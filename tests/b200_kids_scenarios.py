"""Scenarios for the Up to 28 Children DLL (vf2kids_b200.dll), run under tests/b200_time_emu.py.

Each scenario takes a fresh KidsWorld and raises AssertionError on a wrong result. A KidsWorld is
the REAL B200 executable (built from this branch: it has the .vf2kidt table) and the REAL compiled
test DLL in one unicorn address space, with the DLL's hooks written exactly as its own plan says.

Game code that runs for real: CFamilyTree::AddOffspring, EmptyOffspringSlots (the DLL's
replacement), CountSurvivingChildren, ReportDeath, Reset, StartNextGeneration (with
UpdateCurrentFamilyRecord, ldwStrCopy), CAdoptionScene::CreateNextGenerationCandidates and
GetNextCandidate, CVillagerManager::FindEmptySlot, ClonePeepAsAdult and GetVillager,
theGameState::Get, and B200's CVillager::Impregnate from its first instruction to its `ret 14h`
(the twin / triplet decision, B200's forced-count cave, the reserved baby slots, AddOffspring
for each baby).

Seams (recorded, never real): the bodies of theGameState::Save and ::Load after their first
instructions (a fake save file is written / nothing is read), MakeGameStatePath (a fixed folder),
the family-tree appearance observer B200 puts on UpdatePeepRecord, CVillager::CloneAsAdult (copies
the identity fields and makes the clone an adult; the real one is 0x152 bytes of AI, skills and
animation resets), the spawn calls Impregnate makes (they take the first free slot, as
FindEmptySlot does), GetMatriarch / GetPatriarch, ldwGameState::GetRandom (scripted rolls), the
achievement counters, and the DLL's Win32 file imports (an in-memory file system).
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "tools"))
import b200_kids_sites as S  # noqa: E402
import gen_b200_kids_sites as G  # noqa: E402

from b200_time_emu import Emu, EmuError  # noqa: E402
from unicorn.x86_const import UC_X86_REG_EBP, UC_X86_REG_ESP  # noqa: E402

STRIDE = S.VILLAGER_STRIDE
SAVE_DIR = "C:\\Users\\Tester\\Documents\\LDW\\VF2 Kids Test"
DLL_PATH = "C:\\Game\\Virtual Families 2 Patcher Files\\vf2kids_b200.dll"
INVALID = 0xFFFFFFFF
ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND, ERROR_ALREADY_EXISTS = 2, 3, 183
ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION = 5, 32, 33
ERROR_FILENAME_EXCED_RANGE = 206
OPEN_TRIES = 5                 # the DLL's kOpenTries: a shut file is opened this many times

_PROVED = {}


def proved(exe_path):
    """(model of the core variant, derived sites of this executable, pin locations), cached."""
    key = str(exe_path)
    if key not in _PROVED:
        core = os.environ.get("VF2_B200_CORE_EXE") or key
        model = G.validate(Path(core).read_bytes())
        exe = G.Exe(Path(key).read_bytes())
        _PROVED[key] = (model, G.resolve(exe, model), G.locate(exe, model))
    return _PROVED[key]


def s32(v):
    return struct.unpack("<i", struct.pack("<I", v & 0xFFFFFFFF))[0]


class FileSystem:
    """The DLL's Win32 file imports over a dict (case-insensitive paths)."""

    def __init__(self):
        self.files = {}
        self.dirs = set()
        self.handles = {}
        self.next = 0x100
        self.last_error = 0
        self.log = []
        self.shut = {}           # key -> opens still refused (None: every one), as another program holding it
        self.shut_error = ERROR_SHARING_VIOLATION
        self.sleeps = []
        self.max_path = None     # MoveFileExA refuses a destination longer than this

    def hold(self, path, opens=None, error=ERROR_SHARING_VIOLATION):
        """Another program holds the file: `opens` refused opens (None: until released)."""
        self.shut[self.key(path)] = opens
        self.shut_error = error

    def release(self, path):
        self.shut.pop(self.key(path), None)

    def _refused(self, k):
        if k not in self.shut:
            return False
        left = self.shut[k]
        if left is None:
            return True
        if left <= 0:
            del self.shut[k]
            return False
        self.shut[k] = left - 1
        return True

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

    def exists(self, path):
        return self.key(path) in self.files

    def bind(self, emu):
        fs = self

        def create(e):
            path = e.cstr(e.arg(0))
            disposition = e.arg(4)
            k = fs.key(path)
            fs.log.append(("CreateFileA", path, disposition))
            if fs._refused(k):
                fs.last_error = fs.shut_error
                return INVALID, 28
            if disposition == 3:            # OPEN_EXISTING
                if k not in fs.files:
                    fs.last_error = ERROR_FILE_NOT_FOUND if fs.parent(path) in fs.dirs else ERROR_PATH_NOT_FOUND
                    return INVALID, 28
                data = bytearray(fs.files[k])
            elif disposition == 2:          # CREATE_ALWAYS
                if fs.parent(path) not in fs.dirs:
                    fs.last_error = ERROR_PATH_NOT_FOUND
                    return INVALID, 28
                data = bytearray()
                fs.files[k] = b""
            else:
                raise EmuError(f"CreateFileA disposition {disposition}")
            h = fs.next
            fs.next += 4
            fs.handles[h] = {"key": k, "data": data, "pos": 0, "write": disposition == 2}
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
            st["data"] += e.read(buf, n)
            e.w32(got, n)
            return 1, 20

        def close(e):
            st = fs.handles.pop(e.arg(0))
            if st["write"]:
                fs.files[st["key"]] = bytes(st["data"])
            return 1, 4

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

        def move(e):
            src, dst, flags = e.cstr(e.arg(0)), e.cstr(e.arg(1)), e.arg(2)
            fs.log.append(("MoveFileExA", src, dst, flags))
            ks, kd = fs.key(src), fs.key(dst)
            if ks in fs.shut or kd in fs.shut:
                fs.last_error = ERROR_SHARING_VIOLATION
                return 0, 12
            if fs.max_path is not None and len(dst) > fs.max_path:
                fs.last_error = ERROR_FILENAME_EXCED_RANGE
                return 0, 12
            if ks not in fs.files:
                fs.last_error = ERROR_FILE_NOT_FOUND
                return 0, 12
            if kd in fs.files and not flags & 1:
                fs.last_error = ERROR_ALREADY_EXISTS
                return 0, 12
            fs.files[kd] = fs.files.pop(ks)
            return 1, 12

        def delete(e):
            path = e.cstr(e.arg(0))
            fs.log.append(("DeleteFileA", path))
            if fs.key(path) in fs.shut:
                fs.last_error = ERROR_SHARING_VIOLATION
                return 0, 4
            if fs.files.pop(fs.key(path), None) is None:
                fs.last_error = ERROR_FILE_NOT_FOUND
                return 0, 4
            return 1, 4

        emu.imports.update({
            "CreateFileA": create, "ReadFile": read_file, "WriteFile": write_file, "CloseHandle": close,
            "FlushFileBuffers": lambda e: (1, 4), "CreateDirectoryA": mkdir, "MoveFileExA": move,
            "DeleteFileA": delete, "GetLastError": lambda e: (fs.last_error, 0),
            "Sleep": lambda e: (fs.sleeps.append(e.arg(0)), 0)[1:] + (4,),
        })


