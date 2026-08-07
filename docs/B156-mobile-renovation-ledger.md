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

The default-off patch build stages these files under
`OptionalVisualMods/Mobile Renovations` and records the exact source/target
list in its build manifest. When the optional mobile-renovations toggle is
enabled, the same files are copied into `Images/MobileRenovations` and linked
through the B157 post-map overlay renderer. The optional Bathroom 2 plan
remains to reuse the corrected Bathroom 1 files only after a native
second-bathroom render route is verified.

The bundle-level extraction record is tracked in
`data/vf2/mobile-renovation-atlas-contract.json`. It records the eight mobile
texture bundles that supplied the 15 staged room overlays, the extracted
bathroom support textures that are intentionally not staged, and the current
runtime-copy/selector boundary. It now also pins the ten native activation
records and the mobile save-load order used by the static PC parity validator.
The enabled and disabled renderer states are separately recorded in each
generated build manifest; live visual selection still requires player QA.

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
Bathroom 2 art selection; the Cheat Upgrades removal route is source-validated
separately and still needs live QA.

## B157 room-overlay route

The optional renderer registers the 15 mobile styles as PC store items
`0x13C-0x14A`, retaining the mobile price and unlock-level records. They are
appended only to the native House Renovations category (`0x11`,
`gHomeList`/`gHomeListSorted`), expanding it from 10 to 25 rows; they are not
added to Special Upgrades (`gServicesList`). The purchase/activation helper
uses the PC inventory path, and the renderer selects
the first active style in native mobile item order in each room group. Active
style state remains exclusive per room in the PC inventory bytes, while a
separate persisted purchase mask keeps previously bought styles free to
reactivate, matching mobile `TakeOne`/`HaveUpgrade`/`GetPrice` semantics. It
draws the complete source PNG at
1:1 using these camera-relative world anchors:

| Room | Anchor | Variants |
| --- | --- | --- |
| Bathroom | `(535,1263)` | 5 |
| Kitchen | `(930,995)` | 3 |
| Office | `(1357,792)` | 5 |
| Workshop | `(900,1475)` | 2 |

The hook is `theMainScene::DrawScene +0x39`, after `CWorldMap::Draw` and before
stock decals. The disabled build has no hook and does not copy these PNGs into
the runtime image tree. Static contract validation and compilation/linking
pass; player visual QA is still required.

The reproducible enabled overlay build is driven by
`work/build_b157_mobile_renovations.ps1`. It starts from the B156 core output,
sets only `VF2_ENABLE_MOBILE_RENOVATIONS=1`, refuses to overwrite an existing
destination, validates the 15-image manifest, and compiles/links the optional
EXE separately from the existing 16-state B156 matrix.

## Remaining native work

1. Verify the B157 overlay visually in-game against the staged mobile atlases,
   including camera movement and the selected-room boundaries.
2. Live-verify style purchase, switching/free reactivation, and
   save/load behavior against the mobile inventory semantics. The source route
   rebuilds `CContentMap` from the native ten-record table and is guarded by
   the Cheat Upgrades overlay; no generic renderer reset is used.
3. Add Bathroom 2 as a separate optional route only after its overlay anchor
   and state writes are proven.
