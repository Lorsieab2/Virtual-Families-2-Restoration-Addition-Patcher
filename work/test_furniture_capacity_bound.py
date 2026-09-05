#!/usr/bin/env python3
"""The furniture-array sanity bound must match the capacity in the binary.

VF2FindFreeSpaLoungerSlot reads the record count out of the furniture manager
and walks that many records. Before doing so it rejects an implausible count,
which is the guard that stops a corrupt or unexpected value turning the walk
into an out-of-bounds read.

The bound was written as 0x400. The engine's real capacity is 0x200: both
sites that compare the count against an immediate do

    cmp dword ptr [reg + 0x1004], 0x200
    jge <return without adding>

so the array refuses to grow past 512 records and a count above that cannot
occur. A guard at twice the capacity still admits 512 records' worth of
addresses the engine would never populate.

This test reads the constant OUT OF THE OBJECT rather than restating it, so
the source and the binary cannot drift apart silently -- restating 0x200 here
would only pin today's answer to today's guess.

Two deliberate refusals, both from prior defects in this repo:

  * The `cmp` and its `jge` are NOT adjacent (0x0006 then 0x0010 in both
    functions), so this walks decoded instructions instead of reading bytes at
    a fixed displacement.
  * If the sites disagree about the capacity, the test fails rather than
    picking the first. A checker that guesses is worse than no checker.
"""
import pathlib
import re
import struct
import unittest

import capstone

ROOT = pathlib.Path(__file__).resolve().parent
OBJ = ROOT / "desktop_obj_files" / "FurnitureManager.obj"
SOURCE = ROOT / "patch_mobile_furniture_pack.py"
COUNT_FIELD = 0x1004
IMAGE_SCN_CNT_CODE = 0x20


def _code_sections(buf):
    nsec = struct.unpack_from("<H", buf, 2)[0]
    optlen = struct.unpack_from("<H", buf, 16)[0]
    off = 20 + optlen
    for i in range(nsec):
        b = off + i * 40
        _vsize, _vaddr, rawsize, rawptr = struct.unpack_from("<IIII", buf, b + 8)
        chars = struct.unpack_from("<I", buf, b + 36)[0]
        if chars & IMAGE_SCN_CNT_CODE and rawptr and rawsize:
            yield buf[rawptr:rawptr + rawsize]


def capacities_in_the_binary():
    """Every immediate the engine compares the record count against."""
    buf = OBJ.read_bytes()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    found = []
    for data in _code_sections(buf):
        for ins in md.disasm(data, 0):
            if ins.mnemonic != "cmp" or hex(COUNT_FIELD) not in ins.op_str:
                continue
            m = re.search(r",\s*(0x[0-9a-f]+)$", ins.op_str)
            if m:
                found.append(int(m.group(1), 16))
    return found


class TestTheBoundMatchesTheEngine(unittest.TestCase):
    def test_the_binary_agrees_with_itself(self):
        caps = capacities_in_the_binary()
        self.assertTrue(caps, "no capacity comparison found; the object moved")
        self.assertEqual(
            set(caps), {0x200},
            f"the capacity sites disagree: {[hex(c) for c in caps]}; refusing "
            "to pick one",
        )

    def test_the_guard_uses_that_capacity(self):
        caps = capacities_in_the_binary()
        self.assertTrue(caps, "no capacity comparison found; the object moved")
        capacity = caps[0]

        text = SOURCE.read_text(encoding="utf-8")
        guards = re.findall(r"count < 0 \|\| count > (0x[0-9a-fA-F]+)", text)
        self.assertTrue(guards, "the furniture-count guard is gone")
        for guard in guards:
            with self.subTest(guard):
                self.assertEqual(
                    int(guard, 16), capacity,
                    f"guard bounds the count at {guard} but the engine caps "
                    f"the array at {capacity:#x}",
                )


if __name__ == "__main__":
    unittest.main()
