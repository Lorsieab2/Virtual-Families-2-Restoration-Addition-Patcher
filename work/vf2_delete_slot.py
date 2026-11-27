"""Delete Player Slot: send every file tied to one Virtual Families 2 save slot to the Windows Recycle Bin.

The owner (2026-11-23, for the Virtual Villagers patcher; every patcher's tools match): the Copy Player Slot
window's "Delete" choice sends EVERY file linked to a save slot to the Recycle Bin -- "files linked to save slots =
logs, sidecars, backups, family tree files (NOT images) etc". It is the Virtual Villagers patcher's
src/vv_delete_slot.py on Virtual Families 2's own layout. Nothing is ever deleted for good: every file goes through
the Windows shell's Recycle Bin (vf2_translations.recycle: SHFileOperationW with FOF_ALLOWUNDO), so the player can
put any of it back from there. No new backup is made (the owner: the Recycle Bin is the way back).

What goes (Move Player Slot's list, vf2_move_slot.slot_files, so the two never disagree)
    * The slot's save "Virtual Families 2<N>.ldw" and the game's previous save "<N+20>", their Up to 28 Children
      and outfit pictures sidecars (and the ones a DLL set aside), the Names file, and everything in
      "Virtual Families 2 Patcher\\Save <N>" (the Family History log, the Family Tree Maker's tree file, edits,
      page and report).
    * In every whole-folder backup in "Backups": only that slot's files, found the same way inside the backup, so
      every other slot of every backup can still be restored.
    * The slot's own "Replaced by copy/move <date> - Save <N> - <name>" folders in Backups (the files Copy or Move
      once set aside from this slot).
    NOT recycled: pictures (.png, .jpg, .jpeg, .bmp, .gif) -- the owner: "NOT images". They stay where they are and
    the list shows them as kept.

Order and safety
    * Refused while the game runs. The player sees every file first and is asked twice; what they confirmed is
      fingerprinted (each file's size and time, the settings file's bytes), and anything changed since refuses.
    * The save folder's own files go first, then each backup's, then the set-aside folders. If Windows refuses a
      batch, everything stops and the result says what went and what did not (every file checked).
    * Fast (the owner, 2026-11-25, for the Virtual Villagers patcher's PR #876: "almost instant"): one Recycle Bin
      call for each of those parts; a folder that holds nothing but the slot's files (no picture, no other file, no
      link), 30 or more, sent whole as one item; and the drive's "is there a Recycle Bin?" question asked once per
      drive (a fixed drive once per run), while the player reads the list. A drive with no Recycle Bin is refused.
    * The settings file "Virtual Families 20.ldw" is written LAST (the slot's entry "NEW PLAYER", its in-use flag
      clear, as the game writes an empty slot) -- and also after a failure once the slot's save is gone, so the slot
      is never listed with no save behind it.
    * The slot's folders left empty are removed (empty folders only).

Nothing here touches Tk; the tests drive it against throwaway save folders with a stand-in Recycle Bin.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import vf2_copy_slot as cs
import vf2_move_slot as ms
import vf2_rename_family as rename
import vf2_save_backup as save_backup

TITLE = "Delete Player Slot"
PICTURES = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
BATCH = 1000                     # files or whole folders per Recycle Bin call
# A folder costs Windows about as much to recycle as 30 loose files (measured for the Virtual Villagers patcher,
# 2026-11-25: ~0.2 s a folder whatever it holds, ~5 ms a file), so only a folder of at least that many goes whole.
WHOLE_FOLDER_FROM = 30
NO_SAVE = "(no save -- leftover files)"
UNREADABLE = "(a save the game cannot load)"


class DeleteError(cs.CopyError):
    """A delete that was refused or failed, with a reason a player can read."""


class GameRunning(DeleteError):
    """The game that uses this save folder is running."""


def is_picture(path: Path) -> bool:
    return Path(path).name.casefold().endswith(PICTURES)


@dataclass
class Group:
    """Files recycled together: the save folder's own, one backup's, or one set-aside folder's."""
    where: str                                   # "" the save folder; else "Backups\\<folder>"
    root: Path | None = None                     # the folder it was found in (never itself recycled)
    files: list[Path] = field(default_factory=list)
    pictures: list[Path] = field(default_factory=list)
    folders: list[Path] = field(default_factory=list)   # the slot's folders to remove once empty
    aside: Path | None = None                    # a whole set-aside folder of the slot


