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
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


BACKUP_MANIFEST = "vf2_patch_backup_manifest.json"
DEFAULT_BACKUP_ROOT = ".vf2_patch_backups"
DEFAULT_EXE_NAME = "Virtual Families 2.exe"
EXECUTABLE_OVERLAY_SETTINGS = {
    "island_events",
    "cheat_upgrades",
    "holiday_ornaments_collection",
    "behavior_patches",
    "mobile_renovations",
    "mobile_sound_assets",
}
RT_ICON = 3
RT_GROUP_ICON = 14
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
    allow_missing_target: bool
    overwrite_existing: bool
    note: str
    requires: tuple[str, ...]
    restore: bool = False
    remove_when_disabled: bool = False


@dataclass(frozen=True)
class PostAssetPatchVariant:
    index: int
    asset_sha256: str
    offset: int
    expected: bytes
    replacement: bytes
    note: str


@dataclass(frozen=True)
class PostAssetPatch:
    index: int
    file_path: str
    variants: tuple[PostAssetPatchVariant, ...]
    note: str
    requires: tuple[str, ...]


@dataclass(frozen=True)
class PatchSetting:
    id: str
    label: str
    description: str
    default: bool
    category: str = "main"


@dataclass(frozen=True)
class IconResource:
    resource_type: int
    name: int | str
    language: int
    data: bytes


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


def canonical_rel_path_key(rel_path: str) -> str:
    """Return a platform-independent key matching Windows path semantics."""
    return str(Path(rel_path)).replace("\\", "/").casefold()


def resolve_under_game_dir(game_dir: Path, rel_path: str) -> Path:
    root = game_dir.resolve()
    candidate = root / rel_path
    reject_symlink_components(candidate, root, rel_path)
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise PatchError(f"Path escapes game directory: {rel_path}")
    return resolved


def resolve_under_manifest_dir(manifest_dir: Path, rel_path: str) -> Path:
    root = manifest_dir.resolve()
    candidate = root / rel_path
    reject_symlink_components(candidate, root, rel_path)
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise PatchError(f"Path escapes manifest directory: {rel_path}")
    return resolved


def reject_symlink_components(candidate: Path, root: Path, rel_path: str) -> None:
    current = root
    for part in Path(rel_path).parts:
        current = current / part
        if current.is_symlink():
            raise PatchError(f"Symlink path components are not allowed: {rel_path}")


def resolve_under_backup_dir(backup_dir: Path, rel_path: str) -> Path:
    root = backup_dir.resolve()
    candidate = root / rel_path
    reject_symlink_components(candidate, root, rel_path)
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise PatchError(f"Backup path escapes backup directory: {rel_path}")
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


def pe_checksum_offset(data: bytes | bytearray) -> int:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise PatchError("Executable checksum target does not have a valid DOS header.")
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_off + 0x18 > len(data) or data[pe_off:pe_off + 4] != b"PE\0\0":
        raise PatchError("Executable checksum target does not have a valid PE header.")
    optional_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    optional_offset = pe_off + 24
    if optional_size < 68 or optional_offset + optional_size > len(data):
        raise PatchError("Executable checksum target has a truncated optional header.")
    magic = struct.unpack_from("<H", data, optional_offset)[0]
    if magic not in {0x10B, 0x20B}:
        raise PatchError(f"Executable checksum target has unsupported optional-header magic 0x{magic:x}.")
    return optional_offset + 64


def compute_pe_checksum(data: bytes | bytearray) -> int:
    """Return the Windows PE checksum with the stored checksum field treated as zero."""
    checksum_offset = pe_checksum_offset(data)
    padded = bytes(data) + (b"\0" if len(data) & 1 else b"")
    checksum = 0
    for offset in range(0, len(padded), 2):
        word = 0 if checksum_offset <= offset < checksum_offset + 4 else struct.unpack_from("<H", padded, offset)[0]
        checksum = (checksum & 0xFFFF) + word + (checksum >> 16)
    checksum = (checksum & 0xFFFF) + (checksum >> 16)
    checksum = (checksum & 0xFFFF) + (checksum >> 16)
    return (checksum + len(data)) & 0xFFFFFFFF


def refresh_pe_checksum(path: Path) -> int:
    """Write and verify the nonzero Windows PE checksum required by the final EXE."""
    try:
        data = bytearray(path.read_bytes())
        checksum_offset = pe_checksum_offset(data)
        checksum = compute_pe_checksum(data)
        if checksum == 0:
            raise PatchError(f"Computed a zero PE checksum for {path}.")
        struct.pack_into("<I", data, checksum_offset, checksum)
        path.write_bytes(data)
        written = path.read_bytes()
    except PatchError:
        raise
    except OSError as exc:
        raise PatchError(f"Could not refresh the PE checksum in {path}: {exc}") from exc
    stored = struct.unpack_from("<I", written, checksum_offset)[0]
    expected = compute_pe_checksum(written)
    if stored != checksum or stored != expected:
        raise PatchError(
            f"PE checksum verification failed for {path}: stored 0x{stored:08x}, "
            f"expected 0x{expected:08x}."
        )
    return stored


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
            "sha256": section.get("sha256"),
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


def relative_to_game_dir(game_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(game_dir.resolve()))
    except ValueError:
        return str(path)


def resolve_expected_exe_target(
    game_dir: Path,
    rel_path: str,
    expected_pe_structures: tuple[dict[str, Any], ...],
) -> tuple[Path, str, bool]:
    """Resolve an EXE target by its manifest path; PE layout is never an identity fallback."""
    target = resolve_under_game_dir(game_dir, rel_path)
    return target, rel_path, False


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


def _win32_resource_failure(action: str) -> PatchError:
    error_code = ctypes.get_last_error()
    if error_code:
        detail = ctypes.FormatError(error_code).strip()
        return PatchError(f"{action} failed (Windows error {error_code}: {detail}).")
    return PatchError(f"{action} failed (Windows did not report an error code).")


def _decode_resource_identifier(pointer: int | None) -> int | str:
    address = int(pointer or 0)
    if address <= 0xFFFF:
        return address
    return ctypes.wstring_at(address)


def _resource_identifier_pointer(
    value: int | str,
    keepalive: list[Any],
) -> ctypes.c_void_p:
    if isinstance(value, int):
        if value < 0 or value > 0xFFFF:
            raise PatchError(f"Invalid integer resource identifier: {value}.")
        return ctypes.c_void_p(value)
    buffer = ctypes.create_unicode_buffer(value)
    keepalive.append(buffer)
    return ctypes.cast(buffer, ctypes.c_void_p)


def _icon_resource_sort_key(resource: IconResource) -> tuple[Any, ...]:
    name_key: tuple[int, Any]
    if isinstance(resource.name, int):
        name_key = (0, resource.name)
    else:
        name_key = (1, resource.name)
    return resource.resource_type, *name_key, resource.language


def _canonical_icon_resources(resources: tuple[IconResource, ...] | list[IconResource]) -> tuple[IconResource, ...]:
    canonical = tuple(sorted(resources, key=_icon_resource_sort_key))
    seen: set[tuple[int, int | str, int]] = set()
    for resource in canonical:
        if resource.resource_type not in {RT_ICON, RT_GROUP_ICON}:
            raise PatchError(f"Unexpected executable icon resource type: {resource.resource_type}.")
        if not isinstance(resource.name, (int, str)) or resource.name == "":
            raise PatchError("Executable icon resource names must be non-empty strings or integer IDs.")
        if resource.language < 0 or resource.language > 0xFFFF:
            raise PatchError(f"Invalid executable icon resource language: {resource.language}.")
        if not resource.data:
            raise PatchError("Executable icon resources must not be empty.")
        identity = (resource.resource_type, resource.name, resource.language)
        if identity in seen:
            raise PatchError(f"Duplicate executable icon resource: {identity!r}.")
        seen.add(identity)
    return canonical


def _validate_group_icon_resources(resources: tuple[IconResource, ...]) -> None:
    """Validate GRPICONDIR records and their referenced RT_ICON images."""
    icon_sizes: dict[int, set[int]] = {}
    for resource in resources:
        if resource.resource_type == RT_ICON and isinstance(resource.name, int):
            icon_sizes.setdefault(resource.name, set()).add(len(resource.data))

    for resource in resources:
        if resource.resource_type != RT_GROUP_ICON:
            continue
        if len(resource.data) < 6:
            raise PatchError(f"Windows icon group {resource.name!r} has a truncated GRPICONDIR header.")
        reserved, image_type, image_count = struct.unpack_from("<HHH", resource.data)
        if reserved != 0 or image_type != 1 or image_count == 0:
            raise PatchError(
                f"Windows icon group {resource.name!r} has an invalid GRPICONDIR header "
                f"(reserved={reserved}, type={image_type}, count={image_count})."
            )
        expected_size = 6 + (image_count * 14)
        if len(resource.data) != expected_size:
            raise PatchError(
                f"Windows icon group {resource.name!r} has size {len(resource.data)}, "
                f"but its {image_count} entries require {expected_size} bytes."
            )
        for entry_index in range(image_count):
            entry_offset = 6 + (entry_index * 14)
            _width, _height, _colors, entry_reserved, _planes, _bits, image_size, image_id = (
                struct.unpack_from("<BBBBHHIH", resource.data, entry_offset)
            )
            if entry_reserved != 0:
                raise PatchError(
                    f"Windows icon group {resource.name!r} entry {entry_index} has a nonzero reserved byte."
                )
            available_sizes = icon_sizes.get(image_id)
            if not available_sizes:
                raise PatchError(
                    f"Windows icon group {resource.name!r} entry {entry_index} references missing "
                    f"RT_ICON ID {image_id}."
                )
            if image_size not in available_sizes:
                raise PatchError(
                    f"Windows icon group {resource.name!r} entry {entry_index} declares {image_size} bytes "
                    f"for RT_ICON ID {image_id}, but the available resource sizes are "
                    f"{sorted(available_sizes)}."
                )


