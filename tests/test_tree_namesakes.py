"""Two family members with the same name and look are two people on the Family Tree, each with their own age,
parents, number and edits (the Virtual Villagers Fun Patcher's v1.35.85 fix, ported; the owner, 2026-10-29); and a
retyped title line keeps the player's words with the counts and date of now.

In Virtual Families 2 each family member is their own seat in the save's Family Tree, and their parents are that
record's couple, so no parent is ever chosen by name (nothing to ask).  What two namesakes shared was the tree's
edits key ("name|head|body"): a mark, a label or a move made for one showed on the other.  Each now has their own
("name|head|body|<seat>") while a namesake exists; edits that cannot be told to be either one's are kept in the
file ("parked|...") but shown on nobody.  Synthetic saves only (tests/test_family_tree.py's builders), in tmp_path.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vf2_family_tree as ft  # noqa: E402
import vf2_genealogy as gen  # noqa: E402
import vf2_save_reader as r  # noqa: E402
from test_family_tree import blank_save, family, peep, villager  # noqa: E402


def two_toms(second: bool = True) -> bytes:
    """Ann and Bob; their sons Tom (8 years) and -- when `second` -- another Tom of the same look (5 years), and
    their daughter Una."""
    b = blank_save()
    villager(b, 0, "Ann", sex=1, head=1, body=1, age=700)
    villager(b, 1, "Bob", head=2, body=2, age=720)
    villager(b, 2, "Tom", head=3, body=3, age=8 * r.AGE_UNITS_PER_YEAR, father="Bob", mother="Ann")
    villager(b, 4, "Una", sex=1, head=5, body=5, age=3 * r.AGE_UNITS_PER_YEAR, father="Bob", mother="Ann")
    peep(b, 0, 0, "Ann", sex=1, head=1, body=1, slot=0)
    peep(b, 0, 1, "Bob", head=2, body=2, slot=1)
    peep(b, 0, 2, "Tom", head=3, body=3, slot=2)
    if second:
        villager(b, 3, "Tom", head=3, body=3, age=5 * r.AGE_UNITS_PER_YEAR, father="Bob", mother="Ann")
        peep(b, 0, 3, "Tom", head=3, body=3, slot=3)
        peep(b, 0, 4, "Una", sex=1, head=5, body=5, slot=4)
    else:
        peep(b, 0, 3, "Una", sex=1, head=5, body=5, slot=4)
    return bytes(b)


def toms(v: gen.Village) -> list[gen.Person]:
    return sorted((p for p in v.people.values() if p.name == "Tom"), key=lambda p: p.seat)


def test_two_namesakes_are_two_people_with_their_own_age_parents_and_number():
    v = family(two_toms())
    elder, younger = toms(v)
    assert (elder.seat, younger.seat) == ("g1.c0", "g1.c1")
    assert (elder.years, younger.years) == (8, 5)
    ann = next(p for p in v.people.values() if p.name == "Ann")
    bob = next(p for p in v.people.values() if p.name == "Bob")
    assert (elder.father, elder.mother) == (younger.father, younger.mother) == (bob.id, ann.id)
    assert elder.number != younger.number and None not in (elder.number, younger.number)
    assert (elder.namesake_rank, younger.namesake_rank) == (1, 2)
    keys = {ft.entry_key(v, elder), ft.entry_key(v, younger)}
    assert keys == {"Tom|3|3|g1.c0", "Tom|3|3|g1.c1"}
    # Nobody else's key changes.
    una = next(p for p in v.people.values() if p.name == "Una")
    assert ft.entry_key(v, una) == "Una|5|5" and una.namesake_rank == 0
    edits = ft.Edits()
    ft.arrange(v, edits)
    lay = ft.layout(v, edits)
    assert elder.id in lay.x and younger.id in lay.x                       # both drawn


def test_each_namesake_has_their_own_edits():
    v = family(two_toms())
    elder, younger = toms(v)
    edits = ft.Edits()
    edits.entries[ft.entry_key(v, elder)] = {"lines": ["The elder"]}
    edits.entries[ft.entry_key(v, younger)] = {"lines": ["The younger"]}
    ft.arrange(v, edits)
    assert edits.entries[ft.entry_key(v, elder)]["lines"] == ["The elder"]
    assert edits.entries[ft.entry_key(v, younger)]["lines"] == ["The younger"]
    # Kept through the tree file.
    again = ft.Edits.from_data(edits.to_data())
    v2 = family(two_toms())
    ft.arrange(v2, again)
    e2, y2 = toms(v2)
    assert again.entries[ft.entry_key(v2, e2)]["lines"] == ["The elder"]
    assert again.entries[ft.entry_key(v2, y2)]["lines"] == ["The younger"]
    assert again.namesakes == {"Tom|3|3": ["g1.c0", "g1.c1"]}


def test_an_old_shared_edit_is_kept_in_the_file_but_shown_on_nobody():
    v = family(two_toms())
    edits = ft.Edits()
    edits.entries["Tom|3|3"] = {"lines": ["Whose?"]}
    edits.orders = {"2": ["Una|5|5", "Tom|3|3"]}
    assert ft.settle_namesakes(v, edits)
    assert "Tom|3|3" not in edits.entries
    assert edits.entries["parked|Tom|3|3"] == {"lines": ["Whose?"]}
    assert edits.orders["2"] == ["Una|5|5", "parked|Tom|3|3"]
    for p in toms(v):
        assert ft.entry_key(v, p) not in edits.entries
    # Nothing moves on the next run.
    assert not ft.settle_namesakes(v, edits)


def test_the_first_one_keeps_their_edits_when_a_namesake_arrives_and_takes_them_back_when_alone():
    alone = family(two_toms(second=False))
    edits = ft.Edits()
    (tom,) = toms(alone)
    assert ft.entry_key(alone, tom) == "Tom|3|3"
    edits.entries["Tom|3|3"] = {"lines": ["First Tom"]}
    ft.arrange(alone, edits)
    assert edits.key_owners["Tom|3|3"] == "g1.c0"
    # A second Tom: the first keeps his edits under his own seat; the new one has none.
    both = family(two_toms())
    ft.arrange(both, edits)
    elder, younger = toms(both)
    assert edits.entries[ft.entry_key(both, elder)] == {"lines": ["First Tom"]}
    assert ft.entry_key(both, younger) not in edits.entries
    assert "Tom|3|3" not in edits.entries
    # The second one gone again: the first Tom's edits are back under the plain key.
    ft.arrange(alone, edits)
    assert edits.entries["Tom|3|3"] == {"lines": ["First Tom"]}
    assert edits.namesakes == {}


def test_a_dead_and_a_living_namesake_are_two_people_too():
    # A father and the dead grandfather he was named after, with his look (as the tree file remembers him).
    v = family(two_toms(second=False))
    v.people[99] = gen.Person(99, "Bob", 2, 2, sex="Male", age=900, alive=False, gone="died", seat="g0.p1")
    gen.mark_namesakes(v)
    bobs = sorted((p for p in v.people.values() if p.name == "Bob"), key=lambda p: p.seat)
    assert len({ft.entry_key(v, p) for p in bobs}) == 2


def test_a_retyped_title_keeps_the_words_and_refreshes_the_counts_and_date():
    v = family(two_toms())
    edits = ft.Edits()
    edits.title = "The Smiths, 1 family members known -- my words"
    edits.subtitle = "Old: 2 family members known, 1 living -- 2020-01-01 09:30 (kept by me)"
    ft.arrange(v, edits)
    lay = ft.layout(v, edits)
    first, second = ft.title_lines(lay, gen.GAME_TITLE)
    known, living = len(v.known()), len(v.living())
    assert first == f"The Smiths, {known} family members known -- my words"
    assert second.startswith(f"Old: {known} family members known, {living} living -- ")
    assert second.endswith(" (kept by me)") and "2020-01-01" not in second
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} \(kept by me\)$", second)
    # Words that only look like a count are the player's ("11 livings", "v2.5 living").
    edits.subtitle = "11 livings and v2.5 living"
    assert ft.title_lines(lay, gen.GAME_TITLE)[1] == "11 livings and v2.5 living"
    # Not retyped: the tree's own line, as before.
    edits.title = edits.subtitle = ""
    assert ft.title_lines(lay, gen.GAME_TITLE) == ft.default_title_lines(lay, gen.GAME_TITLE)
