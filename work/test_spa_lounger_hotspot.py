"""The spa loungers get a wider drop target than the chaise they borrow.

THE REPORT: "the hotspot for the spa loungers are very small. they should be
widened a bit so it's easier to drop villagers on them. check both the normal
spa lounger and invisible spa lounger."

MEASURED FIRST: Chaise_brown.png.fmap is a 19x14 grid whose object cells are an
eleven-cell ragged diagonal. Both spa loungers borrow that map, and so do
ordinary chaises -- which is why the widening runs on the BORROWER'S OWN COPY
after copy_donor_fmap has written it out under the borrowing item's name. The
donor file is untouched and validate_mobile_chaise_pc_fmaps still holds.
"""

import pathlib
import re
import struct
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
SOURCE = GENERATOR.read_text(encoding="utf-8", errors="replace")

DONOR = (ROOT / "patcher_assets" / "optional_patches"
         / "mobile_furniture_behaviors" / "pc_fmaps" / "Chaise_brown.png.fmap")


def _object_cell_count(data):
    """How many cells carry the map's dominant nonzero value."""
    width, height = struct.unpack_from("<ii", data, 24)
    cells = struct.unpack_from("<%dI" % (width * height), data, 32)
    counts = {}
    for value in cells:
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return 0
    obj = max(counts, key=lambda v: counts[v])
    return counts[obj]


def widen(data):
    """The transform under test, applied to fmap bytes."""
    data = bytearray(data)
    width, height = struct.unpack_from("<ii", data, 24)
    cells = list(struct.unpack_from("<%dI" % (width * height), data, 32))
    counts = {}
    for value in cells:
        if value:
            counts[value] = counts.get(value, 0) + 1
    obj = max(counts, key=lambda v: counts[v])
    before = [i for i, v in enumerate(cells) if v == obj]
    grown = set(before)
    for index in before:
        x, y = index % width, index // width
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    grown.add(ny * width + nx)
    added = 0
    for index in sorted(grown):
        if cells[index] == 0:
            cells[index] = obj
            added += 1
    struct.pack_into("<%dI" % (width * height), data, 32, *cells)
    return width, height, obj, before, cells, added, bytes(data)


class TheWideningIsWiredUp(unittest.TestCase):
    def test_both_spa_loungers_are_named(self):
        m = re.search(r"SPA_LOUNGER_WIDENED_FMAPS = \((.*?)\)", SOURCE, re.S)
        self.assertIsNotNone(m, "SPA_LOUNGER_WIDENED_FMAPS is gone")
        block = m.group(1)
        self.assertIn("SpaLoungerStd.png.fmap", block)
        self.assertIn("InvisibleSpaLounger.png.fmap", block,
                      "the invisible spa lounger was asked for too")

    def test_the_widener_is_called(self):
        self.assertIn("widen_spa_lounger_hotspot(", SOURCE,
                      "the widener is defined but never invoked, so the "
                      "hotspot would ship unchanged")
        self.assertIn("spa_widened", SOURCE,
                      "the widener's results are not recorded anywhere")

    def test_it_runs_after_the_donor_copies(self):
        # Running before copy_donor_fmap would have the copy overwrite it.
        call = SOURCE.rindex("widen_spa_lounger_hotspot(")
        last_copy = SOURCE.rindex("copy_donor_fmap(target, donor,")
        self.assertGreater(
            call, last_copy,
            "the widening runs before the last donor copy, which would "
            "overwrite it")

    def test_no_ordinary_chaise_is_widened(self):
        m = re.search(r"SPA_LOUNGER_WIDENED_FMAPS = \((.*?)\)", SOURCE, re.S)
        block = m.group(1)
        for other in ("Chaise_brown.png.fmap", "Chaise_blue.png.fmap"):
            with self.subTest(fmap=other):
                self.assertNotIn(
                    other, block,
                    "%s is a shared donor map; widening it would change "
                    "ordinary chaises too" % other)


