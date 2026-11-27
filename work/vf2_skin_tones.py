"""Skin Tones: see and change each family member's skin tone in a closed game's saves.

The Skin Tones DLL (vf2skin_b200.dll, runtime/native/b200skin/b200skin.cpp) draws every family member in their skin
tone and keeps the tones beside each save FILE, never in the save:

    <save folder>\\Virtual Families 2 Patcher Data\\Skin Tones\\Virtual Families 2<N>.ldw.dat   (and <N+20>)

The file (little-endian; the DLL reads and writes exactly this)
    header, 52 bytes: +0 "VF2SKIN\\0"; +8 u32 version 1; +12 "VF2B200\\0"; +20 u32 the file's size; +24 u64 FNV-1a 64
    of the save file it describes; +32 u32 that save's size; +36 i32 generations; +40 i32 parent 1's slot; +44 i32
    parent 1's gender (both from the current Family Tree record, -1 when there is none); +48 u32 entry count (<= 400).
    entries, 64 bytes each: +0 i32 slot (-1 when not in the house, else 0..29); +4 i32 gender (0 male, 1 female);
    +8 char name[26] (the save's stored 25-byte name and a NUL); +34 u8 tone (0 none yet, 1..10, 15 Game's own
    chosen); +35 u8 birth tone (0..10); +36 i32 head; +40 i32 body; +44 i32 gen[2]; +52 i32 place[2] (Family Tree
    places: generation 0..30, 0 none; place 0..7); +60 u32 person (copies of one person share it).
    then the FNV-1a 64 of every byte before it.

Which file the game uses for save N (AfterLoad), and so the one file changed here
    1. the N file, when it names the hash and size of save N as it is on disk;
    2. else the N+20 file, when it names save N;
    3. else the N file, when it is valid and its generations, parent 1's slot and parent 1's gender are the save's
       current Family Tree's.
    None: the family has no skin tones yet (it is played once with Skin Tones on). A damaged N file: nothing is
    changed (the DLL sets it aside itself).

A household member's entry: slot, gender and stored name all match. Changing a person changes the tone of every
entry with their person number (copies of one person); the save hash and size stay (the save is not changed), and
only the checksum is made again.

Safety, as Rename Family (vf2_rename_family): refused while the game runs; the save folder is backed up first
("(before skin tones)"); the file is written beside itself and swapped in, read back and checked, and put back on
any failure. One "Appearance changed" record per changed person is added to the slot's Family History log when one
exists. Nothing here touches Tk.
"""
from __future__ import annotations

import os
import re
import struct
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import vf2_family_history as family_history
import vf2_names as names
import vf2_rename_family as rename
import vf2_save_backup as save_backup
import vf2_save_reader as reader

FOLDER = "Skin Tones"
SLOTS = tuple(reader.FAMILY_SLOTS)
BACKUP_LABEL = save_backup.BEFORE_SKIN_TONES
MAGIC = b"VF2SKIN\0"
TAG = b"VF2B200\0"
VERSION = 1
HEADER = 52
ENTRY = 64
MAX_ENTRIES = 400
HOUSEHOLD = reader.VILLAGER_SLOTS        # 30
TREE_GENERATIONS = reader.FAMILY_RECORDS  # 30
PLACES = 8                               # parent 1, parent 2, six children
NONE = 0
GAME_OWN = 15
TONE_COUNT = 10
_HEAD = struct.Struct("<8sI8sIQIiiiI")
_ENTRY = struct.Struct("<ii26sBBiiiiiiI")
FNV_BASIS = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
_MASK = (1 << 64) - 1

TONE_NAMES = ("Porcelain", "Fair", "Light golden", "Light olive", "Copper", "Warm brown", "Medium brown",
              "Deep brown", "Dark", "Ebony")
GAME_OWN_LABEL = "Game's own"
RESET_LABEL = "Reset to birth tone"
NOT_SET_LABEL = "(not set yet)"
NO_TONE_YET = "(no tone yet: play this family once)"
PRESETS = (GAME_OWN_LABEL,) + tuple(f"S{k} {name}" for k, name in enumerate(TONE_NAMES, start=1))


