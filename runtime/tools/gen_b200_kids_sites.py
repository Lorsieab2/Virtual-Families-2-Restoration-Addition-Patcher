#!/usr/bin/env python3
"""Prove the Up to 28 Children sites against the B200 executables and emit the companion DLL's header.

    gen_b200_kids_sites.py --b200 "<core>\\Virtual Families 2 - B200.exe" [--write]
        [--also "<other variant or later build>.exe" ...]

The B200 image is relocated and every matrix variant links to different addresses, so the DLL holds
no address. This tool

* validate(core): reads the CORE variant with pefile and decodes every pin with capstone. It refuses
  (SiteError) unless every pin is the pinned bytes and whole instructions, every pin the DLL searches
  for is found exactly once, every pin found through a call is that call's target, every call the
  DLL relies on is a `call rel32` to the function it expects, every hooked entry's stolen bytes are
  whole position-independent instructions, every layout constant appears as an operand where the
  game uses it, and every derived address equals the core variant's;
* build_model(core): the wildcard masks (relocated 32-bit fields and call/jmp rel32 displacements)
  and every derivation;
* resolve(exe, model): the algorithm the DLL runs, in Python, on any executable;
* render_header(model): the C header, a pure function of b200_kids_sites and the core executable.
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
import b200_kids_sites as S  # noqa: E402

HEADER = RUNTIME / "native" / "b200kids" / "b200kids_sites.h"
IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_SCN_MEM_WRITE = 0x80000000
IMAGE_SCN_MEM_READ = 0x40000000


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

    def section(self, name: str):
        hits = [s for s in self.sections if s[0] == name]
        return hits[0] if len(hits) == 1 else None

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.read(va, 4))[0]


def pin_mask(pin, exe: Exe) -> bytes:
    """1 = wildcard: a relocated 32-bit field, or the displacement of a call/jmp/jcc rel32."""
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


class Model:
    def __init__(self):
        self.pins = []        # dicts: name, bytes, mask, parent (-1 searched), call_offset
        self.sites = list(S.ADDRESS_CONSTANTS)
        self.evidence = []    # (site, kind 'L' or 'A', pin, offset)
        self.calls = []       # (pin, offset, function site or -1)
        self.hooks = []       # (site, replace?, steal)


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
        else:
            pin, off = S.GLOBALS[name]
            m.evidence.append((si, "A", _pin_index(pin), off))
            for pin2, off2 in S.GLOBAL_ALSO.get(name, ()):
                m.evidence.append((si, "A", _pin_index(pin2), off2))
    for pin, off, func in S.CALLS:
        m.calls.append((_pin_index(pin), off, m.sites.index(func) if func else -1))
    for name, (kind, steal) in S.HOOKS.items():
        m.hooks.append((m.sites.index(name), kind == "replace", steal))
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
        if func >= 0 and target != value[model.sites[func]]:
            raise SiteError(f"{model.pins[pi]['name']}+{off:#x}: not a call to {model.sites[func]}")
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
    return {
        "ft_add_offspring": {S.FAMILY_RECORD_SIZE, S.PEEP_RECORD_SIZE, 6, neg(0x50C), neg(0x508),
                             S.VILLAGER_NAME, S.VILLAGER_GENDER, S.VILLAGER_HEAD, S.VILLAGER_BODY,
                             S.VILLAGER_SLOT, S.PEEP_VALID, S.PEEP_GENDER, S.PEEP_SLOT, 0x19},
        "ft_empty_offspring": {6, S.FAMILY_RECORD_SIZE, neg(0x50C)},
        "ft_get_current_family": {S.FAMILY_RECORD_SIZE, neg(S.FAMILY_RECORD_BASE)},
        "ft_count_surviving": {S.FAMILY_RECORD_SIZE, neg(0x50C), neg(0x4E0), S.VILLAGER_ACTIVE,
                               S.PEEP_RECORD_SIZE},
        "ft_report_death": {S.VILLAGER_SLOT, neg(0x4E0), neg(0x50C), 0xFFFFFFFF, S.TREE_GENERATIONS},
        "ft_reset": {0xCB70},
        "ft_start_next_gen": {S.TREE_GENERATIONS, S.TREE_GENERATIONS - 1, S.FAMILY_RECORD_SIZE},
        "ad_activate": {S.ADOPTION_MODE, S.ADOPTION_CANDIDATE},
        "ad_create_candidates": {S.ADOPTION_COUNT, S.ADOPTION_CURSOR, S.RECORD_CHILD_COUNT,
                                 S.RECORD_CHILDREN + S.PEEP_SLOT, S.ADOPTION_CLONES, S.ADOPTION_SOURCES,
                                 S.VILLAGER_SLOT, S.VILLAGER_ACTIVE, S.PEEP_RECORD_SIZE},
        "ad_generate": {S.ADOPTION_MODE, S.ADOPTION_CANDIDATE, S.VILLAGER_ACTIVE},
        "ad_get_next": {S.ADOPTION_COUNT, S.ADOPTION_CURSOR, S.ADOPTION_CLONES},
        "ad_handle_message": {S.ADOPTION_MODE, S.ADOPTION_CANDIDATE, S.ADOPTION_CURSOR, S.ADOPTION_SOURCES,
                              S.HOUSEHOLD_SLOTS, S.VILLAGER_ACTIVE, S.VILLAGER_SLOT},
        "vm_find_empty": {S.VILLAGER_ARRAY_OFFSET + S.VILLAGER_ACTIVE, S.GAME_STATE_RESERVED_BABY,
                          S.GAME_STATE_RESERVED_BABY + 4, S.GAME_STATE_RESERVED_BABY + 8, S.HOUSEHOLD_SLOTS,
                          S.VILLAGER_STRIDE},
        "vm_get_villager": {S.VILLAGER_STRIDE, S.VILLAGER_ARRAY_OFFSET, S.HOUSEHOLD_SLOTS},
        "vm_clone_peep": {S.VILLAGER_STRIDE, S.VILLAGER_ARRAY_OFFSET},
        "v_clone_as_adult": {S.VILLAGER_ACTIVE, S.VILLAGER_AGE},
        "v_impregnate": {1, 2, 3, 0x6B1C},
        "gs_save": {0x90, 0x25B18},
        "gs_load": {0x90, 0x25B18},
        "gs_get": {S.GAME_STATE_INSTANCE},
        "ldw_save": {S.SAVE_BACKUP_OFFSET, S.LDW_PATH_VSLOT},
        "ldw_make_path": {0x14},
    }


def _writes(pin, disp: int) -> bool:
    """Does any instruction of the pin store to [reg + disp]?"""
    for i in _md().disasm(pin.bytes, pin.va):
        if not i.operands:
            continue
        dst = i.operands[0]
        if dst.type == X86_OP_MEM and (dst.mem.disp & 0xFFFFFFFF) == disp and i.mnemonic.startswith("mov"):
            return True
    return False


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
    # CloneAsAdult never writes the slot index: cloning a buffer into a slot keeps that slot's index.
    if _writes(by_name["v_clone_as_adult"], S.VILLAGER_SLOT):
        raise SiteError("CloneAsAdult writes the slot index")
    # MakeGameStatePath's format string.
    fmt_va = None
    for i in _md().disasm(by_name["ldw_make_path"].bytes, by_name["ldw_make_path"].va):
        if i.mnemonic == "push" and i.operands[0].type == X86_OP_IMM and i.address + 1 in core.relocs:
            fmt_va = i.operands[0].imm
    if fmt_va is None or core.read(fmt_va, 9) != b"%s%d.ldw\0":
        raise SiteError("MakeGameStatePath does not format \"%s%d.ldw\"")
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
    for si, replace, steal in model.hooks:
        name = model.sites[si]
        pin = by_name[S.FUNCTIONS[name]]
        if steal < 5 or steal > 16:
            raise SiteError(f"{name}: stolen length {steal} out of range")
        size = 0
        for i in _md().disasm(pin.bytes[:steal], pin.va):
            if i.mnemonic.startswith("j") or i.mnemonic in ("call", "ret", "loop"):
                raise SiteError(f"{name}: a branch in the stolen bytes")
            for op in i.operands:
                if op.type == X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                    raise SiteError(f"{name}: an absolute memory operand in the stolen bytes")
            size += i.size
        if size != steal:
            raise SiteError(f"{name}: the first {steal} bytes are not whole instructions")
        if any(pin.va + k in core.relocs for k in range(steal)):
            raise SiteError(f"{name}: a relocated field in the stolen bytes")
        # Only the first 5 bytes are overwritten; nothing may branch into the rest of the stolen run.
        for i in _md().disasm(pin.bytes, pin.va):
            if (i.mnemonic.startswith("j") or i.mnemonic == "loop") and i.operands \
                    and i.operands[0].type == X86_OP_IMM and pin.va < i.operands[0].imm < pin.va + steal:
                raise SiteError(f"{name}: a branch into the stolen bytes at {i.address:#x}")
    got = resolve(core, model)
    for name in S.FUNCTIONS:
        if got[name] != by_name[S.FUNCTIONS[name]].va:
            raise SiteError(f"{name}: derived {got[name]:#x}")
    for name in S.GLOBALS:
        if got[name] != getattr(S, name):
            raise SiteError(f"{name}: derived {got[name]:#x}, expected {getattr(S, name):#x}")
    if got["GS_GET"] != S.GAME_STATE_GET or got["GAME_STATE_INSTANCE"] != S.GAME_STATE_INSTANCE:
        raise SiteError("HandleMessage does not call theGameState::Get")
    return model


def validate_variant(exe_bytes: bytes, model: Model) -> dict[str, int]:
    """Prove another executable: every pin located, every derivation agrees."""
    return resolve(Exe(exe_bytes), model)


# ---------------------------------------------------------------- header
def render_header(model: Model) -> str:
    def arr(b: bytes) -> str:
        return ", ".join(f"0x{x:02X}" for x in b)

    out = [
        "// GENERATED by runtime/tools/gen_b200_kids_sites.py from runtime/b200_kids_sites.py.",
        "// Do not edit. The DLL holds no game address: it searches the live executable for each pinned",
        "// run (mask 1 = wildcard: a relocated field or a call/jmp displacement), finds the pins marked",
        "// with a parent as the target of the call at that offset of the parent, and derives every",
        "// address from where the runs were found. It installs nothing unless every pin is found exactly",
        "// once, every derivation agrees and every call it relies on calls what the core variant calls.",
        "#pragma once",
        "",
        "struct KidsPin {",
        "    const char *name; unsigned len; const unsigned char *bytes; const unsigned char *mask;",
        "    int parent;           // -1: searched for; else the pin whose call at call_offset targets it",
        "    unsigned call_offset; // offset of that E8 byte in the parent",
        "};",
        "struct KidsEvidence { unsigned char site; char kind; unsigned char pin; unsigned offset; };",
        "struct KidsCall { unsigned char pin; unsigned offset; int function; };",
        "struct KidsHook { unsigned char site; unsigned char replace; unsigned char steal; };",
        "",
    ]
    skip = set(S.CORE_ONLY_CONSTANTS)
    for key in sorted(vars(S)):
        value = getattr(S, key)
        if key.isupper() and isinstance(value, int) and not isinstance(value, bool) and key not in skip:
            out.append(f"#define KIDS_{key} 0x{value:X}u")
    out.append("")
    out.append("enum KidsSite {")
    for name in model.sites:
        out.append(f"    KIDS_SITE_{name},")
    out.append("    KIDS_SITE_COUNT")
    out.append("};")
    out.append("")
    for e in model.pins:
        out.append(f"static const unsigned char kpin_{e['name']}[] = {{ {arr(e['bytes'])} }};")
        out.append(f"static const unsigned char kmask_{e['name']}[] = {{ {arr(e['mask'])} }};")
    out.append("")
    out.append("static const KidsPin KIDS_PINS[] = {")
    for e in model.pins:
        out.append(f'    {{ "{e["name"]}", {len(e["bytes"])}u, kpin_{e["name"]}, kmask_{e["name"]}, '
                   f'{e["parent"]}, 0x{e["offset"]:X}u }},')
    out.append("};")
    out.append("")
    out.append("static const KidsEvidence KIDS_EVIDENCE[] = {")
    for si, kind, pi, off in model.evidence:
        out.append(f"    {{ KIDS_SITE_{model.sites[si]}, '{kind}', {pi}, 0x{off:X}u }},")
    out.append("};")
    out.append("static const KidsCall KIDS_CALLS[] = {")
    for pi, off, func in model.calls:
        f = f"KIDS_SITE_{model.sites[func]}" if func >= 0 else "-1"
        out.append(f"    {{ {pi}, 0x{off:X}u, {f} }},")
    out.append("};")
    out.append("static const KidsHook KIDS_HOOKS[] = {")
    for si, replace, steal in model.hooks:
        out.append(f"    {{ KIDS_SITE_{model.sites[si]}, {1 if replace else 0}, {steal} }},")
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
