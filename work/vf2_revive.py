"""Revive: the snapshots of the family members who died, for bringing one back (owner, 2026-11-26).

The design is the port of the Virtual Villagers patcher's "Revive Buried/Disappeared Villagers" (docs/revive.md);
the owner's decisions it follows:

* a revived family member is the SAME person: name (with the whole name of the Names file), sex, head and body,
  likes and dislikes, career, fertility and "Wants kids?" (procreation desire); moods and needs start fresh;
* the AGE they come back at (the owner, final): someone who died younger than 20 comes back at the age they died
  at (18 and 19 too); someone who died at 20 or older -- or whose age at death is not known -- comes back at 20, the
  game's own 20-year mark (400 age units), WITH their career, level and salary at death;
* only the DEAD can be revived: never a divorced spouse, a child away (college, Boarding School, the Talent Scout) or
  a member of an evicted family; and only the current generation, for now;
* a dead spouse whose partner has remarried comes back as a family member, not a spouse;
* it costs money (``REVIVE_PRICE``; free with Free and Guaranteed Cheats) and is bought in the game.

What this module holds (none of it changes a save, a log or the Names file):

* the snapshot file: one per save file, beside the save, keyed like the Up to 28 Children file
  (``<save folder>\\Virtual Families 2 Patcher Data\\Revive\\Virtual Families 2<N>.ldw.dat``, N and N + 20), never a
  new field in a save. It names the FNV-1a 64 hash and size of the save it was written for, exactly where the
  Children and Outfits files do, so Copy Player Slot, Move, Rename Family, Game Speed and Back Up re-key it the same
  way (vf2_copy_slot.sidecar_rekeys);
* the BACKFILL for people who died before the patch: read-only sources, in the owner's order -- a stale record in
  the save itself, the game's previous save and the patcher's Backups, the Family Tree entry, then the Family History
  log and the Names file -- with every field marked exact, inferred or unknown. It is idempotent (a second run
  writes nothing), it repairs the Backups folders even while the game runs, and only the running game's own live
  saves wait. Every file is written through a temporary file, read back, an existing one copied aside first, and
  the whole run rolled back when any write fails;
* the rules the in-game purchase follows (who may be revived, the age, the role they return in, the price).

The in-game half -- the capture at each death, the rotation with the game's own save and the Special Upgrades row
"Revive a Family Member" -- is the companion DLL vf2revive_b200.dll (runtime/native/b200revive, the same file format)
and the executable's own code (work/patch_mobile_furniture_pack.py, REVIVE_*); see docs/revive.md.

Snapshot file (little-endian):
    0 "VF2REVIV"   8 version (1)   12 "VF2B200\\0"   20 file size   24 save FNV-1a 64 (8)   32 save size
    36..47 reserved (0)   48 entry count (0..MAX_ENTRIES)   52 entries, ENTRY_SIZE each   then the FNV-1a 64 of
    every byte before it (8).
Entry: see _ENTRY below; ``marks`` holds one byte per field of FIELDS: 0 unknown, 1 inferred, 2 exact.
"""
from __future__ import annotations

import os
import struct
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import vf2_game_text as game_text
import vf2_save_reader as reader

# ---------------------------------------------------------------- the rules

# The price of one revival, in the store's own money: $25,000 (the owner, 2026-11-26); free with Free and Guaranteed
# Cheats. The executable's row holds the same price (work/patch_mobile_furniture_pack.py REVIVE_PRICE).
REVIVE_PRICE = 25_000
ADULT_RETURN_UNITS = 400                # 20 years x 20 age units: the game's 20-year mark
UNITS_PER_YEAR = reader.AGE_UNITS_PER_YEAR

# ---------------------------------------------------------------- the file

FOLDER = "Revive"
DATA_FOLDER = "Virtual Families 2 Patcher Data"
MAGIC = b"VF2REVIV"
TAG = b"VF2B200\0"
VERSION = 1
HEADER = 52
MAX_ENTRIES = 256
BEFORE_BACKFILL = "Before backfill"     # Revive\Before backfill\<time>\<file>: a file the backfill replaced
_FNV_BASIS = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3
_MASK = (1 << 64) - 1

UNKNOWN, INFERRED, EXACT = 0, 1, 2
MARK_WORDS = {UNKNOWN: "unknown", INFERRED: "inferred", EXACT: "exact"}

