"""Run the game's own screen-drawing code from the B200 desktop objects (unicorn), for the Picture Maker's screens,
backgrounds, family tree, collections and store pictures (src/vf2_art_screens.py).

`ScreenRig(obj_dir, game, objects)` links the chosen objects (vf2_people_emu.Emu). Every function none of them
defines is a seam: the drawing calls (theGraphicsManager::Draw / DrawCell / DrawCentered, ldwGameWindow::Draw /
DrawScaled / FillRect / SetClipping / ResetClipping, ...) are recorded; the image getters hand out one tagged block
per image id; ldwImage::GetWidth / GetHeight and ldwImageGrid::GetCellRect answer from the real files (the cell
rules of vf2_game_pictures, checked against the game's own GetCellRect in tests/test_game_pictures.py); every other
function the code calls is answered by a default seam that pops the arguments its decorated name declares and
returns 0 (or, for a function returning a pointer or a reference, a zeroed block of its own). Every default call
is kept in `rig.defaults`, so a test can see exactly what the drawing code asked for besides the draws.

theGameState::Get answers a block laid out as the game's own constructor (??0theGameState) lays the window fields
(GetGameWindowWidth 0x400, GetGameWindowHeight 0x300, the wide-screen flag 0: SetToWideScreen is called by no code),
with theGameState's own vtable when theGameState is linked.

Nothing here starts the game or writes a file.
"""
from __future__ import annotations

import struct
from pathlib import Path

from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP

import vf2_people_emu as pe

STRUCT_SIZES = {"ldwPoint": 8, "ldwRect": 16, "ldwColor": 4, "ldwWString": 4}
GAMESTATE_SIZE = 0x26000
WINDOW_W, WINDOW_H = 0x400, 0x300           # ??0theGameState: [+25CD8h] = 400h, [+25CDCh] = 300h


def _f(v: int) -> float:
    return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]


# ------------------------------------------------------------------ decorated names
class _Parser:
    """Reads an MSVC decorated function name far enough to know how many bytes of arguments the callee pops and
    what kind of thing it returns."""

    def __init__(self, text: str):
        self.t, self.i = text, 0
        self.backrefs: list[int] = []

    def peek(self, n=1):
        return self.t[self.i:self.i + n]

    def take(self, n=1):
        s = self.t[self.i:self.i + n]
        self.i += n
        return s

    def name(self) -> str:
        """A qualified name (fragments ending in "@", a digit is a remembered fragment); its first fragment."""
        first = None
        while True:
            c = self.peek()
            if c == "@" or c == "":
                self.take()
                return first or ""
            if c.isdigit():
                self.take()
                first = first or "?"
                continue
            end = self.t.index("@", self.i)
            first = first or self.t[self.i:end]
            self.i = end + 1

    def type(self, param: bool = True) -> tuple[int, str]:
        """(size on the stack, kind) of one type."""
        start = self.i
        c = self.take()
        if c.isdigit():
            return self.backrefs[int(c)], "int"
        if c == "?":                            # a qualified return type
            self.take()
            return self.type(param)
        if c == "X" or c == "@":                 # void, or a constructor's missing return type
            return 0, "void"
        if c in "CDEFGHIJK":
            size, kind = 4, "int"
        elif c == "M":
            size, kind = 4, "float"
        elif c == "N" or c == "O":
            size, kind = 8, "float"
        elif c == "_":
            d = self.take()
            size, kind = (8, "int") if d in "JK" else (4, "int")
        elif c in "PQRS":
            if self.peek() == "6":               # a function pointer
                self.take()
                self.take()                       # calling convention
                self.type(False)
                while self.peek() not in ("@", "Z", ""):
                    self.type()
                self.take()
                size, kind = 4, "ptr"
            else:
                self.take()                       # cv
                self.type(False)
                size, kind = 4, "ptr"
        elif c == "A" or c == "B":
            self.take()
            self.type(False)
            size, kind = 4, "ptr"
        elif c in "UV":
            n = self.name()
            size, kind = STRUCT_SIZES.get(n, 4), "struct"
        elif c == "W":
            self.take()
            self.name()
            size, kind = 4, "int"
        else:
            raise ValueError(f"type {c!r} in {self.t}")
        if param and self.i - start > 1 and len(self.backrefs) < 10:
            self.backrefs.append(size)
        return size, kind


