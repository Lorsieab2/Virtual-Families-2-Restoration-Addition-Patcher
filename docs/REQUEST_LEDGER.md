# VF2 Restoration + Addition Patcher Request Ledger

Last reconciled: 2026-07-12
Published baseline: B153 (`2963ba2`, release
`B153-restoration-addition-patcher`)

This is the durable completeness gate for future builds. A request does not
disappear because it was made in an older chat. A label, checkbox, design note,
dormant hook, or successful link is not proof that a feature is finished.

## Status meanings

- **Shipped / automated-verified**: in the published baseline with
  source/link/package checks.
- **Shipped / in-game QA pending**: shipped, but an important runtime scenario
  still needs a game test.
- **Partial**: implementation exists, but the complete request is not delivered
  or proven.
- **Needs source audit**: prior work may exist but has not been traced from
  setting through native behavior, persistence, packaging, and QA.
- **Not started**: no complete implementation is claimed.
- **Blocked on owned asset/native evidence**: waiting for a self-contained
  source asset or reliable native contract. Outside paths are never a release
  dependency.

## Release invariants

- GitHub is the source of truth and new builds use the newest published build.
- The project and release payload are self-contained.
- Optional features are absent when their setting is off.
- Base-game autonomous behavior choices and likelihoods remain unchanged.
  New routes are additive and explicitly gated.
- Reversible purchases clear their active/save flag and can be bought again.
- Goal progress persists unless a documented action deliberately resets it.
  The Collector's **Sell it all!** choice is the explicit exception: it pays by
  rarity and resets all collections and related goal progress. **Keep** is inert.
- Experimental features stay experimental until critical save/load,
  enable/disable, and in-game routes are proven crash-free.
- Every release updates notes, TODO/changelog, technical discoveries where
  applicable, and the Transparency Log.

## Published B153 baseline

| Request | Status | Evidence / remaining gate |
|---|---|---|
| Holiday Ornaments: 12 mobile IDs, rarity, spawns, sixth page, 72 total, persistence, pickup/drop, Collector integration | Shipped / automated-verified | Linked validators and 16-state matrix; user confirmed spawns. Full save/load and Lucky Rock frequency QA remain. |
| Upright Ornament art and corrected lower-right Candy Cane | Shipped / automated-verified | Canonical sources copied into payload and hash-validated. |
| Page label `Ornaments`, footer strings, Ornamentologist after Bottlologist | Shipped / automated-verified | B152 string/order validator. |
| Holiday Furniture achievement runtime gate | Shipped / in-game QA pending | Exact-SHA `.vf2goal` gate; purchase, award, persistence, and off-state QA remain. |
| Allow Older Pregnancies | Partial / automated-verified | Default-off `.vf2preg` hook ships. Stock under 50; 10% at 50, decreasing to 0.1% floor at 69+; native multiples preserved. All 16 linked layouts, exact-SHA records, helper ABI, stock fallback, and toggle cycles pass; conception/tutorial/birth/save-load QA remains. |
| Reset Ants; Reset/Complete all collections | Shipped / in-game QA pending | Native/package checks exist; verify awards, reset semantics, Holiday on/off, and save/load. |
| 2x/5x/100x Prices and Reset Price Multiplier | Shipped / automated-verified | Both ordinary and career `CalcPrice` returns are hooked; 2x/5x/100x are mutually exclusive and saturate at `INT_MAX`. Reset removes all multiplier inventory flags and returns the current canonical incoming price unchanged, so it does not restore stale cached prices. Broad in-game purchase QA remains. |
| Trigger/Fix malfunctions, Router state, dryer fire, north leaks | Shipped / in-game QA pending | Props and renovation gates linked; gameplay/repair/Handyman/Water Surge QA remains. |
| Rebuy Maid/Gardener to fire and Rockhound/Anti-Spam to remove | Shipped / in-game QA pending | Source route exists; active-flag/save/rebuy QA remains. |
| B150 behavior variations and gates | Needs source audit | Audit the whole age/weather/nursing/gender/manual/autonomous matrix. |
| Compatibility/creator GUI messages | Shipped / automated-verified | Exact constants exist in exporter and GUI and are covered by GUI/exporter tests. |
| Brokerage Account 11% message | Shipped / in-game QA pending | Exact native store description exists; verify its visible wrapping/layout in game. |

## B153 priority

