# Offline VF2 Patcher

The offline patcher is the new release direction for VF2 mod builds. Instead of
distributing modified executables, releases should distribute patch data and a
simple patcher that edits a user-provided vanilla VF2 PC install on disk.

The current display name is `Virtual Families 2 Restoration/Addition Patcher`.
The GUI launcher is `Launch_GUI.bat`. Exported bundles intentionally do not
include a prebuilt `Launch GUI.lnk` shortcut because Windows shortcut targets
are path-specific and can break after ZIP extraction. The patcher was created
with Codex AI in collaboration with Lorsieab2.

The first implementation is `work/offline_vf2_patcher.py`. It applies byte
patches and file/asset patch records from JSON manifests, then can restore
files from its own backups.

## Goals

- Verify the original VF2 files before patching.
- Verify the selected folder is an official LDW website-style Virtual Families
  2 install before creating an output folder, backup, or changed file.
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

The apply command can also take the original executable directly. In that mode
the game directory is inferred from the EXE's parent folder. Current full
bundle manifests declare an output folder, so the patcher copies the vanilla
folder to a separate modded sibling folder and writes changed files there:

```powershell
& "C:\Path\To\Python\python.exe" work\offline_vf2_patcher.py apply `
  --exe "C:\Games\Virtual Families 2\Virtual Families 2.exe" `
  --manifest patches\vf2-b103-full-payload\manifest.json
```

Use `--output-dir` to override the manifest's default modded output folder. For
B105 bundles, the default output folder is `VF2-B105-Modded`, and the modded
executable is named `Virtual Families 2 - Modded B105.exe` so it is obvious
that it is not a vanilla executable. The modded save folder follows that
executable name under `Documents/LDW/Virtual Families 2 - Modded B105`.

Use `--dry-run` to validate target hashes, expected bytes, and asset payload
hashes without writing files. Use `--backup-dir` and `--log` to control where
the backup and patch log are written. Use `--enable`, `--disable`,
`--enable-all`, and `--disable-all` to choose manifest-declared feature
settings before patching.

ELI5: Dry Run validates that the patcher's working. It checks that the selected
Virtual Families 2 folder looks official, checks that the EXE is the expected
one, checks that the patch instructions and payload files match their hashes,
then stops. It does not actually change or write files. Use it when you want to
ask, "Would this patch work?" before actually applying it. If no custom `--log`
path is selected, dry-run and pre-write failure logs are written beside
`manifest.json` so the vanilla game folder stays untouched.

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

Bundle exports now ship readable batch launchers instead of a compiled patcher
EXE. `Launch_GUI.bat` starts the GUI with adjacent `manifest.json`. Prebuilt
`.lnk` shortcuts are not shipped because they can point to the wrong path after
the ZIP is moved or extracted.

The GUI auto-loads adjacent `manifest.json` but does not open the vanilla-folder
picker automatically. The user selects their own vanilla Virtual Families 2
installation folder manually, and the patcher does not look for or assume a
hardcoded local install path.

The GUI auto-populates the modded output folder from the selected vanilla game
folder and manifest `output.default_folder_name`. The Enable/Disable Patches
button uses green bold text, manifest descriptions support `**bold**` markup,
and description blocks resize to keep their full text visible. The completion
popup separates enabled patches from disabled/restored patches and keeps
path/save guidance fixed while the modified-file log is the only scrollable
area. The Vanilla Game Folder Path, Modified Game Folder Path, and Modified
Game Saves Folder Path are shown as bold blue clickable paths.

The GUI groups manifest settings by `category` and provides buttons to enable
all Main, Optional, or Experimental settings without changing unrelated
checkboxes:

| Category | GUI color | Intended settings |
| --- | --- | --- |
| `main` | Green | Core patches, mobile-exclusive furniture, Holiday furniture, and Holiday outfits. |
| `optional` | Black | Invisible Furniture graphics modes, optional visual swaps, custom maps, LDW Posters/Paintings, and Colorful Couches. |
| `experimental` | Red | Settings Evict, Island Events, and anything not 100% confirmed working and crash-free. |

