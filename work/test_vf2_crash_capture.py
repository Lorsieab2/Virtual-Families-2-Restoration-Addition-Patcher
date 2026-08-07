import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import vf2_crash_capture as crash


class Vf2CrashCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.exe = self.root / "Virtual Families 2 - Debugger Test.exe"
        self.exe.write_bytes(b"VF2 exact executable bytes\x00\x01")
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

    def minidump(self, payload=b"DATA", *, declared_size=None):
        declared_size = len(payload) if declared_size is None else declared_size
        header = struct.pack("<4sIIIIIQ", b"MDMP", 0xA793, 1, 32, 0, 0, 0)
        directory = struct.pack("<III", 7, declared_size, 44)
        return header + directory + payload

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

    def test_validate_bundle_emits_verified_hash_report(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        self.assertEqual(report["status"], "validated")
        self.assertEqual(report["exact_build"]["sha256"], hashlib.sha256(self.exe.read_bytes()).hexdigest())
        self.assertEqual(report["capture"]["dump"]["sha256"], hashlib.sha256(self.dump.read_bytes()).hexdigest())
        self.assertEqual(report["capture"]["logs"][0]["sha256"], hashlib.sha256(self.log.read_bytes()).hexdigest())

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
                    self.dump.write_bytes(self.minidump(b"changed"))
                elif artifact == "bad-magic":
                    self.dump.write_bytes(b"NOPE" + b"changed")
                with self.assertRaises(ValueError):
                    crash.validate_bundle(self.manifest, self.exe, self.capture)

    def test_validate_bundle_rejects_truncated_or_out_of_bounds_minidump(self):
        for data in (b"MDMP", self.minidump()[:32], self.minidump(declared_size=5)):
            with self.subTest(size=len(data)):
                self.dump.write_bytes(data)
                self.write_manifest()
                with self.assertRaises(ValueError):
                    crash.validate_bundle(self.manifest, self.exe, self.capture)

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
            "exception_code": "0xC0000005",
            "exception_address": "0x401234",
            "module": "Virtual Families 2 - Debugger Test.exe",
            "module_base": "0x400000",
            "module_rva": "0x1234",
            "registers": [f"{name}={value}" for name, value in {
                "eax": "0x1", "ebx": "0x2", "ecx": "0x3", "edx": "0x4",
                "esi": "0x5", "edi": "0x6", "ebp": "0x700000", "esp": "0x700100",
                "eip": "0x401234", "eflags": "0x202",
            }.items()],
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
        self.assertEqual(record["exact_build"]["sha256"], report["exact_build"]["sha256"])
        self.assertEqual(record["capture"]["dump"]["sha256"], report["capture"]["dump"]["sha256"])
        self.assertTrue(output.is_file())

    def test_emit_ida_json_rejects_report_bound_to_different_executable(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        report_path = self.root / "capture-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        other = self.root / "other.exe"
        other.write_bytes(b"different exact build")
        forged = json.loads(report_path.read_text(encoding="utf-8"))
        forged["exact_build"] = {
            "path": str(other.resolve()),
            "size": other.stat().st_size,
            "sha256": hashlib.sha256(other.read_bytes()).hexdigest(),
        }
        report_path.write_text(json.dumps(forged), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match explicit manifest"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "forged.json", **self.ida_inputs())

    def test_emit_ida_json_rejects_inconsistent_or_incomplete_inputs(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        report_path = self.root / "capture-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        base = self.ida_inputs()
        bad_address = dict(base, exception_address="0x401235")
        with self.assertRaisesRegex(ValueError, "Exception address"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "bad.json", **bad_address)
        bad_eip = dict(base, registers=[item.replace("eip=0x401234", "eip=0x401235") for item in base["registers"]])
        with self.assertRaisesRegex(ValueError, "register eip"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "bad-eip.json", **bad_eip)
        with self.assertRaisesRegex(ValueError, "Missing required registers"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "missing-register.json", **dict(base, registers=base["registers"][:-1]))
        with self.assertRaisesRegex(ValueError, "stack-frame"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "missing-frame.json", **dict(base, stack_frames=[]))
        for field, value in (
            ("exception_address", "0x100000000"),
            ("module_rva", "0x100000000"),
            ("registers", [item.replace("eax=0x1", "eax=0x100000000") for item in base["registers"]]),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "unsigned 32-bit"):
                crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / f"bad-{field}.json", **dict(base, **{field: value}))
        with self.assertRaisesRegex(ValueError, "exceeds unsigned 32-bit"):
            crash.emit_ida_json(
                self.manifest,
                self.exe,
                self.capture,
                report_path,
                self.root / "overflow.json",
                **dict(base, exception_address="0xFFFFFFFF", module_base="0xFFFFFFFF", module_rva="0x1"),
            )
        self.assertEqual(crash.parse_uint32("0xFFFFFFFF", "boundary", allow_zero=True), 0xFFFFFFFF)

    def test_ida_emission_rechecks_report_artifacts(self):
        report = crash.validate_bundle(self.manifest, self.exe, self.capture)
        report_path = self.root / "capture-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        self.dump.write_bytes(self.minidump(b"changed after report"))
        with self.assertRaisesRegex(ValueError, "dump no longer matches"):
            crash.emit_ida_json(self.manifest, self.exe, self.capture, report_path, self.root / "stale.json", **self.ida_inputs())


if __name__ == "__main__":
    unittest.main()
