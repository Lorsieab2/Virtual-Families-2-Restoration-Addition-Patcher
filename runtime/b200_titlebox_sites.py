"""Title Screen Player Name Box: sites in the B200 Virtual Families 2 executable (core variant).

Single source of truth for every address the companion DLL vf2titlebox_b200.dll touches or relies on. Every pin
is the exact bytes of the B200 link output (`Virtual Families 2 - B200.exe`, core variant, built by
work/patch_mobile_furniture_pack.py); the DLL, the generator and the tests refuse an executable that is not that
build at these places.

The B200 image is relocated (DYNAMICBASE, .reloc) and each of the 32 matrix variants links to different
addresses, so the DLL holds no game address. It searches the live image for each pinned run (relocated fields and
call/jmp displacements are wildcards) and derives every address from where the runs were found.
runtime/tools/gen_b200_titlebox_sites.py proves the derivation on the core variant and on every other executable
it is given.

What the DLL does (one write at install, a vtable slot):

* The title screen is theMenuScene. Every frame ldwScene::Draw calls the scene's DrawScene (vtable slot 6, +18h:
  the background picture vf2_boxshot.jpg and the distributor's logo), then DrawControls (every control in the
  scene's list: the buttons, the version and copyright lines, and the current player's name), then DrawSceneFinal
  (slot 7: the floating animation and the butterflies) and the hints.
* The player's name is the ldwTextControl at [scene+0F0h] (control id [scene+0D0h] = 7), made by the
  constructor at (widescreen + 200h, 133h), centred (justify 1), in the window's default font (Segoe32Bold), the
  colour 0xFF804C05 (r 5, g 76, b 128) on no background. UpdateShowPlayer sets its text to the player's name
  (theGameState +25ABCh, while +25B20h, the number of players, is not 0) and adds it to the scene's list, or
  removes it when there is no player.
* The DLL replaces theMenuScene's DrawScene slot (found through RTTI: ".?AVtheMenuScene@@" -> the complete object
  locator at offset 0 -> the one vtable that points to it). Its function first calls the game's own DrawScene,
  then, only while the name control is in the scene's control list and its Draw would draw text, fills the
  rectangle behind the name with the game's own ldwGameWindow::FillRect(rect, colour) in white at alpha 4Dh
  (77/255 = 30%; vf2titlebox.ini Opacity=30, the owner's choice after the first preview). The rectangle is the text's own: x and y exactly as ldwTextControlImpl::Draw places the text,
  the width from the game's own ldwFont::GetWidth(text, scale) and the height from ldwFont::GetHeight(0) times the
  scale, the very calls Draw makes (so a Unicode text DLL that hooks GetWidth sizes the box as it sizes the
  text), plus BOX_PADDING pixels on every side. The controls, the name included, are drawn after it: the box is
  behind the name.
* FillRect's own blend (ldwGameWindowImpl::FillRect with alpha below 1): a = int(alpha * 255 + 0.5) = 77, every
  colour byte of a pixel becomes (old * (255 - a) >> 8) + (255 * a >> 8) = (old * 178 >> 8) + 76.
* The padding is the game's own for a box behind text: the hint (tooltip) box ldwHintControlImpl::Draw draws its
  outer rectangle 8 pixels out from its text rectangle on each side (its SetText keeps the text rectangle, 2
  pixels larger than the text, and Draw grows it by 8), so the box's edge is 8 pixels from where the text's own
  box starts.
"""
from __future__ import annotations

IMAGE_BASE = 0x400000
B200_EXE_NAME = "Virtual Families 2 - B200.exe"

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2titlebox_b200.dll"
INI_NAME = "vf2titlebox.ini"
INI_KEY = "NameBox"
LOG_NAME = "vf2titlebox.log"
STARTUP = "B200TitleBox_Startup"
STATUS_MAGIC = 0x58425454          # 'TTBX' little-endian: T, T, B, X


class Pin:
    """One exact run of the executable (whole instructions of the core variant).

    dll: True = searched for by the DLL (emitted to the header); False = proved here and used by the tests
    only. A relocated 32-bit field and the 32-bit displacement of every call / jmp rel32 are wildcards when
    the run is looked for in another variant.
    """

    def __init__(self, name, va, hexbytes, note, dll=True):
        self.name = name
        self.va = va
        self.bytes = bytes.fromhex(hexbytes)
        self.note = note
        self.dll = dll


