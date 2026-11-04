#!/usr/bin/env python3
"""Prove the Translations sites against the B200 executables, emit the companion DLL's headers and the room table.

    gen_b200_translations_sites.py --b200 "<core>\\Virtual Families 2 - B200.exe" [--write]
        [--also "<other variant or later build>.exe" ...]
    gen_b200_translations_sites.py --b200 <core> --limits-from <exe> [<exe> ...] [--write]

The B200 image is relocated and every matrix variant links to different addresses, so the DLL holds no address.
This tool

* validate(core): reads the CORE variant with pefile and decodes every pin with capstone. It refuses (SiteError)
  unless every pin is the pinned bytes and whole instructions, every pin the DLL searches for is found exactly once,
  every field the DLL reads (the table, its size, the index, the largest id, the manager's instance) is what the core
  variant has and is a relocated address where it is one, the three C runtime entries have at least 5 stolen bytes of
  whole, position-independent instructions, the table starts with {1, key, text, 0} and GetString and the template
  filler read the override at +0Ch;
* resolve(exe): the algorithm the DLL runs, in Python, on any executable;
* render_header(): the C header, a pure function of b200_translations_sites and the core executable;
* scan_limits(exe): every place the game copies one of its own strings into a fixed space (the same scan as the
  Virtual Families 1 Fun Patcher's tools/build_vf1_translation_limits.py), and render_limits(): src/
  vf2_translation_limits.json and runtime/native/b200tr/b200tr_limits.h.

A line the game hands to GetString and then to strncpy with a constant count n gets n - 1 bytes of room; one it
hands to sprintf, strncat or copies byte by byte may not be longer than the English; a line pushed as sprintf's
FORMAT is a printf format (a plain "%" of its translation is handed on as "%%"). Where the id cannot be told (it
comes from data) the DLL's guards on strncpy / strncat / sprintf cut a translated line there to its English length
(or n - 1), so such a copy never holds more than in the English game.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import b200_translations_sites as S  # noqa: E402
from gen_b200_history_sites import Exe, SiteError, _md, find_all, pin_mask  # noqa: E402

ROOT = RUNTIME.parent
HEADER = RUNTIME / "native" / "b200tr" / "b200tr_sites.h"
LIMITS_H = RUNTIME / "native" / "b200tr" / "b200tr_limits.h"
LIMITS_JSON = ROOT / "src" / "vf2_translation_limits.json"

for _p in S.PINS:                 # gen_b200_history_sites.pin_mask reads .skip
    _p.skip = 0


def mask_of(pin, exe: Exe) -> bytes:
    m = bytearray(pin_mask(pin, exe))
    for off, n in pin.wild:
        for k in range(n):
            m[off + k] = 1
    return bytes(m)


def locate(exe: Exe, core: Exe | None = None) -> dict[str, int]:
    """The DLL's search: every pin exactly once in the executable sections. The masks come from the core variant."""
    core = core or exe
    out = {}
    for pin in S.PINS:
        hits = find_all(exe.executable(), pin.bytes, mask_of(pin, core))
        if len(hits) != 1:
            raise SiteError(f"{pin.name}: found {len(hits)} times, not exactly once")
        out[pin.name] = hits[0]
    return out


def pin_fields(exe: Exe, loc: dict[str, int]) -> dict[str, int]:
    """TABLE, COUNT, INDEX, MAX_ID, INSTANCE as the DLL reads them from the located pins."""
    out: dict[str, int] = {}
    for pin in S.PINS:
        for name, (off, kind) in pin.fields.items():
            v = exe.u32(loc[pin.name] + off)
            if out.setdefault(name, v) != v:
                raise SiteError(f"{name}: the pins disagree ({out[name]:#x} vs {v:#x})")
    return out


