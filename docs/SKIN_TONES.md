# Skin Tones (vf2skin_b200.dll): design, pins and evidence (emulated; no live test yet)

The owner's decisions (2026-11-26, the same as the Virtual Families 1 patcher's): ten tones, S1 Porcelain to S10 Ebony,
plus Game's own (the game's own skin; never called "Default" where a player sees it). All bare skin is toned (face,
neck, arms, hands, legs, feet, bald scalps), and of the baby art only the held baby. One file per save, never a save
field. Random tones for founders, arrivals, candidates and everybody already in a family when the setting is first on;
babies inherit by the Virtual Villagers rule. The picker is the patcher's Tools > Skin Tones... window; each change is an
"Appearance changed" record in the Family History log. The masks ship as shape-only pictures. On by default, in Select
All and Owner's Defaults. *Superseded (owner, 2026-11-28):* off by default for players, ticked by Select All and
Owner's Defaults, the same as the Virtual Villagers patcher.

**Held for the next release (owner, 2026-11-28): B210 does not offer Skin Tones.** The owner first hand-edits the
skin mask pictures (the GIMP files). One switch, `HELD_FOR_NEXT_RELEASE = True` in `src/vf2_skin_tones.py` (and its
`work/` copy), makes the exporter (`skin_tones_held()` in `work/export_offline_patch_bundle.py`) leave out the
`skin_tones` setting row, the DLL, the ini, the mask pictures and the `.vf2skin` post-asset toggle, and makes the
Tools tab leave out the Skin Tones... link, its "?" and its How to Use topic. B210's 32 executables (built from
068cb63) still carry the dormant byte and loader; nothing sets the byte, so it stays 00 as built and the loader does
nothing. The patcher still reads, copies, moves and backs up a Skin Tones file a save already has. All the code, the
DLL source and its tests stay; set the switch to False to offer Skin Tones again.

## What the player sees

