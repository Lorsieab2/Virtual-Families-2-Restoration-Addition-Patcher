#!/usr/bin/env python3
import argparse
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ELLIPSIS = chr(0x2026)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import offline_vf2_patcher as patcher
import offline_vf2_patcher_gui as gui


class OfflineVF2PatcherGUITests(unittest.TestCase):
    def test_prepare_output_dir_excludes_desktop_identifier_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "vanilla"
            output = root / "VF2-Test-Modded"
            sounds = source / "Sounds"
            sounds.mkdir(parents=True)
            (sounds / "keep.ogg").write_bytes(b"keep")
            (sounds / "chime3bX-DESKTOP-J6OI2AP.ogg").write_bytes(b"exclude")
            desktop_dir = source / "Images-DESKTOP-ABC123"
            desktop_dir.mkdir()
            (desktop_dir / "nested.png").write_bytes(b"exclude")

            patcher.prepare_output_dir(
                source,
                output,
                set(),
                argparse.Namespace(progress_callback=lambda _message: None),
            )

            self.assertEqual((output / "Sounds" / "keep.ogg").read_bytes(), b"keep")
            self.assertFalse((output / "Sounds" / "chime3bX-DESKTOP-J6OI2AP.ogg").exists())
            self.assertFalse((output / "Images-DESKTOP-ABC123").exists())

    def test_b150_creator_and_save_compatibility_messages_are_exact(self):
        self.assertEqual(
            gui.PROJECT_CREATOR_MESSAGE,
            'Created by Lorsieab2. This is a passion project dedicated to improving the '
            '"Virtual Families 2" experience!\n'
            'No copyright infringement intended! Please support the original game creators! :)',
        )
        self.assertEqual(
            gui.SAVE_COMPATIBILITY_NOTE,
            "Vanilla Virtual Families 2 saves are compatible with the modded version!",
        )

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
            "experimental_feature": patcher.PatchSetting(
                id="experimental_feature",
                label="Experimental feature",
                description="",
                default=False,
                category="experimental",
            ),
        }

        rows = gui.categorized_settings(settings)

        self.assertEqual(
            [category[0] for category in gui.SETTING_CATEGORIES],
            ["main", "optional"],
        )
        self.assertEqual([row[0] for row in rows], ["main", "optional", "other"])
        self.assertNotIn("experimental", [row[0] for row in rows])
        self.assertEqual(rows[0][1:3], ("Main Patches", "#00802b"))
        self.assertEqual(rows[1][1:3], ("Optional Patches", "#000000"))
        self.assertEqual(rows[2][1:3], ("Other Patches", "#000000"))
        self.assertEqual([setting.id for setting in rows[0][3]], ["core_executable"])
        self.assertEqual([setting.id for setting in rows[1][3]], ["custom_map"])
        self.assertEqual([setting.id for setting in rows[2][3]], ["experimental_feature"])

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
            output_parent_dir="D:\\VF2 Builds",
            backup_dir="",
            log=None,
            dry_run=True,
            settings=settings,
            selected_settings={"holiday_furniture"},
        )

        self.assertEqual(args.game_dir, "C:\\Games\\VF2")
        self.assertEqual(args.manifest, "patches\\vf2.json")
        self.assertIsNone(args.output_dir)
        self.assertEqual(args.output_parent_dir, "D:\\VF2 Builds")
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

    def test_saved_paths_round_trip_local_settings_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "patcher_local_settings.json"

            gui.save_saved_paths(
                vanilla_game_dir="C:\\Games\\Virtual Families 2",
                modded_output_dir="C:\\Games\\VF2-B119-Modded",
                settings_path=settings_path,
            )

            self.assertEqual(
                gui.load_saved_paths(settings_path),
                {
                    "vanilla_game_dir": "C:\\Games\\Virtual Families 2",
                    "modded_output_dir": "C:\\Games\\VF2-B119-Modded",
                },
            )

            gui.save_saved_paths(
                vanilla_game_dir="",
                modded_output_dir="C:\\Games\\VF2-B120-Modded",
                settings_path=settings_path,
            )

            self.assertEqual(
                gui.load_saved_paths(settings_path),
                {
                    "vanilla_game_dir": "C:\\Games\\Virtual Families 2",
                    "modded_output_dir": "C:\\Games\\VF2-B120-Modded",
                },
            )

    def test_manifest_readiness_blocks_unready_rows_but_keeps_them_declared(self):
        manifest = {
            "setting_readiness": {
                "stop_feature": {"status": "STOP", "reason": "native bytes not authenticated"},
                "pending_feature": {"status": "pending", "runtime_ready": False, "reason": "awaiting readback"},
                "unlinked_feature": {"link_status": "unlinked"},
                "runtime_feature": {"runtime_ready": False},
            },
            "settings": [
                {"id": "stop_feature", "default": True},
                {"id": "pending_feature", "default": False},
                {"id": "unlinked_feature", "default": False},
                {"id": "runtime_feature", "default": False},
                {"id": "ready_feature", "default": True, "runtime_ready": True, "linked": True},
            ],
        }

        settings = patcher.manifest_settings(manifest)

        self.assertEqual(
            set(settings),
            {"stop_feature", "pending_feature", "unlinked_feature", "runtime_feature", "ready_feature"},
        )
        self.assertTrue(settings["stop_feature"].blocked)
        self.assertIn("manifest status=STOP", settings["stop_feature"].readiness_reason)
        self.assertIn("runtime_ready=false", settings["pending_feature"].readiness_reason)
        self.assertIn("manifest status=unlinked", settings["unlinked_feature"].readiness_reason or "")
        self.assertIn("runtime_ready=false", settings["runtime_feature"].readiness_reason)
        self.assertFalse(settings["ready_feature"].blocked)
        self.assertEqual(
            set(setting.id for _key, _label, _color, rows in gui.categorized_settings(settings) for setting in rows),
            set(settings),
        )
        log = patcher.settings_log(settings, set())
        self.assertIn("stop_feature", log["blocked"])
        self.assertFalse(next(row for row in log["available"] if row["id"] == "stop_feature")["selectable"])
        self.assertTrue(next(row for row in log["available"] if row["id"] == "ready_feature")["selectable"])

    def test_enable_all_and_gui_selection_reject_blocked_settings(self):
        manifest = {
            "settings": [
                {"id": "blocked_feature", "default": False, "status": "pending", "runtime_ready": False, "reason": "not linked"},
                {"id": "ready_feature", "default": False},
            ]
        }
        args = patcher.argparse.Namespace(
            enable_all=True,
            disable_all=False,
            enable=None,
            disable=None,
        )

        with self.assertRaisesRegex(patcher.PatchError, r"blocked_feature: .*runtime_ready=false"):
            patcher.resolve_enabled_settings(manifest, args)

        settings = patcher.manifest_settings(manifest)
        with self.assertRaisesRegex(patcher.PatchError, r"Cannot select blocked setting\(s\): blocked_feature: .*"):
            gui.build_apply_namespace(
                game_dir="C:\\Games\\VF2",
                manifest="patches\\vf2.json",
                settings=settings,
                selected_settings={"blocked_feature"},
            )

    def test_explicit_final_playtest_profile_allows_blocked_rows_only_with_profile_flag(self):
        manifest = {
            "final_playtest_profile": {
                "id": "final_playtest_all_enabled",
                "default_on": ["behavior_patches"],
                "explicitly_default_off": ["no_ai_icons"],
            },
            "settings": [
                {"id": "core_executable", "default": True},
                {"id": "holiday_furniture", "default": True},
                {
                    "id": "behavior_patches",
                    "default": False,
                    "status": "pending",
                    "runtime_ready": False,
                    "linked": False,
                    "reason": "readback pending",
                },
                {"id": "same_sex_marriage", "default": False},
                {"id": "custom_lorsieab2_map_images", "default": False},
                {"id": "transparent_menu_bar", "default": False},
                {"id": "no_ai_icons", "default": True},
            ],
        }
        normal_args = patcher.argparse.Namespace(
            enable_all=True,
            disable_all=False,
            enable=None,
            disable=None,
        )
        with self.assertRaisesRegex(patcher.PatchError, r"behavior_patches: .*runtime_ready=false"):
            patcher.resolve_enabled_settings(manifest, normal_args)

        playtest_args = patcher.argparse.Namespace(
            enable_all=False,
            disable_all=False,
            enable=None,
            disable=None,
            final_playtest_all_enabled=True,
        )
        _settings, enabled = patcher.resolve_enabled_settings(manifest, playtest_args)
        self.assertEqual(
            enabled,
            {"core_executable", "holiday_furniture", "behavior_patches"},
        )

    def test_final_playtest_profile_rejects_unknown_default_on_id(self):
        args = patcher.argparse.Namespace(
            enable_all=False,
            disable_all=False,
            enable=None,
            disable=None,
            final_playtest_all_enabled=True,
        )
        manifest = {
            "final_playtest_profile": {
                "id": "final_playtest_all_enabled",
                "default_on": ["missing_feature"],
            },
            "settings": [{"id": "core_executable", "default": True}],
        }
        with self.assertRaisesRegex(
            patcher.PatchError,
            r"final_playtest_profile\.default_on references unknown setting\(s\): missing_feature",
        ):
            patcher.resolve_enabled_settings(manifest, args)

    def test_final_playtest_profile_allows_unknown_explicitly_off_optional_id(self):
        args = patcher.argparse.Namespace(
            enable_all=False,
            disable_all=False,
            enable=None,
            disable=None,
            final_playtest_all_enabled=True,
        )
        manifest = {
            "final_playtest_profile": {
                "id": "final_playtest_all_enabled",
                "explicitly_default_off": ["missing_visual_patch"],
            },
            "settings": [{"id": "core_executable", "default": True}],
        }
        _settings, enabled = patcher.resolve_enabled_settings(manifest, args)
        self.assertEqual(enabled, {"core_executable"})

    def test_final_playtest_flag_requires_explicit_manifest_profile(self):
        manifest = {"settings": [{"id": "same_sex_marriage", "default": False}]}
        args = patcher.argparse.Namespace(
            enable_all=False,
            disable_all=False,
            enable=None,
            disable=None,
            final_playtest_all_enabled=True,
        )
        with self.assertRaisesRegex(patcher.PatchError, r"requires an explicit final_playtest_all_enabled"):
            patcher.resolve_enabled_settings(manifest, args)

    def test_island_events_ready_for_player_qa_is_selectable(self):
        manifest = {
            "settings": [
                {
                    "id": "island_events",
                    "default": False,
                    "readiness": {
                        "status": "ready_for_player_qa",
                        "runtime_ready": True,
                        "linked": True,
                        "reason": "Static and linked validation are complete; live player QA remains.",
                    },
                },
                {"id": "blocked_feature", "default": False, "status": "pending", "runtime_ready": False},
            ]
        }
        settings = patcher.manifest_settings(manifest)
        self.assertFalse(settings["island_events"].blocked)
        self.assertTrue(settings["blocked_feature"].blocked)

        args = gui.build_apply_namespace(
            game_dir="C:\\Games\\VF2",
            manifest="patches\\vf2.json",
            settings=settings,
            selected_settings={"island_events"},
        )
        _, enabled = patcher.resolve_enabled_settings(manifest, args)
        self.assertEqual(enabled, {"island_events"})
        island_row = next(
            row for row in patcher.settings_log(settings, enabled)["available"]
            if row["id"] == "island_events"
        )
        self.assertTrue(island_row["selectable"])
        self.assertEqual(island_row["readiness_status"], "ready_for_player_qa")
        self.assertIsNone(island_row["readiness_reason"])
        self.assertNotEqual(island_row["readiness_status"], "verified")

    def test_gui_select_all_skips_blocked_settings(self):
        settings = {
            "blocked_feature": patcher.PatchSetting(
                id="blocked_feature",
                label="Blocked",
                description="",
                default=True,
                readiness_status="STOP",
                readiness_reason="manifest status=STOP; linked=false",
            ),
            "ready_feature": patcher.PatchSetting(
                id="ready_feature",
                label="Ready",
                description="",
                default=False,
            ),
        }

        class FakeVar:
            def __init__(self):
                self.value = None

            def set(self, value):
                self.value = value

        controller = object.__new__(gui.VF2PatcherGUI)
        controller.settings = settings
        controller.setting_vars = {setting_id: FakeVar() for setting_id in settings}
        gui.VF2PatcherGUI.select_all_settings(controller)

        self.assertFalse(controller.setting_vars["blocked_feature"].value)
        self.assertTrue(controller.setting_vars["ready_feature"].value)

    def test_saved_output_parent_path_round_trips_and_drives_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "patcher_local_settings.json"
            gui.save_saved_paths(
                modded_output_parent_dir="D:\\VF2 Builds",
                modded_output_dir="D:\\VF2 Builds\\Virtual Families 2 - Modded",
                settings_path=settings_path,
            )
            self.assertEqual(
                gui.load_saved_paths(settings_path),
                {
                    "modded_output_parent_dir": "D:\\VF2 Builds",
                    "modded_output_dir": "D:\\VF2 Builds\\Virtual Families 2 - Modded",
                },
            )

    def test_update_link_points_to_standalone_patcher_releases_repo(self):
        self.assertEqual(
            gui.PATCHER_RELEASES_URL,
            "https://github.com/Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher/releases",
        )

    def test_manifest_build_label_prefers_explicit_build_number(self):
        self.assertEqual(gui.manifest_build_label({"name": "Virtual Families 2 Restoration/Addition Patcher B119"}), "B119")
        self.assertEqual(
            gui.manifest_build_label(
                {"output": {"default_exe_name": "Virtual Families 2 - Modded B120.exe"}}
            ),
            "B120",
        )
        self.assertEqual(gui.manifest_build_label({"name": "VF2 patcher"}), "")


