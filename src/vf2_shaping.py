"""Shaped and right-to-left scripts: which stretches of a text the patched game draws as one shaped run (Render Unicode
with In-Game Fonts, Use Unicode Font and the Game Text tool). runtime/native/b200unicode/b200shape.h is the same rule
in C; tests/test_shaping.py proves the two equal. The rule is Virtual Villagers' and Virtual Families 1's
(patcher/vf1_shaping.py).

Arabic, Hebrew, Syriac, Thaana, the Indic scripts, Thai, Lao, Tibetan, Myanmar, Khmer, Mongolian and the other scripts
whose letters change shape with their neighbours or run right to left were drawn one whole character at a time, each
in its isolated form and in logical order. A RUN of such letters is drawn as one piece by GDI's ExtTextOutW, which
shapes it (Uniscribe) and puts it in visual order (the bidi algorithm, left-to-right base), as Windows draws it in its
own windows. A run is whole characters of one script group with the spaces between two of its words; at most
MAX_RUN_UNITS characters and MAX_RUN_BYTES bytes (a longer one is cut at its last space). A run of one character is
not a run. A run no face of the chain has every letter of, or wider than the font's sheet, is drawn a character at a
time, as before. Text with no such letter is drawn exactly as before.
"""
from __future__ import annotations

# (first, last, script group, right to left): b200shape.h kComplex, sorted, not overlapping
COMPLEX_RANGES: tuple[tuple[int, int, int, bool], ...] = (
    (0x0590, 0x05FF, 1, True), (0x0600, 0x08FF, 2, True), (0x0900, 0x097F, 3, False), (0x0980, 0x09FF, 4, False),
    (0x0A00, 0x0A7F, 5, False), (0x0A80, 0x0AFF, 6, False), (0x0B00, 0x0B7F, 7, False), (0x0B80, 0x0BFF, 8, False),
    (0x0C00, 0x0C7F, 9, False), (0x0C80, 0x0CFF, 10, False), (0x0D00, 0x0D7F, 11, False), (0x0D80, 0x0DFF, 12, False),
    (0x0E00, 0x0E7F, 13, False), (0x0E80, 0x0EFF, 14, False), (0x0F00, 0x0FFF, 15, False), (0x1000, 0x109F, 16, False),
    (0x1780, 0x17FF, 17, False), (0x1800, 0x18AF, 18, False), (0x1900, 0x194F, 19, False), (0x1980, 0x19DF, 20, False),
    (0x1A00, 0x1AAF, 21, False), (0x1B00, 0x1BBF, 22, False), (0x1BC0, 0x1BFF, 23, False), (0x1C00, 0x1C4F, 24, False),
    (0xA800, 0xA82F, 25, False), (0xA880, 0xA8DF, 26, False), (0xA8E0, 0xA8FF, 3, False), (0xA900, 0xA92F, 27, False),
    (0xA930, 0xA95F, 28, False), (0xA980, 0xA9DF, 29, False), (0xA9E0, 0xA9FF, 16, False), (0xAA00, 0xAA5F, 30, False),
    (0xAA60, 0xAA7F, 16, False), (0xAA80, 0xAADF, 31, False), (0xABC0, 0xABFF, 32, False), (0xFB1D, 0xFB4F, 1, True),
    (0xFB50, 0xFDFF, 2, True), (0xFE70, 0xFEFF, 2, True), (0x10800, 0x10FFF, 33, True), (0x11000, 0x11FFF, 34, False),
    (0x1E800, 0x1EFFF, 35, True),
)
MAX_RUN_UNITS = 64
MAX_RUN_BYTES = 380


def script_group(cp: int) -> int:
    lo, hi = 0, len(COMPLEX_RANGES) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        a, b, g, _r = COMPLEX_RANGES[mid]
        if cp < a:
            hi = mid - 1
        elif cp > b:
            lo = mid + 1
        else:
            return g
    return 0


def _plain_space(u) -> bool:
    return u.text == " " and len(u.raw) == 1


def run_end(us: list, i: int) -> int:
    """The index one past the last character of the shaped run that starts with us[i] (vf2_game_text.units), or 0 when
    the run is that one character (b200shape.h RunEnd)."""
    group = script_group(ord(us[i].text[0]))
    if not group:
        return 0
    n = len(us)
    end, units, size, last_space, capped = i + 1, 1, len(us[i].raw), -1, False
    k = i + 1
    while k < n:
        v = us[k]
        if script_group(ord(v.text[0])) == group:
            if units >= MAX_RUN_UNITS or size + len(v.raw) > MAX_RUN_BYTES:
                capped = True
                break
            end = k = k + 1
            size += len(v.raw)
            units += 1
            continue
        if not _plain_space(v):
            break
        q = k
        while q < n and _plain_space(us[q]):
            q += 1
        if q >= n or script_group(ord(us[q].text[0])) != group:
            break
        spaces = q - k
        if units + spaces >= MAX_RUN_UNITS or size + spaces > MAX_RUN_BYTES:
            capped = True
            break
        last_space = k
        units += spaces
        size += spaces
        k = q
    if capped and last_space > i:
        end = last_space
    return end if end > i + 1 else 0
