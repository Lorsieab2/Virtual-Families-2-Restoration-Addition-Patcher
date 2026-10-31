"""The Picture Maker's pictures: an RGBA image, a PNG reader and writer, the game's own scaled blit, and the
export sizes. Standard library only (the patcher ships no Pillow); on Windows the game's big sprite sheets are
read through GDI+ (vf2_gdiplus), which gives the same bytes as the pure reader here, only faster.

Ported from the Fish and Plant Tycoon Fix Patcher's Picture Studio (src/picture_image.py) and kept as close to
it as Virtual Families 2 allows: the image, the PNG reader and writer, "Game size" / 2x / 4x (crisp) / a custom
size (smooth), the small clear margin, the file names. What differs is the game's scaled draw
(game_scaled_cell), which is Virtual Families 2's own blitter.
"""
from __future__ import annotations

import base64
import ctypes
import os
import re
import struct
import sys
import uuid
import zlib
from pathlib import Path

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MARGIN = 4
SIZES = (("1x", 1), ("2x", 2), ("4x", 4))
MAX_SIDE = 8192                 # the largest picture the Picture Maker writes (a custom size is capped)


class PictureError(Exception):
    """A picture that cannot be drawn or read, in words for the player."""


# ------------------------------------------------------------------ the image


class Image:
    """Straight (not premultiplied) 8-bit RGBA, rows top to bottom."""

    __slots__ = ("width", "height", "data")

    def __init__(self, width: int, height: int, data=None) -> None:
        if width < 0 or height < 0:
            raise ValueError("an image cannot have a negative size")
        self.width, self.height = int(width), int(height)
        self.data = bytearray(self.width * self.height * 4) if data is None else bytearray(data)
        if len(self.data) != self.width * self.height * 4:
            raise ValueError("the pixel data does not fit the size")

    def to_png(self) -> bytes:
        return encode_png(self)

    def copy(self) -> "Image":
        return Image(self.width, self.height, self.data)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Image) and (self.width, self.height) == (other.width, other.height) \
            and self.data == other.data

    def __repr__(self) -> str:
        return f"Image({self.width}x{self.height})"

    def pixel(self, x: int, y: int) -> tuple:
        at = (y * self.width + x) * 4
        return tuple(self.data[at:at + 4])

    def sub(self, x: int, y: int, w: int, h: int) -> "Image":
        """The w x h piece at (x, y); any part outside the image is transparent."""
        out = Image(w, h)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 <= x0 or y1 <= y0:
            return out
        row = (x1 - x0) * 4
        for yy in range(y0, y1):
            src = (yy * self.width + x0) * 4
            dst = ((yy - y) * w + (x0 - x)) * 4
            out.data[dst:dst + row] = self.data[src:src + row]
        return out

    def draw(self, src: "Image", x: int, y: int) -> None:
        """src over this image at (x, y), clipped: straight-alpha "over", in exactly the integer steps of the
        standard (Pillow's alpha_composite: 7 fraction bits, x / 255 as ((x >> 8) + x) >> 8), so a picture can be
        checked against an independent composite. A fully covering pixel replaces, a clear one leaves what is
        under it."""
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + src.width), min(self.height, y + src.height)
        if x1 <= x0 or y1 <= y0:
            return
        sd, dd = src.data, self.data
        for yy in range(y0, y1):
            s = ((yy - y) * src.width + (x0 - x)) * 4
            d = (yy * self.width + x0) * 4
            for _ in range(x1 - x0):
                sa = sd[s + 3]
                if sa == 255:
                    dd[d:d + 4] = sd[s:s + 4]
                elif sa:
                    blend = dd[d + 3] * (255 - sa)
                    outa255 = sa * 255 + blend
                    coef1 = sa * 255 * 255 * 128 // outa255
                    coef2 = 255 * 128 - coef1
                    for c in range(3):
                        t = sd[s + c] * coef1 + dd[d + c] * coef2 + (0x80 << 7)
                        dd[d + c] = (((t >> 8) + t) >> 8) >> 7
                    t = outa255 + 0x80
                    dd[d + 3] = ((t >> 8) + t) >> 8
                s += 4
                d += 4

    def bbox(self):
        """(left, top, right, bottom), right and bottom exclusive, of the pixels with any alpha, or None."""
        w, h = self.width, self.height
        alphas = self.data[3::4]
        top = bottom = None
        left, right = w, 0
        for y in range(h):
            row = alphas[y * w:(y + 1) * w]
            if any(row):
                if top is None:
                    top = y
                bottom = y + 1
                first = next(i for i, a in enumerate(row) if a)
                last = w - next(i for i, a in enumerate(reversed(row)) if a)
                left, right = min(left, first), max(right, last)
        if top is None:
            return None
        return left, top, right, bottom

    def cropped(self, margin: int = MARGIN) -> "Image":
        """Cut to the drawn pixels plus `margin` clear pixels each side; nothing drawn is 1 x 1 (plus the margin)."""
        box = self.bbox()
        if box is None:
            return Image(1 + 2 * margin, 1 + 2 * margin)
        left, top, right, bottom = box
        return self.sub(left - margin, top - margin, right - left + 2 * margin, bottom - top + 2 * margin)

    def scaled(self, factor: int) -> "Image":
        """Nearest neighbour, crisp: every pixel becomes factor x factor."""
        factor = int(factor)
        if factor < 1:
            raise ValueError("the scale must be 1 or more")
        if factor == 1:
            return self.copy()
        out = Image(self.width * factor, self.height * factor)
        stride = self.width * 4
        out_stride = stride * factor
        for y in range(self.height):
            row = self.data[y * stride:(y + 1) * stride]
            wide = b"".join(bytes(row[i:i + 4]) * factor for i in range(0, stride, 4))
            for k in range(factor):
                at = (y * factor + k) * out_stride
                out.data[at:at + out_stride] = wide
        return out

    def resized(self, width: int, height: int) -> "Image":
        """Smooth scaling to width x height: a linear (triangle) filter, widened when shrinking so every source
        pixel counts, on premultiplied colour so clear edges stay clean."""
        width, height = int(width), int(height)
        if width < 1 or height < 1:
            raise ValueError("a picture must be at least 1 x 1")
        if (width, height) == (self.width, self.height):
            return self.copy()
        n = self.width * self.height
        src = self.data
        pre = [0.0] * (n * 4)
        for i in range(n):
            a = src[i * 4 + 3]
            if a:
                f = a / 255.0
                pre[i * 4] = src[i * 4] * f
                pre[i * 4 + 1] = src[i * 4 + 1] * f
                pre[i * 4 + 2] = src[i * 4 + 2] * f
                pre[i * 4 + 3] = float(a)
        horizontal = _resample_weights(self.width, width)
        vertical = _resample_weights(self.height, height)
        mid = [0.0] * (width * self.height * 4)
        for y in range(self.height):
            base = y * self.width * 4
            out = y * width * 4
            for x, (first, weights) in enumerate(horizontal):
                r = g = b = a = 0.0
                at = base + first * 4
                for wgt in weights:
                    r += pre[at] * wgt
                    g += pre[at + 1] * wgt
                    b += pre[at + 2] * wgt
                    a += pre[at + 3] * wgt
                    at += 4
                o = out + x * 4
                mid[o], mid[o + 1], mid[o + 2], mid[o + 3] = r, g, b, a
        result = Image(width, height)
        dd = result.data
        row4 = width * 4
        for y, (first, weights) in enumerate(vertical):
            for x in range(width):
                r = g = b = a = 0.0
                at = first * row4 + x * 4
                for wgt in weights:
                    r += mid[at] * wgt
                    g += mid[at + 1] * wgt
                    b += mid[at + 2] * wgt
                    a += mid[at + 3] * wgt
                    at += row4
                o = (y * width + x) * 4
                alpha = int(a + 0.5)
                if alpha <= 0:
                    continue
                dd[o] = max(0, min(255, int(r / a * 255.0 + 0.5)))
                dd[o + 1] = max(0, min(255, int(g / a * 255.0 + 0.5)))
                dd[o + 2] = max(0, min(255, int(b / a * 255.0 + 0.5)))
                dd[o + 3] = min(255, alpha)
        return result

    def photo(self, tk_mod, master, max_side: int | None = None):
        """A Tk PhotoImage of this image (Tk reads PNG alpha), shrunk by whole steps to fit `max_side`."""
        image = self
        if max_side:
            biggest = max(1, image.width, image.height)
            if biggest > max_side:
                factor = -(-biggest // max_side)
                image = image.resized(max(1, image.width // factor), max(1, image.height // factor))
        return tk_mod.PhotoImage(master=master, data=base64.b64encode(image.to_png()))


def _resample_weights(src: int, dst: int) -> list:
    """For each output position, (first source index, weights) of a triangle filter."""
    scale = dst / src
    support = max(1.0, 1.0 / scale)
    out = []
    for i in range(dst):
        centre = (i + 0.5) / scale
        lo = max(0, int(centre - support))
        hi = min(src, int(centre + support) + 1)
        weights = [max(0.0, 1.0 - abs((j + 0.5 - centre) / support)) for j in range(lo, hi)]
        total = sum(weights)
        if total <= 0:
            out.append((min(src - 1, max(0, int(centre))), [1.0]))
            continue
        while weights and weights[0] == 0.0:
            weights.pop(0)
            lo += 1
        while weights and weights[-1] == 0.0:
            weights.pop()
        out.append((lo, [w / total for w in weights]))
    return out


# ------------------------------------------------------------------ the game's scaled draw


def f32(value: float) -> float:
    """value rounded to a C float, as the game's single-precision (SSE) arithmetic rounds each step."""
    return struct.unpack("<f", struct.pack("<f", value))[0]


def scaled_link(value: int, scale: float) -> int:
    """CAnimManager::GetScaledLinkTo{Next,Prev}Pt: (int)(value * scale + 0.5), each step a float."""
    return int(f32(f32(value * f32(scale)) + 0.5))


def game_scaled_cell(sheet: Image, rect: tuple, percent: int) -> Image:
    """A cell drawn the way ldwGameWindowImpl::BlitRectWithAlpha draws it at `percent` (below 100; 100 is
    the cell itself): trunc(w * s) by trunc(h * s) pixels, s = percent / 100 as a float; each pixel the
    average (every channel, alpha too, each sum divided with C's truncation) of the source block under it.
    The block edges come from a double that starts half a step before the cell and grows by w / width
    (h / height) one pixel at a time; a block ends at trunc(edge) + 1 (never past the cell) and the next
    starts after it. The game blends a pixel onto the screen as (colour * a + 127 + under * (255 - a)) >> 8;
    on a clear picture the pixel is kept as (colour, a)."""
    left, top, right, bottom = rect
    w, h = right - left, bottom - top
    if percent >= 100:
        if percent > 100:
            raise PictureError("the game's people are never drawn above their own size")
        return sheet.sub(left, top, w, h)
    s = f32(percent / 100.0)
    dw, dh = int(f32(w * s)), int(f32(h * s))
    out = Image(max(0, dw), max(0, dh))
    if dw <= 0 or dh <= 0:
        return out
    rx, ry = w / dw, h / dh
    last_x, last_y = left + w - 1, top + h - 1
    cols = []
    acc, end = float(left) - rx * 0.5, left - 1
    for _ in range(dw):
        acc += rx
        start = end + 1
        end = min(int(acc) + 1, last_x)
        cols.append((start, end))
    rows = []
    acc, end = float(top) - ry * 0.5, top - 1
    for _ in range(dh):
        acc += ry
        start = end + 1
        end = min(int(acc) + 1, last_y)
        rows.append((start, end))
    src, sw, dst = sheet.data, sheet.width, out.data
    for j, (y0, y1) in enumerate(rows):
        if y0 > y1:
            continue
        for i, (x0, x1) in enumerate(cols):
            if x0 > x1:
                continue
            sums = [0, 0, 0, 0]
            for yy in range(y0, y1 + 1):
                at = (yy * sw + x0) * 4
                block = src[at:at + (x1 - x0 + 1) * 4]
                sums[0] += sum(block[0::4])
                sums[1] += sum(block[1::4])
                sums[2] += sum(block[2::4])
                sums[3] += sum(block[3::4])
            n = (x1 - x0 + 1) * (y1 - y0 + 1)
            a = sums[3] // n
            if a == 0:
                continue
            o = (j * dw + i) * 4
            dst[o], dst[o + 1], dst[o + 2], dst[o + 3] = sums[0] // n, sums[1] // n, sums[2] // n, a
    return out


def game_blend(under: tuple, pixel: tuple) -> tuple:
    """One scaled pixel (colour, a) blended onto an opaque screen pixel as the game's blitter does."""
    r, g, b, a = pixel
    if a == 0:
        return tuple(under)
    keep = 255 - a
    return tuple((c * a + 0x7F + u * keep) >> 8 for c, u in zip((r, g, b), under))


# ------------------------------------------------------------------ PNG


def _chunks(data: bytes):
    if not data.startswith(PNG_MAGIC):
        raise PictureError("not a PNG file")
    at = 8
    while at + 8 <= len(data):
        length, kind = struct.unpack_from(">I4s", data, at)
        body = data[at + 8:at + 8 + length]
        if len(body) != length:
            raise PictureError("the PNG file is cut short")
        yield kind, body
        at += 12 + length
        if kind == b"IEND":
            return


def _unfilter(raw: bytes, height: int, bpp: int, row_bytes: int) -> bytearray:
    """Undo the PNG row filters (None, Sub, Up, Average, Paeth)."""
    out = bytearray(height * row_bytes)
    prev = bytearray(row_bytes)
    at = 0
    for y in range(height):
        kind = raw[at]
        line = bytearray(raw[at + 1:at + 1 + row_bytes])
        at += 1 + row_bytes
        if len(line) != row_bytes:
            raise PictureError("the PNG image data is cut short")
        if kind == 1:
            for i in range(bpp, row_bytes):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif kind == 2:
            line = bytearray((a + b) & 0xFF for a, b in zip(line, prev))
        elif kind == 3:
            for i in range(row_bytes):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(row_bytes):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif kind != 0:
            raise PictureError(f"the PNG uses an unknown row filter ({kind})")
        out[y * row_bytes:(y + 1) * row_bytes] = line
        prev = line
    return out


def decode_png(data: bytes) -> Image:
    """A non-interlaced 8-bit RGBA, RGB, grey or grey+alpha PNG, or a palette PNG, as straight RGBA. The
    colour profile and gamma chunks are ignored, as the game's loader ignores them: the bytes are the
    picture."""
    header, palette, trns, idat = None, b"", None, []
    for kind, body in _chunks(bytes(data)):
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat.append(body)
    if header is None:
        raise PictureError("the PNG has no header")
    width, height, depth, colour, _comp, _filter, interlace = header
    if interlace:
        raise PictureError("interlaced PNGs are not read")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour)
    if channels is None or depth != 8:
        raise PictureError("the PNG's colour format is not one the game uses")
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        raise PictureError(f"the PNG image data could not be unpacked ({exc})") from None
    row_bytes = width * channels
    rows = _unfilter(raw, height, channels, row_bytes)
    image = Image(width, height)
    out = image.data
    if colour == 6:
        out[:] = rows
    elif colour == 2:
        out[0::4], out[1::4], out[2::4] = rows[0::3], rows[1::3], rows[2::3]
        out[3::4] = b"\xff" * (width * height)
    elif colour == 4:
        out[0::4] = out[1::4] = out[2::4] = rows[0::2]
        out[3::4] = rows[1::2]
    elif colour == 0:
        out[0::4] = out[1::4] = out[2::4] = rows
        out[3::4] = b"\xff" * (width * height)
    else:
        alpha = list(trns or b"") + [255] * 256
        table = [bytes(palette[i * 3:i * 3 + 3].ljust(3, b"\0")) + bytes([alpha[i]]) for i in range(256)]
        out[:] = b"".join(table[v] for v in rows)
    return image


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def encode_png(image: Image) -> bytes:
    """An 8-bit RGBA PNG (colour type 6), every row unfiltered (Up for a row that repeats)."""
    stride = image.width * 4
    raw = bytearray()
    prev = bytes(stride)
    for y in range(image.height):
        row = bytes(image.data[y * stride:(y + 1) * stride])
        raw += (b"\x02" + bytes(stride)) if (row == prev and y) else (b"\x00" + row)
        prev = row
    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0)
    return PNG_MAGIC + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) \
        + _chunk(b"IEND", b"")


