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
    d.UtIsUtf8.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
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


def _random_bytes(rng):
    return bytes(rng.randrange(1, 256) for _ in range(rng.randint(0, 24)))


def _all_raws():
    rng = random.Random(20261101)
    raws = [T.encode(s) for s in SAMPLES]
    raws += [T.encode(_random_text(rng)) for _ in range(1500)]
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
        assert bool(lib.UtIsUtf8(raw, len(raw))) == T.is_utf8(raw), raw
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
