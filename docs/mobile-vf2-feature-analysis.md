# Mobile VF2 Feature Analysis

Date: 2026-07-04

This document summarizes how the Android/mobile Virtual Families 2 1.7.16
build exposes and implements the mobile-only feature families that the PC mod is
porting. It combines evidence from the mobile XAPK/OBB inventory, mobile native
symbol strings, current desktop object-table patches, and the B93 patch
manifest.

## Evidence Base

- Mobile package: `work/Virtual+Families+2_1.7.16_APKPure.xapk`
- Re-extracted mobile native/asset inventory:
  `outputs/VF2-Mobile-Cpp-Reconstruction/mobile-native-inventory.json`
- Mobile asset payload: `work/vf2_obb/assets/`
- Current additive manifest:
  `outputs/VF2-Mobile-Furniture-With-Island-Events-B93-Holiday-Outfit-Body-Apply/patch-manifest.json`
- Current implementation hub: `work/patch_mobile_furniture_pack.py`
- Existing subsystem notes:
  `docs/additive-native-array-contract.md`,
  `docs/outfit-system-notes.md`, and
  `docs/island-event-extension-notes.md`

The mobile APK contains four native C++ libraries:

| ABI | Library | Size | Symbolish strings |
| --- | --- | ---: | ---: |
| arm64-v8a | `libVirtualFamilies2.so` | 3,198,680 | 5,946 |
| armeabi-v7a | `libVirtualFamilies2.so` | 2,246,356 | 5,946 |
| x86_64 | `libVirtualFamilies2.so` | 3,375,336 | 5,947 |
| x86 | `libVirtualFamilies2.so` | 3,364,568 | 5,945 |

The OBB asset payload contains 1,092 files: 316 `.ogg`, 251 `.dat`, 276
`.fmap`, 245 `.pvr`, one `.txt`, one `.plist`, and two extensionless files.
The mobile native libraries retain Itanium C++ symbol names, so feature mapping
can start from real class/function names before disassembly.

## Native System Shape

The mobile binary keeps the same LDW C++ architecture as desktop VF2. Important
classes and exposed method names include:

| System | Mobile classes and methods |
| --- | --- |
| Inventory/store | `CInventoryManager::{GetCategoryItem,GetCategoryItemCount,GetPrice,GetNumAvailable,GetOutfit,HaveUpgrade,DrawItem}`, `CScrollingStoreScene::{SetStoreCategory,DrawVisibleStoreItem,HandlePurchaseItem,HandleUpgrade,CompletePurchase}` |
| Furniture | `CFurnitureManager::{AddToWorld,AddToStorage,DropFurniture,HandleMouseDown,FindFurniture,FurnitureHasObject,LoadFmap,ApplyFmapContent,GetFmapName,HavePeepsAdmireFurniture}` |
| Villager behavior | `CBehavior` has 439 recovered methods, including mobile/holiday names such as `AdmiringXmasTree`, `AdultWaterXMasTree`, `InteractHouseXmasDecor`, `KidsCheckXmasStockings`, `AdultsSaveSantasCookies`, `KidStealsSantasCookies`, `LieInHammock`, `WatchingFirePlace`, `PlayingFoosball`, `PlayingPinball`, `PlayingPachinko`, `PlayingPooltable`, `ListenToRadio`, and `DancingRadio`. |
| Hotspots | `CHotSpot::{XmasTree,XmasStockings,Hammock,FirePlace,Foosball,Pinball,Pachinko,Pool,PoolTable,Radio,TV}` |
| Collectibles | `CCollectableItem::{Reset,AddSpawnArea,Add,Find,Drop,Count,CollectionCount,IsCommonCollectable,IsUncommonCollectable,IsRareCollectable,WasItemSpawned,UpdateAchievements}`, `CCollectable::{RegisterObserver,Carry,Drop,ProcessNearbyCollectables}` |
| Collections UI | `CCollectionScene::{sm_sCollectable,DrawScene,HandleMouse,Activate}` |
| Goals/achievements | `CAchievement::{IncrementProgress,SetComplete,ResetSpecificAchievement,DrawAchievement,SaveState,LoadState}`, `CVillagerPlans::PlanToAdvanceAchievement` |
| Island events | `CIslandEvents::{mEventList,mEventHasFired,FireEvent,FireEmailEvent,ForceEvent,EventScalor}`, `CIslandEvent::{CanFire,CalcAward,ImpactGame,IsEmailEvent,HasChoices,GetTargetVillager}` |
| Mobile purchases | `CPurchaseManager::{BuyUpgrade,GiftIAP,RestorePurchase,IAPItemFromIDString,ReportIAPPurchase,ReportAchievement,ReportCollection,ReportCollectionCompleted}`, `CPurchaseManagerImpl::{Purchase,BuyUpgrade,OnPurchaseComplete,SetProductAsPurchased}` |
| Food Club | `CFoodStore::{HaveFoodClub,JoinFoodClub,DoFoodClubDelivery,OrganicDelivery}` |

