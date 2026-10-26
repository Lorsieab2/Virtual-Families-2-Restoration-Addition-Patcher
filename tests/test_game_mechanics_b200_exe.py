"""The Game Mechanics window's settled rules, re-run on the B200 core executable's own code (unicorn).

Needs VF2_B200_CORE_EXE = the matrix build's `Virtual Families 2 - B200.exe` (core variant); skipped otherwise.
Every address below is in that executable (sha256 SHA256_PREFIX...); a different build is skipped, never guessed.
The routines run as linked; only the clock readers, the rand() feeder, sound, speech, achievements, saving and
the scene's other callees are answered by Python.  Nothing starts the game and nothing on disk is written.

Each test also checks that src/vf2_game_mechanics.py says what the run shows.
"""
from __future__ import annotations

import faulthandler
import hashlib
import os
import struct
import sys
from pathlib import Path

import pytest

# unicorn commits guest memory through first-chance access violations it handles itself; faulthandler would print
# a stack for each one (tests/b200_time_emu.py does the same).
faulthandler.disable()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_game_mechanics as gm  # noqa: E402

pefile = pytest.importorskip("pefile")
unicorn = pytest.importorskip("unicorn")
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc  # noqa: E402
from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_EAX, UC_X86_REG_EBP,  # noqa: E402
                               UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ES, UC_X86_REG_ESP,
                               UC_X86_REG_FS, UC_X86_REG_GDTR, UC_X86_REG_SS)

SHA256_PREFIX = "5cad4050c991c3c5"
CORE_EXE = os.environ.get("VF2_B200_CORE_EXE")

BASE = 0x400000
HEAP, HEAPSZ = 0x20000000, 0x2000000
STACK, STACKSZ = 0x30000000, 0x100000
SENT, TEB, GDT = 0x3F000000, 0x3E000000, 0x3D000000

# B200 core addresses (names from the desktop object files the patcher relinks; docs/game-mechanics/spec.md)
RAND = 0x4D8F58
GET_RANDOM = 0x4757C0
GAME_STATE_PTR = 0x685A88                  # theGameState singleton
GET_SECONDS_FROM_GAME_START = 0x475830
GAME_TIME, NUM_TIMERS = 0x683038, 0x683030
SECONDS, SET_SPEED = 0x468B00, 0x468B80
VILLAGER_MANAGER, VILLAGER0, STRIDE = 0x706F90, 0x706F90 + 0x1CC70, 0x1CC0C
TIMEFLOW, TIMEFLOW_INCREMENT_AGE_CALL = 0x4C4C30, 0x4C4DEF
PHYSIOLOGY, OLD_AGE_ROLL_SITE = 0x4C4410, 0x4C47A8
FOOD_GROUPS_ACTIVE = 0x4CB870
UPDATE_DISEASE, DISEASE_ROLL_SITE = 0x4CBBE0, 0x4CBD49
MONEY, UPDATE_INTEREST = 0x68658C, 0x481D80
SPECIAL_UPGRADE_PURCHASE, BROKERAGE = 0x4B8B50, 0x117
SCENE_STEP, MALFUNCTION_PICKED, STEP_END = 0x4A266E, 0x4A28F9, 0x4A2AB1
INVENTORY, CATEGORY_COUNT, CATEGORY_ITEM, ROTATE, GOODIES = 0x6852C0, 0x46B6D0, 0x46B210, 0x46BEB0, 0x56F5BC
FLEA_MARKET = 15
STUBS = {                                  # callee -> bytes it pops
    0x401C00: 8, 0x4C70E0: 8, 0x48DE30: 4, 0x4B6DA0: 0, 0x4B6D20: 0, 0x453420: 16, 0x49A750: 12, 0x4C6620: 24,
    0x49AB50: 0,
}


def core_exe() -> Path:
    if not CORE_EXE or not Path(CORE_EXE).is_file():
        pytest.skip("VF2_B200_CORE_EXE is not set to the B200 core executable")
    data = Path(CORE_EXE).read_bytes()
    if not hashlib.sha256(data).hexdigest().startswith(SHA256_PREFIX):
        pytest.skip("VF2_B200_CORE_EXE is a different build: these addresses are the B200 core's")
    return Path(CORE_EXE)


