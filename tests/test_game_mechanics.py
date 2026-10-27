#!/usr/bin/env python3
"""Game Mechanics (src/vf2_game_mechanics.py and its window): the page's groups, labels, words and settled rules.

The rules themselves are pinned against the B200 core executable in tests/test_game_mechanics_b200_exe.py; here
the page must say what those runs showed, keep every label visible, use family wording and stay read-only.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_game_mechanics as gm  # noqa: E402


class PageTests(unittest.TestCase):
    def setUp(self):
        self.facts = gm.facts()
        self.text = gm.render(self.facts)

    def test_groups_are_the_owners_list_in_order(self):
        self.assertEqual(gm.GROUPS, (
            "Time and ageing", "Needs and upkeep", "Health and sickness", "Old age", "Pregnancy and babies",
            "Careers", "Money and interest", "Leaving home", "Dating, marriage and the next generation",
            "Random Events", "Weather", "Messes and malfunctions", "Collectibles", "The store: prices and buying",
            "Food and Medicine", "Flea Market", "Special Upgrades", "Services", "Home Renovation", "Career upgrades",
            "Furniture and Accessories", "Pets", "Clothing and Hairstyles", "Chance and timer index"))
        seen = []
        for fact in self.facts:
            if not seen or seen[-1] != fact.group:
                seen.append(fact.group)
        self.assertEqual(tuple(seen), gm.GROUPS, "each group once, in GROUPS order")

    def test_every_line_shows_its_label_after_the_bullet(self):
        for fact in self.facts:
            self.assertIn(fact.label, gm.LABELS, fact.text)
        lines = [line for line in self.text.splitlines() if line.startswith((gm.BULLET, gm.SUB_BULLET))]
        self.assertEqual(len(lines), len(self.facts))
        for line in lines:
            body = line[len(gm.SUB_BULLET):] if line.startswith(gm.SUB_BULLET) else line[len(gm.BULLET):]
            self.assertRegex(body, r"^(VERIFIED-E|VERIFIED-C|UNCONFIRMED)  \S")
        for label in gm.LABELS:
            self.assertIn(label, self.text)

    def test_family_wording(self):
        text = self.text
        for name in gm.OPTION_NAMES + gm.STORE_OPTION_NAMES:   # the patcher options' own names (Patches tab)
            text = text.replace(name, "")
        text = text.replace("Virtual Villagers Painting", "")       # a furniture item's own name
        self.assertNotRegex(text, r"(?i)villag|tribe|peep")
        self.assertIn("family member", self.text)
        self.assertNotRegex(gm.INTRO + gm.LABEL_NOTE, r"(?i)villag")

    def test_time_away_is_the_emulated_cap(self):
        self.assertIn("up to 31,000 seconds (8 hours 36 minutes 40 seconds) away is made up in full", self.text)
        self.assertIn("from 31,000 seconds up to and including 24 hours away, 31,000 seconds are made up", self.text)
        self.assertIn("more than 24 hours away, exactly 24 hours are made up: 144 age units, 7.2 years", self.text)
        self.assertNotIn("2.58", self.text)
        for fact in self.facts:
            if "made up" in fact.text and fact.group == gm.TIME and "31,000" in fact.text:
                self.assertEqual(fact.label, gm.VERIFIED_E)

    def test_a_paused_clock_stops(self):
        line = next(f for f in self.facts if f.text.startswith("Pause stops the game clock completely"))
        self.assertEqual(line.label, gm.VERIFIED_E)

    def test_the_owners_three_true_rules_are_shown_plainly(self):
        grains = next(f for f in self.facts if "count one extra food group" in f.text)
        self.assertEqual(grains.label, gm.VERIFIED_E)
        self.assertIn("Grains", grains.text)
        self.assertIn("Dairy alone as 1", grains.text)
        interest = next(f for f in self.facts if f.text.startswith("Interest: 10%"))
        self.assertIn("only 2 days are paid", interest.text)
        self.assertEqual(interest.label, gm.VERIFIED_E)
        broker = next(f for f in self.facts if f.text.startswith(gm.WITH_PATCHER + "Brokerage Account"))
        self.assertIn("Buying it again sets interest to 1%", broker.text)
        self.assertEqual(broker.label, gm.VERIFIED_E)
        malfunction = next(f for f in self.facts if f.text.startswith("House malfunctions"))
        self.assertIn("while the game is paused too", malfunction.text)
        self.assertEqual(malfunction.label, gm.VERIFIED_E)
        # The window describes the game: it never claims to fix anything.
        self.assertNotRegex(self.text, r"(?i)\b(a bug|is a bug|fix(es|ed)? (it|this|the game)|fixed by)\b")

    def test_the_intro_says_the_page_is_the_patched_game_with_the_unpatched_differences(self):
        self.assertIn("The page describes the game with the patcher applied, and gives the unpatched game's "
                      "behaviour wherever it differs.", gm.INTRO)

    def _pair(self, patched_start):
        """The "With the patcher:" line starting so, and the "Unpatched game:" line right after it."""
        index = next(i for i, f in enumerate(self.facts) if f.text.startswith(gm.WITH_PATCHER + patched_start))
        patched, unpatched = self.facts[index], self.facts[index + 1]
        self.assertTrue(unpatched.text.startswith(gm.UNPATCHED), unpatched.text)
        self.assertEqual(patched.group, unpatched.group)
        self.assertFalse(patched.sub or unpatched.sub)
        return patched, unpatched

    def test_the_flea_market_both_ways(self):
        patched, unpatched = self._pair("the Flea Market")
        self.assertIn("shows all 36 of its goods at all times; it never changes", patched.text)
        self.assertEqual(patched.label, gm.VERIFIED_E)
        self.assertIn("0x4B9A90", patched.evidence)
        self.assertIn("the Flea Market shows 5 of its 36 goods, picked at random, and changes them every 6 real "
                      "hours", unpatched.text)
        self.assertIn("more than 6 real hours after the last change", unpatched.text)
        self.assertIn("while the game is closed", unpatched.text)
        self.assertEqual(unpatched.label, gm.VERIFIED_E)
        for needle in ("1582d9e8", "0x4BA710", "0x432050", "0x5346E0", "T + 21,600", "T + 21,601", "T + 86,400"):
            self.assertIn(needle, unpatched.evidence)
        # the 6-hour rule appears only as the unpatched game's
        for fact in self.facts:
            if re.search(r"6 (real )?hours|21,600|six hours", fact.text):
                self.assertRegex(fact.text, r"(?i)unpatched", fact.text)
        index = [(f.text, f.label) for f in self.facts if f.group == gm.INDEX and "Flea Market" in f.text]
        self.assertEqual(index, [("the Flea Market, with the patcher: never changes;", gm.VERIFIED_E),
                                 ("the Flea Market, unpatched game: every 6 hours (real time);", gm.VERIFIED_E)])

    def test_the_special_upgrades_page_both_ways(self):
        patched, unpatched = self._pair("the store's Special Upgrades page")
        for name in ("Brokerage Account", "Food Club", "Health Plan", "Lucky Rock"):
            self.assertIn(name, patched.text)
            self.assertIn(name, unpatched.text)
        self.assertIn("10 items in all", patched.text)
        self.assertIn("has 6 items and sells none of", unpatched.text)
        self.assertEqual((patched.label, unpatched.label), (gm.VERIFIED_E, gm.VERIFIED_E))
        self.assertIn("0x46B6D0", patched.evidence)
        for needle in ("1582d9e8", "0x4BB0A0", "0x4BAA50", "0x556E3C"):
            self.assertIn(needle, unpatched.evidence)
        # the patcher-only purchase rule says it is the patcher's
        broker = next(f for f in self.facts if "Brokerage Account: buying it" in f.text)
        self.assertTrue(broker.text.startswith(gm.WITH_PATCHER))

    def test_the_autosave_line(self):
        # theGameState::AutoSaveGame (B200 0x4994E0, stock 0x4296A0) from theGame::GameUpdate every frame: 120 s on
        # the PC clock, no pause check, SaveCurrentGame writes the slot file a quit writes (spec 17, emulated)
        index = [(f.text, f.label) for f in self.facts if f.group == gm.INDEX and "autosave" in f.text]
        self.assertEqual(index, [("the autosave: every 2 minutes (real time), also while paused, to the same save "
                                  "file a quit writes; the same in the unpatched game;", gm.VERIFIED_E)])

    def test_every_unpatched_line_follows_its_patched_line(self):
        for index, fact in enumerate(self.facts):
            if fact.text.startswith(gm.UNPATCHED):
                self.assertTrue(self.facts[index - 1].text.startswith(gm.WITH_PATCHER), fact.text)
                self.assertTrue(fact.evidence.startswith("stock exe sha256 1582d9e8"), fact.text)

    def test_patcher_options_are_shown_both_ways(self):
        for name in gm.OPTION_NAMES:
            states = [f.text for f in self.facts if f'"{name}", off' in f.text or f'"{name}", on' in f.text]
            self.assertTrue(any(", off" in t for t in states), name)
            self.assertTrue(any(", on" in t for t in states), name)
        older = next(f for f in self.facts if f'"{gm.OPTION_PREGNANCIES}", on: with a parent 50' in f.text)
        self.assertEqual(older.label, gm.UNCONFIRMED)

    def test_old_age_matches_the_formula(self):
        line = next(f for f in self.facts if f.text.startswith("With no food groups"))
        self.assertIn("10% at 56, 50% at 60, 100% at 65", line.text)
        self.assertIn("10% at 60, 50% at 64, 100% at 69", line.text)

    def test_careers_list_every_career_once(self):
        self.assertEqual(len(gm.CAREERS), 132)
        self.assertEqual([c[0] for c in gm.CAREERS], list(range(132)))
        counts = {w: sum(1 for c in gm.CAREERS if c[1] == w) for w in (1, 2, 3)}
        self.assertEqual(counts, {1: 38, 2: 57, 3: 37})
        for _cid, _w, name, salaries in gm.CAREERS:
            self.assertEqual(len(salaries), 8)
            self.assertEqual(sum(1 for f in self.facts if f.text.startswith(name + ":")), 1, name)
        # pay per real hour is half the salary: Pastry Designer 30 -> $15
        self.assertIn("Pastry Designer: $15 per real hour as a Beginner, $50 as a Master", self.text)

    def test_unconfirmed_lines_stay_unconfirmed(self):
        # The time-skip item, the medicines, the Lotto Ticket, the Health Plan and Boarding School are now read from
        # the purchase path (tests/test_game_mechanics_store.py).
        for start in ("What that waiting time holds back", "The Mysterious Collector", "The Wrong Address"):
            fact = next(f for f in self.facts if f.text.startswith(start))
            self.assertEqual(fact.label, gm.UNCONFIRMED, start)

    def test_every_fact_keeps_its_evidence_for_the_export(self):
        for fact in self.facts:
            if not fact.sub:
                self.assertTrue(fact.evidence.strip(), fact.text)


class ClaimsExportTests(unittest.TestCase):
    def test_the_export_lists_every_line_with_its_label_and_evidence(self):
        import importlib.util
        import tempfile
        spec = importlib.util.spec_from_file_location("export_claims", ROOT / "scripts" / "export_game_mechanics_claims.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(module.main(["export", tmp]), 0)
            text = (Path(tmp) / module.FILE_NAME).read_text(encoding="utf-8")
        facts = gm.facts()
        self.assertEqual(len(re.findall(r"^\s*\[(VERIFIED-E|VERIFIED-C|UNCONFIRMED)\] ", text, re.M)), len(facts))
        self.assertIn("evidence: AllVillagersTimeflowUpkeep 0x4C4D29..0x4C4D8F", text)
        for group in gm.GROUPS:
            self.assertIn("\n" + group + "\n", text)


class WindowTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
        except ImportError:  # pragma: no cover
            self.skipTest("tkinter is not available")
        try:
            self.root = tk.Tk()
        except Exception:
            self.skipTest("no display available for Tk")
        self.root.withdraw()
        import vf2_game_mechanics_window as gmw
        self.gmw = gmw

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_the_window_shows_every_group_and_label_and_writes_nothing(self):
        refused = AssertionError("the Game Mechanics window must not write")
        with mock.patch("pathlib.Path.write_bytes", side_effect=refused), \
                mock.patch("pathlib.Path.write_text", side_effect=refused), \
                mock.patch("builtins.open", side_effect=refused):
            window = self.gmw.open_game_mechanics(self.root)
        try:
            page = window.mechanics_page
            text = page.get("1.0", "end-1c")
            self.assertEqual(text.count(gm.UNCONFIRMED), gm.render().count(gm.UNCONFIRMED))
            for group in gm.GROUPS:
                self.assertIn(group, window.mechanics_marks)
            self.assertEqual(str(page.cget("state")), "disabled")
            links = [child.cget("text") for child in window.mechanics_links.winfo_children()]
            self.assertEqual(links, list(gm.GROUPS))
            # every label is drawn in its own colour
            for label in gm.LABELS:
                self.assertTrue(page.tag_ranges(label), label)
                self.assertEqual(page.tag_cget(label, "foreground"), self.gmw.LABEL_COLOURS[label])
            window.mechanics_jump(gm.STORE)
            window.update_idletasks()
            self.assertLessEqual(window.mechanics_links.winfo_reqwidth(), self.gmw.MIN_WIDTH - 2 * self.gmw.PADDING,
                                 "every group link fits the window at its smallest")
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()
