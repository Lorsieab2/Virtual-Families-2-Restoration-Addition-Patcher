#!/usr/bin/env python3
import copy
import tempfile
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher


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

    def test_private_tv_screen_boxes_are_inset_from_bezels(self):
        self.assertEqual(patcher.VF3_TV_ANIMATION_SCREEN_BOXES["Large"], (5, 6, 63, 77))
        self.assertEqual(patcher.VF3_TV_ANIMATION_SCREEN_BOXES["Small"], (3, 3, 46, 57))
        self.assertEqual(patcher.VF3_TV_ANIMATION_SCREEN_BOXES["FathersFavorite"], (8, 10, 90, 96))
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


class HolidayOrnamentGateTests(unittest.TestCase):
    def test_holiday_ornaments_are_disabled_by_default(self):
        self.assertFalse(patcher.ENABLE_HOLIDAY_ORNAMENTS)

    def test_native_contract_reports_stock_collections_for_normal_builds(self):
        contract = patcher.build_native_array_contract()

        self.assertFalse(contract["holiday_ornaments"]["enabled"])
        self.assertIn("48 collectibles", contract["holiday_ornaments"]["status"])


class RuntimePayloadContractTests(unittest.TestCase):
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
        (root / "Images").mkdir(parents=True)
        (root / "Sounds").mkdir(parents=True)
        for filename in patcher.VANILLA_RUNTIME_REQUIRED_FILES:
            (root / filename).write_bytes(b"x")
        for filename in patcher.RUNTIME_REQUIRED_IMAGE_FILES:
            (root / "Images" / filename).write_bytes(b"x")
        (root / "Sounds" / "sound00.wav").write_bytes(b"x")
        for filename in patcher.DESKTOP_RUNTIME_DLL_NAMES:
            (root / filename).write_bytes(b"x")
        vc90 = root / patcher.VC90_CRT_ASSEMBLY_NAME
        vc90.mkdir()
        (vc90 / f"{patcher.VC90_CRT_ASSEMBLY_NAME}.manifest").write_text("<assembly/>", encoding="ascii")
        for filename in patcher.VC90_CRT_DLL_NAMES:
            (vc90 / filename).write_bytes(b"x")

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
