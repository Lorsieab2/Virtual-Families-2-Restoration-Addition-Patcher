#!/usr/bin/env python3
"""Family Logs from save comparisons (src/vf2_family_logs.py).

Every save here is synthetic (tests/vf2_save_builder.py) or a gzip copy of a real save in
tests/fixtures/vf2_saves, written into a temp save folder. No real save folder is touched and no game runs.
"""
import gzip
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import vf2_family_logs as F  # noqa: E402
import vf2_save_reader as R  # noqa: E402
from vf2_save_builder import SaveBuilder  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "vf2_saves"
FOLDER = "Virtual Families 2 - Modded B202"
MOM, DAD = ("Ann", 1, 0, 3, 4), ("Bob", 0, 1, 5, 6)


class NoGame:
    def find_game(self, name):
        return []


class Running:
    def find_game(self, name):
        return [(1234, "Virtual Families 2 - Modded B202.exe")]


def founders() -> SaveBuilder:
    """Generation 1: Ann (slot 0) married Bob (slot 1)."""
    b = SaveBuilder(nickname="Smiths")
    b.villager(0, "Ann", 1, 30, head=3, body=4).villager(1, "Bob", 0, 32, head=5, body=6)
    b.generation(0, MOM, DAD)
    return b


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.docs = Path(self._tmp.name) / "Documents"
        self.folder = self.docs / "LDW" / FOLDER
        self.folder.mkdir(parents=True)
        self.root = F.slot_root(self.folder, 1)
        self.clock = 1000

    def save(self, builder: SaveBuilder, slot: int = 1, previous: bool = False, advance: int = 600) -> None:
        self.clock += advance
        builder.clock(self.clock, self.clock * 2)
        number = slot + 20 if previous else slot
        builder.write(self.folder / R.save_file_name(number))

    def run_slot(self, slot: int = 1) -> F.SlotResult:
        return F.update_slot(self.folder, slot)

    def log(self, kind: str, number: int = 1, root: Path | None = None) -> str:
        return F.log_path(root or self.root, kind, number).read_bytes().decode("cp1252")

    def history(self) -> list:
        return [line for line in self.log("history").split("\r\n")[1:] if line]

    def dated(self) -> list:
        return [line.split("] ", 1)[1] for line in self.history() if not line.startswith("[backfilled")]


class FilesAndFormat(Base):
    def test_every_log_and_data_file_has_the_vf1_name_and_header(self):
        self.save(founders())
        result = self.run_slot()
        self.assertEqual(result.status, "backfilled")
        base = self.folder / "Virtual Families 2 Patcher" / "Save 1"
        for rel in ("Logs/Family History/Family History 1.txt",
                    "Logs/Births and Conceptions/Virtual Families 2 Births and Conceptions Log 1.txt",
                    "Logs/Deaths/Virtual Families 2 Deaths Log 1.txt",
                    "Logs/Events/Virtual Families 2 Events Log 1.txt"):
            text = (base / rel).read_bytes().decode("cp1252")
            self.assertTrue(text.startswith("Family: Smiths (Save 1)\r\n"), rel)
        self.assertTrue((base / "Logs/Family Population/Family Population - Save 1.txt").is_file())
        self.assertTrue((base / "Logs/Family Statistics/Family Statistics - Save 1.txt").is_file())
        data = sorted(p.relative_to(base).as_posix() for p in (base / "Data").rglob("*") if p.is_file())
        self.assertEqual(data, [
            "Data/Log Checks/Virtual Families 2 Backfill - Save 1.dat",
            "Data/Unaccounted Villagers/Virtual Families 2 Family Members at Last Save - Save 1.dat",
        ])

    def test_header_falls_back_to_the_slot_name_then_no_name(self):
        b = founders().nickname("")
        self.save(b)
        self.run_slot()
        self.assertTrue(self.log("history").startswith("Family: (no name) (Save 1)"))

    def test_lines_are_dated_by_the_save_real_time_and_game_clock(self):
        b = founders()
        self.save(b)
        self.run_slot()
        b.villager(2, "Cy", 0, 1, mother="Ann")
        b.generation(0, MOM, DAD, children=[("Cy", 0, 2)])
        self.save(b)
        self.run_slot()
        line = [l for l in self.history() if "Cy" in l][0]
        self.assertRegex(line, r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d, game time [\d.]+ years\] Cy \(Male, 1\) joined")

    def test_snapshot_round_trips(self):
        self.save(founders().villager(4, "Dee", 1, 20, left_home=True, left_seconds=24000))
        self.run_slot()
        path = F.data_path(self.root, F.MEMBERS_DATA, 1)
        snap = F.read_snapshot_text(path.read_bytes().decode("cp1252"))
        self.assertEqual(F.write_snapshot_text(snap), path.read_bytes().decode("cp1252"))
        self.assertIsNone(F.read_snapshot_text("VF2LOGS MEMBERS 1\r\nfamily\tx\r\n"))


