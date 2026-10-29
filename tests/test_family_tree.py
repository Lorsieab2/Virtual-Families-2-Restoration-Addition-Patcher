"""The Family Tree Maker (src/vf2_genealogy.py, vf2_family_tree.py, vf2_family_tree_window.py, vf2_member_info.py,
the Tools tab link): the family read from a save (real-save fixtures, copied, and synthetic saves laid out as
CFamilyTree / CVillager::SaveState write them, docs/vf2-save-format.md), the picture, the editor and the shipped
pictures.  The saves are only read; every file the tests write is in tmp_path."""
from __future__ import annotations

import gzip
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_family_tree as ft  # noqa: E402
import vf2_genealogy as gen  # noqa: E402
import vf2_save_reader as r  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "vf2_saves"


# ---------------------------------------------------------------- building saves
def fixture(name: str) -> bytes:
    return gzip.decompress((FIX / name).read_bytes())


def blank_save(nickname: str = "Testfamily") -> bytearray:
    b = bytearray(r.GAME_FILE_SIZE)
    b[0:4] = b"ldwg"
    struct.pack_into("<qI", b, 4, 1_700_000_000, r.GAME_DATA_SIZE)
    struct.pack_into("<3i", b, r.gs_to_file(r.GS_PENDING_BABIES), -1, -1, -1)
    put_str(b, r.gs_to_file(r.GS_NICKNAME), nickname, 20)
    return b


def put_str(b: bytearray, off: int, text: str, size: int) -> None:
    raw = text.encode("cp1252")[:size - 1]
    b[off:off + size] = raw + b"\0" * (size - len(raw))


def villager(b: bytearray, slot: int, name: str, sex: int = 0, age: int = 600, head: int = 1, body: int = 1,
             active: int = 1, left: int = 0, health: int = 90, cause: int = -1, father: str = "Joey",
             mother: str = "Mum", preg: int = 0, babies: int = 0, career: int = -1, level: int = 0) -> None:
    v = r.gs_to_file(r.GS_VILLAGERS) + slot * r.VILLAGER_RECORD_SIZE
    b[v], b[v + 1] = active, left
    struct.pack_into("<ii", b, v + 8, age, sex)
    put_str(b, v + 8 + 0x10, name, 25)
    struct.pack_into("<ii", b, v + 8 + 0x2C, head, body)
    put_str(b, v + 8 + 0x34, father, 25)
    put_str(b, v + 8 + 0x4E, mother, 25)
    struct.pack_into("<ii", b, v + 0xA8 + 0x0C, health, cause)
    struct.pack_into("<ii", b, v + 0xA8 + 0x24, preg, babies)
    struct.pack_into("<ii", b, v + 0x140, career, level)


def peep(b: bytearray, record: int, place: int, name: str, sex: int = 0, head: int = 1, body: int = 1,
         slot: int = 0, heir: int = -1, present: int = 1, likes: str = "", dislikes: str = "",
         career: int = -1) -> None:
    """place 0 = parent 1, 1 = parent 2, 2 + k = child k (the child count follows)."""
    rec = r.gs_to_file(r.GS_FAMILY_TREE) + 4 + record * r.FAMILY_RECORD_SIZE
    b[rec] = 1
    at = rec + (0x04, 0xDC)[place] if place < 2 else rec + 0x1B8 + (place - 2) * r.PEEP_RECORD_SIZE
    put_str(b, at, name, 25)
    b[at + 0x1A] = present
    struct.pack_into("<iiiiii", b, at + 0x1C, sex, head, body, slot, heir, career)
    put_str(b, at + 0x34, likes, 0x28)
    put_str(b, at + 0x5D, dislikes, 0x28)
    if place >= 2:
        count = struct.unpack_from("<i", b, rec + 0x1B4)[0]
        struct.pack_into("<i", b, rec + 0x1B4, max(count, place - 1))


