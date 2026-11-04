"""Colour emoji, drawn by Windows' DirectWrite and Direct2D: the Game Text preview's copy of what the Unicode text DLL
does in the game (runtime/native/b200unicode/b200colour.inc is the same steps in C; tests/test_colour_emoji.py runs
the DLL's own copy through 32-bit rundll32 and compares every pixel). The same steps as Virtual Families 1's
patcher/vf1_glyph_color.py and Fish and Plant Tycoon's raster_colour.

GDI draws every letter in one colour. A whole character drawn from a colour font (COLR, CBDT, sbix or SVG table) is
drawn here instead, in its own colours:

1. the face (colour_face_for): an emoji shown as a picture (vf2_emoji.is_colour_emoji) from the first colour font of
   the chain that has it (Segoe UI Emoji, then Noto Color Emoji), else Segoe UI Emoji; any other character whose
   chain face is a colour font, from that face;
2. DirectWrite lays the character out in that face at the regular weight (a picture is never emboldened) and the
   game font's em (CreateTextFormat, CreateTextLayout, no wrapping);
3. Direct2D draws it with D2D1_DRAW_TEXT_OPTIONS_ENABLE_COLOR_FONT and grayscale anti-aliasing on a software DC render
   target bound to a 32-bit top-down DIB the line high, transparent, the layout's baseline on the game font's baseline
   row and its pen at x = pad;
4. the cell is the advance (the layout's width rounded) from x = pad, as the black-and-white letters are cut; the
   premultiplied pixels are made straight (colour x 255 / alpha, rounded);
5. a drawing with no colour of its own (has_colour: a flag's two letters, drawn in the brush's white) is not kept: GDI
   draws it, and the game's colour tints it as any letter.

The picture keeps its own colours (the game's tint is never applied to it); a see-through text colour still makes it
see-through. Without Direct2D or DirectWrite the character is drawn by GDI in one colour, as before.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

EMOJI_FACE = "Segoe UI Emoji"
EMOJI_WEIGHT = 400
COLOUR_TABLES = (b"COLR", b"CBDT", b"sbix", b"SVG ")

_HRESULT = ctypes.c_long


class _GUID(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, text: str) -> "_GUID":
        h = text.replace("-", "")
        return cls(int(h[0:8], 16), int(h[8:12], 16), int(h[12:16], 16), (ctypes.c_ubyte * 8)(*bytes.fromhex(h[16:])))


IID_ID2D1Factory = _GUID.parse("06152247-6f50-465a-9245-118bfd3b6007")
IID_IDWriteFactory = _GUID.parse("b859ee5a-d838-4b5b-a2e8-1adc7d93db48")


class _ColorF(ctypes.Structure):
    _fields_ = [("r", ctypes.c_float), ("g", ctypes.c_float), ("b", ctypes.c_float), ("a", ctypes.c_float)]


class _Point2F(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float)]


class _RenderTargetProperties(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("format", ctypes.c_int), ("alphaMode", ctypes.c_int),
                ("dpiX", ctypes.c_float), ("dpiY", ctypes.c_float), ("usage", ctypes.c_int), ("minLevel", ctypes.c_int)]


class _TextMetrics(ctypes.Structure):
    _fields_ = [("left", ctypes.c_float), ("top", ctypes.c_float), ("width", ctypes.c_float),
                ("widthIncludingTrailingWhitespace", ctypes.c_float), ("height", ctypes.c_float),
                ("layoutWidth", ctypes.c_float), ("layoutHeight", ctypes.c_float),
                ("maxBidiReorderingDepth", ctypes.c_uint32), ("lineCount", ctypes.c_uint32)]


class _LineMetrics(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32), ("trailingWhitespaceLength", ctypes.c_uint32),
                ("newlineLength", ctypes.c_uint32), ("height", ctypes.c_float), ("baseline", ctypes.c_float),
                ("isTrimmed", wintypes.BOOL)]


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def _method(obj, index: int, restype, *argtypes):
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    fn = proto(vtable[index])
    return lambda *args: fn(obj, *args)


def _release(obj) -> None:
    if obj:
        _method(obj, 2, ctypes.c_ulong)()


# vtable indices (d2d1.h, dwrite.h)
_D2D_CREATE_DC_RENDER_TARGET = 16
_RT_CREATE_SOLID_BRUSH, _RT_DRAW_TEXT_LAYOUT, _RT_SET_TEXT_AA = 8, 28, 34
_RT_CLEAR, _RT_BEGIN, _RT_END, _DCRT_BIND = 47, 48, 49, 57
_DW_CREATE_TEXT_FORMAT, _DW_CREATE_TEXT_LAYOUT = 15, 18
_TF_SET_WORD_WRAPPING = 5
_TL_GET_LINE_METRICS, _TL_GET_METRICS = 59, 60

_factories = None


def factories():
    """(ID2D1Factory, IDWriteFactory, the software DC render target, the white brush), made once, or None without
    Direct2D / DirectWrite."""
    global _factories
    if _factories is None:
        _factories = False
        if sys.platform == "win32":
            try:
                d2d = ctypes.WinDLL("d2d1.dll")
                dw = ctypes.WinDLL("dwrite.dll")
                d2d.D2D1CreateFactory.restype = _HRESULT
                d2d.D2D1CreateFactory.argtypes = [ctypes.c_int, ctypes.POINTER(_GUID), ctypes.c_void_p,
                                                  ctypes.POINTER(ctypes.c_void_p)]
                dw.DWriteCreateFactory.restype = _HRESULT
                dw.DWriteCreateFactory.argtypes = [ctypes.c_int, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
                f2, fw, rt, brush = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
                if (d2d.D2D1CreateFactory(0, ctypes.byref(IID_ID2D1Factory), None, ctypes.byref(f2)) >= 0 and
                        dw.DWriteCreateFactory(0, ctypes.byref(IID_IDWriteFactory), ctypes.byref(fw)) >= 0):
                    props = _RenderTargetProperties(1, 87, 1, 96.0, 96.0, 0, 0)   # SOFTWARE, B8G8R8A8_UNORM, PREMULTIPLIED
                    hr = _method(f2.value, _D2D_CREATE_DC_RENDER_TARGET, _HRESULT,
                                 ctypes.POINTER(_RenderTargetProperties), ctypes.POINTER(ctypes.c_void_p))(
                        ctypes.byref(props), ctypes.byref(rt))
                    if hr >= 0 and rt.value:
                        hr = _method(rt.value, _RT_CREATE_SOLID_BRUSH, _HRESULT, ctypes.POINTER(_ColorF), ctypes.c_void_p,
                                     ctypes.POINTER(ctypes.c_void_p))(ctypes.byref(_ColorF(1, 1, 1, 1)), None,
                                                                      ctypes.byref(brush))
                    if hr >= 0 and rt.value and brush.value:
                        _factories = (f2.value, fw.value, rt.value, brush.value)
            except (OSError, AttributeError):
                _factories = False
    return _factories or None


_colour_fonts: dict = {}


def is_colour_font(face: str) -> bool:
    """The installed font `face` has a colour table (COLR, CBDT, sbix or SVG): the DLL's ColourFont."""
    if face not in _colour_fonts:
        import vf2_glyph_render as R
        found = False
        if R.available():
            c = R._Canvas(4, 4, face, 16, R.FW_NORMAL)
            try:
                found = c.face().lower() == face.lower() and any(c.font_table(t) for t in COLOUR_TABLES)
            finally:
                c.close()
        _colour_fonts[face] = found
    return _colour_fonts[face]


