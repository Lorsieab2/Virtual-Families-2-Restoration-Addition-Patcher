# TODO

## Highest Priority

- Refactor the mod so releases stop distributing modified executables. Build an
  offline vanilla-to-modded VF2 PC patcher that takes a user-provided original
  VF2 executable, verifies the original EXE hash/version before patching,
  creates a backup, applies clean patch records from a JSON patch manifest, and
  writes a patch log. Initial byte-patch and asset-patch restore scaffolds exist
  in `work/offline_vf2_patcher.py`, including manifest-declared toggleable
  settings, `--exe` input, full-payload beta-folder export, and a Tkinter GUI
  wrapper. B103 has a full-payload test bundle that validates and backs up a
  vanilla `Virtual Families 2.exe` by exact SHA-256 or matching PE section
  structure, then creates a separate `VF2-B103-Modded` output folder with a
  clearly named modded EXE and recreated B103 support folder shape. Next step
  is converting the current VF2 build's native byte changes into clean release
  byte/table records so the patch bundle no longer needs a prebuilt modded EXE
  payload.
- Define the JSON patch manifest contract: each patch record must include file
  path, offset, expected original bytes, replacement bytes, and note. The
  patcher must refuse to patch when expected bytes do not match, and it must
  provide a restore option that can put the backed-up original files back.
- Keep the offline patcher simple and trust-friendly: avoid runtime injection,
  process memory editing, obfuscation, packers, and admin requirements. Prefer
  data, asset, and table patches over executable patches whenever possible.
- Convert the B103 full-payload test bundle into the final no-modified-EXE
  patcher: keep the scaled VF3 TV strips and generated assets as
  `asset_patches`, then add verified native byte/table records required to
  append furniture, Outfit rows/icons, visible Special Upgrades, Settings
  Evict, Invisible Hammock parity, ToolTray synthetic outfit handling, Holiday
  body runtime rendering, and other implemented fixes without distributing a
  premodified EXE.
- Split the current full `core_executable` payload into per-feature native
  patch records so unchecked native settings revert completely too. The B103
  patcher now gates optional assets and visual swaps cleanly, but native
  gameplay/code changes remain bundled together until their object/linker
  patches are translated into separate vanilla EXE byte/table records.
- Use the final cleaned `B98-current-vf2-modded-build` release ZIP as the
  source of truth for future package baselines. It supersedes the older local
  B98 extraction that contained only 29 of the generator's 111 additive
  `Images/Furniture` sprite paths.
- Extract native patch records from object/linker patch data for the offline
  bundle. The active B103 manifest targets the vanilla EXE fingerprint
  originally captured from the user-provided VF2 executable: size `1,511,424`,
  SHA-256
  `1582d9e84e1c32f51475be17335c5137c592cebf809748d401ccef99a32b73c3`, with a
  five-section PE32 structure fingerprint. The older workspace-local vanilla
  EXE candidate has SHA-256
  `67e8cf073be89b9699f4f7a19bc1105ceae865cdaefe98abd0c1e59e5f0d6bc4` and size
  `1,881,088`; full binary diff export is invalid across mismatched EXE
  structures.
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
  current B98 top-level folder shape: `Assets/`, `Images/`,
  `OptionalVisualMods/`, `Original Virtual Families 2 Assets/`, `Sounds/`,
  `ldw.ini`, `wc.dat`, `icon.bmp`, the six required top-level runtime DLLs
  (`SDL2.dll`, `SDL2_image.dll`, `libpng16-16.dll`, `libjpeg-9.dll`,
  `zlib1.dll`, `fmod.dll`), and no legacy `ReferenceAssets/` or
  `Microsoft.VC90.CRT/` folders.
- Keep using `work/vanilla_runtime_payload` as the canonical clean base asset
  seed for source-side generation, but release package shape and final runtime
  payload come from the final cleaned standalone
  `B98-current-vf2-modded-build` ZIP. New releases should use that exact B98
  folder structure, rename the folder shortly, and replace only the packaged
  EXE with the newest build EXE.

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
- In-game test B97 outfit apply stability: buy and apply several generated
  Outfit-section items for both genders, including Holiday rows `50-53`, and
  confirm the stock drop/apply path no longer crashes while the selected item
  still controls `CVillager+0x6A84` instead of collapsing to body `49`.
- In-game test B98 generated outfit strings: scroll the male generated Outfit
  rows past body `03` and verify every base and Holiday male row has its title
  and description instead of `Unknown String Id!!!!`; spot-check female rows
  remain unchanged.
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
- In-game test B99 Settings Evict button: in generation 1 and a later
  generation, open Settings, press Evict, verify the existing mobile-style
  confirmation/removal flow removes all current family members, returns to the
  adoption/new-person path, and remains stable across save-load. Confirm the
  button is not shown after the family tree has already been cleared.
