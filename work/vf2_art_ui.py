"""The Picture Maker's interface pictures for Virtual Families 2: the buttons in every state the game draws, the
check boxes, the Options dialog's choices and sliders, and the dialog backdrops built from their nine tiles at the
sizes the game opens them -- each drawn as the game draws it.

How the game draws them (the B200 desktop objects, work/desktop_obj_files; tests/test_art_ui.py runs every function
named here in Unicorn and compares the draws):

* Buttons (ldwButton, made by ldwButton(id, ldwImageGrid*, point, scene, bool) from a strip of three cells):
  ldwButton::Draw picks by the state ldwButtonImpl +0x30 that HandleMouse keeps: 0 DrawUpState, 1 DrawOverState,
  2 DrawDownState, which call ldwButtonImpl::Draw(0 / 1 / 2): ldwGameWindow::Draw(grid, x, y, cell) -- cell 0
  normal, 1 mouse over, 2 pressed (HandleMouse sets 1 while the pointer is over it, 2 while it is also held
  down). A button not shown (+0x28) draws nothing. A disabled button (+0x29 = 0) would be drawn tinted
  (DrawTinted, cell 0), but the constructor sets +0x29 to 1 and nothing calls ldwButton::Enable or
  SetDisabledTint, so no button is ever drawn greyed out. The label is text (pressed: 2 pixels lower and right).
* Check boxes (ldwRadioButton, a strip of two cells): ldwRadioButton::Draw draws cell min(mouse state, columns/2
  - 1) + (ticked ? columns/2 : 0): with CheckboxStrip.png's two cells, cell 0 unticked and cell 1 ticked, whatever
  the mouse does.
* The Options dialog (theOptionsDialog::DrawNoFadeScene) draws its own choices as two pictures side by side,
  radioselected.png on the chosen one and radioblank.png on the other, at (dialog + 240, row) and (dialog + 328,
  row), and its two volume sliders: WideSlider2.png at (dialog + 240, dialog + 60 / + 100) and sliderhandle.png at
  (dialog + 244 + offset, the same row), the offset 0 to 267 pixels (HandleMouse: dragging clamps it to 0..267;
  a volume v sets it to (int)(v x 263.0)).
* Dialog backdrops (ldwTiledBackground, made by ldwTiledDialog::SetTiling(grid, width, height)): 64 x 64 tiles
  of a nine-cell sheet, never stretched: columns = max(2, (width - 1 + 64 + 12) / 64), rows = max(2, (height - 1
  + 64 + 18) / 64) (the shadow sizes mShadowRightWidth 12 and mShadowBottomHeight 18 set by theGame::Init); Draw
  draws the top row cells 8, 1 ..., 0, each middle row 3, 7 ..., 2, the bottom row 5, 4 ..., 6.
  theGraphicsManager::GetImageGridForCanvas picks the sheet: canvas 1 the e-mail grid (352), 2 orange (350), any
  other orange (351, the same file). A dialog fades in and is then drawn fully opaque, at 70% when its +0xC is set
  (ldwTiledDialog::DrawScene); the pictures show it fully faded in.

USAGE / CELL_LABELS / CELL_UNUSED cover this area's image numbers. Interface text (button labels, dialog words) is
not part of the pictures: the game writes it with its fonts.
"""
from __future__ import annotations

import vf2_game_pictures as gp
from vf2_game_pictures import Art, Draw

TITLE = "Interface"

BTN = "Buttons and controls/Buttons"
TOGGLE = "Buttons and controls/Check boxes and choices"
SLIDE = "Buttons and controls/Sliders"
DLG = "Dialogs and panels/Dialog backdrops"

EMU_BUTTON = "Checked against the game's own ldwButton constructor and ldwButton::Draw run in Unicorn."
EMU_CHECK = "Checked against the game's own ldwRadioButton constructor and ldwRadioButton::Draw run in Unicorn."
EMU_OPTIONS = "Checked against the game's own theOptionsDialog::DrawNoFadeScene run in Unicorn."
EMU_TILES = ("Checked against the game's own ldwTiledBackground constructor and ldwTiledBackground::Draw run in "
             "Unicorn.")
EMU_MESSAGE = ("Checked against the game's own theMessageBoxDlg::Init and DrawNoFadeScene, ldwButton and "
               "ldwTiledBackground run in Unicorn.")