def signature(name: str) -> tuple[int, str, bool]:
    """(bytes the callee pops, return kind, has a hidden return pointer) for a decorated function name; plain C
    names are cdecl returning an int."""
    if not name.startswith("?"):
        return 0, "int", False
    at = name.index("@@") + 2
    while name[at] == "?" or name[at] == "@":
        at += 1
    p = _Parser(name)
    p.i = at
    access = p.take()
    if access in "YZ":
        conv = p.take()
    elif access in "CDKLST":
        conv = p.take()
    else:
        p.take()                                  # cv of `this`
        conv = p.take()
    _rsize, rkind = p.type(False)
    hidden = rkind == "struct"
    args = 0
    if p.peek() == "X":
        p.take()
    else:
        while p.peek() not in ("@", "Z", ""):
            size, _k = p.type()
            args += size
    if hidden:
        args += 4
    pops = args if conv in "EG" else (max(0, args - 8) if conv == "I" else 0)
    return pops, ("ptr" if hidden else rkind), hidden


# ------------------------------------------------------------------ the rig
class AutoEmu(pe.Emu):
    """vf2_people_emu.Emu whose functions without a seam go to `fallback(name)` instead of stopping."""
    fallback = None

    def _thunk_hook(self, uc, address, size, user):
        name = self.thunks.get(address)
        if name is not None and address != pe.STOP and name not in self.seams and self.fallback is not None:
            self.fallback(name)
            return
        super()._thunk_hook(uc, address, size, user)