# ---- layout (the same in every variant; compiled into the DLL)
DRAW_SCENE_VSLOT = 6                # ldwScene::Draw calls [vtable+18h] first: the scene's DrawScene
NAME_CONTROL_FIELD = 0xF0           # theMenuScene: the player's name, an ldwTextControl
SCENE_IMPL_FIELD = 0x04             # ldwScene -> its impl
SCENE_CONTROLS_FIELD = 0x18         # ldwScene impl: the control list, nodes {control, next}
CONTROL_IMPL_FIELD = 0x10           # ldwTextControl -> its ldwTextControlImpl
TEXT_LEFT = 0x08                    # ldwTextControlImpl: bounds left, top, right
TEXT_TOP = 0x0C
TEXT_RIGHT = 0x10
TEXT_SCENE = 0x18                   # the scene whose bounds offset the text
TEXT_EDITABLE = 0x24                # a text box (Draw may shorten an editable text: never the name)
TEXT_SHOWN = 0x2C                   # Draw draws nothing while this byte is 0
TEXT_COUNT_SET = 0x2F               # 1: the length is TEXT_LENGTH, else strlen(TEXT_STRING)
TEXT_STRING = 0x30
TEXT_LENGTH = 0x34
TEXT_FONT = 0x3C                    # 0: the window's font
TEXT_JUSTIFY = 0x40                 # 0 left, 1 centred, 2 right
TEXT_INSET = 0x44
TEXT_OFFSET_Y = 0x48
TEXT_SCALE = 0x58                   # float
WINDOW_IMPL_FIELD = 0x00            # ldwGameWindow -> its impl (FillRect's own mov ecx, [esi])
BOX_COLOR = 0x4DFFFFFF              # ldwColor r | g << 8 | b << 16 | a << 24: white at alpha 4Dh (the default)
BOX_ALPHA = 0x4D                    # 77 / 255 = 30%
BOX_OPACITY_PERCENT = 30            # vf2titlebox.ini Opacity= (1..100, default 30): alpha = (percent * 255 + 50) / 100
BOX_PADDING = 8                     # pixels on every side (the hint box's own margin)
HINT_TEXT_MARGIN = 2                # ldwHintControlImpl::SetText: the text rectangle is the text +- 2
HINT_BOX_MARGIN = 8                 # ldwHintControlImpl::Draw: the box is the text rectangle +- 8
MENU_CLASS = "theMenuScene"

# ---- core-variant numbers used only to prove things and by the tests
NAME_CONTROL_ID_FIELD = 0xD0        # theMenuScene: the name control's id (7)
NAME_CONTROL_X = 0x200              # the constructor: (widescreen + 200h, 133h), justify 1, font 0, scale 1.0
NAME_CONTROL_Y = 0x133
NAME_JUSTIFY = 1
NAME_COLOR = 0xFF804C05             # r 5, g 76, b 128
GS_PLAYER_COUNT = 0x25B20           # theGameState: players; the name shows only while it is not 0
GS_PLAYER_NAME = 0x25ABC            # the current player's name
BACKGROUND_IMAGE = 0x176            # EImage 374, vf2_boxshot.jpg, drawn by DrawScene
DEFAULT_FONT_INDEX = 2              # theStringManager::LoadFonts: the window's font is Segoe32Bold

# ---- core-variant addresses (the DLL derives these in every variant)
MENU_DRAW_SCENE = 0x4A3F90          # theMenuScene::DrawScene() thiscall, ret
GAME_WINDOW_GET = 0x47C460          # ldwGameWindow::Get() static
SCENE_GET_BOUNDS = 0x47ED70         # ldwScene::GetBounds(ldwRect &) thiscall, ret 4
FILL_RECT = 0x47C050                # ldwGameWindow::FillRect(ldwRect &, ldwColor) thiscall, ret 8
WINDOW_GET_FONT = 0x47C4A0          # ldwGameWindow::GetFont() thiscall
FONT_GET_HEIGHT = 0x474A50          # ldwFont::GetHeight(const char *) thiscall, ret 4
FONT_GET_WIDTH = 0x474D50           # ldwFont::GetWidth(const char *, float) thiscall, ret 8
MENU_VTABLE = 0x500610              # theMenuScene's vtable (found through RTTI by the DLL; checked by the generator)
MENU_SLOT_DRAW_SCENE = MENU_VTABLE + 4 * DRAW_SCENE_VSLOT

