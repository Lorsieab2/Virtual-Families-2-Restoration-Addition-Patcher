from pathlib import Path
import argparse
import collections
import json
import re
import shutil
import struct
import zipfile
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
APK_NATIVE = ROOT / "work" / "apk_native"
ASSETS = ROOT / "work" / "vf2_obb" / "assets"
OUT = ROOT / "outputs" / "VF2-Mobile-Cpp-Reconstruction"
DEFAULT_XAPK = Path(r"C:\Users\Owner\Downloads\Virtual+Families+2_1.7.16_APKPure.xapk")


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


def collect_port_targets(class_methods):
    target_classes = [
        "GameFS",
        "CPVR",
        "ldwImage",
        "ldwGameState",
        "theGameState",
        "CContentMap",
        "CFurnitureManager",
        "CInventoryManager",
        "CVillager",
        "CVillagerManager",
        "CVillagerPlans",
        "CBehavior",
    ]
    targets = []
    for class_name in target_classes:
        methods = sorted(class_methods.get(class_name, {}))
        if not methods:
            continue
        focus = [
            method
            for method in methods
            if re.search(r"Load|Read|Write|Save|Fmap|Content|Image|Texture|PVR|Storage|Furniture|Plan|State|Path|File|Zip", method, re.I)
        ]
        targets.append(
            {
                "class": class_name,
                "method_count": len(methods),
                "focused_methods": focus[:80],
                "all_methods": methods[:200],
            }
        )
    return targets


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


def extract_xapk_inputs(xapk_path: Path, refresh: bool = False):
    if APK_NATIVE.exists() and ASSETS.exists() and not refresh:
        return
    if not xapk_path.exists():
        raise FileNotFoundError(f"Mobile inputs are missing and XAPK was not found: {xapk_path}")

    if refresh:
        shutil.rmtree(APK_NATIVE, ignore_errors=True)
        shutil.rmtree(ASSETS.parent, ignore_errors=True)

    APK_NATIVE.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(xapk_path) as xapk:
        apk_name = next(name for name in xapk.namelist() if name.lower().endswith(".apk"))
        apk_bytes = xapk.read(apk_name)
        obb_name = next(name for name in xapk.namelist() if name.lower().endswith(".obb"))
        obb_bytes = xapk.read(obb_name)

    with zipfile.ZipFile(BytesIO(apk_bytes)) as apk:
        for info in apk.infolist():
            if info.is_dir() or not info.filename.startswith("lib/") or not info.filename.endswith(".so"):
                continue
            parts = Path(info.filename).parts
            if len(parts) < 3:
                continue
            abi = parts[1]
            lib_name = parts[-1]
            target = APK_NATIVE / f"lib_{abi}_{lib_name}"
            target.write_bytes(apk.read(info))

    with zipfile.ZipFile(BytesIO(obb_bytes)) as obb:
        for info in obb.infolist():
            if info.is_dir() or not info.filename.startswith("assets/"):
                continue
            target = ASSETS.parent / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(obb.read(info))


def main():
    parser = argparse.ArgumentParser(description="Build a VF2 mobile C++ reconstruction report from the XAPK native code and OBB assets.")
    parser.add_argument("--xapk", default=str(DEFAULT_XAPK))
    parser.add_argument("--refresh-inputs", action="store_true", help="Re-extract APK native libraries and OBB assets from the XAPK.")
    args = parser.parse_args()

    extract_xapk_inputs(Path(args.xapk), args.refresh_inputs)
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
        "source_xapk": str(Path(args.xapk)),
        "asset_extension_counts": dict(collections.Counter(p.suffix.lower() or "<none>" for p in ASSETS.iterdir() if p.is_file())),
        "native_libraries": native_report,
        "jni_symbol_count": len(set(jni_symbols)),
        "jni_symbols": sorted(set(jni_symbols))[:200],
        "class_count": len(class_methods),
        "top_classes": [
            {"class": cls, "method_count": len(methods), "sample_methods": sorted(methods)[:40]}
            for cls, methods in sorted(class_methods.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:80]
        ],
        "port_targets": collect_port_targets(class_methods),
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
    lines.append(f"- Native gameplay libraries inventoried: {len(native_report)}.")
    lines.append(f"- Asset files available under `work/vf2_obb/assets`: {sum(inventory['asset_extension_counts'].values())}.")
    lines.append("")
    lines.append("The native library preserves C++ symbol names. The reconstruction should mirror these classes first:")
    lines.append("")
    for item in inventory["top_classes"][:25]:
        lines.append(f"- `{item['class']}`: {item['method_count']} recovered method names; samples: " + ", ".join(f"`{m}`" for m in item["sample_methods"][:10]))
    lines.append("")
    lines.append("## First IDA/Ghidra Port Targets")
    lines.append("")
    for target in inventory["port_targets"]:
        if not target["focused_methods"]:
            continue
        lines.append(f"### {target['class']}")
        for method in target["focused_methods"][:24]:
            lines.append(f"- `{target['class']}::{method}`")
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
