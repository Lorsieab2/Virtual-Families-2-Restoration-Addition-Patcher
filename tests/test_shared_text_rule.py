#!/usr/bin/env python3
"""Every patcher reader and writer of Virtual Families 2 save and log text uses ONE rule: src/vf2_game_text.py.

For each reader / writer: a Latin-1 name, UTF-8 names ("Łukasz", "日本", "Zoë 👩🏽‍💻"), the old Windows-1252 bytes a
save may already hold, and names at the field's limit (never cut inside a character; the field keeps its 0). Then a
source scan: no src/ module decodes or encodes save or log text with another codec.

Every save here is a temp copy of a fixture (tests/fixtures/vf2_saves). No owner save is ever opened.
"""
from __future__ import annotations

import gzip
import re
import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_copy_slot as cs  # noqa: E402
import vf2_family_history as fh  # noqa: E402
import vf2_game_text as T  # noqa: E402
import vf2_genealogy as gen  # noqa: E402
import vf2_rename_family as rf  # noqa: E402
import vf2_save_reader as r  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "vf2_saves"
WHEN = datetime(2026, 11, 1, 9, 30, 0)

LATIN1 = "Zoë Brontë"
UTF8 = ("Łukasz", "日本", "Zoë 👩🏽‍💻")
OLD_BYTES = b"Ren\xe9e \x93Bo\x94"                # what an older tool or a typed key left: Windows-1252
OLD_TEXT = "Renée “Bo”"
NAMES = (LATIN1,) + UTF8


def fixture(name: str) -> bytes:
    return gzip.decompress((FIX / name).read_bytes())


def whole_characters(text: str, cut: str) -> bool:
    """``cut`` is ``text`` up to a character boundary (vf2_game_text.clusters)."""
    pieces = T.clusters(text)
    return any("".join(pieces[:k]) == cut for k in range(len(pieces) + 1))


class NoGame:
    def find_game(self, save_folder_name):
        return []

    def suspend(self, pid, exe_name):
        raise AssertionError("no game is running")

    def resume(self, handle):
        pass


class FieldRuleTests(unittest.TestCase):
    """The rule itself as the readers and writers use it: field_bytes then decode."""

    def check_field(self, name: str, size: int) -> None:
        raw = T.field_bytes(name, size)
        self.assertEqual(len(raw), size)
        self.assertEqual(raw[-1], 0, "the field always keeps its terminating 0")
        back = T.decode(raw)
        self.assertTrue(whole_characters(name, back), (name, back))
        if len(T.encode(name)) <= size - 1:
            self.assertEqual(back, name)

    def test_every_name_in_every_field_size(self):
        for size in (20, 21, 24, 25, 28, 0x28):
            for name in NAMES + ("A" * 40, "日本" * 10, "Zoë 👩🏽‍💻" * 3, "é" * 30, "🇯🇵" * 8):
                with self.subTest(size=size, name=name):
                    self.check_field(name, size)

    def test_old_windows_1252_bytes_read_as_before(self):
        self.assertEqual(T.decode(OLD_BYTES), OLD_TEXT)
        self.assertEqual(T.decode(OLD_BYTES), OLD_BYTES.decode("cp1252"))


