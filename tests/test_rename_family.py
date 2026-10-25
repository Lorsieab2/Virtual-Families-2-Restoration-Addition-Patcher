#!/usr/bin/env python3
"""Rename Family (src/vf2_rename_family.py): renames the name a family slot is shown under, in a closed game's saves.

Every save here is a temp copy of a real save fixture (tests/fixtures/vf2_saves). No owner save is ever opened.
"""
from __future__ import annotations

import gzip
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_rename_family as rf  # noqa: E402
import vf2_save_backup as sb  # noqa: E402
import vf2_save_reader as r  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "vf2_saves"
WHEN = datetime(2026, 10, 25, 12, 0, 0)
NAME_AT = r.gs_to_file(r.GS_NICKNAME)


def fixture(name: str) -> bytes:
    return gzip.decompress((FIX / name).read_bytes())


class NoGame:
    def find_game(self, save_folder_name):
        return []

    def suspend(self, pid, exe_name):
        raise AssertionError("no game is running")

    def resume(self, handle):
        pass


class Running(NoGame):
    def find_game(self, save_folder_name):
        return [(4242, save_folder_name + ".exe")]


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "Virtual Families 2 - Modded B202"
        self.folder.mkdir()
        self.settings = self.write(0, fixture("settings_slot0.ldw.gz"))
        self.save = self.write(1, fixture("one_generation_slot3.ldw.gz"))

    def write(self, number: int, data: bytes) -> Path:
        path = self.folder / r.save_file_name(number)
        path.write_bytes(data)
        return path

    def snapshot(self) -> dict:
        return {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob("*") if p.is_file()}

    def rename(self, name: str, slot: int = 1, processes=None):
        return rf.rename_family(self.folder, slot, name, processes=processes or NoGame(), now=WHEN)


class NameRuleTests(unittest.TestCase):
    def test_the_game_keeps_19_characters(self):
        self.assertIsNone(rf.name_problem("A" * 19))
        self.assertIn("at most 19", rf.name_problem("A" * 20))

    def test_refused_names(self):
        for name in ("", "   ", "Café", "Tab\there", "NEW PLAYER"):
            with self.subTest(name=name):
                self.assertIsNotNone(rf.name_problem(name))

    def test_accepted_names(self):
        for name in ("Lorsie", "The Smiths 2", "!@#$%^&*()_+-=", "new player", " Spaced "):
            with self.subTest(name=name):
                self.assertIsNone(rf.name_problem(name))

    def test_the_fields_hold_the_longest_name(self):
        self.assertGreaterEqual(rf.NAME_FIELD, rf.MAX_LENGTH + 1)
        self.assertGreaterEqual(rf.MENU_FIELD, rf.MAX_LENGTH + 1)


class ReadTests(Base):
    def test_slots_show_the_name_from_each_save(self):
        infos = rf.read_slots(self.folder)
        self.assertEqual(infos[0].label, "Family slot 1: Lorsieab2")
        self.assertIsNone(infos[0].problem)
        self.assertEqual(infos[1].label, "Family slot 2: (empty)")
        self.assertIsNotNone(infos[1].problem)

    def test_a_save_the_game_cannot_load_is_not_offered(self):
        self.write(5, fixture("legacy_header_slot5.ldw.gz"))
        info = rf.read_slots(self.folder)[4]
        self.assertIsNone(info.name)
        self.assertIn("cannot load", info.label)

    def test_the_real_settings_file_matches_the_slot_saves(self):
        settings = fixture("settings_slot0.ldw.gz")
        self.assertEqual(rf.menu_name(settings, 1), rf.save_name(fixture("one_generation_slot3.ldw.gz")))
        self.assertEqual(rf.menu_name(settings, 4), rf.EMPTY_SLOT_TEXT.encode())


