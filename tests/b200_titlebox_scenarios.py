"""The Title Screen Player Name Box DLL (vf2titlebox_b200.dll) drawing a title screen frame, under emulation.

The REAL executable (the B200 core, or any later matrix build) and the REAL compiled test DLL share one emulated
address space (tests/b200_time_emu.py). Game code that runs for real, at the link address or relocated:
ldwScene::Draw (DrawScene through the vtable slot the DLL replaces, DrawControls, DrawSceneFinal's slot, DrawHints),
theMenuScene::DrawScene, ldwTextControl's constructor (with its ldwHintControl base and its ldwTextControlImpl:
SetText and SetBoundsFromText with the real font), SetColors, SetText, ldwScene::AddControl, ldwTextControl::Draw
and ldwTextControlImpl::Draw, ldwFont::GetWidth / GetHeight with ldwFontImpl::IsValid / GetCharSourceRect on the
game's own Segoe32Bold metrics (src/vf2_game_fonts.json, made from the game's own answers), ldwScene::GetBounds,
ldwGameWindow::Get's callers, GetFont, and ldwGameWindow::FillRect with ldwGameWindowImpl::FillRect's own blend
into an emulated 1024 x 768 ARGB8888 screen.

Seams (recorded, never real): theGraphicsManager (the background picture is painted by the DrawCell seam: the
game's vf2_boxshot.jpg when the game's Images are at hand, else a fixed pattern), the distributor's logo (none),
DrawSceneFinal (the butterflies), the text control's SetActive (it shows the control; its event subscription is
input only), ldwGameWindow::DrawString (recorded; for the preview picture it paints the glyphs of the game's own
font sheet), operator new, and the SDL calls FillRect makes (MapRGB, MapRGBA, Lock/UnlockSurface, FillRect).

Nothing here starts the game, and nothing writes the executable on disk.
"""
from __future__ import annotations

import json
import os
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "runtime" / "tools"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
import b200_titlebox_sites as S  # noqa: E402
import gen_b200_titlebox_sites as G  # noqa: E402

from b200_time_emu import DLL_BASE, Emu  # noqa: E402

SCREEN_W, SCREEN_H = 1024, 768
PITCH = SCREEN_W * 4
NO_COLOR = 0
FONT_NAMES = ("Segoe24", "Segoe24Bold", "Segoe32Bold", "Segoe36Bold")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")

_PROVED = {}


def proved(exe_path):
    """(model of the core variant, derived sites of this executable), cached. The model comes from the core
    variant (VF2_B200_CORE_EXE); exe_path may be any variant."""
    key = str(exe_path)
    if key not in _PROVED:
        core = os.environ.get("VF2_B200_CORE_EXE") or key
        model = G.validate(Path(core).read_bytes())
        _PROVED[key] = (model, G.resolve(G.Exe(Path(key).read_bytes()), model))
    return _PROVED[key]


def rtti_vtable(exe: G.Exe, cls: str) -> int:
    """The one vtable of class `cls` (the same RTTI walk as the DLL's)."""
    saved = S.MENU_CLASS
    try:
        S.MENU_CLASS = cls
        return G.menu_vtable(exe)
    finally:
        S.MENU_CLASS = saved


def blend(byte: int) -> int:
    """ldwGameWindowImpl::FillRect's blend of one colour byte with white at alpha 33h (a = int(0.2 * 255 + 0.5))."""
    a = int(S.BOX_ALPHA / 255.0 * 255 + 0.5)
    return ((byte * (255 - a)) >> 8) + ((255 * a) >> 8) & 0xFF


