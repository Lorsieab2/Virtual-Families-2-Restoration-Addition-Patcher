# B158 runtime QA matrix

## Purpose and boundary

This is a player-executed runtime checklist for the source-complete,
non-hiatus B158 routes. It records what to set up and what evidence to collect;
it contains no runtime results. Do not mark a row complete until the observed
result, save/reload evidence, disable-restoration evidence, and crash-capture
fields are filled.

The matrix covers:

- the `mobile_furniture_behaviors` manual and autonomous routes for the genuine
  VF2 mobile furniture range (`0x2AA-0x2E8`);
- whole-household manual actions for Birthday Banner, Christmas Trees, Dreidel,
  and Menorah;
- the `mobile_renovations` room-overlay route (`0x13C-0x14A`) and the native
  structural renovation purchase/load/removal route (`0xE1-0xEA`).

VF3 Phone, Races, and the 12-child limit are intentionally out of scope and
must not be enabled, researched, or used as a test case.

## Build and evidence preflight

Create separate, disposable test copies. Never reuse a player save without a
backup and a recorded slot identifier.

| ID | Build/setup | Required preflight evidence |
| --- | --- | --- |
| `P0` | Record the exact EXE selected for each run. Use an absolute path and the matching build manifest; record byte size and SHA-256 before launch. | `build_id`, `exe_path`, `exe_size`, `exe_sha256`, manifest path/hash, source commit (`28da840` or later), test-copy path. |
| `P1` | Mobile furniture enabled: offline patcher setting `mobile_furniture_behaviors`; retain the matching `.vf2beh` executable and optional map payload. | Setting state, EXE identity, presence/hash for supplied route maps/assets or the ledger's explicit documented-absent status, clean-save backup. |
| `P2` | Mobile renovations enabled: offline patcher setting `mobile_renovations`; use the matching room-overlay executable/payload. | Setting state, EXE identity, 15-image atlas manifest/hash, clean-save backup. |
| `P3` | Baseline/off build: both settings disabled (or a fresh stock-copy build). Do not mix an enabled EXE with an off payload. | Setting state, EXE identity, absence/restoration inventory for optional maps and `Images/MobileRenovations`. |
| `P4` | Prepare controlled villagers and rooms: resident index, displayed/raw age, health, gender, energy/hunger/food, weather/time, carried baby, and room/object IDs. | Before screenshot or save metadata plus a row-specific setup sheet; record any RNG seed only if the harness exposes one. |

For every row, preserve the pre-test save and record the player-visible save
slot/name and timestamp. If a save file is accessible, record its size and
SHA-256; otherwise record the slot identifier and before/after screenshots.

## Route matrix

`Pending` is the required initial status for every row. The expected column is
the contract to check, not a claim that the contract has been observed.

