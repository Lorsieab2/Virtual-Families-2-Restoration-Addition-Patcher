"""Nothing runs off the screen (B209; the owner: "i dont care if things run out of boxes, they just need to not run off
the screen"; the same rule as Virtual Families 1).

* The model (src/vf2_screen_edge.py): move, cut with "…", keep the lines that fit, the English when not even "…"
  fits; the editor's too_wide and Wrap to fit (never inside a placeholder).
* The game, in emulation (Unicorn, the real B208 core exe + the real test DLL, real GDI, a 1024 x 768 screen):
  DrawString moves and cuts exactly as the model, pixel for pixel; every translatable line at its longest room, and
  worst-case CJK, Arabic and emoji lines, drawn at the right edge, centred, past the left edge and at the bottom,
  stay on the screen; the game's own DrawStringJustified box is moved to the edge and a paragraph taller than the
  screen is cut; the stock English text with no translation chosen is drawn exactly as before (even off the screen),
  and with a translation chosen it is kept on the screen too.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "tests"))

import vf2_game_text as T  # noqa: E402
import vf2_screen_edge as E  # noqa: E402

from test_b200_unicode_dll import GAME_IMAGES, DrawWorld, dlls, exe  # noqa: E402,F401

SW, SH = E.SCREEN_W, E.SCREEN_H
CJK = "日本語の文章" * 40
ARABIC = "مرحبا بكم " * 30
EMOJI = "\U0001F600\U0001F44D\U0001F3FD❤️" * 40


# ---------------------------------------------------------------------------------------------- the model
def test_wrap_to_fit_breaks_long_lines_and_never_a_placeholder():
    fonts = {n: T.load_font(n) for n in E.DRAWN_FONTS}
    line = "Bonjour {name}, " + "la famille est très heureuse aujourd'hui " * 8 + "%d"
    assert E.too_wide(fonts, line)
    wrapped = E.wrap_to_fit(fonts, line)
    assert not E.too_wide(fonts, wrapped) and "\n" in wrapped
    assert "{name}" in wrapped and "%d" in wrapped.split("\n")[-1]
    assert wrapped.replace("\n", " ").split() == line.split()
    assert E.wrap_to_fit(fonts, "Short line") == "Short line"


# ---------------------------------------------------------------------------------------------- the game, emulated
@pytest.fixture(scope="module")
def world(exe, dlls, tmp_path_factory):
    if not (GAME_IMAGES / "Segoe24.png").is_file():
        pytest.skip("no original game folder (work/vanilla_runtime_payload)")
    import vf2_glyph_maker as M
    import vf2_glyph_render as R
    if not R.available():
        pytest.skip("needs Windows' GDI")
    folder = tmp_path_factory.mktemp("screen")
    M.write_sheets(GAME_IMAGES, folder)
    w = DrawWorld(exe, dlls[1], folder)
    w.game_seams(w.s)
    from test_unicode_font import RealGdi, _kernel_seams
    w.real_gdi = RealGdi(w.e, {})
    _kernel_seams(w.e)
    e = w.e
    e.w32(w.window + 0x30, w._surface(SW, SH, b"\0" * SW * SH * 4))          # the game's 1024 x 768 screen
    # vf2tr_b200.dll, when a test chooses a translation: its status block (installed) and B200Tr_EnglishOf
    w.tr_handle, w.tr_on, w.english = 0x7400_0000, False, {}
    w.tr_status = e.alloc(0x40)
    e.write(w.tr_status, struct.pack("<IIIII", 0x54545246, 1, 1, 1, 1))
    english_of = e.fake_code(b"\xC3")

    def english(em):
        return w.english.get(em.arg(0), 0), 0
    e.seam_live(english_of, english)
    module = e.imports["GetModuleHandleW"]

    def get_module(em):
        if em.arg(0) and em.wstr(em.arg(0)).lower() == "vf2tr_b200.dll":
            return (w.tr_handle if w.tr_on else 0), 4
        return module(em)
    proc = e.imports["GetProcAddress"]

    def get_proc(em):
        if em.arg(0) == w.tr_handle:
            name = em.cstr(em.arg(1))
            return {"B200Tr_Status": w.tr_status, "B200Tr_EnglishOf": english_of}[name], 8
        return proc(em)
    e.imports.update({"GetModuleHandleW": get_module, "GetProcAddress": get_proc})
    return w, M.load_fonts(GAME_IMAGES)


def _draw(w, name, raw, x, y):
    font, _f, _s = w.font(name)
    text = w.e.alloc(len(raw) + 1)
    w.e.write(text, raw + b"\0")
    w.blits = []
    w.e.call(w.h["draw_string"], (text, x, y, 0xFFFFFFFF, font), ecx=w.window, edx=0)
    return list(w.blits)


def _on_screen(blits):
    return all(0 <= x and x + bw <= SW and 0 <= y and y + bh <= SH for x, y, bw, bh, _d in blits)


def _model(font, sheet, text, x, y, translation=False):
    from test_colour_emoji import _patcher_blits
    shown, mx, my = E.on_screen(font, text, x, y, translation=translation)
    return _patcher_blits(font, sheet, T.encode(shown), (255, 255, 255), mx, my)


@pytest.mark.parametrize("name", ["Segoe24", "Segoe36Bold"])
def test_drawstring_moves_and_cuts_as_the_model(world, name):
    from test_colour_emoji import _same
    w, fonts = world
    font, sheet = fonts[name]
    w.tr_on = False
    cases = [("Zoë " * 30, SW - 100, 10), ("שלום עולם", SW - 20, 10),
             ("Café", -30, SH - 5), (CJK, 5, 5), (ARABIC, 0, 0), ("é\n" * 60, 10, 10),
             ("naïve", 300, 200)]
    for text, x, y in cases:
        game = _draw(w, name, T.encode(text), x, y)
        _same(game, _model(font, sheet, text, x, y), (name, text[:12], x, y))
        assert _on_screen(game), (name, text[:12])
    # wholly off the screen (an animation not yet in view): left alone
    assert all(b[0] >= SW for b in _draw(w, name, T.encode("Café"), SW + 40, 10))


def test_stock_english_is_untouched_without_a_translation_and_kept_on_screen_with_one(world):
    w, fonts = world
    font, sheet = fonts["Segoe24"]
    text = "Plain English text " * 8
    w.tr_on = False
    raw = T.encode(text)
    off = _draw(w, "Segoe24", raw, SW - 50, 10)
    assert off[0][0] == SW - 50 and not _on_screen(off)                  # the stock game: as before
    w.tr_on = True
    try:
        on = _draw(w, "Segoe24", raw, SW - 50, 10)
        assert _on_screen(on)
        from test_colour_emoji import _same
        _same(on, _model(font, sheet, text, SW - 50, 10, translation=True), "translation chosen")
    finally:
        w.tr_on = False


def _rooms():
    limits = json.loads((ROOT / "src" / "vf2_translation_limits.json").read_text(encoding="utf-8"))
    rooms = set(limits["strncpy_room"].values())
    patch = json.loads((ROOT / "src" / "vf2_patch_strings.json").read_text(encoding="utf-8"))
    for section in patch.values():
        if isinstance(section, list):
            rooms |= {e["max_length"] for e in section if isinstance(e, dict) and e.get("max_length")}
    rooms |= {300, 600, 1199}                         # lines the game copies by their English length can be long
    return sorted(r for r in rooms if 1 <= r < 1200)


@pytest.mark.parametrize("name", ["Segoe24", "Segoe36Bold"])
def test_every_translatable_line_at_its_longest_stays_on_the_screen(world, name):
    """Every room a translation can fill (the copies' rooms, the patch lines', long free lines), in its widest
    letters (W), and worst-case CJK, Arabic and emoji lines: at the right edge, centred, past the left edge and at the
    bottom, with a translation chosen."""
    w, fonts = world
    font, _sheet = fonts[name]
    w.tr_on = True
    try:
        texts = ["W" * r for r in _rooms()] + [CJK, ARABIC, EMOJI, "W" * 200 + "\n" + CJK[:50] + "\n" + ARABIC[:80]]
        for text in texts:
            raw = T.encode(text)
            width = T.get_width(font, raw)
            for x, y in ((SW - 40, 30), (SW // 2 - width // 2, 300), (-25, 100), (100, SH - 10)):
                assert _on_screen(_draw(w, name, raw, x, y)), (name, text[:10], len(text), x, y)
    finally:
        w.tr_on = False


def test_a_dialogs_box_is_moved_to_the_edge_and_a_tall_paragraph_is_cut(world):
    w, fonts = world
    e = w.e
    _status, writes = w.plan(1)
    for wr in writes:
        e.write(wr["va"], wr["bytes"])
    font_obj, _f, _s = w.font("Segoe24")
    e.w32(e.r32(font_obj + 4), w.s["FONT_VTABLE"])
    self_ = e.alloc(16)
    e.w32(self_, w.window)
    font, _sheet = fonts["Segoe24"]

    def draw(text, x, y, box):
        raw = T.encode(text)
        p = e.alloc(len(raw) + 1)
        e.write(p, raw + b"\0")
        w.blits = []
        e.call(w.h["draw_justified"], (p, x, y, box, 0xFFFFFFFF, font_obj, 0, 0, 0), ecx=self_, edx=0)
        return list(w.blits)
    para = "Une très longue phrase de dialogue qui continue encore et encore. " * 6
    blits = draw(para, SW - 100, 50, 300)
    _t, mx, _my, mbox = E.wrap_on_screen(font, para, SW - 100, 50, 300)
    assert mx == SW - 300 and min(b[0] for b in blits) == mx and _on_screen(blits)
    tall = draw("été " * 2000, 10, 10, 400)                   # wraps far taller than the screen
    assert _on_screen(tall) and max(b[1] + b[3] for b in tall) <= SH
    wide = draw(CJK, -50, 10, 2000)                                        # a box wider than the screen
    assert _on_screen(wide)


# ---------------------------------------------------------------------------------------------- the Translations DLL alone
@pytest.fixture(scope="module")
def tr_world(tmp_path_factory):
    """vf2tr_b200.dll's own test build with a translation installed, no Unicode text DLL: the real executable, the
    game's stock DrawString / DrawStringJustified / GetWidth / GetNextJustifiedLine, the screen 1024 x 768."""
    import os
    import subprocess
    vc = os.environ.get("VF2_VCVARS32")
    exe_path = os.environ.get("VF2_UNICODE_EXE") or os.environ.get("VF2_B200_CORE_EXE")
    core = os.environ.get("VF2_B200_CORE_EXE")
    if not vc or not exe_path or not core or not (GAME_IMAGES / "Segoe24.png").is_file():
        pytest.skip("needs VF2_VCVARS32, the executables and the original game folder")
    pytest.importorskip("unicorn")
    out = tmp_path_factory.mktemp("trscreen")
    r = subprocess.run(["cmd.exe", "/d", "/c", str(ROOT / "runtime" / "native" / "build_b200tr.bat"), "test"],
                       env=dict(os.environ, VF2_TR_BUILD_DIR=str(out)), capture_output=True, text=True)
    dll = out / "vf2tr_b200_test.dll"
    assert dll.is_file(), r.stdout + r.stderr
    import b200_translations_scenarios as TS
    from test_b200_unicode_dll import DrawWorld as D
    w = TS.World(exe_path, dll, core=core)
    import vf2_picture_image as P

    class Draw:                                        # DrawWorld's SDL and font seams, over this world's emulator
        _surface, _create, _map, _get, _upper_blit, font = (D._surface, D._create, D._map, D._get, D._upper_blit,
                                                             D.font)
    d = Draw()
    d.e, d.P, d.surfaces, d.blits, d.fonts = w.e, P, {}, [], {}
    w.e.bind_exe_imports({"SDL_UpperBlit": d._upper_blit})
    w.e.imports["HeapFree"] = lambda em: (1, 12)
    d.window = w.e.alloc(0x100)
    w.e.w32(d.window + 0x30, d._surface(SW, SH, b"\0" * SW * SH * 4))
    for off, v in ((0x60, 0), (0x64, 0), (0x68, 4096), (0x6C, 4096)):
        w.e.w32(d.window + off, v)
    assert w.install(TS.make_file(w, {113: "R\u00e9essayer"})) == 1
    order = len(w.protect_calls)
    assert w.e.call(w.e.dll_export("B200Tr_TestScreenEdge")) == 1
    import gen_b200_unicode_sites as G
    from test_b200_unicode_dll import OBJS
    resolved = G.resolve(G.Exe(Path(exe_path)), G.load_pins(OBJS))
    sites = dict(resolved["sites"], FONT_VTABLE=resolved["font_vtable"])
    real_font = d.font

    def font(name):                                    # the font object with its own vtable, as ldwFont::Load makes it
        obj = real_font(name)
        w.e.w32(w.e.r32(obj[0] + 4), sites["FONT_VTABLE"])
        return obj
    d.font = font
    return w, d, sites, order


