"""src/vf2_save_reader.py: the read-only Virtual Families 2 save reader.

Two kinds of evidence, kept apart:
- synthetic saves built here byte by byte at the offsets docs/vf2-save-format.md gives (each field is
  written at its documented offset and read back, so a wrong offset in the reader fails);
- fixtures that are real saves, copied and gzip-compressed byte for byte
  (scripts/make_vf2_save_fixtures.py). Their expected values were decoded with a separate throwaway
  decoder written straight from the disassembly, not with this module.
"""
from __future__ import annotations

import gzip
import importlib.util
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "vf2_saves"
sys.path.insert(0, str(ROOT / "src"))   # the reader decodes text with vf2_game_text, beside it in src/

_spec = importlib.util.spec_from_file_location("vf2_save_reader", ROOT / "src" / "vf2_save_reader.py")
r = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = r          # dataclasses look their module up while the class is built
_spec.loader.exec_module(r)


def fixture(name: str) -> bytes:
    return gzip.decompress((FIX / name).read_bytes())


def blank_family_save() -> bytearray:
    b = bytearray(r.GAME_FILE_SIZE)
    b[0:4] = b"ldwg"
    struct.pack_into("<qI", b, 4, 1_600_000_000, r.GAME_DATA_SIZE)
    return b


def put_str(b: bytearray, off: int, text: str, size: int) -> None:
    raw = text.encode("cp1252")
    assert len(raw) < size
    b[off:off + size] = raw + b"\0" * (size - len(raw))


class FileShape(unittest.TestCase):
    def test_sizes_from_the_game_code(self):
        self.assertEqual(r.GAME_FILE_SIZE, 154408)
        self.assertEqual(r.SETTINGS_FILE_SIZE, 160)
        self.assertEqual(r.VILLAGER_SLOTS * r.VILLAGER_RECORD_SIZE, 0xE808)
        self.assertEqual(4 + r.FAMILY_RECORDS * r.FAMILY_RECORD_SIZE, r.GS_FOOD_STORE - r.GS_FAMILY_TREE)
        self.assertEqual(0x1B8 + 6 * r.PEEP_RECORD_SIZE, r.FAMILY_RECORD_SIZE)
        self.assertEqual(r.gs_to_file(r.GS_VILLAGERS), 0x172B0)

    def test_header_forms(self):
        b = blank_family_save()
        h = r.parse_header(bytes(b))
        self.assertEqual((h.start_time, h.payload_size, h.legacy), (1_600_000_000, r.GAME_DATA_SIZE, False))
        legacy = b"ldwg" + struct.pack("<iI", 5, 4) + b"abcd"
        h = r.parse_header(legacy)
        self.assertTrue(h.legacy)
        self.assertEqual((h.start_time, h.payload_size), (5, 4))
        with self.assertRaises(r.SaveFormatError):
            r.parse_header(b"xxxx" + bytes(12))
        with self.assertRaises(r.SaveFormatError):
            r.parse_header(bytes(b[:-1]))

    def test_real_legacy_file_is_refused_like_the_game(self):
        data = fixture("legacy_header_slot5.ldw.gz")
        self.assertEqual(len(data), 154400)
        h = r.parse_header(data)
        self.assertTrue(h.legacy)
        self.assertEqual(h.payload_size, 0x25B14)
        with self.assertRaises(r.SaveFormatError):
            r.parse_family_save(data)

    def test_file_names(self):
        self.assertEqual(r.save_file_name(3), "Virtual Families 23.ldw")
        self.assertEqual(r.classify_save_file("Virtual Families 20.ldw"), ("settings", 0))
        self.assertEqual(r.classify_save_file("Virtual Families 25.ldw"), ("family", 5))
        self.assertEqual(r.classify_save_file("virtual families 25.ldw"), ("family", 5))
        self.assertEqual(r.classify_save_file("Virtual Families 221.ldw"), ("previous", 1))
        self.assertEqual(r.classify_save_file("Virtual Families 225.ldw"), ("previous", 5))
        for never in ("Virtual Families221.ldw", "Virtual Families 21 - Copy.ldw", "Virtual Families 220.ldw",
                      "Virtual Families 26.ldw", "Virtual Families 241.ldw", "Virtual Families 252.ldw",
                      "Virtual Families 201.ldw", "wc.dat", "ldwLog.txt"):
            self.assertIsNone(r.classify_save_file(never), never)
        self.assertEqual(r.save_folder_name("Virtual Families 2.exe"), "Virtual Families 2")
        self.assertEqual(r.save_folder_name("VF2 B20.2 test.exe"), "VF2 B20")
        self.assertEqual(r.children_sidecar_name(1), "Virtual Families 21.ldw.dat")


