#!/usr/bin/env python3
"""Career work must progress exactly as in the unpatched game.

Owner report: villagers do not work on their careers the way they do in the
vanilla game, so a career can never be maxed out. The owner wants the career
mechanics exactly vanilla while keeping the caption variations.

How a career advances in the stock game (all from the stock objects in
work/desktop_obj_files, which these tests decode):

* CVillager::InitAI makes kitchen (0x047), office (0x02C) and workshop (0x04B)
  work autonomous candidates with weight 500 (then +/-20%), min age 0x168,
  day-only and a career-type gate at +0x50. WorkKitchen0 (0x048) is NOT a
  candidate: it takes the default case, enabled flag 0. WorkKitchenDispatch
  always tail-calls WorkKitchen0, so 0x047 already reaches that plan.
* CVillager::LoadAI calls InitAI and then restores every candidate's SAVED
  weight, so praise (InvokeReward raises the current behaviour's +0x0C towards
  45000) survives a reload.
* CVillagerAI::RealtimeWorkDone, the catch-up run while the game was closed,
  reads the career row's weight and rolls weight/400 chances of 1 in 6 to call
  CVillagerSkills::AdvanceCareer. A trained weight therefore multiplies career
  progress; an untrained one gives a single roll.
* The live behaviours (OfficeCarreerWork, WorkKitchen0, WorkWorkshop) roll
  ChanceOfCareerSuccess and queue PlanToAdvanceCareer in their own plan.

Behavior Patches used to write weight 450 and min age 0x118 into all three
rows and clone 0x047 into 0x048 from its InitAI AND LoadAI hooks. The load-time
write erased praise training on every load, which pins the catch-up at one
roll forever; the 0x048 clone doubled kitchen selections and let praise land
on a row RealtimeWorkDone never reads.

These tests require the enabler to leave the four rows byte-for-byte as it
found them (compiled and executed, not pattern-matched), pin the stock facts
the fix relies on from the stock objects, and require the caption variations
to stay wired.
"""
import re
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

import capstone
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

import extract_emitted_behavior_cpp as emitted
import patch_mobile_furniture_pack as patcher
import test_generated_cpp_compiles as compiles
from coff_patch import CoffObject

HERE = Path(__file__).resolve().parent
STOCK_OBJS = HERE / "desktop_obj_files"
SOURCE = Path(patcher.__file__).read_text(encoding="utf-8")

CANDIDATE_BASE = 0x6BB8
CANDIDATE_SIZE = 0xD0
KITCHEN, KITCHEN0, OFFICE, WORKSHOP = 0x047, 0x048, 0x02C, 0x04B
CAREER_ROWS = (KITCHEN, KITCHEN0, OFFICE, WORKSHOP)
# A row the enabler is known to write (pool table, EnableAllAgesAutonomousCandidate).
# The harness must see it change, or it cannot see anything change.
KNOWN_WRITTEN_ROW = 0x099


def function_text(text, signature):
    start = text.index(signature)
    return text[start:text.index("\n}\n", start) + 3]


def code_only(body):
    return "\n".join(
        line.split("//")[0] for line in body.splitlines())


# --------------------------------------------------------------------------
# Executing the emitted enabler
# --------------------------------------------------------------------------

HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
%(stubs)s
%(helpers)s
%(enabler)s
int main() {
    const unsigned int size = 0x1C000;
    unsigned char *villager = (unsigned char *)malloc(size);
    unsigned char *before = (unsigned char *)malloc(size);
    unsigned int seed = 0x13579BDFu;
    for (unsigned int i = 0; i < size; ++i) {
        seed = seed * 1103515245u + 12345u;
        villager[i] = (unsigned char)(seed >> 16);
    }
    memcpy(before, villager, size);
    VF2EnableAutonomousCandidates(villager);
    unsigned int rows[] = { %(rows)s };
    for (unsigned int r = 0; r < sizeof(rows) / sizeof(rows[0]); ++r) {
        unsigned int off = 0x6BB8 + rows[r] * 0xD0, changed = 0;
        for (unsigned int i = 0; i < 0xD0; ++i) changed += villager[off + i] != before[off + i];
        printf("%%x %%u\n", rows[r], changed);
    }
    return 0;
}
'''


def enabler_harness_source(cpp):
    """The emitted enabler and its record helpers, with every other callee stubbed.

    The stubs only replace functions this harness cannot link (the per-decision
    refresh and the mobile-furniture enabler, which need the game). Those are
    checked separately below to name none of the career rows.
    """
    helpers_start = cpp.index("static void EnableAutonomousCandidateWithWeight(")
    clone_start = cpp.index("static void CloneAutonomousCandidateWithWeight(")
    helpers = cpp[helpers_start:cpp.index("\n}\n", clone_start) + 3]
    enabler = function_text(
        cpp, 'extern "C" void __cdecl VF2EnableAutonomousCandidates(void *villager)')
    defined = set(re.findall(r"static void (\w+)\(", helpers))
    called = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", code_only(enabler)))
    called -= defined | {"VF2EnableAutonomousCandidates", "if", "for", "while", "sizeof"}
    stubs = "\n".join("static void %s(...) {}" % name for name in sorted(called))
    rows = ", ".join("0x%X" % row for row in CAREER_ROWS + (KNOWN_WRITTEN_ROW,))
    return HARNESS % {"stubs": stubs, "helpers": helpers,
                      "enabler": enabler, "rows": rows}, sorted(called)


class TheEnablerLeavesCareerRowsAsStockLeftThem(unittest.TestCase):
    def test_executed_enabler_does_not_touch_any_career_row(self):
        vcvars = compiles._vcvars()
        if vcvars is None:
            self.skipTest("no Visual Studio toolchain on this machine")
        source, stubbed = enabler_harness_source(emitted.emitted_cpp())
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "harness.cpp").write_text(source, encoding="ascii")
            build = subprocess.run(
                '"%s" >nul 2>&1 && cd /d "%s" && cl /nologo /EHsc harness.cpp' % (vcvars, work),
                shell=True, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout[-2000:])
            run = subprocess.run([str(work / "harness.exe")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
        changed = {int(a, 16): int(b) for a, b in
                   (line.split() for line in run.stdout.splitlines())}
        self.assertGreater(
            changed[KNOWN_WRITTEN_ROW], 0,
            "the harness saw no write even to a row the enabler is known to "
            "configure, so it cannot detect a career-row write either")
        for row in CAREER_ROWS:
            with self.subTest(row=hex(row)):
                self.assertEqual(
                    changed[row], 0,
                    "VF2EnableAutonomousCandidates changed %d byte(s) of candidate "
                    "%#05x. It runs after LoadAI restores the saved weights, so any "
                    "write here erases praise training and changes career progress "
                    "(stubbed callees: %s)" % (changed[row], row, ", ".join(stubbed)))

    def test_no_other_emitted_candidate_writer_names_a_career_row(self):
        """The stubbed callees and every other candidate writer in the emitted units.

        The executed test above cannot run the per-decision refresh or the
        mobile-furniture enabler, so their candidate targets are read here from
        the same emitted text: every `0x6BB8 + <id> * 0xD0` and every
        Enable*/Clone* call, plus the mobile enabler's row table.
        """
        cpp = emitted.emitted_cpp()
        mobile = function_text(
            SOURCE, 'extern "C" void __cdecl VF2EnableMobileFurnitureCandidates(void *villager)')
        for name, text in (("spontaneous behaviours unit", code_only(cpp)),
                           ("mobile furniture enabler", code_only(mobile))):
            ids = {int(x, 16) for x in re.findall(r"0x6BB8 \+ (0x[0-9A-Fa-f]+) \* 0xD0", text)}
            for call in re.findall(r"(?:Enable\w*|Clone\w*)AutonomousCandidate\w*\(data, ([^;]*)\);", text):
                ids.update(int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]+", call)[:2])
            ids.update(int(x, 16) for x in re.findall(r"\{ (0x[0-9A-Fa-f]+), +\d+, (?:true|false) +\}", text))
            with self.subTest(unit=name):
                self.assertTrue(ids, "found no candidate writer at all; the scan is broken")
                self.assertEqual(sorted(ids & set(CAREER_ROWS)), [],
                                 "%s writes a career candidate row" % name)


# --------------------------------------------------------------------------
# The stock facts the fix relies on, decoded from the stock objects
# --------------------------------------------------------------------------

def _relocs(obj, sec):
    out = {}
    for i in range(sec.nreloc):
        vaddr, symidx, _ = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + i * 10)
        out[vaddr] = obj.symbol_by_index[symidx]
    return out


def _function_code(obj_name, symbol):
    obj = CoffObject(STOCK_OBJS / obj_name)
    sym = obj.symbol(symbol)
    sec = obj.section(sym.section)
    code = bytes(obj.buf[sec.raw_ptr:sec.raw_ptr + sec.raw_size])
    return obj, sym, sec, code


def stock_initai_records(ids):
    """Stock InitAI's 0xD0-byte record for each id: default fill, then its case."""
    obj, init, sec, code = _function_code("Villager.obj", "?InitAI@CVillager@@QAEXXZ")
    rel = _relocs(obj, sec)

    def resolved(off):
        return rel[off].value + struct.unpack_from("<I", code, off)[0]

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True

    def imm_writes(start, stop_at_indirect):
        for ins in md.disasm(code[start:start + 0x800], start):
            if ins.mnemonic == "jmp":
                return
            if ins.mnemonic == "mov" and ins.operands[0].type == X86_OP_MEM \
                    and ins.operands[1].type == X86_OP_IMM:
                disp = ins.operands[0].mem.disp
                if CANDIDATE_BASE <= disp < CANDIDATE_BASE + CANDIDATE_SIZE:
                    yield disp - CANDIDATE_BASE, ins.operands[0].size, ins.operands[1].imm
            if stop_at_indirect and ins.mnemonic == "movzx" and ins.operands[1].type == X86_OP_MEM:
                return

    defaults = list(imm_writes(init.value, True))
    t1 = t2 = None
    for ins in md.disasm(code[init.value:init.value + 0x400], init.value):
        if ins.mnemonic == "movzx" and t1 is None and ins.operands[1].type == X86_OP_MEM:
            t1 = resolved(ins.address + ins.size - 4)
        if ins.mnemonic == "jmp" and ins.operands[0].type == X86_OP_MEM:
            t2 = resolved(ins.address + ins.size - 4)
            break
    cases = {bid: resolved(t2 + 4 * code[t1 + bid - 2]) for bid in range(2, 0x19A)}
    counts = {}
    for off in cases.values():
        counts[off] = counts.get(off, 0) + 1
    default_case = max(counts, key=counts.get)
    records = {}
    for bid in ids:
        mem = bytearray(CANDIDATE_SIZE)
        for field, size, value in defaults:
            mem[field:field + size] = (value & ((1 << 8 * size) - 1)).to_bytes(size, "little")
        is_default = cases[bid] == default_case
        if not is_default:
            for field, size, value in imm_writes(cases[bid], False):
                mem[field:field + size] = (value & ((1 << 8 * size) - 1)).to_bytes(size, "little")
        records[bid] = (is_default, mem)
    return records


class TheStockGameDrivesCareersThroughTheseRows(unittest.TestCase):
    def test_stock_initai_career_rows(self):
        records = stock_initai_records(CAREER_ROWS)
        for row, career in ((KITCHEN, 1), (OFFICE, 2), (WORKSHOP, 3)):
            with self.subTest(row=hex(row)):
                is_default, mem = records[row]
                self.assertFalse(is_default)
                self.assertEqual(mem[0xCD], 1, "stock already makes career work autonomous")
                self.assertEqual(struct.unpack_from("<I", mem, 0x0C)[0], 500)
                self.assertEqual(struct.unpack_from("<I", mem, 0x4C)[0], 0x168)
                self.assertEqual(struct.unpack_from("<i", mem, 0x50)[0], career)
                self.assertEqual(mem[0x04], 1, "career work is day-only in stock")
        is_default, mem = records[KITCHEN0]
        self.assertTrue(is_default, "WorkKitchen0 has no InitAI case of its own")
        self.assertEqual(mem[0xCD], 0, "WorkKitchen0 is not a stock autonomous candidate")

    def test_realtime_work_reads_the_career_rows_weight(self):
        """RealtimeWorkDone's catch-up scales with the career row's +0x0C."""
        _obj, sym, _sec, code = _function_code(
            "VillagerAI.obj", "?RealtimeWorkDone@CVillagerAI@@QAEXAAVCVillager@@@Z")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.detail = True
        loads, magic, shift = [], None, None
        for ins in md.disasm(code[sym.value:sym.value + 0xA0], sym.value):
            if ins.mnemonic == "mov" and ins.op_str.startswith("esi, dword ptr [edi +"):
                loads.append(ins.operands[1].mem.disp)
            if ins.mnemonic == "mov" and ins.op_str.startswith("eax, 0x51eb851f"):
                magic = True
            if ins.mnemonic == "sar" and ins.op_str.startswith("edx,"):
                shift = ins.operands[1].imm
            if ins.mnemonic == "ret":
                break
        weight = lambda row: CANDIDATE_BASE + row * CANDIDATE_SIZE + 0x0C  # noqa: E731
        # Career types 3, 2, 1 in code order (the switch falls through to workshop first).
        self.assertEqual(loads, [weight(WORKSHOP), weight(OFFICE), weight(KITCHEN)])
        self.assertTrue(magic and shift == 7, "weight / 400 (0x51EB851F, sar 7) not found")

    def test_loadai_restores_saved_weights_after_initai(self):
        _obj, sym, _sec, code = _function_code(
            "Villager.obj", "?LoadAI@CVillager@@QAEXAAUSSaveState@1@@Z")
        body = code[sym.value:sym.value + 0x60]
        self.assertIn(b"\x8d\x8f\xc4\x6b\x00\x00", body,
                      "LoadAI no longer walks the candidate weights at +0x6BC4")


class CareerCaptionsStillVary(unittest.TestCase):
    """The owner wants the label variations kept; they come from the macro retargets."""

    def test_career_macro_rows_are_retargeted_to_label_wrappers(self):
        table = SOURCE[SOURCE.index("def patch_behavior_label_variants(manifest):"):]
        table = table[:table.index("\ndef ", 10)]
        for offset, row, helper in (
                ("0x3B0", "0x047", "_VF2RandomKitchenCareerDispatchLabel"),
                ("0x3BE", "0x048", "_VF2RandomKitchenCareerLabel"),
                ("0x225", "0x02C", "_VF2RandomOfficeCareerLabel"),
                ("0x3E8", "0x04B", "_VF2RandomWorkshopCareerLabel")):
            with self.subTest(row=row):
                self.assertRegex(
                    code_only(table),
                    r'retarget\(%s, %s, "%s",' % (offset, row, helper))

    def test_wrappers_run_the_native_behaviour_before_relabelling(self):
        cpp = code_only(emitted.emitted_cpp())
        for wrapper, native in (
                ("VF2RandomKitchenCareerDispatchLabel", "WorkKitchenDispatch"),
                ("VF2RandomKitchenCareerLabel", "WorkKitchen0"),
                ("VF2RandomOfficeCareerLabel", "OfficeCarreerWork"),
                ("VF2RandomWorkshopCareerLabel", "WorkWorkshop")):
            with self.subTest(wrapper=wrapper):
                body = function_text(cpp, 'extern "C" void __cdecl %s(CVillager &villager)' % wrapper)
                run = body.index("VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::%s)" % native)
                relabel = body.index("VF2ApplyRememberedOrRandomLabel(villager, kVF2BehaviorLabels_career")
                self.assertLess(run, relabel)
                self.assertNotIn("ForgetPlans", body, "a career wrapper must not drop the native plan")


if __name__ == "__main__":
    unittest.main()