## Holiday Outfits

### Mobile Model

The mobile content provides four Holiday outfit sets. In the current PC mapping
these mobile source sets are:

| Mobile source set | PC body value |
| ---: | ---: |
| 51 | 50 |
| 52 | 51 |
| 53 | 52 |
| 54 | 53 |

Each outfit must exist as a complete gendered body/action/sit set. The desktop
renderer uses a 91 x 91 cell grid:

| Sheet role | Female sheet | Male sheet | Columns | Stock rows |
| --- | --- | --- | ---: | ---: |
| body/walk | `female_bodies00.png` | `male_bodies00.png` | 32 | 50 |
| actions | `female_actions00.png` | `male_actions00.png` | 15 | 50 |
| sit/lie | `female_sit00.png` | `male_sit00.png` | 9 | 50 |

The compatibility subset maps mobile source frames into stock role counts:

- source frames `1-32` -> body/walk frames `0-31`
- source frames `33-47` -> action frames `0-14`
- source frames `48-56` -> sit/lie frames `0-8`
- source frames `57-61` are preserved as raw source frames but are not used by
  the first folder-backed renderer pass.

Mobile native symbols confirm the engine has outfit-aware paths:
`CInventoryManager::GetOutfit`, `CInventoryManager::MaybeUpdateOutfits`,
`CBehavior::CheckingOutfit`, `CBehavior::CheckingNewOutfit`, and body generator
methods `CVillager::{GenCommonBodyType,GenUncommonBodyType,GenRareBodyType}`.

### Current PC Port Contract

The additive PC store exposes all base and Holiday body rows as synthetic
Clothing items:

| Gender | Synthetic item range | Body values |
| --- | --- | --- |
| Female | `0x400-0x435` | `0-53` |
| Male | `0x440-0x475` | `0-53` |

Holiday rows are:

| Gender | Item IDs | Body values |
| --- | --- | --- |
| Female | `0x432-0x435` | `50-53` |
| Male | `0x472-0x475` | `50-53` |

Important helper and hook points:

- `CScrollingStoreScene::HandlePurchaseItem + 0x1AD` calls
  `_VF2PurchaseOutfitStoreItem`.
- Synthetic generated outfit IDs are stored directly in `CToolTray` slots.
- `CToolTray::GetToolInHand()` is patched to call
  `_VF2NormalizeOutfitToolInHand` with active flag `0xA4`.
- `CToolTray::GetToolInUse()` is patched to call the same helper with active
  flag `0xA5`.
- `_VF2NormalizeOutfitToolInHand` normalizes synthetic female rows to stock
  tray item `0x4A` and synthetic male rows to stock tray item `0x49` only while
  vanilla application checks are running.
- `_VF2GetOutfitStoreBodyValue` decodes the body from the selected synthetic
  item. B93 keeps separate hand/use globals so `GetToolInHand` cannot clear
  the synthetic item before `GetToolInUse`/`GetOutfit(0x49/0x4A)` resolves body
  values `50-53`.

Rendering is folder-backed:

- `Images/VillagerBodies/Female/Body_50..53/{bodies,actions,sit}/Frame##.png`
- `Images/VillagerBodies/Male/Body_50..53/{bodies,actions,sit}/Frame##.png`

The B93 manifest contains 448 registered Holiday body frame descriptors:
`2 genders * 4 body values * 56 frames`. The current source priority is:

1. repo-local `generated/VillagerBodies` split frames
2. Holiday archive frames, if available
3. expanded-sheet rows only as a migration fallback

The stock `CAnimManager` link-point functions still treat valid sheet rows as
`0-49`; Holiday visual frames draw through one-cell image descriptors, while
head/body link geometry falls back to stock row `49`.

## Holiday Furniture

The mobile furniture table includes a Holiday decor/food set that is not
present in stock desktop PC. The current PC port appends these as furniture
rows starting at `0x2AA`. They preserve the mobile prices, text rows, sprite
paths, and broad store placement where possible, but use desktop donor records
for placement/click safety.

Representative Holiday furniture rows:

| PC item | Name | Mobile item | Store list | Donor | Mobile type | Price | Runtime path |
| ---: | --- | ---: | --- | ---: | ---: | ---: | --- |
| `0x2AA` | Holiday Candles | `0x2AA` | `gAccessories` | `0x256` | 6 | 30 | `Furniture/CandleOnHolder.png` |
| `0x2AB` | Candy Canes | `0x2AB` | `gAccessories` | `0x256` | 6 | 5 | `Furniture/CandyCane.png` |
| `0x2AC` | Christmas Cookie | `0x2AC` | `gAccessories` | `0x256` | 6 | 5 | `Furniture/ChristmasCookie.png` |
| `0x2AD` | Christmas Tree | `0x2AD` | `gAccessories` | `0x233` | 5 | 250 | `Furniture/ChristmasTree1.png` |
| `0x2AE` | Lighted Christmas Tree | `0x2AE` | `gAccessories` | `0x233` | 5 | 350 | `Furniture/ChristmasTree2.png` |
| `0x2B8` | Menorah | `0x2B8` | `gAccessories` | `0x256` | 6 | 25 | `Furniture/Menorah.png` |
| `0x2B9-0x2BC` | Ornaments | `0x2B9-0x2BC` | `gAccessories` | `0x256` | 6 | 5-6 | `Furniture/Ornament*.png` |
| `0x2C8-0x2C9` | Garland | `0x2C8-0x2C9` | `gAccessories` | `0x256` | 6 | 50 | `Furniture/StringOfLeaves.png`, `Furniture/StringOfLights.png` |
| `0x2CA-0x2D2` | Holiday food | `0x2CA-0x2D2` | `gAccessories` | `0x256` | 6 | 5-35 | `Furniture/Thanksgiving*.png` |
| `0x2D4-0x2D5` | Wreaths | `0x2D4-0x2D5` | `gAccessories` | `0x256` | 6 | 100-125 | `Furniture/Wreath*.png` |

The mobile native behavior layer has direct holiday/furniture functions:

- `CHotSpot::XmasTree`
- `CHotSpot::XmasStockings`
- `CBehavior::AdmiringXmasTree`
- `CBehavior::AdultWaterXMasTree`
- `CBehavior::InteractHouseXmasDecor`
- `CBehavior::KidsCheckXmasStockings`
- `CBehavior::EachPeepCelebrateXMasTree`
- `CBehavior::AdmiringXmasKnickKnacks`
- `CBehavior::AdultsSaveSantasCookies`
- `CBehavior::KidStealsSantasCookies`

These names confirm mobile has custom behavior routes for Holiday decorations,
not just static sprites. B156 now ports `KidExaminesCandles` for Holiday
Candles `0x2AA` as an exact child-only manual plan with a minimal PC-safe map.
Plate of Cookies `0x2BE` now age-routes exact child-steal and adult-rescue
manual plans on EObject `0x8F`, including the child route's optional adult
rescuer. The knickknack, single-cookie, garland, and wreath candidates were
then checked against every preserved QAMF. EObject `0x8C`
proves the exact `AdmiringXmasKnickKnacks` route for ten gnome/yard figurines;
EObject `0x8D` proves `InteractHouseXmasDecor` for Red Bow, Santa Wall
Decoration, and both garlands. Those fourteen exact manual routes now use
minimal PC-safe maps. Glass of Eggnog now uses its proven EObject `0x8B` and
exact child-only `CBehavior::Eggnog` manual plan. Single Cookie, Poinsettia,
and both wreaths remain unresolved; the wreath maps contain no `0x8D` EObject
anchor.

Low-level PC table work:

- `?itemInfo@@3PAUsFurnitureInfo@@A` grows by 111 records in B93.
- `?itemInfoLookup@@3PAPAUsFurnitureInfo@@A` grows with the appended records.
- `CFurnitureManager::LoadFmap` range guard widens from stock max offset `0xFB`
  to additive max offset `0x179`.
- `CFurnitureManager::HandleMouseDown` lookup table is extended by copying
  donor case bytes for added furniture; stock cases remain unchanged.

## Other Mobile/Added Furniture Not in Stock PC

The current additive furniture set has 112 rows. Categories:

| Group | Count | Notes |
| --- | ---: | --- |
| Mobile default/holiday/birthday/outdoor/decor rows | 63 | Includes Holiday items, birthday decor, bathroom decor, lounge chairs, patio items. |
| Colorful couches | 7 | Custom/additive couch variants mapped to stock couch donors. |
| LDW poster pack | 6 | Wall decor/posters. |
| VF3 living room import batch | 6 | Plaid/flowered/striped couches/loveseats. |
| Invisible outdoor batch | 3 | Invisible kiddie pool, full-size pool, hammock. |
| Invisible base-furniture batch | 24 | Invisible couches, beds, fireplace, MP3 player, playhouse, trampoline, etc.; B103 adds a separate Invisible Heart-Shaped Bed. |
| VF3 television import batch | 3 | Large, Small, and Father's Favorite TVs. |

Store category growth in current B103 normal builds:

| Store list | Old count | New count | Added examples |
| --- | ---: | ---: | --- |
| `gAccessories` | 47 | 107 | Holiday decor, birthday decor, invisible fireplace/clock/MP3, posters |
| `gFurniture5` | 12 | 30 | Outdoor/patio/invisible pool/hammock/playhouse/trampoline |
| `gFurniture4` | 74 | 84 | Bedroom/wall/invisible beds/posters, including `InvisibleHeartShapedBed` `0x327` |
| `gFurniture3` | 26 | 27 | Invisible kids table |
| `gFurniture2` | 88 | 108 | Couches/loveseats/bookshelves |
| `gAppliances` | targeted widening | includes `0x324-0x326` | VF3 TVs |
| `gPetList` | 13 | 15 | hidden/mobile Turtle `0x245`, Hamster `0x247` |

General Appliances count widening is symbol-relative because stock count `15`
also appears in pet paths. Safe desktop sites are:

- `CInventoryManager::GetCategoryItem` push-count offset `0x73`
- `CInventoryManager::GetCategoryItem` max-index compare offset `0x95`
- `CInventoryManager::GetCategoryItemCount` return offset `0x37`

### VF3 TVs

The mobile-imported TV rows are:

| Item | Name | Donor | Store | Behavior contract |
| ---: | --- | ---: | --- | --- |
| `0x324` | Large Flat Screen TV | `0x1F3` | `gAppliances` | all non-identity, non-store, non-animation fields match base flat-screen TV |
| `0x325` | Small Flat Screen TV | `0x1F3` | `gAppliances` | same |
| `0x326` | Father's Favorite TV | `0x1F3` | `gAppliances` | same |

TV recognition path:

`CBehavior::WatchTVDispatch -> CFurnitureManager::FindFurniture(object 0x0D) -> CFurnitureManager::FurnitureHasObject`

Therefore the PC port must provide `.fmap` object-cell payloads compatible with
the base TV. B93 generates:

- `Assets/VF3LargeFlatScreenTV.png.fmap`
- `Assets/VF3SmallFlatScreenTV.png.fmap`
- `Assets/FathersFavoriteTV.png.fmap`

The generated fmaps use the VF3 sprite alpha footprint but preserve stock TV
object payload values such as `0x003C0001` and `0x003C6800`. Base TV assets and
behavior remain untouched.

## Holiday Ornaments Collection and Goals

### Mobile Collection Shape

Mobile VF2 adds a sixth collection page for Holiday Ornaments. Stock PC has
five pages/60 collectibles:

- `0x4F-0x72`
- `0x86-0x91`
- `0x92-0x9D`

Mobile extends `CCollectionScene::gCollectable` to 72 dwords by appending:

- Holiday Ornament carrying values `0x9E-0xA9`

Mobile art strings/assets include:

- `Collection_Ornaments_Background.png`
- `Collection_ChristmasOrnament_BlueBall.png`
- `Collection_ChristmasOrnament_Crosses.png`
- `Collection_ChristmasOrnament_Disco.png`
- `Collection_ChristmasOrnament_GoldDealio.png`
- `Collection_ChristmasOrnament_Heart.png`
- `Collection_ChristmasOrnament_HotAirBalloon.png`
- `Collection_ChristmasOrnament_RedGoldOrnament.png`
- `Collection_ChristmasOrnament_Silverbell.png`
- `Collection_ChristmasOrnament_Star.png`
- `Collection_ChristmasOrnament_Threebells.png`
- `Collection_ChristmasOrnament_Twirl.png`
- `Collection_ChristmasOrnament_Twisty.png`

`Collection_ChristmasOrnament_CandyCane.png` is decorative source art, not a
13th collectible in the current evidence.

### Spawn Mechanics

Mobile `CCollectableItem::Reset()` registers ornaments as an additional
full-yard spawn family with base carrying value `0x9E`. The four mobile
rectangles are:

