#!/usr/bin/env python3
"""Prove the Stage 1 hook sites against the vanilla executable and emit the
companion DLL's site header.

    gen_sites.py --vanilla "<vanilla game folder>\\Virtual Families 2.exe"

Two separate jobs:

* validate(): decodes every pinned run in the VANILLA executable with capstone
  and refuses (SiteError) unless
    - the bytes are exactly the pinned bytes;
    - a "detour" pin is a whole number of instructions, at least 5 bytes, the
      shortest such run, and none of its instructions is relative (no
      branch/call/ret/int, nothing position-dependent), so the stolen copy
      runs unchanged from the trampoline;
    - a "replace" pin is exactly one instruction of at least 5 bytes;
    - a "retarget" pin is exactly one `call rel32` to CanStartNextGeneration;
    - a "context" pin ends on an instruction boundary;
    - no direct branch anywhere in .text lands inside the bytes the DLL
      overwrites (it may land on their first byte);
    - the CanStartNextGeneration callers are exactly the pinned four, and
      nothing references 0x48FF70 or 0x4A0810 by absolute address.
* render_header(): the C header, a pure function of vf2_runtime_sites.PINS.
  The DLL refuses to install anything unless every pin matches live memory.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

from capstone import (CS_ARCH_X86, CS_GRP_BRANCH_RELATIVE, CS_GRP_CALL, CS_GRP_INT,
                      CS_GRP_IRET, CS_GRP_JUMP, CS_GRP_RET, CS_MODE_32, Cs)
from capstone.x86 import X86_OP_IMM

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))
import vf2_runtime_sites as S  # noqa: E402

HEADER = RUNTIME / "native" / "vf2fun" / "vf2fun_sites.h"
RELATIVE_GROUPS = (CS_GRP_JUMP, CS_GRP_CALL, CS_GRP_RET, CS_GRP_INT, CS_GRP_IRET,
                   CS_GRP_BRANCH_RELATIVE)


class SiteError(RuntimeError):
    pass


class Image:
    def __init__(self, data: bytes):
        self.data = data
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe:pe + 4] != b"PE\0\0":
            raise SiteError("not a PE image")
        nsec = struct.unpack_from("<H", data, pe + 6)[0]
        optsz = struct.unpack_from("<H", data, pe + 20)[0]
        opt = pe + 24
        self.base = struct.unpack_from("<I", data, opt + 28)[0]
        self.sections = []
        for i in range(nsec):
            o = opt + optsz + i * 40
            name = data[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, rva, rsize, raw = struct.unpack_from("<IIII", data, o + 8)
            self.sections.append((name, rva, vsize, raw, rsize))
        text = [s for s in self.sections if s[0] == ".text"]
        if len(text) != 1:
            raise SiteError("expected exactly one .text section")
        _, rva, _vs, raw, rsize = text[0]
        self.text_va = self.base + rva
        self.text = data[raw:raw + rsize]

    def read(self, va: int, size: int) -> bytes:
        rva = va - self.base
        for _n, sva, vsize, raw, rsize in self.sections:
            if sva <= rva and rva + size <= sva + min(max(vsize, rsize), rsize):
                return self.data[raw + rva - sva: raw + rva - sva + size]
        raise SiteError(f"{va:#x}+{size:#x} is not backed by file data")

    def direct_branch_targets(self):
        """(source, target) of every byte position that decodes as a direct
        call/jmp/jcc. Deliberately over-approximate: every offset is tried, so a
        real branch can never be missed (false positives only make it stricter)."""
        t = self.text
        out = []
        for i in range(len(t) - 6):
            b = t[i]
            if b in (0xE8, 0xE9):
                out.append((self.text_va + i, self.text_va + i + 5 + struct.unpack_from("<i", t, i + 1)[0]))
            elif 0x70 <= b <= 0x7F or b == 0xEB:
                out.append((self.text_va + i, self.text_va + i + 2 + struct.unpack_from("<b", t, i + 1)[0]))
            elif b == 0x0F and 0x80 <= t[i + 1] <= 0x8F:
                out.append((self.text_va + i, self.text_va + i + 6 + struct.unpack_from("<i", t, i + 2)[0]))
        return out


def _md() -> Cs:
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    return md


def decode_run(md: Cs, code: bytes, va: int):
    insns = list(md.disasm(code, va))
    if sum(i.size for i in insns) != len(code):
        raise SiteError(f"{va:#x}: pinned bytes do not decode as whole instructions")
    return insns


def is_relative(insn) -> bool:
    if any(insn.group(g) for g in RELATIVE_GROUPS):
        return True
    # x86-32 has no eip-relative addressing; immediates and absolute
    # displacements are position independent.
    return False


def steal_length(md: Cs, code: bytes, va: int, minimum: int = 5) -> int:
    """Shortest whole-instruction run of at least `minimum` bytes, refusing any
    relative instruction inside it."""
    total = 0
    for insn in md.disasm(code, va):
        if is_relative(insn):
            raise SiteError(f"{insn.address:#x}: '{insn.mnemonic} {insn.op_str}' is relative; refusing to steal it")
        total += insn.size
        if total >= minimum:
            return total
    raise SiteError(f"{va:#x}: could not decode {minimum} stealable bytes")


def validate(data: bytes) -> list[str]:
    if hashlib.sha256(data).hexdigest() != S.VANILLA_SHA256:
        raise SiteError("this is not the vanilla Virtual Families 2 executable")
    img = Image(data)
    if img.base != S.IMAGE_BASE:
        raise SiteError(f"unexpected image base {img.base:#x}")
    md = _md()
    facts = []
    overwritten = []
    for pin in S.PINS:
        live = img.read(pin.va, len(pin.expected))
        if live != pin.expected:
            raise SiteError(f"{pin.name} at {pin.va:#x}: expected {pin.expected.hex()} found {live.hex()}")
        insns = decode_run(md, live, pin.va)
        text = "; ".join(f"{i.mnemonic} {i.op_str}".strip() for i in insns)
        if pin.role == "detour":
            n = steal_length(md, img.read(pin.va, 16), pin.va)
            if n != len(pin.expected) or pin.va != S.CHANCE_OF_PREGNANCY or n != S.CHANCE_OF_PREGNANCY_STEAL:
                raise SiteError(f"{pin.name}: steal length {n} does not match the pin ({len(pin.expected)})")
            overwritten.append((pin.name, pin.va, n))
        elif pin.role == "replace":
            if len(insns) != 1 or insns[0].size < 5 or is_relative(insns[0]):
                raise SiteError(f"{pin.name}: must be one non-relative instruction of 5+ bytes")
            overwritten.append((pin.name, pin.va, insns[0].size))
        elif pin.role == "retarget":
            i = insns[0]
            if (len(insns) != 1 or i.mnemonic != "call" or i.size != 5 or i.bytes[0] != 0xE8
                    or i.operands[0].type != X86_OP_IMM or i.operands[0].imm != S.CAN_START_NEXT_GENERATION):
                raise SiteError(f"{pin.name}: not `call {S.CAN_START_NEXT_GENERATION:#x}`")
            overwritten.append((pin.name, pin.va, 5))
        elif pin.role != "context":
            raise SiteError(f"{pin.name}: unknown role {pin.role}")
        facts.append(f"{pin.name} {pin.va:#x} [{pin.role}] {text}")

    # The DLL overwrites [va, va+n). A branch to va itself is fine (it hits the
    # new jmp/call); a branch to any later byte would execute half an
    # instruction.
    branches = img.direct_branch_targets()
    for name, va, n in overwritten:
        inside = [(hex(s), hex(t)) for s, t in branches if va < t < va + n]
        if inside:
            raise SiteError(f"{name}: branches land inside the overwritten bytes: {inside}")
        facts.append(f"{name}: no direct branch lands in {va + 1:#x}-{va + n - 1:#x}")

    callers = sorted(s for s, t in branches
                     if t == S.CAN_START_NEXT_GENERATION and img.read(s, 1)[0] in (0xE8, 0xE9)
                     and decode_run(md, img.read(s, 5), s))
    if tuple(callers) != tuple(sorted(S.NEXT_GENERATION_CALLSITES)):
        raise SiteError(f"CanStartNextGeneration callers changed: {[hex(c) for c in callers]}")
    chance_callers = sorted(s for s, t in branches
                            if t == S.CHANCE_OF_PREGNANCY and img.read(s, 1)[0] in (0xE8, 0xE9))
    if chance_callers != [0x49F5FA]:
        raise SiteError(f"ChanceOfPregnancy callers changed: {[hex(c) for c in chance_callers]}")
    for target in (S.CAN_START_NEXT_GENERATION, S.CHANCE_OF_PREGNANCY):
        if struct.pack("<I", target) in data:
            raise SiteError(f"{target:#x} is referenced by absolute address somewhere")
    facts.append("CanStartNextGeneration direct callers: " + ", ".join(hex(c) for c in callers))
    facts.append("ChanceOfPregnancy direct callers: 0x49f5fa")

    slot = struct.unpack("<I", img.read(S.INIT_SLOT, 4))[0]
    if slot != S.INIT_SLOT_EXPECTED:
        raise SiteError(f"theGame::Init vtable slot holds {slot:#x}")
    facts.append(f"theGame vtable slot 4 at {S.INIT_SLOT:#x} -> {slot:#x}")
    return facts


def render_header() -> str:
    lines = [
        "// GENERATED by runtime/tools/gen_sites.py from runtime/vf2_runtime_sites.py.",
        "// Do not edit. Every run is the exact vanilla Virtual Families 2 bytes; the DLL",
        "// installs nothing unless all of them match live memory.",
        "#pragma once",
        "",
        "struct VF2Pin { const char *name; unsigned va; unsigned len; const unsigned char *bytes; };",
        "",
    ]
    consts = {
        "CHANCE_OF_PREGNANCY": S.CHANCE_OF_PREGNANCY,
        "CHANCE_OF_PREGNANCY_STEAL": S.CHANCE_OF_PREGNANCY_STEAL,
        "COOLDOWN_STORE": S.COOLDOWN_STORE,
        "COOLDOWN_STORE_LEN": S.COOLDOWN_STORE_LEN,
        "COOLDOWN_RESUME": S.COOLDOWN_RESUME,
        "CAN_START_NEXT_GENERATION": S.CAN_START_NEXT_GENERATION,
        "COUNT_SURVIVING_CHILDREN": S.COUNT_SURVIVING_CHILDREN,
        "GET_RANDOM": S.GET_RANDOM,
        "TUTORIAL_TIP": S.TUTORIAL_TIP,
        "TUTORIAL_QUEUE": S.TUTORIAL_QUEUE,
        "VILLAGER_MANAGER": S.VILLAGER_MANAGER,
        "VILLAGER_ARRAY_OFFSET": S.VILLAGER_ARRAY_OFFSET,
        "VILLAGER_STRIDE": S.VILLAGER_STRIDE,
        "GAME_STATE_TRY_FOR_BABY_DEADLINE": S.GAME_STATE_TRY_FOR_BABY_DEADLINE,
    }
    for k, v in consts.items():
        lines.append(f"#define VF2_{k} 0x{v:X}u")
    lines.append("")
    lines.append("static const unsigned VF2_NEXT_GENERATION_CALLSITES[] = { "
                 + ", ".join(f"0x{c:X}u" for c in S.NEXT_GENERATION_CALLSITES) + " };")
    lines.append("")
    for pin in S.PINS:
        body = ", ".join(f"0x{b:02X}" for b in pin.expected)
        lines.append(f"static const unsigned char kPin_{pin.name}[] = {{ {body} }};")
    lines.append("")
    lines.append("static const VF2Pin VF2_PINS[] = {")
    for pin in S.PINS:
        lines.append(f'    {{ "{pin.name}", 0x{pin.va:X}u, {len(pin.expected)}u, kPin_{pin.name} }},')
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vanilla", type=Path, required=True, help="the vanilla Virtual Families 2.exe (read only)")
    ap.add_argument("--check", action="store_true", help="fail if the committed header is out of date")
    args = ap.parse_args()
    try:
        for fact in validate(args.vanilla.read_bytes()):
            print("ok:", fact)
    except SiteError as e:
        print("error:", e, file=sys.stderr)
        return 1
    text = render_header()
    if args.check:
        if HEADER.read_text() != text:
            print("error: vf2fun_sites.h is out of date", file=sys.stderr)
            return 1
        print("header up to date")
        return 0
    HEADER.write_text(text, newline="\n")
    print("wrote", HEADER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
