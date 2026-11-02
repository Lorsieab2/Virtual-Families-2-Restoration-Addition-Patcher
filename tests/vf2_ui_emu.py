"""Run the game's own interface and meter drawing code from the B200 desktop objects (unicorn), for the Picture
Maker's meters and interface pictures (src/vf2_art_meters.py, src/vf2_art_ui.py).

`UiRig(obj_dir, game, objects)` links the chosen objects (vf2_people_emu.Emu); every function they call and do not
define is a seam. theGraphicsManager's GetImage / GetImageGrid / GetImageStrip give a small picture object that
remembers the image id (theGraphicsManager::GetImageGridForCanvas runs whole when its object is linked: it chooses
the id); ldwImageGrid::GetCellRect, GetColumnCount and ldwImage::GetWidth / GetHeight answer from the image table
and the game folder's real picture sizes (vf2_game_pictures.entry_cells, itself checked against the game's
GetCellRect by tests/test_game_pictures.py). Every draw is recorded in order:

  ("draw", image id, cell, x, y, alpha)   ldwGameWindow::Draw of a picture (cell -1: a whole ldwImage) and
                                          theGraphicsManager::Draw / DrawCell (alpha as the float passed)
  ("tinted", image id, cell, x, y, rgba)  ldwGameWindow::DrawTinted
  ("clip", l, t, r, b) / ("unclip",)      ldwGameWindow::SetClipping / ResetClipping
  ("fill", l, t, r, b, rgba)              ldwGameWindow::FillRect (rgba as the floats the game passes, 0-1)

Text (DrawString*, the string manager, fonts) is answered with nothing: the pictures leave text out. Nothing here
starts the game or writes a file.
"""
from __future__ import annotations

import struct
from pathlib import Path

import vf2_game_pictures as gp
import vf2_people_emu as pe


def _f(v: int) -> float:
    return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]


GM = "theGraphicsManager@@"
WIN = "ldwGameWindow@@"