| ID / route | Exact setup and action | Expected runtime contract | Save/reload evidence | Disable/restoration evidence | Crash-capture evidence |
| --- | --- | --- | --- | --- | --- |
| `MF-01` Lounge chairs `0x2DE-0x2E1` | `P1`; place each chair in a clean room; drop an eligible adult, a high-energy villager, and a low-energy villager in sunny/cloudy weather; repeat in rain/storm/fog/snow. | Manual action selects only the documented lounge branches; tired choices are suppressed or weighted by energy; outdoor branches refuse bad weather and preserve stock fallthrough. Record label, pose/anchor, energy/dirtiness deltas, and interruption behavior. | Save after an action completes and reload; chair ownership, villager state, and unrelated household data remain intact; record any transient plan reset. | Repeat on `P3`; optional dispatch/maps are bypassed and the stock rendered-only/desktop route is restored byte-for-byte in the test copy. | If any drop, reload, or weather transition crashes, stop and capture the exact build plus dump/log bundle using the crash-capture protocol below. |
| `MF-02` Patio Table `0x2E6` | `P1`; sunny daytime, table and seats placed; test adult/raw-age `0x118+`, food `>=31`, child, low-food, and bad-weather drops; run preparation then a second villager's drink action. | Correct age/food/weather refusals; preparation and drink use the proven seats/labels/sounds; prop `0x56` is tracked externally for 240 game seconds; no unsafe desktop prop-table indexing. | Save immediately after preparation, after a drink, and after the 240-second expiry; reload each checkpoint and record prop/plan state, household integrity, and whether the transient timer is cleared or re-established. | `P3` clears the tracked prop state and returns the stock route; no mobile behavior map or external prop helper remains active. | Capture any crash around preparation, seat selection, timer expiry, or reload; include the last prop state and game-time value in the incident notes. |
| `MF-02A` Patio Umbrella `0x2E7` | `P1`; place the umbrella and manually drop villagers spanning age, food, weather, and need values. | Every valid manual drop uses the separate `Adjusting umbrella` route: two approaches/waits followed by a three-tick standing wait. No age, food, weather, RNG, stat, prop `0x56`, or autonomous gate is invented. | Save/reload after completion and verify no persistent prop/stat mutation or spontaneous retrigger. | `P3` removes the optional map/dispatcher and restores the stock rendered-only route. | Capture any drop/approach/reload crash with item, villager, orientation, and exact build. |
| `MF-03` Picnic Table `0x2E8` | `P1`; sunny daytime with four seats; test adult/raw-age `0x118+`, food `<31`, child/low-food refusal, bad weather, preparation, ready state, and linked-seat eating. | Correct DealerSay refusals; random food carry `0x0D-0x13`, basket/food work sequence, prop `0x55` 240-second ready state, three fresh sound/animation rounds, orientation-specific seat choice, hunger `-40`, dirtiness `+4`, poo `+6`. | Checkpoint before prep, after ready, after eating, after timer expiry, and after reload; record transient ready state and all stat values without assuming persistence not proven by the native route. | `P3` clears ready tracking, restores stock prop handling, and leaves no optional picnic map/helper effect. | Capture any crash at map placement, preparation, linked seat, timer, or reload; retain exact prop and villager context. |
| `MF-04` Birthday family `0x2DA-0x2DD` | `P1`; place Banner `0x2DB` plus zero/one/multiple Balloons `0x2DA`, Presents `0x2DD`, and Cake `0x2DC`; manually drop a child and an adult on each hotspot. | Banner presence or more than one birthday object triggers every eligible permanent resident with `Celebrating birthday`; exactly one non-Banner object stays child-only; zero objects forgets the triggering villager's plans. Record mixed-object precedence, eligible/away/zero-health filtering, labels, sounds, waits, jumps/twirls, and child age boundary. | Save after each family plan completes and reload the same family; decorations, household membership, and villager state remain valid. Record that the plan is not spuriously re-triggered by reload. | `P3` retains stock child-only/fallback behavior and removes the external whole-family dispatcher/maps; verify no family-wide action occurs. | If a mixed-decoration scan, adult drop, family filtering, or reload crashes, preserve the exact decoration layout and capture bundle. |
| `MF-05` Christmas Trees `0x2AD-0x2AE` | `P1`; place each tree separately and together; manually drop one present eligible resident while other household slots are configured as eligible, away, nonexistent, or zero-health; separately run autonomous admire/water/break scenarios in sunny conditions with required age/need gates. | Manual tree celebration is whole-household and manual-drop-only; eligible household is the 30-slot permanent set excluding nonexistent/away/zero-health residents; plan preserves tree object, voices, `0xFB`, twirls, jumps, waits, and stop sound. Autonomous `0x19C/0x19E/0x19F` remains separately gated; fixing `0x19D` is not tested. | Save/reload after group completion and after each autonomous action; record resident membership and any transient plan/prop state. | `P3` disables group dispatch and autonomous candidates while preserving stock tree behavior and maps. | Capture tree-specific crash context, including tree variant, resident slot, autonomous candidate, weather/time, and exact build. |
| `MF-06` Dreidel `0x2AF` and Menorah `0x2B8` | `P1`; place each object; test full eligible household, away/zero-health/missing resident, and orientation variations; manually drop one resident. | Each valid drop calls the full eligible household only; Dreidel runs seven two-way rounds with sounds `0x63/0x108/0x77/0xBD` and no stop-sound call; Menorah preserves label, three approaches, `0xFB`, twirls, jumps, waits, and stop sound. Neither writes inventory or save state during the plan. | Save before and after completion, reload, and verify objects, residents, and unrelated save data are unchanged. | `P3` restores stock/manual handling and removes whole-family dispatch/maps; no autonomous family candidate appears. | Capture any crash during household collection, orientation, plan rounds, or reload with the resident list and object ID. |
| `MF-07` Stockings `0x2C6-0x2C7` | `P1`; place both sizes; drop ages at raw `0x117`, `0x118`, and `0x167`, plus both genders and varied orientations. | Every manual drop is consumed through displayed-under-18 (raw `<=0x167`); adults are not incorrectly admitted; label, three approaches, voice, waits, four jumps, work, stop sound, and completion match the contract; no weather/time/gender gate is invented. | Save/reload after child completion and after an adult refusal; record no lost villager or item state. | `P3` restores stock behavior and removes optional stocking maps. | Capture age-boundary or orientation crashes with raw/displayed age fields. |
| `MF-08` Candles, Eggnog, Cookies `0x2AA/0x2B0/0x2BE` | `P1`; test child/adult boundary (raw `0x117/0x118`), eligible rescuer present/absent for cookies, food/object presence, orientation, and fallback object/prop states. | Candles preserve child route, 30-percent follow-up, adult selection/fallback; Eggnog consumes older drops without child action and preserves targets/sounds/jumps; Cookies route child steal plus optional adult rescue, and adult direct drop uses rescue only. | Save/reload after child, adult, fallback, and no-rescuer cases; record label, stats, sound completion, and save integrity. | `P3` returns stock handling and removes optional maps/external candidates. | Capture any crash at age branch, rescuer lookup, fallback, or reload, including object ID and villager age. |
| `MF-09` Figurines/decor `0x2B1-0x2B5,0x2BD,0x2C0,0x2C1-0x2C5,0x2C8-0x2C9` | `P1`; place one representative of each EObject `0x8C/0x8D`; test raw-age `7+` child route and adult-only route, orientation, sounds, and work phases. | Figurines use `Enjoying the figurines` with age `7+`; bows/wall decorations/garlands use adult-only `Checking the decorations`; correct sounds, waits, twirls, stop sound, and completion; no mobile-only behavior-table indexing. | Save/reload after each age branch and after interrupted completion; record item, object, age, and plan label. | `P3` restores stock routes and removes optional maps/candidates. | Capture any crash with item/object ID, age, and branch (figurine vs adult decor). |
| `MF-10` Decorative-only negatives `0x2AB,0x2AC,0x2BF,0x2D4-0x2D5` | `P1`; place Candy Canes, Single Cookie, Poinsettia, and both Wreaths; manually drop children and adults on every visible hotspot. | No invented action: mobile-safe maps remain decorative-only, null/unhandled hotspot returns false, and no item-ID fallback starts a behavior. | Save/reload after attempted drops; record no plan, no stat change, and no save corruption. | `P3` and `P1` must both leave these items decorative; no optional route is introduced by disabling/restoring. | Any crash is a regression; capture the exact item, map cell/hotspot, villager, and bundle immediately. |
| `MF-11` Autonomous selector frequency/distribution | `P1`; use controlled sunny/daytime objects and villagers satisfying and violating the documented age, health, need, carried-baby, and ready/preparing gates for tree, patio, picnic, candles, eggnog, figurines, decor, and lounge candidates. Run a fixed, recorded trial count for each eligible candidate set and lounge-choice state. | External candidates appear only when exact gates pass; weights are additive to stock, stock distribution remains reachable, and manual-only family celebrations never appear autonomously. Record trial histograms and compare observed proportions to documented weights with a declared tolerance; a smoke observation alone is insufficient. | Save/reload after a candidate completes and after a transient patio/picnic state expires; record candidate label, object, weather/time, and state. | `P3` leaves the stock selector and conditional distribution unchanged; no external candidate or transient prop helper remains. | Capture any autonomous decision, timer, or reload crash with candidate ID/weight inputs and exact build. |
| `R-01` Mobile room-overlay purchase `0x13C-0x14A` | `P2`; prepare sufficient currency/generation access and purchase/select every style `0x13C-0x14A`, covering Bathroom, Kitchen, Office, and Workshop at the documented anchors. | Styles appear only in House Renovations category `0x11`, one active style per room, exact 1:1 atlas rendering at the four anchors, and no Special Upgrades row. | Save after each purchase and reload; active style and purchase history remain correct, room switching does not duplicate or lose styles, and camera movement does not move the overlay. | `P3` has no overlay hook or runtime `Images/MobileRenovations` payload; stock map and room rendering are restored. | Capture any purchase, draw, camera, reload, or room-boundary crash with style ID, room, anchor, and build identity. |
| `R-02` Renovation switching/history normalization | `P2`; buy two styles in one room, switch between them, repeat a purchase, and use a prepared legacy fixture with active style bytes but missing ever-purchased bits. If no validated legacy fixture exists, mark this scenario `Blocked`, not passed. | Direct persisted active byte at `InventoryManager + itemId + 0x2A3` selects one active style; duplicate purchases normalize; previously purchased styles reactivate free through the separate history mask; no unrelated item byte changes. | Save/reload after each switch and after legacy backfill; record active-byte/history observations, price, and room image before/after. | Disable and restore from the same test copy; active bytes, history, images, and manifest records return to the pre-test state. | Capture any crash or state corruption with room, item ID, active/history values, and exact save checkpoint. |
| `R-03` Renovation direct removal/rebuy | `P2` plus `cheat_upgrades=on`; own an active cosmetic style and a previously purchased inactive style; invoke the Cheat Upgrades-gated removal path, then reactivate the old style and buy/switch another style. | Removal clears only the active room style, preserves purchase history, returns the stock room, saves immediately, and permits free reactivation; no structural renovation record is deleted. | Reload after removal, after free reactivation, and after a new purchase; compare room, active byte, history mask, price, and save identity. | `P3` leaves the stock renderer and native renovation inventory untouched; no mobile style survives in the disabled runtime tree. | Capture any crash during direct removal, immediate save, or reactivation with item ID and state bytes. |
| `R-04` Native structural renovation `0xE1-0xEA` | Use `cheat_upgrades=on` and a clean save with one owned structural renovation at a time; purchase/activate, save, reload, remove through the Cheat Upgrades-gated route, and test one multi-renovation save. | Native activation arguments, prop state, load order, removal, and remaining-renovation replay match the ten-record contract; unrelated rooms and map state remain intact. | Save/reload after activation, multi-renovation load, and removal; record owned IDs and visible map/prop state. | Disabled build restores the untouched native structural route and does not apply mobile cosmetic overlays. | Capture any map-load, removal, or replay crash with owned-ID list and exact build. |
| `R-05` Health Plan/shared-mask collision | `P2` plus `cheat_upgrades=on`; own Health Plan and at least two mobile renovation histories, save/reload, run Reset Achievements, switch/remove/reactivate styles, and separately create a stock new game. | Health Plan bit 0 and renovation bits 1-15 preserve each other through every update; Reset Achievements preserves the shared dword; reload retains both entitlements; stock new-game initialization remains authoritative and begins without inherited mod history. | Record the shared mask before/after each operation and after reload; verify medicine pricing and renovation reactivation independently. | Disable/re-enable the relevant overlays from the same disposable copy and verify no unrelated achievement/persistence mutation. | Capture any mask, pricing, reset, reload, or new-game crash with exact before/after bits and build identity. |

