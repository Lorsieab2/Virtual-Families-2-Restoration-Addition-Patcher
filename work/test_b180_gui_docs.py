#!/usr/bin/env python3
"""The GUI documentation has to keep describing the GUI that ships.

The README and the Transparency Log both describe the wait window and the
settings count. Both are the kind of claim that goes stale silently: a setting
gets added and the count in the prose is still right-looking, or the grab fix
gets reverted and the log still says it was made. Each check here ties a
documented claim to the thing that would falsify it.
"""
import ast
import re
import unittest
from pathlib import Path

import export_offline_patch_bundle as exporter

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
TRANSPARENCY = (ROOT / "docs" / "Transparency Log.txt").read_text(encoding="utf-8")
GUI = (ROOT / "work" / "offline_vf2_patcher_gui.py").read_text(encoding="utf-8")
LEDGER = (ROOT / "docs" / "REQUEST_LEDGER.md").read_text(encoding="utf-8")


class TestTheSettingsCountIsTheRealOne(unittest.TestCase):
    """The README's settings arithmetic has to be checkable, not asserted.

    Only the DEFINED count can be verified from the exporter. The offered count
    depends on which source assets existed at export time, so it is checked
    against a real bundle in test_readme_counts_against_a_bundle.py. This suite
    owns the half that needs no build output, plus the internal consistency of
    the sum itself.

    Two wrong versions preceded this one, and both looked right:

      * pinned to len(SETTINGS), which contradicted the sentence it sat in --
        that sentence says the GUI reads its checkboxes from the shipped
        manifest -- and shipped a count one too high;
      * a hardcoded set of withheld ids, which Codex rejected because the
        exporter filters SOURCE_BACKED_OPTIONAL settings by availability. A
        fixed list goes stale the moment a source asset appears or disappears,
        and would then reject a correctly updated README.
    """

    def _window(self):
        """The passage carrying the arithmetic, so stray digits elsewhere in
        the README cannot satisfy these patterns by accident."""
        return README.split("bundle offers")[1][:700]

    def test_the_readme_states_the_defined_count(self):
        match = re.search(r"defines, which is\s*(\d+)", self._window())
        self.assertIsNotNone(
            match, "the README no longer states how many settings are defined"
        )
        self.assertEqual(int(match.group(1)), len(exporter.SETTINGS))

    def test_the_arithmetic_in_the_explanation_adds_up(self):
        """36 - 2 is 34, not 35.

        The first explanation claimed the withheld entries were the whole
        difference, which cannot be true while the offered count is 35: a
        reader doing the subtraction lands on a different number from the one
        advertised two lines above. Codex caught it. Naming the generated
        setting is what makes the sentence self-consistent, so the sum is
        checked here rather than trusted.
        """
        window = self._window()
        offered = int(re.search(r"(\d+) settings", window).group(1))
        defined = int(re.search(r"defines, which is\s*(\d+)", window).group(1))
        unavailable = int(re.search(r"less (\d+) unavailable", window).group(1))
        generated = int(re.search(r"plus (\d+) generated", window).group(1))
        self.assertEqual(
            defined - unavailable + generated,
            offered,
            f"the README's own numbers do not reconcile: {defined} - "
            f"{unavailable} + {generated} != {offered}",
        )

    def test_the_generated_setting_is_named(self):
        # Without naming it the sum is unverifiable by a reader, which is how
        # the inconsistent version survived review in the first place.
        self.assertIn("core_assets", README)

    def test_the_withheld_settings_are_availability_filtered_not_arbitrary(self):
        """The README says a bundle drops settings whose SOURCE was missing.

        That is only true of source-backed optional settings. If either named
        setting stops being one, the stated mechanism becomes wrong even though
        the numbers still add up -- so the claim is pinned to the set the
        exporter actually filters against.
        """
        for setting_id in ("same_sex_marriage", "transparent_store_bar"):
            with self.subTest(setting_id):
                self.assertIn(
                    setting_id,
                    exporter.SOURCE_BACKED_OPTIONAL_SETTINGS,
                    "the README explains this setting's absence by source "
                    "availability, which only applies to source-backed settings",
                )


