# Virtual Families 2 (B200 Restoration line): "Game Mechanics" window spec (read-only research), v1

Target: the B200 **core** executable `outputs/VF2-B200-matrix-core/Virtual Families 2 - B200.exe` (built by the matrix build)
(analysed from a copy). Every address below is in that file. The patcher's
post-install flag bytes are all 0 in it (`.vf2beh`, `.vf2goal`, `.vf2preg`, `.vf2mort`, `.vf2bugs`, `.vf2scrl`);
where a patcher option flips one of them the rule is given for both states. The unpatched game (the stock
executable) was compared routine by routine in section 22; where it differs, both are given.
Names come from the desktop object files the patcher relinks (`work/desktop_obj_files`), mapped
onto the exe by `coffmap.py` (masked byte match of every function, 2,867 functions placed).

## Evidence labels

- **VERIFIED-E**: the routine was run as linked, inside unicorn (`emu.py`), with game-supplied inputs, and the
  odds counted over every raw `rand()` value. The game's rand is the MSVC LCG; over its full period every 15-bit
  value 0..32767 appears equally often, so counting raw values gives the game's own odds exactly.
- **VERIFIED-C**: the routine sits on a traced call path (below) and the rule is the instruction sequence itself
  (constants, compares, one roll); odds are then the exact count over the 32,768 raw values.
- **UNCONFIRMED**: not on a traced path, reached only from player input that was not traced, or a meaning the
  code does not show. Stated as such.
- Never inferred from save values alone. No design choice is called a bug.

`GetRandom(N)` (0x4757C0) = `rand() % N` for N <= 32,767; for larger N it is `rand()/32767 * (N-1)` truncated
(only 32,768 distinct results). Odds below are exact over the game's rand, so e.g. "rand(100) < 30" is 30.03%,
not 30%; the plain fraction is given where the difference is under 0.1 point.

## 0. Reachability (traced)

- Frame loop: `ldwGame::Run` 0x4754B0 calls the game's vtable +0x1C = `theGame::GameUpdate` 0x497AF0, which calls
  `theMainScene::Get` and the scene's `ldwScene::Update` (vtable +0x10, 0x47EEC0), which calls vtable +0x20 =
  `theMainScene::UpdateScene` 0x4A2590 while the house screen is active. **Frame cap 30 fps**:
  `theGameState` vtable +0x28 (0x4757B0) returns 30, passed to `ldwGameWindow::SetFrameRate`; the window update
  delays to 1000/30 ms per frame. Per-frame rolls therefore run at most 30 times a real second.
- Inside `UpdateScene`:
  - **2-second step** (0x4A266E..0x4A2AB1): `ldwEventManager::GetSeconds() >= next` then next = now + 2. Runs
    `CFoodStore::Update` 0x464F70, `theRealtimeManager::UpdateAll` 0x4A7CF0 (->
    `CVillagerManager::AllVillagersTimeflowUpkeep(false)` 0x4C4C30 and
    `AllVillagersRealtimePhysiologyAndProductivityUpkeep` 0x4C4410), the college e-mail check, the service-worker
    timers and the house-malfunction roll. **This step reads no pause flag.**
  - Every frame: community event, e-mails, the marriage e-mail timer, the island-event timer, `CCollectableItem::Update`
    0x44DE90 (collectibles and messes), `CWeather::Update` 0x4CD110 (skipped while paused), furniture, birds, etc.
- Store purchases run `CScrollingStoreScene::HandleUpgrade` (player input; not traced through the UI dispatch,
  so purchase-only rules are marked where they matter).

## 1. Clock, speed, pause, time away

| Item | Rule | Real time | Save | Status |
|---|---|---|---|---|
| Speed option | gs+0x25B18. Stock code only ever writes **10** (new player, change player, unpause). Values 5 and 20 change the catch-up caps (below) but **nothing in B200 sets them**. | | file 0x25B20 | VERIFIED-C (every writer listed: theCreateNickNameDlg, theChangePlayerDlg, theOptionsDialog, theMainScene pause, store time-skip) |
| Pause | Pause adds 999 to the option and calls `CGameTime::SetSpeed(999)` (stored as speed 0). Unpause subtracts 999; a result of 0 becomes 10. Options dialog unpause writes 10. | | | VERIFIED-C (theMainScene handler 0x4A2xxx `$LN43`, theOptionsDialog) |
| Game seconds | `CGameTime::Seconds()` 0x468B00 = saved base + (real seconds since the last speed change) / (speed/10). At speed 10 one game second = one real second; paused = frozen. | 1 game s = 1 real s | CGameTime file 0x16404 | VERIFIED-E (2026-10-25: `SetSpeed(999)` 0x468B80 run as linked stores speed 0 and banks Seconds(); Seconds() then returns the banked 4,500 at real 5,000, 20,000 and 90,000; after `SetSpeed(10)` it carries on from 4,500) |
| Real seconds | `GetSecondsFromGameStart` = wall clock minus the save header's start time (header +4); **keeps running while the game is closed**. Used by aging, food groups, symptom expiry, collectible expiry, pregnancy cooldown. | | header 0x04 | VERIFIED-C |
| Age unit | `AllVillagersTimeflowUpkeep` adds real seconds since the villager's stamp (state+0x04) to an accumulator (state+0x00), ages by accumulator / 60 / option, keeps the remainder. | **1 unit = 10 real min; 1 year (20 units) = 3 h 20 min** on speed 10 | rec 0x0A8/0x0AC | VERIFIED-C |
| Catch-up cap | `AllVillagersTimeflowUpkeep` 0x4C4D29..0x4C4D8F: the accumulator gains the real seconds since the stamp. **Over 86,400 s it is set to 86,400 and the speed rule is skipped** (`jbe` at 0x4C4D39, `jmp 0x4C4D99` at 0x4C4D45). Otherwise, in the normal 2-second path (argument false), if it is over 31,000 (option 10 or any other), 38,200 (option 5) or 23,800 (option 20) it is set to **31,000**. Every test is "greater than". | at speed 10: up to 31,000 s away is credited in full; **31,000-86,400 s away credits 31,000 s (51 units, 2.55 years)**; **more than 86,400 s away credits 86,400 s (144 units, 7.2 years)** | | **VERIFIED-E** (2026-10-25): the B200 core exe's own `AllVillagersTimeflowUpkeep` run as linked in unicorn, one family member, speed option 10, argument false, accumulator credited at the `IncrementAge` call 0x4C4DEF: 30,000 s away -> 30,000 s (50 units); 50,000 -> 31,000 (51 units, 400 s kept); 86,400 -> 31,000 (51 units, 400 s kept); 200,000 -> 86,400 (144 units). With argument true (the catch-up call) only the 86,400 cap applies (50,000 -> 50,000). Option 1009 (paused) -> 0. Same result as VF1's emulation of its identical code (0x489DF5). *Superseded, wrong:* "capped at 86,400 s; then ... set to 31,000", i.e. at most 31,000 s (2.58 years) per catch-up, which missed the jump past the speed rule. |
| While paused | option >= 999 zeroes the accumulator every step: **no aging, nothing processed, and paused time is never credited later**. Game-second timers freeze. Real-second timers (food groups, symptoms, pregnancy cooldown, collectible expiry) keep running. | | | VERIFIED-C |
| Closed game | Time away is credited on the next run through the same accumulator (capped as above). Each crossed unit is then processed one by one (section 2). | 2.55 years for 31,000-86,400 s away, 7.2 years for more than 86,400 s (*superseded, wrong:* "max 2.58 years") | | VERIFIED-C (cap: VERIFIED-E above) |
| Store "time skip" (item 0x112) | Unpauses, moves the start time back by 3,660 x option s (36,600 s at 10), runs food store + timeflow(catch-up=true) + upkeep, then caps the money gain at **+750**. | one use = up to 61 units | | UNCONFIRMED (purchase path) |
| Day / night | `CNight::GetTimeOfDay` 0x482A30 = **the PC's local clock** (hour + min/60) + CNight+0x860, +12 h when gs+0x25B1C is set, wrapped to 0..24. | follows the real clock | | VERIFIED-C |

## 2. Per-unit villager upkeep (the core of every need)

`AllVillagersRealtimePhysiologyAndProductivityUpkeep` 0x4C4410, from the 2-second step. For every active, at-home
villager with health > 0, it processes each age unit n from state+0x08 ("processed age") up to the current age,
one at a time, repeating until nobody is behind. So all rules below run **once per unit (10 real minutes)**, and a
catch-up replays every crossed unit (up to 144; section 1; *superseded, wrong:* "up to 51"). Status VERIFIED-E (`t_phys.py` runs this function as linked).

| Every | Rule | Address |
|---|---|---|
| 4 units (40 min) | Hunger +5 (`UpdateHungerState`) | 0x4CC6A0 |
| 3 units (30 min) | Health state, happiness state, disease (below) | 0x4C44E0 |
| every 2nd unit, skipped for units more than 12 behind (so a catch-up only does its last 12) | Energy state (below) | 0x4C450F |
| 3 units | **Salary**: money + salary x 6 / 24 (= salary/4) | 0x4C452E |
| unit | Poo (state+0x48) >= 90: set to 25 + rand(25) (the toilet trip itself is a behaviour) | 0x4C455A |
| unit | **Eating**: if food > 0 and (food > 50, or rand(100) < 50): when hunger > 50, food -3 and hunger -3. Otherwise (no food, or the 50% miss below 51 food): 30.03% chance health -1 (cause 1). Food Club owned and food < 60: +60 food first. | 0x4C4575 |
| unit | **Waste**: food >= 1,000 and hunger > 50: 76% chance of 3 more food used | 0x4C460F |
| unit | **No food** (food <= 0): health -1 (cause 1) with 76% + 24% on units divisible by 6; then at health <= 20 on odd units a 31% chance of +1 | 0x4C463C |
| unit | **Sick**: 61% chance of health -1 (cause 0); at health <= 20 that also needs a 31% roll | 0x4C46D0 |
| unit | **Recovery** (food > 0, not sick): 50% chance of +1 health, but at age 55+ (`IsOld`, age >= 1,100) only 50% x 20% = 10%; capped at 100 | 0x4C470A |
| birthday unit (n % 20 = 0) | **Old age** (section 4) | 0x4C476C |
| unit | **Birth** when pregnant (section 6) | 0x4C47D8 |
| unit, catch-up only (more than 2 units behind), adult with a career, not sick, not pregnant | `RealtimeWorkDone` (career credit for time not watched, section 7) | 0x4C4A8F |
| unit | Age 700/900/1000/1200/1300 units (35/45/50/60/65 years) advance the longevity goals 0x55..0x59 | 0x4C4B19 |

