#!/usr/bin/env python3
import ast
import copy
import hashlib
import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher
from coff_patch import CoffObject


def valid_vf3_tv_manifest():
    records = []
    for item in patcher.VF3_TV_ITEMS:
        frame0_label, frame1_label = item["animation_labels"]
        records.append(
            {
                "item": item["short_description"],
                "item_id": hex(item["item_id"]),
                "frame0_enum": hex(patcher.VF3_TV_FLOATING_ANIMS[frame0_label]["enum"]),
                "frame1_enum": hex(patcher.VF3_TV_FLOATING_ANIMS[frame1_label]["enum"]),
                "frame0_label": frame0_label,
                "frame1_label": frame1_label,
                "offsets": {"x": [0, 0, 0, 0], "y": [0, 0, 0, 0]},
            }
        )
    descriptors = []
    floating_entries = []
    for label, info in patcher.VF3_TV_FLOATING_ANIMS.items():
        runtime = patcher.VF3_TV_RUNTIME_ANIMATION_NAMES[label]
        descriptors.append(
            {
                "label": label,
                "floating_anim_enum": hex(info["enum"]),
                "path": runtime,
                "grid": [6, 3],
            }
        )
        floating_entries.append(
            {
                "label": label,
                "enum": hex(info["enum"]),
                "runtime_name": runtime,
                "frames": 18,
            }
        )
    return {
        "FurnitureManager": {"vf3_tv_animation_records": records},
        "theGraphicsManager": {
            "vf3_tv_floating_animation_images": {
                "descriptors": descriptors,
            }
        },
        "FloatingAnim": {"private_vf3_tv_entries": floating_entries},
        "vf3_tv_animation_sheets": {"missing": []},
    }


def valid_vf3_tv_behavior_manifest():
    return {
        "FurnitureManager": {
            "new_item_max_offset": hex(patcher.max_item_offset()),
            "load_fmap_range_patch": {
                "function": "CFurnitureManager::LoadFmap",
                "old_max_offset": hex(0xFB),
                "new_max_offset": hex(patcher.max_item_offset()),
                "offset": hex(0x1E),
            },
            "vf3_tv_behavior_contracts": [
                {
                    "item": item["short_description"],
                    "item_id": hex(item["item_id"]),
                    "donor_item": hex(item["donor"]),
                    "donor_behavior": "base flat-screen TV",
                    "item_type": 5,
                    "verified": "all non-identity, non-store, non-animation fields match donor 0x1F3",
                }
                for item in patcher.VF3_TV_ITEMS
            ],
        },
        "vf3_tv_fmaps": {
            "generated": [
                {
                    "item": item["short_description"],
                    "path": f"Assets/{item['name']}.png.fmap",
                    "grid": [13, 14],
                    "cell_values": [hex(0x003C0001)],
                }
                for item in patcher.VF3_TV_ITEMS
            ],
            "issues": [],
        },
    }


def valid_invisible_hammock_manifest():
    return {
        "FurnitureManager": {
            "invisible_hammock_behavior_contracts": [
                {
                    "item": "Invisible Hammock",
                    "item_id": "0x30c",
                    "donor_item": "0x1e1",
                    "donor_behavior": "base HammockStd",
                    "item_type": 5,
                    "verified": "all non-identity, non-store, non-string fields match donor 0x1E1",
                }
            ],
        },
        "invisible_hammock_drop_action": {
            "status": "stock hammock drop gate accepts base or invisible hammock",
            "base_item": "0x1E1",
            "added_item": "0x30C",
            "native_behavior": "eBehavior_LieInHammockNoLeadIn (0x24)",
            "base_hammock_modified": False,
            "hotspot_modified": True,
            "matches_base_hammock_behavior": True,
        },
        "clickable_added_furniture": {
            "items": [
                {
                    "item": "InvisibleHammock",
                    "item_id": "0x30c",
                    "donor_item": "0x1e1",
                }
            ]
        },
        "behavior_assets": {
            "invisible_outdoor_fmap_donors": [
                {
                    "target": "InvisibleHammock.png.fmap",
                    "donor": "HammockStd.png.fmap",
                    "source": "Assets/HammockStd.png.fmap",
                    "bytes": 1,
                }
            ],
            "missing": [],
        },
    }


def valid_invisible_kids_table_manifest():
    return {
        "FurnitureManager": {
            "invisible_kids_table_behavior_contracts": [
                {
                    "item": "Invisible Kids Table with Chairs",
                    "item_id": "0x321",
                    "donor_item": "0x1ce",
                    "donor_behavior": "base KidsTableAndChairsStd",
                    "item_type": 5,
                    "native_behavior": "CBehavior::ChildrenPlayAtKidsTable (0x130)",
                    "verified": "all non-identity, non-store, non-string fields match donor 0x1CE",
                }
            ],
        },
        "clickable_added_furniture": {
            "items": [
                {
                    "item": "InvisibleKidsTableAndChairs",
                    "item_id": "0x321",
                    "donor_item": "0x1ce",
                }
            ]
        },
        "behavior_assets": {
            "invisible_transparent_fmap_donors": [
                {
                    "target": "InvisibleKidsTableAndChairs.png.fmap",
                    "donor": "KidsTableAndChairsStd.png.fmap",
                    "source": "Assets/KidsTableAndChairsStd.png.fmap",
                    "bytes": 1,
                }
            ],
            "missing": [],
        },
    }


class MobileIslandEventTextTests(unittest.TestCase):
    def test_meteorite_followup_uses_short_dialog_title(self):
        events = {event["name"]: event for event in patcher.load_mobile_island_events()}

        meteorite = events["MeteoriteFallsInYard2"]
        title = next(row["text"] for row in meteorite["strings"] if row["kind"] == "Title")

        self.assertEqual(title, "Meteorite Fragments")
        self.assertLess(len(title), 40)
        self.assertNotIn("scientist is at the door", title)

    def test_metallic_knocking_result_spacing_is_normalized(self):
        events = {event["name"]: event for event in patcher.load_mobile_island_events()}
        result = next(row["text"] for row in events["MetallicKnockingOnDoor"]["strings"] if row["kind"] == "ResultA")

        self.assertIn('"Signal lost. Must seek shelter". You open', result)
        self.assertNotIn('".You', result)


class GenerationLockTests(unittest.TestCase):
    def test_mobile_generation_locks_are_preserved(self):
        self.assertEqual(
            patcher.MOBILE_DATA_BY_PATH["Furniture/CouchNeonPurpleStd.png"]["lock_generation"],
            19,
        )
        self.assertEqual(
            patcher.MOBILE_DATA_BY_PATH["Furniture/SofaPlaid.png"]["lock_generation"],
            12,
        )
        self.assertEqual(
            patcher.MOBILE_DATA_BY_PATH["Furniture/VF3LargeFlatScreenTV.png"]["lock_generation"],
            12,
        )
        self.assertEqual(
            patcher.MOBILE_DATA_BY_PATH["Furniture/InvisibleHammock.png"]["lock_generation"],
            0,
        )

    def test_stock_furniture_records_keep_base_generation_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(patcher.SRC_OBJS / "FurnitureManager.obj", temp_root / "FurnitureManager.obj")
            old_patched = patcher.PATCHED
            patcher.PATCHED = temp_root
            try:
                before_obj = CoffObject(temp_root / "FurnitureManager.obj")
                before_sym = before_obj.symbol(patcher.ITEMINFO)
                before_sec = before_obj.section(before_sym.section)
                stock_len = patcher.ORIG_FURNITURE_COUNT * patcher.RECORD_SIZE
                before_raw = before_sec.raw_ptr + before_sym.value
                before_stock_records = bytes(before_obj.buf[before_raw : before_raw + stock_len])

                patcher.patch_furniture_manager({})

                after_obj = CoffObject(temp_root / "FurnitureManager.obj")
                after_sym = after_obj.symbol(patcher.ITEMINFO)
                after_sec = after_obj.section(after_sym.section)
                after_raw = after_sec.raw_ptr + after_sym.value
                after_stock_records = bytes(after_obj.buf[after_raw : after_raw + stock_len])
                _value, _sectnum, _typ, storage, _aux = struct.unpack_from("<IhHBB", after_obj.buf, after_sym.off + 8)

                self.assertEqual(after_stock_records, before_stock_records)
                self.assertEqual(storage, 2)
            finally:
                patcher.PATCHED = old_patched


class VF3TVAnimationContractTests(unittest.TestCase):
    def test_accepts_b78_frame_enum_order(self):
        manifest = valid_vf3_tv_manifest()

        patcher.validate_vf3_tv_animation_contract(manifest, check_files=False)

        self.assertEqual(manifest["vf3_tv_animation_contract"]["status"], "validated")

    def test_rejects_swapped_east_west_frame_labels(self):
        manifest = valid_vf3_tv_manifest()
        row = manifest["FurnitureManager"]["vf3_tv_animation_records"][0]
        row["frame0_label"], row["frame1_label"] = row["frame1_label"], row["frame0_label"]
        row["frame0_enum"], row["frame1_enum"] = row["frame1_enum"], row["frame0_enum"]

        with self.assertRaisesRegex(RuntimeError, "frame0_label expected Large"):
            patcher.validate_vf3_tv_animation_contract(manifest, check_files=False)

    def test_rejects_missing_private_runtime_descriptor(self):
        manifest = copy.deepcopy(valid_vf3_tv_manifest())
        manifest["theGraphicsManager"]["vf3_tv_floating_animation_images"]["descriptors"] = [
            row
            for row in manifest["theGraphicsManager"]["vf3_tv_floating_animation_images"]["descriptors"]
            if row["label"] != "SmallEast"
        ]

        with self.assertRaisesRegex(RuntimeError, "missing graphics descriptor.*SmallEast"):
            patcher.validate_vf3_tv_animation_contract(manifest, check_files=False)

    def test_private_tv_screen_boxes_match_current_geometry(self):
        self.assertEqual(patcher.VF3_TV_ANIMATION_SCREEN_BOXES["Large"], (4, 5, 65, 80))
        self.assertEqual(patcher.VF3_TV_ANIMATION_SCREEN_BOXES["Small"], (2, 2, 48, 60))
        self.assertEqual(patcher.VF3_TV_ANIMATION_SCREEN_BOXES["FathersFavorite"], (8, 10, 90, 62))
        self.assertEqual(
            patcher.VF3_TV_ANIMATION_SCREEN_BOXES["Large"],
            patcher.VF3_TV_ANIMATION_SCREEN_BOXES["LargeEast"],
        )
        self.assertEqual(
            patcher.VF3_TV_ANIMATION_SCREEN_BOXES["Small"],
            patcher.VF3_TV_ANIMATION_SCREEN_BOXES["SmallEast"],
        )
        self.assertEqual(
            patcher.VF3_TV_ANIMATION_SCREEN_BOXES["FathersFavorite"],
            patcher.VF3_TV_ANIMATION_SCREEN_BOXES["FathersFavoriteEast"],
        )


class VF3TVBehaviorContractTests(unittest.TestCase):
    def test_fmap_cell_value_preserves_stock_tv_object_payloads(self):
        self.assertEqual(patcher.vf3_tv_fmap_cell_value(0x003C6800, 0x003C0001, True), 0x003C6800)
        self.assertEqual(patcher.vf3_tv_fmap_cell_value(0, 0x003C0001, True), 0x003C0001)
        self.assertEqual(patcher.vf3_tv_fmap_cell_value(0x003C6800, 0x003C0001, False), 0)

    def test_accepts_vf3_tv_behavior_manifest(self):
        manifest = valid_vf3_tv_behavior_manifest()

        patcher.validate_vf3_tv_behavior_contract(manifest)

        self.assertEqual(manifest["vf3_tv_behavior_contract"]["status"], "validated")

    def test_rejects_missing_vf3_tv_fmap(self):
        manifest = valid_vf3_tv_behavior_manifest()
        manifest["vf3_tv_fmaps"]["generated"].pop()

        with self.assertRaisesRegex(RuntimeError, "missing generated TV fmap"):
            patcher.validate_vf3_tv_behavior_contract(manifest)

    def test_rejects_load_fmap_guard_drift(self):
        manifest = valid_vf3_tv_behavior_manifest()
        manifest["FurnitureManager"]["load_fmap_range_patch"]["new_max_offset"] = hex(0x134)

        with self.assertRaisesRegex(RuntimeError, "LoadFmap max offset"):
            patcher.validate_vf3_tv_behavior_contract(manifest)