@dataclass
class Plan:
    folder: Path
    slot: int
    name: str | None                             # the family (None: no save, or one the game cannot load)
    settings_before: bytes | None
    settings_after: bytes | None
    groups: list[Group] = field(default_factory=list)
    fingerprints: tuple = ()

    @property
    def files(self) -> list[Path]:
        return [p for g in self.groups for p in g.files]

    @property
    def pictures(self) -> list[Path]:
        return [p for g in self.groups for p in g.pictures]

    def signature(self) -> tuple:
        return (tuple(sorted(str(p).casefold() for p in self.files)), self.fingerprints)

    def preview(self) -> list[str]:
        lines = [f"Recycled:  {p.relative_to(self.folder)}" for p in self.files]
        return lines + [f"Kept (pictures):  {p.relative_to(self.folder)}" for p in self.pictures]


# ---------------------------------------------------------------------------
# What goes
# ---------------------------------------------------------------------------


def _discover(root: Path, slot: int, where: str) -> Group:
    """Slot ``slot``'s files in the save folder (or the whole-folder backup) ``root``."""
    group = Group(where, root)
    for path in ms.slot_files(root, slot):
        (group.pictures if is_picture(path) else group.files).append(path)
    group.folders = [cs.slot_root(root, slot)]
    return group


def _backups(folder: Path) -> list[Path]:
    backups = folder / save_backup.BACKUPS_FOLDER
    if not backups.is_dir():
        return []
    return [entry for entry in sorted(backups.iterdir(), key=lambda p: p.name.casefold())
            if entry.is_dir() and not save_backup._is_link(entry)]


def _snapshots(folder: Path) -> list[Path]:
    """Every whole-folder copy in Backups (a backup, or one that stopped part-way): never a set-aside folder."""
    return [entry for entry in _backups(folder) if cs.aside_slot(entry.name) is None]


def _aside_groups(folder: Path, slot: int) -> list[Group]:
    """The slot's own "Replaced by copy/move ... - Save <N> - ..." folders in Backups."""
    out = []
    for place in _backups(folder):
        if cs.aside_slot(place.name) != slot:
            continue
        group = Group(f"{save_backup.BACKUPS_FOLDER}\\{place.name}", place.parent, aside=place)
        for path in ms._walk(place):
            (group.pictures if is_picture(path) else group.files).append(path)
        out.append(group)
    return out


def plan_delete(folder: Path, slot: int) -> Plan:
    folder = Path(folder)
    if slot not in cs.SLOTS:
        raise DeleteError("A save slot is 1 to 5.")
    save = cs.save_path(folder, slot)
    name = None
    if save.is_file():
        try:
            raw = rename.save_name(save.read_bytes())
        except OSError as exc:
            raise DeleteError(f"Could not read {save.name}: {exc}") from exc
        name = rename.shown(raw) if raw is not None else None
    settings_file = rename.settings_path(folder)
    before = after = None
    if settings_file.is_file():
        before = settings_file.read_bytes()
        if rename._menu_offset(before, slot) is None:
            raise DeleteError(f"The settings file {settings_file.name} is not one the game can load.")
        after = ms._with_menu(before, slot, ms.EMPTY_SLOT, False)
    plan = Plan(folder, slot, name, before, after)
    try:
        plan.groups.append(_discover(folder, slot, ""))
        for snapshot in _snapshots(folder):
            group = _discover(snapshot, slot, f"{save_backup.BACKUPS_FOLDER}\\{snapshot.name}")
            if group.files or group.pictures:
                plan.groups.append(group)
        plan.groups += _aside_groups(folder, slot)
    except OSError as exc:
        raise DeleteError(f"Could not list the save folder: {exc}") from exc
    if not plan.files:                       # nothing at all, or only pictures (which always stay)
        raise DeleteError(f"Save {slot} has no files to delete.")
    prints = []
    for path in plan.files + plan.pictures:
        try:
            info = path.stat()
            prints.append((str(path).casefold(), info.st_size, info.st_mtime_ns))
        except OSError:
            prints.append((str(path).casefold(), None))
    prints.append(("settings", hashlib.sha256(before).hexdigest() if before is not None else None))
    plan.fingerprints = tuple(sorted(prints, key=lambda f: f[0]))
    return plan


