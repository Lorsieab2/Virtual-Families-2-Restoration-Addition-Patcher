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
# Lines as runtime/native/b200history/b200history.cpp writes them (OnBirths, OnDeath, OnMarriage, OnDivorce,
# OnJoined, OnIslandEvent, OnLeftHome, OnGeneration, OnConception, Backfill), and one Virtual Families 1 form.
HISTORY = """Family: Testfamily (Save 1)
[backfilled, no date] Generation 1: Ann (Female) and Bob (Male) were the parents
[2026-10-20 10:00:00] Generation 1 began: Ann (Female, 20) was adopted and started the family
[2026-10-20 10:05:00] Ann (Female, 21) married Bob (Male, 22), generation 1; current spouse of Ann: Bob
[2026-10-20 11:00:00] Conception 1: Ann and Bob (babies Nursing: 2)
[2026-10-20 12:00:00] Birth 1: Cal (Male) was born to Ann and Bob (Twins)
[2026-10-20 12:00:00] Birth 2: Cia (Female) was born to Ann and Bob (Twins)
[2026-10-20 12:30:00] Birth 3: Moe (Male) was born to Ann and (unknown)
[2026-10-20 13:00:00] Divorce: Ann (Female) and Bob (Male, 24) divorced, generation 1; Ann has no current spouse
[2026-10-20 14:00:00] Ann (Female, 25) remarried: Dan (Male, 30), generation 1; earlier spouse: Bob (divorced); current spouse of Ann: Dan
[2026-10-20 15:00:00] Kim (Female, 3) joined the family as a child, adopted (The Little Visitor), generation 1
[2026-10-20 15:01:00] Lou (Male, 4) joined the family as a child, adopted (Adoption Services), generation 1
[2026-10-20 16:00:00] Death 1: Cia (Female, 2) died: Starvation; Family role: Child, generation 1
[2026-10-20 16:30:00] Event 1: The Talent Scout
[2026-10-20 17:00:00] Lou has been sent away to school! (Male, 9, left home)
[2026-10-20 18:00:00] Cal is going to college! (Male, 19, left home)
[2026-10-20 18:30:00] Kim left home with The Talent Scout (Female, 15, left home)
[2026-10-20 18:40:00] Death 2: Dan (Male, 50) died: Old age; Family role: Parent (married in), generation 1; Ann has no current spouse
[2026-10-20 18:50:00] Ann (Female, 52) remarried: Gil (Male, 40), generation 1; earlier spouse: Dan (died); current spouse of Ann: Gil
[2026-10-20 19:00:00] New Generation: generation 2 began: Cal (Male, 25) inherited the house
[2026-10-20 19:10:00] Event 2: Divorce Spouse: Gil
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
    b = couple(kids=kids)                               # Gil divorced: parent 2 zeroed
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
    dan, gil = by_name(v, "Dan"), by_name(v, "Gil")
    assert dan.gone == "died" and dan.years == 50 and dan.cause == "Old age" and dan.how == "Married in"
    assert gil.event == "Divorce Spouse" and dan.generation == gil.generation == bob.generation == 1


def test_history_lines_parse_and_the_tree_works_without_them(tmp_path):
    h = fh.parse(HISTORY)
    assert h.family == "Testfamily"
    assert [b[1] for b in h.births] == ["Cal", "Cia", "Moe"] and h.births[0][5] == "Twins"
    assert h.births[2][4] == fh.UNKNOWN_FATHER and h.births[2][5] == ""
    assert h.deaths == [(1, "Cia", "Female", 2, "Starvation"), (2, "Dan", "Male", 50, "Old age")]
    assert [(m[0], m[3], m[7], m[8]) for m in h.marriages] == [("Ann", "Bob", "", ""), ("Ann", "Dan", "Bob", "divorced"),
                                                              ("Ann", "Gil", "Dan", "died")]
    assert h.divorces == [("Ann", "Bob", "Male", 24, 1)]
    assert [(e[1], e[2]) for e in h.events] == [("The Talent Scout", ""), ("Divorce Spouse", "Gil")]
    assert [(j[0], j[3], j[5]) for j in h.joined] == [("Kim", True, "The Little Visitor"), ("Lou", True,
                                                                                          "Adoption Services")]
    assert h.left == [("Lou", "Male", 9, "Boarding School"), ("Cal", "Male", 19, "College"),
                      ("Kim", "Female", 15, "The Talent Scout")]
    # The Virtual Families 1 forms are read too.
    old = fh.parse("[x] Death 1: Al (Male, 3) died: Disease\n[x] Al (Male, 3) joined the family as a child, adopted, "
                   "generation 1\n[x] Event 3: The Little Visitor: Al\n")
    assert old.deaths == [(1, "Al", "Male", 3, "Disease")] and old.joined[0][3] and old.events[0][2] == "Al"
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


# ---------------------------------------------------------------- spouses in order, Remarried, Divorced, events
def text(v, name, **options):
    import vf2_family_tree as ft
    edits = ft.Edits(**options)
    ft.arrange(v, edits)
    return ft.default_text(ft.layout(v, edits), by_name(v, name))


def logged_family(tmp_path, history: str, spouse=None):
    path = gen.slot_root(tmp_path, 1) / "Logs" / "Family History" / "Family History 1.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(history, encoding="cp1252")
    b = couple(spouse, kids=[{**CAL, "slot": 2}, dict(name="Kim", sex=1, head=7, body=7, slot=5),
                             dict(name="Lou", sex=0, head=8, body=8, slot=6)])
    if spouse:
        villager(b, spouse["slot"], **{k: v for k, v in spouse.items() if k != "slot"})
    villager(b, 2, **CAL, age=400, left=1)
    villager(b, 5, name="Kim", sex=1, head=7, body=7, age=300, left=1, father="", mother="")
    villager(b, 6, name="Lou", sex=0, head=8, body=8, age=180, left=1, father="", mother="")
    write_save(tmp_path, bytes(b))
    return gen.load_village(tmp_path, gen.GAME, 1)


def test_the_log_numbers_each_spouse_and_names_the_events(tmp_path):
    v = logged_family(tmp_path, HISTORY)
    ann = by_name(v, "Ann")
    assert ann.remarried and "Remarried" in text(v, "Ann")
    assert [by_name(v, n).spouse_number for n in ("Bob", "Dan", "Gil")] == [1, 2, 3]
    assert "Husband 1" in text(v, "Bob") and "Divorced" in text(v, "Bob")
    assert "Husband 2" in text(v, "Dan") and "Deceased: Old age" in text(v, "Dan")
    assert "Husband 3" in text(v, "Gil") and "Divorced" in text(v, "Gil")
    assert "Adopted" in text(v, "Kim") and "Popup Event: The Little Visitor" in text(v, "Kim")
    assert "Adopted (Adoption Services)" in text(v, "Lou") and "Left home (Boarding School)" in text(v, "Lou")
    assert "Left home (The Talent Scout)" in text(v, "Kim")
    assert "Popup Event: The Little Visitor" not in text(v, "Kim", show_event=False)
    assert not any("sland" in line for name in ("Kim", "Lou", "Cal") for line in text(v, name))


def test_email_and_popup_event_lines_name_the_kind(tmp_path):
    h = fh.parse("[x] Popup Event 4: The Talent Scout: Cal\n[x] Email Event: Oh! A collectible!\n"
                 "[x] Event 5: The Little Visitor\n")
    assert [(e[1], e[2], e[3]) for e in h.events] == [("The Talent Scout", "Cal", "Popup"),
                                                      ("Oh! A collectible!", "", "Email"),
                                                      ("The Little Visitor", "", "")]
    v = logged_family(tmp_path, HISTORY + "[2026-10-21 10:00:00] Popup Event 9: The Talent Scout: Cal\n")
    cal = by_name(v, "Cal")
    assert (cal.event_title, cal.event_kind) == ("The Talent Scout", "Popup")
    assert "Popup Event: The Talent Scout" in text(v, "Cal")
    assert gen.event_words(gen.Person(0, "X", 1, 1, event_title="A Show")) == "Random Event: A Show"
    off = text(v, "Bob", show_spouse_number=False, show_divorced=False)
    assert "Husband 1" not in off and "Divorced" not in off
    assert "Remarried" not in text(v, "Ann", show_remarried=False)


def test_no_order_unless_the_log_saw_the_first_marriage(tmp_path):
    late = "\n".join(line for line in HISTORY.splitlines() if "Generation 1 began" not in line) + "\n"
    v = logged_family(tmp_path, late)
    assert by_name(v, "Ann").remarried
    assert all(by_name(v, n).spouse_number is None for n in ("Bob", "Dan", "Gil"))
    assert not any(line.startswith(("Husband", "Wife")) for line in text(v, "Dan"))


def test_without_the_log_remarried_only_from_what_the_tree_saw(tmp_path):
    b = couple({**BOB, "slot": 1})
    villager(b, 1, **BOB)
    v = open_tree(tmp_path, bytes(b))
    assert not by_name(v, "Ann").remarried
    b = couple({**DAN, "slot": 3})
    villager(b, 3, **DAN)
    v = open_tree(tmp_path, bytes(b))
    assert by_name(v, "Ann").remarried and "Remarried" in text(v, "Ann")
    assert by_name(v, "Bob").spouse_number is None and by_name(v, "Dan").spouse_number is None
    assert not by_name(v, "Bob").divorced                    # the save does not say why he went


def test_a_same_sex_family_in_the_log_reads_and_labels_by_each_spouses_sex(tmp_path):
    log = """Family: Testfamily (Save 1)