class SaveReaderTests(unittest.TestCase):
    """vf2_save_reader: villager names, Family Tree names, the player name and the settings file's slot list."""

    def setUp(self):
        self.save = bytearray(fixture("one_generation_slot3.ldw.gz"))
        self.settings = bytearray(fixture("settings_slot0.ldw.gz"))
        self.bio = r.gs_to_file(r.GS_VILLAGERS) + 0x08          # villager 0's CVillagerBio
        self.nick = r.gs_to_file(r.GS_NICKNAME)

    def test_villager_and_player_names(self):
        for raw, text in [(T.field_bytes(n, 25), n) for n in NAMES] + [(OLD_BYTES + b"\0", OLD_TEXT)]:
            with self.subTest(text=text):
                self.save[self.bio + 0x10:self.bio + 0x10 + len(raw)] = raw
                self.save[self.nick:self.nick + 20] = T.field_bytes(text, 20)
                parsed = r.parse_family_save(bytes(self.save))
                self.assertEqual(parsed.villagers[0].name, text)
                self.assertEqual(parsed.nickname, T.decode(T.field_bytes(text, 20)))

    def test_the_player_name_at_its_limit_is_cut_at_a_character(self):
        for name in ("A" * 19, "Ł" * 9 + "a", "日本語の名前", "Zoë 👩🏽‍💻"):
            with self.subTest(name=name):
                self.save[self.nick:self.nick + 20] = T.field_bytes(name, 20)
                got = r.parse_family_save(bytes(self.save)).nickname
                self.assertTrue(whole_characters(name, got))
                self.assertLessEqual(len(T.encode(got)), 19)
        # "Zoë 👩🏽‍💻" is 20 bytes: it loses the whole emoji, never part of it
        self.save[self.nick:self.nick + 20] = T.field_bytes("Zoë 👩🏽‍💻", 20)
        self.assertEqual(r.parse_family_save(bytes(self.save)).nickname, "Zoë ")

    def test_settings_slot_list(self):
        o = r.HEADER_SIZE + 0x10
        for k, name in enumerate(NAMES):
            self.settings[o + k * 0x15:o + (k + 1) * 0x15] = T.field_bytes(name, 0x15)
        self.settings[o + 4 * 0x15:o + 5 * 0x15] = OLD_BYTES.ljust(0x15, b"\0")
        names = r.parse_settings(bytes(self.settings)).player_names
        self.assertEqual(names, NAMES + (OLD_TEXT,))


class ChildrenSidecarTests(unittest.TestCase):
    """vf2_genealogy: the Up to 28 Children file's 28-byte name field (b200kids)."""

    SAVE = b"x" * 64

    def round_trip(self, name: str) -> str:
        data = gen.make_children_sidecar(self.SAVE, 1, 0, 0, [gen.ExtraChild(9, 1, "alive", 2, 3, 40, name)])
        at = gen.KIDS_HEADER + 24
        field = data[at:at + 28]
        self.assertEqual(field[-1], 0)
        self.assertEqual(field, T.field_bytes(name, 28))
        return gen.read_children_sidecar(data).children[0].name

    def test_names_round_trip(self):
        for name in NAMES:
            with self.subTest(name=name):
                self.assertEqual(self.round_trip(name), name)

    def test_names_at_the_limit(self):
        self.assertEqual(self.round_trip("A" * 27), "A" * 27)
        self.assertEqual(self.round_trip("A" * 30), "A" * 27)
        self.assertEqual(self.round_trip("日本" * 5), "日本" * 4 + "日")          # 27 bytes, 9 whole characters
        cut = self.round_trip("Zoë 👩🏽‍💻👩🏽‍💻")                       # 35 bytes: the second emoji goes whole
        self.assertEqual(cut, "Zoë 👩🏽‍💻")

    def test_old_windows_1252_bytes(self):
        data = bytearray(gen.make_children_sidecar(self.SAVE, 1, 0, 0,
                                                   [gen.ExtraChild(9, 1, "alive", 2, 3, 40, "x")]))
        at = gen.KIDS_HEADER + 24
        data[at:at + 28] = OLD_BYTES.ljust(28, b"\0")
        struct.pack_into("<Q", data, len(data) - 8, gen.fnv1a64(bytes(data[:-8])))
        self.assertEqual(gen.read_children_sidecar(bytes(data)).children[0].name, OLD_TEXT)