def resolve(exe: Exe, core: Exe | None = None) -> dict[str, int]:
    """The DLL's derivation. {site: VA} for the three C runtime entries, GetString, the filler, the manager's Get,
    and TABLE / COUNT / INDEX / MAX_ID / INSTANCE."""
    loc = locate(exe, core)
    f = pin_fields(exe, loc)
    table_bytes = exe.read(f["TABLE"], 16)
    rec = struct.unpack("<IIII", table_bytes)
    if rec[0] != 1 or rec[3] != 0:
        raise SiteError("the first record is not {1, key, text, 0}")
    if not (1 <= f["COUNT"] <= 0x4000) or not (1 < f["MAX_ID"] <= 0x2000):
        raise SiteError("the table's size is not believable")
    out = dict(f)
    for pin in S.PINS:
        out[pin.name.upper()] = loc[pin.name]
    return out


def _calls(exe_bytes: bytes, va: int):
    return [(i.address, i) for i in _md().disasm(exe_bytes, va)]


def validate(exe_bytes: bytes) -> dict:
    """Prove the core variant; returns the located sites."""
    core = Exe(exe_bytes)
    if core.base != S.IMAGE_BASE:
        raise SiteError(f"image base {core.base:#x} is not {S.IMAGE_BASE:#x}")
    if not core.relocs:
        raise SiteError("the B200 image has no relocations: the ASLR handling would be untested")
    names = set()
    md = _md()
    for pin in S.PINS:
        if pin.name in names:
            raise SiteError(f"duplicate pin {pin.name}")
        names.add(pin.name)
        if core.read(pin.va, len(pin.bytes)) != pin.bytes:
            raise SiteError(f"{pin.name} at {pin.va:#x}: the executable's bytes differ from the pinned bytes")
        ins = list(md.disasm(pin.bytes, pin.va))
        if sum(i.size for i in ins) != len(pin.bytes):
            raise SiteError(f"{pin.name}: pinned bytes are not whole instructions")
        for name, (off, kind) in pin.fields.items():
            want = S.CORE_EXPECTED[name]
            if core.u32(pin.va + off) != want:
                raise SiteError(f"{pin.name}.{name}: {core.u32(pin.va + off):#x}, expected {want:#x}")
            if kind == "abs" and (pin.va + off) not in core.relocs:
                raise SiteError(f"{pin.name}.{name} is not a relocated address")
            if kind == "u32" and (pin.va + off) in core.relocs:
                raise SiteError(f"{pin.name}.{name} is relocated: it is not a plain constant")
        if pin.steal:
            if pin.steal < 5:
                raise SiteError(f"{pin.name}: fewer than 5 bytes stolen")
            n, taken = 0, []
            for i in ins:
                if n >= pin.steal:
                    break
                n += i.size
                taken.append(i)
            if n != pin.steal:
                raise SiteError(f"{pin.name}: the stolen {pin.steal} bytes end inside an instruction")
            for i in taken:
                if i.mnemonic in ("call", "jmp") or i.mnemonic.startswith("j") or i.mnemonic.startswith("loop") \
                        or i.mnemonic == "ret" or any(op.type == 3 and op.mem.base == 0 and op.mem.index == 0
                                                      for op in i.operands):
                    raise SiteError(f"{pin.name}: a stolen instruction is not position independent: {i.mnemonic}")
                # no stolen byte may be a relocated field
                for r in core.relocs:
                    if i.address <= r < i.address + i.size:
                        raise SiteError(f"{pin.name}: a stolen instruction holds a relocated field")
    by_name = {p.name: p for p in S.PINS}
    # GetString and the filler read the override at +0Ch and the text at +08h exactly as the DLL assumes
    for name, reg in (("get_string", "ecx"), ("fill_template", "ebx")):
        text = " ".join(f"{i.mnemonic} {i.op_str}" for i in md.disasm(by_name[name].bytes, by_name[name].va))
        for want in (f"mov {reg}, dword ptr [eax + {S.RECORD_OVERRIDE:#x}]", f"{S.RECORD_TEXT}]", "cmp dword ptr [eax], ecx"):
            if want not in text:
                raise SiteError(f"{name}: no {want!r}")
    # the table: {1, key, text, 0}; the first key is a name that starts with 'e'
    rec = struct.unpack("<IIII", core.read(S.STRING_TABLE, 16))
    if rec[0] != 1 or rec[3] != 0 or not core.cstr(rec[1]).startswith(b"e"):
        raise SiteError("the first record is not {1, 'e...', text, 0}")
    got = resolve(core)
    for name, want in (("GET_STRING", S.GET_STRING), ("FILL_TEMPLATE", S.FILL_TEMPLATE),
                       ("STRING_MANAGER_GET", S.STRING_MANAGER_GET), ("STRNCPY", S.STRNCPY), ("STRNCAT", S.STRNCAT),
                       ("SPRINTF", S.SPRINTF)):
        if got[name] != want:
            raise SiteError(f"{name}: derived {got[name]:#x}, expected {want:#x}")
    return got


