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
from typing import Any, Callable


BACKUP_MANIFEST = "vf2_patch_backup_manifest.json"
DEFAULT_BACKUP_ROOT = ".vf2_patch_backups"
DEFAULT_EXE_NAME = "Virtual Families 2.exe"
INVALID_INSTALL_MESSAGE = (
    "No valid Virtual Families 2 Installation detected! Are you sure you downloaded it from the official website?\n\n"
    "Links:\n"
    "http://www.ldw.com/\n"
    "http://www.virtualfamilies.com/index.php"
)


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
    output_file_path: str | None
    source_path: str
    source_sha256: str
    source_size: int | None
    expected_target_sha256: str | None
    expected_target_pe_structures: tuple[dict[str, Any], ...]
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
    category: str = "main"


ProgressCallback = Callable[[str], None]


def utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise PatchError("Manifest root must be a JSON object.")
    return data


def invalid_install_message(manifest: dict[str, Any]) -> str:
    raw = manifest.get("invalid_install_message")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    runtime = manifest.get("runtime_requirements")
    if isinstance(runtime, dict):
        raw = runtime.get("invalid_install_message")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return INVALID_INSTALL_MESSAGE


def install_validation_error(manifest: dict[str, Any], detail: str) -> PatchError:
    return PatchError(f"{invalid_install_message(manifest)}\n\nDetails: {detail}")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def emit_progress(args: argparse.Namespace, message: str) -> None:
    callback = getattr(args, "progress_callback", None)
    if callback is not None:
        callback(message)
    else:
        print(message)


def should_report_progress(current: int, total: int) -> bool:
    return total <= 20 or current in {1, total} or current % 100 == 0


def report_record_progress(
    args: argparse.Namespace,
    *,
    phase: str,
    kind: str,
    current: int,
    total: int,
    file_path: str,
    index: int,
    status: str = "ok",
) -> None:
    if not should_report_progress(current, total) and status == "ok":
        return
    emit_progress(args, f"{phase} {kind} {current}/{total}: #{index} {file_path} [{status}]")


def log_process_event(
    process_log: list[dict[str, Any]],
    *,
    phase: str,
    kind: str,
    status: str,
    index: int | None = None,
    file_path: str | None = None,
    note: str = "",
    error: str | None = None,
    **extra: Any,
) -> None:
    row: dict[str, Any] = {
        "timestamp_utc": utc_now(),
        "phase": phase,
        "kind": kind,
        "status": status,
    }
    if index is not None:
        row["index"] = index
    if file_path is not None:
        row["file_path"] = file_path
    if note:
        row["note"] = note
    if error:
        row["error"] = error
    row.update(extra)
    process_log.append(row)


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


