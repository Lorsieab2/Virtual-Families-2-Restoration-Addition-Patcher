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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_offline_bundle_zip

ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, cwd=ROOT)




def quarantine(archive: Path, reason: str) -> int:
    """Move a rejected archive aside so it cannot be published by mistake.

    Every gate failure has to do this, not just the verifier's.  A check that
    reports a bad bundle but leaves it sitting at the normal publishable
    filename is a check a later manual upload step walks straight past, which
    is the exact accident the gate exists to prevent.
    """
    rejected = archive.parent / (archive.name + ".REJECTED")
    print(reason, file=sys.stderr)
    try:
        archive.replace(rejected)
    except OSError as exc:
        # Never claim a move that did not happen.  Saying "moved to
        # VF2-B177-Release.zip" while the rejected bundle sits at exactly that
        # publishable name is worse than saying nothing, because it reads as
        # the fail-safe having worked.
        print(
            f"RELEASE GATE FAILED -- and the archive could NOT be quarantined: "
            f"{exc}",
            file=sys.stderr,
        )
        print(
            f"WARNING: {archive} REMAINS AT ITS PUBLISHABLE FILENAME. Move or "
            "delete it by hand before uploading anything.",
            file=sys.stderr,
        )
        return 1
    print(
        f"RELEASE GATE FAILED -- archive moved to {rejected.name} so it "
        "cannot be uploaded by mistake",
        file=sys.stderr,
    )
    return 1


def incomplete_variant_coverage(shipped_variants: object) -> str | None:
    """Reject a release that does not cover every combination the matrix builds.

    verify_offline_bundle_zip deliberately checks an archive against its own
    release's contract, so retained older ZIPs still verify.  That makes "did
    we build all of them?" a question only the gate can ask, at the moment a
    release is made.  Without this, a matrix run that stopped short -- B174.2
    stopped at 14 of 19 -- produces a short bundle that otherwise gates clean.
    """
    expected = len(verify_offline_bundle_zip.EXECUTABLE_VARIANT_REQUIREMENTS)
    if shipped_variants == expected:
        return None
    return (
        f"release ships {shipped_variants} executable variants but the matrix "
        f"defines {expected}; every combination must be built before a release "
        "is gated"
    )


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

    # Resolved before any subprocess runs: the children run with cwd=ROOT, so
    # a caller-relative path validated here would mean a different directory
    # once packaging starts.
    bundle = (
        Path(args.bundle_dir).resolve()
        if args.bundle_dir
        else ROOT / "outputs" / f"VF2-{args.release}-Release"
    )
    # Appended rather than with_suffix(): point releases are real, and
    # Path("VF2-B155.5-Release").with_suffix(".zip") yields "VF2-B155.zip"
    # because it treats ".5-Release" as the suffix.
    archive = (
        Path(args.zip).resolve()
        if args.zip
        else bundle.parent / (bundle.name + ".zip")
    )
    identities = (
        Path(args.identities).resolve()
        if args.identities
        else ROOT / "data" / "vf2" / f"release-identities-{args.release}.json"
    )

    if not bundle.is_dir():
        print(f"bundle directory not found: {bundle}", file=sys.stderr)
        return 1
    # The verifier requires the ZIP's root folder to match the archive stem, so
    # catch the mismatch here rather than after packaging 179 MB.
    if archive.name != bundle.name + ".zip":
        print(
            f"archive {archive.name!r} must be named {bundle.name + '.zip'!r} "
            "to match the bundle directory, or the ZIP root will not verify",
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
        return quarantine(archive, verified.stdout + verified.stderr)

    summary = json.loads(verified.stdout)
    # A new release must cover every combination the matrix can build.  The
    # verifier deliberately checks an archive against its own release's
    # contract so retained older ZIPs still verify, which means "did we build
    # all of them?" has to be asserted here, at the point a release is made.
    # Without this, a matrix run that silently stopped short -- B174.2 stopped
    # at 14 of 19 -- would produce a short bundle that gates clean.
    incomplete = incomplete_variant_coverage(summary.get("executable_variants"))
    if incomplete is not None:
        return quarantine(archive, incomplete)

    if not summary.get("variant_identities_authenticated"):
        return quarantine(archive, "gate did not authenticate variant identities")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"RELEASE GATE PASSED -- {archive} is ready to publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
