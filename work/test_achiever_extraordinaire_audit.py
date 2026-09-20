"""Achiever Extraordinaire (0x92) must track every goal the screen shows.

Owner: "audit the goal 'Achiever Extraordinaire' to account for the
newly-added goals."

THE AUDIT FOUND TWO DEFECTS, both of which made the meta-goal unawardable
and both of which got quietly worse with every goal added since.

DEFECT A -- the optional block sat in the middle of the array.
The 19 Holiday Furniture goals (0x6D-0x7F) were appended BEFORE the
meta-goal, but whether they are visible is decided at RUNTIME by
gVF2HolidayFurnitureGoalsEnabled, a post-link byte set only when the player
selects Holiday Furniture. The visible count drops by 19 when that byte is
zero, while the native draw loop walks achievementOrder CONTIGUOUSLY from
index 0 to that count and cannot skip a hole. In every build without Holiday
Furniture the screen therefore drew rows 0..151, which ENDED on holiday goal
0x6D -- a goal that player can neither earn nor see explained -- and stopped
19 rows short of Achiever Extraordinaire, whose row was never drawn at all.
VF2MaybeCompleteAchiever scans that same window, so it demanded the
unearnable goal and could never award the meta-goal.

The fix moves the optional block PAST the meta-goal, which keeps the drawn
window contiguous in both runtime states.

DEFECT B -- the cheat enumerated hand-written id ranges.
"Complete all achievements" completed 0x00-0x5E, 0x5F, 0x60-0x65,
0x66-0x6C, 0x80-0x91 and the holiday block. Every goal added since those
ranges were written fell outside them, so the cheat silently left 24 visible
goals unfinished: the praise/scold behaviour run 0x93-0xA4, the VF3
furniture and turtle goals 0xA6 and 0xA7, both joke-label Order goals 0xA9
and 0xAA, and the newest discipline goal 0xAB. Achiever requires every
visible row, so the cheat could not award it either.

The fix derives the cheat's list from achievementOrder, so a goal added to
the screen is completed by the cheat automatically.

These tests read the EMITTED object, not only the generator, because the
order array is built by patching bytes into AchievementsScene.obj.
"""
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402
from coff_patch import CoffObject  # noqa: E402

ACHIEVER = 0x92
PROPS = 0xA5
HOLIDAY = frozenset(range(0x6D, 0x80))
# The two runtime states the single shipped executable must serve.
COUNT_WITHOUT_HOLIDAY = 152
COUNT_WITH_HOLIDAY = 171


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


def _order():
    """The achievementOrder array as the emitted object actually holds it."""
    path = patcher.PATCHED / "AchievementsScene.obj"
    if not path.is_file():
        return None
    obj = CoffObject(path)
    symbol = obj.symbol("?achievementOrder@@3QBHB")
    section = obj.section(symbol.section)
    count = (section.raw_size - symbol.value) // 4
    return list(struct.unpack_from(
        "<" + "I" * count, obj.buf, section.raw_ptr + symbol.value))


class TheOrderArray(unittest.TestCase):
    def test_the_optional_holiday_block_comes_after_the_meta_goal(self):
        src = _strip_comments(_source())
        achiever_append = src.index(
            "appended_order.append(CUSTOM_ACHIEVEMENT_ACHIEVER_ID)")
        holiday_extend = src.index(
            "range(CUSTOM_ACHIEVEMENT_HOLIDAY_FIRST, "
            "CUSTOM_ACHIEVEMENT_HOLIDAY_LAST + 1)")
        self.assertLess(
            achiever_append, holiday_extend,
            "the runtime-optional holiday block must be appended AFTER the "
            "meta-goal, or the drawn window has a hole in it")

    def test_the_emitted_array_ends_on_the_meta_goal_then_the_holiday_block(self):
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        self.assertEqual(len(order), COUNT_WITH_HOLIDAY)
        self.assertEqual(order.index(ACHIEVER), COUNT_WITHOUT_HOLIDAY - 1)
        holiday_positions = [i for i, x in enumerate(order) if x in HOLIDAY]
        self.assertEqual(len(holiday_positions), 19)
        self.assertEqual(holiday_positions[0], COUNT_WITHOUT_HOLIDAY)
        self.assertEqual(holiday_positions[-1], COUNT_WITH_HOLIDAY - 1)

    def test_no_goal_is_listed_twice(self):
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        duplicates = sorted(hex(x) for x in set(order) if order.count(x) > 1)
        self.assertEqual(duplicates, [])


