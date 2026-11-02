"""The Picture Maker's effects, animals, furniture and food pictures (src/vf2_art_misc.py).

Always run: the tables' shapes, the keys and categories, every effect either started by some code or proven never
started, the usage words.

With the B200 desktop objects (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) and the original game
(work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR), else skipped (tests/vf2_misc_emu.py runs the code):
* CFloatingAnim's own table and the furniture table sFurnitureInfo must be the module's;
* every effect picture: CFloatingAnim::AddAnim, Update and Draw run whole and every frame's draw (picture, cell,
  place, alpha) must be the picture's layer, the cell cut where the game's ldwImageGrid::GetCellRect(index) cuts it;
* every furniture picture: CFurnitureManager::Draw of the item placed in that orientation, and with its animation
  started by CFurnitureManager::SetOnState, every frame of it;
* who starts which effect: every call to CFloatingAnim::AddAnim and to PlanToSpawnAnim* in all 164 objects, with
  the effect it pushes, from code reached from WinMain (or a static initializer); the effects called unused are
  started by none of them, and CSmoke::Add (the only way to switch a smoke emitter on) is never reached.
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("UC_IGNORE_REG_BREAK", "1")

import vf2_art_misc as am  # noqa: E402
import vf2_game_pictures as gp  # noqa: E402

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE_GAME = (GAME_DIR / "Images" / "carrying.png").is_file()
HAVE_OBJECTS = all((OBJ_DIR / f"{n}.obj").is_file() for n in ("FloatingAnim", "FurnitureManager", "ldwImage",
                                                               "theGraphicsManager"))
needs_code = pytest.mark.skipif(not (HAVE_GAME and HAVE_OBJECTS),
                                reason="no B200 desktop object files or no original game folder")


# ====================================================================== always
def test_tables_and_words():
    assert len(am.ANIM_TABLE) == 64 and sorted(am.ANIM_TABLE) == list(range(64))
    started = set(am.ADDED) | set(am.FURNITURE_ANIMS)
    assert not started & set(am.NEVER_ADDED)
    # every effect is either started by something or proven never started
    assert started | set(am.NEVER_ADDED) == set(range(64))
    # the furniture animations are the furniture table's
    anims = {e for anim, _dx, _dy, _d in am.FURNITURE_ANIM.values() for e in anim if e}
    assert anims == set(am.FURNITURE_ANIMS)
    assert len(am.FURNITURE_ITEMS) == 252
    assert {item for item, image in am.FURNITURE_ITEMS if image == 7} == set(range(0x23B, 0x249))
    assert am.fade_alpha(0) == 1.0 and am.fade_alpha(10) == 0.0 and am.fade_alpha(38) == 0.0
    assert abs(am.fade_alpha(4) - 0.6) < 1e-6
    assert am.frame_cell(480, 11) == 0                  # red spray: 12 frames on 11 cells, the row clamps


@pytest.mark.skipif(not HAVE_GAME, reason="no original game folder (work/vanilla_runtime_payload)")
def test_catalogue_entries():
    files = gp.GameFiles(GAME_DIR)
    arts = am.arts(files)
    keys = [a.key for a in arts]
    assert len(keys) == len(set(keys))
    assert all(k.startswith("misc/") for k in keys)
    for a in arts:
        assert a.category.split("/")[0] in gp.CATEGORY_ORDER, a.category
        assert a.why
        if not a.used:
            assert "never" in a.why or "no code" in a.why, a.key
    unused = {a.key.split("/")[2] for a in arts if not a.used}
    assert unused == {am.EFFECTS[e][0] for e in am.NEVER_ADDED}
    assert sum(1 for k in keys if k.startswith("misc/furniture/") and "/on/" not in k) == sum(
        gp.entry_by_id(image).cells for item, image in am.FURNITURE_ITEMS if not am.is_pet(item))
    assert am.USAGE[77][0] is False and all(am.USAGE[i][0] is False for i in (472, 481, 502, 503, 504, 506, 486,
                                                                               488, 519, 520))
    # every picture draws
    for a in arts[::37]:
        image = gp.draw(files, a)
        assert image.width > 1 and image.height > 1, a.key


# ====================================================================== the game's code
@pytest.fixture(scope="module")
def rig():
    import vf2_misc_emu as me
    return me.MiscRig(OBJ_DIR, GAME_DIR)


@pytest.fixture(scope="module")
def cutter():
    """ldwImageGrid::GetCellRect(index): the file and rectangle of cell `index` of an image, run in Unicorn."""
    import vf2_pictures_emu as pe
    image_rig = pe.ImageRig(OBJ_DIR, GAME_DIR / "Images")
    e = image_rig.e
    seen = {}

    def cut(image: int, index: int) -> tuple:
        if (image, index) not in seen:
            obj = e.call("?GetImage@theGraphicsManagerImpl@@QAEPAVldwImage@@H@Z", [image], ecx=image_rig.manager)
            rect = e.alloc(16)
            e.call("?GetCellRect@ldwImageGrid@@QAEXHAAUldwRect@@@Z", [index, rect], ecx=obj)
            seen[(image, index)] = (image_rig.impl_path[e.r32(obj + 4)].replace("\\", "/").lower(),
                                    tuple(e.s32(rect + 4 * k) for k in range(4)))
        return seen[(image, index)]
    return cut


def _layer(draw) -> tuple:
    return (draw.file.replace("\\", "/").lower(), tuple(draw.rect), draw.x, draw.y, round(draw.alpha, 6))


def _recorded(cut, rec) -> tuple:
    kind, image, x, y, cell, alpha = rec
    assert kind == "scene"
    name, rect = cut(image, cell)
    return (name, rect, x, y, alpha)


@needs_code
def test_the_game_tables(rig):
    assert {k: v for k, v in enumerate(rig.table)} == am.ANIM_TABLE
    infos = rig.infos()
    assert [(i["item"], i["image"]) for i in infos] == list(am.FURNITURE_ITEMS)
    assert {i["item"]: (tuple(i["anim"]), tuple(i["dx"]), tuple(i["dy"]), i["delay"]) for i in infos
            if any(i["anim"])} == am.FURNITURE_ANIM
    assert all(i["offsets"] == 0 for i in infos)            # no item snaps its picture


@needs_code
def test_effects_are_drawn_as_the_game_draws_them(rig, cutter):
    files = gp.GameFiles(GAME_DIR)
    arts = {a.key: a for a in am.arts(files)}
    checked = 0
    for effect, (key, _label, _cat) in am.EFFECTS.items():
        frames = rig.effect(effect)
        assert len(frames) == am.ANIM_TABLE[effect][1]
        for k, draws in enumerate(frames):
            art = arts[f"misc/effect/{key}/{k}"]
            assert [_recorded(cutter, d) for d in draws] == [_layer(layer) for layer in art.layers], art.key
            assert art.checked == am.EFFECT_CHECK
            checked += 1
    for effect, key in ((0x0C, "fade_carried"), (0x10, "fade_collectable")):
        frames = rig.effect(effect, fade_cell=0)
        assert len(frames) == am.ANIM_TABLE[effect][1]
        assert all(d[5] == 0.0 for draws in frames[am.FADE_FRAMES - 1:] for d in draws)
        for k in range(am.FADE_FRAMES):
            art = arts[f"misc/effect/{key}/{k}"]
            assert [_recorded(cutter, d) for d in frames[k]] == [_layer(layer) for layer in art.layers], art.key
            checked += 1
    assert checked == sum(1 for a in arts if a.startswith("misc/effect/"))


@needs_code
def test_furniture_is_drawn_as_the_game_draws_it(rig, cutter):
    files = gp.GameFiles(GAME_DIR)
    arts = {a.key: a for a in am.arts(files)}
    checked = 0
    for item, image in am.FURNITURE_ITEMS:
        if am.is_pet(item):
            continue
        entry = gp.entry_by_id(image)
        delay = am.FURNITURE_ANIM.get(item, (0, 0, 0, 0))[3]
        for o in range(entry.cells):
            art = arts[f"misc/furniture/{item}/{o}"]
            placed = [_recorded(cutter, d) for d in rig.furniture(item, o, 0, 0)]
            assert placed == [_layer(layer) for layer in art.layers], art.key
            checked += 1
            frames = rig.furniture_on(item, o, 0, 0, max(1, delay))
            on = [k for k in arts if k.startswith(f"misc/furniture/{item}/{o}/on/")]
            assert len(frames) == len(on), (item, o)
            for k, draws in enumerate(frames):
                art = arts[f"misc/furniture/{item}/{o}/on/{k}"]
                assert placed + [_recorded(cutter, d) for d in draws] == [_layer(la) for la in art.layers], art.key
                checked += 1
    assert checked == sum(1 for a in arts if a.startswith("misc/furniture/"))


# ---------------------------------------------------------------------- who starts which effect
_ADD = re.compile(r"\?(AddAnim@CFloatingAnim|PlanToSpawnAnim\w*@C(Villager|Pet)Plans)@")
# The calls whose effect is not a pushed number, and what it is.
_COMPUTED = {
    "?Update@CRain@@QAEXXZ": "0x12 on water, 0 on the other wet ground (mov eax, 0x12 / xor eax, eax)",
    "?Update@CSmoke@@QAEXXZ": "an emitter's effect; no emitter is ever on",
    "?SetOnState@CFurnitureManager@@QAEXH_NH@Z": "the furniture's animation",
    "?RestoreAnims@CFurnitureManager@@QAEXXZ": "the furniture's animation",
    "?ProcessCurrentPlan@CVillagerPlans@@QAEXAAVCVillager@@@Z": "a plan step made by PlanToSpawnAnim*",
    "?ProcessCurrentPlan@CPetPlans@@QAEXAAVCPet@@@Z": "a plan step made by PlanToSpawnAnim*",
    "?AddAnim@CFloatingAnim@@QAE?BHW4EFloatingAnim@@UldwPoint@@@Z": "its caller's (a wrapper)",
    "?AddAnim@CFloatingAnim@@QAE?BHW4EFloatingAnim@@UldwPoint@@_N@Z": "its caller's (a wrapper)",
}


def _calls(pattern):
    """(caller, callee, the last thing pushed before the call) for every call, in every function of every object,
    to a symbol `pattern` matches."""
    import capstone
    import vf2_people_emu as pe
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = []
    for path in sorted(OBJ_DIR.glob("*.obj")):
        obj = pe.CoffObject(path)
        by_sect = defaultdict(list)
        for _k, (name, value, sect, cls) in obj.symbols.items():
            if sect > 0 and cls in (2, 3) and not name.startswith((".", "$")) and obj.sections[sect - 1]["chars"] & 0x20:
                by_sect[sect].append((value, name))
        for sect, syms in by_sect.items():
            s = obj.sections[sect - 1]
            data = obj.data[s["ptr"]:s["ptr"] + s["size"]]
            rel = {va: obj.symbols[si][0] for va, si, _t in s["relocs"]}
            syms.sort()
            for k, (value, name) in enumerate(syms):
                end = syms[k + 1][0] if k + 1 < len(syms) else s["size"]
                last = None
                for ins in md.disasm(data[value:end], value):
                    if ins.mnemonic == "push":
                        last = ins.op_str
                    elif ins.mnemonic == "call":
                        target = next((rel[a] for a in range(ins.address, ins.address + ins.size) if a in rel), "")
                        if pattern.search(target):
                            out.append((name, target, last))
                        if not _GETTER.match(target):       # Get() takes nothing: the push is still waiting
                            last = None
    return out


_GETTER = re.compile(r"\?Get@\w+@@SAPAV1@XZ$")


def _number(text):
    return int(text, 0) if text and re.fullmatch(r"(0x[0-9a-f]+|\d+)", text) else None


def _effect_calls():
    """(caller, callee, effect or None) for every call to AddAnim / PlanToSpawnAnim*: the effect is the last number
    pushed before the call (the first argument)."""
    return [(caller, callee, _number(last)) for caller, callee, last in _calls(_ADD)]


@pytest.mark.skipif(not HAVE_OBJECTS, reason="no B200 desktop object files")
def test_who_starts_which_effect():
    import vf2_misc_emu as me
    graph = me.CallGraph(OBJ_DIR)
    live = graph.reachable()
    calls = _effect_calls()
    assert len(calls) > 100
    started = set()
    for caller, _callee, effect in calls:
        if effect is None:
            assert caller in _COMPUTED, caller
            continue
        if caller in live:
            started.add(effect)
    started |= {0x12, 0x00}                               # CRain::Update
    assert "?Update@CRain@@QAEXXZ" in live
    started |= set(am.FURNITURE_ANIMS)
    assert "?SetOnState@CFurnitureManager@@QAEXH_NH@Z" in live
    # CSmoke: Add is the only code that switches an emitter on, and it is never reached
    assert "?Add@CSmoke@@QAE?BHUldwPoint@@HW4EFloatingAnim@@H@Z" not in live
    assert not set(am.NEVER_ADDED) & started
    assert started | set(am.NEVER_ADDED) == set(range(64))
    # every function the module names as starting an effect is reached
    for effect, who in am.ADDED.items():
        for words in who:
            m = re.fullmatch(r"(C\w+|the\w+)::(\w+)", words)
            if not m:
                continue
            cls, fn = m.groups()
            names = [n for n in live if n.startswith(f"?{fn}@{cls}@@")]
            assert names, words
            assert any((caller in names and eff == effect) for caller, _c, eff in calls) or effect in (0x12, 0x00), \
                (words, hex(effect))


@pytest.mark.skipif(not HAVE_OBJECTS, reason="no B200 desktop object files")
def test_unused_pictures_are_never_asked_for():
    """No code asks theGraphicsManager for the unused pictures by number (the effects come only through
    CFloatingAnim's table, the furniture only through sFurnitureInfo)."""
    import vf2_misc_emu as me
    live = me.CallGraph(OBJ_DIR).reachable()
    sites = [(caller, _number(last)) for caller, _callee, last in _calls(re.compile(r"@theGraphicsManager@@QAE"))]
    asked = {n for _caller, n in sites}
    asked_live = {n for caller, n in sites if caller in live}
    assert {593, 594, 596, 608, 635} <= asked_live                # the scan finds the birds', butterflies', ball's
    unused = {img for img, (used, _why) in am.USAGE.items() if not used}
    assert unused == {77, 472, 481, 502, 503, 504, 506, 486, 488, 519, 520, 595, 597}
    assert not (unused - {597}) & asked
    # the hummingbird: only its class's constructor asks for it, and nothing reached makes one
    assert {caller for caller, n in sites if n == 597} == {"??0theHummingbirdClass@@IAE@XZ"}
    assert 597 not in asked_live
    assert not {n for n in live if "theHummingbirdClass@@" in n}
    assert 77 not in {image for _item, image in am.FURNITURE_ITEMS}


# ---------------------------------------------------------------------- pets, birds, the ball
@pytest.fixture(scope="module")
def animals():
    import vf2_misc_emu as me
    return me.AnimalRig(OBJ_DIR, GAME_DIR)


def _scaled(cut, rec) -> tuple:
    """A recorded DrawScaled: (file, rect, x, y, percent) as the Picture Maker's layer has it."""
    kind, image, x, y, row, col, scale, alpha = rec
    assert alpha == 1.0
    entry = gp.entry_by_id(image)
    if kind == "image" or entry.kind == "image":
        name = entry.file.lower()
        rect = (0, 0) + gp.GameFiles(GAME_DIR).size(entry.file)
    else:
        name, rect = cut(image, row * (entry.cols or 1) + col)
    return (name, tuple(rect), x, y, int(am.f32(am.f32(scale) * 100)))


def _scaled_layer(files, layer) -> tuple:
    layer = gp.resolve(files, gp.Art("k", "c", "l", (layer,), True, "")).layers[0]
    return (layer.file.lower(), tuple(layer.rect), layer.x, layer.y, layer.percent)


@needs_code
def test_pets_are_drawn_as_the_game_draws_them(animals, cutter):
    files = gp.GameFiles(GAME_DIR)
    arts = {a.key: a for a in am.arts(files)}
    assert animals.pet_frames() == am.PET_FRAMES
    checked = 0
    for kind in range(len(am.PET_NAMES)):
        for frame in list(range(am.PET_FRAMES)) + ["asleep"]:
            asleep = frame == "asleep"
            draws = animals.pet(0x23B + kind, 0x38 if asleep else frame, 0, 0, asleep=asleep)
            art = arts[f"misc/pet/{kind}/{frame}"]
            assert [_scaled(cutter, d) for d in draws] == [_scaled_layer(files, la) for la in art.layers], art.key
            checked += 1
    # the directions: frames 0..7 move to the direction's own eight, and the shadow moves for directions 1 and 3
    for direction in range(8):
        draws = animals.pet(0x23B, 3, 0, 0, direction=direction)
        assert draws[-1][5] == am.PET_DIRECTION_FRAMES[direction] + 3
        sh = am.pet_shadow(0, 3, direction=direction)
        assert (draws[0][2], draws[0][3]) == sh[:2]
    assert checked == sum(1 for k in arts if k.startswith("misc/pet/"))


@needs_code
def test_birds_and_the_ball(animals, cutter):
    files = gp.GameFiles(GAME_DIR)
    arts = {a.key: a for a in am.arts(files)}
    assert animals.bird(0, 0, 1) == []                                 # state 0 is not drawn
    for pose, state, facing, frame in am.BIRD_POSES:
        side = "left" if facing == 0 else "right"
        art = arts[f"misc/bird/{pose}/{side}/{frame}"]
        draws = animals.bird(state, facing, frame)
        assert [_scaled(cutter, d) for d in draws] == [_scaled_layer(files, la) for la in art.layers], art.key
        if state == 1:
            assert animals.bird(2, facing, frame) == draws                # states 1 and 2 draw alike
    for height in (0, 30):
        # a ball in the yard (at 100, 200: the game rounds the float place by adding 0.5 and truncating)
        draws = animals.ball(100.0, 200.0, float(height))
        art = arts[f"misc/ball/{height}"]
        drawn = [_scaled(cutter, d) for d in draws]
        assert [(n, r, x - 100, y - 200, p) for n, r, x, y, p in drawn] == [_scaled_layer(files, la)
                                                                           for la in art.layers], art.key


@needs_code
def test_scaled_shadows_match_the_blitter():
    """The pets' shadow at 80% and 60%: the Picture Maker's scaled picture, blitted at full size, against the game's
    BlitRectWithAlpha scaling the original (both through the game's own blend), within two levels a colour."""
    import vf2_misc_emu as me
    import vf2_people_emu as pe
    rig = pe.PeopleRig(OBJ_DIR, GAME_DIR)
    files = gp.GameFiles(GAME_DIR)
    name = gp.entry_by_id(am.PET_SHADOW).file
    img = files.image(name)
    for percent in (80, 60):
        art = gp.Art("k", "c", "l", (gp.Draw(name, (0, 0, img.width, img.height), 0, 0, percent=percent),), True, "")
        mine = gp.draw(files, art)
        screen = (mine.width + 4, mine.height + 4)
        game = me.blit(rig, bytes(img.data), img.width, img.height, (0, 0, img.width, img.height), 0, 0, 0.9999999,
                       screen, percent=percent)
        ours = me.blit(rig, bytes(mine.data), mine.width, mine.height, (0, 0, mine.width, mine.height), 0, 0,
                       0.9999999, screen)
        assert max(abs(a - b) for a, b in zip(game, ours)) <= 2
        assert sum(1 for a, b in zip(game, ours) if a != b) < len(game) // 4


# ---------------------------------------------------------------------- butterflies and bubbles
@pytest.fixture(scope="module")
def insects():
    import vf2_misc_emu as me
    return me.InsectRig(OBJ_DIR, GAME_DIR)


def _drawn_scaled(files, image, x, y, cell, percent, centre):
    """A recorded ldwGameWindow::DrawScaled as the layer the Picture Maker should have: the game's own DrawScaled
    run whole decides where BlitRectWithAlpha puts the cell and at what scale."""
    import vf2_misc_emu as me
    name, rect = gp.cell_of(files, image, cell)
    cols = gp.entry_by_id(image).cols or 1
    (blit,) = me.draw_scaled(OBJ_DIR, rect, cols, x, y, cell, percent, centre)
    bx, by, brect, alpha, scale = blit
    assert brect == rect and alpha == 1.0 and int(am.f32(am.f32(scale) * 100) + 0.5) == percent
    return (name.lower(), tuple(rect), bx, by, percent)


def _scaled_art_layer(layer):
    return (layer.file.lower(), tuple(layer.rect), layer.x, layer.y, layer.percent)


@needs_code
def test_scaled_place_is_the_games():
    """ScaledClipRect's centring (and none at 100% or uncentred), for the butterflies' cell size and others."""
    import vf2_misc_emu as me
    for w, h in ((24, 22), (25, 21), (7, 9), (100, 100)):
        for percent in (30, 49, 50, 51, 69, 75, 99, 100, 120):
            for centre in (False, True):
                (blit,) = me.draw_scaled(OBJ_DIR, (10, 20, 10 + w, 20 + h), 4, 300, 200, 0, percent, centre)
                assert blit[:2] == am.scaled_place(300, 200, w, h, percent, centre), (w, h, percent, centre)


@needs_code
def test_butterflies_are_drawn_as_the_game_draws_them(insects):
    files = gp.GameFiles(GAME_DIR)
    arts = {a.key: a for a in am.arts(files)}
    keys = [k for k in arts if k.startswith("misc/butterfly/")]
    assert len(keys) == 2 * 5 * 2 * 2
    for kind, percent in (("title", am.TITLE_SHOWN), ("yard", am.YARD_SHOWN)):
        for row, colour in enumerate(am.BUTTERFLY_COLOURS):
            for right in (False, True):
                for frame in (0, 1):
                    art = arts[f"misc/butterfly/{kind}/{colour}/{'right' if right else 'left'}/{frame}"]
                    vx = 3 if right else -3
                    if kind == "title":
                        rec = [insects.butterfly(row, frame, vx, percent)]
                    else:
                        rec = insects.mini(row, frame, vx, percent)
                    got = [_drawn_scaled(files, *d) for d in rec]
                    assert got == [_scaled_art_layer(la) for la in art.layers], art.key
    # moving straight up or down counts as right; a landed one (title 3, yard 2) faces by its place in the list
    assert insects.butterfly(2, 1, 0, 60)[3] == am.butterfly_cell(2, 1, True)
    for index in (0, 1, 2, 5):
        assert insects.butterfly(1, 0, -4, 60, state=3, index=index)[3] == am.butterfly_cell(1, 0, index % 2 == 0)
        (d,) = insects.mini(4, 1, -4, 40, state=2, index=index)
        assert d[3] == am.butterfly_cell(4, 1, index % 2 == 0)


@needs_code
def test_the_butterflies_ranges_are_the_games():
    """Colour row GetRandom(5), size 50 + GetRandom(50) (title) / 30 + GetRandom(40) (yard), wing frame 0 or 1:
    the spawners and updaters run in Unicorn with GetRandom answering its lowest and highest."""
    import vf2_people_emu as pe
    assert am.TITLE_PERCENTS[0] <= am.TITLE_SHOWN <= am.TITLE_PERCENTS[1]
    assert am.YARD_PERCENTS[0] <= am.YARD_SHOWN <= am.YARD_PERCENTS[1]
    for obj, ctor_this, spawn, update, size, pct_off, row_off, frame_off, step, count in (
            ("theButterflyClass", 0x288, "?SpawnButterflies@theButterflyClass@@QAEXXZ",
             "?UpdateButterflies@theButterflyClass@@QAEXUldwPoint@@@Z", 0x34, 0x30, 0x24, 0x28, 0x34, 12),
            ("theMiniButterflyClass", 0x228, "?SpawnButterflies@CMiniButterflyClass@@QAEXH@Z",
             "?Update@CMiniButterflyClass@@QAEXXZ", 0x3C, 0x34, 0x28, 0x2C, 0x3C, 9)):
        for pick in ("low", "high"):
            e = pe.Emu(OBJ_DIR, [obj])
            e.seam("?GetRandom@ldwGameState@@SAHH@Z", lambda em, p=pick: (0 if p == "low" else em.sarg(0) - 1, 0))
            e.seam("?GetCellRect@ldwImageGrid@@QAEXHAAUldwRect@@@Z", lambda em: (
                [em.w32(em.arg(1) + 4 * k, v) for k, v in enumerate((0, 0, 24, 22))], (0, 8))[1])
            gs = e.alloc(0x40)
            vt = e.alloc(0x40)
            e.w32(gs, vt)
            e.seam("__gs_w", lambda em: (1024, 0))
            e.seam("__gs_h", lambda em: (768, 0))
            e.w32(vt + 0x18, e.thunk_of["__gs_w"])
            e.w32(vt + 0x1C, e.thunk_of["__gs_h"])
            this = e.alloc(0x300)
            e.w32(this + 0x284, gs)
            for name, pop in (("?AcquireTarget@theButterflyClass@@QAEXH@Z", 4),
                              ("?AcquireTarget@theButterflyClass@@QAEXHHH@Z", 12),
                              ("?NewTarget@CMiniButterflyClass@@AAEXH@Z", 4),
                              ("?LeaveWorld@CMiniButterflyClass@@AAEXH_N@Z", 8),
                              ("?AcquireTarget@CMiniButterflyClass@@AAEXH@Z", 4),
                              ("?ChooseNewBehavior@CMiniButterflyClass@@AAEXH@Z", 4)):
                if name in e.globals:
                    e.seam(name, lambda em, pop=pop: (0, pop))
            e.call(spawn, [count] if "Mini" in spawn else [], ecx=this)
            lo, hi = (am.TITLE_PERCENTS if count == 12 else am.YARD_PERCENTS)
            rows = {e.s32(this + step * k + row_off) for k in range(count)}
            pcts = {e.s32(this + step * k + pct_off) for k in range(count)}
            assert rows == {0 if pick == "low" else 4} and pcts == {lo if pick == "low" else hi}, (obj, pick)
            for _ in range(60):
                e.call(update, [0, 0] if count == 12 else [], ecx=this)
                assert {e.s32(this + step * k + frame_off) for k in range(count)} <= {0, 1}


@needs_code
def test_bubbles_are_drawn_as_the_game_draws_them(insects):
    files = gp.GameFiles(GAME_DIR)
    arts = {a.key: a for a in am.arts(files)}
    for image in am.BUBBLES:
        stem = am._stem(gp.entry_by_id(image).file)
        for k in range(am.BUBBLE_FRAMES):
            got = [_drawn_scaled(files, *d) for d in insects.bubble(image, k, 100)]
            assert got == [_scaled_art_layer(la) for la in arts[f"misc/bubbles/{stem}/{k}"].layers], (stem, k)
    # the bubble's float drift is truncated into its place; other sizes are drawn uncentred
    assert insects.bubble(473, 3, 120, 50, 60, 2.7, -1.5)[0][1:] == (52, 59, 3, 120, 0)


@needs_code
def test_the_bubbles_ranges_are_the_games():
    """CBubbles::AddBubble: the picture GetRandom(2), first frame GetRandom(5), size 120 - GetRandom(40); Update
    ends a bubble when its frame reaches 10."""
    import vf2_people_emu as pe
    e = pe.Emu(OBJ_DIR, ["Bubbles"])
    picks = {"mode": "low"}
    e.seam("?GetRandom@ldwGameState@@SAHH@Z", lambda em: (0 if picks["mode"] == "low" else em.sarg(0) - 1, 0))
    asked = []
    e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (0, 0))
    e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z", lambda em: (
        asked.append(em.arg(0)), (em.arg(0), 4))[1])
    import vf2_ui_emu as ue
    at = ue.static_address(e, "?bubble@@3PAUSBubbleInstance@@A")
    bubbles = ue.static_address(e, "?Bubbles@@3VCBubbles@@A")
    assert (am.BUBBLE_PERCENTS[1], am.BUBBLE_PERCENTS[0]) == (120, 81)
    for mode, image, frame, percent in (("low", am.BUBBLES[0], 0, 120), ("high", am.BUBBLES[1], 4, 81)):
        picks["mode"] = mode
        e.call("?Reset@CBubbles@@QAEXXZ", ecx=bubbles)
        e.call("?AddBubble@CBubbles@@QAEXUldwPoint@@HMM@Z", [10, 20, 1, 0.0, 0.0], ecx=bubbles)
        assert (asked[-1], e.s32(at + 0x14), e.s32(at + 0x2C), e.s32(at + 0x18)) == (image, frame, percent, 10)
    # Update moves the frame on (GetRandom(13) < 3 once the delay is spent) and ends the bubble at 10
    picks["mode"] = "low"
    e.call("?Reset@CBubbles@@QAEXXZ", ecx=bubbles)
    e.call("?AddBubble@CBubbles@@QAEXUldwPoint@@HMM@Z", [10, 20, 1, 0.0, 0.0], ecx=bubbles)
    seen = set()
    for _ in range(40):
        if not e.read(at + 4, 1)[0]:
            break
        seen.add(e.s32(at + 0x14))
        e.call("?Update@CBubbles@@QAEXXZ", ecx=bubbles)
    assert seen == set(range(am.BUBBLE_FRAMES)) and not e.read(at + 4, 1)[0]


