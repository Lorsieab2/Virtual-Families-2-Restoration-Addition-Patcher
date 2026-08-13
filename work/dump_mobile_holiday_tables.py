"""Dump the function-pointer neighborhoods that reference VF2 Holiday methods."""

from pathlib import Path

import ida_auto
import ida_bytes
import ida_funcs
import ida_name
import ida_pro
import idautils
import idc

try:
    import ida_hexrays
except ImportError:
    ida_hexrays = None


TARGETS = (
    "KidExaminesCandles",
    "AdmiringXmasTree",
    "AdultWaterXMasTree",
    "AdmiringXmasKnickKnacks",
    "KidStealsSantasCookies",
    "AdultsSaveSantasCookies",
    "InteractHouseXmasDecor",
    "KidsCheckXmasStockings",
    "UsingWarmTowel",
)


def describe(address):
    value = ida_bytes.get_wide_dword(address)
    name = ida_name.get_name(value)
    return f"{address:08X}: {value:08X} {name}"


def dump_function(rows, function, label):
    func = ida_funcs.get_func(function)
    if func is None:
        rows.append(f"===== {label}: function not found at {function:08X} =====")
        return
    rows.append(
        f"===== {label} {ida_name.get_name(func.start_ea)} "
        f"{func.start_ea:08X}-{func.end_ea:08X} ====="
    )
    if ida_hexrays is not None:
        try:
            rows.append(str(ida_hexrays.decompile(func.start_ea)))
        except Exception as exc:
            rows.append(f"decompile failed: {exc}")
    rows.append("----- disassembly -----")
    for address in idautils.FuncItems(func.start_ea):
        rows.append(
            f"{address:08X}: {idc.generate_disasm_line(address, 0) or ''}"
        )
    rows.append("")


def main():
    ida_auto.auto_wait()
    output = Path(idc.ARGV[1])
    rows = []
    for function in idautils.Functions():
        name = ida_name.get_name(function)
        if not any(target in name for target in TARGETS):
            continue
        rows.append(f"===== {name} {function:08X} =====")
        for xref in idautils.XrefsTo(function):
            rows.append(f"xref {xref.frm:08X} type={xref.type}")
            if xref.frm >= 0x300000:
                for address in range(xref.frm - 0x30, xref.frm + 0x34, 4):
                    rows.append(describe(address))
                rows.append("table xrefs:")
                for table_xref in idautils.XrefsTo(xref.frm):
                    caller = ida_funcs.get_func(table_xref.frm)
                    caller_name = (
                        ida_name.get_name(caller.start_ea)
                        if caller is not None
                        else ""
                    )
                    rows.append(
                        f"  {table_xref.frm:08X} type={table_xref.type} "
                        f"caller={caller_name}"
                    )
        rows.append("")
    dump_function(rows, 0x162900, "CBehavior constructor")
    init_ai = [
        function
        for function in idautils.Functions()
        if "CVillager6InitAIEv" in ida_name.get_name(function)
    ]
    if init_ai:
        for function in init_ai:
            dump_function(rows, function, "CVillager::InitAI")
    else:
        rows.append("===== CVillager::InitAI: symbol not found =====")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows), encoding="utf-8")
    ida_pro.qexit(0)


if __name__ == "__main__":
    main()
