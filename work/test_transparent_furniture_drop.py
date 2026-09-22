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
CONTENT_MAP_DISASM = ROOT / "work" / "ContentMap_current_disasm.txt"
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402

ROUTED_INVISIBLE = {0x328, 0x329, 0x32A, 0x32B, 0x32F, 0x331}
VISIBLE_SPA_LOUNGER = 0x330

FALLBACK = "static int VF2TransparentFurnitureSlotAtPoint(ldwPoint point)"
HOOK = "if (slot < 0) slot = VF2TransparentFurnitureSlotAtPoint(point);"
DROP_RESOLVE = "int candidate = VF2FurnitureItemAtSlot(VF2FurnitureSlotAtPointOrTransparent(sample));"
SLOT_UNDER = "    return VF2FurnitureSlotAtPointOrTransparent(sample);"
CELL_IDIOM = "static int VF2ContentCell(int px) { return (px + ((px >> 31) & 7)) >> 3; }"


def _source():
    return GEN.read_text(encoding="utf-8")


def _fallback_body(text):
    """The fallback's DEFINITION, not its forward declaration.

    The declaration ends in `;` and is what `index` finds first; slicing from
    it returns everything up to the next closing brace, which silently passes
    or fails tests against the wrong text.
    """
    start = text.index(FALLBACK + "\n{")
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
        if pathlib.Path(patcher.PATCHED).is_dir() and any(pathlib.Path(patcher.PATCHED).glob("*.cpp")):
            # The generator RAN -- other units are here -- and did not emit the
            # dispatcher. That is the fix being absent from the build, not a
            # missing prerequisite, and it fails.
            raise AssertionError(
                "the generator emitted other units but not "
                "vf2_mobile_furniture_behaviors.cpp; the transparent drop "
                "fallback is absent from this build")
        return None, "work/patched_mobile_furniture_pack_objs has no generated units; run the generator first"
    if path.stat().st_mtime < GEN.stat().st_mtime:
        raise AssertionError(
            "the emitted dispatcher unit is OLDER than the generator, so it does "
            "not contain the current emission; re-run the generator before "
            "trusting this suite")
    return path.read_text(encoding="ascii"), None


def _function_in(text, name):
    """One routine's listing from a dumpbin /disasm text.

    The header line, not a `call` to the symbol from another routine: dumpbin
    prints a function as its decorated name at column 0 followed by the
    undecorated form in parentheses.
    """
    header = re.search("^" + re.escape(name) + r" \(", text, re.M)
    if header is None:
        raise AssertionError(f"{name} has no function header in the listing")
    end = text.find("\nRELOCATIONS", header.start())
    return text[header.start():end if end >= 0 else len(text)]


def _stock_function(name):
    """The dumpbin listing of one CFurnitureManager routine from the stock object."""
    return _function_in(STOCK_DISASM.read_text(encoding="utf-8", errors="replace"), name)


