"""The Picture Maker's screens, family tree, collection pages and store boxes (src/vf2_art_screens.py).

Always run: the decorated-name reader the emulation uses, the module's own clipping and line rules on fixed cases.

With the B200 desktop objects (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) and the original game
(work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR), else skipped: each scene's constructor and DrawScene (and
CAchievement::DrawAchievement, CScrollingStoreScene::DrawVisibleStoreItem, CFamilyTreeScene::DrawFamily /
DrawConnectingLine) run in Unicorn (tests/vf2_screens_emu.py) and every picture's layers must be exactly the
game's recorded draws; the module's tables must be the objects' data tables; the clipping and line rules must be
the game's own ldwGameWindowImpl::ClipRect and DrawLine; theGameState's constructor must set the 1024 x 768 window.
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

import vf2_art_screens as sc  # noqa: E402
import vf2_game_pictures as gp  # noqa: E402

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE_GAME = (GAME_DIR / "Images" / "awards_bg.jpg").is_file()
HAVE_OBJECTS = (OBJ_DIR / "CollectionScene.obj").is_file() and (OBJ_DIR / "theGameState.obj").is_file()
needs_code = pytest.mark.skipif(not (HAVE_GAME and HAVE_OBJECTS),
                                reason="no B200 desktop object files or no original game folder")

try:
    import unicorn  # noqa: F401
    HAVE_UNICORN = True
except ImportError:                                     # pragma: no cover
    HAVE_UNICORN = False
needs_code = pytest.mark.skipif(not (HAVE_GAME and HAVE_OBJECTS and HAVE_UNICORN),
                                reason="no B200 desktop object files, no original game folder or no unicorn")


# ====================================================================== always
def test_the_decorated_name_reader():
    import vf2_screens_emu as se
    assert se.signature("?Draw@theGraphicsManager@@QAEXW4EImage@@HHMH@Z") == (20, "void", False)
    assert se.signature("??0ldwButton@@QAE@HPAVldwImageGrid@@UldwPoint@@PAVldwScene@@_N@Z") == (24, "void", False)
    assert se.signature("?Get@theButterflyClass@@SAPAV1@XZ") == (0, "ptr", False)
    assert se.signature("?GetMousePosition@ldwEventManager@@SA?AUldwPoint@@XZ") == (0, "ptr", True)
    assert se.signature("?Count@CCollectableItem@@QBE?BHW4ECarrying@@@Z") == (4, "int", False)
    assert se.signature("?DrawPeep@CFamilyTreeScene@@AAEXUldwPoint@@HHHM_N@Z") == (28, "void", False)
    assert se.signature("_sprintf") == (0, "int", False)


def test_clipping_and_lines():
    assert sc.clip((0, 0, 248, 91), 85, 195, (93, 187, 960, 768)) == ((8, 0, 248, 91), 93, 195)
    assert sc.clip((0, 0, 1024, 59), 0, 722) == ((0, 0, 1024, 46), 0, 722)
    assert sc.clip((0, 0, 10, 10), 2000, 0) is None
    assert sc.line(520, 190, 693, 190, (1, 2, 3)) == gp.Fill(520, 190, 174, 1, (1, 2, 3, 255))
    assert sc.line(148, 368, 148, 351, (1, 2, 3)) == gp.Fill(148, 351, 1, 18, (1, 2, 3, 255))
    assert sc.line(5, 0, 5, 10, (0, 0, 0), (6, 0, 100, 100)) is None


# ====================================================================== the game's code
def _game_files():
    return gp.GameFiles(GAME_DIR)


def _art(key):
    arts = {a.key: a for a in sc.arts(_game_files())}
    return arts[f"screens/{key}"]


def _layers(art):
    """An Art's layers in the rig's form."""
    files = _game_files()
    art = gp.resolve(files, art)
    out = []
    for layer in art.layers:
        if isinstance(layer, gp.Fill):
            out.append(("fill", layer.x, layer.y, layer.w, layer.h, tuple(layer.rgba)))
        else:
            assert layer.percent == 100 and layer.tint is None and layer.make is None
            out.append(("draw", layer.file, tuple(layer.rect), layer.x, layer.y, layer.alpha))
    return out


def _rig(objects):
    import vf2_screens_emu as se
    return se.ScreenRig(OBJ_DIR, GAME_DIR, [*objects, "theGameState"])


def _check(art, rig, records=None):
    assert art.checked
    assert rig.draws(records) == _layers(art), art.key


SCENES = {
    "menu": ("theMenuScene", "??0theMenuScene@@QAE@XZ", "?DrawScene@theMenuScene@@MAEXXZ", ()),
    "loading": ("theLoadingScene", "??0theLoadingScene@@QAE@XZ", "?DrawScene@theLoadingScene@@MAEXXZ",
                ("theContinuousVariableMeter",)),
    "details": ("theVillagerScene", "??0theVillagerScene@@QAE@XZ", "?DrawScene@theVillagerScene@@MAEXXZ", ()),
    "adoption": ("AdoptionScene", "??0CAdoptionScene@@AAE@XZ", "?DrawScene@CAdoptionScene@@MAEXXZ", ()),
    "dating": ("DatingScene", "??0CDatingScene@@AAE@XZ", "?DrawScene@CDatingScene@@MAEXXZ", ()),
    "help": ("theHelpScene", "??0theHelpScene@@QAE@XZ", "?DrawScene@theHelpScene@@MAEXXZ", ()),
    "store/screen": ("ScrollingStoreScene", "??0CScrollingStoreScene@@AAE@XZ",
                     "?DrawScene@CScrollingStoreScene@@MAEXXZ", ("Money",)),
}


@needs_code
@pytest.mark.parametrize("key", sorted(SCENES))
def test_each_screen_is_the_games(key):
    obj, ctor, fn, extra = SCENES[key]
    rig = _rig([obj, *extra])
    this = rig.new(ctor)
    rig.draw(fn, this)
    _check(_art(key), rig)


@needs_code
def test_the_splash_screen():
    rig = _rig(["theSplashScene"])
    this = rig.new("??0theSplashScene@@QAE@XZ")
    e = rig.e
    assert e.s32(this + 0x2C) == 1 and rig.images[e.r32(this + 0x1C)] == "SPLASH_BG.JPG"
    rig.draw("?DrawScene@theSplashScene@@MAEXXZ", this)
    assert rig.draws() == [] and rig.defaults[-1][0] == "?Draw@CMoviePlayer@@QBEXUldwPoint@@@Z"   # the movie
    e.write(this + 0x19, b"\1")
    rig.draw("?DrawScene@theSplashScene@@MAEXXZ", this)
    _check(_art("splash"), rig)


@needs_code
def test_the_achievements_screen():
    rig = _rig(["AchievementsScene", "Achievement"])
    e = rig.e
    ach = rig.sym("?Achievement@@3VCAchievement@@A")
    e.call("??0CAchievement@@QAE@XZ", ecx=ach)
    this = rig.new("??0CAchievementsScene@@AAE@XZ")
    rig.draw("?DrawScene@CAchievementsScene@@MAEXXZ", this)
    _check(_art("achievements/none"), rig)
    for k in range(0x5F):
        e.write(ach + 12 * k, b"\1")
    rig.draw("?DrawScene@CAchievementsScene@@MAEXXZ", this)
    _check(_art("achievements/earned"), rig)
    # the goals the module keeps are the game's achievementList in achievementOrder
    order, table = rig.sym("?achievementOrder@@3QBHB"), rig.sym("?achievementList@@3PAUsAchievementListEntry@@A")
    goals = tuple(e.s32(table + 28 * e.s32(order + 4 * k) + 4) for k in range(sc.ACHIEVEMENT_ROWS))
    assert goals == sc.ACHIEVEMENT_GOALS


def _tree_rig(families=(3, 5), joined=True):
    rig = _rig(["FamilyTreeScene"])
    e = rig.e
    records = []
    for kids in families:
        r = rig.zalloc(0x1B8 + 24 * 0xD8)
        e.write(r + 0xF6, b"\1")                       # a couple
        e.w32(r + 0x1B4, kids)
        records.append(r)
    if joined:
        e.w32(records[1] + 0x30, 1)                    # the second family's parent is the first family's child 1,
        e.write(records[0] + 0xD8 + 0x1D2, b"\1")      # who has a family of their own
    peeps = []
    e.seam("?NumGenerations@CFamilyTree@@QAEHXZ", lambda em: (len(records), 0))
    e.seam("?GetFamilyRecord@CFamilyTree@@QAEPAUSFamilyRecord@1@H@Z",
           lambda em: (records[em.sarg(0)] if 0 <= em.sarg(0) < len(records) else 0, 4))
    e.seam("?DrawPeep@CFamilyTreeScene@@AAEXUldwPoint@@HHHM_N@Z",
           lambda em: (peeps.append((em.sarg(0), em.sarg(1))), (0, 28))[1])
    this = rig.new("??0CFamilyTreeScene@@AAE@XZ")
    rig.draw("?DrawScene@CFamilyTreeScene@@MAEXXZ", this)
    return rig, this, peeps


@needs_code
def test_the_family_tree():
    rig, this, peeps = _tree_rig()
    e = rig.e
    assert tuple(e.s32(this + o) for o in (0xC, 0x10, 0x14, 0x18)) == sc.TREE_VIEW
    _check(_art("family_tree"), rig)
    assert len({p for p in peeps}) == 4 + 8                 # a portrait in each frame: those are people (left out)
    assert not [r for r in rig.records if r[0] in ("tinted", "scaled", "centered", "draw_rect", "draw?")]


@needs_code
def test_the_collection_pages_and_their_tables():
    rig = _rig(["CollectionScene"])
    e = rig.e
    have = {"n": 1}
    e.seam("?Count@CCollectableItem@@QBE?BHW4ECarrying@@@Z", lambda em: (have["n"], 4))
    this = rig.new("??0CCollectionScene@@AAE@XZ")
    for page in range(5):
        e.w32(this + 0x14, page)
        for n in (1, 0):
            have["n"] = n
            rig.draw("?DrawScene@CCollectionScene@@MAEXXZ", this)
            _check(_art(f"collection/{page}/{'all' if n else 'none'}"), rig)

    def table(name, n, stride=12, width=3):
        at = rig.sym(name)
        return tuple(tuple(e.s32(at + stride * k + 4 * j) for j in range(width)) for k in range(n))
    assert table("?sm_sCollectable@CCollectionScene@@0PAUSCollectable@1@A", 60) == sc.ITEMS
    assert table("?gCollectionFrame@@3PAUSCollectable@CCollectionScene@@A", 5) == sc.FRAMES
    assert table("?gCollectionLabel@@3PAUSCollectable@CCollectionScene@@A", 5) == sc.LABELS
    assert table("?gInsectPin@@3PAUSCollectable@CCollectionScene@@A", 12) == sc.PINS
    assert tuple(v for (v,) in table("?gCollectable@@3PAW4ECarrying@@A", 60, 4, 1)) == sc.VALUES
    # five pages: the arrows go 0 -> 4 on the left and 5 -> 0 on the right (CCollectionScene::HandleMouse)
    import vf2_people_emu as pe
    o = pe.CoffObject(OBJ_DIR / "CollectionScene.obj")
    raw = o.data
    assert b"\xc7\x43\x14\x04\x00\x00\x00" in raw and b"\x83\xf8\x05" in raw


@needs_code
def test_the_collectible_cells_are_the_collections():
    # CCollectableItem::Draw draws an ECarrying value from collectables_small.png (image 493) as cell value - 4Fh
    import vf2_people_emu as pe
    o = pe.CoffObject(OBJ_DIR / "CollectableItem.obj")
    assert b"\x8d\x42\xb1" in o.data                         # lea eax, [edx - 4Fh]
    assert gp.entry_by_id(493).file == "collectables_small.png"
    for k, value in enumerate(sc.VALUES):
        assert sc.CELL_LABELS[(493, value - 79)].startswith(sc.ITEM_NAMES[k])
    assert len(sc.CELL_LABELS) == 60


@needs_code
def test_the_store_boxes():
    rig = _rig(["ScrollingStoreScene", "Money"])
    e = rig.e
    food_club = {"v": 0}
    e.seam("?HaveFoodClub@CFoodStore@@QAE_NXZ", lambda em: (food_club["v"], 0))
    this = rig.new("??0CScrollingStoreScene@@AAE@XZ")
    fn = "?DrawVisibleStoreItem@CScrollingStoreScene@@AAEXHHH@Z"

    def ids(name, n, stride):
        at = rig.sym(name)
        return tuple(e.s32(at + stride * k) for k in range(n))
    assert ids("?gIAPItem@@3PAUsIAPItem@@A", 11, 12) == tuple(i for i, _n in sc.IAP)
    assert ids("?gMenuItem@@3PAUsMenuItem@@A", 8, 16) == sc.MENU
    assert ids("?gFurnitureMenuItem@@3PAUsMenuItem@@A", 8, 16) == sc.FURNITURE_MENU
    e.w32(this + 0xD4, 0x16)
    for k in range(11):
        rig.draw(fn, this, [0, 0, k])
        _check(_art(f"store/iap/{k}"), rig)
    # bought: brokerage (CMoney's rate), Food Club, Health Plan (theGameState+25B1Dh), Lucky Rock (CCollectableItem)
    e.wf(rig.sym("?Money@@3VCMoney@@A") + 8, 1.0)
    food_club["v"] = 1
    e.write(rig.state + 0x25B1D, b"\1")
    e.write(rig.sym("?CollectableItem@@3VCCollectableItem@@A") + 0x8A8, b"\1")
    for k in sc.OWNED_CHECK:
        rig.draw(fn, this, [0, 0, k])
        _check(_art(f"store/iap/{k}/owned"), rig)
    for table, cat in ((0, 0x17), (1, 0x18)):
        e.w32(this + 0xD4, cat)
        for k in range(8):
            rig.draw(fn, this, [0, 0, k])
            _check(_art(f"store/menu/{table}/{k}"), rig)


@needs_code
def test_the_window_is_1024_by_768_and_never_wide():
    rig = _rig([])
    state = rig.zalloc(0x26000)
    rig.e.call("??0theGameState@@IAE@XZ", ecx=state)
    e = rig.e
    assert (e.s32(state + 0x25CD8), e.s32(state + 0x25CDC), e.read(state + 0x25CE0, 1)) == (1024, 768, b"\0")
    assert e.call("?GetWideScreenOffsetX@theGameState@@QAEHXZ", ecx=state) == 0
    # no object refers to SetToWideScreen but its own definition
    import vf2_people_emu as pe
    users = []
    for path in sorted(OBJ_DIR.glob("*.obj")):
        o = pe.CoffObject(path)
        for _k, (name, _v, sect, _c) in o.symbols.items():
            if "SetToWideScreen" in name and sect == 0:
                users.append(path.stem)
        if path.stem == "theGameState":
            index = [k for k, s in o.symbols.items() if "SetToWideScreen" in s[0]]
            for s in o.sections:
                if not s["name"].startswith(".debug"):         # the debug records name every function
                    assert not any(si in index for _va, si, _t in s["relocs"]), s["name"]
    assert users == []


@needs_code
def test_clipping_is_the_games_clip_rect():
    import vf2_pictures_emu as pe2
    meter = pe2.MeterRig(OBJ_DIR)
    import vf2_screens_emu as se
    cases = [((0, 0, 248, 91), 85, 195, (93, 187, 960, 768)), ((0, 0, 1024, 59), 0, 722, (0, 0, 1024, 768)),
             ((0, 0, 923, 57), 48, 745, (40, 85, 984, 768)), ((0, 0, 1024, 4500), 0, 0, (0, 144, 1024, 768)),
             ((0, 0, 1024, 4500), 0, 0, (0, 0, 1024, 767)), ((0, 0, 50, 50), 2000, 10, (0, 0, 1024, 768)),
             ((0, 0, 50, 50), -20, -30, (0, 0, 1024, 768))]
    for rect, x, y, area in cases:
        game = meter.clip_rect(x, y, rect[2], rect[3], area)
        want = None if game is None else ((game[0], game[1], game[0] + game[4], game[1] + game[5]), game[2], game[3])
        assert sc.clip(rect, x, y, area) == want
        assert se.clip_draw(rect, x, y, area) == want


@needs_code
def test_lines_are_the_games_draw_line():
    """ldwGameWindow::DrawLine -> ldwGameWindowImpl::DrawLine run whole; the rectangle it hands FillRect must be the
    module's (and the rig's) line."""
    import vf2_people_emu as pe
    import vf2_screens_emu as se
    e = pe.Emu(OBJ_DIR, ["ldwGameWindow"])
    fills = []
    e.seam("?FillRect@ldwGameWindowImpl@@QAEXAAUldwRect@@MMMM@Z",
           lambda em: (fills.append((tuple(em.s32(em.arg(0) + 4 * k) for k in range(4)),
                                     tuple(em.farg(k) for k in range(1, 5)))), (0, 20))[1])
    window, impl = e.alloc(16), e.alloc(0x100)
    e.w32(window, impl)
    for x1, y1, x2, y2, colour in [(520, 190, 693, 190, 0xFF646464), (148, 368, 148, 351, 0xFF000000)]:
        for area in [(93, 187, 960, 768), (0, 0, 1024, 768), (150, 0, 600, 360)]:
            for k, v in enumerate(area):
                e.w32(impl + 0x60 + 4 * k, v)
            fills.clear()
            e.call("?DrawLine@ldwGameWindow@@QAEXHHHHUldwColor@@@Z", [x1, y1, x2, y2, colour], ecx=window)
            rgb = tuple((colour >> s) & 0xFF for s in (0, 8, 16))
            want = sc.line(x1, y1, x2, y2, rgb, area)
            got = fills[0][0] if fills else None
            if want is None:
                assert not fills
                continue
            assert got == (want.x, want.y, want.x + want.w, want.y + want.h)
            assert fills[0][1] == se.color_floats(colour)
            assert se.fill_rect(se.line_rect(x1, y1, x2, y2), fills[0][1], area)[1:] == (want.x, want.y, want.w,
                                                                                         want.h, want.rgba)


@needs_code
def test_every_picture_is_checked_and_draws():
    files = _game_files()
    arts = sc.arts(files)
    assert len(arts) == 52
    for art in arts:
        assert art.key.startswith("screens/") and art.used and art.checked
        assert art.category.split("/")[0] in gp.CATEGORY_ORDER
        for layer in art.layers:
            assert isinstance(layer, gp.Fill) or files.has(layer.file)
    for key in ("screens/family_tree", "screens/store/iap/8/owned", "screens/collection/4/all"):
        image = gp.draw(files, next(a for a in arts if a.key == key))
        assert (image.width, image.height) in ((1024, 768), (923, 114))
