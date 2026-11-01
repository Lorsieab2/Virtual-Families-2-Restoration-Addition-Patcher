# Virtual Families 2 Restoration/Addition Patcher

Offline patcher and restoration/addition project for the official Windows version of *Virtual Families 2*.

Created with Codex AI in collaboration with Lorsieab2. This is a passion project dedicated to improving the *Virtual Families 2* experience. No copyright infringement is intended; please support the original game creators. :)

## Which copy of the game this supports

**This patcher targets the Windows build of *Virtual Families 2* downloaded from Last Day of Work's own website.** That is the only copy it is developed and tested against.

It has **not** been tested against the Steam release, and whether that build matches has not been established. The patcher validates the installation you point it at and refuses to proceed if it does not recognise it, so an unsupported copy should fail safely rather than be corrupted — but nothing is promised beyond the LDW build.

There is also no practical reason to get the game anywhere else: **all of LDW's PC games are free on their own website.** Download it from there and point the patcher at that installation.

## Requirements

Everything the patcher needs beyond the game itself:

| | |
| --- | --- |
| **Windows** | The patcher edits a Windows executable and ships a `.bat` launcher. There is no macOS or Linux build. |
| **Python 3.9 or newer, with `tkinter`** | Not bundled -- install it from [python.org](https://www.python.org/downloads/) if you do not have it. Keep the **tcl/tk and IDLE** component ticked in the installer (it is on by default); the GUI will not start without it. `Launch_GUI.bat` uses the `py` launcher when it is installed and `python` otherwise. Developed and tested on 3.14. |
| **An official VF2 install** | The Windows build from Last Day of Work's own website, unmodified. See [Which copy of the game this supports](#which-copy-of-the-game-this-supports). |
| **About 500 MB of free disk space, plus room for backups** | The patcher writes a separate modded copy rather than editing your install: a ~110 MB vanilla folder produces a ~210 MB modded folder, and the extracted patcher bundle is another ~200 MB. That figure covers the first run only. Every later **Enable/Disable Patches** run with the vanilla folder selected rebuilds the modded folder, and first saves a complete copy of the old one (about 230 MB, measured on B196) in a new timestamped folder under `.vf2_patch_backups` inside the modded folder by default; if you set the GUI's **Backup folder** field (or `--backup-dir`) to a folder that already exists -- one picked with **Browse** always does -- each run writes a new timestamped folder inside it, and a path that does not exist yet is created and used as given. (**Corrected:** an earlier revision of this change said a Backup folder that already exists stops the run. That was the old behaviour and it made **Browse** unusable; it is fixed in the same change.) The patcher never deletes these, so each such run adds about 230 MB. To reclaim the space, delete older backup folders from wherever they were written; keep the newest if you may want to restore from it. |

**No extra Python packages are needed.** The patcher and its GUI use only the
standard library, so there is nothing to `pip install`.

Administrator rights are not required, and your game install does not have to
be writable. The patcher copies from it and writes a separate modded folder, so
an install under `C:\Program Files` is fine -- use **Save modified folders
under** in the GUI to put the output somewhere your own account can write.
Backups default to a location under that output folder.

Patching itself is offline: no step of validating, patching, or restoring
contacts the network. The one exception is the **Check for updates** link in
the GUI header, which opens the patcher's GitHub page in your browser when you
click it.

**If a release carries more than one archive, take the highest revision.**
B196 carries a single archive, `VF2-B196-Release.zip`, so there is nothing to
choose between. B180 had two -- `VF2-B180-Release.zip` and
`VF2-B180-Release-r2.zip` -- and the rule was to take **r2**. They differ in exactly two files -- `manifest.json` and
`Transparency Log.txt` -- because one setting's description overstated what
it installs; all 32 executables are byte-identical between them. The
original is kept attached rather than replaced so anyone who already
downloaded it can still verify what they have.

If your antivirus quarantines the patcher or the patched executable, do not
simply override it. Confirm first that you downloaded the ZIP from this
project's own releases page, and where the release notes publish a SHA-256 for
the asset, compare it. Pass the **exact filename you downloaded** -- if you
took r2, that is the r2 name, and hashing the other archive will not match:

```
certutil -hashfile VF2-B196-Release.zip SHA256
```

If it matches the published value, you have the file that was released, and a
warning about a modified game binary is expected -- you can then restore it and
exclude the modded output folder. If it does not match, or the release you are
using does not publish one, leave the file quarantined and ask on the issue
tracker: a modified executable is also exactly what a real infection looks
like, and that is not a judgement to make from the warning alone.

### If the window looks frozen

It is probably working. Before writing anything, the patcher verifies every
file it is going to patch -- thousands of records on a full release -- and that
pass takes a while with little appearing on screen. Give it a minute before
assuming it has hung.

## Download

The [releases page](https://github.com/Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher/releases) carries two different kinds of asset, and only one of them is the patcher:

- **`VF2-B<version>-Release.zip` is the patcher.** This is what you want. It contains `Launch_GUI.bat` and the manifest the GUI reads, and you point it at your own VF2 installation. Take the newest one.
- **A `-r2` suffix means a corrected re-pack of that same release.** B180 carries both `VF2-B180-Release.zip` and `VF2-B180-Release-r2.zip`. Take the `-r2` one: it is the same build with one setting description corrected, and it is the same 32 executables byte for byte as the original -- only two of the archive's 7,459 members differ. The original stays attached because release assets are never deleted here, so the version people already downloaded remains available and verifiable.
- **`VF2-B<version>-Playtest-All-Enabled.zip` is not a patcher.** It is a complete pre-patched game folder built for testing a specific change. There is no GUI and nothing to configure. A playtest build has no patcher step, so it bakes in what the patcher would otherwise apply: the mobile sound assets (all 67 staged, and the four hardcoded `.wav` sound routes rewritten to `.ogg`), plus the two experimental rule changes (Allow Older Pregnancies, Older Villager Mortality Curve). (**Corrected 2026-09-29:** this used to call those two "default-off in the GUI"; the B196 manifest ships both with `default: true` and the GUI ticks them.) The patcher bundle instead keeps the stock `.wav` routes in its executables and rewrites them only when you tick **Use mobile sound assets**, which is what keeps that setting reversible. A playtest artifact may be marked "Latest" while the newest patcher bundle is an earlier version, so check the filename rather than the Latest badge.

Release ZIPs and compiled game payloads are intentionally not committed to the source tree.

Vanilla *Virtual Families 2* saves are compatible with the modded version. The patcher creates a separate modded game folder by default and does not overwrite the selected vanilla installation.

Note that VF2 derives its save folder from the executable's own filename: saves live in `Documents\LDW\<exe name>\`, where `<exe name>` is the executable's filename with its extension removed. A modded or playtest EXE with a different filename therefore starts with its own empty save folder rather than continuing an existing family.

## What the patcher does

- Validates a user-selected official VF2 installation before changing files.
- Applies only the patches selected in the manifest-driven GUI.
- Creates or refreshes a clearly named modded copy of the game.
- Supports dry-run validation, backups, restore, and machine-readable logs.
- Uses offline file patching; it does not inject into a running process.

### Patches tab and Tools tab

The window has two tabs. **Patches** is patch selection and the Dry Run / Enable-Disable / Restore Backup
actions, as before. **Tools** holds:

- **Back Up Saves...** lists every `Documents\LDW\Virtual Families 2...` save folder (the patcher's own
  `- Modded` folders are ticked, the stock and copied folders are listed unticked) and copies each ticked one
  into `<save folder>\Backups\Backup <date and time>`. The copy takes everything in the folder except
  `Backups`: the game's `Virtual Families 2<N>.ldw` saves and their `- Copy` files, `ldwLog.txt`, and the
  patcher's own `Virtual Families 2 Patcher Data` folder (the Children sidecar and any other file a patch keeps
  beside a save). A running game is paused for the copy and resumed; every file is verified by size and
  SHA-256, file times are kept, an existing backup is never written into, and a failed copy is set aside as
  `... INCOMPLETE` and never offered. Game speed is set to Paused in the backup's family saves
  (`Virtual Families 2<1-5>.ldw`; the copies only, your own saves are unchanged), so a restored backup opens
  paused and never catches up on the time since it was made. Only a family at Normal is paused; a save at
  another speed, one that cannot be read, and the previous saves `<N+20>` are copied exactly as they are. A
  backup's Children and Outfits files that matched a family save are re-keyed to its paused copy (as Copy Player
  Slot re-keys a copy's), so a restored backup keeps every extra child, those who left home or died included,
  and its outfit pictures; one that did not match is copied exactly as it is.
- **Restore Saves...** lists the backups, newest first, and restores the whole save folder or one family slot
  (its save, the previous save at slot + 20, their Children and Outfits files, and its
  `Virtual Families 2 Patcher\Save <N>` folder with the Family History log and Family Tree files, so they all
  go back together; no other slot's file is touched). It refuses while the game runs,
  shows exactly which files will be replaced, added and removed, restores only after the player says yes, and
  first backs up the current saves as `Backup <date> (before restore)`, so a restore can be undone. It rolls
  back if a file fails. **Delete Backup...** removes one backup.
- **Copy Player Slot...** copies one family into an empty save slot of the same save folder under a new name
  (`src/vf2_copy_slot.py`; tests: `tests/test_copy_slot.py`). It copies every file kept for the slot: the save,
  the game's previous save at slot + 20, the Up to 28 Children and outfit pictures sidecars
  (`Virtual Families 2 Patcher Data\Children` and `\Outfits`, both `<save file>.dat`), and
  `Virtual Families 2 Patcher\Save <N>` (the Family History log and the Family Tree Maker's tree file and edits;
  not its pictures, which it makes again). The new name is written where Rename Family writes it, in the copied
  save and the slot menu, and the settings file marks the slot in use. Each Children and Outfits sidecar is
  re-keyed to the copied save's FNV-1a hash and size (one for another save is copied unchanged, a damaged one is
  not copied), the log's `Family: <name> (Save <N>)` lines say the new save number and a `Family Renamed` record
  notes the name, and `.tree` files get the new slot and name. It asks first (No is the default; Return and
  Escape answer No) and refuses while the game runs. A slot with no save file is empty, whatever the settings'
  player list says (the game rebuilds that list from the saves at every start); a slot that holds another family
  is replaced only after a warning naming it. The target's own files (a replaced family's, or a deleted family's
  leftovers) are moved into `Backups\Replaced by copy <date> - Save <N> - <name>`, never deleted. It backs up first as `Backup <date> (before copy)`, writes
  every file through a temporary file, reads everything back and puts the folder back as it was if anything fails.
  No other slot is touched. No live test.
