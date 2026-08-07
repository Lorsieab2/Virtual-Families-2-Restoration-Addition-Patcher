# Crash-capture readiness

`work/vf2_crash_capture.py` is a workspace-local, fail-closed preparation and
validation tool. It does not launch VF2, change patch settings, read the
registry, or write registry keys.

## Exact-build manifest

Use a separate manifest for the executable selected for the crash test. Do not
reuse a patcher manifest implicitly:

```json
{
  "schema": "vf2-crash-capture/v1",
  "executable": {
    "path": "C:/exact/path/to/selected.exe",
    "size": 1234567,
    "sha256": "lowercase-64-character-sha256"
  },
  "capture": {
    "dump": {
      "path": "crash.dmp",
      "size": 12345,
      "sha256": "lowercase-64-character-sha256"
    },
    "logs": [
      {
        "path": "ldwLog.txt",
        "size": 123,
        "sha256": "lowercase-64-character-sha256"
      }
    ]
  }
}
```

The executable path must be absolute, and every recorded size must be positive.
The capture section is required for bundle validation; it is not required for
the executable-only check or WER planning. Paths under `capture` are safe,
relative paths inside the capture directory. The dump must be a non-empty
Windows minidump with a complete `MINIDUMP_HEADER` (MDMP signature, version
low word `0xA793`, nonzero stream count), a bounded stream directory, and
in-file stream locations. At least one non-empty log is required. All recorded
SHA-256 values are checked against the bytes on disk.

## Commands

Run from the repository root with the workspace Python runtime:

```powershell
python work/vf2_crash_capture.py verify-exe `
  --manifest C:/exact/path/to/exact-build.json `
  --exe C:/exact/path/to/selected.exe
```

Generate WER LocalDumps setup and restore instructions. This writes only the
requested JSON state and text instruction files; it never executes the shown
registry commands:

```powershell
python work/vf2_crash_capture.py emit-wer-plan `
  --manifest C:/exact/path/to/exact-build.json `
  --exe C:/exact/path/to/selected.exe `
  --dump-dir C:/exact/path/to/crash-dumps `
  --state-out C:/exact/path/to/wer-state.json `
  --instructions-out C:/exact/path/to/wer-instructions.ps1
```

The plan targets only the per-executable `HKCU\Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\<selected.exe>` leaf. The generator and generated instructions both refuse any pre-existing backup file, regardless of whether the registry leaf exists. Review and export any pre-existing leaf state before applying the instructions. Restore imports that exact backup, or removes only that exact leaf when it did not previously exist; the parent `LocalDumps` key is never removed.

Validate a captured bundle against the expected dump/log records:

```powershell
python work/vf2_crash_capture.py validate-bundle `
  --manifest C:/exact/path/to/exact-build-with-capture.json `
  --exe C:/exact/path/to/selected.exe `
  --bundle-dir C:/exact/path/to/capture `
  --report-out C:/exact/path/to/capture-report.json
```

Emit the IDA-consumable record only from a successful, still-current bundle
report. The explicit manifest and bundle are revalidated, and the supplied
report must exactly match that fresh identity. Every exception, module, register, and stack-frame field is required;
the module and every frame must satisfy `address = base + RVA`, and `eip` must
equal the exception address. Stack frames use JSON objects with `index`,
`address`, `module`, `module_base`, and `rva`:

```powershell
python work/vf2_crash_capture.py emit-ida-json `
  --manifest C:/exact/path/to/exact-build-with-capture.json `
  --exe C:/exact/path/to/selected.exe `
  --bundle-dir C:/exact/path/to/capture `
  --bundle-report C:/exact/path/to/capture-report.json `
  --output C:/exact/path/to/ida-crash.json `
  --exception-code 0xC0000005 `
  --exception-address 0x<required-address> `
  --module C:/exact/path/to/module.exe `
  --module-base 0x<required-base> `
  --module-rva 0x<required-rva> `
  --register eax=0x<value> --register ebx=0x<value> `
  --register ecx=0x<value> --register edx=0x<value> `
  --register esi=0x<value> --register edi=0x<value> `
  --register ebp=0x<value> --register esp=0x<value> `
  --register eip=0x<exception-address> --register eflags=0x<value> `
  --stack-frame '{"index":0,"address":"0x<address>","module":"<module>","module_base":"0x<base>","rva":"0x<rva>"}'
```

The resulting JSON preserves the verified executable, dump, and log hashes in
plain hex-string form suitable for IDA-side notes and later symbolization.
All x86 addresses, RVAs, and register values must fit `0x00000000` through
`0xFFFFFFFF`. The
tool rejects missing, zero-byte, stale, malformed, or mismatched artifacts
before producing any report or IDA record.
