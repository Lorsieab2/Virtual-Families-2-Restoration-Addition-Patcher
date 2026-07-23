from __future__ import annotations

import hashlib
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "patcher_assets"
    / "optional_patches"
    / "mobile_furniture_behaviors"
    / "mobile_fmaps"
)
DESTINATION = SOURCE.parent / "pc_fmaps"

SPECS = {
    "Birthday_cake.png.fmap": {
        "value": 0x2000A000,
        "cells": ((4, 7), (5, 7), (6, 7)),
        "sha256": "e1c55dc0d38b44003abe878cd9ccdfee3e49b5c7ed9e793d14b25c0fae57926d",
    },
    "Birthday_presents.png.fmap": {
        "value": 0x20009800,
        "cells": ((3, 9), (4, 9), (5, 9)),
        "sha256": "63ef84177e87b4a4dd28c0a85c4aff2ee741423ca4ac34b3d273cb11fd4a18c5",
    },
}


def build() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for filename, spec in SPECS.items():
        source = SOURCE / filename
        data = bytearray(source.read_bytes())
        if data[:4] != b"QAMF":
            raise ValueError(f"Unrecognized QAMF: {source}")
        width, height = struct.unpack_from("<II", data, 24)
        grid_end = 32 + width * height * 4
        if grid_end + 16 != len(data):
            raise ValueError(f"Unexpected QAMF layout: {source}")
        data[32:grid_end] = bytes(grid_end - 32)
        for x, y in spec["cells"]:
            struct.pack_into("<I", data, 32 + (y * width + x) * 4, spec["value"])
        digest = hashlib.sha256(data).hexdigest()
        if digest != spec["sha256"]:
            raise ValueError(f"{filename}: expected {spec['sha256']}, got {digest}")
        target = DESTINATION / filename
        target.write_bytes(data)
        print(f"{filename} {width}x{height} {len(data)} {digest}")


if __name__ == "__main__":
    build()
