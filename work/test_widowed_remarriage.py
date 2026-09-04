#!/usr/bin/env python3
"""A widowed adult can finalize a new same-sex marriage.

The family-tree record keeps naming a dead spouse -- nothing clears it -- so
VF2MarriagePair's "both parent slots are populated" branch stayed true forever
after a bereavement. It resolved one id to a living villager and the other to
null, then returned false. The same-sex fallback below it never ran, and native
Accept cannot write the record for a same-sex pair, so a widowed adult who
accepted a same-sex proposal could never finalize: no announcement, never
listed as married, and dropping the pair together argued instead of starting
private romantic time.

The fix lets exactly the widowed shape fall through to the fallback. That
fallback is not a guess -- it requires the same-sex toggle, excludes recorded
children of this generation, and pairs only when exactly two qualifying adults
are resident.
"""
import re
import unittest

import patch_mobile_furniture_pack as patcher


def _source():
    return (patcher.ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
        encoding="utf-8"
    )


def _marriage_pair_body():
    src = _source()
    start = src.index("static bool VF2MarriagePair(")
    end = src.index("\n}", start)
    return src[start:end]


class TestWidowedFallsThrough(unittest.TestCase):
    def test_the_widowed_shape_is_detected(self):
        body = _marriage_pair_body()
        self.assertIn(
            "bool widowed = (first != 0) != (second != 0);", body,
            "exactly one recorded parent resolving to a living resident is "
            "what identifies a widowed household",
        )

    def test_only_the_widowed_shape_falls_through(self):
        body = _marriage_pair_body()
        self.assertIn("if (!widowed) return false;", body)

    def test_the_stale_survivor_is_cleared_before_falling_through(self):
        # The surviving spouse must not be carried into the fallback as a
        # half-filled result -- the scan decides both members or neither.
        body = _marriage_pair_body()
        widowed_at = body.index("bool widowed =")
        cleared = body[widowed_at:body.index("if (!widowed)")]
        self.assertIn("first = 0;", cleared)
        self.assertIn("second = 0;", cleared)

    def test_a_fully_resolved_pair_still_returns_immediately(self):
        # The ordinary case must be untouched: both parents alive and distinct
        # returns true before any of this runs.
        body = _marriage_pair_body()
        early = body.index("if (first && second && first != second) return true;")
        widowed = body.index("bool widowed =")
        self.assertLess(early, widowed)


class TestTheFallbackStaysGuarded(unittest.TestCase):
    """Falling through is only safe because the fallback is still strict."""

    def test_it_still_requires_the_same_sex_toggle(self):
        body = _marriage_pair_body()
        self.assertIn("if (!VF2SameSexMarriageToggleActive()) return false;", body)

    def test_it_still_excludes_recorded_children(self):
        body = _marriage_pair_body()
        self.assertIn("if (VF2IsCurrentGenerationChild(villager)) continue;", body)

    def test_it_still_requires_exactly_two_adults(self):
        # A widowed adult living alone yields one and must be refused.
        body = _marriage_pair_body()
        self.assertIn("if (count != 2) return false;", body)


class TestDisplayIsUnaffected(unittest.TestCase):
    """Details describes a marriage; it must not use the resolving helper."""

    def test_married_status_still_uses_the_recorded_pair(self):
        src = _source()
        start = src.index("VF2SameSexMarriedStatusForVillager(CVillager *viewed)")
        body = src[start:src.index("\n}", start)]
        self.assertIn("VF2RecordedMarriagePair(first, second)", body)
        self.assertNotIn(
            "VF2MarriagePair(first, second)", body,
            "the display path must keep waiting for a written record, or an "
            "abandoned proposal reads as Married again",
        )

    def test_the_recorded_helper_has_no_fallback(self):
        src = _source()
        start = src.index("static bool VF2RecordedMarriagePair(")
        body = src[start:src.index("\n}", start)]
        self.assertNotIn("VF2SameSexMarriageToggleActive", body)
        self.assertNotIn("VF2MarriageAdult", body)


if __name__ == "__main__":
    unittest.main()
