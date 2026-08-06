# TODO

The cross-build completeness source is docs/REQUEST_LEDGER.md. Before a
release, reconcile it against this file, build history, source settings/hooks,
tests, release notes, and the exported payload. An uncertain historical request
must remain visible as Needs source audit; it must not be silently omitted.

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
- Continue routing the now-disassembled mobile Holiday methods to exact
  furniture items. `KidExaminesCandles`, `AdmiringXmasTree`,
  `AdultWaterXMasTree`, `InteractHouseXmasDecor`, `KidsCheckXmasStockings`,
  `AdmiringXmasKnickKnacks`, `AdultsSaveSantasCookies`, and
  `KidStealsSantasCookies` have code-level plans and object IDs recorded.
  Holiday Candles and the Plate of Cookies child/adult pair are implemented
  manually. Exact QAMF object bits now prove and enable ten
  `AdmiringXmasKnickKnacks` figurines and four adult
  `InteractHouseXmasDecor` wall/garland items. Eggnog now has its exact
  child-only manual `Eggnog` plan and EObject `0x8B` map. The remaining
  Candy Canes, Single Cookie, Poinsettia, and two Wreath maps are now proven
  decorative only: they decode to EObject `0`, their hotspots `0x60/0x61`
  have null mobile handlers, and the mobile drop dispatcher has no item-ID
  fallback. Do not invent behavior routes for them from their artwork names.
- [x] Disassemble all 25 added mobile `CEvent*` firing, award, and impact
  methods and map their exact outcomes. Live event and patch-off QA remains.
- [x] Confirm mobile special-upgrade save fields and effect math. Brokerage
  adds `0.02` to `CMoney+0x08`, whose serialized load caps at `0.11`. Food
  Club persists its active flag and delivery timestamp in its 16-byte save
  block, delivers 500 food immediately, and repeats every 86,400 game-time
  seconds. Health Plan divides medicine IDs `0x18-0x21` by four; mobile
  restores its runtime byte from purchase entitlement, so the desktop port
  now persists ownership in hidden achievement record `0xA8+0x08`, separate
  from the existing Taters/pregnancy/generation mask at record `+0x04`.
  Lucky Rock's exact `Update/Add` arithmetic remains byte-locked.
- Extend offline patcher feature toggles around the report's feature groups:
  Holiday outfits, Holiday furniture, mobile furniture/behavior routes, Holiday
  Ornaments, Island Events/outcomes, visible mobile purchases, and VF3 TV
  assets/recognition.
- Translate B93 `settings_menu.evict.constructor_patches` from object/function-
  relative offsets into final vanilla EXE file offsets before moving them from
  `native_patch_sources` into applyable offline patcher `patches[]` records.
- In-game test B149 Holiday Ornaments: open Collections, verify six pages/72
  collectibles with the Ornaments page last, confirm yard ornaments can be
  picked up and removed, confirm collection counts and the Ornamentologist goal
  advance, verify Lucky Rock odds still affect the new collection through the
  stock `CCollectableItem::Update/Add` path, verify ornaments still draw when
  `Glowing Collectibles` is enabled, and verify save/load persistence.
  Static mobile comparison now confirms row `0x5F` target `12`, Goal Collector
  target `13`, rarity ranges, the three exact mobile `0x9E` spawn rectangles
  (19 total registrations), and
  the small-sheet frame mapping `0x9E-0xA9 => 79-90`. B148 also proves the
  native collection-state/save/reset span, appended sixth-page table,
  page-count helper, pickup-dispatch hooks, observer registrations, tooltip
  buckets, and Mr. B sell-all `0x5F` reset before packaging the experimental
  overlay. B149 additionally proves `Activate()` still uses the five stock
  cached counters while `DrawScene()` routes page-count display through
  `_VF2CollectionPageCount(page)` with page `5 -> 0x9E`.
- In-game test B77 Playhouse spontaneous behavior: verify children can still
  spontaneously use the Playhouse, adults do not select Playhouse
  spontaneously, and manual furniture/drop behavior remains unchanged.
