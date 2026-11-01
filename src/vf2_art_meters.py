"""The Picture Maker's "Meters and bars": every bar Virtual Families 2 draws, empty, full and at the levels where
its look changes, each put together with what the game draws beneath it, in the game's order.

Where the rules come from (the B200 desktop objects, work/desktop_obj_files; tests/test_art_meters.py runs every
function named here in Unicorn and checks these draws against the game's):

* theContinuousVariableMeter (one object, made on first use by Get). Its constructor fetches eight pictures:
  +8 StatusBarSliceB.png (361), +0xC StatusBarSliceR.png (362), +0x10 VD_progressbar-blue.jpg (268),
  +0x14 VD_progressbar-red.jpg (269), +0x18 VD_fade-01.png (270), +0x1C VD_fade-02.png (271),
  +0x20 VD_line-blue.jpg (272), +0x24 VD_line-red.jpg (273). Its one drawing function DrawPercentMeter(colour,
  value) (a jump table for colours 8..13):
    - the percent: colour 9 (career progress) clamps the value to 3,000 and divides by 30; the others clamp it
      to 100; below 0 is 0. The filled width w = percent * 290 / 100 (whole pixels, rounded down), so every
      percent draws a different width (2 or 3 pixels more);
    - it sets the window's clipping to (x0, y, x0 + w, y + 33) (ldwGameWindow::SetClipping), draws whole, each
      cut by the clip (ldwGameWindowImpl::ClipRect): the fill at (x0, y), the edge line at (x0 + w - 3, y), the
      end shading VD_fade-02 at (x0 + 271, y); then resets the clipping. So nothing shows at 0 percent, the
      edge line shows cut to 2 pixels at 1 percent and whole from 2 percent, and the end shading appears from
      94 percent (w 272 > 271).
    - colour 9 uses the red fill and line, every other colour the blue ones. +8, +0xC and +0x18 are never read:
      StatusBarSliceB / R and VD_fade-01 are fetched and never drawn by it.
    - x0 is the colour's place (617 for 8..12, 375 for 13) plus theGameState::GetWideScreenOffsetX (0 on a
      4:3 screen; the pictures use 0).
* The Details screen (theVillagerScene::DrawScene): VD_BG_2.jpg whole at (offset, 0) (it has the five empty
  white troughs painted in), upgradeMeButton.png, the family member, then five bars: Progress (colour 9, y 188:
  3,000 when the career level +0x6B90 is 7 or more, 0 without a career (+0x6B8C = -1), else the promotion
  points +0x6B94), Happiness (10, y 272, +0x6B2C), Fed (11, y 374, 100 - hunger +0x6B34), Energy (12, y 427,
  +0x6B28), Health (8, y 323, +0x6B00); then main_no-comm.png at (offset, 722). The words beside the bars are
  text controls the screen writes.
* The loading screen (theLoadingScene::DrawScene): loading.jpg (cell 0, centred), the frame LoadSceneBarBG.png
  at (375 + offset, 500), then the meter's colour 13 with the scene's counter (+0x28), then the distributor's
  loading logo.
* theSlicedVariableMeter and theVariableMeter: never used. Nothing in the game's code calls their
  DrawPercentMeter or their Get (tests/test_art_meters.py proves it over every object). Drawn here by their own
  code all the same: the sliced meter draws StatusBarSliceB.png every 2 pixels from x 473, value * 290 / 200
  slices (colour 9 counts to 1,000); the variable meter (value 1..100) fills a rectangle (x + 7, y + 5) to
  (x + 7 + value * 151 / 100, y + 28) for colours 0..2, or draws LoadColor.png every 8 pixels, value * 2 / 5 of
  them, for colour 3.
* An achievement on the Awards screen (CAchievement::DrawAchievement, a row at (x, y)): achievement_box.png
  (achievement_complete_box.png when finished) at (x + 8, y); while the achievement is not finished and its goal
  (achievementList + 28 * index + 4) is more than 1, achievement_progress_box.png at (x + 680, y + 14), then,
  when the percent (PercentCompleted: count * 100 / goal) is above 0, a solid fill of colour (216, 120, 10) from
  (x + 682, y + 16), percent * 222 / 100 wide and 25 high (ldwGameWindow::FillRect). The words are text. The
  game marks an achievement finished the moment its count reaches the goal (IncrementProgress -> SetComplete),
  and a finished one shows no bar.

Technology bars: Virtual Families 2 has none. CTech (Tech.obj) only keeps levels (Reset, LoadState, SaveState,
Level) and draws nothing; CVillagerSkills (VillagerSkills.obj) draws nothing; no code but the meters above asks
for a bar picture (tests/test_art_meters.py checks the objects' drawing calls). The workplace upgrades
("Upgrades/...") are furniture pictures, not bars.
"""
from __future__ import annotations

