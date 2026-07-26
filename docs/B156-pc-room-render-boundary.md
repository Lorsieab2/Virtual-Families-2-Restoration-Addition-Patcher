# B156 PC room-render boundary

## Confirmed from the local PC object files

The current PC build does not expose a direct room-overlay selector in the
paths inspected for B156:

- `CContentMap::Draw` uses `ldwGameWindow::FillRect` while traversing map
  content. It does not call `theGraphicsManager::GetImage` or select a room
  PNG.
- `CEnvironment::Draw` is an immediate `ret` in `Environment.obj`, so the
  environment object is not the room-background renderer in this build.
- `CWorldMap::Draw` draws the four-by-four static house background loaded as
  `MapX##Y##.jpg`. The stitched 2048x2048 reference is preserved in the
  ignored file `outputs/B156-PC-house-map-stitch.png`.
- `CWorldMap::LoadAssets` formats those sixteen filenames once and has no
  inventory, upgrade, or renovation-state dependency. Its draw loop only
  culls the tile rectangles and calls `ldwGameWindow::Draw`.
- `CContentMap::ActivateCondemnedArea` changes the 256x256 content grid's
  material, hotspot, and object fields. It does not select or replace a map
  background image.
- `theMainScene::DrawScene` invokes the world map, environment, and furniture
  manager in that order; no per-renovation image argument is visible at this
  call site.

The complete `dumpbin /DISASM /SYMBOLS` capture is preserved in the ignored
file `outputs/B156-PC-Room-Render-Dumpbin.txt`.

## Consequence for the mobile renovation art

The 15 corrected mobile room atlases remain staged under the optional visual
payload. Adding them to the PC image registry alone would not make them render,
and drawing them from the main-scene hook without the native map-tile anchors,
camera transform, and renovation-state selector would risk covering furniture
or villagers. B156 therefore keeps runtime copying disabled until those three
pieces are recovered together.

## Next native target

Add a guarded map-variant path only after establishing the atlas scale and
anchor against the stitched map. The native build currently has no existing
room-state image selector: a safe implementation will need to introduce one,
choose the active variant from persisted renovation state, and preserve the
stock tile path when the optional patch is disabled. Then prove purchase,
save/load, switching/removal, and second-bathroom behavior before any mobile
atlas is bound to live rendering.
