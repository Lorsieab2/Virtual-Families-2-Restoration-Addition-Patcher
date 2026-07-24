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
    "CandleOnHolder.png.fmap": {
        "value": 0x20004800,
        "cells": ((5, 7), (6, 7), (5, 8)),
    },
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
    "GlassOfEggnog.png.fmap": {
        "value": 0x20005800,
        "cells": ((3, 5), (4, 5)),
    },
    "ChristmasTree1.png.fmap": {
        "value": 0x20004000,
        "cells": (
            (8, 18), (9, 18), (10, 18), (11, 18),
            (6, 19), (8, 19), (9, 19), (10, 19), (11, 19), (12, 19),
            (6, 20), (7, 20), (8, 20), (9, 20),
        ),
    },
    "ChristmasTree2.png.fmap": {
        "value": 0x20004000,
        "cells": (
            (15, 17),
            (14, 18), (15, 18),
            (13, 19), (14, 19),
            (6, 20), (7, 20), (8, 20), (9, 20), (10, 20),
            (11, 20), (12, 20), (13, 20),
        ),
    },
    "Menorah.png.fmap": {
        "value": 0x20007000,
        "cells": ((7, 7), (6, 8), (4, 9)),
    },
    "PlateOfCookies.png.fmap": {
        "value": 0x20007800,
        "cells": ((6, 8), (7, 8)),
    },
    "Gnome1.png.fmap": {
        "value": 0x20006000,
        "cells": ((5, 10), (6, 10), (5, 11)),
    },
    "Gnome2.png.fmap": {
        "value": 0x20006000,
        "cells": ((4, 10), (5, 10), (6, 10)),
    },
    "Gnome3.png.fmap": {
        "value": 0x20006000,
        "cells": ((6, 11), (7, 11), (6, 12)),
    },
    "Gnome4.png.fmap": {
        "value": 0x20006000,
        "cells": ((4, 10), (5, 10), (6, 10)),
    },
    "Gnome5.png.fmap": {
        "value": 0x20006000,
        "cells": ((5, 10), (6, 10)),
    },
    "PenguinDecoration.png.fmap": {
        "value": 0x20006000,
        "cells": ((8, 7), (7, 8), (8, 8)),
    },
    "PolarBearDecoration.png.fmap": {
        "value": 0x20006000,
        "cells": ((6, 15), (7, 15), (8, 15)),
    },
    "ReindeerDecoration.png.fmap": {
        "value": 0x20006000,
        "cells": ((4, 13), (5, 13), (9, 13), (5, 14), (8, 14), (9, 14)),
    },
    "SantaGardenDecoration.png.fmap": {
        "value": 0x20006000,
        "cells": ((8, 15), (9, 15)),
    },
    "Snowman.png.fmap": {
        "value": 0x20006000,
        "cells": ((7, 12), (8, 12)),
    },
    "RedBow.png.fmap": {
        "value": 0x20006800,
        "cells": ((3, 10), (4, 10), (5, 10), (6, 10)),
    },
    "SantaWallDecoration.png.fmap": {
        "value": 0x20006800,
        "cells": ((4, 10), (5, 10)),
    },
    "StringOfLeaves.png.fmap": {
        "value": 0x20006800,
        "cells": ((9, 15), (10, 15)),
    },
    "StringOfLights.png.fmap": {
        "value": 0x20006800,
        "cells": ((9, 12), (10, 12)),
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