- In-game test B102 Invisible Hammock parity: buy/place the base Hammock and
  Invisible Hammock separately, drop villagers on each, and verify both use the
  same native hammock drop behavior without crashes. Confirm the widened
  `CHotSpot::Hammock` in-world gate accepts item `0x30C` while the downstream
  base behavior remains `eBehavior_LieInHammockNoLeadIn (0x24)`.
- In-game test B103 Invisible Heart-Shaped Bed: buy/place item `0x327`, verify
  it appears as an invisible Bedroom item, and confirm villager drop/click
  behavior matches the base Heart-Shaped Bed donor `0x252`. Also verify
  `InvisibleAdultDoubleBed` still behaves like the Brown Adult Bed donor
  `0x1B7`.
- Patcher in-game/file-layout test B103 optional gates: run the generated
  patcher with Invisible Furniture visible graphics off, transparent invisible
  furniture off, custom map images off, and all transparent UI swaps off; verify
  the fresh modded output folder does not contain those optional payloads or
  replacements. Then enable each option individually and confirm only the
  expected files appear/change.
- Patcher file-layout test B104 reversible toggles: run the generated patcher,
  enable OptionalSongMods and loose OptionalVisualMods, then uncheck them and
  click Enable/Disable Patches again. Confirm the existing `VF2-B104-Modded`
  folder is refreshed from vanilla, `Sounds/menu.ogg` and `song1-4.ogg` return
  to vanilla, source-only payload folders are not copied wholesale into the
  game, and the JSON log lists enabled/disabled settings with `status:
  success`.
- Patcher release test B105 native/launcher parity: export with
  `--include-byte-patches`, confirm the ZIP contains `Launch_GUI.bat` but no
  `Launch GUI.lnk`, no `launch_gui_shortcut.json`, and no prebuilt modded game
  EXE payload; dry-run/apply against an official install copy, then verify the
  output folder contains `Virtual Families 2 - Modded B105.exe` only and the
  patch log save folder is `Documents/LDW/Virtual Families 2 - Modded B105`.
- Patcher file-layout test B106 optional payloads: verify the generated ZIP is
  self-contained; `white_birds` applies bundled `bird.png`/`bird_shadow.png`,
  transparent Invisible Furniture applies bundled `InvisibleMantleFireplace.png`
  and `InvisibleGrandfatherClock.png`, and `optional_song_mods` is absent unless
  real `payload/OptionalSongMods/*.ogg` files are bundled.
- Patcher file-layout test B107 optional songs: verify the generated ZIP
  includes `payload/OptionalSongMods/menu.ogg` and `song1-4.ogg`, enabling the
  option copies those files to `Sounds/`, and unchecking it plus clicking
  Enable/Disable Patches refreshes the modded folder back to vanilla songs.
- Convert the Store Scroll Bar native `CScrollingStoreScene` draw/mouse hooks
  into setting-gated byte/table records. B110 exposes the default-off setting
  and gates any scroll-bar assets, but current native support still comes from
  the core modded executable payload.
- Patcher file-layout test B110 Invisible Upgrades: enable
  `invisible_upgrades_graphics` and confirm bundled
  `payload/OptionalVisualMods/Invisible Upgrades/*.png` replace
  `Images/Upgrades/*.png`; then uncheck it and click Enable/Disable Patches to
  verify the modded folder refreshes back to vanilla upgrade graphics.
- In-game test B110 VF3 TV patch dependency: enable `vf3_tv_assets_recognition`
  with `core_executable` on and confirm VF3 TV private animation strips animate;
  confirm disabling `core_executable` leaves VF3 TV asset records inactive
  rather than copying unusable animation assets.
- Patcher file-layout test B111 VF3 TV frames: enable
  `vf3_tv_assets_recognition` without the broad `mobile_furniture` setting and
  confirm `Images/VF3TVAnimations/*/Frame*.png` are still copied, because the
  renderer depends on those private frame folders.
- Patcher file-layout test B111 output-only reconfiguration: run the GUI with
  only an existing `VF2-*-Modded` output folder selected, toggle a visual patch,
  click Enable/Disable Patches, and confirm bundled `restore_source_path`
  assets revert unchecked patches without requiring a vanilla folder.
- Patcher in-game smoke B111: extract
  `Virtual-Families-2-Restoration-Addition-Patcher-B111.zip`, run
  `Launch_GUI.bat`, Dry Run a user-selected vanilla VF2 folder, then apply with
  Main patches enabled and confirm the modded folder contains
  `Virtual Families 2 - Modded B111.exe`, VF3 TV animations, Holiday Details
  body files, generation lock icons, and no dependency on creator-local paths.