class TestTheReadmeDoesNotOverclaimRouting(unittest.TestCase):
    """The routed/unrouted split has to survive contact with the prose.

    The first draft of the visible-furniture entry said B180 gave all four
    items a route. It had not: only SpaLoungerStd went through this patcher's
    dispatcher, and the other three relied on the game's native hotspot path
    and were unconfirmed. That overclaim is what this class was written to
    prevent.

    The situation has since changed, and the class changed with it. The
    Exercise Bike, Home Gym System, Ping-Pong Table and Yoga Equipment now each
    have a villager action of their own, registered under their own behaviour
    id -- so naming them as unconfirmed would now be the inaccurate claim.

    What is pinned is therefore the property rather than a phrasing: the entry
    must name all four items, and must not assert that a villager DROPPED on
    one of them acts, because that route is still the native hotspot path and
    is still unconfirmed. An action a villager chooses on their own and a
    reaction to being dropped are different claims, and only the first is
    built.
    """

    VISIBLE_ITEMS = ("Exercise Bike", "Home Gym System", "Ping-Pong Table")

    # Phrasings that would promise a drop reaction nobody has confirmed.
    # Checked case-insensitively, and only when NOT preceded by a negation --
    # "does not claim they act on a drop" contains "act on a drop" and is the
    # opposite of the claim being guarded against. A plain substring test
    # cannot tell an assertion from its denial.
    DROP_CLAIMS = (
        "act on a drop",
        "acts on a drop",
        "responds when dropped",
        "respond when dropped",
        "works when a villager is dropped",
    )

    # A phrase is a disclaimer only when the negation sits in the SAME clause,
    # immediately before it. A wider window is worthless here: the entry
    # legitimately says elsewhere that the hotspot path "cannot tell one added
    # item from another", and a sixty-character look-back picked that up and
    # excused a genuine overclaim. Validated against known-bad, which is how
    # that was caught.
    DISCLAIMERS = (
        "does not claim they ",
        "do not claim they ",
        "not claimed that they ",
        "no claim that they ",
        "unconfirmed whether they ",
    )

    def test_the_entry_names_every_added_visible_item(self):
        entry = next(
            line for line in README.splitlines()
            if line.startswith("- **Four new visible furniture items**")
        )
        for name in self.VISIBLE_ITEMS:
            with self.subTest(name):
                self.assertIn(name, entry)

    def test_the_entry_does_not_promise_an_unconfirmed_drop_reaction(self):
        """The drop route is still the native hotspot path, still unconfirmed.

        The added items have their own autonomous actions now, which is a
        different claim from "drop a villager on one and something happens".
        """
        entry = next(
            line for line in README.splitlines()
            if line.startswith("- **Four new visible furniture items**")
        ).lower()
        for claim in self.DROP_CLAIMS:
            with self.subTest(claim):
                start = 0
                while True:
                    at = entry.find(claim, start)
                    if at < 0:
                        break
                    # The disclaimer must END exactly where the phrase begins,
                    # so only the immediately-preceding clause can excuse it.
                    excused = any(
                        entry[:at].endswith(d) for d in self.DISCLAIMERS
                    )
                    self.assertTrue(
                        excused,
                        "the entry promises a drop reaction that only the "
                        "native hotspot path could provide and no player has "
                        f"confirmed: ...{entry[max(0, at - 70):at + 40]}...",
                    )
                    start = at + 1

    def test_the_entry_points_at_where_the_actions_are_described(self):
        """A reader must be able to find what these items actually do."""
        entry = next(
            line for line in README.splitlines()
            if line.startswith("- **Four new visible furniture items**")
        )
        self.assertIn("Actions for the added furniture", entry)
        self.assertIn(
            "**Actions for the added furniture**", README,
            "the section the entry points at must exist",
        )

    def test_the_routed_visible_item_is_still_the_only_one(self):
        # Reads the same source of truth the sibling docs suite uses, so the
        # prose and the route table cannot drift apart independently.
        docs = (ROOT / "work" / "test_b180_docs.py").read_text(encoding="utf-8")
        routed = re.search(r"ROUTED = \{(.*?)\}", docs, re.S).group(1)
        self.assertIn("SpaLoungerStd", routed)
        for absent in ("ExerciseBikeStd", "HomeGymSystemStd", "PingPongTableStd"):
            with self.subTest(absent):
                self.assertNotIn(absent, routed)


