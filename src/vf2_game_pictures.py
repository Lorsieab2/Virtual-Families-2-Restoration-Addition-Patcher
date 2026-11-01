"""The Picture Maker's "All game pictures": every picture Virtual Families 2 has, drawn as the game draws it.

What there is (src/vf2_game_pictures.json, made by scripts/build_vf2_image_table.py from the B200 desktop objects):

* theGraphicsManager's image table, 633 entries: every sprite, sheet, icon, button, panel, background and
  animation the game draws through it. Each entry is a whole picture, a strip (one row of cells) or a grid
  (columns x rows cells, one file or several side by side), cut exactly as ldwImageGrid's constructors and
  GetCellRect cut it: a cell is the total width / columns by the total height / rows (C division), a column or row
  past the last is the last; a grid over several files finds its file from the cell (the game's own quirks kept:
  the total width is the last row of files', the total height the sum of each row's last file). Every cell is
  offered: animation frames, furniture turned each way, button states, the people's sheets.
* The other files of the Images folder: named in the code (the house map tiles CWorldMap loads by
  "MapX%dY%d.jpg", the fonts, the splash screen) or named nowhere: unused, said so with the reason.
* Files the table names that a game folder does not have: listed as missing (the game cannot draw them).
* Assembled bars: the game's three percent meters drawn whole, at any level (meters below). Only
  theContinuousVariableMeter is used (the Details screen's five bars and the loading bar); theVariableMeter and
  theSlicedVariableMeter are never called: unused, drawn by their own code all the same.
* The patcher's pictures: any file of the chosen game folder that a clean install does not have, or has with
  other bytes (the patcher's furniture, outfits, ornaments, map images), marked "(patcher)".

A cell is drawn at its own size, which is how the game blits it (ldwGameWindowImpl::BlitRectWithAlpha at 100% is
the cell itself; checked in tests/test_picture_maker.py). PNGs are read byte for byte as the game reads them; a
JPEG (or GIF) is decoded by Windows (GDI+), not the game's libjpeg, so its pixels are "not checked against the
game". Nothing is written but the PNGs the player saves; the game folder is only read.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import vf2_picture_image as pi

DATA_FILE = Path(__file__).resolve().parent / "vf2_game_pictures.json"
NOT_CHECKED = "not checked against the game"
UNUSED, PATCHER, MISSING = "unused", "patcher", "missing"
NOT_PICTURES = (".db", ".jbf", ".css", ".txt", ".ini", ".dat", ".fmap", ".ogg", ".wav", ".swf")

CATEGORIES = (
    "People", "Pets", "Furniture", "Upgrades", "Rooms and the house", "Weather and nature",
    "Effects and animations", "Work and food props", "Store and tray icons", "Collectibles and collections",
    "Goals and trophies", "Buttons and controls", "Dialogs and panels", "Meters and bars", "Meters assembled",
    "Screens and backgrounds", "Fonts", "Cursors", "Other", "The patcher's pictures",
)

_RULES = (
    ("People", r"^(female_|male_|bigheads|highrez_bodies|peep_shadow|carrying\.png)"),
    ("Pets", r"^(pet_|petbowls)"),
    ("Furniture", r"^furniture/"),
    ("Upgrades", r"^(upgrades/|old_computer)"),
    ("Collectibles and collections", r"^(collection|fossil|pterodactyl|collectables_small)"),
    ("Goals and trophies", r"^(achievement|awards_)"),
    ("Meters and bars", r"^(vd_progressbar|vd_line|vd_fade|loadscenebarbg|loadcolor|statusbarslice)"),
    ("Store and tray icons", r"(_icon\.png$|^inventoryitems|^home_grid|^menustore|^meunstore|^coins|^dollar|"
                             r"^onsale|^locked|^scrollingstoreitembox|^getmorecoins|^storagecube|^decormodetab|"
                             r"^upgrademebutton|^brokerupgrade)"),
    ("Buttons and controls", r"(^btn_|button|^menubtn|^fbtn_|^vd_btn|^radio|^checkbox|^checkmark|^arrow|^empty1|"
                             r"^touchtoselect|^inisible|^invisible|^slider|^wideslider|^verticalslider|"
                             r"^focus_circle)"),
    ("Dialogs and panels", r"(dlg|^maintooltray|^main_no-comm|^money_console|^familytree_|^statusbar)"),
    ("Rooms and the house", r"^(damage_|foundation_|bathroom2foundation|closed_door|closes_door|curtain|mapx|"
                            r"house\.jpg|hill\.jpg|puddles|kitchengarbage|fridgestates|hole|gopher|rosepetals|"
                            r"sockpile|map_fog)"),
    ("Weather and nature", r"^(snowflake|hailstone|leaf\d|raindrops|sunbeam|bird|dragonflies|butterfly|"
                           r"hummingbird|rainbow|lightsourcemask|ripple|waves|algae|reeffish|beestrip)"),
    ("Work and food props", r"^(foodwork|workwork|workdocs|chopgreens|breads|cans|meal|bbqmeat|antpuzzle|"
                            r"cinnamonbowl|greenlight|redlight|airpurifier)"),
    ("Effects and animations", r"(strip|_anim|anim|sparkle|^dust|^bubble|^foam|^spray|^footprints|^smoke|^roach|"
                               r"^candle|^petal|malfunction|^ball_shadow)"),
    ("Fonts", r"^segoe"),
    ("Cursors", r"^hand"),
    ("Screens and backgrounds", r"(\.jpg$|^main_bg|logo|^vd_bg|^splash|^vf2_boxshot)"),
)


def category_of(file: str) -> str:
    name = file.replace("\\", "/").lower()
    for category, rule in _RULES:
        if re.search(rule, name):
            return category
    return "Other"


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


def table() -> list[Entry]:
    return [Entry(e["id"], e["file"], e["file2"], e["cols"], e["rows"], e["across"], e["down"])
            for e in data()["table"] if e["file"] and e["file"] != "No Graphic"]


# ------------------------------------------------------------------ reading pictures


def load_picture(path: Path) -> pi.Image:
    """A PNG as the game reads it (its bytes); anything else (JPEG, GIF) through Windows' GDI+."""
    path = Path(path)
    if path.suffix.lower() == ".png":
        return pi.load_png(path)
    image = pi._gdiplus_decode(path)
    if image is None:
        raise pi.PictureError(f"{path.name} can be read only on Windows (GDI+).")
    return image


