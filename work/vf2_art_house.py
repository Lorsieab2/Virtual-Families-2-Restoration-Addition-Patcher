"""The Picture Maker's house, yard, weather and night pictures for Virtual Families 2, each drawn as the game draws
it (see vf2_game_pictures for the catalogue they join).

Where the rules come from (the B200 desktop objects, work/desktop_obj_files; tests/test_art_house.py runs every one
of these in Unicorn, see tests/vf2_house_emu.py):

* The yard: CWorldMap::LoadAssets names tile (X, Y) "%sX%01dY%01d.jpg" with "Map" and puts it at (512 X, 512 Y),
  X outer, Y inner; CWorldMap::Draw (theMainScene::DrawScene, first) draws every tile that meets the view with
  ldwGameWindow::Draw(image, x, y) at its place less the view's corner (CWorldView +0, +4). The screen shows the
  window CWorldView::scm_sRect (0, 0, the window's width, its height less 38) of the 2048 x 2048 map; every draw
  is cut to theMainScene's clipping rectangle by ldwGameWindowImpl::ClipRect.
* The house's fixed overlays: CDecal (DrawDecals, right after the map) draws a list RefreshDecals / RefreshProps
  make: the renovations not yet bought (damage_*, foundation_*, bathroom2Foundation, CInventoryManager::HaveUpgrade
  of the Expansion items, or still being finished: CEnvironment::GetPropState of eProp_Finishing*), the home
  improvements bought, the doors, curtains, leaks, holes and things left lying around (the props' "on" bytes,
  CEnvironment +7Ch + 10h x prop), the fridge and the food (CFoodStore +78h), the full bin (theGameState +2Ch) and
  the sock pile (theGameState +148h). Each through ldwGameWindow::Draw(grid, x, y, cell, 1.0).
* The weather (CWeather::Draw, after the people): by day the screen is filled grey 0.3 at the weather's haze
  (CWeather +1Ch, which moves to the target SetCurrent gives: 0.2 when cloudy, foggy or snowing, 0.3 in rain or a
  storm); then cloudy weather's sunbeams (CSunBeam::Draw), a storm's lightning (CLightning::Draw: a fill of
  224, 240, 255 at alpha 127) and rain (CRain::Draw: grey lines, not pictures), fog (CFog::Draw: map_fog.png at
  4 depths), snow (CSnow::Draw). At night CNight::Draw instead.
* The night (CNight::Draw): each lamp of Assets\\lsmap.dat copies the screen under it (CopyScreenRect) and takes its
  light mask's alpha (ldwImage::SetTransparencyMask: the mask's alpha byte, nothing else); the screen is filled
  dark blue (0, 0, 102) at alpha trunc(178 x darkness + 0.5) (ldwGameWindowImpl::FillRect's own blend: every
  colour byte d becomes (d x (255 - A) >> 8) + (c x A >> 8)), and each lamp's copy is drawn back over it.
  CNight::GetDarknessLevel is 0 by day, rises over the twilight, then 0.65 for the first two hours after sunset,
  0.85 after, and 1.0 from midnight to the morning twilight.
The fills and the night are not plain draws: their pictures are `make=` layers (the pixel rules above, checked on
real pixels against the game's own FillRect and SetTransparencyMask in Unicorn).
"""
from __future__ import annotations

import struct

import vf2_game_pictures as gp
import vf2_picture_image as pi

TITLE = "House, yard, weather and night"
MAP_SIZE = 2048
TILE = 512
CHECKED = "Checked against the game's own drawing code ({code}) run in Unicorn."
MAP_CHECK = CHECKED.format(code="CWorldMap::LoadAssets, CWorldMap::Draw and ldwGameWindowImpl::ClipRect")
DECAL_CHECK = CHECKED.format(code="CDecal::LoadAssets, RefreshDecals, RefreshProps and DrawDecals, over the map's "
                                  "CWorldMap::Draw and ldwGameWindowImpl::ClipRect")
DECAL_DRAW = "Drawn over the map by CDecal::DrawDecals, from the list CDecal::RefreshDecals / RefreshProps make"


# ------------------------------------------------------------------ the map
def map_tiles() -> list[tuple[str, int, int]]:
    """(file, x, y) of the 16 tiles, in CWorldMap::LoadAssets' (and CWorldMap::Draw's) order."""
    return [(f"MapX{x}Y{y}.jpg", TILE * x, TILE * y) for x in range(4) for y in range(4)]


def map_draws() -> list[gp.Draw]:
    return [gp.Draw(name, (0, 0, TILE, TILE), x, y) for name, x, y in map_tiles()]


def map_part(left: int, top: int, right: int, bottom: int) -> list[gp.Draw]:
    """The map as the game draws it with the screen's clipping rectangle (left, top, right, bottom) and the view
    at (0, 0): each tile CWorldMap::Draw draws, cut by ClipRect."""
    out = []
    for name, x, y in map_tiles():
        x0, y0 = max(left, x), max(top, y)
        x1, y1 = min(right, x + TILE), min(bottom, y + TILE)
        if x1 > x0 and y1 > y0:
            out.append(gp.Draw(name, (x0 - x, y0 - y, x1 - x, y1 - y), x0, y0))
    return out


def map_image(files: gp.GameFiles, box=(0, 0, MAP_SIZE, MAP_SIZE)) -> pi.Image:
    """The map's pixels in `box` (the tiles are opaque JPEGs: a plain copy)."""
    left, top, right, bottom = box
    out = pi.Image(right - left, bottom - top)
    for draw in map_part(left, top, right, bottom):
        tile = files.image(draw.file)
        l, t, r, b = draw.rect
        row = (r - l) * 4
        for yy in range(t, b):
            src = (yy * tile.width + l) * 4
            dst = ((yy - t + draw.y - top) * out.width + (draw.x - left)) * 4
            out.data[dst:dst + row] = tile.data[src:src + row]
    return out


# ------------------------------------------------------------------ the fill (ldwGameWindowImpl::FillRect)
def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def fill_bytes(rgba: tuple) -> tuple[tuple[int, int, int], int]:
    """FillRect(rect, r, g, b, a)'s colour bytes (each float x 255, truncated, through SDL_MapRGB) and its alpha
    (a x 255 + 0.5, truncated)."""
    colour = tuple(int(f32(f32(c) * 255.0)) for c in rgba[:3])
    return colour, int(f32(f32(f32(rgba[3]) * 255.0) + 0.5))


def colour_floats(value: int) -> tuple:
    """ldwGameWindow::FillRect(rect, ldwColor): the colour dword's bytes (r, g, b, a from the lowest) / 255."""
    return tuple(f32(((value >> (8 * k)) & 0xFF) / 255.0) for k in range(4))


def blend_fill(image: pi.Image, rgba: tuple) -> pi.Image:
    """FillRect's blend over every pixel of an opaque screen: each colour byte d becomes
    ((d x (255 - A)) >> 8) + ((c x A) >> 8), in a byte; at A = 255 (a = 1.0) SDL_FillRect paints the colour."""
    colour, a = fill_bytes(rgba)
    out = image.copy()
    if f32(rgba[3]) == 1.0:
        for k in range(3):
            out.data[k::4] = bytes((colour[k],)) * (out.width * out.height)
        return out
    for k in range(3):
        add = (colour[k] * a) >> 8
        table = bytes((((d * (255 - a)) >> 8) + add) & 0xFF for d in range(256))
        out.data[k::4] = bytes(out.data[k::4]).translate(table)
    return out


