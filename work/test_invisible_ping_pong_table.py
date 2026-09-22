"""The Invisible Ping-Pong Table: the Ping-Pong Table with transparent art.

Owner: "add another furniture item? Invisible Ping-Pong Table: exactly the
same as the normal one but with transparent graphics."

SHAPE, copied from the Invisible Spa Lounger beside the Spa Lounger:

  * an INVISIBLE_OUTDOOR_ITEMS entry, id 0x331 (the next free id; every
    store and lookup bound derives from the maximum item id), same donor
    (the Pool Table), same store list, price and generation lock, same type;
  * the SAME sprite as the visible table. "Invisible" names which item the
    transparency setting may blank (keyed by item name, so the visible table
    is never blanked); the sprite sync writes a fully transparent
    .pngORIGINAL beside it;
  * the borrowed Pool Table map gets the Ping-Pong Table's own object 0x9A,
    so FindFurniture treats both tables as ping-pong tables, never as pool
    tables;
  * the drop dispatch names both ids, and the ping-pong action carries the
    invisible id as its altItemId the way the yoga pair does, so a placed
    invisible table is a venue and a villager dropped on it counts as
    standing on "this item".
"""
import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402

NAME = "InvisiblePingPongTable"
VISIBLE = "PingPongTableStd"


def _source():
    return GEN.read_text(encoding="utf-8")


def _strip_comments(text):
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        out.append(line.split("//")[0] if "//" in line else line)
    return "\n".join(out)


def _function(src, signature_start):
    i = src.index(signature_start)
    close = src.index(")", i)
    end = src.index("\n}\n", close)
    return src[i:end]


def _item(name):
    return next(item for item in (*patcher.INVISIBLE_OUTDOOR_ITEMS, *patcher.NEW_FURNITURE_ITEMS) if item["name"] == name)


class TheItem(unittest.TestCase):
    def test_it_is_the_visible_table_with_its_own_id(self):
        inv, vis = _item(NAME), _item(VISIBLE)
        self.assertEqual(inv["item_id"], 0x331)
        self.assertEqual(patcher.INVISIBLE_PING_PONG_TABLE_ITEM_ID, 0x331)
        self.assertEqual(patcher.furniture_item_id_by_name(NAME), 0x331)
        # The next free id: every bound derives from the maximum, so the new
        # id must be exactly one past the previous maximum (the Spa Lounger).
        self.assertEqual(max(patcher.item_id_for(i) for i in range(len(patcher.ITEMS))), 0x331)
        self.assertEqual(sorted(patcher.item_id_for(i) for i in range(len(patcher.ITEMS))).count(0x331), 1)
        # The dict entry tracks its visible sibling on every field, INCLUDING
        # the generation lock, so a change to the visible table carries over.
        # What the BUILD ships is asserted separately below.
        for key in ("donor", "list", "price", "lock_generation", "item_type"):
            self.assertEqual(inv[key], vis[key], key)
        self.assertEqual(inv["donor"], 0x20C, "the Pool Table")
        self.assertEqual(inv["list"], "gFurniture5")
        self.assertEqual(inv["short_description"], "Invisible Ping-Pong Table")
        self.assertIn("invisible ping-pong table", inv["long_description"])

    def test_the_emitted_record_is_unlocked_like_every_other_invisible_item(self):
        """The EMITTED lock is 0, not the 4 in the dict entry.

        Caught by review: asserting the dict literal proves nothing about the
        build, because apply_generation_lock_distribution() rewrites
        lock_generation to 0 for every item whose custom_pack starts with
        "Invisible ", recording the reason "invisible furniture remains
        placement/debug unlocked".

        That override is deliberate and universal, and the owner has stated it
        directly: all invisible furniture is to have a generation lock of 0.
        The Invisible Spa Lounger already diverges from its visible sibling in
        exactly this way -- it ships 0 while the Spa Lounger ships 12 -- so
        exempting this one item would make it the only locked invisible piece.
        Invisible items exist for roleplaying and placement, and are available
        from the first generation.
        """
        manifest_path = patcher.OUT / "patch-manifest.json"
        if not manifest_path.is_file():
            self.skipTest("generator output not present; run the generator first")
        records = json.loads(manifest_path.read_text(encoding="utf-8"))["items"]
        emitted = {r["name"]: r["mobile_data"] for r in records}
        invisible_locks = {
            name: data.get("lock_generation")
            for name, data in emitted.items()
            if str(data.get("custom_pack", "")).startswith("Invisible ")
        }
        self.assertTrue(invisible_locks)
        self.assertEqual(
            sorted(set(invisible_locks.values())), [0],
            "every invisible item must ship generation 0: "
            + repr(invisible_locks))
        self.assertIn("Invisible Ping-Pong Table", invisible_locks)
        self.assertEqual(invisible_locks["Invisible Ping-Pong Table"], 0)
        # The ORIGINAL lock still tracks the visible table, so the dict entry
        # is not silently drifting away from its sibling.
        self.assertEqual(
            emitted["Invisible Ping-Pong Table"].get("original_lock_generation"),
            emitted["Ping-Pong Table"].get("lock_generation"))

    def test_it_ships_the_visible_tables_sprite_and_borrows_the_pool_map(self):
        inv, vis = _item(NAME), _item(VISIBLE)
        self.assertEqual(inv["source_png"], vis["art_png"])
        self.assertEqual(inv["base_png"], vis["art_png"])
        self.assertEqual(inv["donor_fmap"], vis["donor_fmap"])
        self.assertEqual(patcher.INVISIBLE_OUTDOOR_FMAP_DONORS[NAME + ".png.fmap"], "PoolTableStd.png.fmap")
        self.assertEqual(patcher.INVISIBLE_BASE_GRAPHIC_SOURCE_BY_NAME[NAME], "PingPongTableStd.png")

    def test_the_readme_count_follows(self):
        self.assertEqual(len(patcher.INVISIBLE_OUTDOOR_ITEMS), 9)
        self.assertIn("Nine outdoor pieces", (ROOT / "README.md").read_text(encoding="utf-8"))


