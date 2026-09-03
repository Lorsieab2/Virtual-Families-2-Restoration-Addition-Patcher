#!/usr/bin/env python3
"""The Ping-Pong Table is a real, buyable store item.

It was briefly unregistered by mistake -- kept as a furniture record with no
store list, which left it loadable but absent from every store section. These
tests pin the item to the store so that cannot recur silently.

The furniture record itself must also stay: CFurnitureManager::LoadState hands
a saved item id to LookupFurnitureInfo, which falls back to the first furniture
record when the id is unknown, so dropping record 0x32E would make a placed
table come back as an unrelated object with the wrong art and footprint.
"""
import unittest

import patch_mobile_furniture_pack as patcher

PING_PONG_ITEM_ID = 0x32E


def _ping_pong():
    for item in patcher.NEW_FURNITURE_ITEMS:
        if item["item_id"] == PING_PONG_ITEM_ID:
            return item
    return None


class TestPingPongTable(unittest.TestCase):
    def test_the_record_exists(self):
        item = _ping_pong()
        self.assertIsNotNone(
            item,
            "item 0x32E must keep a furniture record or old saves resolve it "
            "to the first record instead",
        )
        self.assertEqual(item["name"], "PingPongTableStd")

    def test_it_is_registered_in_a_store_section(self):
        item = _ping_pong()
        self.assertEqual(
            item["list"], "gFurniture5",
            "the Ping-Pong Table is a buyable item; a null list would hide it "
            "from the store entirely",
        )
        self.assertIn(item["list"], patcher.LIST_SYMBOLS)
        self.assertEqual(item["section_name"], "Furniture/Placeable")
        self.assertEqual(item["price"], 12000)  # the Pool Table's own price

    def test_a_store_list_actually_carries_the_item(self):
        carried = [
            list_name
            for name, donor, list_name, path in patcher.ITEMS
            if "PingPongTable" in path
        ]
        self.assertEqual(
            carried, ["gFurniture5"],
            "the Ping-Pong Table must reach exactly the gFurniture5 store list",
        )

    def test_no_item_is_left_listless(self):
        # A null list is how the item was hidden before. Nothing declares one
        # now, and the registration path no longer tolerates it.
        for item in patcher.NEW_FURNITURE_ITEMS:
            self.assertIsNotNone(
                item["list"],
                f"{item['name']} has no store list, so it can never be bought",
            )
        self.assertNotIn(None, patcher.LIST_SYMBOLS)

    def test_its_art_and_footprint_still_ship(self):
        item = _ping_pong()
        self.assertTrue((patcher.NEW_FURNITURE_ART_DIR / item["art_png"]).is_file())
        self.assertIn(
            f"{item['name']}.png.fmap", patcher.NEW_FURNITURE_FMAP_DONORS
        )


if __name__ == "__main__":
    unittest.main()
