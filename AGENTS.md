# Rules for automated contributors

Read this before changing anything in this repository.

These rules exist because every one of them was written after a real failure
here — a feature that shipped dead, a fix that silently reverted someone
else's work, a green test suite over a broken build. They are not style
preferences. Breaking them ships regressions to a player.

The repository owner has the final say on every decision. Make the safest,
most narrowly scoped change that fixes the demonstrated problem. If it is not
broken, do not fix it.

---

## 1. Verify the shipped artifact, never the source

A source-level check proves nothing about what the player installs. Before
claiming a fix works, build it and confirm the change is present in the built
executable or object file. Decode the actual bytes; do not pattern-match a
shape.

**"The code is there" has been true three separate times on this project while
the feature was dead:**

- `patch_mobile_table_prop_draw` was written, reviewed, merged — and never
  called. The sprites shipped and nothing drew them.
- `verify_extracted_release_payload.py` was complete and correct, and nothing
  invoked it. The release gate printed `RELEASE GATE PASSED` with zero payload
  assertions executed.
- The decal hook installer had the same shape.

A function that exists and is never reached ships as a missing feature.

Before you finish, ask what your verification would print if the thing it
verifies were absent. If the answer is "the same thing", it is not evidence.

## 2. Prove your change did not remove anything

Run this before merging, every time:

```
git diff --stat origin/main...<your branch>
```

Look for **deletions in any file your change has no business touching**.

A clean merge-tree does **not** mean you preserved what is on `main`. A branch
cut before someone else's merge reverts their work with no conflict at all,
because git sees no competing edit — only an absence. This nearly shipped
here: a pull request that would have silently deleted an entire crash-warning
mechanism reported "no conflict".

`merge-tree` answers *will this apply cleanly*, not *will this preserve main*.

## 3. Every feature toggle must stay reachable

`data/vf2/build-matrix-toggles.json` declares the toggle matrix and
`work/build_matrix.ps1` iterates `$matrix.variants` with no hardcoded count.
If a change makes any toggle combination fail to build, or leaves a feature
inert while its flag is on, that is a shipped regression even if every test
passes.

**Feature flags default to `0` in a fresh build.** If you launch the game and
nothing crashes, you have proven only that the gated code never ran. Set the
flags by **walking the PE section table** — the offsets move between builds.
Three different offsets have already been observed for the same flag:
`0x19C400`, `0x1B0E00`, `0x1B1600`. Reusing a remembered offset writes into
the wrong section and tests nothing.

## 4. Two-way validate every fix

Revert your own change and confirm a test fails. If nothing fails, the fix is
unpinned and the next refactor will silently delete it.

**Assert that the revert actually modified the file before believing the
result.** A scripted edit that matches nothing reports success and is
indistinguishable from a passing check:

```python
assert text.count(old) == 1, "expected 1 match, found %d" % text.count(old)
```

This has already produced a false green here: a revert written through a shell
`python -c` had its escapes mangled, matched nothing, left the file unchanged —
and the suite reported all tests passing. That was read as "the fix is pinned".
It was reporting that unmodified code passes its own tests.

Validate new checks against known-bad input too. A check that cannot fail is
not a check.

## 5. One pull request per change; do not push directly to `main`

Several recent commits landed without a pull request number, and one pair is a
verbatim duplicate: `9966397` and `9dd7ef1` have identical diffstats and touch
the same two files. Re-applied work is how regressions get reintroduced.
(`1596800` and `4dc2dea` share a title but differ in content, so that pair is a
follow-up rather than a duplicate.)

Open a pull request, let review run, merge it once. A merged pull request is
not a finished one — the REST merge does not wait for review.

## 6. Exit code 0 is not proof

Measured failures on this project, each of which looked like success:

- `pytest` exited **0 with 2 failures**. Read the summary line, not the status.
- A batch wrapper returned **0 without running the compiler**. No object file
  was produced and the build was reported clean.
- `gh pr merge` succeeded while printing nothing, and separately exited 1 on a
  merge that had actually landed. Verify against the pull request object.
- A process launcher reported "exited in 0s, code 0" for a game that was
  running fine — a stale handle.
- `0xC0000135` was read as a crash; it is DLL-not-found.

Confirm the artifact exists. Read the actual line. Check the thing, not a
proxy for it.

## 7. Separate static evidence from runtime evidence

Report build and source evidence separately from runtime and player evidence,
and never claim a gameplay complaint is fixed without live verification.

"The descriptors are populated and the hook is unconditional" is a real
finding. It is not the same statement as "villagers no longer eat at an empty
table", and conflating them wastes the owner's time when they play the build
and find otherwise.

## 8. Coordinate before editing shared files

`work/patch_mobile_furniture_pack.py` is roughly 35,000 lines and several
contributors work this repository at once. Say what you are taking before you
edit it, and check whether someone else already holds it. Two agents in the
same function is pure conflict risk for no benefit.

Helpers do not cross emission blocks: a function emitted by one generator
function is not in scope from another, because they produce different `.cpp`
files. Check which generator function you are in before reusing a helper.

## 9. Build recipe

Run the build from PowerShell, driving the batch file directly:

```powershell
Set-Location C:\vf2w\vf2
$env:VF2_BUILD_OUT = "outputs\<name>"
$env:VF2_OUTPUT_EXE = "<name>.exe"
& cmd.exe /c "work\build_b119.bat"
```

Driving it through bash kills it silently between compile and link: the
compiler runs, no executable appears, and nothing is reported. A wrapper
around it has also returned exit 0 without running `cl` at all.

Run the test suite from the main clone at `C:\vf2w\vf2\work`, never from a
worktree — many tests copy build inputs that exist only in the clone, and in a
worktree they fail with `FileNotFoundError` in numbers that look like a real
regression. `test_generated_cpp_compiles.py` silently **skips** in a worktree,
and a skip is not a pass.

## 10. Known correctness rules in this codebase

- **Identify furniture by placement handle, never by point.** `info.point` is
  the walk-to anchor, not the furniture's position, and returns `-1` for
  anything a villager stands beside. Match `info.unknown0` against
  `record[+0x04]`. Reference implementation: `VF2CaptureTableProp`.
- **Bike/treadmill, ping-pong/pool and Home Gym/Yoga share object IDs**, so
  `info.object` alone cannot distinguish them.
- **`FindFurniture` and `LinkPeepToFurniture` do not answer the same
  question.** The latter additionally skips placements with no free peep slot,
  so a probe-then-link pair disagrees exactly when it matters.
- **`UnlinkPeepFromFurniture` does not exist.**
- **`PlanToGo` appends.** It ends in `AddPlan`, which scans for the first empty
  plan slot and stores there. A route set before invoking a donor behaviour is
  not overwritten — the donor's own route lands *after* it, so the villager
  reaches the venue and then walks away again.
- **A placed item changes *where* a behaviour happens, never *whether* it is
  available.** No ownership or `IsInWorld` gate on availability; stock donors
  stay globally available and unchanged when the added item is absent.

## 11. Documents

Correct stale claims in place and record the superseded version as wrong,
rather than deleting it. A dead end that is removed gets re-derived by the next
reader; one that is written down as dead does not.

Never put the owner's personal email addresses in any tracked file.