def pe_structure_fingerprint(path: Path) -> dict[str, Any] | None:
    try:
        data = path.read_bytes()
        if len(data) < 0x40 or data[:2] != b"MZ":
            return None
        pe_off = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_off + 0x18 > len(data) or data[pe_off:pe_off + 4] != b"PE\0\0":
            return None
        coff = pe_off + 4
        machine, section_count, timestamp, _symptr, _nsyms, opt_size, characteristics = struct.unpack_from(
            "<HHIIIHH",
            data,
            coff,
        )
        opt = coff + 20
        section_table = opt + opt_size
        if section_table + section_count * 40 > len(data):
            return None
        magic = struct.unpack_from("<H", data, opt)[0]
        if magic != 0x10B:
            return None

        sections = []
        for index in range(section_count):
            off = section_table + index * 40
            name = data[off:off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size, virtual_address, raw_size, raw_ptr, _reloc_ptr, _line_ptr, _reloc_count, _line_count, flags = struct.unpack_from(
                "<IIIIIIHHI",
                data,
                off + 8,
            )
            if raw_ptr + raw_size > len(data):
                return None
            raw = data[raw_ptr:raw_ptr + raw_size]
            sections.append({
                "name": name,
                "virtual_address": f"0x{virtual_address:x}",
                "virtual_size": f"0x{virtual_size:x}",
                "raw_data_pointer": f"0x{raw_ptr:x}",
                "raw_data_size": f"0x{raw_size:x}",
                "characteristics": f"0x{flags:x}",
                "sha256": hashlib.sha256(raw).hexdigest(),
            })

        return {
            "format": "pe32-section-raw-v1",
            "pe_offset": f"0x{pe_off:x}",
            "machine": f"0x{machine:x}",
            "number_of_sections": section_count,
            "time_date_stamp": f"0x{timestamp:x}",
            "characteristics": f"0x{characteristics:x}",
            "optional_header_size": opt_size,
            "optional_magic": f"0x{magic:x}",
            "address_of_entry_point": f"0x{struct.unpack_from('<I', data, opt + 16)[0]:x}",
            "image_base": f"0x{struct.unpack_from('<I', data, opt + 28)[0]:x}",
            "section_alignment": f"0x{struct.unpack_from('<I', data, opt + 32)[0]:x}",
            "file_alignment": f"0x{struct.unpack_from('<I', data, opt + 36)[0]:x}",
            "size_of_image": f"0x{struct.unpack_from('<I', data, opt + 56)[0]:x}",
            "subsystem": f"0x{struct.unpack_from('<H', data, opt + 68)[0]:x}",
            "sections": sections,
        }
    except (OSError, struct.error):
        return None


def pe_structure_identity(structure: Any) -> dict[str, Any] | None:
    if not isinstance(structure, dict):
        return None
    sections = structure.get("sections")
    if not isinstance(sections, list):
        return None
    identity_sections = []
    for section in sections:
        if not isinstance(section, dict):
            return None
        identity_sections.append({
            "name": section.get("name"),
            "virtual_address": section.get("virtual_address"),
            "virtual_size": section.get("virtual_size"),
            "raw_data_pointer": section.get("raw_data_pointer"),
            "raw_data_size": section.get("raw_data_size"),
            "characteristics": section.get("characteristics"),
        })
    return {
        "format": structure.get("format"),
        "pe_offset": structure.get("pe_offset"),
        "machine": structure.get("machine"),
        "number_of_sections": structure.get("number_of_sections"),
        "characteristics": structure.get("characteristics"),
        "optional_header_size": structure.get("optional_header_size"),
        "optional_magic": structure.get("optional_magic"),
        "address_of_entry_point": structure.get("address_of_entry_point"),
        "image_base": structure.get("image_base"),
        "section_alignment": structure.get("section_alignment"),
        "file_alignment": structure.get("file_alignment"),
        "size_of_image": structure.get("size_of_image"),
        "subsystem": structure.get("subsystem"),
        "sections": identity_sections,
    }


def pe_structure_matches(path: Path, expected: Any) -> bool:
    expected_identity = pe_structure_identity(expected)
    if expected_identity is None:
        return False
    actual = pe_structure_fingerprint(path)
    return pe_structure_identity(actual) == expected_identity


def normalize_pe_structure_list(raw: Any, field: str) -> tuple[dict[str, Any], ...]:
    if raw is None:
        return ()
    if isinstance(raw, dict):
        return (raw,)
    if isinstance(raw, list):
        rows = []
        for index, row in enumerate(raw):
            if not isinstance(row, dict):
                raise PatchError(f"{field} #{index} must be an object.")
            rows.append(row)
        return tuple(rows)
    raise PatchError(f"{field} must be an object or array of objects.")


def pe_structure_matches_any(path: Path, expected_rows: tuple[dict[str, Any], ...]) -> bool:
    return any(pe_structure_matches(path, expected) for expected in expected_rows)


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
            category=str(raw.get("category", "main")).strip().lower() or "main",
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
                "category": setting.category,
            }
            for setting in settings.values()
        ],
    }


def manifest_output_folder_name(manifest: dict[str, Any]) -> str | None:
    raw = manifest.get("output", manifest.get("output_folder"))
    if raw is None:
        return None
    if isinstance(raw, str):
        name = raw
    elif isinstance(raw, dict):
        name = str(
            raw.get(
                "default_folder_name",
                raw.get("folder_name", raw.get("name", "")),
            )
        )
    else:
        raise PatchError("Manifest output must be a string or object.")
    name = name.strip()
    if not name:
        return None
    rel = normalize_rel_path(name, "manifest output folder name")
    if len(Path(rel).parts) != 1:
        raise PatchError("Manifest output folder name must be a single folder name.")
    return rel


def manifest_output_exe_name(manifest: dict[str, Any]) -> str | None:
    raw = manifest.get("output", manifest.get("output_folder"))
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("default_exe_name", raw.get("exe_name", ""))).strip()
    if not name:
        return None
    rel = normalize_rel_path(name, "manifest output EXE name")
    path = Path(rel)
    if len(path.parts) != 1 or path.suffix.lower() != ".exe":
        raise PatchError("Manifest output EXE name must be a single .exe filename.")
    if path.name.lower() == DEFAULT_EXE_NAME.lower():
        raise PatchError("Manifest output EXE name must not be the vanilla Virtual Families 2.exe name.")
    return path.name


def resolve_apply_output_dir(
    args: argparse.Namespace,
    game_dir: Path,
    manifest: dict[str, Any],
) -> Path:
    explicit = getattr(args, "output_dir", None)
    if explicit:
        return Path(explicit).resolve()
    folder_name = manifest_output_folder_name(manifest)
    if folder_name:
        return (game_dir.parent / folder_name).resolve()
    return game_dir


