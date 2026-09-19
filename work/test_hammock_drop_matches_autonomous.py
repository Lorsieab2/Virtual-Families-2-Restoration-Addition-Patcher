"""The manual hammock drop acts exactly like the autonomous hammock rest.

Owner request, for the base hammock (0x1E1) and the Invisible Hammock (0x30C):
"change the manual hammock drop behavior so it acts identically to the
autonomous one ... i like them sleeping for long periods of time".

GROUND TRUTH, decoded from Behavior.obj with dumpbin. The two native routes
were never the same routine:

    0x23 LieInHammock          PlanToWait(10, body 9), then the SleepNW/SleepNE
    (spontaneous)              strip for GetRandom(180)+180, dirtiness 4,
                               happiness 1, energy 2, PlanToReleaseSemaphore.
    0x24 LieInHammockNoLeadIn  PlanToLieDown(GetRandom(10)) then
    (manual drop)              PlanToWait(GetRandom(10), 0x17 -- the chaise
                               body), the same three stat changes, NO
                               semaphore release; and when the link fails a
                               refusal: PlanToGo(object), PlanToSay(0xB7),
                               PlanToShakeHead(4, standing).

Both hammock items dispatch through behaviour id 0x24 on a drop (the
CHotSpot::Hammock gate was widened to accept 0x30C), so retargeting that one
CBehavior constructor macro entry covers both.

These tests pin:
  * ONE rest sequence, VF2PlanHammockRest, used by both entries;
  * the drop entry keeps the native refusal branch and releases no
    semaphore -- the drop route never held one, and the native drop does
    not release one either;
  * the generator retargets the 0x24 macro entry (ctor+0x1B5, relocation at
    +0x1B6) exactly as it already retargets 0x23;
  * the stock object really has those entries where the generator expects
    them, and the PATCHED object really points both at the VF2 functions.
"""
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))


def _source():
    return GEN.read_text(encoding="utf-8")


def _strip_comments(text):
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        out.append(line.split("//")[0] if "//" in line else line)
    return "\n".join(out)


def _function(src, signature_start):
    """Body of a function DEFINITION, never its forward declaration."""
    i = -1
    while True:
        i = src.index(signature_start, i + 1)
        close = src.index(")", i)
        if src.startswith("\n{", close + 1):
            return src[i:src.index("\n}\n", close)]


def _rest(src):
    return _function(src, "static void VF2PlanHammockRest(")


def _anchored(src):
    return _function(src, 'extern "C" void __cdecl VF2LieInHammockAnchoredRest(CVillager &villager)')


def _dropped(src):
    return _function(src, 'extern "C" void __cdecl VF2LieInHammockDropped(CVillager &villager)')


