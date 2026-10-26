"""Scenarios for the Family History DLL (vf2history_b200.dll), run under tests/b200_time_emu.py.

Each scenario takes a fresh HistoryWorld and raises AssertionError on a wrong result. A HistoryWorld is the
REAL B200 core executable and the REAL compiled test DLL in one unicorn address space (at the link address
and relocated, as Windows does with ASLR), with the DLL's hooks written exactly as its own plan says.

Every hook is reached from its live caller: the game's own instructions run up to and through the call the
DLL retargets (or, for CVillager::Impregnate, into the jmp written at its entry), so each scenario proves the
retargeted call lands in the DLL, the DLL chains to the function the game called, and the line is written.

Game code that runs for real: CVillager::Impregnate from its first instruction to its `ret 14h` (the twin /
triplet decision, the reserved baby slots, AddOffspring for each baby); theRealtimeManager::UpdateAll's call
of the physiology pass, then the pass's own delivery code (the first, second and third baby, the pregnancy
cleared); CVillagerManager::AllVillagersTimeflowUpkeep whole (all 30 slots: the dead villager deactivated and
reported, a child of 17Ch reaching college age leaving home), CFamilyTree::ReportDeath, CVillagerPlans::
StartNewBehavior's death tail; CDatingScene's accepted marriage through CFamilyTree::UpdateParents; the
patcher's generated Divorce Spouse block (VillagerExists, GetVillager, GetVillagerInFocus, DetachAll,
memset, UpdateCurrentFamilyRecord); CAdoptionScene::HandleMessage's new-family and Next Generation calls
(StartFamilyTree, B200's generation wrapper, StartNextGeneration); The Little Visitor 1 / 2 and The Talent
Scout's ImpactGame whole; the store's Adoption Services and Boarding School blocks (Boarding School through
the store's own jump table); CIslandEvents::FireEvent whole (the candidate scan, the random pick, the
mEventHasFired write) and CIslandEventDialog's constructor head (the title stored at +54h);
theOptionsDialog::EvictFamily's call of CFamilyTree::EvictFamily (Reset, the evicted flag); the title
menu's confirmed Start Over stub; theGameState's Load slot.

Seams (recorded, never real): theStringManager (the live table is built at run time: each id answers the
executable's own static text), MakeGameStatePath (a fixed folder), the clock (GetSecondsFromGameStart),
ldwGameState::GetRandom (scripted), the achievement counters, CMoney::Add, the life-event queue, the spawn
calls (they take the first free slot, as FindEmptySlot does), GetMatriarch / GetPatriarch, the family-tree
appearance observer B200 puts on UpdatePeepRecord, CVillager::Reset, SetCarrying, the physiology pass's
other upkeep (its entry runs only the delivery block), the bodies of theGameState::Load and ::Init, the
island event dialog's constructor body in FireEvent (it does what its proved head does: +50h the event,
+54h the title text, +4Ch ready), ldwDialog::DoModal's body and the dialog destructor, and the DLL's Win32
file imports (an in-memory file system).
"""
from __future__ import annotations

import os
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "tools"))
import b200_history_sites as S  # noqa: E402
import gen_b200_history_sites as G  # noqa: E402

from b200_time_emu import DLL_BASE, Emu, EmuError  # noqa: E402
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,  # noqa: E402
                               UC_X86_REG_EDX, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)
from unicorn import UC_HOOK_CODE  # noqa: E402

STRIDE = S.VILLAGER_STRIDE
SAVE_DIR = "C:\\Users\\Tester\\Documents\\LDW\\VF2 History Test"
ROOT = SAVE_DIR + "\\Virtual Families 2 Patcher\\Save "
DLL_PATH = "C:\\Game\\Virtual Families 2 Patcher Files\\vf2history_b200.dll"
INVALID = 0xFFFFFFFF
NOW = 50_000_000                 # the game clock (seconds)
SPEED = 10                       # theGameState+25B18h
ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND, ERROR_ALREADY_EXISTS, ERROR_NO_MORE_FILES = 2, 3, 183, 18
STAMP = "[2026-10-25 21:07:05] "  # GetLocalTime below

_PROVED = {}


def proved(exe_path):
    """(model of the core variant, derived sites of this executable, pin locations), cached."""
    key = str(exe_path)
    if key not in _PROVED:
        core = os.environ.get("VF2_B200_CORE_EXE") or key
        model = G.validate(Path(core).read_bytes())
        exe = G.Exe(Path(key).read_bytes())
        _PROVED[key] = (model, G.resolve(exe, model), G.locate(exe, model), G._string_table(exe))
    return _PROVED[key]


def s32(v):
    return struct.unpack("<i", struct.pack("<I", v & 0xFFFFFFFF))[0]


class FileSystem:
    """The DLL's Win32 file imports over a dict (case-insensitive paths)."""

    def __init__(self):
        self.files = {}
        self.dirs = set()
        self.handles = {}
        self.finds = {}
        self.next = 0x100
        self.last_error = 0
        self.log = []

    @staticmethod
    def key(path):
        return path.replace("/", "\\").lower()

    def parent(self, path):
        return self.key(path).rsplit("\\", 1)[0]

    def mkdirs(self, path):
        parts = self.key(path).split("\\")
        for i in range(1, len(parts) + 1):
            self.dirs.add("\\".join(parts[:i]))

    def write(self, path, data):
        self.mkdirs(self.parent(path))
        self.files[self.key(path)] = bytes(data)

    def read(self, path):
        return self.files.get(self.key(path))

    def text(self, path):
        raw = self.read(path)
        return None if raw is None else raw.decode("latin-1")

    def exists(self, path):
        return self.key(path) in self.files

    def under(self, folder):
        k = self.key(folder) + "\\"
        return sorted(f for f in self.files if f.startswith(k))

    def bind(self, emu):
        fs = self

        def create(e):
            path = e.cstr(e.arg(0))
            access, disposition = e.arg(1), e.arg(4)
            k = fs.key(path)
            fs.log.append(("CreateFileA", path, access, disposition))
            if disposition == 3:            # OPEN_EXISTING
                if k not in fs.files:
                    fs.last_error = ERROR_FILE_NOT_FOUND if fs.parent(path) in fs.dirs else ERROR_PATH_NOT_FOUND
                    return INVALID, 28
                data = bytearray(fs.files[k])
            elif disposition == 4:          # OPEN_ALWAYS (the appends)
                if fs.parent(path) not in fs.dirs:
                    fs.last_error = ERROR_PATH_NOT_FOUND
                    return INVALID, 28
                data = bytearray(fs.files.get(k, b""))
                fs.files[k] = bytes(data)
            else:
                raise EmuError(f"CreateFileA disposition {disposition}")
            h = fs.next
            fs.next += 4
            fs.handles[h] = {"key": k, "data": data, "pos": 0, "append": access == 4}
            return h, 28

        def read_file(e):
            h, buf, n, got = e.arg(0), e.arg(1), e.arg(2), e.arg(3)
            st = fs.handles[h]
            chunk = bytes(st["data"][st["pos"]:st["pos"] + n])
            st["pos"] += len(chunk)
            if chunk:
                e.write(buf, chunk)
            e.w32(got, len(chunk))
            return 1, 20

        def write_file(e):
            h, buf, n, got = e.arg(0), e.arg(1), e.arg(2), e.arg(3)
            st = fs.handles[h]
            assert st["append"], "the DLL writes only by appending"
            st["data"] += e.read(buf, n)
            e.w32(got, n)
            return 1, 20

        def close(e):
            st = fs.handles.pop(e.arg(0))
            if st["append"]:
                fs.files[st["key"]] = bytes(st["data"])
            return 1, 4

        def attributes(e):
            k = fs.key(e.cstr(e.arg(0)))
            if k in fs.files:
                return 0x80, 4
            if k in fs.dirs:
                return 0x10, 4
            fs.last_error = ERROR_FILE_NOT_FOUND
            return INVALID, 4

        def mkdir(e):
            path = e.cstr(e.arg(0))
            k = fs.key(path)
            if k in fs.dirs:
                fs.last_error = ERROR_ALREADY_EXISTS
                return 0, 8
            if fs.parent(path) not in fs.dirs:
                fs.last_error = ERROR_PATH_NOT_FOUND
                return 0, 8
            fs.dirs.add(k)
            return 1, 8

        def delete(e):
            path = e.cstr(e.arg(0))
            fs.log.append(("DeleteFileA", path))
            if fs.files.pop(fs.key(path), None) is None:
                fs.last_error = ERROR_FILE_NOT_FOUND
                return 0, 4
            return 1, 4

        def rmdir(e):
            k = fs.key(e.cstr(e.arg(0)))
            fs.log.append(("RemoveDirectoryA", k))
            if any(f.startswith(k + "\\") for f in fs.files) or any(d.startswith(k + "\\") for d in fs.dirs):
                return 0, 4
            fs.dirs.discard(k)
            return 1, 4

        def entry(e, out, name, is_dir):
            e.write(out, bytes(320))
            e.w32(out, 0x10 if is_dir else 0x80)
            e.write(out + 44, name.encode("latin-1") + b"\0")

        def find_first(e):
            pattern, out = e.cstr(e.arg(0)), e.arg(1)
            assert pattern.endswith("\\*"), pattern
            folder = fs.key(pattern[:-2])
            if folder not in fs.dirs:
                fs.last_error = ERROR_PATH_NOT_FOUND
                return INVALID, 8
            names = [(".", True), ("..", True)]
            for d in sorted(fs.dirs):
                if d.startswith(folder + "\\") and "\\" not in d[len(folder) + 1:]:
                    names.append((d[len(folder) + 1:], True))
            for f in sorted(fs.files):
                if f.startswith(folder + "\\") and "\\" not in f[len(folder) + 1:]:
                    names.append((f[len(folder) + 1:], False))
            h = fs.next
            fs.next += 4
            fs.finds[h] = names[1:]
            entry(e, out, *names[0])
            return h, 8

        def find_next(e):
            h, out = e.arg(0), e.arg(1)
            if not fs.finds[h]:
                fs.last_error = ERROR_NO_MORE_FILES
                return 0, 8
            entry(e, out, *fs.finds[h].pop(0))
            return 1, 8

        def find_close(e):
            fs.finds.pop(e.arg(0), None)
            return 1, 4

        def local_time(e):
            e.write(e.arg(0), struct.pack("<8H", 2026, 10, 0, 25, 21, 7, 5, 0))
            return 0, 4

        def protect(e):
            e.w32(e.arg(3), 0x40)
            return 1, 16

        emu.imports.update({
            "CreateFileA": create, "ReadFile": read_file, "WriteFile": write_file, "CloseHandle": close,
            "GetFileAttributesA": attributes, "CreateDirectoryA": mkdir, "DeleteFileA": delete,
            "RemoveDirectoryA": rmdir, "SetFileAttributesA": lambda e: (1, 8), "FindFirstFileA": find_first,
            "FindNextFileA": find_next, "FindClose": find_close, "GetLastError": lambda e: (fs.last_error, 0),
            "GetLocalTime": local_time, "VirtualProtect": protect, "FlushInstructionCache": lambda e: (1, 12),
            "GetCurrentProcess": lambda e: (INVALID, 0),
        })


