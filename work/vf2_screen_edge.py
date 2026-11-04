"""Nothing runs off the screen (the owner, 2026-11-03: "i dont care if things run out of boxes, they just need to not
run off the screen"): the patched game's rule (runtime/native/b200unicode/b200screen.inc), the model the tests compare
the DLL with, and the translation editor's check (vf2_translations_window). The same rule as Virtual Families 1.

At run time (Render Unicode with In-Game Fonts or Use Unicode Font):
* DrawString: a text that would leave the screen but is partly on it is moved so that it ends at the screen's edge;
  one wider than the screen is cut, each line, to its longest start of whole characters and "…"; one taller keeps the
  lines that fit, the last ending in "…"; when not even "…" fits, the English is shown.
* DrawStringJustified (dialogs, events, the store): its box is moved so that it ends at the screen's edge; a box wider
  than the screen becomes the screen's width (the text wraps again at the game's own line breaks); a text that wraps
  taller keeps the lines that fit, with "…".
Only text the patches or a translation bring is touched: text with a letter beyond ASCII, or any text while a
translation is chosen.

The editor measures a translation with the game's own fonts (the letters the patcher makes and the ones Windows
draws included) and warns when a line is wider than the screen; "Wrap to fit" breaks such lines at the game's line
breaks.
"""
from __future__ import annotations

import vf2_game_text as T

SCREEN_W, SCREEN_H = 1024, 768          # the game's window (theGameState: GetGameWindowWidth 400h, 300h)
ELLIPSIS = "…"
ELLIPSIS_UTF8 = b"\xe2\x80\xa6"            # the DLL writes it as UTF-8
DRAWN_FONTS = ("Segoe24", "Segoe24Bold", "Segoe32Bold", "Segoe36Bold")


def width(font: T.GameFont, text: str) -> int:
    return T.get_width(font, T.encode(text))


def fit_line(font: T.GameFont, line: str, room: int, ellipsis: str = ELLIPSIS) -> str | None:
    """b200screen.inc FitLine: the line when it fits, else its longest start of whole characters, trailing spaces
    dropped, then "…"; None when not even "…" fits."""
    if width(font, line) <= room:
        return line
    raw = T.encode(line)
    best, any_fit = "", False
    at = 0
    for u in T.units(raw):
        at += len(u.raw)
        start = T.decode(raw[:at]).rstrip(" ")
        if width(font, start + ellipsis) > room:
            break
        best, any_fit = start, True
    if not any_fit and width(font, ellipsis) > room:
        return None
    return best + ellipsis


def clamp_wanted(text: str, translation: bool) -> bool:
    return translation or any(b >= 0x80 for b in T.encode(text))


