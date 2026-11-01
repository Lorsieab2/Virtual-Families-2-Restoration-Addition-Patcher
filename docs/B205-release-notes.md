# VF2 B205 release notes

**The patcher bundle.** Built from `main` at `61624b1` (PR #465), seeded from the B204 matrix. B205 is a new version, not an in-place update of B204: it carries everything B204 had, plus the changes below.

B205 offers the same 41 settings as the final B204 rebuild. The 32 executable variants are the same feature combinations, all rebuilt because the two website fixes below go into every executable (inside Fix Vanilla Game Bugs; no new DLL and no new setting byte).

**B205 saves to its own folder**, `Documents\LDW\Virtual Families 2 - Modded B205`, because Virtual Families 2 names its save folder after the executable. See "Keeping your B204 families" below.

## Tools

- **Copy Player Slot** (#460, #464). Copies a family into another save slot of the same save folder, under a new name, with every file kept for that slot: the save and the game's previous save, the Up to 28 Children and outfit pictures files, the Family History log and the Family Tree Maker's files.
  - A slot with no save is empty, whatever the player list says.
  - Any slot but the source can be the target. Replacing a family asks first with a warning that names both families; No is the default.
  - The whole save folder is backed up first, as `Backup <date> (before copy)`. A replaced family's files are moved to `Backups\Replaced by copy <date> - Save <N> - <name>`, and a deleted family's leftovers are set aside. Nothing is ever deleted.
  - It refuses while the game runs, and puts everything back if any step fails.
- **Picture Maker** (#461). Draws family members exactly as the game draws them and saves them as PNGs with a clear background: from your save (at home, left home, died, earlier generations, and the outfits in the tool tray) or made your own (both sexes, every age, all heads and outfits). Checked against the game's own drawing code.
- **The Children and Outfits files stay matched to their save** (#462). Rename Family, Game Speed and Back Up Saves change a save's bytes; they now re-key that slot's Up to 28 Children and outfit pictures files to the changed save, so the extra children (including those who left home or died) and each outfit's picture survive the next load. Restoring one slot now also restores its Outfits files, its previous-save files and its Family History and Family Tree files.

## Fixes (Fix Vanilla Game Bugs, in every executable)

- **Startup crash from LDW's website** (#463). At every start the game asks LDW's server to log in. The server now answers with its program code (about 3 KB) instead of a reply, and the stock game reads it into a 2 KB space and crashes about 20 seconds in. The fix reads at most what fits and ignores a reply that is cut short or is a web page, so the game carries on as if the server had not answered.
- **A long server error message** (#465). The game copied an error message from the server into a fixed-size space with no limit; a message over about 220 characters would crash it. The fix cuts the message to fit. The server sends no such message today.

## Carried from B204

Everything B204 had over B203 is in B205:
- the Family History log, on by default;
- the Cure fix (Clear All Illnesses keeps the food groups);
- each bought outfit keeps its own picture;
- R Refreshes the Store and the All 36 Flea Market goods setting;
- Game Mechanics expanded, with every hidden key, click and cheat;
- the Family Tree Maker and its fixes (Relationships dropdown, same-name family members, faster big trees).

## Keeping your B204 families

Copy everything in `Documents\LDW\Virtual Families 2 - Modded B204` except the `Backups` folder into `Documents\LDW\Virtual Families 2 - Modded B205`, including both `Virtual Families 2 Patcher Data` and `Virtual Families 2 Patcher`.

## Checks

- All 32 variants built from `61624b1`, 32 distinct executables; hashes in `docs/b205-matrix-manifest.md`, identities in `data/vf2/release-identities-B205.json`. (Part m1 was rerun alone after the known shared link-response-file race; its first attempt is set aside, never used.)
- The five companion DLLs are the published B204 files, taken from the B204 zip unchanged: `vf2time_b200.dll` `3ea0a2a5...`, `vf2kids_b200.dll` `4a6bb5ff...`, `vf2history_b200.dll` `3c7181bc...`, `vf2outfits_b200.dll` `0ff96da2...`, `vf2refresh_b200.dll` `10ae09db...`. `runtime/` has not changed since B204.
- The bundle reproduces the build on a clean install (8194 of 8194 files) and passed the release gate: **RELEASE GATE PASSED**, no features lost against 25 retained releases (B179 to B204).
- Full test suite with release-only tests, against this matrix (20 workers): 2779 passed, 36 skipped. The only failures were the two checkout-only files `work/test_generated_cpp_compiles.py` and `work/test_transparent_furniture_drop.py`, which said this checkout's generated files are older than the generator; in a worktree of the same commit that had just run the generator they passed (29 passed, 3 skipped). `tests/test_server_reply_guard.py` (19) and `tests/test_server_error_text.py` (16) ran against all 32 executables and passed.
- A default apply of the zip onto a clean game folder made `Virtual Families 2 - Modded B205.exe` with `vf2time`, `vf2history`, `vf2outfits` and `vf2refresh` and their `.ini` files (Up to 28 Children is off by default, so `vf2kids` is not installed). In that executable the Fix Vanilla Game Bugs byte is set, so both website fixes are on, and the Cure test passed.
- Every Python module of the unzipped bundle imports from the bundle itself (25 of 25).
- **Not yet tried in a running game:** the two website fixes, Copy Player Slot's replace, the Picture Maker and the sidecar re-keying.
- Asset: `VF2-B205-Release.zip`, 164,729,468 bytes, SHA-256 `385906c34e9ae0ccfa5f9e0a5b6a13a41c4cd5a6d7bb5eb284b25c84858c5b93`.
