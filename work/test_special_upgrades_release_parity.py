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
    0x133, 0x134, 0x132, 0x14C, 0x14B, 0x152,
    0x136, 0x137, 0x138,
    0x139, 0x13A, 0x13B,
    0x153, 0x154, 0x155, 0x156, 0x157, 0x158, 0x159,
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
            "DatingScene.obj",
            "VillagerManager.obj",
            "theMainScene.obj",
        ):
            shutil.copy2(
                patcher.SRC_OBJS / object_name,
                patcher.PATCHED / object_name,
            )

        cls.manifest = {}
        patcher.patch_marriage_candidate_reroll(cls.manifest)
        patcher.patch_same_sex_marriage(cls.manifest)
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

        self.assertEqual(
            visible["reversible_price_display"],
            {
                "hook": "?GetPrice@CInventoryManager@@QAEHW4EInventoryItem@@@Z + 0x3",
                "helper": "_VF2GetVisibleSpecialUpgradePrice",
                "active_price": 0,
                "inactive_price_source": "explicit item catalog price; mobile renovation styles use kVF2MobileRenovationPrices",
                "purchase_history_affects_inactive_price": False,
            },
        )
        self.assertEqual(
            {item_id: rows[item_id]["price"] for item_id in (0x117, 0x118, 0x119, 0x11A)},
            {0x117: 10000, 0x118: 10000, 0x119: 10000, 0x11A: 77777},
        )

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

        divorce = rows[0x14B]
        self.assertEqual(divorce["name"], "Divorce Spouse")
        self.assertEqual(divorce["icon_file"], "cheat_marriage_email.png")
        self.assertEqual(
            int(divorce["icon"], 16),
            patcher.visible_special_upgrade_icon_id_for(0x14B),
        )
        self.assertEqual(
            int(divorce["description_string"], 16),
            patcher.divorce_spouse_string_ids()[1],
        )
        force_email = rows[0x132]
        same_sex = rows[0x14C]
        reroll = rows[0x152]
        self.assertEqual(force_email["name"], "Force Marriage Email")
        self.assertEqual(same_sex["name"], "Enable Same-Sex Marriage")
        marriage_strings = {
            (row["item_id"], row["role"]): row["text"]
            for row in self.manifest["theStringManager"]["strings"]
            if row.get("item_id") in {"0x132", "0x14c"}
        }
        self.assertEqual(
            marriage_strings[("0x132", "long")],
            "Queues a normal base-game marriage proposal with native candidate rules.",
        )
        self.assertEqual(
            marriage_strings[("0x14c", "long")],
            "Enables same-sex marriage candidates. Buy again to disable this toggle.",
        )
        self.assertEqual(same_sex["icon_file"], "cheat_marriage_email.png")
        self.assertEqual(reroll["name"], "Allow Reroll of Marriage Candidates")
        self.assertEqual(reroll["price"], 0)
        self.assertEqual(reroll["icon_file"], "cheat_marriage_email.png")
        self.assertEqual(
            int(reroll["icon"], 16),
            patcher.visible_special_upgrade_icon_id_for(0x152),
        )
        reroll_contract = self.manifest["MarriageCandidateReroll"]
        self.assertEqual(reroll_contract["cheat_upgrade"]["item_id"], "0x152")
        self.assertEqual(reroll_contract["cheat_upgrade"]["catalog_price"], 0)
        # Persists at InventoryManager + itemId + 0x2A3 (the native save
        # payload) instead of a free-standing custom PE section that native
        # SaveCurrentGame()/Load() never restore.
        self.assertEqual(
            reroll_contract["runtime_flag"]["storage"],
            "InventoryManager + 0x152 + 0x2A3 (same persisted-byte convention as mobile renovations/Bathroom 2)",
        )
        self.assertEqual(reroll_contract["reject"]["hook_offset"], "+0x85")
        self.assertIn("GeneratePeepCandidate", reroll_contract["reject"]["active_call"])
        self.assertIn("GeneratePeepCandidate", reroll_contract["reject"]["active_lifecycle"])
        # Both the active and inactive paths rejoin the untouched native shared
        # tail at HandleMessage +0x8C (there is no separate +0xAC continuation).
        self.assertIn("+0x8C", reroll_contract["reject"]["rejoin"])
        # Accept keeps the untouched stock path, so the reroll toggle is not
        # cleared or duplicated when a candidate is accepted.
        self.assertIn("byte-identical", reroll_contract["accept"])
        self.assertEqual(
            int(same_sex["description_string"], 16),
            patcher.same_sex_marriage_string_ids()[1],
        )
        self.assertNotEqual(force_email["icon"], same_sex["icon"])
        self.assertNotEqual(same_sex["icon"], divorce["icon"])
        item_ids = [item["item_id"] for item in patcher.CHEAT_UPGRADE_ITEMS]
        force_email_index = item_ids.index(0x132)
        self.assertEqual(item_ids[force_email_index + 1 : force_email_index + 4], [0x14C, 0x14B, 0x152])

        self.assertIn(
            "static int VF2VisibleSpecialUpgradeIconFrame(int itemId)",
            self.helper,
        )
        # Regression guard: the marriage toggles must NOT swap their store
        # icon to the generic owned/checkmark artwork when active. The icon
        # resolver keeps their envelope frame whether or not the toggle is on.
        self.assertNotIn(
            "if (itemId == 0x14c &&\n        VF2SameSexMarriageToggleActive())",
            self.helper,
        )
        self.assertNotIn(
            "if (itemId == 0x152 &&\n        gVF2AllowMarriageCandidateReroll != 0)",
            self.helper,
        )
        # No row swaps to the checkmark image anymore (0x162=354 / old 0x166=358).
        self.assertNotIn("return 354;", self.helper)
        self.assertNotIn("return 358;", self.helper)
        self.assertIn("case 0x14B: return 37;", self.helper)
        self.assertIn("case 0x14C: return 38;", self.helper)
        self.assertIn("case 0x152: return 39;", self.helper)
        self.assertIn("VF2CheatToggleActiveByte(0x152) != 0", self.helper)
        self.assertNotIn(
            "int index = itemId - kVF2VisibleSpecialUpgradeFirstItem",
            self.helper,
        )
        draw_helper = (
            patcher.PATCHED / "vf2_generation_locks.cpp"
        ).read_text(encoding="ascii")
        self.assertIn("case 0x14B: frame = 37; break;", draw_helper)
        self.assertIn("case 0x14C: frame = 38; break;", draw_helper)
        self.assertNotIn("int frame = item - 0x117;", draw_helper)

        divorce_strings = [
            row for row in self.manifest["theStringManager"]["strings"]
            if row.get("item_id") == "0x14b"
        ]
        self.assertEqual(
            {(row["pc_string_id"], row["text"]) for row in divorce_strings},
            {
                ("0xee1", "Divorce Spouse"),
                (
                    "0xee2",
                    "WARNING: Permanently removes spouse from the Family Tree and House!",
                ),
            },
        )
        divorce_contract = self.manifest["DivorceSpouse"]
        self.assertEqual(divorce_contract["store_item_id"], "0x14b")
        self.assertEqual(
            divorce_contract["catalog_price"],
            patcher.DIVORCE_SPOUSE_CATALOG_PRICE,
        )
        self.assertEqual(
            divorce_contract["price_semantics"],
            "explicit catalog price while a valid current spouse exists; unavailable otherwise",
        )
        self.assertEqual(
            divorce_contract["owned_state"],
            "never active or owned; generic checkmark/active renderer is bypassed",
        )
        self.assertEqual(
            divorce_contract["target_slot"]["manager_slot_offset"],
            "+0x104",
        )
        self.assertEqual(
            divorce_contract["availability"],
            "zero unless the current second-parent slot is present and its manager slot is in 0..29, exists as an active non-away resident, matches CVillager+0x1BB48, and has living health",
        )
        self.assertEqual(divorce_contract["native_evidence"], {
            "living_health_field": "CVillager+0x6B00",
            "detach_all_symbol": "?DetachAll@CVillager@@QAEXXZ",
            "reset_symbol": "?Reset@CVillager@@QAEXXZ",
            "second_adult_range": "exactly 0xD8 bytes at current-family F+0xDC",
            "update_symbol": "?UpdateCurrentFamilyRecord@CFamilyTree@@QAEXXZ",
        })
        for evidence in (
            "CVillager::DetachAll",
            "CVillager::Reset",
            "zero exactly 0xD8 bytes",
            "CFamilyTree::UpdateCurrentFamilyRecord",
            "common SaveCurrentGame path",
        ):
            self.assertIn(evidence, divorce_contract["apply"])
        for forbidden in ("SetHealth", "OldAge", "ReportDeath", "retain"):
            self.assertNotIn(forbidden, str(divorce_contract))
        self.assertEqual(
            divorce_contract["warning"],
            "WARNING: Permanently removes spouse from the Family Tree and House!",
        )

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

    def test_divorce_is_priced_available_and_never_owned(self):
        divorce_price = self._function_block(
            self.helper,
            'extern "C" int __cdecl VF2GetVisibleSpecialUpgradePrice',
            'extern "C" void __cdecl VF2ApplyVisibleSpecialUpgrade',
        )
        self.assertIn(
            "if (itemId == 0x14B) {\n"
            "        return VF2DivorceSpouseAvailable()\n"
            "            ? 0\n"
            "            : -1;",
            divorce_price,
        )

        active_state = self._function_block(
            self.helper,
            "static bool VF2B150UpgradeIsActive",
            'extern "C" int __cdecl VF2GetB150UpgradePrice',
        )
        self.assertIn(
            "if (itemId == 0x14b) {\n"
            "        // Divorce Spouse is a one-shot action. Never let purchase history\n"
            "        // classify it as an owned/checkmarked Special Upgrade.\n"
            "        return false;\n"
            "    }",
            active_state,
        )

        icon = self._function_block(
            self.helper,
            "static int VF2GetVisibleSpecialUpgradeIconImage",
            "static int VF2GetMobileRenovationIconImage",
        )
        # Divorce Spouse (0x14B) no longer needs a resolver-specific block:
        # every row, including all marriage upgrades, resolves through its icon
        # frame (case 0x14B -> 37) and never swaps to the checkmark image.
        self.assertIn("int index = VF2VisibleSpecialUpgradeIconFrame(itemId);", icon)
        self.assertNotIn("return 354;", icon)
        self.assertNotIn("VF2SameSexMarriageToggleActive()", icon)
        self.assertNotIn("kVF2VisibleSpecialUpgradeIconImageBase + 37;", icon)

        availability = self._function_block(
            self.helper,
            'extern "C" int __cdecl VF2GetOutfitStoreNumAvailable',
            'extern "C" bool __cdecl VF2PurchaseOutfitStoreItem',
        )
        self.assertIn(
            "if (itemId == 0x14B) {\n"
            "        return VF2DivorceSpouseAvailable() ? 1 : 0;\n"
            "    }",
            availability,
        )

        apply_case = self._case_block(self.helper, 0x14B)
        self.assertIn("if (!VF2DivorceSpouse()) return;", apply_case)
        divorce_case = apply_case.split("case 0x14B:", 1)[1].split("default:", 1)[0]
        self.assertNotIn("InventoryManager.TakeOne", divorce_case)
        self.assertNotIn("InventoryManager.ReturnOne", divorce_case)
        self.assertIn("theGameState::Get()->SaveCurrentGame();", self.helper)

        divorce_helpers = self._function_block(
            self.helper,
            "static CVillager *VF2CurrentGenerationSecondAdult",
            "static bool VF2IsSameSexMarriage",
        )
        self.assertIn("FamilyTree.GetCurrentFamily()", divorce_helpers)
        self.assertIn("family + 0x104", divorce_helpers)
        self.assertIn("managerSlot < 0 || managerSlot >= 30", divorce_helpers)
        self.assertIn("spouse->DetachAll();", divorce_helpers)
        self.assertIn("spouse->Reset();", divorce_helpers)
        self.assertIn("family + 0xDC", divorce_helpers)
        self.assertIn("FamilyTree.UpdateCurrentFamilyRecord();", divorce_helpers)
        self.assertNotIn("for (int generation", divorce_helpers)

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
        self.assertIn("CollectableItem.SpawnTrashInHouse(10);", fill_house)
        self.assertIn("CollectableItem.SpawnStainInHouse(10);", fill_house)
        self.assertIn("CollectableItem.SpawnSockInHouse(10);", fill_house)

        fill_garden = self._case_block(self.helper, 0x130)
        self.assertIn("CollectableItem.SpawnWeedsInYard(30);", fill_garden)

        max_sock = self._case_block(self.helper, 0x133)
        self.assertNotIn(
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
        self.assertNotIn("VF2MarriageEmailUnavailable", price)
        self.assertNotIn("0x7FFFFFFF", price)

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
        apply_source = self.helper[apply_start:]
        marriage = self._case_block(self.helper[apply_start:], 0x132)
        self.assertIn("if (VF2MarriageEmailUnavailable())", marriage)
        self.assertIn("VF2QueueMarriageProposal();", marriage)
        self.assertNotIn("kVF2CheatMarriageProposalActive", marriage)
        same_sex_toggle = self._case_block(self.helper[apply_start:], 0x14C)
        self.assertIn("VF2SameSexMarriageToggleActive()", same_sex_toggle)
        # Persists at InventoryManager + 0x14C + 0x2A3 instead of a
        # free-standing custom PE section that native
        # SaveCurrentGame()/Load() never restore.
        self.assertIn(
            "*VF2CheatToggleActiveByte(0x14C) = VF2SameSexMarriageToggleActive() ? 0 : 1;",
            same_sex_toggle,
        )
        self.assertNotIn("InventoryManager.TakeOne((EInventoryItem)itemId);", same_sex_toggle)
        self.assertNotIn("InventoryManager.ReturnOne((EInventoryItem)itemId);", same_sex_toggle)
        same_sex = self._function_block(
            self.helper,
            "static bool VF2IsSameSexMarriage()",
            "extern \"C\" void __cdecl VF2StoreTryForBabyCooldownMaybe",
        )
        self.assertIn("VF2SameSexMarriageToggleActive()", same_sex)
        self.assertIn("extern \"C\" int __fastcall VF2ClassifyRomanticSpouseDrop", same_sex)
        self.assertIn("static bool VF2IsBehaviorSixChildPrivateTimeMarriage()", same_sex)
        self.assertIn("if (firstGender == secondGender) return false;", same_sex)
        self.assertIn("FamilyTree.GetCurrentFamily()", same_sex)
        self.assertIn("family + 0x1B4", same_sex)
        self.assertIn(">= 6", same_sex)
        # The opposite-sex drop route gates on Behavior Patches alone: the
        # classifier only runs behind the native no-room gate, so the family
        # is already full. It must not re-read the +0x1B4 count there.
        self.assertIn("return kVF2IncludeBehaviorGoals ? 1 : 0;", same_sex)
        self.assertNotIn("return VF2IsBehaviorSixChildPrivateTimeMarriage() ? 1 : 0;", same_sex)
        self.assertIn("extern \"C\" bool __cdecl VF2SkipSameSexTryToMakeBaby()", same_sex)
        self.assertIn("return VF2IsSameSexMarriage() ||", same_sex)
        self.assertIn("VF2IsBehaviorSixChildPrivateTimeMarriage();", same_sex)
        self.assertIn("VF2IsSameSexMarriage() ||\n        VF2IsBehaviorSixChildPrivateTimeMarriage()", same_sex)
        self.assertNotIn("VF2MaybeAddCheatMarriageExit", self.helper)
        self.assertNotIn("VF2HandleCheatMarriageProposalExit", self.helper)
        self.assertIn("eEmailMessageMarriageProposal", self.helper)
        self.assertIn("eEmailMessageMarriageProposal = 2", self.helper)

        divorce = self._case_block(self.helper[apply_start:], 0x14B)
        self.assertIn("if (!VF2DivorceSpouse()) return;", divorce)
        self.assertIn("theGameState::Get()->SaveCurrentGame();", apply_source)

        availability = self._function_block(
            self.helper,
            "extern \"C\" int __cdecl VF2GetOutfitStoreNumAvailable",
            "extern \"C\" bool __cdecl VF2PurchaseOutfitStoreItem",
        )
        self.assertIn(
            "if (itemId == 0x14B) {\n"
            "        return VF2DivorceSpouseAvailable() ? 1 : 0;\n"
            "    }",
            availability,
        )
        divorce_helpers = self._function_block(
            self.helper,
            "static CVillager *VF2CurrentGenerationSecondAdult",
            "static bool VF2IsSameSexMarriage",
        )
        for evidence in (
            "FamilyTree.GetCurrentFamily()",
            "family[0xF6]",
            "family + 0x104",
            "managerSlot < 0 || managerSlot >= 30",
            "VillagerManager.VillagerExists(managerSlot, false)",
            "resident + 0x1BB48) != managerSlot",
            "resident + 0x6B00) <= 0",
            "VillagerManager.GetVillagerInFocus() == spouse",
            "VillagerManager.SetNoFocus();",
            "spouse->DetachAll();",
            "spouse->Reset();",
            "unsigned char *secondAdult = family + 0xDC;",
            "for (int offset = 0; offset < 0xD8; ++offset)",
            "secondAdult[offset] = 0;",
            "FamilyTree.UpdateCurrentFamilyRecord();",
        ):
            self.assertIn(evidence, divorce_helpers)
        for forbidden in (
            "SetHealth(",
            "eCauseOfDeath",
            "ReportDeath",
            "CountSurvivingChildren",
            "CanStartNextGeneration",
            "StartNextGeneration",
            "VF2PersistentCheatAndPurchaseMask",
            "for (int generation",
            "GetFamilyRecord(",
            "VF2MarriageAdult",
        ):
            self.assertNotIn(forbidden, divorce_helpers)

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
        native_cell = self._function_block(
            self.helper,
            "static bool VF2DrawAddedStoreIconNativeCell",
            'extern "C" bool __cdecl VF2DrawOutfitStoreIconPoint',
        )
        self.assertIn("GetCellRect(0, 0, cell);", native_cell)
        self.assertIn(
            "DrawTinted(grid, drawX + 2, drawY + 2, 0, kVF2Black, 0.4f, 1.0f)",
            native_cell,
        )
        self.assertIn(
            "DrawTinted(grid, drawX + 4, drawY + 4, 0, kVF2Black, 0.4f, 1.0f)",
            native_cell,
        )
        self.assertIn("window->Draw(grid, drawX, drawY, 0);", native_cell)
        self.assertEqual(
            self.helper.count("static const ldwColor kVF2Black = { 0xFF000000u };"),
            1,
        )
        self.assertNotIn("cLdwBlack", self.helper)
        self.assertNotIn("graphics->Draw", native_cell)
        self.assertIn(
            "return VF2DrawAddedStoreIconNativeCell(x, y, itemId, selected);",
            draw_point,
        )
        self.assertIn("return VF2DrawOutfitStoreIconPoint(", draw_rect)
        self.assertIn("left + (right - left) / 2", draw_rect)
        self.assertIn("top + (bottom - top) / 2", draw_rect)

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
