import re
import unittest

import patch_mobile_furniture_pack as patcher


def source():
    return (patcher.ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
        encoding="utf-8"
    )


def active_cpp(text):
    """`text` with C++ comments removed, so assertions see LIVE code only.

    Review found that a call disabled by prefixing `//` still satisfies an
    `assertIn` for its exact text: commenting out the Home Gym clone left the
    whole contract suite green while the generated C++ silently lost that
    autonomous candidate. Matching against raw source therefore proves a
    string is PRESENT, not that it RUNS.

    Only `//` to end-of-line and `/* ... */` are stripped, and each is
    replaced by a newline or a space so that line structure and token
    boundaries survive. This is deliberately not a C++ parser: it is applied
    to the generator's own emitted-C++ string literals, which use plain
    comments and no `//` inside string constants in the regions asserted on.
    """
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


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
        # THE POOL WRAPPER IS DELIBERATELY NOT IN THIS LIST ANY MORE.
        #
        # SUPERSEDED, recorded rather than deleted (AGENTS.md 11): it used to
        # be checked alongside the two treadmill wrappers, because all three
        # had to choose between a stock donor's label and an added item's while
        # the pairs shared a content-map object.
        #
        # The Ping-Pong Table now has its own object (0x9A), so stock
        # PlayingPooltable routes only to genuine pool tables and its wrapper
        # applies no label at all -- any selector there could only mislabel a
        # stock action. The treadmill wrappers still need theirs, because the
        # bike's LABELS are still applied by wrapping the stock treadmill
        # behaviours even though the bike's venue object is now its own.
        for start_marker, end_marker in (
            ("extern \"C\" void __cdecl VF2RandomTreadmillWalkLabel", "extern \"C\" void __cdecl VF2RandomTreadmillRunLabel"),
            ("extern \"C\" void __cdecl VF2RandomTreadmillRunLabel", "extern \"C\" void __cdecl VF2RandomDrinkLabel"),
        ):
            start = src.index(start_marker, src.index("// The Ping-Pong Table borrows the Pool Table's behaviour wholesale"))
            body = src[start:src.index(end_marker, start)]
            self.assertIn("VF2ApplyVenueLabel", body)
            self.assertIn("if (!", body)
        # And the pool wrapper must NOT carry a selector.
        pool = src.index(
            "extern \"C\" void __cdecl VF2RandomPooltableLabel(CVillager &villager)")
        pool_body = src[pool:src.index("// The Exercise Bike borrows", pool)]
        self.assertNotIn("VF2ApplyVenueLabel", pool_body,
                         "the stock pool wrapper must not relabel anything")

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
            # THE EXERCISE BIKE IS NO LONGER ON THE TREADMILL'S OBJECT.
            #
            # SUPERSEDED, recorded rather than deleted (AGENTS.md 11): this
            # expected "0x04", the Treadmill's object, because the bike
            # borrowed TreadmillStd.png.fmap and therefore declared it. The
            # owner asked for the two to become separate items with separate
            # behaviours -- "the exercise bike is a totally new object" -- so
            # the bike now has object 0x99 and its shipped fmap is retargeted
            # to match. FindFurniture resolves purely by object, so sharing
            # 0x04 is what made the two indistinguishable and forced every
            # earlier fix to be a positional guard instead of a separation.
            "__VF2_EXERCISE_BIKE_ITEM_ID__": "__VF2_EXERCISE_BIKE_OBJECT__",
            "__VF2_HOME_GYM_ITEM_ID__": "0x75",
            "__VF2_YOGA_EQUIPMENT_ITEM_ID__": "0x75",
            # SUPERSEDED alongside the bike: the Ping-Pong Table also has its
            # own object now (0x9A), for the same reason and at the owner's
            # request. Sharing the Pool Table's 0x36 is what made villagers
            # target the ping-pong table to play pool.
            "__VF2_PING_PONG_TABLE_ITEM_ID__": "__VF2_PING_PONG_OBJECT__",
        }
        # An optional alternate item id may sit between the item and its
        # object. VF2RunOwnFurnitureAction* gained that parameter so ONE
        # behaviour can serve two ids: the Yoga Equipment needs it, because the
        # stock item (0x220) and the invisible copy are the same thing with
        # different art and a drop on either must reach the same venue. Callers
        # with no second id pass -1. The pairing this test guards -- which
        # OBJECT each added item is bound to -- is otherwise unchanged.
        for item, obj in expected.items():
            self.assertRegex(
                src, rf"{re.escape(item)}, (?:(?:-1|0x[0-9a-fA-F]+), )?{obj}",
                f"{item} is no longer bound to donor object {obj}")
        self.assertIn("CBehavior::WorkoutTreadmill", src)
        self.assertIn("CBehavior::RunningOnTreadmill", src)
        self.assertIn("CBehavior::WorkingOut", src)
        self.assertIn("CBehavior::QuickWorkout", src)
        self.assertIn("CBehavior::PlayingPooltable", src)
        # The bike and the Treadmill must not converge again. The object the
        # bike searches is substituted from MOBILE_EXERCISE_BIKE_OBJECT, and
        # that constant must differ from the donor object the Treadmill keeps,
        # or the separation the owner asked for silently collapses.
        self.assertNotEqual(
            patcher.MOBILE_EXERCISE_BIKE_OBJECT,
            patcher.MOBILE_EXERCISE_BIKE_DONOR_OBJECT,
            "the Exercise Bike is sharing the Treadmill's object again, so "
            "bike and treadmill actions can resolve to each other")
        # Same guarantee for the Ping-Pong Table and the Pool Table.
        self.assertNotEqual(
            patcher.MOBILE_PING_PONG_OBJECT,
            patcher.MOBILE_PING_PONG_DONOR_OBJECT,
            "the Ping-Pong Table is sharing the Pool Table's object again, so "
            "villagers can target the ping-pong table to play pool")
        # And the two separated items must not collide with EACH OTHER.
        self.assertNotEqual(
            patcher.MOBILE_EXERCISE_BIKE_OBJECT,
            patcher.MOBILE_PING_PONG_OBJECT,
            "the bike and the ping-pong table now share an object, which "
            "trades two old bugs for a new one")

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
        # The guard must receive the DONOR's object, which is what this
        # assertion's message always said it wanted. It previously matched on
        # the parameter named `object`, and that was correct only while every
        # item's own object WAS its donor's.
        #
        # The Exercise Bike broke that assumption: it now has its own 0x99
        # while its donors are the stock Treadmill behaviours searching 0x04.
        # Passing 0x99 here would make the guard look for a BIKE under a
        # villager standing on a TREADMILL, match the remote bike's handle,
        # conclude they were on open floor, and walk them off the treadmill --
        # the precise regression this test exists to prevent.
        self.assertIn(
            "VF2VillagerIsOnOtherFurniture(\n"
            "            villager, itemId, altItemId, donorObject)",
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
        # The clone calls gained a fifth argument, the OBJECT PREREQUISITE, so
        # the bike's candidates can require the BIKE to be placed rather than
        # inheriting the Treadmill's 0x04 from the donor record. Without it the
        # bike's autonomous actions were offered only when a Treadmill was
        # placed. The property this test guards is unchanged: the donor slots
        # 0x049 and 0x0E0 are still cloned FROM and never disabled.
        self.assertIn(
            "CloneAutonomousCandidateWithWeight(data, 0x049, 0x0B1, 450, "
            "__VF2_EXERCISE_BIKE_OBJECT__)", src)
        self.assertIn(
            "CloneAutonomousCandidateWithWeight(data, 0x0E0, 0x0B2, 450, "
            "__VF2_EXERCISE_BIKE_OBJECT__)", src)
        clone = src[src.index("static void CloneAutonomousCandidateWithWeight("):]
        clone = clone[:clone.index("\n}")]
        self.assertIn("target[i] = donor[i]", clone,
                      "cloning no longer copies the donor into the target")
        self.assertNotIn("donor[0xCD] = 0", clone,
                         "cloning now disables the donor candidate, which would "
                         "stop the stock Treadmill being selected")
        # And the prerequisite must only ever be written to the TARGET slot.
        self.assertIn("*(unsigned int *)(target + 0xC4) = objectPrerequisite;",
                      clone)
        self.assertNotIn("donor + 0xC4", clone,
                         "the donor's own object prerequisite must not be "
                         "rewritten, or the stock candidate changes too")

    def test_every_clone_call_site_pins_its_object_prerequisite(self):
        """The COMPLETE clone table, every argument, and the sentinel branch.

        Two review findings on #344 showed that asserting individual call
        sites leaves the unasserted ones free. Both mutations below kept 71
        tests green while undoing authorized fixes:

        1. `objectPrerequisite != 0` -> `== 0` gates the bike and ping-pong
           clones on their STOCK DONORS, so bike autonomy needs a Treadmill
           placed and ping-pong needs a Pool Table. That is exactly the
           cross-targeting bug the owner reported.
        2. The four zero-valued sites (WateringWindowBoxes, Home Gym, Yoga,
           WorkKitchen0) set to the bike object gates Home Gym and Yoga on an
           unrelated Exercise Bike existing.

        A third, found by review on the first revision of THIS test: prefixing
        a call with `//` left all twelve assertions passing while the
        generated C++ lost that candidate entirely. So every match below is
        against `active_cpp`, not raw source -- a commented-out call is an
        absent call.

        So this test pins the WHOLE table by exact text rather than sampling
        it, and pins the sentinel's sense behaviourally. A new clone call
        added without a decision about its prerequisite fails here, which is
        the point: the owner's rule is that each item's actions are offered
        when THAT item is placed and never because of another item.
        """
        src = active_cpp(source())

        # donor, target, prerequisite -- the exact expected table.
        #
        # A zero means "write no prerequisite, leave the donor record's own
        # gates alone". That is correct for these five because their donors
        # are stock behaviours that CONSULT NO PLACED ITEM (see the generator
        # at the VF2GymDonorBehaviors comment). There is no object gate in
        # those donor records to inherit, and what confines each action to its
        # item is the handler's own venue search plus the positional
        # eligibility rule, NOT the candidate gate.
        #
        # So a zero here is a deliberate "no gate", not "same gate as the
        # donor". If a donor ever did carry a non-zero +0xC4 that its clone
        # should not inherit, zero would silently keep the WRONG gate and this
        # table would pin that mistake in place -- which is why the reason is
        # recorded here rather than left implicit.
        expected = [
            (0x034, 0x016, "0"),                             # North shower
            (0x076, 0x077, "0"),                             # WateringWindowBoxes
            (0x0A4, 0x0A5, "0"),                             # WashingInBathroomSink0
            (0x0A4, 0x0A6, "0"),                             # WashingInBathroomSink1
            (0x0A4, 0x0A7, "0"),                             # WashingInBathroomSink2
            (0x0A4, 0x0A8, "0"),                             # WashingInBathroomSink3
            (0x049, 0x0B1, "__VF2_EXERCISE_BIKE_OBJECT__"),  # bike, walking
            (0x0E0, 0x0B2, "__VF2_EXERCISE_BIKE_OBJECT__"),  # bike, running
            (0x04A, 0x0B3, "0"),                             # Home Gym System
            (0x08B, 0x0B4, "0"),                             # Yoga Equipment
            (0x099, 0x0B8, "__VF2_PING_PONG_OBJECT__"),      # Ping-Pong Table
            (0x047, 0x048, "0"),                             # WorkKitchen0
        ]

        for donor, target, prerequisite in expected:
            call = ("CloneAutonomousCandidateWithWeight(data, 0x%03X, 0x%03X, "
                    "450, %s)" % (donor, target, prerequisite))
            with self.subTest(target="0x%03X" % target):
                self.assertIn(
                    call, src,
                    "clone 0x%03X -> 0x%03X must pass prerequisite %s. Either "
                    "the call changed or a prerequisite was altered; both "
                    "change WHEN the action is offered in play."
                    % (donor, target, prerequisite))

        # The table must be COMPLETE. Without this, adding a new clone call
        # with a wrong prerequisite would pass every assertion above.
        actual = re.findall(
            r"CloneAutonomousCandidateWithWeight\(data,[^;]*\);", src)
        self.assertEqual(
            len(actual), len(expected),
            "the clone table has %d call sites but this test pins %d. Add the "
            "new call to `expected` WITH a deliberate prerequisite, so its "
            "gating is a decision rather than an inherited accident."
            % (len(actual), len(expected)))

        # And the sentinel's SENSE, not merely the presence of an assignment.
        # `== 0` passes any assertion that only looks for the write.
        clone = src[src.index("static void CloneAutonomousCandidateWithWeight("):]
        clone = clone[:clone.index("\n}")]
        self.assertIn(
            "if (objectPrerequisite != 0) {", clone,
            "the prerequisite must be written when the caller NAMES one. "
            "Inverting this to `== 0` leaves the bike and ping-pong gated on "
            "their donors and clears every zero-valued clone's real gates.")
        self.assertNotIn(
            "if (objectPrerequisite == 0) {", clone,
            "inverted sentinel: zero would overwrite the donor's gates and a "
            "named object would be ignored")

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
