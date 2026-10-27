"""Scenarios for the Outfit Pictures DLL (vf2outfits_b200.dll), run under tests/b200_time_emu.py.

Each scenario takes a fresh OutfitWorld and raises AssertionError on a wrong result. An OutfitWorld is the
REAL B200 core executable and the REAL compiled test DLL in one unicorn address space (at the link address
and relocated, as Windows does with ASLR), with the DLL's hooks written exactly as its own plan says (or not
written at all: install=False is the stock game, which shows the bug).

Every hook is reached from its live caller: the game's own instructions run up to and through the call the
DLL retargets, so each scenario proves the retargeted call lands in the DLL and the DLL chains to the
function the game called.

Game code that runs for real: the store's buy run of CScrollingStoreScene::HandlePurchaseItem (TakeOne with
its outfit tail, the 12h..17h -> 49h / 4Ah conversion, GetUseCount, CToolTray::AddItem and GetAvailableSlot);
CToolTray::Draw whole (every place), CToolTray::DrawToolInHand whole, CToolTray::HandleMouseDown and
HandleMouseUp whole (PointToSlot, SwapSlots); theMainScene::HandleMouseDown's outfit apply run (the gender
test, CInventoryManager::GetOutfit with B200's expansion-outfit prefix VF2GetOutfitStoreBodyValue, the body
write, CToolTray::UseTool); CToolTray::LoadState / SaveState and CInventoryManager::LoadState / SaveState
(the scenario that checks the save model); theGameState's Save and Load vtable slots.

Seams (recorded, never real): CInventoryManager::DrawItem (it records the item and the two outfit fields at
the moment of the call: the jump table that reads them is proved statically by the prover),
CToolTray::UpdateHintText (hint text only), ldwGameWindow::Get / GetCursorPos and GetInHandState (the cursor),
CVillagerManager::GetVillager / MakeInFocus, CVillagerPlans::ForgetPlans, CVillager::NewBehavior,
MakeGameStatePath (a fixed folder), the bodies of theGameState::Save and ::Load (a save file holding the tray
and the outfit fields as the game's SaveState writes them, and the game's own slot + 20 backup rotation; a
load restores them as the game's LoadState does), and the DLL's Win32 file imports (an in-memory file system).
"""
from __future__ import annotations

import os
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "tools"))
import b200_outfits_sites as S  # noqa: E402
import gen_b200_outfits_sites as G  # noqa: E402

from b200_time_emu import DLL_BASE, Emu, EmuError  # noqa: E402
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ECX, UC_X86_REG_EDI,  # noqa: E402
                               UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)

SAVE_DIR = "C:\\Users\\Tester\\Documents\\LDW\\VF2 Outfits Test"
DLL_PATH = "C:\\Game\\Virtual Families 2 Patcher Files\\vf2outfits_b200.dll"
INVALID = 0xFFFFFFFF
ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND, ERROR_ALREADY_EXISTS = 2, 3, 183
ERROR_SHARING_VIOLATION, ERROR_FILENAME_EXCED_RANGE = 32, 206
OPEN_TRIES = 5
MALE, FEMALE = S.MALE_OUTFIT, S.FEMALE_OUTFIT
TOP = 7                         # the tray's top edge (CToolTray::Reset: 7 in wide screen)
H = 0x49                        # a place's height (Reset)

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


def fnv(data: bytes) -> int:
    h = 0xCBF29CE484222325
    for b in data:
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


SIDECAR_SIZE = 36 + S.TRAY_PLACES * 8 + S.INV_BIND_COUNT * 4 + S.TRAY_PLACES * 4 + 8


def parse_sidecar(raw: bytes) -> dict:
    assert len(raw) == SIDECAR_SIZE, len(raw)
    assert raw[:8] == S.SIDECAR_MAGIC and raw[12:20] == S.SIDECAR_GAME_TAG
    version, size = struct.unpack_from("<I", raw, 8)[0], struct.unpack_from("<I", raw, 20)[0]
    assert version == S.SIDECAR_VERSION and size == len(raw)
    save_hash, = struct.unpack_from("<Q", raw, 24)
    save_size, = struct.unpack_from("<I", raw, 32)
    places = [struct.unpack_from("<ii", raw, 36 + 8 * k) for k in range(S.TRAY_PLACES)]
    inventory = list(struct.unpack_from("<%di" % S.INV_BIND_COUNT, raw, 36 + 8 * S.TRAY_PLACES))
    pictures = list(struct.unpack_from("<%di" % S.TRAY_PLACES, raw, 36 + 8 * S.TRAY_PLACES + 4 * S.INV_BIND_COUNT))
    assert struct.unpack_from("<Q", raw, len(raw) - 8)[0] == fnv(raw[:-8]), "checksum"
    return {"save_hash": save_hash, "save_size": save_size, "places": places, "inventory": inventory,
            "pictures": pictures}


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
        self.sleeps = []

    def hold(self, path, opens=None):
        """Another program holds the file: `opens` refused opens (None: until released)."""
        self.shut[self.key(path)] = opens

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
                fs.last_error = ERROR_SHARING_VIOLATION
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
            assert st["write"]
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

        def protect(e):
            e.w32(e.arg(3), 0x40)
            return 1, 16

        emu.imports.update({
            "CreateFileA": create, "ReadFile": read_file, "WriteFile": write_file, "CloseHandle": close,
            "FlushFileBuffers": lambda e: (1, 4), "CreateDirectoryA": mkdir, "MoveFileExA": move,
            "DeleteFileA": delete, "GetLastError": lambda e: (fs.last_error, 0),
            "Sleep": lambda e: (fs.sleeps.append(e.arg(0)), 0)[1:] + (4,),
            "VirtualProtect": protect, "FlushInstructionCache": lambda e: (1, 12),
            "GetCurrentProcess": lambda e: (INVALID, 0),
        })


