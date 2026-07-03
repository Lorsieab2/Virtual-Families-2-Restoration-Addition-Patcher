#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "work" / "offline_vf2_patcher.py"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


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

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertEqual(game_file.read_bytes(), bytes([1, 2, 0xAA, 0xBB, 5, 6]))
            self.assertTrue((backup / "vf2_patch_backup_manifest.json").is_file())
            self.assertTrue((backup / "patch_log.json").is_file())

            self.run_patcher("restore", "--backup-dir", str(backup))
            self.assertEqual(game_file.read_bytes(), original)
            self.assertTrue((backup / "restore_log.json").is_file())

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
            self.assertIn("Required runtime file is missing: Images", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)

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
            self.write_manifest(manifest, game_file, original, expected="99 99")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
                expect=2,
            )
            self.assertIn("expected bytes do not match", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)
            self.assertFalse(backup.exists())

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