import vf2_game_pictures as gp
from vf2_game_pictures import Art, Draw, Fill

TITLE = "Meters and bars"
CAT = "Meters and bars"

# image ids
LOAD_FRAME, BLUE, RED, FADE_START, FADE_END, LINE_BLUE, LINE_RED = 267, 268, 269, 270, 271, 272, 273
SLICE_BLUE, SLICE_RED, LOAD_COLOUR = 361, 362, 363
LOADING_BG, DETAILS_BG = 366, 462
ACH_BOX, ACH_DONE, ACH_PROGRESS = 625, 626, 627
CONTINUOUS_IDS = frozenset((BLUE, RED, FADE_START, FADE_END, LINE_BLUE, LINE_RED, SLICE_BLUE, SLICE_RED))

BAR_W, BAR_H, END_AT = 290, 33, 271                     # 0x122, the clip's height, VD_fade-02's place
# DrawPercentMeter's colours: x0, y (the jump table's cases)
CONTINUOUS = {8: (617, 323), 9: (617, 188), 10: (617, 272), 11: (617, 374), 12: (617, 427), 13: (375, 500)}
SLICED_Y = {3: 223, 4: 265, 5: 308, 6: 351, 7: 392, 8: 272, 9: 165, 10: 232, 11: 312, 12: 351}
VARIABLE_FILL = {0: (0.9, 0.5, 0.5, 0.9), 1: (0.5, 0.9, 0.5, 0.9), 2: (0.5, 0.5, 0.9, 0.9)}

# The Details screen's bars in the order theVillagerScene::DrawScene draws them: colour, name, offsets read
DETAILS = (
    (9, "Progress", "how near the career's next promotion is: the promotion points (+0x6B94) out of 3,000; full "
                    "at career level 7 or more, empty without a career"),
    (10, "Happiness", "happiness (+0x6B2C), 0 to 100"),
    (11, "Fed", "100 less the hunger (+0x6B34), so it empties as the family member gets hungry"),
    (12, "Energy", "energy (+0x6B28), 0 to 100"),
    (8, "Health", "health (+0x6B00), 0 to 100"),
)

# Levels shown (percent). Every percent is a different width (percent * 290 / 100 pixels: 2 or 3 more each), so
# these are representative, with every level where something new happens: 0 (nothing drawn), 1 (2 pixels: the
# edge line cut), 2 (the edge line whole from here), 93 (the last level without the end shading), 94 (the end
# shading first shows), 100 (full).
LEVELS = (0, 1, 2, 10, 25, 50, 75, 90, 93, 94, 100)
SLICED_LEVELS = (1, 10, 25, 50, 75, 100)
VARIABLE_LEVELS = (1, 25, 50, 75, 100)
ACH_LEVELS = (0, 1, 10, 25, 50, 75, 90, 99, 100)
ACH_COLOUR = (216, 120, 10, 255)                        # 0xFF0A78D8 as an ldwColor: r d8, g 78, b 0a, a ff
ACH_ROW_BOX_AT = (8, 0)                                 # row x + 8, row y
ACH_BOX_AT = (680, 14)                                  # row x + 0x2AA - 2, row y + 0x10 - 2
ACH_FILL_AT = (682, 16)                                 # row x + 0x2AA, row y + 0x10
ACH_FILL_W, ACH_FILL_H = 222, 25                        # 0xDE, 0x19

CHECK_DETAILS = ("Checked against the game's own theVillagerScene::DrawScene and theContinuousVariableMeter::"
                 "DrawPercentMeter (with ldwGameWindowImpl::ClipRect's clipping) run in Unicorn.")
CHECK_LOADING = ("Checked against the game's own theLoadingScene::DrawScene and theContinuousVariableMeter::"
                 "DrawPercentMeter (with ldwGameWindowImpl::ClipRect's clipping) run in Unicorn.")