def validate_executable_shell_icon(path: Path, sizes: tuple[int, ...] = (16, 32, 48)) -> tuple[int, ...]:
    """Prove that Windows can extract the executable icon at shell/taskbar sizes."""
    if os.name != "nt":
        raise PatchError("Executable icon validation is supported only on Windows.")
    if not path.is_file():
        raise PatchError(f"Executable icon validation target does not exist: {path}")
    if not sizes or any(not isinstance(size, int) or size <= 0 for size in sizes):
        raise PatchError("Executable icon validation sizes must be positive integers.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)  # type: ignore[attr-defined]
    user32.PrivateExtractIconsW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint),
        ctypes.c_uint,
        ctypes.c_uint,
    ]
    user32.PrivateExtractIconsW.restype = ctypes.c_uint
    user32.DestroyIcon.argtypes = [ctypes.c_void_p]
    user32.DestroyIcon.restype = ctypes.c_int

    validated: list[int] = []
    for size in sizes:
        icon_handle = ctypes.c_void_p()
        icon_id = ctypes.c_uint()
        ctypes.set_last_error(0)
        extracted = user32.PrivateExtractIconsW(
            str(path),
            0,
            size,
            size,
            ctypes.byref(icon_handle),
            ctypes.byref(icon_id),
            1,
            0,
        )
        try:
            if extracted != 1 or not icon_handle.value:
                error_code = ctypes.get_last_error()
                detail = f" Win32 error {error_code}." if error_code else ""
                raise PatchError(
                    f"Windows could not extract a {size}x{size} shell icon from {path}." + detail
                )
            validated.append(size)
        finally:
            if icon_handle.value:
                user32.DestroyIcon(icon_handle)
    return tuple(validated)


def _enumerate_executable_icon_resources(path: Path) -> tuple[IconResource, ...]:
    if os.name != "nt":
        raise PatchError("Executable icon preservation is supported only on Windows.")
    if not path.is_file():
        raise PatchError(f"Executable icon source does not exist: {path}")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    name_callback_type = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined]
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ssize_t,
    )
    language_callback_type = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined]
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ushort,
        ctypes.c_ssize_t,
    )
    kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    kernel32.LoadLibraryExW.restype = ctypes.c_void_p
    kernel32.FreeLibrary.argtypes = [ctypes.c_void_p]
    kernel32.FreeLibrary.restype = ctypes.c_int
    kernel32.EnumResourceNamesW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        name_callback_type,
        ctypes.c_ssize_t,
    ]
    kernel32.EnumResourceNamesW.restype = ctypes.c_int
    kernel32.EnumResourceLanguagesW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        language_callback_type,
        ctypes.c_ssize_t,
    ]
    kernel32.EnumResourceLanguagesW.restype = ctypes.c_int
    kernel32.FindResourceExW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ushort,
    ]
    kernel32.FindResourceExW.restype = ctypes.c_void_p
    kernel32.LoadResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.LoadResource.restype = ctypes.c_void_p
    kernel32.LockResource.argtypes = [ctypes.c_void_p]
    kernel32.LockResource.restype = ctypes.c_void_p
    kernel32.SizeofResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.SizeofResource.restype = ctypes.c_uint32

    load_flags = 0x00000002 | 0x00000020  # LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE
    module = kernel32.LoadLibraryExW(str(path), None, load_flags)
    if not module:
        raise _win32_resource_failure(f"Loading executable resources from {path}")

    resources: list[IconResource] = []
    callback_errors: list[PatchError] = []
    try:
        for resource_type in (RT_ICON, RT_GROUP_ICON):
            def on_name(
                callback_module: int,
                type_pointer: int,
                name_pointer: int,
                _parameter: int,
                *,
                current_type: int = resource_type,
            ) -> int:
                def on_language(
                    language_module: int,
                    language_type_pointer: int,
                    language_name_pointer: int,
                    language: int,
                    _language_parameter: int,
                ) -> int:
                    try:
                        resource_info = kernel32.FindResourceExW(
                            language_module,
                            language_type_pointer,
                            language_name_pointer,
                            language,
                        )
                        if not resource_info:
                            raise _win32_resource_failure(f"Finding icon resource in {path}")
                        size = kernel32.SizeofResource(language_module, resource_info)
                        loaded = kernel32.LoadResource(language_module, resource_info)
                        if not loaded:
                            raise _win32_resource_failure(f"Loading icon resource from {path}")
                        data_pointer = kernel32.LockResource(loaded)
                        if size and not data_pointer:
                            raise _win32_resource_failure(f"Locking icon resource from {path}")
                        resources.append(
                            IconResource(
                                resource_type=current_type,
                                name=_decode_resource_identifier(language_name_pointer),
                                language=int(language),
                                data=ctypes.string_at(data_pointer, size),
                            )
                        )
                        return 1
                    except PatchError as exc:
                        callback_errors.append(exc)
                        return 0
                    except Exception as exc:
                        callback_errors.append(PatchError(f"Could not read icon resource from {path}: {exc}"))
                        return 0

                language_callback = language_callback_type(on_language)
                ctypes.set_last_error(0)
                enumerated = kernel32.EnumResourceLanguagesW(
                    callback_module,
                    type_pointer,
                    name_pointer,
                    language_callback,
                    0,
                )
                if not enumerated and not callback_errors:
                    callback_errors.append(_win32_resource_failure(f"Enumerating icon resource languages in {path}"))
                return 0 if callback_errors else 1

            name_callback = name_callback_type(on_name)
            ctypes.set_last_error(0)
            enumerated = kernel32.EnumResourceNamesW(
                module,
                ctypes.c_void_p(resource_type),
                name_callback,
                0,
            )
            if callback_errors:
                raise callback_errors[0]
            if not enumerated:
                error_code = ctypes.get_last_error()
                if error_code in {1812, 1813}:  # No resource section, or requested type not found.
                    continue
                raise _win32_resource_failure(f"Enumerating executable icon resources in {path}")
    finally:
        kernel32.FreeLibrary(module)

    return _canonical_icon_resources(resources)


def read_executable_icon_resources(path: Path) -> tuple[IconResource, ...]:
    resources = _enumerate_executable_icon_resources(path)
    icon_count = sum(resource.resource_type == RT_ICON for resource in resources)
    group_count = sum(resource.resource_type == RT_GROUP_ICON for resource in resources)
    if not icon_count or not group_count:
        raise PatchError(
            f"The stock executable does not contain a complete Windows icon resource set: {path} "
            f"(RT_ICON={icon_count}, RT_GROUP_ICON={group_count})."
        )
    _validate_group_icon_resources(resources)
    validate_executable_shell_icon(path)
    return resources


def _update_executable_icon_resources(path: Path, resources: tuple[IconResource, ...]) -> None:
    existing = _enumerate_executable_icon_resources(path)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel32.BeginUpdateResourceW.argtypes = [ctypes.c_wchar_p, ctypes.c_int]
    kernel32.BeginUpdateResourceW.restype = ctypes.c_void_p
    kernel32.UpdateResourceW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ushort,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    kernel32.UpdateResourceW.restype = ctypes.c_int
    kernel32.EndUpdateResourceW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    kernel32.EndUpdateResourceW.restype = ctypes.c_int

    update_handle = kernel32.BeginUpdateResourceW(str(path), 0)
    if not update_handle:
        raise _win32_resource_failure(f"Opening {path} for icon resource update")

    keepalive: list[Any] = []
    try:
        delete_order = sorted(existing, key=lambda item: item.resource_type != RT_GROUP_ICON)
        for resource in delete_order:
            type_pointer = _resource_identifier_pointer(resource.resource_type, keepalive)
            name_pointer = _resource_identifier_pointer(resource.name, keepalive)
            if not kernel32.UpdateResourceW(
                update_handle,
                type_pointer,
                name_pointer,
                resource.language,
                None,
                0,
            ):
                raise _win32_resource_failure(f"Removing an existing icon resource from {path}")

        add_order = sorted(resources, key=lambda item: item.resource_type == RT_GROUP_ICON)
        for resource in add_order:
            type_pointer = _resource_identifier_pointer(resource.resource_type, keepalive)
            name_pointer = _resource_identifier_pointer(resource.name, keepalive)
            data_buffer = ctypes.create_string_buffer(resource.data)
            keepalive.append(data_buffer)
            if not kernel32.UpdateResourceW(
                update_handle,
                type_pointer,
                name_pointer,
                resource.language,
                ctypes.cast(data_buffer, ctypes.c_void_p),
                len(resource.data),
            ):
                raise _win32_resource_failure(f"Writing a stock icon resource to {path}")

        committed = kernel32.EndUpdateResourceW(update_handle, 0)
        update_handle = None
        if not committed:
            raise _win32_resource_failure(f"Committing stock icon resources to {path}")
    except Exception:
        if update_handle:
            kernel32.EndUpdateResourceW(update_handle, 1)
        raise


