#!/usr/bin/env python3
"""The Ping-Pong Table gets its own behaviour label.

The table borrows CBehavior::PlayingPooltable from the Pool Table, which is
the whole reason it has any interaction at all -- but that behaviour labels its
users "Playing pool".

THE TWO TABLES NO LONGER SHARE AN OBJECT. They both answered EObject 0x36 for a
long time, because the Ping-Pong Table borrowed PoolTableStd.png.fmap, and that
is why the owner kept reporting villagers targeting the ping-pong table to play
pool: FindFurniture resolves purely by object, so nothing downstream could tell
them apart. The Ping-Pong Table now declares its own 0x9A and its shipped fmap
is retargeted to match.

The placed-furniture record behind the villager's linked table is still what
distinguishes the two for LABELLING, and that probe must search the ping-pong
table's own object now rather than the Pool Table's.

A stock Pool Table must keep its stock label untouched.
"""
import re
import unittest

NL = chr(10)

import patch_mobile_furniture_pack as patcher


def _source():
    path = patcher.ROOT / "work" / "patch_mobile_furniture_pack.py"
    return path.read_text(encoding="utf-8")


# The body of VF2LinkedFurnitureItemIs, so several tests can inspect it without
# each repeating the pattern.
PROBE_BODY = (
    r"VF2LinkedFurnitureItemIs\(\n"
    r"    CVillager &villager, int object, int itemId\)\n\{(.*?)\n\}"
)


class TestPingPongLabels(unittest.TestCase):
    def test_the_group_exists_with_both_labels(self):
        self.assertIn("ping_pong", patcher.BEHAVIOR_LABEL_GROUP_RANGES)
        start, end = patcher.BEHAVIOR_LABEL_GROUP_RANGES["ping_pong"]
        labels = [text for _key, text in patcher.BEHAVIOR_LABELS[start:end]]
        self.assertEqual(labels, ["Playing ping-pong"])

    def test_the_group_is_appended_after_the_established_ones(self):
        # What matters is that it was APPENDED, not that it is still last --
        # the exercise bike groups were added after it. Inserting a group in
        # the middle is what would shift every established label id.
        names = [name for name, _entries in patcher.BEHAVIOR_LABEL_GROUPS]
        self.assertIn("ping_pong", names)
        # Every group that existed before it still starts where it did, which
        # is what "appended" buys: the snow group is the last of the original
        # set and must still precede this one.
        self.assertLess(names.index("snow"), names.index("ping_pong"))
        start, _end = patcher.BEHAVIOR_LABEL_GROUP_RANGES["ping_pong"]
        snow_start, snow_end = patcher.BEHAVIOR_LABEL_GROUP_RANGES["snow"]
        self.assertEqual(start, snow_end)

    def test_the_label_ids_clear_the_blocks_that_follow_them(self):
        ids = patcher.behavior_label_string_ids_for_group("ping_pong")
        self.assertEqual(len(ids), 1)
        self.assertLess(
            max(ids), patcher.holiday_ornament_collection_title_string_id(),
            "the label ids must stay below the ornament/achievement block",
        )


