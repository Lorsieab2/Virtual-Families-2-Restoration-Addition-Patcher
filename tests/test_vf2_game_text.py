"""The patcher's one text rule (src/vf2_game_text.py) and its text drawing, checked against the game's own code.

* the stored form: decode / encode / fit / field_bytes, clusters (letters with marks, emoji with skin tones and
  joiners, flags), never cutting inside a character, Latin-1 kept single-byte, ambiguous bytes written as UTF-8;
* with the B200 desktop object files (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) and the original game
  (work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR), else skipped: the four fonts' metrics in
  src/vf2_game_fonts.json are what the game's own ldwFont::Load builds, and for every byte, and for many random
  texts of single bytes (ASCII and Latin-1, the game's own text), the patcher's width, height, line breaking,
  DrawString and DrawChars give exactly what the game's own functions give, glyph by glyph (run under unicorn);
* the unpatched game with a UTF-8 name: its own DrawString / GetWidth / GetNextJustifiedLine run over every UTF-8
  byte and over UTF-8 names at the field limit without leaving the font's table (no crash: odd letters only).
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vf2_game_text as T  # noqa: E402

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE = (OBJ_DIR / "ldwFont.obj").is_file() and (GAME_DIR / "Images" / "Segoe24.png").is_file()


# ---------------------------------------------------------------------------------------------- stored form

def test_ascii_and_latin1_stay_single_bytes():
    assert T.encode("Smith") == b"Smith"
    assert T.encode("José Müller") == "José Müller".encode("latin-1")
    assert T.decode("José Müller".encode("latin-1")) == "José Müller"


def test_other_text_is_utf8_and_round_trips():
    for s in ("Łukasz", "İsmail ığş", "日本語", "中文名字", "𒀀𒀁 cuneiform", "Zoë 👩🏽‍💻", "🇫🇷", "€uro", "Ã©"):
        raw = T.encode(s)
        assert T.decode(raw) == s
    assert T.encode("Ã©") == "Ã©".encode("utf-8")       # its Latin-1 bytes would read as UTF-8 "é"
    assert T.encode("€") == b"\x80"                          # Windows-1252 characters stay one byte
    assert T.encode("Renée “Bo”") == b"Ren\xe9e \x93Bo\x94"
    assert T.encode("€ Ł") == "€ Ł".encode("utf-8")


def test_invalid_utf8_reads_one_byte_per_character():
    assert T.decode(b"caf\xe9") == "café"
    assert T.decode(b"\x80\x96x") == "€–x"               # Windows-1252
    for b in range(0x80, 0xA0):
        if b not in (0x81, 0x8D, 0x8F, 0x90, 0x9D):
            assert T.decode(bytes([b, 0x80])) == bytes([b, 0x80]).decode("cp1252")
    assert T.decode(b"\x81") == "\x81"                    # a byte Windows-1252 leaves out
    assert T.decode(b"ab\0cd") == "ab"


def test_clusters():
    assert T.clusters("éa") == ["é", "a"]
    assert T.clusters("👩🏽‍💻x") == ["👩🏽‍💻", "x"]
    assert T.clusters("🇫🇷🇩🇪") == ["🇫🇷", "🇩🇪"]
    assert T.clusters("a\r\nb") == ["a", "\r\n", "b"]
    assert T.length("Zoë 👩🏽‍💻") == 5


@pytest.mark.parametrize("text", ["Zoë 👩🏽‍💻 and more", "日本語のなまえ", "ab́̂cd", "🇫🇷🇩🇪🇮🇹", "José"])
def test_fit_never_cuts_a_character(text):
    for n in range(0, 30):
        raw = T.fit(text, n)
        assert len(raw) <= n
        back = T.decode(raw)
        assert text.startswith(back)
        cl = T.clusters(text)
        assert back == "".join(cl[:T.length(back)])
        assert T.encode(back) == raw


def test_field_bytes_is_the_field_size_with_a_terminator():
    f = T.field_bytes("Zoë 👩🏽‍💻 and more", 25)
    assert len(f) == 25 and f[-1] == 0 and T.decode(f) == "Zoë 👩🏽‍💻 and"[:len(T.decode(f))]


# ---------------------------------------------------------------------------------------------- the game's code

@pytest.fixture(scope="module")
def rig():
    if not HAVE:
        pytest.skip("no B200 desktop object files or no original game folder")
    pytest.importorskip("unicorn")
    from vf2_font_emu import FontRig
    return FontRig(OBJ_DIR, GAME_DIR / "Images")


@pytest.fixture(scope="module")
def fonts():
    return {n: T.load_font(n) for n in T.FONT_NAMES}


def test_metrics_are_the_games_own(rig):
    data = json.loads(T.FONTS_JSON.read_text(encoding="utf-8"))["fonts"]
    for name in T.FONT_NAMES:
        t = rig.table(name)
        for key in ("line_height", "kerning", "sheet", "image", "glyphs", "charmap"):
            assert data[name][key] == t[key], (name, key)


def test_every_byte_has_the_games_rectangle(rig, fonts):
    for name, f in fonts.items():
        for b in range(1, 256):
            l, t, r, bt = rig.source_rect(name, b if b < 0x80 else b - 0x100)
            assert f.stock_rect(b) == (l, t, l + r - l, bt) or f.stock_rect(b) == (l, t, r, bt)


def _random_single_byte(rng, n):
    """A text in the single-byte stored form (bytes that would read as UTF-8 are UTF-8 text, drawn otherwise)."""
    pool = [0x20] * 6 + [0x0A] + list(range(0x21, 0x7F)) + list(range(0xA2, 0x100))
    while True:
        raw = bytes(rng.choice(pool) for _ in range(n))
        if not T.is_utf8(raw):
            return raw


def _norm(placements):
    out = []
    for p in placements:
        g = p.glyph
        assert g.kind == "game"
        out.append(("blit", g.rect, p.x, p.y, 1.0))
    return out


def test_width_height_and_drawing_match_the_game(rig, fonts):
    rng = random.Random(2026_11_01)
    samples = [b"", b"Hi!", b"The Smith Family", b"a\nb", b"\n\nx", "Zoë Müller".encode("latin-1")]
    samples += [_random_single_byte(rng, rng.randint(1, 40)) for _ in range(150)]
    for name, f in fonts.items():
        for raw in samples:
            assert T.get_width(f, raw) == rig.width(name, raw), (name, raw)
            assert T.get_width(f, raw, 0.75) == rig.width(name, raw, 0.75), (name, raw)
            assert T.get_height(f, raw) == rig.height(name, raw), (name, raw)
            assert _norm(T.draw_string(f, raw, 7, 11)) == rig.draw_string(name, raw, 7, 11), (name, raw)
            for count in (0, 1, len(raw) // 2, len(raw), len(raw) + 3):
                adv, pl = T.draw_chars(f, raw, count, 5, 9)
                g_adv, g_bl = rig.draw_chars(name, raw, count, 5, 9)
                assert (adv, _norm(pl)) == (g_adv, g_bl), (name, raw, count)


def test_line_breaking_matches_the_game(rig, fonts):
    rng = random.Random(1101)
    words = [b"the", b"Smith", b"family", b"is", b"happy", b"caf\xe9", b"a", b"supercalifragilistic", b"\n", b" "]
    samples = []
    for _ in range(200):
        samples.append(b" ".join(rng.choice(words) for _ in range(rng.randint(1, 14))))
    samples += [b"", b"   lead", b"x\n\ny", b"\n", b"word"]
    for name, f in fonts.items():
        for raw in samples:
            for max_chars, max_w, keep in ((200, 120, True), (200, 60, False), (7, 400, True), (200, 10, True)):
                mine = T.next_justified_line(f, raw, max_chars, max_w, keep)
                game = rig.next_line(name, raw, max_chars, max_w, keep)
                assert mine == game, (name, raw, max_chars, max_w, keep)


def test_the_unpatched_game_draws_utf8_names_without_leaving_its_font(rig):
    """Every byte 80h..FFh (all UTF-8 continuation and lead bytes) and real UTF-8 names at the 24-byte name limit:
    the stock DrawString / GetWidth / GetNextJustifiedLine stay inside the font's own rectangles."""
    names = ["Zoë 👩🏽‍💻", "日本語のなまえです", "Łukasz Żółć", "𒀀𒀁𒀂𒀃𒀄𒀅"]
    raws = [bytes(range(0x80, 0x100))] + [T.fit(n, 24) for n in names]
    for name in T.FONT_NAMES:
        t = rig.table(name)
        rects = {(g[1], g[2], g[3], g[4]) for g in t["glyphs"]}
        for raw in raws:
            for kind, rect, _x, _y, _a in rig.draw_string(name, raw, 0, 0):
                assert rect in rects
            assert rig.width(name, raw) >= 0
            rig.next_line(name, raw, 200, 100, True)