# Where a snapshot came from, best first. CAPTURED is the game's own capture at the death (the in-game half); the
# rest are the backfill's sources in the owner's order.
CAPTURED, THIS_SAVE, OTHER_SAVE, BACKUP, TREE, LOG = 1, 2, 3, 4, 5, 6
MEMBER = 7          # revived, and living in the house outside the Family Tree's records (the DLL keeps them)
SOURCE_WORDS = {CAPTURED: "captured at the death", THIS_SAVE: "their own record in this save",
                OTHER_SAVE: "their record in the game's other save of the slot", BACKUP: "their record in a backup",
                TREE: "the Family Tree", LOG: "the Family History log",
                MEMBER: "revived: a family member outside the Family Tree"}

FIELDS = ("name", "full_name", "sex", "head", "body", "likes", "dislikes", "likes_text", "dislikes_text", "career",
          "fertility", "procreation_desire", "age_at_death", "cause", "parents", "first_name", "role", "generation",
          "record", "career_level")
_MARKS = 20

ROLE_PARENT, ROLE_SPOUSE, ROLE_CHILD = 0, 1, 2      # role: 0 parent 1, 1 parent 2 (married in), 2 + k child k

# offset, struct format, attribute
_ENTRY = (
    (0, "<I", "source"), (4, "<i", "generation"), (8, "<i", "role"), (12, "<i", "age_at_death"),
    (16, "<i", "cause"), (20, "<i", "sex"), (24, "<i", "head"), (28, "<i", "body"), (32, "<i", "career"),
    (36, "<i", "career_level"), (40, "<i", "fertility"), (44, "<i", "procreation_desire"),
    (48, "<i", "first_name_index"), (52, "<i", "bio_0c"), (56, "<i", "father_head"), (60, "<i", "father_body"),
    (64, "<i", "mother_head"), (68, "<i", "mother_body"), (72, "<i", "heir_sex"), (76, "<i", "heir_head"),
    (80, "<i", "heir_body"),
)
_BYTES = (                              # offset, size, attribute (raw bytes, NUL padded)
    (84, 28, "name"), (112, 28, "heir_name"), (140, 28, "father"), (168, 28, "mother"), (196, 12, "likes"),
    (208, 12, "dislikes"), (220, 40, "likes_text"), (260, 40, "dislikes_text"), (300, _MARKS, "marks"),
    (320, reader.VILLAGER_RECORD_SIZE, "record"), (2300, 1200, "full_name"),
    # the last four bytes (the DLL's S_*): the skin tone and birth tone at the death (B200Skin_ToneOf, Skin Tones),
    # a revived family member's household slot, and flags (1: a tone is kept); read and written back as they are
    (3500, 4, "spare"),
)
ENTRY_SIZE = 3504


def fnv1a64(data: bytes) -> int:
    value = _FNV_BASIS
    for byte in data:
        value = ((value ^ byte) * _FNV_PRIME) & _MASK
    return value


def sidecar_path(folder: Path, number: int) -> Path:
    return Path(folder) / DATA_FOLDER / FOLDER / (reader.save_file_name(number) + ".dat")


def revival_age_units(age_at_death: int | None) -> int:
    """The age a revived family member comes back at, in the game's own age units: 20 (400 units) for anyone who died
    at 20 or older or whose age at death is not known, else the age they died at."""
    if age_at_death is None or age_at_death < 0 or age_at_death >= ADULT_RETURN_UNITS:
        return ADULT_RETURN_UNITS
    return age_at_death


@dataclass
class Snapshot:
    """One family member who died, as far as the sources say. ``marks`` maps each of FIELDS to a mark."""
    source: int = LOG
    generation: int = 0
    role: int = -1
    age_at_death: int = -1
    cause: int = -1
    sex: int = -1
    head: int = -1
    body: int = -1
    career: int = -1
    career_level: int = 0
    fertility: int = 0
    procreation_desire: int = 0
    first_name_index: int = 0
    bio_0c: int = 0
    father_head: int = 0
    father_body: int = 0
    mother_head: int = 0
    mother_body: int = 0
    heir_sex: int = -1
    heir_head: int = -1
    heir_body: int = -1
    name: bytes = b""
    heir_name: bytes = b""
    father: bytes = b""
    mother: bytes = b""
    likes: bytes = b""
    dislikes: bytes = b""
    likes_text: bytes = b""
    dislikes_text: bytes = b""
    record: bytes = b""
    full_name: bytes = b""
    spare: bytes = b"\0\0\0\0"
    marks: dict = field(default_factory=dict)

    def mark(self, name: str) -> int:
        return self.marks.get(name, UNKNOWN)

    @property
    def key(self) -> tuple:
        """Who they are: the generation, the name as the save stores it, sex, head and body."""
        return (self.generation, _strip(self.name), self.sex, self.head, self.body)

    @property
    def name_text(self) -> str:
        whole = _strip(self.full_name)
        return whole.decode("utf-8", "replace") if whole else game_text.decode(_strip(self.name))

    def revival_age(self) -> tuple[int | None, int]:
        """(age units, mark) they would come back at; the mark is exact whenever the rule makes the age certain (a
        death at 20 or older known only to the year, or an unknown age, returns at exactly 20)."""
        if self.mark("age_at_death") == UNKNOWN or self.age_at_death < 0:
            return ADULT_RETURN_UNITS, EXACT
        age = revival_age_units(self.age_at_death)
        if age == ADULT_RETURN_UNITS or self.mark("age_at_death") == EXACT:
            return age, EXACT
        return age, INFERRED


