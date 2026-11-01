"""Run the game's own picture-cutting and meter code from the B200 desktop objects (unicorn), for the Picture
Maker's "All game pictures" (src/vf2_game_pictures.py).

* theGraphicsManagerImpl::GetImage(id) runs whole over the object's own ImageList: GetImageEntry, the choice of
  ldwImage / ldwImageStrip / ldwImageGrid, and ldwImageGrid's two constructors (sprintf "%s%d%d%s" for a grid over
  several files). The pictures themselves are seams: ldwImageImpl(file) remembers the file, GetWidth / GetHeight
  answer the real file's size. Then ldwImageGrid::GetCellRect(column, row) gives every cell's rectangle and the file
  it is in (the grid's +4 after the call).
* theContinuousVariableMeter, theSlicedVariableMeter and theVariableMeter's DrawPercentMeter run whole; their
  Draw, SetClipping, ResetClipping and FillRect calls are recorded.
* ldwGameWindowImpl::ClipRect runs whole on a rectangle and a clipping rectangle.

Nothing here starts the game or writes a file.
"""
from __future__ import annotations

import struct
from pathlib import Path

from unicorn.x86_const import UC_X86_REG_EAX

import vf2_people_emu as pe


def _f(v: int) -> float:
    return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]


class ImageRig:
    OBJECTS = ["theGraphicsManager", "ldwImage"]

    def __init__(self, obj_dir: Path, images: Path):
        self.images = Path(images)
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.impl_path: dict[int, str] = {}
        e.seam("??2@YAPAXI@Z", lambda em: (em.alloc(max(4, em.arg(0))), 0))
        e.seam("??_U@YAPAXI@Z", lambda em: (em.alloc(max(4, em.arg(0))), 0))
        e.seam("??0ldwImageImpl@@QAE@PBD@Z", self._impl)
        e.seam("?GetWidth@ldwImageImpl@@QAEHXZ", lambda em: (self._size(em.ecx)[0], 0))
        e.seam("?GetHeight@ldwImageImpl@@QAEHXZ", lambda em: (self._size(em.ecx)[1], 0))
        e.seam("_sprintf", self._sprintf)
        # the cookie check returns with eax untouched (the multi-file constructor returns `this` through it)
        e.seam("@__security_check_cookie@4", lambda em: (em.uc.reg_read(UC_X86_REG_EAX), 0))
        self.manager = e.alloc(0x40)

    def _impl(self, em):
        self.impl_path[em.ecx] = em.cstr(em.arg(0))
        return em.ecx, 4

    def _size(self, impl: int) -> tuple:
        path = self.images / self.impl_path[impl]
        head = path.read_bytes()[:24]
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])
        import vf2_game_pictures as gp
        p = gp.load_picture(path)
        return p.width, p.height

    def _sprintf(self, em):
        out, fmt = em.arg(0), em.cstr(em.arg(1))
        args = [em.arg(2 + k) for k in range(4)]
        text, k, i = "", 0, 0
        while i < len(fmt):
            if fmt[i] == "%":
                code = fmt[i + 1]
                text += em.cstr(args[k]) if code == "s" else str(args[k] - (1 << 32) if args[k] >> 31 else args[k])
                k += 1
                i += 2
            else:
                text += fmt[i]
                i += 1
        em.write(out, text.encode("latin-1") + b"\0")
        return len(text), 0

    def cells(self, image_id: int, kind: str, count: int) -> list:
        """GetImage(id), then every cell's (file, rect) as GetCellRect gives it ("image": the whole file)."""
        e = self.e
        obj = e.call("?GetImage@theGraphicsManagerImpl@@QAEPAVldwImage@@H@Z", [image_id], ecx=self.manager)
        if not obj:
            raise pe.EmuError(f"GetImage({image_id}) gave nothing")
        if kind == "image":
            impl = e.r32(obj + 4)
            w, h = self._size(impl)
            return [(self.impl_path[impl], (0, 0, w, h))]
        cols = e.s32(obj + 8)
        rect = e.alloc(16)
        out = []
        for i in range(count):
            e.call("?GetCellRect@ldwImageGrid@@QAEXHHAAUldwRect@@@Z", [i % cols, i // cols, rect], ecx=obj)
            out.append((self.impl_path[e.r32(obj + 4)], tuple(e.s32(rect + 4 * k) for k in range(4))))
        return out


class MeterRig:
    OBJECTS = ["theVariableMeter", "theSlicedVariableMeter", "theContinuousVariableMeter", "ldwGameWindow"]
    NAMES = {
        "variable": ("??0theVariableMeter@@QAE@XZ", "?DrawPercentMeter@theVariableMeter@@QAEXW4MeterColorEnum@@HHH@Z"),
        "sliced": ("??0theSlicedVariableMeter@@QAE@XZ",
                   "?DrawPercentMeter@theSlicedVariableMeter@@QAEXW4SlMeterColorEnum@@H@Z"),
        "continuous": ("??0theContinuousVariableMeter@@QAE@XZ",
                       "?DrawPercentMeter@theContinuousVariableMeter@@QAEXW4COMeterColorEnum@@H@Z"),
    }

    def __init__(self, obj_dir: Path):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.images: dict[int, int] = {}
        self.calls: list = []
        gm = e.alloc(16)
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (gm, 0))
        e.seam("?Get@theGameState@@SAPAV1@XZ", lambda em: (0x6000, 0))
        e.seam("?GetImage@theGraphicsManager@@QAEPAVldwImage@@W4EImage@@@Z", self._image)
        e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z", self._image)
        e.seam("?GetWideScreenOffsetX@theGameState@@QAEHXZ", lambda em: (0, 0))
        e.seam("?Draw@ldwGameWindow@@QAEXPAVldwImage@@HH@Z", self._draw)
        e.seam("?SetClipping@ldwGameWindow@@QAEXUldwRect@@@Z", self._clip)
        e.seam("?ResetClipping@ldwGameWindow@@QAEXXZ", lambda em: (self.calls.append(("unclip",)), (0, 0))[1])
        e.seam("?FillRect@ldwGameWindow@@QAEXAAUldwRect@@MMMM@Z", self._fill)
        self.meters = {}
        for name, (ctor, _draw) in self.NAMES.items():
            self.meters[name] = e.alloc(0x100)
            e.call(ctor, ecx=self.meters[name])

    def _image(self, em):
        image_id = em.arg(0)
        if image_id not in self.images:
            self.images[image_id] = em.alloc(16)
        return self.images[image_id], 4

    def _id(self, address: int) -> int:
        return next(k for k, v in self.images.items() if v == address)

    def _draw(self, em):
        self.calls.append(("draw", self._id(em.arg(0)), em.sarg(1), em.sarg(2)))
        return 0, 12

    def _clip(self, em):
        self.calls.append(("clip", em.sarg(0), em.sarg(1), em.sarg(2), em.sarg(3)))
        return 0, 16

    def _fill(self, em):
        r = em.arg(0)
        self.calls.append(("fill", em.s32(r), em.s32(r + 4), em.s32(r + 8), em.s32(r + 12),
                           _f(em.arg(1)), _f(em.arg(2)), _f(em.arg(3)), _f(em.arg(4))))
        return 0, 20

    def draw(self, which: str, colour: int, level: int, x: int = 100, y: int = 200) -> list:
        self.calls = []
        args = [colour, x, y, level] if which == "variable" else [colour, level]
        self.e.call(self.NAMES[which][1], args, ecx=self.meters[which])
        return self.calls

    def clip_rect(self, x: int, y: int, w: int, h: int, clip: tuple):
        """ldwGameWindowImpl::ClipRect(source rect (0, 0, w, h), x, y) with the clipping rectangle `clip`:
        None when nothing is drawn, else (source left, source top, x, y, width, height)."""
        e = self.e
        impl = e.alloc(0x80)
        for k, v in enumerate(clip):
            e.w32(impl + 0x60 + 4 * k, v)
        src, px, py = e.alloc(16), e.alloc(4), e.alloc(4)
        for k, v in enumerate((0, 0, w, h)):
            e.w32(src + 4 * k, v)
        e.w32(px, x)
        e.w32(py, y)
        ok = e.call("?ClipRect@ldwGameWindowImpl@@AAE_NAAUldwRect@@AAH1@Z", [src, px, py], ecx=impl) & 0xFF
        if not ok:
            return None
        left, top, right, bottom = (e.s32(src + 4 * k) for k in range(4))
        return left, top, e.s32(px), e.s32(py), right - left, bottom - top
