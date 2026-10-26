#!/usr/bin/env python3
"""Back Up Saves sets the backup's family saves to Paused (ported from the Virtual Villagers Fun Patcher's
tests/test_backup_paused_speed.py): a restored backup must never catch up on the real time since it was made.

Only the copy changes, never the live save. The pause is Game Speed's own (src/vf2_game_speed.py), which writes
exactly what the game's Pause writes. Only a family's own save at Normal is paused; every other file (another
speed, an unreadable save, the previous save N+20, the settings) is copied byte for byte. Every save here is a temp
copy of a real save fixture (tests/fixtures/vf2_saves). No owner save is ever opened.
"""
from __future__ import annotations

import gzip
import os
import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_game_speed as gs  # noqa: E402
import vf2_save_backup as sb  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "vf2_saves"
PAUSED = "one_generation_slot3.ldw.gz"       # option 1009, clock 0 / 10
NORMAL = "pending_birth_slot1.ldw.gz"        # option 10, clock 10 / 0
LEGACY = "legacy_header_slot5.ldw.gz"        # a save the game cannot load
SETTINGS = "settings_slot0.ldw.gz"
OLD_TIME = 1_600_000_000_000_000_000         # a fixed modification time in ns, kept on every copy


def fixture(name: str) -> bytes:
    return gzip.decompress((FIX / name).read_bytes())


def at_speed(option: int, clock: int) -> bytes:
    data = bytearray(fixture(NORMAL))
    struct.pack_into("<i", data, gs.OPTION_AT, option)
    struct.pack_into("<i", data, gs.CLOCK_AT, clock)
    return bytes(data)


def played_on(data: bytes) -> bytes:
    """The same family saved again later, still at Normal (one clock stamp moved on)."""
    out = bytearray(data)
    saved_at = struct.unpack_from("<I", out, gs.CLOCK_AT + 0x10)[0]
    struct.pack_into("<I", out, gs.CLOCK_AT + 0x10, saved_at + 60)
    return bytes(out)


class NoGame:
    def find_game(self, save_folder_name):
        return []

    def suspend(self, pid, exe_name):
        raise AssertionError("no game is running")

    def resume(self, handle):
        pass


def tree(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*")
            if p.is_file() and sb.BACKUPS_FOLDER not in p.relative_to(folder).parts}


