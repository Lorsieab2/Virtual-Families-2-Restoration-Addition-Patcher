# VF2 B181 release notes

**The patcher bundle.** Prerelease for testing.

Marked prerelease for the usual reason and one specific one. Every automated
gate passes and every fix below was confirmed present in a linked build or in
the shipped assets — but **the four new furniture actions have never been seen
in a running game.** They are verified in the shipped machine code, which is
not the same thing. Where a claim rests on static evidence rather than live
play, this document says so rather than rounding it up.

The furniture, prop and spa lounger items below were reported by the owner
playing B180. The furniture probe fix came from investigating one of those
reports and turned out to be a different defect from the one described. The
smaller corrections came from review findings rather than from play.

## The added furniture has actions of its own

The owner's instruction was that added furniture should not wear a donor's
action under a different name:

> the exercise bike's villager actions should not be a variation of the
> treadmill actions. they should be independent, but use the same animations,
> duration etc. and be exclusive to the exercise bike.

and then, generalising it:

> same for the other added furniture items

B180 shipped the opposite of that. The Exercise Bike wrapped the Treadmill's
behaviour and swapped the *label* when the linked furniture happened to be the
bike; the Ping-Pong Table did the same with the Pool Table. The plan,
animations and duration were the donor's, and so was the identity.

Five new behaviours now exist, each with its **own** id bound to its **own**
handler:

| id | behaviour | donor | item |
| --- | --- | --- | --- |
| `0x0B1` | `VF2ExerciseBikeWalk` | `WorkoutTreadmill` | Exercise Bike `0x32C` |
| `0x0B2` | `VF2ExerciseBikeRun` | `RunningOnTreadmill` | Exercise Bike `0x32C` |
| `0x0B3` | `VF2HomeGymWorkout` | `WorkingOut` | Home Gym System `0x32D` |
| `0x0B4` | `VF2YogaEquipmentWorkout` | `QuickWorkout` | Yoga Equipment `0x32A` |
| `0x0B8` | `VF2PingPongPlay` | `PlayingPooltable` | Ping-Pong Table `0x32E` |

Each new id clones its donor's autonomous candidate record wholesale and then
stamps its own id, so the gates, animations and duration are inherited rather
than reimplemented:

| donor candidate | clones to | weight |
| --- | --- | --- |
| `0x049` | `0x0B1` Exercise Bike, walking | 450 |
| `0x0E0` | `0x0B2` Exercise Bike, running | 450 |
| `0x04A` | `0x0B3` Home Gym System | 450 |
| `0x08B` | `0x0B4` Yoga Equipment | 450 |
| `0x099` | `0x0B8` Ping-Pong Table | 450 |

The donor supplies animations and duration only. Each handler runs the donor's
native plan unchanged and then applies its own label group, so a villager on
the Exercise Bike is running a *bike* action rather than a treadmill action
wearing a different name.

**The Home Gym System had no action at all before this.** Its donor is the
Yoga Equipment, whose behaviours are in-place animations that never consult a
piece of furniture — so cloning that donor produced a faithful clone of a
decoration. It could be bought, placed, and never used. It now has its own
behaviour with ten workout variations: *Lifting weights*, *Doing crunches*,
*Doing cardio exercises*, *Doing resistance training*, *Doing strength
training*, *Doing aerobic exercises*, *Doing endurance exercises*,
*Stretching*, *Doing high-intensity interval training*, *Doing weightlifting*.
The Yoga Equipment gets *Doing yoga*.

Two rules the owner set, both enforced structurally rather than asserted:

- **Stock donors are untouched.** Their own candidate rows are still enabled
  exactly as before; the new rows are additional. A stock Treadmill and Pool
  Table behave identically to B180.
- **Nothing is gated on ownership.** The donor behaviours stay globally
  available. Each new handler declines to act unless *its* item is placed, so
  owning an item **adds** an action and removes none. Positional, never
  permissive.

### What is and is not confirmed here

**Confirmed**, by disassembling the linked executable: each handler pushes its
own item id, calls `IsInWorld`, and returns early when the item is absent, and
all five registration entries are present in the shipped constructor exactly
once each. Those are the checks that carry the weight, because they are what
distinguishes this build from B180.

The ten Home Gym label strings also ship — but that fact proves nothing on its
own, and it is worth saying why rather than listing it as though it did. B180
contained all ten of those strings too, with no registrations, no handlers, and
a Home Gym that did nothing. String presence is satisfied by a build in which
the feature is entirely absent. Missing labels would still be a real failure,
so the check is worth running; it is simply not evidence that anything works.

**Not confirmed:** that any of this looks right in play. Nobody has watched a
villager walk to the gym.

**Separately not claimed:** that a villager *dropped* on one of these reacts.
That is a different question from an action a villager chooses. The drop path
is the game's own `theMainScene::HandleDropOnHotSpot`, which is 70 bytes —
`GetHotSpot` then `Dispatch` — and never reads a furniture item id, so it
cannot tell one added item from another however complete that item's record
is.

