"""Clear All Illnesses cures illness and nothing else, run on the built executables' own code (unicorn).

The Cheat Upgrade "Clear All Illnesses" (0x153) runs VF2ApplyResidentStat(eVF2ResidentClearIllnesses), which calls
VF2ClearIllnesses (work/patch_mobile_furniture_pack.py) for everyone alive at home.  The game's own cures write
exactly two things on a family member's CVillagerState (B200 desktop objects, VillagerState.obj and theMainScene.obj):

* a symptom: its flag byte at +0x5C+k and expiry dword at +0x64+4k (CVillagerState::ClearSymptom, the six symptom
  medicines, the Imported Candy cure);
* the infections: the mild (+0x80) and serious (+0x81) flags, one 16-bit store (Vancomycin; Imported Candy;
  Penicillin clears +0x80 alone).

+0x84..+0x87 and +0x88..+0x97 are the four food groups' active flags and 24-hour expiries:
CVillagerManager::UpdateNutritionAllVillagers sets flag +0x84+g and expiry +0x88+4g = now + 86,400, and
CVillagerState::FoodGroupsActive counts them.  No cure in the game touches them.  Up to B204's first upload the
patcher's cure zeroed them too, so a cured family member lost every food group.

Needs executables built from this branch or later: VF2_KIDS_EXE (the core) and/or VF2_B200_MATRIX_GLOB (every
variant; the cure is compiled into all of them).  Skipped when neither is set.  Every address is found in each
executable by its code, never assumed; nothing starts the game and nothing on disk is written.
"""
from __future__ import annotations

import faulthandler
import glob
import os
import re
import struct
from pathlib import Path

import pytest

faulthandler.disable()   # unicorn's first-chance access violations (tests/b200_time_emu.py does the same)

pefile = pytest.importorskip("pefile")
capstone = pytest.importorskip("capstone")
unicorn = pytest.importorskip("unicorn")
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc  # noqa: E402
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP  # noqa: E402

BASE = 0x400000
HEAP, HEAPSZ = 0x20000000, 0x100000
STACK, STACKSZ = 0x30000000, 0x100000
SENT = 0x3F000000
STATE_OFFSET = 0x6AF4           # CVillager -> CVillagerState (record +0xA8)
VILLAGER_SIZE = 0x1CC0C         # CVillagerManager's villager stride
NOW = 100_000

# VF2ApplyResidentStat: "cmp dword ptr [villager + 0x6B00], 0" (health), "cmp stat, 4", "jmp [stat*4 + table]"
APPLY_RESIDENT_STAT = re.compile(
    rb"\x83[\xB8-\xBF]\x00\x6B\x00\x00\x00.{2,6}\x83[\xF8-\xFF]\x04.{2,6}\xFF\x24[\x85\x8D\x95\x9D\xAD\xB5\xBD]",
    re.S)
# CVillagerState::FoodGroupsActive, byte for byte the B200 desktop object up to its first call
FOOD_GROUPS_ACTIVE = bytes.fromhex("558bec5153565733ffc745fc050000008db1840000008d9988000000")


def _executables() -> list[str]:
    out = []
    if os.environ.get("VF2_KIDS_EXE") and Path(os.environ["VF2_KIDS_EXE"]).is_file():
        out.append(os.environ["VF2_KIDS_EXE"])
    if os.environ.get("VF2_B200_MATRIX_GLOB"):
        out += sorted(glob.glob(os.environ["VF2_B200_MATRIX_GLOB"]))
    return sorted(set(out))


EXES = _executables()


