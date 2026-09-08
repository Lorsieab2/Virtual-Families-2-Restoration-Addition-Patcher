#!/usr/bin/env python3
"""The loungers' placement maps must be desktop-safe in the BUILT assets.

test_borrowed_fmaps_are_desktop_safe.py checks the selection logic against the
source tree. This checks what actually reached a build, because the defect it
guards against shipped in B179 despite the source naming the right donor: the
patch installed the desktop-safe map over each donor's OWN name, and a
borrower's copy is written under the BORROWER's name, which that pass never
visited.

What B179 shipped, and what B180 must not:

    Chaise_brown.png.fmap          no non-zero cells        (desktop-safe)
    InvisibleSpaLounger.png.fmap   0x01B00000 x111, 0x01B00001 x31,
                                   0x01B09800 x1            (RAW MOBILE)

The operative cell is the peep-slot anchor. The behavior ledger records that it
must be translated from mobile 0x01B09800 to desktop 0x00009800, and that
without the translated anchor the desktop FindPeepSlot path rejects every
chair -- which is exactly the reported symptom of a villager lying in the wrong
position or changing behaviour the moment it sat down.

Skips when no finished build is present, so a clean checkout is not red.
"""
import hashlib
import os
import re
import struct
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"

DESKTOP_ANCHOR = 0x00009800
MOBILE_ANCHOR = 0x01B09800

# The desktop-safe map for the donor these all borrow. Comparing against the
# real thing beats inventing a numeric threshold: a first attempt treated
# anything >= 0x01000000 as a mobile marker and flagged 0x2000A800, which is a
# perfectly ordinary DESKTOP cell present in the safe map itself.
PC_FMAP_DONOR = (
    ROOT / "patcher_assets" / "optional_patches" /
    "mobile_furniture_behaviors" / "pc_fmaps" / "Chaise_brown.png.fmap"
)

# The mobile-only footprint markers the behavior ledger forbids installing into
# the desktop content map. These are the cells B179 actually shipped.
FORBIDDEN_MOBILE_CELLS = (0x01B00000, 0x01B00001, 0x01B09800)

LOUNGERS = (
    "InvisibleSpaLounger.png.fmap",
    "InvisibleLounger.png.fmap",
    "SpaLoungerStd.png.fmap",
)

# The two spa loungers ship a DELIBERATELY WIDER drop target than the chaise
# they borrow: the donor's object cells are an eleven-cell ragged diagonal and
# dropping a villager on it was reported as very difficult. The generator
# dilates their own copies by one cell, so they are no longer byte-identical to
# the donor and no longer identical to the plain Invisible Lounger.
#
# That is the intended difference, and it is narrow: only the object-cell count
# may change. Every other property this file checks -- no mobile-only markers,
# no untranslated anchor, same grid, same header -- still applies to all three.
WIDENED_LOUNGERS = (
    "InvisibleSpaLounger.png.fmap",
    "SpaLoungerStd.png.fmap",
)


def _cells(path):
    data = path.read_bytes()
    count = (len(data) - 0x20 - 0x10) // 4
    return Counter(
        struct.unpack_from("<I", data, 0x20 + 4 * i)[0] for i in range(count)
    )


def _release_glob():
    """Which release's matrix output to verify.

    This was pinned to "VF2-B180-matrix-*". That folder is no longer produced,
    so every check in this file skipped -- silently, and for every release
    after B180. The suite reported "5 skipped" and read as green while
    verifying nothing at all, which is the failure this file exists to prevent:
    a check that cannot fail is not evidence.

    VF2_VERIFY_RELEASE names the release explicitly. Otherwise the NEWEST
    matrix output present is used, so the checks follow the current release
    instead of a frozen one.
    """
    named = os.environ.get("VF2_VERIFY_RELEASE")
    if named:
        return "VF2-%s-matrix-*" % named
    releases = sorted(
        {
            m.group(1)
            for d in OUTPUTS.glob("VF2-B*-matrix-*")
            for m in [re.match(r"VF2-(B\d+)-matrix-", d.name)]
            if m
        },
        key=lambda name: int(name[1:]),
    )
    if not releases:
        return None
    return "VF2-%s-matrix-*" % releases[-1]


