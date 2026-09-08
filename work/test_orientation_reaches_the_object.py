"""The orientation comparison must survive into the compiled object.

Codex's finding on #238: every other test in this change derives its result
from the generator SOURCE, so all of them still pass if the block stops being
emitted, a stale helper is compiled, or the linked object never receives the
comparison. A source-only check cannot tell the difference between "the fix is
written" and "players get the fix".

This one reads the EMITTED .cpp and, when the compiled object is present, the
object's own bytes.

sFurnitureInfo2 places orientation at +0x04 in every declaration in the file,
including the `int object;` variant the chair handlers are emitted with -- so
the comparison compiles to a read at +4 from the struct pointer, not +0x14.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
OBJS = WORK / "patched_mobile_furniture_pack_objs"

CHAIR = 'info.orientation == 1 ? "Sit In Chair NW" : "Sit In Chair NE"'


def emitted_sources():
    return sorted(WORK.glob("vf2_*.cpp"))


class TheEmittedSourceCarriesIt(unittest.TestCase):
    def setUp(self):
        # Only units that could carry the handler count. A partial generator
        # run leaves unrelated .cpp files behind (vf2_fmod_thunks.cpp, for
        # one), and asserting against those reports a missing fix that is
        # simply in a file nobody generated. Measured: the compile test alone
        # emits one unrelated unit, and this test failed against it before
        # being scoped.
        self.sources = [p for p in emitted_sources()
                        if "furniture" in p.name or "behavior" in p.name]
        if not self.sources:
            self.skipTest(
                "the behaviours translation unit has not been generated in "
                "this checkout; the compiled-object checks below still apply")

    def test_some_emitted_unit_contains_the_comparison(self):
        hits = [p for p in self.sources
                if CHAIR in p.read_text(encoding="utf-8", errors="replace")]
        self.assertTrue(
            hits,
            "no emitted translation unit contains the orientation "
            "comparison, so the generator block is not reaching the build")

    def test_no_emitted_unit_still_reads_the_padding_offset(self):
        bad = []
        for p in self.sources:
            text = p.read_text(encoding="utf-8", errors="replace")
            if "reinterpret_cast<unsigned char *>(&info) + 0x14" in text:
                bad.append(p.name)
        self.assertEqual(
            bad, [],
            "an emitted unit still reads orientation at +0x14, which is "
            "padding in sFurnitureInfo2: %s" % bad)

    def test_the_governing_struct_puts_orientation_second(self):
        # The offset the compiled comparison will use depends on this.
        for p in self.sources:
            text = p.read_text(encoding="utf-8", errors="replace")
            if CHAIR not in text:
                continue
            site = text.find(CHAIR)
            starts = [i for i in range(len(text))
                      if text.startswith("struct sFurnitureInfo2 {", i)]
            owning = [i for i in starts if i < site]
            if not owning:
                continue
            start = max(owning)
            body = text[start:text.index("};", start)]
            fields = [ln.strip() for ln in body.splitlines()[1:] if ln.strip()]
            self.assertEqual(
                fields[:2], ["int unknown0;", "int orientation;"],
                "in the EMITTED unit, orientation is no longer the second "
                "field, so it is not at +0x04 and the compiled read moves")
            return
        self.skipTest("no emitted unit carries the comparison")


class TheCompiledObjectCarriesIt(unittest.TestCase):
    """Runs only after a full build has produced the helper object.

    work/patched_mobile_furniture_pack_objs/ holds 167 STOCK game objects at
    rest; the generated helper appears there only once the generator and
    compiler have run. So this class skips on a plain checkout by design --
    but a skip is not a pass, and the reason is stated so nobody reads a
    green line as evidence the artifact was checked.
    """

    def setUp(self):
        if not OBJS.is_dir():
            self.skipTest("no built objects present")
        self.objs = sorted(OBJS.glob("vf2_mobile_furniture_behaviors.obj"))
        if not self.objs:
            self.skipTest(
                "the generated helper object is not present; it exists only "
                "after a full build, and the 167 objects here are the stock "
                "game's. Run the build to exercise this class.")

    def test_the_chair_animation_strings_are_in_the_object(self):
        # If the handler were optimised away or never compiled in, neither
        # string would be present and every source-level test would still pass.
        data = self.objs[0].read_bytes()
        for name in (b"Sit In Chair NW", b"Sit In Chair NE"):
            with self.subTest(anim=name.decode()):
                self.assertIn(
                    name, data,
                    "%s is absent from the compiled object, so the chair "
                    "handler is not in the shipped code" % name.decode())

    def test_both_orientations_are_reachable_in_the_object(self):
        # Both arms must survive: a compiler that folded the condition would
        # leave only one string, and that is the failure this whole change is
        # about.
        data = self.objs[0].read_bytes()
        self.assertIn(b"Sit In Chair NW", data)
        self.assertIn(b"Sit In Chair NE", data)


if __name__ == "__main__":
    unittest.main()
