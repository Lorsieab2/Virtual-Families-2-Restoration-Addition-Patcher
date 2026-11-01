# Virtual Families 2 save format (desktop, B200 line)

Reader: `src/vf2_save_reader.py` (read-only). Tests: `tests/test_vf2_save_reader.py`. Fixtures:
`tests/fixtures/vf2_saves/*.ldw.gz`, real saves copied and gzip-compressed byte for byte by
`scripts/make_vf2_save_fixtures.py <folder of copies>`.

**Standard.** A field is **VERIFIED** only when (1) the game's own save writer and loader code put it
at that offset and the code that uses it shows what it is, and (2) real saves hold values consistent
with that. Anything short of both is **UNCONFIRMED** and the reader returns it raw under an
`unconfirmed_*` name. Nothing here is inferred from values alone.

**Code evidence** comes from the desktop object files the patcher relinks (`work/desktop_obj_files`,
gitignored, extracted from the player's install): every function named below was disassembled with
its relocations (capstone over the COFF objects). **Save evidence** comes from 59 copied `.ldw` files out of
the owner's folders (`Documents\LDW\Virtual Families 2`, three "jessie" copies, `- Modded B171`,
`- Modded B192`, `- Modded B202`), all decoded by a separate throwaway decoder and by the reader.

Offsets: "gs" offsets are `theGameState`-relative, as the game code uses them. **File offset = gs
offset + 8** (the 16-byte header, then `theGameData`, which is `theGameState+8`). Record-relative
offsets are given as `+0x...`. All little-endian; `i32`/`u32` 4 bytes.

---

## 1. Which files the game writes, and where (VERIFIED)

