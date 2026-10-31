"""Run the game's own people-drawing code from the B200 desktop object files (unicorn), for the Picture Maker.

The object files (work/desktop_obj_files, or VF2_DESKTOP_OBJ_DIR; gitignored) keep their symbols. This loads the
sections of a few of them into one address space, links their relocations itself, and points every symbol none of
them defines at a Python seam (a function: recorded or answered, never real) or at zeroed memory (data). Then it
calls the game's functions:

* CAnimManager::LoadAssets reads the game's Assets\\anims.dat and Assets\\animpts.dat (fopen/fread are seams that
  read the real files) and builds the link tables; GetScaledLinkToNextPt / GetScaledLinkToPrevPt then answer
  for every frame, head direction, sex and row (src/vf2_people_links.json is made from these answers);
* CVillager::DrawDetailVillager, CVillager::DrawEventVillager, CVillagerManager::DrawVillager (with
  DrawCarriedItems) and CFamilyTreeScene::DrawPeep run whole; their draw calls are seams that record what
  would be drawn where;
* ldwGameWindowImpl::BlitRectWithAlpha (the blitter every scaled draw ends in) runs whole on real pixels.

Nothing here starts the game or writes a file.
"""
from __future__ import annotations

import faulthandler
import struct
from pathlib import Path

from unicorn import (UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_FETCH_UNMAPPED, UC_HOOK_MEM_READ_UNMAPPED,
                     UC_HOOK_MEM_WRITE_UNMAPPED, UC_MODE_32, Uc, UcError)
from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ECX,
                               UC_X86_REG_EIP, UC_X86_REG_ES, UC_X86_REG_ESP, UC_X86_REG_FS, UC_X86_REG_GDTR,
                               UC_X86_REG_GS, UC_X86_REG_SS)

faulthandler.disable()

CODE_BASE = 0x01000000
DATA_BASE = 0x08000000
HEAP_BASE = 0x20000000
HEAP_SIZE = 0x04000000
STACK_BASE = 0x30000000
STACK_SIZE = 0x00200000
THUNK_BASE = 0x40000000
THUNK_SIZE = 0x00100000
TEB_BASE = 0x41000000
GDT_BASE = 0x42000000
STOP = THUNK_BASE + THUNK_SIZE - 0x10        # a return address that ends a call

SKIP_SECTIONS = (".debug", ".drectve", ".chks64", ".llvm", ".gfids", ".giats", ".gljmp", ".voltbl", ".sxdata")


class EmuError(RuntimeError):
    pass


def _align(v: int, a: int = 0x10) -> int:
    return (v + a - 1) & ~(a - 1)


class CoffObject:
    def __init__(self, path: Path):
        self.path = Path(path)
        b = self.path.read_bytes()
        self.data = b
        machine, nsects, _ts, symptr, nsyms, opthdr, _ch = struct.unpack_from("<HHIIIHH", b, 0)
        if machine != 0x14C:
            raise EmuError(f"{path.name}: not an x86 object")
        strtab = symptr + nsyms * 18
        self.sections = []
        off = 20 + opthdr
        for i in range(nsects):
            raw = b[off:off + 8]
            if raw.startswith(b"/"):
                n = int(raw[1:].split(b"\0")[0])
                name = b[strtab + n:b.index(b"\0", strtab + n)].decode("latin-1")
            else:
                name = raw.split(b"\0")[0].decode("latin-1")
            vsize, vaddr, rsize, rptr, relptr, _lp, nrel, _nl, chars = struct.unpack_from("<IIIIIIHHI", b, off + 8)
            relocs = [struct.unpack_from("<IIH", b, relptr + 10 * k) for k in range(nrel)]
            self.sections.append({"name": name, "size": rsize, "ptr": rptr, "chars": chars, "relocs": relocs})
            off += 40
        self.symbols = {}            # index -> (name, value, section, storage class)
        k = 0
        while k < nsyms:
            at = symptr + 18 * k
            raw = b[at:at + 8]
            if raw[:4] == b"\0\0\0\0":
                n = struct.unpack_from("<I", raw, 4)[0]
                name = b[strtab + n:b.index(b"\0", strtab + n)].decode("latin-1")
            else:
                name = raw.split(b"\0")[0].decode("latin-1")
            value, sect, _typ, cls, naux = struct.unpack_from("<IhHBB", b, at + 8)
            self.symbols[k] = (name, value, sect, cls)
            k += 1 + naux


