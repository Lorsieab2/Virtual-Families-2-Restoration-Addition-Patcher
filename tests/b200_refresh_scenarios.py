"""Scenarios for the R Refreshes the Store DLL (vf2refresh_b200.dll), run under tests/b200_time_emu.py.

The REAL executable (a B200 or later matrix build, or one built from this branch) and the REAL compiled test
DLL share one emulated address space. Game code that runs for real: ldwEventManager::HandleKey (the key
dispatch, modal boxes included), the folded scene HandleKey, CScrollingStoreScene::SetStoreCategory,
CInventoryManager::GetCategoryItemCount with the patcher's Flea Market hook, MaybeUpdateOutfits,
MaybeUpdateRotatingItems, CVillager::GenCommonBodyType / GenUncommonBodyType / GenRareBodyType, and the
executable's own dormant loader wrapper. Seams (recorded, never real): ldwGameState::GetRandom (a scripted
sequence, with every bound it is asked for recorded), CGameTime::Seconds and GetSecondsFromGameStart (fixed
clocks), theGameState::Get, the page title (theStringManager GetString, ldwTextControl::SetText), the store's
HandleMessage (vtable slot 3, recorded), and the Win32 imports.

Every scenario takes a fresh World and raises AssertionError on a wrong result (the mutation tests rely on
that). Nothing here starts the game, and nothing writes the executable on disk.
"""
from __future__ import annotations

import os
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "tools"))
import b200_refresh_sites as S  # noqa: E402
import gen_b200_refresh_sites as G  # noqa: E402

from b200_time_emu import DLL_BASE, Emu  # noqa: E402

TYPE_CHAR, TYPE_KEYDOWN = S.KEY_TYPE_CHARACTER, S.KEY_TYPE_KEYDOWN
CLOTHING, FLEA, ON_SALE, MENU, FOOD = S.CLOTHING_CATEGORY, S.FLEA_MARKET_CATEGORY, 3, 0x17, 0x0E
OUTFITS = list(range(S.OUTFIT_FIRST_FIELD, S.OUTFIT_LAST_FIELD + 4, 4))
NEXT = S.OUTFIT_NEXT_PICK_FIELD
FLEA_ROWS = list(range(S.FLEA_ROWS_FIELD, S.FLEA_ROWS_FIELD + 20, 4))
FLEA_NEXT = S.FLEA_NEXT_PICK_FIELD
ONE_OFF_GOODS = (0x29, 0x33, 0x10A)        # itemInfo field 4 = 1: one in stock (Reset), every other good -1
INVENTORY_SIZE = 0x4A4
GAME_SECONDS = 500_000                     # CGameTime::Seconds()
REAL_SECONDS = 9_000_000                   # GetSecondsFromGameStart()
TITLE_CONTROL_FIELD = 0x158

DLL_PATH = "C:\\Game\\Virtual Families 2 Patcher Files\\vf2refresh_b200.dll"
EXE_PATH = "C:\\Game\\Virtual Families 2 - B205.exe"

_PROVED = {}


def proved(exe_path):
    """(model of the core variant, derived sites of this executable), cached. The model comes from the core
    variant (VF2_B200_CORE_EXE); exe_path may be any variant."""
    key = str(exe_path)
    if key not in _PROVED:
        core = os.environ.get("VF2_B200_CORE_EXE") or key
        model = G.validate(Path(core).read_bytes())
        _PROVED[key] = (model, G.resolve(G.Exe(Path(key).read_bytes()), model))
    return _PROVED[key]


def goods(exe_path):
    """gGoodiesList (36 items) as the executable has it, read where MaybeUpdateRotatingItems reads it."""
    exe = G.Exe(Path(exe_path).read_bytes())
    body = exe.read(proved(exe_path)[1]["MAYBE_UPDATE_ROTATING"], 0x80)
    j = body.find(b"\x33\xFF\xBB")              # xor edi, edi; mov ebx, offset gGoodiesList
    start = struct.unpack_from("<I", body, j + 3)[0]
    return [exe.u32(start + 4 * i) for i in range(36)]


def flea_section(exe_path):
    import pefile
    pe = pefile.PE(str(exe_path), fast_load=True)
    found = [pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress for s in pe.sections
             if s.Name.rstrip(b"\0") == S.FLEA_FLAG_SECTION.encode()]
    return found[0] if len(found) == 1 else None