class KidsWorld:
    """One emulated process: a B200 executable built with the .vf2kidt table + the test DLL."""

    def __init__(self, exe, dll, delta=0, install=True):
        self.e = Emu(exe, dll, delta)
        self.delta = delta
        self.model, self.sites, self.pin_locs = proved(exe)
        self.pins = {p.name: self.pin_locs[i] for i, p in enumerate(S.PINS)}
        self._native_scan()
        self.fs = FileSystem()
        self.fs.bind(self.e)
        self.save_dir = SAVE_DIR
        self.fs.mkdirs(SAVE_DIR)
        self.rolls = []
        self.spawned = []
        self.saves = []          # (slot, the bytes of each watched slot at that moment)
        self.watch = []
        self.save_content = {}   # slot -> bytes the fake save writes
        self.load_result = 1
        self.loads = []
        self.observed = []
        self.code_before = self._code()
        self._game_state()
        self._villagers()
        self._seams()
        if install:
            self.install()

    # ------------------------------------------------------------------ addresses
    def s(self, name):
        return self.sites[name] + self.delta

    def p(self, pin):
        return self.pins[pin] + self.delta

    def call_target(self, at):
        return (at + 5 + self.e.r32(at + 1)) & 0xFFFFFFFF

    def _native_scan(self):
        import re as _re
        e = self.e
        addr = e.call(e.dll_export("B200Kids_TestScanAddress"))

        def scan(emu):
            base, size, pat, mask, length, hits = (emu.arg(i) for i in range(6))
            data = emu.read(base, size)
            p, m = emu.read(pat, length), emu.read(mask, length)
            rx = _re.compile(b"".join(b"." if w else _re.escape(bytes([b])) for b, w in zip(p, m)), _re.DOTALL)
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
        e.seam_live(addr, scan)

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
        status = s32(self.e.call(self.e.dll_export("B200Kids_TestPlan"), (1 if enabled else 0, out)))
        count = self.e.r32(out + 4)
        writes = []
        for i in range(count):
            va, b0, b1 = (self.e.r32(out + 8 + i * 12 + 4 * k) for k in range(3))
            writes.append((va, struct.pack("<I", b0) + bytes([b1 & 0xFF])))
        return status, writes

    def install(self):
        status, writes = self.test_plan(True)
        assert status == 1, f"the plan was refused (status {status})"
        for va, raw in writes:
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
        vtable = e.alloc(0x40)
        stub = e.fake_code(b"\xC2\x04\x00")
        e.w32(vtable + S.LDW_PATH_VSLOT, stub)
        e.w32(self.state, vtable)
        self.path_buffer = e.alloc(0x200)

        def make_path(emu):
            slot = emu.arg(0)
            emu.write(self.path_buffer, (self.save_path(slot)).encode("ascii") + b"\0")
            return self.path_buffer, 4
        e.seam_live(stub, make_path)

    def save_path(self, slot):
        return f"{self.save_dir}\\Virtual Families 2{slot}.ldw"

    def sidecar_path(self, slot):
        return f"{self.save_dir}\\Virtual Families 2 Patcher Data\\Children\\Virtual Families 2{slot}.ldw.dat"

    def tree(self):
        return self.s("FAMILY_TREE")

    def villager(self, slot):
        return self.s("VILLAGER_MANAGER") + S.VILLAGER_ARRAY_OFFSET + slot * STRIDE

    def _villagers(self):
        e = self.e
        for slot in range(37):
            v = self.villager(slot)
            e.w32(v + S.VILLAGER_SLOT, slot)
            e.write(v + S.VILLAGER_ACTIVE, b"\0")

    def set_villager(self, slot, name, gender, active=1, age=100, head=3, body=4):
        e = self.e
        v = self.villager(slot)
        e.write(v + S.VILLAGER_NAME, name.encode("ascii")[:24].ljust(25, b"\0"))
        e.w32(v + S.VILLAGER_GENDER, gender)
        e.w32(v + S.VILLAGER_HEAD, head)
        e.w32(v + S.VILLAGER_BODY, body)
        e.w32(v + S.VILLAGER_AGE, age)
        e.write(v + S.VILLAGER_ACTIVE, bytes([active]))

    def active(self, slot):
        return self.e.read(self.villager(slot) + S.VILLAGER_ACTIVE, 1)[0]

    def set_active(self, slot, on):
        self.e.write(self.villager(slot) + S.VILLAGER_ACTIVE, bytes([1 if on else 0]))

    def name(self, slot):
        return self.e.cstr(self.villager(slot) + S.VILLAGER_NAME)

    def start_family(self, parent1=0, parent2=1):
        """Generation 1: parent 1 (female) and parent 2 (male), recorded the way the game records them."""
        self.set_villager(parent1, "Mother", 1, age=600)
        self.set_villager(parent2, "Father", 0, age=620)
        r = self.e.call(self.s("FT_START_NEXT_GEN"), (self.villager(parent1), INVALID), ecx=self.tree())
        assert r & 0xFF == 1
        rec = self.record()
        self.e.write(rec + 0xDC + S.PEEP_VALID, b"\x01")
        self.e.w32(rec + 0xDC + S.PEEP_GENDER, 0)
        self.e.w32(rec + 0xDC + S.PEEP_SLOT, parent2)

    def generations(self):
        return s32(self.e.r32(self.tree() + 4))

    def record(self, gen=None):
        gen = self.generations() if gen is None else gen
        return self.tree() + gen * S.FAMILY_RECORD_SIZE - S.FAMILY_RECORD_BASE

    def stock_children(self):
        return s32(self.e.r32(self.record() + S.RECORD_CHILD_COUNT))

    def stock_child_slot(self, i):
        return s32(self.e.r32(self.record() + S.RECORD_CHILDREN + i * S.PEEP_RECORD_SIZE + S.PEEP_SLOT))

    # ------------------------------------------------------------------ the DLL's own view
    def extras(self):
        out = self.e.alloc(4 + 22 * 12)
        self.e.call(self.e.dll_export("B200Kids_TestExtras"), (out,))
        n = s32(self.e.r32(out))
        return [tuple(s32(self.e.r32(out + 4 + i * 12 + 4 * k)) for k in range(3)) for i in range(n)]

    def engine(self):
        out = self.e.alloc(4 * 40)
        self.e.call(self.e.dll_export("B200Kids_TestEngine"), (out,))
        on, count, cursor, swapped = (s32(self.e.r32(out + 4 * k)) for k in range(4))
        return {"on": on, "count": count, "cursor": cursor, "swapped": swapped,
                "sources": [s32(self.e.r32(out + 16 + 4 * i)) for i in range(max(count, 0))]}

    def table(self):
        base = [self.e.base + s.VirtualAddress for s in self.e.exe.sections if s.Name.rstrip(b"\0") == b".vf2kidt"]
        assert len(base) == 1
        t = base[0]
        magic, version, count = self.e.r32(t), self.e.r32(t + 4), s32(self.e.r32(t + 8))
        return magic, version, [s32(self.e.r32(t + 12 + 4 * i)) for i in range(max(0, min(count, 22)))]

    # ------------------------------------------------------------------ calling the game
    def add_offspring(self, slot):
        return self.e.call(self.s("FT_ADD_OFFSPRING"), (self.villager(slot),), ecx=self.tree()) & 0xFF

    def empty_slots(self):
        return s32(self.e.call(self.s("FT_EMPTY_OFFSPRING"), (), ecx=self.tree()))

    def surviving(self):
        return s32(self.e.call(self.s("FT_COUNT_SURVIVING"), (), ecx=self.tree()))

    def report_death(self, slot):
        self.e.call(self.s("FT_REPORT_DEATH"), (self.villager(slot),), ecx=self.tree())

    def reset_tree(self):
        self.e.call(self.s("FT_RESET"), (), ecx=self.tree())

    def change_name(self, slot, name):
        buf = self.e.alloc(32)
        self.e.write(buf, name.encode("ascii") + b"\0")
        self.e.call(self.s("FT_CHANGE_NAME"), (self.villager(slot), buf), ecx=self.tree())
        # theVillagerScene then copies the text into the villager (strncpy 19h), as the game does
        self.e.write(self.villager(slot) + S.VILLAGER_NAME, name.encode("ascii")[:24].ljust(25, b"\0"))

    def start_next_generation(self, heir, source):
        return self.e.call(self.s("FT_START_NEXT_GEN"), (self.villager(heir), source & 0xFFFFFFFF),
                           ecx=self.tree()) & 0xFF

    def save(self, slot):
        return self.e.call(self.s("GS_SAVE"), (slot,), ecx=self.state) & 0xFF

    def load(self, slot):
        return self.e.call(self.s("GS_LOAD"), (slot,), ecx=self.state) & 0xFF

    def status(self):
        st = self.e.dll_export("B200Kids_Status")
        names = ("magic", "version", "requested", "resolved", "installed", "writeMask", "extras", "lastLoad",
                 "lastSave")
        return {n: self.e.r32(st + 4 * i) for i, n in enumerate(names)}

    # ------------------------------------------------------------------ the scene
    def make_scene(self):
        scene = self.e.alloc(0x200)
        self.e.w32(scene + S.ADOPTION_MODE, 1)
        self.e.w32(scene + S.ADOPTION_CANDIDATE, INVALID)
        return scene

    def create_candidates(self, scene):
        self.e.call(self.s("AD_CREATE_CANDIDATES"), (), ecx=scene)

    def next_candidate(self, scene):
        """What CAdoptionScene::GeneratePeepCandidate does in Next Generation mode: GetNextCandidate,
        show it, and leave the candidate inactive."""
        clone = s32(self.e.call(self.s("AD_GET_NEXT"), (), ecx=scene))
        self.e.w32(scene + S.ADOPTION_CANDIDATE, clone)
        if 0 <= clone < 30:
            self.set_active(clone, 0)
        return clone

    def accept(self, scene):
        """CAdoptionScene::HandleMessage's Accept in Next Generation mode: the candidate on show becomes
        active, StartNextGeneration(candidate, [+38h + [+54h] * 4]), every other household slot leaves."""
        e = self.e
        heir = s32(e.r32(scene + S.ADOPTION_CANDIDATE))
        cursor = s32(e.r32(scene + S.ADOPTION_CURSOR))
        source = s32(e.r32(scene + S.ADOPTION_SOURCES + 4 * cursor))
        self.set_active(heir, 1)
        ok = self.start_next_generation(heir, source)
        for slot in range(30):
            if slot != heir:
                self.set_active(slot, 0)
        return heir, source, ok

    # ------------------------------------------------------------------ seams
    def _seams(self):
        e = self.e
        # B200's family-tree appearance observer (it wraps UpdatePeepRecord at every record write)
        observer = self.call_target(self.p("ft_add_offspring") + 0x7B)

        def observe(emu):
            self.observed.append(emu.arg(0))
            return 0, 4
        e.seam_live(observer, observe)

        def clone_as_adult(emu):
            dest, src = emu.ecx, emu.arg(0)
            for off, n in ((S.VILLAGER_NAME, 25), (S.VILLAGER_GENDER, 4), (S.VILLAGER_HEAD, 4), (S.VILLAGER_BODY, 4)):
                emu.write(dest + off, emu.read(src + off, n))
            emu.w32(dest + S.VILLAGER_AGE, 500)
            emu.write(dest + S.VILLAGER_ACTIVE, b"\x01")
            emu.w32(dest + 0x6B00, 0xC10E)          # a mark: this slot holds a clone
            return 0, 4
        e.seam_live(self.s("V_CLONE_AS_ADULT"), clone_as_adult)

        def body_returns(record, result):
            def fn(emu):
                esp = emu.reg(UC_X86_REG_ESP)
                emu.setreg(UC_X86_REG_EBP, emu.r32(esp))      # the trampoline's push ebp
                emu.setreg(UC_X86_REG_ESP, esp + 4)
                record(emu.r32(esp + 8))
                return result(), 4
            return fn

        def saved(slot):
            self.saves.append((slot, {w: self.e.read(self.villager(w), STRIDE) for w in self.watch}))
            content = self.save_content.get(slot, b"SAVE %d #%d" % (slot, len(self.saves)))
            if slot > 0:
                if self.fs.exists(self.save_path(slot)):
                    self.fs.files[self.fs.key(self.save_path(slot + 20))] = self.fs.read(self.save_path(slot))
                self.fs.write(self.save_path(slot), content)
        e.seam_live(self.s("GS_SAVE") + S.HOOKS["GS_SAVE"][1], body_returns(saved, lambda: 1))
        e.seam_live(self.s("GS_LOAD") + S.HOOKS["GS_LOAD"][1],
                    body_returns(lambda slot: self.loads.append(slot), lambda: self.load_result))

        imp = self.p("v_impregnate")
        e.seam_live(self.call_target(imp + 0x24), lambda emu: (self.villager(self.mother), 0))  # GetMatriarch
        e.seam_live(self.call_target(imp + 0x31), lambda emu: (self.villager(self.father), 0))  # GetPatriarch

        def get_random(emu):
            assert self.rolls, "an unscripted GetRandom"
            return self.rolls.pop(0), 0
        e.seam_live(self.call_target(imp + 0xA3), get_random)
        self.mother, self.father = 0, 1

    def seam_impregnate_tail(self):
        """The calls after the twin / triplet decision (offsets are B200's Impregnate, which is the stock
        function plus one jmp to its forced-count cave)."""
        e = self.e
        imp = self.p("v_impregnate")
        raw = e.read(imp, 0x2D7)

        def call_at(off):
            assert raw[off] == 0xE8, hex(off)
            return self.call_target(imp + off)

        def spawn(pop):
            def fn(emu):
                reserved = {s32(self.e.r32(self.state + S.GAME_STATE_RESERVED_BABY + 4 * k)) for k in range(3)}
                for slot in range(30):
                    if not self.active(slot) and slot not in reserved:
                        self.set_villager(slot, f"Baby {slot}", slot % 2, active=1, age=0)
                        self.spawned.append(slot)
                        return slot, pop
                return INVALID, pop
            return fn
        e.seam_live(call_at(0x14D), spawn(48))          # VF2SpawnBirthPeepWithForcedGender (fastcall, 48 on the stack)
        e.seam_live(call_at(0x219), spawn(4))           # SpawnSpecificPeep(CVillager &)
        e.seam_live(call_at(0x1A9), lambda emu: (0, 8))  # CAchievement::IncrementProgress
        e.seam_live(call_at(0x101), lambda emu: (INVALID, 0))  # ExtremeLimitGenderCorrect
        assert call_at(0x284) == call_at(0x219) and call_at(0x1B7) == call_at(0x1A9)

    def impregnate(self, rolls):
        """Run B200's real CVillager::Impregnate on the mother. Returns (result, babies recorded, +6B1Ch)."""
        e = self.e
        self.rolls = list(rolls)
        self.spawned = []
        name = e.alloc(32)
        e.write(name, b"Father\0")
        mother = self.villager(self.mother)
        e.w32(mother + 0x6B40, 0)
        e.w32(self.villager(self.father) + 0x6B40, 0)
        r = e.call(self.p("v_impregnate"), (1, name, 2, 3, 0), ecx=mother) & 0xFF
        return r, list(self.spawned), s32(e.r32(mother + 0x6B1C)), len(self.rolls)

    def deliver(self):
        """The births: the reserved babies become active and the reservations clear (as the game does)."""
        for k in range(3):
            slot = s32(self.e.r32(self.state + S.GAME_STATE_RESERVED_BABY + 4 * k))
            if slot >= 0:
                self.set_active(slot, 1)
            self.e.w32(self.state + S.GAME_STATE_RESERVED_BABY + 4 * k, INVALID)

    # ------------------------------------------------------------------ helpers
    def have_children(self, n, first_slot=2):
        """n children born one at a time (each recorded through the real, hooked AddOffspring)."""
        for k in range(n):
            slot = first_slot + k
            self.set_villager(slot, f"Kid {k + 1}", k % 2, age=40 + k)
            assert self.add_offspring(slot) == 1, f"child {k + 1} was refused"

    def sidecar(self, slot):
        raw = self.fs.read(self.sidecar_path(slot))
        assert raw is not None, "no sidecar"
        return parse_sidecar(raw)


