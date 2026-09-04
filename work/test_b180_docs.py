#!/usr/bin/env python3
"""The B180 documentation has to keep saying what the build actually does.

These are deliberately not prose checks. Each one ties a documented claim to the
thing that would make it false, so that changing the code without changing the
docs fails here rather than shipping a manual that describes a different build.

The distinction that matters most is between the routed and the unrouted added
furniture. Five items are routed through this patcher's own drop dispatcher;
seven rely on the game's native hotspot path and have NOT been confirmed by a
player. A doc that blurs the two would be claiming something the build cannot
support.
"""
import re
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
TRANSPARENCY = ROOT / "docs" / "Transparency Log.txt"
LEDGER = ROOT / "docs" / "REQUEST_LEDGER.md"

# The dispatcher is written with __VF2_*__ placeholders that only resolve when
# the C is emitted, so route coverage can only be read off the emitted file.
EMITTED = (
    ROOT / "work" / "patched_mobile_furniture_pack_objs" /
    "vf2_mobile_furniture_behaviors.cpp"
)

ROUTED = {
    "InvisiblePicnicTable",
    "InvisiblePatioTable",
    "InvisibleLounger",
    "InvisibleSpaLounger",
    "SpaLoungerStd",
}
UNROUTED = {
    "InvisibleKiddiePool",
    "InvisibleFullSizePool",
    "InvisibleHammock",
    "InvisibleYogaEquipment",
    "ExerciseBikeStd",
    "HomeGymSystemStd",
    "PingPongTableStd",
}


def _added_items():
    items = {}
    for table in (patcher.NEW_FURNITURE_ITEMS, patcher.INVISIBLE_OUTDOOR_ITEMS):
        for item in table:
            items[item["name"]] = item["item_id"]
    return items


class TestTheRoutedAndUnroutedSplitIsReal(unittest.TestCase):
    def test_the_two_sets_cover_every_added_item_exactly_once(self):
        # If an item is added or renamed, this fails and the docs get revisited
        # rather than quietly going stale.
        self.assertEqual(ROUTED | UNROUTED, set(_added_items()))
        self.assertEqual(ROUTED & UNROUTED, set())

    def test_the_docs_do_not_claim_the_unrouted_seven_are_confirmed(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        row = next(
            line for line in ledger.splitlines()
            if "Stock-donor added furniture" in line
        )
        self.assertIn("Needs player confirmation", row)
        self.assertIn("HandleDropOnHotSpot", row)
        # And every one of the seven is named, so none is quietly dropped from
        # the outstanding list.
        for name, item_id in _added_items().items():
            if name in UNROUTED:
                with self.subTest(item=name):
                    self.assertIn(f"0x{item_id:03X}", row)


class TestTransparencyLogMatchesTheBuild(unittest.TestCase):
    def test_it_records_the_b180_sections(self):
        text = TRANSPARENCY.read_text(encoding="utf-8")
        for heading in (
            "B180 added furniture drop routing",
            "B180 added-furniture action labels",
            "B180 store checkmarks from live state",
            "B180 hairstyle store icons",
            "B180 Spa Lounger",
            "B180 picnic and patio props not shipped",
            "B180 verification method",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, text)

    def test_the_props_entry_states_the_real_engine_bound(self):
        # The bound is why the props are absent. If someone later raises it,
        # this sentence has to change with it.
        text = TRANSPARENCY.read_text(encoding="utf-8")
        self.assertIn("0x00 through 0x54 only", text)
        self.assertIn("0x55", text)
        self.assertIn("0x56", text)

    def test_it_does_not_claim_an_unbuilt_bundle(self):
        text = TRANSPARENCY.read_text(encoding="utf-8")
        self.assertIn(
            "No B180 bundle is linked, packaged, or published", text
        )


class TestReadmeMatchesTheBuild(unittest.TestCase):
    def test_it_describes_the_added_furniture_counts(self):
        text = README.read_text(encoding="utf-8")
        invisible = len(patcher.INVISIBLE_OUTDOOR_ITEMS)
        visible = len(patcher.NEW_FURNITURE_ITEMS)
        self.assertIn(f"Eight outdoor pieces", text)
        self.assertEqual(invisible, 8, "README says eight invisible pieces")
        self.assertIn("Four new visible furniture items", text)
        self.assertEqual(visible, 4, "README says four new visible items")

    def test_it_lists_the_labels_that_actually_ship(self):
        text = README.read_text(encoding="utf-8")
        for label in (
            "Playing ping-pong",
            "Using the exercise bike",
            "Doing high-intensity cycling",
        ):
            with self.subTest(label=label):
                self.assertIn(label, text)

    def test_the_removed_label_is_gone_from_docs_and_source(self):
        # Removed at the owner's request. A doc still advertising it would be
        # describing a build that no longer exists.
        source = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
            encoding="utf-8"
        )
        for name, text in (
            ("README", README.read_text(encoding="utf-8")),
            ("patch source", source),
        ):
            with self.subTest(where=name):
                self.assertNotIn("Rallying back and forth", text)

    def test_the_checkmark_section_names_the_reversible_rows(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("Which store rows show a checkmark", text)
        # The point of the section is that drawing and clicking disagree on
        # purpose; losing that sentence loses the reason.
        self.assertIn("still reads the real answer", text)


class TestHairstyleIconDocsMatchTheConstants(unittest.TestCase):
    def test_the_documented_frame_is_the_one_the_build_cuts(self):
        text = TRANSPARENCY.read_text(encoding="utf-8")
        frame = patcher.HEAD_STORE_ICON_FRAME
        count = patcher.HEAD_STORE_ICON_FRAME_COUNT
        width, height = patcher.HEAD_STORE_ICON_CELL_SIZE
        self.assertIn(f"frame {frame} of {count}", text)
        self.assertIn(f"{width}x{height}", text)

    def test_the_engine_cell_is_still_documented_as_retained(self):
        # It stays correct for indexing even though it is wrong for cutting,
        # which is exactly the confusion that caused the sliced icons.
        text = TRANSPARENCY.read_text(encoding="utf-8")
        cell_w, cell_h = patcher.HEAD_STORE_CELL_SIZE
        self.assertIn(f"{cell_w}x{cell_h}", text)
        self.assertNotEqual(
            patcher.HEAD_STORE_CELL_SIZE, patcher.HEAD_STORE_ICON_CELL_SIZE
        )


if __name__ == "__main__":
    unittest.main()
