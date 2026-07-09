# Discoveries

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
  patches, `optional` (black) for visual/invisible/custom additions, and
  `experimental` (red) for Settings Evict, Island Events, Holiday Ornaments,
  and other not-yet-proven work. Tk `Text.count(..., "displaylines")` is used
  to auto-size description blocks so long setting descriptions are fully
  visible.
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
