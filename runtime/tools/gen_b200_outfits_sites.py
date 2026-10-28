#!/usr/bin/env python3
"""Prove the Outfit Pictures sites against the B200 executables and emit the companion DLL's header.

    gen_b200_outfits_sites.py --b200 "<core>\\Virtual Families 2 - B200.exe" [--write]
        [--also "<other variant or later build>.exe" ...]

The B200 image is relocated and every matrix variant links to different addresses, so the DLL holds
no address. This tool

* validate(core): reads the CORE variant with pefile and decodes every pin with capstone. It refuses
  (SiteError) unless every pin is the pinned bytes and whole instructions, every pin the DLL searches
  for is found exactly once, every pin found through a call is that call's target, every call the
  DLL retargets or relies on is a `call rel32` to the function it expects, every layout constant
  appears as an operand where the game uses it, theGameState's vtable holds MakeGameStatePath / Load /
  Save at the slots the DLL uses, DrawItem's jump table sends the male and female outfit to the cases
  that read +468h and +46Ch, SwapSlots and GetOutfit have no caller but the two each the DLL retargets,
  and every derived address equals the core's;
* build_model(core): the wildcard masks (relocated 32-bit fields, call/jmp rel32 displacements and the
  leading bytes another companion DLL may hook) and every derivation;
* resolve(exe, model): the algorithm the DLL runs, in Python, on any executable;
* render_header(model): the C header, a pure function of b200_outfits_sites and the core executable.
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))
import b200_outfits_sites as S  # noqa: E402

HEADER = RUNTIME / "native" / "b200outfits" / "b200outfits_sites.h"
IMAGE_SCN_MEM_EXECUTE = 0x20000000


class SiteError(RuntimeError):
    pass


def _md() -> Cs:
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    return md


class Exe:
    """A B200 executable file: sections (VA, data, flags) at the link-time base."""

    def __init__(self, data: bytes):
        self.data = data
        self.pe = pefile.PE(data=data, fast_load=True)
        self.pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_BASERELOC"]])
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.sections = []
        for s in self.pe.sections:
            raw = s.get_data()[:s.SizeOfRawData]
            self.sections.append((s.Name.rstrip(b"\0").decode(), self.base + s.VirtualAddress, raw,
                                  s.Characteristics, s.Misc_VirtualSize))
        self.relocs = set()
        for block in getattr(self.pe, "DIRECTORY_ENTRY_BASERELOC", []):
            for e in block.entries:
                if e.type == pefile.RELOCATION_TYPE["IMAGE_REL_BASED_HIGHLOW"]:
                    self.relocs.add(self.base + e.rva)

    def read(self, va: int, n: int) -> bytes:
        for _name, sva, raw, _ch, _vs in self.sections:
            if sva <= va and va + n <= sva + len(raw):
                return raw[va - sva: va - sva + n]
        raise SiteError(f"{va:#x}+{n:#x} is not backed by file data")

    def executable(self):
        return [s for s in self.sections if s[3] & IMAGE_SCN_MEM_EXECUTE]

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.read(va, 4))[0]


def pin_mask(pin, exe: Exe) -> bytes:
    """1 = wildcard: a relocated 32-bit field, the displacement of a call/jmp/jcc rel32, or one of the
    pin's leading `skip` bytes (an entry another companion DLL may have hooked)."""
    m = bytearray(len(pin.bytes))
    for va in exe.relocs:
        if pin.va <= va and va + 4 <= pin.va + len(pin.bytes):
            for k in range(4):
                m[va - pin.va + k] = 1
    for i in _md().disasm(pin.bytes, pin.va):
        if (i.mnemonic in ("call", "jmp") or i.mnemonic.startswith("j")) and i.operands \
                and i.operands[0].type == X86_OP_IMM and i.size >= 5:
            o = i.address - pin.va + i.size - 4
            for k in range(4):
                m[o + k] = 1
    for k in range(pin.skip):
        m[k] = 1
    return bytes(m)


def find_all(sections, pin_bytes: bytes, mask: bytes) -> list[int]:
    rx = re.compile(b"".join(b"." if w else re.escape(bytes([b])) for b, w in zip(pin_bytes, mask)), re.DOTALL)
    hits = []
    for _name, va, raw, _ch, _vs in sections:
        for m in rx.finditer(raw):
            hits.append(va + m.start())
    return hits


