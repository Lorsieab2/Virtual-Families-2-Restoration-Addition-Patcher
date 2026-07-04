#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "work" / "export_offline_patch_bundle.py"
PATCHER = ROOT / "work" / "offline_vf2_patcher.py"


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
            (build / "Images" / "VF3LargeFlatScreenTVAnim.png").write_bytes(b"tv")
            (build / "Assets").mkdir()
            (build / "Assets" / "VF3LargeFlatScreenTV.png.fmap").write_bytes(b"fmap")
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "generated_assets": [
                            {"path": "Furniture/CandyCane.png"},
                            {"runtime_name": "VF3LargeFlatScreenTVAnim.png"},
                            {"fmap": "VF3LargeFlatScreenTV.png.fmap"},
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
            self.assertEqual(asset_by_path["Images/VF3LargeFlatScreenTVAnim.png"]["requires"], ["vf3_tv_assets_recognition"])
            self.assertEqual(asset_by_path["Assets/VF3LargeFlatScreenTV.png.fmap"]["requires"], ["vf3_tv_assets_recognition"])
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["holiday_furniture"], 1)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["vf3_tv_assets_recognition"], 2)
            self.assertTrue((out / "payload" / "Images" / "Furniture" / "CandyCane.png").is_file())
            self.assertIn({"path": "Images", "min_files": 1000}, manifest["runtime_requirements"]["required_dirs"])

            settings = self.run_patcher("settings", "--manifest", str(out / "manifest.json"))
            self.assertIn("holiday_furniture [default on]", settings.stdout)
            self.assertIn("vf3_tv_assets_recognition [default on]", settings.stdout)

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
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["export_summary"]["payload_file_count"], 0)


if __name__ == "__main__":
    unittest.main()
