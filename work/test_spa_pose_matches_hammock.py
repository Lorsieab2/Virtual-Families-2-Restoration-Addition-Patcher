"""The spa loungers must pose EXACTLY like the normal chaise loungers.

THE OWNER'S INSTRUCTION, after ten failed rounds:

    "just copy the villager orientation/sleeping action data from the
     normal chaise loungers."

WHAT THE NORMAL LOUNGERS ACTUALLY DO. `VF2HandleMobileChaise` is the
handler driving the loungers the owner has confirmed working. Its pose
branch is:

    if (info.orientation == 1) {
        plans->PlanToWait(duration, eBodyPositionChaise, dir, head);
    } else {
        plans->PlanToLieDown(duration);        <-- normal loungers
    }

Ordinary loungers fall through to `PlanToLieDown` and nothing else: no
`eBodyPositionChaise`, no supplied direction, no head, no Sleep strip.
The engine derives the facing from the furniture itself. That is why
those placements were never reported wrong.

WHY TEN ROUNDS FAILED. The condition used to read

    if (info.orientation == 1 || VF2SpaLoungerHasHandle(info.unknown0))

which FORCED spa loungers into the `PlanToWait` branch while every
ordinary lounger took `PlanToLieDown`. Every round then argued about
which constants to feed that branch -- NE vs NW, coupled vs opposite
arms, 3-arg vs 4-arg. The arguments were never the issue. The spa
loungers were the only furniture routed into the only branch ever
reported broken.

These tests pin the fix: spa loungers take the same path as the normal
ones, and the receiving treatment uses `PlanToLieDown` for its full
duration.
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
DISASM = ROOT / "work" / "VillagerPlans_patched_disasm.txt"


def _source():
    return GEN.read_text(encoding="utf-8")


def _strip_comments(text):
    """Judge CODE, not prose: comments here quote the old wrong forms."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        out.append(line.split("//")[0] if "//" in line else line)
    return "\n".join(out)


def _spa_body(src):
    start = src.index("static void VF2PlanSpaTreatment(")
    return _strip_comments(src[start:src.index("\n}\n", start)])