HAZE_GREY = (0.3, 0.3, 0.3)                 # CWeather::Draw: the haze's colour, 0.3 each (3E99999Ah)
HAZE = {1: 0.2, 2: 0.3, 3: 0.3, 4: 0.2, 5: 0.2}     # CWeather::SetCurrent: the haze each weather moves to
WEATHER_NAMES = {0: "sunny", 1: "cloudy", 2: "raining", 3: "stormy", 4: "foggy", 5: "snowing"}
FLASH = 0x7FFFF0E0                          # Lightning_c_sFlashColor (r, g, b, a = E0h, F0h, FFh, 7Fh)
NIGHT_COLOUR = 0xB2660000                   # CNight +838h: r 0, g 0, b 66h, a B2h


def haze_fill(haze: float) -> tuple:
    return (*HAZE_GREY, f32(haze))


def night_alpha(darkness: float) -> int:
    """CNight::Draw: the colour's alpha byte B2h x darkness + 0.5, truncated (x87)."""
    return int(0xB2 * f32(darkness) + 0.5) & 0xFF


def night_fill(darkness: float) -> tuple:
    return colour_floats((NIGHT_COLOUR & 0x00FFFFFF) | (night_alpha(darkness) << 24))


# ------------------------------------------------------------------ the lamps (CNight)
LSMAP = "root:Assets/lsmap.dat"
LIGHT_MASKS = {1: 603, 2: 600, 3: 598, 4: 599, 5: 601, 6: 602, 7: 603, 8: 604, 9: 605, 10: 606, 11: 607}
LIGHT_NAMES = {1: "Fire", 2: "Torch", 3: "Light100", 4: "Light150", 5: "Light200", 6: "Light250", 7: "Light300",
               8: "Light350", 9: "Light400", 10: "Light450", 11: "Light500"}


