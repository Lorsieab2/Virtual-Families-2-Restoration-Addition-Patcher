import re
import sys
import tempfile
import unittest
import zipfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import verify_offline_bundle_zip as verifier

verifier_test_pattern = re.compile(r"^VF2-B(\d+)(?:\.(\d+))?-Release\.zip$")


RELEASE_ZIP_PATTERN = re.compile(r"^VF2-B(\d+)(?:\.(\d+))?-Release\.zip$")


def newest_release_zip():
    """The highest-numbered release ZIP present locally, if any.

    This used to point at one B161 archive that is not in the repository, so
    the gate failed for everyone regardless of correctness. It then briefly
    picked by modification time, which identifies the most recently copied
    file rather than the newest release -- downloading B173 after B174 would
    have left the current artifact unchecked. Ordering is by parsed release
    number, with point releases (B155.5) sorting after their base.
    """
    best = None
    for path in (ROOT / "outputs").glob("VF2-B*-Release.zip"):
        match = RELEASE_ZIP_PATTERN.match(path.name)
        if not match:
            continue
        key = (int(match.group(1)), int(match.group(2) or 0))
        if best is None or key > best[0]:
            best = (key, path)
    return best[1] if best else None


def newest_release_identities():
    """Return the independent identities for the release selected above."""
    archive = newest_release_zip()
    if archive is None:
        return None
    match = RELEASE_ZIP_PATTERN.match(archive.name)
    if match is None:
        return None
    point = f".{match.group(2)}" if match.group(2) else ""
    return ROOT / "data" / "vf2" / f"release-identities-B{match.group(1)}{point}.json"


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

    def test_release_selection_prefers_highest_number_not_newest_file(self):
        # Modification time identifies the most recently copied file, not the
        # newest release: downloading B173 after B174 must not leave the
        # current artifact unchecked.
        import re as _re
        names = ["VF2-B99-Release.zip", "VF2-B174-Release.zip", "VF2-B155.5-Release.zip"]
        keys = []
        for name in names:
            m = verifier_test_pattern.match(name)
            keys.append(((int(m.group(1)), int(m.group(2) or 0)), name))
        self.assertEqual(max(keys)[1], "VF2-B174-Release.zip")
        # A point release sorts above its own base.
        self.assertGreater((155, 5), (155, 0))

    def test_apply_runner_pattern_accepts_point_releases(self):
        # The exporter's own grammar is B\d+(?:\.\d+)? and B155.5 shipped.
        self.assertTrue(verifier.APPLY_RUNNER_PATTERN.match("Apply_B174_Patcher.bat"))
        self.assertTrue(verifier.APPLY_RUNNER_PATTERN.match("Apply_B174.5_Patcher.bat"))
        self.assertFalse(verifier.APPLY_RUNNER_PATTERN.match("Apply_Patcher.bat"))
        self.assertFalse(verifier.APPLY_RUNNER_PATTERN.match("Apply_B174_Patcher.bat.txt"))

    def test_identities_authenticate_variants_against_an_independent_source(self):
        archive = newest_release_zip()
        identities = newest_release_identities()
        if archive is None or not identities.is_file():
            self.skipTest("no release ZIP or identities file present")

        # Without identities the executables are only self-consistent, and the
        # summary has to say so rather than implying authentication.
        plain = verifier.verify_archive(archive)
        self.assertFalse(plain["variant_identities_authenticated"])

        authenticated = verifier.verify_archive(archive, identities)
        self.assertTrue(authenticated["variant_identities_authenticated"])

        # Swapping two combinations' compiled identities is exactly the defect
        # a self-consistency check cannot see, so it must fail.
        payload = json.loads(identities.read_text(encoding="utf-8"))
        first, second = payload["variants"][0], payload["variants"][-1]
        first["sha256"], second["sha256"] = second["sha256"], first["sha256"]
        first["size"], second["size"] = second["size"], first["size"]
        tmp = tempfile.TemporaryDirectory()
        try:
            swapped = Path(tmp.name) / "swapped.json"
            swapped.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not the binary the build compiled"):
                verifier.verify_archive(archive, swapped)
        finally:
            tmp.cleanup()

    def test_identities_must_cover_the_whole_release_contract(self):
        identities = newest_release_identities()
        if identities is None or not identities.is_file():
            self.skipTest("no identities file present")
        payload = json.loads(identities.read_text(encoding="utf-8"))
        payload["variants"] = payload["variants"][:-1]
        tmp = tempfile.TemporaryDirectory()
        try:
            short = Path(tmp.name) / "short.json"
            short.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "do not cover the release contract"):
                verifier._load_variant_identities(short)
        finally:
            tmp.cleanup()

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