def _strip(raw: bytes) -> bytes:
    return bytes(raw).split(b"\0", 1)[0]


def _pad(raw: bytes, size: int) -> bytes:
    raw = bytes(raw)[:size]
    return raw + b"\0" * (size - len(raw))


def pack_entry(s: Snapshot) -> bytes:
    out = bytearray(ENTRY_SIZE)
    for off, fmt, attr in _ENTRY:
        struct.pack_into(fmt, out, off, getattr(s, attr))
    for off, size, attr in _BYTES:
        if attr == "marks":
            value = bytes(s.marks.get(f, UNKNOWN) for f in FIELDS)
        elif attr == "full_name":
            value = _strip(s.full_name)[:size - 1]
        elif attr in ("name", "heir_name", "father", "mother"):
            value = _strip(getattr(s, attr))[:25]
        else:
            value = getattr(s, attr)
        out[off:off + size] = _pad(value, size)
    return bytes(out)


def unpack_entry(raw: bytes) -> Snapshot | None:
    s = Snapshot()
    for off, fmt, attr in _ENTRY:
        setattr(s, attr, struct.unpack_from(fmt, raw, off)[0])
    for off, size, attr in _BYTES:
        value = bytes(raw[off:off + size])
        if attr == "marks":
            if any(b > EXACT for b in value):
                return None
            s.marks = {f: value[i] for i, f in enumerate(FIELDS)}
        elif attr == "spare":
            setattr(s, attr, value)
        elif attr in ("record", "likes", "dislikes"):
            setattr(s, attr, value)
        else:
            setattr(s, attr, _strip(value))
    for attr in ("record", "likes", "dislikes"):
        if s.mark(attr) == UNKNOWN:
            setattr(s, attr, b"")
    if s.source not in SOURCE_WORDS:
        return None
    return s


@dataclass(frozen=True)
class SnapshotFile:
    save_hash: int
    save_size: int
    entries: list


def read_file(data: bytes) -> SnapshotFile | None:
    """The file as written, or None for anything damaged (wrong tags, size, count or checksum)."""
    if len(data) < HEADER + 8 or data[:8] != MAGIC or data[12:20] != TAG:
        return None
    version, size = struct.unpack_from("<I", data, 8)[0], struct.unpack_from("<I", data, 20)[0]
    count = struct.unpack_from("<I", data, 48)[0]
    if version != VERSION or size != len(data) or count > MAX_ENTRIES or len(data) != HEADER + count * ENTRY_SIZE + 8:
        return None
    if struct.unpack_from("<Q", data, len(data) - 8)[0] != fnv1a64(data[:-8]):
        return None
    entries = []
    for i in range(count):
        s = unpack_entry(data[HEADER + i * ENTRY_SIZE:HEADER + (i + 1) * ENTRY_SIZE])
        if s is None:
            return None
        entries.append(s)
    save_hash, save_size = struct.unpack_from("<QI", data, 24)
    return SnapshotFile(save_hash, save_size, entries)


def make_file(save: bytes, entries: list) -> bytes:
    entries = sorted(entries, key=lambda s: s.key)[:MAX_ENTRIES]
    body = bytearray(HEADER)
    body[:8] = MAGIC
    struct.pack_into("<I", body, 8, VERSION)
    body[12:20] = TAG
    struct.pack_into("<I", body, 20, HEADER + len(entries) * ENTRY_SIZE + 8)
    struct.pack_into("<QI", body, 24, fnv1a64(save), len(save))
    struct.pack_into("<I", body, 48, len(entries))
    for s in entries:
        body += pack_entry(s)
    return bytes(body) + struct.pack("<Q", fnv1a64(bytes(body)))


def describes(data: bytes, save: bytes) -> bool:
    f = read_file(data)
    return f is not None and f.save_size == len(save) and f.save_hash == fnv1a64(save)


# ---------------------------------------------------------------- merging (idempotent; a capture always wins)