class SkinToneError(Exception):
    """A change that was refused or failed, with a reason a player can read."""


class GameRunning(SkinToneError):
    """The game that uses this save folder is running."""


def fnv1a64(data: bytes) -> int:
    value = FNV_BASIS
    for byte in data:
        value = ((value ^ byte) * FNV_PRIME) & _MASK
    return value


def sidecar_path(folder: Path, number: int) -> Path:
    return Path(folder) / save_backup.DATA_FOLDER / FOLDER / (reader.save_file_name(number) + ".dat")


# ---------------------------------------------------------------------------
# The file
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    slot: int
    gender: int
    name: bytes             # all 26 bytes, kept exactly
    tone: int
    birth: int
    head: int
    body: int
    gen: tuple
    place: tuple
    person: int

    @property
    def stored_name(self) -> bytes:
        return _upto_nul(self.name[:25])


@dataclass(frozen=True)
class ToneFile:
    save_hash: int
    save_size: int
    generations: int
    parent_slot: int
    parent_gender: int
    entries: tuple


def _upto_nul(raw: bytes) -> bytes:
    end = raw.find(b"\0")
    return bytes(raw if end < 0 else raw[:end])


def _entry_valid(e: Entry) -> bool:
    if not -1 <= e.slot < HOUSEHOLD or e.gender not in (0, 1) or e.name[25] != 0:
        return False
    if not (1 <= e.tone <= TONE_COUNT or e.tone in (NONE, GAME_OWN)) or e.birth > TONE_COUNT:
        return False
    return all(0 <= g <= TREE_GENERATIONS and 0 <= p < PLACES for g, p in zip(e.gen, e.place))


def read_file(data: bytes) -> ToneFile | None:
    """The file as the DLL reads it (ReadSidecar), or None when the DLL would find it damaged."""
    data = bytes(data)
    if len(data) < HEADER + 8:
        return None
    magic, version, tag, size, save_hash, save_size, gens, pslot, pgender, count = _HEAD.unpack_from(data, 0)
    if magic != MAGIC or tag != TAG or version != VERSION or size != len(data):
        return None
    if count > MAX_ENTRIES or len(data) != HEADER + count * ENTRY + 8:
        return None
    if struct.unpack_from("<Q", data, len(data) - 8)[0] != fnv1a64(data[:-8]):
        return None
    entries = []
    for k in range(count):
        slot, gender, name, tone, birth, head, body, g0, g1, p0, p1, person = _ENTRY.unpack_from(data, HEADER + k * ENTRY)
        entry = Entry(slot, gender, name, tone, birth, head, body, (g0, g1), (p0, p1), person)
        if not _entry_valid(entry):
            return None
        entries.append(entry)
    return ToneFile(save_hash, save_size, gens, pslot, pgender, tuple(entries))


def make_file(tones: ToneFile) -> bytes:
    """The file's bytes, exactly as the DLL writes them (WriteSidecar)."""
    count = len(tones.entries)
    size = HEADER + count * ENTRY + 8
    out = bytearray(_HEAD.pack(MAGIC, VERSION, TAG, size, tones.save_hash, tones.save_size, tones.generations,
                               tones.parent_slot, tones.parent_gender, count))
    for e in tones.entries:
        out += _ENTRY.pack(e.slot, e.gender, bytes(e.name).ljust(26, b"\0")[:26], e.tone, e.birth, e.head, e.body,
                           e.gen[0], e.gen[1], e.place[0], e.place[1], e.person)
    out += struct.pack("<Q", fnv1a64(bytes(out)))
    return bytes(out)


def describes(tones: ToneFile, save: bytes) -> bool:
    return tones.save_size == len(save) and tones.save_hash == fnv1a64(save)


def tone_name(tone: int) -> str:
    """The tone's name as the log writes it."""
    return TONE_NAMES[tone - 1] if 1 <= tone <= TONE_COUNT else GAME_OWN_LABEL


