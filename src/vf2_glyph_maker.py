"""The patcher-made letters: the characters Virtual Families 2's fonts lack, made in each font's own style.

The game's four fonts have ASCII and Latin-1 (U+00A2..U+00FF). For every other character of PATCHER_SET this
makes a glyph cell (the font's line height tall, white with alpha, like the sheet), labelled "(patcher-made)":

* COMPOSED from the font's own pixels when the character is a letter the font has plus one accent: the base
  letter is the game's own glyph, and the accent is cut from the game's own accented letters (the difference
  between "à" and "a", "À" and "A": grave, acute, circumflex, tilde, diaeresis, ring, cedilla), or made from them
  (caron = the circumflex upside down, breve = the lower half of the ring, dot above = one dot of the diaeresis,
  double acute = two acutes, ogonek = the cedilla mirrored, macron = the font's own "¯", comma below = the font's
  own ",", dot below = one dot of the diaeresis). The accent keeps its distance from the letter as in the game's
  own accented letters; capitals take the capital accents. Dotless ı is the game's "i" without its dot (and ì í
  î ï-style accents on i and j sit on the dotless letter).
* DRAWN in the font's style for everything else in the set (Greek, Cyrillic, Vietnamese stacked accents, the
  euro, curly quotes and dashes, letters such as ß-like ẞ, ŋ, ł): Segoe UI (the face the game's sheets were made
  from) at the size, weight and offset fitted to that font, with GDI's grey levels turned into the sheet's own
  alpha levels (src/vf2_game_fonts.json "gdi"), cut to its advance like the sheet's cells.

write_sheets() lays the glyphs of each font out on one picture, "<font>.png" (white, alpha), with "<font>.txt"
beside it (one line per glyph: the code points, then x, y and width on the picture; the height is the font's line
height). The release ships them in "Virtual Families 2 Patcher Files\\Unicode Text\\", where the Unicode Text
companion DLL loads them. The game's own pictures are never changed.
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

import vf2_game_text as T
import vf2_picture_image as P

SHEET_WIDTH = 1024
FORMAT_LINE = "# Virtual Families 2 Fun Patcher: patcher-made glyphs, format 1"

# The characters every font gets as patcher-made glyphs (the rest are drawn at run time, the same way).
PATCHER_RANGES = (
    (0x00A0, 0x00A1),            # no-break space, ¡ (the fonts lack these two Latin-1 characters)
    (0x0100, 0x024F),            # Latin Extended-A and -B
    (0x0259, 0x0259), (0x0292, 0x0292),
    (0x02B9, 0x02DD),            # modifier letters (ˆ ˇ ˘ ˙ ˚ ˛ ˜ ˝)
    (0x0370, 0x03FF),            # Greek
    (0x0400, 0x052F),            # Cyrillic
    (0x1E00, 0x1EFF),            # Latin Extended Additional (Vietnamese, Welsh ...)
    (0x2010, 0x2027), (0x2030, 0x205E),      # punctuation: dashes, quotes, bullets, ellipsis, per mille
    (0x20A0, 0x20C0),            # currency signs
    (0x2100, 0x214F),            # letter-like symbols (™ № ℃ ...)
    (0x2150, 0x218B),            # number forms (⅓ Ⅻ ...)
    (0x2190, 0x21FF),            # arrows
    (0x2200, 0x22FF),            # mathematical operators
    (0x2600, 0x26FF),            # miscellaneous symbols (☀ ☺ ♥ ...)
    (0x2700, 0x27BF),            # dingbats
)

# accents: combining mark -> (kind of placement, how it is made)
ABOVE = "above"
BELOW = "below"
MARKS = {
    0x0300: (ABOVE, "grave"), 0x0301: (ABOVE, "acute"), 0x0302: (ABOVE, "circumflex"),
    0x0303: (ABOVE, "tilde"), 0x0308: (ABOVE, "diaeresis"), 0x030A: (ABOVE, "ring"),
    0x030C: (ABOVE, "caron"), 0x0306: (ABOVE, "breve"), 0x0307: (ABOVE, "dot"), 0x030B: (ABOVE, "double acute"),
    0x0304: (ABOVE, "macron"),
    0x0327: (BELOW, "cedilla"), 0x0328: (BELOW, "ogonek"), 0x0326: (BELOW, "comma"), 0x0323: (BELOW, "dot"),
}
# the accented letters of the game's own fonts each accent is cut from (lower case, capital)
EXEMPLARS = {
    "grave": ("à", "a", "À", "A"), "acute": ("á", "a", "Á", "A"), "circumflex": ("â", "a", "Â", "A"),
    "tilde": ("ã", "a", "Ã", "A"), "diaeresis": ("ä", "a", "Ä", "A"), "ring": ("å", "a", "Å", "A"),
    "cedilla": ("ç", "c", "Ç", "C"),
}
# letters whose caron is written as an apostrophe beside them: drawn, never composed
DRAWN_ALWAYS = set("ďľťĽ")


def in_patcher_set(cp: int) -> bool:
    for a, b in PATCHER_RANGES:
        if a <= cp <= b:
            return True
    return False


def patcher_set() -> list[int]:
    out = []
    for a, b in PATCHER_RANGES:
        for cp in range(a, b + 1):
            ch = chr(cp)
            cat = unicodedata.category(ch)
            if cat in ("Cn", "Cs", "Co", "Cc") or cat.startswith("M"):
                continue
            out.append(cp)
    return out


# ====================================================================== cells

class Cell:
    """An alpha cell: w x h bytes."""

    __slots__ = ("w", "h", "a")

    def __init__(self, w: int, h: int, a=None):
        self.w, self.h = w, h
        self.a = bytearray(w * h) if a is None else bytearray(a)

    def get(self, x, y):
        return self.a[y * self.w + x] if 0 <= x < self.w and 0 <= y < self.h else 0

    def bbox(self):
        top = bottom = None
        left, right = self.w, 0
        for y in range(self.h):
            row = self.a[y * self.w:(y + 1) * self.w]
            if any(row):
                top = y if top is None else top
                bottom = y + 1
                left = min(left, next(i for i, v in enumerate(row) if v))
                right = max(right, self.w - next(i for i, v in enumerate(reversed(row)) if v))
        return None if top is None else (left, top, right, bottom)

    def crop(self, box) -> "Cell":
        l, t, r, b = box
        out = Cell(r - l, b - t)
        for y in range(t, b):
            for x in range(l, r):
                out.a[(y - t) * out.w + (x - l)] = self.get(x, y)
        return out

    def flip_v(self) -> "Cell":
        out = Cell(self.w, self.h)
        for y in range(self.h):
            out.a[y * self.w:(y + 1) * self.w] = self.a[(self.h - 1 - y) * self.w:(self.h - y) * self.w]
        return out

    def flip_h(self) -> "Cell":
        out = Cell(self.w, self.h)
        for y in range(self.h):
            out.a[y * self.w:(y + 1) * self.w] = bytes(reversed(self.a[y * self.w:(y + 1) * self.w]))
        return out

    def paste(self, src: "Cell", x: int, y: int) -> None:
        """src onto this cell at (x, y), clipped; overlapping pixels keep the stronger alpha."""
        for yy in range(src.h):
            ty = y + yy
            if not 0 <= ty < self.h:
                continue
            for xx in range(src.w):
                tx = x + xx
                if 0 <= tx < self.w:
                    v = src.a[yy * src.w + xx]
                    i = ty * self.w + tx
                    if v > self.a[i]:
                        self.a[i] = v


def _components(cell: Cell) -> list:
    """Column runs of ink (left, right) split by empty columns."""
    cols = [any(cell.a[y * cell.w + x] for y in range(cell.h)) for x in range(cell.w)]
    runs, start = [], None
    for x, on in enumerate(cols + [False]):
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x))
            start = None
    return runs


class Maker:
    """The patcher-made glyphs of one game font."""

    def __init__(self, font: T.GameFont, sheet: P.Image):
        self.font, self.sheet = font, sheet
        self.h = font.line_height
        x = self.stock("x")
        xb = x.bbox()
        self.x_top, self.baseline = xb[1], xb[3]           # x-height top row, the row under the baseline
        H = self.stock("H").bbox()
        self.cap_top = H[1]
        self.marks: dict = {}
        self._cut_marks()

    # ---------------------------------------------------------------- the font's own glyphs
    def stock(self, ch: str) -> Cell:
        l, t, r, b = self.font.stock_rect(ord(ch))
        w = r - l
        c = Cell(w, self.h)
        for y in range(min(self.h, b - t)):
            at = ((t + y) * self.sheet.width + l) * 4 + 3
            c.a[y * w:(y + 1) * w] = self.sheet.data[at:at + 4 * w:4]
        return c

    def dotless(self, ch: str) -> Cell:
        """i or j without its dot (every row above the x-height cleared)."""
        c = self.stock(ch)
        for y in range(0, self.x_top):
            c.a[y * c.w:(y + 1) * c.w] = bytes(c.w)
        return c

    # ---------------------------------------------------------------- accents
    def _diff(self, accented: str, base: str, where: str):
        A, B = self.stock(accented), self.stock(base)
        off = (A.w - B.w) // 2
        bb = B.bbox()
        d = Cell(A.w, self.h)
        for y in range(self.h):
            for xx in range(A.w):
                a = A.get(xx, y)
                b = B.get(xx - off, y)
                if a and not b and ((where == ABOVE and y < bb[1]) or (where == BELOW and y >= bb[3] - 1)):
                    d.a[y * A.w + xx] = a
        box = d.bbox()
        if box is None:
            return None
        mark = d.crop(box)
        centre = (box[0] + box[2]) / 2 - ((bb[0] + bb[2]) / 2 + off)
        if where == ABOVE:
            gap = bb[1] - box[3]                      # rows between the accent and the letter
        else:
            gap = box[1] - self.baseline              # rows from the baseline to the accent's top
        return {"cell": mark, "dx": centre, "gap": gap}

    def _cut_marks(self):
        for kind, (lo, lo_base, up, up_base) in EXEMPLARS.items():
            where = BELOW if kind == "cedilla" else ABOVE
            self.marks[(kind, False)] = self._diff(lo, lo_base, where)
            self.marks[(kind, True)] = self._diff(up, up_base, where)
        for upper in (False, True):
            circ = self.marks[("circumflex", upper)]
            ring = self.marks[("ring", upper)]
            dia = self.marks[("diaeresis", upper)]
            acute = self.marks[("acute", upper)]
            ced = self.marks[("cedilla", upper)]
            if circ:
                self.marks[("caron", upper)] = dict(circ, cell=circ["cell"].flip_v())
            if ring:
                rc = ring["cell"]
                half = rc.crop((0, rc.h // 2, rc.w, rc.h))
                self.marks[("breve", upper)] = dict(ring, cell=half)
            if dia:
                runs = _components(dia["cell"])
                if runs:
                    l, r = runs[0]
                    dot = dia["cell"].crop((l, 0, r, dia["cell"].h))
                    self.marks[("dot", upper)] = dict(dia, cell=dot)
                    self.marks[("dot below", upper)] = {"cell": dot, "dx": 0, "gap": 1}
            if acute:
                a = acute["cell"]
                two = Cell(2 * a.w + 1, a.h)
                two.paste(a, 0, 0)
                two.paste(a, a.w + 1, 0)
                self.marks[("double acute", upper)] = dict(acute, cell=two, dx=acute["dx"])
            if ced:
                self.marks[("ogonek", upper)] = dict(ced, cell=ced["cell"].flip_h(), dx=None)
            mac = self.stock("¯")
            mb = mac.bbox()
            if mb and circ:
                self.marks[("macron", upper)] = {"cell": mac.crop(mb), "dx": 0, "gap": circ["gap"] + 1}
            com = self.stock(",")
            cb = com.bbox()
            if cb:
                self.marks[("comma", upper)] = {"cell": com.crop(cb), "dx": 0, "gap": 1}

    # ---------------------------------------------------------------- making one glyph
    def compose(self, ch: str) -> T.Glyph | None:
        if ch in DRAWN_ALWAYS:
            return None
        nfd = unicodedata.normalize("NFD", ch)
        if len(nfd) < 2:
            return None
        base, marks = nfd[0], [ord(m) for m in nfd[1:]]
        if len(marks) > 2 or any(m not in MARKS for m in marks):
            return None
        above = [m for m in marks if MARKS[m][0] == ABOVE]
        below = [m for m in marks if MARKS[m][0] == BELOW]
        if len(above) > 1 or len(below) > 1:
            return None
        if not self.font.has_stock(ord(base)) or not (base.isalpha() or base.isdigit()):
            return None
        upper = base.isupper()
        cell = self.dotless(base) if base in "ij" and above else self.stock(base)
        bb = cell.bbox()
        if bb is None:
            return None
        centre = (bb[0] + bb[2]) / 2
        for m in above:
            kind = MARKS[m][1]
            mk = self.marks.get((kind, upper))
            if not mk:
                return None
            mc = mk["cell"]
            x = round(centre + (mk["dx"] or 0) - mc.w / 2)
            y = max(0, bb[1] - mk["gap"] - mc.h)
            cell.paste(mc, x, y)
        for m in below:
            kind = MARKS[m][1]
            key = ("dot below", upper) if kind == "dot" else (kind, upper)
            mk = self.marks.get(key)
            if not mk:
                return None
            mc = mk["cell"]
            if kind == "ogonek":
                x = bb[2] - mc.w
            elif kind == "cedilla":
                x = round(centre + (mk["dx"] or 0) - mc.w / 2)
            else:
                x = round(centre - mc.w / 2)
            y = self.baseline + mk["gap"] if kind != "cedilla" else self.baseline + mk["gap"]
            cell.paste(mc, x, y)
        return T.Glyph(cell.w, "patcher", None, bytes(cell.a), "composed from the game font")

    def special(self, ch: str) -> T.Glyph | None:
        if ch == " ":
            sp = self.stock(" ")
            return T.Glyph(sp.w, "patcher", None, bytes(sp.a), "the game font's space")
        if ch == "¡":                                          # ¡ = the font's own ! turned over
            ex = self.stock("!")
            box = ex.bbox()
            flipped = ex.crop(box).flip_v()
            q = self.stock("¿").bbox()
            out = Cell(ex.w, self.h)
            out.paste(flipped, box[0], q[1] if q else self.x_top)
            return T.Glyph(out.w, "patcher", None, bytes(out.a), "the game font's ! turned over")
        if ch == "ı":
            c = self.dotless("i")
            return T.Glyph(c.w, "patcher", None, bytes(c.a), "the game font's i without its dot")
        if ch == "ȷ":
            c = self.dotless("j")
            return T.Glyph(c.w, "patcher", None, bytes(c.a), "the game font's j without its dot")
        return None

    def drawn(self, ch: str) -> T.Glyph | None:
        g = T.runtime_glyph(self.font, ch)
        if g.kind != "runtime":
            return None
        return T.Glyph(g.width, "patcher", None, g.alpha, f"drawn in the font's style ({g.source})")

    def make(self, ch: str) -> T.Glyph | None:
        if len(ch) != 1 or not in_patcher_set(ord(ch)):
            return None
        return self.special(ch) or self.compose(ch) or self.drawn(ch)


# ====================================================================== fonts with their patcher-made glyphs

@lru_cache(maxsize=8)
def _sheet(path: str) -> P.Image:
    return P.load_png(Path(path))


def load_fonts(images: Path) -> dict:
    """{font name: (GameFont with patcher-made glyphs made on first use, its sheet)} from a game's Images folder."""
    out = {}
    for name in T.FONT_NAMES:
        font = T.load_font(name)
        sheet = _sheet(str(Path(images) / font.image))
        maker = Maker(font, sheet)
        font.maker = maker.make
        out[name] = (font, sheet)
    return out


