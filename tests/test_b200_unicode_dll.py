"""The Unicode text companion DLL (vf2unicode_b200.dll) against the B200 executables, under emulation.

* static (always): the sites module, the generator's header and the DLL source agree; the generated loader;
* with Visual Studio (VF2_VCVARS32): the shipped and the test DLL build; the shipped one exports
  B200Unicode_Startup and no test entry point;
* with an executable built from this repo (VF2_UNICODE_EXE, else VF2_B200_CORE_EXE / VF2_KIDS_EXE): the DLL's own
  resolver runs under unicorn over the real executable mapped at its link base and relocated (ASLR): every pinned
  function is found, the plan is exactly the 6 entry jumps into the DLL's hooks, ldwFontImpl's GetCharSourceRect
  slot, ldwTextControlImpl's HandleKey slot and the executable's SDL_PollEvent import slot, equal to what
  runtime/tools/gen_b200_unicode_sites.py derives; a changed pinned byte makes it install nothing; the setting off
  plans nothing;
* typing, run in the DLL's own code under unicorn: characters reach the box in the stored form; a character is
  added only when the whole text still fits the box's own byte limit (at the limit and one past it nothing is
  written beyond the box's buffer); Backspace removes a whole character (an emoji with its skin tone and joiner);
  GetText cuts at a character and fills the rest with zeros; a typed text of anything but one ASCII byte is handed
  to the game one character at a time and hidden from the stock code, one ASCII key is left to the stock code.
"""
from __future__ import annotations

import os
import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "tests"))
sys.path.append(str(RUNTIME))
sys.path.append(str(RUNTIME / "tools"))

import b200_unicode_sites as S  # noqa: E402
import vf2_game_text as T  # noqa: E402

NATIVE = RUNTIME / "native" / "b200unicode"
OBJS = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")


def _exe():
    for key in ("VF2_UNICODE_EXE", "VF2_B200_CORE_EXE", "VF2_KIDS_EXE"):
        v = os.environ.get(key)
        if v and Path(v).is_file():
            return Path(v)
    return None


# ---------------------------------------------------------------------------------------------- static
def test_the_dll_source_names_every_site_and_writes_nothing_else():
    src = (NATIVE / "b200unicode.cpp").read_text(encoding="utf-8")
    header = (NATIVE / "b200unicode_sites.h").read_text(encoding="utf-8")
    for name, _obj, _fn in S.FUNCTIONS:
        assert f"UNI_PIN_{name.upper()}" in header
    for site, _pin, _how in S.SITES:
        assert f"UNI_SITE_{site}" in header
    # the only writes: the plan's entry jumps, the two vtable slots and the import slot
    assert src.count("PlanJump(plan,") == 6 and src.count("PlanSlot(plan,") == 3
    assert not re.search(r"\b0x4[0-9A-Fa-f]{5}\b", src)                # no game address (the image is relocated)
    assert 'L"vf2unicodefont.ini"' in src and 'L"vf2unicode.ini"' in src


def test_the_generated_loader_loads_the_dll_by_its_two_bytes():
    gen = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    for needle in ('#pragma section(".vf2utxt", read, write)', '#pragma section(".vf2ufnt", read, write)',
                   "volatile unsigned char gVF2UnicodeText = 0;", "volatile unsigned char gVF2UnicodeFont = 0;",
                   'if (gVF2UnicodeText == 1) VF2LoadUnicodeDll("__VF2_UNICODE_TEXT_RELATIVE_PATH__");',
                   'else if (gVF2UnicodeFont == 1) VF2LoadUnicodeDll("__VF2_UNICODE_FONT_RELATIVE_PATH__");',
                   'GetProcAddress(module, "B200Unicode_Startup")', "patch_unicode_text_manifest(manifest)",
                   'UNICODE_TEXT_DLL_NAME = "vf2unicode_b200.dll"', 'UNICODE_FONT_DLL_NAME = "vf2unicodefont_b200.dll"'):
        assert needle in gen, needle


