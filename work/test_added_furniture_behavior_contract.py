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
        block = src[src.index("static void VF2RunOwnFurnitureAction("):src.index("// The Ping-Pong Table", src.index("static void VF2RunOwnFurnitureAction("))]
        self.assertNotIn("IsInWorld", block)
        self.assertIn("VF2RunNativeBehaviorAndChangedLabel", block)
        self.assertNotIn("if (!changed) return;", block)
        self.assertIn("apply the item's label", block)
        self.assertIn("static void VF2ApplyVenueLabel(", source())

    def test_venue_label_is_applied_when_donor_keeps_native_label(self):
        src = source()
        start = src.index("static void VF2RunOwnFurnitureAction(")
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

    def test_missing_venue_falls_back_to_native_donor(self):
        src = source()
        start = src.index("static void VF2RunOwnFurnitureAction(")
        body = src[start:src.index("extern \"C\" void __cdecl VF2ExerciseBikeWalk", start)]
        self.assertIn("bool const hasVenue", body)
        self.assertIn("VF2RunNativeBehaviorAndChangedLabel", body)
        self.assertIn("VF2EndAddedFurnitureVenue(villager);", body)
        self.assertIn("if (!hasVenue)", body)
        self.assertIn("leave its stock label untouched", body)

    def test_shared_donor_objects_are_explicit_and_separate(self):
        src = source()
        expected = {
            "__VF2_EXERCISE_BIKE_ITEM_ID__": "0x04",
            "__VF2_HOME_GYM_ITEM_ID__": "0x75",
            "__VF2_YOGA_EQUIPMENT_ITEM_ID__": "0x75",
            "__VF2_PING_PONG_TABLE_ITEM_ID__": "0x36",
        }
        for item, obj in expected.items():
            self.assertRegex(src, rf"{re.escape(item)}, {obj}")
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
        self.assertIn("donor PlanToGo callsites retain the selected placed-item destination", src)
        self.assertIn("fallback\": \"native donor behavior remains unchanged", src)

    def test_plan_to_go_wrappers_forward_thiscall_stack_cleanup(self):
        src = source()
        start = src.index("extern \"C\" __declspec(naked) void VF2PlanToGoAtAddedFurniture()")
        body = src[start:src.index("// ---- Added furniture: actions", start)]
        self.assertEqual(body.count("push dword ptr [esp+16]"), 8)
        self.assertEqual(body.count("add esp, 20"), 2)
        self.assertEqual(body.count("ret 16"), 2)


if __name__ == "__main__":
    unittest.main()