| Request | Status | Completion contract |
|---|---|---|
| Fully working Allow Older Pregnancies | Partial / linked validation complete | All 16 layouts now also prove the age-50+ failed-attempt cooldown bypass: the patch skips only the stock `theGameState+0x25AE0` deadline write when either parent is 50+, while flag-off and both-under-50 retain it. Live conception/birth/save-load QA remains. |
| Older Villagers mortality curve | B155.5 source + analytical/simulation + 16-layout linked validation complete | Default-off `.vf2mort` replaces only the birthday old-age roll. It retains threshold `55 + active food groups` (0-4), uses monotonic intensity `0.00365*n + 0.06*max(0,n-55)`, one million-way roll, and a 999999/1000000 cap with no hard maximum age. Full-game calibration uses 60 adults; age 110 takes multiple games and age 122 remains exceptional. Live aging/save/time-away QA remains. |
| Next Generation button around age 60 with age patch | Not started | Gated only with the age patch; stock flow when off. |
| Increase Child Limit to 12 | Partial | Native audit complete: live `CVillagerManager` already has 30 ordinary peep slots, but each generation persists only six `SPeepRecord`s and the Next Generation scene owns two six-entry candidate arrays. A safe implementation needs additive persistence for six extra records per generation plus matched Family Tree draw/hit-test and candidate-array detours; changing the limit constant alone would overwrite the next generation. |
| Force Successful Pregnancy | Not started | Next eligible attempt never argues and succeeds; clear after resulting birth. |
| Next babies Male/Female | Not started | Saved mutually exclusive one-shot applying to every baby in next birth; clear after birth. |
| Next pregnancy Singleton/Twins/Triplets | Not started | Saved mutually exclusive, cap-safe one-shot; clear after birth. |
| Complete all Achievements cheat | Source + linked build validated | Cheat row 0x12E checks `IsComplete` before calling native `SetComplete` for every currently enabled base/modded prerequisite row, preserving normal coin awards without duplicate payouts. Completing the final prerequisite then awards Achiever Extraordinaire through its normal last-goal observer. |
| Trophy icon for Complete all collections and future cheats | Current rows source + linked build validated | Complete all collections 0x127 and Complete all Achievements 0x12E use the self-contained trophy descriptor. New future cheat rows should alias that descriptor unless given a dedicated asset. |
| Restore F5 debugger selector and native editors | B154 automated + user live confirmed | F5 opens without the prior house-load crash. F4/F5/F6/F7 and Up/Down internal key maps pass all 16 linked layouts; specialized editor edge-case QA remains. |
| Light editor: edit/place/remove sources | Core editor user-confirmed / hardening pending | Native add/delete/save/type-cycle/mouse-drag routes work in game; B154 corrects + and - direction. Persistence/export, cancel/reset, fault handling, and patch-off parity still need narrow QA. |
| Recreate dummied debug tools | Needs source audit | Behavior/Content Map editors are absent in checked binaries; replacements require verified engine contracts. |

## Behaviors and variations

