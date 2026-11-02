#!/usr/bin/env python3
"""Copy Player Slot (src/vf2_copy_slot.py): copies a family, with every file kept for it, into an empty save slot.

Every save here is a temp copy of a real save fixture (tests/fixtures/vf2_saves) in a fake save folder; the sidecars
are made in their DLLs' formats. No owner save is ever opened.
"""
from __future__ import annotations

import gzip
import json
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
import vf2_copy_slot as cs  # noqa: E402
import vf2_genealogy as gen  # noqa: E402
import vf2_rename_family as rf  # noqa: E402
import vf2_save_backup as sb  # noqa: E402
import vf2_save_reader as r  # noqa: E402
import vf2_tree_memory as tm  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "vf2_saves"
WHEN = datetime(2026, 10, 31, 12, 0, 0)
PATCHER = "Virtual Families 2 Patcher"
DATA = "Virtual Families 2 Patcher Data"


def fixture(name: str) -> bytes:
    return gzip.decompress((FIX / name).read_bytes())


def outfits_sidecar(save: bytes, pictures=(5, -1, -1, -1, -1, -1, -1, -1, -1)) -> bytes:
    """An outfit pictures sidecar in b200outfits.cpp's format (WriteSidecar): 188 bytes."""
    out = bytearray(cs.OUTFITS_SIZE)
    out[:8] = b"VF2OUTFT"
    struct.pack_into("<I", out, 8, 1)
    out[12:20] = b"VF2B200\0"
    struct.pack_into("<I", out, 20, cs.OUTFITS_SIZE)
    struct.pack_into("<QI", out, 24, cs.fnv1a64(save), len(save))
    for k in range(9):
        struct.pack_into("<II", out, 36 + k * 8, 0xA0 + k, 1)          # the tray's places
    for k in range(9):
        struct.pack_into("<i", out, 144 + k * 4, pictures[k])
    struct.pack_into("<Q", out, 180, cs.fnv1a64(bytes(out[:180])))
    return bytes(out)


