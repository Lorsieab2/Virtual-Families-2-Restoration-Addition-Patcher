#!/usr/bin/env python3
"""The supplied prop art is tracked, and pinned to what was supplied.

The owner provided meal and drinks sprites for the Picnic and Patio Tables --
the artwork half of a request that has been blocked since B156. Art arriving
by hand is exactly the kind of input that goes missing or gets silently
resized, so it is checked in and hash-pinned here rather than left in a
Downloads folder.

These are world props, so they follow the engine's own convention: an
orientation PAIR per prop, RGBA, at the scale of existing placed props such as
PetBowlsFull_SE (62x35). The drinks prop has a single sprite because the patio
drinks stand reads the same from either side.

This does NOT mean the props render yet. CEnvironment::SetProp accepts ids
0x00-0x54 and the two props are 0x55 and 0x56, so the ids never reach the
engine at all -- VF2PatioSetPropAndTrack intercepts them and tracks the state
externally. Drawing is still to be built. The art being present and correct is
a precondition for that work, not evidence it is done.
"""
import hashlib
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = (
    ROOT / "patcher_assets" / "optional_patches" / "mobile_furniture_behaviors"
    / "prop_art"
)

# name -> (width, height, sha256)
SUPPLIED = {
    "mealSE.png": (105, 71, "807906bc2f3c9f5f"),
    "mealSW.png": (115, 67, "4e6326afc3515b61"),
    "patioDrinks.png": (44, 39, "2f932475499c24d6"),
}


def _png(path):
    data = path.read_bytes()
    width, height = struct.unpack_from(">II", data, 16)
    return width, height, data[25], hashlib.sha256(data).hexdigest()[:16]


class TestSuppliedPropArt(unittest.TestCase):
    def test_every_supplied_sprite_is_checked_in(self):
        for name in SUPPLIED:
            with self.subTest(name):
                self.assertTrue(
                    (ART / name).is_file(),
                    f"{name} is missing; the owner supplied it by hand and it "
                    "cannot be regenerated",
                )

    def test_the_sprites_are_the_ones_that_were_supplied(self):
        for name, (width, height, digest) in SUPPLIED.items():
            with self.subTest(name):
                got_w, got_h, colour_type, got_sha = _png(ART / name)
                self.assertEqual((got_w, got_h), (width, height),
                                 f"{name} has been resized")
                self.assertEqual(got_sha, digest, f"{name} has been re-encoded")
                # 6 = RGBA. A prop drawn over the world needs its alpha.
                self.assertEqual(colour_type, 6, f"{name} lost its alpha channel")

    def test_the_meal_prop_keeps_both_orientations(self):
        """A world prop without its pair renders wrong from one side."""
        for suffix in ("SE", "SW"):
            with self.subTest(suffix):
                self.assertIn(f"meal{suffix}.png", SUPPLIED)


class TestTheLedgerStatusMatchesReality(unittest.TestCase):
    """A release-gate row must not say "blocked" once nothing blocks it.

    This ledger is read as a completeness gate, so a stale status does real
    harm in one direction: it defers work that is actually ready. The row said
    "Blocked by engine bound" and closed by awaiting an owner decision, both
    of which stopped being true when the art arrived and the draw route was
    identified.

    The status is tied to the art here rather than left to prose, so the two
    cannot disagree: while the sprites are checked in, the row may not claim
    to be blocked or waiting on a decision.
    """

    LEDGER = ROOT / "docs" / "REQUEST_LEDGER.md"

    def _row(self):
        for line in self.LEDGER.read_text(encoding="utf-8").splitlines():
            if line.startswith("|") and "Picnic and patio table props" in line:
                return [cell.strip() for cell in line.strip("|").split("|")]
        self.fail("the picnic/patio props row is gone from the ledger")

    def test_the_status_is_not_blocked_while_the_art_is_present(self):
        if not all((ART / name).is_file() for name in SUPPLIED):
            self.skipTest("the supplied art is not checked in")
        status = self._row()[1]
        self.assertNotIn(
            "Blocked", status,
            "the art is checked in and the draw route identified; a 'Blocked' "
            "status defers work that is ready",
        )

    def test_the_row_no_longer_awaits_a_decision(self):
        if not all((ART / name).is_file() for name in SUPPLIED):
            self.skipTest("the supplied art is not checked in")
        evidence = self._row()[2]
        self.assertNotIn(
            "awaiting a decision", evidence,
            "the owner supplied the art, which was the decision being awaited",
        )

    def test_the_row_says_what_actually_remains(self):
        """The row must name the outstanding work, whatever it currently is.

        This asked for the literal word "rendering", which was right while the
        draw was unbuilt and became wrong the moment it shipped -- the row
        then had to keep a false word to stay green. Pin the PROPERTY: the row
        states what is left, and does not claim the props are unshipped now
        that the draw is installed and the sprites carry install records.
        """
        status, evidence = self._row()[1], self._row()[2]
        combined = (status + " " + evidence).lower()
        self.assertTrue(
            any(word in combined for word in ("pending", "remains", "outstanding")),
            "the row does not say what is still outstanding",
        )
        for stale in ("they are not shipped", "rendering pending"):
            with self.subTest(stale):
                self.assertNotIn(
                    stale, combined,
                    f"the row still says {stale!r}, but the draw is installed "
                    "and all three sprites carry install records",
                )


if __name__ == "__main__":
    unittest.main()
