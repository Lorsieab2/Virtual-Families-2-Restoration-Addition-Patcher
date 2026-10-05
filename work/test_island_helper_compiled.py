#!/usr/bin/env python3
"""The island-event helper as COMPILED, not as source text (Codex on PR #418).

The source-level tests in test_patch_mobile_furniture_pack.py search the
emitted vf2_island_events.cpp. A stale object can still satisfy the link
checks, so these regenerate the helper from the current generator into a
temporary directory, compile it with the build's own flags
(work/compile_helpers_b22.rsp: /nologo /c /O2), and decode the machine code
the executable will actually contain:

* Virtual Scouts is registered into slot 0x7A with its stock strings
  0x944-0x949, choices on, not an email, outcome kind 26.
* Its ImpactGame branch: OK gives AdjustHappiness(5) to each living resident
  and calls MakeAllVillagersDoIt(100, 7, 7, any, 0, 0); What rats? calls
  FoodStore.Adjust(-100).
* Power Failure: CalcAward rolls GetRandom(4) and takes B2 only on 0, claims
  a free state slot for the event (the defect found live on 2026-10-04), and
  ImpactGame calls GiveAllVillagersSymptom(2, 15).
"""
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher
from coff_patch import CoffObject
from test_generated_cpp_compiles import _vcvars

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
except ImportError:  # pragma: no cover - the toolchain machine has it
    Cs = None

ROOT = Path(patcher.__file__).resolve().parents[1]
IMMEDIATE = re.compile(r"^-?(0x[0-9a-f]+|\d+)$")
RSP = ROOT / "work" / "compile_helpers_b22.rsp"


def build_flags():
    """The compiler switches the real build passes, from its response file."""
    flags = [tok for tok in RSP.read_text(encoding="utf-8").split()
             if tok.startswith("/") and not tok.startswith("/Fo")]
    assert "/O2" in flags and "/c" in flags, flags
    return flags


class Disassembly:
    def __init__(self, obj_path):
        self.obj = CoffObject(obj_path)
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)

    def function(self, name):
        """[(mnemonic, op_str, relocation target name or '')] for a symbol."""
        matches = [s for s in self.obj.symbols if s.name == name and s.section > 0]
        assert len(matches) == 1, (name, len(matches))
        sym = matches[0]
        sec = self.obj.section(sym.section)
        relocs = {}
        for i in range(sec.nreloc):
            va, symidx, _ = struct.unpack_from("<IIH", self.obj.buf, sec.reloc_ptr + i * 10)
            relocs[va] = self.obj.symbol_by_index[symidx].name
        code = bytes(self.obj.buf[sec.raw_ptr:sec.raw_ptr + sec.raw_size])
        out = []
        for ins in self.md.disasm(code[sym.value:], sym.value):
            target = next((relocs[a] for a in range(ins.address, ins.address + ins.size)
                           if a in relocs), "")
            out.append((ins.mnemonic, ins.op_str, target))
        return out


def pushes_before_call(insns, callee_fragment):
    """For each call whose relocation names callee_fragment, the immediate
    pushes since the previous call, in push order."""
    result = []
    pushes = []
    for mnemonic, op_str, target in insns:
        if mnemonic == "push" and IMMEDIATE.match(op_str):
            pushes.append(op_str)
        if mnemonic in ("call", "jmp") and target:
            if callee_fragment in target:
                result.append(list(pushes))
            pushes = []
    return result