class UiRig:
    def __init__(self, obj_dir: Path, game: Path, objects: list[str]):
        self.files = gp.GameFiles(game)
        self.e = e = pe.Emu(obj_dir, objects)
        self.draws: list = []
        self.objects: dict[int, int] = {}            # picture object -> image id
        self.by_id: dict[int, int] = {}
        self.gm = e.alloc(0x100)
        self.window = e.alloc(0x100)
        self.state = e.alloc(0x30000)
        self.strings = e.alloc(0x100)
        self.empty = e.string("")
        e.seam("??2@YAPAXI@Z", lambda em: (em.alloc(max(4, em.arg(0))), 0))
        e.seam("??_U@YAPAXI@Z", lambda em: (em.alloc(max(4, em.arg(0))), 0))
        e.seam("??3@YAXPAXI@Z", lambda em: (0, 0))
        e.seam("??3@YAXPAX@Z", lambda em: (0, 0))
        e.seam(f"?Get@{GM}SAPAV1@XZ", lambda em: (self.gm, 0))
        e.seam(f"?Get@{WIN}SAPAV1@XZ", lambda em: (self.window, 0))
        e.seam("?Get@theGameState@@SAPAV1@XZ", lambda em: (self.state, 0))
        e.seam("?Get@theStringManager@@SAPAV1@XZ", lambda em: (self.strings, 0))
        e.seam("?GetWideScreenOffsetX@theGameState@@QAEHXZ", lambda em: (0, 0))
        for name in (f"?GetImage@{GM}QAEPAVldwImage@@W4EImage@@@Z", f"?GetImageGrid@{GM}QAEPAVldwImageGrid@@W4EImage@@@Z",
                     f"?GetImageStrip@{GM}QAEPAVldwImageStrip@@W4EImage@@@Z"):
            e.seam(name, lambda em: (self.picture(em.arg(0)), 4))
        e.seam(f"?Draw@{GM}QAEXW4EImage@@HHMH@Z", lambda em: self._rec(("draw", em.arg(0), -1, em.sarg(1),
                                                                                   em.sarg(2), em.farg(3)), 20))
        e.seam(f"?DrawCell@{GM}QAEXW4EImage@@HHHMH@Z", lambda em: self._rec(
            ("draw", em.arg(0), em.sarg(1), em.sarg(2), em.sarg(3), em.farg(4)), 24))
        e.seam(f"?Draw@{WIN}QAEXPAVldwImage@@HH@Z", lambda em: self._rec(
            ("draw", self.objects[em.arg(0)], -1, em.sarg(1), em.sarg(2), 1.0), 12))
        e.seam(f"?Draw@{WIN}QAEXPAVldwImageGrid@@HHH@Z", lambda em: self._rec(
            ("draw", self.objects[em.arg(0)], em.sarg(3), em.sarg(1), em.sarg(2), 1.0), 16))
        e.seam(f"?Draw@{WIN}QAEXPAVldwImageGrid@@HHHM@Z", lambda em: self._rec(
            ("draw", self.objects[em.arg(0)], em.sarg(3), em.sarg(1), em.sarg(2), em.farg(4)), 20))
        e.seam(f"?DrawTinted@{WIN}QAEXPAVldwImageGrid@@HHHUldwColor@@MM@Z", lambda em: self._rec(
            ("tinted", self.objects[em.arg(0)], em.sarg(3), em.sarg(1), em.sarg(2), em.arg(4)), 28))
        e.seam(f"?SetClipping@{WIN}QAEXUldwRect@@@Z", lambda em: self._rec(
            ("clip", em.sarg(0), em.sarg(1), em.sarg(2), em.sarg(3)), 16))
        e.seam(f"?ResetClipping@{WIN}QAEXXZ", lambda em: self._rec(("unclip",), 0))
        e.seam(f"?FillRect@{WIN}QAEXAAUldwRect@@MMMM@Z", self._fill_floats)
        e.seam(f"?FillRect@{WIN}QAEXAAUldwRect@@UldwColor@@@Z", self._fill_colour)
        for name, pop in ((f"?DrawString@{WIN}QAEXPBDHHUldwColor@@PAVldwFont@@@Z", 20),
                          (f"?DrawStringCentered@{WIN}QAEXPBDHHUldwColor@@PAVldwFont@@@Z", 20),
                          (f"?DrawStringRight@{WIN}QAEXPBDHHUldwColor@@PAVldwFont@@@Z", 20),
                          (f"?SetFont@{WIN}QAEXPAVldwFont@@@Z", 4)):
            e.seam(name, lambda em, pop=pop: (0, pop))
        e.seam(f"?GetFont@{WIN}QAEPAVldwFont@@XZ", lambda em: (0, 0))
        e.seam("?GetString@theStringManager@@QAEPADW4StringId@@@Z", lambda em: (self.empty, 4))
        e.seam("?GetFont@theStringManager@@QAEPAVldwFont@@W4FontId@@@Z", lambda em: (0, 4))
        e.seam("_sprintf", lambda em: (em.write(em.arg(0), b"\0"), (0, 0))[1])
        e.seam("?GetCellRect@ldwImageGrid@@QAEXHHAAUldwRect@@@Z", self._cell_rect_cr)
        e.seam("?GetCellRect@ldwImageGrid@@QAEXHAAUldwRect@@@Z", self._cell_rect_i)
        e.seam("?GetColumnCount@ldwImageGrid@@QAEHXZ", lambda em: (self._entry(em.ecx).cols or 1, 0))
        e.seam("?GetWidth@ldwImage@@QAEHXZ", lambda em: (self._size(em.ecx)[0], 0))
        e.seam("?GetHeight@ldwImage@@QAEHXZ", lambda em: (self._size(em.ecx)[1], 0))

    # ---- pictures
    def picture(self, image_id: int) -> int:
        if image_id not in self.by_id:
            at = self.e.alloc(0x40)
            self.by_id[image_id] = at
            self.objects[at] = image_id
        return self.by_id[image_id]

    def _entry(self, obj: int) -> gp.Entry:
        return gp.entry_by_id(self.objects[obj])

    def _cells(self, obj: int) -> list:
        return gp.entry_cells(self.files, self._entry(obj))

    def _size(self, obj: int) -> tuple:
        rect = self._cells(obj)[0][1]
        entry = self._entry(obj)
        if entry.kind == "image":
            return rect[2], rect[3]
        return self.files.size(entry.files[0])

    def _write_rect(self, at: int, rect: tuple) -> None:
        for k, v in enumerate(rect):
            self.e.w32(at + 4 * k, v)

    def _cell_rect_cr(self, em):
        cols = self._entry(em.ecx).cols or 1
        self._write_rect(em.arg(2), self._cells(em.ecx)[em.sarg(1) * cols + em.sarg(0)][1])
        return 0, 12

    def _cell_rect_i(self, em):
        self._write_rect(em.arg(1), self._cells(em.ecx)[em.sarg(0)][1])
        return 0, 8

    # ---- recording
    def _rec(self, item, pop):
        self.draws.append(item)
        return 0, pop

    def _fill_floats(self, em):
        r = em.arg(0)
        self.draws.append(("fill", em.s32(r), em.s32(r + 4), em.s32(r + 8), em.s32(r + 12),
                           (em.farg(1), em.farg(2), em.farg(3), em.farg(4))))
        return 0, 20

    def _fill_colour(self, em):
        r, c = em.arg(0), em.arg(1)
        # ldwGameWindow::FillRect(rect, ldwColor) hands each byte / 255.0f to the float FillRect
        chans = [_f(struct.unpack("<I", struct.pack("<f", ((c >> s) & 0xFF) / 255.0))[0]) for s in (0, 8, 16, 24)]
        self.draws.append(("fill", em.s32(r), em.s32(r + 4), em.s32(r + 8), em.s32(r + 12), tuple(chans)))
        return 0, 8

    # ---- helpers for callers
    def vtable_object(self, size: int, slots: dict) -> int:
        """An object whose vtable slot k (a byte offset / 4) is the Python function slots[k](emu) -> (eax, pop)."""
        e = self.e
        table = e.alloc(4 * (max(slots) + 1))
        for k, fn in slots.items():
            name = f"__ui_rig_slot_{table:x}_{k}"
            e.seam(name, fn)
            e.w32(table + 4 * k, e.thunk_of[name])
        obj = e.alloc(size)
        e.w32(obj, table)
        return obj

    def run(self, name: str, args=(), ecx: int = 0) -> list:
        self.draws = []
        self.e.call(name, list(args), ecx=ecx)
        return self.draws


