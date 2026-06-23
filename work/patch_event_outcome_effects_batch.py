from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coff_patch import CoffObject

ROOT = Path(__file__).resolve().parents[1]
OBJ_DIR = ROOT / "work" / "patched_mobile_furniture_pack_objs"

DIR32 = 0x06
REL32 = 0x14


def hook_to_tail(co: CoffObject, sym_name: str, expected: bytes, old_size: int, already_rel: bytes | None = None) -> tuple[int, int]:
    sym = co.symbol(sym_name)
    sec = co.section(sym.section)
    base = sec.raw_ptr + sym.value
    if already_rel is not None and bytes(co.buf[base : base + 5]) == already_rel:
        return sym.section, -1
    got = bytes(co.buf[base : base + len(expected)])
    if got != expected:
        raise RuntimeError(f"Unexpected prologue for {sym_name}: {got.hex(' ')}")
    tail_at = sym.value + old_size
    rel = tail_at - (sym.value + 5)
    co.buf[base : base + 5] = b"\xE9" + struct.pack("<i", rel)
    return sym.section, tail_at


def patch_meteorite_rare(co: CoffObject) -> bool:
    # Mobile MeteoriteFallsInYard1 is mapped onto desktop TheNAS. Replace the
    # old invoice/payment behavior with one random rare collectible in the yard.
    sec_index, tail_at = hook_to_tail(
        co,
        "?ImpactGame@CEventTheNAS@@UAEXXZ",
        bytes.fromhex("8B 41 0C F7 D8 6A 01 51 B9"),
        0x1F,
        bytes.fromhex("E9 1A 00 00 00"),
    )
    if tail_at < 0:
        return False

    payload = bytes.fromhex(
        "56"                    # push esi
        "57"                    # push edi
        "6A 14"                 # push 20
        "E8 00 00 00 00"        # call GetRandom
        "83 C4 04"              # add esp, 4
        "83 F8 04"              # cmp eax, 4
        "7C 20"                 # jl family_a
        "83 F8 08"              # cmp eax, 8
        "7C 24"                 # jl family_b
        "83 F8 0C"              # cmp eax, 12
        "7C 28"                 # jl family_c
        "83 F8 10"              # cmp eax, 16
        "7C 2C"                 # jl family_d
        "8D B8 8A 00 00 00"     # lea edi, [eax+8Ah]
        "EB 32"                 # jmp choose_xy
        "8D 78 57"              # family_a: lea edi, [eax+57h]
        "EB 2D"                 # jmp choose_xy
        "8D 78 5F"              # family_b: lea edi, [eax+5Fh]
        "EB 28"                 # jmp choose_xy
        "8D 78 67"              # family_c: lea edi, [eax+67h]
        "EB 23"                 # jmp choose_xy
        "8D B8 82 00 00 00"     # family_d: lea edi, [eax+82h]
        "EB 1B"                 # jmp choose_xy
        "68 04 01 00 00"        # choose_xy: push 260
        "E8 00 00 00 00"        # call GetRandom
        "83 C4 04"              # add esp, 4
        "05 BC 04 00 00"        # add eax, 4BCh
        "8B F0"                 # mov esi, eax
        "6A 7E"                 # push 126
        "E8 00 00 00 00"        # call GetRandom
        "83 C4 04"              # add esp, 4
        "05 25 07 00 00"        # add eax, 725h
        "6A 00"                 # push false
        "50"                    # push y
        "56"                    # push x
        "57"                    # push carrying
        "B9 00 00 00 00"        # mov ecx, offset CollectableItem
        "E8 00 00 00 00"        # call Add
        "5F"                    # pop edi
        "5E"                    # pop esi
        "C3"                    # ret
    )
    co.insert_section_bytes(sec_index, tail_at, payload)

    get_random = co.symbol("?GetRandom@ldwGameState@@SAHH@Z").index
    collectible = co.symbol("?CollectableItem@@3VCCollectableItem@@A").index
    add = co.symbol("?Add@CCollectableItem@@QAEXW4ECarrying@@UldwPoint@@_N@Z").index
    co.append_relocation(sec_index, tail_at + 0x05, get_random, REL32)
    co.append_relocation(sec_index, tail_at + 0x3D, get_random, REL32)
    co.append_relocation(sec_index, tail_at + 0x53, get_random, REL32)
    co.append_relocation(sec_index, tail_at + 0x69, collectible, DIR32)
    co.append_relocation(sec_index, tail_at + 0x6E, add, REL32)
    return True


