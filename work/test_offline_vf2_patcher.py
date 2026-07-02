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


if __name__ == "__main__":
    unittest.main()