class TheProductionWidenerActuallyWidens(unittest.TestCase):
    """Exercise the REAL widener, not a reimplementation of it.

    Every other class here either searches the generator source for a function
    name or runs the local `widen()` copy below. Both still pass if the
    production `widen_spa_lounger_hotspot` returns without changing a byte --
    which is the failure mode most worth catching, because it ships a build
    where the hotspot was never widened and every test is green.

    So this stages a donor and a borrower in a temporary directory, calls the
    generator's own nested function through the module, and reads the bytes it
    wrote.
    """

    def setUp(self):
        if not DONOR.is_file():
            self.skipTest("donor fmap not present in this checkout")
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen", GENERATOR)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except SystemExit:
            pass
        except Exception as exc:  # pragma: no cover - environment dependent
            self.skipTest("generator not importable here: %s" % exc)
        self.gen = module

    def test_the_recorded_output_names_both_targets_and_their_growth(self):
        """The manifest record is the artifact-side evidence.

        A run that widened nothing records nothing, so an empty list here is a
        silent no-op made visible.
        """
        source = GENERATOR.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            '"spa_lounger_widened_hotspots": spa_widened', source,
            "the widening is not recorded in the build manifest, so a build "
            "that widened nothing cannot be told from one that did")
        # And the record must carry the counts, not just the names.
        self.assertIn('"widened_from"', source)
        self.assertIn('"widened_to"', source)

    def test_running_the_real_sync_widens_both_shipped_maps(self):
        """Call the PRODUCTION path and read the bytes it wrote.

        widen_spa_lounger_hotspot is nested inside sync_behavior_assets, so it
        cannot be invoked directly. Running the enclosing function is what
        makes this a check of the shipped behaviour rather than of a
        reimplementation: a widener that returns without changing a byte fails
        here and passes everything else in this file.
        """
        gen = self.gen
        manifest = {"items": []}
        try:
            gen.sync_behavior_assets(manifest)
        except Exception as exc:  # pragma: no cover - environment dependent
            self.skipTest("sync_behavior_assets needs build inputs here: %s"
                          % exc)

        record = manifest.get("behavior_assets", {}).get(
            "spa_lounger_widened_hotspots")
        self.assertIsNotNone(
            record,
            "sync_behavior_assets recorded no widening at all, so the "
            "production widener did nothing")
        widened = {row["target"]: row for row in record}
        for target in gen.SPA_LOUNGER_WIDENED_FMAPS:
            with self.subTest(target=target):
                self.assertIn(
                    target, widened,
                    "%s was not widened by the production path" % target)
                row = widened[target]
                self.assertGreater(
                    row["widened_to"], row["widened_from"],
                    "%s recorded a widening that grew nothing: %s"
                    % (target, row))

    def test_the_widened_bytes_are_on_disk_after_the_real_sync(self):
        """The manifest could be right while the file was never written."""
        gen = self.gen
        manifest = {"items": []}
        try:
            gen.sync_behavior_assets(manifest)
        except Exception as exc:  # pragma: no cover - environment dependent
            self.skipTest("sync_behavior_assets needs build inputs here: %s"
                          % exc)

        donor_cells = _object_cell_count(DONOR.read_bytes())
        assets = (ROOT / "patcher_assets" / "optional_patches"
                  / "mobile_furniture_behaviors" / "pc_fmaps")
        for target in gen.SPA_LOUNGER_WIDENED_FMAPS:
            path = assets / target
            with self.subTest(target=target):
                if not path.is_file():
                    self.skipTest("%s is not staged in this checkout" % target)
                shipped = _object_cell_count(path.read_bytes())
                self.assertGreater(
                    shipped, donor_cells,
                    "%s on disk has %d object cells, no more than the donor's "
                    "%d -- the widening did not reach the file"
                    % (target, shipped, donor_cells))

    def test_the_targets_and_donors_resolve_to_real_files(self):
        gen = self.gen
        for target in gen.SPA_LOUNGER_WIDENED_FMAPS:
            with self.subTest(target=target):
                donor = (gen.NEW_FURNITURE_FMAP_DONORS.get(target)
                         or gen.INVISIBLE_TRANSPARENT_FMAP_DONORS.get(target)
                         or gen.INVISIBLE_OUTDOOR_FMAP_DONORS.get(target))
                self.assertIsNotNone(
                    donor,
                    "%s has no donor, so the production widener returns "
                    "silently" % target)
                # The donor must exist as a real pc_fmap, or the widener's
                # `donor_path.is_file()` guard returns and nothing happens.
                src = (ROOT / "patcher_assets" / "optional_patches"
                       / "mobile_furniture_behaviors" / "pc_fmaps" / donor)
                self.assertTrue(
                    src.is_file(),
                    "%s names donor %s, which is not present as a pc_fmap; "
                    "the widener would return without widening"
                    % (target, donor))


