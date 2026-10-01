# VF2 B199 release notes

**The patcher bundle.** Built from `main` at `303e5d1` (PR #414), seeded from the B198 matrix.

B199 makes the invisible furniture count as the real thing everywhere the base game checks for one exact store item. Nothing here removes a feature, and the 32 executable variants are the same feature combinations as B198.

## Invisible furniture counts as the real thing (#414)

A few places in the original game check for one specific store item rather than a kind of furniture. The invisible copy of that item therefore did not count, even though it works like the real one everywhere else. Every patched executable now accepts the invisible copy in those places:

- **Goals.** "Staying cool in the pool" completes when you place an Invisible Kiddie Pool or Invisible Full-Size Pool. "Let's dance" completes when you place an Invisible MP3 Player. **Both are confirmed in play**: each completed in a village whose only pool, or only music player, was the invisible one. As with every placed-furniture goal, it counts once the Decorate tab is closed.
- **Kiddie pool play.** Children splash and play in an Invisible Kiddie Pool on their own, as they do in the stock one. The two activities required the stock pool by its item number.
- **Happiness.** Villagers who like music, swimming or resting get the same happiness bonus from the Invisible MP3 Player, the invisible pools and the Invisible Hammock as from the stock pieces.
- **Clicking the Invisible MP3 Player** plays its music even when no stock MP3 player is placed.

**How this was checked.** I searched the base game for the item number of every invisible item's stock version.
- Everything not listed above already treated the invisible pieces like the stock ones. In particular, the furniture a villager chooses on their own is recognised by the kind of object it is, and the invisible copies share it. Every route this patcher adds also lists both versions.
- Every fix from the B197 audit applies to the invisible pieces too.

## Hammock wording

The README and the patcher's descriptions now say which weather allows the autonomous hammock in players' terms: **normal weather and Sunny** (the sun-beam weather Bottled Tropical Sunshine produces), and not Foggy, Raining, Stormy or Snowing.
- The game's own code calls those two weathers "Sunny" and "Cloudy". That internal "Cloudy" is the sun-beam weather, not fog.
- The behaviour itself is unchanged.
- As in the base game, a villager also has to be tired (energy 65 or lower) to choose the hammock on their own.

## Checks

- All 32 variants built from the commit above, 32 distinct executables; identities recorded in `data/vf2/release-identities-B199.json`.
- The bundle reproduces the build on a clean install (8194 of 8194 files) and passed the release gate: **RELEASE GATE PASSED**, no features lost against 19 retained releases.
- Applied with the bundle's own patcher from an untouched game: every one of the six changed checks in the resulting executable reaches the new "stock or invisible" helper, and the goal check translates the invisible pools and MP3 player.
- Asset: `VF2-B199-Release.zip`, 146,662,820 bytes, SHA-256 `9194ad2bb278e34c94d069e3cd65020d2397030037c709fb0ee293ce6f4a9a1b`.
