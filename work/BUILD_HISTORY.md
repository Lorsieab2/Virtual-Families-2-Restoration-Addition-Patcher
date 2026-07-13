# Build History

## B53 - Base Villager Sheets Restore

- Rebuilt from the verified B52 release payload.
- Replaced `female_sit00.png`, `male_sit00.png`, `female_actions00.png`,
  `male_actions00.png`, `female_bodies00.png`, and `male_bodies00.png` with
  the supplied base-game sheets.
- No native object patches, furniture data, or behavior routes changed.

## B54 - Stock Villager Body Runtime Restore

- Restores the stock 0--49 body-row limit and stock rare-body range.
- Disables the experimental holiday body-row append, animator clamp expansion,
  and runtime separated-body export by default.
- Keeps the experimental helper functions in source for later investigation,
  but they are opt-in through `VF2_ENABLE_HOLIDAY_BODY_TYPES=1` and are not
  part of the normal build path.

## B55 - Additive Mobile Island Event Table

- Appends mobile-only event objects after the stock desktop event slots.
- Preserves slots `0x01` through `0x60` and expands the stock list consumers'
  exclusive upper bound for the appended entries.
- Uses a `CIslandEvent`-compatible object prefix and selects target villagers
  in `CanFire`, matching the stock event lifetime rather than selecting them
  while the global event table is constructed.

## B57 - Folder-Backed Holiday Body Renderer

- Stops using the B56 expanded villager body/action/sit spritesheets for holiday
  outfits.
- Registers each holiday body frame as its own one-cell graphics descriptor and
  writes runtime frames under `Images/VillagerBodies`.
- Redirects only the two native villager body draw calls through a folder-backed
  helper. Stock body values `0-49` fall back to the original draw path.
- Keeps the original villager spritesheets as fallback assets and leaves head
  rendering untouched.
- Build folders should be mirrored to both `C:\Users\Owner\Downloads` and
  `C:\Users\Owner\OneDrive\Desktop\LDW Desktop Games!! And Other Stuff\Virtual Families 2 Codex Test Builds`.
  Use `work/sync_build_outputs.py` after a successful build.

## B58 - VF3 TV Appliances And Playhouse

- Adds the VF3 Large Flat Screen TV, VF3 Small Flat Screen TV, and Father's
  Favorite TV as new General Appliances entries.
- Confirms General Appliances is the native `gAppliancesList`; category number
  5 by itself is not the store list authority.
- Gives each added VF3 TV its own sprite-sized fmap and its own base-TV-shaped
  animation sheets so the base desktop TV resources remain untouched.
- Enables the Playhouse spontaneous behavior candidate for all ages, including
  children.

## B59 - Crash Fix And Child-Only Playhouse

- Rebuilt from the B57 folder-backed holiday-body baseline, then reapplied the
  current additive furniture/events patch.
- Fixes the General Appliances count widening to patch only the native
  `GetCategoryItemCount` return for `gAppliancesList`. B58 used a broad pattern
  replacement, which could also widen another stock category that happened to
  return the same desktop count.
- Keeps the added VF3 TVs on their private furniture sprites, fmaps, and
  animation sheet names; base desktop TV assets are not overwritten.
- Changes the Playhouse spontaneous behavior hook to preserve the stock native
  age gates, so it is no longer enabled for all ages.

## B60 - Targeted Appliance Count Widening

- Fixes the remaining B59 startup-crash risk by making General Appliances count
  widening fully symbol-relative instead of partially pattern-based.
- Patches `CInventoryManager::GetCategoryItem` appliance offsets `0x73` and
  `0x95`, and keeps the `CInventoryManager::GetCategoryItemCount` return patch
  targeted at offset `0x37`.
- Prevents the VF3 TV appliance count increase from also widening `gPetList`,
  whose additive count is also `15` after Turtle/Hamster support.
- Keeps the previous Accessories expansion approach intact for distinctive
  category counts.

## B61 - Save-Load Mouse Hook Fix

- Removes the injected `_VF2PatchedDebuggerMouseMove` early-return hook from
  `theMainScene::HandleMouseMove`.
- Maps the B58/B59/B60 save-load crash offset `0x0009ff8b` to that injected
  mouse-move hook region, not to General Appliances count widening.
- Keeps the B60 targeted appliance-count widening and the VF3 TV data intact.

## B62 - F5-Gated Debugger Input

- Keeps normal gameplay on the stock input path by inserting fall-through
  debugger hooks instead of replacing `theMainScene::HandleKeyDown`.
- Debugger input is inert until F5 enables it for the session; normal mouse
  down/move/up and key-character events return false immediately and continue
  into the original handlers.
- Wraps `Debugger` and selected `IEditor` calls with guarded access so a
  debugger/editor fault disables debugger input and falls back to stock input
  instead of crashing the game.
- Removes the normal-startup debug log bootstrap. Debug logging begins only
  after F5 activates debugger input.

## B63 - Base Mouse And Save-Load Restore

- Disables debugger/editor hooks by default after B62 still crashed while
  opening the affected save.
- Leaves `theMainScene::HandleKeyDown`, `DrawScene`, `HandleKeyCharacter`,
  `HandleMouseDown`, `HandleMouseMove`, and `HandleMouseUp` stock in normal
  builds.
- Keeps `vf2_debug_features.cpp` as an empty helper object so existing compile
  and link response files keep working without introducing runtime behavior.
- Adds `VF2_ENABLE_DEBUGGER_FEATURES=1` as a dev-only opt-in for isolated
  debugger research. Even that opt-in path no longer patches main-scene mouse
  handlers.
- User testing confirmed B63 opens the affected save without the B61/B62
  debugger crash.

## B64 - VF3 TV Animation Strip Scaling

- Regenerates only the private VF3 TV animation strip graphics used by the
  added Large, Small, and Father's Favorite TV assets.
- Scales each donor TV frame into an explicit per-cell screen box:
  `Large/LargeEast=(4,5,65,60)`, `Small/SmallEast=(2,3,48,43)`, and
  `FathersFavorite/FathersFavoriteEast=(5,5,96,78)`.
- Leaves base TV strips (`TVAnimBig*.png`, `TVAnimSmall*.png`), villager
  behavior, furniture behavior, debugger/input hooks, and `theMainScene`
  unchanged.

## B65 - VF3 TV Private Floating Animations

- Wires the private VF3 TV animation strips into the runtime instead of leaving
  them as unreferenced assets.
- Appends private `CFloatingAnim::m_sAnim` entries `0x40-0x45`, image
  descriptors `0x4CD-0x4D2`, and extends `CFloatingAnim::LoadAssets` from
  `0x400` to `0x460` table bytes.
- Sets only the added VF3 TV `FurnitureInfo` records to the new private enums
  with zeroed x/y animation offsets; base TV animation enums and stock
  `TVAnimBig*.png`/`TVAnimSmall*.png` assets remain untouched.
- Verifies all non-identity, non-store, non-animation `FurnitureInfo` fields
  still match donor `0x1F3`, and the click-dispatch table aliases each added
  VF3 TV to the same base flat-screen TV donor.
- Keeps debugger features disabled and preserves the stock `theMainScene.obj`
  hash `BA93F6430B45AAB75EFAE17C982BD9AC52DF078AE6E798D7D4F92E5DEBF733FB`.

## B66 - Gendered Outfit Store Icons

- Fixes blank Clothing-store rows for added outfit entries by generating one
  91 x 91 preview icon per outfit row under `Images/OutfitIcons/`.
- Splits added outfit rows into female item IDs `0x400-0x435` and male item
  IDs `0x440-0x475`; total Clothing row count is now 114 including the six
  stock rows.
- Appends outfit icon image descriptors `0x4D3-0x53E` and routes only those
  high outfit item IDs through targeted `CInventoryManager::DrawItem` hooks.
