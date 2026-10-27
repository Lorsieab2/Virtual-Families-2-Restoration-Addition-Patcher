"""The Game Mechanics window's "Unpatched game:" lines, re-run on the STOCK executable's own code (unicorn).

The stock executable is the patcher's vanilla payload, `work/vanilla_runtime_payload/Virtual Families 2.exe`
(gitignored; sha256 SHA256_PREFIX...), or VF2_STOCK_EXE; skipped when absent, and a different build is skipped,
never guessed.  The routines run as linked; only the clock readers, the theGameState singleton getter and the
store title's text calls are answered by Python.  Nothing starts the game and nothing on disk is written.

The stock executable is a different compile of the same game (no symbols): its addresses were found by matching
each B200 routine's constants and call shape (docs/game-mechanics/spec.md section 22).  Each test checks the bytes
it relies on first, then that src/vf2_game_mechanics.py says what the run shows.
"""
from __future__ import annotations

import faulthandler
import hashlib
import os
import struct
import sys
from pathlib import Path

import pytest

faulthandler.disable()                     # unicorn handles its own first-chance faults (see the B200 test)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_game_mechanics as gm  # noqa: E402

pefile = pytest.importorskip("pefile")
unicorn = pytest.importorskip("unicorn")
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc  # noqa: E402
from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_EAX, UC_X86_REG_EBP,  # noqa: E402
                               UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ES, UC_X86_REG_ESP, UC_X86_REG_FS,
                               UC_X86_REG_GDTR, UC_X86_REG_SS)

SHA256_PREFIX = "1582d9e84e1c32f5"
STOCK_EXE = os.environ.get("VF2_STOCK_EXE") or str(ROOT / "work" / "vanilla_runtime_payload" / "Virtual Families 2.exe")

BASE = 0x400000
HEAP, HEAPSZ = 0x20000000, 0x2000000
STACK, STACKSZ = 0x30000000, 0x100000
SENT, TEB, GDT = 0x3F000000, 0x3E000000, 0x3D000000

# stock addresses
RAND = 0x4C4BB8                            # CRT rand (the MSVC LCG)
GAME_STATE_GET = 0x42AC20                  # theGameState::Get
SECONDS_FROM_GAME_START = 0x403FF0         # ldwGameState::GetSecondsFromGameStart (real seconds)
GAME_SECONDS = 0x427920                    # CGameTime::Seconds
INVENTORY = 0xAB3528                       # the CInventoryManager
RESET = 0x4BA8F0                           # CInventoryManager::Reset (a new family)
CATEGORY_COUNT, CATEGORY_ITEM = 0x4BB0A0, 0x4BAA50
ROTATE = 0x4BA710                          # MaybeUpdateRotatingItems
GOODIES = 0x556F98                         # gGoodiesList, 36 items
SERVICES = 0x556E3C                        # the Special Upgrades list
SET_STORE_CATEGORY = 0x432050              # CScrollingStoreScene::SetStoreCategory
STORE_MENU = 0x5346E0                      # the store menu: 16-byte rows (image, string, 0, category)
FLEA_MARKET, SPECIAL_UPGRADES, STORE_MENU_CATEGORY = 15, 0x14, 0x17
TITLE_STUBS = {0x449610: 0, 0x448E90: 4, 0x40E1D0: 4}  # string manager, GetString, SetText: callee -> bytes popped


def stock_exe() -> Path:
    path = Path(STOCK_EXE)
    if not path.is_file():
        pytest.skip("the stock executable (work/vanilla_runtime_payload or VF2_STOCK_EXE) is not present")
    if not hashlib.sha256(path.read_bytes()).hexdigest().startswith(SHA256_PREFIX):
        pytest.skip("a different stock build: these addresses are sha256 1582d9e8's")
    return path


class Emu:
    def __init__(self, exe: Path):
        pe = pefile.PE(str(exe), fast_load=True)
        self.pe = pe
        self.image = pe.get_memory_mapped_image()
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
        self.now = 1000
        self.seed = 1
        self.gs = self.alloc(0x26100)
        self.stubs = {RAND: (self._rand, 0), GAME_STATE_GET: (lambda: self.gs, 0),
                      SECONDS_FROM_GAME_START: (lambda: self.now, 0), GAME_SECONDS: (lambda: self.now, 0)}
        for addr, pop in TITLE_STUBS.items():
            self.stubs[addr] = (lambda: 0, pop)
        self.entered: list[int] = []
        uc.hook_add(UC_HOOK_CODE, self._code)

    def alloc(self, n):
        a = self.heap
        self.heap += (n + 15) & ~15
        return a

    def r32(self, a):
        return struct.unpack("<i", self.uc.mem_read(a, 4))[0]

    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack("<I", v & 0xFFFFFFFF))

    def file_u32(self, va):
        return struct.unpack_from("<I", self.image, va - BASE)[0]

    def file_bytes(self, va, n):
        return bytes(self.image[va - BASE:va - BASE + n])

    def _rand(self):                       # the MSVC LCG, as the game's own rand
        self.seed = (self.seed * 214013 + 2531011) & 0xFFFFFFFF
        return (self.seed >> 16) & 0x7FFF

    def _code(self, uc, addr, size, _user):
        if addr == ROTATE:
            self.entered.append(addr)
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
        self.uc.emu_start(addr, SENT, count=20_000_000)
        return self.uc.reg_read(UC_X86_REG_EAX)


