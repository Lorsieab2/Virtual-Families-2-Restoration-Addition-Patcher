# B169

First release since B168, which predates PR #12. Twenty-one pull requests
landed in between.

## Same-sex marriage

Same-sex marriage worked up to the altar in B168; most of this release is
about everything that happened afterwards.

- **Spouses are now spouses everywhere.** `GetMatriarch` and `GetPatriarch`
  back-fill a couple's missing half regardless of gender, which fixes all 66
  native call sites in one change rather than hooking nineteen functions
  individually (#22). The details screen shows "Married" for a same-sex
  adult (#13).
- **Marrying no longer crashes.** Finalization handles a same-sex pair
  (#28, #29).
- **Private adult romantic time.** A same-sex couple, or an opposite-sex
  couple already at six children, takes the ordinary baby-making path and
  is simply labelled differently. Pregnancy is suppressed for both — it
  holds even against the Force Successful Pregnancy upgrade (#33).
- **Same-sex partners split the sequence.** Behaviour 358 picks which half a
  villager performs from the gender field alone, so a same-sex pair used to
  perform the identical half twice. The halves are now handed out by
  partner slot (#33).
- `VF2MarriagePair` no longer pairs two unrelated adults as spouses (#16).

## Toggles

- **Both cheat toggles survive a relaunch.** Same-Sex Marriage and Marriage
  Candidate Reroll were stored in a custom PE section that the game never
  saves; they now live in the native owned-items array (#12).
- **Marriage Candidate Reroll works.** It used to reroll the candidate and
  then immediately close the proposal it had just rerolled (#23).

## Bathrooms

- **Each bathroom's curtain goes to its own decal slot.** A Bathroom 1
  renovation used to change Bathroom 2's curtain, and one slot was the
  kitchen's garbage sprite (#19, #21).
- **Bathroom 2 fixtures work with a remodel active.** The remodel rows were
  being written into the native owned-items array, which some native code
  reads to decide the room's state; they now have their own storage, with
  migration so existing saves self-heal (#27).
- The native Bathroom 2 renovation survives and gates the remodel rows, so
  the remodels cannot be bought without it (#24).
- The five Bathroom 1 rows are renamed "Bathroom 1 Remodel in *colour*"
  (#20).

## Correctness

- **Arbitrary memory corruption fixed.** A 5-byte hook over a 2-byte branch
  in `HandleDropOnVillager` clobbered the following two pushes, and the
  fall-through executed its own jump displacement as code, then wrote
  through a garbage address. Reachable by dropping any two different-gender
  adults who were not the couple while the house was full — so it affected
  opposite-sex households on a stock Behavior Patches build (#25).

## Build system

- **The VF3 TVs are built from checked-in sources.** They had survived only
  inside each release: the matrix seeds every build from the previous one,
  and the generator keeps a target it finds already present when the source
  is gone. Every retained manifest from B164 through B168 records exactly
  that, so the real sources had been missing for weeks without anything
  noticing, and an unseeded build could not produce the TVs at all. The
  sprites are now checked in, stock donor fmaps resolve from the vanilla
  payload, and a test asserts every VF3 TV has a checked-in source (#30).
- A missing Bathroom 1 renovation asset now hard-fails the build instead of
  silently shipping (#17).
- `work\build_playtest.ps1` produces a single playtest build in one command
  (#18).

## Notes

- `CVillager::StartEmbrace` changes by exactly five bytes, and
  `theMainScene::HandleDropOnVillager` by five. Every refusal in
  `StartEmbrace` — illness, hunger, age, pregnancy state, both random rolls
  — is base-game, as is its entry animation and its sound call.
- Known base-game behaviour, not introduced here: the kiss animation is
  played at `StartEmbrace+0x3A`, before any check runs, so it can be audible
  on a refusal. Where that sound is emitted was never established; every
  attempt to suppress it downstream failed, and one crashed the game with a
  1124-frame stack overflow, because the pending animation is what stops the
  refusal tail's behaviour-137 handoff from re-entering `StartEmbrace`.
