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

    def test_the_read_only_probe_runs_before_the_link(self):
        """A rejected chaise must never have been reserved first.

        LinkPeepToFurniture takes a peep slot as a side effect and this
        engine exposes no unlink call, so checking after the link means an
        ordinary chaise nearer than the lounger gets held against a villager
        who then goes off and does something else -- excluding everyone else
        from it for the duration. FindFurniture answers the same
        nearest-match question and reserves nothing.

        Asserted as an ORDERING rather than by pinning either call's
        arguments, so a rewrite that keeps the property still passes.
        """
        body = _receiving_body()
        probe = body.index("FindFurniture")
        link = body.index("LinkPeepToFurniture")
        self.assertLess(
            probe, link,
            "the link reserves a peep slot, so the identity check has to "
            "happen before it, not after",
        )

    def test_the_probe_result_is_checked_before_the_link(self):
        body = _receiving_body()
        check = body.index("VF2SpaLoungerHasHandle")
        link = body.index("LinkPeepToFurniture")
        self.assertLess(
            check, link,
            "probing and then linking regardless would reserve the chaise "
            "the probe just rejected",
        )

    def test_identity_is_by_placement_handle_not_by_position(self):
        # info.point is the WALK-TO ANCHOR, so hit-testing it asks which item
        # the villager stands INSIDE and returns -1 for anything they stand
        # beside. That is what once left a villager at the Ping-Pong Table
        # labelled "Playing pool". Two chaises of the same type are
        # distinguishable only by handle.
        body = _receiving_body()
        self.assertIn("unknown0", body)
        self.assertNotIn(
            "VF2FurnitureItemAtPoint(probe.point)", body,
            "position lookups cannot tell two chaises of one type apart",
        )
        self.assertNotIn("VF2FurnitureItemAtPoint(info.point)", body)

    def test_what_the_link_actually_reserved_is_confirmed(self):
        # The probe and the link ask slightly different questions -- the
        # linker also skips placements with no free peep slot -- so the
        # result is confirmed rather than assumed.
        body = _receiving_body()
        link = body.index("LinkPeepToFurniture")
        after = body[link:]
        self.assertIn(
            "VF2SpaLoungerHasHandle(info.unknown0)", after,
            "the link's own result is never checked, so a lounger that "
            "filled up between the probe and the link goes unnoticed",
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
