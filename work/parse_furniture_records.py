from pathlib import Path
import json
import struct
import re

ROOT = Path(__file__).resolve().parents[1]
OBJ = ROOT / "work" / "desktop_obj_files" / "FurnitureManager.obj"
OUT = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"

ITEMINFO_SYMBOL = "?itemInfo@@3PAUsFurnitureInfo@@A"
ITEMINFO_LOOKUP_SYMBOL = "?itemInfoLookup@@3PAPAUsFurnitureInfo@@A"
RECORD_SIZE = 0x6C


def parse_coff(path: Path):
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
        name_bytes = b[pos : pos + 8]
        zeroes, str_off = struct.unpack_from("<II", name_bytes, 0)
        if zeroes == 0 and str_off < len(strtab):
            end = strtab.find(b"\0", str_off)
            return strtab[str_off : end if end >= 0 else len(strtab)].decode("ascii", "replace")
        return name_bytes.split(b"\0", 1)[0].decode("ascii", "replace")

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
    b, sections, symbols = parse_coff(OBJ)
    sym_by_name = {s["name"]: s for s in symbols}
    item_sym = sym_by_name[ITEMINFO_SYMBOL]
    sec = sections[item_sym["section"] - 1]
    sec_data = b[sec["raw_ptr"] : sec["raw_ptr"] + sec["raw_size"]]
    item_start = item_sym["value"]
    item_len = 0x6A50
    count = item_len // RECORD_SIZE

    relocs = []
    for i in range(sec["nreloc"]):
        r_off = sec["reloc_ptr"] + i * 10
        vaddr, sym_idx, r_type = struct.unpack_from("<IIH", b, r_off)
        if item_start <= vaddr < item_start + item_len:
            sym = symbols[sym_idx]["name"] if sym_idx < len(symbols) else f"<bad:{sym_idx}>"
            relocs.append({"offset": vaddr - item_start, "record": (vaddr - item_start) // RECORD_SIZE, "field": (vaddr - item_start) % RECORD_SIZE, "symbol": sym, "type": r_type})

    records = []
    for i in range(count):
        off = item_start + i * RECORD_SIZE
        raw = sec_data[off : off + RECORD_SIZE]
        vals = list(struct.unpack("<" + "I" * (RECORD_SIZE // 4), raw))
        rec_relocs = [r for r in relocs if r["record"] == i]
        records.append(
            {
                "index": i,
                "item_id": vals[0],
                "image_id": vals[1],
                "price": vals[2],
                "raw_u32": vals,
                "relocations": rec_relocs,
            }
        )

    field_values = {}
    for field in range(RECORD_SIZE // 4):
        values = [r["raw_u32"][field] for r in records]
        uniq = sorted(set(values))
        field_values[f"0x{field*4:02X}"] = {"unique_count": len(uniq), "min": min(uniq), "max": max(uniq), "sample": uniq[:20]}

    report = {
        "record_size": RECORD_SIZE,
        "item_info_start": item_start,
        "item_info_length": item_len,
        "record_count": count,
        "item_id_min": min(r["item_id"] for r in records),
        "item_id_max": max(r["item_id"] for r in records),
        "field_values": field_values,
        "relocation_count": len(relocs),
        "relocations_by_field": {},
        "records": records,
    }
    by_field = {}
    for r in relocs:
        by_field.setdefault(f"0x{r['field']:02X}", []).append(r["symbol"])
    report["relocations_by_field"] = {k: sorted(set(v))[:50] for k, v in sorted(by_field.items())}

    (OUT / "furniture-records.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# Furniture Records", ""]
    lines.append(f"- Record size: `0x{RECORD_SIZE:X}` / {RECORD_SIZE} bytes")
    lines.append(f"- Record count: {count}")
    lines.append(f"- Item id range in records: `0x{report['item_id_min']:X}` to `0x{report['item_id_max']:X}`")
    lines.append(f"- Relocations inside records: {len(relocs)}")
    lines.append("")
    lines.append("## Inferred Fields From Accessors")
    lines.append("")
    lines.append("- `+0x00`: `EInventoryItem` id")
    lines.append("- `+0x04`: `EImage` id, used by `GetImageGrid` / `GetFmapName`")
    lines.append("- `+0x08`: price or hard-buck display value, used by `GetPrice`")
    lines.append("- `+0x0C`: generation lock level, used by `GetLockGenerationLevel`")
    lines.append("- `+0x14`: short description `StringId`")
    lines.append("- `+0x18`: long description `StringId`")
    lines.append("- `+0x58`: loaded `sFurnitureContentHeader*` cache pointer")
    lines.append("")
    lines.append("## Relocation Fields")
    lines.append("")
    for field, syms in report["relocations_by_field"].items():
        lines.append(f"- `{field}`: {len(syms)} sample symbols")
        for sym in syms[:10]:
            lines.append(f"  - `{sym}`")
    lines.append("")
    lines.append("## First And Last Records")
    lines.append("")
    for r in records[:5] + records[-5:]:
        lines.append(f"- index {r['index']}: item_id `0x{r['item_id']:X}`, image `0x{r['image_id']:X}`, price `{r['price']}`")
    (OUT / "FURNITURE-RECORDS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
