"""Scenarios for the B200 Time Controls DLL, run under tests/b200_time_emu.py.

Every function takes a fresh World and raises AssertionError on a wrong result
(the mutation tests rely on that: a mutated DLL must make at least one scenario
raise). Addresses given as 0x4xxxxx..0x7xxxxx are B200 link-time VAs; World.a()
rebases them for the executable's load delta.
"""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

from b200_time_emu import EmuError, Emu, SENTINEL, TEB_BASE, u32
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
                               UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)

# ---- B200 link-time addresses the scenarios drive (all proved by runtime/b200_time_sites.py)
VM = 0x706F90
GAME_TIME = 0x683038
GAME_STATE_PTR = 0x685A88
SPEED_FIELD = 0x25B18
OPTIONS_VTABLE = 0x5006D8
GAME_STATE_VTABLE = 0x4FC554
TIMEFLOW = 0x4C4C30
SET_SPEED = 0x468B80
SPACE_TOGGLE = 0x49EAC8       # the Space key's pause toggle, entered with edi = the scene
NATIVE_HANDLE_MESSAGE = 0x4A6940
NATIVE_SAVE = 0x49AA00
NATIVE_LOAD = 0x499DC0
CTOR_TAIL = 0x4A61F9          # theOptionsDialog constructor, from AddControl(last check box) to ret 8
TEXT_COLOUR = 0x58BEAC

# ---- dialog control ids of the DLL's own Windows dialog
ID_STATUS, ID_PAUSE, ID_RESUME, ID_SLOW, ID_NORMAL, ID_FAST, ID_X5, ID_X10, ID_WARP = range(560, 569)
WM_INITDIALOG, WM_COMMAND = 0x110, 0x111