def validate_variant(exe_bytes: bytes, core_bytes: bytes | None = None) -> dict[str, int]:
    core = Exe(core_bytes) if core_bytes else None
    return resolve(Exe(exe_bytes), core)


# ---------------------------------------------------------------- header
def render_header(core: Exe) -> str:
    def arr(b: bytes) -> str:
        return ", ".join(f"0x{x:02X}" for x in b)

    out = [
        "// GENERATED by runtime/tools/gen_b200_translations_sites.py from runtime/b200_translations_sites.py.",
        "// Do not edit. The DLL holds no game address: it searches the live executable for each pinned run",
        "// (mask 1 = wildcard: a relocated field, a call/jmp displacement or a table size), reads the table,",
        "// its size, the index and the manager's instance from them, and installs nothing unless every pin is",
        "// found exactly once and every field agrees.",
        "#pragma once",
        "",
        "typedef struct TrPin {",
        "    const char *name; unsigned len; const unsigned char *bytes; const unsigned char *mask;",
        "} TrPin;",
        "",
    ]
    for key in ("RECORD_SIZE", "RECORD_ID", "RECORD_KEY", "RECORD_TEXT", "RECORD_OVERRIDE", "MAX_LINE", "STATUS_MAGIC"):
        out.append(f"#define TR_{key} 0x{getattr(S, key):X}u")
    out.append(f'#define TR_GAME_TITLE_TEXT "{S.GAME_TITLE}"')
    out.append("")
    out.append("enum TrPinIndex {")
    for p in S.PINS:
        out.append(f"    TR_PIN_{p.name.upper()},")
    out.append("    TR_PIN_COUNT")
    out.append("};")
    out.append("")
    out.append("typedef struct TrField { unsigned pin; unsigned offset; } TrField;")
    for p in S.PINS:
        for name, (off, kind) in p.fields.items():
            out.append(f"#define TR_{p.name.upper()}_{name} {{ TR_PIN_{p.name.upper()}, {off}u }}")
    out.append("")
    for p in S.PINS:
        out.append(f"static const unsigned char tpin_{p.name}[] = {{ {arr(p.bytes)} }};")
        out.append(f"static const unsigned char tpinmask_{p.name}[] = {{ {arr(mask_of(p, core))} }};")
    out.append("")
    out.append("static const TrPin TR_PINS[] = {")
    for p in S.PINS:
        out.append(f'    {{ "{p.name}", {len(p.bytes)}u, tpin_{p.name}, tpinmask_{p.name} }},')
    out.append("};")
    out.append("")
    out.append("// the bytes the DLL steals from the entry of a C runtime function it guards")
    out.append("static const unsigned TR_STEAL[TR_PIN_COUNT] = { " +
               ", ".join(f"{p.steal}u" for p in S.PINS) + " };")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- the rooms
GET_STRING_WINDOW = 40