class Folder:
    """A game folder's Images, each file read once."""

    def __init__(self, game_folder) -> None:
        self.folder = Path(game_folder) if game_folder else None
        self._pictures: dict = {}
        self._sizes: dict = {}
        self._index: dict | None = None

    @property
    def images(self) -> Path | None:
        return self.folder / "Images" if self.folder is not None else None

    def index(self) -> dict:
        """Every file under Images: lower-case relative path -> real relative path (Windows does not care about
        case; the table and the folder sometimes differ)."""
        if self._index is None:
            self._index = {}
            if self.images is not None and self.images.is_dir():
                for root, _dirs, files in os.walk(self.images):
                    for name in files:
                        rel = os.path.relpath(os.path.join(root, name), self.images).replace(os.sep, "/")
                        self._index[rel.lower()] = rel
        return self._index

    def has(self, rel: str) -> bool:
        return rel.replace("\\", "/").lower() in self.index()

    def path(self, rel: str) -> Path:
        real = self.index().get(rel.replace("\\", "/").lower())
        if real is None:
            raise pi.PictureError(f"Images/{rel} is not in {self.folder}.")
        return self.images / real

    def picture(self, rel: str) -> pi.Image:
        key = rel.replace("\\", "/").lower()
        if key not in self._pictures:
            self._pictures[key] = load_picture(self.path(rel))
        return self._pictures[key]

    def size(self, rel: str) -> tuple[int, int]:
        """A picture's width and height without decoding it (the PNG header; else the picture)."""
        key = rel.replace("\\", "/").lower()
        if key not in self._sizes:
            path = self.path(rel)
            head = path.read_bytes()[:24]
            if head[:8] == pi.PNG_MAGIC:
                self._sizes[key] = (int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big"))
            else:
                p = self.picture(rel)
                self._sizes[key] = (p.width, p.height)
        return self._sizes[key]


def entry_cells(folder: Folder, entry: Entry) -> list[tuple[str, tuple]]:
    """Every cell of an entry in the game's order (cell i is column i % columns, row i // columns): its file and
    rectangle (left, top, right, bottom), as ldwImageGrid's constructors and GetCellRect make them."""
    if entry.kind == "image":
        w, h = folder.size(entry.file)
        return [(entry.file, (0, 0, w, h))]
    cols, rows = entry.cols, max(1, entry.rows)
    if entry.kind == "grid" and entry.across * entry.down > 1:
        files = entry.files
        total_w = total_h = 0
        for y in range(entry.down):
            row_w, last_h = 0, 0
            for x in range(entry.across):
                w, h = folder.size(files[y * entry.across + x])
                row_w += w
                last_h = h
            total_w = row_w                                  # the constructor keeps the last row's width
            total_h += last_h                                # and adds each row's last file's height
        first_w, first_h = folder.size(files[0])
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
            out.append((files[index], (c * cw, r * ch, c * cw + cw, r * ch + ch)))
        return out
    w, h = folder.size(entry.file)
    cw, ch = w // cols, h // rows
    return [(entry.file, ((i % cols) * cw, (i // cols) * ch, (i % cols) * cw + cw, (i // cols) * ch + ch))
            for i in range(cols * rows)]


def cut(folder: Folder, rel: str, rect: tuple) -> pi.Image:
    left, top, right, bottom = rect
    return folder.picture(rel).sub(left, top, right - left, bottom - top)


# ------------------------------------------------------------------ the meters, assembled


@dataclass(frozen=True)
class Draw:
    """One call a meter makes: the whole picture `image` (a table id) at (x, y), a clipping rectangle, or a
    filled rectangle in a colour (r, g, b, a: 0-1)."""
    kind: str                       # "draw", "clip", "unclip", "fill"
    image: int = 0
    x: int = 0
    y: int = 0
    rect: tuple = ()
    colour: tuple = ()


# theContinuousVariableMeter::DrawPercentMeter(colour, level): the bars the game uses.
CONTINUOUS = {8: (617, 323), 9: (617, 188), 10: (617, 272), 11: (617, 374), 12: (617, 427), 13: (375, 500)}
CONTINUOUS_USE = {8: "Details screen bar 1", 9: "Details screen bar 2 (red; its level counts to 3,000)",
                  10: "Details screen bar 3", 11: "Details screen bar 4", 12: "Details screen bar 5",
                  13: "the loading screen's bar"}
SLICED_Y = {3: 223, 4: 265, 5: 308, 6: 351, 7: 392, 8: 272, 9: 165, 10: 232, 11: 312, 12: 351}
VARIABLE_FILL = {0: (0.9, 0.5, 0.5, 0.9), 1: (0.5, 0.9, 0.5, 0.9), 2: (0.5, 0.5, 0.9, 0.9)}


def _f32(v: float) -> float:
    return pi.f32(v)


def continuous_meter(colour: int, level: int, offset: int = 0) -> list[Draw]:
    """theContinuousVariableMeter::DrawPercentMeter: colour 9 counts to 3,000 (level * 30 / 900, as the game's
    division), the others to 100; the bar (VD_progressbar, red for colour 9) clipped to level * 290 / 100 pixels,
    its end line (VD_line) 3 pixels before the clip's edge, the fade at the far end, then the clipping reset."""
    if colour not in CONTINUOUS:
        return []
    if colour == 9:
        level = min(level, 3000) // 30
    else:
        level = min(level, 100)
    level = max(0, level)
    width = level * 0x122 // 100
    x, y = CONTINUOUS[colour]
    x += offset
    bar, line = (269, 273) if colour == 9 else (268, 272)
    return [Draw("clip", rect=(x, y, x + width, y + 33)), Draw("draw", bar, x, y),
            Draw("draw", line, x + width - 3, y), Draw("draw", 271, x + 271, y), Draw("unclip")]


def sliced_meter(colour: int, level: int) -> list[Draw]:
    """theSlicedVariableMeter::DrawPercentMeter (never called by the game): colour 9 counts to 1,000, the others
    to 100; StatusBarSliceB every 2 pixels from x 473, level * 290 / 200 of them."""
    level = min(level, 1000) // 10 if colour == 9 else min(level, 100)
    level = max(0, level)
    if colour not in SLICED_Y:
        return []
    return [Draw("draw", 361, 0x1D9 + 2 * k, SLICED_Y[colour]) for k in range(level * 0x122 // 200)]


def variable_meter(colour: int, x: int, y: int, level: int) -> list[Draw]:
    """theVariableMeter::DrawPercentMeter (never called by the game): level 1-100; colours 0-2 a filled rectangle
    (x + 7, y + 5) to (x + 7 + level * 151 / 100, y + 28); colour 3 LoadColor every 8 pixels, level * 2 / 5 of
    them."""
    level = max(1, min(level, 100))
    if colour in VARIABLE_FILL:
        return [Draw("fill", rect=(x + 7, y + 5, x + 7 + level * 151 // 100, y + 28), colour=VARIABLE_FILL[colour])]
    if colour == 3:
        return [Draw("draw", 363, x + 8 * k, y) for k in range(level * 320 // 800)]
    return []


def clip_draw(x: int, y: int, w: int, h: int, clip: tuple | None):
    """ldwGameWindowImpl::ClipRect: (None when nothing is drawn) the part of a w x h picture at (x, y) inside the
    clipping rectangle [left, right) x [top, bottom), as (source left, source top, x, y, width, height)."""
    if clip is None:
        return 0, 0, x, y, w, h
    left, top, right, bottom = clip
    if x >= right or y >= bottom or x + w < left or y + h < top:
        return None
    sx = sy = 0
    if x < left:
        sx, w, x = left - x, w - (left - x), left
    if x + w > right:
        w = right - x
    if y < top:
        sy, h, y = top - y, h - (top - y), top
    if y + h > bottom:
        h = bottom - y
    return sx, sy, x, y, w, h


def render_draws(folder: Folder, draws: list[Draw]) -> pi.Image:
    """The meter's calls drawn in order on a clear canvas just big enough (the screen around it left out)."""
    by_id = {e.id: e for e in table()}
    pieces, clip = [], None
    for d in draws:
        if d.kind == "clip":
            clip = d.rect
        elif d.kind == "unclip":
            clip = None
        elif d.kind == "draw":
            picture = folder.picture(by_id[d.image].file)
            part = clip_draw(d.x, d.y, picture.width, picture.height, clip)
            if part is not None and part[4] > 0 and part[5] > 0:
                sx, sy, x, y, w, h = part
                pieces.append((picture.sub(sx, sy, w, h), x, y))
        elif d.kind == "fill":
            left, top, right, bottom = d.rect
            if clip is not None:
                left, top = max(left, clip[0]), max(top, clip[1])
                right, bottom = min(right, clip[2]), min(bottom, clip[3])
            if right > left and bottom > top:
                r, g, b = (int(_f32(c * 255.0)) for c in d.colour[:3])
                alpha = int(_f32(_f32(d.colour[3] * 255.0) + 0.5))
                block = pi.Image(right - left, bottom - top)
                block.data[:] = bytes((r, g, b, alpha)) * ((right - left) * (bottom - top))
                pieces.append((block, left, top))
    if not pieces:
        return pi.Image(1, 1)
    left = min(x for _p, x, _y in pieces)
    top = min(y for _p, _x, y in pieces)
    right = max(x + p.width for p, x, _y in pieces)
    bottom = max(y + p.height for p, _x, y in pieces)
    canvas = pi.Image(right - left, bottom - top)
    for piece, x, y in pieces:
        canvas.draw(piece, x - left, y - top)
    return canvas


# ------------------------------------------------------------------ the catalogue


@dataclass
class Picture:
    """One thing the player can pick: a table entry, a file, or an assembled meter. `frames` names each cell or
    level; `status` is "" (the game's, in use), UNUSED, PATCHER or MISSING; `notes` say what is not checked."""
    key: str
    name: str
    category: str
    kind: str
    frames: list = field(default_factory=list)
    entry: Entry | None = None
    file: str | None = None
    meter: tuple | None = None                  # ("continuous" | "sliced" | "variable", colour)
    status: str = ""
    reason: str = ""
    notes: list = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.name + (f" ({self.status})" if self.status else "")


def _is_picture(rel: str) -> bool:
    return not rel.lower().endswith(NOT_PICTURES)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def patcher_files(folder: Folder) -> dict:
    """Images files that are not the clean game's: new ones and changed ones (relative path -> "new"/"changed").
    A file the clean game has with the same size is hashed; a different size is a change."""
    stock = {k.lower(): v for k, v in data()["stock"].items()}
    out = {}
    for low, rel in folder.index().items():
        if not _is_picture(rel):
            continue
        known = stock.get(low)
        if known is None:
            out[rel] = "new"
            continue
        path = folder.images / rel
        if path.stat().st_size != known[0] or _sha256(path) != known[1]:
            out[rel] = "changed"
    return out


def _frame_names(entry: Entry) -> list[str]:
    if entry.kind == "image":
        return ["The whole picture"]
    if entry.kind == "strip":
        return [f"Cell {k + 1} of {entry.cols}" for k in range(entry.cols)]
    return [f"Cell {k + 1}: column {k % entry.cols + 1}, row {k // entry.cols + 1}" for k in range(entry.cells)]


def _jpeg_note(files) -> list[str]:
    if any(not f.lower().endswith(".png") for f in files):
        return [f"A JPEG or GIF is decoded by Windows, not the game's own decoder: its pixels are {NOT_CHECKED}."]
    return []


METER_LEVELS = list(range(0, 101, 5))


def catalogue(game_folder) -> list[Picture]:
    """Everything the game folder's Images has and the game draws, in category order (name order within)."""
    folder = game_folder if isinstance(game_folder, Folder) else Folder(game_folder)
    changed = patcher_files(folder) if folder.images is not None and folder.images.is_dir() else {}
    out: list[Picture] = []
    seen_files: set = set()
    seen_keys: set = set()
    for entry in table():
        files = entry.files
        key = f"image:{entry.id}:{entry.file}"
        twice = key in seen_keys
        seen_keys.add(key)
        seen_files |= {f.lower() for f in files}
        missing = [f for f in files if not folder.has(f)]
        kind = {"grid": f"grid of {entry.cols} x {entry.rows}", "strip": f"strip of {entry.cols}",
                "image": "whole picture"}[entry.kind]
        name = f"{entry.file}{entry.file2 or ''} (image {entry.id}, {kind})"
        if twice:
            key, name = key + ":again", name + ", listed again in the table"
        pic = Picture(key, name, category_of(entry.file), "table", _frame_names(entry), entry=entry,
                      notes=_jpeg_note(files))
        if missing:
            pic.status, pic.reason = MISSING, (f"The game's image table names {', '.join(missing)}, which this game "
                                               "folder does not have: the game cannot draw it.")
            pic.frames = []
        elif any(f in changed for f in (folder.index().get(x.lower(), x) for x in files)):
            pic.status = PATCHER
            pic.reason = "The patcher's picture: this game folder's file is not the original game's."
        out.append(pic)
    in_code, unused = data()["named_in_code"], {u.lower() for u in data()["unused"]}
    for low, rel in sorted(folder.index().items()):
        if low in seen_files or not _is_picture(rel):
            continue
        pic = Picture(f"file:{rel}", rel, category_of(rel), "file", ["The whole picture"], file=rel,
                      notes=_jpeg_note([rel]))
        known = next((v for k, v in in_code.items() if k.lower() == low), None)
        if rel in changed:
            pic.status = PATCHER
            pic.reason = ("The patcher's picture: not in the original game." if changed[rel] == "new" else
                          "The patcher's picture: this game folder's file is not the original game's.")
            if changed[rel] == "new":
                pic.category = "The patcher's pictures"
        elif known is not None:
            pic.reason = f"Loaded by the game's code by name ({', '.join(known)}), not through the image table."
            pic.notes.append(f"Drawn as the whole file: how its code draws it is {NOT_CHECKED}.")
        elif low in unused:
            pic.status = UNUSED
            pic.reason = ("Unused: nothing in the game's code names this file (not in the image table, not in any "
                          "string of the code).")
        else:
            pic.notes.append(f"Not in the original game's file list: {NOT_CHECKED}.")
        out.append(pic)
    for colour in sorted(CONTINUOUS):
        frames = [f"Level {v}" for v in (range(0, 3001, 150) if colour == 9 else METER_LEVELS)]
        out.append(Picture(f"meter:continuous:{colour}", f"Bar: {CONTINUOUS_USE[colour]}", "Meters assembled",
                           "meter", frames, meter=("continuous", colour),
                           reason="theContinuousVariableMeter, as the game draws it."))
    for colour in sorted(SLICED_Y):
        frames = [f"Level {v}" for v in (range(0, 1001, 50) if colour == 9 else METER_LEVELS)]
        out.append(Picture(f"meter:sliced:{colour}", f"Sliced meter, colour {colour}", "Meters assembled", "meter",
                           frames, meter=("sliced", colour), status=UNUSED,
                           reason="Unused: theSlicedVariableMeter is never called by the game; drawn by its own "
                                  "code all the same."))
    for colour in (0, 1, 2, 3):
        pic = Picture(f"meter:variable:{colour}", f"Percent meter, colour {colour}", "Meters assembled", "meter",
                      [f"Level {v}" for v in range(5, 101, 5)], meter=("variable", colour), status=UNUSED,
                      reason="Unused: theVariableMeter is never called by the game; drawn by its own code all the "
                             "same.")
        if colour in VARIABLE_FILL:
            pic.notes.append("Its colour is drawn at 90% over a clear background; the game blends it over the "
                             f"screen ({NOT_CHECKED}).")
        out.append(pic)
    order = {c: n for n, c in enumerate(CATEGORIES)}
    out.sort(key=lambda p: (order.get(p.category, len(order)), p.kind == "meter", p.name.lower()))
    return out


def frame_level(picture: Picture, frame: int) -> int:
    return int(picture.frames[frame].split()[-1].replace(",", ""))


def render(folder: Folder, picture: Picture, frame: int = 0) -> pi.Image:
    """One frame of a picture, as the game draws it."""
    if picture.status == MISSING:
        raise pi.PictureError(picture.reason)
    if picture.kind == "table":
        rel, rect = entry_cells(folder, picture.entry)[frame]
        return cut(folder, rel, rect)
    if picture.kind == "file":
        return folder.picture(picture.file).copy()
    which, colour = picture.meter
    level = frame_level(picture, frame)
    if which == "continuous":
        draws = continuous_meter(colour, level)
    elif which == "sliced":
        draws = sliced_meter(colour, level)
    else:
        draws = variable_meter(colour, 100, 200, level)
    return render_draws(folder, draws)


def search(pictures: list[Picture], text: str) -> list[Picture]:
    """The pictures whose name, category, status or reason has every word of `text` (any case)."""
    words = text.lower().split()
    if not words:
        return list(pictures)
    return [p for p in pictures
            if all(w in f"{p.label} {p.category} {p.reason} {p.key}".lower() for w in words)]


def safe(text: str) -> str:
    return pi.safe_file_name(text.replace("/", " - "))


def save_all(folder: Folder, pictures: list[Picture], target: Path, options: dict) -> tuple[int, list]:
    """Every frame of every picture as a PNG, in a folder per category (and one per picture with several
    frames). Returns (saved, failed)."""
    target = Path(target)
    saved, failed = 0, []
    for picture in pictures:
        if picture.status == MISSING:
            continue
        where = target / safe(picture.category)
        many = len(picture.frames) > 1
        if many:
            where = where / safe(picture.label)
        where.mkdir(parents=True, exist_ok=True)
        for frame, frame_name in enumerate(picture.frames):
            stem = safe(frame_name if many else picture.label)
            try:
                image = render(folder, picture, frame)
                pi.save_png(image, pi.unique_path(where, stem), **options)
                saved += 1
            except (OSError, pi.PictureError, ValueError) as exc:
                failed.append(f"{picture.label}, {frame_name}: {exc}")
    return saved, failed
