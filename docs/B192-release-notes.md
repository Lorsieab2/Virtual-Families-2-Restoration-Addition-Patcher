# VF2 B192 release notes

**The patcher bundle.** Prerelease for testing. Built from `main` at
`12382b8` (PR #359), seeded from the B191 matrix.

B192 ships four owner-requested changes. Everything else is B191.

## 1. The career-room goals come back on load and after Reset Achievements

Reported: "Office of the Future" did not autocomplete with every career
upgrade owned; the same for the kitchen and workshop goals once a save
already had its ten purchases.

Decoded from the stock objects: these three goals are not counters. The
game's own `CTech::Level(tech)` rebuilds each one from `HaveUpgrade` over
its item range (kitchen items 0xF6..0xFF → goal 0x36, office 0xEB..0xF5 →
0x37, workshop 0x100..0x109 → 0x38), resets the record and increments it by
`min(count, 10)`. The stock game only runs it on an upgrade purchase, so a
save whose records were wiped while the upgrades stayed owned — the
patcher's Reset Achievements cheat does exactly that — never saw them come
back.

The `CTech::LoadState` call inside `theGameState::Load` is retargeted to a
wrapper that runs the native load and then `Tech.Level(0..2)`, the same
relocation-only shape as the pet and achiever load hooks, and the reset
cheat runs the same recompute after `Achievement.Reset()`. Both primitives
are no-ops on a completed record, so completed goals are untouched.
Confirmed in play on a probe build (owner: "very good. the probe works").
PR #357.

## 2. A fifth child-discipline goal: "No banging dishes together!"

Requested: a goal titled "No banging dishes together!" with the description
"You scolded a child for banging dishes.", counting towards "Props to you".

Id 0xAB, the next record past the defined edge (0xA8 stays the purchase-mask
scratch record). The award is an exact match on the native behaviour label
"Banging dishes!" (string key `BangingDishes`, exclamation mark included),
child-only like its four siblings. "Props to you" (0xA5) now requires it at
both decision sites, the scold award path and the load reconciliation, so
its description ("all five additional discipline goals") is literally true.
The goal sits right after "No messing with the light switch!" on the Goals
screen and pays the default 25 coins. PR #358.

Not yet confirmed in play: scolding a child whose label reads "Banging
dishes!" awards it (same mechanism as the four existing discipline goals).

## 3. Event collectables replace the oldest unpicked one when both slots are busy

Reported: the mobile email "Interesting Article about Fossils" never left a
fossil mound in the yard. Owner decision: "fossil email (and any other event
that spawns collectibles) = replace the oldest unpicked collectible", and
"check all mobile and native pc island events and email events for the
spawn collectibles bug".

Decoded from `CollectableItem.obj` and confirmed live: `CCollectableItem::Add`
keeps exactly two event slots (+0x34C, +0x368). With `force == false` it
takes the first free one and returns without spawning when both are busy;
with `force == true` it always writes slot 0. Natural spawns keep the pair
busy most of the time, so the email produced nothing. The mobile 1.7.16
library (`libVirtualFamilies2.so`) has the identical two-slot `Add` and the
identical fossil outcome, so the port was faithful and the failure is
mobile's own.

Every event that spawns a collectable — the mobile fossil email, the native
Bug Whisperer (two spawns) and the native Neighbor Collectible — now goes
through one helper: a free slot is always used first; otherwise the slot
nobody is walking to, else the older spawn stamp, is freed with the native
`Remove(slot)`; the native force path keeps its semantics but moves slot 0
aside so the survivor is kept. Refinements from review: a sacrificed record
is snapshotted and restored if the native spawn does not activate (the
forced random path can still give up after a thousand invalid positions);
the item a burst just spawned is never the next victim (the Bug Whisperer's
second spawn), bounded by the game clock so a leftover record is not
protected hours later. The three native callsites are retargeted by
relocation to a `__thiscall`-shaped thunk, in every variant. Natural
periodic spawns are deliberately untouched. All 25 mobile outcomes were
re-checked against the mobile library and match. PR #359.

