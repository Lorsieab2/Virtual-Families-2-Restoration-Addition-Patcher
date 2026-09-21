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
tests the drop point against those items' fmap OBJECT cells -- the same geometry
the content map uses -- baked at build time from the maps as shipped. The sprite
is never consulted, so it stays fully transparent. The dispatcher unit declares
the table `extern`; sync_behavior_assets appends the definition once the maps
exist as written (so the spa lounger's widened target is included).

WHAT IS NOT TESTED HERE, ON PURPOSE. There is no Python re-implementation of the
cell arithmetic asserting the C++ "would" resolve a point. A model written from
the same assumption as the code agrees with itself and proves nothing about the
binary (the round-trip trap). The semantics that matter are pinned as literal
source properties below -- the negative-offset guard, the mirror test, the
nearest-centre tiebreak -- and the runtime behaviour is the owner's playtest.
"""
import os
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402

ROUTED_INVISIBLE = {0x328, 0x329, 0x32A, 0x32B, 0x32F, 0x331}
VISIBLE_SPA_LOUNGER = 0x330


def _source():
    return GEN.read_text(encoding="utf-8")


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


def _build_assets():
    """An Assets dir holding the routed items' fmaps under their OWN names.

    That is what sync_behavior_assets writes and what the bake reads at its
    real call site; the release payload renames some of them on export, so it
    is deliberately not used here.
    """
    candidates = []
    env = os.environ.get("VF2_PATCH_OUT")
    if env:
        candidates.append(pathlib.Path(env) / "Assets")
    candidates.append(patcher.OUT / "Assets")
    matrix = sorted(
        (ROOT / "outputs").glob("VF2-B*-matrix-final_all_enabled/Assets"),
        key=lambda p: p.stat().st_mtime, reverse=True)
    candidates.extend(matrix)
    needed = [f"{n}.png.fmap" for n in patcher.TRANSPARENT_DROP_FOOTPRINT_ITEMS]
    for assets in candidates:
        if all((assets / n).is_file() for n in needed):
            return assets, None
    return None, ("no build Assets dir holds all of %s under their own names; "
                  "run the generator first" % ", ".join(needed))


def _parse_table(cpp):
    masks = {int(m.group(1), 16): m.group(2).split(",")
             for m in re.finditer(r"kVF2TransparentMask_([0-9A-F]+)\[\d+\] = \{([01,]+)\};", cpp)}
    entries = {int(e[0], 16): tuple(int(x) for x in e[1:])
               for e in re.findall(r"\{ (0x[0-9a-f]+), (\d+), (\d+), (\d+), (\d+), kVF2TransparentMask_", cpp)}
    return masks, entries


class TheDispatcherTemplate(unittest.TestCase):
    """T1: the emission template carries every piece of the fallback."""

    def setUp(self):
        self.src = _source()

    def test_the_fallback_is_defined_and_hooked_after_the_stock_resolver(self):
        self.assertIn("static int VF2TransparentFurnitureItemAtPoint(ldwPoint point)", self.src)
        hook = "if (candidate < 0) candidate = VF2TransparentFurnitureItemAtPoint(sample);"
        self.assertIn(hook, self.src)
        # The fallback runs only after the stock resolver returned nothing, and
        # before any route inspects the candidate.
        resolve = self.src.index("int candidate = VF2FurnitureItemAtPoint(sample);")
        self.assertLess(resolve, self.src.index(hook))
        self.assertLess(self.src.index(hook), self.src.index("__VF2_ADDED_FURNITURE_DROP_DISPATCH__"))

    def test_the_table_is_declared_extern_in_the_dispatcher(self):
        # Declared here, DEFINED later by sync_behavior_assets: the two halves
        # of the emission-order inversion.
        self.assertIn("extern const VF2TransparentFootprint kVF2TransparentFootprints[];", self.src)
        self.assertIn("extern const int kVF2TransparentFootprintCount;", self.src)

    def test_the_cell_size_is_one_named_constant(self):
        # Single-sourced from the QAMF header (+8 == 16 on every shipped map);
        # if a playtest shows the zone scaled wrong this is the number to change.
        self.assertIn("static const int kVF2FmapCellPx = 16;", self.src)

    def test_a_point_left_of_or_above_the_origin_is_outside(self):
        # C division truncates toward zero, so -5 / 16 reads as cell 0; the
        # sign must be tested before dividing or the fallback claims a strip
        # outside every item.
        self.assertIn("if (dx < 0 || dy < 0) continue;", self.src)

    def test_the_footprint_is_tested_mirrored_too(self):
        # Orientation is not decoded; a flipped placement is caught whichever
        # way the engine mirrors it.
        self.assertIn("int mx = fp->cols - 1 - cx;", self.src)
        self.assertIn("bool mirrorHit = fp->mask[cy * fp->cols + mx] != 0;", self.src)

    def test_the_nearest_footprint_centre_wins(self):
        # Keeps the mirror's phantom side from stealing a drop meant for a
        # neighbouring transparent item.
        self.assertIn("if (bestItem < 0 || dist < bestDist) {", self.src)


class TheBakedTable(unittest.TestCase):
    """T2: the masks baked from the maps as written are the right shapes."""

    def setUp(self):
        self.assets, reason = _build_assets()
        if reason:
            self.skipTest(reason)
        self.cpp = patcher.transparent_footprint_table_cpp(self.assets)
        self.masks, self.entries = _parse_table(self.cpp)

    def test_every_routed_invisible_item_has_a_footprint(self):
        self.assertEqual(set(self.entries), ROUTED_INVISIBLE)
        self.assertIn("kVF2TransparentFootprintCount = 6;", self.cpp)

    def test_the_spa_lounger_is_baked_from_the_written_map_widening_included(self):
        # The plain lounger and the spa lounger borrow the SAME donor; the spa
        # lounger's map is then widened by one cell. More solid cells here is
        # the proof the bake read the WRITTEN map, not the donor source -- bake
        # from the source and this collapses to equality.
        solid = {i: m.count("1") for i, m in self.masks.items()}
        self.assertGreater(solid[0x32F], solid[0x32B])

    def test_a_known_object_cell_is_solid_and_a_corner_is_not(self):
        # Chaise_brown's object cells are an eleven-cell ragged diagonal that
        # includes (7,8) (measured in widen_spa_lounger_hotspot); (0,0) is empty.
        cols = self.entries[0x32B][0]
        self.assertEqual(cols, 19)
        lounger = self.masks[0x32B]
        self.assertEqual(lounger[8 * cols + 7], "1")
        self.assertEqual(lounger[0], "0")
        self.assertEqual(self.masks[0x32F][8 * cols + 7], "1")

    def test_each_mask_covers_its_whole_grid(self):
        for item, (cols, rows, cx, cy) in self.entries.items():
            with self.subTest(item=hex(item)):
                self.assertEqual(len(self.masks[item]), cols * rows)
                self.assertTrue(0 <= cx < cols and 0 <= cy < rows)

    def test_a_missing_map_fails_loudly_rather_than_baking_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(RuntimeError):
                patcher.transparent_footprint_table_cpp(pathlib.Path(empty))


class TheDriftGuard(unittest.TestCase):
    """T3: the baked set equals the invisible ids the emitted dispatcher routes.

    This is the test that matters for the future. A new invisible item routed
    through the dispatcher by id but left out of TRANSPARENT_DROP_FOOTPRINT_ITEMS
    would silently return to "transparent drops do nothing"; a footprint baked
    for an item the dispatcher never routes is dead weight. Both sets are
    derived independently -- one from the emitted C++, one from the generator's
    own item table -- so they cannot agree by construction.
    """

    def test_baked_footprints_match_the_routed_invisible_ids(self):
        unit, reason = _emitted_unit()
        if reason:
            self.skipTest(reason)
        # Every id the dispatcher routes: the literal `candidate == <id>`
        # compares, PLUS the ids VF2IsMobileChaise accepts, because the
        # Invisible Lounger is folded into that predicate rather than compared
        # by literal (see the "chaise" binding spec). Both are read from the
        # emitted C++, never from the generator's tables, so this set cannot
        # agree with the baked one by construction.
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
        baked = {patcher.furniture_item_id_by_name(n) for n in patcher.TRANSPARENT_DROP_FOOTPRINT_ITEMS}
        self.assertEqual(routed_invisible, baked)

    def test_the_visible_spa_lounger_is_routed_but_deliberately_not_baked(self):
        # 0x330 goes through the same alpha resolver, but its sprite is never
        # swapped for a transparent one, so it can never need the fallback.
        unit, reason = _emitted_unit()
        if reason:
            self.skipTest(reason)
        self.assertIn("candidate == 0x330", unit)
        baked = {patcher.furniture_item_id_by_name(n) for n in patcher.TRANSPARENT_DROP_FOOTPRINT_ITEMS}
        self.assertNotIn(VISIBLE_SPA_LOUNGER, baked)


class TheDefinitionReachesTheArtifact(unittest.TestCase):
    """T4: the appended DEFINITION is in the emitted unit, not just the extern.

    An unresolved extern compiles to a perfectly good object and only fails at
    link -- a fix that is silently absent while every compile test stays green.
    Only a full generator run (which invokes sync_behavior_assets after the
    dispatcher is emitted) can put the definition there, so this reads what
    that run actually wrote.
    """

    def test_the_table_definition_and_count_are_in_the_emitted_unit(self):
        unit, reason = _emitted_unit()
        if reason:
            self.skipTest(reason)
        self.assertIn("const VF2TransparentFootprint kVF2TransparentFootprints[] = {", unit)
        self.assertIn("kVF2TransparentFootprintCount = 6;", unit)
        masks, entries = _parse_table(unit)
        self.assertEqual(set(entries), ROUTED_INVISIBLE)
        self.assertEqual(len(masks), 6)
        # The extern precedes the definition: declared in the dispatcher,
        # appended afterwards -- the emission-order inversion, in the file.
        self.assertLess(unit.index("extern const VF2TransparentFootprint kVF2TransparentFootprints[];"),
                        unit.index("const VF2TransparentFootprint kVF2TransparentFootprints[] = {"))


if __name__ == "__main__":
    unittest.main()