class World:
    """One emulated process: an executable + the test DLL, optionally with the plan applied."""

    def __init__(self, exe, dll, delta=0, install=True, native_scan=True, sites=None):
        self.e = Emu(exe, dll, delta)
        self.delta = delta
        self.exe_path = str(exe)
        self.sites = sites if sites is not None else proved(exe)[1]
        if native_scan:
            self._native_scans()
        self.randoms = []              # every bound GetRandom was asked for
        self.script = [7, 19, 3, 11, 2, 5, 1, 0, 9, 4, 6, 8]
        self.messages = []             # (message, param) the store's HandleMessage was given
        self.titles = []               # every page title SetText was given
        self.real_seconds = REAL_SECONDS
        self.flea_va = flea_section(exe)
        self.code_before = self._code()
        self.scene = self.e.alloc(0x200)
        if self.sites:
            self._seams()
            self.inventory = self.s("INVENTORY_MANAGER")
            self.vtable = self.e.alloc(0x40)
            for k in range(16):        # a copy of the store's vtable with HandleMessage (slot 3) recorded
                self.e.w32(self.vtable + 4 * k, self.e.r32(self.store_vtable() + 4 * k))
            self.e.w32(self.vtable + 12, self._handle_message_seam())
            self.e.w32(self.scene, self.vtable)
            self.e.w32(self.scene + TITLE_CONTROL_FIELD, self.e.alloc(0x40))
            for item in goods(exe):    # the goods' stock counts as CInventoryManager::Reset leaves them
                self.e.w32(self.inventory + 4 * item, 1 if item in ONE_OFF_GOODS else 0xFFFFFFFF)
            self.e.w32(self.inventory + FLEA_NEXT, 1)     # Reset: the first listing picks
        self.plan = None
        if install:
            self.install()

    @classmethod
    def bare(cls, exe, dll, delta=0, native_scan=True):
        """A world for an executable the generator may refuse: no proved sites, nothing installed."""
        return cls(exe, dll, delta, install=False, native_scan=native_scan, sites={})

    def s(self, name):
        return self.sites[name] + self.delta

    def store_vtable(self):
        return self.s("STORE_SLOT_HANDLE_KEY") - 4 * S.HANDLE_KEY_VSLOT

    def set_flea(self, value):
        assert self.flea_va is not None, "this executable has no .vf2flea byte"
        self.e.write(self.flea_va + self.delta, bytes([value]))

    # ------------------------------------------------------------------ seams
    def _native_scans(self):
        """The DLL's byte-by-byte ScanPattern and NextDword loops run natively (test_resolver_scans_under_the_
        emulator runs the real ones once); every other line of the resolver runs under unicorn."""
        e = self.e
        scan_at = e.call(e.dll_export("B200Refresh_TestScanAddress"))
        next_at = e.call(e.dll_export("B200Refresh_TestNextDwordAddress"))

        def scan(emu):
            base, size, pat, mask, length, hits = (emu.arg(i) for i in range(6))
            data = emu.read(base, size)
            p, m = emu.read(pat, length), emu.read(mask, length)
            rx = re.compile(b"".join(b"." if w else re.escape(bytes([b])) for b, w in zip(p, m)), re.DOTALL)
            first, count = 0, emu.r32(hits)
            for mt in rx.finditer(data):
                if not count:
                    first = base + mt.start()
                count += 1
                if count >= 2:
                    break
            emu.w32(hits, count)
            return first, 0

        def next_dword(emu):
            start, end, value = emu.arg(0), emu.arg(1), emu.arg(2)
            if start + 4 > end:
                return 0, 0
            data = emu.read(start, end - start)
            want = struct.pack("<I", value)
            j = data.find(want)
            while j >= 0 and j % 4:
                j = data.find(want, j + 1)
            return (start + j if j >= 0 else 0), 0
        e.seam_live(scan_at, scan)
        e.seam_live(next_at, next_dword)

    def _seams(self):
        e = self.e

        def get_random(emu):
            n = emu.arg(0)
            self.randoms.append(n)
            v = self.script[(len(self.randoms) - 1) % len(self.script)]
            return v % n, 0                    # cdecl: the caller pops
        e.seam_live(self.s("GET_RANDOM"), get_random)
        e.seam_live(self.s("GAME_TIME_SECONDS"), lambda emu: (GAME_SECONDS, 0))
        self.game_state = state = e.alloc(0x40)
        e.seam_live(self.s("GAME_STATE_GET"), lambda emu: (state, 0))
        e.seam_live(self.s("GET_SECONDS_FROM_GAME_START"), lambda emu: (self.real_seconds, 0))
        strings = e.alloc(0x40)
        e.seam_live(self.s("STRING_MANAGER_GET"), lambda emu: (strings, 0))
        e.seam_live(self.s("GET_STRING"), lambda emu: (0x5000 + emu.arg(0), 4))

        def set_text(emu):
            self.titles.append(emu.arg(0))
            return 0, 4
        e.seam_live(self.s("TEXT_SET_TEXT"), set_text)

    def _handle_message_seam(self):
        def handle_message(emu):
            self.messages.append((emu.arg(0), emu.arg(1)))
            return 1, 8
        addr = self.e.fake_code(b"\xC3")
        self.e.seam_live(addr, handle_message)
        return addr

    # ------------------------------------------------------------------ image
    def _ranges(self):
        pe = self.e.exe
        return [(self.e.base + s.VirtualAddress, min(s.Misc_VirtualSize, s.SizeOfRawData))
                for s in pe.sections if s.Name.rstrip(b"\0") in (b".text", b".rdata")]

    def _code(self):
        return [(a, self.e.read(a, n)) for a, n in self._ranges()]

    def changed_code(self):
        out = set()
        for (a, was) in self.code_before:
            now = self.e.read(a, len(was))
            if now != was:
                out.update(a + i for i in range(len(was)) if now[i] != was[i])
        return out

    def status(self):
        a = self.e.dll_export("B200Refresh_Status")
        keys = ("magic", "version", "requested", "resolved", "installed", "writeMask", "redraws", "passed",
                "fleaRedraws", "fleaFlag")
        return {k: self.e.r32(a + 4 * i) for i, k in enumerate(keys)}

    # ------------------------------------------------------------------ plan
    def test_plan(self, enabled=True):
        out = self.e.alloc(0x100)
        status = self.e.call(self.e.dll_export("B200Refresh_TestPlan"), (1 if enabled else 0, out))
        status = struct.unpack("<i", struct.pack("<I", status & 0xFFFFFFFF))[0]
        writes = []
        for i in range(self.e.r32(out + 4)):
            va, ln, data, b0, b1 = [self.e.r32(out + 8 + i * 20 + 4 * k) for k in range(5)]
            writes.append({"va": va, "len": ln, "data": bool(data), "bytes": struct.pack("<II", b0, b1)[:ln]})
        return status, writes

    def install(self):
        status, writes = self.test_plan(True)
        assert status == 1, f"the plan was refused (status {status})"
        for w in writes:
            self.e.write(w["va"], w["bytes"])
        self.plan = writes
        return writes

    # ------------------------------------------------------------------ the store
    def page(self, category):
        """Open a store page with the game's own SetStoreCategory (it writes the field the DLL reads)."""
        self.e.call(self.s("SET_STORE_CATEGORY"), (category,), ecx=self.scene)
        assert self.e.r32(self.scene + S.STORE_CATEGORY_FIELD) == category

    def clear(self):
        self.randoms.clear()
        self.titles.clear()

    def item_count(self):
        return self.e.rs32(self.scene + 0xD8)

    def inventory_bytes(self):
        return self.e.read(self.inventory, INVENTORY_SIZE)

    def outfits(self):
        return [self.e.r32(self.inventory + f) for f in OUTFITS]

    def set_outfits(self, values, next_pick):
        for f, v in zip(OUTFITS, values):
            self.e.w32(self.inventory + f, v)
        self.e.w32(self.inventory + NEXT, next_pick)

    def flea_rows(self):
        return [self.e.r32(self.inventory + f) for f in FLEA_ROWS]

    def _sync_slot(self):
        """The scene's vtable is a copy of the store's (with HandleMessage recorded): give it the store's live
        HandleKey slot, whatever the DLL has made it."""
        live = self.e.r32(self.store_vtable() + 4 * S.HANDLE_KEY_VSLOT)
        self.e.w32(self.vtable + 4 * S.HANDLE_KEY_VSLOT, live)
        return live

    def key(self, type_, code, sym=0):
        """A key through the store's own vtable slot (what ldwEventManager::HandleKey calls)."""
        fn = self._sync_slot()
        return self.e.call(fn, (type_, code, sym), ecx=self.scene) & 0xFF

    def dispatch(self, type_, code, sym=0, modal_box=False):
        """A key through the game's own ldwEventManager::HandleKey with the store subscribed, and (modal_box)
        a store box subscribed in front of it and made modal, as ldwDialog::DoModal(scene, false) does."""
        e = self.e
        self._sync_slot()
        box_seen = []
        store_entry = e.alloc(16)
        e.write(store_entry, struct.pack("<IIII", self.scene, 0xF, 0, 0))
        head = store_entry
        if modal_box:
            box_vt = e.alloc(0x40)
            box_hk = e.fake_code(b"\xC3")

            def box_key(emu):
                box_seen.append((emu.arg(0), emu.arg(1)))
                return 0, 12                   # the box does not handle R: false
            e.seam_live(box_hk, box_key)
            e.w32(box_vt + 8, box_hk)
            box = e.alloc(0x40)
            e.w32(box, box_vt)
            box_entry = e.alloc(16)
            e.write(box_entry, struct.pack("<IIII", box, 0xF, 1, store_entry))
            head = box_entry
        impl = e.alloc(16)
        e.w32(impl, head)
        manager = e.alloc(16)
        e.w32(manager, impl)
        e.call(self.s("EVENT_MANAGER_HANDLE_KEY"), (type_, code, sym), ecx=manager)
        return box_seen


