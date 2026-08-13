# B158 Island Events and Bathroom 2 leak build

Build output: `outputs/VF2-B158-Island-Events-Bathroom2-Leaks-20260812-r34`

The enabled generator was seeded from `outputs/VF2-B158-Native-Spawn-Cheats-20260812-r33` and run with `VF2_ENABLE_ISLAND_EVENTS=1`. The linked executable is:

`Virtual Families 2 - Island Events Bathroom 2 Leaks.exe`

Size: `1,743,360` bytes

SHA-256: `AA6462518B13550617BFB177C279CA1C0300E8FD2A2AEFB689ECE289119757DA`

The generated manifest records 25 appended Island Event rows. Twenty-three
rows have exact recovered firing/award/impact routes; `MeteoriteFallsInYard1`
and `MarchingBandTripExpenses` retain mobile `CanFire=false`.

Outcome routing uses the native desktop actions:

- money: `CMoney::Adjust`
- furniture: `FurnitureManager::AddToStorage`
- tool item: `CToolTray::AddItem`
- fossil collectible: `CCollectableItem::Add`
- Teens cleanup: `SpawnSockInHouse(10)` and `SpawnTrashInHouse(10)`

The Bathroom 2 leak helper is enabled in the same Island Events overlay. With
renovation item `0xE6`, Water Pressure Surge adds north toilet `0x48`, shower
`0x49`, and sink `0x4A` props. `CVillager::NewBehavior` maps those active props
to the native north-leak reactions while preserving the native repair behavior
IDs.

Verification recorded for this build:

- generator completed successfully
- x86 compilation and link completed successfully
- focused Island Event and gate tests: `34` tests, `OK`, `2` intentional skips
- full patcher/exporter/GUI suites: `337` tests, `OK`, `2` intentional skips
- IDA Pro 9.4 loaded and auto-analyzed the linked PE successfully
- live player dialog/outcome, save/load, and repair QA remains pending
