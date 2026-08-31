# Inherited-only runtime art

635 image files that a build produces but the repository could not. They existed
only inside previous build output folders and reached each new build by being
copied forward from the last one, so the whole set depended on that chain never
breaking.

Copied here from the verified B176 build. `SHA256SUMS.json` records every digest
so later drift is detectable. The matching inventory, which the build validates
against, is `data/vf2/inherited-only-images.json`.

**This is preservation, not the fix.** The goal is still to regenerate this art
from tracked source. This directory exists so the material cannot be lost while
that work happens, and should be deleted in the same change that proves an
unseeded build produces the full image set.

## Correction to the original claim

The commit that added this directory said all 635 "existed in no tracked
location". That was wrong, and the error is recorded here rather than left
standing.

**61 of the 635 were already tracked**, byte-for-byte, under
`patcher_assets/optional_patches/invisible_workspace_upgrades/`.

They are not one image repeated, and a regeneration step must not treat them
that way. `SHA256SUMS.json` splits them cleanly:

- the **31** `Upgrades/invisible images/*` entries share a **single** digest —
  one transparent placeholder under 31 names, so those are reproducible by
  copying one tracked file;
- the **30** `Upgrades/original images/*` entries have **30 distinct** digests.
  They are the visible upgrade artwork used to restore the stock look when the
  optional patch is turned off, and each must come from its own corresponding
  tracked file. Copying the placeholder over these would replace the restore
  art with transparent images.

The inventory count of 635 is correct. What was overstated is how much of it was
genuinely untracked: **574**, not 635.

## Composition

| category | files | notes |
| --- | --- | --- |
| `VillagerBodies/` | 448 | Holiday outfit bodies 50-53, 56 frames each. A generator exists (`sync_holiday_body_runtime_frames`); its source archive was missing. |
| `Furniture/` | 93 | Mobile furniture art, including the Birthday set. |
| `Upgrades/` | 61 | 31 "invisible images" (one shared placeholder digest) plus 30 "original images" (30 distinct digests, the restore artwork). All 61 already tracked, but only the 31 are interchangeable. |
| root | 25 | Map art and working files, mostly `.xcf`. |
| `OutfitIcons/` | 8 | |

By type: 602 `.png`, 30 `.xcf`, 3 `.jpg`.

## The `.xcf` files

`.gitignore` has a blanket `*.xcf` rule, which is why 30 of these never entered
the repository. They are GIMP project files: editing sources, not runtime
assets. They are tracked here because they are the source material for
regenerating the art.

They should **not** ship in a release payload. They currently do, which is a
separate defect from preserving them here.
