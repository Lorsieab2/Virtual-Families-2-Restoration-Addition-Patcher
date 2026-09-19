"""Spa loungers pose exactly as the stock chaise does, via one helper.

THE MODEL, established from evidence after ~20 failed rounds.

The stock game's chaise dispatch, decoded from the shipped binary at
.text+0x37444 (B189; the same result was decoded from B190 earlier):

    orientation == 1 -> body 0x17 (eBodyPositionChaise)         + "SleepNE"
    otherwise        -> body 9    (eBodyPositionRestingHammock) + "SleepNW"

THE BODY POSITION IS ORIENTATION-DEPENDENT. Every earlier attempt hardcoded
body 0x17 for BOTH orientations and then varied the direction, head or strip.
Body 0x17 is the orientation-1 sprite; on an orientation-0 lounger it lies
across the furniture whatever direction is supplied. A direction argument
cannot fix a wrong body sprite, which is why "one lounger right, one wrong"
survived every permutation of the other three arguments.

Ordinary chaises never had the bug (orientation 0 uses PlanToLieDown, whose
native path picks body 9). The hammock never had it (body 9 at both of its
orientations, head + strip from one predicate, 3-argument PlanToWait).

These tests pin:
  * ONE body table, VF2PlanSpaLoungerPose, with the hammock's head pairing
    and call shape, held for the full duration and nothing else;
  * the spa treatment's VF2PlanSpaLoungerRest, which settles THROUGH that
    table and only then sleeps -- the relax sites never sleep, because their
    rolls are awake activities (reading, studying, sitting);
  * EVERY route that poses a villager on a spa lounger goes through the one
    table -- both chaise relax sites and the spa treatment;
  * each route uses ONE placement whole: the drop route the record the
    engine linked, the autonomous route the record it verified;
  * the ordinary-chaise branches are byte-identical to what shipped;
  * each historical mistake, as a negative case that must FAIL.
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
    """Judge CODE, not prose: comments deliberately quote the old wrong forms."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        out.append(line.split("//")[0] if "//" in line else line)
    return "\n".join(out)


def _function(src, signature_start):
    """Body of a function DEFINITION, never its forward declaration.

    Several handlers are forward-declared with the identical signature
    line, so the first textual match may be the declaration. A definition
    is the occurrence whose parameter list's closing paren is followed
    directly by a newline and an opening brace.
    """
    i = -1
    while True:
        i = src.index(signature_start, i + 1)
        close = src.index(")", i)
        if src.startswith("\n{", close + 1):
            return src[i:src.index("\n}\n", close)]


def _pose(src):
    """The body table: PlanToWait for the whole duration, nothing else."""
    return _function(src, "static void VF2PlanSpaLoungerPose(")


def _rest(src):
    """The treatment's settle-then-sleep, which delegates the pose to _pose."""
    return _function(src, "static void VF2PlanSpaLoungerRest(")


def _relax_sites(src):
    """The two chaise relax handlers that can land on a spa lounger."""
    return [
        _function(src, "static bool VF2HandleMobileChaise(CVillager &villager)"),
        _function(src, "static void VF2PlanLinkedChaiseAction("),
    ]


def _spa_treatment(src):
    return _function(src, "static void VF2PlanSpaTreatment(")