# ====================================================================== installed scenarios
def _changed(before, after):
    return {i for i in range(INVENTORY_SIZE) if before[i] != after[i]}


def _only_outfits_changed(w, before):
    allowed = {f + k for f in OUTFITS + [NEXT] for k in range(4)}
    changed = _changed(before, w.inventory_bytes())
    assert changed <= allowed, f"the redraw wrote outside the six outfit rows and their clock: {sorted(changed)}"


def scenario_r_redraws_the_clothing_page(w):
    """R on the Clothing and Hairstyles page: the game's own forced draw, the game's own odds, the 4-hour clock."""
    w.set_outfits([1, 33, 45, 2, 34, 46], GAME_SECONDS + 9000)      # the timed pick is not due
    w.page(CLOTHING)
    assert w.outfits() == [1, 33, 45, 2, 34, 46], "listing the page before the 4 hours does not pick"
    count = w.item_count()
    w.clear()
    before = w.inventory_bytes()
    assert w.key(TYPE_CHAR, ord("r")) == 1, "R on the clothing page is handled"
    assert w.randoms == [0x20, 0x20, 0x0C, 0x0C, 0x06, 0x06], f"not the game's own draw: {w.randoms}"
    s = w.script
    assert w.outfits() == [s[0] % 32, 32 + s[2] % 12, 44 + s[4] % 6, s[1] % 32, 32 + s[3] % 12, 44 + s[5] % 6]
    assert w.e.r32(w.inventory + NEXT) == GAME_SECONDS + S.OUTFIT_REPICK_DELAY
    _only_outfits_changed(w, before)
    assert w.messages == [] and w.titles == [] and w.item_count() == count, "the page is not listed again"
    assert w.status()["redraws"] == 1


