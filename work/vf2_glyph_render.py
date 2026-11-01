"""Draw one character with a Windows font through GDI, the way the Unicode Text companion DLL draws it in the game.

The game's four fonts (Images\\Segoe24.png, Segoe24Bold.png, Segoe32Bold.png, Segoe36Bold.png) are Segoe UI drawn
white on a clear sheet with 16 levels of grey anti-aliasing. A character none of them has is drawn here with GDI,
white on black, ANTIALIASED_QUALITY (grey, never ClearType), at the size and weight fitted to that game font
(src/vf2_game_fonts.json "gdi"), and the grey level becomes the alpha of a white pixel through that font's
own grey -> alpha table ("alpha": for each grey level GDI gives, the sheet's alpha it most often is). runtime/native/b200unicode does exactly the same calls in the game (the same font, the same height,
weight and quality, the same ExtTextOutW position), so the patcher's preview and the game agree.

Which font draws a character: the first in FALLBACK_CHAIN whose own character map ("cmap" table, read with
GetFontData, formats 4 and 12, so characters beyond U+FFFF count too) has it; it is drawn by glyph number
(ETO_GLYPH_INDEX), so those characters draw too. None has it: the missing-glyph box.

Standard library only (ctypes). On a system without GDI (not Windows) nothing can be drawn and `available()` is False.
"""
from __future__ import annotations

import ctypes
import struct
import sys
from functools import lru_cache

# The order the DLL tries, after the game font and the patcher-made glyphs (the owner's list).
FALLBACK_CHAIN = (
    "Segoe UI", "Segoe UI Historic", "Segoe UI Symbol", "Segoe UI Emoji",
    "Microsoft YaHei UI", "Microsoft JhengHei UI", "Yu Gothic UI", "Malgun Gothic", "SimSun-ExtB",
    "Nirmala UI", "Ebrima", "Gadugi", "Leelawadee UI", "Javanese Text", "Myanmar Text", "Mongolian Baiti",
    "Microsoft Himalaya", "Microsoft New Tai Lue", "Microsoft Tai Le", "Microsoft Yi Baiti", "Sylfaen",
    "Noto Sans", "Noto Sans CJK SC", "Noto Sans Symbols", "Noto Sans Symbols 2", "Noto Sans Cuneiform",
)

ANTIALIASED_QUALITY = 4
FW_NORMAL, FW_BOLD = 400, 700


class GlyphRenderError(RuntimeError):
    pass


def available() -> bool:
    return sys.platform == "win32"


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


class _TEXTMETRICW(ctypes.Structure):
    _fields_ = [("tmHeight", ctypes.c_int32), ("tmAscent", ctypes.c_int32), ("tmDescent", ctypes.c_int32),
                ("tmInternalLeading", ctypes.c_int32), ("tmExternalLeading", ctypes.c_int32),
                ("tmAveCharWidth", ctypes.c_int32), ("tmMaxCharWidth", ctypes.c_int32),
                ("tmWeight", ctypes.c_int32), ("tmOverhang", ctypes.c_int32),
                ("tmDigitizedAspectX", ctypes.c_int32), ("tmDigitizedAspectY", ctypes.c_int32),
                ("tmFirstChar", ctypes.c_wchar), ("tmLastChar", ctypes.c_wchar), ("tmDefaultChar", ctypes.c_wchar),
                ("tmBreakChar", ctypes.c_wchar), ("tmItalic", ctypes.c_ubyte), ("tmUnderlined", ctypes.c_ubyte),
                ("tmStruckOut", ctypes.c_ubyte), ("tmPitchAndFamily", ctypes.c_ubyte), ("tmCharSet", ctypes.c_ubyte)]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_int32), ("cy", ctypes.c_int32)]


class _ABC(ctypes.Structure):
    _fields_ = [("abcA", ctypes.c_int32), ("abcB", ctypes.c_uint32), ("abcC", ctypes.c_int32)]


ETO_GLYPH_INDEX = 0x0010


def _gdi():
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    vp = ctypes.c_void_p
    gdi.CreateCompatibleDC.restype = vp
    gdi.CreateCompatibleDC.argtypes = [vp]
    gdi.DeleteDC.argtypes = [vp]
    gdi.CreateDIBSection.restype = vp
    gdi.CreateDIBSection.argtypes = [vp, vp, ctypes.c_uint, ctypes.POINTER(vp), vp, ctypes.c_uint32]
    gdi.SelectObject.restype = vp
    gdi.SelectObject.argtypes = [vp, vp]
    gdi.DeleteObject.argtypes = [vp]
    gdi.CreateFontW.restype = vp
    gdi.CreateFontW.argtypes = [ctypes.c_int] * 5 + [ctypes.c_uint32] * 8 + [ctypes.c_wchar_p]
    gdi.SetTextColor.argtypes = [vp, ctypes.c_uint32]
    gdi.SetBkColor.argtypes = [vp, ctypes.c_uint32]
    gdi.SetBkMode.argtypes = [vp, ctypes.c_int]
    gdi.SetTextAlign.argtypes = [vp, ctypes.c_uint]
    gdi.ExtTextOutW.argtypes = [vp, ctypes.c_int, ctypes.c_int, ctypes.c_uint, vp, vp, ctypes.c_uint, vp]
    gdi.GetTextMetricsW.argtypes = [vp, ctypes.POINTER(_TEXTMETRICW)]
    gdi.GetTextExtentPoint32W.argtypes = [vp, ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(_SIZE)]
    gdi.GetFontData.restype = ctypes.c_uint32
    gdi.GetFontData.argtypes = [vp, ctypes.c_uint32, ctypes.c_uint32, vp, ctypes.c_uint32]
    gdi.GdiFlush.restype = ctypes.c_int
    gdi.GetCharABCWidthsI.argtypes = [vp, ctypes.c_uint, ctypes.c_uint, vp, ctypes.POINTER(_ABC)]
    gdi.GetTextFaceW.argtypes = [vp, ctypes.c_int, ctypes.c_wchar_p]
    return gdi