def kids_sidecar(save: bytes) -> bytes:
    return gen.make_children_sidecar(save, 1, 0, 0, [gen.ExtraChild(9, 1, "alive", 2, 3, 40, "Seventh")])


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
    """Settings (slots 1-3 in use, 4 and 5 empty), Save 1 with its previous save and every per-slot file, and Save 2
    (another family) with its own."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "Virtual Families 2 - Modded B205"
        self.folder.mkdir()
        self.write(0, fixture("settings_slot0.ldw.gz"))
        self.save = self.write(1, fixture("one_generation_slot3.ldw.gz"))
        self.previous = self.write(21, fixture("ten_generations_slot4.ldw.gz"))      # also "Lorsieab2"
        self.other = self.write(2, fixture("pending_birth_slot1.ldw.gz"))
        save, previous = self.save.read_bytes(), self.previous.read_bytes()
        self.put(f"{DATA}/Children/Virtual Families 21.ldw.dat", kids_sidecar(save))
        self.put(f"{DATA}/Children/Virtual Families 221.ldw.dat", kids_sidecar(previous))
        self.put(f"{DATA}/Outfits/Virtual Families 21.ldw.dat", outfits_sidecar(save))
        self.put(f"{DATA}/Outfits/Virtual Families 221.ldw.dat", outfits_sidecar(previous, (7,) + (-1,) * 8))
        self.put(f"{DATA}/Children/Virtual Families 22.ldw.dat", kids_sidecar(self.other.read_bytes()))
        self.put(f"{DATA}/Outfits/Virtual Families 22.ldw.dat", outfits_sidecar(self.other.read_bytes()))
        logs = f"{PATCHER}/Save 1/Logs/Family History"
        self.put(f"{logs}/Family History 1.txt",
                 b"Family: Lorsieab2 (Save 1)\r\n[2026-10-01 10:00:00] Birth 1\r\n  Name: Bob\r\n\r\n")
        self.put(f"{logs}/Family History 2.txt",
                 b"Family: Lorsieab2 (Save 1)\r\n[2026-10-02 10:00:00] Family Renamed 1\r\n  Old name: A\r\n"
                 b"  New name: Lorsieab2\r\n\r\n")
        tree = {"format": tm.FORMAT, "game": 2, "slot": 1, "family": "Lorsieab2", "members": {"list": [], "next": 1}}
        self.put(f"{PATCHER}/Save 1/Data/Family Tree/Virtual Families 2 Family Tree - Save 1.tree",
                 json.dumps(tree, indent=1).encode())
        self.put(f"{PATCHER}/Save 1/Data/Family Tree/Virtual Families 2 Family Tree Edits - Save 1.json",
                 b'{"format": 1, "title": "My family"}')
        self.put(f"{PATCHER}/Save 1/Family Tree/Virtual Families 2 Family Tree - Save 1.png", b"\x89PNG picture")
        self.put(f"{PATCHER}/Save 2/Logs/Family History/Family History 1.txt", b"Family: test (Save 2)\r\n")
        self.put("ldwLog.txt", b"engine log")

    def write(self, number: int, data: bytes) -> Path:
        path = self.folder / r.save_file_name(number)
        path.write_bytes(data)
        return path

    def put(self, relative: str, data: bytes) -> Path:
        path = self.folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def snapshot(self, backups: bool = False) -> dict:
        return {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob("*")
                if p.is_file() and (backups or p.relative_to(self.folder).parts[0] != "Backups")}

    def folders(self) -> set:
        return {p.relative_to(self.folder) for p in self.folder.rglob("*")
                if p.is_dir() and p.relative_to(self.folder).parts[0] != "Backups"}

    def copy(self, name: str = "The Copies", source: int = 1, target: int = 4, processes=None, replace: bool = False):
        return cs.copy_slot(self.folder, source, target, name, processes=processes or NoGame(), now=WHEN,
                            replace=replace)


class SidecarFormatTests(unittest.TestCase):
    def test_fnv_matches_the_family_tree_makers(self):
        data = fixture("one_generation_slot3.ldw.gz")
        self.assertEqual(cs.fnv1a64(data), gen.fnv1a64(data))

    def test_the_children_format_is_the_dlls(self):
        save = fixture("one_generation_slot3.ldw.gz")
        side = kids_sidecar(save)
        self.assertEqual(cs.read_sidecar("Children", side), cs.Sidecar(gen.fnv1a64(save), len(save)))
        for bad in (side[:-1], side.replace(b"VF2KIDS", b"VF1KIDS"), side[:-8] + bytes(8), b""):
            self.assertIsNone(cs.read_sidecar("Children", bad))

    def test_the_outfits_format_is_the_dlls(self):
        save = fixture("one_generation_slot3.ldw.gz")
        side = outfits_sidecar(save)
        self.assertEqual(len(side), 188)
        self.assertEqual(cs.read_sidecar("Outfits", side), cs.Sidecar(cs.fnv1a64(save), len(save)))
        for bad in (side + b"x", side[:100], side[:-8] + bytes(8), b"VF2OUTFT"):
            self.assertIsNone(cs.read_sidecar("Outfits", bad))

    def test_rekeying_changes_only_the_save_fields_and_the_checksum(self):
        save, other = fixture("one_generation_slot3.ldw.gz"), fixture("ten_generations_slot4.ldw.gz")
        for kind, side in (("Children", kids_sidecar(save)), ("Outfits", outfits_sidecar(save))):
            with self.subTest(kind=kind):
                again = cs.rekeyed(side, other)
                self.assertEqual(cs.read_sidecar(kind, again), cs.Sidecar(cs.fnv1a64(other), len(other)))
                self.assertEqual(again[:24], side[:24])
                self.assertEqual(again[36:-8], side[36:-8])
                self.assertEqual(cs.rekeyed(side, save), side)
        kids = gen.read_children_sidecar(cs.rekeyed(kids_sidecar(save), other))
        self.assertEqual((kids.save_hash, kids.save_size), (gen.fnv1a64(other), len(other)))
        self.assertEqual(kids.children[0].name, "Seventh")


class CopyTests(Base):
    def test_a_full_copy_with_every_per_slot_file(self):
        before = self.snapshot()
        result = self.copy()
        after = self.snapshot()
        new = {path for path in after if path not in before}
        self.assertEqual(new, {
            Path("Virtual Families 24.ldw"), Path("Virtual Families 224.ldw"),
            Path(DATA, "Children", "Virtual Families 24.ldw.dat"), Path(DATA, "Children", "Virtual Families 224.ldw.dat"),
            Path(DATA, "Outfits", "Virtual Families 24.ldw.dat"), Path(DATA, "Outfits", "Virtual Families 224.ldw.dat"),
            Path(PATCHER, "Save 4", "Logs", "Family History", "Family History 1.txt"),
            Path(PATCHER, "Save 4", "Logs", "Family History", "Family History 2.txt"),
            Path(PATCHER, "Save 4", "Data", "Family Tree", "Virtual Families 2 Family Tree - Save 4.tree"),
            Path(PATCHER, "Save 4", "Data", "Family Tree", "Virtual Families 2 Family Tree Edits - Save 4.json"),
        })
        # The Family Tree Maker's picture is made again from the save; it is not copied.
        self.assertFalse((self.folder / PATCHER / "Save 4" / "Family Tree").exists())
        self.assertEqual((result.old_name, result.new_name, result.source, result.target),
                         ("Lorsieab2", "The Copies", 1, 4))
        self.assertEqual(result.skipped, [])
        # The saves parse exactly as the originals but for the name.
        copy = (self.folder / "Virtual Families 24.ldw").read_bytes()
        self.assertTrue(cs.same_but_name(before[Path("Virtual Families 21.ldw")], copy, "The Copies"))
        self.assertEqual(r.parse_family_save(copy).nickname, "The Copies")
        older = (self.folder / "Virtual Families 224.ldw").read_bytes()
        self.assertTrue(cs.same_but_name(before[Path("Virtual Families 221.ldw")], older, "The Copies"))
        # Every sidecar describes its copied save, byte for byte as the DLL checks it.
        for kind in ("Children", "Outfits"):
            for number, save in ((4, copy), (24, older)):
                side = (self.folder / DATA / kind / f"Virtual Families 2{number}.ldw.dat").read_bytes()
                self.assertEqual(cs.read_sidecar(kind, side), cs.Sidecar(cs.fnv1a64(save), len(save)))
                original = before[Path(DATA, kind, f"Virtual Families 2{number - 3}.ldw.dat")]
                self.assertEqual(side[36:-8], original[36:-8])
        # The Family Tree Maker shows the copy's children 7 to 28 (it needs the exact save).
        village = gen.load_village(self.folder, slot=4)
        self.assertTrue(any(p.name == "Seventh" for p in village.people.values()))
        # The log and the tree file say Save 4; the newest log file notes the new name.
        logs = self.folder / PATCHER / "Save 4" / "Logs" / "Family History"
        first = (logs / "Family History 1.txt").read_bytes()
        self.assertEqual(first, b"Family: Lorsieab2 (Save 4)\r\n[2026-10-01 10:00:00] Birth 1\r\n  Name: Bob\r\n\r\n")
        second = (logs / "Family History 2.txt").read_bytes().decode("latin-1")
        self.assertTrue(second.startswith("Family: Lorsieab2 (Save 4)\r\n"))
        self.assertTrue(second.endswith("[2026-10-31 12:00:00] Family Renamed 2\r\n  Old name: Lorsieab2\r\n"
                                        "  New name: The Copies\r\n  Copied from: Save 1\r\n\r\n"))
        tree = tm.read_tree_file(tm.tree_file(self.folder, 4))
        self.assertEqual((tree["slot"], tree["family"]), (4, "The Copies"))
        self.assertEqual(tree["members"], {"list": [], "next": 1})

    def test_the_new_name_is_in_the_slot_list_and_inside_the_save(self):
        before = self.snapshot()
        self.copy("Smiths Two")
        settings = r.parse_settings((self.folder / "Virtual Families 20.ldw").read_bytes())
        self.assertEqual(settings.player_names, ("Lorsieab2", "test", "Lorsieab2", "Smiths Two", "NEW PLAYER"))
        self.assertEqual(settings.slot_in_use, (True, True, True, True, False))
        old, new = before[Path("Virtual Families 20.ldw")], (self.folder / "Virtual Families 20.ldw").read_bytes()
        entry = range(rf.MENU_FIRST + 3 * rf.MENU_FIELD, rf.MENU_FIRST + 4 * rf.MENU_FIELD)
        self.assertEqual({i for i in range(len(new)) if new[i] != old[i]} - set(entry), {cs.FLAG_FIRST + 3})
        self.assertEqual(r.read_family_save(self.folder / "Virtual Families 24.ldw").nickname, "Smiths Two")
        self.assertEqual([s.label for s in rf.read_slots(self.folder)][3], "Save 4: Smiths Two")

    def test_the_settings_agree_with_the_games_own_rebuild_at_start(self):
        """theGameState::Load() loads each slot's save at every start: one that loads gives the slot its player name
        and a set flag, one that does not clears the flag. After the copy the settings already say that for the
        copied slot, and the copy changed no other slot's entry."""
        before = r.parse_settings((self.folder / "Virtual Families 20.ldw").read_bytes())
        self.copy("Smiths Two")
        settings = r.parse_settings((self.folder / "Virtual Families 20.ldw").read_bytes())
        copied = r.read_family_save(self.folder / "Virtual Families 24.ldw")
        self.assertTrue(settings.slot_in_use[3])
        self.assertEqual(settings.player_names[3], copied.nickname)
        for k in (0, 1, 2, 4):
            self.assertEqual((settings.player_names[k], settings.slot_in_use[k]),
                             (before.player_names[k], before.slot_in_use[k]))
        # The only per-slot fields of the 0x90-byte block: the five entries at +0x10 and the five flags at +0x79.
        per_slot = {rf.MENU_FIRST + rf.MENU_FIELD * k + i for k in range(5) for i in range(rf.MENU_FIELD)}
        per_slot |= {cs.FLAG_FIRST + k for k in range(5)}
        base = r.HEADER_SIZE
        self.assertEqual(per_slot, set(range(base + 0x10, base + 0x10 + 5 * 0x15)) | set(range(base + 0x79, base + 0x7E)))

    def test_the_same_name_is_allowed_and_adds_no_rename_record(self):
        self.copy("Lorsieab2")
        logs = self.folder / PATCHER / "Save 4" / "Logs" / "Family History"
        self.assertNotIn(b"Copied from", (logs / "Family History 2.txt").read_bytes())
        self.assertEqual((self.folder / "Virtual Families 24.ldw").read_bytes(), self.save.read_bytes())

    def test_other_slots_and_shared_files_are_untouched(self):
        before = self.snapshot()
        self.copy()
        after = self.snapshot()
        for path, data in before.items():
            if path != Path("Virtual Families 20.ldw"):
                self.assertEqual(after[path], data, path)

    def test_the_backup_is_made_first(self):
        before = self.snapshot()
        seen = []
        real = cs._write_new

        def spy(path, data):
            seen.append(sb.list_backups(self.folder))
            return real(path, data)

        with mock.patch.object(cs, "_write_new", spy):
            result = self.copy()
        self.assertTrue(seen and all(len(backups) == 1 and backups[0].before_copy for backups in seen))
        backups = sb.list_backups(self.folder)
        self.assertEqual(len(backups), 1)
        self.assertIn("(before copy)", backups[0].label)
        self.assertEqual(result.backup.backup_folder, backups[0].path)
        for relative, data in before.items():
            if relative.name.endswith(".ldw") and r.classify_save_file(relative.name) and relative.parts == (relative.name,) \
                    and sb.is_slot_save(relative):
                continue                                   # the backup's family saves are set to Paused
            if relative in result.backup.rematched_sidecars:
                # ... and a sidecar that matched such a save is re-keyed to its paused copy (as it was, kept aside)
                self.assertEqual(result.backup.unpaused_bytes[relative], data, relative)
                continue
            self.assertEqual((backups[0].path / relative).read_bytes(), data, relative)

    def test_every_file_goes_through_a_temporary_file(self):
        moves = []
        real_rename, real_replace = os.rename, os.replace

        def rename(a, b):
            moves.append((Path(a), Path(b)))
            return real_rename(a, b)

        def replace(a, b):
            moves.append((Path(a), Path(b)))
            return real_replace(a, b)

        with mock.patch.object(cs.os, "rename", rename), mock.patch.object(cs.os, "replace", replace), \
                mock.patch.object(rf.os, "replace", replace):
            result = self.copy()
        into = {b: a for a, b in moves}
        for entry in result.files:
            self.assertIn(entry.path, into)
            self.assertTrue(into[entry.path].name.endswith(".tmp"), into[entry.path])
            self.assertEqual(into[entry.path].parent, entry.path.parent)
        settings = self.folder / "Virtual Families 20.ldw"
        self.assertTrue(into[settings].name.endswith(".tmp"))
        self.assertEqual(list(self.folder.rglob("*.tmp")), [])


