"""The Picture Maker (src/vf2_picture_maker.py, src/vf2_people_pictures.py, src/vf2_picture_image.py).

Always run: the parts offered, life stages by age, the order things are drawn in, the PNG sizes, transparency,
the patched and the original look, an empty save, the tool tray's outfits and their Outfit Pictures file.

Run with the B200 desktop object files (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) and the original game
(work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR), else skipped: the game's own code run under emulation
(tests/vf2_people_emu.py) -- CAnimManager::LoadAssets (src/vf2_people_links.json must be what it builds),
GetScaledLinkTo{Next,Prev}Pt, DrawDetailVillager, DrawEventVillager, DrawVillager with DrawCarriedItems,
CFamilyTreeScene::DrawPeep and CInventoryManager::DrawItem (every draw the Picture Maker plans must be the one the
game makes) and BlitRectWithAlpha (every scaled pixel must be the game's) -- and a pixel-exact comparison of
whole pictures with a reference composited independently (Pillow) from the game's sheets.

With a patched game (the folder of VF2_B200_CORE_EXE), the patcher's expansion outfits are checked pixel for
pixel against the patcher's own frames.

Carried items: every cell of carrying.png and collectables_small.png is offered and named, with whether the game
carries it (src/vf2_carried_items.json must be what tests/vf2_carry_scan.py reads from every PlanToCarry call in
the objects, and the patcher's own carries what its generator plans); DrawVillager with DrawCarriedItems is run
for every carried value, several frames, body positions, ages and sexes, and must draw exactly what the Picture
Maker plans; whole pictures with carried items are compared pixel for pixel with an independent composite.
"""
from __future__ import annotations

import gzip
import os
import struct
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("UC_IGNORE_REG_BREAK", "1")

import vf2_people_pictures as pp  # noqa: E402
import vf2_picture_image as pi  # noqa: E402
import vf2_picture_maker as pm  # noqa: E402

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
FIXTURES = ROOT / "tests" / "fixtures" / "vf2_saves"
HAVE_GAME = (GAME_DIR / "Images" / "female_bodies00.png").is_file() and (GAME_DIR / "Assets" / "animpts.dat").is_file()
HAVE_OBJECTS = (OBJ_DIR / "AnimManager.obj").is_file() and (OBJ_DIR / "Villager.obj").is_file()

needs_game = pytest.mark.skipif(not HAVE_GAME, reason="no original game folder (work/vanilla_runtime_payload)")
needs_code = pytest.mark.skipif(not (HAVE_GAME and HAVE_OBJECTS),
                                reason="no B200 desktop object files or no original game folder")


def _patched_game() -> Path | None:
    candidates = [Path(os.environ[name]).parent for name in ("VF2_B200_CORE_EXE", "VF2_KIDS_EXE")
                  if os.environ.get(name)]
    for folder in candidates:
        if pp.GameArt(folder).patched and pp.GameArt(folder).present():
            return folder
    return None


@pytest.fixture(scope="module")
def rig():
    if not (HAVE_GAME and HAVE_OBJECTS):
        pytest.skip("no B200 desktop object files or no original game folder")
    pytest.importorskip("unicorn")
    import vf2_people_emu as pe
    r = pe.PeopleRig(OBJ_DIR, GAME_DIR)
    r.load_assets()
    return r


@pytest.fixture(scope="module")
def art():
    if not HAVE_GAME:
        pytest.skip("no original game folder (work/vanilla_runtime_payload)")
    return pp.GameArt(GAME_DIR)


def _save_folder(tmp_path: Path, fixture: str, slot: int) -> Path:
    (tmp_path / f"Virtual Families 2{slot}.ldw").write_bytes(gzip.decompress((FIXTURES / fixture).read_bytes()))
    return tmp_path


# ====================================================================== the parts (always)
def test_make_your_own_offers_every_head_outfit_and_view():
    fields = {f.key: f for f in pm.custom_fields(patched=False)}
    assert [c.key for c in fields["head"].options] == list(range(50))
    assert [c.key for c in fields["body"].options] == list(range(50))
    assert not any(c.patcher for c in fields["body"].options)
    assert [c.key for c in fields["sex"].options] == [pp.FEMALE, pp.MALE]
    assert [c.key for c in fields["view"].options] == [pm.HOUSE, pm.DETAILS, pm.EVENT, pm.TREE]
    assert [c.key for c in fields["frame"].options] == list(range(56))
    assert [c.key for c in fields["turn"].options] == list(range(12))
    assert [c.key for c in fields["big_turn"].options] == [0, 1, 2]
    assert [c.key for c in fields["babies"].options] == [0, 1, 2, 3]
    patched = {f.key: f for f in pm.custom_fields(patched=True)}
    extra = [c for c in patched["body"].options if c.patcher]
    assert [c.key for c in extra] == [50, 51, 52, 53]          # the patcher's Holiday outfits, marked
    assert [c.key for c in patched["body"].options if not c.patcher] == list(range(50))


def test_a_picked_part_is_the_one_drawn():
    spec = {"sex": pp.MALE, "age": 30 * pp.YEAR, "head": 17, "body": 44, "view": pm.HOUSE, "frame": 12,
            "turn": 3, "babies": 0, "shadow": False}
    person = pm.person_from_spec(spec)
    assert person == pp.Person(sex=pp.MALE, head=17, body=44, age=600, babies=0)
    plan = pm.plan_for(person, pm.HOUSE, frame=12, turn=3, shadow=False)
    body = next(layer for layer in plan if layer.what == "body")
    head = next(layer for layer in plan if layer.what == "head")
    assert (body.image, body.col, body.row) == (581, 12, 44)    # male bodies sheet, frame 12, outfit 44
    assert (head.image, head.col, head.row) == (580, 3, 17)     # male heads, turn 3, head 17
    assert [layer.what for layer in plan] == ["body", "head"]   # no shadow asked for


def test_store_tiers_and_names_are_the_games_generators():
    assert [pp.tier(b) for b in (0, 31, 32, 43, 44, 49, 50, 53)] == [
        "Discount", "Discount", "Department", "Department", "Designer", "Designer",
        "the patcher's Holiday outfits", "the patcher's Holiday outfits"]
    assert pp.outfit_name(pp.FEMALE, 7) == "Female Outfit Body 07"
    assert pp.outfit_name(pp.MALE, 51) == "Male Holiday Outfit Body 51"
    assert pp.hairstyle_name(pp.FEMALE, 7) == "Female Hairstyle 07"