def write_executable_icon_resources_atomic(path: Path, resources: tuple[IconResource, ...]) -> None:
    canonical = _canonical_icon_resources(resources)
    if not any(resource.resource_type == RT_ICON for resource in canonical):
        raise PatchError("Cannot write executable icon resources without at least one RT_ICON record.")
    if not any(resource.resource_type == RT_GROUP_ICON for resource in canonical):
        raise PatchError("Cannot write executable icon resources without at least one RT_GROUP_ICON record.")
    _validate_group_icon_resources(canonical)
    if not path.is_file():
        raise PatchError(f"Generated modded executable does not exist: {path}")

    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".vf2icon.exe", dir=path.parent)
    os.close(descriptor)
    temp = Path(temp_name)
    try:
        shutil.copy2(path, temp)
        temp.chmod(temp.stat().st_mode | 0o200)
        _update_executable_icon_resources(temp, canonical)
        refresh_pe_checksum(temp)
        written = _enumerate_executable_icon_resources(temp)
        if written != canonical:
            raise PatchError(f"Stock icon resource verification failed after updating {path}.")
        _validate_group_icon_resources(written)
        validate_executable_shell_icon(temp)
        path.chmod(path.stat().st_mode | 0o200)
        temp.replace(path)
    except PatchError:
        raise
    except OSError as exc:
        raise PatchError(f"Could not preserve stock executable icon resources in {path}: {exc}") from exc
    finally:
        if temp.exists():
            temp.unlink()


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


def manifest_preserve_stock_exe_icon(manifest: dict[str, Any]) -> bool:
    raw = manifest.get("output", manifest.get("output_folder"))
    if not isinstance(raw, dict):
        return False
    value = raw.get("preserve_stock_exe_icon", False)
    if not isinstance(value, bool):
        raise PatchError("Manifest output preserve_stock_exe_icon must be true or false.")
    return value


def manifest_output_save_folder_name(manifest: dict[str, Any], exe_name: str) -> str:
    raw = manifest.get("output", manifest.get("output_folder"))
    if isinstance(raw, dict):
        name = str(raw.get("default_save_folder_name", raw.get("save_folder_name", ""))).strip()
        if name:
            rel = normalize_rel_path(name, "manifest output save folder name")
            if len(Path(rel).parts) != 1:
                raise PatchError("Manifest output save folder name must be a single folder name.")
            return rel
    return Path(exe_name).stem


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
        parent = getattr(args, "output_parent_dir", None)
        if parent:
            return (Path(parent).resolve() / folder_name).resolve()
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


def is_recognized_modded_output_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if (path / DEFAULT_BACKUP_ROOT).is_dir():
        return True
    if path.name.startswith("VF2-") and path.name.endswith("-Modded"):
        return True
    return any(child.is_file() and child.suffix.lower() == ".exe" and "modded" in child.stem.lower() for child in path.iterdir())


def verify_reconfigure_output_dir(output_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if not output_dir.is_dir():
        raise PatchError(f"Modded output folder does not exist: {output_dir}")
    if not is_recognized_modded_output_dir(output_dir):
        raise PatchError(
            "Output-only reconfiguration requires an existing VF2 modded output folder. "
            f"This folder was not recognized as modded: {output_dir}"
        )
    exe_name = manifest_output_exe_name(manifest)
    exe_candidates = sorted(output_dir.glob("*.exe"))
    if exe_name and not (output_dir / exe_name).is_file() and not exe_candidates:
        raise PatchError(f"Modded output folder does not contain the expected modded executable: {exe_name}")
    return [
        {
            "path": str(output_dir),
            "status": "success",
            "mode": "existing_modded_output",
            "exe_count": len(exe_candidates),
        }
    ]


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
            ignored_exe_names = []
            for path in game_dir.iterdir():
                if path.name in expected:
                    actual.add(path.name)
                    continue
                if (
                    path.is_file()
                    and path.suffix.lower() == ".exe"
                ):
                    if accepted_exe_structures and pe_structure_matches_any(path, tuple(accepted_exe_structures)):
                        accepted_exe_names.append(path.name)
                    else:
                        ignored_exe_names.append(path.name)
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
            checks.append(
                {
                    "kind": "exact_top_level_entries",
                    "count": len(expected),
                    "accepted_exe_names": accepted_exe_names,
                    "ignored_exe_names": ignored_exe_names,
                }
            )
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
    *,
    restore_inactive: bool = False,
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
        restore_source_value = raw.get("restore_source_path", raw.get("restore_source_file", raw.get("restore_source")))
        file_path = normalize_rel_path(target_value, f"asset patch #{index} target path")
        output_file_path = None
        if output_value is not None:
            output_file_path = normalize_rel_path(output_value, f"asset patch #{index} output path")
        requires = record_requires(raw, f"asset patch #{index}")
        ensure_known_settings(requires, settings, f"Asset patch #{index}")
        active = record_is_active(requires, enabled_settings)
        restore_requires_raw = raw.get("restore_requires")
        restore_requires = ()
        if restore_requires_raw is not None:
            restore_requires = record_requires(
                {"requires": restore_requires_raw},
                f"asset patch #{index} restore_requires",
            )
            ensure_known_settings(
                restore_requires,
                settings,
                f"Asset patch #{index} restore_requires",
            )
        if restore_inactive and active:
            continue
        restore = False
        remove_when_disabled = False
        if not active:
            if not restore_inactive:
                continue
            restore_allowed = not restore_requires or record_is_active(restore_requires, enabled_settings)
            if restore_source_value is not None and restore_allowed:
                source_value = restore_source_value
                restore = True
            elif bool(raw.get("remove_when_disabled", False)):
                remove_when_disabled = True
            else:
                continue
        source_path = normalize_rel_path(source_value, f"asset patch #{index} source path")
        source_sha_field = "restore_source_sha256" if restore else "source_sha256"
        source_size_field = "restore_source_size" if restore else "source_size"
        if restore and raw.get(source_sha_field) is None:
            continue
        source_sha = normalize_sha256(
            raw.get(source_sha_field, raw.get("sha256")),
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
        if file_path.lower().endswith(".exe") and expected_target_sha is None:
            raise PatchError(
                f"Asset patch #{index} executable target requires expected_target_sha256; "
                "PE structure alone is not an executable identity."
            )
        source_size = None
        if raw.get(source_size_field, raw.get("size")) is not None:
            source_size = parse_int(raw.get(source_size_field, raw.get("size")), f"asset patch #{index} source_size")
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
                allow_missing_target=bool(raw.get("allow_missing_target", raw.get("allow_create_if_missing", False))),
                overwrite_existing=bool(
                    True if restore else raw.get("overwrite_existing", raw.get("replace_existing", raw.get("overwrite", False)))
                ),
                note=(
                    "Restore disabled setting: " if restore
                    else "Remove disabled setting: " if remove_when_disabled
                    else ""
                ) + str(raw.get("note", "")).strip(),
                requires=() if (restore or remove_when_disabled) else requires,
                restore=restore,
                remove_when_disabled=remove_when_disabled,
            )
        )
    return select_exact_executable_overlays(assets, enabled_settings)


