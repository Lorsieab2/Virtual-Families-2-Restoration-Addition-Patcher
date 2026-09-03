# Bathroom 2 fixtures + same-sex private time: investigation state

Findings from the 2026-08-16 session.

The Bathroom 2 fixture bug is **root-caused**. The same-sex private-time
bug was **not**, at the time of writing: the classifier match was the
prime suspect and needed live confirmation, which §3 says in as many
words. Calling both root-caused invited later work to build on an
unverified hypothesis, so this says which is which.

Everything below is evidence, not speculation, unless explicitly marked
as a hypothesis.

**Historical.** Both bugs have since been fixed; this is kept for the
reasoning and the addresses, not as a description of current behaviour.

---

## 1. Bathroom 2 remodels break the Bathroom 2 fixtures

### Symptom
With a "Bathroom 2 Remodel" row active, villagers can no longer use
Bathroom 2's shower, toilet, or sink.

### Established by live-process experiment

| State | Bathroom 2 fixtures |
| --- | --- |
| Native Bathroom 2 only (no remodel) | work |
| A Bathroom 2 Remodel owned (`0x14D`-`0x151`) | **broken** |
| A Bathroom 1 renovation also owned (e.g. Pink `0x140`) | work again |

The decisive test: clearing **only** the owned byte in live memory --
without refreshing decals and without saving -- restored the fixtures
**while the remodel was still drawn on screen**. That isolates the cause
to the stored flag, not to any visual/decal work.

### Root cause
`VF2AIBathroom2ActiveByte` stores each remodel's active flag at
`InventoryManager + itemId + 0x2A3`, which is the game's **native
owned-items array**. Setting it marks inventory items `0x14D`-`0x151` as
owned as far as native code is concerned, and some native consumer reads
that to decide Bathroom 2's fixture/room state.

Ruled out along the way:
- `VF2ApplyAIBathroom2Style` touches no ContentMap, hotspot, or
  `ActivateCondemnedArea` state -- it is visual-only apart from this flag.
- `VF2RebuildOwnedRenovations` is correctly bounded to `0xE1`-`0xEA` and
  cannot pick up these rows.
- House malfunctions use `Environment` props (`0x48/0x49/0x4A` for
  bathroom 2), not inventory items, so that is not the collision.

**Hypothesis (unconfirmed):** a native scan walks the owned array and
takes the first match to resolve room state. With only a Bathroom 2
remodel row set, the scan lands on an entry that yields invalid state for
that room; a Bathroom 1 row set earlier in the array gives it a valid
entry first, which is why Pink masks the bug.

### Why it isn't fixed yet
The fix is to move these five flags off the owned-items array into
storage native code never scans. **No free bits remain in the two masks
audited here** -- which is not the same as there being no free persistent
storage anywhere, and the next steps below look at exactly that (record
`0xA8` offset `0x00`, or claiming another achievement record). What was
verified rather than assumed is that both audited masks are full:

- `VF2PersistentHealthPlanAndRenovationMask` (Achievement record `0xA8`,
  offset `0x08`) is fully allocated:
  - bit 0: health plan entitlement
  - bits 1-15: the 15 mobile renovations (`kVF2MobileRenovationPersistentShift = 1`)
  - **bits 16-31: the "Oldest Villager" age record**
    (`history = (history & 0xFFFFu) | (boundedAge << 16)`)
- `VF2PersistentCheatAndPurchaseMask` (record `0xA8`, offset `0x04`) is
  also full: bits 0-7 flags, bits 8-31 generation counter.

An earlier plan to use bits 16-20 of the first mask would have silently
corrupted the Oldest Villager record in every save.

**Open decision:** claim a new Achievement record, repurpose offset `0x00`
of record `0xA8` (currently unexamined), or find genuinely inert item ids.
Whichever is chosen, the change must include **migration**: on load,
transfer any set legacy byte into the new location and clear the old byte,
so existing saves self-heal instead of silently losing a purchased
remodel -- and so the fixtures unbreak for players already affected.