# ====================================================================== life stages (always)
def test_life_stage_by_age_scales_like_the_game():
    assert pp.body_scale(0) == pi.f32(0.5) and pp.head_scale(0) == pi.f32(0.8)
    assert pp.body_scale(279) < 1.0 and pp.head_scale(279) < 1.0
    assert pp.body_scale(280) == 1.0 and pp.head_scale(280) == 1.0
    assert [pp.percent(pp.body_scale(a)) for a in (0, 100, 279, 280)] == [50, 64, 89, 100]
    assert [pp.percent(pp.head_scale(a)) for a in (0, 100, 279, 280)] == [80, 87, 99, 100]
    assert [pp.stage(y * 20) for y in (0, 1, 2, 3, 12, 13, 19, 20, 44, 45)] == [
        "baby", "toddler", "toddler", "child", "child", "teen", "teen", "adult", "adult", "elder"]


def test_the_old_head_from_age_900():
    young, old = pp.Person(pp.FEMALE, 3, 10, 899), pp.Person(pp.FEMALE, 3, 10, 900)
    assert pp.details_plan(young, 1)[1].col == 4 and pp.details_plan(old, 1)[1].col == 10      # bigheads +6
    assert pp.house_plan(young, 9, 5)[-1].col == 5 and pp.house_plan(old, 9, 5)[-1].col == 17  # heads +12
    assert pp.event_plan(old, facing_you=False)[-1].col == 14
    assert pp.tree_plan(old)[1].col == 4                     # the Family Tree always draws the young head


def test_a_child_is_drawn_smaller():
    child = pp.house_plan(pp.Person(pp.MALE, 3, 10, 100), 46, 5)
    adult = pp.house_plan(pp.Person(pp.MALE, 3, 10, 400), 46, 5)
    assert [layer.percent for layer in child] == [64, 64, 87]
    assert [layer.percent for layer in adult] == [100, 100, 100]


# ====================================================================== layer order (always)
def test_layer_order():
    mum = pp.Person(pp.FEMALE, 3, 10, 400, babies=3)
    assert [layer.what for layer in pp.house_plan(mum, 9, 5)] == ["shadow", "body", "head", "baby", "baby", "baby"]
    # facing NE, NW or N (GetDirection 0, 3, 4) the babies are drawn first, behind her
    assert [layer.what for layer in pp.house_plan(mum, 1, 5)] == ["shadow", "baby", "baby", "baby", "body", "head"]
    for frame, behind in ((26, True), (36, True), (40, True), (43, True), (12, False), (18, False), (44, False),
                          (41, False)):
        order = [layer.what for layer in pp.house_plan(mum, frame, 5)]
        assert (order.index("baby") < order.index("body")) is behind, frame
    assert [layer.what for layer in pp.details_plan(mum, 0)] == ["body", "head"]
    assert [layer.what for layer in pp.event_plan(mum)] == ["shadow", "body", "head"]
    assert [layer.what for layer in pp.tree_plan(mum)] == ["body", "head"]
    assert [layer.what for layer in pp.house_plan(pp.Person(pp.FEMALE, 3, 10, 400, babies=1), 9, 5)][-1:] == ["baby"]


# ====================================================================== carried items (always)
def test_every_carried_picture_is_offered_and_named():
    items = pp.carried_items()
    assert len(items) == 13 * 7 + 6 * 16 == 187
    assert len({it.key for it in items}) == 187 and all(it.name and it.reason for it in items)
    assert [it.cell for it in items if it.sheet == pp.CARRYING] == list(range(91))
    assert [it.cell for it in items if it.sheet == pp.COLLECTABLES] == list(range(96))
    by = {it.key: it for it in items}
    used = [it for it in items if it.status == pp.USED]
    assert len(used) == 74 + 77                   # 74 household items, 60 collectibles and 17 pieces of mess
    # unused in the game: no action carries them (the soda bottle only the patcher's patio drinks)
    assert [it.key for it in items if it.status == pp.UNUSED] == [
        "carrying:0", "carrying:33", "carrying:45", "carrying:50", "collectable:91"]
    assert "patcher's added actions carry it" in by["carrying:33"].reason
    assert "no action in the game's code carries value 45" in by["carrying:45"].reason
    # never shown: the baby as a carried value, the empty cells, the cobwebs, the ornaments in the original game
    never = [it.key for it in items if it.status == pp.NEVER]
    assert never == (["carrying:3"] + [f"carrying:{c}" for c in range(79, 91)] + ["collectable:50", "collectable:51"]
                     + [f"collectable:{c}" for c in range(79, 91)] + [f"collectable:{c}" for c in range(92, 96)])
    assert "skips value 3" in by["carrying:3"].reason
    assert "Position not from the game" in by["carrying:80"].reason and not by["carrying:80"].from_game
    assert [it.key for it in items if not it.from_game] == [f"carrying:{c}" for c in range(79, 91)]
    assert "nothing in the game's code makes a cobweb" in by["collectable:50"].reason
    assert pm.NOT_CHECKED in by["collectable:85"].reason                 # the patcher's ornament spawning
    assert by["collectable:0"].name == "Insect 1 (common)" and by["collectable:35"].name == "Raptor fossil 12 (rare)"
    assert by["collectable:36"].name == "Sock 1" and "picking up a sock" in by["collectable:36"].reason
    assert by["carrying:11"].name == "Wrench" and "fixing the kitchen sink" in by["carrying:11"].reason
    assert all(it.label.endswith(f"({it.status})") for it in items if it.status != pp.USED)
    assert all(name in pp.ACTION_WORDS for v in pp.carried_data()["values"].values() for name in v)
    fields = {f.key: f for f in pm.custom_fields(patched=False)}
    assert [c.key for c in fields["carrying"].options] == [None] + [it.key for it in items]
    assert any("unused in the game" in c.label for c in fields["carrying"].options)
    assert [c.key for c in fields["position"].options] == [None] + list(range(pp.POSITIONS))


