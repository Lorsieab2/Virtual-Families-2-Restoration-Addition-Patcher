#!/usr/bin/env python3
"""Read-only source contracts for the whole-family mobile manual routes."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATCH_SOURCE = ROOT / "work" / "patch_mobile_furniture_pack.py"
LEDGER = ROOT / "docs" / "B156-mobile-furniture-behavior-ledger.md"


def _between(text, start, end):
    begin = text.index(start)
    finish = text.index(end, begin + len(start))
    return text[begin:finish]


class MobileFamilyManualContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PATCH_SOURCE.read_text(encoding="utf-8")
        helper = cls.source.split("helper_source = r'''", 1)[1]
        cls.helper = helper.split("'''", 1)[0]
        cls.ledger = LEDGER.read_text(encoding="utf-8")

    def _metadata(self, name):
        start = self.source.index(f'"name": "{name}"')
        end = self.source.index("        }, {", start)
        return self.source[start:end]

    def test_manual_drop_only_metadata_and_dispatch(self):
        for name in (
            "mobile Birthday Banner",
            "mobile Christmas Trees",
            "mobile Dreidel",
            "mobile Menorah",
        ):
            metadata = self._metadata(name)
            self.assertIn('"manual_drop_only": True', metadata)
            self.assertIn('"whole_household": True', metadata)
            self.assertIn('"autonomous": False', metadata)

        dispatch = _between(
            self.helper,
            "bool const theMainScene::VF2HandleDropOnMobileFurniture",
            "\n}\n",
        )
        self.assertIn("if (gVF2MobileFurnitureBehaviors == 0) return false;", dispatch)
        for item_id, handler in (
            ("0x2DB", "VF2HandleMobileBirthdayBanner"),
            ("0x2AD || candidate == 0x2AE", "VF2HandleMobileXmasTreeGroup"),
            ("0x2AF", "VF2HandleMobileDreidelGroup"),
            ("0x2B8", "VF2HandleMobileMenorahGroup"),
        ):
            self.assertIn(f"candidate == {item_id}", dispatch)
            self.assertIn(f"return {handler}(villager);", dispatch)
        for item_id, handler in (
            ("0x2DC", "VF2HandleMobileBirthdayCake"),
            ("0x2DD", "VF2HandleMobileBirthdayPresents"),
            ("0x2DA", "VF2HandleMobileBirthdayBalloons"),
        ):
            self.assertIn(f"candidate == {item_id}", dispatch)
            self.assertIn(f"return {handler}(villager);", dispatch)

    def test_shared_household_collection_and_group_dispatch(self):
        eligibility = _between(
            self.helper,
            "static int VF2CollectEligibleHousehold",
            "static int VF2BirthdayObjectScan",
        )
        self.assertIn("index < 30", eligibility)
        self.assertIn("VillagerManager.VillagerExists(index, false)", eligibility)
        self.assertIn("data + 0x6B00", eligibility)
        self.assertIn("<= 0", eligibility)

        for handler, plan in (
            ("VF2HandleMobileXmasTreeGroup", "VF2RunMobileXmasTree"),
            ("VF2HandleMobileDreidelGroup", "VF2RunMobileDreidel"),
            ("VF2HandleMobileMenorahGroup", "VF2RunMobileMenorah"),
        ):
            group = _between(self.helper, f"static bool {handler}", "static int VF2VillagerValue")
            self.assertIn("VF2CollectEligibleHousehold(eligible)", group)
            self.assertIn(f"{plan}(*eligible[index]);", group)
            self.assertIn("return true;", group)

    def test_whole_family_handlers_are_not_autonomous_callbacks(self):
        autonomous = _between(
            self.source,
            "MOBILE_FURNITURE_EXTERNAL_AUTONOMOUS_SPECS = (",
            "MOBILE_SPECIAL_UPGRADE_ITEM_IDS =",
        )
        for handler in (
            "VF2HandleMobileBirthdayBanner",
            "VF2HandleMobileXmasTreeGroup",
            "VF2HandleMobileDreidelGroup",
            "VF2HandleMobileMenorahGroup",
        ):
            self.assertNotIn(handler, autonomous)

        self.assertIn("VF2HandleMobileAdmiringXmasTree", autonomous)
        self.assertIn("VF2HandleMobileAdultWaterXmasTree", autonomous)
        self.assertIn("VF2HandleMobileKidBreakingTreeDecor", autonomous)

    def test_birthday_banner_group_plan_invariants(self):
        scan = _between(
            self.helper,
            "static int VF2BirthdayObjectScan",
            "static void VF2RunMobileBirthdayCelebration",
        )
        self.assertRegex(
            scan,
            re.compile(
                r"eObjectBirthdayBanner.*eObjectBirthdayBalloons.*"
                r"eObjectBirthdayPresents.*eObjectBirthdayCake",
                re.S,
            ),
        )

        banner = _between(
            self.helper,
            "static bool VF2HandleMobileBirthdayBanner",
            "static bool VF2HandleMobileHolidayCandles",
        )
        self.assertIn("ObjectExists(CContentMap::eObjectBirthdayBanner)", banner)
        self.assertIn("objectCount > 1", banner)
        self.assertIn("VF2CollectEligibleHousehold(eligible)", banner)
        self.assertIn("VF2RunMobileBirthdayCelebration(*eligible[index]);", banner)
        self.assertIn("VF2HandleMobileBirthdayBalloons(villager)", banner)
        self.assertIn("VF2HandleMobileBirthdayPresents(villager)", banner)
        self.assertIn("VF2HandleMobileBirthdayCake(villager)", banner)

        plan = _between(
            self.helper,
            "static void VF2RunMobileBirthdayCelebration",
            "static bool VF2HandleMobileBirthdayBanner",
        )
        for token in (
            'VF2SetActionLabel(villager, "Celebrating birthday")',
            "0xFB",
            "PlanToJoyTwirlCW(ldwGameState::GetRandom(3) + 4)",
            "PlanToJump(10)",
            "PlanToJump(20)",
            "GetRandom(2) + 2",
            "GetRandom(2) + 1",
            "PlanToStopSound()",
            "StartNewBehavior(villager)",
        ):
            self.assertIn(token, plan)

    def test_tree_dreidel_menorah_exact_plan_invariants(self):
        tree = _between(
            self.helper,
            "static void VF2RunMobileXmasTree",
            "static bool VF2HandleMobileAdmiringXmasTree",
        )
        dreidel = _between(
            self.helper,
            "static void VF2RunMobileDreidel",
            "static void VF2RunMobileXmasTree",
        )
        menorah = _between(
            self.helper,
            "static void VF2RunMobileMenorah",
            "static bool VF2HandleMobileDreidelGroup",
        )

        for plan, object_id, label in (
            (tree, "eObjectXmasTree", "Celebrating around the tree"),
            (dreidel, "eObjectDreidel", "Playing Dreidel"),
            (menorah, "eObjectMenorah", "Celebrating Hanukkah"),
        ):
            self.assertIn(object_id, plan)
            self.assertIn(f'VF2SetActionLabel(villager, "{label}")', plan)
            self.assertNotIn("PlanToActivateProp", plan)
            self.assertNotIn("InventoryManager.", plan)
            self.assertNotIn("SaveCurrentGame", plan)

        for plan in (tree, menorah):
            self.assertIn("0xFB", plan)
            self.assertEqual(plan.count("PlanToJoyTwirlCW(ldwGameState::GetRandom(3) + 4)"), 2)
            self.assertEqual(plan.count("PlanToJump(10)"), 2)
            self.assertEqual(plan.count("PlanToJump(20)"), 2)
            self.assertIn("GetRandom(2) + 2", plan)
            self.assertIn("GetRandom(2) + 1", plan)
            self.assertIn("PlanToStopSound()", plan)
            self.assertIn("StartNewBehavior(villager)", plan)

        self.assertIn("for (int round = 0; round < 7; ++round)", dreidel)
        self.assertIn("GetRandom(100) > 49", dreidel)
        for sound in ("0x63", "0x108", "0x77", "0xBD"):
            self.assertIn(sound, dreidel)
        self.assertIn("static_cast<EBodyPosition>(0x12)", dreidel)
        self.assertIn("static_cast<EBodyPosition>(0x11)", dreidel)
        self.assertNotIn("PlanToStopSound()", dreidel)

    def test_ledger_labels_manual_and_autonomous_paths_separately(self):
        self.assertIn("when a person is manually dropped onto the Banner", self.ledger)
        self.assertIn("manually dropping Cake, Presents, or Balloons", self.ledger)
        self.assertRegex(
            self.ledger,
            re.compile(r"separate autonomous\s+`Maybe\.\.\.` callbacks"),
        )
        self.assertNotIn("Balloons, Presents, and Cake\nall delegate through `AllPeepsCelebratingBirthday`", self.ledger)


if __name__ == "__main__":
    unittest.main()
