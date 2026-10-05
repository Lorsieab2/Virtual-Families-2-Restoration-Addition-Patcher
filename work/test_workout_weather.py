#!/usr/bin/env python3
"""Working out, the Home Gym and Yoga are offered in normal weather and Sunny.

Owner (2026-10-04): "working out, home gym and yoga should be possible in
sunny weather and normal weather".

Stock CVillager::InitAI gives WorkingOut (0x04A) candidate +0xA8 = 0, and the
quick workout (0x08B) jumps into the same case, so both were offered only in
weather type 0 (internal "Sunny", normal weather). Home Gym (0x0B3) and Yoga
(0x0B4) are byte clones of those rows and inherited it. CVillagerAI::
DecideWhatToDo, the only reader of +0xA8, rejects a candidate whose +0xA8 is
not -1 and differs from Weather.currentType. The per-decision refresh now
writes +0xA8 for all four rows.

These read the generator source that emits the C++, because that is what
reaches the build.
"""
import re
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

SOURCE = Path(patcher.__file__).read_text(encoding="utf-8")
ROWS_DECL = "static const unsigned int kWorkoutRows[] = {"


def code_only(body):
    return "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("//"))


def refresh_body():
    start = SOURCE.index(
        "static void VF2RefreshVolatileCandidates(unsigned char *data, bool resetWeights)")
    return code_only(SOURCE[start:SOURCE.index("\n}\n", start)])


class WorkingOutIsOfferedInNormalAndSunnyWeather(unittest.TestCase):
    def setUp(self):
        self.body = refresh_body()

    def test_the_block_is_in_the_per_decision_refresh(self):
        self.assertEqual(SOURCE.count(ROWS_DECL), 1)
        self.assertIn(ROWS_DECL, self.body)
        hook_start = SOURCE.index(
            'extern "C" void __cdecl VF2RefreshHammockEligibility(void *villager)')
        hook = SOURCE[hook_start:SOURCE.index("\n}\n", hook_start)]
        self.assertIn("VF2RefreshVolatileCandidates((unsigned char *)villager, false);", hook)

    def test_all_four_workout_rows_are_covered(self):
        rows = re.search(r"kWorkoutRows\[\] = \{([^}]*)\}", self.body).group(1)
        self.assertEqual(
            sorted(int(r, 0) for r in rows.split(",")),
            [0x04A, 0x08B, 0x0B3, 0x0B4],
            "working out, the quick workout, Home Gym and Yoga")
        loop = re.search(r"for \(int i = 0; i < (\d+); \+\+i\) \{\s*\*\(int \*\)\(data \+ 0x6BB8 \+ "
                         r"kWorkoutRows\[i\] \* 0xD0 \+ 0xA8\) = workoutWeather;", self.body)
        self.assertIsNotNone(loop, "each row's +0xA8 weather field is written")
        self.assertEqual(int(loop.group(1)), 4)

    def test_only_the_weather_field_is_written(self):
        start = self.body.index("const int workoutWeather")
        block = self.body[start:self.body.index("unsigned char *playhouse", start)]
        self.assertNotIn("0xCD", block)
        self.assertNotIn("0x0C)", block)
        self.assertNotIn("VF2SetGatedCandidate", block)

    def test_the_weather_decision_matches_a_model_of_decide_what_to_do(self):
        """For every weather, the written +0xA8 must pass the native check
        exactly in normal (0) and Sunny (1)."""
        expr = re.search(r"const int workoutWeather =\s*([^;]+);", self.body).group(1)
        expr = re.sub(r"\s+", " ", expr)
        cond, yes, no = re.fullmatch(r"\((.+)\) \? (.+) : (.+)", expr).groups()
        eligible = []
        for weather in range(6):  # 0 normal, 1 sun beams, 2-3 rain/storm, 4 fog, 5 snow
            sub = lambda s: s.replace("Weather.currentType", str(weather))
            ok = eval(sub(cond).replace("||", " or ").replace("&&", " and "))
            a8 = eval(sub(yes if ok else no))
            if a8 == -1 or a8 == weather:  # DecideWhatToDo's gate
                eligible.append(weather)
        self.assertEqual(eligible, [0, 1])


if __name__ == "__main__":
    unittest.main()
