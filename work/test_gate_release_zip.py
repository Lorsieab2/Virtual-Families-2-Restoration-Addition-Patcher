"""Gate-level checks that do not require packaging a release.

The gate is the only place that can require a release to cover every
combination the matrix builds: verify_offline_bundle_zip checks an archive
against its own release's contract so retained older ZIPs still verify.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_release_zip as gate
import verify_offline_bundle_zip as verifier


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


if __name__ == "__main__":
    unittest.main()
