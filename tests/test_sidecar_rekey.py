#!/usr/bin/env python3
"""The Children and Outfits sidecars stay matched to their saves after every tool that rewrites a save.

b200kids takes the extra children (7 to 28) from a Children file only when it names the FNV-1a 64 hash and size of
the loaded save (runtime/native/b200kids/b200kids.cpp AfterLoad); otherwise it keeps only those still at home and
drops those who left or died. b200outfits binds its file the same way. Rename Family, Game Speed and Back Up Saves'
Paused copies change a save's bytes, so each re-keys the slot's sidecars that described the save before the change,
exactly as Copy Player Slot re-keys a copy's (vf2_copy_slot.sidecar_rekeys). One-slot Restore Saves takes the slot's
Outfits files, its N+20 sidecars and its "Virtual Families 2 Patcher\\Save N" folder with it.

Every save here is a temp copy of a real save fixture (tests/fixtures/vf2_saves) in a fake save folder; the sidecars
are made in their DLLs' formats. No owner save is ever opened.
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
import vf2_copy_slot as cs  # noqa: E402
import vf2_game_speed as gs  # noqa: E402
import vf2_genealogy as gen  # noqa: E402
import vf2_rename_family as rf  # noqa: E402
import vf2_save_backup as sb  # noqa: E402
import vf2_save_reader as r  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "vf2_saves"
WHEN = datetime(2026, 10, 31, 12, 0, 0)
LATER = datetime(2026, 10, 31, 13, 0, 0)
PATCHER = "Virtual Families 2 Patcher"
DATA = "Virtual Families 2 Patcher Data"
PAUSED = "one_generation_slot3.ldw.gz"        # option 1009, clock 0 / 10; "Lorsieab2"
PAUSED_2 = "ten_generations_slot4.ldw.gz"     # also "Lorsieab2"
NORMAL = "pending_birth_slot1.ldw.gz"         # option 10, clock 10 / 0
KIDS = [gen.ExtraChild(10 + k, k % 2, state, 1, 1, 20, f"Kid{7 + k}")
        for k, state in enumerate(["alive", "alive", "gone", "dead", "gone", "alive"])]
EVERYONE = sorted(k.name for k in KIDS)
AT_HOME = sorted(k.name for k in KIDS if k.state == "alive")


def fixture(name: str) -> bytes:
    return gzip.decompress((FIX / name).read_bytes())


def kids_sidecar(save: bytes) -> bytes:
    return gen.make_children_sidecar(save, 1, 0, 0, KIDS)


def outfits_sidecar(save: bytes) -> bytes:
    """An outfit pictures sidecar in b200outfits.cpp's format (WriteSidecar): 188 bytes."""
    out = bytearray(cs.OUTFITS_SIZE)
    out[:8] = b"VF2OUTFT"
    struct.pack_into("<I", out, 8, 1)
    out[12:20] = b"VF2B200\0"
    struct.pack_into("<I", out, 20, cs.OUTFITS_SIZE)
    struct.pack_into("<QI", out, 24, cs.fnv1a64(save), len(save))
    for k in range(9):
        struct.pack_into("<II", out, 36 + k * 8, 0xA0 + k, 1)
        struct.pack_into("<i", out, 144 + k * 4, 5 if k == 0 else -1)
    struct.pack_into("<Q", out, 180, cs.fnv1a64(bytes(out[:180])))
    return bytes(out)


def unix_after(data: bytes, seconds: int) -> int:
    start = gs._start_time(data)
    return start + gs.read_state(data).saved_at + seconds


class NoGame:
    def find_game(self, save_folder_name):
        return []

    def suspend(self, pid, exe_name):
        raise AssertionError("no game is running")

    def resume(self, handle):
        pass


def simulated_load(folder: Path, slot: int) -> list[str]:
    """The extra children b200kids keeps when the game loads ``slot`` (AfterLoad, the family being the same): every
    one when the slot's Children file (or the N+20 one, for a restored backup) names the save's hash and size;
    otherwise only those still at home."""
    save = (folder / r.save_file_name(slot)).read_bytes()
    found = []
    for number in (slot, slot + r.PREVIOUS_SAVE_OFFSET):
        path = cs.sidecar_path(folder, "Children", number)
        found.append(gen.read_children_sidecar(path.read_bytes()) if path.is_file() else None)
    for file in found:
        if file is not None and file.save_hash == gen.fnv1a64(save) and file.save_size == len(save):
            return sorted(k.name for k in file.children)
    if found[0] is not None:
        return sorted(k.name for k in found[0].children if k.state == "alive")
    return []


