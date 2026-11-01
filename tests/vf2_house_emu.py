"""Run the game's own house, yard, weather and night drawing code from the B200 desktop objects (unicorn), for the
Picture Maker's house pictures (src/vf2_art_house.py; tests/test_art_house.py).

* CWorldMap::LoadAssets (the 16 tiles' names and places) and CWorldMap::Draw (which tiles it draws where for a view)
  run whole; ldwGameWindowImpl::ClipRect cuts each draw to the screen's clipping rectangle.
* CDecal::LoadAssets, RefreshDecals (which ends in RefreshProps) and DrawDecals run whole: the house's fixed overlays
  (damage, foundations, doors, curtains, puddles, upgrades, things left lying around...). Their inputs are seams or
  zeroed data the rig fills: CInventoryManager::HaveUpgrade, CEnvironment::GetPropState / GetPropPosition, the
  props' "on" bytes in CEnvironment (+7Ch + 10h x prop), theGameState (+2Ch the full bin, +148h the sock pile) and
  CFoodStore (+78h the food).
* CWeather::Draw, CSunBeam::Draw, CFog::Draw, CLightning::Draw run whole; their draws and fills are recorded.
* CNight::LoadAssets (Assets\\lsmap.dat through fopen / fread seams over the real file) and CNight::Draw (with its
  PreDraw) run whole; the screen copies, transparency masks, the darkness fill and the draws back are recorded.
* The pixels: ldwGameWindowImpl::FillRect (the haze, the lightning, the night's darkness) and
  ldwImageImpl::SetTransparencyMask (a lamp's light mask) run whole on real pixels; SDL's own calls (SDL_MapRGB,
  SDL_MapRGBA, SDL_LockSurface) are seams.

Nothing here starts the game or writes a file.
"""
from __future__ import annotations

import struct
from pathlib import Path

from unicorn.x86_const import UC_X86_REG_EAX

import vf2_people_emu as pe


def _f(v: int) -> float:
    return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]


def f32(v: float) -> float:
    return struct.unpack("<f", struct.pack("<f", v))[0]


def _sprintf(em):
    out, fmt = em.arg(0), em.cstr(em.arg(1))
    args = [em.arg(2 + k) for k in range(6)]
    text, k, i = "", 0, 0
    while i < len(fmt):
        if fmt[i] == "%":
            j = i + 1
            while fmt[j] in "0123456789-.":
                j += 1
            code = fmt[j]
            value = args[k]
            if code == "s":
                text += em.cstr(value)
            else:
                width = fmt[i + 1:j]
                text += ("%" + width + "d") % (value - (1 << 32) if value >> 31 else value)
            k += 1
            i = j + 1
        else:
            text += fmt[i]
            i += 1
    em.write(out, text.encode("latin-1") + b"\0")
    return len(text), 0


def patch_float_return(e: pe.Emu, name: str) -> int:
    """Make the game's own function `name` (a thiscall with no arguments that returns a float on the x87 stack)
    return the float in the cell this returns: its first bytes become `fld dword ptr [cell]; ret`, once (the code
    is patched before it ever runs; later answers are written to the cell, as data)."""
    cell = e.alloc(4)
    e.write(e.globals[name], b"\xD9\x05" + struct.pack("<I", cell) + b"\xC3")
    return cell


# ====================================================================== the map
class MapRig:
    OBJECTS = ["WorldMap"]

    def __init__(self, obj_dir: Path):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.names: dict[int, str] = {}
        self.draws: list = []
        e.seam("??2@YAPAXI@Z", lambda em: (em.alloc(max(4, em.arg(0))), 0))
        e.seam("_sprintf", _sprintf)
        e.seam("??0ldwImage@@QAE@PBD@Z", self._image)
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?Draw@ldwGameWindow@@QAEXPAVldwImage@@HH@Z", self._draw)
        e.seam("@__security_check_cookie@4", lambda em: (em.uc.reg_read(UC_X86_REG_EAX), 0))
        self.map = e.addr("?WorldMap@@3VCWorldMap@@A")
        e.call("??0CWorldMap@@QAE@XZ", ecx=self.map)
        e.call("?LoadAssets@CWorldMap@@QAEXXZ", ecx=self.map)

    def _image(self, em):
        self.names[em.ecx] = em.cstr(em.arg(0))
        return em.ecx, 4

    def _draw(self, em):
        self.draws.append((self.names[em.arg(0)], em.sarg(1), em.sarg(2)))
        return 0, 12

    def tiles(self) -> list:
        """The tiles LoadAssets made, in its order: (file, x, y)."""
        e = self.e
        return [(self.names[e.r32(self.map + 12 * k)], e.s32(self.map + 12 * k + 4), e.s32(self.map + 12 * k + 8))
                for k in range(16)]

    def draw(self, origin=(0, 0), rect=(0, 0, 2048, 2048)) -> list:
        """CWorldMap::Draw(origin, rect): the tiles drawn and where on the screen."""
        self.draws = []
        self.e.call("?Draw@CWorldMap@@QBEXUldwPoint@@UldwRect@@@Z", [origin[0], origin[1], *rect], ecx=self.map)
        return list(self.draws)


class ClipRig:
    """ldwGameWindowImpl::ClipRect, as every ldwGameWindow::Draw cuts a draw to the clipping rectangle."""
    OBJECTS = ["ldwGameWindow"]

    def __init__(self, obj_dir: Path):
        self.e = pe.Emu(obj_dir, self.OBJECTS)
        self.impl = self.e.alloc(0x80)

    def clip(self, rect: tuple, x: int, y: int, clip: tuple):
        """None when nothing is drawn, else (source rect, x, y) after clipping."""
        e = self.e
        for k, v in enumerate(clip):
            e.w32(self.impl + 0x60 + 4 * k, v)
        src, px, py = e.alloc(16), e.alloc(4), e.alloc(4)
        for k, v in enumerate(rect):
            e.w32(src + 4 * k, v)
        e.w32(px, x)
        e.w32(py, y)
        ok = e.call("?ClipRect@ldwGameWindowImpl@@AAE_NAAUldwRect@@AAH1@Z", [src, px, py], ecx=self.impl) & 0xFF
        if not ok:
            return None
        return tuple(e.s32(src + 4 * k) for k in range(4)), e.s32(px), e.s32(py)