class Backfill(Base):
    def test_existing_family_is_backfilled_once(self):
        b = founders()
        b.villager(2, "Cy", 0, 5, mother="Ann")
        b.generation(0, MOM, DAD, children=[("Cy", 0, 2), ("Gone", 1, -1)])
        self.save(b)
        self.assertEqual(self.run_slot().status, "backfilled")
        lines = self.history()
        self.assertEqual(lines[0], "[backfilled, no date] Generation 1: Ann (Female) and Bob (Male) were the parents")
        self.assertIn("[backfilled, no date] Generation 1: child Gone (Female), died", lines)
        self.assertEqual(self.run_slot().status, "unchanged")
        self.save(b)
        self.run_slot()
        self.assertEqual(lines, self.history())
        marker = F.data_path(self.root, F.BACKFILL_DATA, 1).read_bytes().decode("cp1252")
        self.assertIn("how\tbackfilled", marker)

    def test_logs_already_there_are_never_backfilled_again(self):
        self.save(founders())
        self.run_slot()
        F.data_path(self.root, F.BACKFILL_DATA, 1).unlink()
        F.data_path(self.root, F.MEMBERS_DATA, 1).unlink()
        before = self.history()
        self.run_slot()
        self.assertEqual(before, self.history())
        self.assertIn("logs found", F.data_path(self.root, F.BACKFILL_DATA, 1).read_bytes().decode("cp1252"))

    def test_slot_with_no_family_yet_logs_the_founder_with_a_date(self):
        b = SaveBuilder(nickname="New")
        self.save(b)
        self.run_slot()
        self.assertEqual(self.history(), [])
        b.villager(0, "Ann", 1, 25, head=3, body=4).generation(0, MOM)
        self.save(b)
        self.run_slot()
        self.assertEqual(self.dated(), ["Generation 1 began: Ann (Female, 25) was adopted and started the family"])


