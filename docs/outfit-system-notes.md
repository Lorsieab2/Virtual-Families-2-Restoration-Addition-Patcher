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

## Holiday outfit organization milestone

`work/organize_holiday_outfits.py` copies the existing holiday source frames
into the generated body tree by gender and intended runtime body value. The
four mobile source sets `51` through `54` map onto the first four desktop
additive slots, `Body_50` through `Body_53`, for both Female and Male. Each
set has 61 frames. The output filenames begin with gender and runtime body
value, for example `Female_Body_50_Holiday_Frame_0001.png`.

The raw `Images/HolidayOutfits` inputs are deliberately retained. This step is
asset organization only: it neither expands the stock 0--49 runtime body range
nor changes the animator lookup.

## Holiday compatibility frame milestone

`work/organize_holiday_outfits.py` also emits normalized 91 x 91 compatibility
frames for each additive holiday body. The raw mobile outfit sources have 61
frames per outfit on larger transparent canvases; the compatibility subset maps
them into the same role counts used by the stock desktop sheets:

- source frames 1--32 -> `bodies` frames 0--31
- source frames 33--47 -> `actions` frames 0--14
- source frames 48--56 -> `sit` frames 0--8

Frames are resized and positioned against the stock `Body_49` frame geometry
for the matching gender, role, and frame index. This gives a future runtime
resolver complete per-frame PNGs for body values 50--53 while leaving the
original 0--49 spritesheets as the fallback path. Source frames 57--61 are
preserved as raw holiday copies but are not mapped into the first compatibility
resolver pass.

## Clothing store preview icon milestone

B66 adds explicit store preview art for the generated outfit rows. The added
rows are gender-specific:

- Female outfit item IDs: `0x400` through `0x435`
- Male outfit item IDs: `0x440` through `0x475`

B69 updates the icon source rule. The patcher writes one 91 x 91 PNG per row
under `Images/OutfitIcons/` using the last frame column from the matching
action sheet:

- female rows: `female_actions00.png`
- male rows: `male_actions00.png`
- source cell: row = body value, column = last 91 px frame column (`14` in the
  current desktop/mobile-compatible sheets)

Base body values `0--49` come from the clean base-game runtime sheets copied
into the modified build's local `OUT/Images` folder. The game reads those
build-local `Images/*.png` files at runtime; it must not reference an external
`originalimages` source folder. Holiday body values `50--53` use the
repo-local split `generated/VillagerBodies` frames first, the Holiday archive
second if present, and expanded sheet rows only as a migration fallback.

`theGraphicsManager` receives 108 appended 1 x 1 image descriptors for those
icons. `CInventoryManager::DrawItem(ldwPoint, ...)` and
`CInventoryManager::DrawItem(ldwRect, ...)` have narrow prologue hooks that
only intercept these high outfit item IDs and draw the matching preview icon;
non-outfit inventory drawing falls through to stock code.

## Clothing store purchase milestone

Native outfit application expects stock tray item `0x49` for male outfits and
`0x4A` for female outfits, with the stock selected body value stored in
`CInventoryManager`:

- `InventoryManager+0x468`: male outfit body value
- `InventoryManager+0x46C`: female outfit body value

B69 originally added `_VF2PurchaseOutfitStoreItem` and a narrow
`CScrollingStoreScene::HandlePurchaseItem + 0x1AD` hook. After the normal coin
charge, recognized generated outfit IDs set the matching body field, add tray
item `0x49` or `0x4A`, save the game, and skip the native high-ID no-op path.

B71 removes the risky `CInventoryManager::GetUseCount` hook and stops calling
`CToolTray::IsSlotAvailable` from `GetNumAvailable`. The remaining
`GetNumAvailable` hook is now only a pure synthetic-ID guard that returns `1`
for generated outfit rows and `-1` for all stock rows, so entering the Clothing
category no longer reaches ToolTray state through a generic store availability
query.

B73 fixes the remaining Clothing-entry crash hypothesis in the generated
outfit getter hooks. The member-function hooks call helper functions before
falling through to stock code for base rows, so they must preserve `ECX`, the
native `CInventoryManager this` pointer, across the helper call. The patched
member getters now `push ecx` before the helper call and `pop ecx` before
falling through when the helper returns `-1`.

