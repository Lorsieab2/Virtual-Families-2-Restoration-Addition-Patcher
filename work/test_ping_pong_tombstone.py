#!/usr/bin/env python3
"""The dropped Ping-Pong Table keeps its furniture record.

Removing item 0x32E outright would break saves written by a build that had
it. CFurnitureManager::LoadState restores the saved item id and hands it to
LookupFurnitureInfo, which falls back to the first furniture record when the
id is unknown -- so a placed Ping-Pong Table would come back as an unrelated
object with the wrong art, footprint and behaviour rather than being dropped
safely.

Keeping the record with no store list leaves it loadable and unbuyable.
"""
import unittest

import patch_mobile_furniture_pack as patcher

PING_PONG_ITEM_ID = 0x32E


def _ping_pong():
    for item in patcher.NEW_FURNITURE_ITEMS:
        if item["item_id"] == PING_PONG_ITEM_ID:
            return item
    return None


class TestPingPongTombstone(unittest.TestCase):
    def test_the_record_is_still_registered(self):
        item = _ping_pong()
        self.assertIsNotNone(
            item,
            "item 0x32E must keep a furniture record or old saves resolve it "
            "to the first record instead",
        )
        self.assertEqual(item["name"], "PingPongTableStd")

    def test_it_belongs_to_no_store_section(self):
        self.assertIsNone(
            _ping_pong()["list"],
            "the Ping-Pong Table was dropped, so it must not sit in a store list",
        )

    def test_no_store_list_carries_the_item_id(self):
        for name, donor, list_name, path in patcher.ITEMS:
            if list_name is None:
                continue
            self.assertNotIn(
                "PingPongTable", path,
                f"the tombstone leaked into store list {list_name}",
            )

    def test_its_art_and_footprint_still_ship(self):
        # The record is only useful if the art it names is actually installed.
        item = _ping_pong()
        self.assertTrue((patcher.NEW_FURNITURE_ART_DIR / item["art_png"]).is_file())
        self.assertIn(
            f"{item['name']}.png.fmap", patcher.NEW_FURNITURE_FMAP_DONORS
        )

    def test_tombstones_are_skipped_before_the_list_symbol_lookup(self):
        # by_list feeds LIST_SYMBOLS directly, so a None list must be filtered
        # out rather than reaching it as a key.
        self.assertNotIn(None, patcher.LIST_SYMBOLS)


if __name__ == "__main__":
    unittest.main()
