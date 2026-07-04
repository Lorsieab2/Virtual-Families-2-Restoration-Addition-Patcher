# TODO

## Highest Priority

- Refactor the mod so releases stop distributing modified executables. Build an
  offline vanilla-to-modded VF2 PC patcher that takes a user-provided original
  VF2 executable, verifies the original EXE hash/version before patching,
  creates a backup, applies clean patch records from a JSON patch manifest, and
  writes a patch log. Initial byte-patch and asset-patch restore scaffolds exist
  in `work/offline_vf2_patcher.py`, including manifest-declared toggleable
  settings and a Tkinter GUI wrapper; next step is converting the current VF2
  build's native byte changes and generated payload assets into release
  manifests.
- Define the JSON patch manifest contract: each patch record must include file
  path, offset, expected original bytes, replacement bytes, and note. The
  patcher must refuse to patch when expected bytes do not match, and it must
  provide a restore option that can put the backed-up original files back.
- Keep the offline patcher simple and trust-friendly: avoid runtime injection,
  process memory editing, obfuscation, packers, and admin requirements. Prefer
  data, asset, and table patches over executable patches whenever possible.
- Build the first full current-build offline patch bundle: include the scaled VF3 TV
  animation strips as `asset_patches`, then add the verified native byte records
  required to append the VF3 furniture, private floating-animation table
  entries, gendered outfit icon descriptors, Holiday outfit runtime-frame
  descriptors/payloads, the B75 independent synthetic outfit ToolTray
  normalization patches, the six copied stock villager sprite sheets under
  `Images/`, visible Special Upgrade icon descriptors/payloads, and the B76
  Holiday Ornaments collection art/native table/observer/achievement records,
  the B77 Playhouse child-only autonomous candidate max-age gate, the B78 VF3
  TV frame enum-order swap, the B81 VF3 TV fmap/LoadFmap recognition fix, the
  B93 split ToolTray hand/use synthetic outfit state, generated-frame Holiday
  body source priority, and the B96 final outfit apply resolver without
  distributing a premodified EXE.
- Extract native patch records from object/linker patch data for the offline
  bundle. The workspace-local vanilla EXE candidate has SHA-256
  `67e8cf073be89b9699f4f7a19bc1105ceae865cdaefe98abd0c1e59e5f0d6bc4` and size
  `1,881,088`, while B93's patched EXE is `1,677,824` bytes; full binary diff
  export is therefore invalid for B93.
- When exporting offline patcher manifests, feed the generated build manifest
  through `validate_vf3_tv_animation_contract()` and
  `validate_vf3_tv_behavior_contract()` or equivalent release validation steps
  so malformed VF3 TV east/west frame enum assignments and missing TV fmaps are
  rejected before publication.
- Include `runtime_requirements` in current-build offline patch manifests so
  the patcher verifies the user selected a complete vanilla VF2 folder with
  `Images/`, `Sounds/`, `ldw.ini`, `wc.dat`, and key base art before applying
  byte or asset patches.
- Make antivirus false-positive reduction the top packaging priority. Prefer
  transparent patching and reproducible build artifacts over packed/obfuscated
  executables, preserve normal PE metadata where possible, sign the patcher and
  produced executable with a valid code-signing certificate, publish hashes, and
  maintain a McAfee/SmartScreen/AV vendor false-positive submission process for
  release builds.
- Install or renew a real Authenticode Code Signing certificate before the next
  signed release. On 2026-07-03, the local private-key certs were either
  Server Authentication only or rejected by signtool, so B83/B84/B92 could not be
  signed locally.
- Before each release ZIP upload, verify the archive contains the EXE, the full
  official B93 top-level folder shape: `Assets/`, `Images/`,
  `OptionalVisualMods/`, `Original Virtual Families 2 Assets/`, `Sounds/`,
  `ldw.ini`, `wc.dat`, `icon.bmp`, the six required top-level runtime DLLs
  (`SDL2.dll`, `SDL2_image.dll`, `libpng16-16.dll`, `libjpeg-9.dll`,
  `zlib1.dll`, `fmod.dll`), and no legacy `ReferenceAssets/` or
  `Microsoft.VC90.CRT/` folders.