[2026-10-20 10:00:00] Generation 1 began: Ann (Female, 20) was adopted and started the family
[2026-10-20 10:05:00] Ann (Female, 21) married Zoe (Female, 22), generation 1; current spouse of Ann: Zoe
[2026-10-20 11:00:00] Divorce: Ann (Female) and Zoe (Female, 25) divorced, generation 1; Ann has no current spouse
[2026-10-20 12:00:00] Ann (Female, 26) remarried: Dan (Male, 30), generation 1; earlier spouse: Zoe (divorced); current spouse of Ann: Dan
[2026-10-20 13:00:00] Death 1: Dan (Male, 40) died: Disease; Family role: Parent (married in), generation 1; Ann has no current spouse
[2026-10-20 14:00:00] Ann (Female, 45) remarried: Mia (Female, 41), generation 1; earlier spouse: Dan (died); current spouse of Ann: Mia
"""
    h = fh.parse(log)
    assert [(m[0], m[3], m[4]) for m in h.marriages] == [("Ann", "Zoe", "Female"), ("Ann", "Dan", "Male"),
                                                         ("Ann", "Mia", "Female")]
    assert h.divorces == [("Ann", "Zoe", "Female", 25, 1)]
    v = logged_family(tmp_path, log, spouse={"name": "Mia", "sex": 1, "head": 9, "body": 9, "slot": 3})
    assert "Wife 1" in text(v, "Zoe") and "Divorced" in text(v, "Zoe")
    assert "Husband 2" in text(v, "Dan") and "Deceased: Disease" in text(v, "Dan")
    assert "Wife 3" in text(v, "Mia") and "Remarried" in text(v, "Ann")
