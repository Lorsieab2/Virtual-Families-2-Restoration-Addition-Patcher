# VF2 Outfit System Notes

Status: Phase 1 investigation only. No runtime behavior, object, spritesheet,
or lookup code was changed for this milestone.

## Evidence inspected

- `outputs/VF2-Mobile-Furniture-With-Island-Events-B53-Base-Villager-Sheets-Restore/Images/`
- `Unneeded crap/VF2-Desktop-Object-Analysis/image-descriptors.json`
- `work/desktop_obj_files/AnimManager.obj`
- `work/desktop_obj_files/Villager.obj`
- `work/patch_mobile_furniture_pack.py`

## Sheet storage and grid layout

The desktop renderer uses `ldwImageGrid` objects backed by the following image
descriptors. Every cell is 91 by 91 pixels, preserving the original transparent
padding and anchor placement.

| Gender | Role | File | EImage ID | Grid | Cell size |
| --- | --- | --- | ---: | --- | --- |
| Female | body/walk | `female_bodies00.png` | 577 | 32 columns x 50 rows | 91 x 91 |
| Female | actions | `female_actions00.png` | 578 | 15 columns x 50 rows | 91 x 91 |
| Female | sit/lie | `female_sit00.png` | 579 | 9 columns x 50 rows | 91 x 91 |
| Male | body/walk | `male_bodies00.png` | 581 | 32 columns x 50 rows | 91 x 91 |
| Male | actions | `male_actions00.png` | 582 | 15 columns x 50 rows | 91 x 91 |
| Male | sit/lie | `male_sit00.png` | 583 | 9 columns x 50 rows | 91 x 91 |

The B53 copies measure:

- body sheets: 2912 x 4550 pixels
- action sheets: 1365 x 4550 pixels
- sit sheets: 819 x 4550 pixels

This verifies that an outfit is represented by the **same row number** in the
body, action, and sit grids. The animation frame determines the column; the
villager body value determines the row.

## Current lookup path

1. A villager stores its body/outfit as an integer at `CVillager + 0x6A84`.
2. Drawing calls into `CAnimManager::GetScaledLinkToNextPt` or
   `CAnimManager::GetScaledLinkToPrevPt`.
3. These functions choose the appropriate `ldwImageGrid` for animation part
   and gender, use the animation frame as the column, and use the body value as
   the row.
4. `ldwImageGrid::GetCellRect` turns that column/row pair into a source
   rectangle on the original sheet.

There is no discovered name-to-outfit asset registry in the stock desktop
binary. Base outfits are positional rows, not independently named PNG paths.
Any future manifest layer therefore needs to preserve this row/column contract
and sit *in front of* the stock grid lookup, with a stock-grid fallback.

## Known body ID ranges and limits

The stock `CVillager` generators are zero-based:

| Generator | Native calculation | Resulting IDs |
| --- | --- | --- |
| Common | `GetRandom(0x20)` | 0 through 31 |
| Uncommon | `GetRandom(0x0C) + 0x20` | 32 through 43 |
| Rare | `GetRandom(0x06) + 0x2C` | 44 through 49 |

This matches the 50 rows in each stock sheet. The first visual row is therefore
runtime body ID `0`, even though a human-facing folder name may call it
`Body001`.

The four `CAnimManager` link functions contain a row guard equivalent to:

- accept body value when it is below `0x32` (50)
- otherwise use the last stock row, `0x31` (49)

The previous holiday experiment minimally widened that guard to rows 0 through
53 and widened the rare generator to include 50 through 53. It did **not** add
an independent outfit-definition table, nor did it add matching action/sit
rows.

## B53 compatibility warning

B53 intentionally restored the six supplied base sheets, which are all 50
rows high. Its executable was inherited from B52 and may still contain the
temporary 0--53 animator guard. Therefore IDs 50--53 must be treated as
unsupported until a compatibility layer supplies complete body, action, and sit
row data for every new outfit. The safe fallback is stock row 49/original-sheet
rendering, never an unchecked grid read.

## Phase 2 design constraints

The extraction tool should be offline and non-destructive:

- Read the six original sheets without modifying them.
- Slice cells by the verified 91 x 91 grid, retaining transparent padding.
- Name files by gender, role, zero-based outfit ID, and zero-based frame index.
- Write to a generated directory such as `generated/outfit-extraction/`.
- Emit a manifest containing source file, source image ID, row, column,
  rectangle, and anchor-preserving cell size.

The compatibility layer should first be a resolver that checks a manifest for a
complete replacement set, then falls through to the current stock `ldwImageGrid`
path. It must log unknown outfit IDs, missing roles, invalid frame columns, and
fallback decisions. No stock sheet should be overwritten or removed.

## Files changed by this milestone

- `docs/outfit-system-notes.md`: records the Phase 1 findings only.

## Phase 2 extraction milestone

`work/extract_villager_bodies.py` now performs a non-destructive extraction of
the six stock sheets. Given an `Images` directory, it writes one 91 x 91 PNG
per grid cell under `generated/VillagerBodies`:

- `VillagerBodies/Female/Body_00` through `Body_49`
- `VillagerBodies/Male/Body_00` through `Body_49`

Every filename includes gender, zero-based body value, role (`bodies`,
`actions`, or `sit`), and zero-based frame number. The accompanying
`manifest.json` records the exact original source rectangle for every frame.
For the stock sheets this produces 5,600 frames: 2 genders x 50 body values x
(32 body + 15 action + 9 sit frames). The generated output is intentionally
ignored by Git; only the reproducible extractor is tracked.

## Head extraction milestone

`work/extract_villager_heads.py` performs the equivalent non-destructive
extraction for the four stock head sheets. It writes 24 frames for each of the
50 zero-based head rows under `generated/VillagerHeads`:

- `VillagerHeads/Female/Adult` from `female_heads00.png`
- `VillagerHeads/Female/Elderly` from `female_heads10.png`
- `VillagerHeads/Male/Adult` from `male_heads00.png`
- `VillagerHeads/Male/Elderly` from `male_heads10.png`

Each extracted head frame is 28 x 56 and carries gender, age bank, zero-based
head value, and zero-based frame index in its filename. The emitted manifest
records the exact original source rectangle. This produces 4,800 frames in
total and does not change the stock head lookup or source sheets.

## Build export packaging

`work/package_villager_sprite_exports.py` copies the generated
`VillagerBodies` and `VillagerHeads` folders into a completed build under
`Assets`. These are reference/editing exports only: they do not replace the
stock `Images` sheets or participate in the runtime sprite lookup.
