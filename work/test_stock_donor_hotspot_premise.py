#!/usr/bin/env python3
"""The stock-donor route cannot identify an added item, and here is why.

Seven added items were left out of the mobile drop dispatcher on the argument
that they borrow stock furniture, and that because their .fmap cell
vocabularies are byte-identical to the donors' maps, the native
theMainScene::HandleDropOnHotSpot path already reaches them.

The owner then reported that the Home Gym System does nothing. These tests pin
the two facts that explain it, so the argument cannot be restated later
without something failing.

This is the repository's recurring defect shape once more -- what a check
READS versus what it ASSERTS. Comparing the vocabularies proved the maps
match. It was recorded as proving the drop would be dispatched, which the
comparison never tested and which is false.
"""
import pathlib
import struct
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
FMAPS = ROOT / "assets" / "TextAsset"
SCENE = ROOT / "desktop_obj_files" / "theMainScene.obj"

DONORS = ("YogaGearStd", "TreadmillStd", "PoolTableStd", "HammockStd")


def vocabulary(name):
    """The set of (object type, payload) pairs a map's cells carry."""
    b = (FMAPS / f"{name}.png.fmap").read_bytes()
    w, h = struct.unpack_from("<ii", b, 24)
    pairs = set()
    for i in range(w * h):
        cell = struct.unpack_from("<I", b, 32 + i * 4)[0]
        if cell:
            pairs.add((cell >> 16, cell & 0xFFFF))
    return pairs


def _sym_names(buf):
    symptr, nsym = struct.unpack_from("<II", buf, 8)
    strtab = symptr + nsym * 18

    def name(i):
        b = symptr + i * 18
        raw = buf[b:b + 8]
        if raw[:4] == b"\x00\x00\x00\x00":
            off = struct.unpack_from("<I", raw, 4)[0]
            end = buf.index(b"\x00", strtab + off)
            return buf[strtab + off:end].decode("latin1")
        return raw.rstrip(b"\x00").decode("latin1")

    return name, nsym, symptr


class TestTheDonorMapsCannotTellItemsApart(unittest.TestCase):
    def test_every_donor_carries_the_same_vocabulary(self):
        """Byte-identical hotspot data is the problem, not the reassurance.

        If the donors were distinguishable from one another, borrowing one
        would at least carry a usable identity. They are not.
        """
        vocabs = {name: vocabulary(name) for name in DONORS}
        first = vocabs[DONORS[0]]
        for name, vocab in vocabs.items():
            with self.subTest(name):
                self.assertEqual(
                    vocab, first,
                    f"{name} differs from {DONORS[0]}; if the donor maps have "
                    "become distinguishable the stock-donor argument deserves "
                    "re-examination rather than this failure being silenced",
                )

    def test_the_shared_vocabulary_carries_no_item_identity(self):
        """Two object types, neither of which names an item."""
        self.assertEqual(vocabulary("YogaGearStd"), {(0x0, 0x1), (0x100, 0x0)})


class TestTheStockDropPathNeverReadsAnItemId(unittest.TestCase):
    """HandleDropOnHotSpot dispatches on the hotspot enum and nothing else."""

    def _function_section(self):
        buf = SCENE.read_bytes()
        name, nsym, symptr = _sym_names(buf)
        i = 0
        found = []
        while i < nsym:
            b = symptr + i * 18
            secnum = struct.unpack_from("<h", buf, b + 12)[0]
            if secnum > 0 and "HandleDropOnHotSpot" in name(i):
                found.append(secnum)
            i += 1 + buf[b + 17]
        self.assertEqual(
            len(found), 1,
            f"expected exactly one defining symbol, found {len(found)}; "
            "refusing to guess which",
        )
        return buf, name, found[0]

    def test_it_calls_only_gethotspot_and_dispatch(self):
        buf, name, secnum = self._function_section()
        nsec = struct.unpack_from("<H", buf, 2)[0]
        optlen = struct.unpack_from("<H", buf, 16)[0]
        base = 20 + optlen + (secnum - 1) * 40
        relptr = struct.unpack_from("<I", buf, base + 24)[0]
        nrel = struct.unpack_from("<H", buf, base + 32)[0]

        targets = {
            name(struct.unpack_from("<I", buf, relptr + r * 10 + 4)[0])
            for r in range(nrel)
        }
        joined = " ".join(targets)
        self.assertIn("GetHotSpot", joined)
        self.assertIn("Dispatch", joined)
        for forbidden in ("FindFurniture", "FurnitureManager", "ItemAtPoint"):
            with self.subTest(forbidden):
                self.assertNotIn(
                    forbidden, joined,
                    "the stock drop path would be able to identify an added "
                    f"item if it referenced {forbidden}; if that changes, the "
                    "stock-donor argument may be revisited",
                )


if __name__ == "__main__":
    unittest.main()
