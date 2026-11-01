"""The Picture Maker's house, yard, weather and night pictures (src/vf2_art_house.py) against the game's own code,
run in Unicorn from the B200 desktop objects (tests/vf2_house_emu.py): the map's tiles and their clipping, every
decal the house draws in each state, the weather's draws and fills, the night's lamps, darkness and pixels, and the
pictures the game never shows. Skips without work/ (the objects and a clean game folder)."""
from __future__ import annotations

import os
import struct
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")

pytest.importorskip("unicorn")
if not (OBJ_DIR / "Decal.obj").is_file() or not (GAME_DIR / "Images").is_dir():
    pytest.skip("needs work/desktop_obj_files and work/vanilla_runtime_payload", allow_module_level=True)

import vf2_art_house as h  # noqa: E402
import vf2_game_pictures as gp  # noqa: E402
import vf2_house_emu as he  # noqa: E402
import vf2_picture_image as pi  # noqa: E402


@pytest.fixture(scope="module")
def files():
    return gp.GameFiles(GAME_DIR)


@pytest.fixture(scope="module")
def arts(files):
    return {a.key: a for a in h.arts(files)}


@pytest.fixture(scope="module")
def maprig():
    return he.MapRig(OBJ_DIR)


@pytest.fixture(scope="module")
def cliprig():
    return he.ClipRig(OBJ_DIR)


@pytest.fixture(scope="module")
def decalrig():
    return he.DecalRig(OBJ_DIR)


@pytest.fixture(scope="module")
def imagerig():
    import vf2_pictures_emu
    return vf2_pictures_emu.ImageRig(OBJ_DIR, GAME_DIR / "Images")


@pytest.fixture(scope="module")
def nightrig(files):
    def cells(image, k):
        name, rect = gp.entry_by_id(image).file, None
        if files.has(name):
            rect = gp.cell_of(files, image, k)[1]
        return rect or (0, 0, 10, 100)                              # a missing file: the game's 100 x 100 stand-in
    rig = he.NightRig(OBJ_DIR, GAME_DIR, cells)
    rig.columns = lambda image: gp.entry_by_id(image).cols or 1
    rig.lights = rig.load()
    return rig


@pytest.fixture(scope="module")
def pixels():
    return he.PixelRig(OBJ_DIR)


@pytest.fixture(scope="module")
def graph():
    import vf2_misc_emu
    return vf2_misc_emu.CallGraph(OBJ_DIR)


def _emulated_map(maprig, cliprig, box) -> list:
    """CWorldMap::Draw with the view at (0, 0) and the clipping rectangle `box`, each tile cut by ClipRect."""
    out = []
    for name, x, y in maprig.draw((0, 0), box):
        cut = cliprig.clip((0, 0, 512, 512), x, y, box)
        if cut is not None:
            rect, cx, cy = cut
            out.append((name, rect, cx, cy))
    return out


def _layers(art) -> list:
    return [(d.file, tuple(d.rect), d.x, d.y) for d in art.layers if isinstance(d, gp.Draw) and d.make is None]


def _split(art):
    tiles = [layer for layer in _layers(art) if layer[0].startswith("MapX")]
    rest = [layer for layer in _layers(art) if not layer[0].startswith("MapX")]
    return tiles, rest


# ------------------------------------------------------------------ the map
def test_the_tiles_are_the_ones_the_map_loads(maprig):
    assert maprig.tiles() == h.map_tiles()


def test_every_map_part_is_the_maps_own_draw(arts, maprig, cliprig):
    checked = 0
    for art in arts.values():
        tiles, rest = _split(art)
        if not tiles:
            continue
        if art.key in ("house/map",) or art.key.startswith("house/state/"):
            box = (0, 0, h.MAP_SIZE, h.MAP_SIZE)
        else:
            box = h._box([d for d in art.layers if isinstance(d, gp.Draw) and not d.file.startswith("MapX")]) \
                if rest else (min(t[2] for t in tiles), min(t[3] for t in tiles),
                              max(t[2] + t[1][2] - t[1][0] for t in tiles), max(t[3] + t[1][3] - t[1][1] for t in tiles))
        assert tiles == _emulated_map(maprig, cliprig, box), art.key
        checked += 1
    assert checked > 100


# ------------------------------------------------------------------ the decals
def _run(rig, state):
    return rig.run(upgrades=state.get("upgrades", ()), props=state.get("props", ()), food=state.get("food", 0),
                   gs=state.get("gs"))


