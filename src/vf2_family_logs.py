"""Family Logs for Virtual Families 2, written by comparing saves (no game code is changed or hooked).

Virtual Families 2 keeps no history in a save (docs/vf2-save-format.md section 9: the life-event queue is
not saved), so the patcher writes the logs itself, in the Virtual Families 1 Family Logs format
(docs/FAMILY_LOGS.md of the VF1 patcher), from the difference between the save as it is now and the
snapshot the patcher kept of the save it last logged. Only VERIFIED save fields drive a line; the
cause-of-death number is stored by the game but its meaning is UNCONFIRMED, so a death says "cause not
recorded". Every event is dated by the save it first appears in (that save's real time and game clock); an
event that starts and ends between two saves cannot be seen. The previous save the game keeps
(``Virtual Families 2<N+20>.ldw``) is read too, so a change one save back is not missed.

Per save slot N, beside the save:

    <save folder>\\Virtual Families 2 Patcher\\Save <N>\\Logs\\
        Family History\\Family History <k>.txt
        Births and Conceptions\\Virtual Families 2 Births and Conceptions Log <k>.txt
        Deaths\\Virtual Families 2 Deaths Log <k>.txt
        Events\\Virtual Families 2 Events Log <k>.txt
        Family Population\\Family Population - Save <N>.txt        rewritten at every update
        Family Statistics\\Family Statistics - Save <N>.txt        rewritten at every update
    <save folder>\\Virtual Families 2 Patcher\\Save <N>\\Data\\
        Unaccounted Villagers\\Virtual Families 2 Family Members at Last Save - Save <N>.dat   the snapshot
        Log Checks\\Virtual Families 2 Backfill - Save <N>.dat                              the backfill marker

The header of every log is ``Family: <player nickname> (Save <N>)``: VF2 has no family-name field, so the
save's player nickname (theGameState+0x25ABC, VERIFIED) is used, else the slot's name in the settings file,
else "(no name)". Append-only logs are never rewritten; a file rolls to the next number after 256 numbered
records (the Family History after 2,000 lines). A new family in the slot (Start Over, a new player, other
founders) moves the slot's old Logs and Data into ``Save <N>\\Backups\\Logs before new family <date>`` and
starts fresh; an existing ``Backups`` folder is kept. Nothing here writes, renames or locks a save file.
"""
from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import vf2_save_reader as R

GAME = "Virtual Families 2"
PATCHER_FOLDER = f"{GAME} Patcher"
BACKUPS = "Backups"
ENCODING = "cp1252"          # the game's own text encoding (names are cp1252 bytes)
NL = "\r\n"
HISTORY_LINES_PER_FILE = 2000
RECORDS_PER_FILE = 256
MAX_LOG_FILES = 4096

# kind -> (folder, file stem, the markers that number a record)
LOGS = {
    "history": ("Family History", "Family History", ()),
    "births": ("Births and Conceptions", f"{GAME} Births and Conceptions Log", ("Conception ", "Birth ")),
    "deaths": ("Deaths", f"{GAME} Deaths Log", ("Death ",)),
    "events": ("Events", f"{GAME} Events Log", ("Event ",)),
}
MEMBERS_DATA = ("Unaccounted Villagers", f"{GAME} Family Members at Last Save")
BACKFILL_DATA = ("Log Checks", f"{GAME} Backfill")
MEMBERS_TAG = "VF2LOGS MEMBERS 1"
BACKFILL_TAG = "VF2LOGS BACKFILL 1"

SEX = {0: "Male", 1: "Female"}


class FamilyLogsError(Exception):
    """Family Logs could not be updated, with a reason a player can read."""


# ---------------------------------------------------------------------------
# The snapshot: what the logs need to remember of the save last logged
# ---------------------------------------------------------------------------


@dataclass
class Member:
    slot: int
    name: str
    gender: int
    age_units: int
    head: int
    body: int
    state: str               # "home", "away", "dead" (health 0, not removed yet), "unborn" (a pending baby)
    pregnant: bool = False
    babies: int = 0
    mother: str = ""
    left_seconds: int = 0
    death_logged: bool = False

    @property
    def key(self) -> tuple:
        return (self.slot, self.name, self.gender)

    @property
    def years(self) -> int:
        return max(0, R._c_div(self.age_units, R.AGE_UNITS_PER_YEAR))