_GROUPS = {                      # each mark covers these attributes
    "name": ("name",), "full_name": ("full_name",), "sex": ("sex",), "head": ("head",), "body": ("body",),
    "likes": ("likes",), "dislikes": ("dislikes",), "likes_text": ("likes_text",),
    "dislikes_text": ("dislikes_text",), "career": ("career",), "career_level": ("career_level",),
    "fertility": ("fertility",),
    "procreation_desire": ("procreation_desire",), "age_at_death": ("age_at_death",), "cause": ("cause",),
    "parents": ("father", "mother", "father_head", "father_body", "mother_head", "mother_body"),
    "first_name": ("first_name_index", "bio_0c"), "role": ("role",), "generation": ("generation",),
    "record": ("record",),
}


def merge(a: Snapshot, b: Snapshot) -> Snapshot:
    """The two put together field by field: the better mark wins, then the better source, then ``a``. A snapshot
    captured at the death is never changed."""
    if a.source == CAPTURED:
        return a
    if b.source == CAPTURED:
        return b
    out = replace(a, marks=dict(a.marks))
    for f, attrs in _GROUPS.items():
        if (b.mark(f), -b.source) > (a.mark(f), -a.source):
            for attr in attrs:
                setattr(out, attr, getattr(b, attr))
            out.marks[f] = b.mark(f)
    if not out.heir_name and b.heir_name:
        out.heir_name, out.heir_sex, out.heir_head, out.heir_body = b.heir_name, b.heir_sex, b.heir_head, b.heir_body
    if not (out.spare[3] & 1) and len(b.spare) == 4 and b.spare[3] & 1:
        out.spare = b.spare                      # a skin tone kept at the death
    out.source = min(a.source, b.source)
    return out


def merge_all(entries) -> list:
    by_key: dict[tuple, Snapshot] = {}
    for s in entries:
        by_key[s.key] = merge(by_key[s.key], s) if s.key in by_key else s
    return sorted(by_key.values(), key=lambda s: s.key)


# ---------------------------------------------------------------- reading the sources (read only)

_SEX = {"Male": 0, "Female": 1}
_CAUSE = {"Unknown causes": -1, "Disease": 0, "Starvation": 1, "Old age": 2, "Work accident": 3, "Act of Nature": 4}
_ROLE = {"Parent": ROLE_PARENT, "Parent (married in)": ROLE_SPOUSE, "Child": ROLE_CHILD}


def _record_at(data: bytes, slot: int) -> bytes:
    v = reader.gs_to_file(reader.GS_VILLAGERS) + slot * reader.VILLAGER_RECORD_SIZE
    return bytes(data[v:v + reader.VILLAGER_RECORD_SIZE])


def _peep_raw(data: bytes, record: int, place: int) -> bytes:
    rec = reader.gs_to_file(reader.GS_FAMILY_TREE) + 4 + record * reader.FAMILY_RECORD_SIZE
    at = rec + (0x04, 0xDC)[place] if place < 2 else rec + 0x1B8 + (place - 2) * reader.PEEP_RECORD_SIZE
    return bytes(data[at:at + reader.PEEP_RECORD_SIZE])


def _same(v: reader.Villager, name: bytes, sex: int, head: int, body: int, raw: bytes) -> bool:
    return (_strip(raw[0x18:0x18 + 25]) == name and v.gender == sex and v.head == head and v.body == body)


def _from_record(s: Snapshot, raw: bytes, v: reader.Villager, dead: bool, source: int) -> Snapshot:
    """What their own villager record says. A record of their death is exact; one from a save made while they lived
    is exact for who they are and inferred for the rest ("as when saved")."""
    rest = EXACT if dead else INFERRED
    t = Snapshot(source=source, generation=s.generation, role=s.role, sex=v.gender, head=v.head, body=v.body,
                 name=_strip(raw[0x18:0x18 + 25]), heir_name=s.heir_name, heir_sex=s.heir_sex, heir_head=s.heir_head,
                 heir_body=s.heir_body)
    t.career, t.career_level = v.career_id, v.career_level
    t.fertility, t.procreation_desire = v.fertility, v.procreation_desire
    t.first_name_index, t.bio_0c = v.first_name_index, v.unconfirmed_bio_0c
    t.father, t.mother = _strip(raw[0x3C:0x3C + 25]), _strip(raw[0x56:0x56 + 25])
    t.father_head, t.father_body, t.mother_head, t.mother_body = v.father_head, v.father_body, v.mother_head, \
        v.mother_body
    t.likes, t.dislikes = v.likes_raw, v.dislikes_raw
    t.record = raw
    t.marks = {"name": EXACT, "sex": EXACT, "head": EXACT, "body": EXACT, "parents": EXACT, "first_name": EXACT,
               "likes": rest, "dislikes": rest, "career": rest, "career_level": rest, "fertility": rest,
               "procreation_desire": rest,
               "record": rest}
    if dead:
        t.age_at_death, t.cause = v.age_units, v.cause_of_death
        t.marks.update(age_at_death=EXACT, cause=EXACT)
    return t