class InvisibleHammockBehaviorContractTests(unittest.TestCase):
    def test_accepts_base_hammock_inheritance_manifest(self):
        manifest = valid_invisible_hammock_manifest()

        patcher.validate_invisible_hammock_behavior_contract(manifest)

        self.assertEqual(manifest["invisible_hammock_behavior_contract"]["status"], "validated")

    def test_rejects_missing_hammock_fmap_donor(self):
        manifest = valid_invisible_hammock_manifest()
        manifest["behavior_assets"]["invisible_outdoor_fmap_donors"] = []

        with self.assertRaisesRegex(RuntimeError, "missing InvisibleHammock.png.fmap"):
            patcher.validate_invisible_hammock_behavior_contract(manifest)

    def test_drop_action_widens_hammock_gate_without_breaking_relocated_mov(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            source_hotspot = patcher.SRC_OBJS / "HotSpot.obj"
            shutil.copy2(source_hotspot, temp_root / "HotSpot.obj")
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}

                patcher.patch_invisible_hammock_drop_action(manifest)

                obj = CoffObject(temp_root / "HotSpot.obj")
                symbol = obj.symbol("?Hammock@CHotSpot@@CA?B_NAAVCVillager@@@Z")
                section = obj.section(symbol.section)
                raw = section.raw_ptr + symbol.value
                self.assertEqual(obj.buf[raw + 4 : raw + 9], b"\x90" * 5)
                self.assertEqual(obj.buf[raw + 9], 0xB9)
                self.assertEqual(obj.buf[raw + 14], 0xE8)
                helper = (temp_root / "vf2_invisible_hammock.cpp").read_text(encoding="ascii")
                self.assertIn("VF2EitherHammockInWorld", helper)
                self.assertIn("(EInventoryItem)0x1E1", helper)
                self.assertIn("(EInventoryItem)0x30C", helper)
                self.assertEqual(manifest["invisible_hammock_drop_action"]["base_item"], "0x1E1")
                self.assertEqual(manifest["invisible_hammock_drop_action"]["added_item"], "0x30C")
                self.assertTrue(manifest["invisible_hammock_drop_action"]["hotspot_modified"])
                self.assertTrue(manifest["invisible_hammock_drop_action"]["matches_base_hammock_behavior"])
            finally:
                patcher.PATCHED = old_patched


class InvisibleKidsTableBehaviorContractTests(unittest.TestCase):
    def test_accepts_base_kids_table_inheritance_manifest(self):
        manifest = valid_invisible_kids_table_manifest()

        patcher.validate_invisible_kids_table_behavior_contract(manifest)

        self.assertEqual(manifest["invisible_kids_table_behavior_contract"]["status"], "validated")

    def test_rejects_missing_kids_table_fmap_donor(self):
        manifest = valid_invisible_kids_table_manifest()
        manifest["behavior_assets"]["invisible_transparent_fmap_donors"] = []

        with self.assertRaisesRegex(RuntimeError, "missing InvisibleKidsTableAndChairs.png.fmap"):
            patcher.validate_invisible_kids_table_behavior_contract(manifest)

    def test_stock_kids_table_hotspot_dispatches_native_behavior_directly(self):
        obj = CoffObject(patcher.SRC_OBJS / "HotSpot.obj")
        symbol = obj.symbol("?KidsTable@CHotSpot@@CA?B_NAAVCVillager@@@Z")
        section = obj.section(symbol.section)
        raw = section.raw_ptr + symbol.value

        self.assertEqual(obj.buf[raw + 0x0B : raw + 0x11], b"\x68\x30\x01\x00\x00\xE8")
        reloc_names = []
        for idx in range(section.nreloc):
            off = section.reloc_ptr + idx * 10
            va, symidx, _reloc_type = struct.unpack_from("<LLH", obj.buf, off)
            if va == symbol.value + 0x11:
                reloc_names.append(obj.symbol_by_index[symidx].name)
        self.assertEqual(
            reloc_names,
            ["?NewBehavior@CVillager@@QAEXW4EBehavior@@ABUSBehaviorData@@@Z"],
        )


class SpontaneousBehaviorContractTests(unittest.TestCase):
    def test_b150_behavior_groups_and_native_gates(self):
        groups = {name: entries for name, entries in patcher.BEHAVIOR_LABEL_GROUPS}
        self.assertEqual(
            [text for _key, text in groups["web_13_plus"]],
            ["Buying stuff online"],
        )
        web_basic = [text for _key, text in groups["web_basic"]]
        self.assertEqual(web_basic.count("Watching memes"), 1)
        self.assertIn("Making memes", web_basic)
        self.assertIn("Posting memes online", web_basic)
        self.assertEqual(len(groups["infant_care"]), 9)
        self.assertEqual(
            {text for _key, text in groups["infant_care"]},
            {
                "Teaching baby how to walk",
                "Talking with baby",
                "Feeding baby",
                "Singing lullabies to baby",
                "Playing with baby",
                "Admiring baby",
                "Playing peek-a-boo with baby",
                "Kissing baby",
                "Taking pictures of baby",
            },
        )
        nap_labels = [text for _key, text in groups["nap_dream"]]
        self.assertEqual(len(nap_labels), 30)
        self.assertEqual(len(set(nap_labels)), 30)
        self.assertEqual(nap_labels.count("Dreaming of Isola"), 1)
        self.assertIn("Dreaming of roller coasters", nap_labels)
        self.assertIn("Dreaming of discovering something", nap_labels)
        self.assertEqual(
            groups["bathroom_sink_female_teen_plus"],
            [("eString_PuttingOnJewelry", "Putting on jewelry")],
        )

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            for filename in ("Villager.obj", "VillagerAI.obj", "Behavior.obj", "theMainScene.obj"):
                shutil.copy2(patcher.SRC_OBJS / filename, temp_root / filename)
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}
                patcher.patch_spontaneous_behaviors(manifest)
                helper = (temp_root / "vf2_spontaneous_behaviors.cpp").read_text(encoding="ascii")
                self.assertIn("EnableAllAgesAutonomousCandidateWithWeight(data, 0x046, 450)", helper)
                self.assertIn("EnableNursingMotherAutonomousCandidateWithWeight(data, 0x11F, 450)", helper)
                self.assertIn("*(unsigned int *)(candidate + 0x4C) = 0x168;", helper)
                self.assertIn("candidate[0xA3] = 1;", helper)
                self.assertNotIn("EnableAllAgesAutonomousCandidateWithWeight(data, 0x19A", helper)
                for target in range(0x0A5, 0x0A9):
                    self.assertIn(
                        f"CloneAutonomousCandidateWithWeight(data, 0x0A4, 0x{target:03X}, 450)",
                        helper,
                    )
                self.assertIn("CloneAutonomousCandidateWithWeight(data, 0x034, 0x016, 450)", helper)
                self.assertIn("return VF2AgeValue(villager) >= 0x104;", helper)
                self.assertIn("age >= 0x118 && age < 0x17C", helper)
                self.assertIn("+ 0x6A58", helper)
                self.assertIn("+ 0x6B8C", helper)
                self.assertIn("VF2GenderValue(villager) == 1 && VF2AgeValue(villager) >= 0x118", helper)
                self.assertIn("Weather.currentType == 5", helper)

                patcher.patch_behavior_label_variants(manifest)
                infant = next(
                    row for row in manifest["behavior_label_variants"]["changed"]
                    if row["behavior_id"] == "0x11f"
                )
                self.assertEqual(infant["helper"], "_VF2RandomInfantCareLabel")
            finally:
                patcher.PATCHED = old_patched

    def test_children_play_at_kids_table_is_child_only_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(patcher.SRC_OBJS / "Villager.obj", temp_root / "Villager.obj")
            shutil.copy2(patcher.SRC_OBJS / "VillagerAI.obj", temp_root / "VillagerAI.obj")
            shutil.copy2(patcher.SRC_OBJS / "Behavior.obj", temp_root / "Behavior.obj")
            shutil.copy2(patcher.SRC_OBJS / "theMainScene.obj", temp_root / "theMainScene.obj")
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}

                patcher.patch_spontaneous_behaviors(manifest)

                helper = (temp_root / "vf2_spontaneous_behaviors.cpp").read_text(encoding="ascii")
                self.assertIn(
                    "EnableChildOnlyAutonomousCandidate(data, 0x130); // ChildrenPlayAtKidsTable / Playing quietly",
                    helper,
                )
                self.assertIn("class CNight", helper)
                self.assertIn("extern CNight Night;", helper)
                self.assertIn("Night.AIIsDayTime()", helper)
                self.assertIn("playhouse[0xCD] = (unsigned char)daytimeAllowsPlayhouse;", helper)
                self.assertIn("EnableAllAgesAutonomousCandidateWithWeight(data, 0x127, 450); // RestingBody / Needs to sit down", helper)
                actions = " ".join(manifest["spontaneous_behaviors"]["actions"])
                self.assertIn("playing quietly at kids table", actions)
                self.assertIn("non-adults", actions)
                self.assertIn("daytime only", actions)
            finally:
                patcher.PATCHED = old_patched

    def test_behavior_label_variants_preserve_current_label_on_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(patcher.SRC_OBJS / "Villager.obj", temp_root / "Villager.obj")
            shutil.copy2(patcher.SRC_OBJS / "VillagerAI.obj", temp_root / "VillagerAI.obj")
            shutil.copy2(patcher.SRC_OBJS / "Behavior.obj", temp_root / "Behavior.obj")
            shutil.copy2(patcher.SRC_OBJS / "theMainScene.obj", temp_root / "theMainScene.obj")
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}

                patcher.patch_spontaneous_behaviors(manifest)

                helper = (temp_root / "vf2_spontaneous_behaviors.cpp").read_text(encoding="ascii")
                self.assertIn("static int VF2CurrentLabelInGroup", helper)
                self.assertIn("static int VF2CurrentLabelInGroups2", helper)
                self.assertIn("static void VF2ApplyRememberedOrRandomLabel", helper)
                self.assertIn("static bool VF2RunNativeBehaviorAndChangedLabel", helper)
                self.assertIn("struct VF2BehaviorLabelCacheSlot", helper)
                self.assertIn("static bool VF2GetCachedBehaviorLabel", helper)
                self.assertIn("static void VF2RestoreCachedNativeLabel", helper)
                self.assertIn("VF2RememberBehaviorLabel(villager, (int)labels, selectedStringId);", helper)
                self.assertNotIn("VF2ApplyUncachedRandomLabel", helper)
                self.assertIn("if (slot->stringId == 0)", helper)
                self.assertIn("behaviorLabel[i] = slot->nativeLabel[i];", helper)
                self.assertIn("kVF2RadioListenCacheSentinel = -1", helper)
                self.assertIn("CBehavior::ListenToRadio", helper)
                self.assertIn(
                    "VF2RememberBehaviorLabel(villager, cacheTag, kVF2RadioListenCacheSentinel)",
                    helper,
                )
                self.assertIn("int behaviorId;", helper)
                self.assertIn("unsigned int behaviorSerial;", helper)
                self.assertIn("unsigned int praiseCount;", helper)
                self.assertIn("data + 0x1BBA0", helper)
                self.assertIn("data + 0x1BBA4", helper)
                self.assertIn("data + 0x6B48", helper)
                self.assertIn("data + 0x6B4C", helper)
                self.assertIn("behaviorSerial == slot->behaviorSerial + 1", helper)
                self.assertIn("praiseCount != slot->praiseCount", helper)
                self.assertIn("void ForgetPlans(CVillager &villager, bool force);", helper)
                self.assertIn('extern "C" void __stdcall VF2PraiseCaptureAndForget', helper)
                self.assertIn('extern "C" void __stdcall VF2PraiseStartAndRestore', helper)
                self.assertIn("for (int i = 0; i < 0x28; ++i)", helper)
                self.assertIn("VF2RestoreRawPraiseLabel(villager);", helper)
                self.assertIn("VF2CopyBehaviorLabel(villager, before);", helper)
                self.assertIn("VF2CopyBehaviorLabel(villager, gVF2BehaviorLabelBeforeNative);", helper)
                self.assertIn("return VF2BehaviorLabelChangedSince(villager, before);", helper)
                self.assertIn(
                    "int remembered = VF2CurrentLabelInGroups2(",
                    helper,
                )
                self.assertIn("kVF2BehaviorLabels_video_game_teen", helper)
                self.assertIn("if (!VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::PlayingVideoGame)) return;", helper)
                self.assertIn(
                    "VF2ApplyRememberedOrRandomLabels2(",
                    helper,
                )
                self.assertIn("if (!VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::Shower)) return;", helper)
                self.assertIn("if (!VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::NorthShower)) return;", helper)
                self.assertIn("if (!VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::WashingInBathroomSink)) return;", helper)
                self.assertIn("if (!VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::BathroomGroomingGeneral)) return;", helper)
                self.assertIn("int fixedStringId = kVF2BehaviorLabels_trampoline_textfix[0];", helper)
                self.assertIn("VF2RememberBehaviorLabel(villager, cacheTag, fixedStringId);", helper)
                self.assertIn("int remembered = VF2CurrentCoffeeLabel(villager);", helper)
                self.assertIn("int remembered = VF2CurrentShowerLabel(villager);", helper)
                self.assertIn("VF2ApplyRememberedOrRandomLabel(\n        villager,\n        kVF2BehaviorLabels_radio_dance", helper)
                self.assertNotIn("rememberedDance", helper)
                self.assertNotIn("VF2CurrentLabelMatchesStringId", helper)

                main_obj = CoffObject(temp_root / "theMainScene.obj")
                reward = main_obj.symbol("?InvokeReward@theMainScene@@IAEXAAVCVillager@@@Z")
                reward_sec = main_obj.section(reward.section)
                reloc_targets = {}
                for index in range(reward_sec.nreloc):
                    off = reward_sec.reloc_ptr + index * 10
                    vaddr, symbol_index, _rtype = struct.unpack_from("<IIH", main_obj.buf, off)
                    if vaddr in (
                        reward.value + 0x2EB,
                        reward.value + 0x31B,
                        reward.value + 0x36B,
                        reward.value + 0x3B7,
                    ):
                        reloc_targets[vaddr - reward.value] = main_obj.symbol_by_index[symbol_index].name
                self.assertEqual(reloc_targets[0x36B], "_VF2PraiseCaptureAndForget@8")
                self.assertEqual(reloc_targets[0x3B7], "_VF2PraiseStartAndRestore@4")
                self.assertEqual(
                    reloc_targets[0x2EB],
                    "?ForgetPlans@CVillagerPlans@@QAEXAAVCVillager@@_N@Z",
                )
                self.assertEqual(
                    reloc_targets[0x31B],
                    "?StartNewBehavior@CVillagerPlans@@QAEXAAVCVillager@@@Z",
                )
                self.assertTrue(
                    manifest["spontaneous_behaviors"]["praise_label_stability"][
                        "over_praise_runaway_path_unchanged"
                    ]
                )
            finally:
                patcher.PATCHED = old_patched

    def test_food_drink_label_variants_use_native_base_sequences(self):
        expected_labels = {
            "eString_WatchingCartoons",
            "eString_GettingDrinkMineralWater",
            "eString_GettingDrinkHydrAid",
            "eString_BakingCake",
            "eString_EatingBagChips",
            "eString_MakingPaella",
            "eString_EatingPancakes",
            "eString_PlayingChess",
            "eString_Gardening",
            "eString_PuttingOnFaceMask",
            "eString_PaintingFingernails",
            "eString_JumpingOnTheTrampoline",
        }
        self.assertTrue(expected_labels.issubset(patcher.BEHAVIOR_LABEL_INDEX))

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(patcher.SRC_OBJS / "Villager.obj", temp_root / "Villager.obj")
            shutil.copy2(patcher.SRC_OBJS / "VillagerAI.obj", temp_root / "VillagerAI.obj")
            shutil.copy2(patcher.SRC_OBJS / "Behavior.obj", temp_root / "Behavior.obj")
            shutil.copy2(patcher.SRC_OBJS / "theMainScene.obj", temp_root / "theMainScene.obj")
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}

                patcher.patch_spontaneous_behaviors(manifest)
                helper = (temp_root / "vf2_spontaneous_behaviors.cpp").read_text(encoding="ascii")

                for group in ("drink", "heat_food", "snacks", "meal_prep"):
                    self.assertIn(f"kVF2BehaviorLabels_{group}", helper)
                self.assertIn("if (!VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::GetADrink)) return;", helper)
                self.assertIn("if (!VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::HeatUpFood)) return;", helper)
                self.assertIn("if (!VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::LookingForSnacksDispatch)) return;", helper)
                self.assertIn("if (!VF2RunNativeBehaviorAndChangedLabel(villager, CBehavior::PreparingAMeal)) return;", helper)
                self.assertIn("TV, drink, heat-food, snack, meal-prep", " ".join(manifest["spontaneous_behaviors"]["actions"]))

                patcher.patch_behavior_label_variants(manifest)
                helpers = {row["helper"] for row in manifest["behavior_label_variants"]["changed"]}
                self.assertTrue(
                    {
                        "_VF2RandomDrinkLabel",
                        "_VF2RandomHeatFoodLabel",
                        "_VF2RandomSnacksLabel",
                        "_VF2RandomMealPrepLabel",
                    }.issubset(helpers)
                )
            finally:
                patcher.PATCHED = old_patched


