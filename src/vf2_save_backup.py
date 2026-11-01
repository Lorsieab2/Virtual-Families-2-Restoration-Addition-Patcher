"""Back Up Saves / Restore Saves for Virtual Families 2.

Where the saves are
    Virtual Families 2 saves into Documents\\LDW\\<its exe's name cut at the FIRST dot>.
    The stock game is "Virtual Families 2"; a patched game is named after the
    modded exe the patcher built ("Virtual Families 2 - Modded B202", ...). An exe
    named "Foo.B202.exe" saves into "Foo", so the exe's name can never be read back
    from the folder: a running game is recognised by cutting each running exe's name
    the same way and comparing it with the folder, never the reverse. Inside
    that folder are the game's per-family save files ("Virtual Families 2<N>.ldw",
    with a "- Copy" beside each), its ldwLog.txt, and the patcher's own
    "Virtual Families 2 Patcher Data" folder (the Children sidecar and any other
    file a patch keeps beside a save). Documents is resolved through the Windows
    Known Folder API, because it may be redirected (to OneDrive, say).

What is copied
    Everything in the save folder except its "Backups" folder, into a new
    "Backups\\Backup YYYY-MM-DD HH-MM-SS" folder inside it. An existing backup is
    never written into or replaced, and every copied file is read back and
    checked against the original's size and SHA-256.

Pausing
    If the game that uses the folder is running, every process of it is
    suspended for the copy and always resumed afterwards. If one cannot be
    suspended the backup is refused. The game is never closed.

Game speed Paused in the backup
    Once every file is copied and verified, the backup's copy of each family
    save "Virtual Families 2<1-5>.ldw" at Normal is set to Paused, exactly as
    the game's own Pause sets it (vf2_game_speed), so a restored backup never
    catches up on the real time since it was made. The live saves are never
    changed. A copy already Paused, at another speed or unreadable is kept
    byte for byte; the previous saves <N+20> are not touched. The pause
    changes the copy's bytes, and each Children and Outfits file names the
    hash and size of the save it was written with (b200kids / b200outfits
    take it as their save's only when the loaded save still has them), so
    each of the slot's Children and Outfits files in the backup (N, N+20)
    that described the save before the pause is re-keyed to the paused copy,
    exactly as Copy Player Slot re-keys a copy's; one that described another
    save, or is damaged, is kept byte for byte.

Restore
    A backup is restored (the whole save folder, or one family's save slot) only
    while the game is closed, only after the exact changes were shown and
    confirmed by the player, and only after the current saves were backed up as
    "Backup <date> (before restore)". A backup is never modified by a restore.

Nothing here touches Tk, so the GUI runs it on a worker thread and the tests
drive it with a temp Documents folder and a fake process controller.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import re
import shutil
import stat
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Protocol

GAME_TITLE = "Virtual Families 2"
BACKUPS_FOLDER = "Backups"
BACKUP_PREFIX = "Backup "
DATA_FOLDER = "Virtual Families 2 Patcher Data"
ENGINE_LOG = "ldwLog.txt"
HASH_CHUNK = 1024 * 1024
BEFORE_RESTORE = "(before restore)"
BEFORE_RENAME = "(before rename)"    # Rename Family makes this backup before it writes the new name
BEFORE_SPEED_CHANGE = "(before speed change)"   # Game Speed makes this backup before it writes the new speed
BEFORE_COPY = "(before copy)"        # Copy Player Slot makes this backup before it copies a family
INCOMPLETE = " INCOMPLETE"
IN_PROGRESS = " (in progress)"
DELETING = " (deleting)"
DELETE_ATTEMPTS = 5
DELETE_RETRY_SECONDS = 0.5

_BACKUP_NAME = re.compile(
    r"^Backup (\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})(?: \((\d+)\))?"
    r"(?: (\(before restore\)|\(before rename\)|\(before speed change\)|\(before copy\)))?$"
)
# The game's save files are exactly "Virtual Families 2" + N + ".ldw" (one space, N without leading zeros):
# 0 is the shared settings, 1-5 are families, N + 20 is the previous save of slot N (made for 1-5 only).
# The patcher's sidecar is that file's name + ".dat" under "<Patcher Data>\\Children".  Any other name
# (a player's own "Virtual Families221.ldw", "... - Copy.ldw", ...) is unknown and only a whole-folder
# restore touches it.
_SAVE_NAME = re.compile(r"^Virtual Families 2(0|[1-9]\d*)\.ldw$", re.I)
_SIDECAR_NAME = re.compile(r"^Virtual Families 2(0|[1-9]\d*)\.ldw\.dat$", re.I)
SIDECAR_FOLDERS = ("children", "outfits")      # b200kids / b200outfits SidecarPath, under the Patcher Data folder
PATCHER_FOLDER = "Virtual Families 2 Patcher"   # its "Save <N>" folders: each slot's logs and Family Tree files
SHARED_FILES = ("wc.dat",)      # beside ldwLog.txt, shared by every family


class BackupError(Exception):
    """A backup or restore that could not be done, with a reason a player can read."""


class PauseRefused(BackupError):
    """The game is running and could not be paused, so nothing was copied."""


class RestoreRefused(BackupError):
    """A restore that was not started, with the reason; nothing was changed."""


# ---------------------------------------------------------------------------
# Documents and the save folders
# ---------------------------------------------------------------------------


def documents_folder() -> Path | None:
    """The Documents folder as Windows resolves it (follows redirection), or None."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        folder_id = GUID(
            0xFDD39AD0, 0x238F, 0x46AF,
            (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
        )
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole32.CoTaskMemFree.restype = None
        result = ctypes.c_wchar_p()
        status = shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(result))
        try:
            if status == 0 and result.value:
                return Path(result.value)
        finally:
            ole32.CoTaskMemFree(ctypes.cast(result, ctypes.c_void_p))
    except (OSError, AttributeError):
        pass
    return None


