# VF2 runtime-hook Stage-1 spike — report

**Throwaway PoC. No shipping code changed; the real VF2.exe and the patcher are untouched.** This branch (`spike/vv-runtime-hook-stage1`) is for the VV patcher author's feasibility review and is not intended to merge.

## What Stage 1 was for

The feasibility study (`vf2-runtime-hook-feasibility.md`) rated the runtime-hook build model **GO WITH CAVEATS**. Its §5 PoC proved two independent detours *compose* on one function, but deliberately left one risk open (§5, §8.3.2): **stealing and relocating a real `/O2` prologue** on the actual binary. Stage 1 exists to retire that risk on one real feature.

## Feature chosen

**Allow Older Pregnancies** — an ungated CAVE+DETOUR feature (`work/patch_mobile_furniture_pack.py::patch_allow_older_pregnancies`). Its link-time form detours `CVillagerState::ChanceOfPregnancy` (`?ChanceOfPregnancy@CVillagerState@@QAE_NHHH@Z`, 0xF7 bytes): steal the 8-byte prologue, `E9` at the entry into a section-end cave that checks the runtime flag byte (`gVF2AllowOlderPregnancies`), calls the helper (`VF2RollOlderPregnancy`) on the older-age path, or replays the stolen prologue and continues.

## Result: the prologue steal is clean

The real `/O2` prologue, read from the stock `VillagerState.obj` and verified with capstone:

```
+0x00: push ebp            [55]
+0x01: mov  ebp, esp       [8B EC]
+0x03: mov  eax, 66666667h [B8 67 66 66 66]
```

Three whole instructions, an **exact 8-byte boundary**, and **no relative operands** in the stolen bytes — so the steal needs **no relocation** (unlike a prologue that begins with a `call`/`jmp` rel32 or a RIP-relative `lea`). This is the best case the study hoped for and did not assume.

## The spike (`stage1_spike.c`, 32-bit)

Loads the real prologue bytes, builds the function under test as the **real prologue + a safe stub body**, and installs the trampoline at runtime the way a proxy DLL would (VirtualAlloc RX cave, `E9 rel32` at the entry, `FlushInstructionCache`). Checks, all passing:

```
real prologue == expected steal bytes = 1
prologue steal is the clean 8-byte boundary = 1
install on real prologue = 1
re-hook of patched entry = 0        (composition safety: refuses a non-clean entry)
flag OFF: helper_calls=0, returned=0 (stolen prologue replayed, body continues — behaviour preserved)
flag ON : helper_calls=1, returned=1 (control reaches the DLL-side helper)
RESULT: all checks passed
```

## Scope and honesty

- **The body is stubbed, on purpose.** The stock `ChanceOfPregnancy` body is **not self-contained**: it has 6 external relocations (`ldwGameState::GetRandom`, `CTutorialTip::Queue`/`WasDisplayed`, the `TutorialTip` global). Executing the raw body standalone faults on the first unrelocated `call` — which the first spike run did (`0xC0000005`), and which is a property of the *body needing the whole linked game*, not of the hook. Running the real body is what the linked build's own tests already cover. So the spike proves the **hook mechanism** against the **real prologue**, with a stub for the fall-through body.
- **Proven here:** real-prologue steal is clean and needs no relocation; a runtime `E9`+cave trampoline installs and dispatches flag-gated to a helper or to the replayed prologue; re-hook is refused.
- **Not proven here (next):** the same install performed by an actual **proxy DLL loaded into the running VF2.exe** (DLL search-order hijack of an already-present dependency, e.g. `SDL2_image.dll`), against the function at its **loaded address**, with the helper reading real game globals — verified by in-game behaviour matching the static build. That needs a running game and is the natural Stage-1.5.

## Bearing on the study's verdict

Consistent with **GO WITH CAVEATS**. The riskiest per-site unknown for this feature — real-prologue steal — is **clean**, so the CAVE+DETOUR family (~30 sites) looks portable as the study predicted. This says nothing about the study's hard blocker (§4: the numeric ID cascade + shared tables, Stage 3), which remains the make-or-break and is untouched here.
