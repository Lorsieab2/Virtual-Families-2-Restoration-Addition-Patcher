# VF2 B186 release notes

**The patcher bundle.** Prerelease for testing.

Marked prerelease for the usual reason: every automated gate passes and each
fix below is present in the generated C++ the build compiled, but **nobody has
yet watched these behaviours in live play**. Where a claim rests on static
evidence rather than on a villager observed doing the thing, this document says
so instead of rounding it up.

A note on what B186 *was*. The archive previously published under that tag was
the B185 archive renamed — its interior was entirely B185, down to
`Apply_B185_Patcher.bat` and a `VF2-B185-Release` folder inside a
`VF2-B186-Release.zip`. That is recorded as issue #299. This build replaces it
with a real one, cut from source and seeded from the 32 B185 matrix outputs so
nothing from the previous release is lost.

## Villagers stopped preparing drinks and picnics the moment they reached the kitchen

Reported from live play: "the villagers change behavior as soon as they reach
the kitchen to get the drinks or prepare a picnic", and "they don't finish
their actions properly".

The report was accurate and the timing in it was the clue that mattered — the
state was lost *on arrival*, not at a random point.

**The tracker identified the villager by their action-label text.**
`VF2VillagerStillPreparing` compared the string at `villager + 0x1BBA8` against
the expected caption, and the two `*PreparationActive` functions cleared the
preparer the moment that comparison failed.

**The engine blanks that field mid-plan.** `CVillagerPlans::ForgetPlans`
`strncpy`s a zero-length string over it, and
`VF2StartAutonomousPreparingDrinks` calls `ForgetPlans` **on itself**
immediately before running the preparation. So the tracker was cleared while
the plan was still in progress, the preparer globals went null, and the prop
never activated.

**Restoring the text would not have worked.** The label is not a field the
patch owns. It is written from five modules — 401 sites in `Behavior` alone,
plus `Villager`, `theMainScene`, `VillagerPlans`, and `CVillagerAI::Update`,
which runs every frame. A tracker keyed on that text cannot survive a single AI
update, so this needed a different key rather than a repair.

**The fix uses the field the engine itself uses for this question.** The
tracker now keys on the behaviour serial at `+0x1BBA4`, beside the villager
pointer it already stored, with the behaviour id at `+0x1BBA0` as a second
check. That field was verified rather than assumed: `CVillager`'s constructor
zeroes it, `CVillager::NewBehavior` increments it, nothing else in any
disassembled module writes it, and the base game's own `CFurnitureManager`
reads it after `GetVillager` to ask the same "is this still the same activity"
question.

A praise re-rolls the label and bumps the serial by exactly one while the
activity continues, so a bare equality test would have dropped the preparer on
praise — the same bug through a different door. That case is handled
explicitly, and accepting a praise adopts it as the new baseline so a *second*
praise does not then fail.

**Present in the compiled build, and decoded rather than inferred.** Counting
how often a field offset appears as an immediate proves very little on its own,
since these offsets occur hundreds of times across the engine. Decoding the
instruction stream instead, `mov r32,[r32+0x1BBA4]` -- a real read of the
behaviour serial -- appears at three sites in the build that predates this fix
and at five in this one:

```
pre-fix:  0046673B  00467D6E  004BA421
this one: 0046673B  00467D6E  004B5C12  004B5DBD  004BAA41
```

The two added sites are the fix, inlined. `/O2` inlines the tracker into its
two callers -- one for drinks, one for picnics -- so there is no standalone
symbol to locate, and both copies decode to the source:

```
mov esi,[eax+0x1BBA0]      ; behaviorId
mov ecx,[eax+0x1BBA4]      ; behaviorSerial
mov ebx,[eax+0x6B48]       ; praisedBehaviorId
mov edx,[eax+0x6B4C]       ; praiseCount
cmp esi,[0x70CD9C]         ; behaviorId != recordedBehavior -> reject
mov eax,[0x70CD98]
cmp ecx,eax                ; serial == *recordedSerial -> accept
inc eax
cmp ecx,eax                ; serial == *recordedSerial + 1
cmp ebx,esi                ; praisedBehaviorId == behaviorId
cmp edx,[0x70CDA0]         ; praiseCount != *recordedPraise
mov [0x70CD98],ecx         ; *recordedSerial = behaviorSerial
```

That last store is the praise writeback, which is the part most easily lost and
the part that makes a second praise work. Label-text references are unchanged
at 473, so the engine's own use of `+0x1BBA8` was not disturbed.

A count of serial reads alone would still not settle it: other inlined paths in
this translation unit read `+0x1BBA4` too, so five could in principle be five of
something else while the old tracker survived. What identifies these two as the
PREPARER tracker is the globals they touch. Each copy reaches a disjoint
six-global set, one per preparer:

```
drinks copy: 70CD79 70CD80 70CD94 70CD98 70CD9C 70CDA0
picnic copy: 70CD78 70CD7C 70CD84 70CD88 70CD8C 70CD90
```

Those sets match the source field-for-field -- preparer pointer, serial,
behaviour id, praise count -- and are confirmed as the preparer globals by
their write sites elsewhere in the image:

```
call 0x468A20              ; GameTime.Seconds()
add  eax,0xF0              ; + 240
mov  [0x70CD80],eax        ; the drinks prop deadline
...
mov  [0x70CD84],0          ; the picnic preparer, cleared
```

`0xF0` is 240, the prop lifetime this code sets. Neither copy reads `+0x1BBA8`
at all, so the text comparison is gone from this path rather than merely
joined by a serial read.

A note on the numbers: an earlier draft said seven sites rising to twelve. That
count came from a loose byte-pattern match that caught extra encodings. The
figures above come from decoding ModRM properly and are the ones to trust.

**Not yet confirmed in play.** None of the above shows a villager finishing a
drink. It shows the fix compiled into the shipped executable. Whether the
behaviour is right is what the playtest is for.

## A stock pool table could be captioned "Playing ping-pong"

Found by auditing the equipment labels, after a request to double-check the
ping-pong table "just in case". It was the only one of the five audited items
that was actually broken.

The ping-pong table and the stock pool table both answer EObject `0x36`, and
`VF2RandomPooltableLabel` is bound to the **stock** `PlayingPooltable`
behaviour — so no venue is forced and the engine picks the destination. The
wrapper decided which table it was from a nearest-match probe taken from the
villager's feet *before* the plan ran. That answers "which table is nearest
right now", which is not "which table will the route pick".

With both tables placed, a villager standing nearer the ping-pong table but
routed to the pool table was captioned **"Playing ping-pong" on a stock pool
table**. The mirror case silently kept "Playing pool" on the modded one.

This is the same defect already fixed for the exercise bike, which shares
EObject `0x04` with the stock treadmill exactly as these two tables share
`0x36`. The machinery was already built and already running on this path —
`PlayingPooltable`'s two object `PlanToGo` call sites are retargeted to the
interceptor, so the engine's own choice was being recorded and simply never
read. The wrapper now reads it, and falls back to the probe only when nothing
was recorded, which leaves a stock table's stock caption alone rather than
guessing.

**A correction to the record.** Commit `efcd1eb` claimed "Same stale-probe fix
applied to ping-pong vs pool table." That was not true of the code — the
function contained no reference to the routed-item machinery. The existing test
pinned probe-*before*-native ordering, and ordering was never what was wrong,
so it stayed green over the defect. The property itself is now pinned.

**Decoded in the shipped executable.** In the build that predates this fix, the
wrapper consulted nothing but the stale probe:

```
call 0x4BA700          ; the native behaviour
test al,al
je   done
test bl,bl             ; bl is the pre-probe, and nothing else is consulted
je   done
```

In this build it asks the interceptor first, and falls back to the probe only
when nothing was recorded:

```
cmp  byte [0x70ECFD],0      ; gVF2RoutedItemValid -- was a route recorded?
je   use_probe
cmp  dword [0x70FD3C],esi   ; ...and does it belong to THIS villager?
jne  reject
cmp  dword [0x70FD38],0x32E ; ...and was it the ping-pong table?
jne  reject
mov  bl,1                   ; onPingPong = true
```

The villager-ownership check is the part that matters beyond the headline: the
interceptor runs during plan construction while the wrapper reads after the
behaviour returns, so an unowned global could otherwise hand one villager
another villager's route.

Counting `push 0x32E` would have shown two sites in BOTH builds and proved
nothing -- the fix passes the id to a compare, not a push. Another reason the
immediate-census approach had to go.

## The other four audited items were correct as written

Reported here because "we checked and found nothing" is worth recording:

| item | finding |
|---|---|
| Home Gym | Correct. The single-label bug is genuinely fixed on `main` by `efcd1eb`; the varying applier re-rolls per visit and deliberately does not read the per-villager cache. |
| Exercise bike | Correct. Resolves by item id before the behaviour runs, and the stock-wrapper path already prefers the routed machine. |
| Treadmill | Correct. A stock treadmill cannot receive a bike caption; both wrappers return early unless the route chose the bike. |
| Yoga equipment | Correct. It has one label, `"Doing yoga"`, and that is intended — it is not an instance of the single-label bug. |