- **Rename Family...** changes the name a family slot is shown under. Virtual Families 2 has no family
  surname: the slot is shown under the player name typed when it was started (main menu `Player:`, Change
  Player, the daily email). The tool writes that name (gs+0x25ABC) in the slot's save, its entry in the slot
  menu (`Virtual Families 20.ldw`) and the previous save at slot + 20 when it still holds the old name. The
  rule is the game's own: at most 19 characters (the box takes 20 keys but the game keeps 19), never empty or
  only spaces, never `NEW PLAYER` (the game's text for an empty slot); only printable ASCII is accepted, since
  whether other keys reach the box is UNCONFIRMED. It refuses while the game runs, backs up first as
  `Backup <date> (before rename)`, reads every file back and puts everything back if one fails. The slot's
  Children and Outfits files that matched the renamed saves are re-keyed to them (as Copy Player Slot re-keys a
  copy's), so the game keeps every extra child (7 to 28) and the outfit pictures on the next load; one that did
  not match is left as it is. A family with a Family History log gets one `Family Renamed` record in its newest
  file (old name, new name). Evidence with exe addresses: `docs/vf2-save-format.md` section 11. Code:
  `src/vf2_rename_family.py`; tests: `tests/test_rename_family.py`.
- **Game Speed...** shows each family's saved speed (Paused, Normal, or any other value raw) and sets it to
  **Paused** or **Normal** in a closed game's save, writing what the game's own Pause / Unpause write (traced in
  the stock exe: Options 0x42269B / 0x4226EA, Space 0x43BC52 / 0x43BC7B, `CGameTime::SetSpeed` 0x427A50, which
  stores 0 for 999): the speed option gs+0x25B18 (10, or +999 when paused) and the saved CGameTime. Paused acts
  as if the game was paused just before it saved; Normal as if the paused family were unpaused now, so the clock
  carries on from where it stopped and each living family member's ageing stamp is set to now, as the paused
  game's two-second update keeps it (0x499872): the paused time is never aged in. It refuses any other speed, an
  unpause that would have removed a dead body meanwhile, and a Pause the stock and the patched game would work
  out differently (more than 2^24 s since the last speed change; the patched build rounds to a float). It backs
  up first as `Backup <date> (before speed change)`, writes only the slot save, reads it back, checks no other
  byte changed and puts it back on failure; no log. The slot's Children and Outfits files that matched the save
  are re-keyed to it (as Copy Player Slot does), so the game keeps every extra child and the outfit pictures;
  one that did not match is left as it is. Slow and Fast are not offered: the game sets
  no speed but 10 and the +999 pause. Code: `src/vf2_game_speed.py`; tests: `tests/test_game_speed.py`.
- **Game Mechanics...** (the Game section) opens a read-only window of how Virtual Families 2 works underneath,
  laid out as the Virtual Villagers patcher's: a link to each group at the top (time and ageing, needs and upkeep,
  health and sickness, old age, pregnancy and babies, careers, money and interest, leaving home, dating, marriage
  and the next generation, Random Events (Email and Popup Events), weather, messes and malfunctions, collectibles, the Flea Market and On
  Sale, and a chance-and-timer index), every time a real time at normal speed and every chance the game's exact
  one. Each line shows its label: **VERIFIED-E** (the B200 core exe's own routine run as linked in unicorn and
  every outcome counted), **VERIFIED-C** (read from the exe's own code on a traced call path) or **UNCONFIRMED**.
  Patcher options (0 in the core exe) are shown as options, both ways. The facts come from
  `docs/game-mechanics/spec.md`; the rules settled for the window are pinned against the exe by
  `tests/test_game_mechanics_b200_exe.py` (set `VF2_B200_CORE_EXE`): time away (up to 31,000 s in full, 31,000 s
  up to 24 h away, 24 h when longer), a paused clock that stops, the Grains-slot extra food group for family
  members without a career, interest of at most 2 missed days, Brokerage bought again giving 1%, malfunctions that
  roll while paused, and a Flea Market that never rotates in B200. It reads no save and writes nothing.
  `python scripts/export_game_mechanics_claims.py <folder>` writes every line with its label and evidence.
  Code: `src/vf2_game_mechanics.py` (the lines) and `src/vf2_game_mechanics_window.py`; the window:
  `docs/game-mechanics-window.md`; tests: `tests/test_game_mechanics.py`.
- **Family Tree Maker...** (the Family Tree Maker section) draws a family's tree from its save, the Virtual
  Villagers / Virtual Families 1 Family Tree Maker ported to Virtual Families 2 (VV main cdcface3): one row per
  generation of the save's own Family Tree (parents, the heir and the one who married in, up to six children, and
  children 7 to 28 from the Up to 28 Children file of that very save), each face the game's own head sprite
  (`Images\male_heads00.png` / `female_heads00.png`, column 5, the row the head value), with marks, shapes,
  colours, stickers (the Virtual Families, Virtual Families 2, Fish Tycoon and Plant Tycoon logos), backgrounds (the owner's 27 pictures), pages and PNG/JPG
  export. Under each portrait, where they apply (each a tick box, on by default): Founder, Runner, twins, Married
  in, Heir, Husband N / Wife N (by each spouse's own sex; numbered only when the Family History log saw the first
  marriage), Remarried, Divorced, Adopted, the Random Event ("Popup Event: The Little Visitor"), the career as the
  game words it ("Novice Engineer"), Left home and "Deceased: <cause>". The save is only read. What no record says
  is shown as unknown, never guessed. The tree file
  (`Virtual Families 2 Patcher\Save <N>\Data\Family Tree\Virtual Families 2 Family Tree - Save <N>.tree`) keeps the
  player's edits and every member the tree has ever seen in that save, so a spouse who died with no children, an
  earlier spouse after a remarriage, a divorced spouse and a founder who died childless stay on the tree once seen.
  When the Family History log is there (`...\Save <N>\Logs\Family History`), it adds twins and triplets, causes
  and ages at death, earlier marriages, why someone left home and which event brought an adopted child. The
  **Family Member Info** tab has a **Relationships** dropdown (the Virtual Villagers patcher's, v1.35.85): pick a
  kind of relative, such as "First cousins (6)", to list everyone of that kind by name, and click a name to select
  them on the tree. It covers parents, children, full and half siblings, twins and triplets, grandparents and
  grandchildren of any generation ("Great-great-grandmother", then "3× great-grandmother"), aunts, uncles, nieces,
  nephews, great-aunts, cousins of any degree and removal, half and double forms, partners (the other parent of a
  child), in-laws and step-relations, worked out only from the parents the tree records. The living, the dead and
  those no longer in the house are all listed, the dead and the gone marked. Read-only. Two family members with the
  same name and look are two people, each with their own age, parents (their own seat in the save's Family Tree,
  never chosen by name), number and edits; an edit an earlier build made for both is kept in the tree file but
  shown on neither. A title line you retyped keeps your words, with its counts and date those of the tree now.
  Big trees are laid out several times faster, the picture exactly the same. Code:
  `src/vf2_genealogy.py` (the family), `src/vf2_family_history.py` (the log), `src/vf2_tree_memory.py` (the tree
  file), `src/vf2_family_tree.py` (the picture), `src/vf2_family_tree_window.py`, `src/vf2_member_info.py`,
  `src/vf2_relationships.py`, `src/vf2_tree_editor_tools.py`, `src/vf2_line_colours.py`, `src/vf2_gdiplus.py` and the pictures in
  `src/family_tree_backgrounds/`; the evidence: `docs/family-tree-maker.md`; tests: `tests/test_family_tree.py`
  and `tests/test_family_tree_memory.py`, `tests/test_relationships.py`, `tests/test_tree_namesakes.py`,
  `tests/test_tree_big_speed.py`.
- **Game Font Text...** writes any text in the game's own four fonts and saves it as a PNG (Game size, 2x, 4x,
  a custom size, the Picture Maker's export): a text box, the font, the game's tint colours, a wrap width, a
  live preview drawn exactly as the game draws text (`src/vf2_game_text.py`, proved against the game's own code),
  and a character picker (accents by language, and any Unicode character by name or code). Letters the fonts lack
  are patcher-made in the fonts' own style and labelled "(patcher-made)". Code: `src/vf2_text_tool.py`,
  `src/vf2_game_text.py`, `src/vf2_glyph_maker.py`, `src/vf2_glyph_render.py`, `src/vf2_game_fonts.json`.
- **Picture Maker...** draws family members exactly as Virtual Families 2 draws them and saves them as PNG
  pictures with a clear background: the Fish and Plant Tycoon patcher's Picture Studio made for this game. **From
  my save** lists everyone in a family's save by where they are (at home, left home, died, earlier generations only
  in the Family Tree) and the Male and Female Outfits in the tool tray. A family member at home can be drawn in
  the house (any of the 56 body frames: walking NE/SE/SW/NW, 15 actions, 9 sitting and lying; any of the 12 head
  turns; the shadow; an expecting mother's 1-3 babies in her arms), on the Details screen (the big body and big
  head, 3 head turns), on an event screen (head turned or facing you) or in the Family Tree; anyone else only in
  the Family Tree, as the game does. A tray outfit is drawn as the tray draws it (column 14 of the actions sheet at
  70%), with its own picture when the patcher's Outfit Pictures file is there for that very save, else the last
  one of its sex bought, as the original game shows them. **Make your own** offers both sexes, every age (the body
  drawn at age / 700 + 0.5 and the head at (age / 14 + 80) / 100 below 14 years, the old head from 45 years), all
  50 heads (the patcher's 100 hairstyles), all 50 outfits (Discount 0-31, Department 32-43, Designer 44-49) and,
  with a patched game, the patcher's four Holiday outfits (50-53), drawn from the patcher's own frames where the
  game's cell would go. In both tabs a family member in the house can **carry** any item: all 187 carried-item
  pictures the game has (the 91 cells of `carrying.png`: household things, food, tools, toys, the baby; and the 96
  of `collectables_small.png`: the 60 collectibles, socks, wrappers, weeds, dirt smudges, cobwebs and the Holiday
  ornaments), each named and marked: 151 are carried in the game (the actions that carry them are listed); 5 are
  **unused in the game** (the empty basket, the soda bottle -- carried only by the patcher's patio drinks -- the
  paint can, the TV remote and an extra leaf picture: no action in the game's code carries them); 31 are **never
  shown** (the baby as a carried value, which the carry draw skips; the cobwebs, which nothing makes; the Holiday
  ornaments in the original game; and 16 empty cells). They are drawn as `CVillagerManager::DrawCarriedItems`
  draws them: a `carrying.png` cell 10 left and 10 up of the carry place, a collectible at the place itself, never
  scaled, 10 lower in body positions 2, 9, 17 and 18 and 20 lower in 23 (the body position follows the frame, or
  can be picked), behind the family member when the frame faces NE, NW or N. The 12 empty `carrying.png` cells can
  never be drawn by any carried value (79 or more draws the collectibles sheet), so their position is not from the
  game. A save does not keep what anyone carries; the game draws carried items only in the house. Which values the
  game carries is read from every `PlanToCarry` call in the objects (`src/vf2_carried_items.json`, made by
  `scripts/build_vf2_carried_items.py` with `tests/vf2_carry_scan.py`). **Patched look** follows the game folder
  chosen (on when it has the patcher's frames). PNGs
  are cut to the drawn pixels (with a small margin, or none) at the game's size, 2x or 4x (crisp) or a custom size
  (smooth). The pictures come from the game folder; no game art ships. Saves and game folders are only read.
  How it is checked (`tests/test_picture_maker.py`, with the B200 desktop objects and the original game): the game's
  own `CAnimManager::LoadAssets` builds the link points (`src/vf2_people_links.json`, made by
  `scripts/build_vf2_people_links.py`), and `DrawDetailVillager`, `DrawEventVillager`, `DrawVillager` with
  `DrawCarriedItems`, `CFamilyTreeScene::DrawPeep` and `CInventoryManager::DrawItem` run under unicorn
  (`tests/vf2_people_emu.py`): every draw planned is the game's (image, cell, place, size); the game's blitter
  `BlitRectWithAlpha` runs on real cells and every scaled pixel matches; whole pictures match a Pillow composite of
  the game's sheets pixel for pixel. Every carried value (0-174) is drawn by `DrawVillager` with `DrawCarriedItems`
  in 10 frames, body positions, ages and sexes and must be the Picture Maker's draw, and whole pictures with carried
  items match a Pillow composite pixel for pixel. Not checked against the game: the expansion outfits' placement (taken from the
  patcher's own generated drawing code, not run), an expansion outfit's tray picture, the patcher's ornament spawning
  (the ornaments' carried draw is the game's own), and anything in a running
  game (it was never started). The Family Tree's own frame is not drawn, and the house view is the normal zoom with
  the family member standing on the floor. Code: `src/vf2_picture_maker.py` (the window and the save),
  `src/vf2_people_pictures.py` (the people as the game draws them), `src/vf2_picture_image.py` (the pictures, the
  PNG reader and writer, the game's scaled draw).

  **All game pictures** (the third tab) offers every picture the game has, by category (people, pets, furniture,
  upgrades, rooms and the house, weather and nature, effects and animations, work and food props, store and tray
  icons, collectibles and collections, goals and trophies, buttons and controls, dialogs and panels, meters and
  bars, meters assembled, screens and backgrounds, fonts, cursors, the patcher's pictures), with a search box:
  - all 632 entries of the game's image table (`theGraphicsManager`'s `ImageList`), each cut into every cell exactly
    as `ldwImageGrid`'s constructors and `GetCellRect` cut it (11,922 cells: every animation frame, furniture turned
    each way, button states, the people's sheets);
  - every other file in Images: the house map tiles, the fonts and the splash screen the code loads by name, and the
    unused ones (`main_BG.png`, `VD_BG_2.png`, `MenuBtnCurrency2.png` and the two DRM pictures: nothing in the code
    names them), marked **(unused)**; the four table entries whose files the game does not have are listed as
    **(missing)**;
  - the bars assembled at any level: the Details screen's five bars and the loading bar
    (`theContinuousVariableMeter`, empty to full), and the two meters the game never calls
    (`theSlicedVariableMeter`, `theVariableMeter`), marked **(unused)**;
  - in a patched game, every file that is not the original game's (new or changed), marked **(patcher)**, the new
    ones in their own category by folder.
  **Save all shown** saves every frame of everything the search shows, a folder per category. The list comes from
  `src/vf2_game_pictures.json` (made by `scripts/build_vf2_image_table.py` from the objects and the clean install's
  file list); the pictures are read from the game folder at run time and no game art is in the repository.
  Checked (`tests/test_game_pictures.py`): the data file is what the objects give; `GetImage` and `GetCellRect` run
  under unicorn (`tests/vf2_pictures_emu.py`) for all 628 entries the game folder has and every cell's file and
  rectangle is the Picture Maker's; the three meters' `DrawPercentMeter` make exactly the Picture Maker's calls at
  every colour and many levels; `ClipRect` clips as the Picture Maker does; bars match a Pillow composite pixel for
  pixel. Not checked against the game: JPEG and GIF pixels (decoded by Windows, not the game's libjpeg), how the
  code draws the files it loads by name (shown whole), the unused percent meter's colour (drawn at 90% on a clear
  background; the game blends it over the screen). Not assembled: whole screens, dialogs, rooms or the house with
  furniture placed, pets in motion, weather over the house, day and night; their pieces are all offered as cells.
  Code: `src/vf2_game_pictures.py`.
- **How to Use...** opens the guide: one short page per control. A small **?** button beside each control
  opens the page for it. The pages are `src/vf2_how_to_use.json`, read by `src/vf2_how_to_use.py`.

The code is `src/vf2_save_backup.py`, `src/vf2_rename_family.py` and `src/vf2_game_speed.py` (no Tk; the
latter two read saves through `src/vf2_save_reader.py`), `src/vf2_tools_gui.py` (the Tools tab) and the two guide files;
`work/` holds the copies the exporter ships (`GUI_TOOL_FILES` in `work/export_offline_patch_bundle.py`), and a
test keeps the two trees identical. Tests: `tests/test_save_backup.py`, `tests/test_rename_family.py`,
`tests/test_tools_tab.py` and `tests/test_how_to_use.py`.

After extracting a release, run `Launch_GUI.bat`. The exported bundle also contains `How to Use.txt` with player-facing instructions.
Release bundles include the instruction-only `vf2_crash_capture.py` helper and
an unfilled exact-build manifest template for optional crash QA. Neither the
patcher nor that helper changes the registry or launches VF2; any generated WER
instructions must be reviewed and run manually by the player.

The game's own save-writing path is left alone. `theGameState::SaveCurrentGame` and the per-class `SaveState` serializers are not modified, and the build asserts their stock byte spans and record counts.

The load path is mostly extended by wrappers that run the native `LoadState` first and then reconcile achievements or re-apply the autonomous behavior table in memory. There is one exception: with custom achievements included, five byte spans inside `CAchievement::LoadState` are rewritten so that the reserved-tail validation and clearing ranges cover the custom achievement IDs instead of the stock ones. That changes which ID range the loader validates and clears, not the layout of the record it reads.

## What's included

*Accuracy audit: 2026-09-24, against the shipped B196 bundle. Claims below were
checked against `manifest.json`, the release notes and the owner's confirmed
play reports; superseded claims are marked rather than deleted.*

The GUI reads its checkboxes from the shipped manifest, so the exact list follows
the release you downloaded. The next bundle offers 45 settings (B206): B205's 41 plus **Free and
Guaranteed Cheats**, **All outfits and hairstyles always for sale** (both off by default), **Render Unicode
with In-Game Fonts** and **Use Unicode Font (overrides in-game fonts)** (only one of the two can be on).

That number is not simply the count of settings the patcher defines, which is
46. The settings list drops any optional setting that has no packaged source
assets -- in B201, as in B180, the two named just below -- and the export adds
one setting of its own, `core_assets`, which copies the support files and
generated assets that are not tied to a single feature. So 46 defined, less 2
without packaged assets, plus 1 generated, is the 45 the GUI shows. (B205 and the
final B204 rebuild, which added **All 36 Flea Market goods** and **R Refreshes the Store**: 42 - 2 + 1 = 41;
B205's two website fixes are part of Fix Vanilla Game Bugs, not new settings. The first B204 bundles:
40 - 2 + 1 = 39. Before
the Family History log it was 39 - 2 + 1: B202's and B203's bundles offered 38 settings;
before Up to 28 Children existed the same sum was 38 - 2 + 1: B201's bundle offered
37 settings; before Time Controls the B198 through B200 bundles offered 36,
and before Fix Vanilla Game Bugs the B197 bundle offered 35.)

**A missing checkbox does not mean a missing feature.** That filter asks only
whether a setting has files to copy, so a feature built as *code* rather than
as assets has nothing to package and drops off the list while still being
installed with the executable patch. **Allow Same-Sex Marriage is exactly that
case, and it works in B196.** Only one of the two below is genuinely not
applied.

Two of the entries below do not appear as their own checkbox in the GUI. They
are **not** the same case, and an earlier revision of this README wrongly
described both as simply absent:

- **Allow Same-Sex Marriage** **works, and always has.** It is not a packaged
  asset but compiled code, built into every patched executable and installed
  with the rest of the executable patch. Its on/off state is a byte saved with
  your game (inside the inventory record), not a section of the executable,
  so it survives a relaunch. You turn it on in game with the **Enable Same-Sex
  Marriage** Special Upgrade, which exists only when **Cheat Upgrades** is
  ticked (see
  [Cheat Upgrades in detail](#cheat-upgrades-in-detail)), which is why it needs
  no checkbox of its own. **Corrected 2026-09-24:** this README previously
  listed it as "not offered by the bundle", which told players a working
  feature does not ship. It does ship. The bundle's settings list simply drops
  entries that have no packaged source assets, and a code-only feature has
  none -- that is a quirk of how the list is built, not a missing feature.
  **Corrected 2026-09-29:** this entry previously said the feature is "carried
  in the `.vf2same` section". No B196 executable has a `.vf2same` section; the
  toggle moved into the saved inventory byte because a section byte reset on
  every relaunch.
- **Transparent Store Bar** genuinely is not applied. Unlike the above it is a
  pure image swap, and its replacement image (`main_no-comm.png`) lives in the
  `OptionalVisualMods` tree rather than in this repository, so the export has
  no art to package and nothing to apply. Absent since at least B174.1.

Do not confuse **Transparent Store Bar** with **Store Scroll Bar**,
**Transparent Menu Bar** or **Transparent Decor Tab**. Those are three separate
settings, and all three *are* present and enabled by default in B196 --
verified against the shipped `manifest.json`.

### Main patches (on by default)

- **Patch game executable** - verifies a vanilla `Virtual Families 2.exe` and writes a clearly labeled modded EXE into a separate modded folder.
- **Add mobile Holiday furniture** (on) - mobile Holiday furniture records and generated assets. **All 28 pieces work in play, the Christmas trees included** (confirmed by the owner, 2026-09-24), and all 28 ship their own placement maps. **Corrected 2026-09-24:** this entry previously read "decorative for now". That was wrong twice over. It implied the whole set was inert, and it rested on a generator comment saying the two Christmas trees get deliberately emptied maps -- but the shipped maps are not empty. **Corrected again 2026-09-29, with the maps decoded per setting:** this setting on its own installs placement maps with **0** occupied cells for all 28 pieces (so, on its own, the set really is decorative). The occupied maps come from **Add mobile furniture behaviors**, which replaces 23 of them -- `ChristmasTree1.png.fmap` with 14 occupied cells and `ChristmasTree2.png.fmap` with 13. The Candy Cane, Christmas Cookie, Poinsettia and both Wreaths keep empty maps in every configuration. The earlier figures here ("11 occupied cells each, more than the 7 in a working Wreath") matched no shipped configuration. The owner's in-play confirmation stands: it was made with both settings on, which is the default.
- **Add Holiday outfits** - Holiday outfit body values and runtime frames; needed for Holiday rows in the expanded Outfit store.
- **Add expanded Outfit store** - Outfit store rows for body values 0-49, icons, independent tray items, and body-field sync.
- **Add additional mobile-exclusive furniture** - the non-Holiday mobile furniture set.
- **Add unused pets** - restores the unused Turtle and Hamster pets.
- **Add VF3 TV assets and recognition** - VF3 TV furniture, private animation strips, and TV fmap recognition.
- **Behavior Patches** - the behavior-only executable overlay. See [Behavior Patches in detail](#behavior-patches-in-detail).
- **Text fixes** - miscellaneous string corrections.
- **Fix Vanilla Game Bugs** (`.vf2bugs`, on) - fixes bugs in the original game's menus, its tool-tray outfits, a startup crash and an overlong server error text. You can untick it to get the stock behaviour back; it is one byte in the patched executable (plus, for the outfits, the companion DLL that byte loads), not a separate build.
  - **Start Over** on the title screen asks "Are you sure you want to restart the current game?" before starting a new village, instead of continuing the current one.
  - **Settings > Pause Game: Yes** while the game is already paused no longer leaves it stuck paused after one Space press. The stock game added the pause offset a second time.
  - The invisible **Change Player** click spot a little above and left of the title buttons (the Manage Games button's old position) is removed. Manage Games itself still opens Change Player.
  - The title screen refreshes every time you arrive on it, and again when Manage Games or the new-player name prompt closes. It shows the current player's name, keeps the **Manage Games** button (the stock game dropped it for the rest of the session after the last player was deleted), and labels the first button **Play** or **Continue** according to whether a village exists.
  - **Startup crash** (after B204; executables built after it carry the fix): at every start the game asks LDW's server to log in (`ldwsoftware.com/game_backend/login.php`, later `message.php` and `poll.php`), and its one reply reader reads up to 2,048 bytes into a 2,048-byte buffer and then writes an end marker one past the last byte read. LDW's server now answers with the PHP script's own source (about 3 KB), so the marker landed past the buffer and the game closed itself (error 0xC0000409) about 20 seconds after it started, whenever the reply arrived. Now the reader takes at most 2,047 bytes, so the marker always fits, and a reply that filled the buffer (cut short) or begins with `<` (a script or a web page; the server's real answers are JSON or plain text) is handed on as no reply, the path every reply handler (log in, messages, polls, votes, promo codes) already takes when the server does not answer. A short real answer is handed on unchanged. The callback was run under emulation, with a 3,125-byte PHP reply and with short real-looking answers (`tests/test_server_reply_guard.py`); **not yet tested in a running game.**
  - **Server error text** (B205): when a server answer carries an error, each of the six reply handlers (log in, messages, polls, votes, promo codes, purchases) writes a "Server error" note with that error text into a 256-byte stack buffer with an unbounded `sprintf`, so an error text longer than about 220 characters ran over the stack cookie and the game closed itself (0xC0000409). Now that one call goes through a bounded format (256 bytes, always terminated), so the note is cut to fit; a note that fits is byte for byte the original. LDW's server sends no such answer today. Every handler was run under emulation with a 1,000-character error and with short ones (`tests/test_server_error_text.py`); **not yet tested in a running game.**
  - **Outfit pictures** (B204 in-place update; executables built after it carry the loader): every **Male Outfit** and **Female Outfit** in the tool tray keeps the picture it was bought with. In the original game buying an outfit copies its picture into one field per sex and the tray keeps only the item and its uses, so every outfit of a sex in the tray showed, and put on, the last one bought. A companion DLL (`vf2outfits_b200.dll`, in the Virtual Families 2 Patcher Files folder; its loader rides this setting's `.vf2bugs` byte) keeps each tray place's own picture: set when it is bought, moved with it when you rearrange the tray, used for its picture in the tray and in your hand, and given when you drop it on a family member. Each save's pictures are kept beside it in `Virtual Families 2 Patcher Data\Outfits\<save file>.dat` in the save folder (versioned and checksummed, written after the game saves, used only when it describes the save just loaded; the game's own backup of the previous save keeps its own). The save file itself is not changed. Outfits bought before the fix, or in a save without the file, show and give what they did before; a damaged file is moved aside and a file another program holds is never replaced. The patcher's own expansion outfits and hairstyles work as before. Every step was run on the B200 code under emulation (`tests/test_b200_outfit_pictures.py`); **not yet tested in a running game.**
- **Add visible mobile version purchases** - Brokerage Account, Food Club, Health Plan, and Lucky Rock rows under Special Upgrades.

### Optional patches

**Choosing a set.** Above the list are the Virtual Villagers patcher's four buttons, each with a **?**:
**Select All Patches** (everything but Experimental), **Default Patches** (the defaults below), **Owner's
Defaults** (everything except Up to 28 Children: every cheat and both invisible-furniture settings, the
transparent swap overriding the visible graphics) and **Deselect All Patches**. **Patch Selection
Settings...** opens a window with a search box and one tick box per patch; **Tick These** / **Untick These**
apply the chosen patches, ticking what each needs (or unticking what needs it) as a click does.

**Cheats are off by default** (owner, 2026-11-01: "anything that sets prices to 0 is DEFAULT OFF";
"Anything that makes villagers succeed in skills 100%, no failing, is DEFAULT off"; "Keep off by default: All
items show in flea market/outfits/hairstyles"): **Cheat Upgrades**, **Free and Guaranteed Cheats**, **All 36
Flea Market goods** and **All outfits and hairstyles always for sale**. Every content setting and every paid
upgrade stays on. Next build: 43 settings, 37 on by default; the six off are those four, **Swap Invisible
Furniture Graphics with Transparent Graphics** (place the furniture first) and the Experimental **Up to 28
Children**. **No AI Icons** keeps its default, but it only reskins Cheat Upgrades rows, so it takes effect
(and the GUI ticks it) when Cheat Upgrades is ticked.
**Fixed with it:** in every B205-and-earlier executable built without Cheat Upgrades but with Mobile
Renovations, the store's House Renovations page listed only 10 of its 30 rows and Special Upgrades listed 30
rows where it has 10 (20 read past the end of the list). Both pages are right in the next build.

B205's 41 settings (as in the final B204 rebuild): 39 arrived enabled and two arrived
off (**Swap Invisible Furniture Graphics with Transparent Graphics**, and the
Experimental **Up to 28 Children**). (The first B204 bundles: 39 settings, 37 on. B204 as first published: 36 on, with the Family History log off.) (B202 and B203: 38 settings, 36 on.) (B198 through B200: 36 settings, 35 on;
B201: 37 settings, 36 on; superseded.) The
`(on)` marks below are a reading aid on entries whose default has surprised
people, **not** an exhaustive index -- an unmarked entry is not thereby off.
Uncheck anything you do not want and click **Enable/Disable Patches** to
rebuild the modded folder without it.

**Gameplay and content**

- **The startup crash that once blocked this setting is fixed and shipped.** Builds up to and including B181 faulted a few seconds after launch, before reaching play, whenever **Add mobile furniture behaviors** was enabled, and earlier revisions of this README told you to leave the setting off. That no longer applies: the setting is **on by default** in the current release and the crash does not occur. The cause was a skipped register restore -- an injected branch jumped into a stock epilogue past the instruction that restores a saved register, so the following restores took the wrong stack slots and the villager pointer ended up in the wrong register. The fix adds that restore on the injected path, and was confirmed in a built game rather than only in source: the corrected executable ran with the setting enabled without faulting, while an unfixed build in the same install still faulted within seconds. **The old "leave this setting off" instruction is superseded and is recorded here only so the history stays legible.** See `docs/Transparency Log.txt` for the measurements.
- **Add mobile furniture behaviors** (on) - ported actions for genuine mobile furniture: weather-aware loungers, the Patio Umbrella and tables, Picnic Table, Birthday furniture, and the Holiday pieces. Ships 34 behavior maps and is gated by a one-byte `.vf2beh` runtime flag that is zero until the setting is enabled. It also carries the spa treatments on the two Spa Loungers - see [Spa treatments](#spa-treatments). The Picnic Table and Patio Table behaviours run. The meal and drinks did **not** appear on them in B181 and earlier: the two props are ids the desktop engine's prop array does not hold, so the state is tracked outside it and the draw had to be added from scratch. Four separate defects kept it from working and all four are now fixed in source -- the image descriptors were reserved but never populated, so the sprites could not be resolved at all; the draw hung off a call inside a per-prop branch, so it only ran while an unrelated stock prop was active; the position came from `info.point`, which is the tile a villager stands on rather than the table itself; and the draw used the `AddDecal` overload that has no bounds check. **Shipped in a built binary since B182, and partly confirmed in play.** The fixes have been through every matrix build since, so they are present in the released executables. The owner has since seen both props draw in play -- initially misaligned and behind the furniture -- and B189's playtest table records the **Patio drinks prop position as GOOD**. The **Picnic Table meal prop is confirmed in play too** (2026-09-24), so both props are now confirmed to draw. Since 2026-09-30 the props follow the mobile game's rule: while a picnic or drinks are ready, every picnic or patio table (visible or invisible) shows them, not only the table nearest the villager who prepared them; each table keeps its prop for up to 300 game seconds, and one table is cleared when the 240-second readiness ends. A child or a low-food drop on the Picnic Table now says "This person is too young!" / "Worried about food" like the Patio Table (it previously said "Playing in puddles", and the low-food refusal used an id that on PC belongs to an unrelated patcher-added string). Not yet confirmed in play.
- Playtest follow-up as of B183, kept for the record: the Exercise Bike and Home Gym venue handlers now apply their own labels even when the borrowed donor keeps its native label, while preserving the donor animation and duration. Spa receiving now uses the stock SleepNW/SleepNE strips after a short settle and walks to a small upward-adjusted target. The B183 generated executable was startup-smoke tested from its self-contained package for 15 seconds with zero new matching Windows Application Error/WER events. **All of it has since been confirmed in play.** The owner verified the Spa Lounger receiving pose against the furniture (the remaining spa defect closed in B191), and reports the Exercise Bike and Home Gym System working as described.
- **Use mobile sound assets** (on) - stages the 67 hash-pinned mobile behavior sounds and repoints the four PC WAV routes that must load OGG.
- **Add Holiday Ornaments collection** (on) - 12 yard collectibles, six Collections Chest pages, the Ornamentologist and six-family goals, Lucky Rock rarity odds, and The Collector offer/sell handling.
- **Add mobile-exclusive Random Events** (on) - all 25 authenticated mobile-exclusive Random Event records with their text and choice/result dialogs. Also restores the PC game's unused Virtual Scouts event as a random event: "OK" makes everyone celebrate and gives each villager +5 happiness; "What rats?" costs 100 food. The Power Failure event's "Take a chance" now has a 1 in 4 chance that "The food was not ok.", giving each villager a 15% chance of an upset stomach.
- **Add mobile room renovations** (on) - 15 verified mobile renovation images (5 Bathroom 1, 3 kitchen, 5 office, 2 workshop) at their exact room-map positions, plus their store icons and the five shower-curtain variants. Bathroom 2's own art is not here: it is AI-generated and ships under **2nd Bathroom Mobile-Style Renovations** instead, so that a player who declines the AI art still gets every genuine mobile renovation.
- **2nd Bathroom Mobile-Style Renovations (AI-Generated Art Warning)** (on) - AI-generated Bathroom 2 art, hand-edited, based on the Bathroom 1 mobile renovations. Labeled with an art warning in the GUI. **Requires Add mobile room renovations**: the Bathroom 2 renovations exist only in that executable, so the art is not installed while it is off.
- **Cheat Upgrades** (**off by default** from the next build) - the cheat-only executable overlay, adding 43 Special Upgrade rows. Three of them (Force Successful Pregnancy, Anti-Spam Software Ownership, Rockhound Certificate Ownership) are listed only with **Free and Guaranteed Cheats** ticked too. See [Cheat Upgrades in detail](#cheat-upgrades-in-detail).
- **Free and Guaranteed Cheats** (`.vf2free`, **off by default**; new after B205) - unlocks exactly: the **Force Successful Pregnancy** row (the next try for a baby always passes its pregnancy roll), the **Anti-Spam Software Ownership** row ($0) and the **Rockhound Certificate Ownership** row ($0), all three on the Special Upgrades page of a Cheat Upgrades executable; and a **free Time Warp** in Time Controls. Unticked, those three rows are not listed and every other row is listed in the same order (the same store-page hooks as All 36 Flea Market goods answer the page; nothing in a save changes, so a Force Successful Pregnancy bought earlier stays armed). Emulated on branch builds (`tests/test_store_page_gates_exe.py`); **not live tested**.
- **All outfits and hairstyles always for sale** (`.vf2clth`, **off by default**; new after B205) - ticked, the Clothing and Hairstyles page lists every outfit and all 100 hairstyles (214 rows), as every earlier build did. Unticked, it is the original six rotating outfits (which already cover every base body) plus 6 rows drawn from the 100 hairstyles and 8 holiday outfits, keyed to the game's own outfit pick time, so they change when the six outfits do (every 4 game hours, a new family, or R). Items already bought keep working; nothing is saved. Emulated on branch builds; **not live tested**.

**Experimental rule changes** (each gated by its own one-byte runtime flag, which stays
zero until you enable the setting -- note the SETTINGS themselves ship enabled in the
release bundle, like almost everything else)

- **Allow Older Pregnancies** (`.vf2preg`) - normal fertility below 50, then a chance that tapers from 10% at 50 to a 0.1% floor at 69+; Next Generation also unlocks at 60 with a surviving child.
- **Allow Same-Sex Marriage** (no settings row; see [What's included](#whats-included)) - flips only the spawned candidate's gender field when the in-game **Enable Same-Sex Marriage** Special Upgrade is on; same-sex spouses keep native private romantic time and never become pregnant. **Corrected 2026-09-29:** listed here before as a `.vf2same` one-byte runtime flag. It is not one -- its state is a byte saved with the game, turned on and off by the Cheat Upgrades row.
- **Older Villager Mortality Curve** (`.vf2mort`) - replaces only the annual old-age death roll with a calibrated curve that accelerates past effective age 110. Active food groups still subtract 0-4 effective years. No hard maximum age.
- **Store Scroll Bar** (`.vf2scrl`) (on) - adds a scroll bar to the store.
- **All 36 Flea Market goods** (`.vf2flea`, an Optional patch; on by default in B204-B205, **off by
  default** from the next build; new in the final B204 rebuild) - the store's Flea Market lists all 36 of its goods at all times, as every patched build before
  it did. This used to be
  built in; it is now one byte in the patched executable read by the two Flea Market hooks
  (`VF2GetExpandedFleaMarketCount` / `VF2GetExpandedFleaMarketItem`). Unticked, both hooks step aside and the
  Flea Market is the original game's: 5 of the 36 goods, picked at random, picked again the first time the
  page is opened more than 6 hours of real time after the last pick, and each good one to a pick (the
  game's own pick sets each listed good's stock to 1). While it is ticked **all 36 goods are always in
  stock** (the owner, 2026-10-27: "Make all 36 always in stock."), whatever count the original Flea
  Market left -- a good bought while it was unticked, or in a save first played without the patcher, is
  buyable again -- and that includes the 3 goods the game stocks only one of: the Towelette, the
  Anti-spam Software and the Rockhound Certificate (earlier patched builds sold each of those once).
  Buying one of them again is the game's own purchase: the Towelette and the Anti-spam Software go to
  the tray again, one more tray item each time like any good (with a full tray the game keeps the money
  and adds nothing, as for every good), and buying the Rockhound Certificate again leaves it owned: no
  second certificate, no extra goal or fossil. No goal counts any of the three. An owned Anti-spam
  Software (installed) or Rockhound Certificate still shows its owned checkmark while it can be
  bought again. The patcher's `GetNumAvailable` hook answers "in stock" and writes nothing, so the
  save's counts are kept and count again the moment the setting is unticked.
- **Render Unicode with In-Game Fonts** (`.vf2utxt`, Optional, **on by default**; new after B205, needs the
  B206 executables) and **Use Unicode Font (overrides in-game fonts)** (`.vf2ufnt`, Optional, **off by default**).
  The two cannot be on together: ticking one unticks the other in the GUI, the command line refuses both, and the
  bundle's settings say so (`"excludes"`). Both install the companion DLL `vf2unicode_b200.dll` (the second under
  the name `vf2unicodefont_b200.dll`, so each setting removes only its own files):
  - **what the game can show**: every Unicode character (U+0000..U+10FFFF, beyond U+FFFF too): accents,
    Latin Extended, Turkish ı İ ğ ş, Vietnamese, Greek, Cyrillic, CJK, Hangul, Cuneiform, symbols and emoji, in
    every text the game draws (names, dialogs, the store, events, tips): its four fonts (Segoe24, Segoe24Bold,
    Segoe32Bold, Segoe36Bold: the only fonts the game has) have ASCII and Latin-1; 2,123 more characters per font
    are **patcher-made** (`Virtual Families 2 Patcher Files\Unicode Text\<font>.png` + `.txt`, made at export
    from the original game's own font pictures: accented letters composed from the game's own letters and accents,
    the rest drawn in the fonts' own style), and anything else is drawn when first needed from the first Windows
    font that has it (Segoe UI, Segoe UI Historic, Segoe UI Symbol, Segoe UI Emoji, the CJK fonts, Nirmala UI,
    Ebrima ..., Noto if installed) at the game font's fitted size, weight and alpha levels, else a box. Emoji are
    drawn in one colour (the text's), not in full colour;
  - **typing**: the game's text boxes take every character the keyboard sends (accented keys, dead keys, Alt
    codes, an input method); the original game drops all of them (`CheckForEvents` only passes a one-byte
    `SDL_TEXTINPUT`). A character is added only if the whole name still fits the box; Backspace removes a whole
    character (an emoji with its skin tone too); copying a name to its save field never cuts inside a character;
  - **saves**: the names stay in their own fields. Text of ASCII and Latin-1 letters is stored one byte per letter
    exactly as before (the original game and older tools show it); anything else is UTF-8. The one rule is
    `src/vf2_game_text.py`, which every patcher reader and writer uses (logs, Family Tree, Rename Family, Copy
    Player Slot, the tools). The original game shows UTF-8 names as odd letters (Ã© for é) and never crashes
    (`tests/test_vf2_game_text.py` runs its own drawing code over every byte);
  - **Use Unicode Font** draws every character, ASCII too, with Segoe UI at each game font's size (Face= in
    `vf2unicodefont.ini`), with the same fallback for missing characters, so screens keep their layout.
  - Evidence: the game's own DrawString / DrawChars / GetWidth / GetHeight / GetNextJustifiedLine run under
    emulation give exactly what `src/vf2_game_text.py` gives for every single-byte text; the DLL's own C++ text
    rules equal the Python for thousands of texts; and the DLL's DrawString, run under emulation over the real B205
    executable, draws the same glyphs at the same places with the same pixels as the patcher.
- **R Refreshes the Store** (`.vf2rfsh`, an Optional patch and a cheat, **on by default**; new in the final
  B204 rebuild) - in the store, press **R** (or Shift+R) to pick the store's random items again, the
  game's own way and with the game's own odds:
  - on the **Clothing and Hairstyles** page, the six stock outfits (Discount, Department and Designer, male
    and female) are picked again with the game's own forced pick, `CInventoryManager::MaybeUpdateOutfits(true)`,
    the one the game makes for a new family; the next timed pick moves to 4 hours of game time later, as after
    any pick. With **All outfits and hairstyles always for sale** unticked the 6 rotating hairstyle and
    holiday rows change with it; ticked, every hairstyle is listed, so they stay. An outfit already bought keeps its own
    look: the store copies the pick into the purchase, and R changes only the store's rows;
  - on the **Flea Market** page, always: the game's own pick (`MaybeUpdateRotatingItems`) happens now,
    5 new goods with the game's own stock rules, and the next one 6 hours of real time later. R always
    redraws; with **All 36 Flea Market goods** ticked you won't see a change in the Flea Market
    list: all 36 stay listed, and every one of them reads as in stock whatever count the pick left (the
    pick sets each good's stock to 1, a purchase to 0), so nothing sells out. Untick it later and the stock
    page shows the latest pick's 5 goods with their stock counts;
  - nowhere else: not on any other store page, not On Sale, not outside the store, and not while a box
    (the buy box, the bank, a message, Redeem Credit) is open, because every store box takes the keys
    first. The store screen has no text box, so typing never triggers it.
  A companion DLL (`vf2refresh_b200.dll`) in the Virtual Families 2 Patcher Files folder does the work: it
  replaces one pointer, the store screen's own key handler (found through the game's type information;
  the other screens that share the stock handler keep theirs), and every other key still reaches the game.
  The save gets only what the game itself saves for its own pick. With the setting off the DLL is not
  installed and the executable never loads it. **Not live tested yet**: proved by emulating the built
  executable and the real DLL (see `tests/test_b200_store_refresh.py`).
- **Time Controls** (`.vf2time`, an Optional patch, **on by default**; since B201) - a Time Controls button
  on the game's Settings screen opens a window to pause and resume, pick Slow, Normal, Fast, 5x or 10x, and
  Time Warp everyone at home by +3 years. **The Time Warp costs the same as the store's own Time Warp**
  (owner decision 2026-11-01; free in releases up to B205): the companion DLL (`vf2time_b200.dll`) reads the
  store's price of its Time Warp item from the game when you click it (`CInventoryManager::GetPrice`, the
  call the store's own price code makes; $2,000 in the game's table) and pays it the way a store purchase
  pays. A family with less money is told so and nothing changes (no money, no ageing); nothing is paid if
  nobody at home can age. With **Free and Guaranteed Cheats** ticked (the executable's 1-byte `.vf2free`
  section holds 1) it is free; an executable without that section charges. Pause and the speeds are
  unchanged. **Not live tested**: proved by emulating the built executables with the real DLL and the
  game's own price and money code (see `tests/test_b200_time_controls.py`).
- **Up to 28 Children** (`.vf2kids`, in the patcher's own **Experimental** section (red heading, under Optional Patches, with the warning "Experimental: not yet tested in a running game. Back up your saves before using it."), off by default; Enable All and `--enable-all` leave it off, so it is only ever ticked deliberately; added after B201, not yet in a release) - one
  generation may have up to 28 children instead of 6. Only the first 6 appear in the Family Tree, as
  before; every child, the 7th to the 28th included, can be chosen to inherit the house in Next
  Generation. Twins and triplets never take a family past 28: with 27 children a twin or triplet
  pregnancy has one baby, with 26 a triplet pregnancy has two, at 28 no more babies come, and the
  normal twin and triplet chances are unchanged while there is room. Children 7 to 28 are remembered in
  a small file beside each save (`Virtual Families 2 Patcher Data\Children` in the save folder); the
  save file itself is not changed. Virtual Families 2 natively keeps up to 6 children per generation in its Family Tree, and a household holds at most 30 villagers (2 parents and 28 children). This patch keeps children 7 to 28 in a separate file beside the save, so they never overwrite Family Tree entries; storing more than 6 children in the Family Tree itself would overwrite its entries and glitch the game. Experimental: not yet tested in a running game. Back up your saves before using it. A companion DLL
  (`vf2kids_b200.dll`) in the Virtual Families 2 Patcher Files folder does the work; with the setting
  off it is not installed and the executable never loads it. **Not live tested yet** -- see
  `docs/b200-up-to-28-children.md` for the evidence and what is not covered.
- **Family History log** (`.vf2hist`, an Optional patch, **on by default**, and Enable All and
  `--enable-all` tick it; it was Experimental and off until the 26 October 2026 update of B204;
  new in B204, whose executables carry its loader) - one Family History log per family, in the
  format of the Virtual Families 1 patcher's Family History: one dated record per event, in
  `Virtual Families 2 Patcher\Save N\Logs\Family History\Family History <k>.txt` in the save folder,
  rolling to the next numbered file after 2000 records. Each record is the Virtual Villagers patcher's
  layout: a heading `[YYYY-MM-DD HH:MM:SS] <Kind> <n>` (Conception, Birth, Death, Marriage, Divorce,
  Arrived, Left Home, Generation, New Generation, Renamed, Random Event, Evict Family, Start Over, Family
  Renamed, Family Tree), then `  Label: value` lines and a blank line; each family member is written as
  that patcher writes a villager: the name, then the age, sex, head and body. It records
  marriages and remarriages, same-sex ones included (naming the current spouse and the earlier one, and
  whether that one died or was divorced), spouses lost to divorce (the patcher's Divorce Spouse) or death,
  every conception and birth (twins and triplets marked, with both parents), every death with the game's own
  cause and the person's age, children who join (Adoption Services, The Little Visitor) or leave home
  (college, Boarding School, The Talent Scout), each new generation and its heir, a rename in the Details
  box, a new family, Start Over and Evict Family, and every Random Event as `Email Event: <subject>` or
  `Popup Event: <title>`, the text its dialog shows, with the choice made. Rename Family (Tools tab) adds a
  `Family Renamed` record to a slot
  that has a log. Virtual Families 2 has no family surname, so each file is headed with the player name the save holds. An
  existing family's past is filled in once from its Family Tree, marked "backfilled, no date". No other
  file is written: an earlier spouse and why they left (the game erases a childless spouse's Family Tree
  record at death, and Divorce Spouse clears it) are read back from the log's own records. A new family or
  Start Over in a save slot starts that slot's log again (a `Backups` folder in it is kept); Evict Family keeps it. The
  save file is not changed. A companion DLL (`vf2history_b200.dll`) in the Virtual Families 2 Patcher Files
  folder does the work; with the setting off it is not installed and the executable never loads it.
  **Not live tested
  yet** -- see `docs/FAMILY_HISTORY.md` for every hook, its evidence and what is not covered.

**Asset and UI mods**

- **Virtual Families 3 Furniture** - VF3 furniture imports, including the plaid/striped/flowered living-room set.
- **Add Custom Couches and LDW Posters** - custom couch colourways and the LDW poster set.
- **Add Invisible Furniture - Visible Graphics** and **Swap Invisible Furniture Graphics with Transparent Graphics** - the invisible furniture set, with a companion setting that swaps in fully transparent art. Nine outdoor pieces: the Kiddie Pool, Full-Size Pool, Hammock, Picnic Table, Patio Table, Yoga Equipment, Lounger, Spa Lounger, and (B193) Ping-Pong Table. Each borrows its donor's placement map byte for byte, so villagers treat it as they treat the piece it was cut from. Before B180 that was true only of the donors the base game ships: a borrower whose donor is one of the 34 maps Mobile Furniture Behaviors implements silently received the raw mobile map instead of the desktop-safe one, which is why villagers used the invisible Spa Lounger and Lounger wrongly. B180 routed those borrowers to the donor's desktop-safe map, which fixed the peep-slot anchors but also left them with almost no collision geometry: that map is deliberately sparse, which is correct under the donor's own name and not usable as a borrower's only map. The Patio Table borrower fell from 241 occupied cells to 8, the Picnic Table from 237 to 8, and both loungers from 154 to 12. A borrower now keeps the donor's geometry and takes only the translated anchors, so it has both. The donor's own map is unchanged. See `docs/discoveries.md` for the measurements.
- **Four new visible furniture items** - Exercise Bike, Home Gym System, Ping-Pong Table, and Spa Lounger. These are ordinary store items with their own art, each built on the same donor arrangement as the invisible pieces above. Until B180 none of them did anything when a villager was dropped on one: this patcher's drop dispatcher matches on item id, and only the Invisible Spa Lounger was ever listed, so every other added piece had no route at all. Their records and placement maps were correct and simply never consulted. B180 gives the **Spa Lounger** a route of its own. The **Exercise Bike**, **Home Gym System**, **Ping-Pong Table** and the Yoga Equipment now each have villager actions of their own as well, described under "Actions for the added furniture" below. That replaces an earlier arrangement in which three of them borrowed a base-game action and relabelled it, and the Home Gym System had no action at all -- it was reported in play as doing nothing, which was accurate, because the Yoga Equipment it was modelled on consults no furniture in the base game. Those are actions a villager chooses on their own. **All of these drop routes are now confirmed in play by the owner** -- see the end of this entry. Which of them has a drop route of its own depends on **Behavior Patches** -- the behavior-only executable overlay, not **Add mobile furniture behaviors**, which is a separate setting with its own `.vf2beh` runtime flag. With Behavior Patches off, only the Spa Lounger does, and the others rely on the game's native hotspot path, which dispatches on a hotspot rather than on an item id and so cannot tell one added item from another. With it on -- it is on by default -- the Exercise Bike, Home Gym System, Yoga Equipment and Ping-Pong Table are each matched by exact item id before the stock hotspot is consulted, so a drop on one reaches that item's own action. That routing is present in the emitted source. The owner has confirmed in play that dropping a villager on the Spa Lounger, Patio Table, Picnic Table, Exercise Bike, Home Gym System, Ping-Pong Table, Lounger and Yoga Equipment -- visible and invisible alike -- reaches those items' own actions (B195 fixed the case where transparent art stopped the drop resolving at all). **No added-furniture drop route is outstanding.**
- **Invisible Workspace Upgrades** - invisible variants of the workspace upgrade props.
- **Invisible furniture counts as the real thing** (B199, every patched executable). A few places in the base game check for one exact store item rather than for a kind of furniture, so the invisible copy of that item did not count. They now accept the invisible copy too:
  - **Goals:** "Staying cool in the pool" completes when you place an Invisible Kiddie Pool or Invisible Full-Size Pool, and "Let's dance" when you place an Invisible MP3 Player. Both are confirmed in play (a village whose only pool or music player was the invisible one).
  - **Kiddie pool play:** children splash and play in an Invisible Kiddie Pool on their own, as they do in the stock one (the two activities required the stock pool by item number).
  - **Happiness:** villagers who like music, swimming or resting get the same happiness bonus from the Invisible MP3 Player, the invisible pools and the Invisible Hammock as from the stock pieces.
  - **Clicking the Invisible MP3 Player** plays its music even when no stock MP3 player is placed.

  Everything else already treated the invisible pieces like their stock versions: the furniture a villager chooses on their own is recognised by the kind of object it is, which the invisible copies share, and every route this patcher adds lists both. A sweep of the base game for every invisible item's stock id (2026-10-01) found only the places above.
- **Lorsieab2's Custom Map Images** - replacement map art.
- **Transparent Menu Bar** (on) and **Transparent Decor Tab** (on) - UI chrome transparency. A third transparency setting, **Transparent Store Bar**, is defined but is not in the bundle; see [What's included](#whats-included). (**Store Scroll Bar** is a separate thing entirely -- it *adds* a scroll bar to the store rather than making anything transparent, and is listed under the experimental rule changes above.)
- **White Birds** - recoloured birds.
- **Glowing Collectibles** - makes collectibles easier to spot.
- **Misc Graphics Fixes** - assorted art corrections.
- **Add loose optional visual mod graphics** - drops the loose optional visual mods into the modded folder.
- **Add optional song mods** - optional music replacements.
- **No AI Icons** - requires Cheat Upgrades; swaps the late Special Upgrade icons for non-AI artwork.

**Almost everything in the release bundle is on by default.** From the next
build, 37 of 43 settings arrive enabled when you pick **Default Patches**; the
six off are the four cheats above, **Swap Invisible Furniture Graphics with
Transparent Graphics**, and **Up to 28 Children**, which is Experimental and
which **Select All Patches** leaves off too (B205: 39 of 41 on). The `(on)` marks below are therefore not an exhaustive index --
they were added to entries where the default has surprised people, and an
entry without one is not thereby off. The shipped `manifest.json` is the
authority, and the GUI shows each setting's real initial state. Unticking a
content setting removes its art, placement maps and sounds, but **not** its
store rows: the furniture, outfit and hairstyle rows are compiled into every
patched executable, so they stay listed. Base-game autonomous behavior choices
and likelihoods are left alone except where a patch documents otherwise --
and Behavior Patches does change several stock likelihoods; see
[Behavior Patches in detail](#behavior-patches-in-detail).
**Corrected 2026-09-29:** this paragraph used to say "Every optional feature
is absent when its setting is off", which is untrue of the store rows. As of the audit date above the owner has confirmed
in play: every added-furniture drop route, the Home Gym's caption variation,
the Cheat Upgrades (including Same-Sex Marriage and Reroll of Marriage
Candidates) and the room renovations. The **Picnic Table meal prop** and B196's
**raised ping-pong frequency** are confirmed in play as well, so of the
features this audit examined nothing is left awaiting in-game confirmation. `docs/REQUEST_LEDGER.md`
records the per-request status and `docs/Transparency Log.txt` records the
disclosures.

### Known issues

- **A rare crash when dropping a villager on the Patio Table during bad
  weather, with the drinks prop already drawn.** Reported once on B196 and
  tracked as issue #378. It has **not** been reproduced since -- the same steps
  on the same save now refuse correctly with "Don't like the weather!" instead
  of faulting -- so no fix has shipped, because there is nothing yet to verify
  a fix against. What the single crash dump does show: the fault is a
  data-execution violation inside the game's own stock drop handler, reached
  through a table index past the end of the range that handler initialises.
  If you can reproduce it reliably, please say so on #378; a reproduction is
  the missing piece.

## Cheat Upgrades in detail

Enabling **Cheat Upgrades** adds 43 rows under Special Upgrades. **All 43 are
free.** **The owner confirms the Special Upgrade rows work in play
(2026-09-24).** **Corrected 2026-09-29:** this used to say Enable Same-Sex
Marriage and Allow Reroll of Marriage Candidates cost 10,000 coins each. Both
have been free since PR #95 ("Make every Cheat Upgrade free"); the build sets
their catalog price to 0 and a test pins it.

The toggle rows and the armed pregnancy one-shots are cancelled by buying them
again: an armed one-shot shows a checkmark, and arming one clears the rows it is
mutually exclusive with. **Divorce Spouse is not one of them.** It takes effect
the moment you buy it and saves immediately, so there is nothing to cancel and
buying it again will not bring the spouse back.

**Money**

| Row | Effect |
| --- | --- |
| No Money | Sets coins to 0. |
| Add 100 coins | Adds 100 coins. |
| Add 10 thousand coins | Adds 10,000 coins. |
| Add max amount of coins | Sets coins to the game's maximum. |

**Food**

| Row | Effect |
| --- | --- |
| No Food | Sets food to 0. |
| Add 100 food | Adds 100 food. |
| Add 10 thousand food | Adds 10,000 food. |
| Add max amount of food | Sets food to the game's maximum signed amount. |

**Store**

| Row | Effect |
| --- | --- |
| Unlock everything in the store | Unlocks every generation-locked store entry across all categories. Buy again to restore the original locks. |
| 2x Prices | Everything in the store costs twice as much. |
| 5x Prices | Everything in the store costs five times as much. |
| 100x Prices | Everything in the store costs an insane amount. |
| Reset Price Multiplier | Restores original calculated prices. |

Price modes affect every purchase routed through the store price calculator.

**Achievements, puzzles, and collections**

| Row | Effect |
| --- | --- |
| Reset Achievements | Resets all goals and progress. |
| Complete all Achievements | Completes every currently enabled achievement and awards its normal coin reward. |
| Reset Ants | Resets the ants puzzle so it can be completed again. |
| Reset all collections | Removes every collected item and resets collection progress. |
| Complete all collections | Completes every collection and its related achievements. |

**House and yard**

| Row | Effect |
| --- | --- |
| Trigger all house malfunctions | Causes all possible malfunctions, including sink/toilet leaks and oven/dryer fires. Useful for the "Handyman" goal. Makes the Router offline. |
| Fix all house malfunctions | Fixes every active malfunction and brings the Router back online; clears all 11 malfunction props without resetting ants. |
| Fill available house slots with trash | Spawns 15 pieces of house mess: 5 dirt smudges, 5 socks and 5 wrappers through the native spawners, cycling every sub-type (the cycle carries over between presses, so all six sock sub-types are reached); stops early when the 30 mess slots are full. Will not work if the Maid is active. |
| Clean House | Removes the same four indoor mess categories as the stock Housekeeping Services event. Yard weeds and the laundry-room sock pile are preserved. |
| Fill available yard slots with weeds | Spawns 15 weeds cycling all four weed types through the native spawner (4/4/4/3 per press; the cycle carries over between presses, so the type that gets three rotates); stops early when the 30 mess slots are full. Will not work if the Gardener is active. |
| Clean Garden | Removes every weed from the yard without affecting other collectables. |
| Max out sock pile | Sets only the laundry-room sock pile to 1,000,000 socks. (Earlier builds set 2,147,483,647, which could break the three sock-laundering goals. Every executable now repairs such a save when it loads: negative laundering-goal progress becomes 0 and an oversized or negative pile becomes 1,000,000. Healthy saves are not changed.) |
| No sock pile | Clears the laundry-room sock pile without awarding sock-laundering progress. |

The Dryer lint fire remains a legitimate native random malfunction and requires a Dryer.

**Marriage and family**

| Row | Effect |
| --- | --- |
| Force Marriage Email | Queues a normal base-game marriage proposal with native candidate rules. |
| Enable Same-Sex Marriage | Toggle. Enables same-sex marriage candidates. The feature is built into every patched executable; this row (and so Cheat Upgrades) is what turns it on. |
| Allow Reroll of Marriage Candidates | Toggle. Lets Reject generate a new candidate until Accept is clicked. |
| Divorce Spouse | One-shot action. **WARNING: permanently removes the spouse from the Family Tree and House.** |

**Pregnancy one-shots**

| Row | Effect |
| --- | --- |
| Force Successful Pregnancy | Makes the next eligible try-for-baby attempt pass its pregnancy roll. Stays armed until the native birth routine succeeds. |
| Next Babies Male | Makes every baby in the next successful birth male. Replaces the Female one-shot. |
| Next Babies Female | Makes every baby in the next successful birth female. Replaces the Male one-shot. |
| Next Pregnancy Singleton | Makes the next successful birth one baby. Replaces Twins/Triplets. |
| Next Pregnancy Twins | Twins when two child slots are available, otherwise safely uses available capacity. |
| Next Pregnancy Triplets | Triplets when three child slots are available, otherwise safely uses available capacity. |

**Wellbeing** (each applies to everyone currently in the house)

| Row | Effect |
| --- | --- |
| Clear All Illnesses | Cures every symptom and infection, clearing the same illness fields the game clears itself. Changes no other part of a villager: food groups are kept (before the 27 October 2026 B204 update it also cleared them). |
| Max out Happiness Bar | Fills the Happiness bar. |
| Max out Energy Bar | Fills the Energy bar. |
| Max out Fed Bar | Fills the Fed bar, so nobody is hungry. |
| Max out Health Bar | Fills the Health bar. Does not revive anyone who has already died. |

**Stock Flea Market ownership toggles**

| Row | Effect |
| --- | --- |
| Anti-Spam Software Ownership | Installs or uninstalls the Anti-spam Software without using a computer. Buy again to switch it back. |
| Rockhound Certificate Ownership | Grants or removes the Rockhound Certificate, which lets the family dig for fossils. Buy again to switch it back. |

### Which store rows show a checkmark

The store draws a checkmark on any row it has nothing left to sell. For rows
whose "active" is a state you can be in and come out of, purchase history is
the wrong question, so those rows are answered from live game state instead:

- The four Special Upgrades, each checked against the state it actually sets --
  Brokerage Account against the banking interest rate, Food Club and Lucky Rock
  against their own flags, and Health Plan against the saved entitlement.
- Unlock Everything In The Store, checked by asking whether every lock is in
  fact open.
- The three price multipliers and Reset Price Multiplier. These are mutually
  exclusive, so at most one multiplier ticks, and Reset ticks when none is in
  force.
- Enable Same-Sex Marriage and Allow Reroll Of Marriage Candidates, both plain
  toggles.
- Force Successful Pregnancy, Next Babies Male/Female, and Next Pregnancy
  Singleton/Twins/Triplets, read from the armed-cheat mask.
- Anti-Spam Software and Rockhound Certificate ownership, read from the game's
  own ownership state rather than from the purchase.
- Every house renovation -- the ten native rows, and both added renovation
  catalogues, each of which carries its own active byte.

Only the drawing is affected. The click path still reads the real answer, so a
reversible row stays clickable: buying Unlock Everything a second time restores
the locks, and buying a different multiplier still switches to it.

Unlock Everything In The Store is saved with the village and re-applied when
the save is loaded; it used to reset silently on every relaunch. Cheat state
saved with a village -- the store unlock, the armed pregnancy rows, and the
Same-Sex Marriage and Reroll toggles -- is acted on only by an executable built
with Cheat Upgrades. An executable without them keeps the base-game store locks,
pregnancies, marriage candidates and Reject button, and the saved state comes
back when you return to a Cheat Upgrades executable. A same-sex marriage that
already exists keeps working in every executable.

The two Flea Market rows themselves are untouched base game, and both are independently repurchaseable in every patched executable — including saves where the effect flag is already cleared. Elsewhere, rebuying the Maid or Gardener fires that worker, and rebuying an owned house renovation returns it and rebuilds the native content map so it can be purchased again.

## Current furniture-routing status

The current source routes the Exercise Bike, Home Gym System, Yoga Equipment,
and Ping-Pong Table by exact item id on manual drop. Their own behavior
handlers reuse donor animations and durations, but donor `PlanToGo` calls are
hooked so the selected placed-item destination survives. No ownership check
gates the donor behavior; with no matching placement, the native donor action
falls through unchanged. The current main playtest was regenerated from
current `main` with behavior
patches enabled, and its complete package passed a 15-second startup smoke
test. The owner has since confirmed every one of these drop routes in play
(see **Four new visible furniture items** above). **Corrected 2026-09-29:**
this paragraph previously ended "In-game/player QA is still separate and not
complete", which those play confirmations superseded.

## Spa treatments

Dropping an adult on a **Spa Lounger** or an **Invisible Spa Lounger** starts a
treatment. One villager receives and another gives, and the two halves are
deliberately not symmetrical: receiving can also start on its own through the
autonomous table, while giving is manual-drop only. Giving needs a second
villager already receiving on that same lounger, and autonomous selection picks
one villager at a time, so an autonomous giver would mime a massage at an empty
chair. That asymmetry is intended, not a gap.

The route is locked to those two items by item id, in two independent places -
the drop dispatcher and the slot finder. Both matter. Every lounger in the game,
stock and mobile alike, answers to the same `eObjectChaise` object, so gating on
the object alone would send a villager to whichever chaise happened to be
nearest and have them mime a treatment on it. The slot finder walks the placed
furniture array and resolves an actual free Spa Lounger before anything is
committed.

The giving villager works for `GetRandom(11) + 55` ticks, about one real
minute. The receiving villager settles against that same tick budget and then
holds the sleep strip for `GetRandom(180) + 180` animation frames — the
hammock's own rest length — because `PlanToPlayAnim` counts frames, not ticks,
and sizing the strip from the leftover ticks is what used to make the receiver
get up while the giver was still working (fixed in B191). The receiver's rest
starts when they lie down and is not re-planned when a giver is dropped on
them later, so a giver added in the last moments of a rest can outlast it.
The receiving villager takes the nap's own posture, chosen from the placed
lounger's orientation rather than assumed, so a lounger set the other way round
does not have someone lying across its arm. When the rest ends the receiver
plays `gulpahh_01.ogg` once, gains 2 dirtiness and **recovers** 7-11 energy; the
giver's plan is the work interval alone, with no sound, dirtiness or energy
change. **Corrected 2026-09-29:** this used to say "both halves pay dirtiness
and energy" and that the sound "plays periodically through the treatment";
neither matches the code, which plays it once, after the rest.

One honesty note on the duration: it was written to the nap's pattern, and the
byte-level provenance was not re-confirmed against a native `TakingANap` symbol,
which does not appear under that name in the checked-in disassembly. Treat it as
matching the nap's form rather than as read out of the native routine.

## Behavior Patches in detail

**Behavior Patches** mainly does two things: it adds behaviors to the villager
AI's autonomous candidate table, and it varies the visible action text of
behaviors that already exist. For those two, the candidate keeps its native
object search, walking, animation, sound, and failure handling, and only
selection eligibility and the displayed label change.

Three parts of the patch go further than that, and are described in
**Substantive changes** below: the hammock rest builds its own plan sequence,
six-child private romantic time changes an outcome, and the computer drop gains
a choice it did not have.

**Stock likelihoods this patch changes**

Several candidates in the lists below are ones the base game **already** lets
villagers choose on their own. For those, Behavior Patches does not only keep
them selectable: it replaces the base game's weight with its own fixed value,
which also removes the base game's per-villager +/-20% variation. Decoded from
the base game's `InitAI` and the B196 Behavior Patches executable (**recorded
2026-09-29; whether these cuts are wanted is the owner's decision**):

| Candidate | Base game | With Behavior Patches |
| --- | --- | --- |
| Heat up food (`0xD5`), Look for snacks (`0x25`) | 10000 | 450 |
| Get a drink (`0x19`) | 4000 | 450 |
| Watch TV (`0x3E`) | 4000 | 650 |
| Browse the web (`0x5A`) | 3300, from age 14 | 650, all ages |
| Nap on the couch (`0x83`) | 3000 | 350 |
| Work out (`0x4A`) | 3000 | 450 |
| Grande latte (`0xD9`) | 2000 | 150 |

The same fixed values are written again every time a family is loaded, so a
weight changed by praising or scolding a villager does not survive a reload.
Earlier text in this section said the candidates keep everything native and
"only selection eligibility and the displayed label change"; for the weights
above that was not the whole story.

**Made autonomously selectable**

- Hammock anchored rest (daytime, in normal weather or Sunny -- the sun-beam weather Bottled Tropical Sunshine produces -- only, never in Foggy, Raining, Stormy or Snowing weather; and -- the base game's own rule, kept deliberately -- only when the villager is tired: energy 65 or lower; a manual drop has no such limit), warming hands by and watching the fireplace, pinball / slots / pachinko / pool table / foosball, and random radio or MP3 dancing/listening — all ages.
- Playhouse and playground (daytime only), playing quietly at the kids table, drawing at the easel, the sandbox, the toy train table, and "driving like a grownup" — children only.
- Mending a button and ironing clothes — from displayed age 14.
- Kitchen, office, and workshop career work are *not* on this list: the stock game already chooses them on its own, and Behavior Patches leaves their selection weights, praise training and age/career gates exactly as vanilla, so career progress works as in the unpatched game. Only their captions vary. (Up to B196 the patch reset these weights at every load, which erased the praise that drives career progress.)
- Checking weight, playing video games, browsing the web, watching TV, getting a drink, heating up food, looking for snacks, preparing a meal, bookshelf reading, showers and baths (including the north shower), coffee/tea and the rare grande latte, cocktails, the trampoline, board games, the swimming pool, watering flowers/roses/window boxes, bathroom sink washing and grooming, the telescope, working out, breakfast, teen homework, and teen online exams.
- **Working out, the Home Gym System and the Yoga Equipment in normal weather and Sunny** (the sun-beam weather Bottled Tropical Sunshine produces), never in Foggy, Raining, Stormy or Snowing weather. The base game allowed working out (and the quick workout) in normal weather only, and the Home Gym and Yoga actions, which are built on those two, inherited that rule. A manual drop has no weather limit.
- Teaching first words and the infant-care label family — nursing mothers carrying a baby only.
- **"Needs to sit down" on couches and chairs** (`CBehavior::UseCouch`, `0x189`). This is the behavior a manual drop on a couch or chair runs via `CHotSpot::Couch`, and it is enabled as its own autonomous candidate at weight 450 so the AI picks it too. The stock game has no autonomous record for it, so there is no candidate age gate; the couch requirement lives inside the behavior (it links to a free couch or chair, or does nothing). **Corrected 2026-09-29:** previously "Native couch and age gates are retained".
- **RestingBody** (`0x127`) and its resting label family. Autonomous for all ages at weight 450. Its native sittable targeting and plans are retained. When **Add mobile furniture behaviors** is also enabled, that patch runs last and raises this candidate to weight 2000, where it additionally carries the chaise sunbathing and sit-down routes.

**Label variations**

Grouped visible-label variants are applied to the native TV, web, video game, radio, reading, petting, mending, ironing, telescope, workout, career, shower/bath, coffee/tea, cocktail, pool, sandbox, toy train, playground, and snow-play routes. The wrappers preserve the original behavior plans and only change the displayed action text.

The sit-down pool is shared: the couch/chair route, the chaise route, and RestingBody's own resting labels (`Resting`, `Resting legs`, `Resting tired feet`) all draw from the same age/career/gender-aware label set. RestingBody's wrapper only substitutes a label when the native behavior actually emitted one of its three stock resting labels, so no other native label is disturbed.

**Actions for the added furniture**

Each added item has villager actions of its own rather than a variation of the
base-game item it was modelled on. The distinction matters in play: a villager
using the Exercise Bike is performing a bike action, not a treadmill action
relabelled at the last moment.

- The **Exercise Bike** has its own walking and running actions, labelled
  **Using the exercise bike** and **Doing high-intensity cycling**.
- The **Home Gym System** has its own workout action, with ten variations:
  lifting weights, doing crunches, cardio exercises, resistance training,
  strength training, aerobic exercises, endurance exercises, stretching,
  high-intensity interval training, and weightlifting.
  - **In builds before B185 a villager only ever showed one of the ten, and
    B185 contains the intended fix for that.** Whether the defect actually
    ends there was an open question for several builds, and it is now
    answered: the owner has confirmed in play that the captions do vary. What
    was observed before the fix: all ten were built and emitted, but the
    selection was stuck, so
    whichever variation a villager rolled on their first visit was the one
    they showed for the rest of the game. Reported in play as the gym "only
    showing one action out of its full possibilities", and that report was
    accurate.
  - The cause was not the label cache, which expires correctly. The villager's
    behaviour label persists in memory after a behaviour ENDS, and the code
    that decides "is this villager already doing X" read that leftover text --
    so every later session matched it and re-used the old label instead of
    rolling again. The same defect applied to every multi-label group -- 41 of the 59 groups carry more than one label -- not only the
    gym; it was simply most visible there because the gym has ten.
  - Fixed by asking the label cache, which is keyed to the specific behaviour
    instance, whether the label still belongs to the activity actually running.
    The intended effect is that a villager who is mid-workout keeps their
    caption rather than flickering, and that a new session rolls again. That
    is what the code does.
  - **Confirmed in play.** The owner has since watched a villager use the gym
    across sessions and reports that the captions **do** vary. That is the
    in-game observation this entry spent several builds waiting for, and it
    settles the question: the fix works in the shipped game, not merely in the
    emitted source.
  - **What the static evidence could and could not show, kept for method.**
    Before that observation the entry rested only on build evidence, and it is
    worth recording why that was never enough. The fix is present in the
    emitted C++: the gym's ten string ids are in the generated source, and the
    generator the B185 build ran is byte-identical to the one on main. All 32
    B185 executables differ from the B184 build they were seeded from, which
    rules out a seeded build inheriting the previous release's binary
    untouched -- but a full relink changes every hash whether or not any
    particular feature is in it, so that showed the executables were REBUILT
    and nothing narrower. The executables *can* be examined -- the villager
    label field appears 475 times as a 4-byte immediate in the
    behaviour-patches build -- but **that signature does not discriminate**:
    B184 predates the fix and carries the identical 475. A marker both builds
    share proves nothing, so no binary check separating this build from the
    unfixed one was ever found. **Static evidence alone could not close this;
    only play could.**
  - **Claims this entry used to make, recorded rather than quietly removed.**
    Earlier drafts said the fix was "present in the emitted C++ *and in the
    shipped executables*", and that the defect held only "until B185" — a
    runtime boundary nobody had observed. **Both were unsupported when made.**
    The play confirmation above has since borne the second one out, but that
    does not retroactively make it evidenced at the time -- it was asserted
    from build evidence that could not establish it, and it happened to be
    right. They are noted here because a reader seeing only the corrected text
    cannot tell which claim was withdrawn, and because each is a conclusion
    someone would otherwise reach again from the same evidence: a
    whole-executable hash change shows a relink rather than a feature, and a
    fix being built is not the same as a defect being over.
- The **Yoga Equipment** has its own action, labelled **Doing yoga**.
- Villagers choose the Home Gym and Yoga actions on their own in normal weather and Sunny, like working out itself.
- The **Ping-Pong Table** has its own action, labelled **Playing ping-pong**.
  Villagers choose it on their own, and only while a ping-pong table is placed
  -- the candidate carries the table's own content-map object, so raising how
  often it is offered cannot make anyone play in a house without one. **B196
  raised that frequency from 450 to 3000, matching the Pool Table it was cloned
  from.** At 450 it was offered roughly a seventh as often as pool, which in
  play read as villagers ignoring the table. Both the visible and the invisible
  table count, since availability follows the object each map declares rather
  than the item id. The weight change is verified in the compiled code
  **and confirmed in play** (2026-09-24): the owner reports villagers choosing
  the table on their own at the raised frequency.

Each borrows its base-game counterpart for *animations and duration only* --
those are deliberately unchanged, and reusing them is the point. What is not
borrowed is identity: every one of these carries its own behaviour, so it is
never a branch inside somebody else's.

Two things follow, and both are worth stating plainly because they are what
makes this safe:

- **Stock furniture is untouched.** A stock Treadmill and a stock Pool Table
  behave exactly as they did before, with their own actions and their own
  labels. Nothing about them changes.
- **Nothing is gated on owning an item.** Every base-game action stays
  available to every villager exactly as before. Owning one of these items
  *adds* its action and takes nothing away; an action simply does not fire when
  its own item is not placed, so it happens at that item rather than being a
  reward for buying it.

Before this, three of these items borrowed a base-game action wholesale and
swapped the label once the villager's linked furniture turned out to be the
added one, and the Home Gym System had no action at all -- the Yoga Equipment it
was modelled on consults no furniture in the base game, so the gym could be
bought and placed and never used by anyone.

A separate fault, reported from live play on B180, kept even the label swap from
working: villagers at the Ping-Pong Table were still labelled "Playing pool".
Recovering which item a villager was at went through a point the game hands back
for a different purpose -- the tile a villager stands on to *use* something, not
the item's own footprint -- and testing that point against the footprint asks
"which furniture is the villager standing inside". For anything you stand
beside, a table included, the answer is "none", so the check reported "not that
item" for every item, every time. Each placement carries a unique handle that
the game returns alongside the match, and the record is now found by that
handle, which also keeps two tables of the same kind apart.

**Labels on the shared stock machines**

The Exercise Bike still shares its donor object with the stock Treadmill, so a
villager who reaches the bike through the stock Treadmill behaviours is
relabelled there: walking says **Using the exercise bike** and running says
**Doing high-intensity cycling**. The item is identified from the placement
record under the villager's own feet, so a villager on a stock Treadmill keeps
the stock treadmill labels even when a bike stands next to it. The Ping-Pong
Table no longer needs this: it has its own content-map object, so the stock
Pool Table behaviour only ever reaches a genuine pool table, and **Playing
ping-pong** comes from the table's own action described above.

**Superseded 2026-09-29 -- recorded rather than deleted.** Until this date the
README carried a second copy of the "Made autonomously selectable" and "Label
variations" sections at this point, word for word, followed by a section
titled "Labels for the added furniture". That section said the Ping-Pong Table
*borrows the Pool Table's behaviour* and is relabelled by a wrapper that looks
at which table the villager walked to. **That describes the arrangement before
PR #174 and is wrong for current builds:** the Pool Table wrapper
(`VF2RandomPooltableLabel`) now deliberately classifies nothing and leaves the
stock label alone, and the ping-pong caption is applied only by the table's own
action. It also said the bike was identified "by reading the placed furniture
record the villager linked to"; the current test is the placement under the
villager's feet, adopted after the linked-furniture probe put the bike's
caption on a nearby Treadmill in play.

**Substantive changes**

These three do more than change eligibility or wording:

- **Hammock rest** (`0x23`) is retargeted to a helper that builds its own plan sequence rather than reusing the native one. It links to the hammock, picks the getting-in pose and sleep animation strip to match the placed hammock's orientation, then rests for a randomised interval. Only normal weather and Sunny (the sun-beam weather Bottled Tropical Sunshine produces) allow it; Foggy, Raining, Stormy and Snowing do not. (The game's own code calls these two weathers "Sunny" and "Cloudy"; that internal "Cloudy" is the sun-beam weather, not fog.) The manual hammock drop (`0x24`) is retargeted too, for the base and the invisible hammock alike: it settles with the native drop's own orientation table and then sleeps for the same long interval, so a dropped villager rests like one who chose the hammock themselves.
- **Six-child private romantic time.** Stock `theMainScene::HandleDropOnVillager` refuses the drop when the family is full. That refusal is replaced with a jump to the same target every passing gate already uses, so an opposite-sex spouse pair at six children runs the ordinary romantic sequence — stock cooldown included — instead of being turned away. No cave and no reproduced instructions; the seven refusal bytes are simply unreachable, and the age and same-gender gates above are untouched.
- **Manual computer drop.** When a drop on a computer would have produced ordinary web browsing, a coin flip switches it to playing a video game instead. The stock email, repair, career-work and sickness computer routes are reserved before that point and are not affected, and no autonomous candidate weight changes.

## Source layout

- `src/offline_vf2_patcher.py` - command-line patcher and validation/apply/restore engine.
- `src/offline_vf2_patcher_gui.py` - Tkinter GUI, plus its icon assets under `src/assets/`.
- `src/vf2_tools_gui.py`, `src/vf2_save_backup.py`, `src/vf2_rename_family.py`, `src/vf2_save_reader.py`, `src/vf2_how_to_use.py` and `src/vf2_how_to_use.json` - the GUI's Tools tab, Back Up / Restore Saves, Rename Family and the How to Use guides.
- `src/vf2_genealogy.py`, `src/vf2_family_history.py`, `src/vf2_tree_memory.py`, `src/vf2_family_tree.py`, `src/vf2_family_tree_window.py`, `src/vf2_member_info.py`, `src/vf2_relationships.py`, `src/vf2_tree_editor_tools.py`, `src/vf2_line_colours.py`, `src/vf2_gdiplus.py` and `src/family_tree_backgrounds/` - the Family Tree Maker.
- `tests/` - the patcher, exporter, and GUI test modules that run against `src/`.
- `work/` - the reverse-engineering and build tree: disassembly dumps, analysis and
  export scripts, and the full test suite the shipped tools are synced from.
  `work/export_offline_patch_bundle.py` is the self-contained release-bundle exporter
  and the source of truth for the GUI's setting list; `work/vf2_crash_capture.py` is the
  exact-build dump/log validation and IDA handoff helper; `work/patch_mobile_furniture_pack.py`
  is the native VF2 build/patch pipeline; `work/test_*.py` holds the source, binary-contract,
  exporter, runner, and GUI tests.
- `work/assets/holiday_collectibles/` - curated Holiday Ornament source art and reproducible runtime assets.
- `patcher_assets/optional_patches/` - checked-in source art and audio for the optional asset patches.
- `data/vf2/` - target-identity records, build matrices, furniture/image tables, and the native contracts the tests pin.
- `docs/offline-patcher.md` - technical patcher documentation.
- `docs/villager-behavior-plans.md` - behavior ID and label-family reference.
- `docs/Transparency Log.txt` - implementation and verification disclosures.
- `docs/REQUEST_LEDGER.md` - durable shipped/partial/unverified/deferred request
  inventory and release-completeness gate.
- `docs/discoveries.md` and `docs/TODO.md` - reverse-engineering evidence and remaining manual checks.

## Development

The project is designed to be self-contained. Do not add dependencies on Downloads, Desktop, OneDrive, or another private repository. Build outputs, extracted payloads, executables, caches, and archives stay out of Git and are distributed only through the latest GitHub Release.

Run the Python test modules from the repository root with a compatible Python 3 interpreter, for example:

```powershell
python -m unittest tests.test_offline_vf2_patcher tests.test_export_offline_patch_bundle tests.test_offline_vf2_patcher_gui
```

The `work/` tree keeps the wider suite, including the native build pipeline and
binary-contract tests:

```powershell
python -m unittest work.test_offline_vf2_patcher work.test_export_offline_patch_bundle work.test_offline_vf2_patcher_gui work.test_patch_mobile_furniture_pack
```

To run both suites in parallel (one pytest process per file, 12 at a time; failures are re-run alone and only
those that still fail count):

```powershell
python scripts\run_tests_parallel.py              # ordinary run: the slow release-only tests skip
python scripts\run_tests_parallel.py --release    # the run before a release must use --release
```

The release-only tests are listed in `scripts/release_only.py`; plain `pytest` skips them too unless given
`--release` (or `VF2_RELEASE=1`). CI runs `pytest tests/ --release` as one job. The tests that share files
in the checkout, the measured timings, and running the matrix build and the other release steps in parallel
(`work/build_matrix_parallel.ps1`, `work/release_parallel.ps1`) are in `docs/parallel-tests.md`.

Three suites exist in both `work/` and `tests/`, and a test asserts the two
copies stay identical -- `tests/` differs only in importing the shipped `src/`
copy rather than `work/`. Editing one and not the other fails with "has drifted
from"; sync the pair rather than editing either alone.

Run `build_matrix.ps1` with a clean Windows `PATH`. The link step's
`build_b119.bat` counts lines with `findstr ... | find /C /V ""`, which needs
Windows' `find.exe`. Launched from a shell whose `PATH` puts a Unix toolchain
first -- Git Bash, MSYS, WSL interop -- Unix `find` runs instead, reads `/C` and
`/V` as paths, and walks the filesystem indefinitely. The build then sits at
100% CPU with an empty log while thousands of output files are already on disk,
so it looks exactly like healthy progress; counting output directories reports
success. Count linked executables instead, and set
`$env:PATH = 'C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem'` in the
launcher.

Generated C is the artifact that counts, not the Python that writes it. Some
templates interpolate as f-strings and others are raw strings carrying named
`__VF2_*__` placeholders substituted afterwards, so mixing the two conventions
emits a placeholder literally while every source-reading test still passes.
Compile the single generated file (`cl /c /EHsc`) after changing it, and read
route coverage out of `work/patched_mobile_furniture_pack_objs/*.cpp` rather
than the generator. Text written with `encoding="ascii"` -- the bundle's
patcher README among it -- fails at export time and nowhere earlier, so assert
against a bundle you actually wrote.

The `work/` binary-contract tests additionally need the gitignored local build
support directories (`work/desktop_obj_files`, `work/vanilla_runtime_payload`,
`work/generated_import_libs`, `work/desktop_runtime_dlls`); without them those
tests fail on missing inputs rather than on a real regression.

A build still cannot be reproduced from source alone. 635 runtime images -- most
of the VillagerBodies frames, the mobile furniture art, and the upgrade icons --
reach a build only by inheriting from a previous build output. All 635 are now
preserved under `patcher_assets/inherited_runtime_images`, so they can no longer
be lost, and the build restores them from there (`restore_preserved_inherited_art`,
since PR #86), failing closed on a missing, corrupt or undigested file -- the
B196 build manifest shows 540 of 540 runtime images present; the other 95 are
editing sources that are never installed. **Corrected 2026-09-29:** this said
"no build consumes them from there yet". Of those, 574 previously
existed in no tracked location at all; the other 61 were already tracked
elsewhere and only their runtime copies arrived by inheritance. `work/build_playtest.ps1` takes that
predecessor with `-PreviousBuildDir` and checks both it and the produced build
against the recorded inventory in `data/vf2/inherited-only-images.json`.
Omitting the flag does not reliably produce an unseeded build: the generator
also scans `outputs/` for an older one, and whichever seed it resolves is
reported after generation. Before PR #86 a build that inherited from nothing
was missing all 635 and said so in red; it now takes them from the preserved
store instead.

The GUI modules need a Python build with `tkinter` available.