def tone_label(tone: int) -> str:
    """The tone as the window's box shows it."""
    if tone == NONE:
        return NOT_SET_LABEL
    return f"S{tone} {TONE_NAMES[tone - 1]}" if 1 <= tone <= TONE_COUNT else GAME_OWN_LABEL


def choice_value(label: str, birth: int) -> int | None:
    """The tone a box's choice stores, or None for a choice that changes nothing ("(not set yet)")."""
    if label == GAME_OWN_LABEL:
        return GAME_OWN
    if label == RESET_LABEL:
        return birth if 1 <= birth <= TONE_COUNT else None
    if label in PRESETS:
        return PRESETS.index(label)
    return None


def choices(member: "Member") -> list[str]:
    """The box's values for one family member: the presets, and Reset to birth tone when they have one."""
    out = list(PRESETS)
    if 1 <= member.birth <= TONE_COUNT:
        out.append(RESET_LABEL)
    return out


# ---------------------------------------------------------------------------
# The family
# ---------------------------------------------------------------------------


@dataclass
class Member:
    slot: int                 # the villager slot
    gender: int
    name: str                 # the whole name
    age_years: int
    head: int
    body: int
    entry: int | None         # index into the file's entries, or None (no tone yet)
    tone: int = NONE
    birth: int = NONE

    @property
    def editable(self) -> bool:
        return self.entry is not None

    @property
    def shown_tone(self) -> str:
        return tone_label(self.tone) if self.editable else NO_TONE_YET


@dataclass
class Family:
    folder: Path
    slot: int
    problem: str | None = None            # why nothing can be changed (no tones yet, a damaged file, ...)
    path: Path | None = None              # the file the game uses for this save
    data: bytes = b""                     # its bytes as read
    tones: ToneFile | None = None
    members: list[Member] = field(default_factory=list)
    generations: int = 0


def _family_tree_key(save: reader.FamilySave) -> tuple[int, int, int] | None:
    cur = save.family_tree.current
    if cur is None:
        return None
    return save.family_tree.num_generations, cur.parent1.slot, cur.parent1.gender


def _stored_name(data: bytes, slot: int) -> bytes:
    at = reader.gs_to_file(reader.GS_VILLAGERS) + slot * reader.VILLAGER_RECORD_SIZE + 0x08 + 0x10
    return _upto_nul(data[at:at + 25])


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SkinToneError(f"Could not read {path.name}: {exc}") from exc


def choose_file(folder: Path, slot: int, save_bytes: bytes,
                save: reader.FamilySave) -> tuple[Path | None, bytes, ToneFile | None, str | None]:
    """The file the game uses for save ``slot`` (path, bytes, parsed), or (None, b"", None, why)."""
    own = sidecar_path(folder, slot)
    own_bytes = _read(own)
    own_file = read_file(own_bytes) if own_bytes is not None else None
    if own_bytes is not None and own_file is None:
        return None, b"", None, (f"The skin tones file {own.name} is damaged, so nothing can be changed. The game "
                                 "sets it aside by itself the next time it loads this family.")
    if own_file is not None and describes(own_file, save_bytes):
        return own, own_bytes, own_file, None
    previous = sidecar_path(folder, slot + reader.PREVIOUS_SAVE_OFFSET)
    previous_bytes = _read(previous)
    previous_file = read_file(previous_bytes) if previous_bytes is not None else None
    if previous_file is not None and describes(previous_file, save_bytes):
        return previous, previous_bytes, previous_file, None
    key = _family_tree_key(save)
    if own_file is not None and key is not None and \
            (own_file.generations, own_file.parent_slot, own_file.parent_gender) == key:
        return own, own_bytes, own_file, None
    return None, b"", None, ("This family has no skin tones yet. Play it once with the Skin Tones patch on: the "
                             "game gives everybody a tone then.")


