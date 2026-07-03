#!/usr/bin/env python3
"""Offline JSON byte patcher for user-provided VF2 PC installs.

This tool deliberately avoids runtime injection, process memory editing,
packers, obfuscation, and admin-only install locations. It edits files on disk
only after validating the requested original bytes.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BACKUP_MANIFEST = "vf2_patch_backup_manifest.json"
DEFAULT_BACKUP_ROOT = ".vf2_patch_backups"


class PatchError(RuntimeError):
    """Raised for any validation or patching failure."""


@dataclass(frozen=True)
class BytePatch:
    index: int
    file_path: str
    offset: int
    expected: bytes
    replacement: bytes
    note: str
    requires: tuple[str, ...]


@dataclass(frozen=True)
class AssetPatch:
    index: int
    file_path: str
    source_path: str
    source_sha256: str
    source_size: int | None
    expected_target_sha256: str | None
    expected_target_size: int | None
    overwrite_existing: bool
    note: str
    requires: tuple[str, ...]


@dataclass(frozen=True)
class PatchSetting:
    id: str
    label: str
    description: str
    default: bool


def utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise PatchError("Manifest root must be a JSON object.")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_sha256(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise PatchError(f"{field} is required.")
        return None
    if not isinstance(value, str):
        raise PatchError(f"{field} must be a SHA-256 hex string.")
    text = value.strip().lower()
    if text.startswith("sha256:"):
        text = text[7:]
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise PatchError(f"{field} must be a 64-character SHA-256 hex string.")
    return text


def parse_hex_bytes(value: Any, field: str) -> bytes:
    if isinstance(value, list):
        try:
            return bytes(int(x) for x in value)
        except ValueError as exc:
            raise PatchError(f"{field} list must contain byte values 0..255.") from exc
    if not isinstance(value, str):
        raise PatchError(f"{field} must be a hex string or list of bytes.")
    text = value.strip()
    if text.startswith("hex:"):
        text = text[4:]
    text = re.sub(r"[^0-9a-fA-F]", "", text)
    if len(text) % 2:
        raise PatchError(f"{field} has an odd number of hex digits.")
    try:
        return bytes.fromhex(text)
    except ValueError as exc:
        raise PatchError(f"{field} is not valid hexadecimal.") from exc


def parse_int(value: Any, field: str) -> int:
    if isinstance(value, int):
        if value < 0:
            raise PatchError(f"{field} must be non-negative.")
        return value
    if isinstance(value, str):
        try:
            parsed = int(value, 0)
        except ValueError as exc:
            raise PatchError(f"{field} must be an integer or 0x-prefixed string.") from exc
        if parsed < 0:
            raise PatchError(f"{field} must be non-negative.")
        return parsed
    raise PatchError(f"{field} must be an integer or 0x-prefixed string.")


def normalize_setting_id(value: Any, field: str = "setting id") -> str:
    if not isinstance(value, str) or not value.strip():
        raise PatchError(f"{field} must be a non-empty string.")
    setting_id = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", setting_id):
        raise PatchError(f"{field} contains unsupported characters: {value!r}")
    return setting_id


def split_cli_ids(values: list[str] | None, field: str) -> list[str]:
    ids: list[str] = []
    for value in values or []:
        for part in value.split(","):
            part = part.strip()
            if part:
                ids.append(normalize_setting_id(part, field))
    return ids


def normalize_rel_path(value: Any, field: str = "file path") -> str:
    if not isinstance(value, str) or not value.strip():
        raise PatchError(f"{field} must be a non-empty relative path.")
    raw = value.replace("/", os.sep).replace("\\", os.sep).strip()
    candidate = Path(raw)
    if candidate.is_absolute() or candidate.drive:
        raise PatchError(f"{field} must be relative: {value!r}")
    parts = candidate.parts
    if any(part in ("", ".", "..") for part in parts):
        raise PatchError(f"{field} must not contain '.', '..', or empty segments: {value!r}")
    return str(Path(*parts))


def resolve_under_game_dir(game_dir: Path, rel_path: str) -> Path:
    root = game_dir.resolve()
    resolved = (root / rel_path).resolve()
    if resolved != root and root not in resolved.parents:
        raise PatchError(f"Path escapes game directory: {rel_path}")
    return resolved


def resolve_under_manifest_dir(manifest_dir: Path, rel_path: str) -> Path:
    root = manifest_dir.resolve()
    resolved = (root / rel_path).resolve()
    if resolved != root and root not in resolved.parents:
        raise PatchError(f"Path escapes manifest directory: {rel_path}")
    return resolved


def pe_timestamp(path: Path) -> int | None:
    try:
        with path.open("rb") as handle:
            dos = handle.read(0x40)
            if len(dos) < 0x40 or dos[:2] != b"MZ":
                return None
            pe_off = struct.unpack_from("<I", dos, 0x3C)[0]
            handle.seek(pe_off)
            pe = handle.read(0x18)
            if len(pe) < 0x18 or pe[:4] != b"PE\0\0":
                return None
            return struct.unpack_from("<I", pe, 8)[0]
    except OSError:
        return None


def windows_file_versions(path: Path) -> dict[str, str]:
    if os.name != "nt":
        return {}

    class VSFixedFileInfo(ctypes.Structure):
        _fields_ = [
            ("dwSignature", ctypes.c_uint32),
            ("dwStrucVersion", ctypes.c_uint32),
            ("dwFileVersionMS", ctypes.c_uint32),
            ("dwFileVersionLS", ctypes.c_uint32),
            ("dwProductVersionMS", ctypes.c_uint32),
            ("dwProductVersionLS", ctypes.c_uint32),
            ("dwFileFlagsMask", ctypes.c_uint32),
            ("dwFileFlags", ctypes.c_uint32),
            ("dwFileOS", ctypes.c_uint32),
            ("dwFileType", ctypes.c_uint32),
            ("dwFileSubtype", ctypes.c_uint32),
            ("dwFileDateMS", ctypes.c_uint32),
            ("dwFileDateLS", ctypes.c_uint32),
        ]

    def dotted(ms: int, ls: int) -> str:
        return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"

    try:
        version = ctypes.windll.version  # type: ignore[attr-defined]
        size = version.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return {}
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
            return {}
        info_ptr = ctypes.c_void_p()
        info_len = ctypes.c_uint()
        if not version.VerQueryValueW(buffer, "\\", ctypes.byref(info_ptr), ctypes.byref(info_len)):
            return {}
        if info_len.value < ctypes.sizeof(VSFixedFileInfo):
            return {}
        info = ctypes.cast(info_ptr, ctypes.POINTER(VSFixedFileInfo)).contents
        if info.dwSignature != 0xFEEF04BD:
            return {}
        return {
            "file_version": dotted(info.dwFileVersionMS, info.dwFileVersionLS),
            "product_version": dotted(info.dwProductVersionMS, info.dwProductVersionLS),
        }
    except Exception:
        return {}


def manifest_settings(manifest: dict[str, Any]) -> dict[str, PatchSetting]:
    raw_settings = manifest.get("settings", [])
    settings: dict[str, PatchSetting] = {}
    rows: list[dict[str, Any]]
    if isinstance(raw_settings, dict):
        rows = []
        for setting_id, raw in raw_settings.items():
            if raw is None:
                raw = {}
            if not isinstance(raw, dict):
                raise PatchError(f"Setting {setting_id!r} must be an object.")
            rows.append({"id": setting_id, **raw})
    elif isinstance(raw_settings, list):
        rows = raw_settings
    else:
        raise PatchError("Manifest 'settings' must be an object or array when present.")

    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise PatchError(f"Setting #{index} must be an object.")
        setting_id = normalize_setting_id(raw.get("id"), f"setting #{index} id")
        if setting_id in settings:
            raise PatchError(f"Duplicate setting id: {setting_id}")
        settings[setting_id] = PatchSetting(
            id=setting_id,
            label=str(raw.get("label", setting_id)).strip() or setting_id,
            description=str(raw.get("description", "")).strip(),
            default=bool(raw.get("default", False)),
        )
    return settings


def record_requires(raw: dict[str, Any], field: str) -> tuple[str, ...]:
    values: list[Any] = []
    for key in ("requires", "settings"):
        value = raw.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif isinstance(value, str):
            values.extend(part.strip() for part in value.split(",") if part.strip())
        elif value is not None:
            raise PatchError(f"{field} {key!r} must be a string or array.")
    for key in ("setting", "feature"):
        value = raw.get(key)
        if value is not None:
            values.append(value)
    normalized: list[str] = []
    for index, value in enumerate(values):
        setting_id = normalize_setting_id(value, f"{field} setting #{index}")
        if setting_id not in normalized:
            normalized.append(setting_id)
    return tuple(normalized)


def ensure_known_settings(requires: tuple[str, ...], settings: dict[str, PatchSetting], field: str) -> None:
    unknown = [setting_id for setting_id in requires if setting_id not in settings]
    if unknown:
        raise PatchError(f"{field} references unknown setting(s): {', '.join(unknown)}")


def record_is_active(requires: tuple[str, ...], enabled_settings: set[str]) -> bool:
    return set(requires).issubset(enabled_settings)


def resolve_enabled_settings(manifest: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, PatchSetting], set[str]]:
    settings = manifest_settings(manifest)
    if args.enable_all and args.disable_all:
        raise PatchError("--enable-all and --disable-all cannot be used together.")

    if args.enable_all:
        enabled = set(settings)
    elif args.disable_all:
        enabled = set()
    else:
        enabled = {setting_id for setting_id, setting in settings.items() if setting.default}

    enable_ids = split_cli_ids(args.enable, "--enable")
    disable_ids = split_cli_ids(args.disable, "--disable")
    for setting_id in enable_ids + disable_ids:
        if setting_id not in settings:
            raise PatchError(f"Unknown setting: {setting_id}")
    enabled.update(enable_ids)
    enabled.difference_update(disable_ids)
    return settings, enabled


def settings_log(settings: dict[str, PatchSetting], enabled: set[str]) -> dict[str, Any]:
    return {
        "enabled": sorted(enabled),
        "disabled": sorted(set(settings) - enabled),
        "available": [
            {
                "id": setting.id,
                "label": setting.label,
                "description": setting.description,
                "default": setting.default,
                "enabled": setting.id in enabled,
            }
            for setting in settings.values()
        ],
    }


def count_files(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())


def manifest_runtime_requirements(
    manifest: dict[str, Any],
    settings: dict[str, PatchSetting],
    enabled_settings: set[str],
) -> list[dict[str, Any]]:
    raw = manifest.get("runtime_requirements", manifest.get("required_runtime"))
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise PatchError("Manifest 'runtime_requirements' must be an object when present.")

    requirements: list[dict[str, Any]] = []
    for key in ("files", "required_files"):
        rows = raw.get(key, [])
        if not isinstance(rows, list):
            raise PatchError(f"runtime_requirements.{key} must be an array.")
        for index, row in enumerate(rows):
            if isinstance(row, str):
                requirements.append({"kind": "file", "path": normalize_rel_path(row, f"{key} #{index}")})
                continue
            if not isinstance(row, dict):
                raise PatchError(f"runtime_requirements.{key} #{index} must be a string or object.")
            requires = record_requires(row, f"runtime requirement {key} #{index}")
            ensure_known_settings(requires, settings, f"Runtime requirement {key} #{index}")
            if not record_is_active(requires, enabled_settings):
                continue
            requirements.append({
                "kind": "file",
                "path": normalize_rel_path(row.get("path", row.get("file_path", row.get("file"))), f"{key} #{index} path"),
                "note": str(row.get("note", "")).strip(),
            })

    for key in ("directories", "required_dirs"):
        rows = raw.get(key, [])
        if not isinstance(rows, list):
            raise PatchError(f"runtime_requirements.{key} must be an array.")
        for index, row in enumerate(rows):
            if isinstance(row, str):
                requirements.append({"kind": "directory", "path": normalize_rel_path(row, f"{key} #{index}")})
                continue
            if not isinstance(row, dict):
                raise PatchError(f"runtime_requirements.{key} #{index} must be a string or object.")
            requires = record_requires(row, f"runtime requirement {key} #{index}")
            ensure_known_settings(requires, settings, f"Runtime requirement {key} #{index}")
            if not record_is_active(requires, enabled_settings):
                continue
            min_files = row.get("min_files")
            requirements.append({
                "kind": "directory",
                "path": normalize_rel_path(row.get("path", row.get("dir", row.get("directory"))), f"{key} #{index} path"),
                "min_files": None if min_files is None else parse_int(min_files, f"{key} #{index} min_files"),
                "note": str(row.get("note", "")).strip(),
            })

    return requirements


def verify_runtime_requirements(
    game_dir: Path,
    manifest: dict[str, Any],
    settings: dict[str, PatchSetting],
    enabled_settings: set[str],
) -> list[dict[str, Any]]:
    checks = []
    for requirement in manifest_runtime_requirements(manifest, settings, enabled_settings):
        rel_path = str(requirement["path"])
        path = resolve_under_game_dir(game_dir, rel_path)
        if requirement["kind"] == "file":
            if not path.is_file():
                raise PatchError(f"Required runtime file is missing: {rel_path}")
            checks.append({"kind": "file", "path": rel_path, "size": path.stat().st_size})
            continue

        if not path.is_dir():
            raise PatchError(f"Required runtime directory is missing: {rel_path}")
        file_count = count_files(path)
        min_files = requirement.get("min_files")
        if min_files is not None and file_count < min_files:
            raise PatchError(f"Required runtime directory is incomplete: {rel_path} has {file_count} file(s), expected at least {min_files}.")
        checks.append({"kind": "directory", "path": rel_path, "files": file_count, "min_files": min_files})
    return checks


def manifest_patches(
    manifest: dict[str, Any],
    settings: dict[str, PatchSetting],
    enabled_settings: set[str],
) -> list[BytePatch]:
    raw_patches = manifest.get("patches", [])
    if not isinstance(raw_patches, list):
        raise PatchError("Manifest 'patches' must be an array when present.")
    patches: list[BytePatch] = []
    for index, raw in enumerate(raw_patches):
        if not isinstance(raw, dict):
            raise PatchError(f"Patch #{index} must be an object.")
        file_value = raw.get("file_path", raw.get("file", raw.get("path")))
        expected_value = raw.get("expected_original_bytes", raw.get("expected", raw.get("original")))
        replacement_value = raw.get("replacement_bytes", raw.get("replacement", raw.get("new")))
        file_path = normalize_rel_path(file_value, f"patch #{index} file path")
        requires = record_requires(raw, f"patch #{index}")
        ensure_known_settings(requires, settings, f"Patch #{index}")
        if not record_is_active(requires, enabled_settings):
            continue
        expected = parse_hex_bytes(expected_value, f"patch #{index} expected bytes")
        replacement = parse_hex_bytes(replacement_value, f"patch #{index} replacement bytes")
        if not expected:
            raise PatchError(f"Patch #{index} expected bytes must not be empty.")
        if len(expected) != len(replacement):
            raise PatchError(
                f"Patch #{index} changes byte length ({len(expected)} -> {len(replacement)}); "
                "length-changing patches are not supported."
            )
        patches.append(
            BytePatch(
                index=index,
                file_path=file_path,
                offset=parse_int(raw.get("offset"), f"patch #{index} offset"),
                expected=expected,
                replacement=replacement,
                note=str(raw.get("note", "")).strip(),
                requires=requires,
            )
        )
    return patches


def manifest_asset_patches(
    manifest: dict[str, Any],
    settings: dict[str, PatchSetting],
    enabled_settings: set[str],
) -> list[AssetPatch]:
    raw_assets = manifest.get("asset_patches", manifest.get("assets", []))
    if not isinstance(raw_assets, list):
        raise PatchError("Manifest 'asset_patches' must be an array when present.")
    assets: list[AssetPatch] = []
    for index, raw in enumerate(raw_assets):
        if not isinstance(raw, dict):
            raise PatchError(f"Asset patch #{index} must be an object.")
        target_value = raw.get("file_path", raw.get("target_path", raw.get("target", raw.get("path"))))
        source_value = raw.get("source_path", raw.get("source_file", raw.get("source")))
        file_path = normalize_rel_path(target_value, f"asset patch #{index} target path")
        source_path = normalize_rel_path(source_value, f"asset patch #{index} source path")
        requires = record_requires(raw, f"asset patch #{index}")
        ensure_known_settings(requires, settings, f"Asset patch #{index}")
        if not record_is_active(requires, enabled_settings):
            continue
        source_sha = normalize_sha256(
            raw.get("source_sha256", raw.get("sha256")),
            f"asset patch #{index} source_sha256",
            required=True,
        )
        expected_target_sha = normalize_sha256(
            raw.get(
                "expected_target_sha256",
                raw.get("expected_existing_sha256", raw.get("expected_original_sha256")),
            ),
            f"asset patch #{index} expected_target_sha256",
        )
        source_size = None
        if raw.get("source_size", raw.get("size")) is not None:
            source_size = parse_int(raw.get("source_size", raw.get("size")), f"asset patch #{index} source_size")
        expected_target_size = None
        if raw.get("expected_target_size", raw.get("expected_existing_size")) is not None:
            expected_target_size = parse_int(
                raw.get("expected_target_size", raw.get("expected_existing_size")),
                f"asset patch #{index} expected_target_size",
            )
        assets.append(
            AssetPatch(
                index=index,
                file_path=file_path,
                source_path=source_path,
                source_sha256=source_sha or "",
                source_size=source_size,
                expected_target_sha256=expected_target_sha,
                expected_target_size=expected_target_size,
                overwrite_existing=bool(
                    raw.get("overwrite_existing", raw.get("replace_existing", raw.get("overwrite", False)))
                ),
                note=str(raw.get("note", "")).strip(),
                requires=requires,
            )
        )
    return assets


def manifest_target_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(manifest.get("target_files"), list):
        return manifest["target_files"]
    if isinstance(manifest.get("targets"), list):
        return manifest["targets"]
    target = manifest.get("target")
    if isinstance(target, dict) and isinstance(target.get("files"), list):
        return target["files"]
    return []


def verify_target_files(
    game_dir: Path,
    manifest: dict[str, Any],
    settings: dict[str, PatchSetting],
    enabled_settings: set[str],
) -> list[dict[str, Any]]:
    target_files = manifest_target_files(manifest)
    if not target_files:
        raise PatchError("Manifest must contain target_files with at least the original EXE SHA-256.")

    checks = []
    saw_exe_sha = False
    for index, raw in enumerate(target_files):
        if not isinstance(raw, dict):
            raise PatchError(f"Target file #{index} must be an object.")
        requires = record_requires(raw, f"target file #{index}")
        ensure_known_settings(requires, settings, f"Target file #{index}")
        if not record_is_active(requires, enabled_settings):
            continue
        rel_path = normalize_rel_path(raw.get("file_path", raw.get("file", raw.get("path"))), f"target file #{index}")
        path = resolve_under_game_dir(game_dir, rel_path)
        if not path.is_file():
            raise PatchError(f"Target file does not exist: {rel_path}")
        actual_sha = sha256_file(path)
        actual_size = path.stat().st_size
        actual_timestamp = pe_timestamp(path)
        version_info = windows_file_versions(path)

        expected_sha = raw.get("sha256", raw.get("hash"))
        if expected_sha and actual_sha.lower() != str(expected_sha).lower():
            raise PatchError(f"SHA-256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}")
        if path.suffix.lower() == ".exe" and expected_sha:
            saw_exe_sha = True

        expected_size = raw.get("size")
        if expected_size is not None and actual_size != parse_int(expected_size, f"target file #{index} size"):
            raise PatchError(f"Size mismatch for {rel_path}: expected {expected_size}, got {actual_size}")

        expected_timestamp = raw.get("pe_timestamp")
        if expected_timestamp is not None:
            parsed = parse_int(expected_timestamp, f"target file #{index} pe_timestamp")
            if actual_timestamp != parsed:
                raise PatchError(
                    f"PE timestamp mismatch for {rel_path}: expected 0x{parsed:08x}, got "
                    f"{'none' if actual_timestamp is None else hex(actual_timestamp)}"
                )

        for key in ("file_version", "product_version", "version"):
            if key not in raw:
                continue
            compare_key = "file_version" if key == "version" else key
            actual_version = version_info.get(compare_key)
            if actual_version is None:
                raise PatchError(f"Could not read {compare_key} for {rel_path}.")
            if actual_version != str(raw[key]):
                raise PatchError(f"{compare_key} mismatch for {rel_path}: expected {raw[key]}, got {actual_version}")

        checks.append(
            {
                "file_path": rel_path,
                "sha256": actual_sha,
                "size": actual_size,
                "pe_timestamp": None if actual_timestamp is None else f"0x{actual_timestamp:08x}",
                "requires": list(requires),
                **version_info,
            }
        )
    if not saw_exe_sha:
        raise PatchError("Manifest must verify the original VF2 executable with a SHA-256 target_files entry.")
    return checks


def group_patches(patches: list[BytePatch]) -> dict[str, list[BytePatch]]:
    grouped: dict[str, list[BytePatch]] = {}
    for patch in patches:
        grouped.setdefault(patch.file_path, []).append(patch)
    for file_patches in grouped.values():
        file_patches.sort(key=lambda p: (p.offset, p.index))
        last_end = -1
        last_index = -1
        for patch in file_patches:
            if patch.offset < last_end:
                raise PatchError(f"Patch #{patch.index} overlaps patch #{last_index}.")
            last_end = patch.offset + len(patch.expected)
            last_index = patch.index
    return grouped


def verify_patch_bytes(game_dir: Path, grouped: dict[str, list[BytePatch]]) -> dict[str, bytes]:
    file_data: dict[str, bytes] = {}
    for rel_path, patches in grouped.items():
        path = resolve_under_game_dir(game_dir, rel_path)
        if not path.is_file():
            raise PatchError(f"Patch target file does not exist: {rel_path}")
        data = path.read_bytes()
        for patch in patches:
            end = patch.offset + len(patch.expected)
            if end > len(data):
                raise PatchError(f"Patch #{patch.index} runs past end of {rel_path}.")
            actual = data[patch.offset:end]
            if actual != patch.expected:
                raise PatchError(
                    f"Patch #{patch.index} expected bytes do not match {rel_path} at 0x{patch.offset:x}: "
                    f"expected {patch.expected.hex(' ')}, got {actual.hex(' ')}"
                )
        file_data[rel_path] = data
    return file_data


def verify_asset_patches(game_dir: Path, manifest_dir: Path, assets: list[AssetPatch]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for asset in assets:
        source = resolve_under_manifest_dir(manifest_dir, asset.source_path)
        if not source.is_file():
            raise PatchError(f"Asset source file does not exist: {asset.source_path}")
        source_sha = sha256_file(source)
        source_size = source.stat().st_size
        if source_sha != asset.source_sha256:
            raise PatchError(
                f"SHA-256 mismatch for asset source {asset.source_path}: "
                f"expected {asset.source_sha256}, got {source_sha}"
            )
        if asset.source_size is not None and source_size != asset.source_size:
            raise PatchError(
                f"Size mismatch for asset source {asset.source_path}: "
                f"expected {asset.source_size}, got {source_size}"
            )

        target = resolve_under_game_dir(game_dir, asset.file_path)
        target_exists = target.is_file()
        target_sha = sha256_file(target) if target_exists else None
        target_size = target.stat().st_size if target_exists else None
        action = "create"
        if target_exists:
            action = "replace"
            if asset.expected_target_sha256 and target_sha != asset.expected_target_sha256:
                raise PatchError(
                    f"SHA-256 mismatch for existing asset target {asset.file_path}: "
                    f"expected {asset.expected_target_sha256}, got {target_sha}"
                )
            if asset.expected_target_size is not None and target_size != asset.expected_target_size:
                raise PatchError(
                    f"Size mismatch for existing asset target {asset.file_path}: "
                    f"expected {asset.expected_target_size}, got {target_size}"
                )
            if target_sha == source_sha:
                action = "up_to_date"
            elif not asset.expected_target_sha256 and not asset.overwrite_existing:
                raise PatchError(
                    f"Asset target already exists without an expected_target_sha256 or overwrite_existing=true: "
                    f"{asset.file_path}"
                )
        elif asset.expected_target_sha256 or asset.expected_target_size is not None:
            raise PatchError(f"Expected existing asset target is missing: {asset.file_path}")

        checks.append(
            {
                "index": asset.index,
                "file_path": asset.file_path,
                "source_path": asset.source_path,
                "source_sha256": source_sha,
                "source_size": source_size,
                "target_existed": target_exists,
                "target_sha256": target_sha,
                "target_size": target_size,
                "action": action,
                "requires": list(asset.requires),
                "note": asset.note,
            }
        )
    return checks


def apply_asset_patches(game_dir: Path, manifest_dir: Path, asset_checks: list[dict[str, Any]]) -> None:
    for check in asset_checks:
        if check["action"] == "up_to_date":
            continue
        source = resolve_under_manifest_dir(manifest_dir, str(check["source_path"]))
        target = resolve_under_game_dir(game_dir, str(check["file_path"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".vf2patch.tmp")
        shutil.copy2(source, temp)
        temp.replace(target)


def backup_slug(manifest_path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", manifest_path.stem).strip("._")
    if not stem:
        stem = "vf2_patch"
    return f"{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{stem}"


def create_backup(
    game_dir: Path,
    backup_dir: Path,
    grouped: dict[str, list[BytePatch]],
    asset_checks: list[dict[str, Any]],
    manifest_path: Path,
) -> dict[str, Any]:
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_targets: dict[str, bool] = {rel_path: True for rel_path in grouped}
    for check in asset_checks:
        if check["action"] == "up_to_date":
            continue
        backup_targets.setdefault(str(check["file_path"]), bool(check["target_existed"]))

    files = []
    for rel_path in sorted(backup_targets):
        source = resolve_under_game_dir(game_dir, rel_path)
        existed = backup_targets[rel_path]
        row: dict[str, Any] = {"file_path": rel_path, "existed": existed}
        if existed:
            if not source.is_file():
                raise PatchError(f"Backup target file does not exist: {rel_path}")
            backup_rel = Path("files") / rel_path
            destination = backup_dir / backup_rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            row.update(
                {
                    "backup_path": str(backup_rel).replace("\\", "/"),
                    "sha256": sha256_file(source),
                    "size": source.stat().st_size,
                }
            )
        files.append(row)
    manifest = {
        "backup_created_utc": utc_now(),
        "game_dir": str(game_dir.resolve()),
        "source_manifest": str(manifest_path.resolve()),
        "files": files,
    }
    write_json(backup_dir / BACKUP_MANIFEST, manifest)
    return manifest


def apply_patches_to_data(data: bytes, patches: list[BytePatch]) -> bytes:
    patched = bytearray(data)
    for patch in patches:
        patched[patch.offset : patch.offset + len(patch.expected)] = patch.replacement
    return bytes(patched)


def atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".vf2patch.tmp")
    temp.write_bytes(data)
    temp.replace(path)


def patch_summary(grouped: dict[str, list[BytePatch]]) -> list[dict[str, Any]]:
    rows = []
    for rel_path, patches in sorted(grouped.items()):
        for patch in patches:
            rows.append(
                {
                    "index": patch.index,
                    "file_path": rel_path,
                    "offset": f"0x{patch.offset:x}",
                    "length": len(patch.expected),
                    "expected_original_bytes": patch.expected.hex(" "),
                    "replacement_bytes": patch.replacement.hex(" "),
                    "requires": list(patch.requires),
                    "note": patch.note,
                }
            )
    return rows


def asset_summary(asset_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": check["index"],
            "file_path": check["file_path"],
            "source_path": check["source_path"],
            "source_sha256": check["source_sha256"],
            "source_size": check["source_size"],
            "target_existed": check["target_existed"],
            "target_sha256": check["target_sha256"],
            "target_size": check["target_size"],
            "action": check["action"],
            "requires": check["requires"],
            "note": check["note"],
        }
        for check in asset_checks
    ]


def apply_manifest(args: argparse.Namespace) -> int:
    game_dir = Path(args.game_dir).resolve()
    manifest_path = Path(args.manifest).resolve()
    if not game_dir.is_dir():
        raise PatchError(f"Game directory does not exist: {game_dir}")
    manifest = read_json(manifest_path)
    settings, enabled_settings = resolve_enabled_settings(manifest, args)
    patches = manifest_patches(manifest, settings, enabled_settings)
    assets = manifest_asset_patches(manifest, settings, enabled_settings)
    if not patches and not assets:
        raise PatchError("No active patches remain after applying setting selections.")
    grouped = group_patches(patches)
    target_checks = verify_target_files(game_dir, manifest, settings, enabled_settings)
    runtime_checks = verify_runtime_requirements(game_dir, manifest, settings, enabled_settings)
    file_data = verify_patch_bytes(game_dir, grouped)
    asset_checks = verify_asset_patches(game_dir, manifest_path.parent, assets)

    backup_dir = None
    backup_manifest = None
    if not args.dry_run:
        if args.backup_dir:
            backup_dir = Path(args.backup_dir).resolve()
        else:
            backup_dir = game_dir / DEFAULT_BACKUP_ROOT / backup_slug(manifest_path)
        backup_manifest = create_backup(game_dir, backup_dir, grouped, asset_checks, manifest_path)
        for rel_path, patches_for_file in grouped.items():
            target = resolve_under_game_dir(game_dir, rel_path)
            atomic_write(target, apply_patches_to_data(file_data[rel_path], patches_for_file))
        apply_asset_patches(game_dir, manifest_path.parent, asset_checks)

    patched_files = []
    for rel_path in sorted(grouped):
        target = resolve_under_game_dir(game_dir, rel_path)
        patched_files.append(
            {
                "file_path": rel_path,
                "sha256": sha256_file(target) if not args.dry_run else None,
                "size": target.stat().st_size,
            }
        )

    log = {
        "action": "apply",
        "dry_run": bool(args.dry_run),
        "status": "success",
        "timestamp_utc": utc_now(),
        "game_dir": str(game_dir),
        "manifest": str(manifest_path),
        "manifest_name": manifest.get("name"),
        "settings": settings_log(settings, enabled_settings),
        "target_checks": target_checks,
        "runtime_checks": runtime_checks,
        "backup_dir": None if backup_dir is None else str(backup_dir),
        "backup_manifest": backup_manifest,
        "patches": patch_summary(grouped),
        "asset_patches": asset_summary(asset_checks),
        "patched_files": patched_files,
        "asset_files": [
            {
                "file_path": check["file_path"],
                "action": check["action"],
                "sha256": check["source_sha256"] if not args.dry_run else None,
                "size": check["source_size"],
            }
            for check in asset_checks
        ],
    }
    log_path = Path(args.log).resolve() if args.log else (backup_dir / "patch_log.json" if backup_dir else game_dir / "patch_dry_run_log.json")
    write_json(log_path, log)

    if settings:
        print("Enabled settings: " + (", ".join(sorted(enabled_settings)) if enabled_settings else "(none)"))
    print(
        f"Validated {len(patches)} active byte patch record(s) across {len(grouped)} file(s) "
        f"and {len(assets)} active asset patch record(s)."
    )
    if args.dry_run:
        print(f"Dry run complete. Log: {log_path}")
    else:
        print(f"Patched files successfully. Backup: {backup_dir}")
        print(f"Patch log: {log_path}")
    return 0


def list_manifest_settings(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    manifest = read_json(manifest_path)
    settings = manifest_settings(manifest)
    if args.json:
        write_json(Path(args.json), {"manifest": str(manifest_path), "settings": settings_log(settings, {s for s, row in settings.items() if row.default})})
        print(f"Settings JSON written: {Path(args.json).resolve()}")
        return 0
    if not settings:
        print("This manifest does not declare toggleable settings.")
        return 0
    for setting in settings.values():
        state = "default on" if setting.default else "default off"
        line = f"{setting.id} [{state}] - {setting.label}"
        if setting.description:
            line += f": {setting.description}"
        print(line)
    return 0


def restore_backup(args: argparse.Namespace) -> int:
    backup_dir = Path(args.backup_dir).resolve()
    backup_manifest_path = backup_dir / BACKUP_MANIFEST
    if not backup_manifest_path.is_file():
        raise PatchError(f"Backup manifest not found: {backup_manifest_path}")
    backup_manifest = read_json(backup_manifest_path)
    game_dir = Path(args.game_dir).resolve() if args.game_dir else Path(str(backup_manifest["game_dir"])).resolve()
    if not game_dir.is_dir():
        raise PatchError(f"Game directory does not exist: {game_dir}")

    restored = []
    for raw in backup_manifest.get("files", []):
        if not isinstance(raw, dict):
            raise PatchError("Backup manifest contains an invalid file row.")
        rel_path = normalize_rel_path(raw.get("file_path"), "backup file path")
        target = resolve_under_game_dir(game_dir, rel_path)
        if raw.get("existed", True):
            backup_rel = normalize_rel_path(raw.get("backup_path"), "backup path")
            source = (backup_dir / backup_rel).resolve()
            if not source.is_file():
                raise PatchError(f"Backed-up file is missing: {source}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            restored.append({"file_path": rel_path, "sha256": sha256_file(target), "size": target.stat().st_size})
        else:
            removed = False
            if target.exists():
                if not target.is_file():
                    raise PatchError(f"Restore target is not a regular file: {rel_path}")
                target.unlink()
                removed = True
            restored.append({"file_path": rel_path, "removed": removed, "existed": False})

    log = {
        "action": "restore",
        "status": "success",
        "timestamp_utc": utc_now(),
        "game_dir": str(game_dir),
        "backup_dir": str(backup_dir),
        "restored_files": restored,
    }
    log_path = Path(args.log).resolve() if args.log else backup_dir / "restore_log.json"
    write_json(log_path, log)
    print(f"Restored {len(restored)} file(s).")
    print(f"Restore log: {log_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline VF2 JSON patch manifest applier.")
    sub = parser.add_subparsers(dest="command", required=True)

    apply_cmd = sub.add_parser("apply", help="Validate and apply a JSON patch manifest.")
    apply_cmd.add_argument("--game-dir", required=True, help="Path to the user-provided vanilla VF2 game directory.")
    apply_cmd.add_argument("--manifest", required=True, help="Path to the JSON patch manifest.")
    apply_cmd.add_argument("--backup-dir", help="Backup output directory. Defaults under the game directory.")
    apply_cmd.add_argument("--log", help="Patch log JSON path. Defaults inside the backup directory.")
    apply_cmd.add_argument("--dry-run", action="store_true", help="Validate only; do not back up or modify files.")
    apply_cmd.add_argument("--enable", action="append", help="Enable a manifest setting. Repeat or comma-separate IDs.")
    apply_cmd.add_argument("--disable", action="append", help="Disable a manifest setting. Repeat or comma-separate IDs.")
    apply_cmd.add_argument("--enable-all", action="store_true", help="Enable all manifest-declared settings before patching.")
    apply_cmd.add_argument("--disable-all", action="store_true", help="Disable all manifest-declared settings before patching.")
    apply_cmd.set_defaults(func=apply_manifest)

    settings_cmd = sub.add_parser("settings", help="List toggleable settings declared by a manifest.")
    settings_cmd.add_argument("--manifest", required=True, help="Path to the JSON patch manifest.")
    settings_cmd.add_argument("--json", help="Optional path to write settings metadata as JSON.")
    settings_cmd.set_defaults(func=list_manifest_settings)

    restore_cmd = sub.add_parser("restore", help="Restore files from a patcher backup directory.")
    restore_cmd.add_argument("--backup-dir", required=True, help="Backup directory created by apply.")
    restore_cmd.add_argument("--game-dir", help="Override restore destination. Defaults to original game_dir in backup.")
    restore_cmd.add_argument("--log", help="Restore log JSON path. Defaults inside the backup directory.")
    restore_cmd.set_defaults(func=restore_backup)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except PatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