class RefusalTests(Base):
    def assert_nothing_changed(self, before):
        self.assertEqual(self.snapshot(backups=True), before)

    def test_a_used_target_is_refused_unless_replacing(self):
        before = self.snapshot(backups=True)
        with self.assertRaisesRegex(cs.CopyError, "in use"):
            self.copy(target=2)                       # a save is there, and replace was not given
        self.write(5, b"anything at all")
        before = self.snapshot(backups=True)
        with self.assertRaisesRegex(cs.CopyError, "in use"):
            self.copy(target=5)
        self.assert_nothing_changed(before)
        for replace in (False, True):
            with self.assertRaisesRegex(cs.CopyError, "other than"):
                cs.copy_slot(self.folder, 1, 1, "The Copies", processes=NoGame(), now=WHEN, replace=replace)
        self.assert_nothing_changed(before)

    def test_refused_while_the_game_runs(self):
        before = self.snapshot(backups=True)
        with self.assertRaises(cs.GameRunning) as caught:
            self.copy(processes=Running())
        self.assertIn("Close the game first", str(caught.exception))
        self.assert_nothing_changed(before)

    def test_a_game_started_during_the_backup_stops_the_copy(self):
        class StartsLater(NoGame):
            calls = 0

            def find_game(self, save_folder_name):
                StartsLater.calls += 1
                return [] if StartsLater.calls == 1 else [(1, save_folder_name + ".exe")]

        before = self.snapshot()
        with self.assertRaises(cs.GameRunning):
            self.copy(processes=StartsLater())
        self.assertEqual(self.snapshot(), before)

    def test_bad_names_and_unreadable_saves_are_refused(self):
        before = self.snapshot(backups=True)
        # "Café" was refused under the old printable-ASCII rule; it is a name now (the shared text rule,
        # vf2_game_text). A control character and a name over the field's 19 bytes are still refused.
        for name in ("", "A" * 20, "NEW PLAYER", "Tab\there", "日本語の名前はとても長いです"):
            with self.subTest(name=name), self.assertRaises(cs.CopyError):
                self.copy(name)
        with self.assertRaisesRegex(cs.CopyError, "no family"):
            self.copy(source=5)
        self.assert_nothing_changed(before)


