#!/usr/bin/env python3
"""The hairstyle rows are a real, reachable feature.

The mechanism landed inert: gVF2LastSyntheticHeadByGender was read in two
places and written in none, so VF2ApplyPendingHairstyle could only ever return
-1 and no hairstyle could ever be applied. These tests pin the parts that make
it live -- the write, the store rows that produce a selection to write, and the
routing that lets a hairstyle and an outfit share the one tool.
"""
import re
import unittest

import patch_mobile_furniture_pack as patcher


def _generated_source():
    """The generated C, as a plain string with the f-string braces reduced."""
    path = patcher.ROOT / "work" / "patch_mobile_furniture_pack.py"
    return path.read_text(encoding="utf-8")


class TestHairstyleStoreRows(unittest.TestCase):
    def test_one_row_per_head_per_gender(self):
        entries = patcher.head_store_entries()
        self.assertEqual(len(entries), patcher.HEAD_STORE_ENTRY_COUNT)
        self.assertEqual(len(entries), 2 * patcher.HEAD_STORE_VALUE_COUNT)
        self.assertEqual(
            {e["gender"] for e in entries}, {"female", "male"}
        )

    def test_the_head_count_matches_the_real_sheets(self):
        for sheet in ("female_heads", "male_heads"):
            spec = patcher.CHARACTER_SHEET_SPECS[sheet]
            self.assertEqual(
                spec["original_grid"][1], patcher.HEAD_STORE_VALUE_COUNT,
                f"{sheet} row count and the store row count must agree",
            )
            self.assertEqual(tuple(spec["cell_size"]), patcher.HEAD_STORE_CELL_SIZE)

    def test_item_ids_are_unique_and_clear_of_the_outfits(self):
        head_ids = {e["item_id"] for e in patcher.head_store_entries()}
        outfit_ids = {e["item_id"] for e in patcher.outfit_store_entries()}
        self.assertEqual(len(head_ids), patcher.HEAD_STORE_ENTRY_COUNT)
        self.assertEqual(head_ids & outfit_ids, set())

    def test_item_ids_match_the_ranges_the_generated_c_expects(self):
        src = _generated_source()
        female = re.search(
            r"kVF2HeadStoreFemaleBase = \{HEAD_STORE_GENDER_ITEM_BASES\[\"female\"\]\}", src
        )
        male = re.search(
            r"kVF2HeadStoreMaleBase = \{HEAD_STORE_GENDER_ITEM_BASES\[\"male\"\]\}", src
        )
        count = re.search(r"kVF2HeadStoreValueCount = \{HEAD_STORE_VALUE_COUNT\}", src)
        self.assertTrue(
            female and male and count,
            "the generated C must take these from the Python constants, or the "
            "two halves can drift apart",
        )

    def test_the_id_mapping_round_trips(self):
        for entry in patcher.head_store_entries():
            self.assertEqual(
                patcher.head_for_item(entry["item_id"]),
                (entry["gender"], entry["head_value"]),
            )
        # An outfit id must not resolve as a hairstyle.
        for entry in patcher.outfit_store_entries():
            self.assertIsNone(patcher.head_for_item(entry["item_id"]))


class TestHairstyleIconsComeFromTheGameSheets(unittest.TestCase):
    def test_icons_are_cut_from_the_head_sheets(self):
        self.assertEqual(
            set(patcher.HEAD_STORE_ICON_SOURCE_SHEETS.values()),
            {"female_heads00.png", "male_heads00.png"},
            "hairstyle icons must come from the game's own head art",
        )

    def test_the_icon_frame_exists_in_those_sheets(self):
        for sheet in ("female_heads", "male_heads"):
            frames = patcher.CHARACTER_SHEET_SPECS[sheet]["original_grid"][0]
            self.assertLess(patcher.HEAD_STORE_ICON_FRAME, frames)

    def test_icon_image_ids_are_appended_after_every_other_block(self):
        hd = (
            patcher.holiday_body_descriptor_count()
            if patcher.ENABLE_HOLIDAY_BODY_TYPES
            else 0
        )
        base = patcher.head_icon_image_base(hd)
        # Every other image base must start at or below the hairstyle base, so
        # adding hairstyles cannot shift an id that was already assigned.
        for other in (
            patcher.outfit_icon_image_base(hd),
            patcher.mobile_renovation_image_base(hd),
            patcher.holiday_ornament_collection_image_base(hd),
            patcher.ai_bathroom2_image_base(hd),
            patcher.renovation_curtain_image_base(hd),
        ):
            self.assertLessEqual(other, base)

    def test_icon_ids_are_contiguous_and_unique(self):
        hd = (
            patcher.holiday_body_descriptor_count()
            if patcher.ENABLE_HOLIDAY_BODY_TYPES
            else 0
        )
        ids = [
            patcher.head_icon_image_id(e["gender"], e["head_value"], hd)
            for e in patcher.head_store_entries()
        ]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids, list(range(min(ids), min(ids) + len(ids))))


