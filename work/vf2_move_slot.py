"""Move Player Slot: move one Virtual Families 2 family, with EVERY file tied to its save slot, into another slot of
the same save folder, and leave the slot it came from empty.

The owner (2026-11-22, for the Virtual Villagers patcher; every patcher's tools match): "transfer save files AND
BACKUPS AND LOGS AND ALL DATA FILES TIED TO A SAVE SLOT TO A DIFFERENT SLOT (CAN BE EXTRA DIALOGUES IN COPY PLAYER
SLOT)". It is the "Move" choice of the Copy Player Slot window (vf2_tools_gui), the Virtual Villagers patcher's
src/vv_move_slot.py on Virtual Families 2's own layout. The family keeps its name and every file; only the slot
changes.

What moves (the slot's files exactly as Copy Player Slot knows them, vf2_copy_slot.leftovers)
    * "Virtual Families 2<N>.ldw" and the game's previous save "Virtual Families 2<N+20>.ldw".
    * "Virtual Families 2 Patcher Data\\Children\\..." and "...\\Outfits\\..." sidecars of N and N+20 (and the
      ".unreadable-K.dat" ones a DLL set aside), and the Names file "...\\Names\\Virtual Families 2<N>.ldw.txt".
    * Everything in "Virtual Families 2 Patcher\\Save <N>\\": the Family History log, the Family Tree Maker's tree
      file and edits, and its Family Tree folder (the page, report and pictures).
    * In the shared settings file "Virtual Families 20.ldw": the target's slot-menu entry gets the family's name
      and its in-use flag, and the source's gets "NEW PLAYER" and a clear flag, as the game itself writes them.
    The whole-folder backups in "Backups" are snapshots of every slot at once and stay as they are.

What changes inside a moved file
    A path's "Virtual Families 2<N>.ldw" / "<N+20>" and "Save <N>" become the target's. Every Family History file's
    first line "Family: <name> (Save <N>)" says Save <T>, and a Family Tree Maker tree file records slot <T>
    (Copy Player Slot's own changes). The save and the sidecars are not changed at all: a sidecar names the hash
    and size of its save, and the save's bytes do not change. Every file keeps its times.

Safety
    * Refused while the game runs.
    * The player sees every file first (confirm_and_move); what they saw is fingerprinted, and anything changed
      since refuses the move.
    * The whole save folder is backed up first ("Backups\\Backup <date> (before move)").
    * The target's files -- its family when it holds one (the player said Yes to replacing it), or an earlier
      family's leftovers -- are MOVED, never deleted, into "Backups\\Replaced by move <date> - Save <T> - <name>".
    * Files are moved with a rename on the same disk, never over anything; a file whose content changes is then
      replaced through a temporary file. Every file is read back, the moved save is read with the patcher's reader.
    * All or nothing: any failure moves every file back, puts every changed byte back and returns the set-aside
      files.

Nothing here touches Tk; the tests drive it against throwaway save folders and a fake process list.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import vf2_copy_slot as cs
import vf2_game_text as game_text
import vf2_rename_family as rename
import vf2_save_backup as save_backup
import vf2_save_reader as reader

TITLE = "Move Player Slot"
BACKUP_LABEL = save_backup.BEFORE_MOVE
SLOTS = cs.SLOTS
OFFSET = reader.PREVIOUS_SAVE_OFFSET
EMPTY_SLOT = game_text.encode(rename.EMPTY_SLOT_TEXT)     # "NEW PLAYER": the game's entry for an empty slot


class MoveError(cs.CopyError):
    """A move that was refused or failed, with a reason a player can read."""


class GameRunning(MoveError):
    """The game that uses this save folder is running."""


# ---------------------------------------------------------------------------
# Every file of one slot
# ---------------------------------------------------------------------------


def _walk(root: Path) -> list[Path]:
    """Every file under ``root`` (never through a link), sorted."""
    found: list[Path] = []
    if not root.is_dir() or save_backup._is_link(root):
        return found
    for entry in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if save_backup._is_link(entry):
            continue
        if entry.is_dir():
            found += _walk(entry)
        elif entry.is_file():
            found.append(entry)
    return found


def slot_files(folder: Path, slot: int) -> list[Path]:
    """Every file tied to save slot ``slot`` of ``folder`` (a save folder, or a whole-folder backup of one): the
    saves N and N+20, their sidecars (and the set-aside ones), the Names file and everything in the patcher's
    "Save <N>" folder -- Copy Player Slot's own list (vf2_copy_slot.leftovers). Never anything in Backups."""
    out: list[Path] = []
    for path in cs.leftovers(Path(folder), slot, replace=True):
        if save_backup._is_link(path):
            continue
        if path.is_dir():
            out += _walk(path)
        elif path.is_file():
            out.append(path)
    unique: dict[str, Path] = {}
    for path in out:
        unique.setdefault(str(path).casefold(), path)
    return sorted(unique.values(), key=lambda p: str(p).casefold())


