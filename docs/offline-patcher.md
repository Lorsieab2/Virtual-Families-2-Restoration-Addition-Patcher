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

Use `--output-dir` to choose the exact modded output folder. Alternatively,
use `--output-parent-dir` to choose where the manifest-named folder is created;
`--output-dir` takes precedence when both are supplied. B156 uses the stable
folder and executable names `Virtual Families 2 - Modded` and
`Virtual Families 2 - Modded.exe`. Its save folder is exactly
`Documents/LDW/Virtual Families 2 - Modded`.

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

## Optional crash-capture QA

Exported bundles ship `vf2_crash_capture.py` and an unfilled
`crash-capture-manifest.template.json`. Keep this exact-build manifest separate
from the portable patch `manifest.json`: copy the template, then record the
selected modded EXE's absolute path, positive byte size, and SHA-256. Run
`verify-exe` before generating separate WER setup and restore scripts. The
helper only writes reviewable state and instruction files; it does not change
the registry or launch VF2. Run setup before reproducing the crash and restore
only after collecting the dump and logs.
After a crash, record the dump and log identities, run `validate-bundle`, and
emit IDA JSON only from the successfully revalidated bundle report. See
`docs/crash-capture-readiness.md` for the exact commands and fail-closed gates.

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

The GUI provides a separate **Save modified folders under** picker for choosing
the parent directory of the manifest-named modded folder. It auto-populates the
modded output folder from that parent (or the selected vanilla folder's parent)
and manifest `output.default_folder_name`. The Enable/Disable Patches
button uses green bold text, manifest descriptions support `**bold**` markup,
and description blocks resize to keep their full text visible. The completion
popup separates enabled patches from disabled/restored patches and keeps
path/save guidance fixed while the modified-file log is the only scrollable
area. The Vanilla Game Folder Path, Modified Game Folder Path, and Modified
Game Saves Folder Path are shown as bold blue clickable paths.

The GUI groups manifest settings by `category` and provides buttons to enable
all Main or Optional settings without changing unrelated checkboxes. B156 has
no active Experimental/Not Working section:

| Category | GUI color | Intended settings |
| --- | --- | --- |
| `main` | Green | Core patches, mobile-exclusive furniture, Holiday furniture, and Holiday outfits. |
| `optional` | Black | Holiday Ornaments, Island Events, Allow Older Pregnancies, Allow Same-Sex Marriage, Older Villager Mortality Curve, mobile furniture behaviors, Invisible Furniture graphics modes, optional visual swaps, custom maps, LDW Posters/Paintings, and Colorful Couches. |

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

After all asset and restore records are assembled, the exporter removes every
payload file that is not referenced by `source_path` or `restore_source_path`.
This reachability pass happens before final validation, is summarized in
`export_summary.payload_pruning`, and prevents copied source-only folders from
silently inflating distributable builds with files the patcher cannot read.

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

`work/verify_offline_bundle_zip.py <explicit-zip-path>` independently
certifies the current canonical B158 archive. It fails closed on unsafe or
duplicate ZIP paths, CRC errors, a root-name mismatch, target-fingerprint
drift, executable-variant drift, unreachable settings, or malformed manifest
record types. Its canonical contract also checks four executable variants,
15 mobile-renovation PNGs, 67 mobile sounds (63 restores and four removals),
and all four WAV-to-OGG route records. This is static package evidence only;
it does not establish FMOD decoding, audible parity, gameplay behavior, or
runtime crash-freedom.

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
and moved into `patches[]`. Settings Evict constructor records from
`settings_menu.evict.constructor_patches` are core-native provenance metadata,
not independent optional patch records. Their offsets are object/function-
relative, so their `scope` is `object_relative` and their `apply_status` is
`not_file_offset`.

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
      "requires": ["core_native_patch"],
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
- Settings Evict is part of the core executable patch. It has no independent
  optional toggle; its native confirmation and family-tree reset path remain
  unchanged.
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
- `no_ai_icons` - **No AI Icons**, default off and dependent on
  `cheat_upgrades`. Replaces only the late Special Upgrade icon PNGs with
  replacement images sourced from other LDW games, online art sources, or
  custom-made artwork. The bundled current Cheat Upgrades icon is recorded as
  the restore source, so disabling the setting restores the current icon set;
  disabling Cheat Upgrades still removes its late icon payloads.
- `ai_generated_bathroom2_renovations` - **2nd Bathroom Mobile-Style
  Renovations (AI-Generated Art Warning)**, default off. It stages only the
  five tracked AI-generated source variants, normalized to the vanilla north
  Bathroom 2 crop size and the measured native room-apex anchor. The native
  second-bathroom renovation route remains disabled/hiatus; the exact warning
  shown by the setting is: `Warning: These Bathroom 2 renovation images are
  AI-generated based on the Bathroom 1's mobile renovations art, but manually
  edited by me. (Sorry, I'm too lazy to hand-make the art myself. I'm busy with
  other stuff, but feel free to make some yourself and open an Issue on the
  Github if you want to change it- Lorsieab2)`.
- When `mobile_renovations` is enabled, the black Bathroom 1 row stages its
  verified `shower_curtain_closed_black.png` bytes under the stock filename
  `Images/curtain_closed_southb.png`; the other five source-named curtain
  assets remain available in the gated renovation payload. Bathroom 2 is not
  part of this route.

For the final all-working playtest bundle, the exporter supports
`--final-playtest-all-enabled`. This is an export-only profile: it marks
Island Events, Holiday Ornaments, Behavior Patches, Mobile Renovations,
Mobile Sound Assets, Mobile Furniture Behaviors, Cheat Upgrades, and the
separate AI Bathroom 2 visual overlay default-on in that bundle manifest. It
does not change the general `SETTINGS` defaults; No AI Icons and unrelated
visual options remain default-off.

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

Output-only planning rejects conflicting duplicate output targets before any
verification or apply step. Active/restore/remove collisions are not merged;
the patcher fails closed. Removal is hash-authenticated, but apply remains a
sequential operation rather than a transaction: an interruption or later
post-asset failure can leave a partial output until the user runs the manual
`restore` command against the verified backup.

The default-off `mobile_sound_assets` setting stages all 67 hash-pinned mobile
behavior sound payloads. Four PC sound-table filename routes are changed from
WAV names to their mobile OGG names; disabling the setting removes those four
additive files and restores the other 63 same-name PC payloads from the bundled
base. Static hash and routing checks do not constitute audible runtime QA.

No AI Icons uses the same manifest-relative, hash-checked asset path. Its
replacement record is layered after the normal Cheat Upgrades icon record when
both settings are enabled. During output-only reconfiguration, a selected
restore record takes precedence over the active normal layer for that target;
when Cheat Upgrades is disabled, the restore gate is inactive and the normal
Cheat Upgrades removal record removes the late icon instead.

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

B116 build-specific notes:

- `behavior_patches` now includes child-only spontaneous "Playing quietly" at
  the Kids Table. It enables the existing native
  `CBehavior::ChildrenPlayAtKidsTable` behavior ID `0x130` through the
  autonomous AI candidate table.
- Invisible Kids Table and Chairs keeps the base Kids Table inheritance route:
  item `0x321` clones donor item `0x1CE`, uses
  `KidsTableAndChairsStd.png.fmap`, and is validated as part of the generated
  manifest. No outside asset folders are consulted.

B117 build-specific notes:

- Spontaneous "Playhouse!" remains child-only and now also checks native
  `CNight::AIIsDayTime()` during `CVillagerAI::DecideWhatToDo`. At night, the
  Playhouse candidate is disabled and its AI weight is set to `0`.

B118 build-specific notes:

- Settings Evict uses the existing desktop/mobile handler path. The generated
  core executable NOPs the two `theOptionsDialog` constructor skip branches at
  `+0x2DA` and `+0x2E7`, so control ID `4` is constructed in Settings. The
  confirmation dialog and `CFamilyTree::EvictFamily()` click handler are
  unchanged. User testing showed this was incomplete because the constructed
  button was still not added to the scene control list.

B119 build-specific notes:

- Settings Evict additionally inserts the missing
  `ldwScene::AddControl(evictButton)` call after the Evict button `SetText()`.
  This is the visibility step B118 lacked.
- The GUI saves the last vanilla install folder and modded output folder in
  `patcher_local_settings.json` beside the patcher scripts, then reloads them
  on the next launch. The bundle still does not hardcode install paths.
- Text fixes also replace `Cooking like mommy` -> `Cooking like a grownup` and
  `Driving like daddy` -> `Driving like a grownup`.
- The exporter can bundle an optional Island Events EXE overlay with
  `--island-events-exe`; it applies to the same B119 modded EXE name only when
  both `core_executable` and `island_events` are enabled.
- The GUI header includes a `Check for updates` hyperlink to the standalone
  private patcher release repository:
  `https://github.com/Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher/releases`.
  Future patcher ZIP releases should be published there only.

B121 build-specific notes:

- The Settings Evict confirmation replacement uses explicit line breaks because
  the stock in-game dialog does not auto-wrap long injected string-table
  values. The native Evict button and handler path are unchanged.
- Adds default-off optional `Misc Graphics Fixes`, currently targeting the
  Super Fridge ice maker graphic at `Images/Upgrades/superFridge_NW.png`.
- Adds default-off optional `Glowing Collectibles`, targeting
  `Images/collectables_small.png`.
- Both optional graphics patches are portable: their modded payloads live under
  `payload/OptionalVisualMods/...`, and their vanilla restore sources live
  under `payload/Original Virtual Families 2 Assets/...`.

B122 build-specific notes:

- `invisible_upgrades_graphics` is now presented as `Invisible Workspace
  Upgrades`. Its payload lives entirely under
  `payload/OptionalVisualMods/Invisible Workspace Upgrades/`.
- Enabling the setting copies bundled `invisible images/*.png` to
  `Images/Upgrades/*.png`; disabling and applying copies the paired bundled
  `original images/*.png` files back.
- The exporter reads these source PNGs from tracked `patcher_assets/`, not from
  `Downloads` or any machine-specific folder.

B131 build-specific notes:

- `behavior_patches` now includes grouped behavior-label variants for native
  TV, web, video game, radio, reading, petting, mending, ironing, telescope,
  workout, career, shower/bath, coffee/tea, cocktail, pool, sandbox, toy train,
  playground, and snow-play routes. The wrappers call the original native
  behavior and only alter the displayed action label afterward.
- The optional `cheat_upgrades` overlay adds `Unlock everything in the store` to Special
  Upgrades. It toggles all live `sFurnitureInfo+0x0C` generation locks between
  `0` and the generated original-lock snapshot.
- `expand_game_map` appears under Experimental/Not Working patches as a
  transparent placeholder only. It is intentionally marked not implemented
  until map bounds, tile loading, camera clamps, and save references are mapped.
- The exporter now normalizes manifest paths that contain generated
  `Images/` or `Assets/` segments anywhere in the string. This ensures support
  payloads referenced as `outputs/.../Images/...`, such as split VF3 TV
  animation frames and villager source sheets, are packaged automatically.
- B131 manifests include top-level `build` and `build_label` fields so the GUI
  can display the current build number without relying on folder names.

B132 build-specific notes:

- Water Pressure Surge now preserves the stock first-bathroom leak writes and
  also sets north bathroom leak props `0x48` (toilet), `0x49` (shower), and
  `0x4A` (sink) when the second-bathroom renovation item `0xE6` exists.
- `CVillager::NewBehavior` maps those active north leak props to
  `FreakOutShowerLeakNorth` (`0x135`), `FreakOutToiletLeakNorth` (`0x137`),
  or the existing bathroom sink freak-out (`0x133`); native repair behaviors
  remain `FixingNorthShower` (`0x140`), `FixingNorthToilet` (`0x142`), and
  `FixingNorthBRoomSink` (`0x04E`).

B133 patcher-specific notes:

- Settings Evict is compiled into the core executable and is not exposed as an
  optional checkbox. Island Events remains a default-off Optional patch and
  still needs in-game outcome validation.
- Experimental/Not Working remains reserved for Holiday Ornaments, mobile
  furniture behaviors, Expand game map, and future unstable features.

B134 build/export notes:

- `CFurnitureManager.obj` defines `?itemInfo@@3PAUsFurnitureInfo@@A` as a
  section symbol with COFF storage class `3` (`static`) in the stock object.
  B134 changes the patched symbol storage class to external after appending
  records, without changing the stock table bytes, so helper objects can link
  against the live furniture table for the optional Cheat Upgrades
  `Unlock everything in the store` generation-lock toggle.
- The optional Island Events helper source is emitted from a Python template.
  B134 formats that template before writing `vf2_island_events.cpp`, so the
  doubled C++ braces become normal braces and the generated
  `CMobileIslandEvent` registration lines are inserted instead of literal
  Python text.

B135 patcher/export notes:

- `export_asset_payloads()` now copies source-only payload folders whenever
  they exist in the generated build. `OptionalSongMods/` and
  `Original Virtual Families 2 Assets/originalsounds/` therefore stay bundled
  even when the export has no normal image/fmap asset diffs, so disabling the
  optional song patch can restore vanilla `Sounds/menu.ogg` and
  `Sounds/song1-4.ogg` from inside the portable patcher.

B136 patcher/export notes:

- Exact install-shape validation is intentionally name-agnostic for the game
  executable. `runtime_requirements.exact_top_level_entries` still requires the
  official runtime folders/files, but top-level `.exe` files that are not in
  that list are ignored by the folder-shape check. `verify_target_files()`
  still validates the selected/discovered executable against SHA or accepted
  PE structure before anything is written, so invalid EXEs are rejected at the
  binary-identity step instead of as "unexpected top-level entries".
- `work/official_vf2_pe_structures.json` stores the known official VF2 PC PE
  layouts as structural metadata only. `export_offline_patch_bundle.py` embeds
  those layouts into `target_files[].pe_structures` and the core EXE
  replacement asset record, so the shipped patcher stays self-contained and
  does not need any outside official-EXE path to recognize both official
  vanilla layouts.

B138/B141 Flea Market build/export notes:

- B138 initially followed `MaybeUpdateSaleItems()`, which is actually the
  category `0x03` On Sale cache (`CInventoryManager+0x474`, count/timer at
  `+0x480/+0x484`). B141 corrects the expansion to the real Flea Market path:
  category `0x0F`, `MaybeUpdateRotatingItems()`, `gGoodiesList`, and the
  rotating-goodies cache at `CInventoryManager+0x488` with count/timer fields
  at `+0x49C/+0x4A0`.
- The next Flea Market helper uses the same fixed-list expansion style as the
  Clothing section: count returns `0x24`, and item lookup returns
  `gGoodiesList[index]` directly. It does not filter through
  `CInventoryManager::HaveUpgrade` or the native five-row rotating cache.
- B143 export verification: the patcher ZIP/folder include the fixed core EXE
  and all optional EXE overlays. A CLI `--enable-all --dry-run` passed against
  the test install folder and validated `1070` active/restore asset records.
- Non-Flea store categories, including On Sale, keep the stock paths. The
  patcher export must include the refreshed core, Island Events, Cheat
  Upgrades, and combined EXE overlays so this native hook is present no matter
  which optional overlay combination is selected.

B139 build/export notes:

- `Cheat Upgrades` adds `Reset Achievements` as visible Special Upgrades row
  `0x124`. The generated helper declares `CAchievement::Reset()` and calls the
  global `Achievement` instance, then uses the existing save-at-end path in
  `VF2ApplyVisibleSpecialUpgrade`.
- The trophy icon is bundled as `Images/cheat_reset_achievements.png` in the
  generated build and patcher payload; future exports should not read this icon
  from any Downloads path.
- The B139 patcher export is audited for portable metadata as well as portable
  payloads. `manifest.json`, `Transparency Log.txt`, and active runner scripts
  should not contain build-machine `C:\Users\...` or Downloads paths; provenance
  fields use filenames/build labels only.

B140 patcher release notes:

- B139's existing GitHub Release asset is immutable, so the cleaned portable
  patcher was released as B140 instead of replacing the locked B139 ZIP.
- B140 keeps the B139 gameplay payload shape (`1052` asset records, `2949`
  payload files, four EXE overlay payloads) and changes only the patcher build
  labels/portable metadata.
- All-settings dry run validated all `1052` active/restore asset records
  against the workspace vanilla install.

B141 patcher release notes:

- Behavior-label wrappers now guard their variant labels by checking whether
  the native behavior changed the action label first. This keeps stock
  rejection, shower, bathroom sink, grooming, and age gates intact while still
  adding variants when the action actually starts.
- The generated behavior helper now records the selected stock/custom label in
  a small per-villager/per-wrapper cache. Praise and HUD refresh paths reuse
  that cached label instead of rerolling a sibling variation while the same
  native route remains active. This describes the B141 release state; B150
  supersedes it by caching both radio/MP3 listen and dance choices so praise
  cannot reroll the visible action.
- Cheat Upgrade icons are normalized to transparent `90x90` PNGs during
  payload sync so store rows and buy dialogs do not inherit oversized or
  undersized source art.
- Export verification: `Virtual-Families-2-Restoration-Addition-Patcher-B141`
  contains `1052` asset records and `2949` payload files. An all-settings dry
  run against a valid official test install validated every active/restore
  record and reported no missing payload entries.

B150 patcher/build notes:

- The patcher now treats Behavior Patches as a true executable feature gate,
  not merely descriptive setting metadata. B150 accepts core and all 15
  non-empty combinations of Island Events, Cheat Upgrades, Holiday Ornaments,
  and Behavior Patches, for a complete 16-state overlay matrix. Every overlay
  asset record requires core_executable plus exactly the enabled native feature
  IDs that produced it.
- Behavior Patches owns every B150 autonomous/label/praise/sink change. Cheat
  Upgrades owns every B150 cheat, price mode/reset, malfunction Trigger/Fix, and
  Maid/Gardener/Rockhound/Anti-Spam removal. Holiday Ornaments owns the
  six-page/72-item collection fix. Water Pressure Surge requires Island Events,
  while Brokerage's 11% description follows mobile_purchases.
- The Holiday setting remains default-off Experimental for a replacement
  in-game collection-cycle test. The first B150 release still crashed because
  several internal x86 branches crossed inserted bytes. The hotfix replaces
  HandleMouse/Find/WasItemSpawned insertions with fixed-size code-cave detours,
  repairs The Collector Keep branch and Drop reentry, makes goal completion
  idempotent, retains the stdcall page count and " / 72" suffix, and leaves the
  stock five-page/60-item executable selected when disabled.
- Behavior Patches enables all-age Needs to sit down and Checking weight,
  displayed-age-14+ Mending a button and Ironing clothes, and nursing-mother
  Teaching first words/infant care. Petting is deliberately non-spontaneous.
  Snow routes remain Snowing-only and direct sink subroutines clone the stock
  sink gate rather than becoming unconditional.
- Web additions are Watching memes, Making memes, Posting memes online, and
  age-13+ Buying stuff online. Nursing labels are Teaching baby how to walk,
  Talking with baby, Feeding baby, Singing lullabies to baby, Playing with
  baby, Admiring baby, Playing peek-a-boo with baby, Kissing baby, and Taking
  pictures of baby.
- Nap labels cover Isola, family, pets, friends, the future, beach, snow,
  holidays, vacations, roller coasters, climbing mountains, camping, family
  trips, countryside, LDW games, city, forest, unicorns, fish, jungles,
  tropical islands, skyscrapers, floating in space, treasure, getting rich,
  adventures, swimming, flying, falling, and discovering something.
- The all-age sit-down pool covers thinking/reflection; family, relatives,
  friends, pets, vacations, weekends, and viewing plans; rest/eyes/feet/break;
  enjoying life/scenery; texting, phone games, scrolling/social media;
  scrapbooking; and texting friends/family/relatives. Age 19+ adds
  children/grandchildren/spouse and Texting spouse. Thinking of work requires
  age 19+ with a career; Thinking of school requires that the villager is not an
  age-19+ career holder; Texting boyfriend is female-only and Texting girlfriend
  male-only at ages 14-18.
- Bathroom sink general labels remain face mask, trimming nails, lotion, and
  sunscreen; female grooming adds fingernails, toenails, manicure, pedicure,
  and makeup. Putting on jewelry is female-only from displayed age 14. Normal
  praise now captures the exact 0x28-byte current label before native
  ForgetPlans erases it and restores it before/after the restarted behavior.
  The deliberate over-praise RunAway branch stays native.
- New gated cheat rows are Reset Ants 0x125, Reset all collections 0x126,
  Complete all collections 0x127, 2x Prices 0x128, 5x Prices 0x129, 100x
  Prices 0x12A, Trigger all house malfunctions 0x12B, Reset Price Multiplier
  0x12C, and Fix all house malfunctions 0x12D. The display groups money, food,
  goals/puzzles/collections, prices/reset, and Trigger/Fix while retaining all
  IDs. Reset Price's exact description is "Resets store prices to original
  values."
- Reset Ants resets world-state puzzle 0x13, clears props 0x4D-0x54, and reseeds
  a playable starting set. Collection reset/complete operates on five stock
  12-item pages and conditionally the 0x9E Holiday page/0x5F achievement only
  when that overlay is active.
- Price modes are mutually exclusive, persistent inventory upgrades applied at
  final CalcPrice return. That route covers furniture, Flea Market, renovations,
  career upgrades, Special Upgrades, and the other store categories. Positive
  multiplication saturates at signed INT_MAX. Reset Price Multiplier removes
  active IDs 0x128-0x12A and immediately restores original calculated prices.
- Trigger all house malfunctions sets the regular failure props and Router
  Offline prop 0x17. Fix All clears the exact 11-malfunction set, brings the
  Router online, and leaves ants 0x4D-0x54 alone. Dryer lint fire is also a
  legitimate stock random malfunction: it requires Dryer object 0x48, sets
  prop 0x21, and its native repair advances Handyman 0x3A. North leaks require
  renovation 0xE6; Water Pressure Surge adds them only with Island Events.
- With Cheat Upgrades active, buying an already active Maid or Gardener row at
  zero price clears its service timer, deactivates worker 0x23/0x24, and safely
  clears selection. Rebuying Rockhound Certificate or Anti-Spam removes its
  inventory/state flag. Cheat-disabled overlays retain stock already-purchased
  behavior because the removal helper is explicitly gated.
- Generated runner README text now includes the shared B150 changelog. Generated
  Transparency Log.txt includes the feature matrix, setting-to-feature map, all
  B150 behavior/cheat/fix notes, and an explicit distinction between automated
  source contracts and outstanding manual in-game tests.
- The GUI, README, manifest, and transparency output carry the exact vanilla
  save-compatibility note plus Lorsieab2's passion-project/no-infringement/
  support-the-original-creators message. Brokerage Account states that it can
  increase the Interest Rate up to 11%.
- Automated exporter/unit/build-contract verification does not replace runtime
  gameplay testing. The B150 release still needs the manual matrix, collection,
  behavior gate, price-category, removal, save/reload, and malfunction/repair
  passes recorded in docs/TODO.md.

Settings default to off unless the manifest sets `"default": true`. Command-line
flags can override those defaults:

```powershell
--enable holiday_furniture
--disable holiday_outfits
--enable holiday_furniture,mobile_furniture,vf3_tv_animation_graphics
--enable holiday_ornaments_collection
--enable allow_older_pregnancies
--enable-all
--disable-all
```

Patch logs include the available, enabled, and disabled settings used for the
run.

allow_older_pregnancies is a default-off Optional option. It uses an
exact-SHA post-asset byte toggle in the selected executable rather than a
separate executable overlay, so it does not expand the Island/Cheat/Holiday/
Behavior matrix.

The same post-asset phase controls the independent Holiday Furniture goal
suffix through .vf2goal. Its record requires core_executable and
holiday_furniture; disabling Holiday Furniture recopies the pristine
default-zero payload byte.

B156 removes the active Experimental/Not Working category and the inactive
`expand_game_map` placeholder. Allow Older Pregnancies, Older Villager
Mortality Curve, and mobile furniture behaviors are default-off Optional
patches. Historical build notes above retain their original category wording
to describe what those earlier bundles actually shipped.

The first exact mobile-furniture behavior family is Lounge Chairs `0x2DE-0x2E1`.
When enabled, a default-zero `.vf2beh` flag and four PC-safe furniture maps add
the recovered manual `Relaxing on lounger` action. The wrapper preserves stock
hotspot handling first, adds no autonomous behavior, and disabling the setting
restores the exact rendered-only maps. Invisible/custom/VF3 furniture is outside
this optional patch.

B156 also preserves the exact Windows executable icon resources from the
verified stock `Virtual Families 2.exe`. The patcher validates every icon-group
reference and requires Windows to extract 16x16, 32x32, and 48x48 icons from
the completed temporary EXE before atomically installing it. After the icon
write it refreshes and verifies the nonzero Windows PE checksum. This covers
the folder, desktop-shortcut, and taskbar/pinned-icon cases without
substituting patcher branding for the base-game icon.

## Release Notes

The patcher itself is source-only and uses Python's standard library. Release
packaging should keep it transparent: no packers, no obfuscation, no memory
editing helper, and no admin-only install flow. Published releases should
include hashes and a false-positive submission trail for antivirus vendors when
needed.