class OneRestSequence(unittest.TestCase):
    def test_the_shared_rest_settles_with_the_native_drops_table(self):
        """orientation 1 -> PlanToLieDown (body 9) + SleepNW; otherwise
        PlanToWait(.., 0x17) + SleepNE. Decoded from LieInHammockNoLeadIn,
        the drop the owner confirmed correct. Body 9 at both orientations
        with a head split on `orientation == 3` (probe v17) is the native
        SPONTANEOUS routine's defect and was reported in play as wrong
        orientation plus a flip when the eyes close."""
        rest = _strip_comments(_rest(_source()))
        self.assertIn("bool const liesDown = info.orientation == 1;", rest,
                      "the predicate is not the native drop's compare with 1")
        self.assertIn(
            "    if (liesDown) {\n"
            "        plans->PlanToLieDown(10);\n"
            "    } else {\n"
            "        plans->PlanToWait(10, eBodyPositionChaise);\n"
            "    }", rest,
            "the settle is not the native drop's: PlanToLieDown at "
            "orientation 1, the 2-argument chaise-body wait otherwise")
        self.assertRegex(rest, r'liesDown \? "SleepNW" : "SleepNE"',
                         "the strip does not pair with the body: 9 <-> SleepNW, "
                         "0x17 <-> SleepNE, as the stock RestingBody dispatch "
                         "pairs them; a mismatch flips when the eyes close")
        self.assertIn("ldwGameState::GetRandom(180) + 180,", rest,
                      "the strip is not the long sleep the owner asked for")
        for needle, why in (("plans->PlanToIncDirtiness(4);", "dirtiness changed"),
                            ("plans->PlanToIncHappinessTrend(1);", "happiness changed"),
                            ("plans->PlanToIncEnergy(2);", "energy changed")):
            self.assertIn(needle, rest, why)
        for bad, why in (
            ("eBodyPositionRestingHammock", "body 9 is hardcoded again -- the "
             "native path picks it through PlanToLieDown at orientation 1 only"),
            ("hammockHead", "a head-direction split is back"),
            ("orientation == 3", "`== 3` is never the hammock's predicate"),
            ("PlanToReleaseSemaphore", "the semaphore release belongs to the "
             "spontaneous entry only"),
            ("StartNewBehavior", "each entry starts the behaviour itself"),
        ):
            self.assertNotIn(bad, rest, why)

    def test_the_native_drop_really_compares_with_one_and_waits_in_the_chaise_body(self):
        """Ground truth for the table, pinned to the stock object so it is
        never re-derived from the (defective) native spontaneous routine."""
        import patch_mobile_furniture_pack as patcher
        src = patcher.SRC_OBJS / "Behavior.obj"
        if not src.is_file():
            self.skipTest("missing build input Behavior.obj")
        obj = patcher.CoffObject(src)
        fn = obj.symbol("?LieInHammockNoLeadIn@CBehavior@@CAXAAVCVillager@@@Z")
        sec = obj.section(fn.section)
        body = bytes(obj.buf[sec.raw_ptr + fn.value:sec.raw_ptr + fn.value + 0x100])
        self.assertIn(b"\x83\x7D\xE8\x01\x75", body,
                      "cmp dword ptr [ebp-18h],1 / jne -- the drop compares "
                      "info.orientation with 1")
        self.assertIn(b"\x6A\x17\x6A\x0A", body,
                      "push 17h; push 0Ah -- the other arm waits in the chaise "
                      "body with GetRandom(10)")
        spont = obj.symbol("?LieInHammock@CBehavior@@CAXAAVCVillager@@@Z")
        ssec = obj.section(spont.section)  # its own COMDAT section, not the drop's
        sbody = bytes(obj.buf[ssec.raw_ptr + spont.value:ssec.raw_ptr + spont.value + 0x100])
        self.assertIn(b"\x6A\x09\x6A\x0A", sbody,
                      "the native spontaneous routine waits in body 9 "
                      "unconditionally -- which is why it is not the reference")

    def test_the_spontaneous_entry_uses_it_and_releases_the_semaphore(self):
        a = _strip_comments(_anchored(_source()))
        self.assertIn("VF2PlanHammockRest(plans, info);", a)
        self.assertLess(a.index("VF2PlanHammockRest(plans, info);"),
                        a.index("plans->PlanToReleaseSemaphore();"))
        self.assertLess(a.index("plans->PlanToReleaseSemaphore();"),
                        a.index("plans->StartNewBehavior(villager);"))
        self.assertNotIn("PlanToPlayAnim", a,
                         "the spontaneous entry poses itself instead of "
                         "sharing the one rest")

    def test_the_drop_entry_uses_it_keeps_the_refusal_and_holds_no_semaphore(self):
        d = _strip_comments(_dropped(_source()))
        self.assertIn("VF2PlanHammockRest(plans, info);", d,
                      "the drop entry does not share the one rest sequence")
        self.assertNotIn("PlanToReleaseSemaphore", d,
                         "the drop entry releases a semaphore the drop route "
                         "never held; the native drop does not, so neither "
                         "may this")
        refusal_start = d.index("if (!FurnitureManager.LinkPeepToFurniture(")
        refusal = d[refusal_start:d.index("return;", refusal_start)]
        for needle in (
            "plans->PlanToGo(CContentMap::eObjectHammock, eSpeedNormal, ePriorityNormal, false);",
            "plans->PlanToSay(eStringCannotReachFurniture);",
            "plans->PlanToShakeHead(4, eBodyPositionStanding);",
            "plans->StartNewBehavior(villager);",
        ):
            self.assertIn(needle, refusal,
                          "the native refusal branch is not kept verbatim: "
                          "%s" % needle)
        after = d[d.index("return;", refusal_start):]
        self.assertIn("plans->PlanToGo(info.point, eSpeedNormal, ePriorityNormal);", after)
        self.assertLess(after.index("VF2PlanHammockRest(plans, info);"),
                        after.index("plans->StartNewBehavior(villager);"))
        self.assertNotIn("PlanToLieDown", d,
                         "the drop entry settles itself instead of sharing "
                         "the one rest")
        self.assertNotIn("PlanToPlayAnim", d)

    def test_the_declarations_the_drop_entry_needs_are_in_its_unit(self):
        src = _strip_comments(_source())
        self.assertIn("    eStringCannotReachFurniture = 0xB7,\n    eStringRelaxingInTheHammock = 0xE9\n};", src)
        self.assertIn("    void PlanToSay(StringId text);\n    void PlanToShakeHead(int duration, EBodyPosition bodyPosition);", src)
        self.assertIn("    void PlanToLieDown(int duration);", src)
        self.assertIn("    eBodyPositionStanding = 0,\n    eBodyPositionRestingHammock = 9,", src)
        self.assertIn("    eBodyPositionChaise = 0x17,", src)
        self.assertIn('extern "C" void __cdecl VF2LieInHammockDropped(CVillager &);', src)
        self.assertIn("    friend void __cdecl VF2LieInHammockDropped(CVillager &);", src)