def parse_sidecar(raw: bytes) -> dict:
    assert raw[:8] == S.SIDECAR_MAGIC and raw[12:20] == S.SIDECAR_GAME_TAG
    version, size = struct.unpack_from("<I", raw, 8)[0], struct.unpack_from("<I", raw, 20)[0]
    assert version == S.SIDECAR_VERSION and size == len(raw)
    save_hash, = struct.unpack_from("<Q", raw, 24)
    save_size, gens, pslot, pgender, count = struct.unpack_from("<IiiiI", raw, 32)
    entries = []
    for i in range(count):
        slot, gender, state, head, body, age = struct.unpack_from("<iiiiii", raw, 52 + 64 * i)
        name = raw[52 + 64 * i + 24: 52 + 64 * i + 52].split(b"\0")[0].decode("ascii")
        entries.append({"slot": slot, "gender": gender, "state": state, "head": head, "body": body, "age": age,
                        "name": name})
    assert len(raw) == 52 + 64 * count + 8
    h = 0xCBF29CE484222325
    for b in raw[:-8]:
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    assert struct.unpack_from("<Q", raw, len(raw) - 8)[0] == h, "checksum"
    return {"save_hash": save_hash, "save_size": save_size, "generations": gens, "parent_slot": pslot,
            "parent_gender": pgender, "entries": entries}