def read_family(folder: Path, slot: int) -> Family:
    """The family in ``slot`` and the tones the game uses for it. Only read."""
    folder = Path(folder)
    family = Family(folder, slot)
    save_file = rename.save_path(folder, slot)
    try:
        data = save_file.read_bytes()
    except FileNotFoundError:
        family.problem = "This slot has no family."
        return family
    except OSError as exc:
        family.problem = f"The save could not be read: {exc}"
        return family
    try:
        save = reader.parse_family_save(data)
    except (reader.SaveFormatError, ValueError, struct.error):
        family.problem = f"{save_file.name} is not a Virtual Families 2 save the game can load."
        return family
    family.generations = save.family_tree.num_generations
    try:
        path, raw, tones, problem = choose_file(folder, slot, data, save)
    except SkinToneError as exc:
        family.problem = str(exc)
        return family
    family.path, family.data, family.tones, family.problem = path, raw, tones, problem
    book = names.Book(folder)
    for v in save.household():
        entry = None
        if tones is not None:
            stored = _stored_name(data, v.slot)
            entry = next((k for k, e in enumerate(tones.entries)
                          if e.slot == v.slot and e.gender == v.gender and e.stored_name == stored), None)
        member = Member(v.slot, v.gender, book.full(slot, v.name), v.age_years, v.head, v.body, entry)
        if entry is not None:
            member.tone, member.birth = tones.entries[entry].tone, tones.entries[entry].birth
        family.members.append(member)
    return family


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


@dataclass
class Change:
    member: Member
    old: int
    new: int


@dataclass
class ToneResult:
    folder: Path
    slot: int
    path: Path
    backup: save_backup.BackupResult
    changes: list[Change] = field(default_factory=list)
    notes: list[Path] = field(default_factory=list)      # the Family History files that noted the changes


def edited(tones: ToneFile, family: Family, wanted: dict[int, int]) -> tuple[ToneFile, list[Change]]:
    """The file with each wanted tone (villager slot -> stored tone) set on every entry of that person."""
    entries = list(tones.entries)
    changes: list[Change] = []
    by_slot = {m.slot: m for m in family.members}
    for slot, new in wanted.items():
        member = by_slot.get(slot)
        if member is None or member.entry is None:
            raise SkinToneError("That family member has no skin tone yet: play this family once with Skin Tones on.")
        if not (1 <= new <= TONE_COUNT or new == GAME_OWN):
            raise SkinToneError(f"{new} is not a skin tone.")
        old = entries[member.entry].tone
        if new == old:
            continue
        person = entries[member.entry].person
        for k, e in enumerate(entries):
            if k == member.entry or (person and e.person == person):
                entries[k] = replace(e, tone=new)
        changes.append(Change(member, old, new))
    return replace(tones, entries=tuple(entries)), changes


def _refuse_if_running(folder: Path, processes: save_backup.ProcessController) -> None:
    try:
        running = save_backup.running_games(folder, processes)
    except (OSError, save_backup.BackupError) as exc:
        raise SkinToneError(f"Could not check whether the game is running, so nothing was changed ({exc}).") from exc
    if running:
        shown = ", ".join(sorted({name for _pid, name in running}))
        raise GameRunning(
            f"{shown} is running. Close the game first (quit it normally from its menu): it writes the skin tones "
            "itself when it saves, which would put the old ones back. Nothing was changed."
        )