@dataclass
class Peep:
    name: str
    gender: int
    head: int
    body: int
    slot: int
    present: bool


@dataclass
class Gen:
    parent1: Peep
    parent2: Peep
    children: list
    heir_index: int = -1


@dataclass
class Snapshot:
    family: str
    saved_at: int            # header start time + GetSecondsFromGameStart at the save: the save's real time
    game_seconds: int        # CGameTime::Seconds() at the save
    evicted: int
    gens: list
    members: dict            # slot -> Member
    gen_offset: int = 0      # generations dropped off the 30-record tree window before gens[0]
    deaths: int = 0          # deaths the logs counted (the Family Statistics page)

    @property
    def generation(self) -> int:
        return self.gen_offset + len(self.gens)


def _peep(p: R.PeepRecord) -> Peep:
    return Peep(p.name, p.gender, p.head, p.body, p.slot, p.present)


def snapshot_of(save: R.FamilySave, family: str) -> Snapshot:
    pending = {s for s in save.pending_baby_slots if 0 <= s < R.VILLAGER_SLOTS}
    members = {}
    for v in save.villagers:
        if v.slot in pending:
            state = "unborn"
        elif not v.active:
            continue
        elif v.health <= 0:
            state = "dead"
        elif v.left_home:
            state = "away"
        else:
            state = "home"
        members[v.slot] = Member(
            v.slot, v.name, v.gender, v.age_units, v.head, v.body, state,
            pregnant=state != "unborn" and v.pregnancy_mark != 0,
            babies=v.babies_expected if v.pregnancy_mark != 0 else 0,
            mother=v.mother_name, left_seconds=v.left_home_game_seconds if v.left_home else 0,
        )
    gens = [Gen(_peep(g.parent1), _peep(g.parent2), [_peep(c) for c in g.children], g.parent1.heir_index)
            for g in save.family_tree.generations]
    return Snapshot(family, save_time(save), save.clock.game_seconds_at_save, save.family_tree.evicted, gens, members)


def save_time(save: R.FamilySave) -> int:
    """The real time the save was written: the header's start time plus GetSecondsFromGameStart at the save."""
    return save.header.start_time + save.clock.real_seconds_at_save


def _clean(text: str) -> str:
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _peep_fields(p: Peep) -> list:
    return [_clean(p.name), p.gender, p.head, p.body, p.slot, int(p.present)]


def write_snapshot_text(s: Snapshot) -> str:
    lines = [MEMBERS_TAG, f"family\t{_clean(s.family)}", f"saved\t{s.saved_at}\t{s.game_seconds}",
             f"tree\t{s.evicted}\t{s.gen_offset}\t{len(s.gens)}", f"deaths\t{s.deaths}"]
    for i, g in enumerate(s.gens):
        lines.append("\t".join(map(str, ["gen", i, g.heir_index, *_peep_fields(g.parent1), *_peep_fields(g.parent2)])))
        for k, c in enumerate(g.children):
            lines.append("\t".join(map(str, ["child", i, k, *_peep_fields(c)])))
    for slot in sorted(s.members):
        m = s.members[slot]
        lines.append("\t".join(map(str, [
            "member", m.slot, _clean(m.name), m.gender, m.age_units, m.head, m.body, m.state, int(m.pregnant),
            m.babies, _clean(m.mother), m.left_seconds, int(m.death_logged)])))
    lines.append(f"end\t{len(s.members)}")
    return NL.join(lines) + NL


