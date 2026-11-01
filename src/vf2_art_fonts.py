"""The fonts: Virtual Families 2's four font pictures whole, every glyph the game cuts from them (labelled with its
character), and a line of text in every colour the game's code draws each font in, laid out and coloured exactly
as the game draws text.

How the game does it (the B200 desktop objects; tests/test_art_fonts.py runs it in Unicorn, tests/vf2_fonts_emu.py):

* Four font classes, Segoe24 / Segoe24Bold / Segoe32Bold / Segoe36Bold: each constructor calls
  ldwFont::Load(name, its static fontTable, spacing 0) -> ldwFontImpl::Load, which adds ".png" to a name with no
  dot and loads that picture (so Segoe24.png ... Segoe36Bold.png), keeps the table and the font's height (the first
  glyph's bottom - top) and gives each of the 256 characters a slot: the index of its glyph, or 0 (the first glyph,
  "!") for a character with no glyph (0x00-0x1F, 0x80-0xA1). A table row is (character, left, top, right,
  bottom); the 190 glyphs (! to DEL, space, 0xA2-0xFF) lie in rows across the picture, and none runs past its
  right edge, so the loader's wrap moves none. ldwFontImpl::GetCharSourceRect gives a character's glyph.
* theStringManager::LoadFonts makes the four and keeps them as font ids 0 (Segoe24), 1 (Segoe24Bold),
  2 (Segoe32Bold) and 3 (Segoe36Bold); Segoe32Bold is also the window's default font (ldwGameWindow::SetFont).
* ldwGameWindowImpl::DrawString: a colour whose alpha byte is 0 means white. ldwFontImpl::GetImage gives the font
  picture itself for white, else a copy whose every pixel is the picture's pixel AND SDL_MapRGBA(red, green, blue,
  255): each colour channel ANDed with the colour's (the glyphs are white, so they come out in the colour), the
  alpha kept. Then for each character: a newline moves down the font's height back to the first x; any other
  character's glyph is drawn with its top left at the pen (SDL_UpperBlit for an opaque colour) and the pen moves
  right by the glyph's width plus the spacing (0); a glyph 0 wide is skipped.
"""
from __future__ import annotations

import vf2_game_pictures as gp
import vf2_picture_image as pi

TITLE = "Fonts"
CATEGORY = "Fonts"
SPACING = 0                          # ldwFont::Load's third argument in all four constructors
SAMPLE_TEXT = "The quick brown fox jumps over the lazy dog 0123456789"
CHARS = bytes(range(33, 128)) + b" " + bytes(range(0xA2, 0x100))    # every glyph table's characters, in order
NAMES = ("Segoe24", "Segoe24Bold", "Segoe32Bold", "Segoe36Bold")     # font ids 0, 1, 2, 3
WINDOW_FONT = "Segoe32Bold"

