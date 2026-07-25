"""IDA batch helper for mobile renovation store, save, and render evidence."""

from pathlib import Path

import ida_auto
import ida_bytes
import ida_funcs
import ida_hexrays
import ida_lines
import ida_name
import ida_pro
import idautils
import idc


FUNCTION_NAME_PARTS = (
    "Renovat",
    "ScrollingStoreScene",
    "HaveUpgrade",
    "AddToStorage",
    "theGraphicsManager",
)

# The mobile ELF database has stable addresses even when IDA's imported C++
# names are not present in a fresh analysis.  Keep the renovation/store
# callers explicit so the trace still produces a useful contract in that
# case.
TARGET_ADDRESSES = (
    0x000DD390,  # CScrollingStoreScene::DrawVisibleStoreItem
    0x000DDEE0,  # CScrollingStoreScene::HandleMouse
    0x000DE8A0,  # CScrollingStoreScene::CalcPrice
    0x000DEF00,  # CScrollingStoreScene::HandlePurchaseItem
    0x000DF4F0,  # CScrollingStoreScene::HandleUpgrade
    0x0012E620,  # theGameState::Load
)

STRING_PARTS = (
    "tp233",
    "tp234",
    "tp235",
    "tp238",
    "tp239",
    "tp240",
    "tp241",
    "tp242",
    "renovat",
    "bathroom upgrade",
)


def clean(text):
    return ida_lines.tag_remove(str(text))


def function_start(address):
    function = ida_funcs.get_func(address)
    return function.start_ea if function is not None else None


def render_function(address, name):
    function = ida_funcs.get_func(address)
    if function is None:
        return [f"===== {name} @ {address:08X} (not a function) =====", ""]
    rows = [f"===== {name} @ {address:08X}-{function.end_ea:08X} ====="]
    try:
        rows.append(clean(ida_hexrays.decompile(address)))
    except Exception as exc:
        rows.append(f"[decompile unavailable: {exc}]")
    rows.append("--- disassembly ---")
    for item in idautils.FuncItems(address):
        rows.append(f"{item:08X}: {clean(idc.generate_disasm_line(item, 0))}")
    rows.append("")
    return rows


def main():
    ida_auto.auto_wait()
    output = Path(idc.ARGV[1])
    strings = []
    functions = {}

    for item in idautils.Strings():
        value = str(item)
        if not any(part in value.lower() for part in STRING_PARTS):
            continue
        address = int(item.ea)
        xrefs = []
        for xref in idautils.XrefsTo(address):
            start = function_start(xref.frm)
            name = ida_name.get_name(start) if start is not None else ""
            xrefs.append((xref.frm, start, name))
            if start is not None:
                functions[start] = name or f"sub_{start:X}"
        strings.append((address, value, xrefs))

    for address, name in idautils.Names():
        if any(part.lower() in name.lower() for part in FUNCTION_NAME_PARTS):
            start = function_start(address)
            if start is not None:
                functions[start] = ida_name.get_name(start) or name

    for address in TARGET_ADDRESSES:
        start = function_start(address)
        if start is not None:
            functions[start] = ida_name.get_name(start) or f"sub_{start:X}"

    rows = ["===== MATCHED STRINGS AND XREFS ====="]
    for address, value, xrefs in sorted(strings):
        rows.append(f"{address:08X}: {value!r}")
        if not xrefs:
            rows.append("  [no code xrefs]")
        for source, start, name in xrefs:
            rows.append(
                f"  xref {source:08X} function "
                + (f"{start:08X} {name}" if start is not None else "[none]")
            )
    rows.append("")

    for address, name in sorted(functions.items()):
        rows.extend(render_function(address, name))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows), encoding="utf-8")
    print(
        f"Wrote {len(strings)} strings and {len(functions)} functions "
        f"to {output}"
    )
    # Do not call ida_pro.qexit here: IDA 9.4 removed that compatibility
    # alias.  Returning normally still flushes the output and closes batch
    # analysis cleanly.


if __name__ == "__main__":
    main()
