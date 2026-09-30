#!/usr/bin/env python3
"""Every autonomous candidate the patch enables must require its furniture.

CVillagerAI::DecideWhatToDo asks ContentMap.ObjectExists(candidate[+0xC4])
only when +0xC4 is non-zero:

    mov  eax, [edi+esi+6C7Ch]    ; 0x6BB8 + 0xC4
    test eax, eax / je  skip
    push eax / call ?ObjectExists@CContentMap@@QAE?B_NW4EObject@1@@Z
    test al, al / je  reject

Stock CVillager::InitAI writes +0xC4 only in the switch cases of candidates it
configures. A candidate that falls to the SHARED DEFAULT case keeps +0xC4 = 0,
so when the patch enables it, it is offered in any house -- with or without
the furniture. The native behaviour then runs anyway (foosball plays on the
spot, the fireplace and easel routes animate at nothing, the couch and kids
table routes refuse, the arcade routes waste the decision).

Both halves are decoded from the repository's build inputs rather than
asserted from memory:

* the stock InitAI record of every enabled id (default case or not, and its
  own +0xC4), from work/desktop_obj_files/Villager.obj;
* the object each native behaviour's FIRST furniture lookup
  (FindFurniture or LinkPeepToFurniture) searches, from Behavior.obj.

Every enabled, non-cloned id whose stock record is the default must then be
given exactly the object its own behaviour looks for, or be listed below with
the reason it needs no object.
"""
import re
import struct
import unittest
from pathlib import Path

import capstone
from capstone.x86 import X86_OP_IMM

import patch_mobile_furniture_pack as patcher
import stock_initai_decode
from coff_patch import CoffObject

SOURCE = Path(patcher.__file__).read_text(encoding="utf-8")
OBJS = Path(patcher.SRC_OBJS)

# Enabled default-case candidates that deliberately carry no single +0xC4.
NO_SINGLE_OBJECT = {
    # PlayingPinballGames searches the pinball machine (0x0C), then slots
    # (0x0A), then pachinko (0x27). One +0xC4 cannot say "any of these", so
    # VF2RefreshPinballGamesEligibility gates it per decision instead.
    0x0DC: (0x0C, 0x0A, 0x27),
}


def function_body(signature):
    start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index("\n}\n", start)]


def code_only(text):
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("//"))


def enabled_rows():
    """{behavior id: 'enable' | 'clone'} from VF2EnableAutonomousCandidates."""
    body = code_only(function_body(
        'extern "C" void __cdecl VF2EnableAutonomousCandidates(void *villager)'))
    rows = {}
    for m in re.finditer(r"^\s*(Enable\w+|Clone\w+)\(data, (0x[0-9A-F]+)(?:, (0x[0-9A-F]+))?",
                         body, re.M):
        if m.group(1).startswith("Clone"):
            rows[int(m.group(3), 16)] = "clone"
        else:
            rows.setdefault(int(m.group(2), 16), "enable")
    return rows


def required_objects():
    body = code_only(function_body(
        'extern "C" void __cdecl VF2EnableAutonomousCandidates(void *villager)'))
    found = re.findall(r"RequireAutonomousCandidateObject\(data, (0x[0-9A-F]+), (0x[0-9A-F]+)\);", body)
    return {int(a, 16): int(b, 16) for a, b in found}


def native_lookup_objects():
    """{behavior id: [objects pushed to each FindFurniture/LinkPeepToFurniture]}."""
    obj = CoffObject(OBJS / "Behavior.obj")
    ctor = obj.symbol("??0CBehavior@@QAE@XZ")
    sec = obj.section(ctor.section)
    code = bytes(obj.buf[sec.raw_ptr:sec.raw_ptr + sec.raw_size])
    relocs = {}
    for i in range(sec.nreloc):
        vaddr, symidx, _ = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + i * 10)
        relocs[vaddr] = obj.symbol_by_index[symidx]
    handlers = {}
    for off in sorted(relocs):
        if off < 1 or code[off - 1] != 0x68:
            continue
        nxt = off + 4
        if code[nxt] == 0x6A:
            bid = code[nxt + 1]
        elif code[nxt] == 0x68 and nxt + 1 not in relocs:
            bid = struct.unpack_from("<I", code, nxt + 1)[0]
        else:
            continue
        handlers.setdefault(bid, relocs[off].name)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    lookups = {}
    for bid, name in handlers.items():
        fn = obj.symbol_by_name.get(name)
        if fn is None or fn.section <= 0:
            continue
        fsec = obj.section(fn.section)
        fcode = bytes(obj.buf[fsec.raw_ptr:fsec.raw_ptr + fsec.raw_size])
        frelocs = {}
        for i in range(fsec.nreloc):
            vaddr, symidx, _ = struct.unpack_from("<IIH", obj.buf, fsec.reloc_ptr + i * 10)
            frelocs[vaddr] = obj.symbol_by_index[symidx].name
        last_push = None
        objects = []
        for ins in md.disasm(fcode[fn.value:], fn.value):
            if ins.mnemonic == "push" and ins.operands[0].type == X86_OP_IMM:
                last_push = ins.operands[0].imm
            if ins.mnemonic == "call":
                target = frelocs.get(ins.address + 1, "")
                if "?FindFurniture@CFurnitureManager@@" in target or \
                        "?LinkPeepToFurniture@CFurnitureManager@@" in target:
                    objects.append(last_push)
            if ins.mnemonic == "ret":
                break
        lookups[bid] = objects
    return handlers, lookups


@unittest.skipUnless((OBJS / "Villager.obj").is_file() and (OBJS / "Behavior.obj").is_file(),
                     "work/desktop_obj_files is not present in this checkout")
