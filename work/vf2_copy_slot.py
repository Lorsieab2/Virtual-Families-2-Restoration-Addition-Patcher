"""Copy Player Slot: copy one Virtual Families 2 family, with every file kept for it, into an empty save slot of the
same save folder under a new name, in a closed game's saves.

Modelled on the Fish and Plant Tycoon patcher's Copy Slot (src/save_tools.py copy_slot), on Virtual Families 2's own
layout. Every file below was found by reading the code that writes it.

What belongs to save slot N (1-5)
    * "Virtual Families 2<N>.ldw": the family's save (ldwGameState::MakeGameStatePath; docs/vf2-save-format.md
      section 1).
    * "Virtual Families 2<N+20>.ldw": the game's previous save of the slot, when it keeps one (ldwGameState::Save
      renames N to N+20 before it writes N; the game never loads it).
    * "Virtual Families 2 Patcher Data\\Children\\Virtual Families 2<N>.ldw.dat" and "...<N+20>.ldw.dat": Up to 28
      Children (runtime/native/b200kids/b200kids.cpp, SidecarPath: the save file's name plus ".dat").
    * "Virtual Families 2 Patcher Data\\Outfits\\Virtual Families 2<N>.ldw.dat" and "...<N+20>.ldw.dat": the
      outfit pictures (runtime/native/b200outfits/b200outfits.cpp, SidecarPath).
    * "Virtual Families 2 Patcher\\Save <N>\\": the Family History log (Logs\\Family History\\Family History
      <k>.txt, runtime/native/b200history/b200history.cpp HistoryFile) and the Family Tree Maker's tree file and
      edits (Data\\Family Tree, vf2_tree_memory.tree_file and vf2_family_tree.data_folder), and anything else kept
      there. Its "Family Tree" folder (the tree's picture, page and report, vf2_family_tree.reports_folder) is not
      copied: those are made again from the save every time the tree is made, and a copy would show the old name
      and save number.
    * In the shared settings file "Virtual Families 20.ldw": the slot's slot-menu entry (0x15 bytes at +0x10) and its
      in-use flag (+0x79 + N - 1) (docs/vf2-save-format.md section 7).
    Not per slot, so never copied: ldwLog.txt and wc.dat (shared), the set-aside ".unreadable-K.dat" sidecars (a
    DLL set them aside because they did not describe their save), and the Time Controls and Store Refresh files (they
    sit beside the game, not the saves).

The copy, and how each file stays valid for the copied, renamed save
    * The save is copied byte for byte, then the new name is written where Rename Family writes it (gs+0x25ABC,
      vf2_rename_family). The previous save N+20 is copied too, renamed only when it still holds the old name (as
      Rename Family does). The copies are read back with vf2_save_reader and must parse exactly as the originals,
      but for the name.
    * The settings file gets the target's slot-menu entry (the new name) and its in-use flag, as the game's own
      new-player box writes them; nothing else in it changes. These are its only per-slot fields (docs/vf2-save-
      format.md section 7 lists every field), and they are what the game itself rebuilds at every start:
      theGameState::Load() loads each slot's save and gives one that loads its player name and a set flag.
    * Nothing of a slot lives outside the save folder: the game keeps nothing per slot in the registry (its only
      registry calls are ATL's COM registrar) or elsewhere, and the patcher's DLLs keep nothing per slot beside the
      game (their .ini and .log files there are shared).
    * Children and Outfits sidecars hold the FNV-1a 64 hash and the size of the save file they were written with
      (+24 and +32) and an FNV-1a 64 of every byte before the last 8. Each one is checked as its DLL reads it; one
      that describes the source's save N (or N+20) is re-keyed to the hash and size of that save's copy, with its
      checksum made again, and then checked again against the copy. A sidecar the DLL would take for another save
      (a valid one that describes neither) is copied unchanged: the DLL treats it for the copy exactly as for the
      original. A damaged one is not copied: the DLL would only set it aside.
    * The Family History log: every file's first line, "Family: <name> (Save <N>)", says Save <target>; when the
      name changes, a "Family Renamed" record (Rename Family's) is added to the newest file. The Family Tree
      Maker's tree files (".tree") get the new slot and family name; file names that say "Save <N>" say the
      target's number.

Safety
    * Refused while the game that uses the save folder is running, and when the target slot is in use: it has a save
      file, or the settings file marks it in use. A used slot is never written.
    * Before anything is written the whole save folder is backed up with Back Up Saves' own copier, labelled
      "(before copy)".
    * A deleted family's leftovers in the target slot (its previous save, sidecars, or patcher folder) are never
      overwritten or deleted: each is renamed beside itself with " (set aside before copy <date>)", which no game
      or patcher code reads. They are also in the backup.
    * Every file is written to a temporary file first, then moved into place; a new file never replaces one that
      is there, and the settings file is replaced as Rename Family replaces it. Every file is read back. Any
      failure removes every file the copy made, puts the settings file and every set-aside file back, and so
      leaves the folder as it was. No other slot's file is ever opened for writing.

Nothing here touches Tk; the GUI runs it on a worker thread, and the tests drive it against a temporary save folder
with a fake process list.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import struct
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vf2_rename_family as rename
import vf2_save_backup as save_backup
import vf2_save_reader as reader

SLOTS = tuple(reader.FAMILY_SLOTS)
BACKUP_LABEL = save_backup.BEFORE_COPY
MAX_LENGTH = rename.MAX_LENGTH
PATCHER_FOLDER = "Virtual Families 2 Patcher"           # vf2_genealogy.PATCHER_FOLDER (b200history.cpp kSaves)
DATA_FOLDER = save_backup.DATA_FOLDER                    # "Virtual Families 2 Patcher Data"
SIDECAR_FOLDERS = ("Children", "Outfits")               # b200kids.cpp / b200outfits.cpp SidecarPath
EXPORTS_FOLDER = "Family Tree"                          # Save <N>\Family Tree: made again each time; not copied
TREE_FORMAT = "Virtual Families 2 Patcher family tree"   # vf2_tree_memory.FORMAT
FLAG_FIRST = reader.HEADER_SIZE + 0x79                   # the settings file's in-use flag of slot 1 (gs+0x25B99)
SET_ASIDE = "set aside before copy"

# The two sidecar formats (runtime/native/b200kids/b200kids.cpp and b200outfits.cpp, "the sidecar"): magic, version 1
# at +8, "VF2B200\0" at +12, the file's size at +20, the save file's FNV-1a 64 at +24 and its size at +32, and the
# FNV-1a 64 of every byte before the last 8 at the end.
KIDS_MAGIC = b"VF2KIDS\0"
OUTFITS_MAGIC = b"VF2OUTFT"
SIDECAR_TAG = b"VF2B200\0"
SIDECAR_VERSION = 1
KIDS_HEADER = 52
KIDS_ENTRY = 64
KIDS_MAX_ENTRIES = 22                                    # KIDS_MAX_EXTRA_CHILDREN: children 7 to 28
KIDS_HOUSEHOLD = 30
OUTFITS_SIZE = 188
FNV_BASIS = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
_MASK = (1 << 64) - 1


class CopyError(Exception):
    """A copy that was refused or failed, with a reason a player can read."""


class GameRunning(CopyError):
    """The game that uses this save folder is running."""


def fnv1a64(data: bytes) -> int:
    value = FNV_BASIS
    for byte in data:
        value = ((value ^ byte) * FNV_PRIME) & _MASK
    return value


def save_path(folder: Path, number: int) -> Path:
    return folder / reader.save_file_name(number)


def slot_root(folder: Path, slot: int) -> Path:
    """<save folder>\\Virtual Families 2 Patcher\\Save <N> (vf2_genealogy.slot_root)."""
    return folder / PATCHER_FOLDER / f"Save {slot}"


def sidecar_path(folder: Path, kind: str, number: int) -> Path:
    return folder / DATA_FOLDER / kind / (reader.save_file_name(number) + ".dat")


# ---------------------------------------------------------------------------
# The sidecars
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Sidecar:
    save_hash: int
    save_size: int


def read_sidecar(kind: str, data: bytes) -> Sidecar | None:
    """The save a Children or Outfits sidecar describes, or None when its DLL would find it damaged (the checks of
    ReadSidecar in b200kids.cpp / b200outfits.cpp, as far as the file itself goes)."""
    magic = KIDS_MAGIC if kind == "Children" else OUTFITS_MAGIC
    if len(data) < 44 or data[:8] != magic or data[12:20] != SIDECAR_TAG:
        return None
    version, size = struct.unpack_from("<I", data, 8)[0], struct.unpack_from("<I", data, 20)[0]
    if version != SIDECAR_VERSION or size != len(data):
        return None
    if kind == "Children":
        if len(data) < KIDS_HEADER + 8:
            return None
        count = struct.unpack_from("<I", data, 48)[0]
        if count > KIDS_MAX_ENTRIES or len(data) != KIDS_HEADER + count * KIDS_ENTRY + 8:
            return None
        for k in range(count):
            slot, _gender, state = struct.unpack_from("<iii", data, KIDS_HEADER + k * KIDS_ENTRY)
            if not 0 <= slot < KIDS_HOUSEHOLD or not 1 <= state <= 3:
                return None
    elif len(data) != OUTFITS_SIZE:
        return None
    if struct.unpack_from("<Q", data, len(data) - 8)[0] != fnv1a64(data[:-8]):
        return None
    save_hash, save_size = struct.unpack_from("<QI", data, 24)
    return Sidecar(save_hash, save_size)


def rekeyed(data: bytes, save: bytes) -> bytes:
    """The sidecar describing ``save``: its hash and size, and the checksum made again. Nothing else changes."""
    body = data[:24] + struct.pack("<QI", fnv1a64(save), len(save)) + data[36:-8]
    return body + struct.pack("<Q", fnv1a64(body))


def sidecar_describes(kind: str, data: bytes, save: bytes) -> bool:
    """True when the sidecar's bytes validate as its DLL reads them and name ``save``'s hash and size."""
    sidecar = read_sidecar(kind, data)
    return sidecar is not None and sidecar.save_size == len(save) and sidecar.save_hash == fnv1a64(save)


def sidecar_rekeys(folder: Path, slot: int, saves) -> list[tuple[Path, str, bytes, bytes]]:
    """The sidecars of ``slot`` to re-key after a tool rewrote some of its saves: (path, kind, bytes now, re-keyed).

    ``saves`` is (bytes before, bytes after) for each save the tool rewrote. b200kids and b200outfits take a sidecar
    as their save's only when it names the hash and size of the save as it is on disk (AfterLoad; b200kids otherwise
    keeps only the extra children still at home), so each Children and Outfits file of the slot (N and N+20: both
    DLLs also read the N+20 file for save N) that described one of those saves BEFORE the change is re-keyed to it,
    exactly as a copy's sidecar is (rekeyed: the hash, the size and the checksum, nothing else), and checked again.
    One that is damaged, describes none of them, or whose save did not change is left out. Nothing is written here.
    """
    saves = list(saves)
    out: list[tuple[Path, str, bytes, bytes]] = []
    for kind in SIDECAR_FOLDERS:
        for number in (slot, slot + reader.PREVIOUS_SAVE_OFFSET):
            path = sidecar_path(folder, kind, number)
            try:
                data = path.read_bytes()
            except OSError:
                continue
            for before, after in saves:
                if sidecar_describes(kind, data, before):
                    if after != before:
                        updated = rekeyed(data, after)
                        if sidecar_describes(kind, updated, after):
                            out.append((path, kind, data, updated))
                    break
    return out


# ---------------------------------------------------------------------------
# The slots
# ---------------------------------------------------------------------------


@dataclass
class SlotInfo:
    slot: int
    name: bytes | None              # the family's name in its save, or None
    used: bool                      # a save file is there, or the settings file marks the slot in use
    problem: str | None = None      # why it cannot be copied from

    @property
    def label(self) -> str:
        if self.name is not None:
            return f"Save {self.slot}: {rename.shown(self.name)}"
        if not self.used:
            return f"Save {self.slot}: (empty)"
        return f"Save {self.slot}: (a save the game cannot load)"


def _settings_bytes(folder: Path) -> bytes | None:
    try:
        data = rename.settings_path(folder).read_bytes()
    except OSError:
        return None
    try:
        reader.parse_settings(data)
    except reader.SaveFormatError:
        return None
    return data


def in_use_flag(settings: bytes, slot: int) -> bool:
    return settings[FLAG_FIRST + slot - 1] != 0


def read_slots(folder: Path) -> list[SlotInfo]:
    """Each slot: its family's name, whether it is in use, and why it cannot be copied (None if it can)."""
    settings = _settings_bytes(folder)
    infos: list[SlotInfo] = []
    for slot in SLOTS:
        path = save_path(folder, slot)
        flagged = settings is not None and in_use_flag(settings, slot)
        if not path.exists():
            infos.append(SlotInfo(slot, None, flagged, "This slot has no family."))
            continue
        try:
            name = rename.save_name(path.read_bytes())
        except OSError as exc:
            infos.append(SlotInfo(slot, None, True, f"The save could not be read: {exc}"))
            continue
        info = SlotInfo(slot, name, True)
        if name is None:
            info.problem = f"{path.name} is not a Virtual Families 2 save the game can load."
        elif settings is None:
            info.problem = f"The settings file {rename.settings_path(folder).name} could not be read."
        infos.append(info)
    return infos