| Rect | Coordinates |
| ---: | --- |
| 1 | `(0x634, 0x0B4, 0x764, 0x302)` |
| 2 | `(0x112, 0x0C4, 0x2FA, 0x1BD)` |
| 3 | `(0x098, 0x178, 0x19D, 0x26F)` |
| 4 | `(0x08D, 0x568, 0x137, 0x750)` |

The rarity helpers classify:

- common: `0x9E-0xA1`
- uncommon: `0xA2-0xA5`
- rare: `0xA6-0xA9`

The correct implementation must not create a separate spawn scheduler. It
should register ornaments into the same `CCollectableItem::Update/Add` path so
normal collectible odds and Lucky Rock odds continue to apply.

Hard-coded family recognizers also need updates:

- `CCollectableItem::Find(CVillager&, ECarrying, ldwPoint&)` must recognize
  request base `0x9E` and active variants `0x9E-0xA9`.
- `CCollectableItem::WasItemSpawned(ECarrying)` must recognize the same range.
- `CCollectable::RegisterObserver` must register `0x9E-0xA9`; otherwise
  `Carry`, `Drop`, and `ProcessNearbyCollectables` will not dispatch to
  `CCollectableItem`.

These missing family/observer registrations explain the previously observed
infinite-spawn/non-pickup glitch.

### Collection UI

The PC port appends page `5` instead of replacing stock page `4`.
`CCollectionScene` remains `0x30` bytes; the current patch asks a helper for
page counts rather than adding another cached field.

B93 item overlay image IDs:

| Carrying | Image ID | Position |
| ---: | ---: | --- |
| `0x9E` | `0x53F` | `(180, 476)` |
| `0x9F` | `0x540` | `(353, 476)` |
| `0xA0` | `0x541` | `(531, 476)` |
| `0xA1` | `0x542` | `(708, 476)` |
| `0xA2` | `0x543` | `(193, 302)` |
| `0xA3` | `0x544` | `(531, 302)` |
| `0xA4` | `0x545` | `(353, 302)` |
| `0xA5` | `0x546` | `(708, 302)` |
| `0xA6` | `0x547` | `(180, 126)` |
| `0xA7` | `0x548` | `(353, 126)` |
| `0xA8` | `0x549` | `(531, 126)` |
| `0xA9` | `0x54A` | `(708, 126)` |

The page background uses image ID `0x54B` and title string `0xC8B`.

### Goals/Achievements

Mobile achievement evidence:

- Ornamentologist row: `0x5F`
- Target: `12`
- Title: `Ornamentologist`
- Description: `You completed the collection of holiday ornaments.`
- Goal Collector row: `0x54`
- Goal Collector mobile target: `13`

The PC additive row keeps the PC-native third achievement-list field value
rather than copying mobile's platform-global value. `CAchievement` already
serializes `0x125` 12-byte records, so no save-state size increase is required
for row `0x5F`.

### Mr. B / The Collector Sell-All Path

Mobile maps the Holiday Ornament family into the same collection-state table as
the five stock collectible families. Desktop `CEventTheCollector::ImpactGame`
choice `0` (`Sell`) already calls `CCollectableItem::ResetCollection()`, which
clears the whole collection table rather than individual families. The B142
Holiday Ornaments opt-in therefore reuses that stock reset for item flags and
adds one small `CEventTheCollector::ImpactGame` hook before the existing
achievement tail-call so `CAchievement::ResetSingleAchievementProgress(0x5F)`
also runs. Choice `1` (`Keep`) remains untouched.

`CEventTheCollector::CanFire()` is also the PC-side offer/availability counter.
B144 adds Holiday Ornament base `0x9E` to the same three
`CCollectableItem::CollectionCount()` offer passes used for stock bases
`0x67`, `0x4F`, `0x5B`, `0x86`, and `0x92`, then adds one completed-family
availability check for `0x9E`. Sold ornaments still clear through the stock
collection reset path once the event fires.

## Exclusive Island Events and Outcomes

### Mobile Event Table

Mobile exposes real event classes and virtual methods:

- `CIslandEvents::{mEventList,mEventHasFired,FireEvent,FireEmailEvent,ForceEvent}`
- `CIslandEvent::{CanFire,CalcAward,ImpactGame,IsEmailEvent,HasChoices}`
- `CIslandEventChoiceAB` for two-choice records

The PC port preserves stock desktop slots `0x01-0x60` and appends mobile-only
events beginning at `0x61`. `mEventHasFired` is moved after the enlarged
pointer table. The new exclusive scan bound is `0x7A`.

Current appended mapping:

| Slot | Mobile class | Desktop shell | Email? | Choices? |
| ---: | --- | --- | --- | --- |
| `0x61` | `CEventBlastFromThePast` | `Boring` | no | no |
| `0x62` | `CEventClownHoldingMetalRod` | `AdultProof` | no | yes |
| `0x63` | `CEventEmailFromACME` | `Likes` | yes | no |
| `0x64` | `CEventEmailFromAntonioGuildenstern` | `TheSadNote` | yes | no |
| `0x65` | `CEventEmailFromSchool` | `TheAngryNote` | yes | no |
| `0x66` | `CEventFruitcakes` | `DiaperRash` | no | yes |
| `0x67` | `CEventGreatUncleElmer` | `TheSpam1` | yes | no |
| `0x68` | `CEventGroupOfKidsAtTheDoor` | `TheTrainer` | no | yes |
| `0x69` | `CEventHearStrangeSound` | `TheRareBird` | no | yes |
| `0x6A` | `CEventInterestingArticleAboutFossils` | `IAteSoup` | yes/text-only | no |
| `0x6B` | `CEventInvitation` | `TheCollector` | no | yes |
| `0x6C` | `CEventLoanReturned` | `IAmOnABoat` | no | no |
| `0x6D` | `CEventMarchingBandTripExpenses` | `OhSoClever` | yes | no |
| `0x6E` | `CEventMenInBlackAtDoor` | `EPAVisit` | no | yes |
| `0x6F` | `CEventMetallicKnockingOnDoor` | `ASmallPackage` | no | yes |
| `0x70` | `CEventMeteoriteFallsInYard1` | `TheNAS` | no | no |
| `0x71` | `CEventMeteoriteFallsInYard2` | `ATinyWhiteBox` | no | yes |
| `0x72` | `CEventMissionFromGod` | `AMediumBrownBox` | no | yes |
| `0x73` | `CEventOddOldWomanAtDoor` | `ACealedGreenBag` | no | yes |
| `0x74` | `CEventRIPUncleAlpert` | `TheNCA` | yes | no |
| `0x75` | `CEventResurrectionOfAgatha` | `ILostMyPants` | no | no |
| `0x76` | `CEventStrangePackageOnPorch` | `BoySellingCupcakes` | no | yes |
| `0x77` | `CEventSurpriseVisitFromUnclePhineas` | `SoManyBabies` | no | no |
| `0x78` | `CEventTeens` | `CareerChangeCouncelor` | no | yes |
| `0x79` | `CEventVolunteer` | generated shell | no | yes |

### Current Outcome Status

The current B156 implementation appends event objects, text, choice labels, and
email classification. It does **not** yet reproduce every mobile `ImpactGame`
effect. `docs/TODO.md` still correctly tracks the remaining events as
unfinished.

The first three function-level audits now replace earlier experimental
approximations:

| Mobile event | Exact recovered result |
| --- | --- |
| `MeteoriteFallsInYard1` | Dummied out on mobile: `CanFire()` is always false; `CalcAward()` and `ImpactGame()` are empty. |
| `Teens` | Choice A spawns exactly 10 socks and 10 trash; Choice B sets award `-75` and applies that money adjustment. It fires only with a raw-age `260..340` villager. |
| `StrangePackageOnPorch` | Choice A calculates `GetRandom(100)+50` and awards 50-149 coins; Choice B awards zero. It requires a random adult target. |

The mobile `.so` proves each mobile class has its own `ImpactGame`,
`CalcAward`, and `CanFire` methods, but most exact outcome implementations
still need function-level disassembly before they should be ported. The safe
implementation rule is: map one event at a time from mobile disassembly, then
patch only the corresponding generated or donor shell's `ImpactGame`, keeping
target selection and string rendering stable.

## Villager Behaviors Related to Mobile Content

Mobile native symbols expose behavior and hotspot support for the furniture
families above:

| Feature | Hotspot symbol | Behavior symbols |
| --- | --- | --- |
| TV | `CHotSpot::TV` | `CBehavior::WatchTVDispatch`, `WatchTV0-6`, `TurnOffTV` |
| Hammock | `CHotSpot::Hammock` | `LieInHammock`, `LieInHammockNoLeadIn`, `StudyingInHammock` |
| Fireplace | `CHotSpot::FirePlace` | `WatchingFirePlace` |
| Foosball | `CHotSpot::Foosball` | `PlayingFoosball` |
| Pinball | `CHotSpot::Pinball` | `PlayingPinball`, `PlayingPinballGames` |
| Pachinko | `CHotSpot::Pachinko` | `PlayingPachinko` |
| Pool table | `CHotSpot::PoolTable` | `PlayingPooltable` |
| Pools | `CHotSpot::Pool` | `PlayInPool`, `HangOutPool`, `SwimmingPool`, `SplashingPool` |
| Radio | `CHotSpot::Radio` | `ListenToRadio`, `DancingRadio`, `Dance` |
| Drawing | n/a in current symbol sample | `DrawingOnWall`, `DrawingOnEasel` |
| Holiday tree/decor | `CHotSpot::XmasTree`, `XmasStockings` | `AdmiringXmasTree`, `AdultWaterXMasTree`, `InteractHouseXmasDecor`, `KidsCheckXmasStockings`, `EachPeepCelebrateXMasTree`, `AdultsSaveSantasCookies`, `KidStealsSantasCookies` |

