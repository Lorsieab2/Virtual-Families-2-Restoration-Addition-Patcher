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
    "Birthday_banner.png.fmap": {
        "value": 0x20008800,
        "cells": ((7, 14), (8, 14), (9, 14), (7, 15), (8, 15), (9, 15), (10, 15)),
    },
    "Balloons_birthday.png.fmap": {
        "value": 0x20009000,
        "cells": ((5, 13), (6, 13), (7, 13)),
    },
    "Dreidel.png.fmap": {
        "value": 0x20005000,
        "cells": ((5, 5), (6, 6), (7, 6), (8, 6)),
    },
    "Menorah.png.fmap": {
        "value": 0x20007000,
        "cells": ((7, 7), (6, 8), (4, 9)),
    },
    "StockingLarge.png.fmap": {
        "value": 0x20008000,
        "cells": ((6, 12), (7, 12)),
    },
    "StockingSmall.png.fmap": {
        "value": 0x20008000,
        "cells": ((4, 10), (5, 10)),
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
        target = DESTINATION / filename
        target.write_bytes(data)
        print(
            f"{filename} {width}x{height} {len(data)} "
            f"{hashlib.sha256(data).hexdigest()}"
        )


if __name__ == "__main__":
    build()
