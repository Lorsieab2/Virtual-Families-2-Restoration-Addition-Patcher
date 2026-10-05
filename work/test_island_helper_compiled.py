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
import hashlib
import json
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


IMAGE_REL_I386_DIR32 = 0x06
IMAGE_REL_I386_REL32 = 0x14


def current_release():
    """The newest release with recorded variant identities: (identities,
    island-events variant names). Provenance comes from these records, not
    from file dates."""
    def number(path):
        return int(re.search(r"B(\d+)", path.name).group(1))
    records = sorted((ROOT / "data" / "vf2").glob("release-identities-B*.json"), key=number)
    identities = json.loads(records[-1].read_text(encoding="utf-8"))
    toggles = json.loads((ROOT / "data" / "vf2" / "build-matrix-toggles.json").read_text(encoding="utf-8"))
    return identities, [v["name"] for v in toggles["variants"] if v["island_events"]]


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


def section_pattern(obj, secno):
    """A whole COFF code section as a regex (relocated fields wildcarded),
    plus its relocations as (offset, target symbol, type)."""
    sec = obj.section(secno)
    code = bytes(obj.buf[sec.raw_ptr:sec.raw_ptr + sec.raw_size])
    wild = set()
    relocs = []
    for i in range(sec.nreloc):
        off, symidx, rtype = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + i * 10)
        wild.update(range(off, off + 4))
        relocs.append((off, obj.symbol_by_index[symidx].name, rtype))
    pattern = re.compile(b"".join(b"." if i in wild else re.escape(bytes([b]))
                                  for i, b in enumerate(code)), re.S)
    return pattern, relocs


def locate(data, pattern):
    """Every (virtual address, file offset) where the section occurs."""
    return [(va + m.start() - raw, m.start())
            for va, raw, size in executable_ranges(data)
            for m in pattern.finditer(data, raw, raw + size)]


def defining_object(name):
    """(CoffObject, symbol) defining a stock function, from the generator's
    patched objects first and the untouched desktop objects second."""
    for folder in (patcher.PATCHED, patcher.SRC_OBJS):
        for path in sorted(Path(folder).glob("*.obj")):
            if name.encode() not in path.read_bytes():
                continue
            obj = CoffObject(path)
            sym = [s for s in obj.symbols if s.name == name and s.section > 0]
            if sym:
                return obj, sym[0]
    return None


