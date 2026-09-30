#!/usr/bin/env python3
"""Praise and scolding train candidate weights; the per-decision refresh must keep them.

Stock mechanism, from work/theMainScene_disasm.txt:

* InvokeReward:   w += max(1, (cand[+0x14] - w) / 20)     ; towards the maximum
* InvokeScolding: w -= max(1, (w - cand[+0x10]) / 20)     ; towards the minimum

where w is the candidate weight at +0x0C of the current behaviour's 0xD0-byte
record (CVillager+0x6BB8). SaveAI saves w, LoadAI restores it.

VF2RefreshHammockEligibility runs at the start of every
CVillagerAI::DecideWhatToDo and used to write a FIXED weight into the hammock,
playhouse, snow, Home Gym and Yoga candidates, so a praise or scolding on any
of them was undone at the villager's next decision.

These tests compile the EMITTED VF2SetGatedCandidate with cl and drive it
through praise, scolding and gate changes, rather than pattern-matching it.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher
import test_generated_cpp_compiles as compiles

SOURCE = Path(patcher.__file__).read_text(encoding="utf-8")


def function_text(signature):
    start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index("\n}\n", start) + 3]


def code_only(body):
    return "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("//"))


HARNESS = r'''
#include <stdio.h>
#include <string.h>
%(helper)s
static unsigned int W(unsigned char *c) { return *(unsigned int *)(c + 0x0C); }
static void Praise(unsigned char *c) {
    int w = (int)W(c), mx = 45000, d = (mx - w) / 20; if (d < 1) d = 1;
    *(unsigned int *)(c + 0x0C) = (unsigned int)(w + d);
}
static void Scold(unsigned char *c) {
    int w = (int)W(c), mn = 50, d = (w - mn) / 20; if (d < 1) d = 1;
    *(unsigned int *)(c + 0x0C) = (unsigned int)(w - d);
}
int main() {
    unsigned char c[0xD0];
    memset(c, 0, sizeof c);
    // Load: eligible -> fixed weight; ineligible -> 0 (unchanged behaviour).
    VF2SetGatedCandidate(c, 1, 3000, true);  printf("load_on %%u %%u\n", c[0xCD], W(c));
    Praise(c); unsigned int praised = W(c);
    VF2SetGatedCandidate(c, 1, 3000, false); printf("praise_kept %%u %%u\n", W(c), praised);
    VF2SetGatedCandidate(c, 0, 3000, false); printf("gate_off %%u %%u\n", c[0xCD], W(c));
    VF2SetGatedCandidate(c, 1, 3000, false); printf("gate_back %%u %%u\n", c[0xCD], W(c));
    Scold(c); Scold(c); unsigned int scolded = W(c);
    VF2SetGatedCandidate(c, 1, 3000, false); printf("scold_kept %%u %%u\n", W(c), scolded);
    VF2SetGatedCandidate(c, 0, 3000, true);  printf("load_off %%u %%u\n", c[0xCD], W(c));
    VF2SetGatedCandidate(c, 1, 3000, false); printf("first_on %%u %%u\n", c[0xCD], W(c));
    return 0;
}
'''


class TheRefreshKeepsTrainedWeights(unittest.TestCase):
    def test_the_emitted_helper_keeps_praise_and_scolding(self):
        vcvars = compiles._vcvars()
        if vcvars is None:
            self.skipTest("no Visual Studio toolchain on this machine")
        helper = function_text("static void VF2SetGatedCandidate(")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "harness.cpp").write_text(HARNESS % {"helper": helper}, encoding="ascii")
            build = subprocess.run(
                '"%s" >nul 2>&1 && cd /d "%s" && cl /nologo /EHsc harness.cpp' % (vcvars, work),
                shell=True, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout[-1500:])
            run = subprocess.run([str(work / "harness.exe")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0)
        rows = {parts[0]: [int(x) for x in parts[1:]]
                for parts in (line.split() for line in run.stdout.splitlines())}
        self.assertEqual(rows["load_on"], [1, 3000])
        praised = rows["praise_kept"][1]
        self.assertGreater(praised, 3000)
        self.assertEqual(rows["praise_kept"][0], praised,
                         "the per-decision refresh undid a praise")
        self.assertEqual(rows["gate_off"], [0, praised],
                         "an ineligible candidate must be disabled without "
                         "losing its trained weight")
        self.assertEqual(rows["gate_back"], [1, praised])
        self.assertEqual(rows["scold_kept"][0], rows["scold_kept"][1],
                         "the per-decision refresh undid a scolding")
        self.assertLess(rows["scold_kept"][0], praised)
        # The load-time path is unchanged: fixed weight or 0.
        self.assertEqual(rows["load_off"], [0, 0])
        self.assertEqual(rows["first_on"], [1, 3000],
                         "a candidate that was ineligible at load gets its "
                         "default weight when it first becomes eligible")


class TheRefreshIsWiredThatWay(unittest.TestCase):
    def test_the_per_decision_hook_preserves(self):
        hook = code_only(function_text(
            'extern "C" void __cdecl VF2RefreshHammockEligibility(void *villager)'))
        self.assertIn("VF2RefreshVolatileCandidates((unsigned char *)villager, false);", hook)

    def test_every_volatile_candidate_goes_through_the_helper(self):
        body = code_only(function_text(
            "static void VF2RefreshVolatileCandidates(unsigned char *data, bool resetWeights)"))
        self.assertIn("VF2RefreshWorkoutEligibilityEx(data, resetWeights);", body)
        for name in ("candidate", "playhouse", "snow"):
            with self.subTest(candidate=name):
                self.assertRegex(body, r"VF2SetGatedCandidate\(%s, \w+, \d+, resetWeights\);" % name)
                self.assertNotIn("(%s + 0x0C)" % name, body,
                                 "%s's weight is written directly again" % name)
        workout = code_only(function_text(
            "static void VF2RefreshWorkoutEligibilityEx(unsigned char *data, bool resetWeights)"))
        for name in ("gym", "yoga"):
            with self.subTest(candidate=name):
                self.assertIn("VF2SetGatedCandidate(%s, " % name, workout)
                self.assertNotIn("(%s + 0x0C)" % name, workout)

    def test_the_load_path_still_resets(self):
        enabler = code_only(function_text(
            'extern "C" void __cdecl VF2EnableAutonomousCandidates(void *villager)'))
        self.assertIn("VF2RefreshVolatileCandidates(data, true);", enabler)
        self.assertNotIn("VF2RefreshHammockEligibility(data);", enabler,
                         "the enabler would take the per-decision (preserving) "
                         "path at load")


if __name__ == "__main__":
    unittest.main()
