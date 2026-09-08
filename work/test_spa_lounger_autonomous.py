#!/usr/bin/env python3
"""The spa lounger's receiving half is autonomous; the giving half is not.

Giving a treatment requires a second villager already receiving one on that
same lounger. Autonomous selection picks one villager at a time and cannot
arrange a pair, so an autonomous "giving" would have villagers miming a massage
at an empty chair. Receiving has no such requirement -- one adult, one free
lounger -- so that half, and only that half, is offered autonomously.
"""
import re
import unittest

import patch_mobile_furniture_pack as patcher


def _source():
    return (patcher.ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
        encoding="utf-8"
    )


def _receiving_body():
    """The receiving handler's body, comments stripped.

    Comments name the calls they explain, so an ordering assertion made
    against the raw text would measure prose rather than code. And the
    DEFINITION is found, not the forward declaration -- both begin
    identically and only the definition is followed by an opening brace.
    """
    source = _source()
    signature = "static bool VF2HandleMobileSpaLoungerReceiving(CVillager &villager)"
    start = source.index(signature + "\n{")
    lines = source[start:].split("\n")
    end = next(i for i, line in enumerate(lines) if line.rstrip() == "}")
    return "\n".join(
        line for line in lines[:end] if not line.strip().startswith("//")
    )


class TestOnlyReceivingIsAutonomous(unittest.TestCase):
    def test_the_receiving_handler_exists(self):
        self.assertIn(
            "static bool VF2HandleMobileSpaLoungerReceiving(CVillager &villager)",
            _source(),
        )

    def test_it_is_registered_as_an_external_candidate(self):
        # Not every spec carries a handler key -- the picnic/patio rows are
        # bound by object rather than by named handler.
        handlers = [
            spec.get("handler")
            for spec in patcher.MOBILE_FURNITURE_EXTERNAL_AUTONOMOUS_SPECS
        ]
        self.assertIn("VF2HandleMobileSpaLoungerReceiving", handlers)

    def test_the_candidate_carries_no_mobile_id(self):
        # It is this patcher's own item, so there is no mobile row it was
        # ported from. Inventing an id would imply a provenance it lacks.
        spec = next(
            s
            for s in patcher.MOBILE_FURNITURE_EXTERNAL_AUTONOMOUS_SPECS
            if s.get("handler") == "VF2HandleMobileSpaLoungerReceiving"
        )
        self.assertIsNone(spec["mobile_id"])
        self.assertEqual(spec["object"], patcher.MOBILE_CHAISE_OBJECT)

    def test_it_resolves_a_real_free_spa_lounger_first(self):
        # Checking occupancy where the villager currently STANDS is useless:
        # it samples a position chosen before any destination exists. The
        # candidate must resolve an actual free spa lounger up front, or a
        # villager walks to the nearest ordinary chaise and mimes a treatment
        # on it -- both spa loungers share eObjectChaise with every stock and
        # mobile lounger.
        src = _source()
        start = src.index(
            "static bool VF2HandleMobileSpaLoungerReceiving(CVillager &villager)\n{"
        )
        body = src[start:src.index("\n}", start)]
        self.assertIn("if (!VF2SpaAdult(villager)) return false;", body)
        self.assertIn("VF2FindFreeSpaLoungerSlot(villager)", body)
        self.assertIn("if (loungerSlot < 0) return false;", body)

    def test_no_speculative_link_is_taken(self):
        """The receiving route must never call LinkPeepToFurniture.

        The call RESERVES a peep slot as a side effect and this engine
        exposes no unlink call, so any code shaped "link, then reject if it
        is not a lounger" holds an ordinary chaise against a villager who
        then goes off and does something else.

        A preflight cannot rescue that shape. The link always searches from
        villager.FeetPos(), so a probe anchored at the villager is defeated
        by a FULL nearer chaise (FindFurniture ignores slot availability and
        the link does not), and a probe anchored at the lounger answers a
        question the link never asked. Only not calling it works.
        """
        body = _receiving_body()
        self.assertNotIn(
            "LinkPeepToFurniture", body,
            "a speculative link cannot be released; read the placement "
            "record instead",
        )

    def test_the_walk_anchor_is_hotspot_adjusted(self):
        """PlanToGo must receive info.point, never the raw record position.

        The record's +0x14/+0x18 are the world position. FindFurniture
        produces the walk-to anchor by ADDING the furniture map's hotspot
        offset -- the engine's own instructions, recorded in
        work/test_prop_image_descriptors.py:

            +0x110  sub  esi, [eax]        ; hotspot x
            +0x121  mov  ecx, [ebx + 0x14] ; record x
            +0x127  add  ecx, esi          ; x + hotspot -> info.point.x

        Passing the raw coordinates would walk the villager into the
        furniture footprint, and VF2SpaTreatmentPoint would then subtract
        another four pixels from an already wrong point.
        """
        body = _receiving_body()
        self.assertNotIn(
            "info.point.x = ", body,
            "info.point must come from the lookup, which applies the "
            "hotspot offset, not be assigned from the record",
        )
        self.assertNotIn("info.point.y = ", body)
        self.assertIn("VF2SpaTreatmentPoint(info.point)", body)

    def test_the_lookup_is_the_read_only_one(self):
        # FindFurniture reserves nothing, so asking it costs nothing and
        # there is never anything to release.
        body = _receiving_body()
        self.assertIn("FindFurniture", body)
        self.assertIn("loungerPlacement", body)

    def test_the_lookup_is_confirmed_against_the_chosen_record(self):
        # FindFurniture is nearest-match from the point given. Anchoring it at
        # the record's own position should resolve that placement, but the
        # handle at +0x04 confirms it rather than assuming.
        body = _receiving_body()
        collapsed = " ".join(body.split())
        self.assertIn(
            "*reinterpret_cast<int *>(spaRecord + 0x04) != info.unknown0",
            collapsed,
            "the lookup's result must be tied back to the chosen record",
        )

    def test_a_lounger_walked_toward_is_not_offered_twice(self):
        """VF2SpaOccupantIndex cannot see a villager still walking.

        It asks which furniture slot is under the occupant's feet, so between
        choosing a lounger and arriving at it a recipient is invisible and a
        second adult would be handed the same lounger. The route used to get
        this for free from LinkPeepToFurniture's peep-slot reservation; that
        call was removed because its reservation could not be released, so
        the in-flight part is now kept explicitly.
        """
        source = _source()
        signature = "static int VF2FindFreeSpaLoungerSlot(CVillager &villager)"
        start = source.index(signature + "\n{")
        lines = source[start:].split("\n")
        end = next(i for i, line in enumerate(lines) if line.rstrip() == "}")
        body = "\n".join(
            l for l in lines[:end] if not l.strip().startswith("//"))
        self.assertIn(
            "VF2SpaLoungerClaimedByWalker", body,
            "the finder still offers a lounger someone is walking to",
        )

    def test_the_walk_reservation_is_by_handle(self):
        # Two loungers of the same item id are distinguishable only by the
        # unique handle AddToWorld stamps at record +0x04.
        source = _source()
        start = source.index("static bool VF2SpaLoungerClaimedByWalker(")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn("held.handle != handle", body)

    def test_a_stale_walk_reservation_cannot_block_a_lounger(self):
        # An entry only counts while its villager still carries a receiving
        # label, so an interrupted or dead villager releases the lounger
        # without anything having to clean up after them.
        source = _source()
        start = source.index("static bool VF2SpaLoungerClaimedByWalker(")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn(
            "VF2SpaReceivingIndex(*held.villager) < 0", body,
            "a villager who stopped receiving must stop holding the lounger",
        )

    def test_the_chaise_linker_does_not_reject_after_linking(self):
        """Rejecting a held lounger at this chokepoint is worse, not better.

        A previous revision checked the walk holds here and returned false
        for a held lounger. That recreated the link-then-reject shape the
        spa route had just been rebuilt to avoid: LinkPeepToFurniture has
        ALREADY taken the peep slot, there is no unlink, and the caller then
        runs the unfurnitured behaviour -- so the lounger stays reserved
        against a villager who never uses it, for that whole behaviour.

        Measured rather than argued. Accepting means a reader occupies the
        lounger for GetRandom(20) + 20 and releases it normally; rejecting
        holds it, empty, for the entire fallback. The overlap is cheaper.
        """
        source = _source()
        start = source.index(
            "static bool VF2TryLinkMobileChaise(CVillager &villager, "
            "sFurnitureInfo2 &info)")
        body = source[start:source.index("\n}\n", start)]
        code = "\n".join(
            l for l in body.split("\n") if not l.strip().startswith("//"))
        self.assertNotIn(
            "VF2SpaLoungerClaimedByWalker", code,
            "rejecting here leaks the reservation the link just took",
        )
        self.assertIn("LinkPeepToFurniture", code)

    def test_the_chaise_linker_evicts_the_walker_it_displaced(self):
        """Keeping the link is not enough on its own.

        The spa route does NOT absorb this collision by itself:
        VF2FindFreeSpaLoungerSlot skips held loungers, but only a spa caller
        consults it -- a villager looking for somewhere to read never does.
        An earlier comment here claimed otherwise and was wrong, and nothing
        cancelled the recipient's queued PlanToGo, so both arrived.

        So the reservation is kept and the WALKER is turned away, with the
        handle the link just returned, exactly as the manual drop path does.
        """
        source = _source()
        start = source.index(
            "static bool VF2TryLinkMobileChaise(CVillager &villager, "
            "sFurnitureInfo2 &info)")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn(
            "VF2SpaReleaseHoldOnLounger(info.unknown0, &villager)", body,
            "the displaced spa recipient still walks to this lounger and "
            "sits down on top of whoever linked it",
        )

    def test_the_eviction_uses_the_handle_the_link_returned(self):
        # The engine chose the placement, so only its returned handle names
        # the lounger actually reserved. Evicting on anything else would
        # turn away a walker heading somewhere entirely different.
        source = _source()
        start = source.index(
            "static bool VF2TryLinkMobileChaise(CVillager &villager, "
            "sFurnitureInfo2 &info)")
        body = source[start:source.index("\n}\n", start)]
        link = body.index("LinkPeepToFurniture")
        evict = body.index("VF2SpaReleaseHoldOnLounger")
        self.assertLess(
            link, evict,
            "info.unknown0 is not known until the link returns",
        )

    def test_a_player_drop_takes_the_lounger_from_a_walker(self):
        """The drop wins, and the stale claim is cleared rather than kept.

        A player may drop an adult onto a lounger an autonomous recipient is
        still walking to. VF2SpaOccupantIndex cannot see the walker and the
        link cannot see the custom hold, so without this both target it.

        Refusing the drop would be the wrong resolution -- the player put
        the villager there, and the engine has already reserved the slot
        with no way to give it back. So the walker's claim on THIS placement
        is released instead, which stops it blocking other selections.
        """
        source = _source()
        start = source.index(
            "static bool VF2HandleMobileInvisibleSpaLounger(CVillager &villager)")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn(
            "VF2SpaReleaseHoldOnLounger(receiveInfo.unknown0, &villager)",
            body,
            "a player drop leaves another villager's claim on the lounger, "
            "so it goes on blocking that lounger for everyone else",
        )

    def test_only_the_claim_on_that_lounger_is_released(self):
        # A walker heading somewhere else keeps their claim, and the dropped
        # villager's own claim is not the one being cleared.
        source = _source()
        start = source.index("static void VF2SpaReleaseHoldOnLounger(")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn(".handle != handle) continue;", body)
        self.assertIn("walker == keep) continue;", body)

    def test_the_displaced_walker_is_actually_turned_away(self):
        """Clearing the bookkeeping does not stop a villager walking.

        The walker's PlanToGo and treatment sequence were queued by
        StartNewBehavior before the drop happened, so zeroing two fields
        leaves them arriving anyway and sitting down on top of the dropped
        villager. An earlier version did exactly that while its comment
        claimed the walker would re-evaluate.
        """
        source = _source()
        start = source.index("static void VF2SpaReleaseHoldOnLounger(")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn(
            "ForgetPlans(*walker, false)", body,
            "the walker keeps its queued plans and still arrives",
        )
        self.assertIn("StartNewBehavior(*walker)", body)

    def test_the_claim_is_cleared_before_the_walker_re_evaluates(self):
        # Re-evaluation may well come straight back to this route. If the
        # stale claim were still there the walker would rule out the lounger
        # it is itself holding.
        source = _source()
        start = source.index("static void VF2SpaReleaseHoldOnLounger(")
        body = source[start:source.index("\n}\n", start)]
        cleared = body.index(".handle = 0;")
        restarted = body.index("StartNewBehavior(*walker)")
        self.assertLess(
            cleared, restarted,
            "the walker re-evaluates while still holding its own claim",
        )

    def test_only_a_villager_still_receiving_is_interrupted(self):
        # One that finished, or was already interrupted by something else,
        # has plans of its own that this must not throw away.
        source = _source()
        start = source.index("static void VF2SpaReleaseHoldOnLounger(")
        body = source[start:source.index("\n}\n", start)]
        guard = body.index("VF2SpaReceivingIndex(*walker) < 0")
        forget = body.index("ForgetPlans(*walker, false)")
        self.assertLess(
            guard, forget,
            "an unrelated behaviour would be cancelled",
        )

    def test_an_interrupted_walk_does_not_keep_holding_its_lounger(self):
        """The same-label interruption case, not just the predicate.

        A villager walking to lounger A who is dropped onto lounger B gets a
        FRESH receiving label from the manual route. The stale-entry guard in
        VF2SpaLoungerClaimedByWalker tests for a receiving label, so that new
        label would keep the hold on A looking live for the whole treatment
        at B, and other adults would skip a lounger that is actually free.

        So the manual receiving route must retarget the reservation onto the
        lounger it actually linked.
        """
        source = _source()
        start = source.index(
            "static bool VF2HandleMobileInvisibleSpaLounger(CVillager &villager)")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn(
            "VF2SpaHoldLoungerForWalk(villager, receiveInfo.unknown0, false)", body,
            "the manual route sets a receiving label without retargeting the "
            "reservation, so an interrupted walk keeps holding its lounger",
        )

    def test_a_giver_stops_holding_any_lounger(self):
        # A giver occupies no lounger of their own, so a walk they had started
        # is over. Their receiving label is gone too, but the hold is keyed by
        # villager and has to be dropped explicitly.
        source = _source()
        start = source.index(
            "static bool VF2HandleMobileInvisibleSpaLounger(CVillager &villager)")
        body = source[start:source.index("\n}\n", start)]
        giving = body.index("kVF2SpaGivingLabels[receiving]")
        self.assertIn(
            "VF2SpaReleaseLoungerHold(villager)", body[giving:],
            "a villager who switches to giving must release the lounger they "
            "were walking to",
        )

    def test_releasing_a_hold_clears_both_fields(self):
        # Leaving a handle behind with a null villager would let a later
        # villager reusing that slot inherit a stale handle.
        source = _source()
        start = source.index("static void VF2SpaReleaseLoungerHold(")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn(".villager = 0", body)
        self.assertIn(".handle = 0", body)

    def test_the_reservation_helpers_precede_every_caller(self):
        # The manual route is emitted BEFORE the finder, so the helpers have
        # to sit above it too. Declaring them next to the finder compiled in
        # the autonomous route and broke this one.
        source = _source()
        table = source.index(
            "static VF2SpaWalkReservation gVF2SpaWalkReservations[30]")
        hold = source.index("static void VF2SpaHoldLoungerForWalk(")
        release = source.index("static void VF2SpaReleaseLoungerHold(")
        manual = source.index(
            "static bool VF2HandleMobileInvisibleSpaLounger(")
        receiving_index = source.index("static int VF2SpaReceivingIndex(")
        claimed = source.index("static bool VF2SpaLoungerClaimedByWalker(")
        for label, earlier, later in (
            ("table before hold", table, hold),
            ("hold before the manual route", hold, manual),
            ("release before the manual route", release, manual),
            ("VF2SpaReceivingIndex before its caller",
             receiving_index, claimed),
        ):
            with self.subTest(order=label):
                self.assertLess(earlier, later)

    def test_a_chaise_linker_holds_what_it_linked(self):
        """Evicting the previous walker is only half of it.

        Between a reading/napping/resting/studying villager linking a spa
        lounger and finishing with it, a spa recipient selected afterwards
        would find the placement free: VF2SpaOccupantIndex needs a spa
        receiving label the linker does not have, and the spa finder does
        not read the engine's peep-slot state. So the linker records its
        own claim.
        """
        source = _source()
        start = source.index(
            "static bool VF2TryLinkMobileChaise(CVillager &villager, "
            "sFurnitureInfo2 &info)")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn(
            "VF2SpaHoldLoungerForWalk(villager, info.unknown0, true)", body,
            "nothing records the chaise linker, so a spa recipient chosen "
            "afterwards can walk onto the lounger it is using",
        )
        evict = body.index("VF2SpaReleaseHoldOnLounger")
        claim = body.index("VF2SpaHoldLoungerForWalk")
        self.assertLess(
            evict, claim,
            "the claim must be recorded after the eviction, or the eviction "
            "would clear the claim just made",
        )

    def test_a_chaise_claim_expires_when_the_villager_moves_on(self):
        """A claim that cannot expire is the leak this route was rebuilt to avoid.

        A chaise holder carries no spa receiving label, so the label test
        that expires a spa claim would hold its lounger forever. The engine's
        own link is the authority instead: while linked, the villager is on a
        chaise or walking to one, and VF2FurnitureSlotUnderVillager reports
        the slot beneath it once it arrives.
        """
        source = _source()
        start = source.index("static bool VF2SpaLoungerClaimedByWalker(")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn("held.chaise", body)
        self.assertIn(
            "VF2FurnitureSlotUnderVillager(*held.villager)", body,
            "a chaise claim with no expiry blocks the lounger permanently",
        )
        self.assertIn("under != slotOfHandle) continue;", body)

    def test_a_spa_claim_still_expires_on_its_label(self):
        # The chaise arm must not swallow the spa arm: a spa recipient's
        # claim still lapses when it stops carrying a receiving label.
        source = _source()
        start = source.index("static bool VF2SpaLoungerClaimedByWalker(")
        body = source[start:source.index("\n}\n", start)]
        chaise = body.index("held.chaise")
        label = body.index("VF2SpaReceivingIndex(*held.villager) < 0")
        self.assertLess(chaise, label)
        self.assertIn("VF2SpaReceivingIndex(*held.villager) < 0", body)

    def test_the_reservation_is_taken_only_once_the_walk_is_committed(self):
        # A route that returns early must never leave a lounger held.
        body = _receiving_body()
        hold = body.index("VF2SpaHoldLoungerForWalk")
        start = body.index("StartNewBehavior")
        self.assertLess(
            start, hold,
            "the lounger is held before the behaviour is committed, so an "
            "early return above would leak it",
        )

    def test_the_occupancy_bit_is_rechecked(self):
        # record[+0x0C] & 1 is the occupancy bit. A slot index alone is not a
        # guarantee the record is still live.
        body = _receiving_body()
        self.assertIn("0x0C", body)

    def test_identity_is_by_placement_handle_not_by_position(self):
        # info.point is the WALK-TO ANCHOR, so hit-testing it asks which item
        # the villager stands INSIDE and returns -1 for anything they stand
        # beside. That is what once left a villager at the Ping-Pong Table
        # labelled "Playing pool". Two chaises of the same type are
        # distinguishable only by handle.
        body = _receiving_body()
        self.assertIn("VF2SpaLoungerHasHandle(info.unknown0)", body)
        self.assertNotIn(
            "VF2FurnitureItemAtPoint(info.point)", body,
            "position lookups cannot tell two chaises of one type apart",
        )

    def test_the_finder_accepts_only_the_two_spa_loungers(self):
        src = _source()
        start = src.index("static int VF2FindFreeSpaLoungerSlot(CVillager &villager)")
        body = src[start:src.index("\n}", start)]
        self.assertIn("__VF2_INVISIBLE_SPA_LOUNGER_ITEM_ID__", body)
        self.assertIn("__VF2_SPA_LOUNGER_ITEM_ID__", body)
        # And free means free: a lounger somebody is receiving on is the
        # giving half's business, which stays a manual drop.
        self.assertIn("if (VF2SpaOccupantIndex(villager, slot, 0)) continue;", body)

    def test_the_treatment_matches_the_nap(self):
        # Duration, posture and the gulp-and-sigh all come from the game's own
        # values rather than invented ones.
        src = _source()
        start = src.index("static void VF2PlanSpaTreatment(")
        body = src[start:src.index("\n}", start)]
        self.assertIn("ldwGameState::GetRandom(11) + 55", body) # about one real minute
        self.assertIn("PlanToLieDown", body)                    # the nap's posture
        self.assertIn("info.orientation == 1", body)            # chosen per lounger
        self.assertIn("static_cast<ESound>(0x101)", body)       # gulpahh_01.ogg

    def test_receiving_uses_sleep_animation_and_preserves_total_duration(self):
        src = _source()
        start = src.index("static void VF2PlanSpaTreatment(")
        body = src[start:src.index("\n}", start)]
        self.assertIn("int const settle = 10;", body)
        self.assertIn('PlanToPlayAnim(total - settle, "SleepNW"', body)
        self.assertIn('PlanToPlayAnim(total - settle, "SleepNE"', body)

    def test_both_receiving_routes_raise_the_walk_target_slightly(self):
        src = _source()
        self.assertIn("static ldwPoint VF2SpaTreatmentPoint(ldwPoint point)", src)
        self.assertEqual(src.count("VF2SpaTreatmentPoint(receiveInfo.point)"), 1)
        self.assertEqual(src.count("VF2SpaTreatmentPoint(info.point)"), 1)
        helper = src[src.index("static ldwPoint VF2SpaTreatmentPoint"):src.index("static char const *const kVF2SpaReceivingLabels", src.index("static ldwPoint VF2SpaTreatmentPoint"))]
        self.assertIn("point.y -= 4;", helper)

    def test_manual_giving_uses_the_same_one_minute_duration(self):
        src = _source()
        start = src.index(
            "// Somebody already on THIS lounger? Then this adult performs"
        )
        body = src[start:src.index("\n    // Nobody on this one", start)]
        self.assertIn("plans->PlanToWork(ldwGameState::GetRandom(11) + 55);", body)

    def test_the_giving_labels_are_never_used_autonomously(self):
        src = _source()
        start = src.index(
            "static bool VF2HandleMobileSpaLoungerReceiving(CVillager &villager)\n{"
        )
        body = src[start:src.index("\n}", start)]
        self.assertIn("kVF2SpaReceivingLabels", body)
        self.assertNotIn("kVF2SpaGivingLabels", body)


class TestTheDeclarationPrecedesItsUse(unittest.TestCase):
    """The candidate table names the handler, so it must be declared first.

    Getting this wrong compiles fine as Python and fails as C with
    'undeclared identifier', which no source-reading test would catch --
    the generated file has to be compiled to see it.
    """

    def test_forward_declaration_comes_before_the_candidate_table(self):
        src = _source()
        decl = src.index(
            "static bool VF2HandleMobileSpaLoungerReceiving(CVillager &villager);"
        )
        use = src.index("            VF2HandleMobileSpaLoungerReceiving,")
        self.assertLess(
            decl, use,
            "the handler must be forward-declared before the autonomous "
            "candidate table that names it",
        )


if __name__ == "__main__":
    unittest.main()
