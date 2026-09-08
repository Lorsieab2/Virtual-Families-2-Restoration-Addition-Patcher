"""The export must not silently drop the settings players came for.

B183 shipped 23 settings where B181 shipped 35. Twelve went missing, none
were added, and every step reported success -- the first thing that noticed
was a person opening the archive.

The mechanism is precise. Every executable-overlay setting is in
SOURCE_BACKED_OPTIONAL_SETTINGS, so default_settings() removes any that is
not in available_settings; available_settings is derived from the asset rows
that survive the overlay filter; and that filter strips every row requiring
an overlay setting when the export produced no overlay .exe for it. Omit the
per-feature overlay arguments and the whole chain runs to completion, quietly,
producing a smaller patcher.

apply_final_playtest_defaults() already refused on this condition -- but only
for --final-playtest-all-enabled. Ordinary patcher bundles, the ones players
download, had no such check.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import export_offline_patch_bundle as ex


B181_SETTINGS = 35
B183_SETTINGS = 23


class OverlaySettingsCannotVanish(unittest.TestCase):
    def test_a_complete_bundle_is_accepted(self):
        # The guard is only worth having if it still lets a real release out.
        ex.refuse_to_drop_overlay_settings(
            set(ex.EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS) | {"core_assets"},
            set(ex.EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS),
            False,
        )

    def test_the_b183_shape_is_refused(self):
        # No overlay produced, so every overlay setting would be dropped.
        with self.assertRaises(ValueError) as caught:
            ex.refuse_to_drop_overlay_settings({"core_assets"}, set(), False)
        message = str(caught.exception)
        for setting in ex.EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS:
            with self.subTest(setting=setting):
                self.assertIn(setting, message)

    def test_losing_even_one_overlay_setting_is_refused(self):
        # Not just the all-or-nothing case: B183 lost five, but one is enough
        # for a player to find a feature missing.
        for setting in sorted(ex.EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS):
            available = set(ex.EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS) - {setting}
            with self.subTest(missing=setting):
                with self.assertRaises(ValueError) as caught:
                    ex.refuse_to_drop_overlay_settings(available, available, False)
                self.assertIn(setting, str(caught.exception))

    def test_behavior_patches_specifically_cannot_be_dropped(self):
        # Named on its own because it is the one the owner asked for, and the
        # one B183 dropped while its executable carried the crash fix.
        available = set(ex.EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS) - {"behavior_patches"}
        with self.assertRaises(ValueError) as caught:
            ex.refuse_to_drop_overlay_settings(available, available, False)
        self.assertIn("behavior_patches", str(caught.exception))

    def test_the_refusal_says_how_to_proceed(self):
        with self.assertRaises(ValueError) as caught:
            ex.refuse_to_drop_overlay_settings({"core_assets"}, set(), False)
        message = str(caught.exception)
        with self.subTest(part="names the cause"):
            self.assertIn("overlay", message.lower())
        with self.subTest(part="names the override"):
            self.assertIn("--allow-missing-overlay-settings", message)

    def test_an_explicit_partial_bundle_is_still_possible(self):
        # Deliberately building without an overlay stays available; it is now
        # an argument somebody passes rather than a silent default.
        ex.refuse_to_drop_overlay_settings({"core_assets"}, set(), True)

    def test_behavior_patches_ships_enabled_by_default(self):
        # Offered is not the same as on. The owner asked for both.
        rows = {row["id"]: row for row in ex.SETTINGS}
        self.assertIn("behavior_patches", rows)
        self.assertTrue(
            rows["behavior_patches"].get("default"),
            "behavior_patches is offered but not enabled by default",
        )

    def test_every_overlay_setting_is_droppable_without_the_guard(self):
        # The premise: these are exactly the settings default_settings() will
        # remove when they are not available. If one ever leaves
        # SOURCE_BACKED_OPTIONAL_SETTINGS the guard still holds, but this
        # records why the guard is aimed where it is.
        self.assertLessEqual(
            ex.EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS,
            ex.SOURCE_BACKED_OPTIONAL_SETTINGS,
        )

    def test_the_guard_runs_for_ordinary_bundles_not_only_playtests(self):
        # The whole defect was that the equivalent check existed but was
        # reached only under --final-playtest-all-enabled.
        source = Path(ex.__file__).read_text(encoding="utf-8")
        call = source.index("refuse_to_drop_overlay_settings(\n        available_settings")
        guarded = source.rindex("final_playtest_all_enabled", 0, call)
        between = source[guarded:call]
        self.assertIn(
            "default_settings", between + source[call:call + 400],
            "the guard must sit on the path every export takes",
        )
        # And it must precede the call that does the dropping.
        drop = source.index("settings = default_settings(", call)
        self.assertLess(call, drop)


if __name__ == "__main__":
    unittest.main()
