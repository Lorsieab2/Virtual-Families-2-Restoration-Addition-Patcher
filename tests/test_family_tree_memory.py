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
# Records in the final layout (VF1 docs/FAMILY_HISTORY.md at a5f7ed9; the Virtual Families 2 DLL writes the same).
def person(label: str, name: str, sex: str, head: int, body: int, age: int | None = None, age_label: str = "Age",
           indent: str = "  ") -> str:
    out = f"{indent}{label}: {name}\n"
    if age is not None:
        out += f"{indent}  {age_label}: {age}\n"
    return out + f"{indent}  Sex: {sex}\n{indent}  Head: {head}\n{indent}  Body: {body}\n"


def record(when: str, kind: str, n: int, body: str) -> str:
    return f"[{when}] {kind} {n}\n{body}\n"


def marriage(n, head, hsex, spouse, ssex, g=1, earlier="", when="2026-10-20 10:05:00"):
    body = person("Family member", head, hsex, 1, 1, 21) + person("Married", spouse, ssex, 2, 2, 22)
    if earlier:
        body += f"  Remarried: yes\n  Earlier spouse: {earlier}\n"
    return record(when, "Marriage", n, body + f"  Current spouse of {head}: {spouse}\n  Generation: {g}\n")


def death(n, name, sex, years, cause, role="Child", g=1):
    return record("2026-10-20 16:00:00", "Death", n,
                  f"  Name: {name}\n  Age at death: {years}\n  Sex: {sex}\n  Cause of death: {cause}\n  Head: 1\n"
                  f"  Body: 1\n  Family role: {role}\n  Generation: {g}\n")


def divorce(n, head, hsex, spouse, ssex, years):
    return record("2026-10-20 13:00:00", "Divorce", n,
                  person("Family member", head, hsex, 1, 1) + person("Divorced", spouse, ssex, 2, 2, years)
                  + f"  How: Divorce Spouse\n  Current spouse of {head}: (none)\n  Generation: 1\n")


def birth(n, child, sex, born_as="Single birth", father="Bob"):
    return record("2026-10-20 12:00:00", "Birth", n,
                  person("Child", child, sex, 4, 4) + "  Mother: Ann\n    Head: 1\n    Body: 1\n"
                  + (f"  Father: {father}\n    Head: 2\n    Body: 2\n" if father else "  Father: (unknown)\n")
                  + f"  Born as: {born_as}\n  Generation: 1\n")


def arrived(n, name, sex, years, how):
    return record("2026-10-20 15:00:00", "Arrived", n,
                  f"  Name: {name}\n  Age at arrival: {years}\n  Sex: {sex}\n  Head: 7\n  Body: 7\n  How: {how}\n"
                  "  Family role: Child\n  Generation: 1\n")


def left_home(n, name, sex, years, what):
    return record("2026-10-20 17:00:00", "Left Home", n,
                  f"  Name: {name}\n  Age: {years}\n  Sex: {sex}\n  Head: 4\n  Body: 4\n  What happened: {what}\n"
                  "  Generation: 1\n")


GENERATION_1 = record("2026-10-20 10:00:00", "Generation", 1,
                      "  Name: Ann\n  Age: 20\n  Sex: Female\n  Head: 1\n  Body: 1\n"
                      "  How: Founder (adopted and started the family)\n  Generation: 1\n")
HISTORY = ("Family: Testfamily (Save 1)\n" + GENERATION_1
           + marriage(1, "Ann", "Female", "Bob", "Male")
           + birth(1, "Cal", "Male", "Twin") + birth(2, "Cia", "Female", "Twin") + birth(3, "Moe", "Male", father="")
           + divorce(1, "Ann", "Female", "Bob", "Male", 24)
           + marriage(2, "Ann", "Female", "Dan", "Male", earlier="Bob (divorced)", when="2026-10-20 14:00:00")
           + arrived(1, "Kim", "Female", 3, "Adopted (Popup Event: The Little Visitor)")
           + arrived(2, "Lou", "Male", 4, "Adopted (Adoption Services)")
           + death(1, "Cia", "Female", 2, "Starvation")
           + record("2026-10-20 16:30:00", "Random Event", 1, "  Popup Event: The Talent Scout\n  Choice: A\n"
                    "  Generation: 1\n")
           + left_home(1, "Lou", "Male", 9, "Sent to Boarding School")
           + left_home(2, "Cal", "Male", 19, "Cal is going to college!")
           + left_home(3, "Kim", "Female", 15, "Left home with The Talent Scout (Popup Event)")
           + death(2, "Dan", "Male", 50, "Old age", role="Parent (married in)")
           + marriage(3, "Ann", "Female", "Gil", "Male", earlier="Dan (died)", when="2026-10-20 18:50:00")
           + divorce(2, "Ann", "Female", "Gil", "Male", 41)
           + record("2026-10-20 19:00:00", "Roll the Dice", 1, "  Cost: $500\n  Popup Event: Adoption Day\n"
                    "  Generation: 1\n"))


