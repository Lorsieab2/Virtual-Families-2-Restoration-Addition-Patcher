#!/usr/bin/env python3
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "vf2" / "mobile-sound-route-toggle-contract.json"

EXPECTED = {
    "0x01": ("beaker.wav", "beaker.ogg", "1ea91278c036d016f301b366f1155f9893d2aef52c023a5152aa6cb716b0c591", "0321ff33949e635b1d560d8ab5e0c24b1cf91e24453a182a6479a88cfbfc0ddc", "0x145B1", "0x68", "0x004F70CC"),
    "0x35": ("Child3.wav", "Child3.ogg", "edb4a9ff3f24f077ba7695bb7b7d57fdfdb575f7aea73b3a791969560170b556", "d7eaeb8de15fd71c9b9795273abd309caa94f7f0773240ace6d082815d5d09d7", "0x148F1", "0x3A8", "0x004F770C"),
    "0x39": ("Child7.wav", "Child7.ogg", "92ef57977bb058439ca9c287fb19c338ee7dd55e538be0d2d692cddabb84c040", "31bcddbdf50bcf6ceff01db95eec0b24ad5a2842815a3794b8559feff9628bb7", "0x14931", "0x3E8", "0x004F777C"),
    "0x3A": ("Child8.wav", "Child8.ogg", "efb39f885b51a480537745e625f7e805970825858a1e53f0ba4f2cf1a01f6ff8", "c486c883eff6f612992612a9f233b27365d0425e3bcfb3371c2e8ec28c40f96a", "0x14941", "0x3F8", "0x004F7798"),
}

LITERAL_RAW_OFFSETS = {
    "0x01": "0xEE3B",
    "0x35": "0xF3CD",
    "0x39": "0xF431",
    "0x3A": "0xF44A",
}


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MobileSoundRouteToggleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_scope_fingerprints_and_claims_are_fail_closed(self):
        c = self.contract
        self.assertEqual(c["schema_version"], 1)
        self.assertEqual(c["provenance"]["source_head"], "1c627d57bd4f064410e8951f2e402bc8277c8fa6")
        self.assertEqual(c["inputs"]["sound_obj"]["sha256"], "11730b342977e3f120bf3627e762bebcf9f36976c5cfc34736c89e78523e3bc4")
        self.assertEqual(c["inputs"]["fmod"]["sha256"].lower(), "7c6f7495d0a981f646bc23fdb39c0e349c598f5d6f4ef0ee58311338ae760194")
        self.assertEqual(c["toggle"]["default_enabled"], False)
        self.assertEqual(c["toggle"]["route_count"], 4)
        self.assertFalse(c["claims"]["decoder_selection_verified"])
        self.assertFalse(c["claims"]["ogg_bytes_under_wav_filename_safe"])
        self.assertFalse(c["claims"]["decoded_audio_content_parity_verified"])
        self.assertFalse(c["claims"]["audible_parity_verified"])
        self.assertFalse(c["claims"]["runtime_player_qa_complete"])

    def test_exact_four_routes_and_local_pins(self):
        routes = self.contract["routes"]
        self.assertEqual([r["raw_id_hex"] for r in routes], list(EXPECTED))
        for route in routes:
            with self.subTest(raw_id=route["raw_id_hex"]):
                pc_name, mobile_name, pc_hash, mobile_hash, rec_off, reloc_off, literal_va = EXPECTED[route["raw_id_hex"]]
                literal_raw_off = LITERAL_RAW_OFFSETS[route["raw_id_hex"]]
                so = route["sound_obj"]
                pc = route["pc_wav"]
                mobile = route["mobile_ogg"]
                self.assertEqual(route["raw_id"], int(route["raw_id_hex"], 16))
                self.assertEqual(pc["path"], f"work/vanilla_runtime_payload/Sounds/{pc_name}")
                self.assertEqual(mobile["source_path"], f"work/vf2_apk_extract/obb/assets/{mobile_name}")
                self.assertEqual(mobile["destination_path"], f"Sounds/{mobile_name}")
                self.assertEqual(pc["sha256"], pc_hash)
                self.assertEqual(mobile["sha256"], mobile_hash)
                self.assertEqual(so["record_raw_file_offset_hex"], rec_off)
                self.assertEqual(so["filename_relocation_section_offset_hex"], reloc_off)
                self.assertEqual(so["filename_literal_raw_file_offset_hex"], literal_raw_off)
                self.assertEqual(so["linked_exe"]["filename_literal_va_hex"] if "linked_exe" in so else route["linked_exe"]["filename_literal_va_hex"], literal_va)
                self.assertEqual(so["preimage_literal"], pc_name)
                self.assertEqual(so["replacement_literal"], mobile_name)
                self.assertEqual(len(so["preimage_literal"]), len(so["replacement_literal"]))
                self.assertEqual(so["preimage_literal_ascii_hex"], pc_name.encode("ascii").hex())
                self.assertEqual(so["replacement_literal_ascii_hex"], mobile_name.encode("ascii").hex())
                self.assertEqual(so["preload_dynamic_flag"], 0)
                self.assertEqual(pc["signature"], "RIFF....WAVE")
                self.assertEqual(mobile["signature"], "OggS")
                pc_path = ROOT / pc["path"]
                mobile_path = ROOT / mobile["source_path"]
                sound_obj_bytes = (ROOT / self.contract["inputs"]["sound_obj"]["path"]).read_bytes()
                self.assertTrue(pc_path.is_file())
                self.assertTrue(mobile_path.is_file())
                self.assertEqual(sound_obj_bytes[int(literal_raw_off, 16):int(literal_raw_off, 16) + len(pc_name)], pc_name.encode("ascii"))
                self.assertEqual(pc_path.stat().st_size, pc["size"])
                self.assertEqual(mobile_path.stat().st_size, mobile["size"])
                self.assertEqual(_sha256(pc_path), pc_hash)
                self.assertEqual(_sha256(mobile_path), mobile_hash)
                self.assertTrue(pc_path.read_bytes().startswith(b"RIFF"))
                self.assertEqual(pc_path.read_bytes()[8:12], b"WAVE")
                self.assertTrue(mobile_path.read_bytes().startswith(b"OggS"))

    def test_atomic_staging_rollback_and_offline_packaging(self):
        c = self.contract
        toggle = c["toggle"]
        self.assertEqual(toggle["transaction"], "all_or_nothing_four_routes")
        self.assertEqual(toggle["strategy"], "length_preserving_sound_obj_filename_literal_patch_and_additive_ogg_packaging")
        self.assertEqual(toggle["forbidden_strategy"], "placing_oggs_bytes_under_wav_filenames")
        self.assertTrue(toggle["retain_original_pc_wav_files"])
        self.assertEqual(c["preflight"]["failure_action"], "abort_before_mutation_or_packaging_and_leave_toggle_disabled")
        self.assertFalse(c["staging_and_rollback"]["canonical_sound_obj_mutation_allowed"])
        self.assertTrue(c["staging_and_rollback"]["apply_to_staged_build_inputs_only"])
        self.assertTrue(c["offline_packaging"]["must_be_self_contained"])
        self.assertFalse(c["offline_packaging"]["partial_package_allowed"])
        self.assertEqual(c["offline_packaging"]["feature_default_enabled"], False)
        self.assertIn("discard_the_entire_staged_toggle_result", c["staging_and_rollback"]["rollback_on_any_failure"])


if __name__ == "__main__":
    unittest.main()