class PleaseWaitFeedbackTests(unittest.TestCase):
    """The window must say it is working before it blocks.

    load_manifest_settings() runs on the Tk main thread, so nothing redraws
    until it returns; and during a run every print() the patcher makes is
    captured and only shown at the end, so the log stays empty through the
    verification pass. Both look like a frozen window.
    """

    def setUp(self):
        try:
            import tkinter as tk
        except ImportError:  # pragma: no cover - tkinter is part of CPython
            self.skipTest("tkinter is not available")
        try:
            self.root = tk.Tk()
        except Exception:
            self.skipTest("no display available for Tk")
        self.root.withdraw()
        self.app = gui.VF2PatcherGUI(self.root)
        self.shown = []
        original = self.app._render_settings_placeholder

        def spy(text):
            self.shown.append(text)
            return original(text)

        self.app._render_settings_placeholder = spy

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _manifest(self, tmp):
        path = Path(tmp) / "manifest.json"
        path.write_text('{"target_files": [], "settings": []}', encoding="utf-8")
        return path

    def test_loading_shows_the_wait_popup_and_works_off_the_main_thread(self):
        """The load must run through the wait popup, not on the main thread.

        A status line plus one update_idletasks() still freezes the window --
        Windows relabels it "(Not Responding)" -- which is what the ported VV
        popup exists to prevent. So this asserts the mechanism, not a string:
        the work reaches _run_with_wait, and it does not run on the thread that
        is supposed to be pumping the event loop.
        """
        seen = {}
        original = self.app._run_with_wait

        def spy(message, work):
            seen["message"] = message
            seen["caller_thread"] = threading.current_thread().ident

            def wrapped():
                seen["work_thread"] = threading.current_thread().ident
                return work()

            return original(message, wrapped)

        self.app._run_with_wait = spy
        with tempfile.TemporaryDirectory() as tmp:
            self.app.manifest_var.set(str(self._manifest(tmp)))
            self.assertTrue(self.app.load_manifest_settings())
        self.assertIn("Please wait", seen.get("message", ""))
        self.assertIn("Loading the patches", seen["message"])
        self.assertNotEqual(
            seen["work_thread"], seen["caller_thread"],
            "the work ran on the main thread, so the window would still freeze",
        )
        self.assertNotIn("Please wait", self.app.status_var.get())

    def _capture_after(self):
        """Collect what the worker hands back via root.after().

        _run_worker finishes by posting _finish_worker with root.after(0),
        which only runs inside a live mainloop. These tests never call
        mainloop() -- doing so would block the runner -- so the callback is
        captured and invoked directly. That still exercises the real
        _finish_worker; only Tk's delivery is stood in for.
        """
        posted = []
        original = self.root.after

        def spy(delay, callback=None, *args):
            if callback is not None and delay == 0:
                posted.append(lambda: callback(*args))
                return "after#test"
            return original(delay, callback, *args)

        self.root.after = spy
        return posted

    def _drain(self, posted, timeout=5.0):
        """Run whatever the worker posted, once it has posted it."""
        deadline = time.monotonic() + timeout
        while not posted and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(posted, "the worker never posted its completion")
        while posted:
            posted.pop(0)()

    def test_patching_shows_the_wait_popup_too_not_only_loading(self):
        """The owner asked for the popup while PATCHING, not only loading.

        _run_worker is the long one -- it copies whole game folders and
        writes patched bytes -- and it had no popup at all: only a status
        line and a log that stays empty until the run ends. This asserts a
        real WaitWindow exists while the worker is in flight, so removing
        the call fails the test rather than passing on a string.
        """
        import tkinter as tk

        during = {}
        started = threading.Event()
        release = threading.Event()

        def slow_work():
            started.set()
            release.wait(5)

        posted = self._capture_after()
        self.app._run_worker("Apply", slow_work)
        self.assertTrue(started.wait(5), "the worker never started")
        during["wait"] = getattr(self.app, "_work_wait", None)
        during["is_window"] = isinstance(during["wait"], gui.WaitWindow)
        during["exists"] = bool(
            during["wait"] is not None and during["wait"].winfo_exists()
        )
        release.set()
        self._drain(posted)

        self.assertTrue(
            during["is_window"],
            "no WaitWindow while patching -- the window would look frozen",
        )
        self.assertTrue(during["exists"], "the wait popup was not on screen")
        self.assertIsNone(
            getattr(self.app, "_work_wait", None),
            "the wait popup outlived the run, so it would sit there forever",
        )

    def test_a_popup_that_fails_to_build_does_not_stay_on_screen(self):
        """WaitWindow can raise AFTER putting a window on screen.

        Toplevel.__init__ succeeds and maps the window; _take_grab() can then
        give up on its deadline and raise. The assignment to `wait` never
        completes, so _work_wait stays None and _finish_worker has nothing to
        close -- leaving a popup with its own X disabled sitting there for the
        rest of the session.

        The patch still has to proceed (a popup that cannot be built must not
        stop the work the user asked for), so the orphan has to be destroyed on
        the way out rather than by refusing to run.
        """
        import tkinter as tk

        original = gui.WaitWindow
        built = []

        class ExplodingWaitWindow(original):
            def __init__(self, parent, title, message, modal=True):
                super().__init__(parent, title, message, modal=False)
                built.append(self)
                raise tk.TclError("grab timed out")

        gui.WaitWindow = ExplodingWaitWindow
        try:
            posted = self._capture_after()
            self.app._run_worker("Apply", lambda: None)
            self._drain(posted)
        finally:
            gui.WaitWindow = original

        self.assertTrue(built, "the test never reached WaitWindow construction")
        self.assertIsNone(
            getattr(self.app, "_work_wait", None),
            "a popup that failed to build was recorded as the live one",
        )
        for window in built:
            self.assertFalse(
                window.winfo_exists(),
                "the half-built popup is still on screen; its X is disabled, so "
                "the user cannot dismiss it for the rest of the session",
            )

    def test_a_failed_run_still_closes_the_wait_popup(self):
        """A crash must not leave a modal popup over a dead UI.

        The popup takes a grab, so if it survived a failure the user could
        not click anything -- including the error dialog explaining what
        went wrong. _finish_worker closes it before showing that dialog.
        """
        shown = []
        self.app._show_apply_success = lambda summary: None
        gui.messagebox.showerror = lambda *a, **k: shown.append(a)

        def boom():
            raise RuntimeError("patching blew up")

        posted = self._capture_after()
        self.app._run_worker("Apply", boom)
        self._drain(posted)

        self.assertIn("failed", self.app.status_var.get())
        self.assertIsNone(
            getattr(self.app, "_work_wait", None),
            "the popup survived a failure and would block the whole app",
        )
        # grab_current() is None when nothing holds a grab; Tk stringifies
        # that as "None", so compare the object rather than its text.
        self.assertIsNone(
            self.root.grab_current(),
            "a grab outlived the failed run, so every control stays dead",
        )

    def test_the_wait_popup_cannot_be_closed_and_stops_a_second_run(self):
        # The X does nothing because the work cannot be cancelled part way
        # without leaving a half-copied game folder, and the grab is what
        # blocks a second click on Apply while the first is running.
        wait = gui.WaitWindow(self.root, "Please wait", "Please wait" + ELLIPSIS)
        try:
            # A handler IS bound, which is what stops Tk's default destroy;
            # an unbound protocol would close the window on the X.
            self.assertTrue(wait.protocol("WM_DELETE_WINDOW"),
                            "no close handler bound, so the X would destroy it")
            self.assertFalse(wait.resizable()[0])
            self.assertFalse(wait.resizable()[1])
        finally:
            wait.close()

    def test_the_modal_grab_is_real_not_best_effort(self):
        # A grab that quietly fails leaves the controls live, and a
        # double-click on Apply could start two patch workers against the same
        # output folder. The window waits for visibility and then grabs for
        # real, so a failure here is an error rather than a silent no-op.
        wait = gui.WaitWindow(self.root, "Please wait", "Please wait" + ELLIPSIS)
        try:
            self.assertEqual(str(wait.grab_current()), str(wait))
        finally:
            wait.close()

    def test_centering_keeps_negative_virtual_desktop_coordinates(self):
        # On a monitor left of or above the primary one the parent's root
        # coordinates are legitimately negative. Clamping to zero would throw
        # the popup onto the primary display while it holds a modal grab, so
        # the app would look frozen with the explanation on another screen.
        source = Path(gui.__file__).read_text(encoding="utf-8")
        centre = source[source.index("def _center"):source.index("def close")]
        self.assertNotIn("max(0, x)", centre)
        self.assertNotIn("max(0, y)", centre)
        # The screen-centred fallback still clamps: there a negative value
        # really would be off-screen.
        self.assertIn("max(0, (self.winfo_screenwidth()", centre)

    def test_a_failure_in_the_work_surfaces_on_the_main_thread(self):
        # Captured on the worker and re-raised here, otherwise it vanishes
        # into the thread and the caller sees a silent success.
        def boom():
            raise RuntimeError("worker exploded")

        with self.assertRaises(RuntimeError):
            self.app._run_with_wait("Please wait" + ELLIPSIS, boom)

    def test_the_busy_cursor_is_always_restored(self):
        # Including on failure: a window left on the watch cursor looks
        # permanently busy, which is the impression this feature removes.
        with tempfile.TemporaryDirectory() as tmp:
            self.app.manifest_var.set(str(self._manifest(tmp)))
            self.app.load_manifest_settings()
            self.assertEqual(self.root.cget("cursor"), "")
            self.app.manifest_var.set(str(Path(tmp) / "missing.json"))
            self.assertFalse(self.app.load_manifest_settings())
            self.assertEqual(self.root.cget("cursor"), "")

    def test_a_failed_load_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.app.manifest_var.set(str(Path(tmp) / "missing.json"))
            self.assertFalse(self.app.load_manifest_settings())
            self.app.manifest_var.set(str(self._manifest(tmp)))
            self.assertTrue(self.app.load_manifest_settings())

    def test_a_run_says_it_is_working_before_the_log_fills(self):
        self.app._run_worker("Dry Run", lambda: None, dry_run=True)
        self.assertIn("please wait", self.app.status_var.get().lower())
        for _ in range(50):
            self.root.update()
            if "Checking your game files" in self.app.log_text.get("1.0", "end"):
                break
        log = self.app.log_text.get("1.0", "end")
        self.assertIn("Please wait", log)
        self.assertIn("Checking your game files", log)

    def test_a_failed_load_cannot_leave_a_hidden_selection_applyable(self):
        """A failed load must invalidate the previously loaded manifest.

        Rendering the placeholder destroys the setting controls. If the
        loaded-manifest state survived, restoring the old path would make
        _ensure_manifest_settings_loaded() treat it as current, and Apply
        would read BooleanVars belonging to widgets that no longer exist --
        applying a selection nobody could see or change.
        """
        with tempfile.TemporaryDirectory() as tmp:
            good = self._manifest(tmp)
            self.app.manifest_var.set(str(good))
            self.assertTrue(self.app.load_manifest_settings())
            loaded = self.app.loaded_manifest_path
            self.assertIsNotNone(loaded)

            missing = Path(tmp) / "gone.json"
            self.app.manifest_var.set(str(missing))
            self.assertFalse(self.app.load_manifest_settings())

            # Nothing may survive that a later Apply could read.
            self.assertIsNone(self.app.loaded_manifest_path)
            self.assertEqual(self.app.setting_vars, {})
            self.assertEqual(self.app.settings, {})

            # Restoring the original path must force a real reload.
            self.app.manifest_var.set(str(good))
            self.assertTrue(self.app._ensure_manifest_settings_loaded())
            self.assertEqual(self.app.loaded_manifest_path, loaded)

    def test_a_destroyed_label_does_not_raise(self):
        # Forcing a redraw flushes queued idle resizes for labels a reload has
        # already destroyed.
        import tkinter as tk

        widget = tk.Text(self.root)
        widget.destroy()
        self.app._resize_markup_label(widget)

