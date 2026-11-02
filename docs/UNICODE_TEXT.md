# Unicode text: one character limit for every name box (2026-11-02)

The Unicode text settings themselves (Render Unicode with In-Game Fonts, Use Unicode Font) are described in the
README ("Render Unicode with In-Game Fonts") and `runtime/b200_unicode_sites.py`. This file is the part both
settings share with Virtual Families 1's `docs/UNICODE_TEXT.md` (Virtual-Families-1-Fun-Patcher PR #61): names up
to 300 characters.

## One character limit for every name box

### Release note

> **Names up to 300 characters, everywhere.** With Render Unicode with In-Game Fonts or Use Unicode Font on, every
> name box takes up to 300 characters: the slot menu's family names and New Player, the new family's name, a
> family member's name, adoption and dating; Rename Family and Copy Player Slot take the same 300. It is one limit,
> shared with the other Fun Patchers. Characters are counted as you see them (a letter with its accents, an emoji
> with its skin tone or a family emoji is one), and Backspace removes one whole character. A long name scrolls in
> its box while you type it. The save itself is not changed: a name that fits its field is kept there exactly as
> before; a longer one is kept there as its short form (its start and "...", or "2...", "3..." when two would
> start alike) and the whole name is kept beside the save, in `Virtual Families 2 Patcher Data\Names`. The game
> shows the whole name wherever it shows that name, fitted with an ellipsis (…) only where the game leaves room
> for a name's usual length; the Family Tree Maker, the Family History reader, Rename Family and Copy Player Slot
> use the whole name. Back Up Saves, Restore Saves and Copy Player Slot carry the Names files with the saves. With
> both settings off the game still loads and plays such a save and shows the short form.

### The limit and why (VERIFIED in the exe)

`NAME_LETTERS = 300` in `src/vf2_game_text.py` is the only place the number is written in Python;
`NAME_BOX_BYTES = TEXT_BOX_CEILING_BYTES = 1,200` and the mark `NAME_MARK = "..."` sit beside it. The DLL spells
the same numbers as `kNameLetters` / `kNameBoxBytes` in `runtime/native/b200unicode/b200names.inc`;
`tests/test_name_limit.py` checks they agree and that no other module defines the limit.

The ceiling is the LDW engine's own: `ldwTextControl::SetCanEdit` clamps every box's limit to `0x4B0` = 1,200 bytes
(`mov edx, 4B0h` / `cmp [ebp+0Ch], edx` / `cmovl`, at +45h..+50h of the function) and allocates limit + 1 bytes;
Virtual Families 1 and Fish / Plant Tycoon have the same cap. One code point is at most 4 bytes of UTF-8, so 300
characters of single code points always fit; a character of several code points (a joined family emoji is 25
bytes) can reach the 1,200 bytes first (a box takes a typed code point only while the text stays within 1,200
bytes AND 300 characters). The cap is not patched past.

### The boxes (all ten SetCanEdit calls that make a name box; VERIFIED)

Found in the live executable by whole-function pins (`runtime/b200_unicode_sites.NAME_FUNCTIONS`; the B200
executable is relocated and each matrix variant links differently, so the DLL holds no address). The generator
`runtime/tools/gen_b200_unicode_sites.py` proved all ten in the core executable and every one of the 31 other
B200 matrix executables.

| SetCanEdit call (function, kind) | Stock limit | The box | Where its text goes (GetText -> copy) |
| --- | --- | --- | --- |
| `theChangePlayerDlg::theChangePlayerDlg` x5, F | 14h | the slot menu's five family names | `GetText(gs+25B30h + 15h x (k-1), 14h)` straight into the slot's 21-byte field |
| `theChangePlayerDlg::HandleMessage`, F | 14h | New Player | the same five reads; `GetText(local[20], 14h)` compared with "New Player" |
| `theCreateNickNameDlg::theCreateNickNameDlg`, F | 14h | the new family's name | `GetText(gs+25ABCh, 14h)` straight into the 20-byte field |
| `theVillagerScene::theVillagerScene`, M | 12h | renaming a family member | `GetText(local[20], 13h)`, `CFamilyTree::ChangeName`, `strncpy(member+6A64h, local, 19h)` (Done and UpdateSelection) |
| `CAdoptionScene::CAdoptionScene`, M | 12h | adoption | `GetText(local[20], 13h)`, `strncpy(member+6A64h, local, 19h)` |
| `CDatingScene::CDatingScene`, M | 12h | dating: the partner's name | `GetText(local[20], 13h)`, `strncpy(member+6A64h, local, 19h)` |

