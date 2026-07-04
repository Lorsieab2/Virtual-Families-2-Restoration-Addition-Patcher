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
  `B98-current-vf2-modded-build`, size `340,111,685`, SHA-256
  `9124980ec334de2baa9c6da76ea614f64c38bf24233c68f1a7978ecde3d04f4a`.
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