class HistoryWorld:
    """One emulated process: the B200 core executable + the test DLL."""

    @classmethod
    def bare(cls, exe, dll, delta=0, native_scan=True):
        """Only the address space and the DLL (no game state, no proof of the executable): for an executable
        the resolver must refuse, and for the real byte-by-byte scan."""
        w = cls.__new__(cls)
        w.e = Emu(exe, dll, delta)
        w.delta = delta
        w.seam_fns = {}
        w.fs = FileSystem()
        w.fs.bind(w.e)
        if native_scan:
            w._native_scan()
        return w

    def __init__(self, exe, dll, delta=0, install=True):
        self.e = Emu(exe, dll, delta)
        self.seam_fns = {}
        self.delta = delta
        self.model, self.sites, self.pin_locs, self.strings_table = proved(exe)
        self.pins = {p.name: self.pin_locs[i] for i, p in enumerate(S.PINS)}
        self._native_scan()
        self.fs = FileSystem()
        self.fs.bind(self.e)
        self.fs.mkdirs(SAVE_DIR)
        self.rolls = []
        self.spawned = []
        self.calls = []
        self.loads = []
        self.load_result = 1
        self.on_load = None
        self.code_before = self._code()
        self.strings = {}
        self._game_state()
        self._villagers()
        self._seams()
        self.writes = []
        if install:
            self.install()

    def seam(self, addr, fn):
        """A Python seam at a live address; a second seam at the same address replaces the first (one hook
        per address, so a function is never returned from twice)."""
        if addr not in self.seam_fns:
            self.e.seam_live(addr, lambda emu, addr=addr: self.seam_fns[addr](emu))
        self.seam_fns[addr] = fn

    # ------------------------------------------------------------------ addresses
    def s(self, name):
        return self.sites[name] + self.delta

    def p(self, pin):
        return self.pins[pin] + self.delta

    def call_target(self, at):
        assert self.e.read(at, 1) == b"\xE8", hex(at)
        return (at + 5 + self.e.r32(at + 1)) & 0xFFFFFFFF

    def target(self, pin, off):
        return self.call_target(self.p(pin) + off)

    def _native_scan(self):
        e = self.e
        addr = e.call(e.dll_export("B200History_TestScanAddress"))

        def scan(emu):
            base, size, pat, mask, length, hits = (emu.arg(i) for i in range(6))
            data = emu.read(base, size)
            p, m = emu.read(pat, length), emu.read(mask, length)
            rx = re.compile(b"".join(b"." if w else re.escape(bytes([b])) for b, w in zip(p, m)), re.DOTALL)
            first = 0
            count = emu.r32(hits)
            for mt in rx.finditer(data):
                if not count:
                    first = base + mt.start()
                count += 1
                if count >= 2:
                    break
            emu.w32(hits, count)
            return first, 0
        self.seam(addr, scan)

    def _code(self):
        out = []
        for s in self.e.exe.sections:
            if s.Characteristics & 0x20000000:
                base = self.e.base + s.VirtualAddress
                out.append((base, self.e.read(base, min(s.Misc_VirtualSize, s.SizeOfRawData))))
        return out

    def changed_code(self):
        changed = set()
        for base, was in self.code_before:
            now = self.e.read(base, len(was))
            if now != was:
                changed.update(base + i for i in range(len(was)) if now[i] != was[i])
        return changed

    # ------------------------------------------------------------------ the plan
    def test_plan(self, enabled=True):
        out = self.e.alloc(0x400)
        status = s32(self.e.call(self.e.dll_export("B200History_TestPlan"), (1 if enabled else 0, out)))
        count = self.e.r32(out + 4)
        writes = []
        for i in range(count):
            va, ln, data, b0, b1 = (self.e.r32(out + 8 + i * 20 + 4 * k) for k in range(5))
            writes.append((va, (struct.pack("<I", b0) + bytes([b1 & 0xFF]))[:ln], bool(data)))
        return status, writes

    def install(self):
        status, writes = self.test_plan(True)
        assert status == 1, f"the plan was refused (status {status})"
        for va, raw, _data in writes:
            self.e.write(va, raw)
        self.writes = writes
        return writes

    # ------------------------------------------------------------------ the game's state
    def _game_state(self):
        e = self.e
        self.state = e.alloc(0x26400)
        e.w32(self.s("GAME_STATE_INSTANCE"), self.state)
        for k in range(3):
            e.w32(self.state + S.GAME_STATE_RESERVED_BABY + 4 * k, INVALID)
        e.w32(self.state + 0x25B18, SPEED)
        self.set_slot(1)
        self.set_player("Ana Player")
        vtable = e.alloc(0x40)
        stub = e.fake_code(b"\xC2\x04\x00")
        e.w32(vtable + S.LDW_PATH_VSLOT, stub)
        e.w32(self.state, vtable)
        self.path_buffer = e.alloc(0x200)

        def make_path(emu):
            emu.write(self.path_buffer, f"{SAVE_DIR}\\Virtual Families 2{emu.arg(0)}.ldw".encode("ascii") + b"\0")
            return self.path_buffer, 4
        self.seam(stub, make_path)

    def set_slot(self, slot):
        self.e.w32(self.state + S.GAME_STATE_SLOT, slot)

    def set_player(self, name):
        self.e.write(self.state + S.GAME_STATE_NICKNAME, name.encode("ascii")[:19].ljust(20, b"\0"))

    def tree(self):
        return self.s("FAMILY_TREE")

    def manager(self):
        return self.s("VILLAGER_MANAGER")

    def villager(self, slot):
        return self.manager() + S.VILLAGER_ARRAY_OFFSET + slot * STRIDE

    def _villagers(self):
        for slot in range(30):
            v = self.villager(slot)
            self.e.w32(v + S.VILLAGER_SLOT, slot)
            self.e.write(v + S.VILLAGER_ACTIVE, b"\0")

    def set_villager(self, slot, name, gender, active=1, age=600, head=3, body=4, health=100):
        e = self.e
        v = self.villager(slot)
        e.write(v + S.VILLAGER_NAME, name.encode("ascii")[:24].ljust(25, b"\0"))
        e.w32(v + S.VILLAGER_GENDER, gender)
        e.w32(v + S.VILLAGER_HEAD, head)
        e.w32(v + S.VILLAGER_BODY, body)
        e.w32(v + S.VILLAGER_AGE, age)
        e.w32(v + S.VILLAGER_HEALTH, health)
        e.w32(v + S.VILLAGER_CAUSE, INVALID)
        e.write(v + S.VILLAGER_ACTIVE, bytes([active]))
        e.write(v + S.VILLAGER_LEFT_HOME, b"\0")
        e.w32(v + 0x6AF4, 0)                  # the time accumulator of the upkeep
        e.w32(v + 0x6AF8, NOW)                # the last upkeep time
        e.w32(v + 0x6AFC, NOW - 1000)         # the time Impregnate copies into the pregnancy field (+6B18h)
        e.w32(v + 0x6B40, 0)
        e.w32(v + 0x1BB4C, INVALID)           # the villager it carries: none
        e.w32(v + 0x6B8C, INVALID)            # the career: none (CVillagerSkills::CareerType answers 0)

    def active(self, slot):
        return self.e.read(self.villager(slot) + S.VILLAGER_ACTIVE, 1)[0]

    def set_active(self, slot, on):
        self.e.write(self.villager(slot) + S.VILLAGER_ACTIVE, bytes([1 if on else 0]))

    def generations(self):
        return s32(self.e.r32(self.tree() + 4))

    def record(self, gen=None):
        gen = self.generations() if gen is None else gen
        return self.tree() + gen * S.FAMILY_RECORD_SIZE - S.FAMILY_RECORD_BASE

    def peep(self, which, gen=None):
        rec = self.record(gen)
        return rec + (S.RECORD_PARENT1 if which == 0 else S.RECORD_PARENT2 if which == 1
                      else S.RECORD_CHILDREN + (which - 2) * S.PEEP_RECORD_SIZE)

    def write_peep(self, which, name, gender, slot, gen=None):
        e = self.e
        p = self.peep(which, gen)
        e.write(p, name.encode("ascii")[:24].ljust(25, b"\0"))
        e.write(p + S.PEEP_VALID, b"\x01")
        e.w32(p + S.PEEP_GENDER, gender)
        e.w32(p + S.PEEP_SLOT, slot)
        e.w32(p + S.PEEP_HEAD, 3)
        e.w32(p + S.PEEP_BODY, 4)

    # ------------------------------------------------------------------ the files
    def history_path(self, k=1, slot=1):
        return f"{ROOT}{slot}\\Logs\\Family History\\Family History {k}.txt"

    def history(self, k=1, slot=1):
        text = self.fs.text(self.history_path(k, slot))
        assert text is not None, "no Family History file"
        return text

    def lines(self, k=1, slot=1):
        """The history's lines (header first), without the line ends."""
        return self.history(k, slot).split("\r\n")[:-1]

    def records(self, slot=1, files=None):
        """Every record of every file, in order: (heading without the stamp, [its lines]). Checks the layout: a
        heading "[stamp] Kind n", "  Label: value" lines, then one blank line."""
        out = []
        k = 1
        while self.fs.exists(self.history_path(k, slot)) and (files is None or k <= files):
            lines = self.lines(k, slot)
            assert lines[0].startswith("Family: ") and lines[0].endswith(f" (Save {slot})"), lines[0]
            i = 1
            while i < len(lines):
                head = lines[i]
                assert head.startswith(STAMP) or head.startswith("[backfilled, no date] "), head
                body = []
                i += 1
                while i < len(lines) and lines[i] != "":
                    assert lines[i].startswith("  "), lines[i]
                    body.append(lines[i])
                    i += 1
                assert i < len(lines) and lines[i] == "", "a record ends with a blank line"
                i += 1
                out.append((head.split("] ", 1)[1], body))
            k += 1
        return out

    def headings(self, slot=1):
        return [h for h, _ in self.records(slot)]

    def last(self, slot=1):
        return self.records(slot)[-1]

    # ------------------------------------------------------------------ seams
    def word(self, sid):
        if sid not in self.strings:
            texts = [t for (i, _n), t in self.strings_table.items() if i == sid]
            assert len(texts) == 1, f"string {sid:#x}"
            p = self.e.alloc(len(texts[0]) + 1)
            self.e.write(p, texts[0].encode("latin-1") + b"\0")
            self.strings[sid] = p
        return self.strings[sid]

    def text_at(self, ptr):
        return self.e.cstr(ptr)

    def _seams(self):
        e = self.e
        self.seam(self.s("SM_GET"), lambda emu: (0x5A5A0000, 0))
        self.seam(self.s("SM_GET_STRING"), lambda emu: (self.word(emu.arg(0)), 4))
        self.observer = self.target("ft_update_parents", 0xDC)          # B200's UpdatePeepRecord observer
        assert self.observer == self.target("ft_add_offspring", 0x7B)
        self.seam(self.observer, lambda emu: (self.calls.append(("observer", emu.arg(0))), 4)[1:] and (0, 4))
        # the clock and the random numbers
        self.clock = self.target("vm_timeflow", 0x50)
        self.seam(self.clock, lambda emu: (NOW, 0))
        self.get_random = self.target("ie_fire", 0x1)

        def get_random(emu):
            assert self.rolls, "an unscripted GetRandom"
            return self.rolls.pop(0), 0
        self.seam(self.get_random, get_random)
        # the achievement counters and CMoney::Add
        self.achievement = self.target("ds_marry", 0x17)
        self.seam(self.achievement, lambda emu: (self.calls.append(("achievement", emu.arg(0))), 8)[1:] and (0, 8))
        self.money_add = self.target("ds_marry", 0x31)
        self.seam(self.money_add, lambda emu: (self.calls.append(("money",)), 8)[1:] and (0, 8))
        # GameState::Load body, Init body
        self.seam(self.s("GS_LOAD"), self._load_body)
        self.seam(self.s("GS_INIT"), lambda emu: (self.calls.append(("Init", emu.ecx)), 0)[1:] and (0, 0))

    def _load_body(self, emu):
        slot = emu.arg(0)
        self.loads.append(slot)
        if self.on_load:
            self.on_load(slot)
        return self.load_result, 4

    def run_range(self, start, until, regs=None, stack=()):
        """Run the game's own instructions from `start` up to `until` (the instruction after the call the DLL
        retargets), with the given registers and stack dwords."""
        e = self.e
        esp = e.sp_top - 0x400
        for i, v in enumerate(stack):
            e.w32(esp + 4 * i, v)
        e.setreg(UC_X86_REG_ESP, esp)
        frame = e.alloc(0x2000) + 0x1000
        e.setreg(UC_X86_REG_EBP, frame)
        for reg, v in (regs or {}).items():
            e.setreg(reg, v)
        try:
            e.uc.emu_start(start, until)
        except Exception as ex:  # noqa: BLE001
            raise EmuError(f"stopped at {e.reg(UC_X86_REG_EIP):#x}: {ex}") from ex
        assert e.reg(UC_X86_REG_EIP) == until, f"ended at {e.reg(UC_X86_REG_EIP):#x}, not {until:#x}"
        return frame

    # ------------------------------------------------------------------ the family, as the game makes it
    def adoption_scene(self, mode):
        scene = self.e.alloc(0x100)
        self.e.w32(scene + 0x1C, mode)
        return scene

    def new_family(self, founder):
        """CAdoptionScene::HandleMessage's Accept, new family: StartFamilyTree(founder) through its own call."""
        scene = self.adoption_scene(0)
        p = self.p("ad_handle_message")
        self.run_range(p + 0x13A, p + 0x14B, {UC_X86_REG_EDI: scene, UC_X86_REG_EBX: self.villager(founder)})

    def next_generation(self, heir, source=-1):
        """The same Accept in Next Generation mode (mode 1): B200's wrapper, then StartNextGeneration."""
        scene = self.adoption_scene(1)
        self.e.w32(scene + 0x54, 0)
        self.e.w32(scene + 0x38, source & 0xFFFFFFFF)
        p = self.p("ad_handle_message")
        self.run_range(p + 0x13A, p + 0x171, {UC_X86_REG_EDI: scene, UC_X86_REG_EBX: self.villager(heir)})

    def marry(self, a, b, dowry=500):
        """CDatingScene's accepted marriage: its own UpdateParents(a, b) call."""
        fake = self.e.alloc(0x40)
        self.e.w32(fake + 8, dowry)
        p = self.p("ds_marry")
        self.run_range(p, p + 0x42, {UC_X86_REG_ESI: self.villager(a), UC_X86_REG_EDI: self.villager(b),
                                     UC_X86_REG_EBX: fake})

    def divorce(self):
        """The patcher's Divorce Spouse, the generated block from its first instruction."""
        p = self.p("dv_divorce")
        start = p - 0x5E
        assert self.e.read(start, 6) == bytes.fromhex("8b9f04010000"), "the generated block's start moved"
        self.resets = []
        self.seam(self.call_target(p + 9), lambda emu: (self.resets.append(emu.ecx), 0)[1:] and (0, 0))
        self.run_range(start, p + 0x2E, {UC_X86_REG_EDI: self.record()})

    def report_death_timeflow(self):
        """CVillagerManager::AllVillagersTimeflowUpkeep(false), whole."""
        self.e.call(self.p("vm_timeflow"), (0,), ecx=self.manager())

    def kill(self, slot, cause):
        v = self.villager(slot)
        self.e.w32(v + S.VILLAGER_HEALTH, 0)
        self.e.w32(v + S.VILLAGER_CAUSE, cause & 0xFFFFFFFF)
        self.e.w32(v + 0x6AF8, NOW - 200_000)        # dead long enough for the upkeep to report it

    def death_behavior(self, slot):
        """CVillagerPlans::StartNewBehavior's death behaviour tail: the life event, ReportDeath, deactivate."""
        e = self.e
        p = self.p("vp_death")
        self.seam(self.call_target(p + 0x17), lambda emu: (self.calls.append(("life event",)), 12)[1:] and (0, 12))
        plans = e.alloc(0x100)
        self.run_range(p, p + 0x60, {UC_X86_REG_EBX: self.villager(slot), UC_X86_REG_EDI: plans,
                                     UC_X86_REG_ECX: 0x100, UC_X86_REG_ESI: 0x200})

    # ---- conception and birth
    def seam_impregnate(self, mother, father):
        e = self.e
        imp = self.p("v_impregnate")
        self.seam(self.call_target(imp + 0x24), lambda emu: (self.villager(mother), 0))   # GetMatriarch
        self.seam(self.call_target(imp + 0x31), lambda emu: (self.villager(father), 0))   # GetPatriarch
        raw = e.read(imp, 0x2D7)

        def call_at(off):
            assert raw[off] == 0xE8, hex(off)
            return self.call_target(imp + off)

        def spawn(pop):
            def fn(emu):
                reserved = {s32(e.r32(self.state + S.GAME_STATE_RESERVED_BABY + 4 * k)) for k in range(3)}
                for slot in range(30):
                    if not self.active(slot) and slot not in reserved and slot not in self.spawned:
                        self.set_villager(slot, f"Baby {slot}", slot % 2, active=0, age=0)
                        self.spawned.append(slot)
                        return slot, pop
                return INVALID, pop
            return fn
        self.seam(call_at(0x14D), spawn(48))
        self.seam(call_at(0x219), spawn(4))
        self.seam(call_at(0x101), lambda emu: (INVALID, 0))
        assert call_at(0x1A9) == self.achievement and call_at(0x1B7) == self.achievement
        assert call_at(0xA3) == self.get_random

    def impregnate(self, mother, father, rolls):
        """B200's real CVillager::Impregnate, entered at its first instruction (the DLL's jmp)."""
        e = self.e
        self.seam_impregnate(mother, father)
        self.rolls = list(rolls)
        self.spawned = []
        name = e.alloc(32)
        e.write(name, b"Joey\0")
        fv = self.villager(father)
        r = e.call(self.s("V_IMPREGNATE"), (1, name, e.r32(fv + S.VILLAGER_HEAD), e.r32(fv + S.VILLAGER_BODY), 0),
                   ecx=self.villager(mother)) & 0xFF
        return r

    def deliver(self, mother):
        """theRealtimeManager::UpdateAll's call of the physiology pass; the pass runs its own delivery block
        for the mother (the first, second and third baby, then the pregnancy cleared)."""
        e = self.e
        phys, birth, birth_end = self.s("VM_PHYSIOLOGY"), self.s("VM_BIRTH"), self.s("VM_BIRTH_END")
        start, resume = birth - 0xC, birth_end + 0x1B
        assert e.read(start, 12) == bytes.fromhex("8b8d7cffffff8bb574ffffff")
        assert e.read(birth_end + 0x14, 7) == bytes.fromhex("c7432800000000")
        self.seam(self.call_target(birth + 0x6D), lambda emu: (NOW, 0))                  # GetSecondsFromGameStart
        self.seam(self.call_target(birth_end + 0xF), lambda emu: (0, 4))                 # SetCarrying
        assert self.call_target(birth + 0x2F) == self.get_random
        self.rolls = [0] * 6
        state = self.villager(mother) + 0x6AF4
        saved = {}

        def enter(uc, address, size, user):
            if address != phys:
                return
            saved.update({r: e.reg(r) for r in (UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ESI,
                                                 UC_X86_REG_EDI)})
            frame = e.alloc(0x400) + 0x200
            e.w32(frame - 0x84, self.state)
            e.w32(frame - 0x8C, self.manager())
            e.w32(frame - 0x88, state)
            e.w32(frame - 0x94, state - 0xA0)
            e.setreg(UC_X86_REG_EBP, frame)
            e.setreg(UC_X86_REG_ESP, saved[UC_X86_REG_ESP] - 0x100)
            e.setreg(UC_X86_REG_EBX, state)
            e.setreg(UC_X86_REG_EAX, 1)
            e.setreg(UC_X86_REG_EIP, start)

        def leave(uc, address, size, user):
            if address != resume:
                return
            for r, v in saved.items():
                e.setreg(r, v)
            ret = e.r32(saved[UC_X86_REG_ESP])
            e.setreg(UC_X86_REG_ESP, saved[UC_X86_REG_ESP] + 4)
            e.setreg(UC_X86_REG_EIP, ret)
        h1 = e.uc.hook_add(UC_HOOK_CODE, enter, begin=phys, end=phys)
        h2 = e.uc.hook_add(UC_HOOK_CODE, leave, begin=resume, end=resume)
        rt = e.alloc(0x40)
        p = self.p("rm_update_all")
        try:
            self.run_range(p + 0x10, p + 0x1A, {UC_X86_REG_EDI: rt})
        finally:
            e.uc.hook_del(h1)
            e.uc.hook_del(h2)

    # ---- children who join, leaving home
    def little_visitor(self, which=1):
        e = self.e
        p = self.p("ev_little_visitor1" if which == 1 else "ev_little_visitor2")
        self._seam_spawn_child(self.call_target(p + 0x14))
        event = e.alloc(0x20)
        e.call(p, (0,), ecx=event)

    def _seam_spawn_child(self, spawn_fn):
        def spawn(emu):
            gender = emu.arg(1)
            for slot in range(30):
                if not self.active(slot):
                    self.set_villager(slot, "Visitor" if gender != INVALID else "Adoptee", 0 if gender == 0 else 1,
                                      age=emu.arg(2))
                    self.joined = slot
                    return slot, 12
            return INVALID, 12
        self.seam(spawn_fn, spawn)

    def adoption_services(self):
        p = self.p("st_adoption")
        self._seam_spawn_child(self.call_target(p + 0xB))
        self.run_range(p, p + 0x26)

    def talent_scout(self, slot):
        e = self.e
        p = self.p("ev_talent_scout")
        self.seam(self.call_target(p + 0x12), lambda emu: (0, 8))
        event = e.alloc(0x20)
        e.w32(event + 4, self.villager(slot))
        e.w32(event + 0xC, 100)
        e.call(p, (0,), ecx=event)

    def boarding_school(self, slot):
        """The store's Boarding School: HandleUpgrade's block from the villager in focus, through the store's
        own jump table to the Boarding School case."""
        e = self.e
        p = self.p("st_boarding")
        table = e.r32(p + 0x34)
        cases = [e.r32(table + 4 * k) for k in range(6)]
        assert cases.count(p + 0x38) == 1, "no Boarding School case"
        item = 0x10B + cases.index(p + 0x38)
        store = e.alloc(0x200)
        e.w32(store + 0x160, item)
        e.w32(self.state + 0x25CC4, slot)
        self.run_range(p, p + 0x3F, {UC_X86_REG_EDI: self.state, UC_X86_REG_EBX: store})

    def college(self, slot):
        """AllVillagersTimeflowUpkeep: a child one unit short of 17Ch ages one unit and leaves for college."""
        e = self.e
        p = self.p("vm_timeflow")
        for off, pop in ((0x1ED, 8), (0x205, 12), (0x20C, 0)):
            self.seam(self.call_target(p + off), lambda emu, pop=pop: (0, pop))
        v = self.villager(slot)
        e.w32(v + S.VILLAGER_AGE, 0x17B)
        e.w32(v + 0x6AF8, NOW - 60 * SPEED)
        e.w32(v + 0x6AF4, 0)
        self.report_death_timeflow()

    # ---- Random Events
    def nested(self, fn):
        """Run more game code from inside a seam (what the game does while a dialog is open): below the
        current stack, with every register put back afterwards."""
        e = self.e
        regs = {r: e.reg(r) for r in (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
                                      UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP,
                                      UC_X86_REG_EIP)}
        top = e.sp_top
        e.sp_top = (regs[UC_X86_REG_ESP] - 0x1000) & ~0xF
        try:
            fn()
        finally:
            e.sp_top = top
            for r, v in regs.items():
                e.setreg(r, v)

    def random_event(self, title_id, email=False, other=None, choice=None, then=None):
        """A Random Event through the game's own public entry: CIslandEvents::FireEmailEvent(scene) for an
        e-mail, FireEvent(scene, false) (the hourly check) for a pop-up; each runs the private FireEvent whole:
        the candidates (CanFire, and IsEmailEvent equal to the e-mail argument), the pick, the dialog, DoModal,
        mEventHasFired. `other` is a second event of the other kind that can fire too and must not be picked.
        `choice` (0 A, 1 B) makes it an event with choices and is the button pressed; `then` is what the event
        does to the family while its dialog is open (ImpactGame runs from the dialog's OK)."""
        e = self.e
        p = self.p("ie_fire")
        entry = p - 0x93
        assert e.read(entry, 5) == bytes.fromhex("558bec6aff")
        email_entry, popup_entry = entry - 0x40, entry + 0x110
        assert e.read(email_entry, 10) == bytes.fromhex("558bec6a006a01ff7508")       # push 0; push 1 (e-mail)
        assert e.read(popup_entry, 11) == bytes.fromhex("558becff750c6a00ff7508")     # push b; push 0 (not e-mail)
        assert self.call_target(email_entry + 0xA) == entry and self.call_target(popup_entry + 0xB) == entry
        event_list = e.r32(p + 0x19)
        has_fired = e.r32(p + 0x47)
        for k in range(1, 0x61):
            e.w32(event_list + 4 * k, 0)
        vtable = e.alloc(0x40)
        e.w32(vtable + 4, e.fake_code(b"\xB0\x01\xC3"))                                  # CanFire: yes
        e.w32(vtable + 0x14, e.fake_code(b"\xB0\x01\xC3" if email else b"\x32\xC0\xC3"))   # IsEmailEvent
        e.w32(vtable + 8, e.fake_code(b"\xB8" + struct.pack("<I", title_id) + b"\xC3"))     # GetTitle
        e.w32(vtable + 0x10, e.fake_code(b"\xB0\x01\xC3" if choice is not None else b"\x32\xC0\xC3"))  # choices
        event = e.alloc(0x20)
        e.w32(event, vtable)
        e.w32(event_list + 4 * 7, event)
        e.write(has_fired + 7, b"\0")
        if other is not None:                          # an event of the other kind, also able to fire
            vt2 = e.alloc(0x40)
            e.w32(vt2 + 4, e.fake_code(b"\xB0\x01\xC3"))
            e.w32(vt2 + 0x14, e.fake_code(b"\x32\xC0\xC3" if email else b"\xB0\x01\xC3"))
            e.w32(vt2 + 8, e.fake_code(b"\xB8" + struct.pack("<I", other) + b"\xC3"))
            ev2 = e.alloc(0x20)
            e.w32(ev2, vt2)
            e.w32(event_list + 4 * 9, ev2)
        self.dialogs = []

        def ctor(emu):
            dialog, ev = emu.ecx, emu.arg(0)
            emu.w32(dialog + S.DIALOG_EVENT, ev)
            emu.w32(dialog + S.DIALOG_TITLE, self.word(title_id))
            emu.write(dialog + 0x4C, b"\x01")
            return dialog, 4
        self.seam(self.s("IE_DIALOG_CTOR"), ctor)
        def do_modal(emu):
            dialog = emu.ecx
            self.dialogs.append((dialog, e.r32(dialog + S.DIALOG_EVENT)))
            if choice is not None:
                e.w32(dialog + S.DIALOG_CHOICE, choice)
            if then is not None:
                self.nested(then)
            return 1, 8
        self.seam(self.s("DLG_DO_MODAL"), do_modal)
        self.seam(self.call_target(p + 0x58), lambda emu: (0, 0))                      # the dialog's destructor
        self.rolls = [0]
        scene = e.alloc(0x40)
        if email:
            r = e.call(email_entry, (scene,), ecx=0) & 0xFF
        else:
            r = e.call(popup_entry, (scene, 0), ecx=0) & 0xFF
        assert r == 1 and len(self.dialogs) == 1 and self.dialogs[0][1] == event
        assert e.read(has_fired + 7, 1) == b"\x01", "mEventHasFired"
        return event

    # ---- the rest
    def rename(self, slot, name, site="message"):
        """theVillagerScene's Details box: its own ChangeName(villager, text) call, then (as the game does
        right after) the text copied into the villager's name."""
        p = self.p("vs_rename_message" if site == "message" else "vs_rename_selection")
        reg = UC_X86_REG_EDI if site == "message" else UC_X86_REG_ESI
        e = self.e
        frame = e.alloc(0x2000) + 0x1000
        e.write(frame - 0x18, name.encode("ascii") + b"\0")
        e.setreg(UC_X86_REG_ESP, e.sp_top - 0x400)
        e.setreg(UC_X86_REG_EBP, frame)
        e.setreg(reg, self.villager(slot))
        e.uc.emu_start(p, p + 0x15)
        assert e.reg(UC_X86_REG_EIP) == p + 0x15
        e.write(self.villager(slot) + S.VILLAGER_NAME, name.encode("ascii")[:24].ljust(25, b"\0"))

    def evict(self):
        p = self.p("od_evict")
        self.run_range(p, p + 0xD, {UC_X86_REG_ECX: self.e.alloc(0x100)})

    def start_over(self):
        e = self.e
        p = self.p("mn_start_over")
        menu = e.alloc(0x100)
        e.w32(menu + 0xC, self.state)
        self.run_range(p, p + 0x68, {UC_X86_REG_EDI: menu})
        # Init's body is a seam; of what it resets, the family needs CFamilyTree::Reset (Init calls it), run
        # for real here, as EvictFamily calls it.
        e.call(self.target("ft_evict", 3), (), ecx=self.tree())

    def load(self, slot):
        """theGameState's Load, through the vtable slot the game calls."""
        vt = self.s("GS_VTABLE")
        return self.e.call(self.e.r32(vt + S.GS_LOAD_VSLOT), (slot,), ecx=self.state) & 0xFF

    def load_session_ends(self):
        """The game quit and loaded again: the same family, a new session (nothing the DLL kept in memory)."""
        on_load, self.on_load = self.on_load, None
        try:
            assert self.load(1) == 1
        finally:
            self.on_load = on_load

    def status(self):
        st = self.e.dll_export("B200History_Status")
        names = ("magic", "version", "requested", "resolved", "installed", "writeMask", "records", "lastLoad",
                 "wipes")
        return {n: self.e.r32(st + 4 * i) for i, n in enumerate(names)}

    def household(self, *people):
        """Villagers in slots 0.. : (name, gender[, age])."""
        for slot, person in enumerate(people):
            self.set_villager(slot, person[0], person[1], age=person[2] if len(person) > 2 else 600)


