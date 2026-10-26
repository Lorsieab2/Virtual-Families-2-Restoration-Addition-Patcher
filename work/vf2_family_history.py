"""The Family History log, when the patcher's family-history DLL wrote one: what happened between two openings of
the Family Tree Maker that the save itself does not keep.  Optional: the tree works the same with no log at all.
Only read.

    <save folder>\\Virtual Families 2 Patcher\\Save <N>\\Logs\\Family History\\Family History <k>.txt

The file opens with "Family: <player name> (Save <N>)" (Virtual Families 2 has no surname).  Each line after it is
"[YYYY-MM-DD HH:MM:SS] <event>" (or "[backfilled, no date] ..."); the lines used here, in the formats the DLL
writes (runtime/native/b200history, the Virtual Families 1 Family Logs formats):

    Birth <n>: <child> (<sex>) was born to <mother> and <father>[ (Twins)| (Triplets)]      OnBirths
    Death <n>: <name> (<sex>, <years>) died: <cause>                                       OnDeath
    <a> (<sex>, <years>) married <b> (<sex>, <years>), generation <g>                       OnMarriage
    <name> (<sex>, <years>) joined the family as a child, adopted, generation <g>           OnJoined
    Event <n>: <title>[: <name>]                                                            EventRecord
    <name> is going to college! (<sex>, <years>, left home)                                 OnLeftHome
    <name> has been sent away to school! (<sex>, <years>, left home)                        OnLeftHome
    <name> left home with The Talent Scout (<sex>, <years>, left home)                      OnLeftHome

The sex words, causes, captions and event titles are the game's own strings, as the DLL read them.  The father of
a birth is "(unknown)" when the DLL could not name him.  Event titles: Evict Family, Boarding School, Adoption
Services, The Little Visitor, The Talent Scout; "Divorce Spouse" (the patcher's cheat) is read in the Virtual
Families 1 format, "Event <n>: Divorce Spouse: <name>", should a log carry it.  Conception, generation and
backfilled lines are not needed by the tree (the save holds the same).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import vf2_genealogy as gen

_STAMP = re.compile(r"^\[(?P<when>[^\]]*)\] (?P<text>.*)$")
_BIRTH = re.compile(r"^Birth (\d+): (.+) \((\w+)\) was born to (.+?) and (.+?)(?: \((Twins|Triplets)\))?$")
_DEATH = re.compile(r"^Death (\d+): (.+) \((\w+), (\d+)\) died: (.*)$")
_MARRIED = re.compile(r"^(.+) \((\w+), (\d+)\) married (.+) \((\w+), (\d+)\), generation (\d+)$")
_JOINED = re.compile(r"^(.+) \((\w+), (\d+)\) joined the family as a child(?: of (.+) and (.+)|(, adopted))?, "
                     r"generation (\d+)$")
_EVENT = re.compile(r"^Event (\d+): ([^:(]+?)(?:: (.+?))?(?: \(\$-?\d+\))?$")
_LEFT = re.compile(r"^(?:(.+) is going to college!|(.+) has been sent away to school!|(.+) left home with (.+?)) "
                   r"\((\w+), (\d+), left home\)$")
UNKNOWN_FATHER = "(unknown)"            # PersonName: the DLL's words for a father it could not name
LEFT_EVENTS = ("Boarding School", "The Talent Scout")


@dataclass
class History:
    births: list[tuple] = field(default_factory=list)      # (n, child, sex, mother, father, "Twins"/"Triplets"/"")
    deaths: list[tuple] = field(default_factory=list)      # (n, name, sex, years, cause)
    marriages: list[tuple] = field(default_factory=list)   # (a, sex a, years a, b, sex b, years b, generation)
    joined: list[tuple] = field(default_factory=list)      # (name, sex, years, adopted, generation, line index)
    events: list[tuple] = field(default_factory=list)      # (n, title, name or "", line index)
    left: list[tuple] = field(default_factory=list)        # (name, sex, years, why)
    family: str = ""                                       # the header's player name
    files: list[Path] = field(default_factory=list)


def files(folder: Path, slot: int) -> list[Path]:
    base = gen.slot_root(folder, slot) / "Logs" / "Family History"
    out, k = [], 1
    while (base / f"Family History {k}.txt").is_file():
        out.append(base / f"Family History {k}.txt")
        k += 1
    return out


def parse(text: str, history: History | None = None) -> History:
    h = history or History()
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if line.startswith("Family: ") and not h.family:
            h.family = re.sub(r" \(Save \d+\)$", "", line[len("Family: "):])
            continue
        m = _STAMP.match(line)
        if not m:
            continue
        body = m.group("text")
        index = len(h.joined) + len(h.events) + len(h.births) + len(h.deaths) + len(h.marriages) + len(h.left)
        if b := _BIRTH.match(body):
            h.births.append((int(b.group(1)), b.group(2), b.group(3), b.group(4), b.group(5), b.group(6) or ""))
        elif d := _DEATH.match(body):
            h.deaths.append((int(d.group(1)), d.group(2), d.group(3), int(d.group(4)), d.group(5).strip()))
        elif w := _MARRIED.match(body):
            h.marriages.append((w.group(1), w.group(2), int(w.group(3)), w.group(4), w.group(5), int(w.group(6)),
                                int(w.group(7))))
        elif j := _JOINED.match(body):
            h.joined.append((j.group(1), j.group(2), int(j.group(3)), bool(j.group(6)), int(j.group(7)), index))
        elif e := _EVENT.match(body):
            h.events.append((int(e.group(1)), e.group(2).strip(), (e.group(3) or "").strip(), index))
        elif lh := _LEFT.match(body):
            if lh.group(1):
                name, why = lh.group(1), "College"
            elif lh.group(2):
                name, why = lh.group(2), "Boarding School"
            else:
                name, why = lh.group(3), lh.group(4)
            h.left.append((name, lh.group(5), int(lh.group(6)), why))
    return h


def read(folder: Path, slot: int) -> History | None:
    paths = files(folder, slot)
    if not paths:
        return None
    h = History()
    for path in paths:
        try:
            parse(path.read_bytes().decode("cp1252", errors="replace"), h)
        except OSError:
            continue
        h.files.append(path)
    return h


def _one(people: dict, name: str, sex: str | None = None, pred=lambda p: True) -> gen.Person | None:
    hits = [p for p in people.values() if p.name == name and (sex is None or p.sex == sex) and pred(p)]
    return hits[0] if len(hits) == 1 else None


def _partner_row(p: gen.Person) -> int:
    """The tree row of the couple `p` is a parent of: their own parent seat's generation, or for one seen only
    among their parents' children (an heir), the row below."""
    m = re.match(r"g(\d+)\.(p|c)", p.seat or "")
    if not m:
        return p.generation
    return int(m.group(1)) + (1 if m.group(2) == "c" else 0)