class SyntheticFields(unittest.TestCase):
    def test_every_villager_field_at_its_offset(self):
        b = blank_family_save()
        slot = 7
        v = 0x172B0 + slot * 0x7BC
        b[v] = 1
        b[v + 1] = 1
        struct.pack_into("<I", b, v + 4, 123456)
        bio = v + 8
        struct.pack_into("<iiii", b, bio, 395, 1, 17, 33)
        put_str(b, bio + 0x10, "Ada", 25)
        struct.pack_into("<ii", b, bio + 0x2C, 48, 12)
        put_str(b, bio + 0x34, "Pa", 25)
        put_str(b, bio + 0x4E, "Ma", 25)
        struct.pack_into("<iiiii", b, bio + 0x68, 1, 2, 3, 4, 9)
        put_str(b, bio + 0x7C, "Dad", 24)
        struct.pack_into("<ii", b, bio + 0x98, 21, 22)
        st = v + 0xA8
        struct.pack_into("<IIiii", b, st, 11, 12, 13, 0, 5)
        struct.pack_into("<ii", b, st + 0x24, 99, 2)
        struct.pack_into("<iiiiiiiii", b, st + 0x34, 61, 62, -63, 64, 65, 66, 67, 68, 0)
        b[st + 0x5E] = 1
        struct.pack_into("<iiii", b, v + 0x140, 0x26, 3, 10, 250)
        b[v + 0x150:v + 0x15C] = bytes(range(12))
        b[v + 0x15C:v + 0x168] = bytes(range(12, 24))
        struct.pack_into("<3H", b, v + 0x168, 7, 8, 9)
        struct.pack_into("<I", b, v + 0x7B8, 3)
        s = r.parse_family_save(bytes(b))
        x = s.villager(slot)
        self.assertTrue(x.active and x.left_home)
        self.assertEqual(x.left_home_game_seconds, 123456)
        self.assertEqual((x.age_units, x.age_years, x.gender_name, x.first_name_index, x.unconfirmed_bio_0c),
                         (395, 19, "female", 17, 33))
        self.assertEqual((x.name, x.head, x.body, x.father_name, x.mother_name), ("Ada", 48, 12, "Pa", "Ma"))
        self.assertEqual((x.father_head, x.father_body, x.mother_head, x.mother_body), (1, 2, 3, 4))
        self.assertEqual((x.pregnancy_father_bio_0c, x.pregnancy_father_name, x.pregnancy_father_body,
                          x.pregnancy_father_head), (9, "Dad", 21, 22))
        self.assertEqual((x.health, x.cause_of_death, x.dead), (0, 5, True))
        self.assertEqual((x.pregnancy_mark, x.babies_expected), (99, 2))
        self.assertEqual((x.energy, x.happiness, x.happiness_trend, x.hunger, x.dirtiness, x.poo,
                          x.fertility, x.procreation_desire), (61, 62, -63, 64, 65, 66, 67, 68))
        self.assertEqual(x.symptoms, (0, 0, 1, 0, 0, 0, 0))
        self.assertEqual((x.career_id, x.career_type, x.career_level, x.salary), (0x26, 2, 3, 250))
        self.assertEqual((x.likes_raw, x.dislikes_raw), (bytes(range(12)), bytes(range(12, 24))))
        self.assertEqual(x.ai_values, (7, 8, 9))
        self.assertEqual(s.away(), [x])
        self.assertEqual(s.household(), [])

    def test_family_tree_and_components(self):
        b = blank_family_save()
        ft = 0x1848
        struct.pack_into("<i", b, ft, 1)
        for g in range(2):
            rec = ft + 4 + g * 0x6C8
            b[rec] = 1
            b[rec + 1] = g
            p1 = rec + 4
            put_str(b, p1, "P1-%d" % g, 25)
            b[p1 + 0x1A] = 1
            struct.pack_into("<iiiiii", b, p1 + 0x1C, 1, 5, 6, -1, g - 1, 40)
            put_str(b, p1 + 0x34, "likes", 40)
            put_str(b, p1 + 0x5D, "dislikes", 40)
            p2 = rec + 0xDC
            put_str(b, p2, "Spouse", 25)
            b[p2 + 0x1A] = 1
            struct.pack_into("<i", b, rec + 0x1B4, 2)
            for k in range(2):
                c = rec + 0x1B8 + k * 0xD8
                put_str(b, c, "Kid%d" % k, 25)
                b[c + 0x1A] = 1
                struct.pack_into("<i", b, c + 0x28, 2 + k)
        rec = ft + 4 + 3 * 0x6C8          # after a gap: LoadState stops at the first absent record
        b[rec] = 1
        t = 0x16404
        struct.pack_into("<iiIII", b, t, 10, 0, 1000, 5000, 1600)
        struct.pack_into("<IIi", b, 0x168BC, 4321, 0x7F800000 | 10, 77)
        struct.pack_into("<iii4B", b, 0xE3BC, 250, 1, 3, 1, 2, 3, 4)
        struct.pack_into("<13i", b, 0x163D0, *range(100, 113))
        struct.pack_into("<3i", b, 0x25AB8, 4, -1, -1)
        put_str(b, 0x25AC4, "Player", 20)
        struct.pack_into("<i", b, 0x25AE0, 1001)
        struct.pack_into("<i", b, 0x25B20, 10)
        s = r.parse_family_save(bytes(b))
        tree = s.family_tree
        self.assertEqual((tree.evicted, tree.num_generations), (1, 2))
        g1 = tree.current
        self.assertEqual((g1.index, g1.can_start_next_generation, g1.parent1.name, g1.parent1.heir_index), (1, True, "P1-1", 0))
        self.assertEqual((g1.parent1.gender, g1.parent1.head, g1.parent1.body, g1.parent1.slot, g1.parent1.career_id),
                         (1, 5, 6, -1, 40))
        self.assertEqual((g1.parent1.likes, g1.parent1.dislikes, g1.parent2.name), ("likes", "dislikes", "Spouse"))
        self.assertEqual([(c.name, c.slot) for c in g1.children], [("Kid0", 2), ("Kid1", 3)])
        self.assertEqual(s.clock.game_seconds_at_save, 5600)
        self.assertEqual((s.money.amount, s.money.interest_rate, s.money.last_interest_game_seconds), (4321, 0.1, 77))
        self.assertEqual((s.food.food, s.food.unconfirmed_bytes_0c), (250, (1, 2, 3, 4)))
        self.assertEqual((s.stats.real_start_stamp, s.stats.babies_born, s.stats.oldest_age_years), (100, 102, 108))
        self.assertEqual((s.pending_baby_slots, s.nickname, s.save_version, s.speed_option), ((4, -1, -1), "Player", 1001, 10))
        self.assertEqual([v.slot for v in s.unborn()], [4])

    def test_paused_clock(self):
        c = r.GameClock(0, 10, 50, 777, 99999)
        self.assertEqual(c.game_seconds_at_save, 777)
        c = r.GameClock(20, 10, 100, 1000, 300)       # Seconds() divides real time by speed / 10
        self.assertEqual(c.game_seconds_at_save, 1100)