# ====================================================================== scenarios
MALE, FEMALE = 0, 1
SEX = {MALE: "Male", FEMALE: "Female"}


def member(label, name, sex, age=None, age_label="Age", head=3, body=4, indent="  "):
    """A family member inside a record, as vf1logs.dll writes one."""
    out = [f"{indent}{label}: {name}"]
    if age is not None:
        out.append(f"{indent}  {age_label}: {age}")
    return out + [f"{indent}  Sex: {SEX[sex]}", f"{indent}  Head: {head}", f"{indent}  Body: {body}"]


def self_lines(name, age, sex, age_label="Age", head=3, body=4):
    """A family member at the top of a record."""
    return [f"  Name: {name}", f"  {age_label}: {age}", f"  Sex: {SEX[sex]}", f"  Head: {head}", f"  Body: {body}"]


def founded(w: HistoryWorld):
    """Ana (founder) adopted, then married to Ben, in Save 1."""
    w.household(("Ana", FEMALE, 500), ("Ben", MALE, 520))
    w.set_active(1, 0)
    w.new_family(0)
    w.set_active(1, 1)
    w.marry(0, 1)


ANA_BEN = member("Family member", "Ana", FEMALE, 25) + member("Married", "Ben", MALE, 26)


def scenario_new_family_and_marriage(w: HistoryWorld):
    founded(w)
    assert w.lines()[0] == "Family: Ana Player (Save 1)"
    assert w.records() == [
        ("Generation 1", self_lines("Ana", 25, FEMALE) + ["  How: Founder (adopted and started the family)",
                                                         "  Generation: 1"]),
        ("Marriage 1", ANA_BEN + ["  Current spouse of Ana: Ben", "  Generation: 1"]),
    ]
    assert w.generations() == 1 and w.e.read(w.peep(1), 3) == b"Ben", "UpdateParents recorded the spouse"
    assert not w.fs.exists(f"{ROOT}1\\Data"), "no data file"


