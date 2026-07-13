#!/usr/bin/env python3
"""Bounded linked-image validation for B152 Allow Older Pregnancies."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOB = "VF2-Mobile-Furniture-With-Island-Events-B152-*/*.exe"
STOCK_CONTINUATION = bytes.fromhex(
    "F7 6D 08 53 56 8B F1 C1 FA 03 8B DA B8 56 55 55 55 57 "
    "BF 64 00 00 00 C1 EB 1F 03 DA 8B CF 2B 4E 4C"
)


class LinkedPE:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if len(self.data) < 0x40 or self.data[:2] != b"MZ":
            raise ValueError(f"{path}: not an MZ image")
        self.pe_offset = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[self.pe_offset:self.pe_offset + 4] != b"PE\0\0":
            raise ValueError(f"{path}: missing PE signature")
        coff = self.pe_offset + 4
        self.section_count = struct.unpack_from("<H", self.data, coff + 2)[0]
        optional_size = struct.unpack_from("<H", self.data, coff + 16)[0]
        optional = coff + 20
        if struct.unpack_from("<H", self.data, optional)[0] != 0x10B:
            raise ValueError(f"{path}: expected PE32")
        self.image_base = struct.unpack_from("<I", self.data, optional + 28)[0]
        section_table = optional + optional_size
        self.sections = []
        for index in range(self.section_count):
            off = section_table + index * 40
            name = self.data[off:off + 8].split(b"\0", 1)[0].decode(
                "ascii", "replace"
            )
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from(
                "<IIII", self.data, off + 8
            )
            characteristics = struct.unpack_from("<I", self.data, off + 36)[0]
            if raw_offset + raw_size > len(self.data):
                raise ValueError(f"{path}: section {name} exceeds the file")
            self.sections.append(
                {
                    "name": name,
                    "virtual_size": virtual_size,
                    "rva": rva,
                    "raw_size": raw_size,
                    "raw_offset": raw_offset,
                    "characteristics": characteristics,
                }
            )

    def section(self, name: str) -> dict:
        matches = [row for row in self.sections if row["name"] == name]
        if len(matches) != 1:
            raise ValueError(
                f"{self.path}: expected one {name} section, found {len(matches)}"
            )
        return matches[0]

    def raw_to_rva(self, raw: int) -> int:
        for section in self.sections:
            start = section["raw_offset"]
            if start <= raw < start + section["raw_size"]:
                return section["rva"] + raw - start
        raise ValueError(f"{self.path}: raw offset {raw:#x} is outside sections")

    def rva_to_raw(self, rva: int) -> int:
        for section in self.sections:
            start = section["rva"]
            span = max(section["virtual_size"], section["raw_size"])
            if start <= rva < start + span:
                raw = section["raw_offset"] + rva - start
                if raw >= section["raw_offset"] + section["raw_size"]:
                    break
                return raw
        raise ValueError(f"{self.path}: RVA {rva:#x} is outside raw sections")


def rel32_target(source_rva: int, instruction_size: int, displacement: int) -> int:
    return source_rva + instruction_size + displacement


def validate_exe(path: Path, expected_flag: int) -> dict:
    image = LinkedPE(path)
    flag = image.section(".vf2preg")
    if flag["virtual_size"] != 1 or flag["raw_size"] < 1:
        raise ValueError(f"{path}: .vf2preg is not a one-byte control")
    if not (flag["characteristics"] & 0x80000000):
        raise ValueError(f"{path}: .vf2preg is not writable")
    flag_raw = flag["raw_offset"]
    actual_flag = image.data[flag_raw]
    if actual_flag != expected_flag:
        raise ValueError(
            f"{path}: .vf2preg expected {expected_flag:02x}, got {actual_flag:02x}"
        )

    continuation_raw = image.data.find(STOCK_CONTINUATION)
    if continuation_raw < 8:
        raise ValueError(f"{path}: ChanceOfPregnancy continuation not found")
    if image.data.find(STOCK_CONTINUATION, continuation_raw + 1) >= 0:
        raise ValueError(f"{path}: ChanceOfPregnancy continuation is ambiguous")
    function_raw = continuation_raw - 8
    function_rva = image.raw_to_rva(function_raw)
    prologue = image.data[function_raw:function_raw + 8]
    if prologue[:1] != b"\xE9" or prologue[5:] != b"\x90\x90\x90":
        raise ValueError(f"{path}: ChanceOfPregnancy detour span is invalid")
    detour_disp = struct.unpack_from("<i", prologue, 1)[0]
    trampoline_rva = rel32_target(function_rva, 5, detour_disp)
    trampoline_raw = image.rva_to_raw(trampoline_rva)
    code = image.data[trampoline_raw:trampoline_raw + 66]
    if len(code) != 66:
        raise ValueError(f"{path}: truncated older-pregnancy trampoline")

    if code[:2] != b"\x80\x3D" or code[6:9] != b"\x00\x74\x2C":
        raise ValueError(f"{path}: runtime flag gate drifted")
    expected_gate = bytes.fromhex(
        "81 7C 24 04 E8 03 00 00 7D 0A "
        "81 7C 24 08 E8 03 00 00 7C 18"
    )
    if code[9:29] != expected_gate:
        raise ValueError(f"{path}: age-50 gate drifted")
    expected_call_setup = bytes.fromhex(
        "FF 74 24 0C FF 74 24 0C FF 74 24 0C 51 E8"
    )
    if code[29:43] != expected_call_setup:
        raise ValueError(f"{path}: late-age helper ABI drifted")
    if code[47:61] != bytes.fromhex(
        "83 C4 10 C2 0C 00 55 8B EC B8 67 66 66 66"
    ):
        raise ValueError(f"{path}: stock fallback or ret-12 ABI drifted")
    if code[61] != 0xE9:
        raise ValueError(f"{path}: stock fallback jump is missing")

    flag_va = struct.unpack_from("<I", code, 2)[0]
    expected_flag_va = image.image_base + flag["rva"]
    if flag_va != expected_flag_va:
        raise ValueError(
            f"{path}: trampoline flag VA {flag_va:#x} != {expected_flag_va:#x}"
        )
    helper_disp = struct.unpack_from("<i", code, 43)[0]
    helper_rva = rel32_target(trampoline_rva + 42, 5, helper_disp)
    helper_raw = image.rva_to_raw(helper_rva)
    helper_section = next(
        section
        for section in image.sections
        if section["raw_offset"]
        <= helper_raw
        < section["raw_offset"] + section["raw_size"]
    )
    if not (helper_section["characteristics"] & 0x20000000):
        raise ValueError(f"{path}: late-age helper target is not executable")
    helper_window = image.data[helper_raw:helper_raw + 0x180]
    random_1000 = helper_window.find(b"\x68\xE8\x03\x00\x00")
    tutorial_success = helper_window.find(
        b"\x6A\x00\x6A\x00\x68\x68\x08\x00\x00",
        max(random_1000, 0),
    )
    failure_return = helper_window.find(
        b"\x5F\x5D\x33\xC0\x5B\xC3",
        max(tutorial_success, 0),
    )
    if random_1000 < 0:
        raise ValueError(f"{path}: linked helper does not push GetRandom(1000)")
    if tutorial_success < 0:
        raise ValueError(f"{path}: linked helper lacks success-only 0x868 queue arguments")
    if failure_return < 0:
        raise ValueError(f"{path}: linked helper lacks the false-return epilogue")
    roll_branch = helper_window.find(
        b"\x3B\xC6\x5E\x7D",
        random_1000,
        tutorial_success,
    )
    if roll_branch < 0:
        raise ValueError(f"{path}: linked helper roll comparison/branch drifted")
    branch_target = (
        roll_branch + 5
        + struct.unpack_from("<b", helper_window, roll_branch + 4)[0]
    )
    if branch_target != failure_return:
        raise ValueError(f"{path}: failed late-age roll does not return false directly")
    fallback_disp = struct.unpack_from("<i", code, 62)[0]
    fallback_rva = rel32_target(trampoline_rva + 61, 5, fallback_disp)
    if fallback_rva != function_rva + 8:
        raise ValueError(f"{path}: stock fallback does not resume at +0x8")

    return {
        "path": str(path),
        "sha256": hashlib.sha256(image.data).hexdigest(),
        "size": len(image.data),
        "flag_raw_offset": f"0x{flag_raw:x}",
        "flag_rva": f"0x{flag['rva']:x}",
        "flag_value": f"{actual_flag:02x}",
        "chance_function_rva": f"0x{function_rva:x}",
        "trampoline_rva": f"0x{trampoline_rva:x}",
        "helper_rva": f"0x{helper_rva:x}",
        "helper_random_limit": 1000,
        "helper_success_tutorial_string": "0x868",
        "failed_roll_direct_false_return": True,
        "stock_continuation_bytes": len(STOCK_CONTINUATION),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", action="append", default=[])
    parser.add_argument(
        "--expect-enabled",
        action="store_true",
        help="Expect the post-asset-patched flag byte 01 instead of build default 00.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = [Path(value).resolve() for value in args.exe]
    if not paths:
        paths = sorted((ROOT / "outputs").glob(DEFAULT_GLOB))
    if not paths:
        raise SystemExit("No B152 executable paths were supplied or discovered.")
    expected_flag = 1 if args.expect_enabled else 0
    results = [validate_exe(path, expected_flag) for path in paths]
    print(
        json.dumps(
            {
                "status": "validated",
                "expected_flag": f"{expected_flag:02x}",
                "executable_count": len(results),
                "executables": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
