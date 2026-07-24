# B156 Mobile Furniture Behavior Ledger

## Scope

The optional **Mobile Furniture Behaviors** patch covers only the 63 furniture
records recovered from Virtual Families 2 mobile, PC item IDs `0x2AA` through
`0x2E8` inclusive.

It explicitly excludes:

- every patcher-created Invisible furniture item;
- colorful couch variants;
- LDW posters;
- VF3 furniture imports.

Those additions may keep their existing desktop donor routes, but they are not
mobile-exclusive VF2 furniture and do not count toward this patch.

## Current implementation boundary

All 63 items receive a copied desktop donor click-table byte, but that alone
does not establish the correct mobile action. The base payload deliberately
zeroes unsupported furniture-map cells, leaving unresolved families
rendered-only. The optional patch now replaces 34 proven PC-safe maps, including
the four lounge chairs, Patio Umbrella, Patio Table, Picnic Table, birthday
family, and implemented Holiday families, and enables their exact guarded
manual-drop behaviors.

The supplied mobile OBB contains original QAMF furniture maps for 41 of the 63
items. Exact copies are now preserved under
`patcher_assets/optional_patches/mobile_furniture_behaviors/mobile_fmaps`. The
remaining 22 items have no per-item mobile QAMF in that OBB. Build generation
records both sets in `MobileFurnitureBehaviorEvidence` and fails if the exact
`0x2AA-0x2E8` scope or 41/22 split changes.

Raw mobile QAMF files must not be installed into the desktop content map. Their
mobile-only marker values do not have corresponding handlers in the desktop
`HotSpot.obj`.

## Family ledger

| PC IDs | Mobile furniture | QAMF evidence | Recovered mobile action family | Desktop status |
|---|---|---:|---|---|
| `0x2AA` | Holiday Candles | yes | `KidExaminesCandles` | exact child-only manual route implemented with PC-safe map; autonomous candidate pending |
| `0x2AB` | Candy Canes | yes | no mobile behavior | proven decorative only: EObject 0, unhandled hotspot 0x61 |
| `0x2AC` | Christmas Cookie | yes | no mobile behavior | proven decorative only: EObject 0, unhandled hotspot 0x61 |
| `0x2AD-0x2AE` | Christmas Trees | yes | `XmasTree`; admire, water, celebrate | exact whole-household manual celebration implemented with two PC-safe maps |
| `0x2AF` | Dreidel | yes | exact `Dreidel` hotspot/behavior | exact whole-household external plan implemented with PC-safe map |
| `0x2B0` | Eggnog | yes | exact `Eggnog` family | exact child-only manual route implemented with PC-safe map; autonomous candidate pending |
| `0x2B1-0x2B5` | Holiday gnomes | yes | `AdmiringXmasKnickKnacks` | exact raw-age-7+ manual route implemented with five PC-safe maps |
| `0x2B6-0x2B7` | Large Angel and Large Star | no | no per-item route proven | decorative |
| `0x2B8` | Menorah | yes | exact `Menorah` hotspot/behavior | exact whole-household external plan implemented with PC-safe map |
| `0x2B9-0x2BC` | Ornaments | no | no per-item route proven | decorative |
| `0x2BD` | Penguin Decoration | yes | `AdmiringXmasKnickKnacks` | exact raw-age-7+ manual route implemented with PC-safe map |
| `0x2BE` | Plate of Cookies | yes | adult-save/kid-steal Santa-cookie family | exact age-routed manual pair implemented with PC-safe map; child autonomous candidate pending |
| `0x2BF` | Poinsettia | yes | no mobile behavior | proven decorative only: EObject 0, unhandled hotspot 0x60 |
| `0x2C0`, `0x2C2-0x2C3`, `0x2C5` | Polar bear, reindeer, garden Santa, and snowman | yes | `AdmiringXmasKnickKnacks` | exact raw-age-7+ manual route implemented with four PC-safe maps |
| `0x2C1`, `0x2C4` | Red Bow and Santa Wall Decoration | yes | `InteractHouseXmasDecor` | exact adult-only manual route implemented with two PC-safe maps |
| `0x2C6-0x2C7` | Stockings | yes | exact `XmasStockings` / `KidsCheckXmasStockings` | exact under-18 manual route implemented with two PC-safe maps |
| `0x2C8-0x2C9` | Garlands | yes | `InteractHouseXmasDecor` | exact adult-only manual route implemented with two PC-safe maps |
| `0x2CA-0x2D2` | Thanksgiving food | no | no Thanksgiving-specific hotspot or behavior recovered | decorative |
| `0x2D3` | Holiday Welcome Mat | no | stock desktop Welcome Mat exists; no exclusive action proven | existing donor only |
| `0x2D4-0x2D5` | Wreaths | yes | no mobile behavior | proven decorative only: EObject 0, unhandled hotspot 0x61 |
| `0x2D6-0x2D7` | Designer Soap | no | no exclusive route proven | existing soap donor only |
| `0x2D8-0x2D9` | Towel Sets | no | `UsingWarmTowel` is already native on PC and mobile at behavior `0xE7` / EObject `0x50` | no towel-item binding exists; decorative, no added route |
| `0x2DA` | Birthday Balloons | yes | `BirthdayBalloons`; play/maybe play | exact child-only manual route implemented with PC-safe map |
| `0x2DB` | Birthday Banner | yes | `BirthdayBanner`; celebration family | exact object scan, fallbacks, and whole-household external plan implemented |
| `0x2DC` | Birthday Cake | yes | `BirthdayCake`; poke/maybe poke | exact child-only manual route plus grouped fallback implemented |
| `0x2DD` | Birthday Presents | yes | `BirthdayPresents`; poke/maybe poke | exact child-only manual route plus grouped fallback implemented |
| `0x2DE-0x2E1` | Lounge Chairs | yes | `Chaise`; `LieOnChaiseNoLeadIn` | implemented as the first optional family; exact plan sequence and PC-safe placed-item maps |
| `0x2E2-0x2E3` | Floor Lamps | no | no exclusive route proven | decorative |
| `0x2E4-0x2E5` | Patio surfaces | yes | patio context only | no per-surface action assigned |
| `0x2E6` | Patio Table | yes | `PatioChairs`; prepare/drink family | exact guarded manual prepare/drink routes implemented with two seats and external prop `0x56` |
| `0x2E7` | Patio Umbrella | yes | `PatioUmbrella`; `AdjustingUmbrella` | implemented as the second optional family; exact direct plan sequence and PC-safe placed-item map |
| `0x2E8` | Picnic Table | yes | `PicnicTable`; prepare/eat picnic | exact guarded manual prepare/eat routes implemented with four seats and external prop `0x55` |