Hunger(+0x40), happiness(+0x38), energy(+0x34), poo(+0x48) live in CVillagerState (record +0x0A8; so record
offsets +0x0DC energy, +0x0E0 happiness, +0x0E4 trend, +0x0E8 hunger, +0x0EC dirtiness, +0x0F0 poo,
+0x0F4 fertility, +0x0F8 procreation desire; health +0x0B4, cause +0x0B8).

### Health state (every 3 units, `UpdateHealthState` 0x4CC5F0) VERIFIED-C
Delta = 0, then -1 if happiness <= 10, -1 if hunger >= 90, another -1 if hunger >= 100, -1 if exactly 1 food group
is active, +1 if exactly 4 are active; if sick: -1 with 15% (symptoms only) or 40% (with an infection). Clamped to
-5..+5 and applied (cause "unknown").

### Energy (`UpdateEnergyState` 0x4CBDC0) VERIFIED-C
Delta: -4 if energy >= 10 and clock >= 20:00 or < 05:00; +8 if energy <= 70 and the clock is 05:06..17:00
(PC local time); -1 each for happiness <= 10, health <= 25, health <= 10, hunger >= 90; -3 if sick; clamped
-6..+10. Every second unit, skipped for units more than 12 behind real time.

### Happiness (every 3 units, `UpdateHappinessState` 0x4CBE90) VERIFIED-C
A trend (state+0x3C) collects: happiness < 25: +100 / > 85: -100; food groups 10N-20; money < 1,000: -30,
< 100: another -75, > 8,000: +35, > 50,000: +25, > 100,000: +15; food <= 250: -100, <= 50: another -100;
sick -150; messes on the floor (socks + weeds + wrappers + smudges): 0 -> +50, 1-4 -> +25, >= 10 -> -40 and
>= 20 -> -40 (thresholds halve for a villager who dislikes mess, like 0x4A); +5 per owned house renovation
0xE1..0xEA; +1 per placed furniture item (max 30); like-specific bonuses for owned items (+3..+35);
tech-level bonuses for liked rooms; the head couple's career level x 10 (others 50); population 1: -75,
else 40 x population - 60; a couple term from the spouses' procreation desires; hunger >= 90: -100;
health <= 10: -100. Then happiness += clamp(trend/100, -5, 5) (halved near the ends; -2 when food <= 5 or sick
with a positive trend) and the trend is halved.

### Food groups (nutrition)
Four groups (Grains, Dairy, Meat and a fourth; string 0x39C.. "Groceries: ..."). Putting a grocery bag in the
kitchen (or a Food Club delivery) sets the group active for every villager at home until **real time + 86,400 s
(24 real hours)** (`UpdateNutritionAllVillagers` 0x4C74E0; organics also add happiness trend +5..+14 and
happiness +0..2). `FoodGroupsActive` 0x4CB870 counts **five** slots: the fifth reads the low byte of group 1's
expiry time as its flag and the dword after the four expiries (the career id) as its expiry, so a villager with
no career (-1) and an active first group counts one extra group. Emulated (`t_life.py`): a careerless villager
with N >= 1 groups is treated as N+1. VERIFIED-E. (Code as built; see Open questions.)

**Re-verified 2026-10-25 (VERIFIED-E, `FoodGroupsActive` 0x4CB870 and the physiology upkeep run as linked):** the
first slot is **Grains** (item 4 "Groceries: Grains", string 0x39C, and item 8 "Organics: Grains" both call
`UpdateNutritionAllVillagers(0, ...)` from `theMainScene::HandleMouseDown` 0x49F9A1 / 0x49F9EF). The extra group
needs the **Grains** expiry's low byte to be non-zero, not "any group": careerless with Grains only counts 2,
with Dairy only 1, with all four 5; careerless whose Grains **ran out** (stale expiry) and no group active
still counts **1**; a Grains expiry ending in byte 0 (1 time in 256) gives no extra. For a family member with a
career the fifth pass writes 0 into that low byte (Grains then lasts up to 255 s less). Through the real upkeep
(site 0x4C47A8): careerless with N groups dies on the N+1 schedule (e.g. 2 groups: 0% at 58, 20% at 60, as an
employed member with 3), and through `UpdateDisease` 0x4CBD29 the base chance is 10 / 1000 with 3 groups
(counted 4, so no -2) and 5 / 1000 with 4 (counted 5). The same count feeds `UpdateHealthState` 0x4CC616 and
`UpdateHappinessState` 0x4CBF00. *Superseded, imprecise:* "a careerless villager with N >= 1 groups is treated
as N+1".

## 3. Sickness and symptoms (every 3 units, `UpdateDisease` 0x4CBBE0) VERIFIED-E

Seven symptoms (state+0x5C..0x62; record +0x104..0x10A), names from the diagnosis dialog's mapping:
0 Hiccups, 1 Sore throat, 2 Stomach, 3 Headache, 4 Cough, 5 Skin rash, 6 Runny nose.
Two infections: mild (state+0x80, "penicillin") and serious (state+0x81, "vancomycin").

