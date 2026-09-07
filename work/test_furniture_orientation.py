"""Furniture animations must choose their orientation from the orientation field.

THE DEFECT THIS PINS: the chair-animation site chose between "Sit In Chair NW"
and "Sit In Chair NE" by reading

    *(int *)((unsigned char *)&info + 0x14)

That is not the orientation. sFurnitureInfo2 is laid out

    +0x00 unknown0
    +0x04 orientation
    +0x08 point.x
    +0x0C point.y
    +0x10..+0x1C padding[4]

so +0x14 is padding[1] -- uninitialised memory. The NW/NE choice was therefore
effectively arbitrary and could disagree with the furniture it was chosen for,
which the owner reported as "the villager uses the wrong orientation for the
furniture when they close their eyes".

The +0x14 offset IS meaningful, but for the PLACEMENT RECORD, where +0x14/+0x18
is the world position and +0x10 is the orientation. Two different structures.
This test exists because having the offsets of one and a pointer to the other
compiles perfectly and fails only in play.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
SOURCE = GENERATOR.read_text(encoding="utf-8", errors="replace")


class OrientationComesFromTheOrientationField(unittest.TestCase):
    def test_the_struct_layout_this_rests_on_has_not_moved(self):
        # If sFurnitureInfo2 ever gains or reorders a field, the reasoning in
        # this file is stale and the test should fail loudly rather than keep
        # asserting against a layout that no longer exists.
        m = re.search(r"struct sFurnitureInfo2 \{(.*?)\};", SOURCE, re.S)
        self.assertIsNotNone(m, "sFurnitureInfo2 is gone")
        fields = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
        self.assertEqual(
            fields,
            ["int unknown0;", "int orientation;", "ldwPoint point;",
             "int padding[4];"],
            "sFurnitureInfo2 changed; re-derive the offsets before trusting "
            "any raw-offset read of it")

    def test_the_chair_animation_reads_the_named_field(self):
        m = re.search(r'char const \*chairAnim =(.*?);', SOURCE, re.S)
        self.assertIsNotNone(m, "the chair animation selection is gone")
        expr = m.group(1)
        self.assertIn("info.orientation", expr,
                      "the animation is not chosen from info.orientation")
        self.assertIn("Sit In Chair NW", expr)
        self.assertIn("Sit In Chair NE", expr)

    def test_no_raw_offset_read_of_the_info_struct_for_orientation(self):
        # The specific defect: a byte offset into sFurnitureInfo2 that lands in
        # padding. Any reappearance of this shape is the bug returning.
        self.assertNotIn(
            "reinterpret_cast<unsigned char *>(&info) + 0x14", SOURCE,
            "orientation is being read at +0x14 again, which is padding[1] in "
            "sFurnitureInfo2 -- that offset belongs to the placement record, "
            "not to this struct")

    def test_both_orientations_are_still_reachable(self):
        # A fix that always picks one branch would 'work' for whichever
        # orientation was tested and be wrong for the other. Both names must
        # appear, on opposite sides of the same conditional.
        m = re.search(r'char const \*chairAnim =(.*?);', SOURCE, re.S)
        expr = m.group(1)
        self.assertRegex(
            expr.replace("\n", " "),
            r"\?\s*\"Sit In Chair NW\"\s*:\s*\"Sit In Chair NE\"",
            "the two orientations are no longer the two arms of one "
            "conditional")

    def test_the_chaise_handler_still_reads_the_same_field(self):
        # The correct form this fix was modelled on. If it ever changes to a
        # raw offset, the same class of defect has been reintroduced there.
        self.assertIn("if (info.orientation == 1) {", SOURCE,
                      "the chaise handler no longer reads info.orientation")


if __name__ == "__main__":
    unittest.main()