class RenameTests(Base):
    def test_rename_writes_the_save_and_the_slot_menu_only(self):
        before = self.snapshot()
        result = self.rename("The Smiths")
        self.assertEqual((result.old_name, result.new_name), ("Lorsieab2", "The Smiths"))
        save = self.save.read_bytes()
        self.assertEqual(r.parse_family_save(save).nickname, "The Smiths")
        self.assertEqual(save[NAME_AT:NAME_AT + rf.NAME_FIELD], b"The Smiths" + b"\0" * 10)
        old = before[Path(self.save.name)]
        changed = {i for i in range(len(save)) if save[i] != old[i]}
        self.assertTrue(changed <= set(range(NAME_AT, NAME_AT + rf.NAME_FIELD)))
        settings = r.parse_settings(self.settings.read_bytes())
        self.assertEqual(settings.player_names, ("The Smiths", "test", "Lorsieab2", "NEW PLAYER", "NEW PLAYER"))
        old_settings = before[Path(self.settings.name)]
        new_settings = self.settings.read_bytes()
        first = rf.MENU_FIRST
        self.assertTrue({i for i in range(len(new_settings)) if new_settings[i] != old_settings[i]}
                        <= set(range(first, first + rf.MENU_FIELD)))
        self.assertEqual(result.changed, [self.save, self.settings])

    def test_backup_comes_first_and_is_labelled(self):
        before = self.snapshot()
        result = self.rename("The Smiths")
        backups = sb.list_backups(self.folder)
        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0].before_rename)
        self.assertIn("(before rename)", backups[0].label)
        self.assertEqual(result.backup.backup_folder, backups[0].path)
        for relative, data in before.items():
            self.assertEqual((backups[0].path / relative).read_bytes(), data)

    def test_the_previous_save_is_renamed_only_when_it_holds_the_old_name(self):
        older = self.write(21, fixture("ten_generations_slot4.ldw.gz"))          # also "Lorsieab2"
        result = self.rename("The Smiths")
        self.assertIn(older, result.changed)
        self.assertEqual(rf.save_name(older.read_bytes()), b"The Smiths")

    def test_a_previous_save_of_another_name_is_left_alone(self):
        other = bytearray(fixture("ten_generations_slot4.ldw.gz"))
        other[NAME_AT:NAME_AT + 6] = b"Other\0"
        older = self.write(21, bytes(other))
        result = self.rename("The Smiths")
        self.assertNotIn(older, result.changed)
        self.assertEqual(older.read_bytes(), bytes(other))

    def test_a_running_game_refuses_and_nothing_changes(self):
        before = self.snapshot()
        with self.assertRaises(rf.GameRunning) as caught:
            self.rename("The Smiths", processes=Running())
        self.assertIn("Close the game first", str(caught.exception))
        self.assertEqual(self.snapshot(), before)

    def test_a_bad_name_changes_nothing(self):
        before = self.snapshot()
        for name in ("A" * 20, "NEW PLAYER", "Lorsieab2"):
            with self.subTest(name=name), self.assertRaises(rf.RenameError):
                self.rename(name)
        self.assertEqual(self.snapshot(), before)

    def test_missing_or_unreadable_files_are_refused(self):
        with self.assertRaises(rf.RenameError):
            self.rename("The Smiths", slot=2)
        self.settings.unlink()
        before = self.snapshot()
        with self.assertRaises(rf.RenameError):
            self.rename("The Smiths")
        self.assertEqual(self.snapshot(), before)

    def test_a_failed_backup_changes_nothing(self):
        before = self.snapshot()
        with mock.patch.object(rf.save_backup, "copy_save_folder", side_effect=sb.BackupError("disk full")):
            with self.assertRaises(rf.RenameError) as caught:
                self.rename("The Smiths")
        self.assertIn("nothing was changed", str(caught.exception))
        self.assertEqual(self.snapshot(), before)

    def test_a_failed_write_puts_every_file_back(self):
        self.write(21, fixture("one_generation_slot3.ldw.gz"))
        files = {name: (self.folder / name).read_bytes()
                 for name in ("Virtual Families 21.ldw", "Virtual Families 221.ldw", "Virtual Families 20.ldw")}
        real = rf._write_atomically
        calls = []

        def flaky(path, data):
            calls.append(path)
            if len(calls) == 3:
                raise OSError("the disk went away")
            real(path, data)

        with mock.patch.object(rf, "_write_atomically", side_effect=flaky):
            with self.assertRaises(rf.RenameError) as caught:
                self.rename("The Smiths")
        self.assertIn("every file was put back", str(caught.exception))
        for name, data in files.items():
            self.assertEqual((self.folder / name).read_bytes(), data)

    def test_no_log_or_data_file_is_written(self):
        self.rename("The Smiths")
        outside_backups = {p for p in self.snapshot() if p.parts[0] != sb.BACKUPS_FOLDER}
        self.assertEqual(outside_backups, {Path("Virtual Families 20.ldw"), Path("Virtual Families 21.ldw")})


if __name__ == "__main__":
    unittest.main()
