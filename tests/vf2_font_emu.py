"""Run the game's own font and text code from the B200 desktop object files (unicorn).

The objects (work/desktop_obj_files, or VF2_DESKTOP_OBJ_DIR; gitignored) keep their symbols. tests/vf2_people_emu.Emu
links them into one address space; everything they do not define is a Python seam. This runs, for real:

* the four font constructors (Segoe24, Segoe24Bold, Segoe32Bold, Segoe36Bold): ldwFont::Load and
  ldwFontImpl::Load lay the glyph table out on the sheet and build the 256-entry byte -> glyph map;
* ldwFontImpl::GetCharSourceRect, ldwFont::GetWidth (both), ldwFont::GetHeight, ldwFont::GetNextJustifiedLine;
* ldwGameWindowImpl::DrawString and ldwGameWindowImpl::DrawChars, whose SDL_UpperBlit / BlitRectWithAlpha calls are
  seams that record each glyph blit (source rectangle and screen position).

src/vf2_game_fonts.json (the patcher's copy of the fonts' metrics) is made from these answers, and the tests compare
the patcher's own text drawing (src/vf2_game_text.py) with these calls, glyph by glyph. Nothing here starts the
game or writes a file.
"""
from __future__ import annotations

import struct
from pathlib import Path

from vf2_people_emu import Emu, png_size

FONT_CLASSES = ("Segoe24", "Segoe24Bold", "Segoe32Bold", "Segoe36Bold")
OBJECTS = ["ldwFont", "ldwFontImpl", "ldwGameWindow", *FONT_CLASSES]

SURFACE_SIZE = 0x40             # a fake SDL_Surface: +08 w, +0C h (all the font code reads)
SCREEN_W, SCREEN_H = 4096, 4096


