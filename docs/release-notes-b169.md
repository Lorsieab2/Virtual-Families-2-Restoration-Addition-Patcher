# B169

Seventeen pull requests since B168: #15–#30 and #33.

B168 already contains #12 (toggle persistence), #13 (villager-details
Married status) and #14 — its release config was added by #14 — so none of
those are upgrade changes for an existing B168 user.

## Same-sex marriage

Marrying already worked in B168; the finalization hook predates it. What
was broken was everything the game asks *after* the wedding.

- **Spouses are now spouses everywhere.** `GetMatriarch` and `GetPatriarch`
  back-fill a couple's missing half regardless of gender, which covers all
  66 native call sites in one change rather than hooking nineteen functions
  individually (#22).
- **Unrelated adults are no longer treated as a couple.** `VF2MarriagePair`
  used to pair up any two qualifying resident adults, which also blocked
  Force Marriage Email for a player with no spouse at all (#16).
- **Private adult romantic time.** A same-sex couple, or an opposite-sex
  couple already at six children, takes the ordinary baby-making path and
  is simply labelled differently. Pregnancy is suppressed for both, and it
  holds even against the Force Successful Pregnancy upgrade (#33).
- **Same-sex partners split the sequence.** Behaviour 358 chooses which half
  a villager performs from the gender field alone, so a same-sex pair
  performed the identical half twice. The halves are now handed out by
  partner slot, so one spins and one produces the roses (#33).

An earlier form of the romantic drop (#28, #29) swapped behaviour 358 for
the native 357/356 pair and skipped refusals. That approach was reverted in
#33 and rebuilt as a label variation on 358, so what ships here is #33's
design, not #28/#29's.

## Toggles

- **Marriage Candidate Reroll works.** It used to reroll the candidate and
  then immediately close the proposal it had just rerolled (#23).

## Bathrooms

- **Each bathroom's curtain goes to its own decal slot.** A Bathroom 1
  renovation used to change Bathroom 2's curtain, and one slot turned out
  to be the kitchen's garbage sprite (#19, #21).
- **Bathroom 2 fixtures work with a remodel active.** The remodel rows were
  written into the native owned-items array, which native code reads to
  decide the room's state; they now have their own storage, with migration
  so existing saves self-heal (#27).
- The native Bathroom 2 renovation survives and gates the remodel rows, so
  the remodels cannot be bought without it (#24).
- The five Bathroom 1 rows are renamed "Bathroom 1 Remodel in *colour*"
  (#20).

## Correctness

- **Arbitrary memory corruption fixed.** A 5-byte hook over a 2-byte branch
  in `HandleDropOnVillager` clobbered the following two pushes, and the
  fall-through then executed its own jump displacement as code before
  writing through a garbage address. Reachable by dropping any two
  different-gender adults who were not the couple while the house was full,
  so it affected opposite-sex households on a stock Behavior Patches build
  (#25).

## Build system

- **The VF3 TVs are built from checked-in sources.** They had survived only
  inside each release: the matrix seeds every build from the previous one,
  and the generator keeps a target it finds already present when the source
  is gone. Every retained manifest from B164 through B168 records exactly
  that, so the real sources had been missing for weeks without anything
  noticing, and an unseeded build could not produce the TVs at all. The
  sprites are now checked in, stock donor fmaps resolve from the vanilla
  payload, and a test asserts every VF3 TV has a checked-in source (#30).
- A missing Bathroom 1 renovation asset hard-fails the build instead of
  silently shipping (#17).
- `work\build_playtest.ps1` produces a single playtest build in one command,
  and dead legacy same-sex marriage code is gone (#18).
- Stale manifest-shape assertions in the release parity test fixed (#15).
- Root causes for the Bathroom 2 fixture and same-sex private-time bugs
  documented (#26).

## Notes

- `CVillager::StartEmbrace` changes by exactly five bytes and
  `theMainScene::HandleDropOnVillager` by five. Every refusal in
  `StartEmbrace` — illness, hunger, age, pregnancy state, both random rolls
  — is base-game, as are its entry animation and its sound call.
- Known base-game behaviour, not introduced here: the kiss animation is
  played at `StartEmbrace+0x3A`, before any check runs, so it can be audible
  on a refusal. Where that sound is emitted was never established; every
  attempt to suppress it downstream failed, and one crashed the game with a
  1124-frame stack overflow, because the pending animation is what stops the
  refusal tail's behaviour-137 handoff from re-entering `StartEmbrace`.
