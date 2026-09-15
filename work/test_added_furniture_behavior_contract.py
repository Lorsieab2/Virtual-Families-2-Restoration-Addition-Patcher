import re
import unittest

import patch_mobile_furniture_pack as patcher


def source():
    return (patcher.ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
        encoding="utf-8"
    )


class TestAddedFurnitureContract(unittest.TestCase):
    def test_ownership_never_gates_the_own_handlers(self):
        src = source()
        block = src[src.index("static void VF2RunOwnFurnitureActionEx("):src.index("// The Ping-Pong Table", src.index("static void VF2RunOwnFurnitureActionEx("))]
        self.assertNotIn("IsInWorld", block)
        self.assertIn("VF2RunNativeBehaviorAndChangedLabel", block)
        self.assertNotIn("if (!changed) return;", block)
        self.assertIn("apply the item's label", block)
        self.assertIn("static void VF2ApplyVenueLabel(", source())

    def test_venue_label_is_applied_when_donor_keeps_native_label(self):
        src = source()
        start = src.index("static void VF2RunOwnFurnitureActionEx(")
        body = src[start:src.index('extern "C" void __cdecl VF2ExerciseBikeWalk', start)]
        donor = body.index("VF2RunNativeBehaviorAndChangedLabel(villager, donorBehavior);")
        after = body[donor:]
        self.assertIn("VF2EndAddedFurnitureVenue(villager);", after)
        self.assertIn("VF2ApplyVenueLabel", after)

    def test_venue_label_selector_has_no_native_label_roll(self):
        src = source()
        start = src.index("static void VF2ApplyVenueLabel(")
        body = src[start:src.index("static void VF2ApplyRandomLabel", start)]
        self.assertNotIn("GetRandom(count + 1)", body)
        self.assertIn("GetRandom(count)", body)

    def test_stock_donor_wrappers_use_strict_selector_only_for_added_items(self):
        src = source()
        for start_marker, end_marker in (
            ("extern \"C\" void __cdecl VF2RandomPooltableLabel", "// The Exercise Bike"),
            ("extern \"C\" void __cdecl VF2RandomTreadmillWalkLabel", "extern \"C\" void __cdecl VF2RandomTreadmillRunLabel"),
            ("extern \"C\" void __cdecl VF2RandomTreadmillRunLabel", "extern \"C\" void __cdecl VF2RandomDrinkLabel"),
        ):
            start = src.index(start_marker, src.index("// The Ping-Pong Table borrows the Pool Table's behaviour wholesale"))
            body = src[start:src.index(end_marker, start)]
            self.assertIn("VF2ApplyVenueLabel", body)
            self.assertIn("if (!", body)

    def test_missing_venue_does_not_run_the_shared_donor(self):
        src = source()
        start = src.index("static void VF2RunOwnFurnitureActionEx(")
        body = src[start:src.index("extern \"C\" void __cdecl VF2ExerciseBikeWalk", start)]
        self.assertIn("bool const hasVenue", body)
        self.assertIn("VF2RunNativeBehaviorAndChangedLabel", body)
        self.assertIn("if (!hasVenue)", body)
        missing = body[body.index("if (!hasVenue)"):body.index("VF2BeginAddedFurnitureVenue", body.index("if (!hasVenue)"))]
        self.assertIn("added-furniture candidate", missing)
        self.assertIn("VF2VillagerIsDroppedOnAddedFurniture", missing)
        dropped = missing[missing.index("if (VF2VillagerIsDroppedOnAddedFurniture"):]
        self.assertIn("VF2RunNativeBehaviorAndChangedLabel", dropped)

    def test_shared_donor_objects_are_explicit_and_separate(self):
        src = source()
        expected = {
            "__VF2_EXERCISE_BIKE_ITEM_ID__": "0x04",
            "__VF2_HOME_GYM_ITEM_ID__": "0x75",
            "__VF2_YOGA_EQUIPMENT_ITEM_ID__": "0x75",
            "__VF2_PING_PONG_TABLE_ITEM_ID__": "0x36",
        }
        # An optional alternate item id may sit between the item and its
        # object. VF2RunOwnFurnitureAction* gained that parameter so ONE
        # behaviour can serve two ids: the Yoga Equipment needs it, because the
        # stock item (0x220) and the invisible copy are the same thing with
        # different art and a drop on either must reach the same venue. Callers
        # with no second id pass -1. The pairing this test guards -- which
        # donor OBJECT each added item is bound to -- is unchanged.
        for item, obj in expected.items():
            self.assertRegex(
                src, rf"{re.escape(item)}, (?:(?:-1|0x[0-9a-fA-F]+), )?{obj}",
                f"{item} is no longer bound to donor object {obj}")
        self.assertIn("CBehavior::WorkoutTreadmill", src)
        self.assertIn("CBehavior::RunningOnTreadmill", src)
        self.assertIn("CBehavior::WorkingOut", src)
        self.assertIn("CBehavior::QuickWorkout", src)
        self.assertIn("CBehavior::PlayingPooltable", src)

    def test_manual_drop_routes_added_items_to_own_handlers(self):
        src = source()
        start = src.index("added_furniture_drop_dispatch =")
        body = src[start:src.index("helper_source = helper_source.replace(\n        \"__VF2_ADDED_FURNITURE_DROP_DISPATCH__\"", start)]
        for item, handler in (
            ("__VF2_EXERCISE_BIKE_ITEM_ID__", "VF2ExerciseBikeWalk"),
            ("__VF2_HOME_GYM_ITEM_ID__", "VF2HomeGymWorkout"),
            ("__VF2_YOGA_EQUIPMENT_ITEM_ID__", "VF2YogaEquipmentWorkout"),
            ("__VF2_PING_PONG_TABLE_ITEM_ID__", "VF2PingPongPlay"),
        ):
            self.assertIn(f"candidate == {item}", body)
            self.assertIn(f"{handler}(villager)", body)

    def test_orientation_routes_include_the_invisible_counterparts(self):
        routes = {
            spec["name"]: tuple(spec["item_ids"])
            for spec in patcher.MOBILE_FURNITURE_MANUAL_BINDING_SPECS
        }
        self.assertEqual(
            routes["invisible_spa_lounger"],
            (patcher.INVISIBLE_SPA_LOUNGER_ITEM_ID, patcher.SPA_LOUNGER_ITEM_ID),
        )
        self.assertEqual(
            routes["picnic_table"],
            (patcher.MOBILE_PICNIC_TABLE_ITEM_ID,
             patcher.INVISIBLE_PICNIC_TABLE_ITEM_ID),
        )
        self.assertEqual(
            routes["patio_table"],
            (patcher.MOBILE_PATIO_TABLE_ITEM_ID,
             patcher.INVISIBLE_PATIO_TABLE_ITEM_ID),
        )
        self.assertIn('"name": "InvisibleYogaEquipment"', source())
        self.assertIn("__VF2_YOGA_EQUIPMENT_ITEM_ID__", source())

    def test_exact_identity_uses_placement_handle_not_anchor(self):
        src = source()
        start = src.index("static bool VF2LinkedFurnitureItemIs(")
        body = src[start:src.index("// Donor actions", start)]
        self.assertIn("info.unknown0", body)
        self.assertIn("record + 0x04", body)
        self.assertNotIn("VF2FurnitureItemAtPoint", body)

    def test_venue_wrapper_replaces_donor_destination_and_preserves_fallback(self):
        src = source()
        self.assertIn("_VF2PlanToGoAtAddedFurniture", src)
        self.assertIn("_VF2PlanToGoObjectAtAddedFurniture", src)
        self.assertIn("donor PlanToGo and FindFurniture callsites retain the selected placed-item venue", src)
        # The donor's OWN furniture lookup must be constrained too.
        # FindFurniture runs BEFORE PlanToGo, from the villager's
        # pre-walk feet, so intercepting only the route left the donor
        # bound to whichever shared-EObject placement was nearest --
        # the Treadmill instead of the Exercise Bike, the Pool Table
        # instead of the Ping-Pong Table. Reported in play repeatedly.
        self.assertIn("_VF2FindFurnitureAtAddedFurniture", src)
        self.assertIn("VF2FindFurnitureAtAddedFurnitureImpl", src)
        for donor in ("WorkoutTreadmill", "RunningOnTreadmill",
                      "PlayingPooltable"):
            self.assertIn(donor + " FindFurniture", src,
                          donor + " no longer has its furniture lookup "
                          "constrained to the resolved venue")

    def test_the_findfurniture_wrapper_forwards_every_stack_word(self):
        """The naked wrapper must forward SEVEN words and clean 28 bytes.

        FindFurniture(EObject, ldwPoint, sFurnitureInfo2 &, bool, int, bool) is
        __thiscall: `this` arrives in ecx and the rest are pushed. ldwPoint is
        PASSED BY VALUE and is {int x; int y;}, so it occupies TWO words, not
        one -- 1 + 2 + 1 + 1 + 1 + 1 = 7 words = 28 bytes.

        Caught by review on the first revision, which forwarded six words and
        used `add esp, 28 / ret 24`. That makes the helper read the wrapper's
        own return address as its final bool and leaves the donor's stack four
        bytes out of position at every retargeted callsite -- a corruption, not
        a cosmetic slip. Pinned because the arithmetic is invisible at a glance.
        """
        src = source()
        start = src.index("void VF2FindFurnitureAtAddedFurniture()")
        body = src[start:src.index("}", src.index("__asm", start)) + 1]
        self.assertEqual(
            body.count("push dword ptr [esp+28]"), 7,
            "the wrapper must forward seven stack words; ldwPoint is two")
        self.assertIn("push ecx", body, "`this` must be forwarded")
        self.assertIn("add esp, 32", body,
                      "seven forwarded words plus ecx is 32 bytes to clean")
        self.assertIn("ret 28", body,
                      "the callee-cleanup must match the 28 bytes of "
                      "arguments the caller pushed")
        # The old, wrong arithmetic must not come back.
        self.assertNotIn("push dword ptr [esp+24]", body)
        self.assertNotIn("add esp, 28", body)
        self.assertNotIn("ret 24", body)
        self.assertIn("fallback\": \"native donor behavior remains unchanged", src)

    def test_plan_to_go_wrappers_forward_thiscall_stack_cleanup(self):
        src = source()
        start = src.index("extern \"C\" __declspec(naked) void VF2PlanToGoAtAddedFurniture()")
        body = src[start:src.index("// ---- Added furniture: actions", start)]
        self.assertEqual(body.count("push dword ptr [esp+16]"), 8)
        self.assertEqual(body.count("add esp, 20"), 2)
        self.assertEqual(body.count("ret 16"), 2)

    def test_decal_tail_hook_runs_before_curtain_relocations(self):
        src = source()
        table = src.index("    patch_mobile_table_prop_draw(manifest)")
        curtain = src.index("    patch_bathroom1_curtain_decal(manifest)")
        self.assertLess(table, curtain)


if __name__ == "__main__":
    unittest.main()
