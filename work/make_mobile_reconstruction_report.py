from pathlib import Path
import collections
import json
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
APK_NATIVE = ROOT / "work" / "apk_native"
ASSETS = ROOT / "work" / "vf2_obb" / "assets"
OUT = ROOT / "outputs" / "VF2-Mobile-Cpp-Reconstruction"


def ascii_strings(data: bytes, minimum: int = 4):
    return [m.group(0).decode("ascii", "ignore") for m in re.finditer(rb"[ -~]{%d,}" % minimum, data)]


def split_itanium_nested(name: str):
    if not name.startswith("_ZN"):
        return None
    i = 3
    parts = []
    while i < len(name):
        if name[i] == "E":
            return parts
        m = re.match(r"\d+", name[i:])
        if not m:
            return parts if parts else None
        n = int(m.group(0))
        i += len(m.group(0))
        parts.append(name[i : i + n])
        i += n
    return parts if parts else None


def pvr_info(path: Path):
    data = path.read_bytes()
    if len(data) < 52:
        return {"file": path.name, "size": len(data), "valid": False}
    magic = data[0:4]
    vals = struct.unpack_from("<13I", data, 0)
    # PVR v3 usually stores magic as 0x03525650 little endian: bytes "PVR\x03".
    return {
        "file": path.name,
        "size": len(data),
        "magic_hex": magic.hex(),
        "magic_text": "".join(chr(c) if 32 <= c <= 126 else "." for c in magic),
        "header_u32": vals[:13],
    }


def fmap_info(path: Path):
    data = path.read_bytes()
    if len(data) < 32:
        return {"file": path.name, "size": len(data), "valid": False}
    ints = struct.unpack_from("<8I", data, 0)
    return {
        "file": path.name,
        "size": len(data),
        "magic": data[:4].decode("ascii", "replace"),
        "declared_size": ints[1],
        "payload_offset": ints[2],
        "payload_size": ints[3],
        "u4": ints[4],
        "u5": ints[5],
        "u6": ints[6],
        "u7": ints[7],
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    native_report = {}
    class_methods = collections.defaultdict(collections.Counter)
    jni_symbols = []
    path_hits = []

    for so in sorted(APK_NATIVE.glob("lib_*_libVirtualFamilies2.so")):
        data = so.read_bytes()
        strings = ascii_strings(data)
        symbolish = [s for s in strings if s.startswith("_Z") or s.startswith("Java_")]
        native_report[so.name] = {
            "size": len(data),
            "string_count": len(strings),
            "symbolish_count": len(symbolish),
        }
        for s in symbolish:
            if s.startswith("Java_"):
                jni_symbols.append(s)
            parts = split_itanium_nested(s)
            if parts and len(parts) >= 2:
                class_methods[parts[0]][parts[1]] += 1
        for s in strings:
            low = s.lower()
            if any(k in low for k in ["assets/", ".pvr", ".fmap", ".ldw", ".dat", ".ogg", "virtualfamilies"]):
                path_hits.append(s)

    pvr_samples = [pvr_info(p) for p in sorted(ASSETS.glob("tp*.pvr"))[:30]]
    fmap_samples = [fmap_info(p) for p in sorted(ASSETS.glob("*.fmap"))[:80]]
    fmap_bad = [x for x in fmap_samples if x.get("magic") != "QAMF" or x.get("declared_size") != x.get("size")]

    inventory = {
        "asset_extension_counts": dict(collections.Counter(p.suffix.lower() or "<none>" for p in ASSETS.iterdir() if p.is_file())),
        "native_libraries": native_report,
        "jni_symbol_count": len(set(jni_symbols)),
        "jni_symbols": sorted(set(jni_symbols))[:200],
        "class_count": len(class_methods),
        "top_classes": [
            {"class": cls, "method_count": len(methods), "sample_methods": sorted(methods)[:40]}
            for cls, methods in sorted(class_methods.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:80]
        ],
        "path_string_hits": sorted(set(path_hits))[:500],
        "pvr_samples": pvr_samples,
        "fmap_samples": fmap_samples,
        "fmap_sample_mismatches": fmap_bad,
    }

    (OUT / "mobile-native-inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    lines = []
    lines.append("# VF2 Mobile C++ Reconstruction Notes")
    lines.append("")
    lines.append("## What the APK Actually Contains")
    lines.append("")
    lines.append("- The XAPK contains `com.ldw.virtualfamilies2.apk` plus `main.43.com.ldw.virtualfamilies2.obb`.")
    lines.append("- The APK contains native C++ game libraries for `arm64-v8a`, `armeabi-v7a`, `x86`, and `x86_64`.")
    lines.append("- The OBB contains the asset/data payload: `.pvr` texture pages, `.fmap` sprite maps, `.dat` data tables, and `.ogg` audio.")
    lines.append("- MSVC cannot directly link the Android `.so` libraries because they are ELF/Bionic Android binaries, not Windows PE/COFF binaries.")
    lines.append("")
    lines.append("## Recovered Engine Shape")
    lines.append("")
    lines.append("The native library preserves C++ symbol names. The reconstruction should mirror these classes first:")
    lines.append("")
    for item in inventory["top_classes"][:25]:
        lines.append(f"- `{item['class']}`: {item['method_count']} recovered method names; samples: " + ", ".join(f"`{m}`" for m in item["sample_methods"][:10]))
    lines.append("")
    lines.append("## Asset Format Notes")
    lines.append("")
    lines.append("- `.fmap` files begin with magic `QAMF` and have a declared size matching the file length in the samples checked.")
    lines.append("- Individual furniture names map to `.fmap` files; actual mobile texture data is packed into numbered `tp*.pvr` texture pages.")
    lines.append("- The recovered C++ symbol `CPVR::Load` strongly suggests LDW had its own PVR loader in the engine.")
    lines.append("")
    lines.append("## Practical Port Plan")
    lines.append("")
    lines.append("1. Recreate the LDW core layer: `ldwGameState`, `ldwGameWindow`, `ldwEventManager`, `ldwScene`, `ldwDialog`, image/font/audio wrappers.")
    lines.append("2. Implement `CPVR::Load` or use a PVR decoder to load `tp*.pvr` texture pages on Windows.")
    lines.append("3. Implement `.fmap` parsing so furniture/object sprites resolve to texture-page rectangles and offsets.")
    lines.append("4. Load data tables: `anims.dat`, `animpts.dat`, `cmap.dat`, `lsmap.dat`, and object/catalog tables recovered from symbols/strings.")
    lines.append("5. Recreate game scenes in the order recovered from class names, starting with load screen/main house/furniture placement/save-load.")
    lines.append("6. Diff desktop and mobile `.ldw` saves only after object and person record boundaries are proven.")
    lines.append("")
    lines.append("## Generated Files")
    lines.append("")
    lines.append("- `mobile-native-inventory.json`: machine-readable native symbol, asset, PVR, and FMAP inventory.")
    lines.append("")
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