Bundles can include `patcher_icon.png` and `patcher_icon.ico`. The GUI uses the
PNG as the literal picture beside the bold title and uses the ICO/PNG for the
window icon when Tk can load them. No compiled launcher EXE or prebuilt `.lnk`
shortcut is shipped in B105 bundles.

After a successful GUI apply, the patcher shows a completion popup listing the
enabled patch settings, disabled/restored patch settings, altered files, modded
game folder, and expected modded save folder. The save folder is derived from
the modded EXE name:
`Documents/LDW/(name of modded Virtual Families 2 exe)`. Existing vanilla saves
stay in the original save folder unless the user manually copies them.

B105 bundles prefer native byte/table patch records over a full modded EXE
payload. That keeps the distributed ZIP from containing a ready-made modified
game executable while still letting the patcher create a clearly named modded
EXE after validating the user's vanilla install. If a future feature cannot be
represented safely as byte/table records, the exporter can still create a
verified `core_executable` payload for testing, but that is not the preferred
release shape.

## Bundle Exporter

`work/export_offline_patch_bundle.py` exports a generated build folder into the
offline patcher bundle shape:

```powershell
& "C:\Path\To\Python\python.exe" work\export_offline_patch_bundle.py `
  --build-dir outputs\VF2-Mobile-Furniture-With-Island-Events-B93-Holiday-Outfit-Body-Apply `
  --out-dir outputs\Offline-Patch-Bundles\B93-asset-preview `
  --force
```

The exporter writes `manifest.json` and a manifest-relative `payload/` folder.
It compares build assets against `work/vanilla_runtime_payload`, skips
vanilla-identical files, assigns each asset patch to a feature setting, records
payload SHA-256/size, and includes official-install runtime requirements.

Current generated manifests require the selected vanilla folder to have exactly
these top-level entries before any output folder, backup, or patch write occurs:

```text
Assets
fmod.dll
icon.bmp
Images
ldw.ini
libjpeg-9.dll
libpng16-16.dll
Readme.txt
SDL2.dll
SDL2_image.dll
Sounds
uninst.exe
Virtual Families 2.exe
Virtual Families 2.url
zlib1.dll
```

If validation fails, the GUI/CLI reports:

```text
No valid Virtual Families 2 Installation detected! Are you sure you downloaded it from the official website?

Links:
http://www.ldw.com/
http://www.virtualfamilies.com/index.php
```

By default the exporter uses `--asset-mode additive`, which exports only assets
referenced by the generated build manifest. Use `--asset-mode all` only for
diagnostic full-folder diffs.

When a vanilla executable is available, the exporter can also add target EXE
hash metadata and length-preserving byte diff records:

```powershell
& "C:\Path\To\Python\python.exe" work\export_offline_patch_bundle.py `
  --build-dir outputs\VF2-Mobile-Furniture-With-Island-Events-B93-Holiday-Outfit-Body-Apply `
  --out-dir outputs\Offline-Patch-Bundles\B93-byte-preview `
  --vanilla-exe "C:\Games\Virtual Families 2\Virtual Families 2.exe" `
  --include-byte-patches
```

The byte-diff mode refuses to export if the vanilla and patched EXEs have
different sizes when `--strict-byte-patches` is used. Without strict mode, it
still writes vanilla EXE target metadata and records a
`native_patch_status=byte_diff_skipped` summary so the bundle can keep asset
payloads and hash validation while native patch records are developed from
object/linker patch data.

The B103 full-payload manifest targets the vanilla EXE fingerprint originally
captured from the user-provided
`C:\Users\Owner\Downloads\Virtual Families 2\Virtual Families 2.exe`:

| Field | Value |
| --- | --- |
| Size | `1,511,424` |
| SHA-256 | `1582d9e84e1c32f51475be17335c5137c592cebf809748d401ccef99a32b73c3` |
| PE sections | `5` |
| `.text` raw SHA-256 | `88c37a9989b2ad51429aca3a8e9aa9383914c9312fac2995dc4551a49ec4dc5e` |

An older workspace-local vanilla EXE candidate also exists at
`Unneeded crap\Virtual Families 2.exe`, size `1,881,088`, SHA-256
`67e8cf073be89b9699f4f7a19bc1105ceae865cdaefe98abd0c1e59e5f0d6bc4`.

The B93 patched EXE is `1,677,824` bytes, so full EXE byte-diff export is not
valid for that build. Its native patch records must be exported from the
patcher/linker/object metadata instead.

The pruned B93 asset preview produced 713 asset records:

| Setting | Asset records |
| --- | ---: |
| `holiday_outfits` | 448 |
| `mobile_furniture` | 229 |
| `holiday_ornaments_collection` | 13 |
| `outfit_store_expansion` | 11 |
| `vf3_tv_assets_recognition` | 12 |

That preview is a schema-valid starting point, not a release-ready patch
bundle: it still needs vanilla EXE target metadata and native byte records.

For beta-folder smoke testing, the exporter also supports a full-payload mode:

```powershell
& "C:\Path\To\Python\python.exe" work\export_offline_patch_bundle.py `
  --build-dir outputs\VF2-Mobile-Furniture-With-Island-Events-B103-Invisible-Heart-Bed `
  --out-dir outputs\VF2-B103-Offline-Patcher-Full `
  --vanilla-exe "C:\Path\To\Vanilla\Virtual Families 2.exe" `
  --asset-mode full `
  --include-exe-replacement `
  --include-patcher-scripts `
  --force
```

