"""The Picture Maker's "All game pictures" (src/vf2_game_pictures.py, the tab in src/vf2_picture_maker.py).

Always run: the image table's shape, the categories, the meters' rules, the search, the clipping rule, the
labels (unused, missing, the patcher's, not checked).

With the B200 desktop objects (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) and the original game
(work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR), else skipped: src/vf2_game_pictures.json must be what
scripts/build_vf2_image_table.py reads from the objects; theGraphicsManagerImpl::GetImage and
ldwImageGrid::GetCellRect run under unicorn (tests/vf2_pictures_emu.py) for every table entry the game folder has,
and every cell's file and rectangle must be the Picture Maker's; the three meters' DrawPercentMeter run for every
colour and many levels and must make the Picture Maker's calls; ldwGameWindowImpl::ClipRect must clip as it does;
every frame of every picture is drawn; a meter's picture is compared with an independent composite (Pillow).
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("UC_IGNORE_REG_BREAK", "1")

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


# ====================================================================== always
def test_the_image_table():
    table = gp.table()
    assert len(table) == 632                                   # 633 entries less "No Graphic"
    by_id = {}
    for e in table:
        by_id.setdefault(e.id, []).append(e)
    assert [e.file for e in by_id[85]] == ["Furniture/PirateShipStd.png"] * 2      # the table lists it twice
    heads = by_id[576][0]
    assert (heads.kind, heads.cells, heads.files) == ("grid", 1200, ["female_heads00.png", "female_heads10.png"])
    assert by_id[478][0].kind == "grid" and by_id[478][0].cells == 91
    assert by_id[293][0].kind == "strip" and by_id[293][0].cells == 3
    assert by_id[636][0].kind == "image" and by_id[636][0].cells == 1
    assert sum(1 for e in table if e.file.startswith("Furniture/")) == 240


def test_categories():
    assert gp.category_of("Furniture/HammockStd.png") == "Furniture"
    assert gp.category_of("female_heads00.png") == "People"
    assert gp.category_of("pet_grid.png") == "Pets"
    assert gp.category_of("btn_blue.png") == "Buttons and controls"
    assert gp.category_of("VD_progressbar-blue.jpg") == "Meters and bars"
    assert gp.category_of("collection-insects_fly2.png") == "Collectibles and collections"
    assert gp.category_of("Segoe24Bold.png") == "Fonts"
    assert gp.category_of("MapX2Y3.jpg") == "Rooms and the house"
    assert gp.category_of("hand_open.png") == "Cursors"
    assert gp.category_of("snowflake.png") == "Weather and nature"
    assert all(category_rule in gp.CATEGORIES for category_rule, _rx in gp._RULES)


def test_the_meters_rules():
    bar = gp.continuous_meter(8, 50)
    assert [(d.kind, d.image, d.x, d.y, d.rect) for d in bar] == [
        ("clip", 0, 0, 0, (617, 323, 762, 356)), ("draw", 268, 617, 323, ()), ("draw", 272, 759, 323, ()),
        ("draw", 271, 888, 323, ()), ("unclip", 0, 0, 0, ())]
    assert gp.continuous_meter(9, 1000)[0].rect == (617, 188, 712, 221)          # colour 9 counts to 3,000
    assert gp.continuous_meter(9, 5000)[0].rect == gp.continuous_meter(9, 3000)[0].rect
    assert gp.continuous_meter(7, 50) == [] and gp.continuous_meter(14, 50) == []
    assert len(gp.sliced_meter(4, 100)) == 145 and len(gp.sliced_meter(9, 1000)) == 145
    assert len(gp.variable_meter(3, 0, 0, 50)) == 20 and gp.variable_meter(0, 100, 200, 0)[0].rect == (107, 205,
                                                                                                         108, 228)


def test_clipping_rule():
    assert gp.clip_draw(10, 10, 20, 20, None) == (0, 0, 10, 10, 20, 20)
    assert gp.clip_draw(10, 10, 20, 20, (15, 0, 25, 100)) == (5, 0, 15, 10, 10, 20)
    assert gp.clip_draw(30, 10, 20, 20, (15, 0, 30, 100)) is None                  # the right edge is outside
    assert gp.clip_draw(-5, 10, 5, 20, (0, 0, 30, 100)) == (5, 0, 0, 10, 0, 20)     # touching: nothing wide


def test_search_and_labels():
    pictures = [gp.Picture("a", "btn_blue.png (image 295, strip of 3)", "Buttons and controls", "table", ["x"]),
                gp.Picture("b", "main_BG.png", "Screens and backgrounds", "file", ["x"], status=gp.UNUSED,
                           reason="Unused: nothing names it.")]
    assert [p.key for p in gp.search(pictures, "BUTTONS blue")] == ["a"]
    assert [p.key for p in gp.search(pictures, "unused")] == ["b"]
    assert gp.search(pictures, "  ") == pictures
    assert pictures[1].label == "main_BG.png (unused)"


def test_what_the_data_file_says_is_unused():
    d = gp.data()
    assert set(d["unused"]) == {"DRM/logo1.gif", "DRM/virtualfamilies_drm.jpg", "MenuBtnCurrency2.png",
                                "VD_BG_2.png", "main_BG.png"}
    assert d["named_in_code"]["MapX0Y0.jpg"] == ["WorldMap"] and "SPLASH_BG.jpg" in d["named_in_code"]
    assert len(d["stock"]) == 655


# ====================================================================== with the game
@pytest.fixture(scope="module")
def folder():
    if not HAVE_GAME:
        pytest.skip("no original game folder")
    return gp.Folder(GAME_DIR)


@pytest.fixture(scope="module")
def pictures(folder):
    return gp.catalogue(folder)


@needs_game
def test_the_catalogue(pictures):
    keys = [p.key for p in pictures]
    assert len(keys) == len(set(keys))
    assert sum(1 for p in pictures if p.kind == "table") == 632
    missing = sorted(p.entry.file for p in pictures if p.status == gp.MISSING)
    assert missing == ["LightSourceMask180x8.png", "LightSourceMask200x10.png", "LightSourceMask300x10.png",
                       "small_logo.png"]
    unused = sorted(p.key for p in pictures if p.status == gp.UNUSED)
    assert "file:main_BG.png" in unused and "meter:sliced:3" in unused and "meter:variable:0" in unused
    assert not any(p.status == gp.PATCHER for p in pictures)                     # the original game
    assert {p.category for p in pictures} <= set(gp.CATEGORIES)
    bars = [p for p in pictures if p.key.startswith("meter:continuous")]
    assert len(bars) == 6 and not any(p.status for p in bars)
    jpeg = next(p for p in pictures if p.key.startswith("image:366:"))
    assert any(gp.NOT_CHECKED in n for n in jpeg.notes)
    order = [gp.CATEGORIES.index(p.category) for p in pictures]
    assert order == sorted(order)


@needs_game
def test_every_frame_is_drawn(folder, pictures):
    drawn = 0
    for picture in pictures:
        for frame in range(len(picture.frames)):
            image = gp.render(folder, picture, frame)
            assert image.width > 0 and image.height > 0
            drawn += 1
    assert drawn > 12000
    heads = next(p for p in pictures if p.key == "image:576:female_heads")
    cell = gp.render(folder, heads, 30)                          # column 7, row 2: the second file's half
    rel, rect = gp.entry_cells(folder, heads.entry)[30]
    assert rel == "female_heads00.png" and cell == folder.picture(rel).sub(rect[0], rect[1], rect[2] - rect[0],
                                                                          rect[3] - rect[1])


@needs_game
def test_the_patchers_pictures_are_marked(tmp_path):
    images = tmp_path / "Images"
    (images / "Furniture").mkdir(parents=True)
    source = GAME_DIR / "Images"
    for name in ("carrying.png", "hand.png", "Furniture/HammockStd.png"):
        (images / name).write_bytes((source / name).read_bytes())
    changed = bytearray((source / "hand_open.png").read_bytes())
    (images / "hand_open.png").write_bytes(bytes(changed) + b"\0")                 # other bytes
    (images / "MyMod").mkdir()
    (images / "MyMod" / "new.png").write_bytes((source / "hand.png").read_bytes())
    folder = gp.Folder(tmp_path)
    assert gp.patcher_files(folder) == {"hand_open.png": "changed", "MyMod/new.png": "new"}
    pictures = {p.key: p for p in gp.catalogue(folder)}
    assert pictures["file:MyMod/new.png"].status == gp.PATCHER
    assert pictures["file:MyMod/new.png"].category == "The patcher's pictures"
    assert next(p for p in pictures.values() if p.key.startswith("image:1:")).status == gp.PATCHER
    assert next(p for p in pictures.values() if p.key.startswith("image:2:")).status == ""
    assert next(p for p in pictures.values() if p.key.startswith("image:3:")).status == gp.MISSING


@needs_game
def test_save_all_by_category(folder, pictures, tmp_path):
    chosen = gp.search(pictures, "cursors") + gp.search(pictures, "bar loading")
    saved, failed = gp.save_all(folder, chosen, tmp_path, {"margin": 0, "scale": 1})
    assert failed == [] and saved == 2 + 21
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Cursors", "Meters assembled"]
    assert len(list((tmp_path / "Meters assembled").rglob("*.png"))) == 21


# ====================================================================== against the game's code
@needs_code
def test_the_data_file_is_the_games():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_vf2_image_table as builder
    text = builder.render(builder.build(OBJ_DIR))
    assert text == gp.DATA_FILE.read_text(encoding="utf-8")
    assert text == (ROOT / "work" / "vf2_game_pictures.json").read_text(encoding="utf-8")


@needs_code
def test_every_cell_is_cut_as_the_game_cuts_it(folder):
    pytest.importorskip("unicorn")
    import vf2_pictures_emu as pe
    rig = pe.ImageRig(OBJ_DIR, GAME_DIR / "Images")
    checked = cells = 0
    for entry in gp.table():
        if not all(folder.has(f) for f in entry.files):
            continue
        game = [(f.replace("\\", "/").lower(), r) for f, r in rig.cells(entry.id, entry.kind, entry.cells)]
        mine = [(f.lower(), r) for f, r in gp.entry_cells(folder, entry)]
        assert mine == game, entry
        checked += 1
        cells += len(mine)
    assert checked == 628 and cells == 11922


@needs_code
def test_the_meters_are_the_games():
    pytest.importorskip("unicorn")
    import vf2_pictures_emu as pe
    rig = pe.MeterRig(OBJ_DIR)

    def calls(draws):
        out = []
        for d in draws:
            if d.kind == "draw":
                out.append(("draw", d.image, d.x, d.y))
            elif d.kind == "clip":
                out.append(("clip", *d.rect))
            elif d.kind == "unclip":
                out.append(("unclip",))
            else:
                out.append(("fill", *d.rect, *(pi.f32(v) for v in d.colour)))
        return out

    compared = 0
    for colour in range(16):
        for level in list(range(-5, 106)) + list(range(100, 3200, 37)):
            assert rig.draw("continuous", colour, level) == calls(gp.continuous_meter(colour, level)), (colour, level)
            compared += 1
        for level in list(range(-5, 106)) + list(range(100, 1100, 13)):
            assert rig.draw("sliced", colour, level) == calls(gp.sliced_meter(colour, level)), (colour, level)
            compared += 1
    for colour in range(6):
        for level in range(-5, 106):
            assert rig.draw("variable", colour, level) == calls(gp.variable_meter(colour, 100, 200, level))
            compared += 1
    assert compared > 6000
    rng = random.Random(7)
    for _ in range(3000):
        clip = (rng.randint(0, 50), rng.randint(0, 50), rng.randint(0, 120), rng.randint(0, 120))
        x, y, w, h = rng.randint(-30, 120), rng.randint(-30, 120), rng.randint(1, 40), rng.randint(1, 40)
        assert rig.clip_rect(x, y, w, h, clip) == gp.clip_draw(x, y, w, h, clip), (x, y, w, h, clip)


@needs_code
def test_a_bar_pixel_exact_against_an_independent_composite(folder):
    """The loading screen's bar at several levels against Pillow drawing the game's own calls (made under
    emulation), clipped as ClipRect clips."""
    Image = pytest.importorskip("PIL.Image")
    pytest.importorskip("unicorn")
    import vf2_pictures_emu as pe
    rig = pe.MeterRig(OBJ_DIR)
    files = {e.id: e.file for e in gp.table()}
    for colour, level in ((13, 0), (13, 37), (13, 100), (9, 1500), (8, 64)):
        canvas = Image.new("RGBA", (1100, 700), (0, 0, 0, 0))
        clip = None
        for call in rig.draw("continuous", colour, level):
            if call[0] == "clip":
                clip = call[1:]
            elif call[0] == "unclip":
                clip = None
            elif call[0] == "draw":
                src = Image.open(GAME_DIR / "Images" / files[call[1]]).convert("RGBA")
                x, y = call[2], call[3]
                if clip is not None:
                    box = (max(x, clip[0]), max(y, clip[1]), min(x + src.width, clip[2]), min(y + src.height, clip[3]))
                    if box[2] <= box[0] or box[3] <= box[1]:
                        continue
                    src = src.crop((box[0] - x, box[1] - y, box[2] - x, box[3] - y))
                    x, y = box[0], box[1]
                layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                layer.paste(src, (x, y))
                canvas = Image.alpha_composite(canvas, layer)
        box = canvas.getbbox()
        mine = gp.render_draws(folder, gp.continuous_meter(colour, level))
        if box is None:
            assert mine.bbox() is None
            continue
        want = canvas.crop(box)
        got = mine.cropped(0)
        assert (got.width, got.height) == want.size and bytes(got.data) == want.tobytes(), (colour, level)


# ====================================================================== the window
@pytest.fixture
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
def test_the_all_pictures_tab(tk_root, tmp_path):
    maker = pm.PictureMaker(tk_root, [], str(GAME_DIR))
    maker.quiet = True
    assert [maker.notebook.tab(t, "text") for t in maker.notebook.tabs()] == [
        "From my save", "Make your own", "All game pictures"]
    maker.notebook.select(maker.all_tab)
    maker._tab_changed()
    assert len(maker.all_nodes) == len(maker.load_all())
    maker.search_var.set("bar loading")
    maker.fill_all()
    node, picture = next(iter(maker.all_nodes.items()))
    assert picture.key == "meter:continuous:13"
    maker.all_tree.selection_set(node)
    maker._picked_all()
    maker.all_frame.current(10)
    maker._show_all()
    assert maker.shown["all"] == gp.render(maker.all_source, picture, 10)
    assert "Level 50" in maker.picture_name("all")
    out = maker.save_png("all", str(tmp_path / "bar.png"))
    assert out.is_file()
    maker.search_var.set("cursors")
    maker.fill_all()
    target = maker.save_all_pictures(str(tmp_path / "all"))
    assert len(list(target.rglob("*.png"))) == 2 and "2 picture(s) saved" in maker.last_message
    maker.search_var.set("unused")
    maker.fill_all()
    assert all(p.status == gp.UNUSED or "unused" in p.reason.lower() for p in maker.all_nodes.values())
    maker.close()
