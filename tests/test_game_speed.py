#!/usr/bin/env python3
"""Game Speed (src/vf2_game_speed.py): sets a family's saved speed to Paused or Normal, in a closed game's saves.

Every save here is a temp copy of a real save fixture (tests/fixtures/vf2_saves). No owner save is ever opened.
"""
from __future__ import annotations

import gzip
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
import vf2_save_reader as r  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "vf2_saves"
WHEN = datetime(2026, 10, 25, 12, 0, 0)
PAUSED = "one_generation_slot3.ldw.gz"       # option 1009, clock 0 / 10
PAUSED_2 = "ten_generations_slot4.ldw.gz"
NORMAL = "pending_birth_slot1.ldw.gz"        # option 10, clock 10 / 0


def fixture(name: str) -> bytes:
    return gzip.decompress((FIX / name).read_bytes())


def unix_after(data: bytes, seconds: int) -> int:
    return r.parse_header(data).start_time + gs.read_state(data).saved_at + seconds


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


class RunsAfterBackup(NoGame):
    calls = 0

    def find_game(self, save_folder_name):
        RunsAfterBackup.calls += 1
        return [] if RunsAfterBackup.calls == 1 else [(7, save_folder_name + ".exe")]


class ValueTests(unittest.TestCase):
    def test_the_fixtures_read_as_the_game_stores_them(self):
        self.assertEqual(gs.read_state(fixture(PAUSED)).label, "Paused")
        self.assertEqual(gs.read_state(fixture(PAUSED_2)).label, "Paused")
        self.assertEqual(gs.read_state(fixture(NORMAL)).label, "Normal")
        self.assertIsNone(gs.read_state(fixture("legacy_header_slot5.ldw.gz")))
        self.assertIsNone(gs.read_state(fixture("settings_slot0.ldw.gz")))

    def test_pause_writes_what_the_games_pause_writes(self):
        data = fixture(NORMAL)
        before = gs.read_state(data)
        out = gs.changed_bytes(data, gs.PAUSED)
        after = gs.read_state(out)
        self.assertEqual((after.clock_speed, after.clock_previous, after.option), (0, 10, 1009))
        self.assertEqual((after.changed_at, after.saved_at), (before.saved_at, before.saved_at))
        self.assertEqual(after.banked, before.banked + before.saved_at - before.changed_at)
        self.assertEqual(r.parse_family_save(out).clock.game_seconds_at_save,
                         r.parse_family_save(data).clock.game_seconds_at_save)        # the clock does not jump
        changed = [i for i in range(len(data)) if data[i] != out[i]]
        self.assertTrue(changed)
        self.assertTrue(all(gs.CLOCK_AT <= i < gs.CLOCK_AT + 0x14 or gs.OPTION_AT <= i < gs.OPTION_AT + 4
                            for i in changed))

    def test_unpause_writes_what_the_games_unpause_writes_now(self):
        for name in (PAUSED, PAUSED_2):
            with self.subTest(name=name):
                data = fixture(name)
                before = gs.read_state(data)
                out = gs.changed_bytes(data, gs.NORMAL_NAME, unix_after(data, 2 * 86400))
                after = gs.read_state(out)
                now = before.saved_at + 2 * 86400
                self.assertEqual((after.clock_speed, after.clock_previous, after.option), (10, 0, 10))
                self.assertEqual(after.banked, before.banked)
                self.assertEqual((after.changed_at, after.saved_at), (now, now))
                touched = 0
                for k in range(r.VILLAGER_SLOTS):
                    rec = gs.VILLAGERS_AT + k * r.VILLAGER_RECORD_SIZE
                    old = struct.unpack_from("<II", data, rec + gs.REC_BANKED)
                    new = struct.unpack_from("<II", out, rec + gs.REC_BANKED)
                    health, = struct.unpack_from("<i", data, rec + gs.REC_HEALTH)
                    if data[rec] and not data[rec + 1] and health > 0 and old[1]:
                        self.assertEqual(new, (0, now), k)
                        touched += 1
                    else:
                        self.assertEqual(new, old, k)
                self.assertGreater(touched, 0)
                self.assertTrue(gs.only_speed_fields_differ(data, out))

    def test_refusals(self):
        with self.assertRaisesRegex(gs.SpeedError, "already paused"):
            gs.changed_bytes(fixture(PAUSED), gs.PAUSED)
        with self.assertRaisesRegex(gs.SpeedError, "already at Normal"):
            gs.changed_bytes(fixture(NORMAL), gs.NORMAL_NAME)
        data = fixture(PAUSED)
        with self.assertRaisesRegex(gs.SpeedError, "clock is earlier"):
            gs.changed_bytes(data, gs.NORMAL_NAME, unix_after(data, -5))
        other = bytearray(fixture(NORMAL))
        struct.pack_into("<i", other, gs.OPTION_AT, 20)
        self.assertEqual(gs.read_state(bytes(other)).kind, "other")
        with self.assertRaisesRegex(gs.SpeedError, "other"):
            gs.changed_bytes(bytes(other), gs.PAUSED)

    def test_a_pause_the_two_games_would_work_out_differently_is_refused(self):
        exact = gs.SpeedState(10, 10, 0, 0, 100, (1 << 24) + 2)     # a whole float: both games agree
        self.assertEqual(gs.seconds_at(exact, exact.saved_at), 100 + (1 << 24) + 2)
        with self.assertRaisesRegex(gs.SpeedError, "194 days"):
            gs.seconds_at(gs.SpeedState(10, 10, 0, 0, 100, (1 << 24) + 1), (1 << 24) + 1)

    def test_a_time_controls_speed_is_named_in_words_and_never_offered(self):
        # Time Controls saves every family at 10 / 1009 and loads any other value as 10 / 1009, so none is a target.
        self.assertEqual(gs.TARGETS, ("Paused", "Normal"))
        for value, name in ((20, "Slow"), (5, "Fast"), (2, "5x"), (1, "10x")):
            with self.subTest(value=value):
                data = bytearray(fixture(NORMAL))
                struct.pack_into("<i", data, gs.OPTION_AT, value)
                struct.pack_into("<i", data, gs.CLOCK_AT, value)
                state = gs.read_state(bytes(data))
                self.assertTrue(state.time_controls)
                self.assertEqual((state.kind, state.label), ("other", f"{name} (a Time Controls speed)"))
                self.assertNotIn(name, gs.TARGETS)
                for target in gs.TARGETS:
                    with self.assertRaisesRegex(gs.SpeedError, "Time Controls speed"):
                        gs.changed_bytes(bytes(data), target, unix_after(bytes(data), 60))
                struct.pack_into("<i", data, gs.CLOCK_AT, 10)      # option and clock disagree: raw, as before
                self.assertEqual(gs.read_state(bytes(data)).label, f"other (speed value {value}, clock speed 10)")

    def test_paused_from_a_time_controls_speed_is_paused_and_unpauses_to_normal(self):
        # 999 + speed with a stopped clock: a game with Time Controls loads it as 1009, so its unpause gives Normal.
        for value in (20, 5, 2, 1):
            with self.subTest(value=value):
                data = bytearray(fixture(PAUSED))
                struct.pack_into("<i", data, gs.OPTION_AT, 999 + value)
                struct.pack_into("<i", data, gs.CLOCK_AT + 4, value)
                self.assertEqual(gs.read_state(bytes(data)).label, "Paused")
                out = gs.read_state(gs.changed_bytes(bytes(data), gs.NORMAL_NAME, unix_after(bytes(data), 60)))
                self.assertEqual((out.option, out.clock_speed, out.clock_previous), (10, 10, 0))

    def test_a_round_trip_through_every_offered_speed_has_no_clock_jump(self):
        data = fixture(NORMAL)
        paused = gs.changed_bytes(data, gs.PAUSED)
        normal = gs.changed_bytes(paused, gs.NORMAL_NAME, unix_after(paused, 0))
        again = gs.changed_bytes(normal, gs.PAUSED)
        seconds = r.parse_family_save(data).clock.game_seconds_at_save
        for out, label in ((paused, "Paused"), (normal, "Normal"), (again, "Paused")):
            self.assertEqual(gs.read_state(out).label, label)
            self.assertEqual(r.parse_family_save(out).clock.game_seconds_at_save, seconds)
            self.assertTrue(gs.only_speed_fields_differ(data, out))

    def test_a_dead_body_the_pause_would_have_removed_is_refused(self):
        data = bytearray(fixture(PAUSED))
        rec = gs.VILLAGERS_AT + 29 * r.VILLAGER_RECORD_SIZE
        data[rec], data[rec + 1] = 1, 0
        struct.pack_into("<I", data, rec + gs.REC_STAMP, gs.read_state(bytes(data)).saved_at)
        struct.pack_into("<i", data, rec + gs.REC_HEALTH, 0)
        limit = 240 * 60 * 1009
        gs.changed_bytes(bytes(data), gs.NORMAL_NAME, unix_after(bytes(data), limit - 1))
        with self.assertRaisesRegex(gs.SpeedError, "taken away"):
            gs.changed_bytes(bytes(data), gs.NORMAL_NAME, unix_after(bytes(data), limit))


class WriteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "Virtual Families 2 - Modded B202"
        self.folder.mkdir()
        (self.folder / r.save_file_name(0)).write_bytes(fixture("settings_slot0.ldw.gz"))
        (self.folder / r.save_file_name(1)).write_bytes(fixture(PAUSED))
        (self.folder / r.save_file_name(2)).write_bytes(fixture(NORMAL))
        (self.folder / r.save_file_name(21)).write_bytes(fixture(PAUSED))

    def snapshot(self) -> dict:
        return {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob("*")
                if p.is_file() and sb.BACKUPS_FOLDER not in p.relative_to(self.folder).parts}

    def test_listing_shows_each_speed(self):
        slots = {s.slot: s for s in gs.read_slots(self.folder)}
        self.assertTrue(slots[1].label.endswith("- Paused"))
        self.assertTrue(slots[2].label.endswith("- Normal"))
        self.assertEqual(slots[3].label, "Family slot 3: (empty)")

    def test_listing_names_a_time_controls_speed_and_says_why_it_is_not_changed(self):
        data = bytearray(fixture(NORMAL))
        struct.pack_into("<i", data, gs.OPTION_AT, 2)
        struct.pack_into("<i", data, gs.CLOCK_AT, 2)
        (self.folder / r.save_file_name(3)).write_bytes(bytes(data))
        info = {s.slot: s for s in gs.read_slots(self.folder)}[3]
        self.assertTrue(info.label.endswith("- 5x (a Time Controls speed)"))
        self.assertIn("loads this family at Normal", info.problem)
        with self.assertRaises(gs.SpeedError):
            gs.set_speed(self.folder, 3, "5x", NoGame(), WHEN)

    def test_set_speed_backs_up_writes_only_the_slot_save_and_reads_it_back(self):
        before = self.snapshot()
        data = before[Path(r.save_file_name(1))]
        result = gs.set_speed(self.folder, 1, gs.NORMAL_NAME, NoGame(), WHEN, unix_after(data, 60))
        after = self.snapshot()
        self.assertEqual((result.before, result.after), ("Paused", "Normal"))
        self.assertEqual({k for k in after if after[k] != before.get(k)}, {Path(r.save_file_name(1))})
        backups = sb.list_backups(self.folder)
        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0].before_speed_change)
        self.assertIn("(before speed change)", backups[0].label)
        self.assertEqual((backups[0].path / r.save_file_name(1)).read_bytes(), data)
        self.assertFalse(list(self.folder.glob("*.speed-tmp")))
        self.assertEqual(gs.set_speed(self.folder, 2, gs.PAUSED, NoGame(), WHEN).after, "Paused")

    def test_a_running_game_changes_nothing(self):
        before = self.snapshot()
        with self.assertRaisesRegex(gs.GameRunning, "Close the game first"):
            gs.set_speed(self.folder, 1, gs.NORMAL_NAME, Running(), WHEN)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.folder / sb.BACKUPS_FOLDER).exists())
        RunsAfterBackup.calls = 0
        with self.assertRaises(gs.GameRunning):
            gs.set_speed(self.folder, 2, gs.PAUSED, RunsAfterBackup(), WHEN)
        self.assertEqual(self.snapshot(), before)

    def test_a_failed_read_back_puts_the_save_back(self):
        before = self.snapshot()
        real = gs.read_state
        calls = {"n": 0}

        def flaky(data):
            calls["n"] += 1
            return real(data) if calls["n"] < 3 else None

        with mock.patch.object(gs, "read_state", flaky):
            with self.assertRaisesRegex(gs.SpeedError, "put back as it was"):
                gs.set_speed(self.folder, 2, gs.PAUSED, NoGame(), WHEN)
        self.assertEqual(self.snapshot(), before)

    def test_missing_and_unloadable_slots_are_refused(self):
        with self.assertRaisesRegex(gs.SpeedError, "no family"):
            gs.set_speed(self.folder, 3, gs.PAUSED, NoGame(), WHEN)
        (self.folder / r.save_file_name(5)).write_bytes(fixture("legacy_header_slot5.ldw.gz"))
        with self.assertRaisesRegex(gs.SpeedError, "save the game can load"):
            gs.set_speed(self.folder, 5, gs.PAUSED, NoGame(), WHEN)
        with self.assertRaises(gs.SpeedError):
            gs.set_speed(self.folder, 1, "Fast", NoGame(), WHEN)


if __name__ == "__main__":
    unittest.main()
