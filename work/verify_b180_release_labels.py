"""Check the shipped B180 executables for the label changes this release makes.

Reads the built binaries rather than the source. Every change verified here was
reported by the owner from live play, so the only evidence that counts is the
bytes that reach the player.

The labels live in the Behavior Patches variants, not `core`: `core` carries the
stock strings ("Playing pool", "Taking a nap") because those are base-game
strings, but the new label groups are added by the Behavior Patches patch.
Checking `core` and concluding the change is missing would be reading the wrong
artifact.
"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(r"C:\vf2w\vf2\outputs")
PREFIX = "VF2-B180-matrix-20260904"

# Must appear in any variant that enables Behavior Patches.
ADDED = [
    b"Playing ping-pong",
    b"Using the exercise bike",
    b"Doing high-intensity cycling",
]
# Removed on the owner's request; must appear in NO variant.
REMOVED = [b"Rallying back and forth"]

EXPECTED_VARIANTS = 32


def variants():
    """Only variants that have actually linked.

    A matrix build SEEDS each variant folder from the previous release before
    regenerating it, so a variant that has not linked yet still holds the
    previous release's files. Yielding those would check B179's assets and
    report its defects against B180.
    """
    for d in sorted(ROOT.glob(f"{PREFIX}-*")):
        if d.name.endswith("-logs"):
            continue
        exes = list(d.glob("*.exe"))
        if exes:
            yield d.name.replace(f"{PREFIX}-", ""), exes[0]


def main():
    rows = list(variants())
    if not rows:
        print("no linked variants yet")
        return 1

    behavior = [(n, p) for n, p in rows if "behavior" in n]
    problems = []
    digests = {}

    for name, exe in rows:
        data = exe.read_bytes()
        digests[name] = hashlib.sha256(data).hexdigest()

        for s in REMOVED:
            if s in data:
                problems.append(f"{name}: still contains removed label {s.decode()!r}")

        if "behavior" in name:
            missing = [s.decode() for s in ADDED if s not in data]
            if missing:
                problems.append(f"{name}: missing {missing}")
            else:
                print(f"  {name:44s} all {len(ADDED)} new labels present")
        else:
            print(f"  {name:44s} (no Behavior Patches; labels not expected)")

    print(f"\nlinked variants: {len(rows)}  (behavior-patches variants: {len(behavior)})")

    distinct = len(set(digests.values()))
    print(f"distinct SHA-256s: {distinct} of {len(digests)}")
    if distinct != len(digests):
        seen = {}
        for n, d in digests.items():
            seen.setdefault(d, []).append(n)
        for d, names in seen.items():
            if len(names) > 1:
                problems.append(f"identical binaries: {names}")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    # A partial matrix passing quietly is the dangerous direction at release
    # time, so it gets its own exit code rather than a clean 0.
    if len(rows) != EXPECTED_VARIANTS:
        print(
            f"\nPARTIAL MATRIX: {len(rows)} of {EXPECTED_VARIANTS} variants "
            "linked. Checks passed on those, but this is NOT a release-ready "
            "result -- unlinked variants still hold the previous release's "
            "files."
        )
        return 2

    print(f"\nall checks passed on all {EXPECTED_VARIANTS} variants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