def scenario_shift_r_is_the_same(w):
    w.set_outfits([0] * 6, GAME_SECONDS + 9000)
    w.page(CLOTHING)
    w.clear()
    assert w.key(TYPE_CHAR, ord("R")) == 1
    assert len(w.randoms) == 6 and w.e.r32(w.inventory + NEXT) == GAME_SECONDS + S.OUTFIT_REPICK_DELAY


def scenario_every_press_draws_again(w):
    w.page(CLOTHING)
    w.clear()
    seen = []
    for _ in range(3):
        w.key(TYPE_CHAR, ord("r"))
        seen.append(tuple(w.outfits()))
    assert len(w.randoms) == 18 and w.status()["redraws"] == 3
    for row in seen:
        assert all(0 <= v < 32 for v in (row[0], row[3]))
        assert all(32 <= v < 44 for v in (row[1], row[4]))
        assert all(44 <= v < 50 for v in (row[2], row[5]))


def scenario_the_odds_reach_every_outfit(w):
    """The bounds are the game's: the highest value each draw can give is 31, 43 and 49."""
    w.page(CLOTHING)
    hi = []
    for top in (31, 11, 5):
        w.script = [top]
        w.clear()
        w.key(TYPE_CHAR, ord("r"))
        hi.append(w.outfits())
    assert hi[0][0] == 31 and hi[0][3] == 31 and hi[1][1] == 43 and hi[1][4] == 43 and hi[2][2] == 49


