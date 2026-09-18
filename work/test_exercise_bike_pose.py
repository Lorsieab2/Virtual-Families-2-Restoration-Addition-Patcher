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

# Imported as well as read as text. Most of this module inspects the generator
# as SOURCE, but the Exercise Bike's own object is a CONSTANT and a transform
# function, and those are worth exercising rather than pattern-matched: a
# string check cannot tell whether the cell encoding actually round-trips
# through CContentMap::HasObject's decoder.
import patch_mobile_furniture_pack as patcher

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

    def test_the_bike_drop_can_reach_both_variants(self):
        """A DROP on the Exercise Bike must be able to produce either label.

        Owner report from live play: dropping a villager on the Exercise Bike
        only ever produced "using the exercise bike", never "doing
        high-intensity cycling". The drop dispatch called VF2ExerciseBikeWalk
        unconditionally, so the run helper -- and its whole label family --
        was unreachable from a drop no matter what the player did.

        Both arms are asserted, not merely the presence of a selector: a
        dispatch that names a choice while having one reachable answer passes
        a structural check happily, which is exactly how this defect shipped.
        """
        drop = SOURCE.split("__VF2_EXERCISE_BIKE_ITEM_ID__)", 1)[1]
        drop = drop.split("__VF2_HOME_GYM_ITEM_ID__", 1)[0]
        code = NL.join(
            line for line in drop.splitlines()
            if not line.lstrip().startswith("//"))
        self.assertIn(
            "VF2ExerciseBikeRun(villager);", code,
            "the run variant is unreachable from a drop, so "
            "'doing high-intensity cycling' can never appear")
        self.assertIn(
            "VF2ExerciseBikeWalk(villager);", code,
            "the walk variant must remain reachable")
        self.assertIn(
            "ldwGameState::GetRandom(2)", code,
            "the drop must actually choose between the two, matching the "
            "autonomous path's equal 450/450 weighting")

    def test_the_ineffective_post_walk_probe_stays_gone(self):
        # Re-probing after the native call was tried and cannot fire:
        # VF2RunNativeBehaviorAndChangedLabel only enqueues plans, so FeetPos
        # is unchanged and both probes inspect identical state.
        self.assertNotIn("bikeNow", SOURCE)
        self.assertNotIn("pingPongNow", SOURCE)