def two_generations() -> bytes:
    """Ann (founder, died with children) and Bob; their children Cal (the heir), Dee (left home, record no longer
    in use), Ivy (adopted: no parents' names) and Fay (died); Cal married Eve; Eve expects Gus."""
    b = blank_save()
    villager(b, 0, "Ann", sex=1, head=1, body=1, health=0, cause=2, active=0)
    villager(b, 1, "Bob", head=2, body=2, age=700)
    villager(b, 2, "Cal", head=4, body=4, age=200)
    villager(b, 3, "Dee", sex=1, head=5, body=5, age=400, active=0, left=1)
    villager(b, 4, "Ivy", sex=1, head=6, body=6, age=100, father="", mother="")
    villager(b, 5, "Cal", head=4, body=4, age=620)                       # the heir: the adult clone
    villager(b, 6, "Eve", sex=1, head=7, body=7, age=600, preg=590, babies=1)
    villager(b, 7, "Gus", head=8, body=8, age=0, active=0)
    villager(b, 8, "Fay", sex=1, head=9, body=9, age=60, health=0, cause=0, active=0)
    peep(b, 0, 0, "Ann", sex=1, head=1, body=1, slot=-1)
    peep(b, 0, 1, "Bob", head=2, body=2, slot=1)
    peep(b, 0, 2, "Cal", head=4, body=4, slot=2, heir=0)
    peep(b, 0, 3, "Dee", sex=1, head=5, body=5, slot=3, heir=0)
    peep(b, 0, 4, "Ivy", sex=1, head=6, body=6, slot=4, heir=0)
    peep(b, 0, 5, "Fay", sex=1, head=9, body=9, slot=-1, heir=0)
    peep(b, 1, 0, "Cal", head=4, body=4, slot=5, heir=0)
    peep(b, 1, 1, "Eve", sex=1, head=7, body=7, slot=6)
    peep(b, 1, 2, "Gus", head=8, body=8, slot=7, heir=0)
    struct.pack_into("<3i", b, r.gs_to_file(r.GS_PENDING_BABIES), 7, -1, -1)
    return bytes(b)


def family(data: bytes, folder: Path | None = None, slot: int = 1) -> gen.Village:
    v = gen.build_family(r.parse_family_save(data), slot, data=data)
    gen.finish(v)
    return v


def by_name(village: gen.Village, name: str) -> gen.Person:
    hits = [p for p in village.people.values() if p.name == name]
    assert len(hits) == 1, [(p.name, p.seat) for p in hits]
    return hits[0]


def snapshot(folder: Path) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def write_save(folder: Path, data: bytes, slot: int = 1) -> Path:
    path = folder / f"Virtual Families 2{slot}.ldw"
    path.write_bytes(data)
    return path


# ---------------------------------------------------------------- real saves (copied fixtures)
def test_real_one_generation():
    v = family(fixture("one_generation_slot3.ldw.gz"), slot=3)
    elsa, paulolo = by_name(v, "Elsa"), by_name(v, "Paulolo")
    assert v.tribe == "Lorsieab2" and elsa.how == "Founder" and paulolo.how == "Married in"
    kids = [p for p in v.people.values() if p.generation == 2]
    assert len(kids) == 6 and all(k.alive and k.mother == elsa.id and k.father == paulolo.id for k in kids)
    assert elsa.years == 41


def test_real_ten_generations_link_every_heir():
    v = family(fixture("ten_generations_slot4.ldw.gz"), slot=4)
    assert v.generations == 10
    heirs = [p for p in v.people.values() if p.heir]
    assert len(heirs) == 9
    for p in heirs:                                  # an heir is a child of the generation before
        assert p.father is not None and p.mother is not None


def test_real_full_tree_and_a_baby_on_the_way():
    v = family(fixture("pending_birth_slot1.ldw.gz"))
    assert v.generations == 30 and any("30 generations" in n for n in v.notes)
    baby = by_name(v, "Trishania")
    seat = {p.seat: p for p in v.people.values()}
    assert baby.upcoming and seat["g30.p2"].name == "Wizzy" and baby.mother == seat["g30.p2"].id
    assert baby.father == by_name(v, "Oslo").id and by_name(v, "Oslo").heir
    # Children whose villager record is no longer in use but carries the left-home flag.
    katania = [p for p in v.people.values() if p.name == "Katania" and p.generation == 30]
    assert katania and katania[0].left_home and not katania[0].alive