def deletable_slots(folder: Path) -> list[tuple[int, str]]:
    """Every slot Delete can be used on -- any slot with a file plan_delete finds (its save, its leftovers, its files
    in a backup, a set-aside folder of it), not only one with a save the game loads -- with its label:
    "Save 2: <name>", "Save 2: (no save -- leftover files)", "Save 2: (a save the game cannot load)"."""
    out: list[tuple[int, str]] = []
    for slot in cs.SLOTS:
        try:
            plan = plan_delete(folder, slot)
        except (DeleteError, OSError):
            continue
        if plan.name is not None:
            what = plan.name
        elif cs.save_path(Path(folder), slot).is_file():
            what = UNREADABLE
        else:
            what = NO_SAVE
        out.append((slot, f"Save {slot}: {what}"))
    return out


# ---------------------------------------------------------------------------
# The questions (the words the patchers share)
# ---------------------------------------------------------------------------


def backups_words(backups: int, asides: int) -> str:
    """What else of the slot a delete sends to the Recycle Bin, said plainly so nothing surprises the player (the
    end-to-end check, 2026-11-27): the slot's copies inside earlier backups -- whatever family the slot held when each
    was made -- and the files a copy or move set aside, a move's undo copy among them."""
    parts = []
    if backups:
        parts.append(f"this slot's copies inside {backups} earlier backup(s) of the save folder, even a backup made "
                     "when the slot held an older family, and a move's \"(before move)\" backup")
    if asides:
        parts.append(f"{asides} folder(s) of files a copy or a move set aside from this slot (Backups\\Replaced by "
                     "...), a move's undo copy")
    if not parts:
        return ""
    return " The same goes for " + " and ".join(parts) + "."


def delete_text(plan: Plan) -> str:
    """The delete's question above the list of every file."""
    if plan.name is not None:
        family = plan.name or "(no name)"
    elif cs.save_path(Path(plan.folder), plan.slot).is_file():
        family = "an unreadable save"                    # the Virtual Families 1 patcher's words
    else:
        family = "no family, leftover files"
    backups = sum(1 for g in plan.groups if g.where and g.aside is None)
    asides = sum(1 for g in plan.groups if g.aside is not None)
    text = (f"Every file of Save {plan.slot} ({family}) goes to the Recycle Bin: its save, the game's previous save, "
            f"Up to 28 Children, the outfit pictures, the Names file, the Family History log and the Family Tree "
            f"files." + backups_words(backups, asides))
    text += (f" Pictures stay where they are. Other slots are not touched. No new backup is made: anything can be "
             f"put back from the Recycle Bin. ({plan.folder})")
    return text + f"\n\n{len(plan.files)} file(s) to the Recycle Bin, {len(plan.pictures)} picture(s) kept:"


def delete_final_text(plan: Plan) -> str:
    """The second, explicit question, naming the family."""
    family = plan.name or "the files"
    return (f"Delete {family} from Save {plan.slot}? Its {len(plan.files)} file(s), in this save folder and in its "
            "backups, go to the Recycle Bin. Delete it?")