def target_problem(folder: Path, slot: int) -> str | None:
    """Why ``slot`` cannot receive a copy (it is in use, or the settings cannot be read), or None."""
    if slot not in SLOTS:
        return f"There is no save slot {slot}."
    if save_path(folder, slot).exists():
        return f"Save {slot} is in use ({reader.save_file_name(slot)} is there). A used slot is never written."
    settings = _settings_bytes(folder)
    if settings is None:
        return f"The settings file {rename.settings_path(folder).name} could not be read."
    if in_use_flag(settings, slot):
        return f"The game's settings mark Save {slot} as in use, so it is never written."
    return None


def confirmation_text(folder: Path, source: int, name: bytes | None, target: int, new_name: str) -> str:
    """The question asked before a copy (the owner, 2026-10-31: every Copy Player Slot has a confirmation prompt)."""
    return (f"Copy \"{rename.shown(name)}\" (Save {source}) into the empty Save {target} as \"{new_name}\"?\n\n"
            f"Save folder: {folder.name}\n\n"
            f"The save folder is backed up first, as \"Backup <date> {BACKUP_LABEL}\". Save {source} and every other "
            "slot are not changed.")


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


@dataclass
class NewFile:
    path: Path              # where the copy goes (never a file that is there)
    data: bytes
    source: Path
    what: str               # for the result: "the save", "Up to 28 Children (re-keyed to the copy)", ...
    describes: int | None = None    # a sidecar: the number of the copied save it must describe (N or N+20)


