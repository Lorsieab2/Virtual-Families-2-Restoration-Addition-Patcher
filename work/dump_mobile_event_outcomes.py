"""IDA batch helper for exact VF2 mobile Island Event outcome audits."""

from pathlib import Path

import ida_auto
import ida_funcs
import ida_hexrays
import ida_lines
import ida_name
import ida_pro
import idautils
import idc


TARGET_CLASSES = (
    "CEventClownHoldingMetalRod",
    "CEventHearStrangeSound",
    "CEventMenInBlackAtDoor",
    "CEventMetallicKnockingOnDoor",
    "CEventMeteoriteFallsInYard2",
)


def clean(text):
    return ida_lines.tag_remove(str(text))


def main():
    ida_auto.auto_wait()
    output = Path(idc.ARGV[1])
    matches = []
    for address in idautils.Functions():
        name = ida_name.get_name(address)
        if "CVillagerManager23GetRandomVillagerByAges" in name or any(
            class_name in name for class_name in TARGET_CLASSES
        ):
            matches.append((address, name))

    rows = []
    for address, name in sorted(matches):
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
        rows.append("--- xrefs ---")
        for xref in idautils.XrefsTo(address):
            caller = ida_funcs.get_func(xref.frm)
            caller_name = (
                ida_name.get_name(caller.start_ea) if caller is not None else ""
            )
            rows.append(
                f"{xref.frm:08X} type={xref.type} caller={caller_name}"
            )
        rows.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows), encoding="utf-8")
    print(f"Wrote {len(matches)} matched functions to {output}")
    ida_pro.qexit(0 if matches else 2)


if __name__ == "__main__":
    main()
