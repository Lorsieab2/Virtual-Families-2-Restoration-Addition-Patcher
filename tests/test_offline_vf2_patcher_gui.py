#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import offline_vf2_patcher as patcher
import offline_vf2_patcher_gui as gui


class OfflineVF2PatcherGUITests(unittest.TestCase):
    def test_markup_segments_supports_bold_spans(self):
        self.assertEqual(
            gui.markup_segments("Adds **visible graphics** first."),
            [("Adds ", False), ("visible graphics", True), (" first.", False)],
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
