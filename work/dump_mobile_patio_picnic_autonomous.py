"""IDA batch helper for exact mobile Patio/Picnic autonomous predicates."""

from pathlib import Path

import ida_auto
import ida_funcs
import ida_hexrays
import ida_lines
import ida_name
import ida_pro
import idautils
import idc


TARGET_NAME_PARTS = (
    "CVillager6InitAI",
    "CVillagerAI14DecideWhatToDo",
    "PreparingPicnic",
    "EatAtPicnicTable",
    "PreparingDrinks",
    "DrinkAtPatioChair",
)


def clean(text):
    return ida_lines.tag_remove(str(text))


def function_start(address):
    function = ida_funcs.get_func(address)
    return function.start_ea if function is not None else address


def main():
    ida_auto.auto_wait()
    output = Path(idc.ARGV[1])
    matches = {}
    for address, name in idautils.Names():
        if any(part.lower() in name.lower() for part in TARGET_NAME_PARTS):
            start = function_start(address)
            matches[start] = ida_name.get_name(start) or name

    rows = []
    for address, name in sorted(matches.items()):
        function = ida_funcs.get_func(address)
        end = function.end_ea if function is not None else address
        rows.append(f"===== {name} @ {address:08X}-{end:08X} =====")
        try:
            rows.append(clean(ida_hexrays.decompile(address)))
        except Exception as exc:
            rows.append(f"[decompile unavailable: {exc}]")
        rows.append("--- disassembly ---")
        for item in idautils.FuncItems(address):
            rows.append(
                f"{item:08X}: {clean(idc.generate_disasm_line(item, 0))}"
            )
        rows.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows), encoding="utf-8")
    print(f"Wrote {len(matches)} Patio/Picnic autonomous functions to {output}")
    ida_pro.qexit(0 if matches else 2)


if __name__ == "__main__":
    main()
