# Discoveries

## 2026-07-02 - Offline Patcher Foundation

- `work/offline_vf2_patcher.py` is the source-only patcher scaffold for the
  no-modified-EXE release path.
- Patch manifests are JSON and currently support length-preserving byte records
  with `file_path`, `offset`, `expected_original_bytes`, `replacement_bytes`,
  and `note`.
- Manifests can declare toggleable settings such as `holiday_furniture`,
  `holiday_outfits`, and `mobile_furniture`; byte patches and target-file checks
  can require those settings before becoming active.
- `work/offline_vf2_patcher_gui.py` is a Tkinter front end that generates
  checkboxes directly from manifest settings and calls the same apply/restore
  functions as the CLI.
- The patcher verifies target-file metadata and expected bytes before writing,
  creates a backup manifest, writes patch/restore logs, and restores from its
  own backup folder.

## 2026-07-02 - Save-Load Crash In Debug Mouse-Move Hook

- B58, B59, and B60 WER reports share exception `0xc0000005` at module offset
  `0x0009ff8b`.
- In B60 bytes, RVA `0x9ff70` is the patched
  `theMainScene::HandleMouseMove(ldwPoint)` prologue. Offset `0x9ff8b` lands
  inside the injected `_VF2PatchedDebuggerMouseMove` early-return sequence
  (`pop ebp; ret 8`), not in General Appliances count logic.
- B61 removes the mouse-move debug-editor hook so loaded saves keep the stock
  `theMainScene::HandleMouseMove -> CFurnitureManager::HandleMouseMove ->
  CToolTray::HandleMouseMove` flow. Mouse down/up/key debug hooks remain
  available for editor entry points.
- B61 still crashes on mouse click after loading a save, which points to the
  remaining main-scene mouse down/up debugger hooks touching debugger/editor
  state during vanilla play.
- B62 changes the debugger input hooks to fall through to stock handlers unless
  F5 has enabled debugger input for the session, and wraps `Debugger`/`IEditor`
  calls with guarded access that disables debugger input after an access fault.
- The local B62 signing attempt reached `signtool` but failed because the
  configured certificate thumbprint was not present in the current user's
  certificate store.
- B62 still crashes while opening the affected save, so B63 disables debugger
  hooks by default and leaves all `theMainScene` save-load/draw/input handlers
  stock in normal builds. Debugger work should move to isolated opt-in research
  builds.
- B63's generated `work/patched_mobile_furniture_pack_objs/theMainScene.obj`
  matches `work/desktop_obj_files/theMainScene.obj` byte-for-byte by SHA-256,
  confirming the normal build no longer patches `theMainScene`.
- User testing confirmed B63 opens the affected save without the B61/B62
  debugger crash. Treat default-build `theMainScene` input/draw hooks as
  off-limits until debugger support has an isolated proof path.

## 2026-07-02 - General Appliances Count Collision

- `gAppliancesList` stock count is `15` (`0x0F`), with max index `14`
  (`0x0E`).
- After additive pet support, `gPetList` also has count `15`; broad patching of
  `6A 0F` or `83 FE 0E` can widen pet paths while trying to add VF3 TVs.
- Safe General Appliances widening is now targeted to
  `CInventoryManager::GetCategoryItem` offsets `0x73` and `0x95`, plus
  `CInventoryManager::GetCategoryItemCount` offset `0x37`.
- Accessories worked with the earlier pattern approach because its stock count
  `47` was distinctive in the patched object, but that should not be treated as
  safe for small/common category counts.

## 2026-07-03 - VF3 TV Animation Strip Scaling

- B64 keeps the VF3 TV fix asset-only: no villager behavior, furniture behavior,
  mouse input, or base TV resource patches changed.
- `work/patch_mobile_furniture_pack.py` now scales each generated private VF3
  TV animation frame into an explicit per-cell screen box before writing the
  runtime strips:
  `Large/LargeEast=(4,5,65,60)`, `Small/SmallEast=(2,3,48,43)`, and
  `FathersFavorite/FathersFavoriteEast=(5,5,96,78)`.
- The affected generated runtime files are
  `Images/VF3LargeFlatScreenTVAnim*.png`,
  `Images/VF3SmallFlatScreenTVAnim*.png`, and
  `Images/FathersFavoriteTVAnim*.png`. Stock `TVAnimBig*.png` and
  `TVAnimSmall*.png` remain untouched.