class World:
    """One emulated process: the B200 core exe + the test DLL, optionally with the plan applied."""

    def __init__(self, exe, dll, delta=0, install=True):
        self.e = Emu(exe, dll, delta)
        self.delta = delta
        self.now = 1_000_000
        self.native_handle = []        # (message, param) the ORIGINAL HandleMessage was given
        self.native_handle_result = 0
        self.native_saves = []         # (slot, speed field, CGameTime speed) at each original Save
        self.native_loads = []
        self.load_sets_field = None    # the speed field a Load restores from the "file"
        self.load_result = 1
        self.button_ctors = []
        self.button_texts = []
        self.added = []
        self.plan = None
        self.orig_code = [(addr, self.e.read(addr, size)) for addr, size in self._code_ranges()]
        self.text_snapshot = self._snapshot()
        self._seams()
        # the game's state object and CGameTime
        self.state = self.e.alloc(0x26400)
        self.e.w32(self.a(GAME_STATE_PTR), self.state)
        self.set_gametime(10)
        self.e.w32(self.state + SPEED_FIELD, 10)
        if install:
            self.install()

    def a(self, va):
        return self.e.a(va)

    # ------------------------------------------------------------------ image snapshots
    def _code_ranges(self):
        pe = self.e.exe
        return [(self.e.base + s.VirtualAddress, min(s.Misc_VirtualSize, s.SizeOfRawData))
                for s in pe.sections if s.Name.rstrip(b"\0") in (b".text", b".rdata")]

    def _snapshot(self):
        h = hashlib.sha256()
        for addr, size in self._code_ranges():
            h.update(self.e.read(addr, size))
        return h.hexdigest()

    def code_unchanged(self):
        return self._snapshot() == self.text_snapshot

    def changed_code_bytes(self):
        out = set()
        for (addr, was) in self.orig_code:
            now = self.e.read(addr, len(was))
            if now != was:
                out.update(addr + i for i in range(len(was)) if now[i] != was[i])
        return out

    # ------------------------------------------------------------------ plan
    def test_plan(self, enabled=True, image_base=None):
        out = self.e.alloc(0x400)
        base = self.e.base if image_base is None else image_base
        status = self.e.call(self.e.dll_export("B200Time_TestPlan"), (base, 1 if enabled else 0, out))
        status = struct.unpack("<i", struct.pack("<I", status & 0xFFFFFFFF))[0]
        count = self.e.r32(out + 4)
        writes = []
        for i in range(count):
            va, ln, data, b0, b1 = [self.e.r32(out + 8 + i * 20 + 4 * k) for k in range(5)]
            writes.append({"va": va, "len": ln, "data": bool(data),
                           "bytes": (struct.pack("<II", b0, b1))[:ln]})
        return status, writes

    def install(self):
        status, writes = self.test_plan(True)
        assert status == 1, f"the plan was refused (status {status})"
        for w in writes:
            self.e.write(w["va"], w["bytes"])
        self.plan = writes
        return writes

    # ------------------------------------------------------------------ seams
    def _seams(self):
        e = self.e
        e.seam(0x475830, lambda emu: (self.now, 0))                 # state->Now() (real clock reader)
        e.seam(0x468B00, lambda emu: (self.now & 0xFFFFF, 0))       # CGameTime::Seconds()

        def native_handle(emu):
            self.native_handle.append((emu.arg(0), emu.arg(1)))
            return self.native_handle_result, 8
        e.seam(NATIVE_HANDLE_MESSAGE, native_handle)

        def native_save(emu):
            st = emu.ecx
            self.native_saves.append((emu.arg(0), emu.rs32(st + SPEED_FIELD), emu.rs32(self.a(GAME_TIME) + 0x20)))
            return 1, 4
        e.seam(NATIVE_SAVE, native_save)

        def native_load(emu):
            st = emu.ecx
            self.native_loads.append(emu.arg(0))
            if self.load_sets_field is not None:
                emu.w32(st + SPEED_FIELD, self.load_sets_field)
            return self.load_result, 4
        e.seam(NATIVE_LOAD, native_load)

        e.seam(0x4CE840, lambda emu: (emu.alloc(emu.arg(0)), 0))                  # operator new
        self.gfx = e.alloc(64)
        e.seam(0x49AFD0, lambda emu: (self.gfx, 0))                               # GraphicsManager::Get

        def image_grid(emu):
            assert emu.ecx == self.gfx, "GetImageGrid was not called on the graphics manager"
            return 0x10000000 + emu.arg(0), 4
        e.seam(0x49B1D0, image_grid)

        def button_ctor(emu):
            args = [emu.arg(i) for i in range(6)]
            self.button_ctors.append({"this": emu.ecx, "id": args[0], "grid": args[1],
                                      "x": struct.unpack("<i", struct.pack("<I", args[2]))[0],
                                      "y": struct.unpack("<i", struct.pack("<I", args[3]))[0],
                                      "scene": args[4], "flag": args[5]})
            return emu.ecx, 0x18
        e.seam(0x472D70, button_ctor)

        def set_text(emu):
            self.button_texts.append({"button": emu.ecx, "text": emu.cstr(emu.arg(0)),
                                      "c": (emu.arg(1), emu.arg(2), emu.arg(3)), "font": emu.arg(4)})
            return 0, 0x14
        e.seam(0x4736C0, set_text)

        def add_control(emu):
            self.added.append((emu.ecx, emu.arg(0)))
            return 0, 4
        e.seam(0x47EC70, add_control)

    # ------------------------------------------------------------------ small helpers
    def gametime(self):
        return self.e.rs32(self.a(GAME_TIME) + 0x20)

    def set_gametime(self, speed):
        self.e.w32(self.a(GAME_TIME) + 0x20, speed)
        self.e.w32(self.a(GAME_TIME) + 0x24, speed)

    def field(self):
        return self.e.rs32(self.state + SPEED_FIELD)

    def set_field(self, v):
        self.e.w32(self.state + SPEED_FIELD, v)

    def vtable_slot(self, obj_vtable_link, slot):
        return self.e.r32(self.a(obj_vtable_link) + 4 * slot)

    def test_time(self, op, arg=0):
        r = self.e.call(self.e.dll_export("B200Time_TestTime"), (op, arg))
        return struct.unpack("<i", struct.pack("<I", r))[0]

    # ------------------------------------------------------------------ villagers
    def villager_base(self, k):
        return self.a(VM) + 0x1CC70 + k * 0x1CC0C

    def set_villager(self, k, active=1, left=0, health=100, age=100, acc=0, behind=1300):
        b = self.villager_base(k)
        e = self.e
        e.write(b + 0x1BB84, bytes([active]))
        e.write(b + 0x1BB88, bytes([left]))
        e.w32(b + 0x6B00, health)
        e.w32(b + 0x6A54, age)
        e.w32(b + 0x6AF4, acc)
        e.w32(b + 0x6AF8, self.now - behind)

    def age(self, k):
        return self.e.rs32(self.villager_base(k) + 0x6A54)

    def acc(self, k):
        return self.e.rs32(self.villager_base(k) + 0x6AF4)

    def run_timeflow(self):
        self.e.call(self.a(TIMEFLOW), (0,), ecx=self.a(VM))

    # ------------------------------------------------------------------ the dialog procedure
    def open_time_dialog(self):
        before = len(self.e.dialogs)
        dialog = self.make_dialog()
        self.native_handle.clear()
        self.call_handle_message(dialog, 8, 9)
        assert len(self.e.dialogs) == before + 1, "clicking the Time Controls button did not open the dialog"
        tmpl, owner, proc = self.e.dialogs[-1]
        self.proc = proc
        assert self.dlg(WM_INITDIALOG, 0, 0) == 1
        return tmpl, owner

    def dlg(self, msg, wp, lp):
        return self.e.call(self.proc, (0x777, msg, wp, lp))

    def press(self, control_id):
        assert self.dlg(WM_COMMAND, control_id, 0) == 1
        return self.e.status_text

    # ------------------------------------------------------------------ the options dialog object
    def make_dialog(self):
        e = self.e
        d = e.alloc(0x400)
        e.w32(d, self.a(OPTIONS_VTABLE))
        e.w32(d + 0x14, 0)
        e.w32(d + 0x18, 0)
        e.w32(d + 0x1C, 640)
        e.w32(d + 0x20, 498)
        e.w32(d + 0x80, self.state)
        # theStringManager: fonts at [mgr + 0x10 + 4 * i]
        mgr = e.alloc(64)
        for i in range(4):
            e.w32(mgr + 0x10 + 4 * i, 0xF0000000 + i)
        e.w32(d + 0xB4, mgr)
        # the Done button: a vtable whose slot 3 returns its width and slot 4 its height
        width = e.fake_code(b"\xB8" + struct.pack("<I", 144) + b"\xC3")
        height = e.fake_code(b"\xB8" + struct.pack("<I", 34) + b"\xC3")
        vt = e.alloc(64)
        e.w32(vt + 12, width)
        e.w32(vt + 16, height)
        done = e.alloc(64)
        e.w32(done, vt)
        e.w32(d + 0xD4, done)
        e.w32(self.a(TEXT_COLOUR), 0xAABBCCDD)
        self.mgr = mgr
        return d

    def call_handle_message(self, dialog, message, param):
        slot = self.vtable_slot(OPTIONS_VTABLE, 3)
        return self.e.call(slot, (message, param), ecx=dialog) & 0xFFFFFFFF

    def run_ctor_tail(self, dialog):
        """Run the REAL constructor tail (from `push esi; mov ecx,ebx; call AddControl` of the last
        check box to its `ret 8`) with a frame laid out as the constructor builds it."""
        e = self.e
        box = e.alloc(0x40)
        blob = e.alloc(0x40)
        e.w32(box + 0x10, blob)
        self.box, self.blob = box, blob
        frame = e.sp_top - 0x40
        stack = [(frame, 0xDEAD0000), (frame + 4, SENTINEL), (frame + 8, 0x11), (frame + 0xC, 0x22),
                 (frame - 4, 0xFFFFFFFF), (frame - 8, 0), (frame - 0xC, 0xFFFFFFFF),
                 (frame - 0x18, 0xB1B1B1B1), (frame - 0x1C, 0x51515151), (frame - 0x20, 0xD1D1D1D1),
                 (frame - 0x24, 0xC0C0C0C0)]
        e.write(self.state + 0x25B0A, b"\x01")
        e.run_frame(self.a(CTOR_TAIL), {
            UC_X86_REG_EBX: dialog, UC_X86_REG_ESI: box, UC_X86_REG_EDI: 0xAAAA0001,
            UC_X86_REG_EBP: frame, UC_X86_REG_ESP: frame - 0x24,
        }, stack)
        return frame


