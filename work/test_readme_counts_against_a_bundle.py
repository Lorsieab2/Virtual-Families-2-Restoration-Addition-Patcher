#!/usr/bin/env python3
"""README counts describe what a bundle carries, so a bundle must confirm them.

Two defects reached B180 because README numbers were checked against source
constants instead of a manifest. Both looked correct in review, because the
prose and the assertion were derived from the same wrong authority:

  * "it offers 36 settings" was len(SETTINGS); the bundle carries 35, since
    two settings are deliberately withheld and one is added during export.
  * "20 verified mobile renovation images" counted Bathroom 1 and Bathroom 2
    together; Bathroom 2's art is gated on a different setting and ships
    under its own entry, so Add mobile room renovations carries 15.

The exporter is not a valid check on a claim about a bundle. This suite reads
a built manifest and, when a release archive is available, the archive itself.
It is skipped rather than failed where neither exists -- a machine with no
build output cannot answer the question, and pretending otherwise is how the
suite went red for everyone once already.
"""
import json
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _manifest():
    """The newest built manifest, or None.

    A release archive is preferred: it is what a player actually receives.
    A build-output manifest is the fallback.
    """
    for archive in sorted(
        ROOT.rglob("VF2-B*-Release.zip"), key=lambda p: p.name, reverse=True
    ):
        try:
            with zipfile.ZipFile(archive) as bundle:
                names = [n for n in bundle.namelist() if n.endswith("manifest.json")]
                if names:
                    return json.loads(bundle.read(names[0])), f"archive {archive.name}"
        except (zipfile.BadZipFile, OSError):
            continue
    for path in sorted(
        (ROOT / "outputs").rglob("manifest.json"), key=lambda p: p.name, reverse=True
    ):
        try:
            return json.loads(path.read_text(encoding="utf-8")), f"build {path.parent.name}"
        except (OSError, json.JSONDecodeError):
            continue
    return None, None


class ReadmeCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.source = _manifest()
        if cls.manifest is None:
            raise unittest.SkipTest(
                "needs a built manifest or a release archive; neither is present"
            )

    def _records(self):
        return self.manifest.get("asset_patches", []) + self.manifest.get(
            "post_asset_patches", []
        )

    def _pngs_requiring(self, setting):
        found = set()
        for record in self._records():
            requires = record.get("requires")
            requires = requires if isinstance(requires, list) else (
                [requires] if requires else []
            )
            path = record.get("file_path", "")
            if setting in requires and path.endswith(".png"):
                found.add(path)
        return found

    def test_the_offered_settings_count_matches_the_manifest(self):
        self.assertIn(
            f"bundle offers {len(self.manifest['settings'])} settings",
            README,
            f"README disagrees with {self.source}, which carries "
            f"{len(self.manifest['settings'])} settings",
        )

    def test_the_renovation_count_excludes_the_bathroom_2_art(self):
        """Room images only -- store icons and curtains are not renovations."""
        rooms = {
            p for p in self._pngs_requiring("mobile_renovations")
            if "/store_icons/" not in p and "/curtains/" not in p
        }
        self.assertIn(
            f"{len(rooms)} verified mobile renovation images",
            README,
            f"README disagrees with {self.source}, which carries {len(rooms)} "
            "room images under mobile_renovations",
        )

    def test_bathroom_2_art_is_gated_on_its_own_setting(self):
        """The reason the two counts are separate, pinned so it stays true."""
        own = self._pngs_requiring("ai_generated_bathroom2_renovations")
        self.assertTrue(own, "Bathroom 2 art is no longer gated on its own setting")
        shared = own & self._pngs_requiring("mobile_renovations")
        self.assertEqual(
            shared, set(), "Bathroom 2 art must not also ship under mobile_renovations"
        )

    def test_the_behavior_map_count_matches_the_manifest(self):
        maps = {
            r.get("file_path", "") for r in self._records()
            if r.get("file_path", "").endswith(".fmap")
            and "mobile_furniture_behaviors" in (
                r.get("requires") if isinstance(r.get("requires"), list)
                else [r.get("requires")]
            )
        }
        self.assertIn(f"Ships {len(maps)} behavior maps", README)


if __name__ == "__main__":
    unittest.main()
