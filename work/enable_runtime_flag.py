"""Enable one exact one-byte runtime flag in a linked VF2 PE32 executable."""
from __future__ import annotations

import struct
import sys
from pathlib import Path


def enable(path: Path, section_name: str) -> None:
    data = bytearray(path.read_bytes())
    if data[:2] != b"MZ":
        raise ValueError(f"not a PE image: {path}")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise ValueError(f"invalid PE signature: {path}")
    section_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    section_base = pe + 24 + optional_size
    found = None
    for index in range(section_count):
        off = section_base + index * 40
        name = bytes(data[off : off + 8]).rstrip(b"\0").decode("ascii")
        raw_size, raw_ptr = struct.unpack_from("<II", data, off + 16)
        virtual_size = struct.unpack_from("<I", data, off + 8)[0]
        if name == section_name:
            if found is not None:
                raise ValueError(f"duplicate {section_name} section: {path}")
            if virtual_size != 1 or raw_size < 1 or raw_ptr >= len(data):
                raise ValueError(f"invalid {section_name} runtime section: {path}")
            found = raw_ptr
    if found is None:
        raise ValueError(f"missing {section_name} section: {path}")
    if data[found] not in (0, 1):
        raise ValueError(f"unexpected {section_name} value {data[found]:02x}: {path}")
    data[found] = 1
    path.write_bytes(data)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: enable_runtime_flag.py EXE SECTION")
    enable(Path(sys.argv[1]), sys.argv[2])
