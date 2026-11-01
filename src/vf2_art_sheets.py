"""Every picture file of the game folder, whole and cut into every cell the game cuts it into (the image table and
ldwImageGrid::GetCellRect, vf2_game_pictures), the files the code loads by name, the files nothing loads, and the
patcher's own pictures.

Whether the game ever shows a picture comes from the image table's usage (src/vf2_game_pictures.json "usage",
made by scripts/build_vf2_image_table.py from the code of the B200 desktop objects: which code reached from
WinMain asks theGraphicsManager for each image), refined per cell by the area modules' CELL_LABELS / CELL_UNUSED
(vf2_art_meters, vf2_art_ui, vf2_art_house, vf2_art_misc) and the data file's "cell_unused" / "cell_labels".
"""
from __future__ import annotations

import re
from pathlib import Path

import vf2_game_pictures as gp

TITLE = "Picture files"
SUB = "Picture files"                # the sub-category every file goes in, beside the area's assembled pictures
AREA_MODULES = ("vf2_art_meters", "vf2_art_ui", "vf2_art_house", "vf2_art_misc", "vf2_art_screens", "vf2_art_fonts")

# File name (lower case, the Images-relative path) -> the catalogue's top-level category; the first rule that
# matches wins.
_RULES = (
    ("Fonts", r"^segoe"),
    ("Meters and bars", r"^(vd_progressbar|vd_line|vd_fade|loadscenebarbg|loadcolor|statusbarslice|"
                        r"achievement_progress_box)"),
    ("Collectibles and collections", r"^(collection|fossil|pterodactyl|collectables_small)"),
    ("People", r"^(female_|male_|bigheads|highrez_bodies|peep_shadow|carrying\.png)"),
    ("Animals and insects", r"^(pet_grid|bird|dragonflies|butterfly|hummingbird|reeffish|beestrip|roachstrip|"
                            r"malfunctionants|ball_shadow)"),
    ("Food and cooking", r"^(foodwork|workwork|workdocs|chopgreens|breads|cans\.|meal\.|bbqmeat|antpuzzle|"
                         r"cinnamonbowl|salad_anim|boiling_water_anim)"),
    ("Weather, day and night", r"^(raindrops|rainbow|sunbeam|map_fog|snowflake|hailstone|leaf\d|lightsourcemask|"
                               r"puddles)"),
    ("House and yard", r"^(mapx|house\.jpg|hill\.jpg|damage_|foundation_|bathroom2foundation|closed_door|"
                       r"closes_door|curtain|holesm|holelg|gopherinhole|sockpile|kitchengarbage)"),
    ("Furniture and objects", r"^(furniture/|upgrades/|old_computer|tvanim|eastcpuanim|westcpuanim|fishtank|"
                              r"fireplace|pinball|pachinko|slotmachine|washeranim|airpurifier|fridgestates|"
                              r"greenlight|redlight|rosepetals|petbowls)"),
    ("Store", r"(_icon\.png$|^inventoryitems|^home_grid|^menustore|^meunstore|^coins_level|^onsale|"
              r"^scrollingstoreitembox|^getmorecoins|^storagecube)"),
    ("Icons and cursors", r"^(hand|coins\.png|dollar|locked|checkmark_red|ldwlogo|logo1|small_logo|email_anim|"
                          r"email_big_anim|focus_circle|drm/logo1)"),
    ("Dialogs and panels", r"(dlgtilegrid|^dlgemailgrid|^maintooltray|^main_no-comm|^money_console|"
                           r"^familytree_(parent|child)frame|^achievement_box|^achievement_complete_box|"
                           r"^menubtnbackground)"),
    ("Buttons and controls", r"(^btn_|button|^menubtn|^fbtn_|^vd_btn|^radio|^checkbox|^checkmark|^arrow|^empty1|"
                             r"^touchtoselect|^inisible|^invisible|slider|^familytree_scrollknob|"
                             r"^upgrademebutton|^decormodetab|^collection-all_)"),
    ("Effects and animations", r"(strip|_anim|anim|sparkle|^dust|^bubble|^foam|^spray|^footprints|^smoke|"
                               r"^candle|^petal|^waves|^algae|^ripple|^dripping)"),
)


def category_of(name: str) -> str:
    low = name.replace("\\", "/").lower()
    for category, rule in _RULES:
        if re.search(rule, low):
            return category
    return "Screens and backgrounds"


WHOLE_CHECKED = "The file's own pixels, as the game's picture loader reads them."
JPEG_CHECKED = ("The file's own pixels, decoded byte for byte as the game's own libjpeg-9.dll decodes them "
                "(tests/test_jpeg_decoder.py).")
CELLS_CHECKED = ("Cut where the game's own GetCellRect, run in Unicorn, cuts it; the cell's own pixels, as the game's "
                 "blit draws them at full size.")
