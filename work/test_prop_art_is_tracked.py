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
import re
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



# PHRASES THAT MEAN UNFINISHED, not bare topic words. Each entry has to be
# unambiguous on its own, because a bare topic word is satisfied by a
# sentence that says the opposite: "qa"/"build" by "Confirmed in a build /
# QA complete", "rendering" by "rendering complete", "remains" by "no work
# remains".
_PENDING_PHRASES = (
    "not yet", "not confirmed", "pending", "unconfirmed", "outstanding",
    "yet to be", "has not been", "have not been", "nobody has",
)

# Even an unambiguous phrase is reversed by a negator beside it, and a
# literal blocklist cannot enumerate those forms:
#
#   "Confirmed; nothing pending"            contains "pending"
#   "Done -- nothing unconfirmed remains"   contains "unconfirmed"
#   "No longer awaiting confirmation"       contains "awaiting"
#
# So a phrase is denied only by a negator that IMMEDIATELY PRECEDES it --
# "nothing pending", "no longer awaiting" -- rather than by one occurring
# anywhere in the clause. Scoping it that way matters in both directions:
#
#   "not yet" / "not confirmed"  are not denied by their own leading "not"
#   "Confirmation is pending because it is not complete"  stays PENDING,
#       because the "not" belongs to "not complete", which reinforces it
#
# Negation is also judged per clause, so a row reporting a finished substep
# AND an outstanding one -- "Rendering no longer pending; confirmation still
# outstanding" -- still passes on the clause that is genuinely pending.
_NEGATOR = re.compile(
    r"\b(no|not|nothing|none|never)\b\W*(?:longer\W+)?\w*\W*$"
)
_CLAUSE_SPLIT = re.compile(r"[.;,]| but | and | because ")


def _reads_as_pending(text):
    """True when some clause says work is outstanding without denying it."""
    for clause in _CLAUSE_SPLIT.split(text):
        if not clause.strip():
            continue
        for phrase in _PENDING_PHRASES:
            at = clause.find(phrase)
            if at < 0:
                continue
            if _NEGATOR.search(clause[:at]):
                continue
            return True
    return False


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
        """The row must name the outstanding step, whatever it currently is.

        This required the word "rendering" while rendering was the thing
        still to do. Four defects were found and fixed, so what remains is
        no longer the drawing itself but confirming it in a built binary and
        in play. The requirement is the same in substance: the row must not
        read as finished while something is still outstanding.
        """
        text = (self._row()[1] + " " + self._row()[2]).lower()
        # PHRASES THAT MEAN UNFINISHED, not bare topic words. Each entry has
        # to be unambiguous on its own, because the check is a substring
        # match and a bare topic word is satisfied by a sentence that says
        # the opposite. "qa" and "build" are satisfied by "Confirmed in a
        # build / QA complete"; "rendering" by "rendering complete"; and
        # "remains" by "no work remains" -- every one of which presents the
        # feature as done, the exact claim this test exists to prevent.
        self.assertTrue(
            _reads_as_pending(text),
            "the row does not say what is still outstanding, so a reader "
            "cannot tell whether the props are known to work",
        )
        # And it must not ALSO read as finished. A row can satisfy the phrase
        # above and still open by calling the work complete.
        for claim in ("qa complete", "rendering complete", "no work remains"):
            self.assertNotIn(
                claim, text,
                f"the row claims {claim!r} while confirmation is outstanding",
            )


if __name__ == "__main__":
    unittest.main()
