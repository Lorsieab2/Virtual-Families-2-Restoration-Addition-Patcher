# The Family History log (vf2history_b200.dll): every record, where it is written, and how each event is seen

One log, the **Family History**, of every family event Virtual Families 2 has, for the Family Tree Maker (the save
forgets a spouse who leaves or dies before any child, every earlier spouse, twins and triplets, causes of death and
how anyone joined or left). The patch **Family History log** (setting `family_history`, Experimental, off by
default, never ticked by Enable All) installs its own companion DLL, `vf2history_b200.dll`, in `Virtual Families 2
Patcher Files`, which writes each event as it happens, from the game's own memory and with the game's own words
(theStringManager at run time: "Male", "Female", "Nursing", the causes of death, "New Generation", "{name} is going
to college!", "The Talent Scout", "The Little Visitor", "Adoption Services", and each Random Event's own title). The
layout is the Virtual Families 1 Family History log's (VF1 `feat/family-history` a5f7ed9), which is the Virtual
Villagers Fun Patcher's record layout with family words. In Virtual Families the game's random events are **Random
Events**, each an **Email Event** or a **Popup Event**. **Not live tested**: every hook below is proved statically
and emulated, never run in the game.

## The file (per save slot, beside the save)

    <save folder>\Virtual Families 2 Patcher\Save <N>\Logs\Family History\Family History <k>.txt

It opens with `Family: <player name> (Save <N>)` (Virtual Families 2 has no family surname: the player name the
save holds, gs+25ABCh, as Rename Family uses). Each record is a heading `[YYYY-MM-DD HH:MM:SS] <Kind> <n>`
(numbered per kind across all files: `Death 42` follows the highest `Death` in any file), its `  Label: value` lines
(a family member's own lines one step further in), then a blank line. A family member is written as the Virtual
Villagers patcher writes a villager: the name, then the age (in years), sex, head and body. Nothing is rewritten;
after 2000 records the next one opens file `<k+1>` with the header. There is no other file: the earlier spouse and
why they left are read back from the log's own Marriage, Death and Divorce records.

## Every record

```
[2026-10-24 12:34:56] Conception 1        [2026-10-24 12:34:56] Birth 1
  Mother: Ann                               Child: Cid
    Age at conception: 26                     Sex: Male
    Sex: Female                               Head: 3
    Head: 3                                   Body: 4
    Body: 4                                 Mother: Ann
  Father: Bob   (or "Father: (unknown)")      Head: 3
    Age at conception: 27                     Body: 4
    Sex: Male                               Father: Bob   (or "Father: (unknown)")
    Head: 7                                   Head: 7
    Body: 8                                   Body: 8
  Babies Nursing: 2                         Born as: Single birth | Twin | Triplet
  Generation: 1                             Generation: 1

[...] Death 1                             [...] Marriage 2
  Name: Bob                                 Family member: Ann
  Age at death: 27                            Age: 26
  Sex: Male                                   Sex: Female
  Cause of death: Old age                     Head: 3
  Head: 7                                     Body: 4
  Body: 8                                   Married: Carl
  Family role: Parent (married in)            Age: 29
  Generation: 1                               Sex: Male
  Current spouse of Ann: (none)               Head: 5
                                              Body: 6
[...] Divorce 1                             Remarried: yes                       (a remarriage only)
  Family member: Ann                        Earlier spouse: Bob (died|divorced)  (a remarriage only)
    Sex: Female                             Current spouse of Ann: Carl
    Head: 3                                 Generation: 1
    Body: 4
  Divorced: Bob                           [...] Arrived 1
    Age: 27                                 Name: Wren
    Sex: Male                               Age at arrival: 3
    Head: 7                                 Sex: Female
    Body: 8                                 Head: 3
  How: Divorce Spouse                       Body: 4
  Current spouse of Ann: (none)             How: Adopted (Popup Event: The Little Visitor)
  Generation: 1                                  | Adopted (Adoption Services)
                                            Family role: Child
[...] Left Home 1                           Generation: 1
  Name: Eve
  Age: 19                                 [...] Random Event 1
  Sex: Female                               Popup Event: The Little Visitor     (or "Email Event: Subject: A Secret Admirer")
  Head: 3                                   Choice: A                           (an event with choices: A or B)
  Body: 4                                   Generation: 1
  What happened: Eve is going to college!
     | Left home with The Talent Scout (Popup Event)
     | Sent to Boarding School

[...] Generation 1 / New Generation 1 / Generation 2
  Name: Ann
  Age: 26
  Sex: Female
  Head: 3
  Body: 4
  How: Founder (adopted and started the family) | Founder (after the eviction) | Heir (inherited the house)
  Generation: 1

[...] Renamed 1                (a family member renamed in the Details box; Virtual Families 2 only)
  Old name: Cid
  New name: Zed
  Age: 4
  Sex: Male
  Head: 3
  Body: 4
  Generation: 1

[...] Evict Family 1                  [...] Start Over 1
  Family members: Ann, Bob              The earlier family's history was cleared.
  Generation: 1

[...] Family Renamed 1         (written by Rename Family on the Tools tab)
  Old name: Smith
  New name: Brand New

[backfilled, no date] Family Tree 1      (an existing family's first load, once: what the save's tree holds)
  Parent: Ann                    (Sex, Head, Body one step in; "    Died: yes" for a slot of -1)
  Parent (married in): Bob
  Child: Cid
  Current spouse of Ann: Bob     (the newest generation, both alive)
  Generation: 1
  Note: Recorded afterwards (from the save's Family Tree: no dates, ages, causes, twins or earlier spouses)
```

The records a Random Event's choice makes (a child who arrives or leaves home) follow the event's own record.
Virtual Families 1's Roll the Dice, Spawn Child, Adopt Outside Child, Adopt New Person and "Left the house" come from
vf1fun's Cheat Upgrades and have no Virtual Families 2 counterpart; `Renamed` has no Virtual Families 1 counterpart.

- **A new family** (a new game, or after Start Over) and **Start Over** (the confirmed Start Over) delete
  everything in `Save <N>\` except a `Backups` folder in it; the new family's log opens with `Start Over 1` (after a
  Start Over) and `Generation 1`.
- **Evict Family** keeps the log: everything before the `Evict Family` record belongs to the family that left, and
  the next family's first generation is `Founder (after the eviction)`.
- **Remarriage**: the earlier spouse is the last one the log saw this person marry in the same generation; `(died)`
  or `(divorced)` only when the log has that spouse's Death or Divorce record after the marriage (nothing guessed).

Same-sex marriages: Virtual Families 2 has none, but the patcher's **Allow Same-Sex Marriage** (the Cheat
Upgrades row Enable Same-Sex Marriage) marries a same-sex couple through the same accepted-marriage call of
`CFamilyTree::UpdateParents` (its only caller in every matrix variant, B200 to B203, the all-enabled one
included). Every record names each person with their own sex; there is no husband or wife word. Emulated:
two women marry, divorce and one remarries.

## Hooks (each proved by runtime/tools/gen_b200_history_sites.py on all 128 B200-B203 matrix executables; each emulated from its live caller in tests/b200_history_scenarios.py)

| Event | Where (B200 core) | Kind | Evidence |
|---|---|---|---|
| Conception, babies expected | `CVillager::Impregnate` 0x4BB920 | entry (6 bytes) | its two callers (theMainScene's try-for-a-baby 0x4A2425 and the plans' jmp 0x4B8570, from ProcessCurrentPlan 0x4CA5D9) push the father's head +6A80h and body +6A84h and the name "Joey"; babies expected +6B1Ch. Emulated: the real Impregnate, single / twins / triplets |
| Births | 0x4A7D05, theRealtimeManager::UpdateAll's only call of the physiology pass 0x4C4410 | call | the only delivery (0x4C4886..0x4C4A8F) and the only write of 0 to the pregnancy field are inside it. The father: the one seen at conception this session, else the record's other parent whose head and body equal the mother's +6AF0h / +6AECh (Impregnate stores the head and body it is given there), else "(unknown)". Emulated: UpdateAll's call, then the pass's own delivery code; single, twins, triplets, after a load, and with other looks |
| Deaths and causes | 0x4C4CCC (timeflow) and 0x4CAD92 (death behaviour), the only calls of `CFamilyTree::ReportDeath` | calls | the cause is CVillagerState+10h, written only by SetHealth / AdjustHealth (causes -1, 0, 1, 2 in the B200 code). Emulated: the whole timeflow upkeep and the behaviour's tail, with the real ReportDeath (it erases a childless spouse, and moves the spouse into parent 1 when the head dies childless) |
| Marriage, remarriage | 0x4531F3, `CFamilyTree::UpdateParents`'s only call (the dating scene's accept) | call | UpdateParents writes the one not yet in the tree into parent 2, over whoever was there. Emulated |
| Divorce | the generated Divorce Spouse block's `CVillager::DetachAll` call (0x4B9570 in the core variant) | call | the only block that zeroes the record's parent 2 after resetting the spouse; found in every variant. Emulated: the generated block from its first instruction |
| A new family, Next Generation (the heir) | 0x403A66 and 0x403A8C, CAdoptionScene::HandleMessage's Accept | calls | StartFamilyTree's other caller is theGameState::Load (a save without a tree), not logged. Emulated |
| A child joins | 0x47193A, 0x47198A (The Little Visitor 1/2), 0x48C87B (Adoption Services) | calls | the only AddOffspring callers besides Impregnate's own three (the babies), in every variant. Emulated |
| Leaving home | 0x4C4E24 (college at 17Ch), 0x48CA41 (Boarding School, through the store's jump table), 0x471F5A (The Talent Scout) | calls | SetLeftHome's only callers, in every variant. Emulated |
| Rename | 0x4AAA82 and 0x4AB1FD, theVillagerScene's calls of `CFamilyTree::ChangeName` | calls | ChangeName's only callers; the game calls it whenever the Details box closes or the selection changes, so a record only when the name changes. Emulated |
| Random Events | 0x46F403, CIslandEvents::FireEvent's only call of `ldwDialog::DoModal` | call | FireEvent is reached from FireEmailEvent (e-mail argument 1) and the public FireEvent (0, the hourly check and the store); its scan keeps only events whose IsEmailEvent (vtable +14h) equals that argument; the only CIslandEventDialog is built here and keeps the event at +50h and GetString(GetTitle()) at +54h, which DrawNoFadeScene draws (as an e-mail when +14h is true). The choice is +830h (0 A, 1 B), read when the event's vtable +10h (has choices) is true: CIslandEventDialog::HandleMessage 0x470A10 stores it from button 2 or 3 and runs ImpactGame with it on OK, inside DoModal, so a child who arrives or leaves with the event is recorded right after the event's record. Emulated: both public entries, an event of the other kind left out, the real constructor head, the real HandleMessage, and The Little Visitor and The Talent Scout run inside the dialog |
| Evict Family | 0x4A68E8, theOptionsDialog::EvictFamily's call of CFamilyTree::EvictFamily | call | logged before the household is removed. Emulated |
| Start Over | 0x4A42DF, the confirmed Start Over's call of theGameState::Init (Fix Vanilla Game Bugs; with it off, Start Over continues the game) | call | Emulated: the slot folder emptied, Backups kept, the next family's log opening with `Start Over 1` |
| After a load | theGameState vtable slot 13 | vtable (chains Time Controls) | an existing family's past, once |

Not logged: the Community Event dialog (`CCommunityEvent::Show`, 0x4A2AD9) shows only after an online poll
answers (PollCallback); the poll's server is gone, so it is treated as not reachable (UNCONFIRMED).

## The loader

Every executable gets a dormant `.vf2hist` byte (0 as built) and one more line in the Time Controls loader
wrapper on theGame::Init's first call: after the Time Controls and Up to 28 Children DLLs, when the byte is 1, it
loads `Virtual Families 2 Patcher Files\vf2history_b200.dll` once and calls `B200History_Startup`. The DLL
installs nothing unless `vf2history.ini` says `FamilyHistory=1` and every pin resolves exactly once (all or
nothing). The exporter's post-asset toggle sets the byte and stages the DLL and the ini only while the setting
is on. **This needs a matrix rebuild** (no executable before this branch has `.vf2hist`); the exporter gives a
build without the loader no records for the setting.

## UNCONFIRMED (not shown either way)

- Nothing has run in the game: the records, the slot folder (gs+25B20h) at a new family's adoption, the words
  GetString returns at run time (the emulation answers each id from the executable's static string table).
- The loader in an executable built from this branch: written into the generator, not built or emulated
  here (tests/test_b200_family_history.py's loader tests run with VF2_HISTORY_EXE once the matrix is built).
- The physiology pass: only its delivery block runs under emulation; the dialog constructor: only its head.
- Running beside Up to 28 Children's installed hooks: proved statically (its entry jmps are wildcards in these
  pins; this DLL writes no entry it hooks), not emulated together.
- Start Over followed by a load before the new family is adopted: the new family then empties the folder again
  and the `Start Over` record is lost.
- The Community Event dialog (above).
