#!/usr/bin/env python3
"""A villager dropped on fully transparent invisible furniture still resolves (#369).

Owner: "find out why certain transparent furnitures don't work when villagers
are dropped on them: invisible patio table, picnic table, spa lounger, yoga
equipment."

WHY IT BROKE. VF2HandleDropOnMobileFurniture identifies the dropped-on item
with VF2FurnitureItemAtPoint, which wraps the stock
CFurnitureManager::PtOnFurniture: a bounding-box pass and then
ldwImageImpl::PixelIsVisible -- SDL_GetRGBA on the sprite's own pixels, a hit
only where alpha != 0. The Transparent Graphics setting swaps those items'
sprites for fully transparent ones, so every sampled pixel is alpha 0, the
resolver returns -1, every `candidate == <id>` route is skipped, and the drop
does nothing. Native items (pools, couches, the hammock) never touch that
resolver -- they go through the content map's fmap cells, pure geometry -- which
is why a transparent pool still works. The broken set is exactly the set of
items the patcher's dispatcher routes by id; the owner confirmed the partition
in play.

THE FIX. When the stock resolver returns -1, VF2TransparentFurnitureItemAtPoint
walks the placed furniture records and, for each routed item, asks the ENGINE'S
OWN content block: LookupFurnitureInfo(item).contentBlocks[orientation], the
block CFurnitureManager::LoadFmap built for the orientation the record holds
(authored, mirrored, second block, its mirror), anchored on the content map
exactly as CFurnitureManager::ApplyFmapContent anchors it -- at content cell
(pos - block.origin) / 8 in C integer division -- and reads the cell under the
drop point. No
table is baked, no mirror is guessed and no cell size is assumed: the fallback
agrees with the content map by construction.

SUPERSEDED, RECORDED AS WRONG. The first draft baked each item's object cells
into a table and re-derived the placement at 16 pixels per cell (the QAMF +8
field, which is the OFFSET of the first block and only happens to be 16), with
no origin subtracted and orientation unioned with a mirror guess. Review caught
all three. The tests below pin the constants against the stock DISASSEMBLY, a
source the template cannot agree with by construction.

WHAT IS NOT TESTED HERE, ON PURPOSE. There is no Python model of the fallback
asserting it "would" resolve a point: a model written from the same reading as
the code agrees with itself and proves nothing about the binary (the round-trip
trap). The runtime behaviour is the owner's playtest.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
STOCK_DISASM = ROOT / "work" / "FurnitureManager_current_disasm.txt"
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402

ROUTED_INVISIBLE = {0x328, 0x329, 0x32A, 0x32B, 0x32F, 0x331}
VISIBLE_SPA_LOUNGER = 0x330

FALLBACK = "static int VF2TransparentFurnitureItemAtPoint(ldwPoint point)"
HOOK = "if (candidate < 0) candidate = VF2TransparentFurnitureItemAtPoint(sample);"
CELL_IDIOM = "static int VF2ContentCell(int px) { return (px + ((px >> 31) & 7)) >> 3; }"


def _source():
    return GEN.read_text(encoding="utf-8")


def _fallback_body(text):
    start = text.index(FALLBACK)
    return text[start:text.index("\n}\n", start)]


def _emitted_unit():
    """The dispatcher unit a full generator run wrote, or None.

    Absent means the generator has not been run in this checkout -- a missing
    prerequisite, so callers skip and name it. STALE is different: a unit older
    than the generator describes code that is no longer in the repository, and
    a green check against it proves nothing, so callers FAIL rather than skip
    (the discipline test_generated_cpp_compiles.py already enforces).
    """
    path = patcher.PATCHED / "vf2_mobile_furniture_behaviors.cpp"
    if not path.is_file():
        return None, "work/patched_mobile_furniture_pack_objs/vf2_mobile_furniture_behaviors.cpp is absent; run the generator first"
    if path.stat().st_mtime < GEN.stat().st_mtime:
        raise AssertionError(
            "the emitted dispatcher unit is OLDER than the generator, so it does "
            "not contain the current emission; re-run the generator before "
            "trusting this suite")
    return path.read_text(encoding="ascii"), None


def _stock_function(name):
    """The dumpbin listing of one CFurnitureManager routine from the stock object.

    The header line, not a `call` to the symbol from another routine: dumpbin
    prints a function as its decorated name at column 0 followed by the
    undecorated form in parentheses.
    """
    text = STOCK_DISASM.read_text(encoding="utf-8", errors="replace")
    header = re.search("^" + re.escape(name) + r" \(", text, re.M)
    if header is None:
        raise AssertionError(f"{name} has no function header in {STOCK_DISASM.name}")
    return text[header.start():text.index("\nRELOCATIONS", header.start())]


class TheDispatcherTemplate(unittest.TestCase):
    """T1: the emission template carries every piece of the fallback."""

    def setUp(self):
        self.src = _source()
        self.body = _fallback_body(self.src)

    def test_the_fallback_is_defined_and_hooked_after_the_stock_resolver(self):
        self.assertIn(FALLBACK, self.src)
        self.assertIn(HOOK, self.src)
        # The fallback runs only after the stock resolver returned nothing, and
        # before any route inspects the candidate.
        resolve = self.src.index("int candidate = VF2FurnitureItemAtPoint(sample);")
        self.assertLess(resolve, self.src.index(HOOK))
        self.assertLess(self.src.index(HOOK), self.src.index("__VF2_ADDED_FURNITURE_DROP_DISPATCH__"))

    def test_it_asks_the_engine_for_the_block_it_actually_placed(self):
        # Declared so the compiler mangles the call to the symbol the stock
        # FurnitureManager.obj already imports.
        self.assertIn("sFurnitureInfo &__cdecl LookupFurnitureInfo(EInventoryItem);", self.src)
        self.assertIn("sFurnitureInfo &info = LookupFurnitureInfo((EInventoryItem)itemId);", self.body)
        self.assertIn("const sContentBlock *block = info.contentBlocks[orientation];", self.body)
        # No block yet (LoadFmap has not run) or an orientation with no block:
        # the engine applied nothing, so nothing resolves.
        self.assertIn("if (!info.fmapHeader) continue;", self.body)
        self.assertIn("if (!block || block->cols <= 0 || block->rows <= 0) continue;", self.body)

    def test_the_placed_orientation_selects_the_block(self):
        # Read from the record, clamped exactly as ApplyFmapContent clamps it.
        self.assertIn("int orientation = *reinterpret_cast<int *>(record + 0x10);", self.body)
        self.assertIn("if (orientation < 0 || orientation >= 4) orientation = 0;", self.body)
        # The superseded union-with-mirror guess is gone.
        self.assertNotIn("mirrorHit", self.src)
        self.assertNotIn("kVF2TransparentFootprints", self.src)

    def test_the_block_is_anchored_as_the_engine_anchors_it(self):
        self.assertIn(CELL_IDIOM, self.src)
        self.assertIn("int anchorX = VF2ContentCell(*reinterpret_cast<int *>(record + 0x14) - block->originX);", self.body)
        self.assertIn("int anchorY = VF2ContentCell(*reinterpret_cast<int *>(record + 0x18) - block->originY);", self.body)
        self.assertIn("int cx = pointCellX - anchorX;", self.body)
        self.assertIn("if (cx < 0 || cy < 0 || cx >= block->cols || cy >= block->rows) continue;", self.body)
        # No second cell size anywhere in the template.
        self.assertNotIn("kVF2FmapCellPx", self.src)

    def test_the_object_is_decoded_as_get_object_decodes_it(self):
        self.assertIn("unsigned int object = (((cell >> 11) & 0x40000u) | (cell & 0x3F800u)) >> 11;", self.body)
        self.assertIn("if (object == 0) continue;", self.body)

    def test_the_cell_idiom_is_c_division_by_eight_truncating_toward_zero(self):
        # The idiom is the compiler's rendering of a signed `/ 8` (cdq / and
        # edx,7 / add / sar 3), which truncates toward zero: -5 is cell 0, as
        # the engine has it. Python's `//` floors, so the independent reference
        # is truncation written out; the two differ on every negative
        # non-multiple of 8, which is exactly where a floor would disagree with
        # the content map.
        def trunc8(v):
            return -((-v) // 8) if v < 0 else v // 8
        for px in list(range(-64, 65)) + [-2147483648, 2147483647, -9, -8, -7, -1]:
            self.assertEqual((px + ((px >> 31) & 7)) >> 3, trunc8(px), px)
        self.assertEqual((-5 + ((-5 >> 31) & 7)) >> 3, 0)

    def test_the_struct_shims_carry_the_engine_offsets(self):
        block = self.src[self.src.index("struct sContentBlock {"):]
        block = block[:block.index("};")]
        self.assertEqual(
            re.findall(r"^\s+(?:int|unsigned int) (\w+)", block, re.M),
            ["originX", "originY", "cols", "rows", "cells"])
        info = self.src[self.src.index("struct sFurnitureInfo {\n    char pad0[0x58];"):]
        info = info[:info.index("};")]
        self.assertIn("void *fmapHeader;", info)
        self.assertIn("sContentBlock *contentBlocks[4];", info)


class TheStockDisassemblyAgrees(unittest.TestCase):
    """T2: every offset the fallback uses is the one the stock code uses.

    The template and the dumpbin listing of CFurnitureManager::ApplyFmapContent
    are independent sources; agreement between them is evidence, agreement
    between the template and a model of the template is not.
    """

    def setUp(self):
        if not STOCK_DISASM.is_file():
            self.skipTest("work/FurnitureManager_current_disasm.txt is absent")
        self.apply = _stock_function(
            "?ApplyFmapContent@CFurnitureManager@@QAEXH@Z")
        self.load = _stock_function(
            "?LoadFmap@CFurnitureManager@@AAEXW4EInventoryItem@@_N@Z")

    def test_orientation_is_read_from_record_plus_0x10_and_clamped_to_four(self):
        # Records start at manager+0x1008, so +0x10 in the record is +0x1018.
        self.assertIn("mov         ecx,dword ptr [esi+1018h]", self.apply)
        self.assertIn("cmp         ecx,4", self.apply)
        self.assertIn("xor         ecx,ecx", self.apply)

    def test_the_block_table_sits_at_info_plus_0x5c_indexed_by_orientation(self):
        self.assertIn("mov         edx,dword ptr [eax+ecx*4+5Ch]", self.apply)
        # LoadFmap fills that table: header+[header+8] into +0x5C, its mirror
        # into +0x60, the second block into +0x64 and its mirror into +0x68.
        self.assertIn("mov         dword ptr [ebx+5Ch],ecx", self.load)
        self.assertIn("mov         dword ptr [ebx+60h],eax", self.load)
        self.assertIn("mov         dword ptr [ebx+64h],eax", self.load)
        self.assertIn("mov         dword ptr [ebx+68h],eax", self.load)
        # And the header pointer the fallback tests for null lives at +0x58.
        self.assertIn("mov         dword ptr [ebx+58h],eax", self.load)

    def test_the_origin_is_subtracted_from_the_placement_position(self):
        # y at record+0x18 (+0x1020) minus block+4; x at record+0x14 (+0x101C)
        # minus block+0 -- the anchoring the fallback repeats.
        self.assertIn("mov         eax,dword ptr [esi+1020h]", self.apply)
        self.assertIn("mov         ecx,dword ptr [esi+101Ch]", self.apply)
        self.assertIn("sub         eax,dword ptr [edx+4]", self.apply)
        self.assertIn("sub         ecx,dword ptr [edx]", self.apply)

    def test_only_a_flagged_record_is_applied(self):
        # Bit 0 of record+0x0C (+0x1014), the same placed flag the fallback tests.
        self.assertIn("test        byte ptr [eax+ecx+1014h],1", self.apply)


class TheEmittedUnit(unittest.TestCase):
    """T3: the unit a full generator run wrote carries the fallback, substituted."""

    def setUp(self):
        self.unit, reason = _emitted_unit()
        if reason:
            self.skipTest(reason)

    def test_the_item_list_is_substituted_from_the_item_table(self):
        self.assertNotIn("__VF2_TRANSPARENT_DROP_ITEMS__", self.unit)
        match = re.search(r"kVF2TransparentDropItems\[\] = \{ ([0-9a-fx, ]+) \};", self.unit)
        self.assertIsNotNone(match)
        emitted = {int(x, 16) for x in match.group(1).split(", ")}
        expected = {patcher.furniture_item_id_by_name(n) for n in patcher.TRANSPARENT_DROP_FOOTPRINT_ITEMS}
        self.assertEqual(emitted, expected)
        self.assertEqual(emitted, ROUTED_INVISIBLE)

    def test_the_fallback_and_hook_reach_the_unit(self):
        self.assertIn(FALLBACK, self.unit)
        self.assertIn(HOOK, self.unit)
        self.assertIn(CELL_IDIOM, self.unit)
        self.assertIn("sFurnitureInfo &__cdecl LookupFurnitureInfo(EInventoryItem);", self.unit)

    def test_the_superseded_appended_table_is_gone(self):
        # The earlier mechanism appended a baked table after emission; a unit
        # still carrying it was written by a stale generator.
        self.assertNotIn("kVF2TransparentFootprints", self.unit)
        self.assertNotIn("kVF2TransparentMask_", self.unit)


class TheDriftGuard(unittest.TestCase):
    """T4: the fallback's item set equals the invisible ids the dispatcher routes.

    A new invisible item routed through the dispatcher by id but left out of
    TRANSPARENT_DROP_FOOTPRINT_ITEMS would silently return to "transparent drops
    do nothing"; an item in the list the dispatcher never routes would resolve
    to a candidate no route accepts. Both sets are derived independently -- one
    from the emitted C++, one from the generator's own item table -- so they
    cannot agree by construction.
    """

    def test_the_item_list_matches_the_routed_invisible_ids(self):
        unit, reason = _emitted_unit()
        if reason:
            self.skipTest(reason)
        # Every id the dispatcher routes: the literal `candidate == <id>`
        # compares, PLUS the ids VF2IsMobileChaise accepts, because the
        # Invisible Lounger is folded into that predicate rather than compared
        # by literal (see the "chaise" binding spec).
        routed = {int(x, 16) for x in re.findall(r"candidate == (0x[0-9A-Fa-f]+)", unit)}
        chaise_start = unit.index("static bool VF2IsMobileChaise(int item)")
        chaise = unit[chaise_start:unit.index("\n}\n", chaise_start)]
        routed |= {int(x, 16) for x in re.findall(r"item == (0x[0-9A-Fa-f]+)", chaise)}
        span = re.search(r"item >= (0x[0-9A-Fa-f]+) && item <= (0x[0-9A-Fa-f]+)", chaise)
        if span:
            routed |= set(range(int(span.group(1), 16), int(span.group(2), 16) + 1))
        invisible_names = {it["item_id"]: it["name"]
                           for it in (patcher.INVISIBLE_OUTDOOR_ITEMS + patcher.INVISIBLE_TRANSPARENT_BASE_ITEMS)}
        routed_invisible = {i for i in routed if invisible_names.get(i, "").startswith("Invisible")}
        listed = {patcher.furniture_item_id_by_name(n) for n in patcher.TRANSPARENT_DROP_FOOTPRINT_ITEMS}
        self.assertEqual(routed_invisible, listed)

    def test_the_visible_spa_lounger_is_routed_but_deliberately_not_listed(self):
        # 0x330 goes through the same alpha resolver, but its sprite is never
        # swapped for a transparent one, so it can never need the fallback.
        unit, reason = _emitted_unit()
        if reason:
            self.skipTest(reason)
        self.assertIn("candidate == 0x330", unit)
        listed = {patcher.furniture_item_id_by_name(n) for n in patcher.TRANSPARENT_DROP_FOOTPRINT_ITEMS}
        self.assertNotIn(VISIBLE_SPA_LOUNGER, listed)


if __name__ == "__main__":
    unittest.main()