# Each font's height and its 190 glyphs in table order: (left u16, top u16, width u8), little-endian, as hex.
_TABLES = {
    "Segoe24": (19, (
        "000000000505000000060b0000000a15000000091e0000000e2c0000000c38000000043c0000000541000000054600000007"
        "4d0000000c59000000045d00000007640000000468000000076f00000009780000000981000000098a000000099300000009"
        "9c00000009a500000009ae00000009b700000009c000000009c900000004cd00000004d10000000cdd0000000ce90000000c"
        "f500000008fd000000100d0100000b180100000a220100000b2d0100000c390100000942010000084a0100000c560100000c"
        "620100000567010000066d0100000a77010000087f0100000f8e0100000d9b0100000da80100000ab20100000dbf0100000a"
        "c901000008d101000009da0100000ce60100000b00001a001010001a000a1a001a000923001a000a2d001a000532001a0006"
        "38001a00053d001a000c49001a000750001a000555001a00095e001a000a68001a000870001a000a7a001a000983001a0005"
        "88001a000a92001a000a9c001a0004a0001a0004a4001a0008ac001a0004b0001a000fbf001a000ac9001a000ad3001a000a"
        "dd001a000ae7001a0006ed001a0007f4001a0006fa001a000a04011a00080c011a000c18011a000820011a000828011a0008"
        "30011a000535011a000439011a00053e011a000c4a011a000b55011a00055a011a000963011a00096c011a000975011a0009"
        "7e011a000482011a00088a011a000791011a000fa0011a0007a7011a0009b0011a000cbc011a0000bc011a000fcb011a0007"
        "d2011a0006d8011a000ce4011a0006ea011a0006f0011a0005f5011a000a000034000808003400040c003400030f00340006"
        "15003400071c00340009250034000f3400340010440034001054003400085c0034000b670034000b720034000b7d0034000b"
        "880034000b930034000b9e0034000fad0034000bb800340009c100340009ca00340009d300340009dc00340005e100340005"
        "e600340005eb00340005f00034000cfc0034000d090134000d160134000d230134000d300134000d3d0134000d4a0134000c"
        "560134000d630134000c6f0134000c7b0134000c870134000c93013400099c0134000aa601340009af01340009b801340009"
        "c101340009ca01340009d301340009dc01340009e50134000ef30134000800004e000909004e000912004e00091b004e0009"
        "24004e000428004e00042c004e000430004e000434004e000a3e004e000a48004e000a52004e000a5c004e000a66004e000a"
        "70004e000a7a004e000c86004e000a90004e000a9a004e000aa4004e000aae004e000ab8004e0008c0004e000aca004e0008"
    )),
    "Segoe24Bold": (19, (
        "000000000606000000080e0000000a180000000a220000000f310000000c3d00000005420000000648000000064e00000008"
        "560000000c620000000567000000076e0000000573000000087b0000000a850000000a8f0000000a990000000aa30000000a"
        "ad0000000ab70000000ac10000000acb0000000ad50000000adf00000005e400000005e90000000cf50000000c010100000c"
        "0d010000071401000010240100000c300100000b3b0100000b460100000d53010000095c01000009650100000c710100000d"
        "7e0100000583010000088b0100000b96010000099f01000010af0100000dbc0100000dc90100000ad30100000de00100000b"
        "eb01000009f40100000a00001a000c0c001a000b17001a001128001a000b33001a000a3d001a000a47001a00064d001a0007"
        "54001a00065a001a000c66001a00076d001a000572001a00097b001a000b86001a00088e001a000b99001a0009a2001a0007"
        "a9001a000bb4001a000abe001a0005c3001a0005c8001a000ad2001a0005d7001a000fe7001a000af1001a000afb001a000b"
        "06011a000b11011a000718011a00071f011a000726011a000a30011a000939011a000e47011a000950011a000959011a0008"
        "61011a000667011a00066d011a000673011a000c7f011a000b8a011a00058f011a000a99011a000aa3011a0009ac011a000a"
        "b6011a0006bc011a0008c4011a0008cc011a000fdb011a0007e2011a000aec011a000cf8011a0000000034000f0f00340004"
        "1300340006190034000c25003400072c003400073300340005380034000a42003400094b0034000550003400045400340007"
        "5b00340008630034000a6d003400107d003400108d003400119e00340007a50034000cb10034000cbd0034000cc90034000c"
        "d50034000ce10034000ced00340010fd0034000b080134000911013400091a0134000923013400092c013400053101340005"
        "36013400053b01340005400134000d4d0134000d5a0134000d670134000d740134000d810134000d8e0134000d9b0134000c"
        "a70134000db40134000cc00134000ccc0134000cd80134000ce40134000aee0134000a00004e000b0b004e000914004e0009"
        "1d004e000926004e00092f004e000938004e000941004e000e4f004e000857004e000960004e000969004e000972004e0009"
        "7b004e000580004e000585004e00058a004e00058f004e000a99004e000aa3004e000aad004e000ab7004e000ac1004e000a"
        "cb004e000ad5004e000ce1004e000aeb004e000af5004e000aff004e000a09014e000a13014e00091c014e000b27014e0009"
    )),
    "Segoe32Bold": (26, (
        "0000000008080000000b130000000e210000000d2e00000014420000001153000000075a0000000862000000086a0000000a"
        "740000001084000000068a000000099300000006990000000aa30000000db00000000dbd0000000dca0000000dd70000000d"
        "e40000000df10000000dfe0000000d0b0100000d180100000d25010000062b01000006310100001041010000105101000010"
        "610100000a6b010000168101000010910100000fa00100000eae01000011bf0100000ccb0100000cd701000010e701000012"
        "f901000007000023000a0a0023000f190023000c25002300163b002300124d002300115e0023000e6c002300117d0023000f"
        "8c0023000c980023000da500230011b60023000fc500230017dc0023000feb0023000ef90023000e07012300080f0123000a"
        "19012300082101230010310123000a3b01230007420123000c4e0123000e5c0123000b670123000e750123000c8101230009"
        "8a0123000e980123000ea601230007ad01230007b40123000dc101230007c801230012dd0123000eeb0123000e000046000e"
        "0e0046000e1c00460009250046000a2f00460009380046000e460046000c5200460012640046000d710046000c7d0046000b"
        "880046000890004600089800460008a000460010b000460010c000460007c70046000dd40046000de10046000dee0046000d"
        "fb00460008030146000b0e0146000b19014600142d01460009360146000d4301460010530146000053014600146701460005"
        "6c01460009750146001085014600098e0146000997014600079e0146000eac0146000cb801460006be01460005c301460009"
        "cc0146000ad60146000de301460016000069001616006900172d0069000a3700690010470069001057006900106700690010"
        "770069001087006900109700690016ad0069000ebb0069000cc70069000cd30069000cdf0069000ceb00690007f200690007"
        "f9006900070001690007070169001118016900122a016900113b016900114c016900115d016900116e016900117f01690010"
        "8f01690011a001690011b101690011c201690011d301690011e40169000ef20169000e00008c000e0e008c000c1a008c000c"
        "26008c000c32008c000c3e008c000c4a008c000c56008c001369008c000b74008c000c80008c000c8c008c000c98008c000c"
        "a4008c0007ab008c0007b2008c0007b9008c0007c0008c000ece008c000edc008c000eea008c000ef8008c000e06018c000e"
        "14018c000e22018c001032018c000e40018c000e4e018c000e5c018c000e6a018c000e78018c000c84018c000e92018c000c"
    )),
    "Segoe36Bold": (29, (
        "0000000009090000000d160000000f250000000f34000000174b000000135e00000008660000000a700000000a7a0000000c"
        "860000001298000000079f0000000baa00000007b10000000cbd0000000fcc0000000fdb0000000fea0000000ff90000000f"
        "080100000f170100000f260100000f350100000f440100000f53010000075a01000007610100001273010000128501000012"
        "970100000ba201000019bb01000012cd01000011de010000100000270013130027000e210027000e2f002700124100270014"
        "55002700085d0027000c69002700117a0027000d8700270019a000270015b500270014c900270010d900270014ed00270011"
        "fe0027000e0c0127000f1b012700132e012700113f0127001a59012700116a012700107a012700108a0127000a940127000b"
        "9f0127000aa901270012bb0127000bc601270008ce0127000edc01270010ec0127000c00004e001010004e000e1e004e000a"
        "28004e001038004e001048004e00074f004e000756004e000f65004e00076c004e001784004e001094004e0010a4004e0010"
        "b4004e0010c4004e000ace004e000bd9004e000ae3004e0010f3004e000e01014e001516014e000e24014e000e32014e000c"
        "3e014e000a48014e000850014e000a5a014e00126c014e00127e014e000785014e000f94014e000fa3014e000eb1014e000f"
        "c0014e0008c8014e000dd5014e000ce1014e0017000075000b0b0075000f1a007500122c007500002c007500174300750005"
        "480075000a5200750012640075000b6f0075000b7a007500088200750010920075000d9f00750007a600750006ac0075000a"
        "b60075000cc20075000fd100750019ea0075001903017500191c0175000b270175001239017500124b017500125d01750012"
        "6f0175001281017500129301750018ab01750010bb0175000ec90175000ed70175000ee50175000ef30175000800009c0008"
        "08009c000810009c000818009c00132b009c001540009c001454009c001468009c00147c009c001490009c0014a4009c0012"
        "b6009c0014ca009c0013dd009c0013f0009c001303019c001316019c001026019c001036019c001046019c000e54019c000e"
        "62019c000e70019c000e7e019c000e8c019c000e9a019c0016b0019c000cbc019c000eca019c000ed8019c000ee6019c000e"
        "f4019c00070000c300070700c300070e00c300071500c3000f2400c300103400c300104400c300105400c300106400c30010"
        "7400c300108400c300129600c30010a600c30010b600c30010c600c30010d600c30010e600c3000ef400c300100401c3000e"
    )),
}

