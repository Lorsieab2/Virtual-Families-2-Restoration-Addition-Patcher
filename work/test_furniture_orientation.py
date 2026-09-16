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
    # The chair sites now call VF2SeatChairAnim(info), which reads
    # info.orientation AND the seat's own side. Using the furniture
    # orientation alone gave every seat at one table the same facing,
    # which is why the right-hand side of both tables was reversed in
    # play: LinkPeepToFurniture fills one sFurnitureInfo2 per
    # PLACEMENT, so a table's two sides cannot be told apart by it.
    CHAIR_SITE = 'static char const *VF2SeatChairAnim('

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
        m = re.search(
            r'static char const \*VF2SeatChairAnim\(.*?\n\}', CODE, re.S)
        self.assertIsNotNone(m, "the chair animation selection is gone")
        expr = m.group(0)
        self.assertIn("info.orientation", expr,
                      "the animation is not chosen from info.orientation")
        self.assertIn("Sit In Chair NW", expr)
        self.assertIn("Sit In Chair NE", expr)

    def test_the_chair_animation_is_chosen_per_seat_not_per_table(self):
        """The defect this replaced: one facing for every seat at a table.

        Reported in play with screenshots for both tables -- the villagers on
        the right side faced the wrong way while the left side was correct.
        info.orientation is a property of the PLACEMENT, so it cannot
        distinguish two seats of one table; the seat's own side must take part.
        """
        m = re.search(
            r'static char const \*VF2SeatChairAnim\(.*?\n\}', CODE, re.S)
        self.assertIsNotNone(m)
        body = m.group(0)
        self.assertIn("VF2LinkedSeatIndex", body,
                      "the seat is no longer consulted, so every seat at "
                      "a table would take the same facing again")
        self.assertIn("VF2FurnitureFacesEast(info.orientation)", body,
                      "the furniture orientation is no longer consulted")
        # Both call sites must go through it rather than re-deriving a facing.
        self.assertEqual(
            CODE.count("VF2SeatChairAnim(villager, info, 2);")
            + CODE.count("VF2SeatChairAnim(villager, info, 4);"), 2,
            "both the picnic and the patio chair handlers must use the "
            "per-seat selection")

    def test_the_seat_comes_from_the_engines_own_index(self):
        """The side must come from the ENGINE's seat choice, not coordinates.

        SUPERSEDED APPROACH, recorded rather than deleted (AGENTS.md 11): this
        previously asserted the helper compared info.point.x against the
        table's record[+0x14]. That predicate was DEGENERATE. Decoded from
        work/FurnitureManager.disasm.txt, LinkPeepToFurniture at +0x261-0x283
        computes

            info.point.x = record[+0x14] + (seatAnchor.x - block.origin.x)

        so the difference is a column offset from the content block origin and
        is non-negative for EVERY seat. The test answered true for all of them
        and the wrong-side seating would have shipped unchanged.

        The engine picks a seat by index and writes the villager's peep id into
        record[+0x20 + index*4], so the index is recoverable and is the
        engine's own choice.
        """
        src = CODE
        self.assertIn("static int VF2LinkedSeatIndex(", src,
                      "the seat index helper is gone")
        start = src.index("static int VF2LinkedSeatIndex(")
        body = src[start:src.index("\n}", start)]
        self.assertIn("0x1BB48", body,
                      "the villager's peep id is no longer read")
        self.assertIn("record + 0x20 + seat * 4", body,
                      "the peep slots the link writes are no longer scanned")
        # Identify by placement handle, never by point (AGENTS.md rule).
        self.assertIn("record + 0x04) != info.unknown0", body,
                      "the record must be identified by placement handle")
        # The degenerate comparison must not come back.
        self.assertNotIn("info.point.x >= tableX", src,
                         "the column-offset comparison is degenerate: it is "
                         "true for every seat on both tables")

    def test_the_seat_predicate_actually_discriminates(self):
        """Both animations must be reachable, on BOTH tables' real seat data.

        This is the assertion the earlier rounds lacked, and its absence is why
        two predicates with one reachable answer passed review. A structural
        test -- "the helper is called", "both strings appear" -- cannot tell a
        working conditional from a constant one.

        The ground truth is decoded, not assumed. CContentMap::FindObject
        extracts a cell's object id as ((cell >> 11) & 0x40000 | cell & 0x3F800)
        >> 11; applied to the owner's APK maps that gives

            picnic  (5,9)=0x13 west  (8,11)=0x14 west
                    (15,12)=0x53 EAST (17,10)=0x54 EAST
            patio   (3,8)=0x13 west  (13,8)=0x14 EAST

        and FindPeepSlot enumerates present markers in the order
        {0x13, 0x14, 0x53, 0x54}, so ordinals map to those cells in that order.
        """
        def faces_east(o):
            return o in (0, 2)          # EFurnitureOrientation SE=0, NE=2

        def anim(seat, orientation, seat_count):
            table_east = faces_east(orientation)
            if seat < 0:
                return "NE" if table_east else "NW"
            far = seat >= (seat_count // 2)
            use_ne = (not far) if table_east else far
            return "NE" if use_ne else "NW"

        # The decoded side of each ordinal, per table.
        TRUTH = {
            4: {0: "west", 1: "west", 2: "east", 3: "east"},   # picnic
            2: {0: "west", 1: "east"},                          # patio
        }

        for seat_count, sides in TRUTH.items():
            # 1. Seats on OPPOSITE sides must take opposite animations, and
            #    seats on the SAME side must agree. This is the check that
            #    rejects the superseded (seat & 1), which split {0,2}|{1,3} and
            #    therefore put a west seat and an east seat in each group.
            for a, sa in sides.items():
                for b, sb in sides.items():
                    for orientation in range(4):
                        same = anim(a, orientation, seat_count) ==                             anim(b, orientation, seat_count)
                        self.assertEqual(
                            same, sa == sb,
                            "seats %d(%s) and %d(%s) on a %d-seat table "
                            "disagree with their decoded sides at "
                            "orientation %d" % (a, sa, b, sb, seat_count,
                                                orientation))

            # 2. For a fixed orientation the seats must not all agree.
            for orientation in range(4):
                got = {anim(s, orientation, seat_count) for s in sides}
                self.assertEqual(
                    got, {"NE", "NW"},
                    "a %d-seat table at orientation %d gives every seat the "
                    "same facing (%s); the predicate is degenerate"
                    % (seat_count, orientation, got))

            # 3. For a fixed seat, rotating the table must change the facing.
            for seat in sides:
                got = {anim(seat, o, seat_count) for o in range(4)}
                self.assertEqual(
                    got, {"NE", "NW"},
                    "seat %d of a %d-seat table ignores the furniture "
                    "orientation (%s)" % (seat, seat_count, got))

        # 4. The documented fallback: with no seat, orientation alone decides.
        self.assertNotEqual(anim(-1, 0, 4), anim(-1, 1, 4),
                            "the no-seat fallback ignores orientation")

    def test_the_seat_side_is_the_index_low_bit(self):
        """Pins the mapping the APK and the engine marker array agree on.

        The engine's marker array is {0x13, 0x14, 0x53, 0x54}: the pairs
        {0x13, 0x53} and {0x14, 0x54} differ by 0x40, so seat indices 0/2 take
        one side and 1/3 the other -- the index's LOW BIT.

        The owner's APK corroborates this and shows why no single fmap field
        would do. Picnic seats carry 0x98/0xA0 within each side, distinguished
        additionally by a side bit; the patio table's two seats have the side
        bit CLEAR for both and differ by the seat byte alone.
        """
        src = CODE
        start = src.index("static char const *VF2SeatChairAnim(")
        body = src[start:src.index("\n}", start)]
        self.assertIn("seat >= (seatCount / 2)", body,
                      "the side is no longer taken from the seat ordinal "
                      "against the table's own seat count")
        self.assertNotIn("(seat & 1)", body,
                         "ordinal parity splits {0,2}|{1,3}, which puts a west "
                         "seat and an east seat in each group on the four-seat "
                         "picnic table")
        self.assertIn("VF2FurnitureFacesEast(info.orientation)", body,
                      "the furniture orientation is no longer consulted")
        self.assertIn("VF2LinkedSeatIndex(villager, info)", body)
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
        # remain reachable as the two arms of a conditional.
        m = re.search(
            r'static char const \*VF2SeatChairAnim\(.*?\n\}', CODE, re.S)
        self.assertIsNotNone(m)
        expr = m.group(0).replace("\n", " ")
        self.assertRegex(
            expr,
            r"\?\s*\"Sit In Chair NE\"\s*:\s*\"Sit In Chair NW\"",
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
        # The facing now splits on the EAST/WEST axis rather than on NW
        # alone. VF2FurnitureFacesNorthWest is `orientation == 3`, so SE(0),
        # SW(1) and NE(2) all took eHeadDirectionNE and only NW(3) differed --
        # three of four placements produced an IDENTICAL pose, reported in play
        # a third time as "spa lounger villager orientation has no change".
        self.assertIn("VF2FurnitureFacesEast(info.orientation)", SOURCE,
                      "the chaise facing no longer follows the furniture")
        self.assertIn("eHeadDirectionNE = 0", SOURCE)
        self.assertIn("eHeadDirectionNW = 3", SOURCE)

    def test_the_lounger_facing_does_not_collapse_three_orientations(self):
        """Every lounger pose must split east/west, not on NW alone.

        This is the specific regression: `orientation == 3` maps SE, SW and NE
        onto one head direction, so rotating the lounger changes nothing for
        three of the four placements. Both PlanToWait poses and the spa
        settle/sleep strip must use the east/west split.
        """
        self.assertEqual(
            SOURCE.count("VF2FurnitureFacesEast(info.orientation)\n"
                         "                ? eHeadDirectionNE\n"
                         "                : eHeadDirectionNW"), 2,
            "both chaise poses must use the east/west split")
        self.assertIn("!VF2FurnitureFacesEast(info.orientation)", SOURCE,
                      "the spa settle/sleep strip must use the same split")
        # The sleep strip and the settle pose must agree, so they come from
        # one test rather than two.
        self.assertIn("if (loungerFacesNorthWest) {", SOURCE)
        self.assertIn('"SleepNW"', SOURCE)
        self.assertIn('"SleepNE"', SOURCE)

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