- Leaves villager behavior, furniture behavior, TV behavior, debugger features,
  and stock `theMainScene.obj` unchanged.

## B67 - Visible Special Upgrade Icons

- Fixes blank visible Special Upgrade rows for Brokerage Account, Food Club,
  Health Plan, and Lucky Rock by routing item IDs `0x117-0x11A` through the
  shared added-item `CInventoryManager::DrawItem` helper.
- Keeps their existing standalone image descriptors `0x309-0x30C` and ensures
  the four icon PNG payloads are emitted into the additive output.
- Leaves Special Upgrade purchase/apply behavior, hidden-IAP dialog bypass,
  villager behavior, furniture behavior, debugger features, and stock
  `theMainScene.obj` unchanged.

## B68 - Holiday Outfit Runtime Frame Restore

- Fixes the B66/B67 regression where Holiday outfit store icons could render
  while `holiday_body_runtime_frames.frames` stayed at `0`, leaving runtime
  body-frame descriptors without offsets.
- `sync_holiday_body_runtime_frames()` now searches complete image roots:
  current output, prior completed `VF2-Mobile-Furniture-With-Island-Events-B*`
  folders, then the B56 expanded Holiday body fallback.
- Regenerates all 448 folder-backed Holiday body frames for female/male body
  values `50-53` across `bodies`, `actions`, and `sit`, with all 448 graphics
  descriptors carrying non-null offsets.
- Adds a defensive `vf2_villager_body_frames.cpp` fallback clamp: recognized
  Holiday body grids draw stock row `49` if an individual frame image is
  unavailable instead of passing row `50-53` to the vanilla sheet renderer.
- Keeps the native `CAnimManager` body lookup unpatched, debugger features
  disabled, and villager/furniture behavior routes unchanged.

## B69 - Outfit Purchase And Action Icons

- Changes all generated Clothing-row preview icons to use the matching row's
  last action-sheet frame: `female_actions00.png` / `male_actions00.png`
  column `14`.
- Uses stock action sheets for body values `0-49` and the expanded B56 action
  sheets for Holiday body values `50-53` when the current output has only
  stock rows.
- Adds generated-outfit purchase handling at
  `CScrollingStoreScene::HandlePurchaseItem + 0x1AD`: recognized synthetic
  store IDs set `InventoryManager+0x468` or `+0x46C`, add stock tray item
  `0x49` or `0x4A`, save, and skip the native high-ID no-op path.
- Hooks `CInventoryManager::GetNumAvailable` and `GetUseCount` for the
  generated outfit IDs so the store click path treats them as valid one-use
  outfit rows.

## B70 - VF3 TV Animation Orientation

- Swaps the private VF3 TV animation source orientation: non-East added TV
  labels now use `TVAnimBigE*` frames, and East labels use `TVAnimBig*` frames.
- Retunes the private animation screen boxes to the full slanted face bounds:
  `Large/LargeEast=(4,5,65,80)`, `Small/SmallEast=(2,2,48,60)`, and
  `FathersFavorite/FathersFavoriteEast=(5,8,96,104)`.
- Leaves base `TVAnimBig*.png` / `TVAnimSmall*.png`, furniture behavior,
  villager behavior, and click behavior untouched; only the private VF3
  animation strips are regenerated.

## B71 - Clothing Category Crash Guard

- Removes the B69 generated-outfit `CInventoryManager::GetUseCount` hook.
- Changes `_VF2GetOutfitStoreNumAvailable` into a side-effect-free synthetic
  ID guard: generated outfit rows return available, stock rows fall through to
  native code, and the helper no longer calls `CToolTray::IsSlotAvailable`
  while the Clothing category is opening/drawing.
- Keeps the direct generated-outfit purchase hook that sets
  `InventoryManager+0x468/+0x46C`, adds tray item `0x49/0x4A`, and saves only
  after a generated outfit row is actually purchased.

## B72 - Settings Evict Button

- Calls the existing `patch_options_dialog()` step during the additive patch
  pipeline.
- Enables the dormant Settings Evict control ID `4` by NOPing the two
  `theOptionsDialog` constructor branches that skip Evict button creation for
  normal in-progress families.
- Reuses the existing `theOptionsDialog::EvictFamily()` to
  `CFamilyTree::EvictFamily()` path instead of adding new family-state clearing
  code.

## B73 - Clothing Getter ECX Guard

- Fixes the likely remaining Clothing category crash in the generated-outfit
  getter hooks.
- Preserves `ECX` across member-function outfit helper calls so stock Clothing
  rows can safely fall through to native `CInventoryManager` code with the
  original `this` pointer intact.
- Leaves the generated Clothing rows, outfit icon graphics, direct outfit
  purchase helper, Evict button, TV behavior, furniture behavior, and villager
  behavior unchanged.

## B74 - Any-Generation Settings Evict

- Changes the Settings Evict constructor gate from "generation count < 2" to
  "generation count > 0", so the button is available for every active family
  generation.
- Keeps the existing confirmation and
  `theOptionsDialog::EvictFamily()` -> `CFamilyTree::EvictFamily()` click path.
  `CFamilyTree::EvictFamily()` is generation-agnostic: it resets the family
  tree and marks it evicted, while the Options handler resets villagers and
  routes to the adoption scene.
- Leaves Clothing, furniture, villager, debugger, TV, and store-category
  behavior unchanged.

## B75 - Independent Outfit Tray Items

- Copies the six supplied stock villager sheets into the completed build's
  `Images` folder before outfit icon and frame export generation:
  `female/male_bodies00.png`, `female/male_actions00.png`, and
  `female/male_sit00.png`.
- Exports build-local separated outfit frames under
  `Images/VillagerBodies/<Gender>/Body_##/{bodies,actions,sit}/Frame##.png`
  while keeping runtime stock body rows on the normal sheet renderer.
- Fixes generated outfit purchases so `ToolTray` stores the independent
  synthetic outfit item ID (`0x400-0x435` female, `0x440-0x475` male) instead
  of reusing one stock outfit item per gender and mutating the shared
  `InventoryManager` outfit body field.
- Patches `CToolTray::GetToolInHand()` and `CToolTray::GetToolInUse()` to
  normalize a selected synthetic outfit to stock `0x4A` female or `0x49` male
  only for vanilla main-scene application checks. `GetOutfit()` then decodes
  the body value from the selected synthetic item.
- Leaves stock outfit items, furniture behavior, villager behavior, debugger,
  TV behavior, and base save/load paths otherwise unchanged.

## B76 - Holiday Ornaments Collection

- Adds the mobile Holiday Ornaments collectible range `0x9E-0xA9` as a sixth
  Collections page with generated build-local art from `tp225.pvr`.
- Registers base ornament carrying value `0x9E` through the stock full-yard
  collectible spawn system, so normal spawn cadence and Lucky Rock odds remain
  owned by the existing `CCollectableItem::Update/Add` path.
- Adds the `Ornamentologist` Goals entry at achievement row `0x5F`, target
  `12`, and bumps the Goal Collector target to include the new collection goal.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B76-Holiday-Ornaments-Collection`.

## B77 - Child-Only Playhouse Spontaneous

- Fixes the Playhouse spontaneous candidate so adults no longer select
  `PlayOnPlayStructure` autonomously.
- Sets candidate `0x11E` max age to `0x117`, matching the stock child/adult
  boundary (`CVillager+0x6A54 < 0x118`).
- Leaves furniture drop/click behavior, villager behavior functions, debugger,
  TV behavior, Clothing, and Holiday Ornaments unchanged.

## B78 - VF3 TV Frame Enum Orientation

- Swaps the added VF3 TV `FurnitureInfo` frame `0`/frame `1` private
  floating-animation enum assignments so the overlay slant follows the
  generated furniture frame orientation.
- Leaves the generated private animation strips, base TV assets, click
  behavior, furniture behavior, villager behavior, debugger, Clothing, Holiday
  Ornaments, and Playhouse changes otherwise unchanged.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B78-TV-Frame-Enum-Orientation`.