def confirm_and_delete(
    ask: Callable[..., bool],
    preview: Callable[..., bool],
    run: Callable[[Callable[[], "DeleteResult"]], "DeleteResult"],
    folder: Path,
    slot: int,
    parent=None,
    processes=None,
    now: datetime | None = None,
    recycle=None,
) -> "DeleteResult | None":
    """Refused at once while the game runs. Every file is listed first; then a second question names the family.
    Only Yes to both sends exactly what was listed to the Recycle Bin. None when the player said No: then nothing
    at all changed."""
    controller = processes if processes is not None else save_backup.WindowsProcesses()
    _refuse_if_running(Path(folder), controller)
    plan = plan_delete(folder, slot)
    if recycle is None:
        warm_recycle_bin(Path(folder))           # answered while the player reads the list
    if not preview(parent, TITLE, delete_text(plan), plan.preview(), "Delete it?"):
        return None
    if not ask(parent, TITLE, delete_final_text(plan)):
        return None
    shown = plan.signature()
    return run(lambda: delete_slot(folder, slot, processes=controller, now=now, expected=shown, recycle=recycle))


# ---------------------------------------------------------------------------
# The delete
# ---------------------------------------------------------------------------


@dataclass
class DeleteResult:
    folder: Path
    slot: int
    name: str | None
    recycled: list[Path] = field(default_factory=list)
    not_recycled: list[Path] = field(default_factory=list)
    pictures: list[Path] = field(default_factory=list)
    backups_touched: int = 0
    asides: list[Path] = field(default_factory=list)
    problem: str | None = None                   # why it stopped (None: everything went)
    notes: list[str] = field(default_factory=list)


def _refuse_if_running(folder: Path, processes) -> None:
    try:
        cs._refuse_if_running(folder, processes)
    except cs.GameRunning as exc:
        raise GameRunning(str(exc).replace("about the copied family", "that the family was deleted")) from exc


def _shell(paths: list[Path]) -> None:
    import vf2_translations
    vf2_translations.recycle(paths)


def warm_recycle_bin(folder: Path) -> None:
    """Have Windows' "is there a Recycle Bin on this drive?" answered while the player reads the list (it adds up
    the whole Recycle Bin, which can take a second or more), so the delete itself does not wait for it."""
    import vf2_translations
    vf2_translations.prepare_recycle_bin(folder)


def _linked(entry: os.DirEntry) -> bool:
    return entry.is_symlink() or getattr(entry.stat(follow_symlinks=False), "st_reparse_tag", 0) == 0xA0000003


def _holds_no_file(folder: Path) -> bool:
    """An empty folder (or only empty folders in it), no link anywhere."""
    with os.scandir(folder) as scan:
        for entry in scan:
            if _linked(entry) or not entry.is_dir(follow_symlinks=False) or not _holds_no_file(folder / entry.name):
                return False
    return True