# The spa-lounger hotspot widening merged in #239, after the B181 matrix was
# built. A build from B181 or earlier cannot carry it, and demanding it there
# would be asserting a fix onto a release that predates it.
WIDENING_FIRST_RELEASE = 182


def _release_has_widening(build_name):
    m = re.match(r"VF2-B(\d+)-matrix-", build_name)
    if not m:
        return False
    return int(m.group(1)) >= WIDENING_FIRST_RELEASE


def _finished_builds():
    """Variant folders that actually linked, for the current release only.

    A matrix build seeds each variant from the previous release before
    rebuilding it, so an unlinked folder still holds the PREVIOUS release's
    maps -- and would report B179's defect against B180.
    """
    pattern = _release_glob()
    if pattern is None:
        return
    for d in sorted(OUTPUTS.glob(pattern)):
        if d.name.endswith("-logs"):
            continue
        if list(d.glob("*.exe")) and (d / "Assets").is_dir():
            yield d


class TestShippedLoungerMapsAreDesktopSafe(unittest.TestCase):
    def setUp(self):
        self.builds = list(_finished_builds())
        if not self.builds:
            self.skipTest("no finished current-release build output")

    def test_no_lounger_carries_the_untranslated_mobile_anchor(self):
        for build in self.builds:
            for name in LOUNGERS:
                path = build / "Assets" / name
                if not path.is_file():
                    continue
                with self.subTest(build=build.name, fmap=name):
                    cells = _cells(path)
                    self.assertNotIn(
                        MOBILE_ANCHOR, cells,
                        "carries the untranslated mobile peep anchor; the "
                        "desktop FindPeepSlot path rejects every chair with "
                        "this, which is the wrong-lying-position bug",
                    )
                    self.assertIn(
                        DESKTOP_ANCHOR, cells,
                        "is missing the desktop peep anchor entirely",
                    )

    def test_no_lounger_carries_mobile_only_footprint_markers(self):
        for build in self.builds:
            for name in LOUNGERS:
                path = build / "Assets" / name
                if not path.is_file():
                    continue
                with self.subTest(build=build.name, fmap=name):
                    cells = _cells(path)
                    found = sorted(
                        c for c in FORBIDDEN_MOBILE_CELLS if c in cells
                    )
                    self.assertEqual(
                        found, [],
                        f"mobile-only markers {[hex(m) for m in found]} "
                        "reached the desktop content map",
                    )

    def test_the_shipped_map_matches_the_desktop_safe_donor(self):
        """The strongest form: identical cells to the known-good source map.

        This is what makes the marker list above a belt-and-braces check
        rather than the only defence -- a mobile cell the ledger has not
        enumerated would still show up here as a mismatch.
        """
        if not PC_FMAP_DONOR.is_file():
            self.skipTest("pc_fmaps donor is not present in this tree")
        expected = _cells(PC_FMAP_DONOR)
        for build in self.builds:
            for name in LOUNGERS:
                path = build / "Assets" / name
                if not path.is_file():
                    continue
                with self.subTest(build=build.name, fmap=name):
                    shipped = _cells(path)
                    if name not in WIDENED_LOUNGERS:
                        self.assertEqual(
                            shipped, expected,
                            "does not match the desktop-safe donor map",
                        )
                        continue
                    # A widened spa map must be the donor map PLUS object
                    # cells, never anything else: same length, and every cell
                    # that is not an added object cell unchanged.
                    self.assertEqual(
                        len(shipped), len(expected),
                        "the widened map changed size",
                    )
                    counts = {}
                    for value in expected:
                        if value:
                            counts[value] = counts.get(value, 0) + 1
                    self.assertTrue(counts, "the donor map has no object cells")
                    obj = max(counts, key=lambda v: counts[v])
                    for index, (was, now) in enumerate(zip(expected, shipped)):
                        if was == now:
                            continue
                        self.assertEqual(
                            was, 0,
                            "cell %d was overwritten; only EMPTY cells may "
                            "become object cells" % index,
                        )
                        self.assertEqual(
                            now, obj,
                            "cell %d became %#x rather than the object value "
                            "%#x" % (index, now, obj),
                        )
                    # The widening merged after B181 was built, so asserting it
                    # against B181 or earlier would assert a property onto a
                    # release that predates the fix. Every OTHER check in this
                    # method still applies to those builds: no mobile markers,
                    # no untranslated anchor, no overwritten cell.
                    if not _release_has_widening(build.name):
                        continue
                    self.assertGreater(
                        sum(1 for v in shipped if v == obj),
                        sum(1 for v in expected if v == obj),
                        "the spa map is not actually wider than the donor, so "
                        "the widening did not reach this build",
                    )

    def test_every_lounger_ships_the_same_map(self):
        """They borrow one donor, so a divergence means one missed the fix."""
        for build in self.builds:
            present = [
                build / "Assets" / n
                for n in LOUNGERS
                if (build / "Assets" / n).is_file()
            ]
            if len(present) < 2:
                continue
            with self.subTest(build=build.name):
                digests = {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in present
                }
                # Two groups now, not one: the widened spa pair, and everything
                # else which still ships the donor map untouched. Within each
                # group they must still agree exactly -- a divergence there
                # means one target missed a fix, which is what this test was
                # written to catch.
                widened = {n: d for n, d in digests.items()
                           if n in WIDENED_LOUNGERS}
                plain = {n: d for n, d in digests.items()
                         if n not in WIDENED_LOUNGERS}
                if len(widened) > 1:
                    self.assertEqual(
                        len(set(widened.values())), 1,
                        f"the widened spa loungers disagree: {widened}",
                    )
                if len(plain) > 1:
                    self.assertEqual(
                        len(set(plain.values())), 1,
                        f"the unwidened loungers disagree: {plain}",
                    )
                # And the two groups MUST differ, or the widening never
                # reached this build and every check above passed on
                # unmodified bytes. Only from the release that carries the
                # widening: before it, byte-identical is the CORRECT result.
                if widened and plain and _release_has_widening(build.name):
                    self.assertNotEqual(
                        set(widened.values()), set(plain.values()),
                        "the spa loungers are byte-identical to the plain "
                        "one, so the hotspot widening did not reach this "
                        "build",
                    )