def test_the_translations_dll_alone_writes_two_jumps_after_executable_trampolines(tr_world):
    w, _d, sites, order = tr_world
    e = w.e
    for name in ("DRAW_STRING", "DRAW_JUSTIFIED"):
        at = sites[name]
        assert e.read(at, 1) == b"\xE9"
        target = (at + 5 + struct.unpack("<i", e.read(at + 1, 4))[0]) & 0xFFFFFFFF
        assert target >= 0x30000000                                  # into the DLL
    protects = w.protect_calls[order:]
    rwx_tramps = [p for p in protects if p[2] == 0x40 and p[0] >= 0x30000000]
    entry_writes = [p for p in protects if p[0] in (sites["DRAW_STRING"], sites["DRAW_JUSTIFIED"])]
    assert len(rwx_tramps) == 2 and entry_writes and max(p[3] for p in rwx_tramps) < min(p[3] for p in entry_writes)


def test_the_translations_dll_alone_keeps_drawstring_on_the_screen(tr_world):
    """With a translation and no Unicode DLL, the game's own DrawString (Windows-1252, stock fonts) moved to the edge
    or cut with "..." exactly as the model, pixel for pixel."""
    from test_colour_emoji import _patcher_blits, _same
    w, d, sites, _order = tr_world
    e = w.e
    import vf2_glyph_maker as M
    fonts = M.load_fonts(GAME_IMAGES)
    for name in ("Segoe24", "Segoe36Bold"):
        font_obj, _f, _s = d.font(name)
        font = T.stock_font(fonts[name][0])
        sheet = fonts[name][1]
        for text, x, y in (("Une longue ligne traduite " * 6, SW - 120, 20), ("Caf\u00e9 cr\u00e8me", SW - 30, 40),
                           ("Bonjour", -20, SH - 5), ("W" * 300, 10, 10)):
            raw = text.encode("cp1252")
            p = e.alloc(len(raw) + 1)
            e.write(p, raw + b"\0")
            d.blits = []
            e.call(sites["DRAW_STRING"], (p, x, y, 0xFFFFFFFF, font_obj), ecx=d.window, edx=0)
            game = list(d.blits)
            shown, mx, my = E.on_screen(font, text, x, y, translation=True, ellipsis="...")
            mine = _patcher_blits(font, sheet, shown.encode("cp1252"), (255, 255, 255), mx, my)
            _same(game, mine, (name, text[:10], x))
            assert _on_screen(game), (name, text[:10])


def test_the_translations_dll_alone_moves_a_dialogs_box(tr_world):
    w, d, sites, _order = tr_world
    e = w.e
    font_obj, _f, _s = d.font("Segoe24")
    self_ = e.alloc(16)
    e.w32(self_, d.window)
    text = ("Une tr\u00e8s longue phrase de dialogue qui continue encore et encore. " * 6).encode("cp1252")
    p = e.alloc(len(text) + 1)
    e.write(p, text + b"\0")
    d.blits = []
    e.call(sites["DRAW_JUSTIFIED"], (p, SW - 100, 50, 300, 0xFFFFFFFF, font_obj, 0, 0, 0), ecx=self_, edx=0)
    assert d.blits and _on_screen(d.blits) and min(b[0] for b in d.blits) >= SW - 300
