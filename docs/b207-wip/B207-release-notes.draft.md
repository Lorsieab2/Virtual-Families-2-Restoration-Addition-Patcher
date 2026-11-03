# VF2 B207 release notes

**The patcher bundle.** The 32 executables are built from `main` at `e32fe0f` (PR #488; the release config was merged after it as #489), seeded from the B206 matrix, in 4 parallel parts. The companion DLLs are built and the bundle is exported from `@@EXPORT_SHA@@` (@@EXPORT_WHY@@). B207 is a new version, not an in-place update of B206. It carries everything B206 had, plus the changes below.

B207 offers @@OFFERED@@ settings (@@DEFINED@@ are defined; @@NOT_OFFERED@@). @@DEFAULT_ON@@ of the @@OFFERED@@ are on by default. All 32 executables are rebuilt: every one gains new setting bytes (the Unicode text settings, Copy and Paste in Text Boxes and the Title Screen Player Name Box) and the Fix Vanilla Game Bugs fixes below.

**B207 saves to its own folder**, `Documents\LDW\Virtual Families 2 - Modded B207`, because Virtual Families 2 names its save folder after the executable. See "Keeping your B206 families" below.

## Text and names

- **Render Unicode with In-Game Fonts** (#474, on by default). Names and other text can use letters beyond plain English: accents, other alphabets, emoji. They are drawn in the game's own fonts; a letter the game's font lacks is drawn by the patcher in the same style.
- **Use Unicode Font (overrides in-game fonts)** (#474, off by default). Draws all text in a Windows font instead of the game's fonts.
  - The two cannot be on together. Ticking one unticks the other, and Patch Selection Settings refuses both at once (#476).
  - **Tools tab, Unicode Font...** (#477) picks the font, with a preview of the game's four fonts.
- **Game Font Text** (#474), a Tools tab tool that writes text as a picture in the game's own fonts.
- **Typing fixes** (#480):
  - Characters such as emoji, typed or entered with an input method, now arrive whole instead of as junk letters.
  - Looking at a family member no longer shortens a long name. The original game did this to any name longer than 18 bytes.
  - Wide scripts no longer run past their boxes.
- **Copy and Paste in Text Boxes** (#480, on by default). Ctrl+C, Ctrl+X and Ctrl+V work in the game's text boxes.
- **Names up to 300 characters** (#484) in every name box. A name that fits is saved exactly as before. A longer one is saved in a short form, and the whole name goes in a Names file in `Virtual Families 2 Patcher Data\Names`. The game shows the whole name, fitted to the space.
- **Family History logs whole names** (#486), and a paste into a name box stops at 300 characters.
- **Title Screen Player Name Box** (#488, on by default). A see-through white box behind the player's name on the title screen, so the name is easy to read. @@OPACITY@@

## Owner's Defaults

Owner's Defaults (#478) ticks Render Unicode with In-Game Fonts and leaves Use Unicode Font off. It still ticks everything else except Up to 28 Children.

## Fixed (Fix Vanilla Game Bugs)

- **A rare rain crash** (#481). When a raindrop's new start landed exactly on its old end, the game divided by zero and could crash. The likeliest time was the first rain after starting the game. All 185 divisions in the game's code were checked; this was the only one a running game can reach. The weather code was checked again in #482 and has no other.
- **`petanimpts.dat` was closed twice** (#485) at every start. It is now closed once. What the game loads is unchanged.

## Tools

- **Picture Maker: Every picture** (#483). Every picture the game has, assembled as the game draws it, as in the Virtual Families 1 patcher. It includes the unused ones, and can save one, a group, or all of them.

## Defaults

**Off by default:** Cheat Upgrades; Free and Guaranteed Cheats; All 36 Flea Market goods; All outfits and hairstyles always for sale; the transparent invisible-furniture swap; Up to 28 Children; Use Unicode Font.

**On by default:** everything else, including Render Unicode with In-Game Fonts, Copy and Paste in Text Boxes and the Title Screen Player Name Box. No AI Icons stays waiting for Cheat Upgrades.

## Keeping your B206 families

Copy everything in `Documents\LDW\Virtual Families 2 - Modded B206` except the `Backups` folder into `Documents\LDW\Virtual Families 2 - Modded B207`. That includes both the `Virtual Families 2 Patcher Data` and `Virtual Families 2 Patcher` folders.

@@CHECKS@@
