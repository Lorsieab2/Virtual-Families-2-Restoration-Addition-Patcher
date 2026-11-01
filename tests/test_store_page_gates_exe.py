"""Free and Guaranteed Cheats (.vf2free) and All outfits and hairstyles always for sale (.vf2clth), run on
executables built from this branch (unicorn; nothing starts the game, nothing on disk is written).

* VF2_GATES_CHEAT_EXE: a Cheat Upgrades executable built from this branch (for example the
  cheat_upgrades_holiday_ornaments_mobile_renovations variant).
* VF2_GATES_NOCHEAT_EXE: an executable without Cheat Upgrades built from this branch (for example
  holiday_ornaments_mobile_renovations).

Each test skips without its executable. The store's own CInventoryManager::GetCategoryItemCount /
GetCategoryItem run as linked, with the patcher's head hooks; the two bytes are written in emulator memory,
the way the patcher's runtime-flag records write them on disk. The functions are found by the hooks' own
bytes, so no address is pinned.

Also checked without an executable: the content the owner keeps on by default (Mobile Renovations, the 2nd
Bathroom renovations, the holiday furniture, outfits and collectibles) does not need Cheat Upgrades.
"""
from __future__ import annotations

import faulthandler
import json
import os
import re
import struct
import sys
from pathlib import Path

import pytest

faulthandler.disable()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

CHEAT_EXE = os.environ.get("VF2_GATES_CHEAT_EXE")
NOCHEAT_EXE = os.environ.get("VF2_GATES_NOCHEAT_EXE")

SPECIAL_UPGRADES, CLOTHING, HOUSE_RENOVATIONS = 0x14, 0x0D, 0x11
FREE_ROWS = [0x136, 0x158, 0x159]
NEXT_PICK = 0x470
STOCK_SIX = [0x12, 0x15, 0x13, 0x16, 0x14, 0x17]
HEAD_POOL = set(range(0x480, 0x480 + 50)) | set(range(0x4C0, 0x4C0 + 50))
HOLIDAY_POOL = set(range(0x400 + 50, 0x400 + 54)) | set(range(0x440 + 50, 0x440 + 54))

BASE = 0x400000
HEAP, HEAPSZ = 0x20000000, 0x200000
STACK, STACKSZ = 0x30000000, 0x100000
SENT, TEB, GDT = 0x3F000000, 0x3E000000, 0x3D000000

COUNT_HOOK = re.compile(
    rb"\x55\x8B\xEC\x51\xFF\x75\x08\x51\xE8....\x83\xC4\x08\x59\x83\xF8\xFF\x74\x04\x5D\xC2\x04\x00", re.DOTALL)
ITEM_HOOK = re.compile(
    rb"\x55\x8B\xEC\x51\xFF\x75\x0C\xFF\x75\x08\x51\xE8....\x83\xC4\x0C\x59\x83\xF8\xFF\x74\x04\x5D\xC2\x08\x00",
    re.DOTALL)


