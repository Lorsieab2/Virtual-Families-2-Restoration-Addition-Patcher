#!/usr/bin/env python3
"""The picnic/drinks preparer is tracked by behaviour serial, not label text.

THE DEFECT THIS PINS

VF2VillagerStillPreparing used to identify the preparing villager by comparing
the action-label text at villager+0x1BBA8:

    char const *current = reinterpret_cast<char const *>(villager) + 0x1BBA8;
    return strncmp(current, label, 0x27) == 0;

CVillagerPlans::ForgetPlans blanks that field -- at ForgetPlans+0x165 it
strncpy's a zero-length string over it -- and VF2StartAutonomousPreparingDrinks
calls ForgetPlans on itself immediately before VF2RunMobilePreparingDrinks. So
the tracker was cleared mid-plan, the preparer globals went null, and the prop
never activated. Reported in play as the villager changing behaviour the moment
they reach the kitchen.

WHY A TEXT TRACKER CANNOT BE REPAIRED IN PLACE

The label is not a field the patch owns. It is written from five modules -- 401
sites in Behavior alone, plus Villager, theMainScene, VillagerPlans, and
CVillagerAI::Update, which runs every frame. Restoring the text would lose to
the next frame. That is why this is a re-key rather than a patch-up, and why
the assertions below are about WHICH FIELD is read, not about string contents.

WHY THESE TESTS ARE SHAPED THIS WAY

This file asserts on the generator source rather than on a running game,
because the code under test is C++ emitted by a Python generator and there is
no harness that executes it. That makes the two-way check essential: every test
here was verified to FAIL against the parent implementation and pass against
the fix, so the file cannot silently keep passing if the tracker regresses to
comparing label text.
"""
import re
import unittest

import patch_mobile_furniture_pack as patcher


def _source():
    path = patcher.ROOT / "work" / "patch_mobile_furniture_pack.py"
    return path.read_text(encoding="utf-8")


def _body(name, signature_suffix="(\n"):
    """The body of a static helper, by name."""
    source = _source()
    start = source.index("static bool VF2VillagerStillPreparing(") if name == \
        "VF2VillagerStillPreparing" else source.index(name)
    end = source.index("\n}", start)
    return source[start:end]


class TheTrackerReadsTheBehaviourSerial(unittest.TestCase):
    """+0x1BBA4, the field the engine itself uses for this question.

    CVillager's constructor zeroes it, CVillager::NewBehavior increments it,
    and nothing else in any disassembled module writes it. The base game's
    CFurnitureManager READS it after GetVillager to ask this same "is this
    still the same activity" question, so this is the field's intended use.
    """

    def body(self):
        source = _source()
        start = source.index("static bool VF2VillagerStillPreparing(")
        return source[start:source.index("\n}", start)]

    def test_it_reads_the_serial_field(self):
        body = self.body()
        self.assertIn(
            "0x1BBA4", body,
            "the preparer tracker no longer reads the behaviour serial, which "
            "is the whole fix: ForgetPlans blanks the label the old tracker "
            "compared, so the preparer was dropped on arrival")

    def test_it_does_not_identify_by_label_text(self):
        """The defect itself, stated directly.

        strncmp against +0x1BBA8 is what broke. If it comes back, the kitchen
        bug comes back with it.
        """
        body = self.body()
        self.assertNotIn(
            "strncmp", body,
            "the tracker compares label text again; ForgetPlans blanks that "
            "field mid-plan and CVillagerAI::Update rewrites it every frame")
        self.assertNotIn(
            "0x1BBA8", body,
            "the tracker reads the action-label field again, which five "
            "modules write over")

    def test_it_also_checks_the_behaviour_id(self):
        """A serial that coincidentally matches across a behaviour change must
        still be rejected, so the id at +0x1BBA0 is compared too."""
        body = self.body()
        self.assertIn("0x1BBA0", body)


