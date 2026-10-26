"""The Family Tree Maker's memory (src/vf2_tree_memory.py) and the Family History log (src/vf2_family_history.py):
members the save drops -- a divorced spouse, an earlier spouse after a remarriage, a founder who died childless --
stay on the tree once the tree has seen them; the log fills in what happened between two openings.  Each save
below is what Virtual Families 2's own code writes at that step (FamilyTree.obj, traced in vf2_tree_memory's
docstring; Divorce Spouse: docs/REQUEST_LEDGER.md).  The saves are only read; every file is in tmp_path."""
from __future__ import annotations

import json
import struct

from test_family_tree import blank_save, by_name, peep, snapshot, villager, write_save  # (puts src/ on the path)
import vf2_family_history as fh  # noqa: E402
import vf2_genealogy as gen
import vf2_save_reader as r
import vf2_tree_memory as mem  # noqa: E402

ANN = dict(name="Ann", sex=1, head=1, body=1)
BOB = dict(name="Bob", sex=0, head=2, body=2)
DAN = dict(name="Dan", sex=0, head=3, body=3)
CAL = dict(name="Cal", sex=0, head=4, body=4)
EVE = dict(name="Eve", sex=1, head=5, body=5)


def open_tree(tmp_path, data: bytes) -> gen.Village:
    write_save(tmp_path, data)
    return gen.load_village(tmp_path, gen.GAME, 1, remember=True)


def couple(spouse: dict | None = None, spouse_present: int = 1, kids=(), **ann) -> bytearray:
    b = blank_save()
    villager(b, 0, **{**ANN, **ann})
    peep(b, 0, 0, "Ann", sex=1, head=1, body=1, slot=0)
    if spouse is not None:
        peep(b, 0, 1, spouse["name"], sex=spouse["sex"], head=spouse["head"], body=spouse["body"],
             slot=spouse["slot"], present=spouse_present)
    for k, kid in enumerate(kids):
        peep(b, 0, 2 + k, kid["name"], sex=kid["sex"], head=kid["head"], body=kid["body"], slot=kid["slot"])
    return b


def test_divorce_then_remarriage_keeps_the_first_spouse_and_his_child(tmp_path):
    b = couple({**BOB, "slot": 1}, kids=[{**CAL, "slot": 2}])
    villager(b, 1, **BOB)
    villager(b, 2, **CAL, age=100)
    v = open_tree(tmp_path, bytes(b))
    assert by_name(v, "Cal").father == by_name(v, "Bob").id
    # Divorce Spouse: parent 2's whole record zeroed and Bob's villager reset.
    b = couple(kids=[{**CAL, "slot": 2}])
    villager(b, 2, **CAL, age=100)
    v = open_tree(tmp_path, bytes(b))
    bob = by_name(v, "Bob")
    assert not bob.alive and bob.gone == "left" and any("does not say why" in u for u in bob.unknowns)
    # Remarriage: UpdateParents writes Dan into parent 2; Eve is born.
    b = couple({**DAN, "slot": 3}, kids=[{**CAL, "slot": 2}, {**EVE, "slot": 4}])
    for slot, who in ((2, CAL), (3, DAN), (4, EVE)):
        villager(b, slot, **who, age=100)
    v = open_tree(tmp_path, bytes(b))
    bob, dan, ann = by_name(v, "Bob"), by_name(v, "Dan"), by_name(v, "Ann")
    assert by_name(v, "Cal").father == bob.id and by_name(v, "Cal").mother == ann.id
    assert by_name(v, "Eve").father == dan.id
    assert bob.generation == dan.generation == ann.generation == 1
    data = json.loads(mem.tree_file(tmp_path, 1).read_text("utf-8"))
    seats = {m["name"]: m["seat"] for m in data["members"]["list"]}
    assert seats["Dan"] == "g1.p2" and seats["Bob"].startswith("g1.p2#")