- Healthy villager (no symptom, no infection), per check: rand(1000) < base, base 10, **25 if anyone at home has
  a contagious symptom**, -2 with exactly 3 food groups, -5 with a count of 5. If hit: rand(100) < 3 serious
  infection, < 10 mild infection, else one symptom (the housemate's contagious one if any, else random of 7).
  Exact per-check odds (`t_dis.py`): employed, 0 or 4 groups: symptom 0.906%, mild 0.071%, serious 0.030%
  (total 1.007%); 3 groups: 0.725/0.057/0.024%; careerless with 4 groups (counted as 5): 0.453/0.035/0.015%;
  contagious housemate: 2.266/0.176/0.076%. Every 30 real minutes on speed 10.
- Each symptom lasts until **real time + (6..17) hours** (`SetSymptom` 0x4CBBA0: (rand(12)+6) x 3,600 s); a
  symptom-only villager loses its first symptom when that time passes.
- Mild infection: each check 50% chance to add a symptom when it has none; ends with rand(100) < 3 (3%).
- Serious infection: each check 50% chance to add a new symptom while it has fewer than 2; ends with
  rand(250) < 3 (1.2%).
- Effects of being sick: section 2 (61% health loss per unit, no recovery, happiness -150 trend, energy -3,
  career credit / 8, health-state roll).
- Medicines and the stethoscope (store items Meds1..10) are player actions: UNCONFIRMED here.

## 4. Death

| Cause | Rule | Status |
|---|---|---|
| Old age (stock, `.vf2mort` = 0) | On each birthday unit, with N = food groups counted: if years > 55 + N, death chance = 10% x (years - 55 - N). N = 0: 10% at 56 ... 100% at 65; N = 4: 10% at 60 ... 100% at 69; N = 5 (a careerless villager with all four, section 2): 10% at 61 ... 100% at 70. SetHealth(0, cause 2). *Superseded, wrong:* "N = 4: 10% at 61 ... 100% at 70" (that run's villager had no career, so 4 groups counted 5; re-run 2026-10-25 with a career: 60 / 64 / 69 give 10 / 50 / 100%). | VERIFIED-E (`t_life.py`, every residue; tests/test_game_mechanics_b200_exe.py) |
| Old age (Older Villager Mortality option, `.vf2mort` = 1) | Same birthday check, `VF2RollOlderVillagerMortality` 0x4BA410: effective age = years - N (N clamped 0..4); death if GetRandom(1,000,000) < table[effective age]. Emulated per-birthday odds (N=0): 55: 0%, 60: 1.81%, 65: 3.59%, 70: 5.33%, 75: 7.04%, 80: 8.72%, 90: 11.99%, 100: 15.15%, 110: 18.19%, 115: 40.49%, 120: 56.71%, 125: 68.51%, 150: 93.59%, 200: 99.73%. No age cap. | VERIFIED-E |
| Disease | Health reaches 0 through the sickness loss (cause 0) | VERIFIED-C |
| Starvation | Health reaches 0 through the eating / no-food losses (cause 1) | VERIFIED-C |
| Work accident, Act of Nature | Cause ids exist (strings 0x87F, 0x880); their sources are island events / behaviours, not traced here | settled in section 24 |
| Removal | A dead villager stays active until **240 units (40 real hours)** after its last upkeep stamp, then `ReportDeath` removes it from the tree slot (`AllVillagersTimeflowUpkeep` 0x4C4C9D) | VERIFIED-C |

Cause names (string 0x87B + id): -1 Unknown, 0 Disease, 1 Starvation, 2 Old age, 3 Work accident, 4 Act of Nature;
ids 0-2 match the call sites above, 3-4 settled in section 24. Save: record +0x0B4 health, +0x0B8 cause.

## 5. Aging and life stages

| Stage | Age units (years) | Source | Status |
|---|---|---|---|
| Baby (diaper events) | < 100 (5) | Binky / Diaper Rash / Out Of Diapers CanFire | VERIFIED-C |
| Child | < 280 (14) | AdultPopulation, GetRandomVillager | VERIFIED-C |
| Teen / adult for most checks | >= 280 (14) | same | VERIFIED-C |
| No career assigned at creation | < 340 (17) | `CVillager::Init` | VERIFIED-C |
| Mating / mother caring | >= 360 (18) and < 1,100 (55) | SelectOtherAvailableMatingVillager | VERIFIED-C |
| College | crossing 380 (19) with no career | section 9 | VERIFIED-C |
| Old (`IsOld`) | >= 1,100 (55) | 0x4C4080 area | VERIFIED-C |
| Maximum age | none in code; old age makes 65 + N the stock limit | | VERIFIED-E |

New babies are created with age 40 units (`Impregnate` passes 0x28 to the spawner); oldest-age statistic
GameStats+0x20 (file 0x163E8) is updated in years. Real time per year: 3 h 20 min on speed 10.

## 6. Pregnancy and birth

- **Who**: only the family's Matriarch (married woman) with the Patriarch: `CVillagerPlans::ProcessCurrentPlan`
  case 73 calls `ChanceOfPregnancy(motherAge, fatherAge, fatherFertility)` on the mother's state, then
  `Impregnate`. Also `theMainScene::TryToMakeBaby` (drop) and `ConceiveChildWith`. VERIFIED-C (call sites).
- **Conception odds** `ChanceOfPregnancy` 0x4CB6C0 (VERIFIED-E, `t_preg.py`, father 30, both fertility F):

| Mother age | F 0 | F 25 | F 50 | F 75 | F 100 |
|---|---|---|---|---|---|
| 18-30 | 39.0% | 55.1% | 73.1% | 89.0% | 100% |
| 31 | 17.0% | 33.0% | 51.1% | 67.1% | 83.0% |
| 35 | 9.0% | 25.0% | 43.0% | 59.1% | 75.1% |
| 40 | 0% | 15.0% | 33.0% | 49.1% | 65.1% |
| 45 | 0% | 5.0% | 23.0% | 39.0% | 55.1% |
| 50 | 0% | 0% | 13.0% | 29.0% | 45.0% |
| 51+ | 0% | 0% | 0% | 0% | 0% |

  Formula: 105 - (100 - motherFert)/3 - (100 - fatherFert)/3; fathers 41+ lose (years-40)/5; mothers 31-50 lose
  2 x (years-20); mothers over 50 get 0. **The very first try while tip 0x868 has not been shown always succeeds
  (mother under 50).** Allow Older Pregnancies (`.vf2preg` = 1, a parent 50+) replaces this with
  `VF2RollOlderPregnancy` (patcher table, 10.0% at 50 down to 0.1% from 69; per discoveries.md, settled in section 24 here).
- **Twins / triplets** (`Impregnate` 0x4BB920, VERIFIED-C): bonus = (motherFert - 85 if > 85) + (fatherFert - 85
  if > 85). Twins if rand(100) < 7 + bonus and at least 2 free child slots; then triplets if rand(100) < 25 + bonus
  and 3 free slots. Base: single 93%, twins 5.25%, triplets 1.75%. Needs at least 1 free child slot (6 per
  generation). The patcher's forced-count one-shot (`VF2ApplyForcedBirthCount`) overrides when armed.
- **Length**: birth on the unit after conception age + 20, i.e. **21 units = 3 h 30 min** on speed 10
  (upkeep 0x4C47D8). Babies are spawned inactive at conception (gs+0x25AB0/4/8) and activated at birth.
- **Next try cooldown**: at a birth processed live (not catch-up), gs+0x25AE0 = real time + 600 x (5 - motherDesire/20)
  x (5 - fatherDesire/20) s (desire = state+0x50, 1..99): 4 h 10 min at desire 0, 10 min at desire 80+.
  Where gs+0x25AE0 is read: only `theMainScene::HandleDropOnVillager` (0x49E726 / 0x49E778): a spouse dropped on a
  spouse while it runs shakes their head ("It is too soon to try to make a baby again."), and a wait of more than
  1 hour is cut to now + 3,300 s (0x49E78E). VERIFIED-C.
- Save: record +0x0CC pregnant stamp, +0x0D0 babies expected; GameStats+0x08 babies born.

## 7. Careers and salary

- **Assignment** `CVillagerSkills::Reset` 0x4CB410: career = rand(132) (ids 0-37 kitchen, 38-94 office, 95-131
  workshop), level 0, salary from the table. 132 careers with names and the 8 level salaries:
  `careers.tsv` (from `careers.py`). Levels: Beginner, Novice, Apprentice, Licensed, Practiced, Accomplished,
  Exceptional, Master. VERIFIED-C.
- **Work** (behaviours OfficeCarreerWork / WorkKitchen0 / WorkWorkshop): success if rand(160) < 10 x (level + 9)
  (56.25% at Beginner ... 100% at Master); always success before tip 0x858 is shown.
  Success -> `AdvanceCareer(pay)`: money + salary x 0.06, progress + (4 x roomTech + 20) / (level+1) times 7 / 3 /
  2 / 1 for levels 0 / 1 / 2 / 3-6 (none at 7). Progress 3,000 = promotion: level + 1, new salary, progress 0,
  life event 3, everyone celebrates. VERIFIED-C (behaviour entry from the AI: settled in section 24 frequency).
- **Unwatched work** `RealtimeWorkDone` 0x4C3DB0 (catch-up units only): count = AI value 71 / 44 / 75 (by career
  type) / 400 (0 if pregnant, / 8 if sick); each count has a 1-in-6 chance of an unpaid `AdvanceCareer`.
- **Salary** paid every 3 units: salary / 4 (section 2) = **salary / 2 per real hour** on speed 10, whether or not
  the villager is at work. VERIFIED-E.
- Save: record +0x140 career id, +0x144 level, +0x148 progress, +0x14C salary.

## 8. Money, interest and the four Special Upgrades

| Item | Rule | Save | Status |
|---|---|---|---|
| Balance | double; floor 0, ceiling 4,000,000,000 (`CMoney::Adjust` 0x4818B0) | file 0x168BC | VERIFIED-C |
| Interest | `UpdateInterest` 0x481D80: whole game days (86,400 game s) since the last payment; pays balance x rate x min(days, 2); the date advances by all elapsed days. **At most 2 days are paid after any gap.** Called from the happiness state (every 30 min) and elsewhere. | CMoney+0x0C at file 0x168C4 | VERIFIED-C |
| Rate | default **0.10 per game day** (`Reset` writes 0x3DCCCCCD); saved as percent x 100 in the low 16 bits | file 0x168C0 | VERIFIED-C |
| Special Upgrades page (category 0x14) | B200 core: 10 items, `gServicesList` 0x56F100 = 0x111, 0x112, 0x113, 0x115, 0x116, 0x114 and the patcher's always-on rows 0x117..0x11A (Brokerage Account, Food Club, Health Plan, Lucky Rock). **Unpatched game: 6 items** (0x111, 0x112, 0x113, 0x115, 0x116, 0x114), none of the four (section 22). | | VERIFIED-E both (2026-10-25: `GetCategoryItemCount` / `GetCategoryItem` run as linked in each exe) |
| Brokerage Account (0x117, patcher-visible) | not owned (rate <= 0.1001): rate + 0.02, capped 0.11 -> **11%**. Buying it again removes it: rate = **0.01** (1%) | rate field | VERIFIED-E (2026-10-25: `CScrollingStoreScene::HandlePurchaseItem` 0x48C110, from `HandleMouse` 0x48BAEE / 0x48BC78, charges `CalcPrice` then calls 0x4B8B50 for items 0x117..0x11A; run as linked from 0.10, seven purchases give 0.11, 0.01, 0.03, 0.05, 0.07, 0.09, 0.11: after the 1% each purchase adds 2 points until 11% again). `UpdateInterest` run as linked, balance 1,000 at 0.10: 1 day +100.005, 2 days +200.005, 3 or 10 days +200.005 with the date moved by all of them. |
| Food Club (0x118) | `JoinFoodClub`: active byte FoodStore+0x7C, delivery now; `CFoodStore::Update` delivers 500 food x whole game days missed (no cap) and refreshes all 4 food groups; also +60 food whenever a villager finds food < 60. Removing clears the flag. | FoodStore file 0xE3BC.. | VERIFIED-C |
| Health Plan (0x119) | gs+0x25B1D; stock `GetPrice` divides items 0x18..0x21 (medicine) by 4; ownership stored by the patcher in hidden achievement record 0xA8+0x08 bit 0 | | UNCONFIRMED (price path is player input) |
| Lucky Rock (0x11A) | CCollectableItem+0x8A8: collectible spawn roll rand(3,300) < 3 instead of rand(6,600) < 3 per frame (section 15) | | VERIFIED-C |
| Lotto Ticket (0x114, stock) | rand(10000): 0 -> 50,000; 1-2 -> 25,000; 3-22 -> 5,000; 23-222 -> 1,000; 223-722 -> 750; 723-4055 -> 50% a grocery bag if a tray slot is free; else nothing | | UNCONFIRMED (purchase path; from discoveries.md, matches HandleUpgrade `$LN50`) |

## 9. Leaving home: College, Boarding School, Talent Scout

| Route | Rule | Status |
|---|---|---|
| College | `AllVillagersTimeflowUpkeep` 0x4C4DF4: when a villager's age crosses **380 units (19 years)** and `CareerType` is 0 (no career), plans are dropped, `SetLeftHome` (record +0x001 = 1, +0x004 = game seconds), life event 5, college e-mail timer. Children born in the house have no career (`CVillager::Init` gives none below 340 units), so every child not made heir leaves at 19. | VERIFIED-C |
| Boarding School | Store row (`HandleUpgrade` path at +0x727): `SetLeftHome` on the chosen child, message 0x4C8 "%s has been sent away to school!". | UNCONFIRMED (purchase path) |
| Talent Scout (event 83) | Child-only event (selector 1). Choice A: the child `SetLeftHome` and the family gets **$500** (award fixed 0x1F4). Choice B: nothing. | VERIFIED-E |
| Time away | `YearsAwayFromHome` = (game s now - leave stamp) / 12,000. College-kid e-mails pick from villagers >= 380 units who left (`GetRandomCollegeKid`). | VERIFIED-C |

The save does not say which route was taken (record +0x001 only).

## 10. Dating, marriage, adoption, next generation

| Item | Rule | Status |
|---|---|---|
| Marriage e-mail timer | gs+0x25AE4 (game s). Set to **now + 180 s** at a new game and at a new generation; after a dating visit ends without a match, now + 300 s x visits (gs+0x25AE8) + 600 s per year the single head is over 26. When due, with exactly one adult, a current family record that `CanMarry`: e-mail 2 (the dating scene). | VERIFIED-C (writers in theGameState, CAdoptionScene, CDatingScene, theMainScene 0x4A2D94) |
| Dating candidate | `CDatingScene::GeneratePeepCandidate` 0x452D80: age = head's age + 20 x (rand(6) - 3) units (**-3..+2 years**, uniform), **opposite gender** in the core build (the same-sex branch is a NOP'd jump; the cave still reads the Same-Sex Marriage flag byte at 0x6856AF but its jump was NOP'd). Career etc. from `SpawnSpecificPeep`. | VERIFIED-C |
| Marriage | Accepting runs `CFamilyTree::UpdateParents` (spouse = record parent 2, file 0x1848+4+0xDC), life event 1. | VERIFIED-C (call site) |
| Founder adoption | `CAdoptionScene::GeneratePeepCandidate` 0x403660: gender rand(2), age 20 x (24 + rand(6)) units (**24-29 years**). New game money: $50 + rand(140) ($50-189) in `theGameState` init. | VERIFIED-C |
| Next generation | `CFamilyTree::ReportDeath` sets "can start next generation" when a parent of children dies while a child survives. The house screen shows the notice (`NeedNextGenerationNotify`, scene 8); choosing an heir runs `StartNextGeneration` and **deactivates every other villager**, then `ResetForNextGeneration`. Allow Older Pregnancies (`.vf2preg` = 1) also allows it when the oldest living villager reaches 60 with a surviving child (`VF2CanStartNextGenerationAtOlderAge`). | VERIFIED-C (code path), UNCONFIRMED (heir choice is player input) |
| Child limit | 6 per generation (`AddOffspring` refuses at 6; `EmptyOffspringSlots`). | VERIFIED-C |
| Little Visitor (events 64 / 65) | Needs anyone at home and a free child slot. Choice A: a **3-year-old (60 units) boy (64) / girl (65)** joins and is added to the tree; Choice B: nothing. | VERIFIED-E |
| Adoption Day (56) | Everyone celebrates (behaviour 0x64); no family change. | VERIFIED-E |

## 11. Island events

**Timing** (`theMainScene::UpdateScene` 0x4A2E17, VERIFIED-C): when game seconds >= gs+0x25ADC and anyone is at
home, a random living villager is drawn; if that villager is fully caught up (age = processed age) and no event
e-mail is queued: **66%** queue an e-mail event, **34%** fire a pop-up event now; either way the next check is
**now + 3,600 game s (1 real hour on speed 10; frozen while paused)**. Opening the e-mail resets the timer to now +
3,600 and fires an e-mail event. Selection (`CIslandEvents::FireEvent` 0x46F330): uniform among the registered
events whose `CanFire` is true and whose e-mail flag matches. Not saved (island state lives outside the save).
Store item 0x111 fires one immediately (purchase path).

**Registered events in the core build** (96, `events_registry.tsv`). Effects below are from running each event's
`CalcAward` and `ImpactGame` as linked (`t_events.py`, `events_emulated.txt`); the first roll is enumerated
exactly; where an event rolls again per villager, that second roll is marked. Money: + gain, - cost.

| # | Event | Kind | Needs | Effect |
|---|---|---|---|---|
| 1 | A Secret Admirer | e-mail | living alone | none |
| 2-4, 6-9 | I Ate Soup / I am on a BOAT / So Many Babies / Status-Single / I Lost My Pants / Boring / Likes | e-mail | a teen or adult | flavour; trend -10 (3, 4), +10 (6, 7), energy -20 (8) |
| 5 | Oh So Clever | e-mail | money check | trend -10; 15% stomach symptom |
| 10 / 11 | Electric Bill Correction | e-mail | | -$ / +$ (5..24, uniform) |
| 12, 20-23 | Spam (Funny, Bigger Brain, Nigerian Lottery, Car Insurance, What's What) | e-mail | **no Anti-Spam Software (item 0x33)** | none (12: $0) |
| 13 | Professional Association Fee | e-mail | | -$5 / 8 / 11 |
| 14 | Professional Association Rebate | e-mail | a working villager | +$5..32 (step 3) |
| 15 | Professional Network | e-mail | a working villager | 20 unpaid career advances |
| 16 | Professional Association Award | e-mail | | forced promotion (progress set to 3,001) |
| 17 | Infringement Complaint | e-mail | money check, 50% | none |
| 18 / 19 | Tax Audit (fee / gift) | e-mail | 18: money check, 50% | -$40..114 / +$500 |
| 24-26 | Old Friend (good / bad / angry) | e-mail | | none |
| 27 | Oh! A collectible! | e-mail | | a collectible spawns |
| 28 | My Weather Machine | e-mail | weather Normal or Sunny | weather set to Raining / Snowing / Foggy, 1/3 each |
| 29 | An extra hammock | e-mail | (false in the test house) | everyone runs to the yard |
| 30-32, 34-36 | Birthday present, Preferred Customer, Craft Fair, Rebate (accept), Helpful Child, Bad Cookies | e-mail | 34 needs furniture 0x1F3 | +$10..50 / +$5..79 / +$35..45 / +$50 / +$5..54 / -$5..100 |
| 37, 38, 41, 43 | Office Collection x2, Overdue Book, Bake Sale | e-mail | | -$4..40 / -$5..50 / -$5..50 / -$6..60 |
| 39 | Best Landscape Award | e-mail | 5 weeds or fewer | +$10 x (6 - weeds) |
| 40, 42 | Kite Contest, Hot Dog Contest | e-mail | 42: anyone | +$8..80 / +$5..50 |
| 44 | Neighborhood Children's Association | pop-up | a child, money check | -$10 per child |
| 45-51 | Angry Note, Sad Note, Room Specification, RSVP, Funeral Book, Adoption Response, The Deed | pop-up | | none |
| 52, 53 | Earthquake, Aesthetic Society | pop-up | 53: weeds > 0, money check | none / -$5 per weed |
| 54 | Birdwatcher Society | pop-up | | +$25 / 50 / 75 / 100 |
| 55 | Allergy Season | pop-up | | 3 random villagers get a runny nose |
| 57, 58 | TV Night, BBQ Party | pop-up | a TV / a grill | everyone does the activity |
| 59 | The Broken Window | pop-up | | +$1..30 (rand(30)+1) |
| 60, 61 | Photo Contest, Community Association | pop-up | 60: 2+ people | +$25..125 / -$20..100 |
| 62, 63 | Blowing Trash, Free Lawn Service | pop-up | | 5..12 trash items in the house / 5..12 weeds in the yard |
| 66 | EPA Visit | pop-up | anyone, can afford 3/4 of item 0xE4, not owned | A: pay 3/4 of 0xE4's price and get it built; B: 75% everyone at home gets a skin rash (`GiveAllVillagersSymptom(5, 75)`) |
| 67 | Chemical Manifest | pop-up | | A: pay item 0x1C's price, get 0x1C, then the 75% skin-rash roll; B: the 75% skin-rash roll |
| 68 | Boy Selling Cupcakes | pop-up | | A: -$10, 50% stomach symptom; B: -$45 |
| 69 | Girl Selling Magazines | pop-up | a free tray slot | A: -$20 and one of items 0x34 / 0x35 / 0x36 (1/3 each); B: none |
| 70, 72, 73 | Ran Out Of Diapers, Diaper Rash, Lost Binky | pop-up | a baby (age <= 100 units) | 70 A: -$60; 72 A: pay item 0x1C, B: everyone energy -10; 73 A: everyone happiness +15 |
| 71 | Bug Whisperer | pop-up | | A: -$75, two random bug collectibles (0x4F + rand(12)); B: none |
| 74 | Collecting Contest | pop-up | | A: +$10 with < 10 collectibles, +$50 with 10-20, +$100 with 21+ |
| 75 | Adult-proof | pop-up | 2+ children | A: -$50 |
| 76-78 | Small Package / Medium Brown Box / Sealed Green Bag | pop-up | a free tray slot (false in the test house) | A: an item 0x18+rand(6) / 4+rand(4) / 8+rand(4) |
| 79 | A Tiny White Box | pop-up | | A: food x 2/3 kept (lose 1/3) |
| 80 | Scratch-Off Lottery Ticket | pop-up | money check | A: -$20; 33% win $10 x rand(10) |
| 81 | The Wrong Address | pop-up | | A: -$100 and 50/50 furniture 0x1B5 or 0x1B4 (emulation stopped in the furniture call: settled in section 24) |
| 82 | The Delivery Truck | pop-up | | rand(100): < 33 item 0x21B, < 66 0x21A, else 0x219 (settled in section 24, same stop); B pays the award ($20 x rand(8)) |
| 83 | Talent Scout | pop-up | a child | A: child leaves, +$500 |
| 84 | Beauty Contest | pop-up | a child | A: -$10, 33% win $100 |
| 85-87 | Landscaping / Housekeeping / Total House Care | pop-up | | A: -$20 weeds removed / -$20 socks, wrappers, smudges removed / -$50 all |
| 88 | The Mysterious Collector | pop-up | (false in the test house) | sells collectibles (settled in section 24) |
| 89 | Water Pressure Surge | pop-up | | A: none; B: five leaks (props 0x1A, 0x1B, 0x1C, 0x1D, 0x1F) |
| 90 | Professional Career Training | pop-up | | A: -$250, forced promotion |
| 91 | The Trainer | pop-up | | A: -$5 and **all food lost** (food set to 0) |
| 92 | The Cooking Class | pop-up | | A: kitchen props 0x30, 0x0F, 0x0E, 0x22 (a cooking mess) |
| 93 | The Power Failure | pop-up | | power out (prop 0x17) either way; A "throw out": `CFoodStore::Reset(true)`; B "take a chance": rand(rand(4)) random villagers get a stomach symptom: 0 with 70.8%, 1 with 20.8%, 2 with 8.3% (the Add mobile-exclusive Island Events build replaces this, B200 notes) |
| 94 | Career Change Counselor | pop-up | | A: new random career at level 0 |
| 95 | The Rare Bird | pop-up | (false in the test house) | everyone runs to the yard |
| 96 | School Fund-raiser | pop-up | | A: -$25, +100 food |

"money check" = `UpdateInterest` then a balance compare; the thresholds are in `events_dump.txt` (settled in section 24
values). Exact per-event odds of firing = 1 / (number of eligible events of its kind) at each hourly check.

## 12. Weather (`CWeather`, Weather global 0xB4BA10, type at +0)

Types: 0 Normal, 1 Sunny (sun beams), 2 Raining, 3 Stormy (rain + lightning), 4 Foggy, 5 Snowing.

| Rule | Detail | Real time | Status |
|---|---|---|---|
| Change | `CWeather::Update` 0x4CD110 (every frame, skipped while paused): when game s >= end (+0x08): a non-Normal spell always returns to **Normal**; from Normal the next is uniform over Sunny/Raining/Stormy/Foggy/Snowing (**Sunny never starts at night**, rerolled) | | VERIFIED-C |
| Length | `SetCurrent` 0x4CCF20: Normal 900 + rand(1,500) s; any other 360 + rand(360) s | Normal **15-40 min**, others **6-12 min** on speed 10 | VERIFIED-C |
| Rain / storm effect | intensity +0x14 > 30: everyone outside switches to taking cover (behaviours 0x186, 0x2B, 0 -> 0x187) | | VERIFIED-C |
| Start weather | `CWeather::Reset` uses `Random`: the PC clock's minute mod 6, bumped by one if equal to the previous type or (types 4, 5) with 50% | | settled in section 24 (when Reset runs) |
| Rain items | collectible spawn areas whose base is 0x4F only spawn in Raining or Stormy weather | | VERIFIED-C |
| Weather Machine event | sets Raining, Snowing or Foggy (section 11) | | VERIFIED-E |

## 13. Messes and house malfunctions

| Item | Rule | Real time | Status |
|---|---|---|---|
| Mess spawn | `CCollectableItem::Update` 0x44DE90 (every frame, not while paused): every **300 game minutes** (population < 4) or **150** (4+), the elapsed count of mess items spawn in free slots: rand(100) < 30 weed (0x7D-0x80) unless Gardener (0x116), < 55 sock (0x73-0x78), < 80 candy wrapper (0x79-0x7C), else dirt smudge (0x83-0x85), the last three skipped with a Maid (0x115); with no cobwebs present a roll below 20 spawns nothing. Owning both Maid and Gardener spawns nothing. | every 5 h / 2.5 h on speed 10 | VERIFIED-C |
| Counts | socks +0x8AC, weeds +0x8B0, wrappers +0x8B4, smudges +0x8B8, cobwebs +0x8BC of CCollectableItem (0x5DF0A0): feed happiness (section 2) | | VERIFIED-C |
| House malfunction | 2-second step: rand(800) == 1 (**1 in 800 per 2 s, mean 26.7 real minutes**, any speed and **also while paused**), no malfunction active, at least 360 real s since the save's start: pick rand(14) (or rand(17) when gs+0x28 > 5): 0 prop 0x1A, 1 0x1C, 2 0x1D, 3 Router offline 0x17, 4 0x1F, 5 0x20, 6 0x1B, 7 dryer lint fire 0x21 (needs a dryer), 8-10 north shower / toilet / sink leaks 0x49 / 0x48 / 0x4A (need renovation 0xE6), 11-13 (and 14-16) ants 0x4D / 0x4E / 0x4F with 0x50 + 0x51. Each case is skipped while its permanent-fix flag (gs+0x8C..0x13C) is set. | | VERIFIED-C |
| Poo | state+0x48 >= 90 at a unit: reset to 25-49 | | VERIFIED-C |

Prop names other than Router / dryer fire / north leaks / ants: settled in section 24 (the patcher's Fix All list names
the 11 malfunction props 0x17, 0x1A-0x1D, 0x1F-0x21, 0x48-0x4A). The meaning of gs+0x28: settled in section 24.

## 14. Food

| Item | Rule | Save | Status |
|---|---|---|---|
| Store | `CFoodStore` food +0x78, never below 0, ceiling 2^31-1 | file 0xE3BC | VERIFIED-C |
| Eating / waste / starvation | section 2 | | VERIFIED-E |
| Food groups | 24 real hours per grocery type (section 2) | | VERIFIED-C |
| Food Club | 500 food per game day + all 4 groups; +60 top-up below 60 | | VERIFIED-C |
| Prices | Food Club description promises 50% off food; price code is the purchase path | | UNCONFIRMED |

## 15. Collectibles and the Lucky Rock

| Item | Rule | Real time | Status |
|---|---|---|---|
| Spawn | every frame while not paused: rand(6,600) < 3, or **rand(3,300) < 3 with Lucky Rock** -> `Add` | at 30 fps: mean **73 s**, Lucky Rock **37 s** | VERIFIED-C |
| Where / what | `Add` 0x44CA10: a random registered spawn area (rain-only areas need rain; areas based at 0x67 / 0x86 need item 0x10A), base + rand(4); rarity rand(100): **rare (+8) 4%, uncommon (+4) 13%, common 83%**; Lucky Rock: **8% / 26% / 66%**. Nothing spawns if that exact item is already out or carried. | | VERIFIED-C |
| Expiry | non-mess collectibles vanish when real time passes their expiry | | VERIFIED-C |

## 16. Flea Market and On Sale

| Item | Rule | Real time | Status |
|---|---|---|---|
| Flea Market | B200 lists **all 36 `gGoodiesList` items at all times; it never rotates.** `CInventoryManager::GetCategoryItemCount` 0x46B6D0 first calls the patcher's `VF2GetExpandedFleaMarketCount` 0x4B9A90, which returns 36 for category 15 (the Flea Market) unconditionally, and `GetCategoryItem` 0x46B210 likewise returns `gGoodiesList[i]` from `VF2GetExpandedFleaMarketItem` 0x4B9AB0. `MaybeUpdateRotatingItems` 0x46BEB0 has one caller, the category-15 case at 0x46B7A3, which is therefore never reached. | never changes (the in-game tips 0x873 / 0xA16 still say it changes 3 / several times a day) | VERIFIED-E (2026-10-25: count and items emulated at real s 100,000, +21,601 and +86,400: 36 each time, equal to `gGoodiesList`, the rotation never ran). *Superseded, wrong for B200:* "5 of the 36 shuffled in, next change now + 21,600 real s, every 6 real hours" (the stock code, now dead). **Unpatched game** (stock exe, section 22): 5 of the 36 shuffled in, picked again when the Flea Market is opened more than 21,600 real s after the last pick (real seconds since the family's start: they count while paused and while closed); VERIFIED-E (2026-10-25: from the store menu's Flea Market row, `SetStoreCategory(15)` 0x432050 -> `GetCategoryItemCount` 0x4BB0A0 -> `MaybeUpdateRotatingItems` 0x4BA710, run as linked after `Reset` 0x4BA8F0: 5 goods at T, the same 5 at T + 21,600, 5 new at T + 21,601 and at T + 86,400). |
| On Sale | `MaybeUpdateSaleItems` 0x46C000: every **86,400 game s**, 3 unlocked, non-pet furniture items 0x1AD..0x2A8 | every 24 real hours on speed 10 | VERIFIED-C (the discount is in the price code: UNCONFIRMED) |
| Renovations | the 10 house renovations 0xE1..0xEA each add +5 happiness trend every 30 min (section 2); 0xE6 enables the north-bathroom leaks | | VERIFIED-C |

## 17. Timers (every timer found on the traced paths)

Clock column: **R** = real seconds since the save's start (`GetSecondsFromGameStart`, runs while the game is closed
and while paused), **G** = game seconds (`CGameTime::Seconds`, frozen while paused; = real seconds on speed 10),
**F** = frames (30 per real second), **S** = the 2-second step (runs while paused).

| Timer | Field | Clock | Period / length | Real time on speed 10 | Status |
|---|---|---|---|---|---|
| Upkeep step | theMainScene+0x30 | S | 2 s | 2 s | VERIFIED-C |
| Age unit | state+0x00/+0x04 | R / speed | 60 x speed option real s (600 at Normal; units = seconds / 60 / gs+0x25B18, 0x4C4DCF..0x4C4DE3): game time, section 25 | 10 min (paused time discarded) | VERIFIED-C |
| Dead body removal | state+0x04 | R / speed | 240 units: (now - stamp) / 60 / option >= 240 (0x4C4C80..0x4C4C9D), not capped, so the time closed counts in full | 40 h | VERIFIED-C |
| Pregnancy | state+0x24 | units | 21 units | 3 h 30 min | VERIFIED-C |
| Baby cooldown | gs+0x25AE0 | R | birth: 600 x (5-d1/20)(5-d2/20) s; failed try: 1,200 s; drop refusal: 3,300 s; another path 1,800 x (same product) s | 10 min .. 12 h 30 min | VERIFIED-C (writers and the one reader, HandleDropOnVillager) |
| Symptom | state+0x64.. | R | 6..17 h | 6..17 h | VERIFIED-C |
| Food group | state+0x88.. | R | 86,400 s | 24 h | VERIFIED-C |
| Interest | CMoney+0x0C | G | 86,400 s, max 2 days paid | 24 h | VERIFIED-C |
| Food Club | FoodStore+0x80 | G | 86,400 s, all missed days | 24 h | VERIFIED-C |
| Island event | gs+0x25ADC | G | 3,600 s | 1 h | VERIFIED-C |
| Marriage e-mail | gs+0x25AE4 | G | 180 s, then 300 x visits + 600 x years over 26 | 3 min .. | VERIFIED-C |
| Service workers (Maid / Gardener visits) | gs+0x25AF8, gs+0x25AFC | G | 3,600 s, daytime (PC clock) only; on load an overdue one is reset to 180 + rand(600) / 300 + rand(600) s | 1 h | VERIFIED-C |
| Messes | CCollectableItem+0x8A4 | G | 300 min (population < 4) / 150 min | 5 h / 2.5 h | VERIFIED-C |
| Collectible spawn | per frame | F | 3 / 6,600 (Lucky Rock 3 / 3,300) | mean 73 s / 37 s | VERIFIED-C |
| House malfunction | per step | S | 1 / 800 | mean 26.7 min, also while paused | VERIFIED-C |
| Weather spell | Weather+0x08 | G | Normal 900..2,399 s, others 360..719 s | 15-40 min / 6-12 min | VERIFIED-C |
| Flea Market | InventoryManager+0x4A0 | R | none in B200 (stock 21,600 s; that code is unreachable, section 16) | never | VERIFIED-E |
| Flea Market, unpatched game | InventoryManager+0x4A0 | R | 21,600 s, checked when the Flea Market is opened (stock exe, section 22) | 6 h | VERIFIED-E |
| On Sale | InventoryManager+0x484 | G | 86,400 s | 24 h | VERIFIED-C |
| Day / night | PC local clock | wall clock | | follows the PC clock | VERIFIED-C |
| Villager positions refresh | gs+0x25CD4 | R | 40 s (`TakePositions`) | 40 s | VERIFIED-C |
| Autosave | gs+0x25CE4 (not in the save) | wall clock (CRT `time()`: GetSystemTimeAsFileTime; no speed or pause check) | 120 s. `theGameState::AutoSaveGame` 0x4994E0 saves when the due time < now, then due = now + 120, `SaveCurrentGame` 0x49AB50 (Save(0), Save(slot): the slot file `theGame::Shutdown` 0x498230 writes on quit; it also sets due = now + 120, so any save restarts the wait) and shows on-screen message 0x1E (`0x4533C0`; its text not looked up). Called at 0x498046 by `theGame::GameUpdate` 0x497AF0 (vtable 0x4FC4E4 slot +0x1C; `ldwGame::Run` 0x4754B0 calls it every frame; its only `ret` is 0x49805A, every scene case reaches the check 0x49803D) once the start-up counter theGame+0x24 is past 6. Emulated (the check and AutoSaveGame run as linked in both exes; clock, save and message stubbed): overdue by 1 s -> SaveCurrentGame + message 30, next due +120; due = now or later -> no save; counter 6 -> no save. Stock exe: the same code at 0x4296A0 (clock 0x402820, save 0x429660, message 0x4478F0), called at 0x4290A6 by GameUpdate 0x428B70 (vtable 0x4E2998 slot +0x1C, Run 0x4035E0), emulated with the same results | 2 min, also while paused | VERIFIED-E (stock and B200) |
| Store "time skip" | | | +3,660 x option s | 10 h 10 min of aging | UNCONFIRMED (purchase) |

## 18. Chance index (every rand call)

`rand_index.tsv` lists all **5,205** `GetRandom` call sites in the object code with their argument, the next
instructions and a reach class from the direct call graph (`rand_reach.py`):

| Class | Sites | Meaning |
|---|---|---|
| frame | 420 | reached by direct calls from the house screen's per-frame update / 2-second step |
| behaviour | 4,431 | villager and pet behaviours (action lengths, variants), dispatched by `StartNewBehavior` through the behaviour table |
| event | 107 | island events (section 11) |
| input | 115 | only from mouse / message / store handlers (drops, purchases, dialogs) |
| setup | 39 | only from Init / Reset / Load / constructors |
| other | 93 | no direct caller found (pointer-called or unused) |

Gameplay rolls on the frame path, all covered above (exact odds over the game's rand):
`UpdateScene` rand(800) malfunction, rand(14/17) which one, rand(100) < 66 island-event e-mail;
physiology rand(25) poo, rand(100) x10 eating / waste / starvation / sickness / recovery / old age,
rand(64) x6 newborn positions; `UpdateDisease` rand(1000), rand(100), rand(7), rand(250);
`UpdateHealthState` rand(100) x2; `SetSymptom` rand(12); `ChanceOfPregnancy` rand(100); `Impregnate` rand(100) x2;
`RealtimeWorkDone` rand(6); `CVillagerSkills::Reset` rand(132); `UpdateNutritionAllVillagers` rand(10), rand(3);
`CCollectableItem::Update` rand(6600/3300), rand(100), rand(6/4/3); `Add` rand(areas), rand(4), rand(100);
`CWeather::Update` rand(6), `SetCurrent` rand(1500/360), rand(1000) intensity; `FireEvent` rand(eligible);
Flea Market / On Sale shuffles rand(count); `theGameState::Load` rand(140) start money, rand(600) worker timers.
The other frame-path sites are cosmetic (animation frames, birds, butterflies, bubbles, smoke, rain and snow
particles, e-mail wording, names, looks): `frame_sites.txt`.

Behaviour-table sites (4,431) decide how long actions last and which variant plays. Their rewards (needs changed by
each action) were not decoded in this pass: settled in section 24, future work.

## 19. Per-save values the window can read (file offsets)

| Value | File offset | Section |
|---|---|---|
| Speed option (10; +999 paused) | 0x25B20 | 1 |
| Header start time (real-time base) | 0x04 (i64) | 1 |
| Game time block | 0x16404 (speed, previous speed, real stamp, game s, real s at save) | 1 |
| Villager record n | 0x172B0 + n x 0x7BC: left home +0x001, left-home game s +0x004, age +0x008, gender +0x00C, health +0x0B4, cause +0x0B8, pregnant +0x0CC, babies +0x0D0, energy +0x0DC, happiness +0x0E0, trend +0x0E4, hunger +0x0E8, poo +0x0F0, fertility +0x0F4, desire +0x0F8, symptoms +0x104, symptom expiry +0x10C, infections +0x128 / +0x129, food-group flags +0x12C, food-group expiries +0x130, career +0x140, level +0x144, progress +0x148, salary +0x14C | 2-9 |
| Money, rate, last interest | 0x168BC, 0x168C0, 0x168C4 | 8 |
| Food, Food Club flag, last delivery | 0xE3BC, 0xE3C0, 0xE3C4 (FoodStore +0x78 / +0x7C / +0x80) | 8, 14 |
| Pending babies | 0x25AB8 | 6 |
| Island / baby / marriage / worker timers | gs 0x25ADC / 0x25AE0 / 0x25AE4 / 0x25AF8 (file = gs + 8) | 17 |
| Family tree, child count | 0x1848 | 10 |

The infection and food-group fields lie inside the 0x98-byte CVillagerState copy (`CVillagerState::Copy`, 0x26
dwords), so they are saved; their meaning is from the code above. Lucky Rock (CCollectableItem+0x8A8) and Health
Plan (gs+0x25B1D) are restored by the patcher from its own saved record (discoveries.md); their save location is
UNCONFIRMED here.

## 20. Open questions for the owner (nothing changed)

1. **Food groups**: `FoodGroupsActive` counts a fifth slot made of the first group's expiry byte and the career id,
   so careerless villagers (children, unemployed adults) with any food group count one extra group (later old-age
   limit; at a count of 5 a lower disease chance). Stock code. How should the window present it?
2. **Brokerage Account removal** sets the interest rate to 1%, below the stock 10% default (patcher code at
   0x4B8B7D). Intended?
3. **Catch-up cap for option 20** compares against 23,800 s but then sets 31,000 s (stock code). Not reachable in
   B200 (nothing sets option 20); relevant only if Time Controls (B201) ships.
4. **Flea Market** rotates every 6 real hours while the game's own tip says three times a day.
   *Answered 2026-10-25: false for B200.* The expanded Flea Market lists all 36 items and the rotation is never
   reached (section 16). *True for the unpatched game* (section 22): the window shows both.
5. House malfunction rolls run while the game is paused (the 2-second step has no pause check).
   *Re-verified 2026-10-25 (VERIFIED-E):* the step 0x4A266E..0x4A28F9 run as linked with the speed option at 10
   and at 1009 (paused) both reach `GetRandom(800)` and then the malfunction pick `GetRandom(14)`; the step's clock
   `ldwEventManager::GetSeconds` 0x474600 is `_time64` (wall clock). The only pause checks in `UpdateScene`
   (0x4A25FC, 0x4A264C, 0x4A30AD) lie outside the step.

## 21. Scripts and data (the analysis scripts are kept outside the repo; careers.tsv, events_registry.tsv, events_emulated.txt and rand_index.tsv are in this folder)

`coffmap.py` (symbol map `map_b200.json`), `exedis.py` (named disassembly of the exe), `fn.py` + `dis\*.txt`
(dumpbin of every object), `cg.py` (call graph), `jt.py` (switch tables), `strings.py` -> `strings.tsv`,
`careers.py` -> `careers.tsv`, `emu.py` (unicorn harness), `t_preg.py`, `t_phys.py`, `t_life.py`, `t_dis.py`,
`t_events.py` -> `events_emulated.txt/json`, `events.py` -> `events_registry.tsv`, `ev_dump.py` ->
`events_dump.txt`, `rindex.py` -> `rand_sites.tsv`, `rand_reach.py` -> `rand_index.tsv`, `frame_sites.txt`.
Nothing in any repo, save or install was changed; no game was launched.

## 22. The unpatched game (stock executable), 2026-10-25

Target: `work/vanilla_runtime_payload/Virtual Families 2.exe` (the patcher's vanilla payload, sha256
1582d9e84e1c32f5...). It is a different compile of the same game (frame-pointer omission, no symbols; the desktop
objects place only 67 functions in it), so every routine below was located by matching the B200 routine's constants,
struct offsets and call shape, and then compared instruction by instruction. Nothing was inferred from names.

**Same in the stock exe (adds nothing to the window):** `UpdateScene` 0x4400F0 (2-second step, island-event timer
66% / 3,600 game s, malfunction 1 in 800 then 1 of 14 or 17 with the same 17-case table 0x441160, service-worker
timers, pause checks); `AllVillagersTimeflowUpkeep` 0x499700 (86,400 / 31,000 / 38,200 / 23,800 caps, paused zero,
college at 380 units, body removal at 240 units); the physiology upkeep 0x49B840 (hunger, salary x 6 / 24, poo,
eating, waste, no food, sickness, recovery, old age 1,100 + 20N units, birth and the baby waiting time, catch-up
work, longevity goals); `FoodGroupsActive` 0x4A0A80 (five slots: the Grains quirk is stock); `UpdateDisease`
0x4A13F0; `UpdateEnergyState` 0x4A1320; `UpdateHealthState` 0x4A0AD0; `UpdateHappinessState` 0x4A0B80 (the same 10
renovations 0xE1..0xEA); `SetSymptom` 0x4A09D0; `ChanceOfPregnancy` 0x4A0810; `Impregnate` 0x495360;
`AddOffspring` 0x490360 and the 6-child limit 0x48FEC0; `ReportDeath` 0x4905D0; `CVillagerSkills::Reset` 0x49FAF0
and `AdvanceCareer` 0x4A01B0 (6% pay, 3,000 progress); `RealtimeWorkDone` 0x4985A0; `CMoney::Reset` 0x427C20 (rate
0.10), `UpdateInterest` 0x428150 (at most 2 days), `Adjust` 0x428050 (0 .. 4,000,000,000); start money rand(140) + 50
(0x42AA62); `CFoodStore::Update` / `JoinFoodClub`; the dating and founder candidates 0x42FD80 / 0x42DF60; `CWeather`
0x4A3F80 / 0x4A3DA0 (900 + rand(1,500), 360 + rand(360)); `CCollectableItem::Update` 0x415310 (rand(6,600 / 3,300),
messes every 300 / 150 game minutes) and `Add` 0x415090 (4 / 13%, Lucky Rock 8 / 26%); `MaybeUpdateSaleItems`
0x4BAFA0; `HandleUpgrade` 0x432530 (time skip 3,660 x option, the $750 cap, the Lotto table); the speed option's
writers (10, +999, -999 then 0 -> 10); the autosave `AutoSaveGame` 0x4296A0 (120 s, section 17). The 96 island events are registered in the same order (`CIslandEvents`
constructor 0x41C8E0) and every `CanFire`, `CalcAward` and `ImpactGame` matched by title key has the same constants
and calls.

**Different (each shown both ways in the window):**

| Item | B200 core (with the patcher) | Unpatched game (stock exe) | Status |
|---|---|---|---|
| Flea Market | all 36 goods, never changes (`VF2GetExpandedFleaMarketCount` 0x4B9A90, always on) | 5 of the 36 goods, re-picked when opened more than 21,600 real s after the last pick (`MaybeUpdateRotatingItems` 0x4BA710) | VERIFIED-E both |
| Special Upgrades page | 10 items: the stock 6 and the Brokerage Account, Food Club, Health Plan, Lucky Rock (`patch_visible_special_upgrades`, always on) | 6 items (0x556E3C): none of the four | VERIFIED-E both |

**Reachability of the stock Flea Market** (VERIFIED-C path, VERIFIED-E outcome): `theMainScene::HandleMessage`
0x441EAB opens the store on its menu, `SetStoreCategory(0x17)`; `CScrollingStoreScene::HandleMouse` 0x4340E0, on
the menu (0x434227), reads the clicked row's category from table 0x5346E0 (0x4345CA) and calls
`SetStoreCategory` 0x432050; row 1 is string 0x487 "Flea Market", category 15. `SetStoreCategory` calls
`GetCategoryItemCount` 0x4BB0A0, whose case 15 (jump table 0x4BB17C) calls the rotation and returns +0x49C (5).
Emulated from that caller after `CInventoryManager::Reset` 0x4BA8F0 (a new family: all 36 goods can be picked):
real s 100,000 -> 5 goods, next change 121,600; 121,600 -> the same 5; 121,601 -> 5 new; 186,400 -> 5 new.

**UNCONFIRMED (not on the window):** both exes also keep the game's "Coins and More!" store page (category 0x16,
`HandlePurchaseItem` 0x433A60 stock / 0x48BF20 B200, identical code): coin packs, and the same four upgrades (the
Brokerage Account there adds 2 points). It is reached through the purchase dialog's "Get more coins" button (result
1 -> `HandleMoreBucksRequest` 0x432500); whether that button is ever shown was not traced. It is the same with and
without the patcher, so the window adds nothing for it.

Scripts (outside the repo, scratchpad `gm2`): `fp.py` / `sweep.py` (routine matching), `consts.py`, `evmap2.py`
(events by title key), `stock_flea.py`, `special_upgrades.py`; the repo test is
`tests/test_game_mechanics_stock_exe.py` (skipped without the stock exe).

## 23. Every store item (2026-10-27)

The owner's rule: every store item, upgrade and service gets its own entry. All in the B200 core exe (sha256
5cad4050) unless marked; the stock exe is sha256 1582d9e8. The page's data and lines are `src/vf2_game_mechanics.py`
(`_store_lines`); `tests/test_game_mechanics_store.py` pins them to both executables.