class TestTheWrapperIsInstalled(unittest.TestCase):
    def test_behavior_0x099_is_retargeted(self):
        src = _source()
        self.assertRegex(
            src,
            r'retarget\(0xDE4, 0x099, "_VF2RandomPooltableLabel"',
            "PlayingPooltable must be retargeted or the label never changes",
        )

    def test_the_wrapper_runs_the_native_behaviour(self):
        src = _source()
        body = re.search(
            r"VF2RandomPooltableLabel\(CVillager &villager\)\n\{(.*?)\n\}",
            src, re.S,
        )
        self.assertIsNotNone(body)
        self.assertIn(
            "VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::PlayingPooltable)",
            body.group(1),
            "the native plan must run unchanged; only the label varies",
        )

    def test_a_stock_pool_table_keeps_its_stock_label(self):
        src = _source()
        # Bounded by the next top-level definition rather than the first "\n}".
        # The wrapper body is now a single statement with no inner block, and
        # an earlier version of this extraction relied on a closing brace that
        # only existed while the body had an `if` in it.
        start = src.index(
            "VF2RandomPooltableLabel(CVillager &villager)" + NL + "{")
        body = src[start:src.index(NL + "// The Exercise Bike borrows", start)]
        # THE PROPERTY IS UNCHANGED; what guarantees it is now much simpler.
        #
        # SUPERSEDED, recorded rather than deleted (AGENTS.md 11): this
        # asserted `if (!onPingPong)`, a guard that had to DECIDE whether the
        # villager was at a stock pool table. That decision was necessary only
        # while the two tables shared object 0x36.
        #
        # They no longer do, so stock PlayingPooltable routes only to a genuine
        # pool table and the wrapper applies no label at all. The native label
        # now survives by construction rather than by a correct decision, which
        # is a stronger guarantee than the one this test used to make.
        self.assertNotIn("onPingPong", body)
        # NO LABEL IS APPLIED HERE AT ALL, which is the strongest form of the
        # property this test has ever asserted.
        #
        # It previously located the early return and required it to come
        # BEFORE any label application, matching the call SHAPE rather than a
        # helper name -- an earlier version had pinned
        # "VF2ApplyRememberedOrRandomLabel" and went red on a pure rename.
        # Shape-matching was the right instinct, and it is now unnecessary:
        # there is no label application in this wrapper to be ordered against.
        applications = [
            match.start()
            for match in re.finditer(r"\bVF2Apply\w*Label\w*\(", body)
        ]
        self.assertEqual(
            applications, [],
            "the stock pool wrapper applies a label again; stock "
            "PlayingPooltable only ever routes to a pool table now, so any "
            "label applied here overwrites a correct native one",
        )

    def test_the_wrapper_only_runs_the_native_behaviour(self):
        """SUPERSEDED: there is no probe left whose ordering could matter.

        Recorded rather than deleted (AGENTS.md 11). This required the
        table-identity probe to be taken BEFORE the native behaviour, since a
        probe taken afterwards samples a different moment. That ordering was
        load-bearing while the wrapper had to classify which of two
        same-object tables the villager was at.

        The tables now have separate objects, so stock PlayingPooltable routes
        only to pool tables and the wrapper classifies nothing. The invariant
        reduces to: run the native behaviour, touch nothing else.
        """
        body = re.search(
            r"VF2RandomPooltableLabel\(CVillager &villager\)\n\{(.*?)\n\}",
            _source(), re.S,
        ).group(1)
        self.assertIn("VF2RunNativeBehaviorAndChangedLabel", body)
        self.assertNotIn("VF2LinkedFurnitureItemIs", body)


class TestTheEmittedCIsValid(unittest.TestCase):
    """The generated C, not the Python that generates it.

    vf2_spontaneous_behaviors.cpp is built from a RAW string with named
    __VF2_*__ placeholders substituted afterwards -- not an f-string. Writing
    f-string conventions into it ({NAME:#x} and doubled braces) produces source
    that reads correctly in Python and does not compile: the ping-pong helper
    shipped a literal {PING_PONG_TABLE_ITEM_ID:#x} and failed the
    behavior_patches variant with C2065. Only a real build compiles this file,
    so assert the emitted text here instead.
    """

    def test_no_unsubstituted_placeholders_reach_the_c(self):
        src = _source()
        start = src.index("static bool VF2LinkedFurnitureItemIs")
        end = src.index("VF2RandomDrinkLabel(CVillager &villager)")
        block = src[start:end]
        self.assertNotIn(
            "{PING_PONG_TABLE_ITEM_ID", block,
            "an f-string placeholder in a raw-string block is emitted literally",
        )
        self.assertIn("__VF2_PING_PONG_TABLE_ITEM_ID__", block)

    def test_the_placeholder_is_actually_substituted(self):
        src = _source()
        self.assertIn(
            '"__VF2_PING_PONG_TABLE_ITEM_ID__", f"{PING_PONG_TABLE_ITEM_ID:#x}"',
            src,
            "the placeholder must be replaced when the helper source is built",
        )

    def test_the_block_uses_single_braces(self):
        # Doubled braces are the f-string escape; in a raw string they emit as
        # literal "{{" and "}}", which is not C.
        src = _source()
        start = src.index("static bool VF2LinkedFurnitureItemIs")
        end = src.index("VF2RandomDrinkLabel(CVillager &villager)")
        block = src[start:end]
        self.assertNotIn("{{", block)
        self.assertNotIn("}}", block)