@dataclass
class CopyPlan:
    folder: Path
    source: int
    target: int
    old_name: bytes
    new_name: str
    original: bytes = b""   # the family's save as it was read
    files: list[NewFile] = field(default_factory=list)
    settings: rename.FileChange | None = None
    set_aside: list[tuple[Path, Path]] = field(default_factory=list)     # (leftover, where it goes)
    notes: list[str] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def _set_aside_name(path: Path, stamp: str) -> Path:
    label = f" ({SET_ASIDE} {stamp})"
    if path.is_dir():
        return path.with_name(path.name + label)
    return path.with_name(path.stem + label + path.suffix)


def leftovers(folder: Path, target: int) -> list[Path]:
    """What a deleted family left in the empty target slot, which the copy would otherwise write over: the previous
    save, the sidecars and the patcher's folder for the slot (the game's delete removes only the save itself)."""
    found = [save_path(folder, target + reader.PREVIOUS_SAVE_OFFSET)]
    for kind in SIDECAR_FOLDERS:
        found += [sidecar_path(folder, kind, target), sidecar_path(folder, kind, target + reader.PREVIOUS_SAVE_OFFSET)]
    found.append(slot_root(folder, target))
    return [path for path in found if path.exists()]


_SAVE_WORD = r"(?<![0-9])Save {n}(?![0-9])"
_HEADER = re.compile(rb"\AFamily: (?P<name>[^\r\n]*) \(Save (?P<slot>[0-9]+)\)")


