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
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_offline_bundle_zip

ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, cwd=ROOT)




class UnreadableRelease(Exception):
    """A release archive that cannot be read as one.

    Its own type so the gate can quarantine rather than crash: the read
    happens after packaging, and an uncaught failure there is worse than a
    wrong answer.
    """


def settings_in_archive(archive: Path) -> set[str]:
    """The setting ids a packaged release actually offers.

    Read from the bundle manifest inside the ZIP rather than from the source
    tree, because the question is what this ARCHIVE ships -- which is the
    thing that regressed -- not what the exporter believed it was building.
    """
    try:
        with zipfile.ZipFile(archive) as bundle:
            manifests = sorted(
                (n for n in bundle.namelist() if n.endswith("manifest.json")),
                key=len,
            )
            if not manifests:
                raise UnreadableRelease(f"{archive.name} contains no manifest.json")
            raw = bundle.read(manifests[0]).decode("utf-8", "replace")
        data = json.loads(raw)
        # Schema extraction belongs INSIDE this block. Syntactically valid
        # JSON with the wrong top-level shape -- "[]", say -- parses fine and
        # then raises AttributeError on .get(), which would escape past the
        # catch below and unwind main() after packaging.
        rows = data.get("settings") or []
        offered = {
            row["id"]
            for row in rows
            if isinstance(row, dict) and row.get("id")
        }
    except UnreadableRelease:
        raise
    except Exception as failure:
        # Never let this raise out of the gate. It runs AFTER packaging, so an
        # exception unwinds main() without reaching quarantine() and leaves a
        # rejected archive sitting at its publishable filename -- the exact
        # accident this gate exists to prevent, reached through the gate.
        # A truncated file named exactly VF2-B181-Release.zip passes the
        # grammar filter, so the name check is not enough on its own.
        raise UnreadableRelease(f"{archive.name}: {failure}") from failure
    return offered


# The documented release filename: VF2-B<version>[-r<revision>]-Release.zip.
# Anything else beside it -- a scratch copy, a corrupt download, a hand-edited
# experiment -- is not a release and must not be treated as one.
RELEASE_NAME = re.compile(
    r"^VF2-B(?P<version>\d+(?:\.\d+)*)-Release(?:-r(?P<revision>\d+))?\.zip$"
)


def release_order(path: Path):
    """Sort key for a release filename, or None if it is not one.

    Ordering by NUMERIC COMPONENTS, never lexicographically. Sorted as text,
    "VF2-B99-Release.zip" lands after "VF2-B181-Release.zip", so gating B183
    with both retained would pick B99 as the baseline -- and a setting present
    in B181 but absent from B99 and B183 would never be reported. The gate
    would pass the exact feature loss it exists to block.
    """
    match = RELEASE_NAME.match(path.name)
    if match is None:
        return None
    version = tuple(int(part) for part in match.group("version").split("."))
    revision = int(match.group("revision") or 0)
    return (version, revision)


def earlier_releases(archive: Path) -> list[Path]:
    """Every retained release preceding this one, oldest first.

    ALL of them, not just the newest. Comparing against one predecessor lets
    a thin release launder a loss: with B183 retained beside B181, a B184
    that drops a B181-only setting and adds a replacement reports no loss
    against B183 and passes a cardinality floor, so the setting disappears
    while the gate prints success. A release must not lose a feature ANY
    earlier release shipped, so the baseline is their union.
    """
    this = release_order(archive)
    found = []
    for candidate in archive.parent.glob("*.zip"):
        if candidate.resolve() == archive.resolve():
            continue
        order = release_order(candidate)
        if order is None:
            continue
        if this is not None and order >= this:
            continue
        found.append((order, candidate))
    return [path for _, path in sorted(found)]