class TheRetarget(unittest.TestCase):
    def test_the_generator_retargets_both_macro_entries(self):
        src = _source()
        for needle, why in (
            ('hammock_macro_expected = b"\\x68\\x00\\x00\\x00\\x00\\x6A\\x23"',
             "the 0x23 entry check is gone"),
            ("behavior_obj.retarget_relocation(behavior_sec.index, ctor.value + 0x1A8, anchored_hammock)",
             "the spontaneous route is no longer retargeted"),
            ("drop_macro_raw = behavior_sec.raw_ptr + ctor.value + 0x1B5",
             "the 0x24 entry is not located at ctor+0x1B5"),
            ('drop_macro_expected = b"\\x68\\x00\\x00\\x00\\x00\\x6A\\x24"',
             "the 0x24 entry bytes are not verified before retargeting"),
            ('dropped_hammock = behavior_obj.append_undefined_symbol("_VF2LieInHammockDropped")',
             "the drop symbol is not appended"),
            ("behavior_obj.retarget_relocation(behavior_sec.index, ctor.value + 0x1B6, dropped_hammock)",
             "the MANUAL drop is not retargeted -- the owner's request is "
             "not implemented"),
        ):
            self.assertIn(needle, src, why)
        self.assertLess(
            src.index("ctor.value + 0x1B6, dropped_hammock)"),
            src.index('behavior_obj.write(PATCHED / "Behavior.obj")'),
            "the 0x24 retarget happens after Behavior.obj is written")

    def test_the_record_says_the_drop_is_retargeted(self):
        src = _source()
        self.assertIn('"manual_drop_behavior": "0x24 LieInHammockNoLeadIn retargeted to _VF2LieInHammockDropped', src)
        self.assertNotIn('"manual_drop_behavior": "0x24 LieInHammockNoLeadIn remains native"', src)


def _reloc_symbol(obj, sec, vaddr):
    q = sec.reloc_ptr
    for _ in range(sec.nreloc):
        v, s = struct.unpack_from("<II", obj.buf, q)
        if v == vaddr:
            return obj.symbol_by_index[s].name
        q += 10
    return None