def read_snapshot_text(text: str) -> Snapshot | None:
    """The snapshot, or None when the file is not a complete one (it is then rebuilt, never guessed)."""
    rows = [line.split("\t") for line in text.replace("\r\n", "\n").split("\n") if line]
    if not rows or rows[0] != [MEMBERS_TAG] or rows[-1][0] != "end":
        return None
    try:
        values = {r[0]: r[1:] for r in rows if r[0] in ("family", "saved", "tree", "deaths")}
        evicted, offset, count = map(int, values["tree"])
        gens: list = [None] * count
        members = {}

        def peep(f):
            return Peep(f[0], int(f[1]), int(f[2]), int(f[3]), int(f[4]), f[5] == "1")

        for r in rows:
            if r[0] == "gen":
                gens[int(r[1])] = Gen(peep(r[3:9]), peep(r[9:15]), [], int(r[2]))
        for r in rows:
            if r[0] == "child":
                gens[int(r[1])].children.append(peep(r[3:9]))
            elif r[0] == "member":
                m = Member(int(r[1]), r[2], int(r[3]), int(r[4]), int(r[5]), int(r[6]), r[7], r[8] == "1",
                           int(r[9]), r[10], int(r[11]), r[12] == "1")
                members[m.slot] = m
        if any(g is None for g in gens) or int(rows[-1][1]) != len(members):
            return None
        return Snapshot(values["family"][0] if values["family"] else "", int(values["saved"][0]),
                        int(values["saved"][1]), evicted, gens, members, offset, int(values["deaths"][0]))
    except (KeyError, IndexError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


def slot_root(save_folder: Path, slot: int) -> Path:
    return Path(save_folder) / PATCHER_FOLDER / f"Save {slot}"


def log_path(root: Path, kind: str, number: int) -> Path:
    folder, stem, _markers = LOGS[kind]
    return root / "Logs" / folder / f"{stem} {number}.txt"


def page_path(root: Path, page: str, slot: int) -> Path:
    return root / "Logs" / page / f"{page} - Save {slot}.txt"


def data_path(root: Path, which: tuple, slot: int) -> Path:
    return root / "Data" / which[0] / f"{which[1]} - Save {slot}.dat"


def _read(path: Path) -> str:
    return path.read_bytes().decode(ENCODING, "replace")


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_bytes(text.encode(ENCODING, "replace"))
    os.replace(temp, path)


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "ab") as handle:
        handle.write(text.encode(ENCODING, "replace"))


def header(family: str, slot: int) -> str:
    return f"Family: {_clean(family) or '(no name)'} (Save {slot}){NL}"


def _count_lines(text: str, prefixes) -> tuple[int, int]:
    """Lines starting with any prefix, and the highest number printed right after one."""
    count = highest = 0
    for line in text.split("\n"):
        for prefix in prefixes:
            if line.startswith(prefix):
                count += 1
                digits = ""
                for ch in line[len(prefix):]:
                    if not ch.isdigit():
                        break
                    digits += ch
                if digits:
                    highest = max(highest, int(digits))
                break
    return count, highest


class SlotLogs:
    """The append-only logs and pages of one save slot."""

    def __init__(self, save_folder: Path, slot: int, family: str):
        self.slot = slot
        self.root = slot_root(save_folder, slot)
        self.family = family
        self.written = 0

    def newest(self, kind: str) -> int:
        newest = 0
        for k in range(1, MAX_LOG_FILES + 1):
            if not log_path(self.root, kind, k).is_file():
                break
            newest = k
        return newest

    def create_logs(self) -> None:
        for kind in LOGS:
            if not self.newest(kind):
                _append(log_path(self.root, kind, 1), header(self.family, self.slot))

    def history_lines(self) -> int:
        total = 0
        for k in range(1, self.newest("history") + 1):
            total += _count_lines(_read(log_path(self.root, "history", k)), ("[",))[0]
        return total

    def _target(self, kind: str, per: int, prefixes) -> Path:
        newest = self.newest(kind)
        if not newest:
            return log_path(self.root, kind, 1)
        used = _count_lines(_read(log_path(self.root, kind, newest)), prefixes)[0]
        return log_path(self.root, kind, newest + 1 if used >= per else newest)

    def _append_log(self, kind: str, path: Path, text: str) -> None:
        if not path.is_file():
            text = header(self.family, self.slot) + text
        _append(path, text)
        self.written += 1

    def history(self, stamp: str, text: str) -> None:
        self._append_log("history", self._target("history", HISTORY_LINES_PER_FILE, ("[",)), f"{stamp}{text}{NL}")

    def record(self, kind: str, marker: str, body: list) -> int:
        """Append a numbered record ("Birth 4") and return its number (after the highest in any file)."""
        _folder, _stem, prefixes = LOGS[kind]
        highest = 0
        for k in range(1, self.newest(kind) + 1):
            highest = max(highest, _count_lines(_read(log_path(self.root, kind, k)), (marker,))[1])
        number = highest + 1
        text = f"{marker}{number}{NL}" + "".join(f"{line}{NL}" for line in body)
        self._append_log(kind, self._target(kind, RECORDS_PER_FILE, prefixes), text)
        return number


