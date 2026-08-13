"""IDA batch helper for VF2 mobile villager-drop dispatch evidence."""

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
    "_ZN12theMainScene12DropVillagerEv",
    "_ZN12theMainScene19HandleDropOnHotSpotER9CVillager",
    "_ZN11CContentMap9GetObjectE8ldwPoint",
    "_ZN11CContentMap10GetHotSpotE8ldwPoint",
    "_ZN8CHotSpotC1Ev",
    "_ZNK8CHotSpot8DispatchER9CVillagerN11CContentMap8EHotSpotE",
)


def clean(text):
    return ida_lines.tag_remove(str(text))


def main():
    ida_auto.auto_wait()
    output = Path(idc.ARGV[1])
    rows = []
    found = 0
    for target in TARGETS:
        address = ida_name.get_name_ea(idc.BADADDR, target)
        if address == idc.BADADDR:
            rows.append(f"===== missing {target} =====")
            continue
        found += 1
        function = ida_funcs.get_func(address)
        end = function.end_ea if function is not None else address
        rows.append(f"===== {target} @ {address:08X}-{end:08X} =====")
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
    print(f"Wrote {found} drop-dispatch functions to {output}")
    ida_pro.qexit(0 if found == len(TARGETS) else 2)


if __name__ == "__main__":
    main()