# The colours the game's code passes with each font (0xAABBGGRR: red is the lowest byte), and where: every call
# that asks theStringManager::GetFont for the font and then draws text with it (DrawString, DrawStringCentered,
# DrawStringRight, DrawStringJustified), sets a button's text (ldwButton::SetText) or a text control's colours
# (ldwTextControl::SetColors) (vf2_fonts_emu.font_colours finds them; cLdwNoColor, "no second colour", left out).
WHITE, BLACK = 0xFFFFFFFF, 0xFF000000
COLOURS = {
    "Segoe24Bold": (
        (WHITE, "white", ("??0theMainScene", "??0theMenuScene", "??0thePurchaseDialog",
                          "?DrawAchievement@CAchievement", "?DrawFamily@CFamilyTreeScene", "?DrawScene@CCollectionScene",
                          "?DrawScene@CScrollingStoreScene", "?DrawSceneFinal@theMainScene",
                          "?DrawVisibleStoreItem@CScrollingStoreScene", "?Init@theMessageBoxDlg")),
        (BLACK, "black", ("??0theMainScene", "?DrawScene@CScrollingStoreScene")),
        (0xFF00FF00, "green", ("?DrawVisibleStoreItem@CScrollingStoreScene",)),
        (0xFF66800A, "teal (10, 128, 102)", ("??0CFamilyTreeScene",)),
        (0xFF804C05, "dark blue (5, 76, 128)", ("??0theMainScene", "?DrawAchievement@CAchievement")),
    ),
    "Segoe32Bold": (
        (WHITE, "white", ("??0CBankingDlg", "??0CCommunityEventDialog", "??0CIslandEventDialog",
                          "??0theGameMenuDialog", "??0theMenuScene", "??0theOptionsDialog", "??0thePurchaseDialog",
                          "??0theVillagerScene", "?Init@theMessageBoxDlg")),
        (BLACK, "black", ("??0CIslandEventDialog",)),
        (0xFF804C05, "dark blue (5, 76, 128)", ("??0theLoadingScene",)),
        (0xFFAED2F0, "pale orange (240, 210, 174)", ("??0theVillagerScene",)),
        (0xFFBBB7E8, "pale pink (232, 183, 187)", ("??0theVillagerScene",)),
        (0xFFC5CED8, "pale grey (216, 206, 197)", ("??0theVillagerScene",)),
        (0xFFC8BC98, "pale blue (152, 188, 200)", ("??0theVillagerScene",)),
    ),
    "Segoe36Bold": (
        (WHITE, "white", ("??0CAchievementsScene", "??0CAdoptionScene", "??0CBankingDlg", "??0CCollectionScene",
                          "??0CCommunityEventDialog", "??0CDatingScene", "??0CFamilyTreeInfoDlg",
                          "??0CFamilyTreeScene", "??0CScrollingStoreScene", "??0CStoryScene",
                          "??0theCreateNickNameDlg", "??0theGameMenuDialog", "??0theHelpScene", "??0theMainScene",
                          "??0theMenuScene", "??0theOptionsDialog", "??0thePurchaseDialog", "??0theVillagerScene",
                          "?Init@theMessageBoxDlg", "?Init@theProgressDlg", "?Init@theTipDialog")),
        (BLACK, "black", ("??0CCommunityEventDialog", "?Draw@CStory", "?DrawScene@CScrollingStoreScene")),
        (0xFFCCCC33, "turquoise (51, 204, 204)", ("??0CStoryScene",)),
    ),
}
UNUSED_FONTS = {
    "Segoe24": ("Loaded when the game starts (theStringManager::LoadFonts keeps it as font id 0) but never drawn: "
                "theStringManager::GetFont is only ever called with the ids 1, 2 and 3, GetTinyFont (id 0) is called "
                "by no code, and the window's default font is Segoe32Bold."),
}
WHOLE_CHECKED = "The file's own pixels, as the game's picture loader reads them."
CHECK_GLYPH = ("Cut where the game's own font loader (ldwFont::Load -> ldwFontImpl::Load) and "
               "ldwFontImpl::GetCharSourceRect, run in Unicorn, cut it.")