def _recycle_items(root: Path | None, files: list[Path]) -> list[tuple[Path, list[Path]]]:
    """What to hand Windows for ``files`` (all under ``root``), each with the files it holds: a folder below ``root``
    that holds nothing but those files -- at any depth: no other file, no picture, no link -- and at least
    WHOLE_FOLDER_FROM of them goes whole, as ONE item; every other file goes by itself. The same files either way,
    and the result is still checked file by file. ``root`` itself (the save folder, a backup, the Backups folder)
    is never sent."""
    if root is None:
        return [(p, [p]) for p in files]
    prefix = str(root).rstrip("\\/") + os.sep
    folded_prefix = prefix.casefold()
    listed = {str(p).casefold() for p in files}
    parts_of: list[list[str] | None] = []
    ancestors: dict[str, int] = {}                # each folder holding listed files: how many, at any depth
    for path in files:
        text = str(path)
        if not text.casefold().startswith(folded_prefix):
            parts_of.append(None)
            continue
        parts = text[len(prefix):].split(os.sep)
        parts_of.append(parts)
        for depth in range(1, len(parts)):
            key = (prefix + os.sep.join(parts[:depth])).casefold()
            ancestors[key] = ancestors.get(key, 0) + 1
    whole: dict[str, bool] = {}

    def is_whole(folder: str) -> bool:
        key = folder.casefold()
        if key in whole:
            return whole[key]
        ok = True
        try:
            with os.scandir(folder) as scan:
                entries = list(scan)
        except OSError:
            entries, ok = [], False
        for entry in entries:                    # every entry, so each folder inside is judged too
            here = folder + os.sep + entry.name
            try:
                if _linked(entry):
                    ok = False
                elif entry.is_dir(follow_symlinks=False):
                    if here.casefold() in ancestors:
                        ok = is_whole(here) and ok
                    elif not _holds_no_file(Path(here)):
                        ok = False
                elif here.casefold() not in listed:
                    ok = False
            except OSError:
                ok = False
        whole[key] = ok
        return ok

    items: dict[str, tuple[Path, list[Path]]] = {}
    for path, parts in zip(files, parts_of):
        place = path
        for depth in range(1, len(parts or ())):
            folder = prefix + os.sep.join(parts[:depth])
            if ancestors[folder.casefold()] >= WHOLE_FOLDER_FROM and is_whole(folder):
                place = Path(folder)
                break
        items.setdefault(str(place).casefold(), (place, []))[1].append(path)
    return list(items.values())


def delete_slot(folder: Path, slot: int, processes=None, now: datetime | None = None, expected: tuple | None = None,
                recycle=None) -> DeleteResult:
    """Send slot ``slot``'s files to the Recycle Bin (see the module's notes). ``recycle`` replaces the Windows call
    in tests (a list of paths; raises OSError when they cannot all go)."""
    folder = Path(folder)
    controller = processes if processes is not None else save_backup.WindowsProcesses()
    send = recycle or _shell
    _refuse_if_running(folder, controller)
    plan = plan_delete(folder, slot)
    if expected is not None and plan.signature() != expected:
        raise DeleteError(f"The files of Save {slot} changed after you confirmed, so nothing was deleted. "
                          "Try again to see the list as it is now.")
    result = DeleteResult(folder, slot, plan.name, pictures=plan.pictures)
    for group in plan.groups:
        try:
            items = _recycle_items(group.root, group.files)
            for start in range(0, len(items), BATCH):
                batch = items[start:start + BATCH]
                send([place for place, _held in batch])
                held = [p for _place, files in batch for p in files]
                left = [p for p in held if os.path.lexists(p)]
                if left:
                    raise OSError(f"{len(left)} file(s) were still there afterwards")
                result.recycled += held
            removed: list[Path] = []
            for root in group.folders + ([group.aside] if group.aside is not None else []):
                ms._remove_empty(root, removed)
            if group.where and group.aside is None:
                result.backups_touched += 1
            if group.aside is not None:
                result.asides.append(group.aside)
        except (OSError, cs.CopyError) as exc:
            result.recycled = [p for p in plan.files if not os.path.lexists(p)]
            result.not_recycled = [p for p in plan.files if os.path.lexists(p)]
            result.problem = (f"Windows could not send every file to the Recycle Bin ({exc}), so the delete stopped "
                              f"in {group.where or 'the save folder'}.")
            break
    # The settings file last -- and whenever the slot's save is gone, so the slot is never listed with no save.
    if plan.settings_after is not None and not os.path.lexists(cs.save_path(folder, slot)):
        path = rename.settings_path(folder)
        try:
            if path.read_bytes() == plan.settings_before:
                rename._write_atomically(path, plan.settings_after)
        except (OSError, rename.RenameError) as exc:
            result.notes.append(f"The settings file could not be updated ({exc}); the game rebuilds it when it "
                                "starts.")
    return result
