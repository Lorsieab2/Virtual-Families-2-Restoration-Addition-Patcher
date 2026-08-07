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
| Holiday Ornaments: 12 mobile IDs, rarity, spawns, sixth page, 72 total, persistence, pickup/drop, Collector integration | Shipped / automated-verified | Linked validators and 16-state matrix; user confirmed spawns. Exact mobile/PC Lucky Rock math is proven and both `Update` and `Add` are byte-locked: spawn attempts double from 3/6600 to 3/3300 and rarity changes from 83/13/4 to 66/26/8. Full save/load and live frequency QA remain. |
| Upright Ornament art and corrected lower-right Candy Cane | Shipped / automated-verified | Canonical sources copied into payload and hash-validated. |
| Page label `Ornaments`, footer strings, Ornamentologist after Bottlologist | Shipped / automated-verified | B152 string/order validator. |
| Holiday Furniture achievement runtime gate | Shipped / in-game QA pending | Exact-SHA `.vf2goal` gate; purchase, award, persistence, and off-state QA remain. |
| Allow Older Pregnancies | Partial / automated-verified | Default-off `.vf2preg` hook ships. Stock under 50; 10% at 50, decreasing to 0.1% floor at 69+; native multiples preserved. All 16 linked layouts, exact-SHA records, helper ABI, stock fallback, and toggle cycles pass; conception/tutorial/birth/save-load QA remains. |
| Reset Ants; Reset/Complete all collections | Shipped / in-game QA pending | Native/package checks exist; verify awards, reset semantics, Holiday on/off, and save/load. |
| 2x/5x/100x Prices and Reset Price Multiplier | Shipped / automated-verified | Both ordinary and career `CalcPrice` returns are hooked; 2x/5x/100x are mutually exclusive and saturate at `INT_MAX`. Reset removes all multiplier inventory flags and returns the current canonical incoming price unchanged, so it does not restore stale cached prices. Broad in-game purchase QA remains. |
| Trigger/Fix malfunctions, Router state, dryer fire, north leaks | Shipped / in-game QA pending | Props and renovation gates linked; gameplay/repair/Handyman/Water Surge QA remains. |
| Rebuy Maid/Gardener to fire and Rockhound/Anti-Spam to remove | Shipped / in-game QA pending | Source route exists; active-flag/save/rebuy QA remains. |
| B150 behavior variations and gates | B150 source audit complete; linked validation complete; live QA pending | `docs/discoveries.md` records the recovered raw-age, gender, career, nursing, weather, sink, autonomous, variation, and praise-cache rules. Behavior Patches owns the guarded route, and the 16-state executable matrix validates its independent gate and off-state. Live frequency, age/gender/relationship, weather, nursing, manual, and save/reload checks remain. |
| Compatibility/creator GUI messages | Shipped / automated-verified | Exact constants exist in exporter and GUI and are covered by GUI/exporter tests. |
| Brokerage Account 11% message | Shipped / in-game QA pending | Exact native store description exists; verify its visible wrapping/layout in game. |
| Mobile Special Upgrade mechanics and persistence | Source-complete / linked QA passed | Brokerage `+2%` and 11% cap, Food Club immediate/daily 500-food delivery and 16-byte save state, and Health Plan quarter-price medicine route are source-proven. Desktop Health Plan ownership now survives reload through hidden achievement record `0xA8+0x08`, separate from the Taters/pregnancy/generation mask at `+0x04`; live buy/reload/remove QA remains. |

## B153 priority

