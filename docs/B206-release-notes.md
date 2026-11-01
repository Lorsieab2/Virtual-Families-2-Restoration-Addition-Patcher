# VF2 B206 release notes (draft, started with PR "Patch presets, cheats off by default")

The release build adds its bundle, matrix and settings counts here.

## Patch selection

- **Four preset buttons, as in the Virtual Villagers patcher**, each with a **?**: **Select All Patches** (everything but Experimental), **Default Patches**, **Owner's Defaults** (everything except Up to 28 Children, every cheat and both invisible-furniture settings included) and **Deselect All Patches**.
- **Patch Selection Settings...**: a window with a search box and one tick box per patch; **Tick These** / **Untick These** change the chosen patches the way a click does (a patch brings what it needs, and takes what needs it).

## Cheats are off by default (owner, 1 November 2026)

- **Off by default:** Cheat Upgrades, All 36 Flea Market goods, and two new settings:
  - **Free and Guaranteed Cheats** (the `.vf2free` byte): unlocks exactly the Force Successful Pregnancy row, the $0 Anti-Spam Software Ownership and Rockhound Certificate Ownership rows (Special Upgrades, with Cheat Upgrades), and a free Time Warp.
  - **All outfits and hairstyles always for sale** (the `.vf2clth` byte): off, the Clothing and Hairstyles page is the original six rotating outfits plus 6 rotating hairstyle and holiday-outfit rows.
- Every content setting and paid upgrade stays on. No AI Icons stays on and takes effect with Cheat Upgrades.
- Time Controls' Time Warp now costs the store's Time Warp price (#469); R always redraws the Flea Market (#471).

## Fixed

- **House Renovations and Special Upgrades in builds without Cheat Upgrades.** This was broken in B205's builds without Cheat Upgrades (and every earlier release's): in the 8 B205 executables with Mobile Renovations but without Cheat Upgrades, the store's House Renovations page listed only 10 of its 30 rows, and the Special Upgrades page listed 30 rows where it has 10 (20 of them read past the end of its list). The generator's renovation count patch had matched the Special Upgrades page's bytes. Both pages are right in every B206 executable (emulated: Special Upgrades 10 / 53, House Renovations 30).
