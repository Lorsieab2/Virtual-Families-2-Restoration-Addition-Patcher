#!/usr/bin/env python3
"""The hammock candidate's weather gate must admit Cloudy as documented.

CVillagerAI::DecideWhatToDo filters each 0xD0-byte candidate (base
CVillager+0x6BB8) on fields stock CVillager::InitAI writes. One of those was
being defeated by the patch's own enabler:

* Hammock (0x23). Stock InitAI sets +0xA8 = 0, "weather must equal Sunny".
  DecideWhatToDo rejects a candidate whose +0xA8 is not -1 and differs from
  Weather.currentType. VF2RefreshHammockEligibility admits Sunny (0) and
  Cloudy (1) but left +0xA8 at 0, so Cloudy was always vetoed.

* SUPERSEDED here: this module also pinned a career-row change (0x047,
  0x048, 0x02C, 0x04B enabled through the weight-only helper so stock's
  0x168 minimum age survived). That approach still rewrote the rows'
  weights on every load, erasing the praise training that
  CVillagerAI::RealtimeWorkDone uses to advance careers; PR #405 instead
  leaves the career rows exactly as stock InitAI/LoadAI set them, and pins
  that in work/test_career_rows_match_vanilla.py.

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


HAMMOCK_ANCHOR = "unsigned char *candidate = data + 0x6BB8 + 0x023 * 0xD0;"


def hammock_block():
    """The hammock refresh block, wherever the refresh code lives.

    Anchored on the hammock candidate itself rather than on the enclosing
    function, because the per-decision refresh has been restructured (its body
    moved into a helper the hook calls). The block must still be reached from
    the per-decision hook, which is checked separately.
    """
    assert SOURCE.count(HAMMOCK_ANCHOR) == 1, SOURCE.count(HAMMOCK_ANCHOR)
    start = SOURCE.index(HAMMOCK_ANCHOR)
    block = SOURCE[start:SOURCE.index("unsigned char *playhouse", start)]
    # The name of the function that contains the block.
    head = SOURCE.rfind("\n{\n", 0, start)
    signature = SOURCE[SOURCE.rfind("\n", 0, head) + 1:head]
    name = re.search(r"(\w+)\(", signature).group(1)
    return code_only(block), name


class TheHammockIsOfferedInSunnyAndCloudyWeather(unittest.TestCase):
    def setUp(self):
        self.hammock, self.owner = hammock_block()

    def test_the_hammock_block_runs_every_decision(self):
        hook = code_only(function_body(
            'extern "C" void __cdecl VF2RefreshHammockEligibility(void *villager)'))
        if self.owner != "VF2RefreshHammockEligibility":
            self.assertRegex(hook, r"\b%s\(" % self.owner,
                             "the hammock refresh is no longer reached from "
                             "the per-decision hook")

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


if __name__ == "__main__":
    unittest.main()