def _retarget_name(name: str, source: int, target: int) -> str:
    return re.sub(_SAVE_WORD.format(n=source), f"Save {target}", name)


def _patcher_files(root: Path) -> list[Path]:
    """Every file under the slot's patcher folder, relative, except the Family Tree Maker's pictures (Family Tree)."""
    found: list[Path] = []

    def walk(folder: Path, relative: Path) -> None:
        for entry in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
            if relative == Path() and entry.is_dir() and entry.name.casefold() == EXPORTS_FOLDER.casefold():
                continue
            if save_backup._is_link(entry):
                continue
            if entry.is_dir():
                walk(entry, relative / entry.name)
            elif entry.is_file():
                found.append(relative / entry.name)

    if root.is_dir():
        walk(root, Path())
    return found


def _history_file(relative: Path) -> bool:
    parts = [part.casefold() for part in relative.parts]
    return parts[:2] == ["logs", "family history"] and relative.suffix.casefold() == ".txt"


def _history_number(relative: Path) -> int:
    match = re.search(r"(\d+)$", relative.stem)
    return int(match.group(1)) if match else 0


def history_record(old: str, new: str, source: int, when: datetime, number: int) -> bytes:
    """Rename Family's "Family Renamed" record, with the slot the family was copied from."""
    text = (f"[{when:%Y-%m-%d %H:%M:%S}] Family Renamed {number}\r\n"
            f"  Old name: {old or '(no name)'}\r\n  New name: {new}\r\n  Copied from: Save {source}\r\n\r\n")
    return text.encode("latin-1")


