"""The Picture Maker's interface pictures (src/vf2_art_ui.py) against the game's own code.

Always run: the rules. With the B200 desktop objects (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) and the
original game (work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR), else skipped: ldwButton, ldwRadioButton,
theOptionsDialog::DrawNoFadeScene, ldwTiledBackground and CAchievement::DrawAchievement run in Unicorn and every draw
of every picture must be theirs; the claims about which code fetches which picture are read from the objects.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vf2_art_ui as au  # noqa: E402
import vf2_game_pictures as gp  # noqa: E402

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE_GAME = (GAME_DIR / "Images" / "btn_green.png").is_file()
HAVE_OBJECTS = (OBJ_DIR / "ldwButton.obj").is_file()
needs_game = pytest.mark.skipif(not HAVE_GAME, reason="no original game folder (work/vanilla_runtime_payload)")
needs_code = pytest.mark.skipif(not (HAVE_GAME and HAVE_OBJECTS),
                                reason="needs the B200 desktop objects and the original game folder")


@pytest.fixture(scope="module")
def files():
    return gp.GameFiles(GAME_DIR)


@pytest.fixture(scope="module")
def arts(files):
    return {a.key: a for a in au.arts(files)}


def test_the_rules():
    assert au.tile_grid(640, 498) == (11, 9) and au.tile_grid(10, 10) == (2, 2) and au.tile_grid(53, 47) == (2, 2)
    assert au.tile_grid(54, 47) == (2, 2) and au.tile_grid(117, 110) == (3, 2) and au.tile_grid(117, 111) == (3, 3)
    assert [c for c, _x, _y in au.tiled_draws(200, 120)] == [8, 1, 1, 0, 3, 7, 7, 2, 5, 4, 4, 6]
    assert [au.checkbox_cell(2, m, t) for t in (False, True) for m in (0, 1, 2)] == [0, 0, 0, 1, 1, 1]
    assert au.checkbox_cell(4, 2, True) == 3


@needs_game
def test_the_catalogue(arts):
    assert len(arts) == 3 * len(au.BUTTONS) + 4 + len(au.SLIDER_LEVELS) + len(au.DIALOGS) + 1 + 6 + 2
    for art in arts.values():
        assert art.used and art.checked and art.key.startswith("ui/")
        assert art.category.split("/")[0] in gp.CATEGORY_ORDER
    assert arts["ui/button/296/pressed"].layers[0].rect == (290, 0, 435, 34)
    assert arts["ui/dialog/options"].layers[0].rect == (512, 0, 576, 64)          # top left corner first


@needs_game
def test_every_picture_draws(files, arts):
    for art in arts.values():
        image = gp.draw(files, art)
        assert image.width * image.height > 1 and image.bbox() is not None, art.key


# ------------------------------------------------------------------ against the game
def _rig(objects):
    import vf2_ui_emu as ue
    rig = ue.UiRig(OBJ_DIR, GAME_DIR, objects + ["ldwHintControl"])
    return rig


@needs_code
def test_the_buttons_are_the_games(files, arts):
    import vf2_ui_emu as ue
    rig = _rig(["ldwButton"])
    for image in au.BUTTONS:
        button = rig.e.alloc(0x40)
        rig.e.call("??0ldwButton@@QAE@HPAVldwImageGrid@@UldwPoint@@PAVldwScene@@_N@Z",
                   [1, rig.picture(image), 0, 0, 0, 0], ecx=button)
        impl = rig.e.r32(button + 0x10)
        assert rig.run("?Draw@ldwButton@@UAEXXZ", ecx=button) == []          # not shown until SetActive
        rig.e.write(impl + 0x28, b"\x01")
        assert rig.e.read(impl + 0x29, 1) == b"\x01"                       # the constructor enables it
        for state, key, _words in au.STATES:
            rig.e.w32(impl + 0x30, state)
            draws = rig.run("?Draw@ldwButton@@UAEXXZ", ecx=button)
            assert ue.as_layers(files, draws) == ue.art_layers(arts[f"ui/button/{image}/{key}"]), (image, key)
    # a disabled button would be cell 0 tinted -- but nothing outside ldwButton enables or disables one
    for name in ("?Enable@ldwButton@@", "?SetDisabledTint@ldwButton@@"):
        assert {obj for obj, _fn, _sym in ue.references(OBJ_DIR, name)} <= {"ldwButton"}, name


@needs_code
def test_the_buttons_strips_are_the_games_buttons():
    """Every strip is fetched by the code the pictures name, each just before an ldwButton is made of it."""
    import vf2_ui_emu as ue
    for image in au.BUTTONS:
        sites = {obj for obj, _fn in ue.image_sites(OBJ_DIR, image)}
        assert sites, image
    assert {obj for obj, _fn in ue.image_sites(OBJ_DIR, 622)} == {"theAlignVillagerScene"}
    assert {obj for obj, _fn in ue.image_sites(OBJ_DIR, 623)} == {"theAlignVillagerScene"}
    assert {obj for obj, _fn in ue.image_sites(OBJ_DIR, 313)} == {"theGameMenuDialog"}
    assert {obj for obj, _fn in ue.image_sites(OBJ_DIR, 28)} == {"theMainScene"}


@needs_code
def test_the_check_boxes_are_the_games(files, arts):
    import vf2_ui_emu as ue
    rig = _rig(["ldwRadioButton"])
    box = rig.e.alloc(0x40)
    rig.e.call("??0ldwRadioButton@@QAE@HPAVldwImageStrip@@UldwPoint@@PAVldwScene@@PBDUldwColor@@PAVldwFont@@@Z",
               [5, rig.picture(au.CHECKBOX), 0, 0, 0, rig.empty, 0, 0], ecx=box)
    impl = rig.e.r32(box + 0x10)
    rig.e.write(impl + 0x30, b"\x01")
    for ticked in (False, True):
        rig.e.write(impl + 0x31, bytes((int(ticked),)))
        want = ue.art_layers(arts[f"ui/checkbox/{'ticked' if ticked else 'unticked'}"])
        for mouse in (0, 1, 2):
            rig.e.w32(impl + 0x38, mouse)
            draws = rig.run("?Draw@ldwRadioButton@@UAEXXZ", ecx=box)
            assert ue.as_layers(files, draws) == want, (ticked, mouse)
    # the Options dialog makes its check boxes of CheckboxStrip.png (+0x90)
    assert ue.image_stores(OBJ_DIR, "theOptionsDialog", "??0theOptionsDialog@@QAE@PADW4DialogColorEnum@@@Z")[0x90] \
        == au.CHECKBOX


@needs_code
def test_the_options_dialog_is_the_games(files, arts):
    import vf2_ui_emu as ue
    stores = ue.image_stores(OBJ_DIR, "theOptionsDialog", "??0theOptionsDialog@@QAE@PADW4DialogColorEnum@@@Z")
    assert {k: stores[k] for k in (0x98, 0x9C, 0xA0, 0xA4)} == {0x98: au.RADIO_BLANK, 0x9C: au.RADIO_SELECTED,
                                                               0xA0: au.SLIDER, 0xA4: au.HANDLE}
    rig = _rig(["theOptionsDialog"])
    e = rig.e
    dialog = e.alloc(0x200)
    for off, image in stores.items():
        e.w32(dialog + off, rig.picture(image))
    e.w32(dialog + 0x80, rig.state)
    e.w32(dialog + 0xA8, rig.window)
    e.w32(dialog + 0xB4, rig.strings)
    x0, y0 = 100, 50
    e.w32(dialog + 0x84, x0)
    e.w32(dialog + 0x8C, y0)

    def draw(fullscreen=0, choice=10, flag=0, off1=0, off2=0):
        e.write(dialog + 0x60, b"\x01")                       # the full-screen row is offered
        e.write(rig.state + 0x25B29, bytes((fullscreen,)))
        e.w32(rig.state + 0x25B18, choice)
        e.write(rig.state + 0x25B1C, bytes((flag,)))
        e.w32(dialog + 0x6C, off1)
        e.w32(dialog + 0x70, off2)
        return [d for d in rig.run("?DrawNoFadeScene@theOptionsDialog@@MAEXXZ", ecx=dialog)]

    def moved(layers, dx, dy):
        return [(d[0], d[1], d[2], d[3] - dx, d[4] - dy, d[5]) for d in layers]

    # the choice of row y + 315: 999 or more chooses the left, 10 the right, anything else draws neither
    for value, key in ((999, "left"), (10, "right")):
        row = [d for d in ue.as_layers(files, draw(choice=value)) if d[4] == y0 + 0x13B]
        assert moved(row, x0, y0 + 0x13B) == ue.art_layers(arts[f"ui/choice/{key}"]), key
    assert not [d for d in draw(choice=5) if d[4] == y0 + 0x13B]
    # the row y + 390 follows a flag; the full-screen row is 5 pixels lower when its right side is chosen
    for flag, key in ((1, "left"), (0, "right")):
        row = [d for d in ue.as_layers(files, draw(flag=flag)) if d[4] == y0 + 0x186]
        assert moved(row, x0, y0 + 0x186) == ue.art_layers(arts[f"ui/choice/{key}"]), key
    assert moved([d for d in ue.as_layers(files, draw(fullscreen=1)) if d[4] == y0 + 0xF5], x0, y0 + 0xF5) \
        == ue.art_layers(arts["ui/choice/left"])
    assert moved([d for d in ue.as_layers(files, draw(fullscreen=0)) if d[4] == y0 + 0xFA], x0, y0 + 0xFA) \
        == ue.art_layers(arts["ui/choice/right"])
    # the two sliders
    for offset, _words in au.SLIDER_LEVELS:
        layers = ue.as_layers(files, draw(off1=offset, off2=offset))
        want = ue.art_layers(arts[f"ui/slider/{offset}"])
        for dy in (0, 0x28):
            got = [d for d in layers if d[1] in ("WideSlider2.png", "sliderhandle.png") and d[4] == y0 + 0x3C + dy]
            assert moved(got, x0, y0 + dy) == want, (offset, dy)


@needs_code
def test_the_slider_range_is_the_games():
    """HandleMouse clamps the handle to 0..267 (0x10B) and a volume sets (int)(volume x 263.0)."""
    import vf2_ui_emu as ue
    writes = ue.member_writes(OBJ_DIR, "theOptionsDialog", "?HandleMouse@theOptionsDialog@@UAE_NHUldwPoint@@@Z")
    assert {0x6C: {0, au.HANDLE_MAX}, 0x70: {0, au.HANDLE_MAX}}.items() <= {k: v & {0, au.HANDLE_MAX}
                                                                         for k, v in writes.items()}.items()
    assert "__real@43838000" in ue.called_symbols(OBJ_DIR, "theOptionsDialog")      # 263.0f


def _tiles_rig():
    import vf2_ui_emu as ue
    rig = _rig(["ldwTiledBackground"])
    shadows = ue.static_writes(OBJ_DIR, "theGame", "?Init@theGame@@UAE_NXZ")
    assert shadows["?mShadowRightWidth@ldwTiledBackground@@1HA"] == au.SHADOW_RIGHT
    assert shadows["?mShadowBottomHeight@ldwTiledBackground@@1HA"] == au.SHADOW_BOTTOM
    for name, value in shadows.items():
        if "mShadow" in name:
            rig.e.w32(ue.static_address(rig.e, name), value)
    # nothing ever sets the left and top shadows (they stay 0)
    for side in ("mShadowLeftWidth", "mShadowTopHeight"):
        writers = [(o, f) for o, f, _s in ue.references(OBJ_DIR, side) if o != "ldwTiledBackground"]
        assert not writers, (side, writers)
    return rig


def _tiles(rig, grid, w, h, x=0, y=0, alpha=1.0):
    bg = rig.e.alloc(0x40)
    rig.e.call("??0ldwTiledBackground@@QAE@PAVldwImageGrid@@HH@Z", [rig.picture(grid), w, h], ecx=bg)
    return rig.run("?Draw@ldwTiledBackground@@UAEXUldwPoint@@M@Z", [x, y, alpha], ecx=bg)


@needs_code
def test_the_dialog_backdrops_are_the_games(files, arts):
    import vf2_ui_emu as ue
    rig = _tiles_rig()
    for key, _label, grid, w, h, _where in au.DIALOGS:
        draws = _tiles(rig, grid, w, h)
        assert ue.as_layers(files, draws) == ue.art_layers(arts[f"ui/dialog/{key}"]), key
    for w, h in ((10, 10), (53, 47), (54, 47), (117, 110), (117, 111), (899, 60)):
        draws = _tiles(rig, 352, w, h, 7, 9)
        assert [(d[2], d[3], d[4]) for d in draws] == au.tiled_draws(w, h, 7, 9), (w, h)


@needs_code
def test_the_dialog_sizes_are_the_games():
    """Each dialog's SetTiling(grid, width, height) (or GetImageGridForCanvas's canvas) as the pictures say."""
    import vf2_ui_emu as ue
    found = ue.tiling_calls(OBJ_DIR)
    assert found["BankDialog"] == (560, 440) and found["theOptionsDialog"] == (640, 498)
    assert found["theGameMenuDialog"] == (640, 448) and found["theCreateNickNameDlg"] == (360, 200)
    assert found["theChangePlayerDlg"] == (455, 400) and found["FamilyTreeInfoDlg"] == (710, 250)
    assert found["DiagnosisDialog"] == (600, 340) and found["RedeemCreditDlg"] == (400, 280)
    assert found["thePurchaseDialog"] == (600, 400)
    # the sheets the dialogs that name one ask for (the others choose it by canvas: test_the_canvas_grids)
    for key, obj in (("banking", "BankDialog"), ("diagnosis", "DiagnosisDialog"), ("redeem", "RedeemCreditDlg"),
                     ("purchase", "thePurchaseDialog")):
        grid = next(d[2] for d in au.DIALOGS if d[0] == key)
        assert obj in {o for o, _fn in ue.image_sites(OBJ_DIR, grid)}, key


@needs_code
def test_the_canvas_grids_are_the_games():
    import vf2_ui_emu as ue
    rig = ue.UiRig(OBJ_DIR, GAME_DIR, ["theGraphicsManager"])
    rig.e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z",
               lambda em: (rig.picture(em.arg(0)), 4))
    for canvas, grid in ((0, 351), (1, 352), (2, 350), (3, 351)):
        obj = rig.e.call("?GetImageGridForCanvas@theGraphicsManager@@QAEPAVldwImageGrid@@H@Z", [canvas], ecx=rig.gm)
        assert rig.objects[obj] == grid, canvas


@needs_code
def test_the_achievement_popup_is_the_games(files, arts):
    import vf2_ui_emu as ue
    rig = _rig(["Achievement", "ldwTiledBackground"])
    for name, value in ue.static_writes(OBJ_DIR, "theGame", "?Init@theGame@@UAE_NXZ").items():
        if "mShadow" in name:
            rig.e.w32(ue.static_address(rig.e, name), value)
    ach = rig.e.alloc(0x1000)
    draws = rig.run("?DrawAchievement@CAchievement@@QAEXHHH_NM@Z", [0, au.POPUP[2] * -1, 0x5F, 1, 1.0], ecx=ach)
    tiles = [d for d in draws if d[0] == "draw"]
    assert ue.as_layers(files, tiles) == ue.art_layers(arts["ui/dialog/achievement-popup"])


# ------------------------------------------------------------------ message boxes and the play screen
def _message_rig(title_size, body_h):
    import vf2_ui_emu as ue
    rig = _rig(["theMessageBoxDlg", "ldwButton", "ldwTiledBackground"])
    e = rig.e
    for name, value in ue.static_writes(OBJ_DIR, "theGame", "?Init@theGame@@UAE_NXZ").items():
        if "mShadow" in name:
            e.w32(ue.static_address(e, name), value)
    dialog = e.alloc(0x200)
    seen = {"controls": []}

    def bounds(em):
        r = em.arg(0)
        for k in range(4):
            em.w32(r + 4 * k, em.r32(dialog + 0x14 + 4 * k))
        return 0, 4

    title_vt = rig.vtable_object(8, {2: lambda em: (
        [em.w32(em.arg(0) + 4 * k, v) for k, v in enumerate((0, 0, *title_size))], (0, 4))[1]})

    def text_ctor(em):
        em.w32(em.ecx, em.r32(title_vt))
        return em.ecx, 28

    def tiling(em):
        seen["tiling"] = (rig.objects[em.arg(0)], em.sarg(1), em.sarg(2))
        for k, v in enumerate((0, 0, em.sarg(1), em.sarg(2))):
            em.w32(dialog + 0x14 + 4 * k, v)
        return 0, 12

    e.seam("??0ldwTextControl@@QAE@PAVldwScene@@UldwPoint@@PBDHPAVldwFont@@M@Z", text_ctor)
    e.seam("?SetColors@ldwTextControl@@QAEXUldwColor@@0@Z", lambda em: (0, 8))
    e.seam("?SetPos@ldwTextControl@@QAEXHH_N@Z", lambda em: (0, 12))
    e.seam("?GetWidth@ldwFont@@QAEHPBDM@Z", lambda em: (0, 8))
    e.seam("?GetHeight@ldwFont@@QAEHPBD@Z", lambda em: (0, 4))
    e.seam("?DrawStringJustified@ldwGameWindow@@QAEHPBDHHHUldwColor@@PAVldwFont@@_N3H@Z", lambda em: (body_h, 36))
    e.seam("?SetTiling@ldwTiledDialog@@IAEXPAVldwImageGrid@@HH@Z", tiling)
    e.seam("?AddControl@ldwScene@@IAEXPAVldwControl@@@Z", lambda em: (seen["controls"].append(em.arg(0)), (0, 4))[1])
    e.seam("?GetBounds@ldwScene@@QAEXAAUldwRect@@@Z", bounds)
    e.seam("?GetTextColorForCanvas@theGraphicsManager@@QAE?AUldwColor@@H@Z", lambda em: (em.arg(0), 8))
    e.seam("?GetImageGridForCanvas@theGraphicsManager@@QAEPAVldwImageGrid@@H@Z",
           lambda em: (rig.picture({1: 352, 2: 350}.get(em.arg(0), 351)), 4))
    return rig, dialog, seen


def _message_draws(rig, dialog, seen, title, image, canvas):
    e = rig.e
    e.call("?Init@theMessageBoxDlg@@IAEXPBDW4EImage@@0H@Z",
           [e.string("Title") if title else 0, image or 0, e.string("Text"), canvas], ecx=dialog)
    grid, w, h = seen["tiling"]
    bg = e.alloc(0x40)
    e.call("??0ldwTiledBackground@@QAE@PAVldwImageGrid@@HH@Z", [rig.picture(grid), w, h], ecx=bg)
    draws = rig.run("?Draw@ldwTiledBackground@@UAEXUldwPoint@@M@Z", [0, 0, 1.0], ecx=bg)
    draws += rig.run("?DrawNoFadeScene@theMessageBoxDlg@@MAEXXZ", ecx=dialog)
    button = seen["controls"][-1]
    e.write(e.r32(button + 0x10) + 0x28, b"\x01")                    # shown (SetActive)
    draws += rig.run("?Draw@ldwButton@@UAEXXZ", ecx=button)
    return draws


@needs_code
def test_the_message_boxes_are_the_games(files, arts):
    import vf2_ui_emu as ue
    for image, name in au.LIFE_EVENTS:
        rig, dialog, seen = _message_rig(au.EXAMPLE_TITLE, au.EXAMPLE_BODY_H)
        draws = _message_draws(rig, dialog, seen, True, image, 0)
        assert ue.as_layers(files, draws) == ue.art_layers(arts[f"ui/message/{name}"]), name
    rig, dialog, seen = _message_rig((0, 0), au.EMAIL_BODY_H)
    draws = _message_draws(rig, dialog, seen, False, None, 1)
    assert ue.as_layers(files, draws) == ue.art_layers(arts["ui/message/email"])
    # other sizes follow the same rule
    for title, body_h, image in (((90, 20), 0, None), ((700, 44), 200, 610), ((300, 30), 15, 612),
                                  ((450, 30), 20, 611)):
        rig, dialog, seen = _message_rig(title, body_h)
        draws = _message_draws(rig, dialog, seen, True, image, 2)
        want = au.message_box_layers(files, 350, image, title, body_h)
        assert ue.as_layers(files, draws) == ue.art_layers(gp.Art("x", "x", "x", want, True, "")), (title, body_h)


@needs_code
def test_the_play_screen_frame_is_the_games(files, arts):
    import vf2_ui_emu as ue
    stores = ue.image_stores(OBJ_DIR, "theMainScene", "??0theMainScene@@AAE@XZ")
    assert stores[0xC0] == au.BOTTOM_BAR and stores[0xC4] == au.TRAY
    assert stores[0xC8] == 2 and stores[0xCC] == 1                    # the two mouse pointers
    rig = ue.UiRig(OBJ_DIR, GAME_DIR, ["theMainScene"])
    e = rig.e
    e.seam("?DrawMoney@CMoney@@QAEXUldwPoint@@HUldwColor@@PAVldwFont@@PADH@Z", lambda em: (0, 28))
    e.seam("?Draw@CToolTray@@QAEXXZ", lambda em: (0, 0))
    scene = e.alloc(0x400)
    for off, v in ((0x10, rig.window), (0x14, rig.state), (0x1C, rig.strings), (0xC0, rig.picture(au.BOTTOM_BAR)),
                   (0xC4, rig.picture(au.TRAY)), (0x8C, 0), (0x94, 768), (0xA8, 0)):
        e.w32(scene + off, v)
    e.w32(rig.state + 0x25CC4, 0xFFFFFFFF)                             # no family member chosen
    for flag, key in ((0, "frame"), (1, "frame-lowered")):
        e.write(rig.state + 0x25CE0, bytes((flag,)))
        draws = rig.run("?DrawUI@theMainScene@@IAEXXZ", ecx=scene)
        assert ue.as_layers(files, draws) == ue.art_layers(arts[f"ui/play-screen/{key}"]), key