# ====================================================================== the decals
class DecalRig:
    OBJECTS = ["Decal"]

    def __init__(self, obj_dir: Path):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.grids: dict[int, int] = {}
        self.ids: dict[int, int] = {}
        self.upgrades: set = set()
        self.prop_states: set = set()
        self.positions: dict = {}
        self.asked_upgrades: set = set()
        self.asked_states: set = set()
        self.asked_positions: set = set()
        self.achievements: list = []
        self.draws: list = []
        self.gs = e.alloc(0x30000)
        e.seam("?Get@theGameState@@SAPAV1@XZ", lambda em: (self.gs, 0))
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (0x7000, 0))
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z", self._grid)
        e.seam("?HaveUpgrade@CInventoryManager@@QAE_NW4EInventoryItem@@@Z", self._upgrade)
        e.seam("?GetPropState@CEnvironment@@QAE_NW4EPropEnum@@@Z", self._state)
        e.seam("?GetPropPosition@CEnvironment@@QAE?AUldwPoint@@W4EPropEnum@@@Z", self._position)
        e.seam("?SetComplete@CAchievement@@QAEXW4EAchievement@@@Z",
               lambda em: (self.achievements.append(em.arg(0)), (0, 4))[1])
        e.seam("?Draw@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHM@Z", self._draw)
        self.decal = e.addr("?Decal@@3VCDecal@@A")
        self.env = e.addr("?Environment@@3VCEnvironment@@A")
        self.food = e.addr("?FoodStore@@3VCFoodStore@@A")
        self.view = e.addr("?WorldView@@3VCWorldView@@A")
        e.call("??0CDecal@@QAE@XZ", ecx=self.decal)
        e.call("?LoadAssets@CDecal@@QAEXXZ", ecx=self.decal)

    def _grid(self, em):
        image = em.arg(0)
        if image not in self.grids:
            self.grids[image] = em.alloc(0x40)
            self.ids[self.grids[image]] = image
        return self.grids[image], 4

    def _upgrade(self, em):
        self.asked_upgrades.add(em.arg(0))
        return (1 if em.arg(0) in self.upgrades else 0), 4

    def _state(self, em):
        self.asked_states.add(em.arg(0))
        return (1 if em.arg(0) in self.prop_states else 0), 4

    def _position(self, em):
        out, prop = em.arg(0), em.arg(1)
        self.asked_positions.add(prop)
        x, y = self.positions.get(prop, (0, 0))
        em.w32(out, x)
        em.w32(out + 4, y)
        return out, 8

    def _draw(self, em):
        self.draws.append((self.ids[em.arg(0)], em.sarg(1), em.sarg(2), em.sarg(3), round(em.farg(4), 6)))
        return 0, 20

    def run(self, upgrades=(), states=(), props=(), food=0, gs=None, positions=None, view=(0, 0)) -> list:
        """CDecal::Reset (InitDecals, RefreshDecals -> RefreshProps) and DrawDecals over the given state:
        the draws (image id, x, y, cell, alpha) in the game's order."""
        e = self.e
        self.upgrades, self.prop_states = set(upgrades), set(states)
        self.positions = dict(positions or {})
        self.achievements = []
        e.write(self.env, bytes(0x1000))
        for p in props:
            e.write(self.env + 0x7C + 0x10 * p, b"\x01")
        e.write(self.gs, bytes(0x30000))
        for off, v in (gs or {}).items():
            e.w32(self.gs + off, v)
        e.w32(self.food + 0x78, food)
        e.w32(self.view, view[0])
        e.w32(self.view + 4, view[1])
        e.call("?Reset@CDecal@@QAEXXZ", ecx=self.decal)
        self.draws = []
        e.call("?DrawDecals@CDecal@@QAEXXZ", ecx=self.decal)
        return list(self.draws)


# ====================================================================== the weather
class WeatherRig:
    """CWeather::Draw: the daytime haze fill, then the weather's own draw, and the night at night."""
    OBJECTS = ["Weather"]
    SUBS = {"?Draw@CSunBeam@@QAEXXZ": "sunbeam", "?Draw@CLightning@@QAEXXZ": "lightning",
            "?Draw@CRain@@QAEXXZ": "rain", "?Draw@CFog@@QAEXXZ": "fog", "?Draw@CSnow@@QAEXXZ": "snow",
            "?Draw@CNight@@QAEXXZ": "night"}

    def __init__(self, obj_dir: Path):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.calls: list = []
        self.day = True
        for name, word in self.SUBS.items():
            e.seam(name, lambda em, w=word: (self.calls.append((w,)), (0, 0))[1])
        e.seam("?IsDayTime@CNight@@QAE_NXZ", lambda em: (1 if self.day else 0, 0))
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?FillRect@ldwGameWindow@@QAEXAAUldwRect@@MMMM@Z", self._fill)
        e.seam("?Reset@CWorldView@@QAEX_N@Z", lambda em: (0, 4))
        self.weather = e.addr("?Weather@@3VCWeather@@A")
        self.view = e.addr("?WorldView@@3VCWorldView@@A")
        self.rect = e.addr("?scm_sRect@CWorldView@@0UldwRect@@A")

    def _fill(self, em):
        r = em.arg(0)
        self.calls.append(("fill", tuple(em.s32(r + 4 * k) for k in range(4)),
                           tuple(round(_f(em.arg(k)), 7) for k in range(1, 5))))
        return 0, 20

    def target_haze(self, kind: int) -> float:
        """CWeather::SetCurrent(kind, 0): the haze the weather moves to (CWeather +18h). The weathers' own Reset /
        Stop, the pets' HandleRain, GetRandom and the game clock are seams."""
        e = self.e
        for name in ("?Stop@CRain@@QAEXXZ", "?Stop@CFog@@QAEXXZ", "?Stop@CSnow@@QAEXXZ", "?Reset@CSunBeam@@QAEXXZ",
                     "?Reset@CFog@@QAEXXZ", "?Reset@CSnow@@QAEXXZ", "?HandleRain@CPetManager@@QAEXXZ"):
            e.seam(name, lambda em: (0, 0))
        for name in ("?Reset@CLightning@@QAEX_N@Z", "?Reset@CRain@@QAEX_N@Z"):
            e.seam(name, lambda em: (0, 4))
        e.seam("?GetRandom@ldwGameState@@SAHH@Z", lambda em: (0, 0))
        e.seam("?Seconds@CGameTime@@QAE?BIXZ", lambda em: (1000, 0))
        e.write(self.weather, bytes(0x40))
        e.call("?SetCurrent@CWeather@@QAEXW4EWeather@@H@Z", [kind, 0], ecx=self.weather)
        return e.rf(self.weather + 0x18)

    def draw(self, kind: int, haze: float, day: bool = True, screen=(0, 0, 2048, 2048)) -> list:
        e = self.e
        self.day = day
        self.calls = []
        e.w32(self.weather, kind)
        e.wf(self.weather + 0x1C, haze)
        e.write(self.view + 0x14, b"\x01")
        for k, v in enumerate(screen):
            e.w32(self.rect + 4 * k, v)
        e.call("?Draw@CWeather@@QAEXXZ", ecx=self.weather)
        return list(self.calls)


