"""IDA batch helper for the self-contained VF2 mobile holiday-behavior audit."""

from pathlib import Path

import ida_auto
import ida_funcs
import ida_hexrays
import ida_lines
import ida_name
import ida_pro
import idautils
import idc


TARGETS = (
    "KidExaminesCandles",
    "AdmiringXmasTree",
    "AdultWaterXMasTree",
    "InteractHouseXmasDecor",
    "KidsCheckXmasStockings",
    "AdmiringXmasKnickKnacks",
    "AdultsSaveSantasCookies",
    "KidStealsSantasCookies",
    "Knick",
    "XmasDecor",
)


def clean(text):
    return ida_lines.tag_remove(str(text))


def disassembly(start):
    function = ida_funcs.get_func(start)
    rows = []
    for address in idautils.FuncItems(start):
        rows.append(f"{address:08X}: {clean(idc.generate_disasm_line(address, 0))}")
    return "\n".join(rows), function.end_ea if function else start


def main():
    ida_auto.auto_wait()
    output = Path(idc.ARGV[1])
    matches = []
    for address in idautils.Functions():
        name = ida_name.get_name(address)
        if any(target in name for target in TARGETS):
            matches.append((address, name))

    sections = []
    for address, name in sorted(matches):
        assembly, end = disassembly(address)
        sections.append(f"===== {name} @ {address:08X}-{end:08X} =====")
        try:
            sections.append(clean(ida_hexrays.decompile(address)))
        except Exception as exc:
            sections.append(f"[decompile unavailable: {exc}]")
        sections.append("--- disassembly ---")
        sections.append(assembly)
        sections.append("--- xrefs ---")
        for xref in idautils.XrefsTo(address):
            caller = ida_funcs.get_func(xref.frm)
            caller_name = (
                ida_name.get_name(caller.start_ea) if caller is not None else ""
            )
            sections.append(
                f"{xref.frm:08X} type={xref.type} caller={caller_name}"
            )
        sections.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(sections), encoding="utf-8")
    print(f"Wrote {len(matches)} matched functions to {output}")
    ida_pro.qexit(0 if matches else 2)


if __name__ == "__main__":
    main()