# ====================================================================== scenarios
def scenario_plan_matches_the_sites(w: World):
    """The plan is exactly the five writes, rebased, each with the right content."""
    writes = w.plan
    by_va = {x["va"]: x for x in writes}
    assert len(writes) == 5, writes
    call_site = w.a(0x4A621B)
    aging_site = w.a(0x4C4DEF)
    assert call_site in by_va and aging_site in by_va
    for site in (call_site, aging_site):
        x = by_va[site]
        assert x["len"] == 5 and not x["data"] and x["bytes"][0] == 0xE8
        target = (site + 5 + struct.unpack("<i", x["bytes"][1:5])[0]) & 0xFFFFFFFF
        # the target lies inside the DLL image
        assert 0x30000000 <= target < 0x30030000, hex(target)
    for slot in (0x5006E4, 0x4FC588, 0x4FC58C):
        x = by_va[w.a(slot)]
        assert x["len"] == 4 and x["data"]
        assert 0x30000000 <= u32(x["bytes"]) < 0x30030000
    targets = {u32(by_va[w.a(s)]["bytes"]) for s in (0x5006E4, 0x4FC588, 0x4FC58C)}
    assert len(targets) == 3, "the three vtable slots must get three different functions"


def scenario_button_placed(w: World):
    """The real constructor tail builds the Time Controls button at (30, 434), id 9."""
    d = w.make_dialog()
    frame = w.run_ctor_tail(d)
    e = w.e
    assert e.reg(UC_X86_REG_EIP) == SENTINEL
    assert e.reg(UC_X86_REG_ESP) == frame + 0x10, hex(e.reg(UC_X86_REG_ESP))
    assert e.reg(UC_X86_REG_EAX) == d, "the constructor must still return the dialog"
    assert e.reg(UC_X86_REG_EBX) == 0xB1B1B1B1 and e.reg(UC_X86_REG_ESI) == 0x51515151 \
        and e.reg(UC_X86_REG_EDI) == 0xD1D1D1D1, "callee-saved registers must come back"
    assert e.r32(TEB_BASE) == 0xFFFFFFFF, "fs:[0] (the SEH chain) is restored"
    # SetChecked (the call the stub keeps making) ran for real on the last check box
    assert e.read(w.blob + 0x31, 1) == b"\x01"
    assert w.added[0] == (d, w.box), "the last check box is still added first"
    assert len(w.added) == 2 and w.added[1][0] == d
    assert len(w.button_ctors) == 1
    b = w.button_ctors[0]
    assert (b["id"], b["x"], b["y"], b["scene"], b["flag"]) == (9, 30, 434, d, 0), b
    assert b["grid"] == 0x10000000 + 0x128, "the Done / Evict art"
    assert w.added[1][1] == b["this"], "the new button is the control that is added"
    assert len(w.button_texts) == 1
    t = w.button_texts[0]
    assert t["text"] == "Time Controls" and t["button"] == b["this"]
    assert t["c"] == (0xAABBCCDD,) * 3, "the dialog's own button colour"
    assert t["font"] == 0xF0000002, "Evict's font (font 2)"