def is_patcher_save_folder(name: str) -> bool:
    """Whether ``name`` is the save folder of a game the patcher built ("Virtual Families 2 - Modded...")."""
    return name.casefold().startswith(f"{GAME_TITLE} - Modded".casefold())


def find_save_folders(documents: Path | None) -> list[Path]:
    """Every Documents\\LDW\\Virtual Families 2... folder, the patcher's own ("- Modded") first.

    The game names its save folder after its exe, so the stock "Virtual Families 2", every
    "Virtual Families 2 - Modded ..." build and any copy the player made are listed.  "Virtual Families"
    (the first game) is never listed.
    """
    if documents is None:
        return []
    ldw = documents / "LDW"
    if not ldw.is_dir():
        return []
    title = GAME_TITLE.casefold()
    found = [
        entry for entry in ldw.iterdir()
        if entry.is_dir() and (entry.name.casefold() == title or entry.name.casefold().startswith(title + " "))
    ]

    def order(path: Path) -> tuple[int, str]:
        return (0 if is_patcher_save_folder(path.name) else 1, path.name.casefold())

    return sorted(found, key=order)


def exe_save_folder_name(exe_name: str) -> str:
    """The Documents\\LDW folder an exe saves into: its name cut at the first dot."""
    return exe_name.split(".", 1)[0]


def running_games(save_folder: Path, processes: "ProcessController") -> list[tuple[int, str]]:
    """(pid, exe name) of every running process that saves into ``save_folder`` (no exe name is guessed)."""
    return list(processes.find_game(save_folder.name))


# ---------------------------------------------------------------------------
# What is copied
# ---------------------------------------------------------------------------

_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003


def _is_link(path: Path) -> bool:
    """A symbolic link or junction, which the copy never follows."""
    if path.is_symlink():
        return True
    try:
        tag = getattr(path.lstat(), "st_reparse_tag", 0)
    except OSError:
        return False
    return tag == _IO_REPARSE_TAG_MOUNT_POINT


def files_to_back_up(save_folder: Path) -> list[Path]:
    """Every file under ``save_folder`` except those in its Backups folder, relative and sorted."""
    files: list[Path] = []

    def walk(folder: Path, relative: Path) -> None:
        for entry in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
            if relative == Path() and entry.name.casefold() == BACKUPS_FOLDER.casefold():
                continue
            if entry.is_dir():
                if not _is_link(entry):
                    walk(entry, relative / entry.name)
            elif entry.is_file() and not _is_link(entry):
                files.append(relative / entry.name)

    walk(save_folder, Path())
    return files


# ---------------------------------------------------------------------------
# The copy
# ---------------------------------------------------------------------------


@dataclass
class CopiedFile:
    relative: Path
    size: int
    sha256: str
    times: tuple[int, int] | None = None


@dataclass
class BackupResult:
    save_folder: Path
    backup_folder: Path
    files: list[CopiedFile] = field(default_factory=list)
    paused: int = 0
    resume_problems: list[str] = field(default_factory=list)
    paused_slots: list[str] = field(default_factory=list)   # slot saves whose copy was set to Paused
    # ... and each one's bytes as they were (the original's), so a failed restore puts them back
    # exactly: pausing changes the game clock too, which no speed write could undo. The Children and
    # Outfits files re-keyed to a paused copy are in it too, as they were.
    unpaused_bytes: dict[Path, bytes] = field(default_factory=dict)
    rematched_sidecars: list[Path] = field(default_factory=list)   # re-keyed to a paused copy
    # Slot saves whose copy was not set to Paused (another speed, or not a save Game Speed can read): kept as they were.
    not_paused: list[tuple[str, str]] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_bytes(self) -> int:
        return sum(item.size for item in self.files)


