import hashlib
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

import package_patcher_zip as packager


def pe32_x86(marker=0):
    data = bytearray(0x300)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x14C)
    struct.pack_into("<H", data, 0x86, 1)
    struct.pack_into("<H", data, 0x94, 0xE0)
    struct.pack_into("<H", data, 0x98, 0x10B)
    section = 0x178
    data[section:section + 8] = b".text\0\0\0"
    struct.pack_into("<IIIIIIHHI", data, section + 8, 0x100, 0x1000, 0x100, 0x200, 0, 0, 0, 0, 0x60000020)
    data[0x200] = marker
    return bytes(data)


class PackagePatcherZipTests(unittest.TestCase):
    def write_manifest(self, root, exe=None, *, launcher=False, exact_target=True, include_asset_record=False):
        target_sha = "11" * 32
        manifest = {
            "asset_patches": [],
            "target_files": [],
            "output": {"default_exe_name": "Virtual Families 2 - Modded.exe"},
            "export_summary": {"runner_files": []},
        }
        if exe is not None and (not launcher or include_asset_record):
            data = exe.read_bytes()
            record = {
                "source_path": exe.relative_to(root).as_posix(),
                "source_sha256": hashlib.sha256(data).hexdigest(),
                "source_size": len(data),
                "file_path": "Virtual Families 2.exe",
                "output_file_path": "Virtual Families 2 - Modded.exe",
                "requires": ["core_executable"],
            }
            if exact_target:
                record.update(expected_target_sha256=target_sha, expected_target_size=1234)
                manifest["target_files"] = [{"path": "Virtual Families 2.exe", "sha256": target_sha, "size": 1234}]
            manifest["asset_patches"] = [record]
        if launcher:
            data = exe.read_bytes()
            rel = exe.relative_to(root).as_posix()
            manifest["export_summary"]["launcher"] = {
                "status": "built", "output": rel,
                "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
            }
            manifest["export_summary"]["runner_files"] = [rel]
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_accepts_manifest_authorized_payload_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"
            exe = root / "payload" / "modded.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(pe32_x86())
            self.write_manifest(root, exe)
            archive = Path(tmp) / "bundle.zip"
            self.assertEqual(packager.package(root, archive), 2)
            with zipfile.ZipFile(archive) as zipped:
                self.assertIn("bundle/payload/modded.exe", zipped.namelist())

    def test_rejects_unreferenced_or_arbitrary_executable_before_zip_creation(self):
        for relative in ("payload/extra.exe", "Virtual Families 2.exe"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "bundle"
                exe = root / relative
                exe.parent.mkdir(parents=True)
                exe.write_bytes(pe32_x86())
                self.write_manifest(root)
                archive = Path(tmp) / "bundle.zip"
                with self.assertRaises(ValueError):
                    packager.package(root, archive)
                self.assertFalse(archive.exists())

    def test_rejects_bad_payload_identity_or_non_pe(self):
        for data, exact_target in ((pe32_x86(), False), (b"not-pe", True)):
            with self.subTest(exact_target=exact_target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "bundle"
                exe = root / "payload" / "modded.exe"
                exe.parent.mkdir(parents=True)
                exe.write_bytes(data)
                self.write_manifest(root, exe, exact_target=exact_target)
                with self.assertRaises(ValueError):
                    packager.package(root, Path(tmp) / "bundle.zip")

    def test_rejects_sectionless_truncated_or_out_of_bounds_pe(self):
        sectionless = bytearray(pe32_x86())
        struct.pack_into("<H", sectionless, 0x86, 0)
        truncated_optional = pe32_x86()[:0x99]
        truncated_section_table = pe32_x86()[:0x178 + 39]
        out_of_bounds_section = bytearray(pe32_x86())
        struct.pack_into("<I", out_of_bounds_section, 0x178 + 16, 0x200)
        for data in (bytes(sectionless), truncated_optional, truncated_section_table, bytes(out_of_bounds_section)):
            with self.subTest(size=len(data)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "bundle"
                exe = root / "payload" / "modded.exe"
                exe.parent.mkdir(parents=True)
                exe.write_bytes(data)
                self.write_manifest(root, exe)
                archive = Path(tmp) / "bundle.zip"
                with self.assertRaises(ValueError):
                    packager.package(root, archive)
                self.assertFalse(archive.exists())

    def test_accepts_attested_root_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"
            root.mkdir()
            exe = root / "VF2 Patcher.exe"
            exe.write_bytes(pe32_x86())
            self.write_manifest(root, exe, launcher=True)
            archive = Path(tmp) / "bundle.zip"
            self.assertEqual(packager.package(root, archive), 2)

    def test_rejects_nested_attested_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"
            exe = root / "tools" / "VF2 Patcher.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(pe32_x86())
            self.write_manifest(root, exe, launcher=True)
            archive = Path(tmp) / "bundle.zip"
            with self.assertRaisesRegex(ValueError, "bundle root"):
                packager.package(root, archive)
            self.assertFalse(archive.exists())

    def test_rejects_launcher_asset_role_collision(self):
        for relative in ("VF2 Patcher.exe", "payload/modded.exe"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "bundle"
                exe = root / relative
                exe.parent.mkdir(parents=True)
                exe.write_bytes(pe32_x86())
                self.write_manifest(root, exe, launcher=True, include_asset_record=True)
                archive = Path(tmp) / "bundle.zip"
                with self.assertRaisesRegex(ValueError, "asset payload"):
                    packager.package(root, archive)
                self.assertFalse(archive.exists())

    def test_accepts_zero_executable_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"
            root.mkdir()
            self.write_manifest(root)
            archive = Path(tmp) / "bundle.zip"
            self.assertEqual(packager.package(root, archive), 1)

    def test_rejects_case_insensitive_duplicate_executable_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"
            payload = root / "payload"
            payload.mkdir(parents=True)
            first = payload / "modded.exe"
            first.write_bytes(pe32_x86())
            self.write_manifest(root, first)
            second = payload / "MODDED.exe"
            archive = Path(tmp) / "bundle.zip"
            with self.assertRaisesRegex(ValueError, "duplicate executable"):
                packager.validate_executable_inventory(root, [first, second])
            self.assertFalse(archive.exists())


if __name__ == "__main__":
    unittest.main()
