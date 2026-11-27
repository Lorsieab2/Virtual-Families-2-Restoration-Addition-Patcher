#!/usr/bin/env python3
"""Prove the Skin Tones sites against the B209 executables and emit the companion DLL's header.

    gen_b200_skin_sites.py --core "<core>\\Virtual Families 2 - B209.exe" [--write]
        [--also "<other variant>.exe" ...]

The B209 image is relocated and every matrix variant links to different addresses, so the DLL holds no address.
The pin machinery is Family History's (gen_b200_history_sites: Exe, pin_mask, find_all, call_target); this tool

* validate(core): every pin is the pinned bytes and whole instructions, every searched pin is found exactly once
  and every call-located pin is that call's target, every call the DLL retargets reaches its function (directly or
  through one `jmp rel32` thunk), every call it relies on calls what it should, every hooked entry's stolen bytes
  are whole position-independent instructions with nothing branching into them, every layout constant appears as an
  operand where the game uses it, theGameState's vtable holds MakeGameStatePath / Load / Save at the slots the DLL
  uses, the image table holds every people sheet and the Holiday helpers' id tables name the Holiday pictures, and
  every derived address equals the core's;
* resolve(exe, model): the algorithm the DLL runs, in Python, on any executable;
* render_header(model): the C header, a pure function of b200_skin_sites and the core executable.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from capstone.x86 import X86_OP_IMM, X86_OP_MEM

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))
import b200_skin_sites as S  # noqa: E402
from gen_b200_history_sites import Exe, SiteError, _md, call_target, find_all, pin_mask  # noqa: E402

HEADER = RUNTIME / "native" / "b200skin" / "b200skin_sites.h"


class Model:
    def __init__(self):
        self.pins = []        # dicts: name, bytes, mask, parent (-1 searched), offset, va
        self.sites = list(S.ADDRESS_CONSTANTS)
        self.evidence = []    # (site, kind 'L' or 'A', pin, offset)
        self.calls = []       # (pin, offset, function site): checked exactly
        self.call_hooks = []  # (site of the call, function site): the function or a jmp thunk to it
        self.entry_hooks = [] # (function site, steal)


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
        elif name in S.RETURNS:
            pin, off = S.RETURNS[name]
            m.evidence.append((si, "L", _pin_index(pin), off))
        elif name in S.GLOBALS:
            pin, off = S.GLOBALS[name]
            m.evidence.append((si, "A", _pin_index(pin), off))
            for pin2, off2 in S.GLOBAL_ALSO.get(name, ()):
                m.evidence.append((si, "A", _pin_index(pin2), off2))
        else:
            pin, off, _func = S.CALL_HOOKS[name]
            m.evidence.append((si, "L", _pin_index(pin), off))
    for name, (_pin, _off, func) in S.CALL_HOOKS.items():
        m.call_hooks.append((m.sites.index(name), m.sites.index(func)))
    for pin, off, func in S.CALLS:
        m.calls.append((_pin_index(pin), off, m.sites.index(func)))
    for name, steal in S.ENTRY_HOOKS.items():
        m.entry_hooks.append((m.sites.index(name), steal))
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


REACH_SPAN = 0x40       # a thunk or wrapper calls (or jumps to) the function within its first 40h bytes


def reaches(exe: Exe, target: int, function: int) -> bool:
    """A call to `target` reaches `function`: it is the function, or a thunk or small wrapper that calls or jumps to
    it within its first REACH_SPAN bytes (B209's `jmp` thunk; Cheat Upgrades' VF2ImpregnateAndClearForce). The DLL
    applies the same rule (b200skin.cpp Reaches)."""
    if target == function:
        return True
    code = exe.read(target, REACH_SPAN)
    for i in _md().disasm(code, target):
        if i.mnemonic in ("call", "jmp") and i.size == 5 and i.operands and i.operands[0].type == X86_OP_IMM:
            if i.operands[0].imm & 0xFFFFFFFF == function:
                return True
        if i.mnemonic in ("ret", "int3"):
            break
    return False


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
    for si, func in model.call_hooks:
        site = value[model.sites[si]]
        if not reaches(exe, call_target(exe, site), value[model.sites[func]]):
            raise SiteError(f"{model.sites[si]}: does not reach {model.sites[func]}")
    vt = value["GS_VTABLE"]
    if exe.u32(vt + S.GS_LOAD_VSLOT) != value["GS_LOAD"] or exe.u32(vt + S.GS_SAVE_VSLOT) != value["GS_SAVE"]:
        raise SiteError("theGameState's vtable does not hold Load / Save at slots 13 / 14")
    check_images(exe, value)
    return value


def image_entries(exe: Exe, value: dict[str, int]) -> dict[int, int]:
    """{image id: entry VA} of the image table (the first entry of each id, as the game's lookup finds it)."""
    out = {}
    va, end = value["IMAGE_TABLE"], value["IMAGE_TABLE_END"]
    if not (va < end and (end - va) % S.IMAGE_ENTRY_SIZE == 0):
        raise SiteError("the image table's bounds are not whole entries")
    while va < end:
        out.setdefault(exe.u32(va + S.IMAGE_ENTRY_ID), va)
        va += S.IMAGE_ENTRY_SIZE
    return out


def holiday_frame_path(index: int) -> str:
    sex, rest = divmod(index, S.HOLIDAY_BODIES * S.HOLIDAY_FRAMES_PER_BODY)
    body, k = divmod(rest, S.HOLIDAY_FRAMES_PER_BODY)
    role = 2 if k >= S.HOLIDAY_ROLE_OFFSETS[2] else 1 if k >= S.HOLIDAY_ROLE_OFFSETS[1] else 0
    frame = k - S.HOLIDAY_ROLE_OFFSETS[role]
    return (f"VillagerBodies/{('Female', 'Male')[sex]}/Body_{S.HOLIDAY_FIRST_BODY + body:02d}/"
            f"{('bodies', 'actions', 'sit')[role]}/Frame{frame:02d}.png")


def holiday_detail_path(index: int) -> str:
    sex, body = divmod(index, S.HOLIDAY_BODIES)
    return f"VillagerDetailBodies/{('Female', 'Male')[sex]}/Body_{S.HOLIDAY_FIRST_BODY + body:02d}/Frame00.png"


def check_images(exe: Exe, value: dict[str, int]) -> None:
    entries = image_entries(exe, value)
    for image, part, name in S.IMAGE_SHEETS:
        entry = entries.get(image)
        if entry is None:
            raise SiteError(f"image {image:#x} is not in the image table")
        stem = exe.cstr(exe.u32(entry + 4))
        tiles = exe.u32(entry + 0x14)
        shown = (stem.decode() if tiles == 0 else f"{stem.decode()}{part}0.png") if stem else None
        if shown != name:
            raise SiteError(f"image {image:#x} file {part} is {shown!r}, not {name!r}")
    if [exe.u32(value["HOL_ROLE_FRAMES"] + 4 * k) for k in range(3)] != list(S.HOLIDAY_ROLE_FRAMES) or \
            [exe.u32(value["HOL_ROLE_OFFSETS"] + 4 * k) for k in range(3)] != list(S.HOLIDAY_ROLE_OFFSETS):
        raise SiteError("the Holiday helper's role tables differ")
    for table, count, path in (("HOL_FRAME_IDS", S.HOLIDAY_FRAMES, holiday_frame_path),
                               ("HOL_DETAIL_IDS", S.HOLIDAY_DETAILS, holiday_detail_path)):
        for k in range(count):
            image = exe.u32(value[table] + 4 * k)
            entry = entries.get(image)
            name = exe.cstr(exe.u32(entry + 4)) if entry else None
            if name is None or name.decode() != path(k):
                raise SiteError(f"{table}[{k}] = image {image}: {name!r}, not {path(k)!r}")


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
    return {
        "draw_villager": {S.VILLAGER_STRIDE, S.VILLAGER_ARRAY_OFFSET, 8},
        "draw_carried": {S.VILLAGER_PREGNANT, S.VILLAGER_CARRIED, S.BABY_CELL, 1, 3},
        "hol_scene_impl": {0x246, 0x247, S.HOLIDAY_FRAMES - 1, 3},
        "detail": {S.VILLAGER_AGE, S.VILLAGER_GENDER, S.VILLAGER_HEAD, S.VILLAGER_BODY, 0x384},
        "event": {S.VILLAGER_GENDER, S.VILLAGER_HEAD, S.VILLAGER_BODY},
        "df_parents": {S.RECORD_PARENT1, S.RECORD_PARENT1 + S.PEEP_GENDER, S.RECORD_PARENT1 + S.PEEP_HEAD,
                       S.RECORD_PARENT1 + S.PEEP_BODY, S.RECORD_PARENT2 + S.PEEP_GENDER,
                       S.RECORD_PARENT2 + S.PEEP_HEAD, S.RECORD_PARENT2 + S.PEEP_BODY, 0x10},
        "df_child": {S.PEEP_RECORD_SIZE, S.RECORD_CHILDREN, S.RECORD_CHILD_COUNT, S.RECORD_CHILDREN + S.PEEP_GENDER,
                     S.RECORD_CHILDREN + S.PEEP_HEAD, S.RECORD_CHILDREN + S.PEEP_BODY, 0x10},
        "ms_conceive": {S.VILLAGER_HEAD, S.VILLAGER_BODY, 1, 0},
        "vp_conceive": {S.VILLAGER_HEAD, S.VILLAGER_BODY, 1, 0},
        "gm_find_image": {S.IMAGE_ENTRY_SIZE, 4},
        "vs_rename_message": {S.VILLAGER_NAME, 0x19},
        "vs_rename_selection": {S.VILLAGER_NAME, 0x19},
        "ft_change_name": {0x19},
        "gs_get": {S.CORE_VALUES["GAME_STATE_INSTANCE"]},
    }


def validate(exe_bytes: bytes) -> Model:
    """Prove the core variant; returns the model."""
    core = Exe(exe_bytes)
    if core.base != S.IMAGE_BASE:
        raise SiteError(f"image base {core.base:#x} is not {S.IMAGE_BASE:#x}")
    if not core.relocs:
        raise SiteError("the B209 image has no relocations: the ASLR handling would be untested")
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
    # every retargeted or relied-on call is a whole `call rel32` instruction of its pin
    for name, (pin, off) in [(n, (p, o)) for n, (p, o, _f) in S.CALL_HOOKS.items()] + \
            [(f"{p}+{o:#x}", (p, o)) for p, o, _f in S.CALLS]:
        p = by_name[pin]
        starts = {i.address - p.va: i for i in _md().disasm(p.bytes, p.va)}
        if off not in starts or starts[off].mnemonic != "call" or starts[off].size != 5 or p.bytes[off] != 0xE8:
            raise SiteError(f"{name}: {pin}+{off:#x} is not a call rel32 instruction")
    for name, (pin, off) in S.RETURNS.items():
        p = by_name[pin]
        starts = {i.address - p.va: i for i in _md().disasm(p.bytes, p.va)}
        if off - 5 not in starts or starts[off - 5].mnemonic != "call":
            raise SiteError(f"{name}: {pin}+{off:#x} is not the return address of a call")
    for name, steal in S.ENTRY_HOOKS.items():
        pin = by_name[S.FUNCTIONS[name]]
        if steal < 5 or steal > 16 or pin.skip or pin.how != S.SEARCH and False:
            raise SiteError(f"{name}: stolen length {steal} out of range")
        mask = model.pins[_pin_index(pin.name)]["mask"]
        if any(mask[:steal]):
            raise SiteError(f"{name}: a wildcard in the stolen bytes")
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
        for i in _md().disasm(pin.bytes, pin.va):
            if (i.mnemonic.startswith("j") or i.mnemonic == "loop") and i.operands \
                    and i.operands[0].type == X86_OP_IMM and pin.va < i.operands[0].imm < pin.va + steal:
                raise SiteError(f"{name}: a branch into the stolen bytes at {i.address:#x}")
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
        "// GENERATED by runtime/tools/gen_b200_skin_sites.py from runtime/b200_skin_sites.py.",
        "// Do not edit. The DLL holds no game address: it searches the live executable for each pinned",
        "// run (mask 1 = wildcard: a relocated field, a call/jmp displacement, or the leading bytes of an",
        "// entry another companion DLL hooks), finds the pins marked with a parent as the target of the call",
        "// at that offset of the parent, and derives every address from where the runs were found. It",
        "// installs nothing unless every pin is found exactly once, every derivation agrees and every call",
        "// it relies on calls what the core variant calls.",
        "#pragma once",
        "",
        "struct SkinPin {",
        "    const char *name; unsigned len; const unsigned char *bytes; const unsigned char *mask;",
        "    int parent;           // -1: searched for; else the pin whose call at call_offset targets it",
        "    unsigned call_offset; // offset of that E8 byte in the parent",
        "};",
        "struct SkinEvidence { unsigned char site; char kind; unsigned char pin; unsigned offset; };",
        "struct SkinCall { unsigned char pin; unsigned offset; unsigned char function; };",
        "struct SkinCallHook { unsigned char site; unsigned char function; };",
        "struct SkinEntryHook { unsigned char site; unsigned char steal; };",
        "",
    ]
    skip = set(S.CORE_ONLY_CONSTANTS)
    for key in sorted(vars(S)):
        value = getattr(S, key)
        if key.isupper() and isinstance(value, int) and not isinstance(value, bool) and key not in skip:
            out.append(f"#define SKIN_{key} 0x{value:X}u")
    out.append("")
    out.append("enum SkinSite {")
    for name in model.sites:
        out.append(f"    SKIN_SITE_{name},")
    out.append("    SKIN_SITE_COUNT")
    out.append("};")
    out.append("")
    for e in model.pins:
        out.append(f"static const unsigned char spin_{e['name']}[] = {{ {arr(e['bytes'])} }};")
        out.append(f"static const unsigned char smask_{e['name']}[] = {{ {arr(e['mask'])} }};")
    out.append("")
    out.append("static const SkinPin SKIN_PINS[] = {")
    for e in model.pins:
        out.append(f'    {{ "{e["name"]}", {len(e["bytes"])}u, spin_{e["name"]}, smask_{e["name"]}, '
                   f'{e["parent"]}, 0x{e["offset"]:X}u }},')
    out.append("};")
    out.append("")
    out.append("static const SkinEvidence SKIN_EVIDENCE[] = {")
    for si, kind, pi, off in model.evidence:
        out.append(f"    {{ SKIN_SITE_{model.sites[si]}, '{kind}', {pi}, 0x{off:X}u }},")
    out.append("};")
    out.append("static const SkinCall SKIN_CALLS[] = {")
    for pi, off, func in model.calls:
        out.append(f"    {{ {pi}, 0x{off:X}u, SKIN_SITE_{model.sites[func]} }},")
    out.append("};")
    out.append("static const SkinCallHook SKIN_CALL_HOOKS[] = {")
    for si, func in model.call_hooks:
        out.append(f"    {{ SKIN_SITE_{model.sites[si]}, SKIN_SITE_{model.sites[func]} }},")
    out.append("};")
    out.append("static const SkinEntryHook SKIN_ENTRY_HOOKS[] = {")
    for si, steal in model.entry_hooks:
        out.append(f"    {{ SKIN_SITE_{model.sites[si]}, {steal} }},")
    out.append("};")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", required=True, help="path to the CORE variant's Virtual Families 2 - B209.exe")
    ap.add_argument("--also", action="append", default=[], help="another executable to prove")
    ap.add_argument("--write", action="store_true", help="rewrite the committed header")
    args = ap.parse_args(argv)
    model = validate(Path(args.core).read_bytes())
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
