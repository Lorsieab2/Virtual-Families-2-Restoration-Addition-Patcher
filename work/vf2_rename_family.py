"""Rename Family: change the name a Virtual Families 2 family slot is shown under, in a closed game's saves.

Ported from the Virtual Families 1 patcher's Rename Family. Virtual Families 2 has NO family surname: a family
member has one name and the save holds no family-name field (docs/vf2-save-format.md section 4). The one name
the player types for a family slot, and the one the game shows for it, is the PLAYER NAME. Every address below is
in the stock "Virtual Families 2.exe" (docs/vf2-save-format.md section 11 gives the desktop-object names too).

Where the name lives and where the game shows it (VERIFIED)
    * Entered: the new-player box "Please enter your name..." (string 0xA32, 0x4FB84C). The first player's dialog
      stores it with GetText(gs+0x25ABC, 0x14) at 0x41F9D2..0x41F9DB, then copies it to the slot-menu list
      (0x41F9E0..0x41F9FA); Change Player's NEW PLAYER box does the same for slot N at 0x41F457..0x41F49C.
    * Saved: in the slot save "Virtual Families 2<N>.ldw" at gs+0x25ABC (20 bytes, NUL-terminated).
    * Slot menu: theGameState::Load 0x42A2E0 loads each slot 1..5 at every start and copies that save's
      gs+0x25ABC into the slot-menu list in the settings file "Virtual Families 20.ldw" (gs+0x25B30 + 0x15 x
      (N - 1), 0x15 bytes each; 0x42A3BD..0x42A4EE); a slot whose save does not load gets "NEW PLAYER" (0xA34).
      Change Player shows that list (0x41EDE6).
    * Main menu: "Player: " (0xA31) beside gs+0x25ABC (theMenuScene::UpdateShowPlayer 0x443B80, 0x443BAC).
    * The daily email greets the player with it (0x417B40).
    * The game has no rename of its own: clicking an existing player in Change Player only switches to it.

The rule (VERIFIED)
    The box takes at most 20 keys (SetCanEdit(1, 0x14) at 0x41F92A and 0x41EE0C; the length check is
    0x40E5D3), but GetText(buffer, 0x14) strncpy's 20 bytes and forces buffer[19] = 0 (0x40E22B), so at most 19
    characters are ever stored. The box accepts keys 0x20..0xFF (0x40E5DF..0x40E5EA). An empty box is refused
    (theChangePlayerDlg puts NEW PLAYER back), and a box whose text is exactly "NEW PLAYER" is treated as an
    empty slot (strcmp 0x41F315..0x41F359), so that name is refused here. Only printable ASCII 0x20..0x7E is
    accepted here. A name that breaks the rule is refused, never cut short.
    UNCONFIRMED (not traced): whether keys 0x80..0xFF ever reach the box from a keyboard, and which symbols
    the game's font can draw.

What is written
    * The slot save: gs+0x25ABC (20 bytes): the new name, the rest zeroed.
    * The game's previous save of the slot, "Virtual Families 2<N+20>.ldw", only when it still holds the old
      name (the game never loads it, but it is the same family's earlier save; anything else is left alone).
    * The settings file's slot-menu entry for the slot (0x15 bytes), so the menu shows the new name before the
      game rebuilds it.
    Nothing else changes. There is no checksum; the loader checks the "ldwg" magic and the payload size.

Safety
    * The game must be closed: it saves by itself every 2 minutes and when it quits, which would put the old
      name straight back. Nothing here ever closes or pauses a game.
    * Before anything is written the whole save folder is backed up with Back Up Saves' own copier, labelled
      "(before rename)".
    * Every file is written beside itself and swapped in with os.replace, then read back. Any failure puts every
      file already changed back exactly as it was.
    * No log and no data file is written. The Up to 28 Children file beside a save is named after the save file,
      not the name, so it is untouched.

Nothing here touches Tk; the GUI runs it on a worker thread, and the tests drive it against a temporary copy of a
save folder with a fake process list.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vf2_save_backup as save_backup
import vf2_save_reader as reader

SLOTS = tuple(reader.FAMILY_SLOTS)
BACKUP_LABEL = save_backup.BEFORE_RENAME
MAX_LENGTH = 19                          # GetText(buffer, 0x14) keeps 19 characters (0x40E22B)
NAME_FIELD = 20                          # gs+0x25ABC, char[20]
MENU_FIELD = 0x15                        # one slot-menu entry in the settings file
MENU_FIRST = reader.HEADER_SIZE + 0x10   # file offset of slot 1's entry (gs+0x25B30)
EMPTY_SLOT_TEXT = "NEW PLAYER"           # string 0xA34: the game's text for an empty slot
PRINTABLE = frozenset(chr(code) for code in range(0x20, 0x7F))


class RenameError(Exception):
    """A rename that was refused or failed, with a reason a player can read."""


class GameRunning(RenameError):
    """The game that uses this save folder is running."""


def save_path(folder: Path, number: int) -> Path:
    return folder / reader.save_file_name(number)


def settings_path(folder: Path) -> Path:
    return save_path(folder, 0)


# ---------------------------------------------------------------------------
# The name rule
# ---------------------------------------------------------------------------


def name_problem(name: str) -> str | None:
    """Why ``name`` cannot be a family's name, or None if it can."""
    if not name:
        return "Type a name."
    bad = sorted({ch for ch in name if ch not in PRINTABLE})
    if bad:
        shown = " ".join(repr(ch) for ch in bad)
        return f"Virtual Families 2 cannot use these characters in a name: {shown}."
    if len(name) > MAX_LENGTH:
        return f"{len(name)} characters is too long: the game keeps at most {MAX_LENGTH}."
    if not name.strip(" "):
        return "A name cannot be only spaces."
    if name == EMPTY_SLOT_TEXT:
        return f"\"{EMPTY_SLOT_TEXT}\" is what the game shows for an empty slot, so it cannot be a name."
    return None


