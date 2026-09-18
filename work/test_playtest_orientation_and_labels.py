#!/usr/bin/env python3
"""Regression tests for six defects reported from live play on 2026-09-14.

Every constant asserted here was decoded from the ORIGINAL game object files in
work/desktop_obj_files/, never from this repository's own generated sources.
That distinction is the point of the module. The bugs below all shipped in B186
having passed compilation, binary-signature verification and Codex review, and
several were "fixed" once already against evidence taken from other patcher
code -- which is circular, and confirmed nothing.

The ground truth, and where it comes from:

  EFurnitureOrientation, from the CodeView LF_ENUMERATE records that appear
  IDENTICALLY in two independent objs (FurnitureManager.obj at 0x52e0 and
  Behavior.obj at 0x9cfb):

      eFurnitureOrientation_SE = 0
      eFurnitureOrientation_SW = 1
      eFurnitureOrientation_NE = 2
      eFurnitureOrientation_NW = 3

  EHeadDirection, from theAlignVillagerScene.obj, which builds a const char*
  name table indexed directly by the enum value; the enumerator strings sit at
  consecutive intervals and appear twice (0x24457 and 0x2c9ef):

      -3 RandomUpward, -2 Random, -1 None, 0 Northeast, 1 Southeast,
       2 Southwest, 3 Northwest, 4 SouthSoutheast, 5 South, 6 SouthSouthwest,
       7 UpNE1, 8 UpNE2, 9 UpNW1, 10 UpNW2, 11 Down, 12..14 Detail1..3

  Corroborated by AnimManager.obj's RandomNorthHeadDirection array, {0, 3}.

  A villager FOLLOWS the furniture: NW furniture takes the NW art and head
  direction. ?CheckingFurnitureMagazine@CBehavior@@ shows the stock game doing
  exactly this -- orientation 3 (NW) selects "RestingLegsW", orientation 2 (NE)
  selects "RestingLegsE".
"""
import re
import unittest

NL = chr(10)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "patch_mobile_furniture_pack.py"
OBJS = ROOT / "work" / "desktop_obj_files"


def source_text():
    return SOURCE.read_text(encoding="utf-8")


