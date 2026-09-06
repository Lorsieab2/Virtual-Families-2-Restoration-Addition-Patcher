# Discoveries

## 2026-07-17 - B155.5 Full-Game Calibrated Mortality

- The stock old-age rule is an annual birthday roll after threshold
  `55 + active food groups`, increasing by ten percentage points per effective
  year and reaching certainty ten effective years later.
- B155.5 keeps that threshold and the native 0-4 food-group input, but uses the
  monotonic intensity `0.00365*n + 0.06*max(0,n-55)`, where `n` is effective
  years past the threshold. The annual probability is `1-exp(-intensity)`,
  rounded half-up to millionths and capped at 999999/1000000.
- The late term begins after effective age 110. The first quantized cap is
  effective age 318; one non-death result always remains and there is no hard
  maximum age.
- Calibration treats a full game as 60 adults. Across constant 0-4 food-group
  scenarios, modal death ages are 72-76 and median ages are 74-78. Reaching
  age 110 takes about 4.279-2.289 games per success; reaching 122 takes about
  2796.10-112.00 games per success.
- Birthday reach odds survive through the preceding birthday roll. They are
  deliberately distinguished from survival after the roll performed at the
  milestone age.
- The planned age-122 longevity achievement remains unimplemented; the curve
  permits the age but does not add or claim that goal trigger.

## 2026-07-14 - B155 Realistic Mortality Curve

- Older Villager Mortality now uses the sex-averaged 2022 U.S. Social Security
  period-life-table annual death probabilities for effective ages 55-105.
  Values are stored as integer basis points and still use GetRandom(10000)
  exactly once on each 20-tick birthday.
- Effective age 106 and above uses a 5,000-basis-point (50%) annual mortality
  plateau. This avoids both a hard maximum age and B154's 99.99% yearly cliff.
- Each active food group still subtracts one effective year, clamped to 0-4.
  With constant food-group history, old-age-only survival through displayed age
  122 is about 1 in 268.6 million with zero groups and 1 in 16.8 million with
  all four groups.
- The optional hook continues replacing only the stock old-age mortality block.
  Sickness, starvation, healing, productivity, and all other physiology remain
  native and unchanged.
- Source: SSA Annual Statistical Supplement 2025, table 4.C6 (2022 period life
  table): https://www.ssa.gov/policy/docs/statcomps/supplement/2025/4c.html

## 2026-07-12 - Native Debugger and Editor Interface Split

- Desktop theMainScene.obj implements IDebugger as a secondary base at object
  offset +8; its provider virtual is theMainScene::Debug().
- WaypointEditor.obj and LightSourceEditor.obj implement IEditor, not
  IDebugger. Registering either global with CDebugger::Register is an invalid
  interface cast and has been removed from the dormant research helper.
- The default-off research path now registers only theMainScene+8. It keeps
  editor selection separate: F6 selects Waypoint Editor, F7 selects Light
  Source Editor, and F4 deactivates the current editor.
- The native light editor calls CNight::AddLightSource, DeleteLightSource,
  SetupLightSource, and Save. Visible controls are L add, D delete, and S save;
  dragging moves a source, and two character cases cycle native light types 3
  through 11.
- This remains a key/display-first isolated research path. No main-scene mouse
  handler is restored until save-load and F5/F6/F7 display tests prove stable.

## 2026-07-03 - Mobile Native Reconstruction Bootstrap

- `work/make_mobile_reconstruction_report.py` now bootstraps its own evidence
  from `C:\Users\Owner\Downloads\Virtual+Families+2_1.7.16_APKPure.xapk` when
  `work/apk_native` or `work/vf2_obb/assets` is missing. Use
  `--refresh-inputs` to force a clean APK/OBB re-extraction.
- The refreshed reconstruction inventory found 4 gameplay
  `libVirtualFamilies2.so` variants, 1,092 OBB asset files, 333 recovered C++
  classes, and no size/magic mismatches in the sampled `.fmap` files.
- The next IDA/Ghidra pass should start from the generated
  `outputs/VF2-Mobile-Cpp-Reconstruction/mobile-native-inventory.json`
  `port_targets` list. The highest-value methods are `CPVR::Load`,
  `CPVR::ConvertPVRTC`, `CContentMap::LoadFmap`, `CContentMap::Read`,
  `CFurnitureManager::LoadFmap`, `CFurnitureManager::ApplyFmapContent`,
  `CFurnitureManager::GetFmapName`, `CFurnitureManager::GetImageGrid`,
  `GameFS::AddZipOrFolder`, `GameFS::Fopen`, `GameFS::Fread`,
  `ldwGameState::Load64`, and `theGameState::LoadCurrentGame`.
- Treat those methods as the bridge from APK-native reverse engineering to a
  functioning Windows runtime: first reconstruct asset/file loading, then
  `.fmap` content blocks, then furniture storage/world placement, and only then
  save/load and villager behavior.

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

## 2026-07-03 - Outfit Store Icon Rows

- The added Clothing-store outfit rows were blank because their item IDs live
  at `0x400+`, outside the stock item ranges that
  `CInventoryManager::DrawItem(ldwPoint, ...)` and
  `CInventoryManager::DrawItem(ldwRect, ...)` know how to render. The text,
  price, and outfit helper hooks worked, but the icon path had no valid image
  descriptor/draw route.
- B66 splits the added outfit entries by gender: female rows use item IDs
  `0x400-0x435`, male rows use `0x440-0x475`, for 108 added rows plus the six
  stock Clothing rows (`new_count=114`).
- `work/patch_mobile_furniture_pack.py` now generates 108 preview icons under
  `Images/OutfitIcons/`, registers image descriptors `0x4D3-0x53E`, and adds
  targeted `DrawItem` prologue hooks that draw those descriptors through
  `theGraphicsManager::Draw`. Villager behavior/furniture behavior paths are
  untouched by this icon fix.

## 2026-07-03 - Visible Special Upgrade Icons

- The added visible Special Upgrade rows (`0x117-0x11A`) also used standalone
  image descriptors but did not have a reachable store-icon draw path, leaving
  Brokerage Account, Food Club, Health Plan, and Lucky Rock blank in the
  Special Upgrades list.
- B67 reuses the B66 `CInventoryManager::DrawItem(ldwPoint, ...)` and
  `DrawItem(ldwRect, ...)` prologue hooks. The shared helper now resolves
  either an outfit icon or a visible Special Upgrade icon, then draws through
  `theGraphicsManager::Draw`.
- Visible Special Upgrade icon descriptors remain `0x309-0x30C` and the
  patcher now emits/copies the four required PNG payloads into the additive
  output: `BrokerUpgrade_icon.png`, `FoodClub_icon.png`,
  `HealthPlan_icon.png`, and `LuckyRock_icon.png`.

## 2026-07-03 - Holiday Outfit Runtime Frames

- The Holiday Outfit store previews can render correctly even when the
  runtime villager body-frame records are missing. B66/B67 generated
  `Images/OutfitIcons/` from fallback body sheets, but
  `holiday_body_runtime_frames.frames` regressed to `0` because
  `sync_holiday_body_runtime_frames()` only searched the current additive
  `OUT/Images` folder for stock body/action/sit sheets.
- B68 makes runtime frame generation use the same complete image-root search
  model as the outfit icon generator: current output, prior completed
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B*` builds, then the B56
  expanded Holiday body fallback. With no local Holiday archive present, it
  regenerates all 448 cropped frame PNGs under
  `Images/VillagerBodies/{Female,Male}/Body_50..Body_53/{bodies,actions,sit}`.
- The generated `vf2_villager_body_frames.cpp` fallback now clamps recognized
  Holiday body grids to stock row `49` if a per-frame image cannot be loaded,
  avoiding a vanilla `DrawScaled(... row=50..53 ...)` path. The native
  `CAnimManager` body lookup remains unpatched in normal builds.

## 2026-07-03 - Outfit Store Purchase And Action Icons

- The generated Clothing rows were visible but did not enter the tool tray
  because `CScrollingStoreScene::HandlePurchaseItem` only calls the native
  inventory/tray path for stock item IDs below `0xE1`. The synthetic outfit
  rows at `0x400-0x435` and `0x440-0x475` skipped all native purchase branches
  after the coin charge.
- Stock outfit purchases convert clothing rows into tray item `0x49` for
  male outfits and `0x4A` for female outfits, with body values stored at
  `InventoryManager+0x468` and `InventoryManager+0x46C`. B69 originally
  mirrored that route through `_VF2PurchaseOutfitStoreItem` and hooks
  `CScrollingStoreScene::HandlePurchaseItem + 0x1AD` only for recognized
  generated outfit IDs.
- Store icons now come from the matching row's last action-sheet frame:
  `female_actions00.png` or `male_actions00.png`, 91 px cell column `14`.
  Base rows use the stock 50-row action sheets; Holiday rows use the expanded
  B56 fallback sheet rows `50-53` when the current output only has stock rows.

## 2026-07-03 - VF3 TV Animation Orientation Correction

- The raw TV animation source frames are already isometric. `TVAnimBig_01.png`
  slopes opposite the added VF3 west-facing screen, while
  `TVAnimBigE_01.png` matches it. The added VF3 TV labels therefore need the
  source prefixes swapped: non-East labels use `TVAnimBigE*`, and East labels
  use `TVAnimBig*`.
- B70 keeps the fix asset-only by regenerating the private VF3 TV strips. The
  screen boxes now cover the full slanted face bounding area:
  `Large/LargeEast=(4,5,65,80)`, `Small/SmallEast=(2,2,48,60)`, and
  `FathersFavorite/FathersFavoriteEast=(5,8,96,104)`.
- B70 private strip payload hashes:
  `VF3LargeFlatScreenTVAnim.png=DD4A1B6715FFE7EC810AEE964BF5C0F7ABEA83018CFB79C9745014B86827F1C7`,
  `VF3LargeFlatScreenTVAnimEast.png=73738462932FCDF6CAE2BA575C091B466AA0416D98416B1893CF2EB7C8746F0F`,
  `VF3SmallFlatScreenTVAnim.png=50C3714B47C62BEE6A6A3F0D00EFA01CCD5E3EDDC68C76DEDD848EB00F3903F8`,
  `VF3SmallFlatScreenTVAnimEast.png=A1AF88A771020141D4B298F4307140FF16C2FAD6F10D2644924E82BFCCE3AD3B`,
  `FathersFavoriteTVAnim.png=C12530E3CCEEAE61FDAAC564737311F18A4A6F41734EA4B8CA12BA70ED07CCC7`, and
  `FathersFavoriteTVAnimEast.png=E74071EFECE65336B028A472A7668D5C05ADB31B4CD9FD3FCAAA11801E38906E`.
- No furniture behavior, villager behavior, base TV animation files, or stock
  floating-animation enums are changed by this correction.

## 2026-07-03 - Clothing Category Crash Guard

- B69 added `CInventoryManager::GetNumAvailable` and `GetUseCount` hooks for
  synthetic outfit IDs. User testing found that clicking the Clothing store
  section could crash before an outfit purchase was attempted.
- B71 keeps the `GetNumAvailable` hook but makes it side-effect-free: generated
  outfit IDs return `1`, stock IDs return `-1`, and the helper no longer calls
  `CToolTray::IsSlotAvailable` while the store is opening/drawing rows.
- B71 removes the generated-outfit `GetUseCount` hook entirely. The direct
  purchase hook still sets `InventoryManager+0x468/+0x46C`, adds native tray
  item `0x49/0x4A`, and saves only when an outfit row is actually bought.

## 2026-07-03 - Settings Evict Button

- Desktop `theOptionsDialog.obj` already contains the mobile-style Evict
  implementation. The relevant handlers are
  `theOptionsDialog::EvictFamily()` (`?EvictFamily@theOptionsDialog@@AAEXXZ`)
  and `CFamilyTree::EvictFamily()` (`?EvictFamily@CFamilyTree@@QAEXXZ`).
- The `theOptionsDialog` constructor also contains the Evict control setup, but
  two branches skip that setup for normal in-progress families. B72 NOPs the
  constructor skip branches at `ctor+0x2DA` (`0F 85 80 00 00 00`) and
  `ctor+0x2E7` (`7D 77`) so existing control ID `4` is created in Settings.
- The button reuses existing strings/control flow: label string ID `0x10`,
  confirmation string ID `0x11`, then the existing family-tree eviction
  handler. No new save-state clearing code, villager behavior, or furniture
  behavior is introduced by this patch.

## 2026-07-03 - Clothing Getter ECX Guard

- User testing showed B71/B72 still crashed when entering the Clothing store
  category. The remaining generated-outfit getter hooks call `__cdecl` helper
  functions before stock fallback, but the member methods still need `ECX` as
  the `CInventoryManager this` pointer when the helper returns `-1` for stock
  Clothing rows.
- B73 updates the member-function getter hook payloads
  (`GetNumAvailable`, `GetOutfit`, `GetPrice`, and
  `GetLockGenerationLevel`) to `push ecx` before the helper call and `pop ecx`
  before the stock-fallback compare. Static string getter hooks remain cdecl
  fallthroughs and do not have a `this` pointer to preserve.

## 2026-07-03 - Any-Generation Settings Evict

- The stock `theOptionsDialog` Evict button constructor gate is:
  `cmp FamilyTree+0, 0; jne skip; cmp FamilyTree+4, 2; jge skip`.
  `FamilyTree+4` is the active generation count/index used by
  `CFamilyTree::StartNextGeneration`; generation 1 stores `1`, generation 2
  stores `2`, and so on.
- `CFamilyTree::EvictFamily()` is generation-agnostic. It calls
  `CFamilyTree::Reset()`, then writes `1` to `FamilyTree+0`. The Options
  handler then resets `CVillagerManager`, switches the adoption scene state to
  `2`, copies the current game-state scene slot, sets scene `6`, and ends the
  dialog.
- B74 keeps the Evict button hidden when `FamilyTree+4 <= 0`, but removes the
  generation-1 limit by changing the constructor branch at `ctor+0x2E7` from
  `jge` to `jle` and the compare immediate at `ctor+0x2E6` from `2` to `0`.
  This keeps the click path limited to active families while allowing every
  active generation to use the existing eviction handler.

## 2026-07-04 - Mobile Settings Evict Parity

- Mobile VF2 1.7.16 keeps native symbols for the same eviction path:
  `_ZN16theOptionsDialog11EvictFamilyEv` at `0x1087D0`,
  `_ZN11CFamilyTree11EvictFamilyEv` at `0x1C3B10`,
  `_ZN11CFamilyTree5ResetEv` at `0x1C3150`, and
  `_Z14ShowMessageBoxP8ldwScene8StringIdib` at `0x121070` in
  `work/apk_native/lib_x86_libVirtualFamilies2.so`.
- The mobile Settings constructor
  `_ZN16theOptionsDialogC1EPc15DialogColorEnum` (`0x1074A0`) contains the
  first-generation gate before creating the Evict button. The key bytes at
  `0x10784B` are `83 38 00; 0F 85 CE 00 00 00; 83 78 04 01;
  0F 8F C4 00 00 00`, which skip setup unless the family-tree state is active
  and the generation field at `+4` is `<= 1`.
- Mobile `theOptionsDialog::EvictFamily()` calls the family-tree evict/reset
  path, resets the villager manager, sets `CAdoptionScene+0x1C` to `2`, and
  writes scene `6` into the game-state scene field. This matches the desktop
  code shape already present in `theOptionsDialog.obj`; the mobile difference
  is visibility policy, not a separate eviction routine.
- For PC patches, keep the click handler native. The safe mod point is the
  Settings constructor gate: vanilla/mobile parity is first-generation-only,
  while the B74 any-generation mod should only alter the gate and leave
  `theOptionsDialog::EvictFamily()` / `CFamilyTree::EvictFamily()` untouched.

## 2026-07-07 - Settings Evict Button Re-Enable

- B118 returns to the known-working B72 constructor approach after the B74
  state-preserving gate failed to show the button in current builds. The patch
  NOPs both Settings constructor skip branches at `theOptionsDialog::.ctor`
  `+0x2DA` (`0F 85 80 00 00 00` -> `90 90 90 90 90 90`) and `+0x2E7`
  (`7D 77` -> `90 90`).
- The generation compare bytes at `ctor+0x2E0` remain stock
  `83 3D 04 00 00 00 02`; they are no longer reached as a blocker because the
  second branch is disabled. This makes control ID `4` construct in every
  Settings dialog while preserving the native confirmation/click path.
- The click path is still stock/mobile-derived:
  `theOptionsDialog::EvictFamily()` -> `CFamilyTree::EvictFamily()` ->
  `CFamilyTree::Reset()`, villager-manager reset, adoption scene state `2`, and
  scene `6`. No new save-state clearing routine or villager/furniture behavior
  code was added.

## 2026-07-03 - Independent Generated Outfit Tray Items

- Stock clothing item evidence and `theMainScene::HandleMouseDown` show
  `0x49` is the male outfit tray item and `0x4A` is the female outfit tray
  item. Stock `CInventoryManager::GetOutfit(0x49)` reads
  `InventoryManager+0x468`; `GetOutfit(0x4A)` reads
  `InventoryManager+0x46C`.
- B69-B74 generated outfit purchases reused those stock tray IDs and changed
  the shared `InventoryManager` body field. That explains the observed bug:
  buying another generated outfit of the same gender changed every existing
  outfit item in the toolbar.
- B75 stores generated outfit IDs directly in `CToolTray` slots:
  female rows `0x400-0x435`, male rows `0x440-0x475`. `ToolTray.obj` patches
  `CToolTray::GetToolInHand()` and `CToolTray::GetToolInUse()` to normalize a
  selected synthetic ID to stock `0x4A`/`0x49` only for vanilla main-scene
  checks, while `CInventoryManager::GetOutfit()` decodes the body from the
  selected synthetic ID.
- The build also uses the six clean base-game runtime sprite sheets in the
  modified build's `OUT/Images` folder before generating outfit icons and separated
  `Images/VillagerBodies/<Gender>/Body_##/{bodies,actions,sit}/Frame##.png`
  frames. The game uses build-local `Images/*.png`; it does not point to the
  source `originalimages` folder at runtime.

## 2026-07-03 - Holiday Outfit Body Apply State

- The generated outfit store's visible rows decode correctly:
  female `0x432-0x435` and male `0x472-0x475` are body values `50-53`.
  The remaining body-49 fallback happened during placement, after the ToolTray
  helper normalized a synthetic item to stock `0x4A`/`0x49`.
- `_VF2NormalizeOutfitToolInHand(void* tray, int activeFlagOffset)` now keeps
  separate selected synthetic IDs for `GetToolInHand` (`0xA4`) and
  `GetToolInUse` (`0xA5`). `_VF2GetOutfitStoreBodyValue(int itemId)` checks the
  in-use synthetic ID first, then the in-hand synthetic ID, so a stock-ID query
  cannot clear the Holiday synthetic ID before `CInventoryManager::GetOutfit`
  decodes body `50-53`.
- `sync_holiday_body_runtime_frames()` now prefers repo-local
  `generated/VillagerBodies/<Gender>/Body_50..53/...` frames before any Holiday
  archive or expanded-sheet fallback. The expanded sheet path is now a last
  resort, not the primary source for Holiday art.

## 2026-07-03 - Holiday Ornaments Collection

- The mobile Holiday Ornaments collection art is in `work/vf2_obb/assets/tp225`.
  `tp225.pvr` is old RGBA4444 PVR data; the reliable image payload size is
  header word `5`, not word `3`. Atlas coordinates are bottom-origin.
- The desktop collectible counter and save-state ranges already cover dormant
  carrying values `0x9E-0xA9`, and `CAchievement` save/load/reset already
  serialize `0x125` 12-byte records. B76 therefore adds visible tables and
  hooks without increasing either save-state block.
- `patch_collectable_item_holiday_ornaments()` registers base carrying value
  `0x9E` with the same full-yard `CCollectableItem::AddSpawnArea` rectangles
  used by stock full-yard collections. Stock `CCollectableItem::Update/Add`
  still owns the spawn gate, including normal odds and the Lucky Rock odds
  change.
- `patch_collection_scene_holiday_ornaments()` appends Collections page `5`,
  item IDs `0x9E-0xA9`, generated `Images/CollectionOrnaments/*.png` icons,
  and `Images/collection-ornaments_background.png`. `VF2CollectionPageCount()`
  avoids changing `CCollectionScene` object size by asking
  `CCollectableItem::CollectionCount()` for the active page base.
- `patch_achievement_holiday_ornaments()` appends goal row `0x5F`
  (`Ornamentologist`, target `12`), widens visible/order bounds from `0x5F` to
  `0x60`, appends the ID to `achievementOrder`, and bumps the Goal Collector
  target from `12` to `13`.
- B84 disables this native-table graft in normal builds behind
  `VF2_ENABLE_HOLIDAY_ORNAMENTS=1`. The experimental page made the Collections
  screen crash and made the game report `60` collectibles; stock release builds
  now leave the base four collection pages and `48` total collectibles active.
  Re-enable the flag only for isolated research builds until the page/object
  size assumptions are proven in-game.
- `CCollectableItem::WasItemSpawned(ECarrying)` is exact-ID only, while
  `CCollectableItem::Find(CVillager&, ECarrying, ldwPoint&)` contains manual
  hard-coded family ranges for base collectible requests such as `0x73`,
  `0x79`, `0x7D`, `0x81`, and `0x83`. Holiday Ornaments use base request
  `0x9E` with spawned variants `0x9E-0xA9`, so B86 adds explicit `0x9E`
  family handling to both functions. Without this, the spawn gate does not see
  an active variant and villager pickup searches can miss spawned ornaments.
- The supplied `Holiday Collectibles` folder contains a real
  `Collection_ChristmasOrnament_Frame.png` (`940x732`), 12 collected ornament
  images, 12 matching `*-Placeholder.png` images, and a decorative
  `Collection_ChristmasOrnament_CandyCane.png` with no placeholder pair. B87
  keeps the collectable range at exactly 12 IDs, bakes the placeholders into
  the frame background, copies the 12 collected images as draw overlays, and
  replaces `Images/collectables_small.png` with the supplied `240x640` sheet.

## 2026-07-03 - Playhouse Child-Only Autonomous Gate

- `CVillager + 0x6A54` is the age counter used by stock age selectors.
  `CVillagerManager::SelectRandomLivingChild()` accepts villagers with age
  `< 0x118`; `AdultPopulation()` accepts villagers with age `>= 0x118`.
- `CVillagerAI::DecideWhatToDo()` evaluates autonomous candidate age gates from
  each `0xD0`-byte candidate: max age at candidate offset `+0x48`, min age at
  `+0x4C`. It rejects a candidate when villager age is greater than max or less
  than min.
- B77 changes the Playhouse spontaneous candidate (`0x11E`,
  `CBehavior::PlayOnPlayStructure`) from a generic enabled candidate to an
  explicit child-only candidate with max age `0x117`. This affects only
  autonomous candidate selection; drop/click behavior dispatch is untouched.

## 2026-07-03 - VF3 TV Generated Frame Enum Order

- B70 made the private VF3 TV animation strips mirror-correct, but B77
  screenshots still showed one generated furniture orientation using the
  opposite slant.
- A contact sheet from B77 generated assets showed VF3 TV furniture frame `0`
  is the generated source sprite and matches the private non-East animation
  label, while frame `1` is the horizontal mirror and matches the private East
  animation label. This frame order is opposite the stock TV donor's enum
  order.
- `FurnitureInfo` offsets `+0x24` and `+0x28` are the frame `0` and frame `1`
  floating-animation enum slots for these TV records. B78 swaps only the
  added VF3 TV private enum assignments at those offsets; base
  `TVAnimBig*.png` / `TVAnimSmall*.png`, click behavior, furniture behavior,
  and villager behavior remain untouched.

## 2026-07-03 - VF3 TV Patcher Contract Guard

- `work/patch_mobile_furniture_pack.py` now calls
  `validate_vf3_tv_animation_contract()` before writing `patch-manifest.json`.
  The guard verifies generated `FurnitureManager.vf3_tv_animation_records`
  map frame `0` to the non-East private strip and frame `1` to the East
  private strip for the Large, Small, and Father's Favorite VF3 TVs.
- The same guard checks the private `CFloatingAnim` entries, generated graphics
  descriptors, runtime animation names, and missing-asset list. A future build
  that reintroduces the swapped B77 frame enum order fails during patcher
  generation instead of producing a bad build or offline-patcher bundle source.
- B85 keeps the private VF3 TV strip approach but insets the generated screen
  boxes to reduce minor bezel bleed: Large `5,6,63,77`, Small `3,3,46,57`,
  and Father's Favorite `8,10,90,96`. East/west variants use matching boxes so
  behavior and orientation remain unchanged.
- B88 reverts those B85 inset boxes after in-game screenshots showed the
  overlays became more misaligned. The private VF3 TV animation source boxes
  are back to the B84 values: Large `4,5,65,80`, Small `2,2,48,60`, and
  Father's Favorite `5,8,96,104`; no TV behavior, fmap, stock animation, or
  villager behavior path changes are part of this revert.

## 2026-07-03 - Desktop Runtime DLL Packaging

- The rebuilt EXE links through local import libs for `SDL2.dll`,
  `SDL2_image.dll`, `libpng16-16.dll`, `libjpeg-9.dll`, and `zlib1.dll`, and
  `work/vf2_fmod_thunks.cpp` loads `fmod.dll` at runtime.
- B79 adds `sync_desktop_runtime_dlls()` to copy those six DLLs into the build
  root beside `Virtual Families 2 - Additive Mobile Furniture Pack.exe`.
  Missing DLLs now fail the patcher run instead of producing a release folder
  that cannot launch after extraction.
- B79-B81 still failed before the game window on machines lacking the VC90
  side-by-side runtime requested by the packaged `SDL2_image.dll`. The DLL
  embeds a `Microsoft.VC90.CRT` dependency for x86 version `9.0.21022.8` and
  imports `MSVCR90.dll`.
- B82 adds a private `Microsoft.VC90.CRT/` assembly folder beside the EXE with
  `msvcr90.dll`, `msvcp90.dll`, `msvcm90.dll`, and
  `Microsoft.VC90.CRT.manifest`. The manifest identity matches the
  `SDL2_image.dll` request while the files come from the latest local x86 VC90
  CRT WinSxS directory.

## 2026-07-03 - Holiday Outfit Body Value Lookup

- The generated outfit store IDs already map Holiday rows to body values
  `50-53`: female `0x432-0x435`, male `0x472-0x475`. The remaining clamp was
  in the runtime body/link lookup path, not the store row table.
- `patch_holiday_body_lookup()` widens the two `CAnimManager`
  `GetScaledLinkToNextPt` / `GetScaledLinkToPrevPt` body overloads from valid
  rows `0-49` to `0-53`. The stock invalid-row fallback remains row `49`, so
  bad body values do not try to index arbitrary additive rows.
- `vf2_villager_body_frames.cpp` now applies `VF2SafeFallbackBody()` before any
  native `DrawScaled` fallback: negative body IDs use row `0`, stock rows
  `0-49` pass through, and values `>=50` fall back to row `49` unless they are
  successfully handled by the folder-backed Holiday renderer.
- B89 supersedes the link-widening part of B80 for normal folder-backed
  builds. Because the stock `female/male_{bodies,actions,sit}00.png` sheets
  remain 50 rows, `CAnimManager` link lookup must keep its stock row-49
  fallback for Holiday body values `50-53`. The folder-backed renderer still
  draws the Holiday body art, but head/body attachment points use the same
  row-49 geometry that `_normalize_holiday_body_frame()` used as its template.

## 2026-07-03 - VF3 TV Furniture Recognition

- `CBehavior::WatchTVDispatch` uses the stock TV route:
  `CFurnitureManager::FindFurniture(object 0x0D, FeetPos, ...)`, then says
  the `0x837` "no TV" string if the returned furniture object is not `0x0D`.
  The new VF3 TV furniture records can match donor `0x1F3` and still fail this
  lookup if their `.fmap` content block is not loaded or lacks TV object cells.
- `CFurnitureManager::FurnitureHasObject` reads the content map pointer from
  `sFurnitureInfo + 0x58` and delegates to `CContentMap::HasObject`.
  Therefore added TVs must have valid `Assets/<sprite>.png.fmap` files loaded
  through `CFurnitureManager::LoadFmap`; behavior fields alone are not enough.
- `CFurnitureManager::LoadFmap` has a separate max-offset guard at function
  offset `0x1E`: `lea eax,[esi-0x1AD] ; cmp eax,0xFB ; ja skip`.
  B81 patches that immediate to the expanded furniture max offset so appended
  TV IDs `0x324-0x326` can load fmaps.
- B81 also seeds `OUT/Assets` from `work/vf2_obb/assets` when the output
  folder starts empty, copies `TVFlatScreenStd.png.fmap`, and regenerates the
  three VF3 TV fmaps from the VF3 sprite alpha footprint while preserving the
  stock TV fmap's nonzero cell payload values. This keeps base TV behavior and
  base TV assets untouched.

## 2026-07-03 - Full Runtime Payload Packaging

- B79-B82 had the runtime DLLs but B82's `Images/` folder contained only
  generated/changed additive art. Launch probes showed B82 exits with code `3`
  when using the partial B82 `Images/` tree, but the same B82 EXE stays running
  when paired with a complete vanilla `Images/` payload plus the generated
  additive overlay.
- `work/patch_mobile_furniture_pack.py` now calls
  `sync_vanilla_runtime_payload()` before additive image generation. Normal
  builds use workspace-local runtime inputs or an explicit
  `VF2_VANILLA_RUNTIME_DIR`; required runtime files are `ldw.ini`, `wc.dat`,
  `icon.bmp`, `Images/`, and `Sounds/`.