class TestTheFurnitureProbe(unittest.TestCase):
    def test_the_item_id_is_still_the_derived_constant(self):
        """The item id must come from the furniture table, not a literal.

        TWO SUPERSEDED FORMS, recorded rather than deleted (AGENTS.md 11).
        This test used to assert that the caption probe in
        VF2RandomPooltableLabel compared against the derived item id -- first
        with the POOL TABLE's object 0x36, then with the ping-pong table's own
        0x9A after the separation.

        Neither form survives, because the probe itself is gone: stock
        PlayingPooltable routes only to pool tables now, so any classification
        in that wrapper can only mislabel a stock action. What the test was
        really protecting -- that the item id is DERIVED rather than hardcoded
        -- is pinned here and by
        test_the_item_id_is_derived_from_the_furniture_table below.
        """
        self.assertEqual(patcher.PING_PONG_TABLE_ITEM_ID, 0x32E)
        self.assertIn("__VF2_PING_PONG_TABLE_ITEM_ID__", _source())

    def test_the_item_id_is_derived_from_the_furniture_table(self):
        record = next(
            item for item in patcher.NEW_FURNITURE_ITEMS
            if item["name"] == "PingPongTableStd"
        )
        self.assertEqual(patcher.PING_PONG_TABLE_ITEM_ID, record["item_id"])

    def test_the_probe_uses_the_proven_record_layout(self):
        # The count at manager+0x1004, the 0x40 stride from manager+0x1008, the
        # item id at record+0x00 and the in-world flag at record+0x0C are all
        # confirmed twice over in FurnitureManager.obj: AddToWorld writes them
        # and PtOnFurniture reads them back through its own cursor.
        #
        # record+0x10 is an orientation index rather than a point, so it must
        # not be treated as a position.
        body = re.search(
            PROBE_BODY, _source(), re.S,
        )
        self.assertIsNotNone(body)
        text = body.group(1)
        self.assertIn("manager + 0x1004", text)
        self.assertIn("manager + 0x1008 + slot * 0x40", text)
        self.assertIn("record + 0x0C", text)
        self.assertNotIn(
            "record + 0x10", text,
            "record+0x10 is an orientation index, not the placed point",
        )

    def test_the_probe_matches_the_placement_handle_not_a_point(self):
        """The probe must not hit-test info.point to recover the record.

        This is the bug players saw as "Playing pool" at the Ping-Pong Table.
        FindFurniture sets info.point to record+0x14/+0x18 plus a furniture-map
        hotspot offset, making it the tile the villager stands on to USE the
        item. PtOnFurniture is a point-inside-footprint test, so it was being
        asked which furniture the villager stands INSIDE -- and for anything
        you stand beside, that is nothing. The probe answered "not that item"
        for every item, every time.

        AddToWorld stamps each placement with a unique handle at record+0x04
        and FindFurniture returns it as info.unknown0, so the matched record is
        named exactly, with no geometry.
        """
        text = re.search(PROBE_BODY, _source(), re.S).group(1)
        code = "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith("//")
        )
        self.assertNotIn(
            "VF2BehaviorPtOnFurnitureIndex", code,
            "recovering the slot by hit-testing info.point is the defect; "
            "info.point is the walk-to anchor, not the item's footprint",
        )
        self.assertIn("record + 0x04", code)
        self.assertIn("info.unknown0", code)

    def test_the_probe_bounds_the_record_count(self):
        """0x200 is the array's real capacity, read out of the binary.

        AddToWorld opens with `cmp [edi+0x1004], 0x200 / jge` and returns
        without adding once the count reaches it, so a larger count means the
        structure is not what this code believes it is.
        """
        text = re.search(PROBE_BODY, _source(), re.S).group(1)
        self.assertIn("count < 0 || count > 0x200", text)


