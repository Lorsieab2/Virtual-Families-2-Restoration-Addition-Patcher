from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct


@dataclass
class PESection:
    name: str
    rva: int
    virtual_size: int
    raw_ptr: int
    raw_size: int
    characteristics: int


class PEImage:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        pe_off = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[pe_off : pe_off + 4] != b"PE\0\0":
            raise RuntimeError(f"{path}: not a PE image")
        coff = pe_off + 4
        section_count = struct.unpack_from("<H", self.data, coff + 2)[0]
        optional_size = struct.unpack_from("<H", self.data, coff + 16)[0]
        section_off = coff + 20 + optional_size
        self.sections = []
        for index in range(section_count):
            off = section_off + index * 40
            name = self.data[off : off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size, rva, raw_size, raw_ptr = struct.unpack_from("<IIII", self.data, off + 8)
            characteristics = struct.unpack_from("<I", self.data, off + 36)[0]
            self.sections.append(
                PESection(name, rva, virtual_size, raw_ptr, raw_size, characteristics)
            )

    def executable_sections(self):
        return [section for section in self.sections if section.characteristics & 0x20000000]

    def file_to_rva(self, file_off: int) -> int:
        for section in self.sections:
            if section.raw_ptr <= file_off < section.raw_ptr + section.raw_size:
                return section.rva + file_off - section.raw_ptr
        raise RuntimeError(f"{self.path}: file offset {file_off:#x} is outside sections")

    def rva_to_file(self, rva: int) -> int:
        for section in self.sections:
            span = max(section.virtual_size, section.raw_size)
            if section.rva <= rva < section.rva + span:
                return section.raw_ptr + rva - section.rva
        raise RuntimeError(f"{self.path}: RVA {rva:#x} is outside sections")

    def find_executable(self, pattern: bytes, predicate=None) -> int:
        matches = []
        for section in self.executable_sections():
            start = section.raw_ptr
            end = start + section.raw_size
            position = start
            while True:
                position = self.data.find(pattern, position, end)
                if position < 0:
                    break
                if predicate is None or predicate(position):
                    matches.append(position)
                position += 1
        if len(matches) != 1:
            raise RuntimeError(
                f"{self.path}: expected one executable match for {pattern.hex()}, got {len(matches)}"
            )
        return matches[0]

    def rel32_target(self, opcode_off: int, instruction_size: int = 5) -> int:
        displacement_off = opcode_off + instruction_size - 4
        displacement = struct.unpack_from("<i", self.data, displacement_off)[0]
        return self.file_to_rva(opcode_off) + instruction_size + displacement

    def rel8_target(self, opcode_off: int) -> int:
        displacement = struct.unpack_from("<b", self.data, opcode_off + 1)[0]
        return self.file_to_rva(opcode_off) + 2 + displacement


def expect(condition: bool, message: str):
    if not condition:
        raise RuntimeError(message)


def validate_find(image: PEImage):
    prefix = bytes.fromhex(
        "55 8B EC 83 EC 14 53 56 33 D2 C7 45 FC 80 96 98 00 "
        "8D 71 CC 89 55 F8 57 8B 7D 0C 33 DB 89 75 F4"
    )
    base = image.find_executable(prefix)
    detour = base + 0x86
    expect(image.data[detour] == 0xE9, "Find+0x86 is not a near-jump detour")
    expect(image.data[detour + 5 : detour + 13] == b"\x90" * 8, "Find detour padding drifted")
    cave_rva = image.rel32_target(detour)
    cave = image.rva_to_file(cave_rva)
    expect(
        image.data[cave : cave + 6] == b"\x81\xFF\x9E\x00\x00\x00",
        "Find cave lacks the unsigned imm32 Holiday request compare",
    )
    expect(image.rel8_target(cave + 6) == cave_rva + 27, "Find stock branch misses cave stock path")
    for relative, target in ((16, 0x93), (22, 0xC4), (30, 0xC4), (42, 0xC4), (48, 0x93)):
        size = 6 if image.data[cave + relative] == 0x0F else 5
        expect(
            image.rel32_target(cave + relative, size) == image.file_to_rva(base) + target,
            f"Find cave branch +{relative:#x} misses native +{target:#x}",
        )


def validate_was_item_spawned(image: PEImage):
    prefix = bytes.fromhex(
        "55 8B EC 8D 81 50 03 00 00 33 D2 8B 4D 08 66 90 80 78 FC 00"
    )
    base = image.find_executable(prefix)
    detour = base + 0x14
    expect(image.data[detour] == 0xE9, "WasItemSpawned+0x14 is not a near-jump detour")
    expect(image.data[detour + 5 : detour + 7] == b"\x90\x90", "WasItemSpawned padding drifted")
    cave_rva = image.rel32_target(detour)
    cave = image.rva_to_file(cave_rva)
    expect(image.data[cave : cave + 2] == b"\x0F\x84", "WasItemSpawned cave loses inactive-slot flags")
    expect(
        image.data[cave + 14 : cave + 20] == b"\x81\xF9\x9E\x00\x00\x00",
        "WasItemSpawned cave lacks the unsigned imm32 Holiday request compare",
    )
    expect(
        image.rel32_target(cave, 6) == cave_rva + 42,
        "WasItemSpawned inactive slot misses cave false path",
    )
    expect(
        image.rel32_target(cave + 8, 6) == image.file_to_rva(base) + 0x29,
        "WasItemSpawned exact match misses native true return",
    )
    expect(image.rel8_target(cave + 20) == cave_rva + 42, "WasItemSpawned non-Holiday path drifted")
    expect(image.rel8_target(cave + 28) == cave_rva + 42, "WasItemSpawned lower-bound path drifted")
    expect(
        image.rel32_target(cave + 36, 6) == image.file_to_rva(base) + 0x29,
        "WasItemSpawned Holiday upper-bound path misses true return",
    )
    expect(
        image.rel32_target(cave + 43) == image.file_to_rva(base) + 0x1B,
        "WasItemSpawned cave misses native loop continuation",
    )


def validate_handle_mouse(image: PEImage):
    prefix = bytes.fromhex("55 8B EC 81 EC 60 01 00 00")

    def is_handle_mouse(position):
        return (
            image.data[position + 0x2A : position + 0x32]
            == bytes.fromhex("83 E9 01 74 66 83 E9 01")
            and image.data[position + 0x1EB] == 0xE9
        )

    base = image.find_executable(prefix, is_handle_mouse)
    detour = base + 0x1EB
    expect(image.data[detour + 5 : detour + 7] == b"\x90\x90", "HandleMouse padding drifted")
    cave_rva = image.rel32_target(detour)
    cave = image.rva_to_file(cave_rva)
    expect(image.data[cave : cave + 3] == b"\x83\xF8\x0F", "HandleMouse cave lower bound drifted")
    expect(image.data[cave + 5 : cave + 8] == b"\x83\xF8\x12", "HandleMouse cave upper bound drifted")
    expect(
        image.data[cave + 10 : cave + 16] == b"\x8D\x98\x42\x07\x00\x00",
        "HandleMouse cave label mapping drifted",
    )
    expect(image.rel8_target(cave + 3) == cave_rva + 21, "HandleMouse low bucket misses stock path")
    expect(image.rel8_target(cave + 8) == cave_rva + 21, "HandleMouse high bucket misses stock path")
    for relative in (16, 28):
        expect(
            image.rel32_target(cave + relative) == image.file_to_rva(base) + 0x1F2,
            f"HandleMouse cave return +{relative:#x} misses native continuation",
        )


def validate_drop_and_achievement(image: PEImage):
    drop_prefix = bytes.fromhex(
        "55 8B EC 83 EC 08 56 57 8B 7D 0C 8B F1 83 FF 4F"
    )
    drop = image.find_executable(drop_prefix)
    expect(image.data[drop + 0x171 : drop + 0x173] == b"\x74\x61", "Drop incomplete branch drifted")
    expect(
        image.file_to_rva(drop + 0x173) + struct.unpack_from("<b", image.data, drop + 0x172)[0]
        == image.file_to_rva(drop) + 0x1D4,
        "Drop incomplete branch misses Holiday hook",
    )
    sentinel = image.data.find(
        b"\x68\x9E\x00\x00\x00\x31\xFF\xE9",
        drop + 0x1D4,
        drop + 0x230,
    )
    expect(sentinel >= 0, "Drop Holiday hook lacks its EDI reentry sentinel")
    expect(
        image.rel32_target(sentinel + 7) == image.file_to_rva(drop) + 0x168,
        "Drop Holiday hook no longer reaches native collection-complete check",
    )
    hook = image.find_executable(
        b"\xEB\x10\x83\xFE\x5F\x75\x0B\x6A\x01\x6A\x54\x8B\xCF\xE8"
    )
    expect(hook >= 0, "SetComplete idempotent split-entry hook is missing")


def validate(path: Path):
    image = PEImage(path)
    validate_find(image)
    validate_was_item_spawned(image)
    validate_handle_mouse(image)
    validate_drop_and_achievement(image)


def main():
    parser = argparse.ArgumentParser(
        description="Validate the linked B150 Holiday Ornaments control-flow hotfix."
    )
    parser.add_argument("executables", nargs="+", type=Path)
    args = parser.parse_args()
    for executable in args.executables:
        validate(executable)
        print(f"PASS {executable}")


if __name__ == "__main__":
    main()
