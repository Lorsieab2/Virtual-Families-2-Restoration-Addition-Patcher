#!/usr/bin/env python3
"""An item that borrows a map must not get the raw mobile one.

Mobile Furniture Behaviors ships two maps for each of the 34 items it
implements: the rendered-only base map in the vanilla runtime payload, which
is the raw mobile file, and the desktop-safe map in `pc_fmaps`. The behavior
ledger is explicit that the raw mobile files must never be installed into the
desktop content map, because the desktop tables carry no handler for their
markers.

The patch installs the desktop-safe map over each donor's OWN name. A
borrowing item's copy is written under the BORROWER's name, which that pass
never visits, so every borrower of one of those 34 donors shipped the raw
mobile map -- including both Spa Loungers, whose peep-slot anchor stayed at
the untranslated mobile 0x01B09800 rather than the desktop 0x00009800. The
ledger records that without the translated anchor `FindPeepSlot` rejects every
chair, which is what put a villager in the wrong lying position on a Spa
Lounger set NW, and made one set NE change behaviour immediately, while the
ordinary Loungers -- same artwork, same donor, but resolved under the donor's
own name -- were fine.
"""
import struct
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

PC_FMAPS = patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR
MOBILE_FMAPS = patcher.MOBILE_FURNITURE_BEHAVIOR_SOURCE_DIR

DONOR_TABLES = (
    patcher.COUCH_FMAP_DONORS,
    patcher.NEW_FURNITURE_FMAP_DONORS,
    patcher.INVISIBLE_OUTDOOR_FMAP_DONORS,
    patcher.INVISIBLE_TRANSPARENT_FMAP_DONORS,
    patcher.VF3_TV_FMAP_DONORS,
)

# The mobile marker the desktop build has no handler for, and the anchor the
# desktop FindPeepSlot needs, as the ledger records them.
MOBILE_CHAISE_ANCHOR = 0x01B09800
DESKTOP_CHAISE_ANCHOR = 0x00009800


def _cells(path):
    data = path.read_bytes()
    width, height = struct.unpack_from("<ii", data, 24)
    return [
        struct.unpack_from("<I", data, 32 + index * 4)[0]
        for index in range(width * height)
    ]


class TestDesktopSafeSourceIsPreferred(unittest.TestCase):
    def test_a_donor_with_a_desktop_safe_map_resolves_to_it(self):
        source = patcher.desktop_safe_fmap_source("Chaise_brown.png.fmap")
        self.assertIsNotNone(source)
        self.assertEqual(source.parent, PC_FMAPS)

    def test_a_donor_without_one_resolves_to_nothing(self):
        # Stock desktop donors are already desktop-safe and must keep coming
        # from the payload, so the helper has to decline rather than guess.
        self.assertIsNone(patcher.desktop_safe_fmap_source("SofaWhiteStd.png.fmap"))
        self.assertIsNone(patcher.desktop_safe_fmap_source("PoolTableStd.png.fmap"))


class TestEveryBorrowerAvoidsTheRawMobileMap(unittest.TestCase):
    def test_each_borrowed_donor_that_has_a_safe_map_offers_it(self):
        borrowed = {donor for table in DONOR_TABLES for donor in table.values()}
        covered = [d for d in sorted(borrowed) if (PC_FMAPS / d).is_file()]
        self.assertTrue(covered, "expected at least one borrower of an implemented map")
        for donor in covered:
            with self.subTest(donor):
                self.assertEqual(
                    patcher.desktop_safe_fmap_source(donor),
                    PC_FMAPS / donor,
                    f"{donor} would hand a borrower the raw mobile map",
                )

    def test_the_two_spa_loungers_share_the_ordinary_lounger_map(self):
        """The owner's report: spa loungers must match the base loungers."""
        spa = {
            name: donor
            for table in DONOR_TABLES
            for name, donor in table.items()
            if "Lounger" in name
        }
        self.assertIn("InvisibleSpaLounger.png.fmap", spa)
        for name, donor in spa.items():
            with self.subTest(name):
                self.assertEqual(donor, "Chaise_brown.png.fmap")
                self.assertEqual(
                    patcher.desktop_safe_fmap_source(donor).read_bytes(),
                    (PC_FMAPS / "Chaise_brown.png.fmap").read_bytes(),
                )

    def test_the_untranslated_anchor_is_what_the_safe_map_removes(self):
        """Pins the difference the fix turns on, so it cannot silently invert."""
        raw = _cells(MOBILE_FMAPS / "Chaise_brown.png.fmap")
        safe = _cells(PC_FMAPS / "Chaise_brown.png.fmap")
        self.assertIn(MOBILE_CHAISE_ANCHOR, raw)
        self.assertNotIn(MOBILE_CHAISE_ANCHOR, safe)
        self.assertIn(DESKTOP_CHAISE_ANCHOR, safe)


if __name__ == "__main__":
    unittest.main()
