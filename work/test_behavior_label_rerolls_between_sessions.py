"""A finished behaviour must not pin its label onto the next one.

The reported symptom was that the Home Gym "only shows one action out of their
full possibilities": a villager whose first visit rolled "Doing crunches" showed
"Doing crunches" for the rest of the game, and the other nine labels never
appeared. Ten labels were built and shipping; only the selection was stuck.

The cause was not the label cache. The cache is keyed on the villager's
behaviour id and serial and expires correctly. The stuck value came from the
PERSISTENT label text at villager+0x1BBA8, which survives the end of a
behaviour. ``VF2CurrentLabelInGroup`` matched that leftover text and reported
"this villager is already doing X", so every applier took its remembered-label
early return and never rolled again.

These tests pin the structural rule that makes the defect impossible: the
persistent label is only ever read behind a cache gate. They are source
contract tests because the emitted C cannot be executed here -- the same
technique the widening-scope and installer-resolution suites use.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
SOURCE = GENERATOR.read_text(encoding="utf-8")

PERSISTENT_LABEL_OFFSET = "0x1BBA8"


def function_body(name):
    """The body of an emitted C function, by name."""
    match = re.search(
        r"^static [\w \*&]*?\b%s\(.*?\n\{(.*?)^\}" % re.escape(name),
        SOURCE,
        re.S | re.M,
    )
    assert match, "emitted C function %s not found" % name
    return match.group(1)


class ThePersistentLabelIsOnlyReadBehindTheCacheGate(unittest.TestCase):
    def test_the_scan_and_the_gate_are_separate_functions(self):
        # The text scan says nothing about WHEN the label was set, so it must
        # not be the thing callers reach for by default.
        self.assertIn("static int VF2ScanLabelGroup(", SOURCE)
        self.assertIn("static bool VF2BehaviorLabelStillFromThisSession(", SOURCE)

    def test_the_gate_asks_the_cache_rather_than_reimplementing_it(self):
        # VF2BehaviorLabelCacheStillActive already compares behaviorId and
        # behaviorSerial and tolerates a praise re-roll. The gate must delegate
        # to it, not grow a second, drifting copy of that rule.
        body = function_body("VF2BehaviorLabelStillFromThisSession")
        self.assertIn("VF2GetCachedBehaviorLabel(villager, cacheTag", body)

    def test_only_the_scan_reads_the_persistent_label_field(self):
        """+0x1BBA8 must not be read by any new ad-hoc matcher.

        This is the test that fails if the fix is reverted: restoring the old
        VF2CurrentLabelInGroup puts a read of the persistent label back into a
        function that has no cache gate.
        """
        # The defect is narrower than "reads the field": it is "matches the
        # field against a MOD LABEL GROUP and concludes the villager must still
        # be doing that". Copying the field, writing it, comparing it to a
        # caller-supplied snapshot, or matching it against fixed NATIVE label
        # ids are all legitimate and unrelated -- VF2CopyRawPraiseLabel,
        # VF2SetActionLabel, VF2BehaviorLabelChangedSince,
        # VF2IsRestingBodyNativeLabel and VF2VillagerStillPreparing all do one
        # of those. Testing for the precise shape keeps this test meaningful
        # instead of freezing a list of names that drifts.
        readers = []
        for name in re.findall(r"^static [\w \*&]*?\b(VF2\w+)\(", SOURCE, re.M):
            body = function_body(name)
            if PERSISTENT_LABEL_OFFSET not in body:
                continue
            compares = re.search(r"\bstrn?cmp\b", body)
            against_a_group = re.search(r"labels\[|kVF2BehaviorLabels_", body)
            if compares and against_a_group:
                readers.append(name)
        self.assertEqual(
            sorted(set(readers) - {"VF2ScanLabelGroup"}),
            [],
            "a function reads the persistent behaviour label at %s without "
            "going through the cache gate; a leftover label from a finished "
            "behaviour will be mistaken for the current one and the group "
            "will stop re-rolling" % PERSISTENT_LABEL_OFFSET,
        )

    def test_every_scan_call_site_is_gated(self):
        """No caller may scan without first proving the cache is still live."""
        for name in ("VF2CurrentLabelInGroup", "VF2CurrentLabelInGroupTagged",
                     "VF2CurrentLabelInGroups2", "VF2CurrentLabelInGroups3"):
            body = function_body(name)
            self.assertIn(
                "VF2BehaviorLabelStillFromThisSession", body,
                "%s scans the persistent label without a cache gate" % name,
            )
            gate = body.index("VF2BehaviorLabelStillFromThisSession")
            scan = body.index("VF2ScanLabelGroup")
            self.assertLess(
                gate, scan,
                "%s scans before it gates, so a stale label still wins" % name,
            )


class TheCacheTagMatchesWhatTheApplierWrote(unittest.TestCase):
    """A gate that looks up the wrong slot re-rolls mid-activity instead.

    The multi-group appliers cache under the FIRST group's address. A chain
    scanning group B or C therefore has to present group A's address, or the
    lookup misses, the villager is treated as new, and the caption changes
    while the action is still running -- the opposite regression.
    """

    def test_the_multi_group_appliers_still_cache_under_the_first_group(self):
        # The premise of the tagging rule. If an applier ever changes its tag,
        # this fails rather than the rule quietly protecting against nothing.
        for name in ("VF2ApplyRememberedOrRandomLabels2",
                     "VF2ApplyRememberedOrRandomLabels3"):
            self.assertIn(
                "int cacheTag = (int)labelsA;", function_body(name),
                "%s no longer caches under the first group" % name,
            )

    def test_the_grouped_resolvers_gate_once_on_the_first_group(self):
        for name in ("VF2CurrentLabelInGroups2", "VF2CurrentLabelInGroups3"):
            self.assertIn(
                "VF2BehaviorLabelStillFromThisSession(villager, (int)labelsA)",
                function_body(name),
                "%s gates on a tag its applier never wrote" % name,
            )

    def test_the_hand_rolled_chains_gate_on_their_applier_tag(self):
        # These predate the grouped helpers and chain the scan by hand. Each
        # follow-on group must borrow group A's tag.
        for resolver, tag in (
            ("VF2CurrentShowerLabel", "kVF2BehaviorLabels_shower_general"),
            ("VF2CurrentSitDownLabel", "kVF2BehaviorLabels_sit_down_general"),
        ):
            body = function_body(resolver)
            follow_on = re.findall(
                r"VF2CurrentLabelInGroupTagged\(villager, \(int\)(\w+),", body)
            self.assertTrue(
                follow_on, "%s stopped tagging its follow-on scans" % resolver)
            self.assertEqual(
                set(follow_on), {tag},
                "%s gates a follow-on group on a tag its applier never wrote"
                % resolver,
            )

    def test_coffee_keeps_its_per_group_tags(self):
        """Coffee is the exception and must stay one.

        VF2ApplyCoffeeLabel rolls from whichever pool the time of day selects
        and caches under THAT pool's address, so no single tag covers it. Each
        group's own address is the tag it was written under.
        """
        body = function_body("VF2CurrentCoffeeLabel")
        self.assertNotIn(
            "VF2CurrentLabelInGroupTagged", body,
            "coffee caches under the group it rolled from, so forcing a single "
            "tag here would miss the slot and re-roll mid-drink",
        )


if __name__ == "__main__":
    unittest.main()
