"""The Exercise Bike uses the BASE-GAME TREADMILL sequence, with no seated pose.

THE OWNER'S INSTRUCTION, which supersedes the earlier seated-pose design:

    "for the exercise bike animations just use the base-game treadmill
     animation sequence and orientation. forget the sitting animation."

WHAT CAME BEFORE, and why it is gone. The bike originally rode standing,
because both handlers delegate to a treadmill donor and set no pose. That was
reported as a bug, and the fix retargeted the donors' own PlanToWait callsites
to VF2PlanToWaitSeatedOnBike so the rider sat while the donor kept its
durations and animations. In play that seated pose did not line up with the
bike art -- the villager read as standing inside the machine -- so the owner
asked for the stock treadmill presentation instead.

So the requirement inverted. These tests now pin the ABSENCE of the seated
machinery, because a silent reintroduction would bring the misaligned pose
back. The donors run their stock plans untouched: same animation sequence,
same orientation, same durations as the base game.

What is NOT affected, and must stay: the bike keeps its own LABELS ("Using the
exercise bike", "Doing high-intensity cycling") and its own item identity. Only
the pose substitution was removed.

These tests read the generator source that emits the C++, because that is the
artifact which reaches the build.
"""
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(ROOT, "patch_mobile_furniture_pack.py")
SOURCE = io.open(GEN, encoding="utf-8").read()

HANDLERS = ("VF2ExerciseBikeWalk", "VF2ExerciseBikeRun")


def handler_body(name):
    m = re.search(
        r'extern "C" void __cdecl %s\(CVillager &villager\)\n\{(.*?)\n\}' % name,
        SOURCE, re.S)
    assert m, "handler %s not found in the generator" % name
    return m.group(1)


class TheSeatedPoseIsGone(unittest.TestCase):
    """The pose substitution must not come back by accident."""

    def test_neither_handler_opens_a_seated_window(self):
        for name in HANDLERS:
            with self.subTest(handler=name):
                body = handler_body(name)
                self.assertNotIn(
                    "VF2OpenBikeSeatedWindow", body,
                    "%s still opens the seated window; the owner asked for "
                    "the stock treadmill sequence with no sitting animation"
                    % name)
                self.assertNotIn(
                    "VF2EndBikeSeated", body,
                    "%s still closes a seated window that is no longer opened"
                    % name)

    def test_no_wait_callsite_is_retargeted_to_a_seated_helper(self):
        # The seated pose was installed by substituting the donors' own
        # PlanToWait calls. If that retarget returns, the misaligned pose
        # returns with it.
        self.assertNotIn(
            "_VF2PlanToWaitSeatedOnBike", SOURCE,
            "the seated PlanToWait helper is referenced again; the bike must "
            "run the treadmill donors' stock waits")
        self.assertNotIn(
            "seated PlanToWait", SOURCE,
            "a seated PlanToWait retarget entry is back in the table")

    def test_the_donors_keep_their_own_plans(self):
        # Each handler still runs a treadmill donor -- that is where the
        # animation sequence, orientation and duration come from.
        self.assertIn("CBehavior::WorkoutTreadmill",
                      handler_body("VF2ExerciseBikeWalk"))
        self.assertIn("CBehavior::RunningOnTreadmill",
                      handler_body("VF2ExerciseBikeRun"))


class TheBikeKeepsItsOwnIdentity(unittest.TestCase):
    """Removing the pose must not cost the bike its labels or its item."""

    def test_each_handler_still_uses_its_own_label_group(self):
        pairs = (
            ("VF2ExerciseBikeWalk", "kVF2BehaviorLabels_exercise_bike_walk"),
            ("VF2ExerciseBikeRun", "kVF2BehaviorLabels_exercise_bike_run"),
        )
        for name, group in pairs:
            with self.subTest(handler=name):
                self.assertIn(group, handler_body(name))

    def test_each_handler_still_resolves_the_bike_item(self):
        for name in HANDLERS:
            with self.subTest(handler=name):
                self.assertIn("__VF2_EXERCISE_BIKE_ITEM_ID__",
                              handler_body(name))

    def test_high_intensity_cycling_uses_the_running_donor(self):
        # The two actions must stay distinct: walking borrows the walk donor,
        # cycling borrows the run donor.
        self.assertNotIn("CBehavior::RunningOnTreadmill",
                         handler_body("VF2ExerciseBikeWalk"))
        self.assertNotIn("CBehavior::WorkoutTreadmill",
                         handler_body("VF2ExerciseBikeRun"))


