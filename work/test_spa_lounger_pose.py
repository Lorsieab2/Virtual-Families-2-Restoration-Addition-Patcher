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
  * VF2PlanSpaLoungerRest, which settles THROUGH that table and only then
    sleeps -- used by the spa treatment and by the relax sites' nap and sleep
    rolls only; awake rolls (reading, studying, sitting) hold the pose;
  * the drop route verifies the link landed on a spa lounger, and otherwise
    uses the linked chaise for an ordinary relax rather than the treatment;
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
                    "        if (sleeping) {\n"
                    "            VF2PlanSpaLoungerRest(plans, info.orientation, duration);\n"
                    "        } else {\n"
                    "            VF2PlanSpaLoungerPose(plans, info.orientation, duration);\n"
                    "        }",
                    body,
                    "relax site %d does not split on the roll: nap and sleep "
                    "rolls must sleep (Rest), awake rolls -- reading, "
                    "studying, sitting -- must hold the pose (Pose), as the "
                    "ordinary chaise does. Review caught each half once." % n)
                self.assertLess(
                    body.index("VF2SpaLoungerHasHandle(info.unknown0)) {"),
                    body.index("info.orientation == 1"),
                    "relax site %d tests orientation before the spa handle, so "
                    "a spa lounger at orientation 1 takes the ordinary branch" % n)

    def test_the_sleeping_flag_comes_from_the_nap_and_sleep_rolls_only(self):
        src = _strip_comments(_source())
        site1 = _function(src, "static bool VF2HandleMobileChaise(CVillager &villager)")
        self.assertEqual(site1.count("sleeping = true;"), 2,
                         "site 1 must flag exactly the nap and sleep rolls")
        for label in ('"Taking a nap"', '"Getting some sleep"'):
            i = site1.index(label)
            self.assertLess(i, site1.index("sleeping = true;", i),
                            "%s does not set the flag" % label)
        for label in ('"Reading a book"', '"Studying on the lounger"',
                      '"Needs to sit down"', '"Relaxing on lounger"'):
            i = site1.index(label)
            nxt = site1.index("} else", i)
            self.assertNotIn("sleeping = true;", site1[i:nxt],
                             "%s is flagged as sleeping" % label)
        self.assertIn("bool sleeping = false)", src,
                      "site 2 no longer takes the flag as a defaulted parameter")
        calls = []
        i = 0
        while True:
            i = src.find("VF2PlanLinkedChaiseAction(", i + 1)
            if i < 0:
                break
            calls.append(src[i:src.index(");", i) + 2])
        sleeping_calls = [c for c in calls if c.endswith(", true);")]
        self.assertEqual(
            len(sleeping_calls), 2,
            "exactly the two sleep callers of VF2PlanLinkedChaiseAction pass "
            "true; found %d of %d calls" % (len(sleeping_calls), len(calls)))
        for label in ('"Getting some sleep"', '"Taking a nap"'):
            i = src.index('villager, info, ' + label)
            self.assertIn(", true);", src[i:src.index(");", i) + 2],
                          "%s caller does not pass sleeping" % label)

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
            src.count("VF2PlanSpaLoungerRest(plans, info.orientation, duration);"), 2,
            "expected the rest under `if (sleeping)` at exactly the two relax sites")
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
        # ...but it does VERIFY what the link landed on. eObjectChaise is
        # shared and the link skips a placement with no free peep slot, so a
        # drop on a spa lounger can link an ordinary chaise. That chaise is
        # used as what it is -- an ordinary relax -- never for the treatment.
        guard = after_link.index("int const droppedOn = VF2FurnitureHandleAtSlot(loungerSlot);")
        self.assertLess(guard, after_link.index("VF2SpaTreatmentPoint("),
                        "the handle is checked after the treatment is planned")
        # ...and against the EXACT lounger the player dropped on. With two
        # spa loungers the link can land on the other one (review, round 8).
        self.assertIn(
            "        VF2SpaLoungerHasHandle(receiveInfo.unknown0) &&\n"
            "        (droppedOn == 0 || receiveInfo.unknown0 == droppedOn);\n"
            "    if (!linkedTheDroppedOnLounger) {",
            after_link,
            "the guard accepts any spa lounger; it must require the "
            "dropped-on slot's own handle, and take the fallback otherwise")
        fallback = after_link[guard:after_link.index("VF2SpaReleaseHoldOnLounger(")]
        self.assertIn("VF2SpaReleaseLoungerHold(villager);", fallback)
        self.assertIn('VF2PlanLinkedChaiseAction(\n            villager, receiveInfo, "Relaxing on lounger",', fallback)
        self.assertIn("return true;", fallback,
                      "the fallback falls through into the spa treatment")
        self.assertNotIn("VF2PlanSpaTreatment", fallback)
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


