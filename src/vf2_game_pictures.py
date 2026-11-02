"""The Picture Maker's "Every picture" catalogue: every picture in Virtual Families 2's Images folder (and the
patcher's own), each file whole and cut into every cell the game cuts it into, and the pictures the game
assembles from several draws (meters and bars, buttons in their states, dialogs, the house, weather and night,
fonts), each drawn as the game draws it. Read from the chosen game folder at run time; no game art ships with
the patcher, and nothing is written but the PNGs the player saves.

Where the rules come from (the B200 desktop objects, work/desktop_obj_files, which keep the game's symbols):

* theGraphicsManager's image table (ImageList, src/vf2_game_pictures.json, made by
  scripts/build_vf2_image_table.py): 633 entries, 0x30 bytes each. theGraphicsManagerImpl::GetImage /
  GetImageStrip / GetImageGrid make from an entry an ldwImageGrid of columns x rows cells (rows > 0; one file, or
  the files <file><x><y><file2> side by side), an ldwImageStrip of one row (rows 0, columns > 0) or a whole
  ldwImage. ldwImageGrid::GetCellRect gives each cell (`entry_cells`); tests/test_game_pictures.py runs both in
  Unicorn for every entry.
* A cell drawn at 100% with no fade is the cell's own pixels (ldwGameWindowImpl::BlitRectWithAlpha; checked in
  tests/test_picture_maker.py). PNGs are read as the game's libpng reads them; JPEGs by vf2_jpeg, byte for byte
  as the game's own libjpeg-9.dll decodes them for SDL2_image (tests/test_jpeg_decoder.py).

Each catalogue entry is an `Art`: the layers (`Draw`, `Fill`) in the order the game draws them, whether the game
ever shows it (`why` names the code that does, or says why nothing does), and how it was checked against the game
(`checked`; empty when it was not, which the window shows as "Not checked against the game"). The assembled
pictures come from the vf2_art_*.py modules (`_sources`).
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import vf2_picture_image as pi

DATA_FILE = Path(__file__).resolve().parent / "vf2_game_pictures.json"
TREE_PICTURES = Path(__file__).resolve().parent / "family_tree_backgrounds"
IMAGES_DIR = "Images"
CHECK = "Not checked against the game"
PATCHER_CATEGORY = "Patcher's own pictures"

# The top-level categories, in the order the window lists them ("/" makes a sub-category); the same as the
# Virtual Families 1 patcher's Every picture tab.
CATEGORY_ORDER = (
    "Meters and bars",
    "Buttons and controls",
    "Dialogs and panels",
    "Icons and cursors",
    "Fonts",
    "House and yard",
    "Furniture and objects",
    "Food and cooking",
    "Weather, day and night",
    "Effects and animations",
    "Animals and insects",
    "People",
    "Store",
    "Collectibles and collections",
    "Screens and backgrounds",
    PATCHER_CATEGORY,
)


# ------------------------------------------------------------------ the image table
_DATA: dict | None = None


def data() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return _DATA


@dataclass(frozen=True)
class Entry:
    """One entry of theGraphicsManager's image table."""
    id: int
    file: str
    file2: str | None
    cols: int
    rows: int
    across: int
    down: int

    @property
    def kind(self) -> str:
        return "grid" if self.rows > 0 else ("strip" if self.cols > 0 else "image")

    @property
    def files(self) -> list[str]:
        if self.kind == "grid" and self.across * self.down > 1:
            return [f"{self.file}{x}{y}{self.file2 or ''}" for y in range(self.down) for x in range(self.across)]
        return [self.file]

    @property
    def cells(self) -> int:
        """theGraphicsManager::GetCellCount: columns x rows, a strip its columns, a whole picture 1."""
        if self.rows:
            return self.cols * self.rows
        return self.cols or 1

    @property
    def name(self) -> str:
        return f"{self.file}{self.file2 or ''}" if self.across * self.down > 1 else self.file


_TABLE: list | None = None
_BY_ID: dict | None = None


