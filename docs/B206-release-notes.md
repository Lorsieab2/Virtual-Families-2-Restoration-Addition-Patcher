# VF2 B206 release notes

**The patcher bundle.** Built from `main` at `2ff4152` (PR #472; the release config was merged after it as #473), seeded from the B205 matrix, in 8 parallel parts. B206 is a new version, not an in-place update of B205. It carries everything B205 had, plus the changes below.

B206 offers 43 settings, which is B205's 41 plus two new ones. 37 of the 43 are on by default. All 32 executables are rebuilt, because every one of them gains two new setting bytes and the House Renovations fix.

**B206 saves to its own folder**, `Documents\LDW\Virtual Families 2 - Modded B206`, because Virtual Families 2 names its save folder after the executable. See "Keeping your B205 families" below.

## Choosing patches (#472)

- **Four preset buttons, as in the Virtual Villagers patcher**, each with its own **?**:
  - **Select All Patches** ticks everything except Experimental.
  - **Default Patches** ticks the defaults below.
  - **Owner's Defaults** ticks everything except Up to 28 Children, including every cheat and both invisible-furniture settings. The transparent swap overrides the visible graphics.
  - **Deselect All Patches** clears every tick.
- **Patch Selection Settings...** opens a window with a search box and one tick box per patch. **Tick These** and **Untick These** change the chosen patches the way a click does: a patch brings the patches it needs, and takes away the patches that need it.

## Cheats are off by default (owner, 1 November 2026)

The owner's rules for these defaults:
- "anything that sets prices to 0 is DEFAULT OFF"
- "Anything that makes villagers succeed in skills 100%, no failing, is DEFAULT off"
- "Keep off by default: All items show in flea market/outfits/hairstyles"

**Off by default:**
- Cheat Upgrades.
- All 36 Flea Market goods.
- **Free and Guaranteed Cheats** (new; the `.vf2free` byte). It unlocks exactly:
  - the Force Successful Pregnancy row;
  - the $0 Anti-Spam Software Ownership row;
  - the $0 Rockhound Certificate Ownership row;
  - a free Time Warp.

  The three rows are on the Special Upgrades page and need Cheat Upgrades as well.
- **All outfits and hairstyles always for sale** (new; the `.vf2clth` byte). When it is off, the Clothing and Hairstyles page shows the original six rotating outfits, plus 6 rotating rows drawn from the 100 hairstyles and 8 holiday outfits.

**Still on by default:**
- Every content setting and every paid upgrade, including both kinds of renovations and the holiday furniture, outfits and collectibles.
- Time Controls and R Refreshes the Store.
- **No AI Icons** keeps its default. It only reskins Cheat Upgrades rows, so it takes effect when Cheat Upgrades is ticked, and the patcher ticks it again at that point.

## Time and the store

- **The Time Warp costs money** (#469). The Time Controls Time Warp costs the same as the store's own Time Warp, $2,000. The price is read from the game when you click the button.
  - A family without enough money is told so, and nothing changes.
  - It is free with Free and Guaranteed Cheats ticked.
  - `vf2time_b200.dll` is rebuilt.
- **R always redraws** (#471). R on the Flea Market page now always picks again, also with All 36 Flea Market goods on. In that case you won't see a change in the list. `vf2refresh_b200.dll` is rebuilt.

## Tools

- **Picture Maker: every picture** (#470).

## Fixed

- **House Renovations and Special Upgrades in builds without Cheat Upgrades.** This was broken in B205's builds without Cheat Upgrades, and in every earlier release.
  - **Where:** the 8 B205 executables with Mobile Renovations but without Cheat Upgrades.
  - **What players saw:** the store's House Renovations page listed only 10 of its 30 rows. The Special Upgrades page listed 30 rows where it has 10; 20 of them were read past the end of its list.
  - **Cause:** the generator's renovation count patch had matched the Special Upgrades page's bytes.
  - **Now:** both pages are right in every B206 executable, emulated at Special Upgrades 10 or 53 and House Renovations 30.

## Keeping your B205 families

Copy everything in `Documents\LDW\Virtual Families 2 - Modded B205` except the `Backups` folder into `Documents\LDW\Virtual Families 2 - Modded B206`. That includes both the `Virtual Families 2 Patcher Data` and `Virtual Families 2 Patcher` folders.

## Checks

- All 32 variants are built from `2ff4152`, with 32 distinct executables. The hashes are in `docs/b206-matrix-manifest.md` and the identities in `data/vf2/release-identities-B206.json`.
- The five companion DLLs are built fresh from this commit. `vf2time_b200.dll` (#469) and `vf2refresh_b200.dll` (#471) changed; the other three are rebuilt from unchanged source. Their hashes are in the matrix manifest.
- I emulated the store pages on all 32 executables, using the game's own GetCategoryItemCount and GetCategoryItem:
  - Special Upgrades lists 53 rows with Cheat Upgrades (50 with Free and Guaranteed Cheats off) and 10 without.
  - House Renovations lists 30 rows with Mobile Renovations and 10 without.
- The bundle reproduces the build on a clean install, 8194 of 8194 files.
- The release gate passed: **RELEASE GATE PASSED**, with no features lost against 26 retained releases (B179 to B205).
- **Not yet tried in a running game:** the Time Warp price, R on the Flea Market, the two new settings, the presets window and the House Renovations fix.
- Asset: `VF2-B206-Release.zip`, 164,809,325 bytes, SHA-256 `b37957717551133b1689025fdfa39ea8df629d8a61b569b1a722032e65c095d8`.
