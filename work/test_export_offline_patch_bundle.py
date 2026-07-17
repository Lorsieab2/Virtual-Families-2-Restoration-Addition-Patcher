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
sys.path.insert(0, str(ROOT / "work"))
import export_offline_patch_bundle as exporter


def minimal_pe_bytes(
    with_older_pregnancy_flag=False,
    marker=0,
    with_older_mortality_flag=False,
    mortality_marker=0,
    with_holiday_goal_flag=False,
    goal_marker=0,
):
    runtime_flags = []
    if with_older_pregnancy_flag:
        runtime_flags.append((".vf2preg", marker))
    if with_older_mortality_flag:
        runtime_flags.append((".vf2mort", mortality_marker))
    if with_holiday_goal_flag:
        runtime_flags.append((".vf2goal", goal_marker))
    # Three runtime-flag sections extend the PE section table past 0x200, so
    # keep the legacy fixture offsets for zero-to-two flags and shift only the
    # three-flag B153 coexistence fixtures by one file-alignment block.
    text_raw_offset = 0x400 if len(runtime_flags) > 2 else 0x200
    flag_raw_base = text_raw_offset + 0x200
    data = bytearray(flag_raw_base + 0x200 * len(runtime_flags))
    data[:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    pe = 0x80
    data[pe:pe + 4] = b"PE\0\0"
    coff = pe + 4
    data[coff:coff + 20] = (
        (0x14C).to_bytes(2, "little")
        + (1 + len(runtime_flags)).to_bytes(2, "little")
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
    data[opt + 56:opt + 60] = (
        (2 + len(runtime_flags)) * 0x1000
    ).to_bytes(4, "little")
    data[opt + 68:opt + 70] = (2).to_bytes(2, "little")
    sect = opt + 0xE0
    data[sect:sect + 8] = b".text\0\0\0"
    data[sect + 8:sect + 16] = (0x200).to_bytes(4, "little") + (0x1000).to_bytes(4, "little")
    data[sect + 16:sect + 24] = (
        (0x200).to_bytes(4, "little") + text_raw_offset.to_bytes(4, "little")
    )
    data[sect + 36:sect + 40] = (0x60000020).to_bytes(4, "little")
    data[text_raw_offset:text_raw_offset + 0x200] = bytes(
        (index % 251 for index in range(0x200))
    )
    for index, (section_name, value) in enumerate(runtime_flags):
        flag_sect = sect + 40 * (index + 1)
        raw_offset = flag_raw_base + 0x200 * index
        rva = 0x2000 + 0x1000 * index
        data[flag_sect:flag_sect + 8] = section_name.encode("ascii")
        data[flag_sect + 8:flag_sect + 16] = (
            (1).to_bytes(4, "little") + rva.to_bytes(4, "little")
        )
        data[flag_sect + 16:flag_sect + 24] = (
            (0x200).to_bytes(4, "little") + raw_offset.to_bytes(4, "little")
        )
        data[flag_sect + 36:flag_sect + 40] = (0xC0000040).to_bytes(
            4, "little"
        )
        data[raw_offset] = value
    return bytes(data)


class ExportOfflinePatchBundleTests(unittest.TestCase):
    def test_decimal_build_label_is_preserved(self):
        self.assertEqual(
            exporter.infer_build_label(Path("VF2-Patcher-B155.5")),
            "B155.5",
        )
        self.assertEqual(
            exporter.infer_build_label(Path("bundle"), "manifest-B155.5.json"),
            "B155.5",
        )

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

    def test_exports_and_applies_coexisting_b152_runtime_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            bundle = tmp_path / "bundle"
            game = tmp_path / "game"
            output = tmp_path / "modded"
            disabled_output = tmp_path / "modded-disabled"
            all_disabled_output = tmp_path / "modded-all-disabled"
            base.mkdir()
            build.mkdir()
            game.mkdir()

            patched_name = "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
            patched_data = minimal_pe_bytes(
                with_older_pregnancy_flag=True,
                marker=0,
                with_older_mortality_flag=True,
                mortality_marker=0,
                with_holiday_goal_flag=True,
                goal_marker=0,
            )
            (build / patched_name).write_bytes(patched_data)
            (build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "AllowOlderPregnancies": {
                            "runtime_flag": {
                                "source_section": ".vf2preg",
                                "size": 1,
                                "default": "00",
                            }
                        },
                        "OlderVillagerMortality": {
                            "runtime_flag": {
                                "source_section": ".vf2mort",
                                "size": 1,
                                "default": "00",
                            }
                        },
                        "CustomAchievements": {
                            "runtime_flag": {
                                "source_section": ".vf2goal",
                                "size": 1,
                                "default": "00",
                            }
                        }
                    },
                    indent=2,
                ),
                encoding="ascii",
            )
            vanilla = game / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(bundle),
                "--vanilla-exe",
                str(vanilla),
                "--include-exe-replacement",
            )

            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            setting = {
                row["id"]: row for row in manifest["settings"]
            }["allow_older_pregnancies"]
            self.assertFalse(setting["default"])
            self.assertEqual(setting["category"], "experimental")
            self.assertEqual(len(manifest["post_asset_patches"]), 3)
            records = {
                row["requires"][-1]: row
                for row in manifest["post_asset_patches"]
            }
            goal_record = records["holiday_furniture"]
            self.assertEqual(
                goal_record["requires"],
                ["core_executable", "holiday_furniture"],
            )
            self.assertEqual(goal_record["variants"][0]["offset"], "0xa00")
            record = records["allow_older_pregnancies"]
            self.assertEqual(
                record["requires"],
                ["core_executable", "allow_older_pregnancies"],
            )
            self.assertEqual(len(record["variants"]), 1)
            variant = record["variants"][0]
            self.assertEqual(variant["offset"], "0x600")
            self.assertEqual(variant["expected_asset_bytes"], "00")
            self.assertEqual(variant["replacement_bytes"], "01")
            self.assertEqual(
                variant["asset_sha256"],
                hashlib.sha256(patched_data).hexdigest(),
            )
            self.assertEqual(
                manifest["export_summary"]["post_asset_patch_count"],
                3,
            )
            mortality_record = records["older_villager_mortality"]
            self.assertEqual(
                mortality_record["requires"],
                ["core_executable", "older_villager_mortality"],
            )
            self.assertEqual(mortality_record["variants"][0]["offset"], "0x800")

            # Keep this integration fixture focused on target/asset/post-asset
            # validation rather than the production folder-shape validator.
            manifest["runtime_requirements"] = {
                "required_files": [],
                "required_dirs": [],
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )
            self.run_patcher(
                "apply",
                "--game-dir",
                str(game),
                "--output-dir",
                str(disabled_output),
                "--manifest",
                str(manifest_path),
            )
            disabled_installed = (
                disabled_output / manifest["output"]["default_exe_name"]
            )
            self.assertEqual(disabled_installed.read_bytes()[0x600], 0)
            self.assertEqual(disabled_installed.read_bytes()[0x800], 0)
            self.assertEqual(disabled_installed.read_bytes()[0xA00], 1)
            self.run_patcher(
                "apply",
                "--game-dir",
                str(game),
                "--output-dir",
                str(output),
                "--manifest",
                str(manifest_path),
                "--enable",
                "allow_older_pregnancies",
            )
            installed = output / manifest["output"]["default_exe_name"]
            self.assertTrue(installed.is_file())
            self.assertEqual(installed.read_bytes()[0x600], 1)
            self.assertEqual(installed.read_bytes()[0x800], 0)
            self.assertEqual(installed.read_bytes()[0xA00], 1)
            self.run_patcher(
                "apply",
                "--game-dir",
                str(game),
                "--output-dir",
                str(all_disabled_output),
                "--manifest",
                str(manifest_path),
                "--disable",
                "holiday_furniture",
            )
            all_disabled = (
                all_disabled_output / manifest["output"]["default_exe_name"]
            ).read_bytes()
            self.assertEqual(all_disabled[0x600], 0)
            self.assertEqual(all_disabled[0x800], 0)
            self.assertEqual(all_disabled[0xA00], 0)

    def test_b152_runtime_records_cover_sixteen_unique_layout_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sources = []
            for index in range(16):
                data = bytearray(
                    minimal_pe_bytes(
                        with_older_pregnancy_flag=True,
                        with_older_mortality_flag=True,
                        with_holiday_goal_flag=True,
                    )
                )
                data[0x400 + index] ^= index + 1
                path = tmp_path / f"variant-{index:02d}.exe"
                path.write_bytes(data)
                sources.append(path)
            records = exporter.b152_runtime_flag_post_asset_patches(
                sources,
                output_exe_name="Virtual Families 2 - Modded B152.exe",
                build_manifest_data={
                    "AllowOlderPregnancies": {
                        "runtime_flag": {
                            "source_section": ".vf2preg",
                        }
                    },
                    "OlderVillagerMortality": {
                        "runtime_flag": {
                            "source_section": ".vf2mort",
                        }
                    },
                    "CustomAchievements": {
                        "runtime_flag": {
                            "source_section": ".vf2goal",
                        }
                    }
                },
            )
            self.assertEqual(len(records), 3)
            records_by_setting = {
                row["requires"][-1]: row for row in records
            }
            expected_offsets = {
                "allow_older_pregnancies": "0x600",
                "older_villager_mortality": "0x800",
                "holiday_furniture": "0xa00",
            }
            hashes_by_setting = {}
            for setting_id, offset in expected_offsets.items():
                variants = records_by_setting[setting_id]["variants"]
                self.assertEqual(len(variants), 16)
                hashes = {row["asset_sha256"] for row in variants}
                self.assertEqual(len(hashes), 16)
                hashes_by_setting[setting_id] = hashes
                self.assertEqual({row["offset"] for row in variants}, {offset})
                self.assertEqual(
                    {row["expected_asset_bytes"] for row in variants},
                    {"00"},
                )
                self.assertEqual(
                    {row["replacement_bytes"] for row in variants},
                    {"01"},
                )
            self.assertEqual(
                hashes_by_setting["allow_older_pregnancies"],
                hashes_by_setting["holiday_furniture"],
            )
            self.assertEqual(
                hashes_by_setting["allow_older_pregnancies"],
                hashes_by_setting["older_villager_mortality"],
            )

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
            (build / "Images" / "Furniture" / "Transient.png.pre-frame-pad.bak").write_bytes(b"backup")
            (build / "Images" / "VF3LargeFlatScreenTVAnim.png").write_bytes(b"tv")
            (build / "Images" / "VF3TVAnimations" / "Large").mkdir(parents=True)
            (build / "Images" / "VF3TVAnimations" / "Large" / "Frame01.png").write_bytes(b"tv frame")
            (build / "Images" / "Furniture" / "SofaPlaid.png").write_bytes(b"vf3 loveseat")
            (build / "Images" / "VillagerDetailBodies" / "Female" / "Body_50").mkdir(parents=True)
            (build / "Images" / "VillagerDetailBodies" / "Female" / "Body_50" / "Frame00.png").write_bytes(b"detail body")
            (build / "Assets").mkdir()
            (build / "Assets" / "VF3LargeFlatScreenTV.png.fmap").write_bytes(b"fmap")
            (build / "Assets" / "LDWPoster1Std.fmap").write_bytes(b"poster fmap")
            (build / "Assets" / "FloweredLoveseat.png.fmap").write_bytes(b"vf3 furniture fmap")
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "generated_assets": [
                            {"path": "Furniture/CandyCane.png"},
                            {"path": "Furniture/CouchNeonPurpleStd.png"},
                            {"path": "Furniture/Transient.png.pre-frame-pad.bak"},
                            {"path": "Furniture/SofaPlaid.png"},
                            {"path": "VillagerDetailBodies/Female/Body_50/Frame00.png"},
                            {"path": "Images/VF3TVAnimations/Large/Frame01.png"},
                            {"runtime_name": "VF3LargeFlatScreenTVAnim.png"},
                            {"fmap": "VF3LargeFlatScreenTV.png.fmap"},
                            {"fmap": "LDWPoster1Std.fmap"},
                            {"fmap": "FloweredLoveseat.png.fmap"},
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
            self.assertNotIn("Images/Furniture/Transient.png.pre-frame-pad.bak", asset_by_path)
            self.assertEqual(asset_by_path["Images/Furniture/CandyCane.png"]["requires"], ["holiday_furniture"])
            self.assertEqual(asset_by_path["Images/Furniture/CouchNeonPurpleStd.png"]["requires"], ["custom_couches_ldw_posters"])
            self.assertEqual(asset_by_path["Images/VF3LargeFlatScreenTVAnim.png"]["requires"], ["core_executable", "vf3_tv_assets_recognition"])
            self.assertEqual(asset_by_path["Images/VF3TVAnimations/Large/Frame01.png"]["requires"], ["core_executable", "vf3_tv_assets_recognition"])
            self.assertEqual(asset_by_path["Images/Furniture/SofaPlaid.png"]["requires"], ["core_executable", "vf3_furniture"])
            self.assertEqual(asset_by_path["Assets/FloweredLoveseat.png.fmap"]["requires"], ["core_executable", "vf3_furniture"])
            self.assertEqual(asset_by_path["Images/VillagerDetailBodies/Female/Body_50/Frame00.png"]["requires"], ["holiday_outfits"])
            self.assertEqual(asset_by_path["Assets/VF3LargeFlatScreenTV.png.fmap"]["requires"], ["core_executable", "vf3_tv_assets_recognition"])
            self.assertEqual(asset_by_path["Assets/LDWPoster1Std.fmap"]["requires"], ["custom_couches_ldw_posters"])
            self.assertEqual(asset_by_path["Images/Upgrades/superFridge_NW.png"]["requires"], ["misc_graphics_fixes"])
            self.assertEqual(asset_by_path["Images/collectables_small.png"]["requires"], ["glowing_collectibles"])
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["holiday_furniture"], 1)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["holiday_outfits"], 1)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["custom_couches_ldw_posters"], 2)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["vf3_tv_assets_recognition"], 3)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["vf3_furniture"], 2)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["misc_graphics_fixes"], 1)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["glowing_collectibles"], 1)
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["core_executable"], 5)
            self.assertEqual(manifest["post_asset_patches"], [])
            self.assertEqual(manifest["export_summary"]["post_asset_patch_count"], 0)
            self.assertEqual(manifest["export_summary"]["base_payload"], base.name)
            self.assertNotIn(str(tmp_path), json.dumps(manifest))
            self.assertTrue((out / "payload" / "Images" / "Furniture" / "CandyCane.png").is_file())
            self.assertNotIn("Virtual Families 2.exe", manifest["runtime_requirements"]["exact_top_level_entries"])
            self.assertIn({"path": "Images", "min_files": 600}, manifest["runtime_requirements"]["required_dirs"])

            settings = self.run_patcher("settings", "--manifest", str(out / "manifest.json"))
            self.assertIn("holiday_furniture [default on]", settings.stdout)
            self.assertIn("vf3_tv_assets_recognition [default on]", settings.stdout)
            self.assertIn("behavior_patches [default on]", settings.stdout)
            self.assertIn("text_fixes [default on]", settings.stdout)
            self.assertIn("store_scroll_bar [default off]", settings.stdout)
            self.assertIn("custom_couches_ldw_posters [default off]", settings.stdout)
            self.assertIn("vf3_furniture [default off]", settings.stdout)
            self.assertIn("misc_graphics_fixes [default off]", settings.stdout)
            self.assertIn("glowing_collectibles [default off]", settings.stdout)
            self.assertIn("holiday_ornaments_collection [default off]", settings.stdout)
            self.assertIn("settings_evict_button [default off]", settings.stdout)
            self.assertIn("unused_pets [default on]", settings.stdout)
            self.assertIn("island_events [default off]", settings.stdout)
            self.assertIn("body field sync", settings.stdout)
            self.assertNotIn("transparent_store_bar [default off]", settings.stdout)
            self.assertIn("optional_song_mods [default off]", settings.stdout)
            settings_by_id = {row["id"]: row for row in manifest["settings"]}
            self.assertEqual(settings_by_id["holiday_furniture"]["category"], "main")
            self.assertEqual(settings_by_id["unused_pets"]["category"], "main")
            self.assertEqual(settings_by_id["custom_couches_ldw_posters"]["category"], "optional")
            self.assertEqual(settings_by_id["vf3_furniture"]["category"], "optional")
            self.assertEqual(settings_by_id["misc_graphics_fixes"]["category"], "optional")
            self.assertEqual(settings_by_id["glowing_collectibles"]["category"], "optional")
            self.assertEqual(settings_by_id["settings_evict_button"]["category"], "optional")
            self.assertEqual(settings_by_id["island_events"]["category"], "optional")
            self.assertEqual(settings_by_id["holiday_ornaments_collection"]["category"], "optional")
            self.assertIn(
                "fully linked mobile Holiday Ornament collection",
                settings_by_id["holiday_ornaments_collection"]["description"],
            )
            self.assertEqual(settings_by_id["behavior_patches"]["category"], "main")
            self.assertEqual(settings_by_id["text_fixes"]["category"], "main")
            self.assertEqual(settings_by_id["optional_song_mods"]["category"], "optional")

    def test_holiday_ornament_assets_export_from_overlay_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            holiday_build = tmp_path / "holiday"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            (holiday_build / "Images" / "CollectionOrnaments").mkdir(parents=True)
            (holiday_build / "Images" / "Furniture").mkdir(parents=True)
            (holiday_build / "Images" / "collectables_small.png").write_bytes(b"holiday sheet")
            (holiday_build / "Images" / "collection-ornaments_background.png").write_bytes(b"holiday background")
            (holiday_build / "Images" / "CollectionOrnaments" / "collection_christmasornament_blueball.png").write_bytes(b"blueball")
            (holiday_build / "Images" / "Furniture" / "CandyCane.png").write_bytes(b"not part of ornament overlay")
            (holiday_build / "Virtual Families 2 - Additive Mobile Furniture Pack Holiday Ornaments.exe").write_bytes(b"holiday exe")
            (holiday_build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "generated_assets": [
                            {"path": "Images/collectables_small.png"},
                            {"path": "collection-ornaments_background.png"},
                            {"path": "CollectionOrnaments/collection_christmasornament_blueball.png"},
                            {"path": "Furniture/CandyCane.png"},
                        ]
                    },
                    indent=2,
                ),
                encoding="ascii",
            )

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--holiday-ornaments-exe",
                str(holiday_build / "Virtual Families 2 - Additive Mobile Furniture Pack Holiday Ornaments.exe"),
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            records_by_path = {}
            for row in manifest["asset_patches"]:
                records_by_path.setdefault(row["file_path"], []).append(row)

            def find_requires(path, requires):
                return next((row for row in records_by_path[path] if row["requires"] == requires), None)

            self.assertIsNotNone(find_requires("Images/collectables_small.png", ["holiday_ornaments_collection"]))
            self.assertIsNotNone(find_requires("Images/collection-ornaments_background.png", ["holiday_ornaments_collection"]))
            self.assertIsNotNone(find_requires(
                "Images/CollectionOrnaments/collection_christmasornament_blueball.png",
                ["holiday_ornaments_collection"],
            ))
            self.assertNotIn("Images/Furniture/CandyCane.png", records_by_path)
            self.assertTrue((out / "payload" / "Images" / "collectables_small.png").is_file())
            self.assertTrue((out / "payload" / "Images" / "collection-ornaments_background.png").is_file())
            self.assertTrue((out / "payload" / "Images" / "CollectionOrnaments" / "collection_christmasornament_blueball.png").is_file())
            self.assertFalse((out / "payload" / "Images" / "Furniture" / "CandyCane.png").exists())
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["holiday_ornaments_collection"], 3)

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

    def test_generation_lock_art_is_forced_from_individual_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            from PIL import Image

            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            (build / "Images").mkdir(parents=True)
            (build / "Images" / "GenerationLocks").mkdir(parents=True)
            strip = Image.new("RGBA", (29 * 30, 46), (0, 0, 0, 0))
            for frame in range(29):
                for x in range(frame * 30, frame * 30 + 30):
                    strip.putpixel((x, frame % 46), (frame + 1, 10, 20, 255))
            strip.save(build / "Images" / "locked.png")
            for generation in range(2, 31):
                icon = Image.new("RGBA", (30, 46), (generation, 100, 200, 255))
                icon.save(build / "Images" / "GenerationLocks" / f"lock_{generation:02d}.png")
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")

            self.run_exporter("--build-dir", str(build), "--base-payload", str(base), "--out-dir", str(out))

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            asset_by_path = {row["file_path"]: row for row in manifest["asset_patches"]}
            self.assertEqual(asset_by_path["Images/locked.png"]["requires"], ["core_executable"])
            generated = [
                path
                for path in asset_by_path
                if path.startswith("Images/GenerationLocks/lock_")
            ]
            self.assertEqual(len(generated), 29)
            self.assertEqual(asset_by_path["Images/GenerationLocks/lock_02.png"]["requires"], ["core_executable"])
            self.assertTrue((out / "payload" / "Images" / "GenerationLocks" / "lock_02.png").is_file())
            self.assertTrue((out / "payload" / "Images" / "GenerationLocks" / "lock_30.png").is_file())
            lock_30 = Image.open(out / "payload" / "Images" / "GenerationLocks" / "lock_30.png").convert("RGBA")
            self.assertEqual(lock_30.getpixel((0, 0)), (30, 100, 200, 255))
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["core_executable"], 30)

    def test_generation_lock_art_uses_numbered_frames_when_strip_is_short(self):
        with tempfile.TemporaryDirectory() as tmp:
            from PIL import Image

            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            (build / "Images").mkdir(parents=True)
            (build / "Images" / "GenerationLocks").mkdir(parents=True)
            strip = Image.new("RGBA", (8 * 30, 46), (0, 0, 0, 0))
            for frame in range(8):
                strip.putpixel((frame * 30, 0), (frame, 0, 0, 255))
            strip.save(build / "Images" / "locked.png")
            for generation in range(2, 31):
                icon = Image.new("RGBA", (30, 46), (generation, 1, 2, 255))
                icon.save(build / "Images" / "GenerationLocks" / f"lock_{generation:02d}.png")
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")

            self.run_exporter("--build-dir", str(build), "--base-payload", str(base), "--out-dir", str(out))

            lock_09 = Image.open(out / "payload" / "Images" / "GenerationLocks" / "lock_09.png").convert("RGBA")
            lock_30 = Image.open(out / "payload" / "Images" / "GenerationLocks" / "lock_30.png").convert("RGBA")
            self.assertEqual(lock_09.getpixel((0, 0)), (9, 1, 2, 255))
            self.assertEqual(lock_30.getpixel((0, 0)), (30, 1, 2, 255))

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
            island_exe = build / "Virtual Families 2 - Additive Mobile Furniture Pack Island Events.exe"
            island_exe.write_bytes(b"patched executable with island events")
            (build / "Images" / "Furniture").mkdir(parents=True)
            (build / "Images" / "Furniture" / "InvisibleHammock.png").write_bytes(b"hammock")
            (build / "OptionalVisualMods" / "Invisible Furniture - Base Graphics").mkdir(parents=True)
            (build / "OptionalVisualMods" / "Invisible Furniture - Base Graphics" / "InvisibleHammock.png").write_bytes(b"visible hammock")
            (build / "OptionalVisualMods" / "Invisible Furniture Backups").mkdir(parents=True)
            (build / "OptionalVisualMods" / "Invisible Furniture Backups" / "InvisibleHammock.png").write_bytes(b"transparent backup")
            (build / "OptionalVisualMods" / "PoolTableStd.png").write_bytes(b"pool table visual")
            (build / "OptionalVisualMods" / "bird.png").write_bytes(b"white bird")
            (build / "OptionalVisualMods" / "bird_shadow.png").write_bytes(b"white bird shadow")
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
                "--island-events-exe",
                str(island_exe),
                "--name",
                "VF2 B103 Test Bundle",
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            assets_by_path = {}
            for row in manifest["asset_patches"]:
                assets_by_path.setdefault(row["file_path"], []).append(row)
            exe_records = assets_by_path["Virtual Families 2.exe"]
            core_exe = next(row for row in exe_records if row["requires"] == ["core_executable"])
            island_overlay = next(row for row in exe_records if row["requires"] == ["core_executable", "island_events"])
            self.assertEqual(core_exe["output_file_path"], "Virtual Families 2 - Modded B103.exe")
            self.assertIn("modded B103 executable", core_exe["note"])
            self.assertEqual(island_overlay["output_file_path"], "Virtual Families 2 - Modded B103.exe")
            self.assertIn("Island Events executable overlay", island_overlay["note"])
            self.assertTrue((out / "payload" / "Virtual Families 2 - Modded B103 - Island Events.exe").is_file())
            if "expected_target_pe_structures" in core_exe:
                self.assertNotIn("expected_target_sha256", core_exe)
                self.assertIsInstance(core_exe["expected_target_pe_structures"], list)
                self.assertNotIn("sha256", manifest["target_files"][0])
                self.assertIsInstance(manifest["target_files"][0]["pe_structures"], list)
                self.assertGreaterEqual(len(manifest["target_files"][0]["pe_structures"]), 2)
                self.assertGreaterEqual(len(core_exe["expected_target_pe_structures"]), 2)
                self.assertIn(
                    "0x100",
                    {row.get("pe_offset") for row in manifest["target_files"][0]["pe_structures"]},
                )
                self.assertIn(
                    "0x100",
                    {row.get("pe_offset") for row in core_exe["expected_target_pe_structures"]},
                )
            else:
                self.assertIn("expected_target_sha256", core_exe)
                self.assertIn("sha256", manifest["target_files"][0])
            asset_by_path = {row["file_path"]: row for row in manifest["asset_patches"] if row["file_path"] != "Virtual Families 2.exe"}
            self.assertEqual(asset_by_path["Images/Furniture/InvisibleHammock.png"]["requires"], ["invisible_furniture_visible_graphics"])
            self.assertEqual(
                asset_by_path["Images/Furniture/InvisibleHammock.png"]["source_path"],
                "payload/OptionalVisualMods/Invisible Furniture - Base Graphics/InvisibleHammock.png",
            )
            self.assertEqual(asset_by_path["Images/Furniture/InvisibleHammock.png"]["overwrite_existing"], True)
            self.assertIn("Full B103 beta folder", asset_by_path["Images/Furniture/InvisibleHammock.png"]["note"])
            self.assertEqual(
                asset_by_path["Images/Furniture/PoolTableStd.png"]["requires"],
                ["optional_visual_mod_graphics"],
            )
            self.assertEqual(
                asset_by_path["Images/Furniture/PoolTableStd.png"]["source_path"],
                "payload/OptionalVisualMods/PoolTableStd.png",
            )
            self.assertEqual(asset_by_path["Images/bird.png"]["requires"], ["white_birds"])
            self.assertEqual(asset_by_path["Images/bird_shadow.png"]["requires"], ["white_birds"])
            self.assertNotIn("OptionalVisualMods/Invisible Furniture Backups/InvisibleHammock.png", asset_by_path)
            self.assertNotIn("Sounds/sound00.wav", asset_by_path)
            self.assertNotIn("SDL2.dll", asset_by_path)
            self.assertNotIn("patch-manifest.json", asset_by_path)
            self.assertEqual(manifest["created_with"], "Codex AI")
            self.assertIn("Codex AI", manifest["creator_disclosure"])
            creator_message = (
                'Created by Lorsieab2. This is a passion project dedicated to improving the '
                '"Virtual Families 2" experience!\n'
                'No copyright infringement intended! Please support the original game creators! :)'
            )
            compatibility_note = "Vanilla Virtual Families 2 saves are compatible with the modded version!"
            self.assertEqual(manifest["project_creator_message"], creator_message)
            self.assertEqual(manifest["save_compatibility_note"], compatibility_note)
            self.assertNotIn("Virtual Families 2.exe", manifest["runtime_requirements"]["exact_top_level_entries"])
            self.assertIn({"path": "Assets", "min_files": 200}, manifest["runtime_requirements"]["required_dirs"])
            self.assertEqual(manifest["output"]["default_folder_name"], "VF2-B103-Modded")
            self.assertTrue((out / "payload" / "Virtual Families 2 - Modded B103.exe").is_file())
            self.assertTrue((out / "Apply_B103_Patcher.bat").is_file())
            self.assertTrue((out / "README-B103-PATCHER.txt").is_file())
            self.assertTrue((out / "Transparency Log.txt").is_file())
            self.assertTrue((out / "offline_vf2_patcher.py").is_file())
            self.assertTrue((out / "patcher_icon.png").is_file())
            self.assertTrue((out / "patcher_icon.ico").is_file())
            settings_by_id = {row["id"]: row for row in manifest["settings"]}
            self.assertEqual(settings_by_id["white_birds"]["category"], "optional")
            self.assertEqual(settings_by_id["optional_song_mods"]["category"], "optional")
            self.assertFalse((out / "Virtual Families 2 Restoration-Addition Patcher.exe").exists())
            self.assertFalse((out / "vf2_patcher_launcher.cs").exists())
            self.assertFalse((out / "patcher_launcher_build.json").exists())
            self.assertTrue((out / "Launch_GUI.bat").is_file())
            self.assertFalse((out / "Launch GUI.lnk").exists())
            self.assertFalse((out / "launch_gui_shortcut.json").exists())
            self.assertFalse((out / "payload" / "SDL2.dll").exists())
            self.assertFalse((out / "payload" / "Sounds" / "sound00.wav").exists())
            self.assertIn("Codex AI", (out / "README-B103-PATCHER.txt").read_text(encoding="ascii"))
            self.assertIn(creator_message, (out / "README-B103-PATCHER.txt").read_text(encoding="ascii"))
            self.assertIn(compatibility_note, (out / "README-B103-PATCHER.txt").read_text(encoding="ascii"))
            self.assertIn(compatibility_note, (out / "How to Use.txt").read_text(encoding="ascii"))
            gui_source = (out / "offline_vf2_patcher_gui.py").read_text(encoding="utf-8")
            self.assertIn("PROJECT_CREATOR_MESSAGE", gui_source)
            self.assertIn("SAVE_COMPATIBILITY_NOTE", gui_source)
            self.assertIn("Official install validation", (out / "Transparency Log.txt").read_text(encoding="utf-8"))
            self.assertIn(creator_message, (out / "Transparency Log.txt").read_text(encoding="utf-8"))
            self.assertIn(compatibility_note, (out / "Transparency Log.txt").read_text(encoding="utf-8"))
            self.assertIn("Main Patches (green)", (out / "Transparency Log.txt").read_text(encoding="utf-8"))
            self.assertIn("Prebuilt Launch GUI.lnk is intentionally omitted", (out / "Transparency Log.txt").read_text(encoding="utf-8"))
            self.assertNotIn("Apply_B99_Patcher.bat", manifest["export_summary"]["runner_files"])
            self.assertIn("Launch_GUI.bat", manifest["export_summary"]["runner_files"])
            self.assertNotIn("Launch GUI.lnk", manifest["export_summary"]["runner_files"])
            self.assertNotIn("launch_gui_shortcut.json", manifest["export_summary"]["runner_files"])
            self.assertIn("patcher_icon.png", manifest["export_summary"]["runner_files"])
            self.assertIn("patcher_icon.ico", manifest["export_summary"]["runner_files"])
            self.assertIn("transparency_log", manifest["export_summary"])
            self.assertNotIn("launch_gui_shortcut", manifest["export_summary"])
            self.assertNotIn("launcher", manifest["export_summary"])
            self.assertTrue(manifest["export_summary"]["exe_replacement"])

    def test_exports_complete_behavior_exe_overlay_matrix_and_applies_most_specific(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            game = tmp_path / "game"
            base.mkdir()
            build.mkdir()
            game.mkdir()
            vanilla_data = minimal_pe_bytes()
            vanilla = game / "Virtual Families 2.exe"
            vanilla.write_bytes(vanilla_data)
            patched_exe = build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
            patched_exe.write_bytes(b"core executable without optional native patches")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")

            overlay_specs = [
                ("--island-events-exe", "Island Events", ["core_executable", "island_events"]),
                ("--cheat-upgrades-exe", "Cheat Upgrades", ["core_executable", "cheat_upgrades"]),
                ("--holiday-ornaments-exe", "Holiday Ornaments", ["core_executable", "holiday_ornaments_collection"]),
                ("--behavior-patches-exe", "Behavior Patches", ["core_executable", "behavior_patches"]),
                ("--island-events-cheat-upgrades-exe", "Island Events + Cheat Upgrades", ["core_executable", "island_events", "cheat_upgrades"]),
                ("--island-events-holiday-ornaments-exe", "Island Events + Holiday Ornaments", ["core_executable", "island_events", "holiday_ornaments_collection"]),
                ("--cheat-upgrades-holiday-ornaments-exe", "Cheat Upgrades + Holiday Ornaments", ["core_executable", "cheat_upgrades", "holiday_ornaments_collection"]),
                ("--island-events-behavior-patches-exe", "Island Events + Behavior Patches", ["core_executable", "island_events", "behavior_patches"]),
                ("--cheat-upgrades-behavior-patches-exe", "Cheat Upgrades + Behavior Patches", ["core_executable", "cheat_upgrades", "behavior_patches"]),
                ("--holiday-ornaments-behavior-patches-exe", "Holiday Ornaments + Behavior Patches", ["core_executable", "holiday_ornaments_collection", "behavior_patches"]),
                ("--island-events-cheat-upgrades-holiday-ornaments-exe", "Island Events + Cheat Upgrades + Holiday Ornaments", ["core_executable", "island_events", "cheat_upgrades", "holiday_ornaments_collection"]),
                ("--island-events-cheat-upgrades-behavior-patches-exe", "Island Events + Cheat Upgrades + Behavior Patches", ["core_executable", "island_events", "cheat_upgrades", "behavior_patches"]),
                ("--island-events-holiday-ornaments-behavior-patches-exe", "Island Events + Holiday Ornaments + Behavior Patches", ["core_executable", "island_events", "holiday_ornaments_collection", "behavior_patches"]),
                ("--cheat-upgrades-holiday-ornaments-behavior-patches-exe", "Cheat Upgrades + Holiday Ornaments + Behavior Patches", ["core_executable", "cheat_upgrades", "holiday_ornaments_collection", "behavior_patches"]),
                ("--island-events-cheat-upgrades-holiday-ornaments-behavior-patches-exe", "Island Events + Cheat Upgrades + Holiday Ornaments + Behavior Patches", ["core_executable", "island_events", "cheat_upgrades", "holiday_ornaments_collection", "behavior_patches"]),
            ]
            export_args = [
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--vanilla-exe",
                str(vanilla),
                "--asset-mode",
                "additive",
                "--include-exe-replacement",
                "--name",
                "B150",
            ]
            source_data_by_requires = {}
            source_name_by_field = {}
            for index, (flag, label, requires) in enumerate(overlay_specs, start=1):
                source = build / f"overlay-{index:02d}.exe"
                source_data = f"overlay executable: {label}".encode("ascii")
                source.write_bytes(source_data)
                export_args.extend([flag, str(source)])
                source_data_by_requires[tuple(requires)] = source_data
                source_name_by_field[flag.removeprefix("--").replace("-", "_")] = source.name

            self.run_exporter(*export_args)

            manifest_path = out / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            exe_records = [
                row for row in manifest["asset_patches"]
                if row["file_path"] == "Virtual Families 2.exe"
            ]
            expected_requires = [["core_executable"], *[spec[2] for spec in overlay_specs]]
            self.assertEqual([row["requires"] for row in exe_records], expected_requires)
            self.assertEqual(len(exe_records), 16)
            self.assertEqual(
                [len(row["requires"]) for row in exe_records],
                sorted(len(row["requires"]) for row in exe_records),
            )
            behavior_records = [
                row for row in exe_records
                if "behavior_patches" in row["requires"]
            ]
            self.assertEqual(len(behavior_records), 8)
            self.assertTrue(all("core_executable" in row["requires"] for row in behavior_records))
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["behavior_patches"], 8)
            self.assertIn("behavior_patches", {row["id"] for row in manifest["settings"]})
            for field, source_name in source_name_by_field.items():
                self.assertEqual(manifest["source_build"][field], source_name)
            for record, (_, label, requires) in zip(exe_records[1:], overlay_specs):
                payload = out / record["source_path"]
                self.assertEqual(payload.name, f"Virtual Families 2 - Modded B150 - {label}.exe")
                self.assertEqual(payload.read_bytes(), source_data_by_requires[tuple(requires)])

            # Strip unrelated official-install requirements so this focused test
            # can prove executable overlay precedence with a one-file game tree.
            manifest["runtime_requirements"] = {}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            modded_exe_name = "Virtual Families 2 - Modded B150.exe"

            all_enabled_output = tmp_path / "all-enabled"
            self.run_patcher(
                "apply",
                "--game-dir",
                str(game),
                "--manifest",
                str(manifest_path),
                "--output-dir",
                str(all_enabled_output),
                "--enable-all",
            )
            all_features = (
                "core_executable",
                "island_events",
                "cheat_upgrades",
                "holiday_ornaments_collection",
                "behavior_patches",
            )
            self.assertEqual(
                (all_enabled_output / modded_exe_name).read_bytes(),
                source_data_by_requires[all_features],
            )

            behavior_off_output = tmp_path / "behavior-off"
            self.run_patcher(
                "apply",
                "--game-dir",
                str(game),
                "--manifest",
                str(manifest_path),
                "--output-dir",
                str(behavior_off_output),
                "--enable-all",
                "--disable",
                "behavior_patches",
            )
            nonbehavior_features = (
                "core_executable",
                "island_events",
                "cheat_upgrades",
                "holiday_ornaments_collection",
            )
            self.assertEqual(
                (behavior_off_output / modded_exe_name).read_bytes(),
                source_data_by_requires[nonbehavior_features],
            )

            behavior_only_output = tmp_path / "behavior-only"
            self.run_patcher(
                "apply",
                "--game-dir",
                str(game),
                "--manifest",
                str(manifest_path),
                "--output-dir",
                str(behavior_only_output),
                "--disable-all",
                "--enable",
                "core_executable,behavior_patches",
            )
            self.assertEqual(
                (behavior_only_output / modded_exe_name).read_bytes(),
                source_data_by_requires[("core_executable", "behavior_patches")],
            )

    def test_exe_replacement_can_reuse_target_identity_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            (build / "VF2-B145-Core.exe").write_bytes(b"patched-binary")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            identity_manifest = tmp_path / "identity.json"
            identity_manifest.write_text(
                json.dumps(
                    {
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "pe_structures": [
                                    {
                                        "format": "pe32-section-raw-v1",
                                        "machine": "0x14c",
                                        "pe_offset": "0x130",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--patched-exe",
                "VF2-B145-Core.exe",
                "--target-identity-manifest",
                str(identity_manifest),
                "--asset-mode",
                "additive",
                "--include-exe-replacement",
                "--name",
                "B145",
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            core_exe = next(row for row in manifest["asset_patches"] if row["file_path"] == "Virtual Families 2.exe")
            self.assertEqual(core_exe["output_file_path"], "Virtual Families 2 - Modded B145.exe")
            self.assertEqual(core_exe["expected_target_pe_structures"][0]["pe_offset"], "0x130")
            self.assertEqual(manifest["target_files"][0]["pe_structures"][0]["pe_offset"], "0x130")
            self.assertEqual(manifest["export_summary"]["native_patch_status"]["status"], "target_identity_reused")
            self.assertFalse(manifest["export_summary"]["requires_vanilla_exe_for_apply"])

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

    def test_optional_song_mods_target_sounds_from_source_only_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            songs = tmp_path / "songs"
            original_sounds = build / "Original Virtual Families 2 Assets" / "originalsounds"
            (base / "Sounds").mkdir(parents=True)
            song_names = ["menu.ogg", "song1.ogg", "song2.ogg", "song3.ogg", "song4.ogg"]
            for name in song_names:
                (base / "Sounds" / name).write_bytes(f"vanilla target {name}".encode("ascii"))
            build.mkdir()
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            original_sounds.mkdir(parents=True)
            songs.mkdir()
            for name in song_names:
                (songs / name).write_bytes(f"optional {name}".encode("ascii"))
                (original_sounds / name).write_bytes(f"restore {name}".encode("ascii"))

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--optional-song-mods-dir",
                str(songs),
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            asset_by_path = {row["file_path"]: row for row in manifest["asset_patches"]}
            for name in song_names:
                song = asset_by_path[f"Sounds/{name}"]
                self.assertEqual(song["requires"], ["optional_song_mods"])
                self.assertEqual(song["source_path"], f"payload/OptionalSongMods/{name}")
                self.assertEqual(song["restore_source_path"], f"payload/Original Virtual Families 2 Assets/originalsounds/{name}")
                self.assertEqual(song["expected_target_size"], len(f"vanilla target {name}".encode("ascii")))
                self.assertTrue((out / "payload" / "OptionalSongMods" / name).is_file())
                self.assertTrue((out / "payload" / "Original Virtual Families 2 Assets" / "originalsounds" / name).is_file())
                self.assertFalse((out / "payload" / "Sounds" / name).exists())
            settings_by_id = {row["id"]: row for row in manifest["settings"]}
            self.assertEqual(settings_by_id["optional_song_mods"]["category"], "optional")

    def test_invisible_upgrades_target_images_upgrades_from_source_only_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            invisible = tmp_path / "invisible_upgrades"
            original = tmp_path / "original_upgrades"
            build.mkdir()
            invisible.mkdir()
            original.mkdir()
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            (invisible / "toolwall.png").write_bytes(b"invisible toolwall")
            (original / "toolwall.png").write_bytes(b"original toolwall")

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--invisible-upgrades-dir",
                str(invisible),
                "--original-upgrades-dir",
                str(original),
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            asset_by_path = {row["file_path"]: row for row in manifest["asset_patches"]}
            record = asset_by_path["Images/Upgrades/toolwall.png"]
            self.assertEqual(record["requires"], ["invisible_upgrades_graphics"])
            self.assertEqual(record["source_path"], "payload/OptionalVisualMods/Invisible Workspace Upgrades/invisible images/toolwall.png")
            self.assertEqual(record["restore_source_path"], "payload/OptionalVisualMods/Invisible Workspace Upgrades/original images/toolwall.png")
            self.assertTrue((out / "payload" / "OptionalVisualMods" / "Invisible Workspace Upgrades" / "invisible images" / "toolwall.png").is_file())
            self.assertTrue((out / "payload" / "OptionalVisualMods" / "Invisible Workspace Upgrades" / "original images" / "toolwall.png").is_file())
            settings_by_id = {row["id"]: row for row in manifest["settings"]}
            self.assertEqual(settings_by_id["invisible_upgrades_graphics"]["category"], "optional")
            self.assertFalse(settings_by_id["invisible_upgrades_graphics"]["default"])

    def test_disable_all_refreshes_existing_modded_output_to_vanilla(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game = tmp_path / "Virtual Families 2"
            manifest_path = tmp_path / "manifest.json"
            output = tmp_path / "VF2-B104-Modded"
            (game / "Images").mkdir(parents=True)
            (game / "Images" / "main_BG.png").write_bytes(b"vanilla")
            vanilla_exe = minimal_pe_bytes()
            (game / "Virtual Families 2.exe").write_bytes(vanilla_exe)
            (output / "Images").mkdir(parents=True)
            (output / "Images" / "main_BG.png").write_bytes(b"modded")
            (output / ".vf2_patch_backups").mkdir()
            manifest_path.write_text(
                json.dumps(
                    {
                        "settings": [
                            {"id": "transparent_menu_bar", "default": True},
                        ],
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "sha256": hashlib.sha256(vanilla_exe).hexdigest(),
                                "size": len(vanilla_exe),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/main_BG.png",
                                "source_path": "payload/main_BG.png",
                                "source_sha256": hashlib.sha256(b"modded").hexdigest(),
                                "source_size": len(b"modded"),
                                "overwrite_existing": True,
                                "requires": ["transparent_menu_bar"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (tmp_path / "payload").mkdir()
            (tmp_path / "payload" / "main_BG.png").write_bytes(b"modded")

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game),
                "--manifest",
                str(manifest_path),
                "--output-dir",
                str(output),
                "--disable-all",
            )

            self.assertEqual((output / "Images" / "main_BG.png").read_bytes(), b"vanilla")
            log_path = next((output / ".vf2_patch_backups").glob("*/patch_log.json"))
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(log["status"], "success")
            self.assertEqual(log["settings"]["enabled"], [])
            self.assertEqual(log["settings"]["disabled"], ["transparent_menu_bar"])

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
            self.assertNotIn("Images/stale.png", {row["file_path"] for row in manifest["asset_patches"]})

    def test_bundle_asset_source_audit_rejects_missing_source(self):
        import export_offline_patch_bundle as exporter

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                exporter.validate_bundle_asset_sources(
                    tmp_path,
                    [
                        {
                            "file_path": "Images/missing.png",
                            "source_path": "payload/Images/missing.png",
                        }
                    ],
                )

    def test_bundle_asset_source_audit_rejects_absolute_source(self):
        import export_offline_patch_bundle as exporter

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with self.assertRaises(ValueError):
                exporter.validate_bundle_asset_sources(
                    tmp_path,
                    [
                        {
                            "file_path": "Images/bad.png",
                            "source_path": str(tmp_path / "outside.png"),
                        }
                    ],
                )

    def test_payload_pruning_keeps_only_manifest_referenced_sources(self):
        import export_offline_patch_bundle as exporter

        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            keep = bundle / "payload" / "Images" / "keep.png"
            restore = bundle / "payload" / "Original" / "restore.png"
            orphan = bundle / "payload" / "Unused" / "orphan.png"
            for path, data in ((keep, b"keep"), (restore, b"restore"), (orphan, b"orphan")):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)

            records = [
                {
                    "source_path": "payload/Images/keep.png",
                    "source_sha256": hashlib.sha256(b"keep").hexdigest(),
                    "source_size": len(b"keep"),
                    "restore_source_path": "payload/Original/restore.png",
                    "restore_source_sha256": hashlib.sha256(b"restore").hexdigest(),
                    "restore_source_size": len(b"restore"),
                }
            ]
            summary = exporter.prune_unreferenced_payload_files(bundle, records)

            self.assertTrue(keep.is_file())
            self.assertTrue(restore.is_file())
            self.assertFalse(orphan.exists())
            self.assertFalse(orphan.parent.exists())
            self.assertEqual(summary["removed_file_count"], 1)
            self.assertEqual(summary["removed_bytes"], len(b"orphan"))
            self.assertEqual(summary["retained_file_count"], 2)
            self.assertEqual(summary["retained_bytes"], len(b"keep") + len(b"restore"))
            exporter.validate_bundle_asset_sources(bundle, records)
            keep.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                exporter.validate_bundle_asset_sources(bundle, records)


if __name__ == "__main__":
    unittest.main()
