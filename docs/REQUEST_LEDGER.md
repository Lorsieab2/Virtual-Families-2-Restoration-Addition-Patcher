# VF2 Restoration + Addition Patcher Request Ledger

Last reconciled: 2026-07-12
Published baseline: B152 (`e5f4047`, release
`B152-restoration-addition-patcher`)

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

## Published B152 baseline

| Request | Status | Evidence / remaining gate |
|---|---|---|
| Holiday Ornaments: 12 mobile IDs, rarity, spawns, sixth page, 72 total, persistence, pickup/drop, Collector integration | Shipped / automated-verified | Linked validators and 16-state matrix; user confirmed spawns. Full save/load and Lucky Rock frequency QA remain. |
| Upright Ornament art and corrected lower-right Candy Cane | Shipped / automated-verified | Canonical sources copied into payload and hash-validated. |
| Page label `Ornaments`, footer strings, Ornamentologist after Bottlologist | Shipped / automated-verified | B152 string/order validator. |
| Holiday Furniture achievement runtime gate | Shipped / in-game QA pending | Exact-SHA `.vf2goal` gate; purchase, award, persistence, and off-state QA remain. |
| Allow Older Pregnancies | Partial | Default-off `.vf2preg` hook ships. Stock under 50; 10% at 50, decreasing to 0.1% floor at 69+; native multiples preserved. Full conception/tutorial/birth/save-load QA remains. |
| Reset Ants; Reset/Complete all collections | Shipped / in-game QA pending | Native/package checks exist; verify awards, reset semantics, Holiday on/off, and save/load. |
| 2x/5x/100x Prices and Reset Price Multiplier | Shipped / in-game QA pending | `CalcPrice` route and saturation are source-verified; broad purchase QA remains. |
| Trigger/Fix malfunctions, Router state, dryer fire, north leaks | Shipped / in-game QA pending | Props and renovation gates linked; gameplay/repair/Handyman/Water Surge QA remains. |
| Rebuy Maid/Gardener to fire and Rockhound/Anti-Spam to remove | Shipped / in-game QA pending | Source route exists; active-flag/save/rebuy QA remains. |
| B150 behavior variations and gates | Needs source audit | Audit the whole age/weather/nursing/gender/manual/autonomous matrix. |
| Compatibility/creator GUI messages | Shipped / automated-verified | Exact constants exist in exporter and GUI and are covered by GUI/exporter tests. |
| Brokerage Account 11% message | Shipped / in-game QA pending | Exact native store description exists; verify its visible wrapping/layout in game. |

## B153 priority

| Request | Status | Completion contract |
|---|---|---|
| Fully working Allow Older Pregnancies | Partial | Prove stock parity under 50, decimal curve, tutorial route, Wants Kids/perfumes, multiples, birth, save/load, and extreme ages. |
| Older Villagers mortality curve | Partial | Default-off `.vf2mort` source hook now replaces only the birthday old-age roll: normal survival curve centered at effective age 75, nutrition shift 0-4 years, 0.02% rare tail, and no hard maximum. COFF and exact-SHA exporter tests pass; linked-matrix and live aging/save/time-away QA remain before release. |
| Next Generation button around age 60 with age patch | Not started | Gated only with the age patch; stock flow when off. |
| Increase Child Limit to 12 | Not started | Safely widen birth/adoption storage, household/save records, Family Tree layout, all 12 Next Generation candidates, transition, and compatibility. |
| Force Successful Pregnancy | Not started | Next eligible attempt never argues and succeeds; clear after resulting birth. |
| Next babies Male/Female | Not started | Saved mutually exclusive one-shot applying to every baby in next birth; clear after birth. |
| Next pregnancy Singleton/Twins/Triplets | Not started | Saved mutually exclusive, cap-safe one-shot; clear after birth. |
| Complete all Achievements cheat | Not started | Normal completion/award semantics; enabled base/modded rows; no duplicate awards; Achiever Extraordinaire last. |
| Trophy icon for Complete all collections and future cheats | Needs source audit | Change requested row and use trophy as fallback when no dedicated icon exists. |
| Restore F5 debugger selector and native editors | Partial | Evidence confirms CDebugger, Waypoint, and Light Source editors. Previous main-scene hooks crashed saves; rebuild default-off and key/display-first. |
| Light editor: edit/place/remove sources | Not started | Verify add/move/delete, feedback, persistence/export, cancel/reset, and patch-off behavior. |
| Recreate dummied debug tools | Needs source audit | Behavior/Content Map editors are absent in checked binaries; replacements require verified engine contracts. |

## Behaviors and variations