# ====================================================================== tips, the mouse pointer, the focus ring
def _xmm_seam(fn):
    """A seam for a C runtime function taking and returning a double in xmm0 (__libm_sse2_*_precise)."""
    from unicorn.x86_const import UC_X86_REG_XMM0

    def seam(em):
        raw = em.uc.reg_read(UC_X86_REG_XMM0) & ((1 << 64) - 1)
        x = struct.unpack("<d", struct.pack("<Q", raw))[0]
        em.uc.reg_write(UC_X86_REG_XMM0, struct.unpack("<Q", struct.pack("<d", fn(x)))[0])
        return 0, 0
    return seam


class TipRig:
    """theTipDialog::Init (with the real ldwButton) and DrawNoFadeScene. The font answers: the text is `text_w`
    wide on one line, `body_h` high justified, a line `line_h` high; the game window and the world view are
    `screen_w` wide. SetTiling, SetPos and AddControl are recorded; sin and cos are Python's."""

    def __init__(self, obj_dir: Path, game: Path):
        import math
        self.rig = rig = UiRig(obj_dir, game, ["theTipDialog", "ldwButton", "ldwTiledBackground", "ldwHintControl"])
        self.obj_dir = obj_dir
        e = self.e = rig.e
        for name, value in static_writes(obj_dir, "theGame", "?Init@theGame@@UAE_NXZ").items():
            if "mShadow" in name:
                e.w32(static_address(e, name), value)
        self.dialog = e.alloc(0x200)
        self.font = (400, 60, 20)
        self.screen_w = 1024
        self.seen: dict = {"controls": [], "decal": [], "setpos": None, "tiling": None}
        d = self.dialog

        def tiling(em):
            self.seen["tiling"] = (rig.objects[em.arg(0)], em.sarg(1), em.sarg(2))
            for k, v in enumerate((0, 0, em.sarg(1), em.sarg(2))):
                em.w32(d + 0x14 + 4 * k, v)
            return 0, 12

        e.seam("?GetFont@theStringManager@@QAEPAVldwFont@@W4FontId@@@Z", lambda em: (0, 4))
        e.seam("?GetLargeFont@theStringManager@@QAEPAVldwFont@@XZ", lambda em: (0, 0))
        e.seam("?GetWidth@ldwFont@@QAEHPBDM@Z", lambda em: (self.font[0], 8))
        e.seam("?GetJustifiedHeight@ldwFont@@QAEHPBDHM@Z", lambda em: (self.font[1], 12))
        e.seam("?GetHeight@ldwFont@@QAEHPBD@Z", lambda em: (self.font[2], 4))
        e.seam("?GetWidth@ldwGameWindow@@QAEHXZ", lambda em: (self.screen_w, 0))
        e.seam("?SetTiling@ldwTiledDialog@@IAEXPAVldwImageGrid@@HH@Z", tiling)
        e.seam("?GetImageGridForCanvas@theGraphicsManager@@QAEPAVldwImageGrid@@H@Z",
               lambda em: (rig.picture({1: 352, 2: 350}.get(em.arg(0), 351)), 4))
        e.seam("?GetTextColorForCanvas@theGraphicsManager@@QAE?AUldwColor@@H@Z", lambda em: (em.arg(0), 8))
        e.seam("?GetBounds@ldwScene@@QAEXAAUldwRect@@@Z", lambda em: (
            [em.w32(em.arg(0) + 4 * k, em.r32(d + 0x14 + 4 * k)) for k in range(4)], (0, 4))[1])
        e.seam("?SetPos@ldwTiledDialog@@IAEXHH@Z", lambda em: (
            self.seen.__setitem__("setpos", (em.sarg(0), em.sarg(1))), (0, 8))[1])
        e.seam("?SetSoundFx@ldwButton@@QAEXPAVldwSoundFx@@0@Z", lambda em: (0, 8))
        e.seam("?SetText@ldwButton@@QAEXPBDUldwColor@@11PAVldwFont@@@Z", lambda em: (0, 20))
        e.seam("?AddControl@ldwScene@@IAEXPAVldwControl@@@Z", lambda em: (
            self.seen["controls"].append(em.arg(0)), (0, 4))[1])
        e.seam("?IsLagging@ldwGameWindow@@QAE_NXZ", lambda em: (0, 0))
        e.seam("?GetSeconds@ldwEventManager@@SAIXZ", lambda em: (100, 0))
        e.seam("?GetNextJustifiedLine@ldwFont@@QAEPBDPBDPADHHAA_N_NM@Z", lambda em: (
            em.write(em.arg(1), b"\0"), (rig.empty, 28))[1])
        e.seam("?DrawStringJustified@ldwGameWindow@@QAEHPBDHHHUldwColor@@PAVldwFont@@_N3H@Z", lambda em: (0, 36))
        e.seam("__libm_sse2_sin_precise", _xmm_seam(math.sin))
        e.seam("__libm_sse2_cos_precise", _xmm_seam(math.cos))
        e.seam("?ShowArrow@CDecal@@QAEXPAVldwImage@@HH@Z", lambda em: (self.seen["decal"].append(
            (rig.objects[em.arg(0)], em.sarg(1), em.sarg(2))), (0, 12))[1])
        self.world_view = e.addr("?WorldView@@3VCWorldView@@A")

    def init(self, direction: int, x: int = 0, y: int = 0, string_id: int = 0x800, scene: int = 1,
             world: bool = False) -> None:
        """What the constructor sets, then Init(text, direction, x, y, world): string ids 0x845..0x86D are the
        tutorial instructions (+4Ch), `scene` the dialog's scene (+38h; 0 the play screen)."""
        e, d = self.e, self.dialog
        e.write(d, bytes(0x200))
        e.w32(d + 0x38, scene)
        e.write(d + 0x4C, bytes((int(0x845 <= string_id <= 0x86D),)))
        e.w32(d + 0x54, string_id)
        e.w32(d + 0x64, 2)
        e.w32(d + 0x74, 0xFF000000)
        e.w32(d + 0x7C, direction)
        e.write(d + 0x90, bytes((int(world),)))
        e.write(d + 0x9C, struct.pack("<d", -360.0))
        e.w32(d + 0xAC, 1)
        e.w32(self.world_view + 0x18, self.screen_w)
        self.seen.update(controls=[], decal=[], setpos=None, tiling=None)
        e.call("?Init@theTipDialog@@IAEXPBDW4ArrowDirection@@HH_N@Z", [e.string("Tip"), direction, x, y,
                                                                       int(world)], ecx=d)

    def arrow(self, phase: float) -> list:
        """DrawNoFadeScene at bob phase `phase` (degrees): its draws."""
        self.e.write(self.dialog + 0x9C, struct.pack("<d", phase))
        return self.rig.run("?DrawNoFadeScene@theTipDialog@@MAEXXZ", ecx=self.dialog)

    def box(self) -> list:
        """The box's backdrop as ldwTiledDialog makes it from SetTiling (at (0, 0)), then the OK button's draw."""
        grid, w, h = self.seen["tiling"]
        bg = self.e.alloc(0x40)
        self.e.call("??0ldwTiledBackground@@QAE@PAVldwImageGrid@@HH@Z", [self.rig.picture(grid), w, h], ecx=bg)
        draws = self.rig.run("?Draw@ldwTiledBackground@@UAEXUldwPoint@@M@Z", [0, 0, 1.0], ecx=bg)
        button = self.seen["controls"][-1]
        self.e.write(self.e.r32(button + 0x10) + 0x28, b"\x01")           # shown
        return draws + self.rig.run("?Draw@ldwButton@@UAEXXZ", ecx=button)