| What | Rule | Status |
|---|---|---|
| Store tabs | store menu table 0x574744 (16-byte rows: string, 0, category, icon). `GetCategoryItemCount` 0x46B6D0 / `GetCategoryItem` 0x46B210 run as linked after `CInventoryManager::Reset` 0x46C130 for every category; stock 0x4BB0A0 / 0x4BAA50 after 0x4BA8F0. Patched / stock counts: General Appliances 18 / 15, Living Room 108 / 88, Dining Room 27 / 26, Bedroom 84 / 74, Outdoors 38 / 12, Accessories 109 / 47, Toys 21 / 21, Pets 15 / 13, Clothing 214 / 6, Food and Medicine 18 / 18, Career 31 / 31, Home Renovation 10 / 10, Special Upgrades 10 / 6, Flea Market 36 / 5 of 36 | VERIFIED-E |
| Prices, locks | `GetPrice` 0x46B9F0 and `GetLockGenerationLevel` 0x46B870 run as linked for every item; inventory table 0x56FE70 (0x24-byte rows: id, owned-upgrade flag, uses, price, lock, short and long description, food flag, drop-target flag) and furniture table 0x564F48 (0x6C-byte rows: id, image, price, lock, ...) equal the stock tables 0x553278 / 0x54C87C for every stock item. Locked while lock > `CFamilyTree::NumGenerations` | VERIFIED-E |
| Discounts | `CalcPrice` 0x48ACB0: On Sale (category 3) half; items 4..0xB half with the Food Club; 0x10F x (level + 1). Health Plan (gs+0x25B1D) x 25 / 100 for items 0x18..0x36 in B200 (0x46BA3B), 0x18..0x21 in the stock exe (0x4B9DE0) | VERIFIED-C |
| Buying | `HandleMouse` -> `HandlePurchaseItem` 0x48BF20: items below 0xE1 to the tray (`AddItem`), 0xE1..0x1AC `TakeOne` + `HandleUpgrade` 0x48C2E0, 0x1AD..0x331 to storage; the game saves after every purchase | VERIFIED-C |
| Groceries, medicine, outfits | `theMainScene::HandleMouseDown` 0x49EE90: groceries on `kitchenTableRect1`, +150 food (organics +250), `UpdateNutritionAllVillagers(group, organic)` (Organics: Grains passes organic = false); medicines cure symptom 1..6 / infections, Baby Boost fertility += (102 - F) / 4, Doctor Consultation opens the diagnosis dialog; stock outfits 0x49 / 0x4A by gender | VERIFIED-C |
| Flea Market goods | `DispatchRotatingSundry` 0x49CB90, case table 0x49DD64 / 0x49DCF4 (index = item - 12), byte for byte the desktop object. Weather: Tropical Rain pushes 3 (Stormy), Tropical Sunshine 0 (Normal), Fog 4, Snow 5 (`CWeather::SetCurrent` 0x4CCF20: 0 Normal, 1 Sunny = `CSunBeam::Reset`, 2 Raining, 3 Stormy, 4 Foggy, 5 Snowing). Rewards / scolding: `InvokeReward` / `InvokeScolding` | VERIFIED-C |
| Upgrades, services, renovations | `HandleUpgrade` 0x48C2E0 (cases from its table 0x48CBC0 / 0x48CB70); Lotto `GetRandom(10000)` thresholds 1 / 3 / 23 / 223 / 723 / 4056; Time Warp 3,660 x option s, money capped +750; services act on gs+0x25CC4 | VERIFIED-C |
| Career equipment | `CTech::Level` = owned upgrades of the workplace (at most 12); `AdvanceCareer`: (4 x level + 20) / (career level + 1), x7 / x3 / x2 at levels 0 / 1 / 2 | VERIFIED-C |
| Mood points from items | `UpdateHappinessState` 0x4CBE90: +5 per renovation 0xE1..0xEA, min(placed furniture, 30), the item-and-like table (desktop 0x2ED..0x55F; the Fish Bowl 0x202 skips its like check), 500 x (equipment - 1) for likes 39 / 82 / 81. Like names: string 0x7AF split on commas (120 names; the game has 121 likes, `CLikeList::Add` rand(121)) | VERIFIED-C |
| Patcher rows | `VF2GetVisibleSpecialUpgradePrice` 0x4B9F60, 0x4B8B50; outfit store `VF2GetOutfitStorePrice` 0x4B9E80 ($75; bodies 50..53 $500), names 0xBED + 2 x (54 x sex + body) / 0xF2B + 2 x (50 x sex + style); Cheat Upgrades and the remodels from the generator source (`VF2ApplyVisibleSpecialUpgrade`, `CHEAT_UPGRADE_ITEMS`, `MOBILE_RENOVATION_STYLE_CATALOG`, `AI_BATHROOM2_STYLE_CATALOG`) | VERIFIED-C |

