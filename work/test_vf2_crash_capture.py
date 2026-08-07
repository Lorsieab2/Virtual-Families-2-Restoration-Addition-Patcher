import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import vf2_crash_capture as crash


class Vf2CrashCaptureTests(unittest.TestCase):
    PE_TIMESTAMP = 0x5F3759DF
    PE_SIZE_OF_IMAGE = 0x5000
    PE_CHECKSUM = 0x11223344
    MODULE_BASE = 0x400000
    EXCEPTION_ADDRESS = 0x401234

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.exe = self.root / "Virtual Families 2 - Debugger Test.exe"
        self.exe.write_bytes(self.pe32())
        self.capture = self.root / "capture"
        self.capture.mkdir()
        self.dump = self.capture / "crash.dmp"
        self.dump.write_bytes(self.minidump())
        self.log = self.capture / "ldwLog.txt"
        self.log.write_text("crash action: test\n", encoding="utf-8")
        self.manifest = self.root / "exact-build.json"
        self.write_manifest()

    def tearDown(self):
        self.tmp.cleanup()

    def identity(self, path):
        data = path.read_bytes()
        return {"path": path.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def pe32(self, *, timestamp=None, size_of_image=None, checksum=None, machine=0x14C):
        timestamp = self.PE_TIMESTAMP if timestamp is None else timestamp
        size_of_image = self.PE_SIZE_OF_IMAGE if size_of_image is None else size_of_image
        checksum = self.PE_CHECKSUM if checksum is None else checksum
        image = bytearray(0x400)
        image[:2] = b"MZ"
        struct.pack_into("<I", image, 0x3C, 0x80)
        image[0x80:0x84] = b"PE\0\0"
        struct.pack_into("<HHIIIHH", image, 0x84, machine, 1, timestamp, 0, 0, 0xE0, 0x010F)
        optional = 0x98
        struct.pack_into("<H", image, optional, 0x10B)
        struct.pack_into("<I", image, optional + 16, 0x1000)
        struct.pack_into("<I", image, optional + 28, self.MODULE_BASE)
        struct.pack_into("<I", image, optional + 32, 0x1000)
        struct.pack_into("<I", image, optional + 36, 0x200)
        struct.pack_into("<I", image, optional + 56, size_of_image)
        struct.pack_into("<I", image, optional + 60, 0x200)
        struct.pack_into("<I", image, optional + 64, checksum)
        struct.pack_into("<H", image, optional + 68, 2)
        struct.pack_into("<I", image, optional + 92, 16)
        section = optional + 0xE0
        image[section:section + 8] = b".text\0\0\0"
        struct.pack_into("<IIII", image, section + 8, 0x1000, 0x1000, 0x200, 0x200)
        struct.pack_into("<I", image, section + 36, 0x60000020)
        return bytes(image)

    def minidump(
        self,
        *,
        module_name=None,
        module_base=None,
        module_size=None,
        module_timestamp=None,
        module_checksum=None,
        exception_address=None,
        exception_code=0xC0000005,
        context_eip=None,
        context_flags=0x00010007,
        duplicate_main_module=False,
    ):
        module_name = self.exe.name if module_name is None else module_name
        module_base = self.MODULE_BASE if module_base is None else module_base
        module_size = self.PE_SIZE_OF_IMAGE if module_size is None else module_size
        module_timestamp = self.PE_TIMESTAMP if module_timestamp is None else module_timestamp
        module_checksum = self.PE_CHECKSUM if module_checksum is None else module_checksum
        exception_address = self.EXCEPTION_ADDRESS if exception_address is None else exception_address
        context_eip = exception_address if context_eip is None else context_eip

        directory_rva = 32
        directory_size = 3 * 12
        system_info_rva = directory_rva + directory_size
        exception_rva = system_info_rva + 56
        context_rva = exception_rva + 168
        module_list_rva = context_rva + 716
        module_count = 2 if duplicate_main_module else 1
        module_name_rva = module_list_rva + 4 + (108 * module_count)

        system_info = bytearray(56)
        struct.pack_into("<H", system_info, 0, 0)  # PROCESSOR_ARCHITECTURE_INTEL
        system_info[6] = 1

        context = bytearray(716)
        struct.pack_into("<I", context, 0, context_flags)
        registers = {
            156: 0x6, 160: 0x5, 164: 0x2, 168: 0x4, 172: 0x3, 176: 0x1,
            180: 0x700000, 184: context_eip, 192: 0x202, 196: 0x700100,
        }
        for offset, value in registers.items():
            struct.pack_into("<I", context, offset, value)

        exception = bytearray(168)
        struct.pack_into("<I", exception, 0, 1)
        struct.pack_into("<I", exception, 8, exception_code)
        struct.pack_into("<Q", exception, 24, exception_address)
        struct.pack_into("<II", exception, 160, len(context), context_rva)

        encoded_name = module_name.encode("utf-16-le")
        module_name_record = struct.pack("<I", len(encoded_name)) + encoded_name
        module_list = bytearray(4 + (108 * module_count))
        struct.pack_into("<I", module_list, 0, module_count)
        for index in range(module_count):
            struct.pack_into(
                "<QIIII",
                module_list,
                4 + (index * 108),
                module_base,
                module_size,
                module_checksum,
                module_timestamp,
                module_name_rva + (index * len(module_name_record)),
            )
        module_name_records = module_name_record * module_count

        header = struct.pack("<4sIIIIIQ", b"MDMP", 0xA793, 3, directory_rva, 0, 0, 0)
        directory = b"".join((
            struct.pack("<III", 7, len(system_info), system_info_rva),
            struct.pack("<III", 6, len(exception), exception_rva),
            struct.pack("<III", 4, len(module_list), module_list_rva),
        ))
        return b"".join((header, directory, system_info, exception, context, module_list, module_name_records))

    def write_manifest(self, *, capture=True):
        data = self.exe.read_bytes()
        manifest = {
            "schema": crash.MANIFEST_SCHEMA,
            "executable": {
                "path": str(self.exe.resolve()),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
        }
        if capture:
            manifest["capture"] = {
                "dump": self.identity(self.dump),
                "logs": [self.identity(self.log)],
            }
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")

    def test_verify_exe_requires_exact_path_size_and_hash(self):
        actual = crash.verify_executable(self.manifest, self.exe)
        self.assertEqual(actual["size"], self.exe.stat().st_size)
        self.assertEqual(actual["sha256"], hashlib.sha256(self.exe.read_bytes()).hexdigest())

        other = self.root / "other.exe"
        other.write_bytes(self.exe.read_bytes())
        with self.assertRaisesRegex(ValueError, "path disagrees"):
            crash.verify_executable(self.manifest, other)

        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["executable"]["size"] += 1
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            crash.verify_executable(self.manifest, self.exe)

        manifest["executable"]["size"] = self.exe.stat().st_size
        manifest["executable"]["sha256"] = "00" * 32
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            crash.verify_executable(self.manifest, self.exe)

    def test_verify_exe_rejects_missing_and_zero_byte(self):
        missing = self.root / "missing.exe"
        with self.assertRaises(ValueError):
            crash.verify_executable(self.manifest, missing)
        self.exe.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "zero-byte"):
            crash.verify_executable(self.manifest, self.exe)

    def test_wer_plan_is_instruction_only_and_per_executable(self):
        state_out = self.root / "wer-state.json"
        instructions_out = self.root / "wer-instructions.ps1"
        state = crash.emit_wer_plan(
            self.manifest,
            self.exe,
            self.root / "dumps",
            state_out,
            instructions_out,
        )
        self.assertFalse(state["registry_modified"])
        self.assertTrue(state["instructions_only"])
        self.assertIn(self.exe.name, state["registry_key"])
        instructions = instructions_out.read_text(encoding="utf-8")
        restore_out = self.root / "wer-instructions.restore.ps1"
        self.assertTrue(restore_out.is_file())
        restore = restore_out.read_text(encoding="utf-8")
        self.assertIn(state["registry_key"], instructions)
        self.assertNotIn("Remove-Item -LiteralPath $providerKey", instructions)
        self.assertNotIn("reg.exe import", instructions)
        self.assertIn("Remove-Item -LiteralPath $providerKey", restore)
        self.assertIn("reg.exe import $backupFile", restore)
        self.assertLess(
            restore.index("Remove-Item -LiteralPath $providerKey"),
            restore.index("reg.exe import $backupFile"),
        )
        self.assertNotIn("Remove-Item -LiteralPath 'HKCU:\\Software\\Microsoft\\Windows\\Windows Error Reporting\\LocalDumps'", instructions)
        self.assertLess(
            instructions.index("if (Test-Path -LiteralPath $backupFile)"),
            instructions.index("if (Test-Path -LiteralPath $providerKey)"),
        )

    def test_wer_plan_rejects_stale_backup_before_writing_outputs(self):
        state_out = self.root / "wer-state.json"
        instructions_out = self.root / "wer-instructions.ps1"
        (self.root / "wer-state.preexisting.reg").write_text("stale", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "existing WER backup"):
            crash.emit_wer_plan(self.manifest, self.exe, self.root / "dumps", state_out, instructions_out)
        self.assertFalse(state_out.exists())
        self.assertFalse(instructions_out.exists())
        self.assertFalse((self.root / "wer-instructions.restore.ps1").exists())

    def test_wer_plan_rejects_all_artifact_path_collisions(self):
        state_out = self.root / "wer-state.json"
        setup_out = self.root / "wer-setup.ps1"
        restore_out = self.root / "wer-restore.ps1"
        backup_out = self.root / "wer-state.preexisting.reg"
        cases = (
            (state_out, state_out, restore_out, self.root / "dumps"),
            (state_out, setup_out, setup_out, self.root / "dumps"),
            (state_out, backup_out, restore_out, self.root / "dumps"),
            (state_out, setup_out, backup_out, self.root / "dumps"),
            (state_out, setup_out, restore_out, state_out),
            (state_out, setup_out, restore_out, setup_out),
            (state_out, setup_out, restore_out, restore_out),
            (state_out, setup_out, restore_out, backup_out),
        )
        for state, setup, restore, dump_dir in cases:
            with self.subTest(setup=setup.name, restore=restore.name, dump=dump_dir.name):
                with self.assertRaisesRegex(ValueError, "must all be different"):
                    crash.emit_wer_plan(
                        self.manifest,
                        self.exe,
                        dump_dir,
                        state,
                        setup,
                        restore_out=restore,
                    )

    def test_wer_plan_accepts_custom_restore_and_rejects_missing_parent(self):
        state_out = self.root / "wer-state.json"
        setup_out = self.root / "wer-setup.ps1"
        restore_out = self.root / "custom-restore.ps1"
        state = crash.emit_wer_plan(
            self.manifest,
            self.exe,
            self.root / "dumps",
            state_out,
            setup_out,
            restore_out=restore_out,
        )
        self.assertEqual(state["instructions"]["restore"], str(restore_out.resolve()))
        self.assertTrue(restore_out.is_file())

        missing_restore = self.root / "missing" / "restore.ps1"
        with self.assertRaisesRegex(ValueError, "Restore output parent"):
            crash.emit_wer_plan(
                self.manifest,
                self.exe,
                self.root / "other-dumps",
                self.root / "other-state.json",
                self.root / "other-setup.ps1",
                restore_out=missing_restore,
            )

    def test_validate_bundle_emits_verified_hash_report(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        self.assertEqual(report["status"], "validated")
        self.assertEqual(report["exact_build"]["sha256"], hashlib.sha256(self.exe.read_bytes()).hexdigest())
        self.assertEqual(report["capture"]["dump"]["sha256"], hashlib.sha256(self.dump.read_bytes()).hexdigest())
        self.assertEqual(report["capture"]["logs"][0]["sha256"], hashlib.sha256(self.log.read_bytes()).hexdigest())
        parsed = report["capture"]["dump"]["minidump"]
        self.assertEqual(parsed["architecture"], "x86")
        self.assertEqual(parsed["exception"]["code"], "0xC0000005")
        self.assertEqual(parsed["exception"]["address"], "0x401234")
        self.assertEqual(parsed["context"]["registers"]["eip"], "0x401234")
        self.assertEqual(parsed["main_module"]["name"], self.exe.name)
        self.assertEqual(parsed["main_module"]["base"], "0x400000")
        self.assertEqual(parsed["main_module"]["fault_rva"], "0x1234")
        self.assertEqual(parsed["main_module"]["selected_pe"]["timestamp"], self.PE_TIMESTAMP)
        self.assertEqual(parsed["main_module"]["selected_pe"]["size_of_image"], self.PE_SIZE_OF_IMAGE)
        self.assertEqual(parsed["main_module"]["selected_pe"]["checksum"], self.PE_CHECKSUM)
        self.assertEqual(parsed["main_module"]["correlation"]["checksum"], "verified")
        self.assertGreater(parsed["provenance"]["exception_stream_rva"], 0)
        self.assertGreater(parsed["provenance"]["module_list_stream_rva"], 0)

    def test_validate_bundle_rejects_missing_zero_mismatch_and_bad_dump(self):
        for artifact in ("missing", "zero", "mismatch", "bad-magic"):
            with self.subTest(artifact=artifact):
                self.dump.write_bytes(self.minidump())
                self.log.write_text("crash action: test\n", encoding="utf-8")
                self.write_manifest()
                if artifact == "missing":
                    self.dump.unlink()
                elif artifact == "zero":
                    self.dump.write_bytes(b"")
                elif artifact == "mismatch":
                    changed = bytearray(self.minidump())
                    changed[-1] ^= 0xFF
                    self.dump.write_bytes(changed)
                elif artifact == "bad-magic":
                    self.dump.write_bytes(b"NOPE" + b"changed")
                with self.assertRaises(ValueError):
                    crash.validate_bundle(self.manifest, self.exe, self.capture)

    def test_validate_bundle_rejects_truncated_or_out_of_bounds_minidump(self):
        out_of_bounds = bytearray(self.minidump())
        struct.pack_into("<I", out_of_bounds, 48, 0xFFFFFFFF)
        for data in (b"MDMP", self.minidump()[:32], bytes(out_of_bounds)):
            with self.subTest(size=len(data)):
                self.dump.write_bytes(data)
                self.write_manifest()
                with self.assertRaises(ValueError):
                    crash.validate_bundle(self.manifest, self.exe, self.capture)

    def test_validate_bundle_requires_exception_context_and_module_streams(self):
        cases = {}

        missing_exception = bytearray(self.minidump())
        struct.pack_into("<I", missing_exception, 44, 9)
        cases["missing exception stream"] = missing_exception

        missing_system_info = bytearray(self.minidump())
        struct.pack_into("<I", missing_system_info, 40, 9)
        cases["missing system-info stream"] = missing_system_info

        truncated_exception = bytearray(self.minidump())
        struct.pack_into("<I", truncated_exception, 48, 167)
        cases["truncated exception record"] = truncated_exception

        truncated_context = bytearray(self.minidump())
        exception_rva = struct.unpack_from("<I", truncated_context, 52)[0]
        struct.pack_into("<I", truncated_context, exception_rva + 160, 199)
        cases["truncated x86 context"] = truncated_context

        context_oob = bytearray(self.minidump())
        exception_rva = struct.unpack_from("<I", context_oob, 52)[0]
        struct.pack_into("<I", context_oob, exception_rva + 164, len(context_oob) - 8)
        cases["out-of-bounds context RVA"] = context_oob

        missing_modules = bytearray(self.minidump())
        struct.pack_into("<I", missing_modules, 56, 9)
        cases["missing module-list stream"] = missing_modules

        truncated_module = bytearray(self.minidump())
        struct.pack_into("<I", truncated_module, 60, 111)
        cases["truncated module record"] = truncated_module

        module_count_oob = bytearray(self.minidump())
        module_rva = struct.unpack_from("<I", module_count_oob, 64)[0]
        struct.pack_into("<I", module_count_oob, module_rva, 2)
        cases["out-of-bounds nested module record"] = module_count_oob

        module_name_oob = bytearray(self.minidump())
        module_rva = struct.unpack_from("<I", module_name_oob, 64)[0]
        struct.pack_into("<I", module_name_oob, module_rva + 24, len(module_name_oob) - 2)
        cases["out-of-bounds module-name RVA"] = module_name_oob

        module_name_length_oob = bytearray(self.minidump())
        module_rva = struct.unpack_from("<I", module_name_length_oob, 64)[0]
        module_name_rva = struct.unpack_from("<I", module_name_length_oob, module_rva + 24)[0]
        struct.pack_into("<I", module_name_length_oob, module_name_rva, 0x1000)
        cases["out-of-bounds module-name record"] = module_name_length_oob

        for label, data in cases.items():
            with self.subTest(label=label):
                self.dump.write_bytes(data)
                self.write_manifest()
                with self.assertRaises(ValueError):
                    crash.validate_bundle(self.manifest, self.exe, self.capture)

    def test_validate_bundle_rejects_fault_or_module_identity_mismatch(self):
        cases = {
            "fault outside selected module": self.minidump(
                exception_address=self.MODULE_BASE + self.PE_SIZE_OF_IMAGE,
            ),
            "context EIP disagrees with exception": self.minidump(
                context_eip=self.EXCEPTION_ADDRESS + 1,
            ),
            "context is not marked x86": self.minidump(context_flags=0x00100007),
            "module basename mismatch": self.minidump(module_name="OtherGame.exe"),
            "PE timestamp mismatch": self.minidump(module_timestamp=self.PE_TIMESTAMP + 1),
            "PE image-size mismatch": self.minidump(module_size=self.PE_SIZE_OF_IMAGE + 0x1000),
            "PE checksum mismatch": self.minidump(module_checksum=self.PE_CHECKSUM + 1),
            "ambiguous duplicate main module": self.minidump(duplicate_main_module=True),
        }
        for label, data in cases.items():
            with self.subTest(label=label):
                self.dump.write_bytes(data)
                self.write_manifest()
                with self.assertRaises(ValueError):
                    crash.validate_bundle(self.manifest, self.exe, self.capture)

    def test_validate_bundle_rejects_non_x86_selected_pe(self):
        self.exe.write_bytes(self.pe32(machine=0x8664))
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "x86|machine|PE32"):
            crash.validate_bundle(self.manifest, self.exe, self.capture)

    def test_validate_bundle_rejects_truncated_selected_pe_section(self):
        image = bytearray(self.pe32())
        struct.pack_into("<I", image, 0x178 + 20, 0xFFFFFFFF)
        self.exe.write_bytes(image)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "out-of-bounds PE section"):
            crash.validate_bundle(self.manifest, self.exe, self.capture)

    def test_validate_bundle_marks_absent_dump_checksum_unavailable(self):
        self.dump.write_bytes(self.minidump(module_checksum=0))
        self.write_manifest()
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        correlation = report["capture"]["dump"]["minidump"]["main_module"]["correlation"]
        self.assertEqual(correlation["checksum"], "unavailable")

    def test_validate_bundle_rejects_missing_or_zero_log(self):
        self.log.unlink()
        with self.assertRaises(ValueError):
            crash.validate_bundle(self.manifest, self.exe, self.capture)
        self.log.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "zero-byte"):
            crash.validate_bundle(self.manifest, self.exe, self.capture)

    def test_validate_bundle_rejects_duplicate_dump_and_log_paths(self):
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["capture"]["logs"].append(dict(manifest["capture"]["logs"][0]))
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate capture artifact"):
            crash.validate_bundle(self.manifest, self.exe, self.capture)

        manifest["capture"]["logs"] = [dict(manifest["capture"]["dump"])]
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate capture artifact"):
            crash.validate_bundle(self.manifest, self.exe, self.capture)

    def ida_inputs(self):
        return {
            "stack_frames": [
                json.dumps({"index": 0, "address": "0x401234", "module": "Virtual Families 2 - Debugger Test.exe", "module_base": "0x400000", "rva": "0x1234"}),
                json.dumps({"index": 1, "address": "0x402000", "module": "Virtual Families 2 - Debugger Test.exe", "module_base": "0x400000", "rva": "0x2000"}),
            ],
        }

    def test_emit_ida_json_requires_complete_consistent_record(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        report_path = self.root / "capture-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        output = self.root / "ida-crash.json"
        record = crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, output, **self.ida_inputs())
        self.assertEqual(record["schema"], crash.IDA_SCHEMA)
        self.assertEqual(record["exception"]["code"], "0xC0000005")
        self.assertEqual(record["fault_module"]["rva"], "0x1234")
        self.assertEqual(record["registers"]["eip"], "0x401234")
        self.assertEqual(record["provenance"]["main_module"], "dump ModuleListStream correlated with exact-build selected PE")
        self.assertEqual(record["fault_module"]["timestamp"], self.PE_TIMESTAMP)
        self.assertEqual(record["fault_module"]["size_of_image"], self.PE_SIZE_OF_IMAGE)
        self.assertEqual(record["fault_module"]["checksum"], self.PE_CHECKSUM)
        self.assertEqual(record["fault_module"]["selected_pe"]["basename"], self.exe.name)
        self.assertEqual(record["fault_module"]["correlation"]["checksum"], "verified")
        self.assertEqual(
            record["provenance"]["stream_locations"],
            report["capture"]["dump"]["minidump"]["provenance"],
        )
        self.assertIn("SHA-256", record["provenance"]["dump_identity_limit"])
        self.assertEqual(record["exact_build"]["sha256"], report["exact_build"]["sha256"])
        self.assertEqual(record["capture"]["dump"]["sha256"], report["capture"]["dump"]["sha256"])
        self.assertTrue(output.is_file())

    def test_emit_ida_json_rejects_report_bound_to_different_executable(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        report_path = self.root / "capture-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        other = self.root / "other.exe"
        other.write_bytes(self.exe.read_bytes())
        forged = json.loads(report_path.read_text(encoding="utf-8"))
        forged["exact_build"] = {
            "path": str(other.resolve()),
            "size": other.stat().st_size,
            "sha256": hashlib.sha256(other.read_bytes()).hexdigest(),
        }
        report_path.write_text(json.dumps(forged), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "(does not match explicit manifest|selected main-module basename)"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "forged.json", **self.ida_inputs())

    def test_emit_ida_json_rejects_tampered_recorded_dump_provenance(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        report["capture"]["dump"]["minidump"]["exception"]["address"] = "0x401235"
        report_path = self.root / "capture-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "provenance no longer matches"):
            crash.emit_ida_json(
                self.manifest,
                self.exe,
                self.capture,
                report_path,
                self.root / "tampered-provenance.json",
                **self.ida_inputs(),
            )

    def test_emit_ida_json_rejects_inconsistent_or_incomplete_inputs(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        report_path = self.root / "capture-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        base = self.ida_inputs()
        with self.assertRaisesRegex(ValueError, "stack-frame"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "missing-frame.json", **dict(base, stack_frames=[]))
        invalid_frame = [json.dumps({"index": 0, "address": "0x401235", "module": self.exe.name, "module_base": "0x400000", "rva": "0x1234"})]
        with self.assertRaisesRegex(ValueError, "Stack frame address"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "bad-frame.json", stack_frames=invalid_frame)
        overflow_frame = [json.dumps({"index": 0, "address": "0x100000000", "module": self.exe.name, "module_base": "0x400000", "rva": "0x1234"})]
        with self.assertRaisesRegex(ValueError, "unsigned 32-bit"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "overflow-frame.json", stack_frames=overflow_frame)
        non_contiguous = [base["stack_frames"][0], base["stack_frames"][1].replace('"index": 1', '"index": 2')]
        with self.assertRaisesRegex(ValueError, "contiguous"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "non-contiguous.json", stack_frames=non_contiguous)
        self.assertEqual(crash.parse_uint32("0xFFFFFFFF", "boundary", allow_zero=True), 0xFFFFFFFF)

    def test_ida_emission_rechecks_report_artifacts(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        report_path = self.root / "capture-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        changed = bytearray(self.minidump())
        changed[-1] ^= 0xFF
        self.dump.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "dump no longer matches"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "stale.json", **self.ida_inputs())


if __name__ == "__main__":
    unittest.main()
