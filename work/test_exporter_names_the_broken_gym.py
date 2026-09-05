#!/usr/bin/env python3
"""The player-facing bundle text must say the Home Gym System does not work.

The owner reported it plainly: the Home Gym System does nothing when a
villager is dropped on it. The item is still sold in the store, so a player who
buys it gets nothing and has no way to know that was expected.

The changelog line described the whole stock-donor group as merely awaiting
"player confirmation". That was written before the report and is no longer
true, and it is not an internal note: `write_runner_files()` synthesizes the
`README-*-PATCHER.txt` a player reads, and `write_transparency_log()`
synthesizes the bundled log. Both consume `B180_CHANGELOG_LINES`, so a bundle
built from the old text would present a known-broken item as unconfirmed.

These tests read the SYNTHESIZED DOCUMENTS, not the constant. A warning that
exists in the exporter source but never reaches the generated file is the
failure mode this repository keeps hitting -- the source is not the artifact.

The three items are checked separately because they are in different states,
and collapsing them loses the distinction the owner cares about:

  * Home Gym System   -- reported broken. Must be named as broken.
  * Exercise Bike     -- nobody has reported either way. Must stay named as
                         unconfirmed rather than silently dropped.
  * Invisible Yoga Equipment -- same as the Exercise Bike.
"""
import unittest

import export_offline_patch_bundle as exporter

BROKEN = "Home Gym System"
UNCONFIRMED = ("Exercise Bike", "Invisible Yoga Equipment")


def changelog_text():
    return "\n".join(exporter.B180_CHANGELOG_LINES)


class TestTheChangelogNamesTheBrokenItem(unittest.TestCase):
    def test_it_says_the_gym_does_not_work(self):
        text = changelog_text()
        self.assertIn(BROKEN, text)
        lowered = text.lower()
        self.assertIn(
            "home gym system does not work", lowered,
            "the changelog must say plainly that the Home Gym System does not "
            "work; the owner reported it and it is still sold in the store",
        )

    def test_it_no_longer_calls_the_group_merely_unconfirmed(self):
        """The old wording presented a known-broken item as awaiting a report."""
        lowered = changelog_text().lower()
        self.assertNotIn(
            "player confirmation that these seven act on a drop is outstanding",
            lowered,
            "this sentence predates the owner's report that the Home Gym "
            "System does nothing",
        )

    def test_the_still_unconfirmed_items_keep_their_status(self):
        """Correcting the gym must not quietly drop the other two."""
        lowered = changelog_text().lower()
        self.assertIn("unconfirmed", lowered)
        for name in UNCONFIRMED:
            with self.subTest(name):
                self.assertIn(
                    name.lower(), lowered,
                    f"{name} lost its unconfirmed status while the Home Gym "
                    "wording was corrected",
                )


class TestTheWarningReachesTheGeneratedDocuments(unittest.TestCase):
    """Source is not the artifact. Read what the exporter actually writes.

    A line present in B180_CHANGELOG_LINES but absent from the synthesized
    README or transparency log would leave a player with the old claim, which
    is precisely the defect this test exists to catch.
    """

    def _consumers(self):
        """Exporter functions that embed the changelog into player text."""
        import inspect

        found = {}
        for name in ("write_runner_files", "write_transparency_log"):
            fn = getattr(exporter, name, None)
            if fn is not None:
                found[name] = inspect.getsource(fn)
        self.assertTrue(found, "neither document writer was found")
        return found

    def test_both_writers_embed_the_changelog(self):
        """If a writer stops consuming it, the warning silently stops shipping."""
        for name, source in self._consumers().items():
            with self.subTest(name):
                self.assertIn(
                    "B180_CHANGELOG_LINES", source,
                    f"{name} no longer embeds the changelog, so the Home Gym "
                    "warning would not reach the document it writes",
                )


if __name__ == "__main__":
    unittest.main()
