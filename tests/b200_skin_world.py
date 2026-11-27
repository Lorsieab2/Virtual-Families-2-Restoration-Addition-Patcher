"""The Skin Tones DLL (vf2skin_b200.dll) under emulation, on the REAL B209 core executable (tests/b200_time_emu.py).

A SkinWorld is one emulated process: the B209 core executable (at its link address or relocated, as Windows does with
ASLR) and the REAL compiled test DLL (runtime/native/build_b200skin.bat test: the shipped source with one export more,
B200Skin_TestScanAddress, so the resolver's byte scan can be answered in Python). The DLL installs itself through its
own B200Skin_Startup: the setting, the resolver (every pin found in the live image), the plan, every hook written
with VirtualProtect.

Game code that runs for real: CVillagerManager::DrawVillager (and DrawCarriedItems inside it, and the generated
Holiday body helper), CVillager::DrawDetailVillager and DrawEventVillager (and the portraits' Holiday helper),
CFamilyTreeScene::DrawParent / DrawChild / DrawPeep entered at DrawFamily's own call instructions with the record in
the register DrawFamily keeps it in, CSceneManager::Draw / DrawScaled, ldwGameWindow::DrawScaled, GetCellRect,
ClipRect, ScaledClipRect, SetClipping, theGraphicsManager::Get / GetImageGrid and the image table lookup, the
anim manager's empty link tables, CVillager::Impregnate's two callers' call instructions (the conception) and
theVillagerScene's ChangeName calls.

Seams (recorded, never real): the anim manager's three link functions answer the point (0, 0) and hand out the grid
and cell a scenario queues (in the game they come from Assets\\anims.dat); CWorldMap::IsOnMap, CContentMap::
GetMaterial and ldwGameState::GetRandom answer 0; CVillager::Impregnate's body makes the babies' records itself (as
the game does: hidden, in the reserved slots); CFamilyTree::ChangeName records; theGameState::Load / Save bodies;
MakeGameStatePath (a fixed folder); every Win32 and SDL import of the DLL (an in-memory file system over the real
vanilla Images, the B209 build's Holiday pictures and the patcher's Skin Masks folder, read only; SDL surfaces in the
emulator's memory).

ldwGameWindowImpl::BlitRectWithAlpha is entered for real (the DLL's hook, then its trampoline); what the game's own
blitter is then given (the surface, the rectangle, the place, the scale) is recorded where the trampoline lands
(entry + 9), and the blit returns from there.
"""
from __future__ import annotations

import os
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "runtime" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import b200_skin_sites as S  # noqa: E402
import gen_b200_skin_sites as G  # noqa: E402
from b200_time_emu import DLL_BASE, Emu, EmuError  # noqa: E402
from unicorn import UC_HOOK_CODE, UcError  # noqa: E402
from unicorn.x86_const import (UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,  # noqa: E402
                               UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)

MASKS = ROOT / "patcher_assets" / "skin_masks"
GAME = "C:\\Game\\"
FOLDER = GAME + "Virtual Families 2 Patcher Files\\"
DLL_PATH = FOLDER + "vf2skin_b200.dll"
SAVE_DIR = "C:\\Users\\Tester\\Documents\\LDW\\VF2 Skin Test"
TONES_DIR = SAVE_DIR + "\\Virtual Families 2 Patcher Data\\Skin Tones"
INVALID = 0xFFFFFFFF
BIG_BASE, BIG_SIZE = 0x80000000, 0x30000000       # surfaces and the DLL's VirtualAlloc
SDL_MODULE, REVIVE_MODULE = 0x6A000000, 0x6B000000
STRIDE = S.VILLAGER_STRIDE
ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND, ERROR_ALREADY_EXISTS, ERROR_SHARING_VIOLATION = 2, 3, 183, 32

# B209 core (link addresses) of the game state the harness sets up: core-only, never given to the DLL.
CORE = {
    "WINDOW_GLOBAL": 0x686F10,       # ldwGameWindow::Get's instance
    "GRAPHICS_GLOBAL": 0x6FF750,     # theGraphicsManager::Get's instance
    "SCENE_MANAGER": 0x6F80D0,       # the CSceneManager object
    "LINK_NEXT8": 0x404C60,          # CAnimManager::GetScaledLinkToNextPt (8 arguments)
    "LINK_NEXT7": 0x404D10,          # ... (7 arguments)
    "LINK_PREV": 0x404DC0,           # CAnimManager::GetScaledLinkToPrevPt (6 arguments)
    "IS_ON_MAP": 0x4CE2C0,
    "GET_MATERIAL": 0x450BE0,
    "GET_RANDOM": 0x4757C0,
}
SHEET_FILES = {name: (image, part) for image, part, name in S.IMAGE_SHEETS}
GRID_SHAPES = {          # image id: (stem or file, columns, rows, files across)
    0x240: ("female_heads", 24, 50, 2), 0x244: ("male_heads", 24, 50, 2), 0x15: ("bigheads", 12, 50, 2),
    0x241: ("female_bodies00.png", 32, 50, 1), 0x242: ("female_actions00.png", 15, 50, 1),
    0x243: ("female_sit00.png", 9, 50, 1), 0x245: ("male_bodies00.png", 32, 50, 1),
    0x246: ("male_actions00.png", 15, 50, 1), 0x247: ("male_sit00.png", 9, 50, 1),
    0x16: ("highrez_bodies_final2.png", 2, 50, 1), 0x1DE: ("carrying.png", 13, 7, 1),
}
_PIXELS: dict = {}


