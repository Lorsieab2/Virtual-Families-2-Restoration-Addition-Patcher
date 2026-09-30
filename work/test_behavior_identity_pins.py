#!/usr/bin/env python3
"""Pins for identity checks that a mutation could previously remove unnoticed.

Each of these was mutated in an audit and the whole work/ suite still passed:

* the exact label-session test in VF2BehaviorLabelSlotIsCurrentFor (a label
  cache slot is "current" only for the same behaviour id and the same serial,
  or exactly one praise later);
* the child-only candidate bound, max age 0x117 -- the last age below the
  0x118 "adult only" minimum;
* the spa slot finder's item-id lock (only the two spa lounger items, never an
  ordinary chaise, which shares eObjectChaise);
* the placement-HANDLE comparisons in VF2SpaLoungerHasHandle and in
  VF2FindAddedFurnitureVenueEx (AGENTS.md 10: identify furniture by placement
  handle, never by point).

The label predicates are compiled from the EMITTED source and executed; the
rest are pinned as exact code lines (comments stripped) in the function that
owns them, not as substrings of the whole generator.
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher
import test_generated_cpp_compiles as compiles

SOURCE = Path(patcher.__file__).read_text(encoding="utf-8")


def function_text(signature):
    # Prefer the DEFINITION: several of these are forward-declared first.
    start = SOURCE.find(signature + "\n{")
    if start < 0:
        start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index("\n}\n", start) + 3]


def code_lines(signature):
    return [line.strip() for line in function_text(signature).splitlines()
            if line.strip() and not line.lstrip().startswith("//")]


HARNESS = r'''
#include <stdio.h>
#include <string.h>
class CVillager { public: int unused; };
%(slot)s
static CVillager *gVF2BehaviorLabelBeforeVillager = 0;
%(active)s
%(current)s
static unsigned char buf[0x1C000];
static unsigned char other[0x1C000];
static void Set(unsigned char *d, int id, unsigned int serial, int praisedId, unsigned int praises) {
    *(int *)(d + 0x1BBA0) = id; *(unsigned int *)(d + 0x1BBA4) = serial;
    *(int *)(d + 0x6B48) = praisedId; *(unsigned int *)(d + 0x6B4C) = praises;
}
int main() {
    CVillager &v = *(CVillager *)buf;
    CVillager &w = *(CVillager *)other;
    for (int pass = 0; pass < 2; ++pass) {
        const char *name = pass ? "active" : "current";
        VF2BehaviorLabelCacheSlot s;
        memset(&s, 0, sizeof s);
        s.villager = &v; s.behaviorId = 5; s.behaviorSerial = 10; s.praiseCount = 0;
        gVF2BehaviorLabelBeforeVillager = &v;
#define Q(x) (pass ? VF2BehaviorLabelCacheStillActive(&s) : VF2BehaviorLabelSlotIsCurrentFor(x, &s))
        Set(buf, 5, 10, 0, 0);  printf("%%s same %%d\n", name, (int)Q(v));
        Set(buf, 5, 11, 0, 0);  printf("%%s next_unpraised %%d\n", name, (int)Q(v));
        Set(buf, 5, 11, 5, 1);  printf("%%s praise1 %%d\n", name, (int)Q(v));
        Set(buf, 5, 12, 5, 2);  printf("%%s praise2 %%d\n", name, (int)Q(v));
        Set(buf, 5, 14, 5, 3);  printf("%%s skip %%d\n", name, (int)Q(v));
        Set(buf, 5, 11, 5, 3);  printf("%%s older %%d\n", name, (int)Q(v));
        Set(buf, 6, 12, 5, 2);  printf("%%s other_behavior %%d\n", name, (int)Q(v));
        Set(other, 5, 12, 5, 2);
        if (pass) gVF2BehaviorLabelBeforeVillager = &w;
        printf("%%s other_villager %%d\n", name, (int)Q(w));
    }
    return 0;
}
'''


class TheLabelSessionTestIsExact(unittest.TestCase):
    def test_both_predicates_accept_only_the_same_session(self):
        vcvars = compiles._vcvars()
        if vcvars is None:
            self.skipTest("no Visual Studio toolchain on this machine")
        start = SOURCE.index("struct VF2BehaviorLabelCacheSlot {")
        slot = SOURCE[start:SOURCE.index("};", start) + 2]
        harness = HARNESS % {
            "slot": slot,
            "active": function_text(
                "static bool VF2BehaviorLabelCacheStillActive(VF2BehaviorLabelCacheSlot *slot)"),
            "current": function_text("static bool VF2BehaviorLabelSlotIsCurrentFor("),
        }
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "harness.cpp").write_text(harness, encoding="ascii")
            build = subprocess.run(
                '"%s" >nul 2>&1 && cd /d "%s" && cl /nologo /EHsc harness.cpp' % (vcvars, work),
                shell=True, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout[-1500:])
            run = subprocess.run([str(work / "harness.exe")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0)
        got = {}
        for line in run.stdout.splitlines():
            name, case, value = line.split()
            got[(name, case)] = int(value)
        expected = {
            "same": 1,             # same behaviour, same serial
            "next_unpraised": 0,   # a new session of the same behaviour
            "praise1": 1,          # one praise: same activity, re-baselined
            "praise2": 1,          # a second praise of the same activity
            "skip": 0,             # serial jumped by more than one
            "older": 0,            # serial went backwards
            "other_behavior": 0,
            "other_villager": 0,
        }
        for name in ("current", "active"):
            for case, value in expected.items():
                with self.subTest(predicate=name, case=case):
                    self.assertEqual(got[(name, case)], value)


class TheChildOnlyBoundIsTheLastChildAge(unittest.TestCase):
    def test_child_only_max_age_is_one_below_the_adult_minimum(self):
        child = code_lines(
            "static void EnableChildOnlyAutonomousCandidateWithWeight(unsigned char *villager, "
            "unsigned int behavior, unsigned int weight)")
        adult = code_lines(
            "static void EnableAdultOnlyAutonomousCandidateWithWeight(unsigned char *villager, "
            "unsigned int behavior, unsigned int weight)")
        self.assertIn("*(unsigned int *)(candidate + 0x48) = 0x117;", child)
        self.assertIn("*(unsigned int *)(candidate + 0x4C) = 0;", child)
        self.assertIn("*(unsigned int *)(candidate + 0x4C) = 0x118;", adult)
        # The child-scold achievement guard uses the same boundary.
        self.assertIn("< 0x118) ", SOURCE)

    def test_the_refreshed_child_candidates_keep_the_bound(self):
        body = function_text('extern "C" void __cdecl VF2RefreshHammockEligibility(')
        refresh = body
        if "VF2RefreshVolatileCandidates(" in body:  # refactored form
            refresh = function_text("static void VF2RefreshVolatileCandidates(")
        lines = [line.strip() for line in refresh.splitlines()]
        for name in ("playhouse", "snow"):
            with self.subTest(candidate=name):
                self.assertIn("*(unsigned int *)(%s + 0x48) = 0x117;" % name, lines)


class TheSpaSlotFinderIsLockedToSpaLoungers(unittest.TestCase):
    SIG = "static int VF2FindFreeSpaLoungerSlot(CVillager &villager)"

    def test_only_the_two_spa_items_pass(self):
        lines = code_lines(self.SIG)
        guard = ["if (itemId != __VF2_INVISIBLE_SPA_LOUNGER_ITEM_ID__ &&",
                 "itemId != __VF2_SPA_LOUNGER_ITEM_ID__) {",
                 "continue;",
                 "}"]
        index = lines.index(guard[0])
        self.assertEqual(lines[index:index + 4], guard)
        comparisons = re.findall(r"itemId\s*(?:==|!=|<=|>=|<|>)\s*[\w_]+",
                                 "\n".join(lines))
        self.assertEqual(
            sorted(comparisons),
            sorted(["itemId != __VF2_INVISIBLE_SPA_LOUNGER_ITEM_ID__",
                    "itemId != __VF2_SPA_LOUNGER_ITEM_ID__"]),
            "the spa slot finder accepts some other item; an ordinary chaise "
            "shares eObjectChaise and must never be treated as a spa lounger")


class FurnitureIsIdentifiedByHandle(unittest.TestCase):
    def test_spa_lounger_has_handle_compares_the_handle(self):
        lines = code_lines("static bool VF2SpaLoungerHasHandle(int handle)")
        compare = "if (*reinterpret_cast<int *>(record + 0x04) != handle) continue;"
        self.assertIn(compare, lines)
        self.assertLess(lines.index(compare),
                        lines.index("int itemId = *reinterpret_cast<int *>(record);"),
                        "the item id is read before the handle is matched, so "
                        "the first active record decides")

    def test_the_venue_verifies_the_returned_handle(self):
        lines = code_lines("static bool VF2FindAddedFurnitureVenueEx(")
        verify = "if (!VF2AddedFurnitureHandleIsItem(info.unknown0, recordItem)) continue;"
        self.assertIn(verify, lines)
        find = next(i for i, line in enumerate(lines)
                    if line.startswith("if (!FurnitureManager.FindFurniture("))
        distance = lines.index("long dx = info.point.x - feet.x;")
        self.assertTrue(find < lines.index(verify) < distance,
                        "the FindFurniture result must be verified by handle "
                        "before it can win on distance")

    def test_the_handle_helper_matches_record_handle_and_item(self):
        lines = code_lines("static bool VF2AddedFurnitureHandleIsItem(int handle, int itemId)")
        compare = "if (*reinterpret_cast<int *>(record + 0x04) != handle) continue;"
        answer = "return *reinterpret_cast<int *>(record) == itemId;"
        self.assertIn(compare, lines)
        self.assertIn(answer, lines)
        self.assertEqual(lines.index(answer), lines.index(compare) + 1)


if __name__ == "__main__":
    unittest.main()