class Events(Base):
    def start(self, b=None) -> SaveBuilder:
        b = b or founders()
        self.save(b)
        self.run_slot()
        return b

    def test_conception_then_twins(self):
        b = self.start()
        b.villager(0, "Ann", 1, 30, head=3, body=4, pregnant=True, babies=2)
        b.villager(2, "Cy", 0, 0, active=False, mother="Ann", father="Joey")
        b.villager(3, "Di", 1, 0, active=False, mother="Ann", father="Joey")
        b.pending(2, 3).generation(0, MOM, DAD, children=[("Cy", 0, 2), ("Di", 1, 3)])
        self.save(b)
        self.run_slot()
        self.assertEqual(self.dated(), ["Conception 1: Ann is expecting (babies expected: 2)"])
        births = self.log("births")
        self.assertIn("Conception 1\r\n  Mother: Ann\r\n", births)
        self.assertIn("  Father: not recorded in the save\r\n  Babies expected: 2\r\n", births)
        b.villager(0, "Ann", 1, 30, head=3, body=4)
        b.villager(2, "Cy", 0, 0, mother="Ann", father="Joey").villager(3, "Di", 1, 0, mother="Ann", father="Joey")
        b.pending()
        self.save(b)
        self.run_slot()
        self.assertEqual(self.dated()[1:], ["Birth 1: Cy (Male) was born to Ann (Twins)",
                                            "Birth 2: Di (Female) was born to Ann (Twins)"])
        self.assertIn("  Born as: Twins\r\n  Generation: 1\r\n", self.log("births"))
        self.assertNotIn("joined", "\n".join(self.history()))

    def test_death_seen_with_health_zero_then_removed_is_logged_once(self):
        b = self.start()
        b.villager(1, "Bob", 0, 70, head=5, body=6, health=0, cause=2)
        self.save(b)
        self.run_slot()
        self.assertEqual(self.dated(), ["Death 1: Bob (Male, 70) died (cause not recorded)"])
        deaths = self.log("deaths")
        self.assertIn("  Age at death: 70\r\n", deaths)
        self.assertIn("  Cause of death: not recorded (the save's cause number is 2; its meaning is not confirmed)", deaths)
        self.assertIn("  Family role: Parent (married in)\r\n", deaths)
        b.remove(1).generation(0, MOM, ("Bob", 0, -1, 5, 6))
        self.save(b)
        self.run_slot()
        self.assertEqual(len(self.dated()), 1)
        self.assertIn("Deaths: 1\r\n", F.page_path(self.root, "Family Statistics", 1).read_bytes().decode("cp1252"))

    def test_death_the_tree_reports_between_saves(self):
        b = self.start()
        b.remove(1).generation(0, MOM, ("Bob", 0, -1, 5, 6))
        self.save(b)
        self.run_slot()
        self.assertEqual(self.dated(), ["Death 1: Bob (Male, 32) died (cause not recorded)"])
        self.assertIn("  Age when last seen: 32\r\n  Sex: Male\r\n  Cause of death: not recorded\r\n", self.log("deaths"))

    def test_marriage(self):
        b = SaveBuilder(nickname="Smiths").villager(0, "Ann", 1, 30, head=3, body=4).generation(0, MOM)
        self.start(b)
        b.villager(1, "Bob", 0, 32, head=5, body=6).generation(0, MOM, DAD)
        self.save(b)
        self.run_slot()
        self.assertEqual(self.dated(), ["Ann (Female, 30) married Bob (Male, 32), generation 1"])

    def test_next_generation(self):
        b = founders().villager(2, "Cy", 0, 20, head=7, body=8, mother="Ann")
        b.generation(0, MOM, DAD, children=[("Cy", 0, 2, 7, 8)])
        self.start(b)
        b.generation(1, ("Cy", 0, 2, 7, 8), heir=0)
        self.save(b)
        self.run_slot()
        self.assertEqual(self.dated(), ["New Generation: generation 2 began: Cy (Male, 20) inherited the house"])

    def test_tree_window_of_thirty_keeps_counting_generations(self):
        b = SaveBuilder(nickname="Long")
        for i in range(30):
            b.generation(i, (f"P{i}", 0, -1, i, i))
        b.villager(0, "P29", 0, 30, head=29, body=29).generation(29, ("P29", 0, 0, 29, 29))
        self.start(b)
        # MakeRoomInTree: the oldest record goes, a new one is added at the end
        c = SaveBuilder(nickname="Long")
        for i in range(29):
            c.generation(i, (f"P{i + 1}", 0, -1, i + 1, i + 1))
        c.generation(28, ("P29", 0, 0, 29, 29)).generation(29, ("Q", 0, 1, 40, 40))
        c.villager(0, "P29", 0, 30, head=29, body=29).villager(1, "Q", 0, 20, head=40, body=40)
        self.save(c)
        self.run_slot()
        self.assertEqual(self.dated(), ["New Generation: generation 31 began: Q (Male, 20) inherited the house"])
        self.assertIn("Generations: 31\r\n", F.page_path(self.root, "Family Statistics", 1).read_bytes().decode("cp1252"))

    def test_child_who_joins_and_one_who_leaves_home(self):
        b = founders().villager(2, "Cy", 0, 18, mother="Ann")
        b.generation(0, MOM, DAD, children=[("Cy", 0, 2)])
        self.start(b)
        b.villager(3, "Lil", 1, 6).generation(0, MOM, DAD, children=[("Cy", 0, 2), ("Lil", 1, 3)])
        b.villager(2, "Cy", 0, 19, mother="Ann", left_home=True, left_seconds=36000)
        self.save(b)
        self.run_slot()
        self.assertEqual(self.dated(), ["Cy (Male, 19) left home (game time 3.0 years)",
                                        "Lil (Female, 6) joined the family as a child, generation 1"])

    def test_someone_gone_without_a_recorded_death(self):
        b = founders().villager(5, "Zed", 0, 9)
        self.start(b)
        b.remove(5)
        self.save(b)
        self.run_slot()
        self.assertEqual(self.dated(), ["Zed (Male, 9) is no longer in the family; the save does not say why"])

    def test_eviction_keeps_the_logs_and_the_next_family_follows_it(self):
        self.start()
        c = SaveBuilder(nickname="Smiths").evicted(1)
        self.save(c)
        self.run_slot()
        self.assertEqual(self.dated(), ["Event 1: Evict Family"])
        self.assertIn("  Event: Evict Family\r\n  Family members: Ann, Bob\r\n  Generation: 1\r\n", self.log("events"))
        c.villager(0, "Eve", 1, 22).generation(0, ("Eve", 1, 0))
        self.save(c)
        self.run_slot()
        self.assertEqual(self.dated()[-1], "Generation 1 began after the eviction: Eve (Female, 22) was adopted")

    def test_eviction_and_new_family_in_one_step(self):
        self.start()
        self.save(SaveBuilder(nickname="Smiths").evicted(1).villager(0, "Eve", 1, 22).generation(0, ("Eve", 1, 0)))
        self.run_slot()
        self.assertEqual(self.dated(), ["Event 1: Evict Family",
                                        "Generation 1 began after the eviction: Eve (Female, 22) was adopted"])

    def test_rename_keeps_the_family(self):
        self.start()
        b = founders()
        b.villager(0, "Annie", 1, 30, head=3, body=4).generation(0, ("Annie", 1, 0, 3, 4), DAD)
        self.save(b)
        self.assertNotEqual(self.run_slot().status, "new family")