def background_pixels() -> bytes:
    """The title screen's background, 1024 x 768 BGRA (ARGB8888 in memory): the game's vf2_boxshot.jpg when the
    game's Images are at hand, else a fixed pattern that has every byte value in it."""
    pic = GAME_DIR / "Images" / "vf2_boxshot.jpg"
    if pic.is_file():
        from PIL import Image
        im = Image.open(pic).convert("RGB")
        canvas = Image.new("RGB", (SCREEN_W, SCREEN_H), (0, 0, 0))
        canvas.paste(im, ((SCREEN_W - im.width) // 2, 0))
        r, g, b = canvas.split()
        a = Image.new("L", canvas.size, 255)
        return Image.merge("RGBA", (b, g, r, a)).tobytes()
    out = bytearray(SCREEN_W * SCREEN_H * 4)
    for y in range(SCREEN_H):
        for x in range(SCREEN_W):
            o = (y * SCREEN_W + x) * 4
            out[o] = (x * 7 + y) & 0xFF
            out[o + 1] = (x + y * 3) & 0xFF
            out[o + 2] = (x ^ y) & 0xFF
            out[o + 3] = 0xFF
    return bytes(out)


class Frame:
    """One emulated process: an executable + the test DLL, the title screen set up with a player's name."""

    def __init__(self, exe, dll, *, delta=0, install=True, enabled=True, name=b"Lorsieab2", width_seam=None,
                 paint_text=False, native_scan=True):
        self.e = e = Emu(exe, dll, delta)
        self.delta = delta
        self.sites = proved(exe)[1]
        self.exe = G.Exe(Path(exe).read_bytes())
        self.events = []                # ("fill", rect) / ("text", text, x, y, colour, font) in draw order
        self.paint_text = paint_text
        self.font_tables = {}
        if native_scan:
            self._native_scans()
        self._screen()
        self._fonts()
        self._seams(width_seam)
        self._scene()
        self.slot = self.s("MENU_SLOT_DRAW_SCENE")
        self.stock_slot_value = e.r32(self.slot)
        self.plan = None
        if install:
            self.install(enabled)
        self.make_name_control(name)

    def s(self, name):
        return self.sites[name] + self.delta

    # ------------------------------------------------------------------ the DLL
    def _native_scans(self):
        e = self.e
        scan_at = e.call(e.dll_export("B200TitleBox_TestScanAddress"))
        next_at = e.call(e.dll_export("B200TitleBox_TestNextDwordAddress"))

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

    def test_plan(self, enabled=True):
        e = self.e
        out = e.alloc(0x100)
        status = struct.unpack("<i", struct.pack("<I", e.call(e.dll_export("B200TitleBox_TestPlan"),
                                                             (1 if enabled else 0, out))))[0]
        writes = []
        for i in range(e.r32(out + 4)):
            va, ln, data, b0, b1 = [e.r32(out + 8 + i * 20 + 4 * k) for k in range(5)]
            writes.append({"va": va, "len": ln, "data": bool(data), "bytes": struct.pack("<II", b0, b1)[:ln]})
        return status, writes

    def install(self, enabled=True):
        status, writes = self.test_plan(enabled)
        self.plan = (status, writes)
        for w in writes:
            self.e.write(w["va"], w["bytes"])
        return status, writes

    def hook_address(self):
        return self.e.call(self.e.dll_export("B200TitleBox_TestHook"))

    def status(self):
        a = self.e.dll_export("B200TitleBox_Status")
        keys = ("magic", "version", "requested", "resolved", "installed", "writeMask", "frames", "boxes",
                "lastLeft", "lastTop", "lastRight", "lastBottom")
        out = {}
        for i, k in enumerate(keys):
            v = self.e.r32(a + 4 * i)
            out[k] = v - (1 << 32) if k.startswith("last") and v & 0x80000000 else v
        return out

    # ------------------------------------------------------------------ the screen, the window, the fonts
    def _screen(self):
        e = self.e
        self.pixels = e.alloc(SCREEN_W * SCREEN_H * 4)
        self.background = background_pixels()
        self.format = e.alloc(0x40)
        self.surface = e.alloc(0x40)
        e.w32(self.surface + 4, self.format)
        e.w32(self.surface + 8, SCREEN_W)
        e.w32(self.surface + 0xC, SCREEN_H)
        e.w32(self.surface + 0x10, PITCH)
        e.w32(self.surface + 0x14, self.pixels)
        self.window_impl = e.alloc(0x100)
        e.w32(self.window_impl + 0x30, self.surface)
        for off, v in ((0x60, 0), (0x64, 0), (0x68, SCREEN_W), (0x6C, SCREEN_H)):
            e.w32(self.window_impl + off, v)
        self.window = e.alloc(0x20)
        e.w32(self.window + S.WINDOW_IMPL_FIELD, self.window_impl)

    def _fonts(self):
        """The four game fonts as ldwFont objects over ldwFontImpl data laid out as ldwFontImpl::Load leaves it."""
        e = self.e
        data = json.loads((ROOT / "src" / "vf2_game_fonts.json").read_text(encoding="utf-8"))["fonts"]
        impl_vtable = rtti_vtable(self.exe, "ldwFontImpl") + self.delta
        self.fonts = {}
        for name in FONT_NAMES:
            f = data[name]
            impl = e.alloc(0x41C + 16)
            e.w32(impl, impl_vtable)
            e.w32(impl + 4, f["line_height"])
            e.w32(impl + 8, f["kerning"] & 0xFFFFFFFF)
            image = e.alloc(0x10)
            e.w32(impl + 0xC, image)                 # IsValid: an image
            table = e.alloc(20 * (len(f["glyphs"]) + 1))
            for k, (ch, l, t, r, b) in enumerate(f["glyphs"]):
                e.write(table + 20 * k, struct.pack("<iiiii", ch, l, t, r, b))
            e.write(table + 20 * len(f["glyphs"]), b"\0" * 20)
            e.w32(impl + 0x10, table)
            e.w32(impl + 0x14, f["sheet"][0])
            e.w32(impl + 0x18, f["sheet"][1])
            e.write(impl + 0x1C, struct.pack("<256i", *f["charmap"]))
            font = e.alloc(0x10)
            e.w32(font + 4, impl)
            self.fonts[name] = font
        self.font_names = {v: k for k, v in self.fonts.items()}
        # theStringManager::LoadFonts: the window's own font is Segoe32Bold
        e.w32(self.window_impl + 0x5C, self.fonts[FONT_NAMES[S.DEFAULT_FONT_INDEX]])

    def clear(self):
        self.e.write(self.pixels, self.background)

    def screen(self) -> bytes:
        return self.e.read(self.pixels, SCREEN_W * SCREEN_H * 4)

    # ------------------------------------------------------------------ seams
    def _seams(self, width_seam):
        e = self.e
        e.seam_live(self.s("GAME_WINDOW_GET"), lambda emu: (self.window, 0))
        graphics = e.alloc(0x10)
        grid = e.alloc(0x10)
        e.seam_live(self.s("GRAPHICS_GET"), lambda emu: (graphics, 0))
        e.seam_live(self.s("GET_IMAGE_GRID"), lambda emu: (grid, 4))

        def cell_rect(emu):
            emu.write(emu.arg(1), struct.pack("<iiii", 0, 0, SCREEN_W, SCREEN_H))
            return 0, 8
        e.seam_live(self.s("GET_CELL_RECT"), cell_rect)

        def draw_cell(emu):
            image, cell, x, y = emu.arg(0), emu.arg(1), emu.arg(2), emu.arg(3)
            assert (image, cell, x, y) == (S.BACKGROUND_IMAGE, 0, 0, 0), (image, cell, x, y)
            self.events.append(("background",))
            self.clear()
            return 0, 0x18
        e.seam_live(self.s("DRAW_CELL"), draw_cell)
        e.seam_live(self.s("HAS_MENU_LOGO"), lambda emu: (0, 0))
        e.seam_live(self.s("OPERATOR_NEW"), lambda emu: (emu.alloc(max(emu.arg(0), 4)), 0))
        # ldwTextControlImpl::SetText (ldwTextControl::SetText jumps to it): delete the old copy (+11h), new[] the
        # new one (+50h)
        impl_set_text = self._rel(self.s("TEXT_SET_TEXT") + 7)
        for off, fn in ((0x11, lambda emu: (0, 0)), (0x50, lambda emu: (emu.alloc(max(emu.arg(0), 4)), 0))):
            e.seam_live(self._rel(impl_set_text + off), fn)
        menu_vtable = self.s("MENU_SLOT_DRAW_SCENE") - 4 * S.DRAW_SCENE_VSLOT
        final = e.r32(menu_vtable + 4 * (S.DRAW_SCENE_VSLOT + 1))
        def draw_scene_final(emu):
            self.events.append(("final",))
            return 0, 0
        e.seam_live(final, draw_scene_final)
        text_vtable = rtti_vtable(self.exe, "ldwTextControl") + self.delta

        def set_active(emu):
            impl = emu.r32(emu.ecx + S.CONTROL_IMPL_FIELD)
            emu.write(impl + S.TEXT_SHOWN, bytes([emu.arg(0) & 0xFF]))
            return 0, 4
        self.text_vtable = text_vtable
        e.seam_live(e.r32(text_vtable + 0x14), set_active)

        def draw_string(emu):
            text = emu.cstr(emu.arg(0)).encode("latin-1")
            x, y = (struct.unpack("<i", struct.pack("<I", emu.arg(k)))[0] for k in (1, 2))
            colour, font = emu.arg(3), emu.arg(4)
            fobj = font or emu.r32(self.window_impl + 0x5C)
            self.events.append(("text", text, x, y, colour, self.font_names.get(fobj, fobj)))
            if self.paint_text:
                self._paint_text(text, x, y, colour, self.font_names[fobj])
            return 0, 0x14
        e.seam_live(self.s("DRAW_STRING"), draw_string)
        e.uc.hook_add(__import__("unicorn").UC_HOOK_CODE,
                      lambda uc, a, sz, u: self.events.append(("fill", self._fill_args())),
                      begin=self.s("FILL_RECT"), end=self.s("FILL_RECT"))
        if width_seam is not None:
            def width(emu):
                return width_seam(emu.cstr(emu.arg(0)).encode("latin-1")), 8
            e.seam_live(self.s("FONT_GET_WIDTH"), width)

        # SDL, as FillRect calls it: an ARGB8888 screen
        def map_rgb(emu):
            r, g, b = emu.arg(1) & 0xFF, emu.arg(2) & 0xFF, emu.arg(3) & 0xFF
            return 0xFF000000 | r << 16 | g << 8 | b, 0

        def map_rgba(emu):
            r, g, b, a = (emu.arg(i) & 0xFF for i in range(1, 5))
            return a << 24 | r << 16 | g << 8 | b, 0

        def sdl_fill(emu):
            raise AssertionError("an opaque SDL_FillRect: the box must be blended")
        e.bind_exe_imports({"SDL_MapRGB": map_rgb, "SDL_MapRGBA": map_rgba, "SDL_FillRect": sdl_fill,
                            "SDL_LockSurface": lambda emu: (0, 0), "SDL_UnlockSurface": lambda emu: (0, 0)})

    def _rel(self, at):
        """The target of the call / jmp rel32 at `at`."""
        assert self.e.read(at, 1) in (b"\xE8", b"\xE9"), hex(at)
        return (at + 5 + self.e.rs32(at + 1)) & 0xFFFFFFFF

    def _fill_args(self):
        from unicorn.x86_const import UC_X86_REG_ESP
        e = self.e
        esp = e.reg(UC_X86_REG_ESP)
        rect = struct.unpack("<iiii", e.read(e.r32(esp + 4), 16))
        return rect, e.r32(esp + 8)

    def _paint_text(self, text, x, y, colour, font_name):
        """The preview only: the glyphs of the game's own font sheet, tinted, alpha-blended (src/vf2_game_text)."""
        import vf2_game_text as T
        import vf2_picture_image as pi
        font = T.load_font(font_name)
        sheet = pi.load_png(GAME_DIR / "Images" / f"{font_name}.png")
        rgb = (colour & 0xFF, colour >> 8 & 0xFF, colour >> 16 & 0xFF)
        for p in T.draw_string(font, text, x, y):
            w, h, rgba = T.glyph_pixels(font, p.glyph, sheet, rgb)
            for gy in range(h):
                sy = p.y + gy
                if not 0 <= sy < SCREEN_H:
                    continue
                for gx in range(w):
                    sx = p.x + gx
                    if not 0 <= sx < SCREEN_W:
                        continue
                    o = (gy * w + gx) * 4
                    a = rgba[o + 3]
                    if not a:
                        continue
                    at = self.pixels + (sy * SCREEN_W + sx) * 4
                    b0, g0, r0, _ = self.e.read(at, 4)
                    mix = lambda s, d: (s * a + d * (255 - a)) // 255  # noqa: E731
                    self.e.write(at, bytes([mix(rgba[o + 2], b0), mix(rgba[o + 1], g0), mix(rgba[o], r0), 255]))

    # ------------------------------------------------------------------ the title screen
    def _scene(self):
        e = self.e
        self.scene = scene = e.alloc(0x200)
        e.w32(scene, self.s("MENU_SLOT_DRAW_SCENE") - 4 * S.DRAW_SCENE_VSLOT)
        impl = e.alloc(0x40)
        e.write(impl, b"\x01")                       # active
        e.w32(scene + S.SCENE_IMPL_FIELD, impl)
        state = e.alloc(0x40)                        # [scene+0Ch]: the game state; [vtable+18h] the game's width
        vt = e.alloc(0x40)
        width_fn = e.fake_code(b"\xC3")
        e.seam_live(width_fn, lambda emu: (SCREEN_W, 0))
        e.w32(vt + 0x18, width_fn)
        e.w32(state, vt)
        e.w32(scene + 0xC, state)
        e.w32(scene + 0x28, 0)                       # no widescreen offset
        e.w32(scene + S.NAME_CONTROL_ID_FIELD, 7)

    def make_name_control(self, name: bytes):
        """The constructor's name control, then UpdateShowPlayer's SetText(name) and AddControl."""
        e = self.e
        placeholder = e.alloc(16)
        e.write(placeholder, b"Player 1001\0")      # sprintf(GetString(77Bh), 3E9h): a short placeholder
        ctl = e.alloc(0x20)
        scale = struct.unpack("<I", struct.pack("<f", 1.0))[0]
        e.call(self.s("TEXT_CONTROL_CTOR"),
               (self.scene, 7, S.NAME_CONTROL_X, S.NAME_CONTROL_Y, placeholder, 0, S.NAME_JUSTIFY, 0, scale), ecx=ctl)
        e.call(self.s("TEXT_SET_COLORS"), (S.NAME_COLOR, NO_COLOR), ecx=ctl)
        e.w32(self.scene + S.NAME_CONTROL_FIELD, ctl)
        self.control = ctl
        self.name_impl = e.r32(ctl + S.CONTROL_IMPL_FIELD)
        if name is not None:
            self.set_name(name)
            e.call(self.s("ADD_CONTROL"), (ctl,), ecx=self.scene)

    def set_name(self, name: bytes):
        e = self.e
        text = e.alloc(len(name) + 16)
        e.write(text, name + b"\0")
        e.call(self.s("TEXT_SET_TEXT"), (text,), ecx=self.control)

    def remove_name(self):
        """UpdateShowPlayer with no player: the name control leaves the scene's list (RemoveControl's unlink)."""
        e = self.e
        impl = e.r32(self.scene + S.SCENE_IMPL_FIELD)
        prev, node = None, e.r32(impl + S.SCENE_CONTROLS_FIELD)
        while node:
            nxt = e.r32(node + 4)
            if e.r32(node) == self.control:
                if prev is None:
                    e.w32(impl + S.SCENE_CONTROLS_FIELD, nxt)
                else:
                    e.w32(prev + 4, nxt)
            else:
                prev = node
            node = nxt

    def draw(self) -> bytes:
        """One frame: the game's own ldwScene::Draw of the title screen."""
        self.events = []
        self.clear()
        self.e.call(self.s("SCENE_DRAW"), ecx=self.scene)
        return self.screen()

    def width_of(self, text: bytes, font: str = "Segoe32Bold") -> int:
        """The game's own ldwFont::GetWidth(text, 1.0)."""
        e = self.e
        at = e.alloc(len(text) + 16)
        e.write(at, text + b"\0")
        one = struct.unpack("<I", struct.pack("<f", 1.0))[0]
        return struct.unpack("<i", struct.pack("<I", e.call(self.s("FONT_GET_WIDTH"), (at, one),
                                                            ecx=self.fonts[font])))[0]

    def line_height(self, font: str = "Segoe32Bold") -> int:
        """The game's own ldwFont::GetHeight(0)."""
        return self.e.call(self.s("FONT_GET_HEIGHT"), (0,), ecx=self.fonts[font])

    def text_rect(self):
        """Where the stock Draw put the name: (x, y) of its DrawString, and the font's line height."""
        texts = [ev for ev in self.events if ev[0] == "text"]
        assert len(texts) == 1, self.events
        return texts[0]


def pixel_diff(before: bytes, after: bytes):
    """[(x, y)] of every pixel that differs."""
    out = []
    for y in range(SCREEN_H):
        row = slice(y * PITCH, (y + 1) * PITCH)
        if before[row] == after[row]:
            continue
        for x in range(SCREEN_W):
            o = y * PITCH + x * 4
            if before[o:o + 4] != after[o:o + 4]:
                out.append((x, y))
    return out


def save_png(pixels: bytes, path: Path):
    from PIL import Image
    im = Image.frombytes("RGBA", (SCREEN_W, SCREEN_H), pixels)
    b, g, r, _a = im.split()
    Image.merge("RGB", (r, g, b)).save(path)
