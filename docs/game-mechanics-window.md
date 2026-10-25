# Game Mechanics window

The Tools tab's **Game Mechanics...** link (the Game section, with its "?" guide `game_mechanics`) opens a read-only
window of Virtual Families 2's hidden rules. The window is `src/vf2_game_mechanics_window.py`; its lines are
`src/vf2_game_mechanics.py`; their source is `docs/game-mechanics/spec.md`, the research spec of the B200 core
executable (every patcher option byte 0). It is modelled on the Virtual Villagers patcher's Game Mechanics window.

## Layout

- The intro, then the line that explains the labels, then a link to each group (3 to a row, so all fit the window
  at its smallest). A click scrolls the page to that group's heading.
- The page: a read-only Text box with its own scroll bar that takes the rest of the resizable window. Each group
  is a heading; each line a bullet, a detail an indented dash under the line before it.
- Every line shows its label right after the bullet, in capitals and its own colour:
  **VERIFIED-E** (green: the game's own routine was run as linked, emulated, with the game's inputs and every
  outcome counted over the game's own rand), **VERIFIED-C** (blue: read from the game's own code on a call path
  traced from the running game) or **UNCONFIRMED** (red: not yet shown either way).
- Groups, in order: Time and ageing; Needs and upkeep; Health and sickness; Old age; Pregnancy and babies;
  Careers (with every career's pay per real hour at each level); Money and interest; Leaving home; Dating, marriage
  and the next generation; Island events (every event of the shipped game); Weather; Messes and malfunctions;
  Collectibles; Flea Market and On Sale; Chance and timer index.
- Times are real times at the game's normal speed. Game-clock timers stop while paused; real-time ones do not.
- Patcher options (Older Villager Mortality Curve, Allow Older Pregnancies) are shown as options, both ways.

## What it does not do

It reads no save and writes nothing: no save, install, log, data or settings file. It shows the same page for
every family. Closing it destroys only the window; the Tools tab opens one at a time.

## Words

Family members, never the code's word for them (a test refuses it outside the patcher options' own names). The
window describes the game as it runs; it never calls a rule a bug or says the patcher fixes it.

## Rules settled for the window (2026-10-25)

Each was run as linked on the B200 core executable and is pinned by `tests/test_game_mechanics_b200_exe.py`
(set `VF2_B200_CORE_EXE` to the core build's `Virtual Families 2 - B200.exe`; skipped otherwise):

| Rule | Result | Where |
|---|---|---|
| Time away | up to 31,000 s in full; 31,000 s to 24 h away credits 31,000 s (51 units); more than 24 h credits 24 h (144 units); saved paused credits nothing | `AllVillagersTimeflowUpkeep` 0x4C4D29..0x4C4D8F |
| Paused clock | `SetSpeed(999)` stores speed 0; `Seconds()` returns the banked value | 0x468B80, 0x468B00 |
| Fifth food-group slot | a family member without a career counts one more group whenever the Grains slot's expiry is set (low byte non-zero), even after it runs out; old age, illness, health and happiness all use the count | `FoodGroupsActive` 0x4CB870 |
| Interest | at most 2 missed game days are paid | `CMoney::UpdateInterest` 0x481D80 |
| Brokerage Account | owned and bought again: 1%; then +2 points per purchase back to 11% | `HandlePurchaseItem` 0x48C110 -> 0x4B8B50 |
| Malfunctions | the 2-second step rolls 1 in 800 and picks one at speed 10 and while paused | `UpdateScene` 0x4A266E..0x4A28F9 |
| Flea Market | lists all 36 goods; never rotates (the stock 6-hour rotation is unreachable in B200) | `VF2GetExpandedFleaMarketCount` 0x4B9A90 |

`python scripts/export_game_mechanics_claims.py <folder>` writes every line with its label and evidence for
review.