def prepare_output_dir(
    game_dir: Path,
    output_dir: Path,
    skip_rel_paths: set[str],
    args: argparse.Namespace,
) -> None:
    source_root = game_dir.resolve()
    output_root = output_dir.resolve()
    if output_root == source_root:
        return
    if output_root in source_root.parents or source_root in output_root.parents:
        raise PatchError("Output directory must be a sibling or separate folder, not inside the vanilla game folder.")
    if output_root.exists() and any(output_root.iterdir()):
        can_refresh = (
            (output_root / DEFAULT_BACKUP_ROOT).is_dir()
            or (output_root.name.startswith("VF2-") and output_root.name.endswith("-Modded"))
        )
        if not can_refresh:
            raise PatchError(
                "Output directory already exists and is not recognized as a VF2 modded output folder: "
                f"{output_root}"
            )
        emit_progress(args, f"Refreshing modded output folder from vanilla install: {output_root}")
        for child in output_root.iterdir():
            if child.name == DEFAULT_BACKUP_ROOT:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    elif output_root.exists():
        emit_progress(args, f"Refreshing empty modded output folder from vanilla install: {output_root}")
    else:
        emit_progress(args, f"Creating modded output folder: {output_root}")

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_skips = {str(Path(path)) for path in skip_rel_paths}
    for source in source_root.rglob("*"):
        rel = source.relative_to(source_root)
        if rel.parts and rel.parts[0] == DEFAULT_BACKUP_ROOT:
            continue
        if str(rel) in normalized_skips:
            continue
        target = output_root / rel
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def enforce_modded_exe_name(
    game_dir: Path,
    output_dir: Path,
    manifest: dict[str, Any],
    process_log: list[dict[str, Any]],
) -> str | None:
    desired_name = manifest_output_exe_name(manifest)
    if not desired_name:
        return None
    if output_dir.resolve() == game_dir.resolve():
        return desired_name
    vanilla_exe = output_dir / DEFAULT_EXE_NAME
    modded_exe = output_dir / desired_name
    if modded_exe.exists():
        if vanilla_exe.exists() and vanilla_exe.resolve() != modded_exe.resolve():
            vanilla_exe.unlink()
            log_process_event(
                process_log,
                phase="apply",
                kind="output_exe_name",
                status="success",
                file_path=DEFAULT_EXE_NAME,
                output_file_path=desired_name,
                action="removed_ambiguous_vanilla_named_exe",
            )
        return desired_name
    if vanilla_exe.exists():
        vanilla_exe.replace(modded_exe)
        log_process_event(
            process_log,
            phase="apply",
            kind="output_exe_name",
            status="success",
            file_path=DEFAULT_EXE_NAME,
            output_file_path=desired_name,
            action="renamed_modded_exe",
        )
    return desired_name


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
    accepted_exe_structures: list[dict[str, Any]] = []
    for index, raw_target in enumerate(manifest_target_files(manifest)):
        if not isinstance(raw_target, dict):
            continue
        requires = record_requires(raw_target, f"target file #{index}")
        ensure_known_settings(requires, settings, f"Target file #{index}")
        if not record_is_active(requires, enabled_settings):
            continue
        accepted_exe_structures.extend(
            normalize_pe_structure_list(
                raw_target.get(
                    "pe_structures",
                    raw_target.get(
                        "accepted_pe_structures",
                        raw_target.get("pe_structure", raw_target.get("binary_structure", raw_target.get("structure"))),
                    ),
                ),
                f"target file #{index} pe_structures",
            )
        )
    raw_runtime = manifest.get("runtime_requirements", manifest.get("required_runtime"))
    if isinstance(raw_runtime, dict):
        exact_entries = raw_runtime.get("exact_top_level_entries", raw_runtime.get("top_level_entries"))
        if exact_entries is not None:
            if not isinstance(exact_entries, list) or not all(isinstance(row, str) and row.strip() for row in exact_entries):
                raise PatchError("runtime_requirements.exact_top_level_entries must be an array of non-empty strings.")
            expected = {row.strip() for row in exact_entries}
            actual = set()
            accepted_exe_names = []
            for path in game_dir.iterdir():
                if (
                    path.is_file()
                    and path.suffix.lower() == ".exe"
                    and accepted_exe_structures
                    and pe_structure_matches_any(path, tuple(accepted_exe_structures))
                ):
                    accepted_exe_names.append(path.name)
                    continue
                actual.add(path.name)
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            if missing or extra:
                details = []
                if missing:
                    details.append("missing top-level entries: " + ", ".join(missing))
                if extra:
                    details.append("unexpected top-level entries: " + ", ".join(extra))
                raise install_validation_error(manifest, "; ".join(details))
            checks.append({"kind": "exact_top_level_entries", "count": len(expected), "accepted_exe_names": accepted_exe_names})
    for requirement in manifest_runtime_requirements(manifest, settings, enabled_settings):
        rel_path = str(requirement["path"])
        path = resolve_under_game_dir(game_dir, rel_path)
        if requirement["kind"] == "file":
            if not path.is_file():
                raise install_validation_error(manifest, f"required runtime file is missing: {rel_path}")
            checks.append({"kind": "file", "path": rel_path, "size": path.stat().st_size})
            continue

        if not path.is_dir():
            raise install_validation_error(manifest, f"required runtime directory is missing: {rel_path}")
        file_count = count_files(path)
        min_files = requirement.get("min_files")
        if min_files is not None and file_count < min_files:
            raise install_validation_error(
                manifest,
                f"required runtime directory is incomplete: {rel_path} has {file_count} file(s), expected at least {min_files}.",
            )
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
        output_value = raw.get("output_file_path", raw.get("output_path", raw.get("write_path")))
        source_value = raw.get("source_path", raw.get("source_file", raw.get("source")))
        file_path = normalize_rel_path(target_value, f"asset patch #{index} target path")
        output_file_path = None
        if output_value is not None:
            output_file_path = normalize_rel_path(output_value, f"asset patch #{index} output path")
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
        expected_target_pe_structures = normalize_pe_structure_list(
            raw.get(
                "expected_target_pe_structures",
                raw.get(
                    "accepted_target_pe_structures",
                    raw.get(
                        "expected_target_pe_structure",
                        raw.get("expected_target_structure", raw.get("expected_original_pe_structure")),
                    ),
                ),
            ),
            f"asset patch #{index} expected_target_pe_structures",
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
                output_file_path=output_file_path,
                source_path=source_path,
                source_sha256=source_sha or "",
                source_size=source_size,
                expected_target_sha256=expected_target_sha,
                expected_target_pe_structures=expected_target_pe_structures,
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
        raise PatchError("Manifest must contain target_files with at least one EXE identity record.")

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
        expected_sha = raw.get("sha256", raw.get("hash"))
        expected_pe_structures = normalize_pe_structure_list(
            raw.get(
                "pe_structures",
                raw.get("accepted_pe_structures", raw.get("pe_structure", raw.get("binary_structure", raw.get("structure")))),
            ),
            f"target file #{index} pe_structures",
        )

        path = resolve_under_game_dir(game_dir, rel_path)
        if not path.is_file() and Path(rel_path).suffix.lower() == ".exe" and expected_pe_structures:
            for candidate in sorted(game_dir.glob("*.exe")):
                if pe_structure_matches_any(candidate, expected_pe_structures):
                    path = candidate
                    rel_path = candidate.name
                    break
        if not path.is_file():
            raise install_validation_error(manifest, f"target file does not exist: {rel_path}")
        actual_sha = sha256_file(path)
        actual_size = path.stat().st_size
        actual_timestamp = pe_timestamp(path)
        version_info = windows_file_versions(path)

        matched_by = None
        if expected_sha and actual_sha.lower() == str(expected_sha).lower():
            matched_by = "sha256"
        elif expected_pe_structures and pe_structure_matches_any(path, expected_pe_structures):
            matched_by = "pe_structure"
        elif expected_sha:
            if expected_pe_structures:
                raise install_validation_error(
                    manifest,
                    f"Target identity mismatch for {rel_path}: SHA-256 expected {expected_sha}, got {actual_sha}; "
                    "PE structure did not match any accepted binary structure.",
                )
            raise install_validation_error(
                manifest,
                f"SHA-256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}",
            )
        elif expected_pe_structures:
            raise install_validation_error(
                manifest,
                f"PE structure mismatch for {rel_path}; this is not a recognized VF2 executable build.",
            )

        if path.suffix.lower() == ".exe" and (expected_sha or expected_pe_structures):
            saw_exe_sha = True

        expected_size = raw.get("size")
        if (
            expected_size is not None
            and matched_by != "pe_structure"
            and actual_size != parse_int(expected_size, f"target file #{index} size")
        ):
            raise install_validation_error(manifest, f"Size mismatch for {rel_path}: expected {expected_size}, got {actual_size}")

        expected_timestamp = raw.get("pe_timestamp")
        if expected_timestamp is not None:
            parsed = parse_int(expected_timestamp, f"target file #{index} pe_timestamp")
            if actual_timestamp != parsed:
                raise install_validation_error(
                    manifest,
                    f"PE timestamp mismatch for {rel_path}: expected 0x{parsed:08x}, got "
                    f"{'none' if actual_timestamp is None else hex(actual_timestamp)}",
                )

        for key in ("file_version", "product_version", "version"):
            if key not in raw:
                continue
            compare_key = "file_version" if key == "version" else key
            actual_version = version_info.get(compare_key)
            if actual_version is None:
                raise install_validation_error(manifest, f"Could not read {compare_key} for {rel_path}.")
            if actual_version != str(raw[key]):
                raise install_validation_error(
                    manifest,
                    f"{compare_key} mismatch for {rel_path}: expected {raw[key]}, got {actual_version}",
                )

        checks.append(
            {
                "file_path": rel_path,
                "sha256": actual_sha,
                "size": actual_size,
                "pe_timestamp": None if actual_timestamp is None else f"0x{actual_timestamp:08x}",
                "requires": list(requires),
                "matched_by": matched_by,
                **version_info,
            }
        )
    if not saw_exe_sha:
        raise PatchError("Manifest must verify the original VF2 executable with a SHA-256 or accepted PE-structure target_files entry.")
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


def verify_patch_bytes(
    game_dir: Path,
    grouped: dict[str, list[BytePatch]],
    args: argparse.Namespace,
    process_log: list[dict[str, Any]],
) -> dict[str, bytes]:
    file_data: dict[str, bytes] = {}
    total = sum(len(patches) for patches in grouped.values())
    current = 0
    for rel_path, patches in grouped.items():
        path = resolve_under_game_dir(game_dir, rel_path)
        if not path.is_file():
            for patch in patches:
                log_process_event(
                    process_log,
                    phase="validate",
                    kind="byte_patch",
                    status="error",
                    index=patch.index,
                    file_path=patch.file_path,
                    note=patch.note,
                    error=f"Patch target file does not exist: {rel_path}",
                )
            raise PatchError(f"Patch target file does not exist: {rel_path}")
        data = path.read_bytes()
        for patch in patches:
            current += 1
            end = patch.offset + len(patch.expected)
            if end > len(data):
                message = f"Patch #{patch.index} runs past end of {rel_path}."
                log_process_event(
                    process_log,
                    phase="validate",
                    kind="byte_patch",
                    status="error",
                    index=patch.index,
                    file_path=patch.file_path,
                    note=patch.note,
                    offset=f"0x{patch.offset:x}",
                    error=message,
                )
                report_record_progress(
                    args,
                    phase="Validating",
                    kind="byte patch",
                    current=current,
                    total=total,
                    file_path=patch.file_path,
                    index=patch.index,
                    status="error",
                )
                raise PatchError(message)
            actual = data[patch.offset:end]
            if actual != patch.expected:
                message = (
                    f"Patch #{patch.index} expected bytes do not match {rel_path} at 0x{patch.offset:x}: "
                    f"expected {patch.expected.hex(' ')}, got {actual.hex(' ')}"
                )
                log_process_event(
                    process_log,
                    phase="validate",
                    kind="byte_patch",
                    status="error",
                    index=patch.index,
                    file_path=patch.file_path,
                    note=patch.note,
                    offset=f"0x{patch.offset:x}",
                    expected=patch.expected.hex(),
                    actual=actual.hex(),
                    error=message,
                )
                report_record_progress(
                    args,
                    phase="Validating",
                    kind="byte patch",
                    current=current,
                    total=total,
                    file_path=patch.file_path,
                    index=patch.index,
                    status="error",
                )
                raise PatchError(message)
            log_process_event(
                process_log,
                phase="validate",
                kind="byte_patch",
                status="success",
                index=patch.index,
                file_path=patch.file_path,
                note=patch.note,
                offset=f"0x{patch.offset:x}",
                expected=patch.expected.hex(),
                replacement=patch.replacement.hex(),
            )
            report_record_progress(
                args,
                phase="Validating",
                kind="byte patch",
                current=current,
                total=total,
                file_path=patch.file_path,
                index=patch.index,
            )
        file_data[rel_path] = data
    return file_data


def verify_asset_patches(
    game_dir: Path,
    output_dir: Path,
    manifest_dir: Path,
    assets: list[AssetPatch],
    args: argparse.Namespace,
    process_log: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    total = len(assets)
    for current, asset in enumerate(assets, start=1):
        try:
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
            output_file_path = asset.output_file_path or asset.file_path
            output_target = resolve_under_game_dir(output_dir, output_file_path)
            output_is_validation_target = output_file_path == asset.file_path
            if output_dir.resolve() == game_dir.resolve() and output_is_validation_target:
                output_exists = target_exists
                output_sha = target_sha
                output_size = target_size
            else:
                output_exists = output_target.is_file()
                output_sha = sha256_file(output_target) if output_exists else None
                output_size = output_target.stat().st_size if output_exists else None
            expected_structure_matches = (
                target_exists
                and bool(asset.expected_target_pe_structures)
                and pe_structure_matches_any(target, asset.expected_target_pe_structures)
            )
            action = "create"
            if target_exists:
                action = "replace"
                if asset.expected_target_sha256 and target_sha != asset.expected_target_sha256 and not expected_structure_matches:
                    raise PatchError(
                        f"SHA-256 mismatch for existing asset target {asset.file_path}: "
                        f"expected {asset.expected_target_sha256}, got {target_sha}; "
                        "PE structure did not match any accepted binary structure."
                    )
                if asset.expected_target_pe_structures and not expected_structure_matches and not asset.expected_target_sha256:
                    raise PatchError(f"PE structure mismatch for existing asset target {asset.file_path}.")
                if (
                    asset.expected_target_size is not None
                    and not expected_structure_matches
                    and target_size != asset.expected_target_size
                ):
                    raise PatchError(
                        f"Size mismatch for existing asset target {asset.file_path}: "
                        f"expected {asset.expected_target_size}, got {target_size}"
                    )
                if target_sha == source_sha:
                    action = "up_to_date"
                elif not asset.expected_target_sha256 and not asset.overwrite_existing:
                    raise PatchError(
                        "Asset target already exists without an expected_target_sha256 or overwrite_existing=true: "
                        f"{asset.file_path}"
                    )
            elif asset.expected_target_sha256 or asset.expected_target_size is not None:
                raise PatchError(f"Expected existing asset target is missing: {asset.file_path}")
            if not output_is_validation_target:
                action = "create"
                if output_exists:
                    action = "up_to_date" if output_sha == source_sha else "replace"
                    if action == "replace" and not asset.overwrite_existing:
                        raise PatchError(
                            "Asset output already exists without overwrite_existing=true: "
                            f"{output_file_path}"
                        )
        except PatchError as exc:
            log_process_event(
                process_log,
                phase="validate",
                kind="asset_patch",
                status="error",
                index=asset.index,
                file_path=asset.file_path,
                note=asset.note,
                source_path=asset.source_path,
                error=str(exc),
            )
            report_record_progress(
                args,
                phase="Validating",
                kind="asset patch",
                current=current,
                total=total,
                file_path=asset.file_path,
                index=asset.index,
                status="error",
            )
            raise

        check = {
            "index": asset.index,
            "file_path": asset.file_path,
            "output_file_path": output_file_path,
            "source_path": asset.source_path,
            "source_sha256": source_sha,
            "source_size": source_size,
            "target_existed": target_exists,
            "target_sha256": target_sha,
            "target_size": target_size,
            "target_structure_matched": bool(expected_structure_matches),
            "output_existed": output_exists,
            "output_sha256": output_sha,
            "output_size": output_size,
            "action": action,
            "requires": list(asset.requires),
            "note": asset.note,
        }
        checks.append(check)
        log_process_event(
            process_log,
            phase="validate",
            kind="asset_patch",
            status="success",
            index=asset.index,
            file_path=asset.file_path,
            note=asset.note,
            source_path=asset.source_path,
            output_file_path=output_file_path,
            action=action,
        )
        report_record_progress(
            args,
            phase="Validating",
            kind="asset patch",
            current=current,
            total=total,
            file_path=asset.file_path,
            index=asset.index,
        )
    return checks


def apply_asset_patches(
    output_dir: Path,
    manifest_dir: Path,
    asset_checks: list[dict[str, Any]],
    args: argparse.Namespace,
    process_log: list[dict[str, Any]],
) -> None:
    total = len(asset_checks)
    for current, check in enumerate(asset_checks, start=1):
        file_path = str(check["file_path"])
        output_file_path = str(check.get("output_file_path") or file_path)
        index = int(check["index"])
        if check["action"] == "up_to_date":
            log_process_event(
                process_log,
                phase="apply",
                kind="asset_patch",
                status="skipped",
                index=index,
                file_path=file_path,
                note=str(check.get("note") or ""),
                source_path=str(check["source_path"]),
                output_file_path=output_file_path,
                action="up_to_date",
            )
            report_record_progress(
                args,
                phase="Applying",
                kind="asset patch",
                current=current,
                total=total,
                file_path=output_file_path,
                index=index,
                status="skipped",
            )
            continue
        source = resolve_under_manifest_dir(manifest_dir, str(check["source_path"]))
        target = resolve_under_game_dir(output_dir, output_file_path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + ".vf2patch.tmp")
            shutil.copy2(source, temp)
            temp.replace(target)
        except OSError as exc:
            log_process_event(
                process_log,
                phase="apply",
                kind="asset_patch",
                status="error",
                index=index,
                file_path=file_path,
                note=str(check.get("note") or ""),
                source_path=str(check["source_path"]),
                output_file_path=output_file_path,
                action=str(check["action"]),
                error=str(exc),
            )
            report_record_progress(
                args,
                phase="Applying",
                kind="asset patch",
                current=current,
                total=total,
                file_path=output_file_path,
                index=index,
                status="error",
            )
            raise PatchError(f"Could not apply asset patch #{index} to {output_file_path}: {exc}") from exc
        log_process_event(
            process_log,
            phase="apply",
            kind="asset_patch",
            status="success",
            index=index,
            file_path=file_path,
            note=str(check.get("note") or ""),
            source_path=str(check["source_path"]),
            output_file_path=output_file_path,
            action=str(check["action"]),
        )
        report_record_progress(
            args,
            phase="Applying",
            kind="asset patch",
            current=current,
            total=total,
            file_path=output_file_path,
            index=index,
        )


def backup_slug(manifest_path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", manifest_path.stem).strip("._")
    if not stem:
        stem = "vf2_patch"
    return f"{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{stem}"


def create_backup(
    game_dir: Path,
    output_dir: Path,
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
        output_file_path = str(check.get("output_file_path") or check["file_path"])
        if output_file_path == str(check["file_path"]):
            backup_targets.setdefault(str(check["file_path"]), bool(check["target_existed"]))
        else:
            backup_targets.setdefault(output_file_path, bool(check.get("output_existed", False)))

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
        "game_dir": str(output_dir.resolve()),
        "source_game_dir": str(game_dir.resolve()),
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
            "output_file_path": check.get("output_file_path", check["file_path"]),
            "source_path": check["source_path"],
            "source_sha256": check["source_sha256"],
            "source_size": check["source_size"],
            "target_existed": check["target_existed"],
            "target_sha256": check["target_sha256"],
            "target_size": check["target_size"],
            "target_structure_matched": check.get("target_structure_matched", False),
            "output_existed": check.get("output_existed", check["target_existed"]),
            "output_sha256": check.get("output_sha256", check["target_sha256"]),
            "output_size": check.get("output_size", check["target_size"]),
            "action": check["action"],
            "requires": check["requires"],
            "note": check["note"],
        }
        for check in asset_checks
    ]


def apply_manifest(args: argparse.Namespace) -> int:
    exe_path = Path(args.exe).resolve() if getattr(args, "exe", None) else None
    game_dir = Path(args.game_dir).resolve() if args.game_dir else None
    if exe_path is not None:
        if exe_path.suffix.lower() != ".exe":
            raise PatchError(f"--exe must point to a Virtual Families 2 executable, got {exe_path.name!r}.")
        if game_dir is not None and game_dir != exe_path.parent.resolve():
            raise PatchError("--game-dir and --exe disagree; use the EXE's parent folder or omit --game-dir.")
        game_dir = exe_path.parent.resolve()
    if game_dir is None:
        raise PatchError("Either --game-dir or --exe is required.")
    manifest_path = Path(args.manifest).resolve()
    if not game_dir.is_dir():
        raise PatchError(f"Game directory does not exist: {game_dir}")
    process_log: list[dict[str, Any]] = []
    backup_dir = None
    backup_manifest = None
    settings: dict[str, PatchSetting] = {}
    enabled_settings: set[str] = set()
    try:
        emit_progress(args, f"Loading manifest: {manifest_path}")
        manifest = read_json(manifest_path)
        output_dir = resolve_apply_output_dir(args, game_dir, manifest)
        settings, enabled_settings = resolve_enabled_settings(manifest, args)
        patches = manifest_patches(manifest, settings, enabled_settings)
        assets = manifest_asset_patches(manifest, settings, enabled_settings)
        grouped = group_patches(patches)
        if not grouped and not assets and output_dir.resolve() == game_dir.resolve():
            raise PatchError("No active patches remain enabled.")
        emit_progress(args, "Verifying target files...")
        runtime_checks = verify_runtime_requirements(game_dir, manifest, settings, enabled_settings)
        target_checks = verify_target_files(game_dir, manifest, settings, enabled_settings)
        file_data = verify_patch_bytes(game_dir, grouped, args, process_log)
        asset_checks = verify_asset_patches(game_dir, output_dir, manifest_path.parent, assets, args, process_log)

        if not args.dry_run:
            skip_copy_paths = {
                str(check["file_path"])
                for check in asset_checks
                if str(check.get("output_file_path") or check["file_path"]) != str(check["file_path"])
            }
            prepare_output_dir(game_dir, output_dir, skip_copy_paths, args)
            if args.backup_dir:
                backup_dir = Path(args.backup_dir).resolve()
            else:
                backup_dir = output_dir / DEFAULT_BACKUP_ROOT / backup_slug(manifest_path)
            emit_progress(args, f"Creating backup: {backup_dir}")
            backup_manifest = create_backup(game_dir, output_dir, backup_dir, grouped, asset_checks, manifest_path)
            total_byte_patches = sum(len(patches_for_file) for patches_for_file in grouped.values())
            current_byte_patch = 0
            for rel_path, patches_for_file in grouped.items():
                target = resolve_under_game_dir(output_dir, rel_path)
                try:
                    atomic_write(target, apply_patches_to_data(file_data[rel_path], patches_for_file))
                except OSError as exc:
                    for patch in patches_for_file:
                        log_process_event(
                            process_log,
                            phase="apply",
                            kind="byte_patch",
                            status="error",
                            index=patch.index,
                            file_path=patch.file_path,
                            note=patch.note,
                            offset=f"0x{patch.offset:x}",
                            error=str(exc),
                        )
                    raise PatchError(f"Could not write patched file {rel_path}: {exc}") from exc
                for patch in patches_for_file:
                    current_byte_patch += 1
                    log_process_event(
                        process_log,
                        phase="apply",
                        kind="byte_patch",
                        status="success",
                        index=patch.index,
                        file_path=patch.file_path,
                        note=patch.note,
                        offset=f"0x{patch.offset:x}",
                        length=len(patch.replacement),
                    )
                    report_record_progress(
                        args,
                        phase="Applying",
                        kind="byte patch",
                        current=current_byte_patch,
                        total=total_byte_patches,
                        file_path=patch.file_path,
                        index=patch.index,
                    )
            apply_asset_patches(output_dir, manifest_path.parent, asset_checks, args, process_log)
            enforced_exe_name = enforce_modded_exe_name(game_dir, output_dir, manifest, process_log)
        else:
            enforced_exe_name = manifest_output_exe_name(manifest)

        patched_files = []
        for rel_path in sorted(grouped):
            output_rel_path = (
                enforced_exe_name
                if enforced_exe_name and Path(rel_path).name.lower() == DEFAULT_EXE_NAME.lower()
                else rel_path
            )
            target = resolve_under_game_dir(game_dir if args.dry_run else output_dir, output_rel_path)
            patched_files.append(
                {
                    "file_path": rel_path,
                    "output_file_path": output_rel_path,
                    "sha256": sha256_file(target) if not args.dry_run else None,
                    "size": target.stat().st_size if not args.dry_run else len(file_data[rel_path]),
                }
            )

        asset_files = []
        for check in asset_checks:
            output_file_path = str(check.get("output_file_path") or check["file_path"])
            output_target = resolve_under_game_dir(output_dir, output_file_path)
            asset_files.append(
                {
                    "file_path": check["file_path"],
                    "output_file_path": output_file_path,
                    "action": check["action"],
                    "sha256": sha256_file(output_target) if not args.dry_run and output_target.is_file() else None,
                    "size": output_target.stat().st_size if not args.dry_run and output_target.is_file() else check["source_size"],
                }
            )

        modded_exe_name = next(
            (
                Path(str(row["output_file_path"])).name
                for row in asset_files
                if Path(str(row["output_file_path"])).suffix.lower() == ".exe"
            ),
            enforced_exe_name or DEFAULT_EXE_NAME,
        )
        save_dir = Path.home() / "Documents" / "LDW" / Path(modded_exe_name).stem
        log = {
            "action": "apply",
            "dry_run": bool(args.dry_run),
            "status": "success",
            "timestamp_utc": utc_now(),
            "game_dir": str(game_dir),
            "output_dir": str(output_dir),
            "modded_exe_name": modded_exe_name,
            "modded_save_dir": str(save_dir),
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
            "asset_files": asset_files,
            "process_log": process_log,
        }
        if args.log:
            log_path = Path(args.log).resolve()
        elif backup_dir:
            log_path = backup_dir / "patch_log.json"
        else:
            log_path = manifest_path.with_name("patch_dry_run_log.json")
        write_json(log_path, log)
        setattr(args, "last_apply_log_path", str(log_path))
        setattr(
            args,
            "last_apply_summary",
            {
                "log_path": str(log_path),
                "game_dir": str(game_dir),
                "output_dir": str(output_dir),
                "modded_exe_name": modded_exe_name,
                "modded_save_dir": str(save_dir),
                "enabled_settings": sorted(enabled_settings),
                "settings": settings_log(settings, enabled_settings),
                "patched_files": patched_files,
                "asset_files": asset_files,
                "dry_run": bool(args.dry_run),
            },
        )

        if settings:
            print("Enabled settings: " + (", ".join(sorted(enabled_settings)) if enabled_settings else "(none)"))
            disabled_settings = sorted(set(settings) - enabled_settings)
            print("Disabled settings: " + (", ".join(disabled_settings) if disabled_settings else "(none)"))
        print(
            f"Validated {len(patches)} active byte patch record(s) across {len(grouped)} file(s) "
            f"and {len(assets)} active asset patch record(s)."
        )
        if args.dry_run:
            print(f"Dry run complete. Log: {log_path}")
        else:
            print(f"Patched files successfully. Modded folder: {output_dir}")
            print(f"Backup: {backup_dir}")
            print(f"Patch log: {log_path}")
        return 0
    except PatchError as exc:
        if args.log:
            failure_log_path = Path(args.log).resolve()
        elif backup_dir:
            failure_log_path = backup_dir / "patch_error_log.json"
        else:
            failure_log_path = manifest_path.with_name("patch_error_log.json")
        failure_log = {
            "action": "apply",
            "dry_run": bool(args.dry_run),
            "status": "failure",
            "timestamp_utc": utc_now(),
            "game_dir": str(game_dir),
            "manifest": str(manifest_path),
            "backup_dir": None if backup_dir is None else str(backup_dir),
            "settings": settings_log(settings, enabled_settings) if settings else None,
            "error": str(exc),
            "process_log": process_log,
        }
        write_json(failure_log_path, failure_log)
        emit_progress(args, f"Patch failed. Failure log: {failure_log_path}")
        if settings:
            disabled_settings = sorted(set(settings) - enabled_settings)
            emit_progress(args, "Enabled settings: " + (", ".join(sorted(enabled_settings)) if enabled_settings else "(none)"))
            emit_progress(args, "Disabled settings: " + (", ".join(disabled_settings) if disabled_settings else "(none)"))
        raise


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
    apply_cmd.add_argument("--game-dir", help="Path to the user-provided vanilla VF2 game directory.")
    apply_cmd.add_argument("--exe", help=f"Path to {DEFAULT_EXE_NAME}; the game directory is inferred from its parent.")
    apply_cmd.add_argument("--manifest", required=True, help="Path to the JSON patch manifest.")
    apply_cmd.add_argument("--output-dir", help="Optional modded game output folder. Defaults to the manifest output folder when present, otherwise patches in place.")
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