class FamilyHistoryLogTests(unittest.TestCase):
    """vf2_family_history: a log line holds a name in its stored form (vf2history_b200.dll copies the save's bytes)."""

    def test_log_text_and_log_bytes_round_trip(self):
        for name in NAMES + (OLD_TEXT,):
            text = f"[2026-11-01 09:30:00] Family Renamed 1\r\n  Old name: {name}\r\n  New name: Zed\r\n\r\n"
            with self.subTest(name=name):
                self.assertEqual(fh.log_text(fh.log_bytes(text)), text)

    def test_latin1_lines_stay_single_bytes(self):
        self.assertEqual(fh.log_bytes(f"  Name: {LATIN1}\r\n"), f"  Name: {LATIN1}\r\n".encode("latin-1"))

    def test_a_dll_log_with_mixed_lines(self):
        raw = (b"[2026-11-01 09:30:00] Family Renamed 1\r\n  Old name: " + OLD_BYTES + b"\r\n  New name: "
               + "日本".encode("utf-8") + b"\r\n\r\n[2026-11-01 09:31:00] Family Renamed 2\r\n  Old name: "
               + "日本".encode("utf-8") + b"\r\n  New name: " + LATIN1.encode("latin-1") + b"\r\n\r\n")
        with tempfile.TemporaryDirectory() as tmp:
            logs = rf.history_folder(Path(tmp), 1)
            logs.mkdir(parents=True)
            (logs / "Family History 1.txt").write_bytes(raw)
            h = fh.read(Path(tmp), 1)
        self.assertEqual(h.renames, [(OLD_TEXT, "日本"), ("日本", LATIN1)])


class SlotFolder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "Virtual Families 2 - Modded B205"
        self.folder.mkdir()
        (self.folder / r.save_file_name(0)).write_bytes(fixture("settings_slot0.ldw.gz"))
        (self.folder / r.save_file_name(1)).write_bytes(fixture("one_generation_slot3.ldw.gz"))
        self.logs = rf.history_folder(self.folder, 1)
        self.logs.mkdir(parents=True)
        (self.logs / "Family History 1.txt").write_bytes(b"Family: Lorsieab2 (Save 1)\r\n\r\n")

    def set_old_name(self, raw: bytes) -> None:
        path = self.folder / r.save_file_name(1)
        data = bytearray(path.read_bytes())
        at = r.gs_to_file(r.GS_NICKNAME)
        data[at:at + 20] = raw.ljust(20, b"\0")
        path.write_bytes(bytes(data))
        path = self.folder / r.save_file_name(0)
        data = bytearray(path.read_bytes())
        data[rf.MENU_FIRST:rf.MENU_FIRST + rf.MENU_FIELD] = raw.ljust(rf.MENU_FIELD, b"\0")
        path.write_bytes(bytes(data))

    def saved_name(self, number: int) -> bytes:
        data = (self.folder / r.save_file_name(number)).read_bytes()
        at = r.gs_to_file(r.GS_NICKNAME)
        return data[at:at + 20]


class RenameFamilyTests(SlotFolder):
    """vf2_rename_family: any Unicode name, written with field_bytes within the exact field, and its log record."""

    def test_rename_to_every_kind_of_name(self):
        old = "Lorsieab2"
        for name in (LATIN1, "Łukasz", "日本", "Zoë 💻", "Ł" * 9 + "a", "日本語の名前"):
            with self.subTest(name=name):
                self.assertIsNone(rf.name_problem(name))
                result = rf.rename_family(self.folder, 1, name, processes=NoGame(), now=WHEN)
                self.assertEqual(result.new_name, name)
                self.assertEqual(self.saved_name(1), T.field_bytes(name, 20))
                self.assertEqual(r.parse_family_save((self.folder / r.save_file_name(1)).read_bytes()).nickname,
                                 name)
                settings = r.parse_settings((self.folder / r.save_file_name(0)).read_bytes())
                self.assertEqual(settings.player_names[0], name)
                self.assertEqual(rf.read_slots(self.folder)[0].label, f"Save 1: {name}")
                self.assertEqual(fh.read(self.folder, 1).renames[-1], (old, name))
                old = name

    def test_an_old_windows_1252_name_is_shown_and_logged_as_it_reads(self):
        self.set_old_name(OLD_BYTES)
        self.assertEqual(rf.read_slots(self.folder)[0].label, f"Save 1: {OLD_TEXT}")
        rf.rename_family(self.folder, 1, "日本", processes=NoGame(), now=WHEN)
        self.assertEqual(fh.read(self.folder, 1).renames, [(OLD_TEXT, "日本")])

    def test_the_limit_is_19_bytes_counted_in_whole_characters(self):
        self.assertIsNone(rf.name_problem("A" * 19))
        self.assertIsNone(rf.name_problem("é" * 19))                    # Latin-1: one byte each
        self.assertIsNone(rf.name_problem("Ł" * 9 + "a"))               # 19 bytes
        problem = rf.name_problem("Ł" * 10)                             # 20 bytes
        self.assertIn("10 characters is too long", problem)
        self.assertIn("The first 9 characters fit", problem)
        self.assertIn("at most 19", rf.name_problem("A" * 20))
        self.assertIsNotNone(rf.name_problem("Zoë 👩🏽‍💻"))       # 20 bytes
        before = self.saved_name(1)
        with self.assertRaises(rf.RenameError):
            rf.rename_family(self.folder, 1, "Ł" * 10, processes=NoGame(), now=WHEN)
        self.assertEqual(self.saved_name(1), before, "a name over the limit is refused, never cut")

    def test_the_counter_shows_characters(self):
        self.assertEqual(rf.name_counter(""), ("0 / 19 characters", False))
        self.assertEqual(rf.name_counter("Zoë"), ("3 / 19 characters", False))
        self.assertEqual(rf.name_counter("日本"), ("2 characters (6 / 19 bytes)", False))
        self.assertEqual(rf.name_counter("Zoë 👩🏽‍💻"), ("5 characters (20 / 19 bytes)", True))
        self.assertEqual(rf.name_counter("A" * 20), ("20 / 19 characters", True))

    def test_with_name_never_cuts(self):
        data = bytes(64)
        self.assertEqual(rf._with_name(data, 8, 20, "日本")[8:28], T.field_bytes("日本", 20))
        with self.assertRaises(rf.RenameError):
            rf._with_name(data, 8, 20, "日本語の名前です")                 # 24 bytes