def patch_teens_mess(co: CoffObject) -> bool:
    # Mobile Teens is mapped onto CareerChangeCouncelor. Choice A ("Sure")
    # should leave the house full of cleanup work; choice B should do nothing.
    sec_index, tail_at = hook_to_tail(
        co,
        "?ImpactGame@CEventCareerChangeCouncelor@@UAEXH@Z",
        bytes.fromhex("55 8B EC 83 7D 08 00 75 0E"),
        0x19,
        bytes.fromhex("E9 14 00 00 00"),
    )
    if tail_at < 0:
        return False

    payload = bytes.fromhex(
        "55"                    # push ebp
        "8B EC"                 # mov ebp, esp
        "83 7D 08 00"           # cmp choice, 0
        "75 42"                 # jne done
        "6A 63"                 # push 99
        "B9 00 00 00 00"        # mov ecx, CollectableItem
        "E8 00 00 00 00"        # call SpawnTrashInHouse
        "6A 63"                 # push 99
        "B9 00 00 00 00"        # mov ecx, CollectableItem
        "E8 00 00 00 00"        # call SpawnStainInHouse
        "6A 63"                 # push 99
        "B9 00 00 00 00"        # mov ecx, CollectableItem
        "E8 00 00 00 00"        # call SpawnSockInHouse
        "5D"                    # pop ebp
        "C2 04 00"              # ret 4
    )
    co.insert_section_bytes(sec_index, tail_at, payload)

    collectible = co.symbol("?CollectableItem@@3VCCollectableItem@@A").index
    trash = co.symbol("?SpawnTrashInHouse@CCollectableItem@@QAEXH@Z").index
    stain = co.symbol("?SpawnStainInHouse@CCollectableItem@@QAEXH@Z").index
    sock = co.append_undefined_symbol("?SpawnSockInHouse@CCollectableItem@@QAEXH@Z")
    co.append_relocation(sec_index, tail_at + 0x0C, collectible, DIR32)
    co.append_relocation(sec_index, tail_at + 0x11, trash, REL32)
    co.append_relocation(sec_index, tail_at + 0x18, collectible, DIR32)
    co.append_relocation(sec_index, tail_at + 0x1D, stain, REL32)
    co.append_relocation(sec_index, tail_at + 0x24, collectible, DIR32)
    co.append_relocation(sec_index, tail_at + 0x29, sock, REL32)
    return True


def patch_strange_package_money(co: CoffObject) -> bool:
    # Mobile StrangePackageOnPorch is mapped onto BoySellingCupcakes. The open
    # outcome says the family finds a few coins, so award 10-100 coins.
    sec_index, tail_at = hook_to_tail(
        co,
        "?ImpactGame@CEventBoySellingCupcakes@@UAEXH@Z",
        bytes.fromhex("55 8B EC 83 7D 08 00 56 6A"),
        0x53,
        bytes.fromhex("E9 4E 00 00 00"),
    )
    if tail_at < 0:
        return False

    payload = bytes.fromhex(
        "55"                    # push ebp
        "8B EC"                 # mov ebp, esp
        "83 7D 08 00"           # cmp choice, 0
        "75 2C"                 # jne done
        "6A 5B"                 # push 91
        "E8 00 00 00 00"        # call GetRandom
        "83 C4 04"              # add esp, 4
        "83 C0 0A"              # add eax, 10
        "50"                    # push eax
        "DB 04 24"              # fild dword ptr [esp]
        "D9 1C 24"              # fstp dword ptr [esp]
        "6A 01"                 # push 1
        "51"                    # reserve float arg
        "8B 54 24 08"           # mov edx, [esp+8]
        "89 14 24"              # mov [esp], edx
        "B9 00 00 00 00"        # mov ecx, Money
        "E8 00 00 00 00"        # call Adjust
        "83 C4 04"              # add esp, 4
        "5D"                    # pop ebp
        "C2 04 00"              # ret 4
    )
    co.insert_section_bytes(sec_index, tail_at, payload)

    get_random = co.symbol("?GetRandom@ldwGameState@@SAHH@Z").index
    money = co.symbol("?Money@@3VCMoney@@A").index
    adjust = co.symbol("?Adjust@CMoney@@QAEXM_N@Z").index
    co.append_relocation(sec_index, tail_at + 0x0B, get_random, REL32)
    co.append_relocation(sec_index, tail_at + 0x28, money, DIR32)
    co.append_relocation(sec_index, tail_at + 0x2D, adjust, REL32)
    return True


def main() -> None:
    obj_path = OBJ_DIR / "IslandEvents.obj"
    co = CoffObject(obj_path)
    changes = []
    if patch_meteorite_rare(co):
        changes.append("meteorite rare collectible")
    if patch_teens_mess(co):
        changes.append("teens mess outcome")
    if patch_strange_package_money(co):
        changes.append("strange package coins")
    co.write(obj_path)
    if changes:
        print("Patched: " + ", ".join(changes))
    else:
        print("Event outcome batch hooks already present.")


if __name__ == "__main__":
    main()