def test_every_real_fixture_draws():
    for name in ("one_generation_slot3.ldw.gz", "ten_generations_slot4.ldw.gz", "pending_birth_slot1.ldw.gz"):
        v = family(fixture(name))
        edits = ft.Edits()
        ft.arrange(v, edits)
        assert "<svg" in ft.to_svg(ft.scene(ft.layout(v, edits), gen.GAME_TITLE, {}), {})


def test_a_legacy_or_missing_save_is_a_clear_error(tmp_path):
    with pytest.raises(gen.GenealogyError, match="could not be read"):
        gen.load_village(tmp_path, gen.GAME, 3)
    write_save(tmp_path, fixture("legacy_header_slot5.ldw.gz"), 3)
    with pytest.raises(gen.GenealogyError, match="not a Virtual Families 2 save"):
        gen.load_village(tmp_path, gen.GAME, 3)


# ---------------------------------------------------------------- synthetic saves
def test_synthetic_family_from_the_save():
    v = family(two_generations())
    ann, bob, cal, dee, ivy, fay, eve, gus = (by_name(v, n) for n in ("Ann", "Bob", "Cal", "Dee", "Ivy", "Fay",
                                                                     "Eve", "Gus"))
    assert ann.gone == "died" and ann.how == "Founder" and ann.cause == "Old age"
    assert bob.alive and bob.how == "Married in" and ann.generation == bob.generation == 1
    assert cal.heir and cal.alive and cal.years == 31 and cal.father == bob.id and cal.mother == ann.id
    assert dee.left_home and not dee.alive and any("left-home flag" in u for u in dee.unknowns)
    assert ivy.adopted and ivy.how == "Adopted" and any("Adoption Services or The Little Visitor" in u
                                                        for u in ivy.unknowns)
    assert fay.gone == "died" and fay.cause == "Disease" and fay.years == 3
    assert eve.expecting and gus.upcoming and gus.father == cal.id and gus.mother == eve.id
    assert cal.generation == eve.generation == 2 and gus.generation == 3


def test_causes_of_death_say_what_is_unconfirmed():
    assert [gen.cause_words(c) for c in (0, 1, 2)] == ["Disease", "Starvation", "Old age"]
    assert "UNCONFIRMED" in gen.cause_words(3) and "UNCONFIRMED" in gen.cause_words(-1)


def test_a_spouse_who_died_with_no_children_is_still_in_the_save():
    """ReportDeath clears only parent 2's present byte (VERIFIED): the name stays until a new marriage."""
    b = blank_save()
    villager(b, 0, "Ann", sex=1, head=1)
    villager(b, 1, "Bob", head=2, body=2, health=0, cause=1, active=0)
    peep(b, 0, 0, "Ann", sex=1, head=1, slot=0)
    peep(b, 0, 1, "Bob", head=2, body=2, slot=1, present=0)
    v = family(bytes(b))
    bob = by_name(v, "Bob")
    assert bob.gone == "died" and bob.how == "Married in" and bob.cause == "Starvation" and bob.generation == 1


def test_parent_two_copied_over_a_founder_who_died_childless():
    """ReportDeath copies parent 2 over parent 1 and clears parent 2's present byte: the two entries alike."""
    b = blank_save()
    villager(b, 1, "Bob", head=2, body=2)
    for place in (0, 1):
        peep(b, 0, place, "Bob", head=2, body=2, slot=1, present=1 - place)
    v = family(bytes(b))
    bob = by_name(v, "Bob")
    assert bob.how == "Married in" and gen.is_arrival(bob) and any("no longer names" in u for u in bob.unknowns)
    assert len(v.people) == 1


