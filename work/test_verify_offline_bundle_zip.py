import sys
import tempfile
import unittest
import zipfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import verify_offline_bundle_zip as verifier


CANONICAL = ROOT / "outputs" / "VF2-B161-Repurchaseable-20260812.zip"


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
            "payload/Virtual Families 2 - Modded B161 - Final All-Enabled Native.exe",
        )
        self.assertEqual(len(verifier.EXECUTABLE_VARIANTS), 19)

    def test_real_executable_variants_table_has_no_hash_collisions(self):
        # Confirms the actual, currently-shipped EXECUTABLE_VARIANTS table
        # this repository verifies against does not itself carry the B162
        # defect (two different requires sets sharing one payload hash).
        verifier._reject_executable_variant_hash_collisions(verifier.EXECUTABLE_VARIANTS)

    def test_rejects_two_requires_sets_sharing_one_executable_hash(self):
        # Reproduces the B162 defect at the level of the EXECUTABLE_VARIANTS
        # contract this verifier checks archives against: the
        # core_executable-only baseline and the Final All-Enabled Native
        # overlay must never resolve to the same payload hash.
        same_hash = "a" * 64
        variants = {
            frozenset({"core_executable"}): (
                "payload/core.exe", same_hash, 100,
            ),
            frozenset({
                "core_executable", "island_events", "cheat_upgrades",
                "holiday_ornaments_collection", "behavior_patches", "mobile_renovations",
            }): (
                "payload/final-all-enabled.exe", same_hash, 100,
            ),
        }
        with self.assertRaisesRegex(ValueError, "share one payload hash"):
            verifier._reject_executable_variant_hash_collisions(variants)

        # Distinct hashes for distinct requires sets must not raise.
        variants_ok = dict(variants)
        variants_ok[frozenset({"core_executable"})] = ("payload/core.exe", "b" * 64, 100)
        verifier._reject_executable_variant_hash_collisions(variants_ok)

    def test_canonical_archive_passes_all_contract_gates(self):
        self.assertTrue(CANONICAL.is_file(), CANONICAL)
        result = verifier.verify_archive(CANONICAL)
        self.assertEqual(result["executable_variants"], 19)
        self.assertEqual(result["renovation_assets"], 35)
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