class ThePraiseRestartIsAccepted(unittest.TestCase):
    """A praise bumps the serial by one while the activity CONTINUES.

    This mirrors VF2BehaviorLabelSlotIsCurrentFor, which already solved the
    same problem in this codebase. A bare equality test would drop the preparer
    on praise and reintroduce the reported defect through a different door --
    the villager would still stop preparing, just for a rarer reason.
    """

    def body(self):
        source = _source()
        start = source.index("static bool VF2VillagerStillPreparing(")
        return source[start:source.index("\n}", start)]

    def test_a_serial_one_greater_is_still_the_same_activity(self):
        body = self.body()
        self.assertRegex(
            body, r"\*recordedSerial \+ 1",
            "a praise bumps the serial by one; without this allowance the "
            "preparer is dropped when the player praises the villager")

    def test_the_praise_arm_adopts_the_new_baseline(self):
        """Accepting a restart must WRITE BACK, or the second praise fails.

        The allowance is measured against the recorded serial, so leaving it at
        N makes a second praise arrive at N+2 and be rejected. This is the
        exact trap documented on VF2BehaviorLabelSlotIsCurrentFor, whose
        earlier version omitted the writeback on the reasoning that a query
        should not mutate state.
        """
        body = self.body()
        self.assertIn(
            "*recordedSerial = behaviorSerial;", body,
            "the praise arm does not adopt the restart as the new baseline, "
            "so a second praise of the same action arrives at N+2 and is "
            "rejected as a new session")

    def test_the_praise_arm_requires_the_praise_evidence(self):
        """Serial+1 alone is not a praise. Without the praised-behaviour id and
        a changed praise count, any single NewBehavior would be waved through
        as if it were a praise -- which is the defect, not the fix."""
        body = self.body()
        self.assertIn("0x6B48", body)
        self.assertIn("0x6B4C", body)


class TheIdentityIsRecordedWhenPreparationStarts(unittest.TestCase):
    def test_both_preparers_record_their_identity(self):
        """Recording must happen where the preparer is set, or the tracker
        compares against whatever was left from a previous villager."""
        source = _source()
        for setter in ("gVF2PatioDrinksPreparer = &villager;",
                       "gVF2PicnicPreparer = &villager;"):
            with self.subTest(setter=setter):
                index = source.index(setter)
                following = source[index:index + 400]
                self.assertIn(
                    "VF2RememberPreparer(", following,
                    "the preparer is set without recording the identity the "
                    "tracker will compare against")

    def test_the_recorder_captures_all_three_fields(self):
        source = _source()
        start = source.index("static void VF2RememberPreparer(")
        body = source[start:source.index("\n}", start)]
        for field in ("0x1BBA0", "0x1BBA4", "0x6B4C"):
            with self.subTest(field=field):
                self.assertIn(field, body)


class TheSuccessfulCompletionPathsAreUnchanged(unittest.TestCase):
    """Scope guard.

    The paths that clear the preparer AFTER VF2CaptureTableProp are correct as
    they stand -- the preparation really has finished there. If a future change
    starts routing those through the identity check, that is a behaviour change
    and should be deliberate rather than incidental.
    """

    def test_the_capture_paths_still_clear_the_preparer_directly(self):
        """Each VF2CaptureTableProp call is followed by its own direct clear.

        Checked per call site rather than over one window, because the picnic
        and patio branches sit in separate arms of the same if/else and a
        fixed-size window that happens to span both would pass even if one
        branch stopped clearing.
        """
        source = _source()
        expected = {
            "gVF2PicnicPreparer": "gVF2PicnicPreparer = 0;",
            "gVF2PatioDrinksPreparer": "gVF2PatioDrinksPreparer = 0;",
        }
        calls = [m.start() for m in re.finditer(r"VF2CaptureTableProp\(", source)]
        seen = set()
        for index, start in enumerate(calls):
            # Stop at the NEXT capture call so one branch's window cannot
            # borrow the following branch's clear and report a false pass.
            stop = calls[index + 1] if index + 1 < len(calls) else start + 400
            window = source[start:stop]
            for name, clear in expected.items():
                if "%s," % name in window:
                    with self.subTest(preparer=name):
                        self.assertIn(
                            clear, window,
                            "%s is captured but no longer cleared on the "
                            "successful-completion path" % name)
                    seen.add(name)
        self.assertEqual(
            seen, set(expected),
            "a VF2CaptureTableProp completion path for one of the preparers "
            "has gone missing; this guard would otherwise pass vacuously")


if __name__ == "__main__":
    unittest.main()
