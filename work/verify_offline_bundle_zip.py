"""Fail-closed static verifier for the canonical VF2 offline patcher ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


TARGET_SHA256 = "1582d9e84e1c32f51475be17335c5137c592cebf809748d401ccef99a32b73c3"
TARGET_SIZE = 1_511_424
NATIVE_CORE_SETTINGS = {
    # These settings are implemented in the linked core executable and
    # intentionally have no independent asset/post-asset record.
    "unused_pets",
    "text_fixes",
    "mobile_purchases",
}
ABSENT_ZERO_RECORD_SETTINGS = set()
CORE_ONLY_SETTINGS = {
    "settings_evict_button",
}
B160_EXECUTABLE_VARIANTS = {
    frozenset({"core_executable"}): (
        "payload/Virtual Families 2 - Modded B160.exe",
        "744fac14c3715718c88e6001e37c43bd50621a3f69468bfd29cd094e1d4debc6",
        1_711_616,
    ),
    frozenset({"core_executable", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Mobile Room Renovations.exe",
        "c60f87e4793b19f23cd419f2e480be0d84e1a365412235f93023d19a4b0d43d4",
        1_723_904,
    ),
    frozenset({"core_executable", "island_events", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Island Events.exe",
        "55d03b5d00c3eae54df618be47ab90b6e9c520dac218bea428960c05bd7785e9",
        1_754_624,
    ),
    frozenset({"core_executable", "cheat_upgrades", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Cheat Upgrades.exe",
        "82185c4895293969ea31fda391fdb14a89573261d228c16ce3904011aba2a080",
        1_725_440,
    ),
    frozenset({"core_executable", "holiday_ornaments_collection", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Holiday Ornaments.exe",
        "e2bdfe8d7881f5e141ae4d0344b04168f64856169105a10ef585917918f72bea",
        1_725_952,
    ),
    frozenset({"core_executable", "behavior_patches", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Behavior Patches.exe",
        "b62e9ca54896a145af51e5982788a1cd995052ad966e3f14c3e6bdf83ef4c7bb",
        1_761_280,
    ),
    frozenset({"core_executable", "island_events", "cheat_upgrades", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Island Events + Cheat Upgrades.exe",
        "cd5d60e3077be04440bc404ea49cda1edd9c7b4588848b1af3f91714e55a1b08",
        1_755_648,
    ),
    frozenset({"core_executable", "island_events", "holiday_ornaments_collection", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Island Events + Holiday Ornaments.exe",
        "e6421b46a6c5e1d451b602783cd6dc685e5ef3d826d8e2d1ac602df9c587e4e3",
        1_757_184,
    ),
    frozenset({"core_executable", "cheat_upgrades", "holiday_ornaments_collection", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Cheat Upgrades + Holiday Ornaments.exe",
        "b033ee9488ce9b16b4c00c56df713fa58bca6e3231d5f3ad7c5103daf92c9fbc",
        1_728_512,
    ),
    frozenset({"core_executable", "island_events", "behavior_patches", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Island Events + Behavior Patches.exe",
        "9d34aeb49220d08b105f16892bc2766d44c84d33de14ee2c1958637930dcb521",
        1_791_488,
    ),
    frozenset({"core_executable", "cheat_upgrades", "behavior_patches", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Cheat Upgrades + Behavior Patches.exe",
        "f81f5aa5d8be273df1ecbe597d25cc2926e53ee772668aeb516c1c805adf5b99",
        1_762_304,
    ),
    frozenset({"core_executable", "holiday_ornaments_collection", "behavior_patches", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Holiday Ornaments + Behavior Patches.exe",
        "fb048fa5cf7ef200c45e060e7c5c9dacc11169886f97390ea041628e63818c7b",
        1_764_352,
    ),
    frozenset({"core_executable", "island_events", "cheat_upgrades", "holiday_ornaments_collection", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Island Events + Cheat Upgrades + Holiday Ornaments.exe",
        "1e49f0c7532487daae50dca3ef84afbbb7ba9f8b6c2758bdf31b9b5fcd28a818",
        1_758_208,
    ),
    frozenset({"core_executable", "island_events", "cheat_upgrades", "behavior_patches", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Island Events + Cheat Upgrades + Behavior Patches.exe",
        "088f06ab925e7c1facb204af4951ac2a7bfccc7e5bf876d9e3e4d115c7a57210",
        1_793_536,
    ),
    frozenset({"core_executable", "island_events", "holiday_ornaments_collection", "behavior_patches", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Island Events + Holiday Ornaments + Behavior Patches.exe",
        "41220018f303efbaf07e36c828b8384a97bafd8523de1b43a6e758dfd7b13577",
        1_794_560,
    ),
    frozenset({"core_executable", "cheat_upgrades", "holiday_ornaments_collection", "behavior_patches", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Cheat Upgrades + Holiday Ornaments + Behavior Patches.exe",
        "194e9503ed46ea9c55445a42d1e26a06a1e40b465eadbaf3836c716b23592fad",
        1_765_888,
    ),
    frozenset({"core_executable", "island_events", "cheat_upgrades", "holiday_ornaments_collection", "behavior_patches", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B160 - Final All-Enabled Native.exe",
        "d60930d05f1adaced87bda4e57c4bdd5fe8d614e7b5c40547609cc277ed76f5f",
        1_793_024,
    ),
}

# B161 pins the regenerated source route and includes the two explicit
# mobile-renovation combinations needed to keep feature overlays independent.
EXECUTABLE_VARIANTS = {
    frozenset({"core_executable"}): (
        "payload/Virtual Families 2 - Modded B161.exe",
        "60b4460ae0b110f4ed7d84875fa862f7a531a23be6d293000e7095846d8d3e91",
        1_714_176,
    ),
    frozenset({"core_executable", "behavior_patches"}): (
        "payload/Virtual Families 2 - Modded B161 - Behavior Patches.exe",
        "d9069cce35b1299152345c2c03fc4922dcf6deeaa5d545ce84949abfa58e420e",
        1_751_552,
    ),
    frozenset({
        "core_executable",
        "behavior_patches",
        "cheat_upgrades",
        "holiday_ornaments_collection",
        "island_events",
        "mobile_renovations",
    }): (
        "payload/Virtual Families 2 - Modded B161 - Final All-Enabled Native.exe",
        "ac09ee1828f687526171a056ac4cf2096309ef0f8b6ead9b11d4dd61b52dedee",
        1_797_632,
    ),
    frozenset({"core_executable", "cheat_upgrades"}): (
        "payload/Virtual Families 2 - Modded B161 - Cheat Upgrades.exe",
        "5f09b7d88f6e9061f69af2d609285223c30f82b9ee27e196d4c3e14d1bea3715",
        1_714_688,
    ),
    frozenset({"core_executable", "cheat_upgrades", "behavior_patches"}): (
        "payload/Virtual Families 2 - Modded B161 - Cheat Upgrades + Behavior Patches.exe",
        "0813c4f2e9f0c75ecc54b56d748b714ae7bb535161b8714639a108d75734ce6b",
        1_752_064,
    ),
    frozenset({"core_executable", "cheat_upgrades", "holiday_ornaments_collection"}): (
        "payload/Virtual Families 2 - Modded B161 - Cheat Upgrades + Holiday Ornaments.exe",
        "b396eea70e9c086c1bbbfde2d26ba703326d3f4965d1b3600e59062235268957",
        1_717_760,
    ),
    frozenset({"core_executable", "cheat_upgrades", "holiday_ornaments_collection", "behavior_patches"}): (
        "payload/Virtual Families 2 - Modded B161 - Cheat Upgrades + Holiday Ornaments + Behavior Patches.exe",
        "ca9044b2ad5a982e1699cf70428911d8d4830360db264a53849535049f2aec4d",
        1_755_136,
    ),
    frozenset({"core_executable", "cheat_upgrades", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B161 - Cheat Upgrades + Mobile Room Renovations.exe",
        "0ef2d78b24317a65ec94c4fee0552712bde3869d4fa1bba97995929ff5f2b928",
        1_728_000,
    ),
    frozenset({"core_executable", "holiday_ornaments_collection"}): (
        "payload/Virtual Families 2 - Modded B161 - Holiday Ornaments.exe",
        "0cb16f918009920c1328093eff49d800781468aa878ebfb493ebb4189587bf69",
        1_716_736,
    ),
    frozenset({"core_executable", "holiday_ornaments_collection", "behavior_patches"}): (
        "payload/Virtual Families 2 - Modded B161 - Holiday Ornaments + Behavior Patches.exe",
        "aeb99d713d4293603450c88ad8a0c8fd346dc9494da31cf5e8f1209d26af451a",
        1_754_624,
    ),
    frozenset({"core_executable", "island_events"}): (
        "payload/Virtual Families 2 - Modded B161 - Island Events.exe",
        "c6849caff9d36db90ca82017486b2edf6864b49fb3f0cbff5f8805c25174a61b",
        1_744_384,
    ),
    frozenset({"core_executable", "island_events", "behavior_patches"}): (
        "payload/Virtual Families 2 - Modded B161 - Island Events + Behavior Patches.exe",
        "00f9e60156a8fc962f7ae6b30f710fca1362faa13f77b9bae6ac9f9d5e8b3079",
        1_781_248,
    ),
    frozenset({"core_executable", "island_events", "cheat_upgrades"}): (
        "payload/Virtual Families 2 - Modded B161 - Island Events + Cheat Upgrades.exe",
        "cc8102c19ecdc90b159b72d91c29bb56d4360a74cfc8f2eb6144b258987436fd",
        1_744_384,
    ),
    frozenset({"core_executable", "island_events", "cheat_upgrades", "behavior_patches"}): (
        "payload/Virtual Families 2 - Modded B161 - Island Events + Cheat Upgrades + Behavior Patches.exe",
        "98dfea8774d6747116255efdc8b43055af00be753d5fd98640a7018ea2bce59c",
        1_782_784,
    ),
    frozenset({"core_executable", "island_events", "cheat_upgrades", "holiday_ornaments_collection"}): (
        "payload/Virtual Families 2 - Modded B161 - Island Events + Cheat Upgrades + Holiday Ornaments.exe",
        "df0cf6ab7ea9b04bbaf1a97471841fe520b577f1ce6cfb73ea71b8a42ca7e060",
        1_747_456,
    ),
    frozenset({"core_executable", "island_events", "cheat_upgrades", "holiday_ornaments_collection", "behavior_patches"}): (
        "payload/Virtual Families 2 - Modded B161 - Island Events + Cheat Upgrades + Holiday Ornaments + Behavior Patches.exe",
        "3b3d2de52a5ebf6e92c4bed3adc058ae8c84ea69eb850eecf2d1bdc68c4f52fe",
        1_784_832,
    ),
    frozenset({"core_executable", "island_events", "holiday_ornaments_collection"}): (
        "payload/Virtual Families 2 - Modded B161 - Island Events + Holiday Ornaments.exe",
        "b9ca2202321ad0967cd4ba2797baa58cef38fe30110e00f8935b599ca58b4d45",
        1_746_432,
    ),
    frozenset({"core_executable", "island_events", "holiday_ornaments_collection", "behavior_patches"}): (
        "payload/Virtual Families 2 - Modded B161 - Island Events + Holiday Ornaments + Behavior Patches.exe",
        "11d10a0d5bbb1ee0cccafa387429b3774be23bd8668f2204ed1a3bcdde2bf8ac",
        1_783_808,
    ),
    frozenset({"core_executable", "mobile_renovations"}): (
        "payload/Virtual Families 2 - Modded B161 - Mobile Room Renovations.exe",
        "1b4daef2e7e5cd0937fe0e70dff136215425065a7e7637d1f090d57c7097677a",
        1_726_976,
    ),
}
SOUND_ROUTE_NAMES = {"beaker", "Child3", "Child7", "Child8"}
REQUIRED_RUNNERS = {
    "offline_vf2_patcher.py",
    "offline_vf2_patcher_gui.py",
    "vf2_crash_capture.py",
    "crash-capture-manifest.template.json",
    "Apply_B161_Patcher.bat",
    "Launch_GUI.bat",
}


def _fail(message: str) -> None:
    raise ValueError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a non-empty relative path")
    if "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        _fail(f"{label} is not a safe ZIP-relative path: {value!r}")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        _fail(f"{label} is not a normalized ZIP-relative path: {value!r}")
    PurePosixPath(value)
    return value


def _member_name(root: str, relative: str, label: str) -> str:
    return f"{root}/{_safe_relative(relative, label)}"


def _dict_list(value: object, label: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        _fail(f"{label} must be a list of objects")
    return value


def _requires(record: dict, label: str) -> list[str]:
    value = record.get("requires")
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        _fail(f"{label}.requires must be a duplicate-free list of setting IDs")
    return value


def _read_member(zipped: zipfile.ZipFile, names: set[str], root: str, relative: str, label: str) -> bytes:
    name = _member_name(root, relative, label)
    if name not in names:
        _fail(f"{label} is missing from ZIP: {relative}")
    return zipped.read(name)


def _verify_file_record(zipped: zipfile.ZipFile, names: set[str], root: str, record: dict, label: str) -> None:
    source = record.get("source_path")
    data = _read_member(zipped, names, root, source, f"{label}.source_path")
    expected_size = record.get("source_size")
    expected_sha = str(record.get("source_sha256", "")).lower()
    if not isinstance(expected_size, int) or expected_size <= 0 or len(data) != expected_size:
        _fail(f"{label} source size does not match its manifest")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha) or _sha256(data) != expected_sha:
        _fail(f"{label} source SHA-256 does not match its manifest")


def _verify_zip_inventory(zipped: zipfile.ZipFile, zip_path: Path) -> tuple[str, set[str]]:
    try:
        bad = zipped.testzip()
    except (OSError, zipfile.BadZipFile) as exc:
        _fail(f"ZIP CRC/integrity check failed: {exc}")
    if bad is not None:
        _fail(f"ZIP CRC check failed for {bad}")
    infos = zipped.infolist()
    if not infos:
        _fail("ZIP is empty")
    names = [info.filename for info in infos]
    folded = [name.casefold() for name in names]
    if len(folded) != len(set(folded)):
        _fail("ZIP contains case-insensitive duplicate member names")
    for info in infos:
        name = info.filename
        if not name or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
            _fail(f"ZIP member is unsafe: {name!r}")
        parts = name.split("/")
        if any(part in ("", ".", "..") for part in parts):
            _fail(f"ZIP member is not normalized: {name!r}")
        if stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF):
            _fail(f"ZIP symlink member is forbidden: {name}")
    roots = {name.split("/", 1)[0] for name in names}
    if len(roots) != 1:
        _fail(f"ZIP must contain exactly one top-level root, found {sorted(roots)!r}")
    root = next(iter(roots))
    if root != zip_path.stem:
        _fail(f"ZIP root {root!r} does not match archive stem {zip_path.stem!r}")
    if any(not name.startswith(root + "/") for name in names):
        _fail("ZIP contains a member outside its sole top-level root")
    return root, set(names)


def verify_archive(zip_path: Path | str) -> dict:
    """Verify one explicit archive and return a compact evidence summary."""
    path = Path(zip_path)
    archive_path = path
    if not path.is_file():
        _fail(f"ZIP does not exist: {path}")
    with zipfile.ZipFile(path) as zipped:
        root, names = _verify_zip_inventory(zipped, path)
        manifest_bytes = _read_member(zipped, names, root, "manifest.json", "manifest")
        try:
            manifest = json.loads(manifest_bytes)
        except json.JSONDecodeError as exc:
            _fail(f"manifest.json is invalid JSON: {exc}")
        if not isinstance(manifest, dict):
            _fail("manifest.json must be an object")

        targets = _dict_list(manifest.get("target_files"), "manifest target_files")
        target = [record for record in targets if str(record.get("path", "")).casefold() == "virtual families 2.exe"]
        if len(target) != 1 or target[0].get("size") != TARGET_SIZE or str(target[0].get("sha256", "")).lower() != TARGET_SHA256:
            _fail("manifest target fingerprint is not the pinned vanilla Virtual Families 2.exe")

        settings = _dict_list(manifest.get("settings"), "manifest settings")
        setting_id_values = [item.get("id") for item in settings]
        if any(not isinstance(setting_id, str) or not setting_id for setting_id in setting_id_values):
            _fail("manifest settings contain a missing or invalid ID")
        setting_ids = set(setting_id_values)
        if len(setting_ids) != len(settings):
            _fail("manifest settings contain duplicate IDs")
        if CORE_ONLY_SETTINGS & setting_ids:
            _fail(f"core-only settings are incorrectly advertised as toggles: {sorted(CORE_ONLY_SETTINGS & setting_ids)}")
        if ABSENT_ZERO_RECORD_SETTINGS & setting_ids:
            _fail(f"zero-record settings are incorrectly advertised: {sorted(ABSENT_ZERO_RECORD_SETTINGS & setting_ids)}")

        assets = _dict_list(manifest.get("asset_patches"), "manifest asset_patches")
        posts = _dict_list(manifest.get("post_asset_patches"), "manifest post_asset_patches")
        all_records = assets + posts
        record_settings = {
            req
            for index, record in enumerate(all_records)
            for req in _requires(record, f"manifest patch record {index}")
        }
        if not ABSENT_ZERO_RECORD_SETTINGS.isdisjoint(record_settings):
            _fail("zero-record setting appears in an asset or post record")
        if NATIVE_CORE_SETTINGS & record_settings:
            _fail("native core setting appears in an asset or post record")
        if CORE_ONLY_SETTINGS & record_settings:
            _fail(f"core-only setting appears in an asset or post record: {sorted(CORE_ONLY_SETTINGS & record_settings)}")
        zero_record_settings = {"core_assets"} | NATIVE_CORE_SETTINGS
        if setting_ids - zero_record_settings - record_settings:
            _fail(f"advertised setting has no reachable asset/post record: {sorted(setting_ids - zero_record_settings - record_settings)}")
        if record_settings - setting_ids:
            _fail(f"asset/post record requires an unknown setting: {sorted(record_settings - setting_ids)}")
        native_summary = manifest.get("export_summary", {}).get("native_core_settings", [])
        if not isinstance(native_summary, list) or set(native_summary) != NATIVE_CORE_SETTINGS & setting_ids:
            _fail("manifest native core setting evidence does not match advertised native settings")

        exe_records = [record for record in assets if str(record.get("source_path", "")).lower().endswith(".exe")]
        if len(exe_records) != len(EXECUTABLE_VARIANTS):
            _fail(f"expected {len(EXECUTABLE_VARIANTS)} executable variants, found {len(exe_records)}")
        exe_hashes: set[str] = set()
        for requires, (source, expected_sha, expected_size) in EXECUTABLE_VARIANTS.items():
            matching = [record for record in exe_records if frozenset(_requires(record, "executable record")) == requires]
            if len(matching) != 1 or matching[0].get("source_path") != source:
                _fail(f"missing or ambiguous executable variant for {sorted(requires)}")
            record = matching[0]
            if str(record.get("source_sha256", "")).lower() != expected_sha or record.get("source_size") != expected_size:
                _fail(f"executable manifest identity mismatch for {source}")
            if record.get("expected_target_sha256", "").lower() != TARGET_SHA256 or record.get("expected_target_size") != TARGET_SIZE:
                _fail(f"executable target identity mismatch for {source}")
            _verify_file_record(zipped, names, root, record, f"executable {source}")
            exe_hashes.add(expected_sha)

        renovation_records = [
            record
            for record in assets
            if "mobile_renovations" in _requires(record, "asset record")
            and str(record.get("file_path", "")).startswith("Images/MobileRenovations/")
            and str(record.get("source_path", "")).lower().endswith(".png")
        ]
        if len(renovation_records) != 35:
            _fail(f"expected 35 mobile renovation PNG records, found {len(renovation_records)}")
        for record in renovation_records:
            if not str(record.get("file_path", "")).startswith("Images/MobileRenovations/") or record.get("remove_when_disabled") is not True:
                _fail("mobile renovation record has the wrong destination or removal policy")
            _verify_file_record(zipped, names, root, record, "mobile renovation")

        no_ai_records = [
            record
            for record in assets
            if "no_ai_icons" in _requires(record, "asset record")
        ]
        if "no_ai_icons" in setting_ids:
            if len(no_ai_records) != 15:
                _fail(f"expected 15 No AI Icons records, found {len(no_ai_records)}")
            for record in no_ai_records:
                requires = frozenset(_requires(record, "No AI Icons record"))
                if requires != frozenset({"core_executable", "cheat_upgrades", "no_ai_icons"}):
                    _fail("No AI Icons record has the wrong dependency set")
                path = str(record.get("file_path", ""))
                if not path.startswith("Images/cheat_") or not path.endswith(".png"):
                    _fail("No AI Icons record has the wrong destination")
                if not record.get("restore_source_path") or record.get("restore_requires") != [
                    "core_executable", "cheat_upgrades"
                ]:
                    _fail("No AI Icons record is missing its Cheat Upgrades restore gate")
                _verify_file_record(zipped, names, root, record, "No AI Icons replacement")
                _verify_file_record(
                    zipped,
                    names,
                    root,
                    {
                        "source_path": record["restore_source_path"],
                        "source_sha256": record["restore_source_sha256"],
                        "source_size": record["restore_source_size"],
                    },
                    "No AI Icons restore",
                )
        elif no_ai_records:
            _fail("No AI Icons records exist without the No AI Icons setting")

        sound_records = [record for record in assets if "mobile_sound_assets" in _requires(record, "asset record")]
        if len(sound_records) != 67:
            _fail(f"expected 67 mobile sound records, found {len(sound_records)}")
        restore_count = remove_count = 0
        for record in sound_records:
            _verify_file_record(zipped, names, root, record, "mobile sound")
            data = _read_member(zipped, names, root, record["source_path"], "mobile sound source")
            if not data.startswith(b"OggS"):
                _fail(f"mobile sound payload is not an OGG file: {record['source_path']}")
            has_restore = bool(record.get("restore_source_path"))
            removes = record.get("remove_when_disabled") is True
            if has_restore == removes:
                _fail("each mobile sound record must be exactly restoreable or removable")
            if has_restore:
                restore_count += 1
                restore = _read_member(zipped, names, root, record["restore_source_path"], "mobile sound restore")
                if len(restore) != record.get("restore_source_size") or _sha256(restore) != str(record.get("restore_source_sha256", "")).lower():
                    _fail("mobile sound restore identity does not match its manifest")
            else:
                remove_count += 1
        if (restore_count, remove_count) != (63, 4):
            _fail(f"expected 63 sound restores and 4 removals, found {restore_count} and {remove_count}")
        remove_paths = {record.get("file_path") for record in sound_records if record.get("remove_when_disabled") is True}
        if remove_paths != {f"Sounds/{name}.ogg" for name in SOUND_ROUTE_NAMES}:
            _fail(f"sound removal set is not the four routed sounds: {sorted(remove_paths)!r}")

        route_records = [record for record in posts if frozenset(_requires(record, "post-asset record")) == frozenset({"core_executable", "mobile_sound_assets"})]
        if len(route_records) != 4:
            _fail(f"expected four mobile sound route post records, found {len(route_records)}")
        seen_routes: set[str] = set()
        for record in route_records:
            variants = _dict_list(record.get("variants"), "mobile sound route variants")
            if not variants:
                _fail("mobile sound route variants must not be empty")
            note = str(variants[0].get("note", ""))
            route = next((name for name in SOUND_ROUTE_NAMES if f"{name}.wav" in note and f"{name}.ogg" in note), None)
            if route is None or route in seen_routes:
                _fail("mobile sound post routes are missing or duplicated")
            seen_routes.add(route)
            expected = (route + ".wav").encode("ascii")
            if len(variants) != len(exe_hashes) or {str(v.get("asset_sha256", "")).lower() for v in variants} != exe_hashes:
                _fail(f"mobile sound route {route} does not cover all executable variants")
            replacement = (route + ".ogg").encode("ascii")
            for variant in variants:
                expected_bytes = bytes.fromhex(str(variant.get("expected_asset_bytes", "")))
                replacement_bytes = bytes.fromhex(str(variant.get("replacement_bytes", "")))
                if expected_bytes not in {expected, replacement} or replacement_bytes != replacement:
                    _fail(f"mobile sound route {route} has incorrect byte replacement")
        if seen_routes != SOUND_ROUTE_NAMES:
            _fail("mobile sound post-route set is incomplete")

        export_summary = manifest.get("export_summary")
        if not isinstance(export_summary, dict):
            _fail("manifest export_summary must be an object")
        runner_value = export_summary.get("runner_files")
        if not isinstance(runner_value, list) or any(not isinstance(item, str) for item in runner_value):
            _fail("manifest export_summary.runner_files must be a list of paths")
        runner_files = set(runner_value)
        if not REQUIRED_RUNNERS <= runner_files:
            _fail(f"required patcher/crash-capture runners are missing: {sorted(REQUIRED_RUNNERS - runner_files)}")
        return {
            "zip": str(archive_path),
            "root": root,
            "members": len(names),
            "target_sha256": TARGET_SHA256,
            "executable_variants": len(exe_records),
            "renovation_assets": len(renovation_records),
            "sound_assets": len(sound_records),
            "sound_restores": restore_count,
            "sound_removals": remove_count,
            "sound_routes": len(route_records),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path, help="explicit offline patcher ZIP to verify")
    args = parser.parse_args()
    try:
        result = verify_archive(args.zip_path)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