def test_every_decal_is_what_the_house_draws_in_its_state(decalrig):
    for key, _cat, _label, on, off, draws, _why in h.decals():
        drawn, without = _run(decalrig, on), _run(decalrig, off)
        added = [d for d in drawn if d not in without]
        assert added == [(image, x, y, cell, 1.0) for image, cell, x, y in draws], key


def test_props_that_draw_the_same(decalrig):
    for prop, same in h.SAME_AS.items():
        assert decalrig.run(props=(prop,)) == decalrig.run(props=(same,)), hex(prop)


def test_the_new_house_and_the_finished_house(decalrig):
    assert decalrig.run() == [(image, x, y, cell, 1.0) for image, cell, x, y in h.NEW_HOUSE]
    assert decalrig.run(upgrades=h.ALL_UPGRADE_ITEMS) == \
        [(image, x, y, cell, 1.0) for image, cell, x, y in h.ALL_UPGRADES]
    assert decalrig.asked_upgrades <= set(h.ALL_UPGRADE_ITEMS)


def test_a_renovation_draws_while_it_is_being_finished(decalrig):
    for _word, _label, item, _name, _prop, image, x, y in h._ROOMS:
        decalrig.run(upgrades=(item,))
        props = sorted(decalrig.asked_states)
        finishing = [p for p in props if (image, x, y, 0, 1.0) in decalrig.run(upgrades=(item,), states=(p,))]
        assert len(finishing) == 1, hex(item)


def test_decal_layers_are_the_grids_own_cells(arts, files, imagerig):
    for key, _cat, _label, _on, _off, draws, _why in h.decals():
        art = arts[key]
        _tiles, rest = _split(art)
        want = []
        for image, cell, x, y in draws:
            entry = gp.entry_by_id(image)
            kind = "image" if entry.kind == "image" else "grid"
            name, rect = imagerig.cells(image, kind, cell + 1)[-1]
            want.append((files.relative(name.lower()), rect, x, y))
        assert [(files.relative(f.lower()), r, x, y) for f, r, x, y in rest] == want, key


def test_whole_house_pictures(arts):
    for key, draws in (("house/state/new", h.NEW_HOUSE), ("house/state/everything", h.ALL_UPGRADES)):
        _tiles, rest = _split(arts[key])
        assert [(r[2], r[3]) for r in rest] == [(x, y) for _i, _c, x, y in draws]


# ------------------------------------------------------------------ the weather
@pytest.fixture(scope="module")
def weatherrig():
    return he.WeatherRig(OBJ_DIR)


@pytest.fixture(scope="module")
def skyrig():
    return he.SkyRig(OBJ_DIR)


def test_the_haze_each_weather_moves_to(weatherrig):
    for kind in range(6):
        assert weatherrig.target_haze(kind) == pytest.approx(h.HAZE.get(kind, 0.0), abs=1e-7), kind


def test_the_weathers_draw(weatherrig):
    subs = {0: [], 1: [("sunbeam",)], 2: [("rain",)], 3: [("lightning",), ("rain",)], 4: [("fog",)],
            5: [("snow",)]}
    for kind, after in subs.items():
        for haze in (0.2, 0.3):
            calls = weatherrig.draw(kind, haze, True, h.SCREEN)
            assert calls == [("fill", h.SCREEN, tuple(round(v, 7) for v in h.haze_fill(haze)))] + after
        assert weatherrig.draw(kind, 0.3, False, h.SCREEN) == after + [("night",)]


def test_the_lightning_flash(skyrig):
    calls = skyrig.flash(True, h.SCREEN)
    assert calls == [("fill", h.SCREEN, h.FLASH)]
    assert skyrig.flash(False, h.SCREEN) == []


def test_the_sunbeam(arts, files, skyrig, cliprig):
    x, y = h.SUNBEAM_AT
    calls = skyrig.sunbeams([(x, y, 1.0), (x, -60, 1.0), (x, 1, 1.0)], 1.0, screen=h.SCREEN)
    assert calls[0] == ("grid", 586, x, y, 0, 1.0)
    assert calls[1] == ("grid", 586, x, -60, 0, 0.5)              # fading in over the top 120 pixels
    assert len(calls) == 2                                          # a top inside the screen is not drawn
    name, cell = gp.cell_of(files, 586, 0)
    rect, cx, cy = cliprig.clip(cell, x, y, h.SCREEN)
    assert _layers(arts["house/weather/sunbeam"]) == [(name, rect, cx, cy)]


