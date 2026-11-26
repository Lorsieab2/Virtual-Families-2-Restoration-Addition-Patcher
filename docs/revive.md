# Revive (Virtual Families 2)

Status, 2026-11-26. Design: `C:\vf2w\revive-design.md` (the port of the Virtual Villagers patcher's Revive). The
owner's decisions are final and listed in `src/vf2_revive.py`. Age rule (owner correction, replaces "age 5"): a
family member who died at 18 or older returns at 18 (360 age units, the game's own 18-year mark, the value "Set
Age to 18" writes); one who died at 17 or younger returns at the age they died at.

## Built (patcher side; no executable or DLL change)

* **The snapshot file**, one per save file, never a save field:
  `<save folder>\Virtual Families 2 Patcher Data\Revive\Virtual Families 2<N>.ldw.dat` (N and N + 20). Header as the
  Children / Outfits files (magic `VF2REVIV`, version 1, `VF2B200\0`, file size, the save's FNV-1a 64 and size at
  +24 / +32, count at +48, entries, FNV-1a 64 trailer), so `vf2_copy_slot.sidecar_rekeys` re-keys it for Copy,
  Move, Rename Family, Game Speed and Back Up exactly as it does the Children file, and one-slot Restore takes it.
  Each entry (3,504 bytes) holds who they were (name, whole name, sex, head, body, parents and their looks,
  first-name index), likes and dislikes (the record's lists and the tree's text), career and level, fertility,
  procreation desire, age and cause at death, role and generation, the generation's heir (to tell this family from
  an evicted or later one), the whole 0x7BC-byte villager record when a source has it, the source, and a mark per
  field: 0 unknown, 1 inferred, 2 exact.
* **The backfill** (`vf2_revive.backfill`, Tools tab: **Revive Records...**). The current generation's dead are the
  tree entries `ReportDeath` set to slot -1, the Children file's dead (children 7..28) and the log's Death records of
  the generation (a childless spouse the tree no longer holds). Sources, in the owner's order: their dead record
  in this save (exact); the game's other save of the slot and the Backups (a dead record: exact; a record from
  while they lived: identity exact, the rest inferred, "as when saved"); the tree entry (name, looks, career,
  likes/dislikes text: exact); the log (age in whole years: inferred, but a death at 18+ still gives exactly 18;
  cause: exact) and the Names file (whole name). Field by field the better mark wins, then the better source; a
  snapshot captured at the death (source 1, the in-game half) is never changed. Idempotent (a second run writes
  nothing; pinned). Backups are repaired while the game runs; the live saves of a running game wait (and so do they
  when it cannot be told whether the game runs). Saves, logs and Names files are only read (pinned).
* **The rules the purchase will use**: `refusal` (alive at home, away from home, divorced, another generation or
  family, a not-exactly-known identity, a full house) and `return_role` (a spouse whose partner remarried returns
  as a family member; one whose place is still empty, as the spouse).
* **The price**: `REVIVE_PRICE = 10_000` (proposed; the patcher's own big Special Upgrades, Brokerage Account,
  Food Club and Health Plan, are $10,000 each; Adoption Services is $4,000). The owner confirms it before release.

## Not built: the in-game half

1. **Capture at every death and rotation with the save.** Needs a companion DLL (`vf2revive_b200.dll`) hooking the
   death (`ReportDeath`, as b200history does) and `theGameState::Save` (as b200kids rotates the Children file).
   A new DLL needs a new dormant loader byte in the executable: **an executable change, so a 32-variant matrix
   rebuild at release.** (Folding it into `vf2history_b200.dll` avoids the rebuild but ties it to the Family History
   setting and breaks "one feature, one DLL"; owner's call.)
2. **The Special Upgrades row.** Store rows, their prices and the purchase dispatch (`HandleUpgrade`) are compiled
   into the executable (`work/patch_mobile_furniture_pack.py`); the Cheat Upgrades rows are all $0 there. A priced
   row is an executable change (matrix rebuild). No DLL-side store row exists to reuse; faking one from a DLL is
   less safe than a generated row.
3. **Choosing who to revive in the game.** The store has no person picker. The simplest native option is the
   game's own `theMessageBoxDlg` (used by the patcher's Adoption Services choice), one person at a time with
   "Revive" / "Next". New in-game UI needs the owner's approval first.

### What cannot be proved safe yet (stop point)

* Writing a snapshot over a villager the game's creator just made (`VillagerManager.SpawnSpecificPeep`, as the
  Adoption Services choice uses): which fields the game derives once at creation (sprites from head/body, the like
  lists' structure, UNCONFIRMED in `docs/vf2-save-format.md`; the AI values) needs `CVillager::LoadState` / `Init`
  traced and emulated on the B209 executable and every matrix variant.
* Re-pointing the dead child's slot -1 tree entry at the new slot instead of `AddOffspring` (which would add a
  second entry and count against 6): `ReportDeath`, `FindPeepRecord`, `CountSurvivingChildren`,
  `CanStartNextGeneration` and the next-generation notice must agree; and the Up to 28 Children file for children
  7..28.
* Where a spouse who returns "as a family member" sits in the tree: the record has only parent 1, parent 2 and
  children. Owner decision needed (a child entry; or no tree entry, like a villager the tree does not hold).

Options: (a) build 1-3 as an executable + DLL change, after the traces above, with a matrix rebuild and the
owner's live check; (b) a Tools-tab revive on a closed game's save (no money, no in-game UI; against D8); (c) keep
only the records for now.

## Live checks (owner)

* Tools > Revive Records... on a save folder with a family member who died: the result lists them with the age they
  would return at; the save, logs and Names file are unchanged; running it again says "already recorded".
* With the game running: the result says the live saves wait; the backups are recorded.
* Copy Player Slot / Rename Family / Game Speed / Back Up on that slot: the Revive file goes with it (still read
  as describing the save: Revive Records says "already recorded" afterwards).
