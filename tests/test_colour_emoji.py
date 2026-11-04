"""Colour emoji (B209, the shared spec's row 3; the same rule as Virtual Families 1 and Fish and Plant Tycoon).

* The rule: which whole characters are colour emoji (src/vf2_emoji.py), and the DLL's table is the Python's.
* The DLL's own drawing, with this machine's real Direct2D: ColourCell of the test DLL, run through 32-bit rundll32
  (B200Unicode_RunColour), gives every pixel src/vf2_glyph_color.draw gives, in every game font's em and baseline; a
  flag's two letters and a plain letter are not colour (GDI draws them); a face that is not there draws nothing.
* The game side, in emulation (Unicorn, the real B208 core exe + the real test DLL, the game's own GetImage and tint
  cache): with Direct2D failing to start (LoadLibraryExW finds no d2d1.dll in the emulator) every character, emoji
  too, is drawn by GDI exactly as the patcher draws it without colour; with Direct2D (LoadColour and ColourCell
  carried out by the Python drawing the rundll32 test proves equal), every non-emoji glyph is pixel-identical to the
  patcher's, tinted, and the emoji is blitted in its own colours, untinted, in any text colour, a new one included.
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "tests"))

import vf2_emoji as E  # noqa: E402
import vf2_game_text as T  # noqa: E402

from test_b200_unicode_dll import GAME_IMAGES, DrawWorld, dlls, exe  # noqa: E402,F401

NATIVE = ROOT / "runtime" / "native" / "b200unicode"
RUNDLL32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SysWOW64" / "rundll32.exe"
EMOJI = ["\U0001F600", "\u2764\uFE0F", "\U0001F44D\U0001F3FD", "\U0001F468\u200D\U0001F469\u200D\U0001F467",
         "1\uFE0F\u20E3", "\U0001F3F3\uFE0F\u200D\U0001F308", "\u26BD"]


# ---------------------------------------------------------------------------------------------- the rule
def test_the_rule_picks_pictures_not_text():
    for text in EMOJI:
        assert E.is_colour_emoji(text), text
    for text in ("A", "\u263A", "\u2764", "\u2764\uFE0E", "#", "\u00E9"):
        assert not E.is_colour_emoji(text), text
    assert E.is_colour_emoji("\U0001F1EB\U0001F1F7")            # regional indicators have Emoji_Presentation


def test_the_dlls_table_is_the_patchers():
    assert (NATIVE / "b200emoji.h").read_text(encoding="utf-8").replace("\r\n", "\n") == E.emoji_table_c()
    inc = (NATIVE / "b200colour.inc").read_text(encoding="utf-8")
    for needle in ("0xFE0E", "0xFE0F", "0x20E3", "0x1F3FB", "0x1F3FF", "0xE0020", "0xE007F",
                   "D2D1_DRAW_TEXT_OPTIONS_ENABLE_COLOR_FONT", "D2D1_TEXT_ANTIALIAS_MODE_GRAYSCALE",
                   'L"Segoe UI Emoji"', "LOAD_LIBRARY_SEARCH_SYSTEM32"):
        assert needle in inc, needle


# ---------------------------------------------------------------------------------------------- the DLL, real Direct2D
def _need_windows():
    import vf2_glyph_color as C
    if sys.platform != "win32" or not RUNDLL32.is_file() or C.factories() is None:
        pytest.skip("needs Windows' Direct2D and 32-bit rundll32")


def _dll_cells(dll: Path, tmp_path: Path, face: str, em: int, baseline: int, height: int, letters: list[str]):
    out = tmp_path / "cells.bin"
    field = "/".join("+".join(f"{ord(c):X}" for c in t) for t in letters)
    subprocess.run([str(RUNDLL32), f"{dll},B200Unicode_RunColour", f"{out}|{face}|{em}|{baseline}|{height}|{field}"],
                   check=True, timeout=120)
    data, at, cells = out.read_bytes(), 0, []
    for _ in letters:
        w, h = struct.unpack_from("<ii", data, at)
        at += 8
        rgba = data[at:at + w * h * 4] if w > 0 else None
        at += max(w, 0) * h * 4
        cells.append((w, rgba))
    return cells


@pytest.mark.parametrize("name", T.FONT_NAMES)
def test_the_dll_draws_each_emoji_as_the_patcher_does(dlls, tmp_path, name):
    _need_windows()
    import vf2_glyph_color as C
    font = T.load_font(name)
    em, base, h = font.gdi["px"], T.unicode_baseline(font), font.line_height
    letters = EMOJI + ["\U0001F1EB\U0001F1F7", "A"]
    got = _dll_cells(dlls[1], tmp_path, "Segoe UI Emoji", em, base, h, letters)
    for text, (w, rgba) in zip(letters, got):
        want = C.draw(text, em, base, h, "Segoe UI Emoji")
        if want is None:
            assert w == -1 and text in ("\U0001F1EB\U0001F1F7", "A"), text     # no colour: GDI draws it
            continue
        assert (w, rgba) == want, (name, text)
        assert any(rgba[i] != rgba[i + 1] for i in range(0, len(rgba), 4) if rgba[i + 3]), text   # real colour


def test_a_face_that_is_not_there_draws_nothing(dlls, tmp_path):
    _need_windows()
    import vf2_glyph_color as C
    # DirectWrite substitutes a missing family; the Python and the DLL do the same, so they still agree
    got = _dll_cells(dlls[1], tmp_path, "No Such Face At All", 17, 21, 30, ["\U0001F600"])[0]
    assert got == (C.draw("\U0001F600", 17, 21, 30, "No Such Face At All") or (-1, None))


# ---------------------------------------------------------------------------------------------- the game, emulated
def _world(exe, dlls, tmp_path_factory, colour: bool):
    if not (GAME_IMAGES / "Segoe24.png").is_file():
        pytest.skip("no original game folder (work/vanilla_runtime_payload)")
    import vf2_glyph_maker as M
    import vf2_glyph_render as R
    if not R.available():
        pytest.skip("needs Windows' GDI")
    folder = tmp_path_factory.mktemp("colour_text")
    M.write_sheets(GAME_IMAGES, folder)
    w = DrawWorld(exe, dlls[1], folder)
    w.game_seams(w.s)
    from test_unicode_font import RealGdi, _kernel_seams
    w.real_gdi = RealGdi(w.e, {})
    _kernel_seams(w.e)
    e = w.e
    out = e.alloc(8)
    e.call(e.dll_export("B200Unicode_TestColour"), (out,))
    load, cell = e.r32(out), e.r32(out + 4)
    w.colour_calls = []
    if colour:
        import vf2_glyph_color as C
        e.seam_live(load, lambda em: (1, 0))

        def colour_cell(em):
            face, size, base, height = em.wstr(em.arg(0)), em.arg(1), em.arg(2), em.arg(3)
            units = em.arg(5)
            text = em.read(em.arg(4), 2 * units).decode("utf-16-le", "surrogatepass")
            w.colour_calls.append((face, size, base, height, text))
            drawn = C.draw(text, size, base, height, face)
            if drawn is None:
                return 0xFFFFFFFF, 0
            width, rgba = drawn
            assert len(rgba) <= em.arg(7)
            em.write(em.arg(6), rgba)
            return width, 0
        e.seam_live(cell, colour_cell)
    return w


def _add_tint(w, name, color):
    """A tinted copy of the font's sheet as it is now, put first in the font's tint cache (ldwFontImpl +41Ch: nodes
    {colour, surface, next}), as the game's GetImage makes one the first time a text colour is drawn: every pixel AND
    (r, g, b, FFh). (The emulator does not run SDL2.dll's surface code that GetImage would call.)"""
    e = w.e
    font, _f, _s = w.font(name)
    impl = e.r32(font + 4)
    sheet = e.r32(e.r32(impl + 0x0C))
    sw, sh, pixels = w.surfaces[sheet]
    mask = (color & 0xFF) | (((color >> 8) & 0xFF) << 8) | (((color >> 16) & 0xFF) << 16) | 0xFF000000   # ABGR
    data = bytearray(e.read(pixels, sw * sh * 4))
    for i in range(0, len(data), 4):
        v = struct.unpack_from("<I", data, i)[0] & mask
        struct.pack_into("<I", data, i, v)
    surf = w._surface(sw, sh, bytes(data))
    node = e.alloc(12)
    e.w32(node, color)
    e.w32(node + 4, surf)
    e.w32(node + 8, e.r32(impl + 0x41C))
    e.w32(impl + 0x41C, node)


def _draw(w, name, raw, color, x=3, y=5):
    font, _f, _sheet = w.font(name)
    if color != WHITE and (name, color) not in getattr(w, "tints", set()):
        _add_tint(w, name, color)                     # a new text colour: its tinted copy made now, from the sheet
        w.tints = getattr(w, "tints", set()) | {(name, color)}
    text = w.e.alloc(len(raw) + 1)
    w.e.write(text, raw + b"\0")
    w.blits = []
    w.e.call(w.h["draw_string"], (text, x, y, color, font), ecx=w.window, edx=0)
    return list(w.blits)


def _status(w):
    st = w.e.dll_export("B200Unicode_Status")
    return {"version": w.e.r32(st + 4), "runtime": w.e.r32(st + 32), "colour": w.e.r32(st + 80)}


def _patcher_blits(font, sheet, raw, rgb, x=3, y=5):
    out = []
    for p in T.draw_string(font, raw, x, y):
        gw, gh, data = T.glyph_pixels(font, p.glyph, sheet, rgb)
        out.append((p.x, p.y, gw, gh, data))
    return out


def _same(game, mine, text):
    assert [(x, y, ww, hh) for x, y, ww, hh, _d in game] == [(x, y, ww, hh) for x, y, ww, hh, _d in mine], text
    for (x, _y, _w, _h, a), (_x, _yy, _ww, _hh, b) in zip(game, mine):
        assert a[3::4] == b[3::4], (text, x)                              # the same alpha everywhere
        for i in range(0, len(a), 4):
            if a[i + 3]:
                assert a[i:i + 3] == b[i:i + 3], (text, x, i)                 # the same colour where it shows


TEXTS = ["Hi \U0001F600 there", "\u2764\uFE0F Zo\u00EB \U0001F44D\U0001F3FD", "Plain text, no emoji"]
RED, GREEN, WHITE = 0xFF0000FF, 0xFF00FF00, 0xFFFFFFFF


@pytest.mark.parametrize("name", ["Segoe24", "Segoe32Bold"])
def test_without_direct2d_every_character_is_drawn_by_gdi_as_before(exe, dlls, tmp_path_factory, name, monkeypatch):
    import vf2_glyph_color as C
    w = _world(exe, dlls, tmp_path_factory, colour=False)
    monkeypatch.setattr(C, "factories", lambda: None)                 # the patcher without colour: GDI, tinted
    font = T.load_font(name)
    sheet = w.P.load_png(GAME_IMAGES / font.image)
    import vf2_glyph_maker as M
    font, sheet = M.load_fonts(GAME_IMAGES)[name]
    for text in TEXTS:
        raw = T.encode(text)
        _same(_draw(w, name, raw, RED), _patcher_blits(font, sheet, raw, (255, 0, 0)), text)
    st = _status(w)
    assert st["version"] >= 4 and st["colour"] == 0 and st["runtime"] > 0


@pytest.mark.parametrize("name", ["Segoe24", "Segoe32Bold"])
def test_with_direct2d_emoji_keep_their_colours_and_every_other_glyph_is_unchanged(exe, dlls, tmp_path_factory, name):
    _need_windows()
    import vf2_glyph_maker as M
    w = _world(exe, dlls, tmp_path_factory, colour=True)
    font, sheet = M.load_fonts(GAME_IMAGES)[name]
    for color, rgb in ((WHITE, (255, 255, 255)), (RED, (255, 0, 0)), (GREEN, (0, 255, 0))):   # GREEN: a new tint
        for text in TEXTS:
            raw = T.encode(text)
            game = _draw(w, name, raw, color)
            mine = _patcher_blits(font, sheet, raw, rgb)
            _same(game, mine, (text, hex(color)))
            kinds = [p.glyph.kind for p in T.draw_string(font, raw, 3, 5)]
            assert ("colour" in kinds) == (text != TEXTS[2]), (text, kinds)
    assert _status(w)["colour"] == 3                                   # three emoji, each drawn once
    em, base, h = font.gdi["px"], T.unicode_baseline(font), font.line_height
    assert {c[1:4] for c in w.colour_calls} == {(em, base, h)}
    assert {c[0] for c in w.colour_calls} == {"Segoe UI Emoji"}
