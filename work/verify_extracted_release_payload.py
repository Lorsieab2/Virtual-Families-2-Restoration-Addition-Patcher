"""Verify the EXTRACTED B180 payload, and refuse to pass on absent files.

Run against the unzipped archive, not the build tree. Every stage between the
matrix and a player's download can be the one that breaks.

The trap this guards against was found by dry-running the same logic on B179's
real bundle: the archive ships ONE shared payload rather than per-variant asset
copies, and B179 contains no Spa Lounger files at all because that item did not
exist yet. A checker that simply loops over "the lounger maps it finds" reports
zero problems when it finds zero maps -- vacuously true, and exactly the shape
of failure that ships a broken release. So every expected artifact class has a
minimum count that must be met before its contents are checked.

Counts come from B179's bundle, which is a real shipped archive: 32
executables, 100 hairstyle icons, 113 furniture PNGs.
"""
import hashlib
import json
import pathlib
import shutil
import struct
import sys
import zipfile
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "outputs" / "VF2-B180-Release.zip"
EXTRACT = ROOT / "outputs" / "_b180_extract"

ADDED = [
    b"Playing ping-pong",
    b"Using the exercise bike",
    b"Doing high-intensity cycling",
]
REMOVED = [b"Rallying back and forth"]

MOBILE_ANCHOR = 0x01B09800
DESKTOP_ANCHOR = 0x00009800

# B180 adds the two Spa Loungers; B179 shipped neither, so their presence is
# itself part of what this release must deliver.
LOUNGER_MAPS = (
    "InvisibleSpaLounger.png.fmap",
    "InvisibleLounger.png.fmap",
    "SpaLoungerStd.png.fmap",
)

# Minimums drawn from B179's real bundle. A payload that ships fewer is broken
# regardless of whether what it does ship passes.
MIN_EXECUTABLES = 32
MIN_ICONS = 100
MIN_FURNITURE_PNGS = 113


def cells(path):
    data = path.read_bytes()
    count = (len(data) - 0x30) // 4
    return Counter(
        struct.unpack_from("<I", data, 0x20 + 4 * i)[0] for i in range(count)
    )


def main():
    if not ARCHIVE.is_file():
        sys.exit(f"archive missing: {ARCHIVE}")

    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest().upper()
    print(f"archive: {ARCHIVE.name}  {ARCHIVE.stat().st_size:,} bytes")
    print(f"sha256 : {digest}")

    if EXTRACT.exists():
        shutil.rmtree(EXTRACT)
    EXTRACT.mkdir(parents=True)
    with zipfile.ZipFile(ARCHIVE) as z:
        z.extractall(EXTRACT)

    problems = []

    exes = sorted(EXTRACT.rglob("*.exe"))
    icons = sorted(EXTRACT.rglob("HairstyleIcons/*.png"))
    furniture = sorted(EXTRACT.rglob("Images/Furniture/*.png"))
    maps = {p.name: p for p in EXTRACT.rglob("*.fmap") if p.name in LOUNGER_MAPS}

    print(f"\nexecutables      : {len(exes)}")
    print(f"hairstyle icons  : {len(icons)}")
    print(f"furniture PNGs   : {len(furniture)}")
    # Counted after manifest resolution below, so report it there instead:
    # a raw payload count is misleading when identical files are collapsed.

    # Presence first. Checking contents of an empty set passes vacuously.
    if len(exes) < MIN_EXECUTABLES:
        problems.append(f"only {len(exes)} executables, expected {MIN_EXECUTABLES}")
    if len(icons) < MIN_ICONS:
        problems.append(f"only {len(icons)} hairstyle icons, expected {MIN_ICONS}")
    if len(furniture) < MIN_FURNITURE_PNGS:
        problems.append(
            f"only {len(furniture)} furniture PNGs, expected {MIN_FURNITURE_PNGS}"
        )
    # The lounger maps must be INSTALLED, which is not the same as being
    # present in the payload under their own names. The exporter collapses
    # byte-identical payload files and points several manifest records at one
    # canonical copy, so asking "is SpaLoungerStd.png.fmap in the payload"
    # gets the wrong answer -- and it became the wrong answer precisely
    # BECAUSE the desktop-safe map fix made all three lounger maps identical.
    # The manifest is the authority on what a player ends up with.
    manifest_path = next(EXTRACT.rglob("manifest.json"), None)
    if manifest_path is None:
        problems.append("manifest.json is not in the bundle")
        installed = {}
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        installed = {
            record["file_path"]: record
            for record in manifest.get("asset_patches", [])
            if "file_path" in record
        }

    for name in LOUNGER_MAPS:
        target = f"Assets/{name}"
        record = installed.get(target)
        if record is None:
            problems.append(f"{target} is not installed by the manifest")
            continue
        # Resolve the canonical payload file the record points at.
        candidates = [
            p for p in EXTRACT.rglob(pathlib.PurePosixPath(
                record["source_path"]).name)
            if p.as_posix().endswith(record["source_path"])
        ]
        if not candidates:
            problems.append(
                f"{target}: manifest points at {record['source_path']}, "
                "which is not in the payload"
            )
            continue
        maps[name] = candidates[0]

    print(
        f"lounger maps     : {len(maps)} of {len(LOUNGER_MAPS)} resolved "
        "through the manifest"
    )

    # Labels: the removed one must appear in no executable; the added ones must
    # appear in the behaviour-carrying builds. Every variant ships in one ZIP,
    # so at least one executable must carry each added label.
    for exe in exes:
        data = exe.read_bytes()
        for s in REMOVED:
            if s in data:
                problems.append(f"{exe.name}: still has removed label {s.decode()!r}")
    if exes:
        blob = b"".join(e.read_bytes() for e in exes)
        for s in ADDED:
            if s not in blob:
                problems.append(f"no executable carries {s.decode()!r}")

    for icon in icons:
        size = struct.unpack(">II", icon.read_bytes()[16:24])
        if size != (56, 56):
            problems.append(f"{icon.name}: {size[0]}x{size[1]}, expected 56x56")
            break

    for name, path in maps.items():
        c = cells(path)
        if MOBILE_ANCHOR in c:
            problems.append(f"{name}: carries the untranslated mobile anchor")
        if DESKTOP_ANCHOR not in c:
            problems.append(f"{name}: missing the desktop anchor")

    if problems:
        print("\nPROBLEMS IN THE EXTRACTED PAYLOAD:")
        for p in problems:
            print("  -", p)
        return 1

    print("\nextracted payload passes every check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