class TheTransformIsSafe(unittest.TestCase):
    def setUp(self):
        if not DONOR.is_file():
            self.skipTest("donor fmap not present in this checkout")
        self.raw = DONOR.read_bytes()

    def test_it_actually_widens_the_real_map(self):
        w, h, obj, before, cells, added, _ = widen(self.raw)
        self.assertGreater(added, 0, "nothing was widened")
        self.assertGreaterEqual(
            len(before) + added, len(before) * 2,
            "the target barely grew; the report was that it is very small")

    def test_the_anchor_and_every_other_marker_survive(self):
        w, h, obj, before, cells, added, _ = widen(self.raw)
        orig = list(struct.unpack_from("<%dI" % (w * h), self.raw, 32))
        kept = {i: v for i, v in enumerate(orig) if v and v != obj}
        now = {i: v for i, v in enumerate(cells) if v and v != obj}
        self.assertEqual(kept, now,
                         "a non-object cell was overwritten; the anchor lives "
                         "in one of those and losing it breaks placement")

    def test_the_grid_and_header_do_not_move(self):
        w, h, _obj, _b, _c, _a, out = widen(self.raw)
        self.assertEqual(out[:32], self.raw[:32], "the header changed")
        self.assertEqual(len(out), len(self.raw), "the file size changed")
        self.assertEqual(struct.unpack_from("<ii", out, 24), (w, h))

    def test_no_new_cell_value_is_introduced(self):
        w, h, obj, _b, cells, _a, _o = widen(self.raw)
        orig = set(struct.unpack_from("<%dI" % (w * h), self.raw, 32))
        self.assertTrue(set(cells) <= orig,
                        "a cell value the map never used was introduced")

    def test_every_original_object_cell_is_still_set(self):
        w, h, obj, before, cells, _a, _o = widen(self.raw)
        for index in before:
            self.assertEqual(cells[index], obj,
                             "the widening removed an original object cell")

    def test_dilating_the_target_would_compound_across_builds(self):
        # This is why the real widener dilates from the DONOR's cells rather
        # than the target's. Measured on the real map, repeatedly dilating the
        # target gives 11 -> 33 -> 62 -> 92 -> 125 cells. These maps are
        # written into a tracked asset directory, so consecutive builds would
        # really keep growing the footprint.
        counts = []
        data = self.raw
        for _ in range(3):
            _w, _h, _o, before, _c, added, data = widen(data)
            counts.append(len(before))
        self.assertLess(
            counts[0], counts[1],
            "the transform is being applied to its own output without growing, "
            "so this test no longer demonstrates the hazard it documents")
        self.assertIn("IDEMPOTENT BY CONSTRUCTION", SOURCE,
                      "the widener no longer documents why it reads the donor")
        self.assertIn("donor_cells", SOURCE,
                      "the widener no longer dilates from the donor's cells, "
                      "so repeated builds would compound the footprint")


