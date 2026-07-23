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
rendered-only. The optional patch now replaces only the five proven maps for
the four lounge chairs and Patio Umbrella, and enables their exact manual-drop
behaviors through a guarded dispatcher.

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
| `0x2AA` | Holiday Candles | yes | `KidExaminesCandles` | handler absent; rendered-only |
| `0x2AB` | Candy Canes | yes | generic Christmas decor/knickknack family only | exact route unresolved |
| `0x2AC` | Christmas Cookie | yes | Santa-cookie family exists | exact single-cookie route unresolved |
| `0x2AD-0x2AE` | Christmas Trees | yes | `XmasTree`; admire, water, celebrate | handlers absent; rendered-only |
| `0x2AF` | Dreidel | yes | exact `Dreidel` hotspot/behavior | handlers absent; rendered-only |
| `0x2B0-0x2B5` | Eggnog and holiday gnomes | yes | generic Christmas decor/knickknack family only | exact routes unresolved |
| `0x2B6-0x2B7` | Large Angel and Large Star | no | no per-item route proven | decorative |
| `0x2B8` | Menorah | yes | exact `Menorah` hotspot/behavior | handlers absent; rendered-only |
| `0x2B9-0x2BC` | Ornaments | no | no per-item route proven | decorative |
| `0x2BD` | Penguin Decoration | yes | generic Christmas knickknack family only | exact route unresolved |
| `0x2BE` | Plate of Cookies | yes | adult-save/kid-steal Santa-cookie family | handlers absent; rendered-only |
| `0x2BF-0x2C5` | Poinsettia and Christmas decorations | yes | generic Christmas decor/knickknack family only | exact routes unresolved |
| `0x2C6-0x2C7` | Stockings | yes | exact `XmasStockings` / `KidsCheckXmasStockings` | handlers absent; rendered-only |
| `0x2C8-0x2C9` | Garlands | yes | `InteractHouseXmasDecor` family | exact route unresolved |
| `0x2CA-0x2D2` | Thanksgiving food | no | no Thanksgiving-specific hotspot or behavior recovered | decorative |
| `0x2D3` | Holiday Welcome Mat | no | stock desktop Welcome Mat exists; no exclusive action proven | existing donor only |
| `0x2D4-0x2D5` | Wreaths | yes | `InteractHouseXmasDecor` family | exact route unresolved |
| `0x2D6-0x2D7` | Designer Soap | no | no exclusive route proven | existing soap donor only |
| `0x2D8-0x2D9` | Towel Sets | no | `UsingWarmTowel` exists on mobile | item call chain unresolved |
| `0x2DA` | Birthday Balloons | yes | `BirthdayBalloons`; play/maybe play | exact hotspot proven; complete grouped family still blocked |
| `0x2DB` | Birthday Banner | yes | `BirthdayBanner`; celebration family | exact hotspot proven; complete grouped family still blocked |
| `0x2DC` | Birthday Cake | yes | `BirthdayCake`; poke/maybe poke | exact single-object plan proven; complete grouped family still blocked |
| `0x2DD` | Birthday Presents | yes | `BirthdayPresents`; poke/maybe poke | exact single-object plan proven; complete grouped family still blocked |
| `0x2DE-0x2E1` | Lounge Chairs | yes | `Chaise`; `LieOnChaiseNoLeadIn` | implemented as the first optional family; exact plan sequence and PC-safe placed-item maps |
| `0x2E2-0x2E3` | Floor Lamps | no | no exclusive route proven | decorative |
| `0x2E4-0x2E5` | Patio surfaces | yes | patio context only | no per-surface action assigned |
| `0x2E6` | Patio Table | yes | `PatioChairs`; study/drink family | only `StudyingOnPatio` exists on desktop; placed-item anchoring unresolved |
| `0x2E7` | Patio Umbrella | yes | `PatioUmbrella`; `AdjustingUmbrella` | implemented as the second optional family; exact direct plan sequence and PC-safe placed-item map |
| `0x2E8` | Picnic Table | yes | `PicnicTable`; prepare/eat picnic | handlers absent; rendered-only |

## Patio QAMF finding

`Patio_table.png.fmap` is a 19 by 17 primary content block. Three distinctive
cell values occur only in that map across the audited mobile corpus and never
in the packaged desktop maps. The desktop build has no `PatioChairs` hotspot
handler, so assigning meanings or directions to those values would be a guess.

The desktop `CBehavior::StudyingOnPatio` method is present as behavior `0xC2`,
but it uses fixed world coordinates. That does not make the mobile QAMF markers
desktop-compatible and does not correctly anchor the action to an arbitrarily
placed Patio Table.

## Implemented architecture

The optional patch uses a default-zero `.vf2beh` runtime byte and a single
relocation-only wrapper at `theMainScene::DropVillager`. The wrapper calls the
stock `HandleDropOnHotSpot` first. Only a stock miss, an enabled flag, and one of
the four lounge-chair IDs can reach the added handler; every other path returns
to the unchanged stock fallback. The fixed desktop behavior table (`0x19B`
entries) and hotspot table (`0x5D` entries) do not grow.

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

## Birthday family blocker

The four birthday hotspots and their object IDs are proven: Banner `0x91`,
Balloons `0x92`, Presents `0x93`, and Cake `0x94`. Balloons, Presents, and Cake
all delegate through `AllPeepsCelebratingBirthday`; Banner is always a grouped
celebration. When Banner exists or more than one birthday object is placed, the
mobile build makes every villager run behavior `0x1AF`. That behavior and the
other birthday IDs `0x1AD-0x1B3` are beyond the fixed desktop table ending at
`0x19A`.

Cake-only and Presents-only plan sequences are recovered, but shipping either
alone would diverge whenever the other birthday decorations are present. The
family therefore remains rendered-only until the complete grouped `0x1AF`
sequence and all four PC-safe maps can be ported through the external dispatcher
without indexing or growing the stock table.

The optional lounge family also adds four runtime-gated autonomous choices without
growing the fixed behavior table. `ReadingBook` (`0x12B`, weight 1500) and
`NappingCouch` (`0x83`, weight 3000) preserve the recovered mobile 30-percent
good-weather chaise branches. Desktop `RestingBody` (`0x127`, weight 2000) is the
safe in-range carrier for the mobile Sunbathing plan and is additionally gated to
daytime. `StudyingOnPatio` (`0xC2`, weight 450) carries the requested
`Studying on the lounger` extension; that label and weight are patch choices, not
claims of an exact mobile chaise-study route. With `.vf2beh` zero, each constructor
wrapper returns to its stock desktop target (or the existing Behavior Patches label
wrapper for that build). Rain, storm, fog, and snow reject all outdoor-chair
branches; the stock behavior then remains in control.

Future disruptive household-wide celebration behaviors remain manual-drop-only.
