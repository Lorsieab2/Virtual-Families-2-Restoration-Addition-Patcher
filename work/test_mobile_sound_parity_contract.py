#!/usr/bin/env python3
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "vf2" / "mobile-sound-parity-contract.json"
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _hex_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"0[xX][0-9a-fA-F]+", value):
        raise AssertionError(f"expected a hexadecimal ID string, got {value!r}")
    return int(value, 16)


def _record_index(value):
    if isinstance(value, bool):
        raise AssertionError(f"expected a Sound.obj record index, got {value!r}")
    if isinstance(value, int):
        return value
    return _hex_id(value)


class MobileSoundParityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CONTRACT_PATH.is_file():
            raise AssertionError(f"missing {CONTRACT_PATH}")
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_all_sound_records_use_the_raw_mobile_id_directly(self):
        self.assertEqual(self.contract.get("schema_version"), 1)
        records = self.contract.get("sound_records")
        self.assertIsInstance(records, list)
        self.assertEqual(len(records), 67)
        self.assertEqual(
            self.contract.get("scope", {}).get("sound_record_count"), len(records)
        )
        permitted_status = self.contract.get("fail_closed_policy", {}).get(
            "permitted_parity_status"
        )
        self.assertIsInstance(permitted_status, str)
        self.assertTrue(permitted_status)

        seen_ids = set()
        for record in records:
            with self.subTest(raw_mobile_id=record.get("raw_mobile_id")):
                raw_id = _hex_id(record.get("raw_mobile_id"))
                self.assertNotIn(raw_id, seen_ids)
                seen_ids.add(raw_id)

                pc_record = record.get("pc_sound_obj")
                self.assertIsInstance(pc_record, dict)
                pc_record_index = _record_index(pc_record.get("record_index"))
                self.assertEqual(
                    pc_record_index,
                    raw_id,
                    "Sound.obj must be indexed by the raw mobile ID; N+1 mappings are invalid",
                )
                self.assertIsInstance(pc_record.get("enum_name"), str)
                self.assertTrue(pc_record["enum_name"].strip())
                self.assertIsInstance(pc_record.get("filename"), str)
                self.assertTrue(pc_record["filename"].strip())

                mobile_obb = record.get("mobile_obb")
                self.assertIsInstance(mobile_obb, dict)
                self.assertIs(mobile_obb.get("present"), True)
                self.assertIsInstance(mobile_obb.get("asset_name"), str)
                self.assertTrue(mobile_obb["asset_name"].lower().endswith(".ogg"))
                self.assertIsNotNone(
                    SHA256_RE.fullmatch(mobile_obb.get("sha256", ""))
                )

                parity_status = record.get("parity_status")
                self.assertEqual(parity_status, permitted_status)

    def test_birthday_oh_sound_preserves_native_gender_contract(self):
        behavior = self.contract.get("birthday_oh_sound_behavior")
        self.assertIsInstance(behavior, dict)
        self.assertEqual(behavior.get("native_address"), "0x001CE4C0")
        self.assertEqual(behavior.get("native_size"), "0x4C")
        self.assertEqual(behavior.get("age_cutoff"), "0x118")

        defined = behavior.get("defined_gender_values")
        self.assertEqual(defined["unknown"], {
            "raw_value": -1,
            "esound": "eSound_None",
            "status": "valid_sentinel",
        })
        self.assertEqual(defined["male"], {
            "raw_value": 0,
            "base": "0x40",
            "divisor": 13,
            "range": ["0x40", "0x4C"],
        })
        self.assertEqual(defined["female"], {
            "raw_value": 1,
            "base": "0x4D",
            "divisor": 9,
            "range": ["0x4D", "0x55"],
        })
        self.assertEqual(behavior.get("child_range"), {
            "age": "< 0x118",
            "base": "0x33",
            "divisor": 13,
            "range": ["0x33", "0x3F"],
        })

        other = behavior.get("other_raw_values")
        self.assertEqual(other.get("native_behavior"), "raw_passthrough")
        self.assertEqual(other.get("validation"), "unvalidated")
        self.assertEqual(other.get("status"), "unsupported_corrupt_input_unverified")
        self.assertEqual(other.get("correction"), "none_proven")
        self.assertNotIn("unsafe_fallbacks", self.contract)


if __name__ == "__main__":
    unittest.main()
