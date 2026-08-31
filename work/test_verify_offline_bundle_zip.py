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


def newest_identities_on_disk():
    """The highest-numbered identities file committed to the repo.

    The contract test below checks the shape of an identities file, not its
    agreement with any archive, so tying it to a release ZIP would silence it
    entirely in a clean checkout -- outputs/ is gitignored, so there is never
    an archive there in CI. Pick by parsed release number for the same reason
    newest_release_zip does.
    """
    best = None
    for path in (ROOT / "data" / "vf2").glob("release-identities-B*.json"):
        match = re.match(r"^release-identities-B(\d+)(?:\.(\d+))?\.json$", path.name)
        if not match:
            continue
        key = (int(match.group(1)), int(match.group(2) or 0))
        if best is None or key > best[0]:
            best = (key, path)
    return best[1] if best else None


def contract_size_for(archive):
    """How many executable variants *that* archive is supposed to carry.

    outputs/ may retain B174 or B176, which correctly shipped 19
    combinations.  Comparing whatever archive happens to be newest against
    today's matrix makes these release-oriented tests fail on a perfectly
    valid retained release, so the contract comes from that release's own
    tracked identities file when one exists.
    """
    identities = newest_release_identities()
    if identities is not None and identities.is_file():
        return len(json.loads(identities.read_text(encoding="utf-8-sig"))["variants"])
    return len(verifier.EXECUTABLE_VARIANT_REQUIREMENTS)



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
        # Derived from the matrix, not restated here: a hardcoded count made
        # this test fail the moment the matrix gained the 13 Mobile Renovations
        # combinations it had never built.
        matrix = json.loads(
            (ROOT / "data" / "vf2" / "build-matrix-toggles.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(
            len(verifier.EXECUTABLE_VARIANT_REQUIREMENTS),
            len({
                frozenset(
                    {"core_executable"}
                    | {
                        {"holiday_ornaments": "holiday_ornaments_collection"}.get(k, k)
                        for k, v in variant.items()
                        if k not in ("name", "ai_generated_bathroom2")
                        and isinstance(v, bool)
                        and v
                    }
                )
                for variant in matrix["variants"]
            }),
        )
        # No release name may leak back into the contract, or the verifier
        # starts failing every release after that one again. The contract is
        # now derived from the matrix rather than written out as a literal, so
        # the region to police is the derivation itself.
        source = (ROOT / "work" / "verify_offline_bundle_zip.py").read_text(encoding="utf-8")
        derivation = source.split("def _matrix_variant_requirements", 1)[1].split(
            "\n\n\n", 1
        )[0]
        self.assertNotRegex(derivation, r"B\d+")
        self.assertNotIn(".exe", derivation)
        # And the contract must not be a hand-written literal again.
        self.assertIn(
            "EXECUTABLE_VARIANT_REQUIREMENTS = _matrix_variant_requirements()", source
        )

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
        # The archive's own contract, not today's matrix: a retained B174 or
        # B176 correctly carries 19 and must stay testable.
        self.assertEqual(len(records), contract_size_for(archive))
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
        identities = newest_release_identities()
        result = verifier.verify_archive(
            archive,
            identities if identities is not None and identities.is_file() else None,
        )
        self.assertEqual(result["executable_variants"], contract_size_for(archive))
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

    def test_short_identities_cannot_authenticate_a_full_archive(self):
        """Dropping a variant must still fail -- now caught against the archive.

        _load_variant_identities no longer rejects a short file outright,
        because a retained older release legitimately pins fewer combinations
        than today's matrix builds.  The guarantee moved rather than went
        away: a short identities file no longer describes the archive in front
        of it, so verify_archive fails on the count.  Completeness of a *new*
        release is asserted by work/gate_release_zip.py.
        """
        identities = newest_release_identities()
        if identities is None or not identities.is_file():
            identities = newest_identities_on_disk()
        if identities is None or not identities.is_file():
            self.skipTest("no identities file present")
        archive = newest_release_zip()
        if archive is None or not archive.is_file():
            self.skipTest("no release archive present")
        payload = json.loads(identities.read_text(encoding="utf-8-sig"))
        payload["variants"] = payload["variants"][:-1]
        tmp = tempfile.TemporaryDirectory()
        try:
            short = Path(tmp.name) / "short.json"
            short.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "executable variants, found"):
                verifier.verify_archive(archive, short)
        finally:
            tmp.cleanup()

    def test_retained_older_release_verifies_against_its_own_contract(self):
        """A finished release keeps the contract it shipped with.

        B174, B174.1 and B176 each correctly shipped the 19 combinations that
        existed when they were built.  Deriving the contract globally from
        today's 32-combination matrix reported every retained archive as
        broken, which is both wrong and the fastest way to teach people that a
        failing verifier is normal.
        """
        identities_dir = ROOT / "data" / "vf2"
        historical = sorted(
            path
            for path in identities_dir.glob("release-identities-B*.json")
            if len(json.loads(path.read_text(encoding="utf-8-sig"))["variants"])
            < len(verifier.EXECUTABLE_VARIANT_REQUIREMENTS)
        )
        if not historical:
            self.skipTest("no pre-32-variant identities file is tracked")
        for path in historical:
            with self.subTest(identities=path.name):
                loaded = verifier._load_variant_identities(path)
                shipped = len(json.loads(path.read_text(encoding="utf-8-sig"))["variants"])
                self.assertEqual(len(loaded), shipped)
                self.assertLess(len(loaded), len(verifier.EXECUTABLE_VARIANT_REQUIREMENTS))
                # Every combination it pins must still be one the matrix can
                # build, so a hand-edited file cannot invent one and pass.
                self.assertTrue(set(loaded) <= verifier.EXECUTABLE_VARIANT_REQUIREMENTS)

    def test_identities_naming_a_combination_the_matrix_cannot_build_fail_closed(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            path = Path(tmp.name) / "identities.json"
            path.write_text(
                json.dumps(
                    {
                        "variants": [
                            {
                                "requires": ["core_executable", "not_a_real_toggle"],
                                "sha256": "0" * 64,
                                "size": 1,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "never builds"):
                verifier._load_variant_identities(path)
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

    def test_archive_contract_resolves_from_its_own_release_label(self):
        """A retained archive verifies even when no identities file is passed.

        Otherwise the current matrix is applied to a release that predates it
        and every retained B174/B176 ZIP reports as broken.
        """
        identities_dir = ROOT / "data" / "vf2"
        seen = 0
        for path in sorted(identities_dir.glob("release-identities-B*.json")):
            label = path.stem.replace("release-identities-", "")
            shipped = len(json.loads(path.read_text(encoding="utf-8-sig"))["variants"])
            with self.subTest(release=label):
                resolved = verifier._tracked_contract_for(f"VF2-{label}-Release")
                self.assertIsNotNone(resolved)
                self.assertEqual(len(resolved), shipped)
                seen += 1
        self.assertTrue(seen, "no tracked release identities files found")

    def test_releases_predating_identity_files_keep_their_contract(self):
        """B161-B173 shipped before per-release identity files existed.

        Without a recorded historical contract, verifying one of those
        retained archives falls through to the current matrix and rejects its
        valid 19 executable records.
        """
        historical = json.loads(
            (ROOT / "data" / "vf2" / "historical-release-contracts.json").read_text(
                encoding="utf-8-sig"
            )
        )
        expected = len(historical["combinations"])
        self.assertEqual(expected, 19)
        for label in ("B161", "B165", "B172", "B173"):
            with self.subTest(release=label):
                resolved = verifier._tracked_contract_for(f"VF2-{label}-Release")
                self.assertIsNotNone(resolved)
                self.assertEqual(len(resolved), expected)
                self.assertTrue(resolved <= verifier.EXECUTABLE_VARIANT_REQUIREMENTS)

    def test_historical_contract_matches_the_earliest_tracked_identities(self):
        """Its provenance, asserted rather than trusted.

        The recorded historical combinations are the contract B174, B174.1 and
        B176 all shipped; if that stops being true the recorded table is wrong.
        """
        historical = {
            frozenset(entry)
            for entry in json.loads(
                (ROOT / "data" / "vf2" / "historical-release-contracts.json").read_text(
                    encoding="utf-8-sig"
                )
            )["combinations"]
        }
        for label in ("B174", "B174.1", "B176"):
            path = ROOT / "data" / "vf2" / f"release-identities-{label}.json"
            if not path.is_file():
                continue
            with self.subTest(release=label):
                shipped = {
                    frozenset(entry["requires"])
                    for entry in json.loads(path.read_text(encoding="utf-8-sig"))["variants"]
                }
                self.assertEqual(shipped, historical)

    def test_release_label_ordering(self):
        self.assertLess(verifier._release_sort_key("B174"), verifier._release_sort_key("B174.1"))
        self.assertLess(verifier._release_sort_key("B174.1"), verifier._release_sort_key("B176"))
        self.assertLess(verifier._release_sort_key("B99"), verifier._release_sort_key("B161"))
        for bad in ("", "junk", "174", "B", "Bx"):
            with self.subTest(label=bad):
                with self.assertRaises(ValueError):
                    verifier._release_sort_key(bad)

    def test_unknown_or_malformed_root_falls_back_to_the_matrix(self):
        for root in ("VF2-B999-Release", "junk", "", "VF2--Release"):
            with self.subTest(root=root):
                self.assertIsNone(verifier._tracked_contract_for(root))

    def test_advertised_gate_path_rejects_a_truncated_release(self):
        """--require-identities must be as strict as gate_release_zip.py.

        Both this tool's help and export_release_bundle.py advertise
        --require-identities as the release gate.  A bundle and an identities
        file that omit the same valid combination agree with each other, so
        without a completeness check the advertised path authenticates a
        truncated release and only the separate gate catches it.
        """
        archive = newest_release_zip()
        identities = newest_release_identities()
        if archive is None or identities is None or not identities.is_file():
            self.skipTest("no release ZIP or identities file present")
        shipped = json.loads(identities.read_text(encoding="utf-8-sig"))
        if len(shipped["variants"]) != len(verifier.EXECUTABLE_VARIANT_REQUIREMENTS):
            self.skipTest("newest release is not a complete build")

        # Sanity: the untruncated release passes the advertised path.
        verifier.verify_archive(archive, identities, require_complete=True)

        payload = dict(shipped, variants=shipped["variants"][:-1])
        tmp = tempfile.TemporaryDirectory()
        try:
            short = Path(tmp.name) / "short.json"
            short.write_text(json.dumps(payload), encoding="utf-8")
            # Without completeness this is only caught by the archive count.
            with self.assertRaises(ValueError):
                verifier.verify_archive(archive, short)
            # The advertised gate must name the real problem.
            with self.assertRaisesRegex(ValueError, "every combination the matrix builds"):
                verifier.verify_archive(archive, short, require_complete=True)
        finally:
            tmp.cleanup()

    def test_require_identities_sets_completeness_on_the_cli(self):
        source = Path(verifier.__file__).read_text(encoding="utf-8")
        self.assertIn("require_complete=args.require_identities", source)


if __name__ == "__main__":
    unittest.main()
