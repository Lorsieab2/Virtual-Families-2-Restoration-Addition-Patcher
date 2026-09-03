#!/usr/bin/env python3
"""An invisible item keeps its own footprint, not a smaller stand-in's.

A `.fmap` defines collision, selection and seat/hotspot geometry. Borrowing a
donor map because it was easier to resolve gives a large item a small item's
footprint and anchors, and swapping the graphic to transparent afterwards does
not correct that -- the object still collides and seats villagers on the wrong
cells.

The Picnic and Patio tables briefly used the round table's 11x12 map for
availability reasons. The desktop-safe copies of their own maps are tracked in
`pc_fmaps`, which is on the donor search path, so that trade is unnecessary.
"""
import struct
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

PC_FMAPS = (
    Path(patcher.ROOT)
    / "patcher_assets"
    / "optional_patches"
    / "mobile_furniture_behaviors"
    / "pc_fmaps"
)

# The grids the patcher's own validators already pin for these maps.
EXPECTED_GRIDS = {
    "Picnic_table.png.fmap": (22, 16),
    "Patio_table.png.fmap": (19, 17),
    "Chaise_brown.png.fmap": (19, 14),
}


def _grid(path):
    data = path.read_bytes()
    assert data[:4] == b"QAMF", f"{path} is not a furniture map"
    return struct.unpack_from("<ii", data, 24)


def _item(name):
    for item in patcher.INVISIBLE_OUTDOOR_ITEMS:
        if item["name"] == name:
            return item
    raise AssertionError(f"no invisible item {name}")


class TestInvisibleFurnitureFootprints(unittest.TestCase):
    def test_each_table_uses_its_own_map(self):
        self.assertEqual(
            _item("InvisiblePicnicTable")["donor_fmap"], "Picnic_table.png.fmap"
        )
        self.assertEqual(
            _item("InvisiblePatioTable")["donor_fmap"], "Patio_table.png.fmap"
        )

    def test_no_invisible_outdoor_item_borrows_the_round_table(self):
        # The round table is 11x12, smaller than every item that reached for
        # it, so it is never the right stand-in.
        for item in patcher.INVISIBLE_OUTDOOR_ITEMS:
            self.assertNotEqual(
                item["donor_fmap"], "TableRoundWhiteStd.png.fmap",
                f"{item['name']} would get an 11x12 footprint",
            )

    def test_the_donor_maps_are_the_validated_desktop_safe_ones(self):
        for filename, expected in EXPECTED_GRIDS.items():
            path = PC_FMAPS / filename
            self.assertTrue(path.is_file(), f"{filename} is not tracked in pc_fmaps")
            self.assertEqual(_grid(path), expected, f"{filename} grid drifted")

    def test_every_donor_map_is_resolvable_without_the_obb(self):
        # pc_fmaps is tracked, so a clean checkout can resolve these. The OBB
        # directory is optional and must never be the only source.
        for item in patcher.INVISIBLE_OUTDOOR_ITEMS:
            donor = item["donor_fmap"]
            if donor not in EXPECTED_GRIDS:
                continue
            self.assertTrue(
                (PC_FMAPS / donor).is_file(),
                f"{item['name']} depends on {donor}, which is not checked in",
            )


class TestInheritedSourceAuthenticity(unittest.TestCase):
    def test_tracked_art_is_accepted_when_it_matches_its_digest(self):
        for name in ("Picnic_table.png", "Patio_table.png", "Chaise_brown.png"):
            self.assertIsNotNone(
                patcher.authentic_inherited_furniture_source(name),
                f"{name} should resolve from the digest-verified tracked store",
            )

    def test_an_unknown_name_falls_back_rather_than_blocking(self):
        self.assertIsNone(
            patcher.authentic_inherited_furniture_source("NotATrackedImage.png")
        )


if __name__ == "__main__":
    unittest.main()
