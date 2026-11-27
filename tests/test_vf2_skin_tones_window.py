#!/usr/bin/env python3
"""The Skin Tones window on the Tools tab (vf2_tools_gui._show_skin_tones_dialog), laid out and behaving like Rename
Family's: a save folder, a family, one row per family member with a tone box, then Apply.

All saves here are temp copies: vf2_save_backup.documents_folder is pointed at a temp Documents folder.
"""
import gzip
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import offline_vf2_patcher_gui as gui  # noqa: E402
import test_vf2_skin_tones as tst  # noqa: E402
import vf2_save_backup as sb  # noqa: E402
import vf2_skin_tones as sk  # noqa: E402

FOLDER = "Virtual Families 2 - Modded B209"
FIX = ROOT / "tests" / "fixtures" / "vf2_saves"


class NoGame:
    def find_game(self, save_folder_name):
        return []

    def suspend(self, pid, exe_name):
        raise AssertionError("no game is running")

    def resume(self, handle):
        pass


class Running(NoGame):
    def find_game(self, save_folder_name):
        return [(7, save_folder_name + ".exe")]


class SkinTonesWindowTests(unittest.TestCase):
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
        (self.folder / "Virtual Families 20.ldw").write_bytes(
            gzip.decompress((FIX / "settings_slot0.ldw.gz").read_bytes()))
        self.save = gzip.decompress((FIX / "one_generation_slot3.ldw.gz").read_bytes())
        (self.folder / "Virtual Families 21.ldw").write_bytes(self.save)
        (self.folder / "Virtual Families 25.ldw").write_bytes(b"family five")
        self.tones = sk.sidecar_path(self.folder, 1)
        self.tones.parent.mkdir(parents=True)
        self.tones.write_bytes(tst.build(self.save, tst.FAMILY))
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
        self.app._run_with_wait = lambda message, work, keep_open=False: work()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def snapshot(self):
        return {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob("*") if p.is_file()}

    def rows(self, dialog):
        return {member.name: box for member, box in dialog._vf2_state["rows"]}

    def test_the_link_and_its_guide_are_on_the_tools_tab_after_revive_records(self):
        self.assertIn("skin_tones", self.app.help_keys)
        found = []

        def walk(widget):
            for child in widget.winfo_children():
                found.append(child)
                walk(child)

        walk(self.app.tools_tab)
        links = [w for w in found if w.winfo_class() == "TLabel" and str(w.cget("style")) == "Link.TLabel"]
        texts = [str(w.cget("text")) for w in links]
        at = texts.index("Skin Tones...")
        self.assertEqual(texts[at - 1], "Revive Records...")
        self.assertIs(links[at].master, links[texts.index("Back Up Saves")].master)   # the first row of links

    def test_the_window_lists_the_family_with_a_box_per_member(self):
        dialog = self.app.skin_tones()
        try:
            self.assertEqual(dialog.title(), "Skin Tones")
            self.assertEqual(dialog._vf2_folder_box.get(), FOLDER)
            self.assertEqual(dialog._vf2_slot_list.get(0), "Save 1: Lorsieab2")
            self.assertEqual(dialog._vf2_slot_list.curselection(), (0,))
            rows = self.rows(dialog)
            self.assertEqual(rows["Elsa"].get(), "S3 Light golden")
            self.assertEqual(rows["Paulolo"].get(), "(not set yet)")
            self.assertEqual(rows["Merlino"].get(), "Game's own")
            self.assertEqual(list(rows["Elsa"].cget("values")), list(sk.PRESETS) + ["Reset to birth tone"])
            self.assertEqual(list(rows["Paulolo"].cget("values")), list(sk.PRESETS))     # no birth tone
            self.assertIsNone(rows["Zigo"])                                              # no entry: not editable
            self.assertEqual(str(dialog._vf2_apply_button.cget("state")), "disabled")    # nothing chosen yet
            self.assertEqual(dialog._vf2_problem_var.get(), "")
            dialog._vf2_pick(0, "S3 Light golden")                                       # the same tone
            self.assertEqual(str(dialog._vf2_apply_button.cget("state")), "disabled")
            dialog._vf2_pick(0, "S9 Dark")
            self.assertEqual(str(dialog._vf2_apply_button.cget("state")), "normal")
            dialog._vf2_choose(4)                                                        # b"family five"
            self.assertIn("not a Virtual Families 2 save", dialog._vf2_problem_var.get())
            self.assertEqual(str(dialog._vf2_apply_button.cget("state")), "disabled")
        finally:
            if dialog.winfo_exists():
                dialog.destroy()

    def test_a_family_with_no_tones_yet_says_so_and_offers_nothing(self):
        self.tones.unlink()
        dialog = self.app.skin_tones()
        try:
            self.assertIn("no skin tones yet", dialog._vf2_problem_var.get())
            self.assertEqual(dialog._vf2_state["rows"], [])
            self.assertEqual(str(dialog._vf2_apply_button.cget("state")), "disabled")
            dialog._vf2_start()
            self.assertFalse(self.tones.exists())
        finally:
            dialog.destroy()

    def test_apply_backs_up_and_writes_every_changed_row(self):
        dialog = self.app.skin_tones()
        dialog._vf2_pick(0, "S9 Dark")
        dialog._vf2_pick(2, "Reset to birth tone")
        dialog._vf2_pick(1, "Game's own")
        with mock.patch.object(gui.messagebox, "askyesno", return_value=True) as ask:
            dialog._vf2_start()
        asked = ask.call_args.args[1]
        self.assertIn("Elsa: S3 Light golden -> S9 Dark", asked)
        self.assertIn("Merlino: Game's own -> S7 Medium brown", asked)
        self.assertIn("Paulolo: (not set yet) -> Game's own", asked)
        tones = sk.read_file(self.tones.read_bytes())
        self.assertEqual([e.tone for e in tones.entries], [9, 15, 7, 9, 8])
        self.assertTrue(sb.list_backups(self.folder)[0].before_skin_tones)
        self.assertEqual(self.app.status_var.get(), "Skin Tones: 3 skin tone(s) changed in Save 1.")
        self.info.assert_called_once()
        self.assertTrue(dialog.winfo_exists())                       # it stays open, as Rename Family does
        self.assertEqual(self.rows(dialog)["Elsa"].get(), "S9 Dark")   # read again
        self.assertEqual(str(dialog._vf2_apply_button.cget("state")), "disabled")
        dialog.destroy()

    def test_no_changes_nothing_when_the_player_says_no(self):
        before = self.snapshot()
        dialog = self.app.skin_tones()
        dialog._vf2_pick(0, "S9 Dark")
        with mock.patch.object(gui.messagebox, "askyesno", return_value=False):
            dialog._vf2_start()
        self.assertEqual(self.snapshot(), before)
        dialog.destroy()

    def test_a_running_game_stops_it(self):
        before = self.snapshot()
        dialog = self.app.skin_tones()
        dialog._vf2_pick(0, "S9 Dark")
        with mock.patch.object(sb, "WindowsProcesses", Running), \
                mock.patch.object(gui.messagebox, "askyesno", return_value=True):
            dialog._vf2_start()
        self.assertEqual(self.snapshot(), before)
        self.error.assert_called_once()
        self.assertIn("Close the game first", self.error.call_args[0][1])
        self.assertEqual(self.app.status_var.get(), "Skin Tones: nothing was changed.")
        dialog.destroy()


if __name__ == "__main__":
    unittest.main()
