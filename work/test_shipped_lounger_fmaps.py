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


def _cells(path):
    data = path.read_bytes()
    count = (len(data) - 0x20 - 0x10) // 4
    return Counter(
        struct.unpack_from("<I", data, 0x20 + 4 * i)[0] for i in range(count)
    )


def _finished_builds():
    """Variant folders that actually linked, for the current release only.

    A matrix build seeds each variant from the previous release before
    rebuilding it, so an unlinked folder still holds the PREVIOUS release's
    maps -- and would report B179's defect against B180.
    """
    for d in sorted(OUTPUTS.glob("VF2-B180-matrix-*")):
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
                    self.assertEqual(
                        _cells(path), expected,
                        "does not match the desktop-safe donor map",
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
                self.assertEqual(
                    len(set(digests.values())), 1,
                    f"loungers disagree: {digests}",
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