def moved_relative(relative: Path, source: int, target: int) -> Path:
    """Where the slot's file ``relative`` (inside the save folder) goes in the target slot."""
    parts = relative.parts
    if len(parts) >= 2 and parts[0].casefold() == cs.PATCHER_FOLDER.casefold() \
            and parts[1].casefold() == f"save {source}":
        return Path(parts[0], f"Save {target}", *[cs._retarget_name(part, source, target) for part in parts[2:]])
    name = parts[-1]
    for number, new in ((source + OFFSET, target + OFFSET), (source, target)):
        old = reader.save_file_name(number)
        if name.casefold().startswith(old.casefold()):
            name = reader.save_file_name(new) + name[len(old):]
            break
    return Path(*parts[:-1], name)


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


@dataclass
class Move:
    source: Path                   # the file now
    target: Path                   # where it goes
    original: bytes                # its bytes now
    data: bytes | None = None      # its new bytes, None: as they are


@dataclass
class Plan:
    folder: Path
    source: int
    target: int
    name: bytes                    # the family's name as its save stores it
    settings_before: bytes
    settings_after: bytes
    moves: list[Move] = field(default_factory=list)
    removals: list[Path] = field(default_factory=list)          # the target's files, set aside
    overwritten: str | None = None                              # the family replaced ("(no name)" unreadable)
    fingerprints: tuple = ()                                    # what each file was when planned

    @property
    def shown_name(self) -> str:
        return rename.shown(self.name)

    def signature(self) -> tuple:
        """What the player was shown: every move and every file set aside, and what each of those files and the
        settings file WERE (a path-only list would miss a file changed in place while the question was open)."""
        return (tuple(sorted((str(m.source).casefold(), str(m.target).casefold()) for m in self.moves)),
                tuple(sorted(str(p).casefold() for p in self.removals)),
                self.fingerprints)

    def preview(self) -> list[str]:
        """Every change, one line each: "<from>  ->  <to>"."""
        lines = []
        for m in self.moves:
            changed = " (slot updated inside)" if m.data is not None else ""
            lines.append(f"{m.source.relative_to(self.folder)}  ->  {m.target.relative_to(self.folder)}{changed}")
        return lines


def _fingerprint(path: Path, data: bytes | None = None) -> tuple:
    try:
        info = path.stat()
    except OSError:
        return (str(path).casefold(), None)
    digest = hashlib.sha256(data).hexdigest() if data is not None else ""
    return (str(path).casefold(), info.st_size, info.st_mtime_ns, digest)


def _refuse_if_running(folder: Path, processes) -> None:
    try:
        cs._refuse_if_running(folder, processes)
    except cs.GameRunning as exc:
        raise GameRunning(str(exc).replace("copied family", "moved family")) from exc


def _new_content(relative: Path, raw: bytes, source: int, target: int) -> bytes | None:
    """The file's bytes naming the target slot (Copy Player Slot's own changes), or None when nothing changes."""
    parts = relative.parts
    if len(parts) < 3 or parts[0].casefold() != cs.PATCHER_FOLDER.casefold():
        return None
    inside = Path(*parts[2:])
    if cs._history_file(inside):
        header = cs._HEADER.match(raw)
        if header and header.group("slot") == str(source).encode():
            return raw[:header.start("slot")] + str(target).encode() + raw[header.end("slot"):]
        return None
    if inside.suffix.casefold() == ".tree":
        try:
            tree = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        if isinstance(tree, dict) and tree.get("format") == cs.TREE_FORMAT and tree.get("slot") == source:
            tree["slot"] = target
            return json.dumps(tree, indent=1).encode("utf-8")       # as vf2_tree_memory.write_tree_file
    return None


