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
- **Game Mechanics:** expanded. Every store item, upgrade and research has its own entry (#445, #446), and every line that was UNCONFIRMED is now settled, with the owner's weather names (#449). The Clear All Illnesses entry says what the cure clears and what it keeps. The Imported Candy entry says its cure skips a runny nose, which is how the stock game behaves.
- **The bundle** is exported from the newest `main` (with #449). The Game Mechanics files go only into the bundle, never into an executable.
- **Checks:** `tests/test_cure_keeps_food_groups_exe.py` runs the compiled cure and the game's own food-group count in every built executable. Only the illness fields change, and 4 food groups are still counted after the cure. The same test fails on the first B204 core, where 4 groups dropped to 0. No live test.
- **Full suite** with release-only tests, against this matrix: 2368 passed, 36 skipped. Six files failed in the parallel pass:
  - the Family Tree editor test passed when run alone;
  - two bundle tests read the newest bundle in `outputs\`, which was B203 while the old B204 was moved aside. With the new bundle exported, they passed: 58 passed;
  - two "generated files" tests are checkout-only. In a worktree that had just run the generator, they passed: 29 passed.
- **The release gate** on the new zip: **RELEASE GATE PASSED**, no features lost against 24 retained releases (B179 to B203).

## Updated in place (2026-10-27, second update): outfit pictures, R Refreshes the Store, All 36 Flea Market goods

Updated 27 October 2026 (second update): the Cure fix; each bought outfit keeps its own picture; R Refreshes the Store; the All 36 Flea Market goods setting, with all 36 always in stock when it is on; Game Mechanics: every item, every time says game time or real time, and the Hidden keys, clicks and cheats group. Patch Virtual Families 2 again after updating.

- **Cure fix (#448):** Clear All Illnesses keeps the four food groups (see the section above).
- **Outfit pictures (#454):** each bought outfit keeps its own picture. A new companion DLL, `vf2outfits_b200.dll`, ships with `vf2outfits.ini` and is loaded by the Fix Vanilla Game Bugs byte (`.vf2bugs`).
- **R Refreshes the Store (#455):** a new companion DLL, `vf2refresh_b200.dll`, loaded by a new `.vf2rfsh` byte. Pressing R refreshes the Store's stock.
- **All 36 Flea Market goods (#455, #456, #457):** a new setting (`.vf2flea` byte). While it is on, all 36 Flea Market goods are always in stock, and an owned one-off keeps its checkmark. The bundle now lists 41 settings.
- **Game Mechanics (#452, #453):** every item has its entry, every time says whether it is game time or real time, and a new group lists the Hidden keys, clicks and cheats.
- **Rebuilt:** all 32 executables, from `main` at `551b924` (#457), seeded from the B203 matrix; 32 distinct executables, none identical to the previous B204 build. New hashes in `docs/b204-matrix-manifest.md`, identities in `data/vf2/release-identities-B204.json`. `vf2outfits_b200.dll` (`0ff96da2...`) and `vf2refresh_b200.dll` (`10ae09db...`) are built from `551b924`. The other three companion DLLs are the same files as before (`vf2time_b200.dll` `3ea0a2a5...`, `vf2kids_b200.dll` `4a6bb5ff...`, `vf2history_b200.dll` `3c7181bc...`); their source has not changed.
- **No live test** of the outfit pictures, R Refreshes the Store or the All 36 Flea Market goods setting.

## Updated in place (2026-10-29): Family Tree Maker fixes from the Virtual Villagers patcher

Updated 29 October 2026: Family Tree Maker: a Relationships dropdown; same-name family members shown as two people; faster big trees; a retyped title keeps current counts. No exe or DLL changed; no need to patch again.

- **Relationships dropdown** in the Family Member Info tab (the Virtual Villagers patcher's v1.35.85, `src/vf2_relationships.py`): pick a kind of relative to list everyone of that kind by name; click a name to select them on the tree. Parents, children, full and half siblings, twins and triplets, grandparents and grandchildren of any generation, aunts, uncles, nieces, nephews, great-aunts, cousins of any degree and removal, half and double forms, partners (the other parent of a child), in-laws and step-relations. The dead and those no longer in the house are listed and marked. Read-only.
- **Two family members with the same name and look are two people**, each with their own edits on the tree (their key adds their seat in the save's Family Tree). Their ages, parents and numbers were already their own: in Virtual Families 2 every parent comes from the save's own Family Tree record, never from a name, so there is nothing to ask. An edit an earlier build made under the shared key is kept in the tree file but shown on neither.
- **Big trees are laid out several times faster**, with the same layout and lines to the byte (pinned against the code before, `tests/test_tree_big_speed.py`).
- **A retyped title line** keeps your words; its "family members known", "living" and date are refreshed each time the tree is made.
- Not ported, because Virtual Families 2 has no such thing: default or placeholder fathers (the game has none), the Village Matchmaker, Heathens, and the "Appearance changed" question's wording (the Virtual Families 2 tree never records an earlier look, so that question is never asked).
- **The bundle** is re-exported from the current B204 matrix (from `551b924`) with the same 32 executables and the same five companion DLLs; only the patcher's Python tools changed.