class Emu:
    """The objects' code and data in one address space; seams for everything they do not define."""

    def __init__(self, obj_dir: Path, names: list[str]):
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.objs = [CoffObject(Path(obj_dir) / f"{n}.obj") for n in names]
        self.globals: dict[str, int] = {}
        self.thunks: dict[int, str] = {}
        self.thunk_of: dict[str, int] = {}
        self.data_stubs: dict[str, int] = {}
        self.seams: dict[str, object] = {}
        self.calls: list = []
        self.heap = HEAP_BASE
        self.uc.mem_map(HEAP_BASE, HEAP_SIZE)
        self.uc.mem_map(STACK_BASE, STACK_SIZE)
        self.uc.mem_map(THUNK_BASE, THUNK_SIZE)
        self.uc.mem_map(TEB_BASE, 0x10000)
        self._link()
        self.uc.hook_add(UC_HOOK_CODE, self._thunk_hook, begin=THUNK_BASE, end=THUNK_BASE + THUNK_SIZE - 1)
        self.uc.hook_add(UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED | UC_HOOK_MEM_FETCH_UNMAPPED,
                         self._unmapped)
        # TLS for the thread-safe statics: fs:[2Ch] -> an array whose entry 0 is a zeroed block; the epoch
        # (offset 0, every SECREL is 0 here) is INT_MIN as the CRT starts it.
        tls_block = self.alloc(0x100)
        self.w32(tls_block, 0x80000000)
        tls_array = self.alloc(0x10)
        self.w32(tls_array, tls_block)
        self.w32(TEB_BASE + 0x2C, tls_array)
        self._set_fs(TEB_BASE)
        self.seam("__Init_thread_header", self._init_thread_header)
        self.seam("__Init_thread_footer", lambda e: (0, 0))
        self.seam("@__security_check_cookie@4", lambda e: (0, 0))
        self._unmapped_error = None

    def _set_fs(self, base: int) -> None:
        """Flat segments and FS -> the fake TEB through a small GDT (as tests/b200_time_emu.py does)."""
        gdt = GDT_BASE
        self.uc.mem_map(gdt, 0x1000)

        def entry(b, limit, access, flags):
            return ((limit & 0xFFFF) | ((b & 0xFFFFFF) << 16) | (access << 40) | (((limit >> 16) & 0xF) << 48)
                    | (flags << 52) | (((b >> 24) & 0xFF) << 56))
        self.uc.mem_write(gdt + 8, struct.pack("<Q", entry(0, 0xFFFFF, 0x9B, 0xC)))
        self.uc.mem_write(gdt + 16, struct.pack("<Q", entry(0, 0xFFFFF, 0x93, 0xC)))
        self.uc.mem_write(gdt + 24, struct.pack("<Q", entry(base, 0xFFF, 0x93, 0x4)))
        self.uc.reg_write(UC_X86_REG_GDTR, (0, gdt, 0xFF, 0))
        self.uc.reg_write(UC_X86_REG_CS, 0x08)
        for r in (UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_GS):
            self.uc.reg_write(r, 0x10)
        self.uc.reg_write(UC_X86_REG_FS, 0x18)

    # ------------------------------------------------------------------ memory
    def alloc(self, size: int, align: int = 0x10) -> int:
        at = _align(self.heap, align)
        self.heap = at + _align(max(1, size), 4)
        if self.heap > HEAP_BASE + HEAP_SIZE:
            raise EmuError("the heap is full")
        return at

    def r32(self, a: int) -> int:
        return struct.unpack("<I", bytes(self.uc.mem_read(a, 4)))[0]

    def s32(self, a: int) -> int:
        return struct.unpack("<i", bytes(self.uc.mem_read(a, 4)))[0]

    def w32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<I", v & 0xFFFFFFFF))

    def wf(self, a: int, v: float) -> None:
        self.uc.mem_write(a, struct.pack("<f", v))

    def rf(self, a: int) -> float:
        return struct.unpack("<f", bytes(self.uc.mem_read(a, 4)))[0]

    def read(self, a: int, n: int) -> bytes:
        return bytes(self.uc.mem_read(a, n))

    def write(self, a: int, data: bytes) -> None:
        self.uc.mem_write(a, bytes(data))

    def cstr(self, a: int) -> str:
        out = bytearray()
        while True:
            c = self.uc.mem_read(a + len(out), 1)[0]
            if not c:
                return out.decode("latin-1")
            out.append(c)

    def string(self, text: str) -> int:
        raw = text.encode("latin-1") + b"\0"
        at = self.alloc(len(raw))
        self.write(at, raw)
        return at

    # ------------------------------------------------------------------ linking
    def _link(self) -> None:
        code_at, data_at = CODE_BASE, DATA_BASE
        placed = []                          # (obj, section index, address)
        comdat_seen: set[str] = set()
        for obj in self.objs:
            obj.addr = {}
            # COMDAT sections whose defining symbol another object already gave are left out (first wins)
            defines = {}
            for name, value, sect, cls in obj.symbols.values():
                if sect > 0 and cls == 2:
                    defines.setdefault(sect, []).append(name)
            for i, s in enumerate(obj.sections, 1):
                if s["name"].startswith(SKIP_SECTIONS) or s["chars"] & 0x800 or s["chars"] & 0x200:
                    continue
                names = defines.get(i, [])
                if s["chars"] & 0x1000 and names and all(n in comdat_seen for n in names):
                    continue
                for n in names:
                    if s["chars"] & 0x1000:
                        comdat_seen.add(n)
                if s["chars"] & 0x20:
                    obj.addr[i] = code_at
                    code_at = _align(code_at + max(1, s["size"]))
                else:
                    obj.addr[i] = data_at
                    data_at = _align(data_at + max(1, s["size"]))
                placed.append((obj, i, obj.addr[i]))
        self.uc.mem_map(CODE_BASE, _align(code_at - CODE_BASE + 0x1000, 0x1000))
        self.uc.mem_map(DATA_BASE, _align(data_at - DATA_BASE + 0x1000, 0x1000))
        for obj, i, at in placed:
            s = obj.sections[i - 1]
            if not s["chars"] & 0x80 and s["size"]:
                self.uc.mem_write(at, obj.data[s["ptr"]:s["ptr"] + s["size"]])
        for obj in self.objs:
            for name, value, sect, cls in obj.symbols.values():
                if sect > 0 and cls == 2 and sect in obj.addr and name not in self.globals:
                    self.globals[name] = obj.addr[sect] + value
        for obj, i, at in placed:
            s = obj.sections[i - 1]
            for vaddr, symidx, typ in s["relocs"]:
                name, value, sect, cls = obj.symbols[symidx]
                if sect > 0 and sect in obj.addr:
                    target = obj.addr[sect] + value
                elif sect > 0:                   # a COMDAT left out: the copy another object gave
                    target = self.globals.get(name)
                    if target is None:
                        target = self._external(name, typ)
                elif sect == -1:
                    target = value
                else:
                    target = self.globals.get(name)
                    if target is None:
                        target = self._external(name, typ)
                site = at + vaddr
                if typ == 0x06:              # DIR32
                    self.w32(site, self.r32(site) + target)
                elif typ == 0x14:            # REL32
                    self.w32(site, self.r32(site) + target - (site + 4))
                elif typ == 0x07:            # DIR32NB
                    self.w32(site, self.r32(site) + target)
                elif typ in (0x0A, 0x0B):    # SECTION / SECREL: TLS offsets; every TLS variable is at 0 here
                    self.w32(site, self.r32(site))
                else:
                    raise EmuError(f"relocation type {typ:#x} at {name}")

    def _external(self, name: str, typ: int) -> int:
        if name == "__tls_array":
            return 0x2C
        if typ == 0x14 or name.startswith(("?", "_", "@")) and self._looks_like_function(name):
            if name not in self.thunk_of:
                at = THUNK_BASE + 0x10 * (len(self.thunk_of) + 1)
                self.thunk_of[name] = at
                self.thunks[at] = name
                self.uc.mem_write(at, b"\xC3")
            return self.thunk_of[name]
        if name not in self.data_stubs:
            self.data_stubs[name] = self.alloc(0x10000)
        return self.data_stubs[name]

    @staticmethod
    def _looks_like_function(name: str) -> bool:
        if name.startswith("?"):
            # a decorated data name has "@@3" (global) or "@@2"/"@@0"/"@@1" (static member) before its type
            return not any(tag in name for tag in ("@@3", "@@2", "@@0", "@@1", "@4", "@@6B"))
        return name.startswith("@") or name in ("_fopen", "_fread", "_fclose", "_sprintf", "_SDL_UpperBlit",
                                                "_SDL_LockSurface", "_SDL_UnlockSurface", "__Init_thread_header",
                                                "__Init_thread_footer")

    def addr(self, name: str) -> int:
        if name in self.globals:
            return self.globals[name]
        if name in self.data_stubs:
            return self.data_stubs[name]
        raise KeyError(name)

    def seam(self, name: str, fn) -> None:
        """fn(emu) -> (eax, bytes the callee pops) or None for (0, 0)."""
        self.seams[name] = fn
        if name not in self.thunk_of and name not in self.globals:
            self._external(name, 0x14)
        elif name in self.globals and name not in self.thunk_of:
            # a function one of the objects defines: its first bytes jump to a thunk of its own
            at = THUNK_BASE + 0x10 * (len(self.thunk_of) + 1)
            self.thunk_of[name] = at
            self.thunks[at] = name
            self.uc.mem_write(at, b"\xC3")
            entry = self.globals[name]
            self.uc.mem_write(entry, b"\xE9" + struct.pack("<i", at - (entry + 5)))

    def _init_thread_header(self, e):
        guard = e.arg(0)
        e.w32(guard, 0xFFFFFFFF)
        return 0, 0

    # ------------------------------------------------------------------ calls
    def arg(self, k: int) -> int:
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        return self.r32(esp + 4 + 4 * k)

    def sarg(self, k: int) -> int:
        v = self.arg(k)
        return v - (1 << 32) if v & 0x80000000 else v

    def farg(self, k: int) -> float:
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        return self.rf(esp + 4 + 4 * k)

    @property
    def ecx(self) -> int:
        return self.uc.reg_read(UC_X86_REG_ECX)

    def _thunk_hook(self, uc, address, size, _user):
        if address == STOP:
            uc.emu_stop()
            return
        name = self.thunks.get(address)
        if name is None:
            return
        fn = self.seams.get(name)
        if fn is None:
            self._unmapped_error = f"the game called {name}, which has no seam"
            uc.emu_stop()
            return
        result = fn(self)
        eax, pop = (0, 0) if result is None else result
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = self.r32(esp)
        uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        uc.reg_write(UC_X86_REG_EIP, ret)

    def _unmapped(self, uc, access, address, size, value, _user):
        eip = uc.reg_read(UC_X86_REG_EIP)
        self._unmapped_error = f"unmapped access {address:#x} at eip {eip:#x}"
        return False

    def call(self, name_or_addr, args=(), ecx: int = 0, floats: dict | None = None) -> int:
        """Call a function (thiscall when ecx is given) with 32-bit arguments; returns eax."""
        target = self.addr(name_or_addr) if isinstance(name_or_addr, str) else name_or_addr
        esp = STACK_BASE + STACK_SIZE - 0x1000
        raw = bytearray()
        for k, a in enumerate(args):
            if isinstance(a, float):
                raw += struct.pack("<f", a)
            else:
                raw += struct.pack("<I", a & 0xFFFFFFFF)
        esp -= len(raw) + 4
        self.write(esp, struct.pack("<I", STOP) + raw)
        self.uc.mem_write(STOP, b"\xC3")
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.reg_write(UC_X86_REG_EBP, 0)
        self.uc.reg_write(UC_X86_REG_ECX, ecx)
        self._unmapped_error = None
        try:
            self.uc.emu_start(target, STOP, count=50_000_000)
        except UcError as exc:
            raise EmuError(f"{name_or_addr}: {exc} ({self._unmapped_error})") from None
        if self._unmapped_error:
            raise EmuError(f"{name_or_addr}: {self._unmapped_error}")
        return self.uc.reg_read(UC_X86_REG_EAX)