def stamp_of(s: Snapshot) -> str:
    try:
        when = datetime.fromtimestamp(s.saved_at).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        when = "unknown date"
    return f"[{when}, game time {s.game_seconds / R.GAME_SECONDS_PER_YEAR:.1f} years] "


BACKFILL_STAMP = "[backfilled, no date] "


def _sex(gender: int) -> str:
    return SEX.get(gender, "Unknown")


def _who(m: Member) -> str:
    return f"{m.name} ({_sex(m.gender)}, {m.years})"


# ---------------------------------------------------------------------------
# Comparing two snapshots
# ---------------------------------------------------------------------------


def _same_peep(a: Peep, b: Peep) -> bool:
    """One person in two saves: a rename (ChangeName) keeps the gender, head and body."""
    return a.present == b.present and a.gender == b.gender and (a.name == b.name or (a.head, a.body) == (b.head, b.body))


def align(a: Snapshot, b: Snapshot) -> int | None:
    """How many old generations the tree dropped between the snapshots (0 normally), or None: another family."""
    if not a.gens or not b.gens:
        return None
    for shift in range(len(a.gens)):
        if shift and len(b.gens) < R.FAMILY_RECORDS:
            break       # CFamilyTree::MakeRoomInTree drops a record only when the 30 are full
        overlap = min(len(a.gens) - shift, len(b.gens))
        if all(_same_peep(a.gens[shift + i].parent1, b.gens[i].parent1) for i in range(overlap)):
            return shift
    return None


def _member_named(s: Snapshot, peep: Peep) -> Member | None:
    m = s.members.get(peep.slot)
    if m is not None and m.name == peep.name and m.gender == peep.gender:
        return m
    return None


def _role(s: Snapshot, m: Member) -> str:
    if not s.gens:
        return "(not in the Family Tree)"
    g = s.gens[-1]
    for label, peeps in (("Parent", [g.parent1]), ("Parent (married in)", [g.parent2]), ("Child", g.children)):
        for p in peeps:
            if p.present and p.slot == m.slot and p.name == m.name:
                return label
    return "(not in the Family Tree)"


def _person_text(p: Peep, member: Member | None) -> str:
    if member is not None:
        return _who(member)
    return f"{p.name} ({_sex(p.gender)})"