## B79 - Complete Runtime Package

- Copies the required desktop runtime DLLs into the completed build root:
  `SDL2.dll`, `SDL2_image.dll`, `libpng16-16.dll`, `libjpeg-9.dll`,
  `zlib1.dll`, and `fmod.dll`.
- Records the copied DLLs in `patch-manifest.json` under
  `desktop_runtime_dlls` and fails the patcher run if any required DLL is
  missing from the known runtime source folders.
- Leaves gameplay, furniture data, VF3 TV orientation, Playhouse, Clothing,
  Holiday Ornaments, and executable code behavior otherwise unchanged from
  B78.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B79-Complete-Runtime-Package`.

## B80 - Holiday Outfit Body Values

- Re-enables the native `CAnimManager` body-link lookup widening for Holiday
  outfit rows `50-53`.
- Keeps invalid body values on a stock-safe fallback: link lookups still fall
  back to row `49`, and the folder-backed draw helper clamps unsupported rows
  before calling the vanilla `DrawScaled` path.
- Adds regression tests proving generated Holiday outfit IDs decode to body
  values `50-53` for both female and male rows.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B80-Holiday-Outfit-Body-Values`.

## B81 - VF3 TV Behavior Fmaps

- Patches the separate `CFurnitureManager::LoadFmap` furniture-offset guard
  from stock max `0xFB` to the additive furniture max so appended VF3 TV item
  IDs `0x324-0x326` can load their content maps.
- Ensures empty output folders still receive `Assets/` fmaps by seeding donor
  fmaps from `work/vf2_obb/assets`, then regenerates the three VF3 TV fmaps
  from their sprite footprints while preserving stock TV object-cell payloads.
- Adds `validate_vf3_tv_behavior_contract()` so future builds fail if the new
  TVs lose the LoadFmap patch, donor behavior contract, or generated fmaps.
- Keeps villager behavior, base TV behavior, base TV sprites, and base TV
  animation assets untouched.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B81-VF3-TV-Behavior-Fmaps`.

## B82 - VC90 Runtime Package

- Fixes the B79-B81 launch regression caused by packaging `SDL2_image.dll`
  without its VC90 side-by-side CRT dependency.
- Adds `sync_vc90_crt_private_assembly()` to copy the local x86 VC90 CRT files
  into `Microsoft.VC90.CRT/` and write `Microsoft.VC90.CRT.manifest` matching
  the `SDL2_image.dll` embedded dependency on version `9.0.21022.8`.
- Keeps the B81 VF3 TV behavior/fmap fix intact and does not change gameplay,
  furniture behavior, villager behavior, or TV behavior code.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B82-VC90-Runtime-Package`.

## B83 - Full Runtime Payload

- Fixes the B79-B82 launch regression where release folders contained the SDL
  DLLs but only a partial generated `Images/` tree. Probes showed the B82 EXE
  stayed running with the complete vanilla image payload and exited with code
  `3` with the partial B82 image payload.
- Adds `sync_vanilla_runtime_payload()` to seed every output with the official
  vanilla `Images/`, `Sounds/`, `ldw.ini`, `wc.dat`, and `icon.bmp` before
  overlaying additive art.
- Adds `validate_runtime_payload_contract()` and offline patcher
  `runtime_requirements` support so future builds and patch bundles can reject
  incomplete runtime folders before release or patching.
- Keeps gameplay, furniture behavior, villager behavior, and TV behavior code
  unchanged from B82.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B83-Full-Runtime-Payload`.

## B84 - Disable Unstable Holiday Ornaments Collection

- Disables the experimental Holiday Ornaments collection/page/achievement
  native hooks in normal builds behind `VF2_ENABLE_HOLIDAY_ORNAMENTS=1`.
- Keeps stock Collections behavior active so the UI should remain on the base
  four pages and `48` total collectibles instead of crashing while reporting
  `60`.
- Leaves the research code and generated-art path available for isolated
  Holiday Ornament work, but marks the offline patcher setting experimental and
  default-off.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B84-Disable-Holiday-Ornaments`.

## B85 - VF3 TV Animation Inset

- Refines only the private VF3 TV animation strip screen boxes to reduce minor
  bezel bleed seen in B84 screenshots.
- New boxes: Large `5,6,63,77`, Small `3,3,46,57`, and Father's Favorite
  `8,10,90,96`; East and West variants keep matching box dimensions.
- Leaves base TV assets, VF3 furniture behavior, click handling, fmaps,
  villager behavior, and floating-animation enum order unchanged.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B85-TV-Animation-Inset`.

## B86 - Holiday Ornament Pickup Recognition

- Ornament-enabled research build. Keeps the B84 default source guard
  (`VF2_ENABLE_HOLIDAY_ORNAMENTS=1` required), but generates this build with
  that flag enabled so Holiday Ornament pickup can be tested in-game.
- Adds `0x9E` family-range recognition to
  `CCollectableItem::Find(CVillager&, ECarrying, ldwPoint&)`, matching spawned
  variants `0x9E-0xA9` when villagers search for the base ornament request.
- Adds the same family recognition to
  `CCollectableItem::WasItemSpawned(ECarrying)` so the spawn gate sees an
  already-active ornament variant and does not repeatedly spawn new ornaments.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B86-Holiday-Ornament-Pickup-Fix`.

## B87 - Holiday Ornament Collection Art

- Ornament-enabled research build using the supplied
  `C:\Users\Owner\Downloads\Holiday Collectibles` collection-screen art and
  `C:\Users\Owner\Downloads\collectables_small.png`.
- Bakes the supplied `*-Placeholder.png` ornament silhouettes into the
  `Collection_ChristmasOrnament_Frame.png` background so uncollected slots show
  the expected placeholders without changing `CCollectionScene::DrawScene()`.
- Copies the 12 collected ornament images into `Images/CollectionOrnaments/`
  and preserves `Collection_ChristmasOrnament_CandyCane.png` as decorative
  source art, not a 13th collectible.
- Replaces the build-local `Images/collectables_small.png` with the supplied
  sheet so the small collection icon atlas includes the Holiday Ornament row.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B87-Holiday-Ornament-Collection-Art`.

## B88 - VF3 TV Animation Box Revert

- Reverts the B85 private VF3 TV animation inset boxes after in-game testing
  showed worse overlay alignment.
- Restores the B84 private strip geometry: Large `4,5,65,80`, Small
  `2,2,48,60`, and Father's Favorite `5,8,96,104`; East and West variants
  keep matching dimensions.
- Leaves VF3 TV fmaps, furniture behavior, villager behavior, base TV assets,
  Holiday Ornament research hooks, and runtime packaging unchanged from B87.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B88-TV-Animation-Box-Revert`.

## B89 - Holiday Body Link Fallback

- Fixes the broken Holiday body/head alignment caused by widening native
  `CAnimManager` link lookups to rows `50-53` while normal builds still ship
  50-row stock villager sheets.
- Keeps the folder-backed Holiday body renderer active for visual body frames,
  but preserves the stock row-49 link fallback for head/body attachment points.