def previous_release_archive(archive: Path) -> Path | None:
    """The highest-versioned release preceding this one, or None.

    Compared against whatever shipped last rather than a pinned name, so the
    check keeps working as builds advance without anyone editing it.

    Candidates are restricted to the release grammar before anything is
    opened. A loose glob would accept a scratch ZIP sitting beside the real
    one, and reading it raises out of the gate AFTER packaging -- leaving the
    new archive at its publishable filename with no quarantine, which is the
    accident this whole gate exists to prevent.
    """
    this = release_order(archive)
    candidates = []
    for candidate in archive.parent.glob("*.zip"):
        if candidate.resolve() == archive.resolve():
            continue
        order = release_order(candidate)
        if order is None:
            continue
        if this is not None and order >= this:
            continue
        candidates.append((order, candidate))
    if not candidates:
        return None
    return max(candidates)[1]


# The number of settings a complete release offers. B181 shipped 35; B183
# shipped 23 because twelve overlay flags were never passed to the exporter.
#
# Checked as an ABSOLUTE FLOOR as well as against the baseline, because the
# two questions are different. "No fewer than the previous release" is only
# as good as the release it compares against: if baseline selection ever
# resolves to a thin build, thin quietly becomes the new bar and every
# release after it inherits the loss. An absolute number cannot drift that
# way.
#
# Raise this when a release genuinely adds a setting. It failing on a real
# addition is the intended cost -- a number nobody ever has to revisit is a
# number that is not measuring anything.
EXPECTED_SETTING_COUNT = 35


def short_of_expected(archive: Path) -> str | None:
    """Fewer settings than a complete release carries, or None."""
    offered = settings_in_archive(archive)
    if len(offered) >= EXPECTED_SETTING_COUNT:
        return None
    return (
        f"{archive.name} offers {len(offered)} settings; a complete release "
        f"carries {EXPECTED_SETTING_COUNT}. Twelve were missing from B183 "
        f"because the export ran without the per-feature overlay arguments."
    )


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
    if isinstance(previous, Path):
        previous = [previous]
    before = set()
    names = []
    for older in previous:
        before |= settings_in_archive(older)
        names.append(older.name)
    if not before:
        return None
    dropped = sorted(before - now)
    if not dropped:
        return None
    return (
        f"{archive.name} drops {len(dropped)} setting(s) present in "
        f"{', '.join(names)}, and adds {len(now - before)}:\n  "
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
    parser.add_argument(
        "--allow-missing-predecessor",
        action="store_true",
        help=(
            "Publish without comparing against a previous release. Only for "
            "a genuine first release: a missing predecessor is otherwise a "
            "retained-archive problem, not a reason to skip the check."
        ),
    )
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
    try:
        short = short_of_expected(archive)
    except UnreadableRelease as failure:
        return quarantine(archive, f"the packaged archive is unreadable: {failure}")
    if short is not None:
        return quarantine(archive, short)

    previous = earlier_releases(archive)
    if not previous:
        # A missing predecessor is not evidence of a first release. Both
        # /outputs/ and *.zip are gitignored, so a clean checkout -- or a
        # cleaned outputs/ -- supplies none, which would make every
        # established release indistinguishable from the genuine first one
        # and skip the check exactly when nobody is watching.
        #
        # Refuse instead, and make the bootstrap an explicit decision
        # somebody has to take rather than a default nobody notices.
        if not args.allow_missing_predecessor:
            return quarantine(
                archive,
                f"no predecessor release found beside {archive.name}, so the "
                "feature-regression check could not run. Retain the previous "
                "release ZIP next to this one, or pass "
                "--allow-missing-predecessor if this really is the first "
                "release.",
            )
        print("no predecessor, and the bootstrap override was given")
    else:
        try:
            lost = lost_settings(archive, previous)
        except UnreadableRelease as failure:
            return quarantine(
                archive,
                f"the predecessor could not be read, so the "
                f"feature-regression check could not run: {failure}",
            )
        if lost is not None:
            return quarantine(archive, lost)
        print(
            "no features lost against %d retained release(s): %s"
            % (len(previous), ", ".join(p.name for p in previous))
        )

    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"RELEASE GATE PASSED -- {archive} is ready to publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
