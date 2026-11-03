"""Names longer than their save field: the short form in the save, the whole name in the slot's Names file.

With Render Unicode with In-Game Fonts or Use Unicode Font on, every name box takes up to
``vf2_game_text.NAME_BOX_BYTES`` bytes as stored (1,200, the engine's own cap, no separate character cap: SetCanEdit
clamps every box to 4B0h), but the save keeps each name in a fixed field: a family name 19 bytes (GetText(.., 14h)
into gs+0x25ABC and the slot menu's gs+0x25B30 + 0x15 x (N-1)), a family member's name 18 bytes as typed
(GetText(.., 13h), then strncpy(.., 19h) into the member's 25-byte field). The save format is never changed, so (the
same rule as Virtual Families 1, docs/UNICODE_TEXT.md):

* a name that fits its field is stored as it is, exactly as before;
* a longer name is stored as its SHORT FORM: the longest start of it that fits, cut between whole characters, then
  ``NAME_MARK`` ("...") -- or, when that short form already stands for another name, "2...", "3..." and so on. A
  short form names one name only: it follows the family member wherever the game copies their name (the parents'
  names of their children, the Family Tree, a death), and the stock game (or both Unicode settings off) loads,
  plays and shows it as it is;
* the whole name is kept in the slot's Names file, "Virtual Families 2 Patcher Data\\Names\\Virtual Families
  2<N>.ldw.txt" (N = 1..5, the save file's name + ".txt"): UTF-8 lines, "VF2 Names 1", then
  ``short<TAB>room<TAB>name`` (room: the field's bytes it was made for). The game itself (vf2unicode_b200.dll /
  vf2unicodefont_b200.dll, runtime/native/b200unicode/b200names.inc) writes it when a name is typed, and draws the
  whole name wherever its short form is drawn; the patcher's readers and tools use this module, by the same rule.

A line is never removed: a short form no longer in the save is harmless (a new short form is never made equal to
it), so the game's previous save "<N+20>" stays readable too. A file that cannot be read is read as empty: the save
still shows its short forms.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import vf2_game_text as game_text

NAME_BOX_BYTES = game_text.NAME_BOX_BYTES
MARK = game_text.NAME_MARK
PATCHER_DATA = "Virtual Families 2 Patcher Data"
FOLDER = "Names"
HEADER = "VF2 Names 1"
SLOTS = (1, 2, 3, 4, 5)

FAMILY_ROOM = 19          # GetText(.., 0x14): a family name keeps 19 bytes (gs+0x25ABC, the slot menu's names)
MEMBER_ROOM = 18          # GetText(.., 0x13): a family member's name keeps 18 bytes as typed


@dataclass(frozen=True)
class Entry:
    short: str
    room: int
    full: str


def names_path(folder: Path, slot: int) -> Path:
    return Path(folder) / PATCHER_DATA / FOLDER / f"Virtual Families 2{slot}.ldw.txt"


def size(text: str) -> int:
    """Bytes of ``text`` in the save's stored form (vf2_game_text.encode)."""
    return len(game_text.encode(text))


def name_problem(full: str) -> str | None:
    """Why ``full`` cannot be a name (None when it can): 1..NAME_BOX_BYTES bytes as stored (no separate
    character cap), no control characters."""
    if not full:
        return "A name needs at least one character."
    for ch in full:
        cp = ord(ch)
        if cp < 0x20 or 0x7F <= cp < 0xA0:
            return "A name cannot hold control characters (tabs, line breaks)."
        if 0xD800 <= cp <= 0xDFFF:
            return "A name cannot hold a lone surrogate."
    if size(full) > NAME_BOX_BYTES:
        return (f"A name can be at most {NAME_BOX_BYTES:,} bytes (this one is {size(full):,}); some characters, "
                "such as joined emoji, take many bytes.")
    return None


