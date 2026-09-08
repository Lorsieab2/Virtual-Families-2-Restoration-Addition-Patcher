"""Gate-level checks that do not require packaging a release.

The gate is the only place that can require a release to cover every
combination the matrix builds: verify_offline_bundle_zip checks an archive
against its own release's contract so retained older ZIPs still verify.
"""

from __future__ import annotations

import contextlib
import io
import sys
import re
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_release_zip as gate
import verify_offline_bundle_zip as verifier


class PayloadVerificationIsWiredInTests(unittest.TestCase):
    """The extracted-payload checks must RUN, not merely exist.

    This is the defect the checks themselves were written to prevent, one
    level up: they were written, reviewed, merged and correct, and nothing
    ever called them -- so the gate could print RELEASE GATE PASSED with no
    payload assertion having executed. A safeguard reachable only by
    remembering a second command is off by default.

    Asserted against the gate's source rather than by packaging a real
    archive, because packaging needs a full build; what has to be true is
    that the call exists, runs before the PASSED line, and quarantines on
    failure.
    """

    def _gate_source(self):
        return Path(gate.__file__).read_text(encoding="utf-8")

    def test_the_gate_invokes_the_payload_verifier(self):
        self.assertIn(
            "work/verify_extracted_release_payload.py",
            self._gate_source(),
            "the gate does not run the extracted-payload verifier, so a "
            "release can pass without any payload check having executed",
        )

    def test_the_verifier_runs_before_the_gate_declares_success(self):
        source = self._gate_source()
        invoked = source.index("work/verify_extracted_release_payload.py")
        passed = source.index('print(f"RELEASE GATE PASSED')
        self.assertLess(
            invoked,
            passed,
            "the payload verifier runs after the gate has already declared "
            "the archive publishable, which is the same as not running it",
        )

    def test_a_failing_payload_check_quarantines_the_archive(self):
        source = self._gate_source()
        invoked = source.index("work/verify_extracted_release_payload.py")
        tail = source[invoked:source.index('print(f"RELEASE GATE PASSED')]
        self.assertIn(
            "quarantine(archive",
            tail,
            "a failed payload check must move the archive aside; leaving a "
            "rejected bundle at the publishable filename is the accident "
            "the gate exists to prevent",
        )

    def test_the_verifier_is_given_the_archive_the_gate_packaged(self):
        source = self._gate_source()
        invoked = source.index("work/verify_extracted_release_payload.py")
        tail = source[invoked:invoked + 220]
        self.assertIn(
            "str(archive)",
            tail,
            "the verifier must check the archive this gate just packaged, "
            "not whatever its own default resolution happens to find",
        )


def _bundle(path, settings, name="VF2-B999-Release"):
    """A minimal packaged release carrying just the setting ids."""
    import json as _json
    import zipfile as _zipfile

    with _zipfile.ZipFile(path, "w") as z:
        z.writestr(
            f"{name}/manifest.json",
            _json.dumps({"settings": [{"id": s} for s in settings]}),
        )
    return path


