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

All three mirrored **together**, so the settle pose and the sleep strip cannot
disagree — the defect originally reported on the hammock.

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

## What is NOT claimed

**This fix is not verifiable from the artifact, and that was measured rather
than assumed.** It is a compare constant inside compiled code. No symbol
survives linking, and `SleepNE`/`SleepNW` appear in all 32 executables — they
appeared in B188 and B189 too. The fix changes *which orientation selects
which*, and no check on the archive can observe that.

Everything above establishes that B190 did not *regress* B189. None of it shows
a villager lying correctly on a lounger.

**Issue #330 stays open until the owner confirms it in play.**

## What to check

Drop a villager on **each** spa lounger. Both should lie **along** the lounger,
facing the way the furniture faces, head at the raised end.

Worth a glance too, since they share the same code branch: ordinary and mobile
**Lounge Chairs** should behave exactly as they did in B189.

## Artifact identity

    VF2-B190-Release.zip
    sha256  971d7da169ed8374b3a25b9cb769a16f069f90bfeeeb83d943cbc9cb84e7953f
    bytes   144,562,545
    built from main at 94bcf83 (PR #350)
    tree    c133f411076f7ad29321094ec710cb60ae9067ac