class CopySlotTests(SlotFolder):
    """vf2_copy_slot: the copy's name and its Family History record."""

    def test_copy_with_unicode_names(self):
        for target, name in ((2, "Zoë 💻"), (3, "Łukasz")):
            with self.subTest(name=name):
                cs.copy_slot(self.folder, 1, target, name, processes=NoGame(), now=WHEN, replace=True)
                self.assertEqual(self.saved_name(target), T.field_bytes(name, 20))
                settings = r.parse_settings((self.folder / r.save_file_name(0)).read_bytes())
                self.assertEqual(settings.player_names[target - 1], name)
                self.assertEqual(fh.read(self.folder, target).renames[-1], ("Lorsieab2", name))

    def test_history_record_bytes(self):
        raw = cs.history_record(OLD_TEXT, "日本", 1, WHEN, 3)
        self.assertEqual(fh.log_text(raw), fh.log_text(fh.log_bytes(
            f"[{WHEN:%Y-%m-%d %H:%M:%S}] Family Renamed 3\r\n  Old name: {OLD_TEXT}\r\n  New name: 日本\r\n"
            f"  Copied from: Save 1\r\n\r\n")))
        self.assertIn("日本".encode("utf-8"), raw)


class FamilyTreeTests(unittest.TestCase):
    """vf2_genealogy.load_village (the Family Tree Maker, Member Info, Relationships): names from the save."""

    def test_a_unicode_name_reaches_the_family(self):
        data = bytearray(fixture("one_generation_slot3.ldw.gz"))
        save = r.parse_family_save(bytes(data))
        old = next(v.name for v in save.villagers if v.active and v.name)
        new = "Zoë 👩🏽‍💻"
        fields = []
        for slot in range(r.VILLAGER_SLOTS):
            bio = r.gs_to_file(r.GS_VILLAGERS) + slot * r.VILLAGER_RECORD_SIZE + 0x08
            fields += [(bio + 0x10, 25), (bio + 0x34, 25), (bio + 0x4E, 25), (bio + 0x7C, 24)]
        base = r.gs_to_file(r.GS_FAMILY_TREE)
        for i in range(r.FAMILY_RECORDS):
            rec = base + 4 + i * r.FAMILY_RECORD_SIZE
            fields += [(rec + 0x04, 25), (rec + 0xDC, 25)]
            fields += [(rec + 0x1B8 + k * r.PEEP_RECORD_SIZE, 25) for k in range(r.FAMILY_CHILD_SLOTS)]
        changed = 0
        for at, size in fields:
            if T.decode(bytes(data[at:at + size])) == old:
                data[at:at + size] = T.field_bytes(new, size)
                changed += 1
        self.assertGreater(changed, 0)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / r.save_file_name(1)).write_bytes(bytes(data))
            family = gen.load_village(folder, slot=1)
        names = {p.name for p in family.people.values()}
        self.assertIn(new, names)
        self.assertNotIn(old, names)


