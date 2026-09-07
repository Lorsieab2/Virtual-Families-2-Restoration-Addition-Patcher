"""The Exercise Bike seats the villager, facing the way it was placed.

THE REPORT: the bike should use "the animation cycles sittingNW and SittingNE
depending on the furniture position (first furniture frame is northwest
orientation, second is northeast orientation)".

WHAT IT DID: both bike handlers delegate to CBehavior::WorkoutTreadmill, which
is a standing animation, and set no pose at all -- so a villager on the bike
stood beside it and jogged on the spot.

THE VALUES WERE DECODED, NOT GUESSED. work/desktop_obj_files/AnimManager.obj
carries the enum:

    eBodyPosition_Upright    0x00
    eBodyPosition_Sitting    0x02
    eBodyPosition_SittingNE  0x11
    eBodyPosition_SittingNW  0x12

Upright at 0x00 matches the eBodyPositionStanding this file already declared,
which is what validates the extraction -- a wrong constant would seat the
villager in an unrelated pose and still compile.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
SOURCE = GENERATOR.read_text(encoding="utf-8", errors="replace")
ANIMS = ROOT / "work" / "desktop_obj_files" / "AnimManager.obj"


def helper_body():
    m = re.search(r"static void VF2SeatOnExerciseBike\(.*?\n\}", SOURCE, re.S)
    return m.group(0) if m else ""


def handler_body(name):
    m = re.search(r'void __cdecl %s\(CVillager &villager\)\s*\{(.*?)\n\}' % name,
                  SOURCE, re.S)
    return m.group(1) if m else ""


class TheSeatedPoseIsWiredUp(unittest.TestCase):
    def test_the_helper_exists(self):
        self.assertTrue(helper_body(), "VF2SeatOnExerciseBike is gone")

    def test_both_bike_handlers_seat_the_villager(self):
        for name in ("VF2ExerciseBikeWalk", "VF2ExerciseBikeRun"):
            with self.subTest(handler=name):
                body = handler_body(name)
                self.assertTrue(body, "%s is gone" % name)
                self.assertIn(
                    "VF2SeatOnExerciseBike(villager);", body,
                    "%s does not seat the villager, so the treadmill's "
                    "standing animation is all the player sees" % name)

    def test_the_pose_is_applied_after_the_donor_runs(self):
        # PlanToGo appends, so a pose queued BEFORE the donor is overtaken by
        # the donor's own plan and the villager ends up standing.
        for name in ("VF2ExerciseBikeWalk", "VF2ExerciseBikeRun"):
            with self.subTest(handler=name):
                body = handler_body(name)
                donor = body.index("VF2RunOwnFurnitureAction")
                seat = body.index("VF2SeatOnExerciseBike")
                self.assertGreater(
                    seat, donor,
                    "%s seats the villager before running the donor; the "
                    "donor's own plan would overtake it" % name)

    def test_orientation_comes_from_the_named_field(self):
        body = helper_body()
        self.assertIn("info.orientation", body,
                      "the pose is not chosen from info.orientation")
        self.assertNotIn(
            "&info) + 0x14", body,
            "orientation is being read at +0x14, which is padding in "
            "sFurnitureInfo2 -- the wrong-facing bug all over again")

    def test_both_orientations_are_reachable(self):
        body = helper_body()
        self.assertIn("eBodyPositionSittingNW", body)
        self.assertIn("eBodyPositionSittingNE", body)
        self.assertRegex(
            body.replace("\n", " "),
            r"\?\s*eBodyPositionSittingNW\s*:\s*eBodyPositionSittingNE",
            "the two poses are no longer the two arms of one conditional, so "
            "one orientation may be unreachable")

    def test_a_missing_bike_leaves_the_donor_alone(self):
        body = helper_body()
        self.assertIn("if (!FurnitureManager.FindFurniture(", body)
        self.assertIn("return;", body,
                      "no early return when the bike cannot be resolved; the "
                      "villager would be seated on nothing")


class TheEnumValuesMatchTheGame(unittest.TestCase):
    def setUp(self):
        if not ANIMS.is_file():
            self.skipTest("AnimManager.obj is a gitignored build input")
        self.data = ANIMS.read_bytes()

    def _value(self, name):
        i = self.data.find(name.encode() + b"\0")
        if i < 0:
            return None
        return self.data[i - 2]

    def test_the_control_value_still_decodes(self):
        # Upright must be 0, matching eBodyPositionStanding. If this fails the
        # decode is wrong and the two new constants cannot be trusted either.
        self.assertEqual(
            self._value("eBodyPosition_Upright"), 0x00,
            "the enum decode no longer reproduces a value this file already "
            "knows, so the SittingNE/NW values are not trustworthy")

    def test_the_declared_constants_match_the_object(self):
        for name, declared in (("eBodyPosition_SittingNE", 0x11),
                               ("eBodyPosition_SittingNW", 0x12)):
            with self.subTest(pose=name):
                self.assertEqual(
                    self._value(name), declared,
                    "%s is %#x in AnimManager.obj but this file declares "
                    "%#x" % (name, self._value(name) or -1, declared))

    def test_the_generator_declares_them_with_those_values(self):
        self.assertIn("eBodyPositionSittingNE = 0x11", SOURCE)
        self.assertIn("eBodyPositionSittingNW = 0x12", SOURCE)


if __name__ == "__main__":
    unittest.main()
