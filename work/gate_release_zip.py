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
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_offline_bundle_zip

ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, cwd=ROOT)




def settings_in_archive(archive: Path) -> set[str]:
    """The setting ids a packaged release actually offers.

    Read from the bundle manifest inside the ZIP rather than from the source
    tree, because the question is what this ARCHIVE ships -- which is the
    thing that regressed -- not what the exporter believed it was building.
    """
    with zipfile.ZipFile(archive) as bundle:
        manifests = sorted(
            (n for n in bundle.namelist() if n.endswith("manifest.json")),
            key=len,
        )
        if not manifests:
            return set()
        data = json.loads(bundle.read(manifests[0]).decode("utf-8", "replace"))
    return {
        row["id"]
        for row in (data.get("settings") or [])
        if isinstance(row, dict) and row.get("id")
    }


def previous_release_archive(archive: Path) -> Path | None:
    """The most recent packaged release other than this one, or None.

    Compared against whatever was published last rather than a pinned name,
    so the check keeps working as builds advance without anyone editing it.
    """
    others = [
        p
        for p in sorted(archive.parent.glob("VF2-B*-Release*.zip"))
        if p.resolve() != archive.resolve() and not p.name.endswith(".REJECTED")
    ]
    return others[-1] if others else None


def lost_settings(archive: Path, previous: Path) -> str | None:
    """Name the settings this release drops, or None if it drops none.

    B183 shipped 23 settings where B181 shipped 35 -- twelve features gone,
    none added, 221 asset patches missing -- and the export reported success
    throughout. default_settings() filters SOURCE_BACKED_OPTIONAL_SETTINGS
    down to whatever the run could resolve inputs for, so an export that
    cannot find those assets drops them SILENTLY and still packages.
    Nothing compared the output against the previous release, so the first
    thing that noticed was a person opening the archive.

    Reported as NAMES, not a count: "23 settings, expected 35" tells someone
    a release is short, and the list tells them which build inputs were
    missing.
    """
    now = settings_in_archive(archive)
    before = settings_in_archive(previous)
    if not before:
        return None
    dropped = sorted(before - now)
    if not dropped:
        return None
    return (
        f"{archive.name} drops {len(dropped)} setting(s) present in "
        f"{previous.name}, and adds {len(now - before)}:\n  "
        + "\n  ".join(dropped)
    )


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

    # The extracted-payload checks belong INSIDE the gate, not beside it.
    # They were written, merged and correct, and nothing ever called them:
    # a repo-wide search found this verifier's only entry point was its own
    # __main__, so the gate could print RELEASE GATE PASSED without a single
    # payload assertion having run. A safeguard that depends on somebody
    # remembering a second command is a safeguard that is off by default,
    # which is the same shape as the decal hook that was written correctly
    # and never invoked.
    #
    # Run against the ARCHIVE the gate just packaged and authenticated, so
    # what is verified is what would be published rather than whatever the
    # verifier's own default resolution happens to pick up.
    print("verifying the extracted payload")
    payload = run(
        [
            sys.executable,
            "work/verify_extracted_release_payload.py",
            str(archive),
        ]
    )
    if payload.returncode != 0:
        return quarantine(archive, payload.stdout + payload.stderr)
    print(payload.stdout.strip())

    # A release must not be a strict subset of the one before it. The owner's
    # standing rule is that every release uses the previous one as its base
    # and carries every piece of its content; a build that silently ships
    # fewer features than its predecessor breaks that, and nothing here
    # noticed until a person opened the archive.
    previous = previous_release_archive(archive)
    if previous is not None:
        lost = lost_settings(archive, previous)
        if lost is not None:
            return quarantine(archive, lost)
        print(f"no features lost against {previous.name}")

    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"RELEASE GATE PASSED -- {archive} is ready to publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