class UpdatesLinkTests(unittest.TestCase):
    """The Check for updates link must exist and look clickable.

    It was reported as missing when it had been on screen the whole time: a
    blue label with no underline reads as static text, so nobody tried to
    click it.
    """

    # The copy this suite exercises. tests/ runs against src/, work/ against
    # its own, which is the copy the exporter actually ships.
    GUI = ROOT / "work" / "offline_vf2_patcher_gui.py"

    def test_link_is_present_and_styled_as_a_link(self):
        source = self.GUI.read_text(encoding="utf-8")
        for probe in (
            'text="Check for updates"',
            "_open_updates_url",
            "PATCHER_RELEASES_URL",
            'style.configure("Link.TLabel"',
            'style.configure("LinkHover.TLabel"',
            'update_link.bind("<Enter>"',
            'update_link.bind("<Leave>"',
        ):
            with self.subTest(probe=probe):
                self.assertIn(probe, source)

    def test_link_font_follows_the_configured_default(self):
        # Pinning a point size shrinks the link wherever TkDefaultFont has
        # been enlarged, which is the opposite of making it noticeable.
        source = self.GUI.read_text(encoding="utf-8")
        self.assertIn('tkfont.nametofont("TkDefaultFont")', source)
        self.assertIn("configure(underline=True)", source)
        self.assertNotIn('font=("", 9, "underline")', source)

    def test_both_copies_stay_identical(self):
        # The exporter ships work/; a fix applied only to src/ never reaches
        # anyone's download.
        # Built with joinpath rather than the / operator on a "work" literal:
        # the sync rule that generates the tests/ copy rewrites ROOT / "work"
        # to ROOT / "src", which would make this compare src against itself and
        # never detect the drift it exists to catch.
        shipped = ROOT.joinpath("work", "offline_vf2_patcher_gui.py")
        public = ROOT.joinpath("src", "offline_vf2_patcher_gui.py")
        self.assertEqual(shipped.read_bytes(), public.read_bytes())


if __name__ == "__main__":
    unittest.main()
