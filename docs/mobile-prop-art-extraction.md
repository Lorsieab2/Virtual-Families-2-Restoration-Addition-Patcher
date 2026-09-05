# Extracting the mobile picnic-meal and patio-drinks prop art

Notes for whoever builds the picnic/patio props. Everything below was verified
against the real files; the one place it stops is stated plainly rather than
guessed past.

## The art exists, including the drinks

An earlier reading of this concluded that "mobile never drew the patio drinks,
so there is nothing to port". **That was wrong.** The sprites are in the mobile
build:

    assets/tp7.dat  ->  meal.png, mealse.png, mealsw.png, patiodrinks.png
    assets/tp236.dat -> picnic_table.png, patio_table.png, patio_umbrella.png,
                        patio_brick.png, patio_cobblestone.png

`mealse` and `mealsw` are orientation-specific, which fits the owner's account
that the villager behaviour activates the prop on the table rather than the
table swapping to a different image.

## Where they live

Source: `Virtual Families 2_1.7.16_APKPure.xapk` (the owner's Downloads).

    xapk
      com.ldw.virtualfamilies2.apk                      <- no images
      Android/obb/.../main.43...obb                     <- 1093 entries, the art

The OBB holds 316 `.ogg`, 276 `.fmap`, 251 `.dat` and 245 `.pvr`. Images are
packed into `.pvr` texture atlases with a matching `.dat` per page.

`tp7.pvr` is **PVR v2, 1024x1024, RGBA4444, 16bpp, uncompressed** — no PVRTC
decoding needed. Header is 52 bytes; magic `PVR!` at offset 44. Decode as:

    v = lo | (hi << 8)
    r = ((v >> 12) & 0xF) * 17
    g = ((v >>  8) & 0xF) * 17
    b = ((v >>  4) & 0xF) * 17
    a = ( v        & 0xF) * 17

That produced a clean full-atlas PNG, so the format is settled.

## The trap: the .dat coordinates are NOT atlas coordinates

This is the part worth reading before spending time.

Each `.dat` record looks like `len, name, 00 00, a, b, w, h, w, h` as LE
uint16, and for `meal.png` those fields read:

    a=74  b=535  w=160  h=68  (dup 160x68)

The width and height are right — 160x68 matches the desktop `meal.png` byte for
byte in size. **The 74,535 is not where the sprite is.** Cropping there gives a
plausible-looking image that is wrong.

This was caught only because `meal.png` also ships on the desktop, so there was
a known-good copy to check against:

    cropped at .dat (74,535)   -> 35.5% alpha-shape mismatch
    located by matching        -> (244, 424), 220/220 sample points, exact

So `a`/`b` are something else — packing metadata, a trim offset, or an index
into another structure. Someone needs to work out the real layout.

Two approaches that will NOT work, both tried:

- **Assuming a constant delta.** meal's true position is (+170, -111) from its
  `.dat` values. Applying that to `mealsw.png` lands on a region that is 98/7705
  opaque, i.e. essentially empty.
- **Density scanning for opaque rectangles.** The atlas is densely packed;
  searching for a `w x h` block that is >55% opaque returns 12,000-20,000
  candidates per sprite, many of them 100% opaque. It cannot disambiguate.

## The approach that does work

Cross-reference against sprites whose desktop equivalents already exist. For
each candidate offset, compare the alpha silhouette to the known-good desktop
PNG and require a near-perfect match, as was done for `meal.png`. Decode the
record layout from several such anchors rather than one, then apply it to the
three sprites that have no desktop copy.

**Do not skip the control.** Without checking `meal.png` against the shipped
desktop file, three plausible crops from the wrong coordinates would have looked
entirely convincing.

## What is already in place

- The PC `.fmap` files retain the special-prefix attachment cells:
  `0x2000B800` x4 on `Picnic_table.png.fmap`, `0x2000C000` x6 on
  `Patio_table.png.fmap`. The mobile originals carry the same cells with the
  object id in the high half (`0x23AC` / `0x23B4`), which the PC conversion
  strips.
- State tracking already works. `VF2PatioSetPropAndTrack` intercepts the two
  prop ids, and maintains a guarded external 240-game-second timer with the
  preparing villager recorded. It simply never draws anything.
- The drinking sounds ship on desktop already: `sip_drink.ogg`,
  `ahh_drinking.ogg`, `drinking.ogg`.

## Why the draw belongs in the DLL

`CEnvironment::SetProp` bounds at `cmp edi, 54h` and the two props are `0x55`
and `0x56`. All 27 jump-table cases are claimed by existing props, and every
jump entry is a `DIR32` relocation, so adding a case means editing the COFF
relocation table of a stock object.

The companion DLL avoids that entirely and matches the owner's standing
preference for DLLs over in-exe caves. It can read the existing external state
and draw at the attachment cells without touching `SetProp` at all.

## CORRECTION: the sprites are not decodable from tp7.pvr as written above

Everything above about *where the names live* holds. The decode does not.

`tp7.pvr` was decoded as PVR v2 RGBA4444 and the result looks plausible --
443k fully transparent pixels, varied colour elsewhere. It is still wrong, and
the control proves it. Searching the whole decoded atlas for the desktop
`meal.png` by RGB distance over its opaque pixels gives:

    RGBA4444  best mean error 59.7
    BGRA4444  best mean error 55.4
    ARGB4444  best mean error 68.2
    ABGR4444  best mean error 65.9

RGBA4444 quantisation should put a true match near 8, not 55. No channel order
produces one, so `meal.png` is not present in the decoded image at all.

An earlier note in this file claimed `meal.png` was located at (244,424) with
"220/220 sample points". That was a FALSE POSITIVE: the signature compared only
whether sample points were opaque, and most of the sampled points were
transparent in both images, so a large transparent region scored perfectly.
Checking actual colour at that position gives solid purple (136,51,221) against
the sprite's green (53,102,38), and 1420 of 2720 sampled pixels disagree on
alpha. The "exact" match was an artifact of the metric, not a location.

So the remaining unknown is larger than "the .dat coordinates are wrong": the
pixel data itself is not a plain linear RGBA4444 buffer. Possibilities not yet
ruled out -- twiddled/Morton ordering (common in PVR v2), a second compression
layer, or the sprites living on a different page than the one naming them.

What is still solid:

- the sprite NAMES are in `assets/tp7.dat`, including `patiodrinks.png`
- `mealse.png` / `mealsw.png` exist, so the prop is orientation-specific
- the widths and heights in the .dat records ARE right; `meal.png` reads
  160x68 there and the desktop file is 160x68

What must not be trusted from the earlier section: the (x,y) interpretation,
the "verified" (244,424), and any crop taken from the decoded atlas.

Do not extract sprites from this atlas until a control sprite with a known
desktop copy round-trips to a mean RGB error in single digits. That check is
cheap and it is the only thing separating the real art from a convincing crop
of the wrong pixels.
