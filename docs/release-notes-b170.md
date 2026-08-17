# B170

Fixes the Family Tree screen. Otherwise identical to B169.

## The bug

Bathroom 1's closed-curtain image id was set to **615**, taken from a live
read of the running game's image table. The read was accurate but the id
was not transferable: the running game is the *patched* build, whose table
is shifted by the ~800 images the patcher appends, so runtime ids do not
correspond to the stock ids the patcher indexes.

Against the stock table, **615 is `familytree_bg.jpg`**. Bathroom 1's
curtain colour was therefore applied to the Family Tree background, which
then failed to draw — and with nothing repainting that region, every sprite
on the screen smeared across an uncleared frame.

## The fix

Ids restored to the values `data/vf2/image-descriptors.json` gives:

    539 = curtain_closed_southb.png  ->  Bathroom 1 (south, workshop-side)
    538 = curtain_closed.png         ->  Bathroom 2 (north)

The room mix-up that prompted the original change was never about these
ids. It was fixed by routing each bathroom to its own decal slot in
`RefreshProps` (+0x53A and +0x570), which is untouched, so both curtains
keep working independently.

## Guards added

A wrong image id is invisible by nature: it patches something real, just
not the intended thing.

- `validate_stock_image_ids()` runs before every build and checks all three
  hard-coded stock ids against the descriptor table. Given 615 it fails
  with `image id 615 is 'familytree_bg.jpg' ... expected
  'curtain_closed_southb.png'`.
- `work/audit_image_table.py` reads the descriptor table out of every built
  variant and verifies no stock slot is repointed and no added image reuses
  a stock id. B170: 19 variants, stock 0–636 intact, 751–814 added each,
  zero collisions.

## Bundle

The B169 packaging fixes are included: additive export now carries every
addition (7526 asset patches, was 1263), base-game classification uses a
recorded clean install rather than the working payload, and the release
gate simulates the install — 8193 of 8193 files reproduced byte-for-byte.

Verified by installing onto a clean base game with every patch enabled:
7305 images, 888 assets, matching a known-good install exactly.