class SkyRig:
    """CSunBeam::Draw, CFog::Draw and CLightning::Draw."""
    OBJECTS = ["SunBeam", "Fog", "Lightning"]

    def __init__(self, obj_dir: Path):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.calls: list = []
        self.images: dict[int, int] = {}
        self.ids: dict[int, int] = {}
        e.seam("?IsDayTime@CNight@@QAE_NXZ", lambda em: (1, 0))
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (0x7000, 0))
        e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z", self._image)
        e.seam("?GetImage@theGraphicsManager@@QAEPAVldwImage@@W4EImage@@@Z", self._image)
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?Draw@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHM@Z", lambda em: (self.calls.append(
            ("grid", self.ids[em.arg(0)], em.sarg(1), em.sarg(2), em.sarg(3), round(em.farg(4), 6))), (0, 20))[1])
        e.seam("?Draw@ldwGameWindow@@QAEXPAVldwImage@@HHM@Z", lambda em: (self.calls.append(
            ("image", self.ids[em.arg(0)], em.sarg(1), em.sarg(2), round(em.farg(3), 6))), (0, 16))[1])
        e.seam("?FillRect@ldwGameWindow@@QAEXAAUldwRect@@UldwColor@@@Z", self._fill)
        e.seam("?Reset@CWorldView@@QAEX_N@Z", lambda em: (0, 4))
        self.view = e.addr("?WorldView@@3VCWorldView@@A")
        self.rect = e.addr("?scm_sRect@CWorldView@@0UldwRect@@A")
        self.weather = e.addr("?Weather@@3VCWeather@@A")
        self.sunbeam = e.addr("?SunBeam@@3VCSunBeam@@A")
        self.fog = e.addr("?Fog@@3VCFog@@A")
        self.lightning = e.addr("?Lightning@@3VCLightning@@A")
        e.call("?LoadAssets@CSunBeam@@QAEXXZ", ecx=self.sunbeam)
        e.call("?LoadAssets@CFog@@QAEXXZ", ecx=self.fog)

    def _image(self, em):
        image = em.arg(0)
        at = em.alloc(0x20)
        self.ids[at] = image
        return at, 4

    def _fill(self, em):
        r = em.arg(0)
        self.calls.append(("fill", tuple(em.s32(r + 4 * k) for k in range(4)), em.arg(1)))
        return 0, 8

    def _screen(self, screen, view=(0, 0), intensity=1.0):
        e = self.e
        e.write(self.view + 0x14, b"\x01")
        e.w32(self.view, view[0])
        e.w32(self.view + 4, view[1])
        for k, v in enumerate(screen):
            e.w32(self.rect + 4 * k, v)
        e.wf(self.weather + 0x28, intensity)
        self.calls = []

    def sunbeams(self, beams, intensity=1.0, view=(0, 0), screen=(0, 0, 1024, 730)) -> list:
        """CSunBeam::Draw with its 64 beams set to `beams` [(x, y, fade)] (the rest at fade 0, far below)."""
        e = self.e
        self._screen(screen, view, intensity)
        for k in range(64):
            x, y, fade = beams[k] if k < len(beams) else (0, 5000, 0.0)
            at = self.sunbeam + 0x14 * k
            e.w32(at, x)
            e.w32(at + 4, y)
            e.wf(at + 8, fade)
        e.call("?Draw@CSunBeam@@QAEXXZ", ecx=self.sunbeam)
        return list(self.calls)

    def fog_draw(self, patches, intensity=1.0, view=(0, 0), screen=(0, 0, 1024, 730)) -> list:
        """CFog::Draw with its 4 x 64 patches set to `patches` {(layer, k): (x, y, fade)} (the rest at fade 0)."""
        e = self.e
        self._screen(screen, view, intensity)
        e.w32(self.fog + 0x1404, view[0])
        e.w32(self.fog + 0x1408, view[1])
        for layer in range(4):
            for k in range(64):
                x, y, fade = patches.get((layer, k), (0.0, 5000.0, 0.0))
                at = self.fog + 0x14 * (64 * layer + k)
                e.wf(at, x)
                e.wf(at + 4, y)
                e.wf(at + 8, fade)
        e.call("?Draw@CFog@@QAEXXZ", ecx=self.fog)
        return list(self.calls)

    def flash(self, on=True, screen=(0, 0, 1024, 730)) -> list:
        e = self.e
        self._screen(screen)
        e.write(self.lightning, b"\x01" if on else b"\x00")
        e.call("?Draw@CLightning@@QAEXXZ", ecx=self.lightning)
        return list(self.calls)