def test_a_spouse_who_dies_childless_stays_dead_after_a_remarriage(tmp_path):
    b = couple({**BOB, "slot": 1})
    villager(b, 1, **BOB)
    open_tree(tmp_path, bytes(b))
    # ReportDeath with no children: only parent 2's present byte cleared; his record dead (cause 2).
    b = couple({**BOB, "slot": 1}, spouse_present=0)
    villager(b, 1, **BOB, health=0, cause=2, active=0)
    v = open_tree(tmp_path, bytes(b))
    assert by_name(v, "Bob").gone == "died" and by_name(v, "Bob").cause == "Old age"
    # Ann remarries: Dan written over parent 2; Bob's record reused by a baby.
    b = couple({**DAN, "slot": 3})
    villager(b, 3, **DAN)
    villager(b, 1, name="Tot", head=9, body=9, age=10)
    v = open_tree(tmp_path, bytes(b))
    bob = by_name(v, "Bob")
    assert bob.gone == "died" and not bob.alive and bob.how == "Married in" and bob.generation == 1
    assert by_name(v, "Dan").alive


def test_a_founder_who_dies_childless_is_kept_when_the_spouse_takes_her_place(tmp_path):
    b = couple({**BOB, "slot": 1})
    villager(b, 1, **BOB)
    open_tree(tmp_path, bytes(b))
    # ReportDeath copies parent 2 over parent 1 and clears parent 2's present byte.
    b = blank_save()
    villager(b, 0, **ANN, health=0, active=0)
    villager(b, 1, **BOB)
    for place in (0, 1):
        peep(b, 0, place, "Bob", head=2, body=2, slot=1, present=1 - place)
    v = open_tree(tmp_path, bytes(b))
    ann, bob = by_name(v, "Ann"), by_name(v, "Bob")
    assert ann.gone == "died" and bob.alive and bob.how == "Married in" and bob.generation == ann.generation == 1


def test_someone_seen_once_then_gone_is_kept(tmp_path):
    b = couple({**BOB, "slot": 1})
    villager(b, 1, **BOB)
    villager(b, 5, name="Zed", head=9, body=9, age=300)
    open_tree(tmp_path, bytes(b))
    b = couple({**BOB, "slot": 1})
    villager(b, 1, **BOB)
    zed = by_name(open_tree(tmp_path, bytes(b)), "Zed")
    assert not zed.alive and zed.gone == "left" and any("No longer in the save" in u for u in zed.unknowns)


def test_new_looks_or_a_new_name_never_split_a_spouse(tmp_path):
    b = couple({**BOB, "slot": 1})
    villager(b, 1, **BOB)
    open_tree(tmp_path, bytes(b))
    robert = {**BOB, "name": "Robert", "head": 7}
    b = couple({**robert, "slot": 1})
    villager(b, 1, **robert)
    v = open_tree(tmp_path, bytes(b))
    assert [p.name for p in v.people.values()] == ["Ann", "Robert"]
    data = json.loads(mem.tree_file(tmp_path, 1).read_text("utf-8"))
    member = next(m for m in data["members"]["list"] if m["name"] == "Robert")
    assert member["former"] == ["Bob"] and "changed" in member


def test_a_new_family_starts_a_fresh_tree_file_and_keeps_the_old_one(tmp_path):
    b = couple({**BOB, "slot": 1})
    villager(b, 1, **BOB)
    open_tree(tmp_path, bytes(b))
    b = blank_save()
    villager(b, 0, name="Zoe", sex=1, head=8, body=8)
    peep(b, 0, 0, "Zoe", sex=1, head=8, body=8, slot=0)
    v = open_tree(tmp_path, bytes(b))
    assert [p.name for p in v.people.values()] == ["Zoe"] and any("new family" in n for n in v.notes)
    assert any("earlier family" in p.name for p in mem.tree_file(tmp_path, 1).parent.iterdir())


