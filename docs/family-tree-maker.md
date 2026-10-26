# Family Tree Maker (Virtual Families 2)

The Tools tab's **Family Tree Maker...** draws a family's tree from its save. It is the Virtual Villagers Fun
Patcher's Family Tree Maker (VV `main` cdcface3: ede00e7e plus 555023e0, no "Master ..." lines) by way of the
Virtual Families 1 Patcher's port (VF1 `feat/family-tree` 44db79e), re-traced for Virtual Families 2's own code.
Nothing was carried over from Virtual Families 1 without being checked in VF2's code or saves.

**VERIFIED** = read from VF2's own code (the desktop objects the patcher relinks, `work/desktop_obj_files`,
disassembled with relocations; offsets are into each function) or the stock exe, and consistent with real saves
(the copied fixtures in `tests/fixtures/vf2_saves`). **UNCONFIRMED** = not shown either way; the tree labels it.

## What the save keeps (FamilyTree.obj)

| Fact | Status | Evidence |
|---|---|---|
| One record per generation, oldest first, at most 30 | VERIFIED | `SaveState`/`LoadState`; `StartNextGeneration` calls `MakeRoomInTree` at 30, which shifts records down (`rep movsd` 0x312A dwords) and sets the new oldest record's two heir indexes to -1 |
| Founder: parent 1 with heir index -1 | VERIFIED | `StartFamilyTree` = `StartNextGeneration(v, -1)` |
| Heir: parent 1 of record g+1 carries the index of the child of record g it came from | VERIFIED | `StartNextGeneration` +0x3D..+0x6E searches the previous record's present children for the slot passed in; -1 when none. Real: all 9 links of the 10-generation fixture |
| A marriage writes parent 2 | VERIFIED | `UpdateParents` +0x41: parent 1 empty -> parent 1, else parent 2 (+0x84..+0xCA), heir index -1 |
| An earlier spouse is overwritten by a new marriage | VERIFIED | `UpdateParents` writes parent 2 whole; `CanMarry` = parent 1 present and parent 2 not |
| Parent 1 dies with no children and a spouse: the spouse is copied over parent 1, parent 2's present byte cleared | VERIFIED | `ReportDeath` +0x3D..+0x51 (`rep movsd` 0x36 dwords) |
| Parent 1 dies with no children and no spouse: nothing is written | VERIFIED | `ReportDeath` +0x35..+0x3B |
| Parent 2 dies with no children: only the present byte is cleared, the name stays until a new marriage | VERIFIED | `ReportDeath` +0xB8..+0xC4 |
| A parent with children, or a child, who dies keeps their place with slot -1 | VERIFIED | `ReportDeath` +0x90, +0xD7, +0x109 |
| Children: at most 6 in the save, in the order they joined (a baby at conception) | VERIFIED | `AddOffspring` (refuses at 6); `Impregnate` +0x188/+0x23F/+0x2A9 |
| Children 7 to 28: the Up to 28 Children file of that very save | VERIFIED | `runtime/native/b200kids/b200kids.cpp` sidecar format (`VF2KIDS`/`VF2B200`, FNV-1a of the save) |
| Divorce Spouse zeroes parent 2 and resets the villager: nothing of a divorced spouse is left | VERIFIED (source) | `docs/REQUEST_LEDGER.md` Divorce Spouse; B200 manifest `DivorceSpouse` (store item 0x14B) |
| Likes text: up to three of the comma list in string 0x7AF `eSayLikesList`, copied while the villager exists | VERIFIED | `CLikeList::GetListAsString`; `UpdatePeepRecord`. "running" is in the list, so **Runner** applies |
| Adopted child: no parents' names in the bio | VERIFIED | Adoption Services (`CScrollingStoreScene::HandleUpgrade` +0x585) and The Little Visitor (`CEventTheLittleVisitor1/2::ImpactGame`) call `SpawnSpecificPeep(age, sex, int)`, which passes null names to `Init` |
| Which of the two adopted a child | UNCONFIRMED from the save | the log's Event line names it |
| Natural births: father's name is the literal "Joey" | VERIFIED | docs/vf2-save-format.md section 4 |
| Causes 0 Disease, 1 Starvation, 2 Old age | VERIFIED | `CVillagerManager::AllVillagersRealtimePhysiologyAndProductivityUpkeep`: `AdjustHealth(-1, 0)` after `IsSick` +0x2F5, `(-1, 1)` from hunger +0x1FA / +0x26B, `SetHealth(0, 2)` on the old-age roll +0x3C3; the words are strings 0x87C..0x87E |
| Causes -1 "Unknown causes", 3 "Work accident", 4 "Act of Nature" | UNCONFIRMED | -1 is passed by theMainScene / CVillagerPlans; no caller of 3 or 4 was found; the words follow only the strings' order (the game never shows them) |
| Why someone left home (college, Boarding School, The Talent Scout) | UNCONFIRMED from the save | only the left-home flag is saved (docs/vf2-save-format.md section 8); the log's lines name it |
| A child's record no longer in use but with the left-home flag | VERIFIED | the flag is `SetLeftHome`'s; the tree says "Left home ... the save does not say why they left or what became of them" |