class TheCompiledArtifact(unittest.TestCase):
    """Decode the pose from the COMPILED unit, not from the generator text.

    Every class above reads work/patch_mobile_furniture_pack.py, so if the
    dispatch emitter stopped including this code they would keep passing
    against dead source while the shipped build lost the fix (AGENTS.md
    L16-20; review on #353 rounds 6 and 7). This class emits the flag-on
    units the way the build does, compiles the behaviours unit at /Od so the
    static helpers stay out of line, disassembles the object with dumpbin,
    and then EXECUTES the compiled helpers with a small x86 interpreter --
    once per orientation -- reading the arguments actually handed to each
    call. Checking that the four constants merely appear somewhere in the
    function is not enough: a build that swapped the arms would contain the
    same four constants (review, round 7). The interpreter follows the
    conditional control flow through the stores into the call.

    The listing produced alongside (/FAs) resolves the string labels the
    disassembly references, so the strip handed to PlanToPlayAnim is read
    as "SleepNE" / "SleepNW", not as an anonymous $SG symbol.

    Skips only for a genuinely absent prerequisite (no toolchain, no build
    inputs), never on a failure of the generator, compiler or interpreter.
    """

    THREE_ARG = "?PlanToWait@CVillagerPlans@@QAEXHW4EBodyPosition@@W4EHeadDirection@@@Z"
    FOUR_ARG = "?PlanToWait@CVillagerPlans@@QAEXHW4EBodyPosition@@W4EDirection@@W4EHeadDirection@@@Z"
    PLAY_ANIM = "?PlanToPlayAnim@CVillagerPlans@@QAEXHPBD_NM@Z"

    @classmethod
    def setUpClass(cls):
        import subprocess
        import sys
        import tempfile
        sys.path.insert(0, str(ROOT / "work"))
        import test_generated_cpp_compiles as compiles
        import test_spa_lounger_autonomous as auto

        cls.skip = None
        vcvars = None
        for candidate in getattr(compiles, "VCVARS_CANDIDATES", ()):
            if pathlib.Path(candidate).is_file():
                vcvars = candidate
                break
        if vcvars is None:
            cls.skip = "no Visual Studio toolchain on this machine"
            return
        result = auto.TheGuardSurvivesIntoTheEmittedArtifact._generate()
        if result is None or result[0] is None:
            reason = result[1] if result else "generation failed"
            if "ENABLE_BEHAVIOR_PATCHES" in reason:
                raise AssertionError(reason)
            cls.skip = "cannot emit the C++ in this checkout: %s" % reason
            return
        units = [(n, t) for n, t in result[2]
                 if "static void VF2PlanSpaLoungerPose(" in t]
        if len(units) != 1:
            raise AssertionError(
                "expected exactly one emitted unit to define "
                "VF2PlanSpaLoungerPose, found %d -- the emitter no longer "
                "includes the spa pose" % len(units))
        name, text = units[0]
        with tempfile.TemporaryDirectory() as tmp:
            work = pathlib.Path(tmp)
            (work / name).write_text(text, encoding="ascii")
            stem = pathlib.Path(name).stem
            obj = work / (stem + ".obj")
            asm = work / (stem + ".asm")
            listing = work / "disasm.txt"
            cmd = ('"%s" >nul 2>&1 && cl /c /nologo /EHsc /Od /FAs /Fa"%s" "%s" && '
                   'dumpbin /nologo /disasm "%s" > "%s"'
                   % (vcvars, asm, work / name, obj, listing))
            run = subprocess.run(cmd, cwd=work, shell=True,
                                 capture_output=True, text=True)
            if run.returncode != 0:
                raise AssertionError(
                    "the flag-on emission of %s does not compile or "
                    "disassemble:\n%s" % (name, (run.stdout or "")[-1500:]))
            cls.object_bytes = obj.read_bytes()
            disasm = listing.read_text(encoding="utf-8", errors="replace")
            asm_text = asm.read_text(encoding="utf-8", errors="replace")
        # $SG4447 DB 'SleepNE', 00H  ->  {"$SG4447": "SleepNE"}
        cls.strings = {
            m.group(1): m.group(2)
            for m in re.finditer(r"^(\$SG\d+)\s+DB\s+'([^']*)', 00H", asm_text, re.M)}
        cls.blocks = {}
        current = None
        for line in disasm.splitlines():
            if line and not line[0].isspace() and line.endswith(":"):
                current = line[:-1]
                cls.blocks[current] = []
            elif current is not None:
                cls.blocks[current].append(line)

    def setUp(self):
        if self.skip:
            self.skipTest(self.skip)

    def _block(self, fragment):
        keys = [k for k in self.blocks if fragment in k]
        self.assertEqual(
            len(keys), 1,
            "expected one compiled function containing %r, found %s"
            % (fragment, keys))
        return "\n".join(self.blocks[keys[0]])

    # ---- a small interpreter for the /Od code the compiler emits ---------

    _INSN = re.compile(r"^\s*([0-9A-F]{8}): (?:[0-9A-F]{2} )+\s*(\S+)\s*(.*?)\s*$")

    @staticmethod
    def _split_operands(text):
        out, depth, cur = [], 0, ""
        for ch in text:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            if ch == "," and depth == 0:
                out.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            out.append(cur.strip())
        return out

    def _run(self, block, args):
        """Execute one compiled helper; return the calls it made, in order.

        `args` are the C arguments in order. Each call is recorded as
        (callee, c_args, ecx): cdecl and thiscall both push right-to-left,
        so the C argument order is the reverse of the push order; thiscall's
        `this` travels in ecx.
        """
        code = {}
        order = []
        for line in block.splitlines():
            m = self._INSN.match(line)
            if m:
                addr = int(m.group(1), 16)
                code[addr] = (m.group(2), self._split_operands(m.group(3)))
                order.append(addr)
        self.assertTrue(order, "no instructions decoded")
        regs = {"eax": 0, "ecx": 0, "edx": 0}
        def disp(n):
            """dumpbin spells displacements as 8, 0Ch, 10h: decimal below
            ten, otherwise upper-case hex with a leading 0 when it would
            start with a letter."""
            if n < 10:
                return str(n)
            s = "%X" % n
            return ("0" + s if s[0].isalpha() else s) + "h"

        mem = {"ebp+" + disp(8 + 4 * i): a for i, a in enumerate(args)}
        flags = (0, 0)
        pushes = []
        calls = []

        def imm(tok):
            return int(tok[:-1], 16) if tok.endswith("h") else int(tok)

        def slot(tok):
            m2 = re.search(r"\[(ebp[+-][0-9A-Fa-f]+h?)\]", tok)
            self.assertIsNotNone(m2, "unsupported memory operand %r" % tok)
            return m2.group(1)

        def load(tok):
            if tok in ("eax", "ecx", "edx"):
                return regs[tok]
            if tok == "al":
                return regs["eax"] & 0xFF
            if tok.startswith("offset "):
                label = tok[len("offset "):]
                return self.strings.get(label, label)
            if "ptr [" in tok:
                key = slot(tok)
                self.assertIn(key, mem, "read of unset slot %s" % key)
                return mem[key]
            return imm(tok)

        def store(tok, value):
            if tok in ("eax", "ecx", "edx"):
                regs[tok] = value
            elif tok == "al":
                regs["eax"] = (regs["eax"] & ~0xFF) | (value & 0xFF)
            else:
                mem[slot(tok)] = value

        pc = order[0]
        for _ in range(10000):
            self.assertIn(pc, code, "jump to an address outside the function")
            op, ops = code[pc]
            nxt = order[order.index(pc) + 1] if order.index(pc) + 1 < len(order) else None
            if op in ("nop",) or (op == "int" and ops == ["3"]):
                pass
            elif op == "push" and ops == ["ebp"]:
                pass
            elif op == "pop" and ops == ["ebp"]:
                pass
            elif op == "mov" and ops[0] in ("ebp", "esp"):
                pass
            elif op in ("sub", "add") and ops[0] == "esp":
                pass
            elif op == "movss":
                pass
            elif op == "push":
                pushes.append(load(ops[0]))
            elif op == "call":
                calls.append((ops[0], list(reversed(pushes)), regs["ecx"]))
                pushes = []
            elif op == "ret":
                return calls
            elif op == "jmp":
                pc = int(ops[0], 16)
                continue
            elif op in ("mov", "movzx"):
                store(ops[0], load(ops[1]))
            elif op == "cmp":
                flags = (load(ops[0]), load(ops[1]))
            elif op == "test":
                flags = (load(ops[0]) & load(ops[1]), 0)
            elif op in ("jne", "je", "jle", "jge", "jl", "jg"):
                a, b = flags
                taken = {"jne": a != b, "je": a == b, "jle": a <= b,
                         "jge": a >= b, "jl": a < b, "jg": a > b}[op]
                if taken:
                    pc = int(ops[0], 16)
                    continue
            elif op == "cdq":
                regs["edx"] = -1 if regs["eax"] < 0 else 0
            elif op == "sub":
                store(ops[0], load(ops[0]) - load(ops[1]))
            elif op == "add":
                store(ops[0], load(ops[0]) + load(ops[1]))
            elif op == "sar":
                store(ops[0], load(ops[0]) >> load(ops[1]))
            else:
                self.fail("the interpreter does not handle %s %s at %08X; "
                          "extend it rather than skipping" % (op, ops, pc))
            self.assertIsNotNone(nxt, "fell off the end of the function")
            pc = nxt
        self.fail("the compiled helper did not return within 10000 steps")

    def _pose_args(self, orientation, duration=60):
        calls = self._run(self._block("VF2PlanSpaLoungerPose@@"),
                          ["plans", orientation, duration])
        self.assertEqual([c[0] for c in calls], [self.THREE_ARG],
                         "the compiled pose at orientation %d does not call "
                         "exactly the 3-argument PlanToWait once: %s"
                         % (orientation, [c[0] for c in calls]))
        callee, c_args, this = calls[0]
        self.assertEqual(this, "plans", "PlanToWait is not called on `plans`")
        return c_args  # [duration, body, head]

    def test_the_compiled_pose_takes_the_stock_table_arm_for_arm(self):
        """orientation 1 -> (0x17, NE=0); orientation 0 -> (9, NW=3)."""
        self.assertEqual(self._pose_args(1), [60, 0x17, 0],
                         "orientation 1 must lie with body eBodyPositionChaise "
                         "(0x17) and head eHeadDirectionNE (0)")
        self.assertEqual(self._pose_args(0), [60, 9, 3],
                         "orientation 0 must lie with body "
                         "eBodyPositionRestingHammock (9) and head "
                         "eHeadDirectionNW (3) -- 0x17 here is the ~20-round "
                         "defect, lying ACROSS the lounger")
        self.assertEqual(self._pose_args(2)[1:], [9, 3],
                         "any orientation other than 1 takes the hammock body")
        self.assertEqual(self._pose_args(1, 7)[0], 7,
                         "the duration is not passed through")

    def test_the_compiled_pose_calls_the_three_argument_wait(self):
        pose = self._block("VF2PlanSpaLoungerPose@@")
        self.assertIn("call        " + self.THREE_ARG, pose,
                      "the compiled pose does not call the 3-argument PlanToWait")
        self.assertNotIn(self.FOUR_ARG, pose,
                         "the compiled pose calls the 4-argument PlanToWait")
        self.assertNotIn("PlanToLieDown", pose)
        self.assertNotIn("PlanToPlayAnim", pose,
                         "the compiled pose plays a strip: every awake relax "
                         "roll on a spa lounger would sleep")

    def _rest_calls(self, orientation, duration):
        calls = self._run(self._block("VF2PlanSpaLoungerRest@@"),
                          ["plans", orientation, duration])
        self.assertEqual(
            [c[0] for c in calls],
            ["?VF2PlanSpaLoungerPose@@YAXPAVCVillagerPlans@@HH@Z", self.PLAY_ANIM],
            "the compiled rest must settle through the pose and then play "
            "the strip, nothing else: %s" % [c[0] for c in calls])
        return calls

    def test_the_compiled_rest_settles_then_sleeps_arm_for_arm(self):
        """Settle through the one body table, then SleepNE / SleepNW."""
        for orientation, strip in ((1, "SleepNE"), (0, "SleepNW")):
            with self.subTest(orientation=orientation):
                pose, anim = self._rest_calls(orientation, 60)
                self.assertEqual(pose[1], ["plans", orientation, 10],
                                 "the treatment (60 ticks) must settle for 10")
                self.assertEqual(anim[2], "plans")
                self.assertEqual(anim[1][0], 50, "the strip runs the remainder")
                self.assertEqual(anim[1][1], strip,
                                 "orientation %d must sleep with %s; the "
                                 "inverted strip shipped in several builds"
                                 % (orientation, strip))
                self.assertEqual(anim[1][2], 0, "the strip must not loop")
        pose, anim = self._rest_calls(0, 5)
        self.assertEqual(pose[1][2], 2, "a five-tick nap settles for two")
        self.assertEqual(anim[1][0], 3, "and sleeps for three")

    def test_every_compiled_route_reaches_the_pose(self):
        treatment = self._block("VF2PlanSpaTreatment@@")
        self.assertIn("call        ?VF2PlanSpaLoungerRest@@", treatment)
        for handler in ("VF2HandleMobileChaise@@", "VF2PlanLinkedChaiseAction@@"):
            block = self._block(handler)
            self.assertIn("call        ?VF2PlanSpaLoungerPose@@", block,
                          "%s does not reach the pose (awake rolls)" % handler)
            self.assertIn("call        ?VF2PlanSpaLoungerRest@@", block,
                          "%s does not reach the rest (nap/sleep rolls)" % handler)
        for handler in ("VF2HandleMobileInvisibleSpaLounger@@",
                        "VF2HandleMobileSpaLoungerReceiving@@"):
            self.assertIn("call        ?VF2PlanSpaTreatment@@", self._block(handler),
                          "%s does not reach the treatment" % handler)


if __name__ == "__main__":
    unittest.main()