def fnv(data: bytes) -> int:
    h = 0xCBF29CE484222325
    for b in data:
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


# ====================================================================== scenarios
ALIVE, DEAD, GONE = 1, 2, 3


def scenario_six_stock_then_extras(w: KidsWorld):
    w.start_family()
    assert w.empty_slots() == 28
    w.have_children(6)
    assert w.stock_children() == 6 and w.extras() == []
    assert [w.stock_child_slot(i) for i in range(6)] == list(range(2, 8))
    assert w.empty_slots() == 22
    w.have_children(22, first_slot=8)
    assert w.stock_children() == 6, "the stock record never holds more than six"
    ex = w.extras()
    assert [e[0] for e in ex] == list(range(8, 30)) and all(e[2] == ALIVE for e in ex)
    assert w.empty_slots() == 0
    magic, version, slots = w.table()
    assert (magic, version) == (S.TABLE_MAGIC, S.TABLE_VERSION) and slots == list(range(8, 30))
    # a 29th is refused (there is no free slot anyway; free one to prove the 28 limit alone refuses it)
    w.set_active(29, 0)
    w.set_villager(29, "Kid 29", 0)
    assert w.add_offspring(29) == 0
    assert len(w.extras()) == 22
    # the next record (generation 2) was never touched
    assert w.e.read(w.record(2), S.FAMILY_RECORD_SIZE) == b"\0" * S.FAMILY_RECORD_SIZE


def scenario_free_slots_cap(w: KidsWorld):
    """Room in the 28 is not enough: a baby also needs a free household slot."""
    w.start_family()
    w.have_children(10)
    for slot in range(12, 30):                      # the house is full of others
        w.set_villager(slot, f"Guest {slot}", 0)
    assert w.empty_slots() == 0
    w.set_active(29, 0)
    assert w.empty_slots() == 1
    for k in range(3):                              # a slot reserved for a baby on the way is not free
        w.e.w32(w.state + S.GAME_STATE_RESERVED_BABY + 4 * k, 29 if k == 0 else INVALID)
    assert w.empty_slots() == 0


def scenario_deaths_count_toward_28(w: KidsWorld):
    w.start_family()
    w.have_children(20)
    assert w.surviving() == 20 and w.empty_slots() == 8
    # an extra child dies (both death paths call ReportDeath)
    w.report_death(15)
    w.set_active(15, 0)
    ex = {e[0]: e[2] for e in w.extras()}
    assert ex[15] == DEAD
    assert w.surviving() == 19
    assert w.empty_slots() == 8, "a death does not give back a place in the 28"
    # all six stock children die; the extras still survive, so the family can still pass the house on
    rec = w.record()
    w.e.write(rec + 1, b"\x01")                     # "can start the next generation"
    for slot in range(2, 8):
        w.report_death(slot)
        w.set_active(slot, 0)
    assert w.surviving() == 13
    assert w.e.read(rec + 1, 1) == b"\x01", "the stock flag must stay set while extra children live"
    magic, version, slots = w.table()
    assert 15 not in slots and len(slots) == 13


def scenario_rename_and_reused_slot(w: KidsWorld):
    w.start_family()
    w.have_children(8)
    w.change_name(9, "Renamed")
    assert {e[0]: e[2] for e in w.extras()}[9] == ALIVE
    assert w.surviving() == 8
    # an extra child's slot taken by someone else (not through AddOffspring): no longer that child
    w.set_villager(8, "Stranger", 1)
    assert w.surviving() == 7
    assert {e[0]: e[2] for e in w.extras()}[8] == GONE
    # a new child recorded into a slot a living entry holds, even with the same name and gender: the
    # old entry is someone else now (never two living entries for one slot)
    assert w.add_offspring(9) == 1
    states = [(e[0], e[2]) for e in w.extras()]
    assert states == [(8, GONE), (9, GONE), (9, ALIVE)]
    assert w.surviving() == 7


def _triplet_room(w, born):
    w.start_family()
    w.have_children(born)
    w.seam_impregnate_tail()