The current PC patch uses an autonomous candidate table model instead of
replacing generic behaviors:

- Candidate record size: `0xD0`
- enabled flag: `+0xCD`
- weighted choice value: `+0x0C`
- max age: `+0x48`
- min age: `+0x4C`
- child/non-child boundary: `CVillager+0x6A54 < 0x118`
- mature-adult behavior boundary: `0x168 <= CVillager+0x6A54 < 0x44C`

Enabled B93 spontaneous candidates:

- hammock relaxation, all ages, weather `0` neutral or `1` sunny only
- warm/watch fireplace, all ages
- pinball, slots, pachinko, pool, foosball, all ages
- playhouse, children only, max age `0x117`
- listen/dance to radio
- drawing

`UsingWarmTowel` is not a missing mobile behavior. Both binaries already carry
it at behavior `0xE7`, using EObject `0x50`; the plan goes to that object,
plays `Work`, a random 1-3 count `SwingArm`, then `Work`, and reduces dirtiness
by 2. The Brown and Pink mobile towel-set items have no supplied QAMF and no
proven EObject `0x50` binding, so they remain decorative instead of being
assigned this behavior by description alone.

Drop-action behavior and spontaneous eligibility are separate. Invisible or
mobile furniture should inherit stock clickable/drop behavior by extending
native lookup tables or donor predicates, not by modifying base furniture
cases. Example: Invisible Hammock uses the same donor-cloned fields, donor
`HandleMouseDown` lookup-table case, and donor `.fmap` copy as invisible
fireplaces, then B102 widens only the initial `CHotSpot::Hammock` in-world gate
so item `0x30C` reaches the unchanged base hammock behavior route.
The B103 Invisible Heart-Shaped Bed follows the pure donor-clone path: item
`0x327` uses donor `0x252`, `HeartShapedBed.png.fmap`, and separate invisible
graphics, leaving `InvisibleAdultDoubleBed` on donor `0x1B7`.

## Mobile-Exclusive Purchases

Mobile has an IAP/purchase layer:

- `AndroidBridge::{BeginPurchase,BeginPurchasingOperation,FetchSKU,FinishedUpdatingProductList}`
- `CPurchaseManager::{BuyUpgrade,GiftIAP,RestorePurchase,IAPItemFromIDString,ReportIAPPurchase}`
- `CPurchaseManagerImpl::{Purchase,BuyUpgrade,OnPurchaseComplete,SetProductAsPurchased}`

The desktop port exposes four formerly hidden/mobile-style Special Upgrades as
normal store rows:

| Item | Name | Price | Native/mobile effect route |
| ---: | --- | ---: | --- |
| `0x117` | Brokerage Account | 10000 | Helper increments banking interest; active reset sets interest to 1%. |
| `0x118` | Food Club | 10000 | Helper calls `CFoodStore::JoinFoodClub`; mobile symbols also expose `HaveFoodClub` and `DoFoodClubDelivery`. |
| `0x119` | Health Plan | 10000 | Helper sets the health-plan discount flag. |
| `0x11A` | Lucky Rock | 77777 | Helper sets the collectible boost flag used by collectible odds. |

Store implementation:

- Source list: `gServicesList`
- Old visible count: `6`
- New visible count: `10`
- Existing base items preserved: `0x111`, `0x112`, `0x113`, `0x115`,
  `0x116`, `0x114`
- Added icons:
  - `BrokerUpgrade_icon.png` -> image `0x309`
  - `FoodClub_icon.png` -> image `0x30A`
  - `HealthPlan_icon.png` -> image `0x30B`
  - `LuckyRock_icon.png` -> image `0x30C`
- `CInventoryManager::GetPrice` hook returns `0` when one of these upgrades is
  already active, making the row removable/toggleable in the current PC model.
