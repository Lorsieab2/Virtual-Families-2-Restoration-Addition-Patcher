#!/usr/bin/env python3
"""Prove the Title Screen Player Name Box sites against the B200 executables and emit the companion DLL's header.

    gen_b200_titlebox_sites.py --b200 "<core>\\Virtual Families 2 - B200.exe" [--write] [--also "<other>.exe" ...]

The B200 image is relocated and each of the 32 matrix variants links to different addresses, so the DLL holds no
address. This tool

* validate(core): reads the CORE variant with pefile and decodes every pin with capstone, refusing (SiteError)
  unless the bytes are the pinned bytes and whole instructions, the cross-checks hold (the text control's fields
  the DLL reads, Draw's justification, ldwScene::Draw's order, the colour FillRect takes, the name control's
  field, the RTTI chain of theMenuScene's vtable and the slot the DLL replaces), and every address constant has
  evidence in the pins;
* build_model(core): the wildcard masks, which pins are searched for and which hang off an anchor pin, and every
  derivation of each address constant;
* resolve(exe, model): the DLL's algorithm in Python, including the RTTI search for theMenuScene's vtable;
* render_header(): the C header, a pure function of b200_titlebox_sites and the core executable.

The pin/model/resolve machinery is gen_b200_refresh_sites' (the R Refreshes the Store DLL, one vtable slot too).
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
import b200_titlebox_sites as S  # noqa: E402
import gen_b200_refresh_sites as R  # noqa: E402

HEADER = RUNTIME / "native" / "b200titlebox" / "b200titlebox_sites.h"
SiteError = R.SiteError
Exe = R.Exe
_md = R._md
pin_mask = R.pin_mask
find_all = R.find_all
_calls = R._calls
MIN_INFORMATIVE = R.MIN_INFORMATIVE
MAX_ANCHOR_DISTANCE = R.MAX_ANCHOR_DISTANCE


class Model(R.Model):
    pass


def build_model(core: Exe) -> Model:
    """gen_b200_refresh_sites.build_model over this feature's pins and constants."""
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
                continue
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
    return R.locate(exe, model)


def menu_vtable(exe: Exe) -> int:
    """The DLL's RTTI search: the one type descriptor named .?AVtheMenuScene@@, the one complete object locator at
    offset 0 pointing to it, the one vtable pointing to that locator."""
    name = b".?AV" + S.MENU_CLASS.encode() + b"@@\0"
    hits = []
    for _n, va, raw, _c, _vs in exe.data_sections():
        j = raw.find(name)
        while j >= 0:
            hits.append(va + j)
            j = raw.find(name, j + 1)
    if len(hits) != 1:
        raise SiteError(f"theMenuScene's type descriptor name is found {len(hits)} times")
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
        raise SiteError(f"{len(cols)} complete object locators at offset 0 for theMenuScene")
    vts = []
    for _n, va, raw, _c, _vs in rodata:
        for off in range(0, len(raw) - 3, 4):
            if struct.unpack_from("<I", raw, off)[0] == cols[0]:
                vts.append(va + off + 4)
    if len(vts) != 1:
        raise SiteError(f"{len(vts)} vtables point to theMenuScene's locator")
    return vts[0]


def resolve(exe: Exe, model: Model) -> dict[str, int]:
    """The DLL's algorithm. Returns {constant: VA in this executable}, plus MENU_SLOT_DRAW_SCENE."""
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
    slot = menu_vtable(exe) + 4 * S.DRAW_SCENE_VSLOT
    if exe.u32(slot) != value["MENU_DRAW_SCENE"]:
        raise SiteError("theMenuScene's DrawScene slot does not point to the pinned DrawScene")
    value["MENU_SLOT_DRAW_SCENE"] = slot
    return value


def _operands(pin):
    calls, values, texts = set(), set(), set()
    for i in _md().disasm(pin.bytes, pin.va):
        texts.add(f"{i.mnemonic} {i.op_str}")
        if i.mnemonic in ("call", "jmp") and i.operands and i.operands[0].type == X86_OP_IMM:
            calls.add(i.operands[0].imm)
        for op in i.operands:
            if op.type == X86_OP_IMM and i.mnemonic not in ("call", "jmp") and not i.mnemonic.startswith("j"):
                values.add(op.imm & 0xFFFFFFFF)
            elif op.type == X86_OP_MEM:
                values.add(op.mem.disp & 0xFFFFFFFF)
    return calls, values, texts


