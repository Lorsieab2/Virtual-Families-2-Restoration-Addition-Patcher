# VF2 B189 release notes

**The patcher bundle.** Prerelease for testing.

B189 exists for **one** defect: the spa lounger orientation (#330).

## What the owner confirmed in B188

The owner playtested the published B188 patcher and reported **7 of 8 items
working in actual play**:

| Item | Verdict |
|---|---|
| Exercise Bike drop produces both labels | GOOD |
| Treadmill actions stay at the treadmill | GOOD |
| Exercise Bike autonomous selection | GOOD |
| Ping-Pong Table targeting | GOOD |
| Home Gym acts at the drop point | GOOD |
| Yoga acts at the drop point, centered | GOOD |
| Patio drinks prop position | GOOD |
| **Spa lounger orientation** | **one lounger correct, one wrong** |

Those seven are unchanged in B189. Six issues were closed on that playtest
rather than on any check in this repository.

## The one fix

### Spa lounger orientation (#330)

`VF2FurnitureFacesNorthWest` tested `orientation == 3`. The owner confirmed a
lounger only ever occupies **two** orientations, and a live capture of the
running game showed those are **0 and 1**. So `== 3` was never true for any
real lounger, and **both** placements took the northeast arm. Orientation 0
wants northeast, so it looked right by luck; orientation 1 wants northwest and
was the one reported wrong.

The rule, as the owner stated it — *the villager faces the way the lounger
faces, head and body*:

| orientation | direction | head | strip |
|---|---|---|---|
| 0 (SE) | NE | NE | `SleepNE` |
| 1 (SW) | **NW** | **NW** | **`SleepNW`** |

**The fix is gated, and the gating is the substance of it.** Review caught
that the reclined-pose branch

```cpp
if (info.orientation == 1 || VF2SpaLoungerHasHandle(info.unknown0))
```

admits ordinary and mobile Lounge Chairs at orientation 1, despite its own
comment claiming to be spa-scoped. Changing the shared predicate would have
regressed loungers the owner had already confirmed working. The spa rule now
lives in `VF2SpaLoungerFacesNorthWest`, which returns false unless the handle
is a spa lounger; the shared predicate is restored to `orientation == 3` for
chaises and the hammock.

A truth table over every combination that can reach that branch shows
**exactly one reachable row changes**:

| orientation | spa lounger? | B188 | B189 |
|---|---|---|---|
| 0 | no | flat pose | flat pose |
| 0 | yes | NE | NE |
| **1** | **no** | **NE** | **NE** (unchanged) |
| **1** | **yes** | **NE** | **NW** (the fix) |

Ordinary Lounge Chairs at orientation 1 are byte-identical in behaviour.

## Evidence, and its limits

Each of these is an independent check:

| Check | Result |
|---|---|
| Lounger and orientation suites | 115 passed |
| Mutations of the fix, each caught | 5 of 5 |
| Emitted C++ compiles | yes (a missing forward declaration caused C3861 and was fixed) |
| Codex review | 1 P1, 2 P2 — all addressed |
| CI on the merged commit | green |

The five mutations are the reason the tests are worth citing: reverting the
shared predicate, short-circuiting the spa handle gate, inverting that gate,
returning the wrong orientation, and reverting a pose site to the shared
predicate **all fail** the suite. An earlier version of the test passed the
gate mutation, which would have let the exact regression review had just
caught slip through invisibly.

## What is NOT claimed

**The lounger fix is not verifiable from this artifact, and that was measured
rather than assumed.**

It is a compare constant inside compiled code. Symbols do not survive linking;
`SleepNW` and `SleepNE` both appear in all 32 executables and appeared in B188
too; and `cmp reg,3` occurs 228 times and `cmp reg,1` 252 times in a 1.8MB
binary, so no count can be attributed to the lounger rule.

This differs from B188, whose bike (`0x99`) and ping-pong (`0x9a`) fixes were
content-map retargets readable straight out of the archive. Those remain
checkable here, and are checked — but they verify that B189 did not *regress*
B188, not that the lounger fix works.

**Issue #330 stays open until the owner confirms both loungers in play.**

## What to check

Drop a villager on each spa lounger. Both should lie **along** the lounger,
facing the way the furniture faces, head at the raised end.

Worth a glance too, since they share the same code branch: ordinary and mobile
Lounge Chairs should behave exactly as they did in B188.

## Artifact identity

    VF2-B189-Release.zip
    sha256  d644df48aabb200dc2166a228c18934d8b35712ea6850a41ac74b0d3465cc507
    bytes   144,562,636
    built from main at 3a598d2 (PR #348)

The build itself ran from the pre-merge branch commit `d0d1fd7`, which the
squash merge replaced with `3a598d2`. That is stated rather than glossed,
because a release should not cite a checkout nobody can obtain.

**The equivalence is compared, not asserted.** The build checkout is preserved
as the annotated tag `b189-build-checkout`, so both sides resolve:

```
git rev-parse b189-build-checkout^{tree}   ca7338d233fe0cf3044c0c11bfc8edf4a4729ff0
git rev-parse 3a598d2^{tree}               ca7338d233fe0cf3044c0c11bfc8edf4a4729ff0
```

The first resolves the **actual build checkout**, the second the merged
revision. A tag is a durable ref, so this does not depend on the pre-merge
branch continuing to exist.

This took three review rounds, and every earlier attempt failed the same way:
recording provenance that could not be checked. Citing `d0d1fd7` alone was
unresolvable after the squash merge. Citing the generator blob plus a claim
about the rest of the tree still required trust. Citing only `3a598d2^{tree}`
proved what the *merged* revision contains but not what the *build checkout*
contained. Each was verified against a working copy that still held the
squashed commit — checking from a vantage point no auditor occupies is what
made the earlier attempts look correct.

`3a598d2` is the revision to audit this artifact against.

All three gates passed on this exact file: the repository release gate with
`--require-identities` (32 variants, 7467 members, identities authenticated),
an artifact verifier (8 checks, 0 failed) and a comparator against the B188
bundle (nothing lost: 7467 entries, 153 fmaps, 6587 pngs, all 32 variants).
All 32 executables differ from B188, which rules out a seeded build inheriting
the previous release untouched -- a real failure mode here -- but cannot show
which fix is present.