class TheCaptionFollowsTheTableTheVillagerIsAt(unittest.TestCase):
    """The label must follow the table this villager is actually at.

    VF2RandomPooltableLabel is bound to the STOCK PlayingPooltable behaviour, so
    no venue is forced and the engine picks the destination. Both tables answer
    EObject 0x36, exactly as the treadmill and the exercise bike share 0x04.

    THIS CLASS PREVIOUSLY PINNED A FIX THAT DID NOT WORK, and the history
    matters because the same reasoning was applied to both pairs of furniture.

    It required the wrapper to prefer a route recorded by intercepting PlanToGo
    and asking CContentMap::FindObject which placement the route resolved to.
    But that function takes only an object enum and an out-point -- no villager
    and no position -- so it is a global query that answers identically for
    every villager. With two placements sharing one object id, whichever one it
    returned classified every user of either. The owner reported exactly that
    outcome for the treadmill after the sibling fix shipped.

    ?PlayingPooltable@CBehavior@@ (Behavior.obj section 488) carries exactly ONE
    furniture relocation, ?FindFurniture@CFurnitureManager@@, and references
    neither LinkPeepToFurniture nor CContentMap::FindObject -- the same shape as
    both treadmill behaviours. So the wrapper's own probe already makes the
    identical call the native code makes, with identical arguments, at the
    identical moment: before the behaviour runs, from the villager's feet. It
    was correct, and the recorded route could only override a right answer with
    a position-blind one.

    The sibling pin is TheCaptionFollowsTheMachineTheVillagerIsAt in
    work/test_exercise_bike_pose.py, which carries the disassembly in full.
    """

    def wrapper_body(self):
        source = _source()
        start = source.index(
            'extern "C" void __cdecl VF2RandomPooltableLabel(CVillager &villager)'
            + NL + '{')
        return source[start:source.index(NL + 'extern "C"', start)]

    def test_the_wrapper_no_longer_classifies_at_all(self):
        """The wrapper must not decide anything now that the objects differ.

        SUPERSEDED, recorded rather than deleted (AGENTS.md 11). This used to
        require the wrapper to probe which table the villager was at and
        relabel when it was the added one. That was right while the two SHARED
        object 0x36 and a villager reaching stock PlayingPooltable might have
        been at either.

        Separating the objects removed the ambiguity and made every form of the
        probe wrong:

          * probing 0x36 matches only genuine pool tables after the split, so
            it would silently leave "Playing pool" on the ping-pong table;
          * probing 0x9A asks about a DIFFERENT item than this behaviour routes
            to, so with both placed it finds the ping-pong table and overwrites
            a genuine STOCK POOL caption with a ping-pong label.

        The decisive fact is the binding. The retarget hooks behaviour 0x099 --
        STOCK PlayingPooltable -- while the added table runs on its own id
        0x0B8 through VF2PingPongPlay, which applies
        kVF2BehaviorLabels_ping_pong itself. So this wrapper only ever sees a
        stock pool action, and the correct behaviour is to leave its native
        label alone.
        """
        body = self.wrapper_body()
        self.assertNotIn(
            "VF2LinkedFurnitureItemIs", body,
            "the wrapper is classifying again; stock PlayingPooltable only "
            "ever routes to a pool table now, so any probe here can only "
            "mislabel it")
        self.assertNotIn("onPingPong", body)
        self.assertNotIn("VF2ApplyVenueLabel", body)
        self.assertIn(
            "VF2RunNativeBehaviorAndChangedLabel(villager, "
            "CBehavior::PlayingPooltable);", body,
            "the wrapper must still run the native behaviour")

    def test_the_ping_pong_label_still_has_exactly_one_source(self):
        """Removing the wrapper's relabel must not lose the ping-pong caption.

        It comes from VF2PingPongPlay, on behaviour id 0x0B8, which passes the
        label group itself. If that ever stopped, the caption would be gone
        rather than merely misplaced.
        """
        source = _source()
        start = source.index(
            'extern "C" void __cdecl VF2PingPongPlay(CVillager &villager)')
        handler = source[start:source.index(NL + "}", start)]
        self.assertIn("kVF2BehaviorLabels_ping_pong", handler)
        self.assertIn("__VF2_PING_PONG_OBJECT__", handler)

    def test_the_position_blind_route_machinery_is_gone(self):
        """It cannot answer a per-villager question, so it must not return.

        Comments are stripped first: the explanation above names these symbols
        deliberately, and a raw search would match the documentation of the
        defect rather than the defect itself.
        """
        source = _source()
        code = NL.join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("//"))
        for symbol in ("gVF2RoutedItemValid", "VF2RoutedToItem", "routeIsOurs"):
            with self.subTest(symbol=symbol):
                self.assertNotIn(symbol, code)