def scenario_births_near_the_limit(w_factory):
    """Single, twin and triplet pregnancies at 26, 27 and 28 children (the owner's edge cases)."""
    # rolls: first GetRandom(100) < 7 asks for twins, the second < 25 asks for triplets. The game asks
    # the second only when the first asked for twins AND there is room for two; at 28 it asks nothing.
    SINGLE, TWIN, TRIPLET = (99,), (0, 99), (0, 0)
    expect = {
        26: {SINGLE: (1, 0), TWIN: (2, 0), TRIPLET: (2, 0)},
        27: {SINGLE: (1, 0), TWIN: (1, 1), TRIPLET: (1, 1)},
        28: {SINGLE: (0, 1), TWIN: (0, 2), TRIPLET: (0, 2)},
    }
    for born, cases in expect.items():
        for rolls, (babies, unused) in cases.items():
            w = w_factory()
            _triplet_room(w, born)
            before = len(w.extras()) + w.stock_children()
            r, spawned, count, left = w.impregnate(rolls)
            assert left == unused, (born, rolls, left)
            after = len(w.extras()) + w.stock_children()
            assert after - before == babies == len(spawned), (born, rolls, after - before, spawned)
            if born < 28:
                assert r == 1 and count == babies, (born, rolls, r, count)
                reserved = [s32(w.e.r32(w.state + S.GAME_STATE_RESERVED_BABY + 4 * k)) for k in range(3)]
                assert reserved[:babies] == spawned and all(x == -1 for x in reserved[babies:])
                assert all(not w.active(s) for s in spawned), "babies stay inactive until birth"
            else:
                assert r == 0 and not spawned
            assert after <= 28


def scenario_stock_odds_unchanged(w_factory):
    """With room, the stock thresholds decide: GetRandom(100) below 7 + bonus is twins, below 25 + bonus
    triplets (bonus 0 here)."""
    for rolls, babies in (((6, 24), 3), ((6, 25), 2), ((7,), 1)):
        w = w_factory()
        _triplet_room(w, 10)
        r, spawned, count, left = w.impregnate(rolls)
        assert r == 1 and count == babies == len(spawned) and left == 0, (rolls, count, spawned)


def scenario_dead_babies_still_count(w_factory):
    """Lifetime births decide the limit: 26 born with 3 dead still leaves room for 2, never 3."""
    w = w_factory()
    _triplet_room(w, 26)
    for slot in (20, 21, 22):
        w.report_death(slot)
        w.set_active(slot, 0)
    r, spawned, count, left = w.impregnate((0, 0))
    assert r == 1 and count == 2 and len(spawned) == 2 and left == 0
    assert spawned == [20, 21], "the babies take the free slots the dead left"


def scenario_limit_counts_lifetime_births(w_factory):
    """With free slots (children have died and left their slots), the 28 alone limits: 28 born allows no
    pregnancy, 27 born allows one baby even when twins or triplets are rolled."""
    w = w_factory()
    _triplet_room(w, 28)
    for slot in (12, 13, 14):
        w.report_death(slot)
        w.set_active(slot, 0)
    assert w.empty_slots() == 0
    r, spawned, count, left = w.impregnate((0, 0))
    assert r == 0 and spawned == [] and left == 2, "28 children born: no more babies"
    w = w_factory()
    _triplet_room(w, 27)
    for slot in (12, 13, 14):
        w.report_death(slot)
        w.set_active(slot, 0)
    assert w.empty_slots() == 1
    r, spawned, count, left = w.impregnate((0, 0))
    assert r == 1 and count == 1 and len(spawned) == 1 and left == 1
    assert len(w.extras()) + w.stock_children() == 28


def scenario_next_generation_candidates(w: KidsWorld):
    w.start_family()
    w.have_children(10)
    scene = w.make_scene()
    w.create_candidates(scene)
    eng = w.engine()
    assert eng["on"] == 1 and eng["sources"] == list(range(2, 12))
    assert s32(w.e.r32(scene + S.ADOPTION_COUNT)) == 1
    seen = []
    for k in range(10):
        clone = w.next_candidate(scene)
        assert s32(w.e.r32(scene + S.ADOPTION_CURSOR)) == 0
        assert s32(w.e.r32(scene + S.ADOPTION_CLONES)) == clone
        source = s32(w.e.r32(scene + S.ADOPTION_SOURCES))
        assert clone not in range(0, 12), "a clone never takes a family member's slot while one is free"
        assert w.name(clone) == w.name(source) and w.e.r32(w.villager(clone) + 0x6B00) == 0xC10E
        seen.append(source)
    assert seen == list(range(2, 12)), "every child is offered, the 7th to the 10th included"
    assert w.next_candidate(scene) >= 12 and s32(w.e.r32(scene + S.ADOPTION_SOURCES)) == 2, "it cycles"
    # choose the 9th child
    for _ in range(8):
        w.next_candidate(scene)
    assert s32(w.e.r32(scene + S.ADOPTION_SOURCES)) == 10
    heir, source, ok = w.accept(scene)
    assert ok == 1 and source == 10
    assert w.generations() == 2 and w.extras() == [] and w.engine()["on"] == 0
    rec = w.record()
    assert s32(w.e.r32(rec + S.RECORD_PARENT1 + S.PEEP_SLOT)) == heir
    assert w.e.cstr(rec + S.RECORD_PARENT1) == "Kid 9"
    assert s32(w.e.r32(rec + 0x30)) == -1, "a child the tree never showed has no parent line"
    assert w.table()[2] == []


def scenario_stock_child_heir_keeps_its_line(w: KidsWorld):
    w.start_family()
    w.have_children(9)
    scene = w.make_scene()
    w.create_candidates(scene)
    for _ in range(4):                    # the 4th child: in the stock record at index 3
        w.next_candidate(scene)
    heir, source, ok = w.accept(scene)
    assert ok == 1 and source == 5
    assert s32(w.e.r32(w.record() + 0x30)) == 3


def scenario_six_or_fewer_is_stock(w: KidsWorld):
    w.start_family()
    w.have_children(5)
    scene = w.make_scene()
    w.create_candidates(scene)
    assert w.engine()["on"] == 0
    assert s32(w.e.r32(scene + S.ADOPTION_COUNT)) == 5, "the stock scene cloned all five"
    clones = [s32(w.e.r32(scene + S.ADOPTION_CLONES + 4 * i)) for i in range(5)]
    sources = [s32(w.e.r32(scene + S.ADOPTION_SOURCES + 4 * i)) for i in range(5)]
    assert sources == [2, 3, 4, 5, 6] and all(not w.active(c) for c in clones)
    got = [w.next_candidate(scene) for _ in range(6)]
    assert got == clones + clones[:1]


