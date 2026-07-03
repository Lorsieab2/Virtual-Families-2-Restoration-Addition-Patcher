# Offline VF2 Patcher

The offline patcher is the new release direction for VF2 mod builds. Instead of
distributing modified executables, releases should distribute patch data and a
simple patcher that edits a user-provided vanilla VF2 PC install on disk.

The first implementation is `work/offline_vf2_patcher.py`. It applies byte
patches and file/asset patch records from JSON manifests, then can restore
files from its own backups.

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
  --manifest patches\vf2-b62.json `
  --enable holiday_furniture `
  --disable holiday_outfits
```

Use `--dry-run` to validate target hashes, expected bytes, and asset payload
hashes without writing files. Use `--backup-dir` and `--log` to control where
the backup and patch log are written. Use `--enable`, `--disable`,
`--enable-all`, and `--disable-all` to choose manifest-declared feature
settings before patching.

List the settings exposed by a manifest:

```powershell
& "C:\Path\To\Python\python.exe" work\offline_vf2_patcher.py settings `
  --manifest patches\vf2-b62.json
```

## GUI

The patcher also has a source-only Tkinter GUI:

```powershell
& "C:\Path\To\Python\python.exe" work\offline_vf2_patcher_gui.py
```

The GUI is a wrapper around the same patcher functions used by the CLI. It lets
the user choose the vanilla game folder, choose a JSON manifest, review
manifest-declared settings as checkboxes, run a dry run, apply the selected
patch set, and restore from a patcher backup. Checkboxes are generated from the
manifest, so new optional components such as Holiday furniture, Holiday outfits,
mobile-exclusive furniture, or future feature groups do not require GUI code
changes.

## Restore

```powershell
& "C:\Path\To\Python\python.exe" work\offline_vf2_patcher.py restore `
  --backup-dir "C:\Games\Virtual Families 2\.vf2_patch_backups\20260702_example"
```

The restore command reads `vf2_patch_backup_manifest.json` from the backup
folder, copies original files back, and removes files that the patcher created
when the original target did not exist.

## Manifest Contract

```json
{
  "manifest_version": 1,
  "name": "VF2 example patch",
  "settings": [
    {
      "id": "holiday_furniture",
      "label": "Add Holiday furniture",
      "description": "Adds mobile holiday furniture to the PC build.",
      "default": false
    },
    {
      "id": "holiday_outfits",
      "label": "Add Holiday outfits",
      "description": "Enables folder-backed holiday outfit rows.",
      "default": false
    },
    {
      "id": "outfit_store_expansion",
      "label": "Add expanded Outfit store",
      "description": "Adds generated outfit rows, copied stock sprite sheets, icons, and independent outfit tray items.",
      "default": true
    },
    {
      "id": "mobile_furniture",
      "label": "Add additional mobile-exclusive furniture",
      "description": "Adds non-holiday mobile-exclusive furniture.",
      "default": true
    },
    {
      "id": "vf3_tv_animation_graphics",
      "label": "Fix VF3 TV animation graphics",
      "description": "Adds private VF3 TV animation strips and native table wiring.",
      "default": true
    },
    {
      "id": "holiday_ornaments_collection",
      "label": "Add Holiday Ornaments collection",
      "description": "Adds mobile Holiday Ornament yard collectibles, collection art, and goals.",
      "default": true
    }
  ],
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
      "requires": ["holiday_furniture"],
      "note": "Explain why this patch exists."
    }
  ],
  "asset_patches": [
    {
      "file_path": "Images/VF3LargeFlatScreenTVAnim.png",
      "source_path": "payload/Images/VF3LargeFlatScreenTVAnim.png",
      "source_sha256": "expected lowercase sha256 of the payload file",
      "source_size": 12345,
      "requires": ["vf3_tv_animation_graphics"],
      "note": "B65 scaled private VF3 Large TV animation strip."
    }
  ]
}
```

`target_files` is required, and at least one `.exe` target must include a
`sha256` value so the user-provided vanilla executable is verified before any
patch is written. `size`, `file_version`, `product_version`, and `pe_timestamp`
are validated when present; version and PE timestamp checks are supplemental to
the executable hash.

`runtime_requirements` is optional but should be included by VF2 release
manifests. It lets the patcher verify that the selected game directory is a
complete vanilla runtime folder before any byte or asset patches are written:

```json
{
  "runtime_requirements": {
    "required_files": [
      "ldw.ini",
      "wc.dat",
      "Images/loading.jpg",
      "Images/TVAnimBig.png",
      "Images/TVAnimBigE.png",
      "Images/TVAnimSmall.png",
      "Images/TVAnimSmallE.png"
    ],
    "required_dirs": [
      { "path": "Images", "min_files": 1000 },
      { "path": "Sounds", "min_files": 300 }
    ]
  }
}
```

Directory and file requirement rows can also include `requires`/`settings` like
patch records. Use this to prevent applying the mod to an EXE-only folder or a
partial copied build that would later fail with missing-image or missing-DLL
launch errors.

Each byte patch must be length-preserving. Length-changing edits should be
represented as asset/table replacement work or by adding a future manifest
record type with its own safety rules. Overlapping byte patches are refused.

`asset_patches` copy files from a patch bundle into the user-provided game
folder after verifying the payload file's `source_sha256`. `source_path` is
relative to the manifest folder; `file_path` is relative to the game folder.
Asset records can create new files, which restore later removes. If an asset
target already exists, the patcher allows it only when it already matches the
payload, when `expected_target_sha256` matches, or when
`overwrite_existing=true` is explicit. This keeps private files such as
`Images/VF3LargeFlatScreenTVAnim*.png`,
`Images/VF3SmallFlatScreenTVAnim*.png`, and
`Images/FathersFavoriteTVAnim*.png` patchable without touching stock
`TVAnimBig*.png` or `TVAnimSmall*.png`.

Outfit-store sprite payloads should follow the same rule: include the six
villager sheets as manifest-relative `asset_patches` that copy into the target
game's `Images/` folder. The patched game must read the copied
`Images/female_*00.png` and `Images/male_*00.png` files, never an absolute
external `originalimages` source folder.

## Toggleable Settings

Settings let a release manifest expose optional components before patching, such
as:

- `holiday_furniture` - Add Holiday furniture.
- `holiday_outfits` - Add Holiday outfits.
- `outfit_store_expansion` - Add generated outfit rows, copied villager sprite
  sheets, icons, and independent outfit tray items.
- `mobile_furniture` - Add additional mobile-exclusive furniture.
- `vf3_tv_animation_graphics` - Fix VF3 TV animation graphics.
- `settings_evict_button` - Re-enable the Settings menu Evict button.
- `holiday_ornaments_collection` - Add mobile Holiday Ornament yard
  collectibles, collection screen art, and Goals entries.

Patch records, asset records, and target-file checks can include `requires`,
`settings`, or `setting`. A record is active only when all required settings
are enabled. If a record has no setting requirement, it is always active.

Settings default to off unless the manifest sets `"default": true`. Command-line
flags can override those defaults:

```powershell
--enable holiday_furniture
--disable holiday_outfits
--enable holiday_furniture,mobile_furniture,vf3_tv_animation_graphics,settings_evict_button,holiday_ornaments_collection
--enable-all
--disable-all
```

Patch logs include the available, enabled, and disabled settings used for the
run.

## Release Notes

The patcher itself is source-only and uses Python's standard library. Release
packaging should keep it transparent: no packers, no obfuscation, no memory
editing helper, and no admin-only install flow. Published releases should
include hashes and a false-positive submission trail for antivirus vendors when
needed.