class TheMap(unittest.TestCase):
    def test_the_borrowed_map_is_retargeted_to_the_ping_pong_object(self):
        src = _source()
        i = src.index("        retarget_pairs = {")
        block = src[i:src.index("        }\n", i)]
        self.assertIn('"InvisiblePingPongTable.png.fmap": (\n                MOBILE_PING_PONG_DONOR_OBJECT,\n                MOBILE_PING_PONG_OBJECT,', block)
        self.assertIn('"PingPongTableStd.png.fmap": (\n                MOBILE_PING_PONG_DONOR_OBJECT,\n                MOBILE_PING_PONG_OBJECT,', block)

    def test_the_emitted_map_carries_only_the_ping_pong_object(self):
        emitted = patcher.OUT / "Assets" / (NAME + ".png.fmap")
        visible = patcher.OUT / "Assets" / (VISIBLE + ".png.fmap")
        if not emitted.is_file() or not visible.is_file():
            self.skipTest("generator output not present; run the generator first")
        def objects(path):
            cells = patcher._fmap_cells(path.read_bytes())
            return sorted((((c >> 11) & 0x40000) | (c & 0x3F800)) >> 11 for c in cells if (((c >> 11) & 0x40000) | (c & 0x3F800)))
        self.assertEqual(objects(emitted), objects(visible))
        self.assertEqual(set(objects(emitted)), {patcher.MOBILE_PING_PONG_OBJECT})
        self.assertEqual(emitted.read_bytes(), visible.read_bytes(), "byte-identical to the visible table's map")


class TheSprite(unittest.TestCase):
    def test_the_emitted_sprite_is_the_visible_one_with_a_transparent_original(self):
        out = patcher.OUT / "Images" / "Furniture"
        inv, vis, original = out / (NAME + ".png"), out / (VISIBLE + ".png"), out / (NAME + ".pngORIGINAL")
        if not inv.is_file() or not vis.is_file():
            self.skipTest("generator output not present; run the generator first")
        self.assertEqual(inv.read_bytes(), vis.read_bytes(), "same sprite as the visible table")
        self.assertTrue(original.is_file(), "the transparency setting needs the blank original to swap in")
        self.assertFalse((out / (VISIBLE + ".pngORIGINAL")).is_file(), "the visible table must never be blankable")
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        with Image.open(original).convert("RGBA") as image:
            self.assertEqual(image.size, Image.open(vis).size)
            self.assertEqual(image.getextrema()[3], (0, 0), "every alpha is zero")


