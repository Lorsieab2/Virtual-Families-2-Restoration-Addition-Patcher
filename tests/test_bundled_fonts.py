"""The bundled fonts (runtime/fonts) and the Unicode 18.0 tables.

* every bundled file is byte for byte the verified download its README lists (size, SHA-256), git never changes them,
  and the DLL, the patcher and the exporter name the same files;
* Last Resort's many-to-one character map (cmap format 13) is read: every code point gets its block's glyph;
* the tables are Unicode 18.0.0 from the recorded UnicodeData.txt, equal in the Python and the C header;
* with Windows' GDI: every assigned code point is drawn by some step of the chain (none falls to the missing box);
  unassigned, control and surrogate code points keep the box although Unifont and Last Resort have glyphs for them;
  a bundled face's glyph sits on the game font's baseline inside its line;
* under emulation (the real B208 executable and the built DLL): Startup's font loading asks AddFontResourceExW for
  each bundled file beside the DLL, privately (FR_PRIVATE), and a character only a bundled font has is drawn
  pixel-identical to the patcher's own drawing in all four game fonts.
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "tests"))
FOLDER = ROOT / "runtime" / "fonts"
NATIVE = ROOT / "runtime" / "native" / "b200unicode"

import vf2_glyph_render as R  # noqa: E402
import vf2_unicode_tables as U  # noqa: E402

UCD_SHA256 = "0736451de439ae7baf1425136617da495e09ee5afbe6e394374db7009ea08950"      # UnicodeData.txt 18.0.0


def _table() -> dict:
    rows = {}
    for line in (FOLDER / "README.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) == 8 and cells[1].startswith("`") and re.fullmatch(r"`[0-9a-f]{64}`", cells[5]):
            rows[cells[1].strip("`")] = (int(cells[4].replace(",", "")), cells[5].strip("`"))
    return rows


def test_every_file_is_byte_for_byte_the_verified_download():
    rows = _table()
    assert len(rows) == 11
    for name, (size, sha) in rows.items():
        data = (FOLDER / name).read_bytes()
        assert len(data) == size and hashlib.sha256(data).hexdigest() == sha, name
    assert {p.name for p in FOLDER.iterdir()} == set(rows) | {"README.md"}


def test_the_files_are_never_changed_by_git():
    assert "runtime/fonts/** -text" in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()


def test_the_dll_the_patcher_and_the_exporter_name_the_same_files():
    src = (NATIVE / "b200unicode.cpp").read_text(encoding="utf-8")
    body = re.search(r"kBundledFonts\[\] = \{(.*?)\n\};", src, re.S).group(1)
    assert tuple(re.findall(r'L"([^"]+)"', body)) == R.BUNDLED_FONTS
    exporter = (ROOT / "work" / "export_offline_patch_bundle.py").read_text(encoding="utf-8")
    body = re.search(r"GAME_FONT_FILES = \((.*?)\)\n", exporter, re.S).group(1)
    shipped = tuple(re.findall(r'"([^"]+)"', body))
    assert shipped[:len(R.BUNDLED_FONTS)] == R.BUNDLED_FONTS
    assert set(shipped) == set(_table())                       # the fonts and every licence
    assert 'L"Unicode Text\\\\Fonts\\\\"' in src and 'L"Unicode Font Text\\\\Fonts\\\\"' in src
    assert "AddFontResourceExW(full, FR_PRIVATE, 0)" in src and "InstallBundledFonts();" in src


def _cmap_table(path: Path) -> bytes:
    data = path.read_bytes()
    count = struct.unpack_from(">H", data, 4)[0]
    for i in range(count):
        tag, _sum, off, length = struct.unpack_from(">4sIII", data, 12 + 16 * i)
        if tag == b"cmap":
            return data[off:off + length]
    raise AssertionError("no cmap")


def test_last_resorts_many_to_one_character_map_is_read():
    cm = R.Cmap(_cmap_table(FOLDER / "LastResortHE-Regular.ttf"))
    assert cm.groups and all(len(g) == 4 for g in cm.groups)              # format 13 groups
    assert cm.glyph(0x3D000) and cm.glyph(0x3D000) == cm.glyph(0x3FC3F)   # Seal: one glyph for the block
    assert cm.glyph(0x10FFFD) and cm.glyph(0x0378) and cm.glyph(0x0041)
    assert cm.glyph(0x3D000) != cm.glyph(0x0041)
    assert R.font_file_family((FOLDER / "LastResortHE-Regular.ttf").read_bytes()) == R.BUNDLED_FACES[-1]
    for name, face in zip(R.BUNDLED_FONTS, ("Noto Sans Cuneiform", "Noto Serif Tangut", "Unifont", "Unifont Upper")):
        assert R.font_file_family((FOLDER / name).read_bytes()) == face


def _h_ranges(text: str, name: str) -> tuple:
    body = re.search(name + r"\[\] = \{(.*?)\n\};", text, re.S).group(1)
    return tuple((int(a, 16), int(b, 16)) for a, b in re.findall(r"\{0x([0-9A-F]+)u, 0x([0-9A-F]+)u\}", body))


def test_the_tables_are_unicode_18():
    assert U.UNIDATA_VERSION == "18.0.0" and U.UNIDATA_SHA256 == UCD_SHA256
    h = (NATIVE / "b200unicode_tables.h").read_text(encoding="utf-8")
    assert '#define UT_UNIDATA_VERSION "18.0.0"' in h and f'#define UT_UNIDATA_SHA256 "{UCD_SHA256}"' in h
    assert _h_ranges(h, "UT_EXTEND") == U.EXTEND and _h_ranges(h, "UT_ASSIGNED") == U.ASSIGNED
    assert f"UT_ASSIGNED_COUNT = {len(U.ASSIGNED)}u" in h and f"UT_COMPOSE_COUNT = {len(U.COMPOSE)}u" in h
    # Unicode 18.0: Seal, Tai Yo, Jurchen and the new Armenian letter are assigned; a hole, a control, a surrogate
    # and the noncharacters are not
    for cp in (0x3D000, 0x1E6C0, 0x18E00, 0x0558, 0x0041, 0xE000, 0x10FFFD, 0x17000):
        assert R.is_assigned(cp), hex(cp)
    for cp in (0x0378, 0x0001, 0x007F, 0xD800, 0xDFFF, 0xFFFE, 0xFFFF, 0x110000 - 2, 0x3FC40):
        assert not R.is_assigned(cp), hex(cp)
    # Tolong Siki's letter (new in 18.0) is a letter, not a mark: it starts its own character
    assert not any(a <= 0x11DB0 <= b for a, b in U.EXTEND)
    assert any(a <= 0x1ACF <= b for a, b in U.EXTEND)                    # a new combining mark of 18.0


def test_the_generator_writes_the_committed_tables():
    """With the recorded UnicodeData.txt at hand (VF2_UCD_18), the generator's output is what is committed."""
    ucd = os.environ.get("VF2_UCD_18")
    if not ucd or not Path(ucd).is_file() or hashlib.sha256(Path(ucd).read_bytes()).hexdigest() != UCD_SHA256:
        pytest.skip("set VF2_UCD_18 to Unicode 18.0.0's UnicodeData.txt")
    r = subprocess.run([sys.executable, str(ROOT / "runtime" / "tools" / "gen_b200_unicode_tables.py"), "--ucd", ucd,
                        "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ----------------------------------------------------------------------------------------- with GDI
needs_windows = pytest.mark.skipif(not R.available(), reason="needs Windows' GDI")


@needs_windows
def test_every_assigned_code_point_is_drawn_by_the_chain():
    assert R.load_bundled_fonts() in (0, 5)                 # 0: already loaded by an earlier test in this process
    for face in R.BUNDLED_FACES:
        assert R.cmap(face).groups, face                    # the private font is seen under its name
    assigned = set()
    for a, b in U.ASSIGNED:
        assigned.update(range(a, b + 1))
    covered = set()
    for face in R.FALLBACK_CHAIN:
        covered |= R.cmap(face).covered()
    assert not assigned - covered
    last = R.cmap(R.BUNDLED_FACES[-1]).covered()
    assert assigned <= last                                 # Last Resort alone covers everything
    # a character of each new 18.0 script finds a face, a hole, a control and a surrogate find none
    for cp in (0x3D000, 0x1E6C0, 0x18E00, 0x0558, 0x10940, 0x11DB0, 0x16EA0, 0x12550, 0x17000, 0x10FFFD):
        assert R.font_for(cp) is not None, hex(cp)
    for cp in (0x0378, 0x0001, 0xD800, 0xFFFF, 0x3FC40):
        assert R.has(R.BUNDLED_FACES[-1], cp) and R.font_for(cp) is None, hex(cp)


@needs_windows
def test_a_bundled_glyph_sits_on_the_games_baseline():
    import vf2_game_text as T
    R.load_bundled_fonts()
    for name in T.FONT_NAMES:
        font = T.load_font(name)
        h, base = font.line_height, T.unicode_baseline(font)
        for text, face in (("\U00017000", "Noto Serif Tangut"), ("\u0558", "Unifont"), ("\U00010000", "Unifont Upper"),
                           ("\U0003D000", "Last Resort High-Efficiency")):
            g = T.runtime_glyph(font, text)
            assert g.kind == "runtime" and g.source == face and g.width > 0, (name, text)
            rows = [y for y in range(h) if any(g.alpha[y * g.width:(y + 1) * g.width])]
            assert rows, (name, text)                                   # really drawn, inside the line
            # the ink ends at the baseline (Last Resort's frame reaches a little below it), never above it or below
            # the line
            assert rows[-1] <= base + (h + 3) // 4 and rows[-1] >= base - h // 3, (name, text, rows, base)
            # Unifont is drawn regular in the bold fonts (GDI's synthetic bold smears its outlines into solid blocks):
            # the glyph keeps clear pixels inside its cell
            solid = sum(1 for v in g.alpha if v == 255)
            assert solid < len(g.alpha) // 3, (name, text, solid, len(g.alpha))


# ----------------------------------------------------------------------------------------- under emulation
@pytest.fixture(scope="module")
def built(tmp_path_factory):
    from test_b200_unicode_dll import RUNTIME, _exe, _vcvars, GAME_IMAGES
    if not R.available() or not _vcvars() or _exe() is None or not (GAME_IMAGES / "Segoe24.png").is_file():
        pytest.skip("needs Windows, VF2_VCVARS32, an executable built from this repo (VF2_UNICODE_EXE) and the "
                    "original game folder")
    pytest.importorskip("unicorn")
    pytest.importorskip("pefile")
    out = tmp_path_factory.mktemp("bundled_fonts_build")
    r = subprocess.run(["cmd.exe", "/c", str(RUNTIME / "native" / "build_b200unicode.bat"), "test"],
                       capture_output=True, text=True, env=dict(os.environ, VF2_UNICODE_BUILD_DIR=str(out)))
    assert r.returncode == 0, r.stdout + r.stderr
    return _exe(), out / "vf2unicode_b200_test.dll"


GAME_FOLDER = "C:\\Game\\Virtual Families 2 Patcher Files\\"


@pytest.mark.parametrize("mode,sub,chosen", [(1, "Unicode Text", None), (2, "Unicode Font Text", "Segoe UI"),
                                             (2, "Unicode Font Text", "Unifont")])
def test_the_dll_loads_the_bundled_fonts_privately_and_draws_them_like_the_patcher(built, tmp_path, mode, sub, chosen):
    """chosen = Unifont: Use Unicode Font with a bundled face chosen as the font; it is drawn regular in the bold
    fonts in the game as in the preview (the DLL's WeightFor compares names, the chosen face is its own buffer)."""
    import vf2_game_text as T
    import vf2_glyph_maker as M
    from test_b200_unicode_dll import DrawWorld, GAME_IMAGES
    from test_unicode_font import RealGdi, _kernel_seams
    exe, dll = built
    glyphs = tmp_path / "glyphs"
    M.write_sheets(GAME_IMAGES, glyphs)
    w = DrawWorld(exe, dll, glyphs)
    paths = {f"{GAME_FOLDER}{sub}\\Fonts\\{n}": FOLDER / n for n in R.BUNDLED_FONTS}
    gdi = RealGdi(w.e, paths)
    _kernel_seams(w.e)
    asked = []
    real_add = w.e.imports["AddFontResourceExW"]

    def add_font(em):
        asked.append((em.wstr(em.arg(0)), em.arg(1), em.arg(2)))
        return real_add(em)
    w.e.imports["AddFontResourceExW"] = add_font
    w.e.imports["GetPrivateProfileIntW"] = lambda em: (mode, 16)        # [Patches] Mode= of the setting's ini

    def profile_string(em):                                              # [Font] Face= / [UnicodeFont] Face=
        buf, size = em.arg(3), em.arg(4)
        value = chosen if chosen and em.wstr(em.arg(1)).lower() == "face" else ""
        em.write(buf, (value[:size - 1] + "\0").encode("utf-16-le"))
        return len(value[:size - 1]), 24
    w.e.imports["GetPrivateProfileStringW"] = profile_string
    folder = w.e.alloc(256)
    w.e.write(folder, (GAME_FOLDER + "\0").encode("utf-16-le"))
    assert w.e.call(w.e.dll_export("B200Unicode_TestReadSettings"), (folder,)) == mode
    w.e.call(w.e.dll_export("B200Unicode_TestBundledFonts"))
    assert asked == [(p, 0x10, 0) for p in paths]                       # every file, FR_PRIVATE, in the DLL's order
    assert gdi.calls.count("AddFontResourceExW") == len(R.BUNDLED_FONTS)
    fonts = M.load_fonts(GAME_IMAGES)
    for name in T.FONT_NAMES:
        base, sheet = fonts[name]
        font = T.with_unicode_font(base, chosen) if mode == 2 else base
        # Tangut, the new Armenian letter, Linear B (Unifont Upper), Seal (Last Resort), then mixed with the game's own
        for text in ("\U00017000", "\u0558", "\U00010000", "\U0003D000", "Ab\U00017000\u0558!"):
            raw = T.encode(text)
            game = w.draw(name, raw)
            mine = []
            for p in T.draw_string(font, raw, 3, 5):
                gw, gh, data = T.glyph_pixels(font, p.glyph, sheet)
                mine.append((p.x, p.y, gw, gh, data))
                if p.glyph.kind in ("runtime", "windows") and p.glyph.source != "Segoe UI":
                    assert p.glyph.source in R.BUNDLED_FACES, (name, text, p.glyph.source)
            assert game and any(any(b[4][3::4]) for b in game), (name, text)        # really drawn
            assert [b[:4] for b in game] == [m[:4] for m in mine], (name, text)
            for (x, _y, _w, _h, a), (_x, _yy, _ww, _hh, b) in zip(game, mine):
                assert a[3::4] == b[3::4], (name, text, x)
            assert w.width(name, raw) == T.get_width(font, raw), (name, text)