def _write_atomically(path: Path, data: bytes) -> None:
    temporary = path.with_name(f"{path.name}.skin-{uuid.uuid4().hex[:12]}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    if path.read_bytes() != data:
        raise SkinToneError(f"{path.name} did not read back as written.")


_CHANGED = re.compile(r"^\[[^\]]*\] Appearance changed (\d+)\r?$", re.MULTILINE)


def history_record(change: Change, generations: int, when: datetime, number: int) -> str:
    """One "Appearance changed" record, in the Family History log's own layout (b200history.cpp Self, Field)."""
    m = change.member
    return (f"[{when:%Y-%m-%d %H:%M:%S}] Appearance changed {number}\r\n"
            f"  Name: {m.name}\r\n"
            f"  Age: {m.age_years}\r\n"
            f"  Sex: {'Female' if m.gender == 1 else 'Male'}\r\n"
            f"  Head: {m.head}\r\n"
            f"  Body: {m.body}\r\n"
            f"  Old skin tone: {tone_name(change.old)}\r\n"
            f"  New skin tone: {tone_name(change.new)}\r\n"
            f"  How: Skin Tones window\r\n"
            f"  Generation: {generations}\r\n\r\n")


def log_changes(folder: Path, slot: int, changes: list[Change], generations: int, when: datetime) -> Path | None:
    """One "Appearance changed" record per change, added to the slot's newest Family History file and numbered after
    every earlier one in all of its files, if the log exists; returns the file written."""
    logs = rename.history_folder(folder, slot)
    files = []
    k = 1
    while (logs / f"Family History {k}.txt").is_file():
        files.append(logs / f"Family History {k}.txt")
        k += 1
    if not files or not changes:
        return None
    number = 1
    for path in files:
        text = family_history.log_text(path.read_bytes())
        number = max([number] + [int(n) + 1 for n in _CHANGED.findall(text)])
    newest = files[-1]
    data = newest.read_bytes()
    prefix = b"" if not data or data.endswith(b"\n") else b"\r\n"
    text = "".join(history_record(c, generations, when, number + k) for k, c in enumerate(changes))
    with open(newest, "ab") as out:
        out.write(prefix + family_history.log_bytes(text))
    return newest


def set_tones(
    folder: Path,
    slot: int,
    wanted: dict[int, int],
    processes: save_backup.ProcessController | None = None,
    now: datetime | None = None,
) -> ToneResult:
    """Set the tones ``wanted`` (villager slot -> stored tone: 1..10, 15 Game's own) for the family in ``slot``.

    Refused (SkinToneError, nothing changed) while the game runs, when the family has no tones file or a damaged one,
    or when nothing would change. Otherwise the folder is backed up first, the file is replaced atomically and read
    back, and any failure puts it back as it was."""
    folder = Path(folder)
    if slot not in SLOTS:
        raise SkinToneError(f"There is no family slot {slot}.")
    controller = processes if processes is not None else save_backup.WindowsProcesses()
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    family = read_family(folder, slot)
    if family.problem is not None or family.tones is None or family.path is None:
        raise SkinToneError(family.problem or "This family has no skin tones yet.")
    updated, changes = edited(family.tones, family, wanted)
    if not changes:
        raise SkinToneError("Nothing to change: every family member already has the tone chosen.")
    new_bytes = make_file(updated)
    try:
        backup = save_backup.copy_save_folder(folder, when, suffix=BACKUP_LABEL)
    except save_backup.BackupError as exc:
        raise SkinToneError(f"The backup before changing the skin tones failed, so nothing was changed. {exc}") from exc
    _refuse_if_running(folder, controller)        # the backup took a moment
    path, original = family.path, family.data
    try:
        if path.read_bytes() != original:
            raise SkinToneError(f"{path.name} changed while the skin tones were being set.")
        _write_atomically(path, new_bytes)
        if read_file(path.read_bytes()) != updated:
            raise SkinToneError(f"{path.name} does not hold the new skin tones.")
    except (OSError, SkinToneError) as exc:
        problem = None
        try:
            if path.read_bytes() != original:
                _write_atomically(path, original)
        except (OSError, SkinToneError) as undo:
            problem = undo
        if problem is not None:
            raise SkinToneError(
                f"Setting the skin tones failed ({exc}) and {path.name} could not be put back ({problem}). "
                f"Your backup is in {backup.backup_folder}.") from exc
        raise SkinToneError(
            f"Setting the skin tones failed ({exc}); the file was put back as it was. A backup is in "
            f"{backup.backup_folder}.") from exc
    notes: list[Path] = []
    try:
        noted = log_changes(folder, slot, changes, family.generations, when)
        if noted is not None:
            notes.append(noted)
    except OSError:
        pass            # the tones are set; a log the patcher cannot write is left as it is
    return ToneResult(folder, slot, path, backup, changes, notes)