def call_target(exe: Exe, va: int) -> int:
    raw = exe.read(va, 5)
    if raw[0] != 0xE8:
        raise SiteError(f"{va:#x} is not a call rel32")
    return (va + 5 + struct.unpack("<i", raw[1:])[0]) & 0xFFFFFFFF


def calls_to(exe: Exe, target: int) -> list[int]:
    """Every E8 rel32 in the code whose target is `target`."""
    out = []
    for _name, va, raw, _ch, _vs in exe.executable():
        for k in range(len(raw) - 4):
            if raw[k] == 0xE8 and (va + k + 5 + struct.unpack_from("<i", raw, k + 1)[0]) & 0xFFFFFFFF == target:
                out.append(va + k)
    return out


class Model:
    def __init__(self):
        self.pins = []        # dicts: name, bytes, mask, parent (-1 searched), offset, va
        self.sites = list(S.ADDRESS_CONSTANTS)
        self.evidence = []    # (site, kind 'L' or 'A', pin, offset)
        self.calls = []       # (pin, offset, function site): checked calls (the hooked ones included)
        self.call_hooks = []  # (site of the call, function site)


def _pin_index(name: str) -> int:
    for i, p in enumerate(S.PINS):
        if p.name == name:
            return i
    raise SiteError(f"no pin {name}")


def build_model(core: Exe) -> Model:
    m = Model()
    for p in S.PINS:
        mask = pin_mask(p, core)
        if p.how == S.SEARCH:
            parent, off = -1, 0
        else:
            kind, parent_name, off = p.how
            if kind != "call":
                raise SiteError(f"{p.name}: unknown locator {p.how}")
            parent = _pin_index(parent_name)
        m.pins.append({"name": p.name, "bytes": p.bytes, "mask": mask, "parent": parent, "offset": off,
                       "va": p.va})
    for si, name in enumerate(m.sites):
        if name in S.FUNCTIONS:
            m.evidence.append((si, "L", _pin_index(S.FUNCTIONS[name]), 0))
        elif name in S.GLOBALS:
            pin, off = S.GLOBALS[name]
            m.evidence.append((si, "A", _pin_index(pin), off))
            for pin2, off2 in S.GLOBAL_ALSO.get(name, ()):
                m.evidence.append((si, "A", _pin_index(pin2), off2))
        else:
            pin, off, _func = S.CALL_HOOKS[name]
            m.evidence.append((si, "L", _pin_index(pin), off))
    for name, (pin, off, func) in S.CALL_HOOKS.items():
        m.calls.append((_pin_index(pin), off, m.sites.index(func)))
        m.call_hooks.append((m.sites.index(name), m.sites.index(func)))
    for pin, off, func in S.CALLS:
        m.calls.append((_pin_index(pin), off, m.sites.index(func)))
    return m


def locate(exe: Exe, model: Model) -> list[int]:
    code = exe.executable()
    loc = [None] * len(model.pins)
    pending = list(range(len(model.pins)))
    while pending:
        progress = False
        for i in list(pending):
            e = model.pins[i]
            if e["parent"] < 0:
                hits = find_all(code, e["bytes"], e["mask"])
                if len(hits) != 1:
                    raise SiteError(f"{e['name']}: found {len(hits)} times")
                loc[i] = hits[0]
            else:
                if loc[e["parent"]] is None:
                    continue
                loc[i] = call_target(exe, loc[e["parent"]] + e["offset"])
                live = exe.read(loc[i], len(e["bytes"]))
                if any(not w and a != b for a, b, w in zip(live, e["bytes"], e["mask"])):
                    raise SiteError(f"{e['name']}: the call target's bytes differ")
            pending.remove(i)
            progress = True
        if not progress:
            raise SiteError("a pin's locator never resolves")
    return loc


def draw_case(exe: Exe, value: dict, item: int) -> int:
    """The address DrawItem's switch jumps to for `item`."""
    index = exe.read(value["DRAW_CASE_BYTES"] + item - S.DRAW_FIRST_CASE, 1)[0]
    return exe.u32(value["DRAW_CASE_TABLE"] + 4 * index)


