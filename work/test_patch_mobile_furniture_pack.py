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
import rebuild_holiday_ornament_collection_assets as ornament_assets
import validate_b152_custom_achievement_diagnostics as b152_diagnostics
import validate_b153_runtime_flags as b153_runtime
from coff_patch import CoffObject


class MobileFurnitureCatalogTests(unittest.TestCase):
    def test_catalog_is_workspace_local_and_hash_verified(self):
        expected_path = (
            patcher.ROOT
            / "data"
            / "vf2"
            / "vf2_desktop_base_and_mobile_furniture_sections.csv"
        )
        self.assertEqual(patcher.MOBILE_CSV, expected_path)
        self.assertTrue(expected_path.is_file())
        self.assertEqual(expected_path.stat().st_size, 104577)
        self.assertEqual(
            hashlib.sha256(expected_path.read_bytes()).hexdigest(),
            "a8e965309016d0933f1577ad0865e103e58d5df9a24cb4012a39d8457f293b8c",
        )

    def test_mobile_behavior_fmap_evidence_is_local_and_hash_pinned(self):
        source_dir = patcher.MOBILE_FURNITURE_BEHAVIOR_SOURCE_DIR
        self.assertEqual(
            source_dir,
            patcher.ROOT
            / "patcher_assets"
            / "optional_patches"
            / "mobile_furniture_behaviors"
            / "mobile_fmaps",
        )
        records = []
        for path in sorted(source_dir.glob("*.fmap"), key=lambda item: item.name):
            data = path.read_bytes()
            self.assertGreaterEqual(len(data), 0x30)
            self.assertEqual(data[:4], b"QAMF")
            records.append(
                path.name
                + "\0"
                + hashlib.sha256(data).hexdigest()
            )
        self.assertEqual(len(records), 41)
        digest = hashlib.sha256(("\n".join(records) + "\n").encode("utf-8"))
        self.assertEqual(
            digest.hexdigest(),
            "cb8c649c19a80b3c4ebe037218f96fa626ec2b07d2ef585fa8baf84a1a0b0c1c",
        )

    def test_mobile_behavior_evidence_scope_is_exact_and_excludes_invisible(self):
        mobile_rows = [
            (name, path, patcher.MOBILE_DATA_BY_PATH[path])
            for name, _donor, _list_name, path in patcher.ITEMS
            if patcher.MOBILE_DATA_BY_PATH[path].get("mobile_row") is not None
        ]
        self.assertEqual(len(mobile_rows), 63)
        self.assertEqual(
            [row[2]["mobile_item_id"] for row in mobile_rows],
            list(range(0x2AA, 0x2E9)),
        )
        self.assertFalse(any("Invisible" in row[0] for row in mobile_rows))

    def test_mobile_chaise_pc_fmaps_have_exact_eobject_and_peep_slot_payloads(self):
        expected_hashes = {
            "Chaise_blue.png.fmap": "a92512d05b37824c234463c08076083349b12c5b0ef8d06cabdf4178415f26cf",
            "Chaise_brown.png.fmap": "b0126fa4d05416af958f290262d5f2e20c9f3bb5fc3ab9058db6ae2674835948",
            "Chaise_green.png.fmap": "d3b472fccd0ffb1daeee22e51208d2cb87cf2f957628bcdd6042b0f77c5b05af",
            "Chaise_red.png.fmap": "ea914d7d2e7dc373f9a1dcf9cfdfca627ec9d826750ae2ab8d3d449399c9daaa",
        }
        manifest = {}
        patcher.validate_mobile_chaise_pc_fmaps(manifest)
        self.assertEqual(
            [row["item_id"] for row in manifest["MobileChaisePCFmaps"]["records"]],
            ["0x2de", "0x2df", "0x2e0", "0x2e1"],
        )
        for filename, expected_hash in expected_hashes.items():
            data = (patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR / filename).read_bytes()
            self.assertEqual(len(data), 1112)
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected_hash)
            width, height = struct.unpack_from("<ii", data, 24)
            values = [
                value
                for (value,) in struct.iter_unpack(
                    "<I", data[32 : 32 + width * height * 4]
                )
            ]
            self.assertEqual((width, height), (19, 14))
            self.assertEqual(
                {(i % width, i // width) for i, value in enumerate(values) if value},
                set(patcher.MOBILE_CHAISE_PC_CELLS)
                | {patcher.MOBILE_CHAISE_PC_SLOT_CELL},
            )
            self.assertEqual(
                {value for value in values if value},
                {
                    patcher.MOBILE_CHAISE_PC_CELL_VALUE,
                    patcher.MOBILE_CHAISE_PC_SLOT_CELL_VALUE,
                },
            )
            slot_index = (
                patcher.MOBILE_CHAISE_PC_SLOT_CELL[1] * width
                + patcher.MOBILE_CHAISE_PC_SLOT_CELL[0]
            )
            self.assertEqual(values[slot_index], patcher.MOBILE_CHAISE_PC_SLOT_CELL_VALUE)
            self.assertEqual(values.count(patcher.MOBILE_CHAISE_PC_SLOT_CELL_VALUE), 1)

    def test_mobile_patio_umbrella_pc_fmap_is_exact_eobject_only_payload(self):
        filename = "Patio_umbrella.png.fmap"
        manifest = {}
        patcher.validate_mobile_patio_umbrella_pc_fmap(manifest)
        contract = manifest["MobilePatioUmbrellaPCFmap"]
        self.assertEqual(contract["item_id"], "0x2e7")
        self.assertEqual(contract["object"], "0x96")
        self.assertEqual(contract["excluded_mobile_markers"], [
            "0x01b40000",
            "0x01ac0000",
        ])

        data = (
            patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR / filename
        ).read_bytes()
        self.assertEqual(len(data), 1068)
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "c62d0320f781e57423b1b2dbfe4e474cf61e62b1dc36c7166d09041dbf7fed7d",
        )
        width, height = struct.unpack_from("<ii", data, 24)
        values = [
            value
            for (value,) in struct.iter_unpack(
                "<I", data[32 : 32 + width * height * 4]
            )
        ]
        self.assertEqual((width, height), (15, 17))
        self.assertEqual(
            {(i % width, i // width) for i, value in enumerate(values) if value},
            set(patcher.MOBILE_PATIO_UMBRELLA_PC_CELLS),
        )
        self.assertEqual(
            {value for value in values if value},
            {patcher.MOBILE_PATIO_UMBRELLA_PC_CELL_VALUE},
        )
        self.assertNotIn(0x01B40000, values)
        self.assertNotIn(0x01AC0000, values)

    def test_mobile_patio_table_pc_fmap_keeps_both_seat_anchors(self):
        manifest = {}
        patcher.validate_mobile_patio_table_pc_fmap(manifest)
        contract = manifest["MobilePatioTablePCFmap"]
        self.assertEqual(contract["item_id"], "0x2e6")
        self.assertEqual(contract["object"], "0x98")

        data = (
            patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR
            / "Patio_table.png.fmap"
        ).read_bytes()
        self.assertEqual(len(data), 1340)
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "0a60f9c579554876c15ae416d20fc313947f73ce3fb2a3a4eeb222beac6aab5d",
        )
        width, height = struct.unpack_from("<ii", data, 24)
        values = [
            value
            for (value,) in struct.iter_unpack(
                "<I", data[32 : 32 + width * height * 4]
            )
        ]
        self.assertEqual((width, height), (19, 17))
        self.assertEqual(
            {
                (i % width, i // width)
                for i, value in enumerate(values)
                if value == patcher.MOBILE_PATIO_TABLE_PC_CELL_VALUE
            },
            set(patcher.MOBILE_PATIO_TABLE_PC_CELLS),
        )
        for cell, value in patcher.MOBILE_PATIO_TABLE_PC_SEAT_CELLS.items():
            self.assertEqual(values[cell[1] * width + cell[0]], value)
        self.assertEqual(
            sum(1 for value in values if value),
            len(patcher.MOBILE_PATIO_TABLE_PC_CELLS)
            + len(patcher.MOBILE_PATIO_TABLE_PC_SEAT_CELLS),
        )

    def test_mobile_picnic_table_pc_fmap_keeps_four_exact_seat_anchors(self):
        manifest = {}
        patcher.validate_mobile_picnic_table_pc_fmap(manifest)
        contract = manifest["MobilePicnicTablePCFmap"]
        self.assertEqual(contract["item_id"], "0x2e8")
        self.assertEqual(contract["object"], "0x97")
        self.assertEqual(contract["excluded_mobile_hotspot"], "0x6b")

        data = (
            patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR
            / "Picnic_table.png.fmap"
        ).read_bytes()
        self.assertEqual(len(data), 1456)
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "3d3aaeeeb77e7842cc20be211d8bcf415f85e6d8c6cd0e0f860a934c6cc45060",
        )
        width, height = struct.unpack_from("<ii", data, 24)
        values = [
            value
            for (value,) in struct.iter_unpack(
                "<I", data[32 : 32 + width * height * 4]
            )
        ]
        self.assertEqual((width, height), (22, 16))
        self.assertEqual(
            {
                (i % width, i // width)
                for i, value in enumerate(values)
                if value == patcher.MOBILE_PICNIC_TABLE_PC_CELL_VALUE
            },
            set(patcher.MOBILE_PICNIC_TABLE_PC_CELLS),
        )
        for cell, value in patcher.MOBILE_PICNIC_TABLE_PC_SEAT_CELLS.items():
            self.assertEqual(values[cell[1] * width + cell[0]], value)
        self.assertEqual(
            sum(1 for value in values if value),
            len(patcher.MOBILE_PICNIC_TABLE_PC_CELLS)
            + len(patcher.MOBILE_PICNIC_TABLE_PC_SEAT_CELLS),
        )

    def test_mobile_birthday_cake_pc_fmap_is_exact_eobject_only_payload(self):
        manifest = {}
        patcher.validate_mobile_birthday_cake_pc_fmap(manifest)
        contract = manifest["MobileBirthdayCakePCFmap"]
        self.assertEqual(contract["item_id"], "0x2dc")
        self.assertEqual(contract["object"], "0x94")
        data = (
            patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR
            / "Birthday_cake.png.fmap"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "e1c55dc0d38b44003abe878cd9ccdfee3e49b5c7ed9e793d14b25c0fae57926d",
        )
        width, height = struct.unpack_from("<ii", data, 24)
        values = [
            value
            for (value,) in struct.iter_unpack(
                "<I", data[32 : 32 + width * height * 4]
            )
        ]
        self.assertEqual((width, height), (9, 8))
        self.assertEqual(
            {(i % width, i // width) for i, value in enumerate(values) if value},
            set(patcher.MOBILE_BIRTHDAY_CAKE_PC_CELLS),
        )
        self.assertEqual(
            {value for value in values if value},
            {patcher.MOBILE_BIRTHDAY_CAKE_PC_CELL_VALUE},
        )

    def test_mobile_birthday_presents_pc_fmap_is_exact_eobject_only_payload(self):
        manifest = {}
        patcher.validate_mobile_birthday_presents_pc_fmap(manifest)
        contract = manifest["MobileBirthdayPresentsPCFmap"]
        self.assertEqual(contract["item_id"], "0x2dd")
        self.assertEqual(contract["object"], "0x93")
        data = (
            patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR
            / "Birthday_presents.png.fmap"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "63ef84177e87b4a4dd28c0a85c4aff2ee741423ca4ac34b3d273cb11fd4a18c5",
        )
        width, height = struct.unpack_from("<ii", data, 24)
        values = [
            value
            for (value,) in struct.iter_unpack(
                "<I", data[32 : 32 + width * height * 4]
            )
        ]
        self.assertEqual((width, height), (9, 10))
        self.assertEqual(
            {(i % width, i // width) for i, value in enumerate(values) if value},
            set(patcher.MOBILE_BIRTHDAY_PRESENTS_PC_CELLS),
        )
        self.assertEqual(
            {value for value in values if value},
            {patcher.MOBILE_BIRTHDAY_PRESENTS_PC_CELL_VALUE},
        )

    def test_mobile_birthday_balloons_pc_fmap_is_exact_eobject_only_payload(self):
        manifest = {}
        patcher.validate_mobile_birthday_balloons_pc_fmap(manifest)
        contract = manifest["MobileBirthdayBalloonsPCFmap"]
        self.assertEqual(contract["item_id"], "0x2da")
        self.assertEqual(contract["object"], "0x92")
        data = (
            patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR
            / "Balloons_birthday.png.fmap"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "f66e4dc4776962b32b68e069a133ca9b1a7f57306d7df357866dd2630c307fc3",
        )
        width, height = struct.unpack_from("<ii", data, 24)
        values = [
            value
            for (value,) in struct.iter_unpack(
                "<I", data[32 : 32 + width * height * 4]
            )
        ]
        self.assertEqual((width, height), (11, 14))
        self.assertEqual(
            {(i % width, i // width) for i, value in enumerate(values) if value},
            set(patcher.MOBILE_BIRTHDAY_BALLOONS_PC_CELLS),
        )
        self.assertEqual(
            {value for value in values if value},
            {patcher.MOBILE_BIRTHDAY_BALLOONS_PC_CELL_VALUE},
        )

    def test_mobile_birthday_banner_pc_fmap_is_exact_eobject_only_payload(self):
        manifest = {}
        patcher.validate_mobile_birthday_banner_pc_fmap(manifest)
        contract = manifest["MobileBirthdayBannerPCFmap"]
        self.assertEqual(contract["item_id"], "0x2db")
        self.assertEqual(contract["object"], "0x91")
        data = (
            patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR
            / "Birthday_banner.png.fmap"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "071c79932b55f382e3fe12be01a32f673ae9726339bd4295be3b35bf78456feb",
        )
        width, height = struct.unpack_from("<ii", data, 24)
        values = [
            value
            for (value,) in struct.iter_unpack(
                "<I", data[32 : 32 + width * height * 4]
            )
        ]
        self.assertEqual((width, height), (14, 16))
        self.assertEqual(
            {(i % width, i // width) for i, value in enumerate(values) if value},
            set(patcher.MOBILE_BIRTHDAY_BANNER_PC_CELLS),
        )
        self.assertEqual(
            {value for value in values if value},
            {patcher.MOBILE_BIRTHDAY_BANNER_PC_CELL_VALUE},
        )

    def test_mobile_group_holiday_pc_fmaps_are_exact_eobject_only_payloads(self):
        manifest = {}
        patcher.validate_mobile_group_holiday_pc_fmaps(manifest)
        records = {
            row["filename"]: row
            for row in manifest["MobileGroupHolidayPCFmaps"]["records"]
        }
        specs = {
            "CandleOnHolder.png.fmap": (
                "80d3f61d48e59fd55684edfb205670289fa6b15ba9768624ae318849a9f0bc11",
                (8, 9),
                patcher.MOBILE_HOLIDAY_CANDLES_PC_CELLS,
                patcher.MOBILE_HOLIDAY_CANDLES_PC_CELL_VALUE,
                "0x2aa",
                "0x89",
            ),
            "ChristmasTree1.png.fmap": (
                "5907f7f60209d77d6c63b15b009243756c9f2c4d729134c41c105e0863b66926",
                (15, 22),
                patcher.MOBILE_XMAS_TREE_PC_SPECS["ChristmasTree1.png.fmap"]["cells"],
                patcher.MOBILE_XMAS_TREE_PC_CELL_VALUE,
                "0x2ad",
                "0x88",
            ),
            "ChristmasTree2.png.fmap": (
                "289e237d686f164dfd3e2293aeac248f5259e700125d963b4b578cefd642ccc8",
                (16, 22),
                patcher.MOBILE_XMAS_TREE_PC_SPECS["ChristmasTree2.png.fmap"]["cells"],
                patcher.MOBILE_XMAS_TREE_PC_CELL_VALUE,
                "0x2ae",
                "0x88",
            ),
            "Dreidel.png.fmap": (
                "44f21fc628cd90090f3eaf8eb1925de8d890fa5239828f55d115ae37c453b36a",
                (12, 8),
                patcher.MOBILE_DREIDEL_PC_CELLS,
                patcher.MOBILE_DREIDEL_PC_CELL_VALUE,
                "0x2af",
                "0x8a",
            ),
            "Menorah.png.fmap": (
                "352ba4be943eae6a168a133430ccd6555c5feb41a630c118da2d24c019e39365",
                (10, 11),
                patcher.MOBILE_MENORAH_PC_CELLS,
                patcher.MOBILE_MENORAH_PC_CELL_VALUE,
                "0x2b8",
                "0x8e",
            ),
        }
        self.assertEqual(set(records), set(specs))
        for filename, (digest, grid, cells, cell_value, item_id, obj_id) in specs.items():
            data = (
                patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR / filename
            ).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            width, height = struct.unpack_from("<ii", data, 24)
            values = [
                value
                for (value,) in struct.iter_unpack(
                    "<I", data[32 : 32 + width * height * 4]
                )
            ]
            self.assertEqual((width, height), grid)
            self.assertEqual(
                {(i % width, i // width) for i, value in enumerate(values) if value},
                set(cells),
            )
            self.assertEqual({value for value in values if value}, {cell_value})
            self.assertEqual(records[filename]["item_id"], item_id)
            self.assertEqual(records[filename]["object"], obj_id)

    def test_mobile_xmas_stocking_pc_fmaps_are_exact_eobject_only_payloads(self):
        manifest = {}
        patcher.validate_mobile_xmas_stocking_pc_fmaps(manifest)
        records = {
            row["filename"]: row
            for row in manifest["MobileXmasStockingsPCFmaps"]["records"]
        }
        expected_hashes = {
            "StockingLarge.png.fmap": "f467c400f7ae60efea0ab67ccb33d5ec9327a94383102f750e20dd29d70165a0",
            "StockingSmall.png.fmap": "aa6eee69ecaedcaa03575d6bb916e4442cfc83efda41f6e3a8291371475e8003",
        }
        self.assertEqual(set(records), set(patcher.MOBILE_XMAS_STOCKING_PC_SPECS))
        for filename, spec in patcher.MOBILE_XMAS_STOCKING_PC_SPECS.items():
            data = (
                patcher.MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR / filename
            ).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected_hashes[filename])
            width, height = struct.unpack_from("<ii", data, 24)
            values = [
                value
                for (value,) in struct.iter_unpack(
                    "<I", data[32 : 32 + width * height * 4]
                )
            ]
            self.assertEqual((width, height), spec["grid"])
            self.assertEqual(
                {
                    (i % width, i // width)
                    for i, value in enumerate(values)
                    if value
                },
                set(spec["cells"]),
            )
            self.assertEqual(
                {value for value in values if value},
                {patcher.MOBILE_XMAS_STOCKING_PC_CELL_VALUE},
            )
            self.assertEqual(records[filename]["item_id"], hex(spec["item_id"]))
            self.assertEqual(records[filename]["object"], "0x90")

    def test_mobile_chaise_dispatch_retargets_only_stock_drop_hotspot_call(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                obj_path = patcher.PATCHED / "theMainScene.obj"
                shutil.copy2(patcher.SRC_OBJS / "theMainScene.obj", obj_path)

                def targets(obj, symbol):
                    section = obj.section(symbol.section)
                    result = {}
                    for index in range(section.nreloc):
                        vaddr, symbol_index, rtype = struct.unpack_from(
                            "<IIH", obj.buf, section.reloc_ptr + index * 10
                        )
                        if symbol.value <= vaddr < symbol.value + 0x200:
                            result[vaddr - symbol.value] = (
                                obj.symbol_by_index[symbol_index].name,
                                rtype,
                            )
                    return result

                before = CoffObject(obj_path)
                before_targets = targets(
                    before, before.symbol("?DropVillager@theMainScene@@IAEXXZ")
                )
                manifest = {}
                patcher.patch_mobile_furniture_behavior_dispatch(manifest)
                after = CoffObject(obj_path)
                after_targets = targets(
                    after, after.symbol("?DropVillager@theMainScene@@IAEXXZ")
                )
                expected = dict(before_targets)
                expected[0xCB] = (
                    patcher.MOBILE_FURNITURE_BEHAVIOR_HELPER_SYMBOL,
                    patcher.IMAGE_REL_I386_REL32,
                )
                self.assertEqual(after_targets, expected)
                contract = manifest["MobileFurnitureBehaviors"]
                self.assertEqual(
                    contract["runtime_flag"],
                    {
                        "symbol": patcher.MOBILE_FURNITURE_BEHAVIOR_FLAG_SYMBOL,
                        "source_section": ".vf2beh",
                        "size": 1,
                        "default": "00",
                    },
                )
                self.assertTrue(contract["drop_hook"]["stock_first"])
                self.assertTrue(contract["drop_hook"]["stock_false_fallthrough_preserved"])
                self.assertEqual(
                    contract["implemented_families"][0]["item_ids"],
                    ["0x2de", "0x2df", "0x2e0", "0x2e1"],
                )
                self.assertTrue(contract["implemented_families"][0]["autonomous"])
                self.assertFalse(contract["implemented_families"][0]["manual_drop_only"])
                self.assertTrue(contract["implemented_families"][0]["manual_drop_supported"])
                self.assertEqual(
                    contract["implemented_families"][0]["manual_drop_variants"],
                    [
                        "Relaxing on lounger",
                        "Reading a book",
                        "Studying on the lounger",
                        "Needs to sit down",
                        "Taking a nap",
                        "Getting some sleep",
                    ],
                )
                self.assertEqual(
                    contract["implemented_families"][0]["manual_drop_energy_policy"],
                    {
                        "energy_field": "CVillager+0x6B28",
                        "energy_range": [1, 100],
                        "awake_choice_weight_each": 20,
                        "nap_weight": "max(0, 70-energy)",
                        "sleep_weight": "max(0, 45-energy)*3",
                    },
                )
                self.assertEqual(
                    contract["implemented_families"][0]["autonomous_variants"],
                    [
                        "Catching some rays",
                        "Reading a book",
                        "Taking a nap",
                        "Studying on the lounger",
                        "Needs to sit down",
                    ],
                )
                umbrella = contract["implemented_families"][1]
                self.assertEqual(umbrella, {
                    "name": "mobile patio umbrella",
                    "item_ids": ["0x2e7"],
                    "label": "Adjusting umbrella",
                    "object": "0x96",
                    "manual_drop_only": True,
                    "autonomous": False,
                    "mobile_behavior": "CBehavior::AdjustingUmbrella",
                    "desktop_implementation": "exact direct plan-sequence port",
                })
                patio = contract["implemented_families"][2]
                self.assertEqual(patio["item_ids"], ["0x2e6"])
                self.assertEqual(patio["object"], "0x98")
                self.assertEqual(
                    patio["mobile_behavior_ids"], ["0x1b6", "0x1b7"]
                )
                self.assertTrue(patio["manual_drop_supported"])
                self.assertTrue(patio["children_can_drink_when_ready"])
                self.assertFalse(patio["autonomous"])
                self.assertEqual(
                    patio["drink_ready_state"]["duration_game_seconds"], 240
                )
                self.assertEqual(
                    patio["drink_ready_state"]["save_reload_persistence"],
                    "unproven",
                )
                self.assertEqual(
                    contract["implemented_families"][4],
                    {
                        "name": "mobile Birthday Cake",
                        "item_ids": ["0x2dc"],
                        "label": "Poking cake",
                        "object": "0x94",
                        "manual_drop_only": True,
                        "child_only": True,
                        "raw_age_max": "0x117",
                        "autonomous": False,
                        "mobile_behavior": "CBehavior::PokingCake",
                        "desktop_implementation": "exact direct plan-sequence port",
                    },
                )
                self.assertEqual(
                    contract["implemented_families"][5],
                    {
                        "name": "mobile Birthday Presents",
                        "item_ids": ["0x2dd"],
                        "label": "Checking out the presents",
                        "object": "0x93",
                        "manual_drop_only": True,
                        "child_only": True,
                        "raw_age_max": "0x117",
                        "autonomous": False,
                        "mobile_behavior": "CBehavior::PokingBirthdayPresents",
                        "desktop_implementation": "exact direct plan-sequence port",
                    },
                )
                picnic = contract["implemented_families"][3]
                self.assertEqual(picnic["item_ids"], ["0x2e8"])
                self.assertEqual(picnic["object"], "0x97")
                self.assertEqual(
                    picnic["mobile_behavior_ids"], ["0x1b4", "0x1b5"]
                )
                self.assertTrue(picnic["manual_drop_supported"])
                self.assertTrue(picnic["children_can_eat_when_ready"])
                self.assertFalse(picnic["autonomous"])
                self.assertEqual(
                    picnic["picnic_ready_state"]["duration_game_seconds"], 240
                )
                balloons = contract["implemented_families"][6]
                self.assertEqual(balloons["item_ids"], ["0x2da"])
                self.assertEqual(balloons["label"], "Playing")
                self.assertEqual(balloons["label_string_id"], "0xf0")
                self.assertEqual(balloons["object"], "0x92")
                self.assertEqual(balloons["raw_age_max"], "0x117")
                self.assertEqual(
                    balloons["mobile_behavior"],
                    "CBehavior::PlayingWithBalloons",
                )
                self.assertEqual(balloons["mobile_behavior_id"], "0x1ad")
                self.assertTrue(balloons["manual_drop_only"])
                self.assertFalse(balloons["autonomous"])
                banner = contract["implemented_families"][7]
                self.assertEqual(banner["item_ids"], ["0x2db"])
                self.assertEqual(banner["object"], "0x91")
                self.assertEqual(banner["mobile_behavior_ids"], ["0x1ae", "0x1af"])
                self.assertTrue(banner["whole_household"])
                trees = contract["implemented_families"][8]
                self.assertEqual(trees["item_ids"], ["0x2ad", "0x2ae"])
                self.assertEqual(trees["object"], "0x88")
                self.assertEqual(trees["mobile_behavior_id"], "0x1a0")
                self.assertTrue(trees["whole_household"])
                dreidel = contract["implemented_families"][9]
                self.assertEqual(dreidel["item_ids"], ["0x2af"])
                self.assertEqual(dreidel["object"], "0x8a")
                self.assertEqual(dreidel["mobile_behavior_id"], "0x1a2")
                self.assertTrue(dreidel["whole_household"])
                menorah = contract["implemented_families"][10]
                self.assertEqual(menorah["item_ids"], ["0x2b8"])
                self.assertEqual(menorah["object"], "0x8e")
                self.assertEqual(menorah["mobile_behavior_id"], "0x1a3")
                self.assertTrue(menorah["whole_household"])
                stockings = contract["implemented_families"][11]
                self.assertEqual(stockings["item_ids"], ["0x2c6", "0x2c7"])
                self.assertEqual(stockings["label"], "Checking for stocking stuffers")
                self.assertEqual(stockings["object"], "0x90")
                self.assertEqual(stockings["raw_age_max"], "0x167")
                self.assertEqual(
                    stockings["mobile_behavior"],
                    "CBehavior::KidsCheckXmasStockings",
                )
                self.assertTrue(stockings["manual_drop_only"])
                self.assertFalse(stockings["autonomous"])
                candles = contract["implemented_families"][12]
                self.assertEqual(candles["item_ids"], ["0x2aa"])
                self.assertEqual(candles["label"], "Playing with holiday candles")
                self.assertEqual(candles["object"], "0x89")
                self.assertEqual(candles["raw_age_max"], "0x117")
                self.assertEqual(
                    candles["mobile_behavior"],
                    "CBehavior::KidExaminesCandles",
                )
                self.assertEqual(candles["mobile_behavior_id"], "0x19b")
                self.assertEqual(candles["mobile_candidate_weight"], 2000)
                self.assertTrue(candles["manual_drop_only"])
                self.assertFalse(candles["autonomous"])
                helper = (patcher.PATCHED / "vf2_mobile_furniture_behaviors.cpp").read_text(
                    encoding="ascii"
                )
                wrapper = helper.split(
                    "bool const theMainScene::VF2HandleDropOnMobileFurniture", 1
                )[1]
                self.assertLess(
                    wrapper.index("if (HandleDropOnHotSpot(villager)) return true;"),
                    wrapper.index("if (gVF2MobileFurnitureBehaviors == 0) return false;"),
                )
                self.assertIn("sample.y -= 10;", wrapper)
                self.assertIn("VF2IsMobileChaise(candidate)", wrapper)
                self.assertIn(
                    "if (candidate == 0x2E7) return VF2HandleMobilePatioUmbrella(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2E6) return VF2HandleMobilePatioTable(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2E8) return VF2HandleMobilePicnicTable(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2DC) return VF2HandleMobileBirthdayCake(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2DD) return VF2HandleMobileBirthdayPresents(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2DA) return VF2HandleMobileBirthdayBalloons(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2DB) return VF2HandleMobileBirthdayBanner(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2AA) return VF2HandleMobileHolidayCandles(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2AD || candidate == 0x2AE)",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2AF) return VF2HandleMobileDreidelGroup(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2B8) return VF2HandleMobileMenorahGroup(villager);",
                    wrapper,
                )
                self.assertIn(
                    "if (candidate == 0x2C6 || candidate == 0x2C7)",
                    wrapper,
                )
                self.assertIn('VF2SetActionLabel(villager, "Poking cake");', helper)
                self.assertIn("VF2BirthdayOhSound(villager)", helper)
                self.assertIn("ldwGameState::GetRandom(4) + 2", helper)
                self.assertIn("plans->PlanToJoyTwirlCW(2);", helper)
                self.assertIn(
                    'VF2SetActionLabel(villager, "Checking out the presents");',
                    helper,
                )
                self.assertIn("plans->PlanToBend(1, ePriorityNormal);", helper)
                self.assertIn("plans->PlanToStopSound();", helper)
                balloons_helper = helper.split(
                    "static bool VF2HandleMobileBirthdayBalloons", 1
                )[1].split("static bool VF2HandleMobileBirthdayPresents", 1)[0]
                self.assertIn(
                    "theStringManager::Get()->GetString(eStringPlayingWithToys)",
                    balloons_helper,
                )
                self.assertIn("if (info.object != CContentMap::eObjectBirthdayBalloons)", balloons_helper)
                self.assertIn("int extraBalloonGoes = ldwGameState::GetRandom(2) + 3;", balloons_helper)
                self.assertIn("switch (ldwGameState::GetRandom(6))", balloons_helper)
                self.assertIn('"StompingE", false, 0.02f', balloons_helper)
                self.assertIn('"StompingW", false, 0.02f', balloons_helper)
                self.assertIn("plans->PlanToTwirlCCW", balloons_helper)
                self.assertNotIn("NewBehavior(static_cast<EBehavior>(0x1AD)", balloons_helper)
                banner_helper = helper.split(
                    "static void VF2RunMobileBirthdayCelebration", 1
                )[1].split("static void VF2RunMobileDreidel", 1)[0]
                self.assertIn('VF2SetActionLabel(villager, "Celebrating birthday");', banner_helper)
                self.assertIn("VF2BirthdayObjectScan(selected)", banner_helper)
                self.assertIn("objectCount > 1", banner_helper)
                self.assertIn("VF2HandleMobileBirthdayBalloons(villager)", banner_helper)
                self.assertIn("VF2HandleMobileBirthdayPresents(villager)", banner_helper)
                self.assertIn("VF2HandleMobileBirthdayCake(villager)", banner_helper)
                self.assertNotIn("0x1AE", helper)
                self.assertNotIn("0x1AF", helper)
                self.assertIn("for (int index = 0; index < 30; ++index)", helper)
                self.assertIn("VillagerManager.VillagerExists(index, false)", helper)
                self.assertIn("data + 0x6B00", helper)
                dreidel_helper = helper.split(
                    "static void VF2RunMobileDreidel", 1
                )[1].split("static void VF2RunMobileMenorah", 1)[0]
                self.assertIn('VF2SetActionLabel(villager, "Playing Dreidel");', dreidel_helper)
                self.assertIn("for (int round = 0; round < 7; ++round)", dreidel_helper)
                self.assertIn("ldwGameState::GetRandom(100) > 49", dreidel_helper)
                menorah_helper = helper.split(
                    "static void VF2RunMobileMenorah", 1
                )[1].split("static bool VF2HandleMobileDreidelGroup", 1)[0]
                self.assertIn('VF2SetActionLabel(villager, "Celebrating Hanukkah");', menorah_helper)
                self.assertEqual(menorah_helper.count("plans->PlanToJump("), 4)
                self.assertIn("plans->PlanToStopSound();", menorah_helper)
                tree_helper = helper.split(
                    "static void VF2RunMobileXmasTree", 1
                )[1].split("static void VF2RunMobileMenorah", 1)[0]
                self.assertIn(
                    'VF2SetActionLabel(villager, "Celebrating around the tree");',
                    tree_helper,
                )
                self.assertEqual(tree_helper.count("plans->PlanToJump("), 4)
                self.assertIn("VF2HandleMobileXmasTreeGroup", helper)
                self.assertNotIn("0x1A2", helper)
                self.assertNotIn("0x1A3", helper)
                self.assertNotIn("0x1A0", helper)
                candles_helper = helper.split(
                    "static bool VF2HandleMobileHolidayCandles", 1
                )[1].split("static void VF2RunMobileDreidel", 1)[0]
                self.assertIn(
                    'VF2SetActionLabel(villager, "Playing with holiday candles");',
                    candles_helper,
                )
                self.assertIn("data + 0x6A54) > 0x117", candles_helper)
                self.assertIn("CContentMap::eObjectHolidayCandles", candles_helper)
                self.assertIn("ldwGameState::GetRandom(100) <= 29", candles_helper)
                self.assertIn("static_cast<EAgeSelecter>(2)", candles_helper)
                self.assertIn("static_cast<EGender>(1)", candles_helper)
                self.assertIn("point.x += 20;", candles_helper)
                self.assertIn("point.y += 75;", candles_helper)
                self.assertIn(
                    "plans->PlanToActivateProp(ePropHolidayCandlesFallback);",
                    candles_helper,
                )
                self.assertIn("static_cast<ESound>(0x12C)", candles_helper)
                self.assertIn("static_cast<ESound>(0x37)", candles_helper)
                self.assertIn("plans->PlanToStopSound();", candles_helper)
                self.assertIn(
                    'VF2SetActionLabel(villager, "Checking for stocking stuffers");',
                    helper,
                )
                self.assertIn("point.x += ldwGameState::GetRandom(60) - 30;", helper)
                self.assertEqual(
                    helper.split("static bool VF2HandleMobileXmasStockings", 1)[1]
                    .split("static int VF2CollectEligibleHousehold", 1)[0]
                    .count("plans->PlanToJump("),
                    4,
                )
                self.assertIn(
                    f"eStringBadWeather = {patcher.mobile_lounger_bad_weather_string_id()}",
                    helper,
                )
                self.assertIn("eStringCannotReachFurniture = 0xB7", helper)
                self.assertNotIn("eStringBadWeather = 2", helper)
                self.assertNotIn("eStringCannotReachFurniture = 0xBF", helper)
                self.assertIn(
                    "return static_cast<unsigned int>(Weather.currentType) < 2;",
                    helper,
                )
                self.assertIn("CBehavior::StudyingOnPatio(villager);", helper)
                self.assertIn("ldwGameState::GetRandom(100) > 29", helper)
                self.assertIn('{ 0x12B, 1500, true  }', helper)
                self.assertIn('{ 0x083, 3000, true  }', helper)
                self.assertIn('{ 0x127, 2000, true  }', helper)
                self.assertIn('{ 0x0C2,  450, false }', helper)
                self.assertNotIn("0x1B8", helper)
                for label in (
                    "Relaxing on lounger",
                    "Reading a book",
                    "Taking a nap",
                    "Catching some rays",
                    "Studying on the lounger",
                    "Needs to sit down",
                    "Getting some sleep",
                ):
                    self.assertIn(label, helper)
                umbrella_helper = helper.split(
                    "static bool VF2HandleMobilePatioUmbrella", 1
                )[1].split("static void VF2PlanPatioRefusal", 1)[0]
                self.assertIn(
                    "reinterpret_cast<unsigned char *>(&villager) + 0x6B28",
                    helper,
                )
                self.assertIn("energyValue < 70 ? 70 - energyValue : 0", helper)
                self.assertIn("((70 - energyValue) * 30 + 68) / 69", helper)
                self.assertIn("GetRandom(100) >= napChance", helper)
                self.assertIn("int energyValue = VF2CurrentEnergy(villager);", helper)
                self.assertIn("energyValue < 45 ? (45 - energyValue) * 3 : 0", helper)
                self.assertIn("GetRandom(80 + napWeight + sleepWeight)", helper)
                self.assertIn("Night.AIIsDayTime() && ldwGameState::GetRandom(2) == 0", helper)
                expected_steps = [
                    "plans->ForgetPlans(villager, false);",
                    'VF2SetActionLabel(villager, "Adjusting umbrella");',
                    "CContentMap::eObjectPatioUmbrella,",
                    "plans->PlanToWait(1, eBodyPositionUmbrella);",
                    "CContentMap::eObjectPatioUmbrella,",
                    "plans->PlanToWait(1, eBodyPositionUmbrella);",
                    "plans->PlanToWait(\n        3,\n        eBodyPositionStanding,\n        eDirectionUmbrella,\n        eHeadDirectionUmbrella);",
                    "plans->StartNewBehavior(villager);",
                ]
                cursor = 0
                for step in expected_steps:
                    cursor = umbrella_helper.index(step, cursor) + len(step)
                self.assertNotIn("GetRandom", umbrella_helper)
                self.assertNotIn("PlanToInc", umbrella_helper)
                patio_helper = helper.split(
                    "static bool VF2RunMobilePreparingDrinks", 1
                )[1].split("static bool VF2RunMobilePreparingPicnic", 1)[0]
                self.assertIn('"Getting some drinks"', patio_helper)
                self.assertIn('"Having a refreshing drink"', patio_helper)
                self.assertIn("FoodStore.food < 31", patio_helper)
                self.assertIn("age < 0x118", patio_helper)
                self.assertIn("VF2PatioDrinksActive()", patio_helper)
                manual_refusal = helper.split(
                    "static bool VF2ManualPatioRefusal", 1
                )[1].split("static bool VF2RunMobilePreparingDrinks", 1)[0]
                self.assertLess(
                    manual_refusal.index("villager.NewBehavior("),
                    manual_refusal.index("DealerSay.Say(text, -1);"),
                )
                self.assertIn("eBehaviorShakeHead = 0x175", helper)
                self.assertIn("eStringTooYoung = 0x73D", helper)
                self.assertIn("eStringWorriedAboutFood = 0xA41", helper)
                self.assertIn("plans->PlanToActivateProp(ePropPatioDrinks);", patio_helper)
                self.assertIn("plans->PlanToDecEnergy(7);", patio_helper)
                self.assertIn("plans->PlanToIncHunger(7);", patio_helper)
                self.assertIn("plans->PlanToDecHunger(10);", patio_helper)
                self.assertIn("plans->PlanToIncPoo(6);", patio_helper)
                self.assertIn('"Sit In Chair NW"', patio_helper)
                self.assertIn('"Sit In Chair NE"', patio_helper)
                self.assertEqual(
                    patio_helper.count("ldwGameState::GetRandom(8) + 10"), 3
                )
                self.assertNotIn("0x1B6", patio_helper)
                self.assertNotIn("0x1B7", patio_helper)
                picnic_helper = helper.split(
                    "static bool VF2RunMobilePreparingPicnic", 1
                )[1].split("static int VF2BirthdayOhSound", 1)[0]
                self.assertIn('"Preparing a picnic"', picnic_helper)
                self.assertIn('"Having a picnic"', picnic_helper)
                self.assertIn("VF2PicnicReadyActive()", picnic_helper)
                self.assertIn("eStringPicnicTooYoung = 0x7E7", helper)
                self.assertIn(
                    "eStringPicnicWorriedAboutFood = 0xB67", helper
                )
                self.assertIn(
                    "ldwGameState::GetRandom(7) + 0x0D", picnic_helper
                )
                self.assertIn(
                    "CContentMap::eObjectKitchenFoodDrop", picnic_helper
                )
                self.assertIn(
                    "static_cast<ESound>(0xC7)", picnic_helper
                )
                self.assertIn(
                    "plans->PlanToActivateProp(ePropPicnicReady);",
                    picnic_helper,
                )
                self.assertIn("for (int round = 0; round < 3; ++round)", picnic_helper)
                self.assertIn(
                    "ldwGameState::GetRandom(3) + 0x6A", picnic_helper
                )
                self.assertIn("marker == 0x13 || marker == 0x14", picnic_helper)
                self.assertIn("marker == 0x53 || marker == 0x54", picnic_helper)
                self.assertIn("plans->PlanToDecHunger(40);", picnic_helper)
                self.assertIn("plans->PlanToIncPoo(6);", picnic_helper)
                self.assertNotIn("0x1B4", picnic_helper)
                self.assertNotIn("0x1B5", picnic_helper)
        finally:
            patcher.PATCHED = old_patched

    def test_behavior_patch_computer_drop_adds_only_native_video_game_choice(self):
        old_patched = patcher.PATCHED
        old_behavior_patches = patcher.ENABLE_BEHAVIOR_PATCHES
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                patcher.ENABLE_BEHAVIOR_PATCHES = True
                shutil.copy2(
                    patcher.SRC_OBJS / "theMainScene.obj",
                    patcher.PATCHED / "theMainScene.obj",
                )
                manifest = {}
                patcher.patch_mobile_furniture_behavior_dispatch(manifest)
                helper = (
                    patcher.PATCHED / "vf2_mobile_furniture_behaviors.cpp"
                ).read_text(encoding="ascii")
                self.assertIn("behavior == 0x05A", helper)
                self.assertIn("ldwGameState::GetRandom(2) != 0", helper)
                self.assertIn("eBehaviorPlayingVideoGame", helper)
                self.assertIn(
                    "reinterpret_cast<unsigned char *>(&villager) + 0x6A54",
                    helper,
                )
                self.assertNotIn("0x114 * 0xD0", helper)
                self.assertEqual(
                    manifest["ComputerDropVideoGame"],
                    {
                        "enabled": True,
                        "gate": "behavior_patches",
                        "hotspot": "0x12",
                        "stock_normal_behavior": "0x5a",
                        "added_manual_behavior": "0x114",
                        "normal_drop_weights": {
                            "Browsing web": 1,
                            "Playing video games": 1,
                        },
                        "preserves_exceptional_stock_routes": True,
                        "changes_autonomous_weights": False,
                    },
                )
        finally:
            patcher.PATCHED = old_patched
            patcher.ENABLE_BEHAVIOR_PATCHES = old_behavior_patches

    def test_mobile_chaise_autonomous_macros_are_final_exact_retargets(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                obj_path = patcher.PATCHED / "Behavior.obj"
                shutil.copy2(patcher.SRC_OBJS / "Behavior.obj", obj_path)
                manifest = {}
                patcher.patch_mobile_furniture_behavior_macros(manifest)
                obj = CoffObject(obj_path)
                ctor = obj.symbol("??0CBehavior@@QAE@XZ")
                sec = obj.section(ctor.section)
                expected = {
                    0x10D1: "_VF2MobileReadingBook",
                    0x0722: "_VF2MobileNappingCouch",
                    0x108D: "_VF2MobileRestingBody",
                    0x0489: "_VF2MobileStudyingOnPatio",
                }
                actual = {}
                for index in range(sec.nreloc):
                    vaddr, symbol_index, _rtype = struct.unpack_from(
                        "<IIH", obj.buf, sec.reloc_ptr + index * 10
                    )
                    relative = vaddr - ctor.value
                    if relative in expected:
                        actual[relative] = obj.symbol_by_index[symbol_index].name
                self.assertEqual(actual, expected)
                self.assertTrue(
                    manifest["MobileFurnitureBehaviorMacros"][
                        "stock_fallback_preserved"
                    ]
                )
        finally:
            patcher.PATCHED = old_patched

    def test_mobile_patio_prop_hook_retargets_only_set_prop_call(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                obj_path = patcher.PATCHED / "VillagerPlans.obj"
                shutil.copy2(patcher.SRC_OBJS / "VillagerPlans.obj", obj_path)
                before = CoffObject(obj_path)
                process_name = (
                    "?ProcessCurrentPlan@CVillagerPlans@@QAEXAAVCVillager@@@Z"
                )
                process = before.symbol(process_name)
                sec = before.section(process.section)
                before_section_bytes = bytes(
                    before.buf[sec.raw_ptr : sec.raw_ptr + sec.raw_size]
                )
                before_targets = {}
                for index in range(sec.nreloc):
                    vaddr, symbol_index, rtype = struct.unpack_from(
                        "<IIH", before.buf, sec.reloc_ptr + index * 10
                    )
                    if process.value <= vaddr < process.value + 0x300:
                        before_targets[vaddr] = (
                            before.symbol_by_index[symbol_index].name,
                            rtype,
                        )

                manifest = {}
                patcher.patch_mobile_patio_prop_execution(manifest)
                after = CoffObject(obj_path)
                after_process = after.symbol(process_name)
                after_sec = after.section(after_process.section)
                after_targets = {}
                for index in range(after_sec.nreloc):
                    vaddr, symbol_index, rtype = struct.unpack_from(
                        "<IIH", after.buf, after_sec.reloc_ptr + index * 10
                    )
                    if after_process.value <= vaddr < after_process.value + 0x300:
                        after_targets[vaddr] = (
                            after.symbol_by_index[symbol_index].name,
                            rtype,
                        )

                expected = dict(before_targets)
                expected[process.value + 0x21B] = (
                    patcher.MOBILE_PATIO_PROP_HELPER_SYMBOL,
                    patcher.IMAGE_REL_I386_REL32,
                )
                self.assertEqual(after_targets, expected)
                self.assertEqual(
                    bytes(
                        after.buf[
                            after_sec.raw_ptr :
                            after_sec.raw_ptr + after_sec.raw_size
                        ]
                    ),
                    before_section_bytes,
                )
                contract = manifest["MobilePatioPropExecution"]
                self.assertEqual(contract["call_offset"], "0x21a")
                self.assertTrue(contract["stock_prop_fallback_preserved"])
                self.assertEqual(
                    contract["guarded_mobile_props"], ["0x55", "0x56"]
                )
                self.assertFalse(
                    contract["pc_environment_array_access_for_patio_prop"]
                )
                self.assertFalse(
                    contract["pc_environment_array_access_for_picnic_prop"]
                )
        finally:
            patcher.PATCHED = old_patched

    def test_mobile_chaise_autonomous_candidate_hook_is_runtime_gated(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                obj_path = patcher.PATCHED / "Villager.obj"
                shutil.copy2(patcher.SRC_OBJS / "Villager.obj", obj_path)
                manifest = {}
                patcher.patch_mobile_furniture_autonomous_candidates(manifest)
                obj = CoffObject(obj_path)
                init_ai = obj.symbol("?InitAI@CVillager@@QAEXXZ")
                init_sec = obj.section(init_ai.section)
                init_raw = init_sec.raw_ptr + init_ai.value + 0x4513
                self.assertEqual(obj.buf[init_raw], 0xE9)
                load_ai = obj.symbol("?LoadAI@CVillager@@QAEXAAUSSaveState@1@@Z")
                load_sec = obj.section(load_ai.section)
                for relative in (0x53, 0x94):
                    self.assertEqual(obj.buf[load_sec.raw_ptr + load_ai.value + relative], 0xE9)
                self.assertEqual(
                    manifest["MobileFurnitureAutonomousCandidates"]["helper"],
                    "_VF2EnableMobileFurnitureCandidates",
                )
        finally:
            patcher.PATCHED = old_patched


class DebuggerResearchTests(unittest.TestCase):
    def test_editor_selector_respects_native_interface_split(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp = Path(tmp)
                shutil.copy2(
                    patcher.SRC_OBJS / "theMainScene.obj",
                    temp / "theMainScene.obj",
                )
                patcher.PATCHED = temp
                manifest = {}

                patcher.patch_debug_features(manifest)

                helper = (temp / "vf2_debug_features.cpp").read_text(
                    encoding="ascii"
                )
                developer = manifest["debug_features"]["developer_keys"]
                self.assertEqual(
                    developer["registered_providers"],
                    [
                        "main scene debugger",
                        "villager manager debugger",
                    ],
                )
                self.assertIn("extern CVillagerManager VillagerManager;", helper)
                self.assertIn(
                    "reinterpret_cast<IDebugger *>(&VillagerManager)",
                    helper,
                )
                self.assertIn(
                    'VF2RegisterDebuggerProvider(gVF2VillagerManagerDebuggerProvider, "villager manager")',
                    helper,
                )
                self.assertEqual(
                    developer["villager_manager_page"],
                    {
                        "global_symbol": "?VillagerManager@@3VCVillagerManager@@A",
                        "debug_function": "?Debug@CVillagerManager@@UAEXXZ",
                        "idbugger_base_offset": 0,
                        "native_lines": [
                            "Pos: %d, %d",
                            "FeetPos: %d, %d",
                            "Current behavior: %d",
                            "Current action: %d",
                            "Next action: %d",
                            "Frame: %d",
                        ],
                    },
                )
                self.assertEqual(
                    developer["editor_selector"]["interface_contract"],
                    (
                        "CWaypointEditor and CLightSourceEditor are IEditor "
                        "objects, not IDebugger providers"
                    ),
                )
                self.assertNotIn(
                    "reinterpret_cast<IDebugger *>(&WaypointEditor)",
                    helper,
                )
                self.assertNotIn(
                    "reinterpret_cast<IDebugger *>(&LightSourceEditor)",
                    helper,
                )
                self.assertIn("VF2SetActiveEditor(&WaypointEditor)", helper)
                self.assertIn("VF2SetActiveEditor(&LightSourceEditor)", helper)
                self.assertIn("VF2SetActiveEditor(0)", helper)
                self.assertEqual(
                    [row["function"] for row in developer["input_hooks"]],
                    [
                        "?HandleKeyDown@theMainScene@@IAE?B_NH@Z",
                        "?HandleKeyCharacter@theMainScene@@IAE?B_ND@Z",
                        "?HandleMouseDown@theMainScene@@IAE?B_NUldwPoint@@@Z",
                        "?HandleMouseMove@theMainScene@@IAE?B_NUldwPoint@@@Z",
                        "?HandleMouseUp@theMainScene@@IAE?B_NUldwPoint@@@Z",
                    ],
                )
                self.assertIn(
                    "VF2PatchedDebuggerMouseDown",
                    helper,
                )
                self.assertIn(
                    "VF2PatchedDebuggerMouseMove",
                    helper,
                )
                self.assertIn(
                    "VF2PatchedDebuggerMouseUp",
                    helper,
                )
                keydown_block = helper.split(
                    'extern "C" bool __cdecl VF2PatchedMainSceneHandleKeyDown',
                    1,
                )[1].split(
                    'extern "C" bool __cdecl VF2PatchedDebuggerKeyCharacter',
                    1,
                )[0]
                self.assertNotIn("VF2SafeEditorKeyCharacter", keydown_block)
                self.assertIn("VF2SafeEditorKeyDown(editor, key)", keydown_block)
                character_block = helper.split(
                    'extern "C" bool __cdecl VF2PatchedDebuggerKeyCharacter',
                    1,
                )[1].split(
                    'extern "C" bool __cdecl VF2PatchedDebuggerKeyUp',
                    1,
                )[0]
                self.assertIn("VF2SafeEditorKeyCharacter(editor, key)", character_block)
                self.assertIn("editor == &LightSourceEditor", character_block)
                self.assertIn("if (key == '+') key = '-';", character_block)
                self.assertIn("else if (key == '-') key = '+';", character_block)
                self.assertEqual(
                    developer["editor_selector"]["character_route"],
                    (
                        "printable editor commands are handled only by the "
                        "dedicated HandleKeyCharacter hook to prevent double "
                        "execution"
                    ),
                )
                editor_block = helper.split("class IEditor {", 1)[1].split(
                    "};",
                    1,
                )[0]
                declarations = [
                    "virtual void Reset();",
                    "virtual void Draw();",
                    "virtual bool const HandleKeyCharacter(char key);",
                    "virtual bool const HandleKeyDown(int key);",
                    "virtual bool const HandleKeyUp(int key);",
                    "virtual bool const HandleMouseDown(ldwPoint point);",
                    "virtual bool const HandleMouseUp(ldwPoint point);",
                    "virtual bool const HandleMouseMove(ldwPoint point);",
                    "virtual void Activate(bool active);",
                ]
                self.assertEqual(
                    [
                        editor_block.index(declaration)
                        for declaration in declarations
                    ],
                    sorted(editor_block.index(value) for value in declarations),
                )

                native_editor = CoffObject(
                    patcher.SRC_OBJS / "LightSourceEditor.obj"
                )
                vtable = native_editor.symbol("??_7CLightSourceEditor@@6B@")
                vtable_section = native_editor.section(vtable.section)
                cursor = vtable_section.reloc_ptr
                native_slots = []
                for _ in range(vtable_section.nreloc):
                    vaddr, symbol_index, _ = struct.unpack_from(
                        "<IIH",
                        native_editor.buf,
                        cursor,
                    )
                    if vaddr >= vtable.value:
                        native_slots.append(
                            native_editor.symbol_by_index[symbol_index].name
                        )
                    cursor += 10
                self.assertEqual(
                    native_slots,
                    [
                        "?Reset@CLightSourceEditor@@UAEXXZ",
                        "?Draw@CLightSourceEditor@@UAEXXZ",
                        "?HandleKeyCharacter@CLightSourceEditor@@UAE?B_ND@Z",
                        "?HandleKeyDown@CLightSourceEditor@@UAE?B_NH@Z",
                        "?HandleKeyUp@CLightSourceEditor@@UAE?B_NH@Z",
                        "?HandleMouseDown@CLightSourceEditor@@UAE?B_NUldwPoint@@@Z",
                        "?HandleMouseUp@CLightSourceEditor@@UAE?B_NUldwPoint@@@Z",
                        "?HandleMouseMove@CLightSourceEditor@@UAE?B_NUldwPoint@@@Z",
                        "?Activate@CLightSourceEditor@@UAEX_N@Z",
                    ],
                )
                CoffObject(temp / "theMainScene.obj")
        finally:
            patcher.PATCHED = old_patched

    def test_input_hooks_preserve_native_stack_and_fallthrough(self):
        def generic_payload(argument_offsets, cleanup):
            payload = bytearray(b"\x51")
            for offset in reversed(argument_offsets):
                payload += b"\xFF\x75" + bytes([offset])
            payload += b"\xE8\x00\x00\x00\x00"
            payload += b"\x83\xC4" + bytes([len(argument_offsets) * 4])
            payload += b"\x59\x84\xC0\x74\x06\xB0\x01\x5D\xC2"
            payload += struct.pack("<H", cleanup)
            return bytes(payload)

        keydown_payload = bytes([
            0x51,
            0xFF, 0x75, 0x08,
            0x51,
            0xE8, 0, 0, 0, 0,
            0x83, 0xC4, 0x08,
            0x59,
            0x84, 0xC0,
            0x74, 0x06,
            0xB0, 0x01,
            0x5D,
            0xC2, 0x04, 0x00,
        ])
        specs = [
            (
                "?HandleKeyDown@theMainScene@@IAE?B_NH@Z",
                "_VF2PatchedMainSceneHandleKeyDown",
                keydown_payload,
                6,
                0x0F,
                0x04,
            ),
            (
                "?HandleKeyCharacter@theMainScene@@IAE?B_ND@Z",
                "_VF2PatchedDebuggerKeyCharacter",
                generic_payload([0x08], 0x04),
                5,
                0x49,
                0x04,
            ),
            (
                "?HandleMouseDown@theMainScene@@IAE?B_NUldwPoint@@@Z",
                "_VF2PatchedDebuggerMouseDown",
                generic_payload([0x08, 0x0C], 0x08),
                8,
                0xC4,
                0x08,
            ),
            (
                "?HandleMouseMove@theMainScene@@IAE?B_NUldwPoint@@@Z",
                "_VF2PatchedDebuggerMouseMove",
                generic_payload([0x08, 0x0C], 0x08),
                8,
                0x50,
                0x08,
            ),
            (
                "?HandleMouseUp@theMainScene@@IAE?B_NUldwPoint@@@Z",
                "_VF2PatchedDebuggerMouseUp",
                generic_payload([0x08, 0x0C], 0x08),
                8,
                0x44,
                0x08,
            ),
        ]

        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp = Path(tmp)
                stock_path = patcher.SRC_OBJS / "theMainScene.obj"
                shutil.copy2(stock_path, temp / "theMainScene.obj")
                patcher.PATCHED = temp
                patcher.patch_debug_features({})

                stock = CoffObject(stock_path)
                patched = CoffObject(temp / "theMainScene.obj")
                for function, helper, payload, call_imm, ret_off, cleanup in specs:
                    stock_symbol = stock.symbol(function)
                    patched_symbol = patched.symbol(function)
                    stock_section = stock.section(stock_symbol.section)
                    patched_section = patched.section(patched_symbol.section)
                    stock_raw = stock_section.raw_ptr + stock_symbol.value
                    patched_raw = patched_section.raw_ptr + patched_symbol.value

                    self.assertEqual(
                        bytes(stock.buf[stock_raw:stock_raw + 3]),
                        b"\x55\x8B\xEC",
                    )
                    self.assertEqual(
                        bytes(patched.buf[patched_raw:patched_raw + 3]),
                        b"\x55\x8B\xEC",
                    )
                    self.assertEqual(
                        bytes(stock.buf[stock_raw + ret_off:stock_raw + ret_off + 3]),
                        b"\xC2" + struct.pack("<H", cleanup),
                    )
                    hook_bytes = bytes(
                        patched.buf[patched_raw + 3:patched_raw + 3 + len(payload)]
                    )
                    self.assertEqual(hook_bytes, payload)
                    test_offset = hook_bytes.index(b"\x84\xC0")
                    self.assertEqual(hook_bytes[test_offset + 2], 0x74)
                    branch_delta = struct.unpack_from("<b", hook_bytes, test_offset + 3)[0]
                    self.assertEqual(
                        test_offset + 4 + branch_delta,
                        len(hook_bytes),
                        "false helper result must branch exactly to the stock body",
                    )
                    self.assertEqual(
                        bytes(
                            patched.buf[
                                patched_raw + 3 + len(payload):
                                patched_raw + 3 + len(payload) + 24
                            ]
                        ),
                        bytes(stock.buf[stock_raw + 3:stock_raw + 27]),
                    )

                    relocation_vaddr = patched_symbol.value + 3 + call_imm
                    matches = []
                    cursor = patched_section.reloc_ptr
                    for _ in range(patched_section.nreloc):
                        vaddr, symbol_index, relocation_type = struct.unpack_from(
                            "<IIH",
                            patched.buf,
                            cursor,
                        )
                        if vaddr == relocation_vaddr:
                            matches.append((symbol_index, relocation_type))
                        cursor += 10
                    self.assertEqual(len(matches), 1)
                    symbol_index, relocation_type = matches[0]
                    self.assertEqual(
                        patched.symbol_by_index[symbol_index].name,
                        helper,
                    )
                    self.assertEqual(
                        relocation_type,
                        patcher.IMAGE_REL_I386_REL32,
                    )
        finally:
            patcher.PATCHED = old_patched


    def test_debugger_fallthrough_validator_pins_six_byte_true_return(self):
        source = (patcher.ROOT / "work" / "validate_b153_debugger_fallthrough.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('b"\\x59\\x84\\xC0\\x74\\x06\\xB0\\x01\\x5D\\xC2"', source)
        self.assertIn("target = branch_end + 6", source)
        self.assertIn("expected_target = start + len(pattern)", source)
        self.assertIn('"villager manager debugger"', source)
        self.assertIn('developer.get("registered_providers")', source)
        builder = (patcher.ROOT / "work" / "build_b153_debugger_test.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn('VF2_ENABLE_DEBUGGER_FEATURES = "1"', builder)
        self.assertIn("validate_b153_debugger_fallthrough.py", builder)

    def test_debugger_uses_vf2_internal_function_and_arrow_key_codes(self):
        source = (patcher.ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
            encoding="utf-8"
        )
        expected = {
            "VF2_KEY_UP": "0x3EE",
            "VF2_KEY_DOWN": "0x3EF",
            "VF2_KEY_F4": "0x3FD",
            "VF2_KEY_F5": "0x3FE",
            "VF2_KEY_F6": "0x3FF",
            "VF2_KEY_F7": "0x400",
        }
        for name, value in expected.items():
            self.assertIn(f"{name} = {value}", source)
        self.assertIn("key == VF2_KEY_F5", source)
        self.assertIn("key == VF2_KEY_F4", source)
        self.assertIn("key == VF2_KEY_F6", source)
        self.assertIn("key == VF2_KEY_F7", source)

    def test_debugger_provider_offsets_match_native_objects(self):
        def relocation_target(obj, section, vaddr):
            cursor = section.reloc_ptr
            matches = []
            for _ in range(section.nreloc):
                reloc_vaddr, symbol_index, relocation_type = struct.unpack_from(
                    "<IIH",
                    obj.buf,
                    cursor,
                )
                if reloc_vaddr == vaddr:
                    matches.append(
                        (
                            obj.symbol_by_index[symbol_index].name,
                            relocation_type,
                        )
                    )
                cursor += 10
            self.assertEqual(len(matches), 1)
            return matches[0]

        main_scene = CoffObject(patcher.SRC_OBJS / "theMainScene.obj")
        constructor = main_scene.symbol("??0theMainScene@@AAE@XZ")
        constructor_section = main_scene.section(constructor.section)
        constructor_raw = constructor_section.raw_ptr + constructor.value
        self.assertEqual(
            bytes(main_scene.buf[constructor_raw + 0x45:constructor_raw + 0x48]),
            b"\xC7\x47\x08",
        )
        target, relocation_type = relocation_target(
            main_scene,
            constructor_section,
            constructor.value + 0x48,
        )
        self.assertEqual(
            target,
            "??_7theMainScene@@6BIDebugger@@@",
        )
        self.assertEqual(relocation_type, patcher.IMAGE_REL_I386_DIR32)

        debugger_vtable = main_scene.symbol(
            "??_7theMainScene@@6BIDebugger@@@"
        )
        vtable_section = main_scene.section(debugger_vtable.section)
        target, relocation_type = relocation_target(
            main_scene,
            vtable_section,
            debugger_vtable.value,
        )
        self.assertEqual(target, "?Debug@theMainScene@@MAEXXZ")
        self.assertEqual(relocation_type, patcher.IMAGE_REL_I386_DIR32)

        villager_manager = CoffObject(patcher.SRC_OBJS / "VillagerManager.obj")
        villager_vtable = villager_manager.symbol("??_7CVillagerManager@@6B@")
        villager_vtable_section = villager_manager.section(villager_vtable.section)
        target, relocation_type = relocation_target(
            villager_manager,
            villager_vtable_section,
            villager_vtable.value,
        )
        self.assertEqual(target, "?Debug@CVillagerManager@@UAEXXZ")
        self.assertEqual(relocation_type, patcher.IMAGE_REL_I386_DIR32)

        villager_iddebugger_base = villager_manager.symbol(
            "??_R1A@?0A@EN@IDebugger@@8"
        )
        villager_base_section = villager_manager.section(
            villager_iddebugger_base.section
        )
        villager_base_raw = (
            villager_base_section.raw_ptr + villager_iddebugger_base.value
        )
        self.assertEqual(
            struct.unpack_from("<iii", villager_manager.buf, villager_base_raw + 8),
            (0, -1, 0),
        )

        debugger = CoffObject(patcher.SRC_OBJS / "Debugger.obj")
        register = debugger.symbol(
            "?Register@CDebugger@@QAE?B_NPAVIDebugger@@@Z"
        )
        register_section = debugger.section(register.section)
        register_raw = register_section.raw_ptr + register.value
        self.assertEqual(
            bytes(debugger.buf[register_raw + 0x03:register_raw + 0x09]),
            b"\x8B\x51\x24\x83\xFA\x08",
        )
        self.assertEqual(
            bytes(debugger.buf[register_raw + 0x14:register_raw + 0x18]),
            b"\x89\x44\x91\x04",
        )
        self.assertEqual(
            bytes(debugger.buf[register_raw + 0x1A:register_raw + 0x1D]),
            b"\xFF\x41\x24",
        )

        draw = debugger.symbol("?Draw@CDebugger@@QAEXXZ")
        draw_section = debugger.section(draw.section)
        draw_raw = draw_section.raw_ptr + draw.value
        self.assertEqual(
            bytes(debugger.buf[draw_raw + 0x03:draw_raw + 0x06]),
            b"\x80\x3E\x00",
        )
        self.assertEqual(
            bytes(debugger.buf[draw_raw + 0x08:draw_raw + 0x0B]),
            b"\x8B\x46\x28",
        )
        self.assertEqual(
            bytes(debugger.buf[draw_raw + 0x0B:draw_raw + 0x0E]),
            b"\xC7\x46\x2C",
        )
        self.assertEqual(
            bytes(debugger.buf[draw_raw + 0x12:draw_raw + 0x15]),
            b"\xC7\x46\x30",
        )
        self.assertEqual(
            bytes(debugger.buf[draw_raw + 0x19:draw_raw + 0x1D]),
            b"\x8B\x4C\x86\x04",
        )

    def test_light_editor_character_commands_have_one_native_route(self):
        editor = CoffObject(patcher.SRC_OBJS / "LightSourceEditor.obj")
        keydown = editor.symbol(
            "?HandleKeyDown@CLightSourceEditor@@UAE?B_NH@Z"
        )
        keydown_section = editor.section(keydown.section)
        keydown_raw = keydown_section.raw_ptr + keydown.value
        self.assertEqual(
            bytes(editor.buf[keydown_raw:keydown_raw + 5]),
            b"\x32\xC0\xC2\x04\x00",
        )

        character = editor.symbol(
            "?HandleKeyCharacter@CLightSourceEditor@@UAE?B_ND@Z"
        )
        character_section = editor.section(character.section)
        self.assertEqual(character.value, 0)
        relocation_targets = set()
        cursor = character_section.reloc_ptr
        for _ in range(character_section.nreloc):
            _, symbol_index, _ = struct.unpack_from(
                "<IIH",
                editor.buf,
                cursor,
            )
            relocation_targets.add(editor.symbol_by_index[symbol_index].name)
            cursor += 10
        self.assertTrue(
            {
                "?DeleteLightSource@CNight@@QAEXH@Z",
                "?AddLightSource@CNight@@QAEXW4ELightSource@@UldwPoint@@@Z",
                "?Save@CNight@@QAEXXZ",
            }.issubset(relocation_targets)
        )

    def test_native_editor_character_key_maps_are_pinned(self):
        light = CoffObject(patcher.SRC_OBJS / "LightSourceEditor.obj")
        character = light.symbol(
            "?HandleKeyCharacter@CLightSourceEditor@@UAE?B_ND@Z"
        )
        section = light.section(character.section)
        jump_table = light.symbol("$LN33")
        character_map = light.symbol("$LN31")
        self.assertEqual(jump_table.section, character.section)
        self.assertEqual(character_map.section, character.section)

        relocation_symbols = {}
        cursor = section.reloc_ptr
        for _ in range(section.nreloc):
            virtual_address, symbol_index, _ = struct.unpack_from(
                "<IIH", light.buf, cursor
            )
            relocation_symbols[virtual_address] = (
                light.symbol_by_index[symbol_index].name
            )
            cursor += 10

        slots = [
            relocation_symbols[jump_table.value + offset]
            for offset in range(0, 24, 4)
        ]
        encoded = bytes(
            light.buf[
                section.raw_ptr + character_map.value:
                section.raw_ptr + character_map.value + 0x49
            ]
        )
        commands = {
            chr(0x2B + index): slots[slot]
            for index, slot in enumerate(encoded)
            if slots[slot] != "$LN2"
        }
        self.assertEqual(
            commands,
            {
                "+": "$LN8",
                "-": "$LN12",
                "D": "$LN4",
                "L": "$LN5",
                "S": "$LN7",
                "d": "$LN4",
                "l": "$LN5",
                "s": "$LN7",
            },
        )

        waypoint = CoffObject(patcher.SRC_OBJS / "WaypointEditor.obj")
        waypoint_character = waypoint.symbol(
            "?HandleKeyCharacter@CWaypointEditor@@UAE?B_ND@Z"
        )
        waypoint_section = waypoint.section(waypoint_character.section)
        waypoint_raw = waypoint_section.raw_ptr + waypoint_character.value
        self.assertEqual(
            bytes(waypoint.buf[waypoint_raw + 0x2C:waypoint_raw + 0x3A]),
            b"\x3C\x53\x74\x74\x3C\x73\x74\x70\x3C\x77\x74\x09\x32\xC0",
        )
        waypoint_targets = set()
        cursor = waypoint_section.reloc_ptr
        for _ in range(waypoint_section.nreloc):
            _, symbol_index, _ = struct.unpack_from(
                "<IIH", waypoint.buf, cursor
            )
            waypoint_targets.add(
                waypoint.symbol_by_index[symbol_index].name
            )
            cursor += 10
        self.assertTrue(
            {
                "?Save@CWaypoint@@IAE?B_NXZ",
                "?ScrollTo@CWorldView@@QAEXUldwPoint@@@Z",
            }.issubset(waypoint_targets)
        )

    def test_default_off_writer_preserves_stock_main_scene(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp = Path(tmp)
                stock_path = patcher.SRC_OBJS / "theMainScene.obj"
                copied_path = temp / "theMainScene.obj"
                shutil.copy2(stock_path, copied_path)
                before = hashlib.sha256(copied_path.read_bytes()).hexdigest()
                patcher.PATCHED = temp
                manifest = {}

                patcher.write_disabled_debug_features(manifest)

                self.assertEqual(
                    hashlib.sha256(copied_path.read_bytes()).hexdigest(),
                    before,
                )
                self.assertEqual(
                    (temp / "vf2_debug_features.cpp").read_text(
                        encoding="ascii"
                    ),
                    "/* Debugger hooks are disabled for normal builds. */\n",
                )
                self.assertEqual(
                    manifest["debug_features"]["status"],
                    "disabled",
                )
        finally:
            patcher.PATCHED = old_patched


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

    def test_loan_returned_restores_the_complete_mobile_paragraph(self):
        events = {event["name"]: event for event in patcher.load_mobile_island_events()}
        description = next(
            row["text"]
            for row in events["LoanReturned"]["strings"]
            if row["kind"] == "Desc"
        )
        self.assertIn("a transformed man", description)
        self.assertIn("instead of a handout changed his trajectory", description)
        self.assertIn("came here today to repay the loan", description)
        self.assertTrue(description.endswith("in person."))
        self.assertGreater(len(description), 500)


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
                self.assertIn(
                    "EnableAdultOnlyAutonomousCandidateWithWeight(data, 0x08E, 700); // IroningShirt",
                    helper,
                )
                self.assertIn(
                    "EnableAllAgesAutonomousCandidateWithWeight(data, 0x127, 450); // RestingBody / Needs to sit down",
                    helper,
                )
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
                self.assertIn('extern "C" void __stdcall VF2ScoldAwardAndForget', helper)
                self.assertIn("for (int i = 0; i < 0x28; ++i)", helper)
                self.assertIn("VF2RestoreRawPraiseLabel(villager);", helper)
                self.assertIn("static bool VF2RawBehaviorLabelEquals", helper)
                for label, goal_id in patcher.CUSTOM_ACHIEVEMENT_PRAISE_LABEL_GOALS.items():
                    self.assertIn(
                        f'VF2RawBehaviorLabelEquals(label, "{label}")', helper
                    )
                    self.assertIn(
                        f"Achievement.SetComplete((EAchievement)0x{goal_id:X})",
                        helper,
                    )
                praise_wrapper = helper.split(
                    'extern "C" void __stdcall VF2PraiseCaptureAndForget', 1
                )[1].split(
                    'extern "C" void __stdcall VF2PraiseStartAndRestore', 1
                )[0]
                self.assertLess(
                    praise_wrapper.index("VF2CopyRawPraiseLabel"),
                    praise_wrapper.index("VF2AwardExactPraiseLabel"),
                )
                self.assertLess(
                    praise_wrapper.index("VF2AwardExactPraiseLabel"),
                    praise_wrapper.index("plans->ForgetPlans"),
                )
                scold_wrapper = helper.split(
                    'extern "C" void __stdcall VF2ScoldAwardAndForget', 1
                )[1].split("class CFurnitureManager", 1)[0]
                self.assertIn('VF2RawBehaviorLabelEquals(label, "Scolding pet")', scold_wrapper)
                self.assertIn('VF2RawBehaviorLabelEquals(label, "Posting on Fakebook")', scold_wrapper)
                self.assertIn('VF2RawBehaviorLabelEquals(label, "Posting on ClipTok")', scold_wrapper)
                self.assertIn('VF2RawBehaviorLabelEquals(label, "Posting on Picstagram")', scold_wrapper)
                self.assertIn('VF2RawBehaviorLabelEquals(label, "Procrastinating")', scold_wrapper)
                self.assertIn('VF2RawBehaviorLabelEquals(label, "Throwing clothes on the floor")', scold_wrapper)
                self.assertIn('VF2RawBehaviorLabelEquals(label, "Playing in the toilet")', scold_wrapper)
                self.assertIn('VF2RawBehaviorLabelEquals(label, "Drawing on the wall")', scold_wrapper)
                self.assertIn('VF2RawBehaviorLabelEquals(label, "Switching light on and off")', scold_wrapper)
                self.assertIn(
                    "*(int *)((unsigned char *)&villager + 0x6A54) < 0x118",
                    scold_wrapper,
                )
                self.assertIn("VF2MaybeCompleteDisciplineProps();", scold_wrapper)
                self.assertEqual(scold_wrapper.count("plans->ForgetPlans"), 1)
                self.assertNotIn("return;", scold_wrapper)
                self.assertNotIn("VF2RestoreRawPraiseLabel", scold_wrapper)
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
                scold = main_obj.symbol(
                    "?InvokeScolding@theMainScene@@IAEXAAVCVillager@@@Z"
                )
                scold_sec = main_obj.section(scold.section)
                scold_data = bytes(
                    main_obj.buf[
                        scold_sec.raw_ptr + scold.value :
                        scold_sec.raw_ptr + scold.value + 0x1EA
                    ]
                )
                self.assertEqual(
                    scold_data[0x112:0x11C],
                    b"\x6A\x00\x53\x8B\xCB\xE8\x00\x00\x00\x00",
                )
                scold_targets = {
                    vaddr - scold.value: main_obj.symbol_by_index[symbol_index].name
                    for vaddr, symbol_index, _rtype in (
                        struct.unpack_from(
                            "<IIH", main_obj.buf, scold_sec.reloc_ptr + index * 10
                        )
                        for index in range(scold_sec.nreloc)
                    )
                    if scold.value <= vaddr < scold.value + 0x1EA
                }
                self.assertEqual(scold_targets[0x118], "_VF2ScoldAwardAndForget@8")
                self.assertEqual(
                    [offset for offset, target in scold_targets.items() if target == "_VF2ScoldAwardAndForget@8"],
                    [0x118],
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

    def test_all_custom_achievement_strings_are_exact_and_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(
                patcher.SRC_OBJS / "theStringManager.obj",
                temp_root / "theStringManager.obj",
            )
            old_patched = patcher.PATCHED
            try:
                patcher.PATCHED = temp_root
                manifest = {}
                patcher.patch_string_manager(manifest)

                rows = [
                    row for row in manifest["theStringManager"]["strings"]
                    if row.get("source") == "custom achievement"
                ]
                self.assertEqual(len(rows), len(patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS) * 2)
                by_id_role = {
                    (int(row["achievement_id"], 16), row["role"]): row
                    for row in rows
                }
                for achievement_id, group, title, description in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS:
                    title_id, description_id = patcher.custom_achievement_string_ids(
                        achievement_id
                    )
                    self.assertEqual(
                        by_id_role[(achievement_id, "title")],
                        {
                            "pc_string_id": hex(title_id),
                            "source": "custom achievement",
                            "achievement_id": hex(achievement_id),
                            "group": group,
                            "role": "title",
                            "key": f"eString_CustomAchievement{achievement_id:02X}Title",
                            "text": title,
                        },
                    )
                    self.assertEqual(
                        by_id_role[(achievement_id, "description")]["pc_string_id"],
                        hex(description_id),
                    )
                    self.assertEqual(
                        by_id_role[(achievement_id, "description")]["text"],
                        description,
                    )
                self.assertEqual(patcher.custom_achievement_string_base(), 0xE05)
                self.assertEqual(
                    patcher.custom_achievement_string_ids(0x7F)[1], 0xE44
                )
                self.assertEqual(
                    patcher.custom_achievement_string_ids(0xA7)[1], 0xE94
                )
                reserved = [
                    row for row in manifest["theStringManager"]["strings"]
                    if row.get("source")
                    == "custom achievement reserved capacity"
                ]
                self.assertEqual(len(reserved), 2)
                self.assertEqual(
                    {int(row["achievement_id"], 16) for row in reserved},
                        {0xA7},
                )
                self.assertTrue(all(row["text"] == "" for row in reserved))
                self.assertEqual(
                    patcher.holiday_ornament_collection_footer_string_ids(),
                    (0xE95, 0xE96, 0xE97),
                )
                lounger_rows = [
                    row for row in manifest["theStringManager"]["strings"]
                    if row.get("source") == "mobile lounge chair translated refusal"
                ]
                self.assertEqual(lounger_rows, [{
                    "pc_string_id": hex(patcher.mobile_lounger_bad_weather_string_id()),
                    "source": "mobile lounge chair translated refusal",
                    "key": "eString_VF2LoungerBadWeather",
                    "text": "Don't like the weather!",
                }])
            finally:
                patcher.PATCHED = old_patched

    def test_holiday_collection_screen_uses_ornament_only_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            shutil.copy2(
                patcher.SRC_OBJS / "theStringManager.obj",
                temp_root / "theStringManager.obj",
            )
            old_patched = patcher.PATCHED
            old_ornaments = patcher.ENABLE_HOLIDAY_ORNAMENTS
            try:
                patcher.PATCHED = temp_root
                patcher.ENABLE_HOLIDAY_ORNAMENTS = True
                manifest = {}
                patcher.patch_string_manager(manifest)

                collection_rows = [
                    row
                    for row in manifest["theStringManager"]["strings"]
                    if row.get("source") in {
                        "holiday ornament collection page",
                        "holiday ornament collection footer",
                    }
                ]
                title_rows = [
                    row
                    for row in collection_rows
                    if row["source"] == "holiday ornament collection page"
                ]
                self.assertEqual(
                    title_rows,
                    [{
                        "pc_string_id": hex(
                            patcher.holiday_ornament_collection_title_string_id()
                        ),
                        "source": "holiday ornament collection page",
                        "key": "eString_CollectionHolidayOrnaments",
                        "text": "Ornaments",
                    }],
                )
                self.assertEqual(
                    patcher.holiday_ornament_collection_footer_string_ids(),
                    (0xE95, 0xE96, 0xE97),
                )
                footer_rows = [
                    row
                    for row in collection_rows
                    if row["source"] == "holiday ornament collection footer"
                ]
                self.assertEqual(
                    [
                        (
                            int(row["pc_string_id"], 16),
                            row["rarity"],
                            row["key"],
                            row["text"],
                        )
                        for row in footer_rows
                    ],
                    [
                        (0xE95, "common", "eSayCommonOrnaments",
                         " of 4 common ornaments found."),
                        (0xE96, "uncommon", "eSayUncommonOrnaments",
                         " of 4 uncommon ornaments found."),
                        (0xE97, "rare", "eSayRareOrnaments",
                         " of 4 rare ornaments found."),
                    ],
                )
                self.assertFalse(
                    any("bottle cap" in row["text"].lower() for row in collection_rows)
                )
                achievement_rows = [
                    row
                    for row in manifest["theStringManager"]["strings"]
                    if row.get("source") == "mobile holiday ornament achievement"
                ]
                self.assertIn(
                    "You completed the collection of holiday ornaments.",
                    [row["text"] for row in achievement_rows],
                )
            finally:
                patcher.PATCHED = old_patched
                patcher.ENABLE_HOLIDAY_ORNAMENTS = old_ornaments

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

    def test_career_behavior_label_uses_requested_job_project_wording(self):
        groups = dict(patcher.BEHAVIOR_LABEL_GROUPS)
        self.assertIn(
            ("eString_TakingBossAdvice", "Taking boss' advice on a job project"),
            groups["career"],
        )
        self.assertNotIn(
            ("eString_TakingBossAdvice", "Taking boss's advice on a career project"),
            groups["career"],
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
        self.assertEqual(rows[0x12E]["name"], "Complete all Achievements")
        self.assertIn("normal coin reward", rows[0x12E]["description"])
        self.assertEqual(rows[0x12F]["name"], "Fill available house slots with trash")
        self.assertIn("available collectable slot", rows[0x12F]["description"])
        self.assertEqual(rows[0x130]["name"], "Fill available yard slots with weeds")
        self.assertIn("Existing collectables are preserved", rows[0x130]["description"])
        self.assertEqual(rows[0x131]["name"], "Clean Garden")
        self.assertIn("without affecting other collectables", rows[0x131]["description"])
        self.assertEqual(rows[0x132]["name"], "Spawn Marriage Email")
        self.assertEqual(
            rows[0x132]["description"],
            "Queues an incoming marriage proposal email.",
        )
        self.assertEqual(rows[0x133]["name"], "Max out sock pile")
        self.assertIn("largest visible size of 30 socks", rows[0x133]["description"])
        self.assertEqual(rows[0x134]["name"], "No sock pile")
        self.assertIn("without awarding sock-laundering progress", rows[0x134]["description"])
        self.assertEqual(rows[0x135]["name"], "Clean House")
        self.assertIn("stock Housekeeping Services event", rows[0x135]["description"])
        self.assertIn("Yard weeds", rows[0x135]["description"])
        self.assertIn("laundry-room sock pile", rows[0x135]["description"])
        self.assertEqual(rows[0x136]["name"], "Force Successful Pregnancy")
        self.assertIn("next eligible try-for-baby attempt", rows[0x136]["description"])
        self.assertIn("until the native birth routine succeeds", rows[0x136]["description"])
        self.assertEqual(rows[0x137]["name"], "Next Babies Male")
        self.assertEqual(rows[0x138]["name"], "Next Babies Female")
        self.assertEqual(rows[0x139]["name"], "Next Pregnancy Singleton")
        self.assertEqual(rows[0x13A]["name"], "Next Pregnancy Twins")
        self.assertEqual(rows[0x13B]["name"], "Next Pregnancy Triplets")
        self.assertIn("available capacity", rows[0x13A]["description"])
        self.assertIn("available capacity", rows[0x13B]["description"])
        self.assertEqual(patcher.CHEAT_UPGRADE_LEGACY_COUNT, 19)
        self.assertEqual(patcher.CHEAT_UPGRADE_STRING_COUNT, 38)
        self.assertEqual(
            patcher.cheat_upgrade_string_ids_for_entry(19)[0],
            patcher.holiday_ornament_collection_footer_string_ids()[-1] + 1,
        )
        self.assertEqual(
            patcher.VISIBLE_SPECIAL_UPGRADE_ICON_FILES[0x127],
            "cheat_reset_achievements.png",
        )
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[0x12E], 0x124)
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[0x12F], 0x124)
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[0x130], 0x124)
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[0x131], 0x124)
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[0x132], 0x124)
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[0x133], 0x124)
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[0x134], 0x124)
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[0x135], 0x124)
        self.assertEqual(patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[0x136], 0x124)
        for item_id in range(0x137, 0x13C):
            self.assertEqual(
                patcher.VISIBLE_SPECIAL_UPGRADE_ICON_ALIASES[item_id],
                0x124,
            )
        self.assertEqual(
            patcher.visible_special_upgrade_icon_id_for(0x12E),
            patcher.visible_special_upgrade_icon_id_for(0x124),
        )
        item_ids = [item["item_id"] for item in patcher.CHEAT_UPGRADE_ITEMS]
        self.assertEqual(
            item_ids,
            [
                0x11B, 0x11D, 0x11E, 0x11F,
                0x11C, 0x120, 0x121, 0x122,
                0x123, 0x124, 0x12E, 0x125, 0x126, 0x127,
                0x128, 0x129, 0x12A, 0x12C,
                0x12B, 0x12D,
                0x12F, 0x135,
                0x130, 0x131,
                0x133, 0x134,
                0x132,
                0x136,
                0x137, 0x138,
                0x139, 0x13A, 0x13B,
            ],
        )
        self.assertEqual(item_ids.index(0x12E), item_ids.index(0x124) + 1)
        self.assertEqual(item_ids.index(0x135), item_ids.index(0x12F) + 1)
        self.assertEqual(item_ids.index(0x131), item_ids.index(0x130) + 1)
        self.assertEqual(item_ids.index(0x134), item_ids.index(0x133) + 1)

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
        self.assertIn("static void VF2CompleteAchievementForCheat(int achievement)", source)
        self.assertIn("if (!Achievement.IsComplete(id))", source)
        self.assertIn("static void VF2ClearAchievementNotificationQueueRaw()", source)
        self.assertIn("(unsigned char *)&Achievement + 0xDBC", source)
        self.assertIn("for (int index = 0; index < 0x5F; ++index)", source)
        self.assertLess(
            source.index("VF2ClearAchievementNotificationQueueRaw();"),
            source.index("Achievement.SetComplete(id);"),
        )
        self.assertIn("static void VF2CompleteAllAchievements()", source)
        self.assertIn("for (int achievement = 0x00; achievement <= 0x5E; ++achievement)", source)
        self.assertIn("if (kVF2IncludeOrnamentologistGoal)", source)
        self.assertIn("if (kVF2IncludeBehaviorGoals)", source)
        self.assertIn(
            "for (int achievement = 0x80; achievement <= 0x91; ++achievement)",
            source,
        )
        self.assertIn("if (gVF2HolidayFurnitureGoalsEnabled != 0)", source)
        self.assertIn("case 0x12E:", source)
        self.assertIn("VF2CompleteAllAchievements();", source)
        self.assertIn("if (itemId >= 0x12E && itemId <= 0x13B) itemId = 0x124;", source)
        self.assertIn("case 0x12F:", source)
        self.assertIn("CollectableItem.SpawnTrashInHouse(30);", source)
        self.assertIn("case 0x130:", source)
        self.assertIn("CollectableItem.SpawnWeedsInYard(30);", source)
        self.assertIn("case 0x131:", source)
        self.assertIn("CollectableItem.RemoveAll((ECarrying)0x7D);", source)
        self.assertIn("case 0x132:", source)
        self.assertIn("eEmailMessageMarriageProposal = 2", source)
        self.assertIn(
            "theGameState::Get()->QueueEmailMessage(\n"
            "            eEmailMessageMarriageProposal\n"
            "        );",
            source,
        )
        self.assertIn("static void VF2SetSockPileCount(int count)", source)
        self.assertIn("*(int *)(gameState + 0x148) = count;", source)
        self.assertIn("case 0x133:", source)
        self.assertIn("VF2SetSockPileCount(30);", source)
        self.assertIn("case 0x134:", source)
        self.assertIn("VF2SetSockPileCount(0);", source)
        self.assertIn("static void VF2CleanHouse()", source)
        self.assertIn("CollectableItem.RemoveAll((ECarrying)0x73);", source)
        self.assertIn("CollectableItem.RemoveAll((ECarrying)0x79);", source)
        self.assertIn("CollectableItem.RemoveAll((ECarrying)0x81);", source)
        self.assertIn("CollectableItem.RemoveAll((ECarrying)0x83);", source)
        self.assertIn("case 0x135:", source)
        self.assertIn("VF2CleanHouse();", source)
        self.assertIn("case 0x136:", source)
        self.assertIn("VF2PersistentCheatAndPurchaseMask() |= 0x4;", source)
        for item_id in range(0x137, 0x13C):
            self.assertIn(f"case 0x{item_id:X}:", source)

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
                    self.assertIn("InventoryManager.ReturnOne((EInventoryItem)mode);", source)
                    self.assertIn("bool disable = InventoryManager.HaveUpgrade((EInventoryItem)itemId);", source)
                    self.assertIn("if (!disable) InventoryManager.TakeOne((EInventoryItem)itemId);", source)
                    self.assertIn("if (InventoryManager.HaveUpgrade((EInventoryItem)0x12A)) multiplier = 100;", source)
                    self.assertIn("else if (InventoryManager.HaveUpgrade((EInventoryItem)0x129)) multiplier = 5;", source)
                    self.assertIn("else if (InventoryManager.HaveUpgrade((EInventoryItem)0x128)) multiplier = 2;", source)
                    self.assertIn("if (price <= 0 || multiplier == 1) return price;", source)
                    self.assertIn("VF2ResetB150PriceMode();", source)
                    patch_source = Path(patcher.__file__).read_text(encoding="utf-8")
                    self.assertIn(
                        "case 0x12C:\n        VF2ResetB150PriceMode();\n        break;",
                        patch_source,
                    )
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
                    price_contract = manifest["ScrollingStoreScene"]["price_multiplier"]
                    self.assertEqual(price_contract["enabled"], enabled)
                    if enabled:
                        self.assertEqual(price_contract["multipliers"], [2, 5, 100])
                        self.assertEqual(
                            price_contract["verified_categories"],
                            [
                                "furniture",
                                "flea market",
                                "Special Upgrades",
                                "house renovations 0xE1-0xEA",
                                "career upgrade 0x10F",
                            ],
                        )
                        self.assertEqual(
                            {row["path"] for row in price_contract["patches"]},
                            {"career upgrade", "ordinary purchase"},
                        )
                        self.assertEqual(
                            price_contract["overflow"],
                            "saturates at signed INT_MAX",
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
                self.assertEqual(frames[0]["offset"], [0, 0])
                self.assertEqual(
                    frames[0]["size"],
                    [patcher.HOLIDAY_BODY_CELL_SIZE] * 2,
                )
                with Image.open(images / frames[0]["path"]) as saved:
                    self.assertEqual(
                        saved.size,
                        (patcher.HOLIDAY_BODY_CELL_SIZE,) * 2,
                    )
                self.assertFalse(manifest["holiday_body_runtime_frames"]["issues"])
        finally:
            patcher.OUT = old_out
            patcher.HOLIDAY_BODY_VALUES = old_values
            patcher.HOLIDAY_BODY_SET_IDS = old_sets
            patcher.HOLIDAY_BODY_ROLE_SPECS = old_specs


    def test_purchase_award_hook_retargets_only_add_to_storage_and_precedes_save(self):
        old_patched = patcher.PATCHED
        old_cheats = patcher.ENABLE_CHEAT_UPGRADES
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                patcher.ENABLE_CHEAT_UPGRADES = False
                shutil.copy2(
                    patcher.SRC_OBJS / "ScrollingStoreScene.obj",
                    patcher.PATCHED / "ScrollingStoreScene.obj",
                )
                manifest = {}
                patcher.patch_scrolling_store_scene(manifest)
                patcher.write_outfit_store_helpers(manifest)

                obj = CoffObject(patcher.PATCHED / "ScrollingStoreScene.obj")
                purchase = obj.symbol("?HandlePurchaseItem@CScrollingStoreScene@@AAEXXZ")
                section = obj.section(purchase.section)
                data = bytes(
                    obj.buf[
                        section.raw_ptr + purchase.value :
                        section.raw_ptr + purchase.value + 0x398
                    ]
                )
                self.assertEqual(
                    data[0x2D0:0x2EE],
                    b"\x3D\x28\x03\x00\x00\x7D\x39\x50"
                    b"\xB9\x00\x00\x00\x00\xE8\x00\x00\x00\x00"
                    b"\xE8\x00\x00\x00\x00\x8B\xC8\xE8\x00\x00\x00\x00",
                )
                self.assertEqual(
                    data[0x360:0x36C],
                    b"\xE8\x00\x00\x00\x00\x8B\xC8\xE8\x00\x00\x00\x00",
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
                    targets[0x2DE],
                    "?AddToStorageAndAward@CFurnitureManager@@QAE_NW4EInventoryItem@@@Z",
                )
                self.assertEqual(
                    targets[0x2D9], "?FurnitureManager@@3VCFurnitureManager@@A"
                )
                self.assertEqual(
                    targets[0x2E3], "?Get@theMainScene@@SAPAV1@XZ"
                )
                self.assertEqual(
                    targets[0x2EA], "?TurnDecorateModeOn@theMainScene@@QAEXXZ"
                )
                self.assertEqual(
                    targets[0x361], "?Get@theGameState@@SAPAV1@XZ"
                )
                self.assertEqual(
                    targets[0x368], "?SaveCurrentGame@theGameState@@QAE_NXZ"
                )
                self.assertNotIn(
                    "?AddToStorage@CFurnitureManager@@QAE_NW4EInventoryItem@@@Z",
                    [targets.get(0x2DE)],
                )

                helper = (
                    patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
                ).read_text(encoding="ascii")
                self.assertEqual(helper.count("enum EInventoryItem"), 1)
                self.assertEqual(helper.count("class CFurnitureManager"), 1)
                wrapper = helper.split(
                    "bool CFurnitureManager::AddToStorageAndAward(EInventoryItem item)",
                    1,
                )[1]
                wrapper = wrapper.split("struct sFurnitureInfo", 1)[0]
                self.assertLess(wrapper.index("bool stored = AddToStorage(item);"), wrapper.index("if (stored)"))
                self.assertLess(wrapper.index("if (stored)"), wrapper.index("VF2DispatchSuccessfulFurniturePurchase(item);"))
                self.assertLess(wrapper.index("VF2DispatchSuccessfulFurniturePurchase(item);"), wrapper.index("return stored;"))
                for item_id, goal_id in {
                    **patcher.CUSTOM_ACHIEVEMENT_GENERAL_PURCHASE_GOALS,
                    **patcher.CUSTOM_ACHIEVEMENT_HOLIDAY_PURCHASE_GOALS,
                }.items():
                    self.assertIn(
                        f"case 0x{item_id:X}: return 0x{goal_id:X};", helper
                    )
                self.assertIn("(unsigned char *)&Achievement + 0xA8 * 12", helper)
                self.assertIn("if ((int)item == 0x2CF) purchaseBit = 0x1;", helper)
                self.assertIn("if ((int)item == 0x2CC) purchaseBit = 0x2;", helper)
                self.assertIn("if (oldMask != 0x3 && newMask == 0x3)", helper)
                self.assertEqual(
                    manifest["ScrollingStoreScene"]["custom_achievement_purchase_hook"]["operand_offset"],
                    "0x2de",
                )
        finally:
            patcher.PATCHED = old_patched
            patcher.ENABLE_CHEAT_UPGRADES = old_cheats


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


class CustomAchievementAwardDispatchTests(unittest.TestCase):
    def test_achiever_extraordinaire_is_final_and_checks_selected_visible_order(self):
        rows = {
            achievement_id: (group, title, description)
            for achievement_id, group, title, description
            in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS
        }
        self.assertEqual(
            rows[0x92],
            (
                "meta",
                "Achiever Extraordinaire",
                "Complete every enabled achievement.",
            ),
        )
        self.assertEqual(
            rows[0x93],
            (
                "pet_behavior",
                "Pavlovian Association",
                "You praised someone for training a pet.",
            ),
        )
        self.assertEqual(
            {
                achievement_id: rows[achievement_id]
                for achievement_id in range(0x94, 0x98)
            },
            {
                0x94: (
                    "behavior",
                    "Fakebook Fakery",
                    "You scolded someone for posting on Fakebook.",
                ),
                0x95: (
                    "behavior",
                    "Dance Dunce",
                    "You scolded someone for posting on ClipTok.",
                ),
                0x96: (
                    "behavior",
                    "The Last Trend",
                    "You scolded someone for posting on Clipstagram.",
                ),
                0x97: (
                    "behavior",
                    "Lazy Crazy",
                    "You scolded a child for procrastinating.",
                ),
            },
        )
        self.assertEqual(
            {
                achievement_id: rows[achievement_id][1]
                for achievement_id in range(0x98, 0xA1)
            },
            {
                0x98: "Sim-ling Rivalry",
                0x99: "Blocky Business",
                0x9A: "Dovahkiin",
                0x9B: "Reshaping the World",
                0x9C: "Farming Fanatic",
                0x9D: "Forum Browser",
                0x9E: "Explore, Collect, Compete",
                0x9F: "Waddle On!",
                0xA0: "Pixel Pets",
            },
        )
        self.assertEqual(
            {
                achievement_id: rows[achievement_id][1]
                for achievement_id in range(0xA1, 0xA6)
            },
            {
                0xA1: "No clothes-throwing!",
                0xA2: "No playing in the toilet!",
                0xA3: "No drawing on the wall!",
                0xA4: "No messing with the light switch!",
                0xA5: "Props to you",
            },
        )
        self.assertEqual(
            rows[0xA6],
            (
                "vf3_furniture",
                "Furnishing the Future",
                "You bought a Virtual Families 3 furniture item.",
            ),
        )
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "appended_order.append(CUSTOM_ACHIEVEMENT_ACHIEVER_ID)",
            source,
        )
        self.assertIn(
            "int achievementId = achievementOrder[index];",
            source,
        )
        self.assertIn("if (achievementId == 0x92) continue;", source)
        self.assertIn(
            "if (!achievement->IsComplete((EAchievement)achievementId)) return;",
            source,
        )
        self.assertIn("achievement->SetComplete(achiever);", source)

    def test_achiever_load_reconciliation_is_relocation_only(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                source_obj = patcher.SRC_OBJS / "theGameState.obj"
                target_obj = temp_root / "theGameState.obj"
                shutil.copy2(source_obj, target_obj)
                before = CoffObject(target_obj)
                load_before = before.symbol("?Load@theGameState@@UAE_NH@Z")
                section_before = before.section(load_before.section)
                section_bytes = bytes(
                    before.buf[
                        section_before.raw_ptr :
                        section_before.raw_ptr + section_before.raw_size
                    ]
                )

                manifest = {}
                patcher.patch_achiever_load_reconciliation(manifest)

                after = CoffObject(target_obj)
                load = after.symbol("?Load@theGameState@@UAE_NH@Z")
                section = after.section(load.section)
                self.assertEqual(
                    bytes(
                        after.buf[
                            section.raw_ptr :
                            section.raw_ptr + section.raw_size
                        ]
                    ),
                    section_bytes,
                )
                targets = []
                for index in range(section.nreloc):
                    vaddr, symbol_index, rtype = struct.unpack_from(
                        "<IIH",
                        after.buf,
                        section.reloc_ptr + index * 10,
                    )
                    if vaddr == load.value + 0x134:
                        targets.append(
                            (after.symbol_by_index[symbol_index].name, rtype)
                        )
                self.assertEqual(
                    targets,
                    [(
                        patcher.ACHIEVER_LOAD_HELPER_SYMBOL,
                        patcher.IMAGE_REL_I386_REL32,
                    )],
                )
                self.assertEqual(
                    manifest["AchieverExtraordinaire"]["achievement_id"],
                    "0x92",
                )
                self.assertTrue(
                    manifest["AchieverExtraordinaire"]["must_be_last"]
                )
        finally:
            patcher.PATCHED = old_patched

    def test_birthday_purchase_goal_ids_and_item_ids_are_exact(self):
        self.assertEqual(
            {
                item_id: goal_id
                for item_id, goal_id in patcher.CUSTOM_ACHIEVEMENT_GENERAL_PURCHASE_GOALS.items()
                if goal_id in range(0x80, 0x83)
            },
            {
                0x2DB: 0x80,
                0x2DC: 0x81,
                0x2DA: 0x82,
            },
        )
        rows = {
            achievement_id: (group, title, description)
            for achievement_id, group, title, description in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS
        }
        self.assertEqual(
            {achievement_id: rows[achievement_id] for achievement_id in range(0x80, 0x83)},
            {
                0x80: ("birthday_furniture", "Happy Birthday", "You bought a Birthday Banner."),
                0x81: ("birthday_furniture", "Not a lie", "You bought a Birthday Cake."),
                0x82: ("birthday_furniture", "Full of helium", "You bought Birthday Balloons."),
            },
        )

    def test_maximum_resource_goal_rows_and_exact_thresholds(self):
        rows = {
            achievement_id: (group, title, description)
            for achievement_id, group, title, description
            in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS
        }
        self.assertEqual(
            {achievement_id: rows[achievement_id] for achievement_id in range(0x83, 0x85)},
            {
                0x83: (
                    "resource",
                    "No More Worries",
                    "Have the maximum amount of coins in the bank account.",
                ),
                0x84: (
                    "resource",
                    "Solving World Hunger",
                    "Have the maximum amount of food in the fridge.",
                ),
            },
        )
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        self.assertIn("Money.balance == 4000000000.0", source)
        self.assertIn("FoodStore.food == 0x7FFFFFFF", source)
        self.assertIn(
            "VF2MoneySetAndAward(&Money, 0, 4000000000.0);",
            source,
        )
        self.assertNotIn("3999999999.0", source)
        self.assertIn(
            "patch_maximum_resource_achievement_callsites(manifest)",
            source,
        )

    def test_longevity_goal_rows_and_raw_age_boundaries(self):
        rows = {
            achievement_id: (group, title, description)
            for achievement_id, group, title, description
            in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS
        }
        self.assertEqual(
            {achievement_id: rows[achievement_id] for achievement_id in range(0x85, 0x8A)},
            {
                0x85: ("longevity", "Lucky 70's", "Have a person reach age 70."),
                0x86: ("longevity", "Great 80's", "Have a person reach age 80."),
                0x87: ("longevity", "Mighty 90's", "Have a person reach age 90."),
                0x88: ("longevity", "Centenarian", "Have a person reach age 100 or more."),
                0x89: (
                    "longevity",
                    "Oldest Person in History",
                    "Have a person surpass age 122.",
                ),
            },
        )
        expected = {
            1399: [],
            1400: [0x85],
            1599: [0x85],
            1600: [0x85, 0x86],
            1800: [0x85, 0x86, 0x87],
            2000: [0x85, 0x86, 0x87, 0x88],
            2440: [0x85, 0x86, 0x87, 0x88],
            2441: [0x85, 0x86, 0x87, 0x88, 0x89],
        }
        self.assertEqual(
            {
                age: patcher.longevity_achievement_ids_for_internal_age(age)
                for age in expected
            },
            expected,
        )

    def test_pet_goal_rows_and_exact_live_item_predicates(self):
        rows = {
            achievement_id: (group, title, description)
            for achievement_id, group, title, description
            in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS
        }
        self.assertEqual(
            {achievement_id: rows[achievement_id] for achievement_id in range(0x8A, 0x90)},
            {
                0x8A: ("pet", "A Furry Companion", "Buy a pet and place it in the house."),
                0x8B: ("pet", "The Cat's Meow", "Welcome a black kitten, snow white cat, tabby cat, hairless cat, or fluffy grey cat into the home."),
                0x8C: ("pet", "Man's Best Friend", "Welcome a beagle, yellow lab, black lab, longhair puppy, or chihuahua into the home."),
                0x8D: ("pet", "Itsy Bitsy", "Have a tarantula in the home."),
                0x8E: ("pet", "Hampster Dance", "Have a hamster in the house."),
                0x8F: ("pet", "Lovely Lizards", "Have a lizard in the house."),
            },
        )
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x23A), [])
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x23B), [0x8A, 0x8B])
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x23F), [0x8A, 0x8B])
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x240), [0x8A, 0x8C])
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x244), [0x8A, 0x8C])
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x245), [0x8A])
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x246), [0x8A, 0x8F])
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x247), [0x8A, 0x8E])
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x248), [0x8A, 0x8D])
        self.assertEqual(patcher.pet_achievement_ids_for_item(0x249), [])
        self.assertEqual(
            patcher.pet_achievement_ids_for_item(0x23B, active=False),
            [],
        )

    def test_pet_goal_hooks_are_relocation_only_and_success_filtered(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                for filename in ("FurnitureManager.obj", "theGameState.obj"):
                    shutil.copy2(patcher.SRC_OBJS / filename, temp_root / filename)

                before = {}
                for filename in ("FurnitureManager.obj", "theGameState.obj"):
                    obj = CoffObject(temp_root / filename)
                    before[filename] = {
                        section.index: bytes(
                            obj.buf[
                                section.raw_ptr :
                                section.raw_ptr + section.raw_size
                            ]
                        )
                        for section in obj.sections
                    }

                manifest = {}
                patcher.patch_pet_achievement_callsites(manifest)

                expected = {
                    "FurnitureManager.obj": (
                        "?DropFurniture@CFurnitureManager@@QAEX_N@Z",
                        0x21E,
                        patcher.PET_SPAWN_HELPER_SYMBOL,
                    ),
                    "theGameState.obj": (
                        "?Load@theGameState@@UAE_NH@Z",
                        0x251,
                        patcher.PET_LOAD_HELPER_SYMBOL,
                    ),
                }
                for filename, (function, relative, helper) in expected.items():
                    obj = CoffObject(temp_root / filename)
                    symbol = obj.symbol(function)
                    section = obj.section(symbol.section)
                    self.assertEqual(
                        bytes(
                            obj.buf[
                                section.raw_ptr :
                                section.raw_ptr + section.raw_size
                            ]
                        ),
                        before[filename][section.index],
                    )
                    targets = []
                    for index in range(section.nreloc):
                        vaddr, symbol_index, rtype = struct.unpack_from(
                            "<IIH", obj.buf, section.reloc_ptr + index * 10
                        )
                        if vaddr == symbol.value + relative:
                            targets.append((
                                obj.symbol_by_index[symbol_index].name,
                                rtype,
                            ))
                    self.assertEqual(
                        targets,
                        [(helper, patcher.IMAGE_REL_I386_REL32)],
                    )

                contract = manifest["PetAchievementHooks"]
                self.assertEqual(
                    contract["achievement_ids"],
                    ["0x8a", "0x8b", "0x8c", "0x8d", "0x8e", "0x8f"],
                )
                self.assertEqual(
                    contract["placement"]["award_condition"],
                    "native SpawnPet return >= 0",
                )
                source = Path(patcher.__file__).read_text(encoding="utf-8")
                self.assertIn("if (slot >= 0) VF2CheckPetAchievements(item);", source)
                self.assertIn("for (int slot = 0; slot < 30; ++slot)", source)
                self.assertIn("if (manager->PetExists(slot))", source)
                self.assertIn("manager->GetPet(slot).KindOfPet() + 0x23B", source)
        finally:
            patcher.PATCHED = old_patched

    def test_family_tree_appearance_rows_are_exact(self):
        rows = {
            achievement_id: (group, title, description)
            for achievement_id, group, title, description
            in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS
        }
        self.assertEqual(
            {achievement_id: rows[achievement_id] for achievement_id in range(0x90, 0x92)},
            {
                0x90: (
                    "family_tree",
                    "Return of the Rainbow",
                    "Have a female villager with head value 48 in the family tree.",
                ),
                0x91: (
                    "family_tree",
                    "Spiky!",
                    "Have a male villager with head value 48 in the family tree.",
                ),
            },
        )

    def test_lifetime_generation_counter_preserves_tree_rollover_and_draws_on_goals(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                for filename in (
                    "FamilyTree.obj",
                    "AdoptionScene.obj",
                    "Achievement.obj",
                    "AchievementsScene.obj",
                ):
                    shutil.copy2(patcher.SRC_OBJS / filename, temp_root / filename)
                patcher.PATCHED = temp_root
                manifest = {}
                patcher.patch_custom_achievements(manifest)
                patcher.patch_lifetime_generation_counter(manifest)

                native_name = (
                    "?StartNextGeneration@CFamilyTree@@"
                    "QAE_NAAVCVillager@@H@Z"
                )
                for filename in ("FamilyTree.obj", "AdoptionScene.obj"):
                    obj = CoffObject(temp_root / filename)
                    native_index = obj.symbol(native_name).index
                    helper_index = obj.symbol(
                        "@VF2StartNextGenerationAndCount@16"
                    ).index
                    native_calls = []
                    helper_calls = []
                    for section in obj.sections:
                        for index in range(section.nreloc):
                            vaddr, symbol_index, rtype = struct.unpack_from(
                                "<IIH",
                                obj.buf,
                                section.reloc_ptr + index * 10,
                            )
                            if rtype != patcher.IMAGE_REL_I386_REL32:
                                continue
                            if symbol_index == native_index:
                                native_calls.append((section.index, vaddr))
                            if symbol_index == helper_index:
                                helper_calls.append((section.index, vaddr))
                    self.assertEqual(native_calls, [])
                    self.assertEqual(len(helper_calls), 1)

                scene = CoffObject(temp_root / "AchievementsScene.obj")
                draw = scene.symbol("?DrawScene@CAchievementsScene@@MAEXXZ")
                section = scene.section(draw.section)
                raw = section.raw_ptr + draw.value
                self.assertEqual(scene.buf[raw + 0x105], 0xE9)
                cave = draw.value + 0x10A + struct.unpack_from(
                    "<i", scene.buf, raw + 0x106
                )[0]
                cave_raw = section.raw_ptr + cave
                self.assertEqual(
                    scene.buf[cave_raw : cave_raw + 13],
                    (
                        b"\x60\xE8\0\0\0\0\x61"
                        b"\x6A\x64\x51\x8B\x4D\xF8"
                    ),
                )
                draw_relocations = [
                    struct.unpack_from(
                        "<IIH",
                        scene.buf,
                        section.reloc_ptr + index * 10,
                    )
                    for index in range(section.nreloc)
                ]
                self.assertIn(
                    (
                        cave + 2,
                        scene.symbol(
                            "_VF2DrawLifetimeGenerationCounter"
                        ).index,
                        patcher.IMAGE_REL_I386_REL32,
                    ),
                    draw_relocations,
                )

                contract = manifest["LifetimeGenerationCounter"]
                self.assertEqual(contract["maximum"], 0xFFFFFF)
                self.assertIn("stock 30-record rollover", contract["increment"])
                self.assertEqual(
                    contract["reset_achievements"],
                    "preserves lifetime-generation bits",
                )
                source = Path(patcher.__file__).read_text(encoding="utf-8")
                self.assertIn(
                    "if (!started) {\n        return false;\n    }",
                    source,
                )
                self.assertIn(
                    "VF2PersistentCheatAndPurchaseMask() & 0xFFFFFF00u",
                    source,
                )
                self.assertIn(
                    "(VF2PersistentCheatAndPurchaseMask() & 0xFFu)",
                    source,
                )
                self.assertIn("digitCount < 8", source)
                self.assertIn('"Generation: "', source)
        finally:
            patcher.PATCHED = old_patched

    def test_family_tree_appearance_hooks_are_relocation_only_and_persistent(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                for filename in ("FamilyTree.obj", "theGameState.obj"):
                    shutil.copy2(patcher.SRC_OBJS / filename, temp_root / filename)

                before = {}
                for filename in ("FamilyTree.obj", "theGameState.obj"):
                    obj = CoffObject(temp_root / filename)
                    before[filename] = {
                        section.index: bytes(
                            obj.buf[
                                section.raw_ptr :
                                section.raw_ptr + section.raw_size
                            ]
                        )
                        for section in obj.sections
                    }

                manifest = {}
                patcher.patch_family_tree_appearance_achievement_callsites(
                    manifest
                )

                family = CoffObject(temp_root / "FamilyTree.obj")
                expected_calls = (
                    ("?AddOffspring@CFamilyTree@@QAE_NABVCVillager@@@Z", 0x7C),
                    ("?StartNextGeneration@CFamilyTree@@QAE_NAAVCVillager@@H@Z", 0xD1),
                    ("?UpdateCurrentFamilyRecord@CFamilyTree@@QAEXXZ", 0x17),
                    ("?UpdateCurrentFamilyRecord@CFamilyTree@@QAEXXZ", 0x25),
                    ("?UpdateCurrentFamilyRecord@CFamilyTree@@QAEXXZ", 0x38),
                    ("?UpdateParents@CFamilyTree@@QAE_NAAVCVillager@@0@Z", 0xDD),
                )
                for function_name, relative in expected_calls:
                    function = family.symbol(function_name)
                    section = family.section(function.section)
                    self.assertEqual(
                        bytes(
                            family.buf[
                                section.raw_ptr :
                                section.raw_ptr + section.raw_size
                            ]
                        ),
                        before["FamilyTree.obj"][section.index],
                    )
                    targets = []
                    for index in range(section.nreloc):
                        vaddr, symbol_index, rtype = struct.unpack_from(
                            "<IIH", family.buf, section.reloc_ptr + index * 10
                        )
                        if vaddr == function.value + relative:
                            targets.append((
                                family.symbol_by_index[symbol_index].name,
                                rtype,
                            ))
                    self.assertEqual(
                        targets,
                        [(
                            patcher.APPEARANCE_UPDATE_HELPER_SYMBOL,
                            patcher.IMAGE_REL_I386_REL32,
                        )],
                    )

                game_state = CoffObject(temp_root / "theGameState.obj")
                load = game_state.symbol("?Load@theGameState@@UAE_NH@Z")
                section = game_state.section(load.section)
                self.assertEqual(
                    bytes(
                        game_state.buf[
                            section.raw_ptr :
                            section.raw_ptr + section.raw_size
                        ]
                    ),
                    before["theGameState.obj"][section.index],
                )
                load_targets = []
                for index in range(section.nreloc):
                    vaddr, symbol_index, rtype = struct.unpack_from(
                        "<IIH", game_state.buf, section.reloc_ptr + index * 10
                    )
                    if vaddr == load.value + 0x170:
                        load_targets.append((
                            game_state.symbol_by_index[symbol_index].name,
                            rtype,
                        ))
                self.assertEqual(
                    load_targets,
                    [(
                        patcher.APPEARANCE_LOAD_HELPER_SYMBOL,
                        patcher.IMAGE_REL_I386_REL32,
                    )],
                )

                contract = manifest["FamilyTreeAppearanceAchievementHooks"]
                self.assertTrue(
                    contract["load_reconciliation"]["includes_dead_and_departed"]
                )
                self.assertEqual(
                    len(contract["update_observers"]["callsites"]),
                    6,
                )
                source = Path(patcher.__file__).read_text(encoding="utf-8")
                self.assertIn("if (data == 0 || data[0x1A] == 0) return;", source)
                self.assertIn("int gender = *(int *)(data + 0x1C);", source)
                self.assertIn("int head = *(int *)(data + 0x20);", source)
                self.assertIn("family + 0x1B8 + child * 0xD8", source)
                self.assertNotIn("0x1BB88", source.split(
                    "static void VF2CheckAppearanceAchievement", 1
                )[1].split("extern \"C\" void __fastcall VF2MoneyAdjustAndAward", 1)[0])
        finally:
            patcher.PATCHED = old_patched

    def test_maximum_resource_callsites_are_relocation_only_wrappers(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                for filename in ("Money.obj", "FoodStore.obj", "theGameState.obj"):
                    shutil.copy2(patcher.SRC_OBJS / filename, temp_root / filename)
                patcher.PATCHED = temp_root
                manifest = {}
                patcher.patch_maximum_resource_achievement_callsites(manifest)

                hooks = manifest["maximum_resource_achievement_hooks"]
                self.assertEqual(hooks["money_goal"]["achievement_id"], "0x83")
                self.assertEqual(hooks["food_goal"]["achievement_id"], "0x84")
                for native, callsites in hooks["callsites"].items():
                    self.assertTrue(callsites, native)
                    for callsite in callsites:
                        obj = CoffObject(temp_root / callsite["object"])
                        section = obj.section(callsite["section"])
                        relocation = next(
                            struct.unpack_from(
                                "<IIH",
                                obj.buf,
                                section.reloc_ptr + index * 10,
                            )
                            for index in range(section.nreloc)
                            if struct.unpack_from(
                                "<I",
                                obj.buf,
                                section.reloc_ptr + index * 10,
                            )[0] == int(callsite["offset"], 16)
                        )
                        self.assertEqual(
                            obj.symbol_by_index[relocation[1]].name,
                            callsite["wrapper"],
                        )
                        self.assertEqual(
                            relocation[2],
                            patcher.IMAGE_REL_I386_REL32,
                        )
        finally:
            patcher.PATCHED = old_patched

    def test_general_purchase_aliases_require_success_but_not_holiday_flag(self):
        for item_id, goal_id in patcher.CUSTOM_ACHIEVEMENT_GENERAL_PURCHASE_GOALS.items():
            for holiday_enabled in (False, True):
                with self.subTest(item=hex(item_id), holiday=holiday_enabled):
                    self.assertEqual(
                        patcher.custom_achievement_purchase_dispatch(
                            item_id, True, holiday_enabled, 0x2
                        ),
                        (goal_id, 0x2),
                    )
                    self.assertEqual(
                        patcher.custom_achievement_purchase_dispatch(
                            item_id, False, holiday_enabled, 0x2
                        ),
                        (None, 0x2),
                    )

    def test_furnishing_the_future_covers_every_active_vf3_furniture_item(self):
        active_vf3_ids = {
            item["item_id"]
            for item in (
                patcher.VF3_LIVING_ROOM_BATCH_02_ITEMS
                + patcher.VF3_TV_ITEMS
            )
        }
        mapped_vf3_ids = {
            item_id
            for item_id, goal_id
            in patcher.CUSTOM_ACHIEVEMENT_GENERAL_PURCHASE_GOALS.items()
            if goal_id == patcher.CUSTOM_ACHIEVEMENT_VF3_FURNITURE_ID
        }
        self.assertEqual(active_vf3_ids, mapped_vf3_ids)
        self.assertEqual(
            active_vf3_ids,
            set(range(0x2F6, 0x2FC)) | set(range(0x324, 0x327)),
        )

    def test_holiday_purchase_aliases_are_flag_gated_and_failed_safe(self):
        for item_id, goal_id in patcher.CUSTOM_ACHIEVEMENT_HOLIDAY_PURCHASE_GOALS.items():
            with self.subTest(item=hex(item_id)):
                self.assertEqual(
                    patcher.custom_achievement_purchase_dispatch(item_id, True, True),
                    (goal_id, 0),
                )
                self.assertEqual(
                    patcher.custom_achievement_purchase_dispatch(item_id, True, False),
                    (None, 0),
                )
                self.assertEqual(
                    patcher.custom_achievement_purchase_dispatch(item_id, False, True),
                    (None, 0),
                )
        for item_id in (0, 0x1AD, 0x2D3, 0x328, 0x7FFFFFFF):
            self.assertEqual(
                patcher.custom_achievement_purchase_dispatch(item_id, True, True, 0x2),
                (None, 0x2),
            )

    def test_taters_mask_is_persistent_order_independent_and_duplicate_safe(self):
        for first, second, first_mask in ((0x2CF, 0x2CC, 0x1), (0x2CC, 0x2CF, 0x2)):
            with self.subTest(order=(hex(first), hex(second))):
                goal, saved_mask = patcher.custom_achievement_purchase_dispatch(
                    first, True, True, 0
                )
                self.assertEqual((goal, saved_mask), (None, first_mask))
                self.assertEqual(
                    patcher.custom_achievement_purchase_dispatch(
                        first, True, True, saved_mask
                    ),
                    (None, first_mask),
                )
                self.assertEqual(
                    patcher.custom_achievement_purchase_dispatch(
                        second, True, True, saved_mask
                    ),
                    (0x74, 0x3),
                )
                self.assertEqual(
                    patcher.custom_achievement_purchase_dispatch(
                        second, True, True, 0x3
                    ),
                    (None, 0x3),
                )

        for item_id in patcher.CUSTOM_ACHIEVEMENT_TATERS_PURCHASE_BITS:
            self.assertEqual(
                patcher.custom_achievement_purchase_dispatch(item_id, True, False, 0),
                (None, 0),
            )
            self.assertEqual(
                patcher.custom_achievement_purchase_dispatch(item_id, False, True, 0x2),
                (None, 0x2),
            )
        # CAchievement::Reset clears record+4, so a reset mask starts fresh.
        self.assertEqual(
            patcher.custom_achievement_purchase_dispatch(0x2CF, True, True, 0),
            (None, 0x1),
        )
        self.assertEqual(
            patcher.custom_achievement_purchase_dispatch(
                0x2CC,
                True,
                True,
                patcher.FORCE_SUCCESSFUL_PREGNANCY_MASK | 0x1,
            ),
            (0x74, patcher.FORCE_SUCCESSFUL_PREGNANCY_MASK | 0x3),
        )

    def test_praise_and_scold_dispatch_require_exact_full_labels(self):
        for label, goal_id in patcher.CUSTOM_ACHIEVEMENT_PRAISE_LABEL_GOALS.items():
            self.assertEqual(patcher.custom_achievement_praise_label_dispatch(label), goal_id)
            for near_match in (label + "!", label + " extra", label[:-1], label.lower()):
                if near_match != label:
                    self.assertIsNone(
                        patcher.custom_achievement_praise_label_dispatch(near_match)
                    )
        for negative in (
            "Browsing web",
            "Watching videos",
            "Playing games",
            "Praising",
            "Petting",
            "Scolding pet",
            "Posting memes",
        ):
            self.assertIsNone(patcher.custom_achievement_praise_label_dispatch(negative))

        for label, goal_id in patcher.CUSTOM_ACHIEVEMENT_SCOLD_LABEL_GOALS.items():
            if label in patcher.CUSTOM_ACHIEVEMENT_CHILD_SCOLD_LABELS:
                self.assertEqual(
                    patcher.custom_achievement_scold_label_dispatch(label, 0x117),
                    goal_id,
                )
                self.assertIsNone(
                    patcher.custom_achievement_scold_label_dispatch(label)
                )
                self.assertIsNone(
                    patcher.custom_achievement_scold_label_dispatch(label, 0x118)
                )
            else:
                self.assertEqual(
                    patcher.custom_achievement_scold_label_dispatch(label),
                    goal_id,
                )
            for near_match in (
                label + "!",
                label + " extra",
                label[:-1],
                label.lower(),
            ):
                if near_match != label:
                    self.assertIsNone(
                        patcher.custom_achievement_scold_label_dispatch(
                            near_match,
                            0x117,
                        )
                    )
        for negative in (
            "Scolding",
            "Scolding pet!",
            "Scolding pets",
            "Praising pet",
            "Petting",
            "Posting on Clipstagram",
        ):
            self.assertIsNone(patcher.custom_achievement_scold_label_dispatch(negative))

    def test_props_requires_tight_ship_and_all_four_new_discipline_goals(self):
        complete = {0x30, 0xA1, 0xA2, 0xA3, 0xA4}
        self.assertTrue(patcher.custom_achievement_props_is_satisfied(complete))
        for missing in complete:
            with self.subTest(missing=hex(missing)):
                self.assertFalse(
                    patcher.custom_achievement_props_is_satisfied(complete - {missing})
                )
        self.assertTrue(
            patcher.custom_achievement_props_is_satisfied(complete | {0x2D, 0xA5})
        )


class B153LinkedRuntimeValidatorTests(unittest.TestCase):
    def test_mortality_trampoline_matcher_allows_only_link_fields_to_vary(self):
        linked = bytearray(b153_runtime.MORTALITY_TRAMPOLINE)
        for offset in b153_runtime.MORTALITY_WILDCARDS:
            linked[offset] = (offset * 17 + 3) & 0xFF
        haystack = b"prefix" + bytes(linked) + b"suffix"
        self.assertEqual(
            list(
                b153_runtime.masked_matches(
                    haystack,
                    b153_runtime.MORTALITY_TRAMPOLINE,
                    b153_runtime.MORTALITY_WILDCARDS,
                )
            ),
            [len(b"prefix")],
        )
        linked[30] ^= 1
        self.assertEqual(
            list(
                b153_runtime.masked_matches(
                    bytes(linked),
                    b153_runtime.MORTALITY_TRAMPOLINE,
                    b153_runtime.MORTALITY_WILDCARDS,
                )
            ),
            [],
        )

    def test_b153_matrix_builder_uses_b152_base_and_separate_outputs(self):
        source = (patcher.ROOT / "work" / "build_b153_matrix.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'VF2-Mobile-Furniture-With-Island-Events-B152-$variant', source
        )
        self.assertIn(
            'VF2-Mobile-Furniture-With-Island-Events-B153-$variant', source
        )
        self.assertIn("validate_b153_runtime_flags.py", source)
        self.assertIn("validate_b153_holiday_collection.py", source)
        self.assertNotIn(
            '$previous = Join-Path $outputs "VF2-Mobile-Furniture-With-Island-Events-B153-',
            source,
        )


class OlderPregnancyPatchTests(unittest.TestCase):
    def with_temp_villager_state(self, callback):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                patcher.PATCHED = Path(tmp)
                shutil.copy2(
                    patcher.SRC_OBJS / "VillagerState.obj",
                    patcher.PATCHED / "VillagerState.obj",
                )
                shutil.copy2(
                    patcher.SRC_OBJS / "VillagerPlans.obj",
                    patcher.PATCHED / "VillagerPlans.obj",
                )
                shutil.copy2(
                    patcher.SRC_OBJS / "Villager.obj",
                    patcher.PATCHED / "Villager.obj",
                )
                callback(Path(tmp))
        finally:
            patcher.PATCHED = old_patched

    def test_age_curve_boundaries_and_permanent_floor(self):
        expected = {
            50: 100,
            51: 90,
            59: 10,
            60: 9,
            61: 8,
            68: 1,
            69: 1,
            122: 1,
        }
        self.assertEqual(
            {age: patcher.older_pregnancy_cap_tenths(age) for age in expected},
            expected,
        )
        with self.assertRaisesRegex(ValueError, "ages 50"):
            patcher.older_pregnancy_cap_tenths(49)

    def test_effective_chance_uses_stock_math_then_older_parent_cap(self):
        self.assertEqual(
            patcher.older_pregnancy_effective_chance_tenths(100, 100, 50, 30),
            100,
        )
        self.assertEqual(
            patcher.older_pregnancy_effective_chance_tenths(100, 100, 30, 51),
            90,
        )
        self.assertEqual(
            patcher.older_pregnancy_effective_chance_tenths(100, 100, 50, 68),
            1,
        )
        self.assertEqual(
            patcher.older_pregnancy_effective_chance_tenths(0, 0, 122, 122),
            1,
        )
        with self.assertRaisesRegex(ValueError, "under-50"):
            patcher.older_pregnancy_effective_chance_tenths(100, 100, 49, 49)

    def test_dormant_hook_preserves_stock_continuation_and_exact_abi(self):
        def run(temp_root):
            manifest = {}
            patcher.patch_allow_older_pregnancies(manifest)

            stock = CoffObject(patcher.SRC_OBJS / "VillagerState.obj")
            patched = CoffObject(temp_root / "VillagerState.obj")
            name = "?ChanceOfPregnancy@CVillagerState@@QAE_NHHH@Z"
            stock_sym = stock.symbol(name)
            patched_sym = patched.symbol(name)
            stock_sec = stock.section(stock_sym.section)
            patched_sec = patched.section(patched_sym.section)
            stock_data = bytes(
                stock.buf[
                    stock_sec.raw_ptr + stock_sym.value :
                    stock_sec.raw_ptr + stock_sec.raw_size
                ]
            )
            patched_data = bytes(
                patched.buf[
                    patched_sec.raw_ptr + patched_sym.value :
                    patched_sec.raw_ptr + patched_sec.raw_size
                ]
            )

            self.assertEqual(patched_data[:1], b"\xE9")
            self.assertEqual(patched_data[5:8], b"\x90\x90\x90")
            self.assertEqual(patched_data[8:0xF7], stock_data[8:])
            cave = 0xF7
            self.assertEqual(patched_data[cave:cave + 2], b"\x80\x3D")
            self.assertEqual(patched_data[cave + 7:cave + 9], b"\x74\x2C")
            self.assertEqual(
                patched_data[cave + 9:cave + 17],
                b"\x81\x7C\x24\x04\xE8\x03\x00\x00",
            )
            self.assertEqual(
                patched_data[cave + 19:cave + 27],
                b"\x81\x7C\x24\x08\xE8\x03\x00\x00",
            )
            self.assertEqual(patched_data[cave + 50:cave + 53], b"\xC2\x0C\x00")
            self.assertEqual(patched_data[cave + 53:cave + 61], stock_data[:8])

            relocs = {
                (
                    vaddr,
                    patched.symbol_by_index[symbol_index].name,
                    rtype,
                )
                for vaddr, symbol_index, rtype in (
                    struct.unpack_from(
                        "<IIH",
                        patched.buf,
                        patched_sec.reloc_ptr + index * 10,
                    )
                    for index in range(patched_sec.nreloc)
                )
            }
            self.assertIn(
                (cave + 2, patcher.OLDER_PREGNANCY_FLAG_SYMBOL, 0x0006),
                relocs,
            )
            self.assertIn(
                (cave + 43, patcher.OLDER_PREGNANCY_HELPER_SYMBOL, 0x0014),
                relocs,
            )

            plans = CoffObject(temp_root / "VillagerPlans.obj")
            process_name = "?ProcessCurrentPlan@CVillagerPlans@@QAEXAAVCVillager@@@Z"
            process = plans.symbol(process_name)
            process_sec = plans.section(process.section)
            process_raw = process_sec.raw_ptr + process.value
            self.assertEqual(bytes(plans.buf[process_raw + 0xA45:process_raw + 0xA46]), b"\xE9")
            self.assertEqual(bytes(plans.buf[process_raw + 0xA4A:process_raw + 0xA50]), b"\x90" * 6)
            cooldown_cave = 0xDCA
            self.assertEqual(
                bytes(plans.buf[process_raw + cooldown_cave:process_raw + cooldown_cave + 14]),
                b"\xFF\xB3\x54\x6A\x00\x00\xFF\xB7\x54\x6A\x00\x00\x56\x50",
            )
            plans_relocs = {
                (vaddr, plans.symbol_by_index[symbol_index].name, rtype)
                for vaddr, symbol_index, rtype in (
                    struct.unpack_from(
                        "<IIH",
                        plans.buf,
                        process_sec.reloc_ptr + index * 10,
                    )
                    for index in range(process_sec.nreloc)
                )
            }
            self.assertIn(
                (
                    cooldown_cave + 15,
                    patcher.OLDER_PREGNANCY_COOLDOWN_HELPER_SYMBOL,
                    0x0014,
                ),
                plans_relocs,
            )

            contract = manifest["AllowOlderPregnancies"]
            self.assertFalse(contract["default"])
            self.assertEqual(contract["runtime_flag"]["source_section"], ".vf2preg")
            self.assertTrue(
                contract["tutorial"]["failed_roll_forced_success_disabled_for_late_age_path"]
            )
            self.assertEqual(contract["multiples"], "native pregnancy/birth logic remains unmodified")

        self.with_temp_villager_state(run)

    def test_force_successful_pregnancy_is_relocation_only_and_clears_after_birth(self):
        def run(temp_root):
            manifest = {}
            patcher.patch_allow_older_pregnancies(manifest)

            before = CoffObject(temp_root / "VillagerPlans.obj")
            process_name = "?ProcessCurrentPlan@CVillagerPlans@@QAEXAAVCVillager@@@Z"
            before_process = before.symbol(process_name)
            before_section = before.section(before_process.section)
            before_bytes = bytes(
                before.buf[
                    before_section.raw_ptr :
                    before_section.raw_ptr + before_section.raw_size
                ]
            )

            patcher.patch_force_successful_pregnancy_callsites(manifest)
            after = CoffObject(temp_root / "VillagerPlans.obj")
            process = after.symbol(process_name)
            section = after.section(process.section)
            after_bytes = bytes(
                after.buf[section.raw_ptr : section.raw_ptr + section.raw_size]
            )
            self.assertEqual(after_bytes, before_bytes)
            self.assertEqual(
                after_bytes[process.value + 0x955 : process.value + 0x95A],
                b"\xE8\0\0\0\0",
            )
            self.assertEqual(
                after_bytes[process.value + 0x979 : process.value + 0x97E],
                b"\xE8\0\0\0\0",
            )

            targets = {}
            for index in range(section.nreloc):
                vaddr, symbol_index, relocation_type = struct.unpack_from(
                    "<IIH", after.buf, section.reloc_ptr + index * 10
                )
                if vaddr in (process.value + 0x956, process.value + 0x97A):
                    targets[vaddr - process.value] = (
                        after.symbol_by_index[symbol_index].name,
                        relocation_type,
                    )
            self.assertEqual(
                targets,
                {
                    0x956: (
                        patcher.FORCE_PREGNANCY_CHANCE_HELPER_SYMBOL,
                        0x0014,
                    ),
                    0x97A: (
                        patcher.FORCE_PREGNANCY_BIRTH_HELPER_SYMBOL,
                        0x0014,
                    ),
                },
            )

            villager = CoffObject(temp_root / "Villager.obj")
            impregnate_name = "?Impregnate@CVillager@@QAE_NHPBDHH_N@Z"
            impregnate = villager.symbol(impregnate_name)
            impregnate_section = villager.section(impregnate.section)
            impregnate_bytes = bytes(
                villager.buf[
                    impregnate_section.raw_ptr :
                    impregnate_section.raw_ptr + impregnate_section.raw_size
                ]
            )
            self.assertEqual(
                impregnate_bytes[0xE3:0xE4],
                b"\xE9",
            )
            self.assertEqual(
                impregnate_bytes[0x14D:0x152],
                b"\xE8\0\0\0\0",
            )
            count_cave = 0x2D7
            self.assertEqual(
                impregnate_bytes[count_cave:count_cave + 10],
                b"\x53\x57\xE8\0\0\0\0\x83\xC4\x08",
            )
            villager_targets = {}
            for index in range(impregnate_section.nreloc):
                vaddr, symbol_index, relocation_type = struct.unpack_from(
                    "<IIH",
                    villager.buf,
                    impregnate_section.reloc_ptr + index * 10,
                )
                if vaddr in (count_cave + 3, count_cave + 11, 0x14E):
                    villager_targets[vaddr] = (
                        villager.symbol_by_index[symbol_index].name,
                        relocation_type,
                    )
            self.assertEqual(
                villager_targets,
                {
                    count_cave + 3: (
                        patcher.FORCED_BIRTH_COUNT_HELPER_SYMBOL,
                        0x0014,
                    ),
                    count_cave + 11: (
                        "?Get@theGameState@@SAPAV1@XZ",
                        0x0014,
                    ),
                    0x14E: (
                        patcher.FORCED_BABY_GENDER_HELPER_SYMBOL,
                        0x0014,
                    ),
                },
            )

            contract = manifest["ForceSuccessfulPregnancy"]
            self.assertEqual(contract["store_item_id"], "0x136")
            self.assertEqual(contract["persistent_record_id"], "0xa8")
            self.assertEqual(contract["persistent_mask"], "0x4")
            self.assertIn("native ProcessCurrentPlan", contract["eligibility"])
            self.assertIn("returns true", contract["clear_condition"])
            self.assertIn("remains armed", contract["failed_birth"])
            self.assertEqual(
                contract["gender_controls"]["mutually_exclusive_mask"],
                "0x18",
            )
            self.assertEqual(
                contract["multiplicity_controls"]["mutually_exclusive_mask"],
                "0xe0",
            )
            self.assertIn(
                "clamped",
                contract["multiplicity_controls"]["capacity_rule"],
            )

        self.with_temp_villager_state(run)

    def test_force_successful_pregnancy_helper_preserves_other_persistent_bits(self):
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        self.assertEqual(patcher.FORCE_SUCCESSFUL_PREGNANCY_MASK, 0x4)
        self.assertIn("return VF2PersistentCheatAndPurchaseMask();", source)
        self.assertIn("VF2PersistentCheatAndPurchaseMask() & 0x4", source)
        self.assertIn(
            "return state->ChanceOfPregnancy(motherAge, fatherAge, fatherFertility);",
            source,
        )
        self.assertIn("bool succeeded = villager->Impregnate(", source)
        self.assertIn("if (succeeded) {", source)
        self.assertIn("VF2PersistentCheatAndPurchaseMask() &= ~0xFCu;", source)
        self.assertIn("storedMask = (storedMask & ~0x3u) | newMask;", source)
        self.assertNotIn("VF2PersistentCheatAndPurchaseMask() = 0;", source)
        self.assertEqual(patcher.FORCED_BABY_GENDER_MASK, 0x18)
        self.assertEqual(patcher.FORCED_BIRTH_COUNT_MASK, 0xE0)
        self.assertEqual(patcher.PREGNANCY_ONE_SHOT_MASK, 0xFC)
        self.assertIn("if (requested > availableSlots)", source)
        self.assertIn("requested = availableSlots;", source)
        self.assertIn("mother + 0x6B1C", source)
        self.assertIn("if (mask & 0x8) gender = eGenderMale;", source)
        self.assertIn("if (mask & 0x10) gender = eGenderFemale;", source)

    def test_helper_uses_thousand_roll_and_never_checks_tutorial_on_failure(self):
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        helper = source.split(
            'extern "C" int __cdecl VF2RollOlderPregnancy(', 1
        )[1].split("static int VF2AchievementVisibleCountInternal", 1)[0]
        self.assertIn("ldwGameState::GetRandom(1000)", helper)
        self.assertIn("TutorialTip.Queue", helper)
        self.assertNotIn("WasDisplayed", helper)
        self.assertIn("if (chanceTenths < 1) chanceTenths = 1;", helper)

    def test_hook_is_installed_in_all_compile_time_layouts(self):
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        direct_calls = [
            node
            for node in main.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "patch_allow_older_pregnancies"
        ]
        self.assertEqual(len(direct_calls), 1)
        self.assertNotIn("VF2_ENABLE_ALLOW_OLDER_PREGNANCIES", source)

    def test_next_generation_age_gate_retargets_all_native_queries_only(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                object_names = ("FamilyTreeScene.obj", "theMainScene.obj")
                for object_name in object_names:
                    source_path = patcher.SRC_OBJS / object_name
                    shutil.copy2(source_path, temp_root / object_name)

                manifest = {}
                patcher.patch_next_generation_age_gate(manifest)

                found = []
                for object_name in object_names:
                    obj = CoffObject(temp_root / object_name)
                    for section in obj.sections:
                        for index in range(section.nreloc):
                            vaddr, symbol_index, relocation_type = (
                                struct.unpack_from(
                                    "<IIH",
                                    obj.buf,
                                    section.reloc_ptr + index * 10,
                                )
                            )
                            symbol = obj.symbol_by_index.get(symbol_index)
                            if (
                                symbol is not None
                                and symbol.name
                                == patcher.NEXT_GENERATION_AGE_HELPER_SYMBOL
                            ):
                                found.append(
                                    (
                                        object_name,
                                        section.index,
                                        vaddr,
                                        relocation_type,
                                    )
                                )
                                self.assertEqual(
                                    obj.buf[section.raw_ptr + vaddr - 1],
                                    0xE8,
                                )

                self.assertEqual(
                    [
                        (name, section, hex(vaddr), kind)
                        for name, section, vaddr, kind in found
                    ],
                    [
                        ("FamilyTreeScene.obj", 15, "0xb0", 0x0014),
                        ("FamilyTreeScene.obj", 51, "0x43", 0x0014),
                        ("theMainScene.obj", 76, "0x1d2", 0x0014),
                        ("theMainScene.obj", 100, "0x6f9", 0x0014),
                    ],
                )
                contract = manifest["NextGenerationOlderAgeGate"]
                self.assertEqual(
                    contract["offline_patcher_setting"],
                    "allow_older_pregnancies",
                )
                self.assertEqual(
                    contract["runtime_flag"]["source_section"],
                    ".vf2preg",
                )
                self.assertEqual(
                    contract["age_threshold"]["displayed_years"],
                    60,
                )
                self.assertEqual(
                    contract["age_threshold"]["controller"],
                    "oldest active living non-departed villager",
                )
                self.assertTrue(
                    contract["safety_gates"]["surviving_child_required"]
                )
                self.assertTrue(
                    contract["safety_gates"]["stock_make_room_rollover_retained"]
                )
        finally:
            patcher.PATCHED = old_patched

    def test_next_generation_helper_preserves_stock_and_uses_live_oldest_age(self):
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        helper = source.split(
            'extern "C" bool __fastcall '
            "VF2CanStartNextGenerationAtOlderAge(", 1
        )[1].split(
            'extern "C" int __cdecl VF2RollOlderVillagerMortality(', 1
        )[0]
        self.assertIn(
            "bool stockEligible = tree->CanStartNextGeneration(force);",
            helper,
        )
        self.assertIn(
            "stockEligible || gVF2AllowOlderPregnancies == 0",
            helper,
        )
        self.assertIn("tree->CountSurvivingChildren() <= 0", helper)
        self.assertIn("stock MakeRoomInTree rollover", helper)
        self.assertIn("for (int index = 0; index < 30; ++index)", helper)
        self.assertIn("data[0x1BB84] != 0", helper)
        self.assertIn("data[0x1BB88] != 0", helper)
        self.assertIn("health <= 0", helper)
        self.assertIn("*(int *)(data + 0x6A54)", helper)
        self.assertIn("oldestInternalAge >= 60 * 20", helper)


class VF3StyleChildAdoptionChooserPatchTests(unittest.TestCase):
    def test_adoption_service_detours_to_guarded_singleton_chooser(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                source = patcher.SRC_OBJS / "ScrollingStoreScene.obj"
                shutil.copy2(source, temp_root / source.name)
                original = CoffObject(source)
                original_function = original.symbol(
                    "?HandleUpgrade@CScrollingStoreScene@@AAEXXZ"
                )
                original_section = original.section(original_function.section)
                original_size = original_section.raw_size
                original_raw = (
                    original_section.raw_ptr + original_function.value
                )
                self.assertEqual(
                    bytes(original.buf[original_raw + 0x28:original_raw + 0x2A]),
                    bytes.fromhex("8B D9"),
                    "HandleUpgrade must retain CScrollingStoreScene this in EBX",
                )

                manifest = {}
                patcher.patch_vf3_style_child_adoption_chooser(manifest)
                obj = CoffObject(temp_root / source.name)
                function = obj.symbol(
                    "?HandleUpgrade@CScrollingStoreScene@@AAEXXZ"
                )
                section = obj.section(function.section)
                raw = section.raw_ptr + function.value + 0x57A
                self.assertEqual(obj.buf[raw], 0xE9)
                self.assertEqual(section.raw_size, original_size + 22)
                cave_raw = section.raw_ptr + original_size
                self.assertEqual(
                    bytes(obj.buf[cave_raw:cave_raw + 11]),
                    bytes.fromhex("53 E8 00 00 00 00 83 C4 04 84 C0"),
                )

                relocations = []
                for index in range(section.nreloc):
                    vaddr, symbol_index, rtype = struct.unpack_from(
                        "<IIH",
                        obj.buf,
                        section.reloc_ptr + index * 10,
                    )
                    if vaddr == original_size + 2:
                        relocations.append((
                            obj.symbol_by_index[symbol_index].name,
                            rtype,
                        ))
                self.assertEqual(
                    relocations,
                    [(
                        patcher.ADOPTION_CHOOSER_HELPER_SYMBOL,
                        patcher.IMAGE_REL_I386_REL32,
                    )],
                )
                contract = manifest["VF3StyleChildAdoptionChooser"]
                self.assertIn("GetRandom(7)+2", contract["choices"]["older_child"])
                self.assertIn(
                    "exactly one",
                    contract["singleton"],
                )
                self.assertIn(
                    "EmptyOffspringSlots()>0",
                    contract["capacity"],
                )
        finally:
            patcher.PATCHED = old_patched

    def test_helper_uses_native_initializer_tree_and_achievement_routes(self):
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        helper = source.split(
            'extern "C" bool __cdecl VF2AdoptRandomChildChoice', 1
        )[1].split(
            'extern "C" void __cdecl VF2ApplyForcedBirthCount', 1
        )[0]
        self.assertIn("FamilyTree.EmptyOffspringSlots() <= 0", helper)
        self.assertIn("ldwGameState::GetRandom(7) + 2", helper)
        self.assertIn("ldwGameState::GetRandom(2)", helper)
        self.assertIn("VillagerManager.SpawnSpecificPeep(age, gender, -1)", helper)
        self.assertIn("FamilyTree.AddOffspring(villager)", helper)
        self.assertIn("(EAchievement)0x0C", helper)
        self.assertIn("(EAchievement)0x0D", helper)


class MultipleMarriageCandidatesPatchTests(unittest.TestCase):
    def test_reject_rerolls_in_place_and_preserves_email_state_route(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                shutil.copy2(
                    patcher.SRC_OBJS / "DatingScene.obj",
                    temp_root / "DatingScene.obj",
                )
                manifest = {}
                patcher.patch_multiple_marriage_candidates(manifest)

                dating = CoffObject(temp_root / "DatingScene.obj")
                handle = dating.symbol(
                    "?HandleMessage@CDatingScene@@UAE_NHJ@Z"
                )
                section = dating.section(handle.section)
                raw = section.raw_ptr + handle.value + 0x85
                self.assertEqual(
                    bytes(dating.buf[raw:raw + 19]),
                    bytes.fromhex(
                        "8B CB 90 90 90 90 90 E8 00 00 00 00 "
                        "5F 5E 5B B0 01 EB 14"
                    ),
                )
                relocation = []
                for index in range(section.nreloc):
                    vaddr, symbol_index, rtype = struct.unpack_from(
                        "<IIH",
                        dating.buf,
                        section.reloc_ptr + index * 10,
                    )
                    if vaddr == handle.value + 0x8D:
                        relocation.append((
                            dating.symbol_by_index[symbol_index].name,
                            rtype,
                        ))
                self.assertEqual(
                    relocation,
                    [(
                        "?GeneratePeepCandidate@CDatingScene@@AAEXXZ",
                        patcher.IMAGE_REL_I386_REL32,
                    )],
                )
                contract = manifest["MultipleMarriageCandidates"]
                self.assertEqual(contract["scope"], "core executable")
                self.assertIn("not cleared", contract["email_state"])
                self.assertIn("byte-identical", contract["accept_path"])
        finally:
            patcher.PATCHED = old_patched

    def test_reroll_precedes_same_sex_candidate_hook_in_every_layout(self):
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        calls = [
            node.value.func.id
            for node in main.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in {
                "patch_multiple_marriage_candidates",
                "patch_same_sex_marriage",
            }
        ]
        self.assertEqual(
            calls,
            [
                "patch_multiple_marriage_candidates",
                "patch_same_sex_marriage",
            ],
        )


class SameSexMarriagePatchTests(unittest.TestCase):
    def test_dormant_hooks_cover_candidate_roles_drop_and_pregnancy(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                for filename in (
                    "DatingScene.obj",
                    "VillagerManager.obj",
                    "theMainScene.obj",
                ):
                    shutil.copy2(
                        patcher.SRC_OBJS / filename,
                        temp_root / filename,
                    )
                manifest = {}
                patcher.patch_same_sex_marriage(manifest)

                dating = CoffObject(temp_root / "DatingScene.obj")
                generate = dating.symbol(
                    "?GeneratePeepCandidate@CDatingScene@@AAEXXZ"
                )
                generate_sec = dating.section(generate.section)
                generate_raw = generate_sec.raw_ptr + generate.value + 0x7B
                self.assertEqual(
                    bytes(dating.buf[generate_raw:generate_raw + 3]),
                    b"\x8B\xD7\xE8",
                )

                manager = CoffObject(temp_root / "VillagerManager.obj")
                for function_name in (
                    "?GetMatriarch@CVillagerManager@@QAEPAVCVillager@@XZ",
                    "?GetPatriarch@CVillagerManager@@QAEPAVCVillager@@XZ",
                ):
                    function = manager.symbol(function_name)
                    section = manager.section(function.section)
                    raw = section.raw_ptr + function.value
                    self.assertEqual(manager.buf[raw], 0xE9)
                    self.assertEqual(section.raw_size, 0x58 + 27)

                main_obj = CoffObject(temp_root / "theMainScene.obj")
                drop = main_obj.symbol(
                    "?HandleDropOnVillager@theMainScene@@IAEXAAVCVillager@@@Z"
                )
                drop_sec = main_obj.section(drop.section)
                self.assertEqual(
                    main_obj.buf[drop_sec.raw_ptr + drop.value + 0x256],
                    0xE9,
                )
                try_func = main_obj.symbol(
                    "?TryToMakeBaby@theMainScene@@IAEXXZ"
                )
                try_sec = main_obj.section(try_func.section)
                matches = []
                for index in range(try_sec.nreloc):
                    vaddr, symbol_index, rtype = struct.unpack_from(
                        "<IIH",
                        main_obj.buf,
                        try_sec.reloc_ptr + index * 10,
                    )
                    if vaddr == try_func.value + 0x42:
                        matches.append((
                            main_obj.symbol_by_index[symbol_index].name,
                            rtype,
                        ))
                self.assertEqual(
                    matches,
                    [(
                        patcher.FORCE_PREGNANCY_CHANCE_HELPER_SYMBOL,
                        patcher.IMAGE_REL_I386_REL32,
                    )],
                )

                contract = manifest["SameSexMarriage"]
                self.assertFalse(contract["default"])
                self.assertEqual(
                    contract["runtime_flag"]["source_section"],
                    ".vf2same",
                )
                self.assertIn("0%", contract["pregnancy"])
        finally:
            patcher.PATCHED = old_patched

    def test_hook_is_installed_in_all_compile_time_layouts(self):
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        calls = [
            node for node in main.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "patch_same_sex_marriage"
        ]
        self.assertEqual(len(calls), 1)
        self.assertIn(
            "if (VF2IsSameSexMarriage())",
            source,
        )


class OlderMortalityPatchTests(unittest.TestCase):
    def test_curve_is_monotonic_full_game_calibration_with_rare_tail(self):
        expected = {
            54: 0,
            55: 0,
            56: 3643,
            60: 18084,
            65: 35842,
            70: 53278,
            75: 70399,
            80: 87211,
            90: 119927,
            100: 151470,
            110: 181883,
            111: 232334,
            122: 618845,
            130: 770935,
            317: 999998,
            318: 999999,
        }
        self.assertEqual(
            {
                age: patcher.older_mortality_hazard_millionths(age)
                for age in expected
            },
            expected,
        )
        self.assertEqual(
            len(patcher.OLDER_MORTALITY_HAZARDS_MILLIONTHS),
            263,
        )
        hazards = [
            patcher.older_mortality_hazard_millionths(age)
            for age in range(55, 501)
        ]
        self.assertEqual(hazards, sorted(hazards))
        self.assertLess(max(hazards), patcher.OLDER_MORTALITY_RANDOM_LIMIT)

        survival_122 = patcher.older_mortality_survival_probability_through_age(122)
        self.assertAlmostEqual(survival_122, 2.2723451388172135e-06)
        with_four_groups = (
            patcher.older_mortality_survival_probability_through_age(122, 4)
        )
        self.assertAlmostEqual(with_four_groups, 7.348730358966406e-05)
        self.assertGreater(with_four_groups, survival_122)

        for groups in range(5):
            death_rows = []
            median = None
            for age in range(55, 501):
                reach = patcher.older_mortality_survival_probability_through_age(
                    age - 1, groups
                )
                hazard = (
                    patcher.older_mortality_hazard_millionths(age - groups)
                    / patcher.OLDER_MORTALITY_RANDOM_LIMIT
                )
                death_rows.append((reach * hazard, age))
                if median is None and (
                    patcher.older_mortality_survival_probability_through_age(
                        age, groups
                    )
                    <= 0.5
                ):
                    median = age
            self.assertEqual(max(death_rows)[1], 72 + groups)
            self.assertEqual(median, 74 + groups)

    def test_dormant_hook_preserves_stock_mortality_path_and_exact_abi(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                shutil.copy2(
                    patcher.SRC_OBJS / "VillagerManager.obj",
                    temp_root / "VillagerManager.obj",
                )
                manifest = {}
                patcher.patch_older_villager_mortality(manifest)

                stock = CoffObject(patcher.SRC_OBJS / "VillagerManager.obj")
                patched = CoffObject(temp_root / "VillagerManager.obj")
                name = (
                    "?AllVillagersRealtimePhysiologyAndProductivityUpkeep@"
                    "CVillagerManager@@QAEXXZ"
                )
                stock_sec = stock.section(stock.symbol(name).section)
                patched_sec = patched.section(patched.symbol(name).section)
                stock_data = bytes(
                    stock.buf[stock_sec.raw_ptr : stock_sec.raw_ptr + stock_sec.raw_size]
                )
                patched_data = bytes(
                    patched.buf[
                        patched_sec.raw_ptr : patched_sec.raw_ptr + patched_sec.raw_size
                    ]
                )
                cave = 0x7E2
                self.assertEqual(patched_data[0x353], 0xE9)
                self.assertEqual(patched_data[0x358:0x35C], b"\x90" * 4)
                self.assertEqual(patched_data[0x35C:0x3C8], stock_data[0x35C:0x3C8])
                self.assertEqual(patched_data[cave:cave + 4], b"\x6A\x00\x8B\xCB")
                self.assertEqual(patched_data[cave + 16:cave + 18], b"\x74\x20")
                self.assertEqual(patched_data[cave + 30:cave + 34], b"\x85\xC0\x74\x0B")

                relocs = {
                    (vaddr, patched.symbol_by_index[symidx].name, rtype)
                    for vaddr, symidx, rtype in (
                        struct.unpack_from(
                            "<IIH", patched.buf, patched_sec.reloc_ptr + i * 10
                        )
                        for i in range(patched_sec.nreloc)
                    )
                }
                self.assertIn(
                    (
                        cave + 5,
                        patcher.LONGEVITY_FOOD_GROUPS_HELPER_SYMBOL,
                        0x0014,
                    ),
                    relocs,
                )
                self.assertIn(
                    (cave + 11, patcher.OLDER_MORTALITY_FLAG_SYMBOL, 0x0006),
                    relocs,
                )
                self.assertIn(
                    (
                        cave + 23,
                        patcher.OLDER_MORTALITY_HELPER_SYMBOL,
                        0x0014,
                    ),
                    relocs,
                )
                contract = manifest["OlderVillagerMortality"]
                self.assertFalse(contract["default"])
                self.assertEqual(contract["runtime_flag"]["source_section"], ".vf2mort")
                self.assertIsNone(contract["curve"]["hard_maximum"])
        finally:
            patcher.PATCHED = old_patched

    def test_longevity_load_reconciliation_is_relocation_only_and_filtered(self):
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                patcher.PATCHED = temp_root
                obj_path = temp_root / "VillagerManager.obj"
                shutil.copy2(patcher.SRC_OBJS / "VillagerManager.obj", obj_path)
                patcher.patch_older_villager_mortality({})

                before = CoffObject(obj_path)
                load_name = (
                    "?LoadState@CVillagerManager@@QAE?B_N"
                    "AAUSSaveState@CVillager@@@Z"
                )
                load = before.symbol(load_name)
                sec = before.section(load.section)
                before_bytes = bytes(
                    before.buf[sec.raw_ptr : sec.raw_ptr + sec.raw_size]
                )
                manifest = {}
                patcher.patch_longevity_achievement_load_reconciliation(manifest)

                after = CoffObject(obj_path)
                after_load = after.symbol(load_name)
                after_sec = after.section(after_load.section)
                self.assertEqual(
                    bytes(
                        after.buf[
                            after_sec.raw_ptr :
                            after_sec.raw_ptr + after_sec.raw_size
                        ]
                    ),
                    before_bytes,
                )
                matches = []
                for index in range(after_sec.nreloc):
                    vaddr, symbol_index, rtype = struct.unpack_from(
                        "<IIH", after.buf, after_sec.reloc_ptr + index * 10
                    )
                    if vaddr == after_load.value + 0x34:
                        matches.append(
                            (
                                after.symbol_by_index[symbol_index].name,
                                rtype,
                            )
                        )
                self.assertEqual(
                    matches,
                    [
                        (
                            patcher.LONGEVITY_LOAD_HELPER_SYMBOL,
                            patcher.IMAGE_REL_I386_REL32,
                        )
                    ],
                )
                self.assertEqual(
                    manifest["LongevityAchievementHooks"][
                        "internal_age_thresholds"
                    ],
                    [1400, 1600, 1800, 2000, 2441],
                )
                source = Path(patcher.__file__).read_text(encoding="utf-8")
                self.assertIn("data[0x1BB84] != 0", source)
                self.assertIn("data[0x1BB88] != 0", source)
                self.assertIn("*(int *)(data + 0x6B00)", source)
                self.assertIn("*(int *)(data + 0x6A54)", source)
        finally:
            patcher.PATCHED = old_patched

    def test_hook_is_installed_in_all_compile_time_layouts(self):
        source = Path(patcher.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        calls = [
            node for node in main.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "patch_older_villager_mortality"
        ]
        self.assertEqual(len(calls), 1)


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
                b"\x8D\x98"
                + struct.pack(
                    "<I",
                    patcher.holiday_ornament_collection_footer_string_ids()[0]
                    - 0x0F,
                ),
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
                [
                    hex(value)
                    for value in (
                        patcher.holiday_ornament_collection_footer_string_ids()
                    )
                ],
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
            old_ornaments = patcher.ENABLE_HOLIDAY_ORNAMENTS
            patcher.ENABLE_HOLIDAY_ORNAMENTS = True
            try:
                patcher.patch_custom_achievements(manifest)
            finally:
                patcher.ENABLE_HOLIDAY_ORNAMENTS = old_ornaments
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
                complete_data[:10],
                b"\x51\xE8\x00\x00\x00\x00\x83\xC4\x04\xC3",
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
            self.assertEqual(queue_data[0x19 : 0x1C], b"\x83\xF8\x5F")
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
                b"\xB9\x5F\x00\x00\x00",
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
            self.assertEqual(data[0xA7:0xAE], b"\x8B\xCF\xE8\x00\x00\x00\x00")
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
            self.assertIn(
                (
                    sym.value + 0xAA,
                    obj.symbol(patcher.ACHIEVER_COMPLETION_HELPER_SYMBOL).index,
                    patcher.IMAGE_REL_I386_REL32,
                ),
                relocs,
            )

        self.with_temp_patched_objs(["Achievement.obj", "AchievementsScene.obj"], run)

    def test_custom_achievement_layout_for_all_four_gate_combinations(self):
        old_patched = patcher.PATCHED
        old_ornaments = patcher.ENABLE_HOLIDAY_ORNAMENTS
        old_behavior = patcher.ENABLE_BEHAVIOR_PATCHES
        stock_scene = CoffObject(patcher.SRC_OBJS / "AchievementsScene.obj")
        stock_order_sym = stock_scene.symbol("?achievementOrder@@3QBHB")
        stock_order_sec = stock_scene.section(stock_order_sym.section)
        stock_order = list(struct.unpack_from(
            "<95I",
            stock_scene.buf,
            stock_order_sec.raw_ptr + stock_order_sym.value,
        ))
        try:
            for ornaments, behavior, count_off, count_on, master_target, goal_target in (
                (False, False, 121, 140, 5, 12),
                (True, False, 122, 141, 6, 13),
                (False, True, 147, 166, 5, 12),
                (True, True, 148, 167, 6, 13),
            ):
                with self.subTest(ornaments=ornaments, behavior=behavior):
                    with tempfile.TemporaryDirectory() as tmp:
                        temp_root = Path(tmp)
                        for filename in ("Achievement.obj", "AchievementsScene.obj"):
                            shutil.copy2(patcher.SRC_OBJS / filename, temp_root / filename)
                        patcher.PATCHED = temp_root
                        patcher.ENABLE_HOLIDAY_ORNAMENTS = ornaments
                        patcher.ENABLE_BEHAVIOR_PATCHES = behavior
                        manifest = {}
                        patcher.patch_custom_achievements(manifest)

                        achievement = CoffObject(temp_root / "Achievement.obj")
                        table = achievement.symbol("?achievementList@@3PAUsAchievementListEntry@@A")
                        table_sec = achievement.section(table.section)
                        self.assertEqual(
                            (table_sec.raw_size - table.value) // patcher.ACHIEVEMENT_ROW_SIZE,
                            0xA8,
                        )
                        for achievement_id, _group, _title, _description in patcher.custom_achievement_capacity_row_specs():
                            title_id, description_id = patcher.custom_achievement_string_ids(achievement_id)
                            row = struct.unpack_from(
                                "<7I",
                                achievement.buf,
                                table_sec.raw_ptr + table.value
                                + achievement_id * patcher.ACHIEVEMENT_ROW_SIZE,
                            )
                            self.assertEqual(
                                row,
                                (achievement_id, 1, 0x1ED, 0, title_id, description_id, 0),
                            )
                        self.assertEqual(
                            struct.unpack_from(
                                "<I",
                                achievement.buf,
                                table_sec.raw_ptr + table.value
                                + 0x4D * patcher.ACHIEVEMENT_ROW_SIZE + 4,
                            )[0],
                            master_target,
                        )
                        self.assertEqual(
                            struct.unpack_from(
                                "<I",
                                achievement.buf,
                                table_sec.raw_ptr + table.value
                                + 0x54 * patcher.ACHIEVEMENT_ROW_SIZE + 4,
                            )[0],
                            goal_target,
                        )

                        load = achievement.symbol("?LoadState@CAchievement@@QAE?B_NAAUSSaveState@1@@Z")
                        load_sec = achievement.section(load.section)
                        load_data = bytes(achievement.buf[load_sec.raw_ptr + load.value : load_sec.raw_ptr + load.value + 0x8B])
                        self.assertEqual(load_data[0x39:0x45], b"\x8D\x4E\x00\x8D\x83\xEC\x07\x00\x00\x80\x38\x00")
                        self.assertEqual(load_data[0x51:0x57], b"\x81\xF9\x7C\x00\x00\x00")
                        self.assertEqual(load_data[0x62:0x6D], b"\x8D\x83\xEC\x07\x00\x00\xB9\x7C\x00\x00\x00")

                        set_complete = achievement.symbol(
                            "?SetComplete@CAchievement@@QAEXW4EAchievement@@@Z"
                        )
                        set_complete_sec = achievement.section(
                            set_complete.section
                        )
                        achiever_hook = 0xA7 if ornaments else 0x95
                        set_complete_data = bytes(
                            achievement.buf[
                                set_complete_sec.raw_ptr + set_complete.value :
                                set_complete_sec.raw_ptr + set_complete_sec.raw_size
                            ]
                        )
                        self.assertEqual(
                            set_complete_data[
                                achiever_hook : achiever_hook + 7
                            ],
                            b"\x8B\xCF\xE8\x00\x00\x00\x00",
                        )
                        set_complete_relocs = [
                            struct.unpack_from(
                                "<IIH",
                                achievement.buf,
                                set_complete_sec.reloc_ptr + index * 10,
                            )
                            for index in range(set_complete_sec.nreloc)
                        ]
                        self.assertIn(
                            (
                                set_complete.value + achiever_hook + 3,
                                achievement.symbol(
                                    patcher.ACHIEVER_COMPLETION_HELPER_SYMBOL
                                ).index,
                                patcher.IMAGE_REL_I386_REL32,
                            ),
                            set_complete_relocs,
                        )

                        for function_name, expected_size, count_offset in (
                            ("?SaveState@CAchievement@@QAE?B_NAAUSSaveState@1@@Z", 0x30, 0x06),
                            ("?Reset@CAchievement@@QAEXXZ", 0x27, 0x09),
                        ):
                            state_sym = achievement.symbol(function_name)
                            state_sec = achievement.section(state_sym.section)
                            self.assertEqual(state_sym.value + expected_size, state_sec.raw_size)
                            state_raw = state_sec.raw_ptr + state_sym.value
                            self.assertEqual(
                                achievement.buf[state_raw + count_offset : state_raw + count_offset + 5],
                                b"\xBA\x25\x01\x00\x00",
                            )

                        draw = achievement.symbol("?DrawAchievement@CAchievement@@QAEXHHH_NM@Z")
                        draw_sec = achievement.section(draw.section)
                        draw_data = bytes(
                            achievement.buf[
                                draw_sec.raw_ptr + draw.value : draw_sec.raw_ptr
                                + draw_sec.raw_size
                            ]
                        )
                        self.assertEqual(draw_data[0xD8], 0xE9)
                        self.assertEqual(
                            0xD8 + 5 + struct.unpack_from("<i", draw_data, 0xD9)[0],
                            0x3EB,
                        )
                        self.assertEqual(
                            draw_data[0x3EB:0x3FE],
                            b"\x81\xFF\xA7\x00\x00\x00\x77\x08"
                            b"\x8D\x0C\x7F\x8A\x0C\x8E\xEB\x02\x32\xC9\xE9",
                        )
                        self.assertEqual(
                            0x3FD + 5 + struct.unpack_from("<i", draw_data, 0x3FE)[0],
                            0xE7,
                        )
                        self.assertEqual(draw_data[0x191], 0xE9)
                        self.assertEqual(
                            0x191 + 5 + struct.unpack_from("<i", draw_data, 0x192)[0],
                            0x402,
                        )
                        self.assertEqual(draw_data[0x196:0x19A], b"\x90" * 4)
                        self.assertEqual(
                            draw_data[0x402:0x40A],
                            b"\x81\xFF\xA7\x00\x00\x00\x0F\x87",
                        )
                        self.assertEqual(
                            0x40E + struct.unpack_from("<i", draw_data, 0x40A)[0],
                            0x3CD,
                        )
                        self.assertEqual(draw_data[0x40E], 0xE9)
                        self.assertEqual(
                            0x40E + 5 + struct.unpack_from("<i", draw_data, 0x40F)[0],
                            0x19A,
                        )
                        draw_relocs = [
                            struct.unpack_from(
                                "<IIH",
                                achievement.buf,
                                draw_sec.reloc_ptr + index * 10,
                            )
                            for index in range(draw_sec.nreloc)
                        ]
                        self.assertFalse(
                            any(
                                draw.value + 0x3EB <= relocation[0] < draw.value + 0x413
                                for relocation in draw_relocs
                            )
                        )
                        self.assertEqual(
                            manifest["CustomAchievements"]["draw_bounds"],
                            {
                                "last_visible_id": "0xa7",
                                "comparison": "unsigned imm32",
                                "short_guard": {
                                    "source": "0xd8",
                                    "cave": "0x3eb",
                                    "return": "0xe7",
                                },
                                "near_guard": {
                                    "source": "0x191",
                                    "cave": "0x402",
                                    "fallthrough": "0x19a",
                                    "above_target": "0x3cd",
                                },
                                "coff_relocations_added": 0,
                            },
                        )

                        queue = achievement.symbol("?QueueAchievementNotify@CAchievement@@AAEXW4EAchievement@@@Z")
                        queue_sec = achievement.section(queue.section)
                        self.assertEqual(
                            achievement.buf[queue_sec.raw_ptr + queue.value + 0x19 : queue_sec.raw_ptr + queue.value + 0x1C],
                            b"\x83\xF8\x5F",
                        )
                        pop = achievement.symbol("?PopAchievementNotify@CAchievement@@AAE?AW4EAchievement@@XZ")
                        pop_sec = achievement.section(pop.section)
                        self.assertEqual(pop.value + 0x2F, pop_sec.raw_size)
                        pop_data = bytes(achievement.buf[pop_sec.raw_ptr + pop.value : pop_sec.raw_ptr + pop.value + 0x2F])
                        self.assertEqual(pop_data[0x1B:0x22], b"\xB9\x5E\x00\x00\x00\xF3\xA5")
                        self.assertEqual(pop_data[0x22:0x2C], b"\xC7\x82\x34\x0F\x00\x00\xFF\xFF\xFF\xFF")
                        update = achievement.symbol("?Update@CAchievement@@QAEXXZ")
                        update_sec = achievement.section(update.section)
                        self.assertEqual(update.value + 0x1A1, update_sec.raw_size)
                        update_data = bytes(achievement.buf[update_sec.raw_ptr + update.value : update_sec.raw_ptr + update.value + 0x1A1])
                        self.assertEqual(update_data[0x45:0x4B], b"\x8B\x96\x38\x0F\x00\x00")
                        self.assertEqual(update_data[0x4B:0x51], b"\x8B\x8E\x3C\x0F\x00\x00")

                        scene = CoffObject(temp_root / "AchievementsScene.obj")
                        order_sym = scene.symbol("?achievementOrder@@3QBHB")
                        order_sec = scene.section(order_sym.section)
                        order = list(struct.unpack_from(
                            "<" + "I" * ((order_sec.raw_size - order_sym.value) // 4),
                            scene.buf,
                            order_sec.raw_ptr + order_sym.value,
                        ))
                        expected = stock_order[:]
                        if ornaments:
                            expected.insert(expected.index(0x5E) + 1, 0x5F)
                        expected.extend(range(0x60, 0x66))
                        if behavior:
                            expected.extend(range(0x66, 0x6D))
                            expected.extend(range(0x93, 0xA6))
                        expected.extend(range(0x80, 0x92))
                        expected.append(0xA6)
                        expected.extend(range(0x6D, 0x80))
                        expected.append(0x92)
                        self.assertEqual(order, expected)
                        self.assertEqual(order[-39:-21], list(range(0x80, 0x92)))
                        self.assertEqual(order[-21], 0xA6)
                        self.assertEqual(order[-20:-1], list(range(0x6D, 0x80)))
                        self.assertEqual(order[-1], 0x92)
                        order_contract = manifest["CustomAchievements"][
                            "ornamentologist_order"
                        ]
                        self.assertEqual(order_contract["bottlologist_id"], "0x5e")
                        self.assertEqual(
                            order_contract["ornamentologist_id"], "0x5f"
                        )
                        if ornaments:
                            bottlologist_index = order.index(0x5E)
                            self.assertEqual(
                                order[bottlologist_index + 1],
                                0x5F,
                            )
                            self.assertEqual(order.count(0x5F), 1)
                            self.assertEqual(
                                order_contract,
                                {
                                    "visible": True,
                                    "bottlologist_id": "0x5e",
                                    "ornamentologist_id": "0x5f",
                                    "bottlologist_index": bottlologist_index,
                                    "ornamentologist_index": (
                                        bottlologist_index + 1
                                    ),
                                    "adjacent": True,
                                },
                            )
                            for visible_count in manifest[
                                "CustomAchievements"
                            ]["visible_counts"].values():
                                visible_order = order[:visible_count]
                                visible_bottlologist = visible_order.index(0x5E)
                                self.assertEqual(
                                    visible_order[visible_bottlologist + 1],
                                    0x5F,
                                )
                        else:
                            self.assertNotIn(0x5F, order)
                            self.assertEqual(
                                order_contract["ornamentologist_index"],
                                None,
                            )
                            self.assertIsNone(order_contract["adjacent"])

                        draw_scene = scene.symbol("?DrawScene@CAchievementsScene@@MAEXXZ")
                        draw_scene_sec = scene.section(draw_scene.section)
                        draw_scene_raw = draw_scene_sec.raw_ptr + draw_scene.value
                        self.assertEqual(scene.buf[draw_scene_raw + 0xF5], 0xE9)
                        cave = draw_scene.value + 0xFA + struct.unpack_from(
                            "<i", scene.buf, draw_scene_raw + 0xF6
                        )[0]
                        cave_raw = draw_scene_sec.raw_ptr + cave
                        self.assertEqual(
                            scene.buf[cave_raw : cave_raw + 12],
                            b"\x51\x52\xE8\x00\x00\x00\x00\x5A\x59\x3B\xF0\xE9",
                        )
                        self.assertEqual(
                            cave + 16 + struct.unpack_from("<i", scene.buf, cave_raw + 12)[0],
                            draw_scene.value + 0xFB,
                        )
                        draw_relocs = [
                            struct.unpack_from(
                                "<IIH",
                                scene.buf,
                                draw_scene_sec.reloc_ptr + index * 10,
                            )
                            for index in range(draw_scene_sec.nreloc)
                        ]
                        self.assertIn(
                            (
                                cave + 3,
                                scene.symbol("_VF2AchievementOrderEnd").index,
                                patcher.IMAGE_REL_I386_REL32,
                            ),
                            draw_relocs,
                        )
                        self.assertEqual(
                            manifest["CustomAchievements"]["visible_counts"],
                            {
                                "holiday_furniture_flag_0": count_off,
                                "holiday_furniture_flag_1": count_on,
                            },
                        )
                        self.assertEqual(
                            manifest["CustomAchievements"]["runtime_flag"]["default"],
                            "00",
                        )
                        self.assertEqual(
                            manifest["CustomAchievements"]["meta_targets"],
                            {
                                "master_collector": master_target,
                                "goal_collector": goal_target,
                                "new_rows_increment_goal_collector": False,
                            },
                        )
        finally:
            patcher.PATCHED = old_patched
            patcher.ENABLE_HOLIDAY_ORNAMENTS = old_ornaments
            patcher.ENABLE_BEHAVIOR_PATCHES = old_behavior

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

    def test_upright_holiday_source_set_and_manifest_are_complete(self):
        asset_manifest = json.loads(
            (
                patcher.HOLIDAY_ORNAMENT_PREEXTRACTED_ART_DIR
                / ornament_assets.ASSET_MANIFEST_NAME
            ).read_text(encoding="utf-8")
        )
        source_records = {
            row["filename"]: row for row in asset_manifest["source_assets"]
        }
        self.assertEqual(
            source_records.keys(),
            ornament_assets.source_metadata().keys(),
        )
        self.assertEqual(len(source_records), 27)
        self.assertEqual(
            source_records[
                ornament_assets.BOTTLECAPS_BACKGROUND_SOURCE_NAME
            ]["role"],
            "collection_page_base",
        )
        for name, expected in ornament_assets.source_metadata().items():
            source = patcher.HOLIDAY_ORNAMENT_SUPPLIED_ART_DIR / name
            record = source_records[name]
            self.assertTrue(source.is_file(), name)
            self.assertEqual(record["role"], expected["role"], name)
            self.assertEqual(
                record["sha256"],
                hashlib.sha256(source.read_bytes()).hexdigest(),
                name,
            )
            self.assertEqual(
                record["dimensions"],
                ornament_assets.png_dimensions(source),
                name,
            )

    def test_upright_icons_are_canonical_bit_for_bit_without_transforms(self):
        for runtime_name, source_name, _placeholder_name in (
            patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES
        ):
            source = patcher.HOLIDAY_ORNAMENT_SUPPLIED_ART_DIR / source_name
            canonical = (
                patcher.HOLIDAY_ORNAMENT_PREEXTRACTED_ART_DIR / runtime_name
            )
            self.assertEqual(
                canonical.read_bytes(),
                source.read_bytes(),
                runtime_name,
            )

    def test_collection_background_uses_all_supplied_upright_page_layers(self):
        from PIL import Image, ImageChops

        base = (
            patcher.HOLIDAY_ORNAMENT_SUPPLIED_ART_DIR
            / patcher.HOLIDAY_ORNAMENT_PAGE_BASE_SOURCE
        )
        frame = (
            patcher.HOLIDAY_ORNAMENT_SUPPLIED_ART_DIR
            / patcher.HOLIDAY_ORNAMENT_FRAME_SOURCE
        )
        decoration = (
            patcher.HOLIDAY_ORNAMENT_SUPPLIED_ART_DIR
            / patcher.HOLIDAY_ORNAMENT_PAGE_DECORATION_SOURCE
        )
        with Image.open(base) as opened:
            expected = opened.convert("RGBA")
        with Image.open(frame) as opened:
            frame_image = opened.convert("RGBA")
        with Image.open(decoration) as opened:
            decoration_image = opened.convert("RGBA")
        expected.alpha_composite(
            frame_image,
            patcher.HOLIDAY_ORNAMENT_FRAME_POSITION,
        )
        expected.alpha_composite(
            decoration_image,
            patcher.HOLIDAY_ORNAMENT_CANDY_CANE_POSITION,
        )
        for index, (_runtime_name, _source_name, placeholder_name) in enumerate(
            patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES
        ):
            placeholder_source = (
                patcher.HOLIDAY_ORNAMENT_SUPPLIED_ART_DIR / placeholder_name
            )
            with Image.open(placeholder_source) as opened:
                placeholder = opened.convert("RGBA")
            expected.alpha_composite(
                placeholder,
                patcher.HOLIDAY_ORNAMENT_COLLECTION_SLOT_POSITIONS[index],
            )

        canonical = (
            patcher.HOLIDAY_ORNAMENT_PREEXTRACTED_ART_DIR
            / patcher.HOLIDAY_ORNAMENT_BACKGROUND_FILENAME
        )
        with Image.open(canonical) as opened:
            actual = opened.convert("RGBA")
        self.assertEqual(actual.size, patcher.HOLIDAY_ORNAMENT_PAGE_SIZE)
        self.assertEqual(actual.size, expected.size)
        self.assertIsNone(ImageChops.difference(actual, expected).getbbox())

    def test_canonical_holiday_assets_rebuild_byte_for_byte(self):
        canonical_names = [
            runtime_name
            for runtime_name, _source_name, _placeholder_name in (
                patcher.HOLIDAY_ORNAMENT_COLLECTION_FILES
            )
        ] + [
            patcher.HOLIDAY_ORNAMENT_BACKGROUND_FILENAME,
            ornament_assets.ASSET_MANIFEST_NAME,
        ]
        with tempfile.TemporaryDirectory() as tmp:
            temp_output = Path(tmp) / "collection"
            ornament_assets.rebuild_collection_assets(
                patcher.HOLIDAY_ORNAMENT_SUPPLIED_ART_DIR,
                temp_output,
            )
            for name in canonical_names:
                self.assertEqual(
                    (temp_output / name).read_bytes(),
                    (
                        patcher.HOLIDAY_ORNAMENT_PREEXTRACTED_ART_DIR / name
                    ).read_bytes(),
                    name,
                )

    def test_b152_diagnostics_require_full_page_dimensions(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            image_dir = build_dir / "Images"
            image_dir.mkdir()
            background = image_dir / patcher.HOLIDAY_ORNAMENT_BACKGROUND_FILENAME
            canonical = (
                patcher.HOLIDAY_ORNAMENT_PREEXTRACTED_ART_DIR
                / patcher.HOLIDAY_ORNAMENT_BACKGROUND_FILENAME
            )
            shutil.copyfile(canonical, background)
            manifest = {
                "holiday_ornament_collection_art": {
                    "background": {
                        "dimensions": [1024, 768],
                        "sha256": hashlib.sha256(background.read_bytes()).hexdigest(),
                    }
                }
            }
            result = b152_diagnostics.validate_b152_holiday_ornament_art(
                build_dir,
                manifest,
                True,
            )
            self.assertEqual(result["dimensions"], [1024, 768])
            self.assertIsNone(
                b152_diagnostics.validate_b152_holiday_ornament_art(
                    build_dir,
                    manifest,
                    False,
                )
            )

            Image.new("RGBA", (940, 732)).save(background)
            manifest["holiday_ornament_collection_art"]["background"] = {
                "dimensions": [940, 732],
                "sha256": hashlib.sha256(background.read_bytes()).hexdigest(),
            }
            with self.assertRaisesRegex(
                b152_diagnostics.ValidationError,
                r"expected \(1024, 768\)",
            ):
                b152_diagnostics.validate_b152_holiday_ornament_art(
                    build_dir,
                    manifest,
                    True,
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

            old_ornaments = patcher.ENABLE_HOLIDAY_ORNAMENTS
            patcher.ENABLE_HOLIDAY_ORNAMENTS = True
            try:
                patcher.patch_custom_achievements(manifest)
                patcher.patch_collectable_item_holiday_ornaments(manifest)
                patcher.patch_collectable_holiday_ornament_observers(manifest)
                patcher.patch_collection_scene_holiday_ornaments(manifest)
                patcher.patch_the_collector_holiday_ornaments(manifest)
                patcher.validate_holiday_ornament_native_contract(manifest)
            finally:
                patcher.ENABLE_HOLIDAY_ORNAMENTS = old_ornaments

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
                    "physical_row_count": 0xA8,
                    "visible_count_flag_0": 122,
                    "visible_count_flag_1": 141,
                    "notify_queue_bound": 0x5F,
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
