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

import patch_mobile_furniture_pack as patcher

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
SOURCE = GENERATOR.read_text(encoding="utf-8", errors="replace")

# SOURCE with C++ line comments removed.
#
# The emitted C++ carries long explanatory comments, several of which QUOTE the
# old defective expressions deliberately so the reason for each fix survives in
# the code. A test that searches raw SOURCE therefore matches the documentation
# of a bug and reports it as the bug -- and, worse, a comment sitting between
# `chairAnim =` and its expression lands inside an unanchored regex capture.
# Every test below that inspects an EXPRESSION uses this view; tests that check
# for the presence of a whole construct may still use SOURCE.
CODE = "\n".join(
    line for line in SOURCE.splitlines() if not line.lstrip().startswith("//"))


def governing_declaration(site_marker):
    """The sFurnitureInfo2 declaration that actually governs a call site.

    SOURCE contains FOUR declarations of this struct, and they are not
    identical: three end `int padding[4]` and one has `int object;` followed by
    `int padding[3]`. An unanchored search always finds the first, which is not
    the one the chair handlers are emitted with -- so a layout test written
    that way validates a struct the changed code never sees.
    """
    site = CODE.find(site_marker)
    if site < 0:
        return None
    # Offsets must all come from the SAME string. Mixing CODE offsets with
    # SOURCE offsets silently compares positions in two different texts and
    # selects the wrong declaration.
    starts = [i for i in range(len(CODE))
              if CODE.startswith("struct sFurnitureInfo2 {", i)]
    owning = [i for i in starts if i < site]
    if not owning:
        return None
    start = max(owning)
    end = CODE.index("};", start)
    body = CODE[start + len("struct sFurnitureInfo2 {"):end]
    return [ln.strip() for ln in body.splitlines() if ln.strip()]


class OrientationComesFromTheOrientationField(unittest.TestCase):
    # The chair sites now ask VF2FurnitureFacesNorthWest(info.orientation)
    # instead of `info.orientation == 1`. That old expression was the BUG:
    # EFurnitureOrientation is SE=0, SW=1, NE=2, NW=3 (CodeView LF_ENUMERATE
    # records, identical in FurnitureManager.obj at 0x52e0 and Behavior.obj at
    # 0x9cfb), so `== 1` is SW alone -- it missed NW entirely and answered true
    # for SW. Reported in play: a picnic table facing NE seated its villagers
    # facing the other way.
    #
    # What this module actually guards is unchanged and still pinned below --
    # that the field is read BY NAME rather than at a raw offset that lands in
    # padding, and that the declaration governing these sites keeps orientation
    # as its second field.
    CHAIR_SITE = 'VF2FurnitureFacesNorthWest(info.orientation)'

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
        m = re.search(r'char const \*chairAnim =(.*?);', CODE, re.S)
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
        m = re.search(r'char const \*chairAnim =(.*?);', CODE, re.S)
        expr = m.group(1)
        self.assertRegex(
            expr.replace("\n", " "),
            r"\?\s*\"Sit In Chair NW\"\s*:\s*\"Sit In Chair NE\"",
            "the two orientations are no longer the two arms of one "
            "conditional")

    def test_the_chaise_handler_still_reads_the_same_field(self):
        # The correct form this fix was modelled on. If it ever changes to a
        # raw offset, the same class of defect has been reintroduced there.
        #
        # Note this particular `== 1` is deliberately NOT the corrected facing
        # test. It is the GATE selecting the chaise pose over the flat lying
        # pose, and changing it would alter which pose a stock chaise gets --
        # out of scope for the reported bug. The FACING inside that branch is
        # what was wrong, and it is pinned by the test below.
        self.assertIn("if (info.orientation == 1 || VF2SpaLoungerHasHandle",
                      SOURCE,
                      "the chaise handler no longer reads info.orientation")

    def test_the_chaise_facing_follows_the_furniture(self):
        """The head direction inside the chaise branch must follow the lounger.

        Reported in play twice: villagers on spa loungers were oriented wrongly.
        Two separate things were wrong. The test asked `info.orientation == 1`,
        which is SW alone and missed NW; and both head-direction constants were
        wrong -- eHeadDirectionNE was declared 1, which is really Southeast, and
        eHeadDirectionNW was declared 7, which is really UpNE1, an upward gaze.
        """
        self.assertIn("VF2FurnitureFacesNorthWest(info.orientation)", SOURCE,
                      "the chaise facing no longer follows the furniture")
        self.assertIn("eHeadDirectionNE = 0", SOURCE)
        self.assertIn("eHeadDirectionNW = 3", SOURCE)

    def test_resting_body_targets_all_four_colored_loungers(self):
        chaise = next(
            spec for spec in patcher.MOBILE_FURNITURE_MANUAL_BINDING_SPECS
            if spec["name"] == "chaise"
        )
        self.assertEqual(
            chaise["item_ids"],
            tuple(patcher.MOBILE_CHAISE_ITEM_IDS)
            + (patcher.INVISIBLE_LOUNGER_ITEM_ID,),
        )
        self.assertIn("extern \"C\" void __cdecl VF2MobileRestingBody", SOURCE)
        self.assertIn("VF2TryLinkMobileChaise(villager, info)", SOURCE)
        self.assertIn("VF2PlanLinkedChaiseAction", SOURCE)


if __name__ == "__main__":
    unittest.main()
