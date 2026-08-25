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
# The durable contract is WHICH toggle combinations a release must ship,
# not what this release's executables happen to be called or hash to.
# Pinning filenames and hashes made this verifier fail every release after
# B161 -- including the shipped B172, B173 and B174 ZIPs -- and a check
# that fails every real artifact just teaches people to ignore it.
#
# These 19 combinations are identical between B161 and B174. Each variant's
# integrity is still fully verified, against the ZIP's own bytes via
# _verify_file_record, which is what the frozen hashes were duplicating.
EXECUTABLE_VARIANT_REQUIREMENTS = frozenset({
    frozenset({"core_executable"}),
    frozenset({"behavior_patches", "core_executable"}),
    frozenset({"cheat_upgrades", "core_executable"}),
    frozenset({"core_executable", "holiday_ornaments_collection"}),
    frozenset({"core_executable", "island_events"}),
    frozenset({"core_executable", "mobile_renovations"}),
    frozenset({"behavior_patches", "cheat_upgrades", "core_executable"}),
    frozenset({"behavior_patches", "core_executable", "holiday_ornaments_collection"}),
    frozenset({"behavior_patches", "core_executable", "island_events"}),
    frozenset({"cheat_upgrades", "core_executable", "holiday_ornaments_collection"}),
    frozenset({"cheat_upgrades", "core_executable", "island_events"}),
    frozenset({"cheat_upgrades", "core_executable", "mobile_renovations"}),
    frozenset({"core_executable", "holiday_ornaments_collection", "island_events"}),
    frozenset({"behavior_patches", "cheat_upgrades", "core_executable", "holiday_ornaments_collection"}),
    frozenset({"behavior_patches", "cheat_upgrades", "core_executable", "island_events"}),
    frozenset({"behavior_patches", "core_executable", "holiday_ornaments_collection", "island_events"}),
    frozenset({"cheat_upgrades", "core_executable", "holiday_ornaments_collection", "island_events"}),
    frozenset({"behavior_patches", "cheat_upgrades", "core_executable", "holiday_ornaments_collection", "island_events"}),
    frozenset({"behavior_patches", "cheat_upgrades", "core_executable", "holiday_ornaments_collection", "island_events", "mobile_renovations"}),
})
SOUND_ROUTE_NAMES = {"beaker", "Child3", "Child7", "Child8"}
REQUIRED_RUNNERS = {
    "offline_vf2_patcher.py",
    "offline_vf2_patcher_gui.py",
    "vf2_crash_capture.py",
    "crash-capture-manifest.template.json",
    "Launch_GUI.bat",
}
# The apply runner is named for its release, so it is matched by shape rather
# than pinned: pinning "Apply_B161_Patcher.bat" made every later release fail
# this check for shipping its own correctly-named runner.
# Same build-label grammar the exporter uses in infer_build_label(): point
# releases are real -- B155.5 shipped -- so "B\d+" alone would reject a
# valid Apply_B174.5_Patcher.bat.
APPLY_RUNNER_PATTERN = re.compile(r"^Apply_B\d+(?:\.\d+)?_Patcher\.bat$")