def test_carried_items_are_drawn_where_the_game_puts_them():
    fish, cap = pp.carried_item("carrying:8"), pp.carried_item("collectable:67")
    adult = pp.Person(pp.FEMALE, 3, 10, 400)
    plan = pp.house_plan(adult, 46, 5, carried=fish, at=(500, 300))
    held = plan[-1]
    assert (held.what, held.image, held.col, held.row, held.percent) == ("carried", 478, 8, 0, 100)
    assert (held.x, held.y) == (500 + 7 - 10, 300 + 33 - 10)       # the carry place, 10 left and 10 up
    cap_layer = pp.house_plan(adult, 46, 5, carried=cap, at=(500, 300))[-1]
    assert (cap_layer.image, cap_layer.col, cap_layer.row, cap_layer.x, cap_layer.y) == (493, 1, 11, 507, 333)
    for position, drop in ((2, 10), (9, 10), (17, 10), (18, 10), (23, 20), (7, 0), (0, 0), (16, 0)):
        assert pp.house_plan(adult, 46, 5, carried=fish, position=position, at=(500, 300))[-1].y == 323 + drop
    child = pp.house_plan(pp.Person(pp.MALE, 3, 10, 100), 46, 5, carried=fish, at=(500, 300))[-1]
    assert child.percent == 100 and (child.x, child.y) == (500 + 4 - 10, 300 + 21 - 10)   # place scaled, item not
    mum = pp.Person(pp.FEMALE, 3, 10, 400, babies=2)
    assert [layer.what for layer in pp.house_plan(mum, 9, 5, carried=fish)] == [
        "shadow", "body", "head", "baby", "baby", "carried"]
    assert [layer.what for layer in pp.house_plan(mum, 1, 5, carried=fish)] == [
        "shadow", "baby", "baby", "carried", "body", "head"]                    # facing NE: behind her
    assert pp.positions_for_frame(48) == [2, 7] and pp.positions_for_frame(55) == [23]
    assert pp.default_position(47) == 17 and pp.default_position(33) == 0 and pp.positions_for_frame(10) == [0]
    plan = pm.plan_for(adult, pm.HOUSE, frame=55, carrying="carrying:8")
    assert plan[-1].y == pp.house_plan(adult, 55, pm.DEFAULT_TURN, carried=fish, position=23)[-1].y
    assert pm.plan_for(adult, pm.DETAILS, carrying="carrying:8") == pm.plan_for(adult, pm.DETAILS)
    assert any("only in the house" in n for n in pm.notes(pm.EVENT, adult, False, carrying="carrying:8"))
    assert any("Wrench" in n for n in pm.notes(pm.HOUSE, adult, False, carrying="carrying:11"))
    assert "carrying Fish" in pm.custom_name({"view": pm.HOUSE, "carrying": "carrying:8"})


def test_the_patchers_own_carries_are_its_generators():
    """PATCHER_CARRIES is every PlanToCarry the patcher's generated furniture code makes."""
    source = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    import re
    enum = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"(eCarrying\w+) = 0x([0-9A-Fa-f]+)", source)}
    found = set()
    for m in re.finditer(r"PlanToCarry\(\s*([^;]*?)\);", source):
        arg = m.group(1).strip()
        if arg in enum:
            found.add(enum[arg])
        elif (r := re.fullmatch(r"static_cast<ECarrying>\(0x([0-9A-Fa-f]+)\)", arg)):
            found.add(int(r.group(1), 16))
        elif (r := re.fullmatch(r"static_cast<ECarrying>\(\s*ldwGameState::GetRandom\((\d+)\) \+ 0x([0-9A-Fa-f]+)\)",
                                arg)):
            found |= set(range(int(r.group(2), 16), int(r.group(2), 16) + int(r.group(1))))
        else:
            assert arg in ("carrying", "ECarrying"), arg                      # the chaise helper's argument
    for m in re.finditer(r"VF2PlanLinkedChaiseAction\([^;]*?,\s*(eCarrying\w+|static_cast<ECarrying>\(0\))", source):
        if m.group(1) in enum:
            found.add(enum[m.group(1)])
    found |= {enum[name] for name in ("eCarryingBook", "eCarryingStudyBook")}   # the lounger's own roll
    assert found == set(pp.PATCHER_CARRIES)


# ====================================================================== the look: patched and original (always)
def test_patched_look_uses_the_patchers_frames_only_for_expansion_outfits():
    holiday = pp.Person(pp.FEMALE, 3, 51, 400)
    body = pp.details_plan(holiday, 1, patched=True)[0]
    assert body.file == "Images/VillagerDetailBodies/Female/Body_51/Frame00.png" and body.image is None
    stock = pp.details_plan(holiday, 1, patched=False)[0]
    assert (stock.file, stock.image, stock.row) == (None, 22, 51)      # the original game: GetCellRect's row 49
    assert (stock.x, stock.y) == (body.x, body.y)                      # the frame goes where the cell would
    house = [layer for layer in pp.house_plan(holiday, 46, 5, patched=True) if layer.what == "body"][0]
    assert house.file == "Images/VillagerBodies/Female/Body_51/actions/Frame14.png"
    walk = [layer for layer in pp.house_plan(pp.Person(pp.MALE, 3, 50, 400), 20, 5, patched=True)
            if layer.what == "body"][0]
    assert walk.file == "Images/VillagerBodies/Male/Body_50/bodies/Frame20.png"
    sit = [layer for layer in pp.house_plan(pp.Person(pp.MALE, 3, 53, 400), 50, 5, patched=True)
           if layer.what == "body"][0]
    assert sit.file == "Images/VillagerBodies/Male/Body_53/sit/Frame03.png"
    assert pp.tree_plan(holiday)[0].file is None                       # the Family Tree is never redirected
    ordinary = pp.Person(pp.FEMALE, 3, 12, 400)
    assert pp.house_plan(ordinary, 46, 5, patched=True) == pp.house_plan(ordinary, 46, 5, patched=False)


@needs_game
def test_the_original_game_draws_row_49_for_an_expansion_outfit(art):
    sheet, rect = art.cell(22, 1, 51)
    assert rect == art.cell(22, 1, 49)[1]
    holiday = pp.render(art, pp.details_plan(pp.Person(pp.FEMALE, 3, 51, 400), 1, patched=False))
    designer = pp.render(art, pp.details_plan(pp.Person(pp.FEMALE, 3, 49, 400), 1, patched=False))
    assert holiday == designer