@dataclass(frozen=True)
class SaveFile:
    """A save the backfill reads: its bytes, parsed, and where it is."""
    path: Path
    data: bytes
    save: reader.FamilySave
    source: int


def _load(path: Path, source: int) -> SaveFile | None:
    try:
        data = path.read_bytes()
        return SaveFile(path, data, reader.parse_family_save(data), source)
    except (OSError, reader.SaveFormatError, ValueError, IndexError, struct.error):
        return None


def _find_record(s: Snapshot, files: list) -> Snapshot | None:
    """Their record in the first file that holds a death record of theirs; else the first that holds them alive.
    One record exactly: two alike are never guessed between."""
    alive = None
    for f in files:
        hits = [(v, _record_at(f.data, v.slot)) for v in f.save.villagers]
        hits = [(v, raw) for v, raw in hits if _same(v, _strip(s.name), s.sex, s.head, s.body, raw)]
        dead = [(v, raw) for v, raw in hits if v.health <= 0]
        if len(dead) == 1:
            return _from_record(s, dead[0][1], dead[0][0], True, f.source)
        living = [(v, raw) for v, raw in hits if v.health > 0 and v.active]
        if alive is None and len(living) == 1 and not dead:
            alive = _from_record(s, living[0][1], living[0][0], False, f.source)
    return alive


def _tree_snapshot(data: bytes, save: reader.FamilySave, record: int, place: int) -> Snapshot:
    raw = _peep_raw(data, record, place)
    peep = save.family_tree.generations[record]
    p = (peep.parent1, peep.parent2)[place] if place < 2 else peep.children[place - 2]
    heir = _peep_raw(data, record, 0)
    s = Snapshot(source=TREE, generation=record + 1, role=place, sex=p.gender, head=p.head, body=p.body,
                 name=_strip(raw[:25]), career=p.career_id, likes_text=_strip(raw[0x34:0x34 + 0x28]),
                 dislikes_text=_strip(raw[0x5D:0x5D + 0x28]), heir_name=_strip(heir[:25]),
                 heir_sex=peep.parent1.gender, heir_head=peep.parent1.head, heir_body=peep.parent1.body)
    s.marks = {"name": EXACT, "sex": EXACT, "head": EXACT, "body": EXACT, "likes_text": EXACT,
               "dislikes_text": EXACT, "career": EXACT, "role": EXACT, "generation": EXACT}
    return s


