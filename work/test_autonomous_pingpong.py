#!/usr/bin/env python3
"""Villagers play ping-pong on their own, and only when a table is placed.

Owner: "i want them to play it autonomously and only when a pingpong table
exists in the house." And, on whether several villagers may use one table at
once: "i don't care if multiple villagers line up at the table simultaneously."

WHY IT WAS NOT AUTONOMOUS. VF2PingPongPlay had exactly one caller, the drop
dispatcher in VF2HandleDropOnMobileFurniture, so the only way to start a game
was to pick a villager up and drop them on the table. Nothing in the autonomous
selector offered it.

HOW THE "ONLY WHEN PLACED" HALF IS SATISFIED. The selector already gates every
candidate on ContentMap.ObjectExists(candidate.object). The Ping-Pong Table has
its OWN object, 0x9A, split off the stock Pool Table's 0x36 so the two stopped
being indistinguishable -- and nothing else answers to it. So the generic gate
IS the requirement, with no extra flag. That is not true of eObjectChaise,
which every lounger shares and which is why the spa lounger candidate needs the
separate spaLoungerInWorld test; the contrast is asserted below so nobody
"simplifies" the spa gate away by copying this one.

THE BOUNDS BUG THIS SUITE EXISTS FOR. Adding the candidate meant adding a
fifteenth weight. The weights array, its initialiser table and the initialising
loop bound were three separate literals, and the first draft of this change
updated only the selector -- reading weights[14] out of a weights[14] array.
That is silent at compile time and yields a garbage weight at runtime. The
count tests below tie all four numbers to the spec table so the next candidate
cannot repeat it.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402

PING_PONG_OBJECT = 0x9A


def _source():
    return GEN.read_text(encoding="utf-8")


def _selector(text):
    """The body of the external autonomous selector."""
    start = text.index("    unsigned int externalWeight = 0;")
    return text[text.rindex("static bool", 0, start):text.index("\n}\n", start)]


class TheSpecEntry(unittest.TestCase):
    """The catalogue row that makes ping-pong an autonomous candidate."""

    def setUp(self):
        self.specs = patcher.MOBILE_FURNITURE_EXTERNAL_AUTONOMOUS_SPECS
        self.entry = next(
            (s for s in self.specs if s.get("handler") == "VF2PingPongPlay"), None)

    def test_ping_pong_is_an_autonomous_candidate(self):
        self.assertIsNotNone(
            self.entry, "VF2PingPongPlay is not in the autonomous catalogue")

    def test_it_is_bound_to_the_tables_own_object(self):
        # 0x9A, not the stock Pool Table's 0x36. Binding to 0x36 would offer
        # ping-pong whenever a POOL table was placed, which is the very
        # confusion that object was split to end.
        self.assertEqual(self.entry["object"], PING_PONG_OBJECT)
        self.assertEqual(self.entry["object"], patcher.MOBILE_PING_PONG_OBJECT)
        self.assertEqual(self.entry["object_enum"], "eObjectPingPongTable")

    def test_it_carries_no_mobile_id(self):
        # This patcher's own item; the mobile game has no ping-pong row to
        # port, and a fabricated id could collide with a real registration.
        self.assertIsNone(self.entry["mobile_id"])

    def test_the_enum_value_matches_the_object(self):
        src = _source()
        match = re.search(r"eObjectPingPongTable = (0x[0-9A-Fa-f]+),", src)
        self.assertIsNotNone(match, "eObjectPingPongTable is not declared")
        self.assertEqual(int(match.group(1), 16), PING_PONG_OBJECT)


class TheWeightTableIsInBounds(unittest.TestCase):
    """Four numbers that must agree, and used not to.

    MOBILE_FURNITURE_EXTERNAL_AUTONOMOUS_SPECS is the source of truth; the C++
    array size, its initialiser table and every index the selector reads are
    checked against it.
    """

    def setUp(self):
        self.src = _source()
        self.count = len(patcher.MOBILE_FURNITURE_EXTERNAL_AUTONOMOUS_SPECS)

    def test_the_weights_array_has_one_slot_per_candidate(self):
        match = re.search(r"unsigned int weights\[(\d+)\];", self.src)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), self.count)

    def test_the_base_weight_table_has_one_entry_per_candidate(self):
        match = re.search(r"unsigned int bases\[(\d+)\] = \{", self.src)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), self.count)
        # And it really holds that many values, not just that many declared.
        # Comments are stripped first: they explain the weights and therefore
        # quote them, so counting numerals raw over-counts (this assertion
        # failed on its own first run for exactly that reason).
        body = self.src[match.end():self.src.index("};", match.end())]
        body = re.sub(r"//[^\n]*", "", body)
        values = re.findall(r"\b\d{3,6}\b", body)
        self.assertEqual(len(values), self.count)

    def test_every_selector_index_is_within_the_array(self):
        indices = sorted(
            int(m) for m in re.findall(r"mobileWeights->weights\[(\d+)\]", self.src))
        self.assertTrue(indices, "the selector reads no weights at all")
        self.assertLess(max(indices), self.count,
                        "a selector candidate reads past the end of weights[]")
        # Every slot is used exactly once: a gap means a candidate silently
        # shares another's weight, a repeat means two candidates do.
        self.assertEqual(indices, list(range(self.count)))

    def test_the_initialiser_loop_cannot_drift_from_the_table(self):
        # The bound is sizeof-derived rather than a literal, so growing bases[]
        # grows the loop. A literal here is what left weights[14] uninitialised
        # while the selector read it.
        self.assertIn("index < sizeof(bases) / sizeof(bases[0]);", self.src)


class ThePresenceGate(unittest.TestCase):
    """Offered only when a ping-pong table is actually in the house."""

    def setUp(self):
        self.selector = _selector(_source())

    def test_every_candidate_is_gated_on_its_object_existing(self):
        # The generic gate. For ping-pong this is the WHOLE requirement,
        # because 0x9A belongs to no other item.
        self.assertIn("ContentMap.ObjectExists(candidate.object)", self.selector)

    def test_the_ping_pong_candidate_is_bound_to_its_own_object(self):
        self.assertIn("CContentMap::eObjectPingPongTable", self.selector)
        self.assertIn("VF2PingPongPlay", self.selector)

    def test_the_shared_chaise_object_still_keeps_its_extra_item_check(self):
        # eObjectChaise is shared by EVERY lounger, so ObjectExists alone would
        # offer a spa treatment in a house with only ordinary loungers. This
        # asserts the contrast, so the ping-pong gate is not taken as licence
        # to drop the spa lounger's own test.
        self.assertIn("spaLoungerInWorld", self.selector)
        self.assertIn("FurnitureManager.IsInWorld(", _source())


class TheDropRouteIsUnchanged(unittest.TestCase):
    """Dropping a villager on the table still works exactly as before."""

    def test_the_drop_dispatcher_still_routes_ping_pong(self):
        src = _source()
        self.assertIn("VF2PingPongPlay(villager);", src)
        self.assertIn("candidate == __VF2_PING_PONG_TABLE_ITEM_ID__", src)
        self.assertIn("candidate == __VF2_INVISIBLE_PING_PONG_TABLE_ITEM_ID__", src)

    def test_the_autonomous_scope_validator_still_passes(self):
        # Rejects any autonomous binding for a native family-wide route.
        # Ping-pong is this patcher's own item, so it must not trip it.
        patcher.validate_mobile_furniture_autonomous_scope()


if __name__ == "__main__":
    unittest.main()