class Emu:
    def __init__(self, exe: Path):
        pe = pefile.PE(str(exe), fast_load=True)
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(BASE, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        uc.mem_write(BASE, bytes(pe.__data__[:0x1000]))
        for s in pe.sections:
            uc.mem_write(BASE + s.VirtualAddress, bytes(pe.__data__[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]))
        for base, size in ((HEAP, HEAPSZ), (STACK, STACKSZ), (SENT, 0x1000), (TEB, 0x1000), (GDT, 0x1000)):
            uc.mem_map(base, size)
        uc.mem_write(SENT, b"\xC3" * 0x1000)

        def entry(b, lim, acc, fl):
            return ((lim & 0xFFFF) | ((b & 0xFFFFFF) << 16) | (acc << 40) | (((lim >> 16) & 0xF) << 48) | (fl << 52)
                    | (((b >> 24) & 0xFF) << 56))
        uc.mem_write(GDT + 8, struct.pack("<Q", entry(0, 0xFFFFF, 0x9B, 0xC)))
        uc.mem_write(GDT + 16, struct.pack("<Q", entry(0, 0xFFFFF, 0x93, 0xC)))
        uc.mem_write(GDT + 24, struct.pack("<Q", entry(TEB, 0xFFF, 0x93, 0x4)))
        uc.reg_write(UC_X86_REG_GDTR, (0, GDT, 0xFF, 0))
        for reg, sel in ((UC_X86_REG_CS, 8), (UC_X86_REG_DS, 16), (UC_X86_REG_ES, 16), (UC_X86_REG_SS, 16),
                         (UC_X86_REG_FS, 24)):
            uc.reg_write(reg, sel)
        uc.mem_write(TEB, struct.pack("<I", 0xFFFFFFFF))
        self.heap = HEAP
        self.now = 100_000
        self.plan: dict[int, int] = {}        # GetRandom call site -> raw rand() value
        self.stubs = {RAND: (self._rand, 0), GET_SECONDS_FROM_GAME_START: (lambda: self.now, 0)}
        for addr, pop in STUBS.items():
            self.stubs[addr] = ((lambda: 1) if addr == 0x49AB50 else (lambda: 0), pop)
        self.watch: dict[int, list] = {}
        uc.hook_add(UC_HOOK_CODE, self._code)
        self.gs = self.alloc(0x26100)
        self.w32(GAME_STATE_PTR, self.gs)
        tod = self.alloc(16)
        self.uc.mem_write(tod, struct.pack("<f", 12.0))  # CNight::GetTimeOfDay: noon (fld [tod]; ret)
        self.uc.mem_write(0x482A30, b"\xD9\x05" + struct.pack("<I", tod) + b"\xC3")
        for k in range(30):
            self.w8(VILLAGER0 + k * STRIDE + 0x1BB84, 0)

    # memory
    def alloc(self, n):
        a = self.heap
        self.heap += (n + 15) & ~15
        return a

    def r32(self, a):
        return struct.unpack("<i", self.uc.mem_read(a, 4))[0]

    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack("<I", v & 0xFFFFFFFF))

    def r8(self, a):
        return self.uc.mem_read(a, 1)[0]

    def w8(self, a, v):
        self.uc.mem_write(a, bytes([v & 0xFF]))

    def f32(self, a):
        return struct.unpack("<f", self.uc.mem_read(a, 4))[0]

    def f64(self, a):
        return struct.unpack("<d", self.uc.mem_read(a, 8))[0]

    # execution
    def _rand(self):
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        site, n = self.r32(esp + 12), self.r32(esp + 16)      # GetRandom's caller and its N
        if not (0x401000 <= self.r32(esp) < 0x4F0000):
            site, n = self.r32(esp), 0
        value = self.plan.get(site)
        return ((n - 1) if 0 < n <= 32767 else 32767) if value is None else value

    def _code(self, uc, addr, size, _user):
        record = self.watch.get(addr)
        if record is not None:
            record.append(uc.reg_read(UC_X86_REG_EAX))
        stub = self.stubs.get(addr)
        if stub:
            fn, pop = stub
            result = fn()
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            if result is not None:
                uc.reg_write(UC_X86_REG_EAX, result & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
            uc.reg_write(UC_X86_REG_EIP, ret)

    def call(self, addr, args=(), ecx=0):
        sp = STACK + STACKSZ - 0x100
        for a in reversed(args):
            sp -= 4
            self.w32(sp, a)
        sp -= 4
        self.w32(sp, SENT)
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_EBP, 0)
        self.uc.reg_write(UC_X86_REG_ECX, ecx)
        self.uc.emu_start(addr, SENT, count=50_000_000)
        return self.uc.reg_read(UC_X86_REG_EAX)