## Patio QAMF finding

`Patio_table.png.fmap` is a 19 by 17 primary content block. Its functional
mobile markers were translated into a PC-safe optional map containing EObject
`0x98` plus two proven seat anchors. The raw mobile hotspot metadata remains
excluded because the desktop hotspot table is smaller.

The exact manual Preparing Drinks and Drink at Patio Chair plans are emitted
outside the fixed desktop behavior table. Mobile prop `0x56` is held in an
external 240-game-second state and is never indexed through the smaller PC
environment array. Mobile autonomous IDs `0x1B6-0x1B7` remain unindexed.

## Picnic Table implementation

Picnic Table item `0x2E8` uses EObject `0x97`. Its `22x16` PC-safe optional
QAMF retains anchors `(10..13,15)` and four translated seat markers at `(5,9)`,
`(8,11)`, `(17,10)`, and `(15,12)` while removing mobile hotspot `0x6B`.
The map hashes to
`3d3aaeeeb77e7842cc20be211d8bcf415f85e6d8c6cd0e0f860a934c6cc45060`.

The guarded manual port preserves the adult/raw-age `0x118` and food `31`
preparation gates, child and low-food DealerSay refusals, bad-weather refusal,
random food carry `0x0D-0x13`, kitchen and table work sequence, basket `0x40`,
sound `0xC7`, exact stat changes, and external 240-game-second prop `0x55`.
While ready, any age can eat. The linked-seat route performs three fresh random
sounds `0x6A-0x6C` and three fresh 10-17 chair animations, with exact
orientation/marker selection between `Sit In Chair NW` and `Sit In Chair NE`,
then applies hunger -40, dirtiness +4, and poo +6. Mobile autonomous IDs
`0x1B4-0x1B5` remain deliberately unindexed.

