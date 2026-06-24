"""Organize extracted holiday outfit frames by gender and body type.

This is an asset-layout step only. The stock and raw HolidayOutfits sources
remain intact; copies are added to the generated VillagerBodies tree for a
later compatibility resolver to consume.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from PIL import Image


# The raw mobile source names these holiday sets 51..54. Stock desktop body
# IDs end at 49, so map the four supplied outfits into the first safe additive
# runtime slots: 50..53.
SOURCE_TO_RUNTIME_BODY = {
    51: 50,
    52: 51,
    53: 52,
    54: 53,
}
GENDER_SOURCES = {
    "Female": ("Female Outfits", "FemaleBodies"),
    "Male": ("Male Outfits", "MaleBodies"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize VF2 holiday outfit frames by body type.")
    parser.add_argument(
        "--holiday-root",
        type=Path,
        required=True,
        help="HolidayOutfits directory containing Frames/Female Outfits and Frames/Male Outfits.",
    )
    parser.add_argument(
        "--villager-bodies",
        type=Path,
        default=Path("generated") / "VillagerBodies",
        help="Generated VillagerBodies root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    holiday_root = args.holiday_root.resolve()
    bodies_root = args.villager_bodies.resolve()
    copied: list[dict[str, object]] = []

    for gender, (source_folder, filename_prefix) in GENDER_SOURCES.items():
        source_root = holiday_root / "Frames" / source_folder
        if not source_root.is_dir():
            raise FileNotFoundError(f"Missing holiday outfit source folder: {source_root}")
        # Female source names use 051 while male source names use 0051. Both
        # identify the same runtime body value, so accept either padding width.
        pattern = re.compile(rf"^{re.escape(filename_prefix)}_(\d+)_(\d{{4}})\.png$")
        counts = {body_type: 0 for body_type in SOURCE_TO_RUNTIME_BODY}
        for source in sorted(source_root.glob("*.png")):
            match = pattern.match(source.name)
            if not match:
                continue
            body_type = int(match.group(1))
            frame_number = int(match.group(2))
            if body_type not in SOURCE_TO_RUNTIME_BODY:
                continue
            runtime_body_type = SOURCE_TO_RUNTIME_BODY[body_type]
            target = (
                bodies_root
                / gender
                / f"Body_{runtime_body_type:02d}"
                / f"{gender}_Body_{runtime_body_type:02d}_Holiday_Frame_{frame_number:04d}.png"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            counts[body_type] += 1
            copied.append(
                {
                    "gender": gender,
                    "source_set": body_type,
                    "body_value": runtime_body_type,
                    "frame_number": frame_number,
                    "source_file": source.relative_to(holiday_root).as_posix(),
                    "output_file": target.relative_to(bodies_root).as_posix(),
                    "size": Image.open(source).size,
                }
            )
        for body_type, count in counts.items():
            if count == 0:
                raise ValueError(f"No {gender} holiday frames found for body type {body_type}")

        # Clear the previous direct source-ID layout (Body_54) when rerunning
        # against a generated tree made before the 51..54 -> 50..53 mapping.
        stale = bodies_root / gender / "Body_54"
        if stale.is_dir():
            shutil.rmtree(stale)

    manifest_path = bodies_root / "holiday_outfits_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "format": 1,
                "description": "Holiday outfit frames organized by gender and runtime body value.",
                "source_to_runtime_body": SOURCE_TO_RUNTIME_BODY,
                "source": str(holiday_root),
                "runtime_status": "asset organization only; no body lookup patch applied",
                "frames": copied,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Organized {len(copied)} holiday outfit frames into {bodies_root}")


if __name__ == "__main__":
    main()
