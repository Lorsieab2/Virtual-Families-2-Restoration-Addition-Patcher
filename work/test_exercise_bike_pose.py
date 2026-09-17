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

# Newline as a name, so a stripping expression inside a test never needs a
# backslash escape that the surrounding string quoting would fight over.
NL = chr(10)

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


class TheCaptionFollowsTheMachineTheVillagerIsAt(unittest.TestCase):
    """Bike captions must not appear on a stock treadmill.

    Reported from live play, twice. Both machines answer EObject 0x04, so the
    wrappers on the stock treadmill behaviours cannot tell them apart on their
    own.

    THIS CLASS PREVIOUSLY PINNED A FIX THAT DID NOT WORK, and the history is
    worth keeping because the reasoning was persuasive and still wrong.

    It required the wrappers to prefer a route recorded by intercepting
    PlanToGo and asking CContentMap::FindObject which placement the route
    resolved to. The premise was correct as far as it went -- PlanToGo(EObject,
    ...) really does route through FindObject, and
    work/VillagerPlans_patched_disasm.txt:1915 shows the call. But look at what
    that overload actually passes, at the same site:

        00000009: lea   eax,[ebp-8]              ; a local ldwPoint
        0000000C: mov   dword ptr [ebp-8],0      ; zeroed
        00000013: push  eax                      ; &outPoint
        00000014: push  dword ptr [ebp+8]        ; the EObject
        00000020: mov   ecx, offset ContentMap
        00000025: call  ?FindObject@CContentMap@@QAE?B_NW4EObject@1@AAUldwPoint@@@Z

    Two arguments: an object enum and an out-point. NO VILLAGER AND NO
    POSITION. FindObject is a global "find an object of this type" query, so it
    returns the SAME placement for every villager. With a treadmill and a bike
    both answering 0x04, whichever one it happened to return classified EVERY
    user of either machine -- which is precisely the reported symptom, and why
    the owner saw bike captions on the treadmill after that fix shipped.

    A per-villager ownership gate was then added on top, checking that the
    recorded route belonged to this villager. That could not rescue it either:
    it verifies WHO recorded the route, never WHICH machine that villager goes
    to.

    WHAT ACTUALLY WORKS is what the native behaviours themselves do. From
    Behavior.obj, ?WorkoutTreadmill@ (section 824) and ?RunningOnTreadmill@
    (section 556) each carry exactly ONE furniture relocation --
    ?FindFurniture@CFurnitureManager@@ -- and reference neither
    LinkPeepToFurniture nor CContentMap::FindObject. Their prologue is

        0026  call  ?FeetPos@CVillager@@QBE?BUldwPoint@@XZ
        002b  push 0 / push 0 / push 1
        0031  lea   ecx,[ebp-0x24] / push ecx      ; &sFurnitureInfo2
        0035  push [eax+4] / push [eax]            ; FeetPos.y, FeetPos.x
        003f  push 4                               ; EObject 0x04
        0041  call  ?FindFurniture@CFurnitureManager@@
        004e  push 0x272                           ; the caption string id
        005d  lea   eax,[esi+0x1bba8] / call strncpy
        0079  call  PlanToGo                       ; the walk starts AFTER

    So the native code picks its placement from the PRE-WALK position and
    commits the caption at that same instant. The wrappers' own probe makes the
    identical call with identical arguments at that identical moment, so it
    agrees with the native choice by construction rather than by luck. It was
    correct all along; the recorded route merely overrode it.

    There is also no per-villager alternative to fall back on:
    LinkPeepToFurniture writes its occupant into the FURNITURE RECORD
    (record+0x20), never into the CVillager, so no villager -> furniture
    back-pointer exists to read -- and these two behaviours never call it.
    """

    def wrapper_body(self, name):
        start = SOURCE.index(
            'extern "C" void __cdecl %s(CVillager &villager)\n{' % name)
        return SOURCE[start:SOURCE.index('\nextern "C"', start)]

    def test_both_treadmill_wrappers_use_their_own_probe(self):
        """The probe decides, with nothing layered over it."""
        for name in ("VF2RandomTreadmillWalkLabel", "VF2RandomTreadmillRunLabel"):
            with self.subTest(wrapper=name):
                body = self.wrapper_body(name)
                # SUPERSEDED, recorded rather than deleted (AGENTS.md 11): this
                # asserted VF2LinkedFurnitureItemIs, which is
                # FindFurniture(0x04, feet) -- the same call the native
                # behaviour makes. Faithful to the DONOR's choice, which is why
                # it was adopted, but the donor's choice is a NEAREST MATCH, and
                # nearest-to-feet is not "the machine this villager is on". The
                # owner played that build, found "Using the exercise bike" on
                # the Treadmill, and asked that ONLY the exercise bike carry
                # those captions. The check now reads the item id from the
                # placement record under the villager.
                self.assertIn(
                    "VF2VillagerIsStandingOnItem(\n        villager, "
                    "__VF2_EXERCISE_BIKE_ITEM_ID__)", body,
                    "%s no longer requires the villager to be ON the bike, so "
                    "the bike's caption can land on a treadmill" % name)
                self.assertIn("bool const onBike = bike;", body)
                self.assertIn("if (!onBike) return;", body)

    def test_the_probe_runs_before_the_native_behaviour(self):
        """Timing is the whole point.

        The native code samples FeetPos and commits the caption BEFORE
        PlanToGo, so a probe taken after the behaviour returns would sample a
        different moment. It must come first.
        """
        for name in ("VF2RandomTreadmillWalkLabel", "VF2RandomTreadmillRunLabel"):
            with self.subTest(wrapper=name):
                body = self.wrapper_body(name)
                # The timing property this guards is unchanged: the check must
                # be taken BEFORE the native behaviour runs. Only the question
                # changed -- from "which 0x04 placement is nearest" to "which
                # item is this villager standing on".
                self.assertLess(
                    body.index("VF2VillagerIsStandingOnItem"),
                    body.index("VF2RunNativeBehaviorAndChangedLabel"),
                    "the check must be taken before the native behaviour runs, "
                    "which is when the native code makes its own choice")

    def test_the_position_blind_route_machinery_is_gone(self):
        """None of it may come back: it cannot answer a per-villager question.

        Comments are stripped because the explanation above deliberately names
        these symbols, and a raw search would match the documentation of the
        defect rather than the defect.
        """
        code = NL.join(
            line for line in SOURCE.splitlines()
            if not line.lstrip().startswith("//"))
        for symbol in ("gVF2RoutedItemValid", "gVF2RoutedItemPlans",
                       "gVF2RoutedItemId", "VF2RoutedToItem",
                       "VF2ItemIdAtPoint", "routeIsOurs"):
            with self.subTest(symbol=symbol):
                self.assertNotIn(
                    symbol, code,
                    "%s is back; it derives from CContentMap::FindObject, "
                    "which takes no villager and no position and therefore "
                    "answers identically for everyone" % symbol)

    def test_the_interceptor_no_longer_resolves_anything(self):
        """The PlanToGo interceptor keeps its venue job and nothing else."""
        start = SOURCE.find(
            "static bool __cdecl VF2PlanToGoObjectAtAddedFurnitureImpl(")
        self.assertNotEqual(start, -1, "the PlanToGo(object) interceptor is gone")
        end = SOURCE.find('\nextern "C"', start)
        body = SOURCE[start:end]
        code = NL.join(
            line for line in body.splitlines()
            if not line.lstrip().startswith("//"))
        self.assertIn(
            "gVF2AddedFurnitureVenueActive", code,
            "the venue branch is gone; added furniture would lose its venue")
        self.assertNotIn(
            "ContentMap.FindObject", code,
            "the interceptor is resolving destinations again")

    def test_the_ineffective_post_walk_probe_stays_gone(self):
        # Re-probing after the native call was tried and cannot fire:
        # VF2RunNativeBehaviorAndChangedLabel only enqueues plans, so FeetPos
        # is unchanged and both probes inspect identical state.
        self.assertNotIn("bikeNow", SOURCE)
        self.assertNotIn("pingPongNow", SOURCE)


if __name__ == "__main__":
    unittest.main()
