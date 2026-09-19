# VF2 B187 release notes

**The patcher bundle.** Prerelease for testing.

Marked prerelease for the usual reason, and this time it carries extra weight:
every automated gate passes and each fix below is present in the generated C++
the build compiled, but **nobody has yet watched these behaviours in live
play**. Several of the defects below were reported fixed more than once before
and were still broken when the owner played them, so a passing suite is not
being offered here as evidence that anything works on screen.

A note on what the B187 prerelease *was*. The archive previously published
under that tag was not a patcher at all — it was a playable patched game:
`Virtual Families 2 - B187 Furniture Fixes v2.exe` shipped beside `Assets/`,
`Sounds/`, `wc.dat` and the SDL/fmod DLLs, with none of the patcher's own
files. No `offline_vf2_patcher.py`, no `payload/`, no `Apply_B187_Patcher.bat`.
Both artifacts are named `VF2-B187-Release.zip`, so the name did not
distinguish them; the size did, at roughly 301 MB against the patcher's 144 MB.
This build replaces it with a real patcher bundle.

## The mobile APK settled several questions that guesswork had not

The owner supplied `Virtual Families 2_1.7.16_APKPure.xapk`. Decoding
`main.43.com.ldw.virtualfamilies2.obb` established something that changed the
shape of the whole round of fixes: **the furniture data the PC port ships is
already correct**, and every defect below is in the code that consumes it.

For the picnic and patio tables, the APK-vs-PC difference in every seat cell is
a single constant per table — `0x03AC0000` and `0x01B40000` — which is only the
mobile room/hotspot id the PC port strips. The seat markers themselves are
bit-identical. For the yoga mat, `assets/YogaGearStd.png.fmap` is
**byte-identical** to both shipped PC maps, including its six-cell stand block.

So no `.fmap` was edited in this release, and none needed to be.

## Villagers at the picnic and patio tables sat facing the wrong way

Reported from play with screenshots for both tables: at the picnic table the
villagers on the right-hand side faced outward while the left side looked
correct, and at the patio table one chair seated a villager correctly while the
other left him on the ground beside his chair, facing the wrong way.

**One `sFurnitureInfo2` is filled per *placement*, not per seat.**
`LinkPeepToFurniture` returns a single `info.orientation` for the table, so
choosing the sit animation from it alone gave **every seat at that table the
same facing**. That is not a near miss; it is geometrically impossible for a
table whose seats sit on opposite sides, and it is exactly what the screenshots
show — one side right, the other reversed.

The fix takes the seat from **the engine's own choice**, and the route there is
worth recording because the obvious approach fails silently.

The first attempt compared the seat's position against the table's, expecting a
signed offset. `LinkPeepToFurniture` at +0x261–0x283 computes

```
info.point.x = record[+0x14] + (seatAnchor.x - contentBlock.origin.x)
```

so that difference is a column offset measured from the content block origin,
and is **non-negative for every seat on both tables**. The comparison answered
the same way for all of them, the per-seat selection collapsed straight back to
one facing per table, and the defect would have shipped unchanged. It was
caught in review rather than by the test suite, because the tests pinned the
helper's structure rather than its ability to distinguish anything — the same
lesson as the spa lounger below.

What the engine already does: it loads the seat-marker array
`{0x13, 0x14, 0x53, 0x54}` — the markers `docs/discoveries.md` records as
selecting the exact `Sit In Chair NW` or `NE` label — indexes it by the seat it
chose, and writes the villager's peep id into `record[+0x20 + index*4]`. So the
index is recoverable after the link.

Which ordinal sits on which side then took **two** more attempts, and only the
decoded object ids settled it. `CContentMap::FindObject` extracts a cell's
object id as `((cell >> 11) & 0x40000 | cell & 0x3F800) >> 11`, which gives:

```
Picnic_table   (5,9)=0x13 west    (8,11)=0x14 west
               (15,12)=0x53 EAST  (17,10)=0x54 EAST
Patio_table    (3,8)=0x13 west    (13,8)=0x14 EAST
```

`0x14` is **west** on the picnic table and **east** on the patio table, and the
patio table has no `0x53`/`0x54` at all — so no fixed grouping of the four
markers is right on both. An intermediate version used the ordinal's low bit,
which groups `{0,2}` against `{1,3}`; that is correct on the two-seat patio
table and wrong on the four-seat picnic table, where it puts one west and one
east seat in each group. Two of four villagers would still have faced the wrong
way.

What holds on both: `FindPeepSlot` enumerates the markers the block actually
has, in that fixed order, and each map puts the first half of the enumeration
on one side and the second half on the other. So the side is
`ordinal >= seats / 2`.

## The spa lounger's orientation "had no change"

Reported a third time, in those words. The report was accurate and the reason
is arithmetic rather than subtlety.