class FailureTests(Base):
    def assert_put_back(self, before, folders):
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.folders(), folders)
        self.assertEqual(list(self.folder.rglob("*.tmp")), [])

    def test_a_failure_part_way_leaves_nothing_half_copied(self):
        before, folders = self.snapshot(), self.folders()
        count = len(cs.plan_copy(self.folder, 1, 4, "The Copies", WHEN).files)
        for fail_at in range(1, count + 1):
            with self.subTest(fail_at=fail_at):
                real = cs._write_new
                calls = []

                def flaky(path, data):
                    calls.append(path)
                    if len(calls) == fail_at:
                        raise OSError("the disk is full")
                    return real(path, data)

                with mock.patch.object(cs, "_write_new", flaky), self.assertRaisesRegex(cs.CopyError, "put back"):
                    self.copy()
                self.assert_put_back(before, folders)

    def test_a_failed_settings_write_puts_everything_back(self):
        before, folders = self.snapshot(), self.folders()
        with mock.patch.object(rf, "_write_atomically", side_effect=OSError("locked")), \
                self.assertRaisesRegex(cs.CopyError, "put back"):
            self.copy()
        self.assert_put_back(before, folders)

    def test_a_copy_that_does_not_read_back_is_undone(self):
        before, folders = self.snapshot(), self.folders()
        with mock.patch.object(cs, "same_but_name", return_value=False), \
                self.assertRaisesRegex(cs.CopyError, "does not read back"):
            self.copy()
        self.assert_put_back(before, folders)