class HailRig:
    """CHail as the program starts it (its constructor only), then CHail::DrawIce and CHail::Draw(int) as
    CSceneManager::EndScene calls them every frame."""
    OBJECTS = ["Hail"]

    def __init__(self, obj_dir: Path):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.calls: list = []
        e.seam("?AddElement@CSceneManager@@QAEXW4ESceneElement@@HW4EScenePriority@@H@Z",
               lambda em: (self.calls.append(("element", em.arg(0), em.arg(1))), (0, 16))[1])
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?DrawScaled@ldwGameWindow@@QAEXPAVldwImage@@HHMH_N@Z", lambda em: (self.calls.append(
            ("scaled", em.sarg(1), em.sarg(2), round(em.farg(3), 6), em.sarg(4))), (0, 24))[1])
        e.seam("?GetRandom@ldwGameState@@SAHH@Z", lambda em: (0, 0))
        self.hail = e.addr("?Hail@@3VCHail@@A")
        e.call("??0CHail@@QAE@XZ", ecx=self.hail)

    def frame(self) -> list:
        """One frame: DrawIce, then Draw(index) for every element it added."""
        self.calls = []
        self.e.call("?DrawIce@CHail@@QAEXXZ", ecx=self.hail)
        elements = [c for c in self.calls if c[0] == "element"]
        for _kind, _element, index in elements:
            self.e.call("?Draw@CHail@@QAEXH@Z", [index], ecx=self.hail)
        return list(self.calls)


class SnowRig:
    """CSnow::Draw (the falling flakes) with its flakes set by the rig."""
    OBJECTS = ["Snow"]

    def __init__(self, obj_dir: Path, width: int = 1024):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.calls: list = []
        self.random: list = []
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (0x7000, 0))
        e.seam("?GetImage@theGraphicsManager@@QAEPAVldwImage@@W4EImage@@@Z", lambda em: (0x588000 + em.arg(0), 4))
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?GetWidth@ldwGameWindow@@QAEHXZ", lambda em: (width, 0))
        e.seam("?DrawScaled@ldwGameWindow@@QAEXPAVldwImage@@HHMH_N@Z", lambda em: (self.calls.append(
            ("scaled", em.arg(0) - 0x588000, em.sarg(1), em.sarg(2), round(em.farg(3), 6), em.sarg(4),
             em.arg(5) & 0xFF)), (0, 24))[1])
        e.seam("?GetRandom@ldwGameState@@SAHH@Z", lambda em: (self.random.pop(0) if self.random else 0, 0))
        e.seam("?Reset@CWorldView@@QAEX_N@Z", lambda em: (0, 4))
        self.snow = e.addr("?Snow@@3VCSnow@@A")
        self.view = e.addr("?WorldView@@3VCWorldView@@A")
        self.rect = e.addr("?scm_sRect@CWorldView@@0UldwRect@@A")
        self.weather = e.addr("?Weather@@3VCWeather@@A")
        e.call("??0CSnow@@QAE@XZ", ecx=self.snow)
        e.call("?LoadAssets@CSnow@@QAEXXZ", ecx=self.snow)

    def draw(self, flakes, intensity=1.0, screen=(0, 0, 1024, 730)) -> list:
        """CSnow::Draw with flake k of layer i at flakes[i][k] = (x, y) (floats; the rest far off)."""
        e = self.e
        e.write(self.view + 0x14, b"\x01")
        e.w32(self.view, 0)
        e.w32(self.view + 4, 0)
        for k, v in enumerate(screen):
            e.w32(self.rect + 4 * k, v)
        e.wf(self.weather + 0x28, intensity)
        e.w32(self.snow + 0x1E08, 0)
        e.w32(self.snow + 0x1E0C, 0)
        for layer in range(4):
            for k in range(32):
                x, y = flakes[layer][k] if k < len(flakes[layer]) else (-5000.0, -5000.0)
                at = self.snow + 0x280 * layer + 0x14 * k
                e.wf(at, x)
                e.wf(at + 4, y)
        self.calls = []
        e.call("?Draw@CSnow@@QAEXXZ", ecx=self.snow)
        return list(self.calls)


class RainRig:
    """CRain::Draw (the drops' lines) with its drops set by the rig, and CRain::Update's splashes (where
    CWorldView::RandomPoint lands, CContentMap::GetMaterial answering through `material(x, y)`)."""
    OBJECTS = ["Rain"]

    def __init__(self, obj_dir: Path, material=None):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.calls: list = []
        self.points: list = []
        self.material = material or (lambda x, y: 0)
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?DrawLine@ldwGameWindow@@QAEXHHHHUldwColor@@MM@Z", lambda em: (self.calls.append(
            ("line", em.sarg(0), em.sarg(1), em.sarg(2), em.sarg(3), em.arg(4), em.farg(5), em.farg(6))),
            (0, 28))[1])
        e.seam("?GetRandom@ldwGameState@@SAHH@Z", lambda em: (0, 0))
        e.seam("?Reset@CWorldView@@QAEX_N@Z", lambda em: (0, 4))
        e.seam("?GetNumberOfType@CFloatingAnim@@QBE?BHW4EFloatingAnim@@@Z", lambda em: (0, 4))
        e.seam("?RandomPoint@CWorldView@@QBE?BUldwPoint@@XZ", self._point)
        e.seam("?GetMaterial@CContentMap@@QAE?BW4EMaterial@1@UldwPoint@@@Z",
               lambda em: (self.material(em.sarg(0), em.sarg(1)), 8))
        e.seam("?AddAnim@CFloatingAnim@@QAE?BHW4EFloatingAnim@@UldwPoint@@H_NW4EFloatingAnimEffect@@"
               "W4EScenePriority@@2@Z", lambda em: (self.calls.append(
                   ("anim", em.sarg(0), em.sarg(1), em.sarg(2), em.sarg(3), em.arg(4) & 0xFF, em.sarg(5), em.sarg(6),
                    em.arg(7) & 0xFF)), (0, 32))[1])
        e.seam("?SetVolume@CSound@@QAEXW4ESound@@M@Z", lambda em: (0, 8))
        self.rain = e.addr("?Rain@@3VCRain@@A")
        self.view = e.addr("?WorldView@@3VCWorldView@@A")
        self.rect = e.addr("?scm_sRect@CWorldView@@0UldwRect@@A")
        self.weather = e.addr("?Weather@@3VCWeather@@A")
        e.call("??0CRain@@QAE@XZ", ecx=self.rain)

    def _point(self, em):
        out = em.arg(0)
        x, y = self.points.pop(0) if self.points else (0, 0)
        em.w32(out, x)
        em.w32(out + 4, y)
        return out, 4

    def _screen(self, screen, intensity):
        e = self.e
        e.write(self.view + 0x14, b"\x01")
        e.w32(self.view, 0)
        e.w32(self.view + 4, 0)
        for k, v in enumerate(screen):
            e.w32(self.rect + 4 * k, v)
        e.wf(self.weather + 0x28, intensity)

    def draw(self, drops, intensity=1.0, screen=(0, 0, 1024, 730)) -> list:
        """CRain::Draw with drop k = drops[k] = (x, y, x_before, y_before, dx, speed) (the rest off the screen)."""
        e = self.e
        self._screen(screen, intensity)
        e.w32(self.rain + 0x3000, 0)
        e.w32(self.rain + 0x3004, 0)
        for k in range(512):
            values = drops[k] if k < len(drops) else (-5000, -5000, -5000, -5000, 0, 0)
            for j, v in enumerate(values):
                e.w32(self.rain + 0x18 * k + 4 * j, v)
        self.calls = []
        e.call("?Draw@CRain@@QAEXXZ", ecx=self.rain)
        return [c for c in self.calls if c[0] == "line"]

    def splash(self, point, intensity=1.0, screen=(0, 0, 1024, 730)) -> list:
        """CRain::Update once, CWorldView::RandomPoint giving `point`: the effect it adds there, if any."""
        self._screen(screen, intensity)
        self.points = [point]
        self.calls = []
        self.e.call("?Update@CRain@@QAEXXZ", ecx=self.rain)
        return [c for c in self.calls if c[0] == "anim"]


