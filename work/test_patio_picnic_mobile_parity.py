#!/usr/bin/env python3
"""The Picnic and Patio tables behave like their VF2 mobile counterparts.

THE SPECIFICATION is the shipping mobile build, Virtual Families 2 1.7.16
(APKPure xapk, lib/x86/libVirtualFamilies2.so). The addresses quoted below are
from that library, decoded with IDA 9.4. What each test pins, and the mobile
code it comes from:

* Manual-drop refusals. CHotSpot::PicnicTable @0x1EEDB0 and
  CHotSpot::PatioChairs @0x1EEEA0 say the SAME two strings, mobile ids 2023
  (eSayTooYoung, "This person is too young!") and 2919 (eWorriedFood,
  "Worried about food"). The desktop string table numbers those same strings
  0x73D and 0xA41. The picnic route used the raw mobile ids, and PC 0x7E7 is
  eSayPlayPuddles -- a child dropped on the picnic table said "Playing in
  puddles".

* The props. The meal/drinks are not tied to the villager who prepared them.
  CEnvironment::SetProp(0x55/0x56) @0x1EA910 activates the prop for 240 s;
  CEnvironment::Update @0x1E92A0 switches random tables of that EObject ON via
  CFurnitureManager::SetOnState(handle, true, 1, 300, -1), each for 300 s;
  CEnvironment::UpdateProps @0x1EB480 switches ONE random table off at the
  240 s expiry. So every table shows the prop, selling one table does not take
  it off another, and a second preparer cannot make it vanish.

* Both SetProp call sites. Mobile calls SetProp from CVillagerPlans::
  StartNewBehavior @0x1D6580 AND ProcessCurrentPlan @0x1D6ED0 (case 0x2A in
  each). PC routed only ProcessCurrentPlan+0x21B to the wrapper, so an
  activate-prop plan STARTED by StartNewBehavior+0x395 passed 0x55/0x56 to the
  stock SetProp, which drops ids above 0x54.

* Preparers. Mobile's autonomous records exclude themselves while ANY villager
  is doing the preparation (GetVillagerDoing), not only the latest.

* The invisible tables are the same furniture without art, so everything above
  applies to them identically.

Every test here was mutation-checked: reverting the corresponding fix makes it
fail.
"""
import re
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher
from coff_patch import CoffObject


def generate_helper():
    old_patched = patcher.PATCHED
    try:
        with tempfile.TemporaryDirectory() as tmp:
            patcher.PATCHED = Path(tmp)
            shutil.copy2(
                patcher.SRC_OBJS / "theMainScene.obj",
                patcher.PATCHED / "theMainScene.obj",
            )
            patcher.patch_mobile_furniture_behavior_dispatch({})
            return (patcher.PATCHED / "vf2_mobile_furniture_behaviors.cpp").read_text(
                encoding="ascii"
            )
    finally:
        patcher.PATCHED = old_patched


def code_only(text):
    """Strip // comments so an explanatory comment cannot satisfy a test."""
    return "\n".join(line.split("//")[0] for line in text.split("\n"))


def body(source, start_marker, end_marker="\n}\n"):
    start = source.index(start_marker)
    return source[start:source.index(end_marker, start)]


HAVE_OBJS = (patcher.SRC_OBJS / "theMainScene.obj").is_file()