- Adds a regression test and manifest policy entry proving Holiday body values
  `50-53` draw through folder-backed art while link geometry remains stock-safe.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B89-Holiday-Body-Link-Fallback`.

## B90 - Stock Collections Runtime Assets

- Restores normal build generation to the stock Collections path by leaving the
  experimental Holiday Ornament collection native hook disabled unless
  `VF2_ENABLE_HOLIDAY_ORNAMENTS=1` is explicitly set for research builds.
- Seeds and validates the full runtime `Assets/` payload from the workspace
  asset cache before overlaying additive `.fmap` files. Required sentinels now
  include `cmap.dat`, `wpts.dat`, `animpts.dat`, `anims.dat`, `lsmap.dat`, and
  `TVFlatScreenStd.png.fmap`.
- Tightens direct-build and offline-patcher runtime checks so folders missing
  map/path geometry assets fail before release or patch application.
- Does not alter villager behavior, furniture behavior, or stock collection
  screen code.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B90-Stock-Collections-Runtime-Assets`.

## B91 - Revert Full Assets Payload

- Reverts the B90 full runtime `Assets/` payload seeding and validation after
  in-game testing showed the copied asset payload broke the modded runtime.
- Removes the build path that copied map/path geometry files such as
  `cmap.dat`, `wpts.dat`, `animpts.dat`, `anims.dat`, and `lsmap.dat` into the
  release folder.
- Keeps the stock Collections default from B84/B90: Holiday Ornaments native
  collection hooks remain disabled unless `VF2_ENABLE_HOLIDAY_ORNAMENTS=1` is
  explicitly set for isolated research.
- Removes the old hidden fallback to a `Copy Official` furniture sprite folder;
  normal builds must use build-local/runtime-local art or explicit workspace
  inputs.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B91-Revert-Full-Assets-Payload`.

## B92 - Holiday Ornaments Collectible Array

- Enables Holiday Ornaments by default after verifying the mobile 1.7.16 native
  collection table shape: stock PC has five pages/60 entries, while mobile adds
  page `5` and appends carrying values `0x9E-0xA9` for 72 total entries.
- Keeps the B86 `CCollectableItem` family-range patches for spawn recognition,
  pickup search, `WasItemSpawned`, `CollectionCount`, and first-copy
  achievement progress.
- Adds `CCollectable` constructor observer registrations for `0x9E-0xA9` so
  villager carry/drop dispatch reaches `CCollectableItem` and ornaments can be
  removed and counted after pickup.
- Adds regression tests for the patched 72-entry `gCollectable` table and the
  new ornament observer registrations.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B92-Holiday-Ornaments-Collectable-Array`.

## Next Build Contract - Additive Native Arrays

- Enables the additive mobile Island event table by default in the patcher.
- Records the native arrays that additive builds are allowed to grow:
  furniture records/lookups, inventory category lists, graphics descriptors,
  string rows, Island event slots, furniture click dispatch, and villager
  behavior candidates.
- Documents the rule that new furniture, events, strings, graphics, and behavior
  routes are appended with widened bounds, while base desktop entries remain
  untouched.
- Adds a source audit helper showing the current patcher coverage:
  110 additive furniture/store records, Turtle and Hamster pet additions,
  mobile Island events enabled by default, and holiday body values `50-53`
  remaining opt-in until the folder-backed renderer is stable.

## Next Build Contract - Previous Build Baseline

- New B-build folders must seed from the most recent previous completed
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B*` build before applying
  clean base assets and regenerated additive changes.
- `work/patch_mobile_furniture_pack.py` chooses the highest lower B-number when
  `VF2_PATCH_OUT` names a B-build, or the highest available B-build otherwise.
  `VF2_PREVIOUS_BUILD_DIR` can override the source for explicit rebuilds.
- This preserves runtime packaging fixes and carried-forward additive assets
  while still refreshing base-game `Images` and `Sounds` from the clean
  workspace payload.
- As of the standalone B98-current release, future package roots must preserve
  the B98 ZIP shape exactly: top-level `Assets/`, `Images/`,
  `OptionalVisualMods/`, `Original Virtual Families 2 Assets/`, `Sounds/`, the
  required root launcher/config/DLL files, and no legacy `ReferenceAssets/` or
  `Microsoft.VC90.CRT/` folders. The current release baseline asset is
  `Current VF2 Modded Build! B98.zip` on tag
  `B98-current-vf2-modded-build`, size `353,946,169`, SHA-256
  `63ad60cfb963008bed7cc6706f05146ed7ed6a8f40aa785204c9ccefa36dbf55`.

## Next Build Contract - Offline Patch Bundle Export

- `work/export_offline_patch_bundle.py` exports generated build folders into
  `offline_vf2_patcher.py` manifest/payload bundles with toggleable settings,
  runtime requirements, asset SHA-256 records, and optional vanilla-vs-patched
  EXE byte diffs.
- The B93 asset preview is now pruned by default with `--asset-mode additive`,
  producing 713 manifest-referenced asset records instead of exporting inherited
  previous-build payloads. It still needs vanilla EXE target metadata and
  native byte records before publication.
- The workspace-local vanilla EXE candidate
  `Unneeded crap\Virtual Families 2.exe` exports target metadata successfully
  (SHA-256 `67e8cf073be89b9699f4f7a19bc1105ceae865cdaefe98abd0c1e59e5f0d6bc4`,
  size `1,881,088`), but B93's patched EXE size is `1,677,824`, so native
  records must be derived from linker/object patch metadata rather than a full
  executable byte diff.
- Object-relative native byte triples from build manifests are preserved under
  `native_patch_sources` only. B93 currently exports the three Settings Evict
  constructor records this way; they must be translated to final vanilla EXE
  file offsets before the offline patcher is allowed to apply them.

## B94 - Stability, Outfit Apply, Ornament Opt-In

- Seeds from the current standalone B98 release package folder and preserves its
  top-level package shape.
- Disables Holiday Ornament native collection/spawn/pickup hooks in normal
  builds; `VF2_ENABLE_HOLIDAY_ORNAMENTS=1` remains the isolated research opt-in
  for mobile parity work.
- Disables the mobile Island Event table graft in normal builds;
  `VF2_ENABLE_ISLAND_EVENTS=1` remains research-only until outcomes are mapped
  and crash-free.
- Fixes Holiday outfit placement by keeping a gendered last-synthetic-outfit
  fallback while stock tray normalization maps generated outfit items to stock
  `0x49/0x4A`, so body values `50-53` can survive the apply path instead of
  falling back to body `49`.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B94-Stability-Outfit-Ornament-OptIn`.

## B95 - Holiday Outfit Apply Field Sync

- Seeds from B94 and keeps Holiday Ornaments plus mobile Island Events disabled
  by default for stability.
- Updates the stock `CInventoryManager` male/female outfit body fields whenever
  a generated outfit item is purchased or selected through the tray
  normalization helper. This gives the vanilla apply path body values `50-53`
  for Holiday outfit rows even after the synthetic tray ID is normalized to
  stock item `0x49/0x4A`.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B95-Holiday-Outfit-Apply-Field-Sync`.

## B96 - Holiday Outfit Apply Resolver

- Keeps the B95 purchase/tray fixes but patches the final
  `theMainScene::HandleMouseDown` drop-on-villager apply callsites for stock
  outfit items `0x49` and `0x4A`.
- Redirects those two callsites to `_VF2ResolveOutfitBodyForApply`, which reads
  the selected synthetic outfit from `ToolTray` before falling back to the
  gendered last-synthetic value or vanilla `InventoryManager` body fields.
- Targets the actual villager body write at `CVillager+0x6A84`, fixing the
  failure mode where Holiday outfit items display correctly in the tool tray
  but still apply body `49`.
- Adds the matching live house-view draw redirect at
  `CVillagerManager::DrawVillager + 0x454`, so body values `50-53` render
  through the folder-backed Holiday frame table instead of crashing
  `CSceneManager::DrawScaled` with an out-of-range stock sheet row.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B96-Holiday-Outfit-Apply-Resolver`.

## B97 - Outfit Apply Stability

- Keeps the B96 live house-view Holiday body renderer redirect, but disables
  the direct `theMainScene::HandleMouseDown` stock outfit callsite replacement
  after in-game testing showed generated Outfit-section items could crash on
  drop/apply.
