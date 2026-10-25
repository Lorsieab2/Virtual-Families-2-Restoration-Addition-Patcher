#!/usr/bin/env python3
"""The "?" guides (src/vf2_how_to_use.json): every control the window shows has one, and each stays short."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_how_to_use as guides

# Words a player does not know: the guides are written for players.
TECHNICAL = re.compile(r"\b(sha-?256|hash|offset|opcode|dll|hex|bytes?|sidecar|pid|mutex|api)\b", re.I)


class GuideContentTests(unittest.TestCase):
    def test_every_guide_is_short_and_plain(self):
        self.assertTrue(guides.keys())
        for key in guides.keys():
            with self.subTest(key=key):
                guide = guides.guide(key)
                self.assertTrue(guide.title.strip())
                self.assertTrue(guide.lines)
                self.assertLessEqual(len(guide.lines), guides.MAX_LINES)
                self.assertLessEqual(len(guide.text), guides.MAX_GUIDE_CHARS)
                for line in guide.lines:
                    self.assertLessEqual(len(line), guides.MAX_LINE_CHARS, line)
                    self.assertTrue(line.strip())

    def test_guides_avoid_technical_words(self):
        for key in guides.keys():
            with self.subTest(key=key):
                self.assertIsNone(TECHNICAL.search(guides.guide(key).text))

    def test_guides_use_families_not_villagers(self):
        for key in guides.keys():
            with self.subTest(key=key):
                self.assertNotRegex(guides.guide(key).text, r"(?i)villag")

    def test_the_new_tools_are_covered(self):
        for key in ("back_up_saves", "restore_saves", "rename_family", "how_to_use", "check_updates", "restore_backup",
                    "dry_run", "apply"):
            self.assertIn(key, guides.keys())
        self.assertIn("(before restore)", guides.guide("restore_saves").text)
        self.assertIn("(before rename)", guides.guide("rename_family").text)
        self.assertIn("19", guides.guide("rename_family").text)
        self.assertIn("game_speed", guides.keys())
        self.assertIn("(before speed change)", guides.guide("game_speed").text)
        self.assertIn("Patcher Data", guides.guide("back_up_saves").text)

    def test_unknown_key_fails_loudly(self):
        with self.assertRaises(KeyError):
            guides.guide("no_such_control")

    def test_sections_are_declared(self):
        for key in guides.keys():
            self.assertIn(guides.section(key), ("Patching", "Tools"))


if __name__ == "__main__":
    unittest.main()
