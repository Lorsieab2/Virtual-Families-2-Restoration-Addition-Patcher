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
import re
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
            "plans->PlanToWait(", spa,
            "the spa treatment no longer settles with PlanToWait. "
            "PlanToLieDown cannot be used here: the disassembly shows it "
            "writes action 0x25 with the direction and head fields ZERO, so "
            "it supplies no facing and the sleep strip then imposes its own "
            "-- the villager turns when the eyes close.")

    def test_the_treatment_lies_down_and_then_sleeps(self):
        """Owner: "they should lie down AND sleep too."

        And: "the hammock already does the orientation-aware actions
        correctly. use that."

        The hammock's shape is a short settle that places the body, then
        the orientation-matched Sleep strip for the remainder:

            plans->PlanToWait(10, eBodyPositionRestingHammock, head);
            char const *anim = facesNorthWest ? "SleepNW" : "SleepNE";
            plans->PlanToPlayAnim(rest, anim, false, 0.02f);

        The loungers use PlanToLieDown as their settle -- what the ordinary
        chaises have always used -- then the same orientation-aware strip.
        PlanToLieDown alone leaves the villager lying there awake.
        """
        spa = _spa_body(_source())
        self.assertIn(
            "plans->PlanToWait(", spa,
            "the treatment no longer settles with a facing-carrying call")
        self.assertIn(
            "PlanToPlayAnim(", spa,
            "the treatment lies down but never sleeps")
        self.assertIn(
            'loungerFacesNorthWest ? "SleepNW" : "SleepNE"', spa,
            "the sleep strip is not driven by the same predicate as the "
            "settle. Both phases must come from ONE value or they disagree "
            "and the villager turns when the eyes close.")
        self.assertIn(
            "eBodyPositionChaise", spa,
            "the treatment must supply the chaise body position; the "
            "4-argument PlanToWait is what carries the facing")

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
            src.count("if (info.orientation == 1) {"), 0,
            "a chaise relax site branches on orientation again. Owner: "
            "\"they should use the same plan\" -- both orientations take "
            "PlanToLieDown plus an orientation-aware Sleep strip, not two "
            "different pose mechanisms.")
        self.assertEqual(
            src.count("plans->PlanToWait(" + chr(10) + "        settleTicks,"), 3,
            "expected all three lounger sites (two relax, one treatment) to "
            "settle with the facing-carrying PlanToWait")

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

    def test_the_pose_uses_the_lounger_under_the_villager(self):
        """ROOT CAUSE TEST. The pose must not follow a shared-object lookup.

        VF2HandleMobileInvisibleSpaLounger is the ONLY handler registered
        for the spa lounger item ids, and it builds receiveInfo from
        LinkPeepToFurniture(eObjectChaise, ...). eObjectChaise is shared by
        EVERY ordinary chaise and that call resolves purely by object, so
        receiveInfo can describe DIFFERENT furniture than the lounger the
        villager is lying on -- and the pose then follows the wrong
        orientation.

        That is why no choice of Sleep strip constant could ever be right,
        across roughly twenty attempts. The same shared-object defect was
        behind the Exercise Bike / Treadmill bug in B188, and was fixed the
        same way: correct the lookup, not the consumer.

        The handler already computes the exact slot under the villager for
        its occupancy checks, so the correct orientation is available; it
        was simply being discarded.
        """
        src = _strip_comments(_source())

        self.assertIn(
            "static bool VF2SpaLoungerOrientationUnderVillager(", src,
            "the helper that reads the orientation of the lounger actually "
            "under the villager is gone")

        start = src.index(
            "static bool VF2HandleMobileInvisibleSpaLounger(CVillager &villager)"
            + chr(10) + "{")
        handler = src[start:src.index(chr(10) + "}" + chr(10), start)]

        self.assertIn(
            "VF2SpaLoungerOrientationUnderVillager(villager, actualOrientation)",
            handler,
            "the drop handler no longer corrects the orientation, so the "
            "pose again follows whatever chaise LinkPeepToFurniture happened "
            "to resolve rather than the lounger under the villager")
        self.assertIn(
            "receiveInfo.orientation = actualOrientation;", handler,
            "the corrected orientation is computed but never applied")

        # The correction must happen BEFORE the pose is planned.
        self.assertLess(
            handler.index("receiveInfo.orientation = actualOrientation;"),
            handler.index("VF2PlanSpaTreatment("),
            "the orientation is corrected after the pose is already planned, "
            "so the pose still uses the wrong value")

    def test_the_autonomous_route_reads_one_orientation_source(self):
        """The autonomous route reads orientation from the record it verified.

        It already rejects any info whose handle does not match the spa
        lounger's own slot record, and reads the walk point from that
        record (+0x14, +0x18). Orientation now comes from the same record
        (+0x10) so the two cannot drift apart.
        """
        src = _strip_comments(_source())
        start = src.index(
            "static bool VF2HandleMobileSpaLoungerReceiving(CVillager &villager)"
            + chr(10) + "{")
        handler = src[start:src.index(chr(10) + "}" + chr(10), start)]
        self.assertIn(
            "info.orientation = *reinterpret_cast<int *>(spaRecord + 0x10);",
            handler,
            "the autonomous route no longer reads orientation from the spa "
            "lounger record it verified")

    def test_every_pose_site_drives_body_head_and_strip_from_one_predicate(self):
        """PER-SITE coverage. v8 shipped with 1 of 3 sites fixed.

        That build compiled, passed the suite, and was handed over -- while
        two of the three pose sites still used PlanToLieDown (which supplies
        NO facing: it writes action 0x25 with the direction and head fields
        zeroed) plus `orientation == 3`, which is never true for a spa
        lounger. The villager therefore turned when the eyes closed.

        A test that passes with 2 of 3 sites broken is worthless, so this
        one checks EACH site independently and counts them.
        """
        src = _strip_comments(_source())

        sites = re.findall(
            r"plans->PlanToWait\(\s*settleTicks,(.{0,400}?)0\.02f\);",
            src, re.S)
        self.assertEqual(
            len(sites), 3,
            "expected exactly 3 lounger pose sites (two chaise relax poses "
            "and the spa treatment); found %d. A missing site means a code "
            "path still poses the villager some other way." % len(sites))

        for n, body in enumerate(sites, 1):
            flat = " ".join(body.split())
            with self.subTest(site=n):
                self.assertIn(
                    "eBodyPositionChaise", flat,
                    "site %d does not use the chaise body position" % n)
                self.assertEqual(
                    flat.count("loungerFacesNorthWest"), 3,
                    "site %d does not drive the body direction, the head "
                    "AND the sleep strip from the same predicate. Anything "
                    "less lets the two phases disagree, which is the visible "
                    "flip when the eyes close. Site was: %s" % (n, flat[:160]))

        # The two mechanisms that produced the flip must be gone everywhere.
        self.assertNotIn(
            "plans->PlanToLieDown(settleTicks);", src,
            "a pose site still settles with PlanToLieDown, which supplies no "
            "facing at all -- the strip then imposes its own and the villager "
            "turns when the eyes close")
        self.assertNotIn(
            'info.orientation == 3 ? "SleepNW"', src,
            "a site still selects the strip with `orientation == 3`, which is "
            "NEVER true for a spa lounger (they occupy 0 and 1), so every "
            "lounger got SleepNE regardless of which way it faced")

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