def backup_folder_name(now: datetime) -> str:
    return f"{BACKUP_PREFIX}{now.strftime('%Y-%m-%d %H-%M-%S')}"


def _backup_names(now: datetime, suffix: str) -> Iterator[str]:
    base = backup_folder_name(now)
    for attempt in range(1, 1000):
        name = base if attempt == 1 else f"{base} ({attempt})"
        yield f"{name} {suffix}" if suffix else name


def _new_backup_folder(save_folder: Path, now: datetime, suffix: str = "") -> Path:
    """Create a new, empty "... (in progress)" folder; it is renamed only once every file is verified."""
    backups = save_folder / BACKUPS_FOLDER
    backups.mkdir(exist_ok=True)
    for name in _backup_names(now, suffix):
        if (backups / name).exists():
            continue
        candidate = backups / (name + IN_PROGRESS)
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise BackupError(f"Too many backups named {backup_folder_name(now)} in {backups}.")


def _finish_backup(staging: Path, now: datetime, suffix: str) -> Path:
    for name in _backup_names(now, suffix):
        final = staging.with_name(name)
        if final.exists():
            continue
        for attempt in range(DELETE_ATTEMPTS):
            try:
                staging.rename(final)
                return final
            except FileExistsError:
                break
            except PermissionError:
                if attempt == DELETE_ATTEMPTS - 1:
                    raise
                time.sleep(DELETE_RETRY_SECONDS)
    raise BackupError(f"No free name for the backup in {staging.parent}.")


def _set_aside(staging: Path, label: str) -> Path:
    base = staging.name.removesuffix(IN_PROGRESS) + label
    for attempt in range(1, 100):
        target = staging.with_name(base if attempt == 1 else f"{base} ({attempt})")
        if target.exists():
            continue
        try:
            staging.rename(target)
        except OSError:
            continue
        return target
    return staging


