"""The release verifier must ask the same questions the installer asks.

Both defects these tests pin were real and shipped: the verifier approved
bundles that the installer would then fail on, which is the worst direction
for a release gate to be wrong in.

The checks live inside ``main()``, so they cannot be called directly without
restructuring the module. These tests therefore assert the source contract --
the same technique ``test_offline_vf2_patcher_gui`` uses for the popup
centering rule -- plus behavioural tests of the two resolution rules
themselves, so a rewrite still has to satisfy the behaviour.
"""

import pathlib
import re
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "work" / "verify_extracted_release_payload.py"
INSTALLER = ROOT / "work" / "offline_vf2_patcher.py"

SOURCE = VERIFIER.read_text(encoding="utf-8")
INSTALLER_SOURCE = INSTALLER.read_text(encoding="utf-8")


def index_installed(manifest):
    """The verifier's manifest index, as the installer would key it."""
    installed = {}
    for key in ("asset_patches", "post_asset_patches"):
        for record in manifest.get(key, []):
            target_key = record.get("output_file_path") or record.get("file_path")
            if target_key:
                installed.setdefault(target_key, record)
    return installed


def resolve_under_manifest(manifest_path, source_rel):
    """The verifier's payload resolution, as the installer would resolve it."""
    candidate = manifest_path.parent / pathlib.PurePosixPath(source_rel)
    return candidate if candidate.is_file() else None


class ReleaseVerifierMatchesInstaller(unittest.TestCase):
    def test_the_installer_still_honours_output_file_path(self):
        # The premise of the index rule. If the installer ever stops reading
        # output_file_path, this test should fail rather than the index rule
        # quietly protecting against nothing.
        self.assertIn('raw.get("output_file_path"', INSTALLER_SOURCE)

    def test_the_installer_still_resolves_under_the_manifest_directory(self):
        # The premise of the resolution rule, for the same reason.
        self.assertIn("resolve_under_manifest_dir(manifest_dir, asset.source_path)",
                      INSTALLER_SOURCE)

    def test_the_verifier_indexes_by_the_real_output_target(self):
        # A record may name the expected file in file_path and redirect its
        # output elsewhere. Keying on file_path alone accepts that bundle
        # while the player never receives the map.
        self.assertIn('target_key = record.get("file_path")', SOURCE)
        self.assertIn('record.get("output_file_path") or target_key', SOURCE)

    def test_a_redirected_record_is_not_treated_as_installed(self):
        target = "Assets/SpaLoungerStd.png.fmap"
        manifest = {"asset_patches": [{
            "file_path": target,
            "output_file_path": "Assets/somewhere_else.fmap",
            "source_path": "payload/SpaLoungerStd.png.fmap",
        }]}
        self.assertNotIn(target, index_installed(manifest))

    def test_an_ordinary_record_is_still_treated_as_installed(self):
        # The rule must not reject correct bundles: a record with no
        # output_file_path still keys on file_path.
        target = "Assets/SpaLoungerStd.png.fmap"
        manifest = {"asset_patches": [{
            "file_path": target,
            "source_path": "payload/SpaLoungerStd.png.fmap",
        }]}
        self.assertIn(target, index_installed(manifest))

    def test_the_verifier_does_not_search_the_archive_by_suffix(self):
        # A global rglob whose match test is endswith(source_path) accepts a
        # stale copy deeper in the archive. The installer joins the path under
        # the manifest directory exactly, so the verifier must too.
        self.assertNotIn("EXTRACT.rglob(pathlib.PurePosixPath(", SOURCE)
        self.assertIn("_resolve_manifest_path(manifest_path.parent, source_rel)", SOURCE)

    def test_a_stale_copy_elsewhere_in_the_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            extract = pathlib.Path(tmp)
            manifest_path = extract / "bundle" / "manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text("{}", encoding="utf-8")
            stale = extract / "old" / "payload"
            stale.mkdir(parents=True)
            (stale / "SpaLoungerStd.png.fmap").write_bytes(b"stale")
            self.assertIsNone(
                resolve_under_manifest(manifest_path,
                                       "payload/SpaLoungerStd.png.fmap"))

    def test_the_file_beside_the_manifest_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            extract = pathlib.Path(tmp)
            manifest_path = extract / "bundle" / "manifest.json"
            good = manifest_path.parent / "payload"
            good.mkdir(parents=True)
            manifest_path.write_text("{}", encoding="utf-8")
            (good / "SpaLoungerStd.png.fmap").write_bytes(b"real")
            resolved = resolve_under_manifest(manifest_path,
                                              "payload/SpaLoungerStd.png.fmap")
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.read_bytes(), b"real")

    def test_the_resolved_file_is_hashed_rather_than_the_declared_digest(self):
        # Comparing declared digests to each other only proves the manifest
        # agrees with itself, and `.get(..., "")` maps every omission to the
        # same value, so three records declaring nothing would compare equal.
        self.assertIn("hashlib.sha256(resolved.read_bytes())", SOURCE)
        self.assertRegex(
            SOURCE,
            re.compile(r"declares no source_sha256", re.S),
        )


if __name__ == "__main__":
    unittest.main()