| Request group | Status | Notes |
|---|---|---|
| `Needs to sit down` spontaneous plus thinking/resting/phone/texting/scrapbooking variations and all age/gender/relationship gates | Partial / linked validation | `Needs to sit down` is registered all-ages at weight 450 only under Behavior Patches, and all 16 layouts preserve the gate. Variation age/gender/relationship/location sampling and live stock-weight parity remain. |
| `Ironing clothes` and `Mending a button` spontaneous | Shipped / automated-verified | Adult-only helper uses native age-unit minimum `0x118` (displayed age 14+) and registers Ironing at weight 700; linked 16-layout validation confirms patch-on presence and patch-off absence. Live frequency QA remains. |
| `Petting` not spontaneous | B156 source + linked validation complete | Behavior Patches deliberately does not enable autonomous candidate `0x19A`. The randomized Petting label wrapper remains available only when a manual/native Petting route starts. Live long-session absence QA remains. |
| `Checking weight` spontaneous for all ages | B156 source + linked validation complete | Behavior Patches enables native WeighingSelf candidate `0x046` for all ages at weight 450 while retaining the native scale target and plan. Live location/frequency QA remains. |
| Nursing actions: first words, walking, talking, feeding, lullabies, playing, admiring, peek-a-boo, kissing, pictures | B156 source + linked validation complete | Candidate `0x11F` keeps the native nursing-mother/own-carried-baby gate and weight 450, with the complete requested label pool. Live frequency and praise QA remains. |
| Browsing web: buying online (13+), watching/making/posting memes, cat videos, VideoTube, game/social variations | B156 source + linked validation complete | The existing web route receives the requested label pools. Buying online requires raw age `0x104` (displayed 13+); existing teen/social labels retain their native age route. Exact praise-label preservation is installed. Live frequency/praise QA remains. |
| Taking a nap dream variations | B156 source + linked validation complete | The couch-nap route has the complete 30-label dream pool, including every requested destination/topic, without replacing native nap targeting. Live distribution/praise QA remains. |
| Snowy-weather actions | B156 source + linked validation complete | Snow-play eligibility is refreshed only when `Weather.currentType == 5` (Snowing); patch-off keeps the stock candidate. Live weather-transition/frequency QA remains. |
| Bathroom sink actions; jewelry for females 14+ | B156 source + linked validation complete | Direct sink behaviors `0x0A5-0x0A8` clone the full native `0x0A4` candidate before restoring their IDs/weights. The grooming pools are Behavior-Patches gated, and jewelry requires female gender plus raw age `0x118` (displayed 14+). Live sink/variation QA remains. |
| Manual `Play video games` on computer drop | B156 source + focused compile validation complete | Behavior Patches preserves the stock computer hotspot and every email/repair/career/sickness branch. Only the ordinary manual Browsing web result `0x5A` receives a 50/50 native PlayingVideoGame `0x114` alternative; autonomous weights are unchanged. Live drop-frequency QA remains. |
| Mobile-only furniture actions | B156 lounge family player-verified; Patio Table, Picnic Table, Umbrella, Birthday family, Christmas Stockings, Dreidel, Menorah, and Christmas Trees source complete / remaining routes pending | Scope is exactly the 63 genuine mobile rows `0x2AA-0x2E8`; all Invisible/custom/VF3 items are excluded. Forty-one original QAMFs are tracked locally and 22 absent maps are explicit. Player testing confirms the Lounge Chair anchor/pose and bad-weather refusal. Good-weather manual drops randomly choose relaxing, reading, studying, sitting, napping, or sleeping with energy-dependent nap/sleep weights. Patio Table and Picnic Table have exact guarded manual prepare/use pairs, PC-safe seat maps, and independent external 240-game-second states for unsafe mobile props `0x56` and `0x55`; children may use either once ready, while preparation requires raw age `0x118+` and at least 31 food. Picnic eating preserves three fresh sound/animation rounds and hunger -40. Mobile autonomous pairs `0x1B4-0x1B7` remain deliberately unindexed because they exceed the PC behavior table. The complete Birthday family includes guarded single-object fallbacks and Birthday Banner whole-household celebration. Christmas Trees, Large and Small Stockings, Dreidel, and Menorah have exact guarded plan ports with minimal PC-safe maps. Exact disable restoration is automated; live Patio, Picnic, birthday, Holiday, timer, and save/reload QA remain. |
| Praise string-change bug | B156 source + linked validation complete | InvokeReward captures the exact 0x28-byte action label before native plan clearing, awards exact-label goals, and restores the cached label only for the same behavior serial and incremented praise counter. Scold captures exact text before the single native ForgetPlans call. Live repeated-praise/scold QA remains. |

## Cheats and house state

| Request | Status |
|---|---|
| Spawn max house trash / Spawn max weeds | B156 source + combined executable link complete | Cheat Upgrade items `0x12F-0x130` call the native bounded `SpawnTrashInHouse(30)` and `SpawnWeedsInYard(30)` methods. The UI states that only available collectable slots are filled; existing collectables are preserved. Live purchase/spawn/save QA remains. |
| Max out sock pile / No sock pile | B156 source + fully-enabled linked validation complete | Cheat Upgrades 0x133 and 0x134 write the stock sock-pile counter at `theGameState+0x148`. Max uses 30, the threshold for the sixth and largest stock `sockPileStrip.png` frame; No sock pile uses 0 and deliberately does not award sock-laundering achievement progress. Live purchase/visual/save QA remains. |
| Clean House / Clean Garden | B156 source + fully-enabled linked validation complete | Clean Garden item `0x131` calls the exact stock Weed Bomb selector `RemoveAll(0x7D)`. Clean House item `0x135` matches the stock Housekeeping Services event by calling `RemoveAll` with selectors `0x73`, `0x79`, `0x81`, and `0x83`; yard weeds and the separate laundry-room sock pile remain. Live purchase/remove/save QA remains. |
| Spawn Marriage Email | B156 source + fully-enabled linked validation complete | Cheat Upgrade 0x132 queues the stock marriage-proposal email enum 2 through `theGameState::QueueEmailMessage`, preserving native duplicate suppression and the ten-slot queue limit, then saves through the common cheat path. Live queue-full, duplicate, eligible-family, proposal UI, and save/reload QA remains. |
| Function-sort every Cheat Upgrade | B156 source + fully-enabled linked validation complete; live UI QA pending | Rows are ordered by function: money, food, furniture locks, paired achievement controls, paired collection controls, price multipliers/reset, paired malfunction controls, house trash/Clean House, yard weeds/Clean Garden, sock-pile max/clear, then marriage email. Item IDs and effects remain unchanged. |
| Collector Sell All rarity payment and deliberate reset only | Shipped / in-game QA pending |

