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
odds.

Collections page `5` is appended to the native `CCollectionScene` tables rather
than replacing an existing page. The page uses generated build-local art under
`Images/CollectionOrnaments/` plus `Images/collection-ornaments_background.png`.
The matching Goals entry is achievement `0x5F`; visible achievement/order bounds
must widen to `0x60`, while the existing achievement save block remains large
enough for this row.