class TestHairstyleStringsAreAppended(unittest.TestCase):
    def test_strings_start_after_every_existing_block(self):
        base = patcher.head_store_string_base()
        self.assertGreater(base, patcher.same_sex_marriage_string_ids()[1])
        self.assertGreater(base, patcher.divorce_spouse_string_ids()[1])

    def test_two_strings_per_row_with_no_overlap(self):
        seen = set()
        for entry in patcher.head_store_entries():
            short_id, long_id = patcher.head_string_ids_for_entry(entry["entry_index"])
            self.assertEqual(long_id, short_id + 1)
            self.assertNotIn(short_id, seen)
            self.assertNotIn(long_id, seen)
            seen.update((short_id, long_id))
        self.assertEqual(len(seen), 2 * patcher.HEAD_STORE_ENTRY_COUNT)


class TestTheMissingWriteIsSupplied(unittest.TestCase):
    """The actual defect: the selection array was never written."""

    def test_the_selection_array_is_written_not_only_read(self):
        src = _generated_source()
        writes = re.findall(
            r"gVF2LastSyntheticHeadByGender\[[^\]]+\]\s*=", src
        )
        self.assertTrue(
            writes,
            "gVF2LastSyntheticHeadByGender must be assigned somewhere, or "
            "VF2ApplyPendingHairstyle can only ever return -1",
        )

    def test_a_purchase_records_the_selection(self):
        src = _generated_source()
        purchase = re.search(
            r"VF2PurchaseOutfitStoreItem\(int itemId\) \{\{(.*?)\n\}\}", src, re.S
        )
        self.assertIsNotNone(purchase)
        self.assertIn(
            "VF2SetSelectedHeadForSyntheticItem", purchase.group(1),
            "buying a hairstyle must record it, the way buying an outfit does",
        )

    def test_selecting_one_kind_clears_the_other(self):
        # A hairstyle and an outfit are mutually exclusive uses of one tool.
        src = _generated_source()
        setter = re.search(
            r"VF2SetSelectedHeadForSyntheticItem\(int itemId\) \{\{(.*?)\n\}\}",
            src, re.S,
        )
        self.assertIsNotNone(setter)
        self.assertIn("gVF2LastSyntheticOutfitByGender[gender] = 0", setter.group(1))

    def test_the_apply_path_hands_back_the_existing_body(self):
        src = _generated_source()
        apply = re.search(
            r"VF2ApplyPendingHairstyle\(int stockGender\) \{\{(.*?)\n\}\}", src, re.S
        )
        self.assertIsNotNone(apply)
        body = apply.group(1)
        self.assertIn("kVF2VillagerHeadOffset) = head", body,
                      "it must write the head field")
        self.assertIn("return *(int *)(villager + kVF2VillagerBodyOffset)", body,
                      "and return the current body so the stock write is a no-op")

    def test_the_crashing_callsite_route_stays_uninstalled(self):
        # Retargeting the final-apply callsite is what crashed in B96.
        src = _generated_source()
        self.assertEqual(
            src.count("VF2ApplyOutfitToolField"), 1,
            "VF2ApplyOutfitToolField must remain defined but never installed",
        )


class TestHairstyleRowsReachTheStore(unittest.TestCase):
    def test_hairstyles_join_the_clothing_list(self):
        src = _generated_source()
        self.assertIn("clothing_ids = outfit_ids + head_ids", src)

    def test_the_store_accessors_answer_for_hairstyle_ids(self):
        src = _generated_source()
        for accessor in (
            "VF2GetOutfitStorePrice",
            "VF2GetOutfitStoreIconImage",
            "VF2GetOutfitStoreShortDesc",
            "VF2GetOutfitStoreLongDesc",
            "VF2GetOutfitStoreLockGeneration",
        ):
            body = re.search(
                rf"{accessor}\(int itemId\) \{{\{{(.*?)\n\}}\}}", src, re.S
            )
            self.assertIsNotNone(body, f"{accessor} not found")
            self.assertRegex(
                body.group(1), r"VF2Head(Value|StoreEntryIndex)ForItem|VF2HeadStoreEntryIndex",
                f"{accessor} must handle hairstyle ids too",
            )


if __name__ == "__main__":
    unittest.main()