def test_someone_in_the_house_the_tree_does_not_hold_is_shown_apart():
    b = bytearray(two_generations())
    villager(b, 9, "Zed", head=3, body=3)
    v = family(bytes(b))
    zed = by_name(v, "Zed")
    assert zed.seat == "house.9" and any("does not record them" in u for u in zed.unknowns)


def test_children_seven_to_twenty_eight_from_the_sidecar(tmp_path):
    data = bytearray(two_generations())
    villager(data, 10, "Kit", head=11, body=11, age=40)
    data = bytes(data)
    write_save(tmp_path, data)
    extra = [gen.ExtraChild(10, 0, "alive", 11, 11, 40, "Kit"), gen.ExtraChild(11, 1, "dead", 12, 12, 20, "Lia")]
    side = gen.make_children_sidecar(data, 2, 5, 0, extra)
    path = gen.children_sidecar_path(tmp_path, 1)
    path.parent.mkdir(parents=True)
    path.write_bytes(side)
    assert path.name == "Virtual Families 21.ldw.dat" and path.parent.name == "Children"
    v = gen.load_village(tmp_path, gen.GAME, 1)
    kit, lia = by_name(v, "Kit"), by_name(v, "Lia")
    assert kit.alive and kit.father == by_name(v, "Cal").id and lia.gone == "died" and kit.generation == 3
    # Another save's sidecar is not used; a damaged one is refused as b200kids refuses it.
    write_save(tmp_path, two_generations())
    v = gen.load_village(tmp_path, gen.GAME, 1)
    assert not any(p.name == "Kit" for p in v.people.values()) and any("another save file" in n for n in v.notes)
    assert gen.read_children_sidecar(side[:-1] + bytes([side[-1] ^ 1])) is None
    assert gen.read_children_sidecar(side.replace(b"VF2KIDS", b"VF1KIDS")) is None


def test_runner_from_the_family_trees_likes_and_twins_on_the_way():
    b = blank_save()
    villager(b, 0, "Ma", sex=1, head=1, preg=590, babies=2)
    villager(b, 1, "Pa", head=2)
    villager(b, 2, "B1", head=3, age=0, active=0)
    villager(b, 3, "B2", head=4, age=0, active=0)
    peep(b, 0, 0, "Ma", sex=1, head=1, slot=0, likes=" swimming, running")
    peep(b, 0, 1, "Pa", head=2, slot=1, likes=" water exercising", dislikes=" running")
    peep(b, 0, 2, "B1", head=3, slot=2)
    peep(b, 0, 3, "B2", head=4, slot=3)
    struct.pack_into("<3i", b, r.gs_to_file(r.GS_PENDING_BABIES), 2, 3, -1)
    v = family(bytes(b))
    ma, pa = by_name(v, "Ma"), by_name(v, "Pa")
    assert ma.runner and ma.likes == ["swimming", "running"] and not pa.runner      # a dislike is no runner
    babies = [p for p in v.people.values() if p.upcoming]
    assert len(babies) == 2 and babies[0].litter == babies[1].litter is not None
    edits = ft.Edits()
    ft.arrange(v, edits)
    lay = ft.layout(v, edits)
    assert "Runner" in ft.default_text(lay, ma) and "Runner" not in ft.default_text(lay, pa)
    assert ft.default_text(lay, babies[0]) == ["Upcoming child", "(twins)"]
    edits.show_runner = False
    assert "Runner" not in ft.default_text(ft.layout(v, edits), ma)


