#!/usr/bin/env python3
"""Every behaviour label must fit the villager's label slot.

The slot at CVillager+0x1BBA8 holds 0x27 characters: VF2SetBehaviorLabel and
VF2SetActionLabel both strncpy with a count of 0x27, and every comparison of a
label (VF2LabelBytesEqual, VF2LabelTextEqual, the spa label matcher) stops at
0x27. A longer label is silently cut when displayed.

That shipped once: "Exploring future volunteer opportunities" is 40 bytes and
was shown as "Exploring future volunteer opportunitie". Nothing caught it,
because nothing measured label length.

Two labels are truncated ON PURPOSE -- the rare coffee and burger jokes -- and
their achievement goals are keyed on the truncated text. They are listed here
explicitly; any other overlong label fails.
"""
import re
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

LABEL_SLOT = 0x27

# Label text -> the group it belongs to. Deliberately truncated; the praise
# achievement goals match the first 0x27 bytes (see
# CUSTOM_ACHIEVEMENT_PRAISE_LABEL_GOALS).
DELIBERATE_TRUNCATIONS = {
    "coffee_rare": "Making a Half-Caff Double-Shot Leviathan Latte-Espresso with Heavy Cream",
    "burger_rare": (
        "Eating a Double Triple Bossy Deluxe on a raft, four-by-four, animal "
        "style, with extra shingles, a shimmy and a squeeze and light axle "
        "grease that cries, burns and swims"),
}

SOURCE = Path(patcher.__file__).read_text(encoding="utf-8")


def _size(text):
    return len(text.encode("latin-1"))


class TestBehaviorLabelsFitTheSlot(unittest.TestCase):
    def test_every_label_group_entry_fits(self):
        overlong = []
        seen_deliberate = set()
        for group, entries in patcher.BEHAVIOR_LABEL_GROUPS:
            for _key, text in entries:
                if _size(text) <= LABEL_SLOT:
                    continue
                if DELIBERATE_TRUNCATIONS.get(group) == text:
                    seen_deliberate.add(group)
                    continue
                overlong.append("%s: %r (%d bytes)" % (group, text, _size(text)))
        self.assertEqual(
            overlong, [],
            "these labels exceed the 0x27-byte label slot and would display "
            "truncated; shorten them or list them as deliberate")
        # A stale allowlist entry would let a future overlong label with the
        # same group slip through unnoticed, so every listed truncation must
        # still exist.
        self.assertEqual(seen_deliberate, set(DELIBERATE_TRUNCATIONS))

    def test_the_deliberate_truncations_are_what_the_goals_match(self):
        goals = patcher.CUSTOM_ACHIEVEMENT_PRAISE_LABEL_GOALS
        for group, text in DELIBERATE_TRUNCATIONS.items():
            with self.subTest(group=group):
                self.assertIn(text[:LABEL_SLOT], goals)

    def test_literal_action_labels_fit(self):
        """Labels written straight from C string literals, not the string table."""
        literals = re.findall(
            r'VF2SetActionLabel\(\s*villager,\s*"((?:[^"\\]|\\.)*)"\s*\)', SOURCE)
        self.assertGreater(len(literals), 10, "the literal scan found nothing")
        for array in ("kVF2SpaReceivingLabels", "kVF2SpaGivingLabels"):
            start = SOURCE.index("static char const *const %s[] = {" % array)
            body = SOURCE[start:SOURCE.index("};", start)]
            found = re.findall(r'"((?:[^"\\]|\\.)*)"', body)
            self.assertGreater(len(found), 5, "%s scan found nothing" % array)
            literals.extend(found)
        overlong = [t for t in literals if _size(t) > LABEL_SLOT]
        self.assertEqual(overlong, [])

    def test_the_slot_size_is_still_0x27(self):
        """If the copy width ever changes, this test's limit must follow it."""
        self.assertIn("strncpy(label, text, 0x27);", SOURCE)
        self.assertIn(
            "strncpy(behaviorLabel, theStringManager::Get()->GetString("
            "(StringId)stringId), 0x27);", SOURCE)


if __name__ == "__main__":
    unittest.main()