class NewFamily(Base):
    def test_other_founders_start_a_fresh_folder_and_keep_backups(self):
        self.save(founders())
        self.run_slot()
        keep = self.root / "Backups" / "Backup 2026-01-01 00-00-00"
        keep.mkdir(parents=True)
        (keep / "x.txt").write_text("keep")
        other = SaveBuilder(nickname="Smiths").villager(0, "Zoe", 1, 21, head=9, body=9).generation(0, ("Zoe", 1, 0, 9, 9))
        self.save(other)
        self.assertEqual(self.run_slot().status, "new family")
        self.assertEqual(self.dated(), ["Generation 1 began: Zoe (Female, 21) was adopted and started the family"])
        self.assertEqual((keep / "x.txt").read_text(), "keep")
        old = [p for p in (self.root / "Backups").iterdir() if p.name.startswith("Logs before new family")]
        self.assertEqual(len(old), 1)
        self.assertIn("Ann (Female) and Bob (Male)", self.log("history", root=old[0]))
        self.assertIn("new family", F.data_path(self.root, F.BACKFILL_DATA, 1).read_text("cp1252"))

    def test_start_over_empties_the_logs(self):
        self.save(founders())
        self.run_slot()
        self.save(SaveBuilder(nickname="Smiths"))
        self.assertEqual(self.run_slot().status, "new family")
        self.assertEqual(self.history(), [])

    def test_older_save_is_noted_not_diffed(self):
        b = founders()
        self.save(b)
        self.run_slot()
        b.villager(5, "Zed", 0, 9)
        self.save(b)
        self.run_slot()
        self.save(founders(), advance=-300)
        self.run_slot()
        self.assertTrue(self.dated()[-1].startswith("This save is older than the save logged before it"))
        self.assertEqual(sum("Zed" in line for line in self.history()), 1)


class PreviousSave(Base):
    def test_the_previous_save_is_read_so_one_save_back_is_not_missed(self):
        b = founders()
        self.save(b)
        self.run_slot()
        b.villager(0, "Ann", 1, 30, head=3, body=4, pregnant=True, babies=1)
        b.villager(2, "Cy", 0, 0, active=False, mother="Ann").pending(2)
        b.generation(0, MOM, DAD, children=[("Cy", 0, 2)])
        self.save(b, previous=True)            # the game kept this as Virtual Families 221.ldw
        b.villager(0, "Ann", 1, 30, head=3, body=4).villager(2, "Cy", 0, 0, mother="Ann").pending()
        self.save(b)
        self.run_slot()
        lines = self.history()
        self.assertEqual([l.split("] ", 1)[1] for l in lines[-2:]],
                         ["Conception 1: Ann is expecting (babies expected: 1)", "Birth 1: Cy (Male) was born to Ann"])
        self.assertNotEqual(lines[-2].split("]")[0], lines[-1].split("]")[0])    # each dated by its own save

    def test_a_previous_save_older_than_the_snapshot_is_ignored(self):
        b = founders()
        self.save(b.copy().villager(5, "Old", 0, 3), previous=True)
        self.save(b)
        self.run_slot()
        self.save(b)
        self.run_slot()
        self.assertFalse(any("Old" in line for line in self.history()))


