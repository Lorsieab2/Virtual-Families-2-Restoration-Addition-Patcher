from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def package(source_dir: Path, archive: Path, compresslevel: int = 9) -> int:
    source_dir = source_dir.resolve()
    archive = archive.resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(source_dir)
    archive.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=compresslevel,
        allowZip64=True,
    ) as output:
        for path in files:
            relative = path.relative_to(source_dir).as_posix()
            output.write(path, f"{source_dir.name}/{relative}")
    return len(files)


def main():
    parser = argparse.ArgumentParser(
        description="Create a compact patcher ZIP with portable forward-slash file entries."
    )
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--compresslevel", type=int, default=9, choices=range(0, 10))
    args = parser.parse_args()
    count = package(args.source_dir, args.archive, args.compresslevel)
    print(f"files={count}")
    print(f"bytes={args.archive.stat().st_size}")
    print(f"sha256={sha256_file(args.archive)}")


if __name__ == "__main__":
    main()
