# VF2 B185 release notes

**The patcher bundle.** Prerelease for testing.

Marked prerelease for the usual reason and one specific one. Every automated
gate passes and the fix below is present in the generated C++ the build
compiled — but **nobody has yet watched a villager use the Home Gym repeatedly
and seen the captions vary.** No binary check separating this build from the
unfixed one has been found either -- the executables can be examined, but the
one signature tried appears equally in B184, which predates the fix -- so the
static evidence stops at the generator. Where a claim rests on that rather than live play, this
document says so rather than rounding it up.

## The Home Gym showed one action out of ten

Reported from live play: the gym "only shows one action out of their full
possibilities". That report was accurate, and the cause was not what it looked
like.

**All ten labels were already built and emitted.** The list in the README was
correct — lifting weights, doing crunches, cardio exercises, resistance
training, strength training, aerobic exercises, endurance exercises,
stretching, high-intensity interval training, weightlifting. What was broken
was the *selection*: whichever variation a villager rolled on their first visit
was the one they showed for the rest of the game.

**The label cache was blamed first and was innocent.** It is keyed to the
villager's behaviour id and serial and expires correctly. The stuck value came
from somewhere else: the villager's behaviour label persists in memory *after a
behaviour ends*, and the code deciding "is this villager already doing X" read
that leftover text. So every later session matched the old label and re-used it
instead of rolling again. The wrong first hypothesis is recorded here rather
than quietly dropped, because it is the one a reader would reach on their own.

**This was never only about the gym.** All 47 label groups were frozen the same
way — `nap_dream` has 30 labels, `meal_prep` and `sit_down_general` 24 each,
`career` 21, `coffee` 18. The gym was simply where it was noticed, because ten
variations make a stuck one obvious.

The fix asks the label cache — which knows the specific behaviour instance —
whether the label still belongs to the activity actually running. A villager
mid-workout keeps their caption instead of flickering; a new session rolls
again. The continuation behaviour that the old code existed to provide is
preserved deliberately; it was the wrong *question* being asked, not an
unnecessary one.

### Three further defects were found in the fix itself

Each was caught by review after the first fix looked complete, and each would
have produced the opposite regression — a caption changing *during* an action:

- The first version asked a global that names the last villager to enter a
  wrapped native behaviour, not the villager being asked about. With several
  patched villagers interleaving it named somebody else, so a villager's own
  live label was rejected.
- The second version was deliberately read-only, on the reasoning that a query
  should not mutate state. That reasoning was wrong: the praise allowance is
  measured against the cached record, so the *second* praise of the same action
  re-rolled the caption. Measured — read-only gave keep, then re-roll; the
  existing write-back gave keep, keep.
- Anchoring the resolver was not enough. A group's "keep the native label"
  outcome is stored as a sentinel, and the *applier's own* cache read was still
  going through the global — so that deliberate choice could flip to a mod
  caption mid-action.

## What this build is, and how it was checked

- Built from main at `01973e0`, seeded per variant from the **B184** matrix
  outputs. VF2 builds inherit assets from their seed, so seeding from anything
  older than the previous release silently drops what that release added while
  still reporting success. All 32 seed directories were confirmed present
  before the build.
- `outputs/VF2-B185-Release.zip`, sha256
  `493E8EE14928A25D01164724DF6606E2EFC1DB2F99E484BB9D5FDF0038932406`,
  144,514,567 bytes, 7467 entries.
- **Decoded twice, independently.** Two sessions wrote separate decoders from
  the bundle format rather than sharing one script, and published their figures
  before comparing. Both report 32 executables, 35 settings, five
  executable-overlay settings, `behavior_patches` default on, and no features
  lost against **all five** prior releases (B179, B180, B180-r2, B181, B184).
  The project's own release gate agrees.
- **The binaries were rebuilt from the fixed generator** -- which is a
  weaker claim than it first looks, and worth stating precisely. All 32
  executables differ from the B184 build they were seeded from. That rules
  out a real failure mode on this project, where a seeded build inherits the
  previous release's executable untouched; the check was validated in both
  directions first, a genuine cross-release pair differing 32/32 and a
  release compared against itself differing 0/32. But **a full relink changes
  every hash whether or not any given feature is in it**, so this shows the
  executables were rebuilt and nothing narrower.
- **The executables can be examined, but no binary check separating this
  build from the unfixed one has been found.** Function names do not survive
  linking, so the helpers cannot be looked up by name; the emitted code is
  still locatable by decoding, and the villager label field appears 475 times
  as a 4-byte immediate in the behaviour-patches build. That number is
  identical in B184, which predates the fix -- **a marker both builds share
  proves nothing.** What can be said is that the generator
  this build ran is byte-identical to the one on main and contains all four
  label fixes, and that the binaries were rebuilt from it. The last link --
  from that code to what a player actually sees -- is closed only by playing
  the game.
- Zero Windows crash dumps for Virtual Families 2 since the relink, measured
  by timestamp rather than by eye. Absence of dumps is not proof of a fix.

### One number that reads stronger than it is

The two spa lounger maps both report 33 drop cells. **That is one measurement
reported twice, not two agreeing measurements** — both targets resolve through
the manifest to the same payload file, so "the two loungers agree" is true by
construction and could never fail. The release gate's own output says the same
thing: the spa loungers share a digest. Stated here because a reader counting
independent confirmations would otherwise count one too many.

### A claim these notes used to make, and why it was wrong

An earlier draft of this file, and of the README, said the fix was "confirmed
present in the shipped executables". **That was wrong**, and it is recorded
here rather than quietly removed, because the wrong version supports a
conclusion that does not follow and a reader seeing only the corrected text
would not know which claim had been retracted. Whole-executable hash changes
show a relink, not a feature. A byte-level signature was then tried as a
substitute and also failed to discriminate, for the reason above.

## What still needs a person

- **Watch a villager use the Home Gym several times and count how many
  DIFFERENT captions appear.** Two distinct captions from one villager settles
  it: before the fix a villager showed exactly one for the rest of the game, so
  a second cannot happen by chance.

  **A repeat is not a symptom.** Selection is a uniform
  `GetRandom(count)` with no exclusion of the previous pick, so with ten
  labels a given visit repeats the last one about one time in ten, and roughly
  a third of correct five-visit playtests will contain at least one repeat.
  Reporting "it showed the same one twice" would condemn a working build.
- **The caption must stay stable WITHIN one visit.** That is the opposite
  defect, and three separate versions of this fix produced it before it was
  caught — a villager mid-workout whose caption flickers is a regression, not
  variety.
- The other label groups — napping, meals, sitting, careers, coffee — were
  frozen by the same defect and should now vary as well.
- Praise a villager twice during the same action; the caption should survive
  both.
