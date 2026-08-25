import sys
import tempfile
import unittest
import zipfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import verify_offline_bundle_zip as verifier


def newest_release_zip():
    """The most recent release ZIP present locally, if any.

    This used to point at one B161 archive that is not in the repository, so
    the gate failed for everyone regardless of correctness. Verifying whatever
    release is actually on disk makes it a live check instead.
    """
    candidates = sorted(
        (ROOT / "outputs").glob("VF2-B*-Release.zip"),
        key=lambda path: path.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


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
        # The contract is the toggle combination, not a release's filename.
        requires = frozenset({
            "core_executable",
            "behavior_patches",
            "cheat_upgrades",
            "holiday_ornaments_collection",
            "island_events",
            "mobile_renovations",
        })
        self.assertIn(requires, verifier.EXECUTABLE_VARIANT_REQUIREMENTS)
        self.assertEqual(len(verifier.EXECUTABLE_VARIANT_REQUIREMENTS), 19)
        # No release name may leak back into the pinned contract, or the
        # verifier starts failing every release after that one again.
        source = (ROOT / "work" / "verify_offline_bundle_zip.py").read_text(encoding="utf-8")
        contract = source.split("EXECUTABLE_VARIANT_REQUIREMENTS = ", 1)[1].split("})", 1)[0]
        self.assertNotRegex(contract, r"B\d+")
        self.assertNotIn(".exe", contract)

    def test_shipped_release_has_no_executable_hash_collisions(self):
        # Confirms the release actually on disk does not carry the B162 defect
        # (two different requires sets sharing one payload hash). The check now
        # runs against real manifest records rather than a frozen table.
        archive = newest_release_zip()
        if archive is None:
            self.skipTest("no release ZIP present in outputs/")
        with zipfile.ZipFile(archive) as zipped:
            root = zipped.namelist()[0].split("/", 1)[0]
            manifest = json.loads(zipped.read(f"{root}/manifest.json"))
        records = [
            record
            for record in manifest["asset_patches"]
            if str(record.get("source_path", "")).lower().endswith(".exe")
        ]
        self.assertEqual(len(records), 19)
        verifier._reject_executable_variant_hash_collisions(records)

    def test_rejects_two_requires_sets_sharing_one_executable_hash(self):
        # Reproduces the B162 defect at the level of the EXECUTABLE_VARIANTS
        # contract this verifier checks archives against: the
        # core_executable-only baseline and the Final All-Enabled Native
        # overlay must never resolve to the same payload hash.
        same_hash = "a" * 64
        records = [
            {
                "source_path": "payload/core.exe",
                "source_sha256": same_hash,
                "requires": ["core_executable"],
            },
            {
                "source_path": "payload/final-all-enabled.exe",
                "source_sha256": same_hash,
                "requires": [
                    "core_executable", "island_events", "cheat_upgrades",
                    "holiday_ornaments_collection", "behavior_patches",
                    "mobile_renovations",
                ],
            },
        ]
        with self.assertRaisesRegex(ValueError, "share one payload hash"):
            verifier._reject_executable_variant_hash_collisions(records)

        # Distinct hashes for distinct requires sets must not raise.
        records_ok = [dict(records[0], source_sha256="b" * 64), records[1]]
        verifier._reject_executable_variant_hash_collisions(records_ok)

    def test_shipped_release_passes_all_contract_gates(self):
        archive = newest_release_zip()
        if archive is None:
            self.skipTest("no release ZIP present in outputs/")
        result = verifier.verify_archive(archive)
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