def _gdiplus_decode(path: Path) -> Image | None:
    """The PNG through Windows' GDI+ (32 bpp ARGB, not premultiplied: the file's own bytes), as RGBA; None
    where GDI+ is not there or cannot read it. tests/test_picture_maker.py checks it against decode_png."""
    if sys.platform != "win32":
        return None
    try:
        import vf2_gdiplus as gp
    except ImportError:
        return None
    with gp._LOCK:
        try:
            gdi = gp._Gdi()
        except OSError:
            return None
        g = gdi.g
        bitmap = ctypes.c_void_p()
        try:
            if g.GdipCreateBitmapFromFile(ctypes.c_wchar_p(str(path)), ctypes.byref(bitmap)) != 0:
                return None
            w, h = ctypes.c_uint(), ctypes.c_uint()
            g.GdipGetImageWidth(bitmap, ctypes.byref(w))
            g.GdipGetImageHeight(bitmap, ctypes.byref(h))
            rect, data = gp._Rect(0, 0, w.value, h.value), gp._BitmapData()
            if g.GdipBitmapLockBits(bitmap, ctypes.byref(rect), 1, gp.PIXEL_FORMAT_32BPP_ARGB, ctypes.byref(data)):
                return None
            try:
                stride, width, height = data.Stride, w.value, h.value
                raw = ctypes.string_at(data.Scan0, stride * height)
            finally:
                g.GdipBitmapUnlockBits(bitmap, ctypes.byref(data))
        finally:
            if bitmap:
                g.GdipDisposeImage(bitmap)
            gdi.close()
    rows = raw if stride == width * 4 else b"".join(raw[y * stride:y * stride + width * 4] for y in range(height))
    image = Image(width, height, rows)
    d = image.data
    d[0::4], d[2::4] = rows[2::4], rows[0::4]          # B, G, R, A -> R, G, B, A
    return image