- Add an optional setting for mobile-exclusive furniture behavior support on
  added mobile-exclusive furniture in the PC build, then implement the correct
  villager behavior routes for those furniture items.
- [x] Implement function-level firing, award, and impact routes for all 25
  added mobile-exclusive Island Events. Eight exact mobile classes remain
  deliberately dummied out by `CanFire=false`; their unreachable methods are
  retained only where recovered. No generic firing rule remains for an added
  event.
- In-game test all 25 added mobile Island Events: verify dialog substitutions,
  reachable-event target gates, both choice outcomes, inventory/collectible/
  behavior/happiness/money/career effects, dummied-event nonappearance,
  persistence where applicable, and byte-identical patch-off behavior.
- In-game test B132 second-bathroom leaks: after buying the second-bathroom
  renovation, trigger Water Pressure Surge and confirm the north toilet,
  shower, and sink leaks appear and can be repaired through their native
  second-bathroom repair routes.
- Allow the Kitchen, Workshop, and Office to be renovated with their exclusive
  mobile renovation variants.
- [x] Add a default-off Cheat Upgrades route that removes owned native house
  renovations `0xE1-0xEA`, rebuilds the content map from the exact native load
  activation records, preserves other owned renovations, and saves. Live
  remove/rebuy/switch/save-load QA remains; mobile room-art compositing is a
  separate evidence-gated task.
- Continue B63 in-game validation after the confirmed save-load crash fix:
  click normal gameplay/furniture UI, open General Appliances, place the VF3
  TVs, and verify base TV behavior is unchanged.
- [x] Rebuild debugger support as an isolated opt-in/dev-only path with the
  main-scene debugger provider separate from the native IEditor globals.
- [x] Add guarded key-character and mouse down/move/up routes to the dormant
  developer build; disabled sessions fall through to stock handlers.
- [x] Pin all five native cleanup widths, inserted payloads, REL32 helper
  targets, and stock fallthrough bytes in regression tests.
- [x] Match the generated IEditor declaration to the nine-slot native vtable
  and pin the relocation order in tests.
- [x] Pin the main-scene IDebugger +8 base, CDebugger provider layout, and
  byte-identical default-off main-scene object in native regression tests.
- [x] Route printable editor commands only through HandleKeyCharacter; native
  object tests prove Light Source Editor key-down is a no-op and add/delete/save
  belong to the character handler.
- [x] Pin the native editor character maps before live testing: Light Source
  Editor `+`/`-`/`L`/`D`/`S`, and Waypoint Editor `W`/`S` (letter commands are
  case-insensitive).
- [x] Assemble a minimized, isolated B153 debugger live-test folder with the
  untouched B152 all-patches control, opt-in debugger executable, exact hashes,
  save-safety checklist, launchers, and results template.
- [x] Isolate the house-load crash in the first debugger test: Windows Error
  Reporting identified access violation `0xC0000005` at RVA `0xC5D4B`; the
  disabled JE used `+4` and entered the middle of the six-byte true-return
  sequence's `ret 8` immediate. Both generated hooks now use `+6`, which lands
  exactly at the stock body, and the corrected diagnostic passes the linked
  fallthrough validator.
- [ ] Live-retest the B153 debugger route. House loading now passes. The first
  safe build ignored F5 because it omitted VF2's internal key enum; B153 now
  recognizes F4 0x3FD, F5 0x3FE, F6 0x3FF, F7 0x400, Up 0x3EE, and
  Down 0x3EF in all 16 validated layouts. Visible selector, waypoint, light
  editor, input-fallthrough, and save-persistence QA remain.
  The Light Source Editor bridge now swaps printable `+`/`-` only while that
  editor is active to match the requested increase/decrease direction. B156
  now registers the proven offset-zero `CVillagerManager` debugger provider
  alongside the main-scene provider, so Up/Down have two real pages to cycle.
  Live page-switching and villager-field QA remain.
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
- Future patcher builds: continue mobile-exclusive Island Event outcome work.
  The optional Island Events patch can add event/dialog records, but most
  mobile reward, penalty, spawn, pet, and villager-state effects still need
  native side-effect mapping.
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
  private `Virtual-Families-2-Restoration-Addition-Patcher` GitHub repo, and
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
- In-game test B133 optional Island Events: enable the Optional Island Events
  patch and verify mobile-exclusive events plus mobile-only email events appear
  in-game. Continue auditing outcomes/effects before marking the Island Events
  work complete.
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
  but still appears for children. If teenagers should also draw, use the
  documented growth range between the child cutoff and mature-adult cutoff
  instead of the stock child-only `< 0x118` test.