def scan_limits(exe_bytes: bytes, core_bytes: bytes | None = None) -> dict:
    """Every GetString call and what the code does with the line (see the module notes)."""
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    ex = Exe(exe_bytes)
    sites = resolve(ex, Exe(core_bytes) if core_bytes else None)
    GET, SPRINTF, STRNCPY, STRNCAT = sites["GET_STRING"], sites["SPRINTF"], sites["STRNCPY"], sites["STRNCAT"]
    base = ex.base
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    max_id = sites["MAX_ID"]
    text_sec = next(s for s in ex.sections if s[0] == ".text")
    t_va, code = text_sec[1], text_sec[2]
    img = {n: (va, raw) for n, va, raw, _c, _v in ex.sections}

    def rd(va, n):
        return ex.read(va, n)

    calls = []
    for m in re.finditer(rb"\xE8", code):
        if m.start() + 5 > len(code):
            continue
        at = t_va + m.start()
        if (at + 5 + struct.unpack_from("<i", code, m.start() + 1)[0]) & 0xFFFFFFFF == GET:
            calls.append(at)
    limit: dict[int, int] = {}
    english_only: set[int] = set()
    formats: set[int] = set()
    unresolved: list[dict] = []
    copies = 0

    def decode_before(at: int):
        for back in range(40, 0, -1):
            decoded = list(md.disasm(rd(at - back, back), at - back))
            if decoded and decoded[-1].address + decoded[-1].size == at and sum(i.size for i in decoded) == back:
                return decoded
        return []

    def count_before(at: int):
        """strncpy's count when the compiler pushed it BEFORE the GetString call (the patches' generated code:
        `push 37h; push id; call Get; mov ecx, eax; call GetString; push eax; push dst; call strncpy`): the immediate
        push right before the id push, with no call between them; None otherwise."""
        before = decode_before(at)
        pushes = [k for k, i in enumerate(before) if i.mnemonic == "push"]
        if len(pushes) < 2:
            return None
        count, id_push = before[pushes[-2]], before[pushes[-1]]
        if not (count.op_str.startswith("0x") or count.op_str.isdigit()):
            return None
        if any(i.mnemonic == "call" for i in before[pushes[-2]:pushes[-1]]):
            return None
        return int(count.op_str, 0)

    def ids_at(at: int):
        before = decode_before(at)
        if not before:
            return None
        pushes = [i for i in before if i.mnemonic == "push"]
        if not pushes:
            return None
        last = pushes[-1]
        if last.op_str.startswith("0x") or last.op_str.isdigit():
            return [int(last.op_str, 0)]
        reg = last.op_str
        earlier = before[:before.index(last)]
        if len(earlier) >= 2 and earlier[-1].mnemonic == "add" and earlier[-1].op_str.startswith(reg + ", 0x") \
                and earlier[-2].mnemonic == "sbb" and earlier[-2].op_str == f"{reg}, {reg}":
            n = int(earlier[-1].op_str.split(", ")[1], 16)
            return [n - 1, n]
        walk = [i for i in earlier if not (i.mnemonic in ("cmp", "test", "push") or i.mnemonic.startswith("j"))]
        src = reg
        if walk and walk[-1].mnemonic == "mov" and re.fullmatch(reg + r", (e[a-d]x)", walk[-1].op_str):
            src = walk[-1].op_str.split(", ")[1]
            walk = walk[:-1]
        if len(walk) >= 2 and walk[-1].mnemonic == "add" and walk[-1].op_str.startswith(src + ", 0x") \
                and walk[-2].mnemonic.startswith("set"):
            n = int(walk[-1].op_str.split(", ")[1], 16)
            return [n, n + 1]
        for i in reversed(earlier):
            if i.mnemonic == "mov" and re.fullmatch(reg + r", (0x[0-9a-f]+|\d+)", i.op_str):
                return [int(i.op_str.split(", ")[1], 0)]
            mm = re.fullmatch(reg + r", dword ptr \[(\w+)\*4 \+ (0x[0-9a-f]+)\]", i.op_str) if i.mnemonic == "mov" else None
            if mm:
                table = int(mm.group(2), 16)
                found = []
                for k in range(64):
                    try:
                        v = ex.u32(table + 4 * k)
                    except SiteError:
                        break
                    if not 1 <= v <= max_id:
                        break
                    found.append(v)
                return found or None
            if i.op_str.startswith(reg + ","):
                return None
        return None

    for at in calls:
        try:
            after = list(md.disasm(rd(at, 6 * GET_STRING_WINDOW), at))[1:GET_STRING_WINDOW]
        except SiteError:
            after = list(md.disasm(rd(at, 32), at))[1:]
        kind, count, copy_at, is_format = None, None, None, False
        pushed: list = []
        for k, i in enumerate(after):
            if i.mnemonic in ("ret", "int3"):
                break
            if i.mnemonic == "push":
                pushed.append(i.op_str)
            if i.mnemonic == "call":
                target = int(i.op_str, 16) if i.op_str.startswith("0x") else None
                copy_at = (i.address, target)
                if target == STRNCPY:
                    imm = next((p for p in reversed(pushed[:-2]) if p.startswith("0x") or p.isdigit()), None)
                    early = count_before(at) if len(pushed) == 2 else None
                    if len(pushed) >= 3 and (pushed[-3].startswith("0x") or pushed[-3].isdigit()):
                        kind, count = "strncpy", int(pushed[-3], 0)
                    elif imm is not None:
                        kind, count = "strncpy", int(imm, 0)
                    elif early is not None:
                        kind, count = "strncpy", early
                    else:
                        kind = "english"
                    break
                if target in (SPRINTF, STRNCAT):
                    kind = "english"
                    is_format = target == SPRINTF and len(pushed) == 2 and pushed[0] == "eax"
                    break
                if target == GET or k > 12:
                    pushed = []
                    continue
                pushed = []
            if i.mnemonic == "mov" and re.match(r"byte ptr \[.*\], [a-d]l$", i.op_str) and k \
                    and after[k - 1].mnemonic == "mov" and re.match(r"[a-d]l, byte ptr \[", after[k - 1].op_str):
                kind = "english"
                break
        if kind is None:
            continue
        copies += 1
        ids = ids_at(at)
        if ids is None:
            unresolved.append({"kind": kind, "count": count})
            continue
        for sid in ids:
            if is_format:
                formats.add(sid)
            if kind == "strncpy":
                limit[sid] = min(limit.get(sid, 1 << 30), count - 1)
            else:
                english_only.add(sid)
    rooms, unproved = scan_sprintf_rooms(ex, sites, md, t_va, code)
    return {"get_string_calls": len(calls), "copies": copies, "strncpy_room": limit,
            "english_length": english_only, "format": formats, "unresolved": len(unresolved),
            "sprintf_room": rooms, "sprintf_unproved": unproved}


