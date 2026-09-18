# VF2 B188 release notes

**The patcher bundle.** Prerelease for testing.

Every automated gate passes and each fix below is present in the generated C++
the build actually compiled. **Nobody has watched any of these behaviours in
live play.** Several of the defects below have been reported fixed more than
once and were still broken when the owner played them, so a passing suite is
not offered here as evidence that anything works on screen.

Two of the seven items have hard evidence *inside the shipped archive*, which
is stronger than a passing test but still not a playtest. The other five are
compiled code paths with no artifact-level probe at all, and they are marked
as such rather than implied to be verified.

## The seven fixes

### 1. Spa lounger orientation, both variants (#330)

The villager's pose did not follow the furniture. Root cause: the pose site
used a predicate that pulled orientation SW into the NW arm.

The orientations that actually occur in play are **SE (0) and SW (1)**, not
NE/NW. That was established from a live capture of the running game, and it
contradicted four earlier rounds of fixes that had assumed 2 and 3 from the
visual description.

> **SUPERSEDED — this release shipped the wrong conclusion.** These notes
> originally stated: "Both observed orientations want `SleepNE`, and testing
> `orientation == 3` satisfies both", and that orientations 2 and 3 remained
> unobserved guesses.
>
> The owner's playtest of this very release disproved it. `orientation == 3`
> never matches a real lounger, so **both** placements took `SleepNE`, and the
> owner reported **one lounger correct and one wrong**: SE(0) correct, SW(1)
> broken. SW(1) wants `SleepNW`.
>
> The owner also confirmed a lounger only ever occupies **two** orientations,
> so the "2 and 3 unobserved" caveat described states that do not exist.
>
> **Current expected mapping**, and the rule the owner stated — *the villager
> faces the way the lounger faces, head and body*:
>
> | orientation | direction | head | strip |
> |---|---|---|---|
> | 0 (SE) | NE | NE | `SleepNE` |
> | 1 (SW) | NW | NW | `SleepNW` |
>
> Fixed after this release; see issue #330. The corrected rule is gated on the
> spa-lounger handle, because ordinary Lounge Chairs share the same reclined
> branch and were confirmed working here.

Stock is **not** the model here. Stock `CBehavior::RestingBody` dispatches
four ways on orientation parity and plays `SleepNW` at orientation 0, which is
the value the owner confirms is wrong on screen. An earlier claim that this
fix "copies the stock rule" was false and has been corrected in the source
comment rather than quietly dropped.

### 2. Exercise Bike drop never produced "doing high-intensity cycling" (#336)

Dropping a villager on the bike always produced "using the exercise bike".
The drop dispatch hardcoded the walk variant, so the run label was
unreachable. It now rolls between both.

### 3. Treadmill actions walked the villager to the Exercise Bike (#335)

The bike borrowed `TreadmillStd.png.fmap` and therefore declared the
Treadmill's content-map object `0x04`. `FindFurniture` resolves purely by
object, so the two machines were indistinguishable and every earlier fix had
to be a positional guard instead of a real separation.

**The Exercise Bike is now its own object, `0x99`.** Read out of the shipped
archive:

    ExerciseBikeStd.png.fmap    {0x0: 113, 0x99: 3}
    TreadmillStd.png.fmap       stock, still 0x04

For comparison, the same file in the shipped B187 bundle:

    ExerciseBikeStd.png.fmap    {0x0: 113, 0x04: 3}     <- the defect

Five separate consumers of the shared-object assumption had to be fixed, not
one: venue selection, the donor lookup inside `FindFurniture`, the exclusion
guard that decides whether a villager is already on other furniture, the
caption probe, and the autonomous candidate prerequisite. The exclusion guard
in particular still has to ask about the **donor's** object — passing the
bike's `0x99` there made it search for a bike under a villager standing on a
Treadmill and walk them off it, reintroducing this very bug by a new route.

### 4. Ping-Pong Table targeted for pool (#331)

Same defect shape: the table borrowed the Pool Table's fmap and declared
`0x36`. **The Ping-Pong Table is now object `0x9A`.**

    PingPongTableStd.png.fmap   {0x0: 250, 0x9a: 10}
    PoolTableStd.png.fmap       stock, still 0x36

### 5. Home Gym and Yoga act at the drop point (#337, #329)

Villagers walked elsewhere instead of acting where they were dropped. The
venue lookup kept the *nearest* placement rather than the one the villager was
dropped on. A drop-point preference now wins, scoped to the Home Gym and the
Yoga Equipment only, as requested.

### 6. Patio drinks prop position (#333)

Moved 7 further pixels right on the furniture item; the nudge constant is now
25.

### 7. Autonomous candidates are gated on their own item

Cloned candidate records inherit the donor's object prerequisite at record
offset `+0xC4`. That meant the bike's autonomous actions were offered only
when a **Treadmill** was placed, and ping-pong only when a Pool Table was —
the reported bug, surviving in the autonomous path after the drop path was
fixed.

Each clone now passes its own object explicitly. Confirmed against the game
binary: `CVillager::InitAI` really does gate the treadmill donors on `0x04`
and the pool donor on `0x36`, while the six clones that pass zero have donors
carrying no object gate at all. Resolved through InitAI's two-level switch
(`$LN205` byte map to a case number, then `$LN249`), and the decode is only
trusted because it reproduces those three independently known values before
reporting the six unknown ones.

## What was verified, and what that is worth

Each of these is an independent check with its own exit code, not an inference
from the build exiting 0:

| Check | Result |
|---|---|
| Matrix build | 32/32 variants, 32 linked OK, 0 errors |
| Both new objects, every variant | 32/32 — bike `0x99`, ping-pong `0x9A` |
| Donors kept their objects | treadmill `0x04`, pool `0x36` intact in all 32 |
| No other shipped map claims `0x99`/`0x9A` | every `.fmap` in the archive checked |
| Retarget preserved footprints | bike 3 cells, ping-pong 10 — matching B187 donors cell for cell |
| Gating consistency | one registration signature across 32; `.vf2beh` ships dormant everywhere |
| Regression baseline | 32 variants judged, 0 incomplete, 0 with losses |
| Export | 8226 of 8226 build files reproduced byte-for-byte on a clean install |
| Release gate | PASSED, variant identities authenticated, no features lost against 8 retained releases |
| Independent verifier | exit 0 with `--require-identities` |
| Variant identities | 32/32 both directions, 32 distinct hashes |
| Stale-input check | all 32 shipped executables trace to the current build, 0 to the archived pre-Ping-Pong build |
| Emitted C++ from merged `main` | 12/12 clone calls with resolved prerequisites, all fixes present |

The footprint check earned its place: a mutation that drops one bike cell
while leaving the object id correct passes the object-id checks and is caught
only by that one. Without it, a bike whose collision box had silently shrunk
by a third would have gated clean.

## What is NOT claimed

Everything above is **static** evidence that the mechanisms reached this
archive. None of it establishes that any behaviour is correct in play.

Issues #329, #330, #331, #333, #335, #336 and #337 stay **open**. They will be
closed on the owner's playtest of this patcher and not before — including the
two with artifact-level evidence, because object separation reaching the
archive is not the same as villagers behaving correctly on screen.

## Artifact identity

    VF2-B188-Release.zip
    sha256  d6fe36139b53ac6121b42a2e01229b1a08438bc4ea58061eb9f1cf484545a9ab
    bytes   144,540,741
    built from main at 8525d44