class EveryEnabledCandidateRequiresItsFurniture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.default, cls.fields, cls.cases = stock_initai_decode.decode(OBJS / "Villager.obj")
        cls.handlers, cls.lookups = native_lookup_objects()
        cls.rows = enabled_rows()
        cls.required = required_objects()

    def test_the_decoders_agree_with_known_stock_records(self):
        """Guard the decoders themselves against silently decoding nothing."""
        self.assertEqual(self.fields[0x023].get(0xC4), 0x5B, "hammock")
        self.assertEqual(self.fields[0x099].get(0xC4), 0x36, "pool table")
        self.assertEqual(self.fields[0x0DD].get(0xC4), 0x0C, "pinball")
        self.assertEqual(self.cases[0x096], self.default, "foosball has no case")
        self.assertIn("PlayingFoosball", self.handlers[0x096])
        self.assertEqual(self.lookups[0x096][0], 0x2D)

    def test_every_default_case_row_requires_an_object(self):
        missing = []
        for bid, how in sorted(self.rows.items()):
            if how == "clone" or self.cases.get(bid) != self.default:
                continue
            if bid in NO_SINGLE_OBJECT or bid in self.required:
                continue
            missing.append(hex(bid))
        self.assertEqual(missing, [],
                         "these enabled candidates keep stock +0xC4 = 0 and are "
                         "offered in houses without their furniture")

    def test_each_required_object_is_the_native_lookup_object(self):
        for bid, obj in sorted(self.required.items()):
            with self.subTest(behavior=hex(bid), handler=self.handlers.get(bid)):
                self.assertIn(bid, self.rows, "requires an object for a row it never enables")
                self.assertEqual(self.cases.get(bid), self.default,
                                 "stock InitAI already configures this record")
                self.assertTrue(self.lookups.get(bid), "native behaviour has no furniture lookup")
                self.assertEqual(obj, self.lookups[bid][0],
                                 "not the object the native behaviour searches first")

    def test_the_pinball_games_refresh_checks_every_machine(self):
        self.assertEqual(tuple(self.lookups[0x0DC][:3]), NO_SINGLE_OBJECT[0x0DC])
        body = code_only(function_body(
            "static void VF2RefreshPinballGamesEligibility(unsigned char *data)"))
        self.assertIn("data + 0x6BB8 + 0x0DC * 0xD0", body)
        for obj in NO_SINGLE_OBJECT[0x0DC]:
            self.assertIn("ContentMap.ObjectExists((CContentMap::EObject)0x%02X)" % obj, body)
        self.assertIn("candidate[0xCD] = (unsigned char)(anyMachine ? 1 : 0);", body)
        self.assertNotIn("+ 0x0C)", body, "the refresh must not touch the weight")
        # Per decision: in the hook itself, or in a helper the hook calls (the
        # refresh body may be factored into one, as the trained-weights change
        # does with VF2RefreshVolatileCandidates).
        hook = code_only(function_body(
            'extern "C" void __cdecl VF2RefreshHammockEligibility(void *villager)'))
        reached = [hook]
        for callee in set(re.findall(r"\b(VF2\w+)\(", hook)):
            m = re.search(r"\nstatic void %s\([^)]*\)\n\{" % callee, SOURCE)
            if m:
                reached.append(code_only(SOURCE[m.start():SOURCE.index("\n}\n", m.start())]))
        self.assertTrue(
            any("VF2RefreshPinballGamesEligibility(data);" in body for body in reached),
            "the any-of gate is not re-evaluated per decision")

    def test_the_emitted_helper_writes_the_required_object_field(self):
        """Run the helper: it must write +0xC4 of exactly that candidate."""
        import subprocess
        import tempfile
        import test_generated_cpp_compiles as compiles
        vcvars = compiles._vcvars()
        if vcvars is None:
            self.skipTest("no Visual Studio toolchain on this machine")
        start = SOURCE.index("static void RequireAutonomousCandidateObject(")
        helper = SOURCE[start:SOURCE.index("\n}\n", start) + 3]
        harness = (
            "#include <stdio.h>\n#include <string.h>\n" + helper +
            "static unsigned char v[0x6BB8 + 0x19B * 0xD0];\n"
            "int main() {\n"
            "    memset(v, 0, sizeof v);\n"
            "    RequireAutonomousCandidateObject(v, 0x096, 0x2D);\n"
            "    unsigned int *hit = (unsigned int *)(v + 0x6BB8 + 0x096 * 0xD0 + 0xC4);\n"
            "    int others = 0;\n"
            "    for (unsigned int i = 0; i < sizeof v; ++i) others += v[i] != 0;\n"
            "    printf(\"%u %d\\n\", *hit, others);\n"
            "    return 0;\n}\n")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "h.cpp").write_text(harness, encoding="ascii")
            build = subprocess.run(
                '"%s" >nul 2>&1 && cd /d "%s" && cl /nologo /EHsc h.cpp' % (vcvars, work),
                shell=True, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout[-1500:])
            run = subprocess.run([str(work / "h.exe")], capture_output=True, text=True)
        self.assertEqual(run.stdout.split(), ["45", "1"],
                         "the helper must write 0x2D into +0xC4 of candidate 0x096 "
                         "and nothing else")

    def test_object_exists_is_declared_with_the_native_mangling(self):
        # ?ObjectExists@CContentMap@@QAE?B_NW4EObject@1@@Z returns `const
        # bool`; plain `bool` would mangle differently and fail to LINK.
        self.assertIn("    const bool ObjectExists(EObject object);", SOURCE)


if __name__ == "__main__":
    unittest.main()