# ---- test-only (derived like the others, never given to the DLL)
TEXT_DRAW = 0x47FAC0                # ldwTextControlImpl::Draw() thiscall
TEXT_CONTROL_DRAW = 0x47FAB0        # ldwTextControl::Draw() (vtable): impl->Draw()
DRAW_STRING = 0x47B1A0              # ldwGameWindow::DrawString(text, x, y, colour, font) thiscall, ret 14h
SET_FONT = 0x47C810                 # ldwGameWindow::SetFont(font)
GET_MILLISECONDS = 0x4745C0         # ldwEventManager::GetMilliseconds() (the edit cursor's blink)
FILL_RECT_IMPL = 0x47C0D0           # ldwGameWindowImpl::FillRect(rect, r, g, b, a): the blend
SCENE_DRAW = 0x47ED00               # ldwScene::Draw(): DrawScene (slot 6), DrawControls, DrawSceneFinal (slot 7), DrawHints
SCENE_IS_ACTIVE = 0x47EDC0
DRAW_CONTROLS = 0x47ED30
DRAW_HINTS = 0x47ED50
ADD_CONTROL = 0x47EC70              # ldwScene::AddControl(control): pushes {control, head} at the head
GET_CONTROL = 0x47ED90              # ldwScene::GetControl(id)
OPERATOR_NEW = 0x4CE840             # operator new(size)
TEXT_CONTROL_CTOR = 0x47F750        # ldwTextControl(scene, id, point, text, font, justify, edit, scale)
HINT_CONTROL_CTOR = 0x47C9D0        # ldwHintControl(id): the text control's base
TEXT_IMPL_CTOR = 0x47F8C0           # ldwTextControlImpl's constructor (SetText, SetBoundsFromText(x, y, 0, 0))
TEXT_SET_TEXT = 0x480300            # ldwTextControl::SetText(text)
TEXT_SET_COLORS = 0x480270          # ldwTextControl::SetColors(text colour, background)
GRAPHICS_GET = 0x49AFD0             # theGraphicsManager::Get()
GET_IMAGE_GRID = 0x49B1D0           # theGraphicsManager::GetImageGrid(EImage)
GET_CELL_RECT = 0x47D750            # ldwImageGrid::GetCellRect(cell, rect)
DRAW_CELL = 0x49AE00                # theGraphicsManager::DrawCell(EImage, cell, x, y, scale, alpha)
HAS_MENU_LOGO = 0x455C40            # CDistributor::HasMenuLogo()
UPDATE_SHOW_PLAYER_BODY = 0x4A4643  # theMenuScene::UpdateShowPlayer +13h: GetControl(id), the name copy, SetText
MENU_NAME_CONTROL = 0x4A3E13        # theMenuScene's constructor +7C3h: the name control and its colours
HINT_DRAW_BOX = 0x47CD71            # ldwHintControlImpl::Draw +71h: the hint box, 8 out from the text rectangle
HINT_SET_TEXT_RECT = 0x47D279       # ldwHintControlImpl::SetText +0A9h: the text rectangle, the text +- 2