def _with_menu(settings: bytes, slot: int, raw: bytes, used: bool) -> bytes:
    at = rename._menu_offset(settings, slot)
    if at is None or len(raw) + 1 > rename.MENU_FIELD:
        raise MoveError(f"The settings file {reader.save_file_name(0)} is not one the game can load.")
    out = settings[:at] + raw + b"\0" * (rename.MENU_FIELD - len(raw)) + settings[at + rename.MENU_FIELD:]
    flag = cs.FLAG_FIRST + slot - 1
    return out[:flag] + (b"\x01" if used else b"\x00") + out[flag + 1:]


def _read_only(path: Path) -> bool:
    """``path`` is marked read-only (Windows' Read-only box), so it can be renamed but not rewritten."""
    try:
        return not os.access(path, os.W_OK)
    except OSError:
        return False


def _refuse_read_only(plan: Plan) -> None:
    """Every file the move must rewrite (a log header, a tree file, the settings file) can be written, checked
    before anything moves: a read-only one would stop the move half way (the end-to-end check, 2026-11-26)."""
    rewrite = [m.source for m in plan.moves if m.data is not None] + [rename.settings_path(plan.folder)]
    locked = [p for p in rewrite if _read_only(p)]
    if locked:
        shown = "; ".join(str(p.relative_to(plan.folder)) for p in locked[:8])
        more = f" and {len(locked) - 8} more" if len(locked) > 8 else ""
        raise MoveError(f"These files are read-only, and the move must write the slot number inside them: "
                        f"{shown}{more}. Clear Read-only in each file's Properties (right-click it in File "
                        f"Explorer) and try again. Nothing was moved.")


def plan_move(folder: Path, source: int, target: int) -> Plan:
    """Everything the move would do, worked out and checked before anything is written."""
    folder = Path(folder)
    if source not in SLOTS or target not in SLOTS:
        raise MoveError("A save slot is 1 to 5.")
    if source == target:
        raise MoveError("Choose a slot other than the family's own.")
    save = cs.save_path(folder, source)
    try:
        data = save.read_bytes()
    except FileNotFoundError as exc:
        raise MoveError(f"Save {source} has no family ({save.name} is missing).") from exc
    except OSError as exc:
        raise MoveError(f"Could not read {save.name}: {exc}") from exc
    name = rename.save_name(data)
    if name is None:
        raise MoveError(f"{save.name} is not a Virtual Families 2 save the game can load.")
    try:
        reader.parse_family_save(data)
    except reader.SaveFormatError as exc:
        raise MoveError(f"{save.name} could not be read ({exc}), so nothing was moved.") from exc
    destination = cs.save_path(folder, target)
    if os.path.lexists(destination) and not destination.is_file():
        raise MoveError(f"{destination.name} is not a file, so nothing can be moved into Save {target}.")
    overwritten = cs.target_family_name(folder, target) if destination.is_file() else None
    settings = cs._settings_bytes(folder)
    if settings is None:
        raise MoveError(f"The settings file {rename.settings_path(folder).name} is not one the game can load.")
    after = _with_menu(settings, target, name, True)
    after = _with_menu(after, source, EMPTY_SLOT, False)
    plan = Plan(folder, source, target, name, settings, after, overwritten=overwritten)
    try:
        everything = slot_files(folder, source)
        plan.removals = slot_files(folder, target)
    except OSError as exc:
        raise MoveError(f"Could not list the save folder: {exc}") from exc
    for path in everything:
        relative = path.relative_to(folder)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise MoveError(f"Could not read {relative}: {exc}") from exc
        new_relative = moved_relative(relative, source, target)
        plan.moves.append(Move(path, folder / new_relative, raw, _new_content(relative, raw, source, target)))
    # Every place a file goes must be free once the target's files are set aside: nothing is ever written over.
    removing = {str(p).casefold() for p in plan.removals}
    places = [m.target for m in plan.moves]
    taken = [p for p in places if os.path.lexists(p) and str(p).casefold() not in removing]
    if taken:
        shown = "; ".join(str(p.relative_to(folder)) for p in taken[:8])
        more = f" and {len(taken) - 8} more" if len(taken) > 8 else ""
        raise MoveError(f"These files the move would make are already there and are not Save {target}'s: "
                        f"{shown}{more}. Nothing is ever written over, so nothing was moved.")
    names = [str(p).casefold() for p in places]
    if len(names) != len(set(names)):
        raise MoveError("Two of the slot's files would go to the same place, so nothing was moved.")
    _refuse_read_only(plan)
    plan.fingerprints = tuple(sorted(
        [_fingerprint(m.source, m.original) for m in plan.moves]
        + [_fingerprint(p) for p in plan.removals]
        + [_fingerprint(rename.settings_path(folder), settings)],
        key=lambda f: f[0]))
    return plan