def pointer_draws(obj_dir: Path, image: object, hot: tuple, mouse: tuple) -> list:
    """ldwGameWindow::SetCursor(image, hot x, hot y), then ldwGameWindowImpl::Update with the mouse at `mouse`
    inside the window: the (image, x, y) of every ldwGameWindowImpl::Draw it makes."""
    e = pe.Emu(obj_dir, ["ldwGameWindow"])
    draws: list = []
    window, impl = e.alloc(0x10), e.alloc(0x100)
    e.w32(window, impl)
    e.w32(impl + 8, 1024)
    e.w32(impl + 0xC, 768)
    e.write(impl + 0x1E, b"\x01\x01\x00")                # the window has the mouse; a drawn pointer
    e.w32(impl + 0x30, e.alloc(0x40))
    e.seam("_SDL_ShowCursor", lambda em: (0, 0))
    e.seam("_SDL_GetMouseState", lambda em: (em.w32(em.arg(0), mouse[0]), em.w32(em.arg(1), mouse[1]), (0, 0))[2])
    e.seam("?Draw@ldwGameWindowImpl@@QAEXPAVldwImage@@HH@Z", lambda em: (
        draws.append((em.arg(0), em.sarg(1), em.sarg(2))), (0, 12))[1])
    for name in ("_SDL_GetTicks", "_SDL_Delay", "_SDL_UpdateTexture", "_SDL_RenderClear", "_SDL_RenderCopy",
                 "_SDL_RenderPresent", "_SDL_WarpMouseInWindow", "?Sleep@ldwEventManager@@SAXH@Z",
                 "?CheckForEvents@ldwGameWindowImpl@@AAEXXZ"):
        e.seam(name, lambda em: (0, 0))
    e.w32(impl + 0x50, 0xFFFFFFFF)                        # no mouse warp pending
    e.call("?SetCursor@ldwGameWindow@@QAEXPAVldwImage@@HH@Z", [image, hot[0], hot[1]], ecx=window)
    e.call("?Update@ldwGameWindowImpl@@QAEXXZ", ecx=impl)
    return draws