class TheOneHelper(unittest.TestCase):
    def test_the_engine_exports_the_three_argument_wait(self):
        """Ground truth for the call shape, so it is not re-derived later."""
        if not DISASM.is_file():
            self.skipTest("disassembly not present in this checkout")
        text = DISASM.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "?PlanToWait@CVillagerPlans@@QAEXHW4EBodyPosition@@W4EHeadDirection@@@Z",
            text, "the 3-argument PlanToWait is missing from the decoded binary")

    def test_body_position_follows_the_stock_table(self):
        """orientation 1 -> 0x17, otherwise 9. THIS is the fix."""
        h = _strip_comments(_pose(_source()))
        self.assertIn("orientation == 1", h,
                      "the predicate is no longer orientation == 1")
        self.assertRegex(
            h, r"liesNorthEast\s*\?\s*eBodyPositionChaise\s*:\s*eBodyPositionRestingHammock",
            "the BODY POSITION is not selected by orientation. Hardcoding "
            "eBodyPositionChaise for both orientations is the ~20-round "
            "defect: 0x17 is the orientation-1 sprite and lies ACROSS an "
            "orientation-0 lounger whatever direction is supplied.")

    def test_head_and_strip_pair_like_the_hammock(self):
        """NE body -> NE head -> SleepNE. NW body -> NW head -> SleepNW."""
        src = _source()
        h = _strip_comments(_pose(src))
        self.assertRegex(
            h, r"liesNorthEast\s*\?\s*eHeadDirectionNE\s*:\s*eHeadDirectionNW",
            "the head does not pair with the body: the hammock pairs an NE "
            "head with SleepNE and an NW head with SleepNW")
        h = _strip_comments(_rest(src))
        self.assertRegex(
            h, r'liesNorthEast\s*\?\s*"SleepNE"\s*:\s*"SleepNW"',
            "the strip is INVERTED. Stock and the owner's B190 playtest both "
            "say orientation 1 -> SleepNE, otherwise SleepNW. This inversion "
            "shipped in the last several builds.")

    def test_call_shape_is_the_hammocks(self):
        """3-argument PlanToWait: no EDirection, no PlanToLieDown."""
        h = _strip_comments(_pose(_source()))
        call = re.search(r"PlanToWait\(([^;]*)\);", h, re.S)
        self.assertIsNotNone(call, "the helper does not settle with PlanToWait")
        argc = call.group(1).count(",") + 1
        self.assertEqual(
            argc, 3,
            "the helper passes %d arguments to PlanToWait; the hammock uses "
            "3 (duration, body, head). The 4-argument form failed on both "
            "arms in play and neither working reference uses it." % argc)
        self.assertNotIn("eDirection", h,
                         "the helper passes an EDirection again (4-arg detour)")
        self.assertNotIn("PlanToLieDown", h,
                         "the helper uses PlanToLieDown, which supplies no "
                         "facing: the strip then imposes its own and the "
                         "villager turns when the eyes close")
        self.assertNotIn("orientation == 3", h,
                         "orientation == 3 is never true for a spa lounger")

    def test_both_phases_come_from_one_predicate(self):
        src = _source()
        pose = _strip_comments(_pose(src))
        self.assertEqual(
            pose.count("liesNorthEast ?"), 2,
            "body and head must BOTH be selected by the single predicate")
        rest = _strip_comments(_rest(src))
        self.assertEqual(
            rest.count("liesNorthEast ?"), 1,
            "the strip must be selected by the same predicate")
        self.assertIn(
            "VF2PlanSpaLoungerPose(plans, orientation, settle);", rest,
            "the treatment no longer settles through the ONE body table; a "
            "second PlanToWait here is a second place for the body to be wrong")
        self.assertNotIn("PlanToWait", rest,
                         "the treatment poses itself instead of delegating")
        self.assertNotIn("PlanToPlayAnim", pose,
                         "the pose helper sleeps: every relax roll on a spa "
                         "lounger would close its eyes, including reading")


class EveryRouteUsesIt(unittest.TestCase):
    def test_both_relax_sites_route_spa_loungers_to_the_helper(self):
        src = _strip_comments(_source())
        for n, body in enumerate(_relax_sites(src), 1):
            with self.subTest(site=n):
                self.assertIn(
                    "if (VF2SpaLoungerHasHandle(info.unknown0)) {", body,
                    "relax site %d no longer tests for a spa lounger first" % n)
                self.assertIn(
                    "VF2PlanSpaLoungerPose(plans, info.orientation, duration);",
                    body, "relax site %d does not use the one body table" % n)
                self.assertNotIn(
                    "VF2PlanSpaLoungerRest(", body,
                    "relax site %d sleeps. Its rolls are awake activities -- "
                    "reading, studying, sitting -- which the ordinary chaise "
                    "holds for the full duration; the sleep strip belongs to "
                    "the spa treatment only (review, round 2)" % n)
                self.assertLess(
                    body.index("VF2SpaLoungerHasHandle(info.unknown0)) {"),
                    body.index("info.orientation == 1"),
                    "relax site %d tests orientation before the spa handle, so "
                    "a spa lounger at orientation 1 takes the ordinary branch" % n)

    def test_the_spa_treatment_uses_the_helper_and_nothing_else(self):
        spa = _strip_comments(_spa_treatment(_source()))
        self.assertIn("VF2PlanSpaLoungerRest(plans, info.orientation, total);", spa)
        for bad in ("PlanToWait", "PlanToLieDown", "SleepN", "eBodyPosition",
                    "eHeadDirection", "eDirection"):
            self.assertNotIn(
                bad, spa,
                "the spa treatment poses the villager itself (%s) instead of "
                "delegating; one implementation, one place to be wrong" % bad)

    def test_exactly_three_call_sites(self):
        src = _strip_comments(_source())
        self.assertEqual(
            src.count("VF2PlanSpaLoungerPose(plans, info.orientation, duration);"), 2,
            "expected the pose at exactly the two relax sites")
        self.assertEqual(
            src.count("VF2PlanSpaLoungerRest(plans, info.orientation, total);"), 1,
            "expected the rest at exactly the spa treatment")
        self.assertEqual(
            src.count("VF2PlanSpaLoungerPose("), 4,
            "declaration, two relax sites and the rest's own delegation; "
            "anything else is a route that bypasses the one body table")