Settled 2026-10-27 (the owner: "Investigate the unconfirmed stuff too"), nothing UNCONFIRMED is left in the store
groups:

| What | Rule | Status |
|---|---|---|
| Actions | `CBehavior::CBehavior` registers every action by id (`SetMacro`); each handler's `PlanToInc*` / `PlanToDec*` calls and arguments (rand ranges resolved) are its need changes; `CVillagerPlans::ProcessCurrentPlan` applies each planned change once and marks the step done. The page's Actions group lists the actions any item or furniture piece starts. Every conditional branch of the 63 was read: no need change depends on age, time of day or weather; a missing or unreachable piece plans none; the other branches (Reading 0x33, Using the toilet 0x62, Barbecuing 0xDA, Needs to sit down 0x189, Jumping on the bed 0x55) are given with their action (section 24) | VERIFIED-C |
| Furniture drop actions | `theMainScene::HandleDropOnHotSpot` -> `CContentMap::GetHotSpot` ((cell >> 18) & 0x7F) -> `CHotSpot::Dispatch` (handlers set in `CHotSpot::CHotSpot`, 83 hot spots) -> each handler's `NewBehavior` ids; a piece's hot spots come from its placement map (`GetFmapName`: the image name from `ImageList` 0x579E48, `<name>.fmap`), B204 `final_all_enabled` maps; the patcher changes no stock piece's hot spots | VERIFIED-C |
| Pets | placed through `CFurnitureManager::DropFurniture` -> `CPetManager::SpawnPet`, counted by `NumberOfItemsPlaced`; no pet code calls a need-changing function; a drop on a pet starts behaviour 0x19A (Petting, no need changes) | VERIFIED-C |
| Stock outfits | `CInventoryManager::MaybeUpdateOutfits`: Discount rows rand(32), Department 32 + rand(12), Designer 44 + rand(6), re-picked 14,400 game s after the last pick | VERIFIED-C |
| Outfit store | `VF2NormalizeOutfitToolInHand` 0x4BA000 (generator source): `GetToolInHand` / `GetToolInUse` report the stock outfit tool 0x49 / 0x4A with the row's body or head selected | VERIFIED-C |
| Children's book reader | `GetRandomVillager` selector 6: age >= 280 units with a career and state+0x24 (record +0x0CC, pregnant) zero, or age >= 1,100 units | VERIFIED-C |

