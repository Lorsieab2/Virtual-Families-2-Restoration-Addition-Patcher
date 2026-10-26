#!/usr/bin/env python3
"""The Tools tab, the "?" buttons and the Back Up / Restore Saves dialogs in the patcher window.

All saves here are temp copies: vf2_save_backup.documents_folder is pointed at a temp Documents folder.
"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import offline_vf2_patcher_gui as gui
import vf2_how_to_use as guides
import vf2_save_backup as sb

FOLDER = "Virtual Families 2 - Modded B202"


class NoGame:
    def find_game(self, save_folder_name):
        return []

    def suspend(self, pid, exe_name):
        raise AssertionError("no game is running")

    def resume(self, handle):
        pass


class ToolsTabTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
        except ImportError:  # pragma: no cover
            self.skipTest("tkinter is not available")
        try:
            self.root = tk.Tk()
        except Exception:
            self.skipTest("no display available for Tk")
        self.root.withdraw()
        self.app = gui.VF2PatcherGUI(self.root)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.docs = Path(self._tmp.name) / "Documents"
        self.folder = self.docs / "LDW" / FOLDER
        self.folder.mkdir(parents=True)
        (self.folder / "Virtual Families 21.ldw").write_bytes(b"family one")
        (self.folder / "Virtual Families 25.ldw").write_bytes(b"family five")
        patches = [
            mock.patch.object(sb, "documents_folder", return_value=self.docs),
            mock.patch.object(sb, "WindowsProcesses", NoGame),
            mock.patch.object(gui.messagebox, "showinfo"),
            mock.patch.object(gui.messagebox, "showerror"),
        ]
        self.info, self.error = patches[2].start(), patches[3].start()
        patches[0].start()
        patches[1].start()
        self.addCleanup(mock.patch.stopall)
        # Run the "worker" inline: the wait window is covered by the existing suite.
        self.app._run_with_wait = lambda message, work, keep_open=False: work()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_patches_and_tools_are_separate_tabs(self):
        names = [self.app.notebook.tab(tab, "text") for tab in self.app.notebook.tabs()]
        self.assertEqual(names, ["Patches", "Tools"])
        self.assertIs(self.app.settings_canvas.winfo_toplevel(), self.root)
        self.assertTrue(str(self.app.settings_canvas).startswith(str(self.app.patches_tab)))

    def test_existing_header_and_restore_controls_are_kept(self):
        source = (ROOT / "src" / "offline_vf2_patcher_gui.py").read_text(encoding="utf-8")
        for probe in ('text="Check for updates"', "_open_updates_url", '"Restore Backup", self.start_restore', "Restore log"):
            self.assertIn(probe, source)

    def test_tools_tab_has_both_tools_and_the_guide(self):
        labels = []

        def walk(widget):
            for child in widget.winfo_children():
                try:
                    labels.append(str(child.cget("text")))
                except Exception:
                    pass
                walk(child)

        walk(self.app.tools_tab)
        self.assertIn("Back Up Saves...", labels)
        self.assertIn("Restore Saves...", labels)
        self.assertIn("How to Use...", labels)

    def test_every_guide_has_a_question_mark_button_that_opens_it(self):
        # A setting's guide has its "?" on the setting's row (see the next test); every other guide's "?" is
        # there from the start.
        controls = set(guides.keys()) - set(guides.setting_keys())
        self.assertEqual(self.app.help_keys - {"getting_started"}, controls - {"getting_started"})
        self.assertEqual(self.app.help_keys, controls)
        for key in guides.keys():
            with self.subTest(key=key):
                window = self.app._show_how_to_use(key)
                self.assertIn(guides.control_title(key), window.title())
                self.assertIs(self.app._show_how_to_use(key), window)     # one window per guide
                window.destroy()

    def test_a_setting_with_a_guide_has_its_question_mark_on_its_row(self):
        import json
        self.assertEqual(guides.setting_keys(), ["family_history"])
        rows = [{"id": "family_history", "label": "Family History log", "description": "The log.",
                 "default": False, "category": "experimental"},
                {"id": "time_controls", "label": "Time Controls", "description": "Speeds.", "default": True,
                 "category": "optional"}]
        path = Path(self._tmp.name) / "manifest.json"
        path.write_text(json.dumps({"manifest_version": 1, "settings": rows}), encoding="utf-8")
        self.app.manifest_var.set(str(path))
        self.app._run_with_wait = lambda message, work, keep_open=False: (work(), None) if keep_open else work()
        self.assertTrue(self.app.load_manifest_settings())
        self.assertIn("family_history", self.app.help_keys)
        buttons = []

        def walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == "TButton" and str(child.cget("text")) == "?":
                    buttons.append(child)
                walk(child)
        walk(self.app.settings_inner)
        self.assertEqual(len(buttons), 1, "only the setting with a guide gets a ?")
        row = buttons[0].master
        self.assertIn("Family History log", [str(c.cget("text")) for c in row.winfo_children()
                                             if c.winfo_class() == "TCheckbutton"])
        buttons[0].invoke()
        window = self.app._help_windows.get("family_history")
        self.assertIsNotNone(window)
        self.assertIn("Family History log", window.title())
        window.destroy()

    def test_a_control_without_a_guide_fails_while_the_window_is_built(self):
        with self.assertRaises(KeyError):
            self.app._help_button(self.root, "no_such_control")

    def test_full_guide_lists_every_topic(self):
        window = self.app.show_how_to_use_guide()
        listed = window._vf2_topics.get(0, "end")
        for key in guides.keys():
            self.assertIn("  " + guides.control_title(key), listed)
        self.assertIn("Back Up Saves", window._vf2_page.get("1.0", "end") + " ".join(listed))
        window.destroy()

    def test_back_up_saves_chooser_ticks_only_patcher_folders_and_backs_up(self):
        (self.docs / "LDW" / "Virtual Families 2").mkdir()
        (self.docs / "LDW" / "Virtual Families 2" / "Virtual Families 21.ldw").write_bytes(b"vanilla")
        chooser = self.app.back_up_saves()
        try:
            ticked = {folder.name: var.get() for folder, var in chooser._vf2_choices}
            self.assertEqual(ticked, {FOLDER: True, "Virtual Families 2": False})
            with mock.patch.object(self.app, "_show_backup_results") as results:
                chooser._vf2_start()
            outcomes = results.call_args.args[0]
        finally:
            if chooser.winfo_exists():
                chooser.destroy()
        self.assertEqual(len(outcomes), 1)
        folder, result, error = outcomes[0]
        self.assertIsNone(error)
        self.assertEqual(folder.name, FOLDER)
        self.assertEqual(len(sb.list_backups(self.folder)), 1)
        self.assertEqual(sb.list_backups(self.docs / "LDW" / "Virtual Families 2"), [])     # not ticked, not touched
        self.assertIn("1 of 1", self.app.status_var.get())

    def test_back_up_with_no_save_folders_says_so(self):
        with mock.patch.object(sb, "documents_folder", return_value=self.docs / "empty"):
            self.assertIsNone(self.app.back_up_saves())
        self.info.assert_called_once()
        self.assertIn("No Virtual Families 2 save folders", self.info.call_args.args[1])

    def test_restore_with_no_backups_says_so(self):
        self.assertIsNone(self.app.restore_saves())
        self.assertIn("no save backups", self.info.call_args.args[1])

    def _backed_up(self):
        info = sb.copy_save_folder(self.folder, datetime(2026, 10, 24, 12, 0, 0))
        (self.folder / "Virtual Families 21.ldw").write_bytes(b"family one CHANGED")
        return sb.list_backups(self.folder)[0]

    def test_restore_asks_first_and_declining_changes_nothing(self):
        info = self._backed_up()
        with mock.patch.object(gui.messagebox, "askyesno", return_value=False) as ask:
            restored = self.app._run_restore(self.root, self.folder, info, None)
        self.assertFalse(restored)
        ask.assert_called_once()
        self.assertIn("Replace: Virtual Families 21.ldw", ask.call_args.args[1])
        self.assertEqual((self.folder / "Virtual Families 21.ldw").read_bytes(), b"family one CHANGED")
        self.assertEqual(len(sb.list_backups(self.folder)), 1)

    def test_restore_after_yes_backs_up_then_restores(self):
        info = self._backed_up()
        with mock.patch.object(gui.messagebox, "askyesno", return_value=True):
            restored = self.app._run_restore(self.root, self.folder, info, None)
        self.assertTrue(restored)
        self.assertEqual((self.folder / "Virtual Families 21.ldw").read_bytes(), b"family one")
        labels = [i.label for i in sb.list_backups(self.folder)]
        self.assertEqual(sum("(before restore)" in label for label in labels), 1)
        self.assertIn("before the restore", self.info.call_args.args[1])

    def test_restore_is_refused_while_the_game_runs(self):
        info = self._backed_up()
        with mock.patch.object(sb, "running_game_count", return_value=1), \
                mock.patch.object(gui.messagebox, "askyesno") as ask:
            restored = self.app._run_restore(self.root, self.folder, info, None)
        self.assertFalse(restored)
        ask.assert_not_called()
        self.error.assert_called_once()
        self.assertEqual((self.folder / "Virtual Families 21.ldw").read_bytes(), b"family one CHANGED")

    def test_restore_window_lists_backups_and_one_slot_choice(self):
        self._backed_up()
        window = self.app.restore_saves()
        try:
            self.assertEqual(len(window._vf2_entries), 1)
            self.assertEqual(window._vf2_listbox.size(), 1)
        finally:
            window.destroy()

    def test_the_busy_state_logic_of_the_patch_buttons_is_unchanged(self):
        # The patch buttons are still registered as busy controls (disabled during a run).
        self.assertTrue(self.app.busy_controls)

    # -- Rename Family ------------------------------------------------------

    def _real_saves(self):
        """Slot 1 becomes a copy of a real family save; slot 0 a copy of a real settings file."""
        import gzip
        fixtures = ROOT / "tests" / "fixtures" / "vf2_saves"
        (self.folder / "Virtual Families 20.ldw").write_bytes(gzip.decompress((fixtures / "settings_slot0.ldw.gz").read_bytes()))
        (self.folder / "Virtual Families 21.ldw").write_bytes(
            gzip.decompress((fixtures / "one_generation_slot3.ldw.gz").read_bytes()))

    def _snapshot(self):
        return {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob("*") if p.is_file()}

    def test_rename_family_is_on_the_tools_tab_with_a_guide(self):
        labels = []

        def walk(widget):
            for child in widget.winfo_children():
                try:
                    labels.append(str(child.cget("text")))
                except Exception:
                    pass
                walk(child)

        walk(self.app.tools_tab)
        self.assertIn("Rename Family...", labels)
        self.assertIn("rename_family", self.app.help_keys)

    def test_rename_dialog_offers_only_loadable_slots_and_checks_the_name(self):
        self._real_saves()
        dialog = self.app.rename_family()
        try:
            self.assertEqual(dialog._vf2_slot_var.get(), 1)            # slot 5 holds b"family five": not offered
            self.assertEqual(dialog._vf2_name_var.get(), "Lorsieab2")
            self.assertIn("already", dialog._vf2_problem_var.get())
            dialog._vf2_name_var.set("A" * 20)
            self.assertIn("19", dialog._vf2_problem_var.get())
            dialog._vf2_name_var.set("NEW PLAYER")
            self.assertIn("empty slot", dialog._vf2_problem_var.get())
            before = self._snapshot()
            dialog._vf2_start()                                        # refused: nothing is written
            self.assertEqual(self._snapshot(), before)
        finally:
            if dialog.winfo_exists():
                dialog.destroy()

    def test_a_confirmed_rename_backs_up_and_renames(self):
        import vf2_save_reader as reader
        self._real_saves()
        dialog = self.app.rename_family()
        dialog._vf2_name_var.set("The Smiths")
        with mock.patch.object(gui.messagebox, "askyesno", return_value=True):
            dialog._vf2_start()
        save = reader.read_family_save(self.folder / "Virtual Families 21.ldw")
        self.assertEqual(save.nickname, "The Smiths")
        self.assertEqual(reader.read_settings(self.folder / "Virtual Families 20.ldw").player_names[0], "The Smiths")
        backups = sb.list_backups(self.folder)
        self.assertTrue(backups and backups[0].before_rename)
        self.assertEqual(self.app.status_var.get(), "Rename Family: family slot 1 is now called The Smiths.")
        self.info.assert_called()

    def test_a_running_game_stops_the_rename(self):
        self._real_saves()
        before = self._snapshot()

        class Running(NoGame):
            def find_game(self, save_folder_name):
                return [(7, save_folder_name + ".exe")]

        dialog = self.app.rename_family()
        dialog._vf2_name_var.set("The Smiths")
        with mock.patch.object(sb, "WindowsProcesses", Running), \
                mock.patch.object(gui.messagebox, "askyesno", return_value=True):
            dialog._vf2_start()
        self.assertEqual(self._snapshot(), before)
        self.error.assert_called_once()
        self.assertIn("Close the game first", self.error.call_args[0][1])
        self.assertEqual(self.app.status_var.get(), "Rename Family: nothing was renamed.")

    # -- Game Speed ---------------------------------------------------------

    def _speed_saves(self):
        """Slot 1: a copy of a real paused family save; slot 2: a real one at normal speed."""
        import gzip
        fixtures = ROOT / "tests" / "fixtures" / "vf2_saves"
        (self.folder / "Virtual Families 21.ldw").write_bytes(
            gzip.decompress((fixtures / "one_generation_slot3.ldw.gz").read_bytes()))
        (self.folder / "Virtual Families 22.ldw").write_bytes(
            gzip.decompress((fixtures / "pending_birth_slot1.ldw.gz").read_bytes()))

    def test_game_speed_is_on_the_tools_tab_with_a_guide(self):
        labels = []

        def walk(widget):
            for child in widget.winfo_children():
                try:
                    labels.append(str(child.cget("text")))
                except Exception:
                    pass
                walk(child)

        walk(self.app.tools_tab)
        self.assertIn("Game Speed...", labels)
        self.assertIn("game_speed", self.app.help_keys)

    # -- Game Mechanics -----------------------------------------------------

    def test_game_mechanics_is_on_the_tools_tab_with_a_guide_and_opens_once(self):
        labels = []

        def walk(widget):
            for child in widget.winfo_children():
                try:
                    labels.append(str(child.cget("text")))
                except Exception:
                    pass
                walk(child)

        walk(self.app.tools_tab)
        self.assertIn("Game Mechanics...", labels)
        self.assertIn("game_mechanics", self.app.help_keys)
        before = self._snapshot()
        window = self.app.game_mechanics()
        try:
            self.assertEqual(window.title(), "Game Mechanics")
            self.assertIs(self.app.game_mechanics(), window)        # a second click brings the same window
            self.assertIn("UNCONFIRMED", window.mechanics_page.get("1.0", "end"))
        finally:
            window.destroy()
        self.assertEqual(self._snapshot(), before)                   # the saves are untouched
        self.assertIsNot(self.app.game_mechanics(), window)          # closed: a new one opens

    def test_game_speed_dialog_shows_each_speed_and_sets_one(self):
        import vf2_game_speed as gsp
        self._speed_saves()
        dialog = self.app.game_speed()
        try:
            self.assertEqual(dialog._vf2_slot_var.get(), 1)
            self.assertEqual(dialog._vf2_target_var.get(), "Normal")       # slot 1 is paused
            dialog._vf2_target_var.set("Paused")
            self.assertIn("already", dialog._vf2_problem_var.get())
            before = self._snapshot()
            dialog._vf2_start()                                          # refused: nothing is written
            self.assertEqual(self._snapshot(), before)
            dialog._vf2_slot_var.set(2)
            self.assertEqual(dialog._vf2_target_var.get(), "Paused")
            with mock.patch.object(gui.messagebox, "askyesno", return_value=True) as ask:
                dialog._vf2_start()
            self.assertIn("from Normal to Paused", ask.call_args[0][1])
        finally:
            if dialog.winfo_exists():
                dialog.destroy()
        states = {s.slot: s.state.label for s in gsp.read_slots(self.folder) if s.state}
        self.assertEqual(states, {1: "Paused", 2: "Paused"})
        self.assertTrue(sb.list_backups(self.folder)[0].before_speed_change)
        self.assertEqual(self.app.status_var.get(), "Game Speed: family slot 2 is now Paused.")
        self.info.assert_called()

    def test_a_running_game_stops_the_speed_change(self):
        self._speed_saves()
        before = self._snapshot()

        class Running(NoGame):
            def find_game(self, save_folder_name):
                return [(7, save_folder_name + ".exe")]

        dialog = self.app.game_speed()
        with mock.patch.object(sb, "WindowsProcesses", Running), \
                mock.patch.object(gui.messagebox, "askyesno", return_value=True):
            dialog._vf2_start()
        self.assertEqual(self._snapshot(), before)
        self.error.assert_called_once()
        self.assertIn("Close the game first", self.error.call_args[0][1])
        self.assertEqual(self.app.status_var.get(), "Game Speed: nothing was changed.")


if __name__ == "__main__":
    unittest.main()