class TheDecodedEnumValuesStillMatchTheGameObjects(unittest.TestCase):
    """Pin the constants against the objs, so a future edit cannot drift them.

    If these fail, the patcher's constants and the game's have diverged, and
    every orientation-dependent test below is meaningless until that is fixed.
    """

    def enumerator_value(self, obj_name, symbol):
        data = (OBJS / obj_name).read_bytes()
        index = data.find(symbol.encode("ascii"))
        if index < 0:
            self.skipTest("%s not present in %s" % (symbol, obj_name))
        return int.from_bytes(data[index - 2:index], "little")

    def test_furniture_orientation_is_se_sw_ne_nw(self):
        for obj_name in ("FurnitureManager.obj", "Behavior.obj"):
            with self.subTest(obj=obj_name):
                self.assertEqual(
                    self.enumerator_value(obj_name, "eFurnitureOrientation_SE"), 0)
                self.assertEqual(
                    self.enumerator_value(obj_name, "eFurnitureOrientation_SW"), 1)
                self.assertEqual(
                    self.enumerator_value(obj_name, "eFurnitureOrientation_NE"), 2)
                self.assertEqual(
                    self.enumerator_value(obj_name, "eFurnitureOrientation_NW"), 3)

    def test_stock_yoga_equipment_is_item_0x220(self):
        """The yoga drop fix is worthless if this id is wrong."""
        self.assertEqual(
            self.enumerator_value("FurnitureManager.obj", "eFurniture_YogaGearStd"),
            0x220)

    def head_direction_set(self, compass):
        """The VALUES in one sc_eHeadDirections array, decoded from the obj.

        Unlike EFurnitureOrientation, EHeadDirection has NO CodeView
        LF_ENUMERATE records anywhere in these objs -- I checked all 164, and
        the enumerator names in theAlignVillagerScene.obj are plain strings in a
        pointer table with no values beside them. So the values cannot be read
        off a debug record and must come from data that USES them.

        AnimManager.obj holds four static arrays naming the head directions
        legal for each compass quarter. Those are stored as literal ints, which
        is real value evidence rather than name ordering.
        """
        import struct
        data = (OBJS / "AnimManager.obj").read_bytes()
        opt = struct.unpack_from("<H", data, 16)[0]
        symoff = struct.unpack_from("<I", data, 8)[0]
        nsym = struct.unpack_from("<I", data, 12)[0]
        strtab = symoff + nsym * 18

        def symbol_name(off):
            raw = data[off:off + 8]
            if raw[:4] == b"\0\0\0\0":
                base = struct.unpack_from("<I", raw, 4)[0]
                end = data.index(b"\0", strtab + base)
                return data[strtab + base:end].decode("ascii", "replace")
            return raw.rstrip(b"\0").decode("ascii", "replace")

        wanted = "sc_eHeadDirections@?1??Random%sHeadDirection" % compass
        for i in range(nsym):
            off = symoff + i * 18
            name = symbol_name(off)
            if wanted not in name:
                continue
            value, section = struct.unpack_from("<IH", data, off + 8)
            if section == 0:
                continue
            sh = 20 + opt + (section - 1) * 40
            praw = struct.unpack_from("<I", data, sh + 20)[0]
            raw = data[praw + value:praw + value + 16]
            return [int.from_bytes(raw[k:k + 4], "little") for k in range(0, 16, 4)]
        self.skipTest("no sc_eHeadDirections array for %s" % compass)

    def test_head_direction_values_put_northeast_at_0_and_northwest_at_3(self):
        """Decode the VALUES, not the order the names happen to appear in.

        An earlier version of this test only checked that four symbol names
        occurred in ascending address order, which would still pass if the
        whole enum were shifted -- exactly the objection Codex raised, and it
        was right. The constants are now derived from arrays of literal values.

        The north array is the decisive one: it contains precisely the two
        north-facing directions. Whichever of them also appears in the west
        array is Northwest, and whichever appears in the east array is
        Northeast. No name ordering is consulted at all.
        """
        north = self.head_direction_set("North")
        east = self.head_direction_set("East")
        west = self.head_direction_set("West")

        self.assertEqual(
            sorted(north[:2]), [0, 3],
            "RandomNorthHeadDirection no longer holds {0, 3}, so NE=0 and NW=3 "
            "must be re-derived before trusting the patcher's constants")

        northwest = [v for v in north[:2] if v in west]
        northeast = [v for v in north[:2] if v in east]
        self.assertEqual(
            northwest, [3],
            "the north direction that is also legal facing west is not 3")
        self.assertEqual(
            northeast, [0],
            "the north direction that is also legal facing east is not 0")

    def test_the_patcher_constants_match_the_decoded_values(self):
        """Close the loop: the decoded values must be what the source declares.

        Without this the decode above and the source assertions elsewhere in
        this module never meet, and each could drift independently.
        """
        north = self.head_direction_set("North")
        east = self.head_direction_set("East")
        west = self.head_direction_set("West")
        northeast = [v for v in north[:2] if v in east][0]
        northwest = [v for v in north[:2] if v in west][0]
        text = source_text()
        self.assertIn("eHeadDirectionNE = %d" % northeast, text)
        self.assertIn("eHeadDirectionNW = %d" % northwest, text)


class TheHeadDirectionConstantsAreCorrect(unittest.TestCase):
    """Reported twice in play: spa loungers orient villagers wrongly.

    Both constants were wrong, which is why two attempted fixes changed nothing
    a player could see. Declared in two translation units, so both are checked.
    """

    def test_no_declaration_uses_the_old_wrong_values(self):
        """Only real declarations count.

        The comments above each enum quote the old values deliberately, to
        record what was wrong and why, so a plain substring search would match
        that documentation and fail forever. Comment lines are stripped first.
        """
        code = NL.join(
            line for line in source_text().splitlines()
            if not line.lstrip().startswith("//"))
        self.assertNotIn(
            "eHeadDirectionNE = 1", code,
            "eHeadDirectionNE = 1 is Southeast, not Northeast")
        self.assertNotIn(
            "eHeadDirectionNW = 7", code,
            "eHeadDirectionNW = 7 is UpNE1, an upward gaze, not Northwest")

    def test_every_declaration_uses_the_decoded_values(self):
        text = source_text()
        self.assertGreaterEqual(text.count("eHeadDirectionNE = 0"), 1)
        self.assertGreaterEqual(text.count("eHeadDirectionNW = 3"), 1)