## Implemented architecture

The optional patch uses a default-zero `.vf2beh` runtime byte and a single
relocation-only wrapper at `theMainScene::DropVillager`. The wrapper calls the
stock `HandleDropOnHotSpot` first. Only a stock miss, an enabled flag, and an
explicit implemented mobile item ID can reach an added handler; every other path
returns to the unchanged stock fallback. The fixed desktop behavior table
(`0x19B` entries) and hotspot table (`0x5D` entries) do not grow.

The lounge handler ports mobile `CBehavior::LieOnChaiseNoLeadIn`: it uses
`LinkPeepToFurniture` object `0x95`, preserves the weather and unreachable
refusals, selects the mobile wait/lie pose from furniture orientation, and
applies the recovered dirtiness, happiness-trend, and energy changes. Its four
optional QAMFs preserve the mobile dimensions/origin/trailer but retain only the
11 proven chaise EObject cells using the PC-safe value `0x2000A800`, plus the
required peep-slot EObject `0x13` anchor at `(8, 6)` translated from mobile
`0x01B09800` to desktop `0x00009800`. Without that anchor the desktop
`FindPeepSlot` path rejects every chair. Mobile refusal string IDs are also
translated: unreachable-seat uses stock PC ID `0xB7`, while the exact mobile
bad-weather text is appended as a dedicated PC string. Disabling the patch
restores the exact rendered-only base maps.

The Patio Umbrella handler ports mobile `CBehavior::AdjustingUmbrella` exactly:
go to EObject `0x96`, wait once in body position `0x0D`, repeat the same go/wait,
then wait for three ticks in body position `0` with direction/head direction
`3`, and start the next behavior. It has no mobile predicate, RNG, stat change,
or autonomous route. Its 15 by 17 optional QAMF retains only the four proven
EObject cells using PC-safe value `0x2000B000`; mobile-only markers
`0x01B40000` and `0x01AC0000` are excluded.

## Birthday family status

The four birthday hotspots and their object IDs are proven: Banner `0x91`,
Balloons `0x92`, Presents `0x93`, and Cake `0x94`. Balloons, Presents, and Cake
all delegate through `AllPeepsCelebratingBirthday`; Banner is always a grouped
celebration. When Banner exists or more than one birthday object is placed, the
mobile build makes every villager run behavior `0x1AF`. That behavior and the
other birthday IDs `0x1AD-0x1B3` are beyond the fixed desktop table ending at
`0x19A`.

The child-only manual Birthday Cake and Birthday Presents subsets are now
ported without using the
out-of-range behavior table. Item `0x2DC` uses a minimal PC map containing only
EObject `0x94`; raw age values through `0x117` run the exact recovered Poking
cake plan, while older villagers consume the drop without starting the child
action, matching mobile. The plan preserves the native voice-dependent `GetOh`
sound calculation, random 2-5 cheer and wait durations, orientation-dependent
body pose, and final two-count clockwise joy twirl. Item `0x2DD` uses a minimal
EObject `0x93` map and the exact Checking out the presents sequence: alternating
orientation-aware waits, recovered random birthday sounds, work/bend phases,
the final body waits, sound stop, and behavior completion.

The child-only Birthday Balloons route is now emitted directly without indexing
mobile behavior `0x1AD`. It preserves localized desktop StringId `0xF0`,
the ignored `FindFurniture` return plus EObject `0x92` result check, the common
three-jump lead-in, three or four repeated balloon approaches, and all six
random mobile branches including `StompingE`/`StompingW`, clockwise and
counterclockwise twirls, voice sounds, and the case-specific EObject `0x1F`
approach. Its `11x14` PC-safe map keeps `0x20009000` only at `(5,13)`,
`(6,13)`, and `(7,13)` and hashes to
`f66e4dc4776962b32b68e069a133ca9b1a7f57306d7df357866dd2630c307fc3`.
The executable compiles and links; live child/age-boundary and six-branch QA
remain.

Birthday Banner now preserves the complete mobile
`AllPeepsCelebratingBirthday` contract. It scans Banner, Balloons, Presents, and
Cake in that fixed order. Banner presence or more than one birthday object sends
every eligible permanent resident through the exact `Celebrating birthday`
plan; exactly one non-banner object uses the existing exact Balloons, Presents,
or Cake handler; zero objects forgets the triggering villager's plans. The
family route uses guarded external plans and never indexes mobile behavior IDs
`0x1AE` or `0x1AF`.

