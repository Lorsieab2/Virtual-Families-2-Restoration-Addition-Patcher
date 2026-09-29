"""The release bundle's "Check for updates" line opens the same page as the GUI.

The owner: "Check for updates" goes to the base GitHub repository, not the
releases page. The GUI's link is one constant (src/offline_vf2_patcher_gui.py);
the bundle exporter writes "How to Use.txt" from its own template
(work/export_offline_patch_bundle.py), so a release could otherwise ship the
old link in the text file while the GUI opens the new one (Codex, #383).
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://github.com/Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher/"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UpdateLinkBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "work"))
        cls.bundle = _load("vf2_bundle_exporter", ROOT / "work" / "export_offline_patch_bundle.py")
        cls.source = (ROOT / "work" / "export_offline_patch_bundle.py").read_text(encoding="utf-8")

    def test_the_bundle_updates_url_is_the_base_repository(self):
        self.assertEqual(self.bundle.PATCHER_UPDATES_URL, BASE)

    def test_the_how_to_use_template_uses_it(self):
        self.assertIn("Check for updates:\n{PATCHER_UPDATES_URL}", self.source.replace("\r\n", "\n"))
        self.assertNotIn("Check for updates:\n{PATCHER_RELEASES_URL}", self.source.replace("\r\n", "\n"))

    def test_an_exported_bundle_carries_the_base_repository_link(self):
        # Codex, #383: check the file the exporter actually writes, not just
        # the template's source text.
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = Path(tmp)
            written = self.bundle.write_bundle_runner_files(bundle_dir, "B196")
            self.assertIn("How to Use.txt", written)
            how_to = (bundle_dir / "How to Use.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
            self.assertIn("Check for updates:\n" + BASE + "\n", how_to)
            self.assertNotIn(BASE + "releases", how_to)
            gui = (bundle_dir / "offline_vf2_patcher_gui.py").read_text(encoding="utf-8")
            self.assertIn(f'PATCHER_RELEASES_URL = "{BASE}"', gui)

    def test_the_shipped_how_to_use_and_the_gui_agree(self):
        how_to = (ROOT / "How to Use.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertIn("Check for updates:\n" + BASE + "\n", how_to)
        gui = (ROOT / "src" / "offline_vf2_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn(f'PATCHER_RELEASES_URL = "{BASE}"', gui)


if __name__ == "__main__":
    unittest.main()