## Goals and achievements

Exact-action goals trigger only while the named action/variation is current.
Praise/scold must not overwrite it first. Counting goals persist, award once,
and reset only through their documented reset action.

| Group | Status | Requests |
|---|---|---|
| Wealth/food | B156 source + fully-enabled linked validation complete | No More Worries 0x83 awards at the exact native coin ceiling of 4,000,000,000; Solving World Hunger 0x84 awards at the exact food ceiling of 2,147,483,647. All native Set/Adjust callsites are observed, old maxed saves reconcile after load, and Reset Achievements stays cleared until a later resource mutation or reload. Live award/notification/save QA remains. |
| Pets in home | B156 source + fully-enabled linked validation complete | A Furry Companion 0x8A awards for any successfully placed live pet, including Turtle; The Cat's Meow 0x8B covers items 0x23B-0x23F; Man's Best Friend 0x8C covers 0x240-0x244; Itsy Bitsy 0x8D is Tarantula 0x248; Hampster Dance 0x8E is Hamster 0x247; Lovely Lizards 0x8F is Lizard 0x246. Buying into the Tool Tray does not qualify. Failed/full-capacity placement does not award. Successful save loading reconciles only active pets across all 30 native slots. Live placement, notification, reset, save, and reload QA remains. |
| Longevity | B156 source + fully-enabled linked validation complete | Lucky 70's 0x85, Great 80's 0x86, Mighty 90's 0x87, Centenarian 0x88, and Oldest Person in History 0x89 award at exact raw-age thresholds 1400, 1600, 1800, 2000, and 2441 (>122). The annual old-age path observes the raw-age cursor after native food-group calculation but before mortality, independently of the optional mortality flag. Load reconciliation scans the 30 villager records and excludes inactive, left-home, and dead villagers. Live birthday, notification, reset, save, and reload QA remains. |
| Family-tree appearance | B156 source + fully-enabled linked validation complete | Return of the Rainbow 0x90 requires a persistent female (gender 1) family-tree record with head 48; Spiky! 0x91 requires a persistent male (gender 0) record with head 48. All six native record-update calls are observed after the native write. Load reconciliation scans both parents and up to six children across the 30-generation persistent tree, including dead and departed relatives. Live birth/adoption, notification, reset, save, and reload QA remains. |
| LDW paintings/posters | Shipped / automated-verified | IDs 0x60-0x65 award after successful purchases of the six verified LDW art items. Live purchase/notification QA remains. |
| Exact praise: web/games | Partial / linked validation | Nyan Cat, Like and Subscribe, VF-Inception, Isolan Refugees, and Memz are implemented at 0x66-0x6A. The remaining exact-action goals still require their behavior labels/routes. |
| Exact scold: social/child | Not started | Fakebook Fakery; Dance Dunce; The Last Trend; Lazy Crazy. |
| Pet interaction corrections | Partial / linked validation | Good boy 0x6B and Bad dog 0x6C inspect exact Praising pet/Scolding pet labels before native state clearing. Pavlovian Association remains pending. |
| Birthday purchases | B156 source + 16-layout linked validation complete | Happy Birthday 0x80 maps Birthday Banner 0x2DB; Not a lie 0x81 maps Birthday Cake 0x2DC; Full of helium 0x82 maps Birthday Balloons 0x2DA. Awards occur only after AddToStorage succeeds; live purchase/save/notification QA remains. |
| Discipline | Not started | No clothes-throwing; no toilet play; no bed jumping; no wall drawing; No messing with the light switch! (scold a child for switching the light on and off); Props to you after Tight Ship plus all five additional discipline goals. |
| Holiday Furniture purchases | Shipped / core purchase goals user-confirmed | Coin awards and purchase-goal firing work in game; exhaustive ID aliases, persistence, and patch-off absence remain narrow QA. |
| VF3 furniture | Not started | Furnishing the Future. |
| Ornamentologist/collection goals | Shipped / spawn and award user-confirmed | Ornaments spawn and Ornamentologist wiring works in game; persistence, Lucky Rock weighting, and every reset path remain narrow QA. |
| Achiever Extraordinaire | B156 source + fully-enabled linked validation complete | ID `0x92` is always the final visible row. Every completion scans the exact selected `achievementOrder`, excluding only itself; compile-gated Ornament/Behavior goals and runtime-gated Holiday Furniture goals count only when visible. Successful save load performs the same reconciliation. Live final-award/popup/save QA remains. |

