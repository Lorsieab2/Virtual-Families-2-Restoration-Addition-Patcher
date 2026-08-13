"""Extract stock villager body spritesheets into per-body PNG frames.

Rows map directly to the in-game body value: row 0 is body 0, row 49 is
body 49. The source sheets remain read-only inputs; this tool only writes
generated assets and a manifest describing every source region.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


CELL_SIZE = 91
BODY_COUNT = 50
SHEETS = {
    "bodies": 32,
    "actions": 15,
    "sit": 9,
}
GENDERS = ("female", "male")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract stock VF2 villager body frames without changing source sheets."
    )
    parser.add_argument(
        "--input-images",
        type=Path,
        required=True,
        help="Directory containing male/female bodies00, actions00, and sit00 PNGs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated") / "VillagerBodies",
        help="Generated root for VillagerBodies (default: generated/VillagerBodies).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the destination before extracting.",
    )
    return parser.parse_args()


def source_name(gender: str, sheet: str) -> str:
    return f"{gender}_{sheet}00.png"


def validate_sheet(path: Path, column_count: int) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    expected = (column_count * CELL_SIZE, BODY_COUNT * CELL_SIZE)
    if image.size != expected:
        raise ValueError(f"{path}: expected {expected[0]}x{expected[1]}, got {image.size}")
    return image


def extract_gender(input_images: Path, output: Path, gender: str) -> list[dict[str, object]]:
    gender_name = gender.title()
    gender_root = output / gender_name
    regions: list[dict[str, object]] = []

    for sheet, column_count in SHEETS.items():
        source = input_images / source_name(gender, sheet)
        if not source.is_file():
            raise FileNotFoundError(f"Missing stock spritesheet: {source}")
        image = validate_sheet(source, column_count)

        for body_value in range(BODY_COUNT):
            body_root = gender_root / f"Body_{body_value:02d}"
            for frame_index in range(column_count):
                left = frame_index * CELL_SIZE
                top = body_value * CELL_SIZE
                target = body_root / (
                    f"{gender_name}_Body_{body_value:02d}_{sheet}_Frame_{frame_index:02d}.png"
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                image.crop((left, top, left + CELL_SIZE, top + CELL_SIZE)).save(target)
                regions.append(
                    {
                        "gender": gender_name,
                        "body_value": body_value,
                        "sheet": sheet,
                        "frame_index": frame_index,
                        "source_file": source.name,
                        "source_region": {
                            "left": left,
                            "top": top,
                            "width": CELL_SIZE,
                            "height": CELL_SIZE,
                        },
                        "output_file": target.relative_to(output).as_posix(),
                    }
                )
    return regions


def main() -> None:
    args = parse_args()
    input_images = args.input_images.resolve()
    output = args.output.resolve()
    if args.clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    regions: list[dict[str, object]] = []
    for gender in GENDERS:
        regions.extend(extract_gender(input_images, output, gender))

    manifest = {
        "format": 1,
        "description": "Extracted stock VF2 villager body/action/sit frame regions.",
        "cell_size": {"width": CELL_SIZE, "height": CELL_SIZE},
        "body_values": {"first": 0, "last": BODY_COUNT - 1, "row_matches_body_value": True},
        "frame_counts": SHEETS,
        "inputs": str(input_images),
        "regions": regions,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(regions)} frames to {output}")


if __name__ == "__main__":
    main()