F: a family name, 19 bytes in the save; M: a family member's name, 18 bytes as typed (the field is 25 bytes, the
stock box keeps 18).

Not names, left at their stock limits: `RedeemCreditDlg` (a 20-byte code), `CFamilyTreeInfoDlg` (the Family Tree
note, 80 bytes) and `theAlignVillagerScene` (the developers' animation tool, 20 and 31 bytes).

### The copy-site audit (every GetText call; VERIFIED)

The enlarged buffer is the box's own (`impl+30h`, allocated by SetCanEdit / SetText with limit + 1 bytes). Every
copy of a box's text into a fixed buffer goes through `ldwTextControl::GetText(buffer, size)`, which the DLL
replaces: it writes exactly `size` bytes (the text cut to at most `size - 1` bytes at a character, then zeros), and
a name box gives the game only the short form, never more than the stock game could store.

| GetText call | Size | Destination (fixed buffer) | Then | Result at 300 characters / 1,200 bytes (emulated) |
| --- | --- | --- | --- | --- |
| `theVillagerScene::HandleMessage` (Done) | 13h | local[20] at ebp-18h | ChangeName(member, local); `strncpy(member+6A64h, local, 19h)` into the 25-byte field | short form (<= 18 bytes); no byte outside the local's 19 or the field's 25 changes |
| `theVillagerScene::UpdateSelection` | 13h | local[20] at ebp-18h | the same | the same |
| `CAdoptionScene::HandleMessage` | 13h | local[20] at ebp-18h | `strncpy(member+6A64h, local, 19h)` | the same |
| `CDatingScene::HandleMessage` | 13h | local[20] at ebp-18h | `strncpy(partner+6A64h, local, 19h)` | the same |
| `theCreateNickNameDlg::HandleMessage` | 14h | gs+25ABCh (20 bytes) | none (written in place) | short form (<= 19 bytes); nothing outside the 20 bytes changes |
| `theChangePlayerDlg::HandleMessage` x5 | 14h | gs+25B30h + 15h x (k-1) (21-byte fields) | none | short form; nothing outside the 20 bytes changes |
| `theChangePlayerDlg::HandleMessage` | 14h | local[20] at ebp-24h | compared with "New Player" | short form; nothing outside the 20 bytes changes; nothing recorded |
| `RedeemCreditDlg::GetName` | 14h | this+64h | not a name box: its stock limit 14h, GetText cuts to 19 bytes | unchanged behaviour |
| `CFamilyTreeInfoDlg::HandleMessage` | 50h | record+86h | not a name box (stock limit 50h) | unchanged behaviour |
| `theAlignVillagerScene::HandleMessage` | 1Fh | an animation record | not a name box | unchanged behaviour |
| `CDayNightCycleTestDlg::HandleMessage` | 64h | local[100] | not a name box (no SetCanEdit) | unchanged behaviour |

The box buffer's pointer itself is read only by the box's own methods (SetCanEdit, SetText, its Draw and
auto-size, HandleKey, GetTextLength, GetText and the destructor); the DLL's Draw hook (below) keeps the stock draw
from cutting it.

### How it works (`runtime/native/b200unicode/b200names.inc`, in vf2unicode_b200.dll and vf2unicodefont_b200.dll)

Two more function-entry hooks, a separate group: when any of its nine pins is not found exactly once, the DLL
installs the Unicode text without the long names (`B200Unicode_Status.names = 0`), never nothing at all.

| Site | What the DLL does there |
| --- | --- |
| `ldwTextControl::SetCanEdit` | called from one of the ten name-box calls (its return address): the limit is 1,200 bytes; a box given a short form opens with the whole name |
| `ldwTextControlImpl::Draw` | the stock draw deletes bytes from the end of the box's own text until it fits; a name box too long for its width draws a copy instead -- the end that fits while it is typed into, its start with "…" otherwise -- so its text is never cut |

and the first part's hooks do more: HandleKey counts characters in a name box (300) as well as its bytes (1,200),
and lets a name box scroll instead of refusing a character wider than the box; SetText opens a short form as the
whole name; GetText of a name box gives the short form (`ShortFor`, the rule of `vf2_names.short_form`) and
records the whole name in the Names file of the slot the destination belongs to (the slot menu's field k: slot k;
the new family's name and a member's name: the slot being played, gs+25B20h; a local the game only compares:
nothing); DrawString and GetWidth draw and measure the whole name wherever a short form is drawn, fitted with "…"
into the width of as many "W" as the field holds bytes (the widest name the stock game can show there);
DrawStringJustified (dialogs, events) gets each whole name fitted into its short form's own width, so the stock
wrapping and the heights the game measured from the stored text still hold. Every short form ends with "...", so
only text with "..." in it is looked at.

**The short form** (`src/vf2_names.short_form`, the same in the DLL): a short form already standing for this name
is used again; a name that fits and is no other name's short form is stored as it is; else the longest start that
fits with the mark (trailing spaces dropped) + "...", then + "2...", "3..." until it stands for no other name in
any slot (a family name's short form shows in the slot menu beside the others). It is unique, so it names one
family member: it follows them wherever the game copies their name (their children's parents' names, the Family
Tree's records, their death), through Copy Player Slot, Back Up / Restore Saves and a rename. A typed name the game
set into a box (SetText) and the player did not change is given back unchanged: the stock rule of
`tests/test_name_boxes.py` (a name too long for its box is never cut by viewing it) still holds.

**The Names file**: `<saves>\Virtual Families 2 Patcher Data\Names\Virtual Families 2<N>.ldw.txt` (the save file's
name + ".txt", from the game's own MakeGameStatePath), UTF-8 lines `VF2 Names 1`, then
`short<TAB>room<TAB>whole name` (room: the field's bytes it was made for). Written through a temporary file and
MoveFileEx. A line is never removed: a short form no longer in the save is harmless (a new one is never made equal
to it), and the game's previous save `<N+20>` stays readable. A line that is not valid (no mark, too long for its
room, a control character, more than 300 characters or 1,200 bytes) is left out; a file that cannot be read is
read as empty, and the save shows its short forms.

**Who else reads it** (`src/vf2_names.py`): the Family Tree Maker (`vf2_genealogy.load_village`: the save's names
and the Family History log's are made whole before they are matched), the Family History reader
(`vf2_family_history.whole_names`), Rename Family (a long new name gets its line; a failed rename removes a Names
file it made), Copy Player Slot (the copy takes the source's lines plus the new name's; a family it replaces has
its Names file set aside with its other files) and Back Up / Restore Saves (the Names file is slot N's file:
`vf2_save_backup.file_slot`).

### Proved (tests)

`tests/test_name_limit.py`, with the REAL test DLL on the REAL executable in Unicorn: the AUDIT table above is
every SetCanEdit / GetText call in the desktop objects; the long names' group resolves to what the generator
derives; each of the ten boxes, made by the game's own SetCanEdit from its own call site, takes 300 characters and
refuses the 301st, takes 300 four-byte characters (1,200 bytes) and nothing more, stops a run of 25-byte family
emoji at 48 (1,200 bytes), counts a letter with its mark as one, with guard bytes after the buffer the game
allocates; another call keeps its stock limit; the four member-name sites run the game's own instructions from the
GetText call through the strncpy, and the seven family-name destinations are written by the game's GetText call,
with names that fit exactly, one byte past, 300 characters, 300 accented characters and 1,200 bytes: nothing
outside each destination field or local buffer changes (guard bytes), the destination holds
`vf2_names.short_form`'s answer and the Names file the whole name; names that start alike get "..." and "2..."; a
short form opens as the whole name and comes back unchanged, after a restart too; a damaged Names file reads as
empty; DrawString and GetWidth draw and measure the fitted whole name glyph for glyph as the patcher's
`vf2_game_text`; DrawStringJustified gets it in the short form's width; a long name box draws a fitted copy and
keeps its text. `tests/test_rename_family.py` and `tests/test_copy_slot.py`: long names and the Names file.

### Live checks (not yet done)

1. New family with a 300-character name (type until the box stops): the box scrolls; the main screen and the slot
   menu show the whole name (with "…" where it does not fit); quit and start again: the same.
2. Adopt, date and rename a member with a long name and with a 300-character Japanese name; open the Family Tree
   screen; let a long-named member die.
3. Turn both Unicode settings off and re-patch: the family loads and plays and shows the short forms; turn one on
   again: the whole names are back.
4. Rename Family and Copy Player Slot with a long name; Back Up Saves and Restore Saves; the Family Tree Maker
   shows whole names.
5. Use Unicode Font with Comic Sans MS: the same checks.

### Not in this part

* The Family History DLL (vf2history_b200.dll) still writes the short form into the log; the patcher's readers
  show the whole name from the Names file.
* Copy and Paste in Text Boxes (vf2clip_b200.dll, its own DLL) pastes up to the box's 1,200 bytes; the 300-character
  count is applied to typing.
