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

    sym = co.symbol("?ImpactGame@CEventAdultProof@@UAEXH@Z")
    sec = co.section(sym.section)
    base = sec.raw_ptr + sym.value

    if bytes(co.buf[base : base + 5]) == bytes.fromhex("E9 1A 00 00 00"):
        print("Clown kitten reward hook already present.")
        return

    expected = bytes.fromhex("55 8B EC 83 7D 08 00 75 14")
    if bytes(co.buf[base : base + len(expected)]) != expected:
        raise RuntimeError("Unexpected CEventAdultProof::ImpactGame prologue")

    old_size = 0x1F
    tail_at = sym.value + old_size
    rel = tail_at - (sym.value + 5)
    co.buf[base : base + 5] = b"\xE9" + struct.pack("<i", rel)

    payload = bytes.fromhex(
        "55"                    # push ebp
        "8B EC"                 # mov ebp, esp
        "83 7D 08 00"           # cmp dword ptr [ebp+8], 0
        "75 29"                 # jne done
        "56"                    # push esi
        "6A 05"                 # push 5
        "E8 00 00 00 00"        # call ldwGameState::GetRandom(int)
        "83 C4 04"              # add esp, 4
        "8D B0 3B 02 00 00"     # lea esi, [eax+23Bh]
        "B9 00 00 00 00"        # mov ecx, offset InventoryManager
        "56"                    # push esi
        "E8 00 00 00 00"        # call CInventoryManager::GetUseCount(item)
        "50"                    # push eax
        "56"                    # push esi
        "B9 00 00 00 00"        # mov ecx, offset ToolTray
        "E8 00 00 00 00"        # call CToolTray::AddItem(item, count)
        "5E"                    # pop esi
        "5D"                    # pop ebp
        "C2 04 00"              # ret 4
    )
    co.insert_section_bytes(sym.section, tail_at, payload)

    get_random = co.symbol("?GetRandom@ldwGameState@@SAHH@Z").index
    inventory = co.symbol("?InventoryManager@@3VCInventoryManager@@A").index
    get_use_count = co.symbol("?GetUseCount@CInventoryManager@@QAEHW4EInventoryItem@@@Z").index
    tool_tray = co.symbol("?ToolTray@@3VCToolTray@@A").index
    add_item = co.symbol("?AddItem@CToolTray@@QAE_NW4EInventoryItem@@H@Z").index

    co.append_relocation(sym.section, tail_at + 0x0D, get_random, REL32)
    co.append_relocation(sym.section, tail_at + 0x1B, inventory, DIR32)
    co.append_relocation(sym.section, tail_at + 0x21, get_use_count, REL32)
    co.append_relocation(sym.section, tail_at + 0x28, tool_tray, DIR32)
    co.append_relocation(sym.section, tail_at + 0x2D, add_item, REL32)

    co.write(obj_path)
    print("Patched clown open-door outcome to add a random cat pet.")


if __name__ == "__main__":
    main()