def focus_ring_draws(obj_dir: Path, game: Path, sex=0, head=0, body=0, age=30, frame=0, at=(0, 0)) -> list:
    """CVillagerManager::DrawVillager (vf2_people_emu.PeopleRig.house) for a villager the player has picked
    (CVillager+1BB85h set): its CSceneManager::Draw(image, point, alpha) draws of the ring, as
    ("focus_circle.png", x, y, alpha)."""
    rig = pe.PeopleRig(obj_dir, game)
    e = rig.e
    call = e.call

    def picked(name, args=(), ecx=0, floats=None):
        if isinstance(name, str) and name.startswith("?DrawVillager@CVillagerManager"):
            e.write(ecx + 0x387F5, b"\x01")
            rig.image_names[e.r32(ecx + 0x20)] = "focus_circle.png"
        return call(name, args, ecx, floats)

    e.call = picked
    try:
        draws = rig.house(sex, head, body, age, frame, 0, at=at)
    finally:
        e.call = call
    return [d[1:] for d in draws if d[0] == "scene_plain" and d[1] == "focus_circle.png"]


def blit(obj_dir: Path, pixels: bytes, width: int, height: int, rect: tuple, alpha: float,
         background: tuple = (40, 90, 160)) -> bytes:
    """ldwGameWindowImpl::BlitRectWithAlpha(source, 0, 0, rect, alpha, 1.0, false) onto an opaque screen as big as
    the rectangle, filled with `background`; R, G, B, A bytes in and out (the surfaces hold B, G, R, A)."""
    e = pe.Emu(obj_dir, ["ldwGameWindow"])
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
    left, top, right, bottom = rect
    sw, sh = right - left, bottom - top
    dst, dst_buf = surface(sw, sh, bgra((bytes(background) + b"\xff") * (sw * sh)), 0)
    impl = e.alloc(0x80)
    e.w32(impl + 8, sw)
    e.w32(impl + 0xC, sh)
    e.w32(impl + 0x30, dst)
    e.call("?BlitRectWithAlpha@ldwGameWindowImpl@@AAEXPAUSDL_Surface@@HHHHHHMM_N@Z",
           [src, 0, 0, left, top, right, bottom, float(alpha), 1.0, 0], ecx=impl)
    return bgra(e.read(dst_buf, sw * sh * 4))


