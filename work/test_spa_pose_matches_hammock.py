"""The spa receiving pose must supply a BODY DIRECTION, not just a head.

GROUND TRUTH is work/VillagerPlans_patched_disasm.txt, which decodes the
shipped CVillagerPlans. BOTH overloads exist:

    3-arg  ?PlanToWait@CVillagerPlans@@QAEXHW4EBodyPosition@@W4EHeadDirection@@@Z
    4-arg  ?PlanToWait@CVillagerPlans@@QAEXHW4EBodyPosition@@W4EDirection@@W4EHeadDirection@@@Z

THE DECISIVE DETAIL: the 3-argument implementation writes -1 (0FFFFFFFFh)
into the body-direction field at [ebp-3Ch]. It DISCARDS direction. The
4-argument version fills that same field from its EDirection argument.

eBodyPositionChaise carries no facing of its own, so a reclined pose that
must align to the furniture REQUIRES the 4-argument overload. Calling the
3-arg form leaves the villager lying ACROSS the lounger -- the defect the
owner reported across nine playtest rounds.

An earlier version of this file asserted the OPPOSITE, on the mistaken
belief that only a 2-argument symbol existed. That belief came from
grepping the generator for referenced symbols instead of reading the
binary. Review caught it with the disassembly. Ground truth is the decoded
implementation, not what the generator happens to mention.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
DISASM = ROOT / "work" / "VillagerPlans_patched_disasm.txt"


def _source():
    return GEN.read_text(encoding="utf-8")


def _strip_comments(text):
    """Judge CODE, not prose: comments here quote the old wrong forms."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        out.append(line.split("//")[0] if "//" in line else line)
    return "\n".join(out)


def _pred(match):
    """Normalize a captured predicate: strip whitespace, keep any '!'.

    Capturing the optional '!' is what makes a NEGATED predicate a different
    token, so flipping one ternary alone is caught. Review showed that
    without it, `!loungerFacesNorthWest` compared equal to the plain name
    and the known-bad mutation passed.
    """
    return "".join(match.group(1).split())


def _spa_body(src):
    start = src.index("static void VF2PlanSpaTreatment(")
    return _strip_comments(src[start:src.index("\n}\n", start)])


class TestSpaPoseSuppliesBodyDirection(unittest.TestCase):
    def test_the_engine_really_exports_the_four_argument_overload(self):
        """Pin the ground truth so nobody re-derives it from the wrong place."""
        if not DISASM.is_file():
            self.skipTest("disassembly not present in this checkout")
        text = DISASM.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "?PlanToWait@CVillagerPlans@@QAEXHW4EBodyPosition@@"
            "W4EDirection@@W4EHeadDirection@@@Z", text,
            "the 4-argument PlanToWait is missing from the decoded binary")

    def test_the_spa_pose_passes_a_body_direction(self):
        spa = _spa_body(_source())
        calls = re.findall(r"PlanToWait\(([^;]*)\);", spa, re.S)
        self.assertTrue(calls, "VF2PlanSpaTreatment plans no pose at all")
        for call in calls:
            flat = re.sub(r"VF2SpaLoungerFacesNorthWest\([^)]*\)", "X", call)
            argc = flat.count(",") + 1
            self.assertEqual(
                argc, 4,
                "the spa pose passes %d arguments to PlanToWait. It must pass "
                "4 (duration, body, DIRECTION, head): the 3-argument overload "
                "writes -1 into the body-direction field, and "
                "eBodyPositionChaise supplies no facing of its own, so the "
                "villager ends up lying ACROSS the lounger. Call: %s"
                % (argc, " ".join(flat.split())[:90]))
        self.assertTrue(
            re.search(r"eDirectionNorth(west|east)", spa),
            "the spa pose passes no EDirection at all")

    def test_body_and_head_take_the_same_arm(self):
        """Body and head are ONE phase: they must not disagree.

        Checks the ternary PREDICATES, not token order. Review caught that
        comparing first-occurrence positions let a flipped predicate pass.
        """
        spa = _spa_body(_source())
        head = re.search(
            r"(!?\s*\w+)\s*\?\s*eHeadDirectionNW\s*:\s*eHeadDirectionNE", spa)
        body = re.search(
            r"(!?\s*\w+)\s*\?\s*eDirectionNorthwest\s*:\s*eDirectionNortheast", spa)
        self.assertIsNotNone(
            head, "no 'pred ? eHeadDirectionNW : eHeadDirectionNE' found, so "
                  "a flipped or restructured head mapping is not pinned")
        self.assertIsNotNone(
            body, "no 'pred ? eDirectionNorthwest : eDirectionNortheast' "
                  "found, so a flipped body mapping is not pinned")
        self.assertEqual(
            _pred(head), _pred(body),
            "the head and the body direction are driven by DIFFERENT "
            "predicates (%s vs %s). They are the same phase and must agree, "
            "or the villager's head and body point different ways."
            % (_pred(head), _pred(body)))

    def test_head_and_sleep_strip_take_the_same_arm(self):
        """The hammock pairs an NW head with SleepNW. The spa must match.

        Evaluates both predicate ARMS rather than comparing token order, so
        flipping the animation selection alone is caught.
        """
        spa = _spa_body(_source())
        head = re.search(
            r"(!?\s*\w+)\s*\?\s*eHeadDirectionNW\s*:\s*eHeadDirectionNE", spa)
        self.assertIsNotNone(head, "no head mapping found in the spa pose")

        anim = re.search(
            r"(!?\s*\w+)\s*\?\s*\"(Sleep\w+)\"\s*:\s*\"(Sleep\w+)\"", spa)
        if anim is None:
            anim = re.search(
                r"if\s*\(\s*(!?\s*\w+)\s*\)\s*\{[^}]*\"(Sleep\w+)\"[^}]*\}"
                r"\s*else\s*\{[^}]*\"(Sleep\w+)\"", spa, re.S)
        self.assertIsNotNone(
            anim, "no sleep-strip selection found in the spa pose")

        self.assertEqual(
            _pred(head), _pred(anim),
            "the head and the sleep strip are driven by different predicates "
            "(%s vs %s)" % (_pred(head), _pred(anim)))
        self.assertEqual(
            anim.group(2), "SleepNW",
            "the strip's TRUE arm is %s but the head's TRUE arm is NW. The "
            "working hammock pairs an NW head with SleepNW; opposite arms "
            "make the villager settle and sleep facing differently."
            % anim.group(2))
        self.assertEqual(
            anim.group(3), "SleepNE",
            "the strip's FALSE arm is %s, expected SleepNE" % anim.group(3))

    def test_the_spa_behaviours_are_still_present(self):
        """A pose fix must not delete the spa feature."""
        src = _source()
        self.assertIn("VF2PlanSpaTreatment", src)
        self.assertIn("VF2SpaLoungerHasHandle", src)
        self.assertIn("eBodyPositionChaise", _spa_body(src),
                      "the spa pose must keep the CHAISE body position")
        self.assertIn("point.y -= 4;", src)
        self.assertIn("point.x -= 4;", src)
        self.assertIn('"Relaxing in the spa"', src)


if __name__ == "__main__":
    unittest.main()