def png_pixels(path: Path) -> tuple[int, int, bytes]:
    """(w, h, B G R A bytes: an ARGB8888 surface's memory) of a picture, cached."""
    key = str(path)
    if key not in _PIXELS:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(path).convert("RGBA")
        r, g, b, a = im.split()
        from PIL import Image as I
        _PIXELS[key] = (im.width, im.height, I.merge("RGBA", (b, g, r, a)).tobytes())
    return _PIXELS[key]


def f32(v: float) -> int:
    return struct.unpack("<I", struct.pack("<f", v))[0]


_PROVED: dict = {}


def proved(exe_path):
    key = str(exe_path)
    if key not in _PROVED:
        data = Path(key).read_bytes()
        model = G.validate(data)
        _PROVED[key] = (model, G.resolve(G.Exe(data), model))
    return _PROVED[key]


class Files:
    """The DLL's file imports over a dict (case-insensitive paths), with the game's real pictures read only."""

    def __init__(self, images: Path, built: Path):
        self.images, self.built = Path(images), Path(built)
        self.files: dict[str, bytes] = {}
        self.dirs: set[str] = set()
        self.handles: dict[int, dict] = {}
        self.locked: set[str] = set()         # held by another program: every open fails
        self.next = 0x100
        self.last_error = 0
        self.log: list = []
        self.opened: list[str] = []
        self.overrides: dict[str, bytes | None] = {}    # game / mask files replaced (None: missing)

    @staticmethod
    def key(path: str) -> str:
        return path.replace("/", "\\").lower()

    def parent(self, path: str) -> str:
        return self.key(path).rsplit("\\", 1)[0]

    def mkdirs(self, path: str) -> None:
        parts = self.key(path).split("\\")
        for i in range(1, len(parts) + 1):
            self.dirs.add("\\".join(parts[:i]))

    def write(self, path: str, data: bytes) -> None:
        self.mkdirs(self.parent(path))
        self.files[self.key(path)] = bytes(data)

    def read(self, path: str) -> bytes | None:
        return self.files.get(self.key(path))

    def real(self, path: str) -> bytes | None:
        """A file of the game or of the patcher folder: the real one, read only."""
        if path in self.overrides:
            return self.overrides[path]
        low = path.lower()
        if low.startswith((GAME + "Images\\").lower()):
            rel = path[len(GAME + "Images\\"):]
            base = self.built if rel.lower().startswith(("villagerbodies", "villagerdetailbodies")) else self.images
            p = base / rel
        elif low.startswith((FOLDER + "Skin Masks\\").lower()):
            p = MASKS / path[len(FOLDER + "Skin Masks\\"):]
        else:
            return None
        return p.read_bytes() if p.is_file() else None

    def bind(self, emu: Emu) -> None:
        fs = self

        def open_(path, access, disposition, wide):
            k = fs.key(path)
            fs.log.append(("CreateFile" + ("W" if wide else "A"), path, access, disposition))
            if k in fs.locked:
                fs.last_error = ERROR_SHARING_VIOLATION
                return INVALID
            writing = False
            if disposition == 3:                    # OPEN_EXISTING
                data = fs.files.get(k)
                if data is None and wide:
                    data = fs.real(path)
                    if data is not None:
                        fs.opened.append(path)
                if data is None:
                    fs.last_error = ERROR_FILE_NOT_FOUND if fs.parent(path) in fs.dirs or wide else ERROR_PATH_NOT_FOUND
                    return INVALID
                assert access == 0x80000000, f"only reads open existing files ({path})"
            elif disposition == 2:                  # CREATE_ALWAYS (the temp file of a write)
                if fs.parent(path) not in fs.dirs:
                    fs.last_error = ERROR_PATH_NOT_FOUND
                    return INVALID
                data, writing = b"", True
            else:
                raise EmuError(f"CreateFile disposition {disposition} ({path})")
            h = fs.next
            fs.next += 4
            fs.handles[h] = {"key": k, "data": bytearray(data), "pos": 0, "writing": writing}
            return h

        def create_a(e):
            return open_(e.cstr(e.arg(0)), e.arg(1), e.arg(4), False), 28

        def create_w(e):
            path = e.wstr(e.arg(0))
            if path.lower().endswith("vf2skin.log"):
                return INVALID, 28
            return open_(path, e.arg(1), e.arg(4), True), 28

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
            assert st["writing"], "the DLL writes only a file it created"
            st["data"] += e.read(buf, n)
            e.w32(got, n)
            return 1, 20

        def close(e):
            st = fs.handles.pop(e.arg(0))
            if st["writing"]:
                fs.files[st["key"]] = bytes(st["data"])
            return 1, 4

        def size(e):
            st = fs.handles[e.arg(0)]
            if e.arg(1):
                e.w32(e.arg(1), 0)
            return len(st["data"]), 8

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
            if fs.key(path) in fs.locked or fs.files.pop(fs.key(path), None) is None:
                fs.last_error = ERROR_FILE_NOT_FOUND
                return 0, 4
            return 1, 4

        def move(e):
            src, dst, flags = e.cstr(e.arg(0)), e.cstr(e.arg(1)), e.arg(2)
            fs.log.append(("MoveFileExA", src, dst, flags))
            ks, kd = fs.key(src), fs.key(dst)
            if ks in fs.locked or kd in fs.locked:
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

        emu.imports.update({
            "CreateFileA": create_a, "CreateFileW": create_w, "ReadFile": read_file, "WriteFile": write_file,
            "CloseHandle": close, "GetFileSize": size, "CreateDirectoryA": mkdir, "DeleteFileA": delete,
            "MoveFileExA": move, "FlushFileBuffers": lambda e: (1, 4), "GetLastError": lambda e: (fs.last_error, 0),
            "Sleep": lambda e: (0, 4),
        })


