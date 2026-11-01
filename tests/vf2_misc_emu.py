"""Run the game's own effect, furniture, animal and pet drawing code from the B200 desktop objects (unicorn), for
the Picture Maker's effects, animals, furniture and food pictures (src/vf2_art_misc.py).

The objects (work/desktop_obj_files, or VF2_DESKTOP_OBJ_DIR; gitignored) are linked by tests/vf2_people_emu.Emu;
everything they do not define is a seam. theGraphicsManager hands out fake picture grids (one per image id) whose
columns, rows and sizes are the real files' (vf2_game_pictures' image table); every draw call is recorded with the
image id, the place, the cell, the scale and the alpha the code asked for.

* CFloatingAnim (MiscRig.effect): LoadAssets, AddAnim, then Draw(index) for a frame and Update seven times (the
  effect clock moves on every 7th call) until the effect ends, all whole.
* CFurnitureManager (MiscRig.furniture): Draw(index) of one placed item, and SetOnState(id, true, delay) which adds
  the item's animation through the real CFloatingAnim::AddAnim; then the animation's frames as above.
* AnimalRig: CPetAnimManager::LoadAssets over the game's Assets\\petanimpts.dat and CPetManager::DrawPet (with the
  real CPet), CBird::Draw, CBall::Draw (with the real CInventoryManager::ImageIndex).
* blit: ldwGameWindowImpl::BlitRectWithAlpha run whole with an opacity and a scale.
* Reachability (CallGraph.reachable): every function's and data symbol's relocations over all 164 objects, walked from
  _WinMain@16 and every static initializer the C runtime runs (`$initializer$`); a function outside the walk can
  never run.

Nothing here starts the game or writes a file.
"""
from __future__ import annotations

import struct
from collections import defaultdict
from pathlib import Path

import vf2_people_emu as pe

ANIM_SLOTS = 0x200          # CFloatingAnim: 512 instances of 0x44 bytes from this + 4
ANIM_SIZE = 0x44
ANIM_TYPES = 64             # m_sAnim: 64 entries of 16 bytes (image, frames, random first frame)


def _s(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


def _f(v: int) -> float:
    return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]


class Grids:
    """Fake ldwImageGrid objects, one per image id, answering for the real files (via vf2_game_pictures)."""

    def __init__(self, e: pe.Emu, files):
        import vf2_game_pictures as gp
        self.gp, self.e, self.files = gp, e, files
        self.by_id: dict[int, int] = {}
        self.ids: dict[int, int] = {}

    def grid(self, image: int) -> int:
        if image not in self.by_id:
            at = self.e.alloc(0x40)
            self.by_id[image] = at
            self.ids[at] = image
        return self.by_id[image]

    def shape(self, at: int) -> tuple:
        entry = self.gp.entry_by_id(self.ids[at])
        cells = self.gp.entry_cells(self.files, entry)
        name, rect = cells[0]
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        cols = entry.cols or 1
        rows = max(1, entry.rows)
        return cols, rows, w * cols, h * rows

    def install(self) -> None:
        e = self.e
        e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z",
               lambda em: (self.grid(em.arg(0)), 4))
        e.seam("?GetImage@theGraphicsManager@@QAEPAVldwImage@@W4EImage@@@Z", lambda em: (self.grid(em.arg(0)), 4))
        e.seam("?GetColumnCount@ldwImageGrid@@QAEHXZ", lambda em: (self.shape(em.ecx)[0], 0))
        e.seam("?GetRowCount@ldwImageGrid@@QAEHXZ", lambda em: (self.shape(em.ecx)[1], 0))
        e.seam("?GetWidth@ldwImage@@QAEHXZ", lambda em: (self.shape(em.ecx)[2], 0))
        e.seam("?GetHeight@ldwImage@@QAEHXZ", lambda em: (self.shape(em.ecx)[3], 0))
        e.seam("?GetCellCount@ldwImageGrid@@QAEHXZ", lambda em: (self.shape(em.ecx)[0] * self.shape(em.ecx)[1], 0))