class RealSaves(unittest.TestCase):
    def test_one_generation(self):
        s = r.parse_family_save(fixture("one_generation_slot3.ldw.gz"))
        self.assertEqual((s.save_version, s.nickname, s.family_tree.evicted), (1001, "Lorsieab2", 1))
        g = s.family_tree.current
        self.assertEqual(s.family_tree.num_generations, 1)
        self.assertEqual((g.parent1.name, g.parent1.gender, g.parent1.slot, g.parent1.career_id), ("Elsa", 1, 0, 59))
        self.assertEqual((g.parent2.name, g.parent2.gender, g.parent2.slot), ("Paulolo", 0, 1))
        self.assertEqual([(c.name, c.slot) for c in g.children],
                         [("Merlino", 2), ("Pierur", 3), ("Stephor", 4), ("Zigo", 5), ("Lola", 6), ("Snap", 7)])
        elsa = s.villager(0)
        self.assertEqual((elsa.name, elsa.age_units, elsa.age_years, elsa.health, elsa.career_id, elsa.career_level),
                         ("Elsa", 833, 41, 95, 59, 6))
        lola = s.villager(6)
        self.assertEqual((lola.age_units, lola.head, lola.body, lola.father_name, lola.mother_name),
                         (136, 48, 9, "Joey", "Elsa"))
        self.assertEqual(len(s.household()), 8)
        self.assertEqual((s.money.amount, s.food.food), (52521, 4106))
        self.assertEqual((s.clock.speed, s.clock.game_seconds_base), (0, 40336257))
        self.assertTrue(all(len(v.ai_values) == 0x19B for v in s.household()))

    def test_ten_generations(self):
        s = r.parse_family_save(fixture("ten_generations_slot4.ldw.gz"))
        tree = s.family_tree
        self.assertEqual(tree.num_generations, 10)
        heirs = [(g.parent1.name, g.parent1.heir_index) for g in tree.generations]
        self.assertEqual(heirs[:3], [("Jessiana", -1), ("Brenina", 1), ("Pennette", 2)])
        for prev, g in zip(tree.generations, tree.generations[1:]):
            # the heir who starts a generation is the previous record's child at heir_index
            self.assertEqual(prev.children[g.parent1.heir_index].name, g.parent1.name)
        self.assertEqual(tree.current.parent1.name, "Jessie")
        self.assertEqual(len(s.household()), 30)

    def test_pending_birth(self):
        s = r.parse_family_save(fixture("pending_birth_slot1.ldw.gz"))
        self.assertEqual(s.pending_baby_slots, (1, -1, -1))
        baby = s.villager(1)
        self.assertEqual((baby.active, baby.name, baby.age_units, baby.mother_name), (False, "Trishania", 40, "Wizzy"))
        mother = s.villager(0)
        self.assertEqual((mother.name, mother.pregnancy_mark, mother.babies_expected), ("Wizzy", 560, 1))
        self.assertEqual(s.family_tree.num_generations, 30)
        self.assertEqual(s.family_tree.current.child_count, 1)     # AddOffspring runs at conception

    def test_settings(self):
        st = r.parse_settings(fixture("settings_slot0.ldw.gz"))
        self.assertEqual(st.player_names, ("Lorsieab2", "test", "Lorsieab2", "NEW PLAYER", "NEW PLAYER"))
        self.assertEqual(st.slot_in_use, (True, True, True, False, False))
        self.assertEqual((st.current_slot, st.version), (3, 1001))
        with self.assertRaises(r.SaveFormatError):
            r.parse_family_save(fixture("settings_slot0.ldw.gz"))


class ReadOnly(unittest.TestCase):
    def test_module_never_writes(self):
        import ast
        tree = ast.parse((ROOT / "src" / "vf2_save_reader.py").read_text(encoding="utf-8"))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                called.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
        forbidden = {"open", "write_bytes", "write_text", "remove", "unlink", "rename", "replace",
                     "rmdir", "mkdir", "touch", "chmod"}
        self.assertEqual(called & forbidden, set())
        self.assertIn("read_bytes", called)


if __name__ == "__main__":
    unittest.main()
