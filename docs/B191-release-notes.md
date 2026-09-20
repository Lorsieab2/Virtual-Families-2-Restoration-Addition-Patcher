# VF2 B191 release notes

**The patcher bundle.** Prerelease for testing. Built from `main` at
`e09a33b` (PR #355), seeded from the B190 matrix.

B191 ships two owner-requested behaviour changes, both confirmed in play on
probe builds before this bundle was cut. Everything else is B190.

## 1. The spa receiving treatment now lasts as long as the giving one

Reported: the receiving villager got up while the giver was still working.

Both halves already computed the same `GetRandom(11) + 55`, so the plans
looked identical. They were not in the same unit: `PlanToWork` and
`PlanToWait` count ticks, while `PlanToPlayAnim` counts animation frames at
the speed it is handed. Handing the strip the leftover ticks is what ended
the receiving treatment early.

The strip length is now its own argument, and the treatment passes the
hammock's `GetRandom(180) + 180` — the one reclining sleep already confirmed
in play — rather than an invented conversion factor.

Decoded from the shipped `behavior_patches` executable at `.text+0B3C90`:
`6A 0B` / `8D 70 37` is `GetRandom(11)+55` (the giver's tick budget) and
`68 B4 00 00 00` / `05 B4 00 00 00` is `GetRandom(180)+180` (the strip),
both handed to the rest helper.

## 2. The manual hammock drop now rests for as long as the autonomous one

Requested, for the base hammock and the Invisible Hammock: "i like them
sleeping for long periods of time".

Both hammocks dispatch behaviour `0x24` on a drop, so its `CBehavior`
constructor entry is retargeted to a VF2 drop entry, exactly as `0x23`
already is for the autonomous route. **The settle is the native drop's own
table**, decoded from `Behavior.obj`: orientation 1 lies down
(`PlanToLieDown`, body 9), anything else waits in the chaise body `0x17`,
no head direction — the orientation the owner confirmed correct — and the
strip pairs with the body as the stock `RestingBody` dispatch pairs them
(`9 ↔ SleepNW`, `0x17 ↔ SleepNE`). Only the long `GetRandom(180)+180` sleep
is added.

A first probe shared the autonomous route's mapping instead (body 9 at both
orientations, head/strip split on `orientation == 3`). The owner reported a
wrong facing and a flip between lying down and sleeping. That mapping was
inherited from native `LieInHammock`, which uses body 9 + `SleepNW`
unconditionally — a native defect, not a reference — and is recorded as
superseded in the generator. The autonomous route now shares the corrected
table.

The drop keeps the native refusal branch verbatim (a full hammock still
refuses rather than stacking villagers) and releases no semaphore the drop
route never held.

Decoded from the shipped executable: the `0x24` entry resolves to the VF2
drop entry (carrying the `0E9h` label, the `5Bh` link and the refusal
constants), which calls a shared rest that compares orientation with 1,
pushes `0Ah`/`17h` for the two settle arms, selects between the two strip
literals with `cmovne`, and runs `GetRandom(180)+180`.

## What to check

- **Spa:** drop one adult on a spa lounger and another onto them. The
  receiver should stay lying down for the whole of the giver's treatment;
  the giver should not be left working on an empty lounger.
- **Hammock, both kinds:** drop a villager on each hammock. They should lie
  the way they did in B190 (orientation unchanged), close their eyes, and
  stay for a long sleep instead of getting up after a few seconds. Facing
  should not change when the eyes close. A full hammock should still refuse.
- Ordinary and mobile Lounge Chairs, and the spa pose itself, are unchanged
  from B190.

## Evidence

| Check | Result |
|---|---|
| Owner playtest (probes v16, v18) | both behaviours confirmed: "perfect. everything works as intended." |
| Spa pose / autonomous / orientation / hammock suites | 90 passed, 10 skipped (pose, autonomous, orientation, hammock drop) |
| Full regression suite | 1158 passed, 23 skipped, 8676 subtests; 3 failed, all pre-existing in test_verify_offline_bundle_zip.py against the branch's older B190 identities (pass on main) |
| Mutations caught | 29 spa (incl. the strip sized from leftover ticks again) + 12 hammock (incl. the inverted table, swapped strip pairing, body 9 at both orientations, `orientation == 3`) |
| Codex review rounds on #355 | 9 findings across 6 rounds on #355, each fixed or dispositioned in its thread |
| Matrix build | 32/32 linked, EXIT=0, 59 min, 0 executables inherited from B190 |
| Export | 8226 of 8226 Images/Assets files reproduced byte-for-byte; 7455 payload files |
| Repository gate, identities enforced | PASS — 32 variants authenticated, 7467 members, no features lost vs 11 retained releases |

## Artifact identity

    VF2-B191-Release.zip
    sha256  dac22c53d0180d3739213e45056cba815d8e15d29f3422b06bdc85ca1abbc853
    bytes   144,552,056
    built from main at e09a33b (PR #355)
    tree    0408ca46402a90c0b39f61f59f4f3b0afe17d494