def dead_of(f: SaveFile, folder: Path, number: int, slot: int) -> list:
    """The current generation's family members who died, as this save, its Children file and the slot's Family
    History log know them (identity only: the records are looked up afterwards). Divorced, away or evicted family
    members are never here: none of them is dead."""
    import vf2_family_history
    import vf2_genealogy
    import vf2_names
    tree = f.save.family_tree
    cur = tree.current
    if cur is None:
        return []
    record = cur.index
    gen_number = tree.num_generations
    out: list[Snapshot] = []
    places = [(0, cur.parent1), (1, cur.parent2)] + [(2 + k, c) for k, c in enumerate(cur.children)]
    for place, p in places:
        if p.present and p.slot == -1:           # CFamilyTree::ReportDeath is the only writer of -1
            out.append(_tree_snapshot(f.data, f.save, record, place))
    heir = out[0] if out and out[0].role == ROLE_PARENT else _tree_snapshot(f.data, f.save, record, 0)
    # children 7..28: the Up to 28 Children file of this very save
    try:
        kids = vf2_genealogy.read_children_sidecar(
            (Path(folder) / DATA_FOLDER / "Children" / (reader.save_file_name(number) + ".dat")).read_bytes())
    except OSError:
        kids = None
    if kids is not None and kids.save_hash == fnv1a64(f.data) and kids.save_size == len(f.data):
        for i, kid in enumerate(kids.children):
            if kid.state != "dead":
                continue
            s = Snapshot(source=TREE, generation=gen_number, role=ROLE_CHILD + 6 + i, sex=kid.sex, head=kid.head,
                         body=kid.body, name=game_text.field_bytes(kid.name, 25).rstrip(b"\0"),
                         age_at_death=kid.age, heir_name=heir.name, heir_sex=heir.sex, heir_head=heir.head,
                         heir_body=heir.body)
            s.marks = {"name": EXACT, "sex": EXACT, "head": EXACT, "body": EXACT, "role": EXACT, "generation": EXACT,
                       "age_at_death": INFERRED}
            out.append(s)
    # the log: the age and cause of each death, and the dead the tree no longer holds (a childless spouse)
    history = vf2_family_history.read(folder, slot)
    book = vf2_names.Book(folder)
    if history is not None:
        for e in history.entries:
            if e.kind != "Death" or e.generation() != gen_number:
                continue
            whole = e.get("Name", "")
            sex = _SEX.get(e.get("Sex", ""), -1)
            try:
                head, body = int(e.get("Head", "")), int(e.get("Body", ""))
            except ValueError:
                continue
            match = next((s for s in out if s.sex == sex and s.head == head and s.body == body
                          and book.full(slot, game_text.decode(s.name)) == whole), None)
            years = e.get("Age at death", "")
            log = Snapshot(source=LOG, generation=gen_number, sex=sex, head=head, body=body,
                           heir_name=heir.name, heir_sex=heir.sex, heir_head=heir.head, heir_body=heir.body)
            log.marks = {"sex": EXACT, "head": EXACT, "body": EXACT, "generation": EXACT}
            if years.isdigit():
                log.age_at_death = int(years) * UNITS_PER_YEAR
                log.marks["age_at_death"] = INFERRED          # the log keeps whole years
            if e.get("Cause of death", "") in _CAUSE:
                log.cause = _CAUSE[e.get("Cause of death", "")]
                log.marks["cause"] = EXACT
            if match is not None:
                log.name = match.name
                log.marks["name"] = EXACT
                out[out.index(match)] = merge(match, log)
                continue
            role = _ROLE.get(e.get("Family role", ""))
            if role is None:
                continue
            short = next((x.short for x in book.slots.get(slot, []) if x.full == whole), whole)
            log.name = game_text.field_bytes(short, 25).rstrip(b"\0")
            # the save's own form of the name: the Names file's short form, or the whole name when it fits
            log.marks["name"] = EXACT if short != whole or len(whole.encode("utf-8")) <= 18 else INFERRED
            log.full_name = whole.encode("utf-8")              # the log writes the whole name
            log.marks["full_name"] = EXACT
            log.role = role if role != ROLE_CHILD else -1
            log.marks["role"] = EXACT if role != ROLE_CHILD else INFERRED
            # someone alive in this save under the same identity is not dead here (a later death in the log)
            if any(v.active and v.health > 0 and v.gender == sex and v.head == head and v.body == body
                   and v.name == game_text.decode(log.name) for v in f.save.villagers):
                continue
            out.append(log)
    # the whole name from the slot's Names file
    for s in out:
        if s.mark("full_name") == EXACT:
            continue
        whole = book.full(slot, game_text.decode(s.name))
        if whole != game_text.decode(s.name):
            s.full_name = whole.encode("utf-8")
            s.marks["full_name"] = EXACT
        else:
            s.marks.setdefault("full_name", EXACT)       # their name fits the save: it is their whole name
    return out


# ---------------------------------------------------------------- the backfill

@dataclass
class Target:
    """One snapshot file the backfill makes for one save."""
    folder: Path
    number: int
    slot: int
    path: Path
    save: SaveFile
    in_backup: bool
    status: str = ""            # "written", "unchanged", "waits: the game is running", "set aside", "failed: ..."
    entries: list = field(default_factory=list)
    found: list = field(default_factory=list)       # what the sources say of this save's dead
    keep: list = field(default_factory=list)        # what its file already held
    old: bytes | None = None
    new: bytes | None = None


def _sources(folder: Path, number: int, slot: int, target: SaveFile, live: Path) -> list:
    """Their records, in the owner's order: this save, the slot's other save here, the live folder's saves, then
    every backup (newest first)."""
    import vf2_save_backup
    files = [target]
    other = number + reader.PREVIOUS_SAVE_OFFSET if number == slot else slot
    f = _load(Path(folder) / reader.save_file_name(other), OTHER_SAVE if Path(folder) == live else BACKUP)
    if f is not None:
        files.append(f)
    if Path(folder) != live:
        for n in (slot, slot + reader.PREVIOUS_SAVE_OFFSET):
            f = _load(live / reader.save_file_name(n), OTHER_SAVE)
            if f is not None:
                files.append(f)
    for info in vf2_save_backup.list_backups(live):
        if Path(info.path) == Path(folder):
            continue
        for n in (slot, slot + reader.PREVIOUS_SAVE_OFFSET):
            f = _load(Path(info.path) / reader.save_file_name(n), BACKUP)
            if f is not None:
                files.append(f)
    return files


