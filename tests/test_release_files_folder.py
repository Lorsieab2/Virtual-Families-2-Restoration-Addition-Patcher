"""The unzipped release keeps only what the player opens or reads at its top.

The owner (26 October 2026, after the same change to the VF1 patcher): every loose file at the top of
the unzipped release goes into one folder, "Virtual Families 2 Fun Patcher Files", named as the Virtual
Villagers patcher's "Virtual Villagers Fun Patcher Files". The .bat launchers, How to Use, the README
and the Transparency Log stay at the top; the scripts, manifest.json, payload/, icons and pictures move.

And no file may hit Windows' "path too long" error because of the deeper folder: the patcher's own reads
and writes (staging, output, backups, temp files) work with the patcher sitting deep, and a modded game
folder whose files the game could not open (past 259 characters) is refused up front, never part-way.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import export_offline_patch_bundle as exporter  # noqa: E402
import package_patcher_zip  # noqa: E402
import verify_offline_bundle_zip as verifier  # noqa: E402

sys.path.insert(0, str(ROOT / "src"))
import offline_vf2_patcher as patcher  # noqa: E402

PATCHER = ROOT / "src" / "offline_vf2_patcher.py"
FOLDER = "Virtual Families 2 Fun Patcher Files"
TOP_LEVEL = {"Apply_B999_Patcher.bat", "Launch_GUI.bat", "How to Use.txt", "README-B999-PATCHER.txt"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TopLevelLayoutTests(unittest.TestCase):
    def test_the_folder_name_is_the_same_everywhere(self):
        self.assertEqual(exporter.PATCHER_FILES_FOLDER, FOLDER)
        self.assertEqual(verifier.PATCHER_FILES_FOLDER, FOLDER)
        self.assertEqual(package_patcher_zip.PATCHER_FILES_FOLDER, FOLDER)

    def test_only_player_files_are_written_at_the_top(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "VF2-B999-Release"
            bundle.mkdir()
            written = exporter.write_bundle_runner_files(bundle, "B999")
            top = {p.name for p in bundle.iterdir()}
            self.assertEqual(top, TOP_LEVEL | {FOLDER})
            files = bundle / FOLDER
            for name in ("offline_vf2_patcher.py", "offline_vf2_patcher_gui.py", "vf2_how_to_use.json",
                         "vf2_crash_capture.py", "crash-capture-manifest.template.json",
                         "family_tree_backgrounds/blue-island.png"):
                with self.subTest(name=name):
                    self.assertTrue((files / name).is_file())
                    self.assertIn(f"{FOLDER}/{name}", written)
            # Every listed runner exists at the ZIP-root-relative path the manifest records.
            for rel in written:
                with self.subTest(runner=rel):
                    self.assertTrue((bundle / rel).is_file())
            # And the verifier's required list is satisfied by what the exporter writes.
            self.assertLessEqual(verifier._required_runners(FOLDER + "/"), set(written))

    def test_bat_files_run_the_moved_scripts_relative_to_their_own_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            exporter.write_bundle_runner_files(bundle, "B999")
            gui = (bundle / "Launch_GUI.bat").read_text(encoding="ascii")
            apply = (bundle / "Apply_B999_Patcher.bat").read_text(encoding="ascii")
        for name, text, command in (
            ("Launch_GUI.bat", gui,
             '%VF2_PY% "%FILES_DIR%offline_vf2_patcher_gui.py" "%FILES_DIR%manifest.json"'),
            ("Apply", apply,
             '%VF2_PY% "%FILES_DIR%offline_vf2_patcher.py" apply --exe "%VF2_EXE%" --manifest "%FILES_DIR%manifest.json"'),
        ):
            with self.subTest(bat=name):
                self.assertIn(f'set "FILES_DIR=%~dp0{FOLDER}\\"', text)
                self.assertIn(command, text)
                self.assertNotIn('"%SCRIPT_DIR%offline_vf2_patcher', text)
                self.assertNotIn('"%SCRIPT_DIR%manifest.json"', text)

    @unittest.skipUnless(os.name == "nt", "runs the .bat file under cmd.exe")
    def test_apply_bat_finds_its_files_from_another_folder_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "unzipped here" / "VF2 B999 Release"
            bundle.mkdir(parents=True)
            exporter.write_bundle_runner_files(bundle, "B999")
            (bundle / FOLDER / "manifest.json").write_text("{}", encoding="utf-8")
            elsewhere = Path(tmp) / "some other folder"
            elsewhere.mkdir()
            missing_exe = Path(tmp) / "no such folder" / "Virtual Families 2.exe"
            result = subprocess.run(
                ["cmd", "/c", str(bundle / "Apply_B999_Patcher.bat")],
                cwd=elsewhere, input=f"{missing_exe}\n\n", capture_output=True, text=True, timeout=60,
            )
            # The folder check passed (the .bat found manifest.json by its own folder), so it went on
            # to ask for the EXE and reported the made-up one as missing.
            self.assertIn("File not found", result.stdout)
            self.assertNotIn("folder is missing", result.stdout)

            (bundle / FOLDER / "manifest.json").unlink()
            result = subprocess.run(
                ["cmd", "/c", str(bundle / "Launch_GUI.bat")],
                cwd=elsewhere, input="\n", capture_output=True, text=True, timeout=60,
            )
            self.assertIn(f'The "{FOLDER}" folder is missing', result.stdout)
            self.assertEqual(result.returncode, 1)

    def test_player_text_names_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            exporter.write_bundle_runner_files(bundle, "B999")
            how_to = (bundle / "How to Use.txt").read_text(encoding="ascii")
            readme = (bundle / "README-B999-PATCHER.txt").read_text(encoding="ascii")
        for name, text in (("How to Use", how_to), ("README", readme)):
            with self.subTest(text=name):
                self.assertIn(f'"{FOLDER}"', text)
                self.assertIn("260 characters", text)
        self.assertIn(f'"{FOLDER}"', (ROOT / "How to Use.txt").read_text(encoding="utf-8"))

    def test_overlay_payload_names_are_short(self):
        name = exporter.overlay_payload_name(
            "Virtual Families 2 - Modded B204.exe",
            "Cheat Upgrades + Holiday Ornaments + Behavior Patches + Mobile Room Renovations",
        )
        self.assertEqual(name, "Virtual Families 2 - Modded B204 - CU+HO+BP+MR.exe")
        # The longest overlay entry in the zip, as Windows' Extract All lays it out (the zip's name
        # once more as a folder): it must not be what decides how deep the zip can be unzipped.
        longest = "VF2-B204-Release/" + FOLDER + "/payload/" + exporter.overlay_payload_name(
            "Virtual Families 2 - Modded B204.exe",
            "Island Events + Cheat Upgrades + Holiday Ornaments + Behavior Patches + Mobile Room Renovations",
        )
        self.assertLess(len(longest), 130)


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class VerifierLayoutTests(unittest.TestCase):
    ROOT_NAME = "VF2-B999-Release"

    def names(self, *rels):
        return {f"{self.ROOT_NAME}/{rel}" for rel in rels}

    def test_tidy_layout_is_accepted(self):
        names = self.names(
            "Launch_GUI.bat", "Apply_B999_Patcher.bat", "How to Use.txt", "README-B999-PATCHER.txt",
            "Transparency Log.txt", f"{FOLDER}/manifest.json", f"{FOLDER}/payload/a.png",
            f"{FOLDER}/offline_vf2_patcher.py",
        )
        base, prefix = verifier._bundle_layout(names, self.ROOT_NAME, True)
        self.assertEqual(base, f"{self.ROOT_NAME}/{FOLDER}")
        self.assertEqual(prefix, FOLDER + "/")

    def test_anything_else_loose_at_the_top_is_refused(self):
        for loose in ("offline_vf2_patcher.py", "manifest.json", "patcher_icon.png", "payload/a.png",
                      "family_tree_backgrounds/x.png"):
            with self.subTest(loose=loose):
                names = self.names("Launch_GUI.bat", f"{FOLDER}/manifest.json", loose)
                with self.assertRaisesRegex(ValueError, "may sit at the top"):
                    verifier._bundle_layout(names, self.ROOT_NAME, False)

    def test_the_gate_refuses_the_old_flat_layout(self):
        names = self.names("Launch_GUI.bat", "manifest.json", "payload/a.png")
        with self.assertRaisesRegex(ValueError, "must be in"):
            verifier._bundle_layout(names, self.ROOT_NAME, True)
        # A retained older release (flat) still reads, without the gate's flag.
        self.assertEqual(verifier._bundle_layout(names, self.ROOT_NAME, False), (self.ROOT_NAME, ""))

    def test_gate_passes_the_flag(self):
        self.assertIn('"--require-files-folder"', (ROOT / "work" / "gate_release_zip.py").read_text(encoding="utf-8"))

    def test_packager_reads_the_manifest_in_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "VF2-B999-Release"
            (bundle / FOLDER).mkdir(parents=True)
            (bundle / FOLDER / "manifest.json").write_text('{"asset_patches": []}', encoding="utf-8")
            (bundle / "Launch_GUI.bat").write_text("@echo off\r\n", encoding="ascii")
            archive = Path(tmp) / "VF2-B999-Release.zip"
            self.assertEqual(package_patcher_zip.package(bundle, archive), 2)
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(
                    sorted(z.namelist()),
                    [f"VF2-B999-Release/Launch_GUI.bat", f"VF2-B999-Release/{FOLDER}/manifest.json"],
                )


class LongPathTests(unittest.TestCase):
    """A deep patcher folder and a deep (but still playable) output folder must both work."""

    EXE_NAME = "Virtual Families 2 - Modded Deep.exe"

    @staticmethod
    def deep(base: Path, length: int) -> Path:
        """A folder under BASE whose full path is LENGTH characters, built from long folder names."""
        path = base
        while len(str(path)) < length - 45:
            path = path / ("A long folder name for testing deep paths " + str(len(str(path)) % 10))
        return path / ("x" * (length - len(str(path)) - 1))

    def make_install(self, tmp: Path, bundle: Path):
        game = tmp / "Virtual Families 2"
        (game / "Images").mkdir(parents=True)
        exe = game / "Virtual Families 2.exe"
        exe.write_bytes(b"vanilla exe")
        (game / "Images" / "a.png").write_bytes(b"vanilla a")
        payload = patcher.long_path(bundle / "payload", force=True)
        payload.mkdir(parents=True)
        (payload / "mod.exe").write_bytes(b"modded exe")
        (payload / "a.png").write_bytes(b"modded a")
        manifest = {
            "manifest_version": 1,
            "name": "deep",
            "output": {"default_folder_name": "VF2-BDeep-Modded", "default_exe_name": self.EXE_NAME},
            "settings": [{"id": "core_executable", "default": True}, {"id": "art", "default": True}],
            "target_files": [{"path": exe.name, "sha256": sha(b"vanilla exe"), "size": 11}],
            "asset_patches": [
                {"file_path": exe.name, "output_file_path": self.EXE_NAME, "source_path": "payload/mod.exe",
                 "source_sha256": sha(b"modded exe"), "expected_target_sha256": sha(b"vanilla exe"),
                 "overwrite_existing": True, "requires": ["core_executable"]},
                {"file_path": "Images/a.png", "source_path": "payload/a.png", "source_sha256": sha(b"modded a"),
                 "overwrite_existing": True, "requires": ["art"]},
            ],
        }
        manifest_path = bundle / "manifest.json"
        patcher.long_path(manifest_path, force=True).write_text(json.dumps(manifest), encoding="utf-8")
        return exe, manifest_path

    def run_patcher(self, *args):
        return subprocess.run([sys.executable, str(PATCHER), *args], cwd=ROOT, text=True, capture_output=True)

    def test_check_refuses_a_game_file_past_259_characters(self):
        output = Path("C:/" + "d" * 230)
        patcher.check_game_path_lengths(output, {"Images/a.png"})        # 3 + 230 + 13 = 246: fine
        with self.assertRaisesRegex(patcher.PatchError, "too deep for Windows") as caught:
            patcher.check_game_path_lengths(output, {"Images/a.png", "Images/" + "n" * 30 + ".png"})
        self.assertIn("Nothing was changed", str(caught.exception))

    @unittest.skipUnless(os.name == "nt", "Windows MAX_PATH behaviour")
    def test_long_path_adds_the_prefix_only_when_needed(self):
        short = Path("C:/Games/VF2")
        self.assertEqual(patcher.long_path(short), short)
        self.assertTrue(str(patcher.long_path(short, force=True)).startswith("\\\\?\\C:\\"))
        long = Path("C:/" + "d" * 250)
        self.assertTrue(str(patcher.long_path(long)).startswith("\\\\?\\C:\\"))
        self.assertEqual(patcher.plain_path(patcher.long_path(long)), long)
        unc = Path("\\\\server\\share\\" + "d" * 250)
        self.assertTrue(str(patcher.long_path(unc)).startswith("\\\\?\\UNC\\server\\share\\"))
        self.assertEqual(patcher.plain_path(patcher.long_path(unc)), unc)

    @unittest.skipUnless(os.name == "nt", "Windows MAX_PATH behaviour")
    def test_deep_patcher_and_deep_output_folder_apply_and_back_up(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td).resolve()   # CI's TEMP is an 8.3 short name; the patcher resolves it
            # The manifest and payload sit past MAX_PATH (a deep OneDrive\Desktop-style unzip) ...
            bundle = self.deep(tmp / "OneDrive" / "Desktop", 245) / FOLDER
            self.assertGreater(len(str(bundle / "payload" / "mod.exe")), 260)
            exe, manifest = self.make_install(tmp, bundle)
            # ... and the output folder is as deep as still lets the game open every file it writes,
            # which puts the backups (.vf2_patch_backups\<run>\files\...) well past MAX_PATH.
            output = self.deep(tmp / "Games", 259 - len(self.EXE_NAME) - 1)
            self.assertEqual(len(str(output / self.EXE_NAME)), 259)
            result = self.run_patcher("apply", "--exe", str(exe), "--manifest", str(manifest),
                                      "--output-dir", str(output))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            out = patcher.long_path(output, force=True)
            self.assertEqual((out / self.EXE_NAME).read_bytes(), b"modded exe")
            self.assertEqual((out / "Images" / "a.png").read_bytes(), b"modded a")
            backups = [p for p in (out / ".vf2_patch_backups").rglob("*") if p.is_file()]
            self.assertTrue(any(len(str(patcher.plain_path(p))) > 260 for p in backups))
            # A second run refreshes the deep output folder (deletes and re-copies) and backs it up again.
            result = self.run_patcher("apply", "--exe", str(exe), "--manifest", str(manifest),
                                      "--output-dir", str(output))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((out / "Images" / "a.png").read_bytes(), b"modded a")

    @unittest.skipUnless(os.name == "nt", "Windows MAX_PATH behaviour")
    def test_too_deep_output_folder_is_refused_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td).resolve()   # CI's TEMP is an 8.3 short name; the patcher resolves it
            bundle = tmp / "bundle" / FOLDER
            exe, manifest = self.make_install(tmp, bundle)
            output = self.deep(tmp / "Games", 259 - len(self.EXE_NAME))     # the EXE would be 260
            for dry in ((), ("--dry-run",)):
                with self.subTest(dry_run=bool(dry)):
                    result = self.run_patcher("apply", "--exe", str(exe), "--manifest", str(manifest),
                                              "--output-dir", str(output), *dry)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("too deep for Windows", result.stderr)
                    self.assertFalse(patcher.long_path(output, force=True).exists())


if __name__ == "__main__":
    unittest.main()
