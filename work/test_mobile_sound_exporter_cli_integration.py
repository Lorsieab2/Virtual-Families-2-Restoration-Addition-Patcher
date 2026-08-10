#!/usr/bin/env python3
"""End-to-end static coverage for the exported mobile sound toggle."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "work" / "export_offline_patch_bundle.py"
PATCHER = ROOT / "work" / "offline_vf2_patcher.py"
sys.path.insert(0, str(ROOT / "work"))

import export_offline_patch_bundle as exporter
from test_export_offline_patch_bundle import minimal_pe_bytes


class MobileSoundExporterCliIntegrationTests(unittest.TestCase):
    def run_exporter(self, *args: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(EXPORTER), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"exporter failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
        return result

    def run_patcher(self, *args: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(PATCHER), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"patcher failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
        return result

    def test_exported_manifest_round_trips_all_67_sounds_and_blocks_unverified_apply(self):
        routes = (
            ("beaker.wav", "beaker.ogg"),
            ("Child3.wav", "Child3.ogg"),
            ("Child7.wav", "Child7.ogg"),
            ("Child8.wav", "Child8.ogg"),
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = root / "build"
            base = root / "base"
            bundle = root / "bundle"
            game = root / "game"
            build.mkdir()
            base.mkdir()
            game.mkdir()

            vanilla_data = bytearray(minimal_pe_bytes())
            route_offsets = (0x220, 0x240, 0x260, 0x280)
            for offset, (pc_name, _mobile_name) in zip(route_offsets, routes):
                literal = pc_name.encode("ascii")
                vanilla_data[offset : offset + len(literal)] = literal
            original_exe = bytes(vanilla_data)
            patched_exe = build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
            patched_exe.write_bytes(original_exe)
            vanilla_exe = game / "Virtual Families 2.exe"
            vanilla_exe.write_bytes(original_exe)

            route_contract = [
                {
                    "pc_filename": pc_name,
                    "mobile_filename": mobile_name,
                    "object_offset": exporter.MOBILE_SOUND_ROUTE_PINS[pc_name][1],
                    "expected_bytes": pc_name.encode("ascii").hex(),
                    "replacement_bytes": mobile_name.encode("ascii").hex(),
                }
                for pc_name, mobile_name in routes
            ]
            (build / "patch-manifest.json").write_text(
                json.dumps({"MobileSoundAssets": {"routes": route_contract}}, indent=2),
                encoding="ascii",
            )

            base_sounds = base / "Sounds"
            game_sounds = game / "Sounds"
            base_sounds.mkdir()
            game_sounds.mkdir()
            original_sounds: dict[str, bytes] = {}
            for mobile_name, pc_name in exporter.MOBILE_SOUND_PC_FILENAMES.items():
                if mobile_name.lower() != pc_name.lower():
                    continue
                original = f"stock-{mobile_name}\0".encode("ascii")
                original_sounds[mobile_name] = original
                (base_sounds / mobile_name).write_bytes(original)
                (game_sounds / mobile_name).write_bytes(original)
            self.assertEqual(len(original_sounds), 63)

            # Satisfy the generated manifest's real install-shape checks.
            for directory, minimum in (("Images", 600), ("Assets", 200)):
                target = game / directory
                target.mkdir()
                for index in range(minimum):
                    (target / f"runtime-{index:04d}.dat").write_bytes(b"runtime")
            for index in range(300 - len(original_sounds)):
                (game_sounds / f"runtime-{index:04d}.dat").write_bytes(b"runtime")
            for filename in exporter.RUNTIME_REQUIRED_FILES:
                (game / filename).write_bytes(b"runtime")

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(bundle),
                "--vanilla-exe",
                str(vanilla_exe),
                "--include-exe-replacement",
                "--mobile-sound-assets-dir",
                str(exporter.MOBILE_SOUND_ASSET_SOURCE_DIR),
            )

            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["output"]["preserve_stock_exe_icon"])
            sound_requires = ["core_executable", "mobile_sound_assets"]
            sound_assets = [
                row
                for row in manifest["asset_patches"]
                if row.get("requires") == sound_requires
            ]
            self.assertEqual(len(sound_assets), 67)
            self.assertEqual(
                {Path(row["file_path"]).name for row in sound_assets},
                set(exporter.MOBILE_SOUND_ASSET_FILES),
            )
            self.assertEqual(sum("restore_source_path" in row for row in sound_assets), 63)
            remove_names = {
                Path(row["file_path"]).name
                for row in sound_assets
                if row.get("remove_when_disabled")
            }
            self.assertEqual(
                remove_names,
                {"beaker.ogg", "Child3.ogg", "Child7.ogg", "Child8.ogg"},
            )
            self.assertTrue(
                all((bundle / Path(row["source_path"])).is_file() for row in sound_assets)
            )

            route_records = [
                row
                for row in manifest["post_asset_patches"]
                if row.get("requires") == sound_requires
            ]
            self.assertEqual(len(route_records), 4)
            self.assertTrue(all(len(row["variants"]) == 1 for row in route_records))
            original_exe_hash = hashlib.sha256(original_exe).hexdigest()
            self.assertEqual(
                {row["variants"][0]["asset_sha256"] for row in route_records},
                {original_exe_hash},
            )
            expected_enabled = bytearray(original_exe)
            expected_route_pairs = set(routes)
            generated_route_pairs = set()
            for row in route_records:
                variant = row["variants"][0]
                expected = bytes.fromhex(variant["expected_asset_bytes"])
                replacement = bytes.fromhex(variant["replacement_bytes"])
                generated_route_pairs.add((expected.decode("ascii"), replacement.decode("ascii")))
                offset = int(variant["offset"], 16)
                self.assertEqual(expected, original_exe[offset : offset + len(expected)])
                expected_enabled[offset : offset + len(expected)] = replacement
            self.assertEqual(generated_route_pairs, expected_route_pairs)
            expected_enabled_hash = hashlib.sha256(bytes(expected_enabled)).hexdigest()
            self.assertEqual(
                {row["variants"][0]["result_asset_sha256"] for row in route_records},
                {expected_enabled_hash},
            )

            # The synthetic PE has no icon resources; keep every other generated
            # manifest contract intact while disabling only this fixture-specific
            # resource-copy step.
            manifest["output"]["preserve_stock_exe_icon"] = False
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            mobile_sound_setting = next(
                row for row in manifest["settings"] if row["id"] == "mobile_sound_assets"
            )
            self.assertEqual(mobile_sound_setting["readiness"]["status"], "pending")
            self.assertFalse(mobile_sound_setting["readiness"]["runtime_ready"])
            self.assertFalse(mobile_sound_setting["readiness"]["linked"])

            blocked = subprocess.run(
                [
                    sys.executable,
                    str(PATCHER),
                    "apply",
                    "--game-dir",
                    str(game),
                    "--output-dir",
                    str(root / "output"),
                    "--manifest",
                    str(manifest_path),
                    "--enable",
                    "mobile_sound_assets",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("Blocked setting(s) cannot be enabled", blocked.stderr)
            self.assertIn("mobile_sound_assets", blocked.stderr)
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