class Step:
    """The lines one newer save adds to the logs, compared with the snapshot before it."""

    def __init__(self, logs: SlotLogs, a: Snapshot, b: Snapshot):
        self.logs, self.a, self.b = logs, a, b
        self.stamp = stamp_of(b)
        self.parents_logged: set = set()
        self.dead_keys: set = set()
        self.cause: dict = {}        # slot -> the save's cause-of-death number (meaning UNCONFIRMED)

    def gen_number(self, index: int) -> int:
        return self.b.gen_offset + index + 1

    def member(self, p: Peep) -> Member | None:
        return _member_named(self.b, p) or _member_named(self.a, p)

    # -- the tree ------------------------------------------------------------

    def marriage(self, index: int) -> None:
        g = self.b.gens[index]
        self.parents_logged.add((g.parent2.name, g.parent2.gender))
        self.logs.history(self.stamp, f"{_person_text(g.parent1, self.member(g.parent1))} married "
                                      f"{_person_text(g.parent2, self.member(g.parent2))}, generation {self.gen_number(index)}")

    def new_generation(self, index: int, after_eviction: bool) -> None:
        g = self.b.gens[index]
        number = self.gen_number(index)
        who = _person_text(g.parent1, self.member(g.parent1))
        self.parents_logged.add((g.parent1.name, g.parent1.gender))
        if number == 1 and after_eviction:
            text = f"Generation 1 began after the eviction: {who} was adopted"
        elif number == 1:
            text = f"Generation 1 began: {who} was adopted and started the family"
        else:
            text = f"New Generation: generation {number} began: {who} inherited the house"
        self.logs.history(self.stamp, text)

    def tree(self, shift: int | None, after_eviction: bool = False) -> None:
        a, b = self.a, self.b
        overlap = 0
        if shift is not None:
            overlap = min(len(a.gens) - shift, len(b.gens))
            for i in range(overlap):
                old, new = a.gens[shift + i], b.gens[i]
                if new.parent2.present and not old.parent2.present:
                    self.marriage(i)
                pairs = [(old.parent1, new.parent1), (old.parent2, new.parent2)]
                pairs += list(zip(old.children, new.children))
                for before, now in pairs:
                    # CFamilyTree::ReportDeath writes -1 into the record of the one who died
                    if before.present and now.present and before.slot >= 0 and now.slot == -1:
                        self.tree_death(before, i)
        for i in range(overlap, len(b.gens)):
            self.new_generation(i, after_eviction)
            if b.gens[i].parent2.present:
                self.marriage(i)

    # -- deaths --------------------------------------------------------------

    def death(self, m: Member, seen_dead: bool, cause: int | None, generation: int) -> None:
        if m.key in self.dead_keys or m.death_logged:
            return
        self.dead_keys.add(m.key)
        cause_text = "not recorded"
        if cause is not None and cause != -1:
            cause_text = f"not recorded (the save's cause number is {cause}; its meaning is not confirmed)"
        number = self.logs.record("deaths", "Death ", [
            f"  Name: {m.name}",
            f"  {'Age at death' if seen_dead else 'Age when last seen'}: {m.years}",
            f"  Sex: {_sex(m.gender)}",
            f"  Cause of death: {cause_text}",
            f"  Head: {m.head}",
            f"  Body: {m.body}",
            f"  Family role: {_role(self.a if not seen_dead else self.b, m)}",
            f"  Generation: {generation}",
        ])
        self.logs.history(self.stamp, f"Death {number}: {_who(m)} died (cause not recorded)")
        self.b.deaths += 1

    def tree_death(self, peep: Peep, index: int) -> None:
        m = _member_named(self.a, peep)
        if m is None:
            m = Member(peep.slot, peep.name, peep.gender, 0, peep.head, peep.body, "home")
            m.age_units = -1
        if m.state == "dead" and m.death_logged:
            return
        if m.age_units < 0:
            # Not in the last save's household: only what the Family Tree holds.
            if (peep.slot, peep.name, peep.gender) in self.dead_keys:
                return
            self.dead_keys.add((peep.slot, peep.name, peep.gender))
            number = self.logs.record("deaths", "Death ", [
                f"  Name: {peep.name}", f"  Sex: {_sex(peep.gender)}", "  Cause of death: not recorded",
                f"  Head: {peep.head}", f"  Body: {peep.body}", f"  Generation: {self.gen_number(index)}"])
            self.logs.history(self.stamp, f"Death {number}: {peep.name} ({_sex(peep.gender)}) died (cause not recorded)")
            self.b.deaths += 1
            return
        self.death(m, False, None, self.gen_number(index))

    # -- the household -------------------------------------------------------

    def household(self, fresh: bool = False) -> None:
        a, b = self.a, self.b
        old = {} if fresh else a.members
        generation = b.generation
        born: set = set()
        # Births: the slots Impregnate reserved (inactive until birth) that are now in the family.
        mothers = [m for m in old.values() if m.pregnant]
        delivered = [s for s, m in old.items() if m.state == "unborn" and s in b.members
                     and b.members[s].state != "unborn"]
        if delivered:
            n = len(delivered)
            born_as = "Single birth" if n == 1 else "Twins" if n == 2 else "Triplets"
            for s in delivered:
                c = b.members[s]
                mother = next((m for m in mothers if m.name == c.mother), mothers[0] if len(mothers) == 1 else None)
                mother_name = c.mother or (mother.name if mother else "(unknown)")
                body = [f"  Child: {c.name}", f"    Sex: {_sex(c.gender)}", f"    Head: {c.head}", f"    Body: {c.body}",
                        f"  Mother: {mother_name}"]
                if mother is not None:
                    body += [f"    Head: {mother.head}", f"    Body: {mother.body}"]
                body += ["  Father: not recorded in the save", f"  Born as: {born_as}", f"  Generation: {generation}"]
                number = self.logs.record("births", "Birth ", body)
                text = f"Birth {number}: {c.name} ({_sex(c.gender)}) was born to {mother_name}"
                if n > 1:
                    text += f" ({born_as})"
                self.logs.history(self.stamp, text)
                born.add(s)
        # Conceptions: a pregnancy this save shows that the last one did not.
        for m in b.members.values():
            before = old.get(m.slot)
            if m.pregnant and not (before is not None and before.key == m.key and before.pregnant):
                number = self.logs.record("births", "Conception ", [
                    f"  Mother: {m.name}", f"    Age when seen pregnant: {m.years}", f"    Sex: {_sex(m.gender)}",
                    f"    Head: {m.head}", f"    Body: {m.body}", "  Father: not recorded in the save",
                    f"  Babies expected: {m.babies}", f"  Generation: {generation}"])
                self.logs.history(self.stamp, f"Conception {number}: {m.name} is expecting (babies expected: {m.babies})")
        # Joined, left home, died.
        for m in b.members.values():
            before = old.get(m.slot)
            same = before is not None and before.key == m.key
            if same:
                m.death_logged = before.death_logged
            if m.state == "unborn":
                continue
            if not same and m.slot not in born:
                if (m.name, m.gender) not in self.parents_logged:
                    role = _role(b, m)
                    where = {"Child": " as a child", "(not in the Family Tree)": " (not in the Family Tree)"}.get(role, "")
                    mother = f" (mother: {m.mother})" if m.mother else ""
                    self.logs.history(self.stamp, f"{_who(m)} joined the family{where}{mother}, generation {generation}")
            if m.state == "away" and not (same and before.state == "away"):
                self.logs.history(self.stamp, f"{_who(m)} left home (game time "
                                              f"{m.left_seconds / R.GAME_SECONDS_PER_YEAR:.1f} years)")
        for m in b.members.values():
            if m.state == "dead":
                before = old.get(m.slot)
                if before is not None and before.key == m.key and before.death_logged:
                    m.death_logged = True
                    continue
                self.death(m, True, self.cause.get(m.slot), generation)
                m.death_logged = True
        # Gone from the save without a death the tree records: the save does not say why.
        for m in old.values():
            now = b.members.get(m.slot)
            if now is not None and now.key == m.key:
                continue
            if m.state in ("unborn",) or m.death_logged or m.state == "dead" or m.key in self.dead_keys:
                continue
            self.logs.history(self.stamp, f"{_who(m)} is no longer in the family; the save does not say why")
        for m in b.members.values():
            if m.key in self.dead_keys:
                m.death_logged = True