class FeatureRegressionTests(unittest.TestCase):
    """A release must not ship fewer features than the one before it.

    B183 shipped 23 settings where B181 shipped 35 -- twelve gone, none
    added -- and every step reported success. default_settings() drops
    SOURCE_BACKED_OPTIONAL_SETTINGS the export cannot resolve inputs for, so
    a run that cannot find those assets silently produces a smaller patcher
    and packages it happily. Nothing compared the output against the
    previous release, so a person opening the archive was the first check.
    """

    def test_a_release_that_drops_settings_is_named_and_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = _bundle(root / "VF2-B181-Release.zip", ["a", "b", "c"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a"])
            reason = gate.lost_settings(after, before)
            self.assertIsNotNone(reason, "a release short two settings passed the gate")
            # The names, not just the count: a count says a release is short,
            # the names say which build inputs went missing.
            self.assertIn("b", reason)
            self.assertIn("c", reason)

    def test_an_unchanged_release_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = _bundle(root / "VF2-B181-Release.zip", ["a", "b"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a", "b"])
            self.assertIsNone(gate.lost_settings(after, before))

    def test_a_release_that_only_adds_settings_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = _bundle(root / "VF2-B181-Release.zip", ["a"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a", "b"])
            self.assertIsNone(
                gate.lost_settings(after, before),
                "adding a feature must not be mistaken for losing one",
            )

    def test_a_swap_is_still_a_loss(self):
        # Equal counts, different contents. Comparing sizes would miss this.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = _bundle(root / "VF2-B181-Release.zip", ["a", "b"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a", "c"])
            reason = gate.lost_settings(after, before)
            self.assertIsNotNone(reason)
            self.assertIn("b", reason)

    def test_the_previous_release_is_not_the_archive_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root / "VF2-B181-Release.zip", ["a"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a"])
            previous = gate.previous_release_archive(after)
            self.assertIsNotNone(previous)
            self.assertNotEqual(previous.resolve(), after.resolve())

    def test_a_quarantined_archive_is_not_used_as_the_baseline(self):
        # A rejected release must not become the standard a later one is
        # measured against, or one bad build lowers the bar permanently.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root / "VF2-B182-Release.zip.REJECTED", ["a"])
            _bundle(root / "VF2-B181-Release.zip", ["a", "b"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a"])
            previous = gate.previous_release_archive(after)
            self.assertEqual(previous.name, "VF2-B181-Release.zip")

    def test_a_thin_release_cannot_launder_an_identity_loss(self):
        # The failure this exists for. With the known-thin B183 retained
        # beside B181, comparing against only the NEWEST predecessor lets a
        # B184 drop a B181-only setting, add a replacement to keep the count
        # at 35, and pass both the comparison and the floor -- the setting
        # disappears while the gate prints success. Cardinality cannot catch
        # a swap; identity can.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            full = [f"s{i}" for i in range(gate.EXPECTED_SETTING_COUNT)]
            _bundle(root / "VF2-B181-Release.zip", full)
            _bundle(root / "VF2-B183-Release.zip", full[:23])
            after = _bundle(
                root / "VF2-B184-Release.zip",
                [x for x in full if x != "s30"] + ["replacement"],
            )
            # Same count as a complete release, so the floor is satisfied.
            self.assertIsNone(gate.short_of_expected(after))
            # And the newest predecessor alone reports nothing lost.
            self.assertIsNone(
                gate.lost_settings(after, root / "VF2-B183-Release.zip")
            )
            # The union catches it.
            lost = gate.lost_settings(after, gate.earlier_releases(after))
            self.assertIsNotNone(
                lost, "a B181-only setting vanished behind the thin B183"
            )
            self.assertIn("s30", lost)

    def test_every_earlier_release_is_a_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root / "VF2-B179-Release.zip", ["a"])
            _bundle(root / "VF2-B181-Release.zip", ["b"])
            after = _bundle(root / "VF2-B184-Release.zip", ["a", "b"])
            self.assertEqual(
                [p.name for p in gate.earlier_releases(after)],
                ["VF2-B179-Release.zip", "VF2-B181-Release.zip"],
            )
            self.assertIsNone(gate.lost_settings(after, gate.earlier_releases(after)))

    def test_a_malformed_settings_collection_never_reads_as_empty(self):
        # An empty baseline has nothing to lose, so lost_settings() reports
        # success and a short release stays publishable. Every one of these
        # shapes used to produce an empty set silently: absent, a dict, a
        # string, rows that are not objects, rows without an id, and an
        # explicitly empty list. A read that cannot fail is not a read.
        import zipfile as _zipfile

        shapes = {
            "settings absent": "{}",
            "settings is a dict": '{"settings": {}}',
            "settings is a string": '{"settings": "everything"}',
            "row is not an object": '{"settings": [1]}',
            "row has no id": '{"settings": [{}]}',
            "row id is empty": '{"settings": [{"id": ""}]}',
            "settings is empty": '{"settings": []}',
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, (label, body) in enumerate(shapes.items()):
                path = root / f"VF2-B{100 + index}-Release.zip"
                with _zipfile.ZipFile(path, "w") as bundle:
                    bundle.writestr("x/manifest.json", body)
                with self.subTest(shape=label):
                    with self.assertRaises(gate.UnreadableRelease):
                        gate.settings_in_archive(path)

    def _archives_the_message_says_to_move(self, message, candidates, lost):
        """Work out WHICH archives the refusal is telling us to move.

        Not just that it says "move" -- Codex's point was that "move the
        release(s) NOT offering them" matches a naive regex while telling
        the operator to do the opposite of the right thing. So resolve the
        instruction against the actual archives: the ones it names are the
        ones offering the settings reported lost, and the test then moves
        exactly those.
        """
        collapsed = " ".join(message.split()).lower()
        instruction = re.search(
            r"move the release\(s\)\s*(?P<qualifier>[a-z ]*?)offering them"
            r"\s*out of this directory",
            collapsed,
        )
        if instruction is None:
            return None
        # A qualifier such as "not " inverts the meaning; only an empty one
        # (or a harmless "still ") means "the archives that offer them".
        qualifier = instruction.group("qualifier").strip()
        if qualifier not in ("", "still"):
            return None
        return [
            archive for archive in candidates
            if lost & gate.settings_in_archive(archive)
        ]

    def test_the_test_follows_the_message_rather_than_its_author(self):
        """Every action below is DERIVED from the refusal, not hard-coded.

        Two rounds of review shaped this. First, deleting the guidance
        outright left the suite green at 36 passed, so the test was pinned
        to the message. Then the pin was still too weak: it only checked
        that a "move ..." sentence existed, so rewording it to "move the
        release(s) NOT offering them" would have kept passing while
        instructing the operator to keep the offending baseline.

        Now the message selects the archive. If it names the wrong one, or
        names none, there is nothing to move and the test fails.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = _bundle(root / "VF2-B181-Release.zip", ["alpha", "beta"])
            fresh = _bundle(root / "VF2-B182-Release.zip", ["alpha"])

            message = gate.lost_settings(fresh, [old])
            self.assertIsNotNone(message)
            self.assertIn("beta", message)

            lost = (gate.settings_in_archive(old)
                    - gate.settings_in_archive(fresh))
            to_move = self._archives_the_message_says_to_move(
                message, [old, fresh], lost)
            self.assertIsNotNone(
                to_move,
                "the refusal does not tell the operator to move the archives "
                "OFFERING the dropped settings, so following it would not "
                "reach a publishable state",
            )
            self.assertEqual(
                to_move, [old],
                "the instruction resolves to the wrong archive; moving that "
                "would leave the offending baseline in place",
            )

            # It must also warn that this can leave no predecessor, and name
            # the flag for that case rather than ruling it out.
            collapsed = " ".join(message.split()).lower()
            self.assertIn("no predecessor", collapsed)
            self.assertIn("--allow-missing-predecessor", message)
            self.assertNotIn("will not help", collapsed)

            # NOW do exactly what it resolved to.
            retired = root / "retired"
            retired.mkdir()
            for archive in to_move:
                archive.rename(retired / archive.name)

            with self.subTest(step="the drop is no longer reported"):
                self.assertEqual(gate.earlier_releases(fresh), [])
                self.assertIsNone(gate.lost_settings(fresh, []))

            with self.subTest(step="the predicted second refusal is real"):
                source = Path(gate.__file__).read_text(encoding="utf-8")
                body = source.split("def main(")[1]
                self.assertIn("if not args.allow_missing_predecessor:", body)

            with self.subTest(step="the floor refuses, and says why"):
                # Reached BEFORE lost_settings() in main(), so it has to name
                # the retirement route itself or the guidance above is
                # unreachable for a real retirement.
                floor = gate.short_of_expected(fresh)
                self.assertIsNotNone(floor)
                self.assertIn("EXPECTED_SETTING_COUNT", floor)
                self.assertIn("retired on purpose", floor)

            with self.subTest(step="following THAT instruction passes"):
                # Do what the floor message says: lower the count in the same
                # commit that retires the setting. A retirement must have a
                # way through, or the instructions are a dead end.
                original = gate.EXPECTED_SETTING_COUNT
                try:
                    gate.EXPECTED_SETTING_COUNT = len(
                        gate.settings_in_archive(fresh))
                    self.assertIsNone(gate.short_of_expected(fresh))
                    self.assertIsNone(gate.lost_settings(fresh, []))
                finally:
                    gate.EXPECTED_SETTING_COUNT = original

    def test_every_mention_of_the_flag_permits_the_retirement_case(self):
        """The CLI must not contradict its own refusal.

        The lost-settings message sends an operator to
        --allow-missing-predecessor after a retirement, while the flag help
        and the missing-predecessor refusal both said it was for a first
        release only. Following one meant disobeying another.
        """
        source = Path(gate.__file__).read_text(encoding="utf-8")
        for phrase in ("Only for \"\n            \"a genuine first release",
                       "if this really is the first "):
            with self.subTest(phrase=phrase.strip()[:40]):
                self.assertNotIn(
                    phrase, source,
                    "this wording excludes the deliberate-retirement case "
                    "that the lost-settings refusal sends operators to",
                )

    def test_a_well_formed_manifest_still_reads(self):
        # The shape checks must not reject a real release: the guard is only
        # worth having if it still lets the thing it guards through.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = _bundle(root / "VF2-B181-Release.zip", ["alpha", "beta"])
            self.assertEqual(gate.settings_in_archive(good), {"alpha", "beta"})

    def test_a_manifest_of_the_wrong_shape_is_reported_not_raised(self):
        # Syntactically valid JSON with the wrong top-level type: json.loads
        # succeeds and .get() raises AttributeError. If that happens outside
        # the protected block it escapes main() after packaging and the
        # archive stays at its publishable filename.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import zipfile as _zipfile
            odd = root / "VF2-B181-Release.zip"
            with _zipfile.ZipFile(odd, "w") as z:
                z.writestr("x/manifest.json", "[]")
            with self.assertRaises(gate.UnreadableRelease):
                gate.settings_in_archive(odd)

    def test_an_unreadable_predecessor_is_reported_not_raised(self):
        # The read happens AFTER packaging. An uncaught exception unwinds
        # main() without reaching quarantine(), leaving a rejected archive at
        # its publishable filename -- this gate causing the accident it
        # exists to prevent. A truncated file with the exact canonical name
        # passes the grammar filter, so the name check does not cover this.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VF2-B181-Release.zip").write_bytes(b"truncated, not a zip")
            after = _bundle(root / "VF2-B183-Release.zip", ["a"])
            previous = gate.previous_release_archive(after)
            self.assertEqual(previous.name, "VF2-B181-Release.zip")
            with self.assertRaises(gate.UnreadableRelease):
                gate.lost_settings(after, previous)

    def test_an_archive_with_no_manifest_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import zipfile as _zipfile
            empty = root / "VF2-B181-Release.zip"
            with _zipfile.ZipFile(empty, "w") as z:
                z.writestr("readme.txt", "no manifest here")
            with self.assertRaises(gate.UnreadableRelease):
                gate.settings_in_archive(empty)

    def test_a_missing_predecessor_does_not_read_as_success(self):
        # /outputs/ and *.zip are both gitignored, so a clean checkout or a
        # cleaned outputs/ supplies no predecessor at all. Treating that as a
        # pass makes every established release look like the first one and
        # skips the check exactly when nobody is watching.
        # Asserted behaviourally rather than by pinning an identifier: an
        # earlier version of this test indexed "previous is None" and broke
        # when that branch was rewritten, while the property it protects was
        # untouched.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alone = _bundle(
                root / "VF2-B184-Release.zip",
                [f"setting_{i}" for i in range(gate.EXPECTED_SETTING_COUNT)],
            )
            self.assertEqual(
                gate.earlier_releases(alone), [],
                "no predecessor should be found for a lone archive",
            )
        source = Path(gate.__file__).read_text(encoding="utf-8")
        passed = source.index('print(f"RELEASE GATE PASSED')
        self.assertIn(
            "allow_missing_predecessor", source[:passed],
            "the bootstrap must be an explicit decision, not a default",
        )

    def test_the_bootstrap_override_exists_and_is_opt_in(self):
        source = Path(gate.__file__).read_text(encoding="utf-8")
        self.assertIn("--allow-missing-predecessor", source)
        self.assertIn('action="store_true"', source)

    def test_a_thin_release_is_rejected_even_with_no_baseline(self):
        # "No fewer than the previous release" is only as good as the release
        # it compares against. With no prior archive there is nothing to
        # compare against at all, and without an absolute floor a thin build
        # would pass unexamined.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            thin = _bundle(root / "VF2-B184-Release.zip", ["a", "b"])
            self.assertIsNone(gate.previous_release_archive(thin))
            self.assertIsNotNone(
                gate.short_of_expected(thin),
                "a release with two settings passed with no baseline present",
            )

    def test_a_thin_release_cannot_become_the_new_bar(self):
        # The failure mode the floor exists for: if a thin release is used as
        # the baseline, every later release inherits its loss and the
        # comparison alone reports success forever.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            thin = _bundle(root / "VF2-B183-Release.zip", ["a"])
            after = _bundle(root / "VF2-B184-Release.zip", ["a"])
            # The comparison is happy -- nothing was lost against B183.
            self.assertIsNone(gate.lost_settings(after, thin))
            # The floor is not.
            self.assertIsNotNone(gate.short_of_expected(after))

    def test_a_complete_release_passes_the_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            full = _bundle(
                root / "VF2-B184-Release.zip",
                [f"setting_{i}" for i in range(gate.EXPECTED_SETTING_COUNT)],
            )
            self.assertIsNone(gate.short_of_expected(full))

    def test_the_floor_runs_before_the_baseline_comparison(self):
        # Ordered deliberately: a thin build should be named as thin, not as
        # "lost N settings against whichever archive happened to be nearby".
        source = Path(gate.__file__).read_text(encoding="utf-8")
        floor = source.index("short_of_expected(archive)")
        baseline = source.index("earlier_releases(archive)")
        self.assertLess(
            floor, baseline,
            "a thin build should be named as thin, not as a loss against "
            "whichever archive happened to be nearby",
        )

    def test_the_baseline_is_chosen_by_version_not_by_spelling(self):
        # Sorted as text, VF2-B99 lands AFTER VF2-B181. Gating B183 with both
        # retained would pick B99 as the baseline, and a setting present in
        # B181 but absent from B99 and B183 would never be reported -- the
        # gate passing the exact loss it exists to block.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root / "VF2-B99-Release.zip", ["a"])
            _bundle(root / "VF2-B181-Release.zip", ["a", "b"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a"])
            previous = gate.previous_release_archive(after)
            self.assertEqual(previous.name, "VF2-B181-Release.zip")
            self.assertIsNotNone(
                gate.lost_settings(after, previous),
                "the B181-only setting was dropped and went unreported",
            )

    def test_a_revision_outranks_the_release_it_revises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root / "VF2-B181-Release.zip", ["a"])
            _bundle(root / "VF2-B181-Release-r2.zip", ["a", "b"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a"])
            self.assertEqual(
                gate.previous_release_archive(after).name,
                "VF2-B181-Release-r2.zip",
            )

    def test_a_scratch_zip_is_never_the_baseline(self):
        # Reading a non-release ZIP raises AFTER packaging, which aborts the
        # gate without quarantining and leaves the new archive sitting at its
        # publishable filename.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VF2-B183-Release-corrupt.zip").write_bytes(b"not a zip")
            _bundle(root / "VF2-B181-Release.zip", ["a", "b"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a"])
            previous = gate.previous_release_archive(after)
            self.assertEqual(previous.name, "VF2-B181-Release.zip")
            # And the check still reports the real loss rather than dying.
            self.assertIsNotNone(gate.lost_settings(after, previous))

    def test_a_later_release_is_not_used_as_the_baseline(self):
        # Re-gating an older archive must not measure it against a newer one,
        # which would report every later addition as a loss.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root / "VF2-B190-Release.zip", ["a", "b", "c"])
            _bundle(root / "VF2-B181-Release.zip", ["a"])
            after = _bundle(root / "VF2-B183-Release.zip", ["a"])
            self.assertEqual(
                gate.previous_release_archive(after).name,
                "VF2-B181-Release.zip",
            )

    def test_the_gate_runs_the_check_before_declaring_success(self):
        source = Path(gate.__file__).read_text(encoding="utf-8")
        checked = source.index("lost_settings(archive, previous)")
        passed = source.index('print(f"RELEASE GATE PASSED')
        self.assertLess(checked, passed)
        tail = source[checked:passed]
        self.assertIn("quarantine(archive", tail)


class VariantCoverageTests(unittest.TestCase):
    def test_a_complete_release_passes(self):
        complete = len(verifier.EXECUTABLE_VARIANT_REQUIREMENTS)
        self.assertIsNone(gate.incomplete_variant_coverage(complete))

    def test_a_short_release_is_rejected(self):
        complete = len(verifier.EXECUTABLE_VARIANT_REQUIREMENTS)
        # B174.2's matrix run stopped at 14 of 19 and produced no bundle; a
        # run that stops short must never reach a published release.
        for shipped in (0, 1, 14, 19, complete - 1):
            if shipped == complete:
                continue
            with self.subTest(shipped=shipped):
                message = gate.incomplete_variant_coverage(shipped)
                self.assertIsNotNone(message)
                self.assertIn(str(complete), message)

    def test_a_missing_or_malformed_count_is_rejected(self):
        for shipped in (None, "32", -1):
            with self.subTest(shipped=shipped):
                self.assertIsNotNone(gate.incomplete_variant_coverage(shipped))


class QuarantineTests(unittest.TestCase):
    """A rejected bundle must not stay at the publishable filename.

    Reporting a bad archive but leaving it in place is a check a later
    manual upload step walks straight past.
    """

    def test_rejected_archive_is_moved_aside(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            archive = Path(tmp.name) / "VF2-B999-Release.zip"
            archive.write_bytes(b"not a real bundle")
            code = gate.quarantine(archive, "because")
            self.assertEqual(code, 1)
            self.assertFalse(archive.exists())
            moved = archive.parent / (archive.name + ".REJECTED")
            self.assertTrue(moved.is_file())
            self.assertEqual(moved.read_bytes(), b"not a real bundle")
        finally:
            tmp.cleanup()

    def test_every_gate_failure_path_quarantines(self):
        source = Path(gate.__file__).read_text(encoding="utf-8")
        body = source.split("def main(")[1]
        # Any bare `return 1` after packaging would leave a rejected bundle
        # sitting at the publishable name; failures must go through
        # quarantine() instead.
        after_package = body.split("verified =")[1]
        self.assertNotIn("return 1", after_package)
        # Not a pinned count: adding a legitimate check adds a
        # quarantine path, and a literal here goes stale the first
        # time that happens -- the same failure the release readback
        # contract had when it pinned 34/34/17. What must hold is that
        # every post-packaging failure routes through quarantine, which
        # the assertNotIn above already proves, and that there is at
        # least one such path per gate check.
        self.assertGreaterEqual(
            after_package.count("return quarantine(archive"), 3)

    def test_a_failed_quarantine_warns_instead_of_claiming_a_move(self):
        """A move that did not happen must never be reported as one.

        The archive stays at its publishable filename in that case, so a
        message saying it was "moved to VF2-B177-Release.zip" reads as the
        fail-safe having worked and is worse than saying nothing.
        """
        tmp = tempfile.TemporaryDirectory()
        try:
            archive = Path(tmp.name) / "VF2-B999-Release.zip"
            archive.write_bytes(b"bundle")
            original = Path.replace

            def refuse(self, target):
                raise OSError("archive is locked")

            err = io.StringIO()
            Path.replace = refuse
            try:
                with contextlib.redirect_stderr(err):
                    code = gate.quarantine(archive, "because")
            finally:
                Path.replace = original

            self.assertEqual(code, 1)
            message = err.getvalue()
            self.assertIn("could NOT be quarantined", message)
            self.assertIn("REMAINS AT ITS PUBLISHABLE FILENAME", message)
            self.assertNotIn("archive moved to", message)
            # And the bundle really is still there, unharmed.
            self.assertTrue(archive.is_file())
            self.assertEqual(archive.read_bytes(), b"bundle")
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