class MiscRig:
    OBJECTS = ["FloatingAnim", "FurnitureManager"]

    def __init__(self, obj_dir: Path, game: Path):
        import vf2_game_pictures as gp
        self.files = gp.GameFiles(game)
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.draws: list = []
        self.random: list[int] = []
        self.grids = Grids(e, self.files)
        self.grids.install()
        gm = e.alloc(0x40)
        window = e.alloc(0x40)
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (gm, 0))
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (window, 0))
        e.seam("?GetRandom@ldwGameState@@SAHH@Z", self._random)
        e.seam("?Draw@CSceneManager@@QBEXPAVldwImageGrid@@UldwPoint@@HM@Z", self._scene_draw)
        e.seam("?Draw@ldwGameWindow@@QAEXPAVldwImageGrid@@HHH@Z", self._window_draw)
        e.seam("?Play@CSound@@QAEXW4ESound@@@Z", lambda em: (0, 4))
        e.seam("?StartBubbleGen@CBubbles@@QAEXUldwPoint@@@Z", lambda em: (0, 8))
        e.seam("?StopBubbleGen@CBubbles@@QAEXXZ", lambda em: (0, 0))
        self.anim = e.addr("?FloatingAnim@@3VCFloatingAnim@@A")
        self.manager = e.addr("?FurnitureManager@@3VCFurnitureManager@@A")
        e.call("??0CFloatingAnim@@QAE@XZ", ecx=self.anim)
        e.call("?Reset@CFloatingAnim@@QAEXXZ", ecx=self.anim)
        self.table = self._anim_table()
        e.call("?LoadAssets@CFloatingAnim@@QAEXXZ", ecx=self.anim)

    def static(self, name: str) -> int:
        """The address of a symbol an object keeps to itself (a static: storage class 3)."""
        for obj in self.e.objs:
            for sym, value, sect, cls in obj.symbols.values():
                if sym == name and sect > 0 and sect in obj.addr:
                    return obj.addr[sect] + value
        raise KeyError(name)

    # ---- seams
    def _random(self, em):
        n = em.sarg(0)
        value = self.random.pop(0) if self.random else 0
        return (max(0, min(n - 1, value)) if n > 0 else 0), 0

    def _scene_draw(self, em):
        self.draws.append(("scene", self.grids.ids.get(em.arg(0), em.arg(0)), em.sarg(1), em.sarg(2), em.sarg(3),
                           round(_f(em.arg(4)), 6)))
        return 0, 20

    def _window_draw(self, em):
        self.draws.append(("window", self.grids.ids.get(em.arg(0), em.arg(0)), em.sarg(1), em.sarg(2), em.sarg(3),
                           1.0))
        return 0, 16

    # ---- CFloatingAnim
    def _anim_table(self) -> list:
        """m_sAnim before LoadAssets turns its image ids into grids: (image, frames, random first frame)."""
        at = self.e.addr("?m_sAnim@CFloatingAnim@@0PAUSAnim@1@A")
        return [(self.e.s32(at + 16 * k), self.e.s32(at + 16 * k + 4), self.e.read(at + 16 * k + 8, 1)[0])
                for k in range(ANIM_TYPES)]

    def _slot(self, index: int) -> int:
        return self.anim + 4 + ANIM_SIZE * index

    def _clear(self) -> None:
        for k in range(ANIM_SLOTS):
            self.e.w32(self._slot(k), 0xFFFFFFFF)

    def _play(self, index: int, limit: int = 400) -> list:
        """Draw(index), then Update seven times, until the effect ends: every frame's draws."""
        e, frames = self.e, []
        while e.s32(self._slot(index)) != -1 and len(frames) < limit:
            self.draws = []
            e.call("?Draw@CFloatingAnim@@QBEXH@Z", [index], ecx=self.anim)
            frames.append(list(self.draws))
            for _ in range(7):
                e.call("?Update@CFloatingAnim@@QAEXXZ", ecx=self.anim)
        return frames

    def effect(self, kind: int, x: int = 0, y: int = 0, fade_cell: int = -1, priority: int = 7,
               centred: bool = False) -> list:
        """AddAnim(kind, (x, y), delay 0, no loop, no motion (or the fading cell), priority) and every frame's draws
        until it ends."""
        self._clear()
        self.random = []
        index = self.e.call("?AddAnim@CFloatingAnim@@QAE?BHW4EFloatingAnim@@UldwPoint@@H_NW4EFloatingAnimEffect@@"
                            "W4EScenePriority@@2@Z", [kind, x, y, 0, 0, fade_cell, priority, 1 if centred else 0],
                            ecx=self.anim)
        return self._play(_s(index))

    # ---- CFurnitureManager

    def infos(self) -> list:
        """Every sFurnitureInfo (itemInfo, 0x6C bytes each, 0x6A50 bytes) in the table's order."""
        e = self.e
        at = self.static("?itemInfo@@3PAUsFurnitureInfo@@A")
        out = []
        for k in range(0x6A50 // 0x6C):
            w = [e.s32(at + 0x6C * k + 4 * j) for j in range(27)]
            out.append({"item": w[0], "image": w[1], "anim": w[9:13], "dx": w[13:17], "dy": w[17:21],
                        "delay": w[21], "offsets": w[22]})
        return out

    def _place(self, item: int, orientation: int, x: int, y: int, flags: int = 1, ident: int = 7) -> None:
        e, m = self.e, self.manager
        e.w32(m + 0x1004, 1)                       # one item in the house
        slot = m + 0x1008
        e.write(slot, bytes(0x40))
        e.w32(slot, item)
        e.w32(slot + 4, ident)
        e.w32(slot + 8, 0xFFFFFFFF)                # no animation yet
        e.w32(slot + 0xC, flags)
        e.w32(slot + 0x10, orientation)
        e.w32(slot + 0x14, x)
        e.w32(slot + 0x18, y)
        e.write(m + 0x9014, b"\0\0")               # nothing picked up or pointed at

    def furniture(self, item: int, orientation: int, x: int = 0, y: int = 0) -> list:
        """CFurnitureManager::Draw(0) for `item` placed at (x, y) in `orientation`."""
        self._place(item, orientation, x, y)
        self.draws = []
        self.e.call("?Draw@CFurnitureManager@@QAEXH@Z", [0], ecx=self.manager)
        return list(self.draws)

    def furniture_on(self, item: int, orientation: int, x: int = 0, y: int = 0, delay: int = 1) -> list:
        """SetOnState(id, true, delay) for the placed item: its animation's frames (each a list of draws), or []."""
        self._clear()
        self._place(item, orientation, x, y)
        self.e.call("?SetOnState@CFurnitureManager@@QAEXH_NH@Z", [7, 1, delay], ecx=self.manager)
        index = self.e.s32(self.manager + 0x1008 + 8)
        if index < 0:
            return []
        # the animation loops: one pass over its frames
        frames = self.e.s32(self._slot(index) + 0x18)
        out = []
        for _ in range(frames):
            self.draws = []
            self.e.call("?Draw@CFloatingAnim@@QBEXH@Z", [index], ecx=self.anim)
            out.append(list(self.draws))
            for _ in range(7 * max(1, delay)):
                self.e.call("?Update@CFloatingAnim@@QAEXXZ", ecx=self.anim)
        return out


# ====================================================================== reachability
class CallGraph:
    """Which symbol refers to which (by relocation), over every object: a function's code refers to what it calls or
    names; a data symbol (a vtable, a table) to what it holds."""

    def __init__(self, obj_dir: Path):
        self.refs: dict[str, set] = defaultdict(set)
        self.defined: dict[str, str] = {}
        for path in sorted(Path(obj_dir).glob("*.obj")):
            obj = pe.CoffObject(path)
            by_sect = defaultdict(list)
            for _k, (name, value, sect, cls) in obj.symbols.items():
                if sect > 0 and cls in (2, 3) and not name.startswith((".", "$")):
                    by_sect[sect].append((value, name))
            for sect, syms in by_sect.items():
                s = obj.sections[sect - 1]
                if s["name"].startswith(".debug"):
                    continue
                syms.sort()
                relocs = sorted((va, obj.symbols[si][0]) for va, si, _t in s["relocs"])
                for k, (value, name) in enumerate(syms):
                    end = syms[k + 1][0] if k + 1 < len(syms) else s["size"]
                    if s["chars"] & 0x20:
                        self.defined.setdefault(name, path.stem)
                    for va, target in relocs:
                        if value <= va < end:
                            self.refs[name].add(target)

    def reachable(self) -> set:
        roots = [n for n in self.refs if n == "_WinMain@16" or "$initializer$" in n]
        seen, todo = set(), list(roots)
        while todo:
            n = todo.pop()
            if n in seen:
                continue
            seen.add(n)
            todo.extend(t for t in self.refs.get(n, ()) if t not in seen)
        return seen

    def callers(self, name: str) -> set:
        return {n for n, targets in self.refs.items() if name in targets}


# ====================================================================== the blitter, with an opacity
def blit(rig: "pe.PeopleRig", pixels: bytes, width: int, height: int, rect: tuple, x: int, y: int, alpha: float,
         screen: tuple, background: tuple = (40, 90, 160), percent: int = 100) -> bytes:
    """ldwGameWindowImpl::BlitRectWithAlpha(source, x, y, rect, alpha, percent / 100, false) run whole onto an
    opaque screen `screen` (w, h) of `background`; R, G, B, A bytes in and out (the surfaces hold B, G, R, A)."""
    e = rig.e
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
    dst, dst_buf = surface(sw, sh, bgra((bytes(background) + b"\xff") * (sw * sh)), 0)
    impl = e.alloc(0x40)
    e.w32(impl + 8, sw)
    e.w32(impl + 0xC, sh)
    e.w32(impl + 0x30, dst)
    scale = struct.unpack("<f", struct.pack("<f", percent / 100.0))[0]
    left, top, right, bottom = rect
    e.call("?BlitRectWithAlpha@ldwGameWindowImpl@@AAEXPAUSDL_Surface@@HHHHHHMM_N@Z",
           [src, x, y, left, top, right, bottom, float(alpha), scale, 0], ecx=impl)
    return bgra(e.read(dst_buf, sw * sh * 4))


# ====================================================================== pets, birds and the ball
class AnimalRig:
    """CPetAnimManager::LoadAssets (reading the game's Assets\\petanimpts.dat), CPetManager::DrawPet with the real
    CPet::FeetPos / Scale / KindOfPet, CBird::Draw and CBall::Draw (with the real CInventoryManager::ImageIndex);
    their draws are recorded."""

    OBJECTS = ["PetAnimManager", "PetManager", "Pet", "Bird", "Ball", "InventoryManager"]

    def __init__(self, obj_dir: Path, game: Path):
        import vf2_game_pictures as gp
        self.game = Path(game)
        self.files = gp.GameFiles(game)
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.draws: list = []
        self.handles: dict = {}
        self.grids = Grids(e, self.files)
        self.grids.install()
        gm, window, state, vtable, gstate = (e.alloc(0x40) for _ in range(5))
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (gm, 0))
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (window, 0))
        e.w32(state, vtable)
        e.seam("gs_full_path", lambda em: (em.string(str(self.game / "Assets" / em.cstr(em.arg(0)))), 4))
        e.w32(vtable + 8, e.thunk_of["gs_full_path"])
        e.seam("?Get@ldwGameState@@SAPAV1@XZ", lambda em: (state, 0))
        e.seam("?Get@theGameState@@SAPAV1@XZ", lambda em: (gstate, 0))
        self.game_state = gstate
        e.seam("?GetRandom@ldwGameState@@SAHH@Z", lambda em: (0, 0))
        e.seam("_fopen", self._fopen)
        e.seam("_fread", self._fread)
        e.seam("_fclose", self._fclose)
        e.seam("?GetCellRect@ldwImageGrid@@QAEXHHAAUldwRect@@@Z", self._cell_rect)
        e.seam("?ldwStrCopy@@YAXPADPBDH@Z", self._str_copy)
        e.seam("?DrawScaled@CSceneManager@@QBEXPAVldwImageGrid@@UldwPoint@@HHMM@Z", lambda em: (self.draws.append(
            ("grid", self.grids.ids.get(em.arg(0)), em.sarg(1), em.sarg(2), em.sarg(3), em.sarg(4),
             round(_f(em.arg(5)), 6), round(_f(em.arg(6)), 6))), (0, 0x1C))[1])
        e.seam("?DrawScaled@CSceneManager@@QBEXPAVldwImage@@UldwPoint@@MM_N@Z", lambda em: (self.draws.append(
            ("image", self.grids.ids.get(em.arg(0)), em.sarg(1), em.sarg(2), 0, 0, round(_f(em.arg(3)), 6),
             round(_f(em.arg(4)), 6))), (0, 0x18))[1])
        e.seam("?Draw@CSceneManager@@QBEXPAVldwImage@@UldwPoint@@M@Z", lambda em: (self.draws.append(
            ("image", self.grids.ids.get(em.arg(0)), em.sarg(1), em.sarg(2), 0, 0, 1.0, round(_f(em.arg(3)), 6))),
            (0, 0x10))[1])
        e.seam("?Draw@CSceneManager@@QBEXPAVldwImageGrid@@UldwPoint@@HM@Z", lambda em: (self.draws.append(
            ("grid", self.grids.ids.get(em.arg(0)), em.sarg(1), em.sarg(2), 0, em.sarg(3), 1.0,
             round(_f(em.arg(4)), 6))), (0, 0x14))[1])
        self.pet_anim = e.addr("?PetAnimManager@@3VCPetAnimManager@@A")
        e.call("??0CPetAnimManager@@QAE@XZ", ecx=self.pet_anim)
        e.call("?LoadAssets@CPetAnimManager@@QAEXXZ", ecx=self.pet_anim)
        self.pets = e.addr("?PetManager@@3VCPetManager@@A")

    def _cell_rect(self, em):
        col, row, rect = em.sarg(0), em.sarg(1), em.arg(2)
        import vf2_game_pictures as gp
        entry = gp.entry_by_id(self.grids.ids[em.ecx])
        cells = gp.entry_cells(self.files, entry)
        _name, r = cells[min(row, max(1, entry.rows) - 1) * (entry.cols or 1) + col]
        for k, v in enumerate(r):
            em.w32(rect + 4 * k, v)
        return 0, 12

    @staticmethod
    def _str_copy(em):
        dst, src, n = em.arg(0), em.arg(1), em.sarg(2)
        text = em.cstr(src).encode("latin-1")[:max(0, n - 1)] if src else b""
        em.write(dst, text + bytes(1))
        return 0, 0

    def _fopen(self, em):
        path = Path(em.cstr(em.arg(0)))
        if not path.is_file():
            return 0, 0
        handle = em.alloc(4)
        self.handles[handle] = open(path, "rb")
        return handle, 0

    def _fread(self, em):
        buf, size, count, handle = em.arg(0), em.arg(1), em.arg(2), em.arg(3)
        data = self.handles[handle].read(size * count)
        em.write(buf, data)
        return (len(data) // size if size else 0), 0

    def _fclose(self, em):
        f = self.handles.pop(em.arg(0), None)
        if f:
            f.close()
        return 0, 0

    # ---- CPetManager::DrawPet
    PET_AT = 0x2D74
    PET_SIZE = 0x2D64

    def pet(self, item: int, frame: int, x: int = 0, y: int = 0, direction: int = 0, asleep: bool = False,
            height: int = 0) -> list:
        """DrawPet(0) for pet `item` at (x, y) showing `frame` (CPet+1D40h) facing `direction` (+1D6Ch)."""
        e, at = self.e, self.pets + self.PET_AT
        e.write(at, bytes(self.PET_SIZE))
        e.w32(at + 0x1D24, x)
        e.w32(at + 0x1D28, y)
        e.w32(at + 0x1D40, frame)
        e.w32(at + 0x1D48, height)
        e.w32(at + 0x1D64, item)
        e.write(at + 0x1D6A, bytes([1 if asleep else 0]))
        e.w32(at + 0x1D6C, direction)
        self.draws = []
        e.call("?DrawPet@CPetManager@@QAEXH@Z", [0], ecx=self.pets)
        return list(self.draws)

    def pet_frames(self) -> int:
        """How many frames CPetAnimManager's link table holds (blocks of 1D4h from +C6F8h with image 7)."""
        e, n = self.e, 0
        while e.s32(self.pet_anim + 0xC6F8 + 4 + 0x1D4 * n) == 7 and n < 200:
            n += 1
        return n

    # ---- CBird::Draw
    def bird(self, state: int, facing: int, frame: int, x: int = 0, y: int = 0, height: int = 0,
             scale: float = 1.0) -> list:
        e = self.e
        birds = e.addr("?Bird@@3VCBird@@A")
        e.w32(birds + 0x2AC, self.grids.grid(593))
        e.w32(birds + 0x2B0, self.grids.grid(594))
        e.write(birds, bytes(0x4C))
        e.w32(birds, x)
        e.w32(birds + 4, y)
        e.w32(birds + 0x30, frame)
        e.wf(birds + 0x34, scale)
        e.w32(birds + 0x38, facing)
        e.w32(birds + 0x3C, state)
        e.w32(birds + 0x48, height)
        self.draws = []
        e.call("?Draw@CBird@@QBEXH@Z", [0], ecx=birds)
        return list(self.draws)

    # ---- CBall::Draw
    def ball(self, x: float = 0.0, y: float = 0.0, height: float = 0.0) -> list:
        e = self.e
        ball = e.addr("?Ball@@3VCBall@@A")
        e.write(self.game_state + 0x3C, b"\x01")      # the ball is bought
        e.wf(ball, x)
        e.wf(ball + 4, y)
        e.wf(ball + 0x20, height)
        self.draws = []
        e.call("?Draw@CBall@@QAEXH@Z", [0], ecx=ball)
        return list(self.draws)


# ====================================================================== the store's item pictures
class StoreRig:
    """CInventoryManager::DrawItem(point, item, state, position, shadow) run whole; its draws recorded as
    (kind, image, x, y, cell, percent)."""

    OBJECTS = ["InventoryManager"]

    def __init__(self, obj_dir: Path, game: Path):
        import vf2_game_pictures as gp
        self.files = gp.GameFiles(game)
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.draws: list = []
        self.grids = Grids(e, self.files)
        self.grids.install()
        gm, window = e.alloc(0x40), e.alloc(0x40)
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (gm, 0))
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (window, 0))
        e.seam("?GetCellRect@ldwImageGrid@@QAEXHHAAUldwRect@@@Z", self._cell_rect)
        e.seam("?DrawScaled@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHH_N@Z", lambda em: (self.draws.append(
            ("scaled", self.grids.ids.get(em.arg(0)), em.sarg(1), em.sarg(2), em.sarg(3), em.sarg(4))), (0, 24))[1])
        e.seam("?Draw@ldwGameWindow@@QAEXPAVldwImageGrid@@HHH@Z", lambda em: (self.draws.append(
            ("draw", self.grids.ids.get(em.arg(0)), em.sarg(1), em.sarg(2), em.sarg(3), 100)), (0, 16))[1])
        e.seam("?DrawTinted@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHUldwColor@@MM@Z", lambda em: (self.draws.append(
            ("tinted", self.grids.ids.get(em.arg(0)), em.sarg(1), em.sarg(2), em.sarg(3), round(_f(em.arg(5)), 6))),
            (0, 28))[1])
        e.seam("?DrawItem@CFurnitureManager@@QAEXW4EInventoryItem@@UldwRect@@H_NM@Z", lambda em: (
            self.draws.append(("furniture", em.arg(0), 0, 0, 0, 0)), (0, 0x20))[1])
        self.manager = e.alloc(0x600)

    def _cell_rect(self, em):
        import vf2_game_pictures as gp
        col, row, rect = em.sarg(0), em.sarg(1), em.arg(2)
        entry = gp.entry_by_id(self.grids.ids[em.ecx])
        cells = gp.entry_cells(self.files, entry)
        _name, r = cells[min(row, max(1, entry.rows) - 1) * (entry.cols or 1) + col]
        for k, v in enumerate(r):
            em.w32(rect + 4 * k, v)
        return 0, 12

    def item(self, item: int, state: int = 0, x: int = 0, y: int = 0, position: int = 0, shadow: bool = False,
             pictures: dict | None = None) -> list:
        """DrawItem((x, y), item, state, position, shadow); `pictures` sets the per-item picture slots (+408h + 4 x
        item, +468h, +46Ch: an outfit's row), every other slot -1 (no picture chosen)."""
        e = self.e
        e.write(self.manager + 0x400, b"\xff" * 0x200)
        for off, v in (pictures or {}).items():
            e.w32(self.manager + off, v)
        self.draws = []
        e.call("?DrawItem@CInventoryManager@@QAEXUldwPoint@@W4EInventoryItem@@W4EInventoryItemState@@"
               "W4EInventoryItemPosition@@_N@Z", [x, y, item, state, position, 1 if shadow else 0], ecx=self.manager)
        return list(self.draws)