def test_the_fog(arts, files, skyrig, cliprig):
    x, y = h.FOG_AT
    calls = skyrig.fog_draw({(3, 0): (float(x), float(y), 1.0), (0, 1): (10.0, 20.0, 1.0)}, 1.0,
                            screen=h.SCREEN)
    assert ("image", 587, x, y, 1.0) in calls
    assert ("image", 587, 10, 20, 0.25) in calls                    # the farthest depth
    w, hh = files.size("map_fog.png")
    rect, cx, cy = cliprig.clip((0, 0, w, hh), x, y, h.SCREEN)
    assert _layers(arts["house/weather/fog"]) == [("map_fog.png", rect, cx, cy)]


def _crop(files, box):
    return h.map_image(files, box)


def test_the_fills_pixels_are_the_games(files, pixels):
    box = (1000, 500, 1064, 548)
    crop = _crop(files, box)
    w, hh = crop.width, crop.height
    fills = [h.haze_fill(0.2), h.haze_fill(0.3), h.colour_floats(h.FLASH)]
    fills += [h.night_fill(d) for d in (1.0, 0.85, 0.65, 0.5)]
    for rgba in fills:
        game = pixels.fill(bytes(crop.data), w, hh, (0, 0, w, hh), rgba)
        assert game == bytes(h.blend_fill(crop, rgba).data), rgba
    # half the screen filled: the rectangle is the game's
    game = pixels.fill(bytes(crop.data), w, hh, (0, 0, w // 2, hh), h.haze_fill(0.3))
    mine = h.blend_fill(crop.sub(0, 0, w // 2, hh), h.haze_fill(0.3))
    rows = [game[y * w * 4:(y * w + w // 2) * 4] for y in range(hh)]
    assert b"".join(rows) == bytes(mine.data)


# ------------------------------------------------------------------ the night
def test_the_lamps_and_their_masks(nightrig, files):
    lamps = h.lamps(files)
    assert [(l["kind"], l["x"], l["y"], l["villager"]) for l in nightrig.lights] == lamps
    for light in nightrig.lights:
        assert light["mask"] == h.LIGHT_MASKS[light["kind"]]
    assert {k for k, *_ in lamps} == {6, 8, 9, 11}


def test_every_kind_of_lamp_asks_for_its_mask(nightrig):
    e = nightrig.e
    for kind in range(1, 12):
        s = e.alloc(0x50)
        e.w32(s, kind)
        e.call("?SetupLightSource@CNight@@AAEXPAUSLightSource@1@@Z", [s], ecx=nightrig.night)
        assert nightrig.ids.get(e.r32(s + 0x1C)) == h.LIGHT_MASKS[kind], kind


def test_the_night_colour_and_darkness(nightrig):
    assert nightrig.colour() == h.NIGHT_COLOUR
    for time_, level in ((0.5, 1.0), (23.0, 0.85), (21.5, 0.65), (20.5, 0.5), (12.0, 0.0)):
        assert nightrig.darkness(time_, 6.0, 20.0, 1.0) == pytest.approx(level, abs=1e-7), time_
    for time_, level in ((23.0, 0.85), (21.5, 0.65), (0.5, 1.0), (20.5, 0.5)):
        calls = nightrig.draw(time_)
        fill = [c for c in calls if c[0] == "fill"]
        assert fill == [("fill", (0, 0, 2048, 2048), (h.NIGHT_COLOUR & 0xFFFFFF) | (h.night_alpha(level) << 24))]


@pytest.mark.parametrize("screen,view", [((0, 0, 2048, 2048), (0, 0)), ((0, 0, 1024, 730), (900, 900)),
                                         ((0, 0, 1024, 730), (700, 300))])
def test_the_night_plan_is_the_games(nightrig, files, screen, view):
    calls = nightrig.draw(23.0, screen=screen, view=view)
    copies = [c for c in calls if c[0] == "copy"]
    masks = [c for c in calls if c[0] == "mask"]
    draws = [c for c in calls if c[0] == "draw"]
    plan = h.night_plan(files, screen, view)
    names = {gp.entry_by_id(i).file: i for i in h.LIGHT_MASKS.values()}
    assert [(c[2], c[3], c[4]) for c in copies] == [(p["copy"], *p["offset"]) for p in plan]
    assert [(m[2], m[3], m[4], m[5]) for m in masks] == [(names[p["mask"]], *p["offset"], p["rect"]) for p in plan]
    assert [(d[2], d[3], d[4], d[5]) for d in draws] == [(p["x"], p["y"], p["rect"], 1.0) for p in plan]
    order = [c[0] for c in calls]
    assert order.index("fill") == 2 * len(plan) and order.count("fill") == 1


def test_the_night_pixels_are_the_games(files, pixels):
    """A crop round two lamps, composed with the game's own FillRect and SetTransparencyMask in Unicorn and SDL's
    blit as "over", equals the module's night picture pixel for pixel."""
    box = (800, 380, 1120, 700)
    level = 0.85
    scene = _crop(files, box)
    w, hh = scene.width, scene.height
    plan = h.night_plan(files, (0, 0, w, hh), box[:2])
    assert len(plan) >= 2
    copies = []
    for lamp in plan:
        cx0, cy0, cx1, cy1 = lamp["copy"]
        mask = files.image(lamp["mask"])
        ox, oy = lamp["offset"]
        cw, ch = mask.width, mask.height
        copy = pi.Image(cw, ch)
        piece = scene.sub(cx0, cy0, cx1 - cx0, cy1 - cy0)       # CopyScreenRect: SDL_UpperBlit, alpha 255
        copy.draw(piece, ox, oy)
        masked = pixels.mask(bytes(copy.data), cw, ch, bytes(mask.data), mask.width, mask.height, ox, oy,
                             lamp["rect"])
        copies.append((pi.Image(cw, ch, masked), lamp))
    screen = pi.Image(w, hh, pixels.fill(bytes(scene.data), w, hh, (0, 0, w, hh), h.night_fill(level)))
    for copy, lamp in copies:
        l, t, r, b = lamp["rect"]
        screen.draw(copy.sub(l, t, r - l, b - t), lamp["x"], lamp["y"])
    assert screen == h.night_image(files, level, box)


def test_the_mask_takes_only_the_alpha(files, pixels):
    mask = files.image("LightSourceMask250.png")
    copy = bytes(range(256)) * (mask.width * mask.height * 4 // 256)
    out = pixels.mask(copy, mask.width, mask.height, bytes(mask.data), mask.width, mask.height, 10, 20,
                      (10, 20, 200, 240))
    for y in (20, 100, 239):
        for x in (10, 125, 199):
            at = (y * mask.width + x) * 4
            assert out[at:at + 3] == copy[at:at + 3]
            assert out[at + 3] == mask.data[at + 3]
    assert out[3] == copy[3]                                        # outside the rectangle: untouched


# ------------------------------------------------------------------ never shown
def test_the_wind_is_never_drawn(graph):
    for name in ("?Draw@CWind@@QAEXXZ", "?Update@CWind@@QAEXXZ"):
        assert not graph.callers(name), name
    assert graph.callers("?LoadAssets@CWind@@QAEXXZ") == {"?GameUpdate@theGame@@UAEXXZ"}
    assert not any(h.USAGE[image][0] for image in (590, 591, 592))


def test_hail_is_never_seen(graph):
    for name in ("?Reset@CHail@@QAEX_N@Z", "?Update@CHail@@QAEXXZ", "?Draw@CHail@@QAEXXZ"):
        assert not graph.callers(name), name
    users = graph.callers("?Hail@@3VCHail@@A")
    assert users <= {"?GameUpdate@theGame@@UAEXXZ", "?Shutdown@theGame@@UAEXXZ", "?DrawScene@theMainScene@@MAEXXZ",
                     "?EndScene@CSceneManager@@QAEXXZ", "??__EHail@@YAXXZ", "??__FHail@@YAXXZ"}, users
    rig = he.HailRig(OBJ_DIR)
    first = rig.frame()
    scaled = [c for c in first if c[0] == "scaled"]
    assert len(scaled) == 256 and all(c[3] == 0.0 for c in scaled)
    assert rig.frame() == []
    assert not h.USAGE[589][0]


def test_unused_light_masks(graph, files):
    callers = graph.callers("?AddLightSource@CNight@@QAEXW4ELightSource@@UldwPoint@@@Z") | \
        graph.callers("?AddLightSource@CNight@@QAEXW4ELightSource@@H@Z")
    assert callers == {"?HandleKeyCharacter@CLightSourceEditor@@UAE?B_ND@Z"}
    # a virtual of CLightSourceEditor: only an object of it could call it, and there is one, the global, which only
    # its own start-up code names; the constructor names nothing but the vtable, and only the constructor names that
    vtable, ctor = "??_7CLightSourceEditor@@6B@", "??0CLightSourceEditor@@QAE@XZ"
    assert graph.callers("?LightSourceEditor@@3VCLightSourceEditor@@A") == {"??__ELightSourceEditor@@YAXXZ"}
    assert graph.callers(ctor) == {"??__ELightSourceEditor@@YAXXZ"}
    assert graph.refs[ctor] == {vtable}
    assert graph.callers(vtable) == {ctor}
    assert graph.refs["??__ELightSourceEditor@@YAXXZ"] <= {"?LightSourceEditor@@3VCLightSourceEditor@@A", ctor,
                                                          "??__FLightSourceEditor@@YAXXZ", "_atexit"}
    kinds = {k for k, *_ in h.lamps(files)}
    used = {h.LIGHT_MASKS[k] for k in kinds}
    for image in range(598, 608):
        assert h.USAGE[image][0] == (image in used), image


def test_usage_matches_the_pictures(arts):
    assert not arts["house/weather/leaf1"].used and not arts["house/weather/hailstone"].used
    for key, art in arts.items():
        assert key.startswith("house/")
        assert art.category.split("/")[0] in gp.CATEGORY_ORDER
        assert bool(art.checked) == art.used, key


def test_arts_is_fast(files):
    start = time.perf_counter()
    h.arts(files)
    assert time.perf_counter() - start < 1.0


# ------------------------------------------------------------------ rain, snow, the intro story
@pytest.fixture(scope="module")
def contentrig():
    return he.ContentRig(OBJ_DIR, GAME_DIR)


@pytest.fixture(scope="module")
def rainrig(contentrig):
    return he.RainRig(OBJ_DIR, contentrig.material)


def test_the_rains_lines_are_the_games(rainrig):
    drops = h.rain_drops(h.SCREEN)
    calls = rainrig.draw(drops, 1.0, h.SCREEN)
    assert [c[1:] for c in calls] == h.rain_lines(drops)
    half = rainrig.draw(drops, 0.5, h.SCREEN)
    assert [c[1:] for c in half if c[1] > -5000] == h.rain_lines(drops, 0.5)
    assert len(h.rain_lines(drops, 0.5)) == 256


def test_the_line_pixels_are_the_games(files, pixels):
    box = (200, 400, 296, 472)
    crop = _crop(files, box)
    w, hh = crop.width, crop.height
    lines = [(10, 50, 0, 10, h.RAIN_COLOUR, 0.6, 0.0), (5, 5, 90, 30, 0x00335577, 0.2, 0.9),
             (90, 70, 3, 2, 0x00FFFFFF, 1.0, 0.0), (40, 0, 41, 71, 0x00102030, 0.45, 0.45),
             (95, 10, 95, 60, h.RAIN_COLOUR, 0.5, 0.0), (96, 10, 50, 20, h.RAIN_COLOUR, 0.5, 0.0),
             (-1, 10, 50, 20, h.RAIN_COLOUR, 0.5, 0.0)]
    for line in lines:
        game = pixels.line(bytes(crop.data), w, hh, *line, clip=(0, 0, w - 1, hh - 1))
        mine = crop.copy()
        h.draw_line(mine, *line, clip=(0, 0, w - 1, hh - 1))
        assert game == bytes(mine.data), line
    for line in h.rain_lines(h.rain_drops((0, 0, w, hh), 40, seed=9)):
        game = pixels.line(bytes(crop.data), w, hh, *line, clip=(0, 0, w - 1, hh - 1))
        mine = crop.copy()
        h.draw_line(mine, *line, clip=(0, 0, w - 1, hh - 1))
        assert game == bytes(mine.data), line


def test_the_rains_splashes(files, rainrig, contentrig):
    import vf2_misc_emu as me
    misc = me.MiscRig(OBJ_DIR, GAME_DIR)
    want = h.splash_draws(files)
    for (x, y, frame), draw in zip(h.SPLASH_POINTS, want):
        assert contentrig.material(x, y) == 2
        anims = rainrig.splash((x, y), 1.0, h.SCREEN)
        assert anims == [("anim", h.SPLASH_EFFECT, x, y, 1, 0, -1, 3, 1)]
        misc._clear()
        misc.random = []
        index = misc.e.call("?AddAnim@CFloatingAnim@@QAE?BHW4EFloatingAnim@@UldwPoint@@H_NW4EFloatingAnimEffect@@"
                            "W4EScenePriority@@2@Z", [h.SPLASH_EFFECT, x, y, 1, 0, -1, 3, 1], ecx=misc.anim)
        frames = misc._play(me._s(index))
        assert len(frames) == 3
        image, sx, sy, cell, alpha = frames[frame][0][1:]
        name, rect = gp.cell_of(files, image, cell)
        assert (image, alpha) == (h.SPLASH_IMAGE, 1.0)
        assert draw == (name, rect, sx, sy)
    # elsewhere no splash, on materials 4 and 5 the water rings
    rig = he.RainRig(OBJ_DIR, lambda x, y: x)
    assert rig.splash((9, 0)) == []
    assert rig.splash((4, 0)) == [("anim", 0, 4, 0, 1, 0, -1, 1, 1)]
    assert rig.splash((5, 0)) == [("anim", 0, 5, 0, 1, 0, -1, 1, 1)]


def test_the_storm_is_drawn_in_this_order(weatherrig, skyrig):
    assert [c[0] for c in weatherrig.draw(3, 0.3, True, h.SCREEN)] == ["fill", "lightning", "rain"]


@pytest.mark.parametrize("key,flash", [("house/weather/storm", True), ("house/weather/rain", False)])
def test_the_rain_picture_pixels(files, arts, pixels, key, flash):
    """The whole rain / storm picture, built from the game's own FillRect and DrawLine run in Unicorn over the
    screen (the splashes drawn over the map with the framework's "over", as every picture with transparency)."""
    picture = gp.draw(files, arts[key])
    scene = h.map_image(files, h.SCREEN)
    for name, rect, x, y in h.splash_draws(files):
        l, t, r, b = rect
        scene.draw(files.image(name).sub(l, t, r - l, b - t), x, y)
    w, hh = scene.width, scene.height
    lines = h.rain_lines(h.rain_drops(h.SCREEN))
    assert len(lines) == 512
    fills = [h.haze_fill(0.3)] + ([h.colour_floats(h.FLASH)] if flash else [])
    raw = pixels.compose(bytes(scene.data), w, hh, fills, lines)
    assert raw == bytes(picture.data)

def test_the_snow(files, arts):
    snow = he.SnowRig(OBJ_DIR)
    scaled = he.ScaledDrawRig(OBJ_DIR)
    flakes = h.snow_flakes(h.SCREEN)
    calls = snow.draw(flakes, 1.0, h.SCREEN)
    assert len(calls) == 128
    w, hh = files.size("snowflake.png")
    want = []
    for _kind, image, x, y, alpha, percent, centred in calls:
        assert image == h.SNOWFLAKE and centred == 1
        (blit,) = scaled.draw((w, hh), x, y, alpha, percent, True)
        _b, bx, by, rect, balpha, bscale, _c = blit
        want.append(("snowflake.png", rect, bx, by, int(round(bscale * 100)), balpha))
    layers = [d for d in arts["house/weather/snow"].layers if d.make is None]
    assert [(d.file, d.rect, d.x, d.y, d.percent, round(d.alpha, 6)) for d in layers] == want
    for layer in range(4):
        assert (round(h.snow_layer(layer)[0], 6), h.snow_layer(layer)[1]) == \
            (calls[32 * layer][4], calls[32 * layer][5])


def test_the_intro_story(files, arts):
    rig = he.StoryRig(OBJ_DIR, lambda image: files.size(gp.entry_by_id(image).file))
    for key, images in (("house/story/hill", [(h.HILL, 0, 0, 1.0)]),
                        ("house/story/house", [(h.HILL, 0, 0, 1.0), (h.HOUSE, 0, 0, 1.0)])):
        calls = [c for c in rig.page(images) if c[0] == "scaled"]
        assert [(gp.entry_by_id(c[1]).file, c[2], c[3], c[4], c[5], c[6]) for c in calls] == \
            [(d.file, d.x, d.y, 0, 1.0, 100) for d in arts[key].layers]
        assert all(d.rect == (0, 0, *files.size(d.file)) for d in arts[key].layers)
