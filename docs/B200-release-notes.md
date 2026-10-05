# VF2 B200 release notes

**The patcher bundle.** Built from `main` at `38cb7d4` (PRs #418, #419 and #420), seeded from the B199 matrix.

B200 brings back a cut island event, gives the Power Failure event a real downside, and lets villagers work out in sunny weather. Nothing here removes a feature, and the 32 executable variants are the same feature combinations as B199.

## Virtual Scouts is back (#418)

The PC game ships the text for a "Virtual Scouts" island event but no code to run it, so it never happened. With **Add mobile-exclusive Island Events** on, it is now a random event like the others:

- **"OK"**: everyone at home celebrates, and each villager gets **+5 happiness**.
- **"What rats?"**: you lose **100 food** (the store never goes below 0).

**Confirmed in play** in a test build: OK took a villager's happiness from 52 to 57 and set her action to Celebrating; What rats? took the food from 195 to 95.

## Power Failure can spoil the food (#418)

Choosing **"Take a chance"** in the Power Failure event now has a **1 in 4** chance that **"The food was not ok."**. When that happens, each villager has a **15% chance** of an upset stomach, checked separately for each person. Otherwise the result is the usual "This stuff still looks okay." "Throw out your food" is unchanged.

This also fixes a fault in the patcher's own Power Failure code: the spoiled outcome could never actually happen, because the roll was saved where the result screen never looked. In a test build, 18 rolls in a row all came out fine before the fix. After it, 8 of 25 rolls came out spoiled, which fits 1 in 4.

Both changes are part of **Add mobile-exclusive Island Events**; builds without it keep the stock event and its stock text. Island event state is never written to the save, so existing B199 saves load normally.

## Working out in normal and Sunny weather (#419)

The base game only let villagers choose to work out in **normal** weather, and the Home Gym System and Yoga Equipment actions, which are built on it, inherited that. With **Behavior Patches** on, villagers now choose **working out, the Home Gym System and the Yoga Equipment** in **normal weather and Sunny** (the sun-beam weather Bottled Tropical Sunshine produces), the same as the hammock. Foggy, Raining, Stormy and Snowing still rule them out, as before. Dropping a villager on the equipment was never limited by weather and still is not.

**Checked live** in a test build, by reading the villagers' choice tables from memory: Stormy and normal weather gave the stock values, and in Sunny weather all four workout choices switched to "allowed". The Sunny case was produced by setting the test game's weather value directly, because the bottle in that test ended a storm instead of bringing sun beams.

## Checks

- Every change has tests that fail when it is undone (9 of 9 deliberate breakages caught for #418, 8 of 8 for the compiled and string-table tests added in #420; for #419 every breakage that changes behaviour is caught).
- All 32 variants built from the commit above, 32 distinct executables; identities recorded in `data/vf2/release-identities-B200.json`. Debugger features are off in every variant.
- The bundle reproduces the build on a clean install (8194 of 8194 files) and passed the release gate: **RELEASE GATE PASSED**, no features lost against 20 retained releases.
- Decoded in the linked B200 executables (all-enabled and island-events-only), not just in source: the Virtual Scouts registration and outcome code and the three Power Failure helpers (the 1-in-4 roll with the slot claim, the 15% symptom call, the result text) are each present once and reached from their routes. The four workout weather writes are present in the Behavior Patches builds and absent from the core build.
- Asset: `VF2-B200-Release.zip`, 146,666,177 bytes, SHA-256 `f6a22f083abc3a701a3b4c49f239b9c4877cc11a86c507e0a4e8d3017ab31754`.