PROLOGUE = b"\x55\x8B\xEC"           # push ebp; mov ebp, esp


def frame_space(code: bytes, off: int, x: int) -> int | None:
    """The bytes a stack buffer at [ebp - x] may hold in the function around code offset `off`: up to the nearest
    other [ebp - k] (k < x) the function's bytes could address, else up to ebp. Every byte of the function is read
    as a possible ModRM [ebp + disp8 / disp32] (a superset of the real references: a false one only makes the room
    smaller). The function runs from the last `push ebp; mov ebp, esp` before `off` to the next one; None without."""
    def entry(at: int) -> bool:
        # a function's first instruction: aligned to 16 bytes after the padding or the `ret` of the one before
        # (bytes 55 8B EC inside an instruction would otherwise cut the function short)
        return at % 16 == 0 and at > 0 and (code[at - 1] in (0xCC, 0xC3, 0x90) or code[at - 3] == 0xC2)

    start = code.rfind(PROLOGUE, 0, off)
    while start > 0 and not entry(start):
        start = code.rfind(PROLOGUE, 0, start)
    if start <= 0:
        return None
    end = code.find(PROLOGUE, off)
    while end >= 0 and not entry(end):
        end = code.find(PROLOGUE, end + 1)
    body = code[start:end if end >= 0 else len(code)]
    ks = set()
    for i in range(len(body) - 1):
        b = body[i]
        if b & 0xC7 == 0x45:
            d = struct.unpack_from("<b", body, i + 1)[0]
        elif b & 0xC7 == 0x85 and i + 5 <= len(body):
            d = struct.unpack_from("<i", body, i + 1)[0]
        else:
            continue
        if -0x100000 < d < 0:
            ks.add(-d)
    above = [k for k in ks if k < x]
    return x - (max(above) if above else 0)


