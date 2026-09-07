"""Gate-level checks that do not require packaging a release.

The gate is the only place that can require a release to cover every
combination the matrix builds: verify_offline_bundle_zip checks an archive
against its own release's contract so retained older ZIPs still verify.
"""

from __future__ import annotations

import contextlib
import io
import sys
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
