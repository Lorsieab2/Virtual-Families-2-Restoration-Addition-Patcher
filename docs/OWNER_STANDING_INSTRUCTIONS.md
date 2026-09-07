# Owner standing instructions

The repository owner's own words, recorded verbatim so no contributor has to
be told twice and nobody has to reconstruct them from chat history. **The owner
has the final say on every decision.** Where these conflict with anything else
in the repository, these win.

Read `AGENTS.md` alongside this: that file is the engineering rules, this file
is what the owner has asked for.

---

## Scope and restraint

> DON'T MAKE UP EXTRA DETAILS OR INCLUDE STUFF I DIDN'T EXPLICITLY SAY. DO NOT
> ASSUME ANY INTENTIONS, DESIRES OR ANYTHING!!!!!! DO NOT DO ANYTHING WITHOUT
> EXPLICIT PERMISSION!!! ONLY MAKE NARROWLY-SCOPED FIXES TO ACTUAL PROBLEMS AND
> DON'T INVENT FIXES FOR THINGS THAT AREN'T BROKEN OR THAT YOU THINK ARE BROKEN.

> MAKE THE SAFEST, MOST NARROWLY-SCOPED FIXES FOR ANY PROBLEMS. IF IT'S NOT
> BROKEN DON'T FIX IT. IF IT WORKS NEVER TOUCH IT AGAIN UNLESS I TELL YOU
> OTHERWISE!!

> BIG REMINDER: DO NOT CHANGE ANYTHING APART FROM WHATEVER BUGS/THINGS THE
> HUMAN HAS TOLD YOU TO CHANGE. DO NOT INVENT THINGS, FIX THINGS THAT AREN'T
> BROKEN, AND DO NOT MAKE UP PROBLEMS!!!!!!!

> ACTUALLY FIX PROBLEMS, DO NOT WORK AROUND THEM, SILENTLY OMIT THEM, ETC!!!

> ACTUALLY FIX WHAT'S BROKEN INSTEAD OF REVERTING IT AND FORGETTING ABOUT IT
> UNLESS IT'S LEGIT GONNA MAKE THE GAME CRASH OR SOMETHING!!! REVERT AND FIX!

> Don't give up unless it's gonna break the game, or it's literally impossible
> to implement.

## Work practice

> IMPLEMENT YOUR CHANGES IN A NEW BRANCH OFF OF UPDATED MAIN. MAKE SURE NO
> REGRESSIONS OR BUGS HAPPEN!!

> MAKE SURE ALL FIXES REACH MAIN!!!!!!! THE MOST CURRENT UP TO DATE MAIN!!!!!!

> make sure ALL CHANGES HAVE BEEN COMMITTED ON GITHUB AND HAVE PRS.

> coordinate with the other chats working on the same project before and after
> doing any work!!!

> coordinate with the other chat to merge what's safest, work out the conflicts
> for the others until they're safely mergeable.

> a merged PR is not a finished PR, and the REST merge does not wait for review.

> You may use IDA Pro, Ghidra or whatever tool you need.

> Use dlls to store stuff unless you absolutely have to use cave space since it
> is limited.

## Review findings

> CODEX RUNS AUTOMATICALLY ONCE PRS ARE MADE; PLEASE WAIT FOR THESE FIRST
> FINDINGS AND FIX THEM BEFORE RERUNNING CODEX REVIEW. only run @codex review
> manually once per PR/issue.

> you may rerun codex review when you've made new fixes or have doubts.

> if Codex gives a rate-limited message on a PR, independently review the PR
> yourself and fix it, then merge.

> Old findings on PRs may be superseded or outdated by newer updates. Pls keep
> in mind.

> only if you have no other work, look at old PRs/Issues that have not been
> addressed/fixed and fix the outstanding issues in order of severity.

## Evidence

> make sure your fixes actually land in the shipped build and don't claim the
> bugs are fixed when they're actually not!!!

> ALWAYS CHECK THE CRASH DUMPS AND LOGS.

> CHECK THE CRASH LOGS AND DUMPS WINDOWS MADE PLEASE!!!!!!!

Windows writes them to `%LOCALAPPDATA%\CrashDumps`, and the Application event
log (ID 1000) retains roughly two months, not fourteen days.

## Assets

> make sure all owner-provided sprites or files necessary for things to work
> are included within the patcher and don't rely on outside, owner-exclusive
> files!!!

Two different validators cover two different halves of this, and confusing
them gives a false sense of safety:

- `validate_mod_assets_present()` and `validate_runtime_payload_contract()`
  check that required assets are actually THERE. These are the ones that fail
  when an owner-provided sprite is missing.
- `validate_clean_package()` checks that nothing which should NOT ship has
  shipped: owner paths, private keys and token-shaped values in the bundled
  bytes. **It has no required-asset inventory**, so it passes unchanged when a
  required sprite is absent.

An earlier version of this file credited `validate_clean_package` with
enforcing asset inclusion. That was wrong, and wrong in the most dangerous
direction: it named a check that prints the same result whether or not the
asset is present.

## Documentation

> pls make sure to update: readme transparency docs

## Release gate

Before packaging a prerelease, **all** of the following must be true:

- All of the owner's desired changes and bug fixes acknowledged, worked on and
  completed
- All changes committed on GitHub, each with a pull request
- Working on the most recently updated `main`
- Nothing open and unchanged
- All bot comments acknowledged and fixed
- All pull requests merged with no further bot comments
- **No open pull requests**
- Every single finding on both old and new pull requests acknowledged and dealt
  with
- All GitHub issues acknowledged and fixed
- Every session working the project has independently met the requirements

> only cut a prerelease until all chats working on the same project have
> independently met all the requirements

> give me a green checkmark emoji once all of these are satisfied

Do not send the checkmark before then, and do not send it on a partial gate.

## What the release must be

> please put all new merges and stuff in a new prerelease on Github because
> that is what I'm going to playtest.

> CURRENT RELEASES MUST USE THE PREVIOUS RELEASE AS A BASE TO PREVENT
> REGRESSIONS. MAKE SURE EVERYTHING IS INCLUDED. ABSOLUTELY EVERY PIECE OF
> CONTENT FROM THE PREVIOUS RELEASES, WITHOUT THE BUGS!!!!!!!!

> REMINDER: I WOULD LIKE THE PRERELEASE AS THE PATCHER WITH ALL THE LATEST
> FIXES. NOT A GAME EXE!

The deliverable is the **patcher bundle**, not a pre-patched game folder.

Releases and ZIPs are never deleted — draft them instead, and move stale
outputs aside rather than removing them.

## Current task assignment

The owner assigns areas directly. At the time of writing:

> CODEX IS WORKING ON THE FOLLOWING. DO NOT WORK ON THEM:
> Spa lounger behaviors (both giving and receiving) should last approx. 1
> minute in real-life time. Behaviors and labels should be localized to the spa
> lounger only and not any other loungers. Exercise bike behaviors and labels
> should be localized to the exercise bike only. Home Gym does nothing on
> manual drop. desired behaviors should be localized to the home gym too. Check
> the other newly-altered furniture like the Yoga Equipment for the same stuff.
> WORK ON OTHER STUFF.

Check with the owner before assuming an assignment still stands.

## An open task recorded here so it is not lost

Stale matrix-count metadata. `data/vf2/build-matrix-toggles.json` is internally
inconsistent: `matrix_id` is `vf2-19-variant-toggle-matrix-v1` and `note` begins
"Stable 19-variant feature-toggle matrix", while the `variants` array contains
**32** entries. The array is authoritative, and the B181 release notes state
each of the 32 seeds was checked.

**This is a labelling bug only — confirm that before changing behaviour.**
`work/build_matrix.ps1` iterates `foreach ($config in $matrix.variants)` with
no hardcoded count, so it already builds all 32.

- Do **not** change the variants array; do not add or remove variants.
- Fix `matrix_id` and `note` in `data/vf2/build-matrix-toggles.json`.
- Fix the comment on `work/build_matrix.ps1` line 4 and
  `work/build_playtest.ps1` line 3.
- **Leave historical documents alone.** `docs/B164-release-notes.md`,
  `release-notes-b170/172/173/174/175.md` and
  `data/vf2/build-matrix-release-b168.json` / `-b176.json` say 19 about builds
  that genuinely had 19 variants. That is accurate history; changing it would
  falsify the record.
- Add a test that cannot go stale: assert the declared count matches
  `len(variants)`. Validate it against known-bad by changing the array length
  in a temporary copy and confirming the test fails.
- **Open question, do not guess:** six toggles imply 64 combinations and only 32
  are present. The note says `mobile_renovations` and `ai_generated_bathroom2`
  are always paired, which alone would halve 64 to 32 — determine whether that
  fully accounts for it. If it does, say so in the note. If it does not, report
  which combinations are missing rather than adding any.