class Rolling(Base):
    def test_history_and_records_roll_into_numbered_files(self):
        b = founders()
        self.save(b)
        self.run_slot()
        with mock.patch.object(F, "HISTORY_LINES_PER_FILE", 3), mock.patch.object(F, "RECORDS_PER_FILE", 2):
            for year in range(3):
                b.villager(1, "Bob", 0, 32, head=5, body=6, health=0) if year == 0 else None
                for k in range(3):
                    b.villager(10 + year * 3 + k, f"K{year}{k}", 0, 1, health=0)
                self.save(b)
                self.run_slot()
        self.assertTrue(F.log_path(self.root, "history", 4).is_file())
        self.assertTrue(F.log_path(self.root, "deaths", 5).is_file())
        last = self.log("deaths", 5)
        self.assertTrue(last.startswith("Family: Smiths (Save 1)\r\nDeath 9\r\n"))


class Folders(Base):
    def test_refused_while_the_game_is_running(self):
        self.save(founders())
        with self.assertRaises(F.FamilyLogsError):
            F.update_save_folder(self.folder, Running())
        self.assertFalse(self.root.exists())

    def test_update_all_logs_the_patcher_and_stock_folders_only(self):
        self.save(founders())
        copy = self.docs / "LDW" / "Virtual Families 2 - Copy (5) jessie"
        stock = self.docs / "LDW" / "Virtual Families 2"
        for f in (copy, stock):
            f.mkdir()
            founders().write(f / R.save_file_name(2))
        outcomes = F.update_all(self.docs, NoGame())
        self.assertEqual(sorted(o[0].name for o in outcomes), sorted([FOLDER, "Virtual Families 2"]))
        self.assertFalse((copy / F.PATCHER_FOLDER).exists())
        self.assertTrue(F.slot_root(stock, 2).is_dir())

    def test_unreadable_save_is_skipped(self):
        (self.folder / R.save_file_name(1)).write_bytes(b"ldwg broken")
        self.assertEqual(self.run_slot().status, "unreadable")
        self.assertFalse(self.root.exists())

    def test_save_files_are_never_written(self):
        self.save(founders())
        before = {p.name: p.read_bytes() for p in self.folder.iterdir() if p.is_file()}
        self.run_slot()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir() if p.is_file()})


class RealSaves(Base):
    """Copies of real saves: one family (slot 1) across builds B171 -> B192 -> B202."""

    def put(self, fixture: str, number: int = 1) -> None:
        (self.folder / R.save_file_name(number)).write_bytes(gzip.decompress((FIXTURES / fixture).read_bytes()))

    def test_ten_generation_backfill(self):
        self.put("ten_generations_slot4.ldw.gz", 4)
        self.assertEqual(F.update_slot(self.folder, 4).status, "backfilled")
        text = F.log_path(F.slot_root(self.folder, 4), "history", 1).read_text("cp1252")
        self.assertEqual(text.count("were the parents"), 10)

    def test_the_n_and_n_plus_20_pair_logs_nothing_new(self):
        # The game rewrote the save a second after the previous one: no family change between them.
        self.put("b192_slot1_previous.ldw.gz")
        self.run_slot()
        before = self.history()
        self.put("b192_slot1_previous.ldw.gz", 21)
        self.put("b192_slot1.ldw.gz")
        self.assertEqual(self.run_slot().status, "updated")
        self.assertEqual(before, self.history())

    def test_real_birth_and_a_child_who_appeared(self):
        self.put("pending_birth_slot1.ldw.gz")          # B171: Wizzy pregnant, Trishania not born yet
        self.run_slot()
        self.put("b192_slot1_previous.ldw.gz", 21)
        self.put("b192_slot1.ldw.gz")
        self.run_slot()
        self.assertEqual(self.dated(), [
            "Birth 1: Trishania (Female) was born to Wizzy",
            "Crisory (Male, 3) joined the family as a child (mother: Wizzy), generation 30",
        ])

    def test_real_deaths_and_two_new_generations_past_the_thirty_record_window(self):
        self.put("b192_slot1.ldw.gz")
        self.run_slot()
        self.put("b202_slot1_previous.ldw.gz")
        self.run_slot()
        lines = self.dated()
        self.assertEqual(lines[:2], ["Death 1: Oslo (Male, 37) died (cause not recorded)",
                                     "Death 2: Wizzy (Female, 38) died (cause not recorded)"])
        self.assertIn("New Generation: generation 31 began: Francory (Male) inherited the house", lines)
        self.assertIn("Snap (Male, 34) married Rupee (Female, 32), generation 32", lines)
        stats = F.page_path(self.root, "Family Statistics", 1).read_bytes().decode("cp1252")
        self.assertIn("Generations: 32\r\n", stats)
        self.assertIn("Babies Born: 233\r\n", stats)


if __name__ == "__main__":
    unittest.main()
