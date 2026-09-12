"""The gym and yoga venues must offer their whole behaviour set.

THE DEFECT THIS PINS: VF2HomeGymWorkout hardcoded CBehavior::WorkingOut and
VF2YogaEquipmentWorkout hardcoded CBehavior::QuickWorkout, so each item only
ever produced one action out of the set it was meant to have. The owner
reported it as "they only show one action out of their full possibilities".

Two properties matter and they pull in opposite directions, so both are
asserted:

  the item-gated handlers choose among SEVERAL donors, and
  the general donor behaviours are NOT gated on any item -- they stay
  base-game and autonomous, and a placed item changes WHERE a behaviour
  happens rather than WHETHER it is available.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
SOURCE = GENERATOR.read_text(encoding="utf-8", errors="replace")

# Only the donors whose PlanToGo callsites are retargeted to the venue may be
# offered. patch_added_furniture_venue_callsites rewrites the relocation in
# these two and no others.
EXPECTED_DONORS = (
    "CBehavior::WorkingOut",
    "CBehavior::QuickWorkout",
)

# Verified present in Behavior.obj's symbol table, but NOT venue-aware: they
# keep their own stock-location routes, and PlanToGo appends rather than
# replaces, so a route they append lands after the venue and the villager
# walks away. Offering them would look correct in every static check and do
# the wrong thing in play.
UNRETARGETED_DONORS = (
    "CBehavior::DoingKungFu",
    "CBehavior::DoingTaiChi",
    "CBehavior::Aerobics",
)


def retargeted_symbols():
    """The behaviours whose PlanToGo relocation is actually rewritten."""
    # Slice to the next top-level def rather than to a "for" line: the
    # earlier pattern matched nothing and the guard below turned that into a
    # failure instead of a vacuous pass.
    i = SOURCE.find("def patch_added_furniture_venue_callsites")
    if i < 0:
        return set()
    j = SOURCE.find("\ndef ", i + 1)
    block = SOURCE[i:j if j > 0 else len(SOURCE)]
    return set(re.findall(r"\?([A-Za-z0-9_]+)@CBehavior@@", block))


def donor_table():
    m = re.search(
        r"VF2DonorBehavior const donors\[\] = \{(.*?)\};",
        SOURCE, re.S)
    return m.group(1) if m else ""


def handler_body(name):
    m = re.search(r'void __cdecl %s\(CVillager &villager\)\s*\{(.*?)\n\}' % name,
                  SOURCE, re.S)
    return m.group(1) if m else ""


class GymAndYogaOfferTheirWholeSet(unittest.TestCase):
    def test_the_donor_table_exists_and_is_not_a_single_entry(self):
        table = donor_table()
        self.assertTrue(
            table,
            "the gym donor table is gone; it lives in VF2GymDonorBehaviors(), "
            "which CBehavior befriends -- a file-scope initialiser cannot "
            "reach the private WorkingOut/QuickWorkout members",
        )
        entries = [ln.strip().rstrip(",") for ln in table.splitlines()
                   if ln.strip().startswith("CBehavior::")]
        self.assertGreater(
            len(entries), 1,
            "the venue offers a single behaviour again, which is the defect: "
            "one action out of the full set")
        self.assertEqual(len(entries), len(set(entries)),
                         "a donor is listed twice, so its odds are doubled")

    def test_every_named_behaviour_is_offered(self):
        table = donor_table()
        for donor in EXPECTED_DONORS:
            with self.subTest(donor=donor):
                self.assertIn(donor, table)

    def test_every_offered_donor_is_actually_retargeted_to_the_venue(self):
        # THE FINDING THIS PINS: the table originally offered five donors, but
        # patch_added_furniture_venue_callsites only rewrites the PlanToGo
        # relocation for WorkingOut and QuickWorkout. The other three kept
        # their own stock-location routes, so three of five selections walked
        # away from the gym -- with the code present and every static check
        # passing.
        retargeted = retargeted_symbols()
        self.assertTrue(retargeted,
                        "could not read the retargeted symbol list; this test "
                        "would otherwise pass vacuously")
        table = donor_table()
        offered = set(re.findall(r"CBehavior::([A-Za-z0-9_]+)", table))
        self.assertTrue(offered, "no donors are offered at all")
        for name in sorted(offered):
            with self.subTest(donor=name):
                self.assertIn(
                    name, retargeted,
                    "%s is offered as a venue donor but its PlanToGo is not "
                    "retargeted, so the action would run somewhere else" % name)

    def test_the_unretargeted_donors_are_not_offered(self):
        table = donor_table()
        for donor in UNRETARGETED_DONORS:
            with self.subTest(donor=donor):
                self.assertNotIn(donor, table)

    def test_no_invented_behaviour_symbols(self):
        # DoingAerobics and DoingXExercises do not exist in Behavior.obj. The
        # first is spelled Aerobics; the second is not a behaviour at all --
        # "Doing X exercises" is WorkingOut wearing the "workout" label group.
        for invented in ("CBehavior::DoingAerobics", "CBehavior::DoingXExercises"):
            with self.subTest(symbol=invented):
                self.assertNotIn(invented, SOURCE)

    def test_the_x_exercise_labels_exist_for_working_out(self):
        # The owner's "Doing X exercises" is this label group, not a behaviour.
        for label in ("Doing leg exercises", "Doing abdominal exercises",
                      "Doing crunches"):
            with self.subTest(label=label):
                self.assertIn(label, SOURCE)

    def test_the_gym_handler_uses_the_varied_runner(self):
        body = handler_body("VF2HomeGymWorkout")
        self.assertTrue(body, "VF2HomeGymWorkout is gone")
        self.assertIn("VF2RunOwnFurnitureActionVaried", body)
        self.assertIn("VF2GymDonorBehaviors", body)

    def test_the_yoga_handler_uses_the_varied_runner(self):
        body = handler_body("VF2YogaEquipmentWorkout")
        self.assertTrue(body, "VF2YogaEquipmentWorkout is gone")
        self.assertIn("VF2RunOwnFurnitureActionVaried", body)
        self.assertIn("VF2GymDonorBehaviors", body)

    def test_the_varied_runner_bounds_the_engine_random(self):
        m = re.search(r"static void VF2RunOwnFurnitureActionVaried\((.*?)\n\}",
                      SOURCE, re.S)
        self.assertIsNotNone(m, "VF2RunOwnFurnitureActionVaried is gone")
        body = m.group(1)
        self.assertIn("GetRandom", body, "no random selection happens")
        self.assertIn("index >= donorCount", body,
                      "GetRandom's result is not bounded, so a range this code "
                      "does not own could index past the table")

    def test_a_missing_item_still_falls_back_to_the_plain_donor(self):
        # The availability rule: a placed item changes WHERE, never WHETHER.
        # The fallback now lives in VF2RunOwnFurnitureActionEx, which the plain
        # VF2RunOwnFurnitureAction forwards to; match Ex so this checks the
        # implementation rather than the one-line wrapper.
        m = re.search(r"static void VF2RunOwnFurnitureActionEx\(\s*\n(.*?)\n\}",
                      SOURCE, re.S)
        self.assertIsNotNone(m, "VF2RunOwnFurnitureActionEx is gone")
        body = m.group(1)
        self.assertIn("if (!hasVenue)", body,
                      "the no-venue branch is gone, so an absent item would "
                      "suppress the behaviour instead of falling back")
        self.assertIn("VF2RunNativeBehaviorAndChangedLabel", body)
        self.assertIn("VF2RunOwnFurnitureActionEx(", donor_runner_call(),
                      "the varied runner no longer delegates to the runner "
                      "that owns the fallback")


def donor_runner_call():
    m = re.search(r"static void VF2RunOwnFurnitureActionVaried\((.*?)\n\}",
                  SOURCE, re.S)
    return m.group(1) if m else ""


class GeneralBehavioursStayUngated(unittest.TestCase):
    def test_the_donors_are_not_registered_as_added_furniture_behaviours(self):
        # ADDED_FURNITURE_BEHAVIORS binds ids to the item-gated handlers. The
        # general behaviours must not appear there, or they would stop being
        # base-game and autonomous.
        # Match to the CLOSING paren of the tuple, not the first ")" -- a
        # non-greedy (.*?)\) stops at the end of the first entry and inspects
        # one line, which made an earlier version of this test pass while a
        # general behaviour WAS registered. Caught by reverting.
        m = re.search(
            r"ADDED_FURNITURE_BEHAVIORS = \(\s*\n(.*?)\n\)\s*\n",
            SOURCE, re.S)
        self.assertIsNotNone(m, "ADDED_FURNITURE_BEHAVIORS is gone")
        block = m.group(1)
        self.assertGreaterEqual(
            block.count("(0x"), 3,
            "only %d entries matched; the block regex is truncating"
            % block.count("(0x"))
        for donor in EXPECTED_DONORS:
            bare = donor.split("::", 1)[1]
            with self.subTest(donor=bare):
                self.assertNotIn(
                    '"%s"' % bare, block,
                    "%s was registered as an added-furniture behaviour, which "
                    "would gate a base-game behaviour on owning an item" % bare)


class TheGymLabelVariesPerVisit(unittest.TestCase):
    """The ten workout variations must not collapse to one per villager.

    Reported from live play: adults always "Doing crunches", kids always
    "Doing endurance exercises". VF2ApplyVenueLabel rolls once and every later
    visit takes its remembered-or-cached branch, so a villager keeps the first
    label they ever rolled for the life of the save.

    These assertions are written so that reverting the fix FAILS them. An
    earlier version of this suite passed happily with the gym wired back to
    the sticky applier, which is what let the defect ship.
    """

    def varied_dispatcher(self):
        m = re.search(
            r"static void VF2RunOwnFurnitureActionVaried\(\s*\n(.*?)\n\}",
            SOURCE, re.S)
        self.assertIsNotNone(m, "VF2RunOwnFurnitureActionVaried is gone")
        return m.group(1)

    def test_the_gym_dispatcher_asks_for_a_varying_label(self):
        body = self.varied_dispatcher()
        call = re.search(r"VF2RunOwnFurnitureActionEx\((.*?)\);", body, re.S)
        self.assertIsNotNone(
            call,
            "the gym dispatcher no longer routes through "
            "VF2RunOwnFurnitureActionEx, so it cannot request a varying label")
        args = call.group(1)
        self.assertRegex(
            args, r"\btrue\b",
            "the gym dispatcher passes varyLabelEachVisit=false, so every "
            "villager is stuck with the first workout label they roll -- the "
            "exact defect reported in play")

    def test_the_varying_applier_does_not_consult_the_cache(self):
        m = re.search(
            r"static void VF2ApplyVenueLabelVarying\(\s*\n(.*?)\n\}",
            SOURCE, re.S)
        self.assertIsNotNone(m, "VF2ApplyVenueLabelVarying is gone")
        body = m.group(1)
        self.assertNotIn(
            "VF2GetVillagerCachedBehaviorLabel", body,
            "the varying applier reads the per-villager cache, which is what "
            "pins one label forever")
        self.assertIn(
            "ldwGameState::GetRandom", body,
            "the varying applier must actually re-roll")

    def test_the_sticky_applier_is_left_alone_for_other_furniture(self):
        # The stable caption is deliberate elsewhere; only the gym opts out.
        m = re.search(
            r"static void VF2ApplyVenueLabel\(\s*\n(.*?)\n\}", SOURCE, re.S)
        self.assertIsNotNone(m, "VF2ApplyVenueLabel is gone")
        self.assertIn(
            "VF2GetVillagerCachedBehaviorLabel", m.group(1),
            "the ordinary venue applier lost its cache read, which would "
            "change captions for furniture that is working correctly")

    def test_the_remembered_caption_is_gated_on_the_behaviour_serial(self):
        # THE FIRST VERSION OF THIS FIX WAS A NO-OP AND IS PINNED HERE.
        #
        # It kept the caption whenever rememberedStringId was non-zero. But
        # the caller resolves that through VF2CurrentLabelInGroup, which
        # already returns 0 unless VF2BehaviorLabelStillFromThisSession says
        # the slot is current -- so the branch fired on exactly the condition
        # that made the ORDINARY applier keep the caption, and the gym went on
        # showing one label per villager. The two appliers differed in source
        # shape and not in behaviour.
        #
        # The serial is what separates a praise restarting the same activity
        # from a genuinely new visit, so the accept branch must consult it.
        m = re.search(
            r"static void VF2ApplyVenueLabelVarying\(\s*\n(.*?)\n\}",
            SOURCE, re.S)
        self.assertIsNotNone(m, "VF2ApplyVenueLabelVarying is gone")
        body = "\n".join(
            line for line in m.group(1).splitlines()
            if not line.lstrip().startswith("//"))
        self.assertNotRegex(
            body, r"if \(rememberedStringId\)\s*\{",
            "the remembered caption is accepted unconditionally again, which "
            "is the no-op version of this fix: it keeps the label on exactly "
            "the visits the plain applier would have kept it")
        self.assertIn(
            "VF2LabelSlotIsPraiseRestart", body,
            "nothing distinguishes a praise restart from a new visit, so the "
            "caption either sticks forever or flips mid-activity")

    def test_an_accepted_praise_advances_the_slot(self):
        # VF2BehaviorLabelSlotIsCurrentFor writes the serial back when it
        # accepts a praise, and the comment there records why: leaving the
        # slot at N makes the SECOND praise arrive at N+2 and be rejected as a
        # new session, which re-rolls the caption mid-activity.
        #
        # This predicate deliberately does NOT mutate. It is safe only because
        # the accept branch calls VF2RememberBehaviorLabel, which refreshes
        # behaviorSerial from the villager -- so consecutive praises stay at
        # N+1. If that call is ever dropped, two praises in a row would
        # re-roll, so the pairing is asserted rather than left to be noticed.
        m = re.search(
            r"static void VF2ApplyVenueLabelVarying\(\s*\n(.*?)\n\}",
            SOURCE, re.S)
        self.assertIsNotNone(m, "VF2ApplyVenueLabelVarying is gone")
        body = m.group(1)
        accept = body.index("VF2LabelSlotIsPraiseRestart")
        tail = body[accept:]
        remember = tail.find("VF2RememberBehaviorLabel")
        self.assertNotEqual(
            remember, -1,
            "the praise branch returns without VF2RememberBehaviorLabel, so "
            "the slot keeps its old serial and a second consecutive praise "
            "arrives at N+2 and re-rolls the caption")
        self.assertLess(
            remember, tail.index("return;"),
            "the slot must be refreshed before the branch returns")


if __name__ == "__main__":
    unittest.main()