class ContentRig:
    """CContentMap::Load (Assets\\cmap.dat through fopen / fread seams over the real file) and GetMaterial."""
    OBJECTS = ["ContentMap"]

    def __init__(self, obj_dir: Path, game: Path):
        self.game = Path(game)
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.files: dict = {}
        state = e.alloc(0x20)
        vtable = e.alloc(0x40)
        e.w32(state, vtable)
        e.seam("gs_full_path", lambda em: (em.string(str(self.game / "Assets" / em.cstr(em.arg(0)))), 4))
        e.w32(vtable + 8, e.thunk_of["gs_full_path"])
        e.seam("?Get@ldwGameState@@SAPAV1@XZ", lambda em: (state, 0))
        e.seam("_fopen", self._fopen)
        e.seam("_fread", self._fread)
        e.seam("_fclose", lambda em: (self.files.pop(em.arg(0)).close(), (0, 0))[1])
        self.map = e.addr("?ContentMap@@3VCContentMap@@A")
        e.call("?Load@CContentMap@@QAEXXZ", ecx=self.map)

    def _fopen(self, em):
        path = Path(em.cstr(em.arg(0)))
        handle = em.alloc(4)
        self.files[handle] = open(path, "rb")
        return handle, 0

    def _fread(self, em):
        buf, size, count, handle = em.arg(0), em.arg(1), em.arg(2), em.arg(3)
        data = self.files[handle].read(size * count)
        em.write(buf, data)
        return len(data) // size if size else 0, 0

    def material(self, x: int, y: int) -> int:
        return self.e.call("?GetMaterial@CContentMap@@QAE?BW4EMaterial@1@UldwPoint@@@Z", [x, y], ecx=self.map)


class StoryRig:
    """CStory::AddImage / SetAlpha and CStory::Draw (an intro page's pictures); the picture draws are recorded and
    the page's text is not drawn (CStory's text list is left empty)."""
    OBJECTS = ["Story"]

    def __init__(self, obj_dir: Path, sizes):
        """`sizes(image_id) -> (w, h)` answers ldwImage::GetWidth / GetHeight."""
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.calls: list = []
        self.ids: dict = {}
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (0x7000, 0))
        e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z", self._grid)
        e.seam("?GetImage@theGraphicsManager@@QAEPAVldwImage@@W4EImage@@@Z", self._grid)
        e.seam("?GetWidth@ldwImage@@QAEHXZ", lambda em: (sizes(self.ids[em.ecx])[0], 0))
        e.seam("?GetHeight@ldwImage@@QAEHXZ", lambda em: (sizes(self.ids[em.ecx])[1], 0))
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?GetWidth@ldwGameWindow@@QAEHXZ", lambda em: (1024, 0))
        e.seam("?GetHeight@ldwGameWindow@@QAEHXZ", lambda em: (768, 0))
        e.seam("?FillRect@ldwGameWindow@@QAEXAAUldwRect@@UldwColor@@@Z", lambda em: (self.calls.append(
            ("fill", tuple(em.s32(em.arg(0) + 4 * k) for k in range(4)), em.arg(1))), (0, 8))[1])
        e.seam("?DrawScaled@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHMH_N@Z", lambda em: (self.calls.append(
            ("scaled", self.ids.get(em.arg(0)), em.sarg(1), em.sarg(2), em.sarg(3), round(em.farg(4), 6),
             em.sarg(5), em.arg(6) & 0xFF)), (0, 28))[1])
        e.seam("?Get@theStringManager@@SAPAV1@XZ", lambda em: (0x7100, 0))
        self.story = e.addr("?Story@@3VCStory@@A")

    def _grid(self, em):
        at = em.alloc(0x40)
        self.ids[at] = em.arg(0)
        return at, 4

    def page(self, images) -> list:
        """A page with `images` [(image id, x, y, alpha)] added in order (AddImage, SetAlpha), then CStory::Draw."""
        e = self.e
        e.write(self.story, bytes(0x600))
        for image, x, y, alpha in images:
            index = e.call("?AddImage@CStory@@QAE?BHW4EImage@@HHH@Z", [image, x, y, 0], ecx=self.story)
            e.call("?SetAlpha@CStory@@QAEXHM@Z", [index, f32(alpha)], ecx=self.story)
        self.calls = []
        e.call("?Draw@CStory@@QAEXXZ", ecx=self.story)
        return list(self.calls)


