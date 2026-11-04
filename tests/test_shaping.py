"""Shaped and right-to-left scripts (B209, the shared spec's row 3; the rule of Virtual Villagers and Virtual Families 1).

* The rule: b200shape.h RunEnd (built into the text test DLL) and src/vf2_shaping.run_end find the same runs.
* The drawing: a run is one piece drawn whole by Windows (Uniscribe shapes it and puts it in visual order): an Arabic
  word is joined and a Hebrew one runs right to left, unlike the same letters drawn one at a time.
* The game, in emulation (Unicorn, the real B208 core exe + the real test DLL, this machine's real GDI): DrawString and
  GetWidth of Arabic, Hebrew, Hindi, Thai and mixed texts give exactly the patcher's pieces, places and pixels
  (src/vf2_game_text.draw_string / get_width) in two fonts and two text colours; text with no such letter is drawn as
  before (tests/test_b200_unicode_dll.py's draw tests run unchanged).
"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "tests"))

import vf2_game_text as T  # noqa: E402
import vf2_shaping as S  # noqa: E402

from test_b200_unicode_dll import GAME_IMAGES, DrawWorld, dlls, exe  # noqa: E402,F401
from test_b200_unicode_text import lib  # noqa: E402,F401

TEXTS = [
    "مرحبا بكم",                      # Arabic: welcome
    "שלום עולם",                      # Hebrew: hello world
    "नमस्ते दुनिया",  # Hindi
    "สวัสดีครับ",          # Thai
    "Zoë שלום 12 مرحبا!",  # mixed
    "א b",                                                                # one letter: not a run
]


# ---------------------------------------------------------------------------------------------- the rule
def _c_runs(lib, raw: bytes) -> list[int]:
    lib.UtRuns.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32]
    lib.UtRuns.restype = ctypes.c_uint32
    ends = (ctypes.c_uint32 * (len(raw) + 1))()
    k = lib.UtRuns(raw, len(raw), ends, len(raw) + 1)
    return list(ends[:k])


def _py_runs(raw: bytes) -> list[int]:
    us = T.units(raw)
    starts, at = [], 0
    for u in us:
        starts.append(at)
        at += len(u.raw)
    out = []
    for i in range(len(us)):
        e = S.run_end(us, i)
        out.append(0 if not e else (starts[e] if e < len(us) else at))
    return out


def test_the_dll_and_python_find_the_same_runs(lib):
    long_hebrew = " ".join(["שלום"] * 30)          # past the 64-character cap: cut at a space
    texts = TEXTS + [long_hebrew, "مر  مر", "مر a مر",
                     "การ אב", "مر ", " مر"]
    for text in texts:
        raw = T.encode(text)
        assert _c_runs(lib, raw) == _py_runs(raw), text
    us = T.units(T.encode(long_hebrew))
    end = S.run_end(us, 0)
    assert 0 < end < len(us) and us[end].text == " " and end <= S.MAX_RUN_UNITS
    assert _py_runs(T.encode("א b"))[0] == 0                        # one character is not a run


def test_a_run_is_shaped_and_in_visual_order():
    import vf2_glyph_render as R
    if not R.available():
        pytest.skip("needs Windows' GDI")
    font = T.load_font("Segoe24")
    hebrew = "שלום"
    g = font.run_glyph(hebrew)
    assert g is not None and g.kind == "run"
    # the same letters one at a time, in logical order: the run's picture is their mirror order, not theirs
    singles = [font.glyph(u) for u in T.units(T.encode(hebrew))]
    assert g.width == sum(s.width for s in singles)
    h = font.line_height

    def cols(glyph, x0, w):
        return [bytes(glyph.alpha[y * glyph.width + x0 + x] for y in range(h) for x in range(w))]
    first = singles[0]
    assert cols(g, g.width - first.width, first.width) == cols(first, 0, first.width)    # shin is drawn rightmost
    arabic = "مرحبا"
    joined = font.run_glyph(arabic)
    apart = sum(font.glyph(u).width for u in T.units(T.encode(arabic)))
    assert joined is not None and joined.width < apart                       # joined forms are narrower


# ---------------------------------------------------------------------------------------------- the game, emulated
@pytest.fixture(scope="module")
def world(exe, dlls, tmp_path_factory):
    if not (GAME_IMAGES / "Segoe24.png").is_file():
        pytest.skip("no original game folder (work/vanilla_runtime_payload)")
    import vf2_glyph_maker as M
    import vf2_glyph_render as R
    if not R.available():
        pytest.skip("needs Windows' GDI")
    folder = tmp_path_factory.mktemp("shaping")
    M.write_sheets(GAME_IMAGES, folder)
    w = DrawWorld(exe, dlls[1], folder)
    w.game_seams(w.s)
    from test_unicode_font import RealGdi, _kernel_seams
    w.real_gdi = RealGdi(w.e, {})
    _kernel_seams(w.e)
    return w, M.load_fonts(GAME_IMAGES)


@pytest.mark.parametrize("name", ["Segoe24", "Segoe36Bold"])
def test_the_games_drawstring_draws_runs_as_the_patcher_does(world, name):
    from test_colour_emoji import _draw, _patcher_blits, _same, RED, WHITE
    w, fonts = world
    font, sheet = fonts[name]
    for color, rgb in ((WHITE, (255, 255, 255)), (RED, (255, 0, 0))):
        for text in TEXTS:
            raw = T.encode(text)
            _same(_draw(w, name, raw, color), _patcher_blits(font, sheet, raw, rgb), (name, text))
            assert w.width(name, raw) == T.get_width(font, raw), (name, text)
    kinds = [p.glyph.kind for t in TEXTS for p in T.draw_string(font, T.encode(t), 0, 0)]
    assert kinds.count("run") == 6                                     # each text's run(s); "א b" has none
    st = w.e.dll_export("B200Unicode_Status")
    assert w.e.r32(st + 4) >= 5 and w.e.r32(st + 84) >= 6               # version 5: shapedRuns


def test_a_dialogs_paragraph_draws_a_right_to_left_phrase_whole_and_wraps_it_at_a_space(world):
    """DrawStringJustified (dialogs, events, the store: the game's own wrapping) run whole in emulation: a Hebrew
    phrase that fits the width is one piece, the same pixels as the patcher's run; one wider than the width is cut at
    its space, each part on its own line in visual order, the stock wrapping placing the rest as before."""
    w, fonts = world
    e = w.e
    if not hasattr(w, "justified_ready"):
        _status, writes = w.plan(1)
        for wr in writes:                              # the hooks in place, as the game runs with them
            e.write(wr["va"], wr["bytes"])
        w.justified_ready = True
    font_obj, _f, _s = w.font("Segoe24")
    e.w32(e.r32(font_obj + 4), w.s["FONT_VTABLE"])     # the font object's own vtable (GetCharSourceRect)
    self_ = e.alloc(16)
    e.w32(self_, w.window)
    font, sheet = fonts["Segoe24"]
    phrase = "\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd"
    whole = font.run_glyph(phrase)
    first, second = font.run_glyph("\u05e9\u05dc\u05d5\u05dd"), font.run_glyph("\u05e2\u05d5\u05dc\u05dd")
    lh = font.line_height

    def draw(width):
        raw = T.encode(phrase + " abc")
        p = e.alloc(len(raw) + 1)
        e.write(p, raw + b"\0")
        w.blits = []
        e.call(w.h["draw_justified"], (p, 10, 20, width, 0xFFFFFFFF, font_obj, 0, 0, 0), ecx=self_, edx=0)
        return list(w.blits)
    wide = draw(400)
    letters = [font.glyph(u).width for u in T.units(b"abc")]
    space = font.glyph(T.units(b" ")[0]).width + font.kerning
    x = 10 + whole.width + font.kerning + space
    want = [(10, 20, whole.width, lh)]
    for lw in letters:
        want.append((x, 20, lw, lh))
        x += lw + font.kerning
    assert [b[:4] for b in wide] == want
    assert wide[0][4][3::4] == whole.alpha                               # the run's own pixels
    narrow = draw(60)
    assert [b[:4] for b in narrow[:2]] == [(10, 20, first.width, lh), (10, 20 + lh, second.width, lh)]
    assert narrow[0][4][3::4] == first.alpha and narrow[1][4][3::4] == second.alpha