`--asset-mode full` now exports the cleaned mod-required payload shape: changed
runtime Images, `.fmap` files, and source-only `OptionalVisualMods/`,
`Original Virtual Families 2 Assets/`, and `OptionalSongMods/` folders. It does
not copy root DLLs, `Sounds/`, or arbitrary support files into payload. Passing
`--include-exe-replacement` adds a `core_executable` asset record that verifies
the vanilla
`Virtual Families 2.exe` by whole-file SHA-256 or by the recorded PE32 section
structure, then writes a clearly named modded EXE in the separate output
folder. Runner batch/readme names are inferred from the bundle label, for
example `Apply_B103_Patcher.bat` and `README-B103-PATCHER.txt`. This is useful
for testing the patcher's backup/apply/restore mechanics from an EXE-only
folder, but it is not the final trust-friendly release shape. The final patcher
should replace that full EXE payload with clean byte/table patch records
wherever possible.

B105 release exports should pass `--include-byte-patches` and omit
`--include-exe-replacement` unless a deliberate diagnostic build needs the
full-EXE fallback. This gives code/table features a way to apply while keeping
the ZIP free of a prebuilt modified game executable.

Full bundle exports also write `Transparency Log.txt`. That file documents how
the bundle was built, what the patcher does and does not do, setting defaults,
patch counts, implementation files, launcher notes, known limitations, and the
save-folder guidance shown in the GUI completion popup.

Full bundle exports also write `How to Use.txt`, a short player-facing setup
guide with the validation-only Dry Run explanation, launcher instructions,
vanilla-folder selection guidance, and save-copy guidance.

The `Add Custom Couches and LDW Posters` setting is default off. Its asset
routing covers `CouchNeonPurpleStd`, `CouchBrownColorfulStd`,
`CouchGoldColorfulStd`, `CouchAquaStd`, `CouchPinkColorfulStd`,
`CouchVioletStd`, `CouchLimeGreenStd`, `LDWModernPainting4`,
`LDWModernPainting5`, and `LDWPoster1Std` through `LDWPoster4Std` image/fmap
payloads. Current full-bundle native store rows still come from the full modded
EXE payload until those edits are split into per-feature byte/table records.

A second preview with `--vanilla-exe "Unneeded crap\Virtual Families 2.exe"
--include-byte-patches` writes the target metadata above and keeps the same 713
asset records, but has zero byte records and
`native_patch_status=byte_diff_skipped` because the EXE sizes differ.