def table() -> list[Entry]:
    """The image table's entries in its order ("No Graphic" left out); made once."""
    global _TABLE
    if _TABLE is None:
        _TABLE = [Entry(e["id"], e["file"], e["file2"], e["cols"], e["rows"], e["across"], e["down"])
                  for e in data()["table"] if e["file"] and e["file"] != "No Graphic"]
    return list(_TABLE)


def entry_by_id(image: int) -> Entry:
    """The entry GetImageEntry finds for an id: the first in the table's order."""
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = {}
        for entry in table():
            _BY_ID.setdefault(entry.id, entry)
    return _BY_ID[image]


def entry_cells(files: "GameFiles", entry: Entry) -> list[tuple[str, tuple]]:
    """Every cell of an entry in the game's order (cell i is column i % columns, row i // columns): its file and
    rectangle (left, top, right, bottom), as ldwImageGrid's constructors and GetCellRect make them (the game's own
    quirks kept: over several files the total width is the last row of files', the total height the sum of each
    row's last file)."""
    if entry.kind == "image":
        w, h = files.size(entry.file)
        return [(entry.file, (0, 0, w, h))]
    cols, rows = entry.cols, max(1, entry.rows)
    if entry.kind == "grid" and entry.across * entry.down > 1:
        names = entry.files
        total_w = total_h = 0
        for y in range(entry.down):
            row_w, last_h = 0, 0
            for x in range(entry.across):
                w, h = files.size(names[y * entry.across + x])
                row_w += w
                last_h = h
            total_w = row_w
            total_h += last_h
        first_w, first_h = files.size(names[0])
        cw, ch = total_w // cols, total_h // rows
        per_x, per_y = first_w // cw, first_h // ch
        out = []
        for i in range(cols * rows):
            col, row = i % cols, i // cols
            index = entry.across * (row // per_y) + col // per_x
            if index >= entry.across * entry.down:
                index %= entry.across * entry.down
            c, r = col % per_x, row % per_y
            c = c if c < cols else cols - 1
            r = r if r < rows else rows - 1
            out.append((names[index], (c * cw, r * ch, c * cw + cw, r * ch + ch)))
        return out
    w, h = files.size(entry.file)
    cw, ch = w // cols, h // rows
    return [(entry.file, ((i % cols) * cw, (i // cols) * ch, (i % cols) * cw + cw, (i // cols) * ch + ch))
            for i in range(cols * rows)]


def cell_of(files: "GameFiles", image: int, cell: int = 0) -> tuple[str, tuple]:
    """(file, rectangle) of one cell of an image id (cell 0 of a whole picture is the whole file)."""
    cache = files.__dict__.setdefault("_cells", {})
    cells = cache.get(image)
    if cells is None:
        cells = cache[image] = entry_cells(files, entry_by_id(image))
    return cells[min(max(cell, 0), len(cells) - 1)]


# ------------------------------------------------------------------ the pieces of a picture
@dataclass(frozen=True)
class Draw:
    """One draw the game makes: the rectangle `rect` (left, top, right, bottom; (0, 0, -1, -1) is the whole
    picture, see `resolve`) of the picture `file` at (x, y). `percent` below 100 is the game's scaled blit
    (vf2_picture_image.game_scaled_cell); `alpha` below 1 fades it (every pixel's alpha times `alpha`, as
    BlitRectWithAlpha's opacity); `tint` (r, g, b, 0-255) a coloured copy (a font's colour); `make(files)` instead
    gives the pixels a module computes (a night fill, a haze). `file` names a picture in the game's Images folder,
    "root:<name>" a file beside the exe, or "patcher:<path>" one of the patcher's own."""
    file: str
    rect: tuple = (0, 0, -1, -1)
    x: int = 0
    y: int = 0
    percent: int = 100
    alpha: float = 1.0
    tint: tuple | None = None
    make: Callable | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Fill:
    """A solid rectangle the game fills (x, y, width, height) with an RGBA colour (0-255 each)."""
    x: int
    y: int
    w: int
    h: int
    rgba: tuple


@dataclass(frozen=True)
class Art:
    """One picture in the catalogue. `layers` are Draw / Fill in the order the game draws them.
    `used`: the game shows it (`why` names the code that does), or not (`why` says why it never does).
    `checked`: how it was checked against the game; empty when it was not."""
    key: str
    category: str
    label: str
    layers: tuple
    used: bool
    why: str
    checked: str = ""
    patcher: bool = False

    @property
    def title(self) -> str:
        tags = []
        if not self.used:
            tags.append("(unused)")
        if self.patcher:
            tags.append("(patcher)")
        return " ".join([self.label, *tags])

    def note(self) -> str:
        words = [self.why, self.checked if self.checked else f"{CHECK}."]
        return " ".join(w for w in words if w)


def whole(name: str, x: int = 0, y: int = 0) -> Draw:
    """A draw of a whole picture (its size is filled in when it is drawn: see `resolve`)."""
    return Draw(name, (0, 0, -1, -1), x, y)


def cell(files: "GameFiles", image: int, index: int = 0, x: int = 0, y: int = 0, **kw) -> Draw:
    """A draw of one cell of an image-table picture, as theGraphicsManager::DrawCell / ldwGameWindow::Draw
    (ldwImageGrid, cell) draw it."""
    name, rect = cell_of(files, image, index)
    return Draw(name, rect, x, y, **kw)


# ------------------------------------------------------------------ reading the pictures
def png_size(data_: bytes) -> tuple[int, int]:
    if not data_.startswith(pi.PNG_MAGIC):
        raise pi.PictureError("not a PNG file")
    return struct.unpack(">II", data_[16:24])


def jpeg_size(data_: bytes) -> tuple[int, int]:
    at = 2
    while at + 4 <= len(data_):
        if data_[at] != 0xFF:
            at += 1
            continue
        marker = data_[at + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            at += 1 if marker == 0xFF else 2
            continue
        length = struct.unpack(">H", data_[at + 2:at + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data_[at + 5:at + 9])
            return w, h
        at += 2 + length
    raise pi.PictureError("not a JPEG file")


def decode(path: Path, data_: bytes | None = None) -> pi.Image:
    """A picture file's pixels as straight RGBA, as the game's loader (SDL2_image) gives them."""
    path = Path(path)
    head = data_[:8] if data_ is not None else path.read_bytes()[:8]
    if head.startswith(pi.PNG_MAGIC):
        return pi.load_png(path)
    raw = data_ if data_ is not None else path.read_bytes()
    if raw[:2] == b"\xff\xd8":
        import vf2_jpeg
        return vf2_jpeg.decode(raw)
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        import vf2_small_formats
        return vf2_small_formats.decode_gif(raw)
    if raw[:2] == b"BM":
        import vf2_small_formats
        return vf2_small_formats.decode_bmp(raw)
    raise pi.PictureError(f"{path.name} is not a picture the Picture Maker can read")


def load_picture(path) -> pi.Image:
    """A picture file's pixels (see `decode`)."""
    return decode(Path(path))


class GameFiles:
    """The pictures of one game folder, found as Windows finds them (ignoring case), decoded once."""

    def __init__(self, folder) -> None:
        self.folder = Path(folder) if folder else None
        if self.folder is not None and self.folder.name.lower() == IMAGES_DIR.lower():
            self.folder = self.folder.parent
        self._names: dict[str, Path] | None = None
        self._cache: dict[str, pi.Image] = {}
        self._sizes: dict[str, tuple[int, int]] = {}

    @property
    def images(self) -> Path | None:
        return self.folder / IMAGES_DIR if self.folder is not None else None

    def problem(self) -> str:
        if self.folder is None:
            return "Choose your Virtual Families 2 game folder."
        if not (self.folder / IMAGES_DIR).is_dir():
            return f"{self.folder} has no Images folder: choose the folder Virtual Families 2 is installed in."
        return ""

    def names(self) -> dict[str, Path]:
        """lower-case path relative to Images ('furniture/hammockstd.png') -> the file."""
        if self._names is None:
            found: dict[str, Path] = {}
            root = self.images
            if root is not None and root.is_dir():
                for dirpath, _dirs, names in os.walk(root):
                    for f in names:
                        path = Path(dirpath) / f
                        found[path.relative_to(root).as_posix().lower()] = path
            self._names = found
        return self._names

    def relative(self, lower: str) -> str:
        """The real spelling of a file under Images."""
        path = self.names()[lower]
        return path.relative_to(self.images).as_posix()

    def path(self, name: str) -> Path | None:
        if name.startswith("patcher:"):
            path = Path(name[len("patcher:"):])
            return path if path.is_file() else None
        if name.startswith("root:"):
            path = self.folder / name[len("root:"):] if self.folder else None
            return path if path is not None and path.is_file() else None
        return self.names().get(name.replace("\\", "/").lower())

    def has(self, name: str) -> bool:
        return self.path(name) is not None

    def data(self, name: str) -> bytes:
        path = self.path(name)
        if path is None:
            raise pi.PictureError(f"The game folder has no {name}.")
        return path.read_bytes()

    def size(self, name: str) -> tuple[int, int]:
        key = name.lower()
        if key not in self._sizes:
            if key in self._cache:
                image = self._cache[key]
                self._sizes[key] = (image.width, image.height)
            else:
                path = self.path(name)
                if path is None:
                    raise pi.PictureError(f"The game folder has no {name}.")
                with open(path, "rb") as fh:
                    head = fh.read(64 * 1024)
                if head.startswith(pi.PNG_MAGIC):
                    self._sizes[key] = png_size(head)
                elif head[:2] == b"\xff\xd8":
                    try:
                        self._sizes[key] = jpeg_size(head)
                    except pi.PictureError:
                        self._sizes[key] = jpeg_size(path.read_bytes())
                else:
                    image = self.image(name)
                    self._sizes[key] = (image.width, image.height)
        return self._sizes[key]

    def image(self, name: str) -> pi.Image:
        key = name.lower()
        if key not in self._cache:
            path = self.path(name)
            if path is None:
                raise pi.PictureError(f"The game folder has no {name}.")
            self._cache[key] = decode(path)
        return self._cache[key]

    def forget(self) -> None:
        """Let go of the decoded pictures (Save all frees them as it goes)."""
        self._cache.clear()


# ------------------------------------------------------------------ drawing
def faded(image: pi.Image, alpha: float) -> pi.Image:
    """Every pixel's alpha times `alpha` (a float, as the game's fade): (int)(a * alpha)."""
    if alpha >= 1.0:
        return image
    out = image.copy()
    k = pi.f32(alpha)
    d = out.data
    for i in range(3, len(d), 4):
        if d[i]:
            d[i] = int(pi.f32(d[i] * k))
    return out


def tinted(image: pi.Image, rgb: tuple) -> pi.Image:
    """A coloured copy: every pixel's colour times the tint (c * t / 255), its alpha kept."""
    out = image.copy()
    d = out.data
    r, g, b = rgb[:3]
    for i in range(0, len(d), 4):
        d[i] = d[i] * r // 255
        d[i + 1] = d[i + 1] * g // 255
        d[i + 2] = d[i + 2] * b // 255
    return out


def layer_image(files: GameFiles, layer) -> pi.Image:
    if isinstance(layer, Fill):
        image = pi.Image(max(0, layer.w), max(0, layer.h))
        image.data[:] = bytes(layer.rgba) * (image.width * image.height)
        return image
    if layer.make is not None:
        return layer.make(files)
    sheet = files.image(layer.file)
    left, top, right, bottom = layer.rect
    if layer.percent < 100:
        image = pi.game_scaled_cell(sheet, (left, top, right, bottom), layer.percent)
    else:
        image = sheet.sub(left, top, right - left, bottom - top)
    if layer.tint is not None and tuple(layer.tint[:3]) != (255, 255, 255):
        image = tinted(image, layer.tint)
    return faded(image, layer.alpha)


def render(files: GameFiles, art: Art) -> pi.Image:
    """The picture as the game draws it, on a clear canvas as big as all its draws."""
    pieces = []
    for layer in art.layers:
        image = layer_image(files, layer)
        pieces.append((image, layer.x, layer.y))
    pieces = [p for p in pieces if p[0].width and p[0].height]
    if not pieces:
        return pi.Image(1, 1)
    left = min(x for _i, x, _y in pieces)
    top = min(y for _i, _x, y in pieces)
    right = max(x + i.width for i, x, _y in pieces)
    bottom = max(y + i.height for i, _x, y in pieces)
    canvas = pi.Image(right - left, bottom - top)
    for image, x, y in pieces:
        canvas.draw(image, x - left, y - top)
    return canvas


def resolve(files: GameFiles, art: Art) -> Art:
    """`art` with every whole-picture draw given the picture's size."""
    layers, changed = [], False
    for layer in art.layers:
        if isinstance(layer, Draw) and layer.make is None and tuple(layer.rect) == (0, 0, -1, -1):
            w, h = files.size(layer.file)
            layer = Draw(layer.file, (0, 0, w, h), layer.x, layer.y, layer.percent, layer.alpha, layer.tint)
            changed = True
        layers.append(layer)
    if not changed:
        return art
    return Art(art.key, art.category, art.label, tuple(layers), art.used, art.why, art.checked, art.patcher)


def draw(files: GameFiles, art: Art) -> pi.Image:
    return render(files, resolve(files, art))


# ------------------------------------------------------------------ the patcher's pictures
def _is_picture(rel: str) -> bool:
    return rel.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def patcher_files(files: GameFiles) -> dict:
    """Images files that are not the clean game's: new ones and changed ones (real relative path -> "new" /
    "changed"). A file the clean game has with the same size is hashed; a different size is a change."""
    stock = {k.lower(): v for k, v in data()["stock"].items()}
    out = {}
    for low, path in files.names().items():
        rel = files.relative(low)
        if not _is_picture(rel):
            continue
        known = stock.get(low)
        if known is None:
            out[rel] = "new"
        elif path.stat().st_size != known[0] or _sha256(path) != known[1]:
            out[rel] = "changed"
    return out


# ------------------------------------------------------------------ the catalogue
@dataclass
class Catalogue:
    arts: list = field(default_factory=list)
    problems: list = field(default_factory=list)       # parts that could not be listed, in words

    def categories(self) -> list[str]:
        seen: list[str] = []
        for art in self.arts:
            if art.category not in seen:
                seen.append(art.category)
        return seen

    def find(self, text: str) -> list[Art]:
        words = [w for w in str(text or "").casefold().split() if w]
        if not words:
            return list(self.arts)
        out = []
        for art in self.arts:
            hay = " ".join((art.category, art.title, art.key, art.why)).casefold()
            if all(w in hay for w in words):
                out.append(art)
        return out

    def by_key(self, key: str) -> Art | None:
        for art in self.arts:
            if art.key == key:
                return art
        return None


SOURCE_MODULES = ("vf2_art_sheets", "vf2_art_meters", "vf2_art_ui", "vf2_art_house", "vf2_art_misc", "vf2_art_screens",
                  "vf2_art_fonts")


def _sources():
    """The catalogue's parts, in the order they are listed (each a module with `arts(files) -> list[Art]`)."""
    out = []
    for name in SOURCE_MODULES:
        try:
            out.append(__import__(name))
        except ImportError:
            continue
    return out


def catalogue(files: GameFiles) -> Catalogue:
    cat = Catalogue()
    if files.problem():
        cat.problems.append(files.problem())
        return cat
    seen = set()
    for source in _sources():
        try:
            arts = source.arts(files)
        except Exception as exc:                   # a part that cannot be listed is said, never raised
            cat.problems.append(f"{getattr(source, 'TITLE', source.__name__)}: {exc}")
            continue
        for art in arts:
            if art.key in seen:
                raise ValueError(f"two pictures have the key {art.key}")
            seen.add(art.key)
            cat.arts.append(art)
    order = {c: k for k, c in enumerate(CATEGORY_ORDER)}
    cat.arts.sort(key=lambda a: order.get(a.category.split("/")[0], len(order)))
    return cat