# ---------------------------------------------------------------------------
# The questions (the words the patchers share)
# ---------------------------------------------------------------------------


def aside_label(plan: Plan, when: datetime) -> str:
    return f"{save_backup.BACKUPS_FOLDER}\\{cs.aside_name(when, plan.target, plan.overwritten or cs.target_family_name(plan.folder, plan.target), cs.REPLACED_MOVE)}"


def replace_text(plan: Plan, when: datetime) -> str:
    """The question for a move into a slot that holds a family."""
    old = plan.overwritten or "(no name)"
    return (f"Save {plan.target} holds the {old} family. It will be replaced by {plan.shown_name}, moved from Save "
            f"{plan.source} with all its files. The whole save folder ({plan.folder}) is backed up first, and "
            f"{old}'s files are kept in {aside_label(plan, when)}. Replace it?")


def move_text(plan: Plan, when: datetime) -> str:
    """The move's own question, above the list of every file."""
    text = (f"{plan.shown_name} will move from Save {plan.source} to Save {plan.target}, keeping its name, with its "
            f"save, the game's previous save, Up to 28 Children, the outfit pictures, the Revive snapshots, the skin tones, the Names file, the Family "
            f"History log and the Family Tree files. Save {plan.source} will be empty. The whole save folder "
            f"({plan.folder}) is backed up first.")
    if plan.removals:
        whose = "Leftover files from an earlier family" if plan.overwritten is None else "The files"
        text += f" {whose} in Save {plan.target} are kept in {aside_label(plan, when)}."
    return text + f"\n\nEverything that will change ({len(plan.moves)} file(s) moved):"


def preview_lines(plan: Plan, when: datetime) -> list[str]:
    """The list under the question: each file moved (old -> new), then each file set aside."""
    lines = plan.preview()
    for path in plan.removals:
        lines.append(f"Kept in {aside_label(plan, when)}:  {path.relative_to(plan.folder)}")
    return lines


def confirm_and_move(
    ask: Callable[..., bool],
    preview: Callable[..., bool],
    run: Callable[[Callable[[], "MoveResult"]], "MoveResult"],
    folder: Path,
    source: int,
    target: int,
    parent=None,
    processes=None,
    now: datetime | None = None,
) -> "MoveResult | None":
    """Refused at once while the game runs. A target that holds a family gets the replace question first; then the
    move's question over the list of every file. Only Yes to both backs up and moves exactly what was listed. None
    when the player said No: then nothing at all was written."""
    when = now or datetime.now().replace(microsecond=0)
    controller = processes if processes is not None else save_backup.WindowsProcesses()
    _refuse_if_running(Path(folder), controller)
    plan = plan_move(folder, source, target)
    if plan.overwritten is not None and not ask(parent, TITLE, replace_text(plan, when)):
        return None
    if not preview(parent, TITLE, move_text(plan, when), preview_lines(plan, when), "Move it?"):
        return None
    shown = plan.signature()
    return run(lambda: move_slot(folder, source, target, processes=controller, now=when, expected=shown))


# ---------------------------------------------------------------------------
# The move
# ---------------------------------------------------------------------------