- In-game behavior test B131: while snow weather is active, confirm children
  and teenagers can spontaneously choose Playing in Snow variants. If enum
  `Weather.currentType == 5` is wrong, re-map weather enums from live state.
- In-game Cheat Upgrades test B131: buy `Unlock all furniture` and confirm
  generation locks disappear from stock and added furniture; buy it again and
  confirm the generated original lock table is restored without corrupting
  store rows.
- Patcher smoke B136: extract the B136 patcher ZIP, run Dry Run with all Main
  and Optional patches enabled against a clean vanilla VF2 folder, then apply
  and confirm the combined Island Events + Cheat Upgrades EXE is selected when
  both optional overlays are enabled. In-game, re-check `Unlock all furniture`
  and the optional song restore path. Also confirm the official game EXE is not
  rejected as an "unexpected top-level entry" during folder-shape validation.
- In-game behavior test: after the next patcher/build export, verify label
  variants still choose the same animations after the helper-name cleanup
  (`VF2IsChild`, `VF2IsTeenOrOlder`, `VF2IsMatureAdult`).
- In-game behavior test B141: with Behavior Patches enabled, praise villagers
  while they are doing generated label variants and confirm the visible action
  string stays stable instead of rerolling. This specifically covers the new
  per-villager/per-wrapper label cache after native behavior start. Also verify
  the label-only variants for `Watching TV`, `Getting a drink`, `Heating up
  some food`, `Looking for snacks`, and `Preparing a meal` reuse the same
  native animations and targeting as their base actions.
- In-game behavior test B137: verify the newly wrapped native entries for
  board games, breakfast, flower watering, bathroom sink/grooming, kids table,
  teen homework/online test, sit-down/rest, and `Jumping on the trampoline`.
  These should display the new labels while preserving base routes and object
  targeting.
- B150 source work completed: raw age/gender/career gates are mapped for the
  requested sit-down, web, and jewelry pools, and TeachingFirstWords 0x11F now
  supplies the nursing-mother infant-care label pool. The remaining work is the
  manual in-game eligibility/animation verification listed below; do not widen
  any gate unless that runtime test demonstrates a native mismatch.
- Test: second-bathroom north leak support is patched through
  `CEventTheWaterPressureSurge::ImpactGame(int)` and
  `CVillager::NewBehavior`. Verify in-game that Water Pressure Surge sets the
  north toilet (`0x48`), north shower (`0x49`), and north sink (`0x4A`) leak
  visuals only after second-bathroom renovation (`0xE6`), and that
  `FixingNorthToilet` (`0x142`), `FixingNorthShower` (`0x140`), and
  `FixingNorthBRoomSink` (`0x04E`) clear them without crashes.
- Research: `expand_game_map` is exposed as experimental/not implemented in
  the patcher setting list. Implement only after mapping map-tile bounds,
  content/collision fmaps, camera clamps, and save references.
- Research: name the copied `CVillagerState` fields used by
  `CDailyEmail::Show` at stack offsets `-0x16854`, `-0x16858`, `-0x1683C`,
  and `-0x1692C`; current trigger notes identify them only by branch semantics.
- Research: trace `eString_EmailRepairHouse` outside `CDailyEmail::Show` to
  confirm whether it is unused, reserved, or reached through another object.