def _eviction(logs: SlotLogs, a: Snapshot, b: Snapshot, stamp: str) -> None:
    names = [m.name for m in a.members.values() if m.state in ("home", "away")]
    number = logs.record("events", "Event ", [
        "  Event: Evict Family", f"  Family members: {', '.join(names) if names else '(none)'}",
        f"  Generation: {a.generation}"])
    logs.history(stamp, f"Event {number}: Evict Family")


def backfill(logs: SlotLogs, s: Snapshot) -> None:
    """An existing family logged for the first time: its past, from the save's Family Tree, once."""
    deaths = 0
    for i, g in enumerate(s.gens):
        number = s.gen_offset + i + 1
        p1, p2 = g.parent1, g.parent2
        text = f"Generation {number}: " + (f"{p1.name} ({_sex(p1.gender)})" if p1.present else "(nobody)")
        if p2.present:
            text += f" and {p2.name} ({_sex(p2.gender)})"
        logs.history(BACKFILL_STAMP, text + (" were the parents" if p2.present else " was the parent"))
        for c in g.children:
            if not c.present:
                continue
            line = f"Generation {number}: child {c.name} ({_sex(c.gender)})"
            if c.slot == -1:
                line += ", died"
                deaths += 1
            logs.history(BACKFILL_STAMP, line)
        for p in (p1, p2):
            if p.present and p.slot == -1:
                logs.history(BACKFILL_STAMP, f"Generation {number}: {p.name} died")
                deaths += 1
    for m in s.members.values():
        if m.state == "away":
            logs.history(BACKFILL_STAMP, f"{_who(m)} had left home")
        elif m.state == "dead":
            logs.history(BACKFILL_STAMP, f"{_who(m)} had died")
            deaths += 1
        if m.state == "dead":
            m.death_logged = True
    s.deaths = deaths


# ---------------------------------------------------------------------------
# The pages rewritten at every update
# ---------------------------------------------------------------------------


def population_text(s: Snapshot, slot: int) -> str:
    lines = [f"{GAME} Family Population", header(s.family, slot).rstrip(NL), f"Generation: {s.generation}"]
    k = 0
    for m in sorted(s.members.values(), key=lambda x: x.slot):
        if m.state == "unborn":
            continue
        k += 1
        lines += ["", f"Family Member {k}", f"  Name: {m.name}", f"  Age: {m.years}", f"  Sex: {_sex(m.gender)}",
                  f"  Head: {m.head}", f"  Body: {m.body}", f"  Family role: {_role(s, m)}"]
        if m.state == "dead":
            lines += ["  Health: 0", "  Cause of death: not recorded"]
        if m.pregnant:
            lines += ["  Pregnant: yes", f"  Babies expected: {m.babies}"]
        if m.state == "away":
            lines.append("  Left home: yes")
    if not k:
        lines += ["", "(nobody)"]
    return NL.join(lines) + NL


