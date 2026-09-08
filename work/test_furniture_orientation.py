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


def governing_declaration(site_marker):
    """The sFurnitureInfo2 declaration that actually governs a call site.

    SOURCE contains FOUR declarations of this struct, and they are not
    identical: three end `int padding[4]` and one has `int object;` followed by
    `int padding[3]`. An unanchored search always finds the first, which is not
    the one the chair handlers are emitted with -- so a layout test written
    that way validates a struct the changed code never sees.
    """
    site = SOURCE.find(site_marker)
    if site < 0:
        return None
    starts = [i for i in range(len(SOURCE))
              if SOURCE.startswith("struct sFurnitureInfo2 {", i)]
    owning = [i for i in starts if i < site]
    if not owning:
        return None
    start = max(owning)
    end = SOURCE.index("};", start)
    body = SOURCE[start + len("struct sFurnitureInfo2 {"):end]
    return [ln.strip() for ln in body.splitlines() if ln.strip()]


class OrientationComesFromTheOrientationField(unittest.TestCase):
    CHAIR_SITE = 'info.orientation == 1 ? "Sit In Chair NW"'

    def test_there_really_are_several_declarations(self):
        # If this ever becomes one declaration, the scoping below is
        # unnecessary -- but silently relying on that would be the same
        # mistake in reverse.
        count = SOURCE.count("struct sFurnitureInfo2 {")
        self.assertGreaterEqual(
            count, 1, "sFurnitureInfo2 is gone entirely")

    def test_the_layout_THE_CHAIR_HANDLERS_USE_has_not_moved(self):
        # Scoped to the declaration preceding the changed call site, not the
        # first one in the file. orientation must remain the SECOND field, at
        # +0x04, whatever follows point.
        fields = governing_declaration(self.CHAIR_SITE)
        self.assertIsNotNone(
            fields, "could not locate the declaration governing the chair "
                    "handlers; this test would otherwise pass vacuously")
        self.assertEqual(
            fields[:3],
            ["int unknown0;", "int orientation;", "ldwPoint point;"],
            "the declaration the chair handlers are emitted with changed; "
            "re-derive the offsets before trusting info.orientation")

    def test_that_declaration_is_not_the_first_one_in_the_file(self):
        # Pins the reason this test is scoped at all: an unanchored search
        # picks a different declaration than the one that governs the change.
        site = SOURCE.find(self.CHAIR_SITE)
        first = SOURCE.find("struct sFurnitureInfo2 {")
        starts = [i for i in range(len(SOURCE))
                  if SOURCE.startswith("struct sFurnitureInfo2 {", i)]
        if len(starts) > 1:
            self.assertNotEqual(
                max(i for i in starts if i < site), first,
                "the chair handlers are now governed by the FIRST declaration; "
                "the scoping in this file can be simplified, but check the "
                "layout by hand before doing so")

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
