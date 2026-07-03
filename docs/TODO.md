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
  Holiday Ornaments collection art/native table/achievement records, the B77
  Playhouse child-only autonomous candidate max-age gate, the B78 VF3 TV
  frame enum-order swap, and the B81 VF3 TV fmap/LoadFmap recognition fix
  without distributing a premodified EXE.
- When exporting offline patcher manifests, feed the generated build manifest
  through `validate_vf3_tv_animation_contract()` and
  `validate_vf3_tv_behavior_contract()` or equivalent release validation steps
  so malformed VF3 TV east/west frame enum assignments and missing TV fmaps are
  rejected before publication.
- Make antivirus false-positive reduction the top packaging priority. Prefer
  transparent patching and reproducible build artifacts over packed/obfuscated
  executables, preserve normal PE metadata where possible, sign the patcher and
  produced executable with a valid code-signing certificate, publish hashes, and
  maintain a McAfee/SmartScreen/AV vendor false-positive submission process for
  release builds.
- Before each release ZIP upload, verify the archive contains the EXE, `Images`
  payloads, the six required top-level runtime DLLs (`SDL2.dll`,
  `SDL2_image.dll`, `libpng16-16.dll`, `libjpeg-9.dll`, `zlib1.dll`,
  `fmod.dll`), and the `Microsoft.VC90.CRT/` private assembly folder required
  by the packaged `SDL2_image.dll`.

## Research Leads

- In-game test B76 Holiday Ornaments Collection: verify yard spawns for all 12
  ornaments at stock collectible cadence, verify Lucky Rock affects frequency
  and rarity through the stock spawn path, verify the Collections page
  background/icons/count/scrolling, verify `Ornamentologist` appears and
  completes after 12 unique ornaments, verify Goal Collector includes the new
  goal, and verify save/load persistence.
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
- In-game test B81 VF3 TV recognition: drop villagers on the Large, Small, and
  Father's Favorite VF3 TVs and verify they start the normal TV behavior
  instead of saying "There's no TV"; also verify base TVs still behave
  normally and the release folder contains `Assets/TVFlatScreenStd.png.fmap`
  plus the three generated VF3 TV fmaps.
- Launch-test B82 runtime package: verify the extracted release starts from a
  clean folder with only bundled files, including the `Microsoft.VC90.CRT/`
  private assembly; then re-run the B81 VF3 TV recognition checks.
- In-game test B75 Clothing/outfit behavior: verify opening the Clothing
  section no longer crashes, all generated outfit rows display their
  last-action-frame icons, female rows apply only to female villagers, male rows
  apply only to male villagers, buying multiple generated outfits keeps each
  toolbar item independent, and body values `50-53` apply without
  save-load/detail/house-view crashes.
- In-game test B80 Holiday outfit body-value fix: verify Holiday outfit store
  items `0x432-0x435` and `0x472-0x475` apply villager body values `50-53`
  instead of `49`, and verify a deliberately invalid saved body value falls
  back safely instead of crashing.
- In-game test B74 Settings Evict button: in generation 1 and a later
  generation, open Settings, press Evict, verify the existing
  confirmation/removal flow removes all current family members, returns to the
  adoption/new-person path, and remains stable across save-load.
- In-game test B67 visible Special Upgrade icons: verify Brokerage Account,
  Food Club, Health Plan, and Lucky Rock draw their icon graphics in the
  Special Upgrades list while purchase/apply behavior remains unchanged.