def birth_lines(child, sex, mother="Ana", father="Ben", born_as="Single birth", father_known=True):
    out = [f"  Child: {child}", f"    Sex: {SEX[sex]}", "    Head: 3", "    Body: 4",
           f"  Mother: {mother}", "    Head: 3", "    Body: 4"]
    out += [f"  Father: {father}", "    Head: 3", "    Body: 4"] if father_known else ["  Father: (unknown)"]
    return out + [f"  Born as: {born_as}", "  Generation: 1"]


def conception_lines(babies, mother=("Ana", 25), father=("Ben", 26)):
    return (member("Mother", mother[0], FEMALE, mother[1], "Age at conception")
            + member("Father", father[0], MALE, father[1], "Age at conception")
            + [f"  Babies Nursing: {babies}", "  Generation: 1"])


def scenario_conception_and_birth_single(w: HistoryWorld):
    founded(w)
    assert w.impregnate(0, 1, (99,)) == 1
    baby = w.spawned[0]
    assert w.e.r32(w.villager(0) + S.VILLAGER_CARRIED) == 1
    w.deliver(0)
    assert w.active(baby) == 1 and w.e.r32(w.villager(0) + S.VILLAGER_PREGNANT) == 0
    rec = w.records()
    assert rec[-2] == ("Conception 1", conception_lines(1))
    assert rec[-1] == ("Birth 1", birth_lines(f"Baby {baby}", baby % 2))


