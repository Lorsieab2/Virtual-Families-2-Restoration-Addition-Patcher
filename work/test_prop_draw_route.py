#!/usr/bin/env python3
"""The prop draw route, pinned against the real objects.

Traced after the owner supplied the picnic and patio sprites. Props are not
blitted directly: CDecal::RefreshProps draws them by calling
CDecal::AddDecal(ldwImageGrid *, int, int, float) once per prop type. AddDecal
takes an image grid and world coordinates, so it can draw a sprite that the
prop enum never has to know about -- which is why SetProp's 0x54 bound stops
an id being STORED but does not stop anything being DRAWN.

The detail that matters most here is the one a wrapper would get wrong. The
route into the prop drawing is a TAIL CALL (`jmp rel32`, opcode 0xE9), not a
`call rel32`. Retargeting a tail call REPLACES the callee rather than wrapping
it, so a helper must invoke the original itself. A wrapper written on the
assumption of a `call` site would silently drop the stock prop drawing -- every
existing prop in the game -- which is far worse than the two missing ones it
set out to add. That failure would look like unrelated props vanishing, with
nothing pointing back at this change.
"""
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJS = ROOT / "work" / "desktop_obj_files"

CALL_REL32 = 0xE8
JMP_REL32 = 0xE9

# object -> caller symbol -> (relocation offset, target, expected opcode)
ROUTE = {
    "Environment.obj": {
        "?RefreshProps@CEnvironment@@QAEXXZ": (
            0xE6, "?RefreshDecals@CDecal@@QAEXXZ", JMP_REL32,
        ),
        "?UpdateProps@CEnvironment@@QAEXXZ": (
            0x53, "?RefreshDecals@CDecal@@QAEXXZ", CALL_REL32,
        ),
        "?SetProp@CEnvironment@@QAEXW4EPropEnum@@@Z": (
            0x33B, "?RefreshDecals@CDecal@@QAEXXZ", CALL_REL32,
        ),
    },
    "Decal.obj": {
        "?RefreshDecals@CDecal@@QAEXXZ": (
            0xB70, "?RefreshProps@CDecal@@QAEXXZ", JMP_REL32,
        ),
    },
}


def _coff(name):
    import sys

    sys.path.insert(0, str(ROOT / "work"))
    from coff_patch import CoffObject

    return CoffObject(OBJS / name)


class TestTheDrawRouteIsWhereTheDocsSayItIs(unittest.TestCase):
    def setUp(self):
        if not OBJS.is_dir():
            self.skipTest("desktop_obj_files is a gitignored build input")

    def test_each_documented_call_site_has_the_opcode_recorded(self):
        """A tail call and a call need different wrappers. Pin which is which."""
        for obj_name, sites in ROUTE.items():
            obj = _coff(obj_name)
            for caller, (offset, _target, opcode) in sites.items():
                with self.subTest(f"{obj_name}:{caller}"):
                    symbol = obj.symbol(caller)
                    data = obj.section_data(symbol.section)
                    self.assertEqual(
                        data[offset - 1], opcode,
                        f"{caller} +{offset:#x} is no longer "
                        f"{'a tail call' if opcode == JMP_REL32 else 'a call'}; "
                        "a wrapper built on the old shape would drop the stock "
                        "prop drawing rather than add to it",
                    )

    def test_addecal_is_still_a_public_method_taking_an_image_grid(self):
        """The whole route depends on this signature staying callable."""
        obj = _coff("Decal.obj")
        # public: void __thiscall CDecal::AddDecal(ldwImageGrid *, int, int, float)
        obj.symbol("?AddDecal@CDecal@@QAEXPAVldwImageGrid@@HHM@Z")

    def test_refreshprops_is_reached_from_exactly_one_place(self):
        """More than one site means a wrapper could miss a path.

        RefreshDecals is the only caller. If that ever stops being true, a
        helper hooked here would draw for some routes and not others, which
        reads in game as a prop that flickers rather than one that is absent.
        """
        data = (OBJS / "Decal.obj").read_bytes()
        target = b"?RefreshProps@CDecal@@QAEXXZ"
        nsym = struct.unpack_from("<I", data, 12)[0]
        symptr = struct.unpack_from("<I", data, 8)[0]
        strtab = symptr + nsym * 18

        def name(index):
            off = symptr + index * 18
            raw = data[off:off + 8]
            if raw[:4] == b"\x00\x00\x00\x00":
                start = strtab + struct.unpack_from("<I", raw, 4)[0]
                return data[start:data.index(b"\x00", start)]
            return raw.rstrip(b"\x00")

        nsec = struct.unpack_from("<H", data, 2)[0]
        opt = struct.unpack_from("<H", data, 16)[0]
        hits = 0
        for index in range(nsec):
            off = 20 + opt + index * 40
            section = data[off:off + 8].rstrip(b"\x00").decode("ascii", "replace")
            if not section.startswith(".text"):
                continue
            relptr = struct.unpack_from("<I", data, off + 24)[0]
            nrel = struct.unpack_from("<H", data, off + 32)[0]
            for r in range(nrel):
                _off, sidx, _typ = struct.unpack_from("<IIH", data, relptr + r * 10)
                if name(sidx) == target:
                    hits += 1
        self.assertEqual(hits, 1, f"expected one call to RefreshProps, found {hits}")


class TestTheLogRecordsTheRoute(unittest.TestCase):
    LOG = ROOT / "docs" / "Transparency Log.txt"

    def test_the_route_and_the_tail_call_warning_are_written_down(self):
        text = self.LOG.read_text(encoding="utf-8")
        self.assertIn("how the picnic and patio props would actually be drawn", text)
        self.assertIn("AddDecal", text)
        self.assertIn(
            "TAIL CALL", text,
            "the tail-call shape is the detail a wrapper would get wrong; it "
            "belongs in the record",
        )


if __name__ == "__main__":
    unittest.main()
