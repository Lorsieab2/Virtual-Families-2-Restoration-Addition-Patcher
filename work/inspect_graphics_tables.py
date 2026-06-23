from pathlib import Path
import json
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
OBJ = ROOT / "work" / "desktop_obj_files" / "theGraphicsManager.obj"
OUT = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"


def read_name(buf, strtab, pos):
    raw = buf[pos : pos + 8]
    zeroes, str_off = struct.unpack_from("<II", raw, 0)
    if zeroes == 0 and 0 <= str_off < len(strtab):
        end = strtab.find(b"\0", str_off)
        if end < 0:
            end = len(strtab)
        return strtab[str_off:end].decode("ascii", "replace")
    return raw.split(b"\0", 1)[0].decode("ascii", "replace")


def parse_obj(path):
    b = path.read_bytes()
    machine, nsects, timestamp, symptr, nsyms, opthdr, chars = struct.unpack_from("<HHIIIHH", b, 0)
    sections = []
    off = 20 + opthdr
    for i in range(1, nsects + 1):
        raw_name = b[off : off + 8]
        name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
        virt_size, virt_addr, raw_size, raw_ptr, reloc_ptr, line_ptr, nreloc, nline, characteristics = struct.unpack_from("<IIIIIIHHI", b, off + 8)
        sections.append(
            {
                "index": i,
                "name": name,
                "raw_size": raw_size,
                "raw_ptr": raw_ptr,
                "reloc_ptr": reloc_ptr,
                "nreloc": nreloc,
                "characteristics": characteristics,
            }
        )
        off += 40

    strtab_ptr = symptr + nsyms * 18
    strtab_size = struct.unpack_from("<I", b, strtab_ptr)[0]
    strtab = b[strtab_ptr : strtab_ptr + strtab_size]
    symbols = []
    pos = symptr
    idx = 0
    while idx < nsyms:
        name = read_name(b, strtab, pos)
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b, sections, symbols = parse_obj(OBJ)
    sym_by_idx = {s["index"]: s for s in symbols}
    sym_by_name = {s["name"]: s for s in symbols}

    interesting = {
        name: sym_by_name[name]
        for name in [
            "?ImageList@@3PAUImageDescriptor@@A",
            "?ImageIndex@@3PAPAUImageDescriptor@@A",
            "?GetImageEntry@theGraphicsManagerImpl@@QAEPAUImageDescriptor@@H@Z",
            "?GetImageName@theGraphicsManagerImpl@@QAEPBDH@Z",
            "?GetImageGrid@theGraphicsManagerImpl@@QAEPAVldwImageGrid@@H@Z",
        ]
        if name in sym_by_name
    }

    data_sec = next(s for s in sections if s["index"] == 4)
    image_index_sym = sym_by_name["?ImageIndex@@3PAPAUImageDescriptor@@A"]
    image_index_sec = sections[image_index_sym["section"] - 1]
    data = b[data_sec["raw_ptr"] : data_sec["raw_ptr"] + data_sec["raw_size"]]
    index_data = b[image_index_sec["raw_ptr"] : image_index_sec["raw_ptr"] + image_index_sec["raw_size"]]
    data_relocs = relocs_for_section(b, data_sec)
    index_relocs = relocs_for_section(b, image_index_sec)

    path_strings = []
    for m in re.finditer(rb"(?:Furniture|Images|Rooms|Buttons|UI|Family|Events|Pets)/[ -~]+?\.(?:png|jpg|jpeg|fmap)", b, flags=re.I):
        text = m.group(0).decode("ascii", "replace")
        path_strings.append({"file_offset": m.start(), "text": text})

    # The image list starts at the beginning of section 4. Relocations in the first
    # 0x7000 bytes reveal likely descriptor stride because every path pointer is at +4.
    path_pointer_offsets = []
    for r in data_relocs:
        if r["vaddr"] % 4 == 0 and r["vaddr"] < 0x7000:
            sym = sym_by_idx.get(r["symidx"], {})
            if "??_C@" in sym.get("name", ""):
                path_pointer_offsets.append(r["vaddr"])
    stride_candidates = {}
    for stride in range(16, 96, 4):
        hits = sum(1 for off in path_pointer_offsets if off % stride == 4)
        stride_candidates[stride] = hits

    report = {
        "sections": sections,
        "interesting_symbols": interesting,
        "image_list_section4_raw_size": data_sec["raw_size"],
        "image_index_section": image_index_sec,
        "image_index_symbol": image_index_sym,
        "image_index_bytes": len(index_data),
        "image_index_entries_if_ptrs": len(index_data) // 4,
        "image_index_relocations": len(index_relocs),
        "image_index_first_relocations": [
            {**r, "symbol": sym_by_idx.get(r["symidx"], {}).get("name", "")}
            for r in index_relocs[:30]
        ],
        "path_pointer_offsets_sample": path_pointer_offsets[:80],
        "descriptor_stride_candidates": stride_candidates,
        "path_strings_sample": path_strings[:300],
        "mobile_named_paths_in_obj": [
            p for p in path_strings if any(k in p["text"].lower() for k in ["chaise", "patio", "gnome", "christmas", "birthday", "snowman", "wreath"])
        ],
    }

    (OUT / "graphics-tables.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    best_stride = max(stride_candidates, key=stride_candidates.get)
    lines = [
        "# Graphics Image Tables",
        "",
        f"- `ImageList`: section 4 `.data`, raw size `0x{data_sec['raw_size']:X}`.",
        f"- `ImageIndex`: section {image_index_sec['index']} `{image_index_sec['name']}`, raw size `0x{image_index_sec['raw_size']:X}`.",
        f"- `ImageIndex` has {len(index_data) // 4} pointer slots and {len(index_relocs)} relocations.",
        f"- Best observed `ImageDescriptor` stride candidate: `0x{best_stride:X}` ({best_stride} bytes).",
        f"- Mobile-only path strings already in desktop object: {len(report['mobile_named_paths_in_obj'])}.",
        "",
        "## Interesting Symbols",
        "",
    ]
    for name, sym in interesting.items():
        lines.append(f"- `{name}`: section {sym['section']}, value `0x{sym['value']:X}`, symbol index {sym['index']}")
    lines.extend(["", "## Mobile-Named Paths Already Present", ""])
    if report["mobile_named_paths_in_obj"]:
        for item in report["mobile_named_paths_in_obj"][:100]:
            lines.append(f"- `{item['text']}`")
    else:
        lines.append("- None found.")
    (OUT / "GRAPHICS-IMAGE-TABLES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