The Banner's `14x16` PC-safe map keeps EObject value `0x20008800` only at
`(7,14)`, `(8,14)`, `(9,14)`, `(7,15)`, `(8,15)`, `(9,15)`, and `(10,15)`;
SHA-256 is
`071c79932b55f382e3fe12be01a32f673ae9726339bd4295be3b35bf78456feb`.
Live mixed-decoration precedence, family filtering, placement, and orientation
QA remain. Autonomous-style Maybe callbacks remain excluded because their
selector reachability is not proven.

## Whole-household Dreidel and Menorah

Christmas Tree `0x2AD` and Lighted Christmas Tree `0x2AE` share EObject
`0x88`. Their exact manual hotspot sends all eligible permanent residents
through `Celebrating around the tree`. The external plan preserves three
randomized approaches, age/gender voice selection, sound `0xFB`, two twirls,
four jumps, orientation-aware waits, and sound stop without indexing mobile
behavior `0x1A0`.

The `15x22` Tree 1 map retains fourteen `0x20004000` EObject cells and hashes
to `5907f7f60209d77d6c63b15b009243756c9f2c4d729134c41c105e0863b66926`.
The `16x22` Tree 2 map retains thirteen matching EObject cells and hashes to
`289e237d686f164dfd3e2293aeac248f5259e700125d963b4b578cefd642ccc8`.
Live two-tree placement, group filtering, and orientation QA remain.

Dreidel `0x2AF` / EObject `0x8A` and Menorah `0x2B8` / EObject `0x8E`
use the mobile whole-household contract. The desktop port collects exactly the
30 permanent household slots first, excludes nonexistent, away, and zero-health
residents, then applies each exact external plan. It does not pass mobile
behavior IDs `0x1A2` or `0x1A3` through the desktop table ending at `0x19A`.

Dreidel preserves the exact `Playing Dreidel` label, randomized approach point,
seven two-way rounds, body poses, and sounds. Its `12x8` PC-safe map retains
`0x20005000` only at `(5,5)`, `(6,6)`, `(7,6)`, and `(8,6)`; SHA-256 is
`44f21fc628cd90090f3eaf8eb1925de8d890fa5239828f55d115ae37c453b36a`.

Menorah preserves `Celebrating Hanukkah`, three randomized approaches,
age/gender voice selection, sound `0xFB`, orientation-aware waits, twirls, four
jumps, and sound stop. Its `10x11` PC-safe map retains `0x20007000` only at
`(7,7)`, `(6,8)`, and `(4,9)`; SHA-256 is
`352ba4be943eae6a168a133430ccd6555c5feb41a630c118da2d24c019e39365`.
Both routes compile and link; live multi-resident, missing/away/dead resident,
placement, and orientation QA remain.

## Christmas Stockings subset

Large Stocking `0x2C6` and Small Stocking `0x2C7` share EObject `0x90`.
The exact mobile manual route consumes every drop, permits raw ages through
`0x167` (displayed age under 18), and has no weather, time, or gender gate.
It uses the exact label `Checking for stocking stuffers`, three randomized
horizontal approach points, the recovered child/gender voice selection, the
orientation-dependent wait poses, four jumps, work phases, sound stop, and
behavior completion.

The PC-safe maps preserve their mobile headers and trailers but keep only
EObject value `0x20008000`: Large at `(6,12)` and `(7,12)`, SHA-256
`f467c400f7ae60efea0ab67ccb33d5ec9327a94383102f750e20dd29d70165a0`;
Small at `(4,10)` and `(5,10)`, SHA-256
`aa6eee69ecaedcaa03575d6bb916e4442cfc83efda41f6e3a8291371475e8003`.
The generated helper and executable link successfully. Live placement,
orientation, age-boundary, and voice QA remain.

## Holiday Candles

Holiday Candles `0x2AA` use mobile EObject `0x89`. Mobile
`CVillager::InitAI` identifies `KidExaminesCandles` as behavior `0x19B`, with
weight `2000`, object `0x89`, and the child boundary field `0x118`. Because
`0x19B` lies beyond the desktop behavior table ending at `0x19A`, B156 ports
the exact manual action externally and does not index the mobile autonomous
candidate.