B75 changes generated outfit purchases to store the synthetic outfit item ID in
the `CToolTray` slot instead of reusing one stock tray item per gender. The
synthetic ranges are still:

- Female generated outfit items: `0x400` through `0x435`
- Male generated outfit items: `0x440` through `0x475`

`ToolTray.obj` now patches `CToolTray::GetToolInHand()` and
`CToolTray::GetToolInUse()` so those synthetic IDs normalize to stock female
item `0x4A` or stock male item `0x49` only while vanilla main-scene outfit
checks are running.
`CInventoryManager::GetOutfit()` then resolves the body value from the selected
synthetic ID. This keeps each tray slot independent: buying body `03` and body
`52` no longer mutates both tray icons/items through one shared
`InventoryManager+0x468/+0x46C` field.

The stock tray behavior remains valid for native outfit items `0x49` and
`0x4A`; when no generated outfit item is selected, the helper falls through to
the original `CInventoryManager` body fields.

B93 splits the selected synthetic outfit state by tray query. `GetToolInHand`
uses `gVF2SyntheticOutfitToolInHand` (`activeFlagOffset == 0xA4`) and
`GetToolInUse` uses `gVF2SyntheticOutfitToolInUse` (`activeFlagOffset ==
0xA5`). `_VF2GetOutfitStoreBodyValue` checks the in-use synthetic ID first and
then the in-hand synthetic ID before falling through to vanilla. This prevents a
stock-ID query from clearing the synthetic item before `GetOutfit(0x49/0x4A)`
can decode Holiday body values `50--53`.

## Holiday runtime frame regeneration milestone

B68 fixes a crash-prone split between store preview art and runtime villager
body art. The Clothing store can show Holiday outfit icons from fallback
expanded sheets, but gameplay needs folder-backed runtime frames plus offsets
for body values `50--53`.

`sync_holiday_body_runtime_frames()` now searches complete image roots instead
of only the current additive output folder: current `OUT/Images`, prior
completed `outputs/VF2-Mobile-Furniture-With-Island-Events-B*` build folders,
then `outputs/VF2-Mobile-Furniture-With-Island-Events-B56-Holiday-Body-Lookup-Test`.
B93 changed the Holiday art priority inside that search: split
`generated/VillagerBodies/<Gender>/Body_50..53` frames are preferred over
Holiday archive frames, and expanded sheet rows are only a last fallback.
This regenerates 448 runtime frame PNGs:

- 2 genders
- 4 Holiday body values (`50--53`)
- 56 mapped frames per value (`32 bodies + 15 actions + 9 sit`)

`vf2_villager_body_frames.cpp` still routes only recognized villager body grids
through the folder-backed renderer. If an individual Holiday frame image is
unavailable, the fallback draw call clamps that recognized body-grid row to
stock row `49` instead of passing `50--53` to the vanilla sheet renderer.

## Holiday body value lookup milestone

B80 re-enables the native body-link lookup patch for Holiday outfits. The
generated store IDs are still additive inventory rows, but they decode to real
body values before application:

- female Holiday outfit items: `0x432--0x435` -> body values `50--53`
- male Holiday outfit items: `0x472--0x475` -> body values `50--53`

`patch_holiday_body_lookup()` widens only the body overloads of
`CAnimManager::GetScaledLinkToNextPt()` and
`CAnimManager::GetScaledLinkToPrevPt()` from rows `0--49` to rows `0--53`.
The default invalid-row fallback remains stock row `49`.

`VF2SafeFallbackBody()` protects the folder-backed draw helper fallback:
negative body IDs become row `0`, stock IDs `0--49` pass through, and values
`>=50` fall back to row `49` unless the Holiday frame renderer resolves them.

B89 reverses the native link widening for the current folder-backed renderer.
Normal additive builds do not expand the stock body/action/sit sheets, so
`CAnimManager` must keep clamping body values `50--53` to row `49` for
head/body link points. The one-cell Holiday renderer still draws the visual
body frames; only the link geometry falls back to the stock row-49 template
used during frame normalization.