def resolve(exe: Exe, model: Model) -> dict[str, int]:
    """The DLL's algorithm. Returns {constant: VA in this executable}."""
    loc = locate(exe, model)
    value = {}
    for si, kind, pi, off in model.evidence:
        v = loc[pi] + off if kind == "L" else exe.u32(loc[pi] + off)
        name = model.sites[si]
        if value.setdefault(name, v) != v:
            raise SiteError(f"{name}: derivations disagree ({value[name]:#x} vs {v:#x})")
    for pi, off, func in model.calls:
        target = call_target(exe, loc[pi] + off)
        if target != value[model.sites[func]]:
            raise SiteError(f"{model.pins[pi]['name']}+{off:#x}: not a call to {model.sites[func]}")
    vt = value["GS_VTABLE"]
    if exe.u32(vt + S.GS_LOAD_VSLOT) != value["GS_LOAD"]:
        raise SiteError("theGameState's vtable does not hold Load at slot 13")
    if exe.u32(vt + S.GS_SAVE_VSLOT) != value["GS_SAVE"]:
        raise SiteError("theGameState's vtable does not hold Save at slot 14")
    if not value["INV_DRAW_ITEM"] < value["INV_DRAW_OUTFITS"] < value["INV_DRAW_ITEM"] + 0x100:
        raise SiteError("the outfit cases are not inside DrawItem")
    if not value["INV_TAKE_ONE"] < value["INV_TAKE_OUTFIT"] < value["INV_TAKE_ONE"] + 0x200:
        raise SiteError("the outfit tail is not inside TakeOne")
    if draw_case(exe, value, S.MALE_OUTFIT) != value["INV_DRAW_OUTFITS"] + S.DRAW_CASE_MALE:
        raise SiteError("DrawItem does not draw the male outfit with +468h")
    if draw_case(exe, value, S.FEMALE_OUTFIT) != value["INV_DRAW_OUTFITS"] + S.DRAW_CASE_FEMALE:
        raise SiteError("DrawItem does not draw the female outfit with +46Ch")
    for func, hooks in S.ONLY_CALLERS.items():
        if sorted(calls_to(exe, value[func])) != sorted(value[h] for h in hooks):
            raise SiteError(f"{func} has a caller the DLL does not hook")
    return value


def _operands(pin) -> set[int]:
    values = set()
    for i in _md().disasm(pin.bytes, pin.va):
        for op in i.operands:
            if op.type == X86_OP_IMM and i.mnemonic not in ("call", "jmp") and not i.mnemonic.startswith("j"):
                values.add(op.imm & 0xFFFFFFFF)
            elif op.type == X86_OP_MEM:
                values.add(op.mem.disp & 0xFFFFFFFF)
    return values


def _cross_checks():
    """pin -> operands (immediates or displacements) that must appear in it."""
    neg = lambda v: (-v) & 0xFFFFFFFF  # noqa: E731
    bind = {S.INV_BIND_FIRST + 4 * k for k in range(S.INV_BIND_COUNT)}
    return {
        "st_buy": {S.TRAY_ITEM_LIMIT, S.STORE_SCENE_ITEM, S.MALE_OUTFIT, S.FEMALE_OUTFIT, neg(S.STORE_MALE_FIRST),
                   S.STORE_MALE_LAST - S.STORE_MALE_FIRST, S.STORE_FEMALE_FIRST, S.STORE_FEMALE_LAST},
        "tt_add_item": {4},
        "tt_available": {S.TRAY_COUNT, S.TRAY_FIRST_FREE, 0xFFFFFFFF},
        "tt_draw": {S.TRAY_COUNT, S.TRAY_HEIGHT, S.TRAY_LEFT, S.TRAY_TOP, S.TRAY_HELD, S.TRAY_IN_HAND,
                    S.TRAY_DRAW_OFFSET},
        "tt_draw_in_hand": {S.TRAY_HELD, S.TRAY_IN_USE, 0xFFFFFFFF},
        "inv_draw_item": {neg(S.DRAW_FIRST_CASE), 0x38},
        "inv_draw_outfits": {S.INV_STORE_PICTURES, S.INV_MALE_PICTURE, S.INV_FEMALE_PICTURE, 0xFFFFFFFF},
        "inv_get_outfit": {S.MALE_OUTFIT, S.FEMALE_OUTFIT, S.INV_MALE_PICTURE, S.INV_FEMALE_PICTURE},
        "tt_swap": {S.TRAY_FIRST_FREE, 0xFFFFFFFF, 4},
        "tt_mouse_down": {S.TRAY_IN_HAND, S.TRAY_HELD, S.TRAY_IN_USE},
        "tt_mouse_up": {S.TRAY_IN_HAND, S.TRAY_HELD, S.TRAY_IN_USE},
        "ms_apply": {S.MALE_OUTFIT, S.FEMALE_OUTFIT, S.VILLAGER_GENDER, S.VILLAGER_BODY},
        "tt_use_tool": {S.TRAY_HELD, S.TRAY_IN_USE, S.TRAY_IN_HAND, 4},
        "inv_take_outfit": {S.INV_STORE_PICTURES, S.INV_MALE_PICTURE, S.INV_FEMALE_PICTURE,
                            neg(S.STORE_MALE_FIRST), neg(S.STORE_FEMALE_FIRST), 2},
        "tt_load_state": {S.TRAY_ITEM_LIMIT, S.TRAY_PLACES, S.TRAY_PLACE_SIZE, 4},
        "tt_save_state": {S.TRAY_SAVE_SIZE - 4},
        "inv_load_state": bind,
        "inv_save_state": bind,
        "gs_load": {0x90, 0x25B18},
        "gs_save": {0x90},
    }


