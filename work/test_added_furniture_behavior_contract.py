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

    def test_the_venue_lookup_searches_from_the_placement_not_the_anchor(self):
        """The interceptor must supply the PLACEMENT, not the walk-to point.

        Decoded from work/FurnitureManager.disasm.txt. FindFurniture ranks
        candidates at 0x52-0x66 by

            (point.x - record[+0x14])^2 + (point.y - record[+0x18])^2

        i.e. by distance to each record's OWN placement, and at 0x121-0x137 it
        returns info.point as that placement PLUS the furniture map's hotspot
        offset. The two therefore differ by exactly one hotspot.

        Caught by review: an earlier revision fed info.point back in as the
        search origin. With an added bike or ping-pong table standing near a
        stock treadmill or pool table, the neighbouring stock record can be
        CLOSER to that anchor than the intended item's own placement is --
        which silently reintroduces the cross-targeting the window exists to
        prevent. Supplying the placement makes the intended record's distance
        zero, which nothing else can beat.
        """
        src = source()
        self.assertIn("gVF2AddedFurnitureVenuePlacement", src,
                      "the window no longer carries the placement origin")
        start = src.index("VF2FindFurnitureAtAddedFurnitureImpl(")
        body = src[start:src.index("\n}", start)]
        self.assertIn("point = gVF2AddedFurnitureVenuePlacement;", body,
                      "the lookup must search from the placement")
        self.assertNotIn("point = gVF2AddedFurnitureVenuePoint;", body,
                         "searching from the walk-to anchor is off by one "
                         "hotspot and lets a nearer stock record win")
        # The resolver must actually report the placement it selected, or the
        # window would carry a zeroed point.
        self.assertIn("foundPlacement = placement;", src)
        self.assertIn("if (outPlacement != 0) *outPlacement = foundPlacement;",
                      src)

    def test_the_reported_placement_belongs_to_the_winning_candidate(self):
        """foundPlacement must update only with the rest of the winner.

        The resolver walks every matching record and keeps the nearest. If
        foundPlacement were assigned outside the "is this one better?" branch
        it would hold the LAST record examined rather than the winning one,
        and the venue window would then constrain the donor's lookup to the
        wrong placement -- a subtler version of the bug this whole mechanism
        exists to prevent, and one that would only show up with two or more of
        the same item placed.

        Pinned structurally: the three winner fields must sit together inside
        the same branch.
        """
        src = source()
        start = src.index("ldwPoint foundPlacement = {0, 0};")
        end = src.index("if (!found) return false;", start)
        body = src[start:end]
        # The winning-branch CONDITION gained a preferred-slot term when the
        # owner asked for the Home Gym and Yoga Equipment to act where the
        # villager is dropped, so this anchors on the branch rather than on the
        # exact comparison. The property under test is unchanged: the three
        # winner fields must be assigned together inside that one branch, or a
        # losing record's value can survive.
        branch = body[body.index("|| !found ||"):]
        for field in ("outPoint = info.point;",
                      "foundPlacement = placement;",
                      "foundOrientation ="):
            self.assertIn(field, branch,
                          field + " is not inside the winning-candidate "
                          "branch, so it can hold a losing record's value")
        # And the placement is only handed out once a winner exists.
        self.assertLess(
            src.index("if (!found) return false;", start),
            src.index("if (outPlacement != 0) *outPlacement = foundPlacement;",
                      start),
            "the placement is reported before the no-match early return")

    def test_a_villager_on_other_furniture_is_never_dragged_to_a_venue(self):
        """The Treadmill must behave like stock when a villager is dropped on it.

        Reported in play: dropping a villager on the Treadmill produced "Using
        the exercise bike" and "Doing high-intensity cycling", and the
        treadmill's own actions never ran.

        Cause: VF2RunOwnFurnitureActionEx consulted the villager's position only
        inside the `!hasVenue` branch, which covers the case where the added
        item is ABSENT. With an Exercise Bike placed anywhere in the house
        hasVenue is true, so the position was never checked -- the window opened
        on the bike and the FindFurniture interceptor bound the donor to it,
        walking the villager off the treadmill. The owner owns both machines,
        which is exactly the configuration that triggers it.
        """
        src = source()
        self.assertIn("static bool VF2VillagerIsOnOtherFurniture(", src,
                      "the standing-on-other-furniture guard is gone")

        start = src.index("static void VF2RunOwnFurnitureActionEx(")
        body = src[start:src.index('extern "C" void __cdecl VF2ExerciseBikeWalk', start)]

        # The guard must be evaluated when a venue WAS resolved, which is the
        # case the old code missed. If it only appeared inside !hasVenue the
        # reported bug would still be present.
        self.assertIn("if (hasVenue &&", body,
                      "the position check does not run when a venue resolved, "
                      "which is precisely the reported bug")
        guard = body[body.index("if (hasVenue &&"):]
        self.assertIn(
            "VF2VillagerIsOnOtherFurniture(villager, itemId, altItemId, object)",
            guard,
            "the guard no longer receives the donor object, so it cannot tell "
            "shared-object furniture from an unrelated sofa")
        self.assertLess(
            body.index("if (hasVenue &&"), body.index("VF2BeginAddedFurnitureVenue"),
            "the position check must run BEFORE the venue window opens")

    def test_standing_on_open_floor_still_reaches_the_venue(self):
        """The guard must not break ordinary autonomous behaviour.

        A villager on open floor has no furniture under them, so the helper
        returns false and the venue is honoured. Without this the Exercise Bike
        would become unreachable, which would trade one reported bug for
        another.
        """
        src = source()
        start = src.index("static bool VF2VillagerIsOnOtherFurniture(")
        body = src[start:src.index("\n}", start)]
        self.assertIn("if (slot < 0) return false;", body,
                      "standing on open floor must not count as other furniture")
        # NARROWED after review: only furniture answering the SAME donor object
        # can be stolen from, because the venue window redirects the donor's own
        # FindFurniture and a donor searches only its own object id. Guarding on
        # ANY furniture declined an autonomous bike action whenever the villager
        # stood on a sofa, which is the shape AGENTS.md warns about -- a placed
        # item changing WHETHER a behaviour is available.
        self.assertIn("(CContentMap::EObject)object, sample, info", body,
                      "the guard no longer restricts itself to furniture that "
                      "shares the donor object")
        self.assertIn("if (candidate == itemId) return false;", body,
                      "standing on the item itself must not count as other")
        self.assertIn("altItemId >= 0 && candidate == altItemId", body,
                      "the alternate id must not count as other furniture")

    def test_only_the_exercise_bike_wears_the_bike_captions(self):
        """Owner requirement, stated directly.

        "I want ONLY the exercise bike to have the behaviors 'doing
        high-intensity cycling' and 'using the exercise bike'."

        Both treadmill caption wrappers previously asked
        VF2LinkedFurnitureItemIs, which is FindFurniture(0x04, feet) -- a
        NEAREST MATCH. It resolves its winner by placement handle so it never
        confuses two records, but "nearest to the feet" is not "the machine this
        villager is on": a bike beside the treadmill can win, and the caption
        then lands on a treadmill action.

        VF2VillagerIsStandingOnItem reads the item id from the placement record
        under the villager, which is the test the drop dispatcher already trusts
        for these shared-object items.
        """
        src = source()
        self.assertIn("static bool VF2VillagerIsStandingOnItem(", src)

        for wrapper, donor in (
                ("VF2RandomTreadmillWalkLabel", "WorkoutTreadmill"),
                ("VF2RandomTreadmillRunLabel", "RunningOnTreadmill")):
            start = src.index('extern "C" void __cdecl %s(CVillager &villager)' % wrapper)
            body = src[start:src.index("\n}", start)]
            self.assertIn(
                "VF2VillagerIsStandingOnItem(\n        villager, __VF2_EXERCISE_BIKE_ITEM_ID__)",
                body,
                "%s no longer requires the villager to be ON the bike" % wrapper)
            # Comments deliberately NAME the superseded approach (AGENTS.md 11
            # records dead ends rather than deleting them), so strip comment
            # lines before asserting the CODE no longer calls it. Asserting
            # against the raw text would forbid documenting the very mistake
            # this test exists to prevent.
            code = "\n".join(
                line for line in body.splitlines()
                if not line.lstrip().startswith("//"))
            self.assertNotIn(
                "VF2LinkedFurnitureItemIs", code,
                "%s is back on the nearest-match test, which can put the "
                "bike's caption on a treadmill" % wrapper)
            self.assertIn("if (!onBike) return;", body,
                          "%s no longer leaves the stock label alone when the "
                          "villager is not on the bike" % wrapper)
            self.assertIn("CBehavior::%s" % donor, body,
                          "%s no longer runs its native donor" % wrapper)

    def test_the_stock_treadmill_candidates_are_never_disabled(self):
        """The Treadmill must stay autonomously reachable exactly as stock.

        The bike's candidates are CLONES of the treadmill's (0x049 -> 0x0B1,
        0x0E0 -> 0x0B2). Cloning copies into the target slot and leaves the
        donor slot untouched, so the stock treadmill candidates survive. If a
        future edit ever disabled them the treadmill would stop being selected
        autonomously, which is the other half of what the owner asked for.
        """
        src = source()
        self.assertIn("CloneAutonomousCandidateWithWeight(data, 0x049, 0x0B1, 450)", src)
        self.assertIn("CloneAutonomousCandidateWithWeight(data, 0x0E0, 0x0B2, 450)", src)
        clone = src[src.index("static void CloneAutonomousCandidateWithWeight("):]
        clone = clone[:clone.index("\n}")]
        self.assertIn("target[i] = donor[i]", clone,
                      "cloning no longer copies the donor into the target")
        self.assertNotIn("donor[0xCD] = 0", clone,
                         "cloning now disables the donor candidate, which would "
                         "stop the stock Treadmill being selected")

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


