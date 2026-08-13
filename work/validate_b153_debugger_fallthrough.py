#!/usr/bin/env python3
"""Validate the B153 debugger input-hook false-result fallthrough."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def masked_matches(data: bytes, pattern: bytes, wildcards: set[int]) -> list[int]:
    matches: list[int] = []
    limit = len(data) - len(pattern) + 1
    for start in range(max(0, limit)):
        if all(index in wildcards or data[start + index] == value for index, value in enumerate(pattern)):
            matches.append(start)
    return matches


def hook_pattern(arguments: bytes, cleanup: int, helper_this: bool = False) -> tuple[bytes, set[int]]:
    prefix = b"\x51" + arguments
    if helper_this:
        prefix += b"\x51"
    call = b"\xE8\x00\x00\x00\x00"
    stack = 8 if helper_this or len(arguments) == 6 else 4
    suffix = (
        b"\x83\xC4" + bytes([stack])
        + b"\x59\x84\xC0\x74\x06\xB0\x01\x5D\xC2"
        + cleanup.to_bytes(2, "little")
    )
    pattern = prefix + call + suffix
    call_start = len(prefix)
    return pattern, set(range(call_start + 1, call_start + 5))


def validate(exe: Path, manifest_path: Path) -> dict:
    data = exe.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    developer = manifest.get("debug_features", {}).get("developer_keys", {})
    if "F5-gated" not in str(developer.get("status", "")):
        raise ValueError("debug_features.developer_keys is not F5-gated")
    hooks = developer.get("input_hooks", [])
    if len(hooks) != 5:
        raise ValueError(f"expected five debugger input hooks, found {len(hooks)}")
    expected_providers = [
        "main scene debugger",
        "villager manager debugger",
    ]
    if developer.get("registered_providers") != expected_providers:
        raise ValueError(
            "debugger provider list is incomplete or incorrect: "
            f"{developer.get('registered_providers')!r}"
        )
    expected_key_codes = {
        "Up": "0x3EE",
        "Down": "0x3EF",
        "F4": "0x3FD",
        "F5": "0x3FE",
        "F6": "0x3FF",
        "F7": "0x400",
    }
    if developer.get("internal_key_codes") != expected_key_codes:
        raise ValueError(
            "debugger internal key map is incomplete or incorrect: "
            f"{developer.get('internal_key_codes')!r}"
        )

    specs = [
        ("key_down", *hook_pattern(b"\xFF\x75\x08", 4, helper_this=True), 1),
        ("key_character", *hook_pattern(b"\xFF\x75\x08", 4), 1),
        ("mouse", *hook_pattern(b"\xFF\x75\x0C\xFF\x75\x08", 8), 3),
    ]
    rows = []
    for name, pattern, wildcards, expected_count in specs:
        matches = masked_matches(data, pattern, wildcards)
        if len(matches) != expected_count:
            raise ValueError(f"{name}: expected {expected_count} corrected hook(s), found {len(matches)}")
        jump_offset = pattern.index(b"\x74\x06")
        for start in matches:
            branch_end = start + jump_offset + 2
            target = branch_end + 6
            expected_target = start + len(pattern)
            if target != expected_target:
                raise ValueError(f"{name}: false-result branch does not land at stock body")
        old_pattern = bytearray(pattern)
        old_pattern[jump_offset + 1] = 4
        if masked_matches(data, bytes(old_pattern), wildcards):
            raise ValueError(f"{name}: stale JE +4 hook remains")
        rows.append({"name": name, "count": len(matches), "offsets": [hex(value) for value in matches]})

    return {
        "status": "validated",
        "path": str(exe.resolve()),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "exception_regression": {
            "old_fault_rva": "0xc5d4b",
            "old_exception": "0xc0000005",
            "cause": "JE +4 entered the RET 8 immediate",
            "fix": "JE +6 lands exactly at the stock function body",
        },
        "hooks": rows,
        "registered_providers": expected_providers,
        "internal_key_codes": expected_key_codes,
        "live_retest_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate(args.exe, args.manifest)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
