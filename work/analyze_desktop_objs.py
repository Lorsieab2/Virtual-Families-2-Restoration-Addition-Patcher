from pathlib import Path
import collections
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OBJ_DIR = ROOT / "work" / "desktop_obj_files"
OUT = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"
DUMPBIN = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64\dumpbin.exe")


def ascii_strings(data: bytes, minimum: int = 4):
    return [m.group(0).decode("ascii", "ignore") for m in re.finditer(rb"[ -~]{%d,}" % minimum, data)]


def run_dumpbin(args, path):
    p = subprocess.run([str(DUMPBIN), *args, str(path)], capture_output=True, text=True, errors="replace")
    return p.stdout + p.stderr


def parse_symbols(text):
    symbols = []
    externals = []
    unresolved = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        left, right = line.split("|", 1)
        name = right.strip()
        if not name:
            continue
        symbols.append(name)
        if "External" in left:
            externals.append(name)
        if "UNDEF" in left:
            unresolved.append(name)
    return symbols, externals, unresolved


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    objs = sorted(OBJ_DIR.glob("*.obj"))

    object_reports = []
    all_symbols = collections.Counter()
    all_externals = collections.Counter()
    all_unresolved = collections.Counter()
    source_paths = collections.Counter()
    interesting_terms = [
        "Furniture",
        "Content",
        "Fmap",
        "fmap",
        "Storage",
        "Inventory",
        "Villager",
        "Behavior",
        "Save",
        "Load",
        "Texture",
        "Image",
        "PVR",
        "Map",
        "HotSpot",
    ]
    interesting = collections.defaultdict(list)

    for obj in objs:
        data = obj.read_bytes()
        strings = ascii_strings(data)
        paths = [s for s in strings if re.search(r"[A-Za-z]:\\|\.cpp$|\.h$|\.hpp$", s)]
        for p in paths:
            source_paths[p] += 1

        sym_text = run_dumpbin(["/symbols"], obj)
        symbols, externals, unresolved = parse_symbols(sym_text)
        all_symbols.update(symbols)
        all_externals.update(externals)
        all_unresolved.update(unresolved)

        for sym in symbols:
            for term in interesting_terms:
                if term.lower() in sym.lower():
                    interesting[term].append({"object": obj.name, "symbol": sym})

        object_reports.append(
            {
                "name": obj.name,
                "size": obj.stat().st_size,
                "string_count": len(strings),
                "source_path_samples": paths[:40],
                "symbol_count": len(symbols),
                "external_count": len(externals),
                "unresolved_count": len(unresolved),
                "external_samples": externals[:80],
                "unresolved_samples": unresolved[:80],
            }
        )

    report = {
        "object_count": len(objs),
        "total_size": sum(o.stat().st_size for o in objs),
        "objects": object_reports,
        "top_source_paths": source_paths.most_common(300),
        "top_symbols": all_symbols.most_common(500),
        "top_external_symbols": all_externals.most_common(500),
        "top_unresolved_symbols": all_unresolved.most_common(500),
        "interesting_symbols": {k: v[:500] for k, v in sorted(interesting.items())},
    }
    (OUT / "desktop-object-inventory.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = []
    lines.append("# VF2 Desktop Object File Analysis")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Object files: {report['object_count']}")
    lines.append(f"- Total object size: {report['total_size']:,} bytes")
    lines.append("- Format: MSVC x86 COFF object files (`4C 01` header observed).")
    lines.append("- Debug sections: `.debug$S` and `.debug$T` are present in sampled objects.")
    lines.append("- Runtime directive observed in `main.obj`: `/DEFAULTLIB:LIBCMT`, `/DEFAULTLIB:OLDNAMES`, `/SECTION:.shr,RWS`.")
    lines.append("")
    lines.append("## Largest Objects")
    lines.append("")
    for item in sorted(object_reports, key=lambda x: -x["size"])[:30]:
        lines.append(f"- `{item['name']}`: {item['size']:,} bytes, {item['symbol_count']} symbols, {item['unresolved_count']} unresolved refs")
    lines.append("")
    lines.append("## Source Path / File Hints")
    lines.append("")
    for path, count in report["top_source_paths"][:80]:
        lines.append(f"- `{path}` ({count})")
    lines.append("")
    lines.append("## Furniture-Relevant Symbols")
    lines.append("")
    for hit in report["interesting_symbols"].get("Furniture", [])[:120]:
        lines.append(f"- `{hit['object']}`: `{hit['symbol']}`")
    lines.append("")
    lines.append("## FMAP / Content-Relevant Symbols")
    lines.append("")
    for term in ["Fmap", "fmap", "Content", "Storage", "Inventory"]:
        hits = report["interesting_symbols"].get(term, [])[:80]
        if not hits:
            continue
        lines.append(f"### {term}")
        for hit in hits:
            lines.append(f"- `{hit['object']}`: `{hit['symbol']}`")
        lines.append("")
    lines.append("## Generated Files")
    lines.append("")
    lines.append("- `desktop-object-inventory.json`: machine-readable dump of object inventory, symbols, paths, externals, and interesting symbol groups.")
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