The head direction came from `VF2FurnitureFacesNorthWest`, which is
`orientation == 3`. `EFurnitureOrientation` is SE=0, SW=1, NE=2, NW=3, so:

| furniture | old head direction |
|---|---|
| SE (0) | NE |
| SW (1) | NE |
| NE (2) | NE |
| NW (3) | NW |

**Three of the four placements produced an identical pose.** Rotating the
lounger genuinely changed nothing for most of them, which is what "no change"
looks like from the player's side. The two head directions are an east/west
pair, so the split is now `{SE, NE}` against `{SW, NW}`.

> **SUPERSEDED FOR THE SPA RECEIVING POSE.** "Applied at all three lounger
> sites" was true of B187 and is no longer the rule. The owner playtested B189
> and the villager was still lying across the spa lounger; the **receiving**
> pose needs the **mirror** of whatever the orientation test picks, so it takes
> the opposite arm from the two relax poses. The east/west split described here
> still governs the two chaise relax poses and the shared predicate. Do not
> re-apply it to `VF2PlanSpaTreatment`. See issue #330.
>
> Still true and NOT superseded: the settle pose and the sleep strip must
> derive from ONE test so they cannot disagree. That property is preserved by
> mirroring both together.

Applied at all three lounger sites. The spa settle pose and the
`SleepNW`/`SleepNE` strip now derive from one test so they cannot disagree, and
the invisible Spa Lounger is covered because `VF2SpaLoungerHasHandle` matches
both item ids.

## Villagers doing yoga stood beside the mat

Reported with a screenshot: the villager stands on bare floor off the mat's
right edge.

The fmap is not at fault — it is byte-identical to the mobile original — so the
hotspot the engine derives from the six-cell stand block lands at that block's
**edge** rather than its middle. The walk-to destination now takes an
orientation-aware correction toward the centre, covering the stock Yoga
Equipment (`0x220`) and `InvisibleYogaEquipment`.

The Home Gym borrows the same mat's fmap and keeps its own separate correction,
because the gym's cubby is not the mat's centre. A stale comment claiming the
Yoga Equipment "stands correctly" is recorded as wrong in place rather than
deleted.

## Bike actions ran on the treadmill, and pool was played at the ping-pong table

Reported repeatedly, and the reason the earlier fixes did not take is worth
stating plainly: **they corrected the caption, not the venue.**

Each donor's prologue, decoded from `Behavior.obj`, is

```
FeetPos(); FindFurniture(object, feet, info, ...); strncpy(caption); PlanToGo(...)
```

`FindFurniture` runs **first**, as a nearest-match from the villager's
**pre-walk** feet. The venue window intercepted only `PlanToGo`, so it rewrote
the *destination* while the donor stayed bound to whichever shared-EObject
placement happened to be nearest — the Treadmill instead of the Exercise Bike,
the Pool Table instead of the Ping-Pong Table. Relabelling afterwards cannot
undo that; the villager is already bound to the wrong machine, with its
animations and its orientation.

The window now also covers `FindFurniture`, for the three donors that share an
EObject with a stock item: `WorkoutTreadmill` and `RunningOnTreadmill` on
`0x04`, `PlayingPooltable` on `0x36`.

This also gives the requested drop behaviour. A villager dropped on the
Treadmill never matches the bike's item id, so the bike candidate declines and
the stock treadmill behaviour runs with its own labels.

### Two review findings on that fix, both of which mattered

Automated review raised two P1s against the interception, and neither would
have been caught by the test suite.

**The wrapper corrupted the stack.** `FindFurniture` takes seven stack words,
not six: `ldwPoint` is passed by value and is eight bytes. The naked wrapper
forwarded six and cleaned 28 bytes instead of 32, so the helper read its own
return address as its final `bool` and left the donor's stack four bytes out of
position at every retargeted callsite.

**The lookup searched from the wrong origin, and this one would have left the
reported bug in place.** `FindFurniture` ranks candidates at `0x52`–`0x66` by
distance to each record's **own placement**, then returns `info.point` as that
placement **plus the hotspot offset**. The window was feeding `info.point` back
in as the search origin — off by exactly one hotspot. With an added bike or
ping-pong table standing near a stock treadmill or pool table, the **stock**
record can be closer to that anchor, so the lookup could still return the wrong
machine while every test passed. The window now carries the resolved record's
placement, which makes the intended record's distance zero.

## Prop positions

The picnic meal moves further up and further toward the table's own NE/NW side;
the patio drinks move further right to reach the table centre. These are
screen-space nudges chosen by eye against the art, not values derived from
data, so they are the fixes in this release most likely to need another pass
after the owner looks at them.

The Home Gym stand position was likewise raised toward the bottom corner.

## What was deliberately not changed