def scenario_the_father_after_a_load(w: HistoryWorld):
    """A birth after the game was quit and loaded: the father is the record's other parent whose head and body
    Impregnate kept on the mother; another man with other looks is not."""
    founded(w)
    w.e.w32(w.villager(1) + S.VILLAGER_HEAD, 7)
    w.e.w32(w.peep(1) + S.PEEP_HEAD, 7)
    w.impregnate(0, 1, (99,))
    baby = w.spawned[0]
    assert w.e.r32(w.villager(0) + S.VILLAGER_FATHER_HEAD) == 7, "Impregnate kept the father's head"
    w.load_session_ends()
    w.deliver(0)
    expected = birth_lines(f"Baby {baby}", baby % 2)
    expected[expected.index("  Father: Ben") + 1] = "    Head: 7"
    assert w.last() == ("Birth 1", expected)
    w.impregnate(0, 1, (99,))
    baby2 = w.spawned[0]
    w.load_session_ends()
    w.e.w32(w.villager(0) + S.VILLAGER_FATHER_HEAD, 9)        # looks the record's spouse does not have
    w.deliver(0)
    assert w.last() == ("Birth 2", birth_lines(f"Baby {baby2}", baby2 % 2, father_known=False))


def scenario_twins(w: HistoryWorld):
    founded(w)
    assert w.impregnate(0, 1, (0, 99)) == 1
    assert w.e.r32(w.villager(0) + S.VILLAGER_CARRIED) == 2 and len(w.spawned) == 2
    w.deliver(0)
    rec = w.records()
    assert rec[-3] == ("Conception 1", conception_lines(2))
    assert [h for h, _ in rec[-2:]] == ["Birth 1", "Birth 2"]
    assert all("  Born as: Twin" in lines for _, lines in rec[-2:])


def scenario_triplets(w: HistoryWorld):
    founded(w)
    assert w.impregnate(0, 1, (0, 0)) == 1
    assert w.e.r32(w.villager(0) + S.VILLAGER_CARRIED) == 3 and len(w.spawned) == 3
    w.deliver(0)
    rec = w.records()
    assert rec[-4] == ("Conception 1", conception_lines(3))
    assert [h for h, _ in rec[-3:]] == ["Birth 1", "Birth 2", "Birth 3"]
    assert all("  Born as: Triplet" in lines for _, lines in rec[-3:])
    assert all(w.active(s) for s in w.spawned)


def death_lines(name, age, sex, cause, role, widowed=None):
    out = [f"  Name: {name}", f"  Age at death: {age}", f"  Sex: {SEX[sex]}", f"  Cause of death: {cause}",
           "  Head: 3", "  Body: 4", f"  Family role: {role}", "  Generation: 1"]
    return out + ([f"  Current spouse of {widowed}: (none)"] if widowed else [])


def scenario_child_dies(w: HistoryWorld):
    founded(w)
    w.impregnate(0, 1, (99,))
    baby = w.spawned[0]
    w.deliver(0)
    w.e.w32(w.villager(baby) + S.VILLAGER_AGE, 100)
    w.kill(baby, 0)
    w.report_death_timeflow()
    assert w.active(baby) == 0, "the upkeep deactivated the dead child"
    assert w.last() == ("Death 1", death_lines(f"Baby {baby}", 5, baby % 2, "Disease", "Child"))
    assert s32(w.e.r32(w.peep(2) + S.PEEP_SLOT)) == -1, "ReportDeath ran for real"
    # the same death is not reported twice
    w.set_active(baby, 1)
    w.report_death_timeflow()
    assert [h for h in w.headings() if h.startswith("Death")] == ["Death 1"]


def remarriage_lines(head, head_age, head_sex, spouse, spouse_age, spouse_sex, earlier, how):
    return (member("Family member", head, head_sex, head_age) + member("Married", spouse, spouse_sex, spouse_age)
            + ["  Remarried: yes", f"  Earlier spouse: {earlier} ({how})", f"  Current spouse of {head}: {spouse}",
               "  Generation: 1"])


