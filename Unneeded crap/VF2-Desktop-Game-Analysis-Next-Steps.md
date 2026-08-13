# VF2 Desktop Game Analysis And Plausible Next Steps

Analyzed folder:

`work/vf2_windows_test`

Delivered modded copy:

`outputs/VF2-Mobile-Furniture-Modded`

## High-Level Structure

The desktop game is mostly loose assets plus hardcoded runtime tables:

| Type | Count | Notes |
|---|---:|---|
| `.png` | 1670 | Loose image assets under `Images/`. |
| `.ogg` | 599 | Sound/music. |
| `.fmap` | 276 | Furniture/object map metadata under `Assets/`. |
| `.dat` | 252 | Mostly `tp*.dat` texture/page manifests and map/avatar metadata. |
| `.exe` | 3 | Main executables/uninstaller. |

Relevant executable:

- `Virtual Families 2.exe` - older/smaller build.
- `Virtual Families 2 - Copy Official.exe` - larger official/copy build.

Both contain embedded image/path strings and furniture tables.

## Asset State

The mobile/event PNGs have been added to `Images/Furniture`, and the `.fmap` files already exist in `Assets`.

Verification from the delivered output copy:

- `275` `Assets/*.png.fmap` references checked.
- `272` matching PNGs found under `Images/`.
- The remaining three missing same-name PNGs are old beanbag variants:
  - `ChairBeanbagGreenStdold.png`
  - `ChairBeanbagOrgOldStd.png`
  - `ChairBeanbagRedStdOld.png`

The mobile/event batch itself is present.

## Important Discovery

The EXE has a hardcoded `Furniture/...png` path table.

In `Virtual Families 2 - Copy Official.exe`:

- Embedded furniture image paths found: `239`
- Unique embedded furniture image paths: `239`
- `Assets/*.png.fmap` references: `275`
- `.fmap` assets not present in the EXE furniture path table: `44`

Those `44` are exactly the mobile/event furniture/decor set plus old beanbag variants:

- `Balloons_birthday.png`
- `Birthday_banner.png`
- `Birthday_cake.png`
- `Birthday_presents.png`
- `CandleOnHolder.png`
- `CandyCane.png`
- `Chaise_blue.png`
- `Chaise_brown.png`
- `Chaise_green.png`
- `Chaise_red.png`
- `ChristmasCookie.png`
- `ChristmasTree1.png`
- `ChristmasTree2.png`
- `Dreidel.png`
- `GlassOfEggnog.png`
- `Gnome1.png`
- `Gnome2.png`
- `Gnome3.png`
- `Gnome4.png`
- `Gnome5.png`
- `Menorah.png`
- `Patio_brick.png`
- `Patio_cobblestone.png`
- `Patio_table.png`
- `Patio_umbrella.png`
- `PenguinDecoration.png`
- `Picnic_table.png`
- `PlateOfCookies.png`
- `Poinsettia.png`
- `PolarBearDecoration.png`
- `RedBow.png`
- `ReindeerDecoration.png`
- `SantaGardenDecoration.png`
- `SantaWallDecoration.png`
- `Snowman.png`
- `StockingLarge.png`
- `StockingSmall.png`
- `StringOfLeaves.png`
- `StringOfLights.png`
- `Wreath1.png`
- `Wreath2.png`
- plus old beanbag variant names.

## `tp*.dat` Clue

The `tp*.dat` files do reference some mobile/event asset groups:

- `tp224.dat` contains:
  - `christmastree1.png`
  - `reindeerdecoration.png`
  - `santagardendecoration.png`
  - `snowman.png`
  - `stringofleaves.png`
  - `stringoflights.png`

- `tp226.dat` contains:
  - `candleonholder.png`
  - `candycane.png`
  - `christmascookie.png`
  - `christmastree2.png`
  - `dreidel.png`
  - `glassofeggnog.png`
  - `gnome1.png` through `gnome5.png`

- `tp236.dat` contains:
  - `balloons_birthday.png`
  - `birthday_banner.png`
  - `birthday_cake.png`
  - `birthday_presents.png`
  - `chaise_blue.png`
  - `chaise_brown.png`
  - `chaise_green.png`
  - `chaise_red.png`

So the art may be texture-loadable, but those items are not in the EXE's embedded furniture path/catalog table.

## Likely Architecture

The desktop build appears to have at least two layers:

1. **Texture/page loading layer**
   - Uses `tp*.dat` manifests and loose PNGs.
   - Some mobile/event assets already appear here.

2. **Furniture/catalog/runtime item layer**
   - Hardcoded in the EXE, based on embedded `Furniture/...png` paths and likely adjacent metadata tables.
   - Mobile/event items are missing from this table.

This means adding only PNGs and `.fmap`s is necessary but probably not sufficient. The game also needs catalog/item entries or save-object entries that point at those assets.

## Plausible Next Steps

### Path A: EXE Table Patch

Goal: add the 44 missing `Furniture/...png` paths and matching metadata to the EXE item table.

Risk: moderate/high. There may not be enough slack space to insert new strings and structs in-place. This may require code cave/table relocation patching.

Useful next work:

- Locate the exact pointer table referencing the embedded `Furniture/...png` strings.
- Determine item record size and fields around each furniture item:
  - asset path pointer
  - `.fmap`/object name
  - category
  - price
  - room/placement flags
  - inventory/store flags
- Try replacing an existing low-risk furniture path with `Furniture/Chaise_blue.png` as a proof of load/render.

### Path B: Save Injection Proof

Goal: place a mobile item into a desktop save by reusing an existing furniture object slot and swapping its object/image ID.

Risk: moderate. Needs controlled saves to map object record fields.

Best input:

- Desktop save before placing a known vanilla item.
- Desktop save after placing that known vanilla item.
- Desktop save after moving it.

Then repeat with an item whose EXE entry is similar to the mobile item, such as a couch/chaise-like object.

### Path C: Controlled Diff Tool

Goal: build a local save-diff viewer for Windows `.ldw` saves.

This should parse:

- 16-byte desktop header.
- person table at `0x17a74`, stride `0x7bc`.
- likely object block around `0xe3c0`, stride `0x40`.
- changed 4-byte fields between two saves.

This is the safest next engineering step because it turns unknown binary layout work into observable deltas.

### Path D: External Rebuild

Goal: build a new game runtime using the desktop assets and mobile-added furniture art.

Risk: large scope, but no EXE patching.

This becomes practical after:

- furniture object metadata is mapped
- save format is partially mapped
- room/map coordinates are mapped
- character animation/action data is understood enough to render convincingly

## Recommended Order

1. Build a desktop `.ldw` diff/viewer tool.
2. Use controlled desktop saves to map furniture placement records.
3. Perform a save-injection proof with an existing vanilla furniture item.
4. Try asset substitution proof: replace one existing furniture path with `Furniture/Chaise_blue.png`.
5. If that renders, proceed to EXE table expansion or controlled item replacement.