class TheDonorLookupResolves(unittest.TestCase):
    """A donor of None makes the widener return silently.

    The widener guards `if not donor: return`, which is correct -- but it means
    a lookup that fails produces no error, no widening, and a build that
    reports success. So resolve both targets for real.
    """

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen", GENERATOR)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except SystemExit:
            pass
        except Exception as exc:  # pragma: no cover - environment dependent
            self.skipTest("generator not importable here: %s" % exc)
        self.gen = module

    def test_every_widened_target_resolves_to_a_real_donor(self):
        gen = self.gen
        for target in gen.SPA_LOUNGER_WIDENED_FMAPS:
            with self.subTest(target=target):
                donor = (gen.NEW_FURNITURE_FMAP_DONORS.get(target)
                         or gen.INVISIBLE_TRANSPARENT_FMAP_DONORS.get(target)
                         or gen.INVISIBLE_OUTDOOR_FMAP_DONORS.get(target))
                self.assertIsNotNone(
                    donor,
                    "%s has no donor in any lookup table, so the widener "
                    "returns silently and the hotspot ships unchanged"
                    % target)
                self.assertTrue(donor.endswith(".fmap"))

    def test_the_donor_is_read_from_its_source_not_from_the_output(self):
        """Assets/<donor> is NOT the donor's map, and reading it widens nothing.

        The build installs an EMPTY map under the donor's own name -- B181
        ships Chaise_brown.png.fmap with no object cells at all -- so a widener
        that opened `assets / donor` found zero object cells, hit
        `if not counts: return`, and silently did nothing. The spa loungers
        shipped at the donor's original eleven cells and the reported
        "the hotspot is very small" was never addressed.

        Every check in this file passed throughout, because they read the
        generator's text rather than the map the widener actually opens. This
        one names the call instead.
        """
        source = GENERATOR.read_text(encoding="utf-8")
        start = source.index("def widen_spa_lounger_hotspot(")
        body = source[start:source.index("\n    def ", start + 1)]
        self.assertIn(
            "donor_path = desktop_safe_fmap_source(donor) or find_fmap_source(donor)",
            body,
            "the widener must resolve the DESKTOP-SAFE map: in a "
            "payload-backed build find_fmap_source returns the raw mobile "
            "map, whose dominant nonzero value is metadata 0x01B00000 at 111 "
            "cells rather than the EObject value at 11, so the dominant-value "
            "heuristic would expand metadata and leave the drop target "
            "untouched",
        )
        self.assertNotIn(
            "donor_path = assets / donor", body,
            "Assets/<donor> is the installed empty map, not the donor's "
            "geometry; dilating from it adds nothing",
        )

    def test_the_widening_claims_footprint_cells_and_spares_the_anchor(self):
        """The claim rule is read from the GENERATOR, not from widen() above.

        Every other check in this file runs the local widen() copy, which has
        its own `if cells[index] == 0` and therefore tests itself rather than
        production. Measured: changing the generator's claim rule left all 16
        checks passing. So this one names the production code.

        Empty-only barely widened a borrower: #201 gives it the donor's mobile
        geometry, which occupies 20 of the ring cells, so the drop target
        moved 11 -> 13 where the ring allows 33. A footprint cell is solid but
        not droppable, and converting it adds droppability without removing
        solidity. The peep-slot anchor must survive either form -- overwriting
        it breaks placement outright, which is the failure the desktop-safe
        translation exists to prevent.
        """
        start = SOURCE.index("def widen_spa_lounger_hotspot(")
        body = SOURCE[start:SOURCE.index("\n    def ", start + 1)]
        self.assertIn(
            "claimable = (0,) + MOBILE_CHAISE_FOOTPRINT_CELL_VALUES", body,
            "the widening must be able to claim mobile footprint cells, or a "
            "borrower's drop target stays hemmed in by the geometry #201 "
            "gives it",
        )
        self.assertIn(
            "MOBILE_CHAISE_PC_SLOT_CELL_VALUE", body,
            "the translated peep-slot anchor must be protected from the claim",
        )
        self.assertIn(
            "MOBILE_CHAISE_MOBILE_SLOT_CELL_VALUE", body,
            "an untranslated anchor must be protected too; claiming it would "
            "destroy the evidence that the translation was missed",
        )
        self.assertIn(
            "claimed_from_footprint", body,
            "the record must report how many cells came from the footprint, "
            "so a build that claimed none is distinguishable from one that "
            "did",
        )