- Keep using `work/vanilla_runtime_payload` as the canonical clean base asset
  seed for future builds, but package shape comes from the fixed official B93
  release ZIP. New builds should seed from the most recent previous completed
  B-build first, then overlay this clean asset payload and regenerated
  additive changes.

## Research Leads

- Use `docs/mobile-vf2-feature-analysis.md` as the current coding-level map for
  mobile-only features. Fill remaining low-level gaps from mobile disassembly
  instead of inferring behavior from PC store rows or screenshots alone.
- Disassemble mobile Holiday behavior methods:
  `CBehavior::AdmiringXmasTree`, `AdultWaterXMasTree`,
  `InteractHouseXmasDecor`, `KidsCheckXmasStockings`,
  `EachPeepCelebrateXMasTree`, `AdmiringXmasKnickKnacks`,
  `AdultsSaveSantasCookies`, and `KidStealsSantasCookies`. Record object IDs,
  required `CHotSpot` routes, carried items, animation IDs, sounds, and
  achievement/goal hooks.
- Disassemble all added mobile `CEvent*::ImpactGame` methods and map exact
  outcomes before marking exclusive Island Events complete. The current PC
  event shell list preserves firing/dialog structure, but most mobile reward,
  penalty, spawn, pet, and villager-state effects are still unmapped.
- Confirm mobile special-upgrade save fields and effect math for Brokerage
  Account, Food Club, Health Plan, and Lucky Rock. Lucky Rock especially needs
  exact `CCollectableItem::Update/Add` odds arithmetic before the new Holiday
  Ornament collection can be considered parity-complete.
- Extend offline patcher feature toggles around the report's feature groups:
  Holiday outfits, Holiday furniture, mobile furniture/behavior routes, Holiday
  Ornaments, Island Events/outcomes, visible mobile purchases, and VF3 TV
  assets/recognition.
- Translate B93 `settings_menu.evict.constructor_patches` from object/function-
  relative offsets into final vanilla EXE file offsets before moving them from
  `native_patch_sources` into applyable offline patcher `patches[]` records.
- In-game test B92 Holiday Ornaments: open Collections, verify six pages/72
  collectibles with the Ornaments page last, confirm yard ornaments can be
  picked up and removed, confirm collection counts and the Ornamentologist goal
  advance, verify Lucky Rock odds still affect the new collection through the
  stock `CCollectableItem::Update/Add` path, and verify save/load persistence.
  Static mobile comparison now confirms row `0x5F` target `12`, Goal Collector
  target `13`, rarity ranges, and the four full-yard `0x9E` spawn rectangles.
- In-game test B77 Playhouse spontaneous behavior: verify children can still
  spontaneously use the Playhouse, adults do not select Playhouse
  spontaneously, and manual furniture/drop behavior remains unchanged.
- Add an optional setting for mobile-exclusive furniture behavior support on
  added mobile-exclusive furniture in the PC build, then implement the correct
  villager behavior routes for those furniture items.
- Implement the correct outcomes for added mobile-exclusive Island Events.
  Current added events can fire but do not yet perform their mobile outcomes.
- Allow the second bathroom to have water leaks like the first bathroom; the
  current first-bathroom-only leak behavior is an inconsistency.
- Allow the Kitchen, Workshop, and Office to be renovated with their exclusive
  mobile renovation variants.
- Make all house renovations and upgrades removable and purchasable again after
  removal.
- Continue B63 in-game validation after the confirmed save-load crash fix:
  click normal gameplay/furniture UI, open General Appliances, place the VF3
  TVs, and verify base TV behavior is unchanged.
- Rebuild debugger support as an isolated opt-in/dev-only path. Do not patch
  main-scene mouse handlers in normal builds; first prove a key/display-only
  debugger path can load saves and run without crashes.
- Audit other category list count patches for small/common desktop counts before
  adding more furniture entries.