def scenario_stock_constructor_without_the_plan(w: World):
    """With nothing installed the same constructor tail adds the check box and nothing else."""
    d = w.make_dialog()
    frame = w.run_ctor_tail(d)
    assert w.e.reg(UC_X86_REG_ESP) == frame + 0x10
    assert w.added == [(d, w.box)] and not w.button_ctors and not w.button_texts
    assert w.e.read(w.blob + 0x31, 1) == b"\x01"


def scenario_slot3_dispatch(w: World):
    """Slot 3 opens the dialog for (message 8, id 9) and forwards everything else untouched."""
    d = w.make_dialog()
    w.native_handle_result = 0
    r = w.call_handle_message(d, 8, 9)
    assert r & 0xFF == 1 and not w.native_handle and len(w.e.dialogs) == 1
    tmpl, owner, proc = w.e.dialogs[0]
    assert owner == 0x1234, "the dialog is owned by the active window"
    assert w.e.wstr(tmpl + 22) == "Time Controls"
    assert struct.unpack_from("<H", w.e.read(tmpl, 18), 8)[0] == 10, "ten dialog items"
    # every other click and message reaches the original handler, with its result
    for message, param, result in ((8, 2, 1), (8, 3, 0), (8, 4, 1), (8, 5, 0), (8, 8, 1), (8, 10, 0), (8, 0, 1),
                                   (7, 9, 0), (0, 9, 1), (9, 9, 0)):
        w.native_handle.clear()
        w.native_handle_result = result
        r = w.call_handle_message(d, message, param)
        assert w.native_handle == [(message, param)], (message, param, w.native_handle)
        assert r & 0xFF == result, (message, param, hex(r))
    assert len(w.e.dialogs) == 1, "only message 8 / id 9 opens the dialog"