class ScaledDrawRig:
    """ldwGameWindow::DrawScaled(image, x, y, alpha, percent, centred) as far as BlitRectWithAlpha: the source
    rectangle, the place, the alpha and the scale it hands the blitter (ScaledClipRect run whole)."""
    OBJECTS = ["ldwGameWindow"]

    def __init__(self, obj_dir: Path, screen=(0, 0, 1024, 730)):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.calls: list = []
        self.size = (0, 0)
        e.seam("?GetWidth@ldwImage@@QAEHXZ", lambda em: (self.size[0], 0))
        e.seam("?GetHeight@ldwImage@@QAEHXZ", lambda em: (self.size[1], 0))
        e.seam("?GetGraphic@ldwImageImpl@@QAEPAUSDL_Surface@@XZ", lambda em: (0x1234, 0))
        e.seam("?BlitRectWithAlpha@ldwGameWindowImpl@@AAEXPAUSDL_Surface@@HHHHHHMM_N@Z", lambda em: (
            self.calls.append(("blit", em.sarg(1), em.sarg(2), tuple(em.sarg(k) for k in range(3, 7)),
                               round(em.farg(7), 6), round(em.farg(8), 6), em.arg(9) & 0xFF)), (0, 0x28))[1])
        self.impl = e.alloc(0x80)
        for k, v in enumerate(screen):
            e.w32(self.impl + 0x60 + 4 * k, v)
        self.window = e.alloc(0x10)
        e.w32(self.window, self.impl)
        self.image = e.alloc(0x10)

    def draw(self, size, x, y, alpha, percent, centred=True) -> list:
        self.size = size
        self.calls = []
        self.e.call("?DrawScaled@ldwGameWindow@@QAEXPAVldwImage@@HHMH_N@Z",
                    [self.image, x, y, f32(alpha), percent, 1 if centred else 0], ecx=self.window)
        return list(self.calls)