def scenario_all_36_flea_market_goods_are_left_alone(w):
    """R on the Flea Market page while all 36 goods are listed (the .vf2flea byte 1, or an executable without
    it): nothing is drawn or written, and the game's own handler gets the key."""
    if w.flea_va is not None:
        w.set_flea(1)
    w.page(FLEA)
    assert w.item_count() == 36, "the patched Flea Market lists all 36 goods"
    w.clear()
    before = w.inventory_bytes()
    assert w.key(TYPE_CHAR, ord("r")) == 0
    assert w.randoms == [] and w.inventory_bytes() == before and w.messages == [] and w.titles == []
    assert w.item_count() == 36
    st = w.status()
    assert st["passed"] == 1 and st["redraws"] == 0 and st["fleaRedraws"] == 0
    assert st["fleaFlag"] == (1 if w.flea_va is not None else 0)


def scenario_other_pages_are_left_alone(w):
    for cat in (MENU, ON_SALE, FOOD, 0, 0x10, 0x16):
        w.page(cat)
        w.clear()
        before = w.inventory_bytes()
        assert w.key(TYPE_CHAR, ord("r")) == 0, cat
        assert w.randoms == [] and w.inventory_bytes() == before and w.titles == [], cat
    assert w.status()["redraws"] == 0 and w.status()["fleaRedraws"] == 0


def scenario_other_keys_are_the_games(w):
    """Every other key on the clothing page is the game's own: Esc still leaves, the rest do nothing."""
    w.page(CLOTHING)
    w.clear()
    before = w.inventory_bytes()
    for t, c in ((TYPE_CHAR, ord("t")), (TYPE_CHAR, ord("e")), (TYPE_CHAR, ord(" ")), (TYPE_KEYDOWN, ord("r")),
                 (TYPE_KEYDOWN, ord("R")), (7, ord("r")), (TYPE_CHAR, 0x3E8)):
        assert w.key(t, c) == 0, (t, c)
    assert w.randoms == [] and w.inventory_bytes() == before and w.messages == []
    assert w.key(TYPE_KEYDOWN, S.KEY_ESC) == 1
    assert w.messages == [(8, 1)], "Esc no longer goes back to the house"


def scenario_a_box_open_stops_r(w):
    """The game's own dispatch: with a store box open (modal) R never reaches the store; with none, it does."""
    w.page(CLOTHING)
    w.clear()
    before = w.inventory_bytes()
    seen = w.dispatch(TYPE_CHAR, ord("r"), modal_box=True)
    assert seen == [(TYPE_CHAR, ord("r"))], "the box gets the key first"
    assert w.randoms == [] and w.inventory_bytes() == before, "R reached the store through a modal box"
    w.dispatch(TYPE_CHAR, ord("r"))
    assert len(w.randoms) == 6 and w.status()["redraws"] == 1


def scenario_only_the_store_slot_is_written(w):
    """One write: the store vtable's HandleKey slot. The folded HandleKey and the other scenes' slots stay."""
    assert len(w.plan) == 1 and w.plan[0]["data"] and w.plan[0]["len"] == 4
    slot = w.s("STORE_SLOT_HANDLE_KEY")
    assert w.plan[0]["va"] == slot
    assert DLL_BASE <= struct.unpack("<I", w.plan[0]["bytes"])[0] < DLL_BASE + 0x100000
    assert w.changed_code() == {slot + k for k in range(4)}
    hk = w.s("STORE_HANDLE_KEY")
    others = []
    for _name, sva, raw, _ch, _vs in G.Exe(Path(w.exe_path).read_bytes()).read_only_data():
        want = struct.pack("<I", hk - w.delta)
        j = raw.find(want)
        while j >= 0:
            if j % 4 == 0:
                others.append(sva + j + w.delta)
            j = raw.find(want, j + 1)
    assert slot in others and len(others) >= 2, "the HandleKey is shared, so the function must not be touched"
    for other in others:
        if other != slot:
            assert w.e.r32(other) == hk, "another scene's HandleKey was changed"


