"""The Picture Maker's "Every picture" tab (src/vf2_game_pictures.py, vf2_art_sheets.py, the tab in
src/vf2_picture_maker.py): the same tab as the Virtual Families 1 patcher's.

Always run: the image table's shape, the 16 categories (VF1's, in its order), the file-name rules, the labels
("(unused)", "(patcher)"), Find and Show, cutting PNGs whole or to the drawn pixels.

With the original game (work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR): every picture file is listed whole and
every cell of every table picture is listed once, with the game's cutting; the files no code names are unused; a
sample of every group draws; the patcher's pictures are marked; Save all puts each picture in its category's folder;
the window's Find, Show, preview, Save PNG and Save all work.

With the B200 desktop objects too (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR): src/vf2_game_pictures.json is
what scripts/build_vf2_image_table.py reads from the objects, and theGraphicsManagerImpl::GetImage and
ldwImageGrid::GetCellRect, run in Unicorn (tests/vf2_pictures_emu.py) for every table entry the game folder has,
cut every cell exactly where the catalogue cuts it.

The assembled pictures are checked by tests/test_art_*.py, the JPEG decoder by tests/test_jpeg_decoder.py and which
pictures the game uses by tests/test_picture_usage.py.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("UC_IGNORE_REG_BREAK", "1")

import vf2_art_sheets as sheets  # noqa: E402
import vf2_game_pictures as gp  # noqa: E402
import vf2_picture_image as pi  # noqa: E402
import vf2_picture_maker as pm  # noqa: E402

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE_GAME = (GAME_DIR / "Images" / "carrying.png").is_file()
HAVE_OBJECTS = (OBJ_DIR / "theGraphicsManager.obj").is_file() and (OBJ_DIR / "ldwImage.obj").is_file()
needs_game = pytest.mark.skipif(not HAVE_GAME, reason="no original game folder (work/vanilla_runtime_payload)")
needs_code = pytest.mark.skipif(not (HAVE_GAME and HAVE_OBJECTS),
                                reason="no B200 desktop object files or no original game folder")

VF1_CATEGORIES = ("Meters and bars", "Buttons and controls", "Dialogs and panels", "Icons and cursors", "Fonts",
                  "House and yard", "Furniture and objects", "Food and cooking", "Weather, day and night",
                  "Effects and animations", "Animals and insects", "People", "Store",
                  "Collectibles and collections", "Screens and backgrounds", "Patcher's own pictures")


# ====================================================================== always
def test_the_image_table():
    table = gp.table()
    assert len(table) == 632                                   # 633 entries less "No Graphic"
    by_id: dict = {}
    for e in table:
        by_id.setdefault(e.id, []).append(e)
    assert [e.file for e in by_id[85]] == ["Furniture/PirateShipStd.png"] * 2      # the table lists it twice
    heads = by_id[576][0]
    assert (heads.kind, heads.cells, heads.files) == ("grid", 1200, ["female_heads00.png", "female_heads10.png"])
    assert by_id[478][0].kind == "grid" and by_id[478][0].cells == 91
    assert by_id[293][0].kind == "strip" and by_id[293][0].cells == 3
    assert by_id[636][0].kind == "image" and by_id[636][0].cells == 1
    assert sum(1 for e in table if e.file.startswith("Furniture/")) == 240
    assert gp.entry_by_id(85) == by_id[85][0]                   # GetImageEntry finds the first


def test_the_categories_are_vf1s():
    assert gp.CATEGORY_ORDER == VF1_CATEGORIES
    assert pm.SHOW_CHOICES == ("Every picture", "Only pictures the game shows", "Only unused pictures",
                               "Only pictures not checked against the game", "Only the patcher's own pictures")
    rules = {
        "Furniture/HammockStd.png": "Furniture and objects", "female_heads00.png": "People",
        "pet_grid.png": "Animals and insects", "btn_blue.png": "Buttons and controls",
        "VD_progressbar-blue.jpg": "Meters and bars", "collection-insects_fly2.png": "Collectibles and collections",
        "Segoe24Bold.png": "Fonts", "MapX2Y3.jpg": "House and yard", "hand_open.png": "Icons and cursors",
        "snowflake.png": "Weather, day and night", "OrangeDlgTileGrid.png": "Dialogs and panels",
        "chopGreens1.png": "Food and cooking", "sparklestrip.png": "Effects and animations",
        "InventoryItems.png": "Store", "SPLASH_BG.jpg": "Screens and backgrounds",
        "LightSourceMask250.png": "Weather, day and night", "Upgrades/fan.png": "Furniture and objects",
    }
    for name, category in rules.items():
        assert sheets.category_of(name) == category, name
    assert all(c in gp.CATEGORY_ORDER for c, _rx in sheets._RULES)


def test_labels_find_and_show():
    used = gp.Art("a", "Buttons and controls/Picture files", "btn_blue.png", (gp.whole("btn_blue.png"),), True,
                  "Drawn by ldwButton::Draw.", "Checked.")
    unused = gp.Art("b", "Screens and backgrounds/Picture files", "main_BG.png", (gp.whole("main_BG.png"),), False,
                    "Unused: nothing names it.")
    mine = gp.Art("c", "Patcher's own pictures/Family tree backgrounds", "green-tree.png", (), True, "Ours.", "",
                  True)
    assert unused.title == "main_BG.png (unused)" and mine.title == "green-tree.png (patcher)"
    assert used.note() == "Drawn by ldwButton::Draw. Checked."
    assert unused.note().endswith(gp.CHECK + ".")
    cat = gp.Catalogue([used, unused, mine])
    assert [a.key for a in cat.find("BUTTONS blue")] == ["a"]
    assert [a.key for a in cat.find("unused")] == ["b"]
    assert cat.find("  ") == [used, unused, mine]
    arts = cat.arts
    assert pm.shown(arts, pm.SHOW_CHOICES[0]) == arts
    assert pm.shown(arts, pm.SHOW_CHOICES[1]) == [used]
    assert pm.shown(arts, pm.SHOW_CHOICES[2]) == [unused]
    assert pm.shown(arts, pm.SHOW_CHOICES[3]) == [unused, mine]
    assert pm.shown(arts, pm.SHOW_CHOICES[4]) == [mine]


def test_whole_size_or_cut_to_the_drawn_pixels():
    image = pi.Image(10, 8)
    image.data[(3 * 10 + 4) * 4:(3 * 10 + 4) * 4 + 4] = bytes((1, 2, 3, 255))
    cut = pi.export(image, margin=0)
    kept = pi.export(image, margin=0, crop=False)
    assert (cut.width, cut.height) == (1, 1) and (kept.width, kept.height) == (10, 8)
    assert kept == image


def test_quick_shrink_keeps_every_kth_pixel():
    image = pi.Image(9, 4)
    for i in range(36):
        image.data[i * 4:i * 4 + 4] = bytes((i, 0, 0, 255))
    small = pm.quick_shrink(image, 3)
    assert (small.width, small.height) == (3, 2)
    assert [small.pixel(x, y)[0] for y in range(2) for x in range(3)] == [0, 3, 6, 27, 30, 33]


# ====================================================================== with the game
@pytest.fixture(scope="module")
def files():
    if not HAVE_GAME:
        pytest.skip("no original game folder")
    return gp.GameFiles(GAME_DIR)


@pytest.fixture(scope="module")
def catalogue(files):
    return gp.catalogue(files)


@needs_game
def test_the_catalogue(files, catalogue):
    arts = catalogue.arts
    assert catalogue.problems == []
    assert len({a.key for a in arts}) == len(arts)
    tops = []
    for a in arts:
        top = a.category.split("/")[0]
        if top not in tops:
            tops.append(top)
    assert tops == [c for c in gp.CATEGORY_ORDER if c in tops] and len(tops) >= 15
    assert all(a.why for a in arts)
    assert not any(a.patcher for a in arts if not a.category.startswith(gp.PATCHER_CATEGORY))
    # every file of the Images folder is listed whole
    whole = {layer.file.lower() for a in arts if len(a.layers) == 1 for layer in a.layers
             if isinstance(layer, gp.Draw) and layer.make is None and tuple(layer.rect) == (0, 0, -1, -1)}
    import vf2_art_fonts
    whole |= {n.lower() for n in vf2_art_fonts.font_files()}       # listed whole by the fonts module
    pictures = {n for n in files.names() if n.endswith((".png", ".jpg", ".gif", ".bmp"))}
    assert pictures - whole == set()
    # every cell of every table picture the folder has, once, cut as entry_cells cuts it
    cells = {a.key: a for a in arts
             if a.key.startswith("sheets/") and a.key.count("/") == 2 and a.key.rsplit("/", 1)[-1].isdigit()}
    expected = 0
    for entry, _ids in sheets.groups():
        if not all(files.has(n) for n in entry.files) or entry.kind == "image" or entry.cells == 1:
            continue
        for index, (name, rect) in enumerate(gp.entry_cells(files, entry)):
            art = cells[f"sheets/{entry.id}/{index}"]
            assert art.layers[0].file.lower() == name.lower() and art.layers[0].rect == rect
            expected += 1
    assert expected == len(cells) > 11000
    # missing table files are listed, with nothing to draw
    missing = sorted(a.label.split(" ")[0] for a in arts if a.key.startswith("sheets/") and not a.layers)
    assert missing == ["LightSourceMask180x8.png", "LightSourceMask200x10.png", "LightSourceMask300x10.png",
                       "small_logo.png"]
    # the files no code names
    unused_files = {a.key for a in arts if a.key.startswith("sheets/file/") and not a.used}
    assert unused_files == {f"sheets/file/{n.lower()}" for n in gp.data()["unused"]}


@needs_game
def test_unused_pictures_say_why(catalogue):
    unused = [a for a in catalogue.arts if not a.used]
    assert len(unused) > 300
    for art in unused:
        assert art.title.endswith("(unused)") and len(art.why) > 30, art.key
    by_key = {a.key: a for a in catalogue.arts}
    assert not by_key["sheets/363"].used                       # LoadColor: only theVariableMeter asks for it
    assert not by_key["sheets/597/file0"].used                 # the hummingbird
    assert not by_key["sheets/file/main_bg.png"].used
    assert by_key["sheets/295/0"].used                         # btn_blue


@needs_game
def test_a_picture_of_every_group_draws(files, catalogue):
    seen: dict = {}
    for art in catalogue.arts:
        if art.layers and art.category not in seen:
            seen[art.category] = art
    assert len(seen) > 80
    for category, art in seen.items():
        image = gp.draw(files, art)
        assert image.width > 0 and image.height > 0, category
    heads = catalogue.by_key("sheets/576/30")                  # column 7, row 2 of the two-file heads
    name, rect = gp.entry_cells(files, gp.entry_by_id(576))[30]
    assert name == "female_heads00.png"
    assert gp.draw(files, heads) == files.image(name).sub(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])


@needs_game
def test_the_patchers_pictures_are_marked(tmp_path):
    images = tmp_path / "Images"
    (images / "Furniture").mkdir(parents=True)
    source = GAME_DIR / "Images"
    for name in ("carrying.png", "hand.png", "Furniture/HammockStd.png"):
        (images / name).write_bytes((source / name).read_bytes())
    (images / "hand_open.png").write_bytes((source / "hand_open.png").read_bytes() + b"\0")    # other bytes
    (images / "MyMod").mkdir()
    (images / "MyMod" / "new.png").write_bytes((source / "hand.png").read_bytes())
    files = gp.GameFiles(tmp_path)
    assert gp.patcher_files(files) == {"hand_open.png": "changed", "MyMod/new.png": "new"}
    arts = {a.key: a for a in gp.catalogue(files).arts}
    new = arts["patcher/file/mymod/new.png"]
    assert new.patcher and new.category == "Patcher's own pictures/New pictures in the game folder/MyMod"
    changed = arts["patcher/1/1"]
    assert changed.patcher and changed.title.endswith("(patcher)")
    assert not arts["sheets/2"].patcher and arts["sheets/2"].layers
    assert arts["sheets/3"].layers == ()                       # a file this folder does not have


@needs_game
def test_save_all_by_category(files, catalogue, tmp_path):
    arts = [a for a in catalogue.arts if a.key in ("sheets/1", "sheets/2")]
    arts += [a for a in catalogue.arts if a.category == "Meters and bars/Loading bar"][:3]
    assert len(arts) == 5
    saved, failed, blank = pm.save_arts(files, arts, tmp_path, {"margin": 0, "scale": 1, "crop": True})
    assert (saved, failed) == (5, [])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Icons and cursors", "Meters and bars"]
    assert len(list((tmp_path / "Meters and bars" / "Loading bar").glob("*.png"))) == 3
    saved, _failed, _blank = pm.save_arts(files, arts, tmp_path / "again", {"margin": 0, "scale": 1},
                                          lambda done, total: done < 2)
    assert saved == 2                                          # Stop saving


# ====================================================================== against the game's code
@needs_code
def test_the_data_file_is_the_games():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_vf2_image_table as builder
    text = builder.render(builder.build(OBJ_DIR))
    assert text == gp.DATA_FILE.read_text(encoding="utf-8")
    assert text == (ROOT / "work" / "vf2_game_pictures.json").read_text(encoding="utf-8")


@needs_code
def test_every_cell_is_cut_as_the_game_cuts_it(files):
    pytest.importorskip("unicorn")
    import vf2_pictures_emu as pe
    rig = pe.ImageRig(OBJ_DIR, GAME_DIR / "Images")
    checked = cells = 0
    for entry in gp.table():
        if not all(files.has(f) for f in entry.files):
            continue
        game = [(f.replace("\\", "/").lower(), r) for f, r in rig.cells(entry.id, entry.kind, entry.cells)]
        mine = [(f.lower(), r) for f, r in gp.entry_cells(files, entry)]
        assert mine == game, entry
        checked += 1
        cells += len(mine)
    assert checked == 628 and cells == 11922


# ====================================================================== the window
@pytest.fixture(scope="module")
def tk_root():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except Exception:
        pytest.skip("no display available for Tk")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@needs_game
def test_the_every_picture_tab(tk_root, tmp_path):
    maker = pm.PictureMaker(tk_root, [], str(GAME_DIR))
    maker.quiet = True
    try:
        assert [maker.notebook.tab(t, "text") for t in maker.notebook.tabs()] == [
            "From my save", "Make your own", "Every picture"]
        cat = maker.ensure_catalogue()
        assert maker.all_count_var.get() == f"{len(cat.arts)} of {len(cat.arts)} pictures"
        tops = [maker.all_tree.item(n, "text") for n in maker.all_tree.get_children()]
        assert tops == [c for c in gp.CATEGORY_ORDER if c in tops] and len(tops) >= 15
        maker.search_var.set("loading bar")
        maker._fill_all()
        maker.open_all_groups()
        art = next(a for a in maker.all_nodes.values() if a.category == "Meters and bars/Loading bar")
        maker.select_art(art.key)
        assert maker.shown["all"] == gp.draw(maker.catalogue_files, art)
        assert maker.picture_name("all") == pi.safe_file_name(art.title)
        cut = maker.save_png("all", str(tmp_path / "cut.png"))
        maker.whole_var.set(True)
        whole = maker.save_png("all", str(tmp_path / "whole.png"))
        assert cut.is_file() and whole.is_file() and whole.stat().st_size != cut.stat().st_size
        target = maker.save_every(group=False, folder=str(tmp_path / "all"))
        assert len(list(target.rglob("*.png"))) == len(maker.shown_arts()) > 0
        assert f"{len(maker.shown_arts())} picture(s) saved" in maker.last_message
        maker.search_var.set("leaf")
        maker.show_var.set(pm.SHOW_CHOICES[2])
        maker._fill_all()
        maker.open_all_groups()
        assert maker.all_nodes and all(not a.used for a in maker.all_nodes.values())
        node = next(iter(maker.all_groups))
        maker.all_tree.selection_set(node)
        path = maker.all_groups[node]
        group = maker.save_every(group=True, folder=str(tmp_path / "group"))
        expected = [a for a in maker.shown_arts() if a.category == path or a.category.startswith(path + "/")]
        assert len(list(group.rglob("*.png"))) == len([a for a in expected if a.layers]) > 0
        maker.search_var.set("")
        maker.show_var.set(pm.SHOW_CHOICES[4])
        maker._fill_all()
        assert maker.all_count_var.get().startswith(f"{sum(1 for a in cat.arts if a.patcher)} of")
    finally:
        maker.close()