def _is_rgba8(path: Path) -> bool:
    head = Path(path).read_bytes()[:33]
    return head[:8] == PNG_MAGIC and head[24] == 8 and head[25] == 6 and head[28] == 0


def load_png(path, fast: bool = True) -> Image:
    """A PNG file as straight RGBA. The game's sheets are 8-bit RGBA; those are read through GDI+ when it is
    there (the same bytes), anything else by decode_png."""
    path = Path(path)
    try:
        if fast and _is_rgba8(path):
            image = _gdiplus_decode(path)
            if image is not None:
                return image
        return decode_png(path.read_bytes())
    except OSError as exc:
        raise PictureError(f"{path.name} could not be read ({exc.strerror or exc})") from None


# ------------------------------------------------------------------ export


def export(image: Image, *, scale: int = 1, size=None, margin: int = MARGIN) -> Image:
    """Crop to the drawn pixels plus `margin` (0: none), then scale: `scale` crisply (nearest neighbour) or
    `size=(w, h)` smoothly; a 0 in size keeps the shape."""
    out = image.cropped(max(0, int(margin)))
    if size is not None:
        w, h = (int(v or 0) for v in size)
        if w <= 0 and h <= 0:
            raise PictureError("Give a width, a height or both.")
        if w <= 0:
            w = max(1, round(out.width * h / out.height))
        if h <= 0:
            h = max(1, round(out.height * w / out.width))
        if w > MAX_SIDE or h > MAX_SIDE:
            raise PictureError(f"A picture can be at most {MAX_SIDE} pixels wide or high.")
        return out.resized(w, h)
    scale = int(scale)
    if scale < 1 or out.width * scale > MAX_SIDE or out.height * scale > MAX_SIDE:
        raise PictureError(f"A picture can be at most {MAX_SIDE} pixels wide or high.")
    return out.scaled(scale)


def save_png(image: Image, path, **options) -> Path:
    """Export (see `export`) and write the PNG through a temporary file beside it, so a failed write never leaves
    half a file."""
    path = Path(path)
    data = export(image, **options).to_png()
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return path


_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_file_name(text: str, limit: int = 80) -> str:
    """A label as a Windows file name (no extension): forbidden characters become "-", no trailing dot or space,
    never a reserved device name, never empty."""
    name = _BAD.sub("-", str(text)).strip().rstrip(". ")[:limit].rstrip(". ")
    if not name:
        name = "picture"
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return name


def unique_path(folder: Path, stem: str, suffix: str = ".png") -> Path:
    """folder/stem.png, or "stem (2).png" and so on when that name is taken."""
    path = Path(folder) / f"{stem}{suffix}"
    n = 2
    while path.exists():
        path = Path(folder) / f"{stem} ({n}){suffix}"
        n += 1
    return path
