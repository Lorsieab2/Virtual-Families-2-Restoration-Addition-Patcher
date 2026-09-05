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
def _default_archive():
    """The newest release ZIP in outputs/, not a pinned release name.

    This was hardcoded to VF2-B180-Release.zip, so once B181 shipped the
    checker could not look at the release it was meant to gate -- it verified
    a superseded archive and reported success. A gate pinned to yesterday's
    artifact is worse than no gate, because it still prints a pass.
    """
    out = ROOT / "outputs"
    zips = sorted(out.glob("VF2-B*-Release*.zip")) if out.is_dir() else []
    if not zips:
        return out / "VF2-B180-Release.zip"

    def rank(path):
        stem = path.stem
        rel = stem.split("-")[1][1:] if "-" in stem else "0"
        parts = tuple(int(x) for x in rel.split(".") if x.isdigit())
        rev = stem.rsplit("-r", 1)[1] if "-r" in stem else "0"
        return (parts, int(rev) if rev.isdigit() else 0)

    return max(zips, key=rank)


ARCHIVE = (
    pathlib.Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else _default_archive()
)
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
    # gets the wrong answer. This is a LATENT defect, not one the
    # desktop-safe map fix introduced: B179's manifest already had 220 source
    # files serving more than one target each. The by-name check was always
    # wrong; it simply had no lounger to be wrong about until that fix made
    # the three maps identical. The manifest is the authority on what a
    # player ends up with.
    manifest_path = next(EXTRACT.rglob("manifest.json"), None)
    if manifest_path is None:
        problems.append("manifest.json is not in the bundle")
        installed = {}
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Read BOTH record lists. post_asset_patches is a separate list that
        # runs after the asset pass, and a target sitting there would be
        # reported as "not installed" by a resolver that only reads
        # asset_patches -- a false alarm on a correct bundle, which is the
        # same class of mistake as the by-name check this replaced.
        installed = {}
        for key in ("asset_patches", "post_asset_patches"):
            for record in manifest.get(key, []):
                if "file_path" in record:
                    installed.setdefault(record["file_path"], record)

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

    # Resolving proves they install; equal digests prove they install the SAME
    # map. That is the actual claim the desktop-safe fix makes, and without it
    # three loungers could each resolve to a different file and still pass.
    # Hash the RESOLVED FILE, never the declared digest. A record's
    # source_sha256 is written by the same exporter that wrote the payload, so
    # comparing declared values to each other only proves the manifest agrees
    # with itself. Worse, `.get(..., "")` maps every OMITTED digest to the same
    # empty string, so three records that declare nothing would compare equal
    # and pass -- while the real patcher rejects each asset because the payload
    # does not match the manifest. Digesting the bytes on disk answers the
    # question the manifest cannot be trusted to answer about itself.
    lounger_digests = {}
    for name in LOUNGER_MAPS:
        resolved = maps.get(name)
        if resolved is None:
            continue
        actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
        lounger_digests[name] = actual
        declared = installed[f"Assets/{name}"].get("source_sha256")
        if not declared:
            problems.append(
                f"Assets/{name}: the manifest record declares no source_sha256, "
                "so the patcher cannot verify what it installs"
            )
        elif declared.lower() != actual.lower():
            problems.append(
                f"Assets/{name}: payload digest {actual[:12]} does not match "
                f"the manifest's declared {declared[:12]}"
            )
    if len(lounger_digests) == len(LOUNGER_MAPS):
        distinct = set(lounger_digests.values())
        if len(distinct) != 1:
            problems.append(
                f"loungers install different maps: {lounger_digests}"
            )
        else:
            print(f"                   all three share {distinct.pop()[:12]}")

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