class TheClaimRuleProducesTheApprovedNumber(unittest.TestCase):
    """Run the claim rule and count the result, rather than grep for it.

    The checks above assert SUBSTRINGS of the generator's text. That is
    stronger than the local widen() copy, which tests itself, but it still
    passes if the rule is present and unreachable, fails on a harmless rename,
    and never observes that the drop target actually grew.

    Two wrong numbers were reported for this widening before it landed -- 13
    from the empty-only rule, and 38 from seeding the dilation off the
    already-widened borrower instead of the donor. Neither would have survived
    this check, because it seeds the way production seeds and counts what comes
    out.
    """

    def setUp(self):
        if not DONOR.is_file():
            self.skipTest("donor fmap not present in this checkout")
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen", GENERATOR)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except SystemExit:
            pass
        except Exception as exc:  # pragma: no cover - environment dependent
            self.skipTest("generator not importable here: %s" % exc)
        self.gen = module

    def _borrower(self):
        """A borrower as #201 builds one: donor geometry, safe map's cells."""
        mobile = (ROOT / "patcher_assets" / "optional_patches"
                  / "mobile_furniture_behaviors" / "mobile_fmaps"
                  / "Chaise_brown.png.fmap")
        if not mobile.is_file():
            self.skipTest("mobile donor not present in this checkout")
        raw = _cells_of(mobile.read_bytes())
        safe = _cells_of(DONOR.read_bytes())
        if len(raw) != len(safe):
            self.skipTest("donor grids disagree in this checkout")
        return [s if s and s != d else d for d, s in zip(raw, safe)], safe

    def test_the_drop_target_reaches_the_donor_ring(self):
        gen = self.gen
        borrower, safe = self._borrower()
        width, height = struct.unpack_from("<ii", DONOR.read_bytes(), 24)
        obj = gen.MOBILE_CHAISE_PC_CELL_VALUE

        # SEEDED FROM THE DONOR, exactly as the generator does. Seeding from
        # the borrower gives 38 here and compounds on every rebuild --
        # 38, 63, 92, 125, 160 -- because each pass dilates its own output.
        before = [i for i, v in enumerate(safe) if v == obj]
        grown = set(before)
        for index in before:
            x, y = index % width, index // width
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        grown.add(ny * width + nx)

        claimable = (0,) + gen.MOBILE_CHAISE_FOOTPRINT_CELL_VALUES
        protected = (gen.MOBILE_CHAISE_PC_SLOT_CELL_VALUE,
                     gen.MOBILE_CHAISE_MOBILE_SLOT_CELL_VALUE)
        out = list(borrower)
        claimed = 0
        for index in sorted(grown):
            if out[index] in protected or out[index] not in claimable:
                continue
            if out[index] != 0:
                claimed += 1
            out[index] = obj

        # THE RING SIZE IS ASSERTED ABSOLUTELY, not against itself.
        #
        # Comparing out.count(obj) to len(grown) passes for ANY seed, because
        # both move together -- seeding from the borrower gives ring 38 and
        # 38 claimed, and reads as success. The donor's 11 object cells dilate
        # to exactly 33 positions on this 19x14 grid, so that is the number
        # this must produce. It is also the number the owner approved.
        self.assertEqual(
            len(grown), 33,
            "the donor's dilation ring is %d positions, not 33; the seed is "
            "no longer the donor's object cells, which also makes the "
            "widening compound on every rebuild" % len(grown))
        self.assertEqual(
            out.count(obj), 33,
            "the drop target is %d cells, not 33; %d ring cells were not "
            "claimed" % (out.count(obj), 33 - out.count(obj)))
        self.assertGreater(
            claimed, 0,
            "no cell was claimed from the borrowed footprint, so this is the "
            "empty-only rule that moved the drop target 11 -> 13")
        self.assertIn(
            gen.MOBILE_CHAISE_PC_SLOT_CELL_VALUE, out,
            "the translated peep-slot anchor was consumed by the widening")
        self.assertNotIn(
            gen.MOBILE_CHAISE_MOBILE_SLOT_CELL_VALUE, out,
            "an untranslated anchor appeared, which the claim must never "
            "introduce")

        # IDEMPOTENT: a second pass over the OUTPUT must change nothing.
        #
        # This is what makes the fixed donor seed load-bearing rather than
        # incidental. Re-seeding from the widened map gives 62 here, then 92,
        # 125, 160 -- and these maps are written into a tracked asset
        # directory, so consecutive builds really would keep growing it until
        # the whole grid is a drop target.
        again = list(out)
        for index in sorted(grown):
            if again[index] in protected or again[index] not in claimable:
                continue
            again[index] = obj
        self.assertEqual(
            again.count(obj), out.count(obj),
            "a second pass changed the map, so the widening is not "
            "idempotent and will compound across builds")