class OrdinaryChaisesAreUntouched(unittest.TestCase):
    def test_the_shipped_branches_are_intact_at_both_relax_sites(self):
        """The owner confirmed ordinary loungers working. Keep them so."""
        src = _strip_comments(_source())
        for n, body in enumerate(_relax_sites(src), 1):
            with self.subTest(site=n):
                self.assertIn("} else if (info.orientation == 1) {", body)
                self.assertIn("plans->PlanToLieDown(duration);", body,
                              "ordinary chaise orientation-0 path is gone")
                self.assertRegex(
                    body,
                    r"PlanToWait\(\s*duration,\s*eBodyPositionChaise,\s*"
                    r"VF2SpaLoungerFacesNorthWest\(info\.orientation, info\.unknown0\)",
                    "the ordinary chaise orientation-1 branch is not the "
                    "shipped 4-argument form")

    def test_the_old_forcing_condition_is_gone_everywhere(self):
        src = _strip_comments(_source())
        self.assertNotIn(
            "info.orientation == 1 || VF2SpaLoungerHasHandle(info.unknown0)",
            src,
            "the condition that forced spa loungers into the orientation-1 "
            "body at every orientation is back")


class EachRouteUsesOnePlacement(unittest.TestCase):
    def test_the_drop_route_uses_the_linked_record_whole(self):
        """Nothing is patched between the link and the plan.

        LinkPeepToFurniture is the reservation and cannot be re-anchored:
        it takes no point, and UnlinkPeepFromFurniture does not exist
        (AGENTS.md). Two revisions tried to correct receiveInfo from the slot
        under the villager -- one field, then a read-only FindFurniture
        substitute -- and review rejected both as leaving the reservation on
        one chaise and the villager on another. The hypothesis behind them
        was disproved in round 21 (the body table was the defect).
        """
        src = _strip_comments(_source())
        h = _function(src, "static bool VF2HandleMobileInvisibleSpaLounger(CVillager &villager)")
        after_link = h[h.index("LinkPeepToFurniture("):]
        self.assertNotRegex(after_link, r"receiveInfo(\.\w+)?\s*=[^=]",
                            "a field of the linked record is patched after "
                            "the link: that is the hybrid, in some form")
        for bad in ("FindFurniture(", "UnderVillager(", "spaRecord",
                    "actualOrientation", "ownInfo"):
            self.assertNotIn(bad, after_link,
                             "the drop route second-guesses the link (%s)" % bad)
        self.assertNotIn("VF2SpaLoungerRecordUnderVillager", src)
        self.assertNotIn("VF2SpaLoungerOrientationUnderVillager", src)

    def test_the_autonomous_route_reads_the_verified_record(self):
        src = _strip_comments(_source())
        h = _function(src, "static bool VF2HandleMobileSpaLoungerReceiving(CVillager &villager)")
        self.assertIn(
            "info.orientation = *reinterpret_cast<int *>(spaRecord + 0x10);", h)
        self.assertLess(h.index("!= info.unknown0) return false;"),
                        h.index("info.orientation ="),
                        "the record is trusted before its handle is verified")

    def test_the_nudge_is_per_orientation(self):
        """Three owner requests, each from a screenshot of a confirmed pose:
        orientation 1 (head upper-right) 4px left; orientation 0 (head
        upper-left) 4px left in round 8, then 2px right, net 2px left."""
        src = _strip_comments(_source())
        f = _function(src, "static ldwPoint VF2SpaTreatmentPoint(")
        self.assertIn("point.y -= 4;", f)
        self.assertIn("if (VF2SpaLoungerHasHandle(handle)) {", f,
                      "the horizontal nudge no longer covers both spa "
                      "orientations")
        self.assertIn(
            "point.x -= VF2SpaLoungerFacesNorthWest(orientation, handle) ? 4 : 2;",
            f,
            "orientation 1 must move 4px left and orientation 0 2px left; "
            "any other split contradicts one of the owner's screenshots")
        self.assertNotIn("point.x -= 4;", f,
                         "the one-orientation nudge is back")


class NothingElseWasLost(unittest.TestCase):
    def test_spa_behaviours_and_gates_are_present(self):
        src = _source()
        for needle in ("VF2PlanSpaTreatment", "VF2SpaLoungerHasHandle",
                       "point.y -= 4;",
                       "point.x -= VF2SpaLoungerFacesNorthWest(orientation, handle) ? 4 : 2;",
                       '"Relaxing in the spa"', '"Getting a massage"',
                       "bool spaLoungerInWorld ="):
            self.assertIn(needle, src, needle)

    def test_invisible_furniture_pairs_with_its_visible_twin(self):
        src = _source()
        for inv, vis in (("INVISIBLE_SPA_LOUNGER_ITEM_ID", "SPA_LOUNGER_ITEM_ID"),
                         ("INVISIBLE_PATIO_TABLE_ITEM_ID", "MOBILE_PATIO_TABLE_ITEM_ID"),
                         ("INVISIBLE_PICNIC_TABLE_ITEM_ID", "MOBILE_PICNIC_TABLE_ITEM_ID")):
            with self.subTest(item=inv):
                self.assertTrue("%s, %s" % (inv, vis) in src or "%s, %s" % (vis, inv) in src)


if __name__ == "__main__":
    unittest.main()