class PauseBytesTests(unittest.TestCase):
    def test_pausing_is_game_speeds_own_pause(self):
        before = fixture(NORMAL)
        after = sb.pause_save_bytes(before)
        self.assertEqual(after, gs.changed_bytes(before, gs.PAUSED))
        self.assertEqual(gs.read_state(after).label, "Paused")
        self.assertTrue(gs.only_speed_fields_differ(before, after))

    def test_only_a_family_at_normal_is_paused(self):
        self.assertIsNone(sb.pause_save_bytes(fixture(PAUSED)))
        for data in (at_speed(5, 5), at_speed(20, 20), at_speed(10, 0), fixture(LEGACY), fixture(SETTINGS), b""):
            with self.assertRaises(sb.NotPaused):
                sb.pause_save_bytes(data)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "Documents" / "LDW" / "Virtual Families 2 - Modded B203"
        self.folder.mkdir(parents=True)
        f = self.folder
        (f / "Virtual Families 21.ldw").write_bytes(fixture(NORMAL))
        (f / "Virtual Families 22.ldw").write_bytes(played_on(fixture(NORMAL)))
        (f / "Virtual Families 23.ldw").write_bytes(fixture(PAUSED))              # already paused
        (f / "Virtual Families 24.ldw").write_bytes(at_speed(5, 5))               # another speed
        (f / "Virtual Families 25.ldw").write_bytes(fixture(LEGACY))              # cannot be loaded
        (f / "Virtual Families 221.ldw").write_bytes(fixture(NORMAL))             # slot 1's previous save
        (f / "Virtual Families 20.ldw").write_bytes(fixture(SETTINGS))
        (f / "ldwLog.txt").write_text("log", encoding="utf-8")
        sidecar = f / sb.DATA_FOLDER / "Children" / "Virtual Families 21.ldw.dat"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_bytes(b"children")
        for path in f.rglob("*"):
            if path.is_file():
                os.utime(path, ns=(OLD_TIME, OLD_TIME))

    def test_a_backup_holds_paused_saves_and_the_originals_are_untouched(self):
        originals = tree(self.folder)
        made = sb.copy_save_folder(self.folder, datetime(2026, 10, 26, 12, 0, 0))
        self.assertEqual(tree(self.folder), originals)                       # the live save folder never changes
        copy = made.backup_folder
        for name in ("Virtual Families 21.ldw", "Virtual Families 22.ldw"):
            self.assertEqual(gs.read_state((copy / name).read_bytes()).label, "Paused")
        for name in ("Virtual Families 23.ldw", "Virtual Families 24.ldw", "Virtual Families 25.ldw",
                     "Virtual Families 221.ldw", "Virtual Families 20.ldw", "ldwLog.txt",
                     f"{sb.DATA_FOLDER}/Children/Virtual Families 21.ldw.dat"):
            self.assertEqual((copy / name).read_bytes(), originals[name], name)     # left byte for byte
        self.assertEqual(sorted(made.paused_slots), ["Virtual Families 21.ldw", "Virtual Families 22.ldw"])
        self.assertEqual([n for n, _why in made.not_paused], ["Virtual Families 24.ldw", "Virtual Families 25.ldw"])
        recorded = {f.relative.as_posix(): f for f in made.files}
        for name in ("Virtual Families 21.ldw", "Virtual Families 22.ldw"):
            self.assertEqual((recorded[name].size, recorded[name].sha256), sb._hash_file(copy / name))
            self.assertEqual((copy / name).stat().st_mtime_ns, OLD_TIME)            # the copy keeps the save's time
        self.assertEqual(sb.list_backups(self.folder)[0].slots, [1, 2, 3, 4, 5])
        self.assertEqual(list(self.folder.rglob("*.vf2-pause-tmp")), [])

    def test_the_live_save_is_untouched_by_back_up_saves(self):
        originals = tree(self.folder)
        made = sb.back_up_save_folder(self.folder, NoGame(), datetime(2026, 10, 26, 12, 0, 0))
        self.assertEqual(tree(self.folder), originals)
        self.assertEqual(gs.read_state((self.folder / "Virtual Families 21.ldw").read_bytes()).label, "Normal")
        self.assertEqual(gs.read_state((made.backup_folder / "Virtual Families 21.ldw").read_bytes()).label, "Paused")

    def test_a_backup_with_no_family_saves_is_an_exact_copy(self):
        folder = Path(self.tmp.name) / "Virtual Families 2"
        folder.mkdir()
        (folder / "Virtual Families 20.ldw").write_bytes(fixture(SETTINGS))
        (folder / "ldwLog.txt").write_text("log", encoding="utf-8")
        made = sb.copy_save_folder(folder, datetime(2026, 10, 26, 12, 0, 0))
        self.assertEqual((made.paused_slots, made.not_paused), ([], []))
        self.assertEqual(tree(made.backup_folder), tree(folder))

    def test_a_restore_restores_paused_and_a_failed_one_puts_back_every_byte(self):
        made = sb.copy_save_folder(self.folder, datetime(2026, 10, 26, 12, 0, 0))
        for name in ("Virtual Families 21.ldw", "Virtual Families 22.ldw"):     # played on since, still Normal
            path = self.folder / name
            path.write_bytes(played_on(path.read_bytes()))
        now = tree(self.folder)

        real_place = sb._place
        calls = []

        def failing(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError("disk full")
            return real_place(source, target)

        with mock.patch.object(sb, "_place", side_effect=failing):
            with self.assertRaises(sb.BackupError) as caught:
                sb.restore_backup(self.folder, made.backup_folder, None, NoGame(), datetime(2026, 10, 26, 13, 0, 0))
        self.assertIn("Every file was put back as it was", str(caught.exception))
        self.assertEqual(tree(self.folder), now)                              # exactly as before, not paused

        sb.restore_backup(self.folder, made.backup_folder, None, NoGame(), datetime(2026, 10, 26, 14, 0, 0))
        for name in ("Virtual Families 21.ldw", "Virtual Families 22.ldw"):
            self.assertEqual(gs.read_state((self.folder / name).read_bytes()).label, "Paused")
        self.assertEqual((self.folder / "Virtual Families 24.ldw").read_bytes(), at_speed(5, 5))   # other speeds alone

    def test_a_one_slot_restore_brings_back_a_paused_family(self):
        made = sb.copy_save_folder(self.folder, datetime(2026, 10, 26, 12, 0, 0))
        changed = played_on(fixture(NORMAL))
        (self.folder / "Virtual Families 21.ldw").write_bytes(changed)
        result = sb.restore_backup(self.folder, made.backup_folder, 1, NoGame(), datetime(2026, 10, 26, 13, 0, 0))
        self.assertEqual(gs.read_state((self.folder / "Virtual Families 21.ldw").read_bytes()).label, "Paused")
        self.assertEqual(gs.read_state((self.folder / "Virtual Families 22.ldw").read_bytes()).label, "Normal")
        before = result.before_restore.backup_folder / "Virtual Families 21.ldw"
        self.assertEqual(before.read_bytes(), gs.changed_bytes(changed, gs.PAUSED))


if __name__ == "__main__":
    unittest.main()
