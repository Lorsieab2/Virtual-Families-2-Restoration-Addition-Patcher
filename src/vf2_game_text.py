"""Virtual Families 2's text, one rule for the whole patcher: how a name or line is stored, read, cut and drawn.

THE STORED FORM (every reader and writer of the patcher uses decode / encode / fit here; the Unicode Text DLL in
the game uses the same rule, runtime/native/b200unicode/b200unicode_text.h):

* a save's text field holds bytes up to the first 0 byte;
* if those bytes are valid UTF-8 and hold at least one byte of 80h or more, they are UTF-8;
* otherwise every byte is one character: ASCII; A0h..FFh are Latin-1 (the game's own fonts have those letters, so
  the unpatched game shows them); 80h..9Fh are Windows-1252 (the euro, curly quotes ...), and the five bytes
  Windows-1252 leaves out are their Latin-1 control characters.
* writing (encode): a text whose every character is ASCII, U+00A0..U+00FF or one of the 27 Windows-1252 characters
  of 80h..9Fh is written one byte per character, so the unpatched game and older tools show it exactly as before
  and an old name read and written again keeps its bytes; only if that byte string would itself read as
  UTF-8 (a deliberately typed "Ã©") or the text has any other character is it written as UTF-8. decode(encode(t))
  is always t.

Where Virtual Families 2 differs from the Virtual Villagers rule (UTF-8 for anything beyond ASCII): VF2's own fonts
already draw Latin-1 (U+00A2..U+00FF), so Latin-1 names stay single bytes: the unpatched game shows them correctly,
older patcher tools read them, and they cost one byte of the field instead of two.

CHARACTERS (grapheme clusters): a letter and the marks on it, an emoji with its skin tone or joined emoji, a flag
(two regional indicators) are one character. Lengths and cuts count bytes in the field but never cut inside one.

DRAWING: the stock code draws one byte at a time (ldwGameWindowImpl::DrawString / DrawChars, ldwFont::GetWidth,
GetNextJustifiedLine). layout() and friends below are those functions with a character in place of a byte; for
any text of single bytes they are the stock functions exactly (tests/test_vf2_game_text.py runs the game's own
code to prove it). A character the game's font has is drawn from the font's sheet; one it lacks is a patcher-made
glyph (src/vf2_glyph_maker.py), or drawn from a Windows font in the game font's style (src/vf2_glyph_render.py),
or the missing-glyph box.
"""
from __future__ import annotations

import bisect
import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
import vf2_unicode_tables as _tables  # noqa: E402  (the tables the DLL shares)
FONTS_JSON = HERE / "vf2_game_fonts.json"
FONT_NAMES = ("Segoe24", "Segoe24Bold", "Segoe32Bold", "Segoe36Bold")
FONT_TITLES = {
    "Segoe24": "Segoe 24 (the game's regular text)",
    "Segoe24Bold": "Segoe 24 Bold (buttons and labels)",
    "Segoe32Bold": "Segoe 32 Bold (headings)",
    "Segoe36Bold": "Segoe 36 Bold (titles)",
}

# Windows-1252's 80h..9Fh (None = the five bytes it leaves out: read as the Latin-1 control character)
_CP1252_HIGH = [
    0x20AC, None, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, None,
    0x017D, None, None, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A,
    0x0153, None, 0x017E, 0x0178,
]


_CP1252_BYTE = {cp: 0x80 + i for i, cp in enumerate(_CP1252_HIGH) if cp is not None}

# ====================================================================== the stored form

def _single_byte_char(b: int) -> str:
    if 0x80 <= b <= 0x9F:
        cp = _CP1252_HIGH[b - 0x80]
        return chr(cp if cp is not None else b)
    return chr(b)


def is_utf8(raw: bytes) -> bool:
    """True when the bytes are valid UTF-8 with at least one byte of 80h or more (the stored-form test)."""
    if all(b < 0x80 for b in raw):
        return False
    try:
        raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return False
    return True


