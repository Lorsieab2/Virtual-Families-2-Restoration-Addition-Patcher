#!/usr/bin/env python3
"""Delete Player Slot (src/vf2_delete_slot.py): every file tied to a slot goes to the Recycle Bin; pictures stay.

The fake save folder is Copy Player Slot's (tests/test_copy_slot.py Base). The Recycle Bin is always a stand-in that
moves the files into a temp "bin" folder: no test ever calls Windows' Recycle Bin.
"""
from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import test_copy_slot as tc  # noqa: E402
import vf2_copy_slot as cs  # noqa: E402
import vf2_delete_slot as ds  # noqa: E402
import vf2_save_backup as sb  # noqa: E402
import vf2_save_reader as r  # noqa: E402

WHEN = tc.WHEN
PATCHER, DATA = tc.PATCHER, tc.DATA


class FakeBin:
    """Moves each file into a temp folder beside the save folder, as the Recycle Bin keeps it; ``refuse`` makes the
    n-th call fail before anything moves."""

    def __init__(self, folder: Path, refuse: int | None = None):
        self.root = folder.parent / "bin"
        self.folder = folder
        self.calls: list[list[Path]] = []
        self.kept: dict[Path, Path] = {}
        self.refuse = refuse

    def __call__(self, paths):
        self.calls.append(list(paths))
        if self.refuse is not None and len(self.calls) > self.refuse:
            raise OSError("the stand-in Recycle Bin refused")
        for path in paths:
            place = self.root / str(len(self.kept))
            place.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(place))
            self.kept[path] = place

    def put_back(self) -> None:
        for path, place in self.kept.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(place), str(path))


class Base(tc.Base):
    def setUp(self):
        super().setUp()
        self.put(f"{DATA}/Names/Virtual Families 21.ldw.txt", b"VF2 Names 2\n")
        # A whole-folder backup (every slot) and a folder Copy set aside from Save 1, and one from Save 2.
        self.backup = sb.copy_save_folder(self.folder, WHEN, suffix=sb.BEFORE_COPY).backup_folder
        self.aside = self.put(f"Backups/{cs.aside_name(WHEN, 1, 'Old')}/Virtual Families 21.ldw", b"old family").parent
        self.other_aside = self.put(f"Backups/{cs.aside_name(WHEN, 2, 'A - Save 1 - B')}/Virtual Families 22.ldw",
                                    b"slot 2's").parent

    def delete(self, slot=1, **kw):
        kw.setdefault("processes", tc.NoGame())
        kw.setdefault("recycle", FakeBin(self.folder))
        return ds.delete_slot(self.folder, slot, **kw)


class DeleteTests(Base):
    def test_every_file_of_the_slot_goes_to_the_recycle_bin_but_pictures(self):
        before = self.snapshot(backups=True)
        fake = FakeBin(self.folder)
        result = self.delete(recycle=fake)
        self.assertIsNone(result.problem)
        after = self.snapshot(backups=True)
        gone = set(before) - set(after)
        slot1 = [Path("Virtual Families 21.ldw"), Path("Virtual Families 221.ldw"),
                 Path(f"{DATA}/Children/Virtual Families 21.ldw.dat"), Path(f"{DATA}/Children/Virtual Families 221.ldw.dat"),
                 Path(f"{DATA}/Outfits/Virtual Families 21.ldw.dat"), Path(f"{DATA}/Outfits/Virtual Families 221.ldw.dat"),
                 Path(f"{DATA}/Names/Virtual Families 21.ldw.txt"),
                 Path(f"{PATCHER}/Save 1/Logs/Family History/Family History 1.txt"),
                 Path(f"{PATCHER}/Save 1/Logs/Family History/Family History 2.txt"),
                 Path(f"{PATCHER}/Save 1/Data/Family Tree/Virtual Families 2 Family Tree - Save 1.tree"),
                 Path(f"{PATCHER}/Save 1/Data/Family Tree/Virtual Families 2 Family Tree Edits - Save 1.json")]
        backup = self.backup.relative_to(self.folder)
        expected = set(slot1) | {backup / p for p in slot1} | {Path("Backups") / self.aside.name / "Virtual Families 21.ldw"}
        self.assertEqual(gone, expected)
        self.assertEqual(set(fake.kept), {self.folder / p for p in expected})       # only through the Recycle Bin
        picture = Path(f"{PATCHER}/Save 1/Family Tree/Virtual Families 2 Family Tree - Save 1.png")
        self.assertIn(picture, after)                                       # pictures stay
        self.assertIn(backup / picture, after)
        self.assertEqual(len(result.pictures), 2)
        # Other slots, shared files and other slots' set-aside folders are untouched.
        for key in (Path("Virtual Families 22.ldw"), Path("ldwLog.txt"), backup / "Virtual Families 22.ldw",
                    Path("Backups") / self.other_aside.name / "Virtual Families 22.ldw"):
            self.assertEqual(after[key], before[key])
        self.assertFalse(self.aside.exists())                                # its emptied set-aside folder removed
        self.assertFalse((self.folder / PATCHER / "Save 1" / "Logs").exists())
        # The settings file, last: NEW PLAYER, not in use. No new backup was made.
        settings = r.parse_settings(after[Path("Virtual Families 20.ldw")])
        self.assertEqual(settings.player_names[0], "NEW PLAYER")
        self.assertFalse(settings.slot_in_use[0])
        self.assertEqual(settings.player_names[1:], r.parse_settings(before[Path("Virtual Families 20.ldw")]).player_names[1:])
        self.assertEqual([b.path for b in sb.list_backups(self.folder)], [self.backup])
        self.assertEqual(result.backups_touched, 1)
        self.assertEqual(result.asides, [self.aside])

    def test_a_recycle_bin_restore_brings_every_file_back(self):
        before = self.snapshot(backups=True)
        fake = FakeBin(self.folder)
        self.delete(recycle=fake)
        fake.put_back()
        after = self.snapshot(backups=True)
        for key, data in before.items():
            if key.name != "Virtual Families 20.ldw":
                self.assertEqual(after.get(key), data, str(key))

    def test_a_running_game_or_a_changed_slot_is_refused(self):
        before = self.snapshot(backups=True)
        fake = FakeBin(self.folder)
        with self.assertRaises(ds.GameRunning):
            self.delete(processes=tc.Running(), recycle=fake)
        shown = ds.plan_delete(self.folder, 1).signature()
        self.put(f"{PATCHER}/Save 1/Logs/Family History/Family History 3.txt", b"new")
        with self.assertRaisesRegex(ds.DeleteError, "changed after you confirmed"):
            self.delete(expected=shown, recycle=fake)
        self.assertEqual(fake.calls, [])
        (self.folder / f"{PATCHER}/Save 1/Logs/Family History/Family History 3.txt").unlink()
        self.assertEqual(self.snapshot(backups=True), before)

    def test_a_refused_batch_stops_and_says_what_went(self):
        result = self.delete(recycle=FakeBin(self.folder, refuse=1))
        self.assertIn("could not send every file", result.problem)
        self.assertTrue(result.recycled)
        self.assertTrue(result.not_recycled)
        self.assertTrue(all(not p.exists() for p in result.recycled))
        self.assertTrue(all(p.exists() for p in result.not_recycled))
        # The save itself went in the first batch, so the settings no longer list it.
        self.assertFalse(r.parse_settings((self.folder / "Virtual Families 20.ldw").read_bytes()).slot_in_use[0])

    def test_a_refused_first_batch_leaves_the_settings_alone(self):
        before = self.snapshot(backups=True)
        result = self.delete(recycle=FakeBin(self.folder, refuse=0))
        self.assertEqual(result.recycled, [])
        self.assertEqual(self.snapshot(backups=True), before)