## Renovations, map, events, and family systems

| Request | Status | Completion contract |
|---|---|---|
| Mobile Kitchen/Office/Workshop/first Bathroom renovations | Not started | Curate owned art into workspace; store rows/icons/prices, exact overlays, saved choice, switching/removal, off-state. |
| Same remodels for second Bathroom | Blocked on owned asset/native evidence | Blue mockup is reference; generate self-contained north-room assets for every shipped theme while preserving malfunction routes. |
| Every renovation reversible | Not started | Clear active flags, allow remove/switch/rebuy, persist safely. |
| Expanded map X-1Y0..3 and X4Y0..3 | Removed from B156 scope by user request | No expanded-map patch is exposed. The inactive placeholder and Experimental/Not Working section were removed; no camera, pathing, placement, spawn, or save bounds are changed. |
| VF3 Phone | Not started | Optional phone with independent verified island-style event delivery; email remains. |
| Mobile Island Events and exact outcomes | Partial | Added events can fire; exact native outcomes/state changes remain. |
| Enable Races via VF3 palette/overlay | Not started | Self-contained assets/evidence, saved color, rendering, inheritance/candidates/UI/off-state. |
| Same-sex marriage | Not started | Same-sex candidates and repeatable private romantic action with 0% pregnancy; stock/off-state preserved. |
| Multiple candidates per marriage email | Not started | Reject rerolls; same-sex patch may choose same/opposite sex; preserve email state. |
| VF3-style child adoption chooser | Not started | Choose random baby or age 2-8 child with full traits; singleton; capacity/save/tree safe. |
| Generation counter beyond 30 | Not started | Increment every Start New Generation and show on Goals screen while tree keeps rolling behavior. |

## UI, packaging, and documentation

| Request | Status | Notes |
|---|---|---|
| Vanilla-save compatibility note | Shipped / automated-verified | Exact requested sentence is shared by exporter and GUI and covered by tests. |
| Creator/passion-project/support message | Shipped / automated-verified | Exact requested copy is shared by exporter and GUI and covered by tests. |
| Brokerage rate up to 11% message | Shipped / in-game QA pending | Exact native description is present; visible in-game wrapping remains. |
| Smaller builds / remove redundant EXEs | Partial | B152 is manifest-pruned; 16 native overlays remain required by current architecture. Prefer exact-SHA toggles when safe. |
| Preserve base-game EXE icon | Implemented / automated Windows verification | B156 copies exact stock RT_ICON and RT_GROUP_ICON resources after all EXE mutations, validates group references/sizes, and requires successful Windows extraction at 16x16, 32x32, and 48x48. Player confirmation of folder/desktop/taskbar display remains final live QA. |
| Designated GitHub repository only | Shipped / automated-verified | B152 branch/release is in Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher. |
| Complete changelog and Transparency Log | Ongoing invariant | Required before every release. |
| GitHub publishing/latest release asset only | Ongoing invariant | Commit/push source, verify latest ZIP digest, delete obsolete local release archives. |

## Mandatory uncertainty audit

Before each release:

1. Reconcile chat requests against this ledger, TODO, build history, source
   settings/hooks, tests, release notes, and the actual exported payload.
2. Trace every behavior variation's base action, exact text, age/gender/nursing/
   relationship/weather gate, autonomous/manual eligibility, and off-state.
3. Trace every custom goal's trigger, counter, coin award, persistence, reset,
   order, and optional-patch visibility.
4. Trace every reversible purchase's active flag, removal, re-buy, and save/load.
5. Test Holiday Lucky Rock behavior and full Ornament save/load/UI paths.
6. Audit mobile furniture actions, mobile Island Event outcomes, and the
   remaining in-game Brokerage text layout.
7. Any older request found but absent here is added as **Needs source audit**
   before implementation or release; it is never silently omitted.