def scenario_slot3_without_the_plan(w: World):
    """With nothing installed, (8, 9) is just another message for the original handler."""
    d = w.make_dialog()
    w.native_handle_result = 1
    r = w.call_handle_message(d, 8, 9)
    assert w.native_handle == [(8, 9)] and r & 0xFF == 1 and not w.e.dialogs


def scenario_sdl_missing_does_not_matter(w: World):
    d = w.make_dialog()
    assert w.e.sdl_module == 0
    w.call_handle_message(d, 8, 9)
    assert len(w.e.dialogs) == 1


def scenario_speed_controls(w: World):
    """Pause, Resume and each speed, through the dialog procedure and the REAL CGameTime::SetSpeed."""
    w.open_time_dialog()
    assert w.e.status_text == "Running. Speed: normal."
    cases = [
        (ID_SLOW, 20, 20, "Running. Speed: slow."),
        (ID_FAST, 5, 5, "Running. Speed: fast."),
        (ID_X5, 2, 2, "Running. Speed: 5x."),
        (ID_X10, 1, 1, "Running. Speed: 10x."),
        (ID_NORMAL, 10, 10, "Running. Speed: normal."),
    ]
    for cid, field, gt, text in cases:
        assert w.press(cid) == text
        assert (w.field(), w.gametime()) == (field, gt), (cid, w.field(), w.gametime())
    # pause: the game's own convention (field + 999, CGameTime speed 0)
    assert w.press(ID_PAUSE) == "Paused. Speed: normal."
    assert (w.field(), w.gametime()) == (1009, 0)
    assert w.press(ID_PAUSE) == "Paused. Speed: normal."          # pausing twice changes nothing
    assert (w.field(), w.gametime()) == (1009, 0)
    # a speed chosen while paused is remembered for Resume and the clock stays paused
    assert w.press(ID_X10) == "Paused. Speed: 10x."
    assert (w.field(), w.gametime()) == (999 + 1, 0)
    assert w.press(ID_RESUME) == "Running. Speed: 10x."
    assert (w.field(), w.gametime()) == (1, 1)
    assert w.press(ID_RESUME) == "Running. Speed: 10x."
    assert (w.field(), w.gametime()) == (1, 1)
    # the plain 999 the stock Space key can leave resumes at normal
    w.set_field(999)
    w.set_gametime(0)
    assert w.press(ID_RESUME) == "Running. Speed: normal."
    assert (w.field(), w.gametime()) == (10, 10)