- Moves selected generated outfit body recovery back into the existing
  `CInventoryManager::GetOutfit` hook path. `_VF2GetOutfitStoreBodyValue` now
  reads the current synthetic ToolTray item before falling back to the
  gendered last-synthetic cache or vanilla outfit fields.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B97-Outfit-Apply-Stability`.

## B98 - Male Outfit Strings

- Fixes the `theStringManager` lookup/guard bound used for generated strings.
  The previous row-count based bound stopped at StringId `0xC25`, which made
  male generated Outfit body `04` and later display `Unknown String Id!!!!`.
- Computes the string lookup one-past value from the highest actual generated
  StringId. Normal B98 generation reports `new_one_past_max = 0xC8B`, covering
  all generated Outfit rows plus the added behavior labels.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B98-Male-Outfit-Strings`.

## B99 - Evict and Invisible Hammock Parity

- Keeps the stock/mobile Settings Evict handler path intact and preserves the
  `theOptionsDialog` constructor state guard at `+0x2DA`, while relaxing only
  the generation threshold so the button is available in every active family
  generation.
- Treats Invisible Hammock item `0x30C` as a base HammockStd donor clone for
  behavior fields. The generated furniture row must match donor `0x1E1` for
  every non-identity/store/string field.
- Wires `CHotSpot::Hammock` through `_VF2EitherHammockInWorld`, allowing the
  stock hammock hotspot/drop predicate to accept either base `0x1E1` or
  Invisible Hammock `0x30C` before continuing through the native
  `eBehavior_LieInHammockNoLeadIn (0x24)` action.
- Adds `vf2_invisible_hammock.cpp` to the helper compile and link response
  files and validates `InvisibleHammock.png.fmap` is copied from
  `HammockStd.png.fmap`.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B99-Evict-Hammock-Parity`.

## B99 Offline Patcher - Full-Payload Smoke Bundle

- Adds direct `--exe` input to `work/offline_vf2_patcher.py`, allowing the
  patcher to infer the game folder from `Virtual Families 2.exe`, validate the
  vanilla EXE by exact SHA-256 or by PE32 section structure, create a backup
  under `.vf2_patch_backups`, and write the patched EXE back to the same path.
- Extends `work/export_offline_patch_bundle.py` with `--asset-mode full`,
  `--include-exe-replacement`, and `--include-patcher-scripts`.
- Exports a B99 full-payload patcher bundle to
  `outputs/VF2-B99-Offline-Patcher-Full` and copies it to
  `C:\Users\Owner\Downloads\VF2-B99-Offline-Patcher` for testing.
- Smoke-tested from an EXE-only folder:
  `Virtual Families 2.exe` vanilla SHA-256
  `67e8cf073be89b9699f4f7a19bc1105ceae865cdaefe98abd0c1e59e5f0d6bc4` became
  B99 SHA-256
  `9a713d38e830dcfb2fe1f4f054c36f1340d772c9e28c2abb96501137ee164ea1`, with the
  B99 runtime folder structure recreated beside it.
- Re-exported the B99 full-payload patcher bundle against the user-provided
  vanilla EXE at `C:\Users\Owner\Downloads\Virtual Families 2\Virtual Families
  2.exe`: size `1,511,424`, SHA-256
  `1582d9e84e1c32f51475be17335c5137c592cebf809748d401ccef99a32b73c3`, five
  PE sections. A structure smoke test appended overlay bytes to the copied EXE,
  changed its whole-file SHA, and still patched successfully with
  `matched_by=pe_structure`.

## B101 - Invisible Hammock Fireplace-Style Alias

- Supersedes the B99/B100 `CHotSpot::Hammock` detour attempt. `HotSpot.obj`
  now remains byte-identical to the stock desktop object for the hammock path.
- Keeps Invisible Hammock item `0x30C` as a donor clone of base HammockStd
  `0x1E1`: `CFurnitureManager::itemInfo` behavior fields match the donor,
  `HandleMouseDown` uses the donor lookup-table case, and
  `InvisibleHammock.png.fmap` is copied from `HammockStd.png.fmap`.
- Adds a regression test proving `patch_invisible_hammock_drop_action()` writes
  only the compile-response stub and does not modify `HotSpot.obj`.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B101-Invisible-Hammock-Fireplace-Style`.

## B102 - Invisible Hammock Drop Parity

- Restores the missing native drop gate for Invisible Hammock. B101 preserved
  donor item fields, donor click alias, and `HammockStd.png.fmap`, but
  `CHotSpot::Hammock` still rejected worlds without base item `0x1E1`.
- Patches `CHotSpot::Hammock` safely by NOPing only the hardcoded
  `push 0x1E1`, preserving the relocated `mov ecx, FurnitureManager`, and
  retargeting the existing call to `_VF2EitherHammockInWorld`.
- `_VF2EitherHammockInWorld` checks `IsInWorld(0x1E1)` or `IsInWorld(0x30C)`,
  then the stock function continues through
  `eBehavior_LieInHammockNoLeadIn (0x24)`.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B102-Invisible-Hammock-Drop-Parity`.

## B103 - Invisible Heart-Shaped Bed and Patcher Refresh

- Adds `InvisibleHeartShapedBed` as a new item `0x327` in `gFurniture4`,
  donor-cloned from the base Heart-Shaped Bed `0x252`. The existing
  `InvisibleAdultDoubleBed` remains unchanged as item `0x314` with Brown Adult
  Bed donor `0x1B7`.
- Copies `InvisibleHeartShapedBed.png.fmap` from `HeartShapedBed.png.fmap` and
  generates the usual base/transparent sprite pair from `HeartShapedBed.png`.
- Builds to
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B103-Invisible-Heart-Bed`.
  Linked EXE SHA-256:
  `66343cac83b0f835fa6decb7c9abeb8249c04be269d85e85e989e16a528957eb`.
- Refreshes the full-payload offline patcher bundle at
  `outputs/VF2-B103-Offline-Patcher-Full` with B103-labeled runner files and
  the B103 EXE payload. Smoke apply from a copied vanilla EXE produced the B103
  hash and recreated `Assets/`, `Images/`, `OptionalVisualMods/`,
  `Original Virtual Families 2 Assets/`, and `Sounds/`.
- Adds a separate manifest-declared modded output folder
  (`VF2-B103-Modded`) and writes the patched EXE as
  `Virtual Families 2 - Modded B103.exe` instead of replacing the user-selected
  vanilla EXE in place.
- Adds per-record patcher progress/process-log entries, a GUI completion popup,
  `Transparency Log.txt`, and an optional generated patcher launcher that
  auto-loads the adjacent `manifest.json`.
- Splits optional visual and Invisible Furniture support files behind
  default-off settings so unchecked options are omitted from fresh modded output
  folders. Native/game-code toggles still need future per-feature byte/table
  records before they can revert independently of the full EXE payload.

## B103 Restoration/Addition Patcher ZIP Refresh

- Renames the patcher UI to `Virtual Families 2 Restoration/Addition Patcher`
  and the generated Windows launcher to
  `Virtual Families 2 Restoration-Addition Patcher.exe`.
- Adds a Codex AI creation disclosure to generated README, manifest metadata,
  and `Transparency Log.txt`.
- Adds a pre-write official-install validation gate requiring the exact LDW
  website top-level entries: `Assets`, `Images`, `Sounds`, `Virtual Families
  2.exe`, root DLLs, `Readme.txt`, `ldw.ini`, `icon.bmp`, `uninst.exe`, and
  `Virtual Families 2.url`.
- Updates the GUI with auto-populated paths, green bold Apply Patches text,
  `**bold**` description rendering, `Dry Run (Validate Only)` wording,
  clickable blue path labels, and a completion popup where only the
  modified-file log scrolls.