def history_folder(tmp_path, text: str = HISTORY):
    path = gen.slot_root(tmp_path, 1) / "Logs" / "Family History" / "Family History 1.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="cp1252")
    return path


def logged_family(tmp_path, history: str = HISTORY, spouse=None):
    history_folder(tmp_path, history)
    kids = [{**CAL, "slot": 2}, dict(name="Cia", sex=1, head=6, body=6, slot=-1),
            dict(name="Kim", sex=1, head=7, body=7, slot=5), dict(name="Lou", sex=0, head=8, body=8, slot=6)]
    b = couple(spouse, kids=kids)
    if spouse:
        villager(b, spouse["slot"], **{k: v for k, v in spouse.items() if k != "slot"})
    villager(b, 2, **CAL, age=400, left=1)
    villager(b, 5, name="Kim", sex=1, head=7, body=7, age=300, left=1, father="", mother="")
    villager(b, 6, name="Lou", sex=0, head=8, body=8, age=180, left=1, father="", mother="")
    write_save(tmp_path, bytes(b))
    before = snapshot(tmp_path)
    v = gen.load_village(tmp_path, gen.GAME, 1)
    assert snapshot(tmp_path) == before                    # the log and the save are only read
    return v


def text(v, name, **options):
    import vf2_family_tree as ft
    edits = ft.Edits(**options)
    ft.arrange(v, edits)
    return ft.default_text(ft.layout(v, edits), by_name(v, name))


def test_the_records_parse(tmp_path):
    h = fh.parse(HISTORY)
    assert [(m.head, m.spouse, m.spouse_sex, m.again, m.earlier, m.earlier_how) for m in h.marriages] == [
        ("Ann", "Bob", "Male", False, None, None), ("Ann", "Dan", "Male", True, "Bob", "divorced"),
        ("Ann", "Gil", "Male", True, "Dan", "died")]
    assert [(d[0], d[2], d[3]) for d in h.divorces] == [("Bob", 24, "Ann"), ("Gil", 41, "Ann")]
    assert [(d[0], d[2], d[5]) for d in h.deaths] == [("Cia", 2, "Starvation"), ("Dan", 50, "Old age")]
    assert [(b.babies, b.size, b.father) for b in h.births] == [([("Cal", "Male"), ("Cia", "Female")], 2, "Bob"),
                                                                ([("Moe", "Male")], 1, None)]
    assert [(j[0], j[3]) for j in h.joined] == [("Kim", "Adopted (Popup Event: The Little Visitor)"),
                                                ("Lou", "Adopted (Adoption Services)")]
    assert [(e.kind, e.title, e.choice) for e in h.events] == [("Popup Event", "The Talent Scout", "A")]
    assert [x[3] for x in h.left] == ["Sent to Boarding School", "Cal is going to college!",
                                      "Left home with The Talent Scout (Popup Event)"]
    assert fh.read(tmp_path, 1) is None


def test_the_family_history_fills_in_what_the_save_lost(tmp_path):
    v = logged_family(tmp_path)
    bob, cal, cia = by_name(v, "Bob"), by_name(v, "Cal"), by_name(v, "Cia")
    assert bob.how == "Married in" and bob.divorced and bob.generation == 1
    assert cal.father == bob.id and cia.father == bob.id and cal.litter is not None and cal.litter == cia.litter
    assert cia.cause == "Starvation" and cia.years == 2
    kim, lou = by_name(v, "Kim"), by_name(v, "Lou")
    assert (kim.event_kind, kim.event_title) == ("Popup", "The Talent Scout")       # the last word: she left with it
    assert lou.event == "Adoption Services" and (cal.left_why, lou.left_why) == ("College", "Boarding School")
    assert any("Popup Event: The Talent Scout" in e for e in v.history_events)


def test_the_labels_follow_the_log(tmp_path):
    v = logged_family(tmp_path)
    assert by_name(v, "Ann").remarried and "Remarried" in text(v, "Ann")
    assert [by_name(v, n).spouse_number for n in ("Bob", "Dan", "Gil")] == [1, 2, 3]
    bob = text(v, "Bob")
    assert "Husband 1" in bob and "Divorced" in bob and "Married in" not in bob
    assert "Husband 2" in text(v, "Dan") and "Deceased: Old age" in text(v, "Dan")
    assert "Husband 3" in text(v, "Gil") and "Divorced" in text(v, "Gil")
    assert "Adopted" in text(v, "Kim") and "Popup Event: The Talent Scout" in text(v, "Kim")
    assert "Adopted (Adoption Services)" in text(v, "Lou") and "Left home (Boarding School)" in text(v, "Lou")
    assert "Left home (College)" in text(v, "Cal")
    off = text(v, "Bob", show_spouse_number=False, show_divorced=False)
    assert "Husband 1" not in off and "Divorced" not in off and "Married in" in off
    assert "Remarried" not in text(v, "Ann", show_remarried=False)
    assert "Popup Event: The Talent Scout" not in text(v, "Kim", show_event=False)


