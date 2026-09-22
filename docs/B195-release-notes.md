# VF2 B195 release notes

**The patcher bundle.** Prerelease for testing. Built from `main` at
`a955db4` (PR #370), seeded from the B194 matrix.

B195 ships one owner-reported bug fix. Everything else is B194.

## Invisible furniture responds to a dropped villager while transparent

Reported: with the **Swap Invisible Furniture Graphics with Transparent
Graphics** setting on, dropping a villager on an Invisible Patio Table, Picnic
Table, Spa Lounger or Yoga Equipment did nothing, while the same items worked
with visible graphics and transparent pools and couches worked either way.
Present on B192, B193 and B194: a pre-existing bug, not a regression.

Why: when a villager is dropped the game has to decide what furniture is under
the point, and different items use different code to decide. Native items --
pools, couches, beds, the hammock -- resolve through the content map's fmap
cells, pure geometry, so the sprite never matters. The items the patcher routes
by id for their custom behaviours (spa treatments, picnic, yoga, ping-pong) are
identified through the stock `PtOnFurniture` hit-test, which after a bounding
box check samples the sprite's own pixels and counts a hit only where alpha is
not zero -- the right test for clicking something visible. A fully transparent
sprite has no such pixel, so the item resolved to nothing and every route was
skipped. The broken set is exactly the routed set: Patio Table, Picnic Table,
Spa Lounger, Yoga Equipment, and also the Invisible Lounger and the Invisible
Ping-Pong Table, whose "plays pool" was this same failure -- the patcher path
could not claim the transparent table, so the stock path claimed it as its
Pool Table donor. The owner confirmed the partition in play.

Fix: the stock resolver still runs first, unchanged, so every visible item and
every native item keeps exactly the behaviour it had. Only when it finds
nothing does the dispatcher fall back to the geometry the engine itself placed
for the item: for each placed routed item it takes the content block the game
loaded from that item's fmap for the orientation actually placed (authored,
mirrored, or the second block and its mirror), anchors it exactly as the game's
own `ApplyFmapContent` anchors it on the content map (placement position minus
the block's origin, at the map's 8 pixels per cell), and treats the cell under
the drop point as a hit when the block occupies it -- the same nonzero-cell
rule the engine uses when it writes the block into the map. Nothing is baked
at build time and nothing is guessed about orientation; the fallback agrees
with the content map by construction. The sprite is never consulted, so it
stays fully transparent; no opaque pixels are needed. Issue #369, PR #370.

Review history, for the record: the first draft of this fix baked each item's
cells into a table and re-derived the placement at 16 pixels per cell with no
origin and a mirror guess in place of the orientation; the second gated the
hit on the map's object bits, which mark only a few hotspot cells per item.
Codex review caught all four before anything shipped.

Verified against the emitted dispatcher (the fallback and its hook), the stock
disassembly (every offset the fallback uses -- orientation, block table, origin
subtraction, placed flag -- is the one `ApplyFmapContent` and `LoadFmap` use),
a full generator run and the compiler. Not verified in play.

**Playtest:** with Transparent Graphics on, drop a villager on each of the six,
in both orientations where the item can be flipped. A drop just outside an
item should still do nothing.

Still open from B193/B194, for the owner's eyes: Achiever Extraordinaire is the
bottom Goals row with Holiday Furniture on; the Invisible Ping-Pong Table plays
ping-pong; Achiever awards in a build without Holiday Furniture.
