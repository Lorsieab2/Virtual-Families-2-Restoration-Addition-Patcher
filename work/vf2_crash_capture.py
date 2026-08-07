from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "vf2-crash-capture/v1"
WER_STATE_SCHEMA = "vf2-wer-localdumps-state/v1"
BUNDLE_REPORT_SCHEMA = "vf2-crash-bundle-report/v1"
IDA_SCHEMA = "vf2-crash-capture-ida/v1"
HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")
REGISTER_NAMES = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp", "eip", "eflags")
MAX_UINT32 = 0xFFFFFFFF
MINIDUMP_HEADER_SIZE = 32
MINIDUMP_DIRECTORY_SIZE = 12
MINIDUMP_VERSION_LOW_WORD = 0xA793


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def parse_number(value: Any, label: str, *, allow_zero: bool = False) -> int:
    try:
        number = int(value, 0) if isinstance(value, str) else value
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if isinstance(number, bool) or not isinstance(number, int) or (number < 0 if allow_zero else number <= 0):
        requirement = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{label} must be {requirement}")
    return number


def parse_uint32(value: Any, label: str, *, allow_zero: bool = False) -> int:
    number = parse_number(value, label, allow_zero=allow_zero)
    if number > MAX_UINT32:
        raise ValueError(f"{label} must fit in unsigned 32-bit range")
    return number


def canonical_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise ValueError(f"{label} must be a 64-character SHA-256 hex string")
    return value.lower()


def canonical_path(path: Path) -> str:
    return os.path.normcase(str(path.expanduser().resolve(strict=False)))


def absolute_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute: {value}")
    return path


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return data


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = load_json(path, "Crash-capture manifest")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"Crash-capture manifest schema must be {MANIFEST_SCHEMA!r}")
    executable = manifest.get("executable")
    if not isinstance(executable, dict):
        raise ValueError("Crash-capture manifest must contain an executable object")
    return manifest