NOT_TRACED = ("In the game's image table; which code draws it was not traced, so whether the game shows it is "
              f"{gp.CHECK.lower()}.")
NOT_NAMED = ("Unused: no code of the game names this file. It is not in the image table, and no string in the "
             "game's code names it or builds its name.")
NAMED_WHY = "Loaded by name (not through the image table) by the game's {code} code."
MAP_WHY = "A tile of the yard and the house, loaded by CWorldMap (\"MapX%dY%d.jpg\") and drawn by it."
ICON_WHY = "The game window's icon: the game loads it with SDL_LoadBMP_RW and gives it to SDL_SetWindowIcon."
SPLASH_WHY = "The splash screen theSplashScene shows while the game starts."


def _checked_whole(name: str) -> str:
    return JPEG_CHECKED if name.lower().endswith((".jpg", ".jpeg")) else WHOLE_CHECKED


def _areas() -> list:
    out = []
    for name in AREA_MODULES:
        try:
            out.append(__import__(name))
        except ImportError:
            continue
    return out


def merged() -> tuple[dict, dict, dict]:
    """(USAGE {id: (used, why)}, CELL_LABELS {(id, cell): label}, CELL_UNUSED {(id, cell): why}): the data file's,
    then every area module's on top."""
    d = gp.data()
    usage = {int(k): (bool(v[0]), str(v[1])) for k, v in d.get("usage", {}).items()}
    labels = {tuple(int(p) for p in k.split(":")): v for k, v in d.get("cell_labels", {}).items()}
    unused = {tuple(int(p) for p in k.split(":")): v for k, v in d.get("cell_unused", {}).items()}
    for mod in _areas():
        usage.update(getattr(mod, "USAGE", {}))
        labels.update(getattr(mod, "CELL_LABELS", {}))
        unused.update(getattr(mod, "CELL_UNUSED", {}))
    return usage, labels, unused


def _font_files() -> set[str]:
    try:
        import vf2_art_fonts
        return {name.lower() for name in vf2_art_fonts.font_files()}
    except (ImportError, AttributeError):
        return set()


def groups() -> list[tuple[gp.Entry, list[int]]]:
    """The image table's pictures, one per file and cutting (the first entry, and every id that names it)."""
    out: dict[tuple, tuple[gp.Entry, list[int]]] = {}
    for entry in gp.table():
        key = (entry.name.lower(), entry.cols, entry.rows, entry.across, entry.down)
        if key in out:
            if entry.id not in out[key][1]:
                out[key][1].append(entry.id)
        else:
            out[key] = (entry, [entry.id])
    return list(out.values())


def _shape(entry: gp.Entry) -> str:
    if entry.kind == "image":
        return "drawn whole"
    if entry.kind == "strip":
        return f"a strip of {entry.cols} cells"
    return f"{entry.cols} x {entry.rows} cells"


def _why_for(ids: list[int], usage: dict) -> tuple[bool, str]:
    known = [(i, usage[i]) for i in ids if i in usage]
    if not known:
        return True, NOT_TRACED
    used = any(u[0] for _i, u in known)
    if len(ids) == 1:
        return used, known[0][1][1]
    words = [f"The image table lists this file {len(ids)} times (images {', '.join(map(str, ids))})."]
    words += [f"Image {i}: {u[1]}" for i, u in known]
    return used, " ".join(words)


def _sheet_arts(files: gp.GameFiles, entry: gp.Entry, ids: list[int], category: str, used: bool, why: str,
                labels: dict, unused: dict, key_prefix: str, patcher: bool = False) -> list[gp.Art]:
    arts = []
    sub = f"{category}/{SUB}"
    names = entry.files
    real = [files.relative(n.lower()) if files.has(n) else n for n in names]
    if entry.kind == "image" or entry.cells == 1:
        what = "drawn whole" if entry.kind == "image" else "one cell, the whole picture"
        arts.append(gp.Art(f"{key_prefix}/{entry.id}", sub, f"{real[0]} (image {', '.join(map(str, ids))}, {what})",
                           (gp.whole(real[0]),), used, why, "" if patcher else _checked_whole(real[0]), patcher))
        return arts
    for k, name in enumerate(real):
        arts.append(gp.Art(f"{key_prefix}/{entry.id}/file{k}", sub,
                           f"{name} (image {', '.join(map(str, ids))}, the whole file: the game draws its cells, "
                           f"{_shape(entry)})", (gp.whole(name),), used, why,
                           "" if patcher else _checked_whole(name), patcher))
    group = f"{sub}/{Path(entry.name).stem if len(names) == 1 else entry.name}"
    cells = gp.entry_cells(files, entry)
    for index, (name, rect) in enumerate(cells):
        col, row = index % entry.cols, index // entry.cols
        label = next((labels[(i, index)] for i in ids if (i, index) in labels), None)
        text = (f"Cell {index + 1} (row {row + 1}, column {col + 1})" if entry.rows else f"Cell {index + 1}")
        text += f": {label}" if label else ""
        cell_used, cell_why = used, why
        reason = next((unused[(i, index)] for i in ids if (i, index) in unused), None)
        if used and reason is not None:
            cell_used, cell_why = False, reason
        layer = gp.Draw(files.relative(name.lower()) if files.has(name) else name, rect)
        arts.append(gp.Art(f"{key_prefix}/{entry.id}/{index}", group, text, (layer,), cell_used, cell_why,
                           "" if patcher else CELLS_CHECKED, patcher))
    return arts