def _hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(HASH_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _keep_times(path: Path, times: tuple[int, int]) -> None:
    """Give a copy the access and modification time of its original (a failure fails the copy)."""
    try:
        os.utime(path, ns=times)
        kept = os.stat(path).st_mtime_ns
    except OSError as exc:
        raise BackupError(f"The time of {path.name} could not be kept ({exc}).") from exc
    if abs(kept - times[1]) > 2_000_000_000:
        raise BackupError(f"The time of {path.name} could not be kept (it reads back as another time).")


def _copy_one(source: Path, destination: Path) -> CopiedFile:
    """Copy one file, never over an existing one, and verify it by size and hash."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    original = source.stat()
    with source.open("rb") as reader, destination.open("xb") as writer:
        while True:
            chunk = reader.read(HASH_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
            writer.write(chunk)
    expected = digest.hexdigest()
    copied_size, copied_hash = _hash_file(destination)
    if copied_size != size or copied_hash != expected:
        raise BackupError(f"The copy of {source.name} does not match the original ({copied_size} of {size} bytes).")
    source_size, source_hash = _hash_file(source)
    if source_size != size or source_hash != expected:
        raise BackupError(f"{source.name} changed while it was being copied.")
    times = (original.st_atime_ns, original.st_mtime_ns)
    _keep_times(destination, times)
    return CopiedFile(Path(), size, expected, times)


def copy_save_folder(save_folder: Path, now: datetime | None = None, suffix: str = "") -> BackupResult:
    """Copy the save folder into a new Backups\\Backup <date> folder inside it.

    On any failure the partial backup is renamed "... INCOMPLETE" (never deleted and never left looking
    like a good backup) and BackupError is raised.
    """
    if not save_folder.is_dir():
        raise BackupError(f"The save folder does not exist: {save_folder}")
    relatives = files_to_back_up(save_folder)
    if not relatives:
        raise BackupError(f"There is nothing to back up in {save_folder}.")
    when = now or datetime.now()
    staging = _new_backup_folder(save_folder, when, suffix)
    result = BackupResult(save_folder, staging)
    try:
        for relative in relatives:
            copied = _copy_one(save_folder / relative, staging / relative)
            copied.relative = relative
            result.files.append(copied)
        # Every file is copied and verified; now the copy of each family save is set to Paused (the live
        # save folder is never written).
        paused_saves: list[tuple[Path, bytes, bytes]] = []
        for copied in result.files:
            if not is_slot_save(copied.relative):
                continue
            original = (staging / copied.relative).read_bytes()
            try:
                paused = pause_save_bytes(original)
            except NotPaused as exc:
                result.not_paused.append((copied.relative.name, str(exc)))
                continue
            if paused is None:
                continue                 # already paused
            _write_save(staging / copied.relative, paused, original)
            copied.size, copied.sha256 = _hash_file(staging / copied.relative)
            result.paused_slots.append(copied.relative.name)
            result.unpaused_bytes[copied.relative] = original
            if copied.times is not None:
                _keep_times(staging / copied.relative, copied.times)   # the pause rewrote it
            paused_saves.append((copied.relative, original, paused))
        _rekey_sidecars(staging, result, paused_saves)
        result.backup_folder = _finish_backup(staging, when, suffix)
    except (OSError, BackupError) as exc:
        where = _set_aside(staging, INCOMPLETE)
        reason = exc if isinstance(exc, BackupError) else f"{type(exc).__name__}: {exc}"
        raise BackupError(
            f"The backup could not be completed ({reason}). The partial copy was kept as {where} "
            "and is NOT a usable backup."
        ) from exc
    return result


# ---------------------------------------------------------------------------
# The backup's family saves are set to Paused
# ---------------------------------------------------------------------------
#
# Ported from the Virtual Villagers Fun Patcher (src/vv_save_backup.py, copy_save_folder and
# pause_save_copy): a paused family does not age or catch up while the game is closed, so the backup's
# copy of each slot save is set to Paused. Restoring an old backup then never fast-forwards the family
# through the real time since it was saved. Only the copy changes, never the live save. The pause is
# Game Speed's own (vf2_game_speed.changed_bytes), which writes exactly what the game's Pause writes.
# Only a family at Normal is paused; a save already Paused, at any other speed, or not a save Game Speed
# can read is left byte for byte as it is. The previous saves "Virtual Families 2<N+20>.ldw" are left
# as they are too: VV pauses only a slot's own save, never the game's older copies, and the game never
# loads an N+20 file (vf2_game_speed).


def _rekey_sidecars(staging: Path, result: BackupResult, paused_saves: list[tuple[Path, bytes, bytes]]) -> None:
    """Each Children and Outfits file in the backup that described a save before its pause, re-keyed to the
    paused copy (vf2_copy_slot.sidecar_rekeys), read back and checked."""
    import vf2_copy_slot as copy_slot       # imported here: vf2_copy_slot imports this module

    by_path = {copied.relative: copied for copied in result.files}
    for relative, original, paused in paused_saves:
        match = _SAVE_NAME.match(relative.name)
        if match is None:
            continue
        for path, kind, old, new in copy_slot.sidecar_rekeys(staging, int(match.group(1)), [(original, paused)]):
            sidecar = path.relative_to(staging)
            _write_save(path, new, old)
            if not copy_slot.sidecar_describes(kind, path.read_bytes(), paused):
                raise BackupError(f"The backup's {path.name} did not match the paused copy of {relative.name}.")
            result.unpaused_bytes[sidecar] = old
            result.rematched_sidecars.append(sidecar)
            copied = by_path.get(sidecar)
            if copied is not None:
                copied.size, copied.sha256 = _hash_file(path)
                if copied.times is not None:
                    _keep_times(path, copied.times)


class NotPaused(BackupError):
    """A slot save whose backup copy is left as it is, with the reason a player can read."""


def is_slot_save(relative: Path) -> bool:
    """A family's own save, "Virtual Families 2<1-5>.ldw", at the top of the save folder (the previous
    saves <N+20> and the settings file <0> are not)."""
    match = _SAVE_NAME.match(relative.name)
    return len(relative.parts) == 1 and match is not None and 1 <= int(match.group(1)) <= 5


def pause_save_bytes(data: bytes) -> bytes | None:
    """The save set to Paused exactly as the game's own Pause leaves it, or None when it already is.
    NotPaused when it is not a save Game Speed can read, or is at a speed other than Normal."""
    import vf2_game_speed as game_speed     # imported here: vf2_game_speed imports this module

    state = game_speed.read_state(data)
    if state is None:
        raise NotPaused("not a Virtual Families 2 save whose speed can be read")
    if state.kind == "paused":
        return None
    if state.kind != "normal":
        raise NotPaused(f"its speed is {state.label}; only a family at Normal is paused")
    try:
        paused = game_speed.changed_bytes(data, game_speed.PAUSED)
    except game_speed.SpeedError as exc:
        raise NotPaused(str(exc)) from exc
    after = game_speed.read_state(paused)
    if after is None or after.kind != "paused" or not game_speed.only_speed_fields_differ(data, paused):
        raise BackupError("The paused copy of a family save did not read back as Paused.")
    return paused


def _swap_in(path: Path, data: bytes) -> None:
    """``data`` swapped in through a temporary file of its own, a new name created exclusively."""
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.vf2-pause-tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_save(path: Path, data: bytes, original: bytes) -> None:
    """Swap ``data`` in and read it back. If it does not read back as written, the original is put back
    the same way before the error is raised: a save is never left changed and reported unchanged."""
    _swap_in(path, data)
    try:
        ok = path.read_bytes() == data
    except OSError:
        ok = False
    if ok:
        return
    try:
        _swap_in(path, original)
        back = path.read_bytes() == original
    except OSError:
        back = False
    if not back:
        raise BackupError(f"{path.name} did not read back as written, and could not be put back as it "
                          "was: restore it from a backup.")
    raise BackupError(f"{path.name} did not read back as written; it was put back as it was.")


# ---------------------------------------------------------------------------
# Pausing the game
# ---------------------------------------------------------------------------


class ProcessController(Protocol):
    def find_game(self, save_folder_name: str) -> list[tuple[int, str]]: ...
    def suspend(self, pid: int, exe_name: str) -> object: ...
    def resume(self, handle: object) -> None: ...


class WindowsProcesses:
    """Find, suspend and resume game processes with the Windows API."""

    PROCESS_SUSPEND_RESUME = 0x0800
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TH32CS_SNAPPROCESS = 0x00000002
    ERROR_NO_MORE_FILES = 18

    def __init__(self) -> None:
        from ctypes import wintypes

        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._ntdll = ctypes.WinDLL("ntdll")
        k = self._kernel32
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ]
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        for name in ("NtSuspendProcess", "NtResumeProcess"):
            function = getattr(self._ntdll, name)
            function.argtypes = [wintypes.HANDLE]
            function.restype = ctypes.c_long

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        self._entry_type = PROCESSENTRY32W
        k.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k.Process32FirstW.restype = wintypes.BOOL
        k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k.Process32NextW.restype = wintypes.BOOL

    def find_game(self, save_folder_name: str) -> list[tuple[int, str]]:
        """(pid, exe name) of every running exe whose name cut at its first dot is ``save_folder_name``."""
        k = self._kernel32
        snapshot = k.CreateToolhelp32Snapshot(self.TH32CS_SNAPPROCESS, 0)
        if not snapshot or snapshot == self._wintypes.HANDLE(-1).value:
            raise BackupError(
                "Could not list the running programs to check whether the game is running "
                f"(error {ctypes.get_last_error()})."
            )
        pids: list[tuple[int, str]] = []
        try:
            entry = self._entry_type()
            entry.dwSize = ctypes.sizeof(entry)
            more = k.Process32FirstW(snapshot, ctypes.byref(entry))
            while more:
                name = entry.szExeFile
                if name.casefold().endswith(".exe") and exe_save_folder_name(name).casefold() == save_folder_name.casefold():
                    pids.append((int(entry.th32ProcessID), name))
                more = k.Process32NextW(snapshot, ctypes.byref(entry))
            error = ctypes.get_last_error()
            if error != self.ERROR_NO_MORE_FILES:
                raise BackupError(
                    "Could not read the whole list of running programs to check whether the game "
                    f"is running (error {error})."
                )
        finally:
            k.CloseHandle(snapshot)
        return pids

    def suspend(self, pid: int, exe_name: str) -> object:
        k = self._kernel32
        handle = k.OpenProcess(self.PROCESS_SUSPEND_RESUME | self.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            reason = "access was denied" if error == 5 else f"Windows error {error}"
            raise PauseRefused(f"{exe_name} (process {pid}) is running but could not be paused: {reason}.")
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = self._wintypes.DWORD(len(buffer))
            if not k.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                raise PauseRefused(
                    f"{exe_name} (process {pid}) could not be checked before pausing "
                    f"(Windows error {ctypes.get_last_error()})."
                )
            if Path(buffer.value).name.casefold() != exe_name.casefold():
                raise PauseRefused(f"Process {pid} is no longer {exe_name}; try the backup again.")
            status = self._ntdll.NtSuspendProcess(handle)
            if status != 0:
                raise PauseRefused(
                    f"{exe_name} (process {pid}) is running but could not be paused "
                    f"(status 0x{status & 0xFFFFFFFF:08X})."
                )
        except BaseException:
            k.CloseHandle(handle)
            raise
        return handle

    def resume(self, handle: object) -> None:
        try:
            status = self._ntdll.NtResumeProcess(handle)
            if status != 0:
                raise BackupError(
                    f"The game could not be resumed (status 0x{status & 0xFFFFFFFF:08X}). "
                    "Close it from Task Manager if it stays frozen."
                )
        finally:
            self._kernel32.CloseHandle(handle)


@dataclass
class Pause:
    count: int = 0
    problems: list[str] = field(default_factory=list)


@contextmanager
def paused_game(save_folder: Path, processes: ProcessController) -> Iterator[Pause]:
    """Suspend every running process that saves into ``save_folder``; always resume them."""
    pause = Pause()
    paused: list[object] = []
    failure: BaseException | None = None
    try:
        for pid, exe_name in running_games(save_folder, processes):
            paused.append(processes.suspend(pid, exe_name))
        pause.count = len(paused)
        yield pause
    except BaseException as exc:
        failure = exc
        raise
    finally:
        errors: list[str] = []
        for handle in reversed(paused):
            try:
                processes.resume(handle)
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            if failure is not None:
                failure.add_note("The game could not be resumed: " + "; ".join(errors))
            else:
                pause.problems.extend(errors)


def back_up_save_folder(
    save_folder: Path, processes: ProcessController | None = None, now: datetime | None = None
) -> BackupResult:
    """Pause the game that uses ``save_folder`` (if running), copy, resume."""
    controller = processes if processes is not None else WindowsProcesses()
    with paused_game(save_folder, controller) as pause:
        result = copy_save_folder(save_folder, now)
    result.paused = pause.count
    result.resume_problems = list(pause.problems)
    return result


def running_game_count(save_folder: Path, processes: ProcessController | None = None) -> int:
    """How many processes of the game that saves here are running (0 if none or unknown)."""
    try:
        controller = processes if processes is not None else WindowsProcesses()
        return len(running_games(save_folder, controller))
    except (OSError, BackupError, AttributeError):
        return 0


def describe_size(size: int) -> str:
    if size < 1024:
        return f"{size} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# Listing backups
# ---------------------------------------------------------------------------


@dataclass
class BackupInfo:
    path: Path
    when: datetime
    before_restore: bool
    file_count: int
    size: int
    slots: list[int]
    before_rename: bool = False
    before_speed_change: bool = False
    before_copy: bool = False

    @property
    def label(self) -> str:
        text = self.when.strftime("%Y-%m-%d %H:%M:%S")
        if self.before_restore:
            text += " " + BEFORE_RESTORE
        elif self.before_rename:
            text += " " + BEFORE_RENAME
        elif self.before_speed_change:
            text += " " + BEFORE_SPEED_CHANGE
        elif self.before_copy:
            text += " " + BEFORE_COPY
        return text


def _parse_backup_name(name: str) -> tuple[datetime, int, str] | None:
    match = _BACKUP_NAME.match(name)
    if not match:
        return None
    try:
        when = datetime.strptime(match.group(1), "%Y-%m-%d %H-%M-%S")
    except ValueError:
        return None
    return when, int(match.group(2) or 1), match.group(3) or ""


def file_slot(relative: Path) -> int | str | None:
    """The family slot (1-5) a file belongs to; "engine log", "settings" or "shared" for shared files; else None.

    A slot file is exactly "Virtual Families 2<N>.ldw" at the top of the save folder (N + 20 is the
    previous save of slot N, for slots 1-5 only); the patcher's sidecars are that name + ".dat" in
    "<Patcher Data>\\Children" and "<Patcher Data>\\Outfits" (N + 20's are slot N's too); and everything in
    "Virtual Families 2 Patcher\\Save <N>" (the Family History log, the Family Tree files) is slot N's.  Slot 0
    ("settings"), ldwLog.txt ("engine log") and wc.dat ("shared") belong to no family, and every other name is
    unknown (None): only a whole-folder restore touches those.
    """
    parts = relative.parts
    if len(parts) == 1 and relative.name.casefold() == ENGINE_LOG.casefold():
        return "engine log"
    if len(parts) == 1 and relative.name.casefold() in SHARED_FILES:
        return "shared"
    match = None
    if len(parts) == 1:
        match = _SAVE_NAME.match(relative.name)
    elif len(parts) == 3 and parts[0].casefold() == DATA_FOLDER.casefold() and parts[1].casefold() in SIDECAR_FOLDERS:
        match = _SIDECAR_NAME.match(relative.name)
    elif len(parts) >= 3 and parts[0].casefold() == PATCHER_FOLDER.casefold():
        folder = re.fullmatch(r"Save ([1-5])", parts[1], re.I)
        return int(folder.group(1)) if folder else None
    if match:
        number = int(match.group(1))
        if 21 <= number <= 25:      # the game keeps the previous save of slot N (and its sidecars) at N + 20
            number -= 20
        if 1 <= number <= 5:
            return number
        if number == 0:
            return "settings"       # slot 0: the game's shared settings file, no family's
    return None


def slots_in(files: list[Path]) -> list[int]:
    return sorted({slot for slot in (file_slot(f) for f in files) if isinstance(slot, int)})


def list_backups(save_folder: Path) -> list[BackupInfo]:
    """The usable backups in ``save_folder``\\Backups, newest first (an INCOMPLETE copy is never offered)."""
    backups = save_folder / BACKUPS_FOLDER
    if not backups.is_dir():
        return []
    found: list[tuple[datetime, int, BackupInfo]] = []
    for entry in backups.iterdir():
        parsed = _parse_backup_name(entry.name)
        if parsed is None or not entry.is_dir() or _is_link(entry):
            continue
        when, sequence, label = parsed
        files = files_to_back_up(entry)
        size = sum((entry / relative).stat().st_size for relative in files)
        found.append((when, sequence, BackupInfo(entry, when, label == BEFORE_RESTORE, len(files), size, slots_in(files),
                                                     label == BEFORE_RENAME, label == BEFORE_SPEED_CHANGE,
                                                     label == BEFORE_COPY)))
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [info for _when, _sequence, info in found]


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


@dataclass
class RestorePlan:
    save_folder: Path
    backup: Path
    slot: int | None
    replace: list[Path] = field(default_factory=list)
    add: list[Path] = field(default_factory=list)
    remove: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)

    @property
    def changes(self) -> int:
        return len(self.replace) + len(self.add) + len(self.remove)


def _same_file(a: Path, b: Path) -> bool:
    try:
        return _hash_file(a) == _hash_file(b)
    except OSError:
        return False


def _require_backup_of(save_folder: Path, backup: Path) -> None:
    backups = (save_folder / BACKUPS_FOLDER).resolve()
    if (
        backup.resolve().parent != backups
        or _parse_backup_name(backup.name) is None
        or not backup.is_dir()
        or _is_link(backup)
    ):
        raise RestoreRefused(f"{backup} is not one of this save folder's backups.")


def plan_restore(save_folder: Path, backup: Path, slot: int | None = None) -> RestorePlan:
    """Work out exactly which files a restore replaces, adds and removes.

    Whole folder: the save folder becomes the backup; every file in it is restored and every other file
    (outside Backups, and except the engine's ldwLog.txt, which is no part of a save) is removed.
    One slot: only that family's files (its save and previous save, their Children and Outfits files, and its
    "Virtual Families 2 Patcher\\Save <N>" folder) are touched; files that belong to another slot, or to none,
    are left exactly as they are.
    """
    _require_backup_of(save_folder, backup)
    in_backup = set(files_to_back_up(backup))
    in_folder = set(files_to_back_up(save_folder))
    plan = RestorePlan(save_folder, backup, slot)
    for relative in sorted(in_backup | in_folder, key=lambda p: str(p).casefold()):
        owner = file_slot(relative)
        if owner == "engine log":
            continue
        if slot is not None and owner != slot:
            continue
        here, there = relative in in_folder, relative in in_backup
        if here and there:
            if _same_file(save_folder / relative, backup / relative):
                plan.unchanged.append(relative)
            else:
                plan.replace.append(relative)
        elif there:
            plan.add.append(relative)
        else:
            plan.remove.append(relative)
    if slot is not None and not any(file_slot(p) == slot for p in in_backup):
        raise RestoreRefused(f"This backup holds nothing for save slot {slot}.")
    return plan


def _place(source: Path, target: Path) -> None:
    """Replace ``target`` with a verified copy of ``source``, atomically."""
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = _hash_file(source)
    while True:
        temp = target.with_name(f"{target.name}.vf2-restore-{uuid.uuid4().hex[:12]}.tmp")
        try:
            writer = temp.open("xb")
        except FileExistsError:
            continue
        break
    try:
        with source.open("rb") as reader, writer:
            while True:
                chunk = reader.read(HASH_CHUNK)
                if not chunk:
                    break
                writer.write(chunk)
        if _hash_file(temp) != expected:
            raise BackupError(f"The restored copy of {target.name} did not match the backup.")
        kept = source.stat()
        _keep_times(temp, (kept.st_atime_ns, kept.st_mtime_ns))
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    if _hash_file(target) != expected:
        raise BackupError(f"{target.name} did not match the backup after it was restored.")


@dataclass
class RestoreResult:
    plan: RestorePlan
    before_restore: BackupResult | None


def running_game_names(save_folder: Path, processes: ProcessController | None = None) -> str:
    """The running exe name(s) that save into ``save_folder``, for messages (a plain description if none)."""
    try:
        controller = processes if processes is not None else WindowsProcesses()
        names = sorted({name for _pid, name in running_games(save_folder, controller)}, key=str.casefold)
    except (OSError, BackupError, AttributeError):
        names = []
    return " and ".join(names) if names else f"The game that saves into {save_folder.name}"


def _game_running(save_folder: Path, processes: ProcessController) -> int:
    return len(running_games(save_folder, processes))


def _roll_back(save_folder: Path, before: BackupResult | None, done: list[Path]) -> list[str]:
    problems: list[str] = []
    for relative in reversed(done):
        target = save_folder / relative
        original = before.backup_folder / relative if before else None
        try:
            if original is not None and original.is_file():
                # The before-restore backup's family saves are Paused; such a save goes back byte for byte
                # as it was, from the bytes kept when it was copied.
                if relative in before.unpaused_bytes:
                    _write_save(target, before.unpaused_bytes[relative],
                                target.read_bytes() if target.exists() else b"")
                    kept = original.stat()
                    _keep_times(target, (kept.st_atime_ns, kept.st_mtime_ns))
                else:
                    _place(original, target)
            elif target.exists():
                target.unlink()
        except (OSError, BackupError):
            problems.append(str(relative))
    return problems


def restore_backup(
    save_folder: Path,
    backup: Path,
    slot: int | None = None,
    processes: ProcessController | None = None,
    now: datetime | None = None,
) -> RestoreResult:
    """Restore ``backup`` (all of it, or one slot) into ``save_folder``.

    Refused while the game is running.  First backs the current state up as "Backup <date> (before
    restore)", then applies the plan file by file; on any failure every file already changed is put
    back from that backup.  The caller shows the plan (plan_restore) and gets the player's yes first.
    """
    controller = processes if processes is not None else WindowsProcesses()
    if _game_running(save_folder, controller):
        raise RestoreRefused(
            f"{running_game_names(save_folder, controller)} is running. Quit the game from its own menu first: a running "
            "game writes its families over the restored save the next time it saves (by itself every 2 minutes, or when "
            "it quits). Nothing was changed."
        )
    plan = plan_restore(save_folder, backup, slot)
    if plan.changes == 0:
        return RestoreResult(plan, None)
    before = None
    if files_to_back_up(save_folder):
        before = copy_save_folder(save_folder, now, suffix=BEFORE_RESTORE)
    if _game_running(save_folder, controller):
        raise RestoreRefused(
            f"{running_game_names(save_folder, controller)} was started during the restore, so it was stopped before "
            f"anything was changed. Your current saves are also in "
            f"{before.backup_folder if before else 'the save folder'}."
        )
    done: list[Path] = []
    started = f"{running_game_names(save_folder, controller)} was started during the restore. Quit it from its own menu and restore again."
    try:
        for relative in plan.replace + plan.add:
            if _game_running(save_folder, controller):
                raise BackupError(started)
            done.append(relative)
            _place(backup / relative, save_folder / relative)
        for relative in plan.remove:
            if _game_running(save_folder, controller):
                raise BackupError(started)
            done.append(relative)
            (save_folder / relative).unlink()
    except (OSError, BackupError) as exc:
        problems = _roll_back(save_folder, before, done)
        if problems:
            raise BackupError(
                f"The restore failed ({exc}) and some files could not be put back: {', '.join(problems)}. "
                f"Your saves as they were before the restore are in "
                f"{before.backup_folder if before else '(no files)'}."
            ) from exc
        raise BackupError(f"The restore failed ({exc}). Every file was put back as it was; nothing changed.") from exc
    return RestoreResult(plan, before)


# ---------------------------------------------------------------------------
# Deleting a backup
# ---------------------------------------------------------------------------


def _clear_read_only(path: str) -> None:
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def delete_backup(save_folder: Path, backup: Path) -> None:
    """Delete one backup folder (renamed "... (deleting)" first, so a half-done delete is never offered)."""
    _require_backup_of(save_folder, backup)
    doomed = backup.with_name(backup.name + DELETING)
    try:
        backup.rename(doomed)
    except OSError as exc:
        raise BackupError(
            f"The backup could not be deleted ({exc}); nothing was deleted. "
            "If another program has it open, close that and try again."
        ) from exc

    def retry_writable(function, path, _error):
        _clear_read_only(path)
        parent = os.path.dirname(path)
        if parent:
            _clear_read_only(parent)
        function(path)

    last: OSError | None = None
    for _attempt in range(DELETE_ATTEMPTS):
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(doomed, onexc=retry_writable)
            else:                                         # onexc is new in 3.12; the README promises 3.9
                shutil.rmtree(doomed, onerror=retry_writable)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last = exc
            time.sleep(DELETE_RETRY_SECONDS)
    raise BackupError(
        f"The backup was taken off the list but its folder could not be removed completely ({last}). "
        f"You can delete {doomed} yourself; it is no longer a usable backup."
    )
