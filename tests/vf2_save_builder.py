"""Builds synthetic Virtual Families 2 family saves for tests, at the offsets src/vf2_save_reader.py reads.

Only the fields docs/vf2-save-format.md marks VERIFIED are set. Nothing here reads or writes a real save.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_save_reader as R  # noqa: E402


class SaveBuilder:
    def __init__(self, start_time: int = 1_600_000_000, nickname: str = "Tester"):
        self.b = bytearray(R.GAME_FILE_SIZE)
        self.b[0:4] = R.MAGIC
        struct.pack_into("<qI", self.b, 4, start_time, R.GAME_DATA_SIZE)
        struct.pack_into("<3i", self.b, R.gs_to_file(R.GS_PENDING_BABIES), -1, -1, -1)
        struct.pack_into("<i", self.b, R.gs_to_file(R.GS_SAVE_VERSION), 1001)
        struct.pack_into("<i", self.b, R.gs_to_file(R.GS_SPEED_OPTION), 10)
        self.nickname(nickname)
        self.clock(1000, 0)

    # -- whole-save fields --------------------------------------------------
    def nickname(self, name: str) -> "SaveBuilder":
        o = R.gs_to_file(R.GS_NICKNAME)
        self.b[o:o + 20] = name.encode("cp1252")[:19].ljust(20, b"\0")
        return self

    def clock(self, real_seconds_at_save: int, game_seconds: int) -> "SaveBuilder":
        """Paused clock (speed 0): Seconds() is the stored game seconds."""
        struct.pack_into("<iiIII", self.b, R.gs_to_file(R.GS_GAME_TIME), 0, 10, 0, game_seconds, real_seconds_at_save)
        return self

    def pending(self, *slots: int) -> "SaveBuilder":
        values = list(slots) + [-1] * (3 - len(slots))
        struct.pack_into("<3i", self.b, R.gs_to_file(R.GS_PENDING_BABIES), *values)
        return self

    def evicted(self, flag: int = 1) -> "SaveBuilder":
        struct.pack_into("<i", self.b, R.gs_to_file(R.GS_FAMILY_TREE), flag)
        return self

    def stats(self, babies_born: int = 0, oldest: int = 0) -> "SaveBuilder":
        g = R.gs_to_file(R.GS_GAME_STATS)
        struct.pack_into("<i", self.b, g + 8, babies_born)
        struct.pack_into("<i", self.b, g + 0x20, oldest)
        return self

    # -- villagers ----------------------------------------------------------
    def villager(self, slot: int, name: str, gender: int, years: int, *, active: bool = True, left_home: bool = False,
                 left_seconds: int = 0, health: int = 90, cause: int = -1, head: int = 1, body: int = 2,
                 pregnant: bool = False, babies: int = 0, mother: str = "", father: str = "") -> "SaveBuilder":
        v = R.gs_to_file(R.GS_VILLAGERS) + slot * R.VILLAGER_RECORD_SIZE
        self.b[v:v + R.VILLAGER_RECORD_SIZE] = bytes(R.VILLAGER_RECORD_SIZE)
        self.b[v] = 1 if active else 0
        self.b[v + 1] = 1 if left_home else 0
        struct.pack_into("<I", self.b, v + 4, left_seconds)
        bio, st = v + 0x08, v + 0xA8
        struct.pack_into("<ii", self.b, bio, years * R.AGE_UNITS_PER_YEAR, gender)
        self.b[bio + 0x10:bio + 0x10 + 25] = name.encode("cp1252")[:24].ljust(25, b"\0")
        struct.pack_into("<ii", self.b, bio + 0x2C, head, body)
        self.b[bio + 0x34:bio + 0x34 + 25] = father.encode("cp1252")[:24].ljust(25, b"\0")
        self.b[bio + 0x4E:bio + 0x4E + 25] = mother.encode("cp1252")[:24].ljust(25, b"\0")
        struct.pack_into("<ii", self.b, st + 0x0C, health, cause)
        struct.pack_into("<ii", self.b, st + 0x24, 500 if pregnant else 0, babies if pregnant else 0)
        struct.pack_into("<i", self.b, v + 0x140, -1)
        struct.pack_into("<I", self.b, v + 0x7B8, 0x19B)
        return self

    def remove(self, slot: int) -> "SaveBuilder":
        v = R.gs_to_file(R.GS_VILLAGERS) + slot * R.VILLAGER_RECORD_SIZE
        self.b[v] = 0
        return self

    # -- the Family Tree ----------------------------------------------------
    def _peep(self, offset: int, name: str, gender: int, slot: int, head: int = 1, body: int = 2, heir: int = -1) -> None:
        self.b[offset:offset + R.PEEP_RECORD_SIZE] = bytes(R.PEEP_RECORD_SIZE)
        self.b[offset:offset + 25] = name.encode("cp1252")[:24].ljust(25, b"\0")
        self.b[offset + 0x1A] = 1
        struct.pack_into("<iiiiii", self.b, offset + 0x1C, gender, head, body, slot, heir, -1)

    def generation(self, index: int, parent1: tuple, parent2: tuple | None = None, children=(),
                   heir: int = -1) -> "SaveBuilder":
        """parent/child = (name, gender, slot[, head, body])."""
        r = R.gs_to_file(R.GS_FAMILY_TREE) + 4 + index * R.FAMILY_RECORD_SIZE
        self.b[r:r + R.FAMILY_RECORD_SIZE] = bytes(R.FAMILY_RECORD_SIZE)
        self.b[r] = 1
        self._peep(r + 0x04, *parent1, heir=heir)
        if parent2 is not None:
            self._peep(r + 0xDC, *parent2)
        struct.pack_into("<i", self.b, r + 0x1B4, len(children))
        for k, c in enumerate(children):
            self._peep(r + 0x1B8 + k * R.PEEP_RECORD_SIZE, *c)
        return self

    def clear_tree_from(self, index: int) -> "SaveBuilder":
        for i in range(index, R.FAMILY_RECORDS):
            self.b[R.gs_to_file(R.GS_FAMILY_TREE) + 4 + i * R.FAMILY_RECORD_SIZE] = 0
        return self

    def copy(self) -> "SaveBuilder":
        other = SaveBuilder.__new__(SaveBuilder)
        other.b = bytearray(self.b)
        return other

    def bytes(self) -> bytes:
        return bytes(self.b)

    def write(self, path: Path) -> Path:
        Path(path).write_bytes(self.bytes())
        return Path(path)
