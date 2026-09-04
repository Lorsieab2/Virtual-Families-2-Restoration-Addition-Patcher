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
        self.assertIn("ldwGameState::GetRandom(5) + 5", body)   # the nap's duration
        self.assertIn("PlanToLieDown", body)                    # the nap's posture
        self.assertIn("info.orientation == 1", body)            # chosen per lounger
        self.assertIn("static_cast<ESound>(0x101)", body)       # gulpahh_01.ogg

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