class TheGymAndYogaActWhereTheVillagerIsDropped(unittest.TestCase):
    """Owner: act at the drop point, for the Home Gym and Yoga Equipment ONLY.

    Verbatim request: "Villagers should do their actions where they are dropped
    instead of moving somewhere else for the home Gym and Yoga Equipment only."

    The scope limit is asserted as firmly as the feature: the venue lookup
    otherwise keeps its nearest-placement behaviour, and widening this to other
    items would change furniture the owner did not ask about.
    """

    def test_the_preferred_slot_covers_all_three_item_ids(self):
        text = source()
        self.assertIn("static bool VF2ItemIsHomeGymOrYoga(int itemId)", text)
        block = text.split("VF2ItemIsHomeGymOrYoga(int itemId)", 1)[1]
        block = block.split("}", 1)[0]
        self.assertIn("__VF2_HOME_GYM_ITEM_ID__", block)
        self.assertIn("__VF2_YOGA_EQUIPMENT_ITEM_ID__", block)
        self.assertIn(
            "0x220", block,
            "the STOCK Yoga Equipment is 0x220 and the macro resolves to the "
            "invisible copy only; omitting it makes a drop on the visible item "
            "fall back to the generic 'Working out' label, which is an "
            "already-reported regression")

    def test_other_items_keep_the_nearest_placement_behaviour(self):
        """-1 must remain the default, or every item would act where dropped."""
        text = source()
        self.assertIn(
            "villager, itemId, -1, object, outPoint, 0, -1);", text,
            "the compatibility wrapper must pass -1 so unrelated items are "
            "unaffected")
        self.assertIn("int preferSlot)", text)
        self.assertIn("preferSlot >= 0 && slot == preferSlot", text)

    def test_the_drop_slot_helper_validates_the_record(self):
        """A slot is only honoured when it really is that item, in world."""
        text = source()
        block = text.split("VF2DroppedOnAddedFurnitureSlot(", 1)[1]
        block = block.split("\n}", 1)[0]
        self.assertIn("0x1004", block, "the slot must be bounds-checked")
        self.assertIn("record + 0x0C", block, "the in-world bit must be tested")


if __name__ == "__main__":
    unittest.main()
