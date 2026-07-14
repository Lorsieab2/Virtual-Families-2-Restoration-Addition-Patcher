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
| Fully working Allow Older Pregnancies | Partial / linked validation complete | All 16 layouts pass flag, detour, helper, stock-fallback, exact-SHA, and reversible-toggle checks. Live proof remains for stock parity under 50, decimal curve outcomes, tutorial route, Wants Kids/perfumes, multiples, birth, save/load, and extreme ages. |
| Older Villagers mortality curve | Partial | Default-off `.vf2mort` source hook replaces only the birthday old-age roll: normal survival curve centered at effective age 75, nutrition shift 0-4 years, 0.02% rare tail, and no hard maximum. All 16 linked layouts and exact-SHA toggle cycles pass; live aging/save/time-away QA remains before release. |
| Next Generation button around age 60 with age patch | Not started | Gated only with the age patch; stock flow when off. |
| Increase Child Limit to 12 | Partial | Native audit complete: live `CVillagerManager` already has 30 ordinary peep slots, but each generation persists only six `SPeepRecord`s and the Next Generation scene owns two six-entry candidate arrays. A safe implementation needs additive persistence for six extra records per generation plus matched Family Tree draw/hit-test and candidate-array detours; changing the limit constant alone would overwrite the next generation. |
| Force Successful Pregnancy | Not started | Next eligible attempt never argues and succeeds; clear after resulting birth. |
| Next babies Male/Female | Not started | Saved mutually exclusive one-shot applying to every baby in next birth; clear after birth. |
| Next pregnancy Singleton/Twins/Triplets | Not started | Saved mutually exclusive, cap-safe one-shot; clear after birth. |
| Complete all Achievements cheat | Not started | Normal completion/award semantics; enabled base/modded rows; no duplicate awards; Achiever Extraordinaire last. |
| Trophy icon for Complete all collections and future cheats | Needs source audit | Change requested row and use trophy as fallback when no dedicated icon exists. |
| Restore F5 debugger selector and native editors | B153 built / visible live retest pending | The +6 fallthrough fix passes live house load. F5 was then confirmed ignored because the helper omitted VF2's internal codes. B153 now recognizes F4 0x3FD, F5 0x3FE, F6 0x3FF, F7 0x400, Up 0x3EE, and Down 0x3EF; all 16 layouts pass linked hook/key-map validation. Visible overlay/editor QA remains. |
| Light editor: edit/place/remove sources | Partial | Native L add, D delete, S save, type-cycle, and mouse-drag routes are wired in the default-off developer build. Verify feedback, persistence/export, cancel/reset, fault handling, and patch-off behavior in game. |
| Recreate dummied debug tools | Needs source audit | Behavior/Content Map editors are absent in checked binaries; replacements require verified engine contracts. |

## Behaviors and variations

| Request group | Status | Notes |
|---|---|---|
| `Needs to sit down` spontaneous plus thinking/resting/phone/texting/scrapbooking variations and all age/gender/relationship gates | Partial / linked validation | `Needs to sit down` is registered all-ages at weight 450 only under Behavior Patches, and all 16 layouts preserve the gate. Variation age/gender/relationship/location sampling and live stock-weight parity remain. |
| `Ironing clothes` and `Mending a button` spontaneous | Shipped / automated-verified | Adult-only helper uses native age-unit minimum `0x118` (displayed age 14+) and registers Ironing at weight 700; linked 16-layout validation confirms patch-on presence and patch-off absence. Live frequency QA remains. |
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
| Discipline | Not started | No clothes-throwing; no toilet play; no bed jumping; no wall drawing; No messing with the light switch! (scold a child for switching the light on and off); Props to you after Tight Ship plus all five additional discipline goals. |
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
