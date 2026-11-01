"""The Picture Maker's fonts (src/vf2_art_fonts.py).

Always run: the glyph tables' shape, the character names, the colouring rule on a fixed pixel.

With the B200 desktop objects and the original game (else skipped): each font class's constructor runs in Unicorn
(ldwFont::Load -> ldwFontImpl::Load over the real picture) and every character's glyph (GetCharSourceRect) must be
the module's; the height and the spacing must be the module's; ldwGameWindowImpl::DrawString draws every sample line
and its blits (glyph, place) must be the module's layers, and ldwFontImpl::GetImage's coloured copy of the real
pixels must be the module's colouring; the colours passed with each font must be what the code passes
(vf2_fonts_emu.font_colours), and the font ids the code asks for must leave Segoe24 unused.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("UC_IGNORE_REG_BREAK", "1")

import vf2_art_fonts as fonts  # noqa: E402
import vf2_game_pictures as gp  # noqa: E402
import vf2_picture_image as pi  # noqa: E402

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE_GAME = (GAME_DIR / "Images" / "Segoe24.png").is_file()
HAVE_OBJECTS = (OBJ_DIR / "ldwFontImpl.obj").is_file() and (OBJ_DIR / "Segoe36Bold.obj").is_file()
try:
    import unicorn  # noqa: F401
    HAVE_UNICORN = True
except ImportError:                                     # pragma: no cover
    HAVE_UNICORN = False
needs_game = pytest.mark.skipif(not HAVE_GAME, reason="no original game folder (work/vanilla_runtime_payload)")
needs_code = pytest.mark.skipif(not (HAVE_GAME and HAVE_OBJECTS and HAVE_UNICORN),
                                reason="no B200 desktop object files, no original game folder or no unicorn")


# ====================================================================== always
def test_the_tables():
    assert fonts.font_files() == ["Segoe24.png", "Segoe24Bold.png", "Segoe32Bold.png", "Segoe36Bold.png"]
    for name in fonts.NAMES:
        height, rows = fonts.table(name)
        assert len(rows) == 190 and [c for c, _r in rows] == list(fonts.CHARS)
        assert all(r[3] - r[1] == height for _c, r in rows)
    assert fonts.table("Segoe24")[0] == 19 and fonts.table("Segoe36Bold")[0] == 29
    assert fonts.glyph("Segoe24", 5) == fonts.glyph("Segoe24", ord("!")) == (0, 0, 5, 19)
    assert fonts.char_name(32) == "space" and fonts.char_name(0xE9) == "\"\u00e9\" (character 233)"


def test_the_colouring_is_an_and():
    image = pi.Image(1, 1)
    image.data[:] = bytes((0xF0, 0x0F, 0xAA, 0x80))
    assert bytes(fonts.tint(image, 0xFF33CC0F).data) == bytes((0xF0 & 0x0F, 0x0F & 0xCC, 0xAA & 0x33, 0x80))
    assert fonts.tint(image, 0xFFFFFFFF) is image


# ====================================================================== the game's code
@pytest.fixture(scope="module")
def rig():
    import vf2_fonts_emu as fe
    return fe.FontRig(OBJ_DIR, GAME_DIR)


@needs_code
@pytest.mark.parametrize("name", fonts.NAMES)
def test_every_glyph_is_the_games(rig, name):
    impl = rig.impl(name)
    e = rig.e
    height, rows = fonts.table(name)
    assert rig.names[e.r32(impl + 0xC)] == f"{name}.png"           # the picture the loader asked for
    assert (e.s32(impl + 4), e.s32(impl + 8)) == (height, fonts.SPACING)
    for ch in range(256):
        assert rig.char_rect(name, ch) == fonts.glyph(name, ch), (name, ch)


@needs_code
@pytest.mark.parametrize("name", [n for n in fonts.NAMES if n in fonts.COLOURS])
def test_every_line_is_drawn_as_the_game_draws_it(rig, name):
    files = gp.GameFiles(GAME_DIR)
    picture = rig.picture_surface(name)
    for colour, _words, _sites in fonts.COLOURS[name]:
        blits = rig.draw_string(name, fonts.SAMPLE_TEXT.encode("cp1252"), 0, 0, colour)
        assert all(b[0] == "blit" for b in blits)
        layers = fonts.text_layers(files, name, fonts.SAMPLE_TEXT, colour)
        assert [(b[2], b[3], b[4]) for b in blits] == [(tuple(d.rect), d.x, d.y) for d in layers]
        assert all(d.file == f"{name}.png" for d in layers)
        surfaces = {b[1] for b in blits}
        assert len(surfaces) == 1
        surface = surfaces.pop()
        if colour == fonts.WHITE:
            assert surface == picture and all(d.make is None for d in layers)
        else:
            assert surface != picture
            want = fonts.tint(files.image(f"{name}.png"), colour)
            assert rig.pixels(surface) == bytes(want.data)
            d = layers[1]
            assert bytes(d.make(files).data) == bytes(want.sub(d.rect[0], d.rect[1], d.rect[2] - d.rect[0],
                                                               d.rect[3] - d.rect[1]).data)
    # a colour with no alpha is white; a newline goes down the font's height back to the first x
    blits = rig.draw_string(name, b"Ab\ncd", 7, 9, 0x00123456)
    assert blits[0][1] == picture
    layers = fonts.text_layers(files, name, "Ab\ncd", 0x00123456, 7, 9)
    assert [(b[2], b[3], b[4]) for b in blits] == [(tuple(d.rect), d.x, d.y) for d in layers]
    assert all(d.make is None for d in layers)
    assert (layers[2].x, layers[2].y) == (7, 9 + fonts.table(name)[0])


@needs_code
def test_the_colours_are_the_codes():
    import vf2_fonts_emu as fe
    colours, args = fe.font_colours(OBJ_DIR)
    for font_id, name in enumerate(fonts.NAMES):
        got = {c: sorted(s) for c, s in colours.get(font_id, {}).items()}
        want = {c: sorted(s) for c, _w, s in fonts.COLOURS.get(name, ())}
        assert got == want, name
    # Segoe24 (id 0) is never asked for: only ids 1, 2 and 3 are, GetTinyFont is called by no code
    assert sorted(args) == [1, 2, 3]
    assert "Segoe24" in fonts.UNUSED_FONTS and "Segoe24" not in fonts.COLOURS
    import vf2_people_emu as pe
    for path in sorted(OBJ_DIR.glob("*.obj")):
        o = pe.CoffObject(path)
        tiny = [k for k, s in o.symbols.items() if s[0].startswith("?GetTinyFont@theStringManager")]
        for sec in o.sections:
            if sec["name"].startswith(".debug"):
                continue
            assert not any(si in tiny for _va, si, _t in sec["relocs"]), path.stem


@needs_code
def test_the_four_fonts_are_the_only_font_pictures():
    files = gp.GameFiles(GAME_DIR)
    found = sorted(files.relative(n) for n in files.names() if "segoe" in n or "font" in n)
    assert found == fonts.font_files()


@needs_game
def test_the_catalogue_part():
    files = gp.GameFiles(GAME_DIR)
    arts = fonts.arts(files)
    assert len(arts) == 4 * 191 + sum(len(v) for v in fonts.COLOURS.values())
    assert len({a.key for a in arts}) == len(arts)
    for art in arts:
        assert art.category.startswith("Fonts/") and art.checked
        assert art.used == (not art.key.startswith("fonts/Segoe24/"))
    line = next(a for a in arts if a.key == "fonts/Segoe36Bold/line/FFCCCC33")
    image = gp.draw(files, line)
    assert image.height == 29 and image.width > 600
