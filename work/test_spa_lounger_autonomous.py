#!/usr/bin/env python3
"""The spa lounger's receiving half is autonomous; the giving half is not.

Giving a treatment requires a second villager already receiving one on that
same lounger. Autonomous selection picks one villager at a time and cannot
arrange a pair, so an autonomous "giving" would have villagers miming a massage
at an empty chair. Receiving has no such requirement -- one adult, one free
lounger -- so that half, and only that half, is offered autonomously.
"""
import re
import pathlib
import tempfile
import shutil
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


def _release_hold_body():
    """VF2SpaReleaseHoldOnLounger's body, comments stripped.

    The comments name the calls they explain -- StartNewBehavior above all,
    since the fix is that it is NOT called -- so an assertion against the raw
    text measures prose rather than code.
    """
    source = _source()
    start = source.index("static void VF2SpaReleaseHoldOnLounger(")
    body = source[start:source.index("\n}\n", start)]
    return "\n".join(
        line for line in body.split("\n") if not line.strip().startswith("//")
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
            "ForgetPlans(", body,
            "the walker keeps its queued plans and still arrives",
        )
        self.assertIn("*walker, false)", body)

    def test_the_claim_is_not_handed_to_the_taker(self):
        # Reassigning the entry to `keep` looks equivalent and is not: one of
        # the two callers is VF2TryLinkMobileChaise, whose villager carries no
        # receiving label, so that claim would never expire -- the mechanism
        # reverted in the previous commit.
        source = _source()
        start = source.index("static void VF2SpaReleaseHoldOnLounger(")
        body = source[start:source.index("\n}\n", start)]
        self.assertNotIn(
            "villager = keep", body,
            "handing the claim to the taker revives the unexpirable-claim "
            "problem when that taker is a chaise linker",
        )

    def test_the_displaced_walker_is_not_restarted_synchronously(self):
        """No StartNewBehavior here -- that is the whole fix.

        Four attempts to make a synchronous restart safe each failed for a
        DIFFERENT reason -- the asking-villager skip, the receiving-label
        liveness check, and the pointer keying that lets a nested hold reuse
        the same slot. VF2SpaReleaseHoldOnLounger's header comment sets them
        out one by one and is the single source of truth for that history;
        this docstring deliberately does not restate it, because three
        copies of one explanation is how two of them went stale.

        ForgetPlans alone is what nearly every other interrupt site in this
        file does. The engine picks a villager with no plans up on its next
        tick, by which time this function has returned and the table is
        settled.
        """
        body = _release_hold_body()
        self.assertNotIn(
            "StartNewBehavior", body,
            "a synchronous restart re-enters the spa route from inside this "
            "frame, and the walker cannot be excluded from its own claim",
        )
        self.assertIn("ForgetPlans(", body)
        self.assertIn("*walker, false)", body)

    def test_the_entry_is_released_unconditionally(self):
        # With nothing running between the interrupt and the release, the
        # conditional cleanup the reentrant version needed is gone.
        source = _source()
        start = source.index("static void VF2SpaReleaseHoldOnLounger(")
        body = source[start:source.index("\n}\n", start)]
        self.assertIn("villager = 0;", body)
        self.assertIn("handle = 0;", body)
        self.assertNotIn("VF2_SPA_NO_HANDLE", body)

    def test_no_sentinel_handle_remains(self):
        # The sentinel existed only to survive the restart.
        self.assertNotIn("VF2_SPA_NO_HANDLE", _source())

    def test_only_a_villager_still_receiving_is_interrupted(self):
        # One that finished, or was already interrupted by something else,
        # has plans of its own that this must not throw away.
        source = _source()
        start = source.index("static void VF2SpaReleaseHoldOnLounger(")
        body = source[start:source.index("\n}\n", start)]
        guard = body.index("VF2SpaReceivingIndex(*walker) >= 0")
        forget = body.index("ForgetPlans(")
        self.assertLess(
            guard, forget,
            "an unrelated behaviour would be cancelled",
        )
        # And the entry is released even when the walker was not
        # interrupted, so a finished villager stops holding its lounger.
        self.assertIn("villager = 0;", body[forget:])

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
            "VF2SpaHoldLoungerForWalk(villager, receiveInfo.unknown0)", body,
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

    def test_the_chaise_linker_records_no_claim_of_its_own(self):
        """A claim was tried here and REVERTED; this pins the decision.

        Recording one looked right -- without it a spa recipient chosen
        while a reading villager is on the lounger can be sent to the same
        placement. But no sound expiry is available. Keyed on the
        villager's current furniture slot, a villager standing on bare
        floor reports -1, which is indistinguishable from "still walking",
        so the claim outlived the action and suppressed autonomous spa
        treatments INDEFINITELY whenever a household has one lounger.

        Permanently losing the feature is strictly worse than a reading
        villager holding the lounger for GetRandom(20) + 20 and releasing
        it normally. Closing it properly needs the peep-slot fields of the
        placement record, which this repository does not decode.
        """
        source = _source()
        start = source.index(
            "static bool VF2TryLinkMobileChaise(CVillager &villager, "
            "sFurnitureInfo2 &info)")
        body = source[start:source.index("\n}\n", start)]
        code = "\n".join(
            l for l in body.split("\n") if not l.strip().startswith("//"))
        self.assertNotIn(
            "VF2SpaHoldLoungerForWalk", code,
            "a chaise claim has no sound expiry here; the last one blocked "
            "the lounger permanently when the villager stood on bare floor",
        )
        self.assertIn(
            "VF2SpaReleaseHoldOnLounger(info.unknown0, &villager)", code,
            "the eviction must stay -- it is what stops a displaced walker "
            "arriving on top of whoever linked here",
        )

    def test_the_reservation_record_carries_no_kind_flag(self):
        # The flag existed only to give chaise claims a different expiry.
        # With those gone, every claim expires the same way: on the spa
        # receiving label. One rule, no second liveness test to get wrong.
        source = _source()
        start = source.index("struct VF2SpaWalkReservation")
        body = source[start:source.index("};", start)]
        self.assertNotIn("chaise", body)

    def test_every_claim_expires_on_the_receiving_label(self):
        source = _source()
        start = source.index("static bool VF2SpaLoungerClaimedByWalker(")
        body = source[start:source.index("\n}\n", start)]
        self.assertNotIn("held.chaise", body)
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


