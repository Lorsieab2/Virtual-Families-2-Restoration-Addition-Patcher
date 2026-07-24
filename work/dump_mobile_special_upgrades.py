"""IDA batch helper for exact VF2 mobile special-upgrade mechanics."""

from pathlib import Path

import ida_auto
import ida_bytes
import ida_funcs
import ida_hexrays
import ida_lines
import ida_name
import ida_pro
import ida_xref
import idautils
import idc


TARGET_NAME_PARTS = (
    "CFoodStore",
    "CMoney9LoadState",
    "CMoney9SaveState",
    "CMoney14UpdateInterest",
    "theGameInfoExtensible",
    "Brokerage",
    "FoodClub",
    "HealthPlan",
    "JoinFoodClub",
    "HaveFoodClub",
    "DoFoodClubDelivery",
    "OrganicDelivery",
)

TARGET_OPERAND_VALUES = (
    0x25B34,  # Lucky Rock game-state byte
    0x25B35,  # Health Plan game-state byte
    0xE3D4,  # legacy Food Club/IAP game-state field
)

TARGET_DATA_VALUES = (
    0x25DDE4,
    0x25DDE8,
    0x25DDF4,
    0x25DE88,
)

TARGET_ADDRESSES = (
    0x000DD979,  # CScrollingStoreScene::DrawVisibleStoreItem
    0x000DE17C,  # CScrollingStoreScene::HandleMouse
    0x000DE957,  # CScrollingStoreScene::CalcPrice
    0x000DF082,  # CScrollingStoreScene::HandlePurchaseItem
    0x0012AB2D,  # CPurchaseManagerImpl::Gift
    0x0012B8DE,  # CFoodStore::Update
    0x001D15D3,  # CVillagerManager realtime upkeep
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
            for reference in idautils.XrefsTo(address):
                caller = function_start(reference.frm)
                matches[caller] = (
                    ida_name.get_name(caller) or f"sub_{caller:X}"
                )
    for address in TARGET_ADDRESSES:
        start = function_start(address)
        matches[start] = ida_name.get_name(start) or f"sub_{start:X}"
    for address in idautils.Heads():
        for operand in range(3):
            if idc.get_operand_value(address, operand) in TARGET_OPERAND_VALUES:
                start = function_start(address)
                matches[start] = (
                    ida_name.get_name(start) or f"sub_{start:X}"
                )
                break

    rows = ["===== referenced constants ====="]
    for address in TARGET_DATA_VALUES:
        raw = ida_bytes.get_bytes(address, 8) or b""
        rows.append(f"{address:08X}: {raw.hex()}")
    rows.append("")
    for address, name in sorted(matches.items()):
        function = ida_funcs.get_func(address)
        end = function.end_ea if function is not None else address
        rows.append(f"===== {name} @ {address:08X}-{end:08X} =====")
        callers = []
        reference = ida_xref.get_first_cref_to(address)
        while reference != idc.BADADDR:
            caller = function_start(reference)
            callers.append(
                f"{reference:08X} in "
                f"{ida_name.get_name(caller) or f'sub_{caller:X}'}"
            )
            reference = ida_xref.get_next_cref_to(address, reference)
        rows.append("callers: " + (", ".join(callers) if callers else "(none)"))
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
    print(f"Wrote {len(matches)} matched functions to {output}")
    ida_pro.qexit(0 if matches else 2)


if __name__ == "__main__":
    main()
