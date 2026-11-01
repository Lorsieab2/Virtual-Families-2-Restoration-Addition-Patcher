#!/usr/bin/env python3
"""Prove the Time Controls sites against the B200 executables and emit the
companion DLL's site header.

    gen_b200_time_sites.py --b200 "<core>\\Virtual Families 2 - B200.exe" [--write]
        [--also "<other variant>.exe" ...]

The B200 image is relocated and each of the 32 matrix variants links to
different addresses, so the DLL holds no address. This tool

* validate(core): reads the CORE variant with pefile and decodes every pinned
  run with capstone, refusing (SiteError) unless the bytes are the pinned
  bytes, every `context` pin is whole instructions, the two written call sites
  are `call rel32` to the function the DLL expects, each replaced vtable slot
  is a pointer to its function inside a vtable whose RTTI names the class, and
  every address constant has evidence in the pins;
* build_model(core): the wildcard masks (relocated 32-bit fields and the
  displacement of every call/jmp rel32), which pins are searched for and which
  hang off an anchor pin at a fixed offset, and, for each address constant,
  every way it can be derived from where the pins land;
* resolve(exe, model): the algorithm the DLL runs, in Python. A pin that is
  searched for must match exactly once in the executable sections; an anchored
  pin must match its bytes at its offset; every derivation of a constant must
  agree; each slot is the one pointer to its function in the read-only data.
  Run on the core variant and on every other variant to prove them;
* render_header(): the C header, a pure function of b200_time_sites and the
  core executable.
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
import b200_time_sites as S  # noqa: E402

HEADER = RUNTIME / "native" / "b200time" / "b200time_sites.h"
IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_SCN_MEM_WRITE = 0x80000000
IMAGE_SCN_MEM_READ = 0x40000000
MIN_INFORMATIVE = 16        # unmasked bytes a pin needs to be searched for on its own
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
    """Everything the DLL needs, derived from the core variant."""

    def __init__(self):
        self.pins = []          # dicts: name, bytes, mask, parent, offset
        self.sites = []         # ADDRESS_CONSTANTS, then TEST_ADDRESS_CONSTANTS (never given to the DLL)
        self.dll_sites = 0
        self.evidence = []      # (site index, kind, pin index, offset); kind L abs-loc, A abs field, C call target
        self.slots = []         # (slot site, function site)
        self.calls = []         # (call site, function site)


def build_model(core: Exe) -> Model:
    m = Model()
    pins = list(S.PINS)
    masks = {p.name: pin_mask(p, core) for p in pins}
    searched = []
    for p in pins:
        informative = len(p.bytes) - sum(masks[p.name])
        hits = find_all(core.executable(), p.bytes, masks[p.name])
        if informative >= MIN_INFORMATIVE and hits == [p.va]:
            searched.append(p)
    searched_names = {p.name for p in searched}
    for p in pins:
        m.pins.append({"name": p.name, "bytes": p.bytes, "mask": masks[p.name], "parent": -1, "offset": 0,
                       "va": p.va})
    index = {e["name"]: i for i, e in enumerate(m.pins)}
    unanchored = []
    for e in m.pins:
        if e["name"] in searched_names:
            continue
        best = None
        for q in searched:
            d = e["va"] - q.va
            if -MAX_ANCHOR_DISTANCE <= d <= MAX_ANCHOR_DISTANCE + len(q.bytes)                     and (best is None or abs(d) < abs(e["va"] - best.va)):
                best = q
        if best is None:
            unanchored.append(e["name"])
            continue
        e["parent"] = index[best.name]
        e["offset"] = e["va"] - best.va
    if unanchored:
        raise SiteError("not unique and no anchor pin lies near: " + ", ".join(unanchored))
    m.sites = list(S.ADDRESS_CONSTANTS) + list(S.TEST_ADDRESS_CONSTANTS)
    m.dll_sites = len(S.ADDRESS_CONSTANTS)
    slot_sites = set(S.SLOTS)
    for si, name in enumerate(m.sites):
        value = getattr(S, name)
        if name in slot_sites:
            m.slots.append((si, m.sites.index(S.SLOTS[name])))
            continue
        found = False
        for pi, p in enumerate(pins):
            if p.va <= value < p.va + len(p.bytes) or (name in S.CALL_SITES and value == p.va + len(p.bytes)):
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
    for call, func in S.CALL_SITES.items():
        m.calls.append((m.sites.index(call), m.sites.index(func)))
    return m


def locate(exe: Exe, model: Model) -> list[int]:
    """Where every pin lies in this executable (searched, or at its anchor's offset)."""
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
        loc[i] = loc[e["parent"]] + e["offset"]  # offset may be negative: the anchor can follow the pin
        live = exe.read(loc[i], len(e["bytes"]))
        if any(not w and a != b for a, b, w in zip(live, e["bytes"], e["mask"])):
            raise SiteError(f"{e['name']}: bytes differ at its anchor offset")
    return loc


def resolve(exe: Exe, model: Model) -> dict[str, int]:
    """The DLL's algorithm. Returns {constant: VA in this executable}."""
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
    for call, func in model.calls:
        site = value[model.sites[call]]
        raw = exe.read(site, 5)
        target = (site + 5 + struct.unpack("<i", raw[1:])[0]) & 0xFFFFFFFF
        if raw[0] != 0xE8 or target != value[model.sites[func]]:
            raise SiteError(f"{model.sites[call]}: not a call to {model.sites[func]}")
    data = exe.read_only_data()
    for slot, func in model.slots:
        want = struct.pack("<I", value[model.sites[func]])
        hits = []
        for _n, va, raw, _c, _vs in data:
            j = raw.find(want)
            while j >= 0:
                if j % 4 == 0:
                    hits.append(va + j)
                j = raw.find(want, j + 1)
        if len(hits) != 1:
            raise SiteError(f"{model.sites[slot]}: {len(hits)} pointers to {model.sites[func]}")
        value[model.sites[slot]] = hits[0]
    a, b = S.SLOT_ADJACENT
    if value[b] != value[a] + 4:
        raise SiteError(f"{b} does not follow {a}")
    return value


def _cross_checks():
    """pin name -> (call targets that must appear, 32-bit operands that must appear)."""
    return {
        "options_ctor_buttons": (
            {S.BUTTON_CTOR, S.GRAPHICS_GET_IMAGE_GRID, S.BUTTON_SET_TEXT, S.SCENE_ADD_CONTROL, S.GET_EVICT_FONT,
             S.GAME_NEW},
            {S.OPTIONS_BUTTON_IMAGE, S.OPTIONS_DONE_BUTTON_FIELD, S.OPTIONS_STRING_MANAGER_FIELD,
             S.OPTIONS_TEXT_COLOUR, 0x1D2, S.OPTIONS_BUTTON_BOTTOM_MARGIN, S.SCENE_TOP_FIELD, S.SCENE_BOTTOM_FIELD,
             S.CONTROL_HEIGHT_VOFFSET, 0x14},
        ),
        "options_ctor_ids": (set(), {2, 3, 4, 0x74, 0x78, 0x7C}),
        "options_ctor_head": (set(), {S.OPTIONS_DIALOG_VTABLE}),
        "options_ctor_tail": (set(), {0x25B0A, 0x80}),
        "options_handle_head": (set(), {S.MESSAGE_BUTTON_CLICKED, 0x74}),
        "set_speed": (set(), {S.PAUSED_OFFSET, 0x20, 0x24, 0x28, 0x2C}),
        "space_toggle": ({S.SET_SPEED}, {S.GAME_TIME, S.GAME_STATE_SPEED_FIELD, S.PAUSED_OFFSET, S.SPEED_NORMAL}),
        "increment_age": (set(), set()),
        "timeflow_head": (set(), {0x387F4, 30}),
        "timeflow_eligible": (set(), {(-0x15084) & 0xFFFFFFFF}),
        "timeflow_caps": (set(), {S.GAME_STATE_SPEED_FIELD, S.SPEED_FAST, S.SPEED_NORMAL, S.SPEED_SLOW,
                                  S.PAUSED_OFFSET}),
        "timeflow_ticks": (set(), {S.GAME_STATE_SPEED_FIELD, (-0x15130) & 0xFFFFFFFF, 0x88888889}),
        "timeflow_remainder": (set(), {S.GAME_STATE_SPEED_FIELD}),
        "timeflow_tail": (set(), {S.VILLAGER_STRIDE}),
        "timeflow_caller": (set(), {S.VILLAGER_MANAGER}),
        "game_state_get": (set(), {S.GAME_STATE_INSTANCE_PTR}),
        "game_state_load_speed": ({0x468A20}, {S.GAME_TIME, S.GAME_STATE_SPEED_FIELD}),
        "game_state_save_time": ({0x468AC0}, {S.GAME_TIME}),
        "game_state_save_blob": (set(), {S.GAME_STATE_SPEED_FIELD}),
        "calc_price_head": ({S.GET_PRICE}, {S.INVENTORY_MANAGER, 0xD4, 3}),
        "purchase_spend": ({S.CALC_PRICE, S.MONEY_SPEND}, {S.MONEY}),
        "money_spend_wrapper": ({S.MONEY_ADJUST}, set()),
        "store_time_warp_case": ({0x481D80}, {S.MONEY, S.GAME_STATE_SPEED_FIELD, S.PAUSED_OFFSET,
                                              (-3660) & 0xFFFFFFFF}),
    }


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
    for name, (calls, values) in _cross_checks().items():
        got_calls, got_values = _calls_and_immediates(by_name[name])
        for want in calls:
            if want not in got_calls:
                raise SiteError(f"{name}: no call/jmp to {want:#x}")
        for want in values:
            if (want & 0xFFFFFFFF) not in got_values:
                raise SiteError(f"{name}: no operand {want:#x}")
    derived = (
        ("a villager's first loop pointer is manager + array offset + active offset",
         S.VILLAGER_ARRAY_OFFSET + S.VILLAGER_ACTIVE_OFFSET == 0x387F4),
        ("the age field is the loop pointer - 15130h", S.VILLAGER_ACTIVE_OFFSET - 0x15130 == S.VILLAGER_AGE_OFFSET),
        ("the health field is the loop pointer - 15084h",
         S.VILLAGER_ACTIVE_OFFSET - 0x15084 == S.VILLAGER_HEALTH_OFFSET),
        ("the left-home byte follows the active byte", S.VILLAGER_LEFT_HOME_OFFSET == S.VILLAGER_ACTIVE_OFFSET + 4),
        ("the slots are 13 and 14 of the GameState vtable",
         S.GAME_STATE_SLOT_LOAD == S.GAME_STATE_VTABLE + 13 * 4
         and S.GAME_STATE_SLOT_SAVE == S.GAME_STATE_VTABLE + 14 * 4),
        ("the dialog slot is 3 of its vtable", S.OPTIONS_SLOT_HANDLE_MESSAGE == S.OPTIONS_DIALOG_VTABLE + 12),
    )
    for what, ok in derived:
        if not ok:
            raise SiteError(f"derived constant wrong: {what}")
    entries = (("options_handle_head", S.OPTIONS_HANDLE_MESSAGE), ("set_speed", S.SET_SPEED),
               ("increment_age", S.INCREMENT_AGE), ("game_state_get", 0x499620),
               ("game_state_load_head", S.GAME_STATE_LOAD), ("game_state_save_head", S.GAME_STATE_SAVE),
               ("button_ctor_head", S.BUTTON_CTOR), ("set_text", S.BUTTON_SET_TEXT),
               ("add_control_head", S.SCENE_ADD_CONTROL), ("image_grid", S.GRAPHICS_GET_IMAGE_GRID),
               ("graphics_get", S.GRAPHICS_GET), ("game_new", S.GAME_NEW), ("set_checked", S.CONTROL_SET_CHECKED),
               ("calc_price_head", S.CALC_PRICE), ("money_spend_wrapper", S.MONEY_SPEND),
               ("money_adjust_head", S.MONEY_ADJUST), ("store_time_warp_case", S.TIME_WARP_CASE))
    for pin_name, va in entries:
        if by_name[pin_name].va != va:
            raise SiteError(f"{pin_name} is not the entry {va:#x}")
    # Return conventions the stubs assume.
    for name, tail in (("button_ctor_ret", b"\xC2\x18\x00"), ("add_control_ret", b"\xC2\x04\x00")):
        if by_name[name].bytes != tail:
            raise SiteError(f"{name}: not the expected return")
    if not by_name["money_spend_wrapper"].bytes.endswith(b"\xC2\x08\x00"):
        raise SiteError("the money wrapper does not end in ret 8")
    # GetPrice is thiscall with one int (every exit ret 4), the caller CalcPrice does not clean the stack.
    price_exits = [i for i in _md().disasm(core.read(S.GET_PRICE, 0xA0), S.GET_PRICE) if i.mnemonic == "ret"]
    if not price_exits or any(i.op_str != "4" for i in price_exits):
        raise SiteError("CInventoryManager::GetPrice has an exit that is not ret 4")
    # TIME_WARP_ITEM is the store's Time Warp: HandleUpgrade sends it to the Time Warp case, and its itemInfo
    # row is that item at the store price.
    index = core.read(S.HANDLE_UPGRADE_INDEX + S.TIME_WARP_ITEM - S.FIRST_UPGRADE_ITEM, 1)[0]
    if core.u32(S.HANDLE_UPGRADE_TABLE + 4 * index) != S.TIME_WARP_CASE:
        raise SiteError("HandleUpgrade does not send TIME_WARP_ITEM to the Time Warp case")
    row = S.ITEM_INFO_TABLE + S.TIME_WARP_ITEM * 0x24
    if core.u32(row) != S.TIME_WARP_ITEM or core.u32(row + 0xC) != S.STORE_TIME_WARP_PRICE:
        raise SiteError("the itemInfo row of TIME_WARP_ITEM is not the Time Warp at the store price")
    if core.u32(S.GET_PRICE + 0x97) != S.ITEM_INFO_TABLE + 0xC:
        raise SiteError("GetPrice does not read the price field of the itemInfo table")
    grid = by_name["image_grid"]
    rets = [i for i in _md().disasm(grid.bytes, grid.va) if i.mnemonic == "ret"]
    if not rets or any(i.op_str != "4" for i in rets):
        raise SiteError("GetImageGrid has an exit that is not ret 4")
    # The written sites.
    for call, func in S.CALL_SITES.items():
        va = getattr(S, call)
        raw = core.read(va, 5)
        target = (va + 5 + struct.unpack("<i", raw[1:])[0]) & 0xFFFFFFFF
        if raw[0] != 0xE8 or target != getattr(S, func):
            raise SiteError(f"{call}: not a call rel32 to {func}")
        if any(va + k in core.relocs for k in range(1, 5)):
            raise SiteError(f"{call}: a relocated field inside a retargeted call")
    for slot, func in S.SLOTS.items():
        va = getattr(S, slot)
        if core.u32(va) != getattr(S, func) or va not in core.relocs:
            raise SiteError(f"{slot}: not a relocated pointer to {func}")
        vt = max((v for v in S.VTABLE_CLASSES if v <= va), default=None)
        if vt is None or va >= vt + 4 * 40:
            raise SiteError(f"{slot}: not inside a declared vtable")
        cls, col, td = S.VTABLE_CLASSES[vt]
        if core.u32(vt - 4) != col or core.u32(col + 12) != td:
            raise SiteError(f"{cls}: RTTI chain differs")
        if core.read(td + 8, 64).split(b"\0")[0] != b".?AV" + cls.encode() + b"@@":
            raise SiteError(f"{cls}: the type descriptor names another class")
    model = build_model(core)
    got = resolve(core, model)
    for name in (*S.ADDRESS_CONSTANTS, *S.TEST_ADDRESS_CONSTANTS):
        if got[name] != getattr(S, name):
            raise SiteError(f"{name}: derived {got[name]:#x}, expected {getattr(S, name):#x}")
    return model


def validate_variant(exe_bytes: bytes, model: Model) -> dict[str, int]:
    """Prove another variant: every pin located, every derivation agrees."""
    return resolve(Exe(exe_bytes), model)


# ---------------------------------------------------------------- header
def render_header(model: Model) -> str:
    def arr(b: bytes) -> str:
        return ", ".join(f"0x{x:02X}" for x in b)

    out = [
        "// GENERATED by runtime/tools/gen_b200_time_sites.py from runtime/b200_time_sites.py.",
        "// Do not edit. The DLL holds no game address: it searches the live executable for each pinned",
        "// run (mask 1 = wildcard: a relocated field or a call/jmp displacement) and derives every",
        "// address from where the runs were found. It installs nothing unless every pin is found,",
        "// every derivation agrees and every written site is what the core variant has.",
        "#pragma once",
        "",
        "struct B200Pin {",
        "    const char *name; unsigned len; const unsigned char *bytes; const unsigned char *mask;",
        "    int parent;       // -1: searched for in the executable sections; else the index of its anchor pin",
        "    int offset;       // signed distance from the anchor pin",
        "};",
        "struct B200Evidence { unsigned char site; char kind; unsigned short pin; unsigned offset; };",
        "struct B200Link { unsigned char site; unsigned char function; };",
        "",
    ]
    skip = set(S.ADDRESS_CONSTANTS) | set(S.CORE_ONLY_CONSTANTS)
    for key in sorted(vars(S)):
        value = getattr(S, key)
        if key.isupper() and isinstance(value, int) and not isinstance(value, bool) and key not in skip:
            out.append(f"#define B200TC_{key} 0x{value:X}u")
    out.append("")
    out.append("enum B200Site {")
    for name in model.sites[:model.dll_sites]:
        out.append(f"    B200_SITE_{name},")
    out.append("    B200_SITE_COUNT")
    out.append("};")
    out.append("")
    for e in model.pins:
        out.append(f"static const unsigned char pin_{e['name']}[] = {{ {arr(e['bytes'])} }};")
        out.append(f"static const unsigned char pinmask_{e['name']}[] = {{ {arr(e['mask'])} }};")
    out.append("")
    out.append("static const B200Pin B200_PINS[] = {")
    for e in model.pins:
        out.append(f'    {{ "{e["name"]}", {len(e["bytes"])}u, pin_{e["name"]}, pinmask_{e["name"]}, '
                   f'{e["parent"]}, {e["offset"]} }},')
    out.append("};")
    out.append("")
    out.append("static const B200Evidence B200_EVIDENCE[] = {")
    for si, kind, pi, off in model.evidence:
        if si >= model.dll_sites:
            continue
        out.append(f"    {{ B200_SITE_{model.sites[si]}, '{kind}', {pi}, 0x{off:X}u }},")
    out.append("};")
    out.append("// slot site, the function it points to")
    out.append("static const B200Link B200_SLOTS[] = {")
    for slot, func in model.slots:
        out.append(f"    {{ B200_SITE_{model.sites[slot]}, B200_SITE_{model.sites[func]} }},")
    out.append("};")
    out.append("// call site, the function it calls")
    out.append("static const B200Link B200_CALLS[] = {")
    for call, func in model.calls:
        out.append(f"    {{ B200_SITE_{model.sites[call]}, B200_SITE_{model.sites[func]} }},")
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