Confirmed live on a probe build of the branch with both slots occupied by
unpicked items: the older one was freed and the fossil spawned in it at
(1383, 1910), inside the front-yard rectangle; the newer item survived. In
the unpatched build the same click spawned nothing.

## 4. The two Cheat Upgrades spawn rows spawn fifteen each, evenly split

Requested: "Fill available house slots with trash" spawns 15 pieces made of
equal amounts of dirt smudges, socks and wrappers; "Fill available yard
slots with weeds" spawns 15 weeds with equal numbers of each weed type.

The native spawners take the first free of the 30 mess slots and roll a
random sub-type. The cheats now spawn one item at a time through the native
routine and pin the sub-type of the slot it just filled: 5 smudges, 5 socks
and 5 wrappers with the sub-types cycling, and 15 weeds cycling the four
weed types (4/4/4/3 — fifteen is not divisible by four). The cycle
positions carry over from one press to the next, so all six sock sub-types
are reached and the weed type that gets three rotates. Both stop early when
the 30 slots are full. PR #360.

Not yet confirmed in play: the visible mix after pressing each cheat.

## Closed without a code change

- "Ping-Pong Table not appearing in the Decorate tab": buying it in a probe
  running the owner's exact exe and a copy of the save put item 0x32E in
  storage (money 21048 → 9048); the owner then had it placed. Not
  reproducible.
- "Villagers dropped on the Ping-Pong Table play pool at the pool table" and
  "the invisible patio and picnic tables have no actions": both were
  observed in a probe built from the plain core variant with the mobile
  furniture behaviours flag off. In the owner's real build (Final
  All-Enabled, all runtime flags on) both work; the owner confirmed.

## What to check

- **Goals:** with every office/kitchen/workshop upgrade owned, load the
  save; the three career-room goals should complete. Scold a child who is
  banging dishes; "No banging dishes together!" should complete, and with
  the other four discipline goals and Tight Ship, "Props to you".
- **Fossil email:** when "Interesting Article about Fossils" arrives and the
  yard already has two collectables, one mound should still appear in the
  front yard after OK (the older unpicked collectable is replaced).
- **Cheats:** "Fill available house slots with trash" should leave 5 dirt
  smudges, 5 socks and 5 wrappers; "Fill available yard slots with weeds"
  15 weeds of all four kinds.

## Evidence

| Check | Result |
|---|---|
| Owner playtest | career goals confirmed on probe v19 ("very good. the probe works"); ping-pong drop and invisible tables confirmed working in the owner's build |
| Live probe, event collectables | both slots occupied → older unpicked freed, fossil 113 spawned at (1383, 1910), newer item kept; unpatched build spawned nothing |
| Full regression suite, per branch | #357 1171 passed; #358 1178 passed; #359 1205 passed (rebased tree identical to main's); #360 1165 passed; 0 failures on every final tree |
| Mutations caught | 7 career goals, 12 dishes goal, 21 event collectables, 15 spawn cheats — every single-site mutation fails its suite alone |
| Codex review rounds | #357 and #358 clean; #359 five rounds, four findings each fixed and pinned; #360 three rounds, four findings each fixed and pinned |
| Matrix build | 32/32 linked, EXIT=0, 57 min, built from main at 12382b8 (tree 8b1b391), seeded from B191 |
| Export | 8226 of 8226 Images/Assets files reproduced byte-for-byte on a clean install; 7455 payload files, 7574 asset patches, 32 executables |
| Repository gate, identities enforced | PASS — 32 variants authenticated against the independent identities, 7467 members, no features lost vs 12 retained releases |

## Artifact identity

    VF2-B192-Release.zip
    sha256  a2d79c2319f2716a2df51c1bbf3abe1f9df42cf40632fb5e4b514fa4597331d6
    bytes   144,583,061
    built from main at 12382b8 (PR #359)
    tree    8b1b39199cfa42e4e94d0e0c4bc2188130f2ce95
