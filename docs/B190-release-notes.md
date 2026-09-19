# VF2 B190 release notes

**The patcher bundle.** Prerelease for testing. **Updated in place** — this
release was first published from `94bcf83` (PR #350) and has been rebuilt from
`d4215ca` with PRs #352 and #353; the artifact identity at the bottom names
the bundle that is actually attached.

B190 exists for **one** defect: the spa lounger pose (#330). The first
published build was the sixth attempt and did not fix it. The rebuild ships
the twenty-first, which the owner confirmed in play.

## What actually fixed it (PR #353)

The stock game's own chaise dispatch, decoded from the shipped binary at
`.text+0x37444`:

    orientation == 1 -> body 0x17 (eBodyPositionChaise)         + SleepNE
    otherwise        -> body 9    (eBodyPositionRestingHammock) + SleepNW

**The body position is orientation-dependent.** Every earlier round — all six
published attempts and the fourteen probe builds after them — hardcoded body
`0x17` for **both** orientations and then varied the direction, the head or
the sleep strip. `0x17` is the orientation-1 sprite; on an orientation-0
lounger it lies *across* the furniture whatever direction is supplied. A
direction argument cannot fix a wrong body sprite, which is why "one lounger
right, one wrong" survived every permutation of the other three arguments.

The spa loungers now use one body table, `VF2PlanSpaLoungerPose`, at every
route that puts a villager on one (both chaise relax sites and the spa
treatment), with the head selected from the same predicate through the
3-argument `PlanToWait` — the hammock's shape. The spa treatment settles
through that table and only then plays the sleep strip; the relax rolls
(reading, studying, sitting) hold the pose awake for their full duration, as
the ordinary chaise does.

Everything below the **History** heading describes models that were published
or proposed and are now known to be wrong. They are kept, marked, because
each one was re-derived from scratch at least once when its predecessor was
deleted.

## Also in this rebuild

| change | PR |
|---|---|
| Walk-target nudges on the spa loungers, per orientation: head-at-upper-right placement 4px left; head-at-upper-left placement net 2px left. Both from the owner's screenshots of the confirmed pose. | #353 |
| The drop route uses the placement the engine linked, whole — review caught two revisions that patched it from the slot under the villager and left a hybrid record. | #353 |
| Autonomous spa treatment is offered only while a spa lounger (visible or invisible) is in the house. | #353 |
| Home Gym and Yoga Mat autonomous workouts gated on their object being placed. | #352 |

## What to check

Drop a villager on **each** spa lounger, and let one pick the spa on its own.

**Pass:** the villager lies **along** the lounger with the head at the raised
end, on both placements, and the pose does **not** change when the eyes
close. A villager who picks "Reading a book" or "Studying on the lounger" on
a spa lounger stays awake for it.

**Fail:** lying *across* the lounger on either placement; the pose flipping
when the eyes close; a reader falling asleep after ten ticks.

Ordinary and mobile **Lounge Chairs** should behave exactly as they did in
B189 — their branches are byte-identical to what shipped.

## Evidence

| Check | Result |
|---|---|
| Owner playtest of the pose | confirmed on a probe build of this fix (PR #353 round 21) |
| **Decoded from the shipped B190 executable** | the pose is present and correct — see below |
| Spa pose, autonomous and orientation suites | 79 passed, 10 skipped (pose 20, autonomous, orientation) |
| Full regression suite | 1142 passed, 31 skipped, 8577 subtests, 0 failed (13:34) |
| Mutations caught | 23 of 23 (body table, strip, call shape, each relax site, the hybrid, awake rolls sleeping, naps eyes-open, the drop link landing on an ordinary chaise, three wrong nudge splits) |
| Codex review rounds on #353 | 9 rounds on #353, 17 findings, each fixed and answered in its thread; a tenth request drew no response in 40 minutes |
| Matrix build | 32/32 linked, EXIT=0, 54 min, 0 executables inherited from B189 |
| Export | 8226 of 8226 Images/Assets files reproduced byte-for-byte; 7455 payload files |
| Repository gate, identities enforced | PASS — 32 variants authenticated, 7467 members, no features lost vs 10 retained releases |

The pose fix is a property of the emitted instruction stream, not of any
string or file, so the identity gates above cannot see it. B190 therefore
does not rest on them: the pose was decoded **out of the shipped
`behavior_patches` executable in this bundle**, at `.text+0B3FF0`.

`VF2PlanSpaLoungerRest` with `VF2PlanSpaLoungerPose` inlined into it:

    004B4000  0F 4C DD            cmovl  ebx, ebp        ; settle = max(settle, 1)
    004B4003  8B 7C 24 14         mov    edi, [esp+14h]  ; orientation
    004B4007  B9 17 00 00 00      mov    ecx, 17h        ; eBodyPositionChaise
    004B400C  8D 47 FF            lea    eax, [edi-1]
    004B400F  F7 D8               neg    eax
    004B4011  1B C0               sbb    eax, eax
    004B4013  83 E0 03            and    eax, 3          ; head = (orientation==1) ? 0 : 3
    004B4016  83 FF 01            cmp    edi, 1
    004B4019  50                  push   eax             ; arg3  head
    004B401A  B8 09 00 00 00      mov    eax, 9          ; eBodyPositionRestingHammock
    004B401F  0F 44 C1            cmove  eax, ecx        ; body = (orientation==1) ? 17h : 9
    004B4022  8B 4C 24 14         mov    ecx, [esp+14h]  ; this = plans
    004B4026  50                  push   eax             ; arg2  body
    004B4027  53                  push   ebx             ; arg1  settle
    004B4028  E8 B3 93 01 00      call   PlanToWait      ; the THREE-argument overload
    ...
    004B4042  B9 34 4A 53 00      mov    ecx, offset "SleepNW"
    004B4047  83 FF 01            cmp    edi, 1
    004B404A  6A 00               push   0               ; loop = false
    004B404C  B8 2C 4A 53 00      mov    eax, offset "SleepNE"
    004B4051  0F 45 C1            cmovne eax, ecx        ; strip = (orientation==1) ? NE : NW
    004B4059  55                  push   ebp             ; the remainder of the stay
    004B405A  E8 91 89 01 00      call   PlanToPlayAnim

Read off the instructions, both arms:

| orientation | body | head | strip |
|---|---|---|---|
| `1` | `17h` eBodyPositionChaise | `0` NE | `SleepNE` |
| anything else | `09h` eBodyPositionRestingHammock | `3` NW | `SleepNW` |

That is the stock chaise table, and it is the fix. The compare is against
`1`, the two body constants are both materialised and selected by that
compare, and the call is the three-argument `PlanToWait`. Immediately
after, at `004B4070`, the spa treatment computes `GetRandom(0Bh) + 37h`
(55–65 ticks), passes `info+04`, calls this function, and then plays sound
`101h`, adds 2 dirtiness and `GetRandom(5)+7` energy.

A build that omitted or miscompiled the body table could not produce these
bytes, so this is the artifact-level evidence the earlier release notes
said was missing. The same check runs in CI against the compiled object:
`TheCompiledArtifact` in `work/test_spa_lounger_pose.py` executes the
compiled helpers per orientation and reads the arguments they hand over.

What is still **not** claimed: nobody has played this exact bundle. The
owner confirmed the pose on a probe build of the same fix, and the shipped
bytes above are that fix; the playtest of this artifact is the remaining
step.

## Artifact identity

    VF2-B190-Release.zip
    sha256  6456dc8eeddcf52a6d06eb2578f6a2bfe5d61978cad57ac91c481e27362b6189
    bytes   144,548,873
    built from main at d4215ca (PR #353)
    tree    e82df5255f372c9555e19dc2309fedf63a3502d3

> **Superseded identity** — the bundle first attached to this release:
>
>     sha256  971d7da169ed8374b3a25b9cb769a16f069f90bfeeeb83d943cbc9cb84e7953f
>     bytes   144,562,545
>     built from main at 94bcf83 (PR #350)
>     tree    c133f411076f7ad29321094ec710cb60ae9067ac
>
> That build carried the mirror model below and failed the owner's playtest.

---

## History — superseded models, kept as written

> **EVERYTHING FROM HERE DOWN IS SUPERSEDED** by the body-table fix above.
> Each block was the published or proposed explanation at the time and was
> disproved in play. The common error in all of them: body `0x17` on both
> orientations.

### What the owner reported

The owner playtested the published B189 patcher, photographed the villager
**still lying across the lounger**, and diagnosed it directly:

> flip the villager orientation horizontally for the spa receiving actions

### Why five earlier rounds could not have worked

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

### The fix

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

### Scope — what was deliberately not touched

`VF2PlanSpaTreatment` only, which is the **receiving** pose. Traced rather than
assumed: it has exactly two callers, both receiving routes, and there are
exactly three `eBodyPositionChaise` pose sites in the generator.

| site | status |
|---|---|
| giving villager | untouched — plans `PlanToWork` only, no pose at all |
| two chaise relax poses | untouched — owner confirmed working |
| shared `VF2FurnitureFacesNorthWest` | still `orientation == 3`, unchanged since B187 |
| B189's handle gate | **still in force** — it was never the problem |

### Evidence, and its limits

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

### What is NOT claimed

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

### What to check

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

> **SUPERSEDED — and this was my own replacement table, written to fix the
> previous error.** It paired one facing with one strip per row:
>
> > | lounger placement | expected villager facing | strip |
> > |---|---|---|
> > | SE (orientation 0) | **NW** | `SleepNW` |
> > | SW (orientation 1) | **NE** | `SleepNE` |
>
> That is still the **coupled** rule — one facing per placement, matching its
> strip. The owner's B190 playtest disproved exactly that: they confirmed the
> **strip** correct while the **settle** was wrong. A tester using the table
> above would reject the corrected settle and accept the known-bad coupled
> pose.

> **WHICH BUILD THESE APPLY TO — read this first.** These criteria describe
> the **post-#352** patcher, *not* the artifact whose sha256 was originally
> listed under **Artifact identity** below. That earlier zip was built from
> `94bcf83`, where the settle and the sleep strip still take the **same** arm.
> Its open-eye settle is the pose the owner photographed as wrong, so it
> **cannot** pass the settle criterion below — it is the build that failed it.
>
> The opposite-arm behaviour arrives with PR #352. Check these criteria only
> against a bundle whose Artifact identity names a commit that includes #352;
> the identity block below is updated when that bundle is built.

**There are TWO phases and they are expected to look different.** That is the
whole fix; it is not a glitch.

| phase | when | what to expect |
|---|---|---|
| **settle** | eyes **open**, just lay down | lies **along** the lounger, head at the raised end |
| **sleep** | eyes **closed** | unchanged from B190 — the owner already confirmed this phase correct |

The owner's own description of the bug, which is the acceptance criterion:

> before they close their eyes, they have the wrong position. once they close
> their eyes the position is correct.

**Pass:** both phases look right — the settle no longer sprawls the villager
*across* the lounger, and the eyes-closed pose still looks as it did.

**Fail:** the villager lies across the lounger before the eyes close (the
settle is still wrong), **or** the eyes-closed pose changed (a regression in
the phase that was already correct).

Do **not** judge this by whether the settle facing matches the sleep strip.
Under this fix they deliberately differ.

Worth a glance too, since they share the same code branch: ordinary and mobile
**Lounge Chairs** should behave exactly as they did in B189 — those were
confirmed working and are deliberately untouched.

### Artifact identity

    VF2-B190-Release.zip
    sha256  971d7da169ed8374b3a25b9cb769a16f069f90bfeeeb83d943cbc9cb84e7953f
    bytes   144,562,545
    built from main at 94bcf83 (PR #350)
    tree    c133f411076f7ad29321094ec710cb60ae9067ac