def _existing(folder: Path, number: int, slot: int) -> list:
    """Every snapshot already kept for the slot here (both files, whatever save they name): a source too."""
    out = []
    for n in {number, slot, slot + reader.PREVIOUS_SAVE_OFFSET}:
        try:
            f = read_file(sidecar_path(folder, n).read_bytes())
        except OSError:
            continue
        if f is not None:
            out.extend((n, s) for s in f.entries)
    return out


def plan(folder: Path, live: Path, number: int, slot: int, in_backup: bool) -> Target | None:
    """The snapshot file for one save, without writing anything (None when there is no readable save)."""
    path = Path(folder) / reader.save_file_name(number)
    target = _load(path, THIS_SAVE)
    if target is None:
        return None
    if in_backup:
        target = SaveFile(target.path, target.data, target.save, THIS_SAVE)
    t = Target(Path(folder), number, slot, sidecar_path(folder, number), target, in_backup)
    try:
        t.old = t.path.read_bytes()
    except OSError:
        t.old = None
    sources = _sources(folder, number, slot, target, live)
    found = []
    for s in dead_of(target, folder, number, slot):
        record = _find_record(s, sources)
        found.append(merge(s, record) if record is not None else s)
    keep = []
    if t.old is not None:
        old = read_file(t.old)
        if old is None:
            t.status = "set aside"           # damaged: kept under another name, never overwritten
        else:
            keep = old.entries               # nothing a snapshot file held is ever dropped
    t.found, t.keep = found, keep
    settle(t, [])
    return t


def settle(t: Target, siblings: list) -> None:
    """The file's entries: what it held, then what the slot's snapshot files here and the other save's backfill (the
    ``siblings``, planned in the same run) know of the same people, then what was found (a capture always wins)."""
    wanted = {s.key for s in t.found} | {s.key for s in t.keep}
    elsewhere = BACKUP if t.in_backup else OTHER_SAVE      # the other save's own record is "another save" here
    other_saves = [s for n, s in _existing(t.folder, t.number, t.slot) if n != t.number]
    other_saves += [s for other in siblings for s in other.found]
    extra = [replace(s, source=elsewhere if s.source == THIS_SAVE else s.source)
             for s in other_saves if s.key in wanted]
    t.entries = merge_all(t.keep + extra + t.found)
    t.new = make_file(t.save.data, t.entries)
    if t.status != "set aside":
        t.status = "unchanged" if t.old == t.new else ""


def game_running(folder: Path, processes=None) -> bool:
    """True when the game that saves here runs -- or when that cannot be told (the live saves then wait)."""
    import vf2_save_backup
    try:
        controller = processes if processes is not None else vf2_save_backup.WindowsProcesses()
        return bool(vf2_save_backup.running_games(Path(folder), controller))
    except Exception:  # noqa: BLE001 -- not knowing is treated as running: the live saves wait
        return True


@dataclass
class BackfillResult:
    folder: Path
    targets: list = field(default_factory=list)
    running: bool = False
    error: str | None = None

    @property
    def written(self) -> list:
        return [t for t in self.targets if t.status in ("written", "set aside and written")]


def _aside(path: Path) -> Path:
    stem = path.name[:-len(".dat")]
    for k in range(1, 1000):
        candidate = path.with_name(f"{stem}.unreadable-{k}.dat")
        if not candidate.exists():
            return candidate
    raise OSError(f"no free name to set {path.name} aside")


