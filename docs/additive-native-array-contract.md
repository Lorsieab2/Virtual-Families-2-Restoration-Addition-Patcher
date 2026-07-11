# Additive Native Array Contract

This project should add new VF2 content by extending the desktop game's native
tables and their bounds together. Base desktop entries remain the source of
truth and must not be replaced.

## Furniture and Store Items

New furniture must be appended to `?itemInfo@@3PAUsFurnitureInfo@@A` and exposed
through `?itemInfoLookup@@3PAPAUsFurnitureInfo@@A`. Each appended item also
needs a matching image descriptor, string rows, and store category membership.

Store category lists are native arrays such as `gAppliancesList`,
`gFurniture2List`, `gFurniture4List`, `gFurniture5List`, and
`gAccessoriesList`. Adding an item to a category requires widening both the
array/list contents and the category count logic used by
`CInventoryManager::GetCategoryItemCount`.

Count widening must be symbol-relative when a stock count is ambiguous. General
Appliances starts at `15`, which collides with the additive pet list after
Turtle/Hamster are enabled. The safe appliance sites are
`CInventoryManager::GetCategoryItem` push-count offset `0x73`, max-index compare
offset `0x95`, and `CInventoryManager::GetCategoryItemCount` return offset
`0x37`; broad `6A 0F` or `83 FE 0E` replacement can corrupt unrelated lists.

Pet-store additions follow the same rule. Hidden/mobile pet IDs are appended to
`gPetList` and `gPetListSorted`, and the pet category count is widened by the
same number of entries. The current source adds Turtle and Hamster as
desktop-hidden/mobile pets.

## Graphics and Strings

New graphics are appended to `?ImageList@@3PAUImageDescriptor@@A`; the image
index table must grow by the same number of descriptors. Stock image IDs remain
stable as fallbacks.

New names, descriptions, behavior labels, and event text are appended to
`?stringTable@@3PAUStringItem@@A`; string lookup/count bounds must be widened.
Existing desktop string IDs must not be reused for new content.

## Island Events

The desktop `CIslandEvents::mEventList` array remains the source of truth. Stock
slots `0x01` through `0x60` stay untouched. Mobile-exclusive events are appended
beginning at slot `0x61`, and `mEventHasFired` is moved after the enlarged
pointer table.

Constructor, destructor, scan, and `ForceEvent` bounds must all use the same new
exclusive end value. Mobile source classes beginning with `CEventEmail` are
registered as email events so the stock email event path can select them.

## Clickable Furniture

Clickable behavior should be added by extending the native
`CFurnitureManager::HandleMouseDown` lookup table and copying donor case bytes
for appended items. Stock clickable furniture cases must remain unchanged.

## Villager Behaviors

Spontaneous behaviors should be enabled by adding or widening native candidate
table eligibility, not by replacing unrelated actions such as `Bored`.
Drop-action behavior and spontaneous AI eligibility are separate concerns.

Autonomous candidate records are `0xD0` bytes. The enabled flag is at `+0xCD`,
the weighted random-choice value is at `+0x0C`, max age is at `+0x48`, and min
age is at `+0x4C`. Child-only spontaneous behaviors should cap max age at
`0x117`; the stock child/adult boundary is `CVillager+0x6A54 < 0x118`.

## Holiday Outfits

Holiday body values are enabled by default and can be disabled only for
stock-body diagnostics with `VF2_ENABLE_HOLIDAY_BODY_TYPES=0`. Stock body values
`0-49` stay unchanged. Holiday body/action/sit frames must be registered
together for matching body values and must fall back to stock rendering if an
extracted frame is missing.

## Holiday Ornaments

The mobile Holiday Ornaments collection uses dormant collectible carrying values
`0x9E-0xA9`. The PC patch registers base value `0x9E` as another full-yard
spawn collection through `CCollectableItem::AddSpawnArea`, then lets the stock
`CCollectableItem::Update/Add` path control normal spawn odds and Lucky Rock
odds. Mobile VF2 1.7.16 registers the ornament base with these same four
full-yard spawn rectangles:

- `(0x634, 0x0B4, 0x764, 0x302)`
- `(0x112, 0x0C4, 0x2FA, 0x1BD)`
- `(0x098, 0x178, 0x19D, 0x26F)`
- `(0x08D, 0x568, 0x137, 0x750)`

