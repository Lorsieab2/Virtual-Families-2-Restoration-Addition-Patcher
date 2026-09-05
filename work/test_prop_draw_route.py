#!/usr/bin/env python3
"""The prop draw route, pinned against the real objects.

Traced after the owner supplied the picnic and patio sprites. Props are not
blitted directly: CDecal::RefreshProps draws them through CDecal::AddDecal,
which takes an image grid and world coordinates -- so it can draw a sprite the
prop enum never has to know about. That is why SetProp's 0x54 bound stops an
id being STORED but does not stop anything being DRAWN.

Two things review corrected in the first version of this file, both worth
keeping in mind because both made a green test prove less than it appeared to:

  * It checked each call site's OPCODE but discarded the relocation TARGET, so
    an object where the instruction stayed a `jmp` but pointed somewhere else
    entirely still passed.
  * It counted references to RefreshProps within Decal.obj only. RefreshProps
    is a public method, so a direct call from any other object records its
    relocation in THAT object's table -- the local count would stay at one
    while a second path existed, and a wrapper hooked at the single known site
    would miss it.

The claim that RefreshProps calls AddDecal "sixteen times, once per prop type"
was also wrong, and only counting the relocations exposed it: 19 calls to the
four-argument overload and 25 to the five-argument one.
"""
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJS = ROOT / "work" / "desktop_obj_files"

CALL_REL32 = 0xE8
JMP_REL32 = 0xE9

REFRESH_DECALS = "?RefreshDecals@CDecal@@QAEXXZ"
REFRESH_PROPS = "?RefreshProps@CDecal@@QAEXXZ"
ADD_DECAL_4 = "?AddDecal@CDecal@@QAEXPAVldwImageGrid@@HHM@Z"
ADD_DECAL_5 = "?AddDecal@CDecal@@QAEXPAVldwImageGrid@@HHHM@Z"

# All six Environment sites the log claims reach RefreshDecals, plus the one
# inside Decal.obj. offset -> (target, opcode).
ROUTE = {
    "Environment.obj": {
        "?ClearProp@CEnvironment@@QAEXW4EPropEnum@@@Z": (0x104, REFRESH_DECALS, CALL_REL32),
        "?Refresh@CEnvironment@@QAEX_N@Z": (0x18, REFRESH_DECALS, CALL_REL32),
        "?RefreshProps@CEnvironment@@QAEXXZ": (0xE6, REFRESH_DECALS, JMP_REL32),
        "?SetProp@CEnvironment@@QAEXW4EPropEnum@@@Z": (0x33B, REFRESH_DECALS, CALL_REL32),
        "?SetPropGroceries@CEnvironment@@QAEXW4EPropEnum@@H@Z": (0x98, REFRESH_DECALS, CALL_REL32),
        "?UpdateProps@CEnvironment@@QAEXXZ": (0x53, REFRESH_DECALS, CALL_REL32),
    },
    "Decal.obj": {
        REFRESH_DECALS: (0xB70, REFRESH_PROPS, JMP_REL32),
    },
}

# Counted from the relocations inside RefreshProps, not estimated.
ADD_DECAL_CALLS = {ADD_DECAL_4: 19, ADD_DECAL_5: 25}


def _symbols(data):
    """(name-of-index, function-symbols) for a COFF object."""
    symptr = struct.unpack_from("<I", data, 8)[0]
    nsym = struct.unpack_from("<I", data, 12)[0]
    strtab = symptr + nsym * 18

    def name(index):
        off = symptr + index * 18
        raw = data[off:off + 8]
        if raw[:4] == b"\x00\x00\x00\x00":
            start = strtab + struct.unpack_from("<I", raw, 4)[0]
            return data[start:data.index(b"\x00", start)].decode("ascii", "replace")
        return raw.rstrip(b"\x00").decode("ascii", "replace")

    funcs = []
    for index in range(nsym):
        off = symptr + index * 18
        value, secnum, _typ, cls = struct.unpack_from("<IhHB", data, off + 8)
        if secnum > 0 and cls == 2:
            funcs.append((secnum, value, name(index)))
    return name, funcs