An automated finding asked for the venue-decline branch to fall back to the
stock donor when no venue is placed. That was dispositioned as not actionable:
acting on it reintroduces the cross-targeting above. The added items use their
own behaviour ids (`0x0B1`–`0x0B8`) while the stock donors keep their own
registrations and stay globally available, so no donor is gated and a player
who owns none of these items loses nothing. The manifest records this as
`ownership_gate: false`.

## Evidence boundary

Everything above is **static and disassembly evidence**: source, decoded object
files, the compiled executable, and the build manifest. Each fix is two-way
validated, meaning reverting it makes a test fail, and the generated C++
compiles. For the table seating the tests additionally assert that the
selection DISCRIMINATES -- that no orientation gives every seat the same
facing and no seat ignores the rotation -- because the first version of that
fix passed a structural test while having exactly one reachable answer.

None of that establishes that a villager sits the right way, walks to the right
machine, or stands on the mat. **Live play by the owner is the only thing that
will settle these**, and until it happens every behavioural claim in this
document should be read as "the mechanism is present and reachable", not as
"the defect is fixed".

---

# Round 3 (playtest feedback on the round-2 asset)

The round-2 asset fixed picnic and patio seating, confirmed in play by the
owner. Four defects survived, and this round addresses those four.

## Spa Lounger: the previous three attempts were arguing about the wrong argument

The owner reported "they lie across it", with a screenshot of a villager lying
across the lounger rather than along it. That is a different fault from facing
the wrong end, and it explains why three successive fixes changed nothing.

`eBodyPositionChaise` carries no facing of its own, and the three-argument
`PlanToWait` supplies only a HEAD direction. The BODY therefore kept whatever
facing the villager walked in with. The first attempt tested
`orientation == 1`, the second `orientation == 3`, the third split east/west --
all three tuned an argument that was never controlling the body. No orientation
test could have caught this, because every one of them asserted on the head
argument that was being passed correctly.

The four-argument overload

    ?PlanToWait@CVillagerPlans@@QAEXHW4EBodyPosition@@W4EDirection@@W4EHeadDirection@@@Z

is present in the game's own object file and the patio umbrella route already
calls it in shipped code. All three chaise pose sites now pass a body
direction. `EDirection` was decoded from `AnimManager.obj` CodeView
enumerators as Northeast=0, Southeast=1, Southwest=2, Northwest=3 -- which is
NOT the `EFurnitureOrientation` ordering (SE=0, SW=1, NE=2, NW=3), so the
orientation is mapped rather than passed through.

This is the fourth attempt at this defect and the first to change the
mechanism instead of the argument.

## Treadmill: a regression introduced by the round-2 fix

Dropping a villager on a Treadmill produced "using the exercise bike" and
"doing high-intensity cycling" instead of the treadmill's own actions. The
cause was in the round-2 venue-routing change: the position check ran only
when the item was absent, so a placed Exercise Bike could still capture a
villager already standing on the Treadmill. The guard now runs before the
venue window opens.

An automated review correctly found the first version of that guard too broad:
it declined an autonomous Exercise Bike action whenever the villager stood on
ANY furniture, including a sofa. The suggested remedy -- limit the guard to
manual drops -- was not taken, because the owner asked for the Treadmill to be
stock "on both manual drop and autonomous villager behaviors", and a drop-only
guard leaves the autonomous half open.

The guard was narrowed instead. The hijack exists because the venue window
redirects the DONOR's `FindFurniture`, and a donor only ever searches its own
object id, so a villager can be stolen only from furniture answering that same
object: Treadmill and Exercise Bike are both `0x04`, Pool Table and Ping-Pong
are both `0x36`. A sofa is not `0x04` and was never at risk.

## Owner-specified nudges

Patio drinks moved to X=18 (from 13), and the yoga mat centre offset is 5 with
the Y sign corrected to `-=`, since +Y is down-screen and the previous `+=`
moved the villager the wrong way. Picnic meal 7/9, Home Gym stand 14/12.

## Evidence boundary for round 3

Verified: all 32 variants link, the ZIP gate passes, an independent verifier
authenticates the variant identities, a clean install plus this bundle
reproduces 8,226 of 8,226 asset files byte-for-byte, no features are lost
against 7 retained releases, and the `mobile_furniture_behaviors` flag flips
`00`->`01` in `.vf2beh` for all 32 executables.

Each of the four fixes was confirmed present in the C++ that the shipped
build compiled from, regenerated with behaviour patches enabled. That last
step matters: the leftover `.cpp` files in the shared build directory come
from whichever variant the matrix built last, which was a behaviour-patches-OFF
variant whose spontaneous-behaviours unit is a 78-byte stub. Reading those
files would have suggested the fixes were missing when they were not.

**None of the four round-3 fixes is verified in play.** The spa lounger
especially is the fourth attempt at the same defect, and only the owner's
playtest settles whether the body now aligns with the furniture.
