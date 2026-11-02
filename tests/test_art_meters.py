"""The Picture Maker's meters and bars (src/vf2_art_meters.py) against the game's own code.

Always run: the meters' rules. With the B200 desktop objects (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) and the
original game (work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR), else skipped: theVillagerScene::DrawScene,
theLoadingScene::DrawScene (each with the real theContinuousVariableMeter linked), theSlicedVariableMeter /
theVariableMeter::DrawPercentMeter and CAchievement::DrawAchievement run in Unicorn and every draw of every picture
must be theirs; ldwGameWindowImpl::ClipRect must clip as the pictures clip; the unused meters must have no caller;
a bar is compared pixel for pixel with an independent composite (Pillow).
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vf2_art_meters as am  # noqa: E402
import vf2_game_pictures as gp  # noqa: E402

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE_GAME = (GAME_DIR / "Images" / "VD_BG_2.jpg").is_file()
HAVE_OBJECTS = (OBJ_DIR / "theContinuousVariableMeter.obj").is_file()
needs_game = pytest.mark.skipif(not HAVE_GAME, reason="no original game folder (work/vanilla_runtime_payload)")
needs_code = pytest.mark.skipif(not (HAVE_GAME and HAVE_OBJECTS),
                                reason="needs the B200 desktop objects and the original game folder")


@pytest.fixture(scope="module")
def files():
    return gp.GameFiles(GAME_DIR)


@pytest.fixture(scope="module")
def arts(files):
    return {a.key: a for a in am.arts(files)}


def test_the_rules():
    assert am.percent(9, 1500) == 50 and am.percent(9, 5000) == 100 and am.percent(9, -40) == 0
    assert am.percent(8, 150) == 100 and am.percent(8, -1) == 0
    assert am.continuous_calls(8, 50) == [("clip", 617, 323, 762, 356), ("draw", 268, 617, 323),
                                          ("draw", 272, 759, 323), ("draw", 271, 888, 323), ("unclip",)]
    assert am.continuous_calls(9, 1000)[1:3] == [("draw", 269, 617, 188), ("draw", 273, 709, 188)]
    assert am.continuous_calls(7, 50) == [] and am.continuous_calls(14, 50) == []
    assert len(am.sliced_calls(4, 100)) == 145 and len(am.sliced_calls(9, 1000)) == 145
    assert len(am.variable_calls(3, 0, 0, 50)) == 20
    assert am.clip_draw(10, 10, 20, 20, (15, 0, 25, 100)) == (5, 0, 15, 10, 10, 20)
    assert am.clip_draw(30, 10, 20, 20, (15, 0, 30, 100)) is None
    # where the look changes: the end shading from 94, the edge line whole from 2
    assert am.percent(8, 93) * 290 // 100 <= am.END_AT < am.percent(8, 94) * 290 // 100
    assert 94 in am.LEVELS and 93 in am.LEVELS and 2 in am.LEVELS and 1 in am.LEVELS
    # the trough shown: the bar's 300-pixel white trough and 6 pixels around it
    assert am.trough_rect(8) == (611, 317, 923, 362) and am.trough_rect(13) == (369, 494, 681, 539)


@needs_game
def test_the_catalogue(arts):
    assert len(arts) == 55 + 11 + 10 + 5 + 6 + 20
    assert sum(1 for a in arts.values() if not a.used) == 1 + 4 + 6 + 20
    for art in arts.values():
        assert art.category.split("/")[0] == "Meters and bars" and art.key.startswith("meters/")
        assert art.used or "never" in art.why or "Unused" in art.why
    full = arts["meters/details/health/100"]
    assert [layer.file for layer in full.layers] == ["VD_BG_2.jpg", "VD_progressbar-blue.jpg",
                                                    "VD_line-blue.jpg", "VD_fade-02.png"]
    assert [layer.file for layer in arts["meters/details/health/0"].layers] == ["VD_BG_2.jpg"]
    assert full.layers[1].rect == (0, 0, 290, 33)


@needs_game
def test_every_picture_draws(files, arts):
    for art in arts.values():
        image = gp.draw(files, art)
        assert image.width * image.height > 1 and image.bbox() is not None, art.key


# ------------------------------------------------------------------ against the game
def _villager_scene(rig):
    e = rig.e
    villager = e.alloc(0x8000)
    scene = e.alloc(0x400)
    e.seam("?GetMousePosition@ldwEventManager@@SA?AUldwPoint@@XZ", lambda em: (em.arg(0), 0))
    e.seam("?VillagerExists@CVillagerManager@@QAE_NH_N@Z", lambda em: (1, 8))
    e.seam("?GetVillager@CVillagerManager@@QAEAAVCVillager@@H@Z", lambda em: (villager, 4))
    e.seam("?DrawDetailVillager@CVillager@@QAEXUldwPoint@@_N@Z", lambda em: (0, 12))
    return villager, scene


@needs_code
def test_the_details_bars_are_the_games(files, arts):
    import vf2_ui_emu as ue
    rig = ue.UiRig(OBJ_DIR, GAME_DIR, ["theVillagerScene", "theContinuousVariableMeter"])
    villager, scene = _villager_scene(rig)
    background = gp.cell_of(files, am.DETAILS_BG, 0)
    for colour, name, _what in am.DETAILS:
        for p in am.LEVELS:
            for offset, value in am.details_numbers(colour, p).items():
                rig.e.w32(villager + offset, value)
            draws = rig.run("?DrawScene@theVillagerScene@@MAEXXZ", ecx=scene)
            # the background whole at (0, 0) first, the meters' calls between DrawDetailVillager and main_no-comm
            assert draws[0] == ("draw", am.DETAILS_BG, -1, 0, 0, 1.0)
            own = [d for d in draws if d[0] in ("clip", "unclip") or d[1] in am.CONTINUOUS_IDS]
            assert len(own) == 25 and [d[0] for d in own[::5]] == ["clip"] * 5
            index = [c for c, _n, _w in am.DETAILS].index(colour)
            mine = own[5 * index:5 * index + 5]
            art = arts[f"meters/details/{name.lower()}/{p}"]
            want = ue.art_layers(art)
            assert ue.as_layers(files, mine) == want[1:], (name, p)
            # the trough: that part of the background, at the same place
            l, t, r, b = art.layers[0].rect
            assert art.layers[0].file == background[0] and (art.layers[0].x, art.layers[0].y) == (l, t)
            # nothing else the screen draws covers it
            for d in draws[1:]:
                if d[0] != "draw" or d[1] in am.CONTINUOUS_IDS:
                    continue
                w, h = gp.cell_of(files, d[1], max(0, d[2]))[1][2:]
                assert d[3] >= r or d[3] + w <= l or d[4] >= b or d[4] + h <= t, (name, d)


@needs_code
def test_the_loading_bar_is_the_games(files, arts):
    import vf2_ui_emu as ue
    rig = ue.UiRig(OBJ_DIR, GAME_DIR, ["theLoadingScene", "theContinuousVariableMeter"])
    rig.e.seam("?DrawLoadingLogo@CDistributor@@QAEXHH@Z", lambda em: (0, 8))
    screen = rig.vtable_object(0x40, {6: lambda em: (1024, 0)})
    scene = rig.e.alloc(0x100)
    rig.e.w32(scene + 0x10, screen)
    for p in am.LEVELS:
        rig.e.w32(scene + 0x28, p)
        draws = rig.run("?DrawScene@theLoadingScene@@MAEXXZ", ecx=scene)
        assert draws[0] == ("draw", am.LOADING_BG, 0, 0, 0, 1.0)
        assert draws[1] == ("draw", am.LOAD_FRAME, -1, 375, 500, 1.0)
        art = arts[f"meters/loading/{p}"]
        want = ue.art_layers(art)
        assert ue.as_layers(files, draws[1:]) == want[1:], p
        l, t, _r, _b = art.layers[0].rect
        assert art.layers[0].file == "loading.jpg" and (art.layers[0].x, art.layers[0].y) == (l, t)


@needs_code
def test_every_level_of_every_bar_is_the_games():
    """DrawPercentMeter for every colour and many values (beyond the pictures' levels) makes am's calls."""
    import vf2_pictures_emu as pe
    rig = pe.MeterRig(OBJ_DIR)

    def calls(mine):
        return [(c[0], *c[1:]) if c[0] != "fill" else
                ("fill", *c[1:5], *(gp.pi.f32(v) for v in c[5])) for c in mine]
    for colour in range(0, 15):
        for value in (-5, 0, 1, 2, 3, 29, 30, 31, 50, 93, 94, 99, 100, 101, 999, 1000, 2999, 3000, 3001, 5000):
            assert rig.draw("continuous", colour, value) == calls(am.continuous_calls(colour, value))
            assert rig.draw("sliced", colour, value) == calls(am.sliced_calls(colour, value))
            assert rig.draw("variable", colour, value) == calls(am.variable_calls(colour, 100, 200, value))
    rng = random.Random(7)
    for _ in range(400):
        x, y, w, h = rng.randint(-40, 120), rng.randint(-40, 120), rng.randint(0, 60), rng.randint(0, 60)
        clip = (rng.randint(0, 50), rng.randint(0, 50), rng.randint(0, 120), rng.randint(0, 120))
        assert rig.clip_rect(x, y, w, h, clip) == am.clip_draw(x, y, w, h, clip), (x, y, w, h, clip)


@needs_code
def test_the_unused_meters_and_pieces_are_the_games(files, arts):
    import vf2_pictures_emu as pe
    import vf2_ui_emu as ue
    rig = pe.MeterRig(OBJ_DIR)
    for p in am.SLICED_LEVELS:
        draws = [("draw", c[1], -1, c[2], c[3], 1.0) for c in rig.draw("sliced", 3, p)]
        assert ue.as_layers(files, draws) == ue.art_layers(arts[f"meters/unused/sliced/{p}"])
    for colour in (0, 1, 2, 3):
        for p in (am.VARIABLE_LEVELS if colour < 3 else (3, *am.VARIABLE_LEVELS[1:])):
            draws = [("draw", c[1], -1, c[2] - 100, c[3] - 200, 1.0) if c[0] == "draw" else
                     ("fill", c[1] - 100, c[2] - 200, c[3] - 100, c[4] - 200, c[5:9])
                     for c in rig.draw("variable", colour, p)]
            assert ue.as_layers(files, draws) == ue.art_layers(arts[f"meters/unused/variable/{colour}/{p}"])
    # the end shading piece: a full bar's last draw, moved to (0, 0)
    full = ue.as_layers(files, [("draw", c[1], -1, c[2], c[3], 1.0) if c[0] == "draw" else c
                                for c in rig.draw("continuous", 8, 100)])
    piece = ue.art_layers(arts["meters/pieces/end-shading"])
    assert [(d[1], d[2]) for d in full[-1:]] == [(d[1], d[2]) for d in piece]
    # the pieces never drawn: no colour, no value draws them
    for colour in range(8, 14):
        for value in range(0, 101, 7):
            ids = {c[1] for c in rig.draw("continuous", colour, value) if c[0] == "draw"}
            assert not ids & {am.FADE_START, am.SLICE_BLUE, am.SLICE_RED, am.LOAD_COLOUR}


@needs_code
def test_the_unused_meters_have_no_caller():
    import vf2_ui_emu as ue
    for cls in ("theSlicedVariableMeter", "theVariableMeter"):
        refs = ue.references(OBJ_DIR, f"@{cls}@@")
        assert refs and all(obj == cls for obj, _fn, _sym in refs), refs
    # the pictures they alone fetch: no other code names them as an image
    for image, owners in ((am.LOAD_COLOUR, {"theVariableMeter"}),
                          (am.SLICE_RED, {"theContinuousVariableMeter", "theSlicedVariableMeter"}),
                          (am.SLICE_BLUE, {"theContinuousVariableMeter", "theSlicedVariableMeter"}),
                          (am.FADE_START, {"theContinuousVariableMeter"})):
        assert {obj for obj, _fn in ue.image_sites(OBJ_DIR, image)} == owners, image
    # theContinuousVariableMeter reads +8, +0xC and +0x18 nowhere but its constructor
    assert ue.member_reads(OBJ_DIR, "theContinuousVariableMeter",
                           "?DrawPercentMeter@theContinuousVariableMeter@@QAEXW4COMeterColorEnum@@H@Z") \
        >= {0x10, 0x14, 0x1C, 0x20, 0x24}
    assert not ue.member_reads(OBJ_DIR, "theContinuousVariableMeter",
                               "?DrawPercentMeter@theContinuousVariableMeter@@QAEXW4COMeterColorEnum@@H@Z") \
        & {0x8, 0xC, 0x18}


@needs_code
def test_no_technology_bar():
    """CTech and CVillagerSkills draw nothing: none of their functions calls a drawing function."""
    import vf2_ui_emu as ue
    for obj in ("Tech", "VillagerSkills"):
        called = ue.called_symbols(OBJ_DIR, obj)
        assert not [s for s in called if "theGraphicsManager" in s or "ldwGameWindow" in s or "Meter" in s], obj


@needs_code
def test_the_achievement_bar_is_the_games(files, arts):
    import vf2_ui_emu as ue
    rig = ue.UiRig(OBJ_DIR, GAME_DIR, ["Achievement"])
    ach = rig.e.alloc(0x1000)
    obj = rig.e.objs[0]                     # achievementList is a static of Achievement.obj
    table = next(obj.addr[sect] + value for name, value, sect, _cls in obj.symbols.values()
                 if name == "?achievementList@@3PAUsAchievementListEntry@@A" and sect > 0)
    index = next(k for k in range(0x5F) if rig.e.s32(table + 28 * k + 4) == 100)
    for p in am.ACH_LEVELS:
        rig.e.write(ach + 12 * index, bytes(1))
        rig.e.w32(ach + 12 * index + 4, p)
        draws = rig.run("?DrawAchievement@CAchievement@@QAEXHHH_NM@Z", [0, 0, index, 0, 1.0], ecx=ach)
        assert ue.as_layers(files, draws) == ue.art_layers(arts[f"meters/achievement/{p}"]), p
    rig.e.write(ach + 12 * index, b"\x01")
    draws = rig.run("?DrawAchievement@CAchievement@@QAEXHHH_NM@Z", [0, 0, index, 0, 1.0], ecx=ach)
    assert ue.as_layers(files, draws) == ue.art_layers(arts["meters/achievement/finished"])
    # a count reaching the goal finishes the achievement (so a full bar is never shown)
    rig.e.write(ach + 12 * index, bytes(1))
    rig.e.w32(ach + 12 * index + 4, 99)
    rig.e.seam("?QueueAchievementNotify@CAchievement@@AAEXW4EAchievement@@@Z", lambda em: (0, 4))
    rig.e.seam("?Seconds@CGameTime@@QAE?BIXZ", lambda em: (0, 0))
    rig.e.call("?IncrementProgress@CAchievement@@QAEXW4EAchievement@@H@Z", [index, 1], ecx=ach)
    assert rig.e.read(ach + 12 * index, 1) == b"\x01"


@needs_code
def test_a_bar_pixel_exact_against_an_independent_composite(files, arts):
    """A few bars drawn by the Picture Maker equal Pillow's composite of the game's recorded draws (the
    trough, then each whole picture pasted with its alpha, cut to the clipping rectangle)."""
    from PIL import Image
    import vf2_pictures_emu as pe
    rig = pe.MeterRig(OBJ_DIR)
    for colour, p, key in ((8, 50, "health"), (9, 94, "progress"), (12, 1, "energy"), (11, 100, "fed")):
        art = arts[f"meters/details/{key}/{p}"]
        mine = gp.draw(files, art)
        l, t, _r, _b = am.trough_rect(colour)
        # the pictures' pixels as the game's loader reads them (the JPEGs decoded as its libjpeg decodes them)
        bg = gp.layer_image(files, art.layers[0])
        canvas = Image.frombytes("RGBA", (bg.width, bg.height), bytes(bg.data))
        clip = None
        for call in rig.draw("continuous", colour, am.details_value(colour, p)):
            if call[0] == "clip":
                clip = call[1:]
            elif call[0] == "unclip":
                clip = None
            else:
                pic = files.image(gp.cell_of(files, call[1], 0)[0])
                src = Image.frombytes("RGBA", (pic.width, pic.height), bytes(pic.data))
                x, y = call[2], call[3]
                box = (max(x, clip[0]), max(y, clip[1]), min(x + src.width, clip[2]), min(y + src.height, clip[3]))
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                part = src.crop((box[0] - x, box[1] - y, box[2] - x, box[3] - y))
                layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                layer.paste(part, (box[0] - l, box[1] - t))
                canvas = Image.alpha_composite(canvas, layer)
        assert mine.width == canvas.width and mine.height == canvas.height
        assert bytes(mine.data) == canvas.tobytes(), (colour, p)
