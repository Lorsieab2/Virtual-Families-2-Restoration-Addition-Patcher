# Revive (Virtual Families 2)

Status, 2026-11-26. The owner's decisions are final: the same person returns (name with the Names file's whole
name, sex, head/body, likes/dislikes); **age**: someone who died younger than 20 returns at the age they died (18 and
19 too); someone who died at 20 or older, or whose age at death is not known, returns at **20** (400 age units, the
game's own 20-year mark) **with their career, level and salary at death**; only the dead; money, in game, in Special
Upgrades, **$25,000**, free with Free and Guaranteed Cheats; a dead spouse whose partner remarried **takes no place in
the Family Tree's records** (no child count, heir, Next Generation or Up to 28 Children change) and lives in the house
as a family member; fertility and "Wants kids?" restored, moods and needs fresh; current generation only; snapshots in
a per-save sidecar, taken at every death; a "Revived" record in the Family History. Setting **Revive**: on by default
and in Owner's Defaults (it costs money).

A grown-up revived at 20 with no career needs no special handling: the game sends a child to college only when the
age CROSSES 380 units with no career (`AllVillagersTimeflowUpkeep` +1C4h: the old age below 17Ch and the new one at
or above it), which a revival at 400 never does; and no career test gates a baby (the `CareerType` callers are the
career-room drops, the details screen, the diagnosis and the AI, not `TryToMakeBaby`).

## The pieces

| Piece | Where | What |
|---|---|---|
| Snapshot file | `<save folder>\Virtual Families 2 Patcher Data\Revive\<save file>.dat` | `src/vf2_revive.py` format (header as the Children / Outfits files, keyed to the save's FNV-1a 64 + size); Copy / Move / Rename / Game Speed / Back Up / Restore carry and re-key it. |
| Backfill | Tools tab, **Revive Records...** (`vf2_revive.backfill`) | People who died before the patch: read-only sources in the owner's order, marks, idempotent, backups repaired while the game runs. |
| Companion DLL | `runtime/native/b200revive/b200revive.cpp` -> `vf2revive_b200.dll` (+ `vf2revive.ini`, Revive=1) | Capture at death, the file beside the save (rotated with N -> N+20 after `theGameState::Save`, read after `Load`, a damaged file set aside), the candidate list, the log record. **No game address, no code patching, no executable buffer**: everything comes from the executable's host table; its only writes into the game are theGameState vtable slots 13 / 14 (data, PAGE_READWRITE, the old protection put back), chained like the Time Controls and Outfit Pictures DLLs. |
| Executable | `work/patch_mobile_furniture_pack.py` (`REVIVE_*`, `patch_revive_death_capture`, `patch_revive_manifest`) | `.vf2rviv` byte (0 as built) and the loader (last, after Translations); the host table; two caves in `VillagerState.obj`: `CVillagerState::SetHealth` / `AdjustHealth` call `VF2ReviveOnDeath(this)` on the path that stores a cause of death; the Special Upgrades row 0x15C (the Health Plan's own icon, two new string-table records), listed only while the DLL runs; the purchase rides `VF2RemoveOwnedUpgrade`, the first helper `HandlePurchaseItem` already calls (**no byte of HandlePurchaseItem changes**). |
| Patcher | `work/export_offline_patch_bundle.py` (`revive`), `work/export_release_bundle.py` (`--revive-dll`) | The setting, the byte, the DLL and its ini. |

**This is an executable change: the 32-variant matrix is rebuilt at release.**

## What the trace proved (desktop objects, B209)

* `CVillagerManager::SpawnSpecificPeep`'s three arguments are (name seed, gender, AGE): `CVillager::Init` stores the
  third as the bio age (-1 = a random 0..29 units) and hands the first to `SetRandomName`; the store's own Adoption
  Services calls it with (1, -1, 60h). Init writes head (+6A80h) and body (+6A84h) as plain fields, the name by
  `SetRandomName`, the likes by `CLikeList::Initialize`, the state by `Reset(age)`; nothing is derived from them later
  (the anim control is reset, sprites are read at draw time). `CVillagerManager::LoadState` is `Reset` +
  `CVillager::LoadState` per slot, and `CVillager::LoadState` is a copy of bio, state, skills, the 12-byte like /
  dislike lists and `LoadAI`. So a revival is the game's own creator followed by the subset of LoadState's copies that
  is the person (who they are, looks, parents, skills, likes, dislikes, fertility, procreation desire); age, health,
  moods, needs, plans and the AI values stay as Init made them. With only the tree's career, the salary is the game's
  own (`CVillagerSkills::UpdateSalary`).
* The same mistake was in the generated Adoption Services chooser (`VF2AdoptRandomChildChoice`, the age passed first
  and -1 third); that chooser is not installed (its route was reverted after a crash), so it is corrected in the code
  only. Its revert note also says the crash was never pinned down and names, among the suspects, a theMessageBoxDlg
  built on the stack in generated code -- the pattern the Revive box uses (as the Bathroom 2 notice does). The real
  dialog fits in about 8Ch bytes (HandlePurchaseItem's own frame); the generated buffer is 300h. Live check 2 below
  is the proof that matters.
* `CFamilyTree::ReportDeath`: a parent with children -> its slot -1, Next Generation possible (+1) and its notice
  (+2); a child -> its slot -1, and +1 cleared when no child survives; a childless spouse -> the entry freed; a
  childless heir -> the spouse copied over parent 1. `CountSurvivingChildren` counts the entries whose villager is
  active; `FindPeepRecord` matches by slot, sex and head. So a revived child's own entry is pointed at the new slot
  (no second entry, the six are not used up), and `UpdatePeepRecord` refreshes its career and likes text. Emulated
  on all 32 B209 matrix executables and this branch's build (`tests/test_b200_revive.py`).
* Placement: own entry (slot -1) re-pointed; a child not in the six -> a new child entry (`AddOffspring`; Up to 28
  Children takes 7..28); a spouse whose place is empty -> that place; a spouse whose partner remarried -> no place (a
  household villager the tree does not hold, as the game already allows). A childless heir (whose entry the spouse
  took) is not offered. Next Generation: a revival only ever makes it possible again (a child back after every child
  died, a parent still dead); it never takes it away.
* `SetHealth` / `AdjustHealth` are pinned by no companion DLL; every other DLL's pins were re-proved on this
  branch's builds (history 44, kids 19, outfits 23, refresh 27, time 31, titlebox 30, translations 12 sites).

## Not built yet (the owner's latest request)

* Drawing a remarried partner's revived spouse on the game's own Family Tree screen, under the current spouse, with
  the game's portrait and font, and clicking them as a tree person. The screen is `CFamilyTreeScene` (`DrawScene` ->
  `DrawFamily(gen, x, y)` -> `DrawParent` / `DrawChild` -> `DrawPeep(point, head, body, sex, scale, ...)`; clicks in
  `CheckForPeepHit` / `CheckForFamilyPeepHit`); no companion DLL pins it. The plan: the executable passes the scene's
  vtable and its drawing calls in the host table, the DLL keeps the list of these family members in the snapshot file
  and draws them where `DrawFamily` places the current generation's second parent, one row down. Not proved or built
  in this change: that point inside `DrawFamily` (its scroll and scale) must be traced and emulated first.

## Known limits

* The Family History DLL forgets a death it logged only at the next load: a revived person who dies again in the same
  session in the same household slot may get no second Death record until then.
* The log record names the person by the name the save stores (the Family Tree Maker makes it whole from the Names
  file); the newest log file gets it even past 2000 records.

## Live checks (owner)

1. Revive on: Special Upgrades lists **Revive a Family Member** at $25,000 (free with Free and Guaranteed Cheats;
   2x / 5x / 100x prices apply). Revive off: no row.
2. A family member dies (any cause): buy the row. The box shows them with the age they return at; **Revive** brings
   them back: same name (and whole long name), looks, likes; moods fresh; anyone 20 or older at death at 20 with
   their career, level and salary; anyone younger at the age they died. **Next** goes on; after the last, nothing
   chosen -> the money comes back.
3. The revived child is in the Family Tree in their old place (not a second entry); Next Generation still behaves.
4. A spouse dies childless, the partner remarries, the spouse is revived: they live in the house; the Family Tree's
   children, Next Generation and the child count are unchanged (they are not drawn on the tree yet).
5. Save, quit, reload: the revived person is there; the snapshot list no longer offers them.
6. The Family History log (if on) gets `Arrived` with `How: Revived (Revive a Family Member)`.
7. Not offered: someone alive, away at college / Boarding School / Talent Scout, divorced, or of an earlier
   generation or an evicted family.
8. Tools > Revive Records on a folder with old deaths; then those people are offered in game.