def parse(data: bytes) -> list[Entry]:
    """A Names file's entries (in file order); anything not valid is left out (as the DLL's LoadSlot)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != HEADER:
        return []
    out: list[Entry] = []
    seen: set[str] = set()
    for line in lines[1:]:
        parts = line.rstrip("\r").split("\t")
        if len(parts) != 3 or not parts[1].isdigit() or not parts[1].isascii():
            continue
        short, room, full = parts[0], int(parts[1]), parts[2]
        if (short in seen or not short.endswith(MARK) or name_problem(full) is not None
                or not 1 <= room < NAME_BOX_BYTES or size(short) > room or size(short) > 24):
            continue
        seen.add(short)
        out.append(Entry(short, room, full))
    return out


def render(entries: list[Entry]) -> bytes:
    return ("\n".join([HEADER] + [f"{e.short}\t{e.room}\t{e.full}" for e in entries]) + "\n").encode("utf-8")


def read(path: Path) -> list[Entry]:
    try:
        return parse(Path(path).read_bytes())
    except OSError:
        return []


def read_slot(folder: Path, slot: int) -> list[Entry]:
    return read(names_path(folder, slot))


def write(path: Path, entries: list[Entry]) -> None:
    """Write a Names file through a temporary file beside it, then check it reads back."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = render(entries)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    if path.read_bytes() != data:
        raise OSError(f"{path} did not read back as written")


def short_form(full: str, room: int, taken: dict[str, str]) -> str:
    """What the save field of ``room`` bytes stores for ``full``, given the short forms already ``taken`` (short ->
    name, in file order). The same rule as the DLL's ShortFor (b200names.inc):

    * a short form already standing for this very name, that fits, is used again;
    * a name that fits and is no short form of another name is stored as it is;
    * else the longest start that fits with the mark (trailing spaces dropped) + "...", then + "2...", "3...", ...
      until one is not taken."""
    for short, name in taken.items():
        if name == full and size(short) <= room:
            return short
    if size(full) <= room and full not in taken:
        return full
    n = 1
    while True:
        tail = MARK if n == 1 else f"{n}{MARK}"
        if len(tail) > room:
            raise ValueError("no room for a short form")
        head = game_text.decode(game_text.fit(full, room - len(tail))).rstrip(" ")
        short = head + tail
        if short not in taken:
            return short
        n += 1


def full_name(stored: str, entries) -> str:
    """The whole name for a name as the save stores it (itself when it is no short form)."""
    for e in entries:
        if e.short == stored:
            return e.full
    return stored


class Book:
    """Every slot's Names file in one save folder: what the readers show, and what the tools write."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.slots: dict[int, list[Entry]] = {s: read_slot(self.folder, s) for s in SLOTS}

    def taken(self) -> dict[str, str]:
        """Every short form of every slot (a family name's short form shows in the slot menu beside the others')."""
        out: dict[str, str] = {}
        for slot in SLOTS:
            for e in self.slots[slot]:
                out.setdefault(e.short, e.full)
        return out

    def full(self, slot: int, stored: str) -> str:
        """``stored`` as a family member of ``slot`` (or any slot's family name) is called."""
        for e in self.slots.get(slot, []):
            if e.short == stored:
                return e.full
        for s in SLOTS:
            for e in self.slots[s]:
                if e.short == stored:
                    return e.full
        return stored

    def store(self, slot: int, full: str, room: int) -> tuple[str, Entry | None]:
        """The short form to store for ``full`` in ``slot``'s field of ``room`` bytes, and the new line for the slot's
        Names file (None when none is needed). Nothing is written here."""
        short = short_form(full, room, self.taken())
        if short == full:
            return short, None
        for e in self.slots[slot]:
            if e.short == short:
                return short, None
        return short, Entry(short, room, full)

    def add(self, slot: int, entry: Entry) -> None:
        self.slots[slot] = [e for e in self.slots[slot] if e.short != entry.short] + [entry]

    def rendered(self, slot: int) -> bytes:
        return render(self.slots[slot])

    def write_slot(self, slot: int) -> None:
        write(names_path(self.folder, slot), self.slots[slot])