@pytest.fixture(scope="module")
def emu():
    return Emu(core_exe())


STATE = VILLAGER0 + 0x6AF4                 # family member 0's CVillagerState (record +0xA8)


def _member(e, age=600, health=80):
    e.w8(VILLAGER0 + 0x1BB84, 1)
    e.w8(VILLAGER0 + 0x1BB88, 0)
    e.w32(VILLAGER0 + 0x6A54, age)
    e.w32(STATE + 0x0C, health)


def _groups(e, active, career, grains_expiry=None):
    for k in range(4):
        e.w8(STATE + 0x84 + k, 1 if k in active else 0)
        e.w32(STATE + 0x88 + 4 * k, e.now + 50_000 if k in active else 0)
    if grains_expiry is not None:
        e.w32(STATE + 0x88, grains_expiry)
    e.w32(STATE + 0x98, career)            # record +0x140, the career id


# ------------------------------------------------------------------ time away and the paused clock
def _credited(e, away, catch_up=0, option=10):
    _member(e)
    e.w32(STATE + 0x00, 0)
    e.w32(STATE + 0x04, 1000)
    e.w32(e.gs + 0x25B18, option)
    e.now = 1000 + away
    units = []
    e.watch = {TIMEFLOW_INCREMENT_AGE_CALL: units}
    e.call(TIMEFLOW, (catch_up,), ecx=VILLAGER_MANAGER)
    e.watch = {}
    aged = e.r32(VILLAGER0 + 0x6A54) - 600
    return (units[0] * 600 + e.r32(STATE)) if units else 0, aged


def test_time_away_is_capped_as_the_window_says(emu):
    assert _credited(emu, 30_000) == (30_000, 50)
    assert _credited(emu, 50_000) == (31_000, 51)
    assert _credited(emu, 86_400) == (31_000, 51)          # "greater than": exactly 24 h is still 31,000
    assert _credited(emu, 200_000) == (86_400, 144)
    assert _credited(emu, 50_000, option=1009)[1] == 0     # saved paused: nothing made up
    assert _credited(emu, 50_000, catch_up=1) == (50_000, 83)
    text = gm.render()
    assert "up to 31,000 seconds (8 hours 36 minutes 40 seconds) away is made up in full" in text
    assert "51 age units, about 2.55 years" in text and "144 age units, 7.2 years" in text


def test_a_paused_clock_stops(emu):
    e = emu
    e.w32(NUM_TIMERS, 0)
    for off, value in ((0x20, 10), (0x24, 10), (0x28, 1000), (0x2C, 500)):
        e.w32(GAME_TIME + off, value)
    e.now = 5000
    assert e.call(SECONDS, ecx=GAME_TIME) == 4500
    e.call(SET_SPEED, (999,), ecx=GAME_TIME)
    assert e.r32(GAME_TIME + 0x20) == 0                    # 999 stores speed 0
    for later in (5000, 20_000, 90_000):
        e.now = later
        assert e.call(SECONDS, ecx=GAME_TIME) == 4500
    e.call(SET_SPEED, (10,), ecx=GAME_TIME)
    e.now = 90_060
    assert e.call(SECONDS, ecx=GAME_TIME) == 4560


# ------------------------------------------------------------------ the fifth food-group slot (Grains)
@pytest.mark.parametrize("active, career, stale, counted", [
    ([], -1, None, 0), ([0], -1, None, 2), ([1], -1, None, 1), ([0, 1], -1, None, 3), ([0, 1, 2, 3], -1, None, 5),
    ([0], 5, None, 1), ([0, 1, 2, 3], 5, None, 4),
    ([], -1, 100_000 - 1000, 1),                          # Grains ran out: still one for the careerless
    ([0], -1, (150_000 & ~0xFF), 1),                      # a Grains expiry ending in byte 0: no extra
])
def test_food_groups_counted(emu, active, career, stale, counted):
    emu.now = 100_000
    _groups(emu, active, career, stale)
    assert emu.call(FOOD_GROUPS_ACTIVE, (0,), ecx=STATE) == counted


