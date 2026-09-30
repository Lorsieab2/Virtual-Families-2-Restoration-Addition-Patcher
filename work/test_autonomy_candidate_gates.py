#!/usr/bin/env python3
"""Autonomous-candidate gates the patch must not silently narrow or widen.

CVillagerAI::DecideWhatToDo filters each 0xD0-byte candidate (base
CVillager+0x6BB8) on fields stock CVillager::InitAI writes. Two of those were
being defeated by the patch's own enabler:

* Hammock (0x23). Stock InitAI sets +0xA8 = 0, "weather must equal Sunny".
  DecideWhatToDo rejects a candidate whose +0xA8 is not -1 and differs from
  Weather.currentType. VF2RefreshHammockEligibility admits Sunny (0) and
  Cloudy (1) but left +0xA8 at 0, so Cloudy was always vetoed.

* Career work (0x047, 0x048, 0x02C, 0x04B). Stock InitAI gives 0x047, 0x02C
  and 0x04B a minimum age (+0x4C) of 0x168 (displayed 18). The enabler used
  the "adult only" helper, whose adult bound is 0x118 (displayed 14), and so
  lowered the stock gate by four years.

These read the generator source that emits the C++, because that is what
reaches the build.
"""
import re
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

SOURCE = Path(patcher.__file__).read_text(encoding="utf-8")


def function_body(signature):
    start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index("\n}\n", start)]


def code_only(body):
    return "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("//"))


class TheHammockIsOfferedInSunnyAndCloudyWeather(unittest.TestCase):
    def setUp(self):
        self.body = code_only(function_body(
            'extern "C" void __cdecl VF2RefreshHammockEligibility(void *villager)'))
        start = self.body.index("0x023 * 0xD0")
        self.hammock = self.body[start:self.body.index("playhouse", start)]

    def test_the_refresh_admits_exactly_sunny_and_cloudy(self):
        self.assertIn(
            "const int weatherAllowsHammock = Weather.currentType == 0 || "
            "Weather.currentType == 1;", self.hammock)

    def test_the_stock_weather_equality_gate_is_cleared(self):
        """Without this, DecideWhatToDo vetoes Cloudy on the stock +0xA8 = 0."""
        self.assertIn("*(int *)(candidate + 0xA8) = -1;", self.hammock,
                      "the hammock keeps stock InitAI's Sunny-only weather "
                      "gate, so Cloudy is admitted by the refresh and then "
                      "rejected by DecideWhatToDo")

    def test_the_weather_decision_matches_a_model_of_decide_what_to_do(self):
        """Model the two gates together for every weather value.

        The refresh decides +0xCD from its own expression and writes +0xA8;
        DecideWhatToDo then requires +0xA8 == -1 or +0xA8 == weather. The
        emitted assignments are parsed, not assumed, so a mutation of either
        side changes the outcome here.
        """
        expr = re.search(r"weatherAllowsHammock = ([^;]+);", self.hammock).group(1)
        a8 = re.search(r"\(candidate \+ 0xA8\) = (-?\w+);", self.hammock)
        a8 = int(a8.group(1), 0) if a8 else 0  # stock InitAI value
        eligible = []
        for weather in range(6):  # 0 sunny .. 5 snow
            refresh = eval(expr.replace("Weather.currentType", str(weather))
                           .replace("||", " or ").replace("&&", " and "))
            native = a8 == -1 or a8 == weather
            if refresh and native:
                eligible.append(weather)
        self.assertEqual(eligible, [0, 1], "hammock weathers (0 sunny, 1 cloudy)")


class CareerWorkKeepsTheStockAdultAgeGate(unittest.TestCase):
    CAREER = ("0x047", "0x048", "0x02C", "0x04B")

    def setUp(self):
        self.body = code_only(function_body(
            'extern "C" void __cdecl VF2EnableAutonomousCandidates(void *villager)'))

    def test_no_career_row_uses_an_age_overriding_helper(self):
        for behavior in self.CAREER:
            with self.subTest(behavior=behavior):
                rows = [line.strip() for line in self.body.splitlines()
                        if re.search(r"\(data, (0x\w+, )?%s," % behavior, line)]
                self.assertTrue(rows, "no enabler row for %s" % behavior)
                for row in rows:
                    self.assertFalse(
                        re.match(r"Enable(AdultOnly|ChildOnly|AllAges|NursingMother)", row),
                        "%s is enabled through a helper that rewrites the stock "
                        "age gate: %s" % (behavior, row))

    def test_the_kitchen_clone_copies_the_configured_kitchen_row(self):
        lines = [line.strip() for line in self.body.splitlines()]
        clone = lines.index(
            "CloneAutonomousCandidateWithWeight(data, 0x047, 0x048, 450, 0); "
            "// WorkKitchen0, with kitchen career gates")
        first = next(i for i, line in enumerate(lines) if "(data, 0x047," in line)
        self.assertLess(first, clone)
        later = [line for line in lines[clone + 1:] if "(data, 0x048," in line]
        self.assertEqual(later, [], "0x048 is re-gated after taking 0x047's gates")

    def test_the_weight_only_helper_touches_no_gate(self):
        body = code_only(function_body(
            "static void EnableAutonomousCandidateWithWeight(unsigned char *villager, "
            "unsigned int behavior, unsigned int weight)"))
        writes = re.findall(r"candidate(?:\[|\s*\+\s*)(0x[0-9A-Fa-f]+)", body)
        self.assertEqual(sorted(set(writes)), ["0x0C", "0xCD"])


if __name__ == "__main__":
    unittest.main()
