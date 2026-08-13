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

    sym = co.symbol("?ImpactGame@CEventACealedGreenBag@@UAEXH@Z")
    sec = co.section(sym.section)
    base = sec.raw_ptr + sym.value

    if bytes(co.buf[base : base + 5]) == bytes.fromhex("E9 2C 00 00 00"):
        print("Cat shelter donation hook already present.")
        return

    expected = bytes.fromhex("55 8B EC 83 7D 08 00 75 26")
    if bytes(co.buf[base : base + len(expected)]) != expected:
        raise RuntimeError("Unexpected CEventACealedGreenBag::ImpactGame prologue")

    old_size = 0x31
    tail_at = sym.value + old_size
    rel = tail_at - (sym.value + 5)
    co.buf[base : base + 5] = b"\xE9" + struct.pack("<i", rel)

    payload = bytes.fromhex(
        "55"                    # push ebp
        "8B EC"                 # mov ebp, esp
        "83 7D 08 00"           # cmp dword ptr [ebp+8], 0
        "75 2A"                 # jne done
        "6A 5B"                 # push 91
        "E8 00 00 00 00"        # call ldwGameState::GetRandom(int)
        "83 C4 04"              # add esp, 4
        "83 C0 0A"              # add eax, 10
        "F7 D8"                 # neg eax
        "50"                    # push eax
        "DB 04 24"              # fild dword ptr [esp]
        "D9 1C 24"              # fstp dword ptr [esp]
        "6A 01"                 # push 1
        "51"                    # push ecx, overwritten with float argument
        "8B 54 24 08"           # mov edx, dword ptr [esp+8]
        "89 14 24"              # mov dword ptr [esp], edx
        "B9 00 00 00 00"        # mov ecx, offset Money
        "E8 00 00 00 00"        # call CMoney::Adjust(float,bool)
        "83 C4 04"              # add esp, 4 ; remove temp float
        "5D"                    # pop ebp
        "C2 04 00"              # ret 4
    )
    co.insert_section_bytes(sym.section, tail_at, payload)

    get_random = co.symbol("?GetRandom@ldwGameState@@SAHH@Z").index
    money = co.symbol("?Money@@3VCMoney@@A").index
    adjust = co.symbol("?Adjust@CMoney@@QAEXM_N@Z").index
    co.append_relocation(sym.section, tail_at + 0x0B, get_random, REL32)
    co.append_relocation(sym.section, tail_at + 0x29, money, DIR32)
    co.append_relocation(sym.section, tail_at + 0x2E, adjust, REL32)

    co.write(obj_path)
    print("Patched cat shelter Donate choice to subtract 10-100 coins.")


if __name__ == "__main__":
    main()
