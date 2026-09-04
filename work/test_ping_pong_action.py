#!/usr/bin/env python3
"""The Ping-Pong Table gets its own behaviour label.

The table borrows CBehavior::PlayingPooltable from the Pool Table, which is
the whole reason it has any interaction at all -- but that behaviour labels its
users "Playing pool". Both tables answer to EObject 0x36, so the behaviour
cannot tell them apart on its own; the placed-furniture record behind the
villager's linked table can.

A stock Pool Table must keep its stock label untouched.
"""
import re
import unittest

import patch_mobile_furniture_pack as patcher


def _source():
    path = patcher.ROOT / "work" / "patch_mobile_furniture_pack.py"
    return path.read_text(encoding="utf-8")


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
        self.assertIn("if (!pingPong)", body)
        # The early return must come before any label is applied.
        refuse = body.index("if (!pingPong)")
        apply_at = body.index("VF2ApplyRememberedOrRandomLabel")
        self.assertLess(
            refuse, apply_at,
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
            "villager, __VF2_PING_PONG_TABLE_ITEM_ID__)",
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
        # Item id at record+0x00 and the in-world flag at record+0x0C are what
        # CFurnitureManager::PtOnFurniture and FurnitureHasObject both use;
        # record+0x10 is an orientation index, not a point, so the lookup goes
        # through PtOnFurniture rather than matching coordinates by hand.
        body = re.search(
            r"VF2LinkedFurnitureItemIs\(CVillager &villager, int itemId\)\n\{(.*?)\n\}",
            _source(), re.S,
        )
        self.assertIsNotNone(body)
        text = body.group(1)
        self.assertIn("VF2BehaviorPtOnFurnitureIndex", text)
        self.assertIn("manager + 0x1004", text)
        self.assertIn("manager + 0x1008 + slot * 0x40", text)
        self.assertIn("record + 0x0C", text)
        self.assertNotIn(
            "record + 0x10", text,
            "record+0x10 is an orientation index, not the placed point",
        )

    def test_the_probe_bounds_the_slot(self):
        text = re.search(
            r"VF2LinkedFurnitureItemIs\(CVillager &villager, int itemId\)\n\{(.*?)\n\}",
            _source(), re.S,
        ).group(1)
        self.assertIn("slot < 0 || slot >= count", text)


if __name__ == "__main__":
    unittest.main()