def select_exact_executable_overlays(
    assets: list[AssetPatch],
    enabled_settings: set[str],
) -> list[AssetPatch]:
    """Keep exactly one executable overlay for each active output target.

    Overlay EXEs all write the same named modded executable. Applying multiple
    feature overlays sequentially can silently drop earlier code when no
    combined overlay exists. Fail closed unless the manifest contains exactly
    one record matching the complete enabled overlay set.
    """
    grouped: dict[str, list[AssetPatch]] = {}
    for asset in assets:
        if not asset.source_path.lower().endswith(".exe"):
            continue
        if "core_executable" not in asset.requires:
            continue
        output_path = canonical_rel_path_key(asset.output_file_path or asset.file_path)
        grouped.setdefault(output_path, []).append(asset)

    selected = set()
    for group in grouped.values():
        present_overlay_settings = {
            setting
            for asset in group
            for setting in EXECUTABLE_OVERLAY_SETTINGS
            if setting in asset.requires
        }
        # A plain executable plus a post-asset/runtime-flag record is not an
        # executable overlay matrix and must retain the existing sequencing.
        if not present_overlay_settings:
            selected.update(id(asset) for asset in group)
            continue
        enabled_overlay_settings = {
            setting for setting in EXECUTABLE_OVERLAY_SETTINGS
            if setting in enabled_settings and setting in present_overlay_settings
        }
        wanted = {"core_executable", *enabled_overlay_settings}
        exact = [asset for asset in group if set(asset.requires) == wanted]
        if len(exact) != 1:
            labels = ", ".join(sorted(enabled_overlay_settings)) or "none"
            raise PatchError(
                "No unique executable overlay matches the enabled feature set "
                f"({labels}) for {group[0].output_file_path or group[0].file_path}."
            )
        selected.add(id(exact[0]))

    return [
        asset for asset in assets
        if (
            not asset.source_path.lower().endswith(".exe")
            or "core_executable" not in asset.requires
            or id(asset) in selected
        )
    ]


def validate_asset_target_plan(assets: list[AssetPatch]) -> None:
    """Reject conflicting active/restore/remove records before mutation."""
    grouped: dict[str, list[AssetPatch]] = {}
    for asset in assets:
        output_path = canonical_rel_path_key(asset.output_file_path or asset.file_path)
        grouped.setdefault(output_path, []).append(asset)
    for output_path, group in grouped.items():
        if len(group) < 2:
            continue
        has_restore_or_remove = any(
            asset.restore or asset.remove_when_disabled for asset in group
        )
        all_executable = all(asset.source_path.lower().endswith(".exe") for asset in group)
        if has_restore_or_remove:
            modes = ", ".join(
                "restore" if asset.restore else "remove" if asset.remove_when_disabled else "active"
                for asset in group
            )
            raise PatchError(
                f"Conflicting duplicate asset output target {output_path}: {modes}."
            )
        if not all_executable:
            requirement_signatures = [asset.requires for asset in group]
            source_signatures = [asset.source_path.casefold() for asset in group]
            if (
                len(set(requirement_signatures)) == len(requirement_signatures)
                and len(set(source_signatures)) == len(source_signatures)
            ):
                # Distinct active requirement signatures are an explicit
                # layered visual override; identical signatures are an
                # ambiguous duplicate and fail closed.
                continue
            raise PatchError(
                f"Conflicting duplicate asset output target {output_path}: active, active."
            )


def suppress_active_assets_replaced_by_restore(
    active_assets: list[AssetPatch],
    restore_assets: list[AssetPatch],
) -> list[AssetPatch]:
    """Prefer a selected restore/remove record for a duplicate output path.

    Optional visual layers can share the same target as their normal feature
    asset. During output-only reconfiguration, the selected restore must be the
    sole writer for that path; otherwise the normal active record would make the
    target plan fail closed before the restore can run.
    """

    restore_targets = {
        canonical_rel_path_key(asset.output_file_path or asset.file_path)
        for asset in restore_assets
        if asset.restore or asset.remove_when_disabled
    }
    if not restore_targets:
        return active_assets
    return [
        asset
        for asset in active_assets
        if canonical_rel_path_key(asset.output_file_path or asset.file_path) not in restore_targets
    ]


def verify_reconfigure_executable_identity(
    manifest: dict[str, Any],
    manifest_dir: Path,
    output_dir: Path,
    active_assets: list[AssetPatch],
) -> None:
    """Fail closed before output-only EXE replacement.

    A reconfiguration may switch between known core/overlay payloads, so all
    bundled executable source hashes are accepted for each output path. Any
    other current hash is treated as locally modified or from another build.
    """
    raw_assets = manifest.get("asset_patches", manifest.get("assets", []))
    if not isinstance(raw_assets, list):
        return
    if not any(
        isinstance(raw, dict)
        and EXECUTABLE_OVERLAY_SETTINGS.intersection(record_requires(raw, "executable overlay"))
        for raw in raw_assets
    ):
        # Older/core-only output manifests may have post-asset transforms that
        # legitimately change the final EXE hash; this guard is for the
        # cheat/mobile overlay switch boundary.
        return
    candidates: dict[str, set[str]] = {}
    base_candidates: dict[str, set[str]] = {}
    for index, raw in enumerate(raw_assets):
        if not isinstance(raw, dict):
            continue
        source_value = raw.get("source_path", raw.get("source_file", raw.get("source")))
        if not isinstance(source_value, str) or not source_value.lower().endswith(".exe"):
            continue
        output_value = raw.get("output_file_path", raw.get("output_path", raw.get("write_path")))
        output_path = normalize_rel_path(
            output_value if output_value is not None else raw.get("file_path", raw.get("target_path", raw.get("target", raw.get("path")))),
            f"asset patch #{index} output path",
        )
        source = resolve_under_manifest_dir(manifest_dir, normalize_rel_path(source_value, f"asset patch #{index} source path"))
        if not source.is_file():
            raise PatchError(f"Asset source file does not exist: {source_value}")
        actual_source_sha = sha256_file(source)
        declared_source_sha = normalize_sha256(
            raw.get("source_sha256", raw.get("sha256")),
            f"asset patch #{index} source_sha256",
            required=True,
        )
        if actual_source_sha != declared_source_sha:
            raise PatchError(
                f"SHA-256 mismatch for executable source {source_value}: "
                f"expected {declared_source_sha}, got {actual_source_sha}"
            )
        output_key = canonical_rel_path_key(output_path)
        candidates.setdefault(output_key, set()).add(actual_source_sha)
        base_candidates.setdefault(output_key, set()).add(actual_source_sha)

    raw_post_patches = manifest.get("post_asset_patches", [])
    if isinstance(raw_post_patches, list):
        for index, raw in enumerate(raw_post_patches):
            if not isinstance(raw, dict):
                continue
            file_value = raw.get("file_path", raw.get("file", raw.get("path")))
            if not isinstance(file_value, str):
                continue
            output_key = canonical_rel_path_key(
                normalize_rel_path(file_value, f"post-asset patch #{index} file path")
            )
            for variant_index, variant in enumerate(raw.get("variants", [])):
                if not isinstance(variant, dict) or "result_asset_sha256" not in variant:
                    continue
                result_sha = normalize_sha256(
                    variant.get("result_asset_sha256"),
                    f"post-asset patch #{index} variant #{variant_index} result_asset_sha256",
                    required=True,
                )
                candidates.setdefault(output_key, set()).add(result_sha or "")

    if not candidates:
        return
    active_outputs = {
        canonical_rel_path_key(asset.output_file_path or asset.file_path)
        for asset in active_assets
        if asset.source_path.lower().endswith(".exe")
    }
    for output_key, allowed_hashes in candidates.items():
        output_path = Path(output_key)
        target = resolve_under_game_dir(output_dir, output_path)
        if output_key not in active_outputs:
            raise PatchError(
                f"Output-only reconfiguration has no active executable record for {output_path}; "
                "keep core_executable enabled or provide a restore source."
            )
        if not target.is_file():
            raise PatchError(f"Output-only executable target is missing: {output_path}")
        current_sha = sha256_file(target)
        composed_toggle_match = False
        if current_sha not in allowed_hashes:
            current_data = target.read_bytes()
            for base_sha in base_candidates.get(output_key, set()):
                normalized = bytearray(current_data)
                recognized_ranges = 0
                valid = True
                for post_index, raw in enumerate(raw_post_patches if isinstance(raw_post_patches, list) else []):
                    if not isinstance(raw, dict):
                        continue
                    file_value = raw.get("file_path", raw.get("file", raw.get("path")))
                    if not isinstance(file_value, str) or canonical_rel_path_key(normalize_rel_path(
                        file_value, f"post-asset patch #{post_index} file path"
                    )) != output_key:
                        continue
                    selected = None
                    for variant_index, variant in enumerate(raw.get("variants", [])):
                        if not isinstance(variant, dict):
                            continue
                        variant_sha = normalize_sha256(
                            variant.get("asset_sha256", variant.get("expected_asset_sha256", variant.get("source_sha256"))),
                            f"post-asset patch #{post_index} variant #{variant_index} asset_sha256",
                            required=True,
                        )
                        if variant_sha == base_sha:
                            selected = (variant_index, variant)
                            break
                    if selected is None:
                        continue
                    variant_index, variant = selected
                    expected = parse_hex_bytes(
                        variant.get("expected_asset_bytes", variant.get("expected_bytes", variant.get("expected"))),
                        f"post-asset patch #{post_index} variant #{variant_index} expected bytes",
                    )
                    replacement = parse_hex_bytes(
                        variant.get("replacement_bytes", variant.get("replacement", variant.get("new"))),
                        f"post-asset patch #{post_index} variant #{variant_index} replacement bytes",
                    )
                    offset = parse_int(
                        variant.get("offset"),
                        f"post-asset patch #{post_index} variant #{variant_index} offset",
                    )
                    end = offset + len(expected)
                    if (
                        not expected
                        or len(expected) != len(replacement)
                        or offset < 0
                        or end > len(normalized)
                    ):
                        valid = False
                        break
                    current_bytes = bytes(current_data[offset:end])
                    if current_bytes not in (expected, replacement):
                        valid = False
                        break
                    normalized[offset:end] = expected
                    recognized_ranges += 1
                if (
                    valid
                    and recognized_ranges > 0
                    and hashlib.sha256(normalized).hexdigest() == base_sha
                ):
                    composed_toggle_match = True
                    break
        if current_sha not in allowed_hashes and not composed_toggle_match:
            raise PatchError(
                f"Refusing output-only executable replacement for {output_path}: "
                f"unknown current SHA-256 {current_sha}."
            )