class TestSpaLoungersCopyTheNormalOnes(unittest.TestCase):
    def test_plan_to_lie_down_is_a_real_engine_function(self):
        """Ground truth, so nobody re-derives it from the generator."""
        if not DISASM.is_file():
            self.skipTest("disassembly not present in this checkout")
        text = DISASM.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "?PlanToLieDown@CVillagerPlans@@QAEXH@Z", text,
            "PlanToLieDown is missing from the decoded binary")

    def test_the_receiving_treatment_uses_plan_to_lie_down(self):
        """The spa treatment poses the villager the normal lounger's way."""
        spa = _spa_body(_source())
        self.assertIn(
            "plans->PlanToLieDown(total);", spa,
            "the spa receiving treatment no longer uses PlanToLieDown for "
            "its full duration. The normal chaise loungers -- the ones the "
            "owner confirmed working -- use PlanToLieDown and nothing else.")

    def test_the_receiving_treatment_plans_no_pose_or_strip(self):
        """No PlanToWait, no Sleep strip: the normal loungers use neither.

        Ten rounds were spent tuning those arguments. The normal loungers
        never supply them at all.
        """
        spa = _spa_body(_source())
        self.assertNotIn(
            "PlanToWait", spa,
            "the spa treatment plans a PlanToWait pose again. Normal "
            "loungers do not; they call PlanToLieDown and let the engine "
            "derive the facing from the furniture.")
        self.assertNotIn(
            "Sleep", spa,
            "the spa treatment plans a Sleep animation strip again. Normal "
            "loungers plan no strip at all.")
        for bad in ("eBodyPositionChaise", "eDirectionNorth",
                    "eHeadDirection"):
            self.assertNotIn(
                bad, spa,
                "the spa treatment supplies %s again. The normal loungers "
                "supply no body position, direction or head -- that is the "
                "whole point of copying them." % bad)

    def test_spa_loungers_are_not_forced_off_the_lie_down_path(self):
        """The relax branch must not special-case the spa handle.

        `|| VF2SpaLoungerHasHandle(info.unknown0)` is what routed spa
        loungers into the PlanToWait branch while ordinary loungers took
        PlanToLieDown. It is the reason they were the only furniture
        exhibiting this bug.
        """
        src = _strip_comments(_source())
        self.assertNotIn(
            "info.orientation == 1 || VF2SpaLoungerHasHandle(info.unknown0)",
            src,
            "the relax pose branch special-cases spa loungers again, forcing "
            "them into the PlanToWait branch that every ordinary lounger "
            "avoids. That is the ten-round regression.")
        self.assertEqual(
            src.count("if (info.orientation == 1) {"), 2,
            "expected both chaise relax sites to use the stock "
            "orientation-only condition")

    def test_every_route_into_the_lounger_uses_the_same_wiring(self):
        """Manual drop AND autonomous must share one pose implementation.

        The owner asked for this directly: "make sure both manual drops and
        autonomous behaviors if they exist use that same wiring."

        There are two handlers that pose a villager on a spa lounger:

          VF2HandleMobileInvisibleSpaLounger    manual drop, invisible item
          VF2HandleMobileSpaLoungerReceiving    visible item, and the
                                                registered AUTONOMOUS handler

        Both must delegate to VF2PlanSpaTreatment rather than posing the
        villager themselves, so a future fix cannot correct one route and
        leave the other broken.
        """
        src = _strip_comments(_source())

        for handler in ("VF2HandleMobileInvisibleSpaLounger",
                        "VF2HandleMobileSpaLoungerReceiving"):
            # The DEFINITION, not the forward declaration: match the
            # opening brace, since both share the same signature line.
            start = src.index(
                "static bool %s(CVillager &villager)%s{" % (handler, chr(10)))
            body = src[start:src.index(chr(10) + "}" + chr(10), start)]
            self.assertIn(
                "VF2PlanSpaTreatment(", body,
                "%s no longer delegates to VF2PlanSpaTreatment, so it can "
                "drift away from the other route's pose" % handler)
            for bad in ("PlanToWait", "PlanToLieDown", "SleepN"):
                self.assertNotIn(
                    bad, body,
                    "%s poses the villager itself (%s). Both routes must go "
                    "through VF2PlanSpaTreatment so there is exactly one "
                    "implementation to keep correct." % (handler, bad))

        self.assertEqual(
            src.count("VF2PlanSpaTreatment(plans, villager,"), 2,
            "expected exactly two call sites -- the manual-drop handler and "
            "the autonomous/receiving handler")

        self.assertIn(
            '"handler": "VF2HandleMobileSpaLoungerReceiving"', _source(),
            "the autonomous registration no longer points at the receiving "
            "handler, so autonomous selection would use a different path")

    def test_the_autonomous_route_needs_a_spa_lounger_in_the_house(self):
        """Owner: the autonomous route must require a spa lounger present.

        "the autonomous route should depend on either the spa lounger or the
        invisible spa lounger being present in the house."

        The candidate is gated on eObjectChaise, which EVERY ordinary
        lounger shares. Without an item-level gate the spa behaviour could
        be selected with no spa lounger placed at all;
        VF2FindFreeSpaLoungerSlot would then refuse it, but only after the
        villager had spent a decision on it -- the same silent no-op the
        Home Gym and Yoga gating exists to prevent.
        """
        src = _strip_comments(_source())
        self.assertIn("bool spaLoungerInWorld =", src,
                      "the spa autonomous eligibility flag is gone")

        # Check the GATE EXPRESSION itself, not merely that the macro name
        # appears somewhere in the file -- it appears in the slot finder too,
        # so a file-wide search passes even when the gate tests only one id.
        gs = src.index("bool spaLoungerInWorld =")
        gate = src[gs:src.index(";", gs)]
        for macro in ("__VF2_INVISIBLE_SPA_LOUNGER_ITEM_ID__",
                      "__VF2_SPA_LOUNGER_ITEM_ID__"):
            self.assertIn(
                macro, gate,
                "the spa gate expression does not test %s. BOTH the visible "
                "and the invisible lounger must satisfy it, exactly as "
                "VF2FindFreeSpaLoungerSlot tests both. Gate was: %s"
                % (macro, " ".join(gate.split())))
        self.assertEqual(
            gate.count("IsInWorld"), 2,
            "expected exactly two IsInWorld tests in the spa gate, one per "
            "lounger item; got: %s" % " ".join(gate.split()))

        self.assertIn(
            "VF2HandleMobileSpaLoungerReceiving,%s            spaLoungerInWorld"
            % chr(10), src,
            "the autonomous candidate no longer uses spaLoungerInWorld as "
            "its eligibility, so it can be offered with no spa lounger "
            "placed")

    def test_invisible_furniture_pairs_with_its_visible_twin(self):
        """Owner: apply the same wiring to the other invisible furniture.

        Every invisible item must be registered alongside its visible twin
        so either one satisfies the behaviour. Checked rather than assumed,
        because a handler that lists only one id silently ignores the other.
        """
        src = _source()
        for invisible, visible in (
            ("INVISIBLE_SPA_LOUNGER_ITEM_ID", "SPA_LOUNGER_ITEM_ID"),
            ("INVISIBLE_PATIO_TABLE_ITEM_ID", "MOBILE_PATIO_TABLE_ITEM_ID"),
            ("INVISIBLE_PICNIC_TABLE_ITEM_ID", "MOBILE_PICNIC_TABLE_ITEM_ID"),
        ):
            with self.subTest(item=invisible):
                paired = ("%s, %s" % (invisible, visible) in src
                          or "%s, %s" % (visible, invisible) in src)
                self.assertTrue(
                    paired,
                    "%s is not registered together with %s, so one of the "
                    "two items would not trigger the behaviour"
                    % (invisible, visible))

        # The invisible Lounger rides the shared chaise list.
        self.assertIn("INVISIBLE_LOUNGER_ITEM_ID,", src)
        # Yoga accepts the patcher item and the stock one.
        self.assertIn("__VF2_YOGA_EQUIPMENT_ITEM_ID__", src)
        self.assertIn("(EInventoryItem)0x220", src)

    def test_the_spa_behaviours_are_still_present(self):
        """Copying the normal pose must not delete the spa feature."""
        src = _source()
        self.assertIn("VF2PlanSpaTreatment", src)
        self.assertIn("VF2SpaLoungerHasHandle", src,
                      "the spa handle gate is still needed elsewhere, e.g. "
                      "for the walk-target nudge")
        self.assertIn("point.y -= 4;", src)
        self.assertIn("point.x -= 4;", src)
        self.assertIn('"Relaxing in the spa"', src)
        self.assertIn('"Getting a massage"', src)


if __name__ == "__main__":
    unittest.main()
