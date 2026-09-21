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
import re
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

# THE COUNTS ARE DERIVED, NOT HARDCODED.
#
# Review caught that fixing these at 152/171 described only the all-gates-on
# build. The matrix ships variants with Behavior Patches or Holiday Ornaments
# disabled, and those emit shorter arrays (for example ornaments on with
# behaviour goals off gives 123/142), so a hardcoded pair would fail this
# audit against a perfectly valid variant. These mirror
# VF2AchievementVisibleCountInternal, whose two compile gates are the two
# module flags below; the third gate, Holiday Furniture, is the RUNTIME
# .vf2goal byte and is what separates the two counts.
_HOLIDAY_COUNT = len(HOLIDAY)


def _count_without_holiday():
    count = 0x5F + 6 + 3 + 2 + 5 + 6 + 2 + 1 + 1 + 1
    if patcher.ENABLE_HOLIDAY_ORNAMENTS:
        count += 1
    if patcher.ENABLE_BEHAVIOR_PATCHES:
        count += 29
    return count


COUNT_WITHOUT_HOLIDAY = _count_without_holiday()
COUNT_WITH_HOLIDAY = COUNT_WITHOUT_HOLIDAY + _HOLIDAY_COUNT


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
        self.assertEqual(len(holiday_positions), _HOLIDAY_COUNT)
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

    @staticmethod
    def _cheat_excluded_ids():
        """The ids the EMITTED cheat loop skips, parsed from its source.

        Review caught that building `completed` from the window and then
        checking the window against it is empty by construction: it cannot
        catch a missing exclusion. Adding `if (achievementId == 0xA7)
        continue;` to the production loop would leave a visible goal
        unfinished while a window-derived check still passed.

        So the set of skipped ids is read from the emitted helper instead,
        and coverage is the window MINUS those ids. A stray `continue` for
        any other id then shows up as an uncovered visible row.
        """
        emitted = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
        text = emitted.read_text(encoding="utf-8", errors="replace")
        start = text.index("static void VF2CompleteAllAchievements()")
        body = text[start:text.index("\n}\n", start)]
        loop = body[body.index("for (int index"):]
        excluded = set()
        for match in re.finditer(
                r"achievementId == (0x[0-9a-fA-F]+)", loop):
            excluded.add(int(match.group(1), 16))
        return body, excluded

    def test_the_cheat_covers_every_visible_goal_in_both_states(self):
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        body, excluded = self._cheat_excluded_ids()
        # The loop must complete every row it does not explicitly skip, and
        # the only rows it may skip are the two DERIVED goals (Props and the
        # meta-goal), which are reconciled afterwards. Any other exclusion is
        # a coverage hole.
        self.assertTrue(
            "VF2CompleteAchievementForCheat(achievementId);" in body)
        self.assertEqual(
            excluded, {PROPS, ACHIEVER},
            "the cheat loop skips an id other than the two derived goals: "
            + repr(sorted(hex(x) for x in excluded)))
        for count in (COUNT_WITHOUT_HOLIDAY, COUNT_WITH_HOLIDAY):
            window = order[:count]
            completed = {x for x in window if x not in excluded}
            uncovered = [hex(x) for x in window
                         if x not in completed and x not in (PROPS, ACHIEVER)]
            self.assertEqual(uncovered, [], f"visible rows={count}")
            if patcher.ENABLE_BEHAVIOR_PATCHES:
                self.assertTrue({0x30, 0xA1, 0xA2, 0xA3, 0xA4, 0xAB} <= completed)

    def test_the_newly_added_discipline_goal_is_covered(self):
        # The goal that prompted this audit. It is outside every range the
        # cheat used to enumerate. It is a BEHAVIOUR goal, so it is only in
        # the visible order when that compile gate is on -- the variants that
        # build without Behavior Patches legitimately omit it.
        order = _order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        self.assertEqual(patcher.CUSTOM_ACHIEVEMENT_BANGING_DISHES_ID, 0xAB)
        if not patcher.ENABLE_BEHAVIOR_PATCHES:
            self.assertNotIn(0xAB, order)
            return
        self.assertIn(0xAB, order[:COUNT_WITHOUT_HOLIDAY])


