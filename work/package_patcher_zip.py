from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_manifest(source_dir: Path) -> dict:
    manifest_path = source_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Patcher bundle manifest is missing: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Patcher bundle manifest must be a JSON object.")
    return data


def normalized_relative(path: str) -> str:
    value = str(path).replace("\\", "/").strip("/")
    if not value or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError(f"Invalid manifest-relative path: {path!r}")
    return value


def require_pe32_x86(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError(f"Executable payload is not a valid PE file: {path}")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
        raise ValueError(f"Executable payload is not a valid PE file: {path}")
    coff_offset = pe_offset + 4
    machine, section_count, _timestamp, _symptr, _nsyms, optional_size, _characteristics = struct.unpack_from(
        "<HHIIIHH", data, coff_offset
    )
    optional_offset = coff_offset + 20
    if optional_size < 2 or optional_offset + optional_size > len(data):
        raise ValueError(f"Executable payload has a truncated PE optional header: {path}")
    optional_magic = struct.unpack_from("<H", data, optional_offset)[0]
    if machine != 0x14C or optional_magic != 0x10B:
        raise ValueError(f"Executable payload is not PE32 x86: {path}")
    if section_count == 0:
        raise ValueError(f"Executable payload has no PE sections: {path}")
    section_table = optional_offset + optional_size
    section_table_size = section_count * 40
    if section_table + section_table_size > len(data):
        raise ValueError(f"Executable payload has a truncated PE section table: {path}")
    for index in range(section_count):
        section_offset = section_table + index * 40
        raw_size, raw_pointer = struct.unpack_from("<II", data, section_offset + 16)
        if raw_pointer > len(data) or raw_size > len(data) - raw_pointer:
            raise ValueError(f"Executable payload has an out-of-bounds PE section: {path}")


def validate_executable_inventory(source_dir: Path, files: list[Path]) -> None:
    manifest = load_manifest(source_dir)
    exe_paths: dict[str, tuple[str, Path]] = {}
    for path in files:
        if path.suffix.lower() != ".exe":
            continue
        relative = path.relative_to(source_dir).as_posix()
        key = relative.casefold()
        if key in exe_paths:
            raise ValueError(
                f"Case-insensitive duplicate executable paths: {exe_paths[key][0]!r} and {relative!r}"
            )
        exe_paths[key] = (relative, path)

    asset_records: dict[str, list[dict]] = {}
    for row in manifest.get("asset_patches", []):
        if not isinstance(row, dict) or not str(row.get("source_path", "")).lower().endswith(".exe"):
            continue
        source_path = normalized_relative(row["source_path"])
        asset_records.setdefault(source_path.casefold(), []).append(row)

    target_records = {
        normalized_relative(row["path"]).casefold(): row
        for row in manifest.get("target_files", [])
        if isinstance(row, dict) and row.get("path")
    }
    default_exe_name = str(manifest.get("output", {}).get("default_exe_name", ""))
    launcher = manifest.get("export_summary", {}).get("launcher", {})
    runner_files = {
        normalized_relative(path).casefold()
        for path in manifest.get("export_summary", {}).get("runner_files", [])
    }
    launcher_output = normalized_relative(launcher.get("output", "")) if launcher.get("output") else ""
    launcher_key = launcher_output.casefold()
    if launcher_key and launcher_key in asset_records:
        raise ValueError(f"Launcher executable cannot also be an asset payload: {launcher_output}")
    if launcher_output and Path(launcher_output).parent != Path("."):
        raise ValueError(f"Patcher launcher executable must be at bundle root: {launcher_output}")

    for key, (relative, path) in exe_paths.items():
        require_pe32_x86(path)
        if relative.casefold().startswith("payload/"):
            rows = asset_records.get(key, [])
            if len(rows) != 1:
                raise ValueError(f"Payload executable must have exactly one manifest asset record: {relative}")
            row = rows[0]
            file_path = normalized_relative(row.get("file_path", ""))
            output_file_path = normalized_relative(row.get("output_file_path", ""))
            if not file_path.lower().endswith(".exe") or not output_file_path.lower().endswith(".exe"):
                raise ValueError(f"Executable asset record has non-executable target paths: {relative}")
            if output_file_path != default_exe_name:
                raise ValueError(f"Executable asset output does not match output.default_exe_name: {relative}")
            if "core_executable" not in row.get("requires", []):
                raise ValueError(f"Executable asset is not gated by core_executable: {relative}")
            actual_sha = sha256_file(path).lower()
            actual_size = path.stat().st_size
            if str(row.get("source_sha256", "")).lower() != actual_sha or row.get("source_size") != actual_size:
                raise ValueError(f"Executable asset source hash/size mismatch: {relative}")
            expected_sha = str(row.get("expected_target_sha256", "")).lower()
            expected_size = row.get("expected_target_size")
            if len(expected_sha) != 64 or expected_size is None:
                raise ValueError(f"Executable asset lacks exact target identity: {relative}")
            target = target_records.get(file_path.casefold())
            if not target:
                raise ValueError(f"Executable asset has no matching target_files record: {relative}")
            if str(target.get("sha256", "")).lower() != expected_sha or target.get("size") != expected_size:
                raise ValueError(f"Executable asset target identity disagrees with target_files: {relative}")
            continue

        if (
            launcher.get("status") != "built"
            or key != launcher_output.casefold()
            or key not in runner_files
            or str(launcher.get("sha256", "")).lower() != sha256_file(path).lower()
            or launcher.get("size") != path.stat().st_size
        ):
            raise ValueError(f"Root executable is not an attested patcher launcher: {relative}")

    missing_payloads = sorted(key for key in asset_records if key not in exe_paths)
    if missing_payloads:
        raise ValueError(f"Manifest references missing executable payload: {missing_payloads[0]}")


def package(source_dir: Path, archive: Path, compresslevel: int = 9) -> int:
    source_dir = source_dir.resolve()
    archive = archive.resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(source_dir)
    archive.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    validate_executable_inventory(source_dir, files)
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=compresslevel,
        allowZip64=True,
    ) as output:
        for path in files:
            relative = path.relative_to(source_dir).as_posix()
            output.write(path, f"{source_dir.name}/{relative}")
    return len(files)


def main():
    parser = argparse.ArgumentParser(
        description="Create a compact patcher ZIP with portable forward-slash file entries."
    )
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--compresslevel", type=int, default=9, choices=range(0, 10))
    args = parser.parse_args()
    count = package(args.source_dir, args.archive, args.compresslevel)
    print(f"files={count}")
    print(f"bytes={args.archive.stat().st_size}")
    print(f"sha256={sha256_file(args.archive)}")


if __name__ == "__main__":
    main()