The guarded route accepts raw ages through `0x117`, uses the exact
`Playing with holiday candles` label, two orientation-aware candle inspections,
sounds `0x3D`, and the exact 30-percent follow-up. That branch selects the
mobile `(age selector 2, gender 1)` random villager, pauses that villager,
approaches at offset `(20,75)`, and preserves sounds `0x3C`, `0x12C`, and
`0x37`. If no matching villager exists, the original EObject `0x1A` / prop
`0x10` fallback is retained.

The `8x9` PC-safe map preserves the mobile header and trailer and retains only
EObject value `0x20004800` at `(5,7)`, `(6,7)`, and `(5,8)`. Its SHA-256 is
`80d3f61d48e59fd55684edfb205670289fa6b15ba9768624ae318849a9f0bc11`.
Live placement, orientation, age-boundary, random-adult, no-adult fallback,
and disable-restoration QA remain.

## Plate of Cookies

Plate of Cookies `0x2BE` use EObject `0x8F`. Mobile behavior `0x1A5`
`KidStealsSantasCookies` is an enabled child candidate with weight `2000`,
object `0x8F`, and boundary field `0x118`; behavior `0x1A6`
`AdultsSaveSantasCookies` is not an autonomous candidate. B156 therefore
chooses the exact child or adult plan by raw age on manual drop without
indexing either mobile-only behavior ID through the desktop table.

Children through raw age `0x117` use `Stealing Santa's cookies`, speed `140`,
orientation-aware head turns, the exact random waits, and sounds `0x36`,
`0xC5`, and `0x6A`. The route asks `GetRandomVillager(2,-1,0)` for an adult
of either gender. When present, that adult switches to
`Rescuing Santa's cookies`, uses gender-specific sounds `0x8C/0x99` and
`0x23/0xDC`, approaches at speed `350`, inspects the plate, stops sound, and
returns to normal behavior. The child then goes to EObject `0x16`, works for
3-5 ticks, and completes the original plan. Adults dropped directly on the
plate use the shorter exact rescue plan.

The `9x9` PC-safe map preserves its mobile header/trailer and retains only
EObject value `0x20007800` at `(6,8)` and `(7,8)`. Its SHA-256 is
`cb0bd7dfc1d1c32fed6c0219c52cc677e61375ad8146b5802c1efa1223a4d0d2`.
Live child/adult boundary, orientation, rescuer-present/absent, sound, map
placement, and disable-restoration QA remain.

## Eggnog

Glass of Eggnog `0x2B0` uses mobile EObject `0x8B`. Mobile
`CVillager::InitAI` enables `CBehavior::Eggnog` as behavior `0x1A1`, with
weight `2000`, object `0x8B`, furniture required, and the child boundary field
`0x118`. Because `0x1A1` lies beyond the desktop behavior table, B156 ports
the exact manual child action externally and leaves spontaneous selection
pending.

Raw ages through `0x117` use the exact label `Stealing egg nog`. The plan
preserves the orientation-aware inspection, sounds `0x6D` and `0x3D`, random
waits, three speed-350 trips to EObjects `0x70`, `0x15`, and `0x59`, twelve
jumps, clockwise joy twirl, clockwise and counterclockwise plan twirls, and
the final 4-13 tick wait. It makes no stat changes and does not stop a sound.
Older manual drops are consumed without starting the child action, matching
the mobile age gate.

The `7x6` PC-safe map preserves its mobile header and trailer and retains only
EObject value `0x20005800` at `(3,5)` and `(4,5)`. Its SHA-256 is
`22562ac31d52fcf4bb6b786423653566483166091c87255ca5e304d623a9b792`.
Live child/age-boundary, orientation, movement-target, sound, placement, and
disable-restoration QA remain.

## Christmas figurines and house decorations

The mobile QAMFs prove EObject `0x8C` on ten items: gnomes `0x2B1-0x2B5`,
Penguin Decoration `0x2BD`, Polar Bear Decoration `0x2C0`, Reindeer
Decoration `0x2C2`, Santa Decoration `0x2C3`, and Snowman `0x2C5`. Mobile
behavior `0x1A4`, `AdmiringXmasKnickKnacks`, is enabled at weight `2000`,
requires raw age `7+`, and uses the exact label `Enjoying the figurines`.
The external PC plan preserves the object lookup, approach, villager Oh sound,
random cheer and orientation-aware wait, two-count joy twirl, and behavior
completion.

