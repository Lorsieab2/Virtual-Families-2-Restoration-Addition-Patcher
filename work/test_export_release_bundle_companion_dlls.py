"""A release bundle carries every companion DLL.

Every executable since B201 has the dormant Time Controls loader (.vf2time) and,
since Up to 28 Children, the .vf2kids loader too (and, from the Family History
log on, the .vf2hist loader; from R Refreshes the Store on, the .vf2rfsh loader). The exporter refuses such a build unless it is
handed the DLLs (--time-controls-dll, --up-to-28-children-dll, --family-history-dll,
--store-refresh-dll),
and export_release_bundle.py, the script a release is made with, passed
neither: B201 was exported only after a hand edit to it that was never
committed, and a B202 export from main stopped at "pass --time-controls-dll".

These tests run export_release_bundle.main() against a stand-in matrix and read
the arguments it hands the exporter. Nothing is built or exported.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

WORK = Path(__file__).resolve().parent
REAL_ROOT = WORK.parent
sys.path.insert(0, str(WORK))

import export_release_bundle as erb  # noqa: E402


def _real_exporter_help() -> str:
    return subprocess.run(
        [sys.executable, str(WORK / "export_offline_patch_bundle.py"), "--help"],
        capture_output=True, text=True, cwd=REAL_ROOT,
    ).stdout


class TheReleaseScriptHandsOverBothDlls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.help_text = _real_exporter_help()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "data" / "vf2").mkdir(parents=True)
        shutil.copy(REAL_ROOT / "data" / "vf2" / "build-matrix-toggles.json",
                    self.tmp / "data" / "vf2" / "build-matrix-toggles.json")
        variants = [v["name"] for v in json.loads(
            (REAL_ROOT / "data" / "vf2" / "build-matrix-toggles.json").read_text(encoding="utf-8-sig")
        )["variants"]]
        for name in variants:
            folder = self.tmp / "outputs" / f"VF2-T-matrix-{name}"
            folder.mkdir(parents=True)
            (folder / "Virtual Families 2 - T.exe").write_bytes(b"MZ")
        vanilla = self.tmp / "work" / "vanilla_runtime_payload"
        vanilla.mkdir(parents=True)
        (vanilla / "Virtual Families 2.exe").write_bytes(b"MZ")
        self.exporter_argv = None

    def _run(self, *extra: str) -> int:
        def fake_run(cmd, *args, **kwargs):
            if "--help" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout=self.help_text, stderr="")
            self.exporter_argv = list(cmd[2:])
            return subprocess.CompletedProcess(cmd, 7)

        argv = ["export_release_bundle.py", "--release", "T", "--matrix-prefix", "VF2-T-matrix", *extra]
        with mock.patch.object(erb, "ROOT", self.tmp), \
                mock.patch.object(erb.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(sys, "argv", argv):
            return erb.main()

    def _value(self, flag: str) -> str:
        self.assertIsNotNone(self.exporter_argv, "the exporter was never called")
        self.assertEqual(1, self.exporter_argv.count(flag), f"{flag} not passed exactly once")
        return self.exporter_argv[self.exporter_argv.index(flag) + 1]

    def test_the_exporter_knows_both_flags(self):
        self.assertIn("--time-controls-dll", self.help_text)
        self.assertIn("--up-to-28-children-dll", self.help_text)
        self.assertIn("--family-history-dll", self.help_text)
        self.assertIn("--outfit-pictures-dll", self.help_text)

    def test_by_default_the_runtime_build_dlls_are_passed(self):
        self.assertEqual(7, self._run(), "the exporter's exit code is the script's")
        self.assertEqual(Path(self._value("--time-controls-dll")),
                         (self.tmp / "runtime" / "build" / "vf2time_b200.dll").resolve())
        self.assertEqual(Path(self._value("--up-to-28-children-dll")),
                         (self.tmp / "runtime" / "build" / "vf2kids_b200.dll").resolve())
        self.assertEqual(Path(self._value("--family-history-dll")),
                         (self.tmp / "runtime" / "build" / "vf2history_b200.dll").resolve())
        self.assertEqual(Path(self._value("--outfit-pictures-dll")),
                         (self.tmp / "runtime" / "build" / "vf2outfits_b200.dll").resolve())

    def test_named_dlls_are_passed_as_given(self):
        time_dll = self.tmp / "staged" / "vf2time_b200.dll"
        kids_dll = self.tmp / "staged" / "vf2kids_b200.dll"
        history_dll = self.tmp / "staged" / "vf2history_b200.dll"
        outfits_dll = self.tmp / "staged" / "vf2outfits_b200.dll"
        self.assertEqual(7, self._run("--time-controls-dll", str(time_dll),
                                      "--up-to-28-children-dll", str(kids_dll),
                                      "--family-history-dll", str(history_dll),
                                      "--outfit-pictures-dll", str(outfits_dll)))
        self.assertEqual(Path(self._value("--time-controls-dll")), time_dll.resolve())
        self.assertEqual(Path(self._value("--up-to-28-children-dll")), kids_dll.resolve())
        self.assertEqual(Path(self._value("--family-history-dll")), history_dll.resolve())
        self.assertEqual(Path(self._value("--outfit-pictures-dll")), outfits_dll.resolve())

    def test_an_exporter_without_the_flag_is_refused(self):
        self.help_text = self.help_text.replace("--up-to-28-children-dll", "--something-else")
        self.assertEqual(1, self._run())
        self.assertIsNone(self.exporter_argv, "exported although the DLL could not be passed")

    def test_an_exporter_without_the_store_refresh_flag_is_refused(self):
        self.help_text = self.help_text.replace("--store-refresh-dll", "--something-else")
        self.assertEqual(1, self._run())
        self.assertIsNone(self.exporter_argv, "exported although the DLL could not be passed")

    def test_an_exporter_without_the_family_history_flag_is_refused(self):
        self.help_text = self.help_text.replace("--family-history-dll", "--something-else")
        self.assertEqual(1, self._run())
        self.assertIsNone(self.exporter_argv, "exported although the DLL could not be passed")

    def test_an_exporter_without_the_outfit_pictures_flag_is_refused(self):
        self.help_text = self.help_text.replace("--outfit-pictures-dll", "--something-else")
        self.assertEqual(1, self._run())
        self.assertIsNone(self.exporter_argv, "exported although the DLL could not be passed")


if __name__ == "__main__":
    unittest.main()