def test_the_tools_wrap_never_drops_a_letter():
    """A word wider than the wrap width is broken at characters, never shortened (Codex, PR #474)."""
    for name in T.FONT_NAMES:
        f = T.load_font(name)
        for text, width in ((b"Hello world", 30), (b"supercalifragilistic", 25), ("日本語のなまえです".encode(), 20),
                            (b"a b c", 1), (b"x", 0)):
            lines = T.wrap(f, text, width)
            assert b"".join(lines) == text.replace(b" ", b"")


def test_crlf_is_a_line_break_in_utf8_text_too():
    """UTF-8 text steps over CR and LF one at a time like single-byte text, so LF still breaks the line (Codex)."""
    f = T.load_font("Segoe24")
    placed = T.draw_string(f, T.encode("日\r\n本"), 0, 0)
    assert [p.unit.text for p in placed][-1] == "本" and placed[-1].y == f.line_height and placed[-1].x == 0


def test_fit_keeps_a_name_that_fits_after_a_start_that_does_not():
    """A start of single bytes that reads as UTF-8 must be stored as UTF-8 (longer); the whole name can still fit
    as single bytes (Codex)."""
    name = "a" * 16 + "Ã©é"
    assert len(T.encode(name)) == 19
    assert T.fit(name, 19) == T.encode(name)