- In-game test B78 VF3 TV private floating-animation entries: verify both
  east/west orientations for the Large, Small, and Father's Favorite TV
  overlays are parallel to their screen faces, fill those faces, and leave
  base TV click/animation behavior untouched.
- In-game test B88 VF3 TV animation box revert: verify Large, Small, and
  Father's Favorite overlays are back to the B84-sized private strip boxes and
  are less misaligned than B85/B87, then decide whether the remaining minor
  alignment needs source-art edits instead of another box inset.
- In-game test B81 VF3 TV recognition: drop villagers on the Large, Small, and
  Father's Favorite VF3 TVs and verify they start the normal TV behavior
  instead of saying "There's no TV"; also verify base TVs still behave
  normally and the release folder contains `Assets/TVFlatScreenStd.png.fmap`
  plus the three generated VF3 TV fmaps.
- Launch-test post-B93 runtime packages: verify the extracted release starts
  from a clean folder with the fixed B93 top-level folder/file shape; then
  re-run the B81 VF3 TV recognition checks.
- In-game test B93 Clothing/outfit behavior: verify opening the Clothing
  section no longer crashes, all generated outfit rows display their
  last-action-frame icons, female rows apply only to female villagers, male rows
  apply only to male villagers, buying multiple generated outfits keeps each
  toolbar item independent, and body values `50-53` apply without
  save-load/detail/house-view crashes.
- In-game test B93 Holiday outfit body-value fix: verify Holiday outfit store
  items `0x432-0x435` and `0x472-0x475` apply villager body values `50-53`
  instead of `49`; test both drop/apply paths so `GetToolInHand` and
  `GetToolInUse` keep their selected synthetic IDs until `GetOutfit(0x49/0x4A)`
  resolves the body. Also verify a deliberately invalid saved body value falls
  back safely instead of crashing.
- In-game test B94 stability/outfit gates: load an existing save and leave the
  game running for several minutes to confirm the delayed crash is gone with
  mobile Island Events and Holiday Ornaments disabled by default; then verify
  Holiday outfit items `50-53` still apply as those body values instead of
  falling back to `49`.
- In-game test B95 Holiday outfit field sync: buy at least two generated
  outfits of the same gender, then apply an older toolbar item and a Holiday
  toolbar item. Verify the selected item controls the villager body value and
  Holiday rows `50-53` no longer collapse to `49`.
- In-game test B96 Holiday outfit final apply resolver: buy Holiday outfit
  bodies `50-53` for both genders, verify the correct synthetic outfit appears
  in the tray, drop it on a matching villager, and confirm
  `CVillager+0x6A84` becomes the selected body value rather than `49`.
  Also re-test at least one base male and female outfit to confirm vanilla
  outfit application remains unchanged.
- Continue Holiday Ornament implementation under the isolated
  `VF2_ENABLE_HOLIDAY_ORNAMENTS=1` path: compare the mobile collection table,
  page routing, pickup observer registration, `CollectionCount`, save fields,
  ornament goals, and Lucky Rock rarity math before enabling the collection in
  normal builds again.
- Continue Island Event outcome work under the isolated
  `VF2_ENABLE_ISLAND_EVENTS=1` path: map each mobile `ImpactGame` side effect
  before restoring event table grafts in normal builds.
- In-game test B89 Holiday body link fallback: apply each Holiday outfit to
  male and female adults, then check house view, detail screen, action poses,
  and sitting poses for head/body attachment; this specifically verifies the
  stock row-49 link fallback after removing the B80 link-row widening.
- In-game test B74 Settings Evict button: in generation 1 and a later
  generation, open Settings, press Evict, verify the existing
  confirmation/removal flow removes all current family members, returns to the
  adoption/new-person path, and remains stable across save-load.
- In-game test B67 visible Special Upgrade icons: verify Brokerage Account,
  Food Club, Health Plan, and Lucky Rock draw their icon graphics in the
  Special Upgrades list while purchase/apply behavior remains unchanged.