def scenario_spouse_dies_and_remarriage(w: HistoryWorld):
    """A spouse who dies with no child recorded: CFamilyTree::ReportDeath erases the record (valid byte 0); the
    log's own Marriage and Death records say the next marriage is a remarriage."""
    founded(w)
    w.kill(1, 2)
    w.e.w32(w.villager(1) + S.VILLAGER_AGE, 1600)
    w.death_behavior(1)
    assert w.active(1) == 0
    assert w.last() == ("Death 1", death_lines("Ben", 80, MALE, "Old age", "Parent (married in)", widowed="Ana"))
    assert w.e.read(w.peep(1) + S.PEEP_VALID, 1) == b"\0", "the game erased the childless spouse's record"
    w.set_villager(1, "Cal", MALE, age=700)
    w.marry(0, 1)
    assert w.last() == ("Marriage 2", remarriage_lines("Ana", 25, FEMALE, "Cal", 35, MALE, "Ben", "died"))
    assert w.e.read(w.peep(1), 3) == b"Cal"


def scenario_spouse_with_a_child_dies_and_remarriage(w: HistoryWorld):
    """A spouse who dies with a child recorded keeps the record (slot -1); the remarriage overwrites it."""
    founded(w)
    w.impregnate(0, 1, (99,))
    w.deliver(0)
    w.kill(1, 0)
    w.report_death_timeflow()
    assert s32(w.e.r32(w.peep(1) + S.PEEP_SLOT)) == -1 and w.e.read(w.peep(1) + S.PEEP_VALID, 1) == b"\x01"
    assert w.last() == ("Death 1", death_lines("Ben", 26, MALE, "Disease", "Parent (married in)", widowed="Ana"))
    w.set_villager(1, "Cal", MALE, age=700)
    w.marry(0, 1)
    assert w.last() == ("Marriage 2", remarriage_lines("Ana", 25, FEMALE, "Cal", 35, MALE, "Ben", "died"))


def scenario_head_dies_and_the_widow_remarries(w: HistoryWorld):
    """The generation's head dies with no child recorded: the game moves the spouse into parent 1. The widow's
    next marriage is a remarriage."""
    founded(w)
    w.kill(0, 2)
    w.report_death_timeflow()
    assert w.last() == ("Death 1", death_lines("Ana", 25, FEMALE, "Old age", "Parent", widowed="Ben"))
    assert w.e.read(w.peep(0), 3) == b"Ben" and w.e.read(w.peep(1) + S.PEEP_VALID, 1) == b"\0", \
        "ReportDeath moved the spouse into parent 1"
    w.set_villager(2, "Dot", FEMALE, age=560)
    w.marry(1, 2)
    assert w.last() == ("Marriage 2", remarriage_lines("Ben", 26, MALE, "Dot", 28, FEMALE, "Ana", "died"))


def divorce_lines(head, head_sex, spouse, spouse_age, spouse_sex):
    return (member("Family member", head, head_sex) + member("Divorced", spouse, spouse_sex, spouse_age)
            + ["  How: Divorce Spouse", f"  Current spouse of {head}: (none)", "  Generation: 1"])


def scenario_divorce_and_remarriage(w: HistoryWorld):
    founded(w)
    w.divorce()
    assert w.resets == [w.villager(1)], "the generated block reset the spouse"
    assert w.e.read(w.peep(1), S.PEEP_RECORD_SIZE) == bytes(S.PEEP_RECORD_SIZE), "parent 2 cleared"
    assert w.last() == ("Divorce 1", divorce_lines("Ana", FEMALE, "Ben", 26, MALE))
    w.set_villager(2, "Dan", MALE, age=640)
    w.marry(0, 2)
    assert w.last() == ("Marriage 2", remarriage_lines("Ana", 25, FEMALE, "Dan", 32, MALE, "Ben", "divorced"))


def scenario_same_sex_marriage(w: HistoryWorld):
    """Two women through the same accepted-marriage call, divorce and remarriage: both named, each with her
    own sex, the same records as any marriage."""
    w.household(("Ana", FEMALE, 500), ("Bea", FEMALE, 520))
    w.set_active(1, 0)
    w.new_family(0)
    w.set_active(1, 1)
    w.marry(0, 1)
    assert w.last() == ("Marriage 1", member("Family member", "Ana", FEMALE, 25) + member("Married", "Bea", FEMALE, 26)
                        + ["  Current spouse of Ana: Bea", "  Generation: 1"])
    w.divorce()
    assert w.last() == ("Divorce 1", divorce_lines("Ana", FEMALE, "Bea", 26, FEMALE))
    w.set_villager(2, "Cia", FEMALE, age=560)
    w.marry(2, 0)                                              # the other order: the head is still Ana
    assert w.last() == ("Marriage 2", remarriage_lines("Ana", 25, FEMALE, "Cia", 28, FEMALE, "Bea", "divorced"))


def scenario_remarriage_over_a_dead_spouse_the_log_never_saw(w: HistoryWorld):
    """The record already holds a spouse who died (slot -1) before the log began: the log has no Marriage record
    of them, so the next marriage is written as a marriage (nothing guessed)."""
    w.household(("Ana", FEMALE, 500))
    w.new_family(0)
    w.write_peep(1, "Old", MALE, -1)
    w.set_villager(1, "Cal", MALE, age=700)
    w.marry(0, 1)
    assert w.last() == ("Marriage 1", member("Family member", "Ana", FEMALE, 25) + member("Married", "Cal", MALE, 35)
                        + ["  Current spouse of Ana: Cal", "  Generation: 1"])


def scenario_random_events(w: HistoryWorld):
    """Random Events: a pop-up from the hourly FireEvent and an e-mail from FireEmailEvent, each with an event
    of the other kind able to fire too (FireEvent's own scan leaves it out); the record says which kind, and the
    choice on an event with choices."""
    founded(w)
    w.random_event(0x900, other=0x882, choice=0)
    w.random_event(0x882, email=True, other=0x900)
    w.random_event(0x97B, choice=1)
    rec = w.records()
    assert rec[-3:] == [
        ("Random Event 1", ["  Popup Event: The Little Visitor", "  Choice: A", "  Generation: 1"]),
        ("Random Event 2", ["  Email Event: Subject: A Secret Admirer", "  Generation: 1"]),
        ("Random Event 3", ["  Popup Event: The Talent Scout", "  Choice: B", "  Generation: 1"]),
    ]


def scenario_random_event_title_is_the_dialogs(w: HistoryWorld):
    """CIslandEventDialog's real constructor head stores the event and the title the dialog draws."""
    e = w.e
    ctor = w.s("IE_DIALOG_CTOR")
    title_id = 0x97B
    vtable = e.alloc(0x40)
    e.w32(vtable + 8, e.fake_code(b"\xB8" + struct.pack("<I", title_id) + b"\xC3"))
    event = e.alloc(0x20)
    e.w32(event, vtable)
    for off, pop, value in ((0x32, 4, None), (0xBC, 0, 0x1234), (0xCE, 0, 0x5678)):
        w.seam(w.call_target(ctor + off), lambda emu, pop=pop, value=value: (value if value is not None else emu.ecx, pop))
    dialog = e.alloc(0xA00)
    w.run_range(ctor, ctor + 0xEC, {UC_X86_REG_ECX: dialog}, stack=(0x70001000, event))
    assert e.r32(dialog + S.DIALOG_EVENT) == event
    assert e.cstr(e.r32(dialog + S.DIALOG_TITLE)) == "The Talent Scout"


def scenario_the_choice_is_the_dialogs(w: HistoryWorld):
    """CIslandEventDialog::HandleMessage for real: button 3 (choice B) stores 1 at +830h, the field the record
    reads; OK then runs the event's ImpactGame with it."""
    e = w.e
    handler = w.p("ied_handle_message")
    vtable = e.alloc(0x40)
    calls = []
    for slot in (0x10, 0x2C, 0x30, 0x34, 0x38):
        stub = e.fake_code(b"\xC3")
        e.w32(vtable + slot, stub)
        args = 1 if slot in (0x2C, 0x30, 0x38) else 0

        def method(emu, slot=slot, args=args):
            calls.append((slot, emu.arg(0) if args else None))
            return (1 if slot == 0x10 else 0x900 if slot == 0x2C else 0), 4 * args
        w.seam(stub, method)
    event = e.alloc(0x20)
    e.w32(event, vtable)
    dialog = e.alloc(0xA00)
    e.w32(dialog + S.DIALOG_EVENT, event)
    for off, pop in ((0x37, 0), (0x49, 0), (0x66, 4), (0x73, 4), (0xA0, 4), (0xAD, 4)):
        w.seam(w.call_target(handler + off), lambda emu, pop=pop: (0, pop))
    e.call(handler, (8, 3), ecx=dialog)
    assert e.r32(dialog + S.DIALOG_CHOICE) == 1
    e.call(handler, (8, 1), ecx=dialog)
    assert (0x30, 1) in calls, "OK ran ImpactGame with choice B"


def scenario_children_join_and_leave(w: HistoryWorld):
    founded(w)
    w.random_event(0x900, choice=0, then=lambda: w.little_visitor(1))
    lv = w.joined
    w.adoption_services()
    ad = w.joined
    rec = w.records()
    assert rec[-3:] == [
        ("Random Event 1", ["  Popup Event: The Little Visitor", "  Choice: A", "  Generation: 1"]),
        ("Arrived 1", self_lines("Visitor", 3, MALE, "Age at arrival")
         + ["  How: Adopted (Popup Event: The Little Visitor)", "  Family role: Child", "  Generation: 1"]),
        ("Arrived 2", self_lines("Adoptee", 3, FEMALE, "Age at arrival")
         + ["  How: Adopted (Adoption Services)", "  Family role: Child", "  Generation: 1"]),
    ]
    w.random_event(0x97B, choice=0, then=lambda: w.talent_scout(lv))
    rec = w.records()
    assert rec[-2:] == [
        ("Random Event 2", ["  Popup Event: The Talent Scout", "  Choice: A", "  Generation: 1"]),
        ("Left Home 1", self_lines("Visitor", 3, MALE)
         + ["  What happened: Left home with The Talent Scout (Popup Event)", "  Generation: 1"]),
    ]
    w.boarding_school(ad)
    assert w.last() == ("Left Home 2", self_lines("Adoptee", 3, FEMALE)
                        + ["  What happened: Sent to Boarding School", "  Generation: 1"])
    w.set_villager(5, "Eve", FEMALE, age=0x17B)
    w.college(5)
    assert w.e.read(w.villager(5) + S.VILLAGER_LEFT_HOME, 1) == b"\x01"
    assert w.last() == ("Left Home 3", self_lines("Eve", 19, FEMALE)
                        + ["  What happened: Eve is going to college!", "  Generation: 1"])


