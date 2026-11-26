"""Game Mechanics' Family members group (src/vf2_game_mechanics_family.py; the owner approved the port of the Virtual
Villagers patcher's per-villager group, 2026-11-26).

Every case starts from a committed real save (tests/fixtures/vf2_saves) written into a temporary save folder.  The
values each line shows are checked against the save's own bytes, read here at their file offsets without the
patcher's reader; the cases that need a sickness, food groups or a long name write those fields into the copy.  The
game's own words (the likes list, "Wants kids?") are checked against the English the translation files were made
from, and the code they come from in the desktop objects when they are present (VF2_DESKTOP_OBJ_DIR or
work/desktop_obj_files).
"""
from __future__ import annotations

import gzip
import os
import re
import struct
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_game_mechanics as gm  # noqa: E402
import vf2_game_mechanics_family as fam  # noqa: E402
import vf2_names  # noqa: E402
import vf2_save_reader as sr  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "vf2_saves"
NAMES = ("one_generation_slot3", "pending_birth_slot1", "ten_generations_slot4")
OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
DURATION = re.compile(r"\b(\d[\d,.]*|one|every|each|per)\s+((game|real)\s+)?(seconds?|minutes?|hours?|days?)\b")


def fixture(name: str) -> bytes:
    return gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes())


def put(folder: Path, data: bytes, slot: int = 1) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / sr.save_file_name(slot)
    path.write_bytes(data)
    return path


def record_at(slot: int) -> int:
    """The file offset of villager record `slot` (gs+0x172A8; the payload starts at theGameState+8)."""
    return sr.gs_to_file(sr.GS_VILLAGERS) + slot * sr.VILLAGER_RECORD_SIZE


def i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def cstr(data: bytes, at: int, n: int) -> str:
    return data[at:at + n].split(b"\0")[0].decode("utf-8", "replace")


def lines_of(facts, name: str) -> list[str]:
    out, inside = [], False
    for f in facts:
        if not f.sub:
            inside = f.text.startswith(f"{name}: ")
            if inside:
                out.append(f.text)
        elif inside:
            out.append(f.text)
    return out


@pytest.mark.parametrize("name", NAMES)
def test_every_member_is_listed_with_the_saves_own_values(tmp_path, name):
    data = fixture(name)
    facts = fam.facts(put(tmp_path / "save", data))
    assert facts and all(f.group == gm.FAMILY and f.label in gm.LABELS for f in facts)
    slots = [k for k in range(sr.VILLAGER_SLOTS) if data[record_at(k)]]
    assert slots
    for slot in slots:
        r = record_at(slot)
        who = cstr(data, r + 0x18, 25)
        mine = lines_of(facts, who)
        assert mine, who
        units, sex, health = i32(data, r + 8), i32(data, r + 0xC), i32(data, r + 0xB4)
        head = mine[0]
        assert f"{who}: {('Male', 'Female')[sex]}, {units // 20:,} year" in head
        assert f"({units:,} age units; {20 - units % 20} more" in head
        if health <= 0:
            continue
        assert f"health {health} of 100" in head
        body = "\n".join(mine[1:])
        hunger = i32(data, r + 0xE8)
        assert (f"Happiness {i32(data, r + 0xE0)}, Health {health}, Fed {100 - hunger} (100 less the hunger, "
                f"{hunger}), Energy {i32(data, r + 0xDC)}.") in body
        assert (f"happiness trend {i32(data, r + 0xE4):+,} " in body and f"dirtiness {i32(data, r + 0xEC)}," in body
                and f"toilet need {i32(data, r + 0xF0)} " in body)
        wants, fertility = i32(data, r + 0xF8), i32(data, r + 0xF4)
        assert f"Wants kids?: {wants} (\"{fam.WANTS_KIDS[wants // 10]}\"" in body
        assert f"fertility {fertility} of 100" in body
        assert ("Away from home" in body) == bool(data[r + 1])
        career, level, progress, salary = (i32(data, r + o) for o in (0x140, 0x144, 0x148, 0x14C))
        if career == -1:
            assert "Career: none; no salary." in body
        else:
            _cid, place, job, _pay = fam.CAREER_BY_ID[career]
            assert f"Career: {job} (works in the {gm.WORKPLACES[place]}), {gm.LEVELS[level]} (level {level + 1} of 8)" \
                in body
            assert f"progress {progress:,} of 3,000" in body and f"salary ${salary:,}: ${salary / 2:g} per hour" in body
        likes = [fam.LIKE_WORDS[i] for i in struct.unpack_from("<3i", data, r + 0x150) if i != -1]
        dislikes = [fam.LIKE_WORDS[i] for i in struct.unpack_from("<3i", data, r + 0x15C) if i != -1]
        assert f"Likes: {', '.join(likes) or 'none'}. Dislikes: {', '.join(dislikes) or 'none'}." in body
        symptoms = data[r + 0x104:r + 0x10B]
        assert ("Sick with" in body) == any(symptoms) and (", sick" in head) == any(symptoms)
        conceived = i32(data, r + 0xCC)
        if conceived:
            babies = {1: "1 baby", 2: "twins", 3: "triplets"}[i32(data, r + 0xD0)]
            assert f"Pregnant with {babies}, conceived at age unit {conceived:,}: born on age unit {conceived + 21:,}" \
                in body