def lamps(files: gp.GameFiles) -> list[tuple[int, int, int, int]]:
    """Assets\\lsmap.dat's 26 entries of 50h bytes (kind, x, y, villager), as CNight::LoadAssets reads them; kind 0
    is no lamp and kinds over 11 are skipped."""
    data = files.data(LSMAP)
    out = []
    for k in range(min(26, len(data) // 0x50)):
        kind, x, y, who = struct.unpack_from("<4i", data, k * 0x50)
        if 0 < kind <= 11:
            out.append((kind, x, y, who))
    return out


def night_plan(files: gp.GameFiles, screen=(0, 0, MAP_SIZE, MAP_SIZE), view=(0, 0)) -> list[dict]:
    """For each lamp CNight::PreDraw lights: the screen rectangle it copies (`copy`), the mask, the part of the mask
    over it (`rect`, in the mask) and where it is drawn back (x, y). A lamp at (x, y) covers the mask's cell
    centred there (less half a cell, rounded toward zero), cut to the screen."""
    out = []
    for kind, x, y, _who in lamps(files):
        name, cell = gp.cell_of(files, LIGHT_MASKS[kind], 0)
        if not files.has(name):
            continue
        w, h = cell[2] - cell[0], cell[3] - cell[1]
        x0 = x - int(w / 2) - view[0]
        y0 = y - int(h / 2) - view[1]
        x1, y1 = x0 + w, y0 + h
        if x0 > screen[2] or x1 < screen[0] or y0 > screen[3] or y1 < screen[1]:
            continue
        cx0, cy0, cx1, cy1 = max(x0, screen[0]), max(y0, screen[1]), min(x1, screen[2]), min(y1, screen[3])
        rect = (cell[0] + cx0 - x0, cell[1] + cy0 - y0, cell[0] + cx1 - x0, cell[1] + cy1 - y0)
        out.append({"kind": kind, "mask": name, "copy": (cx0, cy0, cx1, cy1), "offset": (cx0 - x0, cy0 - y0),
                    "rect": rect, "x": cx0, "y": cy0})
    return out


def _over_opaque(dst: pi.Image, src: bytes, alphas: bytes, w: int, h: int, x: int, y: int) -> None:
    """src (R, G, B bytes per pixel in a 4-byte stride) with `alphas` over an opaque dst at (x, y): the framework's
    straight "over" (vf2_picture_image.Image.draw) for an opaque destination."""
    dd = dst.data
    for yy in range(h):
        d = ((y + yy) * dst.width + x) * 4
        s = yy * w * 4
        for xx in range(w):
            sa = alphas[yy * w + xx]
            if sa == 255:
                dd[d:d + 3] = src[s:s + 3]
            elif sa:
                coef1 = sa * 255 * 255 * 128 // (255 * 255)
                coef2 = 255 * 128 - coef1
                for c in range(3):
                    t = src[s + c] * coef1 + dd[d + c] * coef2 + (0x80 << 7)
                    dd[d + c] = (((t >> 8) + t) >> 8) >> 7
            s += 4
            d += 4


def night_image(files: gp.GameFiles, darkness: float, box=(0, 0, MAP_SIZE, MAP_SIZE)) -> pi.Image:
    """The map in `box` at night, as CNight::Draw composes it over a screen that shows that part of the map."""
    left, top, right, bottom = box
    scene = map_image(files, box)
    w, h = right - left, bottom - top
    pieces = []
    for lamp in night_plan(files, (0, 0, w, h), (left, top)):
        cx0, cy0, cx1, cy1 = lamp["copy"]
        piece = scene.sub(cx0, cy0, cx1 - cx0, cy1 - cy0)
        l, t, r, b = lamp["rect"]
        mask = files.image(lamp["mask"]).sub(l, t, r - l, b - t)
        pieces.append((bytes(piece.data), bytes(mask.data[3::4]), piece.width, piece.height, cx0, cy0))
    out = blend_fill(scene, night_fill(darkness))
    for data, alphas, pw, ph, x, y in pieces:
        _over_opaque(out, data, alphas, pw, ph, x, y)
    return out


# ------------------------------------------------------------------ rain (CRain) and its lines
RAIN_COLOUR = 0x007F7F7F                    # CRain::Draw: ldwColor 7F7F7Fh, grey
RAIN_DROPS = 512                            # CRain: 512 drops; Draw draws intensity x 512 of them


def _lcg(seed: int):
    """A fixed stand-in for ldwGameState::GetRandom (the picture's drops and flakes are this generator's)."""
    state = seed & 0xFFFFFFFF
    while True:
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        yield state >> 8


def rain_drops(screen=(0, 0, 1024, 730), count: int = RAIN_DROPS, seed: int = 2) -> list[tuple]:
    """A moment of rain: each drop as CRain keeps it (x, y, x before, y before, dx, speed) after CRain::Update moved
    it once from where CRain::Reset put it (x in the screen's width, y in its height; dx 10 or 11, speed 20-59;
    CRain::Update: the line runs from the drop to where it was)."""
    r = _lcg(seed)
    out = []
    for _ in range(count):
        x0, y0 = next(r) % (screen[2] - 12), next(r) % (screen[3] - 60)      # whole lines inside the screen
        dx, speed = 10 + next(r) % 2, 20 + next(r) % 40
        out.append((x0 + dx, y0 + speed, x0, y0, dx, speed))
    return out


def rain_lines(drops, intensity: float = 1.0) -> list[tuple]:
    """CRain::Draw: for each of the first intensity x 512 drops, DrawLine(x, y, x before, y before, grey, alpha
    speed x 0.7 / 60 at the drop fading to 0 at its tail)."""
    out = []
    for k, (x, y, bx, by, _dx, speed) in enumerate(drops):
        if not f32(intensity) * 512.0 > k:
            break
        out.append((x, y, bx, by, RAIN_COLOUR, f32(f32(f32(float(speed)) * f32(0.7)) / 60.0), 0.0))
    return out


def draw_line(image: pi.Image, x0: int, y0: int, x1: int, y1: int, colour: int, a0: float, a1: float,
              clip=None) -> None:
    """ldwGameWindowImpl::DrawLine(x0, y0, x1, y1, ldwColor, a0, a1) on an opaque screen, step for step: nothing
    if either end is outside the clipping rectangle (its right and bottom edges count as inside); a Bresenham line
    from (x0, y0) to (x1, y1), both ends drawn, each pixel's colour bytes d becoming ((d x (255 - a)) >> 8) +
    ((c x a) >> 8) in a byte, the alpha a going from trunc(a0 x 255 + 0.5) in steps of
    trunc(|A0 - A1| x 256 / (2 x the longer side)) / 256 toward A1, in 8.8 fixed point."""
    left, top, right, bottom = clip or (0, 0, image.width, image.height)
    for x, y in ((x0, y0), (x1, y1)):
        if x < left or x > right or y < top or y > bottom:
            return
    colour_bytes = (colour & 0xFF, (colour >> 8) & 0xFF, (colour >> 16) & 0xFF)
    first = int(f32(f32(f32(a0) * 255.0) + 0.5))
    last = int(f32(f32(f32(a1) * 255.0) + 0.5))
    dx, dy = x1 - x0, y1 - y0
    ax, ay = 2 * abs(dx), 2 * abs(dy)
    major = ax if ax > ay else ay
    step = int((abs(first - last) << 8) / major)
    if not f32(a0) <= f32(a1):
        step = -step
    sx, sy = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
    data, w = image.data, image.width

    def blend(x, y, a):
        at = (y * w + x) * 4
        for c in range(3):
            data[at + c] = (((data[at + c] * (255 - a)) >> 8) + ((colour_bytes[c] * a) >> 8)) & 0xFF

    acc = first << 8
    x, y = x0, y0
    blend(x, y, first)
    if ax > ay:
        err = ay - (ax >> 1)
        while x != x1:
            x += sx
            if err >= 0:
                y += sy
                err -= ax
            acc += step
            err += ay
            blend(x, y, acc >> 8)
    else:
        err = ax - (ay >> 1)
        while y != y1:
            y += sy
            if err >= 0:
                x += sx
                err -= ay
            acc += step
            err += ax
            blend(x, y, acc >> 8)


def rain_image(files: gp.GameFiles, box: tuple, drops, haze: float, flash: bool = False,
               splashes=()) -> pi.Image:
    """The screen `box` of the map (the view at its corner) in rain: the splashes (CFloatingAnim, drawn in the scene),
    the haze, a storm's flash, then the drops' lines."""
    out = map_image(files, box)
    for name, rect, x, y in splashes:
        l, t, r, b = rect
        out.draw(files.image(name).sub(l, t, r - l, b - t), x - box[0], y - box[1])
    out = blend_fill(out, haze_fill(haze))
    if flash:
        out = blend_fill(out, colour_floats(FLASH))
    clip = (0, 0, box[2] - box[0], box[3] - box[1])
    for line in rain_lines(drops):
        draw_line(out, *line, clip=clip)
    return out


# the splashes in the rain pictures: (point CWorldView::RandomPoint gives CRain::Update, frame of the splash)
SPLASH_POINTS = ((180, 520, 0), (90, 660, 1), (100, 100, 2), (300, 150, 1), (500, 200, 0), (700, 120, 2))
SPLASH_EFFECT = 0x12                        # CRain::Update on material 2 (effect 0 on materials 4 and 5)
SPLASH_IMAGE = 495                          # raindrops.png, 3 frames (CFloatingAnim::m_sAnim[12h])


def splash_draws(files: gp.GameFiles) -> list[tuple]:
    """Each splash's frame as CFloatingAnim::Draw draws it: centred on the point (less half a cell, 11, 8)."""
    out = []
    for x, y, frame in SPLASH_POINTS:
        name, rect = gp.cell_of(files, SPLASH_IMAGE, frame)
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        out.append((name, rect, x - w // 2, y - h // 2))
    return out


# ------------------------------------------------------------------ snow (CSnow::Draw)
SNOWFLAKE = 588


def snow_layer(layer: int) -> tuple[float, int]:
    """CSnow::Draw's 4 layers of 32 flakes: alpha 1 - layer x 0.4 / 3 and percent trunc(100 - layer x 50 / 3)."""
    alpha = f32(1.0 - f32(f32(float(layer)) * f32(0.39999998) / 3.0))
    percent = int(f32(100.0 - f32(f32(float(layer)) * 50.0) / 3.0))
    return alpha, percent


def snow_flakes(screen=(0, 0, 1024, 730), seed: int = 5) -> list[list[tuple]]:
    """A moment of snow: 4 layers of 32 flakes (whole-pixel places well inside the screen)."""
    r = _lcg(seed)
    return [[(float(4 + next(r) % (screen[2] - 16)), float(4 + next(r) % (screen[3] - 16))) for _ in range(32)]
            for _ in range(4)]


def snow_draws(files: gp.GameFiles, flakes) -> list[gp.Draw]:
    """Each flake as ldwGameWindow::DrawScaled(snowflake, x, y, alpha, percent, centred) hands it to the blitter: a
    scaled flake moved by half what it shrinks (ScaledClipRect, rounded toward zero)."""
    w, h = files.size("snowflake.png")
    out = []
    for layer, row in enumerate(flakes):
        alpha, percent = snow_layer(layer)
        sw = int(f32(f32(w * f32(percent / 100.0)) + 0.5))
        sh = int(f32(f32(h * f32(percent / 100.0)) + 0.5))
        for x, y in row:
            dx = -int((sw - w) / 2) if percent != 100 else 0
            dy = -int((sh - h) / 2) if percent != 100 else 0
            out.append(gp.Draw("snowflake.png", (0, 0, w, h), int(x) + dx, int(y) + dy, percent, alpha))
    return out


# ------------------------------------------------------------------ the intro story's pictures (CStory)
HILL, HOUSE = 0x172, 0x173


def computed(key: str, box: tuple, make) -> gp.Draw:
    return gp.Draw(f"computed:{key}", (0, 0, box[2] - box[0], box[3] - box[1]), box[0], box[1], make=make)


# ------------------------------------------------------------------ the decals
# (key, category, label, the state it is drawn in, the state it is not (the test runs both), draws (image id,
# cell, x, y), why).  States: upgrades bought (CInventoryManager::HaveUpgrade), props on (CEnvironment), food
# (CFoodStore), theGameState fields.
REN = "House and yard/Renovations"
UPG = "Furniture and objects/Home improvements"
LEFT = "Furniture and objects/Things left around"
KITCHEN = "Food and cooking/In the kitchen"
LEAKS = "House and yard/Leaks and puddles"
HOLES = "House and yard/Yard holes"
DOORS = "House and yard/Doors and curtains"

_ROOM_WHY = ("Drawn until the {what} renovation (eInventoryItem_{item}) is bought, and again while it is being "
             "finished (eProp_{prop}).")
_ROOMS = (
    ("frontporch", "Front porch, before it is built", 0xE1, "ExpansionDeck", "FinishingDeckExpansion", 535,
     1427, 1243),
    ("laundry", "Laundry room, before it is built", 0xE2, "ExpansionLaundry", "FinishingLaundryRoomExpansion", 534,
     272, 1443),
    ("westbedroom", "West bedroom, damaged", 0xE3, "ExpansionAux1", "FinishingAux1RoomExpansion", 532, 318, 1052),
    ("eastbedroom", "East bedroom, damaged", 0xE4, "ExpansionBedroom1", "FinishingBedroom1Expansion", 529, 1067, 629),
    ("kidsroom", "Kids' room, before it is built", 0xE5, "ExpansionBedroom2", "FinishingBedroom2Expansion", 533,
     1061, 261),
    ("bathroom2", "Second bathroom, before it is built", 0xE6, "ExpansionBathroom2", "FinishingBathroom2Expansion",
     537, 805, 151),
    ("masterbedroom", "Master bedroom, damaged", 0xE7, "ExpansionLivingroom2", "FinishingLivingroom2Expansion", 531,
     620, 406),
    ("diningroom", "Dining room, damaged", 0xE8, "ExpansionDiningroom", "FinishingDiningroomExpansion", 528, 654,
     807),
    ("livingroom", "Living room, damaged", 0xE9, "ExpansionLivingroom1", "FinishingLivingroomExpansion", 530, 50,
     596),
    ("backporch", "Back porch, before it is built", 0xEA, "ExpansionReardeck", "FinishingBackPorchExpansion", 536,
     92, 549),
)
_UPGRADES = (
    ("monitor_w", "Office: second monitor (west desk)", 0xEB, ((542, 0, 1418, 965),)),
    ("monitor_e", "Office: second monitor (east desk)", 0xEC, ((543, 0, 1753, 879),)),
    ("airpurifier", "Office: air purifier", 0xED, ((546, 0, 1853, 997),)),
    ("battery", "Office: battery backup", 0xEE, ((547, 0, 1461, 960),)),
    ("fax", "Office: fax machine", 0xEF, ((548, 0, 1811, 933),)),
    ("bin", "Office: waste-paper bin", 0xF0, ((549, 0, 1355, 1040),)),
    ("printer", "Office: printer", 0xF1, ((550, 0, 1846, 950),)),
    ("shredder", "Office: shredder", 0xF2, ((551, 0, 1369, 1016),)),
    ("speakers", "Office: speakers", 0xF3, ((552, 0, 1732, 887), (552, 0, 1793, 924))),
    ("router", "Office: router", 0xF4, ((553, 0, 1507, 1088),)),
    ("whiteboard", "Office: whiteboard", 0xF5, ((554, 0, 1496, 878),)),
    ("microwave", "Kitchen: microwave", 0xF6, ((561, 0, 1294, 1033),)),
    ("coffee", "Kitchen: coffee maker", 0xF7, ((556, 0, 1234, 1066),)),
    ("espresso", "Kitchen: espresso machine", 0xF8, ((557, 0, 1266, 1051),)),
    ("foodprocessor", "Kitchen: food processor", 0xF9, ((559, 0, 1472, 1128),)),
    ("blender", "Kitchen: blender", 0xFA, ((555, 0, 1457, 1112),)),
    ("knives", "Kitchen: professional knives", 0xFB, ((560, 0, 1340, 1082),)),
    ("spicerack", "Kitchen: spice rack (no microwave)", 0xFC, ((558, 0, 1305, 1041),)),
    ("mortar", "Kitchen: mortar and pestle", 0xFD, ((562, 0, 1368, 1071),)),
    ("waffle", "Kitchen: waffle iron", 0xFE, ((564, 0, 1339, 1055),)),
    ("superfridge", "Kitchen: super fridge", 0xFF, ((563, 0, 1110, 1126),)),
    ("drillpress", "Workshop: drill press", 0x100, ((565, 0, 1093, 1533),)),
    ("fan", "Workshop: fan", 0x101, ((566, 0, 1279, 1606),)),
    ("furnace", "Workshop: furnace", 0x102, ((567, 0, 1055, 1576),)),
    ("grinder", "Workshop: grinder", 0x103, ((568, 0, 1123, 1535),)),
    ("lathe", "Workshop: lathe", 0x104, ((569, 0, 1061, 1665),)),
    ("partsbox", "Workshop: parts box", 0x105, ((570, 0, 886, 1614),)),
    ("redtoolbox", "Workshop: red toolbox", 0x106, ((571, 0, 928, 1602),)),
    ("shopvac", "Workshop: shop vacuum", 0x107, ((572, 0, 1323, 1637),)),
    ("toolwall", "Workshop: tool wall", 0x108, ((573, 0, 986, 1540),)),
    ("toolbox", "Workshop: portable toolbox", 0x109, ((501, 0, 1025, 1731),)),
)
# (key, category, label, prop, draws, what it means)
_PROPS = (
    ("hole/1/small", HOLES, "Gopher hole 1, small", 0x05, ((279, 0, 326, 255),), "GopherHole1EmptySM"),
    ("hole/1/large", HOLES, "Gopher hole 1, large", 0x06, ((280, 0, 326, 255),), "GopherHole1EmptyLG"),
    ("hole/1/gopher", HOLES, "Gopher in hole 1", 0x07, ((281, 0, 326, 255),), "GopherHole1Gopher"),
    ("hole/2/small", HOLES, "Gopher hole 2, small", 0x08, ((279, 0, 556, 260),), "GopherHole2EmptySM"),
    ("hole/2/large", HOLES, "Gopher hole 2, large", 0x09, ((280, 0, 556, 260),), "GopherHole2EmptyLG"),
    ("hole/2/gopher", HOLES, "Gopher in hole 2", 0x0A, ((281, 0, 556, 260),), "GopherHole2Gopher"),
    ("hole/3/small", HOLES, "Hole 3, small", 0x0B, ((279, 0, 1664, 193),), "HoleSM1"),
    ("hole/3/large", HOLES, "Hole 3, large", 0x0C, ((280, 0, 1664, 193),), "HoleLG1"),
    ("kitchen/nwcounter", KITCHEN, "Food being prepared (north-west counter)", 0x0E, ((275, 0, 1378, 1095),),
     "KitchenNWCounter"),
    ("kitchen/necounter", KITCHEN, "Food being prepared (north-east counter)", 0x0F, ((275, 1, 1418, 1105),),
     "KitchenNECounter"),
    ("kitchen/recipe", KITCHEN, "Recipe on the counter", 0x11, ((276, 0, 1490, 1160),), "KitchenRecipe"),
    ("left/memoirs", LEFT, "Memoirs on the kitchen table", 0x12, ((478, 54, 1245, 1219),), "KitchenTableMemoirs"),
    ("left/laundry_kids", LEFT, "Laundry basket in the kids' room", 0x13, ((478, 5, 1448, 1048),),
     "LaundryKidsRoom"),
    ("left/laundry_master", LEFT, "Laundry basket in the master bedroom", 0x14, ((478, 5, 1184, 909),),
     "LaundryMasterBR"),
    ("left/laundry_room", LEFT, "Laundry basket in the laundry room", 0x15, ((478, 5, 475, 924),),
     "LaundryLaundryRoom"),
    ("lights/laundry", "Furniture and objects/Lights", "Laundry machines' green lights", 0x16,
     ((283, 0, 532, 949), (283, 0, 500, 977)), "LaundryMachine"),
    ("lights/router", "Furniture and objects/Lights", "Broken router's red light", 0x17, ((284, 0, 1545, 1129),),
     "MalfunctionRouter"),
    ("left/magazine", LEFT, "Magazine in the living room", 0x18, ((478, 49, 1736, 727),), "Magazine0"),
    ("left/game", LEFT, "Board game left out", 0x19, ((478, 35, 1249, 1235),), "Game"),
    ("leak/toilet", LEAKS, "Puddle by the broken toilet", 0x1A, ((575, 1, 614, 1539),), "MalfunctionToilet"),
    ("leak/shower", LEAKS, "Puddle by the broken shower", 0x1B, ((575, 1, 913, 1541),), "MalfunctionShower"),
    ("leak/sink", LEAKS, "Puddle by a broken bathroom sink", 0x1C, ((575, 0, 748, 1428),),
     "MalfunctionBRoomSink0 (MalfunctionBRoomSink1 draws the same)"),
    ("leak/kitchensink", LEAKS, "Puddle by the broken kitchen sink", 0x1F, ((575, 1, 1185, 1212),),
     "MalfunctionKitchenSink"),
    ("leak/toilet2", LEAKS, "Puddle by the broken toilet (second bathroom)", 0x48, ((575, 1, 1181, 358),),
     "MalfunctionToilet2"),
    ("leak/shower2", LEAKS, "Puddle by the broken shower (second bathroom)", 0x49, ((575, 1, 1118, 330),),
     "MalfunctionShower2"),
    ("leak/northsink", LEAKS, "Puddle by the broken north sink", 0x4A, ((575, 1, 948, 372),),
     "MalfunctionNorthSink"),
    ("kitchen/meal", KITCHEN, "Meal on the table", 0x22, ((290, 0, 1240, 1222),), "Meal0"),
    ("kitchen/stovepot", KITCHEN, "Pot on the stove", 0x2B, ((478, 23, 1096, 1176),),
     "StovePot (PressureCooker and StoveBurner draw the same)"),
    ("left/flutes", LEFT, "Glasses on the patio", 0x27, ((478, 21, 173, 1505),), "PatioFlutes"),
    ("kitchen/fryingpan", KITCHEN, "Frying pan on the stove", 0x28, ((478, 25, 1096, 1176),), "ShortTermFryingPan"),
    ("curtain/shower", DOORS, "Shower curtain drawn", 0x29, ((539, 0, 807, 1540),), "Shower"),
    ("curtain/shower2", DOORS, "Shower curtain drawn (second bathroom)", 0x47, ((538, 0, 1071, 212),), "Shower2"),
    ("kitchen/bigpotfull", KITCHEN, "Big pot, full", 0x2C, ((478, 24, 1088, 1178),), "BigPotFull"),
    ("kitchen/bigpotempty", KITCHEN, "Big pot, empty", 0x2D, ((478, 30, 1088, 1178),), "BigPotEmpty"),
    ("kitchen/panfull", KITCHEN, "Pan, full", 0x2E, ((478, 28, 1088, 1178),), "PanFull"),
    ("kitchen/pots", KITCHEN, "Pots by the sink", 0x2F, ((478, 26, 1187, 1116),), "Pots"),
    ("kitchen/dishes", KITCHEN, "Dishes by the sink", 0x30, ((478, 64, 1206, 1115),), "Dishes"),
    ("workshop/0", "Furniture and objects/Workshop", "Work on workshop bench 1", 0x33, ((278, 1, 918, 1645),),
     "WorkshopWorkstation0"),
    ("workshop/1", "Furniture and objects/Workshop", "Work on workshop bench 2", 0x34, ((277, 1, 1158, 1620),),
     "WorkshopWorkstation1"),
    ("workshop/2", "Furniture and objects/Workshop", "Work on workshop bench 3", 0x35, ((277, 2, 1121, 1648),),
     "WorkshopWorkstation2"),
    ("workshop/3", "Furniture and objects/Workshop", "Work on workshop bench 4", 0x36, ((278, 2, 900, 1665),),
     "WorkshopWorkstation3"),
    ("left/orangepeel", LEFT, "Orange peel", 0x50, ((265, 7, 1452, 1901),), "OrangePeel"),
    ("kitchen/cinnamon", KITCHEN, "Cinnamon", 0x51, ((478, 6, 1235, 1081),), "Cinnamon"),
    ("kitchen/cinnamonmortar", KITCHEN, "Cinnamon in the mortar", 0x52, ((266, 0, 1113, 1552),),
     "CinnamonInMortar (AntSprayHalfDone draws the same)"),
    ("kitchen/antpoison", KITCHEN, "Ant poison being bottled", 0x54, ((478, 51, 1078, 1532),), "BottlingAntPoison"),
)
# props that draw the same as another (prop, the one it matches)
SAME_AS = {0x1D: 0x1C, 0x26: 0x2B, 0x2A: 0x2B, 0x53: 0x52}


def decals() -> list[tuple]:
    """Every decal picture: (key, category, label, on state, off state, draws, why)."""
    out = []
    for word, label, item, name, prop, image, x, y in _ROOMS:
        out.append((f"house/renovation/{word}", REN, label, {}, {"upgrades": (item,)}, ((image, 0, x, y),),
                    _ROOM_WHY.format(what=label.split(",")[0].lower(), item=name, prop=prop)))
    out.append(("house/upgrade/oldcomputer_w", UPG, "Office: old computer (west desk)", {}, {"upgrades": (0xEB,)},
                ((544, 0, 1424, 963),), "Drawn until the west desk's second monitor is bought."))
    out.append(("house/upgrade/oldcomputer_e", UPG, "Office: old computer (east desk)", {}, {"upgrades": (0xEC,)},
                ((545, 0, 1755, 878),), "Drawn until the east desk's second monitor is bought."))
    for word, label, item, draws in _UPGRADES:
        out.append((f"house/upgrade/{word}", UPG, label, {"upgrades": (item,)}, {}, draws,
                    "Drawn once this home improvement is bought."))
    out.append(("house/upgrade/spicerack_microwave", UPG, "Kitchen: spice rack (with the microwave)",
                {"upgrades": (0xFC, 0xF6)}, {"upgrades": (0xF6,)}, ((558, 0, 1305, 1013),),
                "With the microwave bought, the spice rack is drawn 28 pixels higher."))
    for word, category, label, prop, draws, name in _PROPS:
        out.append((f"house/{word}", category, label, {"props": (prop,)}, {}, draws,
                    f"Drawn while the house's prop eProp_{name} is on."))
    out.append(("house/door/se", DOORS, "Bathroom door (south-east), closed", {}, {"props": (0x3B,)},
                ((541, 0, 607, 1463),), "Drawn whenever the prop eProp_StallDoorClosedSE is off."))
    out.append(("house/door/sw", DOORS, "Second bathroom door (south-west), closed", {"upgrades": (0xE6,)},
                {"upgrades": (0xE6,), "props": (0x3C,)}, ((540, 0, 1189, 281),),
                "Drawn once the second bathroom is bought, whenever the prop eProp_StallDoorClosedSW is off."))
    for food, word, words in ((0, "empty", "nearly empty (100 food or less)"),
                              (101, "some", "some food (101 to 999)"), (1000, "full", "full (1000 food or more)")):
        cell = {0: 0, 101: 1, 1000: 2}[food]
        out.append((f"house/fridge/{word}", KITCHEN, f"Fridge open, {words}", {"props": (3,), "food": food},
                    {"food": food}, ((282, cell, 1129, 1129),), "Drawn while the fridge is open (eProp_Fridge)."))
        out.append((f"house/fridge/super/{word}", KITCHEN, f"Super fridge open, {words}",
                    {"props": (3,), "food": food, "upgrades": (0xFF,)}, {"food": food, "upgrades": (0xFF,)},
                    ((282, cell + 3, 1129, 1129),),
                    "Drawn while the fridge is open (eProp_Fridge) once the super fridge is bought."))
    out.append(("house/food/cans", KITCHEN, "Cans on the counter (500 food or more)", {"food": 500}, {},
                ((289, 0, 1126, 1117),), "Drawn while there are 500 food or more."))
    out.append(("house/food/bread", KITCHEN, "Bread (1000 food or more)", {"food": 1000}, {"food": 500},
                ((288, 0, 1239, 1090),), "Drawn, with the cans, while there are 1000 food or more."))
    out.append(("house/garbage", LEAKS, "Kitchen bin, full", {"gs": {0x2C: 1}}, {}, ((574, 0, 1048, 1231),),
                "Drawn while the kitchen bin is full (theGameState +2Ch)."))
    for low, high, cell in ((1, 4, 0), (5, 9, 1), (10, 14, 2), (15, 24, 3), (25, 29, 4), (30, None, 5)):
        words = f"{low} to {high} socks" if high else f"{low} socks or more"
        out.append((f"house/socks/{low}", "House and yard/Sock pile", f"Sock pile, {words}", {"gs": {0x148: low}},
                    {}, ((461, cell, 607, 1434),), f"Drawn while the sock pile (theGameState +148h) has {words}."))
    return out


def grid_cell(image: int, cell: int) -> int:
    """The cell ldwGameWindowImpl::Draw(grid, x, y, cell, alpha) really draws: it asks GetCellRect for column
    cell % columns and row cell / columns, and GetCellRect clamps each to the grid (so cell 2 of a 2 x 1 grid is
    cell 0, and any cell of a one-cell picture is that cell)."""
    entry = gp.entry_by_id(image)
    cols, rows = max(1, entry.cols), max(1, entry.rows)
    return min(cell // cols, rows - 1) * cols + min(cell % cols, cols - 1)


def _decal_layers(files: gp.GameFiles, draws) -> list[gp.Draw]:
    return [gp.cell(files, image, grid_cell(image, cell), x, y) for image, cell, x, y in draws]


def _box(layers) -> tuple:
    return (min(d.x for d in layers), min(d.y for d in layers),
            max(d.x + d.rect[2] - d.rect[0] for d in layers), max(d.y + d.rect[3] - d.rect[1] for d in layers))


NEW_HOUSE = ((530, 0, 50, 596), (531, 0, 620, 406), (529, 0, 1067, 629), (528, 0, 654, 807), (532, 0, 318, 1052),
             (537, 0, 805, 151), (533, 0, 1061, 261), (534, 0, 272, 1443), (535, 0, 1427, 1243), (536, 0, 92, 549),
             (544, 0, 1424, 963), (545, 0, 1755, 878), (541, 0, 607, 1463))
ALL_UPGRADES = ((542, 0, 1418, 965), (543, 0, 1753, 879), (546, 0, 1853, 997), (547, 0, 1461, 960),
                (548, 0, 1811, 933), (550, 0, 1846, 950), (551, 0, 1369, 1016), (549, 0, 1355, 1040),
                (552, 0, 1732, 887), (552, 0, 1793, 924), (553, 0, 1507, 1088), (554, 0, 1496, 878),
                (561, 0, 1294, 1033), (556, 0, 1234, 1066), (555, 0, 1457, 1112), (564, 0, 1339, 1055),
                (559, 0, 1472, 1128), (560, 0, 1340, 1082), (557, 0, 1266, 1051), (558, 0, 1305, 1013),
                (562, 0, 1368, 1071), (563, 0, 1110, 1126), (565, 0, 1093, 1533), (566, 0, 1279, 1606),
                (567, 0, 1055, 1576), (568, 0, 1123, 1535), (569, 0, 1061, 1665), (573, 0, 986, 1540),
                (571, 0, 928, 1602), (570, 0, 886, 1614), (572, 0, 1323, 1637), (501, 0, 1025, 1731),
                (541, 0, 607, 1463), (540, 0, 1189, 281))
ALL_UPGRADE_ITEMS = tuple(range(0xE1, 0x10A))

# the weather's representative moments
SUNBEAM_AT = (400, -120)                    # a beam's top 120 pixels above the screen: drawn at its full fade
FOG_AT = (300, 200)                         # a nearest-layer fog patch (layer 4: alpha 1 x fade 1 x strength 1)
SCREEN = (0, 0, 1024, 730)                  # a 1024 x 768 window: the view is 768 - 38 high


def arts(files: gp.GameFiles) -> list[gp.Art]:
    out: list[gp.Art] = []

    def add(key, category, label, layers, used, why, checked):
        layers = tuple(layers)
        if all(files.has(d.file) for d in layers if isinstance(d, gp.Draw) and d.make is None):
            out.append(gp.Art(key, category, label, layers, used, why, checked))

    tiles = all(files.has(name) for name, _x, _y in map_tiles())
    add("house/map", "House and yard/The yard", "The whole house and yard (the 16 map tiles)", map_draws(), True,
        "The house screen's background, drawn first by theMainScene::DrawScene (CWorldMap::Draw); the screen shows "
        "a window of it the size of the game's window less the 38-pixel tool tray, wherever the view has scrolled "
        "to.", MAP_CHECK)

    if tiles:
        for name, draws, label, why in (
                ("new", NEW_HOUSE, "The house as a new family finds it",
                 "Nothing bought yet: every renovation still damaged or unbuilt, the old computers, the bathroom "
                 "door closed."),
                ("everything", ALL_UPGRADES, "The house with every renovation and home improvement bought",
                 "Every renovation done and every home improvement bought; no props on, no food.")):
            layers = _decal_layers(files, draws)
            if all(files.has(d.file) for d in layers):
                add(f"house/state/{name}", "House and yard/The yard", label, map_draws() + layers, True,
                    f"{why} {DECAL_DRAW}.", DECAL_CHECK)
        for key, category, label, _on, _off, draws, why in decals():
            layers = _decal_layers(files, draws)
            if not all(files.has(d.file) for d in layers):
                continue
            add(key, category, label, map_part(*_box(layers)) + layers, True, f"{why} {DECAL_DRAW}.", DECAL_CHECK)
            if key.startswith("house/renovation/"):
                add(key + "/done", category, label.split(",")[0] + ", renovated", map_part(*_box(layers)), True,
                    "Once the renovation is bought and finished nothing is drawn over the map here (CDecal::"
                    "RefreshDecals).", DECAL_CHECK)

    if files.has("rosepetalsOnBed.png"):
        add("house/rosepetals", "Furniture and objects/Bedroom", "Rose petals on the bed (drawn where the bed is)",
            [gp.cell(files, 292, 0, 0, 0)], True,
            "Drawn while eProp_RosepetalsOnBed is on, at the place CEnvironment::GetPropPosition gives for it (the "
            f"bed's; here at 0, 0). {DECAL_DRAW}.",
            CHECKED.format(code="CDecal::RefreshProps and DrawDecals"))

    # ---- weather
    weather_check = CHECKED.format(code="CWeather::Draw and CWeather::SetCurrent") + (
        " The fill's pixels: ldwGameWindowImpl::FillRect run in Unicorn on real pixels.")
    if tiles:
        whole = (0, 0, MAP_SIZE, MAP_SIZE)
        for haze, words in ((0.2, "cloudy, foggy or snowy"), (0.3, "rain or a storm")):
            add(f"house/weather/haze/{haze}", "Weather, day and night/Weather",
                f"Daytime haze in {words} weather (over the map)",
                [computed(f"haze/{haze}", whole, lambda f, h=haze: blend_fill(map_image(f), haze_fill(h)))], True,
                f"By day CWeather::Draw fills the screen grey 76, 76, 76 at the weather's haze, which moves to "
                f"{haze} in {words} weather (CWeather::SetCurrent).", weather_check)
        add("house/weather/lightning", "Weather, day and night/Weather",
            "Lightning flash in a daytime storm (over the map; the rain's lines left out)",
            [computed("lightning", whole, lambda f: blend_fill(blend_fill(map_image(f), haze_fill(0.3)),
                                                               colour_floats(FLASH)))], True,
            "In a storm, after the haze, CLightning::Draw fills the screen with 224, 240, 255 at alpha 127 while the "
            "flash lasts; then CRain::Draw draws the rain as grey lines (not a picture).",
            CHECKED.format(code="CWeather::Draw and CLightning::Draw") + " The fill's pixels: "
            "ldwGameWindowImpl::FillRect run in Unicorn on real pixels.")
        if files.has("sunbeam.png"):
            name, cell = gp.cell_of(files, 586, 0)
            w, h = cell[2] - cell[0], cell[3] - cell[1]
            x, y = SUNBEAM_AT
            box = (0, 0, x + w, y + h)
            add("house/weather/sunbeam", "Weather, day and night/Weather",
                "Sunbeam in cloudy weather, at full strength (over the map's top left)",
                [computed("sunbeam", box, lambda f, b=box: blend_fill(map_image(f, b), haze_fill(0.2))),
                 gp.Draw(name, (cell[0], cell[1] - y, cell[2], cell[3]), x, 0)], True,
                "In cloudy weather CSunBeam::Draw hangs 64 beams from random places: a beam is drawn only while its "
                "top is above the screen's top, at its fade x the weather's strength, and fades in over the top 120 "
                "pixels; this is a fully faded-in beam whose top is 120 pixels above the screen (cut there), over "
                "the haze of cloudy weather at its target 0.2.",
                CHECKED.format(code="CWeather::Draw, CSunBeam::Draw and ldwGameWindowImpl::ClipRect") +
                " The haze's pixels: ldwGameWindowImpl::FillRect run in Unicorn on real pixels.")
        if files.has("map_fog.png"):
            fw, fh = files.size("map_fog.png")
            x, y = FOG_AT
            box = (0, 0, x + fw, y + fh)
            add("house/weather/fog", "Weather, day and night/Weather",
                "Fog patch, nearest layer at full strength (over the map's top left)",
                [computed("fog", box, lambda f, b=box: blend_fill(map_image(f, b), haze_fill(0.2))),
                 gp.Draw("map_fog.png", (0, 0, fw, fh), x, y)], True,
                "In fog CFog::Draw draws map_fog.png 256 times, 64 patches at each of 4 depths, each at its fade x "
                "its depth (0.25, 0.5, 0.75, 1) x the weather's strength, drifting with the view; this is one patch "
                "of the nearest depth fully faded in, over the haze of foggy weather at its target 0.2.",
                CHECKED.format(code="CWeather::Draw and CFog::Draw") +
                " The haze's pixels: ldwGameWindowImpl::FillRect run in Unicorn on real pixels.")

        # ---- rain and snow, over the screen at the map's top left
        rain_check = CHECKED.format(code="CWeather::Draw, CRain::Draw, CRain::Update, CContentMap::GetMaterial and "
                                         "CFloatingAnim::AddAnim / Draw") + (
            " The pixels: ldwGameWindowImpl::FillRect and DrawLine run in Unicorn on real pixels.")
        if files.has("raindrops.png"):
            drops = rain_drops(SCREEN)
            splashes = splash_draws(files)
            for key, label, haze, flash, why in (
                    ("rain", "Rain over the house (a moment of rain at full strength)", 0.3, False,
                     "In rain CRain::Update adds a splash (raindrops.png, 3 frames, centred) where a random point of "
                     "the view is ground of material 2 (on materials 4 and 5 a water ring instead; elsewhere none), "
                     "drawn in the scene under the weather; CWeather::Draw then fills the haze (0.3 here, its "
                     "target) and CRain::Draw draws its 512 drops as grey lines from each drop back to where it was, "
                     "fading from alpha speed x 0.7 / 60 to 0 (ldwGameWindowImpl::DrawLine)."),
                    ("storm", "A storm over the house, with the lightning flash", 0.3, True,
                     "As rain, with the storm's lightning flash (CLightning::Draw: 224, 240, 255 at alpha 127) "
                     "filled after the haze and before the rain's lines.")):
                add(f"house/weather/{key}", "Weather, day and night/Weather", label,
                    [computed(key, SCREEN, lambda f, h=haze, fl=flash, d=drops, s=splashes:
                              rain_image(f, SCREEN, d, h, fl, s))], True,
                    f"{why} The drops' places and the splashes' points and frames are a fixed stand-in for the game's "
                    "random numbers.", rain_check)
        if files.has("snowflake.png"):
            flakes = snow_flakes(SCREEN)
            add("house/weather/snow", "Weather, day and night/Weather", "Snow falling over the house (full strength)",
                [computed("snow", SCREEN, lambda f: blend_fill(map_image(f, SCREEN), haze_fill(0.2)))]
                + snow_draws(files, flakes), True,
                "In snow CWeather::Draw fills the haze (0.2, its target) and CSnow::Draw draws 4 layers of 32 flakes "
                "(snowflake.png): the nearest whole, the others at 83%, 66% and 50% and alpha 0.87, 0.73 and 0.6, "
                "each moved by half what it shrinks (ldwGameWindow::DrawScaled, centred). The flakes' places are a "
                "fixed stand-in for the game's random numbers. The settling snow on the ground (CSnow::DrawIce) is "
                "left out.",
                CHECKED.format(code="CWeather::Draw, CSnow::Draw and ldwGameWindow::DrawScaled as far as "
                                    "BlitRectWithAlpha") + " The haze's pixels: ldwGameWindowImpl::FillRect run in "
                "Unicorn. The scaled, faded flakes' pixels are the Picture Maker's own scaling and fading, not "
                "checked against BlitRectWithAlpha (they can differ by a level or two).")

        # ---- night
        if files.has(LSMAP):
            night_check = CHECKED.format(code="CNight::LoadAssets, CNight::Draw and CNight::GetDarknessLevel") + (
                " The pixels: ldwGameWindowImpl::FillRect and ldwImageImpl::SetTransparencyMask run in Unicorn on "
                "real pixels; each lamp's copy is drawn back at full strength by SDL's own blit, as every picture "
                "with transparency.")
            for level, words in ((1.0, "deep night (midnight to the morning twilight)"),
                                 (0.85, "night (from two hours after sunset)"),
                                 (0.65, "evening (the first two hours after sunset)"),
                                 (0.5, "twilight, half way")):
                add(f"house/night/{level}", "Weather, day and night/Night", f"The house at {words}",
                    [computed(f"night/{level}", whole, lambda f, d=level: night_image(f, d))], True,
                    f"Darkness {level} (CNight::GetDarknessLevel): dark blue at alpha {night_alpha(level)} over the "
                    "screen, with the lamps of Assets\\lsmap.dat putting back the unlit picture through their light "
                    "masks (CNight::Draw).", night_check)

    # ---- the intro story's hill and house (CIntroPage2 / CIntroPage3 through CStory)
    story_check = CHECKED.format(code="CStory::AddImage, CStory::SetAlpha and CStory::Draw")
    if files.has("Hill.jpg"):
        add("house/story/hill", "Screens and backgrounds/Intro story", "Intro story: the hill (page 2, faded in)",
            [gp.Draw("Hill.jpg", (0, 0, *files.size("Hill.jpg")), 0, 0)], True,
            "CIntroPage2::Enter adds Hill.jpg to the story at (the wide-screen offset, 0) at alpha 0, and its "
            "FadeImage fades it in to 1; CStory::Draw draws it whole over the black screen (the page's text, drawn "
            "over it, is left out).", story_check)
    if files.has("Hill.jpg") and files.has("House.jpg"):
        add("house/story/house", "Screens and backgrounds/Intro story",
            "Intro story: the house on the hill (page 3, faded in)",
            [gp.Draw("Hill.jpg", (0, 0, *files.size("Hill.jpg")), 0, 0),
             gp.Draw("House.jpg", (0, 0, *files.size("House.jpg")), 0, 0)], True,
            "CIntroPage3::Enter adds Hill.jpg, then House.jpg at alpha 0 over it, and its FadeImage fades the house "
            "in to 1; CStory::Draw draws both whole, so once faded in the house picture covers the hill (the page's "
            "text is left out).", story_check)

    # ---- never drawn
    for k, name in ((1, "leaf1.png"), (2, "leaf2.png"), (3, "leaf3.png")):
        if files.has(name):
            add(f"house/weather/leaf{k}", "Weather, day and night/Unused", f"Wind leaf {k}", [gp.whole(name)], False,
                USAGE[589 + k][1], "")
    if files.has("hailstone.png"):
        add("house/weather/hailstone", "Weather, day and night/Unused", "Hailstone", [gp.whole("hailstone.png")],
            False, USAGE[589][1], "")
    return out


_DECAL = "drawn over the house by CDecal::DrawDecals"
USAGE = {
    461: (True, f"The sock pile, {_DECAL} (6 sizes by how many socks)."),
    528: (True, f"The dining room before its renovation, {_DECAL}."),
    529: (True, f"The east bedroom before its renovation, {_DECAL}."),
    530: (True, f"The living room before its renovation, {_DECAL}."),
    531: (True, f"The master bedroom before its renovation, {_DECAL}."),
    532: (True, f"The west bedroom before its renovation, {_DECAL}."),
    533: (True, f"The kids' room before it is built, {_DECAL}."),
    534: (True, f"The laundry room before it is built, {_DECAL}."),
    535: (True, f"The front porch before it is built, {_DECAL}."),
    536: (True, f"The back porch before it is built, {_DECAL}."),
    537: (True, f"The second bathroom before it is built, {_DECAL}."),
    538: (True, f"The second bathroom's shower curtain, {_DECAL}."),
    539: (True, f"The shower curtain, {_DECAL}."),
    540: (True, f"The second bathroom's door, closed, {_DECAL}."),
    541: (True, f"The bathroom door, closed, {_DECAL}."),
    574: (True, f"The full kitchen bin, {_DECAL}."),
    575: (True, f"The leaks' puddles, {_DECAL}."),
    370: (True, "The intro story's hill: CIntroPage2::Enter and CIntroPage3::Enter add it to the story, CStory::Draw "
                "draws it."),
    371: (True, "The intro story's house: CIntroPage3::Enter adds it over the hill, CStory::Draw draws it."),
    586: (True, "Cloudy weather's sunbeams, drawn by CSunBeam::Draw."),
    588: (True, "Snow's flakes, drawn by CSnow::Draw in 4 layers (whole, 83%, 66%, 50%)."),
    587: (True, "The fog's patches, drawn by CFog::Draw."),
    589: (False, "Never seen: hailstones are only set up by CHail::Reset and CHail::Update, and no code calls either. "
                 "CHail::DrawIce and CHail::Draw(int) do run every frame, but they only meet the ice as the program "
                 "starts it (zeroed): on the first frame its 256 pieces are drawn at alpha 0, which the blitter "
                 "draws as nothing, and marked melted, and nothing is drawn again."),
    590: (False, "Never drawn: CWind::LoadAssets loads it, but no code calls CWind::Draw (or CWind::Update)."),
    591: (False, "Never drawn: CWind::LoadAssets loads it, but no code calls CWind::Draw (or CWind::Update)."),
    592: (False, "Never drawn: CWind::LoadAssets loads it, but no code calls CWind::Draw (or CWind::Update)."),
    598: (False, "The light mask of a Light100 lamp (CNight::SetupLightSource); no such lamp is ever made: "
                 "Assets\\lsmap.dat has Light250, Light350, Light400 and Light500 lamps, and the only other code "
                 "that adds a lamp, CLightSourceEditor::HandleKeyCharacter, never runs: the editor's one object is only "
                 "ever named by its own start-up code, which builds it and hands it to no one."),
    599: (False, "The light mask of a Light150 lamp (CNight::SetupLightSource); no such lamp is ever made (see "
                 "LightSourceMask100)."),
    602: (True, "The light mask of Assets\\lsmap.dat's Light250 lamps at night (CNight::SetupLightSource, PreDraw)."),
    604: (True, "The light mask of Assets\\lsmap.dat's Light350 lamps at night (CNight::SetupLightSource, PreDraw)."),
    605: (True, "The light mask of Assets\\lsmap.dat's Light400 lamps at night (CNight::SetupLightSource, PreDraw)."),
    606: (False, "The light mask of a Light450 lamp (CNight::SetupLightSource); no such lamp is ever made (see "
                 "LightSourceMask100)."),
    607: (True, "The light mask of Assets\\lsmap.dat's Light500 lamps at night (CNight::SetupLightSource, PreDraw)."),
    600: (False, "The light mask of a Torch (CNight::SetupLightSource, 8 frames); no torch is ever made (see "
                 "LightSourceMask100). The file is missing from the game: asked for, the game would log \"Missing "
                 "Graphic\" and use a clear 100 x 100 picture, so the lamp would give no light."),
    601: (False, "The light mask of a Light200 lamp (CNight::SetupLightSource); no such lamp is ever made (see "
                 "LightSourceMask100). The file is missing from the game (see LightSourceMask180x8)."),
    603: (False, "The light mask of a Fire (10 frames) and of a Light300 lamp (CNight::SetupLightSource); no such "
                 "lamp is ever made (see LightSourceMask100). The file is missing from the game (see "
                 "LightSourceMask180x8)."),
}

CELL_LABELS = {
    **{(575, k): v for k, v in ((0, "Puddle (bathroom sinks)"),
                                (1, "Puddle (toilets, showers, kitchen and north sinks)"))},
    **{(461, k): f"Sock pile, {v}" for k, v in enumerate(("1 to 4 socks", "5 to 9 socks", "10 to 14 socks",
                                                          "15 to 24 socks", "25 to 29 socks", "30 socks or more"))},
    (586, 0): "Sunbeam",
    (282, 0): "Open, nearly empty", (282, 1): "Open, some food", (282, 2): "Open, full",
    (282, 3): "Super fridge open, nearly empty", (282, 4): "Super fridge open, some food",
    (282, 5): "Super fridge open, full",
    (275, 0): "North-west counter", (275, 1): "North-east counter",
    (277, 0): "Workshop bench 3 (the code asks for a third cell, which GetCellRect clamps to this one)",
    (277, 1): "Workshop bench 2",
    (278, 0): "Workshop bench 4 (the code asks for a third cell, which GetCellRect clamps to this one)",
    (278, 1): "Workshop bench 1",
    **{(i, 0): "Light mask" for i in (598, 599, 602, 604, 605, 606, 607)},
}
CELL_UNUSED = {}
