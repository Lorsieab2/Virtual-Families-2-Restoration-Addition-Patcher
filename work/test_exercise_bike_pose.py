"""The Exercise Bike must be ridden SEATED, in the orientation it was placed.

THE REPORT: the bike should use "the animation cycles sittingNW and SittingNE
depending on the furniture position (first furniture frame is northwest
orientation, second is northeast orientation)".

WHAT IT DID: both bike handlers delegate to a treadmill donor, which is a
standing animation, and set no pose at all -- so a villager on the bike stood
beside it and jogged on the spot.

THE VALUES WERE DECODED, NOT GUESSED. work/desktop_obj_files/AnimManager.obj
carries the enum:

    eBodyPosition_Upright    0x00
    eBodyPosition_Sitting    0x02
    eBodyPosition_SittingNE  0x11
    eBodyPosition_SittingNW  0x12

Upright at 0x00 matches the eBodyPositionStanding the generator already
declared, which is what validates the extraction -- a wrong constant would seat
the villager in some unrelated pose.

THE FIRST FIX WAS WRONG AND IS PINNED HERE AS A REGRESSION. It appended a pose
after the donor ran. WorkoutTreadmill enqueues PlanToPlayAnim + PlanToWait
cycles and each wait carries a STANDING body position, so an appended pose left
the villager jogging upright for the entire workout with one seated frame at
the end. The shipped design instead retargets the donor's own PlanToWait
callsites, substituting the seated pose while the donor keeps its durations and
animations.

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


def seated_window():
    m = re.search(r"static bool VF2OpenBikeSeatedWindow\(.*?\n\}", SOURCE, re.S)
    assert m, "VF2OpenBikeSeatedWindow not found in the generator"
    return m.group(0)


class TheSeatedWindowIsWiredUp(unittest.TestCase):
    def test_the_window_helper_exists(self):
        # Three arguments: the third resolves the venue so the pose belongs to
        # the bike the villager actually rides.
        self.assertIn(
            "static bool VF2OpenBikeSeatedWindow("
            "CVillager &villager, int itemId, int object)", SOURCE)

    def test_the_abandoned_append_design_is_gone(self):
        # Appending a pose after the donor is the bug, not the fix.
        self.assertNotIn("VF2SeatOnExerciseBike", SOURCE)

    def test_both_handlers_open_and_close_the_window(self):
        for name in HANDLERS:
            with self.subTest(handler=name):
                body = handler_body(name)
                self.assertIn(
                    "VF2OpenBikeSeatedWindow("
                    "villager, __VF2_EXERCISE_BIKE_ITEM_ID__, 0x04)", body)
                self.assertIn("if (seated) VF2EndBikeSeated(villager);", body)

    def test_the_window_opens_before_the_donor_runs(self):
        # The window must be open while the donor enqueues its waits;
        # opening it afterwards substitutes nothing.
        for name in HANDLERS:
            with self.subTest(handler=name):
                body = handler_body(name)
                self.assertLess(
                    body.index("VF2OpenBikeSeatedWindow"),
                    body.index("VF2RunOwnFurnitureAction"))

    def test_high_intensity_cycling_uses_the_running_donor(self):
        # The owner asked that high-intensity cycling be restricted to the
        # bike. It borrows RunningOnTreadmill, which has its OWN wait callsites.
        self.assertIn(
            "CBehavior::RunningOnTreadmill", handler_body("VF2ExerciseBikeRun"))
        self.assertIn(
            "CBehavior::WorkoutTreadmill", handler_body("VF2ExerciseBikeWalk"))


class BothDonorsAreRetargeted(unittest.TestCase):
    def test_both_treadmill_donors_have_their_waits_retargeted(self):
        # Retargeting only WorkoutTreadmill left high-intensity cycling fully
        # upright while the walking action sat down -- a half-applied fix that
        # no check looking at a single donor could see.
        self.assertIn("WorkoutTreadmill seated PlanToWait", SOURCE)
        self.assertIn("RunningOnTreadmill seated PlanToWait", SOURCE)

    def test_the_wait_retarget_requires_every_callsite(self):
        # A count check that accepted "at least one" would let most of the
        # workout stay standing, so an exact count is required.
        self.assertIn("_VF2PlanToWaitSeatedOnBike", SOURCE)
        self.assertRegex(SOURCE, r"expected \w+ REL32 wait relocations")


class TheOrientationComesFromThePlacement(unittest.TestCase):
    def test_orientation_is_read_from_the_placement_record(self):
        # +0x10 is the placement record's orientation. sFurnitureInfo2's
        # equivalent slot is padding in the declaration this code sees.
        self.assertIn(
            "int orientation = *reinterpret_cast<int *>(record + 0x10);", SOURCE)

    def test_both_orientations_map_to_distinct_seated_poses(self):
        self.assertIn("eBodyPositionSittingNE = 0x11", SOURCE)
        self.assertIn("eBodyPositionSittingNW = 0x12", SOURCE)
        self.assertIn(
            "orientation == 1 ? eBodyPositionSittingNW : eBodyPositionSittingNE",
            SOURCE)

    def test_the_pose_belongs_to_the_bike_the_villager_rides(self):
        # With two bikes placed at different orientations, taking the first
        # record with a matching id could pose for the wrong one, because the
        # route picks the NEAREST.
        window = seated_window()
        self.assertIn(
            "VF2FindAddedFurnitureVenue(villager, itemId, object, venue)", window)
        self.assertIn(
            "info.point.x != venue.x || info.point.y != venue.y", window)

    def test_a_missing_bike_leaves_the_donor_alone(self):
        # No bike placed -> no window -> the stock treadmill user is untouched.
        self.assertIn("return false;", seated_window())
        for name in HANDLERS:
            with self.subTest(handler=name):
                self.assertIn("if (seated)", handler_body(name))


if __name__ == "__main__":
    unittest.main()
