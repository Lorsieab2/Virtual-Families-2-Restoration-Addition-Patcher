#!/usr/bin/env python3
"""Static native/source contract for holiday manual-drop and autonomy routes."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATCH_SOURCE = ROOT / "work" / "patch_mobile_furniture_pack.py"
IDA_DROP = ROOT / "outputs" / "B156-Mobile-Holiday-IDA" / "drop-dispatch.txt"
IDA_ASM = (
    ROOT
    / "outputs"
    / "mobile-reference-audit"
    / "xapk"
    / "apk"
    / "lib"
    / "x86"
    / "libVirtualFamilies2.so.asm"
)


def _between(text, start, end):
    begin = text.index(start)
    finish = text.index(end, begin + len(start))
    return text[begin:finish]


class MobileHolidayNativeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PATCH_SOURCE.read_text(encoding="utf-8")
        cls.drop = IDA_DROP.read_text(encoding="utf-8")
        cls.asm = IDA_ASM.read_text(encoding="utf-8")

    def test_native_drop_chain_binds_family_hotspots(self):
        for token in (
            "theMainScene::DropVillager",
            "CContentMap::GetHotSpot",
            "CHotSpot::Dispatch",
            "000F8E89",
        ):
            self.assertIn(token, self.drop)
        for token in (
            "001EBDB9: mov     [ecx+2E8h]",
            "001EBDCF: mov     [ecx+2F0h]",
            "001EBDE5: mov     [ecx+2F8h]",
        ):
            self.assertIn(token, self.drop)

    def test_native_family_handlers_call_household_manager(self):
        calls = (
            ("_ZN8CHotSpot8XmasTreeER9CVillager", "1A0h"),
            ("_ZN8CHotSpot7DreidelER9CVillager", "1A2h"),
            ("_ZN8CHotSpot7MenorahER9CVillager", "1A3h"),
        )
        for symbol, behavior in calls:
            start = self.asm.index(f"{symbol} proc near")
            end = self.asm.index(" endp", start)
            body = self.asm[start:end]
            self.assertIn(f"push    {behavior}", body)
            self.assertIn(
                "call    __ZN16CVillagerManager20MakeAllVillagersDoIt",
                body,
            )

    def test_pc_dispatch_is_stock_first_and_family_autonomy_free(self):
        builder = _between(
            self.source,
            "def patch_mobile_furniture_behavior_dispatch(manifest):",
            "def patch_mobile_furniture_behavior_macros(manifest):",
        )
        self.assertIn(
            'computer_drop_dispatch = "    if (HandleDropOnHotSpot(villager)) return true;"',
            builder,
        )
        self.assertLess(
            builder.index("HandleDropOnHotSpot(villager)"),
            builder.index("gVF2MobileFurnitureBehaviors == 0"),
        )

        helper = self.source.split("helper_source = r'''", 1)[1]
        helper = helper.split("'''", 1)[0]
        selector = _between(
            helper,
            "extern \"C\" bool __cdecl VF2TryStartMobileFurnitureAutonomous",
            "static bool VF2WeatherAllowsOutdoorFurniture",
        )
        for forbidden in (
            "VF2HandleMobileXmasTreeGroup",
            "VF2HandleMobileDreidelGroup",
            "VF2HandleMobileMenorahGroup",
            # 0x19D is deliberately absent from this list: FixingTreeDecorations
            # is now an enabled autonomous candidate, so forbidding it here
            # failed builds that correctly include it.
            "0x1A0",
            "0x1A2",
            "0x1A3",
        ):
            self.assertNotIn(forbidden, selector)
        for intended in (
            "VF2HandleMobileAdmiringXmasTree",
            "VF2HandleMobileAdultWaterXmasTree",
            "VF2HandleMobileKidBreakingTreeDecor",
        ):
            self.assertIn(intended, selector)


if __name__ == "__main__":
    unittest.main()