def scenario_full_house(w: KidsWorld):
    """2 parents + 28 children: no free slot, so each adult clone is made in the child's own slot and the
    child is put back byte for byte."""
    w.start_family()
    w.have_children(28)
    assert all(w.active(s) for s in range(30))
    snapshots = {s: w.e.read(w.villager(s), STRIDE) for s in range(2, 30)}
    scene = w.make_scene()
    w.create_candidates(scene)
    assert w.engine()["count"] == 28
    first = w.next_candidate(scene)
    assert first == 2 and w.engine()["swapped"] == 2
    assert w.e.r32(w.villager(2) + 0x6B00) == 0xC10E and w.e.rs32(w.villager(2) + S.VILLAGER_AGE) == 500
    assert w.e.rs32(w.villager(2) + S.VILLAGER_SLOT) == 2
    second = w.next_candidate(scene)
    assert second == 3
    assert w.e.read(w.villager(2), STRIDE) == snapshots[2], "the child came back exactly"
    # a save while the 3rd child's clone is on show saves the child, then the clone is on show again
    w.watch = [3]
    on_show = w.e.read(w.villager(3), STRIDE)
    assert w.save(1) == 1
    assert w.saves[-1][1][3] == snapshots[3], "the save saw the child, not the clone"
    assert w.e.read(w.villager(3), STRIDE) == on_show
    # every child, the 28th included
    sources = [s32(w.e.r32(scene + S.ADOPTION_SOURCES))]
    for _ in range(26):
        w.next_candidate(scene)
        sources.append(s32(w.e.r32(scene + S.ADOPTION_SOURCES)))
    assert sources == list(range(3, 30))
    assert all(w.e.read(w.villager(s), STRIDE) == snapshots[s] for s in range(2, 29))
    heir, source, ok = w.accept(scene)
    assert ok == 1 and heir == source == 29
    assert w.e.rs32(w.villager(29) + S.VILLAGER_AGE) == 500, "the heir is the adult clone"
    assert w.active(29) and not any(w.active(s) for s in range(29))
    assert w.engine()["swapped"] == -1


def scenario_sidecar_round_trip(w: KidsWorld):
    w.start_family()
    w.have_children(10)
    w.report_death(9)
    w.set_active(9, 0)
    assert w.save(1) == 1
    st = w.status()
    assert st["lastSave"] == 1
    side = w.sidecar(1)
    save = w.fs.read(w.save_path(1))
    assert side["save_hash"] == fnv(save) and side["save_size"] == len(save)
    assert side["generations"] == 1 and side["parent_slot"] == 0 and side["parent_gender"] == 1
    assert [(x["slot"], x["state"], x["name"]) for x in side["entries"]] == [
        (8, ALIVE, "Kid 7"), (9, DEAD, "Kid 8"), (10, ALIVE, "Kid 9"), (11, ALIVE, "Kid 10")]
    assert w.fs.exists(w.sidecar_path(1)) and not w.fs.exists(w.sidecar_path(1) + ".tmp")
    room = w.empty_slots()
    w.reset_tree()                              # CFamilyTree::LoadState starts with Reset
    assert w.extras() == []
    # the stock record comes back from the save file; the emulated Load does not touch memory
    w.start_family()
    w.have_children(6)
    assert w.load(1) == 1 and w.status()["lastLoad"] == 1
    assert [(e[0], e[2]) for e in w.extras()] == [(8, ALIVE), (9, DEAD), (10, ALIVE), (11, ALIVE)]
    assert w.empty_slots() == room
    assert w.table()[2] == [8, 10, 11]


def scenario_sidecar_follows_backup(w: KidsWorld):
    """The game keeps the previous save at slot + 20; restoring it restores its own sidecar."""
    w.start_family()
    w.have_children(8)
    w.save_content[1] = b"FIRST"
    w.save(1)
    w.have_children(2, first_slot=10)
    w.save_content[1] = b"SECOND"
    w.save(1)
    assert len(w.sidecar(1)["entries"]) == 4 and len(w.sidecar(21)["entries"]) == 2
    # the owner restores the backup save over slot 1
    w.fs.files[w.fs.key(w.save_path(1))] = w.fs.read(w.save_path(21))
    w.reset_tree()
    w.start_family()
    w.have_children(8)
    assert w.load(1) == 1 and w.status()["lastLoad"] == 2
    assert [e[0] for e in w.extras()] == [8, 9]


def scenario_sidecar_other_save_same_family(w: KidsWorld):
    w.start_family()
    w.have_children(10)
    w.save(1)
    w.fs.files[w.fs.key(w.save_path(1))] = b"EDITED ELSEWHERE"   # not the save the sidecar was written with
    w.reset_tree()
    w.start_family()
    w.have_children(6)
    w.set_villager(8, "Kid 7", 0)
    w.set_villager(9, "Kid 8", 1)
    w.set_villager(10, "Someone else", 0)                        # not the child the sidecar names
    w.set_active(11, 0)
    w.set_villager(11, "Kid 10", 1, active=0)                    # away (inactive) but still that child
    assert w.load(1) == 1 and w.status()["lastLoad"] == 3
    assert [(e[0], e[2]) for e in w.extras()] == [(8, ALIVE), (9, ALIVE), (11, ALIVE)]


def scenario_sidecar_other_family_is_ignored(w: KidsWorld):
    w.start_family()
    w.have_children(8)
    w.save(1)
    w.reset_tree()
    w.start_family(parent1=1, parent2=0)        # another family in this slot
    w.have_children(6)
    assert w.load(1) == 1 and w.status()["lastLoad"] == 4
    assert w.extras() == []


def scenario_unreadable_sidecar_is_kept_aside(w: KidsWorld):
    w.start_family()
    w.have_children(8)
    w.save(1)
    raw = bytearray(w.fs.read(w.sidecar_path(1)))
    raw[60] ^= 0xFF
    w.fs.files[w.fs.key(w.sidecar_path(1))] = bytes(raw)
    w.reset_tree()
    w.start_family()
    w.have_children(6)
    assert w.load(1) == 1 and w.status()["lastLoad"] == 5
    assert w.extras() == []
    aside = w.sidecar_path(1)[:-4] + ".unreadable-1.dat"
    assert w.fs.read(aside) == bytes(raw), "the unreadable file is kept, unchanged"
    assert not w.fs.exists(w.sidecar_path(1))
    # a second one gets the next number, the first is never overwritten
    w.fs.files[w.fs.key(w.sidecar_path(1))] = b"garbage"
    w.load(1)
    assert w.fs.read(w.sidecar_path(1)[:-4] + ".unreadable-2.dat") == b"garbage"
    assert w.fs.read(aside) == bytes(raw)


def scenario_nothing_to_write(w: KidsWorld):
    w.start_family()
    w.have_children(6)
    assert w.save(2) == 1 and w.status()["lastSave"] == 2
    assert not w.fs.exists(w.sidecar_path(2))
    assert w.save(0) == 1                         # the settings file: never a sidecar
    assert not any("Virtual Families 20.ldw.dat" in str(x) for x in w.fs.log)


def scenario_evict_and_new_family_clear(w: KidsWorld):
    w.start_family()
    w.have_children(9)
    assert len(w.extras()) == 3
    w.reset_tree()                                # EvictFamily is Reset + flag
    assert w.extras() == [] and w.table()[2] == []
    w.start_family()                              # StartFamilyTree is StartNextGeneration(v, -1)
    assert w.extras() == []



def _aside(w, slot, n=1):
    return w.sidecar_path(slot)[:-4] + f".unreadable-{n}.dat"


def _two_saves(w):
    """Two saves of slot 1: the backup (slot 21) has the first save and its sidecar, slot 1 the second."""
    w.start_family()
    w.have_children(8)
    w.save_content[1] = b"FIRST"
    assert w.save(1) == 1
    w.have_children(2, first_slot=10)
    w.save_content[1] = b"SECOND"
    assert w.save(1) == 1
    assert w.fs.read(w.save_path(21)) == b"FIRST" and w.fs.read(w.save_path(1)) == b"SECOND"
    assert w.sidecar(21)["save_hash"] == fnv(b"FIRST") and w.sidecar(1)["save_hash"] == fnv(b"SECOND")