def _cells_of(data):
    width, height = struct.unpack_from("<ii", data, 24)
    return list(struct.unpack_from("<%dI" % (width * height), data, 32))


class TheWideningScopeIsExactlyTheTwoSpaLoungers(unittest.TestCase):
    """The tuple names the scope, so no check that iterates it can police it.

    Every other check here -- and in test_shipped_lounger_fmaps -- decides what
    to inspect by reading SPA_LOUNGER_WIDENED_FMAPS. A tuple with an extra
    entry is therefore correct by construction: adding
    "InvisibleLounger.png.fmap" widens the PLAIN lounger from 11 cells to 33
    and the whole suite still passes.

    That is not a hypothetical tidy-up. The owner asked for the two SPA
    loungers and only those, so a wrong scope ships a change to an item nobody
    asked about -- and the plain Invisible Lounger is not covered by
    test_no_ordinary_chaise_is_widened either, because it is not a chaise, it
    is a third borrower of the chaise's map.

    So the expected membership is written out here, independent of the tuple.
    """

    EXPECTED = ("SpaLoungerStd.png.fmap", "InvisibleSpaLounger.png.fmap")
    MUST_NOT_BE_WIDENED = (
        "InvisibleLounger.png.fmap",
        "Chaise_brown.png.fmap",
        "Chaise_blue.png.fmap",
        "Chaise_green.png.fmap",
        "Chaise_red.png.fmap",
    )

    def _tuple_entries(self):
        m = re.search(r"SPA_LOUNGER_WIDENED_FMAPS = \((.*?)\)", SOURCE, re.S)
        self.assertIsNotNone(m, "SPA_LOUNGER_WIDENED_FMAPS is gone")
        return set(re.findall(r'"([^"]+\.fmap)"', m.group(1)))

    def test_it_names_exactly_the_two_spa_loungers(self):
        self.assertEqual(
            self._tuple_entries(), set(self.EXPECTED),
            "the widening scope changed; the owner asked for the two spa "
            "loungers and only those, and every other check in this suite "
            "reads this tuple to decide what to inspect, so a wrong scope is "
            "invisible to them")

    def test_no_shared_or_plain_map_is_in_scope(self):
        entries = self._tuple_entries()
        for name in self.MUST_NOT_BE_WIDENED:
            with self.subTest(fmap=name):
                self.assertNotIn(
                    name, entries,
                    "%s must keep the donor's unwidened footprint; widening a "
                    "shared or plain map changes items the owner did not ask "
                    "about" % name)


if __name__ == "__main__":
    unittest.main()