| Request | Status | Completion contract |
|---|---|---|
| Fully working Allow Older Pregnancies | Partial / linked validation complete | All 16 layouts now also prove the age-50+ failed-attempt cooldown bypass: the patch skips only the stock `theGameState+0x25AE0` deadline write when either parent is 50+, while flag-off and both-under-50 retain it. Live conception/birth/save-load QA remains. |
| Older Villagers mortality curve | B155.5 source + analytical/simulation + 16-layout linked validation complete | Default-off `.vf2mort` replaces only the birthday old-age roll. It retains threshold `55 + active food groups` (0-4), uses monotonic intensity `0.00365*n + 0.06*max(0,n-55)`, one million-way roll, and a 999999/1000000 cap with no hard maximum age. Full-game calibration uses 60 adults; age 110 takes multiple games and age 122 remains exceptional. Live aging/save/time-away QA remains. |
| Next Generation button around age 60 with age patch | B156 source + 16-layout linked validation complete; live QA pending | When Allow Older Pregnancies is enabled, all four native `CanStartNextGeneration` queries additionally allow the stock Next Generation flow once the oldest active living non-departed villager reaches displayed age 60. Native eligibility is checked first and a surviving child is still required. Native `StartNextGeneration` and its 30-record `MakeRoomInTree` rollover remain unchanged. With `.vf2preg` off, the wrapper returns the native result unchanged. Live age-59/60 Family Tree, transition, no-child, generation-30 rollover, save/reload, and patch-off QA remains. |
| Increase Child Limit to 12 | Indefinite hiatus (user-directed) | No capacity toggle or implementation work is authorized. The existing native audit remains reference-only: each generation persists six `SPeepRecord`s and the Next Generation scene owns two six-entry candidate arrays. Do not raise the limit constant or pursue the required persistence, Family Tree, and candidate-array detours unless the user reopens this item. |
| Force Successful Pregnancy | B156 source + fully-enabled linked validation complete | Cheat Upgrade 0x136 persists a one-shot in hidden achievement record 0xA8 bit 0x4. It bypasses only the next eligible native `ChanceOfPregnancy` roll; stock partner/gender eligibility, offspring capacity, multiples, naming, family-tree, and birth logic remain intact. The bit clears only when native `CVillager::Impregnate` returns true, remains armed after a capacity failure, survives unrelated Taters-goal writes, and uses the common post-cheat save path. Live purchase, argument-free eligible attempt, full-family, birth, and save/reload QA remains. |
| Next babies Male/Female | B156 source + fully-enabled linked validation complete | Cheat Upgrades 0x137-0x138 use mutually exclusive persisted bits 0x8/0x10. The first native baby spawn receives gender 0/1; native `InitTwin` clones that baby for twins/triplets, so every baby shares the forced gender. Both bits clear only after native `Impregnate` succeeds. Live store, singleton/multiple, save/reload, and post-birth reset QA remains. |
| Next pregnancy Singleton/Twins/Triplets | B156 source + fully-enabled linked validation complete | Cheat Upgrades 0x139-0x13B use mutually exclusive persisted bits 0x20/0x40/0x80. After the stock multiplicity roll, the selected 1/2/3 replaces `CVillager+0x6B1C` and is clamped to the native `EmptyOffspringSlots` result; all stock spawning, achievements, statistics, and Family Tree writes continue. The count bits clear only after native `Impregnate` succeeds. Live 1/2/3-slot boundary and save/reload QA remains. |
| Complete all Achievements cheat | Source + linked build validated | Cheat row 0x12E checks `IsComplete` before calling native `SetComplete` for every currently enabled base/modded prerequisite row, preserving normal coin awards without duplicate payouts. Completing the final prerequisite then awards Achiever Extraordinaire through its normal last-goal observer. |
| Trophy icon for Complete all collections and future cheats | Current rows source + linked build validated | Complete all collections 0x127 and Complete all Achievements 0x12E use the self-contained trophy descriptor. New future cheat rows should alias that descriptor unless given a dedicated asset. |
| Restore F5 debugger selector and native editors | B154 automated + user live confirmed | F5 opens without the prior house-load crash. F4/F5/F6/F7 and Up/Down internal key maps pass all 16 linked layouts; specialized editor edge-case QA remains. |
| Light editor: edit/place/remove sources | Core editor user-confirmed / hardening pending | Native add/delete/save/type-cycle/mouse-drag routes work in game; B154 corrects + and - direction. Persistence/export, cancel/reset, fault handling, and patch-off parity still need narrow QA. |
| Recreate dummied debug tools | Source audit complete; no native route found | `docs/mobile-debug-editor-check.md` records the checked mobile ABIs and desktop objects: no `BehaviorEditor`/`ContentMapEditor` implementation or usable class methods were found. No replacement editor is added without a recovered native contract. |

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
| Mobile-only furniture actions | B158 source + native IDA tree-autonomy extension; live QA pending | Scope is exactly the 63 genuine mobile rows `0x2AA-0x2E8`; all Invisible/custom/VF3 items are excluded. Forty-one original QAMFs are tracked locally and 22 absent maps are explicit. Player testing confirms the Lounge Chair anchor/pose and bad-weather refusal. Good-weather manual drops randomly choose relaxing, reading, studying, sitting, napping, or sleeping with energy-dependent nap/sleep weights. Patio Table and Picnic Table have exact guarded manual prepare/use pairs, PC-safe seat maps, and independent external 240-game-second states for unsafe mobile props `0x56` and `0x55`; children may use either once ready, while manual preparation requires raw age `0x118+` and at least 31 food. Picnic eating preserves three fresh sound/animation rounds and hunger -40. Mobile autonomous pairs `0x1B4-0x1B7` now use the additive external selector with the recovered sunny-day, object, age, health, carried-baby, ready/preparing-state, and need gates plus 3000/12000 base weights. Picnic preference IDs 39 and 40 reproduce the mobile 3x like and 1/4 dislike modifiers. The APK autonomous path has no food-store check, so the manual food warning is not invented there. Christmas Tree autonomous admire `0x19C`, adult watering `0x19E`, and kid-breaking `0x19F` now use exact EObject `0x88` records, native health/stat gates, native plan ports, and the recovered mobile sound IDs; fixing `0x19D` remains unrouted because its activation record is absent. The complete Birthday family includes guarded single-object fallbacks and Birthday Banner whole-household celebration. Holiday Candles, Eggnog, child Santa-cookie stealing, Christmas figurines, and house decorations use the same additive external selector with each exact mobile base weight of 2000 and the proven object and raw-age gates. The selector preserves the native stock conditional distribution and never extends or repurposes the PC table. Adult Santa-cookie rescue remains manual, matching mobile. Candy Canes, Single Cookie, Poinsettia, and both Wreaths are proven decorative-only mobile items: EObject 0, unhandled hotspots `0x60/0x61`, and no item-ID drop fallback. Christmas Trees, Large and Small Stockings, Dreidel, and Menorah have exact guarded plan ports with minimal PC-safe maps. Exact disable restoration is automated; live tree/autonomy, Patio, Picnic, birthday, frequency, timer, interruption, and save/reload QA remain. |
| Praise string-change bug | B156 source + linked validation complete | InvokeReward captures the exact 0x28-byte action label before native plan clearing, awards exact-label goals, and restores the cached label only for the same behavior serial and incremented praise counter. Scold captures exact text before the single native ForgetPlans call. Live repeated-praise/scold QA remains. |