- In-game store test: open `On Sale` and confirm it still shows stock
  discounted furniture rows. Then open `Flea Market` and confirm it lists the
  fixed `0x24`-entry native `gGoodiesList` pool rather than only five random
  rows, with purchases still functioning.
- In-game Cheat Upgrades test B139: complete or partially progress a few goals,
  buy `Reset Achievements`, reopen the Goals screen, and confirm all completion
  and progress values are cleared and still cleared after saving/reopening.
- In-game behavior test B141: with Behavior Patches enabled, drop children and
  adults on stock showers, north showers, bathroom sinks, and grooming-capable
  bathroom objects. Confirm base-game eligibility/targeting is unchanged and
  variants only appear when the native behavior starts.
- In-game visual test B141: verify `No Money`, `No Food`, add-food/add-coin,
  `Unlock all furniture`, and `Reset Achievements` icons fit the Special
  Upgrades row and buy dialog without clipping or white canvases.
- In-game Holiday Ornaments test B146: enable the experimental Holiday
  Ornaments patch, collect ornaments, then trigger Mr. B/The Collector and
  choose `Sell`. Confirm the `0x9E-0xA9` collection flags clear and
  Ornamentologist achievement row `0x5F` resets. In B144+, confirm collected
  ornaments also contribute to Mr. B/The Collector's coin offer and can make
  the event available when the stock collectible families are empty. In B145+,
  click/hover each slot on the sixth Collections page and confirm the tooltip
  path does not crash or show garbage rarity text. In B146+, confirm spawned
  yard ornaments render with the expected icons from `collectables_small.png`
  frames `79-90`.
- Research: use the workspace-local `work/assets/TextAsset/` mirror as the
  source for future mobile furniture/map additions. Do not reference the
  original `Downloads\TextAsset` path in build or patcher code; copy any needed
  files from the workspace mirror into generated payloads.

## B150 Manual Runtime Verification

- Packaging complete: the B150 exporter retains only manifest-reachable
  payload sources. It removed 1,860 unreachable files (100,244,363 bytes),
  excluded three accidental `.pre-frame-pad.bak` records, and produced 1,075
  asset records referencing 1,112 payload files. Keep this reachability audit
  enabled for every future patcher build.

- Holiday Ornaments B150 hotfix: with only holiday_ornaments_collection enabled, click the
  Collections Chest repeatedly, navigate all six pages, and confirm the HUD
  total is 72 rather than 60. Click/hover every ornament slot; collect/save/load
  all 12 ornaments; verify Ornamentologist, Mr. B/The Collector sell/reset, yard
  sprites, and the five stock collections. Repeat with Holiday disabled to
  confirm the stock five-page/60-item screen. Specifically retest the no-hover
  path that previously branched into inserted bytes, picking an incomplete
  ornament collection, The Collector's Keep choice, and repeated completion
  calls for duplicate Goal Collector credit.
  The B152 upright-source refresh is automated and hash-verified; runtime QA
  should additionally confirm the 12 collected overlays appear upright over
  the matching baked placeholders on the 940x732 supplied frame.
- Overlay gating: exercise representative installs from the 16-state
  Island Events/Cheat Upgrades/Holiday Ornaments/Behavior Patches matrix.
  Confirm the manifest selects the one matching EXE and that a disabled feature
  has no native side effects. In particular, Behavior disabled must retain
  stock labels/candidates, and Cheat disabled must not make owned services or
  certificates removable.
- Behavior autonomy: under Behavior Patches, confirm all-age Checking weight and
  Needs to sit down; age-14+ Mending a button and Ironing clothes; and
  nursing-mother-with-carried-baby Teaching first words. Confirm children under
  14 do not receive mending/ironing, non-nursing villagers do not receive infant
  care, and Petting is never added as a spontaneous choice.
- Behavior labels: exercise all 30 nap labels and the B150 web labels. Buying
  stuff online must be absent below age 13 and present at 13+; Watching memes,
  Making memes, and Posting memes online remain in the general web pool.
  Confirm the nine infant-care labels reuse Teaching first words targeting and
  animation safely.