# (speed field, CGameTime speed): running at each speed, and paused (SetSpeed(999) leaves CGameTime at 0)
# at normal / slow / fast / 5x / 10x.
# (999, 999) is left out: stock Space calls SetSpeed(0) there, the module resumes at normal (tested apart).
SPACE_STATES = [(10, 10), (20, 20), (5, 5), (2, 2), (1, 1), (1009, 0), (1019, 0), (1004, 0), (1001, 0),
                (1000, 0)]


def _space(w: World, field, gt):
    """Run the stock Space-key toggle for real; return (field, game-time speed)."""
    e = w.e
    w.set_field(field)
    w.set_gametime(gt)
    scene = e.alloc(0x40)
    e.w32(scene + 0x14, w.state)
    x = e.sp_top - 0x80
    e.run_frame(w.a(SPACE_TOGGLE), {UC_X86_REG_EDI: scene, UC_X86_REG_EBP: x + 4, UC_X86_REG_ESP: x},
                [(x, 0xE1E1E1E1), (x + 4, 0xE2E2E2E2), (x + 8, SENTINEL), (x + 12, 0)])
    return w.field(), w.gametime()


def scenario_pause_resume_match_the_space_key(w: World):
    """Differential: Pause/Resume leave exactly the state the stock Space key leaves."""
    w.open_time_dialog()
    for field, gt in SPACE_STATES:
        expected = _space(w, field, gt)
        w.set_field(field)
        w.set_gametime(gt)
        w.press(ID_RESUME if field >= 999 else ID_PAUSE)
        assert (w.field(), w.gametime()) == expected, ((field, gt), expected, (w.field(), w.gametime()))


def scenario_time_warp(w: World):
    """+3 years through the REAL AllVillagersTimeflowUpkeep and IncrementAge."""
    e = w.e
    w.set_field(10)
    for k in range(30):
        w.set_villager(k, active=0)
    w.set_villager(0)                              # at home, alive
    w.set_villager(1, age=120)                     # at home, alive
    w.set_villager(2, active=0, age=100)           # not in the village
    w.set_villager(3, left=1, age=100)             # left home
    w.set_villager(4, health=0, age=100)           # dead
    w.set_villager(29, age=40)                     # the last slot
    # baseline: 1300 s at speed 10 = 2 native ticks, 100 s left in the accumulator
    w.run_timeflow()
    assert [w.age(k) for k in (0, 1, 2, 3, 4, 29)] == [102, 122, 100, 100, 100, 42], \
        [w.age(k) for k in (0, 1, 2, 3, 4, 29)]
    assert w.acc(0) == 100 and w.acc(29) == 100
    # queue the warp: 60 ticks for the three eligible villagers, then run another pass
    w.now += 1300
    for k in (0, 1, 29):
        w.set_villager(k, age=w.age(k))
    assert w.test_time(4, 60) == 0
    assert w.test_time(5) == 3
    before = {k: w.age(k) for k in (0, 1, 2, 3, 4, 29)}
    w.run_timeflow()
    after = {k: w.age(k) for k in (0, 1, 2, 3, 4, 29)}
    assert after[0] == before[0] + 2 + 60 and after[1] == before[1] + 2 + 60 and after[29] == before[29] + 2 + 60, after
    assert after[2] == before[2] and after[3] == before[3] and after[4] == before[4], "ineligible villagers get nothing"
    assert w.acc(0) == 100 and w.acc(1) == 100 and w.acc(29) == 100, \
        "the accumulator remainder must come from the NATIVE ticks"
    assert w.test_time(5) == 0, "every queued villager has been given the ticks"
    # a second pass: ordinary aging only
    w.now += 1300
    for k in (0, 1, 29):
        w.set_villager(k, age=w.age(k))
    before = dict(after)
    w.run_timeflow()
    assert [w.age(k) for k in (0, 1, 29)] == [before[0] + 2, before[1] + 2, before[29] + 2]