## Cheats and house state

| Request | Status |
|---|---|
| Spawn max house trash / Spawn max weeds | B156 source + combined executable link complete | Cheat Upgrade `0x12F` interleaves ten native `SpawnTrashInHouse(1)`, `SpawnStainInHouse(1)`, and `SpawnSockInHouse(1)` calls because the native indoor pool has 30 shared slots; `0x130` calls native bounded `SpawnWeedsInYard(30)`. Existing collectables are preserved and only available slots are filled. Live purchase/spawn/save QA remains. |
| Max out sock pile / No sock pile | B156 source + fully-enabled linked validation complete | Cheat Upgrade `0x133` calls native bounded `SpawnSockInHouse(0x7FFFFFFF)` and sets the stock sock-pile counter at `theGameState+0x148` to `0x7FFFFFFF`, the requested maximum integer value. No sock pile uses 0 and deliberately does not award sock-laundering achievement progress. Live purchase/visual/save QA remains. |
| Clean House / Clean Garden | B156 source + fully-enabled linked validation complete | Clean Garden item `0x131` calls the exact stock Weed Bomb selector `RemoveAll(0x7D)`. Clean House item `0x135` matches the stock Housekeeping Services event by calling `RemoveAll` with selectors `0x73`, `0x79`, `0x81`, and `0x83`; yard weeds and the separate laundry-room sock pile remain. Live purchase/remove/save QA remains. |
| Spawn Marriage Email | B156 source + fully-enabled linked validation complete | Cheat Upgrade `0x132` is hidden from purchase when the house already has two resident adults, preventing the crash-prone stock candidate path. When eligible, it queues the stock marriage-proposal email enum 2 through `theGameState::QueueEmailMessage`, preserving native duplicate suppression and the ten-slot queue limit, then saves through the common cheat path. Live queue-full, duplicate, eligible-family, two-adult suppression, proposal UI, and save/reload QA remains. |
| Function-sort every Cheat Upgrade | B156 source + fully-enabled linked validation complete; live UI QA pending | Rows are ordered by function: money, food, furniture locks, paired achievement controls, paired collection controls, price multipliers/reset, paired malfunction controls, house trash/Clean House, yard weeds/Clean Garden, sock-pile max/clear, marriage email, forced pregnancy, paired baby gender, then singleton/twins/triplets. Item IDs and effects remain unchanged. |
| Collector Sell All rarity payment and deliberate reset only | Shipped / in-game QA pending |