class TheExerciseBikeHasItsOwnObject(unittest.TestCase):
    """The bike must not share the Treadmill's content-map object.

    Owner: "the exercise bike is a totally new object", and the standing
    symmetric rule that bike actions target only the bike and treadmill
    actions only the treadmill, in BOTH directions and on BOTH the drop and
    autonomous paths.

    Sharing object 0x04 is what made the two indistinguishable to
    CFurnitureManager::FindFurniture, which resolves purely by object. Every
    earlier fix for this had to be a positional guard rather than a real
    separation, and the defect kept returning from whichever direction was not
    guarded.
    """

    def test_the_bike_has_its_own_object_id(self):
        self.assertEqual(patcher.MOBILE_EXERCISE_BIKE_OBJECT, 0x99)
        self.assertNotEqual(
            patcher.MOBILE_EXERCISE_BIKE_OBJECT,
            patcher.MOBILE_EXERCISE_BIKE_DONOR_OBJECT,
            "the bike is sharing the Treadmill's object again")

    def test_the_object_id_is_not_taken_by_another_added_item(self):
        """A collision here would recreate the bug against a different item."""
        others = {
            patcher.MOBILE_CHAISE_OBJECT,
            patcher.MOBILE_PATIO_UMBRELLA_OBJECT,
            patcher.MOBILE_PICNIC_TABLE_OBJECT,
            patcher.MOBILE_PATIO_TABLE_OBJECT,
        }
        self.assertNotIn(patcher.MOBILE_EXERCISE_BIKE_OBJECT, others)

    def test_the_cell_value_decodes_to_the_object_id(self):
        """The encoding is CContentMap::HasObject's own, not an assumption.

        HasObject walks the content block's cells and decodes each as

            id = (((cell >> 11) & 0x40000) | (cell & 0x3F800)) >> 11

        This asserts the declared cell value round-trips through that exact
        decoder, and that the same decoder reproduces all four pre-existing
        added-item values -- which is what makes the encoding evidence rather
        than a guess.
        """
        def decode(cell):
            return (((cell >> 11) & 0x40000) | (cell & 0x3F800)) >> 11

        self.assertEqual(
            decode(patcher.MOBILE_EXERCISE_BIKE_PC_CELL_VALUE),
            patcher.MOBILE_EXERCISE_BIKE_OBJECT)
        for cell, obj in (
            (patcher.MOBILE_CHAISE_PC_CELL_VALUE, patcher.MOBILE_CHAISE_OBJECT),
            (patcher.MOBILE_PATIO_UMBRELLA_PC_CELL_VALUE,
             patcher.MOBILE_PATIO_UMBRELLA_OBJECT),
            (patcher.MOBILE_PICNIC_TABLE_PC_CELL_VALUE,
             patcher.MOBILE_PICNIC_TABLE_OBJECT),
            (patcher.MOBILE_PATIO_TABLE_PC_CELL_VALUE,
             patcher.MOBILE_PATIO_TABLE_OBJECT),
        ):
            self.assertEqual(decode(cell), obj)

    def test_the_retarget_preserves_every_collision_bit(self):
        """Only the object field may move; the footprint must not change.

        A borrower that lost its geometry here would regress the way the Patio
        Table did when borrowers were switched onto the sparse desktop-safe
        map -- 241 occupied cells down to 8.
        """
        import struct
        width, height = 4, 4
        cells = [0] * (width * height)
        cells[0] = 0x00202000   # object 0x04 plus collision flags
        cells[1] = 0x02202000   # object 0x04 plus different flags
        cells[2] = 0x00200000   # footprint only, no object
        data = (b"QAMF" + bytes(20)
                + struct.pack("<ii", width, height)
                + struct.pack("<%dI" % len(cells), *cells))

        out, changed = patcher.retarget_fmap_object(data, 0x04, 0x99)
        self.assertEqual(changed, 2, "both object cells must be retargeted")
        self.assertEqual(len(out), len(data))

        low, high = 0x3F800, 0x40000 << 11
        before = patcher._fmap_cells(data)
        after = patcher._fmap_cells(out)
        self.assertEqual(
            [c & ~low & ~high for c in before],
            [c & ~low & ~high for c in after],
            "a collision flag bit changed, so the footprint moved")

        def decode(cell):
            return (((cell >> 11) & 0x40000) | (cell & low)) >> 11
        self.assertEqual(decode(after[0]), 0x99)
        self.assertEqual(decode(after[1]), 0x99)
        self.assertEqual(decode(after[2]), 0, "a non-object cell was touched")

    def test_a_map_without_the_donor_object_is_reported_not_guessed(self):
        """Zero changes must be visible to the caller, which raises on it."""
        import struct
        cells = [0x00200000, 0, 0, 0]
        data = (b"QAMF" + bytes(20) + struct.pack("<ii", 2, 2)
                + struct.pack("<4I", *cells))
        _out, changed = patcher.retarget_fmap_object(data, 0x04, 0x99)
        self.assertEqual(changed, 0)

    def test_both_bike_helpers_search_the_bike_object(self):
        """The search object and the declared object come from one constant."""
        self.assertEqual(
            SOURCE.count(
                "__VF2_EXERCISE_BIKE_ITEM_ID__, __VF2_EXERCISE_BIKE_OBJECT__,"),
            2,
            "a bike helper is still searching a literal object")
        self.assertNotIn(
            "__VF2_EXERCISE_BIKE_ITEM_ID__, 0x04,", SOURCE,
            "a bike helper still searches the Treadmill's object")
        self.assertIn(
            '"__VF2_EXERCISE_BIKE_OBJECT__", f"{MOBILE_EXERCISE_BIKE_OBJECT:#x}"',
            SOURCE,
            "the object macro must be substituted from the constant, or the "
            "searched object and the declared object can drift apart")

    def test_the_donor_lookup_searches_the_venue_object(self):
        """The donor's OWN FindFurniture must search the bike's object too.

        Codex P1 on #340, and it would have shipped a bike that does nothing.

        Giving the bike object 0x99 changed the object the venue SELECTION
        searches, but the donor behaviours are the stock Treadmill ones and
        they push their own literal 0x04 into their internal FindFurniture.
        The venue wrapper substituted only the search POINT and forwarded that
        object unchanged, so once the bike's fmap stopped declaring 0x04:

          * with no Treadmill placed, the donor's lookup finds nothing and the
            behaviour returns immediately -- the bike silently does nothing;
          * with a Treadmill placed, it binds to the TREADMILL's record, which
            is the exact cross-targeting this change exists to end.

        Both failure modes look like "the item is not placed", which is why
        this is pinned rather than left to a playtest to rediscover.
        """
        self.assertIn("static int gVF2AddedFurnitureVenueObject = -1;", SOURCE)
        self.assertIn(
            "gVF2AddedFurnitureVenueObject = object;", SOURCE,
            "the window does not record the object it was selected from")
        self.assertIn(
            "VF2BeginAddedFurnitureVenue(villager, venue, venuePlacement, object);",
            SOURCE,
            "the venue is opened without the object")
        wrapper = SOURCE.split(
            "static bool __cdecl VF2FindFurnitureAtAddedFurnitureImpl", 1)[1]
        wrapper = wrapper.split("extern \"C\" __declspec(naked)", 1)[0]
        self.assertIn(
            "object = (CContentMap::EObject)gVF2AddedFurnitureVenueObject;",
            wrapper,
            "the donor's own lookup still forwards its literal object, so the "
            "bike would search for something its placement no longer has")
        self.assertIn(
            "gVF2AddedFurnitureVenueObject >= 0", wrapper,
            "the substitution must be gated, or an unset window would force "
            "object 0 onto every donor lookup")

    def test_the_exclusion_keeps_asking_about_the_donor_object(self):
        """The treadmill exclusion must search 0x04, not the bike's 0x99.

        Codex P1 #2 on #340. VF2RunOwnFurnitureActionEx used ONE object for two
        different questions:

          1. which placement is this item's venue -- needs the bike's own 0x99;
          2. is the villager standing on furniture this action could steal them
             away from -- needs the DONOR's 0x04, because a donor can only be
             diverted through the object it searches.

        Giving the bike 0x99 silently changed question 2 as well. With both
        machines placed and a villager standing on the Treadmill, the exclusion
        would search 0x99 at their feet, match the REMOTE bike's handle rather
        than the Treadmill's, conclude the villager was on open floor, and let
        the bike candidate walk them off the Treadmill.

        That is the owner's reported bug returning by a new route:

            "make sure the TREADMILL and ONLY the treadmill behaves identically
             to stock, on both manual drop and autonomous villager behaviors"
        """
        self.assertIn("int donorObject,", SOURCE,
                      "the donor object parameter is gone, so one value is "
                      "answering two different questions again")
        self.assertIn(
            "villager, itemId, altItemId, donorObject)) {", SOURCE,
            "the exclusion is back on the venue object, so a placed bike can "
            "walk a villager off a Treadmill")
        self.assertEqual(
            SOURCE.count("__VF2_EXERCISE_BIKE_DONOR_OBJECT__,"), 2,
            "both bike helpers must pass the Treadmill's object for the "
            "exclusion")
        self.assertIn(
            '"__VF2_EXERCISE_BIKE_DONOR_OBJECT__",' + NL +
            '        f"{MOBILE_EXERCISE_BIKE_DONOR_OBJECT:#x}",', SOURCE,
            "the donor object must be substituted from the constant")

    def test_items_whose_object_is_their_donors_pass_it_twice(self):
        """Ping-Pong and the gym/yoga routes must be unaffected.

        Their own object IS their donor's -- 0x36 and 0x75 -- so both questions
        take the same value and their behaviour is identical to before the
        split. If either silently changed, an unrelated item would have been
        modified to fix the bike.
        """
        self.assertIn("__VF2_PING_PONG_TABLE_ITEM_ID__, 0x36, 0x36,", SOURCE)
        self.assertIn(
            "villager, donorBehaviors[index], itemId, altItemId, object, object,",
            SOURCE,
            "the gym/yoga dispatcher must pass its own object for both")

    def test_closing_the_venue_clears_the_object(self):
        """A stale object must not outlive the window that set it."""
        end = SOURCE.split("static void VF2EndAddedFurnitureVenue", 1)[1]
        end = end.split(NL + "}", 1)[0]
        self.assertIn("gVF2AddedFurnitureVenueObject = -1;", end)

    def test_the_shipped_bike_fmap_is_retargeted(self):
        """The copy that writes the bike's own file must retarget it."""
        self.assertIn('if target == "ExerciseBikeStd.png.fmap":', SOURCE)
        self.assertIn("MOBILE_EXERCISE_BIKE_DONOR_OBJECT,", SOURCE)
        self.assertIn("MOBILE_EXERCISE_BIKE_OBJECT,", SOURCE)
        self.assertIn(
            "carries no object ", SOURCE,
            "a donor map that stops carrying the object must fail the build, "
            "not silently leave the bike sharing the Treadmill's object")


if __name__ == "__main__":
    unittest.main()
