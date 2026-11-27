#!/usr/bin/env python3
"""Skin Tones (src/vf2_skin_tones.py): the tones file the Skin Tones DLL keeps beside each save, read and changed while
the game is closed, and carried by every slot tool.

Every save here is a temp copy of a real save fixture (tests/fixtures/vf2_saves) in a fake save folder; the tones
files are built here byte by byte at the offsets the DLL uses (runtime/native/b200skin/b200skin.cpp). No owner save is
ever opened.
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
sys.path.insert(0, str(ROOT / "tests"))
import test_copy_slot as tc  # noqa: E402
import test_delete_slot as td  # noqa: E402
import vf2_copy_slot as cs  # noqa: E402
import vf2_delete_slot as ds  # noqa: E402
import vf2_family_history as fh  # noqa: E402
import vf2_move_slot as ms  # noqa: E402
import vf2_names as names  # noqa: E402
import vf2_save_backup as sb  # noqa: E402
import vf2_save_reader as r  # noqa: E402
import vf2_skin_tones as sk  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "vf2_saves"
WHEN = datetime(2026, 11, 27, 9, 30, 5)
DATA = "Virtual Families 2 Patcher Data"
LOGS = "Virtual Families 2 Patcher/Save 1/Logs/Family History"
ONE_GEN = "one_generation_slot3.ldw.gz"    # generation 1, parent 1 slot 0 female; Elsa (0, f), Paulolo (1, m) ...
TEN_GEN = "ten_generations_slot4.ldw.gz"


def fixture(name: str) -> bytes:
    return gzip.decompress((FIX / name).read_bytes())


def fnv(data: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in data:
        value = ((value ^ byte) * 0x100000001B3) & ((1 << 64) - 1)
    return value


def person(slot, gender, name, tone, birth, who, head=1, body=2, gen=(1, 0), place=(0, 0)):
    return dict(slot=slot, gender=gender, name=name, tone=tone, birth=birth, head=head, body=body, gen=gen,
                place=place, person=who)


def build(save: bytes, people, generations=1, parent_slot=0, parent_gender=1, save_hash=None) -> bytes:
    """A tones file placed field by field at the offsets the DLL uses."""
    size = 52 + 64 * len(people) + 8
    out = bytearray(size)
    out[0:8] = b"VF2SKIN\0"
    struct.pack_into("<I", out, 8, 1)
    out[12:20] = b"VF2B200\0"
    struct.pack_into("<I", out, 20, size)
    struct.pack_into("<Q", out, 24, fnv(save) if save_hash is None else save_hash)
    struct.pack_into("<I", out, 32, len(save))
    struct.pack_into("<i", out, 36, generations)
    struct.pack_into("<i", out, 40, parent_slot)
    struct.pack_into("<i", out, 44, parent_gender)
    struct.pack_into("<I", out, 48, len(people))
    for k, p in enumerate(people):
        at = 52 + 64 * k
        struct.pack_into("<ii", out, at, p["slot"], p["gender"])
        raw = p["name"] if isinstance(p["name"], bytes) else p["name"].encode("latin-1")
        out[at + 8:at + 8 + len(raw)] = raw
        out[at + 34] = p["tone"]
        out[at + 35] = p["birth"]
        struct.pack_into("<ii", out, at + 36, p["head"], p["body"])
        struct.pack_into("<ii", out, at + 44, *p["gen"])
        struct.pack_into("<ii", out, at + 52, *p["place"])
        struct.pack_into("<I", out, at + 60, p["person"])
    struct.pack_into("<Q", out, size - 8, fnv(bytes(out[:-8])))
    return bytes(out)


def resum(data: bytes) -> bytes:
    return data[:-8] + struct.pack("<Q", fnv(data[:-8]))


def poke(data: bytes, offset: int, value: bytes) -> bytes:
    """``data`` with ``value`` at ``offset`` and the checksum made again, so only the rule being tested fails."""
    return resum(data[:offset] + value + data[offset + len(value):])


FAMILY = [person(0, 1, "Elsa", 3, 3, 1), person(1, 0, "Paulolo", 0, 0, 2), person(2, 0, "Merlino", 15, 7, 3),
          person(-1, 1, "Elsa", 3, 3, 1, gen=(0, 0)),           # a copy of Elsa: the same person number
          person(3, 0, "Pierur", 8, 0, 4)]


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
        self.folder = Path(self._tmp.name) / "Virtual Families 2 - Modded B209"
        self.folder.mkdir()
        (self.folder / r.save_file_name(0)).write_bytes(fixture("settings_slot0.ldw.gz"))
        self.save = fixture(ONE_GEN)
        (self.folder / r.save_file_name(1)).write_bytes(self.save)
        (self.folder / r.save_file_name(21)).write_bytes(fixture(TEN_GEN))
        self.tones = self.put_tones(1, build(self.save, FAMILY))

    def put_tones(self, number: int, data: bytes) -> Path:
        path = sk.sidecar_path(self.folder, number)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def put(self, relative: str, data: bytes) -> Path:
        path = self.folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def snapshot(self) -> dict:
        return {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob("*")
                if p.is_file() and p.relative_to(self.folder).parts[0] != sb.BACKUPS_FOLDER}

    def set(self, wanted, processes=None):
        return sk.set_tones(self.folder, 1, wanted, processes=processes or NoGame(), now=WHEN)


class FileFormatTests(unittest.TestCase):
    def test_a_hand_built_file_reads_and_writes_back_byte_for_byte(self):
        save = fixture(ONE_GEN)
        data = build(save, FAMILY, generations=7, parent_slot=4, parent_gender=0)
        self.assertEqual(len(data), 52 + 64 * 5 + 8)
        tones = sk.read_file(data)
        self.assertIsNotNone(tones)
        self.assertEqual((tones.save_hash, tones.save_size, tones.generations, tones.parent_slot,
                          tones.parent_gender), (fnv(save), len(save), 7, 4, 0))
        elsa = tones.entries[0]
        self.assertEqual((elsa.slot, elsa.gender, elsa.stored_name, elsa.tone, elsa.birth, elsa.head, elsa.body,
                          elsa.gen, elsa.place, elsa.person), (0, 1, b"Elsa", 3, 3, 1, 2, (1, 0), (0, 0), 1))
        self.assertEqual(len(elsa.name), 26)
        self.assertEqual(sk.make_file(tones), data)
        self.assertTrue(sk.describes(tones, save))
        self.assertEqual(sk.make_file(sk.read_file(build(save, []))), build(save, []))

    def test_a_25_byte_name_and_the_bytes_after_its_nul_round_trip(self):
        save = fixture(ONE_GEN)
        data = build(save, [person(0, 1, b"A" * 25, 1, 1, 1), person(1, 0, b"Bo\0junk", 2, 2, 2)])
        tones = sk.read_file(data)
        self.assertEqual(tones.entries[0].stored_name, b"A" * 25)
        self.assertEqual(tones.entries[1].stored_name, b"Bo")
        self.assertEqual(sk.make_file(tones), data)

    def test_every_rule_refuses_a_bad_file(self):
        save = fixture(ONE_GEN)
        good = build(save, FAMILY)
        e = 52                                       # the first entry
        bad = {
            "magic": poke(good, 0, b"VF2SKIX\0"),
            "version": poke(good, 8, struct.pack("<I", 2)),
            "tag": poke(good, 12, b"VF2B201\0"),
            "size field": poke(good, 20, struct.pack("<I", len(good) + 1)),
            "a byte more": resum(good[:-8] + b"\0" + good[-8:]),
            "count": poke(good, 48, struct.pack("<I", 6)),
            "count over 400": poke(good, 48, struct.pack("<I", 401)),
            "checksum": good[:-1] + bytes([good[-1] ^ 1]),
            "short": good[:52],
            "slot -2": poke(good, e, struct.pack("<i", -2)),
            "slot 30": poke(good, e, struct.pack("<i", 30)),
            "gender 2": poke(good, e + 4, struct.pack("<i", 2)),
            "name[25]": poke(good, e + 8 + 25, b"x"),
            "tone 11": poke(good, e + 34, bytes([11])),
            "tone 14": poke(good, e + 34, bytes([14])),
            "tone 16": poke(good, e + 34, bytes([16])),
            "birth 11": poke(good, e + 35, bytes([11])),
            "gen 31": poke(good, e + 44, struct.pack("<i", 31)),
            "gen -1": poke(good, e + 48, struct.pack("<i", -1)),
            "place 8": poke(good, e + 52, struct.pack("<i", 8)),
            "place -1": poke(good, e + 56, struct.pack("<i", -1)),
        }
        for rule, data in bad.items():
            with self.subTest(rule=rule):
                self.assertIsNone(sk.read_file(data))
        for ok in (poke(good, e + 34, bytes([0])), poke(good, e + 34, bytes([15])), poke(good, e + 35, bytes([10])),
                   poke(good, e, struct.pack("<i", -1)), poke(good, e + 44, struct.pack("<i", 30))):
            self.assertIsNotNone(sk.read_file(ok))

    def test_the_presets_and_their_stored_values(self):
        self.assertEqual(sk.PRESETS, ("Game's own", "S1 Porcelain", "S2 Fair", "S3 Light golden", "S4 Light olive",
                                      "S5 Copper", "S6 Warm brown", "S7 Medium brown", "S8 Deep brown", "S9 Dark",
                                      "S10 Ebony"))
        self.assertEqual(sk.choice_value("Game's own", 0), 15)
        for k in range(1, 11):
            self.assertEqual(sk.choice_value(sk.PRESETS[k], 0), k)
        self.assertEqual(sk.choice_value(sk.RESET_LABEL, 6), 6)
        self.assertIsNone(sk.choice_value(sk.RESET_LABEL, 0))
        self.assertIsNone(sk.choice_value(sk.NOT_SET_LABEL, 4))
        self.assertEqual([sk.tone_name(t) for t in (0, 1, 10, 15)], ["Game's own", "Porcelain", "Ebony", "Game's own"])
        self.assertEqual([sk.tone_label(t) for t in (0, 3, 15)], ["(not set yet)", "S3 Light golden", "Game's own"])
        with_birth = sk.Member(0, 1, "Elsa", 41, 26, 35, 0, tone=3, birth=3)
        no_birth = sk.Member(1, 0, "Paulolo", 41, 24, 1, 1, tone=0, birth=0)
        self.assertEqual(sk.choices(with_birth), list(sk.PRESETS) + ["Reset to birth tone"])
        self.assertEqual(sk.choices(no_birth), list(sk.PRESETS))
        self.assertNotIn("Default", " ".join(sk.PRESETS + (sk.RESET_LABEL, sk.NOT_SET_LABEL, sk.NO_TONE_YET)))


class ChosenFileTests(Base):
    def chosen(self):
        family = sk.read_family(self.folder, 1)
        return family.path, family.problem

    def test_the_saves_own_file_comes_first(self):
        self.put_tones(21, build(self.save, FAMILY[:1]))
        self.assertEqual(self.chosen(), (self.tones, None))

    def test_then_the_previous_file_that_describes_the_save(self):
        self.put_tones(1, build(self.save, FAMILY, save_hash=1))          # an older save's
        older = self.put_tones(21, build(self.save, FAMILY[:2]))
        self.assertEqual(self.chosen(), (older, None))

    def test_then_the_own_file_of_the_same_family(self):
        self.put_tones(1, build(self.save, FAMILY, save_hash=1))
        self.put_tones(21, build(self.save, FAMILY, save_hash=2))
        self.assertEqual(self.chosen(), (self.tones, None))

    def test_another_family_or_no_file_means_no_tones_yet(self):
        for gens, pslot, pgender in ((2, 0, 1), (1, 3, 1), (1, 0, 0)):
            with self.subTest(gens=gens, pslot=pslot, pgender=pgender):
                self.put_tones(1, build(self.save, FAMILY, gens, pslot, pgender, save_hash=1))
                path, problem = self.chosen()
                self.assertIsNone(path)
                self.assertIn("no skin tones yet", problem)
                self.assertIn("Play it once", problem)
        self.tones.unlink()
        self.assertIn("no skin tones yet", self.chosen()[1])
        self.assertFalse(sk.sidecar_path(self.folder, 1).exists())     # nothing is made

    def test_a_damaged_file_is_named_and_nothing_changes(self):
        damaged = self.tones.read_bytes()[:-1] + b"\0"
        self.tones.write_bytes(damaged)
        before = self.snapshot()
        path, problem = self.chosen()
        self.assertIsNone(path)
        self.assertIn("damaged", problem)
        with self.assertRaisesRegex(sk.SkinToneError, "damaged"):
            self.set({0: 5})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(sb.list_backups(self.folder), [])


class MembersTests(Base):
    def test_household_members_with_an_entry_are_editable_the_rest_are_not(self):
        family = sk.read_family(self.folder, 1)
        self.assertIsNone(family.problem)
        shown = {m.name: (m.editable, m.shown_tone) for m in family.members}
        self.assertEqual(shown["Elsa"], (True, "S3 Light golden"))
        self.assertEqual(shown["Paulolo"], (True, "(not set yet)"))
        self.assertEqual(shown["Merlino"], (True, "Game's own"))
        self.assertEqual(shown["Pierur"], (True, "S8 Deep brown"))
        for name in ("Stephor", "Zigo", "Lola", "Snap"):
            self.assertEqual(shown[name], (False, "(no tone yet: play this family once)"))
        elsa = family.members[0]
        self.assertEqual((elsa.slot, elsa.gender, elsa.age_years, elsa.head, elsa.body), (0, 1, 41, 26, 35))

    def test_slot_gender_and_name_must_all_match(self):
        self.put_tones(1, build(self.save, [person(0, 0, "Elsa", 3, 3, 1), person(1, 0, "Paulo", 3, 3, 2),
                                            person(4, 0, "Merlino", 3, 3, 3)]))
        self.assertFalse(any(m.editable for m in sk.read_family(self.folder, 1).members))

    def test_whole_names_are_shown(self):
        with mock.patch.object(names.Book, "full", lambda self, slot, stored: stored + " the Whole"):
            family = sk.read_family(self.folder, 1)
        self.assertEqual(family.members[0].name, "Elsa the Whole")


class SetTonesTests(Base):
    def test_one_person_changes_every_entry_of_theirs_and_only_the_tone_and_checksum(self):
        before = self.tones.read_bytes()
        result = self.set({0: 5})
        after = self.tones.read_bytes()
        self.assertEqual(len(after), len(before))
        changed = [k for k in range(len(before)) if before[k] != after[k]]
        tone_bytes = {52 + 34, 52 + 3 * 64 + 34}                  # Elsa and her copy (person 1)
        self.assertTrue(set(changed) - set(range(len(before) - 8, len(before))) == tone_bytes, changed)
        tones = sk.read_file(after)
        self.assertEqual([e.tone for e in tones.entries], [5, 0, 15, 5, 8])
        self.assertEqual([e.birth for e in tones.entries], [3, 0, 7, 3, 0])
        self.assertEqual(after[24:36], before[24:36])                # the save's hash and size stay
        self.assertEqual(self.save, (self.folder / r.save_file_name(1)).read_bytes())   # the save is not changed
        self.assertEqual([(c.member.name, c.old, c.new) for c in result.changes], [("Elsa", 3, 5)])
        self.assertEqual(result.path, self.tones)

    def test_reset_to_birth_tone(self):
        family = sk.read_family(self.folder, 1)
        merlino = next(m for m in family.members if m.name == "Merlino")
        self.assertIn(sk.RESET_LABEL, sk.choices(merlino))
        self.set({merlino.slot: sk.choice_value(sk.RESET_LABEL, merlino.birth)})
        self.assertEqual(sk.read_file(self.tones.read_bytes()).entries[2].tone, 7)

    def test_only_the_chosen_file_is_edited(self):
        self.put_tones(1, build(self.save, FAMILY, save_hash=1))
        older = self.put_tones(21, build(self.save, FAMILY))
        own = self.tones.read_bytes()
        result = self.set({1: 2})
        self.assertEqual(result.path, older)
        self.assertEqual(self.tones.read_bytes(), own)
        self.assertEqual(sk.read_file(older.read_bytes()).entries[1].tone, 2)

    def test_nothing_to_change_and_no_tone_yet_are_refused(self):
        before = self.snapshot()
        with self.assertRaisesRegex(sk.SkinToneError, "Nothing to change"):
            self.set({0: 3})
        with self.assertRaisesRegex(sk.SkinToneError, "no skin tone yet"):
            self.set({5: 3})                                          # Zigo: no entry
        with self.assertRaisesRegex(sk.SkinToneError, "not a skin tone"):
            self.set({0: 11})
        self.assertEqual(self.snapshot(), before)

    def test_a_running_game_is_refused_and_nothing_changes(self):
        before = self.snapshot()
        with self.assertRaisesRegex(sk.GameRunning, "Close the game first"):
            self.set({0: 5}, processes=Running())
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(sb.list_backups(self.folder), [])

    def test_the_folder_is_backed_up_first(self):
        original = self.tones.read_bytes()
        seen = []
        real = sb.copy_save_folder

        def copy(folder, when, suffix=""):
            seen.append(self.tones.read_bytes())
            return real(folder, when, suffix=suffix)

        with mock.patch.object(sb, "copy_save_folder", copy):
            result = self.set({0: 5})
        self.assertEqual(seen, [original])                           # the file was not yet changed
        backups = sb.list_backups(self.folder)
        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0].before_skin_tones)
        self.assertTrue(backups[0].path.name.endswith("(before skin tones)"))
        self.assertTrue(backups[0].label.endswith("(before skin tones)"))
        self.assertEqual((result.backup.backup_folder / DATA / "Skin Tones" / self.tones.name).read_bytes(), original)

    def test_a_failed_write_leaves_the_file_as_it_was(self):
        before = self.snapshot()
        real = os.replace

        def full(source, target):          # only the tones file's swap fails (the backup uses os.replace too)
            if Path(target).parent.name == "Skin Tones":
                raise OSError("disk full")
            real(source, target)

        with mock.patch.object(sk.os, "replace", full):
            with self.assertRaisesRegex(sk.SkinToneError, "put back"):
                self.set({0: 5})
        self.assertEqual(self.snapshot(), before)                   # no temp file left either

    def test_a_file_that_does_not_read_back_is_put_back(self):
        original = self.tones.read_bytes()
        real = sk._write_atomically

        def spoiled(path, data):
            real(path, data)
            if data != original:
                path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))

        with mock.patch.object(sk, "_write_atomically", spoiled):
            with self.assertRaisesRegex(sk.SkinToneError, "put back"):
                self.set({0: 5})
        self.assertEqual(self.tones.read_bytes(), original)

    def test_a_temp_file_then_replace(self):
        calls = []
        real = os.replace

        def spy(source, target):
            if Path(target).parent.name == "Skin Tones":
                calls.append((Path(source).name, Path(target).name))
            real(source, target)

        with mock.patch.object(sk.os, "replace", spy):
            self.set({0: 5})
        self.assertEqual(len(calls), 1)
        self.assertRegex(calls[0][0], r"^Virtual Families 21\.ldw\.dat\.skin-[0-9a-f]{12}\.tmp$")
        self.assertEqual(calls[0][1], "Virtual Families 21.ldw.dat")


class LogTests(Base):
    def test_the_record_is_exact(self):
        log = self.put(f"{LOGS}/Family History 1.txt", b"Family: Lorsieab2 (Save 1)\r\n")
        result = self.set({0: 5})
        self.assertEqual(result.notes, [log])
        self.assertEqual(log.read_bytes(), (
            b"Family: Lorsieab2 (Save 1)\r\n"
            b"[2026-11-27 09:30:05] Appearance changed 1\r\n"
            b"  Name: Elsa\r\n"
            b"  Age: 41\r\n"
            b"  Sex: Female\r\n"
            b"  Head: 26\r\n"
            b"  Body: 35\r\n"
            b"  Old skin tone: Light golden\r\n"
            b"  New skin tone: Copper\r\n"
            b"  How: Skin Tones window\r\n"
            b"  Generation: 1\r\n"
            b"\r\n"))

    def test_no_log_no_record(self):
        result = self.set({0: 5})
        self.assertEqual(result.notes, [])
        self.assertFalse((self.folder / "Virtual Families 2 Patcher").exists())   # no log is ever started

    def test_several_changes_are_numbered_after_every_earlier_one_in_the_newest_file(self):
        first = self.put(f"{LOGS}/Family History 1.txt",
                         b"Family: Lorsieab2 (Save 1)\r\n[2026-11-01 10:00:00] Appearance changed 2\r\n  Name: X\r\n\r\n")
        newest = self.put(f"{LOGS}/Family History 2.txt", b"Family: Lorsieab2 (Save 1)\r\n[x] Birth 1")
        old_first = first.read_bytes()
        self.set({0: 15, 1: 10, 2: 1})
        self.assertEqual(first.read_bytes(), old_first)
        text = newest.read_bytes().decode("utf-8")
        self.assertTrue(text.startswith("Family: Lorsieab2 (Save 1)\r\n[x] Birth 1\r\n[2026-11-27 09:30:05] "
                                        "Appearance changed 3\r\n  Name: Elsa\r\n"))
        self.assertIn("Appearance changed 4\r\n  Name: Paulolo\r\n", text)
        self.assertIn("  Old skin tone: Game's own\r\n  New skin tone: Ebony\r\n", text)     # 0 -> 10
        self.assertIn("Appearance changed 5\r\n  Name: Merlino\r\n", text)
        self.assertIn("  Old skin tone: Game's own\r\n  New skin tone: Porcelain\r\n", text)  # 15 -> 1
        self.assertIn("  Old skin tone: Light golden\r\n  New skin tone: Game's own\r\n", text)
        self.assertEqual(text.count("Appearance changed"), 3)
        history = fh.read(self.folder, 1)
        self.assertEqual([(n, s, o, w, g) for n, s, o, w, g in history.appearances], [
            ("X", "", "", "", 0), ("Elsa", "Female", "Light golden", "Game's own", 1),
            ("Paulolo", "Male", "Game's own", "Ebony", 1), ("Merlino", "Male", "Game's own", "Porcelain", 1)])

    def test_a_log_that_cannot_be_written_leaves_the_change_done(self):
        self.put(f"{LOGS}/Family History 1.txt", b"Family: Lorsieab2 (Save 1)\r\n")
        with mock.patch.object(sk, "log_changes", side_effect=OSError("locked")):
            result = self.set({0: 5})
        self.assertEqual(result.notes, [])
        self.assertEqual(sk.read_file(self.tones.read_bytes()).entries[0].tone, 5)


class FamilyHistoryReaderTests(unittest.TestCase):
    def test_appearance_changed_is_a_known_record(self):
        text = ("Family: A (Save 1)\r\n[2026-11-27 09:30:05] Appearance changed 1\r\n  Name: Elsa\r\n  Age: 41\r\n"
                "  Sex: Female\r\n  Head: 26\r\n  Body: 35\r\n  Old skin tone: Light golden\r\n"
                "  New skin tone: Copper\r\n  How: Skin Tones window\r\n  Generation: 1\r\n\r\n"
                "[2026-11-27 09:31:00] Death 1\r\n  Name: Elsa\r\n  Sex: Female\r\n  Generation: 1\r\n\r\n")
        h = fh.parse(text)
        self.assertEqual([(e.kind, e.number) for e in h.entries], [("Appearance changed", 1), ("Death", 1)])
        self.assertEqual(h.appearances, [("Elsa", "Female", "Light golden", "Copper", 1)])
        self.assertEqual(h.entries[0].get("How"), "Skin Tones window")
        self.assertEqual(len(h.deaths), 1)                           # the records after it are read as before
        self.assertIn("Appearance changed", fh.__doc__)


class SidecarToolTests(Base):
    """Copy, Move, Delete, Rename, Game Speed and Back Up know the Skin Tones folder (tests/test_sidecar_rekey.py
    covers Rename, Game Speed, Back Up and Restore for every folder in SIDECAR_FOLDERS)."""

    def test_the_folder_is_registered(self):
        self.assertIn("Skin Tones", cs.SIDECAR_FOLDERS)
        self.assertEqual(cs.SIDECAR_WHAT["Skin Tones"], "skin tones")
        self.assertIn("skin tones", sb.SIDECAR_FOLDERS)
        self.assertEqual(sk.sidecar_path(self.folder, 21), cs.sidecar_path(self.folder, "Skin Tones", 21))
        self.assertEqual(sb.file_slot(Path(f"{DATA}/Skin Tones/Virtual Families 223.ldw.dat")), 3)
        self.assertEqual(sb.file_slot(Path(f"{DATA}/Skin Tones/Virtual Families 25.ldw.dat")), 5)

    def test_copy_slot_reads_and_rekeys_it(self):
        data = self.tones.read_bytes()
        self.assertEqual(cs.read_sidecar("Skin Tones", data), cs.Sidecar(fnv(self.save), len(self.save)))
        self.assertIsNone(cs.read_sidecar("Skin Tones", data[:-1] + b"\0"))
        other = fixture(TEN_GEN)
        again = cs.rekeyed(data, other)
        self.assertTrue(cs.sidecar_describes("Skin Tones", again, other))
        self.assertEqual(again[:24], data[:24])
        self.assertEqual(again[36:-8], data[36:-8])
        changed = self.save[:100] + bytes([self.save[100] ^ 1]) + self.save[101:]
        found = cs.sidecar_rekeys(self.folder, 1, [(self.save, changed)])
        self.assertEqual([(p.name, kind) for p, kind, _o, _n in found], [("Virtual Families 21.ldw.dat", "Skin Tones")])


class CopyMoveDeleteTests(tc.Base):
    def setUp(self):
        super().setUp()
        for number in (1, 21):
            save = (self.folder / r.save_file_name(number)).read_bytes()
            self.put(f"{DATA}/Skin Tones/Virtual Families 2{number}.ldw.dat", build(save, FAMILY))

    def test_copy_player_slot_rekeys_the_skin_tones_to_the_copy(self):
        before = self.snapshot()
        self.copy()
        for number in (4, 24):
            side = (self.folder / DATA / "Skin Tones" / f"Virtual Families 2{number}.ldw.dat").read_bytes()
            save = (self.folder / r.save_file_name(number)).read_bytes()
            self.assertTrue(cs.sidecar_describes("Skin Tones", side, save), number)
            original = before[Path(DATA, "Skin Tones", f"Virtual Families 2{number - 3}.ldw.dat")]
            self.assertEqual(side[36:-8], original[36:-8])             # the tones themselves are the same

    def test_move_player_slot_carries_them(self):
        before = self.snapshot()
        ms.move_slot(self.folder, 1, 4, processes=tc.NoGame(), now=tc.WHEN)
        after = self.snapshot()
        for old, new in ((1, 4), (21, 24)):
            self.assertNotIn(Path(DATA, "Skin Tones", f"Virtual Families 2{old}.ldw.dat"), after)
            self.assertEqual(after[Path(DATA, "Skin Tones", f"Virtual Families 2{new}.ldw.dat")],
                             before[Path(DATA, "Skin Tones", f"Virtual Families 2{old}.ldw.dat")])
        self.assertTrue(cs.sidecar_describes("Skin Tones", after[Path(DATA, "Skin Tones", "Virtual Families 24.ldw.dat")],
                                             after[Path("Virtual Families 24.ldw")]))

    def test_delete_player_slot_sends_them_to_the_recycle_bin(self):
        fake = td.FakeBin(self.folder)
        ds.delete_slot(self.folder, 1, processes=tc.NoGame(), recycle=fake)
        for number in (1, 21):
            path = self.folder / DATA / "Skin Tones" / f"Virtual Families 2{number}.ldw.dat"
            self.assertFalse(path.exists())
            self.assertIn(path, fake.kept)


if __name__ == "__main__":
    unittest.main()