## Goals and achievements

Exact-action goals trigger only while the named action/variation is current.
Praise/scold must not overwrite it first. Counting goals persist, award once,
and reset only through their documented reset action.

| Group | Status | Requests |
|---|---|---|
| Wealth/food | B156 source + fully-enabled linked validation complete | No More Worries 0x83 awards at the exact native coin ceiling of 4,000,000,000; Solving World Hunger 0x84 awards at the exact food ceiling of 2,147,483,647. All native Set/Adjust callsites are observed, old maxed saves reconcile after load, and Reset Achievements stays cleared until a later resource mutation or reload. Live award/notification/save QA remains. |
| Pets in home | B156 source + fully-enabled linked validation complete | A Furry Companion 0x8A awards for any successfully placed live pet; The Cat's Meow 0x8B is any cat; Man's Best Friend 0x8C is any dog; Slow and Steady 0xA7 is Turtle item 0x245; Itsy Bitsy 0x8D is Tarantula 0x248; Hampster Dance 0x8E is Hamster 0x247; Lovely Lizards 0x8F is Lizard 0x246. Buying into the Tool Tray does not qualify. Failed/full-capacity placement does not award. Successful save loading reconciles only active pets across all 30 native slots. Live placement, notification, reset, save, and reload QA remains. |
| Longevity | B156 source + fully-enabled linked validation complete | Lucky 70's 0x85, Great 80's 0x86, Mighty 90's 0x87, Centenarian 0x88, and Oldest Person in History 0x89 award at exact raw-age thresholds 1400, 1600, 1800, 2000, and 2441 (>122). The annual old-age path observes the raw-age cursor after native food-group calculation but before mortality, independently of the optional mortality flag. Load reconciliation scans the 30 villager records and excludes inactive, left-home, and dead villagers. Live birthday, notification, reset, save, and reload QA remains. |
| Family-tree appearance | B156 source + fully-enabled linked validation complete | Return of the Rainbow 0x90 requires a persistent female (gender 1) family-tree record with head 48; Spiky! 0x91 requires a persistent male (gender 0) record with head 48. All six native record-update calls are observed after the native write. Load reconciliation scans both parents and up to six children across the 30-generation persistent tree, including dead and departed relatives. Live birth/adoption, notification, reset, save, and reload QA remains. |
| LDW paintings/posters | Shipped / automated-verified | IDs 0x60-0x65 award after successful purchases of the six verified LDW art items. Live purchase/notification QA remains. |
| Exact praise: web/games | B156 source + 16-layout linked validation complete; live QA pending | Existing IDs 0x66-0x6A remain exact. IDs 0x98-0xA0 add Sim-ling Rivalry, Blocky Business, Dovahkiin, Reshaping the World, Farming Fanatic, Forum Browser, Explore Collect Compete, Waddle On!, and Pixel Pets. The Poptropicals, Club Puffle, and PetKinz labels were added to the reachable video-game variation table. Near matches do not award. |
| Exact scold: social/child | B156 source + 16-layout linked validation complete; live QA pending | Fakebook Fakery 0x94, Dance Dunce 0x95, The Last Trend 0x96, and child-only Lazy Crazy 0x97 inspect the exact pre-clear action label. The reachable native label is `Posting on Picstagram`; the requested achievement text retains `Clipstagram`. |
| Pet interaction corrections | B156 source + 16-layout linked validation complete; live QA pending | Good boy 0x6B and Bad dog 0x6C inspect exact `Praising pet`/`Scolding pet` labels before native state clearing. Pavlovian Association 0x93 now awards only when the player praises a villager whose exact current action is `Training pet`. It is visible only with Behavior Patches; Achiever Extraordinaire remains final. Live praise, popup, persistence, reset, and patch-off QA remains. |
| Birthday purchases | B156 source + 16-layout linked validation complete | Happy Birthday 0x80 maps Birthday Banner 0x2DB; Not a lie 0x81 maps Birthday Cake 0x2DC; Full of helium 0x82 maps Birthday Balloons 0x2DA. Awards occur only after AddToStorage succeeds; live purchase/save/notification QA remains. |
| Discipline | B156 source + 16-layout linked validation complete; live QA pending | Child-only exact scolds award No clothes-throwing 0xA1, No playing in the toilet 0xA2, No drawing on the wall 0xA3, and No messing with the light switch 0xA4. The stock game already supplies No jumping on the bed. Props to you 0xA5 requires stock Tight Ship 0x30—which itself proves all three stock discipline goals including bed-jumping—plus all four new goals; qualifying saves reconcile on load. |
| Holiday Furniture purchases | Shipped / core purchase goals user-confirmed | Coin awards and purchase-goal firing work in game; exhaustive ID aliases, persistence, and patch-off absence remain narrow QA. |
| VF3 furniture | B156 source + 16-layout linked validation complete; live QA pending | Furnishing the Future 0xA6 awards after a successful purchase of any active VF3 furniture-patch item: six couches/loveseats 0x2F6-0x2FB or three televisions 0x324-0x326. Failed storage purchases do not award. |
| Ornamentologist/collection goals | Shipped / spawn and award user-confirmed | Ornaments spawn and Ornamentologist wiring works in game; exact Lucky Rock weighting is source/link proven. Persistence, live frequency, and every reset path remain narrow QA. |
| Achiever Extraordinaire | B156 source + fully-enabled linked validation complete | ID `0x92` is always the final visible row. Every completion scans the exact selected `achievementOrder`, excluding only itself; compile-gated Ornament/Behavior goals and runtime-gated Holiday Furniture goals count only when visible. Successful save load performs the same reconciliation. Live final-award/popup/save QA remains. |

