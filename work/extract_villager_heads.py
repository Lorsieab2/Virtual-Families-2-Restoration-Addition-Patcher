"""Extract stock VF2 villager head spritesheets into independent PNG frames.

The stock head sheets contain 50 zero-based head rows. ``heads00`` is the
adult bank and ``heads10`` is the elderly bank. The original sheets are only
read; all output is written to a generated directory with a source manifest.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


CELL_WIDTH = 28
CELL_HEIGHT = 56
HEAD_COUNT = 50
FRAME_COUNT = 24
GENDERS = ("female", "male")
AGE_BANKS = {
    "Adult": "00",
    "Elderly": "10",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract stock VF2 villager head frames without changing source sheets."
    )
    parser.add_argument(
        "--input-images",
        type=Path,
        required=True,
        help="Directory containing male/female heads00 and heads10 PNGs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated") / "VillagerHeads",
        help="Generated root for VillagerHeads (default: generated/VillagerHeads).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the destination before extracting.",
    )
    return parser.parse_args()


def validate_sheet(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    expected = (FRAME_COUNT * CELL_WIDTH, HEAD_COUNT * CELL_HEIGHT)
    if image.size != expected:
        raise ValueError(f"{path}: expected {expected[0]}x{expected[1]}, got {image.size}")
    return image


def extract_gender(input_images: Path, output: Path, gender: str) -> list[dict[str, object]]:
    gender_name = gender.title()
    regions: list[dict[str, object]] = []
    for age_bank, suffix in AGE_BANKS.items():
        source = input_images / f"{gender}_heads{suffix}.png"
        if not source.is_file():
            raise FileNotFoundError(f"Missing stock head sheet: {source}")
        image = validate_sheet(source)
        for head_value in range(HEAD_COUNT):
            head_root = output / gender_name / age_bank / f"Head_{head_value:02d}"
            for frame_index in range(FRAME_COUNT):
                left = frame_index * CELL_WIDTH
                top = head_value * CELL_HEIGHT
                target = head_root / (
                    f"{gender_name}_{age_bank}_Head_{head_value:02d}_Frame_{frame_index:02d}.png"
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                image.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT)).save(target)
                regions.append(
                    {
                        "gender": gender_name,
                        "age_bank": age_bank,
                        "head_value": head_value,
                        "frame_index": frame_index,
                        "source_file": source.name,
                        "source_region": {
                            "left": left,
                            "top": top,
                            "width": CELL_WIDTH,
                            "height": CELL_HEIGHT,
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
        "description": "Extracted stock VF2 villager head frame regions.",
        "cell_size": {"width": CELL_WIDTH, "height": CELL_HEIGHT},
        "head_values": {"first": 0, "last": HEAD_COUNT - 1, "row_matches_head_value": True},
        "frame_count": FRAME_COUNT,
        "age_banks": AGE_BANKS,
        "inputs": str(input_images),
        "regions": regions,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(regions)} frames to {output}")


if __name__ == "__main__":
    main()