class TheRoute(unittest.TestCase):
    def test_the_drop_dispatch_names_both_tables(self):
        src = _strip_comments(_source())
        self.assertIn("if (candidate == __VF2_PING_PONG_TABLE_ITEM_ID__ ||\n        candidate == __VF2_INVISIBLE_PING_PONG_TABLE_ITEM_ID__) {\n        VF2PingPongPlay(villager);", src)
        self.assertIn('("__VF2_INVISIBLE_PING_PONG_TABLE_ITEM_ID__", "InvisiblePingPongTable"),', src)
        self.assertIn('"__VF2_INVISIBLE_PING_PONG_TABLE_ITEM_ID__",\n        f"{INVISIBLE_PING_PONG_TABLE_ITEM_ID:#x}",', src)
        self.assertIn("0x220, 0x32A, 0x32C, 0x32D, 0x32E, INVISIBLE_PING_PONG_TABLE_ITEM_ID}", src)

    def test_the_action_carries_the_invisible_table_as_its_alt_item(self):
        src = _strip_comments(_source())
        f = _function(src, 'extern "C" void __cdecl VF2PingPongPlay(CVillager &villager)')
        self.assertIn("VF2RunOwnFurnitureActionEx(", f)
        self.assertIn("__VF2_PING_PONG_TABLE_ITEM_ID__, __VF2_INVISIBLE_PING_PONG_TABLE_ITEM_ID__,\n        __VF2_PING_PONG_OBJECT__, __VF2_PING_PONG_DONOR_OBJECT__,", f)
        self.assertIn("VF2_LABEL_COUNT(kVF2BehaviorLabels_ping_pong), false);", f)

    def test_a_placed_invisible_table_also_admits_the_spontaneous_candidate(self):
        # Villagers choose ping-pong on their own through an autonomous
        # candidate gated on ObjectExists(<object>), NOT on an item id. The
        # invisible table declares the same object 0x9A as the visible one, so
        # placing it alone is enough to admit the candidate, and the action
        # then resolves it as a venue through the altItemId above. This pins
        # the gate to the object constant: were it ever gated on the visible
        # item id instead, an invisible-only yard would offer ping-pong and
        # then silently start nothing.
        src = _strip_comments(_source())
        # The WEIGHT is matched as \d+ on purpose. This test pins the OBJECT
        # the candidate is gated on; the weight is a separate product decision
        # (the owner raised it to match the Pool Table's) and hardcoding it
        # here made this test fail for a change it does not govern.
        # work/test_pingpong_weight.py pins the number itself.
        self.assertRegex(
            src,
            r"CloneAutonomousCandidateWithWeight\(data, 0x099, 0x0B8, \d+, "
            r"__VF2_PING_PONG_OBJECT__\);")
        self.assertEqual(patcher.MOBILE_PING_PONG_OBJECT, 0x9A)
        self.assertEqual(
            patcher.INVISIBLE_OUTDOOR_FMAP_DONORS[NAME + ".png.fmap"],
            patcher.NEW_FURNITURE_FMAP_DONORS[VISIBLE + ".png.fmap"],
            "both tables borrow one map, so both carry object 0x9A")

    def test_the_emitted_dispatcher_routes_both_ids(self):
        emitted = patcher.PATCHED / "vf2_mobile_furniture_behaviors.cpp"
        if not emitted.is_file():
            self.skipTest("generator output not present; run the generator first")
        text = emitted.read_text(encoding="utf-8", errors="replace")
        self.assertIn("if (candidate == 0x32e ||\n        candidate == 0x331) {\n        VF2PingPongPlay(villager);", text)
        special = (patcher.PATCHED / "vf2_spontaneous_behaviors.cpp").read_text(encoding="utf-8", errors="replace")
        self.assertIn("        0x32e, 0x331,\n        0x9a, 0x36,", special)
        self.assertNotIn("__VF2_INVISIBLE_PING_PONG_TABLE_ITEM_ID__", text + special, "an unsubstituted placeholder would not compile")


if __name__ == "__main__":
    unittest.main()
