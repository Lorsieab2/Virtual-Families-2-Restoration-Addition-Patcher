from pathlib import Path
import json
import struct

ROOT = Path(__file__).resolve().parents[1]
OBJ = ROOT / "work" / "desktop_obj_files" / "theGraphicsManager.obj"
OUT = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"

IMAGE_LIST = "?ImageList@@3PAUImageDescriptor@@A"
IMAGE_INDEX = "?ImageIndex@@3PAPAUImageDescriptor@@A"
DESC_SIZE = 0x30
DESC_COUNT = 0x7770 // DESC_SIZE


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


def relocs_for_section(b, sec):
    out = []
    p = sec["reloc_ptr"]
    for _ in range(sec["nreloc"]):
        vaddr, symidx, typ = struct.unpack_from("<IIH", b, p)
        out.append({"vaddr": vaddr, "symidx": symidx, "type": typ})
        p += 10
    return out


def read_cstr(b, sections, symbol):
    if symbol["section"] <= 0:
        return None
    sec = sections[symbol["section"] - 1]
    off = sec["raw_ptr"] + symbol["value"]
    if off < 0 or off >= len(b):
        return None
    end = b.find(b"\0", off)
    if end < 0:
        end = min(len(b), off + 256)
    raw = b[off:end]
    if not raw:
        return ""
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b, sections, symbols = parse_obj(OBJ)
    sym_by_name = {s["name"]: s for s in symbols}
    sym_by_idx = {s["index"]: s for s in symbols}
    list_sym = sym_by_name[IMAGE_LIST]
    list_sec = sections[list_sym["section"] - 1]
    data = b[list_sec["raw_ptr"] : list_sec["raw_ptr"] + list_sec["raw_size"]]
    relocs = relocs_for_section(b, list_sec)
    reloc_by_vaddr = {r["vaddr"]: r for r in relocs}

    records = []
    for i in range(DESC_COUNT):
        off = list_sym["value"] + i * DESC_SIZE
        vals = list(struct.unpack_from("<" + "I" * (DESC_SIZE // 4), data, off))
        path = None
        r = reloc_by_vaddr.get(off + 4)
        if r:
            path = read_cstr(b, sections, sym_by_idx[r["symidx"]])
        records.append({"index": i, "image_id": vals[0], "path": path, "raw_u32": vals})

    gaps = [r for r in records if not r["path"] or r["image_id"] != r["index"]]
    furniture = [r for r in records if r["path"] and r["path"].lower().startswith("furniture/")]

    report = {
        "descriptor_size": DESC_SIZE,
        "descriptor_count": DESC_COUNT,
        "id_min": min(r["image_id"] for r in records),
        "id_max": max(r["image_id"] for r in records),
        "non_identity_or_missing_path_count": len(gaps),
        "non_identity_or_missing_path_sample": gaps[:80],
        "furniture_count": len(furniture),
        "furniture_records": furniture,
        "records": records,
    }
    (OUT / "image-descriptors.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Image Descriptors",
        "",
        f"- Descriptor size: `0x{DESC_SIZE:X}` / {DESC_SIZE} bytes",
        f"- Descriptor count: {DESC_COUNT}",
        f"- Image ID range: `0x{report['id_min']:X}` to `0x{report['id_max']:X}`",
        f"- Furniture image descriptors: {len(furniture)}",
        "",
        "## First Furniture Images",
        "",
    ]
    for r in furniture[:50]:
        lines.append(f"- image `0x{r['image_id']:X}` / {r['image_id']}: `{r['path']}`")
    (OUT / "IMAGE-DESCRIPTORS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