- `validate_runtime_payload_contract()` fails future builds if key base images
  (`loading.jpg`, `MapX0Y0.jpg`, `female_heads00.png`, `TVAnimBig*.png`,
  `TVAnimSmall*.png`, etc.), the full sound payload, SDL DLLs, or the VC90
  private assembly are missing. B83's validated output has 8134 image files and
  317 sound files, and a launch smoke test stayed running.
- `work/offline_vf2_patcher.py` supports manifest `runtime_requirements` so the
  offline patcher can refuse to patch an incomplete copied game folder before
  applying byte or asset records.
- B93 follow-up hardens runtime seeding: normal builds now search only
  `VF2_VANILLA_RUNTIME_DIR` and `work/vanilla_runtime_payload`. Older modded
  output folders are no longer automatic fallback sources; they require the
  explicit diagnostic opt-in `VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK=1`.
- The current correct package-structure baseline is the user-provided GitHub
  release asset `Current VF2 Modded Build! B98.zip` on tag
  `B98-current-vf2-modded-build`, size `353,946,169`, SHA-256
  `63ad60cfb963008bed7cc6706f05146ed7ed6a8f40aa785204c9ccefa36dbf55`.
  Its release-root folders are `Assets/`, `Images/`, `OptionalVisualMods/`,
  `Original Virtual Families 2 Assets/`, and `Sounds/`. Future release
  packages should use a short folder name such as `VF2-B##-Release`, preserve
  this package shape exactly, and replace only the packaged EXE with the newest
  build EXE; `ReferenceAssets/` and `Microsoft.VC90.CRT/` are legacy package
  folders and should not be reintroduced into release roots.

## 2026-07-03 - Stock Collections and Runtime Geometry Payload Rollback

- Stock PC `CCollectionScene::gCollectable` already has five pages/60
  collectibles: `0x4F-0x72`, `0x86-0x91`, and `0x92-0x9D`. Earlier notes that
  described stock as four pages/48 were wrong.
- Mobile VF2 1.7.16 extends `CCollectionScene::sm_sCollectable` to
  `6 * 12 * 12 = 864` bytes and has a 72-dword `gCollectable` sequence that
  appends Holiday Ornament carrying values `0x9E-0xA9`.
- B89 was generated with an incomplete Holiday Ornament collection hook, so
  opening Collections could enter unfinished native-table paths while the game
  still reported the stock PC `60` collectibles.
- B90 tried to seed a full runtime `Assets/` payload and require geometry
  sentinels (`cmap.dat`, `wpts.dat`, `animpts.dat`, `anims.dat`, `lsmap.dat`),
  but that diverged the modded runtime too far and broke in-game behavior.
- B91 removes the B90 `sync_runtime_assets_payload()` step and removes the full
  `Assets/` validator requirements. Normal builds should go back to only the
  generated/additive `.fmap` files needed by the mobile furniture additions
  until the map/pathing asset format is understood and explicitly approved.

## 2026-07-03 - Holiday Ornament Collectible Array and Pickup Path

- B92 enables Holiday Ornaments by default and leaves
  `VF2_ENABLE_HOLIDAY_ORNAMENTS=0` as a stock-collections diagnostic switch.
- `patch_collection_scene_holiday_ornaments()` appends the mobile sixth page to
  `CCollectionScene` tables: `sm_sCollectable`, `gCollectionFrame`,
  `gCollectionLabel`, `gLabelInfo`, and `gCollectable`. A unit test now asserts
  the patched `gCollectable` values equal the mobile 72-entry sequence.
- `CCollectable` owns a separate observer dispatch table used by
  `CCollectable::Carry`, `Drop`, and `ProcessNearbyCollectables`. Stock PC
  constructor registrations stop at `0x9D`; B92 inserts registrations for
  `0x9E-0xA9` so spawned ornaments can be carried, dropped, removed, and counted
  through `CCollectableItem`.
- `CCollectableItem::Drop()` already stores counts in the saved collection-count
  array for the `0x9E-0xA9` range after the B86 family patches; the missing
  observer registration explained why visible ornaments could behave like
  non-pickup objects.

## 2026-07-03 - Mobile Holiday Ornament Goals and Spawn Mechanics

- Mobile VF2 1.7.16 `CCollectableItem::Reset()` inlines spawn-area registration
  instead of calling exported `AddSpawnArea`, but the resulting records match
  the PC patcher contract: four full-yard rectangles with carrying base `0x9E`.
- The four mobile ornament spawn rectangles are `(0x634,0x0B4,0x764,0x302)`,
  `(0x112,0x0C4,0x2FA,0x1BD)`, `(0x098,0x178,0x19D,0x26F)`, and
  `(0x08D,0x568,0x137,0x750)`.
- Mobile `CCollectableItem::CollectionCount()` has an explicit sixth-family
  fallback for `0x9E`; the rarity helpers split ornaments into common
  `0x9E-0xA1`, uncommon `0xA2-0xA5`, and rare `0xA6-0xA9`.
- Mobile `achievementList` row `0x5F` is Ornamentologist with target `12`.
  Mobile Goal Collector row `0x54` has target `13`. The shared third row field
  is platform-wide (`0x23E` in mobile, `0x1ED` in PC), so additive PC rows
  should keep the PC value while mirroring the mobile row IDs and targets.

## 2026-07-04 - Consolidated Mobile Feature Analysis

- `docs/mobile-vf2-feature-analysis.md` now consolidates the mobile VF2
  implementation evidence for Holiday outfits/furniture, non-PC furniture,
  Holiday Ornaments, Island Events, mobile furniture behavior routes, and
  visible mobile purchases.
- Mobile Holiday Ornaments are native collectible IDs `0x9E-0xA9`, collection
  page `5`, achievement row `0x5F`, and Goal Collector row `0x54`. The pickup
  path requires both `CCollectionScene` table growth and `CCollectable`
  observer registrations so `Carry/Drop/ProcessNearbyCollectables` reach
  `CCollectableItem`.
- Mobile holiday and furniture behavior names are directly recoverable from
  native symbols (`CBehavior::AdmiringXmasTree`,
  `KidsCheckXmasStockings`, `AdultsSaveSantasCookies`,
  `LieInHammock`, `PlayingFoosball`, `ListenToRadio`, etc.), but exact
  action-step timing and effects still require per-method disassembly.
- Added Island Events are split between registered PC event shells and native
  outcomes. Only a few outcomes have experimental PC mappings; the remaining
  mobile `CEvent*::ImpactGame` methods need low-level mapping before they can
  be treated as implemented.
- Mobile visible purchases should be modeled as direct upgrade/effect helpers:
  Brokerage Account, Food Club, Health Plan, and Lucky Rock use normal store
  rows/icons plus explicit helper state rather than IAP UI in the PC port.

## 2026-07-04 - Clean Base Asset Payload Source

- `work/vanilla_runtime_payload` has been populated from the user-supplied
  clean base-game asset folder
  `C:\Users\Owner\Downloads\Originnal Virtual Families 2 Assets`. Its
  `originalimages` and `originalsounds` folders are
  normalized to build-local `Images` and `Sounds`; the supplied `Assets` folder
  is kept in the workspace for reference but normal builds still seed only
  `Images` and `Sounds`.
- `work/patch_mobile_furniture_pack.py` now accepts a clean asset payload as
  the canonical seed source even when launcher root files (`ldw.ini`, `wc.dat`,
  `icon.bmp`) are not present. Final release validation still requires those
  files, the desktop DLLs, and the VC90 private assembly before a package can
  be considered runnable.
- Future builds should use this workspace-local clean payload, not external
  "official copy" folders or old modded output folders, for base-game art and
  sound seeding.

## 2026-07-04 - Previous Build Baseline Rule