def colour_face_for(text: str, chain=None) -> str | None:
    """The face one whole character is drawn in colour from, or None (the DLL's ColourFaceFor)."""
    import vf2_emoji as E
    import vf2_glyph_render as R
    import vf2_game_text as T
    chain = R.FALLBACK_CHAIN if chain is None else chain
    cps = [ord(c) for c in text]
    base = next((c for c in cps if not T._is_extend(c) or len(cps) == 1), cps[0])
    if E.is_colour_emoji(text):
        for face in chain:
            if is_colour_font(face) and R.has(face, base):
                return face
        return EMOJI_FACE
    face = R.font_for(base, chain)
    return face if face is not None and is_colour_font(face) else None


def draw(text: str, em: int, baseline: int, height: int, face: str = EMOJI_FACE):
    """`text` (one whole character) in colour, the line high: (width, straight R, G, B, A bytes), or None when Windows
    cannot draw it in colour (no DirectWrite, no such face, or a drawing with no colour: has_colour)."""
    made = factories()
    if made is None:
        return None
    import vf2_glyph_render as R
    gdi32 = R._api()
    _d2d, dw, rt, brush = made
    units = sum(2 if ord(c) > 0xFFFF else 1 for c in text)          # UTF-16 units
    fmt, layout = ctypes.c_void_p(), ctypes.c_void_p()
    dc = bmp = None
    try:
        hr = _method(dw, _DW_CREATE_TEXT_FORMAT, _HRESULT, wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_int,
                     ctypes.c_int, ctypes.c_int, ctypes.c_float, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p))(
            face, None, EMOJI_WEIGHT, 0, 5, float(em), "en-us", ctypes.byref(fmt))
        if hr < 0 or not fmt.value:
            return None
        _method(fmt.value, _TF_SET_WORD_WRAPPING, _HRESULT, ctypes.c_int)(1)          # NO_WRAP
        hr = _method(dw, _DW_CREATE_TEXT_LAYOUT, _HRESULT, wintypes.LPCWSTR, ctypes.c_uint32, ctypes.c_void_p,
                     ctypes.c_float, ctypes.c_float, ctypes.POINTER(ctypes.c_void_p))(
            text, units, fmt.value, 4096.0, float(height * 4), ctypes.byref(layout))
        if hr < 0 or not layout.value:
            return None
        tm = _TextMetrics()
        if _method(layout.value, _TL_GET_METRICS, _HRESULT, ctypes.POINTER(_TextMetrics))(ctypes.byref(tm)) < 0:
            return None
        lm = _LineMetrics()
        count = ctypes.c_uint32(0)
        if _method(layout.value, _TL_GET_LINE_METRICS, _HRESULT, ctypes.POINTER(_LineMetrics), ctypes.c_uint32,
                   ctypes.POINTER(ctypes.c_uint32))(ctypes.byref(lm), 1, ctypes.byref(count)) < 0 or count.value < 1:
            return None
        advance = int(tm.widthIncludingTrailingWhitespace + ctypes.c_float(0.5).value)
        pad = height
        width = advance + 2 * pad
        dc = gdi32.CreateCompatibleDC(None)
        info = _BitmapInfoHeader(ctypes.sizeof(_BitmapInfoHeader), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        bmp = gdi32.CreateDIBSection(dc, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
        if not bmp or not bits.value:
            return None
        old = gdi32.SelectObject(dc, bmp)
        ctypes.memset(bits, 0, width * height * 4)
        rect = wintypes.RECT(0, 0, width, height)
        hr = _method(rt, _DCRT_BIND, _HRESULT, wintypes.HDC, ctypes.POINTER(wintypes.RECT))(dc, ctypes.byref(rect))
        if hr < 0:
            gdi32.SelectObject(dc, old)
            return None
        _method(rt, _RT_BEGIN, None)()
        _method(rt, _RT_SET_TEXT_AA, None, ctypes.c_int)(2)                          # GRAYSCALE
        _method(rt, _RT_CLEAR, None, ctypes.POINTER(_ColorF))(ctypes.byref(_ColorF(0, 0, 0, 0)))
        origin = _Point2F(float(pad), float(baseline) - lm.baseline)
        _method(rt, _RT_DRAW_TEXT_LAYOUT, None, _Point2F, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)(
            origin, layout.value, brush, 4)                                          # ENABLE_COLOR_FONT
        hr = _method(rt, _RT_END, _HRESULT, ctypes.c_void_p, ctypes.c_void_p)(None, None)
        gdi32.GdiFlush()
        raw = ctypes.string_at(bits, width * height * 4)
        gdi32.SelectObject(dc, old)
        if hr < 0:
            return None
    finally:
        for obj in (layout, fmt):
            _release(obj.value)
        if bmp:
            gdi32.DeleteObject(bmp)
        if dc:
            gdi32.DeleteDC(dc)
    if not has_colour(raw):
        return None
    return advance, straight_cell(raw, width, height, pad, advance)


def has_colour(raw: bytes) -> bool:
    """Whether a premultiplied B, G, R, A drawing has colour (Fish and Plant Tycoon's raster_colour, VF1 and the DLL:
    the same test): white ink has B = G = R = A, so some pixel at least 16 opaque with a channel 16 below its alpha is
    the font's own colour."""
    for i in range(0, len(raw), 4):
        a = raw[i + 3]
        if a >= 16 and (raw[i] + 16 < a or raw[i + 1] + 16 < a or raw[i + 2] + 16 < a):
            return True
    return False


def straight_cell(raw: bytes, width: int, height: int, pad: int, advance: int) -> bytes:
    """Columns pad .. pad + advance of the premultiplied B, G, R, A drawing as straight R, G, B, A rows."""
    out = bytearray(advance * height * 4)
    for y in range(height):
        for x in range(advance):
            s = (y * width + pad + x) * 4
            a = raw[s + 3]
            if a:
                b, g, r = raw[s], raw[s + 1], raw[s + 2]
                d = (y * advance + x) * 4
                out[d:d + 4] = bytes((min(255, (r * 255 + a // 2) // a), min(255, (g * 255 + a // 2) // a),
                                      min(255, (b * 255 + a // 2) // a), a))
    return bytes(out)
