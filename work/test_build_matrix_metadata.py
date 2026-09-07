"""Regression tests for the descriptive build-matrix metadata."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data" / "vf2" / "build-matrix-toggles.json"


def validate_matrix_metadata(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    variants = data["variants"]
    match = re.fullmatch(r"vf2-(\d+)-variant-toggle-matrix-v1", data["matrix_id"])
    if match is None:
        raise AssertionError("matrix_id does not declare a numeric variant count")
    declared_id_count = int(match.group(1))
    note_match = re.search(r"Stable (\d+)-variant feature-toggle matrix", data["note"])
    if note_match is None:
        raise AssertionError("note does not declare a numeric variant count")
    declared_note_count = int(note_match.group(1))
    if declared_id_count != declared_note_count:
        raise AssertionError("matrix_id and note disagree")
    if declared_id_count != len(variants):
        raise AssertionError(
            f"declared count {declared_id_count} does not match {len(variants)} variants"
        )
    return len(variants)


class BuildMatrixMetadataTests(unittest.TestCase):
    def test_declared_count_matches_authoritative_variants_array(self):
        self.assertEqual(validate_matrix_metadata(MATRIX), 32)

    def test_known_bad_temp_copy_is_rejected(self):
        data = json.loads(MATRIX.read_text(encoding="utf-8"))
        data["variants"] = data["variants"][:-1]
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / MATRIX.name
            bad.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "does not match"):
                validate_matrix_metadata(bad)


if __name__ == "__main__":
    unittest.main()