# ---------------------------------------------------------------------- the store's item pictures
@needs_code
def test_store_items_are_drawn_as_the_game_draws_them(cutter):
    import vf2_misc_emu as me
    rig = me.StoreRig(OBJ_DIR, GAME_DIR)
    files = gp.GameFiles(GAME_DIR)
    reached = {am.INVENTORY_ITEMS: set(), am.HOME_GRID: set()}
    for item in range(0, 0x1B0):
        for state in (0, 1):
            draws = rig.item(item, state, 0, 0, 1)
            pic = am.store_picture(item, state)
            if item in am.OUTFITS:
                assert [d[1] for d in draws] in ([582], [578]), hex(item)       # the people's action sheets
                continue
            if pic is None:
                assert draws == [], hex(item)
                continue
            assert [(d[0], d[1], d[4], d[5]) for d in draws] == [("draw", pic[0], pic[1], 100)], hex(item)
            if pic[0] in reached:
                reached[pic[0]].add(am.frame_cell(pic[0], pic[1]))
    # the cells no item reaches are the module's unused ones
    unused = {k for k in am.CELL_UNUSED if k[0] in reached}
    assert unused == {(i, c) for i, n in ((am.INVENTORY_ITEMS, 140), (am.HOME_GRID, 55)) for c in range(n)
                      if c not in reached[i]}
    assert unused == {(608, c) for c in range(34, 38)} | {(609, c) for c in range(42, 50)}
    # every store picture: drawn centred on its place (position 0)
    arts = {a.key: a for a in am.arts(files)}
    keys = [k for k in arts if k.startswith("misc/store/")]
    assert len(keys) > 150
    for key in keys:
        item, state = (int(p) for p in key.split("/")[2:4])
        (d,) = rig.item(item, state, 0, 0, 0)
        entry = gp.entry_by_id(d[1])
        if entry.kind == "image":
            w, h = files.size(entry.file)
            drawn = (entry.file.lower(), (0, 0, w, h), d[2], d[3], 1.0)
        else:
            drawn = _recorded(cutter, ("scene", d[1], d[2], d[3], d[4], 1.0))
        assert [drawn] == [_layer(la) for la in arts[key].layers], key
    # the drop shadow DrawItem adds when asked: two black copies at alpha 0.4, 2 and 4 pixels down and right
    draws = rig.item(3, 0, 100, 100, 0, shadow=True)
    assert [(d[0], d[2] - draws[-1][2], d[3] - draws[-1][3], d[5]) for d in draws[:2]] == [
        ("tinted", 2, 2, 0.4), ("tinted", 4, 4, 0.4)]