def scenario_next_generation(w: HistoryWorld):
    founded(w)
    w.impregnate(0, 1, (99,))
    heir = w.spawned[0]
    w.deliver(0)
    w.e.w32(w.villager(heir) + S.VILLAGER_AGE, 500)
    w.next_generation(heir, 0)
    assert w.generations() == 2
    assert w.last() == ("New Generation 1", self_lines(f"Baby {heir}", 25, heir % 2)
                        + ["  How: Heir (inherited the house)", "  Generation: 2"])


def scenario_evict_then_new_family_keeps_the_log(w: HistoryWorld):
    founded(w)
    w.evict()
    assert s32(w.e.r32(w.tree())) == 1, "EvictFamily set the evicted flag"
    assert w.last() == ("Evict Family 1", ["  Family members: Ana, Ben", "  Generation: 1"])
    for slot in range(30):
        w.set_active(slot, 0)
    w.set_villager(3, "Fay", FEMALE, age=500)
    w.new_family(3)
    rec = w.records()
    assert rec[0][0] == "Generation 1" and rec[-1] == ("Generation 2", self_lines("Fay", 25, FEMALE)
                                                       + ["  How: Founder (after the eviction)", "  Generation: 1"])


def scenario_start_over_wipes_the_slot(w: HistoryWorld):
    founded(w)
    w.fs.write(f"{ROOT}1\\Backups\\keep.txt", b"kept")
    w.start_over()
    assert ("Init", w.state) in w.calls
    assert w.fs.under(f"{ROOT}1") == [w.fs.key(f"{ROOT}1\\Backups\\keep.txt")], "only Backups is kept"
    w.household(("Gus", MALE, 500))
    w.new_family(0)
    assert w.records() == [
        ("Start Over 1", ["  The earlier family's history was cleared."]),
        ("Generation 1", self_lines("Gus", 25, MALE) + ["  How: Founder (adopted and started the family)",
                                                       "  Generation: 1"]),
    ]


def scenario_rename_in_the_details_box(w: HistoryWorld):
    """theVillagerScene's two ChangeName calls: a record only when the name really changes."""
    founded(w)
    w.impregnate(0, 1, (99,))
    baby = w.spawned[0]
    w.deliver(0)
    n = len(w.records())
    w.rename(baby, f"Baby {baby}", site="selection")        # unchanged: no record
    assert len(w.records()) == n
    w.rename(baby, "Zed", site="message")
    assert w.last() == ("Renamed 1", [f"  Old name: Baby {baby}", "  New name: Zed", "  Age: 0",
                                      f"  Sex: {SEX[baby % 2]}", "  Head: 3", "  Body: 4", "  Generation: 1"])
    assert w.e.read(w.peep(2), 4) == b"Zed\0", "CFamilyTree::ChangeName ran for real"
    w.rename(0, "Anya", site="selection")
    assert w.last()[0] == "Renamed 2" and w.last()[1][:2] == ["  Old name: Ana", "  New name: Anya"]


def scenario_new_family_wipes_the_old_one(w: HistoryWorld):
    founded(w)
    w.fs.write(f"{ROOT}2\\Logs\\Family History\\Family History 1.txt", b"another slot\r\n")
    w.household(("Hal", MALE, 500))
    w.new_family(0)
    assert w.headings() == ["Generation 1"]
    assert w.fs.read(f"{ROOT}2\\Logs\\Family History\\Family History 1.txt") == b"another slot\r\n"


def scenario_backfill_once(w: HistoryWorld):
    """An existing family loaded for the first time: its Family Tree, once, marked backfilled."""
    def loaded(slot):
        e = w.e
        e.w32(w.tree() + 4, 2)
        e.write(w.record(1), b"\x01")
        w.write_peep(0, "Ida", FEMALE, -1, gen=1)
        w.write_peep(1, "Jon", MALE, -1, gen=1)
        e.w32(w.record(1) + S.RECORD_CHILD_COUNT, 2)
        w.write_peep(2, "Kim", FEMALE, 4, gen=1)
        w.write_peep(3, "Lou", MALE, -1, gen=1)
        e.write(w.record(2), b"\x01")
        w.write_peep(0, "Kim", FEMALE, 4, gen=2)
        w.write_peep(1, "Max", MALE, 5, gen=2)
        w.set_slot(slot)
        w.set_player("Ida Player")
    w.on_load = loaded
    assert w.load(3) == 1 and w.loads == [3]
    assert w.lines(slot=3)[0] == "Family: Ida Player (Save 3)"
    note = "  Note: Recorded afterwards (from the save's Family Tree: no dates, ages, causes, twins or earlier spouses)"
    assert w.records(slot=3) == [
        ("Family Tree 1", member("Parent", "Ida", FEMALE) + ["    Died: yes"]
         + member("Parent (married in)", "Jon", MALE) + ["    Died: yes"]
         + member("Child", "Kim", FEMALE) + member("Child", "Lou", MALE) + ["    Died: yes"]
         + ["  Generation: 1", note]),
        ("Family Tree 2", member("Parent", "Kim", FEMALE) + member("Parent (married in)", "Max", MALE)
         + ["  Current spouse of Kim: Max", "  Generation: 2", note]),
    ]
    assert all(line.startswith("[backfilled, no date] ") for line in w.lines(slot=3)[1:] if line.startswith("["))
    assert w.status()["lastLoad"] == 2
    w.load(3)
    assert len(w.records(slot=3)) == 2, "never backfilled twice"
    assert w.status()["lastLoad"] == 1


def scenario_a_load_with_no_family_writes_nothing(w: HistoryWorld):
    w.load(2)
    assert not w.fs.exists(w.history_path(1, 2))


def scenario_the_log_rolls_after_2000_records(w: HistoryWorld):
    founded(w)
    filler = "".join(f"{STAMP}Filler {i}\r\n  Generation: 1\r\n\r\n" for i in range(1998))
    w.fs.write(w.history_path(1), w.fs.read(w.history_path(1)) + filler.encode("latin-1"))
    assert len(w.records(files=1)) == 2000
    w.random_event(0x900)
    assert len(w.records(files=1)) == 2000
    assert w.lines(2)[:2] == ["Family: Ana Player (Save 1)", STAMP + "Random Event 1"]
    w.random_event(0x97B)
    assert w.last()[0] == "Random Event 2" and w.lines(2)[-3] == "  Popup Event: The Talent Scout"


def scenario_numbers_continue_across_files(w: HistoryWorld):
    founded(w)
    w.fs.write(w.history_path(2), ("Family: Ana Player (Save 1)\r\n" + STAMP + "Death 41\r\n  Name: Old\r\n\r\n").encode())
    w.kill(1, 2)
    w.report_death_timeflow()
    assert w.last()[0] == "Death 42" and STAMP + "Death 42" in w.lines(2)


def scenario_family_story_end_to_end(w: HistoryWorld):
    """One family through every hook, one log."""
    founded(w)
    w.random_event(0x900, choice=0, then=lambda: w.little_visitor(1))
    w.impregnate(0, 1, (0, 99))
    twins = list(w.spawned)
    w.deliver(0)
    w.kill(twins[0], 1)
    w.report_death_timeflow()
    w.divorce()
    w.set_villager(9, "Ned", MALE, age=700)
    w.marry(0, 9)
    w.kill(9, 2)
    w.e.w32(w.villager(9) + S.VILLAGER_AGE, 1500)
    w.death_behavior(9)
    w.set_villager(10, "Oli", MALE, age=800)
    w.marry(0, 10)
    w.impregnate(0, 10, (0, 0))
    w.deliver(0)
    w.e.w32(w.villager(twins[1]) + S.VILLAGER_AGE, 500)
    w.next_generation(twins[1], 1)
    assert w.headings() == ["Generation 1", "Marriage 1", "Random Event 1", "Arrived 1", "Conception 1", "Birth 1",
                            "Birth 2", "Death 1", "Divorce 1", "Marriage 2", "Death 2", "Marriage 3", "Conception 2",
                            "Birth 3", "Birth 4", "Birth 5", "New Generation 1"]
    rec = dict(w.records())
    assert "  Earlier spouse: Ben (divorced)" in rec["Marriage 2"]
    assert "  Earlier spouse: Ned (died)" in rec["Marriage 3"]
    assert "  Current spouse of Ana: (none)" in rec["Death 2"]
    assert all("  Born as: Triplet" in rec[f"Birth {n}"] for n in (3, 4, 5))
    assert all("  Father: Oli" in rec[f"Birth {n}"] for n in (3, 4, 5))


def scenario_a_loss_the_log_never_saw_is_not_guessed(w: HistoryWorld):
    """Ana divorced Ben and married Cal; Cal then left the record while the log was not running. Her next
    marriage names Cal (the last spouse the log saw her marry), with no reason: the log never saw him go."""
    founded(w)
    w.divorce()
    w.set_villager(2, "Cal", MALE, age=700)
    w.marry(0, 2)
    assert "  Earlier spouse: Ben (divorced)" in w.last()[1]
    w.e.write(w.peep(1), bytes(S.PEEP_RECORD_SIZE))          # gone without any hook seeing it
    w.set_villager(3, "Dan", MALE, age=640)
    w.marry(0, 3)
    assert w.last()[1][10:12] == ["  Remarried: yes", "  Earlier spouse: Cal"]


