# VF2 B190 release notes

**The patcher bundle.** Prerelease for testing.

B190 exists for **one** defect: the spa lounger orientation (#330), on its
**sixth** attempt.

## What the owner reported

The owner playtested the published B189 patcher, photographed the villager
**still lying across the lounger**, and diagnosed it directly:

> flip the villager orientation horizontally for the spa receiving actions

## Why five earlier rounds could not have worked

Every previous attempt argued about **which** orientation takes **which**
animation strip — northeast versus northwest — and B189 added a handle gate so
the spa rule could not reach ordinary chaises. All of that tunes a **selector**.

The receiving pose needs the **mirror** of whatever that selector picks. So
both placements were wrong *together*, and tuning the selector could only ever
swap which one looked wrong.

That also explains the observation that misled every round. On B188 the owner
reported *one lounger correct and one wrong*. That was **two stacked defects**:
the selector wrong for one placement, on top of the mirror wrong for both.
Fixing the selector in B189 made both consistently wrong instead of fixing
either.

## The fix

`NE(0)` and `NW(3)` are the horizontal mirror pair for both `EDirection` and
`EHeadDirection`, so the flip is taking the opposite arm of the same test.

| | B189 | B190 |
|---|---|---|
| head | `? NW : NE` | `? NE : NW` |
| body | `? Northwest : Northeast` | `? Northeast : Northwest` |
| strip | `? SleepNW : SleepNE` | `? SleepNE : SleepNW` |

> **SUPERSEDED BY THE OWNER'S B190 PLAYTEST.** This read: *"All three mirrored
> **together**, so the settle pose and the sleep strip cannot disagree — the
> defect originally reported on the hammock."*
>
> The owner playtested this very release and observed something no earlier
> round had isolated:
>
> > before they close their eyes, they have the wrong position. once they
> > close their eyes the position is correct.
>
> The settle pose and the sleep strip therefore index facing **differently**,
> and coupling them is not a safeguard — it is the bug. Every round up to and
> including B190 derived both phases from one test, deliberately, so the
> wrong phase could never be corrected without breaking the right one.
>
> The settle and the strip now take **opposite** arms. The table above
> describes the **strip**, which the owner confirmed correct; the settle takes
> the other arm. See PR #352.
>
> A maintainer who "restores" the coupling described here will reintroduce
> the defect, which is why the original wording is retained and marked rather
> than deleted.

## Scope — what was deliberately not touched

`VF2PlanSpaTreatment` only, which is the **receiving** pose. Traced rather than
assumed: it has exactly two callers, both receiving routes, and there are
exactly three `eBodyPositionChaise` pose sites in the generator.

| site | status |
|---|---|
| giving villager | untouched — plans `PlanToWork` only, no pose at all |
| two chaise relax poses | untouched — owner confirmed working |
| shared `VF2FurnitureFacesNorthWest` | still `orientation == 3`, unchanged since B187 |
| B189's handle gate | **still in force** — it was never the problem |

## Evidence, and its limits

| Check | Result |
|---|---|
| Lounger and orientation suites | 115 passed |
| Mutations caught | 3 of 3 |
| Codex review rounds | 4, **zero P1 findings** |
| Matrix build | 32/32, EXIT=0, zero errors |
| Executables rebuilt vs B189 | 32 of 32, 0 inherited |
| Export | 8226 of 8226 files reproduced byte-for-byte |
| Repository gate, identities enforced | PASS — 32 variants, 7467 members |
| Nothing lost vs B189 | 7467 entries, 153 fmaps, 6587 pngs |

The three mutations are why the tests are worth citing: un-mirroring the body
direction — **exactly the defect in the owner's screenshot** — un-mirroring the
head, and leaving the strip unmirrored so settle and sleep disagree, all fail
the suite.

> **THE THIRD MUTATION IS SUPERSEDED.** "Leaving the strip unmirrored so
> settle and sleep disagree" was treated here as a caught regression. After
> the owner's B190 playtest, settle and sleep are **supposed** to disagree —
> they index facing differently, and that disagreement is the fix in #352,
> not a defect. The first two mutations still stand. This one is recorded as
> wrong so nobody reinstates it as a guard against the current behaviour.

## What is NOT claimed

**Corrected claim.** This section originally said the fix was "not verifiable
from the artifact". That was **overstated**, and review was right to push back:
the absence of *symbols* does not make the change unobservable. The compare
constant and the branch that selects each animation are still present in the
shipped instruction stream and can be decoded from it.

What is accurately true is narrower: **no string, hash or file-level check can
observe this fix.** `SleepNE`/`SleepNW` appear in all 32 executables and
appeared in B188 and B189 too, so their presence proves nothing. The fix
changes *which orientation selects which*, which is a property of the
instructions, not of the strings.

The consequence matters and is stated plainly: **a build in which this mapping
was omitted or miscompiled would still satisfy every hash, rebuild and
string-presence gate reported above.** Those gates establish that B190 did not
regress B189; they do not establish that the fix reached the artifact.

**What a decode of the shipped executable has established so far.** The
`SleepNE`/`SleepNW` literals are referenced **18 times** in `.text` — 7 as
`push imm32` and 11 as `mov reg, imm32`. A scan for pushes alone finds 7 and is
the wrong denominator. Around those references the orientation compare and the
body-position constant decode cleanly, and the method reproduces the **stock**
`CBehavior::RestingBody` mapping at two independent sites — orientation 0 to
body 9 with `SleepNW`, orientation 1 to body `0x17` (chaise) with `SleepNE` —
which is known-good ground truth documented in the generator. A method that
could not reproduce the control would not be trusted for anything else.

**What it has NOT yet established.** `VF2PlanSpaTreatment` is `static` and is
inlined into its two callers, so it has no prologue to anchor on, and the
strip selection nearest the spa call sites compiles to a branchless
conditional move rather than a compare-and-jump. Four candidate blocks were
decoded and each turned out to be a stock or relax pose, not the spa mapping.
So the spa mapping specifically is **not yet confirmed present in the
artifact** — that is an open verification gap, stated here rather than papered
over, and it is tracked separately from the behavioural fix itself.

Everything above establishes that B190 did not *regress* B189. None of it shows
a villager lying correctly on a lounger.

**Issue #330 stays open until the owner confirms it in play.**

## What to check

> **SUPERSEDED — this section told the tester to expect the wrong thing.**
> It originally read: *"Both should lie **along** the lounger, facing the way
> the furniture faces, head at the raised end."*
>
> "Facing the way the furniture faces" is the **B189** rule, and B189 was
> disproved in play. B190 ships the **mirror** of it — the receiving villager
> deliberately takes the *opposite* arm of the lounger-facing predicate.
> A tester following the old sentence would **reject the intended pose as
> broken and accept the superseded one as correct**, on a defect that has
> already failed six rounds. That is why this is corrected here rather than
> quietly dropped.

Drop a villager on **each** spa lounger. Both should lie **along** the lounger,
head at the raised end — not sprawled *across* it, which is the defect.

The villager's facing is the **mirror** of the furniture's, not a match to it:

| lounger placement | expected villager facing | strip |
|---|---|---|
| SE (orientation 0) | **NW** | `SleepNW` |
| SW (orientation 1) | **NE** | `SleepNE` |

If a villager faces the *same* way as the lounger, that is B189's behaviour
and this release did not take effect.

Worth a glance too, since they share the same code branch: ordinary and mobile
**Lounge Chairs** should behave exactly as they did in B189 — those were
confirmed working and are deliberately untouched.

## Artifact identity

    VF2-B190-Release.zip
    sha256  971d7da169ed8374b3a25b9cb769a16f069f90bfeeeb83d943cbc9cb84e7953f
    bytes   144,562,545
    built from main at 94bcf83 (PR #350)
    tree    c133f411076f7ad29321094ec710cb60ae9067ac