def test_no_order_unless_the_log_saw_the_first_marriage(tmp_path):
    backfill = record("backfilled, no date", "Family Tree", 1,
                      person("Parent", "Ann", "Female", 1, 1) + person("Parent (married in)", "Bob", "Male", 2, 2)
                      + "  Generation: 1\n  Note: Recorded afterwards\n")
    late = "Family: Testfamily (Save 1)\n" + backfill + marriage(2, "Ann", "Female", "Dan", "Male",
                                                               earlier="Bob (died)")
    v = logged_family(tmp_path, late)
    assert by_name(v, "Ann").remarried
    assert all(by_name(v, n).spouse_number is None for n in ("Bob", "Dan"))
    assert "Married in" in text(v, "Dan") and not any(line.startswith(("Husband", "Wife")) for line in text(v, "Dan"))


def test_an_eviction_starts_the_family_over_in_the_log(tmp_path):
    h = fh.parse(HISTORY + record("2026-10-21 10:00:00", "Evict Family", 1, "  Family members: Ann\n  Generation: 1\n")
                 + marriage(4, "Zoe", "Female", "Max", "Male"))
    assert [m.spouse for m in h.marriages] == ["Max"] and h.evictions == 1 and not h.deaths


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
    assert "Married in" in text(v, "Bob")


def test_a_same_sex_family_in_the_log_reads_and_labels_by_each_spouses_sex(tmp_path):
    log = ("Family: Testfamily (Save 1)\n" + GENERATION_1 + marriage(1, "Ann", "Female", "Zoe", "Female")
           + divorce(1, "Ann", "Female", "Zoe", "Female", 25)
           + marriage(2, "Ann", "Female", "Dan", "Male", earlier="Zoe (divorced)")
           + death(1, "Dan", "Male", 40, "Disease", role="Parent (married in)")
           + marriage(3, "Ann", "Female", "Mia", "Female", earlier="Dan (died)"))
    h = fh.parse(log)
    assert [(m.spouse, m.spouse_sex) for m in h.marriages] == [("Zoe", "Female"), ("Dan", "Male"), ("Mia", "Female")]
    v = logged_family(tmp_path, log, spouse={"name": "Mia", "sex": 1, "head": 9, "body": 9, "slot": 3})
    assert "Wife 1" in text(v, "Zoe") and "Divorced" in text(v, "Zoe")
    assert "Husband 2" in text(v, "Dan") and "Deceased: Disease" in text(v, "Dan")
    assert "Wife 3" in text(v, "Mia") and "Remarried" in text(v, "Ann")
    assert by_name(v, "Mia").partner == by_name(v, "Ann").id


def test_the_log_folder_is_beside_the_save(tmp_path):
    path = history_folder(tmp_path)
    assert path == tmp_path / "Virtual Families 2 Patcher" / "Save 1" / "Logs" / "Family History" / \
        "Family History 1.txt"
    (path.parent / "Family History 2.txt").write_text(death(3, "Moe", "Male", 1, "Disease"), encoding="cp1252")
    h = fh.read(tmp_path, 1)
    assert len(h.files) == 2 and h.deaths[-1][0] == "Moe"
    assert struct.calcsize("<i") == 4                       # (the save reader's own sizes are its tests')


