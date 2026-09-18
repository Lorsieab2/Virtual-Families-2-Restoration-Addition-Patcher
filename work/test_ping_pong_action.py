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
        body = re.search(
            r"VF2RandomPooltableLabel\(CVillager &villager\)\n\{(.*?)\n\}",
            src, re.S,
        ).group(1)
        # The guard reads onPingPong, which prefers the table the engine's
        # route actually chose and falls back to the pingPong pre-probe when
        # nothing was recorded. It was a bare "if (!pingPong)" before that
        # correction; the property pinned here -- a stock pool table returns
        # before any label is applied -- is unchanged, and is now reached on
        # the routed answer rather than on a stale nearest-match.
        self.assertIn("if (!onPingPong)", body)
        # The early return must come before any label is applied.
        #
        # Found by matching the CALL SHAPE rather than one helper's name.
        # This pinned "VF2ApplyRememberedOrRandomLabel" and went red when
        # that call was renamed to VF2ApplyVenueLabel here -- while the
        # behaviour it protects was completely unchanged. The property is
        # that a stock table returns before ANY label is applied, and which
        # helper applies it is not what this test is for.
        refuse = body.index("if (!onPingPong)")
        applications = [
            match.start()
            for match in re.finditer(r"\bVF2Apply\w*Label\w*\(", body)
        ]
        self.assertTrue(
            applications,
            "no label application found; if the mechanism changed name AND "
            "shape, this test needs rewriting rather than relaxing",
        )
        self.assertLess(
            refuse, min(applications),
            "a pool table must return before the ping-pong label is applied",
        )

    def test_the_table_is_identified_before_the_behaviour_runs(self):
        # LinkPeepToFurniture reports the table the plan will use. Asking
        # afterwards could observe a different link.
        body = re.search(
            r"VF2RandomPooltableLabel\(CVillager &villager\)\n\{(.*?)\n\}",
            _source(), re.S,
        ).group(1)
        probe = body.index("VF2LinkedFurnitureItemIs")
        native = body.index("VF2RunNativeBehaviorAndChangedLabel")
        self.assertLess(probe, native)


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
    def test_it_matches_the_ping_pong_item_id(self):
        self.assertEqual(patcher.PING_PONG_TABLE_ITEM_ID, 0x32E)
        # The generated C interpolates the constant, so the literal appears in
        # the f-string template as the placeholder rather than the value.
        self.assertIn(
            # SUPERSEDED, recorded rather than deleted (AGENTS.md 11): this
            # was `villager, 0x36, ...`, the POOL TABLE's object. Correct only
            # while the Ping-Pong Table borrowed it. The table now declares its
            # own 0x9A, so probing 0x36 would match only genuine pool tables,
            # never the ping-pong item id, and would silently leave "Playing
            # pool" on the ping-pong table. VF2LinkedFurnitureItemIs's own
            # comment warns that getting this object wrong "fails silently".
            "villager, __VF2_PING_PONG_OBJECT__, "
            "__VF2_PING_PONG_TABLE_ITEM_ID__)",
            _source(),
            "the wrapper must compare against the derived item id",
        )

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

    def test_the_wrapper_decides_from_its_own_probe(self):
        body = self.wrapper_body()
        self.assertIn(
            "VF2LinkedFurnitureItemIs(" + NL
            + "        villager, __VF2_PING_PONG_OBJECT__, "
            + "__VF2_PING_PONG_TABLE_ITEM_ID__)", body,
            "the wrapper no longer asks the same question PlayingPooltable "
            "asks, so it cannot agree with the table the engine picks")
        self.assertIn("bool const onPingPong = pingPong;", body)
        self.assertIn("if (!onPingPong) {", body)

    def test_the_probe_runs_before_the_native_behaviour(self):
        """PlayingPooltable samples FeetPos and captions before PlanToGo, so a
        probe taken afterwards would sample a different moment."""
        body = self.wrapper_body()
        self.assertLess(
            body.index("VF2LinkedFurnitureItemIs"),
            body.index("VF2RunNativeBehaviorAndChangedLabel"),
            "the probe must be taken before the native behaviour runs")

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
        self.assertIn(
            "__VF2_PING_PONG_TABLE_ITEM_ID__, __VF2_PING_PONG_OBJECT__,", src)
        self.assertIn("__VF2_PING_PONG_DONOR_OBJECT__,", src)
        self.assertNotIn(
            "__VF2_PING_PONG_TABLE_ITEM_ID__, 0x36, 0x36,", src,
            "the table is back on the Pool Table's object for both questions")

    def test_the_caption_probe_searches_the_tables_own_object(self):
        """The label probe must not keep hardcoding the Pool Table's object.

        VF2LinkedFurnitureItemIs takes the object as a parameter precisely
        because getting it wrong FAILS SILENTLY -- its own comment records an
        earlier round where hardcoding 0x36 made the bike probe search for a
        pool table, never match, and leave the wrong labels in place.

        After the separation the mirror mistake is live: probing 0x36 for the
        ping-pong item would find only genuine pool tables, never match, and
        silently leave "Playing pool" on the ping-pong table.
        """
        src = _source()
        self.assertIn(
            "villager, __VF2_PING_PONG_OBJECT__, "
            "__VF2_PING_PONG_TABLE_ITEM_ID__)", src,
            "the caption probe searches the wrong object, so the ping-pong "
            "label can never be applied")
        self.assertNotIn(
            "villager, 0x36, __VF2_PING_PONG_TABLE_ITEM_ID__)", src,
            "the probe still hardcodes the Pool Table's object")

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