# ---------------------------------------------------------------- the source scan

# Every non-UTF-8 codec any src/ module names, and why it is not save or log text. Anything else fails.
ALLOWED = {
    ("offline_vf2_patcher.py", "ascii"): "PE section names of the exe (8 ASCII bytes)",
    ("vf2_family_tree.py", "ascii"): "base64 text of a picture",
    ("vf2_glyph_maker.py", "ascii"): "the patcher's own glyph list file",
    ("vf2_game_text.py", "latin-1"): "the rule itself",
    ("vf2_text_tool.py", "utf-16-le"): "dropping lone surrogates from typed text",
    ("vf2_glyph_render.py", "utf-16-be"): "a font file's own name table",
    ("vf2_glyph_render.py", "mac_roman"): "a font file's own name table (Macintosh records)",
    ("vf2_unicode_font.py", "utf-16"): "the Unicode Font tool's own ini (Windows' Unicode ini form)",
    ("vf2_unicode_font.py", "latin-1"): "reading back a hand-edited ini of the tool's",
}
CODEC = re.compile(r"""(?:\.(?:decode|encode)\(\s*|encoding\s*=\s*|codecs\.\w+\([^)]*?)["']([A-Za-z0-9_-]+)["']""")
SAVE_TEXT_MODULES = ("vf2_save_reader.py", "vf2_genealogy.py", "vf2_family_history.py", "vf2_rename_family.py",
                     "vf2_copy_slot.py")


class SourceScanTests(unittest.TestCase):
    def codecs_in(self, path: Path) -> list[str]:
        return [m.group(1).lower() for m in CODEC.finditer(path.read_text(encoding="utf-8"))]

    def test_no_module_uses_another_codec_for_save_text(self):
        found = {}
        for path in sorted((ROOT / "src").rglob("*.py")):
            for codec in self.codecs_in(path):
                if codec.replace("_", "-") in ("utf-8", "utf8", "utf-8-sig"):
                    continue
                found.setdefault((path.name, codec), 0)
                found[(path.name, codec)] += 1
        unexpected = sorted(set(found) - set(ALLOWED))
        self.assertEqual(unexpected, [], "decode save / log text with vf2_game_text, not another codec")

    def test_the_save_text_modules_go_through_vf2_game_text(self):
        for name in SAVE_TEXT_MODULES:
            for tree in ("src", "work"):
                with self.subTest(module=f"{tree}/{name}"):
                    source = (ROOT / tree / name).read_text(encoding="utf-8")
                    # the copy's log records go through vf2_family_history.log_text / log_bytes
                    via = "import vf2_family_history" if name == "vf2_copy_slot.py" else "import vf2_game_text"
                    self.assertIn(via, source)
                    self.assertNotRegex(source, r"\.decode\(\s*[\"'](?!utf-8)")
                    self.assertNotRegex(source, r"\.encode\(\s*[\"'](?!utf-8)")

    def test_the_scan_catches_a_cp1252_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.py"
            bad.write_text('name = raw.decode("cp1252", "replace")\nopen(p, encoding="latin-1")\n', encoding="utf-8")
            self.assertEqual(self.codecs_in(bad), ["cp1252", "latin-1"])

    def test_vf2_game_text_ships_beside_the_tools(self):
        self.assertEqual((ROOT / "src" / "vf2_game_text.py").read_bytes(),
                         (ROOT / "work" / "vf2_game_text.py").read_bytes())
        sys.path.append(str(ROOT / "work"))
        import export_offline_patch_bundle as exporter
        import verify_offline_bundle_zip as verifier
        self.assertIn("vf2_game_text.py", exporter.GUI_TOOL_FILES)
        self.assertIn("vf2_game_text.py", verifier.REQUIRED_RUNNERS)


if __name__ == "__main__":
    unittest.main()
