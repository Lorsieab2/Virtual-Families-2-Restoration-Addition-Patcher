#!/usr/bin/env python3
"""A desktop map must not keep a fragment of the mobile object-type field.

Every cell of a `.fmap` packs an object-type field in bits 16-31 and the
cell's own payload -- seat anchor, collision flag, EObject marker -- in bits
0-15. The mobile builds number their furniture types from 0x174 upwards, a
range the desktop game never uses (checked against all 235 maps a clean
Virtual Families 2 install ships: it uses 0x0, 0x2, 0x4 ... 0x164, and never
0x174-0x1b4). So each `pc_fmaps` map is the mobile map with that field
subtracted away, leaving the payload intact.

Patio_table was subtracted by 0x1b0 -- the *chaise's* type, copied from the
neighbouring spec -- rather than its own 0x1b4. Its two seat anchors shipped
as 0x00049801 and 0x0004a001 instead of 0x00009801 and 0x0000a001, so the
seats claimed to belong to furniture type 0x4 and villagers stood wrong at the
patio table's chairs. Nothing caught it because each map was only ever checked
against its own hand-written constants, which carried the same typo.

The invariant is per-file and needs no table to maintain: whatever a map
subtracts, it must subtract the *same* amount from every cell it keeps, and
the result must leave the low 16 bits untouched.
"""
import struct
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

BEHAVIORS = (
    Path(patcher.ROOT)
    / "patcher_assets"
    / "optional_patches"
    / "mobile_furniture_behaviors"
)
MOBILE = BEHAVIORS / "mobile_fmaps"
PC = BEHAVIORS / "pc_fmaps"


def _type(value):
    """The cell's object-type field, with the EObject marker bit masked off.

    Bit 29 flags a cell as the object's EObject marker and survives the strip;
    it is not part of the type. Bit 25 (0x200 here) *is* carried with the type
    -- Patio_table's 0x1b4 and 0x3b4 are two types of one object -- so it is
    left in place.
    """
    return (value >> 16) & 0xFFFF & ~0x2000


def _cells(path):
    data = path.read_bytes()
    assert data[:4] == b"QAMF", f"{path} is not a furniture map"
    width, height = struct.unpack_from("<ii", data, 24)
    return [
        struct.unpack_from("<I", data, 32 + index * 4)[0]
        for index in range(width * height)
    ]


class TestObjectTypeFieldIsStrippedWholly(unittest.TestCase):
    def setUp(self):
        self.names = sorted(path.name for path in PC.glob("*.fmap"))
        self.assertEqual(len(self.names), 34, "expected the 34 validated maps")

    def test_every_kept_cell_keeps_its_payload_verbatim(self):
        for name in self.names:
            with self.subTest(name):
                for mobile, pc in zip(_cells(MOBILE / name), _cells(PC / name)):
                    if pc:
                        self.assertEqual(
                            pc & 0xFFFF,
                            mobile & 0xFFFF,
                            f"{name}: payload rewritten ({mobile:#010x} -> {pc:#010x})",
                        )

    def test_a_cleared_cell_only_ever_drops_a_known_unsafe_payload(self):
        """Zeroing a cell must be deliberate, not incidental.

        The check above compares payloads only where the pc cell survives, so
        a transform that wrongly cleared a cell it should have kept passes it
        silently -- the very failure the seat-anchor regression was. Across
        all 34 maps exactly two payloads are ever dropped: 0x0001 and 0x8800
        on the four holiday-decoration cells the group and stocking validators
        own. 0x8800 is kept on seven other cells, so it is not unsafe by
        itself and only the named maps may drop it.

        0x0001 is NOT mobile-only metadata, and an earlier version of this
        docstring said it was. It is ordinary desktop collision geometry: the
        exact value 0x00000001 occurs 3,458 times across 102 of the 327 maps
        installed with B179, and 3,186 times across 86 files of the retail
        desktop install, where in the stock BlackCouch it forms one contiguous
        51-cell region rather than isolated markers. These maps drop it as part
        of the wider hotspot-metadata exclusion the B156 ledger records for
        each map, which is a choice about what a DONOR's own map carries, not
        a statement that the desktop engine cannot handle the value.

        Anything else being cleared means the strip removed geometry, which is
        how a villager ends up walked to a position that no longer exists.
        """
        may_drop_8800 = {
            "SantaWallDecoration.png.fmap",
            "StockingLarge.png.fmap",
            "StockingSmall.png.fmap",
        }
        for name in self.names:
            with self.subTest(name):
                for index, (mobile, pc) in enumerate(
                    zip(_cells(MOBILE / name), _cells(PC / name))
                ):
                    payload = mobile & 0xFFFF
                    if pc or not payload:
                        continue
                    allowed = {0x0001}
                    if name in may_drop_8800:
                        allowed.add(0x8800)
                    self.assertIn(
                        payload,
                        allowed,
                        f"{name}: cell {index} dropped payload {payload:#06x} "
                        f"({mobile:#010x} -> {pc:#010x}); only the mobile "
                        f"behaviour hotspot may be cleared here",
                    )

    def test_no_map_keeps_a_fragment_of_the_mobile_object_type(self):
        """A kept cell's type must be a type this map actually subtracted.

        A map may carry more than one type -- Patio_table uses 0x1b4 and
        0x3b4, Picnic_table 0x1ac, 0x3ac and 0x3ae -- and a cell may keep a
        small remainder when the value removed was a neighbouring type rather
        than its own (Picnic_table's far seats keep 0x2, which is 0x3ae less
        the map's 0x3ac). What no cell may hold is a remainder that no
        subtraction of a type present in the map could have produced: that is
        the signature of the wrong constant being subtracted, and it leaves a
        live object type behind in the shipped map.
        """
        for name in self.names:
            with self.subTest(name):
                mobile_cells = _cells(MOBILE / name)
                types = {_type(value) for value in mobile_cells if value} - {0}
                for mobile, pc in zip(mobile_cells, _cells(PC / name)):
                    if not pc:
                        continue
                    reachable = {0} | {
                        _type(mobile) - subtracted
                        for subtracted in types
                        if _type(mobile) >= subtracted
                    }
                    self.assertIn(
                        _type(pc),
                        reachable,
                        f"{name}: cell {mobile:#010x} -> {pc:#010x} keeps object "
                        f"type {_type(pc):#06x}, which no type in this map "
                        f"({', '.join(f'{t:#06x}' for t in sorted(types))}) "
                        f"could have left behind",
                    )

    def test_the_patio_table_seat_anchors_are_the_regression(self):
        cells = set(_cells(PC / "Patio_table.png.fmap"))
        self.assertIn(0x00009801, cells)
        self.assertIn(0x0000A001, cells)
        self.assertNotIn(0x00049801, cells, "the 0x1b0 mis-subtraction is back")
        self.assertNotIn(0x0004A001, cells, "the 0x1b0 mis-subtraction is back")


if __name__ == "__main__":
    unittest.main()