- Future B-builds should start by copying the most recent previous completed
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B*` folder into the new
  output folder, then overlay the workspace clean base asset payload and the
  regenerated additive/native changes.
- `work/patch_mobile_furniture_pack.py` now implements this with
  `seed_from_previous_build()`. If `VF2_PATCH_OUT` names a B-build, the source
  selector chooses the highest lower B-number; otherwise it chooses the highest
  available B-build. `VF2_PREVIOUS_BUILD_DIR` can override the source when a
  specific previous folder should be used.
- This rule preserves runtime packaging fixes, DLLs, launcher files, and
  additive assets from the last known build while still refreshing clean
  base-game `Images` and `Sounds` from `work/vanilla_runtime_payload`.

## 2026-07-04 - Offline Patch Bundle Exporter

- `work/export_offline_patch_bundle.py` can now export a generated build folder
  into the `offline_vf2_patcher.py` manifest/payload shape. It writes
  `manifest.json`, copies changed asset payloads under `payload/`, records
  SHA-256 and size for each asset, assigns feature-toggle requirements, and
  emits runtime requirements for complete vanilla game folders.
- The exporter can optionally diff a supplied vanilla EXE against the patched
  build EXE into length-preserving byte patch records. It refuses byte export
  when executable sizes differ, keeping the current JSON patch contract honest.
- `--asset-mode additive` now exports only assets referenced by the generated
  build manifest; `--asset-mode all` remains available for diagnostic
  full-folder diffs. The pruned B93 asset-only preview at
  `outputs/Offline-Patch-Bundles/B93-asset-preview` generated 713 asset
  records: 448 Holiday outfit records, 229 mobile furniture records, 13 Holiday
  Ornament collection records, 11 outfit-store records, and 12 VF3 TV
  asset/recognition records. This is schema-readable by the patcher but still
  needs vanilla EXE target metadata and native byte records before release use.
- `Unneeded crap\Virtual Families 2.exe` is the current workspace-local vanilla
  EXE candidate for offline patch metadata: size `1,881,088`, SHA-256
  `67e8cf073be89b9699f4f7a19bc1105ceae865cdaefe98abd0c1e59e5f0d6bc4`.
  B93's patched EXE is `1,677,824` bytes, so full-EXE byte diff export is
  invalid; the exporter records `native_patch_status=byte_diff_skipped` and the
  native records need to come from object/linker patch metadata.
- Build manifests can also contain explicit native byte triples that are not
  final EXE offsets. The B93 Settings Evict constructor has three
  `settings_menu.evict.constructor_patches` records with object/function-
  relative offsets; the exporter now preserves these under
  `native_patch_sources` with `scope=object_relative` and
  `apply_status=not_file_offset` instead of placing them in `patches[]`.

## 2026-07-04 - B94 Timed Hook Stability Gates

- The delayed runtime crash is most likely tied to timed mobile subsystems that
  were enabled before their PC parity paths were proven. B94 leaves Holiday
  Ornament collection/spawn/pickup hooks and mobile Island Event table grafts
  disabled in normal builds, with `VF2_ENABLE_HOLIDAY_ORNAMENTS=1` and
  `VF2_ENABLE_ISLAND_EVENTS=1` reserved for isolated tests.
- Holiday outfit tool-tray normalization converts generated outfit item IDs back
  to the stock male/female outfit items (`0x49/0x4A`) before the vanilla apply
  path sees them. The helper now stores the last generated outfit by gender in
  `gVF2LastSyntheticOutfitByGender[2]`, letting `VF2GetOutfitStoreBodyValue`
  recover body values `50-53` instead of falling through to body `49`.
- Normal B94 builds intentionally keep the stock PC collection table at 60
  entries until the mobile Holiday Ornament page, pickup observers, collection
  count, and Lucky Rock odds are all verified together.

## 2026-07-04 - Holiday Outfit Apply Field Sync

- The outfit apply path can still observe the vanilla `CInventoryManager`
  male/female outfit body fields after a synthetic tray item has normalized to
  stock item `0x49` or `0x4A`. B95 updates those stock fields whenever a
  generated outfit is purchased or selected through
  `_VF2NormalizeOutfitToolInHand`, so Holiday body rows `50-53` are available
  even if the later apply step falls through to the stock body lookup.
- VF3 TV animation validation should not require loose source frames from
  `Downloads\Sprite` when a build has already inherited the generated runtime
  animation strips from the previous build. B95 treats build-local
  `Images/*TV*Anim*.png` strips as sufficient for validation.

## 2026-07-04 - Holiday Outfit Final Apply Resolver

- In-game B95 evidence showed the store and tool tray can both be correct while
  applying a Holiday outfit still writes body `49`. The final body write is in
  `theMainScene::HandleMouseDown`, not only `CInventoryManager::TakeOne` or
  `CInventoryManager::GetOutfit`.
- The stock male branch at `HandleMouseDown + 0xCE3` applies tray item `0x49`;
  the stock female branch at `+0xD83` applies tray item `0x4A`. Each branch
  calls `CInventoryManager::GetOutfit()` and stores the returned body at
  `CVillager+0x6A84`.
- B96 redirects those two callsites to
  `_VF2ResolveOutfitBodyForApply(stockItem, villagerGender)`. The helper reads
  the selected synthetic outfit from `ToolTray` slot storage before using the
  gendered last-synthetic fallback or vanilla `InventoryManager` body fields.
  This is the current modification point for Holiday body values `50-53`
  falling back to `49` during drop/apply.
- Applying true body values `50-53` also exposed the live house-view renderer
  as a separate crash path. `CVillagerManager::DrawVillager` draws the live body
  through `CSceneManager::DrawScaled` and was not covered by the earlier
  `CVillager::DrawDetailVillager` / `DrawEventVillager` redirect. B96 now
  retargets `DrawVillager + 0x454` to `_VF2DrawSceneVillagerBodyFrame`, using
  the folder-backed Holiday frame table before any stock sheet row can receive
  `50-53`.

## 2026-07-04 - B97 Outfit Apply Stability Revert

- B96 proved body values `50-53` can reach the renderer, but in-game testing
  showed generated Outfit-section items now crash when dropped on villagers.
  The likely risky point is the direct `theMainScene::HandleMouseDown`
  callsite replacement at `+0xCE3` / `+0xD83`, not the store or tray icon path.
- B97 leaves the stock `theMainScene` `CInventoryManager::GetOutfit(0x49/0x4A)`
  calls intact and instead strengthens the existing
  `_VF2GetOutfitStoreBodyValue` hook. When the stock item ID is requested, the
  hook now inspects `ToolTray::GetToolInUse()` and `ToolTray::GetToolInHand()`
  directly via `VF2SelectedSyntheticOutfitFromToolTray()` to recover the
  selected generated outfit body value.
- The abandoned paired head-draw experiment was not carried forward. The only
  live-world Holiday body draw redirect remains
  `CVillagerManager::DrawVillager + 0x454`, matching B96's shipped renderer
  coverage.

## 2026-07-04 - B98 String Lookup Bound Fix

- In-game B97 testing showed male generated Outfit rows displayed icons but
  male body `04` and later showed `Unknown String Id!!!!`. Male body `03`
  used string IDs `0xC23/0xC24`; male body `04` starts at `0xC25/0xC26`.
- The generator incorrectly computed `theStringManager`'s lookup/guard max as
  `ORIG_STRING_ONE_PAST_MAX + len(new_rows)`, producing `new_one_past_max =
  0xC25`. Stock desktop has a gap between string table row count `0xA5D` and
  one-past StringId `0xA69`, so row count and maximum StringId cannot be
  advanced by the same delta.
- B98 now computes lookup/guard one-past from the highest actual generated
  StringId (`max(new_rows.string_id) + 1`). The normal B98 manifest reports
  `new_one_past_max = 0xC8B`, covering the last male Holiday outfit string
  `0xC88` and behavior labels `0xC89-0xC8A`.

## 2026-07-04 - Superseded Local B98 Sprite Regression

- The current generator exposes 111 additive/mobile furniture sprite paths in
  `patch_mobile_furniture_pack.ITEMS`. An older local B98 extraction only
  contained 29 of those additive paths under `Images/Furniture`; 82 were absent
  from that local copy even though their rows still exist in the generator.
- Those missing sprites were recoverable from older complete local builds,
  especially `outputs/VF2-Mobile-Furniture-With-Island-Events-B74-Any-Generation-Evict`.
  They include Holiday/Thanksgiving/Birthday decor, LDW posters, mobile
  recolor furniture, and the VF3 living-room couch/loveseat strips.
- A recovery dump was generated at
  `outputs/VF2-Mobile-Exclusive-Furniture-Sprites-Dump` and copied to
  `C:\Users\Owner\Downloads\VF2-Mobile-Exclusive-Furniture-Sprites-Dump`.
  The dump preserves hashes and source-build evidence in `manifest.json`,
  with 29 sprites under `Present_In_B98` and 82 under
  `Recovered_Missing_From_B98`.
- The user-provided final cleaned B98 ZIP supersedes the incomplete local copy
  and is now the GitHub source of truth for future builds. Its release asset is
  `Current VF2 Modded Build! B98.zip` on tag `B98-current-vf2-modded-build`,
  size `353,946,169`, SHA-256
  `63ad60cfb963008bed7cc6706f05146ed7ed6a8f40aa785204c9ccefa36dbf55`.

## 2026-07-04 - B99 Evict and Invisible Hammock Parity

- B99 keeps the stock/mobile `theOptionsDialog` Evict state guard at constructor
  offset `+0x2DA` (`0F 85 80 00 00 00`) and only relaxes the generation gate:
  compare byte at `+0x2E6` changes `2 -> 0`, and the branch at `+0x2E7`
  changes `jge` (`7D 77`) to `jle` (`7E 77`). The existing
  `theOptionsDialog::EvictFamily()` -> `CFamilyTree::EvictFamily()` handler is
  untouched.
- Invisible Hammock is additive furniture item `0x30C` with donor `0x1E1`
  (`HammockStd`). Its `CFurnitureManager::itemInfo` row now has a contract that
  all non-identity, non-store, non-string fields match donor `0x1E1`; item type
  remains `5`.
- `CHotSpot::Hammock(CVillager&)` is the stock drop/spontaneous eligibility
  predicate for the native hammock behavior. B99 retargets the existing stock
  `FurnitureManager.IsInWorld` call to `_VF2EitherHammockInWorld`, which returns
  true when either base `0x1E1` or invisible `0x30C` is present, then continues
  through the original `eBehavior_LieInHammockNoLeadIn (0x24)` route.
- `sync_behavior_assets()` already copies `InvisibleHammock.png.fmap` from
  `HammockStd.png.fmap`, preserving the base hammock object/collision geometry
  instead of inventing a separate invisible-hammock behavior grid.

## 2026-07-04 - B99 Offline Patcher Full-Payload Test

- `work/offline_vf2_patcher.py apply` now accepts `--exe
  "...\Virtual Families 2.exe"` as an alternative to `--game-dir`. The game
  directory is inferred from the EXE's parent folder, and the name must be the
  canonical `Virtual Families 2.exe`.
- `work/export_offline_patch_bundle.py` supports `--asset-mode full`,
  `--include-exe-replacement`, and `--include-patcher-scripts`. Full mode emits
  every generated build file except patcher/build metadata such as
  `patch-manifest.json`; EXE replacement writes a `core_executable` asset
  record with `expected_target_sha256` for the vanilla EXE and a payload copy of
  the modded EXE named `payload/Virtual Families 2.exe`.
- The B99 test bundle was exported to `outputs/VF2-B99-Offline-Patcher-Full`
  and copied to `C:\Users\Owner\Downloads\VF2-B99-Offline-Patcher`. It contains
  `manifest.json`, `offline_vf2_patcher.py`, `offline_vf2_patcher_gui.py`,
  `Apply_B99_Patcher.bat`, `Launch_GUI.bat`, and the full `payload/` tree.
- Smoke test: starting from a folder containing only workspace-local vanilla
  `Virtual Families 2.exe` SHA-256
  `67e8cf073be89b9699f4f7a19bc1105ceae865cdaefe98abd0c1e59e5f0d6bc4`, the
  patcher created `.vf2_patch_backups/...`, recreated the B99 support folder
  shape (`Assets/`, `Images/`, `OptionalVisualMods/`,
  `Original Virtual Families 2 Assets/`, `Sounds/`, root DLLs), and replaced
  the EXE with SHA-256
  `9a713d38e830dcfb2fe1f4f054c36f1340d772c9e28c2abb96501137ee164ea1`.

## 2026-07-04 - B99 Offline Patcher PE-Structure Matching

- The user-provided vanilla EXE at
  `C:\Users\Owner\Downloads\Virtual Families 2\Virtual Families 2.exe` is size
  `1,511,424`, whole-file SHA-256
  `1582d9e84e1c32f51475be17335c5137c592cebf809748d401ccef99a32b73c3`, PE32
  with five sections. The `.text` raw section SHA-256 is
  `88c37a9989b2ad51429aca3a8e9aa9383914c9312fac2995dc4551a49ec4dc5e`.
- `work/offline_vf2_patcher.py` now computes a `pe32-section-raw-v1`
  fingerprint from the PE header and section table. Target EXE validation
  passes when either the exact whole-file SHA-256 matches or the PE section
  structure and raw section hashes match; overlay/certificate bytes are ignored
  by the structure match.
- `work/export_offline_patch_bundle.py` writes `target_files[].pe_structure`
  and EXE-replacement `asset_patches[].expected_target_pe_structure` when a
  vanilla EXE is supplied. A smoke test appended overlay bytes to a copied
  vanilla EXE, changing its whole-file SHA, and the patcher still applied via
  `matched_by=pe_structure` before replacing it with B99 EXE SHA-256
  `9a713d38e830dcfb2fe1f4f054c36f1340d772c9e28c2abb96501137ee164ea1`.

## 2026-07-04 - B100 Invisible Hammock Drop Crash Attempt

- B99's `patch_invisible_hammock_drop_action()` retargeted
  `CHotSpot::Hammock(CVillager&)` to call `_VF2EitherHammockInWorld`, but it
  only NOPed seven bytes of the original ten-byte
  `push 0x1E1; mov ecx, FurnitureManager` setup. That left three `00` bytes
  in the instruction stream before the helper call, which can fault when the
  drop/hotspot path executes.
- B100 attempted to replace the full ten-byte span at
  `HotSpot.obj!?Hammock@CHotSpot@@CA?B_NAAVCVillager@@@Z + 0x04` with NOPs
  and leave the original call opcode at `+0x0E` retargeted to the helper.
  In the linked EXE, the original DIR32 relocation for
  `FurnitureManager` still wrote address bytes into the NOP span. Result:
  this detour remained unsafe and was abandoned.
- Lesson: the invisible hammock should not patch `CHotSpot::Hammock` this way.
  Either remove/retarget every affected relocation, or use the same safer donor
  alias/fmap inheritance route that already works for invisible fireplaces.

## 2026-07-04 - B101 Invisible Hammock Fireplace-Style Alias

- B101 preserves stock `HotSpot.obj` byte-for-byte for the hammock path. Static
  verification compares `work/desktop_obj_files/HotSpot.obj` to the patched
  object and confirms identical SHA-256
  `91a0681a70822b46251dd1b51dfa8f677fcff608d8f09ae5570ec8e18f17d66a`.
- Invisible Hammock now follows the invisible fireplace strategy:
  donor-cloned `CFurnitureManager::itemInfo` fields from `HammockStd` (`0x1E1`),
  a `HandleMouseDown` donor lookup-table alias from item `0x30C` to donor
  `0x1E1`, and `InvisibleHammock.png.fmap` copied from `HammockStd.png.fmap`.
  No `_VF2EitherHammockInWorld` helper or `CHotSpot::Hammock` detour remains.
- The B101 test EXE was copied to
  `C:\Users\Owner\Downloads\VF2-B101-Invisible-Hammock-Fireplace-Style.exe`,
  size `1,650,176`, SHA-256
  `a2fa2382d1e8015446d8bd7fb8df3532b17b731c00e368e889fa5ba164affde7`.

## 2026-07-05 - B102 Invisible Hammock Drop Parity

- B101 still missed the native drop gate: `CHotSpot::Hammock(CVillager&)`
  checks whether base `HammockStd` item `0x1E1` is in-world before dispatching
  the stock hammock action. Donor item fields, click aliases, and copied
  `HammockStd.png.fmap` are not enough when only Invisible Hammock `0x30C` is
  placed.
- B102 restores drop parity with a relocation-safe hotspot patch. It NOPs only
  the five-byte `push 0x1E1` argument in `HotSpot.obj`, leaves the relocated
  `mov ecx, FurnitureManager` instruction intact, and retargets the existing
  call at `?Hammock@CHotSpot@@CA?B_NAAVCVillager@@@Z + 0x0F` to
  `_VF2EitherHammockInWorld`.
- `_VF2EitherHammockInWorld` returns true when either
  `FurnitureManager.IsInWorld(0x1E1)` or `FurnitureManager.IsInWorld(0x30C)`
  is true. The downstream native behavior remains the base
  `eBehavior_LieInHammockNoLeadIn (0x24)` route.
- Linked B102 verification around the hammock function starts:
  `55 8B EC 51 90 90 90 90 90 B9 <FurnitureManager> E8 <helper> 84 C0`.
  The B99/B100 bad byte patterns are absent. Test EXE:
  `C:\Users\Owner\Downloads\VF2-B102-Invisible-Hammock-Drop-Parity.exe`,
  SHA-256 `2dfa924aa4a5deed8e543f72303a18069637956ccc79bdd37b2060d8a2986151`.

## 2026-07-05 - B103 Invisible Heart-Shaped Bed and Patcher Refresh

- Added `InvisibleHeartShapedBed` as a separate additive Bedroom item instead
  of changing `InvisibleAdultDoubleBed`. The new item is `EInventoryItem`
  `0x327`, donor-cloned from the base Heart-Shaped Bed `0x252`, uses
  `Furniture/InvisibleHeartShapedBed.png`, and copies
  `InvisibleHeartShapedBed.png.fmap` from `HeartShapedBed.png.fmap`.
- The existing `InvisibleAdultDoubleBed` remains item `0x314` with donor
  `0x1B7`, `BedAdultBrownStd.png`, and `BedAdultBrownStd.png.fmap`.
- B103 relinked EXE:
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B103-Invisible-Heart-Bed`,
  size `1,650,688`, SHA-256
  `66343cac83b0f835fa6decb7c9abeb8249c04be269d85e85e989e16a528957eb`.
- Refreshed the full-payload offline patcher at
  `outputs/VF2-B103-Offline-Patcher-Full` and
  `C:\Users\Owner\Downloads\VF2-B103-Offline-Patcher-Full`. The helper files
  are now version-labeled (`Apply_B103_Patcher.bat`,
  `README-B103-PATCHER.txt`) instead of hardcoded B99 names. Smoke apply from a
  copied vanilla EXE produced the B103 EXE hash and recreated the B98-shaped
  support folders.
- The B103 patcher can now create a separate modded output folder declared by
  manifest `output.default_folder_name` (`VF2-B103-Modded`) and can validate
  one path while writing another through `asset_patches[].output_file_path`.
  The current full EXE payload verifies `Virtual Families 2.exe` but writes
  `Virtual Families 2 - Modded B103.exe`.
- Optional visual and invisible-furniture files are now true manifest-gated
  assets. `OptionalVisualMods/Custom Lorsieab2 Map Images`, `Menu-Bar`,
  `Transparent-Store-Bar`, `Purple-Decor-Tab`, `Invisible Furniture - Base
  Graphics`, `Invisible Furniture - Transparent`, and `Invisible Furniture
  Backups` are assigned to their matching default-off settings so an unchecked
  option is omitted from a fresh output folder.
- Per-record validation/apply events are written to `process_log` entries in
  patch logs and streamed to the CLI/GUI progress view. The GUI completion
  popup summarizes enabled patches, altered files, the modded game folder, the
  modded save folder, and save-copy guidance.
- Full bundle exports now include `Transparency Log.txt` and can compile a
  small launcher that auto-loads adjacent `manifest.json` in the Tkinter GUI.
  It does not inject into or touch a running game.

## 2026-07-06 - Restoration/Addition Patcher Install Validation

- The offline patcher now treats the official LDW website installation shape as
  a pre-write gate. `verify_runtime_requirements()` checks
  `runtime_requirements.exact_top_level_entries` before `prepare_output_dir()`,
  `create_backup()`, or any asset/byte writes.
- The generated manifest requires these top-level entries: `Assets`,
  `fmod.dll`, `icon.bmp`, `Images`, `ldw.ini`, `libjpeg-9.dll`,
  `libpng16-16.dll`, `Readme.txt`, `SDL2.dll`, `SDL2_image.dll`, `Sounds`,
  `uninst.exe`, `Virtual Families 2.exe`, `Virtual Families 2.url`, and
  `zlib1.dll`.
- `verify_target_files()` now wraps target EXE missing/hash/PE/size/version
  failures with the same invalid-install message, so a wrong EXE or partial
  folder reports the official-download guidance instead of only raw technical
  hash text.
- The GUI display name is `Virtual Families 2 Restoration/Addition Patcher`;
  the Windows-safe launcher filename is
  `Virtual Families 2 Restoration-Addition Patcher.exe`. The GUI now
  auto-populates the modded output path, renders `**bold**` manifest
  descriptions, shows a green bold Apply Patches button, labels Dry Run as
  `Dry Run (Validate Only)`, and puts modified-file rows in the only scrollable
  area of the completion popup.
- `PatchSetting.category` drives GUI grouping without hardcoding setting IDs in
  the UI. Generated manifests use `main` (green) for core/mobile/Holiday
  patches, `optional` (black) for Settings Evict, Island Events,
  visual/invisible/custom additions, and `experimental` (red) for Holiday
  Ornaments, mobile furniture behaviors, Expand game map, and other
  not-yet-proven work. Tk `Text.count(..., "displaylines")` is used to
  auto-size description blocks so long setting descriptions are fully visible.
- Patcher bundle icon assets are source-controlled under `work/assets/` as
  `patcher_icon.png` and `patcher_icon.ico`. The GUI loads the PNG from the
  bundle folder or source `work/assets`, displays it beside the bold title, and
  uses the ICO/PNG for the window icon; the generated C# launcher embeds the
  ICO when `csc.exe` is available.
- `offline_vf2_patcher_gui.main()` uses the generated launcher's adjacent
  `manifest.json` argument only to preload settings. It does not open the
  vanilla-folder picker automatically, and no hardcoded install folder lookup is
  used; the user chooses the vanilla VF2 installation manually in the Patch
  Input section.
- `Add Custom Couches and LDW Posters` is a separate default-off setting for
  the Colorful Couches and LDW Poster/Painting image/fmap payloads. Remaining
  native store-row gating still depends on future per-feature byte/table
  records because the current full bundle uses a verified full modded EXE
  payload.

## 2026-07-06 - Patcher B104 Toggle Rebuild Model

- `prepare_output_dir()` now treats recognized sibling `VF2-*-Modded` folders
  as rebuildable outputs. On a non-dry run it clears the modded folder except
  `.vf2_patch_backups`, copies the vanilla install again, and then applies only
  currently enabled records. This makes unchecking a patch and clicking
  Enable/Disable Patches remove prior optional files/behavior from the modded
  folder without touching the vanilla install.
- `asset_patches` remain copy-only during apply. Source-only payload folders
  (`OptionalVisualMods`, `Original Virtual Families 2 Assets`, and
  `OptionalSongMods`) are copied into `payload/` by
  `export_offline_patch_bundle.py` but are not copied wholesale into the game.
- Optional song mods are exported from `payload/OptionalSongMods/*.ogg` to
  runtime `Sounds/*.ogg` records behind `optional_song_mods` (default off).
  Vanilla song restoration is achieved by refreshing the modded output from the
  user-selected vanilla install; B104 records also carry restore-source metadata
  when `Original Virtual Families 2 Assets/originalsounds/*.ogg` exists.
- Loose optional visual mod images are exported behind
  `optional_visual_mod_graphics` (default off). The folder rule is:
  furniture-like images target `Images/Furniture`, future
  Workshop/Kitchen/Office upgrade images target `Images/Upgrades`, and loose
  animation strips/UI/other images target `Images`.
- Patcher bundles no longer build or ship the generated
  `Virtual Families 2 Restoration-Addition Patcher.exe`. `Launch_GUI.bat`
  starts the GUI, and `Launch GUI.lnk` is generated as an optional iconed
  shortcut when Windows COM shortcut creation succeeds.

## 2026-07-06 - Patcher B105 Launcher and Native Patch Shape

- Prebuilt Windows `.lnk` files are not portable inside release ZIPs because
  their targets are path-specific after extraction. B105 removes generated
  `Launch GUI.lnk` and stale `launch_gui_shortcut.json`; `Launch_GUI.bat`
  remains the supported launcher and resolves scripts with `%~dp0`.
- `manifest.output.default_exe_name` declares the final modded EXE filename.
  `offline_vf2_patcher.py::enforce_modded_exe_name()` renames byte-patched
  `Virtual Families 2.exe` outputs, or removes the ambiguous vanilla-named EXE
  when a renamed asset payload already created the modded executable.
- Asset-only patcher bundles cannot implement native/code/table features such
  as injected behavior hooks or new furniture records. B105 release exports
  should prefer `--include-byte-patches` over `--include-exe-replacement` so
  native changes are applied locally after vanilla EXE validation without
  distributing a ready-made modified game EXE.

## 2026-07-06 - B106 Generation Locks and Self-Contained Optional Payloads

- `work/patch_mobile_furniture_pack.py::apply_generation_lock_distribution()`
  no longer redistributes added furniture across synthetic generations 10-30.
  It preserves each mobile/custom `lock_generation` value from
  `MOBILE_DATA_BY_PATH`; only custom packs whose `custom_pack` starts with
  `Invisible ` are forced to generation `0` for placement/test access.
- The synthetic redistribution was overriding confirmed mobile values such as
  `Furniture/CouchNeonPurpleStd.png -> 19`,
  `Furniture/SofaPlaid.png -> 12`, and
  `Furniture/VF3LargeFlatScreenTV.png -> 12`, which made the store lock
  metadata unreliable.
- Invisible Furniture transparent graphic overrides are now workspace-backed
  assets in `work/assets/invisible_transparent_overrides/`. The generator
  packages `InvisibleMantleFireplace.png` and `InvisibleGrandfatherClock.png`
  from there into `OptionalVisualMods/Invisible Furniture - Transparent`, so
  patcher ZIPs remain self-contained after export.
- `work/export_offline_patch_bundle.py` now emits `white_birds` setting
  metadata for `OptionalVisualMods/bird.png` and `bird_shadow.png`. Optional
  source-backed settings are hidden when their payload files are not present,
  preventing dead checkboxes such as `optional_song_mods` without bundled
  `.ogg` records.
- Store Scroll Bar is a native `CScrollingStoreScene` draw/mouse hook, not an
  asset-only swap. It should remain hidden as a patcher setting until the
  native hook is split into setting-gated byte/table records or an equivalent
  reversible implementation.

## 2026-07-06 - B107 Base Lock Parity and Optional Songs

- `work/patch_mobile_furniture_pack.py::patch_furniture_manager()` appends new
  furniture records after `ORIG_FURNITURE_COUNT * RECORD_SIZE` and preserves the
  original stock `itemInfo` table bytes. A regression now snapshots the stock
  table before and after patching so base-game generation locks cannot be
  flattened by the append path.
- The stock PC table contains 211 records with nonzero lock-generation fields
  (`raw_u32[3]`), so base furniture/unlocks must continue to flow through the
  vanilla lock handling. The outfit-store lock helper returns `-1` for
  non-outfit item IDs so those records fall through to the stock function body.
- B107 restores the optional song payload to the self-contained patcher ZIP by
  exporting `payload/OptionalSongMods/menu.ogg` and `song1-4.ogg` from the last
  known working B104 payload. The generated manifest exposes
  `optional_song_mods` only when those five bundled files exist.

## 2026-07-06 - B108 Relaxed Official EXE Identity

- `work/offline_vf2_patcher.py::pe_structure_matches()` now compares a stable
  PE layout identity instead of the full `pe32-section-raw-v1` fingerprint.
  `pe_structure_identity()` keeps machine/header/layout fields plus section
  names, raw offsets/sizes, virtual offsets/sizes, and characteristics, while
  ignoring whole-file SHA-256, PE timestamp, overlay/certificate bytes, and
  per-section SHA-256.
- The install validator still verifies the selected folder shape through
  `runtime_requirements`, but a valid official `Virtual Families 2.exe` is no
  longer rejected solely because its SHA-256 or section hashes differ from the
  manifest's reference EXE. Byte patch records still validate their own
  `expected_original_bytes` before writing.

## 2026-07-06 - B109 Accepted EXE Layouts and Install Shape

- `work/offline_vf2_patcher.py::normalize_pe_structure_list()` and
  `pe_structure_matches_any()` allow manifests to list multiple accepted
  official VF2 EXE layouts under `pe_structures` /
  `expected_target_pe_structures`. Dry Run no longer requires the selected EXE
  to match a single SHA-256.
- `verify_target_files()` can resolve a missing manifest EXE filename by
  scanning top-level `.exe` files in the selected game folder and accepting the
  one whose PE layout matches an accepted structure. This avoids hardcoding the
  user's folder path or EXE filename while still refusing random binaries.
- `work/export_offline_patch_bundle.py` no longer includes
  `Virtual Families 2.exe` in `runtime_requirements.exact_top_level_entries`.
  The exact folder-shape check covers the official non-EXE runtime contents,
  while the EXE is validated separately by accepted PE structure. New bundles
  also use the exact failure links `http://www.ldw.com/` and
  `http://www.virtualfamilies.com/index.php`.

## 2026-07-06 - B110 Optional Upgrade Graphics and Patch Settings

- `work/export_offline_patch_bundle.py` adds default-on Main settings
  `behavior_patches` and `text_fixes`. Current native behavior/text changes
  still travel through the core modded executable payload until those edits are
  split into narrower byte/table records.
- `invisible_upgrades_graphics` is a default-off Optional setting. Export reads
  creator-supplied PNGs only at bundle creation time via
  `--invisible-upgrades-dir` and `--original-upgrades-dir`, then stores them
  under `payload/OptionalVisualMods/Invisible Upgrades/` and
  `payload/Original Virtual Families 2 Assets/Upgrades Original Graphics/`.
  Runtime records copy invisible PNGs to `Images/Upgrades/*.png`; disabling the
  setting rebuilds from the selected vanilla install.
- `store_scroll_bar` is now visible as a default-off Optional setting. The
  current scroll bar draw/mouse hook is native `CScrollingStoreScene` support in
  the core executable payload, so full native on/off behavior remains a future
  byte/table-record split.
- VF3 TV asset records now require both `core_executable` and
  `vf3_tv_assets_recognition`, preventing a partial patch where private TV
  animation strips are copied but the modded executable that recognizes them is
  not enabled.
- `validate_bundle_asset_sources()` fails export if any asset source or restore
  source is absolute, escapes the patcher bundle, or is missing. This enforces
  self-contained patcher ZIPs with no runtime dependency on Downloads or other
  creator-local folders.

## 2026-07-06 - B111 VF3 Animation Frames and Output-Only Reconfiguration

- VF3 TV top-level animation strips (`Images/VF3LargeFlatScreenTVAnim*.png`,
  `Images/VF3SmallFlatScreenTVAnim*.png`) were correctly gated as
  `vf3_tv_assets_recognition`, but the private per-frame directories under
  `Images/VF3TVAnimations/*/Frame*.png` were still classified as
  `mobile_furniture`. `setting_for_asset()` now classifies the whole
  `Images/VF3TVAnimations/` tree as VF3 TV recognition assets and
  `asset_requires_for_setting()` keeps them paired with `core_executable`.
- `offline_vf2_patcher.py::apply_manifest()` now supports output-only
  reconfiguration. When no vanilla folder is supplied but `--output-dir` points
  to a recognized modded folder, the patcher validates that folder, skips
  vanilla target identity checks and byte patches, and applies checked asset
  records directly.
- Asset records may use `restore_source_path`, `restore_source_sha256`, and
  `restore_source_size`. In output-only reconfiguration, inactive records with
  bundled restore sources are applied as restore records so unchecking a visual
  patch can revert the modded folder without asking for files outside the
  patcher payload.
- `offline_vf2_patcher.py::resolve_expected_exe_target()` centralizes
  path-independent EXE lookup. Target-file checks and EXE replacement asset
  checks now scan top-level `.exe` files for an accepted VF2 PE layout even
  when the manifest path is `Virtual Families 2.exe`, and `prepare_output_dir()`
  skips the discovered vanilla EXE path so renamed vanilla executables are not
  copied into the modded output beside the clearly named modded EXE.
- The optional `vf3_furniture` setting uses runtime file stems, not store
  display names: `SofaPlaid`, `CouchPlaid`, `CouchFlowers`, `CouchStriped`,
  `SofaStriped`, and `FloweredLoveseat`. These image and fmap records now
  require both `core_executable` and `vf3_furniture`.
- The B111 generation-lock payload path introduced standalone
  `Images/GenerationLocks/lock_02.png` through `lock_30.png` records. B112
  removes the old short-strip fallback: export now requires explicit numbered
  PNG frames, so generation 10 uses `lock_10.png`, generation 30 uses
  `lock_30.png`, and missing frames fail the bundle.
- B111 patcher export verification: `Virtual-Families-2-Restoration-Addition-
  Patcher-B111.zip` was generated with 6,692 asset records and 8,590 payload
  files; Dry Run passed against both local accepted VF2 install layouts.

## 2026-07-06 - B112 Lock Art, VF3 TV Strips, and Holiday Body Pixel Policy

- `work/patch_mobile_furniture_pack.py::apply_generation_lock_distribution()`
  now leaves base-game furniture untouched and assigns locks only to added
  mobile/Holiday/VF3 furniture records whose original `lock_generation` is
  `0`. The deterministic seed
  `vf2-mobile-holiday-vf3-generation-locks-b112` shuffled 39 currently
  eligible records into 13 groups of 3 items, spread over generations
  `10, 12, 13, 15, 17, 18, 20, 22, 23, 25, 27, 28, 30`.
- `work/assets/generation_locks/lock_02.png` through `lock_30.png` is now the
  source of truth for lock art. `sync_generation_lock_art()` composes
  `Images/locked.png` from those files and also copies standalone runtime
  icons to `Images/GenerationLocks/`.
- VF3 TV animation strips have a workspace-bundled nonblank fallback under
  `work/assets/vf3_tv_animations/`. `sync_vf3_tv_animation_sheets()` uses these
  strips if creator-local Sprite frame sources are missing, and
  `validate_vf3_tv_animation_contract()` now rejects fully transparent runtime
  sheets.
- Holiday Body animation frames are no longer resized during fallback
  normalization. Runtime frames are transparent-cropped and placed by stored
  offsets; manifest rows record `canvas_size`, `alpha_bbox`, `size`, `offset`,
  and `resized: false`.
- B112 verification produced `Virtual-Families-2-Restoration-Addition-Patcher-
  B112.zip` with 6,692 asset records and 8,590 payload files. Dry Run against
  `C:\Users\Owner\Downloads\Virtual Families 2 test1` validated 6,505 active
  asset records, including `Images\GenerationLocks\lock_30.png`.

## 2026-07-07 - B113 Child Holiday Body Offset Scaling

- Child villagers draw Holiday Body frames through the same folder-backed
  runtime helper as adults, but the game supplies a reduced child scale. The
  B113 `vf2_villager_body_frames.cpp` helper now scales the stored transparent
  crop offsets with that draw scale in both the Details-screen
  `ldwGameWindow::DrawImage` path and the main-scene
  `ldwImageImpl::DrawFrame` path.
- The fix changes only offset math. Holiday Body runtime/detail frames are
  still transparent-cropped from the supplied source art, report
  `resized: false` in `patch-manifest.json`, and keep the original source
  pixels unscaled.

## 2026-07-07 - B114 Portable Invisible Furniture Reference Graphics

- `sync_invisible_furniture_reference_sets()` no longer consults creator-local
  `Downloads` folders for Invisible Furniture reference graphics. The
  `OptionalVisualMods/Invisible Furniture - Base Graphics` and
  `OptionalVisualMods/Invisible Furniture - Transparent` folders are rebuilt
  only from files already inside the generated build.
- Invisible Full-Size Pool, Invisible Kiddie Pool, and Invisible Hammock now
  use their base-game donor images for the Base Graphics folder:
  `PoolLargeStd.png`, `PoolChildrensStd.png`, and `HammockStd.png`,
  respectively. Their `.pngORIGINAL` transparent backups are generated from
  those same donor image dimensions inside the build, then copied into the
  Transparent folder.
- `CVillagerManager::DrawVillager` passes the main-world body draw parameters
  to `CSceneManager::DrawScaled` as body `scale` followed by `alpha`. B113
  treated that second float like a Y scale, which misaligned Holiday Body
  children in the main scene. B114 uses body scale for both crop-offset axes
  and leaves the Details-screen draw path unchanged.

## 2026-07-07 - B115 Output Refresh EXE Safety

- `offline_vf2_patcher.py::prepare_output_dir()` refreshes recognized modded
  output folders by deleting all non-backup contents before copying vanilla
  files and applying active records. If validation saw
  `Virtual Families 2 - Modded B*.exe` as `up_to_date` before that refresh,
  the old `apply_asset_patches()` path skipped rewriting the EXE after it had
  been deleted.
- `apply_asset_patches()` now rechecks `up_to_date` asset targets at apply
  time. If the refreshed output folder removed or changed the target, the
  patcher converts the record back to `create`/`replace` and copies the
  payload, preventing visual-only toggles from leaving a modded folder without
  its modded executable.

## 2026-07-07 - B116 Child Kids Table Spontaneous Behavior

- `CBehavior::ChildrenPlayAtKidsTable` is registered as behavior ID `0x130`.
  `CHotSpot::KidsTable(CVillager&)` pushes `0x130` and calls
  `CVillager::NewBehavior` directly; unlike `CHotSpot::Hammock`, it has no
  hardcoded `CFurnitureManager::IsInWorld(base_item)` gate to widen.
- `patch_spontaneous_behaviors()` now enables behavior `0x130` through
  `EnableChildOnlyAutonomousCandidate`, using the same child boundary as
  Playhouse (`CVillager+0x6A54 < 0x118`). Adults should not choose this
  behavior spontaneously.
- Invisible Kids Table behavior parity is enforced through the donor-cloned
  furniture path: item `0x321` inherits non-identity behavior fields from
  `KidsTableAndChairsStd` item `0x1CE`, uses donor fmap
  `KidsTableAndChairsStd.png.fmap`, and keeps the generated donor click-table
  alias.

## 2026-07-07 - B117 Daytime-Only Playhouse Spontaneous Behavior

- `VillagerAI.obj` and `Behavior.obj` already reference
  `CNight::AIIsDayTime()`, with global `CNight Night`. This is the native AI
  daytime predicate and is safer than deriving daytime from raw `GameTime`
  seconds.
- `patch_spontaneous_behaviors()` now refreshes behavior `0x11E`
  (`PlayOnPlayStructure` / "Playhouse!") at each
  `CVillagerAI::DecideWhatToDo` refresh. The candidate keeps the child-only
  age cap (`0x117`) but gets weight `0` and enabled flag `0` whenever
  `Night.AIIsDayTime()` returns false.

## 2026-07-07 - B124 Spontaneous Hammock Anchored Rest

- Native hammock behavior `0x23` (`CBehavior::LieInHammock`) walks to content
  object `0x5B` and then plays the sleeping animation, but it does not call
  `CFurnitureManager::LinkPeepToFurniture`; this is why spontaneous hammock
  users can rest beside the placed hammock on some orientations.
- Native hammock behavior `0x24` (`CBehavior::LieInHammockNoLeadIn`) is the
  manual-drop route. It calls `LinkPeepToFurniture(0x5B, villager, ...)`, walks
  to the returned furniture point, then issues `CVillagerPlans::PlanToLieDown`
  or the fallback wait pose.
- B124 keeps the spontaneous candidate on behavior `0x23` so it retains the
  long `SleepNW` / `SleepNE` rest animation, but retargets the `0x23` macro to
  `_VF2LieInHammockAnchoredRest`. The helper calls
  `CFurnitureManager::LinkPeepToFurniture` first, plans a walk to the linked
  hammock point, then chooses the sleep strip from the returned
  `sFurnitureInfo2` orientation. Manual-drop behavior `0x24` remains native.
- B125 tightens the same spontaneous candidate's eligibility: it now requires
  `CFurnitureManager::IsInWorld(0x1E1)` for base `HammockStd` or
  `IsInWorld(0x30C)` for `InvisibleHammock`. When either item exists and
  weather is neutral/sunny, the candidate keeps the standard behavior-patch
  weight `3000`; otherwise the candidate is disabled and weighted `0`.
- The native hammock behaviors write action label string id `0xE9` to
  `CVillager + 0x1BBA8` before `StartNewBehavior`. B125 mirrors that copy in
  `_VF2LieInHammockAnchoredRest`; without it the behavior runs but the HUD
  action text stays at the default "Nothing".
- B126 keeps the same spontaneous behavior `0x23`, weight, and hammock-rest
  lead-in pose, but calls the head-direction overload:
  `PlanToWait(10, EBodyPosition 9, headDirection)`. `sFurnitureInfo2`
  orientation `1` uses head direction `7` before `SleepNW`; the other
  orientation uses head direction `1` before `SleepNE`.
- Added `work/dump_villager_action_plan_data.py` to generate a human-readable
  behavior/action-plan dump from `dump_behavior_disasm.txt` and
  `dump_villagerplans_disasm.txt`. The dump preserves raw x86 push context and
  best-effort inferred `CVillagerPlans::PlanTo*` args, including known
  `EBodyPosition` values `0`, `9`, `0x17` and head directions `1`/`7` used by
  hammock work.

## 2026-07-07 - B119 Settings Evict Visibility

- B118 proved that NOPing the constructor gates at
  `theOptionsDialog::.ctor+0x2DA/+0x2E7` is not enough. The dormant Evict block
  allocates an `ldwButton`, constructs it with control ID `this+0x7C` (`4`),
  and sets string ID `0x10`, but the stock dormant block does not call
  `ldwScene::AddControl` for that button.
- B119 inserts `push esi; mov ecx, ebx; call ldwScene::AddControl` at
  `theOptionsDialog::.ctor+0x360`, immediately after the Evict button
  `SetText()` call and before the radio-button setup. The existing handler
  already compares messages against `this+0x7C` and calls
  `theOptionsDialog::EvictFamily()`, so no handler rewrite is needed.
- Text fixes now retarget existing string-table text relocations instead of
  in-place literal bytes. Stock strings `Cooking like mommy` and
  `Driving like daddy` are replaced with `Cooking like a grownup` and
  `Driving like a grownup` while keeping their original string IDs.

## 2026-07-07 - B121 Evict Text and Optional Graphics Payloads

- The Settings Evict confirmation string is drawn by the stock dialog as a
  literal text run; it does not wrap long replacement strings automatically.
  B121 pre-wraps `eString_EvictFamilyResetWarning` with explicit `\n` line
  breaks so the warning stays inside the modal bounds.
- The patcher now exposes two default-off optional graphics swaps:
  `misc_graphics_fixes` writes
  `payload/OptionalVisualMods/Misc Graphics Fixes/superFridge_NW.png` to
  `Images/Upgrades/superFridge_NW.png`, and `glowing_collectibles` writes
  `payload/OptionalVisualMods/Glowing Collectibles/collectables_small.png` to
  `Images/collectables_small.png`.
- Both B121 optional graphics records include `restore_source_path` entries
  pointing at bundled `Original Virtual Families 2 Assets` vanilla images, so
  unchecking the setting and clicking Enable/Disable Patches can restore the
  vanilla asset from the portable payload.

## 2026-07-07 - B122 Invisible Workspace Upgrades Payload

- The optional upgrades visual swap is now labeled `Invisible Workspace
  Upgrades` while retaining setting ID `invisible_upgrades_graphics` for
  compatibility with existing manifests and tests.
- B122 bundles the supplied paired workspace upgrade PNGs under
  `payload/OptionalVisualMods/Invisible Workspace Upgrades/invisible images/`
  and `payload/OptionalVisualMods/Invisible Workspace Upgrades/original images/`.
  Runtime records target `Images/Upgrades/*.png`; restore records use the
  bundled original-image mate for each invisible PNG.
- The exporter source assets live in tracked `patcher_assets/optional_patches/`
  so the patcher remains portable and future exports do not read from
  `Downloads` or other creator-local folders.

## 2026-07-08 - B127 Patcher Additive Asset Validation

- B126 failed before applying because generated additive asset records such as
  `Assets/Balloons_birthday.png.fmap` carried vanilla target expectations even
  though those files are supposed to be created in a vanilla install.
- `offline_vf2_patcher.py` now supports an explicit `allow_missing_target`
  field on asset records. Missing targets are only created when this flag is
  present; ordinary replacement/restore records still fail if their expected
  target is absent.
- `export_offline_patch_bundle.py` writes `allow_missing_target: true` for
  additive generated payload records. B127 dry-run validation covered all 943
  active/restore asset records with all main and optional settings enabled.

## 2026-07-08 - B128 Portable Songs, TV Sprite, Cheat Icons, and Radio Behavior

- `export_offline_patch_bundle.py` now defaults optional song-mod input to
  tracked `patcher_assets/optional_patches/optional_song_mods/OptionalSongMods`.
  This keeps `optional_song_mods` portable and prevents future patcher exports
  from silently dropping the song setting when no creator-local Downloads path
  is present.
- `work/patch_mobile_furniture_pack.py::sync_vf3_tv_sprite_strips()` now checks
  tracked `work/assets/vf3_tv_sprites/` before the legacy Sprite folder. The
  `FathersFavoriteTV` record is marked as a two-frame source strip and copied
  verbatim from the smaller `214x123` workspace sprite instead of regenerating
  the oversized cabinet-style `294x174` strip.
- Father’s Favorite private TV animation boxes are constrained to
  `(8, 10, 90, 62)` for both directions so animation frames stay inside the
  brown screen border on the smaller sprite.
- Cheat Upgrade store icons are normalized to `90x90` transparent PNGs and
  `sync_visible_special_upgrade_icon_art()` force-refreshes `cheat_*.png`
  targets from the workspace source to avoid stale oversized payload icons.
- Behavior patch radio support now retargets behavior `0x0ED`
  (`DancingRadio`) to `_VF2RandomRadioBehavior`, which randomly calls the
  native `DancingRadio` or `ListenToRadio` macros. Spontaneous radio behavior
  enables the same randomized `0x0ED` candidate for all ages.
- Text fixes now also retarget `Not feeling fresh` to `Not feeling clean`
  through the existing string-table relocation path.

## 2026-07-08 - B129 Outfit Icon Export and VF3 TV Strip Source

- `export_offline_patch_bundle.py::candidate_manifest_rel_paths()` now treats
  manifest shorthand paths under `OutfitIcons/` as `Images/OutfitIcons/`.
  `setting_for_asset()` also assigns `Images/OutfitIcons/*` to
  `outfit_store_expansion`, so generated female, male, and Holiday outfit store
  icons are bundled and toggled with the expanded Outfit Store patch.
- The supplied `FlatScreenVF3BigE.png` and `FlatScreenVF3Big.png` 6x3 TV
  animation sheets are stored under tracked
  `work/assets/vf3_tv_animations/` and used by
  `sync_vf3_tv_animation_sheets()` for VF3 Large Flat Screen TV animations.
  Father's Favorite TV reuses those individual frames and scales them into its
  smaller screen box from the same workspace source.
- `patch_arcade_behavior_labels()` is now called during the normal build. It
  retargets the shared stock `Playing` label pushes inside
  `CBehavior::PlayingPachinko` and `CBehavior::PlayingPinball` to the added
  string IDs for `Playing pachinko` and `Playing pinball`.

## 2026-07-08 - B130 Direct VF3 TV Animation Strip Payloads

- `work/patch_mobile_furniture_pack.py::split_supplied_tv_animation_cells()`
  now splits the bundled `FlatScreenVF3BigE.png` and `FlatScreenVF3Big.png`
  sheets into a fixed `6 x 3` grid, writing `Frame01.png` through
  `Frame18.png` under `Images/VF3TVAnimations/<label>/`.
- `build_supplied_tv_animation_strip()` replaces the previous bounded
  compositor for supplied Large VF3 TV sheets. Large/LargeEast runtime strips
  preserve the supplied cells with only transparent padding to `76 x 89`
  cells, yielding `456 x 267` runtime sheets.
- Father's Favorite TV now reuses those split supplied cells and scales each
  whole cell to the Father's Favorite furniture canvas (`107 x 123` per cell,
  `642 x 369` runtime sheet). This keeps the patcher payload tied to the
  supplied strip art instead of the old generated screen-box overlay.
- B130 patcher validation compared payload files against B129: file counts
  matched (`2947` each), with only the four renamed B129 EXE payloads replaced
  by B130 EXE payloads. The B130 payload includes `108` outfit icons, `5`
  optional-song OGGs, `6` runtime TV animation sheets, and `108` split TV
  animation frame PNGs.

## 2026-07-09 - B131 Behavior Label Variants and Furniture Unlock Cheat

- `work/patch_mobile_furniture_pack.py::patch_spontaneous_behaviors()` now
  writes grouped behavior-label string arrays into
  `vf2_spontaneous_behaviors.cpp`. Wrapper helpers call the native behavior
  first, then replace only the visible action label through
  `CVillager+0x1BBA8` and `theStringManager::GetString()`.
- `patch_behavior_label_variants()` retargets safe no-data
  `CBehavior::CBehavior()` macro rows to wrappers for TV, web, video games,
  mending, ironing, telescope, workout, career, pool, playhouse, snow,
  sandbox, toy train, petting, shower, coffee, and cocktail variants. It
  preserves native plans, walking, animation, sounds, and furniture targeting.
- The non-adult autonomous gate still uses the proven stock boundary
  `CVillager+0x6A54 < 0x118`. Drawing, snow play, sandbox, toy train,
  Playhouse, and Kids Table spontaneous candidates use that range; adult
  ironing/mending/career candidates use `>= 0x118`.
- Snow-play spontaneity is gated by `Weather.currentType == 5`, inferred from
  native weather event callsites that pass enum values `0`, `3`, `4`, and `5`.
  This needs in-game weather verification.
- The optional Cheat Upgrades overlay adds item `0x123`:
  `Unlock all furniture`. Its helper snapshots stock plus appended
  `sFurnitureInfo` generation locks, sets all live locks to `0`, and restores
  the generated lock table when bought again. `sFurnitureInfo` stride is
  `0x6C`; generation lock is field `+0x0C`.

## 2026-07-09 - Villager Behavior/Plan Dump

- `work/dump_villager_action_plan_data.py` now exports a grouped
  `CBehavior -> CVillagerPlans` report under
  `outputs/villager-action-plan-dump/`, including registered behavior IDs,
  recovered plan API signatures, inferred push arguments, known content-object
  constants, and recovered `CVillager` field notes.
- Confirmed field anchors: `CVillager+0x6A54` is the age/growth field used by
  stock adult/non-adult gates, `+0x6A58` is likely gender, `+0x6A5C` is likely
  body/outfit value, `+0x6A60` appears to be head/voice-related rather than a
  baby counter, and `+0x1BBA8` is the current action/status label buffer.
- Native baby-related behavior constructors exist for
  `TeachingFirstWords`, `MomTeachingTalk`, `WashBaby`, `ChangeBaby`,
  `ShowingBabyGarden`, `ShowingBabyToys`, `CelebratingBaby`,
  `JealousAboutBaby`, `ExcitedAboutBaby`, and `PlayingMommy`; actual
  nursing/baby ownership fields still need mapping before enabling these as
  spontaneous nursing-mother behaviors.
- Native north leak reactions exist for `FreakOutShowerLeakNorth` (`0x135`)
  and `FreakOutToiletLeakNorth` (`0x137`). A distinct north sink freak-out
  symbol is absent, but native repair behavior `FixingNorthBRoomSink`
  (`0x04E`) exists. B132 hooks `CEventTheWaterPressureSurge::ImpactGame(int)`
  with `_VF2WaterPressureSurgeSecondBathLeaks`, guarded by
  `InventoryManager.HaveUpgrade(0xE6)`, to add north leak props `0x48`
  (toilet), `0x49` (shower), and `0x4A` (sink); `CVillager::NewBehavior`
  calls `_VF2MapNorthBathroomLeakBehavior` to route villagers to the native
  north leak reactions.

## 2026-07-09 - Stock Special Upgrades Lotto Ticket Odds

- `CScrollingStoreScene::HandleUpgrade()` case `$LN50` handles base Special
  Upgrade item `0x114` (`Lotto Ticket`). It rolls
  `ldwGameState::GetRandom(10000)` and awards 50000 coins on roll `0`, 25000
  coins on `1..2`, 5000 coins on `3..22`, 1000 coins on `23..222`, and 750
  coins on `223..722`.
- Non-cash rolls `723..4055` get a second `GetRandom(100)` check; if the roll
  is `< 50` and a tool-tray slot is available, the game awards random item
  `4..7` and displays `eString_WonABagOfGroceries` (`0x4D1`). All other
  remaining rolls display `eString_NotAWinner` (`0x4D0`).

## 2026-07-09 - Villager Age/Growth Thresholds

- `CVillager+0x6A54` is a growth scalar with multiple native cutoffs. The
  stock child/non-child boundary is `< 0x118`; `AdultPopulation()` and
  `GetRandomVillager(EAgeSelecter)` selector bit `2` start at `>= 0x118`,
  which is better described as teen-or-older for patch logic.
- Mature adult checks use a stricter range. `SelectOtherAvailableMatingVillager`
  requires both villagers to be `>= 0x168` and `< 0x44C`;
  `MothersCaringForBabies` starts at `>= 0x168`; `GetRandomCollegeKid()` starts
  at `>= 0x17C`; selector bit `4` uses `>= 0x44C` for elder/senior selection.
- Future behavior patches should separate helper names by intent: child-only
  (`< 0x118`), teen-or-older (`>= 0x118`), and mature adult
  (`>= 0x168 && < 0x44C`).
- `work/patch_mobile_furniture_pack.py` now emits helper names matching those
  semantics: `VF2IsChild`, `VF2IsTeenOrOlder`, and `VF2IsMatureAdult`. Current
  label routing remains behavior-equivalent; this mainly prevents future
  teen/adult wording mistakes.

## 2026-07-09 - B134 Patcher/Overlay Export Fixes

- `FurnitureManager.obj` contains `?itemInfo@@3PAUsFurnitureInfo@@A` as a
  section-defined COFF symbol with storage class `3` (`static`). Helper C++
  objects can name it but the linker will not resolve that as an external
  definition. `work/coff_patch.py::set_symbol_storage_class()` now lets the
  generator mark the patched `itemInfo` symbol external after appending mobile
  records, preserving stock record bytes while allowing the Cheat Upgrades
  `Unlock all furniture` helper to link.
- The optional Island Events overlay helper is generated by a Python string
  template. It must run through `.format(registrations=...)`; otherwise the
  output file keeps doubled braces and a literal
  `{chr(10).join(registrations)}` line, producing invalid C++.
- B134 smoke validation used `work/vanilla_runtime_payload` plus the
  workspace-local vanilla EXE shape, dry-ran all 1050 asset records, and
  applied all settings to a separate modded folder. With all settings enabled,
  the patcher selected `Virtual Families 2 - Modded B134.exe` from the combined
  Island Events + Cheat Upgrades overlay payload.

## 2026-07-09 - Regression Test Contract Cleanup

- `work/test_patch_mobile_furniture_pack.py` now matches the current VF3 TV
  animation contract: Father's Favorite TV uses the B129 smaller-screen box
  `(8, 10, 90, 62)` for both orientations while Large and Small VF3 TVs keep
  their existing screen boxes.
- `patch_spontaneous_behaviors()` now also edits `Behavior.obj`, so isolated
  tests for the spontaneous behavior helper need to stage `Behavior.obj` beside
  `Villager.obj` and `VillagerAI.obj`. The visible behavior-manifest wording is
  `non-adults` for kids-table/playground-style actions because the helper gates
  on the stock child cutoff rather than a separate prose-only "children" label.

## 2026-07-09 - Radio/MP3 Behavior Patch Contract

- `patch_radio_drop_behavior()` retargets the `CBehavior` constructor macro
  relocation at `??0CBehavior@@QAE@XZ + 0xC3C` from the stock `DancingRadio`
  behavior entry to `_VF2RandomRadioBehavior`. The helper randomly dispatches
  the native `CBehavior::DancingRadio()` or `CBehavior::ListenToRadio()`, so
  base radios, MP3 players, and inherited invisible radio/MP3 routes share the
  same drop behavior pool.
- `patch_spontaneous_behaviors()` enables candidate `0x0ED` for all ages after
  `InitAI` and `LoadAI` restore weights. Because `0x0ED` now resolves through
  `_VF2RandomRadioBehavior`, spontaneous radio/MP3 behavior uses the same
  dance-or-listen selection as manual drops.

## 2026-07-09 - Optional Song Payload Restore Contract

- `work/export_offline_patch_bundle.py::export_asset_payloads()` now copies
  source-only payload folders (`OptionalVisualMods/`,
  `Original Virtual Families 2 Assets/`, and `OptionalSongMods/`) whenever they
  exist in the generated build, even if there are no normal `Images/` or
  `Assets/` candidate diffs. This keeps optional-song restore records portable:
  `optional_song_asset_patches()` can attach
  `payload/Original Virtual Families 2 Assets/originalsounds/*.ogg` as vanilla
  restore sources for `Sounds/menu.ogg` and `Sounds/song1-4.ogg`.

## 2026-07-09 - Patcher Install-Shape EXE Validation

- `work/offline_vf2_patcher.py::verify_runtime_requirements()` now treats
  top-level `.exe` files as executable candidates outside
  `runtime_requirements.exact_top_level_entries`. This fixes the B135 false
  invalid-install popup where `Virtual Families 2.exe` was reported as an
  "unexpected top-level entry" even though the EXE is supposed to be validated
  separately.
- `verify_target_files()` remains the binary authority after folder-shape
  validation. The selected/discovered EXE still must match either a manifest
  SHA-256 record or accepted PE section-layout record before patches can be
  applied.
- `work/official_vf2_pe_structures.json` is the source-side list of accepted
  official VF2 PC PE layouts. `export_offline_patch_bundle.py` embeds those
  structures into every EXE-replacement patcher manifest, including the older
  official layout with `pe_offset=0x100`, `number_of_sections=5`, and
  `file_alignment=0x1000`. Runtime patchers use only the embedded manifest
  records, not outside paths.

## 2026-07-10 - Behavior Label Variant Stability

- `CVillager+0x1BBA8` is the visible action-label buffer used by the HUD. B137
  helper wrappers now compare the current buffer to their generated string
  groups with `strncmp(..., 0x27)` before calling the native behavior, then
  restore the same string ID afterward. This prevents praise/refresh paths from
  rerolling a label such as `Playing Virtual Families` into another video-game
  variant while the underlying native behavior is still active.
- Food/drink variants are label-only wrappers over stock behavior entries:
  `GetADrink` (`0x019`, constructor offset `0x11B`), `HeatUpFood` (`0x0D5`,
  `0xAB4`), `LookingForSnacksDispatch` (`0x025`, `0x1C3`), and
  `PreparingAMeal` (`0x032`, `0x28A`). The wrappers call the original
  `CBehavior` method first and only swap the visible label afterward, so route
  planning, animations, object targeting, and side effects stay native.
- Additional B137 wrapper targets are now documented from
  `work/Behavior_patched_disasm.txt`: board games (`0x107`/`0xE8E`), kitchen
  career (`0x047`/`0x3B0`, `0x048`/`0x3BE`), drawing (`0x118`/`0xFAF`), nap
  dreams (`0x083`/`0x721`), breakfast (`0x0D6`/`0xAC5`), flower watering
  (`0x075`-`0x077`), bathroom sink/grooming (`0x0A4`-`0x0A9`, `0x0AD`), child
  driving (`0x00B`/`0x09D`), kids table (`0x130`/`0x1125`), teen homework/test
  (`0x0C0`/`0x4AA`, `0x0C1`/`0x4BB`), and sit-down/rest (`0x127`/`0x108C`).
- `ToyTrampoline` (`0x199`, constructor offset `0x1875`) does not expose the
  old phrase through `theStringManager.obj`; the B137 fix therefore retargets
  the behavior label wrapper and writes `Jumping on the trampoline` after the
  native trampoline behavior runs.
- The `Unlock all furniture` / no-generation-locks store icon is now copied
  from the self-contained patcher payload source
  `patcher_assets/optional_patches/cheat_upgrades/cheat_no_generation_locks.png`
  instead of relying on an external Downloads path.
- The radio/MP3 dance/listen switch remains the existing `0x0ED` wrapper and
  was intentionally not changed by the B137 label-stability helper.

## 2026-07-10 - Player Email String Pools

- `eString_SendingEmail` is string id `0x0721`; `CBehavior::BrowsingWeb2`
  dispatches it to `CVillagerPlans::PlanToWriteToPlayer`, which creates
  action/plan type `0x41`. The related read-email path uses `0x0720` and plan
  type `0x40`.
- `CDailyEmail::Show` composes player email from header, random greeting,
  optional first-adoption/return comments, one priority status branch, optional
  life-event text, optional remark, ending, and salutation. `CCollegeKidEmail`
  has separate greeting/comment/ending/salutation arrays.
- The full string dump is generated by `work/dump_email_to_player_strings.py`
  into `outputs/vf2-email-to-player-strings/`; the technical architecture notes
  live in `docs/email-to-player.md`.

## 2026-07-10 - Flea Market Rotating Goodies Expansion

- `CInventoryManager::MaybeUpdateSaleItems()` is the `On Sale` source, not the
  Flea Market. It scans `0xFC` furniture IDs from `0x1AD` through `0x2A8` and
  stores three sale rows at `CInventoryManager+0x474`, with count/timer fields
  at `+0x480/+0x484`.
- The actual Flea Market uses `CInventoryManager::MaybeUpdateRotatingItems()`.
  It walks the external `gGoodiesList` array (`0x24` entries), shuffles the
  valid goodies, and stores five rows at `CInventoryManager+0x488`, with
  count/timer fields at `+0x49C/+0x4A0`.
- The next Flea Market fix keeps category `0x0F` but changes the expansion to
  the same fixed-list style used by the expanded Clothing section:
  `VF2GetExpandedFleaMarketCount` returns `0x24`, and
  `VF2GetExpandedFleaMarketItem` reads `gGoodiesList[index]` directly. This
  avoids filtering through the rotating five-item cache and leaves the On Sale
  cache untouched.
- B143 exporter validation: the patcher payload contains the fixed core EXE
  plus all Island Events / Cheat Upgrades / Holiday Ornaments overlay
  combinations. An `--enable-all --dry-run` validated `1070` active/restore
  asset records against the test install shape.

## 2026-07-10 - Reset Achievements Cheat Upgrade

- `CAchievement::Reset()` is the stock goals/progress reset routine. It clears
  the achievement records and notify queue without changing the save-state
  record count.
- B139 adds Cheat Upgrades item `0x124` (`Reset Achievements`) and routes it
  through `VF2ApplyVisibleSpecialUpgrade` to call global `Achievement.Reset()`,
  then uses the existing `theGameState::SaveCurrentGame()` save path.
- The row uses workspace-local `cheat_reset_achievements.png`, copied from the
  supplied trophy icon, so future patcher builds stay portable.
- B139 patcher portability audit confirmed `1052` asset records and `1089`
  payload references with no outside-payload source paths and no missing files
  in either the output folder or ZIP. The exporter now writes source-build
  provenance as filenames/build labels instead of absolute local paths.

## 2026-07-10 - B140 Patcher Release Portability

- GitHub rejected replacing the B139 release asset because the release is
  immutable, so the cleaned self-contained patcher was re-exported as B140.
- B140 preserves the B139 gameplay payload shape: `1052` asset records, `1089`
  payload/restore references, `2949` payload files, and four EXE replacement
  payloads (`core`, `Island Events`, `Cheat Upgrades`, and combined overlay).
- All-enabled dry run against the workspace vanilla install validated every
  active/restore asset record and reported no byte patch records, matching the
  full-EXE-overlay patcher model.

## 2026-07-10 - B141 Behavior and Icon Safety

- Behavior-label wrappers now call the native `CBehavior::*` routine first and
  compare the villager action label at `CVillager+0x1BBA8` before applying a
  variant. If the stock behavior rejects the action, the wrapper returns
  without forcing a new label. This preserves stock shower, bathroom sink,
  grooming, age, object, and targeting gates while still allowing label
  variants when the native route starts.
- B141 adds a small generated `VF2BehaviorLabelCacheSlot` table keyed by
  villager pointer and wrapper label group. The cache reuses the selected
  stock/custom label across praise/HUD refresh calls while the same native
  route is active, so labels such as `Playing Virtual Families` no longer
  reroll into sibling variants after praise.
- B141 originally left the radio/MP3 dance/listen switch uncached. B150
  supersedes that exception: both the native listening branch and the
  dancing/custom-label branch now reuse the praise-stable per-villager cache.
- `sync_visible_special_upgrade_icon_art()` normalizes `cheat_*.png` images to
  a transparent `90x90` canvas before embedding them, so oversized `No Money` /
  `No Food` icons and small `Unlock all furniture` / trophy icons fit the
  Special Upgrades row and buy dialog consistently.
- B141 export smoke: all-settings dry run against
  `C:\Users\Owner\Downloads\Virtual Families 2test2` validated `1052`
  active/restore asset patch records with no missing/error entries. The
  portable patcher folder contains `2949` payload files.

## 2026-07-10 - Holiday Ornaments Sell-All Path

- The experimental Holiday Ornaments family uses carrying values `0x9E-0xA9`
  and achievement row `0x5F`. Stock `CEventTheCollector::ImpactGame(0)` already
  calls `CCollectableItem::ResetCollection()`, which clears the shared
  collection-state table, so B142 only adds the missing
  `CAchievement::ResetSingleAchievementProgress(0x5F)` call before the stock
  achievement reset tail.
- Holiday Ornament art lookup no longer points at Downloads. Collection-page
  art comes from workspace-local supplied files when present or the mobile
  `tp225.pvr` atlas fallback, and the ornament-aware `collectables_small.png`
  now lives under `work/assets/holiday_collectibles/` for portable patcher
  payloads.
- The offline patcher exporter now accepts a standalone Holiday Ornaments EXE
  overlay plus Island Events/Cheat Upgrades combination overlays so multiple
  optional native patches do not overwrite each other.
- B142 export validation: an all-settings dry run validated `1070`
  active/restore records, and a minimal `core_executable` +
  `holiday_ornaments_collection` dry run validated the Holiday overlay EXE,
  `Images/collectables_small.png`, `Images/collection-ornaments_background.png`,
  and all `Images/CollectionOrnaments/*` records without needing
  `mobile_furniture`.

## 2026-07-10 - Mobile TextAsset Workspace Mirror

- The user-supplied mobile `TextAsset` dump has been mirrored to
  `work/assets/TextAsset/` so future furniture additions can use workspace-local
  `.fmap`, `.asset`, `.atlas`, `.skel`, `.txt`, and `.json` material without
  depending on `Downloads` or other outside paths. The mirrored set currently
  contains `574` files, about `5.03 MB`.

## 2026-07-11 - Holiday Ornaments Collector Count

- `CEventTheCollector::CanFire()` is where Mr. B/The Collector both calculates
  the coin offer and decides if the event can fire; `CalcAward(int)` is a stub.
- B144 extends the three stock `CCollectableItem::CollectionCount()` offer
  passes with base collectible `0x9E`, matching the appended Holiday Ornament
  family `0x9E-0xA9` without adding a separate scheduler or counter.
- The same patch adds a final completed-collection availability check for
  `CollectionCount(0x9E, true, true, true)`. Stock completed-family checks for
  `0x67` and `0x86` still short-circuit to success.

## 2026-07-11 - Holiday Ornaments Collection Tooltip

- `CCollectionScene::HandleMouse()` has a separate click-tooltip rarity-label
  lookup in stack locals sized for the 60 stock collectibles. Appending page
  `5` is not enough by itself: ornament indices `60-71` index three additional
  four-item rarity buckets past the stock table.
- B145 initializes the extra tooltip buckets before the stock lookup runs:
  `0x9E-0xA1` uses string `0x751`, `0xA2-0xA5` uses `0x752`, and
  `0xA6-0xA9` uses `0x753`. This preserves the stock five pages while keeping
  the appended Holiday Ornament page from reading scratch stack space during
  click/tooltip handling.

## 2026-07-11 - Patcher Overlay Assets

- `work/export_offline_patch_bundle.py` cannot rely only on the core build's
  `patch-manifest.json` for assets that belong to optional EXE overlays. The
  Holiday Ornaments art is generated in the Holiday overlay build, so B145
  exports overlay assets whose `setting_for_asset()` resolves to
  `holiday_ornaments_collection` from the `--holiday-ornaments-exe` build
  folder and keeps those records gated behind that setting.

## 2026-07-11 - Holiday Ornament Yard Sprite Index

- `CCollectableItem::Add(ECarrying, ldwPoint, bool)` already expands a
  registered spawn-area base with `GetRandom(4)`, then applies the stock
  uncommon `+4` and rare `+8` branches. Holiday Ornaments should continue to
  register base `0x9E` with the mobile full-yard rectangles and let stock odds,
  including Lucky Rock, choose `0x9E-0xA9`.
- `CCollectableItem::Draw(int)` indexes `Images/collectables_small.png` as
  `ECarrying - 0x4F`, so the ornament values `0x9E-0xA9` map to small-sheet
  frames `79-90`. B146 validates the workspace-local `240x640` sheet as a
  `40x40`, six-column grid with enough frames before exporting the portable
  payload.

## 2026-07-11 - Holiday Ornament Small-Sheet Variants

- `Glowing Collectibles` is an optional patcher asset swap for the same runtime
  target, `Images/collectables_small.png`, used by Holiday Ornament yard
  drawing. B147 validates both the generated Holiday sheet and
  `patcher_assets/optional_patches/glowing_collectibles/collectables_small.png`
  against the `ECarrying - 0x4F` frame contract.
- The guard requires nonblank alpha in frames `79-90`, not only a matching
  `240x640`/six-column sheet size. This prevents a future payload cleanup from
  shipping a valid-size visual replacement that silently removes the ornament
  pickup icons.

## 2026-07-11 - Holiday Ornament Native State Contract

- B148 adds `validate_holiday_ornament_native_contract()` for the isolated
  `VF2_ENABLE_HOLIDAY_ORNAMENTS=1` build path. It audits patched COFF objects
  before packaging, without changing stock behavior in normal builds.
- The validator proves `CCollectableItem::Count(ECarrying)` still indexes the
  collection-state table at `this + 0x4A4 + ECarrying * 4`; for ornaments
  `0x9E-0xA9`, that maps to `0x71C-0x74B`.
- It also proves `ResetCollection()` and `SaveState()` still cover the stock
  collection-state span `0x5E0-0x89B` (`0xAF` dwords), so Mr. B/The Collector's
  sell-all reset and save/load persistence include Holiday Ornaments.
- The same contract checks the appended `CCollectionScene::gCollectable` page
  values `0x9E-0xA9`, `_VF2CollectionPageCount` draw helper relocation, tooltip
  rarity labels `0x751/0x752/0x753`, `Find`/`WasItemSpawned` range hooks,
  `CCollectable` observer registrations, and the `0x5F` Ornamentologist reset
  on the sell-all branch.

## 2026-07-11 - Holiday Ornament Collection Page Counts

- B149 tightens the Holiday Ornament validator around `CCollectionScene`.
  `Activate(bool)` still caches only the five stock collection counts at
  `this+0x18..0x28` and leaves `this+0x2C` as the hover-state field.
- The sixth page count is therefore intentionally live-routed in
  `DrawScene()` through `_VF2CollectionPageCount(page)`. The helper maps pages
  to bases `{0x4F, 0x5B, 0x67, 0x86, 0x92, 0x9E}`, so page `5` displays the
  `0x9E-0xA9` Ornament family without changing the `CCollectionScene` object
  size.

## 2026-07-11 - B150 Feature Gates and Holiday Collection Repair

- B150 adds VF2_ENABLE_BEHAVIOR_PATCHES as a real build-time native gate,
  alongside Island Events, Cheat Upgrades, and Holiday Ornaments. The offline
  patcher exports core plus every non-empty combination of those four switches:
  16 executable overlay states in total. The manifest requires exactly the
  corresponding setting IDs before selecting an overlay, so disabling Behavior
  Patches uses an executable whose stock behavior objects were not retargeted.
- Behavior variations, autonomous candidates, the direct bathroom-sink routes,
  and praise-cache changes belong only to behavior_patches. Cheat rows, price
  modes/reset, the malfunction trigger, and removable worker/certificate
  handling belong only to cheat_upgrades. The six-page collection belongs to
  holiday_ornaments_collection; Water Pressure Surge itself belongs to
  island_events; the Brokerage description follows mobile_purchases.
- The B149 Collections Chest crash was a calling-convention mismatch.
  DrawScene() pushed a page argument for _VF2CollectionPageCount, but the
  injected helper was cdecl and left that argument on the stack. A later
  sprintf path could then read page 0 as a string pointer and crash. B150 emits
  _VF2CollectionPageCount@4 as __stdcall, so the helper removes its own
  argument.
- The Holiday overlay also routes the final main-scene collection count through
  CCollectableItem::CollectionCountWithHolidayOrnaments and patches the unique
  visible suffix from " / 60" to " / 72". The Collections screen remains six
  pages of exactly 12 items, with the stock five-page cache/object layout intact
  and page 5 counted live from base carrying value 0x9E.

## 2026-07-11 - B150 Behavior Eligibility and Variations

- The raw age field at CVillager+0x6A54 uses 20 units per displayed year. B150
  therefore uses 0x104 for age 13, 0x118 for age 14, and 0x17C for age 19.
  Gender remains at CVillager+0x6A58 (1 is female in the audited routes), and
  career ID at CVillager+0x6B8C is -1 when no career exists.
- "Needs to sit down"/RestingBody (0x127) and "Checking weight"/WeighingSelf
  (0x046) are autonomous for all ages under Behavior Patches. "Mending a
  button" (0x08D) and "Ironing clothes" (0x08E) become autonomous from displayed
  age 14. Their stock object search, plan, animation, and failure routes remain
  in control after candidate selection.
- "Teaching first words" (0x11F) becomes autonomous only through the audited
  nursing-mother candidate gate: minimum nursing age state 0x168 plus the
  native own-baby/carried-baby requirement. Its label pool adds "Teaching baby
  how to walk", "Talking with baby", "Feeding baby", "Singing lullabies to
  baby", "Playing with baby", "Admiring baby", "Playing peek-a-boo with baby",
  "Kissing baby", and "Taking pictures of baby".
- Petting is the explicit exception to the autonomous-variation audit.
  _VF2RandomPetLabel remains available when a manual/native Petting route
  starts, but candidate 0x19A is not enabled by B150.
- "Browsing web" adds "Watching memes", "Making memes", and "Posting memes
  online" to its general pool. "Buying stuff online" requires displayed age
  13+ (raw >= 0x104). Existing teen/social labels keep the audited native age
  route instead of being widened for the new labels.
- The couch-nap pool contains 30 distinct labels: "Dreaming of Isola",
  "Dreaming of family", "Dreaming of pets", "Dreaming of friends", "Dreaming of
  the future", "Dreaming of the beach", "Dreaming of snow", "Dreaming of
  holidays", "Dreaming of vacations", "Dreaming of roller coasters", "Dreaming
  of climbing mountains", "Dreaming of camping", "Dreaming of family trips",
  "Dreaming of the countryside", "Dreaming of LDW games", "Dreaming of the
  city", "Dreaming of the forest", "Dreaming of unicorns", "Dreaming of fish",
  "Dreaming of jungles", "Dreaming of tropical islands", "Dreaming of
  skyscrapers", "Dreaming of floating in space", "Dreaming of treasure",
  "Dreaming of getting rich", "Dreaming of adventures", "Dreaming of swimming",
  "Dreaming of flying", "Dreaming of falling", and "Dreaming of discovering
  something".
- The all-age sit-down pool contains "Thinking", "Taking a moment to reflect",
  "Thinking of family", "Thinking of relatives", "Thinking of friends",
  "Thinking of pets", "Thinking of vacations", "Thinking of weekend plans",
  "Thinking of what to watch next", "Resting", "Resting eyes", "Resting feet",
  "Relaxing for a bit", "Taking a break", "Enjoying life", "Enjoying the
  scenery", "Texting", "Playing games on phone", "Scrolling on phone",
  "Checking social media on phone", "Scrapbooking", "Texting friends", "Texting
  family", and "Texting relatives".
- At displayed age 19+, the sit-down pool also contains "Thinking of children",
  "Thinking of grandchildren", "Thinking of spouse", and "Texting spouse".
  "Thinking of work" requires age 19+ with a career. "Thinking of school" is
  available to anyone who is not both age 19+ and holding a career. At ages
  14-18, "Texting boyfriend" is female-only and "Texting girlfriend" is
  male-only.
- Direct sink behaviors 0x0A5-0x0A8 clone the full stock 0x0A4 candidate
  record before their own IDs/weights are restored. This enables the requested
  subroutines without discarding the native sink, object, and household gates.
  The general sink pool is face mask, trimming nails, lotion, and sunscreen;
  the female grooming pool adds fingernails, toenails, manicure, pedicure, and
  makeup. "Putting on jewelry" is female-only at displayed age 14+.
- The north-shower route clones the stock shower candidate, and snow-play
  eligibility is refreshed against Weather.currentType == 5 (Snowing).
  Hammocks remain Sunny/Cloudy-only, Playhouse remains child/daytime-only, and
  all other audited candidates retain native object, time, age, gender, and
  career fields unless B150 explicitly documents an override above.
- The label cache now stores behavior ID, behavior serial, the native praise
  counter, and the original native label bytes. A praise restart with the same
  praised behavior and incremented counter restores either the selected custom
  string or exact cached native text. Radio listening/dancing uses the same
  cache through a listening sentinel, fixing the last route that could reroll
  the visible action when a villager was praised.

## 2026-07-11 - B150 Cheat Upgrades, Malfunctions, and Removable Upgrades

- Cheat Upgrade IDs added after Reset Achievements 0x124 are: Reset Ants 0x125,
  Reset all collections 0x126, Complete all collections 0x127, 2x Prices 0x128,
  5x Prices 0x129, 100x Prices 0x12A, Trigger all house malfunctions 0x12B,
  and Reset Price Multiplier 0x12C.
- Reset Ants calls the native ResetWorldState(0x13), clears environment props
  0x4D-0x54, then reseeds one of the first three ant props plus the two fixed
  start pieces 0x50/0x51. This restarts the puzzle instead of merely hiding the
  current ants.
- Reset all collections uses ResetCollection(), resets the five stock page
  achievements 0x4A/0x4B/0x4C/0x5D/0x5E, the aggregate 0x4D, and
  Ornamentologist 0x5F only when Holiday Ornaments is active. Complete all
  collections writes exactly 12 obtained flags for each active page base
  0x4F/0x5B/0x67/0x86/0x92/(optional 0x9E), then completes the corresponding
  page and aggregate achievements.
- 2x, 5x, and 100x are mutually exclusive persistent modes. The helper
  multiplies the final CalcPrice return, covering ordinary store categories and
  career upgrades: furniture, Flea Market goods, renovations, Special
  Upgrades, and other purchases routed through that calculator. Positive
  overflow saturates at signed INT_MAX. Reset Price Multiplier 0x12C removes
  active IDs 0x128-0x12A and restores the original calculated values; its exact
  description is "Resets store prices to original values."
- Trigger all house malfunctions sets the normal native failure props at once.
  It uses the native furniture lookup for Dryer object 0x48 and sets its fire
  only if a Dryer is present. North toilet 0x48, north shower 0x49, and north
  sink 0x4A leaks require second-bathroom renovation item 0xE6.
- Water Pressure Surge adds the three north leaks only in an Island Events
  executable, because that event is registered/firable only when island_events
  is enabled. The native standalone random north-malfunction selectors remain
  available independently and retain their second-bathroom renovation gate.
  Native north repair/freak-out behavior mapping remains shared so existing
  standalone failures can still be noticed and repaired.
- Under Cheat Upgrades only, owned Maid 0x115 and Gardener 0x116 rows become
  zero-price removal actions: buying again clears the service timer, deactivates
  worker villager 0x23/0x24, and clears the selected-villager field if needed.
  Rebuying Rockhound Certificate 0x10A returns/removes the inventory upgrade;
  rebuying Anti-Spam 0x33 clears its game-state flag. Explicit helper guards are
  inert in cheat-disabled executables.
- The visible mobile Brokerage Account description now states that it can
  increase the Interest Rate up to 11%. This is a mobile_purchases-family text
  change rather than a Cheat Upgrades row.
- B150 patcher surfaces state: "Vanilla Virtual Families 2 saves are compatible
  with the modded version!" It also displays Lorsieab2's passion-project/no
  copyright-infringement/support-the-original-creators message in the GUI,
  generated README, manifest metadata, and generated Transparency Log.
- Automated tests and build validators establish source/COFF/string/manifest
  contracts. Manual in-game verification is still required for the complete
  Collections Chest loop, every autonomous eligibility branch, all purchase
  categories, worker/certificate removal, price-mode save/reload/reset, and
  simultaneous malfunction repair behavior.

## 2026-07-11 - B150 Patcher Payload Reachability

- The pre-pruning B150 patcher contained 2,975 payload files, but 1,860 were
  unreachable from every manifest `source_path` and `restore_source_path`.
  Those unreachable files accounted for about 96.6 MB of the 184.1 MB ZIP.
- All patcher file reads are driven by active manifest asset records. The B150
  exporter now performs a final reachability pass, removes only unreachable
  payload files, deletes newly empty directories, revalidates every retained
  source, and records removed/retained counts and bytes in
  `export_summary.payload_pruning`.
- The 16 feature-matrix EXEs account for only about 10.9 MB of the compressed
  ZIP. They remain separate in B150 to preserve the proven four-toggle matrix;
  a future solid archive, binary-delta scheme, or runtime-gated superset EXE can
  reduce that portion without sacrificing independent settings.
- Export-only metadata now records the clean base payload by portable folder
  name instead of embedding a machine-specific absolute workspace path.

## 2026-07-11 - B151 Expanded Map Visual Target

- The corrected user mock-up is preserved at
  `work/reference_images/Expanded VF2 Map.png`: 3072x3070 RGBA,
  SHA-256 `44AE62A37E67C274D52554298FBCCDCD12C29FF4FB97633DF87386E09659F372`.
- B151 should retain the current centered map/house at its existing scale,
  extend the map by one complete tile on every side and corner, and fill the
  added perimeter with matching Lorsieab2 grass.
- The northwest extension is intentionally different from a uniform grass
  border: the current beach expands into the mock-up's large rounded sandy
  field. This corrected reference supersedes the earlier all-grass perimeter
  mock-up.
- A real implementation must widen camera, world, placement, pathing,
  interaction, and save-coordinate contracts alongside the art. Merely placing
  the mock-up behind the current map would not satisfy the B151 target.

## 2026-07-11 - B150 Holiday Ornaments Native Crash Root Cause

- The B150 runtime access violation was not caused by overlay selection, asset
  packaging, the 72-item state range, or the stdcall page-count helper.
  `CoffObject.insert_section_bytes()` shifts COFF symbols and relocations, but
  it cannot rewrite x86 relative branches encoded inside function bodies.
- The Holiday overlay inserted bytes into `CCollectionScene::HandleMouse`,
  `CCollectableItem::Find`, `CCollectableItem::WasItemSpawned`, and
  `CEventTheCollector::ImpactGame`. Native branches that crossed those
  insertions retained old displacements. In the linked B150 EXE,
  `HandleMouse+0x18D` landed inside a call displacement on the ordinary
  no-hover path, directly explaining the Collections Chest crash.
- `Find` and `WasItemSpawned` also encoded 0x9E with signed imm8 compares,
  which compared against -98 instead of carrying value 158. Their replacement
  caves use imm32 compares. `Drop` had a separate incomplete-family reentry
  loop, and the original SetComplete hook could award Goal Collector more than
  once.
- The hotfix uses fixed-size near-jump detours at `HandleMouse+0x1EB`,
  `Find+0x86`, and `WasItemSpawned+0x14`, with appended code caves after
  all in-section insertions. It repairs The Collector's `+0x07` Keep branch,
  adds an EDI reentry sentinel to Drop, and gives SetComplete separate
  already-complete and newly-completed entries.
- Validators now decode the detour and cave displacements, require every cave
  return/accept/skip target, reject the bad signed-imm8 form, and verify the
  idempotent achievement and Collector branch bytes before packaging.

## 2026-07-11 - B150 Direct Praise Label Preservation

- Native `theMainScene::InvokeReward` calls
  `CVillagerPlans::ForgetPlans` at relocation `+0x36B`; ForgetPlans clears
  the 0x28-byte action label at `CVillager+0x1BBA8` before the restarted
  behavior wrapper can inspect it. The previous 64-slot behavior cache was
  therefore a fallback after the authoritative string had already been lost.
- Behavior Patches now retarget only the normal-praise calls: `+0x36B`
  captures the exact label, calls native ForgetPlans, and immediately restores
  it; `+0x3B7` calls native StartNewBehavior and restores the exact bytes
  again. This lets wrappers preserve their current group choice and guarantees
  stock/custom text stability.
- The over-praise RunAway branch at relocations `+0x2EB` and `+0x31B`
  remains native because that path intentionally changes behavior.

## 2026-07-11 - B150 Fix All, Router, and Native Dryer Fire

- Cheat Upgrade 0x12D is `Fix all house malfunctions`. It clears exactly
  props 0x17, 0x1A, 0x1B, 0x1C, 0x1D, 0x1F, 0x20, 0x21, 0x48, 0x49, and 0x4A;
  it does not call ResetWorldState or alter ant props 0x4D-0x54.
- Prop 0x17 is Router Offline. Trigger All already sets it, and Fix All clears
  it, so the paired cheats explicitly drive Router offline/online state.
- Dryer lint fire is already a legitimate stock random malfunction. The
  UpdateScene jump table reaches case +0x41D, checks permanent-fix state +0xCC,
  requires Dryer EObject 0x48 through FindFurniture, and sets prop 0x21.
  `CBehavior::FixingLaundryFire` deactivates 0x21 and advances Handyman
  achievement 0x3A. B150 preserves and validates this native path rather than
  adding a duplicate selector that would distort its odds.
- Special Upgrades display order is now grouped by function while every item ID
  remains stable: money, food, unlock/goals/puzzle/collections, price
  multipliers followed by Reset Price Multiplier, then Trigger/Fix
  malfunctions. Numeric icon indexing stays contiguous through 0x12D.

## 2026-07-11 - B151 Goal and Longevity Intake

- The requested B151 resource, pet, longevity, family-tree head-value, and Older
  Villagers work is specified in `docs/B151-design.md`. The corrected goal
  spelling is `Centenarian`; the requested `Hampster Dance` title remains
  intentionally unchanged.
- Pet goals must require a live placed pet; family-tree appearance goals must
  scan persistent records; and the age-times-20 assumption must be verified in
  VF2 before using candidate raw thresholds.
- Older Villagers is a separate future gate. Its mortality curve is centered
  near 75 but must keep a real rare tail beyond 122, without changing stock
  mortality when disabled.

## 2026-07-11 - Base-Game Villager Mortality

- Raw age is `CVillager+0x6A54` and uses 20 units per displayed year.
  `CVillagerBio::IsOld/IsNotOld` compares it with 0x44C, so the game's
  separate "old" threshold is age 55.
- Stock game speed is 10. AllVillagersTimeflowUpkeep converts wall-clock
  seconds into one raw age unit per 10 minutes, or one displayed year per
  3 hours 20 minutes. The accumulator includes time while the game is closed,
  caps one catch-up at 86,400 seconds, and replays crossed physiology ticks and
  birthdays after return.
- Once per 20 raw age ticks, the realtime physiology routine computes
  `T = 55 + N`, where `N` is the current number of active nutrition groups.
  If age is greater than T, old-age death probability is
  `min(100, 10 * (age - T))` percent. A hit calls SetHealth(0, OldAge)
  immediately, regardless of prior health.
- Four nutrition groups are actually reachable. FoodGroupsActive loops across
  five slots, but the fifth overlaps unrelated state/expiry data and does not
  count normally; this is a stock layout/off-by-one defect. Practical constant
  nutrition outcomes are: N0 first risk 56/mean about 58.66/guaranteed by 65;
  N1 57/59.66/66; N2 58/60.66/67; N3 59/61.66/68; and N4
  60/62.66/69. Base-game villagers therefore cannot normally survive past 69.
- Age 55 also reduces passive healthy recovery: its recovery gate falls from
  50% below 55 to about 10% at 55+. Disease and starvation use separate
  health-loss paths and causes. Energy/exhaustion is tracked separately and is
  not a direct death input in the audited physiology routine.
- The Older Villagers patch should detour the annual old-age decision in
  `CVillagerManager::AllVillagersRealtimePhysiologyAndProductivityUpkeep`,
  not merely change IsOld. The stock IsOld threshold may remain useful for
  senior behavior/healing unless B151 intentionally redesigns it too.

## 2026-07-12 - B153 Optional Older Villager Mortality Hook

- The source now installs a dormant detour at upkeep `+0x353`, immediately
  before the stock `FoodGroupsActive(false)` call. The trampoline reproduces
  that call once. A zero `.vf2mort` byte jumps back to stock `+0x35C`, leaving
  the original old-age block through `+0x3C7` unchanged and reachable.
- When enabled, the trampoline passes raw age and active food-group count to
  `VF2RollOlderVillagerMortality`, calls native `SetHealth(0, OldAge)` only on
  a hit, and rejoins at `+0x3C8`. All unrelated sickness, healing,
  productivity, and family-event code remains outside the detour.
- The helper rolls only when raw age is divisible by 20. Its effective age is
  displayed age minus 0-4 active food groups. The main survival component is
  normal with center 75 and sigma 7; a 0.02% exponential component retains a
  genuine no-hard-cap tail. Effective ages above 130 use a 300/10000 annual
  hazard, so survival past 122 is possible but rare.
- `.vf2mort` follows the existing exact-SHA post-asset architecture instead of
  adding another executable overlay dimension. Focused tests prove relocation
  targets, stock rejoin bytes, a 10,000-way helper roll, all-layout hook
  installation, and coexistence with `.vf2preg` and `.vf2goal`. Linked-matrix
  and live gameplay/time-away/save-load validation remain release gates.
- A one-layout x86 diagnostic linked successfully with both the detoured
  VillagerManager object and generated helper. SHA-256 is
  `A9EE0A6BB1D96296129F4EFE603837512E848BD5F28D6AC536EB318A3F87DC5C`;
  its writable/default-zero `.vf2mort` byte is raw offset `0x197A00`.
  The full native patcher plus exporter regression run passes 117 tests.

## 2026-07-12 - B151 Holiday Ornaments Native Contract

- Mobile 1.7.16 uses carrying IDs `0x9E-0xA9` and exactly three Holiday spawn
  rectangles: `(0x112,0x0C4,0x2FA,0x1BD)`,
  `(0x098,0x178,0x19D,0x26F)`, and
  `(0x08D,0x568,0x137,0x750)`. Adding those to the 16 stock registrations
  produces 19 total spawn areas.
- `CCollectableItem::Find` and `WasItemSpawned` retain stock exact
  carrying-value matches, and `Add` remains byte-identical to stock. Its
  `0x11/0x22` rarity thresholds give 4% rare and 13% uncommon normally; Lucky
  Rock doubles both probabilities.
- The Collections Chest has six 12-item pages and reports 72 collectibles when
  Holiday Ornaments is enabled. The collection remains inside the stock
  `0xAF`-entry Count/Reset/Save/Load state span.
- Master Collector `0x4D` targets 6 completed collections, Goal Collector
  `0x54` targets 13 contributing achievements, and Ornamentologist `0x5F`
  targets 12 unique ornaments. Achievement IDs are queue values, not queue
  slots; the physical notification queue must remain its stock `0x5F` dwords.
- The Collector adds Holiday common, uncommon, and rare counts with three
  relocation-only `CanFire` insertions. Stock final availability and Keep
  behavior remain unchanged; Sell resets unfinished `0x5F` progress before
  entering the stock collection-reset tail.

## 2026-07-12 - Workspace Catalog and Post-Asset Patch Infrastructure

- The authoritative desktop/mobile furniture catalog is now self-contained at
  `data/vf2/vf2_desktop_base_and_mobile_furniture_sections.csv` (104,577
  bytes; SHA-256
  `a8e965309016d0933f1577ad0865e103e58d5df9a24cb4012a39d8457f293b8c`).
  `patch_mobile_furniture_pack.py` and its data exporter both consume this
  workspace path through `MOBILE_CSV`.
- Offline manifests can declare setting-gated `post_asset_patches`. Each record
  names an output file and carries exact `asset_sha256` variants with their own
  offset, expected asset bytes, and equal-length replacement bytes. The
  patcher selects the last active asset payload for that output path and
  rejects missing, duplicate, overlapping, out-of-range, or byte-mismatched
  variants. Duplicate asset SHA-256 variants are rejected while parsing even
  when that payload is not the selected overlay; output target keys use
  Windows case-insensitive path semantics while logs retain manifest spelling.
- Dry runs validate against the hash-verified selected payload without writing.
  Real applies copy all active asset overlays first, recheck the pristine
  target SHA-256, apply grouped post-asset bytes, and only then enforce the
  final executable name and write hashes/logs. Output-only reconfiguration
  recopies the pristine payload before applying an enabled delta; disabling the
  setting therefore restores the payload without another executable variant.
  Selected-source reads, target reads, target identity failures, and atomic
  writes all surface as per-record logged `PatchError` failures so the outer
  failure JSON is preserved instead of leaking an uncaught OS exception.
- Phase A initially emitted the schema and count with an empty
  post_asset_patches array. B152 now has two consumers: Holiday Furniture
  goals through .vf2goal and Allow Older Pregnancies through .vf2preg. Each
  selected executable contributes exact-SHA variants for both independent
  bytes.

## 2026-07-12 - B152 Custom Achievement Layout and Runtime Gate

- Every executable now materializes a dense 128-row `achievementList` through
  ID `0x7F`: stable Ornamentologist row `0x5F`, general goals `0x60-0x65`,
  Behavior/Pet goals `0x66-0x6C`, and the final Holiday Furniture suffix
  `0x6D-0x7F`. All 32 new rows use target 1 and icon `0x1ED`; their 64 exact
  strings occupy stable IDs `0xE02-0xE41` in every native variant.
- `achievementOrder` is filtered at build time for Ornamentologist and
  Behavior goals, while Holiday Furniture remains the final 19-row suffix.
  A writable one-byte `.vf2goal` flag, default `00`, changes the visible count
  at runtime without moving rows or changing save data. Scene height, draw
  bounds, order end, and completed-goal totals all use the filtered count.
- `CAchievement::LoadState` previously copied all `0x125` records and then
  treated IDs `0x5F-0x124` as unused, clearing new progress after reload. It
  now preserves IDs `0x00-0x80` and validates/clears only the true reserved
  tail `0x81-0x124`; SaveState and Reset remain at `0x125` records. Hidden
  record `0x80` is not part of the row/order/meta/notification tables: the low
  two bits of its dword at record `+4` persist whether furniture `0x2CF` and
  `0x2CC` have been bought for the Taters goal. DrawAchievement accepts IDs
  through `0x7F` using `cmp ...,0x7F` plus `JG`, never the unsafe
  sign-extended imm8 `0x80`.
- The notification queue is deliberately still 95 dwords at
  `CAchievement+0xDBC..+0xF34`. The earlier 96-slot widening overwrote the
  adjacent popup timer at `+0xF38`; Pop continues to shift `0x5E` entries and
  clear `+0xF34`, while `+0xF38/+0xF3C` remain popup timer/state fields.
- Native guards now require the exact SaveState (`0x30` bytes), Reset (`0x27`),
  PopAchievementNotify (`0x2F`), and Update (`0x1A1`) symbol spans plus their
  fixed instruction offsets. The DrawScene order-end cave preserves caller-
  saved `ECX` and `EDX` around the helper call while retaining its `EAX`
  result; object and linked-PE validators decode its relocation, source jump,
  register sequence, and exact return site.
- Phase B2 retargets only the shifted
  `CScrollingStoreScene::HandlePurchaseItem+0x2DE` AddToStorage relocation.
  The same-ABI wrapper calls native `CFurnitureManager::AddToStorage` first,
  returns its exact bool, and dispatches an award only when that bool is true,
  before the stock `SaveCurrentGame` call. General purchase mappings are
  `2EA->60`, `2EB->61`, `2EC->62`, `2ED->63`, `2EE->64`, and
  `2E9->65`.
- Holiday Furniture purchase awards run only while the writable `.vf2goal`
  byte is 1. Their mappings are `2B1-2B5->6D`, `2AF/2B8->6E`,
  `2AD/2AE->6F`, `2C5->70`, `2C2->71`, `2D2->72`, `2D0->73`,
  `2CB->75`, `2CD->76`, `2D1->77`, `2CA->78`, `2CE->79`,
  `2C8/2C9->7A`, `2C6/2C7->7B`, `2C4->7C`, `2C3->7D`,
  `2BE->7E`, and `2AC->7F`.
- Taters (`0x74`) uses the hidden record-`0x80` mask described above.
  Successful purchases of `0x2CF` and `0x2CC` set separate bits and award
  only on the transition from a mask other than 3 to mask 3, so either purchase
  order, duplicate purchases, and save/reload are safe.
- The existing `_VF2PraiseCaptureAndForget@8` wrapper now awards from the
  exact captured pre-ForgetPlans label: `Watching cat videos->66`,
  `Posting on VideoTube->67`, `Playing Virtual Families->68`,
  `Playing Virtual Villagers->69`, `Posting memes online->6A`, and
  `Praising pet->6B`. Awards occur before native ForgetPlans; both exact-label
  restorations and the stock over-praise path remain unchanged. The sole
  `InvokeScolding+0x118` ForgetPlans relocation calls a stdcall wrapper that
  awards exact `Scolding pet->6C`, then invokes native ForgetPlans exactly
  once with no restoration.
- Object tests cover all four Holiday/Behavior combinations: visible counts
  are `101/120`, `102/121`, `108/127`, and `109/128` for flag off/on,
  respectively, with exact order suffixes and stock-or-Holiday meta targets.
  The complete patcher module now passes 81 automated tests.
- Two linked B152 diagnostics passed: core/off-off SHA-256
  `F968A57877C151FD046996BCB1FB2B474BB418D594DC036E1B9F6E204AB81629`
  has `.vf2goal` at file offset `0x188400`, purchase wrapper `0xB0230`,
  and purchase hook `0x8B45D`. Holiday+Behavior/on-on SHA-256
  `90A4567943CC423D562FA106A467C91D2D051D0AD3AC6FC4A0BC5FF738D0ADA8`
  has `.vf2goal` at `0x191200`, purchase wrapper `0xB0350`, purchase hook
  `0x8B55D`, praise wrapper `0xB27D0`, and scold wrapper `0xB3D30`.
  Both flag sections have virtual size 1, default byte `00`, and writable PE
  characteristics. Phase B2 is structurally complete; exporter emission and
  the post-asset flag matrix remain B3. These checks do not claim manual
  runtime verification.

## 2026-07-12 - B152 Holiday Ornament Collection Text and Goal Order

- Stock collection rarity strings 0x751-0x753 are specifically bottle-cap
  text (common, uncommon, and rare bottle caps). Reusing them for page 5 made
  the Holiday footer name the wrong family. The Holiday page now owns three
  consecutive additive strings 0xE42-0xE44 with the exact texts
  " of 4 common ornaments found.", " of 4 uncommon ornaments found.", and
  " of 4 rare ornaments found." The existing fixed-size HandleMouse detour
  still uses its isolated cave; only the LEA string-ID base changes.
- The Collections screen alone uses the shorter title "Ornaments". The full
  "Holiday Ornaments" feature name and the Ornamentologist achievement wording
  remain unchanged elsewhere.
- Stock Bottlologist is achievement 0x5E at display-order index 0x4E.
  Holiday-enabled layouts now insert Ornamentologist 0x5F at index 0x4F,
  immediately after Bottlologist, before appending the other custom goals.
  Holiday-disabled layouts still omit 0x5F.
- Exact tests cover the title/footer rows, absence of bottle-cap wording in
  Holiday collection-screen strings, tooltip-cave ID routing, and 0x5E,0x5F
  adjacency for every Holiday/Behavior compile-time combination and both
  runtime-visible counts. The 18-test Holiday-focused run and full 82-test
  patcher module pass. No PNG, descriptor, draw-time flip, or B2 award-hook
  region changed.

## 2026-07-12 - Upright Holiday Ornament Source Art

- The complete 27-PNG supplied set is now workspace-local under
  `work/assets/holiday_collectibles/`: 12 upright collected icons, 12 matching
  placeholders, the decorative Candy Cane, the 940x732 collection frame, and
  the separate 1024x768 Bottlecaps background. Each tracked source is preserved
  byte-for-byte.
- `work/rebuild_holiday_ornament_collection_assets.py` recreates the committed
  runtime layer deterministically. The collected icons are byte-for-byte copies
  with no flip, rotation, crop, or resize. The background is the raw frame with
  the 12 placeholders alpha-composited at
  `HOLIDAY_ORNAMENT_COLLECTION_SLOT_POSITIONS`, matching the existing raw
  fallback; the Bottlecaps background remains separate.
- The version-2 manifest records all 27 source hashes and dimensions plus the
  13 runtime hashes, dimensions, source mappings, placeholder positions, and
  no-orientation-transform provenance. Tests compare icon bytes, independently
  reconstruct the background pixels, and rebuild every canonical file
  byte-for-byte.

## 2026-07-12 - B152 Experimental Allow Older Pregnancies

- Stock CVillagerState::ChanceOfPregnancy(int motherAge, int fatherAge,
  int fatherFertility) stores ages in twentieths of a year. Its 0xF7-byte
  native function hard-zeros pregnancy only when the mother's integer age is
  above 50; successful and first-tutorial-forced outcomes both queue string
  0x868.
- Every B152 executable now carries the same dormant detour and a writable
  one-byte .vf2preg section initialized to 00. When the flag is zero, or
  when both parents are below internal age 1000, the detour restores the exact
  eight displaced prologue bytes and resumes at native offset +0x8; the
  remaining stock bytes and relocations are unchanged.
- With .vf2preg == 01 and either parent age 50+, the helper mirrors stock
  fertility and age-penalty integer math without the mother-over-50 hard zero,
  converts it to tenths of a percent, and caps it by the older parent: 10.0%
  at 50 through 1.0% at 59, then 0.9% at 60 through 0.1% at 68, with a 0.1%
  floor from 69 onward. It compares against GetRandom(1000).
- A successful late-age roll still queues tutorial string 0x868. A failed
  late-age roll returns false directly, so the stock first-pregnancy tutorial
  cannot turn that failure into a success. Multiples selection and all later
  pregnancy/birth logic remain native and unmodified.
- The offline setting is default-off Experimental. Export discovers the
  default-zero byte from each selected linked PE and emits one exact-SHA
  post_asset_patches variant per unique executable payload, so no seventeenth
  build dimension is added.
- A real core diagnostic linked from the B151 core base at 1,669,120 bytes,
  SHA-256 74C8F440FEAE80C3087818BD4B24A0D4B4685A7C2C1916AB01D5C7EF57BC657B.
  Bounded linked validation found .vf2preg at raw offset 0x188800/RVA
  0x757000, ChanceOfPregnancy at RVA 0xC2E50, its cave at 0xC2F47, and the
  helper at 0xB1DE0. It also decoded the 1000-way roll, success-only 0x868
  arguments, direct false return, and stock +0x8 fallback.
- The same real core payload exposes default-00 .vf2goal at raw 0x188600 and
  .vf2preg at raw 0x188800. The exporter emits two nonoverlapping records for
  the same selected SHA: Holiday Furniture goals require core_executable plus
  holiday_furniture; older pregnancies require core_executable plus
  allow_older_pregnancies. The post-asset phase groups and applies both safely.

## 2026-07-12 - Upright Holiday Ornament payload

- The runtime page is a 1024x768 composite built from the supplied
  Collection_Bottlecaps_Background.png base, the upright frame at (74, 4), the
  upright Candy Cane at (848, 461), and all 12 upright placeholders at their
  existing absolute full-page coordinates.
- The 12 collected ornament images are copied byte-for-byte from the supplied
  PNGs. No source layer is flipped, rotated, cropped, or resized.
- The canonical manifest is schema 3 and records all 15 page layers. The
  resulting background SHA-256 is
  C94D42F228B78FB018F8F27392165072202BB57F5BA72B1FC902058678B983E0.

## 2026-07-12 - B153 Twelve-Child Native Layout Audit

- The live household is not limited to six storage objects. `CVillagerManager`
  owns 30 ordinary `CVillager` slots at stride `0x1CC0C`; `GetVillager(int)`
  accepts ordinary indices 0-29, and pregnancy uses generic
  `SpawnSpecificPeep` free-slot allocation. This is sufficient for two parents
  plus 12 living children without widening `CVillagerManager`.
- The hard ceiling is the current `CFamilyTree::SFamilyRecord`. Its child count
  is at `+0x1B4`, its child array begins at `+0x1B8`, each `SPeepRecord` is
  `0xD8` bytes, and each generation record is `0x6C8` bytes: exactly six child
  records. `AddOffspring` rejects count 6 and `EmptyOffspringSlots` returns
  `6-count`. `CVillager::Impregnate` calls the latter before choosing
  singleton/twin/triplet count, so patching that one constant without new
  storage would write into the next generation record.
- The tree owns 30 records. Its `.bss` is `0xCB80`, with the `CFamilyTree`
  global at `+8`; 30 times `0x6C8` is `0xCB70`. The serialized Family Tree
  block in `theGameData` starts at `+0x1840` and the next component starts at
  `+0xE3B4`, leaving exactly `0xCB74` bytes: a four-byte generation count plus
  the 30 stock records and no spare tail. A naive 12-child inline record would
  be `0xBD8`; 30 such records require `0x16350`, adding `0x97E0` bytes and
  shifting every later save component. That is not compatible with stock
  saves without a versioned migration.
- `CFamilyTreeScene::DrawFamily` and `CheckForFamilyPeepHit` both loop the
  recorded child count and address children at `+0x1B8 + index*0xD8`, but their
  only layout break occurs at index 3. Counts above six would continue off the
  existing two-row layout; draw and hit testing must be replaced together with
  a compact 12-child grid.
- `CAdoptionScene::CreateNextGenerationCandidates` does iterate every recorded
  child and filters only missing/dead live IDs, but writes candidate villager
  indices to `this+0x20` and persistent peep IDs to `this+0x38`. Each array has
  only six dwords; the count is already at `this+0x50`. `GetNextCandidate`
  cycles by that count, and acceptance passes the paired peep ID to
  `StartNextGeneration`. Twelve candidates therefore require external arrays
  or a safely enlarged scene object; changing the loop count would overwrite
  scene fields.
- Safe architecture: retain all stock six-child fields for vanilla-save
  compatibility; add default-off sidecar records for child indices 6-11;
  migrate/reset/move them in lockstep with the 30-generation tree; merge stock
  and sidecar children in count/find/death/update/Next Generation paths; and
  persist the sidecar through an explicitly versioned extension before
  enabling births 7-12. The optional patch must remain unavailable until that
  persistence plus 12-candidate and draw/hit-test paths pass save/reload and
  generation-transition tests.

## 2026-07-13 - Default-off debugger input routing

- The dormant developer build now patches five `theMainScene` input entries:
  key down, key character, mouse down, mouse move, and mouse up. Key up remains
  stock because its native function is only a tiny return-false stub without a
  safely replaceable prologue.
- Every new route preserves the stock path until F5 activates the guarded
  debugger session. Key-character and mouse calls are sent to the selected
  `IEditor`; a handled call returns immediately, while an unhandled or disabled
  call resumes the original `theMainScene` function.
- Mouse point arguments are forwarded as x/y dwords. The key-character hook
  widens the native char stack slot for its C helper; the original slot remains
  untouched when execution falls through to the stock function.
- Stock disassembly proves `HandleKeyCharacter(char)` cleans up with `ret 4`;
  all three point handlers use `ret 8`. Follow-up byte validation caught an
  initial research-only `ret 12` mismatch in the character hook before release.
  That interim diagnostic was never shipped and is superseded.
- Native vtable relocations prove the slot order is Reset, Draw, KeyCharacter,
  KeyDown, KeyUp, MouseDown, MouseUp, MouseMove, Activate. The earlier generated
  declaration placed Draw, Activate, MouseMove, and MouseUp in wrong slots;
  guarded calls could therefore dispatch to the wrong native method.
- The earlier vtable-corrected x86 validator at SHA-256
  `73000ACC7AC03DCF55643906394324EA0F7F1B5DEB870EBCF9166BBBCA721305`
  is superseded by the single-dispatch validator below and was never shipped.
- Constructor relocation at `theMainScene+0x48` targets its IDebugger vtable at
  object offset `+8`; that secondary vtable has one slot targeting `Debug`.
- `CDebugger::Register` and `Draw` machine code confirm the provider array at
  `+4`, capacity/count at `+0x24`, selected index at `+0x28`, and draw anchors
  at `+0x2C/+0x30`, matching the guarded helper overlay.
- The default-off writer leaves the canonical 228,896-byte `theMainScene.obj`
  SHA-256 `BA93F6430B45AAB75EFAE17C982BD9AC52DF078AE6E798D7D4F92E5DEBF733FB`
  byte-identical and emits only the disabled helper stub.
- Native `CLightSourceEditor::HandleKeyDown(int)` is the five-byte
  `xor al,al; ret 4` stub. Its character handler instead relocates calls to
  `CNight::AddLightSource`, `DeleteLightSource`, and `Save`, proving printable
  commands belong only on the character route.
- The helper no longer forwards printable keys from key-down and character
  hooks. This prevents L/D/S and type-cycle commands from executing twice.
- The corrected patched scene/helper compile and link into a 1,737,216-byte x86
  Windows GUI diagnostic, SHA-256
  `1D8C51B67CB02BC3310CA5C25DC00E51D792A720B6BE684328488B5B12B04520`.
- The expanded debugger and patcher regression suite passes all 101 tests.
- Native character jump tables remove the remaining editor-control ambiguity:
  the Light Source Editor accepts `+`/`-` for next/previous type and `L`, `D`,
  and `S` (case-insensitive) for add/delete/save. The Waypoint Editor accepts
  `W` to cycle and scroll among five waypoint positions and `S` to save; both
  letter commands are case-insensitive. A regression test now pins these maps.
- A minimized isolated live-test folder pairs that executable with the exact
  B152 all-patches runtime and untouched control executable SHA-256
  `23D0E330AE82C745F8395FA5D22D9B3ACFC49FA85D9B83A5474FEA8382495B4F`.
  It contains 8,472 files / 239,085,638 logical bytes; 8,465 runtime files are
  same-volume hardlinks and no runtime file required a duplicate copy.
- Dumpbin confirms the control and developer executables have the same DLL
  dependency set; the developer image is x86 / Windows GUI.
- This is structural/link validation only. `ENABLE_DEBUGGER_FEATURES` remains
  false by default, published builds retain stock input, and F5/F6/F7/F4 plus
  light add/delete/drag/type/save still require live save-load testing.

## 2026-07-13 - B153 linked matrix, behavior, price, and debugger crash audit

- Built and independently validated all 16 B153 Island Events / Cheat Upgrades /
  Holiday Ornaments / Behavior Patches layouts. Every executable hash is unique;
  `.vf2goal`, `.vf2preg`, and `.vf2mort` remain writable/default-zero and have
  nonoverlapping exact-SHA records with reversible enable/idempotent-enable/
  disable cycles. This is linked structural proof, not live gameplay proof.
- Holiday validation passes eight positive and eight negative layouts, including
  collection labels, Ornamentologist placement, and patch-off absence.
- Behavior validation proves `Ironing clothes` is an age-14+ spontaneous
  candidate and `Needs to sit down` is an all-age spontaneous candidate only
  when Behavior Patches is enabled. The linked label is exactly
  `Taking boss' advice on a job project`; the former career-project string is
  absent.
- Price-multiplier audit confirms both normal and career `CalcPrice` return
  paths use the multiplier helper. The three multipliers are mutually exclusive,
  overflow saturates at `INT_MAX`, and Reset removes IDs `0x128`-`0x12A` then
  returns the current incoming canonical price unchanged; no stale price cache
  is involved.
- Windows Error Reporting identified the first debugger test crash as
  `0xC0000005` at RVA `0xC5D4B`. The disabled branch's JE `+4` landed inside the
  immediate bytes of the six-byte `mov al,1; pop ebp; ret 8` sequence. Both
  generated debugger hooks now use JE `+6`, landing exactly at the stock body.
- The corrected isolated diagnostic is 1,739,264 bytes, SHA-256
  `82936F22A33F8991D9282DB15D90CE1105828C7A2FE57014E7924B98D1510135`.
  Linked validation finds one key-down, one key-character, and three mouse
  hooks, no stale `+4` branch, and exact stock fallthrough targets. Live
  house-load/editor retesting is still required; normal builds remain stock and
  the debugger remains default-off.


## 2026-07-13 - VF2 internal debugger key codes

- The house-load-safe debugger diagnostic still ignored F5 because the helper
  accepted Win32 0x74 and SDL 0x4000003E, while theMainScene receives the
  LDW/VF2 internal key enum.
- Stock CDebugger::HandleKeyDown subtracts 0x3EE for Up, recognizes
  0x3EF for Down, and reaches its visibility toggle at 0x3FE for F5.
  The contiguous function-key mapping establishes F4 0x3FD, F6 0x3FF,
  and F7 0x400.
- The B153 helper now recognizes internal plus Win32/SDL forms for F4-F7 and
  translates alternate Up/Down forms to the native 0x3EE/0x3EF values.
- Every one of the 16 linked B153 layouts contains the same complete key map and
  corrected six-byte false-result fallthrough. The all-patches hash is
  C32E1BC1A5FF4E340C2B8168D06B4DB946C49A4604EA69DDC6F62AD4C367D9C2.

## 2026-07-13 - Next-release pregnancy, mortality, event, and cheat follow-up

- The failed-conception deadline is a 1200-second write to `theGameState+0x25AE0` in `CVillagerPlans::ProcessCurrentPlan`. The new trampoline preserves the exact stock write when the patch is off or both parents are under 50, and skips it only when Allow Older Pregnancies is enabled and either parent is 50+.
- The linked validator now proves that cooldown trampoline and helper in all 16 layouts, including its age-1000 internal threshold, `.vf2preg` flag address, continuation at hook +0xB, and conditional state write.
- The mortality curve is now centered at age 75 with sigma 3. Each active food group subtracts one effective year, preserving the cumulative 0-4-year bonus; annual hazard is capped at 9999/10000 rather than becoming certain. The no-100% cap keeps 122+ mathematically possible while making post-mean survival much rarer.
- The raw mobile `LoanReturned` description was truncated after 'nearly unrecognizable'. The self-contained CSV and generated override now contain the full transformed-man, repaid-loan, and personal-thanks ending; a regression test requires the complete paragraph.
- Light Source Editor printable `+`/`-` input is swapped only for that active editor, matching the requested direction without changing stock key handling or the Waypoint Editor.
- Cheat Upgrade 0x12E (`Complete all Achievements`) uses `CAchievement::SetComplete` for only the goal ranges enabled by the current patch selection. Complete all collections 0x127 and 0x12E use the trophy icon. Achiever Extraordinaire remains a separate pending goal.
- The full 107-test native suite passes, and all 16 linked feature layouts pass Holiday positive/negative and runtime-flag validation after these changes.


## B154 linked release validation (2026-07-14)

- All 177 automated tests pass. The 16 B154 feature layouts have 16 unique hashes and pass linked debugger, Holiday-positive/negative, runtime-flag ABI, exact-SHA enable, repeated-enable idempotence, and exact-disable restoration checks.
- The linked mortality helper requests `GetRandom(10000)`, clamps food groups with `min(activeFoodGroups, 4)`, preserves the 0-4 effective-age bonus, stays below the cap through effective age 130, and reaches the 9999/10000 cap at 131.
- User live confirmation covers F5 without the former crash, Light Source Editor, ornament spawning and Ornamentologist, mortality, new purchase/behavior goals, Cheat Upgrades, and north-bathroom malfunctions. This does not replace the narrower persistence and edge-case audits in the request ledger.
- Mobile-exclusive furniture behaviors remain future default-off optional work. Any disruptive group celebration must be manual-drop-only and cannot become an autonomous household-wide behavior.

## 2026-07-21 - B156 stock executable icon preservation

- The published B155.5 modded executable was inspected and contained zero
  `RT_ICON` and zero `RT_GROUP_ICON` resources, matching the player's report of
  a blank icon in folders and when pinned to the taskbar.
- B156 captures the complete icon resource set from the verified stock
  `Virtual Families 2.exe` before replacing the executable, then writes that
  exact set only after every other executable mutation is complete.
- Icon preservation now rejects malformed `GRPICONDIR` data, missing referenced
  `RT_ICON` IDs, and declared image sizes that do not match the copied image.
- The atomic temporary executable must also pass Windows
  `PrivateExtractIconsW` extraction at 16x16, 32x32, and 48x48 before it can
  replace the generated modded EXE. A real PE32 round-trip regression test—not
  a mocked resource copy—passes all three shell/taskbar sizes.

## 2026-07-21 - B156 birthday purchase goals

- The first three formerly blank reserved achievement rows are now assigned in
  the request-ledger order: Happy Birthday `0x80`, Not a lie `0x81`, and Full
  of helium `0x82`. Remaining unassigned capacity is `0x83-0xA7`; hidden record
  `0xA8` remains the Taters purchase mask.
- Verified furniture mappings are Birthday Banner `0x2DB` -> `0x80`, Birthday
  Cake `0x2DC` -> `0x81`, and Birthday Balloons `0x2DA` -> `0x82`.
- The existing `CFurnitureManager::AddToStorageAndAward` wrapper dispatches the
  goals only when native `AddToStorage` returns true. No new executable detour,
  save sidecar, or counter was added.
- The three always-visible rows are ordered before the runtime-gated Holiday
  Furniture suffix. Visible counts/heights, completed-goal totals, and Complete
  all Achievements include `0x80-0x82`; Holiday gating remains independent.
- Generator validation passes 108 tests with one existing asset-dependent
  skip. All 16 B156 Island/Cheat/Holiday/Behavior layouts compile with unique
  hashes and debugger validation. Linked Holiday validation passes 8 positive
  and 8 negative layouts; all three dormant runtime-flag toggle cycles pass.
  Live purchase, notification, persistence, and reset testing remains pending.
- `work/build_b156_matrix.ps1` explicitly uses the 16 B155.5 layouts as its
  base. The shared matrix builder now accepts build/base labels so later builds
  cannot silently fall back to B155.

## 2026-07-22 - B156 first exact mobile furniture behavior family

- The optional Mobile Furniture Behaviors patch remains limited to genuine VF2
  mobile rows `0x2AA-0x2E8`; Invisible, custom, and VF3 furniture is excluded.
- Lounge Chairs `0x2DE-0x2E1` are the first implemented family. The recovered
  mobile `LieOnChaiseNoLeadIn` plan sequence is ported behind a default-zero
  writable `.vf2beh` byte and a stock-first `DropVillager` relocation wrapper.
- The four optional Chaise QAMFs keep the mobile header, 19x14 grid geometry,
  and trailer. They retain the 11 proven EObject `0x95` cells using desktop
  value `0x2000A800` and translate the required peep-slot EObject `0x13` anchor
  at `(8, 6)` from mobile `0x01B09800` to desktop `0x00009800`. Omitting that
  anchor makes desktop `FindPeepSlot` reject every chair. Mobile string IDs are
  not portable either: the unreachable-seat refusal maps to stock PC `0xB7`,
  and the exact bad-weather text receives a new dedicated PC string ID.
- The patch does not extend the fixed behavior or hotspot tables. It runtime-gates
  autonomous chaise branches through existing in-range desktop behaviors:
  ReadingBook `0x12B` (mobile weight 1500 and 30-percent branch), NappingCouch
  `0x83` (mobile weight 3000 and 30-percent branch), and RestingBody `0x127` as
  the desktop carrier for daytime Sunbathing (mobile weight 2000). The requested
  Studying-on-lounger extension uses `0xC2` at patch-chosen weight 450 and is not
  represented as an exact mobile route. Disabling the option restores stock
  behavior targets and the exact rendered-only base maps.

## 2026-07-23 - B156 player-confirmed chaise and energy-weighted drop choices

- Player testing confirms a good-weather manual drop reaches the chaise, uses
  the correct lie/wait pose, and displays `Relaxing on lounger`. The same player
  test confirms bad weather takes the dedicated refusal path.
- Desktop `CVillager::Init` places `CVillagerState` at `CVillager+0x6AF4`.
  Preserved `CVillagerState::SetEnergy` clamps the value to 1-100 and writes it
  at state offset `+0x34`, proving native energy is `CVillager+0x6B28`.
- The requested manual-drop chooser keeps four awake choices at weight 20 each.
  Nap uses `max(0, 70-energy)` and Getting some sleep uses
  `max(0, 45-energy)*3`; therefore high-energy villagers cannot select either,
  while increasingly exhausted villagers progressively favor them.
- The nap outcome retains native `NappingCouch` energy gain `GetRandom(5)+7`
  and dirtiness +2. Getting some sleep retains native adult sleep energy +10,
  dirtiness +2, and a 10-19 tick chaise lie/wait. Needs to sit down retains
  native RestingBody energy +3 and a 15-29 tick chaise lie/wait.
- The autonomous `NappingCouch` chaise branch also uses native energy. Its
  chance scales from zero at energy 70 to the recovered mobile 30-percent
  maximum at energy 1; the stock couch fallback remains in control when the
  chaise branch is not selected.
- All 16 B156 executable layouts compile with unique hashes. Linked validation
  proves four non-overlapping reversible runtime controls, including `.vf2beh`.
- The remaining Holiday, birthday, patio, umbrella, picnic, and other mobile
  families stay unported until their exact routing and placed-item anchors are
  proven.

## 2026-07-23 - Exact computer-drop and Birthday Cake additions

- Desktop `CHotSpot` registers Computers at hotspot `0x12`. Its handler checks
  active repair state, pending email, computer career work, and sickness before
  selecting ordinary BrowsingWeb behavior `0x5A`. Behavior Patches now changes
  only that final ordinary result: a single 50/50 roll may select native
  PlayingVideoGame `0x114`. No autonomous candidate weight is changed.
- Mobile Birthday Cake item `0x2DC` maps to EObject `0x94`. Its manual hotspot
  is child-only through raw age `0x117`; older villagers consume the drop.
  The exact PokingCake plan is now direct-planned on desktop without indexing
  mobile behavior `0x1B3` into the stock table.
- The PC-safe Birthday Cake map is `9x8`, contains EObject cell value
  `0x2000A000` only at `(4,7)`, `(5,7)`, and `(6,7)`, and has SHA-256
  `e1c55dc0d38b44003abe878cd9ccdfee3e49b5c7ed9e793d14b25c0fae57926d`.
- Mobile Birthday Presents item `0x2DD` maps to EObject `0x93` and shares the
  same child-only raw-age boundary. Its exact direct plan is implemented without
  indexing mobile behavior `0x1B1` into the stock desktop table. The PC-safe
  `9x10` map contains `0x20009800` only at `(3,9)`, `(4,9)`, and `(5,9)`;
  SHA-256 is
  `63ef84177e87b4a4dd28c0a85c4aff2ee741423ca4ac34b3d273cb11fd4a18c5`.
- Focused source tests cover the route, map, manifest, optional export/restore,
  and computer exception boundaries. A Behavior-Patches executable compiled
  successfully; live Birthday Cake and computer-drop testing remains pending.

## 2026-07-23 - Exact Christmas Stockings route and Birthday Balloons proof

- Large Stocking `0x2C6` and Small Stocking `0x2C7` share mobile EObject
  `0x90`. Their manual hotspot always consumes the drop and permits raw ages
  through `0x167`; there is no weather or time predicate.
- The exact `KidsCheckXmasStockings` plan is now emitted directly on desktop:
  `Checking for stocking stuffers`, three randomized x-offset approach points,
  age/gender voice selection, orientation-aware waits, work, four jumps, sound
  stop, and behavior completion. Neither the mobile hotspot nor behavior table
  is indexed.
- The PC-safe Large map is `10x13`, retains `0x20008000` only at `(6,12)` and
  `(7,12)`, and hashes to
  `f467c400f7ae60efea0ab67ccb33d5ec9327a94383102f750e20dd29d70165a0`.
  The Small map is `8x11`, retains the same value only at `(4,10)` and `(5,10)`,
  and hashes to
  `aa6eee69ecaedcaa03575d6bb916e4442cfc83efda41f6e3a8291371475e8003`.
- Birthday Balloons `0x2DA` / EObject `0x92` is no longer blocked. Workspace
  evidence proves desktop string parity for localized StringId `0xF0`
  (`Playing`), the complete child-only plan, every animation/sound API, and the
  safe `11x14` PC map (`f66e4dc4776962b32b68e069a133ca9b1a7f57306d7df357866dd2630c307fc3`).
  The exact direct plan is now implemented and linked without indexing mobile
  behavior `0x1AD`; live child, age-boundary, placement, and random-branch QA
  remain.

## 2026-07-23 - Exact whole-household Dreidel and Menorah routes

- Mobile Dreidel `0x2AF` / EObject `0x8A` and Menorah `0x2B8` / EObject `0x8E`
  both use the same 30-slot resident eligibility contract: present, at home,
  and health greater than zero, with no age or gender restriction.
- Their mobile behavior IDs `0x1A2` and `0x1A3` exceed the desktop behavior
  table. B156 therefore collects eligible permanent residents through
  `CVillagerManager::VillagerExists(index, false)` and `GetVillager(index)`,
  then runs exact external plans. Temporary worker slots `30-36` are excluded.
- Dreidel retains the seven-round randomized sound/wait sequence and uses a
  minimal `12x8` map hashing to
  `44f21fc628cd90090f3eaf8eb1925de8d890fa5239828f55d115ae37c453b36a`.
- Menorah retains its voice selection, `0xFB` sound, twirls, four jumps, and
  orientation-aware waits. Its minimal `10x11` map hashes to
  `352ba4be943eae6a168a133430ccd6555c5feb41a630c118da2d24c019e39365`.
- The behavior-enabled executable compiles and links. Live household filtering,
  simultaneous plan assignment, placement, and orientation QA remain.

## 2026-07-23 - Exact Birthday Banner family and bounded trash/weed cheats

- Birthday Banner `0x2DB` / EObject `0x91` now implements the full mobile
  birthday-object scan in fixed order `0x91-0x94`. Banner presence or multiple
  birthday objects runs the exact external whole-household celebration; a sole
  Balloons, Presents, or Cake object uses its exact existing handler.
- The celebration repeats the object scan per resident, selects the first
  existing object, and preserves the mobile label, voice selection, sound
  `0xFB`, twirls, four jumps, three approaches, orientation-aware waits, sound
  stop, and all failure paths. Mobile IDs `0x1AE/0x1AF` never enter the desktop
  behavior table.
- The minimal Banner map is `14x16`, retains seven `0x20008800` cells, and
  hashes to
  `071c79932b55f382e3fe12be01a32f673ae9726339bd4295be3b35bf78456feb`.
- Cheat Upgrade `0x12F` fills currently available collectable slots with native
  house trash; `0x130` fills them with native yard weeds. Both pass `30` to the
  stock bounded spawn APIs, which skip occupied slots and stop at the fixed
  pool limit. Existing collectables are not overwritten.
- A combined Cheat-Upgrades plus Behavior-Patches executable compiles and links.
  Live purchase, persistence, mixed birthday furniture, and group-action QA
  remain.

## 2026-07-23 - Exact Christmas Tree celebration and Clean Garden

- Christmas Tree `0x2AD` and Lighted Christmas Tree `0x2AE` share EObject
  `0x88` and the exact whole-household `Celebrating around the tree` manual
  route. The guarded external plan excludes absent, away, dead, and temporary
  residents and never indexes mobile behavior `0x1A0`.
- Tree 1's minimal `15x22` map hashes to
  `5907f7f60209d77d6c63b15b009243756c9f2c4d729134c41c105e0863b66926`;
  Tree 2's `16x22` map hashes to
  `289e237d686f164dfd3e2293aeac248f5259e700125d963b4b578cefd642ccc8`.
- Clean Garden Cheat Upgrade `0x131` calls the exact stock Weed Bomb path
  `CollectableItem.RemoveAll((ECarrying)0x7D)`. It removes only weeds
  `0x7D-0x80` through native removal and leaves all other collectables intact.
- Plate of Cookies has no registered mobile manual hotspot. Its exact reachable
  action is an autonomous under-14 kid candidate with an optional adult rescue,
  so B156 does not invent a manual drop behavior for it.

## 2026-07-23 - Exact maximum-resource goals

- `No More Worries` is assigned visible achievement `0x83` and completes only
  when `CMoney.balance` equals the native maximum `4,000,000,000.0`.
  `CMoney::Set` and positive `CMoney::Adjust` both use the exact double clamp
  constant `0x41EDCD6500000000`. The Max Coins cheat now uses that ceiling
  instead of the provisional `3,999,999,999`.
- `Solving World Hunger` is assigned visible achievement `0x84` and completes
  only when `CFoodStore.food` equals the native positive-overflow saturation
  value `0x7FFFFFFF` (`2,147,483,647`).
- All native REL32 callsites for `CMoney::Adjust`, `CMoney::Set`, and
  `CFoodStore::Adjust` are redirected to ABI-compatible observers. The sole
  `CMoney::LoadState` call is also wrapped after Achievement and FoodStore load,
  so already-maxed saves reconcile without a per-frame poll.
- The event-driven design leaves Reset Achievements cleared until the next
  resource mutation or successful reload. IDs `0x83-0x84` are always visible
  before the runtime-gated Holiday suffix and are included in visible completion
  totals and Complete all Achievements.
- The fully enabled B156 executable links and passes Holiday, runtime-flag, and
  debugger validation. Live natural-threshold, cheat-threshold, notification,
  reset, save, and reload QA remains.

## 2026-07-23 - Exact manual Patio Table drink routes

- Mobile Patio Table `0x2E6` uses EObject `0x98`. Its exact manual hotspot
  forgets current plans, lets any age drink while the drinks state is active,
  otherwise requires raw age `0x118+` and at least 31 food before preparing.
  Both preparation and drinking refuse weather types 2 and above.
- Preparing retains the mobile kitchen-source activation, carry `0x21`, Patio
  work/drop sequence, prop `0x56`, random waits, energy -7, dirtiness +7,
  happiness trend +5, and hunger +7. Drinking retains furniture linking,
  literal `Sit In Chair NW` / `Sit In Chair NE` animations with three fresh
  10-17 rolls, both exact sounds, hunger -10, dirtiness +4, and poo +6.
- PC `CEnvironment` cannot safely index mobile prop `0x56`.
  `CVillagerPlans::ProcessCurrentPlan+0x21B` therefore retargets only the native
  `SetProp` relocation to an ABI-compatible wrapper. Every other prop calls the
  stock method; `0x56` instead starts a guarded external 240-game-second state
  using `CGameTime::Seconds`. Save/reload persistence for that short timer is
  not yet proven.
- The PC-safe `Patio_table.png.fmap` retains EObject cells across `(7..12,12)`
  and both proven seat anchors `(3,8)` and `(13,8)`. Its SHA-256 is
  `7c253287702c895a84260c199dab311d32934ae186ec89526e5bb8673b44cbba`.
- At this checkpoint, mobile autonomous behaviors `0x1B6` and `0x1B7`
  exceeded the PC table and no regression-safe paired surrogate was proven.
  The exact manual routes therefore landed first without indexing those IDs
  or repurposing an unrelated stock candidate. The later external-selector
  entry supersedes this pending status.
- The fully enabled executable links at 1,759,232 bytes with SHA-256
  `a9b5b3ab98c8d3c7e0f78a1ef6bd582f82ac5d5569df99d964d1f7e6cfa2ec76`.
  All 16 existing B156 layouts still pass linked Holiday and four-flag
  validation. Live preparation, timer, both chairs, weather, age, food, and
  save/reload QA remains.

## 2026-07-23 - Exact longevity goals and load reconciliation

- Five always-visible achievements now occupy IDs `0x85-0x89`: Lucky 70's,
  Great 80's, Mighty 90's, Centenarian, and Oldest Person in History. Their
  exact raw-age thresholds are `1400`, `1600`, `1800`, `2000`, and `2441`;
  the final goal therefore requires surpassing displayed age 122.
- The proven annual old-age path still uses the B155.5 55-byte mortality
  trampoline. Its existing `FoodGroupsActive(false)` call is retargeted to an
  ABI-compatible wrapper which first preserves the native result, then observes
  the processed raw-age cursor at `CVillagerState+0x08` before either the stock
  or optional mortality roll. The longevity awards therefore do not depend on
  the `.vf2mort` setting.
- `CVillagerManager::LoadState+0x33` retains its sole native villager-load call
  through a fastcall wrapper. After a successful load, reconciliation awards
  from bio age `+0x6A54` only when active `+0x1BB84` is nonzero, left-home
  `+0x1BB88` is zero, and health `+0x6B00` is positive. The manager's exact
  30-record save span is unchanged.
- IDs `0x85-0x89` are included in the visible counts, ordered achievement list,
  Complete all Achievements, and Reset all Achievements persistence capacity.
  The reserved custom range remains `0x8A-0xA7`.
- The fully enabled B156 executable links at 1,759,744 bytes with SHA-256
  `e0c66aeb3ffecde13b2cc697a608e24bc76d738e58593bb44369881a757804cc`.
  Linked validation proves the mortality flag-off stock rejoin, enabled rejoin,
  all four dormant flag toggles, and all 16 existing feature layouts. Live
  birthday, notification, reset, save, and reload QA remains.

## 2026-07-23 - Exact manual Picnic Table routes

- Picnic Table item `0x2E8` uses EObject `0x97`. The exact mobile manual
  handler always forgets current plans, lets any age eat while prop `0x55` is
  ready, and otherwise requires raw age `0x118+` plus at least 31 food to
  prepare. Younger and low-food villagers retain their separate Shake Head
  plus DealerSay refusals.
- Preparing a picnic preserves the kitchen source and prop `3`, random carry
  `0x0D-0x13`, food-drop stop at EObject `0x18`, sound `0xC7`, basket `0x40`,
  Picnic Table work/waits, external prop `0x55`, energy -7, dirtiness +7,
  happiness trend +5, and hunger +7. Weather types 2 and above refuse.
- Having a picnic links to one of four seats and performs three independent
  sound rolls `0x6A-0x6C` plus three independent 10-17 animation rolls.
  Orientation and seat markers `0x13`, `0x14`, `0x53`, and `0x54` select the
  exact `Sit In Chair NW` or `Sit In Chair NE` label. Completion applies
  hunger -40, dirtiness +4, and poo +6.
- PC `CEnvironment` cannot safely index mobile prop `0x55`. The existing
  relocation-only SetProp wrapper now maintains independent wrap-safe 240
  game-second states for Picnic `0x55` and Patio `0x56`, preserving every stock
  prop call. Save/reload persistence for the short external timers remains
  unproven.
- The `22x16` PC-safe QAMF retains EObject anchors `(10..13,15)` and four seat
  anchors while excluding mobile hotspot `0x6B`. Its SHA-256 is
  `3d3aaeeeb77e7842cc20be211d8bcf415f85e6d8c6cd0e0f860a934c6cc45060`.
  At this checkpoint, mobile autonomous behaviors `0x1B4-0x1B5` remained
  unindexed because they exceed the PC behavior table. The later
  external-selector entry supersedes this pending status.
- The fully enabled B156 executable links at 1,760,768 bytes with SHA-256
  `ad202293324ae2d9fb6a56089c63e56dd0ecfaac9d3e7a7abefb9ec4b471d0aa`.
  Linked Holiday and four-runtime-flag validation passes across all 16 existing
  layouts. Live preparation, eating, all four seats, refusals, weather, timer,
  and save/reload QA remains.

## 2026-07-23 - Exact live-pet achievements

- Six always-visible pet achievements now occupy IDs `0x8A-0x8F`: A Furry
  Companion, The Cat's Meow, Man's Best Friend, Itsy Bitsy, Hampster Dance,
  and Lovely Lizards. The title's requested `Hampster` spelling is retained.
- The complete placed-pet inventory range is `0x23B-0x248`: cats
  `0x23B-0x23F`, dogs `0x240-0x244`, Turtle `0x245`, Lizard `0x246`, Hamster
  `0x247`, and Tarantula `0x248`. A Furry Companion accepts every item in that
  range, including Turtle; the five species goals use their exact subsets.
- `CFurnitureManager::DropFurniture+0x21D` retains the sole real inventory
  placement call through an ABI-compatible fastcall wrapper. It awards only
  when native `CPetManager::SpawnPet` returns a nonnegative slot, so purchase,
  Tool Tray storage, invalid items, and full-capacity failures do not qualify.
  The native return value and all machine-code bytes remain unchanged.
- `theGameState::Load(int)+0x250` retains the native
  `CPetManager::LoadState` call through a second relocation-only wrapper. After
  a successful load, it scans all 30 native slots, requires `PetExists`, and
  derives the stored item through `GetPet(slot).KindOfPet()+0x23B`.
  Achievement state loads earlier in the stock sequence.
- IDs `0x8A-0x8F` are included in the visible counts, ordered achievement
  list, Complete all Achievements, and the existing save/reset capacity. The
  reserved custom range is now `0x90-0xA7`.
- The fully enabled B156 executable links at 1,761,792 bytes with SHA-256
  `adf281867fbf395dddf6da33fe7fabd7c9364483ac22ecb91909a5dcab184777`.
  Existing Holiday and four-runtime-flag linked validation passes. Live
  placement, notification, reset, save, and reload QA remains.

## 2026-07-23 - Persistent family-tree appearance achievements

- Return of the Rainbow and Spiky! now occupy IDs `0x90` and `0x91`. The exact
  qualifiers are persistent `CFamilyTree::SPeepRecord` fields: present byte
  `+0x1A`, gender dword `+0x1C`, and head dword `+0x20`. Female is native value
  `1`; male is `0`; both require head `48`.
- All six native `CFamilyTree::UpdatePeepRecord` calls are retargeted through
  one ABI-compatible wrapper: AddOffspring, StartNextGeneration, the three
  UpdateCurrentFamilyRecord calls, and UpdateParents. The native update runs
  before the qualifying record is checked, and no function bytes change.
- `theGameState::Load(int)+0x16F` retains the native
  `CFamilyTree::LoadState` call through a relocation-only wrapper. After a
  successful load, reconciliation scans both parent records and up to six
  children in each of at most 30 loaded generation records. The record-present
  byte is the only membership filter, so dead and departed relatives continue
  to qualify exactly as the persistent family-tree requirement specifies.
- IDs `0x90-0x91` are included in the visible counts, ordered achievement
  list, Complete all Achievements, and existing save/reset capacity. Reserved
  custom capacity is now `0x92-0xA7`.
- The fully enabled B156 executable links at 1,762,816 bytes with SHA-256
  `16a622d702e6464f7b612badc5faee004911cfb66962845c37dc39356f4f3b8c`.
  Existing Holiday and four-runtime-flag linked validation passes. Live
  birth/adoption, notification, reset, save, and reload QA remains.

## 2026-07-23 - Spawn Marriage Email cheat

- Cheat Upgrade `0x132` is Spawn Marriage Email. It calls the stock
  `theGameState::QueueEmailMessage` method with exact `EEmailMessage` value
  `2`, the same value used by the native eligible-single-adult proposal path.
- The stock queue retains duplicate suppression and its ten-message capacity.
  The common cheat-upgrade path then calls `SaveCurrentGame`; no queue storage,
  timer, marriage-eligibility, or proposal UI code is replaced.
- The row reuses the existing trophy icon descriptor and is present only when
  Cheat Upgrades are compiled into the selected executable layout.
- The fully enabled B156 executable remains 1,762,816 bytes and hashes to
  `ac850ace342515e5da097cff362568d9bc060e9070c5ad8ef21a34e81ea73eda`.
  Existing Holiday and four-runtime-flag linked validation passes. Live
  queue-full, duplicate, eligible-family, UI, and save/reload QA remains.

## 2026-07-23 - Exact sock-pile state and cheat controls

- The persistent sock-pile count is the dword at `theGameState+0x148`.
  `CVillagerPlans::ProcessCurrentPlan` increments it when action `0x4C`
  deposits a carried sock, then removes that exact collectable.
- Action `0x4D` reads the same count into achievements `0x3B`, `0x3C`, and
  `0x3D`, clears the count, and sets the stock post-laundry byte at `+0x14C`.
  The cheat clear deliberately writes only the count so it cannot counterfeit
  laundry achievement progress or post-laundry state.
- `CDecal::RefreshDecals` selects the six stock sock-pile frames at counts
  `1`, `5`, `10`, `15`, `25`, and `30`. Counts above 30 use the same last
  frame, so 30 is the exact smallest value that visually maxes the pile.
- Cheat Upgrades `0x133` and `0x134` set the count to `0x7FFFFFFF` and 0
  respectively, then use the existing common `SaveCurrentGame` path. Max also
  calls the native bounded `CCollectableItem::SpawnSockInHouse(0x7FFFFFFF)`
  route; the native 30-record pool bounds physical sock creation while the
  persistent pile counter retains the requested signed-int maximum. The stock
  decal still saturates at its largest frame for every count at or above 30.
- The full 213-test suite passes with one intentional skip. Compiled helper
  readback confirms both writes and the shared save call. The later combined
  B156 link uses the installed Visual Studio Community x86 ATL library and
  includes both cheats; live UI/effect/save QA remains.

## 2026-07-23 - Exact Clean House scope

- Stock `CEventHouseKeepingServices::ImpactGame(int)` defines the native
  indoor-cleaning boundary with four `CCollectableItem::RemoveAll` calls:
  selectors `0x73`, `0x79`, `0x81`, and `0x83`.
- The separate stock Landscaping Services event uses selector `0x7D`.
  Housekeeping therefore leaves yard weeds alone. It also never writes the
  separate sock-pile count at `theGameState+0x148`.
- Cheat Upgrade `0x135` reproduces only the four Housekeeping Services
  removals, then uses the shared post-cheat save path.
- The generated helper compiles, object-code readback retains all four exact
  selectors, and all 213 tests pass with one intentional skip. The later
  combined B156 executable links successfully and includes Clean House; live
  removal/save QA remains.

## 2026-07-23 - Cheat Upgrade function ordering

- The B156 Cheat Upgrade rows are now ordered by function without changing any
  item ID or effect: money, food, furniture locks, Reset/Complete Achievements,
  Reset/Complete Collections, price modes/reset, trigger/fix malfunctions,
  house trash/Clean House, yard weeds/Clean Garden, sock-pile max/clear, and
  Spawn Marriage Email.
- Automated ordering assertions keep each paired inverse action adjacent.

## 2026-07-23 - Combined B156 link, Holiday contract, and shell metadata

- The installed Visual Studio Community toolchain contains the x86 ATL library
  needed by the five pre-existing `FlashPlayer.obj` symbols. The fully enabled
  layout links at 1,758,208 bytes.
- After its PE checksum is refreshed, the executable SHA-256 is
  `00f4df3c3fc6302a73c3dbaafedc5fbb8add23ba3d623644e50f23dbf0d6fe25`.
  The stored checksum is `0x001B4EF8`, and Windows ImageHlp independently
  computes the same value.
- Single-image Holiday Ornaments validation passes the positive manifest and
  linked-PE contracts, including Lucky Rock threshold routing, persistence,
  six-page collection UI, spawning, observers, collector integration, and
  achievement routing.
- Runtime validation finds four separate writable default-zero sections:
  `.vf2beh`, `.vf2goal`, `.vf2preg`, and `.vf2mort`. Enabling writes `01`,
  repeated enabling is idempotent, and disabling restores the exact starting
  executable.
- The raw linker image intentionally has no stock icon because the patcher
  receives the icon from the player's verified vanilla executable. The
  player-facing icon writer validates the icon groups, writes them after all
  executable mutations, refreshes the PE checksum, verifies exact resource
  readback, and proves Windows shell extraction at 16x16, 32x32, and 48x48.

## 2026-07-23 - Achiever Extraordinaire final-goal implementation

- Custom achievement ID `0x92` is now `Achiever Extraordinaire`, with the
  description `Complete every enabled achievement.` It uses the existing
  trophy icon and persisted 12-byte achievement record.
- `0x92` is appended after every other custom range, including the
  runtime-filtered Holiday Furniture range, so it is the final visible
  `achievementOrder` row in all four compile-time layouts and both `.vf2goal`
  states.
- A shared `CAchievement::SetComplete` exit observer scans the exact current
  visible order, skips only `0x92`, and awards it through native
  `SetComplete` only when every other visible row is complete. The completed
  bit prevents recursion and duplicate payout.
- `theGameState::Load` retargets only the existing `CAchievement::LoadState`
  relocation to a wrapper that preserves the native load result and performs
  the same reconciliation. Older saves that already satisfy the goal therefore
  receive it after a successful load.
- The fully enabled linked QA image is 1,758,208 bytes with checksum
  `0x001B5814` and SHA-256
  `470494cf2de84bc073744a05b85aca3ec31de24f33f3ae5594312eae4de37be8`.
  Holiday/Lucky Rock linked validation and all four runtime-flag toggle cycles
  pass on that exact image. Live final-popup and save/reload QA remains.

## 2026-07-24 - Force Successful Pregnancy one-shot

- Cheat Upgrade `0x136` arms bit `0x4` in the already-persisted hidden
  achievement record `0xA8`. The existing Taters purchase goal continues to
  use only bits `0x1-0x2`; its writeback now explicitly preserves every higher
  bit so buying either Taters item cannot disarm the pregnancy cheat.
- In `CVillagerPlans::ProcessCurrentPlan`, only the two existing `REL32`
  targets change. The five-byte calls at `+0x955` and `+0x979` remain
  byte-identical. The first wrapper returns true while armed instead of calling
  `CVillagerState::ChanceOfPregnancy`; the second calls native
  `CVillager::Impregnate` and clears bit `0x4` only when that call succeeds.
- Native partner/gender eligibility, empty-offspring-slot enforcement,
  multiplicity, baby naming, Family Tree writes, achievements, and the
  resulting birth remain unchanged. A capacity failure leaves the one-shot
  armed for the next eligible attempt.
- The fully enabled linked QA image is 1,763,840 bytes with checksum
  `0x001B2A7A` and SHA-256
  `a28ab64bd29f3186e6aeff2522e288d80c3a98a2a893dc3472557d532342585a`.
  All four dormant runtime toggles pass B156 enable/idempotence/restore
  validation, and all 219 tests pass with one intentional skip. Live purchase,
  full-family, birth, and save/reload QA remains.

## 2026-07-24 - Saved baby-gender and multiplicity one-shots

- Cheat Upgrades `0x137-0x138` select Male/Female with mutually exclusive
  persisted bits `0x8/0x10`. The first long-form
  `CVillagerManager::SpawnSpecificPeep` call in `CVillager::Impregnate`
  receives gender 0 or 1. Native twins and triplets use `InitTwin` from that
  first baby, so the selected gender applies to every baby without patching
  the clone path.
- Cheat Upgrades `0x139-0x13B` select Singleton/Twins/Triplets with mutually
  exclusive bits `0x20/0x40/0x80`. A guarded `Impregnate+0xE3` trampoline
  applies 1/2/3 after the stock roll and clamps it to the already-computed
  native `EmptyOffspringSlots` result.
- Native baby spawning, names, appearances, multiple-birth achievements,
  Family Tree writes, and statistics remain in place. Bits `0x4-0x80` clear
  together only after native `Impregnate` succeeds; the Taters bits `0x1-0x2`
  remain untouched.
- The fully enabled linked QA image is 1,765,888 bytes with checksum
  `0x001B0712` and SHA-256
  `4ec5142f74e6a37f55ecc30e1d232e54d553d85275f4113fd5d1192e6f12e344`.
  The three new x86 symbols resolve with the expected decorations, B156
  runtime-toggle/restoration validation passes, and all 219 tests pass with
  one intentional skip. Live 1/2/3-slot, gender, persistence, and reset QA
  remains.

## 2026-07-24 - Lifetime generation counter beyond the rolling tree

- Stock `CFamilyTree::StartNextGeneration` calls `MakeRoomInTree` when
  `CFamilyTree+4` is 30. `MakeRoomInTree` shifts the 29 newer records over the
  oldest record and decrements the stock count to 29; the unchanged native
  start routine then increments it back to 30. The persistent family-tree
  layout therefore remains a rolling 30-generation window.
- B156 retargets the only two native `StartNextGeneration` callers
  (`CFamilyTree::StartFamilyTree` and `CAdoptionScene`) through a same-ABI
  wrapper. The wrapper calls native first and increments only when native
  returns true.
- The lifetime count uses hidden achievement record `0xA8`, field `+4`, bits
  8-31. Existing Taters and pregnancy-control bits remain in bits 0-7. An
  existing save whose lifetime field is zero seeds from the current stock
  `CFamilyTree+4` value, so its next successful generation continues from the
  best count the old save can supply.
- The Goals scene calls a dedicated draw helper after resetting the
  achievement-list clipping rectangle and displays `Generation: N`. This is
  not an achievement row and does not alter visible-goal counts or Achiever
  Extraordinaire.
- Reset Achievements preserves bits 8-31 around the native achievement reset.
  A real new-game reset still clears the achievement block and therefore
  starts the lifetime counter over.
- All 16 B156 executable layouts link uniquely and pass Holiday plus four-flag
  enable/idempotence/restore validation. The fully enabled raw linked image is
  1,766,400 bytes with SHA-256
  `e4064ef91c8a55a33a73fcc06d2bec5dcd5b736ff4c1fcf8c812ad5e215bcf1f`.
  The focused generation-hook/Goals-draw contract test passes. Live
  transition, persistence, visual-placement, 30-to-31 rollover, and new-game
  reset QA remains.
- B158 same-sex marriage support uses a separate default-zero writable
  `.vf2same` byte. When enabled, the only proposal edit is after native
  `GetVillager` returns: the spawned candidate's `CVillager+0x6A58` gender field
  is flipped to the other value. The native opposite-sex spawn argument and the
  proposal scene's Accept, Reject, close, proposal-state, parent-storage, and
  candidate-selector paths remain stock.
- An established enabled same-sex spouse pair is routed to the native
  equal-gender private-romantic-time sequence. Its `TryToMakeBaby` entry returns
  before `ChanceOfPregnancy`/`Impregnate`, so pregnancy is 0%; the pair does not
  use the native refusal or argument outcomes. Opposite-sex couples, non-spouse
  drops, and the flag-off state retain their native routes.
- B158 Behavior Patches extends the same native private-romantic-time detour only
  for an exact current-generation opposite-sex adult spouse pair whose native
  FamilyTree child-slot count at current-record `+0x1B4` is at least six. The
  route bypasses the native refusal/argument branch, and the shared
  `TryToMakeBaby` entry returns before `ChanceOfPregnancy`/`Impregnate`, making
  this action 0% pregnancy. The helper is compile-gated by
  `VF2_ENABLE_BEHAVIOR_PATCHES`; the behavior-disabled executable retains stock
  opposite-sex routing.
- The complete B156 matrix links 16 unique executable layouts. Holiday
  positive/negative validation passes 8/8, and the five default-zero runtime
  controls (`.vf2beh`, `.vf2goal`, `.vf2preg`, `.vf2same`, `.vf2mort`) are
  non-overlapping and restore exactly after enable/re-enable/disable cycles.
  The fully enabled raw layout is 1,767,936 bytes with SHA-256
  `3910A0F2FC67B25D6A86A44F64676507B1F75BFAF2A9D6A607BA86F13E53E61E`;
  its `.vf2same` byte is raw `0x19FA00`, RVA `0x771000`.
- `CDatingScene::HandleMessage(8, 2)` is the stock Reject route. It previously
  deactivated the current candidate, cleared the scene candidate ID, copied
  and cleared the proposal timestamp fields at `theGameState+0x25CB8` and
  `+0x25CBC`, and returned from the scene. B156 now retargets that route's
  existing call relocation to `GeneratePeepCandidate`.
- The native generator already deactivates any current temporary candidate
  before spawning one replacement and refreshing every proposal control.
  Reject therefore rerolls in place without changing the email/timestamp
  fields. `HandleMessage(8, 1)` remains the byte-identical stock Accept route.
  The replacement traverses the `.vf2same` gender helper, preserving the stock
  opposite-sex result when disabled and independently choosing either gender
  when enabled.

## 2026-07-24 - Adoption Services baby-or-child chooser

- The desktop Adoption Services fulfillment route is
  `CScrollingStoreScene::HandleUpgrade+0x57A`. Stock pushes internal age
  `0x3C` (displayed age 3), body `-1`, and gender 1, then calls the
  three-argument `CVillagerManager::SpawnSpecificPeep` overload. That overload
  continues through the full native `CVillager::Init` path.
- B156 replaces only that fulfillment block with a guarded helper. The helper
  first requires `CFamilyTree::EmptyOffspringSlots()>0`, then displays native
  two-button choices for Baby and Child (Age 2-8). Baby supplies internal age
  0. Child uniformly supplies `(GetRandom(7)+2)*20`, corresponding to displayed
  ages 2 through 8. Both choices independently select female or male with
  native `GetRandom(2)`.
- Exactly one native three-argument spawn call occurs per fulfilled purchase.
  The returned villager goes through native `CFamilyTree::AddOffspring`, and
  stock adoption achievements `0x0C` and `0x0D` are incremented only after the
  tree accepts the villager. Invalid spawn and tree-add failures skip the stock
  completion message; a failed tree add also deactivates the just-created
  villager.
- The stock message box returns 0 for its first button and -1 for its second.
  Escape follows the second-button route, so after the player has confirmed
  the Adoption Services purchase, this chooser treats Escape as Older Child
  rather than as a third cancel outcome.
- Local desktop disassembly establishes the PC route and the safety contracts
  above. No preserved VF3 binary/source evidence in this workspace establishes
  that the exact dialog, random-age formula, or button semantics match VF3;
  B156 therefore documents this as the requested VF3-style desktop behavior,
  not a byte-for-byte VF3 code port.
- All 16 B156 executable layouts link with unique hashes. Holiday
  positive/negative validation passes 8/8, and the five dormant runtime
  controls remain non-overlapping, idempotent on repeated enable, and exactly
  restorable. The fully enabled executable is 1,767,936 bytes with SHA-256
  `02894926C99A4080F76B1E8CA36F6746471985F77FA8EFDD4E3F6B87A24B9181`.
  All 226 tests pass with one intentional skip. Live
  purchase/save/family-tree QA remains.

## 2026-07-24 - Pavlovian Association exact praise goal

- Preserved project history defines Pavlovian Association as praising someone
  while they are training a pet. B156 materializes reserved achievement row
  `0x93` with target 1 and requires the exact current label `Training pet`.
- The existing praise hook copies the complete 0x28-byte action label before
  native `ForgetPlans` clears it. The new goal reuses that route; near matches
  do not award it, and no additional gameplay detour is installed.
- Row `0x93` is added to `achievementOrder` only in Behavior-enabled layouts.
  Achiever Extraordinaire retains ID `0x92`, remains the final visible row,
  and includes Pavlovian only when the goal is visible.
- All 16 B156 layouts link uniquely. Holiday validation passes 8/8 positive
  and 8/8 negative, all five runtime flags restore exactly, and all 226 tests
  pass with one intentional skip. The fully enabled executable is 1,767,936
  bytes with SHA-256
  `4939C32A1A6907193984F0B0AA2A1763224A379D579B2A6683E088879E8F107B`.
  Live praise, notification, persistence, reset, and patch-off QA remains.

## 2026-07-24 - B156 Exact-Action and Discipline Goal Completion

- Desktop `theMainScene::InvokeScolding` checks stock achievements `0x2D`,
  `0x2E`, and `0x2F` for three exact behavior IDs and increments aggregate
  achievement `0x30` after each qualifying scold. Therefore stock Tight Ship
  `0x30` is sufficient evidence that all three stock discipline goals,
  including No jumping on the bed, are complete.
- The four genuinely new child-discipline rows use `0xA1-0xA4`. Props to you
  uses `0xA5` and requires Tight Ship plus those four rows; no unverified stock
  sub-achievement ID is duplicated.
- The exact reachable social action is `Posting on Picstagram`, although the
  requested Last Trend achievement text says Clipstagram. Matching uses the
  reachable action label and preserves the requested player-facing text.
- Exact scold awards must not return from the outer wrapper before the original
  ForgetPlans call. The generated cases now complete a goal, check Props, and
  then execute the native cleanup exactly once.

## 2026-07-24 - B156 Furnishing the Future Scope

- The archived requirement is exact: “Buy any Virtual Families 3 furniture
  item (Anything added by the Virtual Families 3 furniture patch).”
- The currently active imported VF3 catalog contains nine items: six
  couches/loveseats at `0x2F6-0x2FB` and three televisions at `0x324-0x326`.
  The earlier batch-01 list is intentionally empty and therefore contributes
  no qualifying IDs.
- The general purchase observer is the correct route because it awards only
  after native AddToStorage succeeds and is independent of Holiday Furniture
  goal visibility.

## 2026-07-24 - Mobile Holiday Candles exact behavior record

- Mobile x86 `CBehavior::CBehavior` installs `KidExaminesCandles` at behavior
  slot `0x19B`; the function pointer is `0x1B7130`.
- Mobile `CVillager::InitAI` switch entry `0x19B` enables the candidate, assigns
  weight `0x7D0` (2000), object `0x89`, and age field `0x118`. This is direct
  candidate evidence for the child gate rather than an inference from the
  method name.
- `KidExaminesCandles` finds EObject `0x89`, labels the action
  `Playing with holiday candles`, and performs two orientation-aware
  inspections. Its 30-percent branch asks `GetRandomVillager(2, 1, 0)` for
  another villager, pauses that villager, approaches at offset `(20,75)`, and
  completes the recovered sound/wait/work sequence. With no matching villager,
  it uses EObject `0x1A` and prop `0x10`.
- Raw `CandleOnHolder.png.fmap` cells `(5,7)` and `(6,7)` combine the same
  object bits with unsupported mobile metadata; `(5,8)` carries the bare
  object payload. The desktop-safe translation retains only `0x20004800` at
  those three cells.
- Desktop behavior slot `0x19B` does not exist. B156 therefore implements the
  exact guarded manual plan externally and leaves spontaneous candidate
  selection unresolved rather than indexing beyond the fixed table.
- The complete 230-test run passes with one intentional skip. All 16 B156
  layouts link uniquely, pass 8 Holiday-positive and 8 Holiday-negative
  checks, and pass exact restoration for all five dormant runtime flags. The
  fully enabled layout is 1,772,544 bytes with SHA-256
  `74BA49761CC2DDC1070AFBB1E6FC812D15C225113D5D37E589766F7B80A59859`.

## 2026-07-24 - Mobile Santa-cookie behavior pair

- Mobile behavior slots `0x1A5` and `0x1A6` are
  `KidStealsSantasCookies` and `AdultsSaveSantasCookies`; both find EObject
  `0x8F`.
- Mobile `CVillager::InitAI` enables only child behavior `0x1A5`, with weight
  `2000`, object `0x8F`, and boundary field `0x118`. Adult behavior `0x1A6`
  uses the default disabled candidate record and is reached directly.
- The child plan uses `Stealing Santa's cookies`, speed `140`, exact
  orientation/head-direction waits, and then asks
  `GetRandomVillager(2,-1,0)` for an adult of either gender. A found adult is
  interrupted and given the exact `Rescuing Santa's cookies` response with
  gender-specific sounds. The child then leaves for EObject `0x16`.
- The direct adult plan is the shorter rescue sequence: gender-specific alert,
  speed-350 approach, gender-specific scold, sound stop, and behavior restart.
- Raw `PlateOfCookies.png.fmap` is `9x9`; its only functional anchors are
  clean object cells `0x20007800` at `(6,8)` and `(7,8)`. The PC-safe
  translation keeps only those two cells.
- The complete 230-test run passes with one intentional skip. All 16 B156
  layouts link uniquely, pass 8 Holiday-positive and 8 Holiday-negative
  checks, and pass exact restoration for all five dormant runtime flags. The
  fully enabled layout is 1,773,568 bytes with SHA-256
  `A31601B316144E2FAE4B6BFE48CA4BD8E9B635DD68CA3590BF567BF0BFBA575F`.

## 2026-07-24 - Mobile Christmas figurine and house-decoration object proof

- Scanning all 41 preserved mobile QAMFs by encoded EObject bits finds object
  `0x8C` only on Gnome1-5, Penguin Decoration, Polar Bear Decoration,
  Reindeer Decoration, Santa Garden Decoration, and Snowman.
- The same scan finds object `0x8D` only on Red Bow, Santa Wall Decoration,
  String of Leaves, and String of Lights. Wreath1 and Wreath2 contain only
  `0x01840000` wall-mask cells and therefore do not prove the house-decoration
  route.
- Mobile `CVillager::InitAI` case `0x1A4` enables weight `2000`, raw-age
  minimum `7`, furniture-required byte `1`, and object `0x8C`. Case `0x1A7`
  enables weight `2000`, raw-age minimum `0x118`, furniture-required byte `1`,
  and object `0x8D`.
- `AdmiringXmasKnickKnacks` labels `Enjoying the figurines`, approaches at
  speed 200, plays the villager Oh sound, cheers for 2-5 ticks, waits for 2-5
  ticks in an orientation-aware pose, and joy-twirls twice.
- `InteractHouseXmasDecor` labels `Checking the decorations`, performs two
  approaches, preserves gender sounds `0x8C/0x99` and `0xCC/0xD3`, sounds
  `0xB5` and `0xE8`, random 3-5 and 2-3 work phases, an orientation-aware
  wait, and sound stop.
- B156 ports both manual plans externally and creates fourteen minimal QAMFs
  with only `0x20006000` or `0x20006800` anchors. It does not index mobile
  behavior slots beyond the desktop table.
- The offline asset overlay now enumerates all 33 implemented behavior maps.
  This also fixes the earlier omission of the already-implemented Candle and
  Cookie maps from player-facing enable/restore records.
- The complete 230-test run passes with one intentional skip. All 16 B156
  layouts link uniquely, pass 8 Holiday-positive and 8 Holiday-negative
  checks, and pass exact restoration for all five dormant runtime flags. The
  fully enabled layout is 1,774,080 bytes with SHA-256
  `7E7389620C19BAF1409332809EAB4BB9F26E19BE367C288116C0CA89CAF0DFA1`.

## 2026-07-24 - Mobile Eggnog exact behavior record

- Mobile `CVillager::InitAI` case `0x1A1` enables `CBehavior::Eggnog` with
  weight `2000`, furniture-required byte `1`, object `0x8B`, and maximum-age
  boundary field `0x118`.
- `CBehavior::Eggnog` labels the action `Stealing egg nog`, approaches the
  selected furniture, performs an orientation-aware inspection, then visits
  EObjects `0x70`, `0x15`, and `0x59` at speed `350`.
- The exact plan contains sound `0x6D`, three sound `0x3D` calls, twelve jumps,
  a 2-6 count joy twirl, 2-4 count clockwise and counterclockwise plan twirls,
  and a final 4-13 tick wait. It has no stat writes and no stop-sound call.
- Raw `GlassOfEggnog.png.fmap` is `7x6`; cells `(3,5)` and `(4,5)` carry the
  only functional object bits. The PC-safe translation keeps only
  `0x20005800` at those cells and hashes to
  `22562ac31d52fcf4bb6b786423653566483166091c87255ca5e304d623a9b792`.
- B156 ports the raw-age-through-`0x117` manual plan externally and leaves
  spontaneous behavior `0x1A1` unindexed beyond the fixed desktop table.
  The offline behavior overlay now contains 34 exact enable/restore maps.
- The complete 230-test run passes with one intentional skip. All 16 B156
  layouts rebuild uniquely, pass 8 Holiday-positive and 8 Holiday-negative
  checks, and pass exact restoration for all five dormant runtime flags. The
  fully enabled layout is 1,775,104 bytes with SHA-256
  `CC46BA5FA861928AD1DEE58335C0F6A3AA1F24B4758C38B5A3E42A0DB6CD2332`.

## 2026-07-24 - First exact mobile Island Event outcomes

- `CEventMeteoriteFallsInYard1::CanFire` at mobile `0x119C50` returns false
  unconditionally. `ImpactGame` at `0x119C80` and `CalcAward` at `0x119C90`
  are empty. The event is a dummied-out shell, not a rare-collectible event.
- `CEventStrangePackageOnPorch::CanFire` at `0x11A7F0` requests a random
  adult. `CalcAward` at `0x11A8F0` returns `GetRandom(100) + 50` for choice
  zero and zero otherwise. `ImpactGame` at `0x11A8A0` applies that award
  through `CMoney::Adjust(..., true)`.
- `CEventTeens::CanFire` at `0x11B4D0` selects any-gender villagers in the
  inclusive raw-age interval 260-340. `CalcAward` at `0x11B600` returns zero
  for choice zero and -75 for choice one. `ImpactGame` at `0x11B590` spawns
  exactly 10 socks and 10 trash for choice zero, or applies the -75 award for
  choice one. No stain-spawn call occurs.
- The desktop binary does not export `GetRandomVillagerByAges`. The external
  implementation therefore scans the 30 resident slots with
  `VillagerExists`, reads raw age at `CVillager+0x6A54`, keeps values 260-340,
  and selects one eligible entry using `GetRandom(count)`.
- The previous experimental event-outcome batch encoded unsupported effects
  and was removed after the exact routes replaced it.
- `CBehavior::UsingWarmTowel` at mobile `0x18FAD0` is behavior `0xE7` using
  EObject `0x50`. The desktop behavior has the same object, approach/work/
  arm-swing plan, and dirtiness reduction. Brown and Pink Towel Set maps do
  not contain a proven EObject `0x50` binding, so no furniture route was
  invented from their names or descriptions.
- All 231 tests pass with one intentional skip. All 16 B156 layouts link
  uniquely, pass 8 Holiday-positive and 8 Holiday-negative checks, and pass
  exact restoration for all five dormant runtime flags. The fully enabled
  layout is 1,775,616 bytes with SHA-256
  `FE659A21E475CE4EED652BF647437928738BB91AAC4483A5F884BD723383FD6D`.

## 2026-07-24 - Second exact mobile Island Event outcome group

- `CEventInvitation::CanFire` at mobile `0x119E20` stores a random adult from
  selector `2` in target 1 and a random child from selector `1` in target 2,
  and succeeds only when both exist.
- `CEventInvitation::CalcAward(int)` at `0x119F70` always stores zero.
  `ImpactGame(int)` at `0x119EF0` gives all children +20 happiness and runs
  behavior `100` over raw ages `7..280` for choice zero; choice one gives all
  children -20 happiness and runs behavior `251` over the same range.
- `CEventFruitcakes::CanFire` at `0x119B00` returns false unconditionally.
  Its unreachable `CalcAward(int)` at `0x119C00` stores -25 for choice zero
  and zero otherwise. Its mobile target-dependent impact at `0x119B60`
  adjusts money, adds inventory item `42`, starts behavior `26`, and sets
  symptom `5`; B156 does not execute that route because exact scheduling
  never supplies its target.
- `CEventGreatUncleElmer::CanFire` at `0x11B850` returns false even though
  `IsEmailEvent` at `0x11B880` returns true. Its unreachable impact at
  `0x11B890` adds furniture item `0x24B` to storage.
- `CEventMarchingBandTripExpenses::CanFire` at `0x11B900` returns false even
  though `IsEmailEvent` at `0x11B930` returns true. `CalcAward` at `0x11B980`
  stores -50 and `ImpactGame` at `0x11B940` applies it.
- `CEventLoanReturned::CanFire` at `0x11B9C0` returns false. `CalcAward` at
  `0x11BA30` stores +20 and `ImpactGame` at `0x11B9F0` applies it.
- Desktop `CIslandEvents::FireEvent` first requires `CanFire`, then filters on
  `IsEmailEvent`; email classification does not bypass a false firing gate.
- All 231 tests pass with one intentional skip. The 16-layout matrix has 16
  unique hashes, passes 8 Holiday-positive and 8 Holiday-negative checks, and
  passes exact toggle/restoration for all five runtime flags. The fully
  enabled executable is 1,775,616 bytes with SHA-256
  `EE9433E810C62153168CEE44DDF1892DBBE42D546169D339CBD51C62A8EE9010`.

## 2026-07-24 - Third exact mobile Island Event outcome group

- `CEventBlastFromThePast::CanFire` at mobile `0x11A960` selects any-gender
  adult. `CalcAward` at `0x11AA40` stores `GetRandom(50)+50`, and
  `ImpactGame` at `0x11A9E0` applies that 50-99 coin award plus 15 target
  happiness trend.
- `CEventEmailFromACME::CanFire` at `0x11B160` selects an adult male.
  `CalcAward` at `0x11B230` stores 70 and `ImpactGame` at `0x11B1F0`
  applies it through `CMoney::Adjust`.
- `CEventEmailFromAntonioGuildenstern::CanFire` at `0x11B270` selects an
  any-gender adult. `CalcAward` at `0x11B350` stores zero. `ImpactGame` at
  `0x11B300` calls `MakeAllVillagersDoIt(424,7,7,-1,null,0)` and adds 15 to
  the target adult's happiness trend.
- `CEventEmailFromSchool::CanFire` at `0x11AAA0` requires a random child and
  chooses randomly among the available matriarch and patriarch for target 1.
  `CalcAward` at `0x11AC00` stores 75-174. `ImpactGame` at `0x11AB90`
  starts behavior `88` on the parent and writes byte 1 at parent offset
  `0x6B74`. B156 now ports this route through the desktop-native selectors,
  `NewBehavior`, and `StartNewBehavior` symbols.
- `CEventInterestingArticleAboutFossils::CanFire` at `0x11A360` selects an
  adult. `ImpactGame` at `0x11A3F0` starts behavior `100`, adds 10 happiness
  trend, chooses carrying `GetRandom(12)+103`, x
  `GetRandom(260)+1212`, and y `GetRandom(126)+1829`, then calls
  `CCollectableItem::Add(..., false)`. B156 now ports this route through the
  desktop-native by-value `ldwPoint` collectible ABI.
- All 231 tests pass with one intentional skip. The complete 16-layout matrix
  has 16 unique hashes, passes 8 Holiday-positive and 8 Holiday-negative
  checks, and passes exact toggle/restoration for all five runtime flags. The
  fully enabled executable is 1,776,128 bytes with SHA-256
  `2FF43E7E5500E0AE22754F4D72384AC528800DDCD470A4CF7BA80CF6D849A36B`.

## 2026-07-24 - School email and Fossils desktop integration

- The existing desktop helper contract confirms `CVillagerPlans` begins at the
  `CVillager` object, `CVillager::NewBehavior` accepts
  `SBehaviorData const&`, and `CCollectableItem::Add` accepts
  `(ECarrying, ldwPoint, bool)` with the two-int point passed by value.
- Email from School stores the selected parent in target 1 and the selected
  child in target 2, preserving dialog substitutions as well as the parent
  behavior/state effect.
- Interesting Article About Fossils uses carrying values `103..114`, which are
  the twelve base fossil variants, and the exact mobile yard rectangle rather
  than a generic collectible spawn helper.
- All 231 tests pass with one intentional skip. The complete 16-layout matrix
  has 16 unique hashes, passes 8 Holiday-positive and 8 Holiday-negative
  checks, and passes exact toggle/restoration for all five runtime flags. The
  fully enabled executable is 1,776,640 bytes with SHA-256
  `A4059B461F52E3D8246FCC95D688CF3AB82DF2CB598E340DEA0395594DB53CF3`.

## 2026-07-24 - Fourth exact mobile Island Event outcome group

- `CEventMeteoriteFallsInYard2::CanFire` at mobile `0x119CD0` uses numeric
  age selector `7` with any gender. `CalcAward(int)` at `0x119DD0` stores 50
  for choice zero and zero otherwise; `ImpactGame(int)` at `0x119D80`
  applies the choice-zero award.
- `CEventClownHoldingMetalRod::CanFire` at `0x11A500` selects an adult.
  Choice zero at `0x11A5B0` stores furniture item `0x23C`, adds like `0x24`,
  removes dislike `0x24`, adds 15 target happiness trend, and adds 15
  happiness to all children. Choice one has no effect.
- The desktop villager layout was independently recovered from PC code before
  porting the Clown outcome: `CLikeList` is at `CVillager+0x1BC34` and
  `CDislikeList` is at `CVillager+0x1BC40`. The mobile object offsets were
  not copied into the PC helper.
- `CEventMenInBlackAtDoor::CanFire` at `0x11AE80` selects an adult. Both
  choices at `0x11AF30` start behavior `0x171`; choice zero also stores
  furniture item `0x219`.
- `CEventHearStrangeSound::CanFire` at `0x11B390` uses numeric age selector
  `7` with any gender. Choice zero at `0x11B440` stores furniture item
  `0x242` and adds 20 target happiness trend; choice one has no effect.
- `CEventMetallicKnockingOnDoor::CanFire` at `0x11B650` returns false
  unconditionally. Its unreachable choice-zero calculation at `0x11B700`
  stores 50 and its unreachable impact at `0x11B6B0` applies that award.
- All 231 tests pass with one intentional skip. The complete 16-layout matrix
  has 16 unique hashes, passes 8 Holiday-positive and 8 Holiday-negative
  checks, and passes exact toggle/restoration for all five runtime flags. The
  fully enabled executable is 1,776,640 bytes with SHA-256
  `57D2161408891891E3D19BBC77D7D889A312A0FE43DF98D1E78C1E606F28C57F`.

## 2026-07-24 - Final seven mobile Island Event outcomes

- `CEventGroupOfKidsAtTheDoor::CanFire` at mobile `0x11AD10` selects an
  adult. Choice zero at `0x11ADC0` stores item `0x23C` and adds 20 target
  happiness trend. `CalcAward(int)` at `0x11AE10` calculates 50-149 for
  choice zero, but the mobile impact does not apply that value to Money.
- `CEventMissionFromGod::CanFire` at `0x11B750` returns false
  unconditionally. Its unreachable choice-zero route calculates -20, applies
  it to Money, and calls `CVillagerManager::CureAllVillagers`.
- `CEventOddOldWomanAtDoor::CanFire` at `0x11A120` requires an adult and a
  post-interest Money balance greater than 20. Choice zero calculates 5-14,
  subtracts that amount, sets symptom `6`, starts behavior `175`, and adds 10
  happiness trend. Choice one sets the same symptom/behavior and subtracts 10
  happiness trend without changing Money.
- The PC Money layout was verified before porting the gate: `CMoney` stores
  its balance as the leading double, and the private desktop
  `UpdateInterest()` method is called before comparing it to 20.
- `CEventRIPUncleAlpert::CanFire` at `0x11A680` selects an adult.
  `CalcAward()` at `0x11A790` calculates 75-174. `ImpactGame()` at
  `0x11A6F0` applies it, stores item `0x1F5`, and starts behavior `23`.
- `CEventResurrectionOfAgatha::CanFire` at `0x11AC60` returns false
  unconditionally. Its unreachable calculation stores -100 and its
  unreachable impact applies that amount to Money.
- `CEventSurpriseVisitFromUnclePhineas::CanFire` at `0x11B000` uses numeric
  selector `7`. Its impact stores item `0x207`, adds like `0x6D`, removes
  dislike `0x6D`, forgets current plans with `false`, and assigns behavior
  `23` without calling `StartNewBehavior`.
- `CEventVolunteer::CanFire` at `0x119FB0` selects an adult. Choice zero
  applies the negation of its zero award, runs behavior `100` for raw age
  exactly `7`, and advances the target's career with `(false, true)`.
- These routes complete function-level firing, award, and impact coverage for
  all 25 added mobile Island Events. Live in-game dialog, targeting, effect,
  persistence, and patch-off validation remains.
- All 231 tests pass with one intentional skip. The complete 16-layout matrix
  has 16 unique hashes, passes 8 Holiday-positive and 8 Holiday-negative
  checks, and passes exact toggle/restoration for all five runtime flags. The
  fully enabled executable is 1,777,664 bytes with SHA-256
  `D85E067CBB3B7A4F647B693F946810CA5209B1454CCBEA5BD78AB2B9EBD6FA3B`.

## 2026-07-24 - Exact Lucky Rock and Holiday Ornament odds

- Mobile `CCollectableItem::Update` at `0x104A30` reads the Lucky Rock byte at
  `CCollectableItem+0x8A8`. Without it, the random gate accepts values 0-2
  from `GetRandom(6600)`, or `3/6600 = 1/2200` per Update. With it, the same
  gate uses `GetRandom(3300)`, or `3/3300 = 1/1100`.
- Mobile `CCollectableItem::Add` at `0x1044A0` selects one registered spawn
  area, then a value in `base..base+3`, then applies rarity offsets from a
  100-way roll. Without Lucky Rock, rolls 0-3 add 8 (4% rare), rolls 4-16 add
  4 (13% uncommon), and 17-99 remain common (83%). With Lucky Rock, rolls 0-7
  are rare (8%), 8-33 uncommon (26%), and 34-99 common (66%).
- Holiday Ornament base `0x9E` is one of the normal registered spawn-area
  entries. The same generic offsets therefore produce common `0x9E-0xA1`,
  uncommon `0xA2-0xA5`, and rare `0xA6-0xA9`; there is no separate ornament
  scheduler that could bypass Lucky Rock.
- The PC stock functions use the same byte, limits, thresholds, and offsets.
  The Holiday validator now requires both complete `Update` and `Add` function
  bodies to remain byte-identical to the stock PC objects.
- All 232 repository tests pass with one intentional skip. The complete
  16-layout B156 matrix passes, including eight Holiday-positive and eight
  Holiday-negative layouts. The fully enabled executable is 1,777,664 bytes
  with SHA-256
  `F3EE7955D59380C5B9259C88BA494C6F5737BA36CF03AB3F4BE7C899994229AE`.

## 2026-07-24 - Exact mobile Special Upgrade state and effects

- Mobile Brokerage Account case 29 adds the exact float constant `0.02` to
  `CMoney+0x08`. `CMoney::SaveState` writes the rounded percentage encoding
  at `SSaveState+0x04`; `LoadState` accepts values through `0.11` and restores
  the stock `0.01` rate for out-of-range values. The PC visible upgrade keeps
  the requested immediate 11% ceiling and removable reset to 1%.
- Mobile `CFoodStore::JoinFoodClub` sets active byte `+0x7C`, records current
  game seconds at `+0x80`, and calls `DoFoodClubDelivery(1)`. Each delivery
  adds `500 * count` food, refreshes all four nutrition groups, and advances
  achievement `0x1D`. `Update` repeats delivery for each elapsed 86,400
  game-time seconds. Save/load copies food `+0x78`, active `+0x7C`, timestamp
  `+0x80`, and organic bytes `+0x84-0x87` through a 16-byte save structure.
- Mobile Health Plan uses `theGameState+0x25B35`. Stock
  `CInventoryManager::GetPrice` applies it only to item IDs `0x18-0x21` and
  divides their price by four. That byte lies outside the base save copy and
  is reapplied by `CPurchaseManagerImpl::Gift` from mobile purchase
  entitlement.
- Desktop has the same hidden price route at `theGameState+0x25B1D`, but no
  mobile entitlement restorer. B156 now stores Health Plan ownership in the
  otherwise-unused dword at hidden achievement record `0xA8+0x08`,
  synchronizes the stock byte during the existing money-load reconciliation,
  and preserves the paid-upgrade field when Reset Achievements runs. The
  Taters/pregnancy/generation mask remains independently stored at record
  `+0x04`.
- Clean verification passed all 16 executable layouts, the linked Holiday
  positive/negative validator, runtime-toggle validation, and all 234
  repository tests (one intentional skip). The fully enabled executable is
  1,777,664 bytes with SHA-256
  `E3DDB645D9228EF5252E6E636AED5D2A175965F6DA7E111F97531930DB43CE52`.

## 2026-07-24 - Candy Cane, Single Cookie, Poinsettia, and Wreath behavior closure

- Mobile `CContentMap::GetObject` decodes
  `((cell >> 11) & 0x7F) | ((cell >> 22) & 0x80)`.
  `CContentMap::GetHotSpot` decodes `(cell >> 18) & 0x7F`.
- Every nonzero Candy Cane `0x2AB`, Single Cookie `0x2AC`, and Wreath
  `0x2D4-0x2D5` map cell is `0x01840000`, yielding EObject `0` and hotspot
  `0x61`. Every nonzero Poinsettia `0x2BF` cell is `0x01800000`, yielding
  EObject `0` and hotspot `0x60`.
- The exact mobile `CHotSpot` constructor initializes its table to null and
  never assigns handlers `0x60` or `0x61`. `CHotSpot::Dispatch` returns false
  when the selected entry is null.
- Mobile `theMainScene::DropVillager` reads a content-map hotspot and sends it
  to `CHotSpot::Dispatch`; it contains no furniture item-ID comparison or
  fallback. These five items are thus decorative only in mobile. B156 should
  not invent behavior maps or attach nearby Holiday actions to them.
- The new negative contract passes the fully enabled generation/link, all
  linked cross-layout validators, and all 235 repository tests (one
  intentional skip). The fully enabled executable is 1,777,664 bytes with
  SHA-256
  `2EF83392E11DE07CF52F45BF1F1FC6BEDF62F0742D7148AE4C702720867426E1`.

## 2026-07-24 - Additive autonomous mobile Holiday behavior selector

- Desktop `CVillagerAI::DecideWhatToDo` scans exactly `0x19B` fixed-size
  candidate records, ending at behavior `0x19A`, then performs one weighted
  random selection. Extending or indexing that array remains unsafe.
- B156 now inserts a guarded external weighted draw immediately before the
  native final draw. It includes only the five mobile candidates with exact
  recovered weights and predicates: Holiday Candles `0x19B`, Eggnog `0x1A1`,
  Santa-cookie stealing `0x1A5`, Christmas figurines `0x1A4`, and house
  decorations `0x1A7`. Each has weight `2000`, its proven EObject gate, and
  its exact raw-age boundary.
- The combined range is `stockWeight + eligibleExternalWeight`. A stock result
  falls through to the unchanged native weighted draw, preserving the
  conditional distribution of every stock candidate. An external result
  starts the already-ported exact plan and exits through the native function
  epilogue.
- When Mobile Furniture Behaviors is disabled, the helper returns false before
  drawing and the native selector runs unchanged. No stock candidate is
  replaced, and the behavior table remains `0x19B` entries.
- Adult Santa-cookie rescue remains direct/manual only, matching the mobile
  candidate table. Patio and Picnic autonomous pairs `0x1B4-0x1B7` were the
  next external-selector tranche and are documented in the following entry.
- All 236 repository tests pass with one intentional skip. Both the
  behavior-disabled core and fully enabled layouts compile and link with the
  new selector. The core executable is 1,708,032 bytes with SHA-256
  `F5BF187D620C1560252842A7AFB01A93859DEAFD7046374F486BC6A172FBB4D7`;
  the fully enabled executable is 1,778,176 bytes with SHA-256
  `8D6E731B7966212A2BA03569B87AE3035A48582363C2DD85DE7491BDB2557F8E`.
- The linked 16-layout Holiday validator still passes 8/8 positive and 8/8
  negative layouts. Runtime validation confirms 16 unique hashes and exact
  enable/idempotence/disable restoration for all five dormant flags.

## 2026-07-24 - Exact Patio and Picnic autonomous candidate records

- IDA recovered the complete mobile `CVillager::InitAI` records for behaviors
  `0x1B4-0x1B7` and the corresponding `CVillagerAI::DecideWhatToDo` predicate
  and dynamic-weight passes.
- Preparing Picnic (`0x1B4`) and Preparing Drinks (`0x1B6`) are sunny-day
  candidates with base weight 3000. They require raw age `0x118+`, EObject
  `0x97` or `0x98`, healthy status, no carried/nursed baby, exact minimum need
  values 10/15/40, the matching ready prop inactive, and no villager already
  doing the same preparation. Need values above 50/60/70 triple the weight.
- Eat at Picnic Table (`0x1B5`) and Drink at Patio Chair (`0x1B7`) are
  sunny-day candidates with base weight 12000. They require the matching ready
  prop active, the matching object, and the recovered minimum hunger value 30;
  hunger above 70 triples the weight.
- Picnic candidates additionally use like IDs 39 and 40. A matching like
  triples weight, and a matching dislike quarters it unless a 3x condition
  already won the mobile branch order. Patio candidates have no like field.
- Neither autonomous preparation record nor its behavior body checks
  `CFoodStore.food`. The food-31 warning belongs only to the manual hotspot
  route and is therefore not added to spontaneous selection.
- The desktop port keeps all four IDs outside the fixed `0x19B` candidate
  array. The external selector evaluates their predicates, combines eligible
  weight with the native total, and starts the already ported plan sequence.
  External preparer pointers reproduce the mobile
  `GetVillagerDoing(0x1B4/0x1B6)` exclusion and clear when the action label
  changes or the matching ready state activates.
- Mobile InitAI adjusts each base weight once per villager by
  `GetRandom(base/5)`, subtracting when a fresh `GetRandom(100)` is below 50
  and adding otherwise. The external cache now performs that same
  initialization for all nine external Holiday/Patio/Picnic candidates from
  the shared InitAI/LoadAI hook. The disabled patch still returns before any
  added random draw.
- All 236 repository tests pass with one intentional skip. The fully enabled
  layout regenerates, compiles, links, and passes the debugger-hook validator
  at 1,779,712 bytes with SHA-256
  `2976615E909C510FC5ABBEB6E3B45A576773F7EBEC2E2B897396B7EA19E074D8`.
  Focused linked runtime validation confirms all five dormant flag sections,
  exact enable bytes, repeated-enable idempotence, and byte-perfect restore.
- A current-source 16-layout claim is intentionally withheld: the older
  `cheat_upgrades_holiday_ornaments` output is a stale partial-matrix remnant
  without `.vf2beh`. The current fully enabled layout itself passes the linked
  Holiday positive check.

## 2026-08-06 - Patio and Picnic readiness persistence boundary

- The desktop port's Patio `0x56` and Picnic `0x55` readiness states remain
  external guarded timers. They use `CGameTime::Seconds()` and the recovered
  240-game-second duration, but they are not part of a native component
  `SSaveState` record.
- The recovered `theGameState::Load(int)` path loads `0x25B18` bytes into a
  temporary `theGameData` object and copies them to `theGameState+0x08`.
  `theGameState::Save(int)` serializes the same `0x25B18`-byte span. This is
  the only proven fixed-size game-state save route in the checked desktop
  evidence.
- The nearby state offsets are not a safe arbitrary extension: `+0x25B1C` is
  used by the night state and `+0x25B1D` is used by the desktop Health Plan
  price route. `+0x25B1E` and `+0x25B1F` have no current disassembly references,
  but they have no version marker or independently proven field ownership and
  sit at the end of the copied region next to the final villager record tail.
- No native-compatible way to encode both active states and their deadlines,
  validate old saves, and rehydrate the external pointers/timers after
  `LoadCurrentGame` was proven. Therefore no persistence patch is shipped;
  the source remains fail-closed until a safe ABI or explicitly versioned
  sidecar is evidenced. This does not change the separate B157 room-overlay
  renderer or its exact 1:1 image placement.

## 2026-08-06 - Increase Child Limit fail-closed ABI contract

- The stock `CFamilyTree` object remains six-child by construction: the child
  count is at `+0x1B4`, the child array begins at `+0x1B8`, each child record is
  `0xD8` bytes, and six records terminate exactly at the `0x6C8` generation
  record boundary.
- Native `AddOffspring`, `EmptyOffspringSlots`,
  `UpdateCurrentFamilyRecord`, `SaveState`, `Reset`, and `MakeRoomInTree` are
  now checked for their stock six-child, `0xD8`, `0x6C8`, `0xCB70`, and
  `0xCB74` boundary bytes before a build can publish a manifest.
- The persistent Family Tree block remains `0xCB74` bytes from `theGameData`
  `+0x1840` to the next component at `+0xE3B4`; no unused serialized tail is
  claimed. The adoption scene's two six-dword candidate arrays remain
  documented at `this+0x20` and `this+0x38`, with count at `this+0x50`.
- The validator records `fail_closed_static_audit` and keeps the capacity
  toggle disabled. It does not implement twelve-child persistence; that still
  requires a versioned sidecar plus matched Family Tree, rollover, draw,
  hit-test, candidate-array, adoption, and save/reload routes.

## 2026-08-06 - Exhaustive mobile furniture route partition

- The genuine mobile furniture scope is exactly 63 rows, IDs `0x2AA-0x2E8`.
  The patcher now requires that evidence to be ordered, complete, and unique
  before it can classify any route.
- Existing validated PC-safe behavior-map evidence covers 34 rows: Chaise
  `0x2DE-0x2E1`, Patio/Picnic/Umbrella, Birthday Cake/ Presents/ Balloons/
  Banner, and the validated Holiday groups. The five exact decorative-only
  rows are Candy Cane `0x2AB`, Christmas Cookie `0x2AC`, Poinsettia `0x2BF`,
  and Wreaths `0x2D4-0x2D5`.
- The remaining 24 rows are explicitly classified
  `rendered_only_unproven`; preserved source QAMFs do not advertise a desktop
  behavior route. The validator rejects missing, duplicate, overlapping, or
  unsupported route advertisements and records all 63 dispositions in
  `MobileFurnitureRouteClassification`.
- This is a static evidence partition only. It does not grant runtime
  behavior to the 24 unresolved rows and does not replace player QA.

## 2026-08-06 - Mobile furniture generated-binding audit

- The 34 classified behavior rows are now cross-checked against generated
  source, not only family metadata. The validator parses the manual
  `theMainScene` dispatcher and requires exactly the supported ID set and
  exactly one handler binding per family.
- The dispatcher must call stock `HandleDropOnHotSpot` first, retain false
  fallthrough, and stop at the default-zero `.vf2beh` gate. Both proven source
  forms are accepted: the normal direct return and the Behavior-Patches
  `handled` branch; no third form is accepted.
- Autonomous validation covers the four chaise stock-candidate rows, the eight
  Holiday external candidates, and the four Patio/Picnic candidates. Their
  twelve mobile IDs, objects, weights, selectors, and stock-table preservation
  are checked. Christmas Tree `AdmiringXmasTree` `0x19C`,
  `AdultWaterXMasTree` `0x19E`, and `KidBreakingTreeDecor` `0x19F` are included;
  `FixingTreeDecorations` `0x19D` remains excluded because its activation
  record is not present. Decorative-only and rendered-only/unproven IDs are
  rejected if they enter the manual family or autonomous bindings.
- The normal gate and the Behavior-Patches shared autonomous hook both pass
  the real patcher entry point. This remains static/link validation; no game
  launch, save access, or player runtime confirmation was performed.

## 2026-08-06 - Gate B132 second-bathroom detours with Island Events

- Player runtime testing reported a crash when entering the house and when
  selecting the second-bathroom toilet-door area in the B157 mobile-renovation
  build. A renderer-off diagnostic also crashed at house entry, so B157's room
  image hook is not sufficient to explain the failure.
- The generated manifest exposed an unsafe feature boundary: `IslandEvents`
  was disabled, but `patch_second_bathroom_leaks()` still modified
  `CEventTheWaterPressureSurge::ImpactGame` and `CVillager::NewBehavior`.
  The native E6 purchase/load activation records are a separate route and must
  remain intact.
- `apply_second_bathroom_leaks()` now applies the B132 event and behavior
  detours only when Island Events is enabled. Island-Events-off builds record
  `disabled_with_island_events` and preserve native E6 activation. A new
  renderer-off, no-B132 diagnostic links with this manifest boundary; runtime
  confirmation and final root-cause attribution remain pending.

## The B179-to-B180 bundle delta, measured rather than inferred

The owner confirmed on 5 September that B180 crashes as well as B181, and
that B179 runs. B179 is therefore the newest known-good build, which makes
the B179-to-B180 delta the tightest available bracket on the regression.
Measured against the extracted bundles rather than the source tree:

- **WHAT THIS BRACKET DOES AND DOES NOT CONTROL FOR.** Each release ships 32
  executable variants with different feature sets, so "B179 runs and B180
  crashes" is a statement about two RELEASES, not yet a controlled comparison
  of two matched variants. The executable actually run is a deployed copy whose
  SHA-256 is `a87aa30555fe012c...`, and it matches NONE of the variants in the
  extracted B180 release payload, so this record cannot say which variant it
  is or what settings produced it. If the two runs used different settings, the
  observed transition includes variant differences as well as build
  differences.

  This does not weaken the two claims below that rest on reading the binaries
  themselves -- the absent behaviour registrations and the byte-identical retry
  loop are properties of the specific files disassembled, whatever variant they
  are. It does mean the ASSET delta above brackets two releases rather than two
  matched builds. Recording the installed executable's hash and the selected
  settings at the time of each run is what would close that gap, and it was not
  captured.

- **Three assets differ under `Assets/`.** `InvisibleLounger.png.fmap`,
  `InvisiblePatioTable.png.fmap` and `InvisiblePicnicTable.png.fmap`. Every
  other file in that directory is byte-identical, and neither bundle has a
  path the other lacks -- 645 files each, compared over the UNION of paths so
  a one-sided addition could not hide.

  THAT IS NOT THE WHOLE BUNDLE, and an earlier version of this entry said
  "exactly three shipped assets differ" without the qualifier, which is wrong
  and would steer a diagnosis away from most of what actually changed. The
  runtime `Images/` tree differs too: **100 files changed and one added**
  (`Furniture/SpaLoungerStd.png`), 6540 files against 6541. The changed set is
  the regenerated `HairstyleIcons/`. Those are loaded by the game and belong
  in the delta.

  So the bracket over the whole payload is 3 changed under `Assets/`, 100
  changed and 1 added under `Images/`. The three fmaps are where this entry
  looked first, not the only thing that moved.
- **The change in all three is the documented desktop-safe strip**: the mobile
  object-type field is removed from the high half of each cell, and the mobile
  behaviour-hotspot cells whose payload is `0x0001` are zeroed. Both halves are
  intended; the zeroing is the "unsafe behaviour cells stripped" described at
  `patch_mobile_furniture_pack.py:4172`.
- **The executable gained an `.rsrc` section** of 0x15EB0 bytes, moving
  `.reloc` from `0x786000` to `0x79C000`. Parsing the resource directory shows
  it holds only `ICON` and `GROUP_ICON`. These are the STOCK GAME icon
  resources, not the patcher's own branding: `offline_vf2_patcher.py` captures
  `RT_ICON` (3) and `RT_GROUP_ICON` (14) from the player's original executable
  and writes them into the patched one, while `patcher_icon.ico` is a separate
  GUI and shortcut asset that never enters this section. An earlier version of
  this entry called it "the patcher icon", which misidentifies where the bytes
  come from and would make this measurement impossible to reproduce.

### What this rules out

- **The five added behaviours are not the cause.** B180 contains zero of the
  five `SetMacro` registrations for ids `0x0B1`-`0x0B4` and `0x0B8`, and B180
  crashes. This previously rested on attributing crash records to binaries;
  it now rests on a build the owner has personally confirmed crashes.
- **The faulting loop is not new.** The byte sequence `47 83 3e 00 74 ed`
  occurs exactly once in each of B179, B180 and B181. The working build
  contains the same retry loop at the same place in the same function.

### Two claims withdrawn after checking

Both were wrong, and both looked convincing before the check:

- The shipped `Patio_table.png.fmap` does not carry the `9c18bec` seat-anchor
  correction, which read as a fix that never reached the artifact. It is not:
  the corrected map ships as `InvisiblePatioTable.png.fmap`, and the
  vanilla-named file in these two bundles carries the uncorrected bytes.

  Stated precisely, because "deliberately left untouched" is too strong as a
  general claim: `mobile_furniture_behavior_asset_patches()` copies the
  corrected `pc_fmaps/Patio_table.png.fmap` into
  `payload/MobileFurnitureBehaviorFmaps` and can target it back to
  `Assets/Patio_table.png.fmap` when the default-on `mobile_furniture_behaviors`
  setting is enabled, in which case an installed game carries the corrected map
  under BOTH names. In the B179 and B180 payloads examined here that folder
  contains no `Patio_table.png.fmap`, so the donor-named file is the
  uncorrected one -- but an investigator must check the installed file rather
  than assuming the restore payload is what runs.
- `Picnic_table`'s far seats keep a `0x0002` residual after the strip. That is
  explicitly allowed and named in
  `test_no_map_keeps_a_fragment_of_the_mobile_object_type`: the map carries
  `0x3ae` as well as `0x3ac`, and `0x3ae - 0x3ac` is `0x2`.

### One real gap in the checks, with the bytes currently correct

`test_every_kept_cell_keeps_its_payload_verbatim` guards its comparison with
`if pc:`, so it skips every cell the transform zeroed. A transform that
wrongly cleared a cell it should have kept would pass that check silently.
The current bytes are right, so this is a hole in the check rather than a
defect in the data.
