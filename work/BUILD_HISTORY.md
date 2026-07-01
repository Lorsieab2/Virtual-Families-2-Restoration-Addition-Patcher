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

## Next Build Contract - Additive Native Arrays

- Enables the additive mobile Island event table by default in the patcher.
- Records the native arrays that additive builds are allowed to grow:
  furniture records/lookups, inventory category lists, graphics descriptors,
  string rows, Island event slots, furniture click dispatch, and villager
  behavior candidates.
- Documents the rule that new furniture, events, strings, graphics, and behavior
  routes are appended with widened bounds, while base desktop entries remain
  untouched.
