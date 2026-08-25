# B173

A build-payload fix and seven new Cheat Upgrades.

The payload fix matters most, and it is the reason this release exists: every
build now ships the base game's furniture footprint maps. Standalone builds had
been shipping without most of them, which meant villagers walked through
furniture and hotspots stopped responding.

## The payload fix

`Assets` was never seeded. `VANILLA_RUNTIME_REQUIRED_DIRS` is
`("Images", "Sounds")`, so the only files a build put in `Assets` were the ones
the generator writes itself. The base game's 242 files — the `.fmap` footprint
maps that carry furniture collision and hotspot data — reached a build only by
being inherited from the previous release through `VF2_PREVIOUS_BUILD_DIR`.

`build_playtest.ps1` deliberately clears that variable, so a standalone build
shipped **119 Assets instead of 242**, missing 207 footprint maps, while its own
output claimed the folder "does not need anything from outside itself".

**Installed releases were never affected.** The offline patcher applies onto a
player's real installation, which already has the stock maps — the B172 payload
contains only 3 of the 242 and works correctly. Only standalone builds were
wrong.

Builds now seed `Assets` from a verified clean-install index, checking every
file by size and SHA-256. This is deliberately not a wholesale directory copy:
the vanilla payload folder holds 845 files against a clean install's 242, so
copying it would ship hundreds of strays. Seeding runs before the behaviour
stagers, so a patch that replaces a footprint map still wins.

### Two guards, one per direction

| Guard | Enforces |
| --- | --- |
| `validate_base_game_payload_intact` | All 897 indexed base-game files present; stock `Assets` byte-identical unless the build declared replacing them. Images are presence-only, since optional visual mods replace stock art by design. |
| `validate_mod_assets_present` | Every `.fmap` a patch staged is still in the payload, and the guard fails rather than passing vacuously if it finds nothing to check. |

Both are covered by tests that assert the failures, not just the happy path:
delete a stock map, tamper with one, declare a replacement, edit an image (must
*not* fail), drop a staged mod map, feed an empty manifest.

All 19 variants in this release carry 888 `Assets` with zero missing base-game
files.

## New Cheat Upgrades

Five wellbeing rows, applied to everyone currently in the house. Dead villagers
are skipped, so none of them revive anyone.

| Row | Effect |
| --- | --- |
| Clear All Illnesses | Cures every symptom and every infection |
| Max out Happiness Bar | Fills Happiness |
| Max out Energy Bar | Fills Energy |
| Max out Fed Bar | Fills Fed |
| Max out Health Bar | Fills Health |

The four stat rows call the game's own setters, so the native low clamps still
apply; 100 is the ceiling, which is what `CVillagerManager`'s own
restore-to-full call passes to `SetHealth`. Fed is stored inverted — the field
counts hunger, proven by every food drop calling `AdjustHunger` with a negative
amount — so a full Fed bar is the minimum of the range.

`CVillagerManager::CureAllVillagers` looked like the obvious way to clear
illnesses, but it is a one-byte `ret` in this build, so the cure reproduces the
two loops `CVillagerState::Reset` runs and nothing else: 7 symptom flags at
`+0x5C` with expiries at `+0x64`, 4 infection flags at `+0x84` with expiries at
`+0x88`. It does not touch the health and age fields `Reset` goes on to
overwrite.

Two more rows toggle stock Flea Market ownership without needing to use the item
on a computer:

| Row | Effect |
| --- | --- |
| Anti-Spam Software Ownership | Flips the same save byte the stock install writes |
| Rockhound Certificate Ownership | Grants or removes the native inventory upgrade |

Both use the items' own store art, lifted from the grids the native draw
actually uses.

## Cancelling the pregnancy one-shots

The six one-shots — Force Successful Pregnancy, Next Babies Male/Female, Next
Pregnancy Singleton/Twins/Triplets — can now be cancelled by buying them again,
and show a checkmark while armed. Arming one clears the rows it is mutually
exclusive with.

Showing the checkmark without losing the click needed care: the store draws the
owned checkmark for any row whose `GetNumAvailable` returns zero, and the click
handler reads that same zero as "not purchasable". The draw and the click read
it through different call sites, so only the draw's is retargeted.

## Anti-spam Software and the Rockhound Certificate are base-game again

Both Flea Market rows are entirely stock: stock availability, stock
one-purchase price, stock removal, and stock descriptions. A previous attempt to
remove Anti-spam Software by dropping a repurchased disc on a computer is gone.

It could not have worked. The stock branch accepts only computer hotspot `0x12`,
and a diagnostic build reported a playtested office computer as hotspot 66 with
`0x12` absent from a 1600x1200 sweep of the house — a symptom of the missing
footprint maps this release fixes. Independently, the repurchase cleared the
ownership flag before any tool reached the tray, so the instruction was
unreachable regardless. The ownership cheat rows replace it.

## Verification

- All 19 variants build, link, and pass both asset guards.
- Image-table audit: 19 variants, 0 problems — stock images 0..636 intact, no id
  collisions.
- Bundle export self-check: a clean install plus this bundle reproduces all
  8195 `Images`/`Assets` files byte-for-byte.
- Test suite: 289 passed, 113 subtests.

Nothing in this release has been playtested in-game.