ALL = [scenario_r_redraws_the_clothing_page, scenario_shift_r_is_the_same, scenario_every_press_draws_again,
       scenario_the_odds_reach_every_outfit, scenario_all_36_flea_market_goods_are_left_alone,
       scenario_other_pages_are_left_alone, scenario_other_keys_are_the_games, scenario_a_box_open_stops_r,
       scenario_only_the_store_slot_is_written]


# ====================================================================== the stock Flea Market (.vf2flea byte 0)
def scenario_stock_flea_market_r_picks_five_new_goods(w):
    """All 36 Flea Market goods off: the stock 5 goods; R makes the game's own pick happen now."""
    w.set_flea(0)
    pool = goods(w.exe_path)
    w.page(FLEA)
    assert w.item_count() == 5 and w.randoms == [36] * 36, "the first listing picks (the game's own shuffle)"
    first = w.flea_rows()
    assert all(g in pool for g in first) and len(set(first)) == 5
    assert w.e.r32(w.inventory + FLEA_NEXT) == REAL_SECONDS + S.FLEA_REPICK_DELAY
    w.clear()
    w.page(FLEA)                                   # listed again before 6 real hours: the same 5, no pick
    assert w.randoms == [] and w.flea_rows() == first
    w.real_seconds += 60
    w.script = [5, 17, 2, 30, 11, 8, 1, 23, 0, 14]
    w.clear()
    before = w.inventory_bytes()
    assert w.key(TYPE_CHAR, ord("r")) == 1
    assert w.randoms == [36] * 36, "the game's own shuffle over the 36 goods"
    after = w.flea_rows()
    assert after != first and all(g in pool for g in after) and len(set(after)) == 5
    assert w.e.r32(w.inventory + S.FLEA_COUNT_FIELD) == 5 and w.item_count() == 5
    assert w.e.r32(w.inventory + FLEA_NEXT) == w.real_seconds + S.FLEA_REPICK_DELAY
    assert w.titles, "the store listed the page again (its own SetStoreCategory)"
    allowed = {f + k for f in FLEA_ROWS + [S.FLEA_COUNT_FIELD, FLEA_NEXT] for k in range(4)}
    allowed |= {4 * g + k for g in pool for k in range(4)}          # the stock counts the pick itself sets
    changed = _changed(before, w.inventory_bytes())
    assert changed <= allowed, f"wrote outside the Flea Market: {sorted(changed)}"
    for f in OUTFITS + [NEXT]:
        assert w.e.read(w.inventory + f, 4) == before[f:f + 4], "the outfits were touched"
    st = w.status()
    assert st["fleaRedraws"] == 1 and st["redraws"] == 0 and st["fleaFlag"] == 1


def scenario_stock_flea_market_counts_are_the_games(w):
    """The pick sets the stock counts as the game does: every pooled good 1, a bought one-off stays 0."""
    w.set_flea(0)
    w.e.w32(w.inventory + 4 * 0x29, 0)             # a one-off already bought
    w.page(FLEA)
    w.real_seconds += 60
    w.key(TYPE_CHAR, ord("r"))
    for g in goods(w.exe_path):
        want = 0 if g == 0x29 else 1
        assert w.e.rs32(w.inventory + 4 * g) == want, hex(g)
    assert 0x29 not in w.flea_rows()


def scenario_stock_flea_market_clock_at_zero_changes_nothing(w):
    """With the real clock still 0 no pick can be due: the old next-pick time is put back, nothing is drawn."""
    w.set_flea(0)
    w.page(FLEA)
    rows = w.flea_rows()
    w.real_seconds = 0
    w.e.w32(w.inventory + FLEA_NEXT, 777)
    w.clear()
    before = w.inventory_bytes()
    w.key(TYPE_CHAR, ord("r"))
    assert w.randoms == [] and w.flea_rows() == rows and w.inventory_bytes() == before


