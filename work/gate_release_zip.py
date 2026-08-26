"""Package a release ZIP and refuse to hand one over that fails the gate.

The pieces already existed -- package_patcher_zip.py builds the archive and
verify_offline_bundle_zip.py checks it -- but nothing connected them, so
cutting a release meant remembering to run the verifier afterwards with the
right identities file. B173 and B174 both went out without it, which is the
same failure mode as a guard nobody runs.

This runs packaging and the strict verification as one step. If verification
fails the ZIP is moved aside rather than left sitting where a release script
would pick it up, because a rejected archive that stays at the expected path
is the one most likely to get uploaded anyway.

Identities must be supplied and must authenticate: without them the executable
check only proves the bundle agrees with itself, since the exporter writes
both the payload and the hashes describing it.

Usage:
    python work/gate_release_zip.py --release B175
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, help="Release name, e.g. B175")
    parser.add_argument(
        "--bundle-dir",
        help="Exported bundle directory (default outputs/VF2-<release>-Release)",
    )
    parser.add_argument("--zip", help="Output archive (default outputs/<bundle-dir>.zip)")
    parser.add_argument(
        "--identities",
        help="Variant identities JSON (default data/vf2/release-identities-<release>.json)",
    )
    args = parser.parse_args()

    bundle = Path(args.bundle_dir) if args.bundle_dir else (
        ROOT / "outputs" / f"VF2-{args.release}-Release"
    )
    archive = Path(args.zip) if args.zip else bundle.with_suffix(".zip")
    identities = Path(args.identities) if args.identities else (
        ROOT / "data" / "vf2" / f"release-identities-{args.release}.json"
    )

    if not bundle.is_dir():
        print(f"bundle directory not found: {bundle}", file=sys.stderr)
        return 1
    # The verifier requires the ZIP's root folder to match the archive stem, so
    # catch the mismatch here rather than after packaging 179 MB.
    if bundle.name != archive.stem:
        print(
            f"bundle directory name {bundle.name!r} must match archive stem "
            f"{archive.stem!r}, or the ZIP root will not verify",
            file=sys.stderr,
        )
        return 1
    if not identities.is_file():
        print(
            f"variant identities not found: {identities}\n"
            "Run work/export_release_bundle.py (which now emits it) or "
            "work/export_release_variant_identities.py.",
            file=sys.stderr,
        )
        return 1

    print(f"packaging {bundle.name} -> {archive.name}")
    packaged = run(
        [sys.executable, "work/package_patcher_zip.py", str(bundle), str(archive)]
    )
    if packaged.returncode != 0:
        print(packaged.stdout + packaged.stderr, file=sys.stderr)
        return 1
    print(packaged.stdout.strip())

    print("verifying with independent variant identities")
    verified = run(
        [
            sys.executable,
            "work/verify_offline_bundle_zip.py",
            str(archive),
            "--identities",
            str(identities),
            "--require-identities",
        ]
    )
    if verified.returncode != 0:
        rejected = archive.with_suffix(".zip.REJECTED")
        try:
            archive.replace(rejected)
        except OSError:
            rejected = archive
        print(verified.stdout + verified.stderr, file=sys.stderr)
        print(
            f"RELEASE GATE FAILED -- archive moved to {rejected.name} so it "
            "cannot be uploaded by mistake",
            file=sys.stderr,
        )
        return 1

    summary = json.loads(verified.stdout)
    if not summary.get("variant_identities_authenticated"):
        print("gate did not authenticate variant identities", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"RELEASE GATE PASSED -- {archive} is ready to publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