class RadioBehaviorContractTests(unittest.TestCase):
    def test_radio_and_mp3_drop_route_randomizes_dance_or_listen(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(patcher.SRC_OBJS / "Behavior.obj", temp_root / "Behavior.obj")
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}

                patcher.patch_radio_drop_behavior(manifest)

                obj = CoffObject(temp_root / "Behavior.obj")
                ctor = obj.symbol("??0CBehavior@@QAE@XZ")
                sec = obj.section(ctor.section)
                relocation_vaddr = ctor.value + 0xC3C
                reloc_names = []
                for idx in range(sec.nreloc):
                    off = sec.reloc_ptr + idx * 10
                    va, symidx, _reloc_type = struct.unpack_from("<LLH", obj.buf, off)
                    if va == relocation_vaddr:
                        reloc_names.append(obj.symbol_by_index[symidx].name)
                self.assertEqual(reloc_names, ["_VF2RandomRadioBehavior"])
                self.assertEqual(
                    manifest["radio_drop_behavior"]["new_behavior"],
                    "random choice: DancingRadio or ListenToRadio",
                )
                self.assertIn("base radio, MP3 player", manifest["radio_drop_behavior"]["scope"])
            finally:
                patcher.PATCHED = old_patched

    def test_spontaneous_radio_uses_same_randomized_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(patcher.SRC_OBJS / "Villager.obj", temp_root / "Villager.obj")
            shutil.copy2(patcher.SRC_OBJS / "VillagerAI.obj", temp_root / "VillagerAI.obj")
            shutil.copy2(patcher.SRC_OBJS / "Behavior.obj", temp_root / "Behavior.obj")
            shutil.copy2(patcher.SRC_OBJS / "theMainScene.obj", temp_root / "theMainScene.obj")
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}

                patcher.patch_spontaneous_behaviors(manifest)

                helper = (temp_root / "vf2_spontaneous_behaviors.cpp").read_text(encoding="ascii")
                self.assertIn(
                    "EnableAutonomousCandidate(data, 0x0ED); // Random radio: DancingRadio or ListenToRadio",
                    helper,
                )
                self.assertIn("random radio/MP3 dancing or listening (all ages)", manifest["spontaneous_behaviors"]["actions"])
            finally:
                patcher.PATCHED = old_patched


class InvisibleFurnitureReferenceSetTests(unittest.TestCase):
    def test_outdoor_transparent_backups_are_generated_from_donor_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_out = patcher.OUT
            try:
                from PIL import Image

                patcher.OUT = Path(tmp)
                furniture = patcher.OUT / "Images" / "Furniture"
                furniture.mkdir(parents=True)
                sources = {
                    "InvisibleKiddiePool": ("PoolChildrensStd.png", (8, 6)),
                    "InvisibleFullSizePool": ("PoolLargeStd.png", (10, 7)),
                    "InvisibleHammock": ("HammockStd.png", (12, 5)),
                }
                for source_name, size in sources.values():
                    Image.new("RGBA", size, (255, 0, 0, 255)).save(furniture / source_name)

                manifest = {}
                patcher.sync_invisible_outdoor_sprites(manifest)

                self.assertEqual(manifest["invisible_outdoor_sprites"]["missing"], [])
                self.assertEqual(manifest["invisible_outdoor_sprites"]["issues"], [])
                for invisible_name, (source_name, size) in sources.items():
                    self.assertEqual((furniture / f"{invisible_name}.png").read_bytes(), (furniture / source_name).read_bytes())
                    with Image.open(furniture / f"{invisible_name}.pngORIGINAL").convert("RGBA") as transparent:
                        self.assertEqual(transparent.size, size)
                        self.assertIsNone(transparent.getbbox())
            finally:
                patcher.OUT = old_out

    def test_outdoor_base_graphics_use_base_game_donors(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_out = patcher.OUT
            try:
                patcher.OUT = Path(tmp)
                furniture = patcher.OUT / "Images" / "Furniture"
                furniture.mkdir(parents=True)
                sources = {
                    "InvisibleKiddiePool": ("PoolChildrensStd.png", b"visible kiddie pool", b"transparent kiddie pool"),
                    "InvisibleFullSizePool": ("PoolLargeStd.png", b"visible full pool", b"transparent full pool"),
                    "InvisibleHammock": ("HammockStd.png", b"visible hammock", b"transparent hammock"),
                }
                for invisible_name, (source_name, visible_bytes, transparent_bytes) in sources.items():
                    (furniture / source_name).write_bytes(visible_bytes)
                    (furniture / f"{invisible_name}.png").write_bytes(b"active invisible placeholder")
                    (furniture / f"{invisible_name}.pngORIGINAL").write_bytes(transparent_bytes)

                manifest = {}
                patcher.sync_invisible_furniture_reference_sets(manifest)

                base = patcher.OUT / "OptionalVisualMods" / "Invisible Furniture - Base Graphics"
                transparent = patcher.OUT / "OptionalVisualMods" / "Invisible Furniture - Transparent"
                for invisible_name, (_, visible_bytes, transparent_bytes) in sources.items():
                    self.assertEqual((base / f"{invisible_name}.png").read_bytes(), visible_bytes)
                    self.assertEqual((transparent / f"{invisible_name}.png").read_bytes(), transparent_bytes)
                self.assertEqual(manifest["invisible_furniture_reference_sets"]["missing"], [])
            finally:
                patcher.OUT = old_out

    def test_reference_transparent_graphics_can_be_generated_before_original_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_out = patcher.OUT
            try:
                from PIL import Image

                patcher.OUT = Path(tmp)
                furniture = patcher.OUT / "Images" / "Furniture"
                furniture.mkdir(parents=True)
                sources = {
                    "InvisibleKiddiePool": ("PoolChildrensStd.png", (8, 6)),
                    "InvisibleFullSizePool": ("PoolLargeStd.png", (10, 7)),
                    "InvisibleHammock": ("HammockStd.png", (12, 5)),
                }
                for invisible_name, (source_name, size) in sources.items():
                    Image.new("RGBA", size, (255, 0, 0, 255)).save(furniture / source_name)
                    (furniture / f"{invisible_name}.png").write_bytes(b"active invisible placeholder")

                manifest = {}
                patcher.sync_invisible_furniture_reference_sets(manifest)

                transparent = patcher.OUT / "OptionalVisualMods" / "Invisible Furniture - Transparent"
                for invisible_name, (_source_name, size) in sources.items():
                    with Image.open(transparent / f"{invisible_name}.png").convert("RGBA") as generated:
                        self.assertEqual(generated.size, size)
                        self.assertIsNone(generated.getbbox())
                self.assertEqual(manifest["invisible_furniture_reference_sets"]["missing"], [])
            finally:
                patcher.OUT = old_out


class InvisibleHeartShapedBedContractTests(unittest.TestCase):
    def test_invisible_heart_bed_is_separate_heart_shaped_bed_clone(self):
        heart_path = "Furniture/InvisibleHeartShapedBed.png"
        rows = [(idx, row) for idx, row in enumerate(patcher.ITEMS) if row[3] == heart_path]

        self.assertEqual(len(rows), 1)
        idx, (_name, donor, list_name, path) = rows[0]
        self.assertEqual(path, heart_path)
        self.assertEqual(patcher.item_id_for(idx), 0x327)
        self.assertEqual(donor, 0x252)
        self.assertEqual(list_name, "gFurniture4")

        data = patcher.MOBILE_DATA_BY_PATH[heart_path]
        self.assertEqual(data["short_description"], "Invisible Heart-Shaped Bed")
        self.assertEqual(data["price"], 2750)

        configured = next(
            item
            for item in patcher.INVISIBLE_TRANSPARENT_BASE_ITEMS
            if item["name"] == "InvisibleHeartShapedBed"
        )
        self.assertEqual(configured["source_png"], "HeartShapedBed.png")
        self.assertEqual(configured["donor_fmap"], "HeartShapedBed.png.fmap")

    def test_existing_invisible_adult_double_bed_stays_brown_bed_clone(self):
        adult = next(
            item
            for item in patcher.INVISIBLE_TRANSPARENT_BASE_ITEMS
            if item["name"] == "InvisibleAdultDoubleBed"
        )

        self.assertEqual(adult["item_id"], 0x314)
        self.assertEqual(adult["donor"], 0x1B7)
        self.assertEqual(adult["source_png"], "BedAdultBrownStd.png")
        self.assertEqual(adult["donor_fmap"], "BedAdultBrownStd.png.fmap")


class SettingsEvictBehaviorTests(unittest.TestCase):
    def test_evict_button_constructor_is_always_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(patcher.SRC_OBJS / "theOptionsDialog.obj", temp_root / "theOptionsDialog.obj")
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}

                patcher.patch_options_dialog(manifest)

                obj = CoffObject(temp_root / "theOptionsDialog.obj")
                symbol = obj.symbol("??0theOptionsDialog@@QAE@PADW4DialogColorEnum@@@Z")
                section = obj.section(symbol.section)
                start = section.raw_ptr + symbol.value
                self.assertEqual(obj.buf[start + 0x2DA : start + 0x2E0], b"\x90" * 6)
                self.assertEqual(obj.buf[start + 0x2E0 : start + 0x2E7], b"\x83\x3D\x04\x00\x00\x00\x02")
                self.assertEqual(obj.buf[start + 0x2E7 : start + 0x2E9], b"\x90" * 2)
                self.assertEqual(obj.buf[start + 0x360 : start + 0x364], b"\x56\x8B\xCB\xE8")
                obj.symbol("?EvictFamily@theOptionsDialog@@AAEXXZ")
                obj.symbol("?EvictFamily@CFamilyTree@@QAEXXZ")
                obj.symbol("?AddControl@ldwScene@@IAEXPAVldwControl@@@Z")
                self.assertIn("added to the Settings control list", manifest["settings_menu"]["evict"]["status"])
            finally:
                patcher.PATCHED = old_patched


