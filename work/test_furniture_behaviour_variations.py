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
        r"kVF2GymDonorBehaviors\[\]\)\(CVillager &\) = \{(.*?)\};",
        SOURCE, re.S)
    return m.group(1) if m else ""


def handler_body(name):
    m = re.search(r'void __cdecl %s\(CVillager &villager\)\s*\{(.*?)\n\}' % name,
                  SOURCE, re.S)
    return m.group(1) if m else ""


class GymAndYogaOfferTheirWholeSet(unittest.TestCase):
    def test_the_donor_table_exists_and_is_not_a_single_entry(self):
        table = donor_table()
        self.assertTrue(table, "kVF2GymDonorBehaviors is gone")
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
        self.assertIn("kVF2GymDonorBehaviors", body)

    def test_the_yoga_handler_uses_the_varied_runner(self):
        body = handler_body("VF2YogaEquipmentWorkout")
        self.assertTrue(body, "VF2YogaEquipmentWorkout is gone")
        self.assertIn("VF2RunOwnFurnitureActionVaried", body)
        self.assertIn("kVF2GymDonorBehaviors", body)

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
        # VF2RunOwnFurnitureAction owns that fallback, so it must still be
        # reached rather than replaced by the varied runner.
        m = re.search(r"static void VF2RunOwnFurnitureAction\(\s*\n(.*?)\n\}",
                      SOURCE, re.S)
        self.assertIsNotNone(m, "VF2RunOwnFurnitureAction is gone")
        body = m.group(1)
        self.assertIn("if (!hasVenue)", body,
                      "the no-venue branch is gone, so an absent item would "
                      "suppress the behaviour instead of falling back")
        self.assertIn("VF2RunNativeBehaviorAndChangedLabel", body)
        self.assertIn("VF2RunOwnFurnitureAction(", donor_runner_call(),
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


if __name__ == "__main__":
    unittest.main()
