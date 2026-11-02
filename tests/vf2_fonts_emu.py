"""Run the game's own font code from the B200 desktop objects (unicorn), for the Picture Maker's fonts
(src/vf2_art_fonts.py).

* FontRig links ldwFont, ldwFontImpl, the four font classes and ldwGameWindow. A font class's constructor runs
  whole (ldwFont::Load -> ldwFontImpl::Load); the picture is a seam that gives the real file's pixels as an SDL
  surface (32-bit ARGB). ldwFontImpl::GetCharSourceRect, ldwFontImpl::GetImage (the colouring, on the real pixels)
  and ldwGameWindowImpl::DrawString (with its ClipRect) run whole; SDL_UpperBlit and BlitRectWithAlpha are recorded.
* font_colours scans the objects' code for the colours passed with each font id (theStringManager::GetFont).

Nothing here starts the game or writes a file.
"""
from __future__ import annotations

import re
import struct
from collections import defaultdict
from pathlib import Path

import vf2_people_emu as pe

OBJECTS = ["ldwFont", "ldwFontImpl", "Segoe24", "Segoe24Bold", "Segoe32Bold", "Segoe36Bold", "ldwGameWindow"]
MASKS = (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)        # the surfaces' R, G, B, A masks


class FontRig:
    def __init__(self, obj_dir: Path, game: Path):
        import vf2_game_pictures as gp
        self.files = gp.GameFiles(game)
        self.e = e = pe.Emu(obj_dir, OBJECTS)
        self.names: dict[int, str] = {}
        self.surfaces: dict[int, tuple] = {}            # surface -> (width, height, pixels address)
        self.blits: list = []
        e.seam("??2@YAPAXI@Z", lambda em: (self._zalloc(max(4, em.arg(0))), 0))
        e.seam("??3@YAXPAXI@Z", lambda em: (0, 0))
        e.seam("_strchr", self._strchr)
        e.seam("?Exists@ldwImage@@SA_NPBD@Z", lambda em: (int(self.files.has(em.cstr(em.arg(0)))), 0))
        e.seam("??0ldwImageImpl@@QAE@PBD@Z", self._image_impl)
        e.seam("?GetGraphic@ldwImageImpl@@QAEPAUSDL_Surface@@XZ", lambda em: (self._picture(em.ecx), 0))
        e.seam("_SDL_CreateRGBSurface", self._create)
        e.seam("_SDL_LockSurface", lambda em: (0, 0))
        e.seam("_SDL_UnlockSurface", lambda em: (0, 0))
        e.seam("_SDL_MapRGBA", self._map)
        e.seam("_SDL_UpperBlit", self._blit)
        e.seam("?BlitRectWithAlpha@ldwGameWindowImpl@@AAEXPAUSDL_Surface@@HHHHHHMM_N@Z",
               lambda em: (self.blits.append(("alpha", [em.arg(k) for k in range(10)])), (0, 40))[1])
        self.format = self._zalloc(0x40)
        e.write(self.format + 8, bytes([32, 4]))
        for k, m in enumerate(MASKS):
            e.w32(self.format + 0xC + 4 * k, m)
        self.screen = self._zalloc(0x40)
        self.window = self._zalloc(0x100)
        e.w32(self.window + 0x30, self.screen)
        for k, v in enumerate((0, 0, 1024, 768)):
            e.w32(self.window + 0x60 + 4 * k, v)
        self.fonts: dict[str, int] = {}

    # ---- memory and seams
    def _zalloc(self, size):
        at = self.e.alloc(size)
        self.e.write(at, bytes(size))
        return at

    def _strchr(self, em):
        at = text_find(em.cstr(em.arg(0)), em.arg(1) & 0xFF)
        return (em.arg(0) + at if at >= 0 else 0), 0

    def _image_impl(self, em):
        self.names[em.ecx] = em.cstr(em.arg(0))
        return em.ecx, 4

    def _surface(self, w, h, pixels: bytes | None = None):
        s = self._zalloc(0x40)
        data = self._zalloc(4 * w * h)
        if pixels is not None:
            self.e.write(data, pixels)
        for off, v in ((4, self.format), (8, w), (0xC, h), (0x10, 4 * w), (0x14, data)):
            self.e.w32(s + off, v)
        self.surfaces[s] = (w, h, data)
        return s

    def _picture(self, impl):
        key = ("picture", impl)
        if key not in self.surfaces:
            image = self.files.image(self.names[impl])
            d = image.data
            raw = bytearray(4 * image.width * image.height)
            for i in range(0, len(d), 4):
                r, g, b, a = d[i], d[i + 1], d[i + 2], d[i + 3]
                raw[i:i + 4] = struct.pack("<I", (a << 24) | (r << 16) | (g << 8) | b)
            self.surfaces[key] = self._surface(image.width, image.height, bytes(raw))
        return self.surfaces[key]

    def _create(self, em):
        assert tuple(em.arg(4 + k) for k in range(4)) == MASKS and em.arg(3) == 32
        return self._surface(em.arg(1), em.arg(2)), 0

    def _map(self, em):
        r, g, b, a = (em.arg(k) & 0xFF for k in range(1, 5))
        return (a << 24) | (r << 16) | (g << 8) | b, 0

    def _blit(self, em):
        src, sr, dr = em.arg(0), em.arg(1), em.arg(3)
        rect = tuple(em.s32(sr + 4 * k) for k in range(4))
        self.blits.append(("blit", src, (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]),
                           em.s32(dr), em.s32(dr + 4)))
        return 0, 0

    # ---- the game's font code
    def font(self, name: str) -> int:
        """A font class made by its own constructor (ldwFont::Load runs whole)."""
        if name not in self.fonts:
            this = self._zalloc(8)
            self.e.call(f"??0{name}@@QAE@XZ", ecx=this)
            self.fonts[name] = this
        return self.fonts[name]

    def impl(self, name: str) -> int:
        return self.e.r32(self.font(name) + 4)

    def char_rect(self, name: str, ch: int) -> tuple:
        impl, rect = self.impl(name), self._zalloc(16)
        self.e.call(self.e.r32(self.e.r32(impl) + 4), [ch if ch < 0x80 else ch - 0x100, rect], ecx=impl)
        return tuple(self.e.s32(rect + 4 * k) for k in range(4))

    def draw_string(self, name: str, text: bytes, x: int, y: int, colour: int) -> list:
        self.blits = []
        at = self._zalloc(len(text) + 1)
        self.e.write(at, text + b"\0")
        self.e.call("?DrawString@ldwGameWindowImpl@@QAEXPBDHHUldwColor@@PAVldwFont@@@Z",
                    [at, x, y, colour, self.font(name)], ecx=self.window)
        return self.blits

    def pixels(self, surface: int) -> bytes:
        """A surface's pixels as straight RGBA."""
        w, h, data = self.surfaces[surface]
        raw = self.e.read(data, 4 * w * h)
        out = bytearray(len(raw))
        for i in range(0, len(raw), 4):
            v = struct.unpack_from("<I", raw, i)[0]
            out[i:i + 4] = bytes(((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF, v >> 24))
        return bytes(out)

    def picture_surface(self, name: str) -> int:
        return self.surfaces[("picture", self.e.r32(self.impl(name) + 0xC))]


def text_find(text: str, ch: int) -> int:
    return text.find(chr(ch)) if ch else len(text)


# ---------------------------------------------------------------- the colours passed with each font
FONT_GETTERS = {"?GetFont@theStringManager@@QAEPAVldwFont@@W4FontId@@@Z": None,
                "?GetLargeFont@theStringManager@@QAEPAVldwFont@@XZ": 3,
                "?GetMediumFont@theStringManager@@QAEPAVldwFont@@XZ": 2,
                "?GetTinyFont@theStringManager@@QAEPAVldwFont@@XZ": 0}
TEXT_CALLS = re.compile(r"DrawString|DrawChars|SetColors@ldwTextControl|SetText@ldwButton")


def font_colours(obj_dir: Path):
    """({font id: {colour: {site}}}, {font id argument: {site}}): in every function of every object that asks
    theStringManager for a font, each text call after it (a draw, a button's SetText, a text control's SetColors;
    a text control's constructor carries the font on to its SetColors) pairs the font asked for since the last text
    call with the colours named since then (the cLdw* colour constants and 0xFF?????? immediates; cLdwNoColor left
    out). A site is the function's name up to its class."""
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    colours, args = defaultdict(lambda: defaultdict(set)), defaultdict(set)
    for path in sorted(Path(obj_dir).glob("*.obj")):
        o = pe.CoffObject(path)
        names = {n for n, _v, _s, _c in o.symbols.values()}
        if not names & set(FONT_GETTERS):
            continue
        consts = {}
        for n, v, s, _c in o.symbols.values():
            if n.startswith("?cLdw") and "UldwColor" in n and s > 0:
                sec = o.sections[s - 1]
                consts[n] = struct.unpack_from("<I", o.data, sec["ptr"] + v)[0]
        by_sect = defaultdict(list)
        for n, v, s, c in o.symbols.values():
            if s > 0 and c in (2, 3) and not n.startswith((".", "$")) and o.sections[s - 1]["chars"] & 0x20:
                by_sect[s].append((v, n))
        for s, syms in by_sect.items():
            sec = o.sections[s - 1]
            syms.sort()
            relocs = {va: o.symbols[si][0] for va, si, _t in sec["relocs"]}
            for k, (v, n) in enumerate(syms):
                end = syms[k + 1][0] if k + 1 < len(syms) else sec["size"]
                code = o.data[sec["ptr"] + v:sec["ptr"] + end]
                site = n.split("@@")[0]
                font, seen, last_push = None, set(), None
                for ins in md.disasm(code, v):
                    refs = [relocs[a] for a in range(ins.address, ins.address + ins.size) if a in relocs]
                    for r in refs:
                        if r in consts and not r.startswith("?cLdwNoColor"):
                            seen.add(consts[r])
                    if ins.mnemonic == "mov" and re.search(r", 0x[fF][fF][0-9a-fA-F]{6}$", ins.op_str):
                        seen.add(int(ins.op_str.split(", ")[1], 16))
                    if ins.mnemonic == "push" and not refs:
                        last_push = ins.op_str
                    if ins.mnemonic != "call" or not refs:
                        continue
                    callee = refs[0]
                    if callee in FONT_GETTERS:
                        f = FONT_GETTERS[callee]
                        if f is None:
                            try:
                                f = int(last_push, 0)
                            except (TypeError, ValueError):
                                f = f"?{last_push}"
                        if not (callee in FONT_GETTERS and n in FONT_GETTERS):
                            args[f].add(site)
                        font = f
                    elif TEXT_CALLS.search(callee):
                        if font is not None:
                            for c in seen:
                                colours[font][c].add(site)
                        font, seen = None, set()
    return colours, args