Note the mobile renovation rows (`0x13C`-`0x14A`) and the two cheat
toggles (`0x14C`, `0x152`) also live in this array, the latter
deliberately (PR #12, for save persistence). Only the five Bathroom 2 rows
should move; the others must keep working and need re-verification after.

---

## 2. Same-sex couples: "private romantic time" on drop

### Requested behavior
Dropping two same-sex spouses on each other should perform "having private
romantic time" -- the same animations and timing as trying for a baby,
with 0% pregnancy chance, always available regardless of child count, and
never refused.

### Native flow (`theMainScene::HandleDropOnVillager`, offsets from function start)

```
+0x1E6  call IsRoomToPopulate
+0x1F2  jnz  -> +0x256      any of these four
+0x1FE  jl   -> +0x256      reach the private/
+0x20A  jl   -> +0x256      cooldown path
+0x218  jz   -> +0x256      <- SAME GENDER already jumps here
+0x21C  Say(StringId 1837)  <- only reached when genders DIFFER
+0x256  cooldown: cmp [gameState+0x25AE0], now
+0x26C  jnb  -> +0x2AB      cooldown not expired -> shake head + Say(1845)
+0x26E  NewBehavior(edi, 0x165) / NewBehavior(esi, 0x164)  <- PRIVATE TIME
```

Useful consequences:
- Behaviors **357 / 356** (`0x165` / `0x164`) are the private-time pair.
- Same-gender pairs **already bypass the child-count gate** natively, so
  "regardless of # of children" needs no work.
- The remaining native gate is the **cooldown** at `+0x266`.
- String `1837` cannot be the reported "These villagers are both the same
  gender." message, because it is only reachable when genders differ.

### What already exists
`TryToMakeBaby` is hooked to skip pregnancy, so these drops are at 0%.

**Prerequisite, as written:** this applied only to executables built with
Behavior Patches. `main()` called `patch_behavior_six_child_private_time`
only under `ENABLE_BEHAVIOR_PATCHES`, while Same-Sex Marriage is an
independently selectable setting, so with Behavior Patches off neither
the classifier detour nor the `TryToMakeBaby` early return was installed
and this paragraph did not describe that supported configuration. That
gap was closed later: the pregnancy guard is its own patch now, installed
with the embrace hook rather than with the optional behaviour patches.

**Superseded (kept because the reasoning matters):** this section used to
describe `patch_behavior_six_child_private_time` hooking `+0x218` and
routing any pair `VF2ClassifyRomanticSpouseDrop` accepted to `+0x26E`.
The classifier only returned 1 when `VF2MarriagePair` resolved the couple
*and* the dropped/target villagers were exactly that pair, which was
correctly identified above as the prime suspect for it not firing in
play. It was.

The deeper problem was that the classifier re-derived, from scratch, the
conditions the surrounding native code had just finished evaluating --
and it was hooked at a site where a 5-byte detour does not fit over a
2-byte `JE` (see §3). The hook now keys off the game's own refusal branch
instead: `+0x21A` is reachable **only** by falling through the `+0x218`
gender test, which is itself only reached after `IsRoomToPopulate()`
returned false and both villagers passed the adult/career checks. That is
precisely the condition the classifier was trying to reconstruct, already
computed by the game. So the refusal is simply replaced by a jump to
`+0x26E`, `+0x218` is left stock, and no cave, helper or reproduced
instructions are needed.

The general lesson: when a hook needs to know something, check whether
the code it is hooking has already worked it out. Reaching a branch can
be the answer.

### Blocked on
The reported message "These villagers are both the same gender."
(string data at `0x00C8AB30`) has **no code xrefs** -- it is resolved
through a runtime-built string table, so its caller cannot be found
statically. Identifying it needs live inspection: locate the pointer in
the runtime string table to recover its StringId, then find the
`CDealerSay::Say` call site using that id.

Until that is known, any change here is guesswork. The tempting shortcut
-- loosening the classifier to accept any two same-gender marriage-adults
without requiring `VF2MarriagePair` to match -- would also let
non-spouse adult pairs start romantic time, and must not be shipped
without in-game verification.

---

## 3. Fixed this session (for context)

- **PR #30**: the VF3 TVs were never being built from source. The build
  matrix points `VF2_PREVIOUS_BUILD_DIR` at the last release, and the
  generator keeps a target it finds already sitting in the output
  directory when the source is gone
  (`kept_existing_target_missing_source`). Every retained manifest from
  B164 through B168 records that for both flat screens --
  `work/assets/vf3_source_sprites` had been missing for weeks and each
  release just recopied the one before it. Worth remembering when
  auditing any other asset: a shipped release is not evidence that an
  asset can still be produced.

- **PR #25**: arbitrary memory corruption in the romantic-drop trampoline.
  The 5-byte hook at `+0x218` clobbered `push -1` / `push 72Dh` at
  `+0x21A`-`+0x21C`, and the fall-through jumped back into its own jump
  displacement, executing `add [eax],eax` then a write through a garbage
  absolute address. Reachable by dropping any two different-gender
  non-couple adults in a full house. Affects **opposite-sex** households
  on a stock Behavior Patches build.