def _old_age_death_percent(e, year, active, career):
    dead = 0
    for r in range(100):
        _member(e, age=year * 20 + 1)
        e.w32(STATE + 0x08, year * 20)
        e.w32(STATE + 0x10, -1)
        for off, value in ((0x38, 50), (0x40, 40), (0x34, 50), (0x24, 0)):
            e.w32(STATE + off, value)
        for k in range(7):
            e.w8(STATE + 0x5C + k, 0)
            e.w32(STATE + 0x64 + 4 * k, 0)
        e.w8(STATE + 0x80, 0)
        e.w8(STATE + 0x81, 0)
        _groups(e, active, career)
        e.w32(0x679810 + 0x78, 500)                       # food in the house
        e.plan = {OLD_AGE_ROLL_SITE: r}
        e.call(PHYSIOLOGY, ecx=VILLAGER_MANAGER)
        if e.r32(STATE + 0x0C) <= 0:
            dead += len(range(r, 32768, 100))
        e.w8(VILLAGER0 + 0x1BB84, 0)
    e.plan = {}
    return round(100 * dead / 32768)


def test_old_age_follows_the_groups_counted(emu):
    emu.now = 100_000
    emu.stubs[SECONDS] = (lambda: emu.now, 0)
    try:
        assert [_old_age_death_percent(emu, y, [], 5) for y in (55, 56, 60, 65)] == [0, 10, 50, 100]
        assert [_old_age_death_percent(emu, y, [0, 1, 2, 3], 5) for y in (59, 60, 64, 69)] == [0, 10, 50, 100]
        # careerless with Grains and Dairy: counted 3, as an employed member with 3 groups
        assert _old_age_death_percent(emu, 60, [0, 1], -1) == _old_age_death_percent(emu, 60, [0, 1, 2], 5) == 20
    finally:
        del emu.stubs[SECONDS]
    text = gm.render()
    assert "10% at 56, 50% at 60, 100% at 65" in text and "10% at 60, 50% at 64, 100% at 69" in text


def test_illness_base_chance(emu):
    emu.now = 100_000
    emu.stubs[0x4C5110] = (lambda: 0xFFFFFFFF, 0)           # nobody at home has a catching symptom

    def base(active, career):
        hit = -1
        for r in range(30):
            for k in range(7):
                emu.w8(STATE + 0x5C + k, 0)
            emu.w8(STATE + 0x80, 0)
            emu.w8(STATE + 0x81, 0)
            _groups(emu, active, career)
            emu.plan = {DISEASE_ROLL_SITE: r}
            emu.call(UPDATE_DISEASE, ecx=STATE)
            if any(emu.r8(STATE + 0x5C + k) for k in range(7)) or emu.r8(STATE + 0x80) or emu.r8(STATE + 0x81):
                hit = r
        emu.plan = {}
        return hit + 1

    try:
        assert base([], 5) == 10 and base([0, 1, 2], 5) == 8 and base([0, 1, 2, 3], 5) == 10
        assert base([0, 1, 2], -1) == 10 and base([0, 1, 2, 3], -1) == 5
    finally:
        del emu.stubs[0x4C5110]


# ------------------------------------------------------------------ money
def test_interest_pays_at_most_two_days(emu):
    emu.stubs[SECONDS] = (lambda: emu.now, 0)
    try:
        for days, gained in ((1, 100), (2, 200), (3, 200), (10, 200)):
            emu.uc.mem_write(MONEY, struct.pack("<d", 1000.0))
            emu.uc.mem_write(MONEY + 8, struct.pack("<f", 0.10))
            emu.w32(MONEY + 0xC, 0)
            emu.now = days * 86_400 + 100
            emu.call(UPDATE_INTEREST, ecx=MONEY)
            assert round(emu.f64(MONEY) - 1000.0) == gained
            assert emu.r32(MONEY + 0xC) == days * 86_400       # the skipped days are gone
    finally:
        del emu.stubs[SECONDS]


def test_brokerage_purchases(emu):
    emu.uc.mem_write(MONEY + 8, struct.pack("<f", 0.10))
    rates = []
    for _ in range(7):
        emu.call(SPECIAL_UPGRADE_PURCHASE, (BROKERAGE,))
        rates.append(round(emu.f32(MONEY + 8), 4))
    assert rates == [0.11, 0.01, 0.03, 0.05, 0.07, 0.09, 0.11]
    assert "Buying it again sets interest to 1%" in gm.render()


