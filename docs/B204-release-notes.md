# VF2 B204 release notes

**The patcher bundle.** Built from `main` at `412660f` (PR #438, Family Tree Maker), seeded from the B203 matrix.

B204 adds one setting, the **Family History log** (Experimental, off by default), to the 38 of B203: 39 in all. The 32 executable variants are the same feature combinations as B203, rebuilt because every executable now carries the log's dormant loader.

## Family Tree Maker (#438)

On the Tools tab, it draws a family's tree from its save: every generation's parents and children, each with their face from the game.
- **It remembers people.** The save forgets a divorced spouse, a spouse replaced by a new marriage, and a parent who died without children. The tree's own file beside the save keeps everyone it has ever seen, along with your edits.
- **Labels under each portrait**, each one you can untick:
  - Husband 1 / Wife 1, Husband 2 / Wife 2…, worded by each spouse's own sex (same-sex couples work the same way);
  - Remarried, Divorced, Deceased with the cause, Adopted;
  - the Random Event that brought them in or took them away (e.g. "Popup Event: The Little Visitor");
  - Career, in the game's own words (e.g. "Novice Engineer"), and Runner.
- **Looks:** 16 new backgrounds and 4 logo stickers (Virtual Families, Virtual Families 2, Fish Tycoon, Plant Tycoon), in the Virtual Villagers patcher's tree style. It exports as a PNG or JPG.

## Family History log (#437, Experimental, off by default)

A companion DLL, `vf2history_b200.dll`, writes one Family History log per family as you play, in the Virtual Villagers patcher's record format. Every person is written with their name, age, sex, head and body. The executable loads the DLL only while the setting is on. **Enable All leaves it off.**

It logs:
- pregnancies and births: single, twins, triplets;
- deaths with the game's cause;
- marriages, remarriages and divorces, including same-sex marriages through the patcher's option;
- children who arrive (The Little Visitor, Adoption Services) or leave home (college, Boarding School, The Talent Scout);
- new generations, renames, Evict Family, Start Over and Family Renamed;
- every Random Event, as an Email Event or a Popup Event, with the choice made.

A family started before the patch gets its earlier generations added once from its tree, marked "backfilled, no date". The Family Tree Maker reads this log to fill in what the save forgets.

## Also in B204
- **Random Events.** The game's events are now called "Random Events" everywhere, each an **Email Event** or a **Popup Event** (#436). The mobile events setting is now **Add mobile-exclusive Random Events**.
- **Fonts.** The Game Mechanics and How to Use pages use the same fonts as the Virtual Families 1 patcher (#435).

## Checks

- All 32 variants built from the commit above, 32 distinct executables. Hashes are in `docs/b204-matrix-manifest.md`, identities in `data/vf2/release-identities-B204.json`.
- The Family History log's 42 hook sites resolve in every executable. Every hook was emulated from its live caller, and the loader was tested in the built B204 core executable.
- Full test suite with release-only tests, against this matrix: 2265 passed, 36 skipped. Four test files failed first, none from the shipped code: two checked the README's setting counts (updated for the new setting, then 33 passed), and two said this checkout's generated build files were older than the generator, which #437 changed; at the same commit, in a worktree that had just run the generator, they passed (29 passed). The Family History tests ran in full, 160 passed, including the loader end to end in the built B204 executable.
- The bundle reproduces the build on a clean install and passed the release gate: **RELEASE GATE PASSED**, with no features lost against 24 retained releases (B179 to B203).
- **No live test** of the Family History log or the Family Tree Maker has been done.
- Asset: `VF2-B204-Release.zip`, 163,944,648 bytes, SHA-256 `082cb1291eb7212517680a2c891fbe6631cb4d768399192417e6070fa29e785e`.

## Updated in place (2026-10-26)

The bundle was re-exported from `main` at `f0911bd` (PR #440) from the same 32 executables and the same three DLLs (identities unchanged), and passed the release gate again (no features lost against 24 retained releases). The full suite: 2274 passed, 37 skipped; the only failures were the same two checkout-only "generated files older than the generator" tests as above (the generator has not changed since `412660f`, where they passed). Only the patcher's own tools changed, to work like the Virtual Villagers patcher's tools:

- **Tools tab:** one box named for the game, with the save folders it found and a row of links, each with its "?". "Family slot N" now reads "Save N".
- **Rename Family and Game Speed:** now use the Virtual Villagers patcher's Rename Tribe form: save folder, family list, a name box with a character counter, and the window stays open. Restore Saves scrolls.
- **Back Up Saves:** like the Virtual Villagers patcher, it now sets the backed-up copy's game speed to Paused. A restored backup opens paused and never catches up on the time since it was made. Your own saves are never changed.
- **Family Tree Maker fix:** it opened the last save folder in the list instead of the one chosen.
- Every patcher window can be minimized and maximized.
- The first B204 zip (SHA-256 `7c0f9eec...`) is replaced.

## Updated in place (2026-10-27): Clear All Illnesses keeps the food groups

Updated 27 October 2026: Cure no longer resets a family member's food groups (all 32 builds rebuilt). Patch Virtual Families 2 again after updating.

- **The bug:** the Cheat Upgrade **Clear All Illnesses** also zeroed the four food groups (Grains, Dairy, Meat and the fourth) of everyone it cured. Their flags and 24-hour timers sit right after the illness fields, and the cure took them for infections. A cured family had no food groups until the next grocery bag or Food Club delivery, which counts against old age, illness, health and happiness.
- **The fix (#448):** the cure now clears only what the game's own cures clear: each symptom and its timer, and the mild and serious infections. Health, food groups and everything else are kept.
- **Rebuilt:** all 32 executables, from `main` at `e0bb126` (#448), seeded from the B203 matrix; 32 distinct executables, new hashes in `docs/b204-matrix-manifest.md`, identities in `data/vf2/release-identities-B204.json`. The three companion DLLs are the same files as before (`vf2time_b200.dll` `3ea0a2a5...`, `vf2kids_b200.dll` `4a6bb5ff...`, `vf2history_b200.dll` `3c7181bc...`).
- **Game Mechanics:** the Clear All Illnesses entry now says what the cure clears and what it keeps. The Imported Candy entry now says its cure skips a runny nose, which is how the stock game behaves.
- **Checks:** `tests/test_cure_keeps_food_groups_exe.py` runs the compiled cure and the game's own food-group count in every built executable. Only the illness fields change, and 4 food groups are still counted after the cure. The same test fails on the first B204 core, where 4 groups dropped to 0. No live test.