CHECK_LINE = ("Drawn as ldwGameWindowImpl::DrawString draws it, run in Unicorn with the font's real pixels: every "
              "glyph, its place and its colour (ldwFontImpl::GetImage's AND) are the game's.")


def font_files() -> list[str]:
    """The font pictures this module shows (vf2_art_sheets leaves them to it)."""
    return [f"{name}.png" for name in NAMES]


_PARSED: dict = {}


def table(name: str) -> tuple[int, list]:
    """(height, [(character, (left, top, right, bottom))] in table order)."""
    if name not in _PARSED:
        height, hexes = _TABLES[name]
        raw = bytes.fromhex("".join(hexes))
        rows = []
        for k, ch in enumerate(CHARS):
            left = int.from_bytes(raw[5 * k:5 * k + 2], "little")
            top = int.from_bytes(raw[5 * k + 2:5 * k + 4], "little")
            rows.append((ch, (left, top, left + raw[5 * k + 4], top + height)))
        _PARSED[name] = (height, rows)
    return _PARSED[name]


def glyph(name: str, ch: int) -> tuple:
    """ldwFontImpl::GetCharSourceRect: the rectangle drawn for a character (the first glyph, "!", when it has none)."""
    _h, rows = table(name)
    for c, rect in rows:
        if c == ch & 0xFF:
            return rect
    return rows[0][1]


