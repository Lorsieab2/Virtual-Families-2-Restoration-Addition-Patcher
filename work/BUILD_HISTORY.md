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