CHECK_SLICED = "Checked against the game's own theSlicedVariableMeter::DrawPercentMeter run in Unicorn."
CHECK_VARIABLE = "Checked against the game's own theVariableMeter::DrawPercentMeter run in Unicorn."
CHECK_ACH = "Checked against the game's own CAchievement::DrawAchievement run in Unicorn."
CHECK_PIECE = "Checked against the game's own theContinuousVariableMeter::DrawPercentMeter run in Unicorn."


# ------------------------------------------------------------------ the game's rules
def percent(colour: int, value: int) -> int:
    """DrawPercentMeter's percent for a value (colour 9: value / 30 of at most 3,000, rounded toward zero)."""
    if colour == 9:
        value = min(value, 3000)
        p = int(value / 30) if value >= 0 else -(-value // 30)
    else:
        p = min(value, 100)
    return max(p, 0)


def continuous_calls(colour: int, value: int, offset: int = 0) -> list:
    """theContinuousVariableMeter::DrawPercentMeter(colour, value)'s calls, in order: ("clip", l, t, r, b),
    ("draw", image id, x, y) (the whole picture), ("unclip",)."""
    if colour not in CONTINUOUS:
        return []
    w = percent(colour, value) * BAR_W // 100
    x, y = CONTINUOUS[colour]
    x += offset
    fill, line = (RED, LINE_RED) if colour == 9 else (BLUE, LINE_BLUE)
    return [("clip", x, y, x + w, y + BAR_H), ("draw", fill, x, y), ("draw", line, x + w - 3, y),
            ("draw", FADE_END, x + END_AT, y), ("unclip",)]


def sliced_calls(colour: int, value: int) -> list:
    """theSlicedVariableMeter::DrawPercentMeter(colour, value) (never called by the game)."""
    if colour not in SLICED_Y:
        return []
    value = max(0, min(value, 1000) // 10 if colour == 9 else min(value, 100))
    return [("draw", SLICE_BLUE, 0x1D9 + 2 * k, SLICED_Y[colour]) for k in range(value * BAR_W // 200)]


def variable_calls(colour: int, x: int, y: int, value: int) -> list:
    """theVariableMeter::DrawPercentMeter(colour, x, y, value) (never called by the game)."""
    value = max(1, min(value, 100))
    if colour in VARIABLE_FILL:
        return [("fill", x + 7, y + 5, x + 7 + value * 151 // 100, y + 28, VARIABLE_FILL[colour])]
    if colour == 3:
        return [("draw", LOAD_COLOUR, x + 8 * k, y) for k in range(value * 320 // 800)]
    return []


def clip_draw(x: int, y: int, w: int, h: int, clip: tuple | None):
    """ldwGameWindowImpl::ClipRect: (None when nothing is drawn) the part of a w x h picture at (x, y) inside the
    clipping rectangle [left, right) x [top, bottom), as (source left, source top, x, y, width, height)."""
    if clip is None:
        return 0, 0, x, y, w, h
    left, top, right, bottom = clip
    if x >= right or y >= bottom or x + w < left or y + h < top:
        return None
    sx = sy = 0
    if x < left:
        sx, w, x = left - x, w - (left - x), left
    if x + w > right:
        w = right - x
    if y < top:
        sy, h, y = top - y, h - (top - y), top
    if y + h > bottom:
        h = bottom - y
    return sx, sy, x, y, w, h


def _f32(v: float) -> float:
    return gp.pi.f32(v)


def fill_rgba(colour: tuple) -> tuple:
    """ldwGameWindowImpl::FillRect's colour from (r, g, b, a) floats: each channel (int)(c * 255.0f); the alpha
    of a blended fill (int)(a * 255.0f + 0.5f)."""
    r, g, b = (int(_f32(_f32(c) * 255.0)) for c in colour[:3])
    a = int(_f32(_f32(_f32(colour[3]) * 255.0) + 0.5))
    return r, g, b, a


def layers(files: gp.GameFiles, calls: list) -> list:
    """The meter's calls as the picture's layers: each whole-picture draw cut by the clipping as ClipRect cuts
    it (draws cut to nothing are left out: they draw no pixel)."""
    out, clip = [], None
    for call in calls:
        kind = call[0]
        if kind == "clip":
            clip = call[1:5]
        elif kind == "unclip":
            clip = None
        elif kind == "draw":
            name, rect = gp.cell_of(files, call[1], 0)
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            part = clip_draw(call[2], call[3], w, h, clip)
            if part is None or part[4] <= 0 or part[5] <= 0:
                continue
            sx, sy, x, y, pw, ph = part
            out.append(Draw(name, (rect[0] + sx, rect[1] + sy, rect[0] + sx + pw, rect[1] + sy + ph), x, y))
        elif kind == "fill":
            left, top, right, bottom, colour = call[1:6]
            if clip is not None:
                left, top = max(left, clip[0]), max(top, clip[1])
                right, bottom = min(right, clip[2]), min(bottom, clip[3])
            if right > left and bottom > top:
                out.append(Fill(left, top, right - left, bottom - top, fill_rgba(colour)))
    return out


def details_value(colour: int, p: int) -> int:
    """The value the Details screen hands the meter for its bar `colour` at p percent."""
    return p * 30 if colour == 9 else p


def details_numbers(colour: int, p: int) -> dict:
    """The family member's numbers (offsets in CVillager) that make the Details bar `colour` show p percent; the
    other bars at 50."""
    numbers = {0x6B00: 50, 0x6B28: 50, 0x6B2C: 50, 0x6B34: 50, 0x6B8C: 3, 0x6B90: 2, 0x6B94: 1500}
    field = {8: 0x6B00, 10: 0x6B2C, 12: 0x6B28}.get(colour)
    if field:
        numbers[field] = p
    elif colour == 11:
        numbers[0x6B34] = 100 - p
    elif colour == 9:
        numbers[0x6B94] = p * 30
    return numbers


def trough_rect(colour: int) -> tuple:
    """The part of the background under bar `colour` the pictures show: the bar and 6 pixels around it."""
    x0, y = CONTINUOUS[colour]
    return x0 - 6, y - 6, x0 + 300 + 6, y + BAR_H + 6


def trough(files: gp.GameFiles, colour: int) -> Draw:
    """That part of the background the calling screen draws first (VD_BG_2.jpg at (0, 0) for the Details screen,
    loading.jpg at (0, 0) for the loading screen)."""
    rect = trough_rect(colour)
    name = gp.cell_of(files, LOADING_BG if colour == 13 else DETAILS_BG, 0)[0]
    return Draw(name, rect, rect[0], rect[1])


def achievement_calls(p: int, finished: bool = False) -> list:
    """CAchievement::DrawAchievement's picture calls for a row at (0, 0) of an achievement whose goal is more
    than 1, at p percent."""
    out = [("draw", ACH_DONE if finished else ACH_BOX, *ACH_ROW_BOX_AT)]
    if not finished:
        out.append(("draw", ACH_PROGRESS, *ACH_BOX_AT))
        if p > 0:
            out.append(("fill", ACH_FILL_AT[0], ACH_FILL_AT[1], ACH_FILL_AT[0] + p * ACH_FILL_W // 100,
                        ACH_FILL_AT[1] + ACH_FILL_H, tuple(c / 255.0 for c in ACH_COLOUR)))
    return out


def achievement_layers(files: gp.GameFiles, p: int, finished: bool = False) -> list:
    out = []
    for call in achievement_calls(p, finished):
        if call[0] == "draw":
            out.append(gp.cell(files, call[1], 0, call[2], call[3]))
        else:
            out.append(Fill(call[1], call[2], call[3] - call[1], call[4] - call[2], ACH_COLOUR))
    return out


# ------------------------------------------------------------------ the catalogue
WORDS = ' The word "{word}" beside it is text the game writes; it is not part of the picture.'
TROUGH = (" Its empty white trough is part of the Details screen's background VD_BG_2.jpg (drawn whole first by "
          "theVillagerScene::DrawScene); the picture shows that part of it.")
LEVEL_WORDS = (" Every percent draws the bar 2 or 3 pixels longer (percent x 290 / 100), so these levels are "
               "a representative set with every level where something new appears.")


def _level_words(p: int) -> str:
    if p == 0:
        return "empty"
    if p == 100:
        return "full"
    return f"{p}% full"


def _level_note(p: int) -> str:
    return {0: " At 0 the meter draws nothing: the clipping is 0 pixels wide.",
            1: " At 1 percent the fill shows 2 pixels and the edge line is cut to them.",
            2: " From 2 percent the 3-pixel edge line shows whole.",
            93: " The last level without the end shading.",
            94: " From 94 percent the end shading (VD_fade-02.png) starts to show.",
            100: " Full: the fill shows 290 of its 296 pixels, the end shading whole."}.get(p, "")


def _details_arts(files: gp.GameFiles) -> list[Art]:
    arts = []
    for colour, name, what in DETAILS:
        for p in LEVELS:
            why = (f"The Details screen's {name} bar: {what}. Drawn {'red' if colour == 9 else 'blue'} by "
                   f"theContinuousVariableMeter (colour {colour}) from theVillagerScene::DrawScene."
                   + _level_note(p) + LEVEL_WORDS + TROUGH + WORDS.format(word=name))
            arts.append(Art(
                f"meters/details/{name.lower()}/{p}", f"{CAT}/{name} bar", f"{name} bar, {_level_words(p)}",
                (trough(files, colour), *layers(files, continuous_calls(colour, details_value(colour, p)))),
                True, why, CHECK_DETAILS))
    return arts


def _loading_arts(files: gp.GameFiles) -> list[Art]:
    arts = []
    for p in LEVELS:
        layers_ = (trough(files, 13), gp.cell(files, LOAD_FRAME, 0, *CONTINUOUS[13]),
                   *layers(files, continuous_calls(13, p)))
        arts.append(Art(
            f"meters/loading/{p}", f"{CAT}/Loading bar", f"Loading bar, {_level_words(p)}", layers_, True,
            "The bar on the loading screen (theLoadingScene::DrawScene): the part of loading.jpg around it, the "
            "frame LoadSceneBarBG.png at (375, 500), then theContinuousVariableMeter's blue bar (colour 13) at "
            "the scene's loading counter." + _level_note(p) + LEVEL_WORDS, CHECK_LOADING))
    return arts


def _sliced_arts(files: gp.GameFiles) -> list[Art]:
    arts = []
    for p in SLICED_LEVELS:
        arts.append(Art(
            f"meters/unused/sliced/{p}", f"{CAT}/Unused sliced meter", f"Sliced meter, {_level_words(p)}",
            tuple(layers(files, sliced_calls(3, p))), False,
            "Unused: theSlicedVariableMeter is never used (no code calls its Get or DrawPercentMeter). Drawn by its "
            "own code all the same: StatusBarSliceB.png every 2 pixels, value x 290 / 200 slices (145 when "
            "full). Every colour draws the same slices on its own row (colour 9 counts to 1,000); shown here "
            "for colour 3.", CHECK_SLICED))
    return arts


def _variable_arts(files: gp.GameFiles) -> list[Art]:
    names = {0: "red", 1: "green", 2: "blue", 3: "LoadColor"}
    arts = []
    for colour in (0, 1, 2, 3):
        # colour 3 draws its first slice at value 3 (3 x 2 / 5 = 1): below that it draws nothing
        for p in (VARIABLE_LEVELS if colour < 3 else (3, *VARIABLE_LEVELS[1:])):
            what = ("a see-through filled rectangle (ldwGameWindow::FillRect, alpha 0.9)" if colour < 3 else
                    "LoadColor.png every 8 pixels, value x 2 / 5 of them")
            arts.append(Art(
                f"meters/unused/variable/{colour}/{p}", f"{CAT}/Unused percent meter",
                f"Percent meter, {names[colour]}, {_level_words(p)}",
                tuple(layers(files, variable_calls(colour, 0, 0, p))), False,
                "Unused: theVariableMeter is never used (no code calls its Get or DrawPercentMeter). Drawn by its "
                f"own code all the same (colour {colour}): {what}. A fill's colour is shown as the game makes it; "
                "on the screen it would be blended with what is under it.", CHECK_VARIABLE))
    return arts


def _achievement_arts(files: gp.GameFiles) -> list[Art]:
    arts = []
    for p in ACH_LEVELS:
        if p == 100:
            used, why = False, (
                "A full achievement bar: the game marks an achievement finished the moment its count reaches the "
                "goal (CAchievement::IncrementProgress -> SetComplete), and the Awards screen shows a finished "
                "one without the bar, so the full bar is never shown.")
        else:
            used, why = True, (
                "An unfinished achievement's row on the Awards screen (CAchievement::DrawAchievement): "
                "achievement_box.png, the box achievement_progress_box.png, then an orange fill as wide as the "
                "count is of the goal (222 pixels for all of it); only achievements whose goal is more than 1 "
                "have the bar.")
        arts.append(Art(
            f"meters/achievement/{p}", f"{CAT}/Achievement progress bar",
            f"Achievement progress bar, {_level_words(p)}", tuple(achievement_layers(files, p)), used,
            why + " The achievement's name, its description and the \"count / goal\" words are text the game "
                  "writes.", CHECK_ACH))
    arts.append(Art(
        "meters/achievement/finished", f"{CAT}/Achievement progress bar", "Finished achievement (no bar)",
        tuple(achievement_layers(files, 100, finished=True)), True,
        "A finished achievement's row: achievement_complete_box.png and no bar (CAchievement::DrawAchievement). "
        "The words on it are text the game writes.", CHECK_ACH))
    return arts


def _piece_arts(files: gp.GameFiles) -> list[Art]:
    return [
        Art("meters/pieces/end-shading", f"{CAT}/Bar pieces", "Bar end shading, as a full bar shows it",
            tuple(layers(files, [("clip", 0, 0, 19, BAR_H), ("draw", FADE_END, 0, 0), ("unclip",)])), True,
            "VD_fade-02.png (19 x 33), drawn whole at the right end of every bar from 94 percent "
            "(theContinuousVariableMeter::DrawPercentMeter).", CHECK_PIECE),
        Art("meters/unused/start-shading", f"{CAT}/Unused bar pieces", "Bar start shading",
            (gp.cell(files, FADE_START, 0),), False, USAGE[FADE_START][1]),
        Art("meters/unused/status-slice-blue", f"{CAT}/Unused bar pieces", "Blue status bar slice",
            (gp.cell(files, SLICE_BLUE, 0),), False, USAGE[SLICE_BLUE][1]),
        Art("meters/unused/status-slice-red", f"{CAT}/Unused bar pieces", "Red status bar slice",
            (gp.cell(files, SLICE_RED, 0),), False, USAGE[SLICE_RED][1]),
        Art("meters/unused/load-colour", f"{CAT}/Unused bar pieces", "Loading bar colour slice",
            (gp.cell(files, LOAD_COLOUR, 0),), False, USAGE[LOAD_COLOUR][1]),
    ]


def arts(files: gp.GameFiles) -> list[Art]:
    out = []
    for part in (_details_arts, _loading_arts, _achievement_arts, _piece_arts, _sliced_arts, _variable_arts):
        try:
            out += part(files)
        except (gp.pi.PictureError, KeyError):         # a picture this game folder lacks: that part is left out
            continue
    return out


USAGE = {
    LOAD_FRAME: (True, "The loading bar's frame (theLoadingScene::DrawScene)."),
    BLUE: (True, "The blue fill of the Details screen's Happiness, Health, Fed and Energy bars and the loading bar "
                 "(theContinuousVariableMeter +0x10)."),
    RED: (True, "The red fill of the Details screen's Progress bar (theContinuousVariableMeter +0x14)."),
    FADE_START: (False, "Fetched into theContinuousVariableMeter (+0x18) but never drawn: its only drawing function "
                        "DrawPercentMeter never reads +0x18, and no other code asks for picture 270."),
    FADE_END: (True, "The shading at the end of a bar from 94 percent (theContinuousVariableMeter +0x1C)."),
    LINE_BLUE: (True, "The moving edge of the blue bars (theContinuousVariableMeter +0x20)."),
    LINE_RED: (True, "The moving edge of the red Progress bar (theContinuousVariableMeter +0x24)."),
    SLICE_BLUE: (False, "Fetched into theContinuousVariableMeter (+8) but never drawn by it (DrawPercentMeter never "
                        "reads +8); the only code that draws it is theSlicedVariableMeter, which is never used."),
    SLICE_RED: (False, "Fetched into theContinuousVariableMeter (+0xC) and theSlicedVariableMeter but never drawn: "
                       "neither DrawPercentMeter reads it."),
    LOAD_COLOUR: (False, "Only theVariableMeter asks for picture 363, and theVariableMeter is never used."),
    ACH_PROGRESS: (True, "The frame of an unfinished achievement's progress bar on the Awards screen "
                         "(CAchievement::DrawAchievement)."),
}

CELL_LABELS = {
    (LOAD_FRAME, 0): "Loading bar frame",
    (BLUE, 0): "Blue bar fill",
    (RED, 0): "Red bar fill",
    (FADE_START, 0): "Shading for a bar's start (never drawn)",
    (FADE_END, 0): "Shading at a bar's end",
    (LINE_BLUE, 0): "Blue bar's moving edge",
    (LINE_RED, 0): "Red bar's moving edge",
}

CELL_UNUSED: dict = {}