@pytest.fixture(scope="module")
def emu():
    return Emu(stock_exe())


def _rel32_target(e, call_va):
    assert e.file_bytes(call_va, 1) == b"\xE8"
    return (call_va + 5 + struct.unpack("<i", e.file_bytes(call_va + 1, 4))[0]) & 0xFFFFFFFF


def test_the_flea_market_is_reached_from_the_store_menu(emu):
    """The live path: theMainScene opens the store on its menu (category 0x17); a click on a menu row in
    CScrollingStoreScene::HandleMouse 0x4340E0 reads that row's category from STORE_MENU and calls SetStoreCategory,
    which asks GetCategoryItemCount for it; for category 15 that runs the rotation 0x4BA710."""
    e = emu
    assert e.file_bytes(0x441EAB, 2) == b"\x6A\x17" and _rel32_target(e, 0x441EB4) == SET_STORE_CATEGORY
    assert e.file_bytes(0x434227, 3) == b"\x83\xF8\x17"                       # cmp eax, 0x17 (the menu)
    assert e.file_bytes(0x4345CA, 6) == b"\x8B\x8F" + struct.pack("<I", STORE_MENU + 0xC)
    assert _rel32_target(e, 0x4345D3) == SET_STORE_CATEGORY
    assert _rel32_target(e, 0x43206C) == CATEGORY_COUNT
    rows = [tuple(e.file_u32(STORE_MENU + 16 * i + 4 * k) for k in (1, 3)) for i in range(8)]
    assert rows[1] == (0x487, FLEA_MARKET)                                    # "Flea Market"
    assert (0x481, SPECIAL_UPGRADES) in rows                                  # "Special Upgrades"
    table = 0x4BB17C                                                          # GetCategoryItemCount's jump table
    assert e.file_bytes(0x4BB0B0, 7) == b"\xFF\x24\x85" + struct.pack("<I", table)
    case = e.file_u32(table + 4 * FLEA_MARKET)
    assert _rel32_target(e, case) == ROTATE


def test_the_unpatched_flea_market_shows_five_and_changes_after_six_real_hours(emu):
    e = emu
    e.now = 1000
    e.call(RESET, ecx=INVENTORY)
    scene = e.alloc(0x400)
    goodies = [e.r32(GOODIES + 4 * i) for i in range(36)]
    shown = {}
    start = 100_000
    for label, now in (("+0", start), ("+6 h", start + 21_600), ("+6 h 1 s", start + 21_601), ("+24 h", start + 86_400)):
        e.now = now
        e.entered.clear()
        e.call(SET_STORE_CATEGORY, (FLEA_MARKET,), ecx=scene)
        assert e.entered == [ROTATE], label
        count = e.r32(scene + 0xD8)
        assert count == 5, label
        shown[label] = [e.call(CATEGORY_ITEM, (FLEA_MARKET, i), ecx=INVENTORY) for i in range(count)]
        assert all(item in goodies for item in shown[label]) and len(set(shown[label])) == 5, label
        if label != "+6 h":
            assert e.r32(INVENTORY + 0x4A0) == now + 21_600, label            # next change: 6 real hours on
    assert shown["+6 h"] == shown["+0"]                                       # not yet: "more than"
    assert shown["+6 h 1 s"] != shown["+0"]
    assert shown["+24 h"] != shown["+6 h 1 s"]
    patched = next(f for f in gm.facts() if f.text.startswith(gm.WITH_PATCHER + "the Flea Market"))
    unpatched = next(f for f in gm.facts() if f.text.startswith(gm.UNPATCHED + "the Flea Market"))
    assert "never changes" in patched.text
    assert "5 of its 36 goods, picked at random, and changes them every 6 hours of real time" in unpatched.text
    assert unpatched.label == gm.VERIFIED_E


def test_the_unpatched_special_upgrades_page_has_six_items(emu):
    e = emu
    count = e.call(CATEGORY_COUNT, (SPECIAL_UPGRADES,), ecx=INVENTORY)
    items = [e.call(CATEGORY_ITEM, (SPECIAL_UPGRADES, i), ecx=INVENTORY) for i in range(count)]
    assert count == 6
    assert items == [0x111, 0x112, 0x113, 0x115, 0x116, 0x114] == [e.r32(SERVICES + 4 * i) for i in range(6)]
    assert not {0x117, 0x118, 0x119, 0x11A} & set(items)    # Brokerage Account, Food Club, Health Plan, Lucky Rock
    line = next(f for f in gm.facts() if f.text.startswith(gm.UNPATCHED + "the Special Upgrades page"))
    assert "has 6 items and sells none of" in line.text and line.label == gm.VERIFIED_E