## Renovations, map, events, and family systems

| Request | Status | Completion contract |
|---|---|---|
| Mobile Kitchen/Office/Workshop/first Bathroom renovations | B157 static renderer and native route validation complete; live QA pending | Fifteen upright, hash-verified mobile room PNGs are local under `work/assets/mobile_renovations/`. The optional toggle registers PC styles `0x13C-0x14A` only in native House Renovations category `0x11` (`gHomeList`/`gHomeListSorted`), expanding that list from 10 to 25; they are absent from Special Upgrades. The renderer draws the complete images 1:1 at the verified Bathroom `(255,1435)`, Kitchen `(930,995)`, Office `(1354,792)`, and Workshop `(500,1400)` anchors from the post-map `theMainScene::DrawScene +0x39` hook. Default-off builds retain the stock map path. Live purchase, switching/removal, save/load, camera, and patch-off visual QA remain. |
| Same remodels for second Bathroom | Blocked on native render evidence | The optional route must reuse the corrected Bathroom 1 art only after a native north-room overlay anchor and state write are proven; the existing `0xE6` malfunction gate remains untouched. |
| Every renovation reversible | B156 source + B157 linked implementation; live QA pending | When Cheat Upgrades is enabled, selecting an owned native renovation `0xE1-0xEA` in the store returns that upgrade, reloads the base `CContentMap`, reapplies every remaining native renovation record from the exact `theGameState::Load` table, and saves. B157 adds the optional style-item removal path and first-owned room selector; live remove/rebuy/switch/save-load and visual QA remain. |
| Expanded map X-1Y0..3 and X4Y0..3 | Removed from B156 scope by user request | No expanded-map patch is exposed. The inactive placeholder and Experimental/Not Working section were removed; no camera, pathing, placement, spawn, or save bounds are changed. |
| VF3 Phone | Indefinite hiatus (user-directed) | No implementation or research is authorized. The existing email system remains unchanged unless the user reopens this item. |
| Mobile Island Events and exact outcomes | B156 source + 16-layout linked validation complete; live QA remains | All 25 added event objects/text remain optional and now follow exact function-level mobile firing, award, and impact evidence. Eight events preserve unconditional mobile `CanFire=false`. Live dialog, targeting, choices/effects, persistence, nonappearance, and patch-off QA remains. |
| Enable Races via VF3 palette/overlay | Indefinite hiatus (user-directed) | No implementation or research is authorized unless the user reopens this item. |
| Same-sex marriage | B156 source + 16-layout linked validation complete; live proposal/save/gameplay QA remains | Default-off `.vf2same` makes each proposal candidate independently female or male through native RNG. The native two-parent family-tree records remain unchanged; guarded spouse-role selectors resolve same-sex couples after acceptance. Established same-sex spouses bypass only the private-action cooldown when dropped on each other, while both normal and cheat-forced pregnancy chances return false before `Impregnate` (0%). Flag-off candidate, selector, cooldown, and pregnancy paths remain stock. All 16 executable layouts link uniquely and all five runtime bytes enable/re-enable/disable without overlap. |
| Multiple candidates per marriage email | B156 source + 16-layout linked validation complete; live QA remains | Reject keeps the active proposal scene open and calls the native candidate generator, which deactivates the rejected temporary villager before displaying one replacement. The stock proposal timestamp/email fields are not cleared. Flag-off replacements remain opposite-sex; `.vf2same` replacements independently choose either gender. Accept remains the untouched native route. |
| VF3-style child adoption chooser | B156 source + 16-layout linked validation complete; live QA pending | Adoption Services now asks for a baby or an older child. Baby uses native internal age 0; older child uniformly chooses displayed age 2-8, and either choice independently uses native `GetRandom(2)` for gender. The native three-argument `SpawnSpecificPeep`, `CVillager::Init`, `CFamilyTree::AddOffspring`, adoption achievements, and stock completion message remain in the route. A pre-spawn capacity check and guarded spawn/tree failures prevent invalid access, and each purchase makes exactly one villager. The desktop implementation is evidence-backed; an exact VF3 implementation match has not been independently established. All 16 executable layouts link uniquely and the five dormant runtime controls still enable idempotently and restore exactly. Live choice-dialog, age/gender, full-family, Family Tree, achievement, and save/reload QA remains. |
| Generation counter beyond 30 | B156 source + 16-layout linked validation complete | Every successful native `StartNextGeneration` call increments a separate 24-bit lifetime counter persisted in hidden achievement record `0xA8` bits 8-31. Existing saves with no counter seed from the current stock generation; failed starts do not increment. The stock 30-record `MakeRoomInTree` rollover is unchanged. The Goals screen draws `Generation: N`, and Reset Achievements preserves the counter while a true new-game achievement reset still clears it. Live generation transition, save/reload, Goals placement, generation 30-to-31 rollover, and new-game reset QA remains. |

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