class OutfitWorld:
    """One emulated process: the B200 core executable + the test DLL."""

    @classmethod
    def bare(cls, exe, dll, delta=0, native_scan=True):
        """Only the address space and the DLL (no game state, no proof of the executable)."""
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
        self.model, self.sites, self.pin_locs = proved(exe)
        self.pins = {p.name: self.pin_locs[i] for i, p in enumerate(S.PINS)}
        self._native_scan()
        self.fs = FileSystem()
        self.fs.bind(self.e)
        self.fs.mkdirs(SAVE_DIR)
        self.draws = []
        self.calls = []
        self.saves = []
        self.loads = []
        self.load_result = 1
        self.code_before = self._code()
        self.cursor = (300, 300)
        self._game_state()
        self._seams()
        self.reset_tray()
        self.reset_inventory()
        self.writes = []
        self.installed = install
        if install:
            self.install()

    def seam(self, addr, fn):
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
        addr = e.call(e.dll_export("B200Outfits_TestScanAddress"))

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
        status = s32(self.e.call(self.e.dll_export("B200Outfits_TestPlan"), (1 if enabled else 0, out)))
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

    def status(self):
        st = self.e.dll_export("B200Outfits_Status")
        names = ("magic", "version", "requested", "resolved", "installed", "writeMask", "known", "lastLoad",
                 "lastSave", "applied", "lent")
        return {n: self.e.r32(st + 4 * i) for i, n in enumerate(names)}

    def kept(self):
        """The DLL's own pictures: [(item, picture)] for the 9 places."""
        out = self.e.alloc(4 * 2 * S.TRAY_PLACES)
        self.e.call(self.e.dll_export("B200Outfits_TestPlaces"), (out,))
        return [(s32(self.e.r32(out + 8 * k)), s32(self.e.r32(out + 8 * k + 4))) for k in range(S.TRAY_PLACES)]

    # ------------------------------------------------------------------ the game's state
    def _game_state(self):
        e = self.e
        self.state = e.alloc(0x26400)
        e.w32(self.state, self.s("GS_VTABLE"))            # the real vtable: Save / Load slots, MakeGameStatePath
        self.path_buffer = e.alloc(0x200)
        make_path = e.r32(self.s("GS_VTABLE") + S.LDW_PATH_VSLOT)

        def path(emu):
            emu.write(self.path_buffer, self.save_path(emu.arg(0)).encode("ascii") + b"\0")
            return self.path_buffer, 4
        self.seam(make_path, path)
        self.villagers = {}

    def save_path(self, slot):
        return f"{SAVE_DIR}\\Virtual Families 2{slot}.ldw"

    def sidecar_path(self, slot):
        return f"{SAVE_DIR}\\Virtual Families 2 Patcher Data\\Outfits\\Virtual Families 2{slot}.ldw.dat"

    def sidecar(self, slot=1):
        raw = self.fs.read(self.sidecar_path(slot))
        assert raw is not None, "no sidecar"
        return parse_sidecar(raw)

    @property
    def tray(self):
        return self.s("TOOL_TRAY")

    @property
    def inv(self):
        return self.s("INVENTORY_MANAGER")

    def reset_tray(self):
        """The tray as CToolTray::Reset leaves it: 9 places of 49h, the fixed tools in 0 and 1, item 4 in 2."""
        e, t = self.e, self.tray
        e.write(t, bytes(0xA8))
        for off, v in ((S.TRAY_COUNT, 9), (S.TRAY_HEIGHT, H), (S.TRAY_LEFT, 0), (S.TRAY_TOP, TOP), (0x84, H),
                       (0x88, TOP + 9 * H), (0x8C, 0), (0x90, TOP), (0x94, H), (0x98, TOP + 9 * H),
                       (S.TRAY_HELD, INVALID)):
            e.w32(t + off, v)
        for k, (item, uses) in enumerate(((1, -1), (2, -1))):
            self.set_place(k, item, uses)

    def set_place(self, k, item, uses=1):
        self.e.w32(self.tray + 8 * k, item)
        self.e.w32(self.tray + 8 * k + 4, uses)

    def places(self):
        return [(s32(self.e.r32(self.tray + 8 * k)), s32(self.e.r32(self.tray + 8 * k + 4))) for k in range(9)]

    def reset_inventory(self):
        e, i = self.e, self.inv
        for item in range(S.STORE_MALE_FIRST, S.STORE_FEMALE_LAST + 1):
            e.w32(i + 4 * item, 9)                    # in stock
        self.set_store(male=(3, 4, 5), female=(6, 7, 8))
        e.w32(i + S.INV_MALE_PICTURE, INVALID)
        e.w32(i + S.INV_FEMALE_PICTURE, INVALID)
        e.w32(i + S.INV_NEXT_REDRAW, 123456)

    def set_store(self, male=None, female=None):
        """The store's pictures: the three male (items 12h..14h) and the three female (15h..17h)."""
        for first, values in ((S.STORE_MALE_FIRST, male), (S.STORE_FEMALE_FIRST, female)):
            if values is not None:
                for k, v in enumerate(values):
                    self.e.w32(self.inv + S.INV_STORE_PICTURES + 4 * (first + k), v)

    def field(self, item):
        return s32(self.e.r32(self.inv + (S.INV_MALE_PICTURE if item == MALE else S.INV_FEMALE_PICTURE)))

    def set_field(self, item, v):
        self.e.w32(self.inv + (S.INV_MALE_PICTURE if item == MALE else S.INV_FEMALE_PICTURE), v)

    # ------------------------------------------------------------------ seams
    def _seams(self):
        e = self.e

        def draw_item(emu):
            # DrawItem(x, y, item, state, position, selected): what it would draw for an outfit is the field
            self.draws.append((s32(emu.arg(0)), s32(emu.arg(1)), emu.arg(2), self.field(MALE), self.field(FEMALE)))
            return 0, 0x18
        self.seam(self.s("INV_DRAW_ITEM"), draw_item)
        self.seam(self.target("tt_add_item", 0x29), lambda emu: (0, 4))           # UpdateHintText
        self.window = e.alloc(0x40)
        self.seam(self.target("tt_draw_in_hand", 0x1B), lambda emu: (self.window, 0))   # ldwGameWindow::Get

        def cursor(emu):
            emu.write(emu.arg(0), struct.pack("<ii", *self.cursor))
            return emu.arg(0), 4
        self.seam(self.target("tt_draw_in_hand", 0x22), cursor)                  # GetCursorPos
        self.seam(self.target("tt_draw_in_hand", 0x41), lambda emu: (0, 0))      # GetInHandState (cdecl)
        # the apply run's villager calls
        self.seam(self.target("ms_apply", 0x18), lambda emu: (self.villagers[emu.arg(0)], 4))   # GetVillager
        self.seam(self.target("ms_apply", 0x2E), lambda emu: (self.calls.append(("MakeInFocus", emu.arg(0))), 4)[1:]
                  and (0, 4))
        self.seam(self.target("ms_apply", 0x4A), lambda emu: (0, 8))             # ForgetPlans
        self.seam(self.target("ms_apply", 0x5A), lambda emu: (self.calls.append(("NewBehavior", emu.arg(0))), 8)[1:]
                  and (0, 8))
        # theGameState::Save / Load bodies (whatever the vtable slots chain to ends here)
        self.seam(self.s("GS_SAVE"), self._save_body)
        self.seam(self.s("GS_LOAD"), self._load_body)

    def save_content(self, extra=b""):
        """What the game's SaveState writes of the tray and the outfit fields, plus the rest of the save."""
        tray = self.e.read(self.tray, S.TRAY_SAVE_SIZE)
        inv = self.e.read(self.inv + S.INV_BIND_FIRST, 4 * S.INV_BIND_COUNT)
        return b"LDWG" + struct.pack("<I", len(self.saves)) + tray + inv + extra

    def _save_body(self, emu):
        slot = emu.arg(0)
        self.saves.append(slot)
        if slot > 0:
            # ldwGameState::Save: remove slot + 20, rename slot -> slot + 20, write slot
            backup = self.fs.key(self.save_path(slot + S.SAVE_BACKUP_OFFSET))
            self.fs.files.pop(backup, None)
            if self.fs.exists(self.save_path(slot)):
                self.fs.files[backup] = self.fs.files.pop(self.fs.key(self.save_path(slot)))
            self.fs.write(self.save_path(slot), self.save_content())
        return 1, 4

    def _load_body(self, emu):
        slot = emu.arg(0)
        self.loads.append(slot)
        raw = self.fs.read(self.save_path(slot)) if slot > 0 else None
        if slot > 0 and (raw is None or not self.load_result):
            return 0, 4
        if raw is not None:
            self.restore(raw[8:8 + S.TRAY_SAVE_SIZE], raw[8 + S.TRAY_SAVE_SIZE:8 + S.TRAY_SAVE_SIZE + 36])
        return 1, 4

    def restore(self, tray, inv):
        """CToolTray::LoadState (Reset, then the places; an item < 0 or >= E1h is 0) and
        CInventoryManager::LoadState (the outfit fields 1:1); scenario_the_save_model_is_the_games checks
        this against the real functions."""
        self.reset_tray()
        for k in range(S.TRAY_PLACES):
            item, uses = struct.unpack_from("<ii", tray, 8 * k)
            if item < 0 or item >= S.TRAY_ITEM_LIMIT:
                item = 0
            self.set_place(k, item, uses)
        self.e.write(self.inv + S.INV_BIND_FIRST, inv)
        self.e.w32(self.tray + S.TRAY_HELD, INVALID)

    # ------------------------------------------------------------------ the game, run for real
    def run_range(self, start, until, regs=None):
        e = self.e
        esp = e.sp_top - 0x400
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

    def buy(self, store_item):
        """The store's buy of an outfit row: HandlePurchaseItem from its TakeOne to its AddItem, for real."""
        scene = self.e.alloc(0x200)
        self.e.w32(scene + S.STORE_SCENE_ITEM, store_item)
        p = self.p("st_buy")
        self.run_range(p, p + 0x68, {UC_X86_REG_EAX: store_item, UC_X86_REG_ESI: scene})
        return self.e.r32(scene + S.STORE_SCENE_ITEM)

    def draw(self):
        """CToolTray::Draw (every place but the one in the hand): [(place, item, picture drawn)]."""
        self.draws = []
        self.e.call(self.p("tt_draw"), (), ecx=self.tray)
        out = []
        for x, y, item, male, female in self.draws:
            assert x == H // 2, x
            k = (y - TOP - H // 2 - 6) // H
            assert y == TOP + k * H + H // 2 + 6
            out.append((k, item, male if item == MALE else female if item == FEMALE else None))
        # the two fixed tools are drawn first, as they are; the rest is what the scenario looks at
        assert out[:2] == [(0, 1, None), (1, 2, None)], out
        return out[2:]

    def draw_in_hand(self):
        self.draws = []
        self.e.call(self.p("tt_draw_in_hand"), (), ecx=self.tray)
        assert len(self.draws) <= 1
        if not self.draws:
            return None
        x, y, item, male, female = self.draws[0]
        assert (x, y) == self.cursor
        return item, male if item == MALE else female if item == FEMALE else None

    def point(self, k):
        return H // 2, TOP + k * H + 20

    def click(self, k):
        """CToolTray::HandleMouseDown on place k."""
        x, y = self.point(k)
        return self.e.call(self.p("tt_mouse_down"), (x, y), ecx=self.tray) & 0xFF

    def drop(self, k):
        """CToolTray::HandleMouseUp on place k."""
        x, y = self.point(k)
        return self.e.call(self.p("tt_mouse_up"), (x, y), ecx=self.tray) & 0xFF

    def hold(self, k, in_use=True):
        """Pick place k up (the game's own click), and, dropped on the world, it is in use."""
        assert self.click(k) == 1
        assert s32(self.e.r32(self.tray + S.TRAY_HELD)) == k
        if in_use:
            self.e.write(self.tray + S.TRAY_IN_USE, b"\x01")

    def villager(self, gender, body=0):
        index = len(self.villagers)
        v = self.e.alloc(0x1CC10)
        self.e.w32(v + S.VILLAGER_GENDER, gender)
        self.e.w32(v + S.VILLAGER_BODY, body)
        self.villagers[index] = v
        return index

    def put_on(self, index, tool):
        """theMainScene::HandleMouseDown's apply: the tool in use (ecx) dropped on villager `index`; returns the
        villager's body afterwards."""
        p = self.p("ms_apply")
        self.run_range(p, p + 0x69, {UC_X86_REG_ECX: tool, UC_X86_REG_EDI: index})
        return s32(self.e.r32(self.villagers[index] + S.VILLAGER_BODY))

    def via_slot(self, vslot, slot):
        fn = self.e.r32(self.s("GS_VTABLE") + vslot)
        return self.e.call(fn, (slot,), ecx=self.state) & 0xFF

    def save(self, slot=1):
        return self.via_slot(S.GS_SAVE_VSLOT, slot)

    def load(self, slot=1):
        return self.via_slot(S.GS_LOAD_VSLOT, slot)


# ====================================================================== helpers
def two_males(w, first=5, second=9):
    """Buy a male outfit at picture `first`, then another at `second` (the store redrew in between)."""
    w.set_store(male=(first, 4, 5))
    assert w.buy(S.STORE_MALE_FIRST) == MALE
    w.set_store(male=(second, 4, 5))
    assert w.buy(S.STORE_MALE_FIRST) == MALE
    assert w.places()[2:4] == [(MALE, 1), (MALE, 1)]


# ====================================================================== the stock game (install=False)
def scenario_stock_every_outfit_is_the_last_one_bought(w: OutfitWorld):
    """Without the fix: two male outfits bought at pictures 5 and 9 both show 9, and the first one puts 9 on."""
    assert not w.installed
    two_males(w)
    assert w.field(MALE) == 9
    assert w.draw() == [(2, MALE, 9), (3, MALE, 9)]
    boy = w.villager(0)
    w.hold(2)
    assert w.draw_in_hand() == (MALE, 9)
    assert w.put_on(boy, MALE) == 9                     # the first outfit puts on the second one's picture
    assert w.places()[2] == (0, 0)                      # UseTool spent it


STOCK = [scenario_stock_every_outfit_is_the_last_one_bought]


# ====================================================================== the fix
def scenario_each_outfit_keeps_its_picture(w: OutfitWorld):
    two_males(w)
    assert w.kept()[2:4] == [(MALE, 5), (MALE, 9)]
    assert w.field(MALE) == 9
    assert w.draw() == [(2, MALE, 5), (3, MALE, 9)]
    assert w.field(MALE) == 9, "the field the save holds is put back after every draw"
    st = w.status()
    assert st["known"] == 2 and st["lent"] == 2


def scenario_the_one_in_the_hand_shows_and_puts_on_its_own(w: OutfitWorld):
    two_males(w)
    boy, other = w.villager(0, body=1), w.villager(0, body=1)
    w.hold(2)
    assert w.draw_in_hand() == (MALE, 5)
    assert w.draw() == [(3, MALE, 9)]                   # the held place is not drawn in the tray
    assert w.put_on(boy, MALE) == 5
    assert w.places()[2] == (0, 0)
    w.draw()                                             # the next frame: the spent place is forgotten
    assert w.kept()[2] == (0, -1)
    assert w.field(MALE) == 9
    w.hold(3)
    assert w.draw_in_hand() == (MALE, 9)
    assert w.put_on(other, MALE) == 9
    assert w.status()["applied"] == 2


def scenario_female_outfits(w: OutfitWorld):
    w.set_store(female=(6, 7, 8))
    assert w.buy(S.STORE_FEMALE_FIRST + 2) == FEMALE     # the rare one, picture 8
    assert w.buy(S.STORE_FEMALE_FIRST) == FEMALE         # the common one, picture 6
    assert w.field(FEMALE) == 6
    assert w.draw() == [(2, FEMALE, 8), (3, FEMALE, 6)]
    girl = w.villager(1)
    w.hold(2)
    assert w.put_on(girl, FEMALE) == 8


def scenario_both_sexes_apart(w: OutfitWorld):
    w.set_store(male=(11, 12, 13), female=(21, 22, 23))
    w.buy(S.STORE_MALE_FIRST + 1)                        # male 12
    w.buy(S.STORE_FEMALE_FIRST)                          # female 21
    w.set_store(male=(31, 32, 33), female=(41, 42, 43))
    w.buy(S.STORE_MALE_FIRST)                            # male 31
    w.buy(S.STORE_FEMALE_FIRST + 2)                      # female 43
    assert w.draw() == [(2, MALE, 12), (3, FEMALE, 21), (4, MALE, 31), (5, FEMALE, 43)]
    assert (w.field(MALE), w.field(FEMALE)) == (31, 43)


def scenario_a_click_swap_moves_the_pictures(w: OutfitWorld):
    two_males(w)
    w.hold(2, in_use=False)                              # picked up
    assert w.click(4) == 1                               # clicked on the empty place 4: SwapSlots(2, 4)
    assert w.places()[2] == (0, 0) and w.places()[4] == (MALE, 1)
    assert w.kept()[4] == (MALE, 5) and w.kept()[2] == (0, -1)
    assert w.draw() == [(3, MALE, 9), (4, MALE, 5)]
    w.hold(3, in_use=False)
    assert w.click(4) == 1                               # two outfits swap places
    assert w.draw() == [(3, MALE, 5), (4, MALE, 9)]


def scenario_a_drag_and_drop_moves_the_pictures(w: OutfitWorld):
    two_males(w)
    w.hold(2, in_use=False)
    assert w.drop(6) == 1                                # dragged onto place 6: SwapSlots(2, 6)
    assert w.places()[6] == (MALE, 1)
    assert w.draw() == [(3, MALE, 9), (6, MALE, 5)]
    w.hold(6, in_use=False)
    assert w.drop(3) == 1
    assert w.draw() == [(3, MALE, 5), (6, MALE, 9)]
    boy = w.villager(0)
    w.hold(3)
    assert w.put_on(boy, MALE) == 5


def scenario_a_used_place_forgets_and_a_new_buy_remembers(w: OutfitWorld):
    two_males(w)
    w.hold(2)
    w.put_on(w.villager(0), MALE)
    w.set_store(male=(17, 4, 5))
    w.buy(S.STORE_MALE_FIRST)                            # fills place 2 again
    assert w.places()[2] == (MALE, 1)
    assert w.draw() == [(2, MALE, 17), (3, MALE, 9)]
    assert w.field(MALE) == 17, "the field is put back after the lent picture"


def scenario_an_outfit_the_dll_did_not_see_is_stock(w: OutfitWorld):
    """A place the DLL never saw bought (an old save's, before the fix) shows and gives the stock field."""
    w.set_place(5, MALE)
    w.set_field(MALE, 14)
    assert w.draw() == [(5, MALE, 14)]
    w.hold(5)
    assert w.put_on(w.villager(0), MALE) == 14
    assert w.status()["applied"] == 0 and w.status()["lent"] == 0


def scenario_a_new_family_forgets(w: OutfitWorld):
    """theGameState::Init resets the tray (CToolTray::Reset: item 4 in place 2, the rest empty); the next
    frame's draw forgets every picture whose place no longer holds its outfit."""
    two_males(w)
    w.reset_tray()
    w.set_place(2, 4)
    assert w.draw() == [(2, 4, None)]
    assert w.kept()[2:4] == [(0, -1), (0, -1)]
    w.set_place(3, MALE)                                 # a male outfit in the same place, never bought here
    w.set_field(MALE, 2)
    assert w.draw() == [(2, 4, None), (3, MALE, 2)]


def scenario_expansion_outfits_are_unchanged(w_factory):
    """The patcher's own expansion outfits (synthetic tray items the game reports as the stock tool) give
    exactly what they give without the DLL; a stock outfit bought beside them keeps its own picture."""
    results = []
    for install in (False, True):
        w = w_factory(install)
        w.set_store(male=(5, 4, 5))
        w.buy(S.STORE_MALE_FIRST)                        # a stock male outfit, place 2
        expansion = 0x440 + 3                            # an expansion male outfit (OUTFIT_STORE_GENDER_ITEM_BASES)
        w.set_place(3, expansion)
        w.hold(3)
        boy = w.villager(0, body=1)
        body = w.put_on(boy, MALE)                       # the game reports the expansion outfit as 49h
        drawn = w.draw()
        results.append((body, drawn[0]))
    stock, fixed = results
    assert fixed[0] == stock[0] and fixed[0] not in (-1, 1), results
    assert fixed[1] == (2, MALE, 5)


def scenario_the_draw_prefix_leaves_stock_outfits_to_the_stock_cases(w: OutfitWorld):
    """B200's added-icon prefix at DrawItem's entry draws only the patcher's own icons: for 49h and 4Ah it
    returns false, so the stock switch (the +468h / +46Ch cases the lent picture is in) draws them."""
    prefix = w.target("inv_draw_item", 0x16)
    for item in (MALE, FEMALE):
        assert w.e.call(prefix, (36, 50, item, 0, 0, 0)) & 0xFF == 0, hex(item)


def scenario_save_and_load_keep_the_pictures(w: OutfitWorld):
    two_males(w)
    assert w.save(1) == 1
    side = w.sidecar(1)
    raw = w.fs.read(w.save_path(1))
    assert side["save_hash"] == fnv(raw) and side["save_size"] == len(raw)
    assert side["pictures"] == [-1, -1, 5, 9, -1, -1, -1, -1, -1]
    assert side["places"][:4] == [(1, -1), (2, -1), (MALE, 1), (MALE, 1)]
    assert side["inventory"][6] == 9                     # +468h, the last male bought
    assert w.status()["lastSave"] == 1
    # the DLL never opens the save file for writing, and writes the sidecar through a temp file
    assert not [x for x in w.fs.log if x[0] == "CreateFileA" and x[2] == 2 and x[1].endswith(".ldw")]
    assert ("MoveFileExA", w.sidecar_path(1) + ".tmp", w.sidecar_path(1), 9) in w.fs.log
    # a reload (the game's LoadState rebuilds the tray)
    w.reset_tray()
    assert w.load(1) == 1
    assert w.status()["lastLoad"] == 1
    assert w.draw() == [(2, MALE, 5), (3, MALE, 9)]
    w.hold(2)
    assert w.put_on(w.villager(0), MALE) == 5


def scenario_settings_saves_and_loads_are_left_alone(w: OutfitWorld):
    two_males(w)
    assert w.save(0) == 1 and w.load(0) == 1
    assert w.saves == [0] and w.loads == [0]
    assert not [x for x in w.fs.log if "Outfits" in x[1]]
    assert w.kept()[2:4] == [(MALE, 5), (MALE, 9)]


def scenario_an_old_save_shows_the_stock_pictures(w: OutfitWorld):
    w.set_place(2, MALE)
    w.set_place(3, MALE)
    w.set_field(MALE, 9)
    w.fs.write(w.save_path(1), w.save_content(b"old"))   # an old save, no sidecar
    assert w.load(1) == 1
    assert w.status()["lastLoad"] == 4 and w.status()["known"] == 0
    assert w.draw() == [(2, MALE, 9), (3, MALE, 9)]
    assert w.save(1) == 1                                # nothing known: nothing written
    assert w.status()["lastSave"] == 2 and not w.fs.exists(w.sidecar_path(1))


def scenario_another_saves_sidecar_is_not_used(w: OutfitWorld):
    two_males(w)
    w.save(1)
    side = w.fs.read(w.sidecar_path(1))
    w.reset_tray()
    w.set_place(2, MALE)
    w.set_place(3, MALE)
    w.set_place(4, MALE)                                 # a different tray
    w.fs.write(w.save_path(1), w.save_content(b"other"))
    w.fs.write(w.sidecar_path(1), side)
    assert w.load(1) == 1
    assert w.status()["lastLoad"] == 4 and w.status()["known"] == 0
    assert [d[2] for d in w.draw()] == [9, 9, 9]


def scenario_a_tool_edited_save_keeps_the_pictures(w: OutfitWorld):
    """Rename Family or Game Speed rewrite the save but not its tray or outfits: the hash differs, the
    described state is exactly the loaded one, so the pictures are kept."""
    two_males(w)
    w.save(1)
    raw = bytearray(w.fs.read(w.save_path(1)))
    raw += b" renamed"
    w.fs.write(w.save_path(1), bytes(raw))
    w.reset_tray()
    assert w.load(1) == 1
    assert w.status()["lastLoad"] == 3
    assert w.draw() == [(2, MALE, 5), (3, MALE, 9)]


def scenario_a_changed_store_is_another_state(w: OutfitWorld):
    """Only the exact state counts: a save whose outfit fields differ is not described."""
    two_males(w)
    w.save(1)
    raw = bytearray(w.fs.read(w.save_path(1)))
    struct.pack_into("<i", raw, 8 + S.TRAY_SAVE_SIZE, 77)   # the store's first picture redrawn
    w.fs.write(w.save_path(1), bytes(raw))
    assert w.load(1) == 1
    assert w.status()["lastLoad"] == 4
    assert [d[2] for d in w.draw()] == [9, 9]


def scenario_a_damaged_sidecar_is_moved_aside(w: OutfitWorld):
    two_males(w)
    w.save(1)
    raw = bytearray(w.fs.read(w.sidecar_path(1)))
    raw[40] ^= 0x01                                      # one byte of what it describes: the checksum fails
    w.fs.write(w.sidecar_path(1), bytes(raw))
    assert w.load(1) == 1
    st = w.status()
    assert st["lastLoad"] == 5 and st["known"] == 0
    aside = w.sidecar_path(1)[:-4] + ".unreadable-1.dat"
    assert w.fs.read(aside) == bytes(raw), "kept, never deleted"
    assert not w.fs.exists(w.sidecar_path(1))
    assert [d[2] for d in w.draw()] == [9, 9]            # fail-open: the stock pictures
    for bad in (b"", b"VF2OUTFT", bytes(SIDECAR_SIZE), bytes(raw) + b"x"):
        w.fs.write(w.sidecar_path(1), bad)
        assert w.load(1) == 1 and w.status()["lastLoad"] == 5, bad[:8]


def scenario_a_wrong_version_or_picture_is_damaged(w: OutfitWorld):
    two_males(w)
    w.save(1)
    good = w.fs.read(w.sidecar_path(1))
    for off, value in ((8, 2), (144 + 4 * 2, 0x100), (144 + 4 * 0, 3)):   # version 2; picture 100h; a picture on place 0
        raw = bytearray(good)
        struct.pack_into("<i", raw, off, value)
        struct.pack_into("<Q", raw, len(raw) - 8, fnv(bytes(raw[:-8])))
        w.fs.write(w.sidecar_path(1), bytes(raw))
        w.reset_tray()
        assert w.load(1) == 1 and w.status()["lastLoad"] == 5, off


def scenario_a_locked_sidecar_is_never_replaced(w: OutfitWorld):
    two_males(w)
    w.save(1)
    path = w.sidecar_path(1)
    before = w.fs.read(path)
    w.fs.hold(path)
    w.reset_tray()
    assert w.load(1) == 1
    assert w.status()["lastLoad"] == 6
    assert len(w.fs.sleeps) == OPEN_TRIES - 1            # it was tried again before it was given up on
    w.set_store(male=(30, 4, 5))
    w.buy(S.STORE_MALE_FIRST)
    assert w.save(1) == 1
    assert w.status()["lastSave"] == 4
    assert w.fs.read(path) == before, "a shut sidecar is never replaced"
    assert not w.fs.exists(w.sidecar_path(1 + S.SAVE_BACKUP_OFFSET))
    assert not [x for x in w.fs.log if x[0] in ("MoveFileExA", "DeleteFileA") and x[1] == path]
    # released: the next save rotates it with its save, and writes the new one
    w.fs.release(path)
    assert w.save(1) == 1 and w.status()["lastSave"] == 1
    assert w.sidecar(1)["pictures"][4] == 30


def scenario_a_sidecar_locked_only_briefly_is_read(w: OutfitWorld):
    two_males(w)
    w.save(1)
    w.fs.hold(w.sidecar_path(1), opens=2)
    w.reset_tray()
    assert w.load(1) == 1 and w.status()["lastLoad"] == 1
    assert w.draw() == [(2, MALE, 5), (3, MALE, 9)]


def scenario_the_backup_slot_follows_its_save(w: OutfitWorld):
    """The game keeps the previous save at slot + 20: its sidecar goes with it, and a restored backup gets its
    own pictures back."""
    two_males(w)                                         # 5, 9
    w.save(1)
    first = w.fs.read(w.save_path(1))
    w.hold(2, in_use=False)
    w.drop(3)                                            # now 9, 5
    w.set_store(male=(40, 4, 5))
    w.buy(S.STORE_MALE_FIRST)                            # the first free place, 4: 40
    w.save(1)
    backup = w.sidecar(1 + S.SAVE_BACKUP_OFFSET)
    assert w.fs.read(w.save_path(21)) == first
    assert backup["save_hash"] == fnv(first) and backup["pictures"][2:4] == [5, 9]
    assert w.sidecar(1)["pictures"][2:5] == [9, 5, 40]
    # the player restores the backup in place of the save
    w.fs.write(w.save_path(1), first)
    w.reset_tray()
    assert w.load(1) == 1
    assert w.status()["lastLoad"] == 2
    assert w.draw() == [(2, MALE, 5), (3, MALE, 9)]


def scenario_a_third_save_drops_the_oldest(w: OutfitWorld):
    two_males(w)
    w.save(1)
    w.set_store(male=(41, 4, 5))
    w.buy(S.STORE_MALE_FIRST)
    w.save(1)
    w.set_store(male=(42, 4, 5))
    w.buy(S.STORE_MALE_FIRST)
    w.save(1)
    assert w.sidecar(21)["pictures"][2:5] == [5, 9, 41]
    assert w.sidecar(1)["pictures"][2:6] == [5, 9, 41, 42]
    assert w.sidecar(21)["save_hash"] == fnv(w.fs.read(w.save_path(21)))
    assert w.sidecar(1)["save_hash"] == fnv(w.fs.read(w.save_path(1)))


def scenario_a_damaged_backup_sidecar_is_set_aside(w: OutfitWorld):
    two_males(w)
    w.save(1)
    w.save(1)
    w.fs.write(w.sidecar_path(21), b"garbage")
    w.save(1)
    aside = w.sidecar_path(21)[:-4] + ".unreadable-1.dat"
    assert w.fs.read(aside) == b"garbage"
    assert w.sidecar(21)["save_hash"] == fnv(w.fs.read(w.save_path(21)))


def scenario_a_failed_load_forgets(w: OutfitWorld):
    two_males(w)
    w.load_result = 0
    w.fs.write(w.save_path(2), b"x")
    assert w.load(2) == 0
    assert w.kept()[2:4] == [(0, -1), (0, -1)]


def scenario_the_save_model_is_the_games(w: OutfitWorld):
    """The fake save body above stands for CToolTray::SaveState / LoadState and CInventoryManager::SaveState /
    LoadState: run the REAL four on a tray and an inventory and compare."""
    e = w.e
    w.set_place(2, MALE, 1)
    w.set_place(3, 0x4C3, 1)                             # an expansion hairstyle: LoadState drops it
    w.set_place(4, -5, 1)
    w.set_store(male=(1, 2, 3), female=(4, 5, 6))
    w.set_field(MALE, 7)
    w.set_field(FEMALE, 8)
    tray_buf = e.alloc(0x100)
    e.call(w.p("tt_save_state"), (tray_buf,), ecx=w.tray)
    assert e.read(tray_buf, S.TRAY_SAVE_SIZE) == e.read(w.tray, S.TRAY_SAVE_SIZE)
    inv_buf = e.alloc(0x500)
    e.call(w.p("inv_save_state"), (inv_buf,), ecx=w.inv)
    bind = e.read(inv_buf + S.INV_BIND_FIRST, 36)
    assert bind == e.read(w.inv + S.INV_BIND_FIRST, 36)
    saved_tray = e.read(tray_buf, S.TRAY_SAVE_SIZE)
    # the model
    w.restore(saved_tray, bind)
    model = (w.places(), e.read(w.inv + S.INV_BIND_FIRST, 36))
    # the real LoadState pair (Reset inside LoadState runs for real except its hint text and its Get)
    w.reset_tray()
    e.write(w.inv + S.INV_BIND_FIRST, bytes(36))
    get = w.call_target(w.target("tt_load_state", 0x0A) + 0x23)       # Reset's theGameState::Get
    flag = e.alloc(0x26000)
    w.seam(get, lambda emu: (flag, 0))
    assert w.target("tt_load_state", 0x40) == w.target("tt_add_item", 0x29)   # UpdateHintText, seamed
    e.call(w.p("tt_load_state"), (tray_buf,), ecx=w.tray)
    e.call(w.p("inv_load_state"), (inv_buf,), ecx=w.inv)
    real = (w.places(), e.read(w.inv + S.INV_BIND_FIRST, 36))
    assert real == model, (real, model)
    assert real[0][3] == (0, 1) and real[0][4] == (0, 1) and real[0][2] == (MALE, 1)


ALL = [scenario_each_outfit_keeps_its_picture, scenario_the_one_in_the_hand_shows_and_puts_on_its_own,
       scenario_female_outfits, scenario_both_sexes_apart, scenario_a_click_swap_moves_the_pictures,
       scenario_a_drag_and_drop_moves_the_pictures, scenario_a_used_place_forgets_and_a_new_buy_remembers,
       scenario_an_outfit_the_dll_did_not_see_is_stock, scenario_a_new_family_forgets,
       scenario_the_draw_prefix_leaves_stock_outfits_to_the_stock_cases, scenario_save_and_load_keep_the_pictures, scenario_settings_saves_and_loads_are_left_alone,
       scenario_an_old_save_shows_the_stock_pictures, scenario_another_saves_sidecar_is_not_used,
       scenario_a_tool_edited_save_keeps_the_pictures, scenario_a_changed_store_is_another_state,
       scenario_a_damaged_sidecar_is_moved_aside, scenario_a_wrong_version_or_picture_is_damaged,
       scenario_a_locked_sidecar_is_never_replaced, scenario_a_sidecar_locked_only_briefly_is_read,
       scenario_the_backup_slot_follows_its_save, scenario_a_third_save_drops_the_oldest,
       scenario_a_damaged_backup_sidecar_is_set_aside, scenario_a_failed_load_forgets,
       scenario_the_save_model_is_the_games]
FACTORY = [scenario_expansion_outfits_are_unchanged]


# ====================================================================== the setting off / on
def _startup(w, ini):
    e = w.e
    seen = []

    def module_name(emu):
        emu.write(emu.arg(1), DLL_PATH.encode("utf-16-le") + b"\0\0")
        return len(DLL_PATH), 12

    def profile(emu):
        seen.append((emu.wstr(emu.arg(0)), emu.wstr(emu.arg(1)), emu.arg(2), emu.wstr(emu.arg(3))))
        return (ini if ini is not None else emu.arg(2)), 16
    e.imports.update({"GetModuleFileNameW": module_name, "GetPrivateProfileIntW": profile})
    e.call(e.dll_export("B200Outfits_Startup"))
    return seen


def scenario_setting_off_writes_nothing(w: OutfitWorld):
    seen = _startup(w, None)
    assert seen == [("Patches", "OutfitPictures", 0, "C:\\Game\\Virtual Families 2 Patcher Files\\vf2outfits.ini")]
    st = w.status()
    assert st["requested"] == 0 and st["installed"] == 0 and st["writeMask"] == 0
    assert w.changed_code() == set()
    assert w.e.r32(w.s("GS_VTABLE") + S.GS_LOAD_VSLOT) == w.s("GS_LOAD")
    assert w.e.r32(w.s("GS_VTABLE") + S.GS_SAVE_VSLOT) == w.s("GS_SAVE")
    two_males(w)
    assert [d[2] for d in w.draw()] == [9, 9]            # the stock game
    assert w.fs.files == {}


def scenario_setting_on_installs_everything(w: OutfitWorld):
    _startup(w, 1)
    st = w.status()
    assert st["requested"] == 1 and st["resolved"] == 1 and st["installed"] == 1
    n = len(S.CALL_HOOKS) + 2
    assert st["writeMask"] == (1 << n) - 1
    sites = [w.s(name) for name in S.CALL_HOOKS]
    assert w.changed_code() <= {a + k for a in sites for k in range(5)}, "nothing but the planned calls"
    for name in S.CALL_HOOKS:
        assert DLL_BASE <= w.call_target(w.s(name)) < DLL_BASE + 0x100000, name
    for vslot in (S.GS_LOAD_VSLOT, S.GS_SAVE_VSLOT):
        assert DLL_BASE <= w.e.r32(w.s("GS_VTABLE") + vslot) < DLL_BASE + 0x100000
    two_males(w)
    assert w.draw() == [(2, MALE, 5), (3, MALE, 9)]


def scenario_another_dll_on_the_slots_is_chained(w: OutfitWorld):
    """Time Controls / Family History replace the Save and Load slots first: this DLL chains to them."""
    e = w.e
    seen = []
    vt = w.s("GS_VTABLE")
    for vslot, name in ((S.GS_LOAD_VSLOT, "load"), (S.GS_SAVE_VSLOT, "save")):
        stock = e.r32(vt + vslot)
        stub = e.fake_code(b"\xC2\x04\x00")

        def other(emu, name=name, stock=stock):
            seen.append(name)
            return (w._save_body if name == "save" else w._load_body)(emu)
        w.seam(stub, other)
        e.w32(vt + vslot, stub)
        assert stock in (w.s("GS_LOAD"), w.s("GS_SAVE"))
    status, writes = w.test_plan(True)
    assert status == 1
    for va, raw, _data in writes:
        e.write(va, raw)
    two_males(w)
    w.save(1)
    w.reset_tray()
    w.load(1)
    assert seen == ["save", "load"]
    assert w.draw() == [(2, MALE, 5), (3, MALE, 9)]


OFF = [scenario_setting_off_writes_nothing, scenario_setting_on_installs_everything,
       scenario_another_dll_on_the_slots_is_chained]


# ====================================================================== the executable's own loader
EXE_PATH = "C:\\Game\\Virtual Families 2 - B204.exe"


def section_va(exe_path, name):
    import pefile
    pe = pefile.PE(str(exe_path), fast_load=True)
    found = [pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress for s in pe.sections if s.Name.rstrip(b"\0") == name]
    assert len(found) == 1, f"the executable has no {name!r} section"
    return found[0]


def run_loader(exe, dll, delta, bugs_flag, ini, others=0, dll_present=True):
    """Run the executable's REAL loader wrapper (theGame::Init's first call) with this DLL as the one it loads
    for Outfit Pictures (the Fix Vanilla Game Bugs byte); the other companion DLLs are absent unless `others`.
    Returns (world, wrapper result, calls log)."""
    import b200_time_scenarios as T
    w = OutfitWorld(exe, dll, delta, install=False)
    e = w.e
    _flag, _call, wrapper = T.loader_sites(exe)
    log = []
    e.write(section_va(exe, b".vf2bugs") + delta, bytes([bugs_flag]))
    for name in (b".vf2time", b".vf2kids", b".vf2hist"):
        e.write(section_va(exe, name) + delta, bytes([others]))
    # theGame::Init's first call returns theGameState::Get(): the instance pointer the wrapper reads
    gs_get = None
    import b200_history_sites as HS
    import gen_b200_history_sites as HG
    hmodel = HG.validate(Path(os.environ.get("VF2_B200_CORE_EXE") or exe).read_bytes())
    hsites = HG.resolve(HG.Exe(Path(exe).read_bytes()), hmodel)
    gs_get = hsites["GAME_STATE_INSTANCE"] + delta
    e.w32(gs_get, w.state)

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
        return (emu.dll_export("B200Outfits_Startup") if name == "B200Outfits_Startup" else 0), 8
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
    e.call(e.dll_export("B200Outfits_TestSetModule"), (DLL_BASE,))
    result = e.call(wrapper + delta, ())
    del HS
    return w, result, log


def scenario_loader_cases(exe, dll, delta):
    """The loader: the Fix Vanilla Game Bugs byte 0 never loads the DLL; 1 loads it, last; the DLL installs
    only when its ini says 1, and then exactly its planned writes are made."""
    others = ["C:\\Game\\Virtual Families 2 Patcher Files\\vf2time_b200.dll",
              "C:\\Game\\Virtual Families 2 Patcher Files\\vf2kids_b200.dll",
              "C:\\Game\\Virtual Families 2 Patcher Files\\vf2history_b200.dll"]
    for flag, ini, other, present, installs in (
            (0, 1, 0, True, False), (1, 0, 0, True, False), (1, 1, 0, False, False),
            (1, 1, 0, True, True), (1, 1, 1, True, True), (0, 1, 1, True, False)):
        w, result, log = run_loader(exe, dll, delta, flag, ini, other, present)
        assert result == w.state, "the wrapper must return theGameState::Get()'s result"
        loads = [x for x in log if x.startswith("exe:LoadLibraryW")]
        expect = ([f"exe:LoadLibraryW {p}" for p in others] if other else []) + \
                 ([f"exe:LoadLibraryW {DLL_PATH}"] if flag else [])
        assert loads == expect, (flag, ini, other, log)
        changed = w.changed_code()
        st = w.status()
        if not installs:
            assert not changed and st["installed"] == 0, (flag, ini, present)
            if flag and present:
                assert [x for x in log if x.startswith("dll:GetPrivateProfileIntW")] == [
                    "dll:GetPrivateProfileIntW Patches OutfitPictures "
                    "C:\\Game\\Virtual Families 2 Patcher Files\\vf2outfits.ini"]
            continue
        assert st["requested"] == 1 and st["resolved"] == 1 and st["installed"] == 1
        sites = [w.s(name) for name in S.CALL_HOOKS]
        assert changed <= {a + k for a in sites for k in range(5)}
        two_males(w)
        assert w.draw() == [(2, MALE, 5), (3, MALE, 9)]
    import b200_time_scenarios as T
    w, result, log = run_loader(exe, dll, delta, 1, 1)
    again = w.e.call(T.loader_sites(exe)[2] + delta, ())
    assert again == w.state
    assert len([x for x in log if x.startswith("exe:LoadLibraryW")]) == 1