# ====================================================================== the night
class NightRig:
    """CNight::LoadAssets and CNight::Draw (PreDraw, the darkness fill, the lamps' copies drawn back)."""
    OBJECTS = ["Night"]

    def __init__(self, obj_dir: Path, game: Path, cells):
        """`cells(image_id, index) -> (left, top, right, bottom)` answers ldwImageGrid::GetCellRect; GetColumnCount
        is answered from `columns(image_id)`."""
        self.game = Path(game)
        self.cells = cells
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        self.calls: list = []
        self.files: dict = {}
        self.grids: dict[int, int] = {}
        self.ids: dict[int, int] = {}
        self.images: dict[int, tuple] = {}
        self.state = e.alloc(0x20)
        vtable = e.alloc(0x40)
        e.w32(self.state, vtable)
        e.seam("gs_full_path", lambda em: (em.string(str(self.game / "Assets" / em.cstr(em.arg(0)))), 4))
        e.w32(vtable + 8, e.thunk_of["gs_full_path"])
        e.seam("?Get@ldwGameState@@SAPAV1@XZ", lambda em: (self.state, 0))
        e.seam("_fopen", self._fopen)
        e.seam("_fread", self._fread)
        e.seam("_fclose", self._fclose)
        e.seam("??2@YAPAXI@Z", lambda em: (em.alloc(max(4, em.arg(0))), 0))
        e.seam("??0ldwImage@@QAE@HH_N@Z", self._new_image)
        e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda em: (0x7000, 0))
        e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z", self._grid)
        e.seam("?GetCellRect@ldwImageGrid@@QAEXHAAUldwRect@@@Z", self._cell)
        e.seam("?GetColumnCount@ldwImageGrid@@QAEHXZ", lambda em: (self.columns(self.ids[em.ecx]), 0))
        e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda em: (0x5000, 0))
        e.seam("?CopyScreenRect@ldwGameWindow@@QAEXPAVldwImage@@ABUldwRect@@HH@Z", self._copy)
        e.seam("?SetTransparencyMask@ldwImage@@QAEXPAV1@HHPAUldwRect@@@Z", self._mask)
        e.seam("?FillRect@ldwGameWindow@@QAEXAAUldwRect@@UldwColor@@@Z", self._fill)
        e.seam("?Draw@ldwGameWindow@@QAEXPAVldwImage@@HHAAUldwRect@@M@Z", self._draw)
        e.seam("?Reset@CWorldView@@QAEX_N@Z", lambda em: (0, 4))
        e.seam("?GetDayOfYear@ldwEventManager@@SAIXZ", lambda em: (0, 0))
        self.night = e.addr("?Night@@3VCNight@@A")
        self.view = e.addr("?WorldView@@3VCWorldView@@A")
        self.rect = e.addr("?scm_sRect@CWorldView@@0UldwRect@@A")
        self.columns = lambda image: 1
        self.clock = patch_float_return(e, "?GetTimeOfDay@CNight@@QAEMXZ")
        self.stub = e.alloc(16)
        self.st0 = e.alloc(4)
        e.write(self.stub, b"\xD9\x1D" + struct.pack("<I", self.st0) + b"\xC3")      # fstp dword ptr [st0]; ret

    # ---- seams
    def _fopen(self, em):
        path = Path(em.cstr(em.arg(0)))
        if not path.is_file():
            return 0, 0
        handle = em.alloc(4)
        self.files[handle] = open(path, "rb")
        return handle, 0

    def _fread(self, em):
        buf, size, count, handle = em.arg(0), em.arg(1), em.arg(2), em.arg(3)
        data = self.files[handle].read(size * count)
        em.write(buf, data)
        return len(data) // size if size else 0, 0

    def _fclose(self, em):
        f = self.files.pop(em.arg(0), None)
        if f:
            f.close()
        return 0, 0

    def _new_image(self, em):
        self.images[em.ecx] = (em.sarg(0), em.sarg(1), em.arg(2) & 0xFF)
        return em.ecx, 12

    def _grid(self, em):
        image = em.arg(0)
        if image not in self.grids:
            self.grids[image] = em.alloc(0x40)
            self.ids[self.grids[image]] = image
        return self.grids[image], 4

    def _cell(self, em):
        index, out = em.sarg(0), em.arg(1)
        for k, v in enumerate(self.cells(self.ids[em.ecx], index)):
            em.w32(out + 4 * k, v)
        return 0, 8

    def _rect(self, em, at):
        return tuple(em.s32(at + 4 * k) for k in range(4))

    def _copy(self, em):
        self.calls.append(("copy", em.arg(0), self._rect(em, em.arg(1)), em.sarg(2), em.sarg(3)))
        return 0, 16

    def _mask(self, em):
        self.calls.append(("mask", em.ecx, self.ids.get(em.arg(0), em.arg(0)), em.sarg(1), em.sarg(2),
                           self._rect(em, em.arg(3))))
        return 0, 16

    def _fill(self, em):
        self.calls.append(("fill", self._rect(em, em.arg(0)), em.arg(1)))
        return 0, 8

    def _draw(self, em):
        self.calls.append(("draw", em.arg(0), em.sarg(1), em.sarg(2), self._rect(em, em.arg(3)),
                           round(em.farg(4), 6)))
        return 0, 20

    # ---- the calls
    def load(self) -> list:
        """CNight's constructor and LoadAssets: the light sources (kind, x, y, villager, mask image id, cell w, h,
        animated, the copy image's size)."""
        e = self.e
        e.seam("?ReCalcDaylightTimes@CNight@@QAEXXZ", lambda em: (0, 0))
        e.call("??0CNight@@QAE@XZ", ecx=self.night)
        e.call("?LoadAssets@CNight@@QAEXXZ", ecx=self.night)
        out = []
        for k in range(26):
            at = self.night + 0x50 * k
            kind = e.s32(at)
            if not kind:
                continue
            image = e.r32(at + 0x28)
            out.append({"kind": kind, "x": e.s32(at + 4), "y": e.s32(at + 8), "villager": e.s32(at + 0xC),
                        "animated": e.read(at + 0x10, 1)[0], "w": e.s32(at + 0x14), "h": e.s32(at + 0x18),
                        "mask": self.ids.get(e.r32(at + 0x1C)), "columns": e.s32(at + 0x20),
                        "copy": self.images.get(image)})
        return out

    def colour(self) -> int:
        return self.e.r32(self.night + 0x838)

    def darkness(self, time: float, sunrise=6.0, sunset=20.0, twilight=1.0) -> float:
        """CNight::GetDarknessLevel(time) with the day's sunrise, sunset and twilight set (AIIsDayTime runs whole,
        its time of day the same `time`)."""
        e = self.e
        e.wf(self.clock, time)
        e.w32(self.night + 0x868, 0)
        e.w32(self.night + 0x850, 0)
        e.wf(self.night + 0x854, sunrise)
        e.wf(self.night + 0x858, sunset)
        e.wf(self.night + 0x85C, twilight)
        e.call("?GetDarknessLevel@CNight@@QAEMM@Z", [f32(time)], ecx=self.night)
        return self._st0()

    def _st0(self) -> float:
        """GetDarknessLevel returns on the x87 stack: a stub pops it into memory."""
        self.e.call(self.stub)
        return self.e.rf(self.st0)

    def draw(self, time: float, screen=(0, 0, 2048, 2048), view=(0, 0), sunrise=6.0, sunset=20.0,
             twilight=1.0) -> list:
        """CNight::Draw at `time` over a screen `screen` looking at `view`: the recorded calls in order."""
        e = self.e
        e.wf(self.clock, time)
        e.w32(self.night + 0x868, 0)
        e.w32(self.night + 0x850, 0)
        e.wf(self.night + 0x854, sunrise)
        e.wf(self.night + 0x858, sunset)
        e.wf(self.night + 0x85C, twilight)
        e.write(self.view + 0x14, b"\x01")
        e.w32(self.view, view[0])
        e.w32(self.view + 4, view[1])
        for k, v in enumerate(screen):
            e.w32(self.rect + 4 * k, v)
        self.calls = []
        e.call("?Draw@CNight@@QAEXXZ", ecx=self.night)
        return list(self.calls)


# ====================================================================== pixels
def _bgra(raw: bytes) -> bytes:
    out = bytearray(raw)
    out[0::4], out[2::4] = raw[2::4], raw[0::4]
    return bytes(out)