@unittest.skipUnless(HAVE_OBJS, "desktop object files are not present")
class GeneratedHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = generate_helper()
        cls.code = code_only(cls.helper)

    # ------------------------------------------------------------ refusals
    def test_picnic_refusals_say_the_same_strings_as_mobile(self):
        picnic = code_only(body(self.helper, "static bool VF2HandleMobilePicnicTable("))
        self.assertIn("VF2ManualPatioRefusal(villager, eStringTooYoung)", picnic)
        self.assertIn("VF2ManualPatioRefusal(villager, eStringWorriedAboutFood)", picnic)

    def test_patio_and_picnic_refuse_identically(self):
        patio = code_only(body(self.helper, "static bool VF2HandleMobilePatioTable("))
        picnic = code_only(body(self.helper, "static bool VF2HandleMobilePicnicTable("))
        refusals = re.compile(r"VF2ManualPatioRefusal\([^;]*;")
        self.assertEqual(
            [r.replace(" ", "").replace("\n", "") for r in refusals.findall(patio)],
            [r.replace(" ", "").replace("\n", "") for r in refusals.findall(picnic)],
        )

    def test_the_refusal_ids_are_the_desktop_numbers_of_the_mobile_strings(self):
        self.assertIn("eStringTooYoung = 0x73D", self.code)
        self.assertIn("eStringWorriedAboutFood = 0xA41", self.code)
        self.assertNotIn("0x7E7", self.code)
        self.assertNotIn("0xB67", self.code)

    # ------------------------------------------------------------ props
    def test_setprop_wrapper_only_arms_the_240_second_readiness(self):
        wrapper = code_only(body(self.helper, "VF2PatioSetPropAndTrack(\n"))
        self.assertEqual(wrapper.count("GameTime.Seconds() + 240"), 2)
        self.assertNotIn("Preparer", wrapper)
        self.assertNotIn("FindFurniture", wrapper)

    def test_paint_draws_on_every_switched_on_table_not_one_captured_slot(self):
        paint = code_only(body(self.helper, "VF2FurniturePaintAndTableProps(\n"))
        self.assertLess(paint.index("self->Draw(index)"), paint.index("VF2DrawTableProp("))
        for kind in ("Picnic", "Patio"):
            with self.subTest(kind=kind):
                self.assertIn("VF2TablePropFind(gVF2%sOn, gVF2%sOnCount, handle)" % (kind, kind), paint)
                self.assertIn("VF2TablePropTurnOnAll(\n                VF2Is%sTableItem" % kind, paint)
                self.assertIn("VF2TablePropExpire(gVF2%sOn, gVF2%sOnCount)" % (kind, kind), paint)
        self.assertIn("tableX + kVF2PatioDrinksNudgeX", paint)
        self.assertIn("tableY - kVF2PicnicMealNudgeY", paint)

    def test_each_table_stays_on_for_its_own_300_seconds(self):
        self.assertIn("static int const kVF2TablePropOnSeconds = 300;", self.code)
        self.assertIn("static int const kVF2TablePropOnMax = 20;", self.code)
        turn_on = code_only(body(self.helper, "static void VF2TablePropTurnOnAll("))
        self.assertIn("now + kVF2TablePropOnSeconds", turn_on)
        # SetOnState(true) acts only on a table that is not already on.
        self.assertIn("if (VF2TablePropFind(list, count, handle) >= 0) continue;", turn_on)
        # No switch-on while furniture is being placed.
        self.assertIn("*(manager + 0x9014) != 0", turn_on)
        expire = code_only(body(self.helper, "static void VF2TablePropExpire("))
        self.assertIn("left < 0", expire)

    def test_readiness_expiry_switches_one_random_table_off(self):
        for fn, obj in (("VF2PicnicReadyActive", "eObjectPicnicTable"),
                        ("VF2PatioDrinksActive", "eObjectPatioTable")):
            with self.subTest(fn=fn):
                active = code_only(body(self.helper, "static bool %s()" % fn))
                self.assertIn("VF2TablePropTurnOffOne(\n        CContentMap::%s" % obj, active)
        turn_off = code_only(body(self.helper, "static void VF2TablePropTurnOffOne("))
        # nearest flag FALSE: FindFurniture then picks at random, as mobile's
        # UpdateProps call FindFurniture(obj, (0,0), info, false, 0, false) does.
        self.assertIn("FindFurniture(object, origin, info, false, 0, 0)", turn_off)
        self.assertIn("origin.x = 0;", turn_off)
        self.assertIn("origin.y = 0;", turn_off)

    def test_the_invisible_tables_carry_the_props_too(self):
        picnic = code_only(body(self.helper, "static bool VF2IsPicnicTableItem("))
        patio = code_only(body(self.helper, "static bool VF2IsPatioTableItem("))
        self.assertIn("0x2E8", picnic)
        self.assertIn(hex(patcher.furniture_item_id_by_name("InvisiblePicnicTable")), picnic)
        self.assertIn("0x2E6", patio)
        self.assertIn(hex(patcher.furniture_item_id_by_name("InvisiblePatioTable")), patio)

    # ------------------------------------------------------------ preparers
    def test_every_preparer_counts_until_its_behaviour_ends(self):
        for kind in ("Picnic", "PatioDrinks"):
            with self.subTest(kind=kind):
                self.assertIn("VF2AddPreparer(gVF2%sPreparers, villager);" % kind, self.code)
                self.assertIn("return VF2AnyStillPreparing(gVF2%sPreparers);" % kind, self.code)
        anyp = code_only(body(self.helper, "static bool VF2AnyStillPreparing("))
        self.assertIn("for (int i = 0; i < kVF2MaxPreparers; ++i)", anyp)
        self.assertIn("any = true;", anyp)

    # ------------------------------------------------------------ mobile quirks kept
    def test_a_failed_patio_link_walks_to_the_picnic_table_like_mobile(self):
        """Mobile CBehavior::DrinkAtPatioChair @0x1BAB50: when LinkPeepToFurniture
        (0x98) fails it plans PlanToGo(0x97 -- the PICNIC table), Say(191
        "There's nowhere to sit!"), ShakeHead(4). Looks like a slip, but it is
        the shipping behaviour, so it is pinned rather than "fixed"."""
        drink = code_only(body(self.helper, "static bool VF2RunMobileDrinkAtPatioChair("))
        fail = drink[drink.index("LinkPeepToFurniture"):drink.index("plans->PlanToGo(info.point")]
        self.assertIn("CContentMap::eObjectPicnicTable", fail)
        self.assertIn("eStringCannotReachFurniture", fail)


