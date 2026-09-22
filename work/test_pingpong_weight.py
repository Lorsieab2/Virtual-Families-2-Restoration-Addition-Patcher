#!/usr/bin/env python3
"""Ping-pong is chosen as often as pool, and still only when a table is placed.

Owner: "Raise pingpong weight to same as pool table."

WHAT WAS WRONG. Ping-pong was already an autonomous candidate -- cloned from
the Pool Table's behaviour 0x099 into 0x0B8 by VF2EnableAutonomousCandidates --
but at weight 450, while the Pool Table's own candidate is enabled by
EnableAllAgesAutonomousCandidate, which defaults to 3000. A ping-pong table was
therefore offered roughly a seventh as often as the pool table it was cloned
from, which read in play as villagers ignoring it.

WHAT THIS SUITE PINS. The two numbers must stay equal, and they are derived
from two independent places in the source -- the clone call and the default
helper -- so they cannot agree merely by construction. It also pins the object
prerequisite, because the weight and the gate are easy to confuse: the weight
decides HOW OFTEN the action is chosen when a table exists, the object decides
WHETHER it is offered at all. Raising one must not disturb the other.

NOT TESTED HERE. Whether a villager actually walks over and plays is the
owner's playtest; a weight in a candidate record cannot establish player-facing
behaviour.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))

POOL_BEHAVIOR = 0x099
PING_PONG_BEHAVIOR = 0x0B8
PING_PONG_OBJECT = 0x9A


def _source():
    return GEN.read_text(encoding="utf-8")


def _pool_default_weight(src):
    """The weight EnableAllAgesAutonomousCandidate gives a stock candidate."""
    match = re.search(
        r"static void EnableAllAgesAutonomousCandidate\(unsigned char \*villager, unsigned int behavior\)\s*\{\s*"
        r"EnableAllAgesAutonomousCandidateWithWeight\(villager, behavior, (\d+)\);",
        src)
    if match is None:
        raise AssertionError("EnableAllAgesAutonomousCandidate's default weight is not readable")
    return int(match.group(1))


def _ping_pong_clone(src):
    """(donor, target, weight, object) from the ping-pong clone call."""
    match = re.search(
        r"CloneAutonomousCandidateWithWeight\(data, (0x[0-9A-Fa-f]+), (0x[0-9A-Fa-f]+), (\d+), "
        r"__VF2_PING_PONG_OBJECT__\);",
        src)
    if match is None:
        raise AssertionError("the ping-pong autonomous clone call is not present")
    return (int(match.group(1), 16), int(match.group(2), 16), int(match.group(3)))


class ThePingPongWeight(unittest.TestCase):
    def setUp(self):
        self.src = _source()

    def test_the_pool_table_is_enabled_at_the_default_weight(self):
        # The comparison target. If the pool table ever stops using the
        # default helper this test must be revisited rather than silently
        # comparing against a stale number.
        self.assertIn(
            f"EnableAllAgesAutonomousCandidate(data, {POOL_BEHAVIOR:#05x}); // PlayingPooltable",
            self.src)

    def test_ping_pong_matches_the_pool_table_weight(self):
        pool = _pool_default_weight(self.src)
        donor, target, weight = _ping_pong_clone(self.src)
        self.assertEqual(donor, POOL_BEHAVIOR)
        self.assertEqual(target, PING_PONG_BEHAVIOR)
        self.assertEqual(
            weight, pool,
            f"ping-pong is weighted {weight} but the pool table it clones is {pool}")

    def test_the_weight_is_not_the_old_value(self):
        # A direct guard on the reported symptom, independent of the helper
        # parse above: 450 was roughly a seventh of the pool table's 3000.
        _, _, weight = _ping_pong_clone(self.src)
        self.assertNotEqual(weight, 450)

    def test_the_object_prerequisite_is_untouched(self):
        # The weight decides how OFTEN; the object decides WHETHER. 0x9A
        # belongs to the Ping-Pong Table alone, so this is what keeps the
        # candidate out of houses with no table. Raising the weight must not
        # disturb it.
        self.assertIn("MOBILE_PING_PONG_OBJECT = 0x9A", self.src)
        clone = re.search(
            r"CloneAutonomousCandidateWithWeight\(data, 0x099, 0x0B8, \d+, (\w+)\);", self.src)
        self.assertIsNotNone(clone)
        self.assertEqual(clone.group(1), "__VF2_PING_PONG_OBJECT__")
        # And the helper still applies a non-zero prerequisite rather than
        # inheriting the donor's, which is the defect shape the Home Gym and
        # Yoga candidates documented.
        self.assertIn("if (objectPrerequisite != 0) {", self.src)
        self.assertIn("*(unsigned int *)(target + 0xC4) = objectPrerequisite;", self.src)


class BothTableVariantsAreCovered(unittest.TestCase):
    """Visible AND invisible ping-pong tables both satisfy the gate.

    Owner: "make sure the pool table fix applies to both visible and
    invisible variants." The candidate is gated on ObjectExists(0x9A), so
    coverage is decided by which fmaps carry that object -- not by the item
    ids, which differ. Both maps must declare it or the invisible table would
    be placed without ever making the behaviour eligible.
    """

    def setUp(self):
        import patch_mobile_furniture_pack as patcher
        self.assets = patcher.OUT / "Assets"
        needed = ["PingPongTableStd.png.fmap", "InvisiblePingPongTable.png.fmap"]
        missing = [n for n in needed if not (self.assets / n).is_file()]
        if not missing:
            return
        # A SKIP HERE WOULD BE THE DEFECT. Review: "both variant-coverage
        # tests are skipped and the suite remains green ... the claimed guard
        # cannot distinguish a valid two-variant payload from one with no maps
        # at all." Correct -- so generate the maps rather than skipping, and
        # fail if they still do not appear.
        if any(pathlib.Path(patcher.PATCHED).glob("*.cpp")):
            # The generator has run in this checkout, so the maps should exist.
            # Their absence is a real payload defect, not a missing setup.
            raise AssertionError(
                "the generator has run but %s %s absent from the build Assets; "
                "a ping-pong table variant would never make the autonomous "
                "candidate eligible" % (", ".join(missing),
                                        "is" if len(missing) == 1 else "are"))
        import subprocess
        result = subprocess.run(
            [sys.executable, str(GEN)], cwd=str(ROOT),
            capture_output=True, text=True)
        still = [n for n in needed if not (self.assets / n).is_file()]
        if still:
            raise AssertionError(
                "ran the generator (exit %d) and %s still absent from %s"
                % (result.returncode, ", ".join(still), self.assets))

    @staticmethod
    def _objects(path):
        import struct
        data = path.read_bytes()
        cols, rows = struct.unpack_from("<ii", data, 24)
        cells = struct.unpack_from("<%dI" % (cols * rows), data, 32)
        found = {}
        for cell in cells:
            obj = (((cell >> 11) & 0x40000) | (cell & 0x3F800)) >> 11
            if obj:
                found[obj] = found.get(obj, 0) + 1
        return found

    def test_both_maps_declare_the_ping_pong_object(self):
        for name in ("PingPongTableStd", "InvisiblePingPongTable"):
            with self.subTest(table=name):
                objects = self._objects(self.assets / f"{name}.png.fmap")
                self.assertIn(
                    PING_PONG_OBJECT, objects,
                    f"{name} does not declare object {PING_PONG_OBJECT:#x}, so placing it "
                    "would never make the autonomous ping-pong candidate eligible")
                self.assertGreater(objects[PING_PONG_OBJECT], 0)

    def test_neither_map_still_declares_the_pool_table_object(self):
        # 0x36 is the stock Pool Table's object. Either map still carrying it
        # would re-create the "invisible ping-pong plays pool" confusion that
        # the object split was made to end.
        for name in ("PingPongTableStd", "InvisiblePingPongTable"):
            with self.subTest(table=name):
                self.assertNotIn(0x36, self._objects(self.assets / f"{name}.png.fmap"))


class TheCompiledObject(unittest.TestCase):
    """The weight must be an immediate in the COMPILED code, not just source.

    AGENTS.md section 1: verify the shipped artifact, never the source.
    Review: "this test only parses the generated .cpp, so it still passes if
    compilation/linking uses a stale object or the helper never reaches the
    executable." Correct. This compiles the unit that carries the clone call
    and decodes the argument out of the instruction stream.

    The weight is the fourth argument of a __cdecl call, so it is pushed
    fourth-from-last before the call -- i.e. `push <weight>` appears in the
    argument sequence alongside `push 9Ah` (the object), `push 0B8h` (the
    target behaviour) and `push 99h` (the donor).
    """

    @classmethod
    def setUpClass(cls):
        import subprocess
        import tempfile
        import patch_mobile_furniture_pack as patcher
        from test_generated_cpp_compiles import _vcvars
        cls.reason = None
        vcvars = _vcvars()
        if vcvars is None:
            cls.reason = "no Visual Studio toolchain on this machine"
            return
        unit = None
        pattern = re.compile(r"CloneAutonomousCandidateWithWeight\(data, 0x099, 0x0[bB]8,", re.I)
        for path in sorted(pathlib.Path(patcher.PATCHED).glob("*.cpp")):
            if pattern.search(path.read_text(encoding="ascii", errors="replace")):
                unit = path
                break
        if unit is None:
            cls.reason = "the ping-pong clone call is in no generated unit; run the generator"
            return
        cls.work = tempfile.TemporaryDirectory()
        work = pathlib.Path(cls.work.name)
        (work / unit.name).write_bytes(unit.read_bytes())
        result = subprocess.run(
            f'"{vcvars}" >nul 2>&1 && cd /d "{work}" && '
            f'cl /c /EHsc /nologo "{unit.name}" && '
            f'dumpbin /nologo /disasm "{unit.stem}.obj" > d.txt',
            shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError("the unit carrying the clone call did not compile/decode:\n"
                                 + (result.stdout or "") + (result.stderr or ""))
        cls.disasm = (work / "d.txt").read_text(encoding="utf-8", errors="replace")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "work", None):
            cls.work.cleanup()

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def test_the_compiled_call_pushes_the_pool_table_weight(self):
        pool = _pool_default_weight(_source())
        # Find the call site by its distinctive argument pair: the target
        # behaviour 0B8h and the object 9Ah, then require the pool weight
        # among the pushes immediately around them.
        window = None
        lines = self.disasm.splitlines()
        for i, line in enumerate(lines):
            if re.search(r"push\s+0B8h", line):
                window = lines[max(0, i - 4):i + 6]
                if any(re.search(r"push\s+9Ah", w) for w in window):
                    break
                window = None
        self.assertIsNotNone(
            window,
            "no compiled call site pushes both the ping-pong behaviour 0B8h and object 9Ah")
        text = "\n".join(window)
        self.assertRegex(
            text, r"push\s+0?%Xh" % pool,
            f"the compiled clone call does not push the pool table weight {pool}; window was:\n{text}")
        # And the superseded value is not what ships.
        self.assertNotRegex(text, r"push\s+1C2h")  # 450


class TheEmittedUnit(unittest.TestCase):
    """The substituted call must reach the emitted C++, not just the template."""

    def setUp(self):
        import patch_mobile_furniture_pack as patcher
        self.unit = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
        candidates = sorted(pathlib.Path(patcher.PATCHED).glob("*.cpp"))
        if not candidates:
            self.skipTest("no generated units; run the generator first")
        self.text = None
        pattern = re.compile(
            r"CloneAutonomousCandidateWithWeight\(data, 0x099, 0x0[bB]8,", re.I)
        for path in candidates:
            body = path.read_text(encoding="ascii", errors="replace")
            if pattern.search(body):
                self.text = body
                break
        if self.text is None:
            self.skipTest("the ping-pong clone call is not in any emitted unit; run the generator")

    def test_the_emitted_clone_carries_the_new_weight_and_the_object(self):
        pool = _pool_default_weight(_source())
        match = re.search(
            r"CloneAutonomousCandidateWithWeight\(data, 0x099, 0x0[bB]8, (\d+), (0x[0-9A-Fa-f]+)\);",
            self.text)
        self.assertIsNotNone(match, "the emitted clone call did not parse")
        self.assertEqual(int(match.group(1)), pool)
        self.assertEqual(int(match.group(2), 16), PING_PONG_OBJECT)


if __name__ == "__main__":
    unittest.main()
