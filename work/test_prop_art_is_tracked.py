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



# PHRASES THAT MEAN UNFINISHED, not bare topic words. A bare topic word is
# satisfied by a sentence saying the opposite: "rendering" by "rendering
# complete", "qa"/"build" by "Confirmed in a build / QA complete", "remains"
# by "no work remains". Every entry below carries the pending sense alone.
_PENDING_PHRASES = (
    "not yet", "not confirmed", "pending", "unconfirmed", "outstanding",
    "yet to be", "has not been", "have not been", "nobody has",
)

# Even an unambiguous phrase is reversed by a negator beside it, and the
# finished forms are open-ended, so a literal blocklist cannot enumerate them:
#
#   "Confirmed; nothing pending"           contains "pending"
#   "No work is currently pending"          contains "pending"
#   "No longer awaiting confirmation"       contains "awaiting"
#
# A phrase is denied by a negator earlier in the same clause with only
# ordinary noun and auxiliary words between them. The window is bounded so an
# unrelated negator cannot leak across a clause, and the phrase's own leading
# "not" is never the negator, so "not yet" and "not confirmed" still count.
# "Confirmation is pending because it is not complete" stays PENDING, because
# that "not" belongs to "not complete" and follows the phrase.
# Five intervening words, not four. "no work is known to be pending" puts
# five words between the negator and the phrase, so a four-word window read
# a finished status as still outstanding. The window exists to stop a
# negator reaching across a whole clause, and the clause separators below
# already bound that, so five stays conservative.
_NEGATOR = re.compile(
    r"\b(?:no|not|nothing|none|never)\b(?:\W+\w+){0,5}\W*$"
)
# Slash-separated substeps are a ledger convention -- "source complete / QA
# pending" -- so "/" separates clauses like any other punctuation.
# Sentence and clause separators. ":" and the dashes matter as much as ";":
# "Blockers: none - QA pending" is a legitimate pending row, and without them
# the negator in the first clause reaches across and suppresses "pending" in
# the second. Hyphen, en dash and em dash are all used in these rows.
# "--" is the ASCII dash these documents actually use -- this very comment
# uses it -- and it was missing, so "not shipped -- qa pending" stayed one
# clause and the leading negator suppressed a genuine pending claim. It has
# to come before the single-hyphen alternative, which would otherwise match
# first and leave a stray "-" heading the next clause.
# The subordinating conjunctions are here for the same reason as the
# punctuation: "not complete while final QA is pending" states outstanding
# work in its second clause, and without a boundary the leading negator
# reaches across and denies it. "although", "though", "until" and "since"
# join clauses the same way and were wrong before the window widened, so
# they are fixed here too rather than left as a narrower version of the
# same defect.
_CLAUSE_SPLIT = re.compile(
    r"[.;,/:\u2013\u2014]|\s--+\s|\s-\s"
    r"| but | and | because | while | although | though | until | since "
)


def _reads_as_pending(text):
    """True when some clause says work is outstanding without denying it."""
    for clause in _CLAUSE_SPLIT.split(text):
        if not clause.strip():
            continue
        for phrase in _PENDING_PHRASES:
            # EVERY occurrence, not just the first: a negated mention can
            # precede a genuine one -- "nothing pending in source / QA
            # pending" -- and stopping at the first hides the real claim.
            for hit in re.finditer(r"\b" + re.escape(phrase) + r"\b", clause):
                if _NEGATOR.search(clause[:hit.start()]):
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

    # Claims that the very work this row is waiting on is already finished.
    # A row may legitimately say one substep is complete while another is
    # pending -- "source complete / QA pending" is the ledger's own idiom --
    # but it must not claim the OUTSTANDING step is done. Dropping the old
    # literal "qa complete" check left "QA complete; release pending" passing
    # a test whose whole purpose is to reject a finished-sounding row.
    _CONTRADICTORY_CLAIMS = (
        "qa complete",
        "qa is complete",
        "qa done",
        "rendering complete",
        "confirmed in play",
        "verified in play",
        "no work remains",
    )

    def test_the_row_never_claims_the_outstanding_work_is_done(self):
        """A pending phrase elsewhere must not excuse a completion claim.

        _reads_as_pending answers "does some clause say work is outstanding".
        It cannot answer "does another clause contradict that", and a row
        carrying both is worse than one carrying neither -- it reads as
        finished to a person and as pending to the check.
        """
        text = (self._row()[1] + " " + self._row()[2]).lower()
        for claim in self._CONTRADICTORY_CLAIMS:
            self.assertNotIn(
                claim,
                text,
                f"the row claims {claim!r} while confirmation is still "
                "outstanding, so it reads as finished to a reader",
            )

    def test_the_row_says_what_actually_remains(self):
        """The row must name the outstanding step, whatever it currently is.

        This required the bare word "rendering" while rendering was the thing
        still to do. Four defects were found and fixed, so what remains is no
        longer the drawing itself but confirming it in a built binary and in
        play. The requirement is the same in substance -- the row must not
        read as finished while something is outstanding -- but a bare topic
        word cannot express it.
        """
        text = (self._row()[1] + " " + self._row()[2]).lower()
        self.assertTrue(
            _reads_as_pending(text),
            "the row does not say what is still outstanding, so a reader "
            "cannot tell whether the props are known to work",
        )

    def test_reads_as_pending_handles_the_wordings_these_rows_use(self):
        """Pin the two ways this helper misread real ledger prose.

        Both were found by review against wording that would plausibly be
        written here, and both failed in a way no existing row happened to
        trigger -- which is exactly why they need a test rather than a fix
        alone. They are asserted as behaviour, not as the regex text, so a
        later rewrite of the pattern still has to satisfy them.
        """
        outstanding = (
            # A negator separated from the phrase by a longer auxiliary
            # phrase must still not be read as denying it across a clause
            # boundary marked by the ASCII "--" dash these documents use.
            "not shipped -- qa pending",
            "not complete: confirmation pending",
            "blockers: none - qa pending",
            "nothing pending in source / qa pending",
            "confirmation is pending because it is not complete",
            "qa pending",
            # Subordinate clauses. Review caught the first of these as a
            # regression from widening the negator window; checking the
            # neighbours showed the other three were already wrong before
            # that, so they are pinned together rather than one at a time.
            "not complete while final qa is pending",
            "not complete although qa is pending",
            "not done until qa is pending",
            "not shipped since qa is pending",
        )
        for text in outstanding:
            with self.subTest(text=text):
                self.assertTrue(
                    _reads_as_pending(text),
                    f"{text!r} names outstanding work but was read as finished",
                )

        finished = (
            # Five words between the negator and the phrase: a four-word
            # window read this finished status as outstanding.
            "no work is known to be pending",
            "nothing pending",
            "no confirmation pending",
        )
        for text in finished:
            with self.subTest(text=text):
                self.assertFalse(
                    _reads_as_pending(text),
                    f"{text!r} denies outstanding work but was read as pending",
                )


if __name__ == "__main__":
    unittest.main()