def scenario_stock_flea_market_clothing_r_is_unchanged(w):
    """The byte changes only the Flea Market: R on the clothing page draws the outfits the same way."""
    w.set_flea(0)
    w.page(CLOTHING)
    w.clear()
    before = w.inventory_bytes()
    assert w.key(TYPE_CHAR, ord("r")) == 1 and w.randoms == [0x20, 0x20, 0x0C, 0x0C, 0x06, 0x06]
    _only_outfits_changed(w, before)


def scenario_byte_one_lists_all_36_again(w):
    """The same executable with the byte back at 1: all 36 goods, and R does nothing on the Flea Market."""
    w.set_flea(0)
    w.page(FLEA)
    assert w.item_count() == 5
    w.set_flea(1)
    w.clear()
    w.page(FLEA)
    assert w.item_count() == 36 and w.randoms == []
    before = w.inventory_bytes()
    assert w.key(TYPE_CHAR, ord("r")) == 0 and w.inventory_bytes() == before and w.randoms == []


FLEA_STOCK = [scenario_stock_flea_market_r_picks_five_new_goods, scenario_stock_flea_market_counts_are_the_games,
              scenario_stock_flea_market_clock_at_zero_changes_nothing,
              scenario_stock_flea_market_clothing_r_is_unchanged, scenario_byte_one_lists_all_36_again]


# ====================================================================== startup (nothing installed first)
def _virtual_protect(emu):
    emu.w32(emu.arg(3), 0x02)
    return 1, 16


def _startup(w, ini, module_path=DLL_PATH):
    e = w.e
    log = []

    def module_name(emu):
        e.write(emu.arg(1), module_path.encode("utf-16-le") + b"\0\0")
        return len(module_path), 12

    def ini_read(emu):
        log.append((emu.wstr(emu.arg(0)), emu.wstr(emu.arg(1)), emu.wstr(emu.arg(3))))
        return ini, 16
    e.imports.update({"GetModuleFileNameW": module_name, "GetPrivateProfileIntW": ini_read,
                      "VirtualProtect": _virtual_protect, "FlushInstructionCache": lambda emu: (1, 12),
                      "GetCurrentProcess": lambda emu: (0xFFFFFFFF, 0)})
    e.call(e.dll_export("B200Refresh_TestSetModule"), (DLL_BASE,))
    e.call(e.dll_export("B200Refresh_Startup"))
    return log


def scenario_setting_off_writes_nothing(w):
    """vf2refresh.ini RefreshKey=0 (or missing): nothing written; R on the clothing page is the game's own."""
    log = _startup(w, 0)
    assert log == [("Patches", "RefreshKey", "C:\\Game\\Virtual Families 2 Patcher Files\\vf2refresh.ini")]
    st = w.status()
    assert st["requested"] == 0 and st["installed"] == 0 and st["writeMask"] == 0
    assert not w.changed_code()
    w.page(CLOTHING)
    w.clear()
    before = w.inventory_bytes()
    assert w.key(TYPE_CHAR, ord("r")) == 0
    assert w.randoms == [] and w.inventory_bytes() == before


def scenario_setting_on_installs(w):
    _startup(w, 1)
    st = w.status()
    assert st["magic"] == S.STATUS_MAGIC and st["requested"] == 1 and st["resolved"] == 1
    assert st["installed"] == 1 and st["writeMask"] == 1
    assert w.changed_code() == {w.s("STORE_SLOT_HANDLE_KEY") + k for k in range(4)}
    w.page(CLOTHING)
    w.clear()
    assert w.key(TYPE_CHAR, ord("r")) == 1 and len(w.randoms) == 6


OFF = [scenario_setting_off_writes_nothing, scenario_setting_on_installs]


# ====================================================================== the executable's own loader
def section_va(exe_path, name):
    import pefile
    pe = pefile.PE(str(exe_path), fast_load=True)
    found = [pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress for s in pe.sections if s.Name.rstrip(b"\0") == name]
    assert len(found) == 1, f"the executable has no {name!r} section"
    return found[0]