# ====================================================================== butterflies and bubbles
class InsectRig:
    """theButterflyClass::DrawButterflies, CMiniButterflyClass::Draw and CBubbles::Draw run whole; their
    ldwGameWindow::DrawScaled(grid, x, y, cell, percent, centre) calls recorded as (image, x, y, cell, percent,
    centre)."""

    OBJECTS = ["theButterflyClass", "theMiniButterflyClass", "Bubbles"]

    def __init__(self, obj_dir: Path, game: Path):
        import vf2_game_pictures as gp
        self.files = gp.GameFiles(game)
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.draws: list = []
        self.grids = Grids(e, self.files)
        self.grids.install()
        self.window = e.alloc(0x40)
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (self.window, 0))
        e.seam("?IsDayTime@CNight@@QAE_NXZ", lambda em: (1, 0))
        e.seam("?DrawScaled@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHH_N@Z", lambda em: (self.draws.append(
            (self.grids.ids.get(em.arg(0)), em.sarg(1), em.sarg(2), em.sarg(3), em.sarg(4), em.arg(5) & 0xFF)),
            (0, 24))[1])

    def butterfly(self, row: int, frame: int, vx: int, percent: int, state: int = 2, index: int = 0) -> list:
        """DrawButterflies with one butterfly (instance `index`) of colour row `row`, wing frame `frame`, moving
        `vx` across, at `percent`, in `state`; the others are out of the picture (state 3 is drawn too, so they
        are left as zeros and their draws dropped)."""
        e = self.e
        this = e.alloc(0x300)
        e.w32(this, self.grids.grid(596))
        e.w32(this + 0x280, self.window)
        at = this + 0x34 * index
        e.w32(at + 0x1C, vx)
        e.w32(at + 0x24, row)
        e.w32(at + 0x28, frame)
        e.w32(at + 0x30, percent)
        e.w32(at + 0x34, state)
        self.draws = []
        e.call("?DrawButterflies@theButterflyClass@@QAEXXZ", ecx=this)
        return self.draws[index]

    def mini(self, row: int, frame: int, vx: int, percent: int, state: int = 1, index: int = 0) -> list:
        e = self.e
        this = e.alloc(0x300)
        e.w32(this + 0x224, self.grids.grid(596))
        e.w32(this + 0x21C, self.window)
        at = this + 0x3C * index
        e.write(at, b"\x01")
        e.w32(at + 0x20, vx)
        e.w32(at + 0x28, row)
        e.w32(at + 0x2C, frame)
        e.w32(at + 0x34, percent)
        e.w32(at + 0x38, state)
        self.draws = []
        e.call("?Draw@CMiniButterflyClass@@QAEXXZ", ecx=this)
        return self.draws