- Patcher in-game smoke B112: extract
  `Virtual-Families-2-Restoration-Addition-Patcher-B112.zip`, run
  `Launch_GUI.bat`, Dry Run a user-selected vanilla VF2 folder, then apply with
  Main patches enabled. Confirm VF3 TV animations show when clicked, lock
  icons 10-30 render with their matching numbered art, and the 39 newly locked
  added mobile/Holiday records appear in generation-lock groups of 3 items.
- In-game Holiday Body B112 audit: apply Holiday Outfit bodies 50-53 to male
  and female villagers, then verify walking/actions/sit frames stay aligned
  without resized pixels. Check Details screen body rows separately.
- In-game Holiday Body B113 audit: apply Holiday Outfit bodies 50-53 to adult
  and child male/female villagers, then verify Details-screen and main-scene
  bodies use the correct scaled offsets without resizing the source art.
- Patcher in-game smoke B114: enable Add Invisible Furniture - Visible
  Graphics and confirm Invisible Full-Size Pool, Invisible Kiddie Pool, and
  Invisible Hammock can be placed with visible base-game graphics. Then enable
  Swap Invisible Furniture Graphics with Transparent Graphics and confirm those
  same items become transparent without requiring any outside asset folders.
- In-game Holiday Body B114 audit: apply Holiday Outfit bodies 50-53 to child
  male/female villagers and verify main-world body/head alignment. Re-check
  Details screen only as a regression because the B114 fix targets main-scene
  `scale, alpha` handling.
- Patcher smoke B115 output refresh: select both a vanilla install folder and
  an existing modded output folder, uncheck only
  `invisible_furniture_transparent_graphics`, click Enable/Disable Patches, and
  confirm the modded EXE remains present after the refresh.
- In-game spontaneous behavior B116: with a Kids Table and Chairs present,
  confirm children can spontaneously choose "Playing quietly" and adults do
  not. Repeat with only Invisible Kids Table and Chairs present to verify the
  donor-cloned invisible item uses the base Kids Table behavior route.
- In-game spontaneous behavior B117: verify children can still spontaneously
  choose "Playhouse!" during daytime, but not when the in-game clock is in a
  nighttime state. Also confirm adults still never choose it spontaneously.
- Future patcher builds: properly implement the Settings Evict button path.
  With the current experimental patch enabled, the button still does not appear
  in Settings.
- Future patcher builds: implement mobile-exclusive Island Events so they have
  real outcomes instead of only shell/event records.
- Future patcher builds: implement the Holiday Ornaments collection without
  collection-screen crashes, including proper collectible pickup/spawn behavior,
  related Goals, and Island Event wiring.
- Future patcher builds: implement mobile-exclusive villager behaviors for the
  added furniture beyond the currently confirmed behavior patches.
- In-game test B106 generation locks: with a fresh save before later
  generations, verify added furniture respects the preserved mobile
  `lock_generation` values rather than appearing fully unlocked by default.
- In-game test B107 base generation locks: on a fresh generation-1 save, confirm
  stock PC furniture that normally unlocks in later generations remains locked,
  proving the appended mobile/custom records did not alter base `itemInfo`
  generation fields.
- Patcher follow-up: split remaining native store-table rows for Custom Couches
  and LDW Posters/Paintings into setting-gated byte/table patch records. The
  current `custom_couches_ldw_posters` setting gates image/fmap payload files,
  but full-bundle native store support still comes from the verified modded EXE
  payload.
- Standalone patcher repo follow-up: keep patcher-only release ZIPs under the
  private `Virtual-Families-2-Addition-Restoration-Patcher` GitHub repo, and
  keep the GUI `Check for updates` link pointed at that repo's Releases page.
- Settings Evict B118 validation: open Settings on a generation 1 and a later
  generation save, confirm the Evict button appears, then click it and verify
  the native confirmation/adoption reset path runs without crashing.
- Settings Evict research follow-up: fully resolve the mobile PLT/control-ID
  mapping for `theOptionsDialog::HandleMessage` so the first-generation mobile
  confirmation click can be documented down to the exact button ID as well as
  the already-confirmed native `EvictFamily` handler path.
- In-game test B67 visible Special Upgrade icons: verify Brokerage Account,
  Food Club, Health Plan, and Lucky Rock draw their icon graphics in the
  Special Upgrades list while purchase/apply behavior remains unchanged.
- Island Events patcher bug: enabling the experimental Island Events setting
  does not currently add the mobile-exclusive event records to the game. Audit
  whether the event table/native records are only present in the core EXE
  payload or missing from the generated patch records entirely.