| Request group | Status | Notes |
|---|---|---|
| `Needs to sit down` spontaneous plus thinking/resting/phone/texting/scrapbooking variations and all age/gender/relationship gates | Needs source audit | Verify records, age unit, spontaneous eligibility, locations, and stock-weight parity. |
| `Ironing clothes` and `Mending a button` spontaneous | Needs source audit | Verify plan registration and patch-off state. |
| `Petting` not spontaneous | Needs source audit | Manual route remains; only autonomous eligibility changes under patch. |
| `Checking weight` spontaneous for all ages | Needs source audit | Verify safe all-age route and location. |
| Nursing actions: first words, walking, talking, feeding, lullabies, playing, admiring, peek-a-boo, kissing, pictures | Needs source audit | Require nursing mother with baby; preserve base frequencies. |
| Browsing web: buying online (13+), watching/making/posting memes, cat videos, VideoTube, game/social variations | Needs source audit | Audit ages and exact-action praise goals. |
| Taking a nap dream variations | Needs source audit | Beach, snow, holidays, vacations, rollercoasters, mountains, camping, family trips, countryside, LDW games, Isola, city, forest, unicorns, fish, jungles, tropical islands, skyscrapers, space, treasure, wealth, adventures, swimming, flying, falling, discovery. |
| Snowy-weather actions | Needs source audit | Identify every ported/requested action and prove weather-only eligibility. |
| Bathroom sink actions; jewelry for females 14+ | Needs source audit | Every sink route/variation must be Behavior-Patches gated. |
| Manual `Play video games` on computer drop | Not started | Add beside Browsing web/verified computer routes without changing autonomous likelihoods. |
| Experimental mobile-only furniture actions | Partial | Audit recognition, routes, gating, animation/location, and base parity. |
| Praise string-change bug | Needs source audit | Preserve exact action/variation text and let goals inspect it before praise changes state. |

## Cheats and house state

| Request | Status |
|---|---|
| Spawn max house trash / Spawn max weeds | Not started |
| Max out sock pile / No sock pile | Not started |
| Clean House / Clean Garden | Not started |
| Spawn Marriage Email | Not started |
| Function-sort every Cheat Upgrade | Partial |
| Collector Sell All rarity payment and deliberate reset only | Shipped / in-game QA pending |

## Goals and achievements

Exact-action goals trigger only while the named action/variation is current.
Praise/scold must not overwrite it first. Counting goals persist, award once,
and reset only through their documented reset action.

| Group | Status | Requests |
|---|---|---|
| Wealth/food | Not started | No More Worries; Solving World Hunger. |
| Pets in home | Not started | A Furry Companion; Cat's Meow; Man's Best Friend; Itsy Bitsy; Hampster Dance; Lovely Lizards. |
| Longevity | Not started | Lucky 70's; Great 80's; Mighty 90's; Centenarian; Oldest Person in History (>122). |
| Family-tree appearance | Not started | Return of the Rainbow (female head 48); Spiky! (male head 48). |
| LDW paintings/posters | Not started | Portal to Paradise; LDW Fan; Palm Pioneer; Caring Soul; Spin-off Specialist; The Adventures Never End. |
| Exact praise: web/games | Not started | Nyan Cat; Like and Subscribe; VF-Inception; Isolan Refugees; Memz; Sim-ling Rivalry; Blocky Business; Dovahkiin; Reshaping the World; Farming Fanatic; Forum Browser; Explore, Collect, Compete (Playing Poptropicals); Waddle On! (Playing Club Puffle); Pixel Pets (Playing PetKinz). |
| Exact scold: social/child | Not started | Fakebook Fakery; Dance Dunce; The Last Trend; Lazy Crazy. |
| Pet interaction corrections | Not started | Good boy = praise someone praising pet; Bad dog = praise someone scolding pet; Pavlovian Association = praise someone training pet. |
| Birthday purchases | Not started | Happy Birthday banner; Not a lie cake; Full of helium balloons. |
| Discipline | Not started | No clothes-throwing; no toilet play; no bed jumping; no wall drawing; Props to you after Tight Ship plus those four. |
| Holiday Furniture purchases | Shipped / in-game QA pending | Audit valid IDs/names, coins, persistence, and patch-off absence. |
| VF3 furniture | Not started | Furnishing the Future. |
| Ornamentologist/collection goals | Shipped / in-game QA pending | Verify award/counters/persistence and all reset paths. |
| Achiever Extraordinaire | Not started | Final visible goal; requires every enabled base/modded goal. |

## Renovations, map, events, and family systems

| Request | Status | Completion contract |
|---|---|---|
| Mobile Kitchen/Office/Workshop/first Bathroom renovations | Not started | Curate owned art into workspace; store rows/icons/prices, exact overlays, saved choice, switching/removal, off-state. |
| Same remodels for second Bathroom | Blocked on owned asset/native evidence | Blue mockup is reference; generate self-contained north-room assets for every shipped theme while preserving malfunction routes. |
| Every renovation reversible | Not started | Clear active flags, allow remove/switch/rebuy, persist safely. |
| Expanded map X-1Y0..3 and X4Y0..3 | Not started | Same tile size, owned grass art, expanded camera/pathing/click/spawn/furniture/save bounds. |
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