class SkinWorld:
    """One emulated process: the B209 core executable + the test DLL, the DLL installed (unless install=False)."""

    def __init__(self, exe, dll, images, built, delta=0, setting=1, install=True, native_scan=False):
        self.exe_path = Path(exe)
        self.e = Emu(exe, dll, delta)
        self.delta = delta
        self.model, self.sites = proved(exe)
        self.seam_fns: dict = {}
        self.fs = Files(images, built)
        self.fs.bind(self.e)
        self.fs.mkdirs(SAVE_DIR)
        self.setting = setting
        self.protects: list = []
        self.surfaces: dict[int, str] = {}
        self.made: dict[int, tuple] = {}
        self.freed: list[int] = []
        self.blits: list[dict] = []
        self.anim_queue: list[tuple[int, int]] = []
        self.revive_members: list[tuple] = []
        self.big_next = BIG_BASE
        self.e.uc.mem_map(BIG_BASE, BIG_SIZE)
        self.code_before = self._code()
        self._imports()
        if not native_scan:
            self._python_scan()
        self._game()
        if install:
            assert self.install() == 1, f"not installed: {self.status()}"

    # ------------------------------------------------------------------ helpers
    def s(self, name):
        return self.sites[name] + self.delta

    def a(self, link):
        return link + self.delta

    def seam(self, addr, fn):
        if addr not in self.seam_fns:
            self.e.seam_live(addr, lambda emu, addr=addr: self.seam_fns[addr](emu))
        self.seam_fns[addr] = fn

    def big(self, n: int) -> int:
        p = self.big_next
        self.big_next += (n + 0xFFF) & ~0xFFF
        if self.big_next > BIG_BASE + BIG_SIZE:
            raise EmuError("the big region is full")
        return p

    def _code(self):
        out = []
        for s in self.e.exe.sections:
            if s.Characteristics & 0x20000000:
                base = self.e.base + s.VirtualAddress
                out.append((base, self.e.read(base, min(s.Misc_VirtualSize, s.SizeOfRawData))))
        return out

    def changed_code(self) -> set[int]:
        changed = set()
        for base, was in self.code_before:
            now = self.e.read(base, len(was))
            if now != was:
                changed.update(base + i for i in range(len(was)) if now[i] != was[i])
        return changed

    def status(self) -> dict:
        names = ("magic", "version", "requested", "resolved", "installed", "entries", "sheets", "refused", "rows",
                 "bytes", "swapped", "made", "lastLoad", "lastSave", "babies", "writeMask")
        raw = self.e.read(self.e.dll_export("B200Skin_Status"), 4 * len(names))
        return dict(zip(names, struct.unpack(f"<{len(names)}I", raw)))

    # ------------------------------------------------------------------ the DLL's imports
    def _python_scan(self):
        e = self.e
        addr = e.call(e.dll_export("B200Skin_TestScanAddress"))

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
        self.seam(addr, scan)

    def _imports(self):
        e = self.e
        w = self

        def protect(emu):
            addr, size, new, old = (emu.arg(i) for i in range(4))
            w.protects.append((addr, size, new))
            emu.w32(old, 0x20 if addr >= emu.base and addr < DLL_BASE else 0x04)
            return 1, 16

        def module_handle(emu):
            name = emu.arg(0)
            if name == 0:
                return emu.base, 4
            n = emu.wstr(name).lower()
            return {"sdl2.dll": SDL_MODULE, "vf2revive_b200.dll": REVIVE_MODULE if w.revive_members is not None
                    else 0}.get(n, 0), 4

        def module_handle_ex(emu):
            flags, address, out = emu.arg(0), emu.arg(1), emu.arg(2)
            assert flags & 4 and DLL_BASE <= address < DLL_BASE + 0x1000000
            emu.w32(out, DLL_BASE)
            return 1, 12

        def module_file_name(emu):
            module, out, room = emu.arg(0), emu.arg(1), emu.arg(2)
            text = GAME + "Virtual Families 2 - B209.exe" if module == 0 else DLL_PATH
            assert len(text) < room
            emu.write(out, text.encode("utf-16-le") + b"\0\0")
            return len(text), 12

        procs = {"SDL_CreateRGBSurface": w._create_surface, "SDL_FreeSurface": w._free_surface,
                 "B200Revive_Members": w._revive_members}

        def proc_address(emu):
            name = emu.cstr(emu.arg(1))
            if name not in procs:
                raise EmuError(f"GetProcAddress {name}")
            key = "dyn:" + name
            for addr, n in emu.thunks.items():
                if n == key:
                    return addr, 8
            addr = 0x70000000 + 0x10 * (len(emu.thunks) + 1)
            emu.thunks[addr] = key
            emu.imports[key] = procs[name]
            return addr, 8

        def profile(emu):
            key = emu.wstr(emu.arg(1))
            path = emu.wstr(emu.arg(3))
            assert path == FOLDER + "vf2skin.ini", path
            return (w.setting if key == "SkinTones" else emu.arg(2)), 16

        def virtual_alloc(emu):
            return w.big(emu.arg(1)), 16

        def perf(emu):
            emu.write(emu.arg(0), struct.pack("<Q", 0x123456789))
            return 1, 4

        e.imports.update({
            "VirtualProtect": protect, "FlushInstructionCache": lambda emu: (1, 12),
            "GetCurrentProcess": lambda emu: (INVALID, 0), "GetCurrentProcessId": lambda emu: (0x1234, 0),
            "GetTickCount": lambda emu: (0x00C0FFEE, 0), "QueryPerformanceCounter": perf,
            "GetModuleHandleW": module_handle, "GetModuleHandleExW": module_handle_ex,
            "GetModuleFileNameW": module_file_name, "GetProcAddress": proc_address,
            "GetPrivateProfileIntW": profile, "VirtualAlloc": virtual_alloc, "VirtualFree": lambda emu: (1, 12),
        })

    # SDL (cdecl)
    def surface(self, name: str, w: int, h: int, pixels: bytes | None = None) -> int:
        """An ARGB8888 SDL_Surface in the emulator's memory (B, G, R, A bytes)."""
        e = self.e
        fmt = e.alloc(0x28)
        e.w32(fmt + 0x0C, 0x00FF0000)
        e.w32(fmt + 0x10, 0x0000FF00)
        e.w32(fmt + 0x14, 0x000000FF)
        e.w32(fmt + 0x18, 0xFF000000)
        e.write(fmt + 8, bytes((32, 4)))
        buf = self.big(w * h * 4)
        if pixels:
            e.write(buf, pixels)
        surf = e.alloc(0x40)
        for off, v in ((4, fmt), (8, w), (0xC, h), (0x10, w * 4), (0x14, buf)):
            e.w32(surf + off, v)
        self.surfaces[surf] = name
        return surf

    def _create_surface(self, emu):
        _flags, w, h, depth, r, g, b, a = (emu.arg(i) for i in range(8))
        assert depth == 32 and (r, g, b, a) == (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
        surf = self.surface(f"made@{len(self.made)}", w, h)
        self.made[surf] = (w, h)
        return surf, 0

    def _free_surface(self, emu):
        self.freed.append(emu.arg(0))
        return 0, 0

    def _revive_members(self, emu):
        out, most = emu.arg(0), emu.arg(1)
        for k, (slot, sex, head, body, name) in enumerate(self.revive_members[:most]):
            at = out + 48 * k
            emu.write(at, struct.pack("<iiii", slot, sex, head, body) + name.encode("latin-1")[:27].ljust(28, b"\0")
                      + bytes(4))
        return min(len(self.revive_members), most), 0

    def pixels(self, surf: int) -> tuple[int, int, bytes]:
        w, h, pitch = self.e.r32(surf + 8), self.e.r32(surf + 0xC), self.e.r32(surf + 0x10)
        assert pitch == w * 4
        return w, h, self.e.read(self.e.r32(surf + 0x14), w * h * 4)

    # ------------------------------------------------------------------ the game
    def _game(self):
        e = self.e
        # theGameState: its instance, a vtable whose MakeGameStatePath (+0Ch) names the test folder
        self.state = e.alloc(0x26400)
        e.w32(self.s("GAME_STATE_INSTANCE"), self.state)
        self.reserve_babies()
        vtable = e.alloc(0x40)
        stub = e.fake_code(b"\xC2\x04\x00")
        e.w32(vtable + S.LDW_PATH_VSLOT, stub)
        e.w32(self.state, vtable)
        self.path_buffer = e.alloc(0x200)

        def make_path(emu):
            emu.write(self.path_buffer, f"{SAVE_DIR}\\Virtual Families 2{emu.arg(0)}.ldw".encode("ascii") + b"\0")
            return self.path_buffer, 4
        self.seam(stub, make_path)
        # the stock Load and Save bodies: the save file is the scenario's
        self.saved: dict[int, bytes] = {}
        self.save_bytes = b"family save 1"

        def load(emu):
            return 1, 4

        def save(emu):
            slot = emu.arg(0)
            path = f"{SAVE_DIR}\\Virtual Families 2{slot}.ldw"
            back = f"{SAVE_DIR}\\Virtual Families 2{slot + 20}.ldw"
            if self.fs.read(path) is not None:
                self.fs.write(back, self.fs.read(path))
            self.fs.write(path, self.save_bytes)
            return 1, 4
        self.seam(self.s("GS_LOAD"), load)
        self.seam(self.s("GS_SAVE"), save)
        for slot in range(30):
            e.write(self.villager(slot) + S.VILLAGER_ACTIVE, b"\0")
        # the draws: the window (its clip rectangle), the graphics manager, the scene manager's camera
        self.window = e.alloc(0x40)
        self.impl = e.alloc(0x100)
        e.w32(self.window, self.impl)
        self.clip(0, 0, 8000, 8000)
        e.w32(self.a(CORE["WINDOW_GLOBAL"]), self.window)
        gm = e.alloc(0x10)
        e.w32(gm, e.alloc(0x10))
        e.w32(self.a(CORE["GRAPHICS_GLOBAL"]), gm)
        scene = self.a(CORE["SCENE_MANAGER"])
        e.w32(scene + 0x3004, 0)
        e.w32(scene + 0x3008, 0)
        e.w32(scene + 0x300C, f32(1.0))
        e.w32(scene + 0x3010, 100)
        for name, ret in (("LINK_NEXT8", 0x20), ("LINK_NEXT7", 0x1C), ("LINK_PREV", 0x18)):
            self.seam(self.a(CORE[name]), self._link(ret))
        self.seam(self.a(CORE["IS_ON_MAP"]), lambda emu: (0, 8))
        self.seam(self.a(CORE["GET_MATERIAL"]), lambda emu: (0, 8))
        self.seam(self.a(CORE["GET_RANDOM"]), lambda emu: (0, 0))
        self.grids: dict[int, int] = {}
        for image in GRID_SHAPES:
            self.grid(image)
        self.finish = e.fake_code(b"\x8B\xE5\x5D\xC2\x28\x00")       # mov esp, ebp; pop ebp; ret 28h
        self.e.uc.hook_add(UC_HOOK_CODE, self._blit_on, begin=self.s("BLIT") + 9, end=self.s("BLIT") + 9)
        self.conceptions: list = []
        self.renames: list = []

    def _link(self, ret: int):
        nargs = ret // 4

        def link(emu):
            out = emu.arg(0)
            emu.w32(out, 0)
            emu.w32(out + 4, 0)
            grid_out, int_out = emu.arg(nargs - 2), emu.arg(nargs - 1)
            if ret != 0x18 and grid_out:
                grid, cell = self.anim_queue.pop(0) if self.anim_queue else (0, 0)
                emu.w32(grid_out, grid)
                if int_out:
                    emu.w32(int_out, cell)
            return out, ret
        return link

    def clip(self, left, top, right, bottom):
        for k, v in enumerate((left, top, right, bottom)):
            self.e.w32(self.impl + 0x60 + 4 * k, v)

    def image_entry(self, image: int) -> int:
        va = self.s("IMAGE_TABLE")
        while va < self.s("IMAGE_TABLE_END"):
            if self.e.r32(va) == image:
                return va
            va += S.IMAGE_ENTRY_SIZE
        raise EmuError(f"no image {image}")

    def grid(self, image: int, *, file_override: str | None = None) -> int:
        """The game's grid of `image`, as GetImageGrid makes it (kept at the table entry's +2Ch), its files' pixels
        read from the real pictures."""
        if image in self.grids:
            return self.grids[image]
        e = self.e
        grid = e.alloc(0x40)
        if image in GRID_SHAPES:
            stem, cols, rows, across = GRID_SHAPES[image]
            names = [stem] if across == 1 else [f"{stem}{x}0.png" for x in range(across)]
            impls, sizes = [], []
            for name in names:
                w, h, px = png_pixels(self.fs.images / name)
                impl = e.alloc(8)
                e.w32(impl, self.surface(name, w, h, px))
                impls.append(impl)
                sizes.append((w, h))
            total_w = sum(s[0] for s in sizes)
            cw, ch = total_w // cols, sizes[0][1] // rows
            if across == 1:
                for off, v in ((4, impls[0]), (8, cols), (0xC, rows), (0x10, cw), (0x14, ch), (0x30, 0)):
                    e.w32(grid + off, v)
            else:
                tiles = e.alloc(4 * across)
                for k, impl in enumerate(impls):
                    e.w32(tiles + 4 * k, impl)
                for off, v in ((8, cols), (0xC, rows), (0x10, cw), (0x14, ch), (0x18, sizes[0][0]),
                               (0x1C, sizes[0][1]), (0x20, across), (0x24, 1), (0x28, sizes[0][0] // cw),
                               (0x2C, sizes[0][1] // ch), (0x30, tiles)):
                    e.w32(grid + off, v)
        else:                                  # a one-picture grid (the Holiday frames and portraits)
            entry = self.image_entry(image)
            rel = e.cstr(e.r32(entry + 4))
            w, h, px = png_pixels(self.fs.built / rel)
            impl = e.alloc(8)
            e.w32(impl, self.surface(rel, w, h, px))
            for off, v in ((4, impl), (8, 1), (0xC, 1), (0x10, w), (0x14, h), (0x30, 0)):
                e.w32(grid + off, v)
        e.w32(self.image_entry(image) + S.IMAGE_ENTRY_GRID, grid)
        self.grids[image] = grid
        return grid

    def holiday_ids(self) -> tuple[list[int], list[int]]:
        frames = [self.e.r32(self.s("HOL_FRAME_IDS") + 4 * k) for k in range(S.HOLIDAY_FRAMES)]
        details = [self.e.r32(self.s("HOL_DETAIL_IDS") + 4 * k) for k in range(S.HOLIDAY_DETAILS)]
        return frames, details

    def _blit_on(self, uc, address, size, user):
        e = self.e
        ebp = e.reg(UC_X86_REG_EBP)
        surf, x, y, left, top, right, bottom, alpha, scale = struct.unpack("<IiiiiiiII", e.read(ebp + 8, 36))
        self.blits.append({"surface": surf, "file": self.surfaces.get(surf, "?"), "rect": (left, top, right, bottom),
                           "x": x, "y": y, "alpha": struct.unpack("<f", struct.pack("<I", alpha))[0],
                           "scale": struct.unpack("<f", struct.pack("<I", scale))[0]})
        e.setreg(UC_X86_REG_EIP, self.finish)

    # ------------------------------------------------------------------ install, load, save
    def install(self) -> int:
        return self.e.call(self.e.dll_export("B200Skin_Startup"), limit=0)

    def vslot(self, off: int) -> int:
        return self.e.r32(self.s("GS_VTABLE") + off)

    def load(self, slot: int = 1) -> int:
        return self.e.call(self.vslot(S.GS_LOAD_VSLOT), (slot,), ecx=self.state) & 0xFF

    def save(self, slot: int = 1) -> int:
        return self.e.call(self.vslot(S.GS_SAVE_VSLOT), (slot,), ecx=self.state) & 0xFF

    def tones_path(self, slot: int) -> str:
        return f"{TONES_DIR}\\Virtual Families 2{slot}.ldw.dat"

    # ------------------------------------------------------------------ the family
    def manager(self) -> int:
        return self.s("VILLAGER_MANAGER")

    def villager(self, slot: int) -> int:
        return self.manager() + S.VILLAGER_ARRAY_OFFSET + slot * STRIDE

    def reserve_babies(self, *slots):
        slots = list(slots) + [-1] * (3 - len(slots))
        for k, v in enumerate(slots):
            self.e.w32(self.state + S.GAME_STATE_RESERVED_BABY + 4 * k, v)

    def set_villager(self, slot, name, gender, *, active=1, age=600, head=3, body=4, health=100):
        e = self.e
        v = self.villager(slot)
        e.write(v + S.VILLAGER_NAME, name.encode("latin-1")[:24].ljust(25, b"\0"))
        e.w32(v + S.VILLAGER_GENDER, gender)
        e.w32(v + S.VILLAGER_HEAD, head)
        e.w32(v + S.VILLAGER_BODY, body)
        e.w32(v + S.VILLAGER_AGE, age)
        e.w32(v + S.VILLAGER_HEALTH, health)
        e.write(v + S.VILLAGER_ACTIVE, bytes([active]))
        e.w32(v + S.VILLAGER_PREGNANT, 0)
        e.w32(v + S.VILLAGER_CARRIED, 0)
        e.w32(v + 0x1CBFC, self.window)          # the portraits' window

    def clear_villager(self, slot):
        self.e.write(self.villager(slot), bytes(STRIDE))

    def record(self, gen: int) -> int:
        return self.s("FAMILY_TREE") + gen * S.FAMILY_RECORD_SIZE - S.FAMILY_RECORD_BASE

    def peep(self, gen: int, place: int) -> int:
        rec = self.record(gen)
        if place == 0:
            return rec + S.RECORD_PARENT1
        if place == 1:
            return rec + S.RECORD_PARENT2
        return rec + S.RECORD_CHILDREN + (place - 2) * S.PEEP_RECORD_SIZE

    def set_generations(self, n: int):
        self.e.w32(self.s("FAMILY_TREE") + S.TREE_GENERATIONS_FIELD, n)

    def set_peep(self, gen, place, name, gender, head=3, body=4, slot=-1):
        e = self.e
        p = self.peep(gen, place)
        e.write(p, name.encode("latin-1")[:24].ljust(25, b"\0"))
        e.write(p + S.PEEP_VALID, b"\x01")
        e.w32(p + S.PEEP_GENDER, gender)
        e.w32(p + S.PEEP_HEAD, head)
        e.w32(p + S.PEEP_BODY, body)
        e.w32(p + S.PEEP_SLOT, slot)
        rec = self.record(gen)
        if place >= 2 and e.r32(rec + S.RECORD_CHILD_COUNT) < place - 1:
            e.w32(rec + S.RECORD_CHILD_COUNT, place - 1)

    # ------------------------------------------------------------------ the draws
    def _run_to(self, start: int, stop: int, regs: dict, args: list[int]):
        e = self.e
        esp = e.sp_top - 0x2000
        for v in reversed(args):
            esp -= 4
            e.w32(esp, v)
        e.setreg(UC_X86_REG_ESP, esp)
        for reg, v in regs.items():
            e.setreg(reg, v)
        try:
            e.uc.emu_start(start, stop, count=0)
        except UcError as exc:
            raise EmuError(f"emulation stopped at eip {e.reg(UC_X86_REG_EIP):#x}: {exc}") from exc
        if e.reg(UC_X86_REG_EIP) != stop:
            raise EmuError(f"ended at {e.reg(UC_X86_REG_EIP):#x}")

    def house(self, slot, *, body_grid=0x245, cell=0, frame=0, babies=0, turn=0) -> list[dict]:
        """CVillagerManager::DrawVillager(slot, 1.0), called at its entry as CSceneManager::EndScene calls it; the
        anim tables hand out the body grid (`body_grid`, or the person's Holiday frame `frame`) and `cell`."""
        e = self.e
        m = self.manager()
        v = self.villager(slot)
        base = m + slot * STRIDE
        if babies:
            e.w32(v + S.VILLAGER_PREGNANT, 1)
            e.w32(v + S.VILLAGER_CARRIED, babies)
        e.w32(m + 0x24, self.grid(0x1DE))
        e.w32(m + 0x18, self.grid(0x240))
        e.w32(m + 0x1C, self.grid(0x244))
        e.w32(m + 4, self.grid(0x1DE))           # a harmless picture for the shadow
        e.w32(base + 0x387E0, frame)
        e.w32(base + 0x3880C, INVALID)           # carrying nothing
        e.w32(base + 0x38808, 0)
        sex = e.r32(v + S.VILLAGER_GENDER)
        # DrawVillager asks the anim tables for the head's grid first (+16Fh), then the body's (+41Eh)
        self.anim_queue = [(self.grid(0x240 if sex == 1 else 0x244), turn), (self.grid(body_grid), cell)]
        self.blits = []
        e.call(self.s("DRAW_VILLAGER"), (slot, f32(1.0)), ecx=m)
        return list(self.blits)

    def detail(self, slot) -> list[dict]:
        """CVillager::DrawDetailVillager(point, false) on the household villager, as the Details scene calls it."""
        e = self.e
        v = self.villager(slot)
        sex = e.r32(v + S.VILLAGER_GENDER)
        self.anim_queue = [(self.grid(0x16), 1 if sex == 1 else 0), (self.grid(0x15), 0)]
        self.blits = []
        e.call(self.s("DETAIL"), (2000, 2000, 0), ecx=v)
        return list(self.blits)

    def event(self, slot) -> list[dict]:
        """CVillager::DrawEventVillager(x, y, 0, 1.0, false) as the event pop-up calls it."""
        e = self.e
        v = self.villager(slot)
        sex = e.r32(v + S.VILLAGER_GENDER)
        e.w32(self.manager() + 4, self.grid(0x1DE))
        self.anim_queue = [(self.grid(0x16), 1 if sex == 1 else 0), (self.grid(0x15), 0)] * 2
        self.blits = []
        e.call(self.s("EVENT"), (2000, 2000, 0, f32(1.0), 0), ecx=v)
        return list(self.blits)

    def tree(self, gen: int, place: int) -> list[dict]:
        """One Family Tree person, entered at DrawFamily's own call instruction (DrawParent of parent 1 / 2 with the
        record in ebx; DrawChild with the record at [ebp+10h] and the child's offset in edi), the arguments as
        DrawFamily pushes them."""
        e = self.e
        p = self.peep(gen, place)
        rec = self.record(gen)
        sex, head, body = (e.r32(p + o) for o in (S.PEEP_GENDER, S.PEEP_HEAD, S.PEEP_BODY))
        scene = e.alloc(0x100)
        for k, v in enumerate((0, 0, 8000, 8000)):
            e.w32(scene + 0xC + 4 * k, v)
        rect = e.alloc(16)
        for k, v in enumerate((0, 0, 8000, 8000)):
            e.w32(rect + 4 * k, v)
        args = [rect, 2000, 2000, sex, head, body, f32(1.0)]
        self.anim_queue = [(self.grid(0x244 if sex == 0 else 0x240), 0), (self.grid(0x245 if sex == 0 else 0x241), 0)] * 8
        self.blits = []
        if place < 2:
            site = self.s("RET_PARENT1" if place == 0 else "RET_PARENT2") - 5
            self._run_to(site, site + 5, {UC_X86_REG_ECX: scene, UC_X86_REG_ESI: scene, UC_X86_REG_EBX: rec}, args)
        else:
            site = self.s("RET_CHILD") - 5
            frame = e.alloc(0x100) + 0x80
            e.w32(frame + 0x10, rec)
            self._run_to(site, site + 5, {UC_X86_REG_ECX: scene, UC_X86_REG_ESI: scene, UC_X86_REG_EBP: frame,
                                          UC_X86_REG_EDI: (place - 2) * S.PEEP_RECORD_SIZE}, args)
        return list(self.blits)

    def revived(self, sex, head, body) -> list[dict]:
        """Revive's revived family member drawn by the executable with DrawParent from its own code (a return address
        that is none of DrawFamily's)."""
        e = self.e
        scene = e.alloc(0x100)
        for k, v in enumerate((0, 0, 8000, 8000)):
            e.w32(scene + 0xC + 4 * k, v)
        rect = e.alloc(16)
        for k, v in enumerate((0, 0, 8000, 8000)):
            e.w32(rect + 4 * k, v)
        self.anim_queue = [(self.grid(0x244 if sex == 0 else 0x240), 0), (self.grid(0x245 if sex == 0 else 0x241), 0)] * 8
        self.blits = []
        e.call(self.s("DRAW_PARENT"), (rect, 2000, 2000, sex, head, body, f32(1.0)), ecx=scene)
        return list(self.blits)

    # ------------------------------------------------------------------ conception and renames
    def conceive(self, mother_slot, father_slot, babies, via="CALL_CONCEIVE_MAIN") -> int:
        """The game's conception call (theMainScene's or the plans'), entered at its call instruction with the
        arguments the game pushes; Impregnate's body is a seam that makes the babies' records hidden in the reserved
        slots, as the game does."""
        e = self.e
        site = self.s(via)
        target = (site + 5 + e.r32(site + 1)) & 0xFFFFFFFF
        father = self.villager(father_slot)
        head, body = e.r32(father + S.VILLAGER_HEAD), e.r32(father + S.VILLAGER_BODY)

        def impregnate(emu):
            self.conceptions.append((emu.ecx, emu.arg(2), emu.arg(3)))
            for k, slot in enumerate(babies):
                self.set_villager(slot, f"Baby{k}", k % 2, active=0, age=0, head=1, body=2)
            self.reserve_babies(*babies)
            m = self.villager(mother_slot)
            emu.w32(m + S.VILLAGER_PREGNANT, 1)
            emu.w32(m + S.VILLAGER_CARRIED, len(babies))
            return 1, 0x14
        self.seam(self.s("IMPREGNATE"), impregnate)
        self._run_to(site, site + 5, {UC_X86_REG_ECX: self.villager(mother_slot)},
                     [1, self.e.alloc(8), head, body, 0])
        del target
        return e.reg(0x13) if False else 1

    def rename(self, slot, name, via="CALL_RENAME_MESSAGE"):
        """theVillagerScene's ChangeName call (the stock ChangeName is a seam that records), then the name copied
        into the villager as the scene does."""
        e = self.e
        text = e.alloc(32)
        e.write(text, name.encode("latin-1") + b"\0")

        def change(emu):
            self.renames.append((emu.arg(0), emu.cstr(emu.arg(1))))
            return 0, 8
        self.seam(self.s("FT_CHANGE_NAME"), change)
        site = self.s(via)
        self._run_to(site, site + 5, {UC_X86_REG_ECX: self.s("FAMILY_TREE")}, [self.villager(slot), text])
        e.write(self.villager(slot) + S.VILLAGER_NAME, name.encode("latin-1")[:24].ljust(25, b"\0"))

    # ------------------------------------------------------------------ the DLL's own answers
    def tone_of(self, slot) -> int:
        v = self.e.call(self.e.dll_export("B200Skin_ToneOf"), (slot,))
        return struct.unpack("<i", struct.pack("<I", v))[0]

    def tone_give(self, slot, tone, birth) -> int:
        return self.e.call(self.e.dll_export("B200Skin_ToneGive"), (slot, tone, birth))