# ====================================================================== the people rig
# The images the people-drawing code asks theGraphicsManager for (data/vf2/image-descriptors.json: id, the
# file or prefix, columns, rows, files across, files down).
PEOPLE_IMAGES = {
    21: ("bigheads", 12, 50, 2, 1),
    22: ("highrez_bodies_final2.png", 2, 50, 1, 1),
    478: ("carrying.png", 13, 7, 1, 1),
    576: ("female_heads", 24, 50, 2, 1),
    577: ("female_bodies00.png", 32, 50, 1, 1),
    578: ("female_actions00.png", 15, 50, 1, 1),
    579: ("female_sit00.png", 9, 50, 1, 1),
    580: ("male_heads", 24, 50, 2, 1),
    581: ("male_bodies00.png", 32, 50, 1, 1),
    582: ("male_actions00.png", 15, 50, 1, 1),
    583: ("male_sit00.png", 9, 50, 1, 1),
}


def png_size(path: Path) -> tuple[int, int]:
    head = Path(path).read_bytes()[:24]
    return struct.unpack(">II", head[16:24])


class PeopleRig:
    """The objects that draw people, linked; theGraphicsManager, ldwGameState and the C file functions are seams
    over the game folder `game` (its Images and Assets)."""

    OBJECTS = ["AnimManager", "ldwImage", "Villager", "VillagerManager", "FamilyTreeScene", "ldwGameWindow",
               "InventoryManager"]

    def __init__(self, obj_dir: Path, game: Path):
        self.game = Path(game)
        self.e = e = Emu(obj_dir, self.OBJECTS)
        self.grids: dict[int, int] = {}
        self.grid_ids: dict[int, int] = {}
        self.files: dict[int, object] = {}
        self.draws: list = []
        self.random: list[int] = []
        self.image_names: dict[int, str] = {}
        for image_id in PEOPLE_IMAGES:
            self._make_grid(image_id)
        self.shadow = e.alloc(0x20)
        self.image_names[self.shadow] = "Images/peep_shadow1.png"
        self.window = e.alloc(0x100)
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (self.window, 0))
        self.gm = e.alloc(0x100)
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (self.gm, 0))
        e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z",
               lambda em: (self.grids.get(em.arg(0), 0), 4))
        # ldwGameState::Get()->vtable[2](name): the full path of a file in the game's Assets folder
        self.state = e.alloc(0x20)
        vtable = e.alloc(0x20)
        e.w32(self.state, vtable)
        e.seam("gs_full_path", self._full_path)
        e.w32(vtable + 8, e.thunk_of["gs_full_path"])
        e.seam("?Get@ldwGameState@@SAPAV1@XZ", lambda em: (self.state, 0))
        e.seam("?GetRandom@ldwGameState@@SAHH@Z", self._get_random)
        e.seam("_fopen", self._fopen)
        e.seam("_fread", self._fread)
        e.seam("_fclose", self._fclose)
        e.seam("?ldwStrCopy@@YAXPADPBDH@Z", self._str_copy)
        self.anim = e.addr("?AnimManager@@3VCAnimManager@@A")
        self.loaded = False

    # ---- CAnimManager
    def load_assets(self) -> None:
        if not self.loaded:
            self.e.call("??0CAnimManager@@QAE@XZ", ecx=self.anim)
            self.e.call("?LoadAssets@CAnimManager@@QAEXXZ", ecx=self.anim)
            self.loaded = True

    def _points(self, at: int) -> list:
        return [[self.e.s32(at + 8 * r), self.e.s32(at + 8 * r + 4)] for r in range(50)]

    def link_tables(self) -> dict:
        """The link tables LoadAssets built, read from CAnimManager as GetScaledLinkTo{Next,Prev}Pt index them
        (body: frame * CA4h + (part + 2 * sex) * 328h; head: (15 * sex + direction) * 328h; each block: the
        image, the cell, 50 previous points, 50 next points). Only part 0 is ever drawn."""
        self.load_assets()
        e, a = self.e, self.anim
        body, head = {}, {}
        for frame in range(57):
            for sex in (0, 1):
                block = a + frame * 0xCA4 + (2 * sex) * 0x328
                body[f"{frame}/{sex}"] = {"image": e.s32(block + 0x76F4), "cell": e.s32(block + 0x76F8),
                                          "prev": self._points(block + 0x76FC), "next": self._points(block + 0x788C)}
        for direction in range(15):
            for sex in (0, 1):
                block = a + (15 * sex + direction) * 0x328
                head[f"{direction}/{sex}"] = {"image": e.s32(block + 0x34774), "cell": e.s32(block + 0x34778),
                                              "prev": self._points(block + 0x3477C),
                                              "next": self._points(block + 0x3490C)}
        facing = {}
        for frame in range(57):
            value = e.call("?GetDirection@CAnimManager@@QAE?AW4EDirection@@W4EAnimFrame@@@Z", [frame], ecx=a)
            facing[str(frame)] = value - (1 << 32) if value & 0x80000000 else value
        return {"body": body, "head": head, "facing": facing}

    def scaled_link(self, which: str, key: int, sex: int, row: int, scale: float) -> tuple:
        """The game's own GetScaledLinkTo{Next,Prev}Pt answer (which: body_next, body_prev, head_next, head_prev)."""
        self.load_assets()
        e = self.e
        out, grid, cell = self.block("out", 8), self.block("grid_out", 4), self.block("cell_out", 4)
        names = {
            "body_next": ("?GetScaledLinkToNextPt@CAnimManager@@QAE?AUldwPoint@@W4EAnimFrame@@W4EAnimPart@@"
                          "W4EAnimGender@@HMPAPAVldwImageGrid@@PAH@Z", [out, key, 0, sex, row, scale, grid, cell]),
            "body_prev": ("?GetScaledLinkToPrevPt@CAnimManager@@QAE?AUldwPoint@@W4EAnimFrame@@W4EAnimPart@@"
                          "W4EAnimGender@@HM@Z", [out, key, 0, sex, row, scale]),
            "head_next": ("?GetScaledLinkToNextPt@CAnimManager@@QAE?AUldwPoint@@W4EHeadDirection@@W4EAnimGender@@"
                          "HMPAPAVldwImageGrid@@PAH@Z", [out, key, sex, row, scale, grid, cell]),
            "head_prev": ("?GetScaledLinkToPrevPt@CAnimManager@@QAE?AUldwPoint@@W4EHeadDirection@@W4EAnimGender@@HM@Z",
                          [out, key, sex, row, scale]),
        }
        name, args = names[which]
        e.call(name, args, ecx=self.anim)
        return e.s32(out), e.s32(out + 4)

    # ---- drawing: the draws are recorded
    def record_draws(self) -> None:
        e = self.e

        def grid_draw(kind, nargs, fields):
            def seam(em):
                values = [em.arg(k) for k in range(nargs)]
                self.draws.append((kind, *fields(em, values)))
                return 0, 4 * nargs
            return seam

        def s(v):
            return v - (1 << 32) if v & 0x80000000 else v

        def f(v):
            return struct.unpack("<f", struct.pack("<I", v))[0]

        # ldwGameWindow::DrawScaled(grid, x, y, row, col, percent, mirror)
        e.seam("?DrawScaled@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHHH_N@Z", grid_draw(
            "window", 7, lambda em, a: (self.grid_ids.get(a[0], a[0]), s(a[1]), s(a[2]), s(a[3]), s(a[4]),
                                        s(a[5]), a[6] & 0xFF)))
        # ldwGameWindow::DrawScaled(grid, x, y, row, col, alpha, percent, mirror)
        e.seam("?DrawScaled@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHHMH_N@Z", grid_draw(
            "window_alpha", 8, lambda em, a: (self.grid_ids.get(a[0], a[0]), s(a[1]), s(a[2]), s(a[3]), s(a[4]),
                                              round(f(a[5]), 6), s(a[6]), a[7] & 0xFF)))
        # ldwGameWindow::DrawScaled(image, x, y, percent, center, mirror)
        e.seam("?DrawScaled@ldwGameWindow@@QAEXPAVldwImage@@HHH_N1@Z", grid_draw(
            "window_image", 6, lambda em, a: (self.image_names.get(a[0], a[0]), s(a[1]), s(a[2]), s(a[3]),
                                              a[4] & 0xFF, a[5] & 0xFF)))
        # CSceneManager::DrawScaled(grid, point, row, col, scale, alpha)
        e.seam("?DrawScaled@CSceneManager@@QBEXPAVldwImageGrid@@UldwPoint@@HHMM@Z", grid_draw(
            "scene", 7, lambda em, a: (self.grid_ids.get(a[0], a[0]), s(a[1]), s(a[2]), s(a[3]), s(a[4]),
                                       round(f(a[5]), 6), round(f(a[6]), 6))))
        # CSceneManager::Draw(grid, point, cell, alpha)
        e.seam("?Draw@CSceneManager@@QBEXPAVldwImageGrid@@UldwPoint@@HM@Z", grid_draw(
            "scene_cell", 5, lambda em, a: (self.grid_ids.get(a[0], a[0]), s(a[1]), s(a[2]), s(a[3]),
                                            round(f(a[4]), 6))))
        # CSceneManager::DrawScaled(image, point, scale, alpha, mirror)
        e.seam("?DrawScaled@CSceneManager@@QBEXPAVldwImage@@UldwPoint@@MM_N@Z", grid_draw(
            "scene_image", 6, lambda em, a: (self.image_names.get(a[0], a[0]), s(a[1]), s(a[2]),
                                             round(f(a[3]), 6), round(f(a[4]), 6), a[5] & 0xFF)))
        # CSceneManager::Draw(image, point, alpha)
        e.seam("?Draw@CSceneManager@@QBEXPAVldwImage@@UldwPoint@@M@Z", grid_draw(
            "scene_plain", 4, lambda em, a: (self.image_names.get(a[0], a[0]), s(a[1]), s(a[2]),
                                             round(f(a[3]), 6))))
        # ldwGameWindow::DrawScaled(grid, x, y, cell, percent, centre) (CInventoryManager::DrawItem)
        e.seam("?DrawScaled@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHH_N@Z", grid_draw(
            "window_cell", 6, lambda em, a: (self.grid_ids.get(a[0], a[0]), s(a[1]), s(a[2]), s(a[3]), s(a[4]),
                                             a[5] & 0xFF)))
        e.seam("?IsOnMap@CWorldMap@@QBE?B_NUldwPoint@@@Z", lambda em: (0, 8))
        scene = e.addr("?SceneManager@@3VCSceneManager@@A")
        e.wf(scene + 0x300C, 1.0)                       # the house at 100% zoom
        e.w32(scene + 0x3010, 100)

    # ---- the draws, run
    VILLAGER_SIZE = 0x1CC0C
    _blocks: dict = {}

    def block(self, key: str, size: int) -> int:
        """A zeroed block of `size`, the same one each time for `key` (the heap is not freed)."""
        at = self._blocks.get((id(self), key))
        if at is None:
            at = self.e.alloc(size)
            self._blocks[(id(self), key)] = at
        self.e.write(at, bytes(size))
        return at

    def _villager(self, at: int, sex: int, head: int, body: int, age: int, babies: int = 0) -> None:
        e = self.e
        e.w32(at + 0x6A54, age)
        e.w32(at + 0x6A58, sex)
        e.w32(at + 0x6A80, head)
        e.w32(at + 0x6A84, body)
        e.w32(at + 0x6B18, 1 if babies else 0)          # CVillagerState+24h: expecting
        e.w32(at + 0x6B1C, babies)                      # CVillagerState+28h: how many
        e.w32(at + 0x1CBFC, self.window)

    def detail(self, sex, head, body, age, turn, at=(0, 0)) -> list:
        """CVillager::DrawDetailVillager(at, false), the head turn rolled as `turn`."""
        e = self.e
        self.record_draws()
        villager = self.block("villager", self.VILLAGER_SIZE)
        self._villager(villager, sex, head, body, age)
        self.random = [0, turn]                         # GetRandom(1000) <= 20: a new turn, GetRandom(3)
        self.draws = []
        e.call("?DrawDetailVillager@CVillager@@QAEXUldwPoint@@_N@Z", [at[0], at[1], 0], ecx=villager)
        return self.draws

    def event(self, sex, head, body, age, facing_you, scale=1.0, at=(0, 0)) -> list:
        """CVillager::DrawEventVillager(at, 0, scale, facing_you)."""
        e = self.e
        self.record_draws()
        villager = self.block("villager", self.VILLAGER_SIZE)
        self._villager(villager, sex, head, body, age)
        manager = e.addr("?VillagerManager@@3VCVillagerManager@@A")
        e.w32(manager + 4, self.shadow)
        self.draws = []
        e.call("?DrawEventVillager@CVillager@@QAEXHHW4EBodyPosition@@M_N@Z",
               [at[0], at[1], 0, float(scale), 1 if facing_you else 0], ecx=villager)
        return self.draws

    def house(self, sex, head, body, age, frame, turn, direction=0, babies=0, at=(0, 0)) -> list:
        """CVillagerManager::DrawVillager(0, 1.0) for a villager at place `at` in body frame `frame`, head turn
        `turn`, facing `direction`, not lifted, not fading, on no water."""
        e = self.e
        self.record_draws()
        manager = self.block("manager", 0x40000)
        villager = manager + 0x1CC70
        self._villager(villager, sex, head, body, age, babies)
        e.w32(manager + 4, self.shadow)
        e.w32(manager + 0x20, self.block("image", 0x20))
        e.w32(manager + 0x24, self.grids[478])
        e.w32(manager + 0x28, self.block("grid", 0x40))
        e.w32(manager + 0x387C4, at[0])                 # CVillager+1BB54, +1BB58: its place
        e.w32(manager + 0x387C8, at[1])
        e.w32(manager + 0x387E0, frame)
        e.w32(manager + 0x387E8, 0)
        e.w32(manager + 0x38800, direction)
        e.w32(manager + 0x38804, turn)
        e.w32(manager + 0x38808, 0)                     # CVillager+1BB98: what it is doing (not sitting)
        e.w32(manager + 0x3880C, 0xFFFFFFFF)            # CVillager+1BB9C: nothing carried
        self.draws = []
        e.call("?DrawVillager@CVillagerManager@@QAEXHM@Z", [0, 1.0], ecx=manager)
        return self.draws

    def peep(self, sex, head, body, at=(0, 0), scale=1.0) -> list:
        """CFamilyTreeScene::DrawPeep(at, sex, head, body, scale, false)."""
        e = self.e
        self.record_draws()
        scene = self.block("tree", 0x400)
        self.draws = []
        e.call("?DrawPeep@CFamilyTreeScene@@AAEXUldwPoint@@HHHM_N@Z", [at[0], at[1], sex, head, body, float(scale), 0],
               ecx=scene)
        return self.draws

    def tray_item(self, sex, picture, at=(0, 0)) -> list:
        """CInventoryManager::DrawItem(at, Male / Female Outfit, 0, 0, false) with the outfit's picture."""
        e = self.e
        self.record_draws()
        inventory = self.block("inventory", 0x600)
        e.w32(inventory + (0x468 if sex == 0 else 0x46C), picture)
        self.draws = []
        e.call("?DrawItem@CInventoryManager@@QAEXUldwPoint@@W4EInventoryItem@@W4EInventoryItemState@@"
               "W4EInventoryItemPosition@@_N@Z", [at[0], at[1], 0x49 if sex == 0 else 0x4A, 0, 0, 0], ecx=inventory)
        return self.draws

    def blit(self, pixels: bytes, width: int, height: int, rect: tuple, x: int, y: int, percent: int,
             screen: tuple, background: tuple = (40, 90, 160)) -> bytes:
        """ldwGameWindowImpl::BlitRectWithAlpha(source, x, y, rect, 1.0, percent / 100, false) onto an opaque
        screen of `screen` (w, h) filled with `background`; the source and the result are R, G, B, A bytes
        (the surfaces hold them as B, G, R, A: ARGB8888)."""
        e = self.e
        e.seam("_SDL_LockSurface", lambda em: (0, 0))
        e.seam("_SDL_UnlockSurface", lambda em: (0, 0))

        def bgra(raw: bytes) -> bytes:
            out = bytearray(raw)
            out[0::4], out[2::4] = raw[2::4], raw[0::4]
            return bytes(out)

        def surface(w, h, data, alpha_mask):
            fmt = e.alloc(0x28)
            e.w32(fmt + 0x0C, 0x00FF0000)
            e.w32(fmt + 0x10, 0x0000FF00)
            e.w32(fmt + 0x14, 0x000000FF)
            e.w32(fmt + 0x18, alpha_mask)
            e.write(fmt + 0x20, bytes((16, 8, 0, 24)))
            e.write(fmt + 8, bytes((32, 4)))
            buf = e.alloc(len(data))
            e.write(buf, data)
            surf = e.alloc(0x40)
            for off, v in ((4, fmt), (8, w), (0xC, h), (0x10, w * 4), (0x14, buf)):
                e.w32(surf + off, v)
            return surf, buf

        src, _ = surface(width, height, bgra(pixels), 0xFF000000)
        sw, sh = screen
        fill = bytes(background) + b"\xff"
        dst, dst_buf = surface(sw, sh, bgra(fill * (sw * sh)), 0)
        impl = e.alloc(0x40)
        e.w32(impl + 8, sw)                             # the window's clip size
        e.w32(impl + 0xC, sh)
        e.w32(impl + 0x30, dst)
        scale = struct.unpack("<f", struct.pack("<f", percent / 100.0))[0]
        left, top, right, bottom = rect
        e.call("?BlitRectWithAlpha@ldwGameWindowImpl@@AAEXPAUSDL_Surface@@HHHHHHMM_N@Z",
               [src, x, y, left, top, right, bottom, 1.0, scale, 0], ecx=impl)
        return bgra(e.read(dst_buf, sw * sh * 4))

    # ---- seams
    def _make_grid(self, image_id: int) -> None:
        e = self.e
        name, cols, rows, across, down = PEOPLE_IMAGES[image_id]
        grid = e.alloc(0x40)
        if across * down == 1:
            w, h = png_size(self.game / "Images" / name)
            for off, v in ((8, cols), (0xC, rows), (0x10, w // cols), (0x14, h // rows), (0x30, 0)):
                e.w32(grid + off, v)
            e.w32(grid + 4, e.alloc(8))
        else:
            images = e.alloc(4 * across * down)
            sizes = {}
            for y in range(down):
                for x in range(across):
                    path = self.game / "Images" / f"{name}{x}{y}.png"
                    sizes[(x, y)] = png_size(path)
                    impl = e.alloc(8)
                    e.w32(impl, x)
                    e.w32(impl + 4, y)
                    e.w32(images + 4 * (y * across + x), impl)
            total_w = sum(sizes[(x, 0)][0] for x in range(across))
            total_h = sum(sizes[(0, y)][1] for y in range(down))
            first_w, first_h = sizes[(0, 0)]
            cw, ch = total_w // cols, total_h // rows
            for off, v in ((8, cols), (0xC, rows), (0x10, cw), (0x14, ch), (0x18, first_w), (0x1C, first_h),
                           (0x20, across), (0x24, down), (0x28, first_w // cw), (0x2C, first_h // ch),
                           (0x30, images)):
                e.w32(grid + off, v)
        self.grids[image_id] = grid
        self.grid_ids[grid] = image_id

    def _full_path(self, em):
        name = em.cstr(em.arg(0))
        return em.string(str(self.game / "Assets" / name)), 4

    def _get_random(self, em):
        n = em.sarg(0)
        value = self.random.pop(0) if self.random else 0
        return max(0, min(n - 1, value)) if n > 0 else 0, 0

    def _fopen(self, em):
        path = Path(em.cstr(em.arg(0)))
        if not path.is_file():
            return 0, 0
        handle = em.alloc(4)
        self.files[handle] = open(path, "rb")
        return handle, 0

    def _fread(self, em):
        buf, size, count, handle = em.arg(0), em.arg(1), em.arg(2), em.arg(3)
        data = self.files[handle].read(size * count)
        em.write(buf, data)
        return len(data) // size if size else 0, 0

    def _str_copy(self, em):
        dst, src, n = em.arg(0), em.arg(1), em.sarg(2)
        text = em.cstr(src).encode("latin-1")[:max(0, n - 1)] if src else b""
        em.write(dst, text + bytes(1))
        return 0, 0

    def _fclose(self, em):
        f = self.files.pop(em.arg(0), None)
        if f:
            f.close()
        return 0, 0
