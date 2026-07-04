#!/usr/bin/env python3
import copy
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

    def test_private_tv_screen_boxes_match_b84_geometry(self):
        self.assertEqual(patcher.VF3_TV_ANIMATION_SCREEN_BOXES["Large"], (4, 5, 65, 80))
        self.assertEqual(patcher.VF3_TV_ANIMATION_SCREEN_BOXES["Small"], (2, 2, 48, 60))
        self.assertEqual(patcher.VF3_TV_ANIMATION_SCREEN_BOXES["FathersFavorite"], (5, 8, 96, 104))
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


class OutfitStoreMappingTests(unittest.TestCase):
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

    def test_holiday_ornaments_are_opt_in_for_normal_build_stability(self):
        self.assertFalse(patcher.ENABLE_HOLIDAY_ORNAMENTS)

    def test_mobile_island_events_are_opt_in_for_normal_build_stability(self):
        self.assertFalse(patcher.ENABLE_ISLAND_EVENTS)

    def test_native_contract_reports_mobile_collection_table_for_normal_builds(self):
        contract = patcher.build_native_array_contract()

        self.assertFalse(contract["holiday_ornaments"]["enabled"])
        self.assertIn("disabled", contract["holiday_ornaments"]["status"])
        self.assertEqual(contract["holiday_ornaments"]["achievement"], "0x5f")
        self.assertEqual(contract["holiday_ornaments"]["achievement_target"], 12)
        self.assertEqual(contract["holiday_ornaments"]["goal_collector_target"], 13)

    def test_mobile_spawn_rect_contract_matches_ornament_reset_records(self):
        self.assertEqual(
            [rect for _symbol, rect in patcher.HOLIDAY_ORNAMENT_SPAWN_RECTS],
            [
                (0x634, 0x0B4, 0x764, 0x302),
                (0x112, 0x0C4, 0x2FA, 0x1BD),
                (0x098, 0x178, 0x19D, 0x26F),
                (0x08D, 0x568, 0x137, 0x750),
            ],
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
            self.assertEqual(manifest["CollectionSceneHolidayOrnaments"]["page"], 5)

        self.with_temp_patched_objs(["CollectionScene.obj"], run)

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

    def test_collectable_item_registers_mobile_ornament_spawn_areas(self):
        def run(temp_root):
            manifest = {}

            patcher.patch_collectable_item_holiday_ornaments(manifest)
            item_patch = next(
                item
                for item in manifest["CollectableItemHolidayOrnaments"]["patches"]
                if item["function"] == "?Reset@CCollectableItem@@QAEXXZ"
            )

            self.assertEqual(item_patch["spawn_area_count"], 4)
            self.assertEqual(item_patch["base_collectable"], "0x9e")
            self.assertEqual(
                item_patch["mobile_spawn_rects"],
                [[hex(value) for value in rect] for _symbol, rect in patcher.HOLIDAY_ORNAMENT_SPAWN_RECTS],
            )

        self.with_temp_patched_objs(["CollectableItem.obj"], run)

    def test_supplied_collection_art_maps_to_twelve_collectibles(self):
        self.assertEqual(
            len(patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES),
            patcher.HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT,
        )
        runtime_names = [entry[0] for entry in patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES]
        source_names = [entry[1] for entry in patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES]

        self.assertEqual(len(runtime_names), len(set(runtime_names)))
        self.assertEqual(len(source_names), len(set(source_names)))
        self.assertFalse(any("CandyCane" in name for name in source_names))


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