class TextFixStringManagerTests(unittest.TestCase):
    def test_text_fixes_retarget_existing_stock_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(patcher.SRC_OBJS / "theStringManager.obj", temp_root / "theStringManager.obj")
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}

                patcher.patch_string_manager(manifest)

                updates = {
                    row["old"]: row["new"]
                    for row in manifest["theStringManager"]["updated_existing_strings"]
                }
                self.assertEqual(updates["Cooking like mommy"], "Cooking like a grownup")
                self.assertEqual(updates["Driving like daddy"], "Driving like a grownup")
                self.assertIn("Settings Evict confirmation", updates)
                self.assertIn("This button will EVICT your current family", updates["Settings Evict confirmation"])
                self.assertIn("Click OK to continue. Otherwise, click Cancel.", updates["Settings Evict confirmation"])
                helper = (temp_root / "vf2_mobile_string_table.c").read_text(encoding="ascii")
                self.assertIn("Cooking like a grownup", helper)
                self.assertIn("Driving like a grownup", helper)
                self.assertIn("This button will EVICT your current family", helper)
                self.assertIn("\\n\\nYou will keep all the money", helper)
            finally:
                patcher.PATCHED = old_patched

class OutfitStoreMappingTests(unittest.TestCase):
    def test_behavior_patch_mutations_are_all_inside_compile_time_gate(self):
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        self.assertIn(
            'ENABLE_BEHAVIOR_PATCHES = os.environ.get("VF2_ENABLE_BEHAVIOR_PATCHES", "0") == "1"',
            source,
        )
        tree = ast.parse(source)
        main = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        gate = next(
            node for node in main.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "ENABLE_BEHAVIOR_PATCHES"
        )
        gated_calls = {
            node.func.id
            for node in ast.walk(gate)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        expected = {
            "patch_invisible_hammock_drop_action",
            "patch_spontaneous_behaviors",
            "patch_bookshelf_reading_behavior",
            "patch_radio_drop_behavior",
            "patch_behavior_label_variants",
            "patch_arcade_behavior_labels",
        }

        self.assertTrue(expected.issubset(gated_calls))
        for node in main.body:
            if node is gate:
                continue
            outside_calls = {
                call.func.id
                for call in ast.walk(node)
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            }
            self.assertTrue(expected.isdisjoint(outside_calls))
        self.assertIn('PATCHED / "vf2_invisible_hammock.cpp"', source)
        self.assertIn('PATCHED / "vf2_spontaneous_behaviors.cpp"', source)
        self.assertIn("Behavior Patches disabled: stock spontaneous and label behavior retained.", source)
        self.assertIn("if ENABLE_BEHAVIOR_PATCHES:\n        validate_invisible_hammock_behavior_contract(manifest)", source)
        self.assertIn(
            "if ENABLE_BEHAVIOR_PATCHES:\n"
            "        for index, (key, text) in enumerate(BEHAVIOR_LABELS):",
            source,
        )

    def test_b150_cheat_upgrade_rows_and_exact_descriptions(self):
        rows = {item["item_id"]: item for item in patcher.CHEAT_UPGRADE_ITEMS}

        self.assertEqual(rows[0x125]["name"], "Reset Ants")
        self.assertEqual(rows[0x126]["name"], "Reset all collections")
        self.assertEqual(rows[0x127]["name"], "Complete all collections")
        self.assertEqual(rows[0x128]["description"], "Everything in the store costs twice as much.")
        self.assertEqual(rows[0x129]["description"], "Everything in the store costs five times as much.")
        self.assertEqual(
            rows[0x12A]["description"],
            "Everything in the store now costs an insane amount. Good Luck!",
        )
        self.assertEqual(rows[0x12B]["name"], "Trigger all house malfunctions")
        self.assertIn('Useful for getting the "Handyman" goal.', rows[0x12B]["description"])
        self.assertIn(0x12B, patcher.VISIBLE_SPECIAL_UPGRADE_ICON_FILES)
        self.assertEqual(rows[0x12C]["name"], "Reset Price Multiplier")
        self.assertEqual(rows[0x12C]["description"], "Resets store prices to original values.")
        self.assertIn(0x12C, patcher.VISIBLE_SPECIAL_UPGRADE_ICON_FILES)
        self.assertEqual(rows[0x12D]["name"], "Fix all house malfunctions")
        self.assertIn("Router back online", rows[0x12D]["description"])
        self.assertIn(0x12D, patcher.VISIBLE_SPECIAL_UPGRADE_ICON_FILES)
        self.assertEqual(
            [item["item_id"] for item in patcher.CHEAT_UPGRADE_ITEMS],
            [
                0x11B, 0x11D, 0x11E, 0x11F,
                0x11C, 0x120, 0x121, 0x122,
                0x123, 0x124, 0x125, 0x126, 0x127,
                0x128, 0x129, 0x12A, 0x12C,
                0x12B, 0x12D,
            ],
        )

        source = Path(patcher.__file__).read_text(encoding="utf-8")
        self.assertIn("theGameState::Get()->ResetWorldState(0x13)", source)
        self.assertIn("for (int prop = 0x4D; prop <= 0x54; ++prop)", source)
        self.assertIn("0x4D + ldwGameState::GetRandom(3)", source)
        self.assertIn("Environment.SetProp((EPropEnum)0x50)", source)
        self.assertIn("Environment.SetProp((EPropEnum)0x51)", source)
        self.assertIn("static void VF2ResetAchievementRaw(int achievement)", source)
        self.assertIn("record[0] = 0;", source)
        self.assertIn("*(unsigned int *)(record + 4) = 0;", source)
        self.assertIn("VF2ResetAchievementRaw(0x4D)", source)
        self.assertIn("VF2ResetAchievementRaw(0x54)", source)
        self.assertIn("for (int i = 0; i < 6; ++i)", source)
        self.assertNotIn("int count = kVF2IncludeHolidayOrnamentCollection ? 6 : 5;", source)
        self.assertIn("for (int sellingGoal = 0x4E; sellingGoal <= 0x53; ++sellingGoal)", source)
        self.assertIn("Achievement.IsComplete((EAchievement)sellingGoal)", source)
        self.assertIn("Achievement.IncrementProgress((EAchievement)0x54, completedSellingGoals)", source)

    def test_trigger_all_malfunctions_uses_native_dryer_and_renovation_gates(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                helper = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
                helper.write_text("", encoding="ascii")

                patcher.write_outfit_store_helpers({})
                source = helper.read_text(encoding="ascii")

                self.assertIn("VF2TriggerAllHouseMalfunctions", source)
                self.assertIn("{0x17, 0x1A, 0x1B, 0x1C, 0x1D, 0x1F, 0x20}", source)
                self.assertIn("Prop 0x17 is Router Offline", source)
                self.assertIn("eObjectDryer = 0x48", source)
                self.assertIn("origin = {100, 100}", source)
                self.assertIn("FurnitureManager.FindFurniture", source)
                self.assertIn("Environment.SetProp((EPropEnum)0x21)", source)
                self.assertIn("InventoryManager.HaveUpgrade((EInventoryItem)0xE6)", source)
                for prop in (0x48, 0x49, 0x4A):
                    self.assertIn(f"Environment.SetProp((EPropEnum)0x{prop:02X})", source)
                self.assertNotIn("Environment.SetProp((EPropEnum)0x4D)", source)

                self.assertIn("VF2FixAllHouseMalfunctions", source)
                self.assertIn(
                    "0x17, 0x1A, 0x1B, 0x1C, 0x1D, 0x1F, 0x20, 0x21, 0x48, 0x49, 0x4A",
                    source,
                )
                fix_source = source.split('extern "C" void __cdecl VF2FixAllHouseMalfunctions()', 1)[1]
                fix_source = fix_source.split("static const int kVF2OutfitStoreFemaleItemBase", 1)[0]
                self.assertIn("Environment.ClearProp", fix_source)
                self.assertNotIn("ResetWorldState", fix_source)
                self.assertNotIn("0x4D,", fix_source)
                self.assertNotIn("0x4E,", fix_source)
                self.assertNotIn("0x50,", fix_source)
                self.assertNotIn("0x54,", fix_source)
        finally:
            patcher.PATCHED = old_patched

    def test_native_north_bathroom_random_malfunctions_remain_renovation_gated(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                shutil.copy2(
                    patcher.SRC_OBJS / "theMainScene.obj",
                    patcher.PATCHED / "theMainScene.obj",
                )
                manifest = {}

                patcher.validate_native_north_bathroom_malfunction_selection(manifest)

                contract = manifest["native_north_bathroom_malfunctions"]
                self.assertEqual(contract["status"], "validated and preserved")
                self.assertEqual(contract["second_bathroom_upgrade"], "0xE6")
                self.assertEqual(
                    [(row["name"], row["prop"]) for row in contract["cases"]],
                    [
                        ("north shower leak", "0x49"),
                        ("north toilet leak", "0x48"),
                        ("north sink leak", "0x4a"),
                    ],
                )
        finally:
            patcher.PATCHED = old_patched

    def test_native_dryer_lint_fire_remains_real_dryer_gated_malfunction(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                for name in ("theMainScene.obj", "Behavior.obj"):
                    shutil.copy2(patcher.SRC_OBJS / name, patcher.PATCHED / name)
                manifest = {}

                patcher.validate_native_dryer_lint_fire_contract(manifest)

                contract = manifest["native_dryer_lint_fire"]
                self.assertEqual(contract["status"], "validated and preserved")
                self.assertEqual(contract["dryer_object"], "0x48")
                self.assertEqual(contract["malfunction_prop"], "0x21")
                self.assertTrue(contract["requires_dryer_in_house"])
                self.assertEqual(contract["repair_advances_achievement"], "0x3a")
                self.assertEqual(contract["achievement_name"], "Handyman")
        finally:
            patcher.PATCHED = old_patched

    def test_water_pressure_surge_adds_all_three_renovation_gated_north_leaks(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                for name in ("IslandEvents.obj", "Villager.obj"):
                    shutil.copy2(patcher.SRC_OBJS / name, patcher.PATCHED / name)
                manifest = {}

                patcher.patch_second_bathroom_leaks(manifest)

                contract = manifest["SecondBathroomLeaks"]
                self.assertEqual(contract["second_bathroom_upgrade_item"], "0xE6")
                self.assertEqual(
                    contract["water_pressure_surge_hook"]["north_props_added"],
                    {
                        "toilet": "0x48",
                        "shower": "0x49",
                        "bathroom_sink": "0x4A",
                    },
                )
                helper = (
                    patcher.PATCHED / "vf2_island_events.cpp"
                ).read_text(encoding="ascii")
                self.assertIn("InventoryManager.HaveUpgrade((EInventoryItem)0xE6)", helper)
                for prop in (0x48, 0x49, 0x4A):
                    self.assertIn(f"Environment.SetProp((EPropEnum)0x{prop:02X})", helper)
        finally:
            patcher.PATCHED = old_patched

    def test_reversible_and_price_helpers_follow_cheat_upgrade_compile_gate(self):
        old_patched = patcher.PATCHED
        old_enabled = patcher.ENABLE_CHEAT_UPGRADES
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                for enabled, expected in ((False, "false"), (True, "true")):
                    patcher.ENABLE_CHEAT_UPGRADES = enabled
                    helper = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
                    helper.write_text("", encoding="ascii")
                    manifest = {}
                    patcher.write_outfit_store_helpers(manifest)
                    source = helper.read_text(encoding="ascii")

                    self.assertIn(
                        f"static const bool kVF2EnableB150CheatUpgrades = {expected};",
                        source,
                    )
                    self.assertIn("if (!kVF2EnableB150CheatUpgrades) return -1;", source)
                    self.assertIn("if (!kVF2EnableB150CheatUpgrades) return false;", source)
                    self.assertIn("if (!kVF2EnableB150CheatUpgrades) return price;", source)
                    self.assertIn("if (kVF2EnableB150CheatUpgrades &&", source)
                    self.assertIn("VF2ResetB150PriceMode", source)
                    self.assertIn("for (int mode = 0x128; mode <= 0x12A; ++mode)", source)
                    self.assertIn("CVillager& GetVillager(int id);", source)
                    self.assertIn("VillagerManager.GetVillager(workerId)", source)
                    self.assertNotIn("GetVillagerPtr(workerId)", source)
                    self.assertIn("VF2DeactivateWorker(0x23, 0x25AF8)", source)
                    self.assertIn("VF2DeactivateWorker(0x24, 0x25AFC)", source)
                    self.assertIn("((unsigned char*)&worker)[0x1BB84] = 0", source)
                    self.assertIn("gameState + 0x25CC4", source)
                    self.assertEqual(
                        manifest["outfit_store_helpers"]["b150_cheat_upgrade_gate"]["enabled"],
                        enabled,
                    )
        finally:
            patcher.PATCHED = old_patched
            patcher.ENABLE_CHEAT_UPGRADES = old_enabled

    def test_calc_price_multiplier_coff_hooks_follow_cheat_gate(self):
        old_patched = patcher.PATCHED
        old_enabled = patcher.ENABLE_CHEAT_UPGRADES
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for enabled in (False, True):
                    patcher.PATCHED = root / ("enabled" if enabled else "disabled")
                    patcher.PATCHED.mkdir()
                    patcher.ENABLE_CHEAT_UPGRADES = enabled
                    shutil.copy2(
                        patcher.SRC_OBJS / "ScrollingStoreScene.obj",
                        patcher.PATCHED / "ScrollingStoreScene.obj",
                    )
                    manifest = {}

                    patcher.patch_scrolling_store_scene(manifest)

                    obj = CoffObject(patcher.PATCHED / "ScrollingStoreScene.obj")
                    calc = obj.symbol("?CalcPrice@CScrollingStoreScene@@AAEHW4EInventoryItem@@PA_N@Z")
                    section = obj.section(calc.section)
                    data = bytes(
                        obj.buf[
                            section.raw_ptr + calc.value :
                            section.raw_ptr + section.raw_size
                        ]
                    )
                    if enabled:
                        self.assertEqual(data[0x79:0x7C], b"\x0F\xAF\xC7")
                        self.assertEqual(data[0x7C], 0xE9)
                        self.assertEqual(data[0x83:0x85], b"\x8B\xC7")
                        self.assertEqual(data[0x85], 0xE9)
                        self.assertIn("_VF2ApplyPriceMultiplier", obj.symbol_by_name)
                        helper = obj.symbol("_VF2ApplyPriceMultiplier")
                        relocs = [
                            struct.unpack_from("<IIH", obj.buf, section.reloc_ptr + index * 10)
                            for index in range(section.nreloc)
                        ]
                        self.assertTrue(any(row[1] == helper.index for row in relocs))
                    else:
                        self.assertEqual(
                            data[0x79:0x83],
                            b"\x0F\xAF\xC7\x5F\x5E\x5B\x5D\xC2\x08\x00",
                        )
                        self.assertEqual(
                            data[0x83:0x8C],
                            b"\x8B\xC7\x5F\x5E\x5B\x5D\xC2\x08\x00",
                        )
                        self.assertNotIn("_VF2ApplyPriceMultiplier", obj.symbol_by_name)
                    self.assertEqual(
                        manifest["ScrollingStoreScene"]["price_multiplier"]["enabled"],
                        enabled,
                    )
        finally:
            patcher.PATCHED = old_patched
            patcher.ENABLE_CHEAT_UPGRADES = old_enabled

    def test_reset_achievements_cheat_upgrade_is_wired_to_native_reset(self):
        reset_rows = [
            item for item in patcher.CHEAT_UPGRADE_ITEMS
            if item["name"] == "Reset Achievements"
        ]

        self.assertEqual(len(reset_rows), 1)
        self.assertEqual(reset_rows[0]["item_id"], 0x124)
        self.assertEqual(
            patcher.VISIBLE_SPECIAL_UPGRADE_ICON_FILES[0x124],
            "cheat_reset_achievements.png",
        )

        source = Path(patcher.__file__).read_text(encoding="utf-8")
        self.assertIn("def normalize_visible_special_upgrade_icon", source)
        self.assertIn("status = \"normalized\"", source)
        self.assertIn("class CAchievement", source)
        self.assertIn("extern CAchievement Achievement;", source)
        self.assertIn("case 0x124:", source)
        self.assertIn("Achievement.Reset();", source)

    def test_holiday_outfit_item_ids_decode_to_body_values_50_53(self):
        for gender in patcher.OUTFIT_STORE_GENDERS:
            for body_value in patcher.HOLIDAY_BODY_VALUES:
                with self.subTest(gender=gender, body_value=body_value):
                    item_id = patcher.outfit_item_id_for_body(gender, body_value)

                    self.assertEqual(patcher.outfit_body_for_item(item_id), (gender, body_value))

    def test_outfit_entry_index_preserves_holiday_body_rows(self):
        body_count = len(patcher.OUTFIT_STORE_BODY_VALUES)

        for body_value in patcher.HOLIDAY_BODY_VALUES:
            with self.subTest(body_value=body_value):
                self.assertEqual(
                    patcher.outfit_store_entry_index("female", body_value),
                    patcher.OUTFIT_STORE_BODY_VALUES.index(body_value),
                )
                self.assertEqual(
                    patcher.outfit_store_entry_index("male", body_value),
                    body_count + patcher.OUTFIT_STORE_BODY_VALUES.index(body_value),
                )

    def test_string_lookup_bound_covers_all_male_outfit_rows(self):
        rows = []
        for entry in patcher.outfit_store_entries():
            short_id, long_id = patcher.outfit_string_ids_for_entry(entry["entry_index"])
            rows.extend([
                (short_id, "short", "text"),
                (long_id, "long", "text"),
            ])

        male_body_04 = patcher.outfit_store_entry_index("male", 4)
        _male_04_short, male_04_long = patcher.outfit_string_ids_for_entry(male_body_04)
        last_male = patcher.outfit_store_entry_index("male", patcher.OUTFIT_STORE_BODY_VALUES[-1])
        _last_short, last_long = patcher.outfit_string_ids_for_entry(last_male)
        one_past = patcher.string_lookup_one_past_for_rows(rows)

        self.assertGreaterEqual(one_past, male_04_long + 1)
        self.assertGreaterEqual(one_past, last_long + 1)

    def test_folder_backed_holiday_bodies_keep_stock_link_fallback(self):
        policy = patcher.holiday_body_link_lookup_policy()

        self.assertEqual(policy["stock_valid_rows"], [0, 49])
        self.assertEqual(policy["holiday_link_fallback_row"], 49)
        self.assertEqual(list(patcher.HOLIDAY_BODY_VALUES), [50, 51, 52, 53])
        self.assertLess(policy["holiday_link_fallback_row"], min(patcher.HOLIDAY_BODY_VALUES))
        self.assertIn("do not expand the stock body/action/sit sheets", policy["reason"])

    def test_outfit_helper_tracks_hand_and_use_synthetic_items_separately(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                helper = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
                helper.write_text("", encoding="ascii")

                patcher.write_outfit_store_helpers({})
                source = helper.read_text(encoding="ascii")

                self.assertIn("gVF2SyntheticOutfitToolInHand", source)
                self.assertIn("gVF2SyntheticOutfitToolInUse", source)
                self.assertIn("gVF2LastSyntheticOutfitByGender[2]", source)
                self.assertIn("VF2SyntheticOutfitSlotForActiveFlag", source)
                self.assertIn("activeFlagOffset == 0xA4", source)
                self.assertIn("activeFlagOffset == 0xA5", source)
                self.assertIn("selectedItems[2] = {gVF2SyntheticOutfitToolInUse, gVF2SyntheticOutfitToolInHand}", source)
                self.assertIn("VF2SetStockOutfitBodyForSyntheticItem", source)
                self.assertIn("InventoryManager.femaleOutfitBody = body", source)
                self.assertIn("InventoryManager.maleOutfitBody = body", source)
                self.assertIn("itemId == kVF2FemaleOutfitTrayItem", source)
        finally:
            patcher.PATCHED = old_patched

    def test_outfit_helper_embeds_expanded_flea_market_pool(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                helper = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
                helper.write_text("", encoding="ascii")

                patcher.write_outfit_store_helpers({})
                source = helper.read_text(encoding="ascii")

                self.assertIn("kVF2FleaMarketCategory = 0x0F", source)
                self.assertIn("kVF2FleaMarketGoodiesCount = 0x24", source)
                self.assertIn("extern EInventoryItem gGoodiesList[];", source)
                self.assertIn("return (int)gGoodiesList[index];", source)
                self.assertIn("return kVF2FleaMarketGoodiesCount;", source)
                self.assertIn("if (index < 0 || index >= kVF2FleaMarketGoodiesCount) return 0;", source)
                self.assertNotIn("VF2ExpandedFleaMarketCandidate", source)
                self.assertNotIn("inventory->HaveUpgrade(item)", source)
                self.assertNotIn("kVF2FleaMarketCategory = 3", source)
                self.assertNotIn("inventory->AvailableForSale(item)", source)
                self.assertIn("VF2GetExpandedFleaMarketCount", source)
                self.assertIn("VF2GetExpandedFleaMarketItem", source)
        finally:
            patcher.PATCHED = old_patched

    def test_main_scene_outfit_apply_resolver_manifest_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj_path = Path(tmp) / "theMainScene.obj"
            shutil.copy2(patcher.SRC_OBJS / "theMainScene.obj", obj_path)

            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = Path(tmp)
                manifest = {}

                patcher.patch_main_scene_outfit_body_apply(manifest)

                resolver = manifest["outfit_apply_body_resolver"]
                self.assertEqual(resolver["villager_body_offset"], hex(0x6A84))
                self.assertEqual(
                    [(row["offset"], row["stock_item"], row["gender_value"], row["helper"]) for row in resolver["patches"]],
                    [
                        (hex(0xCE3), hex(0x49), 0, "_VF2ResolveOutfitBodyForApply"),
                        (hex(0xD83), hex(0x4A), 1, "_VF2ResolveOutfitBodyForApply"),
                    ],
                )
            finally:
                patcher.PATCHED = old_patched

    def test_holiday_runtime_frames_prefer_generated_body_assets(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is required for Holiday body frame generation")

        if not (
            patcher.GENERATED_VILLAGER_BODIES
            / "Female"
            / "Body_50"
            / "Female_Body_50_actions_Frame_00.png"
        ).exists():
            self.skipTest("generated Holiday body frames are not available")

        old_out = patcher.OUT
        old_values = patcher.HOLIDAY_BODY_VALUES
        old_sets = patcher.HOLIDAY_BODY_SET_IDS
        old_specs = patcher.HOLIDAY_BODY_ROLE_SPECS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.OUT = Path(tmp)
                patcher.HOLIDAY_BODY_VALUES = (50,)
                patcher.HOLIDAY_BODY_SET_IDS = (51,)
                patcher.HOLIDAY_BODY_ROLE_SPECS = [
                    {
                        "role": "actions",
                        "source_range": (33, 33),
                        "columns": 15,
                        "sheets": {
                            "female": ("female_actions00.png", "Female Outfits", "FemaleBodies_0"),
                        },
                    }
                ]
                images = patcher.OUT / "Images"
                images.mkdir(parents=True)
                template = Image.new(
                    "RGBA",
                    (patcher.HOLIDAY_BODY_CELL_SIZE * 15, patcher.HOLIDAY_BODY_CELL_SIZE * 50),
                    (0, 0, 0, 0),
                )
                template.save(images / "female_actions00.png")

                manifest = {}
                patcher.sync_holiday_body_runtime_frames(manifest)

                frames = manifest["holiday_body_runtime_frames"]["frames"]
                self.assertEqual(len(frames), 1)
                self.assertEqual(frames[0]["source"], "generated_frame")
                self.assertFalse(manifest["holiday_body_runtime_frames"]["issues"])
        finally:
            patcher.OUT = old_out
            patcher.HOLIDAY_BODY_VALUES = old_values
            patcher.HOLIDAY_BODY_SET_IDS = old_sets
            patcher.HOLIDAY_BODY_ROLE_SPECS = old_specs


class HolidayBodyDrawHelperTests(unittest.TestCase):
    def test_main_scene_offsets_use_body_scale_not_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = Path(tmp)
                manifest = {}

                patcher.write_holiday_body_draw_helper(manifest)

                helper = (patcher.PATCHED / "vf2_villager_body_frames.cpp").read_text(encoding="ascii")
                self.assertIn("float scale,\n    float alpha", helper)
                self.assertIn("point.x += VF2ScaleFloatOffset(kOffsetX[index], scale);", helper)
                self.assertIn("point.y += VF2ScaleFloatOffset(kOffsetY[index], scale);", helper)
                self.assertIn("scene->DrawScaled(frameGrid, point, 0, 0, scale, alpha);", helper)
                self.assertNotIn("point.y += VF2ScaleFloatOffset(kOffsetY[index], alpha);", helper)
                self.assertIn("body scale followed by alpha", manifest["holiday_body_draw_helper"]["main_scene"])
            finally:
                patcher.PATCHED = old_patched


class HolidayOrnamentGateTests(unittest.TestCase):
    def with_temp_patched_objs(self, filenames, callback):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                for filename in filenames:
                    shutil.copy2(patcher.SRC_OBJS / filename, temp_root / filename)
                callback(temp_root)
        finally:
            patcher.PATCHED = old_patched

    def test_holiday_ornaments_are_an_optional_patcher_overlay(self):
        self.assertFalse(patcher.ENABLE_HOLIDAY_ORNAMENTS)

    def test_mobile_island_events_are_opt_in_for_normal_build_stability(self):
        self.assertFalse(patcher.ENABLE_ISLAND_EVENTS)

    def test_native_contract_reports_mobile_collection_table_for_normal_builds(self):
        contract = patcher.build_native_array_contract()

        self.assertFalse(contract["holiday_ornaments"]["enabled"])
        self.assertIn(
            "optional patch not selected",
            contract["holiday_ornaments"]["status"],
        )
        self.assertEqual(contract["holiday_ornaments"]["achievement"], "0x5f")
        self.assertEqual(contract["holiday_ornaments"]["achievement_target"], 12)
        self.assertEqual(contract["holiday_ornaments"]["goal_collector_target"], 13)

    def test_mobile_spawn_rect_contract_matches_ornament_reset_records(self):
        self.assertEqual(
            [rect for _symbol, rect in patcher.HOLIDAY_ORNAMENT_SPAWN_RECTS],
            [
                (0x112, 0x0C4, 0x2FA, 0x1BD),
                (0x098, 0x178, 0x19D, 0x26F),
                (0x08D, 0x568, 0x137, 0x750),
            ],
        )

    def test_holiday_ornament_small_sheet_covers_engine_frame_range(self):
        from PIL import Image

        with Image.open(patcher.HOLIDAY_ORNAMENT_SMALL_COLLECTABLES_SOURCE) as image:
            contract = patcher.holiday_ornament_small_collectables_sheet_contract(
                image.convert("RGBA")
            )

        self.assertEqual(contract["cell_size"], [40, 40])
        self.assertEqual(contract["grid"], [6, 16])
        self.assertEqual(contract["frame_count"], 96)
        self.assertEqual(contract["engine_frame_range"], [79, 90])
        self.assertEqual(contract["engine_index_formula"], "ECarrying - 0x4F")
        self.assertEqual(
            [row["frame"] for row in contract["visible_engine_frames"]],
            list(range(79, 91)),
        )
        self.assertTrue(
            all(row["alpha_pixels"] > 0 for row in contract["visible_engine_frames"])
        )

    def test_holiday_ornament_all_payload_sheets_keep_visible_engine_frames(self):
        from PIL import Image

        for source in (
            patcher.HOLIDAY_ORNAMENT_SMALL_COLLECTABLES_SOURCE,
            patcher.HOLIDAY_ORNAMENT_GLOWING_COLLECTABLES_SOURCE,
        ):
            with self.subTest(source=source):
                with Image.open(source) as image:
                    contract = patcher.holiday_ornament_small_collectables_sheet_contract(
                        image.convert("RGBA")
                    )
                self.assertEqual(contract["grid"], [6, 16])
                self.assertEqual(contract["engine_frame_range"], [79, 90])
                self.assertTrue(
                    all(row["alpha_pixels"] > 0 for row in contract["visible_engine_frames"])
                )

    def test_collection_scene_table_extends_to_mobile_ornament_page(self):
        def run(temp_root):
            manifest = {}

            patcher.patch_collection_scene_holiday_ornaments(manifest)
            obj = CoffObject(temp_root / "CollectionScene.obj")
            sym = obj.symbol("?gCollectable@@3PAW4ECarrying@@A")
            sec = obj.section(sym.section)
            raw = obj.buf[sec.raw_ptr + sym.value : sec.raw_ptr + sym.value + 72 * 4]
            values = list(struct.unpack("<72I", raw))

            expected = (
                list(range(0x4F, 0x73))
                + list(range(0x86, 0x9E))
                + list(range(patcher.HOLIDAY_ORNAMENT_COLLECTABLE_START, patcher.HOLIDAY_ORNAMENT_COLLECTABLE_END + 1))
            )
            self.assertEqual(values, expected)
            sm_sym = obj.symbol(
                "?sm_sCollectable@CCollectionScene@@0PAUSCollectable@1@A"
            )
            sm_sec = obj.section(sm_sym.section)
            sm_raw = (
                sm_sec.raw_ptr
                + sm_sym.value
                + 5 * patcher.HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT * 12
            )
            slots = [
                struct.unpack_from("<III", obj.buf, sm_raw + index * 12)
                for index in range(
                    patcher.HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT
                )
            ]
            self.assertEqual(
                slots,
                [
                    (
                        patcher.holiday_ornament_collection_item_image_id(
                            index,
                            patcher.holiday_body_descriptor_count()
                            if patcher.ENABLE_HOLIDAY_BODY_TYPES
                            else 0,
                        ),
                        *patcher.HOLIDAY_ORNAMENT_COLLECTION_SLOT_POSITIONS[
                            index
                        ],
                    )
                    for index in range(
                        patcher.HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT
                    )
                ],
            )
            self.assertEqual(
                patcher.HOLIDAY_ORNAMENT_COLLECTION_SLOT_POSITIONS,
                [
                    (round(x * 1.28), round(y * 1.28))
                    for x, y in patcher.HOLIDAY_ORNAMENT_MOBILE_SLOT_POSITIONS
                ],
            )
            self.assertEqual(manifest["CollectionSceneHolidayOrnaments"]["page"], 5)
            self.assertEqual(
                manifest["CollectionSceneHolidayOrnaments"]["page_starts"],
                ["0x4f", "0x5b", "0x67", "0x86", "0x92", "0x9e"],
            )
            mouse_sym = obj.symbol("?HandleMouse@CCollectionScene@@UAE_NHUldwPoint@@@Z")
            mouse_sec = obj.section(mouse_sym.section)
            mouse_data = bytes(obj.buf[mouse_sec.raw_ptr + mouse_sym.value : mouse_sec.raw_ptr + mouse_sec.raw_size])
            self.assertEqual(mouse_data[0x1EB], 0xE9)
            self.assertEqual(mouse_data[0x1F0 : 0x1F2], b"\x90\x90")
            tooltip_cave = 0x1EB + 5 + struct.unpack_from("<i", mouse_data, 0x1EC)[0]
            self.assertEqual(mouse_data[tooltip_cave : tooltip_cave + 3], b"\x83\xF8\x0F")
            self.assertEqual(
                mouse_data[tooltip_cave + 10 : tooltip_cave + 16],
                b"\x8D\x98\x42\x07\x00\x00",
            )
            self.assertEqual(
                tooltip_cave + 21,
                tooltip_cave + 5 + struct.unpack_from("<b", mouse_data, tooltip_cave + 4)[0],
            )
            for jump_off in (tooltip_cave + 16, tooltip_cave + 28):
                self.assertEqual(
                    jump_off + 5 + struct.unpack_from("<i", mouse_data, jump_off + 1)[0],
                    0x1F2,
                )
            self.assertEqual(
                manifest["CollectionSceneHolidayOrnaments"]["tooltip_rarity_label_ids"],
                ["0x751", "0x752", "0x753"],
            )
            draw_sym = obj.symbol("?DrawScene@CCollectionScene@@MAEXXZ")
            draw_sec = obj.section(draw_sym.section)
            draw_data = bytes(obj.buf[draw_sec.raw_ptr + draw_sym.value : draw_sec.raw_ptr + draw_sec.raw_size])
            self.assertEqual(draw_data[0x17D], 0xE9)
            self.assertEqual(draw_data[0x182 : 0x184], b"\x90\x90")
            draw_cave = 0x17D + 5 + struct.unpack_from(
                "<i",
                draw_data,
                0x17E,
            )[0]
            self.assertEqual(
                draw_data[draw_cave : draw_cave + 10],
                b"\xFF\x77\x14\xE8\x00\x00\x00\x00\x50\xE9",
            )
            self.assertEqual(
                draw_cave
                + 14
                + struct.unpack_from("<i", draw_data, draw_cave + 10)[0],
                0x184,
            )
            self.assertIn("_VF2CollectionPageCount@4", obj.symbol_by_name)
            self.assertNotIn("_VF2CollectionPageCount", obj.symbol_by_name)
            draw_relocs = [
                struct.unpack_from("<IIH", obj.buf, draw_sec.reloc_ptr + index * 10)
                for index in range(draw_sec.nreloc)
            ]
            self.assertIn(
                (
                    draw_sym.value + draw_cave + 4,
                    obj.symbol("_VF2CollectionPageCount@4").index,
                    patcher.IMAGE_REL_I386_REL32,
                ),
                draw_relocs,
            )
            activate_sym = obj.symbol("?Activate@CCollectionScene@@MAEX_N@Z")
            activate_sec = obj.section(activate_sym.section)
            activate_data = bytes(obj.buf[activate_sec.raw_ptr + activate_sym.value : activate_sec.raw_ptr + activate_sec.raw_size])
            self.assertIn(b"\xC7\x46\x2C\xFF\xFF\xFF\xFF", activate_data)
            self.assertNotIn(b"\x89\x46\x2C", activate_data)

            main_obj = CoffObject(temp_root / "theMainScene.obj")
            map_sym = main_obj.symbol("?MapClickFeedback@theMainScene@@IAEXUldwPoint@@@Z")
            map_sec = main_obj.section(map_sym.section)
            aggregate_helper_name = (
                "?CollectionCountWithHolidayOrnaments@CCollectableItem@@"
                "QBE?BHW4ECarrying@@_N11@Z"
            )
            aggregate_helper = main_obj.symbol(aggregate_helper_name)
            map_relocs = [
                struct.unpack_from("<IIH", main_obj.buf, map_sec.reloc_ptr + index * 10)
                for index in range(map_sec.nreloc)
            ]
            self.assertIn(
                (map_sym.value + 0x66B, aggregate_helper.index, patcher.IMAGE_REL_I386_REL32),
                map_relocs,
            )
            self.assertIn(b" / 72\x00", main_obj.buf)
            self.assertNotIn(b" / 60\x00", main_obj.buf)
            self.assertEqual(
                manifest["CollectionSceneHolidayOrnaments"]["main_scene_total"]["total"],
                72,
            )

        self.with_temp_patched_objs(["CollectionScene.obj", "theMainScene.obj"], run)

    def test_collectable_observers_register_all_mobile_ornaments(self):
        def run(temp_root):
            manifest = {}

            patcher.patch_collectable_holiday_ornament_observers(manifest)
            data = (temp_root / "Collectable.obj").read_bytes()

            for carrying in range(patcher.HOLIDAY_ORNAMENT_COLLECTABLE_START, patcher.HOLIDAY_ORNAMENT_COLLECTABLE_END + 1):
                with self.subTest(carrying=hex(carrying)):
                    self.assertIn(b"\x68" + struct.pack("<I", carrying), data)
            self.assertEqual(
                manifest["CollectableHolidayOrnamentObservers"]["registered_collectables"],
                [hex(item) for item in range(0x9E, 0xAA)],
            )

        self.with_temp_patched_objs(["Collectable.obj"], run)

    def test_ornamentologist_completion_hook_is_idempotent(self):
        def run(temp_root):
            manifest = {}

            patcher.patch_achievement_holiday_ornaments(manifest)
            obj = CoffObject(temp_root / "Achievement.obj")
            complete = obj.symbol(
                "?AchievementsComplete@CAchievement@@QAEHXZ"
            )
            complete_sec = obj.section(complete.section)
            complete_data = bytes(
                obj.buf[
                    complete_sec.raw_ptr + complete.value :
                    complete_sec.raw_ptr + complete_sec.raw_size
                ]
            )
            self.assertEqual(
                complete_data[0x23 : 0x26],
                b"\x83\xFE\x60",
            )
            achievement_list = obj.symbol(
                "?achievementList@@3PAUsAchievementListEntry@@A"
            )
            list_sec = obj.section(achievement_list.section)
            for achievement_id, target in (
                (0x4D, 6),
                (0x54, 13),
                (0x5F, 12),
            ):
                self.assertEqual(
                    struct.unpack_from(
                        "<I",
                        obj.buf,
                        list_sec.raw_ptr
                        + achievement_list.value
                        + achievement_id * patcher.ACHIEVEMENT_ROW_SIZE
                        + 4,
                    )[0],
                    target,
                )

            queue = obj.symbol(
                "?QueueAchievementNotify@CAchievement@@AAEXW4EAchievement@@@Z"
            )
            queue_sec = obj.section(queue.section)
            queue_data = bytes(
                obj.buf[
                    queue_sec.raw_ptr + queue.value :
                    queue_sec.raw_ptr + queue_sec.raw_size
                ]
            )
            self.assertEqual(queue_data[0x19 : 0x1C], b"\x83\xF8\x60")
            reset_queue = obj.symbol(
                "?ResetNotifyQueue@CAchievement@@AAEXXZ"
            )
            reset_queue_sec = obj.section(reset_queue.section)
            reset_queue_data = bytes(
                obj.buf[
                    reset_queue_sec.raw_ptr + reset_queue.value :
                    reset_queue_sec.raw_ptr + reset_queue_sec.raw_size
                ]
            )
            self.assertEqual(
                reset_queue_data[0x11 : 0x16],
                b"\xB9\x60\x00\x00\x00",
            )

            sym = obj.symbol("?SetComplete@CAchievement@@QAEXW4EAchievement@@@Z")
            sec = obj.section(sym.section)
            data = bytes(obj.buf[sec.raw_ptr + sym.value : sec.raw_ptr + sec.raw_size])

            self.assertEqual(data[0x15 : 0x17], b"\x75\x7E")
            self.assertEqual(data[0x88 : 0x8A], b"\x75\x0D")
            self.assertEqual(
                data[0x95 : 0xA7],
                b"\xEB\x10\x83\xFE\x5F\x75\x0B\x6A\x01"
                b"\x6A\x54\x8B\xCF\xE8\x00\x00\x00\x00",
            )
            relocs = [
                struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + index * 10)
                for index in range(sec.nreloc)
            ]
            self.assertIn(
                (
                    sym.value + 0xA3,
                    obj.symbol("?IncrementProgress@CAchievement@@QAEXW4EAchievement@@H@Z").index,
                    patcher.IMAGE_REL_I386_REL32,
                ),
                relocs,
            )

        self.with_temp_patched_objs(["Achievement.obj", "AchievementsScene.obj"], run)

    def test_collectable_item_registers_mobile_ornament_spawn_areas(self):
        def run(temp_root):
            manifest = {}

            patcher.patch_collectable_item_holiday_ornaments(manifest)
            item_patch = next(
                item
                for item in manifest["CollectableItemHolidayOrnaments"]["patches"]
                if item["function"] == "?Reset@CCollectableItem@@QAEXXZ"
            )

            self.assertEqual(item_patch["spawn_area_count"], 3)
            self.assertEqual(item_patch["base_collectable"], "0x9e")
            self.assertEqual(
                item_patch["mobile_spawn_rects"],
                [[hex(value) for value in rect] for _symbol, rect in patcher.HOLIDAY_ORNAMENT_SPAWN_RECTS],
            )
            patched_functions = {
                item["function"]
                for item in manifest["CollectableItemHolidayOrnaments"]["patches"]
            }
            self.assertEqual(
                patched_functions,
                {
                    "?Reset@CCollectableItem@@QAEXXZ",
                    "?IsCommonCollectable@CCollectableItem@@QBE?B_NW4ECarrying@@@Z",
                    "?IsUncommonCollectable@CCollectableItem@@QBE?B_NW4ECarrying@@@Z",
                    "?IsRareCollectable@CCollectableItem@@QBE?B_NW4ECarrying@@@Z",
                    "?CollectionCount@CCollectableItem@@QBE?BHW4ECarrying@@_N11@Z",
                    "?Drop@CCollectableItem@@UAEXAAVCVillager@@W4ECarrying@@@Z",
                },
            )

            obj = CoffObject(temp_root / "CollectableItem.obj")
            stock_obj = CoffObject(
                patcher.SRC_OBJS / "CollectableItem.obj"
            )
            for function_name in (
                "?Add@CCollectableItem@@QAEXW4ECarrying@@UldwPoint@@_N@Z",
                "?Find@CCollectableItem@@QAE?B_NAAVCVillager@@W4ECarrying@@AAUldwPoint@@@Z",
                "?WasItemSpawned@CCollectableItem@@QBE?B_NW4ECarrying@@@Z",
            ):
                patched_sym = obj.symbol(function_name)
                patched_sec = obj.section(patched_sym.section)
                stock_sym = stock_obj.symbol(function_name)
                stock_sec = stock_obj.section(stock_sym.section)
                self.assertEqual(
                    bytes(
                        obj.buf[
                            patched_sec.raw_ptr + patched_sym.value :
                            patched_sec.raw_ptr + patched_sec.raw_size
                        ]
                    ),
                    bytes(
                        stock_obj.buf[
                            stock_sec.raw_ptr + stock_sym.value :
                            stock_sec.raw_ptr + stock_sec.raw_size
                        ]
                    ),
                    function_name,
                )

            reset = obj.symbol("?Reset@CCollectableItem@@QAEXXZ")
            reset_sec = obj.section(reset.section)
            add_spawn = obj.symbol(
                "?AddSpawnArea@CCollectableItem@@"
                "QAEXUldwRect@@W4ECarrying@@@Z"
            )
            reset_relocs = [
                struct.unpack_from(
                    "<IIH",
                    obj.buf,
                    reset_sec.reloc_ptr + index * 10,
                )
                for index in range(reset_sec.nreloc)
            ]
            self.assertEqual(
                sum(
                    symbol_index == add_spawn.index
                    for _vaddr, symbol_index, _rtype in reset_relocs
                ),
                19,
            )

            drop = obj.symbol("?Drop@CCollectableItem@@UAEXAAVCVillager@@W4ECarrying@@@Z")
            drop_sec = obj.section(drop.section)
            drop_data = bytes(obj.buf[drop_sec.raw_ptr + drop.value : drop_sec.raw_ptr + drop_sec.raw_size])
            self.assertIn(b"\x68\x9E\x00\x00\x00\x31\xFF\xE9", drop_data)
            drop_meta = next(
                item
                for item in manifest[
                    "CollectableItemHolidayOrnaments"
                ]["patches"]
                if item["function"].startswith(
                    "?Drop@CCollectableItem"
                )
            )
            self.assertIn("coin-only", drop_meta["duplicate_route"])
            self.assertIn("Duplicate", drop_meta["duplicate_route"])

        self.with_temp_patched_objs(["CollectableItem.obj"], run)

    def test_stock_collectable_add_keeps_generic_rarity_roll_contract(self):
        obj = CoffObject(patcher.SRC_OBJS / "CollectableItem.obj")
        sym = obj.symbol("?Add@CCollectableItem@@QAEXW4ECarrying@@UldwPoint@@_N@Z")
        sec = obj.section(sym.section)
        data = bytes(
            obj.buf[sec.raw_ptr + sym.value : sec.raw_ptr + sec.raw_size]
        )

        self.assertIn(b"\x6A\x04", data)
        self.assertIn(b"\x03\xBC\x8B\x94\x03\x00\x00", data)
        self.assertIn(b"\x83\xC7\x04", data)
        self.assertIn(b"\x83\xC7\x08", data)
        self.assertIn(b"\x89\xBE\x50\x03\x00\x00", data)
        self.assertEqual(
            data[0x194 : 0x19F],
            b"\x8A\x83\xA8\x08\x00\x00\x6A\x04\x88\x45\x0B",
        )
        self.assertEqual(data[0x1B0 : 0x1B2], b"\x6A\x64")
        self.assertEqual(
            data[0x1C1 : 0x1CD],
            b"\x84\xD2\x0F\x95\xC1\x8D\x0C\x8D\x04\x00\x00\x00",
        )
        self.assertEqual(
            data[0x1D8 : 0x1EA],
            b"\x84\xD2\xC7\x45\x14\x11\x00\x00\x00"
            b"\xB8\x22\x00\x00\x00\x0F\x44\x45\x14",
        )

    def test_workspace_collection_art_maps_to_twelve_collectibles(self):
        self.assertEqual(
            len(patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES),
            patcher.HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT,
        )
        runtime_names = [entry[0] for entry in patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES]
        source_names = [entry[1] for entry in patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES]

        self.assertEqual(len(runtime_names), len(set(runtime_names)))
        self.assertEqual(len(source_names), len(set(source_names)))
        self.assertFalse(any("CandyCane" in name for name in source_names))
        asset_manifest = json.loads(
            (
                patcher.HOLIDAY_ORNAMENT_PREEXTRACTED_ART_DIR
                / "asset-manifest.json"
            ).read_text(encoding="utf-8")
        )
        records = {
            row["filename"]: row
            for row in asset_manifest["assets"]
        }
        expected_names = set(runtime_names) | {
            patcher.HOLIDAY_ORNAMENT_BACKGROUND_FILENAME
        }
        self.assertEqual(set(records), expected_names)
        for name, record in records.items():
            source = (
                patcher.HOLIDAY_ORNAMENT_PREEXTRACTED_ART_DIR / name
            )
            self.assertTrue(source.is_file(), name)
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(),
                record["sha256"],
                name,
            )

    def test_collection_art_sync_uses_only_tracked_canonical_assets(self):
        old_out = patcher.OUT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.OUT = Path(tmp)
                manifest = {}

                patcher.sync_holiday_ornament_collection_art(manifest)

                art = manifest["holiday_ornament_collection_art"]
                self.assertEqual(
                    art["status"],
                    "copied_from_workspace_preextracted_assets",
                )
                self.assertEqual(len(art["entries"]), 12)
                self.assertEqual(
                    art["background"]["dimensions"],
                    [1024, 768],
                )
                for row in art["entries"]:
                    target = patcher.OUT / "Images" / row["path"]
                    self.assertTrue(target.is_file())
                    self.assertEqual(
                        hashlib.sha256(target.read_bytes()).hexdigest(),
                        row["sha256"],
                    )
        finally:
            patcher.OUT = old_out

    def test_holiday_disabled_art_cleanup_removes_only_collection_payload(self):
        old_out = patcher.OUT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.OUT = Path(tmp)
                image_root = patcher.OUT / "Images"
                collection_root = image_root / "CollectionOrnaments"
                collection_root.mkdir(parents=True)
                background = (
                    image_root
                    / patcher.HOLIDAY_ORNAMENT_BACKGROUND_FILENAME
                )
                background.write_bytes(b"background")
                for runtime_name, _source_name, _placeholder_name in (
                    patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES
                ):
                    (collection_root / runtime_name).write_bytes(b"icon")
                unrelated = collection_root / "keep-me.png"
                unrelated.write_bytes(b"unrelated")
                manifest = {}

                patcher.remove_holiday_ornament_collection_art(manifest)

                self.assertFalse(background.exists())
                for runtime_name, _source_name, _placeholder_name in (
                    patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES
                ):
                    self.assertFalse(
                        (collection_root / runtime_name).exists()
                    )
                self.assertTrue(unrelated.exists())
                self.assertEqual(
                    len(
                        manifest["holiday_ornament_collection_art"][
                            "removed"
                        ]
                    ),
                    13,
                )
        finally:
            patcher.OUT = old_out

    def test_the_collector_uses_relocation_only_holiday_offer_counts(self):
        def run(temp_root):
            manifest = {}

            patcher.patch_the_collector_holiday_ornaments(manifest)
            obj = CoffObject(temp_root / "IslandEvents.obj")
            sym = obj.symbol("?CanFire@CEventTheCollector@@UAE_NXZ")
            sec = obj.section(sym.section)
            data = bytes(obj.buf[sec.raw_ptr + sym.value : sec.raw_ptr + sec.raw_size])
            stock_obj = CoffObject(patcher.SRC_OBJS / "IslandEvents.obj")
            stock_sym = stock_obj.symbol(
                "?CanFire@CEventTheCollector@@UAE_NXZ"
            )
            stock_sec = stock_obj.section(stock_sym.section)
            self.assertEqual(
                data,
                bytes(
                    stock_obj.buf[
                        stock_sec.raw_ptr + stock_sym.value :
                        stock_sec.raw_ptr + stock_sec.raw_size
                    ]
                ),
            )
            aggregate_helper = obj.symbol(
                "?CollectionCountWithHolidayOrnaments@CCollectableItem@@"
                "QBE?BHW4ECarrying@@_N11@Z"
            )
            stock_count = obj.symbol(
                "?CollectionCount@CCollectableItem@@"
                "QBE?BHW4ECarrying@@_N11@Z"
            )
            relocs = {
                vaddr: (symbol_index, rtype)
                for vaddr, symbol_index, rtype in (
                    struct.unpack_from(
                        "<IIH",
                        obj.buf,
                        sec.reloc_ptr + index * 10,
                    )
                    for index in range(sec.nreloc)
                )
            }
            for operand_off in (0x88, 0xFB, 0x171):
                self.assertEqual(
                    relocs[sym.value + operand_off],
                    (
                        aggregate_helper.index,
                        patcher.IMAGE_REL_I386_REL32,
                    ),
                )
            self.assertEqual(
                relocs[sym.value + 0x1AC],
                (stock_count.index, patcher.IMAGE_REL_I386_REL32),
            )
            meta = manifest["TheCollectorHolidayOrnaments"]
            self.assertEqual(len(meta["offer_count_relocations"]), 3)
            self.assertIn("stock eligibility", meta["availability_route"])
            self.assertEqual(meta["achievement_reset"], "0x5f")
            self.assertTrue(meta["keep_choice_branch"]["unchanged"])
            impact = obj.symbol("?ImpactGame@CEventTheCollector@@UAEXH@Z")
            impact_sec = obj.section(impact.section)
            impact_data = bytes(
                obj.buf[impact_sec.raw_ptr + impact.value : impact_sec.raw_ptr + impact_sec.raw_size]
            )
            self.assertEqual(impact_data[0x07 : 0x09], b"\x75\x66")
            impact_relocs = {
                vaddr: (symbol_index, rtype)
                for vaddr, symbol_index, rtype in (
                    struct.unpack_from(
                        "<IIH",
                        obj.buf,
                        impact_sec.reloc_ptr + index * 10,
                    )
                    for index in range(impact_sec.nreloc)
                )
            }
            reset_helper = obj.symbol(
                "?ResetHolidayOrnamentCollectorProgress@CAchievement@@"
                "QAEXW4EAchievement@@@Z"
            )
            self.assertEqual(
                impact_relocs[impact.value + 0x6B],
                (
                    reset_helper.index,
                    patcher.IMAGE_REL_I386_REL32,
                ),
            )

        self.with_temp_patched_objs(["IslandEvents.obj"], run)

    def test_holiday_ornament_native_contract_validates_sixth_page_count_route(self):
        def run(temp_root):
            manifest = {}
            (temp_root / "vf2_special_upgrade_effects.cpp").write_text(
                "extern \"C\" int __cdecl VF2CollectionPageCount(int page) {\n"
                "    static const int starts[6] = {0x4F, 0x5B, 0x67, 0x86, 0x92, 0x9E};\n"
                "    return starts[page];\n"
                "}\n"
                "void CAchievement::ResetHolidayOrnamentCollectorProgress(\n"
                "    EAchievement stockAchievement\n"
                ") {\n"
                "    ResetSingleAchievementProgress((EAchievement)0x5F);\n"
                "    ResetSingleAchievementProgress(stockAchievement);\n"
                "}\n",
                encoding="ascii",
            )
            helper_path = temp_root / 'vf2_special_upgrade_effects.cpp'
            helper_path.write_text(
                helper_path.read_text(encoding='ascii').replace(
                    '__cdecl VF2CollectionPageCount',
                    '__stdcall VF2CollectionPageCount',
                ),
                encoding='ascii',
            )

            patcher.patch_achievement_holiday_ornaments(manifest)
            patcher.patch_collectable_item_holiday_ornaments(manifest)
            patcher.patch_collectable_holiday_ornament_observers(manifest)
            patcher.patch_collection_scene_holiday_ornaments(manifest)
            patcher.patch_the_collector_holiday_ornaments(manifest)
            patcher.validate_holiday_ornament_native_contract(manifest)

            scene_contract = manifest["holiday_ornament_native_contract"]["collection_scene"]
            self.assertEqual(scene_contract["page_starts"][-1], "0x9e")
            self.assertIn("_VF2CollectionPageCount", scene_contract["page_count_route"])
            native_contract = manifest["holiday_ornament_native_contract"]
            self.assertTrue(
                native_contract["collection_state"][
                    "load_state_covers_holiday_range"
                ]
            )
            self.assertEqual(
                native_contract["spawning"]["total_spawn_area_count"],
                19,
            )
            self.assertEqual(
                native_contract["achievement"],
                {
                    "collection_master_target": 6,
                    "goal_collector_target": 13,
                    "ornamentologist_target": 12,
                    "visible_order_bound": 0x60,
                    "notify_queue_bound": 0x60,
                },
            )
            self.assertFalse(
                native_contract["control_flow"]["find_code_cave"]
            )
            self.assertFalse(
                native_contract["control_flow"][
                    "was_item_spawned_code_cave"
                ]
            )
            self.assertTrue(
                native_contract["control_flow"]["page_count_code_cave"]
            )

        self.with_temp_patched_objs(
            [
                "Achievement.obj",
                "AchievementsScene.obj",
                "CollectableItem.obj",
                "Collectable.obj",
                "CollectionScene.obj",
                "theMainScene.obj",
                "IslandEvents.obj",
            ],
            run,
        )


class RuntimePayloadContractTests(unittest.TestCase):
    def test_previous_build_source_prefers_highest_lower_b_number(self):
        old_root = patcher.ROOT
        old_out = patcher.OUT
        old_env = patcher.os.environ.pop(patcher.PREVIOUS_BUILD_ENV, None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                patcher.ROOT = tmp
                outputs = tmp / "outputs"
                outputs.mkdir()
                for name in (
                    "VF2-Mobile-Furniture-With-Island-Events-B92-Older",
                    "VF2-B93-Release",
                    "VF2-Mobile-Furniture-With-Island-Events-B94-Current",
                ):
                    (outputs / name).mkdir()
                patcher.OUT = outputs / "VF2-Mobile-Furniture-With-Island-Events-B94-Current"

                roots = patcher.previous_build_source_dirs()

                self.assertEqual(roots[0].name, "VF2-B93-Release")
        finally:
            patcher.ROOT = old_root
            patcher.OUT = old_out
            if old_env is not None:
                patcher.os.environ[patcher.PREVIOUS_BUILD_ENV] = old_env

    def test_seed_from_previous_build_copies_runtime_folder(self):
        old_root = patcher.ROOT
        old_out = patcher.OUT
        old_env = patcher.os.environ.pop(patcher.PREVIOUS_BUILD_ENV, None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                patcher.ROOT = tmp
                outputs = tmp / "outputs"
                previous = outputs / "VF2-Mobile-Furniture-With-Island-Events-B93-Previous"
                out = outputs / "VF2-Mobile-Furniture-With-Island-Events-B94-Current"
                (previous / "Images").mkdir(parents=True)
                (previous / "Sounds").mkdir()
                (previous / "Images" / "previous.png").write_bytes(b"image")
                (previous / "Sounds" / "previous.ogg").write_bytes(b"sound")
                (previous / "patch-manifest.json").write_text("{}", encoding="ascii")
                patcher.OUT = out

                manifest = {}
                patcher.seed_from_previous_build(manifest)

                self.assertTrue((out / "Images" / "previous.png").is_file())
                self.assertTrue((out / "Sounds" / "previous.ogg").is_file())
                self.assertEqual(manifest["previous_build_seed"]["source"], str(previous))
        finally:
            patcher.ROOT = old_root
            patcher.OUT = old_out
            if old_env is not None:
                patcher.os.environ[patcher.PREVIOUS_BUILD_ENV] = old_env

    def test_vanilla_runtime_sources_do_not_use_modded_outputs_by_default(self):
        old_env = patcher.os.environ.pop("VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK", None)
        try:
            roots = patcher.vanilla_runtime_payload_source_dirs()

            self.assertIn(patcher.ROOT / "work" / "vanilla_runtime_payload", roots)
            self.assertFalse(any("outputs" in root.parts for root in roots))
        finally:
            if old_env is not None:
                patcher.os.environ["VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK"] = old_env

    def test_release_baseline_tracks_standalone_b98_current_zip(self):
        self.assertEqual(patcher.OFFICIAL_B93_RELEASE_TAG, "B98-current-vf2-modded-build")
        self.assertEqual(patcher.OFFICIAL_B93_RELEASE_ASSET, "Current VF2 Modded Build! B98.zip")
        self.assertEqual(
            patcher.OFFICIAL_B93_RELEASE_SHA256,
            "63ad60cfb963008bed7cc6706f05146ed7ed6a8f40aa785204c9ccefa36dbf55",
        )
        self.assertIn("VF2-B*-Release", patcher.PREVIOUS_BUILD_OUTPUT_GLOBS)

    def test_legacy_output_runtime_sources_are_explicit_opt_in(self):
        old_env = patcher.os.environ.get("VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK")
        try:
            patcher.os.environ["VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK"] = "1"
            roots = patcher.vanilla_runtime_payload_source_dirs()

            self.assertTrue(any("outputs" in root.parts for root in roots))
        finally:
            if old_env is None:
                patcher.os.environ.pop("VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK", None)
            else:
                patcher.os.environ["VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK"] = old_env

    def with_temp_runtime(self, callback):
        old_out = patcher.OUT
        old_min_images = patcher.RUNTIME_MIN_IMAGE_FILE_COUNT
        old_min_sounds = patcher.RUNTIME_MIN_SOUND_FILE_COUNT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.OUT = Path(tmp)
                patcher.RUNTIME_MIN_IMAGE_FILE_COUNT = len(patcher.RUNTIME_REQUIRED_IMAGE_FILES)
                patcher.RUNTIME_MIN_SOUND_FILE_COUNT = 1
                callback(Path(tmp))
        finally:
            patcher.OUT = old_out
            patcher.RUNTIME_MIN_IMAGE_FILE_COUNT = old_min_images
            patcher.RUNTIME_MIN_SOUND_FILE_COUNT = old_min_sounds

    def write_minimal_runtime_payload(self, root):
        for dirname in patcher.OFFICIAL_B93_RELEASE_REQUIRED_DIRS:
            (root / dirname).mkdir(parents=True)
        for filename in patcher.VANILLA_RUNTIME_REQUIRED_FILES:
            (root / filename).write_bytes(b"x")
        for filename in patcher.RUNTIME_REQUIRED_IMAGE_FILES:
            (root / "Images" / filename).write_bytes(b"x")
        (root / "Sounds" / "sound00.wav").write_bytes(b"x")
        for filename in patcher.DESKTOP_RUNTIME_DLL_NAMES:
            (root / filename).write_bytes(b"x")

    def test_sync_accepts_clean_asset_payload_without_root_launcher_files(self):
        old_out = patcher.OUT
        old_sources = patcher.VANILLA_RUNTIME_PAYLOAD_SOURCE_DIRS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                source = tmp / "source"
                out = tmp / "out"
                patcher.OUT = out
                patcher.VANILLA_RUNTIME_PAYLOAD_SOURCE_DIRS = (source,)
                (source / "Images").mkdir(parents=True)
                (source / "Sounds").mkdir(parents=True)
                (source / "Images" / "loading.jpg").write_bytes(b"image")
                (source / "Sounds" / "button_click_switch.ogg").write_bytes(b"sound")

                manifest = {}
                patcher.sync_vanilla_runtime_payload(manifest)

                self.assertTrue((out / "Images" / "loading.jpg").is_file())
                self.assertTrue((out / "Sounds" / "button_click_switch.ogg").is_file())
                self.assertEqual(
                    manifest["base_runtime_payload"]["missing_root_files"],
                    list(patcher.VANILLA_RUNTIME_REQUIRED_FILES),
                )
        finally:
            patcher.OUT = old_out
            patcher.VANILLA_RUNTIME_PAYLOAD_SOURCE_DIRS = old_sources

    def test_accepts_complete_runtime_payload(self):
        def run(root):
            manifest = {}
            self.write_minimal_runtime_payload(root)

            patcher.validate_runtime_payload_contract(manifest)

            self.assertEqual(manifest["runtime_payload_contract"]["status"], "validated")

        self.with_temp_runtime(run)

    def test_rejects_partial_images_payload(self):
        def run(root):
            manifest = {}
            self.write_minimal_runtime_payload(root)
            (root / "Images" / "loading.jpg").unlink()

            with self.assertRaisesRegex(RuntimeError, "missing required base image: Images/loading.jpg"):
                patcher.validate_runtime_payload_contract(manifest)

        self.with_temp_runtime(run)


if __name__ == "__main__":
    unittest.main()