EMU_PLAY = "Checked against the game's own theMainScene::DrawUI run in Unicorn."
EMU_POPUP ="Checked against the game's own CAchievement::DrawAchievement and ldwTiledBackground run in Unicorn."

STATES = ((0, "normal", "Normal"), (1, "over", "Mouse over"), (2, "pressed", "Pressed"))

# image id: (label, where the game makes its buttons)
BUTTONS = {
    297: ("Orange button", "the Awards, adoption, collection, family tree, help, main, main menu, store, story and "
                           "Details screens"),
    296: ("Green button", "the dialogs (bank, community event, diagnosis, family tree info, island event, redeem "
                          "credit, change player, nickname, message boxes, Options, purchase, tips), the story "
                          "and the main screen"),
    298: ("Red button", "the dating screen and the redeem credit, change player, nickname, message box and purchase "
                        "dialogs"),
    295: ("Blue button", "the family tree screen and the main menu"),
    304: ("Purple button", "the main screen"),
    301: ("Big orange button", "the bank and purchase dialogs and the main menu"),
    302: ("Long green button", "the main menu"),
    293: ("Ultra wide button", "the island event and community event dialogs' choices"),
    299: ("Invisible bank button", "the main screen and the store (a see-through area over the bank)"),
    28: ("Invisible portrait button", "the main screen (a see-through area over a portrait)"),
    313: ("Close window button", "the game menu dialog"),
    314: ("Game menu button", "the game menu dialog's eight choices"),
    353: ("Details left arrow button", "the Details screen"),
    354: ("Details right arrow button", "the Details screen"),
    622: ("Up arrow button", "only the villager alignment scene (theAlignVillagerScene, made while the game loads; "
                            "whether the game ever shows that scene was not traced)"),
    623: ("Down arrow button", "only the villager alignment scene (theAlignVillagerScene, made while the game loads; "
                              "whether the game ever shows that scene was not traced)"),
}

CHECKBOX, RADIO_BLANK, RADIO_SELECTED, SLIDER, HANDLE = 357, 355, 356, 359, 360
SLIDER_AT = (0xF0, 0x3C)                      # dialog + 240, + 60 (the second slider + 100)
HANDLE_DX = 0xF4                              # dialog + 244 + offset
HANDLE_MAX = 0x10B                            # 267: HandleMouse clamps the offset to 0..267
HANDLE_SCALE = 263.0                          # a volume v sets (int)(v * 263.0)
SLIDER_LEVELS = ((0, "at 0"), (65, "at a quarter"), (131, "at half"), (197, "at three quarters"),
                 (263, "full (as a full volume sets it)"), (267, "dragged to the end"))
CHOICE_AT = (0xF0, 0x148)                     # the two pictures of a choice: dialog x + 240 and + 328

TILE, SHADOW_RIGHT, SHADOW_BOTTOM = 64, 12, 18
GRIDS = {350: "Orange", 351: "Orange", 352: "E-mail"}
TILE_CELLS = {0: "Top right corner", 1: "Top edge", 2: "Right edge", 3: "Left edge", 4: "Bottom edge",
              5: "Bottom left corner", 6: "Bottom right corner", 7: "Middle", 8: "Top left corner"}