- Sit-down gates: sample the complete general pool at every life stage.
  Thinking of work must require displayed age 19+ with a career; Thinking of
  school must appear only when that conjunction is false; Texting spouse is
  age-19+ only; Texting boyfriend is female-only ages 14-18; Texting girlfriend
  is male-only ages 14-18. Verify adult children/grandchildren/spouse labels and
  all general phone/rest/reflection labels.
- Sink/weather gates: exercise WashingInBathroomSink 0x0A4-0x0A8 and both
  grooming routes on every installed sink. Males must not receive the female
  grooming pool; Putting on jewelry must be female-only age 14+. Verify north
  shower variants require a usable north shower, snow-play fires only during
  Snowing, hammock remains Sunny/Cloudy-only, and Playhouse remains
  child/daytime-only.
- Praise stability hotfix: praise each representative generated action multiple times
  and confirm the current visible string never rerolls, including radio,
  trampoline, web, nap, sit-down, sink, infant-care, and snow variants. Also
  confirm starting a genuinely new behavior can choose a new label and that
  deliberate repeated over-praise still uses the native RunAway behavior.
- Reset Ants: test from unstarted, partially solved, and completed puzzle states.
  Confirm world-state 0x13 and props 0x4D-0x54 reset to a playable starting
  layout, persist after save/reload, and do not alter unrelated malfunctions.
- Collection cheats: test reset/complete with Holiday disabled and enabled.
  Verify exactly five or six 12-item pages, matching page achievements,
  aggregate achievement 0x4D, optional Ornamentologist 0x5F, UI refresh, and
  persistence after save/reload.
- Price modes: activate 2x, 5x, and 100x one at a time and verify furniture,
  Flea Market goods, renovations, career upgrades, Special Upgrades, outfits,
  food/medicine/pets, and every other purchasable category. Confirm modes are
  mutually exclusive, persist across reload, do not overflow negative, and
  Reset Price Multiplier 0x12C removes 0x128-0x12A and restores exact vanilla
  prices with the description "Resets store prices to original values."
- Trigger/Fix all house malfunctions: confirm every normal leak/fire/failure
  becomes active and can be repaired for Handyman credit. Trigger must make the
  Router offline; Fix must clear all 11 malfunction props and return it online
  without changing ant props 0x4D-0x54. Confirm no cheat-triggered dryer fire
  without a placed Dryer, then place one and retry. Independently wait/force the
  legitimate stock Dryer lint-fire case, repair prop 0x21, and verify Handyman
  0x3A advances. Confirm north toilet/shower/sink leaks are absent without
  renovation 0xE6 and present with it.
- North malfunction paths: independently wait/force the stock standalone random
  north toilet/shower/sink failures with renovation 0xE6. With Island Events
  enabled, trigger Water Pressure Surge and verify all three north leaks; with
  Island Events disabled, verify that event cannot fire while the stock
  standalone failures remain possible. Repair every north prop without loops or
  crashes.
- Reversible upgrades: with Cheat Upgrades enabled, repurchase Maid/Gardener
  and verify the correct worker disappears, service expiry clears, and selected
  villager state is valid. Repurchase Rockhound Certificate and Anti-Spam and
  verify their effects disappear and remain removed after reload. Repeat in a
  Cheat-disabled EXE and confirm stock "already purchased" behavior remains.
- Text/notices: verify Brokerage Account states the Interest Rate can reach 11%;
  the GUI shows the Lorsieab2 passion-project/support message and the exact
  vanilla-save compatibility note; generated README, manifest, changelog, and
  Transparency Log carry the same disclosures without local machine paths.

## B151 Holiday Ornaments Release Status

- [x] Static/build work is complete: all 16 native-feature variants compile,
  all 129 source/exporter tests pass, the independent linked validator passes
  eight Holiday-enabled and eight Holiday-disabled executables, canonical art
  hashes match, and default/Holiday-focused/enable-all patcher dry runs pass.
