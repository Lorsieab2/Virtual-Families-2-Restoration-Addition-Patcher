from pathlib import Path
import json
import struct
import re

ROOT = Path(__file__).resolve().parents[1]
OBJ = ROOT / "work" / "desktop_obj_files" / "FurnitureManager.obj"
OUT = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"


def cstrs(data, min_len=4):
    out = []
    for m in re.finditer(rb"[ -~]{%d,}" % min_len, data):
        out.append({"offset": m.start(), "text": m.group(0).decode("ascii", "ignore")})
    return out


def parse():
    b = OBJ.read_bytes()
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
    strtab_size = struct.unpack_from("<I", b, strtab_ptr)[0] if strtab_ptr + 4 <= len(b) else 0
    strtab = b[strtab_ptr : strtab_ptr + strtab_size]

    def sym_name(pos):
        name_bytes = b[pos : pos + 8]
        zeroes, str_off = struct.unpack_from("<II", name_bytes, 0)
        if zeroes == 0 and str_off < len(strtab):
            end = strtab.find(b"\0", str_off)
            if end < 0:
                end = len(strtab)
            return strtab[str_off:end].decode("ascii", "replace")
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

    report = {"machine": machine, "nsects": nsects, "nsyms": nsyms, "sections": sections, "symbols": symbols}
    return b, report


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b, report = parse()
    syms_by_name = {s["name"]: s for s in report["symbols"]}
    interesting = {}
    for s in report["symbols"]:
        if any(k in s["name"] for k in ["itemInfo", "LookupFurnitureInfo", "GetFmapName", "LoadFmap"]):
            interesting[s["name"]] = s
    report["interesting_symbols"] = interesting

    section_extracts = []
    for sec in report["sections"]:
        if sec["raw_size"] and sec["raw_ptr"]:
            data = b[sec["raw_ptr"] : sec["raw_ptr"] + sec["raw_size"]]
            strs = [x for x in cstrs(data) if any(k in x["text"] for k in ["Furniture_", "Image_", "String_", ".fmap"])]
            if strs:
                section_extracts.append({"section": sec, "strings": strs[:300]})
    report["catalog_string_sections"] = section_extracts

    (OUT / "FurnitureManager-coff-structure.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# FurnitureManager COFF Structure", ""]
    lines.append(f"- Sections: {report['nsects']}")
    lines.append(f"- Symbols: {report['nsyms']}")
    lines.append("")
    lines.append("## Interesting Symbols")
    lines.append("")
    for name, s in interesting.items():
        lines.append(f"- `{name}`: section {s['section']}, value 0x{s['value']:X}, storage {s['storage']}")
    lines.append("")
    lines.append("## Sections With Catalog Strings")
    lines.append("")
    for entry in section_extracts:
        sec = entry["section"]
        lines.append(f"- section {sec['index']} `{sec['name']}` raw_size=0x{sec['raw_size']:X} relocations={sec['nreloc']}")
        for st in entry["strings"][:20]:
            lines.append(f"  - +0x{st['offset']:X}: `{st['text']}`")
    (OUT / "FURNITUREMANAGER-COFF-STRUCTURE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