class TestTheWaitWindowClaimsHold(unittest.TestCase):
    @staticmethod
    def _code_of(name):
        """A function's statements, with its docstring dropped.

        The docstrings here explain why wait_visibility() is the wrong repair,
        so scanning raw source for that name would match the warning against
        it as readily as a use of it.
        """
        for node in ast.walk(ast.parse(GUI)):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                body = node.body
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    body = body[1:]
                return chr(10).join(
                    ast.get_source_segment(GUI, statement) or "" for statement in body
                )
        return None

    def test_the_log_describes_a_grab_the_code_actually_takes(self):
        self.assertIn('B180 patcher GUI "Please wait" window', TRANSPARENCY)
        code = self._code_of("_take_grab")
        self.assertIsNotNone(code, "the documented bounded grab is gone")
        self.assertIn("raise", code, "an exhausted deadline must surface, not pass")
        self.assertNotIn(
            "wait_visibility",
            code,
            "the log records that wait_visibility is deliberately not used",
        )

    def test_the_documented_centring_behaviour_is_the_implemented_one(self):
        # The log claims only the screen-centred fallback clamps. Pin that, so
        # reintroducing the clamp on the parent-relative branch fails here.
        body = re.search(
            r"def _center\(.*?(?=\n    def )", GUI, re.S
        )
        self.assertIsNotNone(body, "WaitWindow._center is gone")
        parent_branch, _, fallback = body.group(0).partition("screen")
        self.assertNotIn(
            "max(0", parent_branch,
            "the parent-relative branch must not clamp; it throws the window "
            "onto the primary monitor on a multi-monitor desktop",
        )


class TestEveryB180RequestHasALedgerRow(unittest.TestCase):
    """The ledger's own closing rule is that no request is silently omitted.

    A shipped change with no row is exactly the omission that rule exists to
    prevent, and it is invisible: nothing fails, the feature works, and the
    only trace is that a later audit cannot find where it was asked for. Both
    of these were shipped in B180 with no row until this was written.
    """

    def test_the_wait_window_and_the_fmap_work_are_recorded(self):
        for phrase in ('Please wait', 'fmap inheritance'):
            with self.subTest(phrase):
                self.assertIn(phrase, LEDGER, f"no ledger row covers {phrase!r}")

    def test_those_rows_name_the_evidence_not_just_the_outcome(self):
        # A row saying only "shipped" is not usable by a later audit.
        for token in ('0x01B09800', '0x1b0', 'wait_visibility'):
            with self.subTest(token):
                self.assertIn(token, LEDGER)


class TestTheDedupClaimIsEvidenced(unittest.TestCase):
    """The log claims payload dedup predates B180. That has to stay checkable.

    It matters which way round this is recorded. If the entry read as "our fix
    broke a verification", a later reader would be invited to distrust the fix
    rather than the check. The claim that the collapsing is long-standing is
    what makes the by-name check the defect, so the entry names the release and
    the files that prove it.
    """

    def test_the_entry_names_a_release_predating_b180(self):
        entry = TRANSPARENCY.split("B180 payload deduplication")[1]
        entry = entry.split(chr(10) + "B180 ")[0]
        self.assertIn("B176", entry, "the claim needs the release that evidences it")
        self.assertIn(
            "CouchAquaStd", entry,
            "name a collapsed file, so the claim can be re-checked rather than "
            "taken on trust",
        )

    def test_the_entry_states_the_check_got_stricter_not_looser(self):
        entry = TRANSPARENCY.split("B180 payload deduplication")[1]
        entry = entry.split(chr(10) + "B180 ")[0]
        self.assertIn("more sensitive", entry)
        self.assertIn("B179", entry, "a revised check must cite what it was re-validated against")