class TheOrientationTestsCoverNorthwest(unittest.TestCase):
    """`orientation == 1` is SW ALONE: it misses NW and wrongly claims SW.

    Reported in play with a screenshot: a picnic table facing NE seated its
    villagers and drew its meal facing the other way.
    """

    def test_a_shared_helper_exists_and_names_northwest_only(self):
        text = source_text()
        self.assertIn("static bool VF2FurnitureFacesNorthWest(int orientation)", text)
        match = re.search(
            r"static bool VF2FurnitureFacesNorthWest\(int orientation\)\s*\{(.*?)\}",
            text, re.S)
        self.assertIsNotNone(match)
        self.assertIn("== 3", match.group(1))

    def test_the_seating_animations_use_the_helper(self):
        """Both the picnic table and the patio chair, the latter of which also
        serves the INVISIBLE Patio Table via VF2HandleMobilePatioTable."""
        text = source_text()
        for block in re.findall(
                r"[^\n]*\?\s*\"Sit In Chair NW\"\s*:\s*\"Sit In Chair NE\"", text):
            with self.subTest(block=block.strip()[:60]):
                self.assertNotIn("orientation == 1", block)
        self.assertEqual(text.count('"Sit In Chair NW"'), 2)

    def test_the_meal_sprite_splits_on_the_east_half(self):
        """mealSE/mealSW are an EAST/WEST pair, so the split is {SE, NE}."""
        text = source_text()
        self.assertIn("gVF2PicnicPropOrientation == 0 /* SE */", text)
        self.assertIn("gVF2PicnicPropOrientation == 2 /* NE */", text)
        self.assertNotIn("gVF2PicnicPropOrientation == 1", text)

    def test_the_hammock_settle_pose_and_sleep_strip_share_one_test(self):
        """Reported in play: the lie-down faced wrong while the sleep was right.

        The sleep leg passed an animation name and was correct; the settle leg
        passed a head-direction constant and was not. Deriving both from one
        condition is what stops them disagreeing again. The animation SELECTION
        is deliberately unchanged -- the owner confirmed it correct in play.
        """
        text = source_text()
        self.assertIn("hammockFacesNorthWest", text)
        self.assertIn(
            'char const *sleepAnim = hammockFacesNorthWest ? "SleepNW" : "SleepNE";',
            text)


class TheTreadmillDoesNotUseAPositionBlindQuery(unittest.TestCase):
    """Reported in play: the treadmill still shows the exercise bike's labels.

    CContentMap::FindObject's decorated name is

        ?FindObject@CContentMap@@QAE?B_NW4EObject@1@AAUldwPoint@@@Z

    -- an object enum and an out-point, with NO villager and NO position. It is
    a global query returning the same placement for every villager, so with a
    treadmill and a bike sharing EObject 0x04 it classified every user of either
    machine identically.

    Both stock treadmill behaviours carry exactly ONE furniture relocation,
    ?FindFurniture@CFurnitureManager@@, and reference neither
    LinkPeepToFurniture nor FindObject -- so the wrapper's own FindFurniture
    probe already reproduces the native choice, and the override could only
    replace a correct answer with a position-blind one.
    """

    def test_the_routed_item_machinery_is_gone(self):
        text = source_text()
        code = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("//"))
        for symbol in ("gVF2RoutedItemValid", "gVF2RoutedItemPlans",
                       "VF2RoutedToItem", "VF2ItemIdAtPoint"):
            with self.subTest(symbol=symbol):
                self.assertNotIn(symbol, code)

    def test_the_wrappers_use_their_own_probe(self):
        text = source_text()
        self.assertIn("bool const onBike = bike;", text)
        self.assertIn("bool const onPingPong = pingPong;", text)
        self.assertNotIn("routeIsOurs", text)


class TheYogaEquipmentAnswersADropOnTheStockItem(unittest.TestCase):
    """Reported in play: dropping a villager on the yoga equipment does nothing.

    The dispatch matched only InvisibleYogaEquipment (0x32A), so a drop on the
    visible stock item (0x220) fell through to the stock hotspot -- and stock
    yoga equipment is scenery, since CBehavior::WorkingOut consults no furniture
    at all. The venue lookup needed the same pairing, or the behaviour finds no
    venue and falls back to the plain donor, which relabels the villager
    "Working out" rather than "Doing yoga".
    """

    def test_the_drop_dispatch_accepts_the_stock_id(self):
        text = source_text()
        self.assertIn(
            "if (candidate == 0x220 || candidate == __VF2_YOGA_EQUIPMENT_ITEM_ID__)",
            text)

    def test_the_venue_lookup_accepts_a_second_item_id(self):
        text = source_text()
        self.assertIn("static bool VF2FindAddedFurnitureVenueEx(", text)
        self.assertIn("__VF2_YOGA_EQUIPMENT_ITEM_ID__, 0x220, 0x75,", text)

    def test_the_home_gym_does_not_get_a_second_id(self):
        """Scope guard: the gym's donor is the same yoga item, and a stray
        alternate id here would make a drop on the yoga mat run gym labels."""
        text = source_text()
        self.assertIn("__VF2_HOME_GYM_ITEM_ID__, -1, 0x75,", text)


