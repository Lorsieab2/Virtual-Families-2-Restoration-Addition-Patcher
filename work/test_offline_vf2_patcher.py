#!/usr/bin/env python3
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import offline_vf2_patcher as patcher_mod  # noqa: E402

PATCHER = ROOT / "work" / "offline_vf2_patcher.py"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def minimal_pe_bytes(overlay=b"", section_delta=0):
    data = bytearray(0x400)
    data[:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    pe = 0x80
    data[pe:pe + 4] = b"PE\0\0"
    coff = pe + 4
    data[coff:coff + 20] = (
        (0x14C).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
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
    data[opt + 56:opt + 60] = (0x2000).to_bytes(4, "little")
    data[opt + 68:opt + 70] = (2).to_bytes(2, "little")
    sect = opt + 0xE0
    data[sect:sect + 8] = b".text\0\0\0"
    data[sect + 8:sect + 16] = (0x200).to_bytes(4, "little") + (0x1000).to_bytes(4, "little")
    data[sect + 16:sect + 24] = (0x200).to_bytes(4, "little") + (0x200).to_bytes(4, "little")
    data[sect + 36:sect + 40] = (0x60000020).to_bytes(4, "little")
    data[0x200:0x400] = bytes(((index + section_delta) % 251 for index in range(0x200)))
    return bytes(data) + overlay


def resource_capable_pe_bytes():
    """Small valid PE32 fixture that Windows UpdateResource can extend."""
    data = bytearray(0x400)
    data[:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    pe = 0x80
    data[pe:pe + 4] = b"PE\0\0"
    coff = pe + 4
    struct.pack_into("<HHIIIHH", data, coff, 0x14C, 1, 0, 0, 0, 0xE0, 0x0102)
    opt = coff + 20
    struct.pack_into("<H", data, opt, 0x10B)
    struct.pack_into("<I", data, opt + 4, 0x200)
    struct.pack_into("<I", data, opt + 16, 0x1000)
    struct.pack_into("<I", data, opt + 20, 0x1000)
    struct.pack_into("<I", data, opt + 28, 0x400000)
    struct.pack_into("<I", data, opt + 32, 0x1000)
    struct.pack_into("<I", data, opt + 36, 0x200)
    struct.pack_into("<HH", data, opt + 40, 4, 0)
    struct.pack_into("<HH", data, opt + 48, 4, 0)
    struct.pack_into("<I", data, opt + 56, 0x2000)
    struct.pack_into("<I", data, opt + 60, 0x200)
    struct.pack_into("<H", data, opt + 68, 2)
    struct.pack_into("<IIIIII", data, opt + 72, 0x100000, 0x1000, 0x100000, 0x1000, 0, 16)
    section = opt + 0xE0
    data[section:section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 1, 0x1000, 0x200, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)
    data[0x200] = 0xC3
    return bytes(data)


def real_shell_icon_resources():
    width = height = 32
    pixels = b"\x20\x80\xE0\xFF" * (width * height)
    and_mask = b"\x00" * (((width + 31) // 32) * 4 * height)
    image = struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height * 2,
        1,
        32,
        0,
        len(pixels),
        0,
        0,
        0,
        0,
    ) + pixels + and_mask
    group = struct.pack("<HHHBBBBHHIH", 0, 1, 1, width, height, 0, 0, 1, 32, len(image), 101)
    return (
        patcher_mod.IconResource(patcher_mod.RT_ICON, 101, 1033, image),
        patcher_mod.IconResource(patcher_mod.RT_GROUP_ICON, 1, 1033, group),
    )


class OfflineVF2PatcherTests(unittest.TestCase):
    def test_manifest_output_parent_dir_selects_named_modded_folder(self):
        args = patcher_mod.argparse.Namespace(
            output_dir=None,
            output_parent_dir="C:\\VF2 Builds",
        )
        manifest = {"output": {"default_folder_name": "Virtual Families 2 - Modded"}}
        output = patcher_mod.resolve_apply_output_dir(args, Path("C:\\Games\\VF2"), manifest)
        self.assertEqual(output, Path("C:\\VF2 Builds\\Virtual Families 2 - Modded"))

    def run_patcher(self, *args, expect=0):
        result = subprocess.run(
            [sys.executable, str(PATCHER), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != expect:
            self.fail(
                f"Expected exit {expect}, got {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        return result

    def write_manifest(self, path, game_file, original, expected="03 04", replacement="AA BB"):
        manifest = {
            "manifest_version": 1,
            "name": "unit test manifest",
            "target_files": [
                {
                    "path": game_file.name,
                    "sha256": sha256_bytes(original),
                    "size": len(original),
                }
            ],
            "patches": [
                {
                    "file_path": game_file.name,
                    "offset": "0x2",
                    "expected_original_bytes": expected,
                    "replacement_bytes": replacement,
                    "note": "unit test byte swap",
                }
            ],
        }
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def post_asset_record(self, game_file, original, source_path, source_data, output_name, requires):
        return {
            "file_path": game_file.name,
            "output_file_path": output_name,
            "source_path": source_path,
            "source_sha256": sha256_bytes(source_data),
            "source_size": len(source_data),
            "expected_target_sha256": sha256_bytes(original),
            "expected_target_size": len(original),
            "overwrite_existing": True,
            "requires": requires,
        }

    def post_asset_manifest(
        self,
        game_file,
        original,
        output_name,
        asset_patches,
        variants,
        *,
        feature_default,
    ):
        return {
            "manifest_version": 1,
            "name": "post-asset patch unit test",
            "output": {
                "default_folder_name": "VF2-BPost-Modded",
                "default_exe_name": output_name,
            },
            "settings": [
                {
                    "id": "core_executable",
                    "label": "Core executable",
                    "default": True,
                },
                {
                    "id": "holiday_goal_visibility",
                    "label": "Holiday goal visibility",
                    "default": feature_default,
                    "category": "optional",
                },
            ],
            "target_files": [
                {
                    "path": game_file.name,
                    "sha256": sha256_bytes(original),
                    "size": len(original),
                }
            ],
            "asset_patches": asset_patches,
            "post_asset_patches": [
                {
                    "file_path": output_name,
                    "requires": ["holiday_goal_visibility"],
                    "note": "Toggle the selected executable's test flag.",
                    "variants": variants,
                }
            ],
        }

    def stock_icon_test_resources(self):
        return (
            patcher_mod.IconResource(
                resource_type=patcher_mod.RT_ICON,
                name=101,
                language=1033,
                data=b"stock icon image",
            ),
            patcher_mod.IconResource(
                resource_type=patcher_mod.RT_GROUP_ICON,
                name="MAINICON",
                language=1033,
                data=b"stock icon group",
            ),
        )

    def stock_icon_manifest_fixture(self, tmp_path, *, existing_modded=False):
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        game_file = game_dir / "Virtual Families 2.exe"
        original = b"vanilla executable"
        game_file.write_bytes(original)
        output_name = "Virtual Families 2 - Modded BPost.exe"
        payload_data = b"FLAG\x00DATA"
        payload = tmp_path / "payload" / output_name
        payload.parent.mkdir()
        payload.write_bytes(payload_data)
        manifest_data = self.post_asset_manifest(
            game_file,
            original,
            output_name,
            [
                self.post_asset_record(
                    game_file,
                    original,
                    f"payload/{output_name}",
                    payload_data,
                    output_name,
                    ["core_executable"],
                )
            ],
            [
                {
                    "asset_sha256": sha256_bytes(payload_data),
                    "offset": 4,
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                }
            ],
            feature_default=True,
        )
        manifest_data["output"]["preserve_stock_exe_icon"] = True
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        output_dir = tmp_path / "VF2-BPost-Modded"
        if existing_modded:
            (output_dir / ".vf2_patch_backups").mkdir(parents=True)
            (output_dir / output_name).write_bytes(b"existing icon-bearing modded executable")
        return game_dir, game_file, manifest, output_dir, output_name

    @unittest.skipUnless(sys.platform == "win32", "Windows resource APIs are required")
    def test_real_windows_icon_round_trip_is_shell_extractable(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "stock.exe"
            target = tmp_path / "modded.exe"
            source.write_bytes(resource_capable_pe_bytes())
            target.write_bytes(resource_capable_pe_bytes())
            expected = real_shell_icon_resources()

            patcher_mod._update_executable_icon_resources(source, expected)
            captured = patcher_mod.read_executable_icon_resources(source)
            self.assertEqual(captured, expected)
            self.assertEqual(patcher_mod.validate_executable_shell_icon(source), (16, 32, 48))

            patcher_mod.write_executable_icon_resources_atomic(target, captured)
            self.assertEqual(patcher_mod._enumerate_executable_icon_resources(target), expected)
            self.assertEqual(patcher_mod.validate_executable_shell_icon(target), (16, 32, 48))
            target_data = target.read_bytes()
            checksum_offset = patcher_mod.pe_checksum_offset(target_data)
            self.assertNotEqual(struct.unpack_from("<I", target_data, checksum_offset)[0], 0)
            self.assertEqual(
                struct.unpack_from("<I", target_data, checksum_offset)[0],
                patcher_mod.compute_pe_checksum(target_data),
            )

    def test_refresh_pe_checksum_is_nonzero_verified_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "fixture.exe"
            target.write_bytes(minimal_pe_bytes(overlay=b"odd"))
            checksum_offset = patcher_mod.pe_checksum_offset(target.read_bytes())
            self.assertEqual(struct.unpack_from("<I", target.read_bytes(), checksum_offset)[0], 0)

            first = patcher_mod.refresh_pe_checksum(target)
            first_bytes = target.read_bytes()
            second = patcher_mod.refresh_pe_checksum(target)

            self.assertNotEqual(first, 0)
            self.assertEqual(first, second)
            self.assertEqual(first_bytes, target.read_bytes())
            self.assertEqual(first, patcher_mod.compute_pe_checksum(target.read_bytes()))

    def test_refresh_pe_checksum_rejects_non_pe_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "not-an-exe.bin"
            target.write_bytes(b"not a PE file")
            with self.assertRaisesRegex(patcher_mod.PatchError, "valid DOS header"):
                patcher_mod.refresh_pe_checksum(target)

    def test_icon_group_rejects_missing_referenced_image(self):
        resources = list(real_shell_icon_resources())
        group = bytearray(resources[1].data)
        struct.pack_into("<H", group, 18, 999)
        resources[1] = patcher_mod.IconResource(
            patcher_mod.RT_GROUP_ICON,
            resources[1].name,
            resources[1].language,
            bytes(group),
        )
        with self.assertRaisesRegex(patcher_mod.PatchError, "missing RT_ICON ID 999"):
            patcher_mod._validate_group_icon_resources(tuple(resources))

    def test_icon_group_rejects_wrong_image_size(self):
        resources = list(real_shell_icon_resources())
        group = bytearray(resources[1].data)
        struct.pack_into("<I", group, 14, 123)
        resources[1] = patcher_mod.IconResource(
            patcher_mod.RT_GROUP_ICON,
            resources[1].name,
            resources[1].language,
            bytes(group),
        )
        with self.assertRaisesRegex(patcher_mod.PatchError, "declares 123 bytes"):
            patcher_mod._validate_group_icon_resources(tuple(resources))

    def test_preserves_stock_exe_icon_after_all_executable_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir, game_file, manifest, output_dir, output_name = self.stock_icon_manifest_fixture(tmp_path)
            resources = self.stock_icon_test_resources()
            args = patcher_mod.build_parser().parse_args(
                ["apply", "--game-dir", str(game_dir), "--manifest", str(manifest)]
            )
            args.progress_callback = lambda _message: None

            def write_icons(target, captured):
                self.assertEqual(target, output_dir / output_name)
                self.assertEqual(target.read_bytes(), b"FLAG\x00DATA")
                self.assertEqual(captured, resources)
                target.write_bytes(target.read_bytes() + b"|stock-icons")

            with mock.patch.object(
                patcher_mod,
                "read_executable_icon_resources",
                return_value=resources,
            ) as read_icons, mock.patch.object(
                patcher_mod,
                "write_executable_icon_resources_atomic",
                side_effect=write_icons,
            ) as write_icon_resources:
                patcher_mod.apply_manifest(args)

            read_icons.assert_called_once_with(game_file)
            write_icon_resources.assert_called_once()
            self.assertEqual((output_dir / output_name).read_bytes(), b"FLAG\x01DATA|stock-icons")
            self.assertEqual(game_file.read_bytes(), b"vanilla executable")

    def test_rebases_post_asset_offsets_after_icon_section_shift(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_dir = tmp_path / "manifest"
            output_dir = tmp_path / "output"
            source = manifest_dir / "payload" / "Modded.exe"
            target = output_dir / "Modded.exe"
            source.parent.mkdir(parents=True)
            output_dir.mkdir()
            source.write_bytes(b"linked payload")
            target.write_bytes(b"rewritten output")
            checks = [
                {
                    "index": 0,
                    "file_path": "Modded.exe",
                    "source_path": "payload/Modded.exe",
                    "offset": 0x108,
                    "expected": b"\x00",
                    "replacement": b"\x01",
                    "asset_sha256": patcher_mod.sha256_file(source),
                }
            ]
            source_structure = {
                "sections": [
                    {
                        "name": ".vf2same",
                        "raw_data_pointer": "0x100",
                        "raw_data_size": "0x200",
                    }
                ]
            }
            target_structure = {
                "sections": [
                    {
                        "name": ".vf2same",
                        "raw_data_pointer": "0x300",
                        "raw_data_size": "0x200",
                    }
                ]
            }
            with mock.patch.object(
                patcher_mod,
                "pe_structure_fingerprint",
                side_effect=[source_structure, target_structure],
            ):
                patcher_mod.rebase_post_asset_checks_to_output(
                    output_dir,
                    manifest_dir,
                    checks,
                )

            self.assertEqual(checks[0]["source_offset"], 0x108)
            self.assertEqual(checks[0]["offset"], 0x308)
            self.assertEqual(
                checks[0]["asset_sha256"],
                patcher_mod.sha256_file(target),
            )

    def test_stock_exe_icon_dry_run_validates_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir, game_file, manifest, output_dir, _output_name = self.stock_icon_manifest_fixture(tmp_path)
            resources = self.stock_icon_test_resources()
            args = patcher_mod.build_parser().parse_args(
                [
                    "apply",
                    "--game-dir",
                    str(game_dir),
                    "--manifest",
                    str(manifest),
                    "--dry-run",
                ]
            )
            args.progress_callback = lambda _message: None

            with mock.patch.object(
                patcher_mod,
                "read_executable_icon_resources",
                return_value=resources,
            ) as read_icons, mock.patch.object(
                patcher_mod,
                "write_executable_icon_resources_atomic",
            ) as write_icon_resources:
                patcher_mod.apply_manifest(args)

            read_icons.assert_called_once_with(game_file)
            write_icon_resources.assert_not_called()
            self.assertFalse(output_dir.exists())
            self.assertEqual(game_file.read_bytes(), b"vanilla executable")

    def test_missing_stock_exe_icon_fails_before_output_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir, game_file, manifest, output_dir, _output_name = self.stock_icon_manifest_fixture(tmp_path)
            args = patcher_mod.build_parser().parse_args(
                ["apply", "--game-dir", str(game_dir), "--manifest", str(manifest)]
            )
            args.progress_callback = lambda _message: None

            with mock.patch.object(
                patcher_mod,
                "read_executable_icon_resources",
                side_effect=patcher_mod.PatchError("stock icon resources missing"),
            ), mock.patch.object(patcher_mod, "prepare_output_dir") as prepare_output:
                with self.assertRaisesRegex(patcher_mod.PatchError, "stock icon resources missing"):
                    patcher_mod.apply_manifest(args)

            prepare_output.assert_not_called()
            self.assertFalse(output_dir.exists())
            self.assertEqual(game_file.read_bytes(), b"vanilla executable")

    def test_reconfigure_preserves_icon_from_existing_modded_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _game_dir, _game_file, manifest, output_dir, output_name = self.stock_icon_manifest_fixture(
                tmp_path,
                existing_modded=True,
            )
            existing_exe = output_dir / output_name
            resources = self.stock_icon_test_resources()
            args = patcher_mod.build_parser().parse_args(
                ["apply", "--output-dir", str(output_dir), "--manifest", str(manifest)]
            )
            args.progress_callback = lambda _message: None

            def read_icons(source):
                self.assertEqual(source, existing_exe)
                self.assertEqual(source.read_bytes(), b"existing icon-bearing modded executable")
                return resources

            def write_icons(target, captured):
                self.assertEqual(target, existing_exe)
                self.assertEqual(target.read_bytes(), b"FLAG\x00DATA")
                self.assertEqual(captured, resources)
                target.write_bytes(target.read_bytes() + b"|stock-icons")

            with mock.patch.object(
                patcher_mod,
                "read_executable_icon_resources",
                side_effect=read_icons,
            ) as read_icon_resources, mock.patch.object(
                patcher_mod,
                "write_executable_icon_resources_atomic",
                side_effect=write_icons,
            ) as write_icon_resources:
                patcher_mod.apply_manifest(args)

            read_icon_resources.assert_called_once()
            write_icon_resources.assert_called_once()
            self.assertEqual(existing_exe.read_bytes(), b"FLAG\x01DATA|stock-icons")

    def assert_post_asset_validation_failure(self, variants_factory, expected_error):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            game_file.write_bytes(original)
            output_name = "Virtual Families 2 - Modded BPost.exe"
            payload_data = b"FAIL\x00DATA"
            payload = tmp_path / "payload" / output_name
            payload.parent.mkdir()
            payload.write_bytes(payload_data)
            asset_patches = [
                self.post_asset_record(
                    game_file,
                    original,
                    f"payload/{output_name}",
                    payload_data,
                    output_name,
                    ["core_executable"],
                )
            ]
            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps(
                    self.post_asset_manifest(
                        game_file,
                        original,
                        output_name,
                        asset_patches,
                        variants_factory(sha256_bytes(payload_data)),
                        feature_default=True,
                    ),
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn(expected_error, result.stderr)
            self.assertEqual(game_file.read_bytes(), original)
            self.assertFalse((tmp_path / "VF2-BPost-Modded").exists())

    def direct_post_asset_check(self, file_path, data, *, index=0, offset=4):
        return {
            "index": index,
            "variant_index": 0,
            "file_path": file_path,
            "asset_patch_index": 0,
            "source_path": "payload/modded.exe",
            "asset_sha256": sha256_bytes(data),
            "offset": offset,
            "expected": data[offset : offset + 1],
            "replacement": b"\x01",
            "requires": ["holiday_goal_visibility"],
            "note": "direct post-asset failure test",
        }

    def test_apply_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "patch.json"
            backup = tmp_path / "backup"
            self.write_manifest(manifest, game_file, original)

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertIn("Validating byte patch 1/1", result.stdout)
            self.assertIn("Applying byte patch 1/1", result.stdout)
            self.assertEqual(game_file.read_bytes(), bytes([1, 2, 0xAA, 0xBB, 5, 6]))
            self.assertTrue((backup / "vf2_patch_backup_manifest.json").is_file())
            self.assertTrue((backup / "patch_log.json").is_file())
            log = json.loads((backup / "patch_log.json").read_text(encoding="utf-8"))
            self.assertTrue(any(row["phase"] == "validate" and row["status"] == "success" for row in log["process_log"]))
            self.assertTrue(any(row["phase"] == "apply" and row["status"] == "success" for row in log["process_log"]))

            self.run_patcher("restore", "--backup-dir", str(backup))
            self.assertEqual(game_file.read_bytes(), original)
            self.assertTrue((backup / "restore_log.json").is_file())

    def test_restore_refuses_tampered_backup_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "patch.json"
            backup = tmp_path / "backup"
            self.write_manifest(manifest, game_file, original)

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            backup_manifest = json.loads((backup / "vf2_patch_backup_manifest.json").read_text(encoding="utf-8"))
            backup_file = backup / backup_manifest["files"][0]["backup_path"]
            backup_file.write_bytes(b"tampered backup bytes")

            result = self.run_patcher("restore", "--backup-dir", str(backup), expect=2)

            self.assertIn("Backup SHA-256 mismatch", result.stderr)
            self.assertEqual(game_file.read_bytes(), bytes([1, 2, 0xAA, 0xBB, 5, 6]))
            self.assertFalse((backup / "restore_log.json").exists())

    def test_manifest_output_folder_creates_modded_sibling_and_preserves_vanilla(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            patched = b"patched executable"
            game_file.write_bytes(original)
            payload = tmp_path / "payload" / "Virtual Families 2 - Modded BTest.exe"
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_replacement.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "separate output folder unit test",
                        "output": {
                            "default_folder_name": "VF2-BTest-Modded",
                            "default_exe_name": "Virtual Families 2 - Modded BTest.exe",
                        },
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "output_file_path": "Virtual Families 2 - Modded BTest.exe",
                                "source_path": "payload/Virtual Families 2 - Modded BTest.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(original),
                                "expected_target_size": len(original),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "create verified modded exe in separate folder",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher("apply", "--exe", str(game_file), "--manifest", str(manifest))

            output_dir = tmp_path / "VF2-BTest-Modded"
            self.assertEqual(game_file.read_bytes(), original)
            self.assertFalse((output_dir / game_file.name).exists())
            self.assertEqual((output_dir / "Virtual Families 2 - Modded BTest.exe").read_bytes(), patched)
            backups = list((output_dir / ".vf2_patch_backups").glob("*/vf2_patch_backup_manifest.json"))
            self.assertEqual(len(backups), 1)
            backup_manifest = json.loads(backups[0].read_text(encoding="utf-8"))
            self.assertEqual(Path(backup_manifest["game_dir"]), output_dir.resolve())
            self.assertEqual(Path(backup_manifest["source_game_dir"]), game_dir.resolve())
            log = json.loads((backups[0].parent / "patch_log.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(log["output_dir"]), output_dir.resolve())
            self.assertEqual(log["modded_exe_name"], "Virtual Families 2 - Modded BTest.exe")
            self.assertTrue(log["modded_save_dir"].endswith(str(Path("LDW") / "Virtual Families 2 - Modded BTest")))

    def test_separate_output_may_overwrite_unknown_loose_asset_without_touching_vanilla(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original_exe = b"vanilla executable"
            game_file.write_bytes(original_exe)
            vanilla_sound = game_dir / "Sounds" / "children_giggle3.ogg"
            vanilla_sound.parent.mkdir()
            unknown_sound = b"unknown but preserved vanilla sound variant"
            vanilla_sound.write_bytes(unknown_sound)

            payload = tmp_path / "payload" / "children_giggle3.ogg"
            payload.parent.mkdir()
            mobile_sound = b"known packaged mobile sound"
            payload.write_bytes(mobile_sound)
            manifest = tmp_path / "asset_replace.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "safe separate-output loose asset replacement",
                        "output": {"default_folder_name": "VF2-BTest-Modded"},
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original_exe),
                                "size": len(original_exe),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Sounds/children_giggle3.ogg",
                                "source_path": "payload/children_giggle3.ogg",
                                "source_sha256": sha256_bytes(mobile_sound),
                                "source_size": len(mobile_sound),
                                "expected_target_sha256": sha256_bytes(b"known stock sound"),
                                "expected_target_size": len(b"known stock sound"),
                                "overwrite_existing": True,
                                "note": "replace only in the separate output folder",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher("apply", "--exe", str(game_file), "--manifest", str(manifest))

            self.assertEqual(vanilla_sound.read_bytes(), unknown_sound)
            self.assertEqual(
                (tmp_path / "VF2-BTest-Modded" / "Sounds" / "children_giggle3.ogg").read_bytes(),
                mobile_sound,
            )

    def test_refresh_rewrites_exe_that_was_up_to_date_before_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            patched = b"patched executable"
            game_file.write_bytes(original)

            output_dir = tmp_path / "VF2-BTest-Modded"
            output_dir.mkdir()
            output_exe = output_dir / "Virtual Families 2 - Modded BTest.exe"
            output_exe.write_bytes(patched)

            payload = tmp_path / "payload" / output_exe.name
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_replacement.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "refresh up-to-date exe unit test",
                        "output": {
                            "default_folder_name": output_dir.name,
                            "default_exe_name": output_exe.name,
                        },
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "output_file_path": output_exe.name,
                                "source_path": "payload/Virtual Families 2 - Modded BTest.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(original),
                                "expected_target_size": len(original),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "rewrite modded exe after output-folder refresh",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--output-dir",
                str(output_dir),
                "--manifest",
                str(manifest),
            )

            self.assertIn("Applying asset patch", result.stdout)
            self.assertFalse((output_dir / game_file.name).exists())
            self.assertEqual(output_exe.read_bytes(), patched)
            backups = list((output_dir / ".vf2_patch_backups").glob("*/patch_log.json"))
            self.assertEqual(len(backups), 1)
            log = json.loads(backups[0].read_text(encoding="utf-8"))
            self.assertTrue(
                any(row.get("action") == "up_to_date_recheck_failed" for row in log["process_log"])
            )
            self.assertEqual(log["modded_exe_name"], output_exe.name)
            backup_manifest = json.loads(
                (backups[0].parent / "vf2_patch_backup_manifest.json").read_text(encoding="utf-8")
            )
            backup_row = next(row for row in backup_manifest["files"] if row["file_path"] == output_exe.name)
            self.assertTrue(backup_row["existed"])
            self.assertEqual((backups[0].parent / backup_row["backup_path"]).read_bytes(), patched)

    def test_post_asset_patch_selects_last_asset_sha_and_runs_after_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            game_file.write_bytes(original)
            output_name = "Virtual Families 2 - Modded BPost.exe"
            base_data = b"BASE\x00DATA"
            selected_data = b"SELECT\x00DATA"
            payload_dir = tmp_path / "payload"
            payload_dir.mkdir()
            (payload_dir / "base.exe").write_bytes(base_data)
            (payload_dir / "selected.exe").write_bytes(selected_data)
            asset_patches = [
                self.post_asset_record(
                    game_file,
                    original,
                    "payload/base.exe",
                    base_data,
                    output_name,
                    ["core_executable"],
                ),
                self.post_asset_record(
                    game_file,
                    original,
                    "payload/selected.exe",
                    selected_data,
                    output_name,
                    ["core_executable", "holiday_goal_visibility"],
                ),
            ]
            variants = [
                {
                    "asset_sha256": sha256_bytes(base_data),
                    "offset": "0x4",
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                },
                {
                    "asset_sha256": sha256_bytes(selected_data),
                    "offset": "0x6",
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                },
            ]
            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps(
                    self.post_asset_manifest(
                        game_file,
                        original,
                        output_name,
                        asset_patches,
                        variants,
                        feature_default=True,
                    ),
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
            )

            self.assertIn("Applying post-asset patch 1/1", result.stdout)
            output_dir = tmp_path / "VF2-BPost-Modded"
            output_exe = output_dir / output_name
            self.assertEqual(output_exe.read_bytes(), b"SELECT\x01DATA")
            log_path = next((output_dir / ".vf2_patch_backups").glob("*/patch_log.json"))
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(log["post_asset_patches"][0]["variant_index"], 1)
            self.assertEqual(log["post_asset_patches"][0]["asset_patch_index"], 1)
            apply_events = [
                row
                for row in log["process_log"]
                if row["phase"] == "apply" and row["status"] == "success"
            ]
            asset_positions = [
                index for index, row in enumerate(apply_events) if row["kind"] == "asset_patch"
            ]
            post_position = next(
                index for index, row in enumerate(apply_events) if row["kind"] == "post_asset_patch"
            )
            self.assertLess(max(asset_positions), post_position)

    def test_post_asset_patch_groups_mixed_case_windows_target_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            game_file.write_bytes(original)
            output_name = "Virtual Families 2 - Modded BPost.exe"
            mixed_case_name = "virtual families 2 - MODDED bpost.EXE"
            payload_data = b"CASE\x00\x00END"
            payload = tmp_path / "payload" / output_name
            payload.parent.mkdir()
            payload.write_bytes(payload_data)
            asset_patches = [
                self.post_asset_record(
                    game_file,
                    original,
                    f"payload/{output_name}",
                    payload_data,
                    output_name,
                    ["core_executable"],
                )
            ]
            manifest_data = self.post_asset_manifest(
                game_file,
                original,
                output_name,
                asset_patches,
                [
                    {
                        "asset_sha256": sha256_bytes(payload_data),
                        "offset": 4,
                        "expected_asset_bytes": "00",
                        "replacement_bytes": "01",
                    }
                ],
                feature_default=True,
            )
            manifest_data["post_asset_patches"].append(
                {
                    "file_path": mixed_case_name,
                    "requires": ["holiday_goal_visibility"],
                    "variants": [
                        {
                            "asset_sha256": sha256_bytes(payload_data),
                            "offset": 5,
                            "expected_asset_bytes": "00",
                            "replacement_bytes": "01",
                        }
                    ],
                }
            )
            manifest = tmp_path / "manifest.json"
            manifest.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
            )

            output_dir = tmp_path / "VF2-BPost-Modded"
            self.assertEqual((output_dir / output_name).read_bytes(), b"CASE\x01\x01END")
            log_path = next((output_dir / ".vf2_patch_backups").glob("*/patch_log.json"))
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(
                [row["file_path"] for row in log["post_asset_patches"]],
                [output_name, mixed_case_name],
            )
            self.assertEqual(
                len(
                    [
                        row
                        for row in log["process_log"]
                        if row["phase"] == "apply"
                        and row["kind"] == "post_asset_patch"
                        and row["status"] == "success"
                    ]
                ),
                2,
            )

    def test_post_asset_patch_dry_run_validates_selected_payload_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            game_file.write_bytes(original)
            output_name = "Virtual Families 2 - Modded BPost.exe"
            payload_data = b"DRY\x00RUN"
            payload = tmp_path / "payload" / output_name
            payload.parent.mkdir()
            payload.write_bytes(payload_data)
            asset_patches = [
                self.post_asset_record(
                    game_file,
                    original,
                    f"payload/{output_name}",
                    payload_data,
                    output_name,
                    ["core_executable"],
                )
            ]
            variants = [
                {
                    "asset_sha256": sha256_bytes(payload_data),
                    "offset": 3,
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                }
            ]
            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps(
                    self.post_asset_manifest(
                        game_file,
                        original,
                        output_name,
                        asset_patches,
                        variants,
                        feature_default=True,
                    ),
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--dry-run",
            )

            self.assertIn("Validating post-asset patch 1/1", result.stdout)
            self.assertEqual(game_file.read_bytes(), original)
            self.assertFalse((tmp_path / "VF2-BPost-Modded").exists())
            log = json.loads((tmp_path / "patch_dry_run_log.json").read_text(encoding="utf-8"))
            self.assertEqual(log["post_asset_patches"][0]["asset_sha256"], sha256_bytes(payload_data))
            self.assertTrue(
                any(row["phase"] == "validate" and row["kind"] == "post_asset_patch" for row in log["process_log"])
            )
            self.assertFalse(
                any(row["phase"] == "apply" and row["kind"] == "post_asset_patch" for row in log["process_log"])
            )

    def test_post_asset_patch_setting_gates_and_reconfigures_from_pristine_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            game_file.write_bytes(original)
            output_name = "Virtual Families 2 - Modded BPost.exe"
            payload_data = b"FLAG\x00END"
            patched_data = b"FLAG\x01END"
            payload = tmp_path / "payload" / output_name
            payload.parent.mkdir()
            payload.write_bytes(payload_data)
            asset_patches = [
                self.post_asset_record(
                    game_file,
                    original,
                    f"payload/{output_name}",
                    payload_data,
                    output_name,
                    ["core_executable"],
                )
            ]
            variants = [
                {
                    "asset_sha256": sha256_bytes(payload_data),
                    "offset": 4,
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                }
            ]
            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps(
                    self.post_asset_manifest(
                        game_file,
                        original,
                        output_name,
                        asset_patches,
                        variants,
                        feature_default=False,
                    ),
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
            )
            output_dir = tmp_path / "VF2-BPost-Modded"
            output_exe = output_dir / output_name
            self.assertEqual(output_exe.read_bytes(), payload_data)
            first_log = next((output_dir / ".vf2_patch_backups").glob("*/patch_log.json"))
            self.assertEqual(json.loads(first_log.read_text(encoding="utf-8"))["post_asset_patches"], [])

            self.run_patcher(
                "apply",
                "--output-dir",
                str(output_dir),
                "--manifest",
                str(manifest),
                "--enable",
                "holiday_goal_visibility",
            )
            self.assertEqual(output_exe.read_bytes(), patched_data)
            enabled_logs = []
            for log_path in (output_dir / ".vf2_patch_backups").glob("*/patch_log.json"):
                log = json.loads(log_path.read_text(encoding="utf-8"))
                if log["post_asset_patches"]:
                    enabled_logs.append((log_path, log))
            self.assertEqual(len(enabled_logs), 1)
            enabled_log_path, enabled_log = enabled_logs[0]
            self.assertEqual(enabled_log["mode"], "existing_modded_output")
            backup_manifest = json.loads(
                (enabled_log_path.parent / "vf2_patch_backup_manifest.json").read_text(encoding="utf-8")
            )
            backup_row = next(row for row in backup_manifest["files"] if row["file_path"] == output_name)
            self.assertTrue(backup_row["existed"])
            self.assertEqual((enabled_log_path.parent / backup_row["backup_path"]).read_bytes(), payload_data)

            self.run_patcher(
                "apply",
                "--output-dir",
                str(output_dir),
                "--manifest",
                str(manifest),
            )
            self.assertEqual(output_exe.read_bytes(), payload_data)
            latest_log_path = sorted((output_dir / ".vf2_patch_backups").glob("*/patch_log.json"))[-1]
            latest_log = json.loads(latest_log_path.read_text(encoding="utf-8"))
            self.assertEqual(latest_log["post_asset_patches"], [])

    def test_post_asset_patch_rejects_missing_selected_sha_variant(self):
        self.assert_post_asset_validation_failure(
            lambda _selected_sha: [
                {
                    "asset_sha256": sha256_bytes(b"different payload"),
                    "offset": 4,
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                }
            ],
            "has no variant for selected asset SHA-256",
        )

    def test_post_asset_patch_rejects_duplicate_selected_sha_variants(self):
        self.assert_post_asset_validation_failure(
            lambda selected_sha: [
                {
                    "asset_sha256": selected_sha,
                    "offset": 4,
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                },
                {
                    "asset_sha256": selected_sha,
                    "offset": 4,
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                },
            ],
            "duplicates asset_sha256",
        )

    def test_post_asset_patch_rejects_latent_duplicate_sha_variants(self):
        self.assert_post_asset_validation_failure(
            lambda selected_sha: [
                {
                    "asset_sha256": selected_sha,
                    "offset": 4,
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                },
                {
                    "asset_sha256": sha256_bytes(b"latent payload"),
                    "offset": 0,
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                },
                {
                    "asset_sha256": sha256_bytes(b"latent payload"),
                    "offset": 1,
                    "expected_asset_bytes": "00",
                    "replacement_bytes": "01",
                },
            ],
            "duplicates asset_sha256",
        )

    def test_post_asset_patch_rejects_selected_payload_byte_mismatch(self):
        self.assert_post_asset_validation_failure(
            lambda selected_sha: [
                {
                    "asset_sha256": selected_sha,
                    "offset": 4,
                    "expected_asset_bytes": "FF",
                    "replacement_bytes": "01",
                }
            ],
            "expected asset bytes do not match",
        )

    def test_post_asset_patch_source_read_failure_is_logged_patch_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_data = b"FLAG\x00END"
            source = tmp_path / "payload" / "modded.exe"
            source.parent.mkdir()
            source.write_bytes(source_data)
            patch = patcher_mod.PostAssetPatch(
                index=0,
                file_path="Modded.exe",
                variants=(
                    patcher_mod.PostAssetPatchVariant(
                        index=0,
                        asset_sha256=sha256_bytes(source_data),
                        offset=4,
                        expected=b"\x00",
                        replacement=b"\x01",
                        note="",
                    ),
                ),
                note="source read failure",
                requires=(),
            )
            asset_checks = [
                {
                    "index": 0,
                    "file_path": "Virtual Families 2.exe",
                    "output_file_path": "Modded.exe",
                    "source_path": "payload/modded.exe",
                    "source_sha256": sha256_bytes(source_data),
                }
            ]
            process_log = []
            progress = []
            args = mock.Mock(progress_callback=progress.append)

            with mock.patch.object(Path, "read_bytes", side_effect=OSError("read denied")):
                with self.assertRaisesRegex(patcher_mod.PatchError, "Could not read selected asset source"):
                    patcher_mod.verify_post_asset_patches(
                        tmp_path,
                        [patch],
                        asset_checks,
                        args,
                        process_log,
                    )

            self.assertEqual(len(process_log), 1)
            self.assertEqual(process_log[0]["kind"], "post_asset_patch")
            self.assertEqual(process_log[0]["status"], "error")
            self.assertIn("Could not read selected asset source", process_log[0]["error"])
            self.assertTrue(any("[error]" in message for message in progress))

    def test_post_asset_patch_target_read_failure_is_logged_patch_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            target_data = b"FLAG\x00END"
            target = output_dir / "Modded.exe"
            target.write_bytes(target_data)
            checks = [self.direct_post_asset_check(target.name, target_data)]
            process_log = []
            progress = []
            args = mock.Mock(progress_callback=progress.append)

            with mock.patch.object(Path, "read_bytes", side_effect=OSError("read denied")):
                with self.assertRaisesRegex(patcher_mod.PatchError, "Could not read post-asset patch target"):
                    patcher_mod.apply_post_asset_patches(output_dir, checks, args, process_log)

            self.assertEqual(len(process_log), 1)
            self.assertEqual(process_log[0]["status"], "error")
            self.assertIn("Could not read post-asset patch target", process_log[0]["error"])
            self.assertTrue(any("[error]" in message for message in progress))

    def test_post_asset_patch_missing_target_is_logged_for_every_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            target_data = b"FLAG\x00\x00END"
            checks = [
                self.direct_post_asset_check("Modded.exe", target_data, index=0, offset=4),
                self.direct_post_asset_check("modded.EXE", target_data, index=1, offset=5),
            ]
            process_log = []
            progress = []
            args = mock.Mock(progress_callback=progress.append)

            with self.assertRaisesRegex(patcher_mod.PatchError, "target does not exist after asset copy"):
                patcher_mod.apply_post_asset_patches(output_dir, checks, args, process_log)

            self.assertEqual(len(process_log), 2)
            self.assertEqual({row["status"] for row in process_log}, {"error"})
            self.assertEqual({row["file_path"] for row in process_log}, {"Modded.exe", "modded.EXE"})
            self.assertEqual(len([message for message in progress if "[error]" in message]), 2)

    def test_post_asset_patch_write_failure_reaches_outer_failure_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            game_file.write_bytes(original)
            output_name = "Virtual Families 2 - Modded BPost.exe"
            payload_data = b"FLAG\x00END"
            payload = tmp_path / "payload" / output_name
            payload.parent.mkdir()
            payload.write_bytes(payload_data)
            manifest_data = self.post_asset_manifest(
                game_file,
                original,
                output_name,
                [
                    self.post_asset_record(
                        game_file,
                        original,
                        f"payload/{output_name}",
                        payload_data,
                        output_name,
                        ["core_executable"],
                    )
                ],
                [
                    {
                        "asset_sha256": sha256_bytes(payload_data),
                        "offset": 4,
                        "expected_asset_bytes": "00",
                        "replacement_bytes": "01",
                    }
                ],
                feature_default=True,
            )
            manifest = tmp_path / "manifest.json"
            manifest.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
            failure_log_path = tmp_path / "failure.json"
            args = patcher_mod.build_parser().parse_args(
                [
                    "apply",
                    "--game-dir",
                    str(game_dir),
                    "--manifest",
                    str(manifest),
                    "--log",
                    str(failure_log_path),
                ]
            )
            args.progress_callback = lambda _message: None

            with mock.patch.object(patcher_mod, "atomic_write", side_effect=OSError("write denied")):
                with self.assertRaisesRegex(patcher_mod.PatchError, "Could not write post-asset patch target"):
                    patcher_mod.apply_manifest(args)

            self.assertTrue(failure_log_path.is_file())
            failure_log = json.loads(failure_log_path.read_text(encoding="utf-8"))
            self.assertEqual(failure_log["status"], "failure")
            self.assertIn("Could not write post-asset patch target", failure_log["error"])
            error_rows = [
                row
                for row in failure_log["process_log"]
                if row["phase"] == "apply"
                and row["kind"] == "post_asset_patch"
                and row["status"] == "error"
            ]
            self.assertEqual(len(error_rows), 1)
            self.assertIn("write denied", error_rows[0]["error"])

    def test_dry_run_refuses_renamed_exe_without_exact_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            reference = tmp_path / "reference.exe"
            reference.write_bytes(minimal_pe_bytes())
            renamed_exe = game_dir / "Renamed VF2 Website Build.exe"
            renamed_exe.write_bytes(minimal_pe_bytes(section_delta=17))
            manifest = tmp_path / "structure_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "renamed PE target unit test",
                        "output": {"default_folder_name": "VF2-BTest-Modded"},
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "pe_structures": [patcher_mod.pe_structure_fingerprint(reference)],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--dry-run",
                expect=2,
            )
            self.assertIn("sha256 is required", result.stderr)

    def test_exe_replacement_refuses_renamed_exe_without_exact_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            reference = tmp_path / "reference.exe"
            reference.write_bytes(minimal_pe_bytes())
            renamed_exe = game_dir / "Renamed VF2 Website Build.exe"
            renamed_exe.write_bytes(minimal_pe_bytes(section_delta=29))
            payload = tmp_path / "payload" / "Virtual Families 2 - Modded BTest.exe"
            payload.parent.mkdir()
            patched = b"patched executable payload"
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_replacement_structure_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "renamed PE replacement unit test",
                        "output": {
                            "default_folder_name": "VF2-BTest-Modded",
                            "default_exe_name": payload.name,
                        },
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "pe_structures": [patcher_mod.pe_structure_fingerprint(reference)],
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Virtual Families 2.exe",
                                "output_file_path": payload.name,
                                "source_path": str(payload.relative_to(tmp_path)).replace("\\", "/"),
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_pe_structures": [patcher_mod.pe_structure_fingerprint(reference)],
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn("expected_target_sha256", result.stderr)

    def test_asset_patch_allow_missing_target_creates_additive_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            game_exe = game_dir / "Virtual Families 2.exe"
            game_exe.write_bytes(minimal_pe_bytes(section_delta=12))
            payload = tmp_path / "payload" / "Assets" / "Balloons_birthday.png.fmap"
            payload.parent.mkdir(parents=True)
            payload_bytes = b"new additive fmap"
            payload.write_bytes(payload_bytes)
            manifest = tmp_path / "allow_missing_asset.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "sha256": sha256_bytes(game_exe.read_bytes()),
                                "pe_structures": [patcher_mod.pe_structure_fingerprint(game_exe)],
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Assets/Balloons_birthday.png.fmap",
                                "source_path": "payload/Assets/Balloons_birthday.png.fmap",
                                "source_sha256": sha256_bytes(payload_bytes),
                                "source_size": len(payload_bytes),
                                "expected_target_sha256": "0" * 64,
                                "expected_target_size": 123,
                                "allow_missing_target": True,
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher("apply", "--game-dir", str(game_dir), "--manifest", str(manifest))

            self.assertIn("Patched files successfully", result.stdout)
            self.assertEqual((game_dir / "Assets" / "Balloons_birthday.png.fmap").read_bytes(), payload_bytes)

    def test_byte_patch_output_folder_renames_modded_exe_for_save_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "Virtual Families 2"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "byte_patch_output.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "byte patch renamed output unit test",
                        "output": {
                            "default_folder_name": "VF2-BByte-Modded",
                            "default_exe_name": "Virtual Families 2 - Modded BByte.exe",
                        },
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "patches": [
                            {
                                "file_path": game_file.name,
                                "offset": "0x2",
                                "expected_original_bytes": "03 04",
                                "replacement_bytes": "AA BB",
                                "note": "unit test byte swap",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher("apply", "--exe", str(game_file), "--manifest", str(manifest))

            output_dir = tmp_path / "VF2-BByte-Modded"
            modded_exe = output_dir / "Virtual Families 2 - Modded BByte.exe"
            self.assertEqual(game_file.read_bytes(), original)
            self.assertFalse((output_dir / game_file.name).exists())
            self.assertEqual(modded_exe.read_bytes(), bytes([1, 2, 0xAA, 0xBB, 5, 6]))
            log_path = next((output_dir / ".vf2_patch_backups").glob("*/patch_log.json"))
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(log["modded_exe_name"], "Virtual Families 2 - Modded BByte.exe")
            self.assertTrue(log["modded_save_dir"].endswith(str(Path("LDW") / "Virtual Families 2 - Modded BByte")))
            self.assertEqual(log["patched_files"][0]["output_file_path"], "Virtual Families 2 - Modded BByte.exe")

    def test_apply_with_exe_path_replaces_verified_original_and_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            patched = b"patched executable"
            game_file.write_bytes(original)
            payload = tmp_path / "payload" / "Virtual Families 2.exe"
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_replacement.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "exe replacement unit test",
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "source_path": "payload/Virtual Families 2.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(original),
                                "expected_target_size": len(original),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "replace verified vanilla exe",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--exe",
                str(game_file),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertEqual(game_file.read_bytes(), patched)
            backup_manifest = json.loads((backup / "vf2_patch_backup_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(backup_manifest["files"][0]["file_path"], game_file.name)
            self.assertEqual(backup_manifest["files"][0]["sha256"], sha256_bytes(original))

            self.run_patcher("restore", "--backup-dir", str(backup))
            self.assertEqual(game_file.read_bytes(), original)

    def test_apply_with_exe_path_accepts_any_exe_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_file = tmp_path / "VF2.exe"
            game_file.write_bytes(b"vanilla")
            manifest = tmp_path / "patch.json"
            backup = tmp_path / "backup"
            self.write_manifest(manifest, game_file, b"vanilla", expected="6e", replacement="70")

            self.run_patcher(
                "apply",
                "--exe",
                str(game_file),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )

            self.assertEqual(game_file.read_bytes(), b"vapilla")

    def test_exe_replacement_refuses_matching_pe_structure_when_hash_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            expected_original = minimal_pe_bytes()
            actual_original = minimal_pe_bytes(b"overlay that changes whole-file hash")
            patched = b"patched executable"
            game_file.write_bytes(actual_original)
            structure_source = tmp_path / "expected.exe"
            structure_source.write_bytes(expected_original)
            payload = tmp_path / "payload" / "Virtual Families 2.exe"
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_structure_replacement.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "exe structure replacement unit test",
                        "settings": [{"id": "core_executable", "label": "Patch game executable", "default": True}],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(expected_original),
                                "size": len(expected_original),
                                "pe_structure": patcher_mod.pe_structure_fingerprint(structure_source),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "source_path": "payload/Virtual Families 2.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(expected_original),
                                "expected_target_pe_structure": patcher_mod.pe_structure_fingerprint(structure_source),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "replace structurally matched exe",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--exe",
                str(game_file),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
                expect=2,
            )

            self.assertIn("SHA-256 mismatch", result.stderr)
            self.assertEqual(game_file.read_bytes(), actual_original)
            self.assertFalse(backup.exists())

    def test_exe_replacement_refuses_matching_pe_layout_when_section_hash_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            expected_original = minimal_pe_bytes(section_delta=0)
            actual_original = minimal_pe_bytes(section_delta=7)
            patched = b"patched executable"
            game_file.write_bytes(actual_original)
            structure_source = tmp_path / "expected.exe"
            structure_source.write_bytes(expected_original)
            payload = tmp_path / "payload" / "Virtual Families 2.exe"
            payload.parent.mkdir()
            payload.write_bytes(patched)
            manifest = tmp_path / "exe_layout_replacement.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "exe layout replacement unit test",
                        "settings": [{"id": "core_executable", "label": "Patch game executable", "default": True}],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(expected_original),
                                "size": len(expected_original),
                                "pe_structure": patcher_mod.pe_structure_fingerprint(structure_source),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": game_file.name,
                                "source_path": "payload/Virtual Families 2.exe",
                                "source_sha256": sha256_bytes(patched),
                                "source_size": len(patched),
                                "expected_target_sha256": sha256_bytes(expected_original),
                                "expected_target_pe_structure": patcher_mod.pe_structure_fingerprint(structure_source),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                                "note": "replace layout-matched exe",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--exe",
                str(game_file),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
                expect=2,
            )

            self.assertIn("SHA-256 mismatch", result.stderr)
            self.assertEqual(game_file.read_bytes(), actual_original)
            self.assertFalse(backup.exists())

    def test_target_file_refuses_vf2_exe_by_structure_when_name_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "VF2WebsiteBuild.exe"
            original = minimal_pe_bytes(section_delta=3)
            game_file.write_bytes(original)
            structure_source = tmp_path / "expected.exe"
            structure_source.write_bytes(original)
            manifest = tmp_path / "structure_named_exe.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "structure named exe unit test",
                        "target_files": [
                            {
                                "path": "Virtual Families 2.exe",
                                "pe_structures": [patcher_mod.pe_structure_fingerprint(structure_source)],
                            }
                        ],
                        "patches": [
                            {
                                "file_path": game_file.name,
                                "offset": "0x0",
                                "expected_original_bytes": "4d5a",
                                "replacement_bytes": "4d5a",
                                "note": "dry-run identity patch",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--dry-run",
                expect=2,
            )

            self.assertIn("sha256 is required", result.stderr)

    def test_runtime_requirements_validate_game_payload_before_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            (game_dir / "Images").mkdir()
            (game_dir / "Images" / "loading.jpg").write_bytes(b"image")
            (game_dir / "Sounds").mkdir()
            (game_dir / "Sounds" / "sound00.wav").write_bytes(b"sound")
            (game_dir / "ldw.ini").write_text("ok", encoding="ascii")
            manifest = tmp_path / "runtime_patch.json"
            backup = tmp_path / "backup"
            self.write_manifest(manifest, game_file, original)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["runtime_requirements"] = {
                "required_files": ["ldw.ini", "Images/loading.jpg"],
                "required_dirs": [{"path": "Images", "min_files": 1}, {"path": "Sounds", "min_files": 1}],
            }
            manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            log = json.loads((backup / "patch_log.json").read_text(encoding="utf-8"))
            self.assertEqual(len(log["runtime_checks"]), 4)

    def test_runtime_requirements_refuse_partial_images_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "runtime_patch.json"
            self.write_manifest(manifest, game_file, original)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["runtime_requirements"] = {
                "required_files": ["Images/loading.jpg"],
            }
            manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn("No valid Virtual Families 2 Installation detected!", result.stderr)
            self.assertIn("required runtime file is missing: Images", result.stderr)
            self.assertIn("loading.jpg", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)

    def test_exact_install_validation_refuses_unexpected_top_level_entries_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            (game_dir / "Images").mkdir()
            (game_dir / "unexpected.tmp").write_text("not official", encoding="ascii")
            manifest = tmp_path / "runtime_patch.json"
            output_dir = tmp_path / "modded"
            log_path = tmp_path / "patch_log.json"
            self.write_manifest(manifest, game_file, original)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["runtime_requirements"] = {
                "exact_top_level_entries": ["Images", "Virtual Families 2.exe"],
                "invalid_install_message": "No valid Virtual Families 2 Installation detected! Are you sure you downloaded it from the official website?\n\nLinks:\nhttp://www.ldw.com/\nhttp://www.virtualfamilies.com/index.php",
            }
            manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--output-dir",
                str(output_dir),
                expect=2,
            )

            self.assertIn("No valid Virtual Families 2 Installation detected!", result.stderr)
            self.assertIn("unexpected top-level entries: unexpected.tmp", result.stderr)
            self.assertFalse(output_dir.exists())
            self.assertFalse((game_dir / "patch_error_log.json").exists())
            self.assertTrue((manifest.parent / "patch_error_log.json").is_file())

    def test_exact_install_validation_allows_vf2_exe_when_exact_entries_are_name_agnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            (game_dir / "Images").mkdir()
            manifest = tmp_path / "runtime_patch.json"
            output_dir = tmp_path / "modded"
            log_path = tmp_path / "patch_log.json"
            self.write_manifest(manifest, game_file, original)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["runtime_requirements"] = {
                "exact_top_level_entries": ["Images"],
                "invalid_install_message": "No valid Virtual Families 2 Installation detected! Are you sure you downloaded it from the official website?\n\nLinks:\nhttp://www.ldw.com/\nhttp://www.virtualfamilies.com/index.php",
            }
            manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--output-dir",
                str(output_dir),
                "--log",
                str(log_path),
            )

            self.assertIn("Patched files successfully", result.stdout)
            self.assertTrue((output_dir / "Virtual Families 2.exe").is_file())
            log = json.loads(log_path.read_text(encoding="utf-8"))
            exact_checks = [row for row in log["runtime_checks"] if row["kind"] == "exact_top_level_entries"]
            self.assertEqual(exact_checks[0]["ignored_exe_names"], ["Virtual Families 2.exe"])

    def test_asset_patch_creates_private_tv_strip_and_restore_removes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            source = tmp_path / "payload" / "Images" / "VF3LargeFlatScreenTVAnim.png"
            source.parent.mkdir(parents=True)
            source_data = b"scaled private vf3 tv strip"
            source.write_bytes(source_data)
            target = game_dir / "Images" / "VF3LargeFlatScreenTVAnim.png"
            manifest = tmp_path / "asset_patch.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "asset patch unit test",
                        "settings": [
                            {
                                "id": "mobile_furniture",
                                "label": "Add additional mobile-exclusive furniture",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/VF3LargeFlatScreenTVAnim.png",
                                "source_path": "payload/Images/VF3LargeFlatScreenTVAnim.png",
                                "source_sha256": sha256_bytes(source_data),
                                "source_size": len(source_data),
                                "requires": ["mobile_furniture"],
                                "note": "B64 private VF3 TV animation strip",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertIn("1 active asset patch record", result.stdout)
            self.assertEqual(target.read_bytes(), source_data)
            backup_manifest = json.loads((backup / "vf2_patch_backup_manifest.json").read_text(encoding="utf-8"))
            self.assertIn(
                {"file_path": str(Path("Images") / "VF3LargeFlatScreenTVAnim.png"), "existed": False},
                backup_manifest["files"],
            )

            self.run_patcher("restore", "--backup-dir", str(backup))
            self.assertFalse(target.exists())

    def test_vf3_tv_animation_setting_controls_all_private_strips(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            strip_names = [
                "VF3LargeFlatScreenTVAnim.png",
                "VF3LargeFlatScreenTVAnimEast.png",
                "VF3SmallFlatScreenTVAnim.png",
                "VF3SmallFlatScreenTVAnimEast.png",
                "FathersFavoriteTVAnim.png",
                "FathersFavoriteTVAnimEast.png",
            ]
            payload_dir = tmp_path / "payload" / "Images"
            payload_dir.mkdir(parents=True)
            asset_patches = []
            for index, name in enumerate(strip_names):
                source_data = f"scaled private strip {index}".encode("ascii")
                source = payload_dir / name
                source.write_bytes(source_data)
                asset_patches.append(
                    {
                        "file_path": str(Path("Images") / name),
                        "source_path": str(Path("payload") / "Images" / name),
                        "source_sha256": sha256_bytes(source_data),
                        "source_size": len(source_data),
                        "requires": ["vf3_tv_animation_graphics"],
                        "note": f"B65 private VF3 TV animation strip: {name}",
                    }
                )
            manifest = tmp_path / "vf3_tv_asset_patch.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "vf3 tv animation asset unit test",
                        "settings": [
                            {
                                "id": "vf3_tv_animation_graphics",
                                "label": "Fix VF3 TV animation graphics",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": asset_patches,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertIn("6 active asset patch record", result.stdout)
            for index, name in enumerate(strip_names):
                self.assertEqual((game_dir / "Images" / name).read_bytes(), f"scaled private strip {index}".encode("ascii"))

            self.run_patcher("restore", "--backup-dir", str(backup))
            for name in strip_names:
                self.assertFalse((game_dir / "Images" / name).exists())

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--disable",
                "vf3_tv_animation_graphics",
                expect=2,
            )
            self.assertIn("No active patches remain", result.stderr)

    def test_outfit_sprite_sheet_asset_patches_copy_into_game_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            sheet_names = [
                "female_bodies00.png",
                "female_actions00.png",
                "female_sit00.png",
                "male_bodies00.png",
                "male_actions00.png",
                "male_sit00.png",
            ]
            payload_dir = tmp_path / "payload" / "Images"
            payload_dir.mkdir(parents=True)
            asset_patches = []
            for index, name in enumerate(sheet_names):
                source_data = f"copied stock villager sheet {index}".encode("ascii")
                (payload_dir / name).write_bytes(source_data)
                asset_patches.append(
                    {
                        "file_path": str(Path("Images") / name),
                        "source_path": str(Path("payload") / "Images" / name),
                        "source_sha256": sha256_bytes(source_data),
                        "source_size": len(source_data),
                        "requires": ["outfit_store_expansion"],
                        "note": f"Copy stock villager sprite sheet into the game Images folder: {name}",
                    }
                )
            manifest = tmp_path / "outfit_sheets_asset_patch.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "outfit sheet asset unit test",
                        "settings": [
                            {
                                "id": "outfit_store_expansion",
                                "label": "Add expanded Outfit store",
                                "default": True,
                            }
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            }
                        ],
                        "asset_patches": asset_patches,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertIn("6 active asset patch record", result.stdout)
            for index, name in enumerate(sheet_names):
                expected = f"copied stock villager sheet {index}".encode("ascii")
                self.assertEqual((game_dir / "Images" / name).read_bytes(), expected)

            self.run_patcher("restore", "--backup-dir", str(backup))
            for name in sheet_names:
                self.assertFalse((game_dir / "Images" / name).exists())

    def test_asset_patch_replaces_expected_file_and_restore_recovers_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            source = tmp_path / "payload" / "Images" / "FathersFavoriteTVAnim.png"
            source.parent.mkdir(parents=True)
            source_data = b"new scaled father favorite strip"
            source.write_bytes(source_data)
            target = game_dir / "Images" / "FathersFavoriteTVAnim.png"
            target.parent.mkdir(parents=True)
            old_target_data = b"old misaligned strip"
            target.write_bytes(old_target_data)
            manifest = tmp_path / "asset_patch.json"
            backup = tmp_path / "backup"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "asset replace unit test",
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/FathersFavoriteTVAnim.png",
                                "source_path": "payload/Images/FathersFavoriteTVAnim.png",
                                "source_sha256": sha256_bytes(source_data),
                                "expected_target_sha256": sha256_bytes(old_target_data),
                                "note": "Replace an expected private strip with the scaled B64 strip.",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
            )
            self.assertEqual(target.read_bytes(), source_data)

            self.run_patcher("restore", "--backup-dir", str(backup))
            self.assertEqual(target.read_bytes(), old_target_data)

    def test_in_place_asset_patch_still_refuses_unknown_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = b"vanilla executable"
            game_file.write_bytes(original)
            target = game_dir / "Sounds" / "children_giggle3.ogg"
            target.parent.mkdir()
            unknown = b"unknown existing sound"
            target.write_bytes(unknown)
            source = tmp_path / "payload" / "children_giggle3.ogg"
            source.parent.mkdir()
            replacement = b"known replacement sound"
            source.write_bytes(replacement)
            manifest = tmp_path / "asset_patch.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "in-place authentication unit test",
                        "target_files": [{"path": game_file.name, "sha256": sha256_bytes(original)}],
                        "asset_patches": [
                            {
                                "file_path": "Sounds/children_giggle3.ogg",
                                "source_path": "payload/children_giggle3.ogg",
                                "source_sha256": sha256_bytes(replacement),
                                "expected_target_sha256": sha256_bytes(b"known stock sound"),
                                "overwrite_existing": True,
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply", "--game-dir", str(game_dir), "--manifest", str(manifest), expect=2
            )
            self.assertIn("SHA-256 mismatch for existing asset target", result.stderr)
            self.assertEqual(target.read_bytes(), unknown)

    def test_asset_patch_refuses_source_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            source = tmp_path / "payload" / "Images" / "VF3SmallFlatScreenTVAnim.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"actual strip data")
            manifest = tmp_path / "asset_patch.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "asset hash mismatch unit test",
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/VF3SmallFlatScreenTVAnim.png",
                                "source_path": "payload/Images/VF3SmallFlatScreenTVAnim.png",
                                "source_sha256": sha256_bytes(b"different data"),
                                "note": "Refuse corrupted patch payload.",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn("SHA-256 mismatch for asset source", result.stderr)
            self.assertFalse((game_dir / "Images" / "VF3SmallFlatScreenTVAnim.png").exists())

    def test_output_only_reconfiguration_enables_and_restores_checked_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            modded_dir = tmp_path / "VF2-BUnit-Modded"
            (modded_dir / ".vf2_patch_backups").mkdir(parents=True)
            (modded_dir / "Images" / "Upgrades").mkdir(parents=True)
            (modded_dir / "Virtual Families 2 - Modded BUnit.exe").write_bytes(b"modded exe")
            upgrade = modded_dir / "Images" / "Upgrades" / "toolwall.png"
            upgrade.write_bytes(b"original upgrade")

            payload = tmp_path / "payload"
            invisible = payload / "OptionalVisualMods" / "Invisible Upgrades" / "toolwall.png"
            original = payload / "Original Virtual Families 2 Assets" / "Upgrades Original Graphics" / "toolwall.png"
            invisible.parent.mkdir(parents=True)
            original.parent.mkdir(parents=True)
            invisible.write_bytes(b"invisible upgrade")
            original.write_bytes(b"original upgrade")

            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "output-only reconfigure unit test",
                        "output": {
                            "default_folder_name": "VF2-BUnit-Modded",
                            "default_exe_name": "Virtual Families 2 - Modded BUnit.exe",
                        },
                        "settings": [
                            {
                                "id": "invisible_upgrades_graphics",
                                "label": "Invisible Upgrades Graphics",
                                "default": False,
                                "category": "optional",
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/Upgrades/toolwall.png",
                                "source_path": "payload/OptionalVisualMods/Invisible Upgrades/toolwall.png",
                                "source_sha256": sha256_bytes(b"invisible upgrade"),
                                "source_size": len(b"invisible upgrade"),
                                "restore_source_path": "payload/Original Virtual Families 2 Assets/Upgrades Original Graphics/toolwall.png",
                                "restore_source_sha256": sha256_bytes(b"original upgrade"),
                                "restore_source_size": len(b"original upgrade"),
                                "overwrite_existing": True,
                                "requires": ["invisible_upgrades_graphics"],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--output-dir",
                str(modded_dir),
                "--manifest",
                str(manifest),
                "--enable",
                "invisible_upgrades_graphics",
            )
            self.assertEqual(upgrade.read_bytes(), b"invisible upgrade")

            self.run_patcher(
                "apply",
                "--output-dir",
                str(modded_dir),
                "--manifest",
                str(manifest),
            )
            self.assertEqual(upgrade.read_bytes(), b"original upgrade")
            log_path = sorted((modded_dir / ".vf2_patch_backups").glob("*/patch_log.json"))[-1]
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(log["mode"], "existing_modded_output")
            self.assertTrue(any(row["action"] == "replace" for row in log["asset_files"]))

    def test_no_ai_icons_restore_wins_over_default_layer_and_cheat_disable_removes_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            modded = root / "VF2-BUnit-Modded"
            (modded / ".vf2_patch_backups").mkdir(parents=True)
            (modded / "Virtual Families 2 - Modded BUnit.exe").write_bytes(b"modded exe")
            target = modded / "Images" / "cheat_fill_house_messes.png"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"current icon")

            payload = root / "payload"
            default = payload / "Images" / target.name
            replacement = payload / "OptionalVisualMods" / "No AI Icons" / target.name
            default.parent.mkdir(parents=True)
            replacement.parent.mkdir(parents=True)
            default.write_bytes(b"current icon")
            replacement.write_bytes(b"no ai icon")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "output": {
                            "default_folder_name": modded.name,
                            "default_exe_name": "Virtual Families 2 - Modded BUnit.exe",
                        },
                        "settings": [
                            {"id": "core_executable", "default": True},
                            {"id": "cheat_upgrades", "default": True},
                            {"id": "no_ai_icons", "default": False},
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/cheat_fill_house_messes.png",
                                "source_path": "payload/Images/cheat_fill_house_messes.png",
                                "source_sha256": sha256_bytes(default.read_bytes()),
                                "source_size": default.stat().st_size,
                                "overwrite_existing": True,
                                "remove_when_disabled": True,
                                "requires": ["core_executable", "cheat_upgrades"],
                            },
                            {
                                "file_path": "Images/cheat_fill_house_messes.png",
                                "source_path": "payload/OptionalVisualMods/No AI Icons/cheat_fill_house_messes.png",
                                "source_sha256": sha256_bytes(replacement.read_bytes()),
                                "source_size": replacement.stat().st_size,
                                "restore_source_path": "payload/Images/cheat_fill_house_messes.png",
                                "restore_source_sha256": sha256_bytes(default.read_bytes()),
                                "restore_source_size": default.stat().st_size,
                                "restore_requires": ["core_executable", "cheat_upgrades"],
                                "overwrite_existing": True,
                                "requires": ["core_executable", "cheat_upgrades", "no_ai_icons"],
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--output-dir", str(modded),
                "--manifest", str(manifest),
                "--enable", "no_ai_icons",
            )
            self.assertEqual(target.read_bytes(), b"no ai icon")

            self.run_patcher(
                "apply",
                "--output-dir", str(modded),
                "--manifest", str(manifest),
            )
            self.assertEqual(target.read_bytes(), b"current icon")

            self.run_patcher(
                "apply",
                "--output-dir", str(modded),
                "--manifest", str(manifest),
                "--disable", "cheat_upgrades",
            )
            self.assertFalse(target.exists())

    def test_output_only_removes_hash_authenticated_overlay_asset_and_refuses_unknown_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            modded_dir = tmp_path / "VF2-BUnit-Modded"
            (modded_dir / ".vf2_patch_backups").mkdir(parents=True)
            (modded_dir / "Virtual Families 2 - Modded BUnit.exe").write_bytes(b"modded exe")
            target = modded_dir / "Images" / "MobileRenovations" / "tp238_beige_kitchen.png"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"vanilla placeholder")

            payload = tmp_path / "payload"
            source = payload / "Images" / "MobileRenovations" / "tp238_beige_kitchen.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"mobile renovation")

            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "output-only overlay removal unit test",
                        "output": {
                            "default_folder_name": "VF2-BUnit-Modded",
                            "default_exe_name": "Virtual Families 2 - Modded BUnit.exe",
                        },
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                                "category": "main",
                            },
                            {
                                "id": "mobile_renovations",
                                "label": "Mobile Room Renovations",
                                "default": False,
                                "category": "optional",
                            }
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Images/MobileRenovations/tp238_beige_kitchen.png",
                                "source_path": "payload/Images/MobileRenovations/tp238_beige_kitchen.png",
                                "source_sha256": sha256_bytes(source.read_bytes()),
                                "source_size": source.stat().st_size,
                                "overwrite_existing": True,
                                "remove_when_disabled": True,
                                "requires": ["core_executable", "mobile_renovations"],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--output-dir",
                str(modded_dir),
                "--manifest",
                str(manifest),
                "--enable",
                "mobile_renovations",
            )
            self.assertEqual(target.read_bytes(), b"mobile renovation")

            target.write_bytes(b"player-customized")
            result = self.run_patcher(
                "apply",
                "--output-dir",
                str(modded_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn("Refusing removal", result.stderr)
            self.assertEqual(target.read_bytes(), b"player-customized")

            self.run_patcher(
                "apply",
                "--output-dir",
                str(modded_dir),
                "--manifest",
                str(manifest),
                "--enable",
                "mobile_renovations",
            )
            self.run_patcher(
                "apply",
                "--output-dir",
                str(modded_dir),
                "--manifest",
                str(manifest),
            )
            self.assertFalse(target.exists())

    def test_rejects_ambiguous_cheat_and_mobile_executable_overlays(self):
        def overlay(index, requires):
            return patcher_mod.AssetPatch(
                index=index,
                file_path="Virtual Families 2.exe",
                output_file_path="Virtual Families 2 - Modded BUnit.exe",
                source_path=f"payload/overlay-{index}.exe",
                source_sha256="0" * 64,
                source_size=1,
                expected_target_sha256="1" * 64,
                expected_target_pe_structures=(),
                expected_target_size=1,
                allow_missing_target=False,
                overwrite_existing=True,
                note="overlay",
                requires=tuple(requires),
            )

        assets = [
            overlay(0, ["core_executable"]),
            overlay(1, ["core_executable", "cheat_upgrades"]),
            overlay(2, ["core_executable", "mobile_renovations"]),
        ]
        with self.assertRaisesRegex(patcher_mod.PatchError, "No unique executable overlay"):
            patcher_mod.select_exact_executable_overlays(
                assets,
                {"core_executable", "cheat_upgrades", "mobile_renovations"},
            )
        selected = patcher_mod.select_exact_executable_overlays(
            [*assets, overlay(3, ["core_executable", "cheat_upgrades", "mobile_renovations"])],
            {"core_executable", "cheat_upgrades", "mobile_renovations"},
        )
        self.assertEqual([asset.index for asset in selected], [3])

    def test_rejects_mixed_active_restore_same_exe_target(self):
        def exe(index, source, *, restore=False, requires=("core_executable",)):
            return patcher_mod.AssetPatch(
                index=index,
                file_path="Virtual Families 2.exe",
                output_file_path="Virtual Families 2 - Modded BUnit.exe",
                source_path=source,
                source_sha256="0" * 64,
                source_size=1,
                expected_target_sha256="1" * 64,
                expected_target_pe_structures=(),
                expected_target_size=1,
                allow_missing_target=False,
                overwrite_existing=True,
                note="test",
                requires=tuple(requires),
                restore=restore,
            )

        with self.assertRaisesRegex(patcher_mod.PatchError, "Conflicting duplicate asset output target"):
            patcher_mod.validate_asset_target_plan(
                [
                    exe(0, "payload/core.exe"),
                    exe(1, "payload/restore.exe", restore=True, requires=()),
                ]
            )

    def test_rejects_duplicate_non_executable_targets(self):
        def image(index, source):
            return patcher_mod.AssetPatch(
                index=index,
                file_path="Images/MobileRenovations/x.png",
                output_file_path=None,
                source_path=source,
                source_sha256="0" * 64,
                source_size=1,
                expected_target_sha256=None,
                expected_target_pe_structures=(),
                expected_target_size=None,
                allow_missing_target=True,
                overwrite_existing=True,
                note="test",
                requires=("core_executable",),
            )

        with self.assertRaisesRegex(patcher_mod.PatchError, "Conflicting duplicate asset output target"):
            patcher_mod.validate_asset_target_plan(
                [image(0, "payload/a.png"), image(1, "payload/b.png")]
            )

    def test_output_only_refuses_unknown_executable_hash_before_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            modded_dir = tmp_path / "VF2-BUnit-Modded"
            (modded_dir / ".vf2_patch_backups").mkdir(parents=True)
            output_exe = modded_dir / "Virtual Families 2 - Modded BUnit.exe"
            output_exe.write_bytes(b"unknown current executable")

            payload = tmp_path / "payload"
            payload.mkdir()
            source = payload / "core.exe"
            source.write_bytes(b"known bundled executable")
            manifest = tmp_path / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "output": {
                            "default_folder_name": "VF2-BUnit-Modded",
                            "default_exe_name": output_exe.name,
                        },
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Patch game executable",
                                "default": True,
                                "category": "main",
                            },
                            {
                                "id": "mobile_renovations",
                                "label": "Mobile Room Renovations",
                                "default": True,
                                "category": "optional",
                            },
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Virtual Families 2.exe",
                                "output_file_path": output_exe.name,
                                "source_path": "payload/core.exe",
                                "source_sha256": sha256_bytes(source.read_bytes()),
                                "source_size": source.stat().st_size,
                                "expected_target_sha256": "1" * 64,
                                "expected_target_size": 1,
                                "overwrite_existing": True,
                                "requires": ["core_executable", "mobile_renovations"],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--output-dir",
                str(modded_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn("unknown current SHA-256", result.stderr)
            self.assertEqual(output_exe.read_bytes(), b"unknown current executable")

    def test_output_only_accepts_composed_authenticated_runtime_toggles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "VF2-BUnit-Modded"
            output_dir.mkdir()
            exe_name = "Virtual Families 2 - Modded BUnit.exe"
            base = b"BASE-TOGGLE-A-TOGGLE-B-END"
            composed = bytearray(base)
            offset_a = base.index(b"A")
            offset_b = base.index(b"B")
            composed[offset_a] = ord("1")
            composed[offset_b] = ord("1")
            (output_dir / exe_name).write_bytes(composed)
            payload = root / "payload"
            payload.mkdir()
            source = payload / "core.exe"
            source.write_bytes(base)
            base_sha = sha256_bytes(base)
            manifest = {
                "settings": [
                    {"id": "core_executable", "default": True},
                    {"id": "mobile_renovations", "default": True},
                    {"id": "toggle_a", "default": True},
                    {"id": "toggle_b", "default": True},
                ],
                "asset_patches": [
                    {
                        "file_path": "Virtual Families 2.exe",
                        "output_file_path": exe_name,
                        "source_path": "payload/core.exe",
                        "source_sha256": base_sha,
                        "expected_target_sha256": "1" * 64,
                        "overwrite_existing": True,
                        "requires": ["core_executable", "mobile_renovations"],
                    }
                ],
                "post_asset_patches": [
                    {
                        "file_path": exe_name,
                        "requires": ["toggle_a"],
                        "variants": [{
                            "asset_sha256": base_sha,
                            "offset": offset_a,
                            "expected_asset_bytes": "41",
                            "replacement_bytes": "31",
                        }],
                    },
                    {
                        "file_path": exe_name,
                        "requires": ["toggle_b"],
                        "variants": [{
                            "asset_sha256": base_sha,
                            "offset": offset_b,
                            "expected_asset_bytes": "42",
                            "replacement_bytes": "31",
                        }],
                    },
                ],
            }
            active = patcher_mod.manifest_asset_patches(
                manifest,
                patcher_mod.manifest_settings(manifest),
                {"core_executable", "mobile_renovations", "toggle_a", "toggle_b"},
            )

            patcher_mod.verify_reconfigure_executable_identity(manifest, root, output_dir, active)

            tampered = bytearray(composed)
            tampered[-1] ^= 1
            (output_dir / exe_name).write_bytes(tampered)
            with self.assertRaisesRegex(patcher_mod.PatchError, "unknown current SHA-256"):
                patcher_mod.verify_reconfigure_executable_identity(manifest, root, output_dir, active)

    def test_mobile_sound_enable_then_disable_restores_exe_before_removing_oggs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            modded = root / "VF2-BSound-Modded"
            (modded / ".vf2_patch_backups").mkdir(parents=True)
            exe_name = "Virtual Families 2 - Modded BSound.exe"
            routes = (
                ("beaker.wav", "beaker.ogg"),
                ("Child3.wav", "Child3.ogg"),
                ("Child7.wav", "Child7.ogg"),
                ("Child8.wav", "Child8.ogg"),
            )
            core_data = b"prefix:" + b"|".join(pc.encode("ascii") for pc, _ogg in routes) + b":suffix"
            output_exe = modded / exe_name
            output_exe.write_bytes(core_data)
            payload = root / "payload"
            payload.mkdir()
            core_source = payload / "core.exe"
            core_source.write_bytes(core_data)

            patched = bytearray(core_data)
            post = []
            ogg_records = []
            for index, (pc_name, ogg_name) in enumerate(routes):
                offset = core_data.index(pc_name.encode("ascii"))
                patched[offset : offset + len(pc_name)] = ogg_name.encode("ascii")
                ogg_source = payload / ogg_name
                ogg_source.write_bytes(b"OggS" + bytes([index]) + b"payload")
                ogg_records.append({
                    "file_path": f"Sounds/{ogg_name}",
                    "source_path": f"payload/{ogg_name}",
                    "source_sha256": sha256_bytes(ogg_source.read_bytes()),
                    "source_size": ogg_source.stat().st_size,
                    "allow_missing_target": True,
                    "overwrite_existing": True,
                    "remove_when_disabled": True,
                    "requires": ["core_executable", "mobile_sound_assets"],
                })
                post.append({
                    "file_path": exe_name,
                    "requires": ["core_executable", "mobile_sound_assets"],
                    "variants": [{
                        "asset_sha256": sha256_bytes(core_data),
                        "result_asset_sha256": sha256_bytes(bytes(patched)) if index == len(routes) - 1 else "0" * 64,
                        "offset": hex(offset),
                        "expected_asset_bytes": pc_name.encode("ascii").hex(),
                        "replacement_bytes": ogg_name.encode("ascii").hex(),
                    }],
                })
            final_sha = sha256_bytes(bytes(patched))
            for row in post:
                row["variants"][0]["result_asset_sha256"] = final_sha

            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "manifest_version": 1,
                "output": {"default_folder_name": modded.name, "default_exe_name": exe_name},
                "settings": [
                    {"id": "core_executable", "label": "Core", "default": True, "category": "main"},
                    {"id": "mobile_sound_assets", "label": "Mobile sounds", "default": False, "category": "optional"},
                ],
                "asset_patches": [{
                    "file_path": "Virtual Families 2.exe",
                    "output_file_path": exe_name,
                    "source_path": "payload/core.exe",
                    "source_sha256": sha256_bytes(core_data),
                    "source_size": len(core_data),
                    "expected_target_sha256": sha256_bytes(core_data),
                    "expected_target_size": len(core_data),
                    "overwrite_existing": True,
                    "requires": ["core_executable"],
                }, *ogg_records],
                "post_asset_patches": post,
            }, indent=2), encoding="utf-8")

            self.run_patcher("apply", "--output-dir", str(modded), "--manifest", str(manifest), "--enable", "mobile_sound_assets")
            self.assertEqual(output_exe.read_bytes(), bytes(patched))
            self.assertTrue(all((modded / "Sounds" / ogg).is_file() for _pc, ogg in routes))

            corrupt_target = modded / "Sounds" / routes[0][1]
            corrupt_target.write_bytes(b"player-modified")
            result = self.run_patcher(
                "apply", "--output-dir", str(modded), "--manifest", str(manifest), expect=2
            )
            self.assertIn("Refusing removal", result.stderr)
            self.assertEqual(output_exe.read_bytes(), bytes(patched))
            self.assertEqual(corrupt_target.read_bytes(), b"player-modified")
            corrupt_target.write_bytes((payload / routes[0][1]).read_bytes())

            self.run_patcher("apply", "--output-dir", str(modded), "--manifest", str(manifest))
            self.assertEqual(output_exe.read_bytes(), core_data)
            self.assertTrue(all(not (modded / "Sounds" / ogg).exists() for _pc, ogg in routes))

    def test_mobile_sound_all_67_assets_restore_63_and_remove_four_routes(self):
        import export_offline_patch_bundle as exporter

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            modded = root / "VF2-BSound67-Modded"
            (modded / ".vf2_patch_backups").mkdir(parents=True)
            sounds = modded / "Sounds"
            sounds.mkdir()
            exe_name = "Virtual Families 2 - Modded BSound67.exe"
            routes = (
                ("beaker.wav", "beaker.ogg"),
                ("Child3.wav", "Child3.ogg"),
                ("Child7.wav", "Child7.ogg"),
                ("Child8.wav", "Child8.ogg"),
            )
            core_data = b"prefix:" + b"|".join(pc.encode("ascii") for pc, _ in routes) + b":suffix"
            output_exe = modded / exe_name
            output_exe.write_bytes(core_data)

            bundle = root / "bundle"
            payload = bundle / "payload"
            base = root / "base"
            bundle.mkdir()
            base.mkdir()
            base_sounds = base / "Sounds"
            base_sounds.mkdir()
            original_same_stem = {}
            for filename, pc_name in exporter.MOBILE_SOUND_PC_FILENAMES.items():
                if filename == pc_name:
                    original = (f"stock-{filename}\0").encode("ascii")
                    original_same_stem[filename] = original
                    (base_sounds / filename).write_bytes(original)
            records = exporter.mobile_sound_asset_patches(
                bundle,
                base,
                exporter.MOBILE_SOUND_ASSET_SOURCE_DIR,
            )
            self.assertEqual(len(records), 67)
            self.assertEqual(sum("restore_source_path" in row for row in records), 63)
            self.assertEqual(sum(bool(row["remove_when_disabled"]) for row in records), 4)
            remove_names = {
                Path(row["file_path"]).name
                for row in records
                if row["remove_when_disabled"]
            }
            self.assertEqual(
                remove_names,
                {"beaker.ogg", "Child3.ogg", "Child7.ogg", "Child8.ogg"},
            )
            for filename, original in original_same_stem.items():
                (sounds / filename).write_bytes(original)

            core_source = payload / "core.exe"
            core_source.parent.mkdir(parents=True, exist_ok=True)
            core_source.write_bytes(core_data)
            patched = bytearray(core_data)
            post = []
            for pc_name, ogg_name in routes:
                offset = core_data.index(pc_name.encode("ascii"))
                patched[offset : offset + len(pc_name)] = ogg_name.encode("ascii")
                post.append(
                    {
                        "file_path": exe_name,
                        "requires": ["core_executable", "mobile_sound_assets"],
                        "variants": [
                            {
                                "asset_sha256": sha256_bytes(core_data),
                                "result_asset_sha256": sha256_bytes(bytes(patched)),
                                "offset": hex(offset),
                                "expected_asset_bytes": pc_name.encode("ascii").hex(),
                                "replacement_bytes": ogg_name.encode("ascii").hex(),
                            }
                        ],
                    }
                )
            final_patched_sha = sha256_bytes(bytes(patched))
            for row in post:
                row["variants"][0]["result_asset_sha256"] = final_patched_sha

            manifest = bundle / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "output": {
                            "default_folder_name": modded.name,
                            "default_exe_name": exe_name,
                        },
                        "settings": [
                            {
                                "id": "core_executable",
                                "label": "Core",
                                "default": True,
                                "category": "main",
                            },
                            {
                                "id": "mobile_sound_assets",
                                "label": "Mobile sounds",
                                "default": False,
                                "category": "optional",
                            },
                        ],
                        "asset_patches": [
                            {
                                "file_path": "Virtual Families 2.exe",
                                "output_file_path": exe_name,
                                "source_path": "payload/core.exe",
                                "source_sha256": sha256_bytes(core_data),
                                "source_size": len(core_data),
                                "expected_target_sha256": sha256_bytes(core_data),
                                "expected_target_size": len(core_data),
                                "overwrite_existing": True,
                                "requires": ["core_executable"],
                            },
                            *records,
                        ],
                        "post_asset_patches": post,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.run_patcher(
                "apply",
                "--output-dir",
                str(modded),
                "--manifest",
                str(manifest),
                "--enable",
                "mobile_sound_assets",
            )
            self.assertEqual(output_exe.read_bytes(), bytes(patched))
            self.assertTrue(
                all(
                    (sounds / filename).is_file()
                    for filename in exporter.MOBILE_SOUND_ASSET_FILES
                )
            )

            self.run_patcher(
                "apply",
                "--output-dir",
                str(modded),
                "--manifest",
                str(manifest),
            )
            self.assertEqual(output_exe.read_bytes(), core_data)
            self.assertEqual(
                {path.name for path in sounds.iterdir()},
                set(original_same_stem),
            )
            for filename, original in original_same_stem.items():
                self.assertEqual((sounds / filename).read_bytes(), original)
            self.assertTrue(all(not (sounds / filename).exists() for filename in remove_names))

    def test_refuses_expected_byte_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "patch.json"
            backup = tmp_path / "backup"
            failure_log = tmp_path / "failure.json"
            self.write_manifest(manifest, game_file, original, expected="99 99")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(backup),
                "--log",
                str(failure_log),
                expect=2,
            )
            self.assertIn("expected bytes do not match", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)
            self.assertFalse(backup.exists())
            self.assertTrue(failure_log.is_file())
            log = json.loads(failure_log.read_text(encoding="utf-8"))
            self.assertEqual(log["status"], "failure")
            self.assertTrue(any(row["status"] == "error" and row["kind"] == "byte_patch" for row in log["process_log"]))

    def test_refuses_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4, 5, 6])
            game_file.write_bytes(original)
            manifest = tmp_path / "patch.json"
            self.write_manifest(manifest, game_file, b"wrong original bytes")

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                expect=2,
            )
            self.assertIn("SHA-256 mismatch", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)

    def test_setting_defaults_and_explicit_enable(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            optional_file = game_dir / "optional-holiday.dat"
            original = bytes([1, 2, 3, 4, 5, 6])
            optional_original = b"holiday"
            game_file.write_bytes(original)
            manifest = tmp_path / "settings_patch.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "name": "settings unit test",
                        "settings": [
                            {
                                "id": "holiday_furniture",
                                "label": "Add Holiday furniture",
                                "description": "Adds mobile holiday furniture.",
                                "default": False,
                            },
                            {
                                "id": "mobile_furniture",
                                "label": "Add additional mobile-exclusive furniture",
                                "default": True,
                            },
                        ],
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                                "size": len(original),
                            },
                            {
                                "path": "optional-holiday.dat",
                                "sha256": sha256_bytes(optional_original),
                                "requires": ["holiday_furniture"],
                            },
                        ],
                        "patches": [
                            {
                                "file_path": game_file.name,
                                "offset": "0x1",
                                "expected_original_bytes": "02",
                                "replacement_bytes": "20",
                                "requires": ["mobile_furniture"],
                                "note": "default-on mobile furniture patch",
                            },
                            {
                                "file_path": game_file.name,
                                "offset": "0x3",
                                "expected_original_bytes": "04",
                                "replacement_bytes": "40",
                                "setting": "holiday_furniture",
                                "note": "optional holiday furniture patch",
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            settings = self.run_patcher("settings", "--manifest", str(manifest))
            self.assertIn("holiday_furniture [default off]", settings.stdout)
            self.assertIn("mobile_furniture [default on]", settings.stdout)

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(tmp_path / "backup-default"),
            )
            self.assertEqual(game_file.read_bytes(), bytes([1, 0x20, 3, 4, 5, 6]))

            game_file.write_bytes(original)
            optional_file.write_bytes(optional_original)
            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--backup-dir",
                str(tmp_path / "backup-enabled"),
                "--enable",
                "holiday_furniture",
            )
            self.assertEqual(game_file.read_bytes(), bytes([1, 0x20, 3, 0x40, 5, 6]))

    def test_disable_all_requires_explicit_enabled_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "game"
            game_dir.mkdir()
            game_file = game_dir / "Virtual Families 2.exe"
            original = bytes([1, 2, 3, 4])
            game_file.write_bytes(original)
            manifest = tmp_path / "settings_patch.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "settings": {
                            "holiday_outfits": {
                                "label": "Add Holiday outfits",
                                "default": True,
                            }
                        },
                        "target_files": [
                            {
                                "path": game_file.name,
                                "sha256": sha256_bytes(original),
                            }
                        ],
                        "patches": [
                            {
                                "file_path": game_file.name,
                                "offset": 1,
                                "expected_original_bytes": "02",
                                "replacement_bytes": "99",
                                "requires": ["holiday_outfits"],
                                "note": "holiday outfit toggle patch",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--disable-all",
                expect=2,
            )
            self.assertIn("No active patches", result.stderr)
            self.assertEqual(game_file.read_bytes(), original)

            self.run_patcher(
                "apply",
                "--game-dir",
                str(game_dir),
                "--manifest",
                str(manifest),
                "--disable-all",
                "--enable",
                "holiday_outfits",
                "--backup-dir",
                str(tmp_path / "backup"),
            )
            self.assertEqual(game_file.read_bytes(), bytes([1, 0x99, 3, 4]))


if __name__ == "__main__":
    unittest.main()
