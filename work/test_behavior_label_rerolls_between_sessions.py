"""A finished behaviour must not pin its label onto the next one.

The reported symptom was that the Home Gym "only shows one action out of their
full possibilities": a villager whose first visit rolled "Doing crunches" showed
"Doing crunches" for the rest of the game, and the other nine labels never
appeared. Ten labels were built and shipping; only the selection was stuck.

The cause was not the label cache. The cache is keyed on the villager's
behaviour id and serial and expires correctly. The stuck value came from the
PERSISTENT label text at villager+0x1BBA8, which survives the end of a
behaviour. ``VF2CurrentLabelInGroup`` matched that leftover text and reported
"this villager is already doing X", so every applier took its remembered-label
early return and never rolled again.

These tests pin the structural rule that makes the defect impossible: the
persistent label is only ever read behind a cache gate. They are source
contract tests because the emitted C cannot be executed here -- the same
technique the widening-scope and installer-resolution suites use.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
SOURCE = GENERATOR.read_text(encoding="utf-8")

PERSISTENT_LABEL_OFFSET = "0x1BBA8"


# Any return type, including multi-token ones. Enumerating the shapes was the
# bug: `unsigned int`, `unsigned char *`, `VF2DonorBehavior const *` and
# `__fastcall` all failed to match, so 32 real definitions read as absent.
# Anchor on the NAME and accept whatever precedes it on that line.
_DEFINITION = (
    r'^(?:extern "C" )?[A-Za-z_][\w \*&:]*?\b%s\([^;{]*\)\s*\n?\{(.*?)^\}'
)


def find_function_body(name):
    """The body of an emitted C definition, or None if the file has none.

    None means THERE IS NO DEFINITION -- a forward declaration such as
    `extern "C" void __cdecl VF2RandomBigBurgerLabel(CVillager &);` with the
    real one elsewhere, or a name that only appears in a comment. It must never
    mean "there is a definition and this helper could not parse it": callers
    treat None as nothing-to-check, so an unparseable definition would be
    silently exempted from every rule in this file. has_definition() exists so
    the sweep can tell those two cases apart.
    """
    match = re.search(_DEFINITION % re.escape(name), SOURCE, re.S | re.M)
    return match.group(1) if match else None


def has_definition(name):
    """Is there a definition line for this name at all, however it is spelled?

    Deliberately cruder than _DEFINITION: it asks whether some line opens a
    body for this name, without trying to parse the return type. When this is
    true and find_function_body is None, the helper is at fault, not the code.
    """
    return re.search(
        r'^[A-Za-z_][^\n;]*\b%s\([^;]*$' % re.escape(name),
        SOURCE,
        re.M,
    ) is not None


def function_body(name):
    """The body of an emitted C function, by name.

    Must not match a FORWARD DECLARATION. `extern "C" void __cdecl
    VF2RandomBigBurgerLabel(CVillager &);` precedes the real definition, and a
    pattern that only requires a later opening brace will start there and run
    forward into the next function's body -- returning somebody else's code
    while looking like a successful lookup. A definition's parameter list is
    followed by an opening brace with no semicolon in between, which is what
    distinguishes the two.
    """
    match = re.search(_DEFINITION % re.escape(name), SOURCE, re.S | re.M)
    assert match, "emitted C definition %s not found" % name
    body = match.group(1)
    assert len(body.strip()) > 20, (
        "function_body(%s) returned a %d-character body; it probably matched "
        "the wrong thing" % (name, len(body.strip()))
    )
    return body


class ThePersistentLabelIsOnlyReadBehindTheCacheGate(unittest.TestCase):
    def test_the_scan_and_the_gate_are_separate_functions(self):
        # The text scan says nothing about WHEN the label was set, so it must
        # not be the thing callers reach for by default.
        self.assertIn("static int VF2ScanLabelGroup(", SOURCE)
        self.assertIn("static bool VF2BehaviorLabelStillFromThisSession(", SOURCE)

    def test_the_gate_anchors_on_the_villager_it_was_handed(self):
        """Not on gVF2BehaviorLabelBeforeVillager.

        The first version of this gate called VF2GetCachedBehaviorLabel, which
        goes through VF2BehaviorLabelCacheStillActive and therefore requires
        gVF2BehaviorLabelBeforeVillager == slot->villager. That global names the
        last villager to enter a WRAPPED NATIVE behaviour and is set in exactly
        two places, so a resolver running outside that window sees somebody
        else's villager and the lookup is rejected even when the behaviour id
        and serial match. The caption then re-rolls mid-action --
        VF2ApplySitDownLabelVariants never primes the guard at all.
        """
        body = function_body("VF2BehaviorLabelStillFromThisSession")
        self.assertIn("VF2BehaviorLabelSlotIsCurrentFor", body)
        self.assertNotIn(
            "gVF2BehaviorLabelBeforeVillager",
            function_body("VF2BehaviorLabelSlotIsCurrentFor"),
            "the session predicate depends on the pre-native global again",
        )

    def test_the_predicate_still_compares_identity_and_serial(self):
        # It must not become a weaker test than the one it replaced: the whole
        # point is that a NEW behaviour instance is rejected.
        body = function_body("VF2BehaviorLabelSlotIsCurrentFor")
        self.assertIn("slot->villager != &villager", body)
        self.assertIn("behaviorId != slot->behaviorId", body)
        self.assertIn("behaviorSerial == slot->behaviorSerial", body)

    def test_the_native_restore_path_keeps_the_global_guard(self):
        # VF2BehaviorLabelCacheStillActive is load-bearing for the native-label
        # restore, where the pre-native window IS the right question. The fix
        # is additive and must not have weakened it.
        self.assertIn(
            "if (!slot || gVF2BehaviorLabelBeforeVillager != slot->villager) {",
            function_body("VF2BehaviorLabelCacheStillActive"),
        )

    def test_only_the_scan_reads_the_persistent_label_field(self):
        """+0x1BBA8 must not be read by any new ad-hoc matcher.

        This is the test that fails if the fix is reverted: restoring the old
        VF2CurrentLabelInGroup puts a read of the persistent label back into a
        function that has no cache gate.
        """
        # The defect is narrower than "reads the field": it is "matches the
        # field against a MOD LABEL GROUP and concludes the villager must still
        # be doing that". Copying the field, writing it, comparing it to a
        # caller-supplied snapshot, or matching it against fixed NATIVE label
        # ids are all legitimate and unrelated -- VF2CopyRawPraiseLabel,
        # VF2SetActionLabel, VF2BehaviorLabelChangedSince,
        # VF2IsRestingBodyNativeLabel and VF2VillagerStillPreparing all do one
        # of those. Testing for the precise shape keeps this test meaningful
        # instead of freezing a list of names that drifts.
        readers = []
        unreadable = []
        for name in re.findall(r"^static [\w \*&]*?\b(VF2\w+)\(", SOURCE, re.M):
            body = find_function_body(name)
            if body is None:
                # A name with no definition is a forward declaration and is
                # genuinely nothing to check. A name WITH a definition that the
                # helper could not read is a harness fault, and skipping it
                # would exempt that function from this rule while the test
                # stayed green -- which is the defect this suite exists to
                # catch, in the suite itself.
                if has_definition(name):
                    unreadable.append(name)
                continue
            if PERSISTENT_LABEL_OFFSET not in body:
                continue
            compares = re.search(r"\bstrn?cmp\b", body)
            against_a_group = re.search(r"labels\[|kVF2BehaviorLabels_", body)
            if compares and against_a_group:
                readers.append(name)
        self.assertEqual(
            sorted(unreadable), [],
            "these functions have definitions this test could not parse, so "
            "they were exempted from the rule below without anyone noticing",
        )
        self.assertEqual(
            sorted(set(readers) - {"VF2ScanLabelGroup"}),
            [],
            "a function reads the persistent behaviour label at %s without "
            "going through the cache gate; a leftover label from a finished "
            "behaviour will be mistaken for the current one and the group "
            "will stop re-rolling" % PERSISTENT_LABEL_OFFSET,
        )

    def test_every_scan_call_site_is_gated(self):
        """No caller may scan without first proving the cache is still live."""
        for name in ("VF2CurrentLabelInGroup", "VF2CurrentLabelInGroupTagged",
                     "VF2CurrentLabelInGroups2", "VF2CurrentLabelInGroups3"):
            body = function_body(name)
            self.assertIn(
                "VF2BehaviorLabelStillFromThisSession", body,
                "%s scans the persistent label without a cache gate" % name,
            )
            gate = body.index("VF2BehaviorLabelStillFromThisSession")
            scan = body.index("VF2ScanLabelGroup")
            self.assertLess(
                gate, scan,
                "%s scans before it gates, so a stale label still wins" % name,
            )


class TheCacheTagMatchesWhatTheApplierWrote(unittest.TestCase):
    """A gate that looks up the wrong slot re-rolls mid-activity instead.

    The multi-group appliers cache under the FIRST group's address. A chain
    scanning group B or C therefore has to present group A's address, or the
    lookup misses, the villager is treated as new, and the caption changes
    while the action is still running -- the opposite regression.
    """

    def test_the_multi_group_appliers_still_cache_under_the_first_group(self):
        # The premise of the tagging rule. If an applier ever changes its tag,
        # this fails rather than the rule quietly protecting against nothing.
        for name in ("VF2ApplyRememberedOrRandomLabels2",
                     "VF2ApplyRememberedOrRandomLabels3"):
            self.assertIn(
                "int cacheTag = (int)labelsA;", function_body(name),
                "%s no longer caches under the first group" % name,
            )

    def test_the_grouped_resolvers_gate_once_on_the_first_group(self):
        for name in ("VF2CurrentLabelInGroups2", "VF2CurrentLabelInGroups3"):
            self.assertIn(
                "VF2BehaviorLabelStillFromThisSession(villager, (int)labelsA)",
                function_body(name),
                "%s gates on a tag its applier never wrote" % name,
            )

    def test_the_hand_rolled_chains_gate_on_their_applier_tag(self):
        # These predate the grouped helpers and chain the scan by hand. Each
        # follow-on group must borrow group A's tag.
        for resolver, tag in (
            ("VF2CurrentShowerLabel", "kVF2BehaviorLabels_shower_general"),
            ("VF2CurrentSitDownLabel", "kVF2BehaviorLabels_sit_down_general"),
        ):
            body = function_body(resolver)
            follow_on = re.findall(
                r"VF2CurrentLabelInGroupTagged\(villager, \(int\)(\w+),", body)
            self.assertTrue(
                follow_on, "%s stopped tagging its follow-on scans" % resolver)
            self.assertEqual(
                set(follow_on), {tag},
                "%s gates a follow-on group on a tag its applier never wrote"
                % resolver,
            )

    def test_coffee_keeps_its_per_group_tags(self):
        """Coffee is the exception and must stay one.

        VF2ApplyCoffeeLabel rolls from whichever pool the time of day selects
        and caches under THAT pool's address, so no single tag covers it. Each
        group's own address is the tag it was written under.
        """
        body = function_body("VF2CurrentCoffeeLabel")
        self.assertNotIn(
            "VF2CurrentLabelInGroupTagged", body,
            "coffee caches under the group it rolled from, so forcing a single "
            "tag here would miss the slot and re-roll mid-drink",
        )

class InterleavedVillagersKeepTheirOwnLabels(unittest.TestCase):
    """Executed, not asserted about the source.

    Codex's P1 could not be seen by a source-contract test: nothing about the
    SHAPE of `VF2GetCachedBehaviorLabel(villager, cacheTag, &id)` reveals that
    it consults a global which, at that moment, names a different villager.
    These tests transcribe both predicates from the emitted C and run them
    against two villagers whose behaviours interleave.
    """

    class Slot(object):
        def __init__(self, villager, behavior_id, serial, praise_count=0,
                     string_id=0x1234):
            self.villager = villager
            self.behaviorId = behavior_id
            self.behaviorSerial = serial
            self.praiseCount = praise_count
            # 0 means "the native label is the current one" (the roll-0 case).
            self.stringId = string_id

    class Villager(object):
        def __init__(self, behavior_id, serial, praised_id=-1, praise_count=0):
            self.behaviorId = behavior_id
            self.behaviorSerial = serial
            self.praisedBehaviorId = praised_id
            self.praiseCount = praise_count

    @staticmethod
    def cache_still_active(slot, villager, before_villager):
        """VF2BehaviorLabelCacheStillActive, including its global guard."""
        if slot is None or before_villager is not slot.villager:
            return False
        if villager.behaviorId != slot.behaviorId:
            return False
        if villager.behaviorSerial == slot.behaviorSerial:
            return True
        return (villager.behaviorSerial == slot.behaviorSerial + 1
                and villager.praisedBehaviorId == villager.behaviorId
                and villager.praiseCount != slot.praiseCount)

    @staticmethod
    def slot_is_current_for(villager, slot, writeback=True):
        """VF2BehaviorLabelSlotIsCurrentFor -- no global, but it DOES advance
        the slot when it accepts a praise restart.

        ``writeback=False`` models the earlier read-only version, so the defect
        it caused can be reproduced rather than described.
        """
        if slot is None or slot.villager is not villager:
            return False
        if villager.behaviorId != slot.behaviorId:
            return False
        if villager.behaviorSerial == slot.behaviorSerial:
            if writeback:
                slot.praiseCount = villager.praiseCount
            return True
        if (villager.behaviorSerial == slot.behaviorSerial + 1
                and villager.praisedBehaviorId == villager.behaviorId
                and villager.praiseCount != slot.praiseCount):
            if writeback:
                slot.behaviorSerial = villager.behaviorSerial
                slot.praiseCount = villager.praiseCount
            return True
        return False

    def test_the_old_gate_fails_when_another_villager_ran_last(self):
        """The P1, reproduced.

        Two villagers are mid-activity. Ann's slot matches her behaviour
        exactly, but Bob was the last to enter a wrapped native behaviour, so
        the global names Bob. The old gate rejects Ann's own live slot.
        """
        ann = self.Villager(behavior_id=0x0B3, serial=7)
        bob = self.Villager(behavior_id=0x048, serial=2)
        ann_slot = self.Slot(ann, 0x0B3, 7)

        self.assertFalse(
            self.cache_still_active(ann_slot, ann, before_villager=bob),
            "this is the P1: it should fail, which is why the gate moved",
        )
        self.assertTrue(
            self.slot_is_current_for(ann, ann_slot),
            "the corrected gate must accept Ann's own live slot regardless of "
            "which villager most recently ran a wrapped native behaviour",
        )

    def test_a_slot_belonging_to_another_villager_is_still_rejected(self):
        # Dropping the global must not drop the identity check with it.
        ann = self.Villager(behavior_id=0x0B3, serial=7)
        bob = self.Villager(behavior_id=0x0B3, serial=7)
        self.assertFalse(self.slot_is_current_for(ann, self.Slot(bob, 0x0B3, 7)))

    def test_a_new_behaviour_instance_is_rejected(self):
        # The whole point of the fix: a finished behaviour must not pin its
        # label onto the next one.
        ann = self.Villager(behavior_id=0x0B3, serial=8)
        self.assertFalse(self.slot_is_current_for(ann, self.Slot(ann, 0x0B3, 7)))

    def test_a_different_behaviour_id_is_rejected(self):
        ann = self.Villager(behavior_id=0x048, serial=7)
        self.assertFalse(self.slot_is_current_for(ann, self.Slot(ann, 0x0B3, 7)))

    def test_a_praise_reroll_is_still_the_same_activity(self):
        # Serial+1 with a praise on this behaviour is a re-roll, not a new
        # session, and must keep the label.
        ann = self.Villager(behavior_id=0x0B3, serial=8,
                            praised_id=0x0B3, praise_count=3)
        self.assertTrue(self.slot_is_current_for(
            ann, self.Slot(ann, 0x0B3, 7, praise_count=2)))

    def test_two_consecutive_praises_both_keep_the_label(self):
        """The second P1, reproduced.

        The serial+1 allowance is measured against the SLOT, so accepting a
        restart has to adopt it as the new baseline. Leaving the slot at N
        makes the second praise arrive at N+2 and be rejected as a new
        session, and the caption re-rolls on the second praise of the same
        action.
        """
        ann = self.Villager(behavior_id=0x0B3, serial=7)
        slot = self.Slot(ann, 0x0B3, 7, praise_count=0)
        for praise in (1, 2):
            ann.behaviorSerial += 1
            ann.praisedBehaviorId = 0x0B3
            ann.praiseCount = praise
            self.assertTrue(
                self.slot_is_current_for(ann, slot),
                "praise %d re-rolled the label; the accepted restart did not "
                "advance the slot" % praise,
            )

    def test_the_read_only_version_reproduces_the_defect(self):
        # Proof the test above can fail: without the writeback the second
        # praise is rejected. A check that cannot fail is not evidence.
        ann = self.Villager(behavior_id=0x0B3, serial=7)
        slot = self.Slot(ann, 0x0B3, 7, praise_count=0)
        results = []
        for praise in (1, 2):
            ann.behaviorSerial += 1
            ann.praisedBehaviorId = 0x0B3
            ann.praiseCount = praise
            results.append(
                self.slot_is_current_for(ann, slot, writeback=False))
        self.assertEqual(results, [True, False])

    def test_the_direct_set_branches_never_refresh_the_slot(self):
        """Why the writeback cannot be left to the appliers.

        Most appliers incidentally refresh the slot through
        VF2RememberBehaviorLabel, which is why this defect hid. These four take
        a remembered value and only restore the label text, so nothing else
        advances the slot for them.
        """
        for name in ("VF2ApplyCoffeeLabel", "VF2ApplyShowerLabel",
                     "VF2RandomBigBurgerLabel", "VF2RandomBigCoffeeLabel"):
            body = function_body(name)
            # The branch that honours an already-resolved label: it sets the
            # text and returns, so nothing here advances the cache slot.
            self.assertRegex(
                body,
                r"if \((?:remembered|rememberedStringId)\) \{\s*"
                r"VF2SetBehaviorLabel\(villager, (?:remembered|rememberedStringId)\);\s*"
                r"return;",
                "%s no longer has a direct-set remembered branch; the premise "
                "of the writeback test has changed" % name,
            )
            self.assertNotIn(
                "VF2RememberBehaviorLabel", body,
                "%s now refreshes the slot itself; if that is deliberate the "
                "premise of the writeback test has changed" % name,
            )

    def test_the_predicate_advances_the_slot_on_an_accepted_restart(self):
        body = function_body("VF2BehaviorLabelSlotIsCurrentFor")
        self.assertIn("slot->behaviorSerial = behaviorSerial;", body)
        self.assertEqual(
            body.count("slot->praiseCount = praiseCount;"), 2,
            "both accept paths must record the praise count, as "
            "VF2BehaviorLabelCacheStillActive does",
        )

    def test_the_roll_zero_native_choice_survives_another_villager(self):
        """The third P1, reproduced.

        A group's roll-0 outcome means "keep the native label" and is cached as
        stringId 0. The native text matches nothing in any mod label group, so
        the resolver legitimately returns 0 and the applier falls through to its
        OWN cache lookup. Reading that through the global-guarded function
        reintroduces the defect one level down: with another villager last
        through the wrapped-native path the lookup fails, the applier rolls
        again, and a deliberate native-label choice becomes a mod caption
        mid-action.
        """
        ann = self.Villager(behavior_id=0x0B3, serial=7)
        bob = self.Villager(behavior_id=0x048, serial=2)
        # stringId 0 == "the native label is the current one".
        ann_slot = self.Slot(ann, 0x0B3, 7)
        ann_slot.stringId = 0

        # What the applier used to ask, with Bob last through the native path.
        self.assertFalse(
            self.cache_still_active(ann_slot, ann, before_villager=bob),
            "this is the P1: the applier's own cache read failed and it "
            "re-rolled over the native label",
        )
        # What it asks now.
        self.assertTrue(
            self.slot_is_current_for(ann, ann_slot),
            "the anchored read must find Ann's roll-0 choice regardless of "
            "which villager last ran a wrapped native behaviour",
        )

    def test_every_applier_reads_the_cache_villager_anchored(self):
        # The resolver being anchored is not enough; the appliers do their own
        # cache read, and that is where the roll-0 choice is honoured.
        for name in ("VF2ApplyRememberedOrRandomLabel", "VF2ApplyVenueLabel",
                     "VF2ApplyRememberedOrRandomLabels2",
                     "VF2ApplyRememberedOrRandomLabels3"):
            body = function_body(name)
            self.assertIn(
                "VF2GetVillagerCachedBehaviorLabel(villager, ", body,
                "%s reads the cache through the global-guarded function" % name,
            )
            self.assertNotIn("VF2GetCachedBehaviorLabel(villager, ", body)

    def test_the_anchored_reader_still_restores_the_native_label(self):
        # Dropping this call would leave the roll-0 case with no text to show.
        body = function_body("VF2GetVillagerCachedBehaviorLabel")
        self.assertIn("if (slot->stringId == 0) {", body)
        self.assertIn("VF2RestoreCachedNativeLabel(villager, cacheTag);", body)

    def test_the_radio_handler_keeps_the_global_guarded_read(self):
        """The one place the global IS the right question.

        VF2RandomRadioBehavior sets gVF2BehaviorLabelBeforeVillager itself and
        reads the cache inside that window, so retargeting it would change a
        call path this work has no business touching.
        """
        body = function_body("VF2RandomRadioBehavior")
        self.assertIn("gVF2BehaviorLabelBeforeVillager = &villager;", body)
        self.assertIn("VF2GetCachedBehaviorLabel(villager, cacheTag", body)
        self.assertNotIn("VF2GetVillagerCachedBehaviorLabel", body)

    def test_serial_plus_one_without_a_praise_is_a_new_session(self):
        # The praise allowance must not become a blanket "one serial of slack".
        ann = self.Villager(behavior_id=0x0B3, serial=8,
                            praised_id=-1, praise_count=2)
        self.assertFalse(self.slot_is_current_for(
            ann, self.Slot(ann, 0x0B3, 7, praise_count=2)))



class TheSweepSeesEveryEmittedDefinition(unittest.TestCase):
    """A definition the body finder cannot parse is silently exempt.

    The sweep over every VF2* name treats a None body as "forward
    declaration, nothing to check". That is correct for a real forward
    declaration and catastrophic for a definition the regex merely failed to
    match: the function is then exempt from the ungated-persistent-label check
    this file exists to enforce, and the run still reports green.

    Measured before the fix: 494 emitted VF2* definitions, 50 of which
    returned None because the return type was multi-word -- `unsigned int`,
    `unsigned char *`, `VF2DonorBehavior const *`. All 50 went unchecked.

    This pins the PROPERTY rather than the count, so it keeps working as the
    generator grows.
    """

    DEFINITION = (
        r'^(?:extern "C" )?(?:static )?[A-Za-z_][\w:<>, ]*?[ *]+'
        r'(VF2\w+)\([^;{]*\)\s*\n?\{'
    )

    def test_no_emitted_definition_is_invisible_to_the_sweep(self):
        definitions = set(re.findall(self.DEFINITION, SOURCE, re.M))
        self.assertGreater(
            len(definitions), 100,
            "the definition scan found almost nothing, so this test is not "
            "measuring what it claims to")
        invisible = sorted(name for name in definitions
                           if find_function_body(name) is None)
        self.assertEqual(
            invisible, [],
            "%d emitted definitions are invisible to find_function_body, so "
            "the sweep skips them as though they were forward declarations: "
            "%s" % (len(invisible), invisible[:8]))


if __name__ == "__main__":
    unittest.main()