# (key, label, grid, width, height, where)
DIALOGS = (
    ("options", "Options dialog (640 x 498)", 351, 640, 498,
     "theOptionsDialog's constructor (SetTiling, canvas 0 from the game menu)"),
    ("game-menu", "Game menu dialog (640 x 448)", 351, 640, 448,
     "theGameMenuDialog's constructor (canvas 0 from the main screen)"),
    ("nickname", "Nickname dialog (360 x 200)", 351, 360, 200, "theCreateNickNameDlg's constructor (canvas 0)"),
    ("change-player", "Change player dialog (455 x 400)", 351, 455, 400, "theChangePlayerDlg's constructor"),
    ("family-info", "Family tree info dialog (710 x 250)", 351, 710, 250, "CFamilyTreeInfoDlg's constructor (canvas 0)"),
    ("banking", "Bank dialog (560 x 440)", 350, 560, 440, "CBankingDlg's constructor"),
    ("diagnosis", "Diagnosis dialog (600 x 340)", 351, 600, 340, "theDiagnosisDialog's constructor"),
    ("redeem", "Redeem credit dialog (400 x 280)", 351, 400, 280, "RedeemCreditDlg's constructor"),
    ("purchase", "Purchase dialog (600 x 400)", 351, 600, 400, "thePurchaseDialog's constructor"),
    ("island-orange", "Island event dialog (704 wide; the height follows the text, shown 256)", 350, 704, 256,
     "CIslandEventDialog's constructor (canvas 2)"),
    ("island-email", "Island event e-mail (704 wide; the height follows the text, shown 256)", 352, 704, 256,
     "CIslandEventDialog's constructor (canvas 1, an e-mail)"),
    ("community-orange", "Community event dialog (512 wide; the height follows the text, shown 256)", 350, 512,
     256, "CCommunityEventDialog's constructor (canvas 2)"),
    ("community-email", "Community event e-mail (512 wide; the height follows the text, shown 384)", 352, 512, 384,
     "CCommunityEventDialog's constructor (canvas 1, an e-mail)"),
)
POPUP = (899, 60, -24)                        # CAchievement::DrawAchievement's pop-up: 899 x 60 at (x, y - 24)
POPUP_ALPHA = gp.pi.f32(gp.pi.f32(1.0) * gp.pi.f32(0.7))


# ------------------------------------------------------------------ the game's rules
def button_layers(files: gp.GameFiles, image: int, state: int) -> tuple:
    """ldwButtonImpl::Draw(state) for a shown, enabled button at (0, 0): the strip's cell `state`."""
    return (gp.cell(files, image, state, 0, 0),)


def checkbox_cell(columns: int, mouse: int, ticked: bool) -> int:
    """ldwRadioButton::Draw's cell."""
    half = columns // 2
    return min(mouse, half - 1) + (half if ticked else 0)


def tile_grid(width: int, height: int) -> tuple:
    """ldwTiledBackground::SetInteriorSize: (columns, rows)."""
    cols = (width - 1 + TILE + SHADOW_RIGHT) // TILE
    rows = (height - 1 + TILE + SHADOW_BOTTOM) // TILE
    return max(cols, 2), max(rows, 2)


def tiled_draws(width: int, height: int, x: int = 0, y: int = 0) -> list:
    """ldwTiledBackground::Draw's (cell, x, y) in order for a backdrop of width x height."""
    cols, rows = tile_grid(width, height)
    out = []
    for r in range(rows):
        left, mid, right = (8, 1, 0) if r == 0 else (5, 4, 6) if r == rows - 1 else (3, 7, 2)
        ty = y + r * TILE
        out.append((left, x, ty))
        out.extend((mid, x + (k + 1) * TILE, ty) for k in range(cols - 2))
        out.append((right, x + (cols - 1) * TILE, ty))
    return out


def tiled_backdrop(files: gp.GameFiles, grid: int, width: int, height: int, x: int = 0, y: int = 0,
                   alpha: float = 1.0) -> tuple:
    return tuple(gp.cell(files, grid, cell, tx, ty, alpha=alpha) for cell, tx, ty in tiled_draws(width, height, x, y))


def slider_layers(files: gp.GameFiles, offset: int) -> tuple:
    """The volume slider for a dialog at (0, 0): the track, then the handle `offset` pixels along."""
    return (gp.cell(files, SLIDER, 0, *SLIDER_AT), gp.cell(files, HANDLE, 0, HANDLE_DX + offset, SLIDER_AT[1]))


def choice_layers(files: gp.GameFiles, left_chosen: bool, row: int = 0) -> tuple:
    """One of the Options dialog's choices for a dialog at (0, 0): the left picture, then the right one."""
    return (gp.cell(files, RADIO_SELECTED if left_chosen else RADIO_BLANK, 0, CHOICE_AT[0], row),
            gp.cell(files, RADIO_BLANK if left_chosen else RADIO_SELECTED, 0, CHOICE_AT[1], row))


# ------------------------------------------------------------------ the catalogue
def _button_arts(files: gp.GameFiles) -> list[Art]:
    arts = []
    for image, (label, where) in BUTTONS.items():
        for state, key, words in STATES:
            arts.append(Art(
                f"ui/button/{image}/{key}", BTN, f"{label}, {words.lower()}", button_layers(files, image, state),
                True,
                f"{gp.entry_by_id(image).name} cell {state}: ldwButton draws it while the button is "
                f"{('not touched' if state == 0 else 'under the mouse pointer' if state == 1 else 'held down')}. "
                f"Made into buttons by {where}. No button is ever drawn disabled (nothing calls ldwButton::Enable). "
                "The label on it is text the game writes.", EMU_BUTTON))
    return arts