- [ ] Complete the required manual in-game cycle: launch and idle through yard
  spawning; open the Collections Chest and navigate all six pages; collect
  unique and duplicate ornaments from every rarity; save and reload; exercise
  The Collector's Keep and Sell choices; and verify Reset All Collections and
  Complete All Collections with Holiday Ornaments both enabled and disabled.
- Deferred from B151: the expanded map, new goals, and Older Villagers work
  below remain planning material for a later build.

## B152 Custom Achievement Phase B1/B2 Status

- [x] Materialize stable rows `0x5F-0x7F` in every native variant, register all
  64 exact strings, and keep Holiday Furniture goals as the final contiguous
  `0x6D-0x7F` order suffix.
- [x] Preserve SaveState/Reset at `0x125` records and repair LoadState so IDs
  through hidden record `0x80` persist while only reserved IDs
  `0x81-0x124` are cleared. Record `0x80` dword `+4` low bits persist the
  `0x2CF`/`0x2CC` Taters purchase mask.
- [x] Restore the notification queue to its real `0x5F`-dword capacity and
  structurally protect popup timer/state fields `+0xF38/+0xF3C`.
- [x] Route achievement scene height/order end and completed-goal totals
  through the filtered visible count, with a default-off writable one-byte
  `.vf2goal` Holiday Furniture flag.
- [x] Pass 81 patcher tests and link/inspect the required B152 off-off and
  on-on diagnostics from their matching B151 bases. Both contain 128 rows and
  a writable, size-one, default-`00` `.vf2goal` section.
- [x] Harden B1 with exact Save/Reset/Pop/Update symbol-span guards, preserve
  `ECX/EDX` around the order-end helper, validate its object and linked cave
  bytes/branches, and cover Holiday-only plus Behavior-only object layouts in
  addition to both diagnostic extremes.
- [x] Phase B2 purchase awards: retarget only shifted
  `HandlePurchaseItem+0x2DE`; call native AddToStorage first; preserve its
  bool; award only on success before stock SaveCurrentGame; gate Holiday
  Furniture mappings on `.vf2goal == 1`; and make Taters `0x74`
  order/duplicate/save safe through hidden record `0x80`.
- [x] Phase B2 behavior awards: exact pre-ForgetPlans praise/scold labels cover
  `0x66-0x6C`, Pavlovian `0x93`, social/child goals `0x94-0x97`, nine
  additional praise goals `0x98-0xA0`, and four child-discipline goals
  `0xA1-0xA4`. Props to you `0xA5` requires stock Tight Ship `0x30` plus all
  four new discipline goals. Praise preserves the native restoration and
  over-praise routes; every matching scold still reaches exactly one native
  ForgetPlans call with no label restoration.
- [x] Validate B2 source, object, and linked contracts in core/off-off and
  Holiday+Behavior/on-on diagnostics. This is structural verification only;
  no manual runtime result is claimed.
- [x] Phase B3 exporter: discover .vf2goal from every selected executable,
  emit its exact-SHA record under core_executable plus holiday_furniture, and
  prove it can coexist with .vf2preg across 16 unique synthetic layouts.
- [x] Phase B3 final linked matrix: build and independently validate all 16
  executable layouts, including unique hashes, `.vf2goal`/`.vf2preg`/`.vf2mort`
  sections, exact-SHA records, and enable/repeated-enable/disable byte cycles.
- [ ] In game, re-test runtime enable/disable, save/reload, and completed-goal
  restoration across representative overlay combinations.

## Deferred after B151: Expanded Map

- For a future build, use `work/reference_images/Expanded VF2 Map.png` as the
  visual target. Keep the existing house/map composition centered and add one
  full map tile beyond every current side and corner instead of scaling the
  current map.
- Fill the new perimeter with the matching Lorsieab2 grass treatment, except
  for the northwest/upper-left expansion where the existing beach grows into
  the large rounded sandy area shown in the mock-up.
