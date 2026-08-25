"""Record what each executable variant of a release actually compiled to.

The offline-bundle verifier needs an identity source it does not get from the
thing it is verifying. `manifest.json` cannot serve: the exporter writes both
the payload and the hashes describing it, so checking one against the other
only proves the bundle agrees with itself. If the exporter ever selected the
wrong-but-valid executable for a feature combination, it would record that
executable's hash too and the bundle would verify clean.

This reads the matrix build outputs instead -- produced by build_matrix.ps1 and
the generator, not by the bundle exporter -- and writes the mapping from
feature combination to compiled identity. Feeding that to the verifier as
`--identities` turns a self-consistency check back into an independent gate.

The feature combination for a variant is derived from the toggle matrix rather
than from its directory name: `holiday_ornaments` is advertised to the patcher
as `holiday_ornaments_collection`, `ai_generated_bathroom2` is not a separate
executable dimension, and every variant implies `core_executable`. That
derivation reproduces all 19 combinations a release bundle declares.

Usage:
    python work/export_release_variant_identities.py \
        --matrix-prefix VF2-B174-matrix-20260825 \
        --release B174
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOGGLES = ROOT / "data" / "vf2" / "build-matrix-toggles.json"

# Toggle names as the build matrix spells them vs as a bundle advertises them.
REQUIRES_RENAMES = {"holiday_ornaments": "holiday_ornaments_collection"}
# Present in the toggle matrix but not a separate executable dimension.
NON_EXECUTABLE_TOGGLES = {"ai_generated_bathroom2"}


def variant_requirements() -> dict[str, frozenset[str]]:
    variants = json.loads(TOGGLES.read_text(encoding="utf-8-sig"))["variants"]
    derived: dict[str, frozenset[str]] = {}
    for variant in variants:
        requires = {"core_executable"}
        for key, enabled in variant.items():
            if key == "name" or not isinstance(enabled, bool) or not enabled:
                continue
            if key in NON_EXECUTABLE_TOGGLES:
                continue
            requires.add(REQUIRES_RENAMES.get(key, key))
        derived[variant["name"]] = frozenset(requires)
    return derived


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(matrix_prefix: str) -> list[dict]:
    requirements = variant_requirements()
    outputs = ROOT / "outputs"
    records = []
    problems = []
    for name, requires in sorted(requirements.items()):
        directory = outputs / f"{matrix_prefix}-{name}"
        if not directory.is_dir():
            problems.append(f"missing matrix output for variant {name}: {directory}")
            continue
        executables = sorted(directory.glob("*.exe"))
        if len(executables) != 1:
            problems.append(
                f"variant {name} has {len(executables)} executables, expected exactly 1"
            )
            continue
        executable = executables[0]
        records.append(
            {
                "variant": name,
                "requires": sorted(requires),
                "sha256": sha256_of(executable),
                "size": executable.stat().st_size,
            }
        )
    if problems:
        raise SystemExit(
            "cannot record variant identities:\n- " + "\n- ".join(problems)
        )

    # Two combinations compiling to one binary means the matrix is wrong, and
    # recording it would bless that defect as the expected identity.
    by_hash: dict[str, list[str]] = {}
    for record in records:
        by_hash.setdefault(record["sha256"], []).append(record["variant"])
    collisions = [names for names in by_hash.values() if len(names) > 1]
    if collisions:
        raise SystemExit(
            "refusing to record identities: distinct variants compiled to one "
            "binary: " + "; ".join(" == ".join(names) for names in collisions)
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-prefix", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    records = collect(args.matrix_prefix)
    payload = {
        "note": (
            "Compiled identity of every executable variant, read from the "
            "matrix build outputs rather than from the bundle that is being "
            "verified. Feed to verify_offline_bundle_zip.py --identities."
        ),
        "release": args.release,
        "matrix_prefix": args.matrix_prefix,
        "variants": records,
    }
    out = Path(args.out) if args.out else (
        ROOT / "data" / "vf2" / f"release-identities-{args.release}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"recorded {len(records)} variant identities -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