def test_patched_vs_stock_look_with_a_patched_game():
    folder = _patched_game()
    if folder is None:
        pytest.skip("no patched B200 game folder (VF2_B200_CORE_EXE)")
    patched = pp.GameArt(folder)
    for person, plan_of, frame_file in (
            (pp.Person(pp.MALE, 3, 52, 400), lambda p, look: pp.details_plan(p, 1, patched=look),
             "Images/VillagerDetailBodies/Male/Body_52/Frame00.png"),
            (pp.Person(pp.FEMALE, 3, 50, 400), lambda p, look: pp.house_plan(p, 10, 5, shadow=False, patched=look),
             "Images/VillagerBodies/Female/Body_50/bodies/Frame10.png")):
        body = plan_of(person, True)[0]
        assert body.file == frame_file
        assert pp.render(patched, [body]) == pi.load_png(folder / frame_file)   # the patcher's frame, as it is
        stock_body = plan_of(person, False)[0]
        assert (stock_body.x, stock_body.y) == (body.x, body.y)
        assert pp.render(patched, plan_of(person, True)) != pp.render(patched, plan_of(person, False))


# ====================================================================== sizes and transparency (always)
def _sample() -> pi.Image:
    img = pi.Image(5, 3)
    img.data[(1 * 5 + 2) * 4:(1 * 5 + 2) * 4 + 4] = bytes((200, 10, 20, 255))
    img.data[(1 * 5 + 3) * 4:(1 * 5 + 3) * 4 + 4] = bytes((20, 100, 220, 128))
    return img


def test_the_png_sizes():
    img = _sample()                                        # drawn pixels: 2 x 1
    assert (pi.export(img, scale=1, margin=0).width, pi.export(img, scale=1, margin=0).height) == (2, 1)
    assert (pi.export(img, scale=1).width, pi.export(img, scale=1).height) == (2 + 8, 1 + 8)
    two, four = pi.export(img, scale=2, margin=0), pi.export(img, scale=4, margin=0)
    assert (two.width, two.height, four.width, four.height) == (4, 2, 8, 4)
    assert four.pixel(0, 0) == four.pixel(3, 3) == (200, 10, 20, 255)          # crisp: each pixel a square
    assert four.pixel(4, 0) == (20, 100, 220, 128)
    custom = pi.export(img, size=(20, 0), margin=0)
    assert (custom.width, custom.height) == (20, 10)                            # the shape kept
    assert (pi.export(img, size=(7, 9), margin=0).width, pi.export(img, size=(7, 9), margin=0).height) == (7, 9)
    with pytest.raises(pi.PictureError):
        pi.export(img, size=(0, 0))
    with pytest.raises(pi.PictureError):
        pi.export(img, scale=4, size=None, margin=pi.MAX_SIDE)
    assert pm.export_options("2x") == {"margin": pi.MARGIN, "scale": 2}
    assert pm.export_options("custom", "300", "", margin=False) == {"margin": 0, "size": (300, 0)}
    with pytest.raises(pi.PictureError):
        pm.export_options("custom", "big", "")


def test_transparency(tmp_path):
    img = _sample()
    path = pi.save_png(img, tmp_path / "x.png", scale=2)
    raw = path.read_bytes()
    assert raw[:8] == pi.PNG_MAGIC and raw[24] == 8 and raw[25] == 6           # 8-bit RGBA
    back = pi.decode_png(raw)
    assert back.pixel(0, 0)[3] == 0 and back.pixel(back.width - 1, back.height - 1)[3] == 0
    assert back == pi.export(img, scale=2)
    assert not list(tmp_path.glob(".*.tmp"))                                   # written through a temporary file


@needs_game
def test_a_rendered_picture_is_clear_round_the_person(art):
    img = pi.export(pp.render(art, pp.house_plan(pp.Person(pp.FEMALE, 3, 10, 400), 46, 5)), scale=1)
    corners = [img.pixel(0, 0), img.pixel(img.width - 1, 0), img.pixel(0, img.height - 1),
               img.pixel(img.width - 1, img.height - 1)]
    assert all(c[3] == 0 for c in corners)
    assert any(img.data[3::4])


# ====================================================================== the save (always)
def test_an_empty_save(tmp_path):
    folder = _save_folder(tmp_path, "one_generation_slot3.ldw.gz", 3)
    path = folder / "Virtual Families 23.ldw"
    data = bytearray(path.read_bytes())
    import vf2_save_reader as reader
    for slot in range(reader.VILLAGER_SLOTS):                  # nobody in the house
        data[reader.gs_to_file(reader.GS_VILLAGERS) + slot * reader.VILLAGER_RECORD_SIZE] = 0
    tree = reader.gs_to_file(reader.GS_FAMILY_TREE)
    for record in range(reader.FAMILY_RECORDS):                # nobody in the Family Tree
        data[tree + 4 + record * reader.FAMILY_RECORD_SIZE] = 0
    tray = 8 + pp.GS_TOOL_TRAY
    data[tray:tray + 8 * pp.TRAY_PLACES] = bytes(8 * pp.TRAY_PLACES)    # nothing in the tool tray
    path.write_bytes(bytes(data))
    assert pm.saved_items(folder, 3) == []