- Treat expansion as native world work, not a background-only composite:
  extend terrain/map tiles, camera clamp/scroll limits, world and placement
  bounds, walkability/pathing, hit testing, drop targets, weather/decoration
  coverage, and save-safe coordinates together.
- Preserve the existing house, rooms, renovations, furniture positions, beach,
  yard features, vehicles, and custom map art at their current scale and
  relative positions. Audit any hardcoded map dimensions before implementation.

## Deferred after B151: Goals and Older Villagers

- [x] Add exact-SHA, setting-gated `post_asset_patches` infrastructure so a
  one-byte runtime goal flag can be applied after any selected executable
  overlay without doubling the overlay matrix. Keep exporter output empty
  until real linked offsets are available.
- [ ] Final Phase A commit allowlist: explicitly include
  `data/vf2/vf2_desktop_base_and_mobile_furniture_sections.csv` with the
  patcher/exporter sources, focused tests, and these documentation updates;
  verify the CSV is tracked before committing so the workspace-local catalog
  cannot be omitted.
- [x] In B3, collect the stable Holiday Furniture runtime flag's exact payload
  SHA-256/file-offset pair for all 16 executable variants and emit one
  unambiguous manifest variant per SHA. Automated toggle cycles verify disabled,
  enabled, repeated-enable, and disable-after-enable bytes for every layout.
- [x] Implement the resource, pet, longevity, family-tree appearance,
  exact-action praise/scold, and discipline goals specified for B156.
- [x] Implement Furnishing the Future for a successful purchase of any active
  VF3 furniture-patch item: six couches/loveseats and three televisions.
- [x] Add a separately gated dormant `.vf2mort` hook that replaces only the
  birthday old-age decision, preserves the entire stock block when disabled,
  uses a normal survival curve centered at effective age 75 (sigma 3), grants
  one effective bonus year per active food group (0-4), and caps the annual
  hazard at 99.99% without imposing a hard maximum age.
- [x] Link all 16 B154 executable layouts and validate the `.vf2mort` section,
  helper ABI, exact-SHA post-asset records, coexistence with `.vf2preg` and
  `.vf2goal`, unique hashes, and reversible byte-toggle cycles.
- [x] Replace B155's SSA/50% optional curve in B155.5 with the full-game
  calibrated monotonic curve; analytically validate all 0-4 food-group cases
  and simulate at least one million adults per case.
- [x] Link all 16 B155.5 executable layouts and validate the million-way helper,
  monotonic hazard table, exact-SHA toggles, and patch-off stock restoration.
- [ ] Live-test birthdays, time-away catch-up, starvation/sickness causes, ages
  55/60/75/90/100/122+, save/reload, and patch-off stock parity.
- Keep the exact requested title `Hampster Dance`; use the corrected spelling
  `Centenarian`; and make pet goals require a live placed pet rather than a
  purchased-but-unplaced inventory item.
- Audit package growth before adding another native feature dimension. Prefer
  runtime gating or compact deltas if a naive Older Villagers toggle would
  double the 16-overlay executable matrix.

## B152 Holiday Ornament Text/Order Follow-up

- [x] Use "Ornaments" only as the Collections page title while retaining the
  full "Holiday Ornaments" feature name elsewhere.
- [x] Give the Holiday page dedicated common/uncommon/rare footer strings so
  it never reuses the stock bottle-cap wording.
- [x] Place visible Ornamentologist 0x5F immediately after Bottlologist 0x5E
  in every Holiday-enabled goal layout, with exact adjacency tests.
- [x] Leave all graphics, descriptor orientation, draw-time transforms, and
  B2 purchase/praise/scold hook regions unchanged.
- [ ] In game, open page 5 and verify the short title plus all three rarity
  footers, then open Goals and verify Ornamentologist directly follows
  Bottlologist. Automated tests are structural and do not replace this check.

## B152 Experimental Allow Older Pregnancies

- [x] Install the dormant hook in every executable with independent writable
  .vf2preg byte 00; preserve the native path for flag-off and both-under-50.