## The faces

| Fact | Status | Evidence |
|---|---|---|
| `Images\male_heads00.png` / `female_heads00.png`: 672 x 2800, 12 x 50 cells of 56 x 56 | VERIFIED | the stock exe's image table: `male_heads` id 0x244 at 0x53CDC4, `female_heads` id 0x240 at 0x53CD04, each 24 x 50 over the files 00 and 10; the PNGs' size; `CAnimManager::LoadAssets` +0x18F / +0x199 |
| Column 5 is the face looking straight out; all 50 rows of both sheets have one | VERIFIED | the sheets (measured: 50 boxes each); VF2's Hairstyle store icons use the same frame |
| The row is the head value | consistent, draw call UNCONFIRMED | `CVillager::Init` keeps the head in 0..49 (+0x227 / +0x23A); 50 rows; the head draw itself was not traced |
| The young sheet (00) at every age | owner's rule | |

## With and without the Family History log

Without the log the tree shows everything above, and says what the save does not: an earlier spouse, a
divorced spouse, twins and triplets once born, and why someone left home are not known unless the tree file saw
them. The tree file (`...\Save <N>\Data\Family Tree\Virtual Families 2 Family Tree - Save <N>.tree`) remembers
every member it has seen in that save, so a spouse who died with no children, an earlier spouse after a
remarriage, a divorced spouse and a founder who died childless stay on the tree once seen. After 30 generations it
also knows which generation the save's oldest record is.

With the log (`...\Save <N>\Logs\Family History\Family History <k>.txt`, written by `runtime/native/b200history`)
the tree adds: twins and triplets (Birth records' "Born as"), the cause and age at death, every spouse and the
order of a head's marriages (Marriage records, "Remarried", "Earlier spouse"), divorces, why someone left home
(Left Home records) and the Random Event that brought a member in or took one away ("Adopted (Popup Event: The
Little Visitor)", "Left home with The Talent Scout (Popup Event)"). A name the log gives that matches nobody, or
more than one member, is left alone. Records before the last Evict Family belong to the earlier family.

The format is the Virtual Families 1 Family History log's, the Virtual Villagers record layout (VF1
`origin/feat/family-history` a5f7ed9, `docs/FAMILY_HISTORY.md`): a `[YYYY-MM-DD HH:MM:SS] <Kind> <n>` heading,
`  Label: value` lines with each family member's own lines (age, sex, head, body) one step in, then a blank line.
Kinds: Conception, Birth, Death, Marriage, Divorce, Arrived, Left Home, Generation / New Generation, Random Event
(`Email Event:` / `Popup Event:`), Roll the Dice, Evict Family, Start Over, Family Renamed, and the backfill's
Family Tree. `src/vf2_family_history.py` is VF1's reader ported; the older one-line forms are not read (no
Virtual Families 2 log ever wrote them). It matches VF2's own log (`origin/feat/family-history` 9bfd948,
`docs/FAMILY_HISTORY.md`): an e-mail reads `Email Event: Subject: <subject>` and is shown "Email Event:
<subject>"; `Renamed <n>` (the Details box) makes the earlier records name the person by the new name, and the old
one is kept as a former name; an Arrived or Left Home record right after a Random Event is that event's, unless it
names its own way (Adoption Services, college, Boarding School); `Earlier spouse: X` with no "(died)" or
"(divorced)" labels nothing; Start Over comes before the new family's Generation 1.

Labels from the log: Husband N / Wife N (each spouse's own sex) only when the log saw the head's first marriage
itself, not a backfill; otherwise "Married in". Without the log only what the save and the tree file prove:
Remarried when two or more spouses of one head were seen; never an order, never "Divorced".