# ====================================================================== reading the objects' code
_OBJECTS: dict = {}


def _object(obj_dir: Path, name: str) -> pe.CoffObject:
    key = (str(obj_dir), name)
    if key not in _OBJECTS:
        _OBJECTS[key] = pe.CoffObject(Path(obj_dir) / f"{name}.obj")
    return _OBJECTS[key]


def _functions(obj: pe.CoffObject):
    """(name, section, start, end, relocations {offset: symbol}) of every function of an object."""
    by_sect: dict = {}
    for name, value, sect, cls in obj.symbols.values():
        if sect > 0 and cls in (2, 3) and not name.startswith((".", "$")):
            by_sect.setdefault(sect, []).append((value, name))
    for sect, names in by_sect.items():
        s = obj.sections[sect - 1]
        if not s["chars"] & 0x20:
            continue
        names.sort()
        relocs = {va: obj.symbols[si][0] for va, si, _t in s["relocs"]}
        for k, (value, name) in enumerate(names):
            end = names[k + 1][0] if k + 1 < len(names) else s["size"]
            yield name, s, value, end, {va: t for va, t in relocs.items() if value <= va < end}


def _object_names(obj_dir: Path) -> list[str]:
    return sorted(p.stem for p in Path(obj_dir).glob("*.obj"))


def references(obj_dir: Path, text: str) -> list:
    """Every (object, function or data, symbol) whose code or data refers to a symbol containing `text`, outside
    the definitions' own exception-handling tables."""
    out = []
    for name in _object_names(obj_dir):
        obj = _object(obj_dir, name)
        for i, s in enumerate(obj.sections, 1):
            if s["name"].startswith(".debug"):
                continue
            owners = sorted((v, n) for n, v, sect, cls in obj.symbols.values()
                            if sect == i and cls in (2, 3) and not n.startswith((".", "$")))
            for va, si, _t in s["relocs"]:
                target = obj.symbols[si][0]
                if text in target:
                    owner = next((n for v, n in reversed(owners) if v <= va), "?")
                    out.append((name, owner, target))
    return out


def _disasm(obj: pe.CoffObject, s: dict, start: int, end: int):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    data = obj.data[s["ptr"] + start:s["ptr"] + end]
    return list(md.disasm(data, start))


IMAGE_CALLS = ("?GetImage@theGraphicsManager", "?GetImageGrid@theGraphicsManager", "?GetImageStrip@theGraphicsManager",
               "?Draw@theGraphicsManager", "?DrawCell@theGraphicsManager", "?DrawCentered@theGraphicsManager")