def scan_sprintf_rooms(ex, sites: dict, md, t_va: int, code: bytes) -> tuple[dict, set]:
    """Every sprintf call whose FORMAT is a literal the code pushes (push imm32, a text outside the table) and whose
    destination is a buffer of the caller's frame (`lea reg, [ebp - x]; push reg` as the last push): {format text:
    the smallest frame_space over its calls}. A format with any call whose destination cannot be told this way, or
    whose text is also a line of the table (the linker may fold the two into one address), is in `unproved`."""
    sprintf = sites["SPRINTF"]
    table_texts = set()
    for k in range(sites["COUNT"]):
        try:
            rec = struct.unpack("<IIII", ex.read(sites["TABLE"] + 16 * k, 16))
        except SiteError:
            break
        if rec[2]:
            t = ex.cstr(rec[2])
            if t is not None:
                table_texts.add(t)
    rooms: dict[bytes, int] = {}
    unproved: set[bytes] = set()
    for m in re.finditer(rb"\xE8", code):
        if m.start() + 5 > len(code):
            continue
        at = t_va + m.start()
        if (at + 5 + struct.unpack_from("<i", code, m.start() + 1)[0]) & 0xFFFFFFFF != sprintf:
            continue
        before = []
        for back in range(64, 0, -1):
            d = list(md.disasm(code[m.start() - back:m.start()], at - back))
            if d and d[-1].address + d[-1].size == at and sum(i.size for i in d) == back:
                before = d
                break
        pushes = [k for k, i in enumerate(before) if i.mnemonic == "push"]
        if len(pushes) < 2:
            continue
        dst, fmt = before[pushes[-1]], before[pushes[-2]]
        if not fmt.op_str.startswith("0x") or fmt.size != 5:
            continue
        text = ex.cstr(int(fmt.op_str, 16))
        if text is None:
            continue
        room = None
        if re.fullmatch(r"e(ax|bx|cx|dx|si|di)", dst.op_str):
            for i in reversed(before[:pushes[-1]]):
                mm = re.fullmatch(dst.op_str + r", \[ebp - (0x[0-9a-f]+)\]", i.op_str) if i.mnemonic == "lea" else None
                if mm:
                    room = frame_space(code, m.start(), int(mm.group(1), 16))
                    break
                if i.op_str.startswith(dst.op_str + ",") or i.mnemonic in ("call", "pop", "xchg") \
                        or i.mnemonic.startswith("j"):
                    break
        if room is None or text in table_texts:
            unproved.add(text)
        else:
            rooms[text] = min(rooms.get(text, 1 << 30), room)
    return rooms, unproved


# The line the program parses: never translated (the decimal point numbers are written with).
NEVER = {36: "the decimal point (eString_Decimal): numbers are written with it"}


def merge_limits(scans: list[dict]) -> dict:
    limit: dict[int, int] = {}
    english: set[int] = set()
    formats: set[int] = set()
    for s in scans:
        for k, v in s["strncpy_room"].items():
            limit[k] = min(limit.get(k, 1 << 30), v)
        english |= s["english_length"]
        formats |= s["format"]
    sprintf_room: dict[bytes, int] = {}
    unproved: set[bytes] = set()
    for s in scans:
        unproved |= s["sprintf_unproved"]
        for k, v in s["sprintf_room"].items():
            sprintf_room[k] = min(sprintf_room.get(k, 1 << 30), v)
    # only a format every executable proves, and only one a translated line can reach as an argument (%s)
    sprintf_room = {k: v for k, v in sprintf_room.items()
                    if k not in unproved and b"%s" in k and all(k in s["sprintf_room"] for s in scans)}
    return {
        "comment": "Written by runtime/tools/gen_b200_translations_sites.py from the B200 executables; do not edit.",
        "executables": len(scans),
        "get_string_calls": max(s["get_string_calls"] for s in scans),
        "copies": max(s["copies"] for s in scans),
        "unresolved_copies": max(s["unresolved"] for s in scans),
        "strncpy_room": {str(k): v for k, v in sorted(limit.items())},
        "english_length": sorted(english),
        "never": {str(k): v for k, v in sorted(NEVER.items())},
        "format": sorted(formats),
        # sprintf formats the game's code pushes itself, whose every call writes into a buffer of its own frame:
        # the bytes that buffer holds (the smallest over the calls and the executables), so a translated %s
        # argument may make the text that long, not only as long as the English (guard_sprintf)
        "sprintf_room": {k.decode("cp1252"): v for k, v in sorted(sprintf_room.items())},
    }