class LeftoverTests(Base):
    def setUp(self):
        super().setUp()
        self.stale = self.write(24, b"a deleted family's previous save")
        self.stale_kids = self.put(f"{DATA}/Children/Virtual Families 24.ldw.dat", b"old kids")
        self.stale_log = self.put(f"{PATCHER}/Save 4/Logs/Family History/Family History 1.txt",
                                  b"Family: Gone (Save 4)\r\n")

    def test_a_deleted_familys_files_go_into_the_replaced_by_copy_folder(self):
        unreadable = self.put(f"{DATA}/Outfits/Virtual Families 24.ldw.unreadable-1.dat", b"set aside by the DLL")
        before = self.snapshot()
        result = self.copy()
        aside = self.folder / "Backups" / "Replaced by copy 2026-10-31 12-00-00 - Save 4 - (no name)"
        self.assertEqual(result.aside_folder, aside)
        self.assertFalse(result.replaced)
        for path in (self.stale, self.stale_kids, self.stale_log, unreadable):
            relative = path.relative_to(self.folder)
            self.assertEqual((aside / relative).read_bytes(), before[relative], relative)
        self.assertFalse(unreadable.exists())               # nothing of the old family stays beside the copy
        self.assertNotIn(b"Gone", (self.folder / PATCHER / "Save 4" / "Logs" / "Family History" /
                                   "Family History 1.txt").read_bytes())
        # Nothing reads it: no file of it is left in the save folder proper, and it is never a restorable backup.
        self.assertFalse(any("Replaced by copy" in str(p) for p in self.snapshot()))
        self.assertEqual([b.path.name for b in sb.list_backups(self.folder)],
                         ["Backup 2026-10-31 12-00-00 (before copy)"])
        self.assertNotIn("Backups", [p.relative_to(self.folder).parts[0]
                                     for p in self.folder.rglob("*") if p.is_file()
                                     and sb.file_slot(p.relative_to(self.folder)) is not None])

    def test_a_failure_puts_the_set_aside_files_back(self):
        before, folders = self.snapshot(), self.folders()
        with mock.patch.object(rf, "_write_atomically", side_effect=OSError("locked")), \
                self.assertRaises(cs.CopyError):
            self.copy()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.folders(), folders)