class TheObjects(unittest.TestCase):
    """The stock object has the entries where the generator looks, and the
    patched object points both at the VF2 functions. Skips only when the
    build inputs are genuinely absent."""

    @classmethod
    def setUpClass(cls):
        import patch_mobile_furniture_pack as patcher
        cls.patcher = patcher
        cls.skip = None
        for name in ("Villager.obj", "VillagerAI.obj", "Behavior.obj", "theMainScene.obj"):
            if not (patcher.SRC_OBJS / name).is_file():
                cls.skip = "missing build input %s" % name
                return

    def setUp(self):
        if self.skip:
            self.skipTest(self.skip)

    def _ctor(self, obj):
        ctor = obj.symbol("??0CBehavior@@QAE@XZ")
        return ctor, obj.section(ctor.section)

    def test_the_stock_object_has_both_entries_where_the_generator_looks(self):
        p = self.patcher
        obj = p.CoffObject(p.SRC_OBJS / "Behavior.obj")
        ctor, sec = self._ctor(obj)
        base = sec.raw_ptr + ctor.value
        self.assertEqual(bytes(obj.buf[base + 0x1A7:base + 0x1AE]), b"\x68\x00\x00\x00\x00\x6A\x23")
        self.assertEqual(bytes(obj.buf[base + 0x1B5:base + 0x1BC]), b"\x68\x00\x00\x00\x00\x6A\x24")
        self.assertEqual(_reloc_symbol(obj, sec, ctor.value + 0x1A8),
                         "?LieInHammock@CBehavior@@CAXAAVCVillager@@@Z")
        self.assertEqual(_reloc_symbol(obj, sec, ctor.value + 0x1B6),
                         "?LieInHammockNoLeadIn@CBehavior@@CAXAAVCVillager@@@Z",
                         "ctor+0x1B6 is not the manual hammock drop's entry")

    def test_the_patched_object_points_both_entries_at_vf2(self):
        p = self.patcher
        if not hasattr(p, "ENABLE_BEHAVIOR_PATCHES"):
            self.fail("the generator no longer exposes ENABLE_BEHAVIOR_PATCHES")
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            for name in ("Villager.obj", "VillagerAI.obj", "Behavior.obj", "theMainScene.obj"):
                shutil.copy2(p.SRC_OBJS / name, temp_root / name)
            old_patched, old_flag = p.PATCHED, p.ENABLE_BEHAVIOR_PATCHES
            try:
                p.PATCHED = temp_root
                p.ENABLE_BEHAVIOR_PATCHES = True
                p.patch_spontaneous_behaviors({})
            finally:
                p.PATCHED, p.ENABLE_BEHAVIOR_PATCHES = old_patched, old_flag
            obj = p.CoffObject(temp_root / "Behavior.obj")
            ctor, sec = self._ctor(obj)
            self.assertEqual(_reloc_symbol(obj, sec, ctor.value + 0x1A8),
                             "_VF2LieInHammockAnchoredRest")
            self.assertEqual(_reloc_symbol(obj, sec, ctor.value + 0x1B6),
                             "_VF2LieInHammockDropped",
                             "the patched constructor still dispatches the "
                             "manual drop to the native short routine")
            units = sorted(temp_root.glob("*.cpp"))
            carrying = [u for u in units
                        if "VF2LieInHammockDropped(CVillager &villager)" in
                        u.read_text(encoding="utf-8", errors="replace")]
            self.assertEqual(len(carrying), 1,
                             "expected exactly one emitted unit to define the "
                             "drop entry, found %s" % [u.name for u in carrying])
            # The retarget names a symbol; the emitted unit must define it or
            # the link fails with an unresolved external nobody sees here.
            text = carrying[0].read_text(encoding="utf-8", errors="replace")
            self.assertIn('extern "C" void __cdecl VF2LieInHammockDropped(CVillager &villager)', text)
            self._compile(carrying[0])

    def _compile(self, unit):
        import test_generated_cpp_compiles as compiles
        vcvars = next((c for c in compiles.VCVARS_CANDIDATES if pathlib.Path(c).is_file()), None)
        if vcvars is None:
            self.skipTest("no Visual Studio toolchain on this machine")
        with tempfile.TemporaryDirectory() as tmp:
            work = pathlib.Path(tmp)
            shutil.copy2(unit, work / unit.name)
            run = subprocess.run(
                '"%s" >nul 2>&1 && cl /c /nologo /EHsc "%s"' % (vcvars, work / unit.name),
                cwd=work, shell=True, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0,
                             "the unit carrying the hammock drop does not "
                             "compile:\n%s" % (run.stdout or "")[-1500:])
            obj = (work / unit.name).with_suffix(".obj").read_bytes()
            for sym in (b"_VF2LieInHammockDropped", b"_VF2LieInHammockAnchoredRest",
                        b"?PlanToSay@CVillagerPlans@@QAEXW4StringId@@@Z",
                        b"?PlanToShakeHead@CVillagerPlans@@QAEXHW4EBodyPosition@@@Z",
                        b"?PlanToLieDown@CVillagerPlans@@QAEXH@Z",
                        b"?PlanToWait@CVillagerPlans@@QAEXHW4EBodyPosition@@@Z"):
                self.assertIn(sym, obj, "%r is not in the compiled unit" % sym)


if __name__ == "__main__":
    unittest.main()