- Groups patch settings as green Main Patches, black Optional Patches, and red
  Experimental/Not Working Patches; setting descriptions now auto-size so the
  full description remains visible in the scrollable settings panel.
- Adds `patcher_icon.png` and `patcher_icon.ico` to the bundle. The GUI shows
  the literal family picture beside the bold title, and the generated Windows
  launcher embeds the ICO when a local C# compiler is available.
- The generated launcher still auto-loads adjacent `manifest.json`, but the GUI
  no longer opens the vanilla-folder picker automatically. The user selects the
  vanilla VF2 installation manually, and no hardcoded install path is used.
- Adds buttons to enable all Main Patches, all Optional Content, or all
  Experimental Patches without changing unrelated categories.
- Adds the default-off `Add Custom Couches and LDW Posters` setting for
  Colorful Couches and LDW Poster/Painting image/fmap payloads. Native
  store-row gating for that feature still needs future per-feature byte/table
  records because current full bundles use a verified full modded EXE payload.
- Ships the patcher as a ZIP bundle for testing instead of a loose folder only.

## B104 - Restoration/Addition Patcher BAT Refresh

- Increments the patcher release to B104 and removes the compiled patcher
  launcher EXE from generated bundles. B104 ships `Launch_GUI.bat` plus an
  optional `Launch GUI.lnk` shortcut that uses `patcher_icon.ico` when Windows
  shortcut creation succeeds.
- Adds the default-on `Add unused pets` setting for the existing Turtle/Hamster
  pet-store native metadata (`gPet` / `pet_store_additions`).
- Adds the default-off `Add optional song mods` setting. Optional songs stay in
  `payload/OptionalSongMods` and write to runtime `Sounds/*.ogg` only when the
  setting is enabled.
- Adds default-off loose `OptionalVisualMods` image support. Loose furniture
  images target `Images/Furniture`; future Workshop/Kitchen/Office upgrade
  images target `Images/Upgrades`; other loose images target `Images`.
- Makes recognized `VF2-*-Modded` output folders refresh from the vanilla
  install before checked patch records are applied. Unchecking a patch and
  clicking Enable/Disable Patches now removes that patch from the regenerated
  modded folder.
- Keeps `OptionalVisualMods`, `Original Virtual Families 2 Assets`, and
  `OptionalSongMods` as read-only/copy-only payload source folders during
  apply; they are not copied wholesale into the playable game folder.

## B105 - Restoration/Addition Patcher Launcher and Byte Patch Refresh

- Removes generated `Launch GUI.lnk` from patcher ZIPs because Windows
  shortcuts are path-specific and can break after extraction. `Launch_GUI.bat`
  is the supported GUI launcher and stale shortcut/status files are cleared on
  forced exports.
- Adds manifest `output.default_exe_name` and patcher-side output enforcement
  so byte-patched builds are renamed from `Virtual Families 2.exe` to
  `Virtual Families 2 - Modded B105.exe`, with the save folder derived from the
  same EXE stem.
- B105 release packaging should use `--include-byte-patches` and avoid
  `--include-exe-replacement` for normal releases. This keeps native/code/table
  features working while avoiding a ZIP that contains a ready-made modified game
  executable payload.

## B118 - Settings Evict Button Re-Enable

- Re-enables the dormant Settings Evict button by NOPing both stock
  `theOptionsDialog` constructor skip branches at `+0x2DA` and `+0x2E7`.
- Leaves the existing native confirmation click path untouched:
  `theOptionsDialog::EvictFamily()` still delegates to
  `CFamilyTree::EvictFamily()`, then resets the villager manager and switches
  to the adoption scene flow.
- Exports `Virtual-Families-2-Restoration-Addition-Patcher-B118.zip` and the
  standalone `Virtual Families 2 - Modded B118.exe` for testing.

## B119 - Settings Evict AddControl and Patcher Release Repo

- Completes the Settings Evict visibility patch by inserting the missing
  `ldwScene::AddControl(evictButton)` call after the dormant button's
  `SetText()` call. B118 enabled the constructor path but did not attach the
  button to the Settings scene control list.
- Adds stock text fixes for `Cooking like mommy` and `Driving like daddy`,
  retargeting them to gender-neutral `...like a grownup` wording.
- Adds an optional Island Events EXE overlay export path so enabling the
  experimental Island Events setting can swap in a bundled event-enabled EXE
  instead of leaving the checkbox visually enabled but functionally inert.
- Adds a GUI `Check for updates` hyperlink to the private standalone patcher
  release repo:
  `https://github.com/Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher/releases`.
- Saves the last vanilla install folder and modded output folder in
  `patcher_local_settings.json` beside the patcher for the next launch.

## B120 - Patcher Path and Island Events Refresh

- Publishes the portable B120 patcher bundle to the standalone patcher release
  repo.
- Shows the current build label in the GUI, adds a Check for updates link, and
  persists the vanilla/modded paths between launches.
- Moves Settings Evict and Island Events to Optional patches now that the
  button/event listing path is functional, and bundles the Island Events EXE
  overlay so the checkbox has a real payload.

## B121 - Evict Warning Wrap and Optional Graphics Patches

- Pre-wraps the Settings Evict confirmation string with explicit line breaks so
  it fits inside the stock in-game modal instead of clipping horizontally.
- Adds default-off optional `Misc Graphics Fixes`, currently replacing
  `Images/Upgrades/superFridge_NW.png`.
- Adds default-off optional `Glowing Collectibles`, replacing
  `Images/collectables_small.png`.
- Both new graphics patches are self-contained in the patcher payload and carry
  bundled vanilla restore sources for disable/reapply flows.

## B122 - Invisible Workspace Upgrades Payload

- Renames the optional upgrades visual setting label to `Invisible Workspace
  Upgrades` while keeping setting ID `invisible_upgrades_graphics`.
- Bundles the supplied invisible/original workspace upgrade PNG pairs under
  `payload/OptionalVisualMods/Invisible Workspace Upgrades/`.
- Enables/restores those graphics through `Images/Upgrades/*.png` asset records
  with paired `restore_source_path` entries, so applying and disabling the
  patch are both self-contained.

## B138 - Flea Market Expanded Sale Pool

- Adds native hooks for `CInventoryManager::GetCategoryItemCount` and
  `CInventoryManager::GetCategoryItem` when the active store category is the
  Flea Market (`3`).
- Recomputes the native eligible sale pool across item IDs `0x1AD` through
  `0x2A8` using the same generation-lock, pet-exclusion, and
  `AvailableForSale` filters seen in `MaybeUpdateSaleItems()`.
- Leaves the stock three-item sale cache at `CInventoryManager+0x474`
  untouched so its adjacent count and refresh timer fields are not overwritten.

## B139 - Reset Achievements Cheat Upgrade

- Adds `Reset Achievements` as Cheat Upgrades row `0x124` in Special Upgrades.
- Reuses the stock `CAchievement::Reset()` routine, then follows the existing
  visible-special-upgrade save path so goal/progress reset state persists.
- Bundles the trophy icon as `cheat_reset_achievements.png` in the workspace
  cheat-upgrade asset sources for self-contained patcher exports.

## B140 - Portable Patcher Metadata Refresh

- Re-exports the B139 gameplay payload as a B140 patcher release because the
  existing B139 GitHub Release asset is immutable and cannot be replaced.
- Keeps the same `1052` asset records and four EXE overlay payloads, but writes
  source-build provenance as portable filenames/build labels instead of local
  `C:\Users\...` paths.
- Verified the B140 patcher with an all-settings dry run against the workspace
  vanilla install; all `1052` active/restore asset records validated.

## B141 - Behavior Guard and Flea Market Retarget