def scenario_time_warp_skips_the_unlucky(w: World):
    """A queued villager who died or left home before the pass is dropped, not given the ticks later."""
    e = w.e
    for k in range(30):
        w.set_villager(k, active=0)
    w.set_villager(0)
    w.set_villager(1)
    assert w.test_time(4, 60) == 0 and w.test_time(5) == 2
    e.write(w.villager_base(1) + 0x1BB88, b"\x01")      # villager 1 leaves home
    assert w.test_time(5) == 1
    w.run_timeflow()
    assert w.age(0) == 162 and w.age(1) == 100


def scenario_stock_aging_without_the_plan(w: World):
    for k in range(30):
        w.set_villager(k, active=0)
    w.set_villager(0)
    w.run_timeflow()
    assert w.age(0) == 102 and w.acc(0) == 100


def scenario_save_normalises_the_speed(w: World):
    """Save writes any non-stock speed as normal and puts the live speed back."""
    e = w.e
    slot_save = w.vtable_slot(GAME_STATE_VTABLE, 14)
    rows = [
        # (live field, live CGameTime speed, slot, expected (field, gametime) seen by the original Save)
        (1, 1, 1, (10, 10)),          # 10x running -> normal
        (20, 20, 2, (10, 10)),        # slow -> normal
        (5, 5, 3, (10, 10)),
        (2, 2, 4, (10, 10)),
        (1000, 0, 1, (1009, 0)),  # paused at 10x -> paused at normal
        (1019, 0, 2, (1009, 0)),  # paused at slow -> paused at normal
        (10, 10, 1, (10, 10)),        # stock: untouched
        (10, 77, 1, (10, 77)),        # a stock field is left alone whatever the clock says (no SetSpeed)
        (1009, 0, 1, (1009, 0)),    # stock paused: untouched
        (1, 1, 0, (1, 1)),            # slot 0 is the header only: untouched
    ]
    for field, gt, slot, expected in rows:
        w.native_saves.clear()
        w.set_field(field)
        w.set_gametime(gt)
        r = e.call(slot_save, (slot,), ecx=w.state)
        assert r & 0xFF == 1
        assert w.native_saves == [(slot, expected[0], expected[1])], (field, gt, slot, w.native_saves)
        assert (w.field(), w.gametime()) == (field, gt), "the live speed is put back after the save"


def scenario_load_normalises_the_speed(w: World):
    """A loaded non-stock speed becomes normal (paused stays paused); stock values are untouched."""
    e = w.e
    slot_load = w.vtable_slot(GAME_STATE_VTABLE, 13)
    rows = [
        # (speed the "file" holds, slot, expected field, expected CGameTime speed given gametime 77 before)
        (1, 1, 10, 10),
        (20, 2, 10, 10),
        (5, 3, 10, 10),
        (1000, 1, 1009, 77),     # paused at 10x -> paused at normal; the clock stays as loaded
        (1019, 1, 1009, 77),
        (10, 1, 10, 77),         # stock
        (1009, 1, 1009, 77),     # stock paused
        (1, 0, 1, 77),           # slot 0: header only
    ]
    for saved, slot, field, gt in rows:
        w.native_loads.clear()
        w.load_sets_field = saved
        w.load_result = 1
        w.set_field(10)
        w.set_gametime(77)
        w.set_villager(0)
        w.test_time(4, 60)
        r = e.call(slot_load, (slot,), ecx=w.state)
        assert r & 0xFF == 1
        assert w.native_loads == [slot]
        assert (w.field(), w.gametime()) == (field, gt), (saved, slot, w.field(), w.gametime())
        if slot:
            assert w.test_time(5) == 0, "a load clears any queued warp"
    # a failed load changes nothing
    w.load_sets_field = 1
    w.load_result = 0
    w.set_field(10)
    r = e.call(slot_load, (1,), ecx=w.state)
    assert r & 0xFF == 0 and w.field() == 1