def _stock_external_definitions():
    """Every symbol the PATCHED stock objects define as External.

    Read from the patcher's own output directory, because that is what the
    build links: patch_furniture_manager promotes itemInfo from Static to
    External there, and the unpatched object would wrongly report it as
    unreachable. Static definitions are deliberately excluded -- a Static
    definition is exactly what cannot satisfy another object's reference.
    """
    import subprocess
    from test_generated_cpp_compiles import _vcvars
    objs = sorted(pathlib.Path(patcher.PATCHED).glob("*.obj"))
    if not objs or _vcvars() is None:
        return None
    defined = set()
    for chunk in [objs[i:i + 24] for i in range(0, len(objs), 24)]:
        names = " ".join(f'"{o.name}"' for o in chunk)
        result = subprocess.run(
            f'"{_vcvars()}" >nul 2>&1 && cd /d "{pathlib.Path(patcher.PATCHED)}" && '
            f'dumpbin /nologo /symbols {names}',
            shell=True, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "External" in line and "UNDEF" not in line and "|" in line:
                defined.add(line.split("|", 1)[1].strip().split(" ", 1)[0])
    # The real link also takes the OTHER generated units, which define the
    # cross-unit helpers this one calls (VF2PingPongPlay, VF2HomeGymWorkout
    # and friends). They are .cpp here rather than .obj, so compile them the
    # way the build does and read their exports too -- otherwise every
    # legitimate cross-unit call reads as unresolvable.
    import tempfile
    sources = [p for p in sorted(pathlib.Path(patcher.PATCHED).glob("*.cpp"))]
    if sources:
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            for src in sources:
                (work / src.name).write_bytes(src.read_bytes())
            names = " ".join(f'"{s.name}"' for s in sources)
            subprocess.run(
                f'"{_vcvars()}" >nul 2>&1 && cd /d "{work}" && cl /c /EHsc /nologo {names}',
                shell=True, capture_output=True, text=True)
            built = sorted(work.glob("*.obj"))
            for chunk in [built[i:i + 24] for i in range(0, len(built), 24)]:
                objnames = " ".join(f'"{o.name}"' for o in chunk)
                result = subprocess.run(
                    f'"{_vcvars()}" >nul 2>&1 && cd /d "{work}" && '
                    f'dumpbin /nologo /symbols {objnames}',
                    shell=True, capture_output=True, text=True)
                for line in result.stdout.splitlines():
                    if "External" in line and "UNDEF" not in line and "|" in line:
                        defined.add(line.split("|", 1)[1].strip().split(" ", 1)[0])
    return defined


def _build_assets():
    """An Assets dir holding the routed items' fmaps under their OWN names."""
    import os
    candidates = []
    env = os.environ.get("VF2_PATCH_OUT")
    if env:
        candidates.append(pathlib.Path(env) / "Assets")
    candidates.append(patcher.OUT / "Assets")
    needed = [f"{n}.png.fmap" for n in patcher.TRANSPARENT_DROP_FOOTPRINT_ITEMS]
    for assets in candidates:
        if all((assets / n).is_file() for n in needed):
            return assets, None
    return None, "no build Assets dir holds the routed items' maps under their own names; run the generator first"


class TheDispatcherTemplate(unittest.TestCase):
    """T1: the emission template carries every piece of the fallback."""

    def setUp(self):
        self.src = _source()
        self.body = _fallback_body(self.src)

    def test_the_fallback_is_defined_and_hooked_after_the_stock_resolver(self):
        self.assertIn(FALLBACK, self.src)
        # One choke point: the stock slot resolver first, the geometry
        # fallback only when it found nothing.
        chokepoint = self.src[self.src.index("static int VF2FurnitureSlotAtPointOrTransparent(ldwPoint point)"):]
        chokepoint = chokepoint[:chokepoint.index("\n}\n")]
        self.assertIn("int slot = VF2FurnitureSlotAtPoint(point);", chokepoint)
        self.assertIn(HOOK, chokepoint)

    def test_every_consumer_of_a_point_goes_through_the_choke_point(self):
        # The DROP resolves its item through the recovered slot, and the spa's
        # own probe (VF2FurnitureSlotUnderVillager, which VF2SpaOccupantIndex
        # calls for the dropped villager AND each candidate occupant) shares
        # it. Resolving only the dropped item would leave a treatment on a
        # transparent lounger broken: loungerSlot would still be -1 and the
        # occupant scan would reject every match. Caught in review.
        self.assertIn(DROP_RESOLVE, self.src)
        self.assertIn(SLOT_UNDER, self.src)
        # The superseded item-level entry point is gone entirely.
        self.assertNotIn("VF2TransparentFurnitureItemAtPoint", self.src)
        # Nothing reaches the alpha-only slot resolver for a drop any more.
        self.assertNotIn("int candidate = VF2FurnitureItemAtPoint(sample);", self.src)
        self.assertLess(self.src.index(DROP_RESOLVE),
                        self.src.index("__VF2_ADDED_FURNITURE_DROP_DISPATCH__"))

    def test_the_fallback_returns_a_slot_not_an_item(self):
        # An item id cannot tell two copies of the same lounger apart, which
        # is exactly what the spa handler needs.
        self.assertIn("hit = slot;", self.body)
        self.assertNotIn("hit = itemId;", self.body)

    def test_it_asks_the_engine_for_the_block_it_actually_placed(self):
        # itemInfo, not the Static LookupFurnitureInfo: the array's storage
        # class is promoted to External by patch_furniture_manager, so a
        # generated object can link against it. The declaration's element
        # type must be named sFurnitureInfo or the mangled name does not match.
        self.assertIn("extern sFurnitureInfo itemInfo[];", self.src)
        # Not called from the fallback: it is Static in the stock object.
        # Scoped to the fallback body -- the generator mentions the name
        # elsewhere (in disassembly notes and other units' comments), and a
        # whole-file search would fail on those.
        self.assertNotIn("LookupFurnitureInfo", self.body)
        self.assertIn("sFurnitureInfo *info = VF2FurnitureInfoForItem(itemId);", self.body)
        self.assertIn("const sContentBlock *block = info->contentBlocks[orientation];", self.body)
        # No record, no block yet (LoadFmap has not run), or an orientation
        # with no block: the engine applied nothing, so nothing resolves.
        self.assertIn("if (!info || !info->fmapHeader) continue;", self.body)
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

    def test_a_visible_sprite_keeps_its_stock_behaviour(self):
        """The fallback fires only where the sprite really is blank.

        Both graphics packs are player-installed assets, so the executable
        cannot read the setting -- it has to ask the sprite. Without this the
        fallback would fire in the transparent gutters of the Base (visible)
        sprites, which are only 45-64% opaque, and change behaviour for
        players who never enabled Transparent Graphics. Caught in review.
        """
        self.assertIn("static bool VF2SpriteIsBlankAround(sFurnitureInfo *info, int localX, int localY)", self.src)
        self.assertIn("if (grid->PixelIsVisible(localX + dx, localY + dy)) return false;", self.src)
        # Applied in the fallback, and the drop is rejected when it fails.
        self.assertIn("if (!VF2SpriteIsBlankAround(info,", self.body)
        # The declaration must match the stock export's signature or the
        # mangled name will not resolve at link.
        self.assertIn("bool PixelIsVisible(int x, int y);", self.src)

    def test_occupancy_is_the_hit_not_the_object_bits(self):
        # ApplyContentBlock writes every nonzero cell and skips the zeros; the
        # object bits mark a few hotspot cells per map (see TheShippedMaps) and
        # a gate on them leaves most of a transparent item dead to a drop --
        # the second draft's defect, caught in review.
        self.assertIn("if (block->cells[cy * block->cols + cx] == 0) continue;", self.body)
        self.assertNotIn("object == 0", self.body)
        self.assertNotIn("0x3F800", self.body)

    def test_a_later_placement_owns_an_overlapped_cell(self):
        # ApplyFmapContent applies slots in order and a later block overwrites
        # an earlier one; the fallback keeps the last hit for the same reason.
        self.assertIn("int hit = -1;", self.body)
        self.assertIn("hit = slot;", self.body)

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
        # THIS unit's definition, anchored on its first member: the generator
        # emits a different sFurnitureInfo for vf2_special_upgrade_effects
        # (item/image/price/generationLock + pad to 0x6C). Separate
        # translation units, so both are legal, but a bare search for the
        # struct name finds whichever comes first in the generator.
        info = self.src[self.src.index("struct sFurnitureInfo {\n    int item;                         // +0x00"):]
        info = info[:info.index("};")]
        # item +0x00, image +0x04 (the EImage PtOnFurniture reads to get the
        # sprite grid), then padding to put fmapHeader at +0x58 and the block
        # table at +0x5C -- the offsets the stock code uses. The whole record
        # is 0x6C, the stride itemInfo[] is indexed by.
        self.assertIn("int image;", info)
        self.assertIn("char pad0[0x50];", info)
        self.assertIn("void *fmapHeader;", info)
        self.assertIn("sContentBlock *contentBlocks[4];", info)
        self.assertEqual(4 + 4 + 0x50 + 4 + 4 * 4, 0x6C)


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


class TheContentMapDisassemblyAgrees(unittest.TestCase):
    """T2b: the cell arithmetic and the occupancy rule are the content map's.

    work/ContentMap_current_disasm.txt is the dumpbin listing of the stock
    ContentMap.obj, checked in for this cross-check.
    """

    def setUp(self):
        if not CONTENT_MAP_DISASM.is_file():
            self.skipTest("work/ContentMap_current_disasm.txt is absent")
        text = CONTENT_MAP_DISASM.read_text(encoding="utf-8", errors="replace")
        self.apply = _function_in(text, "?ApplyContentBlock@CContentMap@@QAEPAUsContentBlock@@PAU2@UldwPoint@@_N@Z")
        self.get_object = _function_in(text, "?GetObject@CContentMap@@QAE?AW4EObject@1@PAUsContentBlock@@UldwPoint@@@Z")

    def test_a_world_pixel_becomes_a_cell_by_signed_division_by_eight(self):
        # cdq / and edx,7 / lea (add) / sar 3 in both routines: the idiom
        # VF2ContentCell spells out.
        for listing in (self.apply, self.get_object):
            self.assertIn("cdq", listing)
            self.assertIn("and         edx,7", listing)
            self.assertRegex(listing, r"sar         e[a-d]x,3")
        self.assertNotIn("sar         ebx,4", self.apply)

    def test_apply_content_block_writes_nonzero_cells_and_skips_zeros(self):
        # The occupancy rule: a zero cell is not applied to the map, every
        # other value is -- object bits or not.
        self.assertRegex(self.apply, r"cmp         dword ptr \[edi\],0\s*\n\s*[0-9A-F]+: [0-9A-F ]+\s+je ")


class TheShippedMaps(unittest.TestCase):
    """T2c: the maps carry occupied cells with NO object bits, in the majority.

    This is the evidence that an object gate is the wrong test. Read from the
    build's own Assets under the items' own names (the release payload renames
    some on export).
    """

    def setUp(self):
        self.assets, reason = _build_assets()
        if reason:
            self.skipTest(reason)

    @staticmethod
    def _grid(path):
        import struct
        data = path.read_bytes()
        cols, rows = struct.unpack_from("<ii", data, 24)
        cells = struct.unpack_from("<%dI" % (cols * rows), data, 32)
        return cols, rows, cells

    @staticmethod
    def _object(cell):
        # CContentMap::GetObject's decode, bits 11..17 and 29.
        return (((cell >> 11) & 0x40000) | (cell & 0x3F800)) >> 11

    def test_most_occupied_cells_carry_no_object(self):
        for name in patcher.TRANSPARENT_DROP_FOOTPRINT_ITEMS:
            with self.subTest(item=name):
                cols, rows, cells = self._grid(self.assets / f"{name}.png.fmap")
                occupied = [c for c in cells if c]
                with_object = [c for c in occupied if self._object(c)]
                self.assertGreater(len(occupied), 4 * len(with_object),
                                   f"{name}: {len(with_object)} object cells of {len(occupied)} occupied")

    def test_a_named_occupied_objectless_cell_on_each_map(self):
        # The known-bad case for an object gate, pinned by coordinate: an
        # occupied cell with no object bits, well inside the item.
        for name, (x, y) in {"InvisiblePicnicTable": (5, 0), "InvisiblePatioTable": (7, 1),
                             "InvisibleLounger": (2, 1), "InvisibleSpaLounger": (2, 1),
                             "InvisibleYogaEquipment": (3, 0), "InvisiblePingPongTable": (12, 0)}.items():
            with self.subTest(item=name, cell=(x, y)):
                cols, rows, cells = self._grid(self.assets / f"{name}.png.fmap")
                cell = cells[y * cols + x]
                self.assertNotEqual(cell, 0)
                self.assertEqual(self._object(cell), 0)


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
        self.assertIn("extern sFurnitureInfo itemInfo[];", self.unit)
        # The search bound is substituted, not left as a placeholder.
        self.assertNotIn("__VF2_FURNITURE_SEARCH_COUNT__", self.unit)
        self.assertRegex(self.unit, r"kVF2FurnitureRecordSearchCount = \d+;")

    def test_the_superseded_appended_table_is_gone(self):
        # The earlier mechanism appended a baked table after emission; a unit
        # still carrying it was written by a stale generator.
        self.assertNotIn("kVF2TransparentFootprints", self.unit)
        self.assertNotIn("kVF2TransparentMask_", self.unit)


class TheCompiledObject(unittest.TestCase):
    """T3b: the fallback and its call site are in the compiled OBJECT.

    AGENTS.md section 1: verify the shipped artifact, never the source. The
    emitted unit is compiled exactly as test_generated_cpp_compiles.py and the
    real build compile it, and the object is decoded with dumpbin: the drop
    handler must call the stock resolver and then the fallback, and the
    fallback must import LookupFurnitureInfo by the mangled name the stock
    FurnitureManager.obj already relocates against. A source that reads right
    but compiles to something else -- an inlined-away call, a mangling that
    names a symbol the linker will never see -- fails here and nowhere else.
    """

    STOCK_LOOKUP = "?LookupFurnitureInfo@@YAAAUsFurnitureInfo@@W4EInventoryItem@@@Z"

    @classmethod
    def setUpClass(cls):
        import subprocess
        import tempfile
        from test_generated_cpp_compiles import _vcvars
        cls.reason = None
        vcvars = _vcvars()
        if vcvars is None:
            cls.reason = "no Visual Studio toolchain on this machine"
            return
        unit, reason = _emitted_unit()
        if reason:
            cls.reason = reason
            return
        cls.work = tempfile.TemporaryDirectory()
        work = pathlib.Path(cls.work.name)
        (work / "vf2_mobile_furniture_behaviors.cpp").write_text(unit, encoding="ascii")
        result = subprocess.run(
            f'"{vcvars}" >nul 2>&1 && cd /d "{work}" && '
            'cl /c /EHsc /nologo vf2_mobile_furniture_behaviors.cpp && '
            'dumpbin /nologo /disasm vf2_mobile_furniture_behaviors.obj > disasm.txt && '
            'dumpbin /nologo /symbols vf2_mobile_furniture_behaviors.obj > symbols.txt',
            shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError("the emitted dispatcher did not compile or decode:\n"
                                 + (result.stdout or "") + (result.stderr or ""))
        cls.disasm = (work / "disasm.txt").read_text(encoding="utf-8", errors="replace")
        cls.symbols = (work / "symbols.txt").read_text(encoding="utf-8", errors="replace")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "work", None):
            cls.work.cleanup()

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def _listing(self, fragment):
        """One compiled routine, bounded by the NEXT routine's header.

        dumpbin does not separate functions with a blank line, so slicing to
        the next "\\n\\n" returns the rest of the object -- 472 KB of other
        functions, in which any call can be found. That made an earlier
        version of this check vacuous: a mutation that removed the call from
        the routine under test still passed, because the call existed
        somewhere downstream. Bound on the next header instead.
        """
        headers = [(m.start(), m.group(0)) for m in
                   re.finditer(r"^\?\S+ \([^\n]*\):\s*$", self.disasm, re.M)]
        self.assertTrue(headers, "the disassembly has no function headers")
        for i, (start, line) in enumerate(headers):
            if fragment in line:
                end = headers[i + 1][0] if i + 1 < len(headers) else len(self.disasm)
                return self.disasm[start:end]
        self.fail(f"no compiled routine named like {fragment}")

    def test_the_choke_point_calls_the_stock_resolver_then_the_fallback(self):
        choke = self._listing("VF2FurnitureSlotAtPointOrTransparent")
        calls = [m.group(1) for m in re.finditer(r"call\s+(\S+)", choke)]
        stock = [i for i, c in enumerate(calls) if "VF2FurnitureSlotAtPoint" in c and "Transparent" not in c]
        fallback = [i for i, c in enumerate(calls) if "VF2TransparentFurnitureSlotAtPoint" in c]
        self.assertTrue(stock, "the choke point does not call the stock slot resolver")
        self.assertTrue(fallback, "the choke point does not call the fallback -- the fix is not in the object")
        self.assertLess(stock[0], fallback[0], "the fallback is called before the stock resolver")

    def test_both_the_drop_and_the_spa_probe_reach_the_choke_point(self):
        # The two consumers that must recover on a transparent item: the drop
        # dispatcher, and the slot probe VF2SpaOccupantIndex uses for the
        # dropped villager and each candidate occupant.
        for caller in ("VF2HandleDropOnMobileFurniture@theMainScene",
                       "VF2FurnitureSlotUnderVillager"):
            with self.subTest(caller=caller):
                listing = self._listing(caller)
                self.assertRegex(listing, r"call\s+\S*VF2FurnitureSlotAtPointOrTransparent",
                                 f"{caller} does not reach the transparent-aware resolver")

    def test_the_fallback_reads_the_furniture_array_not_the_static_lookup(self):
        """Every external the fallback needs must be one the linker can supply.

        LookupFurnitureInfo is Static in FurnitureManager.obj, so a generated
        object cannot call it: that compiles cleanly and fails at LINK. An
        earlier draft did exactly that, and this suite did not catch it
        because it stopped at `cl /c`. itemInfo is the reachable one --
        patch_furniture_manager promotes its storage class to External.
        """
        fallback = self._listing("VF2FurnitureInfoForItem")
        self.assertIn("?itemInfo@@3PAUsFurnitureInfo@@A", fallback)
        # The static accessor is not referenced anywhere in this object.
        self.assertNotIn(self.STOCK_LOOKUP, self.disasm)
        self.assertNotIn(self.STOCK_LOOKUP, self.symbols)

    def test_every_undefined_external_is_one_the_stock_objects_export(self):
        """The link check, in symbol form: no UNDEF this build cannot satisfy.

        Each UNDEF External in the generated object must be defined -- and
        defined as External, not Static -- by some stock object, or the real
        link fails. A Static definition is the exact trap the previous draft
        fell into, and a name matched case-insensitively or by substring
        would hide it, so both sides are exact.
        """
        undefs = set(re.findall(r"UNDEF\s+\S+\s+\S*\s*External\s+\|\s+(\S+)", self.symbols))
        self.assertTrue(undefs, "the object declares no externals at all; the parse is wrong")
        exported = _stock_external_definitions()
        if exported is None:
            self.skipTest("no stock object directory to resolve externals against")
        # Compiler/CRT helpers are supplied by the toolchain, not the game.
        # @__security_check_cookie@4 is emitted by /GS and resolved from the
        # CRT at link; it is not a game symbol and never will be.
        unresolved = sorted(
            n for n in undefs
            if n not in exported
            and not n.startswith(("__", "@__", "_CIcos", "_CIsin", "_CIsqrt", "_ftol", "_alloca"))
            and not n.lstrip("_").startswith(("memset", "memcpy", "strncpy", "strncmp", "sprintf", "rand", "atoi"))
        )
        self.assertEqual(unresolved, [], f"these externals no stock object defines: {unresolved}")


class TheRealLink(unittest.TestCase):
    """T3c: the whole program LINKS with the fallback in it.

    The strongest available check short of playing the game, and the one that
    would have caught the defect this class was added for: calling a Static
    stock symbol compiles cleanly and only fails here. Symbol-level checks
    approximate this; link/@rsp IS it.

    Slow (about a minute, ~370 objects), so it is opt-in via VF2_LINK_TEST=1
    and run before a release. The release build links all 32 variants anyway,
    which is the real gate; this makes the failure reproducible in one step.
    """

    def test_the_patched_objects_link_into_an_executable(self):
        import os
        import subprocess
        import tempfile
        if os.environ.get("VF2_LINK_TEST") != "1":
            self.skipTest("set VF2_LINK_TEST=1 to run the full link (about a minute)")
        builder = ROOT / "work" / "build_b119.bat"
        if not builder.is_file():
            self.skipTest("work/build_b119.bat is absent")
        unit, reason = _emitted_unit()
        if reason:
            self.skipTest(reason)
        with tempfile.TemporaryDirectory() as out:
            env = dict(os.environ, VF2_BUILD_OUT=out, VF2_OUTPUT_EXE="VF2-linktest.exe")
            result = subprocess.run(f'"{builder}"', shell=True, cwd=str(ROOT),
                                    capture_output=True, text=True, env=env)
            exe = pathlib.Path(out) / "VF2-linktest.exe"
            if result.returncode != 0 or not exe.is_file():
                tail = ((result.stdout or "") + (result.stderr or "")).splitlines()
                errors = [l for l in tail if "error" in l.lower() or "unresolved" in l.lower()]
                self.fail("the patched objects do not link:\n  " + "\n  ".join(errors[:10] or tail[-10:]))
            self.assertGreater(exe.stat().st_size, 1_000_000)


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