def validate(exe_bytes: bytes) -> Model:
    """Prove the core variant; returns the model."""
    core = Exe(exe_bytes)
    if core.base != S.IMAGE_BASE:
        raise SiteError(f"image base {core.base:#x} is not {S.IMAGE_BASE:#x}")
    if not core.relocs:
        raise SiteError("the B200 image has no relocations: the ASLR handling would be untested")
    names = set()
    for pin in S.PINS:
        if pin.name in names:
            raise SiteError(f"duplicate pin {pin.name}")
        names.add(pin.name)
        if core.read(pin.va, len(pin.bytes)) != pin.bytes:
            raise SiteError(f"{pin.name} at {pin.va:#x}: the executable's bytes differ from the pinned bytes")
        insns = list(_md().disasm(pin.bytes, pin.va))
        if sum(i.size for i in insns) != len(pin.bytes):
            raise SiteError(f"{pin.name}: pinned bytes are not whole instructions")
    by_name = {p.name: p for p in S.PINS}
    for name, values in _cross_checks().items():
        got = _operands(by_name[name])
        for want in values:
            if (want & 0xFFFFFFFF) not in got:
                raise SiteError(f"{name}: no operand {want:#x}")
    model = build_model(core)
    for e in model.pins:
        if e["parent"] < 0:
            if sum(1 for w in e["mask"] if not w) < 16:
                raise SiteError(f"{e['name']}: too few fixed bytes to search for")
            hits = find_all(core.executable(), e["bytes"], e["mask"])
            if hits != [e["va"]]:
                raise SiteError(f"{e['name']}: found at {[hex(h) for h in hits]}")
        else:
            parent = model.pins[e["parent"]]
            if call_target(core, parent["va"] + e["offset"]) != e["va"]:
                raise SiteError(f"{e['name']}: not the target of the call at {parent['name']}+{e['offset']:#x}")
    # every retargeted call is a whole `call rel32` instruction of its pin
    for name, (pin, off, _func) in S.CALL_HOOKS.items():
        p = by_name[pin]
        starts = {i.address - p.va: i for i in _md().disasm(p.bytes, p.va)}
        if off not in starts or starts[off].mnemonic != "call" or starts[off].size != 5 or p.bytes[off] != 0xE8:
            raise SiteError(f"{name}: {pin}+{off:#x} is not a call rel32 instruction")
    got = resolve(core, model)
    for name in S.FUNCTIONS:
        if got[name] != by_name[S.FUNCTIONS[name]].va:
            raise SiteError(f"{name}: derived {got[name]:#x}")
    for name in S.GLOBALS:
        if got[name] != S.CORE_VALUES[name]:
            raise SiteError(f"{name}: derived {got[name]:#x}, expected {S.CORE_VALUES[name]:#x}")
    if core.u32(got["GS_VTABLE"] + S.LDW_PATH_VSLOT) != S.CORE_MAKE_GAME_STATE_PATH:
        raise SiteError("theGameState's vtable +0Ch is not MakeGameStatePath")
    return model