def decode(raw: bytes) -> str:
    """The text a field holds (bytes up to the first 0)."""
    raw = bytes(raw).split(b"\0", 1)[0]
    if is_utf8(raw):
        return raw.decode("utf-8")
    return "".join(_single_byte_char(b) for b in raw)


def encode(text: str) -> bytes:
    """The bytes a field gets for `text` (no terminating 0). See the module notes."""
    text = text.replace("\0", "")
    if all(ord(c) < 0x80 or 0xA0 <= ord(c) <= 0xFF or ord(c) in _CP1252_BYTE for c in text):
        single = bytes(_CP1252_BYTE.get(ord(c), ord(c)) for c in text)
        if not is_utf8(single):
            return single
    return text.encode("utf-8", "surrogatepass")


# The largest name a Virtual Families 2 text box can hold, in bytes of the stored form: ldwTextControl::SetCanEdit
# caps every box at 4B0h = 1,200 bytes (300 characters of 4 bytes in the worst case; GetText then cuts to the
# destination field). The save fields themselves are fixed (player and nickname 20, family member 19 with the stock
# box at 18, Family Tree note 80); a longer name needs a per-save sidecar. One named constant, so the shared limit
# across the patchers can be set here.
TEXT_BOX_CEILING_BYTES = 1200

# ====================================================================== characters (grapheme clusters)

_EXTEND_STARTS = [a for a, _b in _tables.EXTEND]


def _is_extend(cp: int) -> bool:
    """A code point that stays with the character before it (src/vf2_unicode_tables.EXTEND: combining marks,
    joiners, variation selectors, emoji modifiers, tags)."""
    i = bisect.bisect_right(_EXTEND_STARTS, cp) - 1
    return i >= 0 and cp <= _tables.EXTEND[i][1]


def _is_regional(cp: int) -> bool:
    return 0x1F1E6 <= cp <= 0x1F1FF


def clusters(text: str) -> list[str]:
    """The characters of `text` as a reader sees them (a simplified extended grapheme cluster rule: marks, joiners,
    variation selectors, emoji modifiers and tags stay with what they follow; a ZWJ joins the next character;
    regional indicators pair; CR LF is one). The DLL uses the same rule."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        start = i
        cp = ord(text[i])
        i += 1
        if cp == 0x0D and i < n and text[i] == "\n":
            i += 1
        elif _is_regional(cp) and i < n and _is_regional(ord(text[i])):
            i += 1
        while i < n:
            c = ord(text[i])
            if _is_extend(c):
                i += 1
                if c == 0x200D and i < n and ord(text[i]) not in (0x0A, 0x0D):
                    i += 1
                continue
            break
        out.append(text[start:i])
    return out


def length(text: str) -> int:
    """How many characters (clusters) `text` has: the character limit counts these."""
    return len(clusters(text))


def fit(text: str, max_bytes: int) -> bytes:
    """The stored form of the longest start of `text`, in whole characters, that fits in max_bytes bytes."""
    raw = encode(text)
    if len(raw) <= max_bytes:
        return raw
    out = b""
    prefix = ""
    for c in clusters(text):
        prefix += c
        piece = encode(prefix)          # the cut text gets its own stored form (it may be Latin-1 again)
        if len(piece) > max_bytes:
            break
        out = piece
    return out


def field_bytes(text: str, size: int) -> bytes:
    """A fixed field of `size` bytes: the text (cut to size - 1 bytes at a character), then zero bytes."""
    raw = fit(text, size - 1)
    return raw + b"\0" * (size - len(raw))


# A letter typed as a base letter and combining accents (e + U+0301) is drawn as the one letter it makes (é),
# for the letters of these blocks: Latin-1, Latin Extended-A/B, Greek, Cyrillic, Latin Extended Additional, Greek
# Extended. A fixed table (src/vf2_unicode_tables.py; the DLL has the same one), never a general normalisation.
COMPOSE = {"".join(chr(c) for c in seq): chr(cp) for seq, cp in _tables.COMPOSE.items()}


# ====================================================================== units: what the drawing code steps over

@dataclass(frozen=True)
class Unit:
    text: str        # the character (cluster), "\n" for a line break
    raw: bytes       # its bytes in the stored form

    @property
    def size(self) -> int:
        return len(self.raw)


def units(raw: bytes) -> list[Unit]:
    """The text's characters with their bytes. Single-byte text: one unit per byte (as the stock code steps)."""
    raw = bytes(raw).split(b"\0", 1)[0]
    if is_utf8(raw):
        return [Unit(c, c.encode("utf-8", "surrogatepass")) for c in clusters(raw.decode("utf-8"))]
    return [Unit(_single_byte_char(b), bytes([b])) for b in raw]


