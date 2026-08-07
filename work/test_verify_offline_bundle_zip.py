import sys
import tempfile
import unittest
import zipfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import verify_offline_bundle_zip as verifier


CANONICAL = ROOT / "outputs" / "VF2-B158-1b01c94-Toggle-Corrected-Playtest-Final.zip"


class OfflineBundleZipVerifierTests(unittest.TestCase):
    def test_summary_zip_field_uses_archive_input_not_asset_path(self):
        source = (ROOT / "work" / "verify_offline_bundle_zip.py").read_text(encoding="utf-8")
        self.assertIn('"zip": str(archive_path)', source)

    def test_sound_routes_count_unique_authenticated_executable_identities(self):
        source = (ROOT / "work" / "verify_offline_bundle_zip.py").read_text(encoding="utf-8")
        self.assertIn("len(variants) != len(exe_hashes)", source)
        self.assertNotIn("len(variants) != len(EXECUTABLE_VARIANTS)", source)

    def test_candidate_zero_record_contract_matches_present_feature_records(self):
        self.assertNotIn("island_events", verifier.ABSENT_ZERO_RECORD_SETTINGS)
        self.assertNotIn("holiday_ornaments_collection", verifier.ABSENT_ZERO_RECORD_SETTINGS)
        self.assertNotIn("behavior_patches", verifier.ABSENT_ZERO_RECORD_SETTINGS)
        self.assertNotIn("store_scroll_bar", verifier.ABSENT_ZERO_RECORD_SETTINGS)

    def test_verifier_requires_final_all_enabled_native_overlay(self):
        requires = frozenset({
            "core_executable",
            "behavior_patches",
            "cheat_upgrades",
            "holiday_ornaments_collection",
            "island_events",
            "mobile_renovations",
        })
        self.assertEqual(
            verifier.EXECUTABLE_VARIANTS[requires][0],
            "payload/Virtual Families 2 - Modded B158 - Final All-Enabled Native.exe",
        )
        self.assertEqual(len(verifier.EXECUTABLE_VARIANTS), 8)

    def test_canonical_archive_passes_all_contract_gates(self):
        self.assertTrue(CANONICAL.is_file(), CANONICAL)
        result = verifier.verify_archive(CANONICAL)
        self.assertEqual(result["executable_variants"], 8)
        self.assertEqual(result["renovation_assets"], 15)
        self.assertEqual(result["sound_assets"], 67)
        self.assertEqual(result["sound_restores"], 63)
        self.assertEqual(result["sound_removals"], 4)
        self.assertEqual(result["sound_routes"], 4)

    def _unsafe_archive(self, names):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "safe.zip"
        with zipfile.ZipFile(path, "w") as zipped:
            for name in names:
                zipped.writestr(name, b"x")
        return tmp, path

    def test_rejects_unsafe_or_noncanonical_inventory_before_manifest(self):
        for names in (("safe/manifest.json", "../escape"), ("safe/manifest.json", "other/file"), ("safe/manifest.json", "SAFE/MANIFEST.JSON")):
            with self.subTest(names=names):
                tmp, path = self._unsafe_archive(names)
                try:
                    with self.assertRaises(ValueError):
                        verifier.verify_archive(path)
                finally:
                    tmp.cleanup()

    def test_explicit_path_is_required_and_missing_archive_fails_closed(self):
        with self.assertRaises(ValueError):
            verifier.verify_archive(ROOT / "outputs" / "does-not-exist.zip")

    def test_malformed_manifest_types_fail_closed(self):
        malformed_values = (
            {"target_files": [None]},
            {"target_files": [], "settings": [None]},
            {"target_files": [], "settings": [{"id": []}]},
            {"target_files": [], "settings": [], "asset_patches": [{"requires": None}], "post_asset_patches": []},
        )
        for manifest in malformed_values:
            with self.subTest(manifest=manifest):
                tmp = tempfile.TemporaryDirectory()
                try:
                    path = Path(tmp.name) / "safe.zip"
                    with zipfile.ZipFile(path, "w") as zipped:
                        zipped.writestr("safe/manifest.json", json.dumps(manifest))
                    with self.assertRaises(ValueError):
                        verifier.verify_archive(path)
                finally:
                    tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