- Guards Behavior Patch label variants behind the native behavior start result
  by comparing the villager action label at `CVillager+0x1BBA8` before and
  after each stock `CBehavior::*` call. This keeps stock shower, bathroom sink,
  grooming, age, object, and targeting gates intact while still applying label
  variants after accepted actions.
- Adds a per-villager/per-wrapper label cache so praise/HUD refresh calls keep
  the selected stock/custom behavior label instead of rerolling another
  variation while the same native route is still active.
- Corrects the Flea Market expansion from the category `0x03` On Sale cache to
  the real category `0x0F` rotating-goodies path backed by `gGoodiesList`.
- Normalizes Cheat Upgrade icons to transparent `90x90` payload images and
  refreshes the bundled `Reset Achievements` trophy icon from the supplied
  workspace-local copy.
- Exports `Virtual-Families-2-Restoration-Addition-Patcher-B141` with `1052`
  asset records, `2949` payload files, four B141 EXE overlays, and a clean
  all-settings dry run.

## B150 - Gated Behavior, Collection, Cheat, and Patcher Upgrade

- Adds Behavior Patches as the fourth independently built optional native
  switch. Together with Island Events, Cheat Upgrades, and Holiday Ornaments,
  B150 produces the full 16-state executable overlay matrix. Disabled features
  are absent from the selected executable instead of relying only on GUI
  checkbox metadata.
- Fixes the Holiday Ornaments Collections Chest crash by changing the injected
  collection page-count helper from cdecl to stdcall. Adds the Holiday family
  to the main-scene total and changes the unique visible suffix from 60 to 72,
  yielding six pages of 12 only under holiday_ornaments_collection.
- Behavior Patches makes Needs to sit down and Checking weight spontaneous for
  all ages; Mending a button and Ironing clothes spontaneous from displayed age
  14; and Teaching first words spontaneous only for nursing mothers carrying a
  baby. Petting label variants remain manual/native and Petting is not made
  spontaneous.
- Adds infant-care labels Teaching baby how to walk, Talking with baby, Feeding
  baby, Singing lullabies to baby, Playing with baby, Admiring baby, Playing
  peek-a-boo with baby, Kissing baby, and Taking pictures of baby.
- Adds Browsing web labels Watching memes, Making memes, Posting memes online,
  and Buying stuff online. Buying is gated to displayed age 13+.
- Expands Taking a nap to 30 dream labels: Isola, family, pets, friends, future,
  beach, snow, holidays, vacations, roller coasters, climbing mountains,
  camping, family trips, countryside, LDW games, city, forest, unicorns, fish,
  jungles, tropical islands, skyscrapers, floating in space, treasure, getting
  rich, adventures, swimming, flying, falling, and discovering something.
- Expands Needs to sit down with general reflection/rest/phone/scrapbook/texting
  labels. Age 19+ adds children/grandchildren/spouse and Texting spouse;
  Thinking of work requires age 19+ with a career; Thinking of school requires
  not being an age-19+ career holder; Texting boyfriend is female-only and
  Texting girlfriend male-only at ages 14-18.
- Enables direct sink behaviors 0x0A5-0x0A8 by cloning the native sink candidate
  gates, retains the general and female grooming pools, and adds Putting on
  jewelry for females age 14+. North-shower and snow routes preserve their
  object/weather gates; snow remains Weather.currentType 5 only.
- Repairs praise label retention by caching behavior ID/serial, the native
  praise counter, exact stock-label bytes, and the Radio listening/dancing
  branch, allowing a praise restart to reuse the current action string.
- Adds Cheat Upgrade rows Reset Ants 0x125, Reset all collections 0x126,
  Complete all collections 0x127, 2x Prices 0x128, 5x Prices 0x129, 100x
  Prices 0x12A, Trigger all house malfunctions 0x12B, and Reset Price
  Multiplier 0x12C.
- Reset Ants resets native world puzzle 0x13, clears ant props 0x4D-0x54, and
  reseeds the native start pieces. Collection reset raw-clears page/Master
  completion and progress, resets Holiday achievement state across overlay
  toggles, and recomputes Goal Collector from preserved selling goals.
  Completion covers five stock 12-item pages and conditionally adds the Holiday
  page/achievement only in a Holiday overlay.
- Price modes are mutually exclusive persistent toggles applied to the final
  CalcPrice result, covering furniture, Flea Market, renovations, career and
  Special Upgrades, and other store purchases. Overflow saturates at INT_MAX.
  Reset Price Multiplier removes active 0x128-0x12A and uses the exact
  description "Resets store prices to original values."
- Trigger all house malfunctions sets the normal house failure props. Dryer fire
  requires a Dryer lookup; north toilet/shower/sink leaks require renovation
  0xE6. Island Events Water Pressure Surge adds the three gated north leaks,
  while the stock standalone north random path remains independently available
  with its native renovation gate.
- Under Cheat Upgrades, rebuying Maid/Gardener fires the active service worker,
  clears its timer, and repairs selected-villager state. Rebuying Rockhound
  Certificate/Anti-Spam removes the owned upgrade/flag. Explicit cheat guards
  retain stock already-purchased behavior when the setting is disabled.
- Updates Brokerage Account text to state that its Interest Rate can reach 11%
  under mobile_purchases.
- Adds the exact vanilla-save compatibility note and Lorsieab2 passion-project,
  no-infringement, and support-the-original-creators message to the GUI,
  generated README, manifest metadata, and Transparency Log.
- Automated source, COFF, string, manifest, and exporter contracts cover these
  additions. Manual in-game matrix/collection/eligibility/store/removal/
  save-reload/malfunction testing remains tracked in docs/TODO.md and is not
  represented here as completed runtime verification.
- Final B150 automation generated, compiled, linked, and manifest-checked all
  16 Island/Cheat/Holiday/Behavior combinations. All build logs were clean and
  all 16 EXE SHA-256 values were unique. Test totals were 69 binary-patcher and
  30 exporter/GUI tests. Export totals were 1,075 asset records and 1,112
  manifest-reachable payload files.
- Final reachability pruning removed 1,860 payload files (100,244,363 bytes)
  that no source/restore record could read, excluded three generated `.bak`
  artifacts, revalidated retained hashes/sizes, and replaced the absolute
  base-payload metadata with its portable folder name. The 16-overlay matrix
  is retained because it contributes only about 10.9 MB compressed and
  preserves every independent native-setting combination.
- Final release archive:
  `outputs/Virtual-Families-2-Restoration-Addition-Patcher-B150.zip`,
  86,326,515 bytes, 1,122 entries, SHA-256
  `5A2EAE1FA89D723CE808FD82EC3FDA182AEF3E02E298F79CD3EEEECE5E7BF1DE`.

## B150 Hotfix - Holiday Control Flow, Praise, and Malfunction Pair

- Replaces the first B150 Holiday asset after a user-confirmed access violation.
  HandleMouse, Find, and WasItemSpawned use fixed-size detours to appended code
  caves; Drop has an incomplete-family reentry sentinel; The Collector Keep
  branch is repaired; and SetComplete awards the new collection meta-goal only
  on first completion.
- Normal praise now captures/restores the exact 0x28-byte action label around
  InvokeReward's native ForgetPlans/StartNewBehavior sequence. The intentional
  over-praise RunAway path remains native.
- Adds Fix all house malfunctions 0x12D, pairs Router offline/online state with
  Trigger/Fix, groups cheat rows by function without renumbering, and validates
  the stock Dryer-gated lint-fire/Handyman path.
- Records the requested B151 goal and Older Villagers design separately in
  docs/B151-design.md.
- Rebuilt all 16 overlays. All eight linked Holiday PEs passed direct branch
  validation. Tests: 71 binary patcher plus 56 exporter/runner/GUI, 127 total.
  Default and enable-all dry runs passed on the full official-install fixture.