def arts(files: gp.GameFiles) -> list[gp.Art]:
    usage, labels, unused = merged()
    fonts = _font_files()
    changed = gp.patcher_files(files)
    changed_low = {k.lower(): v for k, v in changed.items()}
    out: list[gp.Art] = []
    done: set[str] = set()
    for entry, ids in groups():
        category = category_of(entry.file)
        used, why = _why_for(ids, usage)
        for n in entry.files:
            done.add(n.lower())
        missing = [n for n in entry.files if not files.has(n)]
        if missing:
            out.append(gp.Art(f"sheets/{entry.id}", f"{category}/{SUB}",
                              f"{entry.name} (image {', '.join(map(str, ids))}, missing)", (), used,
                              f"The image table names {', '.join(missing)}, which the game folder does not have: the "
                              f"game cannot draw it. {why}"))
            continue
        out += _sheet_arts(files, entry, ids, category, used, why, labels, unused, "sheets")
        if any(n.lower() in changed_low for n in entry.files):
            out += _sheet_arts(files, entry, ids, f"{gp.PATCHER_CATEGORY}/Changed game pictures", True,
                               "The patcher's picture: this game folder's file is not the original game's. " + why,
                               labels, {}, f"patcher/{entry.id}", patcher=True)
    in_code = {k.lower(): v for k, v in gp.data()["named_in_code"].items()}
    stock_unused = {u.lower() for u in gp.data()["unused"]}
    for low, path in sorted(files.names().items()):
        if low in done or low in fonts or not gp._is_picture(low):
            continue
        rel = files.relative(low)
        if changed_low.get(low) == "new":
            folder = rel.rsplit("/", 1)[0] if "/" in rel else "Images"
            out.append(gp.Art(f"patcher/file/{low}", f"{gp.PATCHER_CATEGORY}/New pictures in the game folder/{folder}",
                              rel, (gp.whole(rel),), True,
                              "The patcher's picture: the original game does not have this file.", "", True))
            continue
        if low.startswith("mapx"):
            category, used, why = "House and yard", True, MAP_WHY
        elif low == "splash_bg.jpg":
            category, used, why = "Screens and backgrounds", True, SPLASH_WHY
        elif low in in_code:
            category, used, why = category_of(rel), True, NAMED_WHY.format(code=", ".join(in_code[low]))
        elif low in stock_unused:
            category, used, why = category_of(rel), False, NOT_NAMED
        else:
            category, used, why = category_of(rel), True, f"Not in the original game's file list: {gp.CHECK.lower()}."
        label = f"{rel} (drawn whole)" if used else rel
        out.append(gp.Art(f"sheets/file/{low}", f"{category}/{SUB}", label, (gp.whole(rel),), used, why,
                          _checked_whole(rel)))
        if changed_low.get(low) == "changed":
            out.append(gp.Art(f"patcher/file/{low}", f"{gp.PATCHER_CATEGORY}/Changed game pictures", rel,
                              (gp.whole(rel),), True,
                              "The patcher's picture: this game folder's file is not the original game's.", "", True))
    if files.has("root:icon.bmp"):
        out.append(gp.Art("sheets/icon.bmp", f"Icons and cursors/{SUB}", "icon.bmp (the window's icon)",
                          (gp.whole("root:icon.bmp"),), True, ICON_WHY,
                          "The file's own pixels (a lossless BMP, read as SDL_LoadBMP reads it)."))
    out += tree_arts()
    return out


def tree_arts() -> list[gp.Art]:
    """The patcher's own family tree backgrounds (src/family_tree_backgrounds)."""
    out = []
    folder = gp.TREE_PICTURES
    if not folder.is_dir():
        return out
    for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if path.suffix.lower() not in (".png", ".jpg"):
            continue
        out.append(gp.Art(f"patcher/tree/{path.name.lower()}", f"{gp.PATCHER_CATEGORY}/Family tree backgrounds",
                          path.name, (gp.whole(f"patcher:{path}"),), True,
                          "A background the patcher's Family Tree Maker can draw a tree on (the patcher's own; the "
                          "game never shows it).", "", True))
    return out