- [x] Implement the older-parent cap in tenths of a percent: 10.0% at age 50,
  1.0% at 59, 0.9% at 60, 0.1% at 68, and a permanent 0.1% floor at 69+.
- [x] Keep successful tutorial queueing, bypass first-pregnancy forced success
  after a failed late-age roll, and leave multiple-birth logic untouched.
- [x] Add default-off Experimental patcher metadata plus exact-SHA post-asset
  .vf2preg variants without expanding the 16-executable matrix.
- [x] Coexist with the independent .vf2goal Holiday Furniture record for the
  same payload SHA; both records are nonoverlapping and grouped safely.
- [x] Compile and bounded-validate a real core diagnostic: .vf2preg is
  writable/default-00 at raw 0x188800, and the native detour/helper/stock
  fallback plus 1000-way roll and success-only tutorial queue all decode.
- [x] Run the linked validator over all 16 final B153 matrix executables and
  dry-run/apply `.vf2preg` with enable, repeated-enable, and disable restoration
  against every selected-overlay SHA.
- [x] Detour the failed-attempt cooldown store and skip only the
  `theGameState+0x25AE0` deadline write when the patch is enabled and either
  parent is age 50+; linked validation proves flag-off/both-under-50 parity.
- [x] Route all four Family Tree/main-scene `CanStartNextGeneration` queries
  through one ABI-compatible wrapper. When `.vf2preg` is enabled, displayed
  age 60 for the oldest active living non-departed villager additionally
  enables the native flow, provided a surviving child exists. Native
  `StartNextGeneration` and its 30-record `MakeRoomInTree` rollover remain
  unchanged. Flag-off returns the native result.
- [ ] Manually test ages 49, 50, 59, 60, 68, 69, and an extreme old-age save;
  confirm normal under-50 attempts, late-age failures, successful births,
  save/reload, and native singleton/twin/triplet outcomes.
- [ ] In game, check the Family Tree at oldest-villager ages 59 and 60, start
  the next generation at 60, and verify no-child, generation-30, save/reload,
  and `.vf2preg`-off behavior.

## B152 Upright Holiday Ornament Payload

- [x] Copy all 12 supplied collected icons byte-for-byte with no orientation
  or size transformation.
- [x] Rebuild the 1024x768 page from the supplied base, upright frame, upright
  lower-right Candy Cane at (848, 461), and 12 upright placeholders.
- [x] Validate deterministic rebuilds, exact source hashes, full-page geometry,
  Holiday gate behavior, and exporter payload routing.
- [ ] Open the collection page in game and visually confirm the frame, Candy
  Cane, placeholders, and collected ornaments are upright and aligned.

## B153 Experimental Increase Child Limit

- [x] Audit live villager capacity, conception allocation, Family Tree record
  geometry, save-block boundaries, Family Tree draw/hit testing, and Next
  Generation candidate arrays from the desktop COFF objects.
- [ ] Design and prove a vanilla-save-compatible, versioned persistence
  extension for six extra `SPeepRecord`s per generation. Do not raise
  `EmptyOffspringSlots` before this exists: the stock record has room for only
  six and would overwrite the following generation.
- [ ] Add sidecar-aware Family Tree count/add/find/death/update/reset,
  `MakeRoomInTree`, and `StartNextGeneration` routes while preserving the
  stock six records byte-for-byte when the patch is disabled.
- [ ] Replace Family Tree child drawing and hit testing as one unit with a
  readable 12-child grid; verify all 12 names, portraits, death tinting, and
  information dialogs across current and historical generations.
- [ ] Replace the two six-dword Adoption/Next Generation arrays with
  12-candidate external storage and verify cycling plus selection of every
  child, including indices 6-11.
- [ ] Test singleton/twin/triplet births at counts 5-11, adoption, save/reload,
  time away, death, generation transition, generation-30 rollover, patch-off
  parity, and loading unmodified vanilla saves before exposing the setting.