def _plan_patcher_folder(plan: CopyPlan, when: datetime) -> None:
    folder, source, target = plan.folder, plan.source, plan.target
    root = slot_root(folder, source)
    out = slot_root(folder, target)
    history: list[NewFile] = []
    for relative in _patcher_files(root):
        data = (root / relative).read_bytes()
        moved = Path(*[_retarget_name(part, source, target) for part in relative.parts])
        what = "patcher file"
        if _history_file(relative):
            what = "Family History log"
            header = _HEADER.match(data)
            if header and header.group("slot") == str(source).encode():
                data = data[:header.start("slot")] + str(target).encode() + data[header.end("slot"):]
        elif relative.suffix.casefold() == ".tree":
            what = "Family Tree Maker tree file"
            try:
                tree = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                tree = None
            if isinstance(tree, dict) and tree.get("format") == TREE_FORMAT:
                if "slot" in tree:
                    tree["slot"] = target
                if "family" in tree:
                    tree["family"] = plan.new_name
                data = json.dumps(tree, indent=1).encode("utf-8")       # as vf2_tree_memory.write_tree_file
            else:
                plan.notes.append(f"{relative} is not a tree file the Family Tree Maker reads; copied as it is.")
        entry = NewFile(out / moved, data, root / relative, what)
        plan.files.append(entry)
        if what == "Family History log":
            history.append(entry)
    old = rename.shown(plan.old_name)
    if history and old != plan.new_name:
        number = 1
        for entry in history:
            text = entry.data.decode("cp1252", errors="replace")
            number = max([number] + [int(n) + 1 for n in rename._RENAMED.findall(text)])
        newest = max(history, key=lambda item: _history_number(item.path.relative_to(out)))
        prefix = b"" if not newest.data or newest.data.endswith(b"\n") else b"\r\n"
        newest.data = newest.data + prefix + history_record(old, plan.new_name, source, when, number)


