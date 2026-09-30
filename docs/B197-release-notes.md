# VF2 B197 release notes

**The patcher bundle.** Built from `main` at `580a698` (PR #407, after #384-#406), seeded from the
B196 matrix.

B197 is the result of a full audit of B196 (2026-09-29/30): every setting,
the patcher, the GUI and the release packaging were traced from the code that
changes, checked in the built executables, and where possible checked in a
running game. 24 pull requests fixed what it found. Nothing here removes a
feature.

## Crash fixed: dropping a villager on the Invisible Patio Table (#378)

**Issue #378 is fixed (#384).** Dropping a villager on the Invisible Patio
Table, Invisible Picnic Table, Invisible Lounger, Invisible Spa Lounger or the
visible Spa Lounger could crash the game. That happened once the store's
**Pets** page had been shown in the session, which is why it looked random.

The cause was in those items' placement maps. They carried hotspot numbers
copied from the mobile game that the PC game's drop handler has no entry for,
so it jumped to whatever data sat past its table. After the Pets page is drawn
that data is a pet's item number, and the game tried to run it as code.
**Reproduced live on B196** with a debugger attached: access violation
executing address `0x245`.

The maps no longer carry those numbers. Each item keeps exactly the same
footprint, collision and drop area as in B196: the built maps match B196 cell
for cell apart from the removed hotspot. Unticking **Add mobile furniture
behaviors** later also no longer puts the unsafe maps back. **Confirmed live:**
the same steps on the fixed build do not crash, and the villager has a
refreshing drink at the table.

## Villagers

- **Careers can be maxed again (#405).** Praising a villager while they work
  their career raises how much career progress they earn while the game is
  closed. Behavior Patches reset those career weights on every load, erasing
  the praise, so careers stalled. Career work now behaves exactly as in the
  base game; the varied career captions are kept.
- **Computer drop (#385).** Dropping someone on a computer now switches
  ordinary web browsing to a video game half the time, as intended. The check
  read the villager's *age* instead of their current activity, so it almost
  never fired on a computer and instead fired on any furniture drop of a
  villager aged exactly 4.5.
- **Hammock in Cloudy weather (#395).** Villagers now choose the hammock on
  their own in Cloudy weather as well as Sunny, as documented; a base-game
  "Sunny only" rule had been left in place.
- **Furniture must exist (#403).** Fireplace watching, foosball, pinball,
  slots, pachinko, the kids table, the easel, the playhouse and sitting on a
  couch are only chosen when that furniture is in the house. Before, a villager
  could "play foosball" in the middle of an empty room.
- **Praise and scolding stick within a session (#398)** for the hammock,
  playhouse, snow, Home Gym and Yoga activities, which a per-decision refresh
  had been resetting.
- **Treadmill captions (#397).** A villager on the stock Treadmill no longer
  shows the Exercise Bike's captions after using the bike; the one caption too
  long for the game's label is shortened.
- **Picnic and Patio tables match the mobile game (#394).** From the mobile
  game's own code: the picnic table says "This person is too young!" and
  "Worried about food" (it showed an unrelated message); a prepared meal or
  drinks now shows on **every** picnic or patio table, visible or invisible,
  for 300 seconds each, instead of on one table that could lose it; several
  villagers can prepare at once without the props vanishing; every completed
  preparation makes the props ready.

## Cheat Upgrades

- **Max out sock pile (#391)** sets 1,000,000 socks instead of the largest
  number the game can hold, which overflowed the laundering goals. Saves
  already damaged by the old value are repaired when loaded; healthy saves are
  untouched.
- **Complete all Achievements (#392)** now pays every goal's coin reward once;
  it used to pay only about one.
- **Reset Achievements (#391)** keeps armed pregnancy one-shots.
- **Unlock everything in the store (#393)** is saved with the village and
  survives a relaunch; a new village starts locked.
- **Builds without Cheat Upgrades (#393)** ignore cheat state saved by a build
  with them (reroll and armed pregnancy options), instead of acting on it with
  no row to turn it off.
- **A new village (#406)**, via Start Over or a new player in the same
  session, no longer inherits the previous village's Health Plan or Oldest
  Villager record.

## The patcher

- **Restore Backup (#386)** restores into the folder the backup came from. It
  used to restore into the vanilla game folder in the GUI, which could delete
  vanilla files.
- **Output folder safety (#386).** Pointing the output at a folder that is not
  a modded game folder is refused before anything is backed up or moved.
  Read-only files no longer crash a rebuild halfway, and any failure writes the
  failure log.
- **Enable/Disable on an existing modded folder (#387, #396)** now works and
  gives the same folder as a fresh apply with the same selection, including
  removing the files of unticked settings. Files you add yourself are left
  alone.
- **Backup folder (#388)**: a folder picked with **Browse** now gets a new
  per-run subfolder; it used to fail every time. Each rebuild's ~230 MB backup,
  which is never deleted automatically, is documented.
- **Settings (#402)**: unticking a setting unticks the settings that need it,
  and ticking one ticks what it needs (No AI Icons needs Cheat Upgrades). The
  settings built into every executable are shown as always on. The summary no
  longer calls a setting enabled when nothing of it was installed.
- **Bundle contents (#390)**: editor cache files are no longer installed into
  the game folder; with both on, Invisible Workspace Upgrades wins over Misc
  Graphics Fixes for the Super Fridge; hairstyle icons are installed with the
  executable; the AI Bathroom 2 art requires Mobile Room Renovations.
- **Release gate (#389)** now checks every file and every runtime switch in the
  bundle, so a bundle missing a file or a switch cannot be published.
- **Docs (#400, #401, #404)**: README and setting descriptions corrected where
  the code disagreed (for example, the two marriage rows are free, and
  Same-Sex Marriage is saved with the game).

## Verification

- **Checked live on this exact B197 bundle** (Defaults, applied by its own
  patcher from a clean install, new save): with the store's Pets page shown,
  dropping a villager on the Invisible Patio Table does not crash and the
  villager gets drinks, with the drinks prop drawn on the table; **Unlock
  everything in the store** is still ticked after quitting and relaunching;
  **Complete all Achievements** from 0 coins paid 6,225 coins (it paid about
  one reward before); **Add max amount of coins** sets 4,000,000,000.
- **Checked live on earlier builds this audit:** the #378 crash reproduced on
  B196 (access violation executing `0x245`, a pet item number), the restored
  Hamster, an Island Event and its result dialog.
- **Checked in the built executables:** each code fix above was decoded out of
  a build.
- **Still to confirm in play** (each is verified in the built executable):
  career progress after praise, save and reload; the computer drop; the
  hammock in Cloudy weather (force it with a Flea Market weather bottle);
  Start Over after buying Health Plan and Unlock Everything; a drop on the
  Invisible Picnic Table; props on several picnic/patio tables at once.

Saves from B196 load unchanged.
