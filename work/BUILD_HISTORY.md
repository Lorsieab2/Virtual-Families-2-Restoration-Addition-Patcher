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