def scenario_off_changes_nothing(w: World):
    """Setting off, or any pin different, plans nothing and the executable stays byte for byte."""
    assert w.code_unchanged()
    status, writes = w.test_plan(False)
    assert (status, writes) == (0, [])
    assert w.code_unchanged()
    # the executable loaded somewhere other than the DLL is told (a wrong delta): the pins refuse
    status, writes = w.test_plan(True, image_base=w.e.base + 0x1000)
    assert status == -1 and writes == [], status
    assert w.code_unchanged()


def scenario_install_diff_is_exactly_the_plan(w: World):
    """With the plan applied, .text/.rdata differ from the stock image only inside the planned writes,
    and every write changes something."""
    changed = w.changed_code_bytes()
    planned = set()
    for x in w.plan:
        planned.update(range(x["va"], x["va"] + x["len"]))
        assert any(a in changed for a in range(x["va"], x["va"] + x["len"])), x
    assert changed and changed <= planned, sorted(hex(a) for a in changed - planned)[:8]


def scenario_warp_button(w: World):
    """The Time Warp button asks first; Yes queues +3 years for everyone at home, No queues nothing."""
    for k in range(30):
        w.set_villager(k, active=0)
    for k in (0, 1, 2):
        w.set_villager(k)
    w.open_time_dialog()
    w.e.messagebox_answer = 7      # IDNO
    assert w.press(ID_WARP) == "Running. Speed: normal."
    assert w.test_time(5) == 0
    w.e.messagebox_answer = 6      # IDYES
    assert w.press(ID_WARP) == "Running. Speed: normal. A time warp is under way."
    assert w.test_time(5) == 3
    assert any("Everyone at home ages at once" in str(c) for c in w.e.calls if c[0] == "MessageBoxW")
    w.run_timeflow()
    assert [w.age(k) for k in (0, 1, 2)] == [162, 162, 162]       # 100 + 2 native ticks + 60 (3 years)
    assert w.press(ID_NORMAL) == "Running. Speed: normal."          # the note goes once nobody is pending
    # the dialog closes on Close / Escape / the X button
    for msg, wp in ((WM_COMMAND, 1), (WM_COMMAND, 2), (0x10, 0)):
        assert w.dlg(msg, wp, 0) == 1


def scenario_pins_are_enforced(w: World):
    """Any single wrong byte in any pinned run (first or last) makes the plan refuse, with nothing planned."""
    import b200_time_sites as S
    e = w.e
    assert w.test_plan(True)[0] == 1
    for pin in S.PINS:
        for off in (0, len(pin.bytes) - 1):
            addr = w.a(pin.va) + off
            was = e.read(addr, 1)
            e.write(addr, bytes([was[0] ^ 0x01]))
            status, writes = w.test_plan(True)
            assert status == -1 and not writes, (pin.name, off, status)
            e.write(addr, was)
    assert w.test_plan(True)[0] == 1


ALL = [
    scenario_plan_matches_the_sites,
    scenario_install_diff_is_exactly_the_plan,
    scenario_button_placed,
    scenario_slot3_dispatch,
    scenario_sdl_missing_does_not_matter,
    scenario_speed_controls,
    scenario_pause_resume_match_the_space_key,
    scenario_time_warp,
    scenario_time_warp_skips_the_unlucky,
    scenario_warp_button,
    scenario_save_normalises_the_speed,
    scenario_load_normalises_the_speed,
]
STOCK = [
    scenario_stock_constructor_without_the_plan,
    scenario_slot3_without_the_plan,
    scenario_stock_aging_without_the_plan,
]
OFF = [scenario_off_changes_nothing, scenario_pins_are_enforced]


def run_installed(exe, dll, delta):
    for fn in ALL:
        fn(World(exe, dll, delta, install=True))


def run_stock(exe, dll, delta):
    """The DLL is loaded and asked for its plan with the setting off; nothing is written."""
    for fn in STOCK:
        w = World(exe, dll, delta, install=False)
        w.test_plan(False)
        assert w.code_unchanged()
        fn(w)
    for fn in OFF:
        fn(World(exe, dll, delta, install=False))
