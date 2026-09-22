#!/usr/bin/env python3
"""Ping-pong is chosen as often as pool, and still only when a table is placed.

Owner: "Raise pingpong weight to same as pool table."

WHAT WAS WRONG. Ping-pong was already an autonomous candidate -- cloned from
the Pool Table's behaviour 0x099 into 0x0B8 by VF2EnableAutonomousCandidates --
but at weight 450, while the Pool Table's own candidate is enabled by
EnableAllAgesAutonomousCandidate, which defaults to 3000. A ping-pong table was
therefore offered roughly a seventh as often as the pool table it was cloned
from, which read in play as villagers ignoring it.

WHAT THIS SUITE PINS. The two numbers must stay equal, and they are derived
from two independent places in the source -- the clone call and the default
helper -- so they cannot agree merely by construction. It also pins the object
prerequisite, because the weight and the gate are easy to confuse: the weight
decides HOW OFTEN the action is chosen when a table exists, the object decides
WHETHER it is offered at all. Raising one must not disturb the other.

NOT TESTED HERE. Whether a villager actually walks over and plays is the
owner's playtest; a weight in a candidate record cannot establish player-facing
behaviour.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))

POOL_BEHAVIOR = 0x099
PING_PONG_BEHAVIOR = 0x0B8
PING_PONG_OBJECT = 0x9A


def _source():
    return GEN.read_text(encoding="utf-8")


def _pool_default_weight(src):
    """The weight EnableAllAgesAutonomousCandidate gives a stock candidate."""
    match = re.search(
        r"static void EnableAllAgesAutonomousCandidate\(unsigned char \*villager, unsigned int behavior\)\s*\{\s*"
        r"EnableAllAgesAutonomousCandidateWithWeight\(villager, behavior, (\d+)\);",
        src)
    if match is None:
        raise AssertionError("EnableAllAgesAutonomousCandidate's default weight is not readable")
    return int(match.group(1))


def _ping_pong_clone(src):
    """(donor, target, weight, object) from the ping-pong clone call."""
    match = re.search(
        r"CloneAutonomousCandidateWithWeight\(data, (0x[0-9A-Fa-f]+), (0x[0-9A-Fa-f]+), (\d+), "
        r"__VF2_PING_PONG_OBJECT__\);",
        src)
    if match is None:
        raise AssertionError("the ping-pong autonomous clone call is not present")
    return (int(match.group(1), 16), int(match.group(2), 16), int(match.group(3)))


class ThePingPongWeight(unittest.TestCase):
    def setUp(self):
        self.src = _source()

    def test_the_pool_table_is_enabled_at_the_default_weight(self):
        # The comparison target. If the pool table ever stops using the
        # default helper this test must be revisited rather than silently
        # comparing against a stale number.
        self.assertIn(
            f"EnableAllAgesAutonomousCandidate(data, {POOL_BEHAVIOR:#05x}); // PlayingPooltable",
            self.src)

    def test_ping_pong_matches_the_pool_table_weight(self):
        pool = _pool_default_weight(self.src)
        donor, target, weight = _ping_pong_clone(self.src)
        self.assertEqual(donor, POOL_BEHAVIOR)
        self.assertEqual(target, PING_PONG_BEHAVIOR)
        self.assertEqual(
            weight, pool,
            f"ping-pong is weighted {weight} but the pool table it clones is {pool}")

    def test_the_weight_is_not_the_old_value(self):
        # A direct guard on the reported symptom, independent of the helper
        # parse above: 450 was roughly a seventh of the pool table's 3000.
        _, _, weight = _ping_pong_clone(self.src)
        self.assertNotEqual(weight, 450)

    def test_the_object_prerequisite_is_untouched(self):
        # The weight decides how OFTEN; the object decides WHETHER. 0x9A
        # belongs to the Ping-Pong Table alone, so this is what keeps the
        # candidate out of houses with no table. Raising the weight must not
        # disturb it.
        self.assertIn("MOBILE_PING_PONG_OBJECT = 0x9A", self.src)
        clone = re.search(
            r"CloneAutonomousCandidateWithWeight\(data, 0x099, 0x0B8, \d+, (\w+)\);", self.src)
        self.assertIsNotNone(clone)
        self.assertEqual(clone.group(1), "__VF2_PING_PONG_OBJECT__")
        # And the helper still applies a non-zero prerequisite rather than
        # inheriting the donor's, which is the defect shape the Home Gym and
        # Yoga candidates documented.
        self.assertIn("if (objectPrerequisite != 0) {", self.src)
        self.assertIn("*(unsigned int *)(target + 0xC4) = objectPrerequisite;", self.src)


class BothTableVariantsAreCovered(unittest.TestCase):
    """Visible AND invisible ping-pong tables both satisfy the gate.

    Owner: "make sure the pool table fix applies to both visible and
    invisible variants." The candidate is gated on ObjectExists(0x9A), so
    coverage is decided by which fmaps carry that object -- not by the item
    ids, which differ. Both maps must declare it or the invisible table would
    be placed without ever making the behaviour eligible.
    """

    def setUp(self):
        import patch_mobile_furniture_pack as patcher
        self.assets = patcher.OUT / "Assets"
        needed = ["PingPongTableStd.png.fmap", "InvisiblePingPongTable.png.fmap"]
        if not all((self.assets / n).is_file() for n in needed):
            self.skipTest("the built Assets do not hold both ping-pong maps; run the generator")

    @staticmethod
    def _objects(path):
        import struct
        data = path.read_bytes()
        cols, rows = struct.unpack_from("<ii", data, 24)
        cells = struct.unpack_from("<%dI" % (cols * rows), data, 32)
        found = {}
        for cell in cells:
            obj = (((cell >> 11) & 0x40000) | (cell & 0x3F800)) >> 11
            if obj:
                found[obj] = found.get(obj, 0) + 1
        return found

    def test_both_maps_declare_the_ping_pong_object(self):
        for name in ("PingPongTableStd", "InvisiblePingPongTable"):
            with self.subTest(table=name):
                objects = self._objects(self.assets / f"{name}.png.fmap")
                self.assertIn(
                    PING_PONG_OBJECT, objects,
                    f"{name} does not declare object {PING_PONG_OBJECT:#x}, so placing it "
                    "would never make the autonomous ping-pong candidate eligible")
                self.assertGreater(objects[PING_PONG_OBJECT], 0)

    def test_neither_map_still_declares_the_pool_table_object(self):
        # 0x36 is the stock Pool Table's object. Either map still carrying it
        # would re-create the "invisible ping-pong plays pool" confusion that
        # the object split was made to end.
        for name in ("PingPongTableStd", "InvisiblePingPongTable"):
            with self.subTest(table=name):
                self.assertNotIn(0x36, self._objects(self.assets / f"{name}.png.fmap"))


class TheEmittedUnit(unittest.TestCase):
    """The substituted call must reach the emitted C++, not just the template."""

    def setUp(self):
        import patch_mobile_furniture_pack as patcher
        self.unit = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
        candidates = sorted(pathlib.Path(patcher.PATCHED).glob("*.cpp"))
        if not candidates:
            self.skipTest("no generated units; run the generator first")
        self.text = None
        pattern = re.compile(
            r"CloneAutonomousCandidateWithWeight\(data, 0x099, 0x0[bB]8,", re.I)
        for path in candidates:
            body = path.read_text(encoding="ascii", errors="replace")
            if pattern.search(body):
                self.text = body
                break
        if self.text is None:
            self.skipTest("the ping-pong clone call is not in any emitted unit; run the generator")

    def test_the_emitted_clone_carries_the_new_weight_and_the_object(self):
        pool = _pool_default_weight(_source())
        match = re.search(
            r"CloneAutonomousCandidateWithWeight\(data, 0x099, 0x0[bB]8, (\d+), (0x[0-9A-Fa-f]+)\);",
            self.text)
        self.assertIsNotNone(match, "the emitted clone call did not parse")
        self.assertEqual(int(match.group(1)), pool)
        self.assertEqual(int(match.group(2), 16), PING_PONG_OBJECT)


if __name__ == "__main__":
    unittest.main()
