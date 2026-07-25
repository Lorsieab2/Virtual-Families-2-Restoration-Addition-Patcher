# B156 PC room-render boundary

## Confirmed from the local PC object files

The current PC build does not expose a direct room-overlay selector in the
paths inspected for B156:

- `CContentMap::Draw` uses `ldwGameWindow::FillRect` while traversing map
  content. It does not call `theGraphicsManager::GetImage` or select a room
  PNG.
- `CEnvironment::Draw` is an immediate `ret` in `Environment.obj`, so the
  environment object is not the room-background renderer in this build.
- `CWorldMap::Draw` draws the four-by-four world-map image set loaded as
  `MapX##Y##.jpg`. It is unrelated to the house renovation atlases.
- `theMainScene::DrawScene` invokes the world map, environment, and furniture
  manager in that order; no per-renovation image argument is visible at this
  call site.

The complete `dumpbin /DISASM /SYMBOLS` capture is preserved in the ignored
file `outputs/B156-PC-Room-Render-Dumpbin.txt`.

## Consequence for the mobile renovation art

The 15 corrected mobile room atlases remain staged under the optional visual
payload. Adding them to the PC image registry alone would not make them render,
and drawing them from the main-scene hook without the native room coordinates,
camera transform, and renovation-state selector would risk covering furniture
or villagers. B156 therefore keeps runtime copying disabled until those three
pieces are recovered together.

## Next native target

Trace the caller/vtable path that invokes `CContentMap::Draw` and identify the
PC room-state data that supplies the map's room materials and bounds. The
selector must then be proven for purchase, save/load, switching/removal, and
second-bathroom behavior before any atlas is bound to live rendering.