The exporter also preserves explicit native patch byte triples found in build
metadata under `native_patch_sources`. These are source records only, not
applyable patch records, unless they have been translated to final file offsets
and moved into `patches[]`. B93 currently exposes three Settings Evict
constructor records from `settings_menu.evict.constructor_patches`; their
offsets are object/function-relative, so their `scope` is `object_relative` and
their `apply_status` is `not_file_offset`.

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
      "default": false,
      "category": "main"
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
      "description": "Adds generated outfit rows, copied stock sprite sheets, icons, independent outfit tray items, and stock outfit body field sync.",
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
      "label": "Add Holiday Ornaments collection (experimental)",
      "description": "Adds mobile Holiday Ornament yard collectibles, collection art, and goals. Disabled until the native collection page no longer crashes.",
      "default": false
    }
  ],
  "target_files": [
    {
      "path": "Virtual Families 2.exe",
      "sha256": "expected lowercase sha256",
      "size": 123456,
      "file_version": "0.0.0.0",
      "pe_timestamp": "0x12345678",
      "pe_structure": {
        "format": "pe32-section-raw-v1",
        "number_of_sections": 5,
        "sections": [
          {
            "name": ".text",
            "virtual_address": 4096,
            "virtual_size": 904777,
            "raw_data_pointer": 4096,
            "raw_data_size": 905216,
            "sha256": "section raw-data sha256"
          }
        ]
      }
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
  "native_patch_sources": [
    {
      "source_path": "settings_menu/evict/constructor_patches/0",
      "offset": "0x2DA",
      "expected_original_bytes": "0f8580000000",
      "replacement_bytes": "909090909090",
      "requires": ["settings_evict_button"],
      "scope": "object_relative",
      "apply_status": "not_file_offset",
      "next_step": "Translate object/function-relative offset to final EXE file offset before moving into patches[].",
      "note": "Original build-manifest note."
    }
  ],
  "asset_patches": [
    {
      "file_path": "Images/VF3LargeFlatScreenTVAnim.png",
      "source_path": "payload/Images/VF3LargeFlatScreenTVAnim.png",
      "source_sha256": "expected lowercase sha256 of the payload file",
      "source_size": 12345,
      "expected_target_pe_structures": [],
      "requires": ["vf3_tv_animation_graphics"],
      "note": "B65 scaled private VF3 Large TV animation strip."
    }
  ]
}
```

`target_files` is required, and at least one `.exe` target must include
`pe_structures`, `accepted_pe_structures`, `pe_structure`, or a legacy `sha256`
fallback so the user-provided vanilla executable is verified before any patch
is written. The current VF2 releases use accepted PE structures instead of a
fixed SHA-256. If the manifest's EXE filename is not present, the patcher scans
top-level `.exe` files in the selected folder and accepts one whose PE layout
matches an accepted structure.

`pe_structure` uses the patcher's `pe32-section-raw-v1` fingerprint for
traceability. Install validation compares only the stable PE identity fields:
PE header layout plus each section's name, raw file offset, raw size, virtual
address/size, and characteristics. It deliberately ignores whole-file SHA-256,
PE timestamp, overlay/certificate bytes, and per-section raw-data SHA-256 when
a compatible structure is present, so valid official VF2 EXEs with different
hashes are accepted.

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
      { "path": "Images", "min_files": 600 },
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
An asset record can also include `output_file_path`; in that case `file_path`
is the validation target inside the selected vanilla game folder, while
`output_file_path` is where the replacement is written in the modded output
folder. Older full-EXE test bundles used this for `Virtual Families 2.exe` so
the vanilla EXE was verified but the patched file was created as a clearly
renamed modded EXE. B105 release bundles should normally use byte patch records
instead of shipping a full modded EXE payload.

Asset records can create new files, which restore later removes. If an asset
target already exists, the patcher allows it only when it already matches the
payload, when `expected_target_sha256` matches, when
one of `expected_target_pe_structures` matches for a PE target, or when
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
- `unused_pets` - Add the unused Turtle and Hamster pet store entries. Default
  on.
- `invisible_furniture_visible_graphics` - Add Invisible Furniture with visible
  base-game-style placement graphics. Default off. Enable this first so the
  furniture can be placed in game.
- `invisible_furniture_transparent_graphics` - Swap placed Invisible Furniture
  graphics to transparent versions. Default off, and requires the visible
  invisible-furniture setting for active replacements.
- `vf3_tv_animation_graphics` - Fix VF3 TV animation graphics.
- `settings_evict_button` - Re-enable the Settings menu Evict button. Default
  off until the in-game implementation is stable.
- `holiday_ornaments_collection` - Mobile Holiday Ornament yard collectibles,
  collection screen art, and Goals entries. Current manifest conversion must
  include the B86 `CCollectableItem::Find()` and `WasItemSpawned()`
  family-range patches for request `0x9E` and active variants `0x9E-0xA9`, the
  B92 `CCollectionScene` six-page table append, the B92 `CCollectable`
  observer registrations for `0x9E-0xA9`, the mobile-matched four full-yard
  `0x9E` spawn rectangles, the mobile-matched Ornamentologist row `0x5F`
  target `12` and Goal Collector row `0x54` target `13`, the B87 supplied
  `Images/CollectionOrnaments/*` payloads, baked-placeholder frame background,
  and replacement `Images/collectables_small.png`.
- `custom_lorsieab2_map_images` - Optional visual-only map image swap from
  `OptionalVisualMods/Custom Lorsieab2 Map Images`. Default off.
- `transparent_menu_bar` - Optional transparent bottom menu bar visual swap.
  Default off. Credit to swedane on LDWForums.
- `transparent_store_bar` - Optional transparent bottom store bar visual swap.
  Default off. Credit to Corylea on LDWForums.
- `white_birds` - Optional visual swap that copies bundled white-bird
  `bird.png` and `bird_shadow.png` assets to `Images/`. Default off.
- `store_scroll_bar` - Optional store-screen scroll bar setting. Default off.
  Current native draw/mouse support is bundled in the core modded executable;
  full native on/off behavior still requires future byte/table record splitting.
- `invisible_upgrades_graphics` - Optional visual swap that copies bundled
  Invisible Upgrades PNGs to `Images/Upgrades`. Default off. Disabling it and
  clicking Enable/Disable Patches refreshes the modded folder from vanilla
  upgrade graphics.
- `transparent_decor_tab` - Optional transparent purple Decor tab visual swap.
  Default off. Credit to swedane on LDWForums.
- `optional_visual_mod_graphics` - Optional loose `OptionalVisualMods` image
  swaps. Furniture graphics target `Images/Furniture`; future Workshop,
  Kitchen, and Office upgrade graphics target `Images/Upgrades`; other loose
  images target `Images`. Default off.
- `optional_song_mods` - Optional song swap that copies
  `payload/OptionalSongMods/*.ogg` into `Sounds/*.ogg`. Default off.

Patch records, asset records, and target-file checks can include `requires`,
`settings`, or `setting`. A record is active only when all required settings
are enabled. If a record has no setting requirement, it is always active.

Unchecked settings must not leave their feature files in the fresh modded output
folder. The exporter therefore assigns optional visual source folders,
Invisible Furniture visible graphics, Invisible Furniture transparent graphics,
and active replacement records to the same feature gates. Re-running the
patcher with Enable/Disable Patches refreshes a recognized `VF2-*-Modded`
output folder from the vanilla install, then applies only checked records.
Unchecked settings are therefore removed from the refreshed modded folder by
omission. Native/game-code features still bundled through the monolithic
`core_executable` payload cannot be fully unbundled by checkbox until their
native changes are converted into separate byte/table patch records.

B111 adds output-only reconfiguration for existing modded folders. If the GUI
or CLI provides a modded output folder but no vanilla folder, pressing
Enable/Disable Patches reconfigures that existing folder in place. This mode
does not refresh from vanilla and does not run byte patches. For unchecked
asset records that include `restore_source_path`, the patcher copies the
bundled restore asset back into the modded folder. This keeps visual toggles
self-contained when the original vanilla install is not available.

B111 also makes EXE identity path-independent for both `target_files` and EXE
replacement `asset_patches`: `resolve_expected_exe_target()` scans the selected
folder's top-level `.exe` files for an accepted VF2 PE layout. The manifest may
still say `Virtual Families 2.exe`, but the actual install EXE can have another
filename. When a renamed vanilla EXE is discovered, the output refresh skips
that discovered source EXE so the modded folder contains the clearly named
modded EXE instead of an ambiguous copied vanilla executable.

Source-only payload folders are read-only/copy-only during apply:
`OptionalVisualMods/`, `Original Virtual Families 2 Assets/`, and
`OptionalSongMods/` stay in `payload/` and are not copied wholesale into the
game. Optional song records copy `payload/OptionalSongMods/*.ogg` into
`Sounds/*.ogg` only when `optional_song_mods` is enabled. Invisible Upgrades
records copy `payload/OptionalVisualMods/Invisible Upgrades/*.png` into
`Images/Upgrades/*.png` only when `invisible_upgrades_graphics` is enabled.
Optional visual records copy source graphics into runtime folders: furniture
graphics to `Images/Furniture`, future Workshop/Kitchen/Office upgrade graphics
to `Images/Upgrades`, and animation strips or other loose images to `Images`.
Generated patcher ZIPs must be self-contained: after export, no setting may
depend on creator-local folders such as Downloads. Source-backed optional
settings are omitted from the manifest if their corresponding payload files are
not bundled. `export_offline_patch_bundle.py::validate_bundle_asset_sources()`
fails export if any `asset_patches[].source_path` or `restore_source_path` is
absolute, escapes the bundle, or points to a missing file.

B112 payload grouping details:

- `vf3_tv_assets_recognition`: top-level VF3 TV animation strips plus private
  `Images/VF3TVAnimations/*/Frame*.png` folders; requires `core_executable`.
- `holiday_outfits`: `Images/VillagerBodies/*` and
  `Images/VillagerDetailBodies/*`, including Details-screen body 50-53 support.
- `vf3_furniture`: `SofaPlaid`, `CouchPlaid`, `CouchFlowers`,
  `CouchStriped`, `SofaStriped`, and `FloweredLoveseat` images/fmaps; default
  off and requires `core_executable`.
- `core_executable`: generated standalone `Images/GenerationLocks/lock_02.png`
  through `lock_30.png`, copied from explicit bundled numbered frames. The
  exporter no longer synthesizes generation 10-30 from a short `locked.png`
  strip; missing numbered frames fail export.

B112 build-specific notes:

- Added mobile/Holiday/VF3 furniture records whose original `lock_generation`
  is `0` are assigned deterministic shuffled generation locks in groups of
  3-4 items across the 10-30 range. The B112 data set has 39 such records, so
  it produced 13 groups of 3. Base-game furniture records are not included in
  this assignment path.
- VF3 TV runtime animation strips are bundled from
  `work/assets/vf3_tv_animations/` when external Sprite frame sources are
  absent. The generated build and patcher payload include top-level strips and
  `Images/VF3TVAnimations/*/Frame*.png`; validation rejects transparent strips.
- Holiday Body animation frames are transparent-cropped with stored draw
  offsets and are not resized. The build manifest records `resized: false`,
  source canvas size, alpha bounding box, crop size, and draw offset per frame.

B113 build-specific notes:

- Child Holiday Body rendering now scales the stored transparent-crop offsets
  by the active villager draw scale in both the Details screen and main game.
  This preserves the B112 no-resize policy while correcting child-only
  misalignment.

B114 build-specific notes:

- Invisible Furniture Base/Transparent Graphics are generated only from files
  already present in the build payload. The patcher does not look in
  creator-local or user-local folders for Invisible Full-Size Pool, Invisible
  Kiddie Pool, or Invisible Hammock graphics.
- The Base Graphics folder maps those three invisible items to their base-game
  donor art (`PoolLargeStd.png`, `PoolChildrensStd.png`, `HammockStd.png`).
  The Transparent folder maps them to `.pngORIGINAL` transparent backups that
  are generated from the same donor image dimensions inside the build.
- The main-world Holiday Body draw helper now treats the two trailing draw
  parameters as `scale, alpha`. Both stored crop offsets are multiplied by the
  body scale, which fixes child main-scene alignment without changing the
  Details-screen body renderer.

B115 patcher-specific notes:

- Asset records that validate as `up_to_date` are rechecked during apply. This
  matters when both a vanilla install folder and an existing modded output
  folder are selected: the output refresh can delete the already-up-to-date
  modded EXE before asset application begins, so the patcher must verify the
  target still exists before skipping.

Settings default to off unless the manifest sets `"default": true`. Command-line
flags can override those defaults:

```powershell
--enable holiday_furniture
--disable holiday_outfits
--enable holiday_furniture,mobile_furniture,vf3_tv_animation_graphics,settings_evict_button
--enable holiday_ornaments_collection
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