class ThePingPongTableHasItsOwnObject(unittest.TestCase):
    """The table must not share the Pool Table's content-map object.

    Owner, reported across three separate rounds:

        "Villagers still target the pingpong table to play pool autonomously"

    This is the IDENTICAL root cause the Exercise Bike had. PingPongTableStd
    borrows PoolTableStd.png.fmap and therefore answered the Pool Table's
    object 0x36. CFurnitureManager::FindFurniture resolves purely by object,
    so the two tables were indistinguishable downstream and every earlier fix
    had to be a positional guard or a label probe rather than a separation.
    """

    def test_the_table_has_its_own_object_id(self):
        self.assertEqual(patcher.MOBILE_PING_PONG_OBJECT, 0x9A)
        self.assertNotEqual(
            patcher.MOBILE_PING_PONG_OBJECT,
            patcher.MOBILE_PING_PONG_DONOR_OBJECT,
            "the Ping-Pong Table is sharing the Pool Table's object again")

    def test_the_autonomous_clone_requires_the_ping_pong_table(self):
        """The 0x0B8 clone must name its OWN object as the prerequisite.

        Codex P1 on #344, and it found a real hole in my own two-way
        validation: I mutated the BIKE call sites and confirmed tests failed,
        but never mutated the ping-pong one. Replacing
        `__VF2_PING_PONG_OBJECT__` with `0` here left 379 tests green while
        restoring the exact defect.

        Why it matters: CloneAutonomousCandidateWithWeight copies the donor's
        whole candidate record, so a 0 prerequisite means "inherit the donor's"
        -- and the donor is stock pool behaviour 0x099, whose prerequisite is
        the Pool Table's 0x36. CVillagerAI::DecideWhatToDo then calls
        ObjectExists on it, so autonomous ping-pong would only ever be offered
        when a POOL TABLE happened to be placed.

        Asserted at the CALL SITE, because the generic `target + 0xC4` write
        and the bike call sites are all satisfied without this one.
        """
        # The weight is matched as \d+: this assertion is about the fifth
        # argument, the object prerequisite. Pinning the fourth made it fail
        # when the owner raised ping-pong's weight to match the Pool Table's,
        # a change this test does not govern. work/test_pingpong_weight.py
        # pins the weight against the pool table's own default.
        self.assertRegex(
            _source(),
            r"CloneAutonomousCandidateWithWeight\(data, 0x099, 0x0B8, \d+, "
            r"__VF2_PING_PONG_OBJECT__\)",
            "the ping-pong autonomous candidate inherits the Pool Table's "
            "object prerequisite, so it is only offered when a pool table is "
            "placed")

    def test_the_object_id_collides_with_nothing(self):
        """A collision would recreate the bug against a different item."""
        others = {
            patcher.MOBILE_CHAISE_OBJECT,
            patcher.MOBILE_PATIO_UMBRELLA_OBJECT,
            patcher.MOBILE_PICNIC_TABLE_OBJECT,
            patcher.MOBILE_PATIO_TABLE_OBJECT,
            patcher.MOBILE_EXERCISE_BIKE_OBJECT,
        }
        self.assertNotIn(patcher.MOBILE_PING_PONG_OBJECT, others)

    def test_the_cell_value_decodes_to_the_object_id(self):
        """The encoding is CContentMap::HasObject's own, not an assumption."""
        def decode(cell):
            return (((cell >> 11) & 0x40000) | (cell & 0x3F800)) >> 11

        self.assertEqual(
            decode(patcher.MOBILE_PING_PONG_PC_CELL_VALUE),
            patcher.MOBILE_PING_PONG_OBJECT)

    def test_the_shipped_fmap_is_retargeted(self):
        """The copy that writes the table's own file must retarget it."""
        src = _source()
        self.assertIn('"PingPongTableStd.png.fmap": (', src)
        self.assertIn("MOBILE_PING_PONG_DONOR_OBJECT,", src)
        self.assertIn("MOBILE_PING_PONG_OBJECT,", src)
        self.assertIn(
            "carries no object ", src,
            "a donor map that stops carrying the object must fail the build, "
            "not silently leave the table sharing the Pool Table's object")

    def test_the_behaviour_splits_venue_from_donor_object(self):
        """Venue selection uses 0x9A; the exclusion still asks about 0x36.

        Same split the Exercise Bike needed. The donor is the stock
        PlayingPooltable behaviour, and 0x36 is the only object it can be
        diverted through, so the exclusion must keep asking about 0x36 even
        though the table itself has moved.
        """
        src = _source()
        # Both tables' ids, then the own object, then the donor object the
        # exclusion asks about (the invisible sibling rides as altItemId).
        self.assertIn(
            "__VF2_PING_PONG_TABLE_ITEM_ID__, __VF2_INVISIBLE_PING_PONG_TABLE_ITEM_ID__,\n"
            "        __VF2_PING_PONG_OBJECT__, __VF2_PING_PONG_DONOR_OBJECT__,", src)
        self.assertNotIn(
            "__VF2_PING_PONG_TABLE_ITEM_ID__, 0x36, 0x36,", src,
            "the table is back on the Pool Table's object for both questions")

    def test_the_stock_pool_wrapper_does_not_classify_by_our_object(self):
        """The stock wrapper must not probe the ping-pong table at all.

        SUPERSEDED, and this one was mine from earlier the same day. I added a
        test requiring the caption probe to search the table's OWN object
        (0x9A) instead of the Pool Table's 0x36, reasoning that probing 0x36
        after the separation would never match and would silently leave
        "Playing pool" on the ping-pong table.

        That reasoning was right about 0x36 and wrong about the remedy. Review
        caught the rest: VF2RandomPooltableLabel wraps STOCK
        CBehavior::PlayingPooltable, which searches 0x36 and therefore always
        routes to a genuine POOL TABLE. Probing 0x9A there asks about a
        DIFFERENT item than the behaviour routes to, so with both tables placed
        it finds the ping-pong table and overwrites a real stock pool caption
        with a ping-pong label.

        The binding is what settles it: the retarget hooks behaviour 0x099
        (stock pool), while the added table runs on its own 0x0B8 through
        VF2PingPongPlay, which applies the ping-pong label itself. The stock
        wrapper never sees the added table, so it must classify nothing.
        """
        src = _source()
        self.assertNotIn(
            "villager, __VF2_PING_PONG_OBJECT__, "
            "__VF2_PING_PONG_TABLE_ITEM_ID__)", src,
            "the stock pool wrapper is probing the ping-pong table again, "
            "which can only mislabel a stock pool action")
        self.assertNotIn(
            "villager, 0x36, __VF2_PING_PONG_TABLE_ITEM_ID__)", src,
            "the probe is back on the Pool Table's object")

    def test_both_object_macros_are_substituted_from_constants(self):
        """Searched object and declared object must not be able to drift."""
        src = _source()
        self.assertIn(
            '"__VF2_PING_PONG_OBJECT__", f"{MOBILE_PING_PONG_OBJECT:#x}"', src)
        self.assertIn(
            '"__VF2_PING_PONG_DONOR_OBJECT__", '
            'f"{MOBILE_PING_PONG_DONOR_OBJECT:#x}"', src)


if __name__ == "__main__":
    unittest.main()