# ---------------------------------------------------------------------------
# Reading the saves
# ---------------------------------------------------------------------------


def _field(data: bytes, offset: int, width: int) -> bytes | None:
    """The NUL-terminated bytes in the field, or None when the field has no NUL."""
    raw = data[offset:offset + width]
    end = raw.find(b"\0")
    return None if end < 0 else bytes(raw[:end])


def _name_offset(data: bytes) -> int | None:
    """File offset of gs+0x25ABC when ``data`` is a family save the game loads, else None."""
    try:
        header = reader.parse_header(data)
    except reader.SaveFormatError:
        return None
    if header.legacy or header.payload_size != reader.GAME_DATA_SIZE:
        return None
    return reader.gs_to_file(reader.GS_NICKNAME)


def _menu_offset(data: bytes, slot: int) -> int | None:
    try:
        header = reader.parse_header(data)
    except reader.SaveFormatError:
        return None
    if header.legacy or header.payload_size != reader.SETTINGS_DATA_SIZE:
        return None
    return MENU_FIRST + MENU_FIELD * (slot - 1)


def save_name(data: bytes) -> bytes | None:
    """The player name in a slot save's bytes, or None if they are not a family save."""
    offset = _name_offset(data)
    return None if offset is None else _field(data, offset, NAME_FIELD)


def menu_name(data: bytes, slot: int) -> bytes | None:
    """Slot ``slot``'s entry in the settings file's bytes, or None."""
    offset = _menu_offset(data, slot)
    return None if offset is None else _field(data, offset, MENU_FIELD)


def shown(raw: bytes | None) -> str:
    return "(no name)" if not raw else raw.decode("cp1252", "replace")


@dataclass
class SlotInfo:
    slot: int
    name: bytes | None          # the name in the slot's save, or None
    problem: str | None = None  # why it cannot be renamed, if it cannot

    @property
    def label(self) -> str:
        if self.name is None:
            if self.problem == "This slot has no family.":
                return f"Family slot {self.slot}: (empty)"
            return f"Family slot {self.slot}: (a save the game cannot load)"
        return f"Family slot {self.slot}: {shown(self.name)}"


def read_slots(folder: Path) -> list[SlotInfo]:
    """Each slot's name, from its own save."""
    try:
        settings = settings_path(folder).read_bytes()
    except OSError:
        settings = b""
    settings_ok = bool(settings) and menu_name(settings, 1) is not None
    slots: list[SlotInfo] = []
    for slot in SLOTS:
        path = save_path(folder, slot)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            slots.append(SlotInfo(slot, None, "This slot has no family."))
            continue
        except OSError as exc:
            slots.append(SlotInfo(slot, None, f"The save could not be read: {exc}"))
            continue
        name = save_name(data)
        info = SlotInfo(slot, name)
        if name is None:
            info.problem = f"{path.name} is not a Virtual Families 2 save the game can load."
        elif not settings_ok:
            info.problem = f"The settings file {settings_path(folder).name} could not be read."
        slots.append(info)
    return slots


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _with_name(data: bytes, offset: int, width: int, name: str) -> bytes:
    """``data`` with the field at ``offset`` holding ``name``, NUL-padded."""
    encoded = name.encode("ascii")
    if len(encoded) + 1 > width:
        raise RenameError(f"{name!r} does not fit a {width}-byte name field.")
    return data[:offset] + encoded + b"\0" * (width - len(encoded)) + data[offset + width:]


def _write_atomically(path: Path, data: bytes) -> None:
    """Replace ``path`` with ``data`` through a temporary file, then verify."""
    temporary = path.with_name(f"{path.name}.rename-{uuid.uuid4().hex[:12]}.tmp")   # a leftover never blocks a rename
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
        raise RenameError(f"{path.name} did not read back as written.")


@dataclass
class FileChange:
    path: Path
    original: bytes
    updated: bytes


@dataclass
class RenameResult:
    folder: Path
    slot: int
    old_name: str
    new_name: str
    backup: save_backup.BackupResult
    changed: list[Path] = field(default_factory=list)


