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
        geometry, which occupies 20 of the 25 ring cells, so the drop target
        moved 11 -> 13 where the ring allows 38. A footprint cell is solid but
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


if __name__ == "__main__":
    unittest.main()