# ------------------------------------------------------------------ malfunctions while paused
def test_malfunctions_roll_while_paused(emu):
    scene = emu.alloc(0x400)
    emu.w32(scene + 0x14, emu.gs)
    emu.w32(scene + 0x18, emu.alloc(0x100))
    emu.w8(scene + 0x20, 0)
    emu.w8(scene + 0x5C, 1)                                 # no college e-mail check
    emu.w8(0x5A03F8, 1)                                     # skip the web-message block
    rolls = []

    def get_random():
        n = emu.r32(emu.uc.reg_read(UC_X86_REG_ESP) + 4)
        rolls.append(n)
        return 1 if n == 800 else 0
    saved = dict(emu.stubs)
    for addr, pop in ((0x474600, 0), (0x48E1B0, 4), (0x464F70, 0), (0x4A7CF0, 0), (0x499520, 0), (0x49A4E0, 0),
                      (0x456020, 4), (0x4571C0, 0), (0x482AB0, 0), (0x4C6FE0, 4)):
        emu.stubs[addr] = ((lambda: 1000) if addr == 0x474600 else (lambda: 0), pop)
    emu.stubs[GET_RANDOM] = (get_random, 0)
    ends = []

    def stop(uc, addr, _size, _user):
        if addr in (MALFUNCTION_PICKED, STEP_END):
            ends.append(addr)
            uc.emu_stop()
    hook = emu.uc.hook_add(UC_HOOK_CODE, stop)
    try:
        for option in (10, 1009):
            emu.w32(emu.gs + 0x25B18, option)
            emu.w32(emu.gs + 0x28, 0)
            emu.w32(scene + 0x30, 0)
            emu.now = 5000
            rolls.clear()
            ends.clear()
            sp = STACK + STACKSZ - 0x2000
            emu.uc.reg_write(UC_X86_REG_ESP, sp)
            emu.uc.reg_write(UC_X86_REG_EBP, sp + 0x800)
            emu.uc.reg_write(UC_X86_REG_EBX, scene)
            emu.uc.emu_start(SCENE_STEP, SENT, count=2_000_000)
            assert rolls == [800, 14] and ends == [MALFUNCTION_PICKED], option
    finally:
        emu.uc.hook_del(hook)
        emu.stubs = saved
    assert len(range(1, 32768, 800)) == 41                 # 1 in 799.2 per 2-second step


# ------------------------------------------------------------------ the Flea Market
def test_the_flea_market_never_rotates(emu):
    ran = []
    emu.watch = {ROTATE: ran}
    goodies = [emu.r32(GOODIES + 4 * i) for i in range(36)]
    try:
        for now in (100_000, 100_000 + 21_601, 100_000 + 86_400):
            emu.now = now
            count = emu.call(CATEGORY_COUNT, (FLEA_MARKET,), ecx=INVENTORY)
            assert count == 36
            assert [emu.call(CATEGORY_ITEM, (FLEA_MARKET, i), ecx=INVENTORY) for i in range(count)] == goodies
        assert ran == []
        # Control: with the patcher's expanded count answered "not mine" (in emulator memory only), the same call
        # reaches the stock rotation and lists 5 -- so the watch above would have seen it.
        emu.stubs[0x4B9A90] = (lambda: 0xFFFFFFFF, 0)       # VF2GetExpandedFleaMarketCount, cdecl
        emu.w32(INVENTORY + 0x4A0, 0)
        assert emu.call(CATEGORY_COUNT, (FLEA_MARKET,), ecx=INVENTORY) == 5
        assert ran
    finally:
        emu.watch = {}
        emu.stubs.pop(0x4B9A90, None)
    assert "never changes" in next(f.text for f in gm.facts() if f.text.startswith(gm.WITH_PATCHER + "the Flea Market"))


# ------------------------------------------------------------------ the Special Upgrades page
SPECIAL_UPGRADES, SERVICES_LIST = 0x14, 0x56F100


def test_the_special_upgrades_page_sells_the_four_added_upgrades(emu):
    count = emu.call(CATEGORY_COUNT, (SPECIAL_UPGRADES,), ecx=INVENTORY)
    items = [emu.call(CATEGORY_ITEM, (SPECIAL_UPGRADES, i), ecx=INVENTORY) for i in range(count)]
    assert count == 10
    assert items == [0x111, 0x112, 0x113, 0x115, 0x116, 0x114, 0x117, 0x118, 0x119, 0x11A]
    assert items == [emu.r32(SERVICES_LIST + 4 * i) for i in range(10)]
    line = next(f for f in gm.facts() if f.text.startswith(gm.WITH_PATCHER + "the store's Special Upgrades page"))
    assert "10 items in all" in line.text and line.label == gm.VERIFIED_E