def _text_relocations(data):
    """Yield (section_index, offset, symbol_index) for every .text relocation."""
    nsec = struct.unpack_from("<H", data, 2)[0]
    opt = struct.unpack_from("<H", data, 16)[0]
    for index in range(nsec):
        off = 20 + opt + index * 40
        section = data[off:off + 8].rstrip(b"\x00").decode("ascii", "replace")
        if not section.startswith(".text"):
            continue
        relptr = struct.unpack_from("<I", data, off + 24)[0]
        nrel = struct.unpack_from("<H", data, off + 32)[0]
        for r in range(nrel):
            offset, sidx, _typ = struct.unpack_from("<IIH", data, relptr + r * 10)
            yield index + 1, offset, sidx


class PropRouteTests(unittest.TestCase):
    def setUp(self):
        if not OBJS.is_dir():
            self.skipTest("desktop_obj_files is a gitignored build input")

    def _coff(self, name):
        import sys

        sys.path.insert(0, str(ROOT / "work"))
        from coff_patch import CoffObject

        return CoffObject(OBJS / name)

    def test_every_documented_site_keeps_its_opcode_and_its_target(self):
        """Opcode alone is not enough.

        A site whose instruction is still a `jmp` but which now points at a
        different function would leave the documented route false while this
        test stayed green, so the relocation target is checked too.
        """
        for obj_name, sites in ROUTE.items():
            data = (OBJS / obj_name).read_bytes()
            name, _funcs = _symbols(data)
            obj = self._coff(obj_name)
            relocs = {
                (sec, off): name(sidx)
                for sec, off, sidx in _text_relocations(data)
            }
            for caller, (offset, target, opcode) in sites.items():
                with self.subTest(f"{obj_name}:{caller.split('@')[0]}"):
                    symbol = obj.symbol(caller)
                    body = obj.section_data(symbol.section)
                    self.assertEqual(
                        body[offset - 1], opcode,
                        f"{caller} +{offset:#x} is no longer "
                        f"{'a tail call' if opcode == JMP_REL32 else 'a call'}; "
                        "a wrapper built on the old shape would drop the stock "
                        "prop drawing rather than add to it",
                    )
                    self.assertEqual(
                        relocs.get((symbol.section, offset)), target,
                        f"{caller} +{offset:#x} no longer targets {target}",
                    )

    def test_refreshprops_is_called_from_exactly_one_place_repo_wide(self):
        """Scan every object, not just Decal.obj.

        RefreshProps is public, so a direct call from another object records
        its relocation in that object's table. Counting only within Decal.obj
        would stay at one while a second path existed, and a wrapper hooked at
        the single known site would silently miss it -- which reads in game as
        a prop that refreshes inconsistently rather than one that is absent.
        """
        sites = []
        for path in sorted(OBJS.glob("*.obj")):
            data = path.read_bytes()
            if REFRESH_PROPS.encode("ascii") not in data:
                continue
            name, _funcs = _symbols(data)
            for _sec, offset, sidx in _text_relocations(data):
                if name(sidx) == REFRESH_PROPS:
                    sites.append((path.name, hex(offset)))
        self.assertEqual(
            len(sites), 1,
            f"expected one incoming call to RefreshProps across all objects, "
            f"found {len(sites)}: {sites}",
        )
        self.assertEqual(sites[0][0], "Decal.obj")

    def test_refreshprops_really_makes_the_documented_decal_calls(self):
        """Looking the symbol up by name proves nothing about the caller.

        If RefreshProps stopped calling AddDecal, called only one overload, or
        changed its call count, the conclusion that wrapping it provides the
        drawing route would be unsupported -- while a name lookup stayed green.
        """
        data = (OBJS / "Decal.obj").read_bytes()
        name, funcs = _symbols(data)
        counts = {ADD_DECAL_4: 0, ADD_DECAL_5: 0}
        for sec, offset, sidx in _text_relocations(data):
            target = name(sidx)
            if target not in counts:
                continue
            owner = max(
                (f for f in funcs if f[0] == sec and f[1] <= offset),
                key=lambda f: f[1], default=None,
            )
            if owner and owner[2] == REFRESH_PROPS:
                counts[target] += 1
        self.assertEqual(
            counts, ADD_DECAL_CALLS,
            "RefreshProps' AddDecal calls have changed; the documented draw "
            "route rests on these",
        )