def scenario_unreadable_backup_is_set_aside(w: KidsWorld):
    """The game removes the save at slot + 20 at every save; an unreadable sidecar there is read first and
    kept beside itself, never deleted."""
    _two_saves(w)
    raw = bytearray(w.fs.read(w.sidecar_path(21)))
    raw[60] ^= 0xFF
    w.fs.files[w.fs.key(w.sidecar_path(21))] = bytes(raw)
    second = w.fs.read(w.sidecar_path(1))
    w.save_content[1] = b"THIRD"
    mark = len(w.fs.log)
    assert w.save(1) == 1 and w.status()["lastSave"] == 1
    assert w.fs.read(_aside(w, 21)) == bytes(raw), "the unreadable backup sidecar is kept, unchanged"
    assert w.fs.read(w.sidecar_path(21)) == second, "this slot's validated sidecar went with its save"
    assert w.sidecar(1)["save_hash"] == fnv(b"THIRD")
    assert ("DeleteFileA", w.sidecar_path(21)) not in w.fs.log[mark:]


def scenario_foreign_backup_is_set_aside(w: KidsWorld):
    """A sidecar that validates but was not written with the save beside it is someone else's: it is set
    aside, never deleted and never rotated."""
    _two_saves(w)
    backup_side, slot_side = w.fs.read(w.sidecar_path(21)), w.fs.read(w.sidecar_path(1))
    w.fs.files[w.fs.key(w.save_path(21))] = b"A BACKUP FROM ELSEWHERE"
    w.save_content[1] = b"THIRD"
    assert w.save(1) == 1 and w.status()["lastSave"] == 1
    assert w.fs.read(_aside(w, 21)) == backup_side, "the foreign backup sidecar is kept, unchanged"
    assert w.fs.read(w.sidecar_path(21)) == slot_side
    # this slot's own sidecar, when its save was changed elsewhere, is foreign too: set aside, not rotated
    side_before = w.fs.read(w.sidecar_path(1))
    w.fs.files[w.fs.key(w.save_path(1))] = b"EDITED ELSEWHERE"
    w.save_content[1] = b"FOURTH"
    assert w.save(1) == 1 and w.status()["lastSave"] == 1
    assert w.fs.read(_aside(w, 1)) == side_before
    assert not w.fs.exists(w.sidecar_path(21)), "an unvalidated sidecar is never rotated onto the backup"
    assert not w.fs.exists(_aside(w, 21, 2)), "the backup's own validated sidecar goes with its save"
    assert w.sidecar(1)["save_hash"] == fnv(b"FOURTH")


def scenario_shut_sidecar_is_retried_never_set_aside(w: KidsWorld):
    """A sidecar another program holds open is tried again, never judged damaged, never set aside, and
    never replaced by a save that would drop the children it records."""
    w.start_family()
    w.have_children(8)
    w.report_death(8)
    w.set_active(8, 0)
    assert w.save(1) == 1
    side = w.fs.read(w.sidecar_path(1))
    held = [(8, DEAD), (9, ALIVE)]
    # held briefly: the open is tried again and the load is exact
    for error in (ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION, ERROR_ACCESS_DENIED):
        w.reset_tree()
        w.start_family()
        w.have_children(6)
        w.fs.sleeps.clear()
        w.fs.hold(w.sidecar_path(1), opens=OPEN_TRIES - 1, error=error)
        assert w.load(1) == 1 and w.status()["lastLoad"] == 1, error
        assert [(e[0], e[2]) for e in w.extras()] == held
        assert len(w.fs.sleeps) == OPEN_TRIES - 1 and sum(w.fs.sleeps) <= 1200
    # held throughout: left exactly as it is
    w.reset_tree()
    w.start_family()
    w.have_children(6)
    w.fs.sleeps.clear()
    w.fs.hold(w.sidecar_path(1))
    assert w.load(1) == 1 and w.status()["lastLoad"] == 6
    assert len(w.fs.sleeps) == OPEN_TRIES - 1, "a shut open is tried a bounded number of times"
    assert w.extras() == []
    assert w.fs.read(w.sidecar_path(1)) == side and not w.fs.exists(_aside(w, 1))
    # a save while it is still shut writes nothing over it and moves nothing
    w.have_children(1, first_slot=10)
    assert w.save(1) == 1 and w.status()["lastSave"] == 4
    assert w.fs.read(w.sidecar_path(1)) == side and not w.fs.exists(_aside(w, 1))
    assert not w.fs.exists(w.sidecar_path(21))
    # released: the next save reads it, keeps everything it records (it was written with the save the
    # game has since moved to slot + 20, so its dead child still counts) and adds what this session added
    w.fs.release(w.sidecar_path(1))
    assert w.save(1) == 1 and w.status()["lastSave"] == 1
    entries = [(x["slot"], x["state"]) for x in w.sidecar(1)["entries"]]
    assert entries == [(10, ALIVE), (8, DEAD), (9, ALIVE)], entries
    assert not w.fs.exists(_aside(w, 1))


def scenario_long_path_set_aside(w: KidsWorld):
    """The longest save path the game can make: the damaged sidecar is set aside; when even the set-aside
    name cannot be made, the file is left exactly as it is (never deleted) and no save replaces it."""
    base = "C:\\" + "\\".join(["L" * 60] * 3) + "\\"
    w.save_dir = base
    w.save_dir = base + "D" * (257 - len(w.save_path(1)))   # slot 21's save path is then 258, the most there is
    w.fs.mkdirs(w.save_dir)
    w.fs.mkdirs(w.fs.parent(w.sidecar_path(1)))             # a file system that takes long paths
    assert len(w.save_path(1)) == 257 and len(w.sidecar_path(1)) > 260 + 24
    w.start_family()
    w.have_children(8)
    assert w.save(1) == 1 and w.status()["lastSave"] == 1
    good = w.fs.read(w.sidecar_path(1))
    w.fs.files[w.fs.key(w.sidecar_path(1))] = b"damaged"
    w.reset_tree()
    w.start_family()
    w.have_children(6)
    assert w.load(1) == 1 and w.status()["lastLoad"] == 5
    assert w.fs.read(_aside(w, 1)) == b"damaged" and not w.fs.exists(w.sidecar_path(1))
    # the set-aside name does not fit (the file system refuses it): nothing is deleted
    w.fs.files[w.fs.key(w.sidecar_path(1))] = b"damaged again"
    w.fs.max_path = len(w.sidecar_path(1))
    assert w.load(1) == 1 and w.status()["lastLoad"] == 7
    assert w.fs.read(w.sidecar_path(1)) == b"damaged again"
    w.have_children(2, first_slot=8)
    assert w.save(1) == 1 and w.status()["lastSave"] == 4
    assert w.fs.read(w.sidecar_path(1)) == b"damaged again", "a damaged file that cannot be set aside is kept"
    assert good != b"damaged again"