@dataclass
class MoveResult:
    folder: Path
    source: int
    target: int
    name: str
    backup: save_backup.BackupResult
    moved: list[tuple[Path, Path]] = field(default_factory=list)
    updated: list[Path] = field(default_factory=list)            # moved files whose content names the target now
    removed: list[Path] = field(default_factory=list)            # the target's files, set aside
    set_aside: Path | None = None
    overwritten: str | None = None


@dataclass
class _Done:
    aside: list[tuple[Path, Path]] = field(default_factory=list)       # (the target's file, where it was set)
    aside_dirs: list[Path] = field(default_factory=list)
    moved: list[list] = field(default_factory=list)                    # [Move, rewritten?]
    dirs: list[Path] = field(default_factory=list)                     # folders the move made
    removed_dirs: list[Path] = field(default_factory=list)             # the source's emptied folders, removed
    settings: bool = False


def _rename(source: Path, target: Path) -> None:
    """``source`` renamed to ``target``, never over a file that is there (Windows refuses one itself)."""
    if os.path.lexists(target):
        raise MoveError(f"{target.name} is already there; nothing was moved over it.")
    os.rename(source, target)


def _write_over(path: Path, data: bytes, times: tuple[int, int]) -> None:
    """``path``'s content replaced through a temporary file, its times kept, read back."""
    temporary = path.with_name(f"{path.name}.move-{uuid.uuid4().hex[:12]}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.utime(temporary, ns=times)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.read_bytes() != data:
        raise MoveError(f"{path.name} did not read back as written.")


def _move_one(folder: Path, move: Move, done: _Done, fail: bool = False) -> None:
    info = move.source.stat()
    times = (info.st_atime_ns, info.st_mtime_ns)
    cs._make_folders(folder, move.target, done.dirs)
    _rename(move.source, move.target)
    done.moved.append([move, False])
    if fail:
        raise MoveError("stopped for the test")
    if move.data is not None:
        done.moved[-1][1] = True
        _write_over(move.target, move.data, times)
    if move.target.read_bytes() != (move.data if move.data is not None else move.original):
        raise MoveError(f"{move.target.name} did not read back after the move.")


def _remove_empty(root: Path, removed: list[Path]) -> None:
    """The folders under ``root`` (and ``root``) left empty, removed deepest first; anything left in one stays."""
    if not root.is_dir() or save_backup._is_link(root):
        return
    folders = [Path(dirpath) for dirpath, _dirs, _files in os.walk(root)]
    for sub in sorted(folders, key=lambda p: -len(p.parts)):
        try:
            if not any(sub.iterdir()):
                sub.rmdir()
                removed.append(sub)
        except OSError:
            pass


def _roll_back(plan: Plan, done: _Done) -> list[str]:
    problems: list[str] = []
    if done.settings:
        path = rename.settings_path(plan.folder)
        try:
            if path.read_bytes() != plan.settings_before:
                rename._write_atomically(path, plan.settings_before)
        except (OSError, rename.RenameError) as exc:
            problems.append(f"{path.name}: {exc}")
    for directory in reversed(done.removed_dirs):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            problems.append(f"{directory}: {exc}")
    for move, rewritten in reversed(done.moved):
        # A file whose rewrite failed (read-only) still holds its original bytes: it is only renamed back. A rewrite
        # that cannot be undone never stops the rename, so the file is always back in its own place.
        try:
            if rewritten and move.target.read_bytes() != move.original:
                info = move.target.stat()
                _write_over(move.target, move.original, (info.st_atime_ns, info.st_mtime_ns))
        except (OSError, MoveError) as exc:
            problems.append(f"{move.source.name} (now {move.target}): {exc}")
        try:
            move.source.parent.mkdir(parents=True, exist_ok=True)
            _rename(move.target, move.source)
        except (OSError, MoveError) as exc:
            problems.append(f"{move.source.name} (now {move.target}): {exc}")
    for directory in sorted(done.dirs, key=lambda p: -len(p.parts)):   # deepest first
        try:
            directory.rmdir()
        except OSError:
            pass
    for original, aside in reversed(done.aside):
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            _rename(aside, original)
        except (OSError, MoveError) as exc:
            problems.append(f"{original.name} (set aside as {aside}): {exc}")
    for directory in reversed(done.aside_dirs):
        try:
            directory.rmdir()
        except OSError:
            pass
    return problems


def verify(plan: Plan) -> None:
    """The source left empty, the moved save read with the patcher's reader, every file read back, and the settings
    file listing the family in the target and NEW PLAYER in the source."""
    folder = plan.folder
    if os.path.lexists(cs.save_path(folder, plan.source)):
        raise MoveError(f"Save {plan.source} still has a save after the move.")
    moved = cs.save_path(folder, plan.target)
    data = moved.read_bytes()
    original = next(m.original for m in plan.moves if m.target == moved)
    if data != original or rename.save_name(data) != plan.name:
        raise MoveError("The moved save is not the family that was moved.")
    reader.parse_family_save(data)
    for m in plan.moves:
        if m.source.exists():
            raise MoveError(f"{m.source.name} is still in Save {plan.source}.")
        if m.target.read_bytes() != (m.data if m.data is not None else m.original):
            raise MoveError(f"{m.target.name} did not read back after the move.")
    settings = rename.settings_path(folder).read_bytes()
    if settings != plan.settings_after:
        raise MoveError("The settings file does not read back as written.")
    parsed = reader.parse_settings(settings)
    if not parsed.slot_in_use[plan.target - 1] or parsed.slot_in_use[plan.source - 1]:
        raise MoveError("The settings file does not list the moved family.")


def move_slot(
    folder: Path,
    source: int,
    target: int,
    processes: save_backup.ProcessController | None = None,
    now: datetime | None = None,
    expected: tuple | None = None,
    _fail_after: int | None = None,
) -> MoveResult:
    """Move the family in ``source`` and everything tied to that slot into ``target``.

    Refused (MoveError, nothing changed) when the game is running, the source cannot be read, or a place a file
    would go is taken by something that is not the target's. Otherwise the folder is backed up first, the
    target's files are set aside, and every file is moved; on any failure everything is put back. ``expected`` is
    the plan the player was shown (Plan.signature): a different plan now refuses the move. ``_fail_after`` (tests
    only) makes the move fail after that many files."""
    folder = Path(folder)
    controller = processes if processes is not None else save_backup.WindowsProcesses()
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    plan = plan_move(folder, source, target)
    if expected is not None and plan.signature() != expected:
        raise MoveError(f"The files of Save {source} or Save {target} changed after you confirmed, so nothing was "
                        "moved. Try again to see the list as it is now.")
    try:
        backup = save_backup.copy_save_folder(folder, when, suffix=BACKUP_LABEL)
    except save_backup.BackupError as exc:
        raise MoveError(f"The backup before moving failed, so nothing was moved. {exc}") from exc
    _refuse_if_running(folder, controller)        # the backup took a moment
    done = _Done()
    aside = None
    try:
        if plan_move(folder, source, target).signature() != plan.signature():
            raise MoveError(f"The files of Save {source} or Save {target} changed while the backup was made.")
        if plan.removals:
            aside = cs.aside_folder(folder, when, target, plan.overwritten or cs.target_family_name(folder, target),
                                    cs.REPLACED_MOVE)
            for path in plan.removals:
                place = aside / path.relative_to(folder)
                cs._make_folders(folder, place, done.aside_dirs)
                _rename(path, place)
                done.aside.append((path, place))
        for count, move in enumerate(plan.moves):
            _move_one(folder, move, done, fail=_fail_after is not None and count >= _fail_after)
        done.settings = True
        rename._write_atomically(rename.settings_path(folder), plan.settings_after)
        _remove_empty(cs.slot_root(folder, source), done.removed_dirs)
        verify(plan)
    except Exception as exc:  # noqa: BLE001 -- every failure is rolled back
        problems = _roll_back(plan, done)
        if problems:
            raise MoveError(
                f"The move failed ({exc}) and these could not be put back: {'; '.join(problems)}. "
                f"Your backup is in {backup.backup_folder}.") from exc
        raise MoveError(
            f"The move failed ({exc}); every file was put back and Save {source} and Save {target} are as they "
            f"were. A backup is in {backup.backup_folder}.") from exc
    return MoveResult(folder, source, target, plan.shown_name, backup,
                      [(m.source, m.target) for m in plan.moves], [m.target for m in plan.moves if m.data is not None],
                      list(plan.removals), aside, plan.overwritten)