class LinkedIslandHelper(unittest.TestCase):
    """Codex on PRs #420 and #422: check what players install, not an object.

    For every island-events variant of the current release (selected by its
    identity record, and its executable's SHA-256 checked against it):

    * each helper's code section, compiled fresh from the current generator,
      occurs exactly once in the linked executable;
    * every call the helper makes resolves, at its relocation's exact operand
      offset, to the located definition of the named function: another helper,
      or the stock function located from its own object file (functions too
      small to locate uniquely are listed and skipped);
    * every data reference to the same global resolves to one address;
    * every hook the patched IslandEvents.obj installs -- the CIslandEvents
      constructor and Power Failure's CalcAward, GetResultDescription and
      ImpactGame -- sits in that stock method's own linked section and
      resolves to the right helper.
    """

    @classmethod
    def setUpClass(cls):
        vcvars = _vcvars()
        if vcvars is None or Cs is None:
            raise unittest.SkipTest("no Visual Studio toolchain or capstone on this machine")
        cls.identities, cls.variants = current_release()
        prefix = cls.identities["matrix_prefix"]
        cls.exes = {}
        for name in cls.variants:
            found = sorted((ROOT / "outputs" / f"{prefix}-{name}").glob("*.exe"))
            if found:
                cls.exes[name] = found[0]
        if not cls.exes:
            raise unittest.SkipTest(f"{prefix} is not built in outputs/; run work/build_matrix.ps1")
        cls.tmp, cls.dis = compile_fresh_helper(vcvars)
        cls.helper = cls.dis.obj
        cls.island = CoffObject(Path(cls.tmp.name) / "IslandEvents.obj")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_island_variant_of_the_release_is_built(self):
        self.assertEqual(sorted(self.exes), sorted(self.variants))

    def test_executables_match_the_release_identities(self):
        expected = {v["variant"]: v["sha256"] for v in self.identities["variants"]}
        for name, exe in self.exes.items():
            with self.subTest(name):
                self.assertEqual(hashlib.sha256(exe.read_bytes()).hexdigest(), expected[name])

    def test_helpers_calls_and_hooks_resolve_in_every_variant(self):
        helper_sections = {}
        for fn in LINKED_FUNCTIONS:
            sym = [s for s in self.helper.symbols if s.name == fn and s.section > 0][0]
            helper_sections[fn] = (sym,) + section_pattern(self.helper, sym.section)
        stock = {}
        unlocatable = set()
        for name, exe in self.exes.items():
            data = exe.read_bytes()
            with self.subTest(name):
                located = {}
                for fn, (sym, pattern, relocs) in helper_sections.items():
                    hits = locate(data, pattern)
                    self.assertEqual(len(hits), 1, f"{fn}: {len(hits)} linked copies")
                    located[fn] = (hits[0][0] + sym.value, hits[0], relocs)
                globals_seen = {}
                for fn, (_addr, (va, raw), relocs) in located.items():
                    sec = self.helper.section(helper_sections[fn][0].section)
                    for off, target, rtype in relocs:
                        value = struct.unpack_from("<I", data, raw + off)[0]
                        if rtype == IMAGE_REL_I386_DIR32:
                            # The object holds the addend (e.g. +4 into an
                            # array); the symbol's own address is the rest.
                            addend = struct.unpack_from("<I", self.helper.buf, sec.raw_ptr + off)[0]
                            globals_seen.setdefault(target, set()).add((value - addend) & 0xFFFFFFFF)
                            continue
                        if rtype != IMAGE_REL_I386_REL32 or not target.startswith(("?", "_VF2")):
                            continue
                        dest = va + off + 4 + struct.unpack_from("<i", data, raw + off)[0]
                        if target in located:
                            self.assertEqual(dest, located[target][0], f"{fn} -> {target}")
                            continue
                        if target not in stock:
                            found = defining_object(target)
                            stock[target] = (found[1].value,) + section_pattern(found[0], found[1].section)[:1] if found else None
                        if stock[target] is None:
                            unlocatable.add(target)
                            continue
                        value_in_section, pattern = stock[target]
                        hits = locate(data, pattern)
                        if len(hits) != 1:
                            unlocatable.add(target)
                            continue
                        self.assertEqual(dest, hits[0][0] + value_in_section, f"{fn} -> {target}")
                for target, values in globals_seen.items():
                    self.assertEqual(len(values), 1, f"{target} resolves to {len(values)} addresses")
                hooks = 0
                for secno in range(1, len(self.island.sections) + 1):
                    if not self.island.section(secno).name.startswith(".text"):
                        continue
                    pattern, relocs = section_pattern(self.island, secno)
                    to_helpers = [(off, tg) for off, tg, rt in relocs
                                  if rt == IMAGE_REL_I386_REL32 and tg in LINKED_FUNCTIONS]
                    if not to_helpers:
                        continue
                    hits = locate(data, pattern)
                    self.assertEqual(len(hits), 1, f"IslandEvents section {secno}: {len(hits)} copies")
                    va, raw = hits[0]
                    for off, target in to_helpers:
                        dest = va + off + 4 + struct.unpack_from("<i", data, raw + off)[0]
                        self.assertEqual(dest, located[target][0], f"hook -> {target}")
                        hooks += 1
                # The constructor registration and the three Power Failure
                # lifecycle detours.
                self.assertEqual(hooks, 4)
        # Only tiny stock functions may be unlocatable, and the ones the new
        # behaviour depends on must not be.
        for needed in ("?GiveAllVillagersSymptom@CVillagerManager@@QAEXW4ESymptom@@H@Z",
                       "?GetRandom@ldwGameState@@SAHH@Z",
                       "?AdjustHappiness@CVillagerState@@QAEXH@Z",
                       "?Adjust@CFoodStore@@QAEXH@Z",
                       "?MakeAllVillagersDoIt@CVillagerManager@@QAEXW4EBehavior@@HHW4EGender@@PAHH@Z"):
            self.assertNotIn(needed, unlocatable)


if __name__ == "__main__":
    unittest.main()
