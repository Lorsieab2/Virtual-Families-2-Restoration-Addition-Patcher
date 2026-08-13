from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coff_patch import CoffObject

ROOT = Path(__file__).resolve().parents[1]
OBJ_DIR = ROOT / "work" / "patched_mobile_furniture_pack_objs"

DIR32 = 0x06
REL32 = 0x14


def main() -> None:
    obj_path = OBJ_DIR / "IslandEvents.obj"
    co = CoffObject(obj_path)

    sym = co.symbol("?ImpactGame@CEventATinyWhiteBox@@UAEXH@Z")
    sec = co.section(sym.section)
    base = sec.raw_ptr + sym.value

    if bytes(co.buf[base : base + 5]) == bytes.fromhex("E9 2E 00 00 00"):
        print("Meteorite sell award hook already present.")
        return

    expected = bytes.fromhex("55 8B EC 83 7D 08 00 75 28")
    if bytes(co.buf[base : base + len(expected)]) != expected:
        raise RuntimeError("Unexpected CEventATinyWhiteBox::ImpactGame prologue")

    old_size = 0x33
    tail_at = sym.value + old_size
    rel = tail_at - (sym.value + 5)
    co.buf[base : base + 5] = b"\xE9" + struct.pack("<i", rel)

    payload = bytes.fromhex(
        "55"                    # push ebp
        "8B EC"                 # mov ebp, esp
        "83 7D 08 00"           # cmp dword ptr [ebp+8], 0
        "75 14"                 # jne done
        "6A 01"                 # push 1
        "51"                    # push ecx, overwritten with float argument
        "B9 00 00 00 00"        # mov ecx, offset Money
        "C7 04 24 00 00 48 42"  # mov dword ptr [esp], 50.0f
        "E8 00 00 00 00"        # call CMoney::Adjust(float,bool)
        "5D"                    # pop ebp
        "C2 04 00"              # ret 4
    )
    co.insert_section_bytes(sym.section, tail_at, payload)

    money = co.symbol("?Money@@3VCMoney@@A").index
    adjust = co.symbol("?Adjust@CMoney@@QAEXM_N@Z").index
    co.append_relocation(sym.section, tail_at + 0x0D, money, DIR32)
    co.append_relocation(sym.section, tail_at + 0x19, adjust, REL32)

    co.write(obj_path)
    print("Patched meteorite fragment Sell choice to award 50 coins.")


if __name__ == "__main__":
    main()