def test_the_header_is_what_the_generator_writes():
    if not (OBJS / "ldwFont.obj").is_file():
        pytest.skip("no B200 desktop object files")
    pytest.importorskip("pefile")
    import gen_b200_unicode_sites as G
    assert G.render_header(G.load_pins(OBJS)) == (NATIVE / "b200unicode_sites.h").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------- built DLLs
def _vcvars():
    v = os.environ.get("VF2_VCVARS32")
    return v if v and Path(v).is_file() else None


@pytest.fixture(scope="module")
def dlls():
    if not _vcvars():
        pytest.skip("VF2_VCVARS32 is not set")
    bat = RUNTIME / "native" / "build_b200unicode.bat"
    for kind in ("", "test"):
        r = subprocess.run(["cmd.exe", "/c", str(bat)] + ([kind] if kind else []), capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
    return RUNTIME / "build" / "vf2unicode_b200.dll", RUNTIME / "build" / "vf2unicode_b200_test.dll"


def test_the_shipped_dll_has_no_test_entry_points(dlls):
    shipped, test = dlls
    data = shipped.read_bytes()
    assert b"B200Unicode_Startup" in data and b"B200Unicode_TestPlan" not in data
    assert b"B200Unicode_TestPlan" in test.read_bytes()


# ---------------------------------------------------------------------------------------------- emulation
class World:
    def __init__(self, exe: Path, dll: Path, delta: int = 0):
        from b200_time_emu import Emu
        self.e = e = Emu(exe, dll, delta)
        self.delta = delta
        self._native_scans()
        self.messages, self.keys = [], []

    def _native_scans(self):
        e = self.e
        scan_at = e.call(e.dll_export("B200Unicode_TestScanAddress"))
        next_at = e.call(e.dll_export("B200Unicode_TestNextDwordAddress"))

        def scan(emu):
            base, size, pat, mask, length, hits = (emu.arg(i) for i in range(6))
            data = emu.read(base, size)
            p, m = emu.read(pat, length), emu.read(mask, length)
            rx = re.compile(b"".join(b"." if w else re.escape(bytes([b])) for b, w in zip(p, m)), re.DOTALL)
            first, count = 0, emu.r32(hits)
            for mt in rx.finditer(data):
                if not count:
                    first = base + mt.start()
                count += 1
                if count >= 2:
                    break
            emu.w32(hits, count)
            return first, 0

        def next_dword(emu):
            start, end, value = emu.arg(0), emu.arg(1), emu.arg(2)
            if start + 4 > end:
                return 0, 0
            data = emu.read(start, end - start)
            want = struct.pack("<I", value)
            j = data.find(want)
            while j >= 0 and j % 4:
                j = data.find(want, j + 1)
            return (start + j if j >= 0 else 0), 0
        e.seam_live(scan_at, scan)
        e.seam_live(next_at, next_dword)

    def plan(self, mode=1):
        e = self.e
        out = e.alloc(0x200)
        status = e.call(e.dll_export("B200Unicode_TestPlan"), (mode, out))
        status = struct.unpack("<i", struct.pack("<I", status))[0]
        writes = []
        for i in range(e.r32(out + 4)):
            va, ln, data, b0, b1 = [e.r32(out + 8 + i * 20 + 4 * k) for k in range(5)]
            writes.append({"va": va, "len": ln, "data": bool(data), "bytes": struct.pack("<II", b0, b1)[:ln]})
        return status, writes

    def sites(self):
        e = self.e
        out = e.alloc(4 * 32)
        e.call(e.dll_export("B200Unicode_TestSites"), (out,))
        names = []
        for site, _p, _h in S.SITES:
            if site not in names:
                names.append(site)
        vals = [e.r32(out + 4 * i) for i in range(len(names) + 3)]
        return dict(zip(names + ["FONT_VTABLE", "TEXT_VTABLE", "POLL_SLOT"], vals))

    def hooks(self):
        e = self.e
        out = e.alloc(4 * 12)
        e.call(e.dll_export("B200Unicode_TestHooks"), (out,))
        keys = ("draw_string", "draw_chars", "get_width", "next_line", "get_text", "draw_justified", "char_rect",
                "handle_key", "poll")
        return {k: e.r32(out + 4 * i) for i, k in enumerate(keys)}

    def game_seams(self, sites):
        e = self.e
        self.events = e.alloc(0x40)
        e.seam_live(sites["EVENTS_GET"], lambda emu: (self.events, 0))

        def post(emu):
            self.messages.append((emu.ecx, emu.arg(0), emu.arg(1)))
            return 0, 8
        e.seam_live(sites["POST_MESSAGE"], post)

        def handle_key(emu):
            self.keys.append((emu.arg(0), emu.arg(1), emu.arg(2)))
            return 0, 12
        e.seam_live(sites["EVENTS_HANDLE_KEY"], handle_key)


@pytest.fixture(scope="module")
def exe():
    p = _exe()
    if p is None:
        pytest.skip("no executable built from this repo (VF2_UNICODE_EXE / VF2_B200_CORE_EXE)")
    pytest.importorskip("unicorn")
    pytest.importorskip("pefile")
    return p


@pytest.mark.parametrize("delta", [0, 0x01230000])
def test_the_plan_is_the_proved_sites(exe, dlls, delta):
    import gen_b200_unicode_sites as G
    proved = G.resolve(G.Exe(exe), G.load_pins(OBJS)) if (OBJS / "ldwFont.obj").is_file() else None
    w = World(exe, dlls[1], delta)
    status, writes = w.plan(1)
    assert status == 1
    s = w.sites()
    h = w.hooks()
    jumps = {wr["va"]: wr for wr in writes if not wr["data"]}
    slots = {wr["va"]: wr for wr in writes if wr["data"]}
    assert len(writes) == 9 and len(jumps) == 6 and len(slots) == 3
    for site, hook, length in (("DRAW_STRING", "draw_string", 5), ("DRAW_CHARS", "draw_chars", 5),
                               ("GET_WIDTH", "get_width", 5), ("NEXT_LINE", "next_line", 5),
                               ("GET_TEXT", "get_text", 5), ("DRAW_JUSTIFIED", "draw_justified", 9)):
        wr = jumps[s[site]]
        assert wr["len"] == length and wr["bytes"][0] == 0xE9
        assert (s[site] + 5 + struct.unpack("<i", wr["bytes"][1:5])[0]) & 0xFFFFFFFF == h[hook]
        if proved:
            assert s[site] == proved["sites"][site] + delta
    assert struct.unpack("<I", slots[s["FONT_VTABLE"] + 4]["bytes"][:4])[0] == h["char_rect"]
    assert struct.unpack("<I", slots[s["TEXT_VTABLE"] + 8]["bytes"][:4])[0] == h["handle_key"]
    assert struct.unpack("<I", slots[s["POLL_SLOT"]]["bytes"][:4])[0] == h["poll"]
    if proved:
        assert s["POLL_SLOT"] == proved["poll_slot"] + delta
        assert s["FONT_VTABLE"] == proved["font_vtable"] + delta
    assert w.plan(0) == (0, [])


def test_a_changed_pinned_byte_installs_nothing(exe, dlls):
    w = World(exe, dlls[1])
    w.plan(1)
    site = w.sites()["GET_WIDTH"]
    w2 = World(exe, dlls[1])
    w2.e.write(site + 0x40, bytes([w2.e.read(site + 0x40, 1)[0] ^ 0x5A]))
    assert w2.plan(1)[0] == -1


# ---------------------------------------------------------------------------------------------- typing
def _box(w, max_bytes, text=b""):
    e = w.e
    scene = e.alloc(0x20)
    e.write(scene + 8, b"\x01")
    ctl = e.alloc(0x80)
    buf = e.alloc(max_bytes + 1 + 16)
    e.write(buf + max_bytes + 1, b"\xAB" * 16)               # a canary after the box's buffer
    e.write(buf, text + b"\0")
    e.w32(ctl + 4, 77)
    e.w32(ctl + 0x1C, scene)
    e.write(ctl + 0x25, b"\x01")
    e.w32(ctl + 0x28, max_bytes)
    e.w32(ctl + 0x30, buf)
    return ctl, buf


def _typed_model(text: str, max_bytes: int) -> bytes:
    """What typing `text` one code point at a time leaves in a box of max_bytes (the DLL's rule)."""
    cur = ""
    for ch in text:
        if len(T.encode(cur + ch)) <= max_bytes:
            cur += ch
    return T.encode(cur)


@pytest.fixture(scope="module")
def typing_world(exe, dlls):
    w = World(exe, dlls[1])
    assert w.plan(1)[0] == 1
    s = w.sites()
    w.game_seams(s)
    w.s, w.h = s, w.hooks()
    return w


def _type(w, ctl, text):
    for ch in text:
        cp = ord(ch)
        if cp < 0x80:
            continue
        w.e.call(w.h["handle_key"], (5, cp | S.KEY_MARK, 0), ecx=ctl, edx=0)


@pytest.mark.parametrize("text,limit", [("Łukasz Żółć", 18), ("日本語のなまえ", 18), ("ééééééééééééééééééééé", 18),
                                        ("ééééééééé", 9), ("Ω", 1), ("👩🏽‍💻", 19)])
def test_typing_stays_inside_the_box(typing_world, text, limit):
    w = typing_world
    ctl, buf = _box(w, limit)
    model = ""
    for ch in text:
        if ord(ch) < 0x80:
            # ASCII goes to the stock HandleKey: put it in the buffer as the stock code would (len < max)
            cur = w.e.cstr(buf).encode("latin-1")
            if len(cur) < limit:
                w.e.write(buf, cur + ch.encode() + b"\0")
                model += ch
            continue
        w.e.call(w.h["handle_key"], (5, ord(ch) | S.KEY_MARK, 0), ecx=ctl, edx=0)
        if len(T.encode(model + ch)) <= limit:
            model += ch
    raw = w.e.read(buf, limit + 1).split(b"\0", 1)[0]
    assert raw == T.encode(model)
    assert len(raw) <= limit
    assert w.e.read(buf + limit + 1, 16) == b"\xAB" * 16             # nothing beyond the buffer


def test_backspace_removes_a_whole_character(typing_world):
    w = typing_world
    ctl, buf = _box(w, 40, "Zoë 👩🏽‍💻".encode("utf-8"))
    w.e.call(w.h["handle_key"], (5, 8, 8), ecx=ctl, edx=0)
    assert w.e.read(buf, 41).split(b"\0", 1)[0] == T.encode("Zoë ")
    w.e.call(w.h["handle_key"], (5, 8, 8), ecx=ctl, edx=0)
    w.e.call(w.h["handle_key"], (5, 8, 8), ecx=ctl, edx=0)
    assert w.e.read(buf, 41).split(b"\0", 1)[0] == b"Zo"


def test_a_number_box_takes_no_letters(typing_world):
    w = typing_world
    ctl, buf = _box(w, 10, b"12")
    w.e.write(ctl + 0x2D, b"\x01")
    w.e.call(w.h["handle_key"], (5, 0xE9 | S.KEY_MARK, 0), ecx=ctl, edx=0)
    assert w.e.read(buf, 3) == b"12\0"


@pytest.mark.parametrize("text,size", [("Zoë 👩🏽‍💻 and more", 20), ("日本語のなまえです", 19), ("José", 5), ("abc", 20)])
def test_get_text_cuts_at_a_character(typing_world, text, size):
    w = typing_world
    ctl, buf = _box(w, 200, T.encode(text))
    wrapper = w.e.alloc(0x20)
    w.e.w32(wrapper + 0x10, ctl)
    dst = w.e.alloc(size + 8)
    w.e.write(dst, b"\xCD" * (size + 8))
    w.e.call(w.h["get_text"], (dst, size), ecx=wrapper, edx=0)
    got = w.e.read(dst, size)
    expect = T.fit(text, size - 1)
    assert got == expect + b"\0" * (size - len(expect))
    assert w.e.read(dst + size, 8) == b"\xCD" * 8


def test_typed_text_reaches_the_game_one_character_at_a_time(typing_world):
    w = typing_world
    e = w.e
    events = []

    def real_poll(emu):
        ev = emu.arg(0)
        if not events:
            return 0, 0
        typ, text = events.pop(0)
        emu.w32(ev, typ)
        emu.write(ev + S.TEXT_FIELD, text + b"\0")
        return 1, 0
    fake = e.fake_code(b"\xC3")
    e.seam_live(fake, real_poll)
    e.call(e.dll_export("B200Unicode_TestSetPoll"), (fake,))
    ev = e.alloc(0x40)
    cases = [
        ("é".encode(), [(5, 0xE9 | S.KEY_MARK, 0)], S.SDL_HIDDEN_EVENT),
        ("ab".encode(), [(5, 0, ord("a")), (5, 0, ord("b"))], S.SDL_HIDDEN_EVENT),
        ("日本".encode(), [(5, 0x65E5 | S.KEY_MARK, 0), (5, 0x672C | S.KEY_MARK, 0)], S.SDL_HIDDEN_EVENT),
        ("𒀀".encode(), [(5, 0x12000 | S.KEY_MARK, 0)], S.SDL_HIDDEN_EVENT),
        (b"a", [], S.SDL_TEXTINPUT),                                      # one ASCII key: the stock path
    ]
    for text, keys, after in cases:
        w.keys.clear()
        events.append((S.SDL_TEXTINPUT, text))
        assert e.call(w.h["poll"], (ev,)) == 1
        assert w.keys == keys
        assert e.r32(ev) == after
    events.append((0x300, b""))                                           # a key press is untouched
    w.keys.clear()
    e.call(w.h["poll"], (ev,))
    assert w.keys == [] and e.r32(ev) == 0x300


# ---------------------------------------------------------------------------------------------- drawing
GAME_IMAGES = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload") / "Images"
ABGR = (0xFF, 0xFF00, 0xFF0000, 0xFF000000)           # what SDL2_image gives a PNG with alpha (RGBA bytes)


class DrawWorld(World):
    """The DLL's drawing hooks run under unicorn over the real executable (ClipRect, GetImage, the tint cache are
    the game's own code); SDL2 / SDL2_image and the DLL's file and heap calls are seams over real files: the
    original game's font picture and the patcher-made glyph files written by src/vf2_glyph_maker.py."""

    def __init__(self, exe, dll, glyph_dir: Path):
        import b200_time_emu
        b200_time_emu.HEAP_SIZE = max(b200_time_emu.HEAP_SIZE, 0x6000000)     # four fonts' sheets and their rooms
        super().__init__(exe, dll)
        import vf2_picture_image as P
        self.P = P
        e = self.e
        assert self.plan(1)[0] == 1
        self.s, self.h = self.sites(), self.hooks()
        self.glyph_dir = glyph_dir
        self.files, self.blits = {}, []
        self.surfaces = {}
        sdl, img = 0x6000_0000, 0x6100_0000

        def module(emu):
            name = emu.arg(0)
            if name == 0:
                return emu.base, 4
            return {"sdl2.dll": sdl, "sdl2_image.dll": img}.get(emu.wstr(name).lower(), 0), 4
        e.imports["GetModuleHandleW"] = module
        for name, fn in (("SDL_CreateRGBSurface", self._create), ("SDL_FreeSurface", lambda em: (0, 0)),
                         ("SDL_LockSurface", lambda em: (0, 0)), ("SDL_UnlockSurface", lambda em: (0, 0)),
                         ("SDL_MapRGBA", self._map), ("SDL_GetRGBA", self._get), ("IMG_Load", self._img_load)):
            e.dyn_procs[name] = fn
        e.imports.update({
            "GetProcessHeap": lambda em: (1, 0),
            "HeapAlloc": lambda em: (em.alloc(em.arg(2), fill=0) if em.arg(2) else em.alloc(16), 12),
            "HeapFree": lambda em: (1, 12),
            "CreateFileW": self._open, "GetFileSize": self._size, "ReadFile": self._read_file,
            "CloseHandle": lambda em: (1, 4), "WideCharToMultiByte": self._w2mb,
            "lstrcatW": self._lstrcat,
        })
        e.bind_exe_imports({"SDL_UpperBlit": self._upper_blit})
        assert e.call(e.dll_export("B200Unicode_TestLoadSdl")) == 1
        # the window: +30h the screen, +5Ch no default font, +60h..+6Ch the clip rectangle
        self.window = e.alloc(0x100)
        e.w32(self.window + 0x30, self._surface(64, 64, b"\0" * 64 * 64 * 4))
        for off, v in ((0x60, 0), (0x64, 0), (0x68, 4096), (0x6C, 4096)):
            e.w32(self.window + off, v)
        self.fonts = {}

    # ---- SDL
    def _surface(self, w, h, rgba: bytes, masks=ABGR):
        e = self.e
        fmt = e.alloc(0x30)
        e.w32(fmt, 0x16762004)
        e.write(fmt + 8, bytes([32, 4]))
        for k, m in enumerate(masks):
            e.w32(fmt + 0x0C + 4 * k, m)
        surf = e.alloc(0x40)
        pixels = e.alloc(w * h * 4)
        e.write(pixels, rgba)
        e.w32(surf + 4, fmt)
        e.w32(surf + 8, w)
        e.w32(surf + 0xC, h)
        e.w32(surf + 0x10, w * 4)
        e.w32(surf + 0x14, pixels)
        self.surfaces[surf] = (w, h, pixels)
        return surf

    def _create(self, em):
        w, h = em.arg(1), em.arg(2)
        masks = tuple(em.arg(k) for k in range(4, 8))
        return self._surface(w, h, b"\0" * (w * h * 4), masks), 0

    def _map(self, em):
        fmt = em.arg(0)
        r, g, b, a = (em.arg(k) & 0xFF for k in range(1, 5))
        masks = [em.r32(fmt + 0x0C + 4 * k) for k in range(4)]
        v = 0
        for c, m in zip((r, g, b, a), masks):
            shift = (m & -m).bit_length() - 1
            v |= (c << shift) & m
        return v, 0

    def _get(self, em):
        pixel, fmt = em.arg(0), em.arg(1)
        masks = [em.r32(fmt + 0x0C + 4 * k) for k in range(4)]
        for k, m in enumerate(masks):
            shift = (m & -m).bit_length() - 1
            em.write(em.arg(2 + k), bytes([(pixel & m) >> shift]))
        return 0, 0

    def _img_load(self, em):
        path = em.cstr(em.arg(0)).encode("latin-1").decode("utf-8")
        img = self.P.load_png(self.glyph_dir / Path(path.replace("\\", "/")).name)
        return self._surface(img.width, img.height, bytes(img.data)), 0

    def _upper_blit(self, em):
        src, srect, dst, drect = (em.arg(k) for k in range(4))
        x, y, w, h = struct.unpack("<iiii", em.read(srect, 16))
        dx, dy = struct.unpack("<ii", em.read(drect, 8))
        sw, sh, pixels = self.surfaces[src]
        rows = [em.read(pixels + ((y + yy) * sw + x) * 4, w * 4) for yy in range(h)]
        self.blits.append((dx, dy, w, h, b"".join(rows)))
        return 0, 0

    # ---- files
    def _open(self, em):
        name = em.wstr(em.arg(0)).replace("\\", "/").rsplit("/", 1)[-1]
        path = self.glyph_dir / name
        if not path.is_file():
            return 0xFFFFFFFF, 28
        handle = 0x500 + len(self.files)
        self.files[handle] = path.read_bytes()
        return handle, 28

    def _size(self, em):
        return len(self.files[em.arg(0)]), 8

    def _read_file(self, em):
        data = self.files[em.arg(0)]
        n = min(em.arg(2), len(data))
        em.write(em.arg(1), data[:n])
        em.w32(em.arg(3), n)
        return 1, 20

    def _w2mb(self, em):
        text = em.wstr(em.arg(2)).encode("utf-8") + b"\0"
        em.write(em.arg(4), text)
        return len(text), 32

    def _lstrcat(self, em):
        a, b = em.arg(0), em.arg(1)
        s = em.wstr(a) + em.wstr(b)
        em.write(a, s.encode("utf-16-le") + b"\0\0")
        return a, 8

    # ---- a game font object, as ldwFont::Load leaves it, with the original game's sheet
    def font(self, name):
        if name in self.fonts:
            return self.fonts[name]
        e = self.e
        f = T.load_font(name)
        sheet = self.P.load_png(GAME_IMAGES / f.image)
        surf = self._surface(sheet.width, sheet.height, bytes(sheet.data))
        image_impl = e.alloc(8)
        e.w32(image_impl, surf)
        table = e.alloc(20 * (len(f.glyphs) + 1))
        for k, g in enumerate(f.glyphs):
            e.write(table + 20 * k, struct.pack("<iiiii", *g))
        impl = e.alloc(0x420)
        e.w32(impl, 0x1234)
        e.w32(impl + 4, f.line_height)
        e.w32(impl + 8, f.kerning)
        e.w32(impl + 0xC, image_impl)
        e.w32(impl + 0x10, table)
        e.w32(impl + 0x14, sheet.width)
        e.w32(impl + 0x18, sheet.height)
        e.write(impl + 0x1C, struct.pack("<256i", *f.charmap))
        font = e.alloc(8)
        e.w32(font + 4, impl)
        self.fonts[name] = (font, f, sheet)
        return self.fonts[name]

    def draw(self, name, raw, x=3, y=5):
        font, _f, _sheet = self.font(name)
        text = self.e.alloc(len(raw) + 1)
        self.e.write(text, raw + b"\0")
        self.blits = []
        self.e.call(self.h["draw_string"], (text, x, y, 0xFFFFFFFF, font), ecx=self.window, edx=0)
        return list(self.blits)

    def width(self, name, raw):
        font, _f, _s = self.font(name)
        text = self.e.alloc(len(raw) + 1)
        self.e.write(text, raw + b"\0")
        v = self.e.call(self.h["get_width"], (text, struct.unpack("<I", struct.pack("<f", 1.0))[0]),
                        ecx=font, edx=0)
        return struct.unpack("<i", struct.pack("<I", v))[0]


@pytest.fixture(scope="module")
def draw_world(exe, dlls, tmp_path_factory):
    if not (GAME_IMAGES / "Segoe24.png").is_file():
        pytest.skip("no original game folder (work/vanilla_runtime_payload)")
    import vf2_glyph_maker as M
    folder = tmp_path_factory.mktemp("unicode_text")
    M.write_sheets(GAME_IMAGES, folder)
    return DrawWorld(exe, dlls[1], folder), M.load_fonts(GAME_IMAGES)


SAMPLES = ["Łódź Żółć", "İstanbul ığüşöç", "José Müller", "Nguyễn Thị", "€5 “quotes” — ok…", "Αθήνα Москва",
           "Hi!\nZoë", "e\u0301 a\u0308"]


@pytest.mark.parametrize("name", T.FONT_NAMES)
def test_the_games_drawstring_draws_what_the_patcher_draws(draw_world, name):
    """Every blit the DLL's DrawString makes (place and pixels) is a glyph the patcher's text drawing places at the
    same spot with the same pixels: the game font's own letters and the patcher-made ones."""
    w, fonts = draw_world
    font, sheet = fonts[name]
    for text in SAMPLES:
        raw = T.encode(text)
        game = w.draw(name, raw)
        mine = []
        for p in T.draw_string(font, raw, 3, 5):
            gw, gh, data = T.glyph_pixels(font, p.glyph, sheet)
            mine.append((p.x, p.y, gw, gh, data))
        assert [(x, y, ww, hh) for x, y, ww, hh, _d in game] == [(x, y, ww, hh) for x, y, ww, hh, _d in mine], text
        for (x, y, ww, hh, a), (_x, _y, _w, _h, b) in zip(game, mine):
            # the same alpha everywhere; colour only where the pixel shows (a clear pixel's colour is unseen)
            assert a[3::4] == b[3::4], (text, x)
        assert w.width(name, raw) == T.get_width(font, raw), text
