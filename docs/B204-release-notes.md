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
- Full test suite with release-only tests, against this matrix: 2265 passed, 36 skipped. Five test files failed first, none from the shipped code: three checked the README's setting counts (updated for the new setting, then 33 passed), and two said this checkout's generated build files were older than the generator, which #437 changed; at the same commit, in a worktree that had just run the generator, they passed (29 passed). The Family History tests ran in full, 160 passed, including the loader end to end in the built B204 executable.
- The bundle reproduces the build on a clean install and passed the release gate: **RELEASE GATE PASSED**, with no features lost against 24 retained releases (B179 to B203).
- **No live test** of the Family History log or the Family Tree Maker has been done.
- Asset: `VF2-B204-Release.zip`, 163,938,534 bytes, SHA-256 `7c0f9eec9dbf18417f7a7da6eddb12c07eb2e41e99d444abcbefa9f60e7b3b1f`.