def manifest_post_asset_patches(
    manifest: dict[str, Any],
    settings: dict[str, PatchSetting],
    enabled_settings: set[str],
) -> list[PostAssetPatch]:
    raw_patches = manifest.get("post_asset_patches", [])
    if not isinstance(raw_patches, list):
        raise PatchError("Manifest 'post_asset_patches' must be an array when present.")
    patches: list[PostAssetPatch] = []
    for index, raw in enumerate(raw_patches):
        if not isinstance(raw, dict):
            raise PatchError(f"Post-asset patch #{index} must be an object.")
        file_path = normalize_rel_path(
            raw.get("file_path", raw.get("file", raw.get("path"))),
            f"post-asset patch #{index} file path",
        )
        requires = record_requires(raw, f"post-asset patch #{index}")
        ensure_known_settings(requires, settings, f"Post-asset patch #{index}")
        if not record_is_active(requires, enabled_settings):
            continue
        raw_variants = raw.get("variants")
        if not isinstance(raw_variants, list) or not raw_variants:
            raise PatchError(f"Post-asset patch #{index} variants must be a non-empty array.")
        variants: list[PostAssetPatchVariant] = []
        variant_indexes_by_sha256: dict[str, int] = {}
        for variant_index, raw_variant in enumerate(raw_variants):
            if not isinstance(raw_variant, dict):
                raise PatchError(f"Post-asset patch #{index} variant #{variant_index} must be an object.")
            asset_sha256 = normalize_sha256(
                raw_variant.get(
                    "asset_sha256",
                    raw_variant.get("expected_asset_sha256", raw_variant.get("source_sha256")),
                ),
                f"post-asset patch #{index} variant #{variant_index} asset_sha256",
                required=True,
            )
            normalized_asset_sha256 = asset_sha256 or ""
            previous_variant_index = variant_indexes_by_sha256.get(normalized_asset_sha256)
            if previous_variant_index is not None:
                raise PatchError(
                    f"Post-asset patch #{index} variant #{variant_index} duplicates asset_sha256 "
                    f"from variant #{previous_variant_index}: {normalized_asset_sha256}"
                )
            variant_indexes_by_sha256[normalized_asset_sha256] = variant_index
            expected = parse_hex_bytes(
                raw_variant.get(
                    "expected_asset_bytes",
                    raw_variant.get("expected_bytes", raw_variant.get("expected")),
                ),
                f"post-asset patch #{index} variant #{variant_index} expected bytes",
            )
            replacement = parse_hex_bytes(
                raw_variant.get("replacement_bytes", raw_variant.get("replacement", raw_variant.get("new"))),
                f"post-asset patch #{index} variant #{variant_index} replacement bytes",
            )
            if not expected:
                raise PatchError(f"Post-asset patch #{index} variant #{variant_index} expected bytes must not be empty.")
            if len(expected) != len(replacement):
                raise PatchError(
                    f"Post-asset patch #{index} variant #{variant_index} changes byte length "
                    f"({len(expected)} -> {len(replacement)}); length-changing patches are not supported."
                )
            offset = parse_int(
                raw_variant.get("offset"),
                f"post-asset patch #{index} variant #{variant_index} offset",
            )
            if offset < 0:
                raise PatchError(f"Post-asset patch #{index} variant #{variant_index} offset must not be negative.")
            variants.append(
                PostAssetPatchVariant(
                    index=variant_index,
                    asset_sha256=normalized_asset_sha256,
                    offset=offset,
                    expected=expected,
                    replacement=replacement,
                    note=str(raw_variant.get("note", "")).strip(),
                )
            )
        patches.append(
            PostAssetPatch(
                index=index,
                file_path=file_path,
                variants=tuple(variants),
                note=str(raw.get("note", "")).strip(),
                requires=requires,
            )
        )
    return patches


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
        expected_sha = normalize_sha256(
            raw.get("sha256", raw.get("hash")),
            f"target file #{index} sha256",
            required=Path(rel_path).suffix.lower() == ".exe",
        )
        expected_pe_structures = normalize_pe_structure_list(
            raw.get(
                "pe_structures",
                raw.get("accepted_pe_structures", raw.get("pe_structure", raw.get("binary_structure", raw.get("structure")))),
            ),
            f"target file #{index} pe_structures",
        )

        path, rel_path, discovered_by_structure = resolve_expected_exe_target(
            game_dir,
            rel_path,
            expected_pe_structures,
        )
        if not path.is_file():
            raise install_validation_error(manifest, f"target file does not exist: {rel_path}")
        actual_sha = sha256_file(path)
        actual_size = path.stat().st_size
        actual_timestamp = pe_timestamp(path)
        version_info = windows_file_versions(path)

        matched_by = None
        if expected_sha and actual_sha.lower() != expected_sha:
            raise install_validation_error(
                manifest,
                f"SHA-256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}",
            )
        if expected_sha:
            matched_by = "sha256"
        if expected_pe_structures and not pe_structure_matches_any(path, expected_pe_structures):
            raise install_validation_error(
                manifest,
                f"PE section identity mismatch for {rel_path}; supplied section hashes/layout do not match.",
            )

        if path.suffix.lower() == ".exe" and expected_sha:
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
                "discovered_by_structure": discovered_by_structure,
                **version_info,
            }
        )
    if not saw_exe_sha:
        raise PatchError("Manifest must verify the original VF2 executable with an exact SHA-256 target_files entry.")
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

            reconfigure_output = bool(getattr(args, "reconfigure_output", False))
            separate_output = output_dir.resolve() != game_dir.resolve()
            output_file_path = asset.output_file_path or asset.file_path
            executable_asset = any(
                Path(path).suffix.lower() == ".exe"
                for path in (asset.file_path, output_file_path)
            )
            authenticate_existing_target = not reconfigure_output and (
                not separate_output or not asset.overwrite_existing or executable_asset
            )
            output_target = resolve_under_game_dir(output_dir, output_file_path)
            output_is_validation_target = output_file_path == asset.file_path
            target, target_file_path, discovered_by_structure = resolve_expected_exe_target(
                game_dir,
                asset.file_path,
                asset.expected_target_pe_structures,
            )
            if reconfigure_output and not output_is_validation_target:
                target = output_target
                target_file_path = output_file_path
                discovered_by_structure = False
            target_exists = target.is_file()
            target_sha = sha256_file(target) if target_exists else None
            target_size = target.stat().st_size if target_exists else None
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
            if asset.remove_when_disabled:
                if not reconfigure_output:
                    raise PatchError(
                        f"Asset removal for disabled setting requires output-only reconfiguration: {asset.file_path}"
                    )
                if target_exists and target_sha != source_sha:
                    raise PatchError(
                        f"Refusing removal of {asset.file_path}: target SHA-256 {target_sha} "
                        f"does not match the known enabled asset {source_sha}."
                    )
                action = "remove" if target_exists else "remove_missing"
            elif target_exists:
                action = "replace"
                if (
                    authenticate_existing_target
                    and asset.expected_target_sha256
                    and target_sha != asset.expected_target_sha256
                ):
                    raise PatchError(
                        f"SHA-256 mismatch for existing asset target {asset.file_path}: "
                        f"expected {asset.expected_target_sha256}, got {target_sha}"
                    )
                if (
                    authenticate_existing_target
                    and asset.expected_target_pe_structures
                    and not expected_structure_matches
                    and not asset.expected_target_sha256
                ):
                    raise PatchError(f"PE structure mismatch for existing asset target {asset.file_path}.")
                if (
                    authenticate_existing_target
                    and
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
                if not reconfigure_output:
                    if not asset.allow_missing_target:
                        raise PatchError(f"Expected existing asset target is missing: {asset.file_path}")
                    action = "create"
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
            "target_file_path": target_file_path,
            "output_file_path": output_file_path,
            "source_path": asset.source_path,
            "source_sha256": source_sha,
            "source_size": source_size,
            "target_existed": target_exists,
            "target_sha256": target_sha,
            "target_size": target_size,
            "target_structure_matched": bool(expected_structure_matches),
            "discovered_by_structure": discovered_by_structure,
            "output_existed": output_exists,
            "output_sha256": output_sha,
            "output_size": output_size,
            "action": action,
            "remove_when_disabled": asset.remove_when_disabled,
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


def verify_post_asset_patches(
    manifest_dir: Path,
    patches: list[PostAssetPatch],
    asset_checks: list[dict[str, Any]],
    args: argparse.Namespace,
    process_log: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_assets: dict[str, dict[str, Any]] = {}
    for check in asset_checks:
        output_file_path = str(check.get("output_file_path") or check["file_path"])
        # Asset patches are applied in manifest order, so the last active record
        # for an output path is the payload that the post-asset phase will see.
        selected_assets[canonical_rel_path_key(output_file_path)] = check

    checks: list[dict[str, Any]] = []
    total = len(patches)
    for current, patch in enumerate(patches, start=1):
        try:
            selected_asset = selected_assets.get(canonical_rel_path_key(patch.file_path))
            if selected_asset is None:
                raise PatchError(
                    f"Post-asset patch #{patch.index} has no active asset payload for {patch.file_path}."
                )
            selected_sha256 = str(selected_asset["source_sha256"]).lower()
            matching_variants = [
                variant for variant in patch.variants if variant.asset_sha256 == selected_sha256
            ]
            if not matching_variants:
                raise PatchError(
                    f"Post-asset patch #{patch.index} has no variant for selected asset SHA-256 "
                    f"{selected_sha256} ({patch.file_path})."
                )
            if len(matching_variants) != 1:
                raise PatchError(
                    f"Post-asset patch #{patch.index} has {len(matching_variants)} ambiguous variants for "
                    f"selected asset SHA-256 {selected_sha256} ({patch.file_path})."
                )
            variant = matching_variants[0]
            source_path = str(selected_asset["source_path"])
            source = resolve_under_manifest_dir(manifest_dir, source_path)
            if not source.is_file():
                raise PatchError(f"Selected asset source file does not exist: {source_path}")
            try:
                source_data = source.read_bytes()
            except OSError as exc:
                raise PatchError(f"Could not read selected asset source {source_path}: {exc}") from exc
            source_sha256 = hashlib.sha256(source_data).hexdigest()
            if source_sha256 != selected_sha256:
                raise PatchError(
                    f"Selected asset source SHA-256 changed for {source_path}: "
                    f"expected {selected_sha256}, got {source_sha256}"
                )
            end = variant.offset + len(variant.expected)
            if end > len(source_data):
                raise PatchError(
                    f"Post-asset patch #{patch.index} variant #{variant.index} runs past the end of "
                    f"selected asset {source_path}."
                )
            actual = source_data[variant.offset:end]
            if actual != variant.expected:
                raise PatchError(
                    f"Post-asset patch #{patch.index} expected asset bytes do not match {source_path} "
                    f"at 0x{variant.offset:x}: expected {variant.expected.hex(' ')}, got {actual.hex(' ')}"
                )
            for prior in checks:
                if canonical_rel_path_key(str(prior["file_path"])) != canonical_rel_path_key(patch.file_path):
                    continue
                prior_end = int(prior["offset"]) + len(prior["expected"])
                if variant.offset < prior_end and int(prior["offset"]) < end:
                    raise PatchError(
                        f"Post-asset patch #{patch.index} overlaps post-asset patch #{prior['index']} "
                        f"for {patch.file_path}."
                    )
        except PatchError as exc:
            log_process_event(
                process_log,
                phase="validate",
                kind="post_asset_patch",
                status="error",
                index=patch.index,
                file_path=patch.file_path,
                note=patch.note,
                error=str(exc),
            )
            report_record_progress(
                args,
                phase="Validating",
                kind="post-asset patch",
                current=current,
                total=total,
                file_path=patch.file_path,
                index=patch.index,
                status="error",
            )
            raise

        note = variant.note or patch.note
        check = {
            "index": patch.index,
            "variant_index": variant.index,
            "file_path": patch.file_path,
            "asset_patch_index": int(selected_asset["index"]),
            "source_path": source_path,
            "asset_sha256": selected_sha256,
            "offset": variant.offset,
            "expected": variant.expected,
            "replacement": variant.replacement,
            "requires": list(patch.requires),
            "note": note,
        }
        checks.append(check)
        log_process_event(
            process_log,
            phase="validate",
            kind="post_asset_patch",
            status="success",
            index=patch.index,
            file_path=patch.file_path,
            note=note,
            variant_index=variant.index,
            asset_patch_index=int(selected_asset["index"]),
            source_path=source_path,
            asset_sha256=selected_sha256,
            offset=f"0x{variant.offset:x}",
            expected=variant.expected.hex(),
            replacement=variant.replacement.hex(),
        )
        report_record_progress(
            args,
            phase="Validating",
            kind="post-asset patch",
            current=current,
            total=total,
            file_path=patch.file_path,
            index=patch.index,
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
        if check["action"] in {"remove", "remove_missing"}:
            target = resolve_under_game_dir(output_dir, output_file_path)
            if check["action"] == "remove_missing":
                log_process_event(
                    process_log,
                    phase="apply",
                    kind="asset_patch",
                    status="skipped",
                    index=index,
                    file_path=file_path,
                    note=str(check.get("note") or ""),
                    output_file_path=output_file_path,
                    action="remove_missing",
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
            try:
                if not target.is_file():
                    raise PatchError(f"Removal target disappeared before apply: {output_file_path}")
                actual_sha = sha256_file(target)
                if actual_sha != str(check["source_sha256"]):
                    raise PatchError(
                        f"Refusing removal of {output_file_path}: target SHA-256 changed "
                        f"from {check['source_sha256']} to {actual_sha}."
                    )
                target.unlink()
            except OSError as exc:
                raise PatchError(f"Could not remove disabled asset {output_file_path}: {exc}") from exc
            log_process_event(
                process_log,
                phase="apply",
                kind="asset_patch",
                status="success",
                index=index,
                file_path=file_path,
                note=str(check.get("note") or ""),
                output_file_path=output_file_path,
                action="remove",
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
            continue
        if check["action"] == "up_to_date":
            source = resolve_under_manifest_dir(manifest_dir, str(check["source_path"]))
            target = resolve_under_game_dir(output_dir, output_file_path)
            if target.is_file() and sha256_file(target) == str(check["source_sha256"]):
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
            check["action"] = "create" if not target.exists() else "replace"
            log_process_event(
                process_log,
                phase="apply",
                kind="asset_patch",
                status="info",
                index=index,
                file_path=file_path,
                note=str(check.get("note") or ""),
                source_path=str(check["source_path"]),
                output_file_path=output_file_path,
                action="up_to_date_recheck_failed",
            )
        source = resolve_under_manifest_dir(manifest_dir, str(check["source_path"]))
        target = resolve_under_game_dir(output_dir, output_file_path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + ".vf2patch.tmp")
            if temp.is_symlink():
                raise PatchError(f"Temporary patch path must not be a symlink: {temp}")
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


def report_post_asset_apply_error(
    checks: list[dict[str, Any]],
    message: str,
    args: argparse.Namespace,
    process_log: list[dict[str, Any]],
    *,
    completed: int,
    total: int,
) -> None:
    for relative_index, check in enumerate(checks, start=1):
        file_path = str(check["file_path"])
        index = int(check["index"])
        log_process_event(
            process_log,
            phase="apply",
            kind="post_asset_patch",
            status="error",
            index=index,
            file_path=file_path,
            note=str(check.get("note") or ""),
            variant_index=int(check["variant_index"]),
            asset_patch_index=int(check["asset_patch_index"]),
            asset_sha256=str(check["asset_sha256"]),
            offset=f"0x{int(check['offset']):x}",
            error=message,
        )
        report_record_progress(
            args,
            phase="Applying",
            kind="post-asset patch",
            current=min(completed + relative_index, total),
            total=total,
            file_path=file_path,
            index=index,
            status="error",
        )


def apply_post_asset_patches(
    output_dir: Path,
    post_asset_checks: list[dict[str, Any]],
    args: argparse.Namespace,
    process_log: list[dict[str, Any]],
) -> None:
    grouped: dict[str, dict[str, Any]] = {}
    for check in post_asset_checks:
        file_path = str(check["file_path"])
        key = canonical_rel_path_key(file_path)
        group = grouped.setdefault(key, {"display_path": file_path, "checks": []})
        group["checks"].append(check)

    total = len(post_asset_checks)
    current = 0
    for group in grouped.values():
        file_path = str(group["display_path"])
        checks = list(group["checks"])
        try:
            target = resolve_under_game_dir(output_dir, file_path)
        except PatchError as exc:
            report_post_asset_apply_error(checks, str(exc), args, process_log, completed=current, total=total)
            raise
        if not target.is_file():
            message = f"Post-asset patch target does not exist after asset copy: {file_path}"
            report_post_asset_apply_error(checks, message, args, process_log, completed=current, total=total)
            raise PatchError(message)
        selected_hashes = {str(check["asset_sha256"]) for check in checks}
        if len(selected_hashes) != 1:
            message = f"Post-asset patches selected conflicting asset payloads for {file_path}."
            report_post_asset_apply_error(checks, message, args, process_log, completed=current, total=total)
            raise PatchError(message)
        selected_sha256 = next(iter(selected_hashes))
        try:
            data = target.read_bytes()
        except OSError as exc:
            message = f"Could not read post-asset patch target {file_path}: {exc}"
            report_post_asset_apply_error(checks, message, args, process_log, completed=current, total=total)
            raise PatchError(message) from exc
        actual_sha256 = hashlib.sha256(data).hexdigest()
        if actual_sha256 != selected_sha256:
            message = (
                f"Post-asset patch target SHA-256 mismatch after asset copy for {file_path}: "
                f"expected selected asset {selected_sha256}, got {actual_sha256}"
            )
            report_post_asset_apply_error(checks, message, args, process_log, completed=current, total=total)
            raise PatchError(message)

        patched = bytearray(data)
        for check in checks:
            offset = int(check["offset"])
            expected = bytes(check["expected"])
            actual = bytes(patched[offset : offset + len(expected)])
            if actual != expected:
                message = (
                    f"Post-asset patch #{check['index']} expected bytes do not match {file_path} "
                    f"at 0x{offset:x}: expected {expected.hex(' ')}, got {actual.hex(' ')}"
                )
                report_post_asset_apply_error(checks, message, args, process_log, completed=current, total=total)
                raise PatchError(message)
            replacement = bytes(check["replacement"])
            patched[offset : offset + len(expected)] = replacement
        try:
            atomic_write(target, bytes(patched))
        except OSError as exc:
            message = f"Could not write post-asset patch target {file_path}: {exc}"
            report_post_asset_apply_error(checks, message, args, process_log, completed=current, total=total)
            raise PatchError(message) from exc

        for check in checks:
            current += 1
            offset = int(check["offset"])
            replacement = bytes(check["replacement"])
            log_process_event(
                process_log,
                phase="apply",
                kind="post_asset_patch",
                status="success",
                index=int(check["index"]),
                file_path=str(check["file_path"]),
                note=str(check.get("note") or ""),
                variant_index=int(check["variant_index"]),
                asset_patch_index=int(check["asset_patch_index"]),
                asset_sha256=selected_sha256,
                offset=f"0x{offset:x}",
                length=len(replacement),
            )
            report_record_progress(
                args,
                phase="Applying",
                kind="post-asset patch",
                current=current,
                total=total,
                file_path=str(check["file_path"]),
                index=int(check["index"]),
            )


def backup_slug(manifest_path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", manifest_path.stem).strip("._")
    if not stem:
        stem = "vf2_patch"
    return f"{_dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{stem}"


def create_backup(
    game_dir: Path,
    output_dir: Path,
    backup_dir: Path,
    grouped: dict[str, list[BytePatch]],
    asset_checks: list[dict[str, Any]],
    post_asset_checks: list[dict[str, Any]],
    manifest_path: Path,
) -> dict[str, Any]:
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_targets: dict[str, bool] = {rel_path: True for rel_path in grouped}
    output_backup_paths: set[str] = set()
    if output_dir.resolve() != game_dir.resolve() and output_dir.is_dir():
        for existing in output_dir.rglob("*"):
            if not existing.is_file():
                continue
            rel_path = str(existing.relative_to(output_dir)).replace("\\", "/")
            if rel_path == DEFAULT_BACKUP_ROOT or rel_path.startswith(DEFAULT_BACKUP_ROOT + "/"):
                continue
            backup_targets[rel_path] = True
            output_backup_paths.add(rel_path)
    for check in asset_checks:
        if check["action"] == "up_to_date":
            continue
        output_file_path = str(check.get("output_file_path") or check["file_path"])
        if output_file_path == str(check["file_path"]) and output_dir.resolve() != game_dir.resolve():
            backup_targets.setdefault(output_file_path, bool(check.get("output_existed", False)))
            output_backup_paths.add(output_file_path)
        elif output_file_path == str(check["file_path"]):
            backup_targets.setdefault(str(check["file_path"]), bool(check["target_existed"]))
        else:
            backup_targets.setdefault(output_file_path, bool(check.get("output_existed", False)))
    post_asset_display_paths: dict[str, str] = {}
    for check in post_asset_checks:
        file_path = str(check["file_path"])
        post_asset_display_paths.setdefault(canonical_rel_path_key(file_path), file_path)
    for file_path in post_asset_display_paths.values():
        target = resolve_under_game_dir(output_dir, file_path)
        backup_targets[file_path] = target.is_file()
        output_backup_paths.add(file_path)

    files = []
    for rel_path in sorted(backup_targets):
        source_root = output_dir if rel_path in output_backup_paths else game_dir
        source = resolve_under_game_dir(source_root, rel_path)
        existed = backup_targets[rel_path]
        row: dict[str, Any] = {"file_path": rel_path, "existed": existed}
        if existed:
            if not source.is_file():
                raise PatchError(f"Backup target file does not exist: {rel_path}")
            backup_rel = Path("files") / rel_path
            destination = resolve_under_backup_dir(backup_dir, str(backup_rel))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            backup_sha = sha256_file(destination)
            source_sha = sha256_file(source)
            if backup_sha != source_sha:
                raise PatchError(
                    f"Backup verification failed for {rel_path}: "
                    f"source {source_sha}, backup {backup_sha}"
                )
            row.update(
                {
                    "backup_path": str(backup_rel).replace("\\", "/"),
                    "sha256": source_sha,
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
    if temp.is_symlink():
        raise PatchError(f"Temporary patch path must not be a symlink: {temp}")
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
            "target_file_path": check.get("target_file_path", check["file_path"]),
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
            "remove_when_disabled": check.get("remove_when_disabled", False),
            "requires": check["requires"],
            "note": check["note"],
        }
        for check in asset_checks
    ]


def post_asset_patch_summary(post_asset_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": int(check["index"]),
            "variant_index": int(check["variant_index"]),
            "file_path": str(check["file_path"]),
            "asset_patch_index": int(check["asset_patch_index"]),
            "source_path": str(check["source_path"]),
            "asset_sha256": str(check["asset_sha256"]),
            "offset": f"0x{int(check['offset']):x}",
            "expected_asset_bytes": bytes(check["expected"]).hex(" "),
            "replacement_bytes": bytes(check["replacement"]).hex(" "),
            "requires": list(check["requires"]),
            "note": str(check.get("note") or ""),
        }
        for check in post_asset_checks
    ]


def apply_manifest(args: argparse.Namespace) -> int:
    exe_path = Path(args.exe).resolve() if getattr(args, "exe", None) else None
    requested_game_dir = Path(args.game_dir).resolve() if args.game_dir else None
    requested_output_dir = Path(args.output_dir).resolve() if getattr(args, "output_dir", None) else None
    game_dir = requested_game_dir
    reconfigure_output = False
    if exe_path is not None:
        if exe_path.suffix.lower() != ".exe":
            raise PatchError(f"--exe must point to a Virtual Families 2 executable, got {exe_path.name!r}.")
        if game_dir is not None and game_dir != exe_path.parent.resolve():
            raise PatchError("--game-dir and --exe disagree; use the EXE's parent folder or omit --game-dir.")
        if (
            game_dir is None
            and exe_path.name.lower() != DEFAULT_EXE_NAME.lower()
            and is_recognized_modded_output_dir(exe_path.parent.resolve())
        ):
            game_dir = exe_path.parent.resolve()
            reconfigure_output = True
        else:
            game_dir = exe_path.parent.resolve()
    if game_dir is None and requested_output_dir is not None:
        game_dir = requested_output_dir
        reconfigure_output = True
    if game_dir is None:
        raise PatchError("Either --game-dir, --exe, or --output-dir is required.")
    if reconfigure_output and requested_game_dir is not None:
        reconfigure_output = False
    setattr(args, "reconfigure_output", reconfigure_output)
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
        output_dir = game_dir if reconfigure_output else resolve_apply_output_dir(args, game_dir, manifest)
        settings, enabled_settings = resolve_enabled_settings(manifest, args)
        patches = manifest_patches(manifest, settings, enabled_settings)
        assets = manifest_asset_patches(manifest, settings, enabled_settings)
        post_asset_patches = manifest_post_asset_patches(manifest, settings, enabled_settings)
        restore_assets = manifest_asset_patches(manifest, settings, enabled_settings, restore_inactive=True) if reconfigure_output else []
        if reconfigure_output:
            assets = suppress_active_assets_replaced_by_restore(assets, restore_assets)
        all_assets = [
            *(asset for asset in [*assets, *restore_assets] if not asset.remove_when_disabled),
            *(asset for asset in [*assets, *restore_assets] if asset.remove_when_disabled),
        ]
        validate_asset_target_plan(all_assets)
        if reconfigure_output:
            verify_reconfigure_executable_identity(
                manifest,
                manifest_path.parent,
                output_dir,
                assets,
            )
        grouped = group_patches(patches)
        if reconfigure_output and grouped:
            raise PatchError("Output-only reconfiguration cannot apply byte patches without a vanilla game folder.")
        if not grouped and not all_assets and not post_asset_patches and output_dir.resolve() == game_dir.resolve():
            raise PatchError("No active patches remain enabled.")
        emit_progress(args, "Verifying target files...")
        if reconfigure_output:
            emit_progress(args, f"Reconfiguring existing modded output folder: {output_dir}")
            runtime_checks = verify_reconfigure_output_dir(output_dir, manifest)
            target_checks = []
            file_data = {}
        else:
            runtime_checks = verify_runtime_requirements(game_dir, manifest, settings, enabled_settings)
            target_checks = verify_target_files(game_dir, manifest, settings, enabled_settings)
            file_data = verify_patch_bytes(game_dir, grouped, args, process_log)
        asset_checks = verify_asset_patches(game_dir, output_dir, manifest_path.parent, all_assets, args, process_log)
        post_asset_checks = verify_post_asset_patches(
            manifest_path.parent,
            post_asset_patches,
            asset_checks,
            args,
            process_log,
        )
        preserve_stock_exe_icon = manifest_preserve_stock_exe_icon(manifest)
        captured_icon_resources: tuple[IconResource, ...] = ()
        icon_source: Path | None = None
        if preserve_stock_exe_icon:
            desired_exe_name = manifest_output_exe_name(manifest)
            if not desired_exe_name:
                raise PatchError(
                    "Manifest output preserve_stock_exe_icon requires a default_exe_name."
                )
            icon_asset_check = next(
                (
                    check
                    for check in asset_checks
                    if Path(str(check.get("output_file_path") or check["file_path"])).name.lower()
                    == desired_exe_name.lower()
                    and Path(str(check["file_path"])).suffix.lower() == ".exe"
                ),
                None,
            )
            if icon_asset_check is None:
                raise PatchError(
                    "Manifest requests stock EXE icon preservation, but no active executable replacement "
                    f"writes {desired_exe_name}."
                )
            icon_source = resolve_under_game_dir(game_dir, str(icon_asset_check["target_file_path"]))
            emit_progress(args, f"Validating stock executable icon resources: {icon_source}")
            try:
                captured_icon_resources = read_executable_icon_resources(icon_source)
            except PatchError as exc:
                log_process_event(
                    process_log,
                    phase="validate",
                    kind="exe_icon_resources",
                    status="error",
                    source_path=str(icon_source),
                    output_file_path=desired_exe_name,
                    error=str(exc),
                )
                raise
            log_process_event(
                process_log,
                phase="validate",
                kind="exe_icon_resources",
                status="success",
                source_path=str(icon_source),
                output_file_path=desired_exe_name,
                icon_count=sum(
                    resource.resource_type == RT_ICON for resource in captured_icon_resources
                ),
                group_icon_count=sum(
                    resource.resource_type == RT_GROUP_ICON for resource in captured_icon_resources
                ),
            )

        if not args.dry_run:
            skip_copy_paths = {
                str(check.get("target_file_path") or check["file_path"])
                for check in asset_checks
                if str(check.get("output_file_path") or check["file_path"]) != str(check["file_path"])
            }
            if args.backup_dir:
                backup_dir = Path(args.backup_dir).resolve()
            else:
                backup_dir = output_dir / DEFAULT_BACKUP_ROOT / backup_slug(manifest_path)
            emit_progress(args, f"Creating backup: {backup_dir}")
            backup_manifest = create_backup(
                game_dir,
                output_dir,
                backup_dir,
                grouped,
                asset_checks,
                post_asset_checks,
                manifest_path,
            )
            if not reconfigure_output:
                prepare_output_dir(game_dir, output_dir, skip_copy_paths, args)
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
            apply_post_asset_patches(output_dir, post_asset_checks, args, process_log)
            enforced_exe_name = enforce_modded_exe_name(game_dir, output_dir, manifest, process_log)
            if preserve_stock_exe_icon:
                if not enforced_exe_name:
                    raise PatchError("Could not resolve the generated modded EXE name for icon preservation.")
                icon_target = resolve_under_game_dir(output_dir, enforced_exe_name)
                emit_progress(args, f"Preserving stock executable icon resources: {icon_target}")
                try:
                    write_executable_icon_resources_atomic(icon_target, captured_icon_resources)
                except PatchError as exc:
                    log_process_event(
                        process_log,
                        phase="apply",
                        kind="exe_icon_resources",
                        status="error",
                        source_path=str(icon_source) if icon_source else None,
                        output_file_path=enforced_exe_name,
                        error=str(exc),
                    )
                    raise
                log_process_event(
                    process_log,
                    phase="apply",
                    kind="exe_icon_resources",
                    status="success",
                    source_path=str(icon_source) if icon_source else None,
                    output_file_path=enforced_exe_name,
                    icon_count=sum(
                        resource.resource_type == RT_ICON for resource in captured_icon_resources
                    ),
                    group_icon_count=sum(
                        resource.resource_type == RT_GROUP_ICON for resource in captured_icon_resources
                    ),
                )
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
        save_folder_name = manifest_output_save_folder_name(manifest, modded_exe_name)
        save_dir = Path.home() / "Documents" / "LDW" / save_folder_name
        log = {
            "action": "apply",
            "dry_run": bool(args.dry_run),
            "status": "success",
            "timestamp_utc": utc_now(),
            "mode": "existing_modded_output" if reconfigure_output else "vanilla_to_modded_output",
            "game_dir": str(game_dir),
            "output_dir": str(output_dir),
            "modded_exe_name": modded_exe_name,
            "modded_save_folder_name": save_folder_name,
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
            "post_asset_patches": post_asset_patch_summary(post_asset_checks),
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
                "mode": "existing_modded_output" if reconfigure_output else "vanilla_to_modded_output",
                "modded_exe_name": modded_exe_name,
                "modded_save_folder_name": save_folder_name,
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
            f"and {len(all_assets)} active/restore asset patch record(s)."
        )
        print(f"Validated {len(assets)} active asset patch record(s).")
        print(f"Validated {len(post_asset_patches)} active post-asset patch record(s).")
        if restore_assets:
            print(f"Validated {len(restore_assets)} restore asset patch record(s).")
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

    rows = backup_manifest.get("files", [])
    if not isinstance(rows, list):
        raise PatchError("Backup manifest files must be an array.")

    validated_rows = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise PatchError("Backup manifest contains an invalid file row.")
        rel_path = normalize_rel_path(raw.get("file_path"), "backup file path")
        target = resolve_under_game_dir(game_dir, rel_path)
        if raw.get("existed", True):
            backup_rel = normalize_rel_path(raw.get("backup_path"), "backup path")
            source = resolve_under_backup_dir(backup_dir, backup_rel)
            if not source.is_file():
                raise PatchError(f"Backed-up file is missing: {source}")
            data = source.read_bytes()
            actual_sha = hashlib.sha256(data).hexdigest()
            expected_sha = normalize_sha256(
                raw.get("sha256"),
                f"backup file {rel_path} sha256",
                required=True,
            )
            if actual_sha != expected_sha:
                raise PatchError(
                    f"Backup SHA-256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}"
                )
            expected_size = raw.get("size")
            if expected_size is not None and len(data) != parse_int(expected_size, f"backup file {rel_path} size"):
                raise PatchError(
                    f"Backup size mismatch for {rel_path}: expected {expected_size}, got {len(data)}"
                )
            validated_rows.append((rel_path, target, True, data))
        else:
            if target.exists():
                if not target.is_file():
                    raise PatchError(f"Restore target is not a regular file: {rel_path}")
            validated_rows.append((rel_path, target, False, None))

    restored = []
    for rel_path, target, existed, data in validated_rows:
        if existed:
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(target, data)
            restored.append({"file_path": rel_path, "sha256": sha256_file(target), "size": target.stat().st_size})
        else:
            removed = False
            if target.exists():
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
    apply_cmd.add_argument("--game-dir", help="Path to the user-provided vanilla VF2 game directory. Omit only when reconfiguring an existing modded --output-dir.")
    apply_cmd.add_argument("--exe", help=f"Path to {DEFAULT_EXE_NAME}; the game directory is inferred from its parent.")
    apply_cmd.add_argument("--manifest", required=True, help="Path to the JSON patch manifest.")
    apply_cmd.add_argument("--output-dir", help="Optional modded game output folder. Defaults to the manifest output folder when a vanilla game folder is supplied. If --game-dir is omitted, this must be an existing modded folder to reconfigure.")
    apply_cmd.add_argument("--output-parent-dir", help="Optional parent folder for the manifest-named modded output folder. Ignored when --output-dir is supplied.")
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