The mobile rarity helpers classify `0x9E-0xA1` as common ornaments,
`0xA2-0xA5` as uncommon ornaments, and `0xA6-0xA9` as rare ornaments.
Stock `CCollectableItem::Add(ECarrying, ldwPoint, bool)` already treats a
registered spawn-area base generically: it rolls `GetRandom(4)` for base
members, then applies the existing `+4` uncommon and `+8` rare bumps before
storing the concrete spawned collectible. That means the Holiday Ornament patch
should keep using `AddSpawnArea(0x9E, ...)` instead of adding a separate
ornament scheduler; Lucky Rock remains in the stock odds path.

The base value must also be taught to every hard-coded collectible family
recognizer. `CCollectableItem::WasItemSpawned(ECarrying)` checks exact IDs, and
`CCollectableItem::Find(CVillager&, ECarrying, ldwPoint&)` only recognizes the
stock family ranges unless patched. Holiday Ornaments therefore add `0x9E`
request handling for active variants `0x9E-0xA9` in both routines; otherwise
the game can keep spawning ornaments and fail to route villagers to pick them
up.

`CCollectable` also has its own carrying-value observer table. Stock PC
registers `CCollectableItem` for collectible values through `0x9D`; B92 adds
constructor registrations for `0x9E-0xA9` so villager `Carry`/`Drop` calls reach
`CCollectableItem` and increment collection counts.

Stock PC `CCollectionScene::gCollectable` is a five-page table with 60 dwords:
`0x4F-0x72`, `0x86-0x91`, and `0x92-0x9D`. Mobile 1.7.16 expands the same
table to six pages/72 dwords by appending `0x9E-0xA9`; B92 mirrors that shape
instead of replacing page `4`. The page uses workspace-local supplied art when
available, otherwise it decodes the mobile `tp225.pvr` atlas and writes the 12
collected ornament images under `Images/CollectionOrnaments/` for the stock
`Count(item) > 0` overlay path. `Collection_ChristmasOrnament_CandyCane.png` is
decorative source art, not a 13th collectible. B142 also sources the ornament
aware `collectables_small.png` from `work/assets/holiday_collectibles/` so the
small yard/collection sheet is portable. The matching Goals entry is
achievement `0x5F`; visible achievement/order bounds must widen to `0x60`,
while the existing achievement save block remains large enough for this row.
Mobile row `0x5F` has target `12`, and mobile Goal Collector row `0x54` has
target `13`. The third achievement-list field is platform-global rather than
ornament-specific (`0x23E` on mobile, `0x1ED` on PC), so the PC additive row
keeps the PC-native `0x1ED`.

B142 adds the stock Mr. B/The Collector sell-all acknowledgement path.
`CEventTheCollector::ImpactGame(0)` already calls
`CCollectableItem::ResetCollection()`, which clears the collection-state table
used by the appended `0x9E-0xA9` family. The additive hook only inserts an
extra `CAchievement::ResetSingleAchievementProgress(0x5F)` call before the
stock achievement-reset tail; it does not alter the keep branch.

B144 also extends `CEventTheCollector::CanFire()` with base `0x9E` in the
same `CCollectableItem::CollectionCount()` offer passes used by the five stock
families, plus one completed-family availability check for the ornament
family. `CEventTheCollector::CalcAward(int)` is a stub on PC, so the
offer/availability hook belongs in `CanFire()`.

`CCollectionScene::HandleMouse()` also keeps its click-tooltip rarity labels in
a stock 60-item stack-local lookup. B145 initializes three additional four-item
buckets for ornament indices `60-71`, reusing the stock common/uncommon/rare
string IDs `0x751`, `0x752`, and `0x753`; otherwise the sixth page can render
but click/tooltip handling reads past the initialized stock table.

`CCollectableItem::Draw(int)` indexes `Images/collectables_small.png` with
`ECarrying - 0x4F`. Holiday Ornaments `0x9E-0xA9` therefore require exact
small-sheet frames `79-90`. The portable source sheet is validated as a stock
`40x40`, six-column grid with 96 frames, so the engine can draw the appended
ornaments without referencing any outside asset folder.