@lru_cache(maxsize=1)
def _api():
    if not available():
        raise GlyphRenderError("drawing a character needs Windows (GDI)")
    return _gdi()


def _font(face: str, height: int, weight: int):
    gdi = _api()
    # CreateFontW(height, width, escapement, orientation, weight, italic, underline, strikeout, charset,
    #             out precision, clip precision, quality, pitch and family, face)
    return gdi.CreateFontW(-int(height), 0, 0, 0, int(weight), 0, 0, 0, 1, 0, 0, ANTIALIASED_QUALITY, 0, face)


class _Canvas:
    """A memory DC with a 32-bit top-down DIB, white text on black, the font selected."""

    def __init__(self, width: int, height: int, face: str, px: int, weight: int):
        gdi = _api()
        self.gdi, self.width, self.height = gdi, width, height
        self.dc = gdi.CreateCompatibleDC(None)
        bmi = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        self.bitmap = gdi.CreateDIBSection(self.dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        if not self.bitmap:
            gdi.DeleteDC(self.dc)
            raise GlyphRenderError("GDI could not make a drawing surface")
        self.bits = bits.value
        self.old_bitmap = gdi.SelectObject(self.dc, self.bitmap)
        self.font = _font(face, px, weight)
        self.old_font = gdi.SelectObject(self.dc, self.font)
        gdi.SetTextColor(self.dc, 0x00FFFFFF)
        gdi.SetBkColor(self.dc, 0)
        gdi.SetBkMode(self.dc, 2)                 # OPAQUE
        gdi.SetTextAlign(self.dc, 0)              # TA_TOP | TA_LEFT

    def metrics(self) -> _TEXTMETRICW:
        tm = _TEXTMETRICW()
        self.gdi.GetTextMetricsW(self.dc, ctypes.byref(tm))
        return tm

    def face(self) -> str:
        buf = ctypes.create_unicode_buffer(64)
        self.gdi.GetTextFaceW(self.dc, 64, buf)
        return buf.value

    def extent(self, text: str) -> int:
        size = _SIZE()
        self.gdi.GetTextExtentPoint32W(self.dc, text, len(text), ctypes.byref(size))
        return size.cx

    def draw(self, text: str, x: int, y: int) -> bytes:
        ctypes.memset(self.bits, 0, self.width * self.height * 4)
        buf = ctypes.create_unicode_buffer(text)
        self.gdi.ExtTextOutW(self.dc, int(x), int(y), 0, None, buf, len(text), None)
        self.gdi.GdiFlush()
        return ctypes.string_at(self.bits, self.width * self.height * 4)

    def font_table(self, tag: bytes) -> bytes:
        t = struct.unpack("<I", tag)[0]
        n = self.gdi.GetFontData(self.dc, t, 0, None, 0)
        if n in (0, 0xFFFFFFFF):
            return b""
        buf = ctypes.create_string_buffer(n)
        if self.gdi.GetFontData(self.dc, t, 0, buf, n) != n:
            return b""
        return buf.raw

    def close(self) -> None:
        gdi = self.gdi
        gdi.SelectObject(self.dc, self.old_font)
        gdi.SelectObject(self.dc, self.old_bitmap)
        gdi.DeleteObject(self.font)
        gdi.DeleteObject(self.bitmap)
        gdi.DeleteDC(self.dc)


class Cmap:
    """A font's Unicode character map ("cmap" table, read with GetFontData): format 12 (all of Unicode, preferred)
    or format 4 (U+0000..U+FFFF). glyph(cp) is the glyph number, 0 = the font does not have it. The DLL parses
    the same subtables the same way (b200unicode_glyphs.h)."""

    def __init__(self, table: bytes):
        self.groups: list = []          # (first, last, glyph of first) for format 12 and format 4 delta segments
        self.single: dict = {}          # format 4 segments that use the glyph array
        self._parse(table)
        self.groups.sort()
        self._starts = [g[0] for g in self.groups]

    def _parse(self, table: bytes) -> None:
        if len(table) < 4:
            return
        _ver, count = struct.unpack_from(">HH", table, 0)
        best4 = best12 = None
        for k in range(count):
            if 4 + 8 * k + 8 > len(table):
                break
            pid, eid, off = struct.unpack_from(">HHI", table, 4 + 8 * k)
            if off + 2 > len(table) or not (pid == 0 or (pid == 3 and eid in (1, 10))):
                continue
            fmt = struct.unpack_from(">H", table, off)[0]
            if fmt == 12 and best12 is None:
                best12 = off
            elif fmt == 4 and best4 is None:
                best4 = off
        if best12 is not None and best12 + 16 <= len(table):
            n = struct.unpack_from(">I", table, best12 + 12)[0]
            for k in range(n):
                at = best12 + 16 + 12 * k
                if at + 12 > len(table):
                    break
                first, last, glyph = struct.unpack_from(">III", table, at)
                if first <= last:
                    self.groups.append((first, last, glyph))
            return
        if best4 is None or best4 + 14 > len(table):
            return
        off = best4
        segx2 = struct.unpack_from(">H", table, off + 6)[0]
        ends = off + 14
        starts = ends + segx2 + 2
        deltas = starts + segx2
        offsets = deltas + segx2
        if offsets + segx2 > len(table):
            return
        for k in range(segx2 // 2):
            end = struct.unpack_from(">H", table, ends + 2 * k)[0]
            start = struct.unpack_from(">H", table, starts + 2 * k)[0]
            delta = struct.unpack_from(">h", table, deltas + 2 * k)[0]
            ro = struct.unpack_from(">H", table, offsets + 2 * k)[0]
            if start > end or start == 0xFFFF:
                continue
            if ro == 0:
                for c in range(start, end + 1):
                    self.single[c] = (c + delta) & 0xFFFF
                continue
            for c in range(start, end + 1):
                at = offsets + 2 * k + ro + 2 * (c - start)
                g = struct.unpack_from(">H", table, at)[0] if at + 2 <= len(table) else 0
                self.single[c] = (g + delta) & 0xFFFF if g else 0

    def glyph(self, cp: int) -> int:
        if cp in self.single:
            return self.single[cp]
        import bisect
        i = bisect.bisect_right(self._starts, cp) - 1
        if i >= 0:
            first, last, g = self.groups[i]
            if first <= cp <= last:
                return g + (cp - first)
        return 0


@lru_cache(maxsize=None)
def cmap(face: str, weight: int = FW_NORMAL) -> Cmap:
    """The character map of the installed font `face` at `weight` (a bold face can be another font of the same
    collection, with other glyph numbers); empty when Windows gives another font for that name."""
    if not available():
        return Cmap(b"")
    c = _Canvas(4, 4, face, 16, weight)
    try:
        if c.face().lower() != face.lower():
            return Cmap(b"")
        return Cmap(c.font_table(b"cmap"))
    finally:
        c.close()


def has(face: str, cp: int) -> bool:
    return cmap(face).glyph(cp) != 0


def font_for(cp: int, chain=FALLBACK_CHAIN) -> str | None:
    for face in chain:
        if has(face, cp):
            return face
    return None


IGNORABLE = (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF)


def _ignorable(cp: int) -> bool:
    return cp in IGNORABLE or 0xFE00 <= cp <= 0xFE0F or 0xE0000 <= cp <= 0xE0FFF


@lru_cache(maxsize=4096)
def render(text: str, face: str, px: int, weight: int, cell_height: int, top: int) -> tuple:
    """`text` (one character: a cluster) drawn with `face` at pixel height px, glyph by glyph by glyph number
    (ExtTextOutW with ETO_GLYPH_INDEX, so characters beyond U+FFFF draw too): each code point the face has is
    drawn at the pen and moves it by its advance (GetCharABCWidthsI: a + b + c); joiners, variation selectors and
    tags draw nothing; a code point the face lacks is left out. The canvas is 10 x px wide (the pen starts
    at x = px) and cell_height tall, the text's top at `top`.

    Returns (advance, grey bytes of width x cell_height, width, the pen's start x). The DLL does the same calls."""
    width = 10 * max(1, int(px))
    cm = cmap(face, weight)
    glyphs = [cm.glyph(ord(ch)) for ch in text if not _ignorable(ord(ch))]
    glyphs = [g for g in glyphs if g]
    c = _Canvas(width, cell_height, face, px, weight)
    try:
        ctypes.memset(c.bits, 0, width * cell_height * 4)
        pen = int(px)
        for g in glyphs:
            arr = (ctypes.c_uint16 * 1)(g)
            c.gdi.ExtTextOutW(c.dc, pen, int(top), ETO_GLYPH_INDEX, None, arr, 1, None)
            abc = _ABC()
            c.gdi.GetCharABCWidthsI(c.dc, g, 1, None, ctypes.byref(abc))
            pen += abc.abcA + abc.abcB + abc.abcC
        c.gdi.GdiFlush()
        raw = ctypes.string_at(c.bits, width * cell_height * 4)
    finally:
        c.close()
    # white text on black with grey anti-aliasing: the three channels are equal; the green one is the grey
    return pen - int(px), bytes(raw[1::4]), width, int(px)