class ThePositionNudgesAreNamedAndScoped(unittest.TestCase):
    """Two positioning reports, both confirmed working apart from placement.

    The owner confirmed the patio drinks now render ON TOP of the table and
    asked only for a shift right; and asked for the home gym's villager to stand
    lower and left, in the cubby. Named constants so a follow-up playtest has
    numbers to retune rather than buried literals.
    """

    def test_the_patio_nudge_is_applied_at_the_draw_only(self):
        text = source_text()
        self.assertIn("static int const kVF2PatioDrinksNudgeX", text)
        self.assertIn("gVF2PatioPropX + kVF2PatioDrinksNudgeX", text)

    def test_the_home_gym_nudge_is_scoped_to_the_gym(self):
        """The gym's own correction stays keyed to the gym's item id.

        SUPERSEDED CLAIM, recorded rather than deleted (AGENTS.md 11): this
        docstring previously said the Yoga Equipment "stands correctly, so it
        must not move". That was wrong. The owner reported with a screenshot
        that a villager doing yoga stands off the mat's right edge on bare
        floor, so the yoga route needs its own correction -- pinned by
        test_the_yoga_route_centres_the_villager_on_the_mat below. The two
        corrections are separate because they want different destinations: the
        gym's cubby is not the mat's centre.
        """
        text = source_text()
        self.assertIn("if (itemId == __VF2_HOME_GYM_ITEM_ID__) {", text)
        self.assertIn("VF2FurnitureFacesEast(foundOrientation)", text)
        self.assertIn("kVF2HomeGymStandNudgeX", text)
        self.assertIn("outPoint.y += kVF2HomeGymStandNudgeY;", text)

    def test_the_yoga_route_centres_the_villager_on_the_mat(self):
        """Doing yoga must stand the villager ON the blue mat, not beside it.

        Reported in play with a screenshot. The fmap is not at fault: decoding
        the owner's APK (1.7.16, main.43 OBB) shows YogaGearStd.png.fmap is
        byte-identical to both shipped PC maps, including its six-cell stand
        block 0x0203A800 at (3,2) (4,2) (5,2) (3,3) (4,3) (5,3). The hotspot
        the engine derives from it lands at that block's EDGE, so the
        destination takes a correction the same shape the Home Gym uses.

        Covers BOTH variants: 0x220 is the stock Yoga Equipment and
        __VF2_YOGA_EQUIPMENT_ITEM_ID__ substitutes to InvisibleYogaEquipment.
        """
        text = source_text()
        self.assertIn(
            "if (itemId == 0x220 || itemId == __VF2_YOGA_EQUIPMENT_ITEM_ID__) {",
            text,
            "the yoga centring is gone, or no longer covers both variants")
        self.assertIn("kVF2YogaMatCentreNudgeX", text)
        # NE/NW, not merely east/west. The owner asked to "move yoga NE or
        # NW depending on furniture position 5 pixels" after playing the build
        # whose correction moved along X with a flat +Y. +Y is DOWN-screen, so
        # both diagonals require a NEGATIVE Y -- the same convention the picnic
        # meal nudge uses and which is confirmed correct in play.
        self.assertIn("outPoint.y -= kVF2YogaMatCentreNudgeY;", text,
                      "the yoga correction no longer travels up-screen, so it "
                      "is east/west rather than NE/NW")
        self.assertNotIn("outPoint.y += kVF2YogaMatCentreNudgeY;", text,
                         "a positive Y moves the villager DOWN-screen, which "
                         "is neither NE nor NW")
        # Orientation-aware per the owner's standing rule: respect the
        # furniture orientation always.
        block = text[text.index("THE YOGA MAT: STAND ON IT"):]
        block = block[:block.index("return true;")]
        self.assertIn("VF2FurnitureFacesEast(foundOrientation)", block,
                      "the yoga correction ignores the furniture orientation")
        self.assertIn("-kVF2YogaMatCentreNudgeX", block,
                      "the correction is not mirrored for west-facing mats")

    def test_the_picnic_meal_moves_up_and_toward_each_table_facing(self):
        text = source_text()
        self.assertIn("kVF2PicnicMealNudgeX", text)
        self.assertIn("kVF2PicnicMealNudgeY", text)
        self.assertIn("VF2FurnitureFacesEast(gVF2PicnicPropOrientation)", text)
        self.assertIn("gVF2PicnicPropY - kVF2PicnicMealNudgeY", text)

    def test_yoga_uses_the_orientation_aware_native_workout_route(self):
        text = source_text()
        start = text.rindex('extern "C" void __cdecl VF2YogaEquipmentWorkout')
        end = text.index('extern "C" void __cdecl VF2PingPongPlay', start)
        body = text[start:end]
        self.assertIn("VF2RunOwnFurnitureActionVaried", body)
        self.assertIn("CBehavior::WorkingOut", text)
        self.assertIn("FindFurniture", text)
        self.assertIn("VF2VillagerIsDroppedOnAddedFurniture", text)