def compile_fresh_helper(vcvars):
    """Regenerate vf2_island_events.cpp from the current generator into a
    temporary directory and compile it with the build's own flags. Returns
    (TemporaryDirectory, Disassembly of the fresh object)."""
    holder = tempfile.TemporaryDirectory()
    tmp = Path(holder.name)
    old = patcher.PATCHED
    try:
        patcher.PATCHED = tmp
        shutil.copy2(patcher.SRC_OBJS / "IslandEvents.obj", tmp / "IslandEvents.obj")
        manifest = {}
        patcher.patch_island_events(manifest)
        patcher.patch_power_failure_event(manifest)
    finally:
        patcher.PATCHED = old
    flags = " ".join(build_flags())
    result = subprocess.run(
        f'"{vcvars}" >nul 2>&1 && cd /d "{tmp}" && cl {flags} vf2_island_events.cpp',
        shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        holder.cleanup()
        raise AssertionError("vf2_island_events.cpp does not compile:\n" + result.stdout[-2000:])
    return holder, Disassembly(tmp / "vf2_island_events.obj")


class CompiledIslandHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vcvars = _vcvars()
        if cls.vcvars is None or Cs is None:
            raise unittest.SkipTest("no Visual Studio toolchain or capstone on this machine")
        cls.tmp, cls.dis = compile_fresh_helper(cls.vcvars)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_virtual_scouts_is_registered_into_slot_0x7a(self):
        insns = self.dis.function("_VF2RegisterMobileIslandEvents")
        # The Virtual Scouts object: its six string ids at +0x14..+0x28,
        # choices on at +0x2C (word 1 = has_choices true, is_email false),
        # outcome kind 26 at +0x30, then stored to slots[0x19] = slot 0x7A
        # (the helper receives &mEventList[0x61]).
        text = [f"{m} {o}" for m, o, _ in insns]
        start = text.index("mov dword ptr [eax + 0x14], 0x944")
        block = text[start:start + 10]
        self.assertEqual(block, [
            "mov dword ptr [eax + 0x14], 0x944",
            "mov dword ptr [eax + 0x18], 0x945",
            "mov dword ptr [eax + 0x1c], 0x946",
            "mov dword ptr [eax + 0x20], 0x947",
            "mov dword ptr [eax + 0x24], 0x948",
            "mov dword ptr [eax + 0x28], 0x949",
            "mov word ptr [eax + 0x2c], 1",
            "mov dword ptr [eax + 0x30], 0x1a",
            "mov dword ptr [esi + 0x64], eax",
            "pop esi",
        ])

    def test_virtual_scouts_outcomes_in_the_compiled_impact_game(self):
        insns = self.dis.function("?ImpactGame@CMobileIslandEvent@@QAEXH@Z")
        text = [f"{m} {o}" for m, o, _ in insns]
        start = text.index("cmp eax, 0x1a")
        end = text.index("cmp eax, 0x19", start)
        block = insns[start:end]
        # OK: +5 happiness for each living resident, then everyone celebrates.
        self.assertEqual(pushes_before_call(block, "AdjustHappiness@CVillagerState"), [["5"]])
        self.assertIn(("cmp", "dword ptr [eax + 0x6b00], 0", ""), block)
        self.assertEqual(
            pushes_before_call(block, "MakeAllVillagersDoIt"),
            [["0", "0", "-1", "7", "7", "0x64"]])  # count, ids, gender any, 7, 7, Celebrate
        # What rats?: FoodStore.Adjust(-100), tail-called with the argument
        # rewritten in place.
        rats = [i for i, (m, o, t) in enumerate(block) if "Adjust@CFoodStore" in t]
        self.assertEqual(len(rats), 1)
        self.assertEqual(block[rats[0] - 2][:2], ("mov", "dword ptr [esp + 4], 0xffffff9c"))
        # Choice 0 is OK: the branch tests the choice and jumps to the rats
        # path only when it is non-zero.
        self.assertEqual(block[2][:2], ("cmp", "dword ptr [esp + 0x10], 0"))
        self.assertEqual(block[3][0], "jne")

    def test_power_failure_rolls_one_in_four(self):
        insns = self.dis.function("_VF2PowerFailureCalcAward")
        self.assertEqual(pushes_before_call(insns, "GetRandom@ldwGameState"), [["4"]])
        after = [i for i, (m, o, t) in enumerate(insns) if "GetRandom" in t][0]
        self.assertEqual([m for m, _, _ in insns[after + 1:after + 4]], ["add", "test", "jne"])

    def test_power_failure_claims_the_free_state_slot(self):
        insns = self.dis.function("_VF2PowerFailureCalcAward")
        event_reg = next(o.split(",")[0] for m, o, _ in insns
                         if m == "mov" and o.endswith("dword ptr [esp + 8]"))
        stores = [o for m, o, _ in insns
                  if m == "mov" and o.startswith("dword ptr [e") and o.endswith(f"], {event_reg}")]
        # One store into a free slot, one into the round-robin replacement.
        # The pre-fix helper returned the free slot unclaimed: one store.
        self.assertEqual(len(stores), 2, stores)

    def test_power_failure_symptom_is_fifteen_percent(self):
        insns = self.dis.function("_VF2PowerFailureImpactGame")
        self.assertEqual(
            pushes_before_call(insns, "GiveAllVillagersSymptom"), [["0xf", "2"]])


LINKED_FUNCTIONS = (
    "_VF2RegisterMobileIslandEvents",
    "?ImpactGame@CMobileIslandEvent@@QAEXH@Z",
    "_VF2PowerFailureCalcAward",
    "_VF2PowerFailureImpactGame",
    "_VF2PowerFailureGetResultDescription",
)


def newest_linked_all_enabled_exe():
    """The newest matrix build's all-enabled executable, or None.

    outputs/ is this checkout's own (git-ignored) build folder."""
    candidates = sorted(
        (ROOT / "outputs").glob("VF2-B*-matrix-final_all_enabled/*.exe"),
        key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def executable_ranges(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    image_base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    for i in range(count):
        o = pe + 24 + opt + i * 40
        _vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, o + 8)
        if struct.unpack_from("<I", data, o + 36)[0] & 0x20000000:
            yield image_base + va, raw_ptr, raw_size


class LinkedIslandHelper(unittest.TestCase):
    """Codex on PR #420: the compiled object is not what players install.

    Each helper body compiled above (its relocated fields as wildcards) must
    occur exactly once in the LINKED executable of the newest all-enabled
    matrix build, and must be reached by a rel32 call or jmp -- the
    IslandEvents detours, the CIslandEvents constructor hook and the
    ImpactGame thunk. A build that linked a stale helper, dropped it, or lost
    a detour fails here.
    """

    @classmethod
    def setUpClass(cls):
        vcvars = _vcvars()
        if vcvars is None or Cs is None:
            raise unittest.SkipTest("no Visual Studio toolchain or capstone on this machine")
        cls.exe = newest_linked_all_enabled_exe()
        if cls.exe is None:
            raise unittest.SkipTest("no matrix build in outputs/; run work/build_matrix.ps1")
        if cls.exe.stat().st_mtime < Path(patcher.__file__).stat().st_mtime:
            raise unittest.SkipTest(
                f"{cls.exe.parent.name} predates the generator; rebuild before trusting this check")
        cls.tmp, cls.dis = compile_fresh_helper(vcvars)
        cls.data = cls.exe.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def body_pattern(self, name):
        obj = self.dis.obj
        sym = [s for s in obj.symbols if s.name == name and s.section > 0][0]
        sec = obj.section(sym.section)
        code = bytes(obj.buf[sec.raw_ptr + sym.value:sec.raw_ptr + sec.raw_size])
        wild = set()
        for i in range(sec.nreloc):
            va, _, _ = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + i * 10)
            if va >= sym.value:
                wild.update(range(va - sym.value, va - sym.value + 4))
        return re.compile(b"".join(b"." if i in wild else re.escape(bytes([b]))
                                   for i, b in enumerate(code)), re.S)

    def test_each_helper_is_linked_once_and_reached(self):
        data = self.data
        ranges = list(executable_ranges(data))
        for name in LINKED_FUNCTIONS:
            with self.subTest(name):
                pattern = self.body_pattern(name)
                hits = [va + m.start() - raw
                        for va, raw, size in ranges
                        for m in pattern.finditer(data, raw, raw + size)]
                self.assertEqual(len(hits), 1, f"{name}: {len(hits)} linked copies")
                target = hits[0]
                callers = [
                    va + i - raw
                    for va, raw, size in ranges
                    for i in range(raw, raw + size - 5)
                    if data[i] in (0xE8, 0xE9)
                    and va + i - raw + 5 + struct.unpack_from("<i", data, i + 1)[0] == target
                ]
                self.assertTrue(callers, f"{name} is linked but nothing reaches it")


if __name__ == "__main__":
    unittest.main()
