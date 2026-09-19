"""The spa receiving pose must use the SAME call shape as the hammock.

WHY THIS EXISTS. Nine playtest rounds were spent changing direction values
inside a call that was discarding them. The owner had to relaunch the game
every time to discover nothing had changed.

The engine exports exactly ONE PlanToWait symbol:

    ?PlanToWait@CVillagerPlans@@QAEXHW4EBodyPosition@@@Z

The working hammock pose uses the 3-argument form
(duration, body, head). The spa receiving pose was using a FOUR-argument
form with an extra EDirection, which does not match and meant the head
value never took effect -- so BOTH arms of the orientation predicate
rendered the identical wrong pose.

These tests fail on that mistake instead of making the owner find it.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"


def _source():
    return GEN.read_text(encoding="utf-8")


def _strip_comments(text):
    """Judge CODE, not prose: comments here quote the OLD wrong forms."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith(chr(47)*2):
            continue
        out.append(line.split(chr(47)*2)[0] if chr(47)*2 in line else line)
    return chr(10).join(out)


def _spa_body(src):
    start = src.index("static void VF2PlanSpaTreatment(")
    return _strip_comments(src[start:src.index("\n}\n", start)])


def _hammock_body(src):
    start = src.index("bool const hammockFacesNorthWest")
    return _strip_comments(src[start:start + 800])


class TestSpaPoseMatchesHammock(unittest.TestCase):
    def test_the_spa_pose_call_takes_three_arguments(self):
        """A 4-argument PlanToWait does not match the exported symbol."""
        spa = _spa_body(_source())
        calls = re.findall(r"PlanToWait\(([^;]*)\);", spa, re.S)
        self.assertTrue(calls, "VF2PlanSpaTreatment plans no pose at all")
        for call in calls:
            argc = call.count(",") + 1
            # EXACTLY three, not "at most three". Review caught that
            # assertLessEqual also accepts the 2-argument overload, so
            # dropping the head entirely would have kept this test green --
            # silently discarding the head is the very defect being pinned.
            self.assertEqual(
                argc, 3,
                "the spa pose passes %d arguments to PlanToWait; it must pass "
                "exactly 3 (duration, body, head). The engine "
                "exports only PlanToWait(int, EBodyPosition) and the working "
                "hammock uses the 3-argument (duration, body, head) form. A "
                "4th EDirection argument does not reach the function, so the "
                "head value is silently discarded and BOTH orientations "
                "render the same wrong pose: %s" % (argc, call.strip()))

    def test_no_edirection_is_passed_to_the_spa_pose(self):
        spa = _spa_body(_source())
        for bad in ("eDirectionNortheast", "eDirectionNorthwest",
                    "eDirectionSoutheast", "eDirectionSouthwest"):
            self.assertNotIn(
                bad, spa,
                "the spa pose still passes %s. PlanToWait takes no "
                "EDirection; the hammock passes only an EHeadDirection." % bad)

    def test_head_and_sleep_strip_go_the_same_way(self):
        """The hammock pairs NW head with SleepNW. The spa must match."""
        src = _source()
        spa = _spa_body(src)
        ham = _hammock_body(src)

        ham_head_nw_first = ham.index("eHeadDirectionNW") < ham.index("eHeadDirectionNE")
        ham_nw_first = ham.index('"SleepNW"') < ham.index('"SleepNE"')
        self.assertEqual(
            ham_head_nw_first, ham_nw_first,
            "the hammock reference itself no longer pairs head with strip")

        spa_head_nw_first = spa.index("eHeadDirectionNW") < spa.index("eHeadDirectionNE")
        spa_nw_first = spa.index('"SleepNW"') < spa.index('"SleepNE"')
        self.assertEqual(
            spa_head_nw_first, spa_nw_first,
            "the spa pose puts the head on one arm and the sleep strip on "
            "the OPPOSITE arm. The working hammock pairs them the same way "
            "(NW head with SleepNW), so the villager settles and sleeps "
            "facing consistently.")

    def test_no_call_site_passes_four_arguments(self):
        """EVERY PlanToWait in the generator must be a supported shape.

        Removing the fabricated 4-argument declaration broke an unrelated
        site -- the patio umbrella -- with C2661, because it was still
        passing four arguments. Review caught it; this pins it so the whole
        emitted translation unit stays compilable, not just the spa handler.
        """
        src = _strip_comments(_source())
        for m in re.finditer(r"plans->PlanToWait\(([^;]*)\);", src, re.S):
            call = m.group(1)
            # A predicate call inside an argument contributes its own comma.
            flat = re.sub(r"VF2SpaLoungerFacesNorthWest\([^)]*\)", "X", call)
            argc = flat.count(",") + 1
            self.assertLessEqual(
                argc, 3,
                "a PlanToWait call passes %d arguments: %s. The engine "
                "exports only PlanToWait(int, EBodyPosition) and the 3-arg "
                "(duration, body, head) overload; a 4th argument fails to "
                "compile once the fabricated declaration is gone."
                % (argc, " ".join(flat.split())[:90]))

    def test_the_spa_behaviours_are_still_present(self):
        """Copying the hammock must not delete the spa feature."""
        src = _source()
        self.assertIn("VF2PlanSpaTreatment", src)
        self.assertIn("VF2SpaLoungerHasHandle", src)
        self.assertIn("eBodyPositionChaise", _spa_body(src),
                      "the spa pose must keep the CHAISE body position; the "
                      "hammock's body position belongs to hammock art")
        self.assertIn("point.y -= 4;", src)
        self.assertIn("point.x -= 4;", src)
        self.assertIn('"Relaxing in the spa"', src)


if __name__ == "__main__":
    unittest.main()
