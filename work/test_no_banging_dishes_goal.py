"""The fifth child-discipline goal: "No banging dishes together!" (0xAB).

Owner request: a new goal titled "No banging dishes together!" with the
description "You scolded a child for banging dishes.", counting towards
"Props to you" (0xA5).

SHAPE, copied from the four existing child-discipline goals 0xA1-0xA4:

  * the award is an EXACT match on the villager's raw behaviour label at the
    moment of the scold. The native label is "Banging dishes!" -- with the
    exclamation mark -- under string key BangingDishes in theStringManager.obj,
    which this file pins so the comparison can never drift to a paraphrase;
  * child-only: the emitted scold case guards on internal age < 0x118 like
    its four siblings, and the Python dispatch mirror does the same;
  * Props to you has TWO decision sites (the scold award path and the
    load-reconciliation path) plus the Python predicate the suite uses; all
    three must require 0xAB, because 0xAB is not inside the 0xA1-0xA4 run
    those sites walk;
  * the goal is visible: appended to achievementOrder right after 0xA4, the
    C++ visible count and the manifest count both grow to 29 behaviour goals,
    and the completed-count reads the record explicitly.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402

GOAL = 0xAB
LABEL = "Banging dishes!"
TITLE = "No banging dishes together!"
DESCRIPTION = "You scolded a child for banging dishes."


def _source():
    return GEN.read_text(encoding="utf-8")


def _strip_comments(text):
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        out.append(line.split("//")[0] if "//" in line else line)
    return "\n".join(out)


def _function(src, signature_start):
    i = src.index(signature_start)
    close = src.index(")", i)
    end = src.index("\n}\n", close)
    return src[i:end]


class TheIds(unittest.TestCase):
    def test_the_goal_is_the_next_record_past_the_defined_edge(self):
        self.assertEqual(patcher.CUSTOM_ACHIEVEMENT_BANGING_DISHES_ID, GOAL)
        self.assertEqual(patcher.CUSTOM_ACHIEVEMENT_DEFINED_LAST_ID, GOAL)
        self.assertEqual(patcher.CUSTOM_ACHIEVEMENT_LAST_ID, GOAL)
        self.assertEqual(patcher.CUSTOM_ACHIEVEMENT_RESERVED_FIRST_ID, GOAL + 1)
        # 0xA8 stays the purchase-mask scratch record; nothing is defined there.
        self.assertNotIn(0xA8, {row[0] for row in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS})

    def test_the_row_carries_the_requested_texts(self):
        rows = {row[0]: row[1:] for row in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS}
        self.assertEqual(rows[GOAL], ("behavior", TITLE, DESCRIPTION))
        # Strings are derived from the id, so the new row gets its own pair.
        short_id, long_id = patcher.custom_achievement_string_ids(GOAL)
        self.assertEqual(long_id, short_id + 1)
        self.assertNotIn(GOAL, patcher.CUSTOM_ACHIEVEMENT_COIN_REWARDS, "pays the default 25 like its siblings")


class TheLabel(unittest.TestCase):
    def test_the_native_label_text_exists_with_the_exclamation_mark(self):
        obj = patcher.SRC_OBJS / "theStringManager.obj"
        if not obj.is_file():
            self.skipTest("missing build input theStringManager.obj")
        data = obj.read_bytes()
        self.assertIn(b"BangingDishes\0", data)
        self.assertIn(LABEL.encode() + b"\0", data)

    def test_the_exact_label_is_a_child_only_scold_award(self):
        self.assertEqual(patcher.CUSTOM_ACHIEVEMENT_SCOLD_LABEL_GOALS[LABEL], GOAL)
        self.assertIn(LABEL, patcher.CUSTOM_ACHIEVEMENT_CHILD_SCOLD_LABELS)
        self.assertEqual(patcher.custom_achievement_scold_label_dispatch(LABEL, 0x117), GOAL)
        self.assertIsNone(patcher.custom_achievement_scold_label_dispatch(LABEL, 0x118), "adults do not earn it")
        self.assertIsNone(patcher.custom_achievement_scold_label_dispatch(LABEL), "no age, no award")
        for near in ("Banging dishes", "Banging dishes! ", "banging dishes!", "Doing the dishes"):
            self.assertIsNone(patcher.custom_achievement_scold_label_dispatch(near, 0x117), near)
        self.assertIsNone(patcher.custom_achievement_praise_label_dispatch(LABEL), "a praise never awards it")

    def test_the_emitted_scold_case_guards_on_child_age(self):
        emitted = patcher.PATCHED / "vf2_spontaneous_behaviors.cpp"
        if not emitted.is_file():
            self.skipTest("generator output not present; run the generator first")
        text = emitted.read_text(encoding="utf-8", errors="replace")
        case = re.search(
            r'if \(VF2RawBehaviorLabelEquals\(label, "Banging dishes!"\)\) \{ '
            r'if \(\*\(int \*\)\(\(unsigned char \*\)&villager \+ 0x6A54\) < 0x118\) '
            r'Achievement\.SetComplete\(\(EAchievement\)0xAB\); \}',
            text,
        )
        self.assertIsNotNone(case, "the emitted scold case for the label is missing or not child-gated")


class PropsToYou(unittest.TestCase):
    def test_the_python_predicate_requires_the_fifth_goal(self):
        complete = {0x30, 0xA1, 0xA2, 0xA3, 0xA4, GOAL}
        self.assertTrue(patcher.custom_achievement_props_is_satisfied(complete))
        self.assertFalse(patcher.custom_achievement_props_is_satisfied(complete - {GOAL}))

    def test_both_cpp_decision_sites_require_the_fifth_goal(self):
        src = _strip_comments(_source())
        load_site = _function(src, "static void VF2MaybeCompleteDisciplineProps(CAchievement *achievement)")
        scold_site = _function(src, "static void VF2MaybeCompleteDisciplineProps()\n")
        for name, body in (("load reconciliation", load_site), ("scold award", scold_site)):
            with self.subTest(site=name):
                loop = body.index("for (int id = 0xA1; id <= 0xA4; ++id)")
                guard = body.index("IsComplete((EAchievement)0xAB)) return;")
                award = body.index("SetComplete((EAchievement)0xA5);")
                self.assertLess(loop, guard, "the 0xAB guard follows the 0xA1-0xA4 loop")
                self.assertLess(guard, award, "0xA5 is awarded only after the 0xAB guard")


class TheGoalsScreen(unittest.TestCase):
    def test_the_visible_counts_agree_at_twenty_nine(self):
        src = _strip_comments(_source())
        self.assertIn("if (kVF2IncludeBehaviorGoals) count += 29;", src)
        self.assertIn("behavior_goal_visible_count = 29", src)
        self.assertNotIn("count += 28;", src)

    def test_the_completed_count_reads_the_record_explicitly(self):
        src = _strip_comments(_source())
        f = _function(src, 'extern "C" int __cdecl VF2AchievementsCompleteVisible(')
        self.assertIn("if (achievement->IsComplete((EAchievement)0xAB)) ++completed;", f)
        # Inside the behaviour-goal gate, beside the two Order goals.
        self.assertLess(f.index("0xAA)) ++completed;"), f.index("0xAB)) ++completed;"))

    def test_the_goal_is_ordered_with_its_siblings_ahead_of_props(self):
        src = _strip_comments(_source())
        i = src.index("    appended_order = []")
        block = src[i:src.index("    order_sym = scene_obj.symbol(", i)]
        self.assertIn("CUSTOM_ACHIEVEMENT_DISCIPLINE_LAST_ID + 1,", block)
        dishes = block.index("appended_order.append(CUSTOM_ACHIEVEMENT_BANGING_DISHES_ID)")
        props = block.index("appended_order.append(CUSTOM_ACHIEVEMENT_PROPS_ID)")
        self.assertLess(dishes, props)
        self.assertNotIn("CUSTOM_ACHIEVEMENT_PROPS_ID + 1,", block, "the old range would skip the appended id")


if __name__ == "__main__":
    unittest.main()