# ---------------------------------------------------------------- the picture
def png(width: int, height: int, pixel=lambda x, y: (0, 0, 0, 0)) -> bytes:
    raw = b"".join(b"\0" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def fake_images(folder: Path) -> Path:
    """Head sheets shaped like the game's: 12 x 50 cells of 56 pixels; each cell of column 5 a face 20 wide."""
    folder.mkdir(parents=True)

    def face(x, y):
        cx, row_y = x - ft.HEAD_FRAME * ft.HEAD_W, y % ft.HEAD_H
        return (200, 150, 100, 255) if 18 <= cx < 38 and 6 <= row_y < 36 else (0, 0, 0, 0)
    sheet = png(12 * ft.HEAD_W, 50 * ft.HEAD_H, face)
    for name in ft.SHEETS[gen.GAME]:
        (folder / name).write_bytes(sheet)
    return folder


def test_head_sheets_are_the_games_young_ones_in_column_five(tmp_path):
    assert (ft.HEAD_W, ft.HEAD_H, ft.HEAD_FRAME) == (56, 56, 5)
    images = fake_images(tmp_path / "Images")
    present = ft.sheets_present(gen.GAME, images)
    assert set(present) == {"male_heads00.png", "female_heads00.png"}
    boxes = ft.head_boxes(present["male_heads00.png"])
    assert len(boxes) == 50 and boxes[0] == (18, 6, 38, 36)
    v = family(two_generations())
    edits = ft.Edits()
    ft.arrange(v, edits)
    svg = ft.to_svg(ft.scene(ft.layout(v, edits), gen.GAME_TITLE, present, images), present)
    assert f'viewBox="{5 * 56} {4 * 56} 56 56"' in svg            # Cal: head 4, column 5


def test_the_games_own_head_sheets_have_fifty_faces():
    images = ROOT / "work" / "vanilla_runtime_payload" / "Images"
    present = ft.sheets_present(gen.GAME, images)
    if not present:
        pytest.skip("the stock game's Images (a gitignored build input) is not here")
    for path in present.values():
        assert ft._png_size(path) == (12 * ft.HEAD_W, 50 * ft.HEAD_H)
        assert len(ft.head_boxes(path)) == 50


def test_descriptors_in_family_words_and_no_masters():
    v = family(two_generations())
    edits = ft.Edits()
    ft.arrange(v, edits)
    lay = ft.layout(v, edits)
    text = {p.name: ft.default_text(lay, p) for p in v.known()}
    assert "Founder" in text["Ann"] and "Deceased: Old age" in text["Ann"] and "(deceased)" not in text["Ann"]
    assert "Married in" in text["Bob"] and "Heir" in text["Cal"] and "Adopted" in text["Ivy"]
    assert "(no longer in the house)" in text["Dee"]
    assert not any("Master" in line or "game units" in line for lines in text.values() for line in lines)
    assert "show_masters" not in dict(ft.DESCRIPTOR_OPTIONS) and "show_heir" in dict(ft.DESCRIPTOR_OPTIONS)
    edits.show_masters = False                       # (Virtual Villagers' field: not the Heir option)
    assert "Heir" in ft.default_text(ft.layout(v, edits), by_name(v, "Cal"))
    edits.show_heir = False
    assert "Heir" not in ft.default_text(ft.layout(v, edits), by_name(v, "Cal"))
    edits.show_deceased = False                     # the patcher's own "(deceased)" again
    assert "(deceased)" in ft.default_text(ft.layout(v, edits), by_name(v, "Ann"))
    # An older tree kept the Heir option under show_masters.
    assert ft.Edits.from_data({"format": 1, "show_masters": False}).show_heir is False


def test_left_home_says_why_when_the_log_does():
    b = bytearray(two_generations())
    villager(b, 3, "Dee", sex=1, head=5, body=5, age=400, active=1, left=1)
    v = family(bytes(b))
    dee = by_name(v, "Dee")
    edits = ft.Edits()
    ft.arrange(v, edits)
    assert "Left home" in ft.default_text(ft.layout(v, edits), dee)
    dee.left_why = "Boarding School"
    assert "Left home (Boarding School)" in ft.default_text(ft.layout(v, edits), dee)


def test_edits_path_and_settings_survive_a_save(tmp_path):
    edits = ft.Edits(title="Our family")
    edits.text_box_opacity, edits.text_box_colour = 60.0, "#ffeecc"
    edits.group_opts["Male"] = {"show_years": False}
    path = ft.Edits.path(tmp_path, gen.GAME, 2)
    assert path == tmp_path / "Virtual Families 2 Patcher" / "Save 2" / "Data" / "Family Tree" / \
        "Virtual Families 2 Family Tree Edits - Save 2.json"
    edits.save(path)
    back = ft.Edits.load(path)
    assert (back.title, back.text_box_opacity, back.text_box_colour) == ("Our family", 60.0, "#ffeecc")
    v = family(two_generations())
    ft.arrange(v, back)
    assert not any("years old" in line for line in ft.default_text(ft.layout(v, back), by_name(v, "Cal")))


def test_write_puts_the_page_report_and_picture_beside_the_save(tmp_path):
    write_save(tmp_path, two_generations())
    images = fake_images(tmp_path / "game" / "Images")
    before = (tmp_path / "Virtual Families 21.ldw").read_bytes()
    written = ft.write(tmp_path, gen.GAME, 1, images)
    out = tmp_path / "Virtual Families 2 Patcher" / "Save 1" / "Family Tree"
    assert written.report.parent == out and written.page.parent == out
    assert "Testfamily" in written.report.read_text("utf-8")
    import vf2_gdiplus
    if vf2_gdiplus.available():
        assert written.picture is not None and written.picture.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert (tmp_path / "Virtual Families 21.ldw").read_bytes() == before


# ---------------------------------------------------------------- the shipped pictures
OWNER_PICTURES = 27


def test_every_background_and_logo_ships_byte_for_byte_in_both_trees():
    pictures = [ref[6:] for _n, _c, _g, ref in ft.PRESETS if ref.startswith("asset:")]
    logos = [ref[6:] for _n, ref in ft.LOGOS]
    assert len(pictures) == OWNER_PICTURES and len(set(pictures)) == OWNER_PICTURES
    assert logos == ["virtual-families-logo.png", "virtual-families-2-logo.png", "fish-tycoon-logo.png",
                     "plant-tycoon-logo.png"]
    src = sorted(p.name for p in (ROOT / "src" / "family_tree_backgrounds").iterdir())
    assert src == sorted(pictures + logos)
    for name in src:
        a = (ROOT / "src" / "family_tree_backgrounds" / name).read_bytes()
        assert a == (ROOT / "work" / "family_tree_backgrounds" / name).read_bytes() and a[:8] == b"\x89PNG\r\n\x1a\n"
        assert ft.picture_path(f"asset:{name}", None) is not None
    sys.path.append(str(ROOT / "work"))             # after src/: the exporter and verifier live only in work/
    import export_offline_patch_bundle as exporter
    import verify_offline_bundle_zip as verifier
    shipped = {f"family_tree_backgrounds/{n}" for n in src}
    assert shipped <= set(exporter.GUI_TOOL_FILES) and shipped <= verifier.REQUIRED_RUNNERS
    for module in ("vf2_genealogy.py", "vf2_family_history.py", "vf2_tree_memory.py", "vf2_family_tree.py",
                   "vf2_family_tree_window.py", "vf2_member_info.py", "vf2_relationships.py",
                   "vf2_line_colours.py", "vf2_tree_editor_tools.py", "vf2_gdiplus.py"):
        assert module in exporter.GUI_TOOL_FILES and module in verifier.REQUIRED_RUNNERS


def test_framed_backgrounds_show_their_colour_round_the_frame():
    import vf2_gdiplus
    if not vf2_gdiplus.available():
        pytest.skip("GDI+ is Windows only")
    for _name, colour, _g, ref in ft.PRESETS:
        if ref in ("asset:sand-in-black-frame.png", "asset:canvas-in-wood-frame.png"):
            w, h, px = vf2_gdiplus.backdrop_pixels(ft.Backdrop(colour, "", ft.BACKGROUNDS / ref[6:], "contain"),
                                                   1200, 600)
            b, g, red, a = px[0:4]
            assert "#%02x%02x%02x" % (red, g, b) == colour and a == 255


# ---------------------------------------------------------------- the editor window and the Tools tab
@pytest.fixture(scope="module")
def tk_root():
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display: {exc}")
    root.withdraw()
    yield root
    root.destroy()


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.tree_style = None
        self.tree_window = {}
        self.saved = 0

    def _run_with_wait(self, label, func, keep_open=False):
        return func()

    def _save_settings(self):
        self.saved += 1


def test_editor_opens_selects_and_saves_a_tree_file(tk_root, tmp_path):
    import vf2_family_tree_window as w
    write_save(tmp_path, two_generations())
    images = fake_images(tmp_path / "game" / "Images")
    v = gen.load_village(tmp_path, gen.GAME, 1)
    ed = w.TreeEditor(FakeApp(tk_root), tmp_path, gen.GAME, 1, gen.GAME_TITLE, images, v, ft.Edits())
    try:
        ed.withdraw()
        tk_root.update()
        cal = by_name(ed.village, "Cal")
        ed._select([cal.id])
        ed._refresh_selected()
        info = ed.info_tab.text.get("1.0", "end")
        assert "Cal" in info and "Heir" in info
        assert [ed.village.people[q].name for q in w.find_villagers(ed.village, ed.edits, "adopted")] == ["Ivy"]
        assert ed._save_tree()
        tree = ft.data_folder(tmp_path, 1) / f"Virtual Families 2 Family Tree - Save 1{ft.TREE_SUFFIX}"
        data = json.loads(tree.read_text("utf-8"))
        assert data["format"] == ft.TREE_FORMAT and data["slot"] == 1 and data["family"] == "Testfamily"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["Virtual Families 2 Patcher", "Virtual Families 21.ldw",
                                                              "game"]
        assert [name for name, _ref in ed.logos] == ["Virtual Families logo", "Virtual Families 2 logo",
                                                     "Fish Tycoon logo", "Plant Tycoon logo"]
    finally:
        ed.destroy()


def test_the_picker_lists_each_slot_and_opens_the_family(tk_root, tmp_path, monkeypatch):
    import vf2_family_tree_window as w
    write_save(tmp_path, two_generations())
    write_save(tmp_path, b"broken", 3)
    opened = []
    monkeypatch.setattr(w, "_open_editor", lambda app, dialog, folder, game, info, title, images:
                        opened.append((folder, game, info.slot, title, images)))
    dialog = w.open_family_tree(FakeApp(tk_root), folders=[tmp_path])
    try:
        rows = dialog._vf2_slots.get(0, "end")
        assert rows[0] == "Save 1: Testfamily (2 generations)" and rows[1] == "Save 2: (empty)"
        assert rows[2].startswith("Save 3: cannot be read")
        dialog._vf2_start()
        assert opened == [(tmp_path, gen.GAME, 1, gen.GAME_TITLE, None)]
    finally:
        dialog.destroy()


def test_tools_tab_has_the_family_tree_maker(tk_root, tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import ttk

    import vf2_tools_gui as tools
    monkeypatch.setattr(tools, "tree_settings_path", lambda: tmp_path / "family_tree_settings.json")

    class Window(tools.ToolsTabMixin):
        def __init__(self, root):
            self.root = root
            self.status_var = tk.StringVar(master=root)
            self.notebook = ttk.Notebook(root)      # the Tools tab refreshes its saves line on a tab change
            self._init_tools()

    top = tk.Toplevel(tk_root)
    top.withdraw()
    style = ttk.Style(top)
    for name in ("Link.TLabel", "LinkHover.TLabel", "Muted.TLabel"):
        style.configure(name)
    style.configure("Section.TLabelframe")
    app = Window(top)
    try:
        tab = ttk.Frame(top)
        app._build_tools_tab(tab)

        def walk(widget):
            yield widget
            for child in widget.winfo_children():
                yield from walk(child)
        texts = [x.cget("text") for x in walk(tab) if x.winfo_class() in ("TLabel", "TLabelframe")]
        assert "Family Tree Maker..." in texts and "family_tree" in app.help_keys   # one game box, as in VV
        app.tree_style, app.tree_window = {"font": "Arial"}, {"zoom": 2}
        app._save_settings()
        assert tools.load_tree_settings() == {"style": {"font": "Arial"}, "window": {"zoom": 2}}
    finally:
        top.destroy()


# ---------------------------------------------------------------- the owner's Virtual Families labels
def labels(v: gen.Village, name: str, **options) -> list[str]:
    edits = ft.Edits(**options)
    ft.arrange(v, edits)
    return ft.default_text(ft.layout(v, edits), by_name(v, name))


def test_every_label_is_a_ticked_descriptor_option():
    keys = dict(ft.DESCRIPTOR_OPTIONS)
    new = ("show_adopted", "show_event", "show_spouse_number", "show_remarried", "show_divorced", "show_career",
           "show_deceased")
    assert all(k in keys and getattr(ft.Edits(), k) is True for k in new)
    data = ft.Edits(show_career=False, show_divorced=False).to_data()
    back = ft.Edits.from_data(data)
    assert back.show_career is False and back.show_divorced is False and back.show_event is True
    assert all(k in ft.STYLE_KEYS and k in ft.GROUP_FIELDS for k in new)


def test_career_as_the_game_words_it_only_from_a_record_of_theirs():
    b = bytearray(two_generations())
    villager(b, 1, "Bob", head=2, body=2, age=700, career=38, level=1)      # Engineer, Novice
    peep(b, 0, 0, "Ann", sex=1, head=1, body=1, slot=-1, career=39)          # a dead parent: the tree record's
    peep(b, 1, 2, "Gus", head=8, body=8, slot=7, heir=0, career=0)           # an unborn child's entry: never written
    v = family(bytes(b))
    assert gen.career_words(by_name(v, "Bob")) == "Novice Engineer"
    assert gen.career_words(by_name(v, "Ann")) == "Architect"
    assert gen.career_words(by_name(v, "Gus")) == "" and gen.career_words(by_name(v, "Ivy")) == ""
    assert "Novice Engineer" in labels(v, "Bob") and "Novice Engineer" not in labels(v, "Bob", show_career=False)
    assert (len(gen.CAREER_NAMES), gen.CAREER_NAMES[0], gen.CAREER_NAMES[131]) == (132, "Pastry Designer",
                                                                                     "Pen Designer")


def test_deceased_keeps_the_cause_and_says_when_it_is_unconfirmed():
    v = family(two_generations())
    assert "Deceased: Disease" in labels(v, "Fay")
    by_name(v, "Fay").cause = gen.cause_words(3)
    assert "Deceased: Work accident (unconfirmed)" in labels(v, "Fay")
    by_name(v, "Fay").cause = ""
    assert "Deceased" in labels(v, "Fay")


def test_a_same_sex_couple_is_drawn_like_any_other():
    b = blank_save()
    villager(b, 0, "Ann", sex=1, head=1)
    villager(b, 1, "Zoe", sex=1, head=2, body=2)
    villager(b, 2, "Kit", sex=0, head=3, age=100)
    peep(b, 0, 0, "Ann", sex=1, head=1, slot=0)
    peep(b, 0, 1, "Zoe", sex=1, head=2, body=2, slot=1)
    peep(b, 0, 2, "Kit", head=3, slot=2)
    v = family(bytes(b))
    kit, ann, zoe = by_name(v, "Kit"), by_name(v, "Ann"), by_name(v, "Zoe")
    assert {kit.father, kit.mother} == {ann.id, zoe.id} and ann.generation == zoe.generation == 1
    assert "Married in" in labels(v, "Zoe")
    edits = ft.Edits()
    ft.arrange(v, edits)
    assert "<svg" in ft.to_svg(ft.scene(ft.layout(v, edits), gen.GAME_TITLE, {}), {})