def test_the_family_trees_likes_are_the_same_words():
    # CLikeList::GetListAsString wrote the Family Tree's words from the same places: LIKE_WORDS is read in order.
    checked = 0
    for name in NAMES:
        data = fixture(name)
        save = sr.parse_family_save(data)
        tree = fam.Tree(save)
        rec = save.family_tree.current
        for peep in (rec.parent1, rec.parent2) + rec.children:
            v = tree.villager(peep)
            if v is None:
                continue
            raw = data[record_at(v.slot):record_at(v.slot + 1)]
            assert fam.like_text(fam.places(raw, fam.LIKES)).replace("none", "") == peep.likes.strip(), peep.name
            assert fam.like_text(fam.places(raw, fam.DISLIKES)).replace("none", "") == peep.dislikes.strip()
            checked += 1
    assert checked >= 10


def test_the_games_own_words():
    # The English the translation files were made from (strings 0x7AF / 0x7B0 = 1967 / 1968, 0x723..0x727).
    english = {}
    for line in (ROOT / "translations" / "fr.tsv").read_text(encoding="utf-8").splitlines():
        m = re.match(r"strings/(\d+)~[0-9a-f]+\t([^\t]*)\t", line)
        if m:
            english[int(m.group(1))] = m.group(2)
    for sid in (1967, 1968):
        assert tuple(w.strip() for w in english[sid].split(",")) == fam.LIKE_WORDS
    assert "water exercising" in fam.LIKE_WORDS and len(fam.LIKE_WORDS) == 120
    assert [english[sid] for sid in range(1827, 1832)] == list(dict.fromkeys(fam.WANTS_KIDS))


def test_the_code_the_words_come_from():
    state, plans = OBJ_DIR / "VillagerState.obj", OBJ_DIR / "VillagerPlans.obj"
    if not state.is_file() or not plans.is_file():
        pytest.skip("needs the desktop objects (VF2_DESKTOP_OBJ_DIR or work/desktop_obj_files)")
    code = state.read_bytes()
    # WantChildrenString: the ten string ids 0x723 0x723 0x724 0x724 0x725 0x725 0x726 0x726 (two xmm constants),
    # then 0x727 three times, picked by value / 10.
    assert b"__xmm@00000724000007240000072300000723" in code and b"__xmm@00000726000007260000072500000725" in code
    # IsSick: the seven symptom bytes state +0x5C..+0x62; FoodGroupsActive: flags +0x84, ends +0x88.
    assert all(bytes.fromhex(f"8079{0x5C + k:02x}00") in code for k in range(7))
    assert bytes.fromhex("8db184000000") in code and bytes.fromhex("8d9988000000") in code
    # The try's Impregnate call passes the literal "Joey" as the father's name.
    assert b"??_C@_04PIDKGECL@Joey?$AA@" in plans.read_bytes() and fam.FATHER_STAND_IN == "Joey"


def test_sickness_infection_food_groups_and_a_whole_name(tmp_path):
    data = bytearray(fixture("pending_birth_slot1"))
    save = sr.parse_family_save(bytes(data))
    wizzy, oslo = (next(v for v in save.villagers if v.active and v.name == n) for n in ("Wizzy", "Oslo"))
    w, o = record_at(wizzy.slot), record_at(oslo.slot)
    saved = save.clock.real_seconds_at_save
    data[w + 0x104 + 4] = 1                                          # a cough
    struct.pack_into("<I", data, w + 0x10C + 16, saved + 7200)
    data[w + 0x128] = 1                                              # a mild infection
    data[o + 0x129] = 1                                              # a serious infection, no symptom
    for k in range(4):
        data[o + 0x12C + k] = int(k in (1, 3))                       # Dairy running, Fruits and Veggies over
    struct.pack_into("<4I", data, o + 0x130, 0, saved + 600, 0, saved - 1)
    short = "Oslo Whole" + vf2_names.MARK
    tree = sr.gs_to_file(sr.GS_FAMILY_TREE) + 4 + (len(save.family_tree.generations) - 1) * sr.FAMILY_RECORD_SIZE
    seat = next(tree + off for off in (0x04, 0xDC) if cstr(bytes(data), tree + off, 25) == "Oslo")
    for at, room in ((o + 0x18, 25), (seat, 25)):                    # his own record and the current Family Tree's
        assert cstr(bytes(data), at, room) == "Oslo"
        data[at:at + room] = short.encode().ljust(room, b"\0")
    folder = tmp_path / "save"
    path = put(folder, bytes(data))
    vf2_names.write(vf2_names.names_path(folder, 1), [vf2_names.Entry(short, 18, "Oslo Wholename-Smith")])
    facts = fam.facts(path)
    wiz = "\n".join(lines_of(facts, "Wizzy"))
    assert ", sick." in wiz.splitlines()[0]
    assert f"Sick with a cough (its time ends {fam.when(save, saved + 7200)}, real time)" in wiz
    assert "; also a mild infection (Penicillin or Vancomycin ends it). See Health and sickness" in wiz
    assert "Spouse: Oslo Wholename-Smith" in wiz and "the father's looks are " in wiz
    osl = lines_of(facts, "Oslo Wholename-Smith")
    assert osl and ", sick" not in osl[0]
    body = "\n".join(osl)
    assert "Not sick by the game's test (no symptom), but carries a serious infection (Vancomycin ends it)" in body
    assert f"Whole name: Oslo Wholename-Smith; the save keeps the short form \"{short}\"" in body
    assert (f"Dairy until {fam.when(save, saved + 600)}, Fruits and Veggies until {fam.when(save, saved - 1)} "
            "(already over). The game counts 1.") in body


