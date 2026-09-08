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
import re
import pathlib
import shutil
import struct
import sys
import zipfile
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _resolve_manifest_path(manifest_dir, value):
    """Mirror the installer's relative, contained source-path resolution."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("source path must be non-empty")
    raw = value.replace("\\", "/")
    if re.match(r"^[A-Za-z]:", raw) or raw.startswith("//"):
        raise ValueError("source path must be relative and contained")
    candidate = pathlib.PurePosixPath(raw)
    if candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        raise ValueError("source path must be relative and contained")
    root = pathlib.Path(manifest_dir).resolve()
    resolved = (root / pathlib.Path(*candidate.parts)).resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError("source path escapes manifest directory")
    return resolved


def _setting_is_ready(manifest, setting_id, row):
    metadata = {}
    for container_name in ("setting_readiness", "feature_readiness"):
        container = manifest.get(container_name)
        if isinstance(container, dict) and isinstance(container.get(setting_id), dict):
            metadata.update(container[setting_id])
    nested = row.get("readiness")
    if isinstance(nested, dict):
        metadata.update(nested)
    status = str(metadata.get("status", row.get("readiness_status", ""))).strip().lower()
    if status in {"stop", "stopped", "pending", "unlinked"}:
        return False
    return metadata.get("runtime_ready", True) is not False and metadata.get("linked", True) is not False


def _declared_settings(manifest):
    """Every setting the manifest declares, whatever its default.

    _default_enabled_settings answers "what does a default install turn on".
    That is the wrong question for a presence check: a file whose setting
    defaults to off is still installed by the manifest when the player selects
    it, and is still shipped in the bundle.
    """
    settings = manifest.get("settings")
    ids = set()
    if isinstance(settings, list):
        for entry in settings:
            if isinstance(entry, dict):
                value = entry.get("id") or entry.get("name")
                if value:
                    ids.add(value)
            elif isinstance(entry, str):
                ids.add(entry)
    elif isinstance(settings, dict):
        ids.update(settings)
    return ids


def _default_enabled_settings(manifest):
    raw_settings = manifest.get("settings", [])
    if isinstance(raw_settings, dict):
        rows = [
            {"id": setting_id, **(value if isinstance(value, dict) else {})}
            for setting_id, value in raw_settings.items()
        ]
    elif isinstance(raw_settings, list):
        rows = raw_settings
    else:
        rows = []
    enabled = set()
    for row in rows:
        if not isinstance(row, dict) or not row.get("default"):
            continue
        setting_id = str(row.get("id", "")).strip()
        if setting_id and _setting_is_ready(manifest, setting_id, row):
            enabled.add(setting_id)
    return enabled


def _record_requires(record):
    values = []
    for key in ("requires", "settings"):
        value = record.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif isinstance(value, str):
            values.extend(part.strip() for part in value.split(",") if part.strip())
        elif value is not None:
            return None
    for key in ("setting", "feature"):
        if record.get(key) is not None:
            values.append(record[key])
    normalized = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            return None
        value = value.strip()
        if value not in normalized:
            normalized.append(value)
    return normalized


def _normalize_declared_sha256(value):
    """Accept exactly what the patcher accepts, and nothing more.

    offline_vf2_patcher.normalize_sha256 strips surrounding whitespace and an
    optional "sha256:" prefix before matching 64 hex characters. Comparing a
    raw .lower() against the computed digest would reject a manifest the
    player's own patcher consumes happily -- a gate stricter than the thing it
    gates is a false alarm, not a safeguard.
    """
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text.startswith("sha256:"):
        text = text[7:]
    return text if re.fullmatch(r"[0-9a-f]{64}", text) else None


def _default_archive():
    """The newest release ZIP in outputs/, not a pinned release name.

    This was hardcoded to VF2-B180-Release.zip, so once B181 shipped the
    checker could not look at the release it was meant to gate -- it verified
    a superseded archive and reported success. A gate pinned to yesterday's
    artifact is worse than no gate, because it still prints a pass.
    """
    out = ROOT / "outputs"
    # Only the documented release grammar: VF2-B<version>-Release[-r<n>].zip.
    # A looser glob picks up scratch archives sitting beside the real one --
    # VF2-B181-Release-corrupt.zip ranks identically to VF2-B181-Release.zip
    # and sorts first, so the gate would verify the scratch file and pass.
    pattern = re.compile(r"^VF2-B\d+(?:\.\d+)*-Release(?:-r\d+)?\.zip$")
    zips = (
        sorted(p for p in out.glob("VF2-B*-Release*.zip") if pattern.match(p.name))
        if out.is_dir()
        else []
    )
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
# The two the widener dilates. The plain Invisible Lounger is not one of them
# and must keep the donor's unwidened footprint.
# The EObject value, and the drop-target counts each lounger must ship. The
# two spa maps are dilated into the donor's ring; the plain one is not.
OBJECT_CELL = 0x2000A800
WIDENED_DROP_CELLS = 33
PLAIN_DROP_CELLS = 11

WIDENED_LOUNGER_MAPS = (
    "InvisibleSpaLounger.png.fmap",
    "SpaLoungerStd.png.fmap",
)

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
        # RESOLVE AGAINST EVERY DECLARED SETTING, NOT ONLY THE DEFAULTS.
        #
        # "installed by the manifest" is a question about PRESENCE -- does the
        # bundle carry a record that puts this file on disk when its setting
        # is selected. Filtering to default-enabled settings answers a
        # different question, "is it installed in a default install", and then
        # reports the answer under the presence heading.
        #
        # Two of the three lounger maps require
        # invisible_furniture_visible_graphics, which is default: False. So a
        # correct bundle -- files present, anchors translated, geometry
        # carried -- was quarantined with "is not installed by the manifest".
        # Both B181 and B184 fail this way, and B181 is a release the owner
        # has been playing.
        #
        # The filter was added to stop a record whose setting is absent from
        # the bundle being counted, which is a real concern; declared_settings
        # keeps that, since a record requiring a setting the manifest never
        # declares is still skipped.
        declared_settings = _declared_settings(manifest)
        installed = {}
        for key in ("asset_patches", "post_asset_patches"):
            for record in manifest.get(key, []):
                requires = _record_requires(record)
                if not isinstance(requires, list) or not set(requires).issubset(declared_settings):
                    continue
                target_key = record.get("file_path")
                if key == "asset_patches":
                    target_key = record.get("output_file_path") or target_key
                if target_key:
                    installed[target_key] = record

    for name in LOUNGER_MAPS:
        target = f"Assets/{name}"
        record = installed.get(target)
        if record is None:
            problems.append(f"{target} is not installed by the manifest")
            continue
        # Resolve the payload file exactly where the installer looks.
        source_rel = record["source_path"]
        try:
            resolved = _resolve_manifest_path(manifest_path.parent, source_rel)
        except ValueError:
            resolved = None
        if resolved is None or not resolved.is_file():
            problems.append(
                f"{target}: manifest points at {source_rel}, which is not "
                "present at that path relative to the manifest"
            )
            continue
        maps[name] = resolved

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
        record = installed.get(f"Assets/{name}")
        if record is None:
            # A map present in the payload under its own name but with no
            # manifest record. The resolution loop above already recorded that
            # as a problem; subscripting here would raise KeyError and abort
            # before the collected problems are printed, turning a diagnosable
            # bundle into a stack trace.
            continue
        actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
        lounger_digests[name] = actual
        declared = _normalize_declared_sha256(record.get("source_sha256"))
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
    # THE TWO SPA LOUNGERS SHIP A WIDER DROP TARGET THAN THE PLAIN ONE.
    #
    # This required all three to be byte-identical, which held until the spa
    # hotspot widening: the owner reported the spa loungers were very hard to
    # drop a villager onto, so their maps -- and only theirs -- are dilated
    # into the donor's ring. The plain Invisible Lounger is deliberately left
    # alone, so identical digests are now the FAILURE rather than the
    # requirement.
    #
    # What still has to hold is that the two spa maps agree with EACH OTHER
    # and differ from the plain one. Both get the same treatment, so a
    # disagreement between them means one missed the widening.
    spa_digests = {n: d for n, d in lounger_digests.items()
                   if n in WIDENED_LOUNGER_MAPS}
    plain_digests = {n: d for n, d in lounger_digests.items()
                     if n not in WIDENED_LOUNGER_MAPS}
    if (len(spa_digests) == len(WIDENED_LOUNGER_MAPS)
            and len(set(spa_digests.values())) != 1):
        problems.append(
            f"the spa loungers install different maps, so one missed the "
            f"hotspot widening: {spa_digests}"
        )
    if (spa_digests and plain_digests
            and set(spa_digests.values()) == set(plain_digests.values())):
        problems.append(
            "the spa loungers are byte-identical to the plain lounger, so "
            "the hotspot widening did not reach this build"
        )
    # AND DECODE THE GEOMETRY. Digests alone cannot tell a 33-cell widening
    # from a 13-cell one: the empty-only rule that shipped before #258
    # produces spa maps that match EACH OTHER and DIFFER from the plain map,
    # satisfying both conditions above while the intended widening is absent.
    # Only counting the drop cells separates them.
    for name in WIDENED_LOUNGER_MAPS:
        resolved = maps.get(name)
        if resolved is None or not resolved.is_file():
            continue
        drop = cells(resolved).get(OBJECT_CELL, 0)
        # EQUALITY, NOT A LOWER BOUND. `drop < 33` catches an incomplete
        # widening and admits an over-widened one, which is the compounding
        # defect: seeding the dilation from the widened output instead of the
        # donor gives 38, and a second pass over that gives 62, then 92, 125,
        # 160 into a tracked asset directory. Both of those are numbers this
        # project actually produced today. The ring is deterministic, so the
        # exact figure is knowable and anything else is wrong.
        if drop != WIDENED_DROP_CELLS:
            problems.append(
                f"Assets/{name}: {drop} drop-target cells, expected exactly "
                f"{WIDENED_DROP_CELLS}. Fewer means the widening is "
                f"incomplete (the empty-only rule produces 13 and still "
                f"passes every digest check); more means it compounded, "
                f"which happens when the dilation is seeded from its own "
                f"output rather than from the donor"
            )
    for name in LOUNGER_MAPS:
        if name in WIDENED_LOUNGER_MAPS:
            continue
        resolved = maps.get(name)
        if resolved is None or not resolved.is_file():
            continue
        drop = cells(resolved).get(OBJECT_CELL, 0)
        if drop != PLAIN_DROP_CELLS:
            problems.append(
                f"Assets/{name}: {drop} drop-target cells, expected "
                f"{PLAIN_DROP_CELLS}; the plain lounger must keep the donor's "
                f"footprint -- the owner asked for the two spa loungers only"
            )
    if (spa_digests and plain_digests
            and set(spa_digests.values()) != set(plain_digests.values())):
        print("                   spa loungers share %s, plain lounger %s"
              % (sorted(set(spa_digests.values()))[0][:12],
                 sorted(set(plain_digests.values()))[0][:12]))

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