def _toggle_arts(files: gp.GameFiles) -> list[Art]:
    arts = []
    for ticked in (False, True):
        cell = checkbox_cell(2, 0, ticked)
        arts.append(Art(
            f"ui/checkbox/{'ticked' if ticked else 'unticked'}", TOGGLE,
            f"Check box, {'ticked' if ticked else 'not ticked'}", (gp.cell(files, CHECKBOX, cell),), True,
            f"CheckboxStrip.png cell {cell}, drawn by ldwRadioButton for the Options dialog's four check boxes "
            "(and the villager alignment scene's two); the mouse does not change it. The words beside it are text.",
            EMU_CHECK))
    for left in (True, False):
        arts.append(Art(
            f"ui/choice/{'left' if left else 'right'}", TOGGLE,
            f"Options dialog choice, {'left' if left else 'right'} chosen", choice_layers(files, left), True,
            "theOptionsDialog::DrawNoFadeScene draws each of its choices as two pictures 88 pixels apart: "
            "radioselected.png on the chosen side, radioblank.png on the other. The words beside them are text. "
            "One of its rows (full screen or window) is drawn 5 pixels lower when the right-hand picture is the "
            "chosen one (y + 250 against y + 245).", EMU_OPTIONS))
    return arts


def _slider_arts(files: gp.GameFiles) -> list[Art]:
    return [Art(
        f"ui/slider/{offset}", SLIDE, f"Volume slider, {words}", slider_layers(files, offset), True,
        "One of the Options dialog's two volume sliders (theOptionsDialog::DrawNoFadeScene): WideSlider2.png, then "
        f"sliderhandle.png {offset} pixels along. Dragging moves the handle 0 to 267 pixels; a volume sets it to "
        "(int)(volume x 263), so 263 is the end a full volume shows.", EMU_OPTIONS) for offset, words in SLIDER_LEVELS]


def _dialog_arts(files: gp.GameFiles) -> list[Art]:
    arts = []
    for key, label, grid, w, h, where in DIALOGS:
        cols, rows = tile_grid(w, h)
        arts.append(Art(
            f"ui/dialog/{key}", DLG, label, tiled_backdrop(files, grid, w, h), True,
            f"The backdrop {where} sets: {GRIDS[grid].lower()} tiles ({gp.entry_by_id(grid).name}), {cols} x {rows} "
            "tiles of 64 pixels (the width and height plus the 12 and 18 pixel shadow, rounded up). Shown fully "
            "faded in. The dialog's words, pictures and buttons are drawn on top of it.", EMU_TILES))
    w, h, _dy = POPUP
    arts.append(Art(
        "ui/dialog/achievement-popup", DLG, "Achievement earned pop-up (899 x 60)",
        tiled_backdrop(files, 351, w, h, alpha=POPUP_ALPHA), True,
        "The pop-up CAchievement::DrawAchievement shows when an achievement is earned: orange tiles 899 x 60, drawn "
        "at 70% of its fade (shown here fully faded in: 70%). Its words are text. The see-through pixels are the "
        "Picture Maker's fade (each alpha times 0.7); on the screen the game's own blend can differ from it by 1 "
        "in a few pixels.", EMU_POPUP))
    return arts


# ------------------------------------------------------------------ message boxes
OK_BUTTON = 296                               # btn_green: the message box's OK button
LIFE_EVENTS = ((610, "wedding"), (611, "birth"), (612, "college"), (613, "promotion"), (614, "death"))
EXAMPLE_TITLE = (400, 30)                     # an example title: one line, 400 pixels wide
EXAMPLE_BODY_H = 60                           # an example message: 3 lines
EMAIL_BODY_H = 120