def test_pregnancy_and_the_unborn_child(tmp_path):
    facts = fam.facts(put(tmp_path / "save", fixture("pending_birth_slot1")))
    wiz = "\n".join(lines_of(facts, "Wizzy"))
    assert ("Pregnant with 1 baby, conceived at age unit 560: born on age unit 581, 19 age units to go (3 hours 10 "
            "minutes of game time, 3 hours 10 minutes of real time at Normal speed); the father's looks are Oslo's "
            "(the save keeps the father's name as \"Joey\"") in wiz
    assert "Children in the save's Family Tree: Trishania (on the way, not born yet)." in wiz
    assert facts[-1].text.startswith("Babies on the way: 1,")


def test_spouse_parents_and_children(tmp_path):
    facts = fam.facts(put(tmp_path / "save", fixture("one_generation_slot3")))
    elsa = "\n".join(lines_of(facts, "Elsa"))
    assert "the head of the family, generation 1 (the founder)" in elsa and "Spouse: Paulolo" in elsa
    assert "Children in the save's Family Tree: Merlino (at home), Pierur (at home)" in elsa
    merlino = "\n".join(lines_of(facts, "Merlino"))
    assert "Parents: Elsa and Paulolo (the save's Family Tree)." in merlino
    assert "\"Joey\" is the name the game writes for the father when a try for a baby works" in merlino
    assert "a teen (14 to 17)" not in merlino and "a child (under 14)" in merlino


def test_every_time_names_its_clock_and_nothing_names_a_sex_rule(tmp_path):
    for name in NAMES:
        for f in fam.facts(put(tmp_path / name, fixture(name))):
            if DURATION.search(f.text):
                assert "real time" in f.text or "game time" in f.text, f.text
            assert "Matriarch" not in f.text and "Patriarch" not in f.text and not re.search(r"(?i)villag", f.text)


def test_an_unreadable_save_says_so(tmp_path):
    path = put(tmp_path / "save", b"ldwg not a save")
    facts = fam.facts(path)
    assert len(facts) == 1 and facts[0].text.startswith("This save could not be read:")
    assert fam.find_families([tmp_path / "save"]) == []


def test_the_family_module_only_reads():
    source = (ROOT / "src" / "vf2_game_mechanics_family.py").read_text(encoding="utf-8")
    for call in (r"\bopen\(", r"write_bytes", r"write_text", r"\.unlink\(", r"shutil", r"subprocess", r"os\.remove"):
        assert re.search(call, source) is None, call


def test_the_window_lists_each_family_switches_and_writes_nothing(tmp_path):
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except Exception:
        pytest.skip("no display available for Tk")
    root.withdraw()
    import vf2_game_mechanics_window as gmw
    folder = tmp_path / "Virtual Families 2 - Modded"
    put(folder, fixture("one_generation_slot3"), 1)
    put(folder, fixture("pending_birth_slot1"), 2)
    families = fam.find_families([folder])
    assert [f.label for f in families] == [f"Save 1: Lorsieab2 ({folder.name})", f"Save 2: Lorsieab2 ({folder.name})"]
    refused = AssertionError("the Game Mechanics window must not write")
    try:
        with mock.patch("pathlib.Path.write_bytes", side_effect=refused), \
                mock.patch("pathlib.Path.write_text", side_effect=refused):
            window = gmw.open_game_mechanics(root, families)
            page = window.mechanics_page
            shown = page.get("1.0", "end-1c")
            assert "Elsa: Female, 41 years" in shown and "Wizzy:" not in shown
            assert gm.FAMILY in window.mechanics_marks
            window.family_box.current(1)
            window.family_box.event_generate("<<ComboboxSelected>>")
            window.update()
            shown = page.get("1.0", "end-1c")
            assert "Wizzy: Female, 28 years" in shown and "Elsa:" not in shown
            assert str(page.cget("state")) == "disabled"
            for group in gm.GROUPS:
                assert group in window.mechanics_marks
            window.destroy()
            empty = gmw.open_game_mechanics(root)
            assert gmw.NO_FAMILY in empty.mechanics_page.get("1.0", "end-1c")
            assert empty.family_box.get() == gmw.NO_FAMILY
            empty.destroy()
    finally:
        root.destroy()
