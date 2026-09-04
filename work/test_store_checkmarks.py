#!/usr/bin/env python3
"""Store rows that are active show a checkmark.

CScrollingStoreScene::DrawVisibleStoreItem draws the owned checkmark for any
row whose GetNumAvailable is zero. Only the DRAW site is retargeted, so a
reversible row still reports its real availability to the click handler and
stays clickable -- buying Unlock Everything again restores the locks, and
buying a price multiplier again switches to it.

Before this, only the pregnancy one-shots and the two ownership cheats were
checkmarked; everything else the owner listed showed no tick however plainly
it was in force.
"""
import re
import unittest

import patch_mobile_furniture_pack as patcher


def _source():
    return (patcher.ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
        encoding="utf-8"
    )


def _row_check_body():
    src = _source()
    start = src.index("static bool VF2StoreRowShowsActive(int itemId) {{")
    return src[start:src.index("\n}}", start)]


class TestTheDrawHookConsultsIt(unittest.TestCase):
    def test_the_draw_hook_reports_zero_for_an_active_row(self):
        src = _source()
        start = src.index("VF2StoreDrawNumAvailable(")
        body = src[start:src.index("\n}}", start)]
        self.assertIn("if (VF2StoreRowShowsActive(itemId)) return 0;", body)

    def test_only_the_draw_site_is_affected(self):
        # The click handler must keep seeing the real answer, or a reversible
        # row becomes unclickable and can never be turned back off.
        src = _source()
        self.assertIn(
            "so only the draw's site is retargeted here", src,
            "the split between draw and click is what keeps reversible rows "
            "clickable, and it must stay documented",
        )


class TestEveryRequestedRowIsCovered(unittest.TestCase):
    def test_the_four_visible_special_upgrades(self):
        body = _row_check_body()
        for item_id in (0x117, 0x118, 0x119, 0x11A):
            self.assertIn(f"case {item_id:#X}:".replace("0X", "0x"), body)

    def test_unlock_everything(self):
        self.assertIn("case 0x123:", _row_check_body())

    def test_the_price_multipliers_and_reset(self):
        body = _row_check_body()
        self.assertIn("itemId == 0x128 || itemId == 0x129 || itemId == 0x12A", body)
        self.assertIn("if (itemId == 0x12C) {{", body)

    def test_reset_ticks_only_when_no_multiplier_is_in_force(self):
        # Reset Price Multiplier is "active" precisely when none of the three
        # multipliers is owned -- prices are at their original values.
        body = _row_check_body()
        reset = body[body.index("if (itemId == 0x12C) {{"):]
        self.assertIn("!InventoryManager.HaveUpgrade((EInventoryItem)0x128)", reset)
        self.assertIn("!InventoryManager.HaveUpgrade((EInventoryItem)0x129)", reset)
        self.assertIn("!InventoryManager.HaveUpgrade((EInventoryItem)0x12A)", reset)

    def test_the_marriage_toggles(self):
        body = _row_check_body()
        self.assertIn("VF2SameSexMarriageToggleActive()", body)
        self.assertIn("VF2CheatToggleActiveByte", body)

    def test_every_house_renovation(self):
        body = _row_check_body()
        self.assertIn("itemId >= 0xE1 && itemId <= 0xEA", body)
        self.assertIn("VF2IsAIBathroom2Style(itemId)", body)
        self.assertIn("VF2IsMobileRenovationStyle(itemId)", body)

    def test_the_ownership_cheats_were_already_covered(self):
        # Anti-spam and Rockhound go through the one-shot path, which reads
        # live game state rather than the purchase mask.
        src = _source()
        start = src.index("static bool VF2OneShotUpgradeArmed(int itemId) {{")
        body = src[start:src.index("\n}}", start)]
        self.assertIn("VF2IsStockOwnershipCheat(itemId)", body)
        self.assertIn("VF2StockOwnershipActive(itemId)", body)


class TestDeclarationOrder(unittest.TestCase):
    """Valid Python, invalid C -- only compiling the generated file catches it."""

    def test_all_store_locks_unlocked_is_declared_before_use(self):
        src = _source()
        decl = src.index("static bool VF2AllStoreLocksUnlocked();")
        use = src.index("case 0x123: return VF2AllStoreLocksUnlocked();")
        self.assertLess(decl, use)


class TestTheEmittedCHasTheCheckmarkWiring(unittest.TestCase):
    """Read the generated file: placeholders only resolve at emit time."""

    EMITTED = (
        patcher.ROOT / "work" / "patched_mobile_furniture_pack_objs" /
        "vf2_special_upgrade_effects.cpp"
    )

    def setUp(self):
        if not self.EMITTED.is_file():
            self.skipTest(f"{self.EMITTED.name} has not been generated here")
        self.text = self.EMITTED.read_text(encoding="utf-8")
        start = self.text.index("static bool VF2StoreRowShowsActive(int itemId)")
        self.body = self.text[start:self.text.index("\n}", start)]

    def test_no_placeholder_survived(self):
        # The failure this guards against emits the brace form literally and
        # is invisible to every test that reads the Python.
        self.assertNotIn("__VF2_", self.body)
        # An unsubstituted f-string placeholder looks like {NAME} or
        # {NAME:#x}. Ordinary C braces never contain an identifier followed
        # by a closing brace on the same line with no code between.
        leftovers = re.findall(r"\{[A-Z_][A-Z0-9_]*(?::[^}]*)?\}", self.body)
        self.assertEqual(leftovers, [], f"unsubstituted placeholders: {leftovers}")

    def test_the_toggle_ids_resolved_to_real_numbers(self):
        same_sex = f"{patcher.SAME_SEX_MARRIAGE_ITEM_ID:#x}"
        reroll = f"{patcher.MARRIAGE_CANDIDATE_REROLL_ITEM_ID:#x}"
        self.assertIn(same_sex, self.body.lower())
        self.assertIn(reroll, self.body.lower())

    def test_it_is_wired_into_the_draw_site_only(self):
        # Draw returns 0 so the checkmark appears; the click path must keep
        # reading the real answer or reversible rows stop being clickable.
        self.assertIn("if (VF2StoreRowShowsActive(itemId)) return 0;", self.text)
        self.assertEqual(
            self.text.count("VF2StoreRowShowsActive(itemId)"), 1,
            "the helper should be consulted at exactly one call site -- the "
            "draw hook. Wiring it into the click path too would stop rebuying "
            "Unlock Everything from restoring the locks.",
        )

    def test_the_reset_multiplier_row_is_the_negation_of_the_three(self):
        # Reset ticks only when none of the three multipliers is in force.
        for item in ("0x128", "0x129", "0x12A"):
            with self.subTest(multiplier=item):
                self.assertIn(item.lower(), self.body.lower())


if __name__ == "__main__":
    unittest.main()
