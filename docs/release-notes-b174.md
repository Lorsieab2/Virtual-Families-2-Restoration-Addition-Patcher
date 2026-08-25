# B174

Fixes the two Flea Market ownership cheat rows shipped in B173. Otherwise
identical to B173.

## The bug

Buying **Anti-Spam Software Ownership** or **Rockhound Certificate Ownership**
while the row was already checked did nothing: the checkmark stayed on and the
upgrade stayed owned. Turning a row on always worked; only turning it off was
broken.

## Why

Reporting active is what broke it — the same property that draws the checkmark.

`VF2B150UpgradeIsActive` decides whether the store draws a row's owned
checkmark, and it *also* gates `VF2RemoveOwnedUpgrade`. So buying an active row
is captured by the removal route before the apply handler ever runs. These two
rows had no branch of their own there, so the click fell through to the generic
tail:

```cpp
InventoryManager.ReturnOne((EInventoryItem)itemId);   // itemId = 0x158 / 0x159
```

That is the **cheat row's** id, not the stock item. The inventory does not hold
it, so the call did nothing, returned `true`, and swallowed the click.
`VF2ToggleStockOwnership` never ran and the flag stayed set.

The pregnancy one-shot rows carry a comment about exactly this hazard: anything
reporting active through that predicate must handle its own removal. The
warning was there and these two rows were still written past it.

## The fix

`VF2RemoveOwnedUpgrade` now has an explicit branch for the ownership rows that
clears the **stock** flag — `theGameState+0x6C` for Anti-spam Software, native
inventory ownership of item `0x10a` for the Rockhound Certificate.

The write is split out of the toggle into `VF2SetStockOwnership(itemId, owned)`
so the removal route can only ever remove. Expressing it as a toggle there would
let a future caller re-enable an upgrade through the remove path, which is not a
thing a removal route should be able to do.

Turning a row on is unchanged: an inactive row is not captured by the removal
route at all, so it reaches the apply handler as before.

## Verification

Disassembled from the linked executable:

- Anti-spam → `mov cl, [esp+8]` / `mov byte [eax+0x6C], cl` — writes the
  requested value rather than toggling blindly
- Rockhound → `push 0x10a` then `HaveUpgrade` / `TakeOne` / `ReturnOne` — the
  **stock** item, not the cheat row's id

Also:

- All 19 variants build, link, and pass both asset guards, with zero missing
  base-game files.
- Image-table audit: 19 variants, 0 problems — stock images 0..636 intact, no id
  collisions.
- Test suite: 291 passed, 113 subtests. The test asserts the removal route
  clears through the setter, that it does not call the toggle there, and that
  the toggle is defined in terms of the setter.

Both directions of both rows were confirmed in-game before this release.