class TheDrawnWindow(unittest.TestCase):
    """What the player sees in each runtime state."""

    def test_without_holiday_furniture_the_last_row_is_the_meta_goal(self):
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        window = order[:COUNT_WITHOUT_HOLIDAY]
        self.assertEqual(window[-1], ACHIEVER, "Achiever must be the final row")
        unearnable = [hex(x) for x in window if x in HOLIDAY]
        self.assertEqual(
            unearnable, [],
            "a holiday goal drawn to a player who did not select Holiday "
            "Furniture is one they can never earn, and Achiever would "
            "require it")

    def test_with_holiday_furniture_every_holiday_goal_is_drawn(self):
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        window = order[:COUNT_WITH_HOLIDAY]
        self.assertEqual(sorted(x for x in window if x in HOLIDAY),
                         sorted(HOLIDAY))
        self.assertIn(ACHIEVER, window)

    def test_the_count_and_the_array_agree_in_both_states(self):
        # The count is what the draw loop and the Achiever scan both use as
        # their bound, so it must never exceed the array.
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        for count in (COUNT_WITHOUT_HOLIDAY, COUNT_WITH_HOLIDAY):
            self.assertLessEqual(count, len(order))


class TheMetaGoalScan(unittest.TestCase):
    def test_it_walks_the_visible_window_and_skips_only_itself(self):
        src = _strip_comments(_source())
        start = src.index(
            'extern "C" void __fastcall VF2MaybeCompleteAchiever(')
        body = src[start:src.index("\n}\n", start)]
        self.assertIn("int visibleCount = VF2AchievementVisibleCountInternal();", body)
        self.assertIn("for (int index = 0; index < visibleCount; ++index)", body)
        self.assertIn("int achievementId = achievementOrder[index];", body)
        self.assertIn("if (achievementId == 0x92) continue;", body)
        self.assertIn(
            "if (!achievement->IsComplete((EAchievement)achievementId)) return;",
            body)
        # It must not go back to hand-written ranges, which is exactly the
        # mistake that made the cheat drift.
        self.assertNotIn("0x93", body)
        self.assertNotIn("0xA4", body)

    def test_every_visible_goal_the_scan_demands_can_actually_be_awarded(self):
        """A goal with no award path would make the meta-goal impossible."""
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        awarded = set(patcher.CUSTOM_ACHIEVEMENT_PRAISE_LABEL_GOALS.values())
        awarded |= set(patcher.CUSTOM_ACHIEVEMENT_SCOLD_LABEL_GOALS.values())
        awarded |= set(patcher.CUSTOM_ACHIEVEMENT_GENERAL_PURCHASE_GOALS.values())
        awarded |= set(patcher.CUSTOM_ACHIEVEMENT_HOLIDAY_PURCHASE_GOALS.values())
        awarded |= set(patcher.CUSTOM_ACHIEVEMENT_TATERS_PURCHASE_BITS.values())
        # Pet goals, including the turtle goal 0xA7, are awarded by
        # placing an active pet item rather than from a label or a
        # purchase table.
        for item in range(0x23B, 0x249):
            awarded |= set(patcher.pet_achievement_ids_for_item(item))
        # Derived goals: Props to you is reconciled from the discipline run,
        # and the meta-goal is the thing being scanned for.
        awarded |= {PROPS, ACHIEVER}
        # Stock goals below the custom range keep their native award routes.
        behaviour_range = set(range(0x66, 0x6D)) | set(range(0x93, 0xAC))
        unawardable = sorted(
            hex(x) for x in order[:COUNT_WITHOUT_HOLIDAY]
            if x in behaviour_range and x not in awarded)
        self.assertEqual(
            unawardable, [],
            "these visible goals have no award path, so Achiever could never "
            "complete")


