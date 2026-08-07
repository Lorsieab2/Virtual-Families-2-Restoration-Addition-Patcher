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
- The mobile `0xE1-0xEA` handler also calls `CEnvironment::SetProp` for each
  renovation. The inspected PC `CEnvironment::Draw` is an immediate return,
  so porting those state writes alone cannot display the mobile room art.
- `theMainScene::DrawScene` invokes the world map, environment, and furniture
  manager in that order; no per-renovation image argument is visible at this
  call site.

The complete `dumpbin /DISASM /SYMBOLS` capture is preserved in the ignored
file `outputs/B156-PC-Room-Render-Dumpbin.txt`.

## B157 1:1 overlay implementation

B157 adds the guarded renderer and keeps it disabled by default. With
`VF2_ENABLE_MOBILE_RENOVATIONS=1`, the patcher registers all 15 complete PNG
overlays under `Images/MobileRenovations` with a `[1,1]` descriptor and no
resampling. It inserts the helper at `theMainScene::DrawScene +0x39`, directly
after `CWorldMap::Draw` and before the stock decal draw.

The helper reads the world-view origin, selects the first active style for each
room in native mobile item order from PC style IDs `0x13C-0x14A`, and draws each selected image at its
absolute map anchor minus the camera origin. The encoded anchors are Bathroom
`(535,1263)`, Kitchen `(930,995)`, Office `(1357,792)`, and Workshop
`(900,1475)`. The PNG dimensions are preserved exactly; no scale or crop is
applied.

The disabled build has no main-scene hook and no runtime
`Images/MobileRenovations` directory. This preserves the stock map path while
leaving the same art in the optional staged payload. Static generation,
contract validation, compilation, and linking pass for the enabled route;
live visual/player confirmation is still pending.

The native purchase and save-load state routes are a separate, proven layer:
the PC `HandleUpgrade` and `theGameState::Load(int)` paths already carry the
same ten mobile `0xE1-0xEA` condemned-area activations. The patcher now checks
those routes against `data/vf2/mobile-renovation-atlas-contract.json` and
fails closed on drift. This native-state validation is independent of the
optional B157 renderer; it does not by itself prove live visual selection.

## Remaining validation

The PC style catalog and first-owned-per-room selector are now statically
linked. Live purchase, switching/free reactivation, save/load, camera movement, and
patch-off visual QA remain. Bathroom 2 remains deferred because no separate
second-bathroom overlay/state route has been proven.
