# Offline VF2 Patcher

The offline patcher is the new release direction for VF2 mod builds. Instead of
distributing modified executables, releases should distribute patch data and a
simple patcher that edits a user-provided vanilla VF2 PC install on disk.

The first implementation is `work/offline_vf2_patcher.py`. It applies byte
patches from JSON manifests and can restore files from its own backups.

## Goals

- Verify the original VF2 files before patching.
- Refuse to patch if the target bytes do not match the manifest.
- Create a backup before writing any patched file.
- Write machine-readable patch and restore logs.
- Avoid runtime injection, process memory editing, obfuscation, packers, and
  admin requirements.
- Prefer data, asset, and native table patch records over executable byte
  patches whenever possible.

## Apply

```powershell
& "C:\Path\To\Python\python.exe" work\offline_vf2_patcher.py apply `
  --game-dir "C:\Games\Virtual Families 2" `
  --manifest patches\vf2-b62.json
```

Use `--dry-run` to validate hashes and expected bytes without writing files.
Use `--backup-dir` and `--log` to control where the backup and patch log are
written.

## Restore

```powershell
& "C:\Path\To\Python\python.exe" work\offline_vf2_patcher.py restore `
  --backup-dir "C:\Games\Virtual Families 2\.vf2_patch_backups\20260702_example"
```

The restore command reads `vf2_patch_backup_manifest.json` from the backup
folder and copies the original files back.

## Manifest Contract

```json
{
  "manifest_version": 1,
  "name": "VF2 example patch",
  "target_files": [
    {
      "path": "Virtual Families 2.exe",
      "sha256": "expected lowercase sha256",
      "size": 123456,
      "file_version": "0.0.0.0",
      "pe_timestamp": "0x12345678"
    }
  ],
  "patches": [
    {
      "file_path": "Virtual Families 2.exe",
      "offset": "0x1234",
      "expected_original_bytes": "AA BB CC DD",
      "replacement_bytes": "11 22 33 44",
      "note": "Explain why this patch exists."
    }
  ]
}
```

`target_files` is required, and at least one `.exe` target must include a
`sha256` value so the user-provided vanilla executable is verified before any
patch is written. `size`, `file_version`, `product_version`, and `pe_timestamp`
are validated when present; version and PE timestamp checks are supplemental to
the executable hash.

Each byte patch must be length-preserving. Length-changing edits should be
represented as asset/table replacement work or by adding a future manifest
record type with its own safety rules. Overlapping byte patches are refused.

## Release Notes

The patcher itself is source-only and uses Python's standard library. Release
packaging should keep it transparent: no packers, no obfuscation, no memory
editing helper, and no admin-only install flow. Published releases should
include hashes and a false-positive submission trail for antivirus vendors when
needed.