def on_screen(font: T.GameFont, text: str, x: int, y: int, *, translation: bool = False,
              screen=(SCREEN_W, SCREEN_H), ellipsis: str = ELLIPSIS):
    """b200screen.inc OnScreen: (text, x, y) DrawString draws; text None: the English is shown instead. The Translations
    DLL alone (no Unicode text DLL: b200tr_screen.inc) does the same with ellipsis "..." (the stock fonts have no
    "…")."""
    sw, sh = screen
    if not text or not clamp_wanted(text, translation):
        return text, x, y
    w = width(font, text)
    lines = text.count("\n") + 1
    h = lines * font.line_height
    if x >= 0 and x + w <= sw and y >= 0 and y + h <= sh:
        return text, x, y
    if x >= sw or x + w <= 0 or y >= sh or y + h <= 0:
        return text, x, y
    fit = max(1, sh // font.line_height)
    if w > sw or lines > fit:
        parts = text.split("\n")
        out = []
        for k, line in enumerate(parts[:fit]):
            if k + 1 == fit and len(parts) > fit:
                line += ellipsis
            fitted = fit_line(font, line, sw, ellipsis)
            if fitted is None:
                return None, x, y
            out.append(fitted)
        text = "\n".join(out)
        w = width(font, text)
        h = (text.count("\n") + 1) * font.line_height
    x = 0 if (x < 0 or w > sw) else (sw - w if x + w > sw else x)
    y = 0 if (y < 0 or h > sh) else (sh - h if y + h > sh else y)
    return text, x, y


def _wrap(font: T.GameFont, raw: bytes, box: int, rows: int) -> tuple[int, int]:
    """b200screen.inc WrappedHeight's loop: (the height, the byte where the line after `rows` lines starts)."""
    n, at, lines, cut = len(raw), 0, 0, len(raw)
    while at < n and lines < 4096:
        while at < n and raw[at] == 0x20:
            at += 1
        if at >= n:
            break
        if lines == rows:
            cut = at
        _line, used, dbl = T.next_justified_line(font, raw[at:], 0x3FF, box, False)
        if not used:
            break
        lines += 1
        if dbl:
            if lines == rows:
                cut = at + used
            lines += 1
        at += used
    return lines * font.line_height, cut


def break_inside_words(font: T.GameFont, text: str, box: int) -> str:
    """b200screen.inc BreakInsideWords: the game's own wrapping ends a line only at a space; where
    GetNextJustifiedLine ends one inside a word (UAX #14 next to CJK, Thai ..., or in a word wider than the box) a
    line break is put. Text whose lines all end at spaces is unchanged."""
    raw = T.encode(text)
    n, at, out, changed = len(raw), 0, bytearray(), False
    while at < n:
        while at < n and raw[at] == 0x20:
            out.append(0x20)
            at += 1
        if at >= n:
            break
        _line, used, _dbl = T.next_justified_line(font, raw[at:], 0x3FF, box, False)
        if not used:
            used = n - at
        out += raw[at:at + used]
        at += used
        if at < n and raw[at - 1] not in (0x20, 0x0A) and raw[at] not in (0x20, 0x0A):
            out.append(0x0A)
            changed = True
    return T.decode(bytes(out)) if changed else text


def wrapped_height(font: T.GameFont, text: str, box: int) -> int:
    """How tall DrawStringJustified wraps `text` in a box `box` wide (b200screen.inc WrappedHeight)."""
    return _wrap(font, T.encode(text), box, 1 << 30)[0]


def wrap_on_screen(font: T.GameFont, text: str, x: int, y: int, box: int, *, translation: bool = False,
                   screen=(SCREEN_W, SCREEN_H)):
    """b200screen.inc WrapOnScreen: (text, x, y, box width) DrawStringJustified draws."""
    sw, sh = screen
    if not text or box <= 0 or not clamp_wanted(text, translation):
        return text, x, y, box
    box = min(box, sw)                               # a box wider than the screen: the screen
    text = break_inside_words(font, text, box)
    h = wrapped_height(font, text, box)
    if x >= 0 and x + box <= sw and y >= 0 and y + h <= sh:
        return text, x, y, box
    if x >= sw or x + box <= 0 or y >= sh or y + h <= 0:
        return text, x, y, box
    raw = T.encode(text)
    rows = max(1, sh // font.line_height)
    cut = _wrap(font, raw, box, rows)[1]
    if h > sh and cut < len(raw):
        kept = raw[:cut].rstrip(b" \n")
        while kept and wrapped_height(font, T.decode(kept + ELLIPSIS_UTF8), box) > sh:
            us = T.units(kept)
            kept = b"".join(u.raw for u in us[:-1]).rstrip(b" \n")
        text = T.decode(kept + ELLIPSIS_UTF8)
        h = wrapped_height(font, text, box)
    x = 0 if x < 0 else (sw - box if x + box > sw else x)
    y = 0 if (y < 0 or h > sh) else (sh - h if y + h > sh else y)
    return text, x, y, box


# --------------------------------------------------------------------------- the translation editor's check
def too_wide(fonts: dict, text: str, screen_w: int = SCREEN_W) -> list[tuple[str, int, str]]:
    """The lines of `text` wider than the screen in a game font: (line, its width in pixels, the font). Measured with
    the game's own letters, the patcher-made ones and the ones Windows draws. `fonts`: name -> GameFont."""
    out = []
    for line in text.split("\n"):
        widest = max(((width(fonts[name], line), name) for name in DRAWN_FONTS if name in fonts), default=(0, ""))
        if widest[0] > screen_w:
            out.append((line, widest[0], widest[1]))
    return out


def wrap_to_fit(fonts: dict, text: str, screen_w: int = SCREEN_W) -> str:
    """Wrap to fit: each line wider than the screen in the widest game font is broken where the game's own wrapping
    breaks it (GetNextJustifiedLine at the screen's width: spaces, and the places UAX #14 allows), never inside a
    {placeholder} or a %-conversion."""
    import re
    font = max((fonts[n] for n in DRAWN_FONTS if n in fonts), key=lambda f: f.line_height)
    out = []
    for line in text.split("\n"):
        if width(font, line) <= screen_w:
            out.append(line)
            continue
        protected = [(m.start(), m.end()) for m in re.finditer(r"\{[^{}]*\}|%[-+ #0]*\d*(?:\.\d+)?[a-zA-Z%]", line)]
        pieces = [T.decode(p) for p in T.wrap(font, T.encode(line), screen_w)]
        # join pieces back where a break would fall inside a protected span
        merged, at = [], 0
        for piece in pieces:
            start = line.find(piece, at) if piece else at
            if merged and any(a < start < b for a, b in protected):
                merged[-1] = merged[-1] + line[at:start] + piece
            else:
                merged.append(piece)
            at = start + len(piece)
        out.extend(merged)
    return "\n".join(out)