# ---------------------------------------------------------------- the VF2 DLL's own forms (origin/feat/family-history 9bfd948)
# Records exactly as runtime/native/b200history writes them (its tests/b200_history_scenarios.py expectations):
# Start Over before Generation 1, an e-mail's "Subject:", the Random Event's child right after it, Renamed, and an
# earlier spouse whose going the log never saw.
VF2_LOG = """Family: Ana Player (Save 1)
[2026-10-25 21:07:05] Start Over 1
  The earlier family's history was cleared.

[2026-10-25 21:07:05] Generation 1
  Name: Ana
  Age: 25
  Sex: Female
  Head: 3
  Body: 4
  How: Founder (adopted and started the family)
  Generation: 1

[2026-10-25 21:07:05] Marriage 1
  Family member: Ana
    Age: 25
    Sex: Female
    Head: 3
    Body: 4
  Married: Ben
    Age: 26
    Sex: Male
    Head: 3
    Body: 4
  Current spouse of Ana: Ben
  Generation: 1

[2026-10-25 21:07:05] Random Event 1
  Popup Event: The Little Visitor
  Choice: A
  Generation: 1

[2026-10-25 21:07:05] Arrived 1
  Name: Visitor
  Age at arrival: 3
  Sex: Male
  Head: 3
  Body: 4
  How: Adopted (Popup Event: The Little Visitor)
  Family role: Child
  Generation: 1

[2026-10-25 21:07:05] Arrived 2
  Name: Adoptee
  Age at arrival: 3
  Sex: Female
  Head: 3
  Body: 4
  How: Adopted (Adoption Services)
  Family role: Child
  Generation: 1

[2026-10-25 21:07:05] Random Event 2
  Email Event: Subject: A Secret Admirer
  Generation: 1

[2026-10-25 21:07:05] Random Event 3
  Popup Event: The Talent Scout
  Choice: A
  Generation: 1

[2026-10-25 21:07:05] Left Home 1
  Name: Visitor
  Age: 3
  Sex: Male
  Head: 3
  Body: 4
  What happened: Left home with The Talent Scout (Popup Event)
  Generation: 1

[2026-10-25 21:07:05] Left Home 2
  Name: Adoptee
  Age: 3
  Sex: Female
  Head: 3
  Body: 4
  What happened: Sent to Boarding School
  Generation: 1

[2026-10-25 21:07:05] Renamed 1
  Old name: Adoptee
  New name: Zed
  Age: 3
  Sex: Female
  Head: 3
  Body: 4
  Generation: 1

[2026-10-25 21:07:05] Marriage 2
  Family member: Ana
    Age: 30
    Sex: Female
    Head: 3
    Body: 4
  Married: Dan
    Age: 31
    Sex: Male
    Head: 3
    Body: 4
  Remarried: yes
  Earlier spouse: Ben
  Current spouse of Ana: Dan
  Generation: 1

"""


def test_the_vf2_logs_own_forms(tmp_path):
    h = fh.parse(VF2_LOG)
    assert [e.kind for e in h.entries][:2] == ["Start Over", "Generation"]
    assert [(e.kind, e.title, e.choice) for e in h.events] == [("Popup Event", "The Little Visitor", "A"),
                                                               ("Email Event", "A Secret Admirer", None),
                                                               ("Popup Event", "The Talent Scout", "A")]
    assert h.renamed == [("Adoptee", "Zed", "Female")]
    assert [j[0] for j in h.joined] == ["Visitor", "Zed"] and h.joined[0][6].title == "The Little Visitor"
    assert [x[0] for x in h.left] == ["Visitor", "Zed"] and h.left[0][5].title == "The Talent Scout"
    assert (h.marriages[1].again, h.marriages[1].earlier, h.marriages[1].earlier_how) == (True, "Ben", None)
    # The family in the save: Ana and Dan, and their children Visitor and Zed (renamed), both away.
    path = gen.slot_root(tmp_path, 1) / "Logs" / "Family History" / "Family History 1.txt"
    path.parent.mkdir(parents=True)
    path.write_text(VF2_LOG, encoding="cp1252")
    b = blank_save("Ana Player")
    for slot, name, sex, head in ((0, "Ana", 1, 3), (1, "Dan", 0, 5)):
        villager(b, slot, name, sex=sex, head=head, body=4)
        peep(b, 0, slot, name, sex=sex, head=head, body=4, slot=slot)
    for k, (slot, name, sex) in enumerate(((2, "Visitor", 0), (3, "Zed", 1))):
        villager(b, slot, name, sex=sex, head=3, body=4, age=60, left=1, father="", mother="")
        peep(b, 0, 2 + k, name, sex=sex, head=3, body=4, slot=slot)
    write_save(tmp_path, bytes(b))
    v = gen.load_village(tmp_path, gen.GAME, 1)
    ben, dan, zed, visitor = (by_name(v, n) for n in ("Ben", "Dan", "Zed", "Visitor"))
    assert not ben.divorced and "Divorced" not in text(v, "Ben")          # the log never saw him go
    assert (ben.spouse_number, dan.spouse_number) == (1, 2) and "Husband 2" in text(v, "Dan")
    assert "Remarried" in text(v, "Ana")
    assert zed.former == ["Adoptee"] and "Adopted (Adoption Services)" in text(v, "Zed")
    assert zed.alive and "Left home (Boarding School)" in text(v, "Zed")      # away (the save's left-home flag)
    assert "Popup Event: The Talent Scout" in text(v, "Visitor")
    assert zed.left_why == "Boarding School" and (visitor.event_kind, visitor.event_title) == ("Popup",
                                                                                             "The Talent Scout")
    assert any("Email Event: A Secret Admirer" in e for e in v.history_events)