class Exe:
    def __init__(self, path: str):
        pefile = pytest.importorskip("pefile")
        unicorn = pytest.importorskip("unicorn")
        from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
        from unicorn import x86_const as X
        self.X = X
        self.path = Path(path)
        self.manifest = json.loads((self.path.parent / "patch-manifest.json").read_text(encoding="utf-8"))
        pe = pefile.PE(str(path), fast_load=True)
        self.sections = {s.Name.rstrip(b"\0"): s for s in pe.sections}
        text = self.sections[b".text"]
        code = pe.__data__[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]
        counts = [m.start() for m in COUNT_HOOK.finditer(code)]
        items = [m.start() for m in ITEM_HOOK.finditer(code)]
        assert len(counts) == 1 and len(items) == 1, (counts, items)
        self.count_fn = BASE + text.VirtualAddress + counts[0]
        self.item_fn = BASE + text.VirtualAddress + items[0]
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(BASE, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        uc.mem_write(BASE, bytes(pe.__data__[:0x1000]))
        for s in pe.sections:
            uc.mem_write(BASE + s.VirtualAddress, bytes(pe.__data__[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]))
        for base, size in ((HEAP, HEAPSZ), (STACK, STACKSZ), (SENT, 0x1000), (TEB, 0x1000), (GDT, 0x1000)):
            uc.mem_map(base, size)
        uc.mem_write(SENT, b"\xC3" * 0x1000)

        def entry(b, lim, acc, fl):
            return ((lim & 0xFFFF) | ((b & 0xFFFFFF) << 16) | (acc << 40) | (((lim >> 16) & 0xF) << 48) | (fl << 52)
                    | (((b >> 24) & 0xFF) << 56))
        uc.mem_write(GDT + 8, struct.pack("<Q", entry(0, 0xFFFFF, 0x9B, 0xC)))
        uc.mem_write(GDT + 16, struct.pack("<Q", entry(0, 0xFFFFF, 0x93, 0xC)))
        uc.mem_write(GDT + 24, struct.pack("<Q", entry(TEB, 0xFFF, 0x93, 0x4)))
        uc.reg_write(X.UC_X86_REG_GDTR, (0, GDT, 0xFF, 0))
        for reg, sel in ((X.UC_X86_REG_CS, 8), (X.UC_X86_REG_DS, 16), (X.UC_X86_REG_ES, 16), (X.UC_X86_REG_SS, 16),
                         (X.UC_X86_REG_FS, 24)):
            uc.reg_write(reg, sel)
        uc.mem_write(TEB, struct.pack("<I", 0xFFFFFFFF))
        # A stand-in CInventoryManager: the hooks and the paths run here read only its outfit pick fields.
        self.inventory = HEAP + 0x1000
        self.set_next_pick(0x7FFFFFFF)

    def has(self, section: bytes) -> bool:
        return section in self.sections

    def set_byte(self, section: bytes, value: int) -> None:
        s = self.sections[section]
        assert s.Misc_VirtualSize == 1
        self.uc.mem_write(BASE + s.VirtualAddress, bytes([value]))

    def set_next_pick(self, value: int) -> None:
        self.uc.mem_write(self.inventory + NEXT_PICK, struct.pack("<I", value & 0xFFFFFFFF))

    def _call(self, addr, args):
        X = self.X
        sp = STACK + STACKSZ - 0x100
        for a in reversed(args):
            sp -= 4
            self.uc.mem_write(sp, struct.pack("<I", a & 0xFFFFFFFF))
        sp -= 4
        self.uc.mem_write(sp, struct.pack("<I", SENT))
        self.uc.reg_write(X.UC_X86_REG_ESP, sp)
        self.uc.reg_write(X.UC_X86_REG_EBP, 0)
        self.uc.reg_write(X.UC_X86_REG_ECX, self.inventory)
        self.uc.emu_start(addr, SENT, count=5_000_000)
        assert self.uc.reg_read(X.UC_X86_REG_ESP) == sp + 4 + 4 * len(args), "not a thiscall return"
        return struct.unpack("<i", struct.pack("<I", self.uc.reg_read(X.UC_X86_REG_EAX)))[0]

    def page(self, category: int) -> list[int]:
        count = self._call(self.count_fn, (category,))
        return [self._call(self.item_fn, (category, i)) for i in range(count)]


def _exe(path, label):
    if not path or not Path(path).is_file():
        pytest.skip(f"{label} is not set to an executable built from this branch")
    exe = Exe(path)
    if not (exe.has(b".vf2free") and exe.has(b".vf2clth")):
        pytest.skip(f"{label} has no .vf2free / .vf2clth byte: it was not built from this branch")
    return exe


@pytest.fixture(scope="module")
def cheat():
    return _exe(CHEAT_EXE, "VF2_GATES_CHEAT_EXE")


@pytest.fixture(scope="module")
def nocheat():
    return _exe(NOCHEAT_EXE, "VF2_GATES_NOCHEAT_EXE")


# ------------------------------------------------------------------ Free and Guaranteed Cheats
def test_the_three_rows_are_listed_only_with_the_byte(cheat):
    cheat.set_byte(b".vf2free", 1)
    on = cheat.page(SPECIAL_UPGRADES)
    cheat.set_byte(b".vf2free", 0)
    off = cheat.page(SPECIAL_UPGRADES)
    contract = cheat.manifest["FreeGuaranteedCheats"]
    assert len(on) == contract["special_upgrades_rows_flag_on"] == 6 + 4 + 43
    assert len(off) == contract["special_upgrades_rows_flag_off"] == len(on) - 3
    assert all(row in on for row in FREE_ROWS) and not any(row in off for row in FREE_ROWS)
    assert off == [row for row in on if row not in FREE_ROWS], "every other row, in the same order"
    assert on[:10] == [0x111, 0x112, 0x113, 0x115, 0x116, 0x114, 0x117, 0x118, 0x119, 0x11A]
    # Every other Cheat Upgrades row is still there.
    for row in (0x11B, 0x11D, 0x123, 0x12B, 0x137, 0x13B, 0x153, 0x157):
        assert row in off
    # Out of range answers 0 rather than reading past the list.
    assert cheat._call(cheat.item_fn, (SPECIAL_UPGRADES, len(off))) == 0
    # Any byte but 1 is off.
    cheat.set_byte(b".vf2free", 2)
    assert cheat.page(SPECIAL_UPGRADES) == off
    cheat.set_byte(b".vf2free", 0)


def test_other_pages_ignore_the_free_byte(cheat):
    pages = {}
    for value in (0, 1):
        cheat.set_byte(b".vf2free", value)
        pages[value] = cheat.page(HOUSE_RENOVATIONS)
    cheat.set_byte(b".vf2free", 0)
    assert pages[0] == pages[1] and len(pages[0]) == 30


def test_without_cheat_upgrades_the_byte_changes_nothing(nocheat):
    pages = {}
    for value in (0, 1):
        nocheat.set_byte(b".vf2free", value)
        pages[value] = nocheat.page(SPECIAL_UPGRADES)
    nocheat.set_byte(b".vf2free", 0)
    assert pages[0] == pages[1] == [0x111, 0x112, 0x113, 0x115, 0x116, 0x114, 0x117, 0x118, 0x119, 0x11A]
    assert nocheat.manifest["FreeGuaranteedCheats"]["rows_listed_in_this_variant"] == 0


# ------------------------------------------------------------------ both pages' row counts, with and without cheats
@pytest.mark.parametrize("which, special, renovations", [("cheat", 53, 30), ("nocheat", 10, 30)])
def test_special_upgrades_and_house_renovations_have_their_own_counts(which, special, renovations, request):
    """B205 and earlier, without Cheat Upgrades: Special Upgrades 30 (20 rows past gServicesList) and House
    Renovations 10 of 30, because the renovation count patch matched the Special Upgrades case's bytes."""
    exe = request.getfixturevalue(which)
    exe.set_byte(b".vf2free", 1)
    rows = exe.page(SPECIAL_UPGRADES)
    assert len(rows) == special == exe.manifest["VisibleSpecialUpgrades"]["new_count"]
    assert len(set(rows)) == len(rows), "no row twice"
    assert set(rows) <= set(range(0x111, 0x15A)), "every row is a Special Upgrade"
    exe.set_byte(b".vf2free", 0)
    assert len(exe.page(HOUSE_RENOVATIONS)) == renovations == exe.manifest["HouseRenovations"]["new_count"]


def test_the_renovation_anchors_match_exactly_once_for_either_special_upgrades_count():
    """The bytes the renovation patch searches depend only on the Special Upgrades count before it, which is 10
    (no Cheat Upgrades) or 53 (Cheat Upgrades) in all 32 variants: each anchored pattern matches exactly once,
    at the House Renovations case, in both; the old bare patterns matched the Special Upgrades case at 10."""
    import patch_mobile_furniture_pack as P
    if not (P.SRC_OBJS / "InventoryManager.obj").is_file():
        pytest.skip("the desktop object files are not present")
    for special in (10, 53):
        obj = P.CoffObject(P.SRC_OBJS / "InventoryManager.obj")
        count = obj.symbol(P.GET_CATEGORY_ITEM_COUNT)
        item = obj.symbol(P.GET_CATEGORY_ITEM)
        count_start = obj.section(count.section).raw_ptr + count.value
        item_start = obj.section(item.section).raw_ptr + item.value
        # What patch_visible_special_upgrades writes first.
        obj.buf[count_start + 0x19:count_start + 0x1E] = b"\xB8" + struct.pack("<I", special)
        obj.buf[item_start + 0x1D:item_start + 0x20] = b"\x83\xFE" + bytes([special - 1])
        count_body = bytes(obj.buf[count_start:count_start + obj.section(count.section).raw_size - count.value])
        item_body = bytes(obj.buf[item_start:item_start + obj.section(item.section).raw_size - item.value])
        anchored_count = [m.start() + 5 for m in re.finditer(re.escape(
            b"\x5E\x5D\xC2\x04\x00\xB8\x0A\x00\x00\x00\x5E\x5D\xC2\x04\x00"), count_body)]
        anchored_bound = [m.start() for m in re.finditer(re.escape(b"\x83\xFE\x09\x77"), item_body)]
        assert anchored_count == [0xD6] and anchored_bound == [0x3E2], special
        bare_count = count_body.find(b"\xB8\x0A\x00\x00\x00\x5E\x5D\xC2\x04\x00")
        bare_bound = item_body.find(b"\x83\xFE\x09")
        assert (bare_count, bare_bound) == ((0x19, 0x1D) if special == 10 else (0xD6, 0x3E2)), special
    source = Path(P.__file__).read_text(encoding="utf-8")
    assert 'bounds_pattern = b"\\x83\\xFE\\x09\\x77"' in source
    assert 'count_pattern = b"\\x5E\\x5D\\xC2\\x04\\x00\\xB8\\x0A' in source


# ------------------------------------------------------------------ the content stays with both cheats off
@pytest.mark.parametrize("which", ["cheat", "nocheat"])
def test_renovations_and_holiday_outfits_are_there_with_both_cheat_bytes_off(which, request):
    exe = request.getfixturevalue(which)
    exe.set_byte(b".vf2free", 0)
    exe.set_byte(b".vf2clth", 0)
    renovations = exe.page(HOUSE_RENOVATIONS)
    contract = exe.manifest["HouseRenovations"]
    assert len(renovations) == contract["new_count"] == 30
    assert sorted(renovations) == sorted(int(x, 16) for x in contract["display_order"])
    for row in contract["added_items"] + contract["ai_bathroom2_items"]:
        assert int(row["item_id"], 16) in renovations, row["name"]
    # The holiday outfits and every hairstyle are still sold: all of them with the byte, in the rotation without.
    exe.set_byte(b".vf2clth", 1)
    everything = exe.page(CLOTHING)
    exe.set_byte(b".vf2clth", 0)
    assert HOLIDAY_POOL <= set(everything) and HEAD_POOL <= set(everything)
    seen = set()
    for pick in range(400):
        exe.set_next_pick(1000 + pick * 14400)
        seen |= set(exe.page(CLOTHING)[6:])
    exe.set_next_pick(0x7FFFFFFF)
    assert seen == HOLIDAY_POOL | HEAD_POOL, "every hairstyle and holiday outfit comes round"


def test_no_content_setting_needs_cheat_upgrades():
    import export_offline_patch_bundle as X
    for setting in ("mobile_renovations", "ai_generated_bathroom2_renovations", "holiday_furniture",
                    "holiday_outfits", "holiday_ornaments_collection", "outfit_store_expansion", "mobile_purchases",
                    "time_controls", "free_guaranteed_cheats", "all_outfits_hairstyles"):
        assert "cheat_upgrades" not in X.asset_requires_for_setting(setting), setting
    # The one setting that does: No AI Icons only reskins Cheat Upgrades rows.
    assert X.asset_requires_for_setting("no_ai_icons") == ["core_executable", "cheat_upgrades", "no_ai_icons"]


# ------------------------------------------------------------------ All outfits and hairstyles always for sale
def test_the_clothing_page_with_the_byte_is_every_row(cheat):
    cheat.set_byte(b".vf2clth", 1)
    rows = cheat.page(CLOTHING)
    cheat.set_byte(b".vf2clth", 0)
    contract = cheat.manifest["AllOutfitsForSale"]
    assert len(rows) == contract["rows_flag_on"] == 214
    assert rows[:6] == STOCK_SIX
    assert rows == STOCK_SIX + [int(x, 16) for x in cheat.manifest["InventoryManager"]["lists"]["gClothingList"]["added_ids"]]


def test_the_clothing_page_without_the_byte_is_the_stock_six_and_six_rotating_rows(cheat):
    cheat.set_byte(b".vf2clth", 0)
    cheat.set_next_pick(5000)
    first = cheat.page(CLOTHING)
    assert len(first) == cheat.manifest["AllOutfitsForSale"]["rows_flag_off"] == 12
    assert first[:6] == STOCK_SIX
    extras = first[6:]
    assert len(set(extras)) == 6 and set(extras) <= HEAD_POOL | HOLIDAY_POOL
    # The same pick time draws the same rows (nothing random between draws, nothing saved) ...
    assert cheat.page(CLOTHING) == first
    assert cheat._call(cheat.item_fn, (CLOTHING, 12)) == 0
    # ... and a new pick time (every 4 game hours, a new family, R) draws new ones.
    cheat.set_next_pick(5000 + 14400)
    second = cheat.page(CLOTHING)
    assert second[:6] == STOCK_SIX and second[6:] != extras
    cheat.set_next_pick(0x7FFFFFFF)


def test_the_free_byte_and_the_outfit_byte_are_independent(cheat):
    cheat.set_byte(b".vf2free", 1)
    cheat.set_byte(b".vf2clth", 0)
    assert len(cheat.page(CLOTHING)) == 12
    assert len(cheat.page(SPECIAL_UPGRADES)) == 53
    cheat.set_byte(b".vf2free", 0)
    cheat.set_byte(b".vf2clth", 1)
    assert len(cheat.page(CLOTHING)) == 214
    assert len(cheat.page(SPECIAL_UPGRADES)) == 50
    cheat.set_byte(b".vf2clth", 0)


def test_the_exporter_flips_exactly_those_bytes(cheat, nocheat):
    import pefile
    import export_offline_patch_bundle as X
    for exe in (cheat, nocheat):
        for fn, sid, sec in ((X.free_guaranteed_cheats_post_asset_patches, "free_guaranteed_cheats", b".vf2free"),
                             (X.all_outfits_post_asset_patches, "all_outfits_hairstyles", b".vf2clth")):
            records = fn([exe.path], output_exe_name="Out.exe", build_manifest_data=exe.manifest)
            assert len(records) == 1 and records[0]["requires"] == ["core_executable", sid]
            variant = records[0]["variants"][0]
            pe = pefile.PE(str(exe.path), fast_load=True)
            flag = [s for s in pe.sections if s.Name.rstrip(b"\0") == sec][0]
            assert int(variant["offset"], 16) == flag.PointerToRawData
            assert variant["expected_asset_bytes"] == "00" and variant["replacement_bytes"] == "01"