- The old hidden-IAP dialog route is bypassed because calling it from visible
  desktop store rows caused blank/crashing dialogs.

### Stock Lotto Ticket odds

The base Special Upgrades `Lotto Ticket` is item `0x114` in `gServicesList`.
Its purchase effect lives in
`CScrollingStoreScene::HandleUpgrade()` case `$LN50`.

The first roll is `ldwGameState::GetRandom(10000)`, treated as `0..9999`.
Thresholds are:

| Roll range | Outcome | Chance |
| ---: | --- | ---: |
| `0` | 50000 coins | 0.01% |
| `1..2` | 25000 coins | 0.02% |
| `3..22` | 5000 coins | 0.20% |
| `23..222` | 1000 coins | 2.00% |
| `223..722` | 750 coins | 5.00% |
| `723..4055` plus `GetRandom(100) < 50` and an open tray slot | random grocery/tool-tray item `4..7` | 16.665% before slot failure |
| Remaining rolls, failed 50% item roll, or no open tray slot | not a winner | 76.105% plus any item-slot failures |

Cash payout text uses string `0x4CF` (`eString_LottoWinnings`), no-win text
uses `0x4D0`, and grocery prize text uses `0x4D1`
(`eString_WonABagOfGroceries`).

## Settings Evict Button

Mobile VF2 implements Evict as a normal Settings-dialog control, gated by
family generation:

- Constructor symbol:
  `_ZN16theOptionsDialogC1EPc15DialogColorEnum` at `0x1074A0` in
  `work/apk_native/lib_x86_libVirtualFamilies2.so`
- Button action symbol:
  `_ZN16theOptionsDialog11EvictFamilyEv` at `0x1087D0`
- Family-tree action symbol:
  `_ZN11CFamilyTree11EvictFamilyEv` at `0x1C3B10`

The constructor branch near `0x10784B` checks the family-tree state and the
field at `+4`; it skips Evict setup unless the family is active and that field
is `<= 1`. This is the mobile first-generation-only behavior.

The click path should not be reimplemented for PC. Mobile calls the native
Options handler, which delegates to `CFamilyTree::EvictFamily()`, clears the
villager manager, sets `CAdoptionScene+0x1C` to `2`, switches the game state to
scene `6`, and closes the dialog. The PC binary already contains the same
desktop-mangled functions, so porting the mobile feature means exposing the
existing control and preserving the stock handler.

## Patch/Porting Rules From This Analysis

1. Append native tables and widen their bounds together; do not overwrite stock
   rows.
2. Keep base PC furniture and TV behavior untouched; copy donor behavior bytes
   or extend lookup tables for new items.
3. For mobile furniture with behavior, prove both the drop/click route and the
   spontaneous AI candidate route. They are not the same subsystem.
4. Holiday outfits require complete body/action/sit coverage and safe stock-row
   fallback; do not expand vanilla sheet lookups unless the sheets are actually
   expanded.
5. Holiday Ornaments must be registered in collection UI tables, spawn areas,
   rarity helpers, family recognizers, observer dispatch, and achievements.
6. Island Event text shells are not enough. Exact `ImpactGame` logic must be
   ported from mobile disassembly one event at a time.
7. Mobile purchases should be exposed as transparent store/helper effects, not
   Android IAP runtime calls, when ported to PC.
8. The offline patcher manifest should group these features behind settings:
   `holiday_furniture`, `holiday_outfits`, `outfit_store_expansion`,
   `mobile_furniture`, `vf3_tv_animation_graphics`,
   `holiday_ornaments_collection`, `mobile_furniture_behaviors`,
   `island_event_outcomes`, and `visible_special_upgrades`.

## Open Low-Level Research Tasks

- Disassemble mobile `CEvent*::ImpactGame` methods for every appended Island
  Event and map exact rewards, penalties, spawned items, pets, emails, and
  villager-state changes.
- Disassemble mobile Holiday behavior methods (`InteractHouseXmasDecor`,
  `KidsCheckXmasStockings`, `AdultsSaveSantasCookies`,
  `KidStealsSantasCookies`) and identify required furniture object IDs,
  carried items, floating animations, and achievement hooks.
- Confirm the exact mobile save-state fields for Brokerage Account, Food Club,
  Health Plan, and Lucky Rock, then map them to PC fields or explicit helper
  state.
- Verify mobile Lucky Rock's collectible odds arithmetic in
  `CCollectableItem::Update/Add` instead of assuming the desktop boost flag
  matches.
- Finish behavior support for every added mobile furniture row that has a
  named mobile `CHotSpot`/`CBehavior` route.
