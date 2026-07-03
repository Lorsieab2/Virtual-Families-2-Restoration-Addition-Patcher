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