def _n(v: int) -> str:
    """An operand as capstone prints it (decimal below 10)."""
    return str(v) if v < 10 else hex(v)


def _cross_checks():
    """pin name -> (call targets that must appear, operands that must appear, instructions that must appear)."""
    return {
        "menu_draw_scene": ({S.DRAW_CELL, S.HAS_MENU_LOGO, S.GRAPHICS_GET, S.GET_IMAGE_GRID, S.GET_CELL_RECT},
                            {S.BACKGROUND_IMAGE}, {"ret "}),
        "text_draw_body": ({S.GAME_WINDOW_GET, S.SCENE_GET_BOUNDS, S.FILL_RECT, S.WINDOW_GET_FONT, S.SET_FONT,
                            S.FONT_GET_HEIGHT, S.FONT_GET_WIDTH},
                           {S.TEXT_SHOWN, S.TEXT_SCENE, S.TEXT_LEFT, S.TEXT_FONT, S.TEXT_COUNT_SET, S.TEXT_LENGTH,
                            S.TEXT_STRING, S.TEXT_SCALE, S.TEXT_OFFSET_Y, S.TEXT_TOP},
                           {f"cmp byte ptr [esi + {S.TEXT_SHOWN:#x}], 0", f"mov ecx, dword ptr [esi + {S.TEXT_SCENE:#x}]",
                            f"mov edi, dword ptr [esi + {S.TEXT_FONT:#x}]",
                            f"cmp byte ptr [esi + {S.TEXT_COUNT_SET:#x}], 0",
                            f"mov ebx, dword ptr [esi + {S.TEXT_LENGTH:#x}]",
                            f"mov ebx, dword ptr [esi + {S.TEXT_STRING:#x}]",
                            f"movss xmm0, dword ptr [esi + {S.TEXT_SCALE:#x}]",
                            f"mov eax, dword ptr [esi + {S.TEXT_OFFSET_Y:#x}]",
                            f"add eax, dword ptr [esi + {S.TEXT_TOP:#x}]",
                            "push 0", "cvttss2si eax, xmm0", f"push dword ptr [esi + {S.TEXT_STRING:#x}]"}),
        "text_draw": ({S.DRAW_STRING, S.GET_MILLISECONDS},
                      {S.TEXT_JUSTIFY, S.TEXT_INSET, S.TEXT_RIGHT, S.TEXT_EDITABLE},
                      {f"mov eax, dword ptr [esi + {S.TEXT_JUSTIFY:#x}]",
                       f"mov edi, dword ptr [esi + {S.TEXT_RIGHT:#x}]", f"sub edi, dword ptr [esi + {S.TEXT_INSET:#x}]",
                       f"mov edi, dword ptr [esi + {S.TEXT_INSET:#x}]", f"add edi, dword ptr [esi + {_n(S.TEXT_LEFT)}]",
                       "sar edi, 1", f"cmp byte ptr [esi + {S.TEXT_EDITABLE:#x}], 0"}),
        "fill_rect_color": ({S.FILL_RECT_IMPL}, set(), {"shr edx, 0x18", "ret 8"}),
        "scene_draw": ({S.SCENE_IS_ACTIVE, S.DRAW_CONTROLS, S.DRAW_HINTS}, set(),
                       {f"call dword ptr [eax + {4 * S.DRAW_SCENE_VSLOT:#x}]", "call dword ptr [eax + 0x1c]"}),
        "draw_controls_and_hints": (set(), {S.SCENE_IMPL_FIELD, S.SCENE_CONTROLS_FIELD},
                                    {f"mov esi, dword ptr [ecx + {_n(S.SCENE_IMPL_FIELD)}]",
                                     f"mov esi, dword ptr [esi + {S.SCENE_CONTROLS_FIELD:#x}]",
                                     "mov ecx, dword ptr [esi]", "mov esi, dword ptr [esi + 4]"}),
        "add_control": ({S.OPERATOR_NEW, S.SCENE_IS_ACTIVE}, {S.SCENE_CONTROLS_FIELD}, set()),
        "text_control_ctor": ({S.HINT_CONTROL_CTOR, S.OPERATOR_NEW, S.TEXT_IMPL_CTOR}, {S.CONTROL_IMPL_FIELD},
                              {f"mov dword ptr [esi + {S.CONTROL_IMPL_FIELD:#x}], eax"}),
        "update_show_player_body": ({S.GET_CONTROL, S.TEXT_SET_TEXT},
                                    {S.NAME_CONTROL_ID_FIELD, S.GS_PLAYER_COUNT, S.GS_PLAYER_NAME, S.NAME_CONTROL_FIELD},
                                    {f"mov ecx, dword ptr [ebx + {S.NAME_CONTROL_FIELD:#x}]"}),
        "hint_draw_box": (set(), {(-S.HINT_BOX_MARGIN) & 0xFFFFFFFF, S.HINT_BOX_MARGIN},
                          {f"add eax, -{S.HINT_BOX_MARGIN}", f"add eax, {S.HINT_BOX_MARGIN}",
                           "add eax, dword ptr [ebx + 0x44]", "add eax, dword ptr [ebx + 0x48]"}),
        "hint_set_text_rect": (set(), set(),
                               {f"add dword ptr [esi + 0x20], -{S.HINT_TEXT_MARGIN}",
                                f"add dword ptr [esi + 0x28], {S.HINT_TEXT_MARGIN}",
                                f"add dword ptr [esi + 0x24], -{S.HINT_TEXT_MARGIN}",
                                f"add dword ptr [esi + 0x2c], {S.HINT_TEXT_MARGIN}"}),
        "menu_name_control": ({S.TEXT_CONTROL_CTOR, S.TEXT_SET_COLORS},
                              {S.NAME_CONTROL_X, S.NAME_CONTROL_Y, S.NAME_CONTROL_FIELD, S.NAME_CONTROL_ID_FIELD},
                              {f"mov dword ptr [edi + {S.NAME_CONTROL_FIELD:#x}], eax", "push 1", "push 0"}),
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
    for name, (calls, values, texts) in _cross_checks().items():
        got_calls, got_values, got_texts = _operands(by_name[name])
        for want in calls:
            if want not in got_calls:
                raise SiteError(f"{name}: no call/jmp to {want:#x}")
        for want in values:
            if (want & 0xFFFFFFFF) not in got_values:
                raise SiteError(f"{name}: no operand {want:#x}")
        for want in texts:
            if not any(t == want or t.startswith(want) for t in got_texts):
                raise SiteError(f"{name}: no instruction {want!r}")
    # The DLL's DrawScene replacement calls the stock one as thiscall with no argument: it ends in a plain ret.
    if by_name["menu_draw_scene"].bytes[-1:] != b"\xC3" or b"\xC2" in by_name["menu_draw_scene"].bytes[-3:-2]:
        raise SiteError("theMenuScene::DrawScene does not end in a plain ret")
    # The body pin starts right after the 7 bytes a Unicode text DLL may replace, which are the stock prologue.
    if core.read(S.TEXT_DRAW, 7) != bytes.fromhex("558BEC83EC3856") or by_name["text_draw_body"].va != S.TEXT_DRAW + 7:
        raise SiteError("the text box's Draw does not start with the 7-byte prologue the body pin skips")
    if by_name["text_draw"].bytes[7:] [:len(by_name["text_draw_body"].bytes)] != by_name["text_draw_body"].bytes:
        raise SiteError("the two Draw pins disagree")
    # GetWidth (ret 8), GetHeight (ret 4), GetBounds (ret 4), FillRect (ret 8): the DLL's call frames.
    for name, va, ret in (("GetWidth", S.FONT_GET_WIDTH, b"\xC2\x08\x00"), ("GetHeight", S.FONT_GET_HEIGHT, b"\xC2\x04\x00"),
                          ("GetBounds", S.SCENE_GET_BOUNDS, b"\xC2\x04\x00")):
        body = core.read(va, 0xB0)
        if ret not in body:
            raise SiteError(f"{name} does not return with {ret.hex()}")
    if core.read(S.GAME_WINDOW_GET, 1) != b"\xA1" or core.read(S.GAME_WINDOW_GET + 5, 1) != b"\xC3":
        raise SiteError("ldwGameWindow::Get is not mov eax, [instance]; ret")
    if core.read(S.WINDOW_GET_FONT, 6) != bytes.fromhex("8B018B405CC3"):
        raise SiteError("ldwGameWindow::GetFont is not [[this]+5Ch]")
    if S.BOX_COLOR >> 24 != S.BOX_ALPHA or S.BOX_COLOR & 0xFFFFFF != 0xFFFFFF:
        raise SiteError("derived constant wrong: the box is not white at its alpha")
    if S.BOX_PADDING != S.HINT_BOX_MARGIN:
        raise SiteError("the padding is not the hint box's margin")
    if S.MENU_SLOT_DRAW_SCENE != S.MENU_VTABLE + 4 * S.DRAW_SCENE_VSLOT:
        raise SiteError("derived constant wrong: the slot is not DrawScene's")
    vt = menu_vtable(core)
    if vt != S.MENU_VTABLE:
        raise SiteError(f"theMenuScene's vtable is {vt:#x}, not {S.MENU_VTABLE:#x}")
    if core.u32(S.MENU_SLOT_DRAW_SCENE) != S.MENU_DRAW_SCENE or S.MENU_SLOT_DRAW_SCENE not in core.relocs:
        raise SiteError("theMenuScene's DrawScene slot is not a relocated pointer to the pinned DrawScene")
    model = build_model(core)
    got = resolve(core, model)
    for name in (*S.ADDRESS_CONSTANTS, *S.TEST_ADDRESS_CONSTANTS, "MENU_SLOT_DRAW_SCENE"):
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
        "// GENERATED by runtime/tools/gen_b200_titlebox_sites.py from runtime/b200_titlebox_sites.py.",
        "// Do not edit. The DLL holds no game address: it searches the live executable for each pinned run",
        "// (mask 1 = wildcard: a relocated field or a call/jmp displacement), derives every address from",
        "// where the runs were found, and finds theMenuScene's vtable through its RTTI. It installs nothing",
        "// unless every pin is found once, every derivation agrees and the DrawScene slot points to the",
        "// pinned DrawScene.",
        "#pragma once",
        "",
        "struct TboxPin {",
        "    const char *name; unsigned len; const unsigned char *bytes; const unsigned char *mask;",
        "    int parent;       // -1: searched for in the executable sections; else the index of its anchor pin",
        "    int offset;       // signed distance from the anchor pin",
        "};",
        "struct TboxEvidence { unsigned char site; char kind; unsigned short pin; unsigned offset; };",
        "",
    ]
    skip = set(S.ADDRESS_CONSTANTS) | set(S.CORE_ONLY_CONSTANTS)
    for key in sorted(vars(S)):
        value = getattr(S, key)
        if key.isupper() and isinstance(value, int) and not isinstance(value, bool) and key not in skip:
            out.append(f"#define TBOX_{key} 0x{value:X}u")
    out.append(f'#define TBOX_MENU_TYPE_NAME ".?AV{S.MENU_CLASS}@@"')
    out.append("")
    out.append("enum TboxSite {")
    for name in model.sites[:model.dll_sites]:
        out.append(f"    TBOX_SITE_{name},")
    out.append("    TBOX_SITE_COUNT")
    out.append("};")
    out.append("")
    dll_pins = [e for e in model.pins if e["dll"]]
    for e in dll_pins:
        out.append(f"static const unsigned char tpin_{e['name']}[] = {{ {arr(e['bytes'])} }};")
        out.append(f"static const unsigned char tpinmask_{e['name']}[] = {{ {arr(e['mask'])} }};")
    out.append("")
    out.append("static const TboxPin TBOX_PINS[] = {")
    for e in dll_pins:
        out.append(f'    {{ "{e["name"]}", {len(e["bytes"])}u, tpin_{e["name"]}, tpinmask_{e["name"]}, '
                   f'{e["parent"]}, {e["offset"]} }},')
    out.append("};")
    out.append("")
    out.append("static const TboxEvidence TBOX_EVIDENCE[] = {")
    for si, kind, pi, off in model.evidence:
        if si >= model.dll_sites:
            continue
        out.append(f"    {{ TBOX_SITE_{model.sites[si]}, '{kind}', {pi}, 0x{off:X}u }},")
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