| What | Rule | Evidence |
|---|---|---|
| Save folder | `<Documents>\LDW\<exe file name up to its FIRST '.'>\` | `ldwGameState::MakePath(name, false)`: `GetModuleFileNameA`, take the part after the last `\`, cut at the first `.` (`strchr`), `SHGetSpecialFolderPathA(CSIDL_PERSONAL=5)`, append `\LDW`, `CreateDirectoryA`, append `\<exe name>`, `CreateDirectoryA`, append `\<file>`. |
| Save file name | `Virtual Families 2<N>.ldw` | `ldwGameState::MakeGameStatePath(N)`: `sprintf("%s%d.ldw", GetGameName(), N)`; `theGameState::GetGameName` returns the constant `"Virtual Families 2"` (not the exe name). |
| Slot 0 | `Virtual Families 20.ldw`, 160 bytes: the shared settings block (player names, slot-in-use flags, current slot) | `theGameState::Save(0)` / `Load(0)`: 0x90 bytes from gs+0x25B20. |
| Slots 1..5 | `Virtual Families 21.ldw` .. `25.ldw`, 154,408 bytes each: one family each | `theGameState::LoadCurrentGame` tries slots 1..5 by the flags gs+0x25B99..0x25B9D; `theChangePlayerDlg` handles players 1..5. |
| Previous save | `Virtual Families 2<N+20>.ldw` (221..225): the save that slot N held before the last save | `ldwGameState::Save(data, size, N)`, only when N > 0: `remove(path(N+20))`, then `rename(path(N), path(N+20))`, then write `path(N)`. Slot 0 is never rotated, so `220.ldw` never exists. |
| Deleting a player | removes only `path(N)`; `N+20` stays | `theChangePlayerDlg::HandleMessage` clears gs+0x25B98+N and calls `theGameState::RemoveGameFile(N)` -> `ldwGameState::RemoveFile(N)` (one `remove`), then saves slot 0. |
| `ldwLog.txt` | in the save folder, shared by all slots | `ldwLog::Open` / `Write` / `WriteLine` / `NewLine`: `MakePath("ldwLog.txt")`. Not part of any save. |
| `wc.dat` | in the save folder, shared | `CCredentials::GetPath`: `MakePath("wc.dat")`; `CCredentials::Init` / `Save` (web-client credentials). Not part of any save. |
| `ldw.ini` | beside the **exe**, not in the save folder | `ldwGameState::GetConfigPath`: the exe's folder; read with `GetPrivateProfileIntA` (`FullScreen`, `ForceFullScreen`, `ForceWindowed`). |
| N+40 files | **none**: no code path in the game builds a slot number other than N and N+20 | every caller of `MakeGameStatePath` / `Save` / `Load` / `RemoveFile` (ldwGameState, theGameState, theChangePlayerDlg). |

Real folders agree: every `.ldw` the game names is 160 bytes (slot 0) or 154,408 bytes; `221`/`222`/`223`
pair with `21`/`22`/`23` (same header time, older content); slot 0's in-use flags match the slot
files present (B202: `1,1,1,0,0` with `21`,`22`,`23` on disk).

Files in the owner's folders the game never writes (player copies): `* - Copy*.ldw`, `* copy.ldw`,
`Virtual Families221.ldw` (no space: not `GetGameName()+N`), `Virtual Families 252.ldw` (N=52).
`virtual families 25.ldw` (lower case) is slot 5 (Windows names are case-insensitive) but holds a
12-byte legacy header and a 154,388-byte payload, which this build's `theGameState::Load(5)` refuses
(section 2).

**The patcher's per-slot files** (beside the game's): `<save folder>\Virtual Families 2 Patcher
Data\Children\<save file name>.dat`, e.g. `Virtual Families 21.ldw.dat` and `Virtual Families
221.ldw.dat` (`runtime/native/b200kids/b200kids.cpp` `SidecarPath`: the whole save file name plus
`.dat`); set-aside copies `<name less .dat>.unreadable-N.dat`. The DLL rotates them with the game's
N -> N+20 rotation. The Time Controls DLL keeps nothing per slot (`vf2time.ini`/`vf2time.log` sit in
the install's `Virtual Families 2 Patcher Files`).

### Where the Back Up / Restore tool's rule differs (`feat/tools-tab`, `src/vf2_save_backup.py`)

- `_SLOT_IN_NAME = r"virtual families ?2(\d+)"` makes the space optional, so `Virtual Families221.ldw`
  (a name the game never writes) is filed as slot 1's previous save. The game's name is exactly
  `Virtual Families 2` + N. The regex is also unanchored, so any name *containing* the pattern counts
  (e.g. `Virtual Families 252.ldw` is ignored only because 52 is out of range).
- `game_exe_name(folder)` returns `<folder>.exe` and the module docstring says the folder is the exe
  name "without .exe". The game cuts the exe name at its **first** `.`, so an exe named with a dot
  (e.g. `VF2 B20.2.exe`) saves to `LDW\VF2 B20`, and `<folder>.exe` is not that exe.
- The N+20 rule, slot 0 = settings, `ldwLog.txt` belonging to no slot, and the Children sidecar
  matching its save file's slot are all correct. Restoring one slot while leaving `N+20` in place is
  consistent with the game (a deleted player's `N+20` also stays).

---

## 2. Header (VERIFIED)

`ldwGameState::Save` writes the global `gameStateHeader` (16 bytes) then the payload; `Load` checks it.

| Off | Type | Field | Evidence |
|---|---|---|---|
| 0x00 | char[4] | `ldwg` | `Load` compares bytes `6C 64 77 67`; `.data` initial value |
| 0x04 | i64 | start time (`_time64`) that `GetSecondsFromGameStart` counts from | `ldwGameState` ctor `_time64(&hdr+4)`; `GetSecondsFromGameStart` = `difftime(now, hdr+4)`, resets it if negative; `AdjustSecondsFromGameStart` adds to it; `Load` copies the file's header into the global, so it carries from save to save. Real: 2021-06..2024-09 values. |
| 0x0C | u32 | payload size | `Save` stores its size argument; `Load(ptr,size,slot)` requires it equal (0x25B18 family, 0x90 settings). |

Legacy form, also accepted by `Load`: magic, i32 time at +4, u32 size at +8, payload at +12. The
real `virtual families 25.ldw` has it with size 0x25B14, which `theGameState::Load` rejects (it asks
for exactly 0x25B18). The reader refuses it the same way.

## 3. Family save map (`theGameState::Save` / `Load(int N>0)`, 0x25B18 bytes) (VERIFIED)

| gs off | file off | size | Component | Save / load function |
|---|---|---|---|---|
| 0x0168 | 0x0170 | | CAchievement | `CAchievement::SaveState` / `LoadState` (not decoded) |
| 0x0F24 | 0x0F2C | | CCollectableItem | not decoded |
| 0x178C | 0x1794 | | CDailyEmail | not decoded |
| 0x1840 | 0x1848 | 0xCB74 | **CFamilyTree** | `CFamilyTree::SaveState` / `LoadState` (section 5) |
| 0xE3B4 | 0xE3BC | 0x10 | **CFoodStore** | section 6 |
| 0xE3C4 | 0xE3CC | | CFurnitureManager | not decoded |
| 0x163C8 | 0x163D0 | 0x34 | **CGameStats** | section 6 |
| 0x163FC | 0x16404 | 0x14 | **CGameTime** | section 6 |
| 0x16410 | 0x16418 | | CInventoryManager | not decoded |
| 0x168B4 | 0x168BC | 0x0C | **CMoney** | section 6 |
| 0x168C0 / 0x168CC / 0x16914 / 0x16FD8 | | | CTech / CToolTray / CTutorialTip / CPetManager | not decoded |
| 0x172A8 | 0x172B0 | 30 x 0x7BC | **CVillagerManager** | `CVillagerManager::SaveState` -> `CVillager::SaveState` per slot 0..29 (section 4) |
| 0x25AB0 | 0x25AB8 | 3 x i32 | pending baby slots | section 6 |
| 0x25ABC | 0x25AC4 | char[20] | player nickname | section 6 |
| 0x25AD8 | 0x25AE0 | i32 | save version, 1001 | `Save` writes 0x3E9 before writing; `Load` resets `CDailyEmail` when < 0x3E9 |
| 0x25B18 | 0x25B20 | i32 | speed option | section 6 |

## 4. Villager record (0x7BC, slot order 0..29) (VERIFIED unless marked)

`CVillager::SaveState` (`CVillagerManager::SaveState` calls `DetachAll` first for a villager who is
active, home and not flagged at +0x1BB50). `LoadState` is the exact mirror. The record index is the
household slot (`CVillagerManager` slot, the id `CFamilyTree` stores); the slot number itself is not
written.

| Off | Type | Field | Source in CVillager | Evidence |
|---|---|---|---|---|
| 0x000 | u8 | active | +0x1BB84 | written 0 when +0x1BB50 is set. `VillagerExists`, `Population`, `GetRandomCollegeKid` test it. A pending baby is inactive (section 7). |
| 0x001 | u8 | left home | +0x1BB88 | `CVillager::SetLeftHome` sets 1. `VillagerExists` is false for it. |
| 0x004 | u32 | game seconds when left home | +0x1BB8C | `SetLeftHome`: `CGameTime::Seconds()`; `YearsAwayFromHome` = (Seconds - it) / 12000. |
| 0x008 | 0xA0 | CVillagerBio | +0x6A54 | `CVillagerBio::Copy` (0x28 dwords) |
| 0x0A8 | 0x98 | CVillagerState | +0x6AF4 | `CVillagerState::Copy` (0x26 dwords) |
| 0x140 | 0x10 | CVillagerSkills | +0x6B8C | `CVillagerSkills::Copy` |
| 0x150 | 12 | CLikeList | +0x1BC34 | raw; structure UNCONFIRMED |
| 0x15C | 12 | CDislikeList | +0x1BC40 | raw; structure UNCONFIRMED |
| 0x168 | u16 x 0x19B | AI values | +0x6BC4 stride 0xD0 | `SaveAI`: min(entry+0, entry+8) per entry; `LoadAI` also reads an older 0x193 x u32 layout. Meaning UNCONFIRMED. |
| 0x7B8 | u32 | AI value count, 0x19B | | `SaveAI`. Real: 411 in every active record. |

### CVillagerBio (record +0x008; villager +0x6A54)

| Bio off | Rec off | Type | Field | Evidence |
|---|---|---|---|---|
| 0x00 | 0x008 | i32 | age, in age units | `IncrementAge` adds to it; `theVillagerScene::UpdateScene` shows `age / 20` as years; `IsOld` >= 1100; `Init`: no career below 340; college at 380 (`AllVillagersTimeflowUpkeep`, `GetRandomCollegeKid`). Real: Elsa 833 = 41 years on screen math. |
| 0x04 | 0x00C | i32 | gender, 0 male / 1 female | `Reset`: rand(100) > 49; `SetRandomName`: 1 picks the female name lists; `GetMatriarch` wants 1, `GetPatriarch` 0. Real: female names have 1. |
| 0x08 | 0x010 | i32 | first-name list index | `SetRandomName`: rand(157)+1, then copies the comma-separated entry at that index. |
| 0x0C | 0x014 | i32 | UNCONFIRMED | `SetRandomName(arg)` stores arg (rand(50)+1 when -1); `Impregnate` passes the mother's value to the baby. |
| 0x10 | 0x018 | char[25] | name | `GenerateName(bio+0x10, 0x19)`; `AddOffspring` / `StartNextGeneration` copy it into the tree. |
| 0x2C | 0x034 | i32 | head | `Init` (0..49, from the parents' heads); tree +0x20 copies it. |
| 0x30 | 0x038 | i32 | body | `Init`; tree +0x24 copies it. |
| 0x34 | 0x03C | char[25] | father's name | `Init` arg 4 (`strncpy 0x19`); empty unless both parent names are given. Shown by `DrawDetailVillagerParents`. Real: "Joey" for every born child: `CVillagerPlans::ProcessCurrentPlan` calls `Impregnate` with the literal `"Joey"`, so this is the game's own value, not the father's real name. |
| 0x4E | 0x056 | char[25] | mother's name | `Init` arg 5. |
| 0x68 | 0x070 | i32 | father's head | `Init` arg 7; drawn with the head sheet in `DrawDetailVillagerParents`. |
| 0x6C | 0x074 | i32 | father's body | `Init` arg 6 |
| 0x70 | 0x078 | i32 | mother's head | `Init` arg 9 |
| 0x74 | 0x07C | i32 | mother's body | `Init` arg 8 |
| 0x78 | 0x080 | i32 | (mother) father's bio+0x0C at conception | `Impregnate` arg 1 |
| 0x7C | 0x084 | char[24] | (mother) father's name at conception | `Impregnate` arg 2, `strncpy 0x18` |
| 0x98 | 0x0A0 | i32 | (mother) father's body at conception | `Impregnate` arg 4 |
| 0x9C | 0x0A4 | i32 | (mother) father's head at conception | `Impregnate` arg 3 |

There is **no surname / family-name field** anywhere in the save: VF2 villagers have one name (bio+0x10),
the string table has no surname string, and the only other names are the parents' names above, the
Family Tree's copies, the player nickname (gs+0x25ABC) and slot 0's player names.

### CVillagerState (record +0x0A8; villager +0x6AF4)

| State off | Rec off | Type | Field | Evidence |
|---|---|---|---|---|
| 0x00 | 0x0A8 | u32 | UNCONFIRMED: real seconds accumulated toward the next age step | `AllVillagersTimeflowUpkeep` adds elapsed real seconds, caps it, ages by it / 60 / speed option, keeps the remainder. |
| 0x04 | 0x0AC | u32 | UNCONFIRMED: `GetSecondsFromGameStart` at the last upkeep | same function |
| 0x08 | 0x0B0 | i32 | UNCONFIRMED | `Reset(age)` stores the age; `Impregnate` copies it to +0x24; birth fires when +0x24 + 20 < +0x08 |
| 0x0C | 0x0B4 | i32 | health 0..100; 0 = dead | `SetHealth` / `AdjustHealth` clamp to 0..100 and store the cause only at 0; `GetMatriarch`/`Population` need > 0. |
| 0x10 | 0x0B8 | i32 | cause of death (ECauseOfDeath), -1 while alive | same two functions. Enum values UNCONFIRMED. |
| 0x24 | 0x0CC | i32 | pregnant when nonzero | `Impregnate` writes it; `Population` adds +0x28 while it is nonzero; behaviours test it. Real: Wizzy 560 with a pending baby. |
| 0x28 | 0x0D0 | i32 | babies expected 1/2/3 | `Impregnate` |
| 0x34..0x50 | 0x0DC..0x0F8 | i32 x 8 | energy, happiness, happiness trend (-500..500), hunger, dirtiness, poo, fertility, procreation desire (1..99) | `SetEnergy` .. `SetProcreationDesire` each store one offset with its clamp |
| 0x5C | 0x104 | u8 x 7 | symptoms | `SetSymptom` / `IsSick` |
| 0x64 | 0x10C | u32 x 7 | symptom expiry (`GetSecondsFromGameStart` + (rand(12)+6)*3600) | `SetSymptom` |
| others | | | UNCONFIRMED | `Reset` initialises them; not decoded |

### CVillagerSkills (record +0x140; villager +0x6B8C)

| Off | Field | Evidence |
|---|---|---|
| +0x00 i32 | career id, -1 none | `CareerType`: -1 -> 0, <= 0x25 -> 1, <= 0x5E -> 2, else 3; `SetNoCareer` writes -1. Tree +0x30 copies it. |
| +0x04 i32 | career level (`GetCareerLevelName` uses & 7) | |
| +0x08 i32 | UNCONFIRMED (Reset 10, SetNoCareer 0) | |
| +0x0C i32 | salary | `UpdateSalary` from the career table |

## 5. Family Tree (`CFamilyTree::SaveState`, gs+0x1840) (VERIFIED)

| Off | Type | Field | Evidence |
|---|---|---|---|
| +0x0000 | i32 | evicted flag (`CFamilyTree+0`) | `Reset` 0; `EvictFamily` = `Reset` then 1; the Settings Evict button is hidden when it is nonzero. Real B202 slot 3: 1 (a family started after an eviction). |
| +0x0004 | 30 x 0x6C8 | SFamilyRecord, one per generation, oldest first | `SaveState` copies all 30; `LoadState` copies records until the first whose +0 byte is 0 and counts them into `CFamilyTree+4` (`NumGenerations`). The count itself is not saved. |

The generation of a record is its position (record 0 = the founders). The window is 30 records:
`StartNextGeneration` calls `MakeRoomInTree` at 30, which drops the oldest record, so after 30
generations position no longer equals generation, and the stock save keeps no lifetime count.

### SFamilyRecord (0x6C8)

| Off | Type | Field | Evidence |
|---|---|---|---|
| 0x000 | u8 | present | `StartNextGeneration` / `UpdateParents` set 1; `GetFamilyRecord`, `GetCurrentFamily` test it |
| 0x001 | u8 | can start next generation | `CanStartNextGeneration`; `ReportDeath` sets it when a parent of children dies, clears it when no child survives |
| 0x002 | u8 | next-generation notice pending | `NeedNextGenerationNotify` / `ResetNextGenerationNotify`; set with +0x001 |
| 0x004 | 0xD8 | parent 1 (SPeepRecord) | `StartNextGeneration` (the founder or heir) |
| 0x0DC | 0xD8 | parent 2, the spouse | `UpdateParents` (from `CDatingScene::HandleMessage`, the marriage); `CanMarry` = parent 1 present and parent 2 absent |
| 0x1B4 | i32 | child count (dead children keep counting) | `AddOffspring` refuses at 6; `EmptyOffspringSlots` = 6 - count |
| 0x1B8 | 6 x 0xD8 | children | `AddOffspring` |

### SPeepRecord (0xD8)

| Off | Type | Field | Evidence |
|---|---|---|---|
| 0x00 | char[25] | name | `ldwStrCopy(rec, villager+0x6A64, 0x19)`; `ChangeName` updates it |
| 0x1A | u8 | present | |
| 0x1C | i32 | gender | from villager+0x6A58 |
| 0x20 | i32 | head | from villager+0x6A80 |
| 0x24 | i32 | body | from villager+0x6A84 |
| 0x28 | i32 | household slot, -1 after death | from villager+0x1BB48; `ReportDeath` writes -1; `FindPeepRecord`, `CountSurvivingChildren` use it. Real: dead/older parents -1. |
| 0x2C | i32 | parent 1: index of the previous record's child who became this generation's heir (-1 founder/none) | `StartNextGeneration` searches the previous record's children for the heir's id; `UpdateParents` writes -1 for a spouse; `MakeRoomInTree` writes -1 on the new oldest record. Real: every heir_index points at the child with the heir's name (all 9 links of a 10-generation save). Children: not written (0); meaning there UNCONFIRMED. |
| 0x30 | i32 | career id | `UpdatePeepRecord` copies CVillagerSkills+0 while the villager exists |
| 0x34 | char[40] | likes text | `UpdatePeepRecord`: `CLikeList::GetListAsString` |
| 0x5D | char[40] | dislikes text | `UpdatePeepRecord`: `CDislikeList::GetListAsString` |
| 0x85..0xD7 | | UNCONFIRMED | not written by any CFamilyTree function |

**Marriage / spouse link**: the current record's parent 2 (+0xDC, present byte +0xF6, slot +0x104).
The villager records hold no spouse field. **Divorce** does not exist in the stock game (the
patcher's Divorce Spouse cheat zeroes +0xDC; `docs/REQUEST_LEDGER.md`).

## 6. Clock, money, food, statistics, misc (VERIFIED unless marked)

**CGameTime (0x14, gs+0x163FC)**: +0x00 speed (`CGameTime+0x20`; `SpeedMultiplier` = speed / 10, 0 =
paused; `Reset` takes the speed option), +0x04 previous speed, +0x08 `GetSecondsFromGameStart` at the
last speed change, +0x0C game seconds at that change, +0x10 `GetSecondsFromGameStart` when saved
(`SaveState`). `Seconds()` = +0x0C + (real now - +0x08) / multiplier, or +0x0C while paused; the
reader evaluates it at +0x10 (`game_seconds_at_save`). `LoadState` puts the offline time (now - +0x10)
in `CGameTime+0x30`.

**Time units.** One age unit = 60 x speed-option real seconds (`AllVillagersTimeflowUpkeep`:
accumulated real seconds / 60 / gs+0x25B18); 20 age units = 1 year on screen. With the default
option 10: 600 s per unit, 12,000 s per year, which matches `YearsAwayFromHome` (game seconds /
12,000). An option of 999 or more zeroes the accumulator, so nobody ages (the real modded saves have
1009). Real seconds become game seconds by the `Seconds()` formula above.

**CMoney (0xC, gs+0x168B4)**: +0 u32 balance (`SaveState`: double + 0.5 truncated); +4 interest
rate x 100 in the low 16 bits, OR 0x7F800000 (`LoadState` decodes low16 / 100 into `CMoney+8`, the
fraction `UpdateInterest` pays per 86,400 game seconds; default 0.1; a legacy float form is also
accepted); +8 game seconds of the last interest payment (`CMoney+0xC`, `UpdateInterest`/`Reset`).

**CFoodStore (0x10, gs+0xE3B4)**: +0 food (`CFoodStore+0x78`, clamped >= 0; the daily email's low-food
branch tests <= 100); +4 bool, +8 i32, +0xC..0xF bytes: UNCONFIRMED.

**CGameStats (0x34, gs+0x163C8)**, a copy of `CGameStats+0..0x33`: +0x00 `GetSecondsFromGameStart`
stamp the "real game hours" statistic counts from (`GetStatRealGameHoursThisGame`); +0x08 babies born
(`Impregnate` adds its baby count); +0x20 oldest age reached, years (`AllVillagersTimeflowUpkeep`);
the rest UNCONFIRMED.

**Pending babies, gs+0x25AB0/4/8**: the slots `Impregnate` spawned (inactive) for the first, second
and third baby, -1 none. `AllVillagersRealtimePhysiologyAndProductivityUpkeep` activates them
(birth) and writes -1. Real: B171 slot 1 has 1 with slot 1 inactive and the mother pregnant.

**Nickname, gs+0x25ABC char[20]**: `theCreateNickNameDlg` / `theChangePlayerDlg` (`GetText(.., 0x14)`),
also copied to slot 0's player-name list; `RestartCurrentGame` keeps it.

**Speed option, gs+0x25B18**: `InitOptions` 10; values 5/10/20 change the upkeep caps; >= 999
stops aging; `theCreateNickNameDlg` resets >= 999 to 10 for a new player. Names of the settings
UNCONFIRMED.

**Pause / Unpause (VERIFIED in the stock exe, traced for Game Speed, `src/vf2_game_speed.py`).** Options Yes:
UpdateAll 0x42ACB0, `CGameTime::SetSpeed(999)` 0x42269B, gs+0x25B18 += 999 (0x4226A6), UpdateAll; Options No:
UpdateAll, `SetSpeed(10)` 0x4226EA, gs+0x25B18 = 10 (0x4226F5), UpdateAll; Space 0x43BC2D the same without
UpdateAll (unpause stores option - 999, 10 if 0). `SetSpeed` 0x427A50 returns at once for the current speed, else
banks `Seconds()` 0x427920 in +0x0C, stamps +0x08, moves +0x00 to +0x04 and stores the new speed, **except that
999 stores 0** (`xor ebp, ebp` 0x427A6F): a paused clock is stopped (real saves: 1009 / 0 / 10). Those four are
the only callers of SetSpeed and the game writes no speed option but 10, +999, option - 999 and the store time
skip's temporary - 999 / restore (0x432A2F / 0x432A86): there is no Slow or Fast. While paused the two-second
update still restamps each active, at-home, living villager's state+4 and zeroes state+0 (0x4997E9..0x499872);
UpdateAll also writes gs+0x25AF4 = now (0x42ACF7, no reader). The stock Seconds() is x87 at the CRT's 53-bit
default (0x4C8CB5); the patched build's (relinked SSE object code, B202 0x468B50) rounds the elapsed seconds to
a float, which agrees only below 2^24 s. Note: the reader's `game_seconds_at_save` uses the float form, so for
the stock exe it can be off by a few seconds past 2^24 s since the last speed change (no real save is).

Not saved: the life-event queue (gs+0x25CE8, 20 x 0x3C) and the email queue lie past gs+0x25B20.

## 7. Settings file, slot 0 (0x90 from gs+0x25B20) (VERIFIED unless marked)

| Off | Field | Evidence |
|---|---|---|
| 0x00 i32 | current slot (1..5; 0 none) | `LoadCurrentGame`, `theChangePlayerDlg` |
| 0x04 i32 | the slot before the last switch | `theChangePlayerDlg::HandleMessage` (copies 0x00 here before a switch, and in one branch copies it back); `InitGameInfo` 0 |
| 0x08 u8 | set to 1 by `InitGameInfo`; when set, 0x8C gets the same time as 0x88 | `InitGameInfo` |
| 0x0C i32 | 0; nothing reads it | `InitGameInfo` only |
| 0x09 u8 | full screen | `InitGameInfo` (FullScreen / ForceFullScreen), `Load(0)` (ForceWindowed) |
| 0x10 | player names, 5 x char[0x15] for slots 1..5 | `theChangePlayerDlg`, `theCreateNickNameDlg` |
| 0x79..0x7D u8 | slot 1..5 in use | `LoadCurrentGame`; delete player clears it |
| 0x80 i32 | 1001 | `InitGameInfo` |
| 0x84 u8 | "no slot could be loaded" | `LoadCurrentGame` clears it, sets 1 when no slot loads |
| 0x88 u32 | `_time64` low dword at `InitGameInfo` | |
| 0x8C u32 | the same time when 0x08 is set, else 0 | `InitGameInfo` |

**Per slot: only the names and the in-use flags (VERIFIED, every reference to gs+0x25B20..0x25BAF in the desktop
objects; audited for Copy Player Slot, 2026-10-31).** Every other field above is the game's own. And the game
rebuilds both at every start: `theGameState::Load()` loads slot 0, then each `Virtual Families 2<N>.ldw` for
N = 1..5 in turn; a save that loads gives its player name (gs+0x25ABC) to the slot's entry and sets its flag, one
that does not gives the entry `NEW PLAYER` (0xA34) and clears the flag. So the settings file only has to agree
with the saves until the next start; Copy Player Slot and Rename Family write exactly what that rebuild gives.

**Nothing of a slot lives outside the save folder (VERIFIED, imports and strings of every desktop object).** The
registry functions are only in `FlashPlayer.obj` (its statically linked ATL registrar, COM registration). The
other files the game opens are `ldw.ini` (beside the exe, read only), `ldwLog.txt` and `wc.dat` (save folder,
shared: the engine log and `CCredentials`, the LDW WebClient login), and its data files (`anims.dat`, `cmap.dat`,
`lsmap.dat`, `wpts.dat`, `petanimpts.dat`, `sm.xml`). Achievements (CAchievement), the daily email and the
collection are in each slot's save (section 3).

## 8. Status of a villager, from the saved bytes

All from the code above: **in the house** = active, not left home, health > 0 (`VillagerExists` +
alive). **Dead** = active and health <= 0, cause at state+0x10; `AllVillagersTimeflowUpkeep` clears
active and calls `CFamilyTree::ReportDeath` once 240 age-unit steps of real time have passed since
the last upkeep stamp, so a dead villager can be saved still active. **Away** = active with left home
set, for three reasons that all call `CVillager::SetLeftHome`: college (age crosses 380 with no
career, `AllVillagersTimeflowUpkeep`, life event 5), Boarding School (`CScrollingStoreScene::HandleUpgrade`,
message 0x4C8 "%s has been sent away to school!"), the Talent Scout island event
(`CEventTheTalentScout::ImpactGame`). **The save does not record which one** (only the flag and the
game time); the reason is UNCONFIRMED from a save and must be captured at the call. **Unborn** = a
slot in the pending-baby list (inactive). An inactive slot outside that list is empty; its bytes can
still hold an old villager.

## 9. What the log DLL needs to hook (code evidence; no live test)

The save holds state, not history, and the life-event queue is not saved, so each event has to be
caught when the game makes it:

| Event | Where the game does it | Notes for a hook |
|---|---|---|
| Conception (baby recorded) | `CVillager::Impregnate` (from `CVillagerPlans::ProcessCurrentPlan`, `theMainScene::TryToMakeBaby`, `ConceiveChildWith`) | spawns 1-3 inactive babies, `CFamilyTree::AddOffspring` each **at conception**, sets gs+0x25AB0..B8, life event 2 |
| Birth | `CVillagerManager::AllVillagersRealtimePhysiologyAndProductivityUpkeep` | sets the pending slots active (+0x1BB84 = 1) and the list to -1 |
| Adoption (child) | `CFamilyTree::AddOffspring` from `CScrollingStoreScene::HandleUpgrade`, `CEventTheLittleVisitor1/2::ImpactGame` | |
| Founder adoption / next generation | `CAdoptionScene::HandleMessage` -> `CFamilyTree::StartFamilyTree` / `StartNextGeneration(heir, id)` | heir index written at record +0x30 |
| Marriage | `CDatingScene::HandleMessage` -> `CFamilyTree::UpdateParents`, life event 1 | |
| Death | health 0 in `CVillagerState::SetHealth` / `AdjustHealth` (cause), life event 4 in `CVillagerPlans::StartNewBehavior`, removal + `CFamilyTree::ReportDeath` in `AllVillagersTimeflowUpkeep` / `StartNewBehavior` | three different moments; which one a log calls "death" is the owner's choice |
| College / Boarding School / Talent Scout | `CVillager::SetLeftHome` and its three callers | hook the callers to know the reason |
| Eviction | `theOptionsDialog::EvictFamily` -> `CFamilyTree::EvictFamily` | |
| Divorce | none in the stock game | only the patcher's cheat |
| Promotion | `CVillagerSkills::AdvanceCareer`, life event 3 | |

## 10. Corrections

- `docs/discoveries.md` (2026-08-06 child-limit notes) called the Family Tree block's first dword "a
  four-byte generation count". It is `CFamilyTree+0`, the eviction flag; corrected in place.

## 11. The name a family slot is shown under (Rename Family, `src/vf2_rename_family.py`)

VF2 has no family surname (section 4). The one name the player types for a family slot, and the one the game
shows for it, is the **player name**. Addresses are in the stock `Virtual Families 2.exe` (found by matching
the desktop objects' code; the vanilla build is compiled differently, so the object offsets do not carry
over). Every row is VERIFIED from code, and real saves agree: in all nine of the owner's VF2 folders that have a settings file each in-use
slot-menu entry equals that slot save's gs+0x25ABC, and every empty slot holds `NEW PLAYER` (copies read only).

| What | Where | Evidence |
|---|---|---|
| Typed | new-player box, prompt `Please enter your name...` (string 0xA32 at 0x4FB84C) | `theCreateNickNameDlg` ctor `SetCanEdit(1, 0x14)` at 0x41F92A; `theChangePlayerDlg` ctor at 0x41EE0C (one box per slot) |
| Box limit | 20 keys | `ldwTextControl::SetCanEdit` 0x40DE40 stores the limit (`+0x28`, capped at 0x4B0) at 0x40DE95; `HandleKey` 0x40E540 refuses a key once the length reaches it (0x40E5D3) |
| Keys | 0x20..0xFF | `HandleKey` 0x40E5DF..0x40E5EA (non-numeric box); Backspace 0x40E59F, Enter/Tab end the edit 0x40E5C9..0x40E5D1 |
| Stored | gs+0x25ABC, 20 bytes, **at most 19 characters** | `ldwTextControl::GetText` 0x40E210: `strncpy(buf, text, n)` then `buf[n-1] = 0` (0x40E22B); called with n = 0x14 at 0x41F9D2..0x41F9DB (first player) and 0x41F471..0x41F47B (Change Player, NEW PLAYER box) |
| Slot menu | settings file `Virtual Families 20.ldw`, gs+0x25B30 + 0x15 x (N-1) | the OK handlers copy the name there (0x41F9E0..0x41F9FA, 0x41F480..0x41F49C); `theGameState::Load` 0x42A2E0 loads every slot at start and copies each save's gs+0x25ABC into its entry (0x42A3BD..0x42A4EE), or `NEW PLAYER` (0xA34) when the save does not load |
| Shown | main menu `Player: ` (0xA31) + gs+0x25ABC | `theMenuScene::UpdateShowPlayer` 0x443B80 (0x443BAC); Change Player lists the entries (0x41EDE6); the daily email greets the player with it (0x417B40) |
| Empty name | refused | Change Player puts `NEW PLAYER` back into an emptied box |
| `NEW PLAYER` | means an empty slot | Change Player compares the box with string 0xA34 (0x41F315..0x41F359) and treats a match as a new slot |
| In-game rename | none | clicking an existing player only switches to it (0x41F370..0x41F396) |

UNCONFIRMED (not traced): whether keys 0x80..0xFF reach the box from a keyboard, and which of them the
game's font draws. Rename Family therefore accepts only printable ASCII 0x20..0x7E, 1 to 19 characters, not
only spaces and never exactly `NEW PLAYER`; a longer name is refused, never cut. It writes the slot save's
gs+0x25ABC, the slot's entry in the settings file, and the previous save N+20 only when it still holds the
old name, after a `Backup <date> (before rename)`.
