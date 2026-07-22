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

All 63 items currently receive a copied desktop donor click-table byte, but that
does not establish the correct mobile action. The generator deliberately zeroes
their unsupported furniture-map cells, leaving them rendered-only.

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
| `0x2DA` | Birthday Balloons | yes | `BirthdayBalloons`; play/maybe play | handlers absent; rendered-only |
| `0x2DB` | Birthday Banner | yes | `BirthdayBanner`; celebration family | handlers absent; rendered-only |
| `0x2DC` | Birthday Cake | yes | `BirthdayCake`; poke/maybe poke | handlers absent; rendered-only |
| `0x2DD` | Birthday Presents | yes | `BirthdayPresents`; poke/maybe poke | handlers absent; rendered-only |
| `0x2DE-0x2E1` | Lounge Chairs | yes | `Chaise`; `LieOnChaiseNoLeadIn` | handlers absent; rendered-only |
| `0x2E2-0x2E3` | Floor Lamps | no | no exclusive route proven | decorative |
| `0x2E4-0x2E5` | Patio surfaces | yes | patio context only | no per-surface action assigned |
| `0x2E6` | Patio Table | yes | `PatioChairs`; study/drink family | only `StudyingOnPatio` exists on desktop; placed-item anchoring unresolved |
| `0x2E7` | Patio Umbrella | yes | `PatioUmbrella`; `AdjustingUmbrella` | handlers absent; rendered-only |
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

## Required implementation architecture

The final optional patch must use a default-zero `.vf2beh` runtime byte and an
external descriptor/dispatcher for added mobile IDs only. Stock items, all
unresolved mobile descriptors, and the disabled path must fall through to the
unchanged desktop logic. The fixed desktop behavior table (`0x19B` entries) and
hotspot table (`0x5D` entries) must not grow.

Disruptive household-wide celebration behavior must be manual-drop-only. It
must not become an autonomous candidate.