def run_loader(exe, dll, delta, flag, ini, others=0, dll_present=True):
    """The executable's REAL loader wrapper (theGame::Init's first call) with this DLL as the one it loads for
    R Refreshes the Store; the other companion DLLs' bytes are `others` and their DLLs absent. flag None leaves
    the .vf2rfsh byte as the file has it. Returns (world, wrapper result, game state, calls log)."""
    import b200_time_scenarios as T
    w = World(exe, dll, delta, install=False)
    e = w.e
    _flag, _call, wrapper = T.loader_sites(exe)
    log = []
    if flag is not None:
        e.write(section_va(exe, b".vf2rfsh") + delta, bytes([flag]))
    for name in (b".vf2time", b".vf2kids", b".vf2hist"):
        e.write(section_va(exe, name) + delta, bytes([others]))
    state = w.game_state               # theGameState::Get() is a seam here (MaybeUpdateRotatingItems calls it too)

    def exe_module_name(emu):
        log.append("exe:GetModuleFileNameW")
        e.write(emu.arg(1), EXE_PATH.encode("utf-16-le") + b"\0\0")
        return len(EXE_PATH), 12

    def exe_load(emu):
        path = emu.wstr(emu.arg(0))
        log.append("exe:LoadLibraryW " + path)
        return (DLL_BASE if path == DLL_PATH and dll_present else 0), 4

    def exe_proc(emu):
        name = emu.cstr(emu.arg(1))
        log.append("exe:GetProcAddress " + name)
        return (e.dll_export(S.STARTUP) if name == S.STARTUP else 0), 8
    e.bind_exe_imports({"GetModuleFileNameW": exe_module_name, "LoadLibraryW": exe_load,
                        "GetProcAddress": exe_proc})

    def dll_module_name(emu):
        e.write(emu.arg(1), DLL_PATH.encode("utf-16-le") + b"\0\0")
        return len(DLL_PATH), 12

    def dll_ini(emu):
        log.append("dll:GetPrivateProfileIntW " + emu.wstr(emu.arg(1)) + " " + emu.wstr(emu.arg(3)))
        return ini, 16
    e.imports.update({"GetModuleFileNameW": dll_module_name, "GetPrivateProfileIntW": dll_ini,
                      "VirtualProtect": _virtual_protect, "FlushInstructionCache": lambda emu: (1, 12),
                      "GetCurrentProcess": lambda emu: (0xFFFFFFFF, 0)})
    w.code_before = w._code()
    e.call(e.dll_export("B200Refresh_TestSetModule"), (DLL_BASE,))
    result = e.call(wrapper + delta, ())
    return w, result, state, log


def scenario_loader_cases(exe, dll, delta):
    """The dormant loader: byte 0 never loads the DLL; byte 1 loads it once, after the other companion DLLs;
    the DLL installs only when its ini says 1; then R redraws the clothing page."""
    for flag, ini, others, present, installs in ((0, 1, 0, True, False), (1, 0, 0, True, False),
                                                  (1, 1, 0, False, False), (1, 1, 0, True, True),
                                                  (1, 1, 1, True, True), (0, 1, 1, True, False)):
        w, result, state, log = run_loader(exe, dll, delta, flag, ini, others, present)
        assert result == state, "the wrapper must return theGameState::Get()'s result"
        loads = [x for x in log if x.startswith("exe:LoadLibraryW")]
        assert (loads[-1:] == [f"exe:LoadLibraryW {DLL_PATH}"]) == bool(flag), (flag, log)
        assert len(loads) == 3 * others + (1 if flag else 0), (flag, others, log)
        st = w.status()
        if not installs:
            assert not w.changed_code() and st["installed"] == 0
            continue
        assert st["installed"] == 1 and w.changed_code() == {w.s("STORE_SLOT_HANDLE_KEY") + k for k in range(4)}
        w.page(CLOTHING)
        w.clear()
        assert w.key(TYPE_CHAR, ord("r")) == 1 and len(w.randoms) == 6
    import b200_time_scenarios as T
    w, _result, state, log = run_loader(exe, dll, delta, 1, 1)
    assert w.e.call(T.loader_sites(exe)[2] + delta, ()) == state
    assert len([x for x in log if x.startswith("exe:LoadLibraryW")]) == 1, "the DLL is loaded once"
