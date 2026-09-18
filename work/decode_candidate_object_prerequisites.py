# -*- coding: utf-8 -*-
"""Resolve behaviour -> object prerequisite through InitAI's two-level switch.

Third attempt. The two earlier ones failed and are recorded in the PR:
  1. assumed $LN249 slot index == behaviour id (it is a CASE NUMBER)
  2. assumed InitAI lived in section #2 and read a symbol table instead

InitAI is in its own COMDAT section, so rather than trust any section header
this locates $LN205 by SIGNATURE: the first 18 bytes the text dump renders
(00 01 02 BE 03 BE BE BE BE 04 BE 05 BE BE BE 06 07 08). That anchors the
section-relative address 0x4818 to a concrete file offset, and every other
section-relative address follows from the same base.

The dispatch, read from the disassembly at InitAI+0x250:

    lea   eax,[ebx-2]                 ; index = behaviour id - 2
    cmp   eax,197h                    ; 0x198 entries
    ja    $LN207                      ; default, no per-behaviour fields
    movzx eax,byte ptr $LN205[eax]    ; byte map -> CASE NUMBER
    jmp   dword ptr $LN249[eax*4]     ; case number -> case block

Cross-checks before any result is reported, so a wrong base cannot produce
plausible-looking rows the way attempt 1 did:
  A. the signature must be unique in the file
  B. every byte-map entry must index a real case or be the default 0xBE
  C. the treadmill donors must resolve to 0x04 and the pool donor to 0x36 --
     independently known from the owner's in-play report and the #343 review
"""
import os
import re
import sys

SIG = bytes([0x00, 0x01, 0x02, 0xBE, 0x03, 0xBE, 0xBE, 0xBE, 0xBE,
             0x04, 0xBE, 0x05, 0xBE, 0xBE, 0xBE, 0x06, 0x07, 0x08])
MAP_REL = 0x4818
TABLE_REL = 0x451C
BIAS = 2
COUNT = 0x198
DEFAULT_CASE = 0xBE
_HERE = os.path.dirname(os.path.abspath(__file__))
OBJ = os.path.join(_HERE, "desktop_obj_files", "Villager.obj")
DISASM = os.path.join(_HERE, "Villager.disasm.txt")
# dumpbin /RELOCATIONS output for Villager.obj, checked in beside this
# script so the decode is reproducible without the MSVC toolchain.
RELOCS = os.path.join(_HERE, "Villager_relocations.txt")


def main():
    blob = open(OBJ, "rb").read()

    # --- A. unique signature -> section base
    hits = []
    start = 0
    while True:
        i = blob.find(SIG, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    if len(hits) != 1:
        print("signature is not unique (%d hits); cannot anchor" % len(hits))
        return 1
    base = hits[0] - MAP_REL
    print("$LN205 at file 0x%X  ->  section base 0x%X" % (hits[0], base))

    byte_map = list(blob[hits[0]:hits[0] + COUNT])
    print("byte map read: %d entries" % len(byte_map))

    # --- case number -> label, from relocations
    case_to_label = {}
    for line in open(RELOCS, encoding="utf-8", errors="replace"):
        m = re.match(r"\s+([0-9A-F]{8})\s+DIR32\s+\S+\s+\S+\s+(\$LN\d+)\s*$", line)
        if not m:
            continue
        off = int(m.group(1), 16)
        if off < TABLE_REL or (off - TABLE_REL) % 4:
            continue
        case_to_label[(off - TABLE_REL) // 4] = m.group(2)
    print("cases resolved from relocations: %d" % len(case_to_label))

    # --- B. every map entry must be a real case or the default
    unknown = sorted({c for c in byte_map
                      if c != DEFAULT_CASE and c not in case_to_label})
    if unknown:
        print("byte map references %d case numbers with no relocation: %s"
              % (len(unknown), [hex(c) for c in unknown[:8]]))
        return 1
    print("every byte-map entry resolves (or is the 0xBE default)")

    # --- label -> +0xC4 write
    text = open(DISASM, encoding="utf-8", errors="replace").read()
    body = text[text.index("?InitAI@CVillager@@QAEXXZ"):]
    lines = body.splitlines()
    label_at = {}
    for i, line in enumerate(lines):
        m = re.match(r"^(\$LN\d+):", line)
        if m:
            label_at[m.group(1)] = i

    def prereq(label):
        i = label_at.get(label)
        if i is None:
            return None
        for line in lines[i + 1:]:
            if re.match(r"^\$LN\d+:", line):
                break
            m = re.search(
                r"mov\s+dword ptr \[esi\+(?:eax|edi)\+6C7Ch\],([0-9A-Fa-f]+)h?",
                line)
            if m:
                return int(m.group(1), 16)
        return None

    def lookup(behaviour):
        index = behaviour - BIAS
        if index < 0 or index >= COUNT:
            return None, None, None
        case = byte_map[index]
        if case == DEFAULT_CASE:
            return case, "(default)", None
        label = case_to_label.get(case)
        return case, label, (prereq(label) if label else None)

    # --- C. the control donors, known independently
    CONTROLS = [(0x049, 0x04, "Treadmill walk"),
                (0x0E0, 0x04, "Treadmill run"),
                (0x099, 0x36, "PlayingPooltable")]
    print()
    print("CONTROL CHECK -- these three are known from the owner's in-play")
    print("report and the #343 review; if they do not match, the decode is wrong")
    print("-" * 74)
    control_ok = True
    for bid, expect, name in CONTROLS:
        case, label, value = lookup(bid)
        got = hex(value) if value else "none"
        ok = value == expect
        control_ok = control_ok and ok
        print("  0x%03X %-18s case %-4s %-10s got %-7s expect %-6s %s"
              % (bid, name, ("%02X" % case) if case is not None else "-",
                 label or "-", got, hex(expect), "OK" if ok else "MISMATCH"))
    if not control_ok:
        print()
        print("CONTROLS FAILED -- not reporting the zeroes. The decode is")
        print("still wrong somewhere, and a table that disagrees with")
        print("confirmed in-play behaviour is not evidence.")
        return 1

    ZEROES = [(0x034, "North shower        -> 0x016"),
              (0x076, "WateringRoses       -> 0x077"),
              (0x0A4, "BathroomSink        -> 0x0A5..0x0A8"),
              (0x04A, "WorkingOut          -> 0x0B3 Home Gym"),
              (0x08B, "yoga donor          -> 0x0B4 Yoga"),
              (0x047, "WorkKitchenDispatch -> 0x048")]
    print()
    print("THE SIX ZERO-PINNED DONORS")
    print("-" * 74)
    bad = []
    for bid, name in ZEROES:
        case, label, value = lookup(bid)
        got = hex(value) if value else "none (zero)"
        print("  0x%03X %-40s case %-4s %-10s %s"
              % (bid, name, ("%02X" % case) if case is not None else "-",
                 label or "-", got))
        if value:
            bad.append((bid, value))

    print()
    if bad:
        print("PINNING 0 IS WRONG FOR:")
        for bid, v in bad:
            print("  0x%03X carries %s -- passing 0 KEEPS that gate on the clone"
                  % (bid, hex(v)))
        return 1
    print("VERIFIED: all six donors carry NO object prerequisite, so passing 0")
    print("writes nothing and inherits nothing. The pinned zeroes are correct,")
    print("and the three named-object overrides are necessary. Controls passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