One note on the yoga item, stated plainly because it could be mistaken for a
defect: a B185-era report described kids stuck on "Doing endurance exercises",
which is a **home gym** string, not a yoga one. The yoga item has only ever had
a single label defined. If more variations are wanted there, that is a feature
request rather than a bug, and nothing was changed on that basis.

## Every patch now ships on by default

Per the standing instruction that builds and the patcher alike default every
patch on, 37 of the 38 settings in the patcher's table now default to enabled.

**One documented exception.** `invisible_furniture_transparent_graphics` stays
off, and not as an opinion about the feature. The two invisible-furniture
settings are sequential, and their own descriptions say so — "Enable this first
so you can place them in-game", then "Once you have placed them, enable this to
make them fully invisible". Defaulting the swap on would make the furniture
invisible before it could be placed, which loses the feature more thoroughly
than one unticked box does. The visible-graphics half, the one needed to use
the feature at all, now defaults on.

**The all-enabled playtest is now actually all-enabled.** `No AI Icons` was
still being forced off for the final playtest profile, from a B158-era
packaging rule that predates the current instruction — so an "all-enabled"
artifact shipped with it disabled regardless of the table. That override is
removed. It is an optional visual replacement for the late Special Upgrade
icons, so forcing it off protected nothing.

Several user-facing descriptions contradicted the new defaults — `Store Scroll
Bar` read "Default off." while shipping on — and are corrected. Historical
changelog entries describing what *past* releases did are deliberately left
alone; rewriting those would make the log lie about the past.

## Automated tests now run on every push

There was no CI. Every regression had to be caught by someone running pytest
locally, or by a playtest reaching the owner.

The portable suite — 212 tests and 91 subtests, about 35 seconds — now runs on
GitHub Actions for every push and pull request. Subtests are reported
**individually** rather than collapsed into one result per method: the JUnit
report carries 303 entries instead of 212, so a single failing subtest is
visible in the run summary and annotated on the line in a pull request.

(An earlier draft of these notes said 209 tests and 299 entries. That census was
measured before the three `EveryPatchDefaultsOn` tests landed and is
superseded; the figures above are the current measured output.)

The larger `work/` suite is deliberately not run there. Those tests read build
inputs that are gitignored, so on a runner they would either fail spuriously or
pass while checking a fraction of their assertions — and a green badge that
means the latter is worse than no badge. They remain a local gate.

**CI earned its keep on the first run.** It found three real failures that were
invisible on every machine this suite had been run on: on a GitHub Windows
runner the account name exceeds eight characters, so `TemporaryDirectory`
returns the 8.3 short path while the patcher resolves to the long one, and
three icon tests compared the same file under two spellings. Fixed in the
tests; no production code changed.

## Save paths are now pinned against the base game

A test compares the patched executable's decoded save-path strings against the
verified vanilla image and fails if any are added or dropped. This exists
because a save path that differs from the stock game sends saves somewhere the
base game will not look, and that surfaces as lost progress rather than as a
crash.

Measured across all 160 built executables from B178 through B185: every variant
carries exactly the stock set, and the game's only save-path string is `\LDW`.
Verified against known-bads — adding `C:\VF2Saves`, adding
`Documents\LDW\Virtual Families 2`, swapping `\LDW` for `\XYZ`, and a UTF-16
`My Games\VF2` are all detected.

## The 2026-09-07 crash dumps: what is and is not established

Three Windows crash dumps exist from a playtest build, written within 13
seconds of each other, two at the identical fault address. They are recorded as
issue #302, which stays **open**.

Decoded properly, all three are DEP **execute** violations — the process jumped
into `.data` and tried to execute it. The earlier analysis of these dumps had
the exception-record offsets wrong and concluded they were bad pointer reads;
that is corrected on the issue. The faulting instruction is a `call` through a
register that held a *villager pointer* instead of the callback it was given,
and the callback was still correct on the stack at the time.

**No fix is being shipped for it, and that is deliberate.** What clobbers the
register has not been isolated: the intervening calls preserve it correctly and
the callback saves and restores registers symmetrically, so the corruption
originates somewhere deeper in the native path that static inspection has not
reached. Settling it needs a debugger against a reproduction. Writing a
speculative fix into that path would be worse than leaving it alone.

The dumps predate this build by 82 commits and there are no newer VF2 dumps
across a week that included playtesting, which is suggestive but **not** proof
— the function the process died inside is byte-for-byte unchanged. If a crash
appears in this build, the fault address and the villager's label are the two
things worth capturing; they would confirm it is still live and give something
to trace.

## Content

Seeded from the 32 B185 matrix outputs, so everything the previous release
carried is carried forward. All patches, cheats and features are enabled and
compiled in.
