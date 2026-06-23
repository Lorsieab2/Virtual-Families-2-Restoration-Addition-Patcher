from pathlib import Path
import json
import shutil
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coff_patch import CoffObject

ROOT = Path(__file__).resolve().parents[1]
SRC_OBJS = ROOT / "work" / "desktop_obj_files"
PATCHED = ROOT / "work" / "patched_mobile_chaises_objs"
OUT = ROOT / "outputs" / "VF2-Mobile-Additive-Chaise-Proof"
ANALYSIS = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"

ITEMINFO = "?itemInfo@@3PAUsFurnitureInfo@@A"
ITEMLOOKUP = "?itemInfoLookup@@3PAPAUsFurnitureInfo@@A"
IMAGELIST = "?ImageList@@3PAUImageDescriptor@@A"

RECORD_SIZE = 0x6C
DESC_SIZE = 0x30

CHAISES = [
    ("blue", 0x2A9, 0x279, "Furniture/Chaise_blue.png", "_vf2mob_chaise_blue"),
    ("brown", 0x2AA, 0x27A, "Furniture/Chaise_brown.png", "_vf2mob_chaise_brown"),
    ("green", 0x2AB, 0x27B, "Furniture/Chaise_green.png", "_vf2mob_chaise_green"),
    ("red", 0x2AC, 0x27C, "Furniture/Chaise_red.png", "_vf2mob_chaise_red"),
]


def copy_obj_tree():
    if PATCHED.exists():
        shutil.rmtree(PATCHED)
    PATCHED.mkdir(parents=True)
    for obj in SRC_OBJS.glob("*.obj"):
        shutil.copy2(obj, PATCHED / obj.name)


def raw_records_by_item():
    data = json.loads((ANALYSIS / "furniture-records.json").read_text(encoding="utf-8"))
    return {r["item_id"]: r for r in data["records"]}


def patch_u32_patterns(buf: bytearray, old: bytes, new: bytes) -> int:
    n = 0
    start = 0
    while True:
        pos = buf.find(old, start)
        if pos < 0:
            break
        buf[pos : pos + len(old)] = new
        n += 1
        start = pos + len(new)
    return n