- Every family member drawn in their tone: in the house (walking, every action, sitting, the Holiday outfits 50 to 53
  too), the Details, Adoption and marriage proposal portraits (the big heads, the older look from 45, and the big
  bodies, Holiday portrait bodies too), an event pop-up's and the main screen's portrait, the Family Tree (the dead and
  those who left too, and Revive's revived family members shown under the current spouse) and the menu's family. The
  babies a mother holds (carrying.png cell 3, once per baby) are drawn in the babies' tone. Hair, eyes, lips and
  clothes stay the game's own.
- Tools > Skin Tones... (the game closed): one row per family member at home with Game's own, S1 Porcelain ... S10
  Ebony, and Reset to birth tone. The save folder is backed up first ("(before skin tones)"); each change appends an
  "Appearance changed" record ("Old skin tone" / "New skin tone", "How: Skin Tones window") to the slot's Family History.

## Who gets which tone

| Who | Tone | Where in the code |
|---|---|---|
| A family with no tones file (the patch is new, or the file was lost) | everybody in the house and every Family Tree entry of every generation: a random tone, also their birth tone | `AfterLoad` -> `Reconcile(true)` |
| Founders, adopted children, spouses, visitors, Adoption and proposal candidates (household villager records) | random | `Newcomer` |
| A baby | rolled once at the conception (Impregnate makes the babies' records hidden in theGameState +25AB0h): 95% `(father + mother) / 2 + rand(3) - 1` held to 1..10, 5% any tone; a parent with no tone or Game's own counts as the other; twins and triplets copy the first baby | `BabiesMade`, from the two conception calls |
| A copy the game makes of someone (Next Generation's adult heir) | theirs | `Newcomer` |

Vanilla VF2 writes a head-inheritance rule and then throws it away (CVillager::Init); the owner chose the Virtual
Villagers / Virtual Families 1 rule for the tone regardless. The random numbers are the DLL's own (xorshift32 seeded
from the clock), never the game's rand(). The father is the household villager whose head and body Impregnate is
given (the mother's spouse first), as the Family History DLL finds him.

## Loading (its own setting byte, from B210)

Every executable built from B210 on carries a dormant `.vf2skin` byte (0 as built) and one loader line in the
theGame::Init wrapper, right after the Family History DLL's: with the byte 1 it loads
`Virtual Families 2 Patcher Filesf2skin_b200.dll` and calls `B200Skin_Startup()`, which reads its own setting
(`vf2skin.ini`, `[Patches] SkinTones=1`). It does not need the Family History log. The exporter's post-asset toggle
sets the byte, and its records for the DLL, the ini and the masks require only `skin_tones`; a build without the
loader (B209 and earlier) has no SkinTones contract and gets no records. (#535 first had the Family History DLL
load it; superseded.) The DLL loads before Store Refresh, Outfit Pictures, Title Box, Unicode Text, Translations
and Revive, whose resolvers are proved to find their pins with its writes in place. With the Family History log
off, the Skin Tones window still changes tones; it adds an "Appearance changed" record only to a log that exists.

## How it draws

Every cell draw of a person ends in ldwGameWindowImpl::BlitRectWithAlpha (entry hook, 9 bytes stolen). While a toned
person is drawn, a blit from a sheet of people (found by its SDL surface in the image table's grid, +2Ch) is given a
kept copy of that one row with the skin recoloured by the approved OKLCh method (skin_tables.h, VF2's anchor), and the
rectangle moves to the copy's row; a Holiday frame or portrait body (its own one-cell picture; the ids are read from
the generated helpers' tables) gets a recoloured copy of the picture. At most 96 MB of copies are kept, least recently
used first; a failed SDL_CreateRGBSurface draws the game's own row.

| Draw | Hook | The person |
|---|---|---|
| The house and the menu's family | CVillagerManager::DrawVillager entry | the slot argument |
| The held babies | DrawCarriedItems' two calls in DrawVillager | the first reserved baby's tone, only on carrying.png cell 3 |
| Details, Adoption, proposal | CVillager::DrawDetailVillager entry | `this` |
| Event pop-up, main screen portrait | CVillager::DrawEventVillager entry | `this` |
| Family Tree | DrawParent / DrawChild entries, told by the return address: DrawFamily's parent calls (record in ebx) and child call ([ebp+10h] + 1B8h + edi) | the tree entry: its villager slot while the name and sex are theirs, else the person who holds that place |
| Revive's revived member (B210 code calls DrawParent itself) | the same entry, any other return address | the B200Revive_Members entry with that sex, head and body |

## Memory room in the 32-bit executable

The B209 executables are not large-address-aware: 2 GB of user space. Every picture in the build's Images folder,
decoded at 32 bits a pixel, is 910 MB even counting the duplicate copies kept in subfolders the game never loads; the
game holds far less at once. With the 96 MB cap on kept rows and 7.8 MB of decoded masks the worst case stays near
1.0 GB. The rows are separate surfaces of 0.2 to 1 MB each (no large contiguous block), and an allocation that fails
only means that one draw is the game's own.

## The masks

`patcher_assets/skin_masks`: 1-bit pictures (white = skin), no game pixel. The 14 sheets are the workbench's finished
`layers\<sheet>\Skin mask.png`. The Holiday outfits (bodies 50 to 53: 448 frames and 8 portrait bodies, the patcher's
own art as the B209 build installs it, the same in all 32 variants) were made with the workbench's own method
(`vfskin.skin_mask`) run on each stock sheet with the four outfits added as rows 50 to 53; the same run reproduces the
approved stock masks to 99.98% or better (masks.json, `method_agreement_with_approved_stock_masks`). The DLL uses a mask
only when the game's file is the very file it was made from (size and FNV-1a 64 in skin_masks.h).

## The file

`<save folder>\Virtual Families 2 Patcher Data\Skin Tones\<save file>.dat`: "VF2SKIN\0", version 1, "VF2B200\0", the
size, the save's FNV-1a 64 and size, generations, parent 1's slot and sex, up to 400 entries of 64 bytes (slot, sex,
stored name, tone 0/1..10/15, birth tone, head, body, two tree places, person number), FNV-1a 64. Written after
theGameState::Save (temp file, then replace), rotated with the save (N -> N+20); after a load the save's own file, else
the backup's, else another file of the same family; an unreadable file is renamed `.unreadable-<k>.dat`; a file another
program holds is left alone and nothing is toned or written for that save. Copy / Move / Delete Player Slot, Rename
Family, Game Speed and Back Up / Restore carry and re-key it (vf2_copy_slot.SIDECAR_FOLDERS).

## For Revive (vf2revive_b200.dll)

    int B200Skin_ToneOf(int slot);                       // at the death: tone | birth << 8; -1 when off or nobody
    int B200Skin_ToneGive(int slot, int tone, int birth); // after the revival, in the new slot: 1 when given

`GetModuleHandleW(L"vf2skin_b200.dll")` + `GetProcAddress`. Give(slot, 0, ...) is refused: the revived villager is then
a newcomer (a random tone). A revived member drawn under the current spouse needs nothing more from Revive than
`B200Revive_Members` (it already exports it).

## Evidence

- `runtime/tools/gen_b200_skin_sites.py`: 26 pins on the B209 core (capstone + pefile), every derivation, every hooked
  call reaching its function (directly, through B209's jmp thunk, or Cheat Upgrades' pregnancy wrapper), the stolen
  bytes whole and position independent, the image table and the Holiday helpers' tables; all 32 B209 matrix
  executables resolve.
- `tests/test_b200_skin_tones.py` (Unicorn, the real DLL on the real B209 core, at the link address and relocated):
  the install writes exactly the planned jmps and calls and every code page and the trampolines are made
  PAGE_EXECUTE_READWRITE; setting off changes nothing; an executable it cannot prove is left alone; the real scan
  resolves; Game's own draws the game's own; the house heads (young and older look), bodies, actions and sitting, the
  portraits' big heads and bodies, the Holiday frames and portrait bodies, the tree's parents, a child (alive and dead)
  and a revived member, the held babies (cell 3, twice for twins) are recoloured exactly on the mask's skin, every other
  pixel the game's own, the skin the approved recolour to one level; a modded sheet and a broken mask are drawn as the
  game draws them; first-load random tones kept across save and load; 60 conceptions through both calls (twins copy,
  the rule), a Game's own parent; renames; newcomers and copies; a damaged file set aside, a shut file left alone, the
  backup rotated; Revive's two exports; the companions loaded after this DLL still resolve with its writes in place;
  the masks are a fresh run of the mask tool.
- `tests/test_vf2_skin_tones.py`, `tests/test_vf2_skin_tones_window.py`, `tests/test_sidecar_rekey.py`: the patcher's
  window, the file reader and writer, the log record, and the slot tools carrying the file.

## Not proven (needs the live game)

1. Real-PC time of a sheet's first use (hashing the sheet file, decoding its mask: tens of ms) and of a first row.
2. Real SDL surfaces (the copies are SDL_CreateRGBSurface surfaces in the sheet's own format; proven on emulated ARGB).
3. The anim tables: the emulation hands each draw the grid and cell; in the game they come from Assets\anims.dat.
4. The menu's family draws through DrawVillager like the house (one caller, CSceneManager::EndScene); not drawn in the
   emulation as a separate scene.
5. Two Family Tree people with the same name and sex in neighbouring generations, not the same person, with the same
   head and body could share a tone (the heir rule, as Virtual Families 1).
6. The patcher's own pictures (Family Tree Maker, Picture Maker, the store's previews) still show the game's own skin.