def test_when_the_oldest_generation_is_dropped_the_tree_keeps_counting(tmp_path):
    """MakeRoomInTree drops record 0 at a 31st generation: the tree file knows who the new oldest record is."""
    b = blank_save()
    villager(b, 0, **ANN, health=0, active=0)
    villager(b, 1, **CAL, age=600)
    peep(b, 0, 0, "Ann", sex=1, head=1, body=1, slot=-1)
    peep(b, 0, 2, "Cal", head=4, body=4, slot=1)
    peep(b, 1, 0, "Cal", head=4, body=4, slot=1, heir=0)
    open_tree(tmp_path, bytes(b))
    b = blank_save()
    villager(b, 1, **CAL, age=600)
    peep(b, 0, 0, "Cal", head=4, body=4, slot=1)
    v = open_tree(tmp_path, bytes(b))
    assert mem.first_generation(tmp_path, 1, r.parse_family_save(bytes(b))) == 2
    cal, ann = by_name(v, "Cal"), by_name(v, "Ann")
    assert cal.seat == "g2.p1" and cal.generation == 2 and ann.generation == 1 and not any(
        "new family" in n for n in v.notes)


def test_remembering_never_writes_the_save_and_keeps_the_edits(tmp_path):
    b = couple({**BOB, "slot": 1})
    villager(b, 1, **BOB)
    open_tree(tmp_path, bytes(b))
    path = mem.tree_file(tmp_path, 1)
    assert path.name == "Virtual Families 2 Family Tree - Save 1.tree"
    data = mem.read_tree_file(path)
    data["edits"] = {"format": 1, "title": "Ours"}
    mem.write_tree_file(path, data)
    before = (tmp_path / "Virtual Families 21.ldw").read_bytes()
    gen.load_village(tmp_path, gen.GAME, 1, remember=True)
    assert (tmp_path / "Virtual Families 21.ldw").read_bytes() == before
    assert mem.read_tree_file(path)["edits"] == {"format": 1, "title": "Ours"}
    snap = snapshot(tmp_path)
    gen.load_village(tmp_path, gen.GAME, 1)                 # without remember, nothing at all is written
    assert snapshot(tmp_path) == snap


# ---------------------------------------------------------------- the Family History log
# Lines as runtime/native/b200history writes them (OnBirths, OnDeath, OnMarriage, OnJoined, EventRecord,
# OnLeftHome, OnGeneration, OnConception, Backfill).
HISTORY = """Family: Testfamily (Save 1)
[backfilled, no date] Generation 1: Ann (Female) and Bob (Male) were the parents
[2026-10-20 10:00:00] Generation 1 began: Ann (Female, 20) was adopted and started the family
[2026-10-20 10:05:00] Ann (Female, 21) married Bob (Male, 22), generation 1
[2026-10-20 11:00:00] Conception 1: Ann and Bob (babies Nursing: 2)
[2026-10-20 12:00:00] Birth 1: Cal (Male) was born to Ann and Bob (Twins)
[2026-10-20 12:00:00] Birth 2: Cia (Female) was born to Ann and Bob (Twins)
[2026-10-20 12:30:00] Birth 3: Moe (Male) was born to Ann and (unknown)
[2026-10-20 13:00:00] Event 1: Divorce Spouse: Bob
[2026-10-20 14:00:00] Ann (Female, 25) married Dan (Male, 30), generation 1
[2026-10-20 15:00:00] Event 2: The Little Visitor: Kim
[2026-10-20 15:00:00] Kim (Female, 3) joined the family as a child, adopted, generation 1
[2026-10-20 15:01:00] Event 3: Adoption Services: Lou
[2026-10-20 15:01:00] Lou (Male, 4) joined the family as a child, adopted, generation 1
[2026-10-20 16:00:00] Death 1: Cia (Female, 2) died: Starvation
[2026-10-20 17:00:00] Event 4: Boarding School: Lou
[2026-10-20 17:00:00] Lou has been sent away to school! (Male, 9, left home)
[2026-10-20 18:00:00] Cal is going to college! (Male, 19, left home)
[2026-10-20 18:30:00] Kim left home with The Talent Scout (Female, 15, left home)
[2026-10-20 19:00:00] New Generation: generation 2 began: Cal (Male, 25) inherited the house
"""