def _refuse_if_running(folder: Path, processes: save_backup.ProcessController) -> None:
    try:
        running = save_backup.running_games(folder, processes)
    except (OSError, save_backup.BackupError) as exc:
        raise RenameError(f"Could not check whether the game is running, so nothing was changed ({exc}).") from exc
    if running:
        names = ", ".join(sorted({name for _pid, name in running}))
        raise GameRunning(
            f"{names} is running. Close the game first (quit it normally from its menu): it saves by itself "
            "every 2 minutes and when it quits, which would put the old name back. Nothing was changed."
        )


def plan_changes(folder: Path, slot: int, new_name: str) -> tuple[bytes, list[FileChange]]:
    """The old name, and the new bytes of every file that holds it."""
    save = save_path(folder, slot)
    try:
        data = save.read_bytes()
    except FileNotFoundError as exc:
        raise RenameError(f"Family slot {slot} has no family ({save.name} is missing).") from exc
    except OSError as exc:
        raise RenameError(f"Could not read {save.name}: {exc}") from exc
    old = save_name(data)
    offset = _name_offset(data)
    if old is None or offset is None:
        raise RenameError(f"{save.name} is not a Virtual Families 2 save the game can load.")
    if old == new_name.encode("ascii"):
        raise RenameError(f"Family slot {slot} is already called {new_name}.")
    settings = settings_path(folder)
    try:
        menu = settings.read_bytes()
    except OSError as exc:
        raise RenameError(f"Could not read the settings file {settings.name}: {exc}") from exc
    menu_at = _menu_offset(menu, slot)
    if menu_at is None or menu_name(menu, slot) is None:
        raise RenameError(f"The settings file {settings.name} is not one the game can load.")
    changes = [FileChange(save, data, _with_name(data, offset, NAME_FIELD, new_name))]
    previous = save_path(folder, slot + reader.PREVIOUS_SAVE_OFFSET)
    try:
        older = previous.read_bytes()
    except FileNotFoundError:
        older = None
    except OSError as exc:
        raise RenameError(f"Could not read {previous.name}: {exc}") from exc
    if older is not None:
        older_at = _name_offset(older)
        if older_at is not None and save_name(older) == old:
            changes.append(FileChange(previous, older, _with_name(older, older_at, NAME_FIELD, new_name)))
    changes.append(FileChange(settings, menu, _with_name(menu, menu_at, MENU_FIELD, new_name)))
    return old, changes


def _restore(changes: list[FileChange]) -> list[str]:
    """Put every changed file back; the reasons any could not be."""
    problems: list[str] = []
    for change in reversed(changes):
        try:
            if change.path.read_bytes() != change.original:
                _write_atomically(change.path, change.original)
        except (OSError, RenameError) as exc:
            problems.append(f"{change.path.name}: {exc}")
    return problems


def rename_family(
    folder: Path,
    slot: int,
    new_name: str,
    processes: save_backup.ProcessController | None = None,
    now: datetime | None = None,
) -> RenameResult:
    """Rename the family in ``slot`` of ``folder`` to ``new_name``.

    Refused (RenameError, nothing changed) when the name breaks the rule, the game is running, or the saves
    cannot be read. Otherwise the folder is backed up first, every file is replaced atomically and read back,
    and any failure restores every file already changed.
    """
    if slot not in SLOTS:
        raise RenameError(f"There is no family slot {slot}.")
    problem = name_problem(new_name)
    if problem is not None:
        raise RenameError(problem)
    controller = processes if processes is not None else save_backup.WindowsProcesses()
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    old, changes = plan_changes(folder, slot, new_name)
    try:
        backup = save_backup.copy_save_folder(folder, when, suffix=BACKUP_LABEL)
    except save_backup.BackupError as exc:
        raise RenameError(f"The backup before renaming failed, so nothing was changed. {exc}") from exc
    _refuse_if_running(folder, controller)        # the backup took a moment
    done: list[FileChange] = []
    target = new_name.encode("ascii")
    try:
        for change in changes:
            if change.path.read_bytes() != change.original:
                raise RenameError(f"{change.path.name} changed while it was being renamed.")
            done.append(change)
            _write_atomically(change.path, change.updated)
        settings = settings_path(folder)
        for change in changes:
            data = change.path.read_bytes()
            holds = (menu_name(data, slot) if change.path == settings else save_name(data)) == target
            if not holds:
                raise RenameError(f"{change.path.name} does not hold the new name.")
    except (OSError, RenameError) as exc:
        problems = _restore(done)
        if problems:
            raise RenameError(
                f"The rename failed ({exc}) and these files could not be put back: {'; '.join(problems)}. "
                f"Your backup is in {backup.backup_folder}."
            ) from exc
        raise RenameError(
            f"The rename failed ({exc}); every file was put back as it was. A backup is in {backup.backup_folder}."
        ) from exc
    return RenameResult(folder, slot, shown(old), new_name, backup, [change.path for change in changes])