def statistics_text(s: Snapshot, save: R.FamilySave, slot: int) -> str:
    members = sum(1 for m in s.members.values() if m.state == "home")
    unborn = sum(1 for m in s.members.values() if m.state == "unborn")
    lines = [GAME, "Family Statistics", header(s.family, slot).rstrip(NL), "",
             f"Generations: {s.generation}", f"Family Members: {members}",
             f"Babies Born: {max(0, save.stats.babies_born - unborn)}", f"Deaths: {s.deaths}",
             f"Oldest Family Member Ever: {save.stats.oldest_age_years}", f"Money: ${save.money.amount}",
             f"Food: {save.food.food}"]
    return NL.join(lines) + NL


# ---------------------------------------------------------------------------
# Updating a slot
# ---------------------------------------------------------------------------


@dataclass
class SlotResult:
    slot: int
    status: str              # "updated", "unchanged", "started", "backfilled", "new family", "no save", "unreadable"
    lines: int = 0
    message: str = ""


def family_name(save: R.FamilySave, save_folder: Path, slot: int) -> str:
    if save.nickname:
        return save.nickname
    try:
        settings = R.read_settings(Path(save_folder) / R.save_file_name(0))
        return settings.player_names[slot - 1]
    except (OSError, R.SaveFormatError, IndexError):
        return ""


def _read_save(path: Path) -> R.FamilySave | None:
    try:
        return R.parse_family_save(path.read_bytes())
    except (OSError, R.SaveFormatError, ValueError, IndexError):
        return None


def _set_aside(root: Path, when: datetime) -> Path | None:
    """Move the slot's Logs and Data into Save N\\Backups (a new family starts fresh; nothing is deleted)."""
    moving = [p for p in (root / "Logs", root / "Data") if p.exists()]
    if not moving:
        return None
    base = root / BACKUPS / f"Logs before new family {when.strftime('%Y-%m-%d %H-%M-%S')}"
    target, n = base, 2
    while target.exists():
        target = base.with_name(f"{base.name} ({n})")
        n += 1
    target.mkdir(parents=True)
    for p in moving:
        shutil.move(str(p), str(target / p.name))
    return target


def _write_marker(root: Path, slot: int, family: str, how: str) -> None:
    _write_atomic(data_path(root, BACKFILL_DATA, slot), NL.join([BACKFILL_TAG, f"family\t{_clean(family)}", f"how\t{how}"]) + NL)


def _start(logs: SlotLogs, b: Snapshot, slot: int, how_if_family: str) -> str:
    """A slot's first logs: the headers, and the family's past from the tree (once, with the marker)."""
    logs.create_logs()
    marker = data_path(logs.root, BACKFILL_DATA, slot)
    if marker.is_file():
        return "started"
    if logs.history_lines():
        _write_marker(logs.root, slot, b.family, "logs found")
        return "started"
    if b.gens:
        backfill(logs, b)
        _write_marker(logs.root, slot, b.family, how_if_family)
        return "backfilled"
    _write_marker(logs.root, slot, b.family, "no family yet")
    return "started"