def image_sites(obj_dir: Path, image: int) -> set:
    """(object, function) of every call to theGraphicsManager's picture functions whose image argument (the last
    value pushed before the call) is the number `image`."""
    out = set()
    for name in _object_names(obj_dir):
        obj = _object(obj_dir, name)
        for fn, s, start, end, relocs in _functions(obj):
            if not any(t.startswith(IMAGE_CALLS) for t in relocs.values()):
                continue
            last = None
            for ins in _disasm(obj, s, start, end):
                if ins.mnemonic == "push":
                    last = ins.op_str
                elif ins.mnemonic == "call":
                    target = next((relocs[a] for a in range(ins.address, ins.address + ins.size) if a in relocs), "")
                    if target.startswith(IMAGE_CALLS):
                        try:
                            if int(last or "", 0) == image:
                                out.add((name, fn))
                        except ValueError:
                            pass
                    last = None
    return out


def member_reads(obj_dir: Path, obj_name: str, function: str) -> set:
    """The offsets [this + k] a function reads through the register holding `this` (ecx at entry, and every
    register it is copied to by "mov reg, ecx" before ecx changes)."""
    import capstone.x86 as x86
    obj = _object(obj_dir, obj_name)
    for fn, s, start, end, _relocs in _functions(obj):
        if fn != function:
            continue
        this = {"ecx"}
        out = set()
        for ins in _disasm(obj, s, start, end):
            ops = ins.op_str.split(", ")
            if ins.mnemonic == "mov" and len(ops) == 2 and ops[1] in this and ops[0] in ("edi", "esi", "ebx"):
                this.add(ops[0])
            for op in ins.operands:
                if op.type == x86.X86_OP_MEM and op.mem.base and ins.reg_name(op.mem.base) in this - {"ecx"} \
                        and op.mem.index == 0:
                    out.add(op.mem.disp)
        return out
    raise KeyError(function)


def image_stores(obj_dir: Path, obj_name: str, function: str) -> dict:
    """{member offset: image id} for each theGraphicsManager GetImage* call with an immediate image number whose
    result (eax) the function stores into [reg + offset] before its next call."""
    obj = _object(obj_dir, obj_name)
    for fn, s, start, end, relocs in _functions(obj):
        if fn != function:
            continue
        out, last, pending = {}, None, None
        for ins in _disasm(obj, s, start, end):
            ops = ins.op_str.split(", ")
            if ins.mnemonic == "push":
                last = ins.op_str
            elif ins.mnemonic == "call":
                target = next((relocs[a] for a in range(ins.address, ins.address + ins.size) if a in relocs), "")
                pending = None
                if target.startswith(IMAGE_CALLS[:3]):
                    try:
                        pending = int(last or "", 0)
                    except ValueError:
                        pending = None
                last = None
            elif pending is not None and ins.mnemonic == "mov" and len(ops) == 2 and ops[1] == "eax" \
                    and ops[0].startswith("dword ptr [") and "+ " in ops[0]:
                out[int(ops[0].split("+ ")[1].rstrip("]"), 0)] = pending
                pending = None
        return out
    raise KeyError(function)


def static_writes(obj_dir: Path, obj_name: str, function: str) -> dict:
    """{symbol: value} for each "mov dword ptr [symbol], immediate" a function makes."""
    obj = _object(obj_dir, obj_name)
    for fn, s, start, end, relocs in _functions(obj):
        if fn != function:
            continue
        out = {}
        for ins in _disasm(obj, s, start, end):
            target = next((relocs[a] for a in range(ins.address, ins.address + ins.size) if a in relocs), None)
            ops = ins.op_str.split(", ")
            if ins.mnemonic == "mov" and target and len(ops) == 2 and ops[0] == "dword ptr [0]":
                try:
                    out[target] = int(ops[1], 0)
                except ValueError:
                    pass
        return out
    raise KeyError(function)


def member_writes(obj_dir: Path, obj_name: str, function: str) -> dict:
    """{offset: set of immediates} for each "mov dword ptr [reg + offset], immediate" in a function."""
    obj = _object(obj_dir, obj_name)
    for fn, s, start, end, _relocs in _functions(obj):
        if fn != function:
            continue
        out: dict = {}
        for ins in _disasm(obj, s, start, end):
            ops = ins.op_str.split(", ")
            if ins.mnemonic == "mov" and len(ops) == 2 and ops[0].startswith("dword ptr [e") and "+ " in ops[0] \
                    and "*" not in ops[0]:
                try:
                    value = int(ops[1], 0)
                except ValueError:
                    continue
                out.setdefault(int(ops[0].split("+ ")[1].rstrip("]"), 0), set()).add(value)
        return out
    raise KeyError(function)


