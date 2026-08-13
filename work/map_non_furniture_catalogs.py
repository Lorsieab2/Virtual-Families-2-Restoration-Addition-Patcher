from pathlib import Path
import json
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
OBJ_DIR = ROOT / "work" / "desktop_obj_files"
OUT = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"

TARGETS = [
    "Collectable.obj",
    "CollectableItem.obj",
    "CollectionScene.obj",
    "CommunityEvent.obj",
    "CommunityEventDefs.obj",
    "CommunityEventDialog.obj",
    "FoodStore.obj",
    "ScrollingStoreScene.obj",
    "thePurchaseDialog.obj",
    "Villager.obj",
    "VillagerBio.obj",
    "VillagerManager.obj",
    "VillagerState.obj",
    "theVillagerScene.obj",
]

KEYWORDS = [
    "Collect",
    "collection",
    "Community",
    "Event",
    "Store",
    "Food",
    "Villager",
    "Body",
    "Head",
    "Hair",
    "Cloth",
    "Skin",
    "Image",
    "Defs",
    "List",
]


def sym_name(buf, strtab, pos):
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
        sections.append({"index": i, "name": name, "raw_size": raw_size, "raw_ptr": raw_ptr, "reloc_ptr": reloc_ptr, "nreloc": nreloc, "chars": characteristics})
        off += 40
    strtab_ptr = symptr + nsyms * 18
    strtab_size = struct.unpack_from("<I", b, strtab_ptr)[0]
    strtab = b[strtab_ptr : strtab_ptr + strtab_size]
    symbols = []
    pos = symptr
    idx = 0
    while idx < nsyms:
        name = sym_name(b, strtab, pos)
        value, sectnum, typ, storage, aux = struct.unpack_from("<IhHBB", b, pos + 8)
        symbols.append({"index": idx, "name": name, "value": value, "section": sectnum, "storage": storage, "aux": aux})
        pos += 18 * (1 + aux)
        idx += 1 + aux
    return b, sections, symbols


def strings(buf):
    out = []
    for m in re.finditer(rb"[ -~]{4,}", buf):
        text = m.group(0).decode("ascii", "ignore")
        if any(k.lower() in text.lower() for k in ["collect", "event", "villager", "body", "hair", "head", "skin", "store", "food", ".png", ".fmap"]):
            out.append({"offset": m.start(), "text": text})
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for name in TARGETS:
        path = OBJ_DIR / name
        if not path.exists():
            continue
        b, sections, symbols = parse_obj(path)
        interesting_symbols = []
        for s in symbols:
            if s["section"] > 0 and any(k.lower() in s["name"].lower() for k in KEYWORDS):
                interesting_symbols.append(s)
        report[name] = {
            "sections": sections,
            "interesting_symbols": interesting_symbols,
            "strings": strings(b)[:500],
        }
    (OUT / "non-furniture-catalog-map.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# Non-Furniture Catalog Map", ""]
    for name, info in report.items():
        lines.append(f"## {name}")
        lines.append("")
        lines.append("### Interesting Symbols")
        lines.append("")
        for s in info["interesting_symbols"][:80]:
            lines.append(f"- `{s['name']}` section {s['section']} value `0x{s['value']:X}`")
        if not info["interesting_symbols"]:
            lines.append("- None found by keyword.")
        lines.append("")
        lines.append("### Relevant Strings")
        lines.append("")
        for st in info["strings"][:80]:
            lines.append(f"- `0x{st['offset']:X}` `{st['text']}`")
        if not info["strings"]:
            lines.append("- None found by keyword.")
        lines.append("")
    (OUT / "NON-FURNITURE-CATALOG-MAP.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