def validate_variant(exe_bytes: bytes, model: Model) -> dict[str, int]:
    """Prove another executable: every pin located, every derivation agrees."""
    return resolve(Exe(exe_bytes), model)


# ---------------------------------------------------------------- header
def render_header(model: Model) -> str:
    def arr(b: bytes) -> str:
        return ", ".join(f"0x{x:02X}" for x in b)

    out = [
        "// GENERATED by runtime/tools/gen_b200_outfits_sites.py from runtime/b200_outfits_sites.py.",
        "// Do not edit. The DLL holds no game address: it searches the live executable for each pinned",
        "// run (mask 1 = wildcard: a relocated field, a call/jmp displacement, or the leading bytes of an",
        "// entry another companion DLL may have hooked), finds the pins marked with a parent as the target",
        "// of the call at that offset of the parent, and derives every address from where the runs were",
        "// found. It installs nothing unless every pin is found exactly once, every derivation agrees and",
        "// every call it relies on calls what the core variant calls.",
        "#pragma once",
        "",
        "struct OutfPin {",
        "    const char *name; unsigned len; const unsigned char *bytes; const unsigned char *mask;",
        "    int parent;           // -1: searched for; else the pin whose call at call_offset targets it",
        "    unsigned call_offset; // offset of that E8 byte in the parent",
        "};",
        "struct OutfEvidence { unsigned char site; char kind; unsigned char pin; unsigned offset; };",
        "struct OutfCall { unsigned char pin; unsigned offset; unsigned char function; };",
        "struct OutfCallHook { unsigned char site; unsigned char function; };",
        "",
    ]
    skip = set(S.CORE_ONLY_CONSTANTS)
    for key in sorted(vars(S)):
        value = getattr(S, key)
        if key.isupper() and isinstance(value, int) and not isinstance(value, bool) and key not in skip:
            out.append(f"#define OUTF_{key} 0x{value:X}u")
    out.append("")
    out.append("enum OutfSite {")
    for name in model.sites:
        out.append(f"    OUTF_SITE_{name},")
    out.append("    OUTF_SITE_COUNT")
    out.append("};")
    out.append("")
    for e in model.pins:
        out.append(f"static const unsigned char opin_{e['name']}[] = {{ {arr(e['bytes'])} }};")
        out.append(f"static const unsigned char omask_{e['name']}[] = {{ {arr(e['mask'])} }};")
    out.append("")
    out.append("static const OutfPin OUTF_PINS[] = {")
    for e in model.pins:
        out.append(f'    {{ "{e["name"]}", {len(e["bytes"])}u, opin_{e["name"]}, omask_{e["name"]}, '
                   f'{e["parent"]}, 0x{e["offset"]:X}u }},')
    out.append("};")
    out.append("")
    out.append("static const OutfEvidence OUTF_EVIDENCE[] = {")
    for si, kind, pi, off in model.evidence:
        out.append(f"    {{ OUTF_SITE_{model.sites[si]}, '{kind}', {pi}, 0x{off:X}u }},")
    out.append("};")
    out.append("static const OutfCall OUTF_CALLS[] = {")
    for pi, off, func in model.calls:
        out.append(f"    {{ {pi}, 0x{off:X}u, OUTF_SITE_{model.sites[func]} }},")
    out.append("};")
    out.append("static const OutfCallHook OUTF_CALL_HOOKS[] = {")
    for si, func in model.call_hooks:
        out.append(f"    {{ OUTF_SITE_{model.sites[si]}, OUTF_SITE_{model.sites[func]} }},")
    out.append("};")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b200", required=True, help="path to the CORE variant's Virtual Families 2 - B200.exe")
    ap.add_argument("--also", action="append", default=[], help="another executable to prove")
    ap.add_argument("--write", action="store_true", help="rewrite the committed header")
    args = ap.parse_args(argv)
    model = validate(Path(args.b200).read_bytes())
    for other in args.also:
        validate_variant(Path(other).read_bytes(), model)
    text = render_header(model)
    if args.write:
        HEADER.parent.mkdir(parents=True, exist_ok=True)
        HEADER.write_text(text, newline="\n")
        print(f"wrote {HEADER}")
    elif not HEADER.is_file() or HEADER.read_text() != text:
        print("the committed header differs from a fresh render")
        return 1
    print(f"{len(S.PINS)} pins proved on the core variant, {len(args.also)} other executables resolved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
