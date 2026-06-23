from pathlib import Path
import json
import struct

ROOT = Path(__file__).resolve().parents[1]
OBJ = ROOT / "work" / "desktop_obj_files" / "InventoryManager.obj"
OUT = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"
FURNITURE_RECORDS = OUT / "furniture-records.json"
IMAGE_DESCRIPTORS = OUT / "image-descriptors.json"

LISTS = {
    "gFurnitureList": "?gFurnitureList@@3PAW4EInventoryItem@@A",
    "gFurniture1List": "?gFurniture1List@@3PAW4EInventoryItem@@A",
    "gFurniture2List": "?gFurniture2List@@3PAW4EInventoryItem@@A",
    "gFurniture3List": "?gFurniture3List@@3PAW4EInventoryItem@@A",
    "gFurniture4List": "?gFurniture4List@@3PAW4EInventoryItem@@A",
    "gFurniture5List": "?gFurniture5List@@3PAW4EInventoryItem@@A",
    "gAccessoriesList": "?gAccessoriesList@@3PAW4EInventoryItem@@A",
    "gFurniture6List": "?gFurniture6List@@3PAW4EInventoryItem@@A",
    "gFurniture7List": "?gFurniture7List@@3PAW4EInventoryItem@@A",
    "gFurniture8List": "?gFurniture8List@@3PAW4EInventoryItem@@A",
    "gFurniture9List": "?gFurniture9List@@3PAW4EInventoryItem@@A",
}


def parse_obj(path):
    b = path.read_bytes()
    machine, nsects, timestamp, symptr, nsyms, opthdr, chars = struct.unpack_from("<HHIIIHH", b, 0)
    sections = []
    off = 20 + opthdr
    for i in range(1, nsects + 1):
        raw_name = b[off : off + 8]
        name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
        virt_size, virt_addr, raw_size, raw_ptr, reloc_ptr, line_ptr, nreloc, nline, characteristics = struct.unpack_from("<IIIIIIHHI", b, off + 8)
        sections.append({"index": i, "name": name, "raw_size": raw_size, "raw_ptr": raw_ptr, "reloc_ptr": reloc_ptr, "nreloc": nreloc})
        off += 40

    strtab_ptr = symptr + nsyms * 18
    strtab_size = struct.unpack_from("<I", b, strtab_ptr)[0]
    strtab = b[strtab_ptr : strtab_ptr + strtab_size]

    def sym_name(pos):
        raw = b[pos : pos + 8]
        zeroes, str_off = struct.unpack_from("<II", raw, 0)
        if zeroes == 0 and 0 <= str_off < len(strtab):
            end = strtab.find(b"\0", str_off)
            if end < 0:
                end = len(strtab)
            return strtab[str_off:end].decode("ascii", "replace")
        return raw.split(b"\0", 1)[0].decode("ascii", "replace")

    symbols = []
    pos = symptr
    idx = 0
    while idx < nsyms:
        name = sym_name(pos)
        value, sectnum, typ, storage, aux = struct.unpack_from("<IhHBB", b, pos + 8)
        symbols.append({"index": idx, "name": name, "value": value, "section": sectnum, "type": typ, "storage": storage, "aux": aux})
        pos += 18 * (1 + aux)
        idx += 1 + aux
    return b, sections, symbols


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b, sections, symbols = parse_obj(OBJ)
    syms = {s["name"]: s for s in symbols}
    records = json.loads(FURNITURE_RECORDS.read_text(encoding="utf-8"))["records"]
    image_records = json.loads(IMAGE_DESCRIPTORS.read_text(encoding="utf-8"))["records"]
    furniture_by_item = {r["item_id"]: r for r in records}
    image_by_id = {r["image_id"]: r for r in image_records}

    list_symbols = []
    for label, mangled in LISTS.items():
        s = syms[mangled]
        list_symbols.append({"label": label, "mangled": mangled, "section": s["section"], "value": s["value"]})
    list_symbols.sort(key=lambda x: (x["section"], x["value"]))

    extracted = []
    for i, item in enumerate(list_symbols):
        sec = sections[item["section"] - 1]
        same_sec_after = [x for x in list_symbols if x["section"] == item["section"] and x["value"] > item["value"]]
        end = min([x["value"] for x in same_sec_after] + [sec["raw_size"]])
        size = end - item["value"]
        count = size // 4
        raw = b[sec["raw_ptr"] + item["value"] : sec["raw_ptr"] + item["value"] + count * 4]
        ids = list(struct.unpack("<" + "I" * count, raw)) if count else []
        items = []
        for inventory_id in ids:
            frec = furniture_by_item.get(inventory_id)
            path = None
            if frec:
                img = image_by_id.get(frec["image_id"])
                path = img.get("path") if img else None
            items.append({"item_id": inventory_id, "item_hex": f"0x{inventory_id:X}", "image_id": frec["image_id"] if frec else None, "path": path})
        extracted.append({**item, "byte_length_to_next_list_symbol": size, "count_if_packed_u32": count, "items": items})

    (OUT / "inventory-lists.json").write_text(json.dumps(extracted, indent=2), encoding="utf-8")

    lines = ["# Inventory Category Lists", ""]
    for entry in extracted:
        lines.append(f"## {entry['label']}")
        lines.append("")
        lines.append(f"- Section {entry['section']}, offset `0x{entry['value']:X}`")
        lines.append(f"- Packed count to next list symbol: {entry['count_if_packed_u32']}")
        lines.append("")
        for item in entry["items"][:80]:
            path = item["path"] or "(not furniture/image unknown)"
            lines.append(f"- `{item['item_hex']}` image `{item['image_id']}`: `{path}`")
        lines.append("")
    (OUT / "INVENTORY-LISTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
