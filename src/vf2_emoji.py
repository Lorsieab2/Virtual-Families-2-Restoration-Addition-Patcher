"""Which whole characters are emoji shown as pictures (colour emoji): the one rule of the patcher's tools and of the
Unicode text DLL (runtime/native/b200unicode/b200emoji.h is the same table, written by emoji_table_c and checked by
tests/test_colour_emoji.py). The same rule and table as Virtual Families 1 (patcher/vf1_emoji.py).

A whole character (grapheme cluster) is a colour emoji when nothing in it asks for text presentation (U+FE0E) and
* a code point of it has Emoji_Presentation (an emoji shown as a picture by default: faces, animals, flags'
  regional indicators, skin tones), or
* it holds U+FE0F (emoji presentation asked for, as in a red heart), a keycap U+20E3, a skin tone (U+1F3FB..U+1F3FF)
  or a tag character (U+E0020..U+E007F, subdivision flags).
A joined sequence (U+200D) is a colour emoji when any of its parts is.
"""
from __future__ import annotations

# Unicode 18.0's Emoji_Presentation (emoji-data.txt), as Virtual Families 1's table (its tests compare it with
# Windows' ICU: every emoji ICU knows is in it).
EMOJI_PRESENTATION_RANGES: tuple[tuple[int, int], ...] = (
    (0x231A, 0x231B), (0x23E9, 0x23EC), (0x23F0, 0x23F0), (0x23F3, 0x23F3), (0x25FD, 0x25FE), (0x2614, 0x2615),
    (0x2648, 0x2653), (0x267F, 0x267F), (0x2693, 0x2693), (0x26A1, 0x26A1), (0x26AA, 0x26AB), (0x26BD, 0x26BE),
    (0x26C4, 0x26C5), (0x26CE, 0x26CE), (0x26D4, 0x26D4), (0x26EA, 0x26EA), (0x26F2, 0x26F3), (0x26F5, 0x26F5),
    (0x26FA, 0x26FA), (0x26FD, 0x26FD), (0x2705, 0x2705), (0x270A, 0x270B), (0x2728, 0x2728), (0x274C, 0x274C),
    (0x274E, 0x274E), (0x2753, 0x2755), (0x2757, 0x2757), (0x2795, 0x2797), (0x27B0, 0x27B0), (0x27BF, 0x27BF),
    (0x2B1B, 0x2B1C), (0x2B50, 0x2B50), (0x2B55, 0x2B55), (0x1F004, 0x1F004), (0x1F0CF, 0x1F0CF), (0x1F18E, 0x1F18E),
    (0x1F191, 0x1F19A), (0x1F1E6, 0x1F1FF), (0x1F201, 0x1F201), (0x1F21A, 0x1F21A), (0x1F22F, 0x1F22F),
    (0x1F232, 0x1F236), (0x1F238, 0x1F23A), (0x1F250, 0x1F251), (0x1F300, 0x1F320), (0x1F32D, 0x1F335),
    (0x1F337, 0x1F37C), (0x1F37E, 0x1F393), (0x1F3A0, 0x1F3CA), (0x1F3CF, 0x1F3D3), (0x1F3E0, 0x1F3F0),
    (0x1F3F4, 0x1F3F4), (0x1F3F8, 0x1F43E), (0x1F440, 0x1F440), (0x1F442, 0x1F4FC), (0x1F4FF, 0x1F53D),
    (0x1F54B, 0x1F54E), (0x1F550, 0x1F567), (0x1F57A, 0x1F57A), (0x1F595, 0x1F596), (0x1F5A4, 0x1F5A4),
    (0x1F5FB, 0x1F64F), (0x1F680, 0x1F6C5), (0x1F6CC, 0x1F6CC), (0x1F6D0, 0x1F6D2), (0x1F6D5, 0x1F6D9),
    (0x1F6DC, 0x1F6DF), (0x1F6EB, 0x1F6EC), (0x1F6F4, 0x1F6FC), (0x1F7E0, 0x1F7EB), (0x1F7F0, 0x1F7F0),
    (0x1F90C, 0x1F93A), (0x1F93C, 0x1F945), (0x1F947, 0x1F9FF), (0x1FA70, 0x1FA7C), (0x1FA80, 0x1FAC6),
    (0x1FAC8, 0x1FAC8), (0x1FACC, 0x1FADD), (0x1FADF, 0x1FAEB), (0x1FAEF, 0x1FAFA),
)

TEXT_PRESENTATION = 0xFE0E
EMOJI_PRESENTATION_SELECTOR = 0xFE0F
KEYCAP = 0x20E3


def is_emoji_presentation(cp: int) -> bool:
    lo, hi = 0, len(EMOJI_PRESENTATION_RANGES) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        a, b = EMOJI_PRESENTATION_RANGES[mid]
        if cp < a:
            hi = mid - 1
        elif cp > b:
            lo = mid + 1
        else:
            return True
    return False


def is_colour_emoji(cluster: str) -> bool:
    """Whether one whole character is drawn as a colour picture (the DLL's IsColourEmoji)."""
    cps = [ord(c) for c in cluster]
    if TEXT_PRESENTATION in cps:
        return False
    return any(is_emoji_presentation(cp) or cp in (EMOJI_PRESENTATION_SELECTOR, KEYCAP) or 0x1F3FB <= cp <= 0x1F3FF
               or 0xE0020 <= cp <= 0xE007F for cp in cps)


def emoji_table_c() -> str:
    """runtime/native/b200unicode/b200emoji.h (generated, never edited by hand)."""
    lines = ["// GENERATED from src/vf2_emoji.py (EMOJI_PRESENTATION_RANGES) by tests/test_colour_emoji.py's rule. Do not",
             "// edit: the patcher's tools and the Unicode text DLL must pick the same colour emoji.",
             "#pragma once",
             f"static const unsigned kEmojiPresentation[{len(EMOJI_PRESENTATION_RANGES)}][2] = {{"]
    row: list[str] = []
    for a, b in EMOJI_PRESENTATION_RANGES:
        row.append(f"{{0x{a:X},0x{b:X}}}")
        if len(row) == 6:
            lines.append("    " + ",".join(row) + ",")
            row = []
    if row:
        lines.append("    " + ",".join(row) + ",")
    lines.append("};")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    from pathlib import Path
    out = Path(__file__).resolve().parents[1] / "runtime" / "native" / "b200unicode" / "b200emoji.h"
    out.write_text(emoji_table_c(), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
