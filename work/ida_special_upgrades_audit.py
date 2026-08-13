"""Read-only IDA audit for the VF2 Special Upgrades regression."""

from __future__ import annotations

import hashlib
import json
import os
import sys

import ida_auto
import ida_funcs
import ida_nalt
import ida_name
import idautils
import idc


def argument_values() -> tuple[str, str]:
    args = list(getattr(idc, "ARGV", []))
    label = args[1] if len(args) > 1 else "input"
    report = args[2] if len(args) > 2 else os.path.join(os.getcwd(), "ida_special_upgrades_audit.json")
    return label, report


def string_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def main() -> None:
    ida_auto.auto_wait()
    label, report_path = argument_values()
    input_path = os.path.abspath(ida_nalt.get_input_file_path())
    result: dict[str, object] = {
        "label": label,
        "input": input_path,
        "sha256": hashlib.sha256(open(input_path, "rb").read()).hexdigest().upper(),
        "strings": [],
        "functions": [],
    }

    needles = (
        "Systematic Desensitization",
        "Psychotherapy",
        "Higher Learning Classes",
        "Advanced Career Training",
        "Career Change",
        "Trigger all house malfunctions",
        "Fix all house malfunctions",
        "Reset Price Multiplier",
        "Brokerage Account",
        "Food Club",
        "Health Plan",
        "Lucky Rock",
    )
    needle_lower = tuple(value.lower() for value in needles)
    seen_strings: set[int] = set()
    string_rows: list[dict[str, object]] = []
    function_eas: set[int] = set()
    for string in idautils.Strings():
        text = string_text(string).strip("\x00")
        lowered = text.lower()
        if not any(needle in lowered for needle in needle_lower):
            continue
        if string.ea in seen_strings:
            continue
        seen_strings.add(string.ea)
        xrefs = []
        for xref in idautils.XrefsTo(string.ea, 0):
            function = ida_funcs.get_func(xref.frm)
            function_ea = function.start_ea if function else idc.BADADDR
            if function_ea != idc.BADADDR:
                function_eas.add(function_ea)
            xrefs.append(
                {
                    "from": hex(xref.frm),
                    "function": hex(function_ea) if function_ea != idc.BADADDR else None,
                    "function_name": ida_name.get_ea_name(function_ea) if function_ea != idc.BADADDR else None,
                }
            )
        string_rows.append({"ea": hex(string.ea), "text": text, "xrefs": xrefs})
    result["strings"] = string_rows

    result["functions"] = [
        {"ea": hex(ea), "name": ida_name.get_ea_name(ea)}
        for ea in sorted(function_eas)
    ]
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    idc.qexit(0)


if __name__ == "__main__":
    main()
