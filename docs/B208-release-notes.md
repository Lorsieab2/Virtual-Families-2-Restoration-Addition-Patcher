# VF2 B208 release notes

**The patcher bundle.** The 32 executables are built from `main` at `bb52bcd` (PR #507; the release config was merged after it as #509), seeded from the B207 matrix, in 4 parallel parts. The companion DLLs are built and the bundle is exported from `015d456` (main after #508 and #510, which changed only the README, tests and the repo's translations folder). B208 is a new version, not an in-place update of B207. It carries everything B207 had, plus the changes below.

B208 offers 48 settings (49 are defined; one is not offered). 41 of the 48 are on by default. All 32 executables are rebuilt: each gains the new Translations setting byte.

**B208 saves to its own folder**, `Documents\LDW\Virtual Families 2 - Modded B208`, because Virtual Families 2 names its save folder after the executable. See "Keeping your B207 families" below.

## Translations (new, on by default)

- **The game in your language** (#500, #503). A new add-on, `vf2tr_b200.dll`, swaps the game's own text for a translation file's, falling back to English for any line a translation leaves out. Every line the patcher adds is translatable too (1,418 lines), and each line keeps to the space the game gives it.
- **The Translations window** (#507), on the Tools tab, as in the Virtual Families 1 patcher:
  - choose a language (by its own name; it takes effect the next time the game starts, with no re-patching);
  - **Make a translation**: a two-column editor with a preview in the game's own font, protected placeholders, and he/she and plural choices;
  - **Add** (button or drag and drop), **Edit**, **Check**, **Export**, and a list you can select several from;
  - **Delete...** sends translations to the Recycle Bin (No is the default; English can't be deleted);
  - **Download from GitHub...** lists the shared translations in this repo's public `translations/` folder (no login, every file checked before it is installed);
  - **Share on GitHub...** shows the confirmation text exactly as written, asks for a credit name you type yourself, and never reads, saves or sends an email address.
- **Shared translations are checked:** every submitted file is scanned with VirusTotal and validated before it can be accepted.
- The percent sign in French and similar ("50 % de") is accepted (#497).
- Without the Unicode setting, curly quotes, dashes and the no-break space are shown as plain ones instead of "!" (#506).

## Names and text

- **Names up to 1,200 bytes** (#498), with no separate character cap.
- **Accented Latin letters are saved as one byte again** (#499), so the original game shows them; other letters are saved as UTF-8. Saves from B207 load as before.
- **The long-names file has checksums** (#501): a damaged record is skipped, and a record that could not be written is tried again.
- **Paste with both Unicode settings off** keeps only the characters the game's own fonts can draw (#502).
- **Line breaking** for Japanese, Chinese, Korean and Thai (#504). In the original game, a word wider than its line lost one letter for each line; it is now cut across lines instead.
- The fallback font order matches the other patchers, and the tool is now called **Game Text...** with an "As the stock game shows it" view (#505).

## Defaults

**Off by default:** Cheat Upgrades; Free and Guaranteed Cheats; All 36 Flea Market goods; All outfits and hairstyles always for sale; the transparent invisible-furniture swap; Up to 28 Children; Use Unicode Font.

**On by default:** everything else, including Translations, Render Unicode with In-Game Fonts, Copy and Paste in Text Boxes and the Title Screen Player Name Box.

## Keeping your B207 families

Copy everything in `Documents\LDW\Virtual Families 2 - Modded B207` except the `Backups` folder into `Documents\LDW\Virtual Families 2 - Modded B208`. That includes both the `Virtual Families 2 Patcher Data` and `Virtual Families 2 Patcher` folders.

## Known gaps

- The Behavior Patches caption "Having private adult romantic time" is in the translation template but still shows in English: the patcher's generated game code copies it directly. A later version fixes it.
- Three stock lines differ between builds with and without Island Events, so a translation of them shows English in Island Events builds.
- Not yet in B208 (planned for B209): colour emoji, fitting names to the real width of each spot, joined-up and right-to-left scripts, and the Unicode 18 fonts.

## Checks

- All 32 variants are built from `bb52bcd`, with 32 distinct executables. The hashes are in `docs/b208-matrix-manifest.md` and the identities in `data/vf2/release-identities-B208.json`.
- Every companion DLL is built fresh from `015d456`. Every helper buffer a DLL runs code from is made executable before use (a test checks each one), the lesson from B207's start-up crash.
- The release gate passed: **RELEASE GATE PASSED**, with no features lost against 28 retained releases (B179 to B207), and "shipped defaults match the SETTINGS table". The bundle reproduces the build on a clean install.
- Full test suite with release-only tests (2 workers): 3,645 passed. The few files that failed were fixed (#510: the README's setting counts and one test that followed the time controls' now-translatable button text) or are checks of generated source files that pass in a freshly generated checkout. The README count, GUI docs and bundle-verifier tests pass against this bundle (79 passed).
- Every Python module of the unzipped bundle imports from the bundle itself (48 of 48).
- A default apply of the zip onto a clean game folder: Special Upgrades 10 rows, House Renovations 30, Clothing and Hairstyles 12 (emulated). Owner's Defaults: 53, 30 and 214.
- **Tried in a running game** (this zip, default settings, a windowed test copy, with mouse and keyboard): the game starts and stays up with every add-on loaded, including Translations; "Zoë 日本👍" typed as the player name, with the emoji arriving whole; pasting "Zoe" plus a separate diaeresis and a line break gave "Zoë X"; after quitting and restarting, the title screen shows the name on the 30% white box.
- **Not yet tried in a running game:** the Translations window and a translated game, Download from GitHub, Share on GitHub, names near the 1,200-byte limit and the long-names file, and line breaking of Japanese or Thai text in a pop-up.
- Asset: `VF2-B208-Release.zip`, 165,874,692 bytes, SHA-256 `dbae9ee9a4ab12eb1bd0369cc504acb8c973656525e14be24ca46403525a9d90`.