def patch_furniture_manager(manifest):
    obj = CoffObject(PATCHED / "FurnitureManager.obj")
    item_sym = obj.symbol(ITEMINFO)
    item_sec = obj.section(item_sym.section)
    insert_off = item_sym.value + 0x6A50
    donors = raw_records_by_item()
    donor_ids = [0x26E, 0x26F, 0x270, 0x272]
    payload = bytearray()
    for donor_id, (_, item_id, image_id, _path, _sym) in zip(donor_ids, CHAISES):
        vals = donors[donor_id]["raw_u32"][:]
        vals[0] = item_id
        vals[1] = image_id
        vals[2] = 650
        vals[0x58 // 4] = 0
        payload += struct.pack("<" + "I" * (RECORD_SIZE // 4), *vals)
    obj.insert_section_bytes(item_sym.section, insert_off, bytes(payload))

    # Furniture item range max: old offset 0xFB, new offset 0xFF.
    patterns = [
        (b"\x3D\xFB\x00\x00\x00", b"\x3D\xFF\x00\x00\x00"),
        (b"\x81\xFE\xFB\x00\x00\x00", b"\x81\xFE\xFF\x00\x00\x00"),
        (b"\x81\xF9\xFB\x00\x00\x00", b"\x81\xF9\xFF\x00\x00\x00"),
        (b"\x81\xFA\xFB\x00\x00\x00", b"\x81\xFA\xFF\x00\x00\x00"),
    ]
    range_patches = sum(patch_u32_patterns(obj.buf, old, new) for old, new in patterns)

    # LookupFurnitureInfo scan-end addend is symbol-relative: itemInfo+0x6A50.
    # Four new 0x6C-byte records make that itemInfo+0x6C00.
    end_patches = patch_u32_patterns(obj.buf, b"\x50\x6A\x00\x00", b"\x00\x6C\x00\x00")

    # itemInfoLookup .bss was 252 pointers. Extend to 256.
    lookup_sym = obj.symbol(ITEMLOOKUP)
    lookup_sec = obj.section(lookup_sym.section)
    obj.grow_bss_section(lookup_sym.section, lookup_sec.raw_size, len(CHAISES) * 4)

    obj.write(PATCHED / "FurnitureManager.obj")
    manifest["FurnitureManager"] = {
        "added_records": len(CHAISES),
        "range_patches": range_patches,
        "scan_end_patches": end_patches,
        "lookup_bss_added_bytes": len(CHAISES) * 4,
    }


def patch_inventory_manager(manifest):
    obj = CoffObject(PATCHED / "InventoryManager.obj")
    list_sym = obj.symbol("?gFurniture2List@@3PAW4EInventoryItem@@A")
    insert_off = list_sym.value + 88 * 4
    payload = struct.pack("<IIII", *(item_id for _color, item_id, _img, _path, _sym in CHAISES))
    obj.insert_section_bytes(list_sym.section, insert_off, payload)

    range_patterns = [
        (b"\x3D\xFB\x00\x00\x00", b"\x3D\xFF\x00\x00\x00"),
        (b"\x81\xFE\xFB\x00\x00\x00", b"\x81\xFE\xFF\x00\x00\x00"),
        (b"\x81\xF9\xFB\x00\x00\x00", b"\x81\xF9\xFF\x00\x00\x00"),
        (b"\x81\xFA\xFB\x00\x00\x00", b"\x81\xFA\xFF\x00\x00\x00"),
    ]
    range_patches = sum(patch_u32_patterns(obj.buf, old, new) for old, new in range_patterns)

    # gFurniture2 count: max index 0x57 -> 0x5B. Sorting calls often pass count 0x58 -> 0x5C.
    count_patches = 0
    count_patches += patch_u32_patterns(obj.buf, b"\x83\xFE\x57", b"\x83\xFE\x5B")
    count_patches += patch_u32_patterns(obj.buf, b"\x6A\x58", b"\x6A\x5C")
    count_patches += patch_u32_patterns(obj.buf, b"\xC7\x45\x08\x58\x00\x00\x00", b"\xC7\x45\x08\x5C\x00\x00\x00")

    # Sorted gFurniture2 bss storage must hold 92 pointers instead of 88.
    sorted_sym = obj.symbol("?gFurniture2ListSorted@@3PAW4EInventoryItem@@A")
    # The sorted arrays are contiguous in .bss; grow at the end of gFurniture2ListSorted.
    obj.grow_bss_section(sorted_sym.section, sorted_sym.value + 88 * 4, 16)

    obj.write(PATCHED / "InventoryManager.obj")
    manifest["InventoryManager"] = {
        "added_category_ids": [hex(x[1]) for x in CHAISES],
        "range_patches": range_patches,
        "count_patches": count_patches,
        "sorted_bss_added_bytes": 16,
    }


def patch_graphics_manager(manifest):
    obj = CoffObject(PATCHED / "theGraphicsManager.obj")
    img_sym = obj.symbol(IMAGELIST)
    img_sec = obj.section(img_sym.section)
    donor_offset = img_sym.value + 206 * DESC_SIZE
    donor = bytes(obj.buf[img_sec.raw_ptr + donor_offset : img_sec.raw_ptr + donor_offset + DESC_SIZE])
    donor_vals = list(struct.unpack("<" + "I" * (DESC_SIZE // 4), donor))

    descriptor_patches = []
    for _color, _item_id, image_id, path, sym_name in CHAISES:
        vals = donor_vals[:]
        vals[0] = image_id
        vals[1] = 0
        vals[2] = 4
        desc_off = img_sym.value + image_id * DESC_SIZE
        obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack("<" + "I" * (DESC_SIZE // 4), *vals)
        symidx = obj.append_undefined_symbol(sym_name)
        obj.append_relocation(img_sym.section, desc_off + 4, symidx)
        descriptor_patches.append({"image_id": hex(image_id), "path": path, "symbol": sym_name})

    obj.write(PATCHED / "theGraphicsManager.obj")
    manifest["theGraphicsManager"] = {"descriptors": descriptor_patches}


def write_strings_source():
    src = PATCHED / "vf2_mobile_chaise_strings.c"
    lines = [
        'const char vf2mob_chaise_blue[] = "Furniture/Chaise_blue.png";',
        'const char vf2mob_chaise_brown[] = "Furniture/Chaise_brown.png";',
        'const char vf2mob_chaise_green[] = "Furniture/Chaise_green.png";',
        'const char vf2mob_chaise_red[] = "Furniture/Chaise_red.png";',
        "",
    ]
    src.write_text("\n".join(lines), encoding="ascii")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    copy_obj_tree()
    manifest = {"additive_items": [{"color": c, "item_id": hex(i), "image_id": hex(img), "path": p} for c, i, img, p, _s in CHAISES]}
    patch_furniture_manager(manifest)
    patch_inventory_manager(manifest)
    patch_graphics_manager(manifest)
    write_strings_source()
    (OUT / "patch-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
