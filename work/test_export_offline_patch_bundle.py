#!/usr/bin/env python3
import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "work" / "export_offline_patch_bundle.py"
PATCHER = ROOT / "work" / "offline_vf2_patcher.py"


def minimal_pe_bytes():
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
    data[0x200:0x400] = bytes((index % 251 for index in range(0x200)))
    return bytes(data)


class ExportOfflinePatchBundleTests(unittest.TestCase):
    def run_exporter(self, *args):
        result = subprocess.run(
            [sys.executable, str(EXPORTER), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            self.fail(f"exporter failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        return result

    def run_exporter_expect(self, *args, expect=0):
        result = subprocess.run(
            [sys.executable, str(EXPORTER), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != expect:
            self.fail(
                f"Expected exporter exit {expect}, got {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        return result

    def run_patcher(self, *args, expect=0):
        result = subprocess.run(
            [sys.executable, str(PATCHER), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != expect:
            self.fail(
                f"Expected patcher exit {expect}, got {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        return result

    def test_exports_changed_assets_with_feature_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            (base / "Images" / "Furniture").mkdir(parents=True)
            (base / "Images" / "Furniture" / "Unchanged.png").write_bytes(b"same")
            (build / "Images" / "Furniture").mkdir(parents=True)
            (build / "Images" / "Furniture" / "Unchanged.png").write_bytes(b"same")
            (build / "Images" / "Furniture" / "CandyCane.png").write_bytes(b"holiday")
            (build / "Images" / "Furniture" / "CouchNeonPurpleStd.png").write_bytes(b"custom couch")
            (build / "Images" / "VF3LargeFlatScreenTVAnim.png").write_bytes(b"tv")
            (build / "Assets").mkdir()
            (build / "Assets" / "VF3LargeFlatScreenTV.png.fmap").write_bytes(b"fmap")
            (build / "Assets" / "LDWPoster1Std.fmap").write_bytes(b"poster fmap")
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "generated_assets": [
                            {"path": "Furniture/CandyCane.png"},
                            {"path": "Furniture/CouchNeonPurpleStd.png"},
                            {"runtime_name": "VF3LargeFlatScreenTVAnim.png"},
                            {"fmap": "VF3LargeFlatScreenTV.png.fmap"},
                            {"fmap": "LDWPoster1Std.fmap"},
                        ]
                    },
                    indent=2,
                ),
                encoding="ascii",
            )

            self.run_exporter("--build-dir", str(build), "--base-payload", str(base), "--out-dir", str(out))

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            asset_by_path = {row["file_path"]: row for row in manifest["asset_patches"]}
            self.assertNotIn("Images/Furniture/Unchanged.png", asset_by_path)
            self.assertEqual(asset_by_path["Images/Furniture/CandyCane.png"]["requires"], ["holiday_furniture"])
            self.assertEqual(asset_by_path["Images/Furniture/CouchNeonPurpleStd.png"]["requires"], ["custom_couches_ldw_posters"])
            self.assertEqual(asset_by_path["Images/VF3LargeFlatScreenTVAnim.png"]["requires"], ["vf3_tv_assets_recognition"])
            self.assertEqual(asset_by_path["Assets/VF3LargeFlatScreenTV.png.fmap"]["requires"], ["vf3_tv_assets_recognition"])
            self.assertEqual(asset_by_path["Assets/LDWPoster1Std.fmap"]["requires"], ["custom_couches_ldw_posters"])
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["holiday_furniture"], 1)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["custom_couches_ldw_posters"], 2)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["vf3_tv_assets_recognition"], 2)
            self.assertTrue((out / "payload" / "Images" / "Furniture" / "CandyCane.png").is_file())
            self.assertIn("Virtual Families 2.exe", manifest["runtime_requirements"]["exact_top_level_entries"])
            self.assertIn({"path": "Images", "min_files": 600}, manifest["runtime_requirements"]["required_dirs"])

            settings = self.run_patcher("settings", "--manifest", str(out / "manifest.json"))
            self.assertIn("holiday_furniture [default on]", settings.stdout)
            self.assertIn("vf3_tv_assets_recognition [default on]", settings.stdout)
            self.assertIn("custom_couches_ldw_posters [default off]", settings.stdout)
            self.assertIn("holiday_ornaments_collection [default off]", settings.stdout)
            self.assertIn("settings_evict_button [default off]", settings.stdout)
            self.assertIn("transparent_store_bar [default off]", settings.stdout)
            self.assertIn("island_events [default off]", settings.stdout)
            self.assertIn("body field sync", settings.stdout)
            settings_by_id = {row["id"]: row for row in manifest["settings"]}
            self.assertEqual(settings_by_id["holiday_furniture"]["category"], "main")
            self.assertEqual(settings_by_id["custom_couches_ldw_posters"]["category"], "optional")
            self.assertEqual(settings_by_id["settings_evict_button"]["category"], "experimental")

    def test_exports_byte_patches_when_vanilla_exe_is_supplied(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            vanilla = tmp_path / "vanilla.exe"
            vanilla.write_bytes(bytes([1, 2, 3, 4, 5, 6]))
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(bytes([1, 2, 0xAA, 0xBB, 5, 6]))

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--vanilla-exe",
                str(vanilla),
                "--include-byte-patches",
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["target_files"][0]["sha256"], __import__("hashlib").sha256(vanilla.read_bytes()).hexdigest())
            self.assertEqual(len(manifest["patches"]), 1)
            self.assertEqual(manifest["patches"][0]["offset"], "0x2")
            self.assertEqual(manifest["patches"][0]["requires"], ["core_native_patch"])
            settings = {row["id"] for row in manifest["settings"]}
            self.assertIn("core_native_patch", settings)
            self.assertIn("core_assets", settings)
            self.assertEqual(manifest["export_summary"]["native_patch_status"]["status"], "byte_diff_exported")

    def test_size_mismatch_records_native_patch_skip_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            vanilla = tmp_path / "vanilla.exe"
            vanilla.write_bytes(bytes([1, 2, 3, 4, 5, 6]))
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(bytes([1, 2, 3]))

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--vanilla-exe",
                str(vanilla),
                "--include-byte-patches",
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["target_files"][0]["size"], len(vanilla.read_bytes()))
            self.assertEqual(manifest["patches"], [])
            status = manifest["export_summary"]["native_patch_status"]
            self.assertEqual(status["status"], "byte_diff_skipped")
            self.assertIn("sizes differ", status["reason"])

    def test_exports_full_bundle_with_exe_replacement_and_runners(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla_data = minimal_pe_bytes()
            vanilla.write_bytes(vanilla_data)
            patched_exe = build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
            patched_exe.write_bytes(b"patched executable")
            (build / "Images" / "Furniture").mkdir(parents=True)
            (build / "Images" / "Furniture" / "InvisibleHammock.png").write_bytes(b"hammock")
            (build / "OptionalVisualMods" / "Invisible Furniture - Base Graphics").mkdir(parents=True)
            (build / "OptionalVisualMods" / "Invisible Furniture - Base Graphics" / "InvisibleHammock.png").write_bytes(b"visible hammock")
            (build / "OptionalVisualMods" / "Invisible Furniture Backups").mkdir(parents=True)
            (build / "OptionalVisualMods" / "Invisible Furniture Backups" / "InvisibleHammock.png").write_bytes(b"transparent backup")
            (build / "Sounds").mkdir()
            (build / "Sounds" / "sound00.wav").write_bytes(b"sound")
            (build / "SDL2.dll").write_bytes(b"dll")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--vanilla-exe",
                str(vanilla),
                "--asset-mode",
                "full",
                "--include-exe-replacement",
                "--include-patcher-scripts",
                "--name",
                "VF2 B103 Test Bundle",
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            asset_by_path = {row["file_path"]: row for row in manifest["asset_patches"]}
            self.assertEqual(asset_by_path["Virtual Families 2.exe"]["requires"], ["core_executable"])
            self.assertEqual(asset_by_path["Virtual Families 2.exe"]["output_file_path"], "Virtual Families 2 - Modded B103.exe")
            self.assertIn("modded B103 executable", asset_by_path["Virtual Families 2.exe"]["note"])
            self.assertEqual(asset_by_path["Virtual Families 2.exe"]["expected_target_sha256"], hashlib.sha256(vanilla_data).hexdigest())
            self.assertIsInstance(asset_by_path["Virtual Families 2.exe"]["expected_target_pe_structure"], dict)
            self.assertIsInstance(manifest["target_files"][0]["pe_structure"], dict)
            self.assertEqual(asset_by_path["Images/Furniture/InvisibleHammock.png"]["requires"], ["invisible_furniture_visible_graphics"])
            self.assertEqual(
                asset_by_path["Images/Furniture/InvisibleHammock.png"]["source_path"],
                "payload/OptionalVisualMods/Invisible Furniture - Base Graphics/InvisibleHammock.png",
            )
            self.assertEqual(asset_by_path["Images/Furniture/InvisibleHammock.png"]["overwrite_existing"], True)
            self.assertIn("Full B103 beta folder", asset_by_path["Images/Furniture/InvisibleHammock.png"]["note"])
            self.assertEqual(
                asset_by_path["OptionalVisualMods/Invisible Furniture Backups/InvisibleHammock.png"]["requires"],
                ["invisible_furniture_transparent_graphics"],
            )
            self.assertEqual(asset_by_path["Sounds/sound00.wav"]["overwrite_existing"], True)
            self.assertEqual(asset_by_path["SDL2.dll"]["overwrite_existing"], True)
            self.assertNotIn("patch-manifest.json", asset_by_path)
            self.assertEqual(manifest["created_with"], "Codex AI")
            self.assertIn("Codex AI", manifest["creator_disclosure"])
            self.assertIn("Virtual Families 2.exe", manifest["runtime_requirements"]["exact_top_level_entries"])
            self.assertIn({"path": "Assets", "min_files": 200}, manifest["runtime_requirements"]["required_dirs"])
            self.assertEqual(manifest["output"]["default_folder_name"], "VF2-B103-Modded")
            self.assertTrue((out / "payload" / "Virtual Families 2 - Modded B103.exe").is_file())
            self.assertTrue((out / "Apply_B103_Patcher.bat").is_file())
            self.assertTrue((out / "README-B103-PATCHER.txt").is_file())
            self.assertTrue((out / "Transparency Log.txt").is_file())
            self.assertTrue((out / "offline_vf2_patcher.py").is_file())
            self.assertTrue((out / "patcher_icon.png").is_file())
            self.assertTrue((out / "patcher_icon.ico").is_file())
            self.assertTrue((out / "Virtual Families 2 Restoration-Addition Patcher.exe").is_file() or (out / "vf2_patcher_launcher.cs").is_file())
            self.assertIn("Codex AI", (out / "README-B103-PATCHER.txt").read_text(encoding="ascii"))
            self.assertIn("Official install validation", (out / "Transparency Log.txt").read_text(encoding="utf-8"))
            self.assertIn("Main Patches (green)", (out / "Transparency Log.txt").read_text(encoding="utf-8"))
            self.assertNotIn("Apply_B99_Patcher.bat", manifest["export_summary"]["runner_files"])
            self.assertIn("patcher_icon.png", manifest["export_summary"]["runner_files"])
            self.assertIn("patcher_icon.ico", manifest["export_summary"]["runner_files"])
            self.assertIn("transparency_log", manifest["export_summary"])
            self.assertIn("launcher", manifest["export_summary"])
            self.assertTrue((out / "vf2_patcher_launcher.cs").is_file())
            self.assertTrue(manifest["export_summary"]["exe_replacement"])

    def test_exports_object_relative_native_patch_sources_as_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "settings_menu": {
                            "evict": {
                                "constructor_patches": [
                                    {
                                        "offset": "0x2DA",
                                        "expected_original_bytes": "0f8580000000",
                                        "replacement_bytes": "909090909090",
                                        "note": "evict branch",
                                    }
                                ]
                            }
                        }
                    },
                    indent=2,
                ),
                encoding="ascii",
            )

            self.run_exporter("--build-dir", str(build), "--base-payload", str(base), "--out-dir", str(out))

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["patches"], [])
            self.assertEqual(manifest["export_summary"]["native_patch_source_count"], 1)
            source = manifest["native_patch_sources"][0]
            self.assertEqual(source["source_path"], "settings_menu/evict/constructor_patches/0")
            self.assertEqual(source["requires"], ["settings_evict_button"])
            self.assertEqual(source["scope"], "object_relative")
            self.assertEqual(source["apply_status"], "not_file_offset")
            self.assertEqual(source["offset"], "0x2DA")
            self.assertEqual(source["expected_original_bytes"], "0f8580000000")
            self.assertEqual(source["replacement_bytes"], "909090909090")

    def test_strict_byte_patches_fail_on_size_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            vanilla = tmp_path / "vanilla.exe"
            vanilla.write_bytes(bytes([1, 2, 3, 4, 5, 6]))
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(bytes([1, 2, 3]))

            result = self.run_exporter_expect(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--vanilla-exe",
                str(vanilla),
                "--include-byte-patches",
                "--strict-byte-patches",
                expect=1,
            )
            self.assertIn("sizes differ", result.stderr)

    def test_all_asset_mode_exports_unreferenced_diffs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            (base / "Images").mkdir(parents=True)
            (build / "Images").mkdir(parents=True)
            (build / "Images" / "UnreferencedGenerated.png").write_bytes(b"generated")
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--asset-mode",
                "all",
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            asset_by_path = {row["file_path"]: row for row in manifest["asset_patches"]}
            self.assertIn("Images/UnreferencedGenerated.png", asset_by_path)
            self.assertEqual(manifest["export_summary"]["asset_mode"], "all")

    def test_force_clears_stale_payload_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            stale = out / "payload" / "Images" / "stale.png"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"stale")
            stale_runner = out / "Apply_B99_Patcher.bat"
            stale_runner.write_text("stale", encoding="ascii")
            (out / "manifest.json").write_text("{}", encoding="ascii")

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--force",
            )

            self.assertFalse(stale.exists())
            self.assertFalse(stale_runner.exists())
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["export_summary"]["payload_file_count"], 0)


if __name__ == "__main__":
    unittest.main()