## 24. The formerly UNCONFIRMED lines (2026-10-27)

Weather names follow the owner (decision 2026-10-27): Normal (the plain sky) = type 0 `eWeather_Sunny`, Sunny (the
grey tint with sun beams) = type 1 `eWeather_Cloudy`, Raining 2,
Stormy 3, Foggy 4, Snowing 5 (CodeView enum `EWeather`, Weather.obj).

| What | Rule | Status |
|---|---|---|
| Newborn age | `Impregnate` 0x4BB920 -> `SpawnSpecificPeep` age argument 0x28 = 40 units = 2 years | VERIFIED-C |
| Work accident / act of nature | causes 3 / 4; their only setters `MakeRandomVillagersInjured` / `MakeRandomVillagersDead` have no callers and are not linked into B200; the 20 `AdjustHealth` / `SetHealth` sites pass cause -1, 0, 1 or 2: never happen | VERIFIED-C |
| Allow Older Pregnancies, on | trampoline in `ChanceOfPregnancy` (a parent's internal age >= 1,000) -> `VF2RollOlderPregnancy`: stock formula without the mother cutoff x 10, capped by `VF2OlderPregnancyCapTenths` (age 50..59: (60 - age) x 10; 60..68: 69 - age; 69+: 1), at least 1, `GetRandom(1000) <` it; `VF2StoreTryForBabyCooldownMaybe` skips the 1,200 s failed-try wait for such a couple | VERIFIED-C |
| Baby wait reader / drop try | `HandleDropOnVillager` refuses while gs+0x25AE0 runs, cuts > 1 h to 3,300 s; `TryToMakeBaby` 0x4A23C0: success -> wait 0, `Impregnate`, everyone does 0x7B, each spouse trend +300 and happiness + 5 x (desire / 20); failure -> wait = now + (5 - m/20)(5 - f/20) x 1,800 s, trend -50 and happiness -3 each | VERIFIED-C |
| Work choice | `CVillagerAI::DecideWhatToDo`: `GetRandom(total)` over the eligible actions' weights; x 3 for a need trigger or a held like, / 4 for a dislike; office 0x2C, kitchen 0x47, workshop 0x4B only by day or evening; `InitAI` run as linked: 469 / 553 / 478, min 50, max 45,000, likes 82 / 39 / 81 | VERIFIED-E (weights), VERIFIED-C (rule) |
| Catch-up work | upkeep 0x4C4A8F: age - processed age > 2 units, not sick, not pregnant, a career -> `RealtimeWorkDone` 0x4C3DB0: weight of the career's work action / 400 tries, each `GetRandom(6) == 0` -> `AdvanceCareer(v, pay true, promote false)` | VERIFIED-C |
| Heir | `CAdoptionScene::CreateNextGenerationCandidates` 0x4034A0 clones as adult every offspring id != -1; only `CFamilyTree::ReportDeath` 0x457A50 writes -1 (live death behaviour, or 240 units later): a child who left home is still offered | VERIFIED-C |
| Hammock e-mail | `ImpactGame`: `MakeAllVillagersRunTo` x 750..834, y 184..240 only | VERIFIED-C |
| Small Package / Medium Brown Box / Sealed Green Bag | yes: item rand(6) + 0x18 (the six medicines) / rand(4) + 4 (groceries) / rand(4) + 8 (organics); someone at home and a free tray place | VERIFIED-C |
| Wrong Address | yes: -$100; rand(100) < 50 -> 0x1B5 Blue Children's Bed (50.05%), else 0x1B4 Pink (49.95%), to storage | VERIFIED-C |
| Delivery Truck | yes: rand(100) < 33 -> 0x21B ($4,150 Wall Painting), < 66 -> 0x21A ($350), else 0x219 ($450), to storage; no: rand(8) x $20 | VERIFIED-C |
| Mysterious Collector | can fire with someone at home and an item on collection page 0x67 or 0x86; award $20 / $30 / $100 per common / uncommon / rare over pages 0x67, 0x4F, 0x5B, 0x86, 0x92; yes: award, collections reset, goals 0x4A, 0x4B, 0x4C, 0x5D (and one more) reset | VERIFIED-C |
| Rare Bird | yes: -(rand(8) x 10 + 15); everyone runs to x 174..240, y 269..309 and does 0x7D | VERIFIED-C |
| Money checks | run as linked: Scratch-off > $21; EPA >= $1,312; Oh So Clever, Office Collection, Overdue Book, Professional Fee >= $750; Infringement and Tax Audit fee >= $750 and rand(100) >= 50; Tax Audit gift none. Read: Aesthetic Society, Children's Association, Community Association >= $750; Career Training > $255; Trainer > $5; Electric Bill none | VERIFIED-E / VERIFIED-C |
| Starting weather | `CWeather::Reset` (only from `theGameState::Init`): type 0; rand(100) < 20 -> next = `Random(0)`, change after 30 game s; `Random(prev)` = PC minute mod 6, a 4 or 5 +1 mod 6 when rand(100) < 50, equal to prev +1 mod 6; weather not saved | VERIFIED-C |
| Drawing | `CWeather::Draw`: type 0 (Normal) nothing; type 1 (Sunny) grey tint 0.2 by day and `CSunBeam`; 2 rain; 3 rain and lightning; 4 fog; 5 snow; the tint by day only | VERIFIED-C |
| Breakdowns | picks 0 toilet, 1 / 2 bathroom sinks, 3 router, 4 kitchen sink, 5 stove, 6 shower, 7 dryer lint fire, 8..10 north bathroom (0x49 / 0x48 / 0x4A), 11..13 ants; with kitchen garbage gs+0x28 > 5 `GetRandom(17)`, 14..16 ants | VERIFIED-C |
| Patcher drop routes | generator helpers: lounger roll 80 + nap (70 - energy) + sleep 3 x (45 - energy) weights, branch changes as on the page, refused for weather type >= 2; patio / picnic preparing -7 energy +7 dirt +5 trend +7 hunger, drinking -10 hunger, picnic -40 hunger, each +4 dirt +6 poo; bike = treadmill walk / run 50%; gym and yoga = WorkingOut (-4 energy, +5 dirt) / QuickWorkout (-7, +7, +5 trend) 50%; ping-pong = PlayingPooltable; spa receiving +2 dirt, +7..11 energy; umbrella, birthday and holiday helpers plan no need changes | VERIFIED-C |
| Action branches | Reading: `LinkPeepToFurniture(0x5A)` fails -> head shake, trend -1, else +1; toilet: both occupants (gs+0x25C80 / +0x25CA8) taken -> the wait path skips the changes; BBQ: food <= 10 refusal; Needs to sit down: energy (state+0x34) > 35 -> +3, else +10 (the 45..52 is the lie-down length); Jumping on the bed: -2 energy three times, +3 trend, nothing without a bed | VERIFIED-C |

Tropical Sunshine: the owner says it gives Sunny weather; the code (B200 0x49D890, push 0 before
`PlanToChangeWeather`; the plan step calls `OverrideNight(180)` at 0x4CAFDC) sets type 0, the plain sky the owner calls Normal. A
contradiction to live-check.

Baby wait clock: every writer of gs+0x25AE0 and its one reader use `GetSecondsFromGameStart` 0x475830 (`_time64` minus the save's start time): real time, running while paused or closed, unaffected by the speed option; the Time Warp moves it on by moving the start time back. A drop with more than 3,600 s left sets now + 3,300 s (0x49E773..0x49E78E), so a player never waits more than 55 minutes after trying. VERIFIED-C.

## 25. Clocks (2026-10-27)

| Clock | Source | Speed | Paused | Closed | Used by | Status |
|---|---|---|---|---|---|---|
| Real time | `GetSecondsFromGameStart` 0x475830 = `_time64` - the save's start time | no effect | runs | runs | food groups, symptoms, the baby wait, collectibles on the floor, the unpatched Flea Market, the malfunction start (> 360 s, 0x4A28C0) | VERIFIED-C |
| Real time while running | `ldwEventManager::GetSeconds` 0x474600 (the 2-second step, 0x4A266E); frames | no effect | step runs, frames' collectible rolls stop | stops | upkeep step, malfunctions, autosave; collectible rolls | VERIFIED-C |
| Game time, age clock | real seconds since the stamp / 60 / speed option | scales | discarded (accumulator 0 at option >= 999, 0x4C4D99) | capped catch-up: options 10, 2, 1: in full to 31,000 s; 5: in full to 38,200 s, then 31,000; 20: in full to 23,800 s, then 31,000; over 86,400 s: 86,400 (emulated at 10, 5, 20, 2, 1) | ageing, needs, health, salary, pregnancy, body removal (uncapped) | VERIFIED-E |
| Game time, game clock | `CGameTime::Seconds` 0x468B00 = banked + (real - anchor) x 10 / speed (emulated: 10,000 real s -> 10,000 at 10, 20,000 at 5, 5,000 at 20, 0 at 0) | scales | stopped (`SetSpeed(999)` stores 0) | Save/LoadState keep speed, anchor and banked seconds, so the whole time closed counts at the saved speed (none if saved paused) | Random Events, messes, weather, interest, Food Club, On Sale, Maid / Gardener, dating and college e-mails, outfit restock, OverrideNight | VERIFIED-E (Seconds), VERIFIED-C (load) |

Speeds: gs+0x25B18 / `CGameTime`+0x20: Normal 10 (the stock game's only speed besides Pause); the patcher's Time
Controls (runtime/native/b200time/b200time_time.inc): Slow 20, Fast 5, 5x 2, 10x 1. One hour of game time = speed / 10
real hours. The Time Warp moves the start time back 3,660 x option s: 61 age units at any speed, every real-time count
+3,660 x option s.