def file_identity(path: Path, label: str) -> dict[str, Any]:
    try:
        if not path.is_file():
            raise ValueError(f"{label} is missing or is not a regular file: {path}")
        size = path.stat().st_size
        if size <= 0:
            raise ValueError(f"{label} is zero-byte: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"{label} cannot be read: {path}") from exc
    return {"path": str(path.resolve()), "size": size, "sha256": digest.hexdigest()}


def verify_executable(manifest_path: Path, selected_exe: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    expected = manifest["executable"]
    expected_path = absolute_path(expected.get("path"), "executable.path")
    expected_size = _positive_int(expected.get("size"), "executable.size")
    expected_hash = canonical_hash(expected.get("sha256"), "executable.sha256")
    selected_path = selected_exe.expanduser()
    if not selected_path.is_absolute():
        raise ValueError(f"Selected executable path must be absolute: {selected_exe}")
    if canonical_path(selected_path) != canonical_path(expected_path):
        raise ValueError(
            f"Selected executable path disagrees with manifest: {selected_path} != {expected_path}"
        )
    actual = file_identity(selected_path, "Selected executable")
    if actual["size"] != expected_size:
        raise ValueError(
            f"Selected executable size mismatch: {actual['size']} != {expected_size}"
        )
    if actual["sha256"] != expected_hash:
        raise ValueError("Selected executable SHA-256 mismatch")
    return actual


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if not path.parent.is_dir():
        raise ValueError(f"Output parent directory is missing: {path.parent}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _relative_artifact(root: Path, value: Any, label: str) -> tuple[str, Path]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.path is required")
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError(f"{label}.path must be a safe relative bundle path")
    resolved_root = root.resolve()
    candidate = (resolved_root / Path(*parts)).resolve(strict=False)
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{label}.path escapes the bundle directory") from exc
    return "/".join(parts), candidate


def _verify_artifact(root: Path, record: Any, label: str, *, require_dump_magic: bool = False) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be an object")
    relative, path = _relative_artifact(root, record.get("path"), label)
    expected_size = _positive_int(record.get("size"), f"{label}.size")
    expected_hash = canonical_hash(record.get("sha256"), f"{label}.sha256")
    actual = file_identity(path, label)
    if actual["size"] != expected_size:
        raise ValueError(f"{label} size mismatch: {actual['size']} != {expected_size}")
    if actual["sha256"] != expected_hash:
        raise ValueError(f"{label} SHA-256 mismatch")
    if require_dump_magic:
        _validate_minidump(path, label)
    return {"path": str(path), "relative_path": relative, "size": actual["size"], "sha256": actual["sha256"]}


def _validate_minidump(path: Path, label: str) -> None:
    try:
        file_size = path.stat().st_size
    except OSError as exc:
        raise ValueError(f"{label} cannot be read: {path}") from exc
    if file_size < MINIDUMP_HEADER_SIZE:
        raise ValueError(f"{label} has a truncated MINIDUMP_HEADER: {path}")
    try:
        with path.open("rb") as stream:
            header = stream.read(MINIDUMP_HEADER_SIZE)
            if len(header) != MINIDUMP_HEADER_SIZE:
                raise ValueError(f"{label} has a truncated MINIDUMP_HEADER: {path}")
            signature, version, stream_count, directory_rva, _checksum, _timestamp, _flags = struct.unpack(
                "<4sIIIIIQ", header
            )
            if signature != b"MDMP" or (version & 0xFFFF) != MINIDUMP_VERSION_LOW_WORD:
                raise ValueError(f"{label} has an invalid MINIDUMP_HEADER: {path}")
            if stream_count <= 0 or directory_rva < MINIDUMP_HEADER_SIZE or directory_rva > file_size:
                raise ValueError(f"{label} has an invalid minidump stream directory: {path}")
            if stream_count > (file_size - directory_rva) // MINIDUMP_DIRECTORY_SIZE:
                raise ValueError(f"{label} has a truncated minidump stream directory: {path}")
            directory_size = stream_count * MINIDUMP_DIRECTORY_SIZE
            stream.seek(directory_rva)
            directory = stream.read(directory_size)
            if len(directory) != directory_size:
                raise ValueError(f"{label} has a truncated minidump stream directory: {path}")
            for offset in range(0, directory_size, MINIDUMP_DIRECTORY_SIZE):
                _stream_type, data_size, data_rva = struct.unpack_from("<III", directory, offset)
                if data_rva > file_size or data_size > file_size - data_rva:
                    raise ValueError(f"{label} has an out-of-bounds minidump stream: {path}")
                if data_size and data_rva < MINIDUMP_HEADER_SIZE:
                    raise ValueError(f"{label} has a stream overlapping its header: {path}")
    except OSError as exc:
        raise ValueError(f"{label} cannot be read: {path}") from exc


def validate_bundle(manifest_path: Path, selected_exe: Path, bundle_dir: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    exact_build = verify_executable(manifest_path, selected_exe)
    root = bundle_dir.expanduser()
    if not root.is_dir():
        raise ValueError(f"Capture bundle directory is missing: {bundle_dir}")
    capture = manifest.get("capture")
    if not isinstance(capture, dict):
        raise ValueError("Crash-capture manifest must contain a capture object for bundle validation")
    dump = _verify_artifact(root, capture.get("dump"), "capture.dump", require_dump_magic=True)
    logs = capture.get("logs")
    if not isinstance(logs, list) or not logs:
        raise ValueError("capture.logs must contain at least one log artifact")
    verified_logs = []
    seen: set[str] = {dump["relative_path"].casefold()}
    for index, record in enumerate(logs):
        verified = _verify_artifact(root, record, f"capture.logs[{index}]")
        key = verified["relative_path"].casefold()
        if key in seen:
            raise ValueError(f"Duplicate capture artifact path: {verified['relative_path']}")
        seen.add(key)
        verified_logs.append(verified)
    return {
        "schema": BUNDLE_REPORT_SCHEMA,
        "status": "validated",
        "exact_build": exact_build,
        "capture": {"dump": dump, "logs": verified_logs},
    }


def emit_wer_plan(
    manifest_path: Path,
    selected_exe: Path,
    dump_dir: Path,
    state_out: Path,
    instructions_out: Path,
    *,
    restore_out: Path | None = None,
    dump_count: int = 3,
    dump_type: int = 2,
) -> dict[str, Any]:
    executable = verify_executable(manifest_path, selected_exe)
    dump_root = absolute_path(str(dump_dir), "dump directory")
    if dump_root.exists() and not dump_root.is_dir():
        raise ValueError(f"Dump directory is not a directory: {dump_root}")
    if dump_count <= 0:
        raise ValueError("dump_count must be positive")
    if dump_type not in (1, 2):
        raise ValueError("dump_type must be 1 (mini) or 2 (full)")
    exe_name = Path(executable["path"]).name
    registry_subkey = f"Software\\Microsoft\\Windows\\Windows Error Reporting\\LocalDumps\\{exe_name}"
    registry_key = f"HKCU\\{registry_subkey}"
    provider_key = f"HKCU:\\{registry_subkey}"
    backup_file = state_out.with_name(state_out.stem + ".preexisting.reg").resolve()
    if restore_out is None:
        restore_out = instructions_out.with_name(
            instructions_out.stem + ".restore" + instructions_out.suffix
        )
    if backup_file.exists():
        raise ValueError(f"Refusing to overwrite an existing WER backup: {backup_file}")
    state = {
        "schema": WER_STATE_SCHEMA,
        "registry_modified": False,
        "instructions_only": True,
        "executable": executable,
        "registry_key": registry_key,
        "values": {"DumpFolder": str(dump_root), "DumpType": dump_type, "DumpCount": dump_count},
        "preexisting_state": {"must_be_exported_before_setup": True, "backup_file": str(backup_file)},
        "instructions": {
            "setup": str(instructions_out.resolve()),
            "restore": str(restore_out.resolve()),
        },
        "restore": {"scope": registry_key, "never_delete_parent_localdumps_key": True},
    }
    if not state_out.parent.is_dir():
        raise ValueError(f"Output parent directory is missing: {state_out.parent}")
    if not instructions_out.parent.is_dir():
        raise ValueError(f"Output parent directory is missing: {instructions_out.parent}")
    if not restore_out.parent.is_dir():
        raise ValueError(f"Restore output parent directory is missing: {restore_out.parent}")
    output_paths = {canonical_path(state_out), canonical_path(instructions_out), canonical_path(restore_out)}
    if len(output_paths) != 3:
        raise ValueError("WER state, setup, and restore outputs must be different files")
    _write_json(state_out, state)
    escaped_dump = str(dump_root).replace("'", "''")
    escaped_provider = provider_key.replace("'", "''")
    escaped_registry = registry_key.replace("'", "''")
    escaped_backup = str(backup_file).replace("'", "''")
    setup_instructions = f"""# WER LocalDumps setup instructions for {exe_name}
# Generated state is instructions only; this tool did not read or modify the registry.
# Review the exact executable hash in the adjacent state JSON before running.
# Run this setup once, reproduce the crash, then run the separate restore script.
$ErrorActionPreference = 'Stop'
$providerKey = '{escaped_provider}'
$registryKey = '{escaped_registry}'
$backupFile = '{escaped_backup}'

# Setup: refuse any stale backup before inspecting or changing the key.
if (Test-Path -LiteralPath $backupFile) {{ throw "Refusing to overwrite an existing WER backup: $backupFile" }}
if (Test-Path -LiteralPath $providerKey) {{
    reg.exe export $registryKey $backupFile /y | Out-Null
    if ($LASTEXITCODE -ne 0) {{ throw "WER registry export failed; no setup was applied" }}
}}
New-Item -Path $providerKey -Force | Out-Null
New-ItemProperty -Path $providerKey -Name DumpFolder -PropertyType ExpandString -Value '{escaped_dump}' -Force | Out-Null
New-ItemProperty -Path $providerKey -Name DumpType -PropertyType DWord -Value {dump_type} -Force | Out-Null
New-ItemProperty -Path $providerKey -Name DumpCount -PropertyType DWord -Value {dump_count} -Force | Out-Null
"""
    restore_instructions = f"""# WER LocalDumps restore instructions for {exe_name}
# Run only after the crash dump/log collection is complete.
$ErrorActionPreference = 'Stop'
$providerKey = '{escaped_provider}'
$backupFile = '{escaped_backup}'

# Restore the exact saved per-executable key, or remove only this leaf key when
# it did not exist before setup. Never remove the LocalDumps parent.
if (Test-Path -LiteralPath $backupFile) {{
    if (Test-Path -LiteralPath $providerKey) {{
        Remove-Item -LiteralPath $providerKey -Recurse -Force
    }}
    reg.exe import $backupFile | Out-Null
    if ($LASTEXITCODE -ne 0) {{ throw "WER registry restore import failed" }}
}} elseif (Test-Path -LiteralPath $providerKey) {{
    Remove-Item -LiteralPath $providerKey -Recurse -Force
}}
"""
    instructions_out.write_text(setup_instructions, encoding="utf-8")
    restore_out.write_text(restore_instructions, encoding="utf-8")
    return state


def _load_bundle_report(path: Path) -> dict[str, Any]:
    report = load_json(path, "Bundle report")
    if report.get("schema") != BUNDLE_REPORT_SCHEMA or report.get("status") != "validated":
        raise ValueError("Bundle report is not a validated crash-capture report")
    exact_build = report.get("exact_build")
    if not isinstance(exact_build, dict):
        raise ValueError("Bundle report is missing exact_build")
    exe_path = absolute_path(exact_build.get("path"), "Bundle report exact_build.path")
    expected_exe = {
        "path": str(exe_path),
        "size": _positive_int(exact_build.get("size"), "Bundle report exact_build.size"),
        "sha256": canonical_hash(exact_build.get("sha256"), "Bundle report exact_build.sha256"),
    }
    actual_exe = file_identity(exe_path, "Bundle report executable")
    if actual_exe["size"] != expected_exe["size"] or actual_exe["sha256"] != expected_exe["sha256"]:
        raise ValueError("Bundle report executable no longer matches its recorded identity")
    capture = report.get("capture")
    if not isinstance(capture, dict):
        raise ValueError("Bundle report is missing capture")
    dump_record = capture.get("dump")
    if not isinstance(dump_record, dict):
        raise ValueError("Bundle report is missing capture.dump")
    dump_path = absolute_path(dump_record.get("path"), "Bundle report capture.dump.path")
    dump = {
        "path": str(dump_path),
        "size": _positive_int(dump_record.get("size"), "Bundle report capture.dump.size"),
        "sha256": canonical_hash(dump_record.get("sha256"), "Bundle report capture.dump.sha256"),
    }
    actual_dump = file_identity(dump_path, "Bundle report dump")
    if actual_dump["size"] != dump["size"] or actual_dump["sha256"] != dump["sha256"]:
        raise ValueError("Bundle report dump no longer matches its recorded identity")
    _validate_minidump(dump_path, "Bundle report dump")
    logs = capture.get("logs")
    if not isinstance(logs, list) or not logs:
        raise ValueError("Bundle report must contain at least one log")
    verified_logs = []
    for index, record in enumerate(logs):
        if not isinstance(record, dict):
            raise ValueError(f"Bundle report capture.logs[{index}] must be an object")
        log_path = absolute_path(record.get("path"), f"Bundle report capture.logs[{index}].path")
        log = {
            "path": str(log_path),
            "size": _positive_int(record.get("size"), f"Bundle report capture.logs[{index}].size"),
            "sha256": canonical_hash(record.get("sha256"), f"Bundle report capture.logs[{index}].sha256"),
        }
        actual_log = file_identity(log_path, f"Bundle report log {index}")
        if actual_log["size"] != log["size"] or actual_log["sha256"] != log["sha256"]:
            raise ValueError(f"Bundle report log {index} no longer matches its recorded identity")
        verified_logs.append(log)
    return {"exact_build": expected_exe, "capture": {"dump": dump, "logs": verified_logs}}


def _bundle_identity(report: dict[str, Any]) -> dict[str, Any]:
    exact_build = report["exact_build"]
    capture = report["capture"]
    return {
        "exact_build": {
            "path": exact_build["path"],
            "size": exact_build["size"],
            "sha256": exact_build["sha256"],
        },
        "capture": {
            "dump": {
                "path": capture["dump"]["path"],
                "size": capture["dump"]["size"],
                "sha256": capture["dump"]["sha256"],
            },
            "logs": [
                {"path": log["path"], "size": log["size"], "sha256": log["sha256"]}
                for log in capture["logs"]
            ],
        },
    }


def parse_registers(values: list[str]) -> dict[str, str]:
    if not values:
        raise ValueError("At least one --register is required")
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("Registers must use NAME=VALUE")
        name, raw = value.split("=", 1)
        name = name.strip().lower()
        if name not in REGISTER_NAMES or name in parsed:
            raise ValueError(f"Register must be one unique x86 register: {name}")
        parsed[name] = f"0x{parse_uint32(raw.strip(), f'register {name}', allow_zero=True):X}"
    missing = [name for name in REGISTER_NAMES if name not in parsed]
    if missing:
        raise ValueError(f"Missing required registers: {', '.join(missing)}")
    return {name: parsed[name] for name in REGISTER_NAMES}


def parse_stack_frames(values: list[str]) -> list[dict[str, Any]]:
    if not values:
        raise ValueError("At least one --stack-frame is required")
    frames = []
    for raw in values:
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Each --stack-frame must be a JSON object") from exc
        if not isinstance(frame, dict):
            raise ValueError("Each --stack-frame must be a JSON object")
        module = frame.get("module")
        if not isinstance(module, str) or not module.strip():
            raise ValueError("Each stack frame requires a module")
        index = parse_number(frame.get("index"), "stack frame index", allow_zero=True)
        address = parse_uint32(frame.get("address"), "stack frame address")
        base = parse_uint32(frame.get("module_base"), "stack frame module_base")
        rva = parse_uint32(frame.get("rva"), "stack frame rva", allow_zero=True)
        if base > MAX_UINT32 - rva:
            raise ValueError("Stack frame module_base + rva exceeds unsigned 32-bit range")
        if address != base + rva:
            raise ValueError("Stack frame address must equal module_base + rva")
        frames.append({"index": index, "address": f"0x{address:X}", "module": module, "module_base": f"0x{base:X}", "rva": f"0x{rva:X}"})
    frames.sort(key=lambda frame: frame["index"])
    if [frame["index"] for frame in frames] != list(range(len(frames))):
        raise ValueError("Stack frame indices must be unique and contiguous from zero")
    return frames


def emit_ida_json(
    manifest_path: Path,
    selected_exe: Path,
    bundle_dir: Path,
    bundle_report_path: Path,
    output_path: Path,
    *,
    exception_code: Any,
    exception_address: Any,
    module: str,
    module_base: Any,
    module_rva: Any,
    registers: list[str],
    stack_frames: list[str],
) -> dict[str, Any]:
    stored = _load_bundle_report(bundle_report_path)
    fresh = validate_bundle(manifest_path, selected_exe, bundle_dir)
    if _bundle_identity(stored) != _bundle_identity(fresh):
        raise ValueError("Bundle report does not match explicit manifest and freshly verified bundle")
    trusted = fresh
    if not isinstance(module, str) or not module.strip():
        raise ValueError("module is required")
    code = parse_uint32(exception_code, "exception code")
    address = parse_uint32(exception_address, "exception address")
    base = parse_uint32(module_base, "module base")
    rva = parse_uint32(module_rva, "module RVA", allow_zero=True)
    if base > MAX_UINT32 - rva:
        raise ValueError("Module base + module RVA exceeds unsigned 32-bit range")
    if address != base + rva:
        raise ValueError("Exception address must equal module base + module RVA")
    parsed_registers = parse_registers(registers)
    if parse_number(parsed_registers["eip"], "register eip") != address:
        raise ValueError("register eip must equal exception address")
    parsed_frames = parse_stack_frames(stack_frames)
    record = {
        "schema": IDA_SCHEMA,
        "exact_build": trusted["exact_build"],
        "capture": trusted["capture"],
        "exception": {"code": f"0x{code:X}", "address": f"0x{address:X}"},
        "fault_module": {"name": module, "base": f"0x{base:X}", "rva": f"0x{rva:X}", "address": f"0x{address:X}"},
        "registers": parsed_registers,
        "stack_frames": parsed_frames,
        "required_fields": [
            "exception.code",
            "exception.address",
            "fault_module.name",
            "fault_module.base",
            "fault_module.rva",
            "registers",
            "stack_frames",
            "exact_build.sha256",
            "capture.dump.sha256",
        ],
    }
    _write_json(output_path, record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed VF2 crash-capture readiness tooling.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-exe", help="verify one selected EXE against an exact-build manifest")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--exe", type=Path, required=True)

    wer = subparsers.add_parser("emit-wer-plan", help="write separate WER LocalDumps setup and restore instructions only")
    wer.add_argument("--manifest", type=Path, required=True)
    wer.add_argument("--exe", type=Path, required=True)
    wer.add_argument("--dump-dir", type=Path, required=True)
    wer.add_argument("--state-out", type=Path, required=True)
    wer.add_argument("--instructions-out", type=Path, required=True)
    wer.add_argument("--restore-out", type=Path)
    wer.add_argument("--dump-count", type=int, default=3)
    wer.add_argument("--dump-type", type=int, choices=(1, 2), default=2)

    bundle = subparsers.add_parser("validate-bundle", help="validate the captured dump/log bundle in a manifest")
    bundle.add_argument("--manifest", type=Path, required=True)
    bundle.add_argument("--exe", type=Path, required=True)
    bundle.add_argument("--bundle-dir", type=Path, required=True)
    bundle.add_argument("--report-out", type=Path)

    ida = subparsers.add_parser("emit-ida-json", help="emit an IDA-consumable crash record")
    ida.add_argument("--manifest", type=Path, required=True)
    ida.add_argument("--exe", type=Path, required=True)
    ida.add_argument("--bundle-dir", type=Path, required=True)
    ida.add_argument("--bundle-report", type=Path, required=True)
    ida.add_argument("--output", type=Path, required=True)
    ida.add_argument("--exception-code", required=True)
    ida.add_argument("--exception-address", required=True)
    ida.add_argument("--module", required=True)
    ida.add_argument("--module-base", required=True)
    ida.add_argument("--module-rva", required=True)
    ida.add_argument("--register", action="append", required=True)
    ida.add_argument("--stack-frame", action="append", required=True)

    args = parser.parse_args()
    if args.command == "verify-exe":
        result = verify_executable(args.manifest, args.exe)
    elif args.command == "emit-wer-plan":
        result = emit_wer_plan(
            args.manifest,
            args.exe,
            args.dump_dir,
            args.state_out,
            args.instructions_out,
            restore_out=args.restore_out,
            dump_count=args.dump_count,
            dump_type=args.dump_type,
        )
    elif args.command == "validate-bundle":
        result = validate_bundle(args.manifest, args.exe, args.bundle_dir)
        if args.report_out:
            _write_json(args.report_out, result)
    else:
        result = emit_ida_json(
            args.manifest,
            args.exe,
            args.bundle_dir,
            args.bundle_report,
            args.output,
            exception_code=args.exception_code,
            exception_address=args.exception_address,
            module=args.module,
            module_base=args.module_base,
            module_rva=args.module_rva,
            registers=args.register,
            stack_frames=args.stack_frame,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