- Replacement package retains 1,075 asset records, 1,112 reachable payload
  files, and 16 unique executable hashes. ZIP: 86,331,216 bytes, 1,122 files,
  SHA-256
  `847B8999135290632AD4216E463585EB2E7D3C4BCFEA79AF47A1BCE10CAAEC48`.

## B152 - Holiday Ornament Collection Text and Order

- Shortens only the Collections page title from "Holiday Ornaments" to
  "Ornaments".
- Replaces the reused bottle-cap rarity/footer IDs with dedicated additive
  ornament strings 0xE42-0xE44 and routes the existing fixed-size tooltip cave
  to their consecutive ID base.
- Keeps Ornamentologist at internal achievement ID 0x5F while inserting it
  directly after Bottlologist 0x5E in every layout where it is visible.
- Adds exact string, cave-routing, native-contract, and four-layout adjacency
  tests. The 18-test Holiday-focused run and full 82-test patcher module pass.
  No graphics or B2 award-hook regions changed; manual UI verification remains
  outstanding.

## B152 - Experimental Allow Older Pregnancies

- Adds a dormant ChanceOfPregnancy detour and default-zero writable .vf2preg
  byte to every executable, preserving the untouched native continuation when
  disabled or when both parents are under 50.
- The enabled late-age path uses GetRandom(1000), caps stock fertility math
  by the older parent's requested 10.0%-to-0.1% curve, and prevents the stock
  first-pregnancy tutorial from forcing a failed old-age roll to success.
- Adds a default-off Experimental patcher setting and generates exact-SHA
  post-asset variants for selected executable overlays, avoiding another
  matrix dimension. Multiples logic remains native.
- Core diagnostic SHA-256
  74C8F440FEAE80C3087818BD4B24A0D4B4685A7C2C1916AB01D5C7EF57BC657B
  links .vf2preg at raw 0x188800 and passes the bounded detour/helper validator.
- The exporter also locates .vf2goal at raw 0x188600 in that same payload and
  emits an independent Holiday Furniture goal record. Two-record apply tests
  cover default, both-enabled, both-disabled, and 16 unique layout hashes.

## B152 - Upright Holiday Ornament Graphics Payload

- Rebuilds the runtime collection page at 1024x768 from the supplied wood
  background, upright frame at (74, 4), upright Candy Cane at (848, 461), and 12
  upright placeholders at their absolute page coordinates.
- Ships the 12 supplied collected-icon PNGs byte-for-byte. No graphics are
  flipped, rotated, cropped, or resized.
- Canonical manifest schema 3 records all page layers. The rebuilt background
  SHA-256 is C94D42F228B78FB018F8F27392165072202BB57F5BA72B1FC902058678B983E0.
- Twenty-two Holiday Ornament tests plus the exporter routing test pass.

## B152 - Fresh Matrix Export and Package Pruning

- Rebuilt all 16 Island Events/Cheat Upgrades/Holiday Ornaments/Behavior
  Patches combinations from the B151 matrix instead of reusing stale output
  executables.
- Every generated variant passed its feature-gate check. The linked Holiday
  validator passed all eight Holiday-enabled and all eight Holiday-disabled
  variants.
- Exported only manifest-reachable files. The final ZIP contains 1,112 payload
  files and excludes stale EXEs plus build and patch logs.
- Final release archive:
  `outputs/Virtual-Families-2-Restoration-Addition-Patcher-B152.zip`,
  85,738,821 bytes, SHA-256
  `543A2E5814DECC7F70F30D8454F1475E3AD1A49FF8D3E6D63B8CFF709BE0DC36`.

## B153 Research - Request Ledger and Native Debugger Interface

- Adds `docs/REQUEST_LEDGER.md` as the durable cross-build completeness gate.
  It separates shipped, runtime-QA-pending, partial, uncertain, blocked, and
  not-started requests and includes all currently recovered behavior, cheat,
  goal, renovation, map, family, event, UI, packaging, and debugger requests.
- Desktop COFF inspection proves `theMainScene+8` is an `IDebugger` base,
  while `WaypointEditor` and `LightSourceEditor` are `IEditor` globals.
  The old research helper's editor-to-debugger casts were invalid.
- Corrects the dormant/default-off helper to register only the real main-scene
  debugger provider. F6 selects Waypoint Editor, F7 selects Light Source
  Editor, and F4 exits the selected editor through an independent IEditor route.
- Keeps mouse handlers stock in this phase. The native light editor's L add,
  D delete, S save, type cycling, and drag code are documented, but drag is not
  exposed until the key/display-only path passes save-load testing.
- The generated helper compiles successfully with the Visual C++ x86 toolchain.
  The targeted debugger interface regression test and Python syntax checks pass.

## B153 Source - Optional Older Villager Mortality Curve

- Adds a dormant `.vf2mort` byte and a default-off Experimental patcher row.
  Exact-SHA post-asset records toggle it independently of `.vf2preg` and
  `.vf2goal`, without expanding the 16 executable layouts.
- Detours only the annual old-age decision in VillagerManager upkeep. Flag-off
  calls native FoodGroupsActive and rejoins the unchanged stock block;
  enabled mode rolls the replacement curve and rejoins immediately afterward.
- Uses a normal survival component centered at effective age 75 (sigma 7), a
  0-4 year nutrition shift, and a 0.02% exponential no-hard-cap tail. Above
  effective age 130, annual old-age hazard remains 3%.
- Focused COFF, curve, and three-runtime-flag exporter tests pass. This source
  milestone is not yet a B153 release or a claim of live-gameplay validation.
- A disposable linked diagnostic resolves the native hook/helper and exposes
  writable/default-zero `.vf2mort` at raw `0x197A00`; SHA-256 is
  `A9EE0A6BB1D96296129F4EFE603837512E848BD5F28D6AC536EB318A3F87DC5C`.
  The full patcher/exporter suite passes 117 tests.

## B153 Research - Twelve-Child Storage and Next Generation

- Proves the live villager manager already has 30 ordinary slots, so 12 living
  children do not require enlarging the household object.
- Maps the actual blockers: six `0xD8` child records inside each `0x6C8`
  generation, a completely occupied `0xCB74` Family Tree save block, a
  two-row renderer/hit tester designed around six children, and two six-entry
  Next Generation candidate arrays embedded in `CAdoptionScene`.
- Records the safe implementation boundary: versioned sidecar persistence and
  coordinated tree/candidate/UI detours must land before the birth limit can
  be raised. This research milestone intentionally does not ship a partial
  12-child toggle that could corrupt generations or scene fields.

## B153 Source - Guarded Native Debugger Input

- Keeps debugger support completely default-off. Normal builds still use the
  stock `theMainScene.obj`; only `ENABLE_DEBUGGER_FEATURES=1` produces the
  developer research route.
- Extends the existing F5-gated key-down hook with key-character and mouse
  down/move/up hooks. Disabled sessions and unhandled events resume the stock
  functions, while guarded access faults disable the research session.
- Preserves the correct interface split: only `theMainScene+8` registers as an
  `IDebugger`; F6/F7 select Waypoint/Light Source through `IEditor`, and F4
  exits the active editor.
- Stock disassembly found and the source corrects an interim character-hook
  cleanup mismatch: `HandleKeyCharacter(char)` uses `ret 4`, not `ret 12`.
  The superseded research diagnostic was never shipped.
- The corrected COFF object and helper link into a disposable x86 diagnostic.
  SHA-256:
  `680A40B76E38C381AC3817687553078378616F1B18AE88B7E95D5537223B8FA3`.
- Byte-level tests cover all five payloads, native cleanup widths, REL32 helper
  targets, and stock fallthrough. The complete 97-test suite passes.
- Live save-load, selector, waypoint, light-source, input-fallthrough, and
  fault-recovery validation remains before enabling this path in a release.
