#!/usr/bin/env python3
"""Prove the Unicode Text sites against B200 executables and write the companion DLL's header.

    gen_b200_unicode_sites.py --exe "<core>\\Virtual Families 2 - B205.exe" [--also <exe> ...] [--write]
                              [--objs work/desktop_obj_files]

* every pin of runtime/b200_unicode_sites.FUNCTIONS is the whole stock function from its B200 desktop object file;
  a relocated field (any relocation of the object) is a wildcard;
* resolve(exe): each pin is found in the executable's code exactly once; each site of SITES is derived (the pin's
  address, or the target of each of its calls to a symbol) and every derivation of a site agrees; the RTTI vtables
  of ldwFontImpl and ldwTextControlImpl hold GetCharSourceRect and HandleKey in the slots the DLL replaces; the
  SDL_PollEvent call goes through an import thunk (jmp dword ptr [slot]) whose slot is in the import table;
  DrawStringJustified starts with the 9 bytes the DLL moves to its trampoline.
* render_header(): runtime/native/b200unicode/b200unicode_sites.h: the pins, masks, evidence, constants and the
  four fonts' signatures and fitted drawing (src/vf2_game_fonts.json).
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))
import b200_unicode_sites as S  # noqa: E402

HEADER = ROOT / "runtime" / "native" / "b200unicode" / "b200unicode_sites.h"
FONTS_JSON = ROOT / "src" / "vf2_game_fonts.json"
SIGNATURE_GLYPHS = 24
IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_SCN_MEM_WRITE = 0x80000000
IMAGE_SCN_MEM_READ = 0x40000000


class SiteError(RuntimeError):
    pass


# ---------------------------------------------------------------------------------------------- objects
class Coff:
    def __init__(self, path: Path):
        b = Path(path).read_bytes()
        self.data = b
        machine, nsects, _ts, symptr, nsyms, opthdr, _ch = struct.unpack_from("<HHIIIHH", b, 0)
        if machine != 0x14C:
            raise SiteError(f"{path}: not an x86 object")
        strtab = symptr + nsyms * 18
        self.sections = []
        off = 20 + opthdr
        for _ in range(nsects):
            vsize, vaddr, rsize, rptr, relptr, _lp, nrel, _nl, chars = struct.unpack_from("<IIIIIIHHI", b, off + 8)
            relocs = [struct.unpack_from("<IIH", b, relptr + 10 * k) for k in range(nrel)]
            self.sections.append((b[rptr:rptr + rsize], relocs))
            off += 40
        self.names = {}
        self.where = {}
        k = 0
        while k < nsyms:
            at = symptr + 18 * k
            raw = b[at:at + 8]
            if raw[:4] == b"\0\0\0\0":
                n = struct.unpack_from("<I", raw, 4)[0]
                name = b[strtab + n:b.index(b"\0", strtab + n)].decode("latin-1")
            else:
                name = raw.split(b"\0")[0].decode("latin-1")
            value, sect, _typ, cls, naux = struct.unpack_from("<IhHBB", b, at + 8)
            self.names[k] = name
            if sect > 0 and cls == 2 and value == 0:
                self.where.setdefault(name, sect - 1)
            k += 1 + naux

    def function(self, name: str):
        if name not in self.where:
            raise SiteError(f"{name} is not defined in the object")
        data, relocs = self.sections[self.where[name]]
        mask = bytearray(len(data))
        calls, absolutes = [], []
        for off, sym, typ in relocs:
            for i in range(4):
                if off + i < len(mask):
                    mask[off + i] = 1
            if typ == 0x14:                 # REL32
                calls.append((off, self.names[sym]))
            elif typ == 0x06:               # DIR32: an absolute address field
                absolutes.append((off, self.names[sym]))
        return bytes(data), bytes(mask), calls, absolutes


def load_pins(objs: Path) -> list:
    cache = {}
    pins = []
    for name, obj, func in S.FUNCTIONS:
        if obj not in cache:
            cache[obj] = Coff(Path(objs) / f"{obj}.obj")
        data, mask, calls, absolutes = cache[obj].function(func)
        pins.append({"name": name, "bytes": data, "mask": mask, "calls": calls, "absolutes": absolutes})
    return pins


# ---------------------------------------------------------------------------------------------- executable
class Exe:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.pe = pefile.PE(str(path), fast_load=True)
        self.pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.sections = []
        for s in self.pe.sections:
            raw = s.get_data()[:s.SizeOfRawData]
            self.sections.append((s.Name.rstrip(b"\0").decode(), self.base + s.VirtualAddress, raw, s.Characteristics))
        self.imports = {}
        for entry in getattr(self.pe, "DIRECTORY_ENTRY_IMPORT", []):
            for imp in entry.imports:
                if imp.name:
                    self.imports[imp.address] = (entry.dll.decode(), imp.name.decode())

    def read(self, va: int, n: int) -> bytes:
        for _n, sva, raw, _c in self.sections:
            if sva <= va and va + n <= sva + len(raw):
                return raw[va - sva:va - sva + n]
        raise SiteError(f"{va:#x} is not in the file")

    def u32(self, va):
        return struct.unpack("<I", self.read(va, 4))[0]

    def code(self):
        return [s for s in self.sections if s[3] & IMAGE_SCN_MEM_EXECUTE]

    def rodata(self):
        return [s for s in self.sections if not s[3] & (IMAGE_SCN_MEM_EXECUTE | IMAGE_SCN_MEM_WRITE)
                and s[3] & IMAGE_SCN_MEM_READ]

    def data(self):
        return [s for s in self.sections if not s[3] & IMAGE_SCN_MEM_EXECUTE and s[3] & IMAGE_SCN_MEM_READ]


def _regex(data: bytes, mask: bytes):
    out = b"".join(b"." if m else re.escape(bytes([c])) for c, m in zip(data, mask))
    return re.compile(out, re.DOTALL)


def find(sections, data, mask) -> list:
    rx = _regex(data, mask)
    hits = []
    for _n, va, raw, _c in sections:
        for m in rx.finditer(raw):
            hits.append(va + m.start())
    return hits


def vtable(exe: Exe, type_name: str) -> int:
    name = type_name.encode() + b"\0"
    hits = find(exe.data(), name, bytes(len(name)))
    if len(hits) != 1:
        raise SiteError(f"{type_name}: type descriptor found {len(hits)} times")
    td = hits[0] - 8
    cols = []
    for _n, va, raw, _c in exe.rodata():
        for k in range(0, len(raw) - 16, 4):
            if struct.unpack_from("<I", raw, k + 12)[0] == td and raw[k:k + 8] == bytes(8):
                cols.append(va + k)
    if len(cols) != 1:
        raise SiteError(f"{type_name}: complete object locator found {len(cols)} times")
    vts = []
    for _n, va, raw, _c in exe.rodata():
        for k in range(0, len(raw) - 4, 4):
            if struct.unpack_from("<I", raw, k)[0] == cols[0]:
                vts.append(va + k + 4)
    if len(vts) != 1:
        raise SiteError(f"{type_name}: vtable found {len(vts)} times")
    return vts[0]


def resolve(exe: Exe, pins: list) -> dict:
    loc = {}
    for p in pins:
        hits = find(exe.code(), p["bytes"], p["mask"])
        if len(hits) != 1:
            raise SiteError(f"{exe.path.name}: pin {p['name']} found {len(hits)} times")
        loc[p["name"]] = hits[0]
    by_name = {p["name"]: p for p in pins}
    sites = {}
    for site, pin, how in S.SITES:
        values = []
        if how == "entry":
            values.append(loc[pin])
        else:
            sym = how[1]
            for off, name in by_name[pin]["calls"]:
                if name == sym:
                    at = loc[pin] + off
                    values.append((at + 4 + exe.u32(at)) & 0xFFFFFFFF)
            if how[0] == "abs":
                values = []
                for off, name in by_name[pin]["absolutes"]:
                    if name == sym:
                        values.append(exe.u32(loc[pin] + off))
            if not values:
                raise SiteError(f"{pin} has no {how[0]} reference to {sym}")
        for v in values:
            if site in sites and sites[site] != v:
                raise SiteError(f"{exe.path.name}: {site} derived as {sites[site]:#x} and {v:#x}")
            sites[site] = v
    fvt = vtable(exe, S.FONT_TYPE_NAME)
    if exe.u32(fvt + 4 * S.FONT_VSLOT_CHAR_RECT) != sites["CHAR_RECT"]:
        raise SiteError("ldwFontImpl's vtable slot 1 is not GetCharSourceRect")
    tvt = vtable(exe, S.TEXT_TYPE_NAME)
    if exe.u32(tvt + 4 * S.TEXT_VSLOT_HANDLE_KEY) != sites["TEXT_HANDLE_KEY"]:
        raise SiteError("ldwTextControlImpl's vtable slot 2 is not HandleKey")
    thunk = exe.read(sites["POLL_EVENT"], 6)
    if thunk[:2] != b"\xFF\x25":
        raise SiteError("SDL_PollEvent is not called through an import thunk")
    slot = struct.unpack("<I", thunk[2:])[0]
    if exe.imports.get(slot) != ("SDL2.dll", "SDL_PollEvent"):
        raise SiteError(f"the thunk's slot {slot:#x} is not SDL2.dll!SDL_PollEvent ({exe.imports.get(slot)})")
    head = exe.read(sites["DRAW_JUSTIFIED"], S.JUSTIFIED_STEAL)
    if head != bytes.fromhex("558BEC81EC50050000"):
        raise SiteError("DrawStringJustified does not start with push ebp; mov ebp,esp; sub esp,550h")
    return {"pins": loc, "sites": sites, "font_vtable": fvt, "text_vtable": tvt, "poll_slot": slot}


# ---------------------------------------------------------------------------------------------- header
def _arr(name: str, data: bytes) -> str:
    rows = []
    for i in range(0, len(data), 24):
        rows.append("    " + " ".join(f"0x{b:02X}," for b in data[i:i + 24]))
    return f"static const unsigned char {name}[] = {{\n" + "\n".join(rows) + "\n};"


def render_header(pins: list) -> str:
    site_names = []
    for site, _pin, _how in S.SITES:
        if site not in site_names:
            site_names.append(site)
    fonts = json.loads(FONTS_JSON.read_text(encoding="utf-8"))["fonts"]
    out = ["// GENERATED by runtime/tools/gen_b200_unicode_sites.py from runtime/b200_unicode_sites.py, the B200",
           "// desktop object files and src/vf2_game_fonts.json. Do not edit. The DLL holds no game address: it finds",
           "// each whole stock function (mask 1 = a relocated field) in the live executable exactly once and derives",
           "// every site from where they are; it installs nothing unless every derivation agrees.",
           "#pragma once", "",
           "struct UniPin { const char *name; unsigned len; const unsigned char *bytes; const unsigned char *mask; };",
           "struct UniEvidence { unsigned char site; char kind; unsigned char pin; unsigned offset; };",
           "struct UniFont {",
           "    const char *name; int lineHeight; int signature[24]; int px; int weight; int top;",
           "    unsigned char alpha[256];", "};", "",
           f"#define UNI_STATUS_MAGIC 0x{S.STATUS_MAGIC:X}u",
           f"#define UNI_KEY_TYPE_CHARACTER {S.KEY_TYPE_CHARACTER}",
           f"#define UNI_KEY_MARK 0x{S.KEY_MARK:X}u",
           f"#define UNI_SDL_TEXTINPUT 0x{S.SDL_TEXTINPUT:X}u",
           f"#define UNI_SDL_HIDDEN_EVENT 0x{S.SDL_HIDDEN_EVENT:X}u",
           f"#define UNI_TEXT_FIELD 0x{S.TEXT_FIELD:X}u",
           f"#define UNI_FONT_VSLOT_CHAR_RECT {S.FONT_VSLOT_CHAR_RECT}u",
           f"#define UNI_TEXT_VSLOT_HANDLE_KEY {S.TEXT_VSLOT_HANDLE_KEY}u",
           f'#define UNI_FONT_TYPE_NAME "{S.FONT_TYPE_NAME}"',
           f'#define UNI_TEXT_TYPE_NAME "{S.TEXT_TYPE_NAME}"',
           f"#define UNI_JUSTIFIED_STEAL {S.JUSTIFIED_STEAL}u", "",
           "enum UniSite {"]
    out += [f"    UNI_SITE_{n}," for n in site_names] + ["    UNI_SITE_COUNT", "};", "", "enum UniPinId {"]
    out += [f"    UNI_PIN_{p['name'].upper()}," for p in pins] + ["    UNI_PIN_COUNT", "};", ""]
    for p in pins:
        out.append(_arr(f"upin_{p['name']}", p["bytes"]))
        out.append(_arr(f"upinmask_{p['name']}", p["mask"]))
    out += ["", "static const UniPin UNI_PINS[] = {"]
    out += [f'    {{ "{p["name"]}", {len(p["bytes"])}u, upin_{p["name"]}, upinmask_{p["name"]} }},' for p in pins]
    out += ["};", "", "// kind L = the pin's address + offset; C = the target of the rel32 call field at pin + offset;",
            "// A = the address held in the absolute field at pin + offset",
            "static const UniEvidence UNI_EVIDENCE[] = {"]
    index = {p["name"]: i for i, p in enumerate(pins)}
    by_name = {p["name"]: p for p in pins}
    for site, pin, how in S.SITES:
        si = site_names.index(site)
        if how == "entry":
            out.append(f"    {{ UNI_SITE_{site}, 'L', {index[pin]}, 0x0u }},")
        elif how[0] == "abs":
            for off, name in by_name[pin]["absolutes"]:
                if name == how[1]:
                    out.append(f"    {{ UNI_SITE_{site}, 'A', {index[pin]}, 0x{off:X}u }},")
        else:
            for off, name in by_name[pin]["calls"]:
                if name == how[1]:
                    out.append(f"    {{ UNI_SITE_{site}, 'C', {index[pin]}, 0x{off:X}u }},")
    out += ["};", "", "// the four game fonts: line height, the widths of the first 24 glyph entries (how the DLL knows",
            "// which font a font object is), and the fitted Segoe UI drawing with its alpha levels",
            "static const UniFont UNI_FONTS[] = {"]
    for name in ("Segoe24", "Segoe24Bold", "Segoe32Bold", "Segoe36Bold"):
        f = fonts[name]
        sig = [g[3] - g[1] for g in f["glyphs"][:SIGNATURE_GLYPHS]]
        g = f["gdi"]
        out.append(f'    {{ "{name}", {f["line_height"]}, {{{", ".join(map(str, sig))}}}, {g["px"]}, {g["weight"]}, '
                   f'{g["top"]},')
        out.append("      {" + ", ".join(str(v) for v in g["alpha"]) + "} },")
    out += ["};", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True, type=Path)
    ap.add_argument("--also", nargs="*", default=[], type=Path)
    ap.add_argument("--objs", type=Path, default=ROOT / "work" / "desktop_obj_files")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    pins = load_pins(a.objs)
    for path in [a.exe, *a.also]:
        r = resolve(Exe(path), pins)
        print(f"{path.name}: {len(r['pins'])} pins, {len(r['sites'])} sites, poll slot {r['poll_slot']:#x}")
    text = render_header(pins)
    if a.write:
        HEADER.parent.mkdir(parents=True, exist_ok=True)
        HEADER.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {HEADER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