class EmptySlotTests(Base):
    """The owner, 2026-11-01: "the game sees (game name)1-5.ldw as player slots". The fixture's settings mark Save 3
    in use (a stale entry) but there is no "Virtual Families 23.ldw"."""

    def test_a_slot_with_no_save_is_empty_whatever_the_settings_say(self):
        settings = r.parse_settings((self.folder / "Virtual Families 20.ldw").read_bytes())
        self.assertTrue(settings.slot_in_use[2])
        self.assertTrue(cs.slot_is_empty(self.folder, 3))
        self.assertIsNone(cs.target_problem(self.folder, 3))
        self.assertEqual(cs.read_slots(self.folder)[2].label, "Save 3: (empty)")
        result = self.copy("Third Copy", target=3)
        self.assertFalse(result.replaced)
        after = r.parse_settings((self.folder / "Virtual Families 20.ldw").read_bytes())
        self.assertEqual((after.player_names[2], after.slot_in_use[2]), ("Third Copy", True))
        self.assertEqual(r.read_family_save(self.folder / "Virtual Families 23.ldw").nickname, "Third Copy")

    def test_a_save_the_settings_call_new_player_is_a_player(self):
        raw = bytearray((self.folder / "Virtual Families 20.ldw").read_bytes())
        raw[cs.FLAG_FIRST + 1] = 0                     # Save 2 has a save, but the list says unused
        (self.folder / "Virtual Families 20.ldw").write_bytes(bytes(raw))
        info = cs.read_slots(self.folder)[1]
        self.assertTrue(info.used)
        self.assertIsNone(info.problem)                # it can be copied from
        self.assertIsNotNone(cs.target_problem(self.folder, 2))   # and is not offered as empty
        result = cs.copy_slot(self.folder, 2, 5, "From Two", processes=NoGame(), now=WHEN)
        self.assertEqual(result.target, 5)

    def test_the_empty_prompt_uses_the_shared_words(self):
        text = cs.confirmation_text(self.folder, 1, b"Lorsieab2", 4, "The Copies", WHEN)
        self.assertEqual(text, f"Save 4 is empty. It will get a copy of Lorsieab2 (Save 1), named The Copies. The whole "
                               f"save folder ({self.folder}) is backed up first. Copy it?")