# ====================================================================== fonts

@dataclass
class Glyph:
    width: int                       # the cell width (stock: right - left of the source rectangle)
    kind: str                        # "game", "patcher" (patcher-made), "runtime" (Windows font), "box"
    rect: tuple | None = None        # game glyphs: (left, top, right, bottom) on the game's sheet
    alpha: bytes | None = None       # other glyphs: width * line_height alpha bytes
    source: str = ""                 # how a patcher-made / runtime glyph was made


@dataclass
class GameFont:
    name: str
    line_height: int
    kerning: int
    sheet_size: tuple
    image: str
    glyphs: list                     # [code, left, top, right, bottom] in the game's table order
    charmap: list                    # 256 entries: byte -> index into glyphs
    gdi: dict
    extra: dict = field(default_factory=dict)      # cluster -> Glyph (patcher-made), filled by the glyph maker
    runtime: dict = field(default_factory=dict)    # cluster -> Glyph (Windows font), made on first use
    maker: object = None                           # cluster -> patcher-made Glyph or None (vf2_glyph_maker)

    def stock_rect(self, byte: int) -> tuple:
        """ldwFontImpl::GetCharSourceRect for one byte (a byte the font lacks gives entry 0, '!')."""
        g = self.glyphs[self.charmap[byte & 0xFF]]
        return g[1], g[2], g[3], g[4]

    def has_stock(self, cp: int) -> bool:
        """The game's sheet has its own picture for this code point (never via the entry-0 fallback)."""
        if cp >= 0x100:
            return False
        if cp < 0x20 or cp == 0x7F:
            return True                      # control bytes: the stock code draws them (entry 0) - kept stock
        k = self.charmap[cp]
        return self.glyphs[k][0] == cp or (k == 0 and cp == self.glyphs[0][0])

    def glyph(self, unit: Unit) -> Glyph:
        text = unit.text
        if len(unit.raw) == 1 and (ord(text) < 0x80 or self.has_stock(ord(text))):
            # one stored byte the stock code would draw from the sheet (ASCII, or a Latin-1 letter the font has)
            l, t, r, b = self.stock_rect(unit.raw[0])
            return Glyph(r - l, "game", (l, t, r, b))
        nfc = COMPOSE.get(text, text)
        if len(nfc) == 1 and self.has_stock(ord(nfc)):
            l, t, r, b = self.stock_rect(ord(nfc))
            return Glyph(r - l, "game", (l, t, r, b))
        if nfc in self.extra:
            return self.extra[nfc]
        if self.maker is not None:
            made = self.maker(nfc)
            if made is not None:
                self.extra[nfc] = made
                return made
        if text in self.runtime:
            return self.runtime[text]
        g = runtime_glyph(self, text)
        self.runtime[text] = g
        return g


@lru_cache(maxsize=1)
def _font_data() -> dict:
    return json.loads(FONTS_JSON.read_text(encoding="utf-8"))["fonts"]


def load_font(name: str) -> GameFont:
    d = _font_data()[name]
    return GameFont(name, d["line_height"], d["kerning"], tuple(d["sheet"]), d["image"], d["glyphs"], d["charmap"],
                    d["gdi"])


