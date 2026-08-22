# B172

Force Successful Pregnancy is no longer spent by an unlucky roll. Otherwise
identical to B171.

## The change

Force Successful Pregnancy is a one-shot: you arm it expecting the next
attempt to work. `CVillager::StartEmbrace` could still refuse on a random
roll, so the armed shot got spent re-dropping the couple until the dice
cooperated.

While the upgrade is armed, **exactly two** refusals are skipped:

    +0x171  1846 "not in the mood"   gate +0x16F je   -> resume +0x17B
    +0x19D  1851 "can't agree"       gate +0x19B jge  -> resume +0x1A7

Both are pure `GetRandom` decisions about whether the couple feels like it.
Each is reached from exactly one gate, so each has a single unambiguous
resume point, and skipping one takes the very branch a luckier roll would
have taken — no state is skipped, because the native code had not yet done
anything different.

## Everything else is base-game

Verified by diffing the patched object against the stock one:

| refusal | status |
| --- | --- |
| 1857 too hungry | stock |
| 1853 under-age | stock |
| 1849 pregnant/busy | stock |
| 1847 illness | stock |
| 1850 same gender | stock |
| couch/bed check | stock |

Under-age and pregnant/busy were left alone for safety rather than
tidiness: the first would put a child into the routine, the second risks a
second impregnation. Illness could not be done cleanly in any case — its
refusal is reached from two different gates converging on one target, so a
cave there has no single resume point.

Each patched site uses the same 28-byte cave: the 5-byte `mov esi,
<StringId>` becomes a jump to a cave that asks the helper and either
continues at that gate's success target or reproduces the mov and the jump
verbatim. When the upgrade is not armed, every path falls through to the
stock instructions.

## Also in this release

- The six-child private-time predicate stays opposite-sex only. Making it
  gender-agnostic was a no-op — an active same-sex marriage already
  qualifies at any child count — and would only have leaked same-sex
  behaviour into the toggle-off state.
- README now states which copy of the game is supported: the Windows build
  from Last Day of Work's own website. The Steam release is untested and not
  known to match, and LDW's PC games are free on their site.
- README now documents the shipped patch list, and corrects the documented
  defaults: release bundles ship with the all-enabled profile, so Holiday
  Ornaments, Island Events, mobile room renovations, AI Bathroom 2 and
  **Cheat Upgrades** are on when you pick Defaults.

## Verification

- 19/19 variants built and linked, zero failures
- Image-table audit: stock ids 0–636 intact in every variant, no collisions
- Release gate: 8193 of 8193 Images/Assets files reproduced byte-for-byte on
  a clean install
- Installed onto a clean base game with every patch enabled: 7305 images,
  888 assets
