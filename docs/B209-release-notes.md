# VF2 B209 release notes

**The patcher bundle.** The 32 executables are built from `main` at `9d0c9f5` (PR #521; the release config was merged after it as #522), seeded from the B208 matrix, in 4 parallel parts. The companion DLLs are built and the bundle is exported from `010c68f` (main after #523 to #526, which change only the DLLs, the translation files and tests). B209 is a new version, not an in-place update of B208. It carries everything B208 had, plus the changes below.

All 32 executables are rebuilt: each holds the patcher's own lines as new string-table records.

**B209 saves to its own folder**, `Documents\LDW\Virtual Families 2 - Modded B209`, because Virtual Families 2 names its save folder after the executable. See "Keeping your B208 families" below.

## Every script, every letter

- **Colour emoji** (#517). Emoji are drawn in colour (Segoe UI Emoji) in names, the bottom bar, the Family screen, Details and the title screen, never tinted by the text colour.
- **Joined-up and right-to-left scripts** (#518). Arabic and Hebrew are drawn joined and reading right to left; Hindi and other Indic scripts and Thai are shaped, the way Windows shows them. English text is unchanged.
- **Every Unicode 18.0 character** (#515, #520). The newest letters draw, from open fonts shipped with the patcher (GNU Unifont, Noto Sans Cuneiform, Noto Serif Tangut, and Last Resort for anything still without a font), loaded only for the game and never installed in Windows. In the game's bold fonts they are thickened to match its letters.
- **Word lists for languages without spaces** (#513): Thai, Lao, Khmer and Burmese wrap at word boundaries even on Windows without its own language library.
- **Typing** (#524, #525, #526): a full box now keeps what was typed whole: a name box shows a shortened copy ending in "…" while it keeps the whole name, and any other box refuses a character that would not fit together with its marks, so a vowel mark is never left on its own. Changing only the end of a long name is now kept too.

## Translations

- **Nothing runs off the screen** (#519). Translated text, and any text with letters beyond plain English, is kept on the screen: a line that would leave it is moved to end at the edge, or cut with "…", or shown in English. This works with the Unicode settings on and off. The translation editor warns about lines too wide for the screen, has a **Wrap to fit** button, and Check lists them.
- **Every patch line is really translated** (#516). Each line the patcher adds is its own string-table record, so a translation reaches it: the "Having private adult romantic time" caption, the Power Failure result, the Oldest Villager and Generation counters and the Bathroom 2 refusal.
- **The original game's own words translate too** (#523): 14 lines the original game writes into its program instead of its text list, among them the title screen's "Manage Games" and copyright line, the "Decor" button, "Done" in Settings, the "Lvl 1" of a career, and the Redeem Credit messages.
- **Whole translations in the level line** (#523): a translated career level ("Débutant (1)") is no longer cut to the length of the English word.

## Names

- **Long names are never lost at quit** (#514): the Names file is written as soon as a name is set, and the game's own save writes any that are still waiting.
- **Family History logs show accented names correctly** (#524). The log now writes every name as proper UTF-8, so "Zoë" no longer reads "Zo�" in a text editor. Lines an earlier version wrote stay as they are.
- The Family History add-on installs in every B209 executable (#521).

## Defaults

**Off by default:** Cheat Upgrades; Free and Guaranteed Cheats; All 36 Flea Market goods; All outfits and hairstyles always for sale; the transparent invisible-furniture swap; Up to 28 Children; Use Unicode Font.

**On by default:** everything else, including Translations, Render Unicode with In-Game Fonts, Copy and Paste in Text Boxes and the Title Screen Player Name Box.

## Keeping your B208 families

Copy everything in `Documents\LDW\Virtual Families 2 - Modded B208` except the `Backups` folder into `Documents\LDW\Virtual Families 2 - Modded B209`. That includes both the `Virtual Families 2 Patcher Data` and `Virtual Families 2 Patcher` folders.

## Known limits

- A translated line that the game builds from its data into a space whose size the patcher cannot prove is cut to the length of the English line rather than risk writing past it.
- With both Unicode settings off, letters beyond Windows-1252 (emoji, Arabic and so on) show as the original game shows them.

## Tried in a running game

On a windowed test copy with Owner's Defaults and the (TEST) French translation, with mouse and keyboard:

- The whole game ran in French: the title screen (including "Gérer les parties" and "Droits d'auteur"), the name prompt, the intro, the adoption certificate, the house, the main menu, Settings, the Family screen and Details ("Débutant (1)"). Long French pop-ups wrapped, and the intro's top-right line stayed on the screen.
- A player "Zoë 😀👍🏽❤️ مرحبا" and a member "Zoë 😀👍🏽" showed the emoji in colour in the name box, the bottom bar, the family tree and on the title screen's box; the Arabic joined and right to left.
- Hebrew "שלום", Hindi "नमस्ते" and Thai "สวัสดี" drew correctly; Tangut U+17000, Armenian U+0558 and U+1CCFA drew, and the unassigned U+0378 showed a box.
- With the final DLLs: "אבג नमस्ते สวัสดี" typed into the Details name box was kept whole (the box shows a shortened copy ending in "…"); replacing only its last syllable with "ครับ" was stored as a rename; and a long Thai family note stopped at a whole letter, with no mark left on its own.
- The Names file was written when the name was set, the game saved at quit, and the Family History log is valid UTF-8.
- With Render Unicode turned off, the French text drew in the game's own fonts with its accents, and Settings stayed on the screen.
- Every add-on logged "installed"; the translation loaded 4,109 lines and refused none.

**Not yet tried in a running game:** the romantic-time caption, the Power Failure result and the counters in French (shown by the tests on the real game code), Download from GitHub and Share on GitHub, and names near the 1,200-byte limit.

## Checks

- All 32 variants are built from `9d0c9f5`, with 32 distinct executables. The hashes are in `docs/b209-matrix-manifest.md` and the identities in `data/vf2/release-identities-B209.json`.
- Every companion DLL is built fresh from `010c68f`, and every one in the zip matches that build.
- The release gate passed: **RELEASE GATE PASSED**, with no features lost against the retained releases and "shipped defaults match the SETTINGS table". The bundle reproduces the build on a clean install. The zip holds no "(TEST)" translation.
- Full test suite with release-only tests (2 workers): 3,755 passed. The only files that failed are two checks of generated source files (`work/test_generated_cpp_compiles.py`, `work/test_transparent_furniture_drop.py`), which pass in a freshly generated checkout of the build (27 passed).
- Every Python module of the unzipped bundle imports from the bundle itself (52 of 52).
- A default apply of the zip onto a clean game folder: Special Upgrades 10 rows, House Renovations 30, Clothing and Hairstyles 12 (emulated). Owner's Defaults: 53, 30 and 214.
- Asset: `VF2-B209-Release.zip`, 171,826,137 bytes, SHA-256 `92070260cadeed229f308e87fc6be4ec9d5a1257c3f54a90c98de06ff74af4ad`.