def missing_box(font: GameFont) -> Glyph:
    """The missing-glyph box: an outline from cap height to the baseline, 0.6 em wide, with one clear column each
    side. The DLL draws the same box."""
    h = font.line_height
    px = font.gdi["px"]
    w = max(4, (px * 6 + 5) // 10)
    ascent = max(2, (px * 7 + 5) // 10)
    base = min(h - 1, -font.gdi["top"] + (px * 108 + 50) // 100)
    top = max(0, base - ascent)
    a = bytearray(w * h)
    for y in range(top, base + 1):
        for x in range(1, w - 1):
            if y in (top, base) or x in (1, w - 2):
                a[y * w + x] = 255
    return Glyph(w, "box", None, bytes(a), "missing")


def runtime_glyph(font: GameFont, text: str) -> Glyph:
    """A character the game font and the patcher-made glyphs lack, drawn with the first Windows font of the chain
    that has it (src/vf2_glyph_render.py), at the game font's fitted size, cut to its cell and given the sheet's
    alpha levels. The DLL makes the same cell."""
    import vf2_glyph_render as R
    if not R.available():
        return missing_box(font)
    cps = [ord(c) for c in text]
    base = next((c for c in cps if not _is_extend(c) or len(cps) == 1), cps[0])
    face = R.font_for(base)
    if face is None:
        return missing_box(font)
    g = font.gdi
    h = font.line_height
    adv, grey, w, ox = R.render(text, face, g["px"], g["weight"], h, g["top"])
    adv = max(0, min(adv, w - ox))
    lut = g["alpha"]
    a = bytearray(adv * h)
    for y in range(h):
        row = grey[y * w + ox: y * w + ox + adv]
        a[y * adv: (y + 1) * adv] = bytes(lut[v] for v in row)
    return Glyph(adv, "runtime", None, bytes(a), face)


# ====================================================================== the stock functions, per character

def get_width(font: GameFont, raw: bytes, scale: float = 1.0) -> int:
    """ldwFont::GetWidth(const char *, float): per line the sum of (kerning + glyph width) * scale (each step
    truncated), the widest line, minus one kerning."""
    import struct as _s
    sc = _s.unpack("<f", _s.pack("<f", scale))[0]
    widest = cur = 0
    for u in units(raw):
        if u.text == "\n":
            if cur:
                widest = max(widest, cur)
            cur = 0
            continue
        g = font.glyph(u)
        v = _s.unpack("<f", _s.pack("<f", float(font.kerning + g.width)))[0]
        cur += int(_s.unpack("<f", _s.pack("<f", v * sc))[0])
    cur = max(cur, widest)
    return cur - font.kerning if cur else 0


def get_height(font: GameFont, raw: bytes) -> int:
    """ldwFont::GetHeight: the line height times (1 + the line breaks). Bytes only: a UTF-8 character never holds
    a 0Ah byte, so this is the stock function for every stored form (the DLL leaves it alone)."""
    raw = bytes(raw).split(b"\0", 1)[0]
    return font.line_height * (1 + raw.count(b"\n"))


@dataclass
class Placement:
    glyph: Glyph
    x: int
    y: int
    unit: Unit


def draw_string(font: GameFont, raw: bytes, x: int, y: int) -> list[Placement]:
    """ldwGameWindowImpl::DrawString: a line break moves down one line height and back to the starting x, a glyph
    of width 0 draws nothing and does not move, every other glyph is drawn at (x, y) and moves x by its width plus
    the kerning."""
    out = []
    x0 = x
    for u in units(raw):
        if u.text == "\n":
            y += font.line_height
            x = x0
            continue
        g = font.glyph(u)
        if g.width == 0:
            continue
        out.append(Placement(g, x, y, u))
        x += g.width + font.kerning
    return out


def draw_chars(font: GameFont, raw: bytes, count: int, x: int, y: int) -> tuple[int, list[Placement]]:
    """ldwGameWindowImpl::DrawChars: the first `count` BYTES at most (never part of a character: a character
    that would cross `count` is not drawn), as DrawString; returns how far x moved."""
    out, x0, used = [], x, 0
    for u in units(raw):
        if used + u.size > count:
            break
        used += u.size
        if u.text == "\n":
            y += font.line_height
            x = x0
            continue
        g = font.glyph(u)
        if g.width == 0:
            continue
        out.append(Placement(g, x, y, u))
        x += g.width + font.kerning
    return x - x0, out


def _wide(text: str) -> bool:
    """A character after which a line may break although no space follows (CJK, kana, Hangul, fullwidth)."""
    cp = ord(text[0])
    return (0x1100 <= cp <= 0x115F or 0x2E80 <= cp <= 0xA4CF or 0xAC00 <= cp <= 0xD7A3 or 0xF900 <= cp <= 0xFAFF
            or 0xFE30 <= cp <= 0xFE4F or 0xFF00 <= cp <= 0xFF60 or 0xFFE0 <= cp <= 0xFFE6
            or 0x20000 <= cp <= 0x3FFFD)


def next_justified_line(font: GameFont, raw: bytes, max_bytes: int, max_width: int, keep_newline: bool = True,
                        scale: float = 1.0) -> tuple[bytes, int, bool]:
    """ldwFont::GetNextJustifiedLine, step for step, with a character in place of a byte.

    Returns (the line written, how many bytes of `raw` it consumed, the flag it sets on a second line break in a
    row). Stock: leading and repeated spaces are skipped; a line break becomes a space (or ends the line when
    keep_newline is false); when the line is wider than max_width or max_bytes have been written, the line goes
    back to its last space (an empty line if it has none). max_bytes counts BYTES (it guards the caller's
    buffer): a character of several bytes that would pass it ends the line before it, back to a space.

    One addition for scripts written without spaces: when the character that made the line too long, or the one
    before it, is a wide (CJK) character, the line ends just before that character. Text of single bytes (all
    the game's own text) is the stock function exactly."""
    import struct as _s

    def f32(v):
        return _s.unpack("<f", _s.pack("<f", v))[0]

    sc = f32(scale)
    us = units(raw)
    offs = [0]
    for u in us:
        offs.append(offs[-1] + u.size)
    buf: list = []                 # the caller's buffer, one unit per position
    esi = count = width = p = 0
    prev_newline = False

    def put(i, unit):
        if i < len(buf):
            buf[i] = unit
        else:
            buf.append(unit)

    def line(k):
        return b"".join(w.raw for w in buf[:k])

    def overflow(esi, p):
        # 0x116: buf[esi] is the character just written; p is the unit after it
        if buf[esi].text == " ":
            return line(esi), offs[p], False
        if _wide(buf[esi].text) or (esi > 0 and _wide(buf[esi - 1].text)):
            if esi == 0:
                return line(1), offs[p], False
            return line(esi), offs[p - 1], False
        return _walk_back(buf, esi, p, offs)

    while p < len(us):
        u = us[p]
        start = p
        if u.text == "\n":
            p += 1
            if prev_newline:
                return line(esi), offs[p], True
            prev_newline = True
            if count == 0 or buf[esi - 1].text == " ":
                continue
            if not keep_newline:
                return line(esi), offs[p], False
            unit = Unit(" ", b" ")
        else:
            prev_newline = False
            if u.text == " " and (count == 0 or buf[esi - 1].text == " "):
                p += 1
                continue
            unit = u
        if max_bytes > 0 and unit.size > 1 and count + unit.size > max_bytes:
            put(esi, unit)              # never kept: the walk back always ends before it
            return _walk_back(buf, esi, start + 1, offs)
        put(esi, unit)
        g = font.glyph(unit)
        count += unit.size
        p = start + 1
        width += int(f32(f32(float(font.kerning + g.width)) * sc))
        if width > max_width or (max_bytes > 0 and count >= max_bytes):
            return overflow(esi, p)
        esi += 1
    return line(esi), offs[p], False


def _walk_back(buf, esi, p, offs):
    """The stock walk back: the write and read positions step back together until the written unit is a space
    (the line ends before it) or the line start (an empty line)."""
    while True:
        if esi == 0:
            return b"", offs[p], False
        esi -= 1
        p -= 1
        if buf[esi].text == " ":
            return b"".join(w.raw for w in buf[:esi]), offs[p], False


# ====================================================================== pictures

def tint(alpha_value: int, rgb: tuple) -> tuple:
    """ldwFontImpl::GetImage: every sheet pixel (white, a) AND the colour (r, g, b, FFh) -> (r, g, b, a)."""
    return rgb[0], rgb[1], rgb[2], alpha_value


def glyph_alpha(font: GameFont, glyph: Glyph, sheet) -> bytes:
    """A glyph's alpha cell (width * line height)."""
    if glyph.alpha is not None:
        return glyph.alpha
    l, t, r, b = glyph.rect
    w, h = r - l, b - t
    out = bytearray(w * h)
    for yy in range(h):
        at = ((t + yy) * sheet.width + l) * 4 + 3
        out[yy * w:(yy + 1) * w] = sheet.data[at:at + 4 * w:4]
    return bytes(out)


def glyph_pixels(font: GameFont, glyph: Glyph, sheet, rgb=(255, 255, 255)) -> tuple[int, int, bytes]:
    """The glyph as the game blits it: the sheet's own pixels for a game glyph (white tint: the sheet itself),
    else white with the glyph's alpha, each pixel AND (r, g, b, FFh)."""
    if glyph.rect is not None:
        l, t, r, b = glyph.rect
        w, h = r - l, b - t
        data = bytearray(w * h * 4)
        for yy in range(h):
            at = ((t + yy) * sheet.width + l) * 4
            data[yy * w * 4:(yy + 1) * w * 4] = sheet.data[at:at + 4 * w]
    else:
        w, h = glyph.width, font.line_height
        data = bytearray(w * h * 4)
        for i, a in enumerate(glyph.alpha):
            data[4 * i:4 * i + 4] = bytes((255, 255, 255, a))
    if tuple(rgb) != (255, 255, 255):
        r0, g0, b0 = rgb
        for i in range(0, len(data), 4):
            data[i] &= r0
            data[i + 1] &= g0
            data[i + 2] &= b0
    return w, h, bytes(data)


def wrap(font: GameFont, raw: bytes, max_width: int, max_bytes: int = 0x3FF) -> list[bytes]:
    """The lines a wrapped paragraph gets: GetNextJustifiedLine over and over, as the game's dialogs call it
    (keep_newline false, so a line break ends a line; a blank line between two breaks is kept)."""
    lines = []
    rest = bytes(raw).split(b"\0", 1)[0]
    guard = 0
    while rest and guard < 10000:
        guard += 1
        line, used, double = next_justified_line(font, rest, max_bytes, max_width, False)
        if used <= 0 and not line:
            # the stock function cannot place a word wider than the box: show it on its own line
            cut = units(rest)[0].size
            line, used = rest[:cut], cut
        lines.append(line)
        if double:
            lines.append(b"")
        rest = rest[used:]
    return lines


def render(font: GameFont, sheet, raw: bytes, rgb=(255, 255, 255), *, max_width: int = 0, background=None):
    """A picture of the text exactly as the game draws it: every glyph's own pixels (the sheet's for a game
    glyph), tinted the game's way, at the place DrawString puts it; a line break starts a new line. With
    max_width, the text is wrapped first (wrap). The picture is as wide as the widest line and line height times
    the line count tall, clear, or `background` (r, g, b) under the text. Returns a vf2_picture_image.Image."""
    import vf2_picture_image as P
    raw = bytes(raw).split(b"\0", 1)[0]
    lines = wrap(font, raw, max_width) if max_width else raw.split(b"\n")
    if not lines:
        lines = [b""]
    width = max([get_width(font, ln) for ln in lines] + [1])
    height = font.line_height * len(lines)
    img = P.Image(width, height)
    if background is not None:
        img.data[:] = bytes((background[0], background[1], background[2], 255)) * (width * height)
    for k, ln in enumerate(lines):
        for p in draw_string(font, ln, 0, k * font.line_height):
            w, h, data = glyph_pixels(font, p.glyph, sheet, rgb)
            img.draw(P.Image(w, h, data), p.x, p.y)
    return img


def glyph_label(glyph: Glyph) -> str:
    """How the patcher shows where a glyph comes from."""
    return {"game": "(game font)", "patcher": "(patcher-made)", "runtime": f"(patcher-made from {glyph.source})",
            "box": "(missing: box)"}[glyph.kind]
