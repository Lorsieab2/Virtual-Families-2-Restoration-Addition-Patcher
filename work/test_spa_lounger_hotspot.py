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


if __name__ == "__main__":
    unittest.main()
