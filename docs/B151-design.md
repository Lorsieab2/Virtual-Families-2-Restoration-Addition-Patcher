# Virtual Families 2 Restoration/Addition Patcher B151 Design

B151 starts from the final B150 hotfix. Its two major workstreams are the
expanded-map implementation and a new additive goal/longevity set. None of the
items below belong in the B150 executable or save schema.

## Requested goals

### Resource goals

| Goal | Requirement |
| --- | --- |
| No More Worries | Have the maximum amount of coins in the bank account. |
| Solving World Hunger | Have the maximum amount of food in the fridge. |

The B151 implementation must use the game's real saturation values rather than
an approximate large number. Current B150 evidence uses 3,999,999,999 for the
coin cap and signed INT_MAX for food; both values must be revalidated at the
native achievement trigger before assigning goal IDs.

### Pet goals

| Goal | Requirement |
| --- | --- |
| A Furry Companion | Buy a pet and place it in the house. |
| The Cat's Meow | Welcome a black kitten, snow white cat, tabby cat, hairless cat, or fluffy grey cat into the home. |
| Man's Best Friend | Welcome a beagle, yellow lab, black lab, longhair puppy, or chihuahua into the home. |
| Itsy Bitsy | Have a tarantula in the home. |
| Hampster Dance | Have a hamster in the house. |
| Lovely Lizards | Have a lizard in the house. |

Keep the requested pun/title spelling **Hampster Dance**, while the requirement
uses the animal spelling **hamster**. Pet completion must be based on a live pet
placed in the world, not merely an item bought or left in the Tool Tray. B151
must derive the exact inventory/pet IDs from the native pet tables before
coding the cat, dog, tarantula, hamster, and lizard sets.

### Longevity goals

| Goal | Requirement |
| --- | --- |
| Lucky 70's | Have a person reach age 70. |
| Great 80's | Have a person reach age 80. |
| Mighty 90's | Have a person reach age 90. |
| Centenarian | Have a person reach age 100 or more. |
| Oldest Person in History | Have a person surpass age 122. |

**Centenarian** is the corrected spelling. Raw-age candidates are 1,400,
1,600, 1,800, 2,000, and greater than 2,440 if VF2's observed
displayed-years-times-20 conversion holds. B151 must validate that conversion
against the actual birthday/display and death routines before patching the
thresholds.

### Family-tree appearance goals

| Goal | Requirement |
| --- | --- |
| Return of the Rainbow | Have a female villager with head value 48 in the family tree. |
| Spiky! | Have a male villager with head value 48 in the family tree. |

These checks must scan persistent family-tree records so a qualifying relative
continues to count after leaving the active household. The implementation must
verify VF2's native gender encoding and head-field offset instead of assuming
the live-villager layout is identical to the saved tree layout.

## Older Villagers patch

Add a separately gated **Older Villagers** patch. With it disabled, the stock
death/lifespan path must remain byte-for-byte native. With it enabled:

- ordinary death ages should follow a normal-style distribution centered near
  age 75, with most villagers dying in their mid-70s through 80s;
- the tail must genuinely allow ages 90, 100, and rare survival beyond 122 so
  the new goals are attainable;
- illness, starvation, exhaustion, time-away simulation, birthdays, family
  tree age records, and save/reload must all use the same resulting lifespan;
- the implementation must patch the native mortality decision, not freeze age
  or repeatedly cancel a death event;
- the distribution width and any hard upper bound must be chosen only after
  the stock mortality probability and random-number path are disassembled.

The base-game path is now identified. Once per displayed birthday it uses
`T = 55 + N`, where N is the number of active nutrition groups, then applies
`min(100, 10 * (age - T))` percent death chance after age T. Only four food
groups are normally reachable, so fully nourished villagers first risk old-age
death at 60 and are guaranteed to die by 69. B151 should replace this annual
decision block while deciding separately whether the stock IsOld age-55
recovery penalty should remain.

The option belongs in the patcher's native overlay matrix. If adding it would
double the current 16-EXE matrix, B151 should first evaluate a runtime-gated
superset or binary-delta overlay so package size does not grow needlessly.

## Additive goal-system contract

Before assigning IDs, B151 must audit and extend together:

- the achievement record table, saved completion/progress storage, reset
  bounds, display order, goal-scene height, and string lookup range;
- every event hook that should complete a goal: money/food adjustment, pet
  placement or household load, birthday/age update, and family-tree insertion
  or load;
- Reset Achievements and any complete/reset cheat paths;
- behavior when B151 is enabled on a vanilla or B150 save, and when the option
  is later disabled.

New hooks should prefer relocation retargeting or fixed-size detours to
end-of-section code caves. Do not repeat B150's unsafe pattern of inserting
bytes into a native function without auditing every crossing branch.

## Expanded map

The authoritative visual reference remains
`work/reference_images/Expanded VF2 Map.png`. Preserve the centered house at
its current scale, add one complete tile on all four sides and corners, fill the
new perimeter with matching grass, and extend the northwest beach into the
rounded sandy area. Camera limits, map bounds, walkability, placement, hit
testing, weather/decor coverage, and save-safe coordinates must expand with the
art.

## Workstream 3: Holiday Ornaments collection

B151's focused third workstream is the complete mobile 1.7.16 Holiday Ornaments collection. It restores carrying IDs `0x9E`-`0xA9`, their three spawn rectangles, exact rarity ranges, sixth Collections Chest page, 72-item total, collection persistence, achievements, Collector offer/reset behavior, canonical artwork, disabled-build cleanup, and sixteen-state matrix coverage. The native implementation preserves stock exact-match `Find`, `WasItemSpawned`, `Add`, and Lucky Rock behavior and uses isolated caves or relocation-only insertions where stock code has no room.

All sixteen executables compile; 129 source/exporter tests and independent linked validation pass. This is static/build evidence only. Launch, chest navigation, pickup/duplicate/completion, save/reload, Collector Keep/Sell, and collection-cheat testing still require a manual in-game cycle.

### Explicitly deferred

The expanded-map concept and proposed next-build goals are not B151 workstreams and are not implemented in this build. Their mockups and design notes remain planning material only.