def write_sheets(images: Path, out_dir: Path) -> list[Path]:
    """Every font's patcher-made glyphs as "<font>.png" + "<font>.txt" in out_dir (the release's Unicode Text
    folder). Returns the files written."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    cps = patcher_set()
    for name, (font, _sheet_img) in load_fonts(images).items():
        cells = []
        for cp in cps:
            g = font.maker(chr(cp))
            if g is not None and g.width > 0:
                cells.append((cp, g))
        h = font.line_height
        x = y = 0
        placed = []
        for cp, g in cells:
            if x + g.width > SHEET_WIDTH:
                x, y = 0, y + h
            placed.append((cp, g, x, y))
            x += g.width
        img = P.Image(SHEET_WIDTH, y + h)
        for cp, g, gx, gy in placed:
            for yy in range(h):
                for xx in range(g.width):
                    a = g.alpha[yy * g.width + xx]
                    if a:
                        at = ((gy + yy) * img.width + gx + xx) * 4
                        img.data[at:at + 4] = bytes((255, 255, 255, a))
        png = out_dir / f"{name}.png"
        png.write_bytes(img.to_png())
        lines = [FORMAT_LINE, f"font {name}", f"height {h}", f"count {len(placed)}"]
        for cp, g, gx, gy in placed:
            lines.append(f"{cp:X}\t{gx}\t{gy}\t{g.width}")
        txt = out_dir / f"{name}.txt"
        txt.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
        written += [png, txt]
    return written


def read_sheet_index(path: Path) -> dict:
    """{code point: (x, y, width)} of a "<font>.txt" (the DLL reads the same lines)."""
    out = {}
    for line in Path(path).read_text(encoding="ascii").splitlines():
        if not line or line.startswith(("#", "font ", "height ", "count ")):
            continue
        cp, x, y, w = line.split("\t")
        out[int(cp, 16)] = (int(x), int(y), int(w))
    return out