def apply(village: gen.Village, h: History) -> None:
    """Fill in from the log what the save cannot show: spouses who married in and are gone (a first spouse after a
    remarriage), causes and ages at death, twins and triplets, the parents named at a birth, why someone left home,
    and the event that brought a child in.  A name the log gives that matches nobody, or more than one member, is
    left alone (never a guess)."""
    people = village.people
    source = "The Family History log."

    # Spouses who married in: anyone the save no longer holds is added, beside the one they married.
    for a, _sa, _ya, b, sb, yb, _g in h.marriages:
        partner = _one(people, a)
        if _one(people, b, sb) is not None or partner is None:
            continue
        pid = max(people, default=-1) + 1
        q = gen.Person(pid, b, None, None, sex=sb)
        q.arrived, q.how, q.event = True, "Married in", "Married in"
        q.gone = "left"
        q.seat = f"g{_partner_row(partner)}.p2#log{pid}"
        q.birth_record = (partner.birth_record or 0) + 0.5
        q.unknowns.append(f"Married {a} at {yb}; no longer in the save, which keeps only the latest spouse (their "
                          "looks, and what became of them unless the log says, are not known).")
        q.sources.append(source)
        people[pid] = q

    for _n, name, sex, years, cause in h.deaths:
        p = _one(people, name, sex, lambda q: not q.alive and not q.upcoming)
        if p is None:
            continue
        p.gone, p.cause = "died", cause or p.cause
        if p.age is None or p.age // gen.UNITS_PER_YEAR != years:
            p.age = years * gen.UNITS_PER_YEAR
        p.unknowns = [u for u in p.unknowns if not u.startswith(("Not in the house now", "No longer in"))]
        p.sources.append(source)

    # Births: the parents named at the birth, and twins and triplets (the DLL logs a delivery's babies together).
    litter = max((p.litter or 0 for p in people.values()), default=0)
    run: list = []
    for _n, child, sex, mother, father, born_as in h.births:
        c = _one(people, child, sex, lambda q: not q.upcoming)
        if c is not None:
            for label, named in (("mother", mother), ("father", father)):
                parent = _one(people, named) if named != UNKNOWN_FATHER else None
                if parent is not None and parent.id != c.id and getattr(c, label) != parent.id:
                    setattr(c, label, parent.id)
            c.sources.append(source)
        size = {"Twins": 2, "Triplets": 3}.get(born_as, 1)
        if size == 1:
            run = []
            continue
        if not run or len(run) >= size or run[0][1] != (mother, father, born_as):
            litter += 1
            run = []
        run.append((c, (mother, father, born_as)))
        if c is not None:
            c.litter = litter
    counts: dict[int, int] = {}
    for p in people.values():
        if p.litter is not None:
            counts[p.litter] = counts.get(p.litter, 0) + 1
    for p in people.values():
        if p.litter is not None and counts[p.litter] < 2:
            p.litter = None

    # Why they left home (the save keeps only that they did: docs/vf2-save-format.md section 8).
    for name, sex, _years, why in h.left:
        p = _one(people, name, sex)
        if p is not None:
            p.left_why = why
            p.sources.append(source)

    # Events: a child who joined adopted is named by the event that brought them (Adoption Services or The Little
    # Visitor); Divorce Spouse (the patcher's cheat), should the log carry it.
    adopted_by: dict[str, str] = {}
    for _n, title, name, _i in h.events:
        if name and title in gen.ADOPTED_EVENTS:
            adopted_by[name] = title
        p = _one(people, name) if name else None
        if p is None:
            continue
        if title == "Divorce Spouse":
            p.event = "Divorce Spouse"
            p.unknowns = [u for u in p.unknowns if "Divorce" not in u and not u.startswith(("No longer in",
                                                                                              "Married "))]
            p.unknowns.append("Divorced (the patcher's Divorce Spouse, Family History log).")
        elif title in LEFT_EVENTS and not p.left_why:
            p.left_why = title
    for name, sex, _years, adopted, _g, _i in h.joined:
        p = _one(people, name, sex)
        if p is None or not adopted:
            continue
        p.adopted, p.arrived, p.how = True, True, "Adopted"
        if name in adopted_by:
            p.event = adopted_by[name]
            p.unknowns = [u for u in p.unknowns if not u.startswith("Adopted:")]
    village.sources.extend(str(p) for p in h.files)