def _load_variant_identities(path: Path) -> dict[frozenset[str], tuple[str, int]]:
    """Read compiled variant identities produced from the matrix build.

    Independent of the archive being verified: manifest.json is written by the
    bundle exporter alongside the payload it describes, so checking one against
    the other only proves the bundle agrees with itself. An exporter that
    selected the wrong-but-valid executable for a feature combination would
    record that executable's hash too, and the bundle would verify clean.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"variant identities file is unreadable: {exc}")
    variants = raw.get("variants")
    if not isinstance(variants, list) or not variants:
        _fail("variant identities file lists no variants")
    identities: dict[frozenset[str], tuple[str, int]] = {}
    for entry in variants:
        if not isinstance(entry, dict):
            _fail("variant identities entry is not an object")
        requires = entry.get("requires")
        digest = str(entry.get("sha256", "")).lower()
        size = entry.get("size")
        if not isinstance(requires, list) or not all(isinstance(x, str) for x in requires):
            _fail("variant identities entry has an invalid requires list")
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or not isinstance(size, int) or size <= 0:
            _fail(f"variant identities entry for {sorted(requires)} has an invalid identity")
        key = frozenset(requires)
        if key in identities:
            _fail(f"variant identities file lists {sorted(requires)} twice")
        identities[key] = (digest, size)
    if set(identities) != EXECUTABLE_VARIANT_REQUIREMENTS:
        missing = sorted(sorted(x) for x in EXECUTABLE_VARIANT_REQUIREMENTS - set(identities))
        extra = sorted(sorted(x) for x in set(identities) - EXECUTABLE_VARIANT_REQUIREMENTS)
        _fail(
            "variant identities do not cover the release contract; "
            f"missing={missing} unexpected={extra}"
        )
    return identities


def _fail(message: str) -> None:
    raise ValueError(message)


def _reject_executable_variant_hash_collisions(records: list[dict]) -> None:
    """Refuse a release where two different toggle combinations ship one binary.

    Two combinations sharing one payload hash means two manifest records point
    at the same executable despite representing different feature sets -- e.g.
    the B162 release, where the plain core_executable baseline and the Final
    All-Enabled Native overlay were exported from the same source EXE. Every
    variant is expected to compile distinct code, so a collision means the
    release's executable matrix is wrong, even though a per-variant lookup
    would still resolve each one individually.
    """
    by_hash: dict[str, list[str]] = {}
    for record in records:
        digest = str(record.get("source_sha256", "")).lower()
        label = f"{sorted(_requires(record, 'executable record'))} -> {record.get('source_path')}"
        by_hash.setdefault(digest, []).append(label)
    colliding = [group for group in by_hash.values() if len(group) > 1]
    if colliding:
        _fail(
            "two or more executable variants with different requires share "
            "one payload hash: " + "; ".join(" == ".join(group) for group in colliding)
        )


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


def verify_archive(zip_path: Path | str, identities_path: Path | str | None = None) -> dict:
    """Verify one explicit archive and return a compact evidence summary."""
    path = Path(zip_path)
    archive_path = path
    if not path.is_file():
        _fail(f"ZIP does not exist: {path}")
    identities = (
        _load_variant_identities(Path(identities_path))
        if identities_path is not None
        else None
    )
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
        if len(exe_records) != len(EXECUTABLE_VARIANT_REQUIREMENTS):
            _fail(
                f"expected {len(EXECUTABLE_VARIANT_REQUIREMENTS)} executable "
                f"variants, found {len(exe_records)}"
            )
        _reject_executable_variant_hash_collisions(exe_records)
        exe_hashes: set[str] = set()
        for requires in EXECUTABLE_VARIANT_REQUIREMENTS:
            matching = [
                record
                for record in exe_records
                if frozenset(_requires(record, "executable record")) == requires
            ]
            if len(matching) != 1:
                _fail(f"missing or ambiguous executable variant for {sorted(requires)}")
            record = matching[0]
            source = record.get("source_path")
            if not isinstance(source, str) or not source.lower().endswith(".exe"):
                _fail(f"executable variant {sorted(requires)} has no source path")
            # Identity is checked against the bytes actually in the ZIP rather
            # than a hash frozen at some past release.
            _verify_file_record(zipped, names, root, record, f"executable {source}")
            if identities is not None:
                expected_sha, expected_size = identities[requires]
                if (
                    str(record.get("source_sha256", "")).lower() != expected_sha
                    or record.get("source_size") != expected_size
                ):
                    _fail(
                        f"executable for {sorted(requires)} is not the binary the "
                        f"build compiled for that combination ({source})"
                    )
            if (
                str(record.get("expected_target_sha256", "")).lower() != TARGET_SHA256
                or record.get("expected_target_size") != TARGET_SIZE
            ):
                _fail(f"executable target identity mismatch for {source}")
            exe_hashes.add(str(record.get("source_sha256", "")).lower())

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
        apply_runners = sorted(name for name in runner_files if APPLY_RUNNER_PATTERN.match(name))
        if len(apply_runners) != 1:
            _fail(
                "expected exactly one Apply_B<release>_Patcher.bat runner, found: "
                + (", ".join(apply_runners) if apply_runners else "none")
            )
        return {
            "zip": str(archive_path),
            "root": root,
            "members": len(names),
            "target_sha256": TARGET_SHA256,
            "executable_variants": len(EXECUTABLE_VARIANT_REQUIREMENTS),
            "variant_identities_authenticated": identities is not None,
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
    parser.add_argument(
        "--identities",
        type=Path,
        help=(
            "compiled variant identities from the matrix build "
            "(work/export_release_variant_identities.py). Without this the "
            "executables are only checked for internal consistency, because "
            "the manifest is written by the same tool as the payload."
        ),
    )
    parser.add_argument(
        "--require-identities",
        action="store_true",
        help="fail unless --identities is supplied; use this when gating a release",
    )
    args = parser.parse_args()
    if args.require_identities and args.identities is None:
        parser.error("--require-identities was given without --identities")
    try:
        result = verify_archive(args.zip_path, args.identities)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
