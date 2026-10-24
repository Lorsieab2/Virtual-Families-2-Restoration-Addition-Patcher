#!/usr/bin/env python3
"""Back Up Saves / Restore Saves for Virtual Families 2 (src/vf2_save_backup.py).

Every test works on a temp copy built here: the player's real Documents\\LDW is never read or written.
"""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_save_backup as sb

FOLDER = "Virtual Families 2 - Modded B202"


class FakeProcesses:
    def __init__(self, running=0):
        self.running = running
        self.suspended = []
        self.resumed = []
        self.refuse = False
        self.fail_resume = False

    def find(self, exe_name):
        self.last_exe = exe_name
        return list(range(100, 100 + self.running))

    def suspend(self, pid, exe_name):
        if self.refuse:
            raise sb.PauseRefused(f"{exe_name} could not be paused")
        self.suspended.append(pid)
        return pid

    def resume(self, handle):
        if self.fail_resume:
            raise sb.BackupError("could not resume")
        self.resumed.append(handle)


class TempSaves(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.docs = Path(self._tmp.name) / "Documents"
        self.folder = self.docs / "LDW" / FOLDER
        self.folder.mkdir(parents=True)
        self.clock = datetime(2026, 10, 24, 12, 0, 0)

    def write(self, relative, data):
        path = self.folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def populate(self):
        self.write("Virtual Families 20.ldw", b"settings")
        self.write("Virtual Families 21.ldw", b"family one")
        self.write("Virtual Families 21 - Copy.ldw", b"family one copy")
        self.write("Virtual Families 25.ldw", b"family five")
        self.write("Virtual Families 225.ldw", b"family five previous")
        self.write("ldwLog.txt", b"log")
        self.write(Path(sb.DATA_FOLDER) / "Children" / "Virtual Families 25.ldw.dat", b"kids five")
        self.write(Path(sb.DATA_FOLDER) / "Children" / "Virtual Families 21.ldw.dat", b"kids one")

    def tick(self):
        self.clock += timedelta(seconds=5)
        return self.clock


class FindingFolders(TempSaves):
    def test_lists_vf2_folders_and_never_vf1(self):
        ldw = self.docs / "LDW"
        for name in ("Virtual Families 2", "Virtual Families", "Virtual Families - Modded", "Virtual Families 2 - Copy (5)",
                     "Virtual Villagers - A New Home", "Plant Tycoon"):
            (ldw / name).mkdir()
        names = [p.name for p in sb.find_save_folders(self.docs)]
        self.assertEqual(names, [FOLDER, "Virtual Families 2", "Virtual Families 2 - Copy (5)"])

    def test_modded_folders_are_the_ticked_ones(self):
        self.assertTrue(sb.is_patcher_save_folder(FOLDER))
        self.assertTrue(sb.is_patcher_save_folder("virtual families 2 - modded playtest"))
        self.assertFalse(sb.is_patcher_save_folder("Virtual Families 2"))
        self.assertFalse(sb.is_patcher_save_folder("Virtual Families 2 - Copy (5)"))

    def test_no_documents_or_no_ldw_is_an_empty_list(self):
        self.assertEqual(sb.find_save_folders(None), [])
        self.assertEqual(sb.find_save_folders(Path(self._tmp.name) / "nowhere"), [])

    def test_exe_name_is_the_folder_name(self):
        self.assertEqual(sb.game_exe_name(self.folder), FOLDER + ".exe")


class Backing(TempSaves):
    def test_backup_copies_saves_and_patcher_data_verified(self):
        self.populate()
        result = sb.back_up_save_folder(self.folder, FakeProcesses(), self.clock)
        self.assertEqual(result.file_count, 8)
        backup = result.backup_folder
        self.assertEqual(backup, self.folder / "Backups" / "Backup 2026-10-24 12-00-00")
        for relative in sb.files_to_back_up(self.folder):
            self.assertEqual((backup / relative).read_bytes(), (self.folder / relative).read_bytes())
        self.assertTrue((backup / sb.DATA_FOLDER / "Children" / "Virtual Families 25.ldw.dat").is_file())
        self.assertEqual(result.paused, 0)

    def test_backup_keeps_file_times(self):
        self.populate()
        before = (self.folder / "Virtual Families 21.ldw").stat().st_mtime_ns
        result = sb.back_up_save_folder(self.folder, FakeProcesses(), self.clock)
        after = (result.backup_folder / "Virtual Families 21.ldw").stat().st_mtime_ns
        self.assertLess(abs(after - before), 2_000_000_000)

    def test_a_backup_never_contains_the_backups_folder_or_overwrites_an_older_one(self):
        self.populate()
        first = sb.back_up_save_folder(self.folder, FakeProcesses(), self.clock)
        second = sb.back_up_save_folder(self.folder, FakeProcesses(), self.clock)   # the same second
        self.assertNotEqual(first.backup_folder, second.backup_folder)
        self.assertTrue(second.backup_folder.name.endswith("(2)"))
        self.assertEqual(second.file_count, 8)       # the first backup is not inside the second
        self.assertEqual(len(sb.list_backups(self.folder)), 2)

    def test_running_game_is_paused_then_resumed(self):
        self.populate()
        procs = FakeProcesses(running=2)
        result = sb.back_up_save_folder(self.folder, procs, self.clock)
        self.assertEqual(result.paused, 2)
        self.assertEqual(sorted(procs.resumed), sorted(procs.suspended))
        self.assertEqual(procs.last_exe, FOLDER + ".exe")

    def test_game_that_cannot_be_paused_is_never_copied(self):
        self.populate()
        procs = FakeProcesses(running=1)
        procs.refuse = True
        with self.assertRaises(sb.PauseRefused):
            sb.back_up_save_folder(self.folder, procs, self.clock)
        self.assertFalse((self.folder / "Backups").exists())

    def test_a_failed_resume_is_reported_but_the_backup_stands(self):
        self.populate()
        procs = FakeProcesses(running=1)
        procs.fail_resume = True
        result = sb.back_up_save_folder(self.folder, procs, self.clock)
        self.assertEqual(len(result.resume_problems), 1)
        self.assertEqual(len(sb.list_backups(self.folder)), 1)

    def test_empty_folder_is_refused(self):
        with self.assertRaises(sb.BackupError):
            sb.copy_save_folder(self.folder, self.clock)

    def test_incomplete_copy_is_set_aside_and_never_listed(self):
        self.populate()
        original = sb._copy_one

        def broken(source, destination):
            if source.name.endswith("25.ldw"):
                raise sb.BackupError("disk full")
            return original(source, destination)

        sb._copy_one = broken
        try:
            with self.assertRaises(sb.BackupError):
                sb.copy_save_folder(self.folder, self.clock)
        finally:
            sb._copy_one = original
        self.assertEqual(sb.list_backups(self.folder), [])
        self.assertTrue(any(p.name.endswith("INCOMPLETE") for p in (self.folder / "Backups").iterdir()))

    def test_list_is_newest_first_and_labels_before_restore(self):
        self.populate()
        a = sb.copy_save_folder(self.folder, self.clock)
        b = sb.copy_save_folder(self.folder, self.tick(), suffix=sb.BEFORE_RESTORE)
        listed = sb.list_backups(self.folder)
        self.assertEqual([i.path for i in listed], [b.backup_folder, a.backup_folder])
        self.assertTrue(listed[0].before_restore)
        self.assertIn("(before restore)", listed[0].label)
        self.assertEqual(listed[1].slots, [1, 5])


class Slots(unittest.TestCase):
    def test_slot_attribution(self):
        slot = lambda name: sb.file_slot(Path(name))
        self.assertEqual(slot("Virtual Families 25.ldw"), 5)
        self.assertEqual(slot("virtual families 25 - Copy.ldw"), 5)
        self.assertEqual(slot("Virtual Families 225.ldw"), 5)            # slot 5's previous save
        self.assertEqual(slot("Virtual Families 20.ldw"), "settings")
        self.assertEqual(slot("Virtual Families 2 Patcher Data/Children/Virtual Families 23.ldw.dat"), 3)
        self.assertIsNone(slot("Virtual Families 2 Patcher Data/Children/notes.txt"))
        self.assertEqual(sb.file_slot(Path("ldwLog.txt")), "engine log")
        self.assertIsNone(sb.file_slot(Path("sub/ldwLog.txt")))


class Restoring(TempSaves):
    def backup_then_change(self):
        self.populate()
        backup = sb.copy_save_folder(self.folder, self.clock).backup_folder
        self.write("Virtual Families 21.ldw", b"family one CHANGED")
        self.write("Virtual Families 25.ldw", b"family five CHANGED")
        self.write("Virtual Families 24.ldw", b"a family born after the backup")
        self.write("ldwLog.txt", b"newer log")
        return backup

    def test_plan_lists_exactly_the_changes(self):
        backup = self.backup_then_change()
        plan = sb.plan_restore(self.folder, backup)
        self.assertEqual({p.name for p in plan.replace}, {"Virtual Families 21.ldw", "Virtual Families 25.ldw"})
        self.assertEqual([p.name for p in plan.remove], ["Virtual Families 24.ldw"])
        self.assertEqual(plan.add, [])
        self.assertNotIn(Path("ldwLog.txt"), plan.replace + plan.remove)
        self.assertTrue(plan.changes)

    def test_planning_changes_nothing(self):
        backup = self.backup_then_change()
        before = {p: (self.folder / p).read_bytes() for p in sb.files_to_back_up(self.folder)}
        sb.plan_restore(self.folder, backup)
        sb.plan_restore(self.folder, backup, 5)
        after = {p: (self.folder / p).read_bytes() for p in sb.files_to_back_up(self.folder)}
        self.assertEqual(before, after)

    def test_whole_restore_backs_up_what_it_replaces_first(self):
        backup = self.backup_then_change()
        result = sb.restore_backup(self.folder, backup, None, FakeProcesses(), self.tick())
        self.assertEqual((self.folder / "Virtual Families 21.ldw").read_bytes(), b"family one")
        self.assertFalse((self.folder / "Virtual Families 24.ldw").exists())
        self.assertEqual((self.folder / "ldwLog.txt").read_bytes(), b"newer log")
        saved = result.before_restore.backup_folder
        self.assertTrue(saved.name.endswith("(before restore)"))
        self.assertEqual((saved / "Virtual Families 21.ldw").read_bytes(), b"family one CHANGED")
        self.assertEqual((saved / "Virtual Families 24.ldw").read_bytes(), b"a family born after the backup")
        self.assertEqual((backup / "Virtual Families 21.ldw").read_bytes(), b"family one")   # the backup is untouched

    def test_a_restore_can_be_undone_from_the_before_restore_backup(self):
        backup = self.backup_then_change()
        changed = {p: (self.folder / p).read_bytes() for p in sb.files_to_back_up(self.folder)}
        result = sb.restore_backup(self.folder, backup, None, FakeProcesses(), self.tick())
        sb.restore_backup(self.folder, result.before_restore.backup_folder, None, FakeProcesses(), self.tick())
        self.assertEqual(changed, {p: (self.folder / p).read_bytes() for p in sb.files_to_back_up(self.folder)})

    def test_one_slot_restore_touches_only_that_family(self):
        backup = self.backup_then_change()
        sb.restore_backup(self.folder, backup, 5, FakeProcesses(), self.tick())
        self.assertEqual((self.folder / "Virtual Families 25.ldw").read_bytes(), b"family five")
        self.assertEqual((self.folder / "Virtual Families 21.ldw").read_bytes(), b"family one CHANGED")
        self.assertEqual((self.folder / "Virtual Families 24.ldw").read_bytes(), b"a family born after the backup")

    def test_one_slot_plan_includes_that_slots_sidecar_and_previous_save(self):
        self.populate()
        backup = sb.copy_save_folder(self.folder, self.clock).backup_folder
        self.write(Path(sb.DATA_FOLDER) / "Children" / "Virtual Families 25.ldw.dat", b"kids five CHANGED")
        self.write("Virtual Families 225.ldw", b"previous CHANGED")
        plan = sb.plan_restore(self.folder, backup, 5)
        self.assertEqual({p.name for p in plan.replace}, {"Virtual Families 25.ldw.dat", "Virtual Families 225.ldw"})

    def test_a_slot_the_backup_lacks_is_refused(self):
        backup = self.backup_then_change()
        with self.assertRaises(sb.RestoreRefused):
            sb.plan_restore(self.folder, backup, 3)

    def test_nothing_to_restore_changes_nothing_and_makes_no_extra_backup(self):
        self.populate()
        backup = sb.copy_save_folder(self.folder, self.clock).backup_folder
        result = sb.restore_backup(self.folder, backup, None, FakeProcesses(), self.tick())
        self.assertIsNone(result.before_restore)
        self.assertEqual(len(sb.list_backups(self.folder)), 1)

    def test_a_running_game_blocks_the_restore_before_anything_changes(self):
        backup = self.backup_then_change()
        with self.assertRaises(sb.RestoreRefused):
            sb.restore_backup(self.folder, backup, None, FakeProcesses(running=1), self.tick())
        self.assertEqual((self.folder / "Virtual Families 21.ldw").read_bytes(), b"family one CHANGED")
        self.assertEqual(len(sb.list_backups(self.folder)), 1)      # no before-restore backup either

    def test_a_failure_part_way_puts_every_file_back(self):
        backup = self.backup_then_change()
        changed = {p: (self.folder / p).read_bytes() for p in sb.files_to_back_up(self.folder)}
        original = sb._place
        calls = []

        def flaky(source, target):
            calls.append(target.name)
            if len(calls) == 2 and source.is_relative_to(backup):
                raise sb.BackupError("simulated disk error")
            return original(source, target)

        sb._place = flaky
        try:
            with self.assertRaises(sb.BackupError) as caught:
                sb.restore_backup(self.folder, backup, None, FakeProcesses(), self.tick())
        finally:
            sb._place = original
        self.assertIn("nothing changed", str(caught.exception))
        self.assertEqual(changed, {p: (self.folder / p).read_bytes() for p in sb.files_to_back_up(self.folder)})

    def test_only_this_folders_backups_can_be_restored_or_deleted(self):
        self.populate()
        other = self.docs / "LDW" / "Virtual Families 2"
        other.mkdir()
        (other / "Virtual Families 21.ldw").write_bytes(b"x")
        foreign = sb.copy_save_folder(other, self.clock).backup_folder
        with self.assertRaises(sb.RestoreRefused):
            sb.plan_restore(self.folder, foreign)
        with self.assertRaises(sb.RestoreRefused):
            sb.delete_backup(self.folder, foreign)
        with self.assertRaises(sb.RestoreRefused):
            sb.plan_restore(self.folder, self.folder)

    def test_delete_removes_one_backup_only(self):
        self.populate()
        a = sb.copy_save_folder(self.folder, self.clock).backup_folder
        b = sb.copy_save_folder(self.folder, self.tick()).backup_folder
        sb.delete_backup(self.folder, a)
        self.assertEqual([i.path for i in sb.list_backups(self.folder)], [b])
        self.assertTrue((self.folder / "Virtual Families 21.ldw").is_file())


if __name__ == "__main__":
    unittest.main()