EObject `0x8D` is present on Red Bow `0x2C1`, Santa Wall Decoration `0x2C4`,
Holiday Garland `0x2C8`, and Lighted Garland `0x2C9`. Mobile behavior `0x1A7`,
`InteractHouseXmasDecor`, is enabled at weight `2000` with adult minimum
`0x118`. Its exact `Checking the decorations` plan preserves both approaches,
gender sounds `0x8C/0x99` and `0xCC/0xD3`, sounds `0xB5` and `0xE8`, both
random work phases, the orientation-aware wait, sound stop, and completion.

All fourteen PC-safe maps preserve their mobile dimensions, headers, and
trailers, zero every unsupported cell, and restore only the proven EObject
anchors as `0x20006000` or `0x20006800`. Mobile behavior IDs `0x1A4` and
`0x1A7` remain outside the fixed PC behavior table, so spontaneous selection
remains pending rather than indexing an invalid slot.

## Decorative-only Holiday items

Mobile `CContentMap::GetObject` decodes
`((cell >> 11) & 0x7F) | ((cell >> 22) & 0x80)`, while `GetHotSpot` decodes
`(cell >> 18) & 0x7F`. Every nonzero cell in Candy Canes `0x2AB`, Single
Cookie `0x2AC`, Poinsettia `0x2BF`, and Wreaths `0x2D4-0x2D5` therefore has
EObject `0`. Candy Canes, Single Cookie, and both Wreaths contain only
`0x01840000`, which decodes to hotspot `0x61`; Poinsettia contains only
`0x01800000`, which decodes to hotspot `0x60`.

The exact mobile `CHotSpot` constructor leaves handlers `0x60` and `0x61`
null. `theMainScene::DropVillager` obtains only the content-map hotspot and
calls `CHotSpot::Dispatch`; it never checks the furniture item ID. A null
handler returns false. These five items are thus source-proven decorative
furniture on mobile, not missing villager behaviors. B156 deliberately creates
no PC behavior map or invented action for them.

Player testing on 2026-07-23 confirms the exact manual chaise pose/anchor works
in good weather and the dedicated bad-weather refusal fires correctly. Manual
drops now choose randomly among Relaxing on lounger, Reading a book, Studying
on the lounger, Needs to sit down, Taking a nap, and Getting some sleep. The
four awake choices each have weight 20. Native energy is the clamped 1-100
integer at `CVillager+0x6B28`; lower means more exhausted. Nap weight is
`max(0, 70-energy)` and sleep weight is `max(0, 45-energy)*3`, so neither tired
choice can occur at high energy and full sleep increasingly dominates severe
exhaustion. Nap retains the native random 7-11 energy gain and dirtiness +2;
sleep retains the native adult-sleep energy +10 and dirtiness +2. This weighted
manual chooser is a requested desktop extension layered over the recovered
mobile chaise anchor/pose, not a claim about mobile's drop dispatcher.

The optional lounge family also adds four runtime-gated autonomous candidates
without growing the fixed behavior table. `ReadingBook` (`0x12B`, weight 1500) and
`NappingCouch` (`0x83`, weight 3000) retain their good-weather chaise branches.
Reading preserves the recovered mobile 30-percent roll; nap scales from zero at
energy 70 to that 30-percent maximum at energy 1. Desktop `RestingBody` (`0x127`, weight 2000) is the
safe in-range carrier for the mobile Sunbathing plan and the native Needs to sit
down outcome: daytime chooses between them, while nighttime permits only sitting.
`StudyingOnPatio` (`0xC2`, weight 450) carries the requested
`Studying on the lounger` extension; that label and weight are patch choices, not
claims of an exact mobile chaise-study route. With `.vf2beh` zero, each constructor
wrapper returns to its stock desktop target (or the existing Behavior Patches label
wrapper for that build). Rain, storm, fog, and snow reject all outdoor-chair
branches; the stock behavior then remains in control.

Future disruptive household-wide celebration behaviors remain manual-drop-only.
