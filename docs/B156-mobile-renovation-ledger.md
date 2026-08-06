# B156 mobile renovation ledger

## Confirmed from the supplied VF2 mobile 1.7.16 build

The mobile load path uses the existing house-renovation inventory range
`0xE1-0xEA` (decimal `225-234`). On successful load it checks each owned
upgrade and activates the following condemned-area map regions:

| Item | Map area | Native activation call |
| --- | --- | --- |
| `0xE9` (`233`) | `(11,7)` | `ActivateCondemnedArea(11,7,0,1,56,52)` |
| `0xE7` (`231`) | `(12,7)` | `ActivateCondemnedArea(12,7,0,1,57,48)` |
| `0xE4` (`228`) | `(15,7)` | `ActivateCondemnedArea(15,7,0,1,53,49)` |
| `0xE8` (`232`) | `(9,7)` | `ActivateCondemnedArea(9,7,0,1,54,53)` |
| `0xE3` (`227`) | `(10,7)` | `ActivateCondemnedArea(10,7,0,1,52,108)` |
| `0xE5` (`229`) | `(14,7)` | `ActivateCondemnedArea(14,7,0,1,59,105)` |
| `0xE2` (`226`) | `(8,7)` | `ActivateCondemnedArea(8,7,0,1,55,107)` |
| `0xE1` (`225`) | `(16,6)` | `ActivateCondemnedArea(16,6,0,1,61,51)` |
| `0xEA` (`234`) | `(17,6)` | `ActivateCondemnedArea(17,6,0,1,62,109)` |
| `0xE6` (`230`) | `(13,7)` | `ActivateCondemnedArea(13,7,0,1,58,106)` |

Evidence source: the IDA recovery of `theGameState::Load` in
`outputs/B156-Mobile-Holiday-IDA/special-upgrades.txt`, where the ten
`CInventoryManager::HaveUpgrade` checks occur after the core save-state loads.

## Local art status

The supplied mobile room atlases were decoded into 15 upright RGBA PNGs under
`work/assets/mobile_renovations/`. The asset QA manifest proves each output is
the exact vertical row reversal of its extracted source; no scaling, crop,
redraw, or recoloring was applied. The groups are:

- Bathroom 1: five `tp233`-`tp235` variants.
- Kitchen: three `tp238`-`tp240` variants.
- Office: five `tp239`-`tp242` variants.
- Workshop: two `tp238`/`tp242` variants.

The patch build now stages these files under
`OptionalVisualMods/Mobile Renovations` and records the exact source/target
list in its build manifest. They are not copied into the live `Images` tree:
the PC executable's room-background selector has not yet been proven, so
activating these files without that binding would be an unsupported native
render change. The optional Bathroom 2 plan remains to reuse the corrected
Bathroom 1 files once a native second-bathroom render route is verified.

The bundle-level extraction record is tracked in
`data/vf2/mobile-renovation-atlas-contract.json`. It records the eight mobile
texture bundles that supplied the 15 staged room overlays, the extracted
bathroom support textures that are intentionally not staged, and the current
runtime-copy/selector boundary. It now also pins the ten native activation
records and the mobile save-load order used by the static PC parity validator.
This is still metadata plus static route validation; it does not claim that
the PC executable can yet select these overlays at runtime.

## Native PC route parity

The inspected PC executable already contains the corresponding native routes.
B156 now validates them on every generated build instead of replacing them:

- `CScrollingStoreScene::HandleUpgrade` dispatches each item `0xE1-0xEA` to
  the stock `ActivateCondemnedArea` call with the mobile map/material/hotspot/
  object arguments and then sets the matching environment prop.
- `theGameState::Load(int)` checks the same ten owned upgrades in the mobile
  order and replays the same `ActivateCondemnedArea` arguments.

The build manifest records this as
`mobile_renovation_native_behavior.status = validated_and_preserved`. The
validator is deliberately fail-closed: if a call target, switch entry,
activation argument, prop, or load-order record drifts, the build stops.
This proves the native purchase and save-load state path. It does not solve
room-background compositing or Bathroom 2 art selection; the Cheat Upgrades
removal route is source-validated separately and still needs live QA.

## Remaining native work

1. Recover the PC map-tile compositing and renovation-state selector. The
   inspected PC path renders the static house background through
   `CWorldMap::Draw` from `Images/MapX##Y##.jpg` (16 512x512 tiles), not a
   proven per-item `EImage` room selector. The mobile activation coordinates
   above are condemned-area/content-map coordinates; they must not be treated
   as pixel anchors until the corresponding PC map geometry is verified.
   Bind each `0xE1-0xEA` state to the correct staged atlas/variant only after
   its scale and tile anchor are measured against the stitched map.
2. Recover the PC map-tile compositing and renovation-state selector, then
   verify the visual result in-game against the staged mobile atlases.
3. Live-verify the Cheat Upgrades removal/re-purchase route, switching, and
   save/load behavior against the mobile inventory semantics. The source route
   rebuilds `CContentMap` from the native ten-record table and is guarded by
   the Cheat Upgrades overlay; no generic renderer reset is used.
4. Add Bathroom 2 as a separate optional route only after its overlay anchor
   and state writes are proven.
