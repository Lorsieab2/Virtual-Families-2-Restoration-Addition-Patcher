#!/usr/bin/env python3
"""Validate B158 mobile-furniture and mobile-sound linkage in a final PE."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from validate_b153_runtime_flags import LinkedPE, validate_one_byte_flag


ROOT = Path(__file__).resolve().parents[1]
SOUND_CONTRACT = ROOT / "data" / "vf2" / "mobile-sound-route-toggle-contract.json"
FMOD_SHA256 = "7c6f7495d0a981f646bc23fdb39c0e349c598f5d6f4ef0ee58311338ae760194"
SOUND_OBJECT_SHA256 = "11730b342977e3f120bf3627e762bebcf9f36976c5cfc34736c89e78523e3bc4"

RUNTIME_FLAG_SECTIONS = {
    "holiday_furniture_goals": ".vf2goal",
    "mobile_furniture_behaviors": ".vf2beh",
    "allow_older_pregnancies": ".vf2preg",
    "same_sex_marriage": ".vf2same",
    "older_villager_mortality": ".vf2mort",
    "store_scroll_bar": ".vf2scrl",
}

FURNITURE_LINK_MARKERS = {
    "reading": b"Reading a book",
    "sitting": b"Needs to sit down",
    "picnic_prepare": b"Preparing a picnic",
    "picnic_active": b"Having a picnic",
    "drinks_prepare": b"Getting some drinks",
    "drinks_active": b"Having a refreshing drink",
    "birthday": b"Celebrating birthday",
    "dreidel": b"Playing Dreidel",
    "hanukkah": b"Celebrating Hanukkah",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(manifest, dict), f"{path}: manifest is not an object")
    return manifest


def _validate_runtime_flags(
    image: LinkedPE,
    furniture_enabled: bool,
    holiday_furniture_enabled: bool,
) -> dict:
    expected = {
        setting_id: (
            1
            if (
                (furniture_enabled and setting_id == "mobile_furniture_behaviors")
                or (holiday_furniture_enabled and setting_id == "holiday_furniture_goals")
            )
            else 0
        )
        for setting_id in RUNTIME_FLAG_SECTIONS
    }
    flags = {
        setting_id: validate_one_byte_flag(image, section_name, expected[setting_id])
        for setting_id, section_name in RUNTIME_FLAG_SECTIONS.items()
    }
    offsets = [int(row["raw_offset"], 16) for row in flags.values()]
    _require(len(offsets) == len(set(offsets)), f"{image.path}: runtime flag offsets overlap")

    original = bytes(image.data)
    enabled = bytearray(original)
    behavior_raw = int(flags["mobile_furniture_behaviors"]["raw_offset"], 16)
    enabled[behavior_raw] = 1
    enabled_once = bytes(enabled)
    enabled[behavior_raw] = 1
    _require(bytes(enabled) == enabled_once, f"{image.path}: furniture enable is not idempotent")
    enabled[behavior_raw] = original[behavior_raw]
    _require(bytes(enabled) == original, f"{image.path}: furniture disable did not restore exact bytes")

    return {
        "flags": flags,
        "toggle_cycle": {
            "section": ".vf2beh",
            "enable_sets_byte_to_01": True,
            "repeated_enable_idempotent": True,
            "disable_after_enable_restores_exact_original": True,
        },
    }


def _validate_furniture(image: LinkedPE, manifest: dict, furniture_enabled: bool) -> dict:
    bindings = manifest.get("MobileFurnitureRuntimeBindings", {})
    manual = bindings.get("manual_dispatch", {})
    autonomous = bindings.get("autonomous", {})
    _require(
        bindings.get("status") == "validated exact 34-row manual and applicable autonomous bindings",
        f"{image.path}: furniture binding contract is not the validated 34-row contract",
    )
    _require(manual.get("item_count") == 34, f"{image.path}: furniture manual count drifted")
    _require(manual.get("family_count") == 17, f"{image.path}: furniture family count drifted")
    _require(manual.get("stock_first") is True, f"{image.path}: stock-first dispatch is not preserved")
    _require(manual.get("stock_false_fallthrough") is True, f"{image.path}: stock false fallthrough is not preserved")
    _require(autonomous.get("item_count") == 23, f"{image.path}: autonomous item count drifted")
    _require(autonomous.get("external_candidate_count") == 12, f"{image.path}: autonomous candidate count drifted")

    evidence = manifest.get("MobileFurnitureBehaviorEvidence", {})
    _require(evidence.get("mobile_item_count") == 63, f"{image.path}: mobile furniture record count drifted")
    _require(evidence.get("source_fmap_count") == 41, f"{image.path}: source fmap count drifted")
    _require(evidence.get("missing_fmap_count") == 22, f"{image.path}: missing fmap count drifted")

    macros = manifest.get("MobileFurnitureBehaviorMacros", {})
    _require(macros.get("status") == "final runtime-gated constructor retargets", f"{image.path}: furniture macro contract drifted")
    _require(macros.get("stock_fallback_preserved") is True, f"{image.path}: furniture stock fallback is not preserved")
    patio = manifest.get("MobilePatioPropExecution", {})
    _require(patio.get("status") == "exact relocation-only wrapper", f"{image.path}: patio wrapper contract drifted")
    _require(patio.get("stock_prop_fallback_preserved") is True, f"{image.path}: patio stock fallback is not preserved")

    markers = {}
    for name, marker in FURNITURE_LINK_MARKERS.items():
        count = image.data.count(marker)
        _require(count >= 1, f"{image.path}: linked furniture marker missing: {marker!r}")
        markers[name] = {"literal": marker.decode("ascii"), "count": count}

    behavior_section = image.section(".vf2beh")
    _require(behavior_section["virtual_size"] == 1, f"{image.path}: .vf2beh is not one byte")
    _require(behavior_section["raw_size"] >= 1, f"{image.path}: .vf2beh has no raw byte")
    _require(bool(behavior_section["characteristics"] & 0x80000000), f"{image.path}: .vf2beh is not writable")

    return {
        "status": "linked_section_readback_and_code_markers_verified",
        "record_count": evidence["mobile_item_count"],
        "manual_item_count": manual["item_count"],
        "manual_family_count": manual["family_count"],
        "autonomous_item_count": autonomous["item_count"],
        "autonomous_external_candidate_count": autonomous["external_candidate_count"],
        "source_fmap_count": evidence["source_fmap_count"],
        "missing_fmap_count": evidence["missing_fmap_count"],
        "stock_first": manual["stock_first"],
        "stock_false_fallthrough": manual["stock_false_fallthrough"],
        "behavior_section": {
            "name": ".vf2beh",
            "raw_offset": f"0x{behavior_section['raw_offset']:x}",
            "rva": f"0x{behavior_section['rva']:x}",
            "value": f"{image.data[behavior_section['raw_offset']]:02x}",
            "writable": True,
            "expected_default": "00" if not furniture_enabled else "01",
        },
        "linked_code_markers": markers,
        "runtime_behavior_qa": "pending_player_test",
    }


def _va_to_raw(image: LinkedPE, va: int) -> int:
    _require(va >= image.image_base, f"{image.path}: VA {va:#x} is below image base")
    return image.rva_to_raw(va - image.image_base)


def _validate_sound(image: LinkedPE, manifest: dict) -> dict:
    contract = json.loads(SOUND_CONTRACT.read_text(encoding="utf-8"))
    routes = contract.get("routes", [])
    _require(len(routes) == 4, f"{image.path}: sound route contract does not contain four routes")
    sound_manifest = manifest.get("MobileSoundAssets", {})
    _require(sound_manifest.get("enabled") is True, f"{image.path}: mobile sound assets are not enabled in the manifest")
    _require(sound_manifest.get("route_count") == 4, f"{image.path}: sound manifest route count drifted")
    _require(sound_manifest.get("source_object_sha256") == SOUND_OBJECT_SHA256, f"{image.path}: Sound.obj source hash drifted")

    fmod = image.path.parent / "fmod.dll"
    _require(fmod.is_file(), f"{image.path}: staged fmod.dll is missing")
    fmod_sha = _sha256(fmod)
    _require(fmod_sha == FMOD_SHA256, f"{image.path}: fmod.dll hash drifted: {fmod_sha}")

    verified_routes = []
    sounds_dir = image.path.parent / "Sounds"
    for route in routes:
        spec = route["sound_obj"]
        mobile_name = spec["replacement_literal"]
        pc_name = spec["preimage_literal"]
        mobile = mobile_name.encode("ascii")
        pc = pc_name.encode("ascii")
        _require(image.data.count(mobile) == 1, f"{image.path}: {mobile_name!r} is not unique")
        _require(image.data.count(pc) == 0, f"{image.path}: stale WAV literal remains: {pc_name!r}")
        literal_raw = image.data.find(mobile)
        literal_rva = image.raw_to_rva(literal_raw)
        literal_va = image.image_base + literal_rva
        pointer_bytes = struct.pack("<I", literal_va)
        pointer_raw = image.data.find(pointer_bytes)
        _require(pointer_raw >= 0, f"{image.path}: no linked pointer resolves to {mobile_name}")
        _require(image.data.find(pointer_bytes, pointer_raw + 1) < 0, f"{image.path}: linked pointer for {mobile_name} is ambiguous")
        _require(pointer_raw >= 8, f"{image.path}: sound record for {mobile_name} is truncated")
        record = struct.unpack_from("<4I", image.data, pointer_raw - 8)
        expected_id = route["raw_id"]
        _require(record[0] == expected_id, f"{image.path}: {mobile_name} pointer is not in record {expected_id:#x}")
        _require(record[2] == literal_va, f"{image.path}: {mobile_name} filename field drifted")
        _require(record[3] == spec["preload_dynamic_flag"], f"{image.path}: {mobile_name} preload flag drifted")

        staged_mobile = sounds_dir / mobile_name
        staged_pc = sounds_dir / pc_name
        _require(staged_mobile.is_file(), f"{image.path}: staged OGG is missing: {mobile_name}")
        _require(_sha256(staged_mobile) == route["mobile_ogg"]["sha256"], f"{image.path}: staged OGG hash drifted: {mobile_name}")
        _require(staged_mobile.stat().st_size == route["mobile_ogg"]["size"], f"{image.path}: staged OGG size drifted: {mobile_name}")
        _require(staged_mobile.read_bytes()[:4] == b"OggS", f"{image.path}: staged OGG signature missing: {mobile_name}")
        _require(staged_pc.is_file(), f"{image.path}: original WAV is missing: {pc_name}")
        _require(_sha256(staged_pc) == route["pc_wav"]["sha256"], f"{image.path}: original WAV hash drifted: {pc_name}")
        _require(staged_pc.read_bytes()[:12][0:4] == b"RIFF" and staged_pc.read_bytes()[8:12] == b"WAVE", f"{image.path}: original WAV signature missing: {pc_name}")

        verified_routes.append({
            "raw_id": route["raw_id_hex"],
            "mobile_filename": mobile_name,
            "mobile_literal_raw_offset": f"0x{literal_raw:x}",
            "mobile_literal_rva": f"0x{literal_rva:x}",
            "mobile_literal_va": f"0x{literal_va:x}",
            "record_raw_offset": f"0x{pointer_raw - 8:x}",
            "filename_pointer_field_raw_offset": f"0x{pointer_raw:x}",
            "record_words": [f"0x{word:x}" for word in record],
            "preload_dynamic_flag": record[3],
        })

    return {
        "status": "linked_route_pointer_readback_verified",
        "route_count": len(verified_routes),
        "fmod_sha256": fmod_sha,
        "routes": verified_routes,
        "audible_parity_qa": "pending_player_test",
    }


def validate(
    exe: Path,
    manifest_path: Path,
    furniture_enabled: bool = False,
    holiday_furniture_enabled: bool = False,
) -> dict:
    image = LinkedPE(exe)
    manifest = _read_manifest(manifest_path)
    runtime = _validate_runtime_flags(image, furniture_enabled, holiday_furniture_enabled)
    furniture = _validate_furniture(image, manifest, furniture_enabled)
    sound = _validate_sound(image, manifest)
    return {
        "status": "passed",
        "contract_id": "vf2-b158-mobile-feature-readback-v1",
        "executable": {
            "path": str(exe),
            "sha256": hashlib.sha256(image.data).hexdigest(),
            "size": len(image.data),
            "image_base": f"0x{image.image_base:x}",
        },
        "runtime_flags": runtime,
        "mobile_furniture_behaviors": furniture,
        "mobile_sound_assets": sound,
        "player_qa": {
            "furniture_behavior_actions": "pending",
            "placement_age_weather_object_gates": "pending",
            "disable_restore_cycle": "pending",
            "fmod_audible_parity": "pending",
            "release_ready": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--expect-furniture-enabled",
        action="store_true",
        help="Expect .vf2beh to be 01 and the other runtime controls to remain 00.",
    )
    parser.add_argument(
        "--expect-holiday-furniture-enabled",
        action="store_true",
        help="Expect .vf2goal to be 01 in a final profile that enables Holiday Furniture.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate(
        args.exe.resolve(),
        args.manifest.resolve(),
        args.expect_furniture_enabled,
        args.expect_holiday_furniture_enabled,
    )
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
