from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coff_patch import CoffObject


ROOT = Path(__file__).resolve().parents[1]
OBJ_DIR = ROOT / "work" / "patched_mobile_furniture_pack_objs"
REL32 = 0x14


def patch_scrolling_store_scene() -> None:
    obj_path = OBJ_DIR / "ScrollingStoreScene.obj"
    co = CoffObject(obj_path)

    handle_mouse = co.symbol("?HandleMouse@CScrollingStoreScene@@UAE_NHUldwPoint@@@Z")
    handle_purchase = co.symbol("?HandlePurchaseItem@CScrollingStoreScene@@AAEXXZ")

    mouse_sec = co.section(handle_mouse.section)
    purchase_sec = co.section(handle_purchase.section)

    def mouse_bytes(offset: int, size: int) -> bytes:
        start = mouse_sec.raw_ptr + handle_mouse.value + offset
        return bytes(co.buf[start : start + size])

    def purchase_bytes(offset: int, size: int) -> bytes:
        start = purchase_sec.raw_ptr + handle_purchase.value + offset
        return bytes(co.buf[start : start + size])

    # Special-upgrade rows were still routed to old "already owned/maxed"
    # message boxes. Send rows 7+ to the regular confirmation dialog so the
    # helper can dispatch Buy or Cancel from the green/red dialog buttons.
    if mouse_bytes(0x44C, 5) == bytes.fromhex("83 FE 07 75 22"):
        start = mouse_sec.raw_ptr + handle_mouse.value + 0x44C
        co.buf[start : start + 5] = bytes.fromhex("E9 9A 00 00 00")
    elif mouse_bytes(0x44C, 5) != bytes.fromhex("E9 9A 00 00 00"):
        raise RuntimeError("Unexpected HandleMouse special-upgrade gate bytes")

    # Replace:
    #   test eax,eax; jne skip; mov ecx,edi; call HandlePurchaseItem
    # with:
    #   push eax; push edi; nop*4; call VF2HandleSpecialUpgradeDialogResult
    # The call is placed so the existing relocation at 0x529 can be retargeted.
    dialog_hook = bytes.fromhex("50 57 90 90 90 90 E8 00 00 00 00")
    original_dialog = bytes.fromhex("85 C0 75 07 8B CF E8 00 00 00 00")
    if mouse_bytes(0x522, 11) == original_dialog:
        start = mouse_sec.raw_ptr + handle_mouse.value + 0x522
        co.buf[start : start + 11] = dialog_hook
        symidx = co.append_undefined_symbol("_VF2HandleSpecialUpgradeDialogResult@8")
        co.retarget_relocation(handle_mouse.section, handle_mouse.value + 0x529, symidx, REL32)
    elif mouse_bytes(0x522, 11) == dialog_hook:
        symidx = co.append_undefined_symbol("_VF2HandleSpecialUpgradeDialogResult@8")
        co.retarget_relocation(handle_mouse.section, handle_mouse.value + 0x529, symidx, REL32)
    else:
        raise RuntimeError("Unexpected HandleMouse dialog-result bytes")

    # Precharge coin-backed special upgrades before the original IAP handler
    # sets feature flags. If the upgrade is already active or unaffordable, the
    # helper returns 1 and we jump to the normal function epilogue.
    precharge_payload = bytes.fromhex(
        "56"                    # push esi
        "E8 00 00 00 00"        # call VF2PrechargeSpecialUpgrade
        "83 C4 04"              # add esp,4
        "84 C0"                 # test al,al
        "74 05"                 # jz continue
        "E9 DB 02 00 00"        # jmp epilogue after inserted-byte shift
    )
    original_purchase = bytes.fromhex("0F 85 3D 01 00 00")
    if purchase_bytes(0x41, len(precharge_payload)) == precharge_payload:
        pass
    elif purchase_bytes(0x41, len(original_purchase)) == original_purchase:
        co.insert_section_bytes(handle_purchase.section, handle_purchase.value + 0x41, precharge_payload)
        symidx = co.append_undefined_symbol("_VF2PrechargeSpecialUpgrade")
        co.append_relocation(handle_purchase.section, handle_purchase.value + 0x43, symidx, REL32)
    else:
        raise RuntimeError("Unexpected HandlePurchaseItem insertion point bytes")

    # Brokerage Account: allow repeat purchases up to 11%, one percent at a time.
    co.buf[:] = co.buf.replace(bytes.fromhex("CD CC CC 3D"), bytes.fromhex("AE 47 E1 3D"))
    co.buf[:] = co.buf.replace(bytes.fromhex("0A D7 A3 3C"), bytes.fromhex("0A D7 23 3C"))

    co.write(obj_path)


def patch_string_titles() -> None:
    obj_path = OBJ_DIR / "theStringManager.obj"
    data = bytearray(obj_path.read_bytes())
    replacements = {
        b"Brokerage Account $0.99": b"Brokerage Account 9999",
        b"Food Club $0.99": b"Food Club 10000",
        b"Health Plan $0.99": b"Health Plan 10000",
        b"Lucky Rock $0.99": b"Lucky Rock 77777",
    }
    for old, new in replacements.items():
        idx = data.find(old)
        if idx < 0:
            padded = new + b"\0" * (len(old) - len(new))
            if data.find(padded) >= 0:
                continue
            raise RuntimeError(f"Could not find string {old!r}")
        if len(new) > len(old):
            raise RuntimeError(f"Replacement too long for {old!r}")
        data[idx : idx + len(old)] = new + b"\0" * (len(old) - len(new))
    obj_path.write_bytes(data)


def main() -> None:
    patch_scrolling_store_scene()
    patch_string_titles()
    print("Patched Special Upgrades purchase/undo hooks and titles.")


if __name__ == "__main__":
    main()