def _plan_sidecars(plan: CopyPlan, saves: dict[int, tuple[bytes, bytes]]) -> None:
    """``saves``: each save number of the source (N, N+20) -> (its bytes, its copy's bytes)."""
    folder, source, target = plan.folder, plan.source, plan.target
    offset = reader.PREVIOUS_SAVE_OFFSET
    for kind in SIDECAR_FOLDERS:
        what = "Up to 28 Children" if kind == "Children" else "outfit pictures"
        for number, copy_number in ((source, target), (source + offset, target + offset)):
            path = sidecar_path(folder, kind, number)
            if not path.is_file():
                continue
            data = path.read_bytes()
            sidecar = read_sidecar(kind, data)
            if sidecar is None:
                plan.skipped.append((path, f"its {what} file is damaged; its DLL would only set it aside"))
                continue
            describes = next((n for n, (original, _copy) in saves.items()
                              if sidecar.save_hash == fnv1a64(original) and sidecar.save_size == len(original)), None)
            if describes is None:
                plan.files.append(NewFile(sidecar_path(folder, kind, copy_number), data, path, what))
                plan.notes.append(f"{path.name} ({what}) describes no save of Save {source}; copied unchanged, so "
                                  "its DLL treats it for the copy as it does for the original.")
                continue
            copied = saves[describes][1]
            updated = rekeyed(data, copied)
            label = what if updated == data else f"{what} (re-keyed to the copy)"
            plan.files.append(NewFile(sidecar_path(folder, kind, copy_number), updated, path, label,
                                      describes=describes - source + target))


