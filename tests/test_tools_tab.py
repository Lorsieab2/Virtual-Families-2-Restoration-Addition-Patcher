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
        self.assertIn("Update Family Logs", labels)

    def _family_save(self, slot: int = 2) -> None:
        sys.path.insert(0, str(ROOT / "tests"))
        from vf2_save_builder import SaveBuilder
        b = SaveBuilder(nickname="Smiths").villager(0, "Ann", 1, 30).generation(0, ("Ann", 1, 0))
        b.write(self.folder / f"Virtual Families 2{slot}.ldw")

    def test_opening_the_tools_tab_updates_the_family_logs_quietly(self):
        self._family_save()
        self.app.notebook.select(self.app.patches_tab)
        self.app._tools_tab_changed()
        self.assertFalse((self.folder / "Virtual Families 2 Patcher").exists())   # not on the Patches tab
        self.app.notebook.select(self.app.tools_tab)
        self.app._tools_tab_changed()
        history = self.folder / "Virtual Families 2 Patcher" / "Save 2" / "Logs" / "Family History" / "Family History 1.txt"
        self.assertTrue(history.read_bytes().startswith(b"Family: Smiths (Save 2)\r\n"))
        self.assertIn("Family Logs:", self.app.status_var.get())
        self.info.assert_not_called()
        self.error.assert_not_called()

    def test_update_family_logs_button_shows_each_slot(self):
        self._family_save()
        with mock.patch.object(self.app, "_show_family_logs_results") as shown:
            outcomes = self.app.update_family_logs()
        folder, results, error = outcomes[0]
        self.assertEqual(folder.name, FOLDER)
        self.assertIsNone(error)
        self.assertEqual({r.slot: r.status for r in results}[2], "backfilled")
        self.assertEqual({r.slot: r.status for r in results}[1], "unreadable")   # setUp's placeholder file
        shown.assert_called_once()
        dialog = self.app._show_family_logs_results(outcomes)
        dialog.destroy()

    def test_update_family_logs_is_refused_while_the_game_runs(self):
        class Running(NoGame):
            def find_game(self, save_folder_name):
                return [(42, FOLDER + ".exe")]
        self._family_save()
        with mock.patch.object(sb, "WindowsProcesses", Running), mock.patch.object(self.app, "_show_family_logs_results"):
            outcomes = self.app.update_family_logs()
        self.assertIsNone(outcomes[0][1])
        self.assertIn("running", outcomes[0][2])
        self.assertFalse((self.folder / "Virtual Families 2 Patcher").exists())
        self.assertIn("Not updated while the game is running", self.app.status_var.get())

    def test_every_guide_has_a_question_mark_button_that_opens_it(self):
        self.assertEqual(self.app.help_keys - {"getting_started"}, set(guides.keys()) - {"getting_started"})
        self.assertEqual(self.app.help_keys, set(guides.keys()))
        for key in guides.keys():
            with self.subTest(key=key):
                window = self.app._show_how_to_use(key)
                self.assertIn(guides.control_title(key), window.title())
                self.assertIs(self.app._show_how_to_use(key), window)     # one window per guide
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


if __name__ == "__main__":
    unittest.main()
