#!/usr/bin/env python3
"""Prove the R Refreshes the Store sites against the B200 executables and emit the companion DLL's header.

    gen_b200_refresh_sites.py --b200 "<core>\\Virtual Families 2 - B200.exe" [--write] [--also "<other>.exe" ...]

The B200 image is relocated and each of the 32 matrix variants links to different addresses, so the DLL
holds no address. This tool

* validate(core): reads the CORE variant with pefile and decodes every pin with capstone, refusing
  (SiteError) unless the bytes are the pinned bytes and whole instructions, the cross-checks hold (the
  category field, the forced-draw argument, the outfit fields and the 4-hour delay, the jump-table entry of
  the Clothing page, the RTTI chain of the store's vtable and the slot the DLL replaces), and every address
  constant has evidence in the pins;
* build_model(core): the wildcard masks, which pins are searched for and which hang off an anchor pin, and
  every derivation of each address constant;
* resolve(exe, model): the DLL's algorithm in Python, including the RTTI search for the store's vtable;
* render_header(): the C header, a pure function of b200_refresh_sites and the core executable.
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
import b200_refresh_sites as S  # noqa: E402

HEADER = RUNTIME / "native" / "b200refresh" / "b200refresh_sites.h"
IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_SCN_MEM_WRITE = 0x80000000
IMAGE_SCN_MEM_READ = 0x40000000
MIN_INFORMATIVE = 16
MAX_ANCHOR_DISTANCE = 0x400


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
                                  s.Characteristics, max(s.Misc_VirtualSize, s.SizeOfRawData)))
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

    def read_only_data(self):
        return [s for s in self.sections
                if not s[3] & (IMAGE_SCN_MEM_EXECUTE | IMAGE_SCN_MEM_WRITE) and s[3] & IMAGE_SCN_MEM_READ]

    def data_sections(self):
        """Every readable section that is not code (the type descriptor's name lives in .data)."""
        return [s for s in self.sections if not s[3] & IMAGE_SCN_MEM_EXECUTE and s[3] & IMAGE_SCN_MEM_READ]

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


def _regex(pin_bytes: bytes, mask: bytes):
    out = b""
    for b, w in zip(pin_bytes, mask):
        out += b"." if w else re.escape(bytes([b]))
    return re.compile(out, re.DOTALL)


def find_all(sections, pin_bytes: bytes, mask: bytes) -> list[int]:
    rx = _regex(pin_bytes, mask)
    hits = []
    for _name, va, raw, _ch, _vs in sections:
        for m in rx.finditer(raw):
            hits.append(va + m.start())
    return hits


def _calls(pin) -> list[tuple[int, int]]:
    """(offset of the rel32 field, target) of every call/jmp rel32 in a pin."""
    out = []
    for i in _md().disasm(pin.bytes, pin.va):
        if i.mnemonic in ("call", "jmp") and i.size == 5 and i.operands and i.operands[0].type == X86_OP_IMM:
            out.append((i.address - pin.va + 1, i.operands[0].imm))
    return out


class Model:
    def __init__(self):
        self.pins = []          # dicts: name, bytes, mask, parent, offset, va, dll
        self.sites = []         # ADDRESS_CONSTANTS, then TEST_ADDRESS_CONSTANTS
        self.dll_sites = 0
        self.evidence = []      # (site index, kind, pin index, offset); kind L location, A abs field, C call target


def build_model(core: Exe) -> Model:
    m = Model()
    pins = list(S.PINS)
    masks = {p.name: pin_mask(p, core) for p in pins}
    searched = set()
    for p in pins:
        informative = len(p.bytes) - sum(masks[p.name])
        if informative >= MIN_INFORMATIVE and find_all(core.executable(), p.bytes, masks[p.name]) == [p.va]:
            searched.add(p.name)
    for p in pins:
        m.pins.append({"name": p.name, "bytes": p.bytes, "mask": masks[p.name], "parent": -1, "offset": 0,
                       "va": p.va, "dll": p.dll})
    index = {e["name"]: i for i, e in enumerate(m.pins)}
    by_name = {p.name: p for p in pins}
    unanchored = []
    for e in m.pins:
        if e["name"] in searched:
            continue
        # a DLL pin may only hang off another DLL pin (the header holds no test pin)
        cands = [by_name[n] for n in searched if by_name[n].dll or not e["dll"]]
        best = None
        for q in cands:
            d = e["va"] - q.va
            if -MAX_ANCHOR_DISTANCE <= d <= MAX_ANCHOR_DISTANCE + len(q.bytes) \
                    and (best is None or abs(d) < abs(e["va"] - best.va)):
                best = q
        if best is None:
            unanchored.append(e["name"])
            continue
        e["parent"] = index[best.name]
        e["offset"] = e["va"] - best.va
    if unanchored:
        raise SiteError("not unique and no anchor pin lies near: " + ", ".join(unanchored))
    # The DLL's pins come first so the header's pin indices are the model's.
    order = sorted(range(len(m.pins)), key=lambda i: (not m.pins[i]["dll"], i))
    remap = {old: new for new, old in enumerate(order)}
    m.pins = [m.pins[i] for i in order]
    for e in m.pins:
        if e["parent"] >= 0:
            e["parent"] = remap[e["parent"]]
    pins = [by_name[e["name"]] for e in m.pins]
    m.sites = list(S.ADDRESS_CONSTANTS) + list(S.TEST_ADDRESS_CONSTANTS)
    m.dll_sites = len(S.ADDRESS_CONSTANTS)
    for si, name in enumerate(m.sites):
        value = getattr(S, name)
        found = False
        for pi, p in enumerate(pins):
            if si < m.dll_sites and not p.dll:
                continue                      # the DLL's sites come from the DLL's pins only
            if p.va <= value < p.va + len(p.bytes):
                m.evidence.append((si, "L", pi, value - p.va))
                found = True
            for va in sorted(core.relocs):
                if p.va <= va and va + 4 <= p.va + len(p.bytes) and core.u32(va) == value:
                    m.evidence.append((si, "A", pi, va - p.va))
                    found = True
            for off, target in _calls(p):
                if target == value:
                    m.evidence.append((si, "C", pi, off))
                    found = True
        if not found:
            raise SiteError(f"{name} ({value:#x}) has no evidence in any pin")
    return m


def locate(exe: Exe, model: Model) -> list[int]:
    code = exe.executable()
    loc = [None] * len(model.pins)
    for i, e in enumerate(model.pins):
        if e["parent"] >= 0:
            continue
        hits = find_all(code, e["bytes"], e["mask"])
        if len(hits) != 1:
            raise SiteError(f"{e['name']}: found {len(hits)} times")
        loc[i] = hits[0]
    for i, e in enumerate(model.pins):
        if e["parent"] < 0:
            continue
        loc[i] = loc[e["parent"]] + e["offset"]
        live = exe.read(loc[i], len(e["bytes"]))
        if any(not w and a != b for a, b, w in zip(live, e["bytes"], e["mask"])):
            raise SiteError(f"{e['name']}: bytes differ at its anchor offset")
    return loc


def store_vtable(exe: Exe) -> int:
    """The DLL's RTTI search: the one type descriptor named .?AVCScrollingStoreScene@@, the one complete
    object locator at offset 0 pointing to it, the one vtable pointing to that locator."""
    name = b".?AV" + S.STORE_CLASS.encode() + b"@@\0"
    hits = []
    for _n, va, raw, _c, _vs in exe.data_sections():
        j = raw.find(name)
        while j >= 0:
            hits.append(va + j)
            j = raw.find(name, j + 1)
    if len(hits) != 1:
        raise SiteError(f"the store's type descriptor name is found {len(hits)} times")
    td = hits[0] - 8
    rodata = exe.read_only_data()
    cols = []
    for _n, va, raw, _c, _vs in rodata:
        for off in range(12, len(raw) - 3, 4):
            if struct.unpack_from("<I", raw, off)[0] == td:
                col = va + off - 12
                if exe.u32(col) == 0 and exe.u32(col + 4) == 0:
                    cols.append(col)
    if len(cols) != 1:
        raise SiteError(f"{len(cols)} complete object locators at offset 0 for the store")
    vts = []
    for _n, va, raw, _c, _vs in rodata:
        for off in range(0, len(raw) - 3, 4):
            if struct.unpack_from("<I", raw, off)[0] == cols[0]:
                vts.append(va + off + 4)
    if len(vts) != 1:
        raise SiteError(f"{len(vts)} vtables point to the store's locator")
    return vts[0]


def resolve(exe: Exe, model: Model) -> dict[str, int]:
    """The DLL's algorithm. Returns {constant: VA in this executable}, plus STORE_SLOT_HANDLE_KEY."""
    loc = locate(exe, model)
    value = {}
    for si, kind, pi, off in model.evidence:
        if kind == "L":
            v = loc[pi] + off
        elif kind == "A":
            v = exe.u32(loc[pi] + off)
        else:
            v = loc[pi] + off + 4 + struct.unpack("<i", exe.read(loc[pi] + off, 4))[0]
        v &= 0xFFFFFFFF
        name = model.sites[si]
        if value.setdefault(name, v) != v:
            raise SiteError(f"{name}: derivations disagree ({value[name]:#x} vs {v:#x})")
    slot = store_vtable(exe) + 4 * S.HANDLE_KEY_VSLOT
    if exe.u32(slot) != value["STORE_HANDLE_KEY"]:
        raise SiteError("the store's HandleKey slot does not point to the pinned HandleKey")
    value["STORE_SLOT_HANDLE_KEY"] = slot
    return value


def _calls_and_immediates(pin):
    calls, values = set(), set()
    for i in _md().disasm(pin.bytes, pin.va):
        if i.mnemonic in ("call", "jmp") and i.operands and i.operands[0].type == X86_OP_IMM:
            calls.add(i.operands[0].imm)
        for op in i.operands:
            if op.type == X86_OP_IMM and i.mnemonic not in ("call", "jmp") and not i.mnemonic.startswith("j"):
                values.add(op.imm & 0xFFFFFFFF)
            elif op.type == X86_OP_MEM:
                values.add(op.mem.disp & 0xFFFFFFFF)
    return calls, values


def _cross_checks():
    """pin name -> (call targets that must appear, operands that must appear)."""
    outfit_fields = set(range(S.OUTFIT_FIRST_FIELD, S.OUTFIT_LAST_FIELD + 4, 4))
    return {
        "store_handle_key": (set(), {S.KEY_TYPE_KEYDOWN, S.KEY_ESC, 8, 1, 0xC}),
        "set_store_category_head": ({S.GET_CATEGORY_ITEM_COUNT}, {S.STORE_CATEGORY_FIELD, S.INVENTORY_MANAGER, 0xD8}),
        "maybe_update_outfits": ({S.GAME_TIME_SECONDS, S.GEN_COMMON_BODY, S.GEN_UNCOMMON_BODY, S.GEN_RARE_BODY},
                                 outfit_fields | {S.OUTFIT_NEXT_PICK_FIELD, S.OUTFIT_REPICK_DELAY, S.GAME_TIME}),
        "gen_body_types": ({S.GET_RANDOM}, {0x20, 6, 0x2C, 0xC}),
        "clothing_count_case": ({S.MAYBE_UPDATE_OUTFITS}, {0}),
        "reset_forced_draw": ({S.MAYBE_UPDATE_OUTFITS}, {1, 0x384}),
        "event_manager_handle_key": (set(), {4 * S.HANDLE_KEY_VSLOT, 2, 0xC}),
        "maybe_update_rotating_items": ({S.GET_RANDOM, S.GET_SECONDS_FROM_GAME_START},
                                        {S.FLEA_NEXT_PICK_FIELD, S.FLEA_COUNT_FIELD, S.FLEA_REPICK_DELAY, 5, 1,
                                         *range(S.FLEA_ROWS_FIELD, S.FLEA_ROWS_FIELD + 20, 4)}),
        "flea_count_case": ({S.MAYBE_UPDATE_ROTATING}, {S.FLEA_COUNT_FIELD}),
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
        if sum(i.size for i in _md().disasm(pin.bytes, pin.va)) != len(pin.bytes):
            raise SiteError(f"{pin.name}: pinned bytes are not whole instructions")
    by_name = {p.name: p for p in S.PINS}
    for name, (calls, values) in _cross_checks().items():
        got_calls, got_values = _calls_and_immediates(by_name[name])
        for want in calls:
            if want not in got_calls:
                raise SiteError(f"{name}: no call/jmp to {want:#x}")
        for want in values:
            if (want & 0xFFFFFFFF) not in got_values:
                raise SiteError(f"{name}: no operand {want:#x}")
    # The Flea Market pick reads its next-pick time into edx (the due test) and stores now + delay there.
    mur = {(i.mnemonic, i.op_str) for i in _md().disasm(by_name["maybe_update_rotating_items"].bytes,
                                                         S.MAYBE_UPDATE_ROTATING)}
    if ("mov", f"edx, dword ptr [ecx + {S.FLEA_NEXT_PICK_FIELD:#x}]") not in mur \
            or ("mov", f"dword ptr [ecx + {S.FLEA_NEXT_PICK_FIELD:#x}], eax") not in mur:
        raise SiteError("MaybeUpdateRotatingItems does not keep its next-pick time at the field the DLL clears")
    # The force flag is the byte argument: cmp byte [ebp+8],0; jne past the clock test.
    muo = by_name["maybe_update_outfits"].bytes
    if muo[3:7] != b"\x80\x7D\x08\x00" or muo[10] != 0x75:
        raise SiteError("MaybeUpdateOutfits does not skip its clock test on a true argument")
    if muo[-3:] != b"\xC2\x04\x00":
        raise SiteError("MaybeUpdateOutfits does not end in ret 4")
    # The pinned HandleKey: type 6 / code 3E8h only, ret 0Ch on both exits.
    hk = list(_md().disasm(by_name["store_handle_key"].bytes, S.STORE_HANDLE_KEY))
    rets = [i for i in hk if i.mnemonic == "ret"]
    if len(rets) != 2 or any(i.op_str != "0xc" for i in rets):
        raise SiteError("the pinned HandleKey does not return with ret 0Ch")
    if hk[2].op_str != "dword ptr [ebp + 8], 6" or hk[4].op_str != "dword ptr [ebp + 0xc], 0x3e8":
        raise SiteError("the pinned HandleKey reads more than type 6 and Esc")
    # SetStoreCategory stores its argument at the category field the DLL reads.
    ssc = list(_md().disasm(by_name["set_store_category_head"].bytes, S.SET_STORE_CATEGORY))
    if not any(i.mnemonic == "mov" and i.op_str == f"dword ptr [esi + {S.STORE_CATEGORY_FIELD:#x}], ebx" for i in ssc):
        raise SiteError("SetStoreCategory does not store the category at the field the DLL reads")
    # GetCategoryItemCount's jump table: entry 0Dh is the clothing case, entry 0Fh is not.
    gcic = core.read(S.GET_CATEGORY_ITEM_COUNT, 0x40)
    j = gcic.find(b"\xFF\x24\x85")
    if j < 0:
        raise SiteError("GetCategoryItemCount has no jump table")
    table = struct.unpack_from("<I", gcic, j + 3)[0]
    if core.u32(table + 4 * S.CLOTHING_CATEGORY) != S.CLOTHING_COUNT_CASE + 10:
        raise SiteError("GetCategoryItemCount's case 0Dh is not the clothing case that calls MaybeUpdateOutfits")
    if core.u32(table + 4 * S.FLEA_MARKET_CATEGORY) != S.FLEA_COUNT_CASE + 10:
        raise SiteError("GetCategoryItemCount's case 0Fh is not the Flea Market case that calls MaybeUpdateRotatingItems")
    if S.CLOTHING_CATEGORY == S.FLEA_MARKET_CATEGORY or S.KEY_R_LOWER != ord("r") or S.KEY_R_UPPER != ord("R"):
        raise SiteError("derived constant wrong: the keys or the pages")
    if S.STORE_SLOT_HANDLE_KEY != S.STORE_VTABLE + 4 * S.HANDLE_KEY_VSLOT:
        raise SiteError("derived constant wrong: the slot is not HandleKey's")
    # The store's vtable, by RTTI, as the DLL finds it; its slot points to the pinned HandleKey and is relocated.
    vt = store_vtable(core)
    if vt != S.STORE_VTABLE:
        raise SiteError(f"the store's vtable is {vt:#x}, not {S.STORE_VTABLE:#x}")
    if core.u32(S.STORE_SLOT_HANDLE_KEY) != S.STORE_HANDLE_KEY or S.STORE_SLOT_HANDLE_KEY not in core.relocs:
        raise SiteError("the store's HandleKey slot is not a relocated pointer to the pinned HandleKey")
    model = build_model(core)
    got = resolve(core, model)
    for name in (*S.ADDRESS_CONSTANTS, *S.TEST_ADDRESS_CONSTANTS, "STORE_SLOT_HANDLE_KEY"):
        if got[name] != getattr(S, name):
            raise SiteError(f"{name}: derived {got[name]:#x}, expected {getattr(S, name):#x}")
    return model


def validate_variant(exe_bytes: bytes, model: Model) -> dict[str, int]:
    return resolve(Exe(exe_bytes), model)


# ---------------------------------------------------------------- header
def render_header(model: Model) -> str:
    def arr(b: bytes) -> str:
        return ", ".join(f"0x{x:02X}" for x in b)

    out = [
        "// GENERATED by runtime/tools/gen_b200_refresh_sites.py from runtime/b200_refresh_sites.py.",
        "// Do not edit. The DLL holds no game address: it searches the live executable for each pinned run",
        "// (mask 1 = wildcard: a relocated field or a call/jmp displacement), derives every address from",
        "// where the runs were found, and finds the store's vtable through its RTTI. It installs nothing",
        "// unless every pin is found once, every derivation agrees and the store's HandleKey slot points to",
        "// the pinned HandleKey.",
        "#pragma once",
        "",
        "struct RfshPin {",
        "    const char *name; unsigned len; const unsigned char *bytes; const unsigned char *mask;",
        "    int parent;       // -1: searched for in the executable sections; else the index of its anchor pin",
        "    int offset;       // signed distance from the anchor pin",
        "};",
        "struct RfshEvidence { unsigned char site; char kind; unsigned short pin; unsigned offset; };",
        "",
    ]
    skip = set(S.ADDRESS_CONSTANTS) | set(S.CORE_ONLY_CONSTANTS)
    for key in sorted(vars(S)):
        value = getattr(S, key)
        if key.isupper() and isinstance(value, int) and not isinstance(value, bool) and key not in skip:
            out.append(f"#define RFSH_{key} 0x{value:X}u")
    out.append(f'#define RFSH_STORE_TYPE_NAME ".?AV{S.STORE_CLASS}@@"')
    out.append(f'#define RFSH_FLEA_FLAG_SECTION "{S.FLEA_FLAG_SECTION}"')
    out.append("")
    out.append("enum RfshSite {")
    for name in model.sites[:model.dll_sites]:
        out.append(f"    RFSH_SITE_{name},")
    out.append("    RFSH_SITE_COUNT")
    out.append("};")
    out.append("")
    dll_pins = [e for e in model.pins if e["dll"]]
    for e in dll_pins:
        out.append(f"static const unsigned char rpin_{e['name']}[] = {{ {arr(e['bytes'])} }};")
        out.append(f"static const unsigned char rpinmask_{e['name']}[] = {{ {arr(e['mask'])} }};")
    out.append("")
    out.append("static const RfshPin RFSH_PINS[] = {")
    for e in dll_pins:
        out.append(f'    {{ "{e["name"]}", {len(e["bytes"])}u, rpin_{e["name"]}, rpinmask_{e["name"]}, '
                   f'{e["parent"]}, {e["offset"]} }},')
    out.append("};")
    out.append("")
    out.append("static const RfshEvidence RFSH_EVIDENCE[] = {")
    for si, kind, pi, off in model.evidence:
        if si >= model.dll_sites:
            continue
        out.append(f"    {{ RFSH_SITE_{model.sites[si]}, '{kind}', {pi}, 0x{off:X}u }},")
    out.append("};")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b200", required=True, help="path to the CORE variant's Virtual Families 2 - B200.exe")
    ap.add_argument("--also", action="append", default=[], help="another variant's executable to prove")
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
    elif HEADER.read_text() != text:
        print("the committed header differs from a fresh render")
        return 1
    print(f"{len(S.PINS)} pins proved on the core variant, {len(args.also)} other variants resolved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