def _swap_in(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.vf2-revive-tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.read_bytes() != data:
        raise OSError(f"{path} did not read back as written")


def backfill(live: Path, processes=None, now: datetime | None = None) -> BackfillResult:
    """Make or complete every snapshot file of one save folder: its live saves (unless the game runs: they wait) and
    every backup's. Idempotent. All or nothing: when a write fails, every file written by this run is put back as
    it was (and a file set aside is put back under its own name)."""
    import vf2_save_backup
    live = Path(live)
    now = now or datetime.now()
    result = BackfillResult(live, running=game_running(live, processes))
    places = [(live, False)] + [(Path(info.path), True) for info in vf2_save_backup.list_backups(live)]
    for folder, in_backup in places:
        for slot in reader.FAMILY_SLOTS:
            pair = []
            for number in (slot, slot + reader.PREVIOUS_SAVE_OFFSET):
                try:
                    t = plan(folder, live, number, slot, in_backup)
                except (OSError, ValueError, struct.error) as exc:
                    result.targets.append(Target(folder, number, slot, sidecar_path(folder, number), None, in_backup,
                                                 status=f"failed: {exc}"))
                    continue
                if t is not None:
                    pair.append(t)
            for t in pair:                       # each save's file knows what the other's backfill found
                settle(t, [other for other in pair if other is not t])
                if not t.entries and t.old is None:
                    continue
                if not in_backup and result.running:
                    t.status = "waits: the game is running"
                result.targets.append(t)
    done: list[tuple[Target, Path | None, Path | None]] = []      # (target, set-aside name, copy made first)
    try:
        for t in result.targets:
            if t.status in ("unchanged",) or t.status.startswith(("waits", "failed")):
                continue
            aside = copy = None
            if t.status == "set aside":
                aside = _aside(t.path)
                os.replace(t.path, aside)
                done.append((t, aside, None))
                t.old = None
            elif t.old is not None:
                copy = t.path.parent / BEFORE_BACKFILL / now.strftime("%Y-%m-%d %H-%M-%S") / t.path.name
                copy.parent.mkdir(parents=True, exist_ok=True)
                copy.write_bytes(t.old)
                if copy.read_bytes() != t.old:
                    raise OSError(f"the copy of {t.path.name} did not read back")
            if aside is None:
                done.append((t, None, copy))
            _swap_in(t.path, t.new)
            if not describes(t.path.read_bytes(), t.save.data):
                raise OSError(f"{t.path.name} does not describe its save after writing")
            t.status = "set aside and written" if aside is not None else "written"
    except OSError as exc:
        result.error = str(exc)
        for t, aside, _copy in reversed(done):
            try:
                if t.old is not None:
                    _swap_in(t.path, t.old)
                elif t.path.exists():
                    t.path.unlink()
                if aside is not None and aside.exists():
                    os.replace(aside, t.path)
                t.status = "rolled back"
            except OSError as again:
                t.status = f"failed: could not be put back ({again})"
    return result


# ---------------------------------------------------------------- the in-game purchase's rules

def refusal(save: reader.FamilySave, s: Snapshot, history=None) -> str | None:
    """Why ``s`` cannot be revived into ``save``, or None. Only the dead of the current generation of the same
    family come back; a full house refuses."""
    import vf2_game_text as gt
    tree = save.family_tree
    cur = tree.current
    name = gt.decode(_strip(s.name))
    for v in save.villagers:
        if v.active and v.health > 0 and v.name == name and v.gender == s.sex and v.head == s.head \
                and v.body == s.body:
            return f"{s.name_text} is not dead: " + ("they are away from home (college, Boarding School or the "
                                                     "Talent Scout)." if v.left_home else "they are at home.")
    if history is not None:
        for d in history.divorces:
            if d[0] == s.name_text and d[4] == s.generation:
                return f"{s.name_text} was divorced, not dead."
    if cur is None or s.generation != tree.num_generations or (
            gt.decode(_strip(s.heir_name)), s.heir_sex, s.heir_head, s.heir_body) != (
            cur.parent1.name, cur.parent1.gender, cur.parent1.head, cur.parent1.body):
        return f"{s.name_text} is not of the current generation of this family."
    if s.mark("sex") != EXACT or s.mark("head") != EXACT or s.mark("body") != EXACT:
        return f"Who {s.name_text} was is not known exactly."
    if sum(1 for v in save.villagers if v.active) >= reader.VILLAGER_SLOTS:
        return "The house is full (30 family members)."
    return None


def return_role(save: reader.FamilySave, s: Snapshot) -> str:
    """How they come back (the executable's VF2RevivePlan): "spouse" when they were the married-in parent and that
    place is still theirs or empty; a spouse whose partner has remarried comes back as a "family member" who lives
    in the house and takes no place in the Family Tree's records (the owner, 2026-11-26); a parent as "parent"; a
    child, or anyone the six children's places no longer hold, as a "child"."""
    cur = save.family_tree.current
    if s.role == ROLE_SPOUSE:
        if cur is not None and cur.parent2.present and cur.parent2.slot != -1:
            return "family member"
        return "spouse"
    if s.role == ROLE_PARENT:
        return "parent"
    return "child"


def summary(t: Target) -> list[str]:
    """One line per family member: their name, the age they would come back at, and what is not exact."""
    lines = []
    for s in t.entries:
        age, mark = s.revival_age()
        when = f"returns at {age // UNITS_PER_YEAR}" if age is not None else "returns at an unknown age"
        unsure = [f for f in FIELDS if s.mark(f) != EXACT]
        lines.append(f"{s.name_text}: {when} ({MARK_WORDS[mark]}); from {SOURCE_WORDS[s.source]}"
                     + (f"; not exact: {', '.join(unsure)}" if unsure else "; every detail exact"))
    return lines
