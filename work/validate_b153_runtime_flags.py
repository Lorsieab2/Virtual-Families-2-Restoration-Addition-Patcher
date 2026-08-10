#!/usr/bin/env python3
"""Independent linked-image validation for B153 dormant runtime flags."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import export_offline_patch_bundle as exporter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOB = (
    "VF2-Mobile-Furniture-With-Island-Events-B153-*/"
    "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
)
STOCK_CONTINUATION = bytes.fromhex(
    "F7 6D 08 53 56 8B F1 C1 FA 03 8B DA B8 56 55 55 55 57 "
    "BF 64 00 00 00 C1 EB 1F 03 DA 8B CF 2B 4E 4C"
)


MORTALITY_TRAMPOLINE = bytes.fromhex(
    "6A 00 8B CB E8 00 00 00 00 80 3D 00 00 00 00 00 74 20 "
    "50 FF 73 08 E8 00 00 00 00 83 C4 08 85 C0 74 0B "
    "6A 02 6A 00 8B CB E8 00 00 00 00 E9 00 00 00 00 "
    "E9 00 00 00 00"
)
MORTALITY_WILDCARD_RANGES = (
    range(5, 9),
    range(11, 15),
    range(23, 27),
    range(41, 45),
    range(46, 50),
    range(51, 55),
)
MORTALITY_WILDCARDS = frozenset(
    offset for offsets in MORTALITY_WILDCARD_RANGES for offset in offsets
)
MORTALITY_B155_SSA_2022_BASIS_POINTS_55_TO_105 = (
    67, 73, 79, 86, 93, 101, 109, 117, 126, 135,
    145, 154, 164, 175, 189, 204, 221, 240, 262, 287,
    315, 351, 388, 428, 472, 524, 581, 643, 714, 794,
    887, 990, 1107, 1237, 1375, 1528, 1695, 1882, 2086, 2302,
    2527, 2756, 2990, 3222, 3445, 3673, 3906, 4143, 4382, 4622,
    4875,
)
MORTALITY_B155_HAZARDS_BASIS_POINTS_55_TO_130 = (
    MORTALITY_B155_SSA_2022_BASIS_POINTS_55_TO_105 + (5000,) * 25
)
MORTALITY_B155_5_HAZARDS_MILLIONTHS_55_TO_317 = tuple(
    min(
        999999,
        int(
            math.floor(
                -math.expm1(
                    -(
                        0.00365 * max(0, age - 55)
                        + 0.06 * max(0, age - 110)
                    )
                )
                * 1000000
                + 0.5
            )
        ),
    )
    for age in range(55, 318)
)

PREGNANCY_COOLDOWN_TRAMPOLINE = bytes.fromhex(
    "FF B3 54 6A 00 00 FF B7 54 6A 00 00 56 50 E8 00 00 00 00 "
    "83 C4 10 8B 4D D0 6A CE E9 00 00 00 00"
)
PREGNANCY_COOLDOWN_WILDCARDS = frozenset((*range(15, 19), *range(28, 32)))


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


# These controls are deliberately resolved from the final PE section table.
# Icon-resource preservation can insert a file-alignment block before the
# sections, so a source/build-time raw offset is not a valid final readback
# coordinate.  .shr is intentionally absent: it is native HWND storage, not a
# gameplay runtime toggle.
RUNTIME_FLAG_SECTIONS = {
    "holiday_furniture_goals": ".vf2goal",
    "mobile_furniture_behaviors": ".vf2beh",
    "allow_older_pregnancies": ".vf2preg",
    "same_sex_marriage": ".vf2same",
    "older_villager_mortality": ".vf2mort",
    "store_scroll_bar": ".vf2scrl",
}


def rel32_target(source_rva: int, instruction_size: int, displacement: int) -> int:
    return source_rva + instruction_size + displacement


def validate_older_pregnancy(path: Path, expected_flag: int) -> dict:
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

    cooldown_candidates = []
    for section in image.sections:
        if not (section["characteristics"] & 0x20000000):
            continue
        raw = section["raw_offset"]
        section_data = image.data[raw:raw + section["raw_size"]]
        cooldown_candidates.extend(
            raw + offset
            for offset in masked_matches(
                section_data,
                PREGNANCY_COOLDOWN_TRAMPOLINE,
                PREGNANCY_COOLDOWN_WILDCARDS,
            )
        )
    if len(cooldown_candidates) != 1:
        raise ValueError(
            f"{path}: expected one pregnancy-cooldown trampoline, "
            f"found {len(cooldown_candidates)}"
        )
    cooldown_trampoline_raw = cooldown_candidates[0]
    cooldown_trampoline_rva = image.raw_to_rva(cooldown_trampoline_raw)
    cooldown_code = image.data[
        cooldown_trampoline_raw:cooldown_trampoline_raw + 32
    ]
    cooldown_helper_rva = rel32_target(
        cooldown_trampoline_rva + 14,
        5,
        struct.unpack_from("<i", cooldown_code, 15)[0],
    )
    executable_section_for_rva(image, cooldown_helper_rva)
    cooldown_continue_rva = rel32_target(
        cooldown_trampoline_rva + 27,
        5,
        struct.unpack_from("<i", cooldown_code, 28)[0],
    )
    cooldown_detours = []
    for section in image.sections:
        if not (section["characteristics"] & 0x20000000):
            continue
        raw = section["raw_offset"]
        section_data = image.data[raw:raw + section["raw_size"]]
        for offset in range(0, max(len(section_data) - 11, 0)):
            if section_data[offset] != 0xE9:
                continue
            if section_data[offset + 5:offset + 11] != b"\x90" * 6:
                continue
            source_rva = section["rva"] + offset
            target_rva = rel32_target(
                source_rva,
                5,
                struct.unpack_from("<i", section_data, offset + 1)[0],
            )
            if target_rva == cooldown_trampoline_rva:
                cooldown_detours.append(source_rva)
    if len(cooldown_detours) != 1:
        raise ValueError(
            f"{path}: expected one pregnancy-cooldown detour, "
            f"found {len(cooldown_detours)}"
        )
    cooldown_hook_rva = cooldown_detours[0]
    if cooldown_continue_rva != cooldown_hook_rva + 11:
        raise ValueError(f"{path}: pregnancy cooldown does not resume at +0xb")

    cooldown_helper_raw = image.rva_to_raw(cooldown_helper_rva)
    cooldown_helper = image.data[cooldown_helper_raw:cooldown_helper_raw + 120]
    helper_prefix = bytes.fromhex(
        "81 7C 24 0C E8 03 00 00 7D 0E "
        "81 7C 24 10 E8 03 00 00 7D 04 32 C0 EB 02 B0 01 80 3D"
    )
    helper_suffix = bytes.fromhex(
        "00 74 04 84 C0 75 0E 8B 44 24 04 8B 4C 24 08 "
        "89 88 E0 5A 02 00 C3"
    )
    if cooldown_helper[:28] == helper_prefix:
        cooldown_flag_va = struct.unpack_from("<I", cooldown_helper, 28)[0]
        if cooldown_flag_va != expected_flag_va:
            raise ValueError(f"{path}: pregnancy cooldown flag VA drifted")
        if cooldown_helper[32:54] != helper_suffix:
            raise ValueError(f"{path}: pregnancy cooldown conditional write drifted")
    else:
        same_flag = image.section(".vf2same")
        same_flag_va = image.image_base + same_flag["rva"]
        if cooldown_helper[:5] != b"\x83\xEC\x08\x80\x3D":
            raise ValueError(f"{path}: same-sex cooldown guard prologue drifted")
        if struct.unpack_from("<I", cooldown_helper, 5)[0] != same_flag_va:
            raise ValueError(f"{path}: same-sex cooldown flag VA drifted")
        shifted_prefix = bytes.fromhex(
            "81 7C 24 14 E8 03 00 00 7D 0E "
            "81 7C 24 18 E8 03 00 00 7D 04 32 C0 EB 02 B0 01 80 3D"
        )
        shifted_suffix = bytes.fromhex(
            "00 74 04 84 C0 75 0E 8B 44 24 0C 8B 4C 24 10 "
            "89 88 E0 5A 02 00 83 C4 08 C3"
        )
        shifted = cooldown_helper.find(shifted_prefix)
        if shifted < 0:
            raise ValueError(f"{path}: pregnancy cooldown age-50 gate drifted")
        cooldown_flag_va = struct.unpack_from(
            "<I", cooldown_helper, shifted + len(shifted_prefix)
        )[0]
        if cooldown_flag_va != expected_flag_va:
            raise ValueError(f"{path}: pregnancy cooldown flag VA drifted")
        suffix_start = shifted + len(shifted_prefix) + 4
        if cooldown_helper[
            suffix_start:suffix_start + len(shifted_suffix)
        ] != shifted_suffix:
            raise ValueError(f"{path}: pregnancy cooldown conditional write drifted")

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
        "cooldown_hook_rva": f"0x{cooldown_hook_rva:x}",
        "cooldown_trampoline_rva": f"0x{cooldown_trampoline_rva:x}",
        "cooldown_helper_rva": f"0x{cooldown_helper_rva:x}",
        "age_50_plus_skips_failed_attempt_cooldown": True,
    }


def validate_one_byte_flag(
    image: LinkedPE,
    section_name: str,
    expected_flag: int,
) -> dict:
    section = image.section(section_name)
    if section["virtual_size"] != 1 or section["raw_size"] < 1:
        raise ValueError(
            f"{image.path}: {section_name} is not a one-byte control"
        )
    if not (section["characteristics"] & 0x80000000):
        raise ValueError(f"{image.path}: {section_name} is not writable")
    raw = section["raw_offset"]
    actual = image.data[raw]
    if actual != expected_flag:
        raise ValueError(
            f"{image.path}: {section_name} expected {expected_flag:02x}, "
            f"got {actual:02x}"
        )
    return {
        "section": section_name,
        "raw_offset": f"0x{raw:x}",
        "rva": f"0x{section['rva']:x}",
        "value": f"{actual:02x}",
        "writable": True,
    }


def validate_applied_runtime_flag_bytes(
    path: Path,
    expected_flag: int,
) -> dict[str, dict]:
    """Read applied runtime controls from the final PE section table.

    This is intentionally independent of source-object offsets and of the
    static helper/trampoline contracts.  It is the readback used after an
    asset-preserving reconfiguration has shifted PE raw data.
    """
    image = LinkedPE(path)
    flags = {
        setting_id: validate_one_byte_flag(image, section_name, expected_flag)
        for setting_id, section_name in RUNTIME_FLAG_SECTIONS.items()
    }
    offsets = [int(flag["raw_offset"], 16) for flag in flags.values()]
    if len(offsets) != len(set(offsets)):
        raise ValueError(f"{path}: runtime flag section offsets overlap")
    return flags


def executable_section_for_rva(image: LinkedPE, rva: int) -> dict:
    for section in image.sections:
        span = max(section["virtual_size"], section["raw_size"])
        if section["rva"] <= rva < section["rva"] + span:
            if not (section["characteristics"] & 0x20000000):
                raise ValueError(
                    f"{image.path}: RVA {rva:#x} target is not executable"
                )
            return section
    raise ValueError(f"{image.path}: RVA {rva:#x} has no linked section")


def masked_matches(data: bytes, pattern: bytes, wildcards: frozenset[int]):
    limit = len(data) - len(pattern) + 1
    for start in range(max(limit, 0)):
        if all(
            offset in wildcards or data[start + offset] == expected
            for offset, expected in enumerate(pattern)
        ):
            yield start


def validate_older_mortality(
    path: Path,
    expected_flag: int,
    build_label: str = "B153",
) -> dict:
    image = LinkedPE(path)
    flag = validate_one_byte_flag(image, ".vf2mort", expected_flag)
    candidates = []
    for section in image.sections:
        if not (section["characteristics"] & 0x20000000):
            continue
        raw = section["raw_offset"]
        section_data = image.data[raw:raw + section["raw_size"]]
        candidates.extend(
            raw + offset
            for offset in masked_matches(
                section_data,
                MORTALITY_TRAMPOLINE,
                MORTALITY_WILDCARDS,
            )
        )
    if len(candidates) != 1:
        raise ValueError(
            f"{path}: expected one mortality trampoline, found {len(candidates)}"
        )
    trampoline_raw = candidates[0]
    trampoline_rva = image.raw_to_rva(trampoline_raw)
    code = image.data[trampoline_raw:trampoline_raw + 55]

    flag_va = struct.unpack_from("<I", code, 11)[0]
    expected_flag_va = image.image_base + int(flag["rva"], 16)
    if flag_va != expected_flag_va:
        raise ValueError(
            f"{path}: mortality flag VA {flag_va:#x} != {expected_flag_va:#x}"
        )

    food_rva = rel32_target(
        trampoline_rva + 4,
        5,
        struct.unpack_from("<i", code, 5)[0],
    )
    helper_rva = rel32_target(
        trampoline_rva + 22,
        5,
        struct.unpack_from("<i", code, 23)[0],
    )
    set_health_rva = rel32_target(
        trampoline_rva + 40,
        5,
        struct.unpack_from("<i", code, 41)[0],
    )
    for target in (food_rva, helper_rva, set_health_rva):
        executable_section_for_rva(image, target)

    detour_sources = []
    for section in image.sections:
        if not (section["characteristics"] & 0x20000000):
            continue
        raw = section["raw_offset"]
        section_data = image.data[raw:raw + section["raw_size"]]
        for offset in range(0, max(len(section_data) - 9, 0)):
            if section_data[offset] != 0xE9:
                continue
            if section_data[offset + 5:offset + 9] != b"\x90" * 4:
                continue
            source_rva = section["rva"] + offset
            target = rel32_target(
                source_rva,
                5,
                struct.unpack_from("<i", section_data, offset + 1)[0],
            )
            if target == trampoline_rva:
                detour_sources.append(source_rva)
    if len(detour_sources) != 1:
        raise ValueError(
            f"{path}: expected one mortality detour, found {len(detour_sources)}"
        )
    hook_rva = detour_sources[0]
    mortality_done_rva = rel32_target(
        trampoline_rva + 45,
        5,
        struct.unpack_from("<i", code, 46)[0],
    )
    stock_continue_rva = rel32_target(
        trampoline_rva + 50,
        5,
        struct.unpack_from("<i", code, 51)[0],
    )
    if stock_continue_rva != hook_rva + 9:
        raise ValueError(f"{path}: mortality flag-off path does not resume at +9")
    if mortality_done_rva != hook_rva + 0x75:
        raise ValueError(f"{path}: mortality enabled path does not rejoin at +0x75")

    helper_raw = image.rva_to_raw(helper_rva)
    helper_window = image.data[helper_raw:helper_raw + 0x240]
    age_math = bytes.fromhex(
        "B8 CD CC CC CC F7 E1 C1 EA 04 8D 04 92 C1 E0 02 2B C8 75"
    )
    if helper_window.find(age_math) != 8:
        raise ValueError(f"{path}: mortality helper 20-tick birthday math drifted")
    try:
        build_number = float(build_label.lstrip("Bb"))
    except ValueError as exc:
        raise ValueError(f"Invalid build label for mortality validation: {build_label}") from exc
    if build_number >= 155.5:
        if b"\x68\x40\x42\x0f\x00" not in helper_window:
            raise ValueError(f"{path}: mortality helper does not request GetRandom(1000000)")
        if bytes.fromhex("BE 3F 42 0F 00 81 FA 3D 01 00 00 7F") not in helper_window:
            raise ValueError(f"{path}: B155.5 mortality cap/table boundary drifted")
        hazard_table = struct.pack(
            "<263i", *MORTALITY_B155_5_HAZARDS_MILLIONTHS_55_TO_317
        )
        if image.data.count(hazard_table) != 1:
            raise ValueError(
                f"{path}: expected one exact B155.5 millionth mortality table"
            )
        helper_random_limit = 1000000
        hazard_metadata = {
            "maximum_hazard_millionths": 999999,
            "hazard_table_first_effective_age": 55,
            "hazard_table_last_effective_age": 317,
        }
    elif build_number >= 155:
        if b"\x68\x10\x27\x00\x00" not in helper_window:
            raise ValueError(f"{path}: mortality helper does not request GetRandom(10000)")
        if bytes.fromhex("BE 88 13 00 00 81 FA 82 00 00 00 7F") not in helper_window:
            raise ValueError(f"{path}: mortality helper 50-percent age-106+ plateau drifted")
        hazard_table = struct.pack(
            "<76i", *MORTALITY_B155_HAZARDS_BASIS_POINTS_55_TO_130
        )
        if image.data.count(hazard_table) != 1:
            raise ValueError(
                f"{path}: expected one exact B155 SSA/plateau mortality table"
            )
        helper_random_limit = 10000
        hazard_metadata = {
            "maximum_hazard_basis_points": 5000,
            "hazard_table_first_effective_age": 55,
            "hazard_table_last_effective_age": 130,
        }
    else:
        if b"\x68\x10\x27\x00\x00" not in helper_window:
            raise ValueError(f"{path}: mortality helper does not request GetRandom(10000)")
        if bytes.fromhex("BE 0F 27 00 00 81 FA 82 00 00 00 7F") not in helper_window:
            raise ValueError(f"{path}: mortality helper 99.99-percent hazard cap drifted")
        helper_random_limit = 10000
        hazard_metadata = {
            "maximum_hazard_basis_points": 9999,
            "hazard_table_first_effective_age": 55,
            "hazard_table_last_effective_age": 130,
        }
    if bytes.fromhex("B8 04 00 00 00 3B C8 0F 4F C8") not in helper_window:
        raise ValueError(f"{path}: mortality helper four-group clamp drifted")
    if bytes.fromhex("83 FA 37 7C") not in helper_window:
        raise ValueError(f"{path}: mortality helper effective-age-55 gate drifted")

    return {
        "flag": flag,
        "trampoline_rva": f"0x{trampoline_rva:x}",
        "hook_rva": f"0x{hook_rva:x}",
        "food_groups_target_rva": f"0x{food_rva:x}",
        "helper_rva": f"0x{helper_rva:x}",
        "set_health_target_rva": f"0x{set_health_rva:x}",
        "flag_off_rejoins_stock_at_hook_plus": "0x9",
        "enabled_rejoins_after_old_age_block_at_hook_plus": "0x75",
        "helper_random_limit": helper_random_limit,
        **hazard_metadata,
        "maximum_food_group_effective_age_reduction": 4,
    }


def validate_exe(
    path: Path,
    expected_flag: int,
    build_label: str = "B153",
    *,
    validate_static_helpers: bool = True,
) -> dict:
    image = LinkedPE(path)
    runtime_flags = validate_applied_runtime_flag_bytes(path, expected_flag)
    if validate_static_helpers:
        pregnancy = validate_older_pregnancy(path, expected_flag)
        mortality = validate_older_mortality(path, expected_flag, build_label)
        static_helper_validation = {
            "status": "validated",
            "build_label": build_label,
        }
    else:
        # Applied-byte readback must remain usable when a final executable's
        # helper was built from a newer/alternate source contract.  Do not
        # silently call that a helper validation; report the distinction.
        pregnancy = None
        mortality = {
            "flag": runtime_flags["older_villager_mortality"],
            "static_helper_validation": "skipped",
        }
        static_helper_validation = {
            "status": "skipped",
            "reason": "runtime section readback only",
        }
    original = bytes(image.data)
    flag_offsets = [int(flag["raw_offset"], 16) for flag in runtime_flags.values()]
    if len(set(flag_offsets)) != len(flag_offsets):
        raise ValueError(f"{path}: runtime flag offsets overlap")
    enabled = bytearray(original)
    for offset in flag_offsets:
        enabled[offset] = 1
    enabled_once = bytes(enabled)
    for offset in flag_offsets:
        enabled[offset] = 1
    repeated_enable_idempotent = bytes(enabled) == enabled_once
    for offset in flag_offsets:
        enabled[offset] = 0
    disable_restores_original = bytes(enabled) == original

    return {
        "path": str(path),
        "sha256": hashlib.sha256(image.data).hexdigest(),
        "size": len(image.data),
        "runtime_flags": runtime_flags,
        "older_pregnancy": pregnancy,
        "older_mortality": mortality,
        "static_helper_validation": static_helper_validation,
        "toggle_cycle": {
            "runtime_flag_count": len(flag_offsets),
            "nonoverlapping_offsets": True,
            "enable_sets_all_to_01": all(enabled_once[offset] == 1 for offset in flag_offsets),
            "repeated_enable_idempotent": repeated_enable_idempotent,
            "disable_after_enable_restores_exact_original": disable_restores_original,
        },
    }


def validate_post_asset_records(
    results: list[dict],
    executable_paths: list[Path],
    build_manifest_path: Path,
    build_label: str,
) -> list[dict]:
    build_manifest = json.loads(build_manifest_path.read_text(encoding="utf-8"))
    records = exporter.b152_runtime_flag_post_asset_patches(
        executable_paths,
        output_exe_name=f"Virtual Families 2 - Modded {build_label}.exe",
        build_manifest_data=build_manifest,
    )
    expected = {
        "mobile_furniture_behaviors": ("mobile_furniture_behaviors", ".vf2beh"),
        "holiday_furniture": ("holiday_furniture_goals", ".vf2goal"),
        "allow_older_pregnancies": ("allow_older_pregnancies", ".vf2preg"),
        "same_sex_marriage": ("same_sex_marriage", ".vf2same"),
        "older_villager_mortality": ("older_villager_mortality", ".vf2mort"),
    }
    if len(records) != len(expected):
        raise ValueError(
            f"Expected {len(expected)} runtime records, got {len(records)}"
        )
    result_by_sha = {row["sha256"].lower(): row for row in results}
    for record in records:
        setting_id = record["requires"][-1]
        if setting_id not in expected:
            raise ValueError(f"Unexpected runtime record {setting_id}")
        result_key, section_name = expected[setting_id]
        variants = record.get("variants", [])
        if len(variants) != len(result_by_sha):
            raise ValueError(
                f"{setting_id}: expected {len(result_by_sha)} variants, "
                f"got {len(variants)}"
            )
        seen = set()
        for variant in variants:
            sha = str(variant["asset_sha256"]).lower()
            if sha in seen or sha not in result_by_sha:
                raise ValueError(f"{setting_id}: duplicate or unknown SHA {sha}")
            seen.add(sha)
            flag = result_by_sha[sha]["runtime_flags"][result_key]
            if variant["offset"].lower() != flag["raw_offset"].lower():
                raise ValueError(f"{setting_id}: flag offset mismatch for {sha}")
            if variant["expected_asset_bytes"] != "00":
                raise ValueError(f"{setting_id}: expected byte is not 00")
            if variant["replacement_bytes"] != "01":
                raise ValueError(f"{setting_id}: replacement byte is not 01")
            if section_name != flag["section"]:
                raise ValueError(f"{setting_id}: section contract drifted")
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--build-label",
        default="B153",
        help="Build label used for automatic output discovery (default: B153).",
    )
    parser.add_argument("--build-manifest", type=Path)
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
        build_glob = DEFAULT_GLOB.replace("B153", args.build_label)
        paths = sorted((ROOT / "outputs").glob(build_glob))
    if not paths:
        raise SystemExit(
            f"No {args.build_label} executable paths were supplied or discovered."
        )
    expected_flag = 1 if args.expect_enabled else 0
    results = []
    failures = []
    for path in paths:
        try:
            results.append(validate_exe(path, expected_flag, args.build_label))
        except (OSError, ValueError, struct.error) as exc:
            failures.append(f"{path}: {exc}")
    if failures:
        raise SystemExit(
            f"{args.build_label} runtime-flag validation failed:\n- "
            + "\n- ".join(failures)
        )
    hashes = {row["sha256"] for row in results}
    if len(results) == 16 and len(hashes) != 16:
        raise ValueError(
            f"Expected 16 unique linked executable hashes, got {len(hashes)}"
        )
    build_manifest_path = args.build_manifest
    if build_manifest_path is None:
        candidate = paths[0].parent / "patch-manifest.json"
        if candidate.is_file():
            build_manifest_path = candidate
    post_asset_patches = []
    if build_manifest_path is not None:
        post_asset_patches = validate_post_asset_records(
            results, paths, build_manifest_path.resolve(), args.build_label
        )
    report = {
        "status": "validated",
        "expected_flag": f"{expected_flag:02x}",
        "executable_count": len(results),
        "unique_executable_hashes": len(hashes),
        "post_asset_patch_record_count": len(post_asset_patches),
        "post_asset_patches": post_asset_patches,
        "executables": results,
    }
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
