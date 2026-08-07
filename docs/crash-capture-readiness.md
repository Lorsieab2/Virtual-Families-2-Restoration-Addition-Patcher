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
relative paths inside the capture directory. At least one non-empty log is
required. All recorded SHA-256 values are checked against the bytes on disk.

The selected executable must be a bounded PE32 x86 image. Bundle validation
requires a non-empty Windows minidump with a complete `MINIDUMP_HEADER` (MDMP
signature, version low word `0xA793`, nonzero stream count), a bounded stream
directory, and in-file stream locations. It also requires exactly one bounded
x86 `ExceptionStream` with its referenced thread context and a bounded
`ModuleListStream`, including every nested module record and module-name RVA.
The exception address must fall inside the selected main module. That module is
correlated with the selected executable by case-insensitive basename, PE
timestamp, `SizeOfImage`, and PE checksum when the checksum is available. A
missing, duplicate, truncated, out-of-bounds, wrong-architecture,
or contradictory required record is rejected.

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
  --instructions-out C:/exact/path/to/wer-setup.ps1 `
  --restore-out C:/exact/path/to/wer-restore.ps1
```

The plan targets only the per-executable `HKCU\Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\<selected.exe>` leaf. The generator and generated instructions both refuse any pre-existing backup file, regardless of whether the registry leaf exists. Review and export any pre-existing leaf state before applying the instructions. Restore imports that exact backup, or removes only that exact leaf when it did not previously exist; the parent `LocalDumps` key is never removed.
Run setup once, reproduce and capture the crash, and then run the separate
restore script. Restore removes the modified executable leaf before importing a
pre-existing backup so setup-added values cannot survive registry merge
behavior.

Validate a captured bundle against the expected dump/log records:

```powershell
python work/vf2_crash_capture.py validate-bundle `
  --manifest C:/exact/path/to/exact-build-with-capture.json `
  --exe C:/exact/path/to/selected.exe `
  --bundle-dir C:/exact/path/to/capture `
  --report-out C:/exact/path/to/capture-report.json
```

The successful report stores the bounded, dump-derived facts under
`capture.dump.minidump`, including the exception, x86 context/registers,
correlated main module, fault RVA, and source stream/record RVAs.

Emit the IDA-consumable record only from a successful, still-current bundle
report. The explicit manifest and bundle are revalidated, and the supplied
report must exactly match that fresh identity. The exception code and address,
selected module base and computed RVA, and x86 register context are consumed
from the validated minidump facts rather than accepted as replacement command
line values. At least one analyst-supplied stack frame remains required. Each
frame must satisfy `address = base + RVA` and uses a JSON object with `index`,
`address`, `module`, `module_base`, and `rva`:

```powershell
python work/vf2_crash_capture.py emit-ida-json `
  --manifest C:/exact/path/to/exact-build-with-capture.json `
  --exe C:/exact/path/to/selected.exe `
  --bundle-dir C:/exact/path/to/capture `
  --bundle-report C:/exact/path/to/capture-report.json `
  --output C:/exact/path/to/ida-crash.json `
  --stack-frame '{"index":0,"address":"0x<address>","module":"<module>","module_base":"0x<base>","rva":"0x<rva>"}'
```

The resulting JSON preserves the verified executable, dump, and log hashes in
plain hex-string form suitable for IDA-side notes and later symbolization. It
also records the dump-derived exception/thread-context and selected-module
facts, the selected PE identity used for correlation, and the validation report
provenance from which those facts were consumed. Its provenance distinguishes
those parsed facts from the analyst-supplied stack frames. All x86 addresses,
RVAs, and register values must fit `0x00000000` through `0xFFFFFFFF`. The tool
rejects missing, zero-byte, stale, malformed, or mismatched artifacts before
producing any report or IDA record.

## Remaining dump-identity limit

The exact-build manifest SHA-256 authenticates the selected executable on disk;
it remains a separate gate from minidump validation. A normal minidump does not
contain the complete loaded executable bytes or their SHA-256. Matching the
dump module's basename, PE timestamp, `SizeOfImage`, and available checksum to
the selected executable is strong structural correlation, but it is not
cryptographic proof that the process loaded those exact bytes. Preserve this
limitation in crash reports and do not describe the dump-to-EXE relationship as
an exact hash match unless an independent captured-module hash establishes it.