def history_folder(tmp_path):
    path = gen.slot_root(tmp_path, 1) / "Logs" / "Family History" / "Family History 1.txt"
    path.parent.mkdir(parents=True)
    path.write_text(HISTORY, encoding="cp1252")
    return path


def test_the_family_history_fills_in_what_the_save_lost(tmp_path):
    history_folder(tmp_path)
    kids = [{**CAL, "slot": 2}, dict(name="Cia", sex=1, head=6, body=6, slot=-1),
            dict(name="Kim", sex=1, head=7, body=7, slot=5), dict(name="Lou", sex=0, head=8, body=8, slot=6)]
    b = couple({**DAN, "slot": 3}, kids=kids)
    villager(b, 3, **DAN)
    villager(b, 2, **CAL, age=400, left=1)
    villager(b, 5, name="Kim", sex=1, head=7, body=7, age=300, left=1, father="", mother="")
    villager(b, 6, name="Lou", sex=0, head=8, body=8, age=180, left=1, father="", mother="")
    write_save(tmp_path, bytes(b))
    before = snapshot(tmp_path)
    v = gen.load_village(tmp_path, gen.GAME, 1)
    assert snapshot(tmp_path) == before
    bob, cal, cia = by_name(v, "Bob"), by_name(v, "Cal"), by_name(v, "Cia")
    assert bob.how == "Married in" and bob.event == "Divorce Spouse" and bob.generation == 1
    assert cal.father == bob.id and cia.father == bob.id and cal.litter is not None and cal.litter == cia.litter
    assert cia.cause == "Starvation" and cia.years == 2
    kim, lou = by_name(v, "Kim"), by_name(v, "Lou")
    assert kim.event == "The Little Visitor" and lou.event == "Adoption Services"
    assert not any(u.startswith("Adopted:") for u in kim.unknowns + lou.unknowns)
    assert (cal.left_why, lou.left_why, kim.left_why) == ("College", "Boarding School", "The Talent Scout")
    assert by_name(v, "Dan").event == "Married in"


def test_history_lines_parse_and_the_tree_works_without_them(tmp_path):
    h = fh.parse(HISTORY)
    assert h.family == "Testfamily"
    assert [b[1] for b in h.births] == ["Cal", "Cia", "Moe"] and h.births[0][5] == "Twins"
    assert h.births[2][4] == fh.UNKNOWN_FATHER and h.births[2][5] == ""
    assert h.deaths == [(1, "Cia", "Female", 2, "Starvation")]
    assert [m[3] for m in h.marriages] == ["Bob", "Dan"]
    assert [(e[1], e[2]) for e in h.events] == [("Divorce Spouse", "Bob"), ("The Little Visitor", "Kim"),
                                                ("Adoption Services", "Lou"), ("Boarding School", "Lou")]
    assert [(j[0], j[3]) for j in h.joined] == [("Kim", True), ("Lou", True)]
    assert h.left == [("Lou", "Male", 9, "Boarding School"), ("Cal", "Male", 19, "College"),
                      ("Kim", "Female", 15, "The Talent Scout")]
    assert fh.read(tmp_path, 1) is None


def test_the_log_folder_is_beside_the_save(tmp_path):
    path = history_folder(tmp_path)
    assert path == tmp_path / "Virtual Families 2 Patcher" / "Save 1" / "Logs" / "Family History" / \
        "Family History 1.txt"
    (path.parent / "Family History 2.txt").write_text("[2026-10-21 10:00:00] Death 2: Moe (Male, 1) died: Disease\n",
                                                      encoding="cp1252")
    h = fh.read(tmp_path, 1)
    assert len(h.files) == 2 and h.deaths[-1][1] == "Moe"
    assert struct.calcsize("<i") == 4                       # (the save reader's own sizes are its tests')