def test_the_family_in_a_save(tmp_path):
    folder = _save_folder(tmp_path, "one_generation_slot3.ldw.gz", 3)
    items = pm.saved_items(folder, 3)
    home = [it for it in items if it.group == "At home"]
    assert [it.label for it in home] == ["Elsa", "Paulolo", "Merlino", "Pierur", "Stephor", "Zigo", "Lola", "Snap"]
    assert all(it.views == (pm.HOUSE, pm.DETAILS, pm.EVENT, pm.TREE) for it in home)
    elsa = home[0].person
    assert (elsa.sex, elsa.head, elsa.body, elsa.age // 20) == (pp.FEMALE, 26, 35, 41)
    big = _save_folder(Path(tempfile.mkdtemp(dir=tmp_path)), "ten_generations_slot4.ldw.gz", 4)
    groups = [it.group for it in pm.saved_items(big, 4)]
    assert groups == sorted(groups, key=pm.GROUPS.index)              # at home first, then the rest
    assert "In the Family Tree" in groups and "At home" in groups
    assert all(it.views == (pm.TREE,) for it in pm.saved_items(big, 4) if it.group != "At home")


def _tray_save(base: bytes, places: dict, male: int, female: int) -> bytes:
    data = bytearray(base)
    tray = 8 + pp.GS_TOOL_TRAY
    for place in range(pp.TRAY_PLACES):
        item = places.get(place, 0)
        data[tray + 8 * place:tray + 8 * place + 8] = struct.pack("<ii", item, 1 if item else 0)
    inv = 8 + pp.GS_INVENTORY
    data[inv + pp.INV_MALE_PICTURE:inv + pp.INV_MALE_PICTURE + 4] = struct.pack("<i", male)
    data[inv + pp.INV_FEMALE_PICTURE:inv + pp.INV_FEMALE_PICTURE + 4] = struct.pack("<i", female)
    return bytes(data)


def _sidecar(save: bytes, pictures: list) -> bytes:
    raw = bytearray(pp.SIDECAR_SIZE)
    raw[0:8] = b"VF2OUTFT"
    raw[8:12] = struct.pack("<I", 1)
    raw[12:20] = b"VF2B200\0"
    raw[20:24] = struct.pack("<I", pp.SIDECAR_SIZE)
    raw[24:32] = struct.pack("<Q", pp._fnv(save))
    raw[32:36] = struct.pack("<I", len(save))
    tray = 8 + pp.GS_TOOL_TRAY
    raw[36:36 + 72] = save[tray:tray + 72]
    raw[36 + 72 + 36:36 + 72 + 36 + 36] = struct.pack("<9i", *pictures)
    raw[pp.SIDECAR_SIZE - 8:] = struct.pack("<Q", pp._fnv(bytes(raw[:pp.SIDECAR_SIZE - 8])))
    return bytes(raw)


def test_tool_tray_outfits_keep_their_own_pictures():
    base = gzip.decompress((FIXTURES / "one_generation_slot3.ldw.gz").read_bytes())
    save = _tray_save(base, {2: pp.MALE_OUTFIT, 3: pp.FEMALE_OUTFIT, 4: pp.MALE_OUTFIT, 5: 7}, male=33, female=48)
    stock = pp.tray_outfits(save, None)              # the original game: every outfit of a sex is the last bought
    assert [(o.place, o.sex, o.picture, o.own) for o in stock] == [
        (2, pp.MALE, 33, False), (3, pp.FEMALE, 48, False), (4, pp.MALE, 33, False)]
    sidecar = _sidecar(save, [-1, -1, 12, -1, 44, -1, -1, -1, -1])
    own = pp.tray_outfits(save, sidecar)
    assert [(o.place, o.picture, o.own) for o in own] == [(2, 12, True), (3, 48, False), (4, 44, True)]
    assert pp.tray_outfits(save + b"x", sidecar)[0].picture == 33          # a file for another save is not used
    damaged = bytearray(sidecar)
    damaged[150] ^= 1
    assert pp.tray_outfits(save, bytes(damaged))[0].picture == 33           # nor a damaged one
    assert pp.tray_outfit_plan(pp.MALE, 12)[0].image == 582 and pp.tray_outfit_plan(pp.FEMALE, 12)[0].image == 578


# ====================================================================== the game's own code (inputs)
def _canon_layer(layer) -> tuple:
    if layer.file is not None:
        return ("file", layer.file, layer.x, layer.y, layer.percent)
    return ("cell", layer.image, layer.x, layer.y, layer.col, layer.row, layer.percent)


def _canon_draw(draw) -> tuple:
    kind = draw[0]
    if kind == "window":
        _k, image, x, y, row, col, pct, _flag = draw
        return ("cell", image, x, y, col, row, pct)
    if kind == "window_alpha":
        _k, image, x, y, row, col, alpha, pct, _flag = draw
        assert alpha == 1.0
        return ("cell", image, x, y, col, row, pct)
    if kind == "scene":
        _k, image, x, y, row, col, scale, alpha = draw
        assert alpha == 1.0
        return ("cell", image, x, y, col, row, int(pi.f32(100.0 * pi.f32(scale))))
    if kind == "scene_cell":
        _k, image, x, y, cell, alpha = draw
        cols = pp.IMAGES[image][1]
        return ("cell", image, x, y, cell % cols, cell // cols, 100)
    if kind == "scene_image":
        _k, name, x, y, scale, alpha, _flag = draw
        return ("file", name, x, y, int(pi.f32(100.0 * pi.f32(scale))))
    if kind == "window_image":
        _k, name, x, y, pct, _c, _f = draw
        return ("file", name, x, y, pct)
    if kind == "window_cell":
        _k, image, x, y, cell, pct, _centre = draw
        cols = pp.IMAGES[image][1]
        return ("cell", image, x, y, cell % cols, cell // cols, pct)
    raise AssertionError(draw)


AGES = (0, 1, 57, 100, 199, 279, 280, 500, 899, 900, 1300)
PEOPLE = [(sex, head, body, age) for sex in (0, 1) for (head, body) in ((0, 0), (17, 31), (49, 49), (3, 52))
          for age in AGES]


@needs_code
def test_the_link_file_is_what_the_game_builds():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_vf2_people_links as builder
    assert builder.render(builder.build(OBJ_DIR, GAME_DIR)) == pp.LINKS_FILE.read_text(encoding="utf-8")
    assert (ROOT / "work" / "vf2_people_links.json").read_text(encoding="utf-8") == \
        pp.LINKS_FILE.read_text(encoding="utf-8")


@needs_code
def test_scaled_links_are_the_games(rig):
    checked = 0
    for age in AGES:
        for scale in {pp.body_scale(age), pp.head_scale(age)}:
            for frame in (0, 9, 33, 46, 50, 56):
                for sex in (0, 1):
                    for which in ("next", "prev"):
                        assert pp.link("body", which, frame, sex, 52, scale) == \
                            rig.scaled_link(f"body_{which}", frame, sex, 52, scale)
                        checked += 1
            for turn in (0, 5, 11, 12, 13, 14):
                for sex in (0, 1):
                    for row in (0, 3, 49, 51):
                        assert pp.link("head", "next", turn, sex, row, scale) == \
                            rig.scaled_link("head_next", turn, sex, row, scale)
                        checked += 1
    assert checked > 1000


@needs_code
def test_details_screen_draws_are_the_games(rig):
    for sex, head, body, age in PEOPLE:
        for turn in (0, 1, 2):
            at = (300 + age % 7, 400 - turn)
            game = [_canon_draw(d) for d in rig.detail(sex, head, body, age, turn, at)]
            mine = [_canon_layer(layer) for layer in pp.details_plan(pp.Person(sex, head, body, age), turn, at=at)]
            assert mine == game, (sex, head, body, age, turn)


@needs_code
def test_house_draws_are_the_games(rig):
    for sex, head, body, age in PEOPLE[::3]:
        for frame in range(56):
            turn = frame % 12
            babies = frame % 4 if sex == 1 else 0
            direction = pp.facing(frame)
            at = (500 + frame, 300 + age % 11)
            game = [_canon_draw(d) for d in rig.house(sex, head, body, age, frame, turn, direction & 0xFFFFFFFF,
                                                       babies, at)]
            person = pp.Person(sex, head, body, age, babies)
            mine = [_canon_layer(layer) for layer in pp.house_plan(person, frame, turn, at=at)]
            assert mine == game, (sex, head, body, age, frame, turn, babies)


@needs_code
def test_event_screen_draws_are_the_games(rig):
    for sex, head, body, age in PEOPLE:
        for facing_you in (False, True):
            at = (250, 330)
            game = [_canon_draw(d) for d in rig.event(sex, head, body, age, facing_you, 1.0, at)]
            mine = [_canon_layer(layer) for layer in
                    pp.event_plan(pp.Person(sex, head, body, age), facing_you=facing_you, at=at)]
            assert mine == game, (sex, head, body, age, facing_you)


@needs_code
def test_family_tree_draws_are_the_games(rig):
    for sex, head, body, _age in PEOPLE[::len(AGES)]:
        game = [_canon_draw(d) for d in rig.peep(sex, head, body, (120, 90))]
        mine = [_canon_layer(layer) for layer in pp.tree_plan(pp.Person(sex, head, body), at=(120, 90))]
        assert mine == game


@needs_code
def test_tool_tray_outfit_draws_are_the_games(rig, art):
    for sex in (0, 1):
        for picture in (0, 12, 49):
            game = rig.tray_item(sex, picture, (640, 45))
            assert len(game) == 1 and game[0][-1] == 1                     # the centring flag
            layer = pp.tray_outfit_plan(sex, picture, at=(640, 45))[0]
            assert _canon_layer(layer) == _canon_draw(game[0]) and layer.centre


@needs_code
def test_the_carried_items_file_is_the_games_code():
    pytest.importorskip("capstone")
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_vf2_carried_items as builder
    import vf2_carry_scan as scan
    assert builder.render(builder.build(OBJ_DIR)) == pp.CARRIED_FILE.read_text(encoding="utf-8")
    found = scan.scan(OBJ_DIR)
    assert found["unresolved"] == []
    carried = {v for v in found["values"] if v >= 0}
    assert sorted(set(range(79)) - carried) == [0, 3, 33, 45, 50]          # never in anyone's hands
    assert {"PickCollectable", "PickupSock", "PullingWeeds", "ThrowAwayWrapper", "CleanDirtSmudge"} <= \
        set(found["pickup"])


@needs_code
def test_body_positions_are_the_games(rig):
    assert rig.body_positions() == pp.body_positions()
    assert len(pp.body_positions()) == pp.POSITIONS


@needs_code
def test_carried_item_draws_are_the_games(rig):
    """DrawVillager with DrawCarriedItems for every value a carried item can have (0-174): what the game draws must
    be what the Picture Maker plans, for several frames (both sides), body positions, ages and both sexes. Value 3
    draws nothing as a carried item (the game's baby comes only from Babies on the way)."""
    cases = ((46, 16, 400, 0), (1, 0, 100, 1), (48, 2, 900, 2), (48, 7, 600, 0), (55, 23, 30, 3), (20, 0, 279, 1),
             (47, 17, 1300, 0), (49, 18, 0, 2), (54, 9, 500, 0), (36, 3, 57, 1))
    checked = 0
    for item in pp.carried_items():
        if item.value is None:
            continue
        for k, (frame, position, age, babies) in enumerate(cases):
            sex = (item.cell + k) % 2
            babies = babies if sex == pp.FEMALE else 0
            at = (480 + k, 300 + item.cell % 7)
            game = [_canon_draw(d) for d in rig.house(sex, 7, 20, age, frame, 5, pp.facing(frame) & 0xFFFFFFFF,
                                                       babies, at, carrying=item.value, position=position)]
            plan = pp.house_plan(pp.Person(sex, 7, 20, age, babies), frame, 5, at=at,
                                 carried=None if item.value == 3 else item, position=position)
            assert [_canon_layer(layer) for layer in plan] == game, (item.key, frame, position, age)
            checked += 1
    assert checked == (91 - 12 + 96) * len(cases)
    # carrying.png cells 79-90 are out of the carry draw's reach: values 79-90 draw the collectibles sheet
    for value in range(79, 91):
        draws = rig.house(0, 7, 20, 400, 46, 5, pp.facing(46), 0, (500, 300), carrying=value)
        assert draws[-1][:2] == ("scene_cell", 493) and draws[-1][4] == value - 79


@needs_code
def test_carried_items_pixel_exact_against_an_independent_composite(rig, art):
    """Whole house pictures with carried items (both sheets, babies too, every body-position height) against
    Pillow compositing the game's own sheets where the game's own code draws them."""
    Image = pytest.importorskip("PIL.Image")

    def cell(image, col, row):
        name, cols, rows, across, _down = pp.IMAGES[image]
        if across > 1:
            name = f"{name}{col // (cols // across)}0.png"
            col %= cols // across
            cols //= across
        sheet = Image.open(GAME_DIR / "Images" / name).convert("RGBA")
        cw, ch = sheet.width // cols, sheet.height // rows
        return sheet.crop((col * cw, row * ch, col * cw + cw, row * ch + ch))

    compared = 0
    for sex, age, frame, position, babies, key in ((1, 400, 46, 16, 2, "carrying:8"), (0, 400, 55, 23, 0, "collectable:67"),
                                                   (1, 500, 47, 17, 1, "carrying:64"), (0, 400, 1, 0, 0, "collectable:40"),
                                                   (1, 300, 48, 2, 3, "carrying:33"), (0, 400, 50, 21, 0, "collectable:91")):
        item = pp.carried_item(key)
        draws = rig.house(sex, 7, 20, age, frame, 5, pp.facing(frame), babies, (0, 0), carrying=item.value,
                          position=position)
        draws = [d for d in draws if d[0] != "scene_image"]                       # the shadow: scaled below
        pieces = []
        for d in draws:
            c = _canon_draw(d)
            assert c[-1] == 100
            pieces.append((cell(c[1], c[4], c[5]), c[2], c[3]))
        left = min(x for _p, x, _y in pieces)
        top = min(y for _p, _x, y in pieces)
        right = max(x + p.width for p, x, _y in pieces)
        bottom = max(y + p.height for p, _x, y in pieces)
        want = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
        for piece, x, y in pieces:
            layer = Image.new("RGBA", want.size, (0, 0, 0, 0))
            layer.paste(piece, (x - left, y - top))
            want = Image.alpha_composite(want, layer)
        got = pp.render(art, pp.house_plan(pp.Person(sex, 7, 20, age, babies), frame, 5, shadow=False,
                                           carried=item, position=position))
        assert (got.width, got.height) == want.size and bytes(got.data) == want.tobytes(), key
        compared += 1
    assert compared == 6


@needs_code
def test_every_scaled_pixel_is_the_games(rig, art):
    """game_scaled_cell against BlitRectWithAlpha itself, blended onto an opaque screen as the game blends."""
    cases = [((577, 9, 10), (50, 57, 64, 70, 76, 83, 89, 99)), ((580, 5, 3), (80, 84, 87, 93, 99)),
             ((22, 1, 30), (50, 64, 89)), ((21, 4, 7), (80, 90, 99)), ((582, 14, 44), (70,))]
    for (image, col, row), percents in cases:
        sheet, rect = art.cell(image, col, row)
        cell = sheet.sub(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
        for pct in percents:
            bg = (40 + pct, 90, 160)
            sw, sh = cell.width + 12, cell.height + 12
            out = rig.blit(bytes(cell.data), cell.width, cell.height, (0, 0, cell.width, cell.height), 5, 7, pct,
                           (sw, sh), bg)
            layer = pi.game_scaled_cell(cell, (0, 0, cell.width, cell.height), pct)
            for y in range(sh):
                for x in range(sw):
                    got = tuple(out[(y * sw + x) * 4:(y * sw + x) * 4 + 3])
                    lx, ly = x - 5, y - 7
                    inside = 0 <= lx < layer.width and 0 <= ly < layer.height
                    want = pi.game_blend(bg, layer.pixel(lx, ly)) if inside else bg
                    assert got == want, (image, col, row, pct, x, y)
    shadow = art.picture("Images/peep_shadow1.png")
    out = rig.blit(bytes(shadow.data), shadow.width, shadow.height, (0, 0, shadow.width, shadow.height), 0, 0, 64,
                   (shadow.width, shadow.height), (0, 0, 0))
    layer = pi.game_scaled_cell(shadow, (0, 0, shadow.width, shadow.height), 64)
    for y in range(layer.height):
        for x in range(layer.width):
            assert tuple(out[(y * shadow.width + x) * 4:(y * shadow.width + x) * 4 + 3]) == \
                pi.game_blend((0, 0, 0), layer.pixel(x, y))


@needs_code
def test_pixel_exact_against_an_independent_composite(rig, art):
    """Whole pictures at full size against Pillow compositing the game's own sheets at the places the game's
    own code draws them."""
    Image = pytest.importorskip("PIL.Image")
    sheets: dict = {}

    def cell(image, col, row):
        name, cols, rows, across, down = pp.IMAGES[image]
        if across == 1:
            key = name
        else:
            key = f"{name}{col // (cols // across)}0.png"
            col %= cols // across
        if key not in sheets:
            sheets[key] = Image.open(GAME_DIR / "Images" / key).convert("RGBA")
        sheet = sheets[key]
        cw, ch = sheet.width // (cols // across), sheet.height // rows
        return sheet.crop((col * cw, row * ch, col * cw + cw, row * ch + ch))

    def reference(draws):
        pieces = []
        for d in draws:
            c = _canon_draw(d)
            assert c[-1] == 100
            if c[0] == "file":
                pieces.append((Image.open(GAME_DIR / c[1]).convert("RGBA"), c[2], c[3]))
            else:
                pieces.append((cell(c[1], c[4], c[5]), c[2], c[3]))
        left = min(x for _p, x, _y in pieces)
        top = min(y for _p, _x, y in pieces)
        right = max(x + p.width for p, x, _y in pieces)
        bottom = max(y + p.height for p, _x, y in pieces)
        canvas = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
        for piece, x, y in pieces:
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            layer.paste(piece, (x - left, y - top))
            canvas = Image.alpha_composite(canvas, layer)
        return canvas

    compared = 0
    for sex, head, body, age in [(0, 7, 20, 400), (1, 3, 10, 1000), (1, 26, 35, 820), (0, 49, 49, 300)]:
        cases = [(rig.detail(sex, head, body, age, 1), pp.details_plan(pp.Person(sex, head, body, age), 1)),
                 (rig.house(sex, head, body, age, 46, 5, 6, 2 if sex else 0),
                  pp.house_plan(pp.Person(sex, head, body, age, 2 if sex else 0), 46, 5)),
                 (rig.house(sex, head, body, age, 50, 3, 0, 0), pp.house_plan(pp.Person(sex, head, body, age), 50, 3)),
                 (rig.peep(sex, head, body), pp.tree_plan(pp.Person(sex, head, body)))]
        for draws, plan in cases:
            want = reference(draws)
            got = pp.render(art, plan)
            assert (got.width, got.height) == want.size
            assert bytes(got.data) == want.tobytes(), (sex, head, body, age)
            compared += 1
    assert compared == 16


@needs_game
def test_gdiplus_reads_the_same_bytes_as_the_pure_reader(art):
    if sys.platform != "win32":
        pytest.skip("GDI+ is Windows only")
    for name in ("peep_shadow1.png", "carrying.png", "bigheads00.png"):
        path = GAME_DIR / "Images" / name
        fast = pi._gdiplus_decode(path)
        assert fast is not None
        assert fast == pi.decode_png(path.read_bytes()), name


@needs_game
def test_saved_items_render_in_every_view(tmp_path, art):
    folder = _save_folder(tmp_path, "one_generation_slot3.ldw.gz", 3)
    for item in pm.saved_items(folder, 3):
        for view in item.views:
            img = pm.render_item(art, item, view)
            assert img.width > 10 and img.height > 10 and any(img.data[3::4])


# ====================================================================== the window
@pytest.fixture
def tk_root():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except Exception:
        pytest.skip("no display available for Tk")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_the_tools_tab_opens_one_picture_maker(tk_root, tmp_path, monkeypatch):
    import offline_vf2_patcher_gui as gui
    import vf2_save_backup as sb
    folder = tmp_path / "Documents" / "LDW" / "Virtual Families 2 - Modded B204"
    folder.mkdir(parents=True)
    monkeypatch.setattr(sb, "documents_folder", lambda: tmp_path / "Documents")
    app = gui.VF2PatcherGUI(tk_root)
    maker = app.picture_maker()
    assert maker.window.title() == "Picture Maker" and "picture_maker" in app.help_keys
    assert app.picture_maker() is maker                                     # one at a time
    assert [maker.notebook.tab(t, "text") for t in maker.notebook.tabs()] == ["From my save", "Make your own",
                                                                             "Every picture"]
    assert maker.window.resizable() == (True, True)
    maker.close()


@needs_game
def test_the_window_draws_and_saves(tk_root, tmp_path):
    (tmp_path / "saves").mkdir()
    saves = _save_folder(tmp_path / "saves", "one_generation_slot3.ldw.gz", 3)
    maker = pm.PictureMaker(tk_root, [saves], str(GAME_DIR))
    maker.quiet = True
    assert maker.current_slot() == 3 and maker.art.present() and not maker.art.patched
    node = next(n for n, it in maker.item_nodes.items() if it.label == "Elsa")
    maker.save_tree.selection_set(node)
    maker._picked_saved()
    assert list(maker.save_controls["view"].cget("values")) == ["In the house", "Details screen", "Event screen",
                                                               "Family Tree"]
    shown = maker.shown["save"]
    elsa = next(it for it in maker.items if it.label == "Elsa")
    assert shown == pm.render_item(maker.art, elsa, pm.HOUSE)
    maker.save_controls["view"].current(1)
    maker._show_saved()
    assert maker.shown["save"] == pm.render_item(maker.art, elsa, pm.DETAILS, big_turn=1)
    maker.save_controls["view"].current(0)
    carrying = maker.save_controls["carrying"]
    assert len(carrying.cget("values")) == 188 and carrying.get() == "Nothing"
    carrying.current(1 + 8)                                            # the fish
    maker._show_saved()
    assert maker.shown["save"] == pm.render_item(maker.art, elsa, pm.HOUSE, carrying="carrying:8")
    assert maker.shown["save"] != pm.render_item(maker.art, elsa, pm.HOUSE)
    assert "Carrying: Fish" in maker.save_preview["info"].cget("text")
    assert "carrying Fish" in maker.picture_name("save")
    maker.save_controls["position"].current(1 + 23)
    maker._show_saved()
    assert maker.shown["save"] == pm.render_item(maker.art, elsa, pm.HOUSE, carrying="carrying:8", position=23)
    carrying.current(0)
    maker.save_controls["position"].current(0)
    maker.save_controls["view"].current(1)
    maker._show_saved()
    maker.size_var.set("2x")
    out = maker.save_png("save", str(tmp_path / "elsa.png"))
    picture = pi.decode_png(out.read_bytes())
    assert (picture.width, picture.height) == ((maker.shown["save"].bbox()[2] - maker.shown["save"].bbox()[0] + 8) * 2,
                                               (maker.shown["save"].bbox()[3] - maker.shown["save"].bbox()[1] + 8) * 2)
    folder = maker.save_all(str(tmp_path / "all"))
    assert len(list(folder.glob("*.png"))) == 8 and "8 picture(s) saved" in maker.last_message
    assert maker.custom_spec()["view"] == pm.HOUSE and maker.shown["custom"] is not None
    maker.custom_boxes["body"]["box"].current(12)
    maker._show_custom()
    assert maker.shown["custom"] == pm.render_custom(maker.art, maker.custom_spec())
    assert len(maker.custom_boxes["body"]["box"].cget("values")) == 50          # no patcher outfits in this game
    unused = [c.key for c in pm.carrying_choices()].index("carrying:45")
    maker.custom_boxes["carrying"]["box"].current(unused)                       # an unused one: offered and drawn
    maker._show_custom()
    assert maker.custom_spec()["carrying"] == "carrying:45"
    assert maker.shown["custom"] == pm.render_custom(maker.art, maker.custom_spec())
    assert "Unused in the game" in maker.custom_preview["info"].cget("text")
    maker.close()


def test_what_is_not_checked_is_said():
    holiday = pp.Person(pp.FEMALE, 3, 51, 400)
    assert any(pm.NOT_CHECKED in n for n in pm.notes(pm.HOUSE, holiday, patched=True))
    assert not any(pm.NOT_CHECKED in n for n in pm.notes(pm.HOUSE, holiday, patched=False))
    assert not any(pm.NOT_CHECKED in n for n in pm.notes(pm.DETAILS, pp.Person(pp.FEMALE, 3, 12, 400), True))
    assert any("frame" in n for n in pm.notes(pm.TREE, holiday, patched=True))
    tray = pp.TrayOutfit(2, pp.MALE, 52, True)
    assert any(pm.NOT_CHECKED in n for n in pm.notes(pm.TRAY, None, True, tray))
