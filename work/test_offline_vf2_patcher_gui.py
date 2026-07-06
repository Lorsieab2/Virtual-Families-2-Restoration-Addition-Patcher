#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import offline_vf2_patcher as patcher
import offline_vf2_patcher_gui as gui


class OfflineVF2PatcherGUITests(unittest.TestCase):
    def test_markup_segments_supports_bold_spans(self):
        self.assertEqual(
            gui.markup_segments("Adds **visible graphics** first."),
            [("Adds ", False), ("visible graphics", True), (" first.", False)],
        )

    def test_categorized_settings_groups_by_manifest_category(self):
        settings = {
            "core_executable": patcher.PatchSetting(
                id="core_executable",
                label="Patch game executable",
                description="",
                default=True,
                category="main",
            ),
            "custom_map": patcher.PatchSetting(
                id="custom_map",
                label="Custom map",
                description="",
                default=False,
                category="optional",
            ),
            "settings_evict_button": patcher.PatchSetting(
                id="settings_evict_button",
                label="Settings Evict",
                description="",
                default=False,
                category="experimental",
            ),
        }

        rows = gui.categorized_settings(settings)

        self.assertEqual([row[0] for row in rows], ["main", "optional", "experimental"])
        self.assertEqual(rows[0][1:3], ("Main Patches", "#00802b"))
        self.assertEqual(rows[1][1:3], ("Optional Patches", "#000000"))
        self.assertEqual(rows[2][1:3], ("Experimental/Not Working Patches", "#b00020"))
        self.assertEqual([setting.id for setting in rows[0][3]], ["core_executable"])
        self.assertEqual([setting.id for setting in rows[1][3]], ["custom_map"])
        self.assertEqual([setting.id for setting in rows[2][3]], ["settings_evict_button"])

    def test_setting_ids_for_category_handles_defaults(self):
        settings = {
            "core_executable": patcher.PatchSetting(
                id="core_executable",
                label="Patch game executable",
                description="",
                default=True,
            ),
            "custom_map": patcher.PatchSetting(
                id="custom_map",
                label="Custom map",
                description="",
                default=False,
                category="optional",
            ),
        }

        self.assertEqual(gui.setting_ids_for_category(settings, "main"), ["core_executable"])
        self.assertEqual(gui.setting_ids_for_category(settings, "optional"), ["custom_map"])
        self.assertEqual(gui.setting_ids_for_category(settings, "experimental"), [])

    def test_estimate_wrapped_lines_expands_long_descriptions(self):
        measure = len

        self.assertEqual(gui.estimate_wrapped_lines("short text", 20, measure), 1)
        self.assertGreaterEqual(
            gui.estimate_wrapped_lines("this description should wrap onto another visible line", 18, measure),
            3,
        )

    def test_build_apply_namespace_uses_exact_checkbox_selection(self):
        settings = {
            "holiday_furniture": patcher.PatchSetting(
                id="holiday_furniture",
                label="Add Holiday furniture",
                description="",
                default=False,
            ),
            "mobile_furniture": patcher.PatchSetting(
                id="mobile_furniture",
                label="Add mobile furniture",
                description="",
                default=True,
            ),
        }
        args = gui.build_apply_namespace(
            game_dir="C:\\Games\\VF2",
            manifest="patches\\vf2.json",
            output_dir="",
            backup_dir="",
            log=None,
            dry_run=True,
            settings=settings,
            selected_settings={"holiday_furniture"},
        )

        self.assertEqual(args.game_dir, "C:\\Games\\VF2")
        self.assertEqual(args.manifest, "patches\\vf2.json")
        self.assertIsNone(args.output_dir)
        self.assertIsNone(args.backup_dir)
        self.assertIsNone(args.log)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.disable_all)
        self.assertEqual(args.enable, ["holiday_furniture"])

        manifest = {
            "settings": [
                {"id": "holiday_furniture", "default": False},
                {"id": "mobile_furniture", "default": True},
            ]
        }
        _, enabled = patcher.resolve_enabled_settings(manifest, args)
        self.assertEqual(enabled, {"holiday_furniture"})

    def test_build_apply_namespace_rejects_unknown_selected_setting(self):
        settings = {
            "holiday_outfits": patcher.PatchSetting(
                id="holiday_outfits",
                label="Add Holiday outfits",
                description="",
                default=False,
            )
        }

        with self.assertRaises(patcher.PatchError):
            gui.build_apply_namespace(
                game_dir="C:\\Games\\VF2",
                manifest="patches\\vf2.json",
                settings=settings,
                selected_settings={"mobile_furniture"},
            )

    def test_build_restore_namespace_uses_optional_game_dir(self):
        args = gui.build_restore_namespace(
            backup_dir="C:\\Games\\VF2\\.vf2_patch_backups\\example",
            game_dir="",
            log="",
        )

        self.assertEqual(args.backup_dir, "C:\\Games\\VF2\\.vf2_patch_backups\\example")
        self.assertIsNone(args.game_dir)
        self.assertIsNone(args.log)


if __name__ == "__main__":
    unittest.main()