## Required evidence record for every row

Copy this record once per scenario, not once per route family:

```text
status: Pending
row_id:
scenario:
setting_state: mobile_furniture_behaviors=on/off; mobile_renovations=on/off
build_id:
exe_path:
exe_size:
exe_sha256:
manifest_path:
manifest_sha256:
save_slot_or_name:
save_before_timestamp:
save_before_size_or_screenshot:
setup_values: villager slots, raw/displayed ages, health, gender, needs,
  weather/time, object/item IDs, room/anchor, food, carried baby, orientation
action_steps:
expected_observation:
observed_observation:
plan_label_and_sounds:
stat_deltas:
prop_or_inventory_deltas:
save_after_timestamp:
save_after_size_or_screenshot:
reload_observation:
disable_build_identity:
disable_observation:
restoration_observation:
crash_status: not triggered / captured / blocked
crash_manifest_path:
crash_dump_path_size_sha256:
crash_log_paths_sizes_sha256:
exception_code_address:
fault_module_base_rva:
registers_and_stack_frames:
notes_and_artifacts:
```

## Crash-capture protocol

Do not retry a crashing scenario until its evidence is copied. For a crash,
create a separate exact-build manifest using schema `vf2-crash-capture/v1` with
absolute EXE path, positive size, and SHA-256. Preserve a non-empty
`crash.dmp` with a valid `MDMP` header and at least one non-empty log (normally
`ldwLog.txt`). Then run the existing read-only checks in
`docs/crash-capture-readiness.md`:

1. `verify-exe` against the exact executable;
2. `validate-bundle` against the dump/log bundle;
3. only after a successful bundle report, `emit-ida-json` with exception code,
   exception address, module/base/RVA, all required registers, and complete
   stack frames.

Record the generated report paths and hashes in the row record. A missing,
zero-byte, stale, malformed, or hash-mismatched artifact is `Blocked`, not a
pass. A clean run records `crash_status: not triggered` plus the build, save,
and log evidence; it does not imply crash freedom outside the tested scenario.

## Completion rule

A route is runtime-verified only when every applicable scenario has a recorded
`observed_observation`, save/reload result, disable/restoration result, and
crash status tied to one exact executable identity. Until then, retain
`status: Pending` and keep the corresponding REQUEST_LEDGER live-QA item open.
