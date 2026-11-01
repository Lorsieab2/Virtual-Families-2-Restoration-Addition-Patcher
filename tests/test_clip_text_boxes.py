"""Copy and Paste in Text Boxes (vf2clip_b200.dll: runtime/native/b200unicode built with B200UNICODE_CLIP).

Under unicorn over an executable built from this repo, the clip DLL's SDL_PollEvent hook runs with the game's own
ldwEventManager::HandleKey and ldwTextControlImpl::HandleKey (the stock box code: its byte limit, its buffer) and
Windows' clipboard as seams:

* Ctrl+V and Shift+Insert paste at the end of the focused box, Ctrl+C / Ctrl+Insert copy its whole text, Ctrl+X cuts
  it; the key events are hidden from the game; with no box being edited nothing happens and the event goes on;
* pasted text: CR, LF and Tab become a space each, other control characters and lone surrogates are dropped; with
  both Unicode settings off only Windows-1252 characters go in, one byte each; with a Unicode setting on each whole
  character (grapheme cluster) goes through the box's HandleKey and one the box takes only part of is taken back;
* at the box's limit and one past it: the text stops at the limit and the bytes after the buffer are untouched;
* the plan writes only the SDL_PollEvent import slot; the setting off plans nothing.
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
sys.path.append(str(ROOT / "runtime"))
sys.path.append(str(ROOT / "runtime" / "tools"))

import b200_unicode_sites as S  # noqa: E402
import vf2_game_text as T  # noqa: E402
from test_b200_unicode_dll import RUNTIME, World, _vcvars, exe  # noqa: E402,F401  (fixture)

KEYDOWN, KEYUP = 0x300, 0x301
CTRL, SHIFT = 0x0040, 0x0001
INSERT = 0x40000049
CF_UNICODETEXT = 13


@pytest.fixture(scope="module")
def clip_dll(tmp_path_factory):
    if not _vcvars():
        pytest.skip("VF2_VCVARS32 is not set")
    out = tmp_path_factory.mktemp("clip_build")
    bat = RUNTIME / "native" / "build_b200unicode.bat"
    for kind in ("clip", "cliptest"):
        r = subprocess.run(["cmd.exe", "/c", str(bat), kind], capture_output=True, text=True,
                           env=dict(os.environ, VF2_UNICODE_BUILD_DIR=str(out)))
        assert r.returncode == 0, r.stdout + r.stderr
    return out / "vf2clip_b200.dll", out / "vf2clip_b200_test.dll"


def test_the_shipped_clip_dll_has_no_test_entry_points(clip_dll):
    shipped, test = clip_dll
    assert b"B200Unicode_Startup" in shipped.read_bytes() and b"B200Unicode_TestPlan" not in shipped.read_bytes()
    assert b"B200Clip_Status" in shipped.read_bytes() and b"vf2clip.ini" in shipped.read_bytes().replace(b"\0", b"")


class ClipWorld:
    def __init__(self, exe_path, dll, unicode_on=False):
        self.w = w = World(exe_path, dll)
        self.e = e = w.e
        status, writes = w.plan(3)
        assert status == 1
        self.writes = writes
        self.s, self.h = w.sites(), w.hooks()
        self.messages = []
        self.clipboard = None                       # the clipboard's text (str) or None
        self.set_text = []
        self.unicode_on = unicode_on
        # the game's ldwEventManager: [mgr] -> list -> first node {handler, flags, stop, next}
        self.mgr = e.alloc(0x20)
        self.list = e.alloc(0x10)
        e.w32(self.mgr, self.list)
        e.seam_live(self.s["EVENTS_GET"], lambda em: (self.mgr, 0))

        def post(em):
            self.messages.append((em.arg(0), em.arg(1)))
            return 0, 8
        e.seam_live(self.s["POST_MESSAGE"], post)
        if unicode_on:
            # the Unicode text DLL's HandleKey (tested in tests/test_b200_unicode_dll.py) as its model: a character
            # goes in when the whole text still fits the box's limit in the stored form
            def uni_key(em):
                box, code, sym = em.ecx, em.arg(1), em.arg(2)
                buf, limit = em.r32(box + 0x30), em.r32(box + 0x28)
                text = T.decode(em.read(buf, limit + 1).split(b"\0")[0])
                ch = chr(code & 0x1FFFFF) if code & S.KEY_MARK else chr(sym)
                raw = T.encode(text + ch)
                if len(raw) <= limit:
                    em.write(buf, raw + b"\0")
                return 1, 12
            fake = e.fake_code(b"\xC3")
            e.seam_live(fake, uni_key)
            e.w32(self.s["TEXT_VTABLE"] + 8, fake)
        status_block = e.alloc(0x40)
        e.write(status_block, struct.pack("<IIIII", S.STATUS_MAGIC, 2, 1, 1, 1))
        self.status_block = status_block
        e.imports.update({
            "OpenClipboard": lambda em: (1, 4), "CloseClipboard": lambda em: (1, 0),
            "EmptyClipboard": self._empty, "GetClipboardData": self._get, "SetClipboardData": self._set,
            "GlobalLock": lambda em: (em.arg(0), 4), "GlobalUnlock": lambda em: (1, 4),
            "GlobalAlloc": lambda em: (em.alloc(em.arg(1) + 8), 8), "GlobalFree": lambda em: (0, 4),
            "GetModuleHandleW": self._module, "GetProcAddress": self._proc,
        })
        self.events = []

        def real_poll(em):
            ev = em.arg(0)
            if not self.events:
                return 0, 0
            typ, sym, mod = self.events.pop(0)
            em.write(ev, b"\0" * 0x38)
            em.w32(ev, typ)
            em.w32(ev + 0x14, sym)
            em.write(ev + 0x18, struct.pack("<H", mod))
            return 1, 0
        fake_poll = e.fake_code(b"\xC3")
        e.seam_live(fake_poll, real_poll)
        e.call(e.dll_export("B200Unicode_TestSetPoll"), (fake_poll,))
        self.ev = e.alloc(0x40)

    # ---- Windows
    def _empty(self, em):
        self.clipboard = None
        return 1, 0

    def _get(self, em):
        if em.arg(0) != CF_UNICODETEXT or self.clipboard is None:
            return 0, 4
        data = self.clipboard.encode("utf-16-le", "surrogatepass") + b"\0\0"
        p = em.alloc(len(data) + 8)
        em.write(p, data)
        return p, 4

    def _set(self, em):
        assert em.arg(0) == CF_UNICODETEXT
        p, out = em.arg(1), b""
        while True:
            u = em.read(p + len(out), 2)
            if u == b"\0\0":
                break
            out += u
        self.clipboard = out.decode("utf-16-le", "surrogatepass")
        return em.arg(1), 8

    def _module(self, em):
        name = em.wstr(em.arg(0)).lower() if em.arg(0) else ""
        if name in ("vf2unicode_b200.dll", "vf2unicodefont_b200.dll"):
            return (0x7100_0000 if self.unicode_on and name == "vf2unicode_b200.dll" else 0), 4
        if name == "sdl2.dll":
            return 0, 4
        return em.base if not name else 0, 4

    def _proc(self, em):
        if em.arg(0) == 0x7100_0000 and em.cstr(em.arg(1)) == "B200Unicode_Status":
            return self.status_block, 8
        raise AssertionError(f"GetProcAddress {em.cstr(em.arg(1))}")

    # ---- a text box being edited, first in the key order
    def box(self, limit, text=b"", number=False, editing=True):
        e = self.e
        impl = e.alloc(0x80)
        e.w32(impl, self.s["TEXT_VTABLE"])
        e.w32(impl + 4, 77)
        owner = e.alloc(0x20)
        e.write(owner + 8, b"\x01")
        e.w32(impl + 0x1C, owner)
        e.write(impl + 0x24, b"\x01\x01" if editing else b"\x01\x00")
        e.write(impl + 0x2D, b"\x01" if number else b"\x00")
        e.w32(impl + 0x28, limit)
        buf = e.alloc(limit + 1 + 16)
        e.write(buf, text + b"\0")
        e.write(buf + limit + 1, b"\xAB" * 16)                 # the bytes after the box's buffer
        e.w32(impl + 0x30, buf)
        node = e.alloc(0x10)
        e.w32(node, impl)
        e.w32(node + 4, 2)
        e.w32(self.list, node)
        self.impl, self.buf, self.limit = impl, buf, limit
        return impl

    def text(self) -> bytes:
        return self.e.read(self.buf, self.limit + 1).split(b"\0")[0]

    def guard(self) -> bool:
        return self.e.read(self.buf + self.limit + 1, 16) == b"\xAB" * 16

    def press(self, sym, mod):
        """A key press and release: [(event type after the hook)]."""
        after = []
        for typ in (KEYDOWN, KEYUP):
            self.events.append((typ, sym, mod))
            assert self.e.call(self.h["clip_poll"], (self.ev,)) == 1
            after.append(self.e.r32(self.ev))
        return after


@pytest.fixture
def stock(exe, clip_dll):
    return ClipWorld(exe, clip_dll[1], unicode_on=False)


@pytest.fixture
def unicode(exe, clip_dll):
    return ClipWorld(exe, clip_dll[1], unicode_on=True)


def test_the_plan_is_only_the_poll_slot(stock):
    assert len(stock.writes) == 1 and stock.writes[0]["data"]
    assert struct.unpack("<I", stock.writes[0]["bytes"][:4])[0] == stock.h["clip_poll"]
    assert stock.w.plan(0) == (0, []) and stock.w.plan(1) == (0, [])


def test_paste_copy_and_cut(stock):
    stock.box(20, b"Ann")
    stock.clipboard = "e Smith"
    assert stock.press(ord("v"), CTRL) == [S.SDL_HIDDEN_EVENT] * 2
    assert stock.text() == b"Anne Smith" and stock.guard()
    stock.clipboard = "-Jones"
    stock.press(INSERT, SHIFT)                                   # Shift+Insert pastes too
    assert stock.text() == b"Anne Smith-Jones"
    stock.clipboard = None
    stock.press(ord("c"), CTRL)
    assert stock.clipboard == "Anne Smith-Jones" and stock.text() == b"Anne Smith-Jones"
    stock.clipboard = None
    stock.press(INSERT, CTRL)                                    # Ctrl+Insert copies
    assert stock.clipboard == "Anne Smith-Jones"
    stock.clipboard = None
    stock.press(ord("x"), CTRL)
    assert stock.clipboard == "Anne Smith-Jones" and stock.text() == b""
    assert any(m == (0x0C, 77) for m in stock.messages)


def test_nothing_happens_without_a_box_being_edited(stock):
    stock.box(20, b"Ann", editing=False)
    stock.clipboard = "xyz"
    assert stock.press(ord("v"), CTRL) == [KEYDOWN, KEYUP]       # the events go on to the game untouched
    assert stock.text() == b"Ann"
    stock.box(20, b"Ann")
    assert stock.press(ord("v"), 0) == [KEYDOWN, KEYUP]          # a plain V is not a paste
    assert stock.press(ord("v"), CTRL | 0x0100) == [KEYDOWN, KEYUP]   # Ctrl+Alt+V is not one either
    assert stock.text() == b"Ann"


def test_pasted_text_is_cleaned_and_kept_to_windows_1252(stock):
    stock.box(40)
    stock.clipboard = "a\r\nb\tc\x01d\x7f€Ł\U0001F44D\ud800eé"
    stock.press(ord("v"), CTRL)
    # CR, LF, Tab: a space each; \x01 \x7f, lone surrogate dropped; L-stroke and the emoji are not Windows-1252
    assert stock.text() == b"a  b c" + b"d" + b"\x80" + b"e\xe9"


@pytest.mark.parametrize("limit", [5, 18])
def test_paste_stops_at_the_limit_and_one_past_it(stock, limit):
    stock.box(limit, b"ab")
    stock.clipboard = "x" * (limit - 2)                           # exactly to the limit
    stock.press(ord("v"), CTRL)
    assert stock.text() == b"ab" + b"x" * (limit - 2) and stock.guard()
    stock.clipboard = "y"                                         # one past it
    stock.press(ord("v"), CTRL)
    assert stock.text() == b"ab" + b"x" * (limit - 2) and stock.guard()
    stock.box(limit, b"")
    stock.clipboard = "z" * (limit + 1)
    stock.press(ord("v"), CTRL)
    assert stock.text() == b"z" * limit and stock.guard()


def test_a_number_box_takes_digits(stock):
    stock.box(6, b"", number=True)
    stock.clipboard = "1a2b3"
    stock.press(ord("v"), CTRL)
    assert stock.text() == b"123"


def test_with_unicode_on_whole_characters_go_in(unicode):
    unicode.box(18, T.encode("Zo"))
    unicode.clipboard = "ë Łukasz \U0001F44D\U0001F3FD"
    unicode.press(ord("v"), CTRL)
    got = T.decode(unicode.text())
    assert got.startswith("Zoë Łukasz") and len(unicode.text()) <= 18 and unicode.guard()
    # a cluster that does not fit whole is left out whole (never half of it)
    assert all(not c.startswith("\U0001F44D") or c == "\U0001F44D\U0001F3FD" for c in T.clusters(got))
    unicode.clipboard = None
    unicode.press(ord("c"), CTRL)
    assert unicode.clipboard == got


@pytest.mark.parametrize("limit", [4, 18])
def test_with_unicode_on_the_limit_and_one_past_it(unicode, limit):
    unicode.box(limit, b"")
    unicode.clipboard = "\U00012000" * 10                          # 4 bytes each
    unicode.press(ord("v"), CTRL)
    assert unicode.text() == T.encode("\U00012000" * (limit // 4)) and unicode.guard()
    unicode.clipboard = "a" * (limit - len(unicode.text()) + 1)
    unicode.press(ord("v"), CTRL)
    assert len(unicode.text()) == limit and unicode.guard()


# ---------------------------------------------------------------------------------------------- the build and bundle
def test_the_generated_loader_loads_the_clip_dll_by_its_own_byte():
    gen = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    for needle in ('#pragma section(".vf2clip", read, write)', "volatile unsigned char gVF2Clip = 0;",
                   'if (gVF2Clip == 1) VF2LoadUnicodeDll("__VF2_CLIP_RELATIVE_PATH__");',
                   '"__VF2_CLIP_RELATIVE_PATH__",', 'CLIP_DLL_NAME = "vf2clip_b200.dll"', "patch_clip_manifest(manifest)"):
        assert needle in gen, needle
    # before the Unicode text DLL, and not an "else": it loads with either Unicode setting or neither
    assert gen.index('if (gVF2Clip == 1)') < gen.index('if (gVF2UnicodeText == 1)')
    start = gen.index("def patch_clip_manifest(manifest):")
    body = gen[start:gen.index("\ndef ", start + 10)]
    ns = {"TIME_CONTROLS_PATCHER_FOLDER": "Virtual Families 2 Patcher Files"}
    for line in gen.splitlines():
        if line.startswith(("CLIP_", "UNICODE_TEXT_STARTUP")):
            exec(line, ns)
    exec(body, ns)
    manifest = {"TimeControls": {}}
    ns["patch_clip_manifest"](manifest)
    c = manifest["ClipBoard"]
    assert c["offline_patcher_setting"] == "copy_paste_text_boxes" and c["default"] is True
    assert c["runtime_flag"]["source_section"] == ".vf2clip" and c["companion_dll"] == "vf2clip_b200.dll"
    assert c["companion_ini"] == "vf2clip.ini" and c["label"] == "Copy and Paste in Text Boxes"


def _exporter():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vf2_exporter_clip", ROOT / "work" / "export_offline_patch_bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_setting_row_and_its_files(clip_dll, tmp_path):
    ex = _exporter()
    rows = {r["id"]: r for r in ex.SETTINGS}
    row = rows["copy_paste_text_boxes"]
    assert row["label"] == "Copy and Paste in Text Boxes" and row["default"] is True and "excludes" not in row
    for key in ("Ctrl+V", "Shift+Insert", "Ctrl+C", "Ctrl+Insert", "Ctrl+X", "Windows-1252", "do nothing anywhere else"):
        assert key in row["description"], key
    assert ex.RUNTIME_FLAG_SECTION_BY_SETTING["copy_paste_text_boxes"] == ".vf2clip"
    contract = {"ClipBoard": {"offline_patcher_setting": "copy_paste_text_boxes", "companion_dll": "vf2clip_b200.dll",
                              "companion_ini": "vf2clip.ini", "runtime_flag": {"source_section": ".vf2clip"}}}
    records = ex.clip_asset_patches(tmp_path, clip_dll[0], contract)
    folder = "Virtual Families 2 Patcher Files"
    assert sorted(r["file_path"] for r in records) == [f"{folder}/vf2clip.ini", f"{folder}/vf2clip_b200.dll"]
    assert all(r["requires"] == ["core_executable", "copy_paste_text_boxes"] and r["remove_when_disabled"]
               for r in records)
    assert (tmp_path / "payload" / "ClipBoard" / "vf2clip.ini").read_bytes() == b"[Patches]\r\nMode=3\r\n"
    with pytest.raises(ValueError, match="--clip-dll"):
        ex.clip_asset_patches(tmp_path, None, contract)
    with pytest.raises(ValueError, match="shipped clip build"):
        ex.clip_asset_patches(tmp_path, _renamed(clip_dll[1], tmp_path), contract)
    assert ex.clip_asset_patches(tmp_path, None, {}) == []


def _renamed(test_dll: Path, tmp: Path) -> Path:
    """The harness build under the shipped name (the exporter must refuse it)."""
    d = tmp / "harness"
    d.mkdir(exist_ok=True)
    out = d / "vf2clip_b200.dll"
    out.write_bytes(test_dll.read_bytes())
    return out