## The picnic and patio props draw

The owner reported the props not appearing on the tables. The art shipped and
the draw did not: `patch_mobile_table_prop_draw` was **defined in main and
never called**. The two prop ids never entered the engine's prop array and
that wrapper was their only draw, so the sprites installed into every build
and nothing drew them. It is now invoked.

Nothing in the test suite could have caught this. A function that is never
called cannot fail, the suite reads the generator rather than the build, and
the only symptom was a manifest key that was *absent* rather than wrong. A
check that every installer is actually reached now exists.

## The spa lounger treatment no longer loops

The owner reported the spa behaviours "still looping, broken and not at all
what I wanted". The fix existed and had been **stranded on an unmerged
branch**. The treatment split the rest into three `PlanToLieDown` calls, each
of which restarts the getting-in animation rather than continuing the rest,
and emitted the sigh once per slice so it replayed on every restart. It is now
one rest for the whole treatment.

## The furniture probe answers the right question

`VF2LinkedFurnitureItemIs` recovered the matched slot by hit-testing
`info.point` against the furniture footprint. Those two disagree about what
that point is: it is the **walk-to anchor**, not the furniture origin, so the
test asked "which furniture is the villager standing *inside*" — which for
anything you stand beside is nothing. The probe returned false for every item,
every time, which reads exactly like unwired code. It now matches on the
unique placement handle the furniture manager stamps into each record.

This is why the Ping-Pong Table kept saying "Playing pool" even after it had a
label of its own.

## Smaller corrections

- The placed-furniture sanity bound was `0x400`. The engine caps that array at
  `0x200` — both sites that compare the count against an immediate say so — and
  the guard now matches the binary.
- The Invisible Spa Lounger ships its own sprite **in the build**, not just in
  the source. Changing the item definition alone left the build emitting a
  generic brown chaise, because the sprite sync searched only one asset store
  and a stale seeded copy satisfied it with no error.
- The bundle's own documentation no longer describes the Home Gym as broken.
  It was broken when that text was written; it is not now.

## What is still outstanding

- **In-game QA on everything above.** This is the release to test.
- A fresh clone of the repository cannot run the full suite: several build
  inputs are untracked by design, and without them roughly 125 tests error in
  ways that look like regressions and are purely environmental. Pre-existing,
  unchanged by this release.
- The build manifest reports `outfit_store_icons` as `partial_or_failed`. This
  is **unchanged from B180**, which reports exactly the same status, so it is
  not caused by anything in this release. It has not been investigated and
  nobody has reported a problem with those icons. Recorded here because this
  document promises to say what is not confirmed, and a reader who opened the
  manifest would otherwise find that status with no acknowledgement anywhere.

## A note for anyone diffing the payload against a build

The bundle is an additive patch, not a file tree, and it carries one more
layer of indirection than that: `deduplicate_payload_files` collapses
byte-identical payload files to a single copy and rewrites every other install
record's source path to point at the survivor.

So counting payload *members* undercounts by exactly the number of deduped
aliases, and a file can be entirely absent as a member while still installing
correctly. `SpaLoungerStd.png` is the clearest case in this release: it is not
a payload member, and the manifest installs it from
`payload/Images/Furniture/InvisibleSpaLounger.png` — byte-identical, because
the owner's rule is that both loungers wear the same sprite.

That rule is also why the situation is new. In B180 the two loungers were
*not* identical, since the invisible one was still shipping a brown chaise;
there was nothing to collapse, so both shipped as members. Repairing the
sprite is what created the duplicate. Anyone comparing B180 against B181 by
member name will see the two files swap places and reasonably suspect a
regression.

The check that answers the real question is whether every file the build
produces has an install record whose source exists in the payload. For this
release: **6669 install records, zero unresolvable sources.** A further 597
build files carry no record because they are unchanged stock art the player
already has, which is what additive mode means.

## Build provenance

Built from `main` at `9f3bee0`, seeded per variant from the **B180** matrix
outputs.

The seed is not a plumbing detail. VF2 builds **inherit assets** from their
seed, so seeding from anything older than the previous release silently
carries that older release's art forward. This release was very nearly seeded
from B178, which would have dropped the corrected furniture art B180 shipped —
in a bundle that was internally consistent and passed every test. The
difference is measurable: the same tip and the same matrix config, built from a
B178 seed versus a B180 seed, produce executables with different hashes.

Each of the 32 seeds was checked individually for the three things the runtime
payload contract needs — `wc.dat`, the `Original Virtual Families 2 Assets`
folder, and a linked executable — rather than by taking the newest directory,
because an interrupted run leaves a directory that satisfies none of them and
the directory is created before anything links.

The widowed-remarriage change is **not** included: the owner ruled that
behaviour intentional base-game design.