class Base(unittest.TestCase):
    """Settings; Save 1 (paused) with its previous save 21; Save 2 (normal, another family); a Children and an
    Outfits file for each, each describing its own save."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "Virtual Families 2 - Modded B205"
        self.folder.mkdir()
        self.write(0, fixture("settings_slot0.ldw.gz"))
        self.write(1, fixture(PAUSED))
        self.write(21, fixture(PAUSED_2))
        self.write(2, fixture(NORMAL))
        for number in (1, 21, 2):
            save = (self.folder / r.save_file_name(number)).read_bytes()
            self.sidecar("Children", number).write_bytes(kids_sidecar(save))
            self.sidecar("Outfits", number).write_bytes(outfits_sidecar(save))

    def write(self, number: int, data: bytes) -> Path:
        path = self.folder / r.save_file_name(number)
        path.write_bytes(data)
        return path

    def sidecar(self, kind: str, number: int, folder: Path | None = None) -> Path:
        path = cs.sidecar_path(folder or self.folder, kind, number)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put(self, relative: str, data: bytes) -> Path:
        path = self.folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def matches(self, kind: str, number: int, folder: Path | None = None) -> bool:
        folder = folder or self.folder
        return cs.sidecar_describes(kind, cs.sidecar_path(folder, kind, number).read_bytes(),
                                    (folder / r.save_file_name(number)).read_bytes())

    def snapshot(self) -> dict:
        return {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob("*")
                if p.is_file() and p.relative_to(self.folder).parts[0] != sb.BACKUPS_FOLDER}

    def rel(self, kind: str, number: int) -> Path:
        return cs.sidecar_path(Path(), kind, number)


class TheBug(Base):
    def test_a_stale_children_file_drops_the_children_who_left_or_died(self):
        self.assertEqual(simulated_load(self.folder, 2), EVERYONE)
        path = self.folder / r.save_file_name(2)
        path.write_bytes(gs.changed_bytes(path.read_bytes(), gs.PAUSED))     # the save changed, its file did not
        self.assertEqual(simulated_load(self.folder, 2), AT_HOME)
        self.assertNotEqual(AT_HOME, EVERYONE)


class RenameTests(Base):
    def test_rename_rekeys_the_slots_children_and_outfits_files(self):
        before = self.snapshot()
        result = rf.rename_family(self.folder, 1, "Newname", processes=NoGame(), now=WHEN)
        after = self.snapshot()
        self.assertEqual(sorted(p.name for p in result.rematched),
                         ["Virtual Families 21.ldw.dat", "Virtual Families 21.ldw.dat",
                          "Virtual Families 221.ldw.dat", "Virtual Families 221.ldw.dat"])
        for kind in cs.SIDECAR_FOLDERS:
            for number in (1, 21):
                self.assertTrue(self.matches(kind, number), (kind, number))
                key = self.rel(kind, number)
                self.assertEqual(after[key][:24], before[key][:24])
                self.assertEqual(after[key][36:-8], before[key][36:-8])     # only the hash, size and checksum
            self.assertEqual(after[self.rel(kind, 2)], before[self.rel(kind, 2)])  # another slot: untouched
        self.assertEqual(simulated_load(self.folder, 1), EVERYONE)
        self.assertEqual(len(result.changed), 3)                           # the saves 1 and 21 and the settings

    def test_rename_leaves_a_sidecar_that_did_not_match(self):
        foreign = kids_sidecar(b"another save")
        self.sidecar("Children", 1).write_bytes(foreign)
        damaged = self.sidecar("Outfits", 21)
        damaged.write_bytes(damaged.read_bytes()[:-1] + b"\0")
        damaged_bytes = damaged.read_bytes()
        result = rf.rename_family(self.folder, 1, "Newname", processes=NoGame(), now=WHEN)
        self.assertEqual(self.sidecar("Children", 1).read_bytes(), foreign)
        self.assertEqual(damaged.read_bytes(), damaged_bytes)
        self.assertEqual(sorted(str(p.relative_to(self.folder)) for p in result.rematched),
                         sorted(str(self.rel(k, n)) for k, n in (("Outfits", 1), ("Children", 21))))

    def test_a_failed_rename_puts_every_file_back(self):
        before = self.snapshot()
        with mock.patch.object(rf, "sidecar_matches", return_value=False):
            with self.assertRaisesRegex(rf.RenameError, "put back"):
                rf.rename_family(self.folder, 1, "Newname", processes=NoGame(), now=WHEN)
        self.assertEqual(self.snapshot(), before)


class SpeedTests(Base):
    def test_game_speed_rekeys_the_slots_files_both_ways(self):
        for slot, target in ((1, gs.NORMAL_NAME), (2, gs.PAUSED)):
            with self.subTest(slot=slot, target=target):
                before = self.snapshot()
                save = before[Path(r.save_file_name(slot))]
                result = gs.set_speed(self.folder, slot, target, NoGame(), WHEN, unix_after(save, 60))
                self.assertEqual(sorted(str(p.relative_to(self.folder)) for p in result.rematched),
                                 sorted(str(self.rel(k, slot)) for k in cs.SIDECAR_FOLDERS))
                after = self.snapshot()
                self.assertEqual({k for k in after if after[k] != before.get(k)},
                                 {Path(r.save_file_name(slot))} | {self.rel(k, slot) for k in cs.SIDECAR_FOLDERS})
                for kind in cs.SIDECAR_FOLDERS:
                    self.assertTrue(self.matches(kind, slot))
                self.assertEqual(simulated_load(self.folder, slot), EVERYONE)

    def test_game_speed_leaves_a_sidecar_that_did_not_match(self):
        foreign = outfits_sidecar(b"another save")
        self.sidecar("Outfits", 2).write_bytes(foreign)
        result = gs.set_speed(self.folder, 2, gs.PAUSED, NoGame(), WHEN)
        self.assertEqual(self.sidecar("Outfits", 2).read_bytes(), foreign)
        self.assertEqual([p.name for p in result.rematched], ["Virtual Families 22.ldw.dat"])
        self.assertEqual(result.rematched[0].parent.name, "Children")

    def test_a_failed_speed_change_puts_the_save_and_sidecars_back(self):
        before = self.snapshot()
        with mock.patch.object(rf, "sidecar_matches", return_value=False):
            with self.assertRaisesRegex(gs.SpeedError, "put back"):
                gs.set_speed(self.folder, 2, gs.PAUSED, NoGame(), WHEN)
        self.assertEqual(self.snapshot(), before)


class BackupTests(Base):
    def test_the_backups_sidecars_match_its_paused_copy_and_the_live_ones_are_untouched(self):
        before = self.snapshot()
        result = sb.back_up_save_folder(self.folder, NoGame(), WHEN)
        backup = result.backup_folder
        self.assertEqual(result.paused_slots, [r.save_file_name(2)])     # slot 1 was already paused
        self.assertEqual(sorted(map(str, result.rematched_sidecars)),
                         sorted(str(self.rel(k, 2)) for k in cs.SIDECAR_FOLDERS))
        for kind in cs.SIDECAR_FOLDERS:
            for number in (1, 21, 2):
                self.assertTrue(self.matches(kind, number, backup), (kind, number))
        self.assertEqual(simulated_load(backup, 2), EVERYONE)
        self.assertEqual(self.snapshot(), before)
        for kind in cs.SIDECAR_FOLDERS:
            self.assertEqual(result.unpaused_bytes[self.rel(kind, 2)], before[self.rel(kind, 2)])
        for copied in result.files:
            self.assertEqual(sb._hash_file(backup / copied.relative), (copied.size, copied.sha256))

    def test_a_backup_keeps_a_sidecar_that_did_not_match_as_it_is(self):
        foreign = kids_sidecar(b"another save")
        self.sidecar("Children", 2).write_bytes(foreign)
        result = sb.back_up_save_folder(self.folder, NoGame(), WHEN)
        self.assertEqual(result.rematched_sidecars, [self.rel("Outfits", 2)])
        self.assertEqual(cs.sidecar_path(result.backup_folder, "Children", 2).read_bytes(), foreign)

    def play_on(self) -> None:
        """The family plays on after the backup: a new save, new sidecars."""
        live = self.folder / r.save_file_name(2)
        newer = live.read_bytes()[:-2] + b"\x01\x02"
        live.write_bytes(newer)
        self.sidecar("Children", 2).write_bytes(kids_sidecar(newer))
        self.sidecar("Outfits", 2).write_bytes(outfits_sidecar(newer))

    def test_a_restored_backup_keeps_every_child(self):
        for slot in (None, 2):
            with self.subTest(slot=slot):
                backup = sb.back_up_save_folder(self.folder, NoGame(), WHEN).backup_folder
                self.play_on()
                sb.restore_backup(self.folder, backup, slot, NoGame(), LATER)
                self.assertEqual(gs.read_state((self.folder / r.save_file_name(2)).read_bytes()).label, "Paused")
                for kind in cs.SIDECAR_FOLDERS:
                    self.assertTrue(self.matches(kind, 2))
                self.assertEqual(simulated_load(self.folder, 2), EVERYONE)
                sb.delete_backup(self.folder, backup)

    def test_a_failed_restore_puts_the_sidecars_back_as_they_were(self):
        backup = sb.back_up_save_folder(self.folder, NoGame(), WHEN).backup_folder
        self.play_on()
        before = self.snapshot()
        real = sb._place
        placed = []

        def flaky(source, target):
            placed.append(target.name)
            if len(placed) == 3:                       # the save and its two sidecars are the three changes
                raise OSError("disk full")
            real(source, target)

        with mock.patch.object(sb, "_place", flaky):
            with self.assertRaisesRegex(sb.BackupError, "put back"):
                sb.restore_backup(self.folder, backup, None, NoGame(), LATER)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(simulated_load(self.folder, 2), EVERYONE)


class OneSlotRestoreTests(Base):
    def test_the_slots_files(self):
        self.assertEqual(sb.file_slot(Path(f"{DATA}/Outfits/Virtual Families 23.ldw.dat")), 3)
        self.assertEqual(sb.file_slot(Path(f"{DATA}/Children/Virtual Families 223.ldw.dat")), 3)
        self.assertEqual(sb.file_slot(Path(f"{DATA}/Outfits/Virtual Families 224.ldw.dat")), 4)
        self.assertEqual(sb.file_slot(Path(f"{PATCHER}/Save 3/Logs/Family History/Family History 1.txt")), 3)
        self.assertEqual(sb.file_slot(Path(f"{PATCHER}/Save 2/Data/Family Tree/x.tree")), 2)
        self.assertIsNone(sb.file_slot(Path(f"{PATCHER}/Save 9/x.txt")))
        self.assertIsNone(sb.file_slot(Path(f"{PATCHER}/x.txt")))
        self.assertIsNone(sb.file_slot(Path(f"{DATA}/Children/Virtual Families 21.ldw.unreadable-1.dat")))
        self.assertIsNone(sb.file_slot(Path("Elsewhere/Save 3/x.txt")))

    def test_a_one_slot_restore_takes_the_slots_outfits_previous_sidecars_and_folder_and_nothing_else(self):
        logs1 = f"{PATCHER}/Save 1/Logs/Family History/Family History 1.txt"
        logs2 = f"{PATCHER}/Save 2/Logs/Family History/Family History 1.txt"
        self.put(logs1, b"Family: Lorsieab2 (Save 1)\r\n")
        self.put(logs2, b"Family: test (Save 2)\r\n")
        backup = sb.back_up_save_folder(self.folder, NoGame(), WHEN).backup_folder
        old = self.snapshot()
        # Slot 1 plays on: every one of its files changes; slot 2's log grows too.
        self.put(logs1, b"Family: Lorsieab2 (Save 1)\r\n[later] Birth 1\r\n")
        self.put(logs2, b"Family: test (Save 2)\r\n[later] Birth 1\r\n")
        for number in (1, 21):
            live = self.folder / r.save_file_name(number)
            newer = live.read_bytes()[:-2] + b"\x03\x04"
            live.write_bytes(newer)
            self.sidecar("Children", number).write_bytes(kids_sidecar(newer))
            self.sidecar("Outfits", number).write_bytes(outfits_sidecar(newer))
        self.put(f"{PATCHER}/Save 1/Data/Family Tree/new.tree", b"{}")
        plan = sb.plan_restore(self.folder, backup, 1)
        self.assertIn(Path(logs1), plan.replace)
        self.assertIn(Path(f"{PATCHER}/Save 1/Data/Family Tree/new.tree"), plan.remove)
        sb.restore_backup(self.folder, backup, 1, NoGame(), LATER)
        now = self.snapshot()
        for number in (1, 21):
            self.assertEqual(now[Path(r.save_file_name(number))], old[Path(r.save_file_name(number))])
            for kind in cs.SIDECAR_FOLDERS:
                self.assertEqual(now[self.rel(kind, number)], old[self.rel(kind, number)], (kind, number))
                self.assertTrue(self.matches(kind, number))
        self.assertEqual(now[Path(logs1)], old[Path(logs1)])
        self.assertNotIn(Path(f"{PATCHER}/Save 1/Data/Family Tree/new.tree"), now)
        self.assertEqual(now[Path(logs2)], b"Family: test (Save 2)\r\n[later] Birth 1\r\n")   # another slot
        self.assertEqual(simulated_load(self.folder, 1), EVERYONE)


if __name__ == "__main__":
    unittest.main()