class ReplaceTests(Base):
    """The owner, 2026-11-01: "able to overwrite existing slots (with a confirmation prompt of course)"."""

    def setUp(self):
        super().setUp()
        self.old_previous = self.write(222, fixture("one_generation_slot3.ldw.gz"))
        self.put(f"{DATA}/Children/Virtual Families 222.ldw.dat", kids_sidecar(self.old_previous.read_bytes()))
        self.put(f"{DATA}/Children/Virtual Families 22.ldw.unreadable-1.dat", b"set aside by the DLL")
        self.put(f"{PATCHER}/Save 2/Data/Family Tree/Virtual Families 2 Family Tree - Save 2.tree", b"{}")

    def test_the_replace_prompt_uses_the_shared_words(self):
        old = rf.shown(rf.save_name(self.other.read_bytes()))
        text = cs.confirmation_text(self.folder, 1, b"Lorsieab2", 2, "The Copies", WHEN)
        self.assertEqual(text, f"Save 2 holds the {old} family. It will be replaced by a copy of Lorsieab2 (Save 1), "
                               f"named The Copies. The whole save folder ({self.folder}) is backed up first, and "
                               f"{old}'s files are kept in Backups\\Replaced by copy 2026-10-31 12-00-00 - Save 2 - "
                               f"{old}. Replace it?")

    def test_a_used_slot_is_replaced_and_its_files_kept(self):
        old = rf.shown(rf.save_name(self.other.read_bytes()))
        before = self.snapshot()
        result = self.copy("The Copies", target=2, replace=True)
        self.assertTrue(result.replaced)
        aside = self.folder / "Backups" / f"Replaced by copy 2026-10-31 12-00-00 - Save 2 - {old}"
        self.assertEqual(result.aside_folder, aside)
        after = self.snapshot()
        mine = [p for p in before if sb.file_slot(p) == 2 or p.name.startswith("Virtual Families 22.ldw.unreadable")]
        self.assertGreaterEqual(len(mine), 7)
        for relative in mine:
            self.assertEqual((aside / relative).read_bytes(), before[relative], relative)     # kept, never deleted
        # The backup holds the old family too.
        backup = result.backup.backup_folder
        kept = result.backup.unpaused_bytes.get(Path("Virtual Families 22.ldw"),     # (the backup's copy is Paused)
                                                (backup / "Virtual Families 22.ldw").read_bytes())
        self.assertEqual(kept, before[Path("Virtual Families 22.ldw")])
        # The slot is now the copy, with nothing of the old family attached.
        copy = (self.folder / "Virtual Families 22.ldw").read_bytes()
        self.assertTrue(cs.same_but_name(before[Path("Virtual Families 21.ldw")], copy, "The Copies"))
        for kind in ("Children", "Outfits"):
            side = (self.folder / DATA / kind / "Virtual Families 22.ldw.dat").read_bytes()
            self.assertEqual(cs.read_sidecar(kind, side), cs.Sidecar(cs.fnv1a64(copy), len(copy)))
        self.assertFalse((self.folder / DATA / "Children" / "Virtual Families 22.ldw.unreadable-1.dat").exists())
        logs = self.folder / PATCHER / "Save 2" / "Logs" / "Family History"
        self.assertEqual(sorted(p.name for p in logs.iterdir()), ["Family History 1.txt", "Family History 2.txt"])
        self.assertTrue((logs / "Family History 1.txt").read_bytes().startswith(b"Family: Lorsieab2 (Save 2)"))
        settings = r.parse_settings((self.folder / "Virtual Families 20.ldw").read_bytes())
        self.assertEqual((settings.player_names[1], settings.slot_in_use[1]), ("The Copies", True))
        # No other slot changed.
        for relative, data in before.items():
            owner = sb.file_slot(relative)
            if owner in (1, 3, 4, 5):
                self.assertEqual(after.get(relative), data, relative)

    def test_a_failed_replace_puts_the_old_family_back(self):
        before, folders = self.snapshot(), self.folders()
        with mock.patch.object(rf, "_write_atomically", side_effect=OSError("locked")), \
                self.assertRaisesRegex(cs.CopyError, "put back"):
            self.copy("The Copies", target=2, replace=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.folders(), folders)
        self.assertEqual([p.name for p in (self.folder / "Backups").iterdir()],
                         ["Backup 2026-10-31 12-00-00 (before copy)"])