class TheGuardSurvivesIntoTheEmittedArtifact(unittest.TestCase):
    """Every other check in this file reads the GENERATOR, not its output.

    That is the weakness Codex named on #253: a source-contract test still
    passes if the block stops being emitted, if a stale generated file is
    compiled, or if the emission is gated behind a flag that is off. The
    generator saying the right thing and the build shipping it are two
    different claims.

    This one regenerates under VF2_ENABLE_BEHAVIOR_PATCHES=1 and reads the
    .cpp the compiler is handed. It skips only when the generated sources are
    genuinely absent -- never on an exception from the generator itself,
    because a generator that crashes is the regression, not a missing
    prerequisite.
    """

    OBJS = "patched_mobile_furniture_pack_objs"

    # The emitters this class drives, and the file each must produce. Naming
    # them is the point: an emitter that silently stops writing its file would
    # otherwise leave every assertion below searching an empty string and
    # passing for the wrong reason.
    REQUIRED_EMITTERS = (
        "patch_spontaneous_behaviors",
        "patch_mobile_furniture_behavior_dispatch",
    )

    @classmethod
    def _generate(cls):
        """Emit the sources into a TEMP directory and return them joined.

        NOT a glob of work/patched_mobile_furniture_pack_objs. That directory
        is gitignored and persistent, so globbing it means: on a clean checkout
        every test here skips, and after an older or interrupted run they
        validate STALE C++ even when the current generator no longer emits the
        handler -- the exact regression this class exists to catch. Measured on
        main before this change: the directory held three unrelated .cpp files
        from a partial run and the class reported "3 failed" against code that
        has nothing to do with the spa lounger.

        Deliberately NOT a hardcoded filename either. Which file a function is
        emitted into is an implementation detail of the generator's layout, so
        naming one would fail on a harmless reorganisation while still passing
        if the code vanished from the file it moved out of.
        """
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            for name in ("Villager.obj", "VillagerAI.obj", "Behavior.obj",
                         "theMainScene.obj"):
                src = patcher.SRC_OBJS / name
                if not src.is_file():
                    return None, "missing build input %s" % name
                shutil.copy2(src, temp_root / name)
            old_patched = patcher.PATCHED
            # THE FLAG-ON BRANCH IS WHAT SHIPS. ENABLE_BEHAVIOR_PATCHES is
            # fixed at import time and is False under a normal test run, so
            # emitting without forcing it produces the flag-OFF branch --
            # measured at 256211 chars against 257838 with it on. The handler
            # appears in both, so the assertions were not vacuous, but they
            # were describing a branch the release does not build.
            old_flag = getattr(patcher, "ENABLE_BEHAVIOR_PATCHES", None)
            try:
                patcher.PATCHED = temp_root
                if old_flag is not None:
                    patcher.ENABLE_BEHAVIOR_PATCHES = True
                # An exception here is the regression, not a missing
                # prerequisite, so it is deliberately NOT caught.
                patcher.patch_spontaneous_behaviors({})
                # The spa release handler is emitted by the DISPATCH pass, not
                # the spontaneous one. Verified rather than assumed:
                # VF2SpaReleaseHoldOnLounger lives inside
                # patch_mobile_furniture_behavior_dispatch.
                patcher.patch_mobile_furniture_behavior_dispatch({})
            finally:
                patcher.PATCHED = old_patched
                if old_flag is not None:
                    patcher.ENABLE_BEHAVIOR_PATCHES = old_flag
            sources = sorted(temp_root.glob("*.cpp"))
            if not sources:
                # NOT a skip. Skipping is for a missing PREREQUISITE; an
                # emitter that runs and writes nothing is the regression, and
                # returning a skip here left the suite green while the check
                # that would have caught it never ran.
                raise AssertionError(
                    "the emitters ran but produced no .cpp at all")
            # Hand the sources to the persistent objs directory when it
            # exists, so test_generated_cpp_compiles.py -- which owns the
            # compile question -- is compiling this same emission rather than
            # whatever an older run left behind. RESIDUAL, stated plainly:
            # pattern-matching text cannot prove the C++ is syntactically
            # valid or that the build includes it; only that compile does.
            objs = patcher.ROOT / "work" / cls.OBJS
            if objs.is_dir():
                for src in sources:
                    try:
                        shutil.copy2(src, objs / src.name)
                    except OSError:
                        pass
            return ("\n".join(p.read_text(encoding="utf-8", errors="replace")
                              for p in sources), len(sources))

    @staticmethod
    def _strip_comments(text):
        """Code, not prose. A guard that is commented out is not a guard."""
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        return re.sub(r"//[^\n]*", "", text)

    def setUp(self):
        result = self._generate()
        if result is None or result[0] is None:
            # Only a genuinely absent BUILD INPUT is a skip. _generate raises
            # for an emission that produced nothing, so that path cannot be
            # mistaken for a missing prerequisite.
            reason = result[1] if result else "generation failed"
            self.skipTest(
                "cannot emit the C++ in this checkout: %s" % reason)
        text, count = result
        self.emitted = text
        # Every assertion below runs against comment-stripped code, so a
        # commented-out guard cannot satisfy a substring search.
        self.code = self._strip_comments(text)
        self.source_count = count

    def test_the_emission_actually_produced_something_to_inspect(self):
        """An empty emission must not pass by searching an empty string.

        This is the residual on "decode the compiled helper rather than its
        source": reading the .cpp still does not prove the compiler was handed
        it -- test_generated_cpp_compiles.py answers that. What this can do is
        refuse to draw conclusions from an emission that produced nothing,
        which is how the stale-directory defect presented.

        An earlier version of this asserted a source count of ten, carried over
        from a FULL generator run. This class drives only the two emitters that
        produce the handler under test, so ten was never the right number and
        the assertion failed on correct output -- a fact about the threshold,
        not the artifact.
        """
        self.assertGreater(
            self.source_count, 0,
            "the emitters produced no .cpp at all, so every assertion in this "
            "class would be searching an empty string")
        self.assertGreater(
            len(self.code.strip()), 1000,
            "the emitted C++ is only %d characters after stripping comments; "
            "that is not a real emission"
            % len(self.code.strip()))
        for name in self.REQUIRED_EMITTERS:
            self.assertTrue(
                hasattr(patcher, name),
                "%s no longer exists, so this class is no longer driving the "
                "pass that emits the handler it checks" % name)

    def test_the_reservation_release_is_in_the_shipped_source(self):
        self.assertIn(
            "VF2SpaReleaseHoldOnLounger", self.code,
            "the release handler never reached the emitted C++, so every "
            "source-contract check in this file is describing code the build "
            "does not compile")

    def test_the_walker_skip_is_in_the_shipped_source(self):
        """A villager must never be excluded by its own claim."""
        # Against COMMENT-STRIPPED code: `// if (!walker || walker == keep)`
        # satisfies a raw substring search while the shipped build has no
        # guard at all.
        self.assertIn(
            "walker == keep", self.code,
            "the self-claim skip is absent from the emitted C++")

    def test_no_synchronous_restart_reached_the_artifact(self):
        """The restart was removed for a family of defects; if it comes back
        in the emitted source, it comes back in the game.

        COMMENTS ARE STRIPPED FIRST. The handler's own comment explains at
        length why StartNewBehavior was removed, so a raw substring search
        matches that prose and fails on correct code -- which it did on the
        first draft of this test. Measuring code means measuring code.
        """
        body = self.code
        start = body.find("VF2SpaReleaseHoldOnLounger(int handle")
        self.assertGreater(
            start, -1, "the release handler's definition is not in the "
            "emitted C++")
        end = body.find("\n}", start)
        code = body[start:end]
        self.assertNotIn(
            "StartNewBehavior", code,
            "a synchronous restart is back inside the release handler in the "
            "emitted C++")


if __name__ == "__main__":
    unittest.main()