def _step(logs: SlotLogs, a: Snapshot, save: R.FamilySave, save_folder: Path, slot: int) -> tuple[Snapshot, str]:
    b = snapshot_of(save, logs.family)
    cause = {v.slot: v.cause_of_death for v in save.villagers if v.active and v.health <= 0}
    if b.saved_at == a.saved_at:
        b.gen_offset, b.deaths = a.gen_offset, a.deaths
        for m in b.members.values():
            old = a.members.get(m.slot)
            if old is not None and old.key == m.key:
                m.death_logged = old.death_logged
        return b, "unchanged"
    b.deaths = a.deaths
    if b.saved_at < a.saved_at:
        b.gen_offset = a.gen_offset if align(a, b) is not None else 0
        for m in b.members.values():
            old = a.members.get(m.slot)
            if old is not None and old.key == m.key:
                m.death_logged = old.death_logged or m.state == "dead"
            elif m.state == "dead":
                m.death_logged = True
        logs.history(stamp_of(b), "This save is older than the save logged before it (a restored backup or a copy); "
                                  "the logs continue from it, and nothing between the two was logged")
        return b, "updated"
    if b.evicted and not a.evicted:
        _eviction(logs, a, b, stamp_of(b))
        step = Step(logs, Snapshot(a.family, a.saved_at, a.game_seconds, 0, [], {}), b)
        step.cause = cause
        step.tree(None, after_eviction=True)
        step.household(fresh=True)
        return b, "updated"
    if a.gens:
        shift = align(a, b)
        if shift is None:
            # Start Over, a new player or other founders: the slot's logs begin again.
            _set_aside(logs.root, datetime.now())
            logs.written = 0
            if len(b.gens) <= 1:
                logs.create_logs()
                _write_marker(logs.root, slot, b.family, "new family")
                step = Step(logs, Snapshot(b.family, a.saved_at, a.game_seconds, 0, [], {}), b)
                step.cause = cause
                b.deaths = 0
                step.tree(None)
                step.household(fresh=True)
            else:
                b.deaths = 0
                _start(logs, b, slot, "new family")
            return b, "new family"
        b.gen_offset = a.gen_offset + shift
    else:
        shift = None
    step = Step(logs, a, b)
    step.cause = cause
    step.tree(shift)
    step.household()
    return b, "updated"


def update_slot(save_folder: Path, slot: int) -> SlotResult:
    """Bring one slot's logs up to date with its save (and the previous save the game keeps)."""
    save_folder = Path(save_folder)
    path = save_folder / R.save_file_name(slot)
    if not path.is_file():
        return SlotResult(slot, "no save")
    save = _read_save(path)
    if save is None:
        return SlotResult(slot, "unreadable", message=f"{path.name} could not be read as a Virtual Families 2 save.")
    name = family_name(save, save_folder, slot)
    logs = SlotLogs(save_folder, slot, name)
    snap_file = data_path(logs.root, MEMBERS_DATA, slot)
    a = read_snapshot_text(_read(snap_file)) if snap_file.is_file() else None
    status = "unchanged"
    if a is None:
        b = snapshot_of(save, name)
        status = _start(logs, b, slot, "backfilled")
    else:
        chain = []
        previous = _read_save(save_folder / R.save_file_name(slot + R.PREVIOUS_SAVE_OFFSET))
        if previous is not None and a.saved_at < save_time(previous) < save_time(save):
            chain.append(previous)
        chain.append(save)
        b = a
        for s in chain:
            b, what = _step(logs, b, s, save_folder, slot)
            if what != "unchanged":
                status = "new family" if what == "new family" or status == "new family" else what
        if status == "unchanged" and logs.written:
            status = "updated"
    b.family = name
    _write_atomic(page_path(logs.root, "Family Population", slot), population_text(b, slot))
    _write_atomic(page_path(logs.root, "Family Statistics", slot), statistics_text(b, save, slot))
    _write_atomic(snap_file, write_snapshot_text(b))
    return SlotResult(slot, status, logs.written)


def logged_save_folder(name: str) -> bool:
    """The save folders the logs are kept for: the stock game's and every game the patcher built."""
    import vf2_save_backup
    return name.casefold() == GAME.casefold() or vf2_save_backup.is_patcher_save_folder(name)


def update_save_folder(save_folder: Path, processes=None) -> list:
    """Every slot of one save folder. Refused while the game that uses the folder is running."""
    import vf2_save_backup
    if vf2_save_backup.running_game_count(Path(save_folder), processes):
        raise FamilyLogsError(
            f"{Path(save_folder).name}: the game is running. Family Logs are updated from the saves the game "
            "writes when you quit, so quit the game first.")
    return [update_slot(save_folder, slot) for slot in R.FAMILY_SLOTS]


def update_all(documents: Path | None, processes=None) -> list:
    """(save folder, slot results or None, error or None) for every logged save folder in Documents\\LDW."""
    import vf2_save_backup
    outcomes = []
    for folder in vf2_save_backup.find_save_folders(documents):
        if not logged_save_folder(folder.name):
            continue
        try:
            outcomes.append((folder, update_save_folder(folder, processes), None))
        except (FamilyLogsError, OSError) as exc:
            outcomes.append((folder, None, str(exc)))
    return outcomes