def _call_targets(code: bytes, va: int) -> list[int]:
    """The direct (E8 rel32) call targets in code, in order."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    return [i.address + 5 + struct.unpack("<i", bytes(i.bytes[1:5]))[0]
            for i in md.disasm(code, va) if i.bytes[0] == 0xE8 and i.size == 5]


class Exe:
    def __init__(self, path: str):
        pe = pefile.PE(path, fast_load=True)
        data = pe.__data__
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        t0, t1, tva = text.PointerToRawData, text.PointerToRawData + text.SizeOfRawData, BASE + text.VirtualAddress
        code = bytes(data[t0:t1])
        hits = [m.start() for m in APPLY_RESIDENT_STAT.finditer(code)]
        assert len(hits) == 1, f"VF2ApplyResidentStat: {len(hits)} candidates"
        start = hits[0]
        while not (code[start - 1] == 0xCC and start % 16 == 0):   # back to the function's padded start
            start -= 1
        self.apply = tva + start
        calls = _call_targets(code[start:hits[0]], self.apply)
        assert len(calls) == 2, calls                  # VillagerExists(index, false), GetVillager(index)
        self.villager_exists, self.get_villager = calls
        fga = code.find(FOOD_GROUPS_ACTIVE)
        assert fga > 0 and code.find(FOOD_GROUPS_ACTIVE, fga + 1) < 0, "FoodGroupsActive"
        self.food_groups_active = tva + fga
        fga_calls = _call_targets(code[fga:fga + 0x56], self.food_groups_active)
        assert len(fga_calls) == 2, fga_calls          # theGameState::Get, GetSecondsFromGameStart
        game_state_get, seconds = fga_calls

        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(BASE, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        uc.mem_write(BASE, bytes(data[:0x1000]))
        for s in pe.sections:
            uc.mem_write(BASE + s.VirtualAddress, bytes(data[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]))
        for base, size in ((HEAP, HEAPSZ), (STACK, STACKSZ), (SENT, 0x1000)):
            uc.mem_map(base, size)
        uc.mem_write(SENT, b"\xC3" * 0x1000)
        self.villager = HEAP                            # one family member, slot 0
        self.state = HEAP + STATE_OFFSET
        self.stubs = {
            self.villager_exists: (lambda: 1 if self._arg(0) == 0 else 0, 8),
            self.get_villager: (lambda: self.villager, 4),
            game_state_get: (lambda: HEAP + VILLAGER_SIZE, 0),
            seconds: (lambda: NOW, 0),
        }
        uc.hook_add(UC_HOOK_CODE, self._code)

    def _arg(self, k):
        return struct.unpack("<I", self.uc.mem_read(self.uc.reg_read(UC_X86_REG_ESP) + 4 + 4 * k, 4))[0]

    def _code(self, uc, addr, _size, _user):
        stub = self.stubs.get(addr)
        if stub:
            fn, pop = stub
            result = fn()
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            uc.reg_write(UC_X86_REG_EAX, result & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
            uc.reg_write(UC_X86_REG_EIP, ret)

    def call(self, addr, args=(), ecx=0):
        sp = STACK + STACKSZ - 0x100
        for a in reversed(args):
            sp -= 4
            self.uc.mem_write(sp, struct.pack("<I", a & 0xFFFFFFFF))
        sp -= 4
        self.uc.mem_write(sp, struct.pack("<I", SENT))
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_ECX, ecx)
        self.uc.emu_start(addr, SENT, count=5_000_000)
        return self.uc.reg_read(UC_X86_REG_EAX)

    def state_bytes(self) -> bytes:
        return bytes(self.uc.mem_read(self.state, 0x200))

    def sick_and_fed(self, health=80):
        """A family member with all seven symptoms, both infections and all four food groups; every other state
        byte a recognisable pattern."""
        self.uc.mem_write(self.villager, bytes((k * 7 + 3) & 0xFF for k in range(VILLAGER_SIZE)))
        w8 = lambda off, v: self.uc.mem_write(self.state + off, bytes([v]))
        w32 = lambda off, v: self.uc.mem_write(self.state + off, struct.pack("<I", v & 0xFFFFFFFF))
        w32(0x0C, health)
        for k in range(7):
            w8(0x5C + k, 1)
            w32(0x64 + 4 * k, NOW + 3600 * (k + 6))
        w8(0x80, 1)
        w8(0x81, 1)
        for g in range(4):
            w8(0x84 + g, 1)
            w32(0x88 + 4 * g, NOW + 50_000 + g)        # low byte non-zero: no fifth slot surprises
        w32(0x98, 5)                                   # a career: the fifth slot counts nothing


@pytest.fixture(scope="module", params=EXES or [None], ids=lambda p: Path(p).parent.name if p else "none")
def exe(request):
    if request.param is None:
        pytest.skip("VF2_KIDS_EXE / VF2_B200_MATRIX_GLOB are not set to executables built from this branch")
    return Exe(request.param)


CURED = {0x5C + k for k in range(7)} | {0x64 + b for b in range(28)} | {0x80, 0x81}
FOOD_GROUPS = set(range(0x84, 0x98))


def test_the_cure_clears_illness_and_keeps_the_food_groups(exe):
    exe.sick_and_fed()
    # Counted first: for a member with a career, the game's own fifth pass writes 0 into the Grains expiry's low
    # byte (+0x88), so the snapshot is taken after it and the cure alone is compared.
    assert exe.call(exe.food_groups_active, (0,), ecx=exe.state) == 4
    before = exe.state_bytes()
    villager_before = bytes(exe.uc.mem_read(exe.villager, VILLAGER_SIZE))
    exe.call(exe.apply, (0,))                          # eVF2ResidentClearIllnesses
    after = exe.state_bytes()

    changed = {k for k in range(len(before)) if before[k] != after[k]}
    assert changed == {k for k in CURED if before[k] != 0}, sorted(hex(k) for k in changed)
    assert all(after[k] == 0 for k in CURED)           # every symptom, both infections
    assert after[0x84:0x98] == before[0x84:0x98]       # the food groups' flags and timers, untouched
    assert exe.call(exe.food_groups_active, (0,), ecx=exe.state) == 4
    villager_after = bytes(exe.uc.mem_read(exe.villager, VILLAGER_SIZE))
    outside = [k for k in range(VILLAGER_SIZE) if villager_before[k] != villager_after[k]
               and not (STATE_OFFSET <= k < STATE_OFFSET + 0x200)]
    assert outside == []                               # nothing else on the villager


def test_the_cure_leaves_the_dead_alone(exe):
    exe.sick_and_fed(health=0)
    before = exe.state_bytes()
    exe.call(exe.apply, (0,))
    assert exe.state_bytes() == before
