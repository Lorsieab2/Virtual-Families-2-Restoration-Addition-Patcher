# VF2 B203 release notes

**The patcher bundle.** The executables are built from `main` at `471f6f5` (PR #430, Game Mechanics), seeded from the B202 matrix; the bundle was re-exported from `main` at `215e349` (PR #433), see "Updated in place" below.

B203 changes no game code and no setting: the 38 settings of B202 are unchanged, and the 32 executable variants are the same feature combinations, rebuilt from this commit. What is new is the patcher's **Tools** tab.

## The Tools tab

- **Back Up Saves / Restore Saves** (#427). One click copies your save folder into a dated backup beside your saves. A running game is paused for the copy, then carries on.
  - Restore puts back a whole backup, or just one family's own files. The game must be closed. Your saves as they are now are backed up first, so a restore can be undone.
  - Every file is checked after it is copied, and if anything fails, everything goes back as it was.
- **Rename Family** (#428). Virtual Families 2 has no family surname: a family is shown under the player name typed at its start, on the slot menu, as "Player:" on the main menu, in Change Player and in the daily e-mail. Rename changes that name in the save, its slot-menu entry and its previous-save copy.
  - Up to 19 characters, the most the game keeps.
  - The game must be closed, and your saves are backed up first, as "(before rename)".
- **Game Speed** (#429). Sets a closed game's family to **Paused** or **Normal**, the only speeds the game saves.
  - It writes exactly what the game's own Pause writes, or what loading the family and pressing unpause would; the paused time is never counted as ageing.
  - It refuses a running game, a speed it does not recognise, a PC clock earlier than the save, and a family member whose body the game would have taken away meanwhile.
  - Your saves are backed up first, as "(before speed change)".
- **Game Mechanics** (#430). A read-only page on how Virtual Families 2 works underneath, worked out from the game's own code. It covers:
  - time and ageing, including time away while the game is closed: in full up to 31,000 seconds; 31,000 seconds up to 24 hours; 24 hours beyond;
  - needs, health, sickness, old age, pregnancy;
  - all 132 careers with pay per real hour;
  - money and interest, leaving home, dating and marriage;
  - every island event, weather, messes, malfunctions, collectibles, and the Flea Market and On Sale.

  Every line says what stands behind it: VERIFIED-E (the game's own code run, exact odds), VERIFIED-C (read on a path the running game takes) or UNCONFIRMED. It opens no save or game file.
- **How to Use** and a "?" beside every tool.

## Checks

- All 32 variants built from the commit above, 32 distinct executables; hashes in `docs/b203-matrix-manifest.md`, identities in `data/vf2/release-identities-B203.json`.
- Full test suite with release-only tests, against this matrix: 2071 passed, 31 skipped, 0 failed (on `215e349`).
- The bundle reproduces the build on a clean install (8194 of 8194 files) and passed the release gate: **RELEASE GATE PASSED**, no features lost against 23 retained releases (B179 to B202). The two companion DLLs are the B202 files themselves (`runtime/` unchanged).
- **No live test** of the new tools has been done.
- Asset: `VF2-B203-Release.zip`, 146,882,710 bytes, SHA-256 `c70371d6aea4ef59a58213b317f68850133532b229a0b7c6d9966c30b26f599b`.

## Updated in place (2026-10-25)

The bundle was re-exported from `main` at `215e349` on the same day, from the same 32 executables and the same two DLLs (identities unchanged), and passed the release gate again. Only the patcher's own files changed:

- **Game Mechanics** now gives the unpatched game's behaviour wherever it differs from the game with the patcher. Only two facts do, each emulated in the stock exe:
  - The Flea Market: unpatched, 5 of its 36 goods, re-picked after 6 real hours; with the patcher, all 36 always.
  - The Special Upgrades page: 6 items unpatched, 10 with the patcher.
- **Autosave:** the game saves by itself every 2 minutes (real time, also while paused) as well as when you quit. The Back Up, Restore, Rename Family and Game Speed texts used to say it saved only on quit; the Game Mechanics page now lists the autosave.
- The first B203 zip (SHA-256 `63ca18fc...`) is replaced.
