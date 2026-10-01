# VF2 B198 release notes

**The patcher bundle.** Built from `main` at `eab44df` (PR #412, after #410 and #411), seeded from the
B197 matrix.

B198 follows the B197 audit. It adds one new setting, **Fix Vanilla Game
Bugs**, which fixes bugs that are in the original game's menus as well as in
every earlier patched build, and one README correction. Nothing here removes a
feature, and the 32 executable variants are the same feature combinations as
B197.

## New setting: Fix Vanilla Game Bugs (Main, on by default)

One checkbox for fixes to the stock game's own menu bugs. It is a single byte
in the patched executable (`.vf2bugs`), the same kind of switch as Allow Older
Pregnancies, so unticking it gives the original behaviour back exactly. Every
bug below was reproduced in the game with the setting off and checked fixed
with it on.

- **Start Over asks first (#411, now under this setting).** On the title
  screen, Start Over did exactly what Continue does and dropped you back into
  your village. It now asks "Are you sure you want to restart the current
  game?" **OK** starts a new village for the same player (the intro story,
  then adoption); **Cancel** leaves everything as it was. With no village yet
  it behaves like Play, as before.
- **Settings > Pause Game: Yes.** Clicking **Yes** while the game was
  already paused (for example after pressing Space) paused it "twice", so the
  next Space press left it still paused and a second press was needed. It now
  stays a single pause.
- **Invisible Change Player button removed.** Clicking an empty spot a little
  above and to the left of the title buttons opened the Change Player dialog.
  That was the Manage Games button's old position, left clickable after the
  button was moved. Manage Games still opens Change Player.
- **The title screen keeps itself up to date.** It now shows your player's
  name when you arrive, not only after opening Manage Games. The first button
  says **Play** or **Continue** according to whether a village exists: the
  original game chose that label once, when it loaded, so after starting your
  first village it still said Play, and after deleting your player it still
  said Continue. The **Manage Games** button no longer disappears for the
  rest of the session after you delete your last player and create a new one.

## Documentation

- **README (#410):** the autonomous hammock also needs a tired villager
  (the base game's energy rule, kept by the owner's decision).

## Checks

- Every fix was decoded in the built executable (each hook lands on its code
  and each one reads the `.vf2bugs` byte) and tested live, with the setting on
  and again with it off in the same executable.
- All 32 variants built from the commit above, 32 distinct executables, each
  carrying the `.vf2bugs` byte at its default `00`; identities recorded in
  `data/vf2/release-identities-B198.json`.
- The bundle reproduces the build on a clean install (8194 of 8194 files) and
  passed the release gate: **RELEASE GATE PASSED**, no features lost against
  18 retained releases. It offers 36 settings, Fix Vanilla Game Bugs among
  them, on by default.
- Applied with the bundle's own patcher from an untouched game: the default
  selection sets `.vf2bugs` to `01`; unticking Fix Vanilla Game Bugs changes
  only that byte back to `00`; ticking it again restores a byte-identical
  executable.
- Live on that bundle-applied game (new save folder): the old hotspot does
  nothing, the title shows the player's name and **Continue**, Start Over asks
  before restarting, and Pause Game: Yes while paused needs only one Space.
- Asset: `VF2-B198-Release.zip`, 146,659,573 bytes, SHA-256
  `79f3d8f86aba041f16a8978f65de46adb8e898506c8d307268f48bd97b47510a`.

## Tooling

- The two older runtime-flag validator scripts know the new `.vf2bugs`
  section (#412, from Codex's review).