ALL = [
    scenario_six_stock_then_extras,
    scenario_free_slots_cap,
    scenario_deaths_count_toward_28,
    scenario_rename_and_reused_slot,
    scenario_next_generation_candidates,
    scenario_stock_child_heir_keeps_its_line,
    scenario_six_or_fewer_is_stock,
    scenario_full_house,
    scenario_sidecar_round_trip,
    scenario_sidecar_follows_backup,
    scenario_sidecar_other_save_same_family,
    scenario_sidecar_other_family_is_ignored,
    scenario_unreadable_sidecar_is_kept_aside,
    scenario_unreadable_backup_is_set_aside,
    scenario_foreign_backup_is_set_aside,
    scenario_shut_sidecar_is_retried_never_set_aside,
    scenario_long_path_set_aside,
    scenario_nothing_to_write,
    scenario_evict_and_new_family_clear,
]
# Scenarios that need several fresh worlds (they are given a factory).
FACTORY = [
    scenario_births_near_the_limit,
    scenario_stock_odds_unchanged,
    scenario_dead_babies_still_count,
    scenario_limit_counts_lifetime_births,
]


def scenario_stock_when_off(w: KidsWorld):
    """With the setting off the plan is empty and the executable's code is unchanged; the stock functions
    keep the six-child limit."""
    status, writes = w.test_plan(False)
    assert status == 0 and writes == []
    assert not w.changed_code()
    w.start_family()
    for k in range(6):
        w.set_villager(2 + k, f"Kid {k + 1}", k % 2)
        assert w.add_offspring(2 + k) == 1
    w.set_villager(8, "Kid 7", 0)
    assert w.add_offspring(8) == 0, "stock refuses the 7th"
    assert w.empty_slots() == 0


OFF = [scenario_stock_when_off]


# ====================================================================== the executable's loader
EXE_PATH = "C:\\Game\\Virtual Families 2 - B200.exe"
TIME_DLL_PATH = "C:\\Game\\Virtual Families 2 Patcher Files\\vf2time_b200.dll"


def section_va(exe_path, name):
    import pefile
    pe = pefile.PE(str(exe_path))
    hits = [pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress for s in pe.sections if s.Name.rstrip(b"\0") == name]
    assert len(hits) == 1, name
    return hits[0]


def run_loader(exe, dll, delta, kids_flag, ini, time_flag=0, dll_present=True):
    """Run the executable's REAL loader wrapper (theGame::Init's first call) with this DLL as the one it
    loads for Up to 28 Children. Returns (world, wrapper result, calls log)."""
    import b200_time_scenarios as T
    w = KidsWorld(exe, dll, delta, install=False)
    e = w.e
    _flag, _call, wrapper = T.loader_sites(exe)
    log = []
    e.write(section_va(exe, b".vf2kids") + delta, bytes([kids_flag]))
    e.write(section_va(exe, b".vf2time") + delta, bytes([time_flag]))

    def wide(addr, text):
        e.write(addr, text.encode("utf-16-le") + b"\0\0")
        return len(text)

    def exe_get_module_file_name(emu):
        log.append("exe:GetModuleFileNameW")
        return wide(emu.arg(1), EXE_PATH), 12

    def exe_load_library(emu):
        path = emu.wstr(emu.arg(0))
        log.append("exe:LoadLibraryW " + path)
        if path == DLL_PATH and dll_present:
            return 0x30000000, 4
        return 0, 4

    def exe_get_proc(emu):
        name = emu.cstr(emu.arg(1))
        log.append("exe:GetProcAddress " + name)
        return (emu.dll_export("B200Kids_Startup") if name == "B200Kids_Startup" else 0), 8
    e.bind_exe_imports({"GetModuleFileNameW": exe_get_module_file_name, "LoadLibraryW": exe_load_library,
                        "GetProcAddress": exe_get_proc})

    def dll_get_module_file_name(emu):
        log.append("dll:GetModuleFileNameW")
        return wide(emu.arg(1), DLL_PATH), 12

    def dll_get_ini(emu):
        log.append("dll:GetPrivateProfileIntW " + emu.wstr(emu.arg(0)) + " " + emu.wstr(emu.arg(1)) + " "
                   + emu.wstr(emu.arg(3)))
        return ini, 16

    def dll_virtual_protect(emu):
        emu.w32(emu.arg(3), 0x20)
        return 1, 16
    e.imports.update({
        "GetModuleFileNameW": dll_get_module_file_name, "GetPrivateProfileIntW": dll_get_ini,
        "VirtualProtect": dll_virtual_protect, "FlushInstructionCache": lambda emu: (1, 12),
        "GetCurrentProcess": lambda emu: (0xFFFFFFFF, 0),
    })
    w.code_before = w._code()
    e.call(e.dll_export("B200Kids_TestSetModule"), (0x30000000,))
    result = e.call(wrapper + delta, ())
    return w, result, log


def scenario_loader_cases(exe, dll, delta):
    """The dormant loader: byte 0 never loads the DLL; byte 1 loads it (after the Time Controls DLL);
    the DLL installs only when its ini says 1, and then exactly its eleven entry jumps are written."""
    for kids, ini, time_flag, present, installs in ((0, 1, 0, True, False), (1, 0, 0, True, False),
                                                    (1, 1, 0, False, False), (1, 1, 0, True, True),
                                                    (1, 1, 1, True, True), (0, 1, 1, True, False)):
        w, result, log = run_loader(exe, dll, delta, kids, ini, time_flag, present)
        assert result == w.state, "the wrapper must return theGameState::Get()'s result"
        loads = [x for x in log if x.startswith("exe:LoadLibraryW")]
        expect = ([f"exe:LoadLibraryW {TIME_DLL_PATH}"] if time_flag else []) + \
                 ([f"exe:LoadLibraryW {DLL_PATH}"] if kids else [])
        assert loads == expect, (kids, ini, time_flag, log)
        changed = w.changed_code()
        st = w.status()
        if not installs:
            assert not changed, (kids, ini, time_flag, present, len(changed))
            assert st["installed"] == 0
            if kids and present:
                assert st["requested"] == (1 if ini else 0)
                assert [x for x in log if x.startswith("dll:GetPrivateProfileIntW")] == [
                    "dll:GetPrivateProfileIntW Patches UpTo28Children "
                    "C:\\Game\\Virtual Families 2 Patcher Files\\vf2kids.ini"]
            continue
        assert st["requested"] == 1 and st["resolved"] == 1 and st["installed"] == 1
        assert st["writeMask"] == (1 << len(S.HOOKS)) - 1
        entries = {w.s(name) for name in S.HOOKS}
        expected = {a + k for a in entries for k in range(5)}
        # the import-table slots the test bound are data, not code; only the eleven jumps changed
        assert changed <= expected and len(changed) >= 4 * len(entries), (len(changed), len(expected))
        for a in entries:
            assert w.e.read(a, 1) == b"\xE9"
            target = (a + 5 + struct.unpack("<i", w.e.read(a + 1, 4))[0]) & 0xFFFFFFFF
            assert 0x30000000 <= target < 0x30100000
        # and it works: a seventh child is recorded
        w.start_family()
        w.have_children(7)
        assert len(w.extras()) == 1
    # the wrapper twice: the DLL is loaded once
    import b200_time_scenarios as T
    w, result, log = run_loader(exe, dll, delta, 1, 1)
    again = w.e.call(T.loader_sites(exe)[2] + delta, ())
    assert again == w.state
    assert len([x for x in log if x.startswith("exe:LoadLibraryW")]) == 1
