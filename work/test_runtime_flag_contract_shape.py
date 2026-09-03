#!/usr/bin/env python3
"""A malformed runtime-flag contract must fail, not vanish.

The Same-Sex Marriage toggle moved out of a free-standing `.vf2same` PE
section into the native save payload, so its contract legitimately carries no
`source_section`. Recognising that by the ABSENCE of the key meant a contract
that merely *lost* the key -- a typo, a half-written edit -- looked exactly
like the new format, and the setting was silently dropped from the exported
bundle. A release could ship without a setting and nothing would say so.

The new shape has to identify itself now.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import export_offline_patch_bundle as exporter

PERSISTED = {
    "storage": "InventoryManager + 0x14C + 0x2A3 (same persisted-byte convention)",
    "size": 1,
    "default": "00",
    "enabled": "01",
    "persistence": "part of the native save payload (CInventoryManager)",
}


def _export(runtime_flag):
    return exporter.same_sex_marriage_post_asset_patches(
        [],
        output_exe_name="whatever.exe",
        build_manifest_data={
            "SameSexMarriage": {
                "runtime_hooks_installed": True,
                "runtime_flag": runtime_flag,
            }
        },
    )


class TestPersistedShapeIsRecognisedPositively(unittest.TestCase):
    def test_the_real_contract_is_accepted(self):
        self.assertTrue(exporter._is_persisted_byte_flag(PERSISTED))
        self.assertEqual(_export(PERSISTED), [],
                         "the persisted form has no SHA-patchable section")

    def test_a_sectioned_contract_is_not_mistaken_for_it(self):
        sectioned = dict(PERSISTED, source_section=".vf2same")
        del sectioned["storage"]
        self.assertFalse(exporter._is_persisted_byte_flag(sectioned))


class TestMalformedContractsFailClosed(unittest.TestCase):
    def test_a_misspelled_source_section_raises(self):
        # The exact regression: this used to be indistinguishable from the new
        # format, so the setting disappeared from the bundle without an error.
        with self.assertRaises(ValueError):
            _export({"sourcesection": ".vf2same", "size": 1})

    def test_a_half_written_contract_raises(self):
        with self.assertRaises(ValueError):
            _export({"storage": "somewhere"})

    def test_an_empty_contract_raises(self):
        with self.assertRaises(ValueError):
            _export({})

    def test_a_wrong_width_flag_is_not_accepted_as_persisted(self):
        # One byte is the whole convention. Anything else is not this format,
        # and guessing would be how a bad contract slips through again.
        self.assertFalse(exporter._is_persisted_byte_flag(dict(PERSISTED, size=4)))

    def test_non_string_fields_are_not_accepted(self):
        self.assertFalse(exporter._is_persisted_byte_flag(dict(PERSISTED, default=0)))
        self.assertFalse(exporter._is_persisted_byte_flag(dict(PERSISTED, storage=None)))


if __name__ == "__main__":
    unittest.main()
