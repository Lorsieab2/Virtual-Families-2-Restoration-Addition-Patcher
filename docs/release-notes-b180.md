# VF2 B180 release notes

**The patcher bundle.** Prerelease for testing.

Marked prerelease: every automated gate passes and every fix below was
confirmed present in a linked build or in the shipped assets, but **nothing
here has been played.** Where a claim rests on static evidence rather than
live play, this document says so rather than rounding it up.

Every one of these came from the owner's own play session on B179.

## The added furniture now does something

The invisible Picnic Table, Patio Table and Lounger, and both Spa Loungers,
did nothing when a villager was dropped on them.

The cause was not the artwork or the placement maps, both of which were
correct. `theMainScene::VF2HandleDropOnMobileFurniture` dispatches on **item
id**, and of the twelve added items only the Invisible Spa Lounger (`0x32F`)
had a route. Everything else placed correctly and then had nothing asking it
to act — which is why the Spa Lounger appeared to be the only one that worked.

Routes now exist for the Invisible Picnic Table (`0x328`), Invisible Patio
Table (`0x329`), Invisible Lounger (`0x32B`) and the new visible Spa Lounger
(`0x330`). The Invisible Lounger is folded into the chaise family rather than
given a route of its own, so it inherits every chaise behaviour — including
any added later — instead of a copy of one.

**Seven items are deliberately not routed here** and rely on the game's native
hotspot path instead: the Invisible Kiddie Pool, Invisible Full-Size Pool,
Invisible Hammock, Invisible Yoga Equipment, Exercise Bike, Home Gym System and
Ping-Pong Table. They borrow stock desktop furniture, whose drop handling runs
through `HandleDropOnHotSpot` ahead of this dispatcher. Their placement maps
were compared against the donor maps in a real build and are byte-identical, so
the hotspot data they carry is already the donor's — and the Ping-Pong Table
demonstrably ran the Pool Table behaviour, which is why it displayed "playing
pool". **No player has confirmed these seven act on a drop, and this release
does not claim they do.**

## Villagers lie down properly on a Spa Lounger

Reported as: the NW orientation made villagers lie in the NE position, and the
NE orientation made them change behaviour immediately.

Both Spa Loungers already named the ordinary Lounger's map as their donor, so
on paper they used the same map. They did not. Mobile Furniture Behaviors ships
two maps per implemented item — a raw mobile base map and a desktop-safe one —
and the patch installed the desktop-safe map over each donor's **own** name.
A borrowing item's copy is written under the **borrower's** name, which that
pass never visited, so both invisible loungers shipped the raw mobile file.

The operative difference is the peep-slot anchor. B179 shipped the untranslated
mobile `0x01B09800` plus 142 mobile-only footprint cells; the desktop
`FindPeepSlot` path rejects every chair without the translated `0x00009800`.
That is the wrong lying position and the instant behaviour change.

Verified in this build: all three loungers now carry `0x00009800` and are
byte-identical to the desktop-safe donor map. The patio table's two seat
anchors were carrying a stray object type in the same way and are corrected
too.

## The hairstyle icons are no longer cut in half

The store icons were being cropped on the engine's own 28x56 indexing cell. The
drawn heads are about 29px wide and centred on 12 visual frames of 56x56, so a
28px cut removed half of every head.

Measured in the built assets: B179 shipped 100 icons per variant at 28x56 whose
opaque pixels ran to column 0 — touching the edge is what a clipped head looks
like. B180 ships them at 56x56 with the head occupying columns 15 to 43, clear
of both edges. They are cut at frame 5 of 12, the column the owner asked for.

## The action labels say the right thing

The Ping-Pong Table said "Playing pool" and the Exercise Bike said it was
walking or running on a treadmill, because both borrow those behaviours.

- Ping-Pong Table: **"Playing ping-pong"**
- Exercise Bike, walking: **"Using the exercise bike"**
- Exercise Bike, running: **"Doing high-intensity cycling"**

Animations are unchanged, at the owner's explicit instruction.

Each wrapper reads the placed furniture record the villager actually linked to
and compares its item id, so a stock Pool Table or Treadmill keeps its stock
label. B179 got this wrong by asking which furniture a villager *could* use —
a question that reserves a link as a side effect and answered about the wrong
table.

**"Rallying back and forth" has been removed** on request. It shipped in B179;
it is absent from every variant here.

## Store rows show a checkmark when they are active

The store draws a checkmark on any row it has nothing left to sell, which is
the wrong question for a row whose "active" is a state you can enter and leave.
Those rows are now answered from live game state: the four Special Upgrades,
Unlock Everything In The Store, the three price multipliers and Reset Price
Multiplier, Enable Same-Sex Marriage, Allow Reroll Of Marriage Candidates, the
pregnancy cheat rows, Anti-Spam and Rockhound ownership, and every house
renovation including both added catalogues.

Only the drawing changes. The click path still reads the real answer, so a
reversible row stays clickable — buying Unlock Everything again restores the
locks, and buying a different multiplier still switches to it.

## A Spa Lounger you can see

A visible **Spa Lounger** (250 coins) joins the invisible one and behaves
identically — they share one route rather than two copies of it. Art supplied
by the owner.

The treatment uses the nap's duration and posture, chosen from the placed
lounger's orientation so a villager does not lie across the arm of one placed
the other way round, and plays `gulpahh_01.ogg` periodically the way the
refreshing-drink behaviour does.

**Receiving a treatment is autonomous; giving one is not.** Giving requires a
second villager already receiving on that same lounger, and autonomous
selection picks one villager at a time — an autonomous giver would mime a
massage at an empty chair. The receiving half resolves an actual free Spa
Lounger before committing, because both Spa Loungers share their object type
with every stock and mobile lounger.

## Not included

**The picnic and patio table props.** `CEnvironment::SetProp` accepts prop ids
`0x00`–`0x54`; the picnic and patio drink props are `0x55` and `0x56`. The
compare is followed by a compiler-generated jump table whose index and target
displacements are link-time relocations, so admitting those two ids would read
past the end of the index table and jump through whatever followed. Doing it
properly means extending both tables and writing case bodies for two props that
have no desktop art and no desktop handler — a feature, not a bound
adjustment.

**Widowed remarriage.** A widowed adult cannot remarry naturally once there are
children on the family tree. The owner ruled this intentional base-game
behaviour, so the change built for it was withdrawn unmerged and is recorded in
the request ledger as working-as-intended.

## How this was checked

Every check below was first pointed at **B179** — the release that actually
shipped these defects — and confirmed to fail there. A checker that has only
ever seen a good build proves nothing.

- Action labels: fails on all seven B179 behavior-patches variants, catching
  the stale label and both missing bike labels. Passes here.
- Hairstyle icons: all 3200 B179 icons fail both the size and the edge check.
  Passes here.
- Lounger maps: 192 failures on B179. Passes here.
- Generated C compiles as a standalone translation unit, and no `__VF2_*__`
  placeholder survives into any emitted file.
- Every variant's executable has a distinct SHA-256.

What none of this covers is whether the game plays correctly, which is why
this is a prerelease.
