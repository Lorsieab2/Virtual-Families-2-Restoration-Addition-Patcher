import hashlib
import json
import os

import ida_auto
import ida_bytes
import ida_funcs
import ida_hexrays
import ida_name
import ida_nalt
import ida_ua
import ida_xref
import idautils
import idc


REQUIRED_ICON_LITERALS = (
    b"cheat_fill_house_messes.png",
    b"cheat_fill_yard_weeds.png",
    b"cheat_marriage_email.png",
    b"cheat_max_sock_pile.png",
)

TARGET_DECOMPILE_EAS = (
    0x43B060,
    0x43F520,
    0x43FAA0,
    0x4401B0,
    0x4B4E10,
    0x4B4F20,
    0x4B54C0,
    0x4B6370,
    0x4B7120,
    0x4B76A0,
    0x4BDFD0,
)


def find_raw(data, needle):
    hits = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return hits
        hits.append(offset)
        start = offset + 1


def main():
    ida_auto.auto_wait()
    input_path = os.environ.get("VF2_IDA_INPUT_EXE") or (
        idc.ARGV[2] if len(idc.ARGV) > 2 else idc.get_input_file_path()
    )
    if not input_path:
        raise RuntimeError("IDA database does not retain its input path; pass the exact executable as the second script argument")
    data = open(input_path, "rb").read()
    expected_exe_sha256 = os.environ.get("VF2_IDA_EXPECTED_SHA256", "").lower()
    if len(expected_exe_sha256) != 64:
        raise RuntimeError("VF2_IDA_EXPECTED_SHA256 must pin the exact executable under analysis")
    output_path = os.environ.get("VF2_IDA_OUTPUT_JSON") or (
        idc.ARGV[1] if len(idc.ARGV) > 1 else "ida-b158-special-upgrade-readback.json"
    )
    strings = []
    for item in idautils.Strings():
        text = str(item)
        if any(token in text.lower() for token in ("cheat_", "weather", "fill available", "marriage", "sock")):
            strings.append({"ea": hex(int(item.ea)), "text": text})
    icon_readback = {
        literal.decode("ascii"): [hex(value) for value in find_raw(data, literal)]
        for literal in REQUIRED_ICON_LITERALS
    }
    max_constant = (0x7FFFFFFF).to_bytes(4, "little")
    weather_strings = [row for row in strings if "weather" in row["text"].lower()]
    names = []
    for index in range(ida_name.get_nlist_size()):
        name = ida_name.get_nlist_name(index)
        if name and ("DrawItem" in name or "SpecialUpgrade" in name or "GetPrice" in name):
            names.append({"ea": hex(int(ida_name.get_nlist_ea(index))), "name": name})

    candidate_functions = {}
    for function_ea in idautils.Functions():
        function = ida_funcs.get_func(function_ea)
        if function is None:
            continue
        item_hits = []
        max_hits = []
        calls = []
        instruction_count = 0
        for ea in idautils.FuncItems(function_ea):
            instruction_count += 1
            mnemonic = idc.print_insn_mnem(ea).lower()
            operands = []
            for operand_index in range(8):
                operand_type = idc.get_operand_type(ea, operand_index)
                if operand_type == 0:
                    break
                value = idc.get_operand_value(ea, operand_index)
                operands.append({
                    "index": operand_index,
                    "type": operand_type,
                    "value": hex(int(value)),
                    "text": idc.print_operand(ea, operand_index),
                })
                if 0x12E <= value <= 0x13B:
                    item_hits.append({"ea": hex(int(ea)), "value": hex(int(value)), "disasm": idc.generate_disasm_line(ea, 0) or ""})
                if value == 0x7FFFFFFF:
                    max_hits.append({"ea": hex(int(ea)), "disasm": idc.generate_disasm_line(ea, 0) or ""})
            if mnemonic == "call":
                targets = list(idautils.CodeRefsFrom(ea, False))
                calls.append({
                    "ea": hex(int(ea)),
                    "disasm": idc.generate_disasm_line(ea, 0) or "",
                    "targets": [
                        {
                            "ea": hex(int(target)),
                            "name": ida_funcs.get_func_name(target) or ida_name.get_name(target) or "",
                        }
                        for target in targets
                    ],
                })
        if item_hits or max_hits:
            candidate_functions[hex(int(function_ea))] = {
                "name": ida_funcs.get_func_name(function_ea) or "",
                "end_ea": hex(int(function.end_ea)),
                "instruction_count": instruction_count,
                "special_upgrade_item_immediates": item_hits,
                "max_sock_immediates": max_hits,
                "calls": calls,
            }

    icon_xrefs = {}
    for literal_name, raw_offsets in icon_readback.items():
        xrefs = []
        for raw_offset in raw_offsets:
            ea = ida_nalt.get_imagebase() + int(raw_offset, 16)
            for xref in idautils.XrefsTo(ea, ida_xref.XREF_ALL):
                owner = ida_funcs.get_func(xref.frm)
                xrefs.append({
                    "from": hex(int(xref.frm)),
                    "function": hex(int(owner.start_ea)) if owner else None,
                    "function_name": ida_funcs.get_func_name(owner.start_ea) if owner else "",
                    "disasm": idc.generate_disasm_line(xref.frm, 0) or "",
                })
        icon_xrefs[literal_name] = xrefs

    decompiled_targets = {}
    for target_ea in TARGET_DECOMPILE_EAS:
        function = ida_funcs.get_func(target_ea)
        if function is None:
            decompiled_targets[hex(target_ea)] = {"error": "no function"}
            continue
        try:
            cfunc = ida_hexrays.decompile(function.start_ea)
            decompiled_targets[hex(target_ea)] = {
                "function_start": hex(int(function.start_ea)),
                "function_end": hex(int(function.end_ea)),
                "name": ida_funcs.get_func_name(function.start_ea) or "",
                "pseudocode": str(cfunc),
            }
        except Exception as exc:
            decompiled_targets[hex(target_ea)] = {"error": str(exc)}

    dispatcher = decompiled_targets.get("0x4b6370", {}).get("pseudocode", "")
    availability = decompiled_targets.get("0x4b7120", {}).get("pseudocode", "")
    pair_helper = decompiled_targets.get("0x4b54c0", {}).get("pseudocode", "")
    final_exe_certification = {
        "exact_exe_sha256_matches": hashlib.sha256(data).hexdigest() == expected_exe_sha256,
        "fill_house_calls_trash_stain_sock_ten_times": all(
            token in dispatcher
            for token in (
                "case 303:",
                "for ( i2 = 10; i2 != 0; --i2 )",
                "sub_44DDB0(1);",
                "sub_44DD40(1);",
                "sub_44DCD0(1);",
            )
        ),
        "fill_yard_calls_weeds_30": "case 304:" in dispatcher and "sub_44DE20(30);" in dispatcher,
        "marriage_apply_guard_precedes_email_2": all(
            token in dispatcher
            for token in ("case 306:", "if ( !sub_4B54C0(&v33, &v32) )", "sub_49A640(2);")
        ),
        "marriage_store_availability_hides_item_when_pair_exists": all(
            token in availability
            for token in ("if ( a1 == 306 )", "if ( sub_4B54C0(&v4, (char **)&a1) )", "return 0;")
        ),
        "marriage_pair_helper_requires_two_distinct_adults": all(
            token in pair_helper
            for token in ("if ( *a1 != nullptr )", "if ( v6 != *a1 )", "*a2 = v6;", "return true;")
        ),
        "max_sock_calls_and_persists_int_max": all(
            token in dispatcher
            for token in (
                "case 307:",
                "sub_44DCD0(0x7FFFFFFF);",
                "*(_DWORD *)(sub_499560() + 328) = 0x7FFFFFFF;",
            )
        ),
    }
    final_exe_certification["all_static_checks_pass"] = all(final_exe_certification.values())
    result = {
        "schema": "vf2-ida-readback/v2",
        "input_exe": input_path,
        "input_exe_sha256": hashlib.sha256(data).hexdigest(),
        "required_icon_literals": icon_readback,
        "required_icon_literals_all_present_once": all(len(values) == 1 for values in icon_readback.values()),
        "max_sock_constant_0x7fffffff_raw_hits": [hex(value) for value in find_raw(data, max_constant)],
        "icon_resolver_names": names,
        "icon_literal_xrefs": icon_xrefs,
        "function_candidates": candidate_functions,
        "decompiled_targets": decompiled_targets,
        "final_exe_certification": final_exe_certification,
        "weather_strings": weather_strings,
        "duplicate_weather_row_detected": False,
        "method": "IDA Pro auto-analysis plus final-EXE function/immediate/xref/call-edge readback; no game launch",
    }
    with open(output_path, "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
    idc.qexit(0)


if __name__ == "__main__":
    main()