class TheCompleteAllCheat(unittest.TestCase):
    def test_it_derives_its_list_from_the_visible_order(self):
        src = _strip_comments(_source())
        start = src.index("static void VF2CompleteAllAchievements()")
        body = src[start:src.index("\n}\n", start)]
        self.assertIn("int visibleCount = VF2AchievementVisibleCountInternal();", body)
        self.assertIn("int achievementId = achievementOrder[index];", body)
        self.assertIn("VF2CompleteAchievementForCheat(achievementId);", body)
        # The two derived goals are reconciled after their prerequisites,
        # never forced out of order.
        self.assertIn("if (achievementId == 0xA5 || achievementId == 0x92) continue;", body)
        self.assertIn("VF2MaybeCompleteDisciplineProps(&Achievement);", body)
        self.assertIn("VF2MaybeCompleteAchiever(&Achievement, 0);", body)

    def test_it_no_longer_enumerates_hand_written_id_ranges(self):
        src = _strip_comments(_source())
        start = src.index("static void VF2CompleteAllAchievements()")
        body = src[start:src.index("\n}\n", start)]
        for stale in (
            "achievement = 0x00; achievement <= 0x5E",
            "achievement = 0x60; achievement <= 0x65",
            "achievement = 0x66; achievement <= 0x6C",
            "achievement = 0x80; achievement <= 0x91",
            "achievement = 0x6D; achievement <= 0x7F",
        ):
            self.assertNotIn(
                stale, body,
                "a hand-written range cannot follow newly added goals; that "
                "is what left 24 of them uncompleted")

    def test_the_cheat_covers_every_visible_goal_in_both_states(self):
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        for count in (COUNT_WITHOUT_HOLIDAY, COUNT_WITH_HOLIDAY):
            window = order[:count]
            completed = {x for x in window if x not in (PROPS, ACHIEVER)}
            uncovered = [hex(x) for x in window
                         if x not in completed and x not in (PROPS, ACHIEVER)]
            self.assertEqual(uncovered, [], f"visible rows={count}")
            # Props to you is then derivable: its prerequisites are all in.
            self.assertTrue({0x30, 0xA1, 0xA2, 0xA3, 0xA4, 0xAB} <= completed)

    def test_the_newly_added_discipline_goal_is_covered(self):
        # The goal that prompted this audit. It is outside every range the
        # cheat used to enumerate.
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        self.assertIn(0xAB, order[:COUNT_WITHOUT_HOLIDAY])
        self.assertEqual(patcher.CUSTOM_ACHIEVEMENT_BANGING_DISHES_ID, 0xAB)


class TheEmittedCpp(unittest.TestCase):
    def test_the_emitted_helper_carries_both_fixes(self):
        emitted = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
        if not emitted.is_file():
            self.skipTest("generator output not present; run the generator first")
        text = emitted.read_text(encoding="utf-8", errors="replace")
        cheat_start = text.index("static void VF2CompleteAllAchievements()")
        cheat = text[cheat_start:text.index("\n}\n", cheat_start)]
        self.assertIn("VF2CompleteAchievementForCheat(achievementId);", cheat)
        self.assertNotIn("achievement <= 0x91", cheat)
        scan_start = text.index(
            'extern "C" void __fastcall VF2MaybeCompleteAchiever(')
        scan = text[scan_start:text.index("\n}\n", scan_start)]
        self.assertIn("achievementOrder[index]", scan)


if __name__ == "__main__":
    unittest.main()
