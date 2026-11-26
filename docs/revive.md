# Revive (Virtual Families 2)

Status, 2026-11-26. The owner's decisions are final: the same person returns (name with the Names file's whole
name, sex, head/body, likes/dislikes, career); age 18 for a death at 18 or older (360 age units, the game's own
18-year mark, the value "Set Age to 18" writes), else the age at death; only the dead; money, in game, in Special
Upgrades, **$25,000**, free with Free and Guaranteed Cheats; a dead spouse whose partner remarried returns as a
**child entry** of the Family Tree; fertility and "Wants kids?" restored, moods and needs fresh; current generation
only; snapshots in a per-save sidecar, taken at every death; a "Revived" record in the Family History. Setting
**Revive**: on by default and in Owner's Defaults (it costs money).

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

* `CVillagerManager::SpawnSpecificPeep(age, gender, -1)` = `FindEmptySlot` + `CVillager::Init`. Init writes head
  (+6A80h) and body (+6A84h) as plain fields, the name by `SetRandomName`, the likes by `CLikeList::Initialize`,
  the state by `Reset(age)`; nothing is derived from them later (the anim control is reset, sprites are read at draw
  time). `CVillagerManager::LoadState` is `Reset` + `CVillager::LoadState` per slot, and `CVillager::LoadState` is a
  copy of bio, state, skills, the 12-byte like / dislike lists and `LoadAI`. So a revival is the game's own creator
  followed by the subset of LoadState's copies that is the person (who they are, looks, parents, skills, likes,
  dislikes, fertility, procreation desire); age, health, moods, needs, plans and the AI values stay as Init made them.
* `CFamilyTree::ReportDeath`: a parent with children -> its slot -1, Next Generation possible (+1) and its notice
  (+2); a child -> its slot -1, and +1 cleared when no child survives; a childless spouse -> the entry freed; a
  childless heir -> the spouse copied over parent 1. `CountSurvivingChildren` counts the entries whose villager is
  active; `FindPeepRecord` matches by slot, sex and head. So a revived child's own entry is pointed at the new slot
  (no second entry, the six are not used up), and `UpdatePeepRecord` refreshes its career and likes text. Emulated
  on all 32 B209 matrix executables and this branch's build (`tests/test_b200_revive.py`).
* Placement: own entry (slot -1) re-pointed; a spouse whose partner remarried, or a child not in the six -> a new child
  entry (`AddOffspring`; Up to 28 Children takes 7..28); a spouse whose place is empty -> that place. A childless heir
  (whose entry the spouse took) is not offered. Next Generation: a revival only ever makes it possible again (a child
  back after every child died, a parent still dead); it never takes it away.
* `SetHealth` / `AdjustHealth` are pinned by no companion DLL; every other DLL's pins were re-proved on this
  branch's build (history 44, kids 19, outfits 23, refresh 27, time 31, titlebox 30, translations 12 sites).

## Known limits

* The Family History DLL forgets a death it logged only at the next load: a revived person who dies again in the same
  session in the same household slot may get no second Death record until then.
* The log record names the person by the name the save stores (the Family Tree Maker makes it whole from the Names
  file); the newest log file gets it even past 2000 records.

## Live checks (owner)

1. Revive on: Special Upgrades lists **Revive a Family Member** at $25,000 (free with Free and Guaranteed Cheats;
   2x / 5x / 100x prices apply). Revive off: no row.
2. A family member dies (any cause): buy the row. The box shows them with the age they return at; **Revive** brings
   them back: same name (and whole long name), looks, likes, career; moods fresh; adults at 18, a child at the age
   they died. **Next** goes on; after the last, nothing chosen -> the money comes back.
3. The revived child is in the Family Tree in their old place (not a second entry); Next Generation still behaves.
4. A spouse dies childless, the partner remarries, the spouse is revived: they join as a child of the tree.
5. Save, quit, reload: the revived person is there; the snapshot list no longer offers them.
6. The Family History log (if on) gets `Arrived` with `How: Revived (Revive a Family Member)`.
7. Not offered: someone alive, away at college / Boarding School / Talent Scout, divorced, or of an earlier
   generation or an evicted family.
8. Tools > Revive Records on a folder with old deaths; then those people are offered in game.
