"""The Unicode Text DLL's text rules (runtime/native/b200unicode/b200unicode_text.h) equal the patcher's
(src/vf2_game_text.py), text by text.

The header is built into a test DLL of this Python's bitness (b200unicode_texttest.cpp, with Visual Studio's
vcvars: VF2_VCVARS32's folder, its vcvars64.bat on a 64-bit Python; skipped without it) and called with ctypes:
the stored-form test, the characters (clusters with their bytes), encode, decode, the accent table, and the stock
GetWidth and GetNextJustifiedLine with a character in place of a byte (a test font whose widths come from the
code points), over fixed texts in many scripts and thousands of random ones. tests/test_vf2_game_text.py proves the
Python equal to the game's own code for every single-byte text.

The tables both use (src/vf2_unicode_tables.py, b200unicode_tables.h) are checked to be the same.
"""
from __future__ import annotations

import ctypes
import os
import random
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "runtime" / "tools"))

import vf2_game_text as T  # noqa: E402
import vf2_unicode_tables as TABLES  # noqa: E402

NATIVE = ROOT / "runtime" / "native" / "b200unicode"
MAXCP = 16


def _vcvars() -> Path | None:
    v = os.environ.get("VF2_VCVARS32")
    if not v:
        return None
    p = Path(v)
    if struct.calcsize("P") == 8:
        p = p.with_name("vcvars64.bat")
    return p if p.is_file() else None


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    vc = _vcvars()
    if vc is None:
        pytest.skip("VF2_VCVARS32 is not set (Visual Studio's vcvars32.bat)")
    out = tmp_path_factory.mktemp("uttest")
    dll = out / "vf2unicode_texttest.dll"
    bat = out / "build.bat"
    bat.write_text(f'@echo off\r\ncall "{vc}" >nul\r\ncd /d "{out}"\r\ncl /nologo /O2 /LD /EHsc /W4 '
                   f'"{NATIVE / "b200unicode_texttest.cpp"}" /Fe:vf2unicode_texttest.dll\r\n', encoding="ascii")
    r = subprocess.run(["cmd.exe", "/c", str(bat)], capture_output=True, text=True)
    assert dll.is_file(), r.stdout + r.stderr
    d = ctypes.CDLL(str(dll))
    u32p = ctypes.POINTER(ctypes.c_uint32)
    d.UtUnits.argtypes = [ctypes.c_char_p, ctypes.c_uint32, u32p, u32p, u32p, u32p, ctypes.c_uint32]
    d.UtUnits.restype = ctypes.c_uint32
    d.UtEncode.argtypes = [u32p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
    d.UtDecode.argtypes = [ctypes.c_char_p, ctypes.c_uint32, u32p, ctypes.c_uint32]
    d.UtDecode.restype = ctypes.c_uint32
    d.UtComposed.argtypes = [u32p, ctypes.c_uint32]
    d.UtComposed.restype = ctypes.c_uint32
    d.UtGetWidth.argtypes = [ctypes.c_char_p, ctypes.c_float, ctypes.c_int]
    d.UtNextLine.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.c_float, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
    d.UtNextLine.restype = ctypes.c_uint32
    return d


def c_units(lib, raw: bytes):
    n = len(raw) + 1
    starts, sizes, counts = (ctypes.c_uint32 * n)(), (ctypes.c_uint32 * n)(), (ctypes.c_uint32 * n)()
    cps = (ctypes.c_uint32 * (n * MAXCP))()
    k = lib.UtUnits(raw, len(raw), starts, sizes, counts, cps, n)
    out = []
    for i in range(k):
        c = [cps[i * MAXCP + j] for j in range(min(counts[i], MAXCP))]
        out.append((starts[i], sizes[i], "".join(chr(x) for x in c)))
    return out


def py_units(raw: bytes):
    out, at = [], 0
    for u in T.units(raw):
        out.append((at, u.size, u.text))
        at += u.size
    return out


class FakeFont:
    """The test DLL's font: width (7 x sum(code points) + 3 x count) % 13, a space 4."""
    kerning = 0

    def __init__(self, kerning=0):
        self.kerning = kerning

    def glyph(self, unit):
        if unit.text == " ":
            return T.Glyph(4, "game")
        cps = [ord(c) for c in unit.text][:MAXCP]
        return T.Glyph((7 * sum(cps) + 3 * len(unit.text)) % 13, "game")


SAMPLES = [
    "", "Hi!", "The Smith Family", "a\nb", "\n\nx", "Zoë Müller", "Łukasz Żółć", "İstanbul ığüşöç Şişli",
    "Nguyễn Thị Hằng", "Αθήνα Москва", "日本語のなまえ 中文名字 한국어", "𒀀𒀁𒀂 cuneiform", "Zoë 👩🏽‍💻 🇫🇷🇩🇪 👍🏿",
    "é ä ố", "€ “quotes” — ok…", "Ã©", "a\r\nb", "‍‍", "🇫", "x‍\n",
]


def _random_text(rng):
    pool = (list("abc XYZ\n,.") + ["é", "Ł", "ı", "ş", "日", "本", "😀", "́", "‍", "👩", "🏽", "🇫", "🇷",
            "️", "€", "Ã", "©", "𒀀", "\r"])
    return "".join(rng.choice(pool) for _ in range(rng.randint(0, 30)))


# line breaking (UAX #14): kinsoku marks, small kana, Thai, a zero width space, brackets, long words, emoji
BREAK_SAMPLES = [
    "\u65e5\u672c\u8a9e\u3002\u65e5\u672c\u8a9e\u3001\u300c\u65e5\u672c\u300d\u3067\u3059", "\u304d\u3083\u3063\u3068\u30fc\u30fc\u30fc\u30fc",
    "\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35\u0e04\u0e23\u0e31\u0e1a \u0e02\u0e2d\u0e1a\u0e04\u0e38\u0e13", "a\u200bb\u200bc\u200bd",
    "Hello \u65e5\u672c\u8a9e world", "(\u65e5\u672c)(\u8a9e)", "supercalifragilisticexpialidocious",
    "\U0001f600\U0001f600\U0001f600 \U0001f468\u200d\U0001f469\u200d\U0001f467 x", "\uff08\u65e5\u672c\uff09\u3002\uff01\uff1f",
    "\u65e5 \u672c  \u8a9e\n\u65e5\u672c\n\n\u8a9e", "\u1000\u1001\u1002 \u1780\u1781\u1782 \u0e81\u0e82", "a\u3001b\u3002",
]


def _random_break_text(rng):
    pool = (list("abc  XYZ.,!?()\n") + ["\u65e5", "\u672c", "\u8a9e", "\u3002", "\u3001", "\u300c", "\u300d", "\u3083", "\u30fc",
            "\u304b", "\u0e01", "\u0e32", "\u0e31", "\u200b", "\U0001f600", "\uff08", "\uff09", "\u0301", "word", "words"])
    return "".join(rng.choice(pool) for _ in range(rng.randint(1, 40)))


def _random_bytes(rng):
    return bytes(rng.randrange(1, 256) for _ in range(rng.randint(0, 24)))


def _all_raws():
    rng = random.Random(20261101)
    raws = [T.encode(s) for s in SAMPLES + BREAK_SAMPLES]
    raws += [T.encode(_random_text(rng)) for _ in range(1500)]
    raws += [T.encode(_random_break_text(rng)) for _ in range(1500)]
    raws += [_random_bytes(rng) for _ in range(1500)]
    return raws


def test_the_tables_are_the_same_in_python_and_the_dll():
    h = (NATIVE / "b200unicode_tables.h").read_text(encoding="utf-8")
    assert f"static const unsigned UT_EXTEND_COUNT = {len(TABLES.EXTEND)}u;" in h
    assert f"static const unsigned UT_COMPOSE_COUNT = {len(TABLES.COMPOSE)}u;" in h
    for a, b in TABLES.EXTEND:
        assert f"{{0x{a:X}u, 0x{b:X}u}}," in h
    for seq, cp in TABLES.COMPOSE.items():
        s = list(seq) + [0] * (4 - len(seq))
        assert f"{{{{{', '.join(f'0x{c:X}u' for c in s)}}}, {len(seq)}u, 0x{cp:X}u}}," in h


def test_stored_form_units_and_decode(lib):
    for raw in _all_raws():
        raw = raw.split(b"\0", 1)[0]
        assert c_units(lib, raw) == py_units(raw), raw
        cap = len(raw) + 1
        cps = (ctypes.c_uint32 * cap)()
        k = lib.UtDecode(raw, len(raw), cps, cap)
        assert "".join(chr(cps[i]) for i in range(k)) == T.decode(raw), raw


def test_encode(lib):
    rng = random.Random(7)
    texts = SAMPLES + [_random_text(rng) for _ in range(2000)] + ["José", "Renée “Bo”", "€ Ł", "ÿ", "\x81"]
    for s in texts:
        s = s.replace("\0", "")
        cps = (ctypes.c_uint32 * max(1, len(s)))(*[ord(c) for c in s])
        buf = ctypes.create_string_buffer(4 * len(s) + 8)
        n = lib.UtEncode(cps, len(s), buf, len(buf))
        assert buf.raw[:n] == T.encode(s), s
        if len(T.encode(s)) > 2:
            assert lib.UtEncode(cps, len(s), buf, len(T.encode(s)) - 1) == -1


def test_composed_letters(lib):
    for text, letter in T.COMPOSE.items():
        cps = (ctypes.c_uint32 * len(text))(*[ord(c) for c in text])
        assert lib.UtComposed(cps, len(text)) == ord(letter)
    cps = (ctypes.c_uint32 * 2)(ord("q"), 0x301)
    assert lib.UtComposed(cps, 2) == 0


@pytest.mark.parametrize("kerning", [0, 1, -1])
def test_width_and_line_breaking(lib, kerning):
    f = FakeFont(kerning)
    rng = random.Random(kerning + 5)
    for raw in _all_raws():
        raw = raw.split(b"\0", 1)[0]
        for scale in (1.0, 0.75):
            assert lib.UtGetWidth(raw, scale, kerning) == T.get_width(f, raw, scale), (raw, scale)
        for _ in range(3):
            max_bytes = rng.choice([200, 7, 3, 1, 0, 12])
            max_w = rng.choice([400, 60, 20, 5, 0])
            keep = rng.random() < 0.5
            out = ctypes.create_string_buffer(len(raw) + 16)
            dbl = ctypes.c_int()
            used = lib.UtNextLine(raw, out, max_bytes, max_w, 1 if keep else 0, 1.0, kerning, ctypes.byref(dbl))
            mine = T.next_justified_line(f, raw, max_bytes, max_w, keep)
            assert (out.value, used, bool(dbl.value)) == mine, (raw, max_bytes, max_w, keep)
            if max_bytes > 0:
                assert len(out.value) <= max(max_bytes, max(u.size for u in T.units(raw)) if raw else 0)


def _break_flags(lib, raw: bytes):
    lib.UtBreaks.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
    lib.UtBreaks.restype = ctypes.c_uint32
    flags = ctypes.create_string_buffer(len(raw) + 8)
    k = lib.UtBreaks(raw, len(raw), flags, len(raw) + 8)
    return [bool(flags.raw[i]) for i in range(k + 1)]


def test_break_places_are_the_same_in_the_dll_without_icu_and_in_python(lib):
    """UAX #14 with the built-in table (the DLL without icu.dll, the patcher always): the same places."""
    lib.UtIcu.argtypes = [ctypes.c_int]
    lib.UtIcu.restype = ctypes.c_int
    lib.UtIcu(0)
    import vf2_line_break as LB
    seen_break = False
    for raw in _all_raws():
        raw = raw.split(b"\0", 1)[0]
        us = T.units(raw)
        want = LB.break_flags([(ord(u.text[0]), ord(u.text[min(len(u.text), 16) - 1])) for u in us])
        got = _break_flags(lib, raw)
        assert got == want[:len(got)] and len(got) == len(want), raw
        seen_break = seen_break or any(want)
    assert seen_break


def test_the_line_break_table_header_is_what_the_generator_writes():
    import gen_b200_line_break as G
    assert (NATIVE / "b200linebreak_table.h").read_text(encoding="utf-8").replace("\r\n", "\n") == G.render()


def test_with_windows_icu_the_breaks_follow_uax14_dictionary_and_kinsoku(lib):
    """The DLL asks Windows' own ICU (icu.dll, Windows 10 1903 and later) when the host has it: Thai breaks only
    between words (the table breaks between any two characters), and no line starts with a closing mark or ends with
    an opening one."""
    lib.UtIcu.argtypes = [ctypes.c_int]
    lib.UtIcu.restype = ctypes.c_int
    try:
        if not lib.UtIcu(1):
            pytest.skip("this Windows has no icu.dll")
        thai = "\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35\u0e04\u0e23\u0e31\u0e1a\u0e02\u0e2d\u0e1a\u0e04\u0e38\u0e13\u0e21\u0e32\u0e01"
        raw = T.encode(thai)
        icu_flags = _break_flags(lib, raw)
        lib.UtIcu(0)
        table_flags = _break_flags(lib, raw)
        lib.UtIcu(1)
        assert sum(icu_flags) >= 2 and sum(table_flags) > sum(icu_flags)       # words, not letters
        assert all(t for i, t in enumerate(table_flags) if icu_flags[i])       # ICU's places are among the table's
        jp = "\u65e5\u672c\u8a9e\u3002\u300c\u65e5\u672c\u300d\u3001\u304d\u3083"
        flags = _break_flags(lib, T.encode(jp))
        units = [u.text for u in T.units(T.encode(jp))]
        for i, text in enumerate(units):
            if flags[i]:
                assert text not in "\u3002\u300d\u3001", (i, text)       # no line starts with a closing mark
                assert units[i - 1] != "\u300c", (i, units[i - 1])               # none ends with an opening one
        assert any(flags)
    finally:
        lib.UtIcu(0)


def test_fit_for_the_text_boxes_get_text(lib):
    """GetText's cut (the DLL's hook of ldwTextControl::GetText): the longest start that fits, whole characters."""
    lib.UtFit.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_char_p]
    lib.UtFit.restype = ctypes.c_uint32
    for raw in _all_raws():
        raw = raw.split(b"\0", 1)[0]
        for n in (0, 1, 2, 5, 18, 19, 79):
            out = ctypes.create_string_buffer(n + 8)
            k = lib.UtFit(raw, len(raw), n, out)
            assert out.raw[:k] == T.fit(T.decode(raw), n), (raw, n)


def test_fit_tries_every_start(lib):
    lib.UtFit.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_char_p]
    lib.UtFit.restype = ctypes.c_uint32
    raw = T.encode("a" * 16 + "Ã©é")                # UTF-8 as a whole (22 bytes)
    out = ctypes.create_string_buffer(32)
    for room in (16, 17, 19, 20, 21, 22, 30):
        k = lib.UtFit(raw, len(raw), room, out)
        assert out.raw[:k] == T.fit("a" * 16 + "Ã©é", room), room