- In-game test B125 hammock spontaneous behavior alignment/eligibility: verify
  villagers can spontaneously choose Relax in Hammock when either base
  `HammockStd` (`0x1E1`) or `InvisibleHammock` (`0x30C`) is placed, use the
  linked hammock point, choose the matching `SleepNW`/`SleepNE` strip for the
  placed hammock orientation, close their eyes/rest for a while, and do not lie
  beside the hammock on either orientation.
- In-game test B128 radio/MP3 behavior parity: when adults or children are
  dropped on base radio, MP3 player, or invisible inherited radio/MP3 items,
  confirm they randomly choose between "Dancing" and "Listening to the Radio".
  With Behavior Patches enabled, confirm spontaneous radio behavior also chooses
  from the same randomized behavior pool.
- In-game test B127 patcher apply path: with all main and optional settings
  enabled, confirm generated additive files such as `Assets/*.fmap`, VF3 TV
  animation strips, and Cheat Upgrades payloads are created in the modded
  output folder and no longer fail as missing vanilla targets.
- In-game visual test B129: verify Father's Favorite TV uses the smaller
  two-frame sprite, its private TV animation is generated from the bundled VF3
  strip frames and fits inside the brown screen border, Cheat Upgrade icons fit
  the Special Upgrades icon column, the optional song patch swaps/restores OGGs,
  and the HUD status reads "Not feeling clean".
- In-game test B129 expanded Outfit Store patcher payload: after applying the
  patcher to a vanilla install, confirm all female and male generated Outfit
  rows 0-53 have preview icons, including Holiday body values 50-53.
- In-game test B129 behavior labels: with Behavior Patches enabled, verify
  Pachinko Machine and Pinball Machine actions show "Playing pachinko" and
  "Playing pinball" instead of the shared "Playing" label.
- In-game visual test B130 VF3 TV animation payloads: apply the B130 patcher
  with `vf3_tv_assets_recognition` enabled and confirm the Large VF3 Flat
  Screen TV uses the bundled `FlatScreenVF3Big*.png` strip frames directly.
  Also confirm Father's Favorite TV uses the same split supplied frames scaled
  to its smaller furniture canvas, with no stale B129/bounded-compositor strip
  visible in-game.
- In-game behavior test B131: enable Behavior Patches and confirm TV, radio,
  web, video game, reading, petting, mending, ironing, telescope, workout,
  career, shower/bath, coffee/tea, cocktail, pool, sandbox, toy train,
  playground, and snow-play label variants display correctly while preserving
  the native animation/targeting route.
- In-game behavior test B131: confirm Drawing is no longer selected by adults,
  but still appears for children/teenagers if the stock non-adult threshold
  `CVillager+0x6A54 < 0x118` covers both groups.
- In-game behavior test B131: while snow weather is active, confirm children
  and teenagers can spontaneously choose Playing in Snow variants. If enum
  `Weather.currentType == 5` is wrong, re-map weather enums from live state.
- In-game Cheat Upgrades test B131: buy `Unlock all furniture` and confirm
  generation locks disappear from stock and added furniture; buy it again and
  confirm the generated original lock table is restored without corrupting
  store rows.
- Research: document the exact teen/adult boundary separately from the proven
  adult boundary, then decide whether teen+adult web/social variants should
  use a broader gate than the current adult-only wrappers.
- Research: implement nursing-mother infant-care variants and the requested
  shared infant-care handoff only after documenting the baby/babyplets fields
  and native partner-wait plan route. Native baby-related behavior IDs are now
  known: `TeachingFirstWords` (`0x11F`), `WashBaby` (`0x181`), `ChangeBaby`
  (`0x182`), `MomTeachingTalk` (`0x18F`), plus `ShowingBabyGarden`,
  `ShowingBabyToys`, `CelebratingBaby`, `JealousAboutBaby`,
  `ExcitedAboutBaby`, and `PlayingMommy`.
- Research: re-enable second-bathroom north leak reactions. Native behavior
  constructors exist for `FreakOutShowerLeakNorth` (`0x135`) and
  `FreakOutToiletLeakNorth` (`0x137`); `FreakOutBathroomSinkLeak` (`0x133`)
  exists but a distinct `BathroomSinkLeakNorth` behavior symbol has not been
  proven yet. Also inspect `CEventTheWaterPressureSurge::ImpactGame` and the
  faucet-outcome writes before patching second-bathroom leak spawning.
- Research: `expand_game_map` is exposed as experimental/not implemented in
  the patcher setting list. Implement only after mapping map-tile bounds,
  content/collision fmaps, camera clamps, and save references.
