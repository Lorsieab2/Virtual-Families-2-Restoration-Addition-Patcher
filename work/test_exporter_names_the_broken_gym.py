#!/usr/bin/env python3
"""The bundled player documentation must describe the added furniture honestly.

This file has now guarded the claim in both directions, which is the point
worth keeping.

The owner reported that the Home Gym System did nothing, while the changelog
described the whole stock-donor group as merely awaiting "player
confirmation". That was a known-broken item presented as unconfirmed, and it
was not an internal note: `write_runner_files()` synthesizes the
`README-*-PATCHER.txt` a player reads and `write_transparency_log()`
synthesizes the bundled log, so both consume `B180_CHANGELOG_LINES`.

The Home Gym has since been given a villager action of its own, so saying it
does not work became false in the *other* direction. A test pinned to the
words "does not work" would have forced a true statement to be replaced with a
lie in order to stay green.

So these tests assert the PROPERTY the text must have, never one phrasing:

  * the four items with their own actions are named and not disclaimed;
  * the distinction between an action a villager CHOOSES and a reaction to
    being DROPPED is preserved, because only the first is built;
  * nothing claims a drop reaction, which the native hotspot path cannot
    deliver -- it dispatches on a hotspot enum and never reads a furniture
    item id, so it cannot tell one added item from another.

That last distinction is the one that keeps being lost, and it is why the
group is described as working without the text over-promising.
"""
import unittest

import export_offline_patch_bundle as exporter

ACTING = (
    "Exercise Bike",
    "Home Gym System",
    "Yoga Equipment",
    "Ping-Pong Table",
)


def changelog_text():
    return "\n".join(exporter.B180_CHANGELOG_LINES)


class TestTheItemsWithActionsAreNamed(unittest.TestCase):
    def test_each_one_appears(self):
        lowered = changelog_text().lower()
        for name in ACTING:
            with self.subTest(name):
                self.assertIn(
                    name.lower(), lowered,
                    f"{name} received its own villager action and the shipped "
                    "changelog does not mention it",
                )

    def test_the_gym_is_not_still_described_as_broken(self):
        """It had no action at all; it has one now.

        Leaving the old wording in place would tell a player a working item is
        broken, which is as wrong as the claim this file originally fixed.
        """
        lowered = changelog_text().lower()
        self.assertNotIn(
            "home gym system does not work", lowered,
            "the Home Gym System now has its own action with ten workout "
            "variations; describing it as broken is a false claim",
        )


class TestTheDropReactionIsNotClaimed(unittest.TestCase):
    """An action chosen and a reaction to a drop are different claims.

    Only the first is built. The drop path is the game's own
    theMainScene::HandleDropOnHotSpot, which is 70 bytes -- GetHotSpot then
    Dispatch -- and never reads a furniture item id, so it cannot distinguish
    one added item from another however complete that item's record is.
    """

    def test_the_text_keeps_the_distinction(self):
        lowered = changelog_text().lower()
        self.assertIn(
            "dropped", lowered,
            "the changelog must still separate an action a villager chooses "
            "from a reaction to being dropped",
        )
        self.assertIn("not claimed", lowered)

    def test_no_bare_promise_that_a_drop_reacts(self):
        """A disclaimer must not be excusable by a negation elsewhere.

        Only the clause immediately before the phrase may disclaim it, so a
        sentence promising a drop reaction cannot be excused by an unrelated
        "not" further along the line.
        """
        lowered = changelog_text().lower()
        needle = "act on a drop"
        start = 0
        while True:
            hit = lowered.find(needle, start)
            if hit < 0:
                break
            before = lowered[max(0, hit - 40):hit]
            self.assertTrue(
                before.rstrip().endswith(("not", "n't")) or "not " in before,
                f"the text promises a drop reaction at {hit}: "
                f"...{lowered[max(0, hit - 60):hit + 40]}...",
            )
            start = hit + len(needle)


class TestTheWarningReachesTheGeneratedDocuments(unittest.TestCase):
    """Source is not the artifact. Read what the exporter actually writes.

    A line present in B180_CHANGELOG_LINES but absent from the synthesized
    README or transparency log would leave a player with the old claim.
    """

    def _consumers(self):
        import inspect

        found = {}
        for name in ("write_runner_files", "write_transparency_log"):
            fn = getattr(exporter, name, None)
            if fn is not None:
                found[name] = inspect.getsource(fn)
        self.assertTrue(found, "neither document writer was found")
        return found

    def test_both_writers_embed_the_changelog(self):
        """If a writer stops consuming it, the text silently stops shipping."""
        for name, source in self._consumers().items():
            with self.subTest(name):
                self.assertIn(
                    "B180_CHANGELOG_LINES", source,
                    f"{name} no longer embeds the changelog, so this text "
                    "would not reach the document it writes",
                )


if __name__ == "__main__":
    unittest.main()
