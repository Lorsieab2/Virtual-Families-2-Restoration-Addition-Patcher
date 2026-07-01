from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATIONS = (
    Path(r"C:\Users\Owner\Downloads"),
    Path(r"C:\Users\Owner\OneDrive\Desktop\LDW Desktop Games!! And Other Stuff\Virtual Families 2 Codex Test Builds"),
)


def copy_build_folder(build_folder: Path, destination_root: Path) -> Path:
    build_folder = build_folder.resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / build_folder.name
    shutil.copytree(build_folder, destination, dirs_exist_ok=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mirror a completed VF2 build folder to the standard local test locations."
    )
    parser.add_argument("build_folder", help="Build folder to copy, usually under outputs/.")
    parser.add_argument(
        "--destination",
        action="append",
        type=Path,
        dest="destinations",
        help="Extra destination root. Defaults are Downloads and the OneDrive VF2 test builds folder.",
    )
    args = parser.parse_args()

    build_folder = Path(args.build_folder)
    if not build_folder.is_absolute():
        build_folder = ROOT / build_folder
    if not build_folder.is_dir():
        raise SystemExit(f"Build folder not found: {build_folder}")

    destinations = list(DEFAULT_DESTINATIONS)
    if args.destinations:
        destinations.extend(args.destinations)

    for destination_root in destinations:
        copied_to = copy_build_folder(build_folder, destination_root)
        print(copied_to)


if __name__ == "__main__":
    main()
