#!/usr/bin/env python3
import json
import shutil
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
import offline_vf2_patcher as patcher


def minimal_pe_bytes(
    with_older_pregnancy_flag=False,
    marker=0,
    with_older_mortality_flag=False,
    mortality_marker=0,
    with_holiday_goal_flag=False,
    goal_marker=0,
    with_mobile_furniture_behavior_flag=False,
    behavior_marker=0,
    with_same_sex_marriage_flag=False,
    same_sex_marker=0,
    with_store_scroll_bar_flag=False,
    store_scroll_bar_marker=0,
):
    runtime_flags = []
    if with_older_pregnancy_flag:
        runtime_flags.append((".vf2preg", marker))
    if with_older_mortality_flag:
        runtime_flags.append((".vf2mort", mortality_marker))
    if with_holiday_goal_flag:
        runtime_flags.append((".vf2goal", goal_marker))
    if with_mobile_furniture_behavior_flag:
        runtime_flags.append((".vf2beh", behavior_marker))
    if with_same_sex_marriage_flag:
        runtime_flags.append((".vf2same", same_sex_marker))
    if with_store_scroll_bar_flag:
        runtime_flags.append((".vf2scrl", store_scroll_bar_marker))
    # Three or more runtime-flag sections extend the PE section table past
    # 0x200, so shift those coexistence fixtures by one file-alignment block.
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
        data[flag_sect:flag_sect + 8] = section_name.encode("ascii").ljust(8, b"\0")
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
    def test_default_settings_expose_linked_behavior_overlay_for_player_qa(self):
        available = set(exporter.SOURCE_BACKED_OPTIONAL_SETTINGS) | {"core_executable"}
        settings = exporter.default_settings(False, True, available)
        by_id = {row["id"]: row for row in settings}

        with self.subTest(setting_id="behavior_patches"):
            readiness = by_id["behavior_patches"]["readiness"]
            self.assertEqual(readiness["status"], "ready_for_player_qa")
            self.assertTrue(readiness["runtime_ready"])
            self.assertTrue(readiness["linked"])
            self.assertIn("player", readiness["reason"])
            self.assertTrue(readiness["reason"])
        for setting_id in ("mobile_furniture_behaviors", "mobile_sound_assets"):
            with self.subTest(setting_id=setting_id):
                self.assertTrue(by_id[setting_id]["default"])
                readiness = by_id[setting_id]["readiness"]
                self.assertEqual(readiness["status"], "ready_for_player_qa")
                self.assertTrue(readiness["runtime_ready"])
                self.assertTrue(readiness["linked"])
                self.assertIn("player", readiness["reason"])
                self.assertTrue(readiness["reason"])
        for setting_id in ("mobile_renovations", "ai_generated_bathroom2_renovations"):
            with self.subTest(setting_id=setting_id):
                readiness = by_id[setting_id]["readiness"]
                self.assertEqual(readiness["status"], "ready_for_player_qa")
                self.assertTrue(readiness["runtime_ready"])
                self.assertTrue(readiness["linked"])
                self.assertIn("player", readiness["reason"])
        island_readiness = by_id["island_events"]["readiness"]
        self.assertEqual(island_readiness["status"], "ready_for_player_qa")
        self.assertTrue(island_readiness["runtime_ready"])
        self.assertTrue(island_readiness["linked"])
        self.assertIn("player", island_readiness["reason"])
        self.assertNotIn("readiness", exporter.SETTINGS[0])

        parsed = patcher.manifest_settings({"settings": settings})
        island = parsed["island_events"]
        self.assertFalse(island.blocked)
        island_log = next(row for row in patcher.settings_log(parsed, set())["available"] if row["id"] == "island_events")
        self.assertTrue(island_log["selectable"])
        self.assertEqual(island_log["readiness_status"], "ready_for_player_qa")
        self.assertIsNone(island_log["readiness_reason"])

        _resolved, enabled = patcher.resolve_enabled_settings(
            {"settings": settings},
            patcher.argparse.Namespace(
                enable_all=True,
                disable_all=False,
                enable=None,
                disable=None,
            ),
        )
        self.assertIn("behavior_patches", enabled)

    def test_no_ai_icon_generator_uses_tracked_source_art(self):
        generator = (ROOT / "work" / "build_no_ai_icons.py").read_text(encoding="utf-8")
        self.assertIn('ROOT / "patcher_assets" / "optional_patches" / "no_ai_icons" / "source_art"', generator)
        self.assertNotIn('ROOT / "work" / "assets" / "no_ai_icons" / "raw"', generator)
        source_art = ROOT / "patcher_assets" / "optional_patches" / "no_ai_icons" / "source_art"
        self.assertEqual(len(list(source_art.glob("*.png"))), 16)
        self.assertEqual(
            exporter.NO_AI_ICON_REPLACEMENT_PROVENANCE["cheat_reset_achievements.png"],
            "patcher_assets/optional_patches/no_ai_icons/source_art/Icon_Resort_Improvement.png",
        )
        self.assertEqual(
            exporter.NO_AI_ICON_REPLACEMENT_PROVENANCE["cheat_trophy_gold2x.png"],
            "patcher_assets/optional_patches/no_ai_icons/source_art/trophy_gold2x.png",
        )
        trophy_source = source_art / "trophy_gold2x.png"
        self.assertEqual(
            hashlib.sha256(trophy_source.read_bytes()).hexdigest().upper(),
            "7ACFEA13C00BCC46141C5ECE8F4A3D0448D39BF5F8F063F16839D9D0197FB3B6",
        )

    def test_final_playtest_profile_is_manifest_local_and_keeps_no_ai_off(self):
        self.assertNotIn("same_sex_marriage", exporter.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS)
        original_defaults = {row["id"]: row["default"] for row in exporter.SETTINGS}
        available = set(exporter.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS) | {"core_executable"}
        settings = [dict(row) for row in exporter.SETTINGS]
        next(row for row in settings if row["id"] == "no_ai_icons")["default"] = True
        updated = exporter.apply_final_playtest_defaults(settings, available)
        updated_by_id = {row["id"]: row for row in updated}
        for setting_id in exporter.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS:
            self.assertTrue(updated_by_id[setting_id]["default"], setting_id)
        self.assertFalse(updated_by_id["same_sex_marriage"]["default"])
        self.assertFalse(updated_by_id["no_ai_icons"]["default"])
        for setting_id in (
            "custom_lorsieab2_map_images",
            "transparent_menu_bar",
            "transparent_store_bar",
            "transparent_decor_tab",
            "optional_visual_mod_graphics",
        ):
            self.assertFalse(updated_by_id[setting_id]["default"], setting_id)
        self.assertEqual(
            original_defaults,
            {row["id"]: row["default"] for row in exporter.SETTINGS},
        )

    def test_final_playtest_profile_allows_absent_explicitly_off_optional_setting(self):
        settings = [
            dict(row)
            for row in exporter.SETTINGS
            if row["id"] != "no_ai_icons"
        ]
        updated = exporter.apply_final_playtest_defaults(
            settings,
            set(exporter.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS),
        )
        updated_by_id = {row["id"]: row for row in updated}
        self.assertNotIn("no_ai_icons", updated_by_id)
        for setting_id in exporter.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS:
            self.assertTrue(updated_by_id[setting_id]["default"], setting_id)

    def test_final_playtest_profile_fails_closed_when_feature_record_is_missing(self):
        settings = [dict(row) for row in exporter.SETTINGS]
        with self.assertRaisesRegex(ValueError, "missing required feature records"):
            exporter.apply_final_playtest_defaults(
                settings,
                set(exporter.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS) - {"mobile_sound_assets"},
            )

    def test_final_playtest_profile_exposes_one_all_five_native_overlay(self):
        self.assertEqual(
            exporter.FINAL_PLAYTEST_NATIVE_REQUIRES,
            [
                "core_executable",
                "behavior_patches",
                "cheat_upgrades",
                "holiday_ornaments_collection",
                "island_events",
                "mobile_renovations",
            ],
        )
        source = EXPORTER.read_text(encoding="utf-8")
        self.assertIn('"Final All-Enabled Native"', source)
        self.assertIn('"native_overlay_requires": FINAL_PLAYTEST_NATIVE_REQUIRES', source)

    def test_merged_native_overlay_inputs_keep_mobile_dependency_and_explicit_final_source(self):
        source = EXPORTER.read_text(encoding="utf-8")
        self.assertIn("--final-playtest-native-exe", source)
        self.assertIn("--native-overlays-include-mobile-renovations", source)
        self.assertIn("requires if \"mobile_renovations\" in requires else [*requires, \"mobile_renovations\"]", source)
        self.assertIn("overlay_specs[final_index] = final_spec", source)
        # The "final source" must genuinely be distinct from the plain core
        # executable, not merely present as a variable name: see
        # test_final_playtest_all_enabled_rejects_reusing_the_core_executable
        # for the behavioral guarantee. A bare
        # "final_playtest_native_exe or patched_exe" fallback with no
        # byte-identity check is exactly the bug that shipped in B162.
        self.assertIn("sha256_file(final_source) == sha256_file(patched_exe)", source)

    def test_b156_uses_stable_modded_folder_exe_and_save_names(self):
        self.assertEqual(exporter.modded_output_folder_name("B156"), "Virtual Families 2 - Modded")
        self.assertEqual(exporter.modded_exe_output_name("B156"), "Virtual Families 2 - Modded.exe")
        self.assertEqual(exporter.modded_save_folder_name("B156"), "Virtual Families 2 - Modded")

    def test_decimal_build_label_is_preserved(self):
        self.assertEqual(
            exporter.infer_build_label(Path("VF2-Patcher-B155.5")),
            "B155.5",
        )
        self.assertEqual(
            exporter.infer_build_label(Path("bundle"), "manifest-B155.5.json"),
            "B155.5",
        )

    def test_b156_settings_have_no_experimental_section_or_expanded_map(self):
        settings_by_id = {row["id"]: row for row in exporter.SETTINGS}

        self.assertNotIn("expand_game_map", settings_by_id)
        self.assertNotIn(
            "experimental",
            {row["category"] for row in exporter.SETTINGS},
        )
        for setting_id in (
            "allow_older_pregnancies",
            "same_sex_marriage",
            "older_villager_mortality",
            "mobile_furniture_behaviors",
            "mobile_renovations",
        ):
            with self.subTest(setting_id=setting_id):
                self.assertEqual(settings_by_id[setting_id]["category"], "optional")
        cheat_description = settings_by_id["cheat_upgrades"]["description"]
        self.assertIn("0xE1-0xEA", cheat_description)
        self.assertIn("rebuilds the native content map", cheat_description)

    def test_mobile_renovation_assets_require_the_toggle_and_core_executable(self):
        self.assertEqual(
            exporter.setting_for_asset(Path("Images/MobileRenovations/tp238_beige_kitchen.png")),
            "mobile_renovations",
        )
        self.assertEqual(
            exporter.asset_requires_for_setting("mobile_renovations"),
            ["core_executable", "mobile_renovations"],
        )
        self.assertEqual(
            exporter.setting_for_asset(
                Path("Images") / "curtain_closed_southb.png"
            ),
            "mobile_renovations",
        )
        self.assertEqual(
            exporter.loose_optional_visual_target(
                Path("Mobile Renovations") / "curtain_closed_southb.png"
            ),
            Path("Images") / "curtain_closed_southb.png",
        )

    def test_ai_bathroom2_setting_is_default_off_with_exact_provenance(self):
        settings_by_id = {row["id"]: row for row in exporter.SETTINGS}
        setting = settings_by_id["ai_generated_bathroom2_renovations"]
        self.assertEqual(
            setting["label"],
            "2nd Bathroom Mobile-Style Renovations (AI-Generated Art Warning)",
        )
        self.assertFalse(setting["default"])
        self.assertEqual(setting["category"], "optional")
        self.assertIn("AI-generated", setting["description"])
        self.assertIn("Bathroom 1's mobile renovations art", setting["description"])
        self.assertEqual(
            exporter.setting_for_asset(
                Path("OptionalVisualMods") / exporter.AI_BATHROOM2_OPTIONAL_FOLDER / "bathroom2_ai_blue.png"
            ),
            "ai_generated_bathroom2_renovations",
        )
        self.assertEqual(
            exporter.setting_for_asset(
                Path("Images") / "AIGeneratedBathroom2" / "bathroom2_ai_blue.png"
            ),
            "ai_generated_bathroom2_renovations",
        )
        self.assertEqual(
            exporter.asset_requires_for_setting("ai_generated_bathroom2_renovations"),
            ["core_executable", "ai_generated_bathroom2_renovations"],
        )
        self.assertIn(
            "ai_generated_bathroom2_renovations",
            exporter.OUTPUT_ONLY_REMOVABLE_ASSET_SETTINGS,
        )

    def test_ai_bathroom2_asset_source_option_is_exported_separately_from_exe_matrix(self):
        source = EXPORTER.read_text(encoding="utf-8")
        self.assertIn("--ai-generated-bathroom2-dir", source)
        self.assertIn('"ai_generated_bathroom2_renovations"', source)

    def test_mobile_sound_setting_is_default_on_for_player_qa_and_core_gated(self):
        settings_by_id = {row["id"]: row for row in exporter.SETTINGS}
        self.assertEqual(settings_by_id["mobile_sound_assets"]["category"], "optional")
        self.assertTrue(settings_by_id["mobile_sound_assets"]["default"])
        self.assertEqual(
            exporter.asset_requires_for_setting("mobile_sound_assets"),
            ["core_executable", "mobile_sound_assets"],
        )
        for filename in exporter.MOBILE_SOUND_ASSET_FILES:
            self.assertEqual(
                exporter.setting_for_asset(Path("Sounds") / filename),
                "mobile_sound_assets",
            )

    def test_native_core_settings_require_matching_manifest_evidence(self):
        manifest = {
            "InventoryManager": {
                "pet_store_additions": [
                    {"name": "Turtle", "item_id": "0x245"},
                    {"name": "Hamster", "item_id": "0x247"},
                ]
            },
            "VisibleSpecialUpgrades": {
                "added_items": [
                    {"item_id": item_id}
                    for item_id in ("0x117", "0x118", "0x119", "0x11a")
                ]
            },
            "theStringManager": {
                "updated_existing_strings": [
                    {"old": old, "new": new}
                    for old, new in (
                        ("{name} sees pet", "{name} sees their adorable pet."),
                        ("Cooking like mommy", "Cooking like a grownup"),
                        ("Driving like daddy", "Driving like a grownup"),
                        ("Not feeling fresh", "Not feeling clean"),
                    )
                ]
            },
        }
        self.assertEqual(
            exporter.native_core_settings_available(manifest, True),
            {"unused_pets", "text_fixes", "mobile_purchases"},
        )
        self.assertEqual(exporter.native_core_settings_available(manifest, False), set())
        self.assertNotIn(
            "unused_pets",
            exporter.native_core_settings_available({}, True),
        )

        settings = exporter.default_settings(
            include_byte_patches=False,
            include_exe_replacement=True,
            available_settings={
                "core_executable",
                "unused_pets",
                "text_fixes",
                "mobile_purchases",
            },
        )
        by_id = {row["id"]: row for row in settings}
        for setting_id in ("unused_pets", "text_fixes", "mobile_purchases"):
            with self.subTest(setting_id=setting_id):
                self.assertIn(setting_id, by_id)
                self.assertTrue(by_id[setting_id]["default"])

    def test_no_ai_icons_setting_is_default_off_and_cheat_gated(self):
        settings_by_id = {row["id"]: row for row in exporter.SETTINGS}
        setting = settings_by_id["no_ai_icons"]
        self.assertEqual(setting["label"], "No AI Icons")
        self.assertFalse(setting["default"])
        self.assertEqual(setting["category"], "optional")
        self.assertIn("other LDW games", setting["description"])
        self.assertIn("online art sources", setting["description"])
        self.assertIn("custom-made", setting["description"])
        self.assertIn("late Special Upgrade icon PNGs", setting["description"])
        self.assertIn("Disabling restores", setting["description"])
        self.assertEqual(
            exporter.asset_requires_for_setting("no_ai_icons"),
            ["core_executable", "cheat_upgrades", "no_ai_icons"],
        )
        self.assertEqual(
            exporter.setting_for_asset(
                Path("OptionalVisualMods") / "No AI Icons" / "cheat_marriage_email.png"
            ),
            "no_ai_icons",
        )

    def test_no_ai_icon_records_are_complete_and_have_current_icon_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = root / "build"
            base = root / "base"
            bundle = root / "bundle"
            (build / "Images").mkdir(parents=True)
            (base / "Images").mkdir(parents=True)
            for filename in exporter.NO_AI_ICON_TARGETS:
                (build / "Images" / filename).write_bytes(f"current-{filename}".encode("ascii"))

            records = exporter.no_ai_icon_asset_patches(bundle, build, base)
            self.assertEqual(
                [row["file_path"] for row in records],
                [f"Images/{filename}" for filename in exporter.NO_AI_ICON_TARGETS],
            )
            self.assertEqual(len(records), 15)
            for record in records:
                self.assertEqual(
                    record["requires"],
                    ["core_executable", "cheat_upgrades", "no_ai_icons"],
                )
                self.assertEqual(
                    record["restore_requires"],
                    ["core_executable", "cheat_upgrades"],
                )
                self.assertEqual(
                    (bundle / record["restore_source_path"]).read_bytes(),
                    (build / record["file_path"]).read_bytes(),
                )
                replacement_name = exporter.NO_AI_ICON_REPLACEMENT_FILES.get(
                    Path(record["file_path"]).name,
                    Path(record["file_path"]).name,
                )
                self.assertEqual(
                    (bundle / record["source_path"]).read_bytes(),
                    (exporter.NO_AI_ICON_SOURCE_DIR / replacement_name).read_bytes(),
                )

    def test_no_ai_icon_generation_fails_closed_when_source_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "no_ai_icons"
            source.mkdir()
            build = root / "build"
            base = root / "base"
            bundle = root / "bundle"
            old_source = exporter.NO_AI_ICON_SOURCE_DIR
            try:
                exporter.NO_AI_ICON_SOURCE_DIR = source
                with self.assertRaisesRegex(ValueError, "source set is incomplete"):
                    exporter.no_ai_icon_asset_patches(bundle, build, base)
                self.assertFalse((bundle / "payload").exists())
            finally:
                exporter.NO_AI_ICON_SOURCE_DIR = old_source

    def test_mobile_sound_routes_emit_four_exact_sha_atomic_records(self):
        routes = [
            {
                "pc_filename": pc,
                "mobile_filename": mobile,
                "object_offset": exporter.MOBILE_SOUND_ROUTE_PINS[pc][1],
                "expected_bytes": pc.encode("ascii").hex(),
                "replacement_bytes": mobile.encode("ascii").hex(),
            }
            for pc, mobile in (
                ("beaker.wav", "beaker.ogg"),
                ("Child3.wav", "Child3.ogg"),
                ("Child7.wav", "Child7.ogg"),
                ("Child8.wav", "Child8.ogg"),
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            exe = tmp / "core.exe"
            exe.write_bytes(b"prefix" + b"".join(row["pc_filename"].encode("ascii") for row in routes))
            records = exporter.mobile_sound_assets_post_asset_patches(
                [exe],
                output_exe_name="Virtual Families 2 - Modded B158.exe",
                build_manifest_data={"MobileSoundAssets": {"routes": routes}},
                allowed_source_sha256s={hashlib.sha256(exe.read_bytes()).hexdigest()},
            )
            self.assertEqual(len(records), 4)
            self.assertTrue(all(row["requires"] == ["core_executable", "mobile_sound_assets"] for row in records))
            self.assertTrue(all(len(row["variants"]) == 1 for row in records))
            self.assertEqual(len({row["variants"][0]["result_asset_sha256"] for row in records}), 1)
            self.assertEqual(
                {row["variants"][0]["expected_asset_bytes"] for row in records},
                {pc.encode("ascii").hex().upper() for pc, _mobile in (
                    ("beaker.wav", "beaker.ogg"),
                    ("Child3.wav", "Child3.ogg"),
                    ("Child7.wav", "Child7.ogg"),
                    ("Child8.wav", "Child8.ogg"),
                )},
            )

            with self.assertRaisesRegex(ValueError, "not authenticated"):
                exporter.mobile_sound_assets_post_asset_patches(
                    [exe],
                    output_exe_name="Virtual Families 2 - Modded B158.exe",
                    build_manifest_data={"MobileSoundAssets": {"routes": routes}},
                    allowed_source_sha256s={"0" * 64},
                )

    def test_store_scroll_bar_marker_emits_authenticated_per_exe_variant(self):
        contract = {
            "StoreScrollBar": {
                "runtime_flag": {
                    "symbol": "_gVF2StoreScrollbar",
                    "source_section": ".vf2scrl",
                    "size": 1,
                    "default": "00",
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "core.exe"
            second = root / "overlay.exe"
            first.write_bytes(minimal_pe_bytes(with_store_scroll_bar_flag=True))
            second_data = bytearray(minimal_pe_bytes(with_store_scroll_bar_flag=True))
            second_data[0x200] ^= 0x7F
            second.write_bytes(second_data)
            hashes = {
                hashlib.sha256(first.read_bytes()).hexdigest(),
                hashlib.sha256(second.read_bytes()).hexdigest(),
            }
            records = exporter.store_scroll_bar_post_asset_patches(
                [first, second],
                output_exe_name="Virtual Families 2 - Modded B158.exe",
                build_manifest_data=contract,
                allowed_source_sha256s=hashes,
            )
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record["requires"], ["core_executable", "store_scroll_bar"])
            self.assertEqual(len(record["variants"]), 2)
            self.assertEqual({row["offset"] for row in record["variants"]}, {"0x400"})
            self.assertEqual({row["expected_asset_bytes"] for row in record["variants"]}, {"00"})
            self.assertEqual({row["replacement_bytes"] for row in record["variants"]}, {"01"})
            self.assertTrue(all(len(row["result_asset_sha256"]) == 64 for row in record["variants"]))

            with self.assertRaisesRegex(ValueError, "default byte mismatch"):
                bad = root / "bad.exe"
                bad.write_bytes(minimal_pe_bytes(with_store_scroll_bar_flag=True, store_scroll_bar_marker=1))
                exporter.store_scroll_bar_post_asset_patches(
                    [bad],
                    output_exe_name="Virtual Families 2 - Modded B158.exe",
                    build_manifest_data=contract,
                    allowed_source_sha256s={hashlib.sha256(bad.read_bytes()).hexdigest()},
                )

    def test_store_scroll_bar_manifest_setting_requires_active_post_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            build = root / "build"
            out = root / "bundle"
            vanilla = root / "Virtual Families 2.exe"
            base.mkdir()
            build.mkdir()
            patched = build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
            patched.write_bytes(minimal_pe_bytes(with_store_scroll_bar_flag=True))
            vanilla.write_bytes(minimal_pe_bytes())
            (build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "StoreScrollBar": {
                            "runtime_flag": {
                                "symbol": "_gVF2StoreScrollbar",
                                "source_section": ".vf2scrl",
                                "size": 1,
                                "default": "00",
                            }
                        }
                    }
                ),
                encoding="ascii",
            )
            self.run_exporter(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(out),
                "--vanilla-exe", str(vanilla),
                "--include-exe-replacement",
            )
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            settings = {row["id"] for row in manifest["settings"]}
            self.assertIn("store_scroll_bar", settings)
            records = [
                row for row in manifest["post_asset_patches"]
                if row["requires"] == ["core_executable", "store_scroll_bar"]
            ]
            self.assertEqual(len(records), 1)
            variant = records[0]["variants"][0]
            enabled = bytearray(patched.read_bytes())
            enabled[0x400] = 1
            self.assertEqual(
                variant["result_asset_sha256"],
                hashlib.sha256(bytes(enabled)).hexdigest(),
            )

    def test_mobile_sound_assets_stage_pinned_oggs(self):
        # The restore records this asserts are built by hashing each original
        # PC sound in the base payload, so without work/vanilla_runtime_payload
        # (gitignored, absent from a fresh clone) every record comes back with
        # no restore_source_path and the assertion below reads as a product
        # failure. Skip on the missing input instead, the way the release-ZIP
        # tests in this suite already do.
        if not exporter.DEFAULT_BASE_PAYLOAD.is_dir():
            self.skipTest(
                "work/vanilla_runtime_payload is not present; "
                "cannot compute sound restore records"
            )
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bundle = tmp / "bundle"
            base = exporter.DEFAULT_BASE_PAYLOAD
            bundle.mkdir()
            records = exporter.mobile_sound_asset_patches(
                bundle,
                base,
                exporter.MOBILE_SOUND_ASSET_SOURCE_DIR,
            )
            self.assertEqual(len(records), 67)
            self.assertEqual(sum(bool(row["remove_when_disabled"]) for row in records), 4)
            self.assertEqual(sum("restore_source_path" in row for row in records), 63)
            self.assertEqual(
                {Path(row["file_path"]).name for row in records},
                set(exporter.MOBILE_SOUND_ASSET_FILES),
            )
            for filename in exporter.MOBILE_SOUND_ASSET_FILES:
                self.assertTrue((bundle / "payload" / "MobileSoundAssets" / filename).is_file())

    def test_mobile_sound_assets_reject_partial_or_corrupt_sources_before_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            for filename in exporter.MOBILE_SOUND_ASSET_FILES[:-1]:
                shutil.copy2(exporter.MOBILE_SOUND_ASSET_SOURCE_DIR / filename, source / filename)
            bundle = root / "bundle"
            base = root / "base"
            bundle.mkdir()
            base.mkdir()
            with self.assertRaisesRegex(ValueError, "Missing mobile sound asset"):
                exporter.mobile_sound_asset_patches(bundle, base, source)
            self.assertFalse((bundle / "payload" / "MobileSoundAssets").exists())

            shutil.copy2(
                exporter.MOBILE_SOUND_ASSET_SOURCE_DIR / exporter.MOBILE_SOUND_ASSET_FILES[-1],
                source / exporter.MOBILE_SOUND_ASSET_FILES[-1],
            )
            corrupt = source / exporter.MOBILE_SOUND_ASSET_FILES[0]
            corrupt.write_bytes(corrupt.read_bytes() + b"corrupt")
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                exporter.mobile_sound_asset_patches(bundle, base, source)
            self.assertFalse((bundle / "payload" / "MobileSoundAssets").exists())

    def test_late_special_upgrade_icons_are_gated_by_cheat_overlay(self):
        for filename in (
            "cheat_no_coins.png",
            "cheat_no_food.png",
            "cheat_add_coins.png",
            "cheat_add_food.png",
            "cheat_no_generation_locks.png",
            "cheat_reset_achievements.png",
            "cheat_fill_house_messes.png",
            "cheat_marriage_email.png",
            "cheat_next_pregnancy_triplets.png",
        ):
            with self.subTest(filename=filename):
                self.assertEqual(
                    exporter.setting_for_asset(Path("Images") / filename),
                    "cheat_upgrades",
                )
        self.assertEqual(
            exporter.asset_requires_for_setting("cheat_upgrades"),
            ["core_executable", "cheat_upgrades"],
        )

        without_cheat = {
            row["id"]
            for row in exporter.default_settings(
                include_byte_patches=False,
                include_exe_replacement=True,
                available_settings={"core_executable", "mobile_renovations"},
            )
        }
        self.assertNotIn("cheat_upgrades", without_cheat)
        with_cheat = {
            row["id"]
            for row in exporter.default_settings(
                include_byte_patches=False,
                include_exe_replacement=True,
                available_settings={"core_executable", "cheat_upgrades"},
            )
        }
        self.assertIn("cheat_upgrades", with_cheat)

    def test_overlay_backed_assets_are_not_exposed_without_their_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            (build / "Images" / "MobileRenovations").mkdir(parents=True)
            (build / "Images" / "MobileRenovations" / "tp238_beige_kitchen.png").write_bytes(b"renovation")
            (build / "Images" / "cheat_reset_achievements.png").write_bytes(b"cheat icon")
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "generated_assets": [
                            {"path": "Images/MobileRenovations/tp238_beige_kitchen.png"},
                            {"path": "Images/cheat_reset_achievements.png"},
                        ]
                    }
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
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            records = {row["file_path"]: row for row in manifest["asset_patches"]}
            self.assertNotIn("Images/MobileRenovations/tp238_beige_kitchen.png", records)
            self.assertNotIn("Images/cheat_reset_achievements.png", records)
            setting_ids = {row["id"] for row in manifest["settings"]}
            self.assertNotIn("mobile_renovations", setting_ids)
            self.assertNotIn("cheat_upgrades", setting_ids)

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

    @staticmethod
    def mark_synthetic_settings_runtime_ready(manifest, *setting_ids):
        """Mark only synthetic overlay rows ready for selection tests."""
        readiness = manifest.setdefault("setting_readiness", {})
        for setting_id in setting_ids:
            ready = {
                "status": "verified",
                "runtime_ready": True,
                "linked": True,
                "reason": "Synthetic overlay fixture authenticated for selection tests.",
            }
            readiness[setting_id] = dict(ready)
            for row in manifest.get("settings", []):
                if isinstance(row, dict) and row.get("id") == setting_id:
                    row["readiness"] = dict(ready)

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
                with_same_sex_marriage_flag=True,
                same_sex_marker=0,
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
                        "SameSexMarriage": {
                            "runtime_flag": {
                                "source_section": ".vf2same",
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
            self.assertTrue(manifest["output"]["preserve_stock_exe_icon"])
            # This fixture uses a synthetic minimal PE without resources; icon
            # transfer has dedicated patcher tests with resource-bearing PEs.
            manifest["output"]["preserve_stock_exe_icon"] = False
            setting = {
                row["id"]: row for row in manifest["settings"]
            }["allow_older_pregnancies"]
            self.assertFalse(setting["default"])
            self.assertEqual(setting["category"], "optional")
            self.assertEqual(len(manifest["post_asset_patches"]), 4)
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
            same_sex_record = records["same_sex_marriage"]
            self.assertEqual(
                same_sex_record["requires"],
                ["core_executable", "same_sex_marriage"],
            )
            self.assertEqual(same_sex_record["variants"][0]["offset"], "0xc00")
            self.assertEqual(
                manifest["export_summary"]["post_asset_patch_count"],
                4,
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
            self.assertEqual(disabled_installed.read_bytes()[0xC00], 0)
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
            self.assertEqual(installed.read_bytes()[0xC00], 0)
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
            self.assertEqual(all_disabled[0xC00], 0)

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
                        with_mobile_furniture_behavior_flag=True,
                        with_same_sex_marriage_flag=True,
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
                    },
                    "MobileFurnitureBehaviors": {
                        "runtime_flag": {
                            "source_section": ".vf2beh",
                        }
                    },
                    "SameSexMarriage": {
                        "runtime_flag": {
                            "source_section": ".vf2same",
                        }
                    }
                },
            )
            self.assertEqual(len(records), 5)
            records_by_setting = {
                row["requires"][-1]: row for row in records
            }
            expected_offsets = {
                "allow_older_pregnancies": "0x600",
                "older_villager_mortality": "0x800",
                "holiday_furniture": "0xa00",
                "mobile_furniture_behaviors": "0xc00",
                "same_sex_marriage": "0xe00",
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
            self.assertEqual(
                hashes_by_setting["allow_older_pregnancies"],
                hashes_by_setting["mobile_furniture_behaviors"],
            )
            self.assertEqual(
                hashes_by_setting["allow_older_pregnancies"],
                hashes_by_setting["same_sex_marriage"],
            )

    def test_same_sex_marriage_post_asset_patch_skips_persisted_byte_manifest(self):
        # Same-Sex Marriage used to live in a free-standing custom PE
        # section (.vf2same) purely so this exporter's exact-SHA post-asset
        # patch could locate and flip it externally. That storage was
        # replaced with a byte inside CInventoryManager
        # (InventoryManager + itemId + 0x2A3) so the toggle actually
        # persists across a process relaunch/save reload -- see
        # patch_mobile_furniture_pack.py's VF2CheatToggleActiveByte(). The
        # new manifest shape has no source_section for this technique to
        # target, so the exporter must skip this one setting's external
        # toggle cleanly (return no records) instead of raising and
        # breaking the whole release build.
        records = exporter.same_sex_marriage_post_asset_patches(
            [],
            output_exe_name="Virtual Families 2 - Modded.exe",
            build_manifest_data={
                "SameSexMarriage": {
                    "runtime_hooks_installed": True,
                    "runtime_flag": {
                        "storage": "InventoryManager + 0x14C + 0x2A3 "
                            "(same persisted-byte convention as mobile "
                            "renovations/Bathroom 2)",
                        "size": 1,
                        "default": "00",
                        "enabled": "01",
                        "persistence": "part of the native save payload",
                    },
                }
            },
        )
        self.assertEqual(records, [])

    def test_mobile_furniture_behavior_assets_export_and_restore_exact_maps(self):
        expected_hashes = {
            "Chaise_blue.png.fmap": "a92512d05b37824c234463c08076083349b12c5b0ef8d06cabdf4178415f26cf",
            "Chaise_brown.png.fmap": "b0126fa4d05416af958f290262d5f2e20c9f3bb5fc3ab9058db6ae2674835948",
            "Chaise_green.png.fmap": "d3b472fccd0ffb1daeee22e51208d2cb87cf2f957628bcdd6042b0f77c5b05af",
            "Chaise_red.png.fmap": "ea914d7d2e7dc373f9a1dcf9cfdfca627ec9d826750ae2ab8d3d449399c9daaa",
            "Patio_umbrella.png.fmap": "c62d0320f781e57423b1b2dbfe4e474cf61e62b1dc36c7166d09041dbf7fed7d",
            "Patio_table.png.fmap": "0a60f9c579554876c15ae416d20fc313947f73ce3fb2a3a4eeb222beac6aab5d",
            "Picnic_table.png.fmap": "3d3aaeeeb77e7842cc20be211d8bcf415f85e6d8c6cd0e0f860a934c6cc45060",
            "Birthday_banner.png.fmap": "071c79932b55f382e3fe12be01a32f673ae9726339bd4295be3b35bf78456feb",
            "Balloons_birthday.png.fmap": "f66e4dc4776962b32b68e069a133ca9b1a7f57306d7df357866dd2630c307fc3",
            "Birthday_cake.png.fmap": "e1c55dc0d38b44003abe878cd9ccdfee3e49b5c7ed9e793d14b25c0fae57926d",
            "Birthday_presents.png.fmap": "63ef84177e87b4a4dd28c0a85c4aff2ee741423ca4ac34b3d273cb11fd4a18c5",
            "CandleOnHolder.png.fmap": "80d3f61d48e59fd55684edfb205670289fa6b15ba9768624ae318849a9f0bc11",
            "ChristmasTree1.png.fmap": "5907f7f60209d77d6c63b15b009243756c9f2c4d729134c41c105e0863b66926",
            "ChristmasTree2.png.fmap": "289e237d686f164dfd3e2293aeac248f5259e700125d963b4b578cefd642ccc8",
            "Dreidel.png.fmap": "44f21fc628cd90090f3eaf8eb1925de8d890fa5239828f55d115ae37c453b36a",
            "GlassOfEggnog.png.fmap": "22562ac31d52fcf4bb6b786423653566483166091c87255ca5e304d623a9b792",
            "Gnome1.png.fmap": "239f7adcae51ac9a16de74df90af1fbf532238b61614fc82670b2500bcaa8455",
            "Gnome2.png.fmap": "0b025200e7cb6c25a767bba703ae0ee8048769a69b1e18383e72b0ce2d6a6eb0",
            "Gnome3.png.fmap": "6b34222939bcfc60408d7ff60e3a3a93bd271398c393d53f0a60b1b173504662",
            "Gnome4.png.fmap": "37ed6f4e6b63a5b09a9bc82979535583038363efc8e44ca27af2a3d62abf8c93",
            "Gnome5.png.fmap": "0ee4bb4e95d8409b4539b6a5320eca417bd61dd641f4f6bd8d40f9fc2452cafb",
            "Menorah.png.fmap": "352ba4be943eae6a168a133430ccd6555c5feb41a630c118da2d24c019e39365",
            "PenguinDecoration.png.fmap": "12f2d782a2f570570f9126bb87cc3d9bb7bf4cd04881c6521d909ea7460277b8",
            "PlateOfCookies.png.fmap": "cb0bd7dfc1d1c32fed6c0219c52cc677e61375ad8146b5802c1efa1223a4d0d2",
            "PolarBearDecoration.png.fmap": "7640dc46d1769ce490f8032ae798203213600daaf13290acabc9252f6285d63a",
            "RedBow.png.fmap": "85fdcb318bb1549844173c5c10bf669d4c0a3a0b6de7dd7e1ae8c4e29d94035b",
            "ReindeerDecoration.png.fmap": "50f2d2293c64ad25b70cd0808b858af40f71156ffc816ae4512714e64b863e7c",
            "SantaGardenDecoration.png.fmap": "03f0c7e5ffcaa57ccb0f46ade96b4397add658d51e7a2ee18970ad1353f7e775",
            "SantaWallDecoration.png.fmap": "0cb058be3e24652008e20e0efaf1b101d6ddac6642aba1ce0d8b5ecf63a2eee1",
            "Snowman.png.fmap": "098b79691ae4cd1e6d36e295c057a3b2740b3991986be1b62dd77d4e73c82f61",
            "StockingLarge.png.fmap": "f467c400f7ae60efea0ab67ccb33d5ec9327a94383102f750e20dd29d70165a0",
            "StockingSmall.png.fmap": "aa6eee69ecaedcaa03575d6bb916e4442cfc83efda41f6e3a8291371475e8003",
            "StringOfLeaves.png.fmap": "c1268f8d827045e210854bb3bd70dec14f8991d18302219cd78f3c090366b174",
            "StringOfLights.png.fmap": "ce35221e4a91a75ec2994e4a731db230fdd31ff55b59267a663192fe6f4ad113",
        }
        mobile_dir = (
            ROOT / "patcher_assets" / "optional_patches"
            / "mobile_furniture_behaviors" / "mobile_fmaps"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            empty_base = root / "empty-base"
            empty_base.mkdir()
            self.assertEqual(
                exporter.mobile_furniture_behavior_asset_patches(bundle, empty_base),
                [],
            )

            partial_base = root / "partial-base"
            (partial_base / "Assets").mkdir(parents=True)
            first = next(iter(expected_hashes))
            (partial_base / "Assets" / first).write_bytes((mobile_dir / first).read_bytes())
            with self.assertRaisesRegex(ValueError, "incomplete"):
                exporter.mobile_furniture_behavior_asset_patches(bundle, partial_base)

            base = root / "base"
            (base / "Assets").mkdir(parents=True)
            for filename in expected_hashes:
                (base / "Assets" / filename).write_bytes((mobile_dir / filename).read_bytes())
            records = exporter.mobile_furniture_behavior_asset_patches(bundle, base)
            self.assertEqual(len(records), 34)
            self.assertEqual(
                [Path(row["file_path"]).name for row in records],
                list(expected_hashes),
            )
            for record in records:
                filename = Path(record["file_path"]).name
                self.assertEqual(
                    record["requires"],
                    ["core_executable", "mobile_furniture_behaviors"],
                )
                self.assertTrue(record["overwrite_existing"])
                self.assertTrue(record["allow_missing_target"])
                self.assertEqual(record["source_sha256"], expected_hashes[filename])
                enabled = bundle / Path(record["source_path"])
                restored = bundle / Path(record["restore_source_path"])
                original = base / "Assets" / filename
                self.assertEqual(
                    enabled.read_bytes(),
                    (exporter.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR / filename).read_bytes(),
                )
                self.assertEqual(restored.read_bytes(), original.read_bytes())
                self.assertEqual(
                    record["expected_target_sha256"],
                    hashlib.sha256(original.read_bytes()).hexdigest(),
                )
                self.assertEqual(
                    record["restore_source_sha256"],
                    record["expected_target_sha256"],
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
            # Shipped, not skipped. "Identical to the supplied base payload"
            # is no longer sufficient to call a file one the player already
            # has: work/vanilla_runtime_payload accumulated 603 patcher-added
            # fmaps from previous builds, so that rule dropped 528 genuine
            # additions and shipped a release without its fixture data. Only
            # the recorded clean-install index (data/vf2/
            # clean-base-game-assets.json) can classify a file as base-game,
            # and this synthetic path is not in it.
            self.assertIn("Images/Furniture/Unchanged.png", asset_by_path)
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
            transparency = (out / "Transparency Log.txt").read_text(encoding="utf-8")
            self.assertIn("Settings Evict is compiled into the core executable patch and is not an independent optional setting.", transparency)
            self.assertNotIn("Optional Patches (black): Holiday Ornaments, Settings Evict,", transparency)
            self.assertTrue((out / "payload" / "Images" / "Furniture" / "CandyCane.png").is_file())
            self.assertNotIn("Virtual Families 2.exe", manifest["runtime_requirements"]["exact_top_level_entries"])
            self.assertIn({"path": "Images", "min_files": 600}, manifest["runtime_requirements"]["required_dirs"])

            settings = self.run_patcher("settings", "--manifest", str(out / "manifest.json"))
            self.assertIn("holiday_furniture [default on]", settings.stdout)
            self.assertIn("vf3_tv_assets_recognition [default on]", settings.stdout)
            self.assertNotIn("behavior_patches", settings.stdout)
            self.assertNotIn("text_fixes", settings.stdout)
            self.assertNotIn("store_scroll_bar", settings.stdout)
            self.assertIn("custom_couches_ldw_posters [default off]", settings.stdout)
            self.assertIn("vf3_furniture [default off]", settings.stdout)
            self.assertIn("misc_graphics_fixes [default off]", settings.stdout)
            self.assertIn("glowing_collectibles [default off]", settings.stdout)
            self.assertNotIn("holiday_ornaments_collection", settings.stdout)
            self.assertNotIn("settings_evict_button", settings.stdout)
            self.assertNotIn("unused_pets", settings.stdout)
            self.assertNotIn("mobile_purchases", settings.stdout)
            self.assertNotIn("island_events", settings.stdout)
            self.assertIn("body field sync", settings.stdout)
            self.assertNotIn("transparent_store_bar [default off]", settings.stdout)
            self.assertIn("optional_song_mods [default off]", settings.stdout)
            settings_by_id = {row["id"]: row for row in manifest["settings"]}
            self.assertEqual(settings_by_id["holiday_furniture"]["category"], "main")
            self.assertEqual(settings_by_id["custom_couches_ldw_posters"]["category"], "optional")
            self.assertEqual(settings_by_id["vf3_furniture"]["category"], "optional")
            self.assertEqual(settings_by_id["misc_graphics_fixes"]["category"], "optional")
            self.assertEqual(settings_by_id["glowing_collectibles"]["category"], "optional")
            self.assertNotIn("settings_evict_button", settings_by_id)
            self.assertNotIn("store_scroll_bar", settings_by_id)
            self.assertNotIn("unused_pets", settings_by_id)
            self.assertNotIn("text_fixes", settings_by_id)
            self.assertNotIn("mobile_purchases", settings_by_id)
            self.assertNotIn("island_events", settings_by_id)
            self.assertNotIn("holiday_ornaments_collection", settings_by_id)
            self.assertNotIn("behavior_patches", settings_by_id)
            self.assertNotIn("expand_game_map", settings_by_id)
            self.assertNotIn(
                "experimental",
                {row["category"] for row in manifest["settings"]},
            )
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
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(
                minimal_pe_bytes(marker=1)
            )
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            (holiday_build / "Images" / "CollectionOrnaments").mkdir(parents=True)
            (holiday_build / "Images" / "Furniture").mkdir(parents=True)
            (holiday_build / "Images" / "collectables_small.png").write_bytes(b"holiday sheet")
            (holiday_build / "Images" / "collection-ornaments_background.png").write_bytes(b"holiday background")
            (holiday_build / "Images" / "CollectionOrnaments" / "collection_christmasornament_blueball.png").write_bytes(b"blueball")
            (holiday_build / "Images" / "Furniture" / "CandyCane.png").write_bytes(b"not part of ornament overlay")
            (holiday_build / "Virtual Families 2 - Additive Mobile Furniture Pack Holiday Ornaments.exe").write_bytes(
                minimal_pe_bytes(marker=2)
            )
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())
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
                "--vanilla-exe",
                str(vanilla),
                "--include-exe-replacement",
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
            self.assertEqual(manifest["export_summary"]["asset_counts_by_setting"]["holiday_ornaments_collection"], 4)

    def test_mobile_renovations_exe_overlay_is_exported_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())
            patched_exe = build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
            patched_exe.write_bytes(minimal_pe_bytes(marker=1))
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            mobile_overlay = tmp_path / "Virtual Families 2 - Mobile Renovations.exe"
            mobile_overlay.write_bytes(minimal_pe_bytes(marker=2))

            self.run_exporter(
                "--build-dir",
                str(build),
                "--base-payload",
                str(base),
                "--out-dir",
                str(out),
                "--name",
                "B157",
                "--vanilla-exe",
                str(vanilla),
                "--include-exe-replacement",
                "--mobile-renovations-exe",
                str(mobile_overlay),
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            overlay = next(
                row
                for row in manifest["asset_patches"]
                if row["file_path"] == "Virtual Families 2.exe"
                and row["requires"] == ["core_executable", "mobile_renovations"]
            )
            payload = out / overlay["source_path"]
            self.assertEqual(payload.name, "Virtual Families 2 - Modded B157 - Mobile Room Renovations.exe")
            self.assertEqual(payload.read_bytes(), mobile_overlay.read_bytes())
            self.assertEqual(
                manifest["source_build"]["mobile_renovations_exe"],
                mobile_overlay.name,
            )
            self.assertIn("mobile_renovations", {row["id"] for row in manifest["settings"]})

    def test_mobile_renovation_art_is_exported_from_overlay_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "core"
            overlay_build = tmp_path / "renovations"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            (overlay_build / "Images" / "MobileRenovations").mkdir(parents=True)
            renovation_art = overlay_build / "Images" / "MobileRenovations" / "tp238_beige_kitchen.png"
            renovation_art.write_bytes(b"renovation-art")
            curtain_dir = overlay_build / "Images" / "MobileRenovations" / "curtains"
            curtain_dir.mkdir(parents=True)
            curtain = curtain_dir / "shower_curtain_closed_black.png"
            curtain.write_bytes(b"bathroom1-curtain")
            (overlay_build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "generated_assets": [{"path": "Images/MobileRenovations/tp238_beige_kitchen.png"}],
                        "mobile_renovation_art_sources": {
                            "bathroom1_curtain_assets": [{"runtime_target": str(curtain)}],
                        },
                    }
                ),
                encoding="ascii",
            )
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(
                minimal_pe_bytes(marker=1)
            )
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            mobile_overlay = overlay_build / "mobile.exe"
            mobile_overlay.write_bytes(minimal_pe_bytes(marker=2))

            self.run_exporter(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(out),
                "--vanilla-exe", str(vanilla),
                "--include-exe-replacement",
                "--mobile-renovations-exe", str(mobile_overlay),
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            art_record = next(
                row for row in manifest["asset_patches"]
                if row["file_path"] == "Images/MobileRenovations/tp238_beige_kitchen.png"
            )
            self.assertEqual(art_record["requires"], ["core_executable", "mobile_renovations"])
            self.assertTrue(art_record["remove_when_disabled"])
            self.assertEqual((out / art_record["source_path"]).read_bytes(), renovation_art.read_bytes())
            curtain_record = next(
                row for row in manifest["asset_patches"]
                if row["file_path"] == "Images/MobileRenovations/curtains/shower_curtain_closed_black.png"
            )
            self.assertEqual(curtain_record["requires"], ["core_executable", "mobile_renovations"])
            self.assertTrue(curtain_record["remove_when_disabled"])
            self.assertEqual((out / curtain_record["source_path"]).read_bytes(), curtain.read_bytes())

    def test_cheat_upgrades_mobile_renovations_combined_overlay_is_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())
            patched_exe = build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
            patched_exe.write_bytes(minimal_pe_bytes(marker=1))
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            cheat_overlay = tmp_path / "cheat.exe"
            cheat_overlay.write_bytes(minimal_pe_bytes(marker=2))
            mobile_overlay = tmp_path / "renovations.exe"
            mobile_overlay.write_bytes(minimal_pe_bytes(marker=3))
            combined_overlay = tmp_path / "cheat-renovations.exe"
            combined_overlay.write_bytes(minimal_pe_bytes(marker=4))

            self.run_exporter(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(out),
                "--name", "B158",
                "--vanilla-exe", str(vanilla),
                "--include-exe-replacement",
                "--cheat-upgrades-exe", str(cheat_overlay),
                "--mobile-renovations-exe", str(mobile_overlay),
                "--cheat-upgrades-mobile-renovations-exe", str(combined_overlay),
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            requires = ["core_executable", "cheat_upgrades", "mobile_renovations"]
            overlay = next(
                row for row in manifest["asset_patches"]
                if row["file_path"] == "Virtual Families 2.exe"
                and row["requires"] == requires
            )
            self.assertEqual((out / overlay["source_path"]).read_bytes(), combined_overlay.read_bytes())
            self.assertEqual(
                manifest["source_build"]["cheat_upgrades_mobile_renovations_exe"],
                combined_overlay.name,
            )
            setting_ids = {row["id"] for row in manifest["settings"]}
            self.assertIn("cheat_upgrades", setting_ids)
            self.assertIn("mobile_renovations", setting_ids)
            exe_records = [
                row for row in manifest["asset_patches"]
                if row["file_path"] == "Virtual Families 2.exe"
            ]
            self.assertEqual(
                [row["requires"] for row in exe_records],
                [
                    ["core_executable"],
                    ["core_executable", "cheat_upgrades"],
                    ["core_executable", "mobile_renovations"],
                    ["core_executable", "cheat_upgrades", "mobile_renovations"],
                ],
            )

            game = tmp_path / "game"
            game.mkdir()
            (game / "Virtual Families 2.exe").write_bytes(vanilla.read_bytes())
            manifest["runtime_requirements"] = {}
            manifest["output"]["preserve_stock_exe_icon"] = False
            self.mark_synthetic_settings_runtime_ready(
                manifest,
                "mobile_renovations",
            )
            manifest_path = out / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            applied = tmp_path / "applied"
            self.run_patcher(
                "apply",
                "--game-dir", str(game),
                "--manifest", str(manifest_path),
                "--output-dir", str(applied),
                "--disable-all",
                "--enable", "core_executable,cheat_upgrades,mobile_renovations",
            )
            self.assertEqual(
                (applied / "Virtual Families 2 - Modded B158.exe").read_bytes(),
                combined_overlay.read_bytes(),
            )

    def test_island_events_mobile_renovations_combined_overlay_is_exported(self):
        # Before --island-events-mobile-renovations-exe existed, there was no
        # way to export a manifest record for this combination at all - the
        # exporter's overlay matrix only ever covered mobile_renovations
        # alone, cheat_upgrades+mobile_renovations, and the all-five final
        # profile (see the B162 audit finding on the incomplete matrix).
        # Mirrors test_cheat_upgrades_mobile_renovations_combined_overlay_is_exported
        # for one of the 13 previously-impossible combinations, proving the
        # export -> apply -> unique-overlay-selection pipeline now works
        # end-to-end for it.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            build.mkdir()
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())
            patched_exe = build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
            patched_exe.write_bytes(minimal_pe_bytes(marker=1))
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            island_overlay = tmp_path / "island.exe"
            island_overlay.write_bytes(minimal_pe_bytes(marker=2))
            mobile_overlay = tmp_path / "renovations.exe"
            mobile_overlay.write_bytes(minimal_pe_bytes(marker=3))
            combined_overlay = tmp_path / "island-renovations.exe"
            combined_overlay.write_bytes(minimal_pe_bytes(marker=4))

            self.run_exporter(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(out),
                "--name", "B163",
                "--vanilla-exe", str(vanilla),
                "--include-exe-replacement",
                "--island-events-exe", str(island_overlay),
                "--mobile-renovations-exe", str(mobile_overlay),
                "--island-events-mobile-renovations-exe", str(combined_overlay),
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            requires = ["core_executable", "island_events", "mobile_renovations"]
            overlay = next(
                row for row in manifest["asset_patches"]
                if row["file_path"] == "Virtual Families 2.exe"
                and row["requires"] == requires
            )
            self.assertEqual((out / overlay["source_path"]).read_bytes(), combined_overlay.read_bytes())
            self.assertEqual(
                manifest["source_build"]["island_events_mobile_renovations_exe"],
                combined_overlay.name,
            )

            game = tmp_path / "game"
            game.mkdir()
            (game / "Virtual Families 2.exe").write_bytes(vanilla.read_bytes())
            manifest["runtime_requirements"] = {}
            manifest["output"]["preserve_stock_exe_icon"] = False
            self.mark_synthetic_settings_runtime_ready(
                manifest,
                "mobile_renovations",
                "island_events",
            )
            manifest_path = out / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            applied = tmp_path / "applied"
            self.run_patcher(
                "apply",
                "--game-dir", str(game),
                "--manifest", str(manifest_path),
                "--output-dir", str(applied),
                "--disable-all",
                "--enable", "core_executable,island_events,mobile_renovations",
            )
            self.assertEqual(
                (applied / "Virtual Families 2 - Modded B163.exe").read_bytes(),
                combined_overlay.read_bytes(),
            )

    def test_final_playtest_all_enabled_rejects_reusing_the_core_executable(self):
        # Reproduces the actual B162 release defect: --final-playtest-all-enabled
        # was invoked without a --final-playtest-native-exe distinct from the
        # auto-detected --patched-exe, so "final_source = final_playtest_native_exe
        # or patched_exe" silently fell back to reusing the same file for both
        # the core_executable-only baseline and the Final All-Enabled Native
        # overlay. package_patcher_zip.validate_executable_inventory() rejects
        # that shipped bundle; the exporter itself must refuse to produce it.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            base.mkdir()
            build.mkdir()
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(
                minimal_pe_bytes(marker=1)
            )

            reused = self.run_exporter_expect(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(tmp_path / "reused-core"),
                "--vanilla-exe", str(vanilla),
                "--include-exe-replacement",
                "--final-playtest-all-enabled",
                expect=1,
            )
            self.assertIn("byte-identical", reused.stderr)
            self.assertFalse((tmp_path / "reused-core").exists())

            # An explicit --final-playtest-native-exe that is (by mistake)
            # byte-identical to the core build must be rejected the same way.
            same_bytes_explicit = tmp_path / "same-bytes.exe"
            same_bytes_explicit.write_bytes(minimal_pe_bytes(marker=1))
            reused_explicit = self.run_exporter_expect(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(tmp_path / "reused-explicit"),
                "--vanilla-exe", str(vanilla),
                "--include-exe-replacement",
                "--final-playtest-all-enabled",
                "--final-playtest-native-exe", str(same_bytes_explicit),
                expect=1,
            )
            self.assertIn("byte-identical", reused_explicit.stderr)
            self.assertFalse((tmp_path / "reused-explicit").exists())

    def test_require_distinct_final_playtest_source_only_rejects_byte_identical(self):
        # Focused unit coverage for the guard used above, isolated from the
        # rest of --final-playtest-all-enabled's much larger fixture
        # requirements (mobile_furniture_behaviors, ai_generated_bathroom2,
        # mobile_sound_assets, etc. must all be independently satisfied for a
        # full end-to-end success run, which is out of scope for this check).
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            patched_exe = tmp_path / "patched.exe"
            patched_exe.write_bytes(minimal_pe_bytes())
            same_bytes = tmp_path / "same.exe"
            same_bytes.write_bytes(minimal_pe_bytes())
            distinct = tmp_path / "distinct.exe"
            distinct.write_bytes(minimal_pe_bytes(with_older_pregnancy_flag=True, marker=7))

            with self.assertRaisesRegex(ValueError, "byte-identical"):
                exporter.require_distinct_final_playtest_source(same_bytes, patched_exe)
            # Must not raise for a genuinely distinct source.
            exporter.require_distinct_final_playtest_source(distinct, patched_exe)

    def test_cheat_upgrades_mobile_renovations_matrix_must_be_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            base.mkdir()
            build.mkdir()
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(
                minimal_pe_bytes(marker=1)
            )
            cheat_overlay = tmp_path / "cheat.exe"
            cheat_overlay.write_bytes(minimal_pe_bytes(marker=2))
            mobile_overlay = tmp_path / "renovations.exe"
            mobile_overlay.write_bytes(minimal_pe_bytes(marker=3))
            combined_overlay = tmp_path / "combined.exe"
            combined_overlay.write_bytes(minimal_pe_bytes(marker=4))

            missing_combined = self.run_exporter_expect(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(tmp_path / "missing-combined"),
                "--vanilla-exe", str(vanilla),
                "--include-exe-replacement",
                "--cheat-upgrades-exe", str(cheat_overlay),
                "--mobile-renovations-exe", str(mobile_overlay),
                expect=1,
            )
            self.assertIn("requires --cheat-upgrades-mobile-renovations-exe", missing_combined.stderr)
            self.assertFalse((tmp_path / "missing-combined").exists())

            missing_single = self.run_exporter_expect(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(tmp_path / "missing-single"),
                "--vanilla-exe", str(vanilla),
                "--include-exe-replacement",
                "--cheat-upgrades-exe", str(cheat_overlay),
                "--cheat-upgrades-mobile-renovations-exe", str(combined_overlay),
                expect=1,
            )
            self.assertIn("requires both", missing_single.stderr)
            self.assertFalse((tmp_path / "missing-single").exists())

    def test_overlay_backed_loose_assets_mark_output_only_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            base.mkdir()
            (build / "Images" / "MobileRenovations").mkdir(parents=True)
            (build / "Images" / "MobileRenovations" / "tp238_beige_kitchen.png").write_bytes(b"renovation")
            (build / "Images" / "cheat_reset_achievements.png").write_bytes(b"cheat")
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())
            patched = build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
            patched.write_bytes(minimal_pe_bytes(marker=1))
            (build / "patch-manifest.json").write_text(
                json.dumps(
                    {
                        "generated_assets": [
                            {"path": "Images/MobileRenovations/tp238_beige_kitchen.png"},
                            {"path": "Images/cheat_reset_achievements.png"},
                        ]
                    }
                ),
                encoding="ascii",
            )
            mobile_overlay = tmp_path / "mobile.exe"
            mobile_overlay.write_bytes(minimal_pe_bytes(marker=2))
            cheat_overlay = tmp_path / "cheat.exe"
            cheat_overlay.write_bytes(minimal_pe_bytes(marker=3))
            combined_overlay = tmp_path / "combined.exe"
            combined_overlay.write_bytes(minimal_pe_bytes(marker=4))

            self.run_exporter(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(out),
                "--vanilla-exe", str(vanilla),
                "--include-exe-replacement",
                "--mobile-renovations-exe", str(mobile_overlay),
                "--cheat-upgrades-exe", str(cheat_overlay),
                "--cheat-upgrades-mobile-renovations-exe", str(combined_overlay),
            )
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            records = {
                row["file_path"]: row
                for row in manifest["asset_patches"]
                if row["file_path"].endswith(".png")
            }
            self.assertTrue(records["Images/MobileRenovations/tp238_beige_kitchen.png"]["remove_when_disabled"])
            self.assertTrue(records["Images/cheat_reset_achievements.png"]["remove_when_disabled"])

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
            patched_exe.write_bytes(minimal_pe_bytes(marker=1))
            island_exe = build / "Virtual Families 2 - Additive Mobile Furniture Pack Island Events.exe"
            island_exe.write_bytes(minimal_pe_bytes(marker=2))
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
            self.assertEqual(core_exe["expected_target_sha256"], hashlib.sha256(vanilla.read_bytes()).hexdigest())
            self.assertEqual(island_overlay["expected_target_sha256"], core_exe["expected_target_sha256"])
            self.assertEqual(manifest["target_files"][0]["sha256"], core_exe["expected_target_sha256"])
            if "expected_target_pe_structures" in core_exe:
                self.assertIsInstance(core_exe["expected_target_pe_structures"], list)
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
            core_payload = next(
                row for row in manifest["asset_patches"]
                if row["file_path"] == "Virtual Families 2.exe"
            )
            self.assertTrue((out / core_payload["source_path"]).is_file())
            self.assertEqual(
                (out / core_payload["source_path"]).stat().st_size,
                core_payload["source_size"],
            )
            self.assertTrue((out / "Apply_B103_Patcher.bat").is_file())
            self.assertTrue((out / "README-B103-PATCHER.txt").is_file())
            self.assertTrue((out / "Transparency Log.txt").is_file())
            self.assertTrue((out / "offline_vf2_patcher.py").is_file())
            self.assertTrue((out / "vf2_crash_capture.py").is_file())
            crash_template = json.loads(
                (out / "crash-capture-manifest.template.json").read_text(encoding="ascii")
            )
            self.assertEqual(crash_template["schema"], "vf2-crash-capture/v1")
            self.assertEqual(crash_template["executable"]["path"], "")
            self.assertNotIn(str(tmp_path), json.dumps(crash_template))
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
            help_text = (out / "How to Use.txt").read_text(encoding="ascii")
            self.assertIn("Crash capture QA only", help_text)
            self.assertIn("never changes Windows Error Reporting", help_text)
            self.assertIn("Never substitute manifest.json", help_text)
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
            self.assertIn("vf2_crash_capture.py", manifest["export_summary"]["runner_files"])
            self.assertIn(
                "crash-capture-manifest.template.json",
                manifest["export_summary"]["runner_files"],
            )
            self.assertNotIn("Launch GUI.lnk", manifest["export_summary"]["runner_files"])
            self.assertNotIn("launch_gui_shortcut.json", manifest["export_summary"]["runner_files"])
            self.assertIn("patcher_icon.png", manifest["export_summary"]["runner_files"])
            self.assertIn("patcher_icon.ico", manifest["export_summary"]["runner_files"])
            self.assertIn("transparency_log", manifest["export_summary"])
            self.assertNotIn("launch_gui_shortcut", manifest["export_summary"])
            self.assertNotIn("launcher", manifest["export_summary"])
            self.assertTrue(manifest["export_summary"]["exe_replacement"])

    def test_exe_replacement_rejects_non_pe_and_non_x86_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle = tmp_path / "bundle"
            bundle.mkdir()
            vanilla = tmp_path / "Virtual Families 2.exe"
            vanilla.write_bytes(minimal_pe_bytes())

            invalid = tmp_path / "invalid.exe"
            invalid.write_bytes(b"not a PE executable")
            with self.assertRaisesRegex(ValueError, "not a valid PE32 executable"):
                exporter.export_exe_replacement_payload(
                    bundle_dir=bundle,
                    patched_exe=invalid,
                    vanilla_exe=vanilla,
                    accepted_exes=None,
                    target_exe_name="Virtual Families 2.exe",
                    build_label="B159",
                )

            wrong_machine = bytearray(minimal_pe_bytes())
            pe_offset = int.from_bytes(wrong_machine[0x3C:0x40], "little")
            wrong_machine[pe_offset + 4:pe_offset + 6] = (0x8664).to_bytes(2, "little")
            invalid.write_bytes(wrong_machine)
            with self.assertRaisesRegex(ValueError, "not a 32-bit x86 executable"):
                exporter.export_exe_replacement_payload(
                    bundle_dir=bundle,
                    patched_exe=invalid,
                    vanilla_exe=vanilla,
                    accepted_exes=None,
                    target_exe_name="Virtual Families 2.exe",
                    build_label="B159",
                )
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
            patched_exe.write_bytes(minimal_pe_bytes(marker=31))
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
                source_data = minimal_pe_bytes(marker=index)
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
                self.assertTrue(payload.is_file())
                self.assertEqual(payload.read_bytes(), source_data_by_requires[tuple(requires)])

            # Strip unrelated official-install requirements so this focused test
            # can prove executable overlay precedence with a one-file game tree.
            manifest["runtime_requirements"] = {}
            # This synthetic PE intentionally has no resource directory. Icon
            # preservation is covered against resource-bearing fixtures in the
            # patch-engine tests; disable it for this overlay-only matrix.
            manifest["output"]["preserve_stock_exe_icon"] = False
            self.mark_synthetic_settings_runtime_ready(
                manifest,
                "island_events",
                "behavior_patches",
            )
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
            (build / "VF2-B145-Core.exe").write_bytes(minimal_pe_bytes(marker=1))
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")
            identity_manifest = tmp_path / "identity.json"
            identity_manifest.write_text(
                json.dumps(
                    {
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "sha256": "11" * 32,
                                "size": len(minimal_pe_bytes()),
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
            self.assertEqual(core_exe["expected_target_sha256"], "11" * 32)
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
            self.assertEqual(source["requires"], ["core_native_patch"])
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

    def test_runtime_asset_export_excludes_desktop_source_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base"
            build = tmp_path / "build"
            out = tmp_path / "bundle"
            (base / "Images").mkdir(parents=True)
            (build / "Images").mkdir(parents=True)
            (build / "Images" / "MapX0Y2-DESKTOP-J6OI2AP.xcf").write_bytes(b"dev")
            (build / "Images" / "MapX1y2-DESKTOP-J6OI2AP.png").write_bytes(b"dev")
            (build / "Images" / "MapX0Y2.png").write_bytes(b"runtime")
            (build / "Images" / "notes-DESKTOP-J6OI2AP.txt").write_bytes(b"doc")
            (build / "Virtual Families 2 - Additive Mobile Furniture Pack.exe").write_bytes(b"patched")
            (build / "patch-manifest.json").write_text("{}", encoding="ascii")

            self.run_exporter(
                "--build-dir", str(build),
                "--base-payload", str(base),
                "--out-dir", str(out),
                "--asset-mode", "all",
            )

            asset_paths = {
                row["file_path"] for row in json.loads(
                    (out / "manifest.json").read_text(encoding="utf-8")
                )["asset_patches"]
            }
            self.assertNotIn("Images/MapX0Y2-DESKTOP-J6OI2AP.xcf", asset_paths)
            self.assertNotIn("Images/MapX1y2-DESKTOP-J6OI2AP.png", asset_paths)
            self.assertNotIn("Images/notes-DESKTOP-J6OI2AP.txt", asset_paths)
            self.assertIn("Images/MapX0Y2.png", asset_paths)
            self.assertTrue(
                exporter.is_desktop_runtime_source_file(
                    Path("Images/MapX0Y2-DESKTOP-J6OI2AP.xcf")
                )
            )

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

    def test_payload_deduplication_repoints_records_to_one_canonical_source(self):
        import export_offline_patch_bundle as exporter

        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            first = bundle / "payload" / "Images" / "first.png"
            second = bundle / "payload" / "OptionalVisualMods" / "second.png"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_bytes(b"same bytes")
            second.write_bytes(b"same bytes")
            digest = hashlib.sha256(b"same bytes").hexdigest()
            records = [
                {
                    "file_path": "Images/target-a.png",
                    "source_path": "payload/Images/first.png",
                    "source_sha256": digest,
                    "source_size": len(b"same bytes"),
                },
                {
                    "file_path": "Images/target-b.png",
                    "source_path": "payload/OptionalVisualMods/second.png",
                    "source_sha256": digest,
                    "source_size": len(b"same bytes"),
                },
            ]

            summary = exporter.deduplicate_payload_files(bundle, records)

            self.assertEqual(summary["removed_file_count"], 1)
            self.assertEqual(summary["removed_bytes"], len(b"same bytes"))
            self.assertEqual(records[0]["source_path"], records[1]["source_path"])
            self.assertTrue((bundle / records[0]["source_path"]).is_file())
            self.assertFalse(second.exists())
            exporter.validate_bundle_asset_sources(bundle, records)


class CleanBaseGameReferenceTests(unittest.TestCase):
    """The additive diff must never consult the working payload.

    Two releases shipped broken because it did. work/vanilla_runtime_payload
    has accumulated 603 patcher-added fmaps from previous builds, so its
    "vanilla" Assets directory holds 845 files where a clean install has
    242. Diffing against it classified 528 genuine additions as files the
    player already had.
    """

    def test_clean_base_index_matches_a_real_clean_install(self):
        doc = json.loads(
            (ROOT / "data" / "vf2" / "clean-base-game-assets.json").read_text(
                encoding="utf-8-sig"
            )
        )
        # A clean Virtual Families 2 install, not a patched one.
        self.assertEqual(doc["counts"]["Images"], 655)
        self.assertEqual(doc["counts"]["Assets"], 242)
        for entry in doc["files"].values():
            self.assertIn("sha256", entry)
            self.assertIn("size", entry)

    def test_working_payload_is_not_used_as_the_clean_reference(self):
        source = (ROOT / "work" / "export_offline_patch_bundle.py").read_text(
            encoding="utf-8"
        )
        start = source.index("def matches_base_payload(")
        body = source[start:source.index("\ndef ", start + 10)]
        # It must consult the recorded clean index...
        self.assertIn("clean_base_game_index()", body)
        # ...and must not hash the payload copy to decide "already present".
        self.assertNotIn("base_payload / rel", body)

    def test_export_skip_uses_the_clean_reference_too(self):
        # The selector was fixed first and the bug survived, because a second
        # check further down still compared against the payload and dropped
        # what the selector had correctly included.
        source = (ROOT / "work" / "export_offline_patch_bundle.py").read_text(
            encoding="utf-8"
        )
        start = source.index("def export_asset_payloads(")
        body = source[start:source.index("\ndef ", start + 10)]
        self.assertIn("if matches_base_payload(rel, build_dir, base_payload):", body)
        self.assertNotIn("if base.is_file() and sha256_file(base) == source_sha:", body)


class MobileSoundBuilderFlagTests(unittest.TestCase):
    """Where VF2_ENABLE_MOBILE_SOUND_ASSETS may be turned on, and where it must not be.

    The playtest builder has no patcher step, so it bakes the four .wav->.ogg
    routes into the executable at link time. The matrix builder must not: its
    executables are what the patcher bundle ships, and the exporter applies
    those same routes as exact-SHA post-asset patches keyed on the stock .wav
    strings. A pre-routed matrix executable makes that export fail outright --

        ValueError: Expected exactly one beaker.wav route in <exe>

    -- because allow_prelinked_ogg is only enabled for the playtest export path
    (final_playtest_all_enabled). It would also make "Use mobile sound assets"
    one-way: with the routes baked in, unticking it could not restore the stock
    .wav routes.
    """

    def _flag_values(self, name):
        """Every value assigned to the env var in one builder script."""
        text = (ROOT / "work" / name).read_text(encoding="utf-8")
        values = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("$env:VF2_ENABLE_MOBILE_SOUND_ASSETS"):
                continue
            values.append(stripped.split("=", 1)[1].strip().strip('"'))
        return values

    def test_playtest_builder_enables_mobile_sound_assets(self):
        self.assertEqual(self._flag_values("build_playtest.ps1"), ["1"])

    def test_matrix_builder_leaves_mobile_sound_assets_to_the_patcher(self):
        self.assertEqual(
            self._flag_values("build_matrix.ps1"),
            ["0"],
            "build_matrix.ps1 must leave VF2_ENABLE_MOBILE_SOUND_ASSETS at 0; "
            "pre-routed executables break mobile_sound_assets_post_asset_patches.",
        )


class NonRuntimeSourceExclusionTests(unittest.TestCase):
    """Editing sources must not reach a release payload.

    B176 shipped 30 .xcf GIMP project files -- 49,028,504 uncompressed bytes,
    43,823,872 compressed, 24.7% of that entire download -- because the payload
    walk rejected only .bak. SDL_image cannot decode a .xcf and nothing in the
    engine's asset tables names one, so they were pure inherited weight.
    """

    def test_xcf_and_bak_are_both_excluded(self):
        self.assertEqual(
            exporter.NON_RUNTIME_SOURCE_SUFFIXES, {".bak", ".xcf"}
        )

    def test_nested_upgrade_source_folders_are_excluded(self):
        """The two working folders inside Images/Upgrades are not runtime art.

        The engine loads Images/Upgrades/<name>.png. These subfolders are the
        swap source and the restore backup for Invisible Workspace Upgrades;
        the exporter already installs the real swap flat and ships the same
        files under OptionalVisualMods, so copying the folders put 61
        unreadable files into every install.
        """
        for rel, expected in (
            (Path("Images/Upgrades/invisible images/toolwall.png"), True),
            (Path("Images/Upgrades/original images/toolwall.png"), True),
            (Path("Images/Upgrades/toolwall.png"), False),
            (Path("Images/Furniture/Balloons_birthday.png"), False),
            (Path("Images/Furniture/BlackBookshelf.xcf"), True),
        ):
            with self.subTest(path=str(rel)):
                self.assertEqual(exporter.is_non_runtime_source_path(rel), expected)

    def test_full_mode_walk_also_excludes_non_runtime_sources(self):
        """--asset-mode full returns from its own branch, so it needs the check too.

        is_full_payload_candidate accepts every PNG under Images, so without
        this the working folders and .xcf files reappear in full bundles -- and
        the release verifier now omits them from its expected set, so nothing
        would have reported it. Exercised through the walk rather than by
        reading the source, so it cannot pass on a moved code block.
        """
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            keep = build / "Images" / "Upgrades" / "toolwall.png"
            drop_a = build / "Images" / "Upgrades" / "invisible images" / "toolwall.png"
            drop_b = build / "Images" / "Upgrades" / "original images" / "toolwall.png"
            drop_c = build / "Images" / "Furniture" / "BlackBookshelf.xcf"
            for path in (keep, drop_a, drop_b, drop_c):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
            found = {
                p.relative_to(build).as_posix()
                for p in exporter.iter_candidate_assets(build, {}, "full")
            }
        self.assertIn("Images/Upgrades/toolwall.png", found)
        for excluded in (
            "Images/Upgrades/invisible images/toolwall.png",
            "Images/Upgrades/original images/toolwall.png",
            "Images/Furniture/BlackBookshelf.xcf",
        ):
            self.assertNotIn(excluded, found)

    def test_payload_walk_uses_the_shared_suffix_set(self):
        source = (ROOT / "work" / "export_offline_patch_bundle.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "if rel.suffix.lower() in NON_RUNTIME_SOURCE_SUFFIXES:", source
        )
        # The old single-suffix test must not survive alongside it.
        self.assertNotIn('if rel.suffix.lower() == ".bak":', source)


class TestSuiteCopiesInSyncTests(unittest.TestCase):
    """tests/ and work/ hold the same suites and must not drift apart.

    They already did: PR #36 changed the additive diff to classify base-game
    files from the recorded clean install rather than the supplied payload and
    updated the work/ copy's expectation, but not the tests/ copy. tests/ then
    asserted the old behaviour and failed for months, which is indistinguishable
    from a real regression and trains everyone to ignore a red suite.

    The only sanctioned difference is which tool tree a suite points at: tests/
    exercises the shipped src/ copies, work/ exercises the development ones.
    """

    # name -> True when the two copies must be byte-identical.
    SUITES = {
        "test_export_offline_patch_bundle.py": True,
        "test_offline_vf2_patcher.py": False,
        "test_offline_vf2_patcher_gui.py": False,
    }

    def test_tool_copies_match_between_src_and_work(self):
        """The two implementation trees must not drift.

        The bundle exporter ships the **work/** copies -- SOURCE_DIR is the
        work directory and write_bundle_runner_files() copies from there. A
        change made only in src/ therefore never reaches a release, while
        tests/ (which imports src/) still goes green. That happened to the
        "Please wait" GUI feedback: src/ had it, the shipped GUI did not, and
        both suites passed.
        """
        for name in (
            "offline_vf2_patcher.py",
            "offline_vf2_patcher_gui.py",
            "vf2_crash_capture.py",
        ):
            src_path = ROOT / "src" / name
            work_path = ROOT / "work" / name
            if not src_path.is_file() or not work_path.is_file():
                continue
            with self.subTest(tool=name):
                self.assertEqual(
                    src_path.read_text(encoding="utf-8"),
                    work_path.read_text(encoding="utf-8"),
                    f"src/{name} and work/{name} have drifted; the exporter "
                    f"ships work/{name}, so a src-only change never reaches a "
                    "release",
                )

    def test_tests_copy_matches_the_work_copy(self):
        for name, identical in self.SUITES.items():
            with self.subTest(suite=name):
                work_text = (ROOT / "work" / name).read_text(encoding="utf-8")
                tests_text = (ROOT / "tests" / name).read_text(encoding="utf-8")
                expected = work_text
                if not identical:
                    # These two import the tool under test; tests/ takes the
                    # shipped src/ copy. Nothing else may differ.
                    expected = work_text.replace('ROOT / "work"', 'ROOT / "src"')
                self.assertEqual(
                    tests_text,
                    expected,
                    f"tests/{name} has drifted from work/{name}; "
                    "sync the two rather than editing one.",
                )


class TestBundleChangelogReachesTheWrittenLog(unittest.TestCase):
    """The changelog blocks must survive into the file, not just the source.

    write_bundle_runner_files() writes the bundle's patcher README with
    encoding="ascii". A non-ASCII character in any changelog line therefore
    fails when the bundle is written and at no earlier point -- reading the
    exporter source cannot show it, and neither can importing the tuple.
    """

    def test_every_changelog_block_is_written_out(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            bundle.mkdir()
            exporter.write_bundle_runner_files(bundle, "B180")
            # The changelog goes into the bundle's own patcher README, which is
            # written with encoding="ascii".
            log = (bundle / "README-B180-PATCHER.txt").read_text(encoding="utf-8")
            for heading, lines in (
                ("B151 changelog", exporter.B151_CHANGELOG_LINES),
                ("B162 changelog", exporter.B162_CHANGELOG_LINES),
                ("B180 changelog", exporter.B180_CHANGELOG_LINES),
            ):
                with self.subTest(block=heading):
                    self.assertIn(heading, log)
                    for line in lines:
                        self.assertIn(line, log)

    def test_the_b180_block_covers_what_b180_changed(self):
        joined = "\n".join(exporter.B180_CHANGELOG_LINES)
        for topic in (
            "drop routing",
            "Ping-Pong",
            "exercise bike",
            "checkmark",
            "hairstyle",
            "Spa Lounger",
        ):
            with self.subTest(topic=topic):
                self.assertIn(topic, joined)

    def test_the_unrouted_items_are_not_claimed_to_work(self):
        # Seven items rely on the native hotspot path and have not been
        # confirmed by a player. Saying otherwise in a shipped log would be a
        # claim the build cannot support.
        joined = "\n".join(exporter.B180_CHANGELOG_LINES)
        self.assertIn("outstanding and is not claimed", joined)


if __name__ == "__main__":
    unittest.main()
