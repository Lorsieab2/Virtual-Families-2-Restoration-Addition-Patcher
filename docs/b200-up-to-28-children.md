# Up to 28 Children: design, pins and evidence (static and emulated, no live test)

The owner's request (2026-10-21): up to 28 children per generation. Only the first 6 appear in the
Family Tree; every child, the 7th to the 28th included, can be chosen to inherit the house in Next
Generation. Children the stock save cannot hold are kept in a `.dat` sidecar beside the save (the
Virtual Villagers patcher's convention); the save format does not change. Twins and triplets near
the limit are clamped (27 children: a twin or triplet pregnancy has one baby; 26: a triplet pregnancy
has two), never past 28. Its own companion DLL and its own setting. The request said "off by default
unless the owner says otherwise"; this repository's standing owner rule is that every patch defaults
on (`tests/test_export_offline_patch_bundle.py`, EveryPatchDefaultsOn), so it is on by default. One
line (`"default"` in `SETTINGS`) turns it off by default if the owner prefers.

This was the "Increase Child Limit to 12" workstream, put on indefinite hiatus at B153
(`docs/REQUEST_LEDGER.md`, `docs/TODO.md`, `docs/discoveries.md` 2026-07-12 and 2026-08-06). The owner
reopened it as Up to 28 Children; the B153 audit's findings all still hold and are re-proved below.

## 1. Where the stock game limits children

All addresses are the B200 core executable (`outputs/VF2-B200-matrix-core`); the retail addresses are
`C:\vf2w\_vanilla_rt\Virtual Families 2.exe` (SHA-256 1582d9e8...73c3, not relocated). Every B200
function below was found by searching the core executable for the desktop object file's own bytes
(`work/patched_mobile_furniture_pack_objs`), exactly one hit each; the retail game was compiled
separately, so its code is different bytes with the same layout (section 4).

| What | B200 | Retail | Evidence |
|---|---|---|---|
| Household slots | `CVillagerManager::GetVillager` 0x4C5F10, `FindEmptySlot` 0x4C5B40 | SaveState 0x498EF4 | `cmp eax,1Eh` (30 slots); SaveState writes 30 records of 7BCh (E808h) at gs+172A8h |
| Family Tree record | `CFamilyTree::AddOffspring` 0x457600 | 0x490370 | count at record+1B4h (`[tree + n*6C8h - 50Ch]`), `cmp edx,6; je refuse`, child records D8h from +1B8h: 1B8h + 6*D8h = 6C8h, the size of one record |
| Family Tree save block | `theGameState::Save` 0x49AA00 | 0x42956D | FamilyTree::SaveState(gs+1840h), the next component at gs+E3B4h: 4 + 30*6C8h bytes, no tail |
| Births | `CFamilyTree::EmptyOffspringSlots` 0x457840 | 0x48FEC0 | `6 - count` (6 with no family) |
| Twins / triplets | `CVillager::Impregnate` 0x4BB920 | 0x495360 | first call EmptyOffspringSlots; none = no pregnancy; twins need it > 1, triplets > 2; chances GetRandom(100) < 7 + bonus and < 25 + bonus. B200's forced-count cheat (the jmp at +E3h) clamps to it too |
| Family Tree display | `CFamilyTreeScene::DrawFamily` / `CheckForFamilyPeepHit` | | loop the record's child count; never more than 6 recorded, so the tree shows the first 6 |
| Next Generation | `CAdoptionScene::CreateNextGenerationCandidates` 0x4034A0, `GetNextCandidate` 0x403900, `HandleMessage` 0x403920 | | clones every recorded child as an adult (`ClonePeepAsAdult`) into six-dword arrays at scene+20h (clone slots) and +38h (source slots), count +50h, cursor +54h; Accept calls StartNextGeneration(scene[+10h], scene[+38h + 4*scene[+54h]]) and deactivates every other household slot |

**On the owner's description sentence.** The patch description carries, as the owner wrote it:
"Virtual Families 2 can natively support up to 30 villagers per generation; any more will start
overwriting Family Tree entries and glitch the game." The disassembly agrees that the household is
30 villager slots. It does not show a 30-villager point at which Family Tree entries are overwritten:
the Family Tree record holds 2 parents + **6** children per generation, and a 7th child written into
it would overwrite the next generation's record (that is the stock refusal at count 6). Past 30
villagers the game does not overwrite anything: `FindEmptySlot` returns -1 and no villager is
spawned. This difference is reported to the owner, who decides whether to change the wording.

## 2. What the patch does

Executable (generator, every variant, all dormant while `.vf2kids` is 0):

- `.vf2kids`: one byte, 0 as built (the exporter's exact-SHA toggle sets it to 1).
- `.vf2kidt`: a 100-byte table (magic 'V2KT', version 1, count, 22 household slots) the DLL keeps
  current with the living extra children.
- The Time Controls loader wrapper on theGame::Init's first call also loads
  `Virtual Families 2 Patcher Files\vf2kids_b200.dll` when the byte is 1, after the Time Controls DLL,
  once, and calls `B200Kids_Startup`.
- `VF2IsBehaviorSixChildPrivateTimeMarriage` (Behavior Patches: a couple whose family is full takes
  the romantic route with no pregnancy) asks `FamilyTree.EmptyOffspringSlots() <= 0` instead of
  reading `+1B4h >= 6`. Stock that is `6 - +1B4h <= 0`, the same test; with the DLL it is the 28 limit.
  Without this, a Behavior Patches couple would stop having babies at six.
- `VF2IsCurrentGenerationChild` (the same-sex marriage pair fallback: "a recorded child is not the
  spouse") also answers true for a slot in the table, so an adult 7th-28th child is not taken for a
  spouse. False whenever the byte is 0.

The DLL (`runtime/native/b200kids/b200kids.cpp`, one feature): eleven entry hooks, each a 5-byte jmp.
Wrapped functions run their own first whole, position-independent instructions in a trampoline
(the prover checks there is no relocated field, no branch, no absolute operand and no branch target
inside the stolen run):

| Hook | What it does |
|---|---|
| EmptyOffspringSlots (replaced) | min(28 - children recorded this generation (stock count + every extra entry, living or not, as the stock count also keeps the dead), free household slots (inactive, not reserved for a baby on the way)). |
| AddOffspring | stock below 6; at 6 the child becomes an extra entry (slot, gender, name, head, body, age) and the stock record is never written. An older living entry for the same slot is marked gone (never two living entries for one slot). Refuses past 22 extras. |
| CountSurvivingChildren | stock + living extra children that are active (the stock test). |
| ReportDeath | marks the extra child dead first, then the stock function (which recounts survivors through the hook, so the "can start the next generation" flag stays set while extras live). |
| ChangeName | follows a rename (the Details screen calls it before copying the new name into the villager; the old name stays acceptable). |
| Reset | clears the extras (LoadState, Evict Family). |
| StartNextGeneration | a new generation (or new family) starts with no extras. |
| CreateNextGenerationCandidates / GetNextCandidate | stock when no extra child exists. Otherwise every child (stock order, then extras) is a candidate, cloned as an adult one at a time; the stock arrays hold only the candidate on show, at index 0 (count 1, cursor 0), so the stock Accept code is used unchanged. The clone takes a free slot (stock `ClonePeepAsAdult`); when there is none (2 parents + 28 children) or the only free slot is the child's own, the clone is made in the child's own slot from a copy of the child, which is put back byte for byte before the next candidate is shown and around any save. |
| theGameState::Save / Load | see section 3. |

A living extra child is identified by its household slot (the game's own index: a slot never moves),
its gender and its name; an entry whose slot now holds someone else is "gone" (it still counts toward
the 28, like a stock child whose record keeps counting). A child who is inactive but still in its slot
(a baby on the way) stays a child.

## 3. The sidecar

`<save folder>\Virtual Families 2 Patcher Data\Children\<save file>.dat`, beside the save file the
game itself writes (`ldwGameState::MakeGameStatePath`, the path the game saves to), one per save
file. Format (little-endian): `VF2KIDS\0`, version 1, game tag `VF2B200\0`, file size, the FNV-1a 64
of the save file it was written with and that file's size, the generation count, parent 1's slot and
gender, the entry count, 64-byte entries (slot, gender, state alive/dead/gone, head, body, age,
name[28]) and an FNV-1a 64 checksum of all of it.

- Written after every successful save of a family slot (1..5) that has extra children, atomically (a
  `.tmp` file, flushed, then a replace). Slot 0 (the settings file) never has one.
- The game keeps the previous save at slot + 20 (`ldwGameState::Save` removes slot + 20 and renames
  the save to it). The DLL does the same with the sidecars, so a restored backup has its own sidecar.
- After a load: the sidecar whose save-file hash matches the loaded file (this slot's, then the
  backup's) is used as is (dead and gone entries keep counting); otherwise a sidecar of the same family
  keeps only the children still found in their slots; another family's is ignored. A missing file is
  empty. An unreadable or foreign file is renamed `<name>.unreadable-N.dat` and never overwritten.
- The save file itself is never written by the DLL: the extra children are ordinary villagers in the
  30 slots the stock save already stores.

## 4. Evidence

Static (capstone + pefile), `runtime/tools/gen_b200_kids_sites.py`, `tests/test_b200_up_to_28_children.py`:

- 23 pins on the B200 core executable (whole functions; for Impregnate and theGameState::Load their
  whole head), each found exactly once (three found as the target of a pinned call), every derived address agreeing; resolved in all 32 B200 matrix variants,
  the B201 core executable and the core executable built from this branch.
- Every layout constant is an operand of the function that uses it (section 1), `CloneAsAdult` never
  writes the slot index, MakeGameStatePath formats `%s%d.ldw`.
- The retail executable has the same layout: six runs pinned exactly at fixed addresses (record size,
  six-child cap, current-record arithmetic, EmptyOffspringSlots, the twin / triplet rule and its
  EmptyOffspringSlots call, 30 saved villagers, the Family Tree save block).
- A damaged executable (any fixed byte of any pin), a wrong constant and a stolen run that ends inside
  an instruction are refused.

Emulated (unicorn, the REAL compiled DLL with the REAL game code, at the link address and relocated
by 0x1A0000; `tests/b200_kids_scenarios.py`): 28 children recorded (6 stock, 22 extra, the next
generation's record untouched), the 29th refused; the free-slot cap; deaths keep counting toward 28;
the stock flag survives the six stock children dying; renames and reused slots; single / twin /
triplet pregnancies at 26, 27 and 28 children through B200's real `CVillager::Impregnate` (and at 27
and 28 with free slots, so the 28 alone limits); the stock odds unchanged with room; Next Generation
offering every child, the stock six-or-fewer path unchanged, the full house (in-place clones, children
restored byte for byte, a save during the scene saving the child), Accept of a stock child (parent line
kept) and of an extra child (no line); the sidecar round trip, the backup, another save of the same
family, another family, an unreadable sidecar kept aside, nothing written without extras; the
executable's own loader end to end (byte off: never loaded; on: loaded after Time Controls, installs
only with the ini on, exactly the eleven jumps); the exporter's records driving the real loader; and
14 source mutations, each caught by a scenario.

## 5. Differences from the request, and what is not covered

- The heir chosen from the 7th-28th children has no line to a parent in the Family Tree (the tree never
  showed that child); a stock child heir keeps its line.
- The Family Tree appearance achievements B200 checks on recorded people ("Return of the Rainbow",
  "Spiky!") are not checked on children 7-28: they are not Family Tree records.
- A lost or deleted sidecar loses the extra children's status: they stay ordinary villagers in the
  house but can no longer be chosen in Next Generation, and the limit is counted from the stock six
  again (the free-slot cap still holds, so nothing overflows).
- No live test. The Next Generation scene's drawing of a candidate made in a child's own slot, the
  game's real `CloneAsAdult` (a seam in the emulation), real saves and loads, and Windows file
  behaviour are not exercised in a running game.