class InvisibleTablesShareTheObjects(unittest.TestCase):
    """The prop predicates match item ids; mobile matches EObject 0x97/0x98.
    They agree only while no other shipped map carries those objects."""

    def _objects(self, path):
        data = path.read_bytes()
        if len(data) < 32 or data[:4] != b"QAMF":
            return set()
        width, height = struct.unpack_from("<II", data, 24)
        if len(data) < 32 + 4 * width * height:
            return set()
        cells = struct.unpack_from("<%dI" % (width * height), data, 32)
        return {(((c >> 11) & 0x40000) | (c & 0x3F800)) >> 11 for c in cells if c}

    def test_only_the_table_maps_carry_the_picnic_and_patio_objects(self):
        root = patcher.ROOT / "patcher_assets"
        carriers = set()
        for path in root.rglob("*.fmap"):
            if "mobile_fmaps" in path.parts:
                continue  # the untranslated APK originals, never shipped
            if self._objects(path) & {0x97, 0x98}:
                carriers.add(path.name)
        self.assertEqual(carriers, {"Picnic_table.png.fmap", "Patio_table.png.fmap"})

    def test_only_the_invisible_tables_borrow_those_maps(self):
        borrowers = sorted(
            item["name"]
            for table in (patcher.INVISIBLE_OUTDOOR_ITEMS, patcher.INVISIBLE_TRANSPARENT_BASE_ITEMS)
            for item in table
            if item.get("donor_fmap") in {"Picnic_table.png.fmap", "Patio_table.png.fmap"}
        )
        self.assertEqual(borrowers, ["InvisiblePatioTable", "InvisiblePicnicTable"])


@unittest.skipUnless((patcher.SRC_OBJS / "VillagerPlans.obj").is_file(),
                     "desktop object files are not present")
class BothSetPropCallsRouteToTheWrapper(unittest.TestCase):
    def _targets(self, obj, name, start, stop):
        sym = obj.symbol(name)
        sec = obj.section(sym.section)
        out = {}
        for index in range(sec.nreloc):
            vaddr, symbol_index, rtype = struct.unpack_from(
                "<IIH", obj.buf, sec.reloc_ptr + index * 10)
            if sym.value + start <= vaddr < sym.value + stop:
                out[vaddr - sym.value] = obj.symbol_by_index[symbol_index].name
        return out

    def test_start_new_behavior_and_process_current_plan(self):
        old_patched = patcher.PATCHED
        start_name = "?StartNewBehavior@CVillagerPlans@@QAEXAAVCVillager@@@Z"
        process_name = "?ProcessCurrentPlan@CVillagerPlans@@QAEXAAVCVillager@@@Z"
        setprop = "?SetProp@CEnvironment@@QAEXW4EPropEnum@@@Z"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                path = patcher.PATCHED / "VillagerPlans.obj"
                shutil.copy2(patcher.SRC_OBJS / "VillagerPlans.obj", path)
                before = CoffObject(path)
                before_start = self._targets(before, start_name, 0, 0x2000)
                before_process = self._targets(before, process_name, 0, 0x2000)
                self.assertEqual(before_start.get(0x396), setprop)
                self.assertEqual(before_process.get(0x21B), setprop)
                manifest = {}
                patcher.patch_mobile_patio_prop_execution(manifest)
                after = CoffObject(path)
                after_start = self._targets(after, start_name, 0, 0x2000)
                after_process = self._targets(after, process_name, 0, 0x2000)
                helper = patcher.MOBILE_PATIO_PROP_HELPER_SYMBOL
                expected_start = dict(before_start)
                expected_start[0x396] = helper
                expected_process = dict(before_process)
                expected_process[0x21B] = helper
                self.assertEqual(after_start, expected_start)
                self.assertEqual(after_process, expected_process)
                record = manifest["MobilePatioPropExecution"]
                self.assertEqual(record["start_new_behavior_relocation_offset"], "0x396")
        finally:
            patcher.PATCHED = old_patched


@unittest.skipUnless((patcher.SRC_OBJS / "theStringManager.obj").is_file(),
                     "desktop object files are not present")
class DesktopStringNumbers(unittest.TestCase):
    """Read the desktop string enum from theStringManager.obj's CodeView
    constants (S_CONSTANT 0x1107, type 0x1FD2, 16-bit value, name) so the ids
    the helper uses are checked against the game, not against this file."""

    def _constant(self, value):
        data = (patcher.SRC_OBJS / "theStringManager.obj").read_bytes()
        needle = b"\x07\x11\xd2\x1f\x00\x00" + struct.pack("<H", value)
        at = data.index(needle) + len(needle)
        return data[at:data.index(b"\0", at)].decode("ascii")

    def test_the_ids_name_the_mobile_strings(self):
        self.assertEqual(self._constant(0x73D), "eSayTooYoung")
        self.assertEqual(self._constant(0xA41), "eWorriedFood")
        self.assertEqual(self._constant(0xB7), "eString_SayNoSeat")

    def test_the_old_picnic_id_was_a_different_string(self):
        self.assertEqual(self._constant(0x7E7), "eSayPlayPuddles")


if __name__ == "__main__":
    unittest.main()