class SidecarCaseTests(Base):
    def test_a_damaged_sidecar_is_not_copied(self):
        self.put(f"{DATA}/Outfits/Virtual Families 21.ldw.dat", b"VF2OUTFT damaged")
        result = self.copy()
        self.assertFalse((self.folder / DATA / "Outfits" / "Virtual Families 24.ldw.dat").exists())
        self.assertEqual([path.name for path, _why in result.skipped], ["Virtual Families 21.ldw.dat"])

    def test_a_sidecar_for_another_save_is_copied_unchanged(self):
        other = kids_sidecar(fixture("legacy_header_slot5.ldw.gz"))
        self.put(f"{DATA}/Children/Virtual Families 21.ldw.dat", other)
        result = self.copy()
        self.assertEqual((self.folder / DATA / "Children" / "Virtual Families 24.ldw.dat").read_bytes(), other)
        self.assertTrue(any("copied unchanged" in note for note in result.notes))

    def test_a_previous_save_of_another_name_is_copied_byte_for_byte(self):
        older = bytearray(self.previous.read_bytes())
        at = r.gs_to_file(r.GS_NICKNAME)
        older[at:at + 20] = b"Earlier\0" + bytes(12)
        self.previous.write_bytes(bytes(older))
        self.put(f"{DATA}/Children/Virtual Families 221.ldw.dat", kids_sidecar(bytes(older)))
        self.copy()
        self.assertEqual((self.folder / "Virtual Families 224.ldw").read_bytes(), bytes(older))
        self.assertEqual((self.folder / DATA / "Children" / "Virtual Families 224.ldw.dat").read_bytes(),
                         kids_sidecar(bytes(older)))

    def test_a_family_with_no_patcher_files_copies_its_save_alone(self):
        for path in sorted(self.folder.rglob("*"), reverse=True):
            if path.is_file() and path.suffix != ".ldw" and path.name != "ldwLog.txt" or \
                    path.is_file() and path.name == "Virtual Families 221.ldw":
                path.unlink()
        result = self.copy()
        self.assertEqual([entry.path.name for entry in result.files], ["Virtual Families 24.ldw"])


class BackupLabelTests(unittest.TestCase):
    def test_before_copy_backups_are_listed_with_their_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Backups" / "Backup 2026-10-31 12-00-00 (before copy)").mkdir(parents=True)
            info = sb.list_backups(folder)[0]
            self.assertTrue(info.before_copy)
            self.assertEqual(info.label, "2026-10-31 12:00:00 (before copy)")


if __name__ == "__main__":
    unittest.main()
