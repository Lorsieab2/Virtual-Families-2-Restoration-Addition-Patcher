from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coff_patch import CoffObject

ROOT = Path(__file__).resolve().parents[1]
OBJ_DIR = ROOT / "work" / "patched_mobile_furniture_pack_objs"
REL32 = 0x14


def main() -> None:
    obj_path = OBJ_DIR / "theMainScene.obj"
    co = CoffObject(obj_path)
    sym = co.symbol("?HandleMouseDown@theMainScene@@IAE?B_NUldwPoint@@@Z")
    sec = co.section(sym.section)
    base = sec.raw_ptr + sym.value

    helper_name = "_VF2HandleActionBarTipsClick"
    if helper_name in co.symbol_by_name:
        print("Action-bar tips hook already present.")
        return

    insert_at = sym.value + 0x53
    expected = bytes.fromhex("8B 55 0C A1")
    if bytes(co.buf[base + 0x53:base + 0x57]) != expected:
        raise RuntimeError("Unexpected theMainScene::HandleMouseDown insertion bytes")

    payload = bytes.fromhex(
        "FF 75 0C"            # push [ebp+0Ch] ; y
        "FF 75 08"            # push [ebp+08h] ; x
        "56"                  # push esi       ; this
        "E8 00 00 00 00"      # call _VF2HandleActionBarTipsClick
        "83 C4 0C"            # add esp,0Ch
        "84 C0"               # test al,al
        "74 05"               # je continue
        "E9 5F 00 00 00"      # jmp existing handled-return path
    )
    co.insert_section_bytes(sym.section, insert_at, payload)
    helper = co.append_undefined_symbol(helper_name)
    co.append_relocation(sym.section, insert_at + 7, helper, REL32)
    co.write(obj_path)
    print("Patched action-bar tips click hook.")


if __name__ == "__main__":
    main()