class FontRig:
    """The font objects linked; every font constructed from the game folder's Images (only the PNG sizes are read)."""

    def __init__(self, obj_dir: Path, images: Path):
        self.images = Path(images)
        self.e = e = Emu(Path(obj_dir), OBJECTS)
        self.surfaces: dict[int, str] = {}
        self.blits: list = []
        e.seam("??2@YAPAXI@Z", lambda em: (em.alloc(em.arg(0)), 0))
        e.seam("??3@YAXPAXI@Z", lambda em: (0, 0))
        e.seam("_strchr", self._strchr)
        e.seam("?Exists@ldwImage@@SA_NPBD@Z", lambda em: (1, 0))
        e.seam("??0ldwImageImpl@@QAE@PBD@Z", self._image_ctor)
        e.seam("?GetGraphic@ldwImageImpl@@QAEPAUSDL_Surface@@XZ", lambda em: (em.r32(em.ecx), 0))
        e.seam("_SDL_UpperBlit", self._upper_blit)
        e.seam("?BlitRectWithAlpha@ldwGameWindowImpl@@AAEXPAUSDL_Surface@@HHHHHHMM_N@Z", self._alpha_blit)
        e.seam("?GetImage@ldwFontImpl@@QAEPAUSDL_Surface@@UldwColor@@@Z", self._get_image)
        e.seam("_sprintf", self._sprintf)
        # __security_check_cookie returns with eax untouched (DrawChars returns its advance through it)
        from unicorn.x86_const import UC_X86_REG_EAX
        e.seam("@__security_check_cookie@4", lambda em: (em.uc.reg_read(UC_X86_REG_EAX), 0))
        self.fonts: dict[str, int] = {}
        for name in FONT_CLASSES:
            obj = e.alloc(0x10)
            e.call(f"??0{name}@@QAE@XZ", ecx=obj)
            self.fonts[name] = obj
        # a ldwGameWindowImpl: +30h the screen surface, +5Ch the default font, +60h..+6Ch the clip rectangle
        self.window = e.alloc(0x100)
        self.screen = e.alloc(SURFACE_SIZE)
        e.w32(self.window + 0x30, self.screen)
        e.w32(self.window + 0x60, 0)
        e.w32(self.window + 0x64, 0)
        e.w32(self.window + 0x68, SCREEN_W)
        e.w32(self.window + 0x6C, SCREEN_H)

    # ---------------------------------------------------------------- seams
    def _strchr(self, em):
        s, c = em.arg(0), em.arg(1) & 0xFF
        k = 0
        while True:
            b = em.read(s + k, 1)[0]
            if b == c:
                return s + k, 0
            if not b:
                return 0, 0
            k += 1

    def _image_ctor(self, em):
        this, path = em.ecx, em.cstr(em.arg(0))
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        w, h = png_size(self.images / name)
        surf = em.alloc(SURFACE_SIZE)
        em.w32(surf + 8, w)
        em.w32(surf + 0xC, h)
        em.w32(this, surf)
        self.surfaces[surf] = name
        return this, 4

    def _get_image(self, em):
        impl = em.ecx
        return em.r32(em.r32(impl + 0xC)), 4

    def _sprintf(self, em):
        out, fmt, v = em.arg(0), em.cstr(em.arg(1)), em.sarg(2)
        text = (fmt % v).encode("latin-1") + b"\0"
        em.write(out, text)
        return len(text) - 1, 0

    def _upper_blit(self, em):
        src = em.arg(1)
        dst = em.arg(3)
        l, t, w, h = struct.unpack("<iiii", em.read(src, 16))
        x, y = struct.unpack("<ii", em.read(dst, 8))
        self.blits.append(("blit", (l, t, l + w, t + h), x, y, 1.0))
        return 0, 0

    def _alpha_blit(self, em):
        x, y, l, t, r, b = (em.sarg(k) for k in range(1, 7))
        self.blits.append(("alpha", (l, t, r, b), x, y, round(em.farg(7), 6)))
        return 0, 0x24

    # ---------------------------------------------------------------- the fonts
    def table(self, name: str) -> dict:
        """The font as ldwFontImpl::Load left it: line height, kerning, sheet size, glyph rectangles, byte map."""
        e = self.e
        impl = e.r32(self.fonts[name] + 4)
        table = e.r32(impl + 0x10)
        glyphs = []
        k = 0
        while True:
            ch, l, t, r, b = struct.unpack("<iiiii", e.read(table + 20 * k, 20))
            if ch == 0:
                break
            glyphs.append([ch, l, t, r, b])
            k += 1
        charmap = list(struct.unpack("<256i", e.read(impl + 0x1C, 1024)))
        return {"line_height": e.s32(impl + 4), "kerning": e.s32(impl + 8),
                "sheet": [e.s32(impl + 0x14), e.s32(impl + 0x18)],
                "image": self.surfaces[e.r32(e.r32(impl + 0xC))], "glyphs": glyphs, "charmap": charmap}

    def source_rect(self, name: str, ch: int) -> tuple:
        e = self.e
        impl = e.r32(self.fonts[name] + 4)
        rect = e.alloc(16)
        e.call("?GetCharSourceRect@ldwFontImpl@@UAEXHAAUldwRect@@@Z", (ch, rect), ecx=impl)
        return struct.unpack("<iiii", e.read(rect, 16))

    def _bytes(self, raw: bytes) -> int:
        at = self.e.alloc(len(raw) + 1)
        self.e.write(at, raw + b"\0")
        return at

    def width(self, name: str, raw: bytes, scale: float = 1.0) -> int:
        v = self.e.call("?GetWidth@ldwFont@@QAEHPBDM@Z", (self._bytes(raw), scale), ecx=self.fonts[name])
        return v - (1 << 32) if v & 0x80000000 else v

    def height(self, name: str, raw: bytes) -> int:
        return self.e.call("?GetHeight@ldwFont@@QAEHPBD@Z", (self._bytes(raw),), ecx=self.fonts[name])

    def next_line(self, name: str, raw: bytes, max_chars: int, max_width: int, keep: bool = True,
                  scale: float = 1.0) -> tuple[bytes, int, bool]:
        """GetNextJustifiedLine: (the line it wrote, bytes consumed, the newline flag)."""
        e = self.e
        src = self._bytes(raw)
        out = e.alloc(len(raw) + 0x400)
        flag = e.alloc(4)
        e.w32(flag, 0)
        end = e.call("?GetNextJustifiedLine@ldwFont@@QAEPBDPBDPADHHAA_N_NM@Z",
                     (src, out, max_chars, max_width, flag, 1 if keep else 0, scale), ecx=self.fonts[name])
        line = b""
        k = 0
        while True:
            c = e.read(out + k, 1)[0]
            if not c:
                break
            line += bytes([c])
            k += 1
        return line, (end - src) if end else -1, bool(e.read(flag, 1)[0])

    def draw_string(self, name: str, raw: bytes, x: int, y: int, rgba=(255, 255, 255, 255)) -> list:
        """ldwGameWindowImpl::DrawString: every glyph blit it makes, in order."""
        self.blits = []
        color = rgba[0] | rgba[1] << 8 | rgba[2] << 16 | rgba[3] << 24
        self.e.call("?DrawString@ldwGameWindowImpl@@QAEXPBDHHUldwColor@@PAVldwFont@@@Z",
                    (self._bytes(raw), x, y, color, self.fonts[name]), ecx=self.window)
        return list(self.blits)

    def draw_chars(self, name: str, raw: bytes, count: int, x: int, y: int, rgba=(255, 255, 255, 255)) -> tuple:
        """ldwGameWindowImpl::DrawChars(text, count, x, y, false, colour, font): (advance it returns, blits)."""
        self.blits = []
        color = rgba[0] | rgba[1] << 8 | rgba[2] << 16 | rgba[3] << 24
        v = self.e.call("?DrawChars@ldwGameWindowImpl@@QAEHPBDHHH_NUldwColor@@PAVldwFont@@@Z",
                        (self._bytes(raw), count, x, y, 0, color, self.fonts[name]), ecx=self.window)
        return (v - (1 << 32) if v & 0x80000000 else v), list(self.blits)
