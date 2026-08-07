#!/usr/bin/env python3
import hashlib
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher
from coff_patch import CoffObject


EXPECTED_CHEAT_IDS = (
    0x11B, 0x11D, 0x11E, 0x11F,
    0x11C, 0x120, 0x121, 0x122,
    0x123, 0x124, 0x12E, 0x125, 0x126, 0x127,
    0x128, 0x129, 0x12A, 0x12C,
    0x12B, 0x12D,
    0x12F, 0x135, 0x130, 0x131,
    0x133, 0x134, 0x132,
    0x136, 0x137, 0x138,
    0x139, 0x13A, 0x13B,
)
LATE_CHEAT_IDS = tuple(range(0x12E, 0x13C))
WEATHER_REFUSAL_TEXT = "Don't like the weather!"


class SpecialUpgradesReleaseParityTests(unittest.TestCase):
    """Static release-contract checks for the cheat-enabled Special Upgrades overlay."""

    @classmethod
    def setUpClass(cls):
        cls._old_patched = patcher.PATCHED
        cls._old_cheats = patcher.ENABLE_CHEAT_UPGRADES
        cls._old_renovations = patcher.ENABLE_MOBILE_RENOVATIONS
        cls._old_out = patcher.OUT
        cls._tmp = tempfile.TemporaryDirectory()
        patcher.PATCHED = Path(cls._tmp.name)
        patcher.OUT = Path(cls._tmp.name) / "out"
        patcher.ENABLE_CHEAT_UPGRADES = True
        patcher.ENABLE_MOBILE_RENOVATIONS = False

        for object_name in (
            "InventoryManager.obj",
            "ScrollingStoreScene.obj",
            "theStringManager.obj",
        ):
            shutil.copy2(
                patcher.SRC_OBJS / object_name,
                patcher.PATCHED / object_name,
            )

        cls.manifest = {}
        patcher.patch_visible_special_upgrades(cls.manifest)
        patcher.patch_inventory_manager(cls.manifest)
        patcher.patch_scrolling_store_scene(cls.manifest)
        patcher.write_outfit_store_helpers(cls.manifest)
        patcher.patch_string_manager(cls.manifest)
        patcher.sync_visible_special_upgrade_icon_art(cls.manifest)
        cls.helper = (
            patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
        ).read_text(encoding="ascii")

    @classmethod
    def tearDownClass(cls):
        patcher.PATCHED = cls._old_patched
        patcher.ENABLE_CHEAT_UPGRADES = cls._old_cheats
        patcher.ENABLE_MOBILE_RENOVATIONS = cls._old_renovations
        patcher.OUT = cls._old_out
        cls._tmp.cleanup()

    @staticmethod
    def _case_block(source, item_id):
        marker = f"case 0x{item_id:X}:"
        start = source.index(marker)
        next_case = source.find("\n    case ", start + len(marker))
        return source[start:] if next_case < 0 else source[start:next_case]

    @staticmethod
    def _function_block(source, start_marker, end_marker):
        start = source.index(start_marker)
        end = source.index(end_marker, start + len(start_marker))
        return source[start:end]

    def test_cheat_enabled_manifest_has_distinct_concrete_late_icons(self):
        visible = self.manifest["VisibleSpecialUpgrades"]
        rows = {int(row["item_id"], 16): row for row in visible["added_items"]}
        cheat_ids = tuple(item["item_id"] for item in patcher.CHEAT_UPGRADE_ITEMS)

        self.assertEqual(cheat_ids, EXPECTED_CHEAT_IDS)
        self.assertEqual(len(set(cheat_ids)), len(cheat_ids))
        self.assertTrue(set(cheat_ids).issubset(rows))
        self.assertEqual(
            visible["new_count"],
            6 + len(patcher.MOBILE_SPECIAL_UPGRADE_ITEM_IDS) + len(EXPECTED_CHEAT_IDS),
        )
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES, {})
        self.assertEqual(
            self.manifest["outfit_store_helpers"][
                "visible_special_upgrade_icon_aliases"
            ],
            {},
        )

        late_icons = []
        late_icon_files = []
        for item_id in LATE_CHEAT_IDS:
            self.assertIn(item_id, rows)
            row = rows[item_id]
            self.assertTrue(row["icon_file"])
            self.assertIn(row["icon_file"], patcher.VISIBLE_SPECIAL_UPGRADE_ICON_FILES.values())
            self.assertEqual(
                int(row["icon"], 16),
                patcher.visible_special_upgrade_icon_id_for(item_id),
            )
            self.assertNotEqual(row["icon"], rows[0x124]["icon"])
            late_icons.append(row["icon"])
            late_icon_files.append(row["icon_file"])
        self.assertEqual(len(late_icons), len(set(late_icons)))
        self.assertEqual(len(late_icon_files), len(set(late_icon_files)))

        art = self.manifest["visible_special_upgrade_icon_art"]
        self.assertEqual(art["status"], "available")
        self.assertEqual(art["missing"], [])
        art_rows = {int(row["item_id"], 16): row for row in art["entries"]}
        self.assertEqual(
            set(art_rows),
            set(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_FILES),
        )
        for item_id, expected_path in patcher.VISIBLE_SPECIAL_UPGRADE_ICON_FILES.items():
            art_row = art_rows[item_id]
            self.assertEqual(
                art_row["image_id"],
                hex(patcher.visible_special_upgrade_icon_id_for(item_id)),
            )
            self.assertEqual(art_row["path"], expected_path)
            self.assertEqual(art_row["path"], rows[item_id]["icon_file"])
            self.assertTrue(Path(art_row["source"]).is_file())
            self.assertEqual(art_row["size"], [patcher.VISIBLE_SPECIAL_UPGRADE_ICON_CELL_SIZE] * 2)
            self.assertNotEqual(art_row["status"], "missing")

        late_source_hashes = {
            hashlib.sha256(Path(art_rows[item_id]["source"]).read_bytes()).hexdigest()
            for item_id in LATE_CHEAT_IDS
        }
        self.assertEqual(len(late_source_hashes), len(LATE_CHEAT_IDS))

    def test_every_cheat_row_reaches_purchase_dispatch_effect_and_save(self):
        cheat_ids = EXPECTED_CHEAT_IDS
        apply_start = self.helper.index(
            "extern \"C\" void __cdecl VF2ApplyVisibleSpecialUpgrade"
        )
        apply_source = self.helper[apply_start:]
        for item_id in cheat_ids:
            self.assertIn(f"case 0x{item_id:X}:", apply_source)

        self.assertIn(
            "default:\n        return;\n    }\n\n    theGameState::Get()->SaveCurrentGame();",
            apply_source,
        )

        visible_contract = self.manifest["ScrollingStoreScene"][
            "visible_special_upgrades"
        ]
        self.assertEqual(
            visible_contract["purchase_hook"],
            "?HandlePurchaseItem@CScrollingStoreScene@@AAEXXZ + 0x1AD",
        )

        obj = CoffObject(patcher.PATCHED / "ScrollingStoreScene.obj")
        purchase = obj.symbol("?HandlePurchaseItem@CScrollingStoreScene@@AAEXXZ")
        section = obj.section(purchase.section)
        data = bytes(
            obj.buf[
                section.raw_ptr + purchase.value :
                section.raw_ptr + purchase.value + 0x398
            ]
        )
        max_visible_index = max(EXPECTED_CHEAT_IDS) - patcher.MOBILE_SPECIAL_UPGRADE_ITEM_IDS[0]
        self.assertIn(
            b"\x2D\x17\x01\x00\x00\x83\xF8"
            + bytes([max_visible_index])
            + b"\x77\x0E\x51",
            data,
        )

        targets = {
            vaddr - purchase.value: obj.symbol_by_index[symbol_index].name
            for vaddr, symbol_index, _rtype in (
                struct.unpack_from(
                    "<IIH", obj.buf, section.reloc_ptr + index * 10
                )
                for index in range(section.nreloc)
            )
            if purchase.value <= vaddr < purchase.value + 0x398
        }
        self.assertEqual(
            targets[0x1F1],
            "_VF2ApplyVisibleSpecialUpgrade",
        )

        inventory = self.manifest["InventoryManager"]["outfit_store_additions"]
        getter_helpers = {hook["helper"] for hook in inventory["getter_hooks"]}
        draw_helpers = {hook["helper"] for hook in inventory["draw_hooks"]}
        self.assertIn("_VF2GetOutfitStoreNumAvailable", getter_helpers)
        self.assertIn("_VF2GetOutfitStorePrice", getter_helpers)
        self.assertIn("_VF2DrawOutfitStoreIconPoint", draw_helpers)
        self.assertIn("_VF2DrawOutfitStoreIconRect", draw_helpers)

        inventory_obj = CoffObject(patcher.PATCHED / "InventoryManager.obj")
        relocation_targets = {
            inventory_obj.symbol_by_index[symbol_index].name
            for section in inventory_obj.sections
            if section.reloc_ptr
            for index in range(section.nreloc)
            for _vaddr, symbol_index, _rtype in (
                struct.unpack_from(
                    "<IIH", inventory_obj.buf, section.reloc_ptr + index * 10
                ),
            )
        }
        self.assertTrue(
            {
                "_VF2GetOutfitStoreNumAvailable",
                "_VF2GetOutfitStorePrice",
                "_VF2DrawOutfitStoreIconPoint",
                "_VF2DrawOutfitStoreIconRect",
            }.issubset(relocation_targets)
        )

    def test_named_effects_and_marriage_refusal_are_fail_closed(self):
        fill_house = self._case_block(self.helper, 0x12F)
        self.assertIn("CollectableItem.SpawnTrashInHouse(1);", fill_house)
        self.assertIn("CollectableItem.SpawnStainInHouse(1);", fill_house)
        self.assertIn("CollectableItem.SpawnSockInHouse(1);", fill_house)

        fill_garden = self._case_block(self.helper, 0x130)
        self.assertIn("CollectableItem.SpawnWeedsInYard(30);", fill_garden)

        max_sock = self._case_block(self.helper, 0x133)
        self.assertIn(
            "CollectableItem.SpawnSockInHouse(kVF2MaximumSockPileCount);",
            max_sock,
        )
        self.assertIn("VF2SetSockPileCount(kVF2MaximumSockPileCount);", max_sock)
        self.assertIn("static const int kVF2MaximumSockPileCount = 0x7FFFFFFF;", self.helper)

        availability = self._function_block(
            self.helper,
            "extern \"C\" int __cdecl VF2GetOutfitStoreNumAvailable",
            "extern \"C\" bool __cdecl VF2PurchaseOutfitStoreItem",
        )
        self.assertIn(
            "if (itemId == 0x132 && VF2MarriageEmailUnavailable()) {\n"
            "        // A second resident adult means the stock proposal path has no valid\n"
            "        // candidate state.  Hide the purchase instead of queueing the email\n"
            "        // into the crash-prone path.\n"
            "        return 0;\n"
            "    }",
            availability,
        )
        price = self._function_block(
            self.helper,
            "extern \"C\" int __cdecl VF2GetVisibleSpecialUpgradePrice",
            "extern \"C\" void __cdecl VF2ApplyVisibleSpecialUpgrade",
        )
        self.assertIn("return VF2MarriageEmailUnavailable() ? 0x7FFFFFFF : -1;", price)

        adult = self._function_block(
            self.helper,
            "static bool VF2MarriageAdult(CVillager *villager)",
            "static CVillager *VF2VillagerByPersistentId",
        )
        self.assertIn("raw[0x1BB84] == 0", adult)
        self.assertIn("raw[0x1BB88] != 0", adult)
        self.assertIn("*(int *)(raw + 0x6B00) <= 0", adult)
        self.assertIn("CareerType() != 0", adult)
        pair = self._function_block(
            self.helper,
            "static bool VF2MarriagePair(CVillager *&first, CVillager *&second)",
            "static bool VF2MarriageEmailUnavailable",
        )
        self.assertIn("for (int index = 0; index < 30; ++index)", pair)
        self.assertIn("if (first && second && first != second) return true;", pair)

        apply_start = self.helper.index(
            "extern \"C\" void __cdecl VF2ApplyVisibleSpecialUpgrade"
        )
        marriage = self._case_block(self.helper[apply_start:], 0x132)
        self.assertIn("if (VF2MarriageEmailUnavailable())", marriage)
        self.assertIn("theGameState::Get()->QueueEmailMessage(", marriage)
        self.assertIn("eEmailMessageMarriageProposal", marriage)
        self.assertIn("eEmailMessageMarriageProposal = 2", self.helper)

        draw_point = self._function_block(
            self.helper,
            'extern "C" bool __cdecl VF2DrawOutfitStoreIconPoint',
            'extern "C" bool __cdecl VF2DrawOutfitStoreIconRect',
        )
        draw_rect = self.helper[
            self.helper.index(
                'extern "C" bool __cdecl VF2DrawOutfitStoreIconRect'
            ):
        ]
        for draw_hook in (draw_point, draw_rect):
            self.assertIn("int image = VF2GetAddedStoreIconImage(itemId);", draw_hook)
            self.assertIn("if (image < 0) return false;", draw_hook)
            self.assertIn("graphics->Draw", draw_hook)

    def test_weather_refusal_is_not_a_catalog_row_or_cheat_string(self):
        catalog_text = [
            text
            for item in patcher.CHEAT_UPGRADE_ITEMS
            for text in (item["name"], item["description"])
        ]
        self.assertNotIn(WEATHER_REFUSAL_TEXT, catalog_text)
        renovation_text = [
            text
            for style in patcher.MOBILE_RENOVATION_STYLE_CATALOG
            for text in (style["name"], style["short"], style["long"])
        ]
        self.assertNotIn(WEATHER_REFUSAL_TEXT, renovation_text)
        visible_text = [
            text
            for row in self.manifest["theStringManager"]["strings"]
            if row.get("source") in {"visible special upgrade", "cheat upgrade entry"}
            for text in [row.get("text")]
        ]
        self.assertNotIn(WEATHER_REFUSAL_TEXT, visible_text)

        weather_id = patcher.mobile_lounger_bad_weather_string_id()
        cheat_string_ids = {
            string_id
            for index in range(len(EXPECTED_CHEAT_IDS))
            for string_id in patcher.cheat_upgrade_string_ids_for_entry(index)
        }
        self.assertNotIn(weather_id, cheat_string_ids)
        self.assertNotIn(
            weather_id,
            {
                patcher.visible_special_upgrade_desc_id_for(index)
                for index in range(patcher.SPECIAL_UPGRADE_DESCRIPTION_COUNT)
            },
        )
        renovation_string_ids = {
            string_id
            for index in range(patcher.MOBILE_RENOVATION_IMAGE_COUNT)
            for string_id in patcher.mobile_renovation_string_ids_for(index)
        }
        self.assertNotIn(weather_id, renovation_string_ids)

        strings = self.manifest["theStringManager"]["strings"]
        weather_rows = [
            row for row in strings if row.get("text") == WEATHER_REFUSAL_TEXT
        ]
        self.assertEqual(len(weather_rows), 1)
        self.assertEqual(
            weather_rows[0]["source"],
            "mobile lounge chair translated refusal",
        )
        self.assertEqual(weather_rows[0]["pc_string_id"], hex(weather_id))
        self.assertFalse(
            any(
                row is not weather_rows[0]
                and row.get("pc_string_id") == hex(weather_id)
                for row in strings
            )
        )
        self.assertFalse(
            any(
                row.get("source") == "cheat upgrade entry"
                and row.get("text") == WEATHER_REFUSAL_TEXT
                for row in strings
            )
        )


if __name__ == "__main__":
    unittest.main()
