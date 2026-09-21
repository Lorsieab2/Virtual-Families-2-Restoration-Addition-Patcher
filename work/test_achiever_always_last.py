"""Achiever Extraordinaire (0x92) is the LAST row the Goals screen draws.

Owner: move the goal so it is always at the bottom of the list regardless of
patches enabled.

The physical achievementOrder keeps 0x92 BEFORE the 19 runtime-optional holiday
goals (0x6D-0x7F) so the drawn window stays contiguous when Holiday Furniture is
off (audit #363, test_achiever_extraordinaire_audit.py). That order is correct
for the completion SCAN, which is position-independent, but it draws 0x92 twenty
rows from the bottom when holiday is on.

So the DRAW walks a display copy -- achievementDisplayOrder -- that is the same
visible window with 0x92 pulled to the end, rebuilt each draw for the current
runtime holiday state. The draw loop's base pointer is detoured through
VF2AchievementDisplayBase, which rebuilds the copy before the loop reads a row.
The completion scan and the "complete all" cheat still read the real
achievementOrder, so autocomplete is untouched.

These tests pin: the display build puts 0x92 last with the window length
preserved in both runtime states; the draw base is detoured to the display
array while the scan still reads the real array; and the stock achievementOrder
is unchanged by this feature.
"""
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402
from coff_patch import CoffObject  # noqa: E402

ACHIEVER = 0x92
HOLIDAY = frozenset(range(0x6D, 0x80))
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"


def _source():
    return GEN.read_text(encoding="utf-8")


def _real_order():
    """The real achievementOrder from the emitted object (what the SCAN reads)."""
    path = patcher.PATCHED / "AchievementsScene.obj"
    if not path.is_file():
        return None
    obj = CoffObject(path)
    sym = obj.symbol("?achievementOrder@@3QBHB")
    sec = obj.section(sym.section)
    count = (sec.raw_size - sym.value) // 4
    return list(struct.unpack_from("<" + "I" * count, obj.buf, sec.raw_ptr + sym.value))


def _build_display(order, visible_count):
    """The reference for VF2AchievementBuildDisplayOrder: the window minus the
    meta-goal, then the meta-goal appended last."""
    out = [x for x in order[:visible_count] if x != ACHIEVER]
    out.append(ACHIEVER)
    return out


class TheDisplayBuildPutsTheMetaGoalLast(unittest.TestCase):
    """The reference behaviour, checked against the real order in both states."""

    def _counts(self):
        without = 0x5F + 6 + 3 + 2 + 5 + 6 + 2 + 1 + 1 + 1
        if patcher.ENABLE_HOLIDAY_ORNAMENTS:
            without += 1
        if patcher.ENABLE_BEHAVIOR_PATCHES:
            without += 29
        return without, without + len(HOLIDAY)

    def test_the_meta_goal_is_last_in_both_runtime_states(self):
        order = _real_order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        for visible in self._counts():
            with self.subTest(visible=visible):
                display = _build_display(order, visible)
                self.assertEqual(display[-1], ACHIEVER,
                                 "the meta-goal must be the final drawn row")
                self.assertEqual(display.count(ACHIEVER), 1,
                                 "the meta-goal must appear exactly once")

    def test_the_window_length_is_preserved(self):
        # The scroll offset, content height and order-end bound all key off the
        # visible count, so the display copy must keep the same length.
        order = _real_order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        for visible in self._counts():
            with self.subTest(visible=visible):
                self.assertEqual(len(_build_display(order, visible)), visible)

    def test_holiday_rows_draw_only_when_the_runtime_byte_is_set(self):
        order = _real_order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        without, with_holiday = self._counts()
        off = _build_display(order, without)
        self.assertEqual([x for x in off if x in HOLIDAY], [],
                         "no holiday row may be drawn when holiday is off")
        on = _build_display(order, with_holiday)
        self.assertEqual(sorted(x for x in on if x in HOLIDAY), sorted(HOLIDAY),
                         "every holiday row must draw when holiday is on")
        # ... and the meta-goal is still last, AFTER all the holiday rows.
        self.assertEqual(on[-1], ACHIEVER)
        self.assertGreater(on.index(ACHIEVER),
                           max(i for i, x in enumerate(on) if x in HOLIDAY))