def char_name(ch: int) -> str:
    if ch == 32:
        return "space"
    if ch == 127:
        return "character 127 (DEL, no letter)"
    return f"\"{bytes([ch]).decode('cp1252')}\" (character {ch})"


def tint(image: pi.Image, colour: int) -> pi.Image:
    """ldwFontImpl::GetImage: each pixel's red, green and blue ANDed with the colour's; alpha kept. White is the
    picture itself."""
    r, g, b = colour & 0xFF, (colour >> 8) & 0xFF, (colour >> 16) & 0xFF
    if (r, g, b) == (255, 255, 255):
        return image
    out = image.copy()
    d = out.data
    for i in range(0, len(d), 4):
        d[i] &= r
        d[i + 1] &= g
        d[i + 2] &= b
    return out


def _tinted_glyph(file, rect, colour):
    def make(files):
        l, t, r, b = rect
        return tint(files.image(file).sub(l, t, r - l, b - t), colour)
    return make


def text_layers(files, name: str, text: str, colour: int, x: int = 0, y: int = 0) -> list:
    """The draws ldwGameWindowImpl::DrawString makes for `text` (an opaque colour)."""
    height, _rows = table(name)
    file = files.relative(f"{name}.png".lower())
    if not (colour >> 24) & 0xFF:
        colour = WHITE
    pen, out = x, []
    for ch in text.encode("cp1252"):
        if ch == 10:
            pen, y = x, y + height
            continue
        rect = glyph(name, ch)
        width = rect[2] - rect[0]
        if not width:
            continue
        if (colour & 0xFFFFFF) == 0xFFFFFF:
            out.append(gp.Draw(file, rect, pen, y))
        else:
            out.append(gp.Draw(file, rect, pen, y, make=_tinted_glyph(file, rect, colour)))
        pen += width + SPACING
    return out


def arts(files: gp.GameFiles) -> list[gp.Art]:
    out = []
    for font_id, name in enumerate(NAMES):
        file = f"{name}.png"
        if not files.has(file):
            continue
        real = files.relative(file.lower())
        cat = f"{CATEGORY}/{name}"
        used = name not in UNUSED_FONTS
        loaded = (f"Font id {font_id}" + (", the window's default font" if name == WINDOW_FONT else "")
                  + f": loaded by the {name} font class (ldwFont::Load(\"{name}\"); ldwFontImpl::Load adds \".png\").")
        why = loaded if used else f"{loaded} {UNUSED_FONTS[name]}"
        w, h = files.size(real)
        out.append(gp.Art(f"fonts/{name}/file", cat, f"{name}.png (the whole font picture)",
                          (gp.Draw(real, (0, 0, w, h)),), used, why, WHOLE_CHECKED))
        height, rows = table(name)
        for k, (ch, rect) in enumerate(rows):
            extra = (" It is also drawn for every character with no glyph of its own (0x00-0x1F, 0x80-0xA1)."
                     if k == 0 else "")
            out.append(gp.Art(f"fonts/{name}/glyph/{ch}", cat, f"{name}: {char_name(ch)}",
                              (gp.Draw(real, rect, 0, 0),), used,
                              f"Glyph {k + 1} of 190 in {name}'s table, {rect[2] - rect[0]} x {height} pixels.{extra}"
                              + ("" if used else f" {UNUSED_FONTS[name]}"), CHECK_GLYPH))
        for colour, words, sites in COLOURS.get(name, ()):
            out.append(gp.Art(f"fonts/{name}/line/{colour:08X}", cat, f"{name}: a line of text in {words}",
                              tuple(text_layers(files, name, SAMPLE_TEXT, colour)), True,
                              f"The game draws {name} in {words} (colour {colour:08X}h) in "
                              f"{', '.join(s.lstrip('?') for s in sites)}. The words are a sample.", CHECK_LINE))
    return out
