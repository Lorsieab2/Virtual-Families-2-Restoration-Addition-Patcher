#!/usr/bin/env python3
"""A spa-lounger drop that links the wrong chaise degrades ON PURPOSE (#365).

Both spa loungers share the stock eObjectChaise object with every ordinary
chaise, and LinkPeepToFurniture searches from the villager's feet and takes the
nearest free peep slot. So a drop on a spa lounger can link a DIFFERENT chaise:
a nearer ordinary one, the other spa lounger, or this lounger skipped because an
occupant the spa occupancy check cannot see (an ordinary relaxer, who carries no
spa receiving label) holds its slot. When that happens the villager performs an
ordinary chaise relax instead of the spa treatment -- issue #365, reported as
"the spa lounger sometimes uses the behavior from the normal chaise loungers,"
and visible at either orientation.

That degrade is DELIBERATE, not the defect it looks like. LinkPeepToFurniture is
the reservation, it takes no anchor point, and this engine exposes no unlink
call -- so once it lands on the wrong chaise the reservation cannot be given
back. Re-resolving the dropped-on lounger afterwards (e.g. a read-only
FindFurniture on the slot record) was tried and REJECTED across review rounds
8, 9 and 21, because it leaves the engine's reservation on one chaise while the
villager walks to another. test_spa_lounger_pose.py's
EachRouteUsesOnePlacement::test_the_drop_route_uses_the_linked_record_whole is
the guard that forbids that re-anchor, and it must stay green.

This file is a CHARACTERIZATION test: it pins the current, intended fallback so
that a future change to the shared-object drop path is a conscious one and not
an accident, and so the reason the obvious "fix" is absent is recorded next to
the code rather than only in review history. It asserts no behaviour change.
"""
import unittest

import patch_mobile_furniture_pack as patcher


def _source():
    return (patcher.ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
        encoding="utf-8"
    )


def _drop_handler_body():
    """The manual-drop handler's body, comments stripped.

    The DEFINITION is found, not the forward declaration: both begin
    identically and only the definition is followed by an opening brace.
    Comments name the calls they explain, so every assertion here is made
    against the comment-stripped text -- measuring code, not prose.
    """
    source = _source()
    signature = "static bool VF2HandleMobileInvisibleSpaLounger(CVillager &villager)"
    start = source.index(signature + "\n{")
    lines = source[start:].split("\n")
    end = next(i for i, line in enumerate(lines) if line.rstrip() == "}")
    return "\n".join(
        line for line in lines[:end] if not line.strip().startswith("//")
    )


def _fallback_block():
    """The `if (!linkedTheDroppedOnLounger) { ... }` block, comments stripped.

    This is the only place the drop handler can degrade to a chaise relax, so
    the fallback assertions are scoped to it rather than to the whole handler,
    which also contains the ordinary spa path.
    """
    body = _drop_handler_body()
    start = body.index("if (!linkedTheDroppedOnLounger)")
    lines = body[start:].split("\n")
    # The block closes at the first lone `}` at the handler's first indent
    # level (four spaces), which is the `}` of the if-block.
    end = next(i for i, line in enumerate(lines) if line == "    }")
    return "\n".join(lines[: end + 1])


class TestTheWrongLinkDegradesToAChaiseRelax(unittest.TestCase):
    """The intended behaviour of #365's fallback, pinned."""

    def test_the_link_target_is_verified_by_the_dropped_on_handle(self):
        """A drop is a spa treatment only when the link landed on THIS lounger.

        eObjectChaise is shared, so "the link returned a spa lounger" is not
        enough -- with two loungers it could be the other one. The guard
        requires the dropped-on slot's own handle.
        """
        body = _drop_handler_body()
        self.assertIn("int const droppedOn = VF2FurnitureHandleAtSlot(loungerSlot);", body)
        self.assertIn("receiveInfo.unknown0 == droppedOn", body)

    def test_dropped_on_known_comes_from_the_slot_index_not_a_zero_handle(self):
        """Handle 0 is a real handle (the first placement's), so the "is the
        dropped-on slot known" flag must be the slot index, not a zero test
        (review, round 9)."""
        body = _drop_handler_body()
        self.assertIn("bool const droppedOnKnown = loungerSlot >= 0;", body)

    def test_a_mismatched_link_runs_the_ordinary_chaise_relax(self):
        """The fallback plans VF2PlanLinkedChaiseAction, labelled as a relax."""
        block = _fallback_block()
        self.assertIn("VF2PlanLinkedChaiseAction(", block)
        self.assertIn('"Relaxing on lounger"', block)

    def test_the_fallback_does_not_plan_the_spa_treatment(self):
        """The degraded path must not run the treatment on the wrong chaise."""
        block = _fallback_block()
        self.assertNotIn("VF2PlanSpaTreatment", block)

    def test_the_fallback_evicts_the_walker_before_consuming_the_reservation(self):
        """A walker already heading to the linked lounger is released first.

        The fallback consumes the reservation, and custom walk holds are
        invisible to LinkPeepToFurniture, so the release must precede the plan
        (review, round 9)."""
        block = _fallback_block()
        self.assertLess(
            block.index("VF2SpaReleaseHoldOnLounger(receiveInfo.unknown0, &villager);"),
            block.index("VF2PlanLinkedChaiseAction("),
        )


class TestTheRejectedReResolveStaysAbsent(unittest.TestCase):
    """The obvious "fix" for #365 is forbidden here; keep it forbidden.

    Re-resolving the dropped-on lounger after the link splits the reservation
    from the villager and was rejected in review rounds 8, 9 and 21. This is a
    second, local statement of the same rule the pose suite's
    test_the_drop_route_uses_the_linked_record_whole enforces, so the reason is
    recorded beside #365's own tests and a future reader does not rediscover it
    the hard way.
    """

    def test_no_post_link_reresolve_in_the_drop_handler(self):
        body = _drop_handler_body()
        after_link = body[body.index("LinkPeepToFurniture("):]
        for forbidden in ("FindFurniture(", "spaRecord", "UnderVillager("):
            self.assertNotIn(
                forbidden, after_link,
                "the drop handler re-anchors after the link (%s): that is the "
                "reservation/villager split rejected in review rounds 8/9/21 "
                "and forbidden by test_the_drop_route_uses_the_linked_record_"
                "whole. See issue #365." % forbidden)

    def test_the_pose_suite_guard_still_exists(self):
        """The authoritative guard must be present for this cross-reference to
        mean anything; if it is renamed or removed, this fails loudly rather
        than pointing at nothing."""
        pose_suite = (patcher.ROOT / "work" / "test_spa_lounger_pose.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "def test_the_drop_route_uses_the_linked_record_whole", pose_suite,
            "the guard this file cross-references is gone; update the reference "
            "in issue #365's tests")


if __name__ == "__main__":
    unittest.main()