def message_box_geometry(files: gp.GameFiles, image: int | None, title: tuple | None, body_h: int) -> dict:
    """theMessageBoxDlg::Init(title, image, text, canvas): the dialog's size, the picture's place and the OK
    button's place (inside the dialog), for a title of `title` (width, height; None: no title) and a message
    `body_h` pixels high (what ldwGameWindow::DrawStringJustified answers)."""
    btn = gp.cell_of(files, OK_BUTTON, 0)[1]
    btn_w, btn_h = btn[2] - btn[0], btn[3] - btn[1]
    title_w, title_h = title if title else (400, 0)
    img_w, img_h = files.size(gp.cell_of(files, image, 0)[0]) if image else (0, 0)
    text_w = img_w if img_w > title_w + 60 else title_w + 60
    width = (btn_w if btn_w + 60 > text_w + 60 else text_w) + 60
    height = body_h + img_h + title_h + btn_h + 100
    return {"size": (width, height), "image": ((width - img_w) // 2, title_h + 40),
            "button": ((width - btn_w) // 2, height - btn_h - 20)}


def message_box_layers(files: gp.GameFiles, grid: int, image: int | None, title: tuple | None,
                       body_h: int) -> tuple:
    """The backdrop (ldwTiledDialog), the picture (theMessageBoxDlg::DrawNoFadeScene), then the OK button
    (ldwButton, normal), for a dialog at (0, 0)."""
    g = message_box_geometry(files, image, title, body_h)
    layers = list(tiled_backdrop(files, grid, *g["size"]))
    if image:
        layers.append(gp.cell(files, image, 0, *g["image"]))
    layers.append(gp.cell(files, OK_BUTTON, 0, *g["button"]))
    return tuple(layers)


def _message_arts(files: gp.GameFiles) -> list[Art]:
    arts = []
    for image, name in LIFE_EVENTS:
        w, h = message_box_geometry(files, image, EXAMPLE_TITLE, EXAMPLE_BODY_H)["size"]
        arts.append(Art(
            f"ui/message/{name}", "Dialogs and panels/Message boxes", f"Life event message: {name} ({w} x {h})",
            message_box_layers(files, 351, image, EXAMPLE_TITLE, EXAMPLE_BODY_H), True,
            f"A message box with a picture (ShowMessageBox with a picture, canvas 0, as CLifeEvent::Show opens "
            f"them): orange tiles, {gp.cell_of(files, image, 0)[0]} centred under the title, the message, then "
            "the green OK button (theMessageBoxDlg::Init and DrawNoFadeScene). Its size follows the words: shown "
            "for an example title one line (30 pixels) high and 400 wide and a message 3 lines (60 pixels) high. "
            "The title, the message and the button's label are text.", EMU_MESSAGE))
    w, h = message_box_geometry(files, None, None, EMAIL_BODY_H)["size"]
    arts.append(Art(
        "ui/message/email", "Dialogs and panels/Message boxes", f"E-mail message ({w} x {h})",
        message_box_layers(files, 352, None, None, EMAIL_BODY_H), True,
        "The message box the daily e-mail and the college kid's e-mail open (CDailyEmail::Show, "
        "CCollegeKidEmail::Show: ShowMessageBox with no title and no picture, canvas 1): e-mail tiles, the message, "
        "then the green OK button. Its height follows the words: shown for an example message 120 pixels high. "
        "The words are text.", EMU_MESSAGE))
    return arts


# ------------------------------------------------------------------ the play screen
TRAY, BOTTOM_BAR = 629, 372
SCREEN_H = 768


def play_screen_layers(files: gp.GameFiles, lowered: bool = False) -> tuple:
    """theMainScene::DrawUI's pictures: mainToolTray_ws.png at (0, -6) ((0, 0) when the game state's +0x25CE0 is
    set),
    then main_BG_ws.png along the bottom (the scene's height less its own)."""
    bar_h = files.size(gp.cell_of(files, BOTTOM_BAR, 0)[0])[1]
    return (gp.cell(files, TRAY, 0, 0, 0 if lowered else -6), gp.cell(files, BOTTOM_BAR, 0, 0, SCREEN_H - bar_h))


def _play_arts(files: gp.GameFiles) -> list[Art]:
    why = ("The play screen's interface frame as theMainScene::DrawUI draws it: the tool tray mainToolTray_ws.png "
           "down the left side (its top 6 pixels above the screen), then the bottom panel main_BG_ws.png. On top of them the game then draws the money "
           "(its amount as text, its icon by CMoney::DrawMoney beside the text), the chosen family member's "
           "portrait, the tools in the tray (CToolTray::Draw: inventory pictures) and the screen's buttons; those "
           "are left out.")
    return [
        Art("ui/play-screen/frame", "Dialogs and panels/Play screen", "Play screen tool tray and bottom panel",
            play_screen_layers(files), True, why, EMU_PLAY),
        Art("ui/play-screen/frame-lowered", "Dialogs and panels/Play screen",
            "Play screen tool tray and bottom panel (tray 6 pixels lower)", play_screen_layers(files, True), True,
            why + " When the game state's flag +0x25CE0 is set (the flag that also makes the Details screen fill "
            "its background black first) the tray is drawn at the top of the screen instead of 6 pixels above "
            "it.", EMU_PLAY),
    ]


# ------------------------------------------------------------------ tips (theTipDialog)
TIPS = "Dialogs and panels/Tips"
TIP_GRID = 351                                # GetImageGridForCanvas(0): orange tiles
TIP_BUTTON = 296                              # btn_green.png, the OK button (button id 2)
ARROWS = {1: (376, "up"), 2: (377, "down"), 3: (378, "left"), 4: (379, "right")}   # ArrowDirection -> image
ARROWS_USED = (1, 2, 3)                       # no code configures a tip with direction 4
GAME_PI = 3.14159                             # __real@400921f9f01b866e: the game's own (short) pi
BOB_START = -360.0                            # the constructor's first phase (__real@c076800000000000)
BOB_FARTHEST = 0.0                            # a phase (reached: it steps 5 or 8 degrees a frame) where the bob is
BOB_NEAREST = 90.0                            # largest, and where it is smallest (cos(sin(phase)) is cos 1)
EXAMPLE_TIP = (400, 60, 20)                   # an example tip: text 400 pixels wide, 3 lines of 20 pixels
SCREEN_W = 1024                               # ldwGameWindow::GetWidth and the world view's width (an example)
EMU_TIP = ("Checked against the game's own theTipDialog::Init and DrawNoFadeScene, ldwButton and "
           "ldwTiledBackground run in Unicorn.")
EMU_ARROW = ("Checked against the game's own theTipDialog::Init and DrawNoFadeScene run in Unicorn (sin and cos "
             "answered by Python's).")


def tip_geometry(files: gp.GameFiles, text_w: int, body_h: int, line_h: int, instruction: bool = False,
                 window_w: int = SCREEN_W, world_w: int = SCREEN_W) -> dict:
    """theTipDialog::Init: the box's size and the OK button's place in it. `text_w` is the font's width of the
    text (one line), `body_h` its justified height, `line_h` one line's height. An instruction tip (string ids
    0x845..0x86D on the play screen) is as wide as the world view and drawn at the top of it, 26 pixels shorter."""
    btn = gp.cell_of(files, TIP_BUTTON, 0)[1]
    btn_w, btn_h = btn[2] - btn[0], btn[3] - btn[1]
    cap = (window_w // TILE) * TILE - SHADOW_RIGHT - 0x48
    width = min(text_w, cap)
    if instruction:
        width = (world_w // TILE) * TILE - SHADOW_RIGHT - 0x48
        body_h = body_h - line_h if body_h // line_h > 3 else 2 * line_h
    height = body_h + 0x24 + 2 * btn_h - (0x1A if instruction else 0)
    w = width + 0x48
    return {"size": (w, height), "button": ((w - btn_w) // 2, height - btn_h // 2 - btn_h)}


def tip_box_layers(files: gp.GameFiles, text_w: int, body_h: int, line_h: int, instruction: bool = False) -> tuple:
    """The box (ldwTiledDialog), then the OK button (ldwButton, normal), for a box at (0, 0)."""
    g = tip_geometry(files, text_w, body_h, line_h, instruction)
    return tiled_backdrop(files, TIP_GRID, *g["size"]) + (gp.cell(files, TIP_BUTTON, 0, *g["button"]),)


def tip_bob(amount: int, phase: float) -> int:
    """DrawNoFadeScene's bob: (int)(cos(sin(phase x pi / 180)) x amount), pi being the game's 3.14159."""
    import math
    return int(math.cos(math.sin(phase * GAME_PI / 180.0)) * amount)


def arrow_place(files: gp.GameFiles, direction: int, phase: float) -> tuple:
    """Where theTipDialog draws its arrow for a tip pointing at (0, 0): Init places the picture against the point
    (below it, above it, right of it, left of it) and DrawNoFadeScene moves it away from the point by the bob,
    a quarter of the picture's height (up and down arrows) or width."""
    image, _way = ARROWS[direction]
    w, h = files.size(gp.cell_of(files, image, 0)[0])
    if direction == 1:
        return -(w // 2), tip_bob(h // 4, phase)
    if direction == 2:
        return -(w // 2), -h - tip_bob(h // 4, phase)
    if direction == 3:
        return tip_bob(w // 4, phase), -(h // 2)
    return -w - tip_bob(w // 4, phase), -(h // 2)


def _tip_arts(files: gp.GameFiles) -> list[Art]:
    text_w, body_h, line_h = EXAMPLE_TIP
    out = []
    w, h = tip_geometry(files, text_w, body_h, line_h)["size"]
    out.append(Art(
        "ui/tip/box", TIPS, f"Tip box ({w} x {h})", tip_box_layers(files, text_w, body_h, line_h), True,
        "A tip (theTipDialog, opened by CTutorialTip::Display for the tutorial and the game's hints, and by the "
        "family tree screen): orange tiles as wide as its text plus 72 pixels and as high as its text plus 36 "
        "and twice the green OK button, the button centred at the bottom. Shown for an example text 400 pixels "
        "wide and 3 lines (60 pixels) high. The words and the button's label are text. Its arrow, when it has "
        "one, is drawn on its own beside the thing it points at (below).", EMU_TIP))
    w, h = tip_geometry(files, text_w, body_h, line_h, True)["size"]
    out.append(Art(
        "ui/tip/instruction", TIPS, f"Tutorial instruction tip ({w} x {h})",
        tip_box_layers(files, text_w, body_h, line_h, True), True,
        "A tutorial instruction (string ids 0x845 to 0x86D) shown on the play screen: theTipDialog::Init makes it "
        "as wide as the world view less 84 pixels (here for a 1024 pixel wide view) and puts it at the top; up to "
        "3 lines of text make it two lines high, and it is 26 pixels shorter than other tips. The words and the "
        "button's label are text.", EMU_TIP))
    for direction, (image, way) in ARROWS.items():
        used = direction in ARROWS_USED
        name = gp.cell_of(files, image, 0)[0]
        for phase, key, words in ((BOB_FARTHEST, "far", "farthest from the point"),
                                  (BOB_NEAREST, "near", "nearest to the point")):
            x, y = arrow_place(files, direction, phase)
            why = (f"{name}: theTipDialog::Init picks it for arrow direction {direction} and places it against the "
                   "point the tip shows; DrawNoFadeScene draws it there moved away from the point by a bob that "
                   "swings between about half and all of a quarter of the picture's "
                   f"{'height' if direction < 3 else 'width'} (shown {words}, the point being (0, 0)). ")
            if used:
                why += ("The tutorial tips (CTutorialTip::Reset), the adoption and store tips and the family tree "
                        "tips use directions 1 to 3. The blockage tip (CTutorialTip::ConfigBlockageTip) hands its "
                        "left arrow to CDecal::ShowArrow instead, which draws it in the world.")
            else:
                why += ("But no tip ever has direction 4: every CTutorialTip::ConfigureTip call (CTutorialTip::Reset, "
                        "ConfigBlockageTip, CAdoptionScene::HandleMessage, theGameState::Load) and the family tree "
                        "screen's own tip pass directions 1 to 3 (and Reset clears the rest to 0, no arrow), so "
                        "the right arrow is never drawn.")
            out.append(Art(f"ui/tip/arrow/{way}/{key}", TIPS, f"Tip arrow pointing {way}, {words}",
                           (gp.cell(files, image, 0, x, y),), used, why, EMU_ARROW))
    return out


# ------------------------------------------------------------------ mouse pointers and the selected villager ring
CURSORS = "Icons and cursors/Mouse pointers"
ICONS = "Icons and cursors/Icons"
HOT_SPOT = (21, 24)                           # UI_HandCursorHotSpot
FOCUS_RING = 364                              # focus_circle.png (CVillagerManager +0x20)
FOCUS_AT = (-19, 11)                          # where DrawVillager puts it for a grown man standing, from his place
EMU_FOCUS = ("Checked against the game's own CVillagerManager::DrawVillager run in Unicorn (a grown man, standing, "
             "at 100% zoom).")
EMU_CURSOR = ("Checked against the game's own ldwGameWindow::SetCursor and ldwGameWindowImpl::Update (which draws "
              "the pointer) run in Unicorn.")


def _pointer_arts(files: gp.GameFiles) -> list[Art]:
    out = []
    for image, key, label, why in (
            (1, "open", "Mouse pointer, open hand",
             "The game's mouse pointer: theMainScene's constructor and HandleMouseUp set it "
             "(ldwGameWindow::SetCursor with the hot spot UI_HandCursorHotSpot, 21 in and 24 down); the game "
             "hides the system pointer and ldwGameWindowImpl::Update draws this picture at the mouse less the hot "
             "spot every frame. Shown with the mouse at (0, 0)."),
            (2, "held", "Mouse pointer, closed hand",
             "The pointer while the mouse button is held down: theMainScene::HandleMouseDown sets it (same hot "
             "spot), and ldwGameWindowImpl::Update draws it at the mouse less the hot spot. Shown with the mouse at "
             "(0, 0).")):
        out.append(Art(f"ui/cursor/{key}", CURSORS, label,
                       (gp.cell(files, image, 0, -HOT_SPOT[0], -HOT_SPOT[1]),), True, why, EMU_CURSOR))
    out.append(Art(
        "ui/icon/focus-ring", ICONS, "Selected villager ring", (gp.cell(files, FOCUS_RING, 0, *FOCUS_AT),), True,
        "focus_circle.png (CVillagerManager::LoadAssets keeps it): CVillagerManager::DrawVillager draws it on the "
        "ground under the villager the player has picked, before the villager. Shown for a grown man standing, "
        "his place being (0, 0); its place moves a little with the villager's size.", EMU_FOCUS))
    return out


def arts(files: gp.GameFiles) -> list[Art]:
    out = []
    for part in (_button_arts, _toggle_arts, _slider_arts, _dialog_arts, _message_arts, _play_arts, _tip_arts,
                 _pointer_arts):
        try:
            out += part(files)
        except (gp.pi.PictureError, KeyError):         # a picture this game folder lacks: that part is left out
            continue
    return out


USAGE: dict = {
    1: (True, "The mouse pointer: theMainScene sets it (ldwGameWindow::SetCursor) when it is made and on mouse up; "
              "ldwGameWindowImpl::Update draws it."),
    2: (True, "The mouse pointer while the button is held: theMainScene::HandleMouseDown sets it; "
              "ldwGameWindowImpl::Update draws it."),
    364: (True, "The selected villager's ring, drawn by CVillagerManager::DrawVillager under the villager."),
    376: (True, "The tips' up arrow (arrow direction 1), drawn by theTipDialog::DrawNoFadeScene."),
    377: (True, "The tips' down arrow (arrow direction 2), drawn by theTipDialog::DrawNoFadeScene."),
    378: (True, "The tips' left arrow (arrow direction 3), drawn by theTipDialog::DrawNoFadeScene (the blockage tip "
                "hands it to CDecal::ShowArrow)."),
    379: (False, "theTipDialog::Init would take it for arrow direction 4, but no tip has direction 4: every "
                 "CTutorialTip::ConfigureTip call and the family tree screen's tip pass 1 to 3, so it is never drawn."),
}

CELL_LABELS = {(image, state): words for image in BUTTONS for state, _k, words in STATES}
CELL_LABELS.update({(CHECKBOX, 0): "Not ticked", (CHECKBOX, 1): "Ticked"})
CELL_LABELS.update({(grid, cell): words for grid in GRIDS for cell, words in TILE_CELLS.items()})

# The mouse pointer (ldwGameWindow::SetCursor, hot spot UI_HandCursorHotSpot (21, 24)): theMainScene sets
# hand_open.png when it is made and on mouse up, hand.png on mouse down; ldwGameWindowImpl::Update draws it.
CELL_LABELS.update({(1, 0): "Mouse pointer (hot spot 21, 24)",
                    (2, 0): "Mouse pointer while the button is held (hot spot 21, 24)"})

CELL_UNUSED: dict = {}
