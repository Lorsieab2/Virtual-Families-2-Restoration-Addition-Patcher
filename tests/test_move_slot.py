#!/usr/bin/env python3
"""Move Player Slot (src/vf2_move_slot.py): moves a family, with every file tied to its slot, to another slot.

The fake save folder is Copy Player Slot's (tests/test_copy_slot.py Base): temp copies of the real save fixtures and
sidecars made in their DLLs' formats. No owner save is ever opened.
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import test_copy_slot as tc  # noqa: E402
import vf2_copy_slot as cs  # noqa: E402
import vf2_move_slot as ms  # noqa: E402
import vf2_rename_family as rf  # noqa: E402
import vf2_save_backup as sb  # noqa: E402
import vf2_save_reader as r  # noqa: E402

WHEN = tc.WHEN
PATCHER, DATA = tc.PATCHER, tc.DATA


class Base(tc.Base):
    def setUp(self):
        super().setUp()
        self.put(f"{DATA}/Names/Virtual Families 21.ldw.txt", b"VF2 Names 2\n")
        self.put(f"{DATA}/Children/Virtual Families 21.ldw.unreadable-1.dat", b"set aside by the DLL")

    def move(self, source=1, target=4, **kw):
        kw.setdefault("processes", tc.NoGame())
        kw.setdefault("now", WHEN)
        return ms.move_slot(self.folder, source, target, **kw)

    def backup_snapshot(self) -> dict:
        return {p.relative_to(self.folder): p.read_bytes() for p in (self.folder / "Backups").rglob("*") if p.is_file()}


class MoveTests(Base):
    def test_everything_of_the_slot_moves_and_the_source_is_left_empty(self):
        before = self.snapshot()
        result = self.move()
        after = self.snapshot()
        moved = {
            "Virtual Families 21.ldw": "Virtual Families 24.ldw",
            "Virtual Families 221.ldw": "Virtual Families 224.ldw",
            f"{DATA}/Children/Virtual Families 21.ldw.dat": f"{DATA}/Children/Virtual Families 24.ldw.dat",
            f"{DATA}/Children/Virtual Families 221.ldw.dat": f"{DATA}/Children/Virtual Families 224.ldw.dat",
            f"{DATA}/Children/Virtual Families 21.ldw.unreadable-1.dat":
                f"{DATA}/Children/Virtual Families 24.ldw.unreadable-1.dat",
            f"{DATA}/Outfits/Virtual Families 21.ldw.dat": f"{DATA}/Outfits/Virtual Families 24.ldw.dat",
            f"{DATA}/Outfits/Virtual Families 221.ldw.dat": f"{DATA}/Outfits/Virtual Families 224.ldw.dat",
            f"{DATA}/Names/Virtual Families 21.ldw.txt": f"{DATA}/Names/Virtual Families 24.ldw.txt",
            f"{PATCHER}/Save 1/Logs/Family History/Family History 1.txt":
                f"{PATCHER}/Save 4/Logs/Family History/Family History 1.txt",
            f"{PATCHER}/Save 1/Logs/Family History/Family History 2.txt":
                f"{PATCHER}/Save 4/Logs/Family History/Family History 2.txt",
            f"{PATCHER}/Save 1/Data/Family Tree/Virtual Families 2 Family Tree - Save 1.tree":
                f"{PATCHER}/Save 4/Data/Family Tree/Virtual Families 2 Family Tree - Save 4.tree",
            f"{PATCHER}/Save 1/Data/Family Tree/Virtual Families 2 Family Tree Edits - Save 1.json":
                f"{PATCHER}/Save 4/Data/Family Tree/Virtual Families 2 Family Tree Edits - Save 4.json",
            f"{PATCHER}/Save 1/Family Tree/Virtual Families 2 Family Tree - Save 1.png":
                f"{PATCHER}/Save 4/Family Tree/Virtual Families 2 Family Tree - Save 4.png",
        }
        self.assertEqual(len(result.moved), len(moved))
        for old, new in moved.items():
            with self.subTest(old=old):
                self.assertNotIn(Path(old), after)
                self.assertIn(Path(new), after)
        self.assertFalse((self.folder / PATCHER / "Save 1").exists())         # its emptied folder removed
        # The save and its sidecars are byte for byte the same: the sidecars still describe the save.
        for old in ("Virtual Families 21.ldw", "Virtual Families 221.ldw", f"{DATA}/Children/Virtual Families 21.ldw.dat",
                    f"{DATA}/Outfits/Virtual Families 221.ldw.dat", f"{DATA}/Names/Virtual Families 21.ldw.txt"):
            self.assertEqual(after[Path(moved[old])], before[Path(old)])
        save = after[Path("Virtual Families 24.ldw")]
        self.assertTrue(cs.sidecar_describes("Children", after[Path(f"{DATA}/Children/Virtual Families 24.ldw.dat")],
                                             save))
        # Other slots and shared files are untouched.
        for key in (Path("Virtual Families 22.ldw"), Path("ldwLog.txt"), Path(f"{DATA}/Children/Virtual Families 22.ldw.dat"),
                    Path(f"{PATCHER}/Save 2/Logs/Family History/Family History 1.txt")):
            self.assertEqual(after[key], before[key])
        # The settings file: the family in Save 4, NEW PLAYER in Save 1.
        settings = r.parse_settings(after[Path("Virtual Families 20.ldw")])
        self.assertEqual(settings.player_names[3], "Lorsieab2")
        self.assertTrue(settings.slot_in_use[3])
        self.assertEqual(settings.player_names[0], "NEW PLAYER")
        self.assertFalse(settings.slot_in_use[0])
        self.assertEqual(rf.read_slots(self.folder)[3].label, "Save 4: Lorsieab2")
        # The backup came first and holds the folder as it was.
        backups = sb.list_backups(self.folder)
        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0].path.name.endswith("(before move)"))
        self.assertTrue(backups[0].label.endswith("(before move)"))
        self.assertEqual((backups[0].path / "Virtual Families 21.ldw").exists(), True)
        self.assertIsNone(result.set_aside)

    def test_the_question_names_the_revive_and_skin_tones_files(self):
        from datetime import datetime
        text = ms.move_text(ms.plan_move(self.folder, 1, 4), datetime(2026, 11, 27, 12, 0, 0))
        self.assertIn("the Revive snapshots, the skin tones,", text)

    def test_slot_numbers_inside_files_are_updated(self):
        result = self.move()
        logs = self.folder / PATCHER / "Save 4" / "Logs" / "Family History"
        for name in ("Family History 1.txt", "Family History 2.txt"):
            self.assertTrue((logs / name).read_bytes().startswith(b"Family: Lorsieab2 (Save 4)\r\n"))
        tree = json.loads((self.folder / PATCHER / "Save 4" / "Data" / "Family Tree" /
                           "Virtual Families 2 Family Tree - Save 4.tree").read_text(encoding="utf-8"))
        self.assertEqual(tree["slot"], 4)
        self.assertEqual(tree["family"], "Lorsieab2")                          # the same family, the same name
        self.assertEqual(len(result.updated), 3)

    def test_the_target_slots_leftovers_are_set_aside(self):
        leftover = self.put(f"{DATA}/Outfits/Virtual Families 24.ldw.dat", b"an earlier family's outfits")
        log = self.put(f"{PATCHER}/Save 4/Logs/Family History/Family History 1.txt", b"Family: Gone (Save 4)\r\n")
        result = self.move()
        self.assertIsNotNone(result.set_aside)
        self.assertTrue(result.set_aside.name.startswith("Replaced by move 2026-10-31 12-00-00 - Save 4 - "))
        self.assertEqual((result.set_aside / leftover.relative_to(self.folder)).read_bytes(),
                         b"an earlier family's outfits")
        self.assertEqual((result.set_aside / log.relative_to(self.folder)).read_bytes(), b"Family: Gone (Save 4)\r\n")
        self.assertNotEqual(leftover.read_bytes(), b"an earlier family's outfits")      # the moved family's now
        self.assertEqual(sorted(result.removed), sorted([leftover, log]))
        self.assertEqual([b.path.name for b in sb.list_backups(self.folder)],
                         [b.path.name for b in sb.list_backups(self.folder) if b.path.name.startswith("Backup ")])

    def test_an_occupied_target_is_replaced_and_kept(self):
        before = self.snapshot()
        old = r.read_family_save(self.other).nickname
        result = self.move(source=1, target=2)
        self.assertEqual(result.overwritten, old)
        self.assertTrue(result.set_aside.name.endswith(f" - Save 2 - {old}"))
        for relative in (Path("Virtual Families 22.ldw"), Path(f"{DATA}/Children/Virtual Families 22.ldw.dat"),
                         Path(f"{PATCHER}/Save 2/Logs/Family History/Family History 1.txt")):
            self.assertEqual((result.set_aside / relative).read_bytes(), before[relative])
        self.assertEqual((self.folder / "Virtual Families 22.ldw").read_bytes(), before[Path("Virtual Families 21.ldw")])
        self.assertFalse((self.folder / "Virtual Families 21.ldw").exists())

    def test_any_failure_puts_everything_back(self):
        self.put(f"{PATCHER}/Save 4/Logs/Family History/Family History 1.txt", b"Family: Gone (Save 4)\r\n")
        before = self.snapshot()
        folders = self.folders()
        count = len(ms.plan_move(self.folder, 1, 4).moves)
        for fail_after in (0, 1, 5, count - 1):
            with self.subTest(fail_after=fail_after):
                with self.assertRaisesRegex(cs.CopyError, "every file was put back"):
                    self.move(_fail_after=fail_after)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.folders(), folders)
                aside = [p for p in (self.folder / "Backups").iterdir() if p.name.startswith("Replaced by")]
                self.assertEqual(aside, [])

    def _read_only_cases(self):
        return {"history": self.folder / PATCHER / "Save 1/Logs/Family History/Family History 2.txt",
                "tree": self.folder / PATCHER / "Save 1/Data/Family Tree/Virtual Families 2 Family Tree - Save 1.tree",
                "settings": rf.settings_path(self.folder)}

    def test_a_read_only_file_the_move_must_rewrite_refuses_before_anything_moves(self):
        # The end-to-end check (2026-11-26): a read-only log was renamed into the target, its header rewrite failed,
        # and the rollback never renamed it back.
        import os
        for which, path in self._read_only_cases().items():
            with self.subTest(which=which):
                before, folders = self.snapshot(backups=True), self.folders()
                os.chmod(path, 0o444)
                try:
                    with self.assertRaisesRegex(ms.MoveError, "read-only.*Nothing was moved") as caught:
                        self.move(1, 5)
                finally:
                    os.chmod(path, 0o666)
                self.assertIn(path.name, str(caught.exception))
                self.assertEqual(self.snapshot(backups=True), before)
                self.assertEqual(self.folders(), folders)

    def test_a_read_only_rewrite_failing_mid_move_still_rolls_everything_back(self):
        import os
        for which, path in self._read_only_cases().items():
            for target in (5, 2):                                  # an empty target, and one with its own logs
                with self.subTest(which=which, target=target):
                    before, folders = self.snapshot(), self.folders()
                    os.chmod(path, 0o444)
                    try:
                        with mock.patch.object(ms, "_refuse_read_only", lambda plan: None, create=True):
                            with self.assertRaisesRegex(cs.CopyError, "every file was put back") as caught:
                                self.move(1, target)
                        self.assertFalse(os.access(path, os.W_OK))     # still read-only, as it was
                    finally:
                        os.chmod(path, 0o666)
                    self.assertNotIn("could not be put back", str(caught.exception))
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(self.folders(), folders)

    def test_a_failure_after_the_settings_puts_them_back(self):
        before = self.snapshot()
        with mock.patch.object(ms, "verify", side_effect=ms.MoveError("checked for the test")):
            with self.assertRaisesRegex(cs.CopyError, "every file was put back"):
                self.move()
        self.assertEqual(self.snapshot(), before)

    def test_a_running_game_is_refused_and_nothing_written(self):
        before = self.snapshot()
        with self.assertRaises(ms.GameRunning):
            self.move(processes=tc.Running())
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.folder / "Backups").exists())

    def test_a_changed_slot_after_confirming_is_refused(self):
        shown = ms.plan_move(self.folder, 1, 4).signature()
        self.put(f"{PATCHER}/Save 1/Logs/Family History/Family History 3.txt", b"Family: Lorsieab2 (Save 1)\r\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ms.MoveError, "changed after you confirmed"):
            self.move(expected=shown)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.folder / "Backups").exists())

    def test_an_empty_or_same_source_is_refused(self):
        with self.assertRaisesRegex(ms.MoveError, "no family"):
            ms.plan_move(self.folder, 3, 4)
        with self.assertRaisesRegex(ms.MoveError, "other than"):
            ms.plan_move(self.folder, 1, 1)


class NameTests(unittest.TestCase):
    def test_every_slot_mark_in_a_path(self):
        cases = {
            "Virtual Families 21.ldw": "Virtual Families 23.ldw",
            "Virtual Families 221.ldw": "Virtual Families 223.ldw",
            f"{DATA}/Children/Virtual Families 221.ldw.dat": f"{DATA}/Children/Virtual Families 223.ldw.dat",
            f"{DATA}/Names/Virtual Families 21.ldw.txt": f"{DATA}/Names/Virtual Families 23.ldw.txt",
            f"{PATCHER}/Save 1/Family Tree/Virtual Families 2 Family Tree - Save 1 - Page 2.png":
                f"{PATCHER}/Save 3/Family Tree/Virtual Families 2 Family Tree - Save 3 - Page 2.png",
            f"{PATCHER}/Save 1/Logs/Family History/Family History 11.txt":
                f"{PATCHER}/Save 3/Logs/Family History/Family History 11.txt",
        }
        for old, new in cases.items():
            with self.subTest(old=old):
                self.assertEqual(ms.moved_relative(Path(old), 1, 3), Path(new))


class ConfirmationTests(Base):
    def test_no_at_either_question_writes_nothing(self):
        before = self.snapshot()
        ran = []
        for answers in ((False, True), (True, False)):
            with self.subTest(answers=answers):
                asked, shown = [], []
                result = ms.confirm_and_move(
                    lambda parent, title, text: asked.append(text) or answers[0],
                    lambda parent, title, text, lines, question: shown.append(lines) or answers[1],
                    lambda work: ran.append(work),
                    self.folder, 1, 2, processes=tc.NoGame(), now=WHEN)
                self.assertIsNone(result)
                self.assertEqual(len(asked), 1)
                self.assertTrue(asked[0].startswith("Save 2 holds the "))
                self.assertTrue(asked[0].endswith("Replace it?"))
        self.assertEqual(ran, [])
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.folder / "Backups").exists())

    def test_an_empty_target_asks_only_the_preview_and_yes_moves_exactly_the_list(self):
        asked, shown = [], []
        result = ms.confirm_and_move(
            lambda parent, title, text: asked.append(text) or True,
            lambda parent, title, text, lines, question: shown.append((text, lines, question)) or True,
            lambda work: work(), self.folder, 1, 4, processes=tc.NoGame(), now=WHEN)
        self.assertEqual(asked, [])
        text, lines, question = shown[0]
        self.assertEqual(question, "Move it?")
        self.assertIn("Lorsieab2 will move from Save 1 to Save 4", text)
        self.assertIn("backed up first", text)
        self.assertEqual(len(lines), len(result.moved))
        self.assertIn(f"Virtual Families 21.ldw  ->  Virtual Families 24.ldw", lines)


if __name__ == "__main__":
    unittest.main()
