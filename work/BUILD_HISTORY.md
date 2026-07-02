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