PINS = [
    Pin(
        "menu_draw_scene", MENU_DRAW_SCENE,
        "558BEC83EC105356578BD9E83070FFFF8BF868760100008BCFE82272FFFF8D4DF00F57C0516A008BC80F1145F0E88E97FDFF"
        "8B4B0C8B75F82B75F08B01FF50186A642BC651998BCFC704240000803F2BC26A00D1F8506A006876010000E80E6EFFFFB964"
        "1A6600E8441CFBFF84C074188B4328B9641A660068F401000005BC02000050E8081CFBFF5F5E5B8BE55DC3",
        "Whole theMenuScene::DrawScene() thiscall, plain ret: the background (EImage 176h, cell 0) centred at the "
        "top, then the distributor's menu logo when it has one. The DLL calls it first, every frame.",
    ),
    Pin(
        "text_draw_body", TEXT_DRAW + 7,
        "8BF1807E2C000F84E901000053E887C9FFFF8B4E188BD8895DF00F57C00F1145C885C974098D45C850E87BF2FFFF807E5300"
        "742E0F1046088B4DC8FF7650660F7EC00F1145D8014DE003C18BCB8945D88B45CC0145DC0145E48D45D850E827C5FFFF578B"
        "CBE86FC9FFFF8B7E3C8945EC897DF485FF751A85C00F847401000085FF750E8BF8C745EC00000000897DF4EB08578BCBE8B0"
        "CCFFFF807E2F0074058B5E34EB0F8B5E308D4B018A034384C075F92BD96A008BCFE8CD4EFFFFF30F104658660F6EC80F5BC9"
        "F30F59C1F30F2CC08945E88B464803460C8B7DE88945FC85DB741DF30F104658518B4DF4F30F110424FF7630E89051FFFF",
        "ldwTextControlImpl::Draw from +7 (after the 7 bytes a Unicode text DLL may replace) to its GetWidth call: "
        "nothing while [esi+2Ch] is 0; ldwGameWindow::Get; the scene's GetBounds; the background FillRect(rect, "
        "colour) when [esi+50h] has alpha; the font [esi+3Ch] or the window's GetFont; the length ([esi+34h] when "
        "[esi+2Fh], else strlen [esi+30h]); the height GetHeight(0) * scale [esi+58h]; the top [esi+48h] + "
        "[esi+0Ch]; the width GetWidth(text, scale). The DLL's helpers are the functions this run calls.",
    ),
    Pin(
        "text_draw", TEXT_DRAW,
        "558BEC83EC38568BF1807E2C000F84E901000053E887C9FFFF8B4E188BD8895DF00F57C00F1145C885C974098D45C850E87B"
        "F2FFFF807E5300742E0F1046088B4DC8FF7650660F7EC00F1145D8014DE003C18BCB8945D88B45CC0145DC0145E48D45D850"
        "E827C5FFFF578BCBE86FC9FFFF8B7E3C8945EC897DF485FF751A85C00F847401000085FF750E8BF8C745EC00000000897DF4"
        "EB08578BCBE8B0CCFFFF807E2F0074058B5E34EB0F8B5E308D4B018A034384C075F92BD96A008BCFE8CD4EFFFFF30F104658"
        "660F6EC80F5BC9F30F59C1F30F2CC08945E88B464803460C8B7DE88945FC85DB741DF30F104658518B4DF4F30F110424FF76"
        "30E89051FFFF8BD08945F8EB0533D28955F88B464083E800742983E801740F83E80175258B7E102B7E442BFAEB1B8B4E088B"
        "46102BC12BC2992BC28BF8D1FF03F9EB068B7E44037E0885DB741E807E240074188B45F803C73B46107E0E8B46304B85C074"
        "87C6041800EB818B4DFC034DCC037DC885DB8B5DF0894DFC74146A00FF764C5157FF76308BCBE857B5FFFF8B4DFC807E2500"
        "7459807E2600742F037DF88D463880380074116A00FF764C5157508BCBE82EB5FFFFEB13FF76548B45E803C1505751578BCB"
        "E809A5FFFFE83449FFFF3B4620761A68FA000000E83549FFFF83C404894620807E26000F94C08846268B45EC85C07408508B"
        "CBE856CBFFFF5F5B5E8BE55DC3",
        "Whole stock ldwTextControlImpl::Draw: the x by the justification (0: inset + left; 1: left + (right - "
        "left - width) / 2; 2: right - inset - width), plus the scene's left; then DrawString(text, x, y, colour "
        "[esi+4Ch], 0). The box's x and y are these.",
        dll=False,
    ),
    Pin(
        "fill_rect_color", FILL_RECT,
        "558BEC8B450C8BD0F30F100DB8454F00C1EA18568BF183EC108BC8660F6EC20F5BC0C1E9100FB6C9F30F5EC1F30F1144240C"
        "660F6EC18BC80F5BC0C1E9080FB6C90FB6C0F30F5EC1F30F11442408660F6EC10F5BC08B0EF30F5EC1F30F11442404660F6E"
        "C00F5BC0F30F5EC1F30F110424FF7508E8070000005E5DC20800",
        "Whole ldwGameWindow::FillRect(ldwRect &, ldwColor) thiscall, ret 8: each byte of the colour (r, g, b, a "
        "from the lowest) divided by 255.0 and passed with the rectangle to ldwGameWindowImpl::FillRect, which "
        "blends with alpha below 1 (the box: 4Dh / 255 = 0.302).",
        dll=False,
    ),
    Pin(
        "scene_draw", SCENE_DRAW,
        "568BF1E8B800000084C0741D8B068BCEFF50188BCEE8160000008B068BCEFF501C8BCE5EE9270000005EC3",
        "Whole ldwScene::Draw(): when IsActive, [vtable+18h] (DrawScene), DrawControls, [vtable+1Ch] "
        "(DrawSceneFinal), DrawHints. The box drawn in DrawScene is under every control.",
        dll=False,
    ),
    Pin(
        "draw_controls_and_hints", DRAW_CONTROLS,
        "568B71048B761885F674130F1F4400008B0E8B01FF50188B760485F675F25EC3568B71048B761885F674130F1F4400008B0E"
        "8B01FF501C8B760485F675F25EC3",
        "ldwScene::DrawControls and DrawHints: the list [[this+4]+18h], nodes {control, next}; each control's "
        "[vtable+18h] (Draw) and [vtable+1Ch] (DrawHint).",
        dll=False,
    ),
    Pin(
        "add_control", ADD_CONTROL,
        "558BEC515356576A088BF9E8C0FB04008B5D088BD083C4048955FC85D2740D8B4F048B4918891A894A04EB0233D28B47048B"
        "CF8950188B33E8130100000FB6C08BCB50FF56145F5E5B8BE55DC20400",
        "Whole ldwScene::AddControl(control): a new node {control, old head} becomes the head of [[this+4]+18h]; "
        "then control->SetActive(IsActive()).",
        dll=False,
    ),
    Pin(
        "text_control_ctor", TEXT_CONTROL_CTOR,
        "558BEC6AFF68F71F4F0064A1000000005083EC0856A100C6590033C5508D45F464A3000000008BF18975F0FF750CE84DD2FF"
        "FF6A5CC745FC00000000C706D0834F00E8A9F0040083C4048945ECC645FC0185C07442F30F10452851F30F1104248BC856FF"
        "7524FF7520FF751CFF7518FF7508FF7514FF7510FF750CE8F00000008946108BC68B4DF464890D00000000595E8BE55DC224"
        "00C74610000000008BC68B4DF464890D00000000595E8BE55DC22400",
        "Whole ldwTextControl(scene, id, point, text, font, justify, edit, scale): the ldwHintControl base, then "
        "new ldwTextControlImpl (5Ch bytes) at [this+10h], which sets the text and SetBoundsFromText(x, y, 0, 0).",
        dll=False,
    ),
    Pin(
        "text_set_colors", TEXT_SET_COLORS,
        "558BEC8B49108B450889414C8B450C8941508B45088941545DC20800",
        "Whole ldwTextControl::SetColors(text, background): [impl+4Ch] text, [impl+50h] background.",
        dll=False,
    ),
    Pin(
        "text_set_text", TEXT_SET_TEXT,
        "558BEC8B49105DE904000000",
        "Whole ldwTextControl::SetText(text): impl->SetText(text) (the impl's own copy).",
        dll=False,
    ),
    Pin(
        "update_show_player_body", UPDATE_SHOW_PLAYER_BODY,
        "FFB3D0000000E842A7FDFF8B530C89459483BA205B020000746C5681C2BC5A0200C6459800578BF20F1F4400008A024284C0"
        "75F98D7D982BD64F0F1F008A47014784C075F88BCA8D4598C1E902F3A58BCA83E103F3A48B8BF000000050E85BBCFDFF",
        "theMenuScene::UpdateShowPlayer +13h (the part every variant keeps; Fix Vanilla Game Bugs detours its "
        "entry and its AddControl): GetControl([this+0D0h]); while theGameState+25B20h is not 0 the name at "
        "+25ABCh is copied and set as the text of [this+0F0h].",
        dll=False,
    ),
    Pin(
        "menu_name_control", MENU_NAME_CONTROL,
        "8B47288D95D0FEFFFF51C704240000803F05000200006A006A016A0052683301000050FFB7D000000057E80EB9FDFFEB0233"
        "C08987F00000008BC8FF35ACFF6F00C785CCFEFFFF054C80FFFFB5CCFEFFFFC645FC00E803C4FDFF",
        "theMenuScene's constructor +7C3h: ldwTextControl(this, [this+0D0h], (widescreen + 200h, 133h), text, "
        "font 0, justify 1, false, 1.0) stored at [this+0F0h], then SetColors(0xFF804C05, no colour).",
        dll=False,
    ),
    Pin(
        "hint_draw_box", HINT_DRAW_BOX,
        "0F1043208B4B340F1145E885C9757D8B45E88BCB83C0F80343448945E88B45F083C0080343448945F08B45EC83C0F8034348"
        "8945EC8B45F483C0080343488945F48D45E85056E824010000FF73648D45E88BCE50E886F2FFFFFF73688345E8028D45E883"
        "6DF0028BCE8345EC02836DF40250E868F2FFFF8345E806836DF0068345EC06836DF406",
        "ldwHintControlImpl::Draw +71h, the game's box behind a text (a hint): the text rectangle [esi+20h..2Ch] "
        "grown by 8 on every side (add -8 / +8) and filled (FillRect), its inside 2 in filled again, the text 6 "
        "further in. The title box's padding is this 8.",
        dll=False,
    ),
    Pin(
        "hint_set_text_rect", HINT_SET_TEXT_RECT,
        "51C704240000803F8BCF53C7462000000000E8C07AFFFF538BCF894628C7462400000000E8AE77FFFF89462C834620FE8346"
        "2802834624FE83462C02",
        "ldwHintControlImpl::SetText +0A9h: the text rectangle is (0, 0, GetWidth, GetHeight) grown by 2 on every "
        "side.",
        dll=False,
    ),
]