class EveryPatchDefaultsOnInTheGenerator(unittest.TestCase):
    """Requested by the owner: "fix the default generator so ALL PATCHES ARE ON".

    The generator's flags had defaulted OFF while the exporter's settings table
    said the features shipped enabled. A plain generator run therefore produced
    a nearly-stock build, and any check run against those sources could report a
    fix "absent" when it was merely compiled out.

    The named exception is the invisible transparent furniture graphics, which
    the owner excluded by name: it has a sequencing dependency, since the player
    must place the invisible furniture while it is still visible.
    """

    OPT_IN_BY_DESIGN = {
        # Not a player-facing patch. Its own comment records that the
        # debugger/editor hooks have repeatedly crashed during save-load and
        # mouse input, so defaulting it on would ship those crashes.
        "VF2_ENABLE_DEBUGGER_FEATURES",
    }

    def test_no_feature_gate_defaults_off(self):
        offenders = []
        for match in re.finditer(
                r'os\.environ\.get\(\s*"(VF2_ENABLE_[A-Z0-9_]+)"\s*,\s*"0"\s*\)',
                source_text()):
            name = match.group(1)
            if name not in self.OPT_IN_BY_DESIGN:
                offenders.append(name)
        self.assertEqual(
            sorted(offenders), [],
            "these feature gates still default OFF, so a plain generator run "
            "omits them: %s" % sorted(offenders))

    def test_the_runtime_gates_stay_dormant_for_the_exporter(self):
        """The .vf2beh / .vf2scrl bytes must ship 0, and that is correct.

        This test previously asserted they default to 1, on the theory that a
        0 meant the features shipped "compiled in but inert". That was wrong,
        and the export proved it: work/export_offline_patch_bundle.py asserts
        the shipped default is 00 (runtime_flag_variant_for_exe), so a 1 here
        aborts the whole bundle with ".vf2beh default byte mismatch".

        The real contract is that the linked EXE carries each byte DORMANT and
        the exporter emits an exact-SHA post-asset patch rewriting 00 -> 01
        when the player's setting is enabled. Both settings already default to
        True, so the features are on by default in the artifact players
        install -- which is what the owner asked for. Whether a gated feature
        is on by default is decided by the setting default plus that toggle,
        NOT by the byte in the linked EXE.
        """
        text = source_text()
        self.assertIn(
            "volatile unsigned char gVF2MobileFurnitureBehaviors = 0;", text)
        self.assertIn(
            "volatile unsigned char gVF2StoreScrollbar = 0;", text)
        self.assertNotIn(
            "volatile unsigned char gVF2MobileFurnitureBehaviors = 1;", text)
        self.assertNotIn(
            "volatile unsigned char gVF2StoreScrollbar = 1;", text)

    def test_the_exporter_settings_that_drive_those_bytes_default_on(self):
        """The byte is dormant, so THIS is what makes the features ship on.

        The owner asked for a patcher where all patches are on by default,
        with the invisible transparent furniture graphics as the single
        exception. For .vf2beh and .vf2scrl the linked EXE deliberately ships
        0, so the only thing that decides what a player gets is the exporter
        setting default plus its post-asset toggle. Nothing pinned that, which
        is how a 1 in the generator came to look like the fix.
        """
        import sys
        sys.path.insert(0, str(ROOT / "work"))
        import export_offline_patch_bundle as exporter
        settings = {s["id"]: s for s in exporter.SETTINGS}
        for setting in ("behavior_patches", "mobile_furniture"):
            self.assertIn(setting, settings,
                          "no %s setting in the exporter" % setting)
            self.assertTrue(
                settings[setting]["default"],
                "%s no longer defaults on, so the patcher would ship it off "
                "even though the dormant runtime byte relies on it" % setting)

    def test_the_transparent_graphics_setting_still_ships_disabled(self):
        """The reverse failure. Turning this on by default would leave a player
        placing invisible furniture they cannot see."""
        exporter = (ROOT / "work" / "export_offline_patch_bundle.py").read_text(
            encoding="utf-8")
        index = exporter.index('"id": "invisible_furniture_transparent_graphics"')
        entry = exporter[index:index + 600]
        self.assertIn('"default": False', entry)


if __name__ == "__main__":
    unittest.main()