class ScreenRig:
    def __init__(self, obj_dir: Path, game: Path, objects: list[str]):
        import vf2_game_pictures as gp
        self.gp = gp
        self.files = gp.GameFiles(game)
        self.e = e = AutoEmu(obj_dir, objects)
        self.defaults: list = []
        self.records: list = []
        self.images: dict[int, int] = {}          # block -> image id
        self.blocks: dict[int, int] = {}          # image id -> block
        self.dummies: dict[str, int] = {}
        self.clip = None
        self.time = 0
        self._vtable = e.alloc(4 * 256)
        for k in range(256):
            name = f"vslot{k:#x}"
            e.seam(name, lambda em, k=k: self._vslot(k))
            e.w32(self._vtable + 4 * k, e.thunk_of[name])
        e.fallback = self._default
        # the game state: the window fields as its constructor sets them
        self.state = e.alloc(GAMESTATE_SIZE)
        try:
            e.w32(self.state, e.addr("??_7theGameState@@6B@"))
        except KeyError:
            e.w32(self.state, self._vtable)
        e.w32(self.state + 0x25CD8, WINDOW_W)
        e.w32(self.state + 0x25CDC, WINDOW_H)
        e.write(self.state + 0x25CE0, b"\0")
        self.window = self.dummy("ldwGameWindow")
        self.gm = self.dummy("theGraphicsManager")
        s = e.seam
        s("?Get@theGameState@@SAPAV1@XZ", lambda em: (self.state, 0))
        s("?Get@ldwGameState@@SAPAV1@XZ", lambda em: (self.state, 0))
        s("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (self.window, 0))
        s("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (self.gm, 0))
        s("?GetWidth@ldwGameWindow@@QAEHXZ", lambda em: (WINDOW_W, 0))
        s("?GetHeight@ldwGameWindow@@QAEHXZ", lambda em: (WINDOW_H, 0))
        if "?GetWideScreenOffsetX@theGameState@@QAEHXZ" not in e.globals:
            s("?GetWideScreenOffsetX@theGameState@@QAEHXZ", lambda em: (0, 0))
        s("??2@YAPAXI@Z", lambda em: (self.zalloc(max(4, em.arg(0))), 0))
        s("??_U@YAPAXI@Z", lambda em: (self.zalloc(max(4, em.arg(0))), 0))
        s("_malloc", lambda em: (self.zalloc(max(4, em.arg(0))), 0))
        s("_memset", self._memset)
        s("_memcpy", self._memcpy)
        s("_memmove", self._memcpy)
        for getter in ("?GetImage@theGraphicsManager@@QAEPAVldwImage@@W4EImage@@@Z",
                       "?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z",
                       "?GetImageStrip@theGraphicsManager@@QAEPAVldwImageStrip@@W4EImage@@@Z"):
            s(getter, lambda em: (self.block(em.arg(0)), 4))
        s("?Draw@theGraphicsManager@@QAEXW4EImage@@HHMH@Z", self._gm_draw)
        s("?DrawCell@theGraphicsManager@@QAEXW4EImage@@HHHMH@Z", self._gm_draw_cell)
        s("?DrawCentered@theGraphicsManager@@QAEXW4EImage@@HH@Z", self._gm_draw_centered)
        s("?GetWidth@ldwImage@@QAEHXZ", lambda em: (self._image_size(em.ecx)[0], 0))
        s("?GetHeight@ldwImage@@QAEHXZ", lambda em: (self._image_size(em.ecx)[1], 0))
        s("?GetCellWidth@ldwImageGrid@@QAEHXZ", lambda em: (self._cell_size(em.ecx)[0], 0))
        s("?GetCellHeight@ldwImageGrid@@QAEHXZ", lambda em: (self._cell_size(em.ecx)[1], 0))
        s("?GetCellRect@ldwImageGrid@@QAEXHAAUldwRect@@@Z", self._cell_rect)
        s("?GetCellRect@ldwImageGrid@@QAEXHHAAUldwRect@@@Z", self._cell_rect2)
        w = "ldwGameWindow@@QAEX"
        s(f"?Draw@{w}PAVldwImage@@HH@Z", lambda em: self._win_draw(em, False, 2))
        s(f"?Draw@{w}PAVldwImage@@HHM@Z", lambda em: self._win_draw(em, False, 3))
        s(f"?Draw@{w}PAVldwImageGrid@@HHH@Z", lambda em: self._win_draw(em, True, 3))
        s(f"?Draw@{w}PAVldwImageGrid@@HHHM@Z", lambda em: self._win_draw(em, True, 4))
        s(f"?Draw@{w}PAVldwImage@@HHAAUldwRect@@M@Z", self._win_draw_rect)
        s(f"?DrawScaled@{w}PAVldwImage@@HHMH_N@Z", lambda em: self._win_scaled(em, False))
        s(f"?DrawScaled@{w}PAVldwImageGrid@@HHHMH_N@Z", lambda em: self._win_scaled(em, True))
        s(f"?FillRect@{w}AAUldwRect@@UldwColor@@@Z", self._fill_color)
        s(f"?FillRect@{w}AAUldwRect@@MMMM@Z", self._fill_floats)
        s(f"?SetClipping@{w}UldwRect@@@Z", self._set_clip)
        s(f"?ResetClipping@{w}XZ", self._reset_clip)
        s(f"?DrawLine@{w}HHHHUldwColor@@@Z", self._line)
        s(f"?DrawTinted@{w}PAVldwImage@@HHUldwColor@@MM_N@Z", self._tinted)
        s("?Exists@ldwImage@@SA_NPBD@Z", lambda em: (int(self.files.has(em.cstr(em.arg(0)))), 0))
        s("??0ldwImage@@QAE@PBD@Z", self._named_image)

    # ---- memory
    def zalloc(self, size: int) -> int:
        at = self.e.alloc(size)
        self.e.write(at, bytes(size))
        return at

    def dummy(self, name: str, size: int = 0x2000) -> int:
        if name not in self.dummies:
            at = self.zalloc(size)
            self.e.w32(at, self._vtable)
            self.dummies[name] = at
        return self.dummies[name]

    def _memset(self, em):
        em.write(em.arg(0), bytes([em.arg(1) & 0xFF]) * em.arg(2))
        return em.arg(0), 0

    def _memcpy(self, em):
        em.write(em.arg(0), em.read(em.arg(1), em.arg(2)))
        return em.arg(0), 0

    # ---- the default seam
    def _default(self, name: str):
        e, uc = self.e, self.e.uc
        try:
            pops, kind, hidden = signature(name)
        except Exception as exc:                                  # pragma: no cover - a name it cannot read
            e._unmapped_error = f"cannot read the decorated name {name}: {exc}"
            uc.emu_stop()
            return
        esp = uc.reg_read(UC_X86_REG_ESP)
        args = [e.r32(esp + 4 + 4 * k) for k in range(6)]
        self.defaults.append((name, e.ecx, args))
        if name.startswith("??0"):                    # a constructor returns `this`, given the generic vtable
            eax = e.ecx
            if eax and e.r32(eax) == 0:
                e.w32(eax, self._vtable)
        elif hidden:
            eax = args[0]
        elif kind == "ptr":
            eax = self.dummy(name)
        else:
            eax = 0
        ret = e.r32(esp)
        uc.reg_write(UC_X86_REG_EAX, eax)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + pops)
        uc.reg_write(UC_X86_REG_EIP, ret)

    def _vslot(self, k: int):
        self.defaults.append((f"vslot{k:#x}", self.e.ecx, []))
        return 0, 0

    # ---- images
    def block(self, image_id: int) -> int:
        if image_id not in self.blocks:
            at = self.zalloc(0x40)
            self.blocks[image_id] = at
            self.images[at] = image_id
        return self.blocks[image_id]

    def _entry(self, block: int):
        return self.gp.entry_by_id(self.images[block])

    def _image_size(self, block: int):
        if isinstance(self.images.get(block), str):
            return self.files.size(self.images[block])
        entry = self._entry(block)
        if entry.kind == "image":
            return self.files.size(entry.file)
        cells = self.gp.entry_cells(self.files, entry)
        return cells[0][1][2] * entry.cols, cells[0][1][3] * max(1, entry.rows)

    def _cell_size(self, block: int):
        _f_, r = self.gp.entry_cells(self.files, self._entry(block))[0]
        return r[2] - r[0], r[3] - r[1]

    def _cell(self, image_id, cell: int):
        if isinstance(image_id, str):                 # a picture loaded by name (ldwImage(name))
            w, h = self.files.size(image_id)
            return self.files.relative(image_id.lower()), (0, 0, w, h)
        return self.gp.cell_of(self.files, image_id, cell)

    def _cell_rect(self, em):
        image_id = self.images[em.ecx]
        _name, r = self._cell(image_id, em.arg(0))
        for k, v in enumerate(r):
            em.w32(em.arg(1) + 4 * k, v)
        return 0, 8

    def _cell_rect2(self, em):
        entry = self._entry(em.ecx)
        _name, r = self._cell(entry.id, em.arg(1) * max(1, entry.cols) + em.arg(0))
        for k, v in enumerate(r):
            em.w32(em.arg(2) + 4 * k, v)
        return 0, 12

    # ---- recorded draws: ("draw", image id, cell, x, y, alpha, percent, clip)
    def _rec(self, image_id, cell, x, y, alpha=1.0, percent=100):
        self.records.append(("draw", image_id, cell, x, y, round(alpha, 6), percent, self.clip))

    def _gm_draw(self, em):
        self._rec(em.arg(0), 0, em.sarg(1), em.sarg(2), em.farg(3), em.sarg(4))
        return 0, 20

    def _gm_draw_cell(self, em):
        self._rec(em.arg(0), em.sarg(1), em.sarg(2), em.sarg(3), em.farg(4), em.sarg(5))
        return 0, 24

    def _gm_draw_centered(self, em):
        self.records.append(("centered", em.arg(0), em.sarg(1), em.sarg(2), self.clip))
        return 0, 12

    def _win_draw(self, em, grid: bool, nargs: int):
        image = self.images.get(em.arg(0))
        if image is None:
            self.records.append(("draw?", em.arg(0), [em.sarg(k) for k in range(1, nargs + 1)]))
        elif grid:                                        # (grid, x, y, cell[, alpha])
            alpha = em.farg(4) if nargs == 4 else 1.0
            self._rec(image, em.sarg(3), em.sarg(1), em.sarg(2), alpha)
        else:
            alpha = em.farg(3) if nargs == 3 else 1.0
            self._rec(image, 0, em.sarg(1), em.sarg(2), alpha)
        return 0, 4 * (nargs + 1)

    def _win_draw_rect(self, em):
        r = em.arg(3)
        self.records.append(("draw_rect", self.images.get(em.arg(0)), em.sarg(1), em.sarg(2),
                             tuple(em.s32(r + 4 * k) for k in range(4)), round(em.farg(4), 6), self.clip))
        return 0, 20

    def _win_scaled(self, em, grid: bool):
        if grid:
            self.records.append(("scaled", self.images.get(em.arg(0)), em.sarg(3), em.sarg(1), em.sarg(2),
                                 round(em.farg(4), 6), em.sarg(5), self.clip))
            return 0, 28
        self.records.append(("scaled", self.images.get(em.arg(0)), 0, em.sarg(1), em.sarg(2), round(em.farg(3), 6),
                             em.sarg(4), self.clip))
        return 0, 24

    def _fill_color(self, em):
        r = em.arg(0)
        c = em.arg(1)
        self.records.append(("fill", tuple(em.s32(r + 4 * k) for k in range(4)), c, self.clip))
        return 0, 8

    def _fill_floats(self, em):
        r = em.arg(0)
        self.records.append(("fillf", tuple(em.s32(r + 4 * k) for k in range(4)),
                             tuple(round(em.farg(k), 6) for k in range(1, 5)), self.clip))
        return 0, 20

    def _set_clip(self, em):
        # ldwGameWindow::SetClipping: the impl's clipping rectangle (+60h..+6Ch) becomes the rectangle as given
        self.clip = tuple(em.sarg(k) for k in range(4))
        self.records.append(("clip", self.clip))
        return 0, 16

    def _reset_clip(self, em):
        # ldwGameWindow::ResetClipping: (0, 0, the window's width, its height)
        self.clip = None
        self.records.append(("unclip",))
        return 0, 0

    def _line(self, em):
        self.records.append(("line", em.sarg(0), em.sarg(1), em.sarg(2), em.sarg(3), em.arg(4), self.clip))
        return 0, 20

    def _tinted(self, em):
        self.records.append(("tinted", self.images.get(em.arg(0)), em.sarg(1), em.sarg(2), em.arg(3),
                             round(em.farg(4), 6), round(em.farg(5), 6), em.arg(6) & 0xFF, self.clip))
        return 0, 28

    def _named_image(self, em):
        name = em.cstr(em.arg(0))
        self.images[em.ecx] = name
        return em.ecx, 4

    def sym(self, name: str) -> int:
        """The address of a symbol, global or static (a file's own table)."""
        if name in self.e.globals:
            return self.e.globals[name]
        for obj in self.e.objs:
            for n, value, sect, _cls in obj.symbols.values():
                if n == name and sect > 0 and sect in obj.addr:
                    return obj.addr[sect] + value
        return self.e.addr(name)

    def symbol_at(self, address: int) -> str:
        """The function (and offset) an address is in, for messages."""
        best = None
        for obj in self.e.objs:
            for name, value, sect, cls in obj.symbols.values():
                if sect > 0 and sect in obj.addr and cls in (2, 3) and not name.startswith((".", "$")):
                    at = obj.addr[sect] + value
                    if at <= address and (best is None or at > best[0]):
                        best = (at, name)
        return f"{best[1]}+{address - best[0]:#x}" if best else hex(address)

    # ---- running
    def new(self, ctor: str, size: int = 0x4000) -> int:
        this = self.zalloc(size)
        self.e.call(ctor, ecx=this)
        return this

    def draw(self, fn: str, this: int, args=()) -> list:
        self.records = []
        self.clip = None
        self.e.call(fn, list(args), ecx=this)
        return self.records

    def draws(self, records=None) -> list:
        """The recorded drawing as the picture's layers, in order: ("draw", file, rect, x, y, alpha) after the
        clipping rectangle (the game's ldwGameWindowImpl::ClipRect: the visible part of the cell, moved by what is
        cut off its left and top; no clipping rectangle is the whole window), and ("fill", x, y, w, h, rgba) for
        FillRect and the straight lines ldwGameWindowImpl::DrawLine fills."""
        out = []
        for r in (self.records if records is None else records):
            kind = r[0]
            if kind == "draw":
                _k, image, cell, x, y, alpha, percent, clip = r
                if percent != 100:
                    raise AssertionError(f"a scaled draw of {image}: {r}")
                name, rect = self._cell(image, cell)
                clipped = clip_draw(rect, x, y, clip or (0, 0, WINDOW_W, WINDOW_H))
                if clipped is not None:
                    rect, x, y = clipped
                    out.append(("draw", name, rect, x, y, alpha))
            elif kind in ("fill", "fillf"):
                rect, colour, clip = r[1], r[2], r[3]
                floats = colour if kind == "fillf" else color_floats(colour)
                fill = fill_rect(rect, floats, clip or (0, 0, WINDOW_W, WINDOW_H))
                if fill is not None:
                    out.append(fill)
            elif kind == "line":
                _k, x1, y1, x2, y2, colour, clip = r
                rect = line_rect(x1, y1, x2, y2)
                fill = fill_rect(rect, color_floats(colour), clip or (0, 0, WINDOW_W, WINDOW_H))
                if fill is not None:
                    out.append(fill)
            elif kind in ("clip", "unclip"):
                continue
            else:
                raise AssertionError(f"a draw the pictures do not cover: {r}")
        return out


def f32(v: float) -> float:
    return struct.unpack("<f", struct.pack("<f", v))[0]


def color_floats(colour: int) -> tuple:
    """ldwGameWindow::FillRect / DrawLine (ldwColor): each byte (r, g, b, a from the lowest) / 255.0f."""
    return tuple(f32(f32((colour >> s) & 0xFF) / f32(255.0)) for s in (0, 8, 16, 24))


def line_rect(x1, y1, x2, y2):
    """ldwGameWindowImpl::DrawLine for a straight line: the rectangle it fills (both ends included)."""
    if x1 == x2:
        return (x1, min(y1, y2), x1 + 1, max(y1, y2) + 1)
    if y1 == y2:
        return (min(x1, x2), y1, max(x1, x2) + 1, y1 + 1)
    raise AssertionError(f"a slanted line ({x1}, {y1}) - ({x2}, {y2})")


def fill_rect(rect, floats, clip):
    """ldwGameWindowImpl::FillRect: the rectangle cut to the clipping rectangle (nothing when it is outside), each
    channel (int)(f * 255.0f); an alpha of 1 is an opaque SDL_FillRect."""
    l, t, r, b = rect
    cl, ct, cr, cb = clip
    if l > cr or r < cl or t > cb or b < ct:
        return None
    l, t, r, b = max(l, cl), max(t, ct), min(r, cr), min(b, cb)
    if r <= l or b <= t:
        return None
    if floats[3] != 1.0:
        raise AssertionError(f"a see-through fill {rect} {floats}")
    rgb = tuple(int(f32(f * f32(255.0))) for f in floats[:3])
    return ("fill", l, t, r - l, b - t, (*rgb, 255))

def clip_draw(rect, x, y, clip):
    """ldwGameWindowImpl::ClipRect's rule for a clipping rectangle (left, top, right, bottom): None when nothing of
    the cell is inside, else (cut rectangle, x, y)."""
    if clip is None:
        return tuple(rect), x, y
    l, t, r, b = rect
    w, h = r - l, b - t
    cl, ct, cr, cb = clip
    if x < cl:
        l += cl - x
        w -= cl - x
        x = cl
    if y < ct:
        t += ct - y
        h -= ct - y
        y = ct
    if x + w > cr:
        w = cr - x
    if y + h > cb:
        h = cb - y
    if w <= 0 or h <= 0:
        return None
    return (l, t, l + w, t + h), x, y


def vtable_names(obj_dir: Path, obj: str, symbol: str, slots: int = 64) -> list:
    """The function names a vtable in an object holds, slot by slot."""
    o = pe.CoffObject(Path(obj_dir) / f"{obj}.obj")
    for _k, (n, v, s, _c) in o.symbols.items():
        if n == symbol:
            sec = o.sections[s - 1]
            rel = {va: o.symbols[si][0] for va, si, _t in sec["relocs"]}
            return [rel.get(v + 4 * k) for k in range(slots) if (v + 4 * k) in rel]
    raise KeyError(symbol)
