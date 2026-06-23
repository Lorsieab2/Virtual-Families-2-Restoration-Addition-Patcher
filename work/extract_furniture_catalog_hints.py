from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OBJ = ROOT / "work" / "desktop_obj_files" / "FurnitureManager.obj"
MOBILE_ASSETS = ROOT / "outputs" / "VF2-Mobile-Furniture-Modded" / "Assets"
OUT = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"
DUMPBIN = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64\dumpbin.exe")


def strings(data: bytes, min_len: int = 4):
    return [m.group(0).decode("ascii", "ignore") for m in re.finditer(rb"[ -~]{%d,}" % min_len, data)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = OBJ.read_bytes()
    ss = strings(data)

    groups = {
        "eFurniture": sorted(set(s for s in ss if s.startswith("eFurniture_"))),
        "eImage": sorted(set(s for s in ss if s.startswith("eImage_"))),
        "eString": sorted(set(s for s in ss if s.startswith("eString_"))),
        "mobile_present_in_desktop_obj": {},
        "mobile_fmaps": [],
    }

    mobile_names = []
    for p in sorted(MOBILE_ASSETS.glob("*.fmap")):
        stem = p.name.removesuffix(".png.fmap")
        mobile_names.append(stem)
        if re.search(r"Chaise|Patio|Birthday|Christmas|Gnome|Snowman|Wreath", stem, re.I):
            groups["mobile_fmaps"].append({"name": p.name, "length": p.stat().st_size})
            groups["mobile_present_in_desktop_obj"][stem] = any(stem in s for s in ss)

    text = subprocess.check_output([str(DUMPBIN), "/all", str(OBJ)], text=True, errors="replace")
    sections = []
    for line in text.splitlines():
        if "SECT" in line and "itemInfo" in line:
            sections.append(line.strip())

    groups["itemInfo_symbols"] = sections
    groups["counts"] = {k: len(v) if isinstance(v, list) else len(v) for k, v in groups.items()}

    (OUT / "furniture-catalog-hints.json").write_text(json.dumps(groups, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Furniture Catalog Hints")
    lines.append("")
    lines.append("This is extracted from `FurnitureManager.obj`. It proves the base relink still uses the desktop furniture catalog.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- `eFurniture_*` strings in `FurnitureManager.obj`: {len(groups['eFurniture'])}")
    lines.append(f"- `eImage_*` strings in `FurnitureManager.obj`: {len(groups['eImage'])}")
    lines.append(f"- `eString_*` strings in `FurnitureManager.obj`: {len(groups['eString'])}")
    lines.append("")
    lines.append("## Catalog Symbols")
    lines.append("")
    for s in sections:
        lines.append(f"- `{s}`")
    lines.append("")
    lines.append("## Mobile/Event FMAPs Checked")
    lines.append("")
    for item in groups["mobile_fmaps"]:
        present = groups["mobile_present_in_desktop_obj"][item["name"].removesuffix(".png.fmap")]
        lines.append(f"- `{item['name']}` ({item['length']} bytes): {'already referenced' if present else 'not referenced by desktop FurnitureManager.obj'}")
    lines.append("")
    lines.append("## Why The Current Rebuild Is Base Desktop")
    lines.append("")
    lines.append("The relink used the unmodified desktop `FurnitureManager.obj`. The mobile `.fmap` and image files can exist beside the game, but no object/store/furniture entry points to them yet.")
    lines.append("")
    lines.append("## Next Patch Point")
    lines.append("")
    lines.append("Patch or replace the furniture catalog path through `CFurnitureManager::GetFmapName`, `LookupFurnitureInfo`, and `itemInfo` / `itemInfoLookup` so new `EInventoryItem` values resolve to mobile `.fmap` names, images, prices, descriptions, storage/store categories, and placement rules.")
    (OUT / "FURNITURE-CATALOG-HINTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
