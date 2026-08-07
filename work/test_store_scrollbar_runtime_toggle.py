#!/usr/bin/env python3
"""End-to-end Store Scroll Bar runtime-marker coverage.

The fixture intentionally models the post-asset boundary: a generated core
payload contains a writable, default-zero ``.vf2scrl`` section and the
exporter emits an exact-SHA 00 -> 01 variant.  The patcher is then exercised
through its public CLI so output-only reconfiguration (enable, repeat, and
disable) is authenticated rather than directly mutating bytes in the test.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "work" / "offline_vf2_patcher.py"
sys.path.insert(0, str(ROOT / "work"))
import export_offline_patch_bundle as exporter  # noqa: E402
import patch_mobile_furniture_pack as generator  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_pe_bytes(*, scroll_byte: int = 0, text_salt: int = 0) -> bytes:
    """Return a tiny valid PE32 image with one writable .vf2scrl byte.

    The raw pointer is deliberately stable at 0x400, while ``text_salt``
    lets the vanilla and generated payloads have distinct authenticated
    hashes without changing the section layout.
    """

    if not 0 <= scroll_byte <= 0xFF:
        raise ValueError("scroll_byte must fit one byte")
    data = bytearray(0x600)
    data[:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    pe = 0x80
    data[pe:pe + 4] = b"PE\0\0"
    coff = pe + 4
    data[coff:coff + 20] = (
        (0x14C).to_bytes(2, "little")       # x86
        + (2).to_bytes(2, "little")         # .text + .vf2scrl
        + (0x12345678).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (0xE0).to_bytes(2, "little")
        + (0x103).to_bytes(2, "little")
    )
    opt = coff + 20
    data[opt:opt + 2] = (0x10B).to_bytes(2, "little")
    data[opt + 16:opt + 20] = (0x1000).to_bytes(4, "little")
    data[opt + 28:opt + 32] = (0x400000).to_bytes(4, "little")
    data[opt + 32:opt + 36] = (0x1000).to_bytes(4, "little")
    data[opt + 36:opt + 40] = (0x200).to_bytes(4, "little")
    data[opt + 56:opt + 60] = (0x3000).to_bytes(4, "little")
    data[opt + 68:opt + 70] = (2).to_bytes(2, "little")
    section_table = opt + 0xE0

    # .text, raw 0x200..0x400.
    text = section_table
    data[text:text + 8] = b".text\0\0\0"
    data[text + 8:text + 16] = (
        (0x200).to_bytes(4, "little") + (0x1000).to_bytes(4, "little")
    )
    data[text + 16:text + 24] = (
        (0x200).to_bytes(4, "little") + (0x200).to_bytes(4, "little")
    )
    data[text + 36:text + 40] = (0x60000020).to_bytes(4, "little")
    data[0x200:0x400] = bytes(((index + text_salt) % 251 for index in range(0x200)))

    # One initialized writable marker section.  Virtual size is exactly one
    # byte; raw size is one file-alignment block, matching the exporter
    # contract's requirement that the first raw byte is the initialized flag.
    flag = section_table + 40
    data[flag:flag + 8] = b".vf2scrl"
    data[flag + 8:flag + 16] = (
        (1).to_bytes(4, "little") + (0x2000).to_bytes(4, "little")
    )
    data[flag + 16:flag + 24] = (
        (0x200).to_bytes(4, "little") + (0x400).to_bytes(4, "little")
    )
    data[flag + 36:flag + 40] = (0xC0000040).to_bytes(4, "little")
    data[0x400] = scroll_byte
    return bytes(data)


class StoreScrollbarRuntimeToggleTests(unittest.TestCase):
    def test_generator_contract_is_default_off_and_guards_before_scene_reads(self):
        source = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
        self.assertEqual(generator.STORE_SCROLLBAR_FLAG_SECTION, ".vf2scrl")
        self.assertEqual(generator.STORE_SCROLLBAR_FLAG_SYMBOL, "_gVF2StoreScrollbar")
        self.assertIn('#pragma section(".vf2scrl", read, write)', source)
        self.assertIn(
            'volatile unsigned char gVF2StoreScrollbar = 0;',
            source,
        )
        for signature in (
            'extern "C" void __cdecl VF2DrawStoreScrollbar(void *scene)',
            'extern "C" void __cdecl VF2HandleStoreScrollbarMouse(void *scene, int message, int x, int y)',
        ):
            start = source.index(signature)
            body = source[start:]
            self.assertLess(
                body.index("if (gVF2StoreScrollbar == 0)"),
                body.index("field_i(scene"),
            )
        self.assertIn('manifest["StoreScrollBar"]', source)

    def run_patcher(self, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(PATCHER), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != expect:
            self.fail(
                f"expected patcher exit {expect}, got {result.returncode}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def write_fixture(self, tmp_path: Path) -> tuple[Path, Path, Path, bytes, bytes]:
        game_dir = tmp_path / "game"
        payload_dir = tmp_path / "payload"
        game_dir.mkdir()
        payload_dir.mkdir()

        vanilla = synthetic_pe_bytes(text_salt=17)
        payload = synthetic_pe_bytes(text_salt=83)
        game_exe = game_dir / "Virtual Families 2.exe"
        payload_exe = payload_dir / "Virtual Families 2 - Scroll Toggle.exe"
        game_exe.write_bytes(vanilla)
        payload_exe.write_bytes(payload)

        records = exporter.b152_runtime_flag_post_asset_patches(
            [payload_exe],
            output_exe_name=payload_exe.name,
            build_manifest_data={
                "StoreScrollBar": {
                    "runtime_flag": {
                        "symbol": "_gVF2StoreScrollbar",
                        "source_section": ".vf2scrl",
                        "size": 1,
                        "default": "00",
                    }
                }
            },
            allowed_source_sha256s={sha256_bytes(payload)},
        )
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["requires"], ["core_executable", "store_scroll_bar"])
        self.assertEqual(len(record["variants"]), 1)
        variant = record["variants"][0]
        self.assertEqual(variant["offset"], "0x400")
        self.assertEqual(variant["expected_asset_bytes"], "00")
        self.assertEqual(variant["replacement_bytes"], "01")
        self.assertEqual(variant["asset_sha256"], sha256_bytes(payload))
        self.assertEqual(variant["result_asset_sha256"], sha256_bytes(synthetic_pe_bytes(scroll_byte=1, text_salt=83)))

        manifest = {
            "manifest_version": 1,
            "name": "Store Scroll Bar runtime-marker test",
            "output": {
                "default_folder_name": "VF2-Scroll-Toggle-Test",
                "default_exe_name": payload_exe.name,
                "preserve_stock_exe_icon": False,
            },
            "settings": [
                {"id": "core_executable", "label": "Core", "default": True},
                {
                    "id": "store_scroll_bar",
                    "label": "Store Scroll Bar",
                    "description": "test",
                    "default": False,
                    "category": "optional",
                },
            ],
            "target_files": [
                {
                    "path": game_exe.name,
                    "sha256": sha256_bytes(vanilla),
                    "size": len(vanilla),
                }
            ],
            "asset_patches": [
                {
                    "file_path": game_exe.name,
                    "output_file_path": payload_exe.name,
                    "source_path": f"payload/{payload_exe.name}",
                    "source_sha256": sha256_bytes(payload),
                    "source_size": len(payload),
                    "expected_target_sha256": sha256_bytes(vanilla),
                    "expected_target_size": len(vanilla),
                    "overwrite_existing": True,
                    "requires": ["core_executable"],
                }
            ],
            "post_asset_patches": records,
            "runtime_requirements": {"required_files": [], "required_dirs": []},
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return game_dir, manifest_path, payload_exe, vanilla, payload

    def test_enable_repeated_enable_disable_restores_exact_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            game_dir, manifest, payload_exe, _vanilla, payload = self.write_fixture(tmp_path)
            output_dir = tmp_path / "VF2-Scroll-Toggle-Test"

            # Default-off apply copies the authenticated core payload without
            # activating the post-asset record.
            self.run_patcher(
                "apply", "--game-dir", str(game_dir), "--manifest", str(manifest)
            )
            self.assertEqual((output_dir / payload_exe.name).read_bytes(), payload)
            self.assertEqual((output_dir / payload_exe.name).read_bytes()[0x400], 0)

            # Enabling activates exactly one .vf2scrl byte.
            self.run_patcher(
                "apply",
                "--game-dir", str(game_dir),
                "--output-dir", str(output_dir),
                "--manifest", str(manifest),
                "--enable", "store_scroll_bar",
            )
            enabled = (output_dir / payload_exe.name).read_bytes()
            expected_enabled = synthetic_pe_bytes(scroll_byte=1, text_salt=83)
            self.assertEqual(enabled, expected_enabled)
            enabled_hash = sha256_bytes(enabled)

            # Output-only reconfiguration must be idempotent and keep the
            # exact enabled bytes (not apply 01 -> 01 blindly to an unknown
            # payload).
            self.run_patcher(
                "apply",
                "--output-dir", str(output_dir),
                "--manifest", str(manifest),
                "--enable", "store_scroll_bar",
            )
            self.assertEqual((output_dir / payload_exe.name).read_bytes(), enabled)
            self.assertEqual(sha256_bytes((output_dir / payload_exe.name).read_bytes()), enabled_hash)

            # Disabling reconfigures from the authenticated enabled result to
            # the exact source payload and removes the active post-asset byte.
            self.run_patcher(
                "apply",
                "--output-dir", str(output_dir),
                "--manifest", str(manifest),
                "--disable", "store_scroll_bar",
            )
            disabled = (output_dir / payload_exe.name).read_bytes()
            self.assertEqual(disabled, payload)
            self.assertEqual(disabled[0x400], 0)

    def test_wrong_expected_marker_byte_fails_closed_before_write(self):
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            game_dir, manifest, payload_exe, _vanilla, _payload = self.write_fixture(tmp_path)
            output_dir = tmp_path / "VF2-Scroll-Toggle-Test"

            # Keep the authenticated source hash but lie about the source
            # marker byte.  The post-asset validator must reject the route
            # before copying or mutating the output executable.
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_data["post_asset_patches"][0]["variants"][0]["expected_asset_bytes"] = "7F"
            manifest.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
            self.run_patcher(
                "apply",
                "--game-dir", str(game_dir),
                "--output-dir", str(output_dir),
                "--manifest", str(manifest),
                "--enable", "store_scroll_bar",
                expect=2,
            )
            self.assertFalse(output_dir.exists())

    def test_export_rejects_nonzero_default_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "bad-scroll.exe"
            source.write_bytes(synthetic_pe_bytes(scroll_byte=2))
            with self.assertRaisesRegex(ValueError, r"\.vf2scrl default byte mismatch"):
                exporter.b152_runtime_flag_post_asset_patches(
                    [source],
                    output_exe_name=source.name,
                    build_manifest_data={
                        "StoreScrollBar": {
                            "runtime_flag": {
                                "symbol": "_gVF2StoreScrollbar",
                                "source_section": ".vf2scrl",
                                "size": 1,
                                "default": "00",
                            }
                        }
                    },
                    allowed_source_sha256s={sha256_bytes(source.read_bytes())},
                )


if __name__ == "__main__":
    unittest.main()
