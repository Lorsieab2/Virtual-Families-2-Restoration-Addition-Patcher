#!/usr/bin/env python3
"""The Bathroom 2 legacy byte is cleared even when the remodel is disabled.

The byte at InventoryManager+itemId+0x2A3 is what breaks a player's shower,
toilet and sink. A save written by a build that had the remodel enabled still
carries it, so a build with the remodel switched OFF has to clean it up -- that
is precisely the case the cleanup exists for.

Every path that normally reaches the normalizer is gated on
kVF2EnableAIBathroom2: VF2DrawAIBathroom2 returns before normalizing, and the
Bathroom 2 arm of the curtain resolver is only taken when the feature is on. So
without an ungated call the cleanup never ran in the build that needed it.
"""
import re
import unittest

import patch_mobile_furniture_pack as patcher


def _source():
    return (patcher.ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
        encoding="utf-8"
    )


def _function_body(name, src):
    start = src.index(name)
    brace = src.index("{{", start)
    depth = 0
    i = brace
    while i < len(src) - 1:
        if src[i:i + 2] == "{{":
            depth += 1
            i += 2
            continue
        if src[i:i + 2] == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return src[brace:i]
            continue
        i += 1
    raise AssertionError(f"unbalanced body for {name}")


class TestLegacyCleanupRunsWhenDisabled(unittest.TestCase):
    def test_the_resolver_normalizes_when_the_remodel_is_off(self):
        body = _function_body("VF2ResolveRenovationCurtainImage(int image)", _source())
        self.assertIn("if (!kVF2EnableAIBathroom2)", body)
        self.assertIn("VF2NormalizeAIBathroom2ActivesAndSave();", body)

    def test_that_call_precedes_the_gated_arms(self):
        body = _function_body("VF2ResolveRenovationCurtainImage(int image)", _source())
        cleanup = body.index("if (!kVF2EnableAIBathroom2)")
        gated = body.index("kVF2StockBathroom1ClosedCurtainImage")
        self.assertLess(
            cleanup, gated,
            "the ungated cleanup must run before the feature-gated branches",
        )

    def test_the_draw_path_stays_gated(self):
        # VF2DrawAIBathroom2 must keep its early return; it is not the fix.
        body = _function_body(
            "static void VF2DrawAIBathroom2(", _source()
        )
        self.assertIn("!kVF2EnableAIBathroom2", body)

    def test_clearing_is_unconditional_but_migration_is_not(self):
        body = _function_body("VF2NormalizeAIBathroom2Actives()", _source())
        clear = body.index("*legacy = 0;")
        migrate = body.index("VF2PersistentAIBathroom2Mask()")
        self.assertLess(
            clear, migrate,
            "the byte is cleared first, unconditionally",
        )
        self.assertIn(
            "if (VF2IsAIBathroom2Style(itemId))", body,
            "carrying the flag into the active mask stays gated on the feature",
        )

    def test_the_legacy_accessor_is_range_only(self):
        body = _function_body("VF2AIBathroom2LegacyActiveByte(int itemId)", _source())
        self.assertIn("VF2IsAIBathroom2ItemId", body)
        self.assertNotIn(
            "VF2IsAIBathroom2Style", body,
            "the style test folds in the feature gate, which returned null in a "
            "disabled build and left the byte uncleared",
        )


if __name__ == "__main__":
    unittest.main()