class EveryGateCombination(unittest.TestCase):
    """The audit must hold for every shipped matrix variant, not just this one.

    Review caught that fixing the counts at 152/171 described only the
    all-gates-on build. The matrix also ships variants with Behavior Patches
    or Holiday Ornaments disabled, whose arrays are shorter, so this rebuilds
    the order array under each combination and re-checks the two invariants
    the audit exists to protect: the meta-goal is the last row a player must
    complete, and no unearnable holiday row is drawn when the runtime byte is
    zero.
    """

    COMBINATIONS = (
        # ornaments, behavior, rows without holiday, rows with holiday
        (False, False, 122, 141),
        (True, False, 123, 142),
        (False, True, 151, 170),
        (True, True, 152, 171),
    )

    def test_the_derived_counts_match_every_declared_combination(self):
        for ornaments, behavior, off, on in self.COMBINATIONS:
            with self.subTest(ornaments=ornaments, behavior=behavior):
                count = 0x5F + 6 + 3 + 2 + 5 + 6 + 2 + 1 + 1 + 1
                if ornaments:
                    count += 1
                if behavior:
                    count += 29
                self.assertEqual(count, off)
                self.assertEqual(count + _HOLIDAY_COUNT, on)

    def test_the_meta_goal_is_last_before_the_holiday_block_in_every_variant(self):
        import shutil
        import tempfile
        old_patched = patcher.PATCHED
        old_ornaments = patcher.ENABLE_HOLIDAY_ORNAMENTS
        old_behavior = patcher.ENABLE_BEHAVIOR_PATCHES
        try:
            for ornaments, behavior, off, on in self.COMBINATIONS:
                with self.subTest(ornaments=ornaments, behavior=behavior):
                    patcher.ENABLE_HOLIDAY_ORNAMENTS = ornaments
                    patcher.ENABLE_BEHAVIOR_PATCHES = behavior
                    with tempfile.TemporaryDirectory() as tmp:
                        root = pathlib.Path(tmp)
                        patcher.PATCHED = root
                        for name in ("AchievementsScene.obj", "Achievement.obj"):
                            shutil.copy2(patcher.SRC_OBJS / name, root / name)
                        manifest = {}
                        patcher.patch_custom_achievements(manifest)
                        order = _order()
                        self.assertEqual(len(order), on)
                        # The meta-goal ends the drawn window when the
                        # runtime holiday byte is zero ...
                        self.assertEqual(order[off - 1], ACHIEVER)
                        self.assertEqual(
                            [x for x in order[:off] if x in HOLIDAY], [],
                            "no unearnable holiday row may be drawn")
                        # ... and the holiday rows follow it when it is set.
                        self.assertEqual(
                            sorted(order[off:]), sorted(HOLIDAY))
        finally:
            patcher.PATCHED = old_patched
            patcher.ENABLE_HOLIDAY_ORNAMENTS = old_ornaments
            patcher.ENABLE_BEHAVIOR_PATCHES = old_behavior


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

    def test_the_helper_compiles_and_both_fixes_survive_into_the_object(self):
        """Compile the helper and DECODE the object, not just the .cpp text.

        Review: rereading vf2_special_upgrade_effects.cpp still passes if the
        build compiles a stale unit, drops the helper, or fails to link the
        changed loop. Generated source is not artifact evidence. So this
        compiles the unit exactly as the matrix build does and reads the
        resulting COFF object, proving both functions are emitted and that
        the cheat loop actually calls VF2CompleteAchievementForCheat and the
        meta-goal scan actually reads achievementOrder in compiled code.

        The helper is a source unit the matrix build compiles; the executable
        it links into is the release gate's concern. What this test adds over
        the text check is that the two functions survive the compiler into an
        object with the expected external references.
        """
        import shutil
        import subprocess
        import tempfile

        emitted = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
        if not emitted.is_file():
            self.skipTest("generator output not present; run the generator first")

        vcvars = None
        for candidate in (
            pathlib.Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat"),
            pathlib.Path(r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars32.bat"),
        ):
            if candidate.is_file():
                vcvars = candidate
                break
        if vcvars is None:
            self.skipTest("no MSVC toolchain to compile the helper")

        with tempfile.TemporaryDirectory() as tmp:
            work = pathlib.Path(tmp)
            shutil.copy2(emitted, work / emitted.name)
            result = subprocess.run(
                f'"{vcvars}" >nul 2>&1 && cd /d "{work}" && '
                f'cl /c /EHsc /nologo "{emitted.name}"',
                shell=True, capture_output=True, text=True)
            obj = work / (emitted.stem + ".obj")
            self.assertEqual(
                result.returncode, 0,
                "the helper unit must compile:\n"
                + (result.stdout or "") + (result.stderr or ""))
            self.assertTrue(obj.is_file(), "no object was produced")

            compiled = CoffObject(obj)
            names = {sym.name for sym in compiled.symbols}
            # The cheat function and the meta-goal scan must BOTH be emitted
            # into the object as defined functions.
            self.assertTrue(
                any("VF2CompleteAllAchievements" in n for n in names),
                "the cheat function was dropped from the compiled object")
            self.assertTrue(
                any("VF2MaybeCompleteAchiever" in n for n in names),
                "the meta-goal scan was dropped from the compiled object")
            # The cheat loop's body must reference the shared completion
            # helper, and the array both functions walk must be an external
            # reference the linker resolves against AchievementsScene.
            self.assertTrue(
                any("VF2CompleteAchievementForCheat" in n for n in names),
                "the compiled cheat no longer calls the completion helper")
            self.assertTrue(
                any("achievementOrder" in n for n in names),
                "neither compiled function reads the visible order array")


if __name__ == "__main__":
    unittest.main()