def render_limits_header(data: dict) -> str:
    rows = [f"    {{ {int(k)}, {v} }}," for k, v in data["strncpy_room"].items()]
    english = ", ".join(str(v) for v in data["english_length"])
    never = ", ".join(data["never"].keys())
    return "\n".join([
        "/* Written by runtime/tools/gen_b200_translations_sites.py from the B200 executables; do not edit. */",
        "#pragma once",
        "typedef struct { unsigned short id; unsigned short room; } b200tr_room;",
        "static const b200tr_room B200TR_STRNCPY_ROOM[] = {\n" + "\n".join(rows) + "\n    { 0, 0 }\n};",
        f"static const unsigned short B200TR_ENGLISH_LENGTH[] = {{ {english}, 0 }};",
        f"static const unsigned short B200TR_NEVER[] = {{ {never}, 0 }};",
        "/* The lines the game hands sprintf as its FORMAT: a plain '%' of their translation is written as \"%%\". */",
        f"static const unsigned short B200TR_FORMAT[] = {{ {', '.join(str(v) for v in data['format'])}, 0 }};",
        "/* sprintf formats the game's code pushes itself and the bytes of the frame buffer every call writes into. */",
        "typedef struct { const char *format; unsigned short room; } b200tr_sprintf_room;",
        "static const b200tr_sprintf_room B200TR_SPRINTF_ROOM[] = {\n"
        + "".join(f"    {{ {_c_text(k)}, {v} }},\n" for k, v in data.get("sprintf_room", {}).items())
        + "    { 0, 0 }\n};",
        "",
    ])


def _c_text(s: str) -> str:
    return '"' + "".join(c if 0x20 <= ord(c) < 0x7F and c not in '"\\' else f"\\x{ord(c):02x}\"\"" for c in s) + '"'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b200", required=True, help="path to the CORE variant's Virtual Families 2 - B200.exe")
    ap.add_argument("--also", action="append", default=[], help="another variant's executable to prove")
    ap.add_argument("--limits-from", nargs="*", default=None, help="executables to scan for the room table")
    ap.add_argument("--write", action="store_true", help="rewrite the committed files")
    args = ap.parse_args(argv)
    core_bytes = Path(args.b200).read_bytes()
    validate(core_bytes)
    for other in args.also:
        validate_variant(Path(other).read_bytes(), core_bytes)
    text = render_header(Exe(core_bytes))
    status = 0
    if args.write:
        HEADER.parent.mkdir(parents=True, exist_ok=True)
        HEADER.write_text(text, newline="\n")
        print(f"wrote {HEADER}")
    elif HEADER.read_text() != text:
        print("the committed header differs from a fresh render")
        status = 1
    if args.limits_from:
        data = merge_limits([scan_limits(Path(p).read_bytes(), core_bytes) for p in args.limits_from])
        j = json.dumps(data, indent=1) + "\n"
        h = render_limits_header(data)
        if args.write:
            LIMITS_JSON.parent.mkdir(parents=True, exist_ok=True)
            LIMITS_JSON.write_text(j, encoding="utf-8", newline="\n")
            LIMITS_H.write_text(h, encoding="utf-8", newline="\n")
            print(f"wrote {LIMITS_JSON} and {LIMITS_H}")
        elif LIMITS_JSON.read_text(encoding="utf-8") != j or LIMITS_H.read_text(encoding="utf-8") != h:
            print("the committed limits differ from a fresh scan")
            status = 1
        print(f"{data['get_string_calls']} GetString calls, {data['copies']} copies, {len(data['strncpy_room'])} "
              f"strncpy lines, {len(data['english_length'])} English-length lines, {len(data['format'])} formats, "
              f"{data['unresolved_copies']} unresolved (guarded at run time)")
    print(f"{len(S.PINS)} pins proved on the core variant, {len(args.also)} other variants resolved")
    return status


if __name__ == "__main__":
    sys.exit(main())
