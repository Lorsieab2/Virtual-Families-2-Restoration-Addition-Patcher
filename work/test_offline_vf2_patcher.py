#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import offline_vf2_patcher as patcher_mod  # noqa: E402

PATCHER = ROOT / "work" / "offline_vf2_patcher.py"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def minimal_pe_bytes(overlay=b"", section_delta=0):
    data = bytearray(0x400)
    data[:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    pe = 0x80
    data[pe:pe + 4] = b"PE\0\0"
    coff = pe + 4
    data[coff:coff + 20] = (
        (0x14C).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (0x12345678).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (0xE0).to_bytes(2, "little")
        + (0x103).to_bytes(2, "little")
    )
    opt = coff + 20
    data[opt:opt + 2] = (0x10B).to_bytes(2, "little")
    data[opt + 16:opt + 20] = (0x1000).to_bytes(4, "little")
    data[opt + 28:opt + 32] = (0x400000).to_bytes(4, "little")
    data[opt + 32:opt + 36] = (0x1000).to_bytes(4, "little")
    data[opt + 36:opt + 40] = (0x200).to_bytes(4, "little")
    data[opt + 56:opt + 60] = (0x2000).to_bytes(4, "little")
    data[opt + 68:opt + 70] = (2).to_bytes(2, "little")
    sect = opt + 0xE0
    data[sect:sect + 8] = b".text\0\0\0"
    data[sect + 8:sect + 16] = (0x200).to_bytes(4, "little") + (0x1000).to_bytes(4, "little")
    data[sect + 16:sect + 24] = (0x200).to_bytes(4, "little") + (0x200).to_bytes(4, "little")
    data[sect + 36:sect + 40] = (0x60000020).to_bytes(4, "little")
    data[0x200:0x400] = bytes(((index + section_delta) % 251 for index in range(0x200)))
    return bytes(data) + overlay


class OfflineVF2PatcherTests(unittest.TestCase):
    def run_patcher(self, *args, expect=0):
        result = subprocess.run(
            [sys.executable, str(PATCHER), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != expect:
            self.fail(
                f"Expected exit {expect}, got {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        return result

    def write_manifest(self, path, game_file, original, expected="03 04", replacement="AA BB"):
        manifest = {
            "manifest_version": 1,
            "name": "unit test manifest",
            "target_files": [
                {
                    "path": game_file.name,
                    "sha256": sha256_bytes(original),
                    "size": len(original),
                }
            ],
            "patches": [
                {
                    "file_path": game_file.name,
                    "offset": "0x2",
                    "expected_original_bytes": expected,
                    "replacement_bytes": replacement,
                    "note": "unit test byte swap",
                }
            ],
        }
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def test_apply_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "patch.json"
            backup = tmp_path / "backup"
            self.write_manifest(manifest, game_file, original)

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertIn("Validating byte patch 1/1", result.stdout)
            self.assertIn("Applying byte patch 1/1", result.stdout)
            self.assertEqual(game_file.read_bytes(), bytes([1, 2, 0xAA, 0xBB, 5, 6]))
            self.assertTrue((backup / "vf2_patch_backup_manifest.json").is_file())
            self.assertTrue((backup / "patch_log.json").is_file())
            log = json.loads((backup / "patch_log.json").read_text(encoding="utf-8"))
            self.assertTrue(any(row["phase"] == "validate" and row["status"] == "success" for row in log["process_log"]))
            self.assertTrue(any(row["phase"] == "apply" and row["status"] == "success" for row in log["process_log"]))

            self.run_patcher("restore", "--backup-dir", str(backup))
            self.assertEqual(game_file.read_bytes(), original)
            self.assertTrue((backup / "restore_log.json").is_file())

    def test_manifest_output_folder_creates_modded_sibling_and_preserves_vanilla(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            patched = b"patched executable"
            game_file.write_bytes(original)
            payload = tmp_path / "payload" / "Virtual Families 2 - Modded BTest.exe"
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_replacement.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "separate output folder unit test",
                        "output": {
                            "default_folder_name": "VF2-BTest-Modded",
                            "default_exe_name": "Virtual Families 2 - Modded BTest.exe",
                        },
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "output_file_path": "Virtual Families 2 - Modded BTest.exe",
                                "source_path": "payload/Virtual Families 2 - Modded BTest.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(original),
                                "expected_target_size": len(original),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "create verified modded exe in separate folder",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher("apply", "--exe", str(game_file), "--manifest", str(manifest))

            output_dir = tmp_path / "VF2-BTest-Modded"
            self.assertEqual(game_file.read_bytes(), original)
            self.assertFalse((output_dir / game_file.name).exists())
            self.assertEqual((output_dir / "Virtual Families 2 - Modded BTest.exe").read_bytes(), patched)
            backups = list((output_dir / ".vf2_patch_backups").glob("*/vf2_patch_backup_manifest.json"))
            self.assertEqual(len(backups), 1)
            backup_manifest = json.loads(backups[0].read_text(encoding="utf-8"))
            self.assertEqual(Path(backup_manifest["game_dir"]), output_dir.resolve())
            self.assertEqual(Path(backup_manifest["source_game_dir"]), game_dir.resolve())
            log = json.loads((backups[0].parent / "patch_log.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(log["output_dir"]), output_dir.resolve())
            self.assertEqual(log["modded_exe_name"], "Virtual Families 2 - Modded BTest.exe")
            self.assertTrue(log["modded_save_dir"].endswith(str(Path("LDW") / "Virtual Families 2 - Modded BTest")))

    def test_refresh_rewrites_exe_that_was_up_to_date_before_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            patched = b"patched executable"
            game_file.write_bytes(original)

            output_dir = tmp_path / "VF2-BTest-Modded"
            output_dir.mkdir()
            output_exe = output_dir / "Virtual Families 2 - Modded BTest.exe"
            output_exe.write_bytes(patched)

            payload = tmp_path / "payload" / output_exe.name
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_replacement.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "refresh up-to-date exe unit test",
                        "output": {
                            "default_folder_name": output_dir.name,
                            "default_exe_name": output_exe.name,
                        },
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "output_file_path": output_exe.name,
                                "source_path": "payload/Virtual Families 2 - Modded BTest.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(original),
                                "expected_target_size": len(original),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "rewrite modded exe after output-folder refresh",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--output-dir",
                str(output_dir),
                "--manifest",
                str(manifest),
            )

            self.assertIn("Applying asset patch", result.stdout)
            self.assertFalse((output_dir / game_file.name).exists())
            self.assertEqual(output_exe.read_bytes(), patched)
            backups = list((output_dir / ".vf2_patch_backups").glob("*/patch_log.json"))
            self.assertEqual(len(backups), 1)
            log = json.loads(backups[0].read_text(encoding="utf-8"))
            self.assertTrue(
                any(row.get("action") == "up_to_date_recheck_failed" for row in log["process_log"])
            )
            self.assertEqual(log["modded_exe_name"], output_exe.name)

    def test_dry_run_accepts_renamed_valid_pe_structure_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            reference = tmp_path / "reference.exe"
            reference.write_bytes(minimal_pe_bytes())
            renamed_exe = game_dir / "Renamed VF2 Website Build.exe"
            renamed_exe.write_bytes(minimal_pe_bytes(section_delta=17))
            manifest = tmp_path / "structure_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "renamed PE target unit test",
                        "output": {"default_folder_name": "VF2-BTest-Modded"},
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "pe_structures": [patcher_mod.pe_structure_fingerprint(reference)],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--dry-run",
            )

            self.assertIn("Dry run complete", result.stdout)
            log = json.loads((tmp_path / "patch_dry_run_log.json").read_text(encoding="utf-8"))
            self.assertEqual(log["target_checks"][0]["file_path"], renamed_exe.name)
            self.assertTrue(log["target_checks"][0]["discovered_by_structure"])

    def test_exe_replacement_accepts_renamed_valid_pe_structure_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            reference = tmp_path / "reference.exe"
            reference.write_bytes(minimal_pe_bytes())
            renamed_exe = game_dir / "Renamed VF2 Website Build.exe"
            renamed_exe.write_bytes(minimal_pe_bytes(section_delta=29))
            payload = tmp_path / "payload" / "Virtual Families 2 - Modded BTest.exe"
            payload.parent.mkdir()
            patched = b"patched executable payload"
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_replacement_structure_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "renamed PE replacement unit test",
                        "output": {
                            "default_folder_name": "VF2-BTest-Modded",
                            "default_exe_name": payload.name,
                        },
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "pe_structures": [patcher_mod.pe_structure_fingerprint(reference)],
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Virtual Families 2.exe",
                                "output_file_path": payload.name,
                                "source_path": str(payload.relative_to(tmp_path)).replace("\\", "/"),
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_pe_structures": [patcher_mod.pe_structure_fingerprint(reference)],
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
            )

            output_dir = tmp_path / "VF2-BTest-Modded"
            self.assertIn("Patched files successfully", result.stdout)
            self.assertEqual((output_dir / payload.name).read_bytes(), patched)
            self.assertFalse((output_dir / renamed_exe.name).exists())

    def test_asset_patch_allow_missing_target_creates_additive_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            game_exe = game_dir / "Virtual Families 2.exe"
            game_exe.write_bytes(minimal_pe_bytes(section_delta=12))
            payload = tmp_path / "payload" / "Assets" / "Balloons_birthday.png.fmap"
            payload.parent.mkdir(parents=True)
            payload_bytes = b"new additive fmap"
            payload.write_bytes(payload_bytes)
            manifest = tmp_path / "allow_missing_asset.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "pe_structures": [patcher_mod.pe_structure_fingerprint(game_exe)],
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Assets/Balloons_birthday.png.fmap",
                                "source_path": "payload/Assets/Balloons_birthday.png.fmap",
                                "source_sha256": sha256_bytes(payload_bytes),
                                "source_size": len(payload_bytes),
                                "expected_target_sha256": "0" * 64,
                                "expected_target_size": 123,
                                "allow_missing_target": True,
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher("apply", "--game-dir", str(game_dir), "--manifest", str(manifest))

            self.assertIn("Patched files successfully", result.stdout)
            self.assertEqual((game_dir / "Assets" / "Balloons_birthday.png.fmap").read_bytes(), payload_bytes)

    def test_byte_patch_output_folder_renames_modded_exe_for_save_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "byte_patch_output.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "byte patch renamed output unit test",
                        "output": {
                            "default_folder_name": "VF2-BByte-Modded",
                            "default_exe_name": "Virtual Families 2 - Modded BByte.exe",
                        },
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "patches": [
                            {
                                "file_path": game_file.name,
                                "offset": "0x2",
                                "expected_original_bytes": "03 04",
                                "replacement_bytes": "AA BB",
                                "note": "unit test byte swap",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher("apply", "--exe", str(game_file), "--manifest", str(manifest))

            output_dir = tmp_path / "VF2-BByte-Modded"
            modded_exe = output_dir / "Virtual Families 2 - Modded BByte.exe"
            self.assertEqual(game_file.read_bytes(), original)
            self.assertFalse((output_dir / game_file.name).exists())
            self.assertEqual(modded_exe.read_bytes(), bytes([1, 2, 0xAA, 0xBB, 5, 6]))
            log_path = next((output_dir / ".vf2_patch_backups").glob("*/patch_log.json"))
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(log["modded_exe_name"], "Virtual Families 2 - Modded BByte.exe")
            self.assertTrue(log["modded_save_dir"].endswith(str(Path("LDW") / "Virtual Families 2 - Modded BByte")))
            self.assertEqual(log["patched_files"][0]["output_file_path"], "Virtual Families 2 - Modded BByte.exe")

    def test_apply_with_exe_path_replaces_verified_original_and_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            patched = b"patched executable"
            game_file.write_bytes(original)
            payload = tmp_path / "payload" / "Virtual Families 2.exe"
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_replacement.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "exe replacement unit test",
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "source_path": "payload/Virtual Families 2.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(original),
                                "expected_target_size": len(original),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "replace verified vanilla exe",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--exe",
                str(game_file),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertEqual(game_file.read_bytes(), patched)
            backup_manifest = json.loads((backup / "vf2_patch_backup_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(backup_manifest["files"][0]["file_path"], game_file.name)
            self.assertEqual(backup_manifest["files"][0]["sha256"], sha256_bytes(original))

            self.run_patcher("restore", "--backup-dir", str(backup))
            self.assertEqual(game_file.read_bytes(), original)

    def test_apply_with_exe_path_accepts_any_exe_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_file = tmp_path / "VF2.exe"
            game_file.write_bytes(b"vanilla")
            manifest = tmp_path / "patch.json"
            backup = tmp_path / "backup"
            self.write_manifest(manifest, game_file, b"vanilla", expected="6e", replacement="70")

            self.run_patcher(
                "apply",
                "--exe",
                str(game_file),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )

            self.assertEqual(game_file.read_bytes(), b"vapilla")

    def test_exe_replacement_accepts_matching_pe_structure_when_hash_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            expected_original = minimal_pe_bytes()
            actual_original = minimal_pe_bytes(b"overlay that changes whole-file hash")
            patched = b"patched executable"
            game_file.write_bytes(actual_original)
            structure_source = tmp_path / "expected.exe"
            structure_source.write_bytes(expected_original)
            payload = tmp_path / "payload" / "Virtual Families 2.exe"
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_structure_replacement.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "exe structure replacement unit test",
                        "settings": [{"id": "core_executable", "label": "Patch game executable", "default": True}],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(expected_original),
                                "size": len(expected_original),
                                "pe_structure": patcher_mod.pe_structure_fingerprint(structure_source),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "source_path": "payload/Virtual Families 2.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(expected_original),
                                "expected_target_pe_structure": patcher_mod.pe_structure_fingerprint(structure_source),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "replace structurally matched exe",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher("apply", "--exe", str(game_file), "--manifest", str(manifest), "--backup-dir", str(backup))

            self.assertEqual(game_file.read_bytes(), patched)
            log = json.loads((backup / "patch_log.json").read_text(encoding="utf-8"))
            self.assertEqual(log["target_checks"][0]["matched_by"], "pe_structure")
            self.assertTrue(log["asset_patches"][0]["target_structure_matched"])

    def test_exe_replacement_accepts_matching_pe_layout_when_section_hash_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            expected_original = minimal_pe_bytes(section_delta=0)
            actual_original = minimal_pe_bytes(section_delta=7)
            patched = b"patched executable"
            game_file.write_bytes(actual_original)
            structure_source = tmp_path / "expected.exe"
            structure_source.write_bytes(expected_original)
            payload = tmp_path / "payload" / "Virtual Families 2.exe"
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_layout_replacement.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "exe layout replacement unit test",
                        "settings": [{"id": "core_executable", "label": "Patch game executable", "default": True}],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(expected_original),
                                "size": len(expected_original),
                                "pe_structure": patcher_mod.pe_structure_fingerprint(structure_source),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "source_path": "payload/Virtual Families 2.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(expected_original),
                                "expected_target_pe_structure": patcher_mod.pe_structure_fingerprint(structure_source),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "replace layout-matched exe",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher("apply", "--exe", str(game_file), "--manifest", str(manifest), "--backup-dir", str(backup))

            self.assertEqual(game_file.read_bytes(), patched)
            log = json.loads((backup / "patch_log.json").read_text(encoding="utf-8"))
            self.assertEqual(log["target_checks"][0]["matched_by"], "pe_structure")
            self.assertTrue(log["asset_patches"][0]["target_structure_matched"])

    def test_target_file_can_find_vf2_exe_by_structure_when_name_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "VF2WebsiteBuild.exe"
            original = minimal_pe_bytes(section_delta=3)
            game_file.write_bytes(original)
            structure_source = tmp_path / "expected.exe"
            structure_source.write_bytes(original)
            manifest = tmp_path / "structure_named_exe.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "structure named exe unit test",
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "pe_structures": [patcher_mod.pe_structure_fingerprint(structure_source)],
                            }
                        ],
                        "patches": [
                            {
                                "file_path": game_file.name,
                                "offset": "0x0",
                                "expected_original_bytes": "4d5a",
                                "replacement_bytes": "4d5a",
                                "note": "dry-run identity patch",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher("apply", "--game-dir", str(game_dir), "--manifest", str(manifest), "--dry-run")

            self.assertIn("Dry run complete", result.stdout)

    def test_runtime_requirements_validate_game_payload_before_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            (game_dir / "Images").mkdir()
            (game_dir / "Images" / "loading.jpg").write_bytes(b"image")
            (game_dir / "Sounds").mkdir()
            (game_dir / "Sounds" / "sound00.wav").write_bytes(b"sound")
            (game_dir / "ldw.ini").write_text("ok", encoding="ascii")
            manifest = tmp_path / "runtime_patch.json"
            backup = tmp_path / "backup"
            self.write_manifest(manifest, game_file, original)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["runtime_requirements"] = {
                "required_files": ["ldw.ini", "Images/loading.jpg"],
                "required_dirs": [{"path": "Images", "min_files": 1}, {"path": "Sounds", "min_files": 1}],
            }
            manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            log = json.loads((backup / "patch_log.json").read_text(encoding="utf-8"))
            self.assertEqual(len(log["runtime_checks"]), 4)

    def test_runtime_requirements_refuse_partial_images_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "runtime_patch.json"
            self.write_manifest(manifest, game_file, original)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["runtime_requirements"] = {
                "required_files": ["Images/loading.jpg"],
            }
            manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn("No valid Virtual Families 2 Installation detected!", result.stderr)
            self.assertIn("required runtime file is missing: Images", result.stderr)
            self.assertIn("loading.jpg", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)

    def test_exact_install_validation_refuses_unexpected_top_level_entries_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            (game_dir / "Images").mkdir()
            (game_dir / "unexpected.tmp").write_text("not official", encoding="ascii")
            manifest = tmp_path / "runtime_patch.json"
            output_dir = tmp_path / "modded"
            log_path = tmp_path / "patch_log.json"
            self.write_manifest(manifest, game_file, original)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["runtime_requirements"] = {
                "exact_top_level_entries": ["Images", "Virtual Families 2.exe"],
                "invalid_install_message": "No valid Virtual Families 2 Installation detected! Are you sure you downloaded it from the official website?\n\nLinks:\nhttp://www.ldw.com/\nhttp://www.virtualfamilies.com/index.php",
            }
            manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--output-dir",
                str(output_dir),
                expect=2,
            )

            self.assertIn("No valid Virtual Families 2 Installation detected!", result.stderr)
            self.assertIn("unexpected top-level entries: unexpected.tmp", result.stderr)
            self.assertFalse(output_dir.exists())
            self.assertFalse((game_dir / "patch_error_log.json").exists())
            self.assertTrue((manifest.parent / "patch_error_log.json").is_file())

    def test_exact_install_validation_allows_vf2_exe_when_exact_entries_are_name_agnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            (game_dir / "Images").mkdir()
            manifest = tmp_path / "runtime_patch.json"
            output_dir = tmp_path / "modded"
            log_path = tmp_path / "patch_log.json"
            self.write_manifest(manifest, game_file, original)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["runtime_requirements"] = {
                "exact_top_level_entries": ["Images"],
                "invalid_install_message": "No valid Virtual Families 2 Installation detected! Are you sure you downloaded it from the official website?\n\nLinks:\nhttp://www.ldw.com/\nhttp://www.virtualfamilies.com/index.php",
            }
            manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--output-dir",
                str(output_dir),
                "--log",
                str(log_path),
            )

            self.assertIn("Patched files successfully", result.stdout)
            self.assertTrue((output_dir / "Virtual Families 2.exe").is_file())
            log = json.loads(log_path.read_text(encoding="utf-8"))
            exact_checks = [row for row in log["runtime_checks"] if row["kind"] == "exact_top_level_entries"]
            self.assertEqual(exact_checks[0]["ignored_exe_names"], ["Virtual Families 2.exe"])

    def test_asset_patch_creates_private_tv_strip_and_restore_removes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            source = tmp_path / "payload" / "Images" / "VF3LargeFlatScreenTVAnim.png"
            source.parent.mkdir(parents=True)
            source_data = b"scaled private vf3 tv strip"
            source.write_bytes(source_data)
            target = game_dir / "Images" / "VF3LargeFlatScreenTVAnim.png"
            manifest = tmp_path / "asset_patch.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "asset patch unit test",
                        "settings": [
                            {
                                "id": "mobile_furniture",
                                "label": "Add additional mobile-exclusive furniture",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/VF3LargeFlatScreenTVAnim.png",
                                "source_path": "payload/Images/VF3LargeFlatScreenTVAnim.png",
                                "source_sha256": sha256_bytes(source_data),
                                "source_size": len(source_data),
                                "requires": ["mobile_furniture"],
                                "note": "B64 private VF3 TV animation strip",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertIn("1 active asset patch record", result.stdout)
            self.assertEqual(target.read_bytes(), source_data)
            backup_manifest = json.loads((backup / "vf2_patch_backup_manifest.json").read_text(encoding="utf-8"))
            self.assertIn(
                {"file_path": str(Path("Images") / "VF3LargeFlatScreenTVAnim.png"), "existed": False},
                backup_manifest["files"],
            )

            self.run_patcher("restore", "--backup-dir", str(backup))
            self.assertFalse(target.exists())

    def test_vf3_tv_animation_setting_controls_all_private_strips(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            strip_names = [
                "VF3LargeFlatScreenTVAnim.png",
                "VF3LargeFlatScreenTVAnimEast.png",
                "VF3SmallFlatScreenTVAnim.png",
                "VF3SmallFlatScreenTVAnimEast.png",
                "FathersFavoriteTVAnim.png",
                "FathersFavoriteTVAnimEast.png",
            ]
            payload_dir = tmp_path / "payload" / "Images"
            payload_dir.mkdir(parents=True)
            asset_patches = []
            for index, name in enumerate(strip_names):
                source_data = f"scaled private strip {index}".encode("ascii")
                source = payload_dir / name
                source.write_bytes(source_data)
                asset_patches.append(
                    {
                        "file_path": str(Path("Images") / name),
                        "source_path": str(Path("payload") / "Images" / name),
                        "source_sha256": sha256_bytes(source_data),
                        "source_size": len(source_data),
                        "requires": ["vf3_tv_animation_graphics"],
                        "note": f"B65 private VF3 TV animation strip: {name}",
                    }
                )
            manifest = tmp_path / "vf3_tv_asset_patch.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "vf3 tv animation asset unit test",
                        "settings": [
                            {
                                "id": "vf3_tv_animation_graphics",
                                "label": "Fix VF3 TV animation graphics",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": asset_patches,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertIn("6 active asset patch record", result.stdout)
            for index, name in enumerate(strip_names):
                self.assertEqual((game_dir / "Images" / name).read_bytes(), f"scaled private strip {index}".encode("ascii"))

            self.run_patcher("restore", "--backup-dir", str(backup))
            for name in strip_names:
                self.assertFalse((game_dir / "Images" / name).exists())

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--disable",
                "vf3_tv_animation_graphics",
                expect=2,
            )
            self.assertIn("No active patches remain", result.stderr)

    def test_outfit_sprite_sheet_asset_patches_copy_into_game_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            sheet_names = [
                "female_bodies00.png",
                "female_actions00.png",
                "female_sit00.png",
                "male_bodies00.png",
                "male_actions00.png",
                "male_sit00.png",
            ]
            payload_dir = tmp_path / "payload" / "Images"
            payload_dir.mkdir(parents=True)
            asset_patches = []
            for index, name in enumerate(sheet_names):
                source_data = f"copied stock villager sheet {index}".encode("ascii")
                (payload_dir / name).write_bytes(source_data)
                asset_patches.append(
                    {
                        "file_path": str(Path("Images") / name),
                        "source_path": str(Path("payload") / "Images" / name),
                        "source_sha256": sha256_bytes(source_data),
                        "source_size": len(source_data),
                        "requires": ["outfit_store_expansion"],
                        "note": f"Copy stock villager sprite sheet into the game Images folder: {name}",
                    }
                )
            manifest = tmp_path / "outfit_sheets_asset_patch.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "outfit sheet asset unit test",
                        "settings": [
                            {
                                "id": "outfit_store_expansion",
                                "label": "Add expanded Outfit store",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": asset_patches,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertIn("6 active asset patch record", result.stdout)
            for index, name in enumerate(sheet_names):
                expected = f"copied stock villager sheet {index}".encode("ascii")
                self.assertEqual((game_dir / "Images" / name).read_bytes(), expected)

            self.run_patcher("restore", "--backup-dir", str(backup))
            for name in sheet_names:
                self.assertFalse((game_dir / "Images" / name).exists())

    def test_asset_patch_replaces_expected_file_and_restore_recovers_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            source = tmp_path / "payload" / "Images" / "FathersFavoriteTVAnim.png"
            source.parent.mkdir(parents=True)
            source_data = b"new scaled father favorite strip"
            source.write_bytes(source_data)
            target = game_dir / "Images" / "FathersFavoriteTVAnim.png"
            target.parent.mkdir(parents=True)
            old_target_data = b"old misaligned strip"
            target.write_bytes(old_target_data)
            manifest = tmp_path / "asset_patch.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "asset replace unit test",
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/FathersFavoriteTVAnim.png",
                                "source_path": "payload/Images/FathersFavoriteTVAnim.png",
                                "source_sha256": sha256_bytes(source_data),
                                "expected_target_sha256": sha256_bytes(old_target_data),
                                "note": "Replace an expected private strip with the scaled B64 strip.",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertEqual(target.read_bytes(), source_data)

            self.run_patcher("restore", "--backup-dir", str(backup))
            self.assertEqual(target.read_bytes(), old_target_data)

    def test_asset_patch_refuses_source_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            source = tmp_path / "payload" / "Images" / "VF3SmallFlatScreenTVAnim.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"actual strip data")
            manifest = tmp_path / "asset_patch.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "asset hash mismatch unit test",
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/VF3SmallFlatScreenTVAnim.png",
                                "source_path": "payload/Images/VF3SmallFlatScreenTVAnim.png",
                                "source_sha256": sha256_bytes(b"different data"),
                                "note": "Refuse corrupted patch payload.",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn("SHA-256 mismatch for asset source", result.stderr)
            self.assertFalse((game_dir / "Images" / "VF3SmallFlatScreenTVAnim.png").exists())

    def test_output_only_reconfiguration_enables_and_restores_checked_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            modded_dir = tmp_path / "VF2-BUnit-Modded"
            (modded_dir / ".vf2_patch_backups").mkdir(parents=True)
            (modded_dir / "Images" / "Upgrades").mkdir(parents=True)
            (modded_dir / "Virtual Families 2 - Modded BUnit.exe").write_bytes(b"modded exe")
            upgrade = modded_dir / "Images" / "Upgrades" / "toolwall.png"
            upgrade.write_bytes(b"original upgrade")

            payload = tmp_path / "payload"
            invisible = payload / "OptionalVisualMods" / "Invisible Upgrades" / "toolwall.png"
            original = payload / "Original Virtual Families 2 Assets" / "Upgrades Original Graphics" / "toolwall.png"
            invisible.parent.mkdir(parents=True)
            original.parent.mkdir(parents=True)
            invisible.write_bytes(b"invisible upgrade")
            original.write_bytes(b"original upgrade")

            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "output-only reconfigure unit test",
                        "output": {
                            "default_folder_name": "VF2-BUnit-Modded",
                            "default_exe_name": "Virtual Families 2 - Modded BUnit.exe",
                        },
                        "settings": [
                            {
                                "id": "invisible_upgrades_graphics",
                                "label": "Invisible Upgrades Graphics",
                                "default": False,
                                "category": "optional",
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/Upgrades/toolwall.png",
                                "source_path": "payload/OptionalVisualMods/Invisible Upgrades/toolwall.png",
                                "source_sha256": sha256_bytes(b"invisible upgrade"),
                                "source_size": len(b"invisible upgrade"),
                                "restore_source_path": "payload/Original Virtual Families 2 Assets/Upgrades Original Graphics/toolwall.png",
                                "restore_source_sha256": sha256_bytes(b"original upgrade"),
                                "restore_source_size": len(b"original upgrade"),
                                "overwrite_existing": True,
                                "requires": ["invisible_upgrades_graphics"],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--output-dir",
                str(modded_dir),
                "--manifest",
                str(manifest),
                "--enable",
                "invisible_upgrades_graphics",
            )
            self.assertEqual(upgrade.read_bytes(), b"invisible upgrade")

            self.run_patcher(
                "apply",
                "--output-dir",
                str(modded_dir),
                "--manifest",
                str(manifest),
            )
            self.assertEqual(upgrade.read_bytes(), b"original upgrade")
            log_path = sorted((modded_dir / ".vf2_patch_backups").glob("*/patch_log.json"))[-1]
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(log["mode"], "existing_modded_output")
            self.assertTrue(any(row["action"] == "replace" for row in log["asset_files"]))

    def test_refuses_expected_byte_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "patch.json"
            backup = tmp_path / "backup"
            failure_log = tmp_path / "failure.json"
            self.write_manifest(manifest, game_file, original, expected="99 99")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
                "--log",
                str(failure_log),
                expect=2,
            )
            self.assertIn("expected bytes do not match", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)
            self.assertFalse(backup.exists())
            self.assertTrue(failure_log.is_file())
            log = json.loads(failure_log.read_text(encoding="utf-8"))
            self.assertEqual(log["status"], "failure")
            self.assertTrue(any(row["status"] == "error" and row["kind"] == "byte_patch" for row in log["process_log"]))

    def test_refuses_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "patch.json"
            self.write_manifest(manifest, game_file, b"wrong original bytes")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn("SHA-256 mismatch", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)

    def test_setting_defaults_and_explicit_enable(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            optional_file = game_dir / "optional-holiday.dat"
            original = bytes([1, 2, 3, 4, 5, 6])
            optional_original = b"holiday"
            game_file.write_bytes(original)
            manifest = tmp_path / "settings_patch.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "settings unit test",
                        "settings": [
                            {
                                "id": "holiday_furniture",
                                "label": "Add Holiday furniture",
                                "description": "Adds mobile holiday furniture.",
                                "default": False,
                            },
                            {
                                "id": "mobile_furniture",
                                "label": "Add additional mobile-exclusive furniture",
                                "default": True,
                            },
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            },
                            {
                                "path": "optional-holiday.dat",
                                "sha256": sha256_bytes(optional_original),
                                "requires": ["holiday_furniture"],
                            },
                        ],
                        "patches": [
                            {
                                "file_path": game_file.name,
                                "offset": "0x1",
                                "expected_original_bytes": "02",
                                "replacement_bytes": "20",
                                "requires": ["mobile_furniture"],
                                "note": "default-on mobile furniture patch",
                            },
                            {
                                "file_path": game_file.name,
                                "offset": "0x3",
                                "expected_original_bytes": "04",
                                "replacement_bytes": "40",
                                "setting": "holiday_furniture",
                                "note": "optional holiday furniture patch",
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            settings = self.run_patcher("settings", "--manifest", str(manifest))
            self.assertIn("holiday_furniture [default off]", settings.stdout)
            self.assertIn("mobile_furniture [default on]", settings.stdout)

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(tmp_path / "backup-default"),
            )
            self.assertEqual(game_file.read_bytes(), bytes([1, 0x20, 3, 4, 5, 6]))

            game_file.write_bytes(original)
            optional_file.write_bytes(optional_original)
            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(tmp_path / "backup-enabled"),
                "--enable",
                "holiday_furniture",
            )
            self.assertEqual(game_file.read_bytes(), bytes([1, 0x20, 3, 0x40, 5, 6]))

    def test_disable_all_requires_explicit_enabled_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4])
            game_file.write_bytes(original)
            manifest = tmp_path / "settings_patch.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "settings": {
                            "holiday_outfits": {
                                "label": "Add Holiday outfits",
                                "default": True,
                            }
                        },
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                            }
                        ],
                        "patches": [
                            {
                                "file_path": game_file.name,
                                "offset": 1,
                                "expected_original_bytes": "02",
                                "replacement_bytes": "99",
                                "requires": ["holiday_outfits"],
                                "note": "holiday outfit toggle patch",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--disable-all",
                expect=2,
            )
            self.assertIn("No active patches", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--disable-all",
                "--enable",
                "holiday_outfits",
                "--backup-dir",
                str(tmp_path / "backup"),
            )
            self.assertEqual(game_file.read_bytes(), bytes([1, 0x99, 3, 4]))


if __name__ == "__main__":
    unittest.main()
