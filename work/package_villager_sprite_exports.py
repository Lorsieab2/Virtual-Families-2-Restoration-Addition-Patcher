"""Copy generated villager sprite extractions into a packaged game build.

The exports are reference/editing assets only. They are placed under Assets so
they do not replace the stock Images sheets or alter the game's runtime lookup.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


EXPORT_NAMES = ("VillagerBodies", "VillagerHeads")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package generated villager sprite exports into a build.")
    parser.add_argument("--generated-root", type=Path, default=Path("generated"))
    parser.add_argument("--build", type=Path, required=True, help="Completed game build directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_root = args.generated_root.resolve()
    assets = args.build.resolve() / "Assets"
    assets.mkdir(parents=True, exist_ok=True)

    for name in EXPORT_NAMES:
        source = generated_root / name
        if not source.is_dir():
            raise FileNotFoundError(f"Missing generated export: {source}")
        destination = assets / name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
        print(f"Packaged {source} -> {destination}")


if __name__ == "__main__":
    main()