class DeletableSlotsTests(Base):
    def test_every_slot_with_files_is_listed(self):
        self.put(f"{DATA}/Outfits/Virtual Families 25.ldw.dat", b"leftover")
        labels = dict(ds.deletable_slots(self.folder))
        self.assertEqual(labels[1], "Save 1: Lorsieab2")
        self.assertEqual(labels[5], f"Save 5: {ds.NO_SAVE}")
        self.assertNotIn(3, labels)                       # nothing at all
        self.assertIn(2, labels)

    def test_a_stopped_delete_can_be_finished(self):
        self.delete(recycle=FakeBin(self.folder, refuse=1))
        self.assertIn(1, dict(ds.deletable_slots(self.folder)))
        result = self.delete()
        self.assertIsNone(result.problem)
        self.assertNotIn(1, dict(ds.deletable_slots(self.folder)))


class ConfirmationTests(Base):
    def test_two_questions_and_no_at_either_changes_nothing(self):
        before = self.snapshot(backups=True)
        for answers in ((False, True), (True, False)):
            with self.subTest(answers=answers):
                fake = FakeBin(self.folder)
                asked, shown = [], []
                result = ds.confirm_and_delete(
                    lambda parent, title, text: asked.append(text) or answers[1],
                    lambda parent, title, text, lines, question: shown.append((text, question)) or answers[0],
                    lambda work: work(), self.folder, 1, processes=tc.NoGame(), recycle=fake)
                self.assertIsNone(result)
                self.assertEqual(len(shown), 1)
                self.assertEqual(shown[0][1], "Delete it?")
                self.assertEqual(len(asked), 0 if not answers[0] else 1)
                self.assertEqual(fake.calls, [])
        self.assertEqual(self.snapshot(backups=True), before)

    def test_yes_to_both_recycles_and_the_words_name_everything(self):
        fake = FakeBin(self.folder)
        asked, shown = [], []
        result = ds.confirm_and_delete(
            lambda parent, title, text: asked.append(text) or True,
            lambda parent, title, text, lines, question: shown.append((text, lines)) or True,
            lambda work: work(), self.folder, 1, processes=tc.NoGame(), recycle=fake)
        text, lines = shown[0]
        self.assertIn("Every file of Save 1 (Lorsieab2) goes to the Recycle Bin", text)
        self.assertIn("1 backup(s) and 1 folder(s) of files it replaced", text)
        self.assertIn("Pictures stay", text)
        self.assertEqual(sum(line.startswith("Recycled:") for line in lines), len(result.recycled))
        self.assertEqual(sum(line.startswith("Kept (pictures):") for line in lines), 2)
        self.assertTrue(asked[0].startswith("Delete Lorsieab2 from Save 1?"))
        self.assertIsNone(result.problem)


if __name__ == "__main__":
    unittest.main()