- If in-game B64 still shows the old alignment, the next research point is the
  furniture-to-animation-sheet lookup path; binary strings still primarily show
  the stock TV animation descriptor names.

## 2026-07-03 - VF3 TV Private Floating Animation Entries

- B64 generated private VF3 TV animation strips, but those strips were dead
  data: the linked EXE and `theGraphicsManager.obj` still referenced stock
  `TVAnimBig.png`, `TVAnimBigE.png`, `TVAnimSmall.png`, and
  `TVAnimSmallE.png`, not the VF3 private strip filenames.
- `CFurnitureManager::SetOnState` / `RestoreAnims` read floating animation
  enum fields from `FurnitureInfo` offsets `+0x24 + frame*4`, x offsets from
  `+0x34 + frame*4`, y offsets from `+0x44 + frame*4`, and speed from `+0x54`.
  Stock flat-screen item `0x1F3` uses enum `0x2A`/`0x19` with offsets
  x=`0x13`/`0x0C`, y=`0x0C`/`0x0D`.
- `CFloatingAnim::m_sAnim` is a 64-entry, 16-byte-per-entry table. Stock enum
  `0x19` maps to image `0x1FB` (`TVAnimBig.png`), `0x1A` to `0x1FC`
  (`TVAnimSmall.png`), `0x29` to `0x20D` (`TVAnimSmallE.png`), and `0x2A` to
  `0x20E` (`TVAnimBigE.png`). `CFloatingAnim::LoadAssets` scanned only the
  original `0x400` bytes until patched.
- B65 appends private floating-animation enum slots `0x40-0x45`, private image
  descriptors `0x4CD-0x4D2`, and extends the `LoadAssets` bound to `0x460`.
  Only the three added VF3 TV `FurnitureInfo` records point to these private
  enums, with zeroed animation offsets because the generated strip cells are
  already padded to the furniture canvas. Base TV assets and behavior remain
  untouched.
- The B65 generator records a `vf3_tv_behavior_contracts` manifest section and
  raises if any non-identity, non-store, non-animation `FurnitureInfo` field
  drifts from donor item `0x1F3`. `clickable_added_furniture` also maps all
  three VF3 TVs to donor `0x1F3`, so villager/drop/click behavior stays aligned
  with the base flat-screen TV while the private animation graphics differ.

## 2026-07-03 - Offline Patcher Asset Records

- `work/offline_vf2_patcher.py` now supports `asset_patches` in addition to
  length-preserving byte `patches`.
- Asset records use `source_path` relative to the manifest folder,
  destination `file_path` relative to the game folder, required
  `source_sha256`, optional `source_size`, optional
  `expected_target_sha256`, and the same `requires`/`setting` feature gates as
  byte records.
- Restore tracks whether an asset target existed before patching. Existing
  targets are backed up and restored; newly created files are removed on
  restore.
- B65 VF3 TV strip payload hashes for future offline manifests:
  `VF3LargeFlatScreenTVAnim.png=BA59E973F2EC01AB4D25FDE96C65BB9BCF10E6345A153E7FEA5588FF60DDC028`,
  `VF3LargeFlatScreenTVAnimEast.png=BD4E2674B4674D460EFBE475DAC2861A324B7729E40ACEE3016537689F2B995E`,
  `VF3SmallFlatScreenTVAnim.png=18B99084E0F532A0EA9608670F955C631AE0CBEFBEB0B12C207C3FD26F63C791`,
  `VF3SmallFlatScreenTVAnimEast.png=E0D4504D422DA5998035F6F7B30BD8DF0FEBDF643F95541D0F79BFC99D6032D7`,
  `FathersFavoriteTVAnim.png=97E2A88D68808E3013F3D93106612B1FCFD588B0D635F3DED6218E4FDA6B87B1`,
  and
  `FathersFavoriteTVAnimEast.png=1B1C904DAAD7F04DB4690A0D2DF8E2B3EF16F0F1EAE64AB2410EC53E64FBBC27`.
- The offline patcher regression suite now covers a
  `vf3_tv_animation_graphics` toggle that applies/restores all six private VF3
  TV strip assets as a group. The remaining offline-patcher work is converting
  B65's native descriptor/table/furniture-record changes into verified byte
  records against a vanilla executable.
