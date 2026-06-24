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