def plan_copy(folder: Path, source: int, target: int, new_name: str, when: datetime | None = None) -> CopyPlan:
    """Every file the copy writes, with its bytes, without writing anything. CopyError when it cannot be done."""
    when = when or datetime.now()
    if source not in SLOTS:
        raise CopyError(f"There is no save slot {source}.")
    if target == source:
        raise CopyError("Choose an empty slot other than the family's own.")
    problem = target_problem(folder, target)
    if problem:
        raise CopyError(problem)
    problem = rename.name_problem(new_name)
    if problem:
        raise CopyError(problem)
    save = save_path(folder, source)
    try:
        data = save.read_bytes()
    except FileNotFoundError as exc:
        raise CopyError(f"Save {source} has no family ({save.name} is missing).") from exc
    except OSError as exc:
        raise CopyError(f"Could not read {save.name}: {exc}") from exc
    old = rename.save_name(data)
    at = rename._name_offset(data)
    if old is None or at is None:
        raise CopyError(f"{save.name} is not a Virtual Families 2 save the game can load.")
    settings_file = rename.settings_path(folder)
    settings = _settings_bytes(folder)
    menu_at = None if settings is None else rename._menu_offset(settings, target)
    if settings is None or menu_at is None:
        raise CopyError(f"The settings file {settings_file.name} is not one the game can load.")
    plan = CopyPlan(folder, source, target, old, new_name, original=data)
    copy = rename._with_name(data, at, rename.NAME_FIELD, new_name)
    saves = {source: (data, copy)}
    previous = save_path(folder, source + reader.PREVIOUS_SAVE_OFFSET)
    if previous.is_file():
        older = previous.read_bytes()
        older_at = rename._name_offset(older)
        older_copy = older
        if older_at is not None and rename.save_name(older) == old:
            older_copy = rename._with_name(older, older_at, rename.NAME_FIELD, new_name)
        saves[source + reader.PREVIOUS_SAVE_OFFSET] = (older, older_copy)
        plan.files.append(NewFile(save_path(folder, target + reader.PREVIOUS_SAVE_OFFSET), older_copy, previous,
                                  "the game's previous save" + (" (renamed)" if older_copy != older else "")))
    _plan_sidecars(plan, saves)
    _plan_patcher_folder(plan, when)
    # The save itself last of the slot's files, then the settings file: until both are written the game sees no
    # family in the target slot.
    plan.files.append(NewFile(save_path(folder, target), copy, save, "the save (renamed)"))
    updated = rename._with_name(settings, menu_at, rename.MENU_FIELD, new_name)
    flag = FLAG_FIRST + target - 1
    updated = updated[:flag] + b"\x01" + updated[flag + 1:]
    plan.settings = rename.FileChange(settings_file, settings, updated)
    stamp = when.strftime("%Y-%m-%d %H-%M-%S")
    plan.set_aside = [(path, _set_aside_name(path, stamp)) for path in leftovers(folder, target)]
    for _path, aside in plan.set_aside:
        if aside.exists():
            raise CopyError(f"{aside.name} is already there; try again in a moment.")
    written = [entry.path for entry in plan.files]
    if len({str(path).casefold() for path in written}) != len(written):
        raise CopyError("Two of the files to copy would have the same name; nothing was changed.")
    return plan


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _write_new(path: Path, data: bytes) -> None:
    """``data`` into a temporary file beside ``path``, then moved to ``path``, which must not be there (on Windows the
    move itself refuses an existing file). Read back."""
    if path.exists():
        raise CopyError(f"{path.name} appeared while copying; it was not written over.")
    temporary = path.with_name(f"{path.name}.copy-{uuid.uuid4().hex[:12]}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "nt":
            os.rename(temporary, path)
        else:
            if path.exists():
                raise CopyError(f"{path.name} appeared while copying; it was not written over.")
            os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    if path.read_bytes() != data:
        raise CopyError(f"{path.name} did not read back as written.")


def _make_folders(folder: Path, path: Path, made: list[Path]) -> None:
    missing: list[Path] = []
    parent = path.parent
    while parent != folder and not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir()
        made.append(directory)


@dataclass
class CopyResult:
    folder: Path
    source: int
    target: int
    old_name: str
    new_name: str
    backup: save_backup.BackupResult
    files: list[NewFile] = field(default_factory=list)
    set_aside: list[tuple[Path, Path]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def _refuse_if_running(folder: Path, processes: save_backup.ProcessController) -> None:
    try:
        running = save_backup.running_games(folder, processes)
    except (OSError, save_backup.BackupError) as exc:
        raise CopyError(f"Could not check whether the game is running, so nothing was changed ({exc}).") from exc
    if running:
        names = ", ".join(sorted({name for _pid, name in running}))
        raise GameRunning(
            f"{names} is running. Close the game first (quit it normally from its menu): it saves by itself every "
            "2 minutes and when it quits, and it would not know about the copied family. Nothing was changed."
        )


def same_but_name(original: bytes, copy: bytes, new_name: str) -> bool:
    """The copy parses exactly as the original but for the family's name (vf2_save_reader), and no byte differs
    outside the name field."""
    at = rename._name_offset(original)
    if at is None or len(original) != len(copy):
        return False
    if any(a != b for i, (a, b) in enumerate(zip(original, copy)) if not at <= i < at + rename.NAME_FIELD):
        return False
    expected = dataclasses.replace(reader.parse_family_save(original), nickname=new_name)
    return reader.parse_family_save(copy) == expected


def verify(plan: CopyPlan) -> None:
    """Read every written file back and check it is valid for the copy; CopyError otherwise."""
    for entry in plan.files:
        if entry.path.read_bytes() != entry.data:
            raise CopyError(f"{entry.path.name} does not hold what was written.")
    target = save_path(plan.folder, plan.target)
    copy = target.read_bytes()
    source = save_path(plan.folder, plan.source).read_bytes()
    if not same_but_name(source, copy, plan.new_name):
        raise CopyError(f"{target.name} does not read back as Save {plan.source} with the new name.")
    previous = save_path(plan.folder, plan.target + reader.PREVIOUS_SAVE_OFFSET)
    copies = {plan.target: copy}
    if any(entry.path == previous for entry in plan.files):
        copies[plan.target + reader.PREVIOUS_SAVE_OFFSET] = previous.read_bytes()
    for entry in plan.files:
        if entry.describes is None:
            continue                # not a sidecar, or one that describes no save of the slot (copied unchanged)
        save = copies.get(entry.describes)
        sidecar = read_sidecar(entry.path.parent.name, entry.path.read_bytes())
        if save is None or sidecar is None or sidecar.save_hash != fnv1a64(save) or sidecar.save_size != len(save):
            raise CopyError(f"{entry.path.name} ({entry.path.parent.name}) does not describe the copied save.")
    settings = reader.parse_settings(rename.settings_path(plan.folder).read_bytes())
    if settings.player_names[plan.target - 1] != plan.new_name or not settings.slot_in_use[plan.target - 1]:
        raise CopyError("The settings file does not list the copied family.")


def _roll_back(plan: CopyPlan, created: list[Path], folders: list[Path], moved: list[tuple[Path, Path]],
               settings_written: bool) -> list[str]:
    problems: list[str] = []
    if settings_written and plan.settings is not None:
        try:
            if plan.settings.path.read_bytes() != plan.settings.original:
                rename._write_atomically(plan.settings.path, plan.settings.original)
        except (OSError, rename.RenameError) as exc:
            problems.append(f"{plan.settings.path.name}: {exc}")
    for path in reversed(created):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            problems.append(f"{path}: {exc}")
    for directory in reversed(folders):
        try:
            directory.rmdir()
        except OSError:
            pass
    for original, aside in reversed(moved):
        try:
            os.rename(aside, original)
        except OSError as exc:
            problems.append(f"{aside.name}: {exc}")
    return problems


def copy_slot(
    folder: Path,
    source: int,
    target: int,
    new_name: str,
    processes: save_backup.ProcessController | None = None,
    now: datetime | None = None,
) -> CopyResult:
    """Copy the family in ``source`` into the empty slot ``target`` of ``folder`` as ``new_name``.

    Refused (CopyError, nothing changed) when the game is running, the target slot is in use, the name breaks the
    game's rule, or the saves cannot be read. Otherwise the folder is backed up first ("(before copy)"), every file
    is written through a temporary file and read back, and any failure puts the folder back as it was.
    """
    controller = processes if processes is not None else save_backup.WindowsProcesses()
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    plan = plan_copy(folder, source, target, new_name, when)
    try:
        backup = save_backup.copy_save_folder(folder, when, suffix=BACKUP_LABEL)
    except save_backup.BackupError as exc:
        raise CopyError(f"The backup before copying failed, so nothing was changed. {exc}") from exc
    _refuse_if_running(folder, controller)        # the backup took a moment
    created: list[Path] = []
    folders: list[Path] = []
    moved: list[tuple[Path, Path]] = []
    settings_written = False
    try:
        if target_problem(folder, target):
            raise CopyError(target_problem(folder, target))
        if save_path(folder, source).read_bytes() != plan.original:
            raise CopyError("The family's save changed while it was being copied.")
        if plan.settings.path.read_bytes() != plan.settings.original:
            raise CopyError(f"{plan.settings.path.name} changed while the family was being copied.")
        for original, aside in plan.set_aside:
            os.rename(original, aside)
            moved.append((original, aside))
        for entry in plan.files:
            _make_folders(folder, entry.path, folders)
            _write_new(entry.path, entry.data)
            created.append(entry.path)
        settings_written = True
        rename._write_atomically(plan.settings.path, plan.settings.updated)
        verify(plan)
    except (OSError, CopyError, rename.RenameError, reader.SaveFormatError) as exc:
        problems = _roll_back(plan, created, folders, moved, settings_written)
        if problems:
            raise CopyError(
                f"The copy failed ({exc}) and these could not be put back: {'; '.join(problems)}. "
                f"Your backup is in {backup.backup_folder}."
            ) from exc
        raise CopyError(
            f"The copy failed ({exc}); everything was put back as it was. A backup is in {backup.backup_folder}."
        ) from exc
    return CopyResult(folder, source, target, rename.shown(plan.old_name), new_name, backup, plan.files,
                      plan.set_aside, plan.notes, plan.skipped)
