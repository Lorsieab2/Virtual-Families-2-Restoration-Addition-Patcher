#!/usr/bin/env python3
"""Rebuild canonical Holiday Ornament collection art from tracked raw PNGs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

import patch_mobile_furniture_pack as patcher


DEFAULT_SOURCE_DIR = patcher.HOLIDAY_ORNAMENT_SUPPLIED_ART_DIR
DEFAULT_OUTPUT_DIR = patcher.HOLIDAY_ORNAMENT_PREEXTRACTED_ART_DIR
ASSET_MANIFEST_NAME = "asset-manifest.json"
FRAME_SOURCE_NAME = patcher.HOLIDAY_ORNAMENT_FRAME_SOURCE
DECORATIVE_SOURCE_NAME = "Collection_ChristmasOrnament_CandyCane.png"
BOTTLECAPS_BACKGROUND_SOURCE_NAME = "Collection_Bottlecaps_Background.png"
CANVAS_SIZE = (1024, 768)
FRAME_POSITION = (74, 4)
CANDY_CANE_POSITION = (848, 461)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> list[int]:
    with Image.open(path) as image:
        if image.format != "PNG":
            raise RuntimeError(f"Expected a PNG source: {path}")
        return list(image.size)


def source_metadata() -> dict[str, dict]:
    metadata: dict[str, dict] = {
        FRAME_SOURCE_NAME: {
            "role": "collection_frame",
            "position": list(FRAME_POSITION),
        },
        DECORATIVE_SOURCE_NAME: {
            "role": "collection_page_decoration",
            "position": list(CANDY_CANE_POSITION),
        },
        BOTTLECAPS_BACKGROUND_SOURCE_NAME: {
            "role": "collection_page_base",
            "position": [0, 0],
        },
    }
    for index, (runtime_name, source_name, placeholder_name) in enumerate(
        patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES
    ):
        collectable_id = hex(patcher.HOLIDAY_ORNAMENT_COLLECTABLE_START + index)
        position = list(patcher.HOLIDAY_ORNAMENT_COLLECTION_SLOT_POSITIONS[index])
        metadata[source_name] = {
            "role": "collected_icon",
            "collectable_id": collectable_id,
            "runtime_filename": runtime_name,
        }
        metadata[placeholder_name] = {
            "role": "placeholder",
            "collectable_id": collectable_id,
            "position": position,
        }
    if len(metadata) != 27:
        raise RuntimeError(
            f"Holiday Ornament raw-source contract expected 27 PNGs, got {len(metadata)}"
        )
    return metadata


def validate_raw_sources(source_dir: Path) -> list[dict]:
    metadata = source_metadata()
    missing = [name for name in metadata if not (source_dir / name).is_file()]
    if missing:
        raise RuntimeError(
            "Holiday Ornament raw-source set is incomplete: "
            + ", ".join(sorted(missing))
        )
    return [
        {
            "filename": name,
            **metadata[name],
            "sha256": sha256_file(source_dir / name),
            "dimensions": png_dimensions(source_dir / name),
        }
        for name in sorted(metadata)
    ]


def compose_collection_background(source_dir: Path, target: Path) -> list[dict]:
    with Image.open(source_dir / BOTTLECAPS_BACKGROUND_SOURCE_NAME) as opened:
        background = opened.convert("RGBA")
    if background.size != CANVAS_SIZE:
        raise RuntimeError(
            f"Holiday Ornament page base must be {CANVAS_SIZE}, got {background.size}"
        )
    with Image.open(source_dir / FRAME_SOURCE_NAME) as opened:
        frame = opened.convert("RGBA")
    with Image.open(source_dir / DECORATIVE_SOURCE_NAME) as opened:
        candy_cane = opened.convert("RGBA")
    background.alpha_composite(frame, FRAME_POSITION)
    background.alpha_composite(candy_cane, CANDY_CANE_POSITION)
    placeholder_records = []
    for index, (_runtime_name, _source_name, placeholder_name) in enumerate(
        patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES
    ):
        with Image.open(source_dir / placeholder_name) as opened:
            placeholder = opened.convert("RGBA")
        position = patcher.HOLIDAY_ORNAMENT_COLLECTION_SLOT_POSITIONS[index]
        # These coordinates are already absolute 1024x768 page coordinates.
        background.alpha_composite(placeholder, position)
        placeholder_records.append(
            {
                "filename": placeholder_name,
                "position": list(position),
                "dimensions": list(placeholder.size),
            }
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    background.save(target, format="PNG", optimize=False, compress_level=9)
    return [
        {
            "filename": BOTTLECAPS_BACKGROUND_SOURCE_NAME,
            "role": "base",
            "position": [0, 0],
            "dimensions": list(background.size),
        },
        {
            "filename": FRAME_SOURCE_NAME,
            "role": "frame",
            "position": list(FRAME_POSITION),
            "dimensions": list(frame.size),
        },
        {
            "filename": DECORATIVE_SOURCE_NAME,
            "role": "decoration",
            "position": list(CANDY_CANE_POSITION),
            "dimensions": list(candy_cane.size),
        },
        *[{**record, "role": "placeholder"} for record in placeholder_records],
    ]


def rebuild_collection_assets(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    source_records = validate_raw_sources(source_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime_records = []
    for index, (runtime_name, source_name, _placeholder_name) in enumerate(
        patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES
    ):
        source = source_dir / source_name
        target = output_dir / runtime_name
        shutil.copyfile(source, target)
        runtime_records.append(
            {
                "filename": runtime_name,
                "source_filename": source_name,
                "collectable_id": hex(
                    patcher.HOLIDAY_ORNAMENT_COLLECTABLE_START + index
                ),
                "sha256": sha256_file(target),
                "dimensions": png_dimensions(target),
                "copy_policy": "bit_for_bit_no_orientation_transform",
            }
        )

    background_name = patcher.HOLIDAY_ORNAMENT_BACKGROUND_FILENAME
    background_target = output_dir / background_name
    layers = compose_collection_background(source_dir, background_target)
    runtime_records.append(
        {
            "filename": background_name,
            "role": "collection_background",
            "source_base": BOTTLECAPS_BACKGROUND_SOURCE_NAME,
            "source_frame": FRAME_SOURCE_NAME,
            "source_decoration": DECORATIVE_SOURCE_NAME,
            "sha256": sha256_file(background_target),
            "dimensions": png_dimensions(background_target),
            "composition": {
                "operation": "rgba_alpha_composite",
                "canvas_size": list(CANVAS_SIZE),
                "coordinate_system": "absolute_full_canvas_top_left",
                "layers": layers,
                "orientation_transform": "none",
                "resize": "none",
            },
        }
    )

    manifest = {
        "schema_version": 3,
        "collection": "Holiday Ornaments",
        "provenance": {
            "origin": "User-supplied upright Holiday Ornaments PNG set",
            "workspace_source_root": "work/assets/holiday_collectibles",
            "generator": "work/rebuild_holiday_ornament_collection_assets.py",
            "icon_policy": (
                "Bit-for-bit copies of the supplied collected icons; no flip, "
                "rotation, crop, or resize."
            ),
            "background_policy": (
                "1024x768 Collection_Bottlecaps_Background.png base, upright "
                "Collection_ChristmasOrnament_Frame.png at (74, 4), upright "
                "Collection_ChristmasOrnament_CandyCane.png at (848, 461), and "
                "the 12 upright placeholders at their absolute page positions; "
                "no flip, rotation, crop, or resize."
            ),
        },
        "source_assets": source_records,
        "assets": runtime_records,
    }
    (output_dir / ASSET_MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild canonical upright Holiday Ornament runtime assets."
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    manifest = rebuild_collection_assets(args.source_dir, args.output_dir)
    print(
        f"Rebuilt {len(manifest['assets'])} runtime assets from "
        f"{len(manifest['source_assets'])} tracked source PNGs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