def tiling_calls(obj_dir: Path) -> dict:
    """{object: (width, height)} of each ldwTiledDialog::SetTiling call whose size is two immediates (the last
    such call in the object): the immediates pushed in the 14 instructions before it, less the image number
    pushed for a GetImageGrid / GetImageGridForCanvas call between."""
    out = {}
    for name in _object_names(obj_dir):
        obj = _object(obj_dir, name)
        for fn, s, start, end, relocs in _functions(obj):
            if not any("?SetTiling@ldwTiledDialog" in t for t in relocs.values()):
                continue
            code = _disasm(obj, s, start, end)
            for k, ins in enumerate(code):
                target = next((relocs[a] for a in range(ins.address, ins.address + ins.size) if a in relocs), "")
                if ins.mnemonic != "call" or "?SetTiling@ldwTiledDialog" not in target:
                    continue
                values = []
                window = code[max(0, k - 14):k]
                skip = set()                         # the image / canvas argument of a GetImageGrid* call
                for j, w in enumerate(window):
                    w_target = next((relocs[a] for a in range(w.address, w.address + w.size) if a in relocs), "")
                    if w.mnemonic == "call" and "GetImageGrid" in w_target:
                        pushes = [i for i in range(j) if window[i].mnemonic == "push"]
                        if pushes:
                            skip.add(pushes[-1])
                for j, w in enumerate(window):
                    if w.mnemonic != "push" or j in skip:
                        continue
                    try:
                        values.append(int(w.op_str, 0))
                    except ValueError:
                        continue
                if len(values) >= 2:
                    out[name] = (values[-1], values[-2])
    return out


def static_address(emu: pe.Emu, name: str) -> int:
    """A linked object's static or global, by name."""
    if name in emu.globals:
        return emu.globals[name]
    for obj in emu.objs:
        for sym, value, sect, _cls in obj.symbols.values():
            if sym == name and sect > 0 and sect in obj.addr:
                return obj.addr[sect] + value
    raise KeyError(name)


def called_symbols(obj_dir: Path, obj_name: str) -> set:
    """Every symbol an object's code refers to."""
    obj = _object(obj_dir, obj_name)
    return {t for _fn, _s, _a, _b, relocs in _functions(obj) for t in relocs.values()}


def as_layers(files: gp.GameFiles, draws: list) -> list:
    """Recorded draws as the picture's layers, as vf2_art_meters.layers makes them from its calls: each draw cut by
    the clipping (ldwGameWindowImpl::ClipRect's rule, itself checked against the game), draws cut to nothing left
    out; a whole picture is its cell 0; fills keep the floats."""
    import vf2_art_meters as am
    out, clip = [], None
    for d in draws:
        if d[0] == "clip":
            clip = d[1:5]
        elif d[0] == "unclip":
            clip = None
        elif d[0] == "draw":
            name, rect = gp.cell_of(files, d[1], max(0, d[2]))
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            part = am.clip_draw(d[3], d[4], w, h, clip)
            if part is None or part[4] <= 0 or part[5] <= 0:
                continue
            sx, sy, x, y, pw, ph = part
            out.append(("draw", name, (rect[0] + sx, rect[1] + sy, rect[0] + sx + pw, rect[1] + sy + ph), x, y,
                        round(d[5], 6)))
        elif d[0] == "fill":
            left, top, right, bottom = d[1:5]
            if clip is not None:
                left, top = max(left, clip[0]), max(top, clip[1])
                right, bottom = min(right, clip[2]), min(bottom, clip[3])
            if right > left and bottom > top:
                out.append(("fill", left, top, right - left, bottom - top, am.fill_rgba(d[5])))
        else:
            out.append(d)
    return out


def art_layers(art) -> list:
    """An Art's layers in as_layers' form."""
    out = []
    for layer in art.layers:
        if isinstance(layer, gp.Fill):
            out.append(("fill", layer.x, layer.y, layer.w, layer.h, tuple(layer.rgba)))
        else:
            out.append(("draw", layer.file, tuple(layer.rect), layer.x, layer.y, round(layer.alpha, 6)))
    return out