class TheCaptionFollowsTheMachineTheRouteChose(unittest.TestCase):
    """Bike captions must not appear on a stock treadmill.

    Reported from live play. Both machines answer EObject 0x04, so the
    wrappers on the stock treadmill behaviours cannot tell them apart on
    their own.

    WHY THE OBVIOUS FIXES DO NOT WORK, both established by measurement:

    The PRE-probe is a nearest-match FindFurniture from the villager's feet
    taken before the behaviour runs. WorkoutTreadmill makes that same query
    from that same position, so the probe is not wrong -- it just answers
    "which machine is nearest now", which is not "which machine will the
    route pick".

    Probing AGAIN after the call cannot help either.
    VF2RunNativeBehaviorAndChangedLabel only invokes the behaviour
    constructor and enqueues plans; it does not execute them, so FeetPos()
    is unchanged and both probes inspect identical state. That version was
    written, shipped in a PR, and correctly rejected.

    WHAT DOES WORK: PlanToGo(EObject, ...) resolves its destination through
    CContentMap::FindObject -- decoded from VillagerPlans_patched_disasm.txt,
    where the object overload zeroes a local ldwPoint, passes its address to
    ?FindObject@CContentMap@@QAE?B_NW4EObject@1@AAUldwPoint@@@Z and routes to
    what it writes back. The interceptor already wrapping that call asks the
    same function the same question and records the placement at the answer.
    """

    def intercept_body(self):
        start = SOURCE.find("static bool __cdecl VF2PlanToGoObjectAtAddedFurnitureImpl(")
        self.assertNotEqual(start, -1, "the PlanToGo(object) interceptor is gone")
        end = SOURCE.find('\nextern "C"', start)
        self.assertNotEqual(end, -1, "no definition follows the interceptor")
        return SOURCE[start:end]

    def test_the_interceptor_asks_the_engines_own_resolver(self):
        body = self.intercept_body()
        self.assertIn(
            "ContentMap.FindObject(object, routed)", body,
            "the interceptor no longer resolves the destination, so a wrapper "
            "cannot learn which machine the route picked")
        self.assertIn("gVF2RoutedItemValid = true;", body)

    def test_the_resolver_runs_only_when_no_venue_is_forced(self):
        # With a venue active the route is already ours and the recorded item
        # would be meaningless; the early return must come first.
        body = self.intercept_body()
        self.assertLess(
            body.index("gVF2AddedFurnitureVenueActive"),
            body.index("ContentMap.FindObject"),
            "the venue branch must return before the fallback records anything")

    def test_both_treadmill_wrappers_prefer_the_routed_machine(self):
        for name in ("VF2RandomTreadmillWalkLabel", "VF2RandomTreadmillRunLabel"):
            with self.subTest(wrapper=name):
                start = SOURCE.index(
                    'extern "C" void __cdecl %s(CVillager &villager)\n{' % name)
                body = SOURCE[start:SOURCE.index('\nextern "C"', start)]
                self.assertIn(
                    "VF2RoutedToItem(__VF2_EXERCISE_BIKE_ITEM_ID__)", body,
                    "%s still decides from the stale pre-probe alone, which is "
                    "the defect: a bike caption on a treadmill workout" % name)
                self.assertIn("if (!onBike) return;", body)

    def test_an_unrecorded_route_leaves_the_stock_label_alone(self):
        # VF2RoutedToItem returns false when nothing was recorded, so a
        # wrapper that cannot tell must not relabel. A real treadmill keeping
        # its real caption is the safe direction.
        start = SOURCE.index("static bool VF2RoutedToItem(int itemId)")
        body = SOURCE[start:SOURCE.index("\n}", start)]
        self.assertIn("gVF2RoutedItemValid &&", body,
                      "VF2RoutedToItem must refuse to answer when nothing was "
                      "recorded rather than defaulting to a match")

    def test_the_ineffective_post_walk_probe_stays_gone(self):
        # Re-probing after the native call was tried and cannot fire.
        self.assertNotIn("bikeNow", SOURCE)
        self.assertNotIn("pingPongNow", SOURCE)


if __name__ == "__main__":
    unittest.main()
