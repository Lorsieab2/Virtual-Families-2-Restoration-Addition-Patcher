#!/usr/bin/env python3
"""Export an offline VF2 patch bundle from a generated build folder.

The bundle format is consumed by ``offline_vf2_patcher.py``. It contains a
manifest plus payload files, but not build outputs, caches, or extracted bulk
assets committed to git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_PAYLOAD = ROOT / "work" / "vanilla_runtime_payload"
DEFAULT_EXE_NAME = "Virtual Families 2.exe"
PATCHED_EXE_NAMES = (
    "Virtual Families 2 - Additive Mobile Furniture Pack.exe",
    "Virtual Families 2.exe",
)
BYTE_PATCH_CHUNK_SIZE = 256
ASSET_MODES = ("additive", "all")

SETTINGS = [
    {
        "id": "holiday_furniture",
        "label": "Add Holiday furniture",
        "description": "Adds mobile Holiday furniture records and generated assets.",
        "default": True,
    },
    {
        "id": "holiday_outfits",
        "label": "Add Holiday outfits",
        "description": "Adds folder-backed Holiday outfit body values and runtime frames.",
        "default": True,
    },
    {
        "id": "outfit_store_expansion",
        "label": "Add expanded Outfit store",
        "description": "Adds generated outfit store rows, icons, independent tray item support, and stock outfit body field sync.",
        "default": True,
    },
    {
        "id": "mobile_furniture",
        "label": "Add additional mobile-exclusive furniture",
        "description": "Adds non-Holiday mobile furniture, invisible furniture variants, and supporting assets.",
        "default": True,
    },
    {
        "id": "vf3_tv_assets_recognition",
        "label": "Add VF3 TV assets and recognition",
        "description": "Adds VF3 TV furniture, private animation strips, and TV fmap recognition assets.",
        "default": True,
    },
    {
        "id": "holiday_ornaments_collection",
        "label": "Add Holiday Ornaments collection",
        "description": "Adds mobile Holiday Ornament yard collectibles, collection art, and goals. Experimental until pickup/count/spawn parity is proven.",
        "default": False,
    },
    {
        "id": "mobile_purchases",
        "label": "Add visible mobile purchases",
        "description": "Adds visible Brokerage Account, Food Club, Health Plan, and Lucky Rock store support.",
        "default": True,
    },
    {
        "id": "settings_evict_button",
        "label": "Add Settings Evict button",
        "description": "Enables the mobile-style Settings Evict button.",
        "default": True,
    },
    {
        "id": "mobile_furniture_behaviors",
        "label": "Add mobile furniture behaviors",
        "description": "Enables added villager behavior routes for mobile furniture where implemented.",
        "default": True,
    },
    {
        "id": "island_events",
        "label": "Add mobile Island Events",
        "description": "Adds mobile-exclusive Island Event shell records and implemented outcomes. Experimental until timed event outcomes are crash-free.",
        "default": False,
    },
]

HOLIDAY_FURNITURE_FILES = {
    "CandleOnHolder",
    "CandyCane",
    "ChristmasCookie",
    "ChristmasTree1",
    "ChristmasTree2",
    "Dreidel",
    "GlassOfEggnog",
    "Gnome1",
    "Gnome2",
    "Gnome3",
    "Gnome4",
    "Gnome5",
    "LargeAngel",
    "LargeStar",
    "Menorah",
    "Ornament1",
    "Ornament2",
    "Ornament3",
    "Ornament4",
    "PenguinDecoration",
    "PlateOfCookies",
    "Poinsettia",
    "PolarBearDecoration",
    "RedBow",
    "ReindeerDecoration",
    "SantaGardenDecoration",
    "SantaWallDecoration",
    "Snowman",
    "StockingLarge",
    "StockingSmall",
    "StringOfLeaves",
    "StringOfLights",
    "ThanksgivingCranberry",
    "ThanksgivingDressing",
    "ThanksgivingGravy",
    "ThanksgivingGreenBeans",
    "ThanksgivingHam",
    "ThanksgivingMashedPotatoes",
    "ThanksgivingPie",
    "ThanksgivingSouffle",
    "ThanksgivingTurkey",
    "WelcomeMat",
    "Wreath1",
    "Wreath2",
}

VF3_TV_FILES = {
    "VF3LargeFlatScreenTV",
    "VF3SmallFlatScreenTV",
    "FathersFavoriteTV",
    "VF3LargeFlatScreenTVAnim",
    "VF3LargeFlatScreenTVAnimEast",
    "VF3SmallFlatScreenTVAnim",
    "VF3SmallFlatScreenTVAnimEast",
    "FathersFavoriteTVAnim",
    "FathersFavoriteTVAnimEast",
}

MOBILE_PURCHASE_ICON_FILES = {
    "BrokerUpgrade_icon",
    "FoodClub_icon",
    "HealthPlan_icon",
    "LuckyRock_icon",
}

RUNTIME_REQUIRED_FILES = [
    "ldw.ini",
    "wc.dat",
    "Images/loading.jpg",
    "Images/MapX0Y0.jpg",
    "Images/MenuStoreClothing1.png",
    "Images/female_heads00.png",
    "Images/male_heads00.png",
    "Images/TVAnimBig.png",
    "Images/TVAnimBigE.png",
    "Images/TVAnimSmall.png",
    "Images/TVAnimSmallE.png",
]

RUNTIME_REQUIRED_DIRS = [
    {"path": "Images", "min_files": 1000},
    {"path": "Sounds", "min_files": 300},
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def relative_posix(path: Path) -> str:
    return path.as_posix()


def hex_bytes(data: bytes) -> str:
    return data.hex(" ").upper()


def count_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for child in path.rglob("*") if child.is_file())


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def candidate_manifest_rel_paths(value: str) -> list[Path]:
    text = value.replace("\\", "/").strip()
    if not text:
        return []
    try:
        path = Path(text)
    except ValueError:
        return []

    candidates: list[str] = []
    if path.is_absolute():
        parts = path.parts
        lowered = [part.lower() for part in parts]
        for root_name in ("images", "assets"):
            if root_name not in lowered:
                continue
            index = lowered.index(root_name)
            candidates.append("/".join(parts[index:]))
    else:
        if text.startswith(("Images/", "Assets/")):
            candidates.append(text)
        elif text.startswith(("Furniture/", "VillagerBodies/", "HolidayOutfits/", "CollectionOrnaments/")):
            candidates.append("Images/" + text)
        elif "/" not in text and text.lower().endswith((".png", ".jpg", ".bmp")):
            candidates.append("Images/" + text)
        elif "/" not in text and text.lower().endswith(".fmap"):
            candidates.append("Assets/" + text)

    result = []
    for candidate in candidates:
        rel = Path(candidate)
        if rel.parts and rel.parts[0] in {"Images", "Assets"}:
            result.append(rel)
    return result


def collect_manifest_asset_paths(data: Any) -> set[Path]:
    paths: set[Path] = set()
    if isinstance(data, dict):
        for value in data.values():
            paths.update(collect_manifest_asset_paths(value))
    elif isinstance(data, list):
        for value in data:
            paths.update(collect_manifest_asset_paths(value))
    elif isinstance(data, str):
        paths.update(candidate_manifest_rel_paths(data))
    return paths


def find_patched_exe(build_dir: Path, explicit: str | None) -> Path:
    if explicit:
        path = build_dir / explicit
        if not path.is_file():
            raise FileNotFoundError(f"Patched EXE not found: {path}")
        return path
    for name in PATCHED_EXE_NAMES:
        path = build_dir / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"No patched EXE found in {build_dir}")


def target_file_record(vanilla_exe: Path, target_exe_name: str) -> dict[str, Any]:
    record = {
        "path": target_exe_name,
        "sha256": sha256_file(vanilla_exe),
        "size": vanilla_exe.stat().st_size,
        "note": "Verified vanilla VF2 PC executable.",
    }
    return record


def build_byte_patches(vanilla_exe: Path, patched_exe: Path, target_exe_name: str) -> list[dict[str, Any]]:
    original = vanilla_exe.read_bytes()
    replacement = patched_exe.read_bytes()
    if len(original) != len(replacement):
        raise ValueError(
            f"Cannot export simple byte patches when EXE sizes differ: "
            f"{len(original)} != {len(replacement)}"
        )

    patches: list[dict[str, Any]] = []
    start: int | None = None
    old_chunk = bytearray()
    new_chunk = bytearray()

    def flush() -> None:
        nonlocal start, old_chunk, new_chunk
        if start is None:
            return
        patches.append(
            {
                "file_path": target_exe_name,
                "offset": f"0x{start:X}",
                "expected_original_bytes": hex_bytes(bytes(old_chunk)),
                "replacement_bytes": hex_bytes(bytes(new_chunk)),
                "requires": ["core_native_patch"],
                "note": f"Generated EXE byte diff chunk at 0x{start:X}.",
            }
        )
        start = None
        old_chunk = bytearray()
        new_chunk = bytearray()

    for offset, (old, new) in enumerate(zip(original, replacement, strict=True)):
        if old == new:
            flush()
            continue
        if start is None:
            start = offset
        old_chunk.append(old)
        new_chunk.append(new)
        if len(old_chunk) >= BYTE_PATCH_CHUNK_SIZE:
            flush()
    flush()
    return patches


def native_patch_status(status: str, **extra: Any) -> dict[str, Any]:
    data = {"status": status}
    data.update(extra)
    return data


def setting_for_native_source(path_parts: list[str]) -> str:
    path_text = "/".join(path_parts)
    if "settings_menu/evict" in path_text:
        return "settings_evict_button"
    if "HolidayOrnament" in path_text or "holiday_ornament" in path_text:
        return "holiday_ornaments_collection"
    if "IslandEvents" in path_text:
        return "island_events"
    if "vf3_tv" in path_text or "VF3" in path_text:
        return "vf3_tv_assets_recognition"
    return "core_native_patch"


def collect_native_patch_sources(data: Any, path_parts: list[str] | None = None) -> list[dict[str, Any]]:
    if path_parts is None:
        path_parts = []
    records: list[dict[str, Any]] = []
    if isinstance(data, dict):
        has_explicit_bytes = all(
            key in data
            for key in ("offset", "expected_original_bytes", "replacement_bytes")
        )
        if has_explicit_bytes:
            records.append(
                {
                    "source_path": "/".join(path_parts),
                    "offset": str(data["offset"]),
                    "expected_original_bytes": str(data["expected_original_bytes"]),
                    "replacement_bytes": str(data["replacement_bytes"]),
                    "requires": [setting_for_native_source(path_parts)],
                    "note": str(data.get("note", "")).strip(),
                    "scope": "object_relative",
                    "apply_status": "not_file_offset",
                    "next_step": "Translate object/function-relative offset to final EXE file offset before moving into patches[].",
                }
            )
        for key, value in data.items():
            records.extend(collect_native_patch_sources(value, [*path_parts, str(key)]))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            records.extend(collect_native_patch_sources(value, [*path_parts, str(index)]))
    return records


def setting_for_asset(rel_path: Path) -> str:
    text = relative_posix(rel_path)
    stem = rel_path.stem
    if stem.endswith(".png"):
        stem = stem[:-4]
    parts = rel_path.parts
    if text.startswith("Images/VillagerBodies/") or text.startswith("Images/HolidayOutfits/"):
        return "holiday_outfits"
    if stem in VF3_TV_FILES:
        return "vf3_tv_assets_recognition"
    if text.startswith("Images/CollectionOrnaments/") or "CollectionOrnament" in stem or stem == "collectables_small":
        return "holiday_ornaments_collection"
    if len(parts) >= 3 and parts[0] == "Images" and parts[1] == "Furniture" and stem in HOLIDAY_FURNITURE_FILES:
        return "holiday_furniture"
    if len(parts) >= 2 and parts[0] == "Assets" and stem in HOLIDAY_FURNITURE_FILES:
        return "holiday_furniture"
    if stem in MOBILE_PURCHASE_ICON_FILES:
        return "mobile_purchases"
    if text.startswith("Images/OutfitStoreIcons/") or stem.startswith(("female_", "male_")):
        return "outfit_store_expansion"
    if parts and parts[0] in {"Images", "Assets"}:
        return "mobile_furniture"
    return "core_assets"


def iter_candidate_assets(build_dir: Path, manifest_data: dict[str, Any], asset_mode: str) -> list[Path]:
    roots = [build_dir / "Images", build_dir / "Assets"]
    allowed_paths: set[Path] | None = None
    if asset_mode == "additive":
        allowed_paths = {
            rel
            for rel in collect_manifest_asset_paths(manifest_data)
            if (build_dir / rel).is_file()
        }

    paths: list[Path] = []
    for root in roots:
        if root.is_dir():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if allowed_paths is not None and path.relative_to(build_dir) not in allowed_paths:
                    continue
                paths.append(path)
    return sorted(paths)


def export_asset_payloads(
    build_dir: Path,
    base_payload: Path,
    bundle_dir: Path,
    manifest_data: dict[str, Any],
    asset_mode: str,
) -> list[dict[str, Any]]:
    payload_root = bundle_dir / "payload"
    asset_patches: list[dict[str, Any]] = []
    for source in iter_candidate_assets(build_dir, manifest_data, asset_mode):
        rel = source.relative_to(build_dir)
        base = base_payload / rel
        source_sha = sha256_file(source)
        source_size = source.stat().st_size
        if base.is_file() and sha256_file(base) == source_sha:
            continue

        payload_target = payload_root / rel
        payload_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, payload_target)

        record = {
            "file_path": relative_posix(rel),
            "source_path": relative_posix(Path("payload") / rel),
            "source_sha256": source_sha,
            "source_size": source_size,
            "requires": [setting_for_asset(rel)],
            "note": f"Generated asset payload for {relative_posix(rel)}.",
        }
        if base.is_file():
            record["expected_target_sha256"] = sha256_file(base)
            record["expected_target_size"] = base.stat().st_size
            record["overwrite_existing"] = True
        asset_patches.append(record)
    return asset_patches


def default_settings(include_byte_patches: bool) -> list[dict[str, Any]]:
    settings = list(SETTINGS)
    if include_byte_patches:
        settings.insert(
            0,
            {
                "id": "core_native_patch",
                "label": "Apply core native code/table patches",
                "description": "Applies byte records generated by diffing the vanilla EXE against the patched build EXE.",
                "default": True,
            },
        )
    settings.append(
        {
            "id": "core_assets",
            "label": "Copy core generated assets",
            "description": "Copies generated assets that are not tied to a narrower feature toggle.",
            "default": True,
        }
    )
    return settings


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    build_dir = Path(args.build_dir).resolve()
    bundle_dir = Path(args.out_dir).resolve()
    base_payload = Path(args.base_payload).resolve()
    manifest_in = Path(args.build_manifest).resolve() if args.build_manifest else build_dir / "patch-manifest.json"
    build_manifest_data = load_json(manifest_in) if manifest_in.is_file() else {}
    patched_exe = find_patched_exe(build_dir, args.patched_exe)
    vanilla_exe = Path(args.vanilla_exe).resolve() if args.vanilla_exe else None
    target_exe_name = args.target_exe_name or DEFAULT_EXE_NAME

    if bundle_dir.exists() and any(bundle_dir.iterdir()) and not args.force:
        raise FileExistsError(f"Output bundle directory is not empty: {bundle_dir}")
    bundle_dir.mkdir(parents=True, exist_ok=True)
    if args.force:
        payload_dir = bundle_dir / "payload"
        if payload_dir.exists():
            shutil.rmtree(payload_dir)
        manifest_path = bundle_dir / "manifest.json"
        if manifest_path.exists():
            manifest_path.unlink()

    byte_patches: list[dict[str, Any]] = []
    native_status: dict[str, Any]
    target_files: list[dict[str, Any]] = []
    if vanilla_exe:
        target_files.append(target_file_record(vanilla_exe, target_exe_name))
        if args.include_byte_patches:
            try:
                byte_patches = build_byte_patches(vanilla_exe, patched_exe, target_exe_name)
                native_status = native_patch_status(
                    "byte_diff_exported",
                    byte_patch_count=len(byte_patches),
                    vanilla_size=vanilla_exe.stat().st_size,
                    patched_size=patched_exe.stat().st_size,
                )
            except ValueError as exc:
                if args.strict_byte_patches:
                    raise
                native_status = native_patch_status(
                    "byte_diff_skipped",
                    reason=str(exc),
                    next_step="Extract native patch records from object/linker patch data instead of full EXE diff.",
                    vanilla_size=vanilla_exe.stat().st_size,
                    patched_size=patched_exe.stat().st_size,
                )
        else:
            native_status = native_patch_status(
                "not_requested",
                reason="Vanilla EXE metadata was exported, but --include-byte-patches was not set.",
                vanilla_size=vanilla_exe.stat().st_size,
                patched_size=patched_exe.stat().st_size,
            )
    else:
        native_status = native_patch_status(
            "missing_vanilla_exe",
            reason="No --vanilla-exe was supplied, so target EXE metadata and byte patches were not exported.",
        )

    asset_patches = export_asset_payloads(build_dir, base_payload, bundle_dir, build_manifest_data, args.asset_mode)
    native_patch_sources = collect_native_patch_sources(build_manifest_data)

    asset_counts_by_setting: dict[str, int] = {}
    for row in asset_patches:
        for setting in row.get("requires", []):
            asset_counts_by_setting[setting] = asset_counts_by_setting.get(setting, 0) + 1

    manifest = {
        "manifest_version": 1,
        "name": args.name or f"VF2 offline patch bundle from {build_dir.name}",
        "description": "Generated offline patch bundle for user-provided vanilla VF2 PC installs.",
        "source_build": {
            "build_dir": str(build_dir),
            "build_manifest": str(manifest_in) if manifest_in.is_file() else None,
            "patched_exe": str(patched_exe),
            "build_manifest_keys": sorted(build_manifest_data) if build_manifest_data else [],
        },
        "settings": default_settings(bool(byte_patches)),
        "target_files": target_files,
        "runtime_requirements": {
            "required_files": RUNTIME_REQUIRED_FILES,
            "required_dirs": RUNTIME_REQUIRED_DIRS,
        },
        "patches": byte_patches,
        "native_patch_sources": native_patch_sources,
        "asset_patches": asset_patches,
        "export_summary": {
            "byte_patch_count": len(byte_patches),
            "native_patch_status": native_status,
            "native_patch_source_count": len(native_patch_sources),
            "asset_patch_count": len(asset_patches),
            "asset_counts_by_setting": dict(sorted(asset_counts_by_setting.items())),
            "payload_file_count": count_files(bundle_dir / "payload"),
            "base_payload": str(base_payload),
            "asset_mode": args.asset_mode,
            "target_exe_name": target_exe_name,
            "requires_vanilla_exe_for_apply": not bool(target_files),
        },
    }
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True, help="Generated VF2 build folder to export.")
    parser.add_argument("--out-dir", required=True, help="Bundle output directory.")
    parser.add_argument("--build-manifest", help="Generated build patch-manifest.json. Defaults to BUILD_DIR/patch-manifest.json.")
    parser.add_argument("--base-payload", default=str(DEFAULT_BASE_PAYLOAD), help="Clean base asset payload used for diff filtering.")
    parser.add_argument("--vanilla-exe", help="Original vanilla VF2 EXE used for target hash and optional byte diff export.")
    parser.add_argument("--patched-exe", help="Patched EXE filename inside build dir. Auto-detected by default.")
    parser.add_argument("--target-exe-name", default=DEFAULT_EXE_NAME, help="Relative EXE path expected in the user's game folder.")
    parser.add_argument("--name", help="Manifest display name.")
    parser.add_argument("--asset-mode", choices=ASSET_MODES, default="additive", help="Asset export mode. 'additive' exports manifest-referenced assets; 'all' exports every Images/Assets diff.")
    parser.add_argument("--include-byte-patches", action="store_true", help="Diff vanilla EXE against patched EXE into byte patch records.")
    parser.add_argument("--strict-byte-patches", action="store_true", help="Fail if --include-byte-patches cannot produce byte records.")
    parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty output directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_manifest(args)
    out_dir = Path(args.out_dir).resolve()
    manifest_path = out_dir / "manifest.json"
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "byte_patches": len(manifest["patches"]),
                "asset_patches": len(manifest["asset_patches"]),
                "payload_files": manifest["export_summary"]["payload_file_count"],
                "requires_vanilla_exe_for_apply": manifest["export_summary"]["requires_vanilla_exe_for_apply"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