class PixelRig:
    """ldwGameWindowImpl::FillRect and ldwImageImpl::SetTransparencyMask on real pixels (R, G, B, A bytes in and
    out). The screen is ARGB8888 (as the window's surface, bytes B, G, R, X); a light's copy and a mask PNG are
    ABGR8888 (R, G, B, A bytes: ldwImageImpl(w, h, true) asks SDL_CreateRGBSurface for those masks, SDL_image gives
    a PNG with alpha the same)."""
    OBJECTS = ["ldwGameWindow", "ldwImage", "ldwImageImpl"]

    def __init__(self, obj_dir: Path):
        self.e = e = pe.Emu(obj_dir, self.OBJECTS)
        e.seam("_SDL_LockSurface", lambda em: (0, 0))
        e.seam("_SDL_UnlockSurface", lambda em: (0, 0))
        e.seam("_SDL_MapRGB", lambda em: (self._map(em.arg(0), em.arg(1), em.arg(2), em.arg(3), 0xFF), 0))
        e.seam("_SDL_MapRGBA", lambda em: (self._map(em.arg(0), em.arg(1), em.arg(2), em.arg(3), em.arg(4)), 0))
        e.seam("_SDL_FillRect", self._sdl_fill)
        self.formats: dict[int, tuple] = {}

    def _format(self, masks: tuple) -> int:
        e = self.e
        fmt = e.alloc(0x28)
        for k, m in enumerate(masks):
            e.w32(fmt + 0x0C + 4 * k, m)
        e.write(fmt + 8, bytes((32, 4)))
        self.formats[fmt] = masks
        return fmt

    def _map(self, fmt, r, g, b, a):
        masks = self.formats[fmt]
        value = 0
        for c, m in zip((r & 0xFF, g & 0xFF, b & 0xFF, a & 0xFF), masks):
            if m:
                shift = (m & -m).bit_length() - 1
                value |= (c << shift) & m
        return value

    def _sdl_fill(self, em):
        surf, rect, colour = em.arg(0), em.arg(1), em.arg(2)
        x, y, w, h = (em.s32(rect + 4 * k) for k in range(4))
        pitch, buf = em.r32(surf + 0x10), em.r32(surf + 0x14)
        for row in range(y, y + h):
            em.write(buf + row * pitch + 4 * x, struct.pack("<I", colour) * w)
        return 0, 0

    def surface(self, w: int, h: int, data: bytes, masks: tuple) -> tuple[int, int]:
        e = self.e
        fmt = self._format(masks)
        buf = e.alloc(len(data))
        e.write(buf, data)
        surf = e.alloc(0x40)
        for off, v in ((4, fmt), (8, w), (0xC, h), (0x10, w * 4), (0x14, buf)):
            e.w32(surf + off, v)
        return surf, buf

    SCREEN = (0x00FF0000, 0x0000FF00, 0x000000FF, 0)
    ABGR = (0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000)

    def fill(self, pixels: bytes, w: int, h: int, rect: tuple, rgba_floats: tuple) -> bytes:
        """FillRect(rect (left, top, right, bottom), r, g, b, a) over a screen holding `pixels` (R, G, B, A
        bytes; the screen keeps no alpha). Returns the screen's R, G, B bytes with A 255."""
        e = self.e
        surf, buf = self.surface(w, h, _bgra(pixels), self.SCREEN)
        impl = e.alloc(0x80)
        e.w32(impl + 0x30, surf)
        for k, v in enumerate((0, 0, w, h)):
            e.w32(impl + 0x60 + 4 * k, v)
        r = e.alloc(16)
        for k, v in enumerate(rect):
            e.w32(r + 4 * k, v)
        e.call("?FillRect@ldwGameWindowImpl@@QAEXAAUldwRect@@MMMM@Z", [r, *[f32(v) for v in rgba_floats]], ecx=impl)
        out = bytearray(_bgra(e.read(buf, w * h * 4)))
        out[3::4] = b"\xff" * (w * h)
        return bytes(out)

    def line(self, pixels: bytes, w: int, h: int, x0: int, y0: int, x1: int, y1: int, colour: int, a0: float,
             a1: float, clip=None) -> bytes:
        """ldwGameWindowImpl::DrawLine(x0, y0, x1, y1, ldwColor, alpha at the start, alpha at the end) over a
        screen holding `pixels` (R, G, B, A bytes). Returns the screen's R, G, B bytes with A 255."""
        e = self.e
        surf, buf = self.surface(w, h, _bgra(pixels), self.SCREEN)
        impl = e.alloc(0x80)
        e.w32(impl + 0x30, surf)
        for k, v in enumerate(clip or (0, 0, w, h)):
            e.w32(impl + 0x60 + 4 * k, v)
        e.call("?DrawLine@ldwGameWindowImpl@@QAEXHHHHUldwColor@@MM@Z",
               [x0, y0, x1, y1, colour, f32(a0), f32(a1)], ecx=impl)
        out = bytearray(_bgra(e.read(buf, w * h * 4)))
        out[3::4] = b"\xff" * (w * h)
        return bytes(out)

    def compose(self, pixels: bytes, w: int, h: int, fills=(), lines=(), clip=None) -> bytes:
        """Over one screen holding `pixels`: FillRect(the whole screen, rgba) for each of `fills`, then DrawLine for
        each of `lines` (x0, y0, x1, y1, ldwColor, a0, a1), in that order. R, G, B bytes out, A 255."""
        e = self.e
        surf, buf = self.surface(w, h, _bgra(pixels), self.SCREEN)
        impl = e.alloc(0x80)
        e.w32(impl + 0x30, surf)
        for k, v in enumerate(clip or (0, 0, w, h)):
            e.w32(impl + 0x60 + 4 * k, v)
        r = e.alloc(16)
        for k, v in enumerate((0, 0, w, h)):
            e.w32(r + 4 * k, v)
        for rgba in fills:
            e.call("?FillRect@ldwGameWindowImpl@@QAEXAAUldwRect@@MMMM@Z", [r, *[f32(v) for v in rgba]], ecx=impl)
        for x0, y0, x1, y1, colour, a0, a1 in lines:
            e.call("?DrawLine@ldwGameWindowImpl@@QAEXHHHHUldwColor@@MM@Z",
                   [x0, y0, x1, y1, colour, f32(a0), f32(a1)], ecx=impl)
        out = bytearray(_bgra(e.read(buf, w * h * 4)))
        out[3::4] = b"\xff" * (w * h)
        return bytes(out)

    def mask(self, copy: bytes, cw: int, ch: int, mask: bytes, mw: int, mh: int, x: int, y: int,
             rect: tuple) -> bytes:
        """ldwImage::SetTransparencyMask(mask, x, y, rect) on a light's copy (both R, G, B, A bytes)."""
        e = self.e
        csurf, cbuf = self.surface(cw, ch, copy, self.ABGR)
        msurf, _mbuf = self.surface(mw, mh, mask, self.ABGR)

        def image(surf):
            impl = e.alloc(0x10)
            e.w32(impl, surf)
            e.write(impl + 4, b"\x01")
            obj = e.alloc(0x10)
            e.w32(obj + 4, impl)
            return obj
        target, source = image(csurf), image(msurf)
        r = e.alloc(16)
        for k, v in enumerate(rect):
            e.w32(r + 4 * k, v)
        e.call("?SetTransparencyMask@ldwImage@@QAEXPAV1@HHPAUldwRect@@@Z", [source, x, y, r], ecx=target)
        return e.read(cbuf, cw * ch * 4)