class TheEmittedBuildFunction(unittest.TestCase):
    def _strip(self, text):
        return "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith("//")
        )

    def test_the_build_appends_the_meta_goal_after_the_others(self):
        src = self._strip(_source())
        start = src.index("void __cdecl VF2AchievementBuildDisplayOrder()")
        body = src[start:src.index("\n}\n", start)]
        # skips the meta-goal in the copy loop ...
        self.assertIn("if (achievementId == 0x92) continue;", body)
        # ... then appends it once at the end.
        self.assertIn("achievementDisplayOrder[out++] = 0x92;", body)
        # and it is bounded by the visible count and the array capacity.
        self.assertIn("VF2AchievementVisibleCountInternal()", body)
        self.assertIn("kVF2AchievementDisplayCapacity", body)

    def test_the_order_end_bound_points_into_the_display_array(self):
        src = self._strip(_source())
        start = src.index("const int *__cdecl VF2AchievementOrderEnd()")
        body = src[start:src.index("\n}\n", start)]
        self.assertIn("achievementDisplayOrder + VF2AchievementVisibleCountInternal()", body)

    def test_the_display_base_rebuilds_before_returning(self):
        src = self._strip(_source())
        start = src.index("const int *__cdecl VF2AchievementDisplayBase(")
        body = src[start:src.index("\n}\n", start)]
        self.assertLess(body.index("VF2AchievementBuildDisplayOrder()"),
                        body.index("return achievementDisplayOrder"))


class TheScanIsUnchanged(unittest.TestCase):
    """Autocomplete must keep reading the REAL order, not the display copy."""

    def _strip(self, text):
        return "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith("//")
        )

    def test_the_meta_goal_scan_reads_the_real_order(self):
        src = self._strip(_source())
        start = src.index('void __fastcall VF2MaybeCompleteAchiever(')
        body = src[start:src.index("\n}\n", start)]
        self.assertIn("achievementOrder[index]", body)
        self.assertNotIn("achievementDisplayOrder", body,
                         "the completion scan must read the real order, so that "
                         "autocomplete is independent of the drawn position")

    def test_the_real_order_is_unchanged_by_this_feature(self):
        # The physical achievementOrder still ends on the meta-goal then the
        # holiday block, exactly as audit #363 fixed it. This feature only adds
        # a display copy; it must not move the real rows.
        order = _real_order()
        if order is None:
            self.skipTest("generator output not present; run the generator first")
        without = 0x5F + 6 + 3 + 2 + 5 + 6 + 2 + 1 + 1 + 1
        if patcher.ENABLE_HOLIDAY_ORNAMENTS:
            without += 1
        if patcher.ENABLE_BEHAVIOR_PATCHES:
            without += 29
        self.assertEqual(order[without - 1], ACHIEVER,
                         "the real order must still place the meta-goal before "
                         "the holiday block")


class TheDrawBaseDetour(unittest.TestCase):
    """The byte patch: the loop base is detoured to the display array."""

    def _patched_draw(self):
        path = patcher.PATCHED / "AchievementsScene.obj"
        if not path.is_file():
            return None
        obj = CoffObject(path)
        sym = obj.symbol("?DrawScene@CAchievementsScene@@MAEXXZ")
        sec = obj.section(sym.section)
        return obj, sym, sec

    def test_the_base_pointer_site_is_a_near_jump_to_a_cave(self):
        got = self._patched_draw()
        if got is None:
            self.skipTest("generator output not present; run the generator first")
        obj, sym, sec = got
        raw = sec.raw_ptr + sym.value
        # The stock `lea esi,[eax*4+achievementOrder]` is replaced by a near
        # jump plus two NOPs.
        self.assertEqual(obj.buf[raw + 0xC6], 0xE9,
                         "the base-pointer lea was not detoured")
        self.assertEqual(bytes(obj.buf[raw + 0xCB:raw + 0xCD]), b"\x90\x90")

    def test_the_detour_calls_the_display_base_helper(self):
        got = self._patched_draw()
        if got is None:
            self.skipTest("generator output not present; run the generator first")
        obj, sym, sec = got
        # A relocation to _VF2AchievementDisplayBase must exist in the draw
        # section (the cave's call), and the old DIR32 to achievementOrder must
        # be gone from the loop body.
        display_idx = next(
            (s.index for s in obj.symbols if s.name == "_VF2AchievementDisplayBase"),
            None)
        self.assertIsNotNone(display_idx,
                             "_VF2AchievementDisplayBase is not referenced")
        order_idx = obj.symbol("?achievementOrder@@3QBHB").index
        display_reloc = False
        stale_order_reloc_in_body = False
        for k in range(sec.nreloc):
            vaddr, symidx, _ = struct.unpack_from(
                "<IIH", obj.buf, sec.reloc_ptr + k * 10)
            off = vaddr - sym.value
            if symidx == display_idx:
                display_reloc = True
            # The loop body is everything before the appended caves (< 0x100 in
            # the stock layout); a surviving achievementOrder reloc there would
            # mean the base still binds the real array.
            if symidx == order_idx and off < 0x100:
                stale_order_reloc_in_body = True
        self.assertTrue(display_reloc,
                        "the detour never calls _VF2AchievementDisplayBase")
        self.assertFalse(stale_order_reloc_in_body,
                         "a stale achievementOrder relocation survives in the "
                         "draw loop body")


if __name__ == "__main__":
    unittest.main()