class TestTheSuiteSkipClaimHolds(unittest.TestCase):
    def test_the_log_records_why_tests_skip_and_they_still_do(self):
        self.assertIn("B180 test suite: inputs a checkout cannot have", TRANSPARENCY)
        for name in (
            "test_mobile_holiday_native_contract.py",
            "test_mobile_sound_route_toggle_contract.py",
        ):
            source = (ROOT / "work" / name).read_text(encoding="utf-8")
            with self.subTest(name):
                self.assertIn(
                    "skipTest", source,
                    "the documented skip is gone; the suite would be red again",
                )


class TestTheChecksumExampleMatchesTheRecommendedAsset(unittest.TestCase):
    """Telling a reader which file to take, then hashing a different one.

    The README recommends r2, and the checksum command a few lines below
    still named VF2-B<version>-Release.zip. A reader substituting B180 would
    have hashed an archive they were told not to download -- and got a
    mismatch against the published digest, which is the one outcome most
    likely to make someone think the file is tampered with.

    Introduced by the same change that added the recommendation, which is the
    shape worth pinning: guidance and the command implementing it drifting
    apart inside one edit.
    """

    def test_the_command_names_the_archive_the_readme_recommends(self):
        named = re.findall(r"`(VF2-B\d+(?:\.\d+)?-Release-r(\d+)\.zip)`", README)
        self.assertTrue(named, "the README no longer names a recommended archive")
        # Take the HIGHEST revision named, not the first. The README's own rule
        # is "take the highest revision", so the check has to follow the same
        # rule -- otherwise a future page that mentions an older revision
        # earlier in the prose would pin the command to the wrong file.
        name = max(named, key=lambda pair: int(pair[1]))[0]
        command = re.search(r"certutil -hashfile (\S+) SHA256", README)
        self.assertIsNotNone(command, "the checksum example is gone")
        self.assertEqual(
            command.group(1), name,
            "the checksum example hashes an archive the README tells readers "
            "not to download",
        )

    def test_the_reader_is_told_to_use_their_own_filename(self):
        # A hardcoded name goes stale at the next revision; the instruction to
        # pass what they actually downloaded does not.
        self.assertIn("exact filename you downloaded", README)


class TestTheRecurringPatternIsRecorded(unittest.TestCase):
    """Nine defects, one fault. The write-up has to survive.

    A peer session asked for this to live somewhere durable, on the grounds
    that neither of us would remember the list in a month. That is the whole
    value of it: the instances are unremarkable individually and only obvious
    together, so an entry that loses them stops being useful while still
    looking complete.
    """

    LOG = ROOT / "docs" / "Transparency Log.txt"
    HEADING = "the recurring defect: what a check READS versus what it ASSERTS"

    def _entry(self):
        text = self.LOG.read_text(encoding="utf-8")
        self.assertIn(self.HEADING, text, "the pattern write-up is gone")
        return text.split(self.HEADING, 1)[1].split(chr(10) + "B180 ", 1)[0]

    def test_the_instances_are_enumerated_not_summarised(self):
        """A summary of nine cases is not the same artefact as the nine cases.

        Summarising them back into a paragraph is the likeliest way this entry
        degrades, and it would read as tidier while carrying less.
        """
        entry = self._entry()
        for marker in ("1.", "5.", "9."):
            with self.subTest(marker):
                self.assertIn(marker, entry)

    def test_it_records_what_catches_the_fault(self):
        """The instances are the evidence; the practices are the point."""
        entry = self._entry()
        for practice in (
            "FORGE A KNOWN-BAD INPUT",
            "PIN EXACT NUMBERS",
            "ASK WHAT THE CLAIM IS ABOUT",
            "MAKE GUARDS EXPIRE",
        ):
            with self.subTest(practice):
                self.assertIn(practice, entry)

    def test_it_keeps_the_counter_case(self):
        """Without one, the entry reads as "every claim was wrong".

        The ornaments count was checked identically and was correct. Losing
        that invites someone to "fix" a right number.
        """
        self.assertIn("ornaments", self._entry())


if __name__ == "__main__":
    unittest.main()