# Addresses the DLL derives (in this order: the header's enum).
ADDRESS_CONSTANTS = ("MENU_DRAW_SCENE", "GAME_WINDOW_GET", "SCENE_GET_BOUNDS", "FILL_RECT", "WINDOW_GET_FONT",
                     "FONT_GET_HEIGHT", "FONT_GET_WIDTH")
# Addresses only the tests need.
TEST_ADDRESS_CONSTANTS = ("TEXT_DRAW", "DRAW_STRING", "SET_FONT", "GET_MILLISECONDS", "FILL_RECT_IMPL",
                          "SCENE_DRAW", "SCENE_IS_ACTIVE", "DRAW_CONTROLS", "DRAW_HINTS", "ADD_CONTROL",
                          "GET_CONTROL", "OPERATOR_NEW", "TEXT_CONTROL_CTOR", "HINT_CONTROL_CTOR", "TEXT_IMPL_CTOR",
                          "TEXT_SET_TEXT", "TEXT_SET_COLORS", "GRAPHICS_GET", "GET_IMAGE_GRID", "GET_CELL_RECT",
                          "DRAW_CELL", "HAS_MENU_LOGO")
# Core-variant numbers used only to prove things; never emitted to the DLL.
CORE_ONLY_CONSTANTS = ("IMAGE_BASE", "MENU_VTABLE", "MENU_SLOT_DRAW_SCENE", "TEXT_CONTROL_DRAW",
                       "UPDATE_SHOW_PLAYER_BODY", "MENU_NAME_CONTROL", "NAME_CONTROL_ID_FIELD", "NAME_CONTROL_X",
                       "NAME_CONTROL_Y", "NAME_JUSTIFY", "NAME_COLOR", "GS_PLAYER_COUNT", "GS_PLAYER_NAME",
                       "BACKGROUND_IMAGE", "DEFAULT_FONT_INDEX", "HINT_TEXT_MARGIN", "HINT_BOX_MARGIN",
                       "HINT_DRAW_BOX", "HINT_SET_TEXT_RECT",
                       *TEST_ADDRESS_CONSTANTS)
