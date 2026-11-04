"""The fallback chain of Windows fonts for a character the game font lacks is one list, in the shared spec's order
(docs/UNICODE_TEXT.md): the DLL's kChain (runtime/native/b200unicode/b200unicode.cpp) is the patcher's
FALLBACK_CHAIN (src/vf2_glyph_render.py), a face that is not installed is skipped."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vf2_glyph_render as R  # noqa: E402

# The shared spec (UNICODE_SPEC.md, "Fallback chain"), in order. "Yu Gothic (UI)" is the face "Yu Gothic UI".
SPEC = (
    "Segoe UI", "Segoe UI Historic", "Segoe UI Symbol", "Segoe UI Emoji", "Yu Gothic UI", "Meiryo",
    "Microsoft YaHei UI", "Microsoft JhengHei UI", "Malgun Gothic", "SimSun-ExtB", "Nirmala UI", "Ebrima", "Gadugi",
    "Leelawadee UI", "Myanmar Text", "Javanese Text", "Mongolian Baiti", "Microsoft Himalaya", "Microsoft Yi Baiti",
    "Microsoft New Tai Lue", "Microsoft Tai Le", "Microsoft PhagsPa", "Sylfaen", "Cambria Math", "Noto Sans",
    "Noto Sans Symbols", "Noto Sans Symbols 2", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans Math",
    "Noto Sans Cuneiform", "Noto Color Emoji",
    # the bundled fonts (runtime/fonts), loaded for the game only, last
    "Noto Serif Tangut", "Unifont", "Unifont Upper", "Last Resort High-Efficiency",
)


def _dll_chain() -> tuple:
    text = (ROOT / "runtime" / "native" / "b200unicode" / "b200unicode.cpp").read_text(encoding="utf-8")
    body = re.search(r"kChain\[\] = \{(.*?)\n\};", text, re.S).group(1)
    return tuple(re.findall(r'L"([^"]+)"', body))


def test_the_patcher_and_the_dll_use_the_shared_order():
    assert len(SPEC) == 36 and len(set(SPEC)) == 36
    assert tuple(R.FALLBACK_CHAIN) == SPEC
    assert _dll_chain() == SPEC
    assert R.BUNDLED_FACES == SPEC[-4:]


def test_a_face_that_is_not_installed_is_skipped():
    seen = []

    def fake_has(face, cp):
        seen.append(face)
        return face == "Cambria Math"

    original = R.has
    try:
        R.has = fake_has
        assert R.font_for(0x2211) == "Cambria Math"
    finally:
        R.has = original
    assert seen[0] == "Segoe UI" and seen[-1] == "Cambria Math"