ALL = [scenario_rename_in_the_details_box, scenario_same_sex_marriage, scenario_a_loss_the_log_never_saw_is_not_guessed,
       scenario_new_family_and_marriage, scenario_conception_and_birth_single, scenario_the_father_after_a_load,
       scenario_twins, scenario_triplets, scenario_child_dies, scenario_spouse_dies_and_remarriage,
       scenario_spouse_with_a_child_dies_and_remarriage, scenario_head_dies_and_the_widow_remarries,
       scenario_remarriage_over_a_dead_spouse_the_log_never_saw, scenario_divorce_and_remarriage,
       scenario_random_events, scenario_random_event_title_is_the_dialogs, scenario_the_choice_is_the_dialogs,
       scenario_children_join_and_leave, scenario_next_generation, scenario_evict_then_new_family_keeps_the_log,
       scenario_start_over_wipes_the_slot, scenario_new_family_wipes_the_old_one, scenario_backfill_once,
       scenario_a_load_with_no_family_writes_nothing, scenario_the_log_rolls_after_2000_records,
       scenario_numbers_continue_across_files, scenario_family_story_end_to_end]


# ====================================================================== the setting off
def scenario_setting_off_writes_nothing(w: HistoryWorld):
    """B200History_Startup with FamilyHistory not 1 (the ini off, or no ini: GetPrivateProfileIntW answers the
    default 0): nothing planned, no byte of the game changed, no file written."""
    e = w.e
    seen = []

    def module_name(emu):
        emu.write(emu.arg(1), DLL_PATH.encode("utf-16-le") + b"\0\0")
        return len(DLL_PATH), 12

    def profile(emu):
        seen.append((emu.wstr(emu.arg(0)), emu.wstr(emu.arg(1)), emu.arg(2), emu.wstr(emu.arg(3))))
        return emu.arg(2), 16
    e.imports.update({"GetModuleFileNameW": module_name, "GetPrivateProfileIntW": profile})
    e.call(e.dll_export("B200History_Startup"))
    assert seen == [("Patches", "FamilyHistory", 0, "C:\\Game\\Virtual Families 2 Patcher Files\\vf2history.ini")]
    st = w.status()
    assert st["requested"] == 0 and st["installed"] == 0 and st["writeMask"] == 0
    assert w.changed_code() == set()
    assert w.e.r32(w.s("GS_VTABLE") + S.GS_LOAD_VSLOT) == w.s("GS_LOAD")
    status, writes = w.test_plan(False)
    assert (status, writes) == (0, [])
    assert w.fs.files == {}


def scenario_setting_on_installs_everything(w: HistoryWorld):
    e = w.e

    def module_name(emu):
        emu.write(emu.arg(1), DLL_PATH.encode("utf-16-le") + b"\0\0")
        return len(DLL_PATH), 12
    e.imports.update({"GetModuleFileNameW": module_name, "GetPrivateProfileIntW": lambda emu: (1, 16)})
    e.call(e.dll_export("B200History_Startup"))
    st = w.status()
    assert st["requested"] == 1 and st["resolved"] == 1 and st["installed"] == 1
    n = len(S.CALL_HOOKS) + len(S.ENTRY_HOOKS) + 1
    assert st["writeMask"] == (1 << n) - 1
    sites = [w.s(name) for name in S.CALL_HOOKS] + [w.s(name) for name in S.ENTRY_HOOKS]
    changed = w.changed_code()
    assert changed <= {a + k for a in sites for k in range(5)}, "nothing but the planned calls and the entry jmp"
    for name in S.CALL_HOOKS:          # each call now reaches the DLL
        at = w.s(name)
        assert w.e.read(at, 1) == b"\xE8" and DLL_BASE <= w.call_target(at) < DLL_BASE + 0x100000, name
    entry = w.s("V_IMPREGNATE")
    assert w.e.read(entry, 1) == b"\xE9"
    assert DLL_BASE <= (entry + 5 + w.e.r32(entry + 1)) & 0xFFFFFFFF < DLL_BASE + 0x100000
    assert DLL_BASE <= w.e.r32(w.s("GS_VTABLE") + S.GS_LOAD_VSLOT) < DLL_BASE + 0x100000


OFF = [scenario_setting_off_writes_nothing, scenario_setting_on_installs_everything]


# ====================================================================== the executable's own loader
EXE_PATH = "C:\\Game\\Virtual Families 2 - B204.exe"
TIME_DLL_PATH = "C:\\Game\\Virtual Families 2 Patcher Files\\vf2time_b200.dll"
KIDS_DLL_PATH = "C:\\Game\\Virtual Families 2 Patcher Files\\vf2kids_b200.dll"


def section_va(exe_path, name):
    import pefile
    pe = pefile.PE(str(exe_path), fast_load=True)
    found = [pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress for s in pe.sections if s.Name.rstrip(b"\0") == name]
    assert len(found) == 1, f"the executable has no {name!r} section"
    return found[0]


def run_loader(exe, dll, delta, history_flag, ini, time_flag=0, kids_flag=0, dll_present=True):
    """Run the executable's REAL loader wrapper (theGame::Init's first call) with this DLL as the one it loads
    for the Family History log; the Time Controls and Up to 28 Children DLLs are absent. history_flag None
    leaves the .vf2hist byte the executable file has. Returns (world, wrapper result, calls log)."""
    import b200_time_scenarios as T
    w = HistoryWorld(exe, dll, delta, install=False)
    e = w.e
    _flag, _call, wrapper = T.loader_sites(exe)
    log = []
    if history_flag is not None:
        e.write(section_va(exe, b".vf2hist") + delta, bytes([history_flag]))
    e.write(section_va(exe, b".vf2time") + delta, bytes([time_flag]))
    e.write(section_va(exe, b".vf2kids") + delta, bytes([kids_flag]))

    def wide(addr, text):
        e.write(addr, text.encode("utf-16-le") + b"\0\0")
        return len(text)

    def exe_get_module_file_name(emu):
        log.append("exe:GetModuleFileNameW")
        return wide(emu.arg(1), EXE_PATH), 12

    def exe_load_library(emu):
        path = emu.wstr(emu.arg(0))
        log.append("exe:LoadLibraryW " + path)
        return (DLL_BASE if path == DLL_PATH and dll_present else 0), 4

    def exe_get_proc(emu):
        name = emu.cstr(emu.arg(1))
        log.append("exe:GetProcAddress " + name)
        return (emu.dll_export("B200History_Startup") if name == "B200History_Startup" else 0), 8
    e.bind_exe_imports({"GetModuleFileNameW": exe_get_module_file_name, "LoadLibraryW": exe_load_library,
                        "GetProcAddress": exe_get_proc})

    def dll_get_module_file_name(emu):
        log.append("dll:GetModuleFileNameW")
        return wide(emu.arg(1), DLL_PATH), 12

    def dll_get_ini(emu):
        log.append("dll:GetPrivateProfileIntW " + emu.wstr(emu.arg(0)) + " " + emu.wstr(emu.arg(1)) + " "
                   + emu.wstr(emu.arg(3)))
        return ini, 16
    e.imports.update({"GetModuleFileNameW": dll_get_module_file_name, "GetPrivateProfileIntW": dll_get_ini})
    w.code_before = w._code()
    e.call(e.dll_export("B200History_TestSetModule"), (DLL_BASE,))
    result = e.call(wrapper + delta, ())
    return w, result, log


def scenario_loader_cases(exe, dll, delta):
    """The dormant loader: byte 0 never loads the DLL; byte 1 loads it (after the Time Controls and Up to 28
    Children DLLs); the DLL installs only when its ini says 1, and then exactly its planned writes are made."""
    for flag, ini, time_flag, kids_flag, present, installs in (
            (0, 1, 0, 0, True, False), (1, 0, 0, 0, True, False), (1, 1, 0, 0, False, False),
            (1, 1, 0, 0, True, True), (1, 1, 1, 1, True, True), (0, 1, 1, 1, True, False)):
        w, result, log = run_loader(exe, dll, delta, flag, ini, time_flag, kids_flag, present)
        assert result == w.state, "the wrapper must return theGameState::Get()'s result"
        loads = [x for x in log if x.startswith("exe:LoadLibraryW")]
        expect = ([f"exe:LoadLibraryW {TIME_DLL_PATH}"] if time_flag else []) + \
                 ([f"exe:LoadLibraryW {KIDS_DLL_PATH}"] if kids_flag else []) + \
                 ([f"exe:LoadLibraryW {DLL_PATH}"] if flag else [])
        assert loads == expect, (flag, ini, time_flag, kids_flag, log)
        changed = w.changed_code()
        st = w.status()
        if not installs:
            assert not changed, (flag, ini, present, len(changed))
            assert st["installed"] == 0
            if flag and present:
                assert st["requested"] == (1 if ini else 0)
                assert [x for x in log if x.startswith("dll:GetPrivateProfileIntW")] == [
                    "dll:GetPrivateProfileIntW Patches FamilyHistory "
                    "C:\\Game\\Virtual Families 2 Patcher Files\\vf2history.ini"]
            continue
        assert st["requested"] == 1 and st["resolved"] == 1 and st["installed"] == 1
        sites = [w.s(name) for name in S.CALL_HOOKS] + [w.s(name) for name in S.ENTRY_HOOKS]
        assert changed <= {a + k for a in sites for k in range(5)}
        for name in S.CALL_HOOKS:
            assert DLL_BASE <= w.call_target(w.s(name)) < DLL_BASE + 0x100000, name
        # and it works: a new family is logged
        w.household(("Ana", FEMALE, 500))
        w.new_family(0)
        assert w.headings() == ["Generation 1"]
    # the wrapper twice: the DLL is loaded once
    import b200_time_scenarios as T
    w, result, log = run_loader(exe, dll, delta, 1, 1)
    again = w.e.call(T.loader_sites(exe)[2] + delta, ())
    assert again == w.state
    assert len([x for x in log if x.startswith("exe:LoadLibraryW")]) == 1