class TestTheLogRecordsTheRoute(unittest.TestCase):
    LOG = ROOT / "docs" / "Transparency Log.txt"

    def _entry(self):
        text = self.LOG.read_text(encoding="utf-8")
        heading = "how the picnic and patio props would actually be drawn"
        self.assertIn(heading, text, "the draw-route entry is gone")
        return text.split(heading, 1)[1].split(chr(10) + "B180 ", 1)[0]

    def test_the_tail_call_warning_is_written_down(self):
        entry = self._entry()
        self.assertIn("AddDecal", entry)
        self.assertIn(
            "TAIL CALL", entry,
            "the tail-call shape is the detail a wrapper would get wrong",
        )

    def test_the_log_states_the_counted_call_numbers(self):
        """The 'sixteen' claim was wrong. Keep the counted ones honest."""
        entry = self._entry()
        for count in ADD_DECAL_CALLS.values():
            with self.subTest(count):
                self.assertIn(str(count), entry)


class TestTheDecalCallShape(unittest.TestCase):
    """The wrapper's arguments come from this sequence, so pin it.

    Decoded rather than inferred. The first AddDecal call in RefreshProps sets
    up its arguments as immediate constants, which is what makes the wrapper
    tractable: there is no furniture record to resolve and no coordinate space
    to reconcile, only two literals per sprite.

    The prop-record stride is confirmed here too. `mov eax, ebx` / `shl eax, 4`
    then `cmp byte [eax+0x7c], 0` is the prop*16 + 0x7C the request ledger
    recorded from the SetProp fall-through, arrived at from the other end.
    """

    OBJ = OBJS / "Decal.obj"
    # mov eax, ebx ; shl eax, 4 ; cmp byte [eax+0x7c], 0
    STRIDE = bytes((0x8B, 0xC3, 0xC1, 0xE0, 0x04, 0x80, 0xB8, 0x7C, 0x00, 0x00, 0x00, 0x00))

    def setUp(self):
        if not self.OBJ.is_file():
            self.skipTest("Decal.obj is a gitignored build input")

    def _body(self):
        import sys

        sys.path.insert(0, str(ROOT / "work"))
        from coff_patch import CoffObject

        obj = CoffObject(self.OBJ)
        symbol = obj.symbol(REFRESH_PROPS)
        # section_data returns a memoryview, whose count()/in count ELEMENTS
        # rather than subsequences -- both silently return 0 for a byte
        # pattern that is present. Convert once, here, so no caller can be
        # caught by it.
        return bytes(obj.section_data(symbol.section))

    def test_the_prop_record_stride_is_still_sixteen_bytes(self):
        """prop*16 + 0x7C, reached from the drawing side.

        If this ever changes, both the ledger's account of the SetProp
        fall-through and the wrapper's reading of prop state are wrong.
        """
        body = self._body()
        hits = body.count(self.STRIDE)
        self.assertGreater(
            hits, 0,
            "the index*16 + 0x7c prop-record access is gone from RefreshProps",
        )

    def test_the_decal_coordinates_are_immediates(self):
        """push <imm32> twice, immediately before the call.

        This is what removes the coordinate-space question entirely. If the
        caller ever starts computing coordinates instead, a wrapper passing
        literals would draw in the wrong place, and nothing else here would
        notice.
        """
        body = self._body()
        # push 0xff ; push 0x146 ; push dword [edi+0x182c]
        setup = bytes((0x68, 0xFF, 0x00, 0x00, 0x00, 0x68, 0x46, 0x01, 0x00, 0x00))
        self.assertIn(
            setup, body,
            "the documented immediate-coordinate call setup is gone; the "
            "wrapper's literals would no longer match how props are drawn",
        )

    def test_the_log_does_not_overstate_the_immediates(self):
        """43 of 44, not all of them.

        An earlier draft said every coordinate was an immediate. One call --
        the four-argument one at RefreshProps+0x6e5 -- pushes esi and
        dword [eax] instead, a computed position. Overstating this matters in
        one direction: it would tell a later reader that literals are the only
        form the engine accepts, when in fact it supports both.
        """
        text = (ROOT / "docs" / "Transparency Log.txt").read_text(encoding="utf-8")
        entry = text.split("what a prop decal call actually looks like", 1)[1]
        entry = entry.split(chr(10) + "B180 ", 1)[0]
        self.assertIn("43 of the 44", entry)
        self.assertIn(
            "0x6e5", entry,
            "the exception must be named so it can be re-checked",
        )

    def test_the_log_records_that_position_is_resolved(self):
        text = (ROOT / "docs" / "Transparency Log.txt").read_text(encoding="utf-8")
        self.assertIn("what a prop decal call actually looks like", text)
        self.assertIn(
            "POSITION. RESOLVED", text,
            "the coordinate question was recorded as unconfirmed; once answered "
            "the earlier note has to say so, or it reads as still open",
        )


if __name__ == "__main__":
    unittest.main()
