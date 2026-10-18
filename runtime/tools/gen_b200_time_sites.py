#!/usr/bin/env python3
"""Prove every Time Controls site against the B200 executable and emit the
companion DLL's site header.

    gen_b200_time_sites.py --b200 "<folder>\\Virtual Families 2 - B200.exe" [--write]

Two jobs, kept apart (same split as gen_sites.py, which proves the vanilla
runtime-hook sites):

* validate(): reads the B200 executable with pefile and decodes every pinned
  run with capstone, refusing (SiteError) unless
    - the bytes are exactly the pinned bytes (a relocated 32-bit field is
      compared as link-time value; the .reloc table names those fields);
    - a "context" pin is whole instructions;
    - a "retarget" pin is exactly one `call rel32` to its target;
    - a "vtable_slot" pin is a 4-byte pointer holding exactly its target, in a
      declared vtable whose RTTI chain (COL -> TypeDescriptor) names the class;
    - no two written runs overlap and no direct branch anywhere in .text lands
      inside the bytes the DLL overwrites (it may land on their first byte);
    - every address constant the DLL uses is proved by the instructions of a
      pin (CROSS_CHECKS), so a number cannot drift from its evidence.
* render_header(): the C header, a pure function of b200_time_sites. The DLL
  installs nothing unless every pin matches live memory.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import b200_time_sites as S  # noqa: E402
import gen_sites  # noqa: E402  (the PE image reader / branch scan shared with the vanilla proof)

HEADER = RUNTIME / "native" / "b200time" / "b200time_sites.h"
SiteError = gen_sites.SiteError


def _md() -> Cs:
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    return md


def relocated_fields(exe: bytes) -> set[int]:
    """VAs of every HIGHLOW (absolute 32-bit) relocation in the executable."""
    pe = pefile.PE(data=exe, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_BASERELOC"]])
    out = set()
    for block in getattr(pe, "DIRECTORY_ENTRY_BASERELOC", []):
        for entry in block.entries:
            if entry.type == pefile.RELOCATION_TYPE["IMAGE_REL_BASED_HIGHLOW"]:
                out.add(pe.OPTIONAL_HEADER.ImageBase + entry.rva)
    return out


def pin_reloc_offsets(pin, fields: set[int]) -> list[int]:
    """Offsets inside the pin where a relocated 32-bit field starts."""
    return sorted(va - pin.va for va in fields if pin.va <= va and va + 4 <= pin.va + len(pin.bytes))


def calls_and_immediates(pin):
    """(call/jmp rel32 targets, absolute 32-bit values) decoded from a context pin."""
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


# pin name -> (call targets that must appear, 32-bit immediates/displacements that must appear)
CROSS_CHECKS = {
    "options_ctor_buttons": (
        {S.BUTTON_CTOR, S.GRAPHICS_GET_IMAGE_GRID, S.BUTTON_SET_TEXT, S.SCENE_ADD_CONTROL, S.GET_EVICT_FONT,
         S.GAME_NEW},
        {S.OPTIONS_BUTTON_IMAGE, S.OPTIONS_DONE_BUTTON_FIELD, S.OPTIONS_STRING_MANAGER_FIELD,
         S.OPTIONS_TEXT_COLOUR, 0x1D2, S.OPTIONS_BUTTON_BOTTOM_MARGIN, S.SCENE_TOP_FIELD, S.SCENE_BOTTOM_FIELD,
         S.CONTROL_HEIGHT_VOFFSET, 0x14},
    ),
    "options_ctor_ids": (set(), {2, 3, 4, 0x74, 0x78, 0x7C}),
    "options_ctor_head": (set(), {S.OPTIONS_DIALOG_VTABLE}),
    "options_ctor_tail": (set(), {0x25B0A, 0x80}),  # the last check box reads its setting from the game state; [ebx+80h] = state
    "options_handle_head": (set(), {S.MESSAGE_BUTTON_CLICKED, 0x74}),
    "set_speed": (set(), {S.PAUSED_OFFSET, 0x20, 0x24, 0x28, 0x2C}),
    "space_toggle": ({S.SET_SPEED}, {S.GAME_TIME, S.GAME_STATE_SPEED_FIELD, S.PAUSED_OFFSET, S.SPEED_NORMAL}),
    "increment_age": (set(), set()),
    "timeflow_head": (set(), {0x387F4, 30}),
    "timeflow_eligible": (set(), {(-0x15084) & 0xFFFFFFFF}),
    "timeflow_caps": (set(), {S.GAME_STATE_SPEED_FIELD, S.SPEED_FAST, S.SPEED_NORMAL, S.SPEED_SLOW, S.PAUSED_OFFSET}),
    "timeflow_ticks": (set(), {S.GAME_STATE_SPEED_FIELD, (-0x15130) & 0xFFFFFFFF, 0x88888889}),
    "timeflow_remainder": (set(), {S.GAME_STATE_SPEED_FIELD}),
    "timeflow_tail": (set(), {S.VILLAGER_STRIDE}),
    "timeflow_caller": (set(), {S.VILLAGER_MANAGER}),
    "game_state_get": (set(), {S.GAME_STATE_INSTANCE_PTR}),
    "game_state_load_speed": ({0x468A20}, {S.GAME_TIME, S.GAME_STATE_SPEED_FIELD}),
    "game_state_save_time": ({0x468AC0}, {S.GAME_TIME}),
    "game_state_save_blob": (set(), {S.GAME_STATE_SPEED_FIELD}),
}

# The villager layout the module relies on follows from these two derived facts.
DERIVED_CONSTANTS = (
    ("a villager's first loop pointer is manager + array offset + active offset",
     S.VILLAGER_ARRAY_OFFSET + S.VILLAGER_ACTIVE_OFFSET == 0x387F4),
    ("the age field is the loop pointer - 15130h", S.VILLAGER_ACTIVE_OFFSET - 0x15130 == S.VILLAGER_AGE_OFFSET),
    ("the health field is the loop pointer - 15084h", S.VILLAGER_ACTIVE_OFFSET - 0x15084 == S.VILLAGER_HEALTH_OFFSET),
    ("the left-home byte follows the active byte", S.VILLAGER_LEFT_HOME_OFFSET == S.VILLAGER_ACTIVE_OFFSET + 4),
    ("the slots are 13 and 14 of the GameState vtable",
     S.GAME_STATE_SLOT_LOAD == S.GAME_STATE_VTABLE + 13 * 4 and S.GAME_STATE_SLOT_SAVE == S.GAME_STATE_VTABLE + 14 * 4),
    ("the dialog slot is 3 of its vtable", S.OPTIONS_SLOT_HANDLE_MESSAGE == S.OPTIONS_DIALOG_VTABLE + 12),
)


def validate(exe: bytes) -> None:
    img = gen_sites.Image(exe)
    if img.base != S.IMAGE_BASE:
        raise SiteError(f"image base {img.base:#x} is not {S.IMAGE_BASE:#x}")
    fields = relocated_fields(exe)
    if not fields:
        raise SiteError("the B200 image has no relocations: the module's ASLR handling would be untested")
    names = set()
    written = []
    for pin in S.PINS:
        if pin.name in names:
            raise SiteError(f"duplicate pin {pin.name}")
        names.add(pin.name)
        have = img.read(pin.va, len(pin.bytes))
        if have != pin.bytes:
            raise SiteError(f"{pin.name} at {pin.va:#x}: the executable's bytes differ from the pinned bytes")
        if pin.kind in ("context", "retarget"):
            insns = list(_md().disasm(pin.bytes, pin.va))
            if sum(i.size for i in insns) != len(pin.bytes):
                raise SiteError(f"{pin.name}: pinned bytes are not whole instructions")
        if pin.kind == "retarget":
            insns = list(_md().disasm(pin.bytes, pin.va))
            if len(insns) != 1 or pin.bytes[0] != 0xE8 or len(pin.bytes) != 5 or insns[0].operands[0].imm != pin.target:
                raise SiteError(f"{pin.name}: not exactly one call rel32 to {pin.target:#x}")
            if pin_reloc_offsets(pin, fields):
                raise SiteError(f"{pin.name}: a relocated field inside a retargeted call")
            written.append(pin)
        elif pin.kind == "vtable_slot":
            if len(pin.bytes) != 4 or struct.unpack("<I", pin.bytes)[0] != pin.target:
                raise SiteError(f"{pin.name}: not a 4-byte pointer to {pin.target:#x}")
            if pin_reloc_offsets(pin, fields) != [0]:
                raise SiteError(f"{pin.name}: the slot is not a relocated pointer")
            vt = max((v for v in S.VTABLE_CLASSES if v <= pin.va), default=None)
            if vt is None or pin.va >= vt + 4 * 40:
                raise SiteError(f"{pin.name}: not inside a declared vtable")
            cls, col, td = S.VTABLE_CLASSES[vt]
            if struct.unpack("<I", img.read(vt - 4, 4))[0] != col:
                raise SiteError(f"{cls}: the vtable's CompleteObjectLocator is not {col:#x}")
            if struct.unpack("<I", img.read(col + 12, 4))[0] != td:
                raise SiteError(f"{cls}: the locator's TypeDescriptor is not {td:#x}")
            name = img.read(td + 8, 64).split(b"\0")[0]
            if name != b".?AV" + cls.encode() + b"@@":
                raise SiteError(f"{cls}: RTTI names {name!r}")
            written.append(pin)
        elif pin.kind not in ("context", "data"):
            raise SiteError(f"{pin.name}: unknown kind {pin.kind}")
    for a in written:
        for b in written:
            if a is not b and a.va < b.va + len(b.bytes) and b.va < a.va + len(a.bytes):
                raise SiteError(f"written runs {a.name} and {b.name} overlap")
    branches = img.direct_branch_targets()
    for pin in written:
        for src, dst in branches:
            if pin.va < dst < pin.va + len(pin.bytes) and not (pin.va <= src < pin.va + len(pin.bytes)):
                raise SiteError(f"a branch at {src:#x} lands inside {pin.name} ({dst:#x})")
    by_name = {p.name: p for p in S.PINS}
    for name, (calls, values) in CROSS_CHECKS.items():
        got_calls, got_values = calls_and_immediates(by_name[name])
        # An absolute field is stored as its link-time value, so a plain compare is right.
        for want in calls:
            if want not in got_calls:
                raise SiteError(f"{name}: no call/jmp to {want:#x}")
        for want in values:
            if (want & 0xFFFFFFFF) not in got_values:
                raise SiteError(f"{name}: no operand {want:#x}")
    for what, ok in DERIVED_CONSTANTS:
        if not ok:
            raise SiteError(f"derived constant wrong: {what}")
    # The entry points the DLL replaces begin their pins.
    if by_name["options_handle_head"].va != S.OPTIONS_HANDLE_MESSAGE:
        raise SiteError("options_handle_head is not the HandleMessage entry")
    if by_name["set_speed"].va != S.SET_SPEED or by_name["increment_age"].va != S.INCREMENT_AGE:
        raise SiteError("SetSpeed / IncrementAge pins are not at their entries")
    if by_name["game_state_get"].va != 0x499620:
        raise SiteError("game_state_get is not the Get entry")
    # Return conventions the stubs assume.
    for name, tail in (("button_ctor_ret", b"\xC2\x18\x00"), ("add_control_ret", b"\xC2\x04\x00"),
                       ("image_grid_ret_1", b"\xC2\x04\x00"), ("image_grid_ret_2", b"\xC2\x04\x00"),
                       ("image_grid_ret_3", b"\xC2\x04\x00"), ("image_grid_ret_4", b"\xC2\x04\x00"),
                       ("image_grid_ret_5", b"\xC2\x04\x00"), ("image_grid_ret_6", b"\xC2\x04\x00"),
                       ("graphics_get_ret_1", b"\xC3"), ("graphics_get_ret_2", b"\xC3")):
        if by_name[name].bytes != tail:
            raise SiteError(f"{name}: not the expected return")


def identifier(name: str) -> str:
    return "B200TC_" + name.upper()


def render_header(exe: bytes | None = None) -> str:
    """The generated header. `exe` supplies the relocation fields; when absent the
    committed header is returned unchanged by the caller (tests compare against
    a render from the real executable)."""
    fields = relocated_fields(exe) if exe is not None else set()
    out = [
        "// GENERATED by runtime/tools/gen_b200_time_sites.py from runtime/b200_time_sites.py.",
        "// Do not edit. Every run is the exact B200 core executable's bytes; the DLL installs",
        "// nothing unless all of them match live memory. Addresses are link-time VAs at image",
        "// base 0x400000; the DLL adds the live module base - 0x400000 (the image is relocated).",
        "#pragma once",
        "",
        "struct B200Pin {",
        "    const char *name; unsigned va; unsigned len; const unsigned char *bytes;",
        "    const unsigned short *relocs; unsigned relocCount;  // offsets of relocated 32-bit fields",
        "};",
        "",
    ]
    for key in sorted(vars(S)):
        value = getattr(S, key)
        if key.isupper() and isinstance(value, int) and not isinstance(value, bool):
            out.append(f"#define {identifier(key)} 0x{value:X}u")
    out.append("")
    for pin in S.PINS:
        offs = pin_reloc_offsets(pin, fields)
        arr = ", ".join(f"0x{b:02X}" for b in pin.bytes)
        out.append(f"static const unsigned char pin_{pin.name}[] = {{ {arr} }};")
        out.append(f"static const unsigned short pin_{pin.name}_relocs[] = {{ {', '.join(str(o) for o in offs) or '0'} }};")
    out.append("")
    out.append("static const B200Pin B200_PINS[] = {")
    for pin in S.PINS:
        n = len(pin_reloc_offsets(pin, fields))
        out.append(f'    {{ "{pin.name}", 0x{pin.va:X}u, {len(pin.bytes)}u, pin_{pin.name}, '
                   f'pin_{pin.name}_relocs, {n}u }},')
    out.append("};")
    out.append("")
    # The writes: which pins the DLL changes, and to what.
    out.append("// Pins the DLL writes: 'C' = call rel32 retarget, 'S' = vtable slot.")
    out.append("struct B200Write { const char *pin; char kind; unsigned va; };")
    out.append("static const B200Write B200_WRITES[] = {")
    for pin in S.PINS:
        if pin.kind == "retarget":
            out.append(f'    {{ "{pin.name}", \'C\', 0x{pin.va:X}u }},')
        elif pin.kind == "vtable_slot":
            out.append(f'    {{ "{pin.name}", \'S\', 0x{pin.va:X}u }},')
    out.append("};")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b200", required=True, help="path to Virtual Families 2 - B200.exe (core variant)")
    ap.add_argument("--write", action="store_true", help="rewrite the committed header")
    args = ap.parse_args(argv)
    exe = Path(args.b200).read_bytes()
    validate(exe)
    text = render_header(exe)
    if args.write:
        HEADER.parent.mkdir(parents=True, exist_ok=True)
        HEADER.write_text(text, newline="\n")
        print(f"wrote {HEADER}")
    elif HEADER.read_text() != text:
        print("the committed header differs from a fresh render")
        return 1
    print(f"{len(S.PINS)} pins proved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
