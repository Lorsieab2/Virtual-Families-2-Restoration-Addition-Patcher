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

Trace the map-tile load/draw path and identify the PC room-state data that
selects or replaces the affected `MapX##Y##.jpg` regions. Establish the atlas
scale and anchor against the stitched map, then prove purchase, save/load,
switching/removal, and second-bathroom behavior before any mobile atlas is
bound to live rendering.