class TestStockDonorBorrowersMatchTheirDonors(unittest.TestCase):
    """The seven stock-donor items must ship their donor's map exactly.

    These are the items that rely on the game's native hotspot path rather
    than this patcher's drop dispatcher. That only works if the placement data
    they carry IS the donor's, so this checks the built artifact rather than
    the manifest that says which donor they name.

    It does NOT establish that a villager dropped on one of these acts. That
    is a separate claim and no playtest has confirmed it.
    """

    BORROWERS = {
        "InvisibleYogaEquipment.png.fmap": "YogaGearStd.png.fmap",
        "HomeGymSystemStd.png.fmap": "YogaGearStd.png.fmap",
        "ExerciseBikeStd.png.fmap": "TreadmillStd.png.fmap",
        "PingPongTableStd.png.fmap": "PoolTableStd.png.fmap",
        "InvisibleHammock.png.fmap": "HammockStd.png.fmap",
        "InvisibleKiddiePool.png.fmap": "PoolChildrensStd.png.fmap",
        "InvisibleFullSizePool.png.fmap": "PoolLargeStd.png.fmap",
    }

    def setUp(self):
        self.builds = list(_finished_builds())
        if not self.builds:
            self.skipTest("no finished current-release build output")

    def test_each_borrower_is_byte_identical_to_its_donor(self):
        checked = 0
        for build in self.builds:
            assets = build / "Assets"
            for borrower, donor in self.BORROWERS.items():
                bp, dp = assets / borrower, assets / donor
                if not (bp.is_file() and dp.is_file()):
                    continue
                with self.subTest(build=build.name, fmap=borrower):
                    self.assertEqual(
                        hashlib.sha256(bp.read_bytes()).hexdigest(),
                        hashlib.sha256(dp.read_bytes()).hexdigest(),
                        f"{borrower} no longer matches {donor}; the native "
                        "hotspot path depends on it carrying the donor's map",
                    )
                    checked += 1
        self.assertGreater(
            checked, 0,
            "found no borrower/donor pairs to compare -- a vacuous pass",
        )


if __name__ == "__main__":
    unittest.main()
