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
- **Not proven here (next):** the same install performed **in the running VF2.exe**, against the function at its **loaded address**, with the helper reading real game globals — verified by in-game behaviour matching the static build. That needs a running game and is the natural Stage 1.5.

## Independent reproduction

The VF2 feasibility-study session independently re-derived and reproduced this spike: rebuilt `stage1_spike.c` (VS x86) and ran it (all checks pass, exit 0); re-derived the prologue from the stock `VillagerState.obj` with capstone; and confirmed `ChanceOfPregnancy.bin` is byte-identical to the real 0xF7-byte (247-byte) stock function, so the spike is tied to the actual binary. Verdict: **GO for Stage 1.5**; the §5 open risk is retired for the CAVE+DETOUR family.

### Stage 1.5 install shape — an OPEN design decision (three candidates)

An earlier draft proposed a **proxy DLL hijacking `SDL2_image.dll`**. This is an **open decision for the owner / whoever runs Stage 1.5** — but *not* a vote between sessions' preferences, and *not* proxy-vs-nothing. There are **three** injection vectors to compare against fail-open / AV profile / robustness, all sharing the same load properties below:

| Vector | Load | Fail-open? | AV profile | Cost |
|---|---|---|---|---|
| **Proxy / hijack** (forward a real dependency) | simplest | **No** — load-bearing for the game (bad forward or quarantine → game won't start) | highest | one renamed real DLL + forwarders |
| **Separate launcher / injector** (start the game, then install) | second process | **Yes** — game binary untouched | its own (a second process that writes another's memory) | a launcher process |
| **Static import stub in the base exe** (added import that loads the companion) | most robust | **Yes** | lowest of the three | reintroduces **one** build step on the base image (not 32) |

Fail-open beats cheap-proxy as a default: the loader should not be load-bearing unless there is a concrete VF2 reason it must be. The proxy option additionally turns on two **mechanism claims** (from the VV production author, who ships the model) about what a proxy forces, each either true of VF2 or not:

1. **A proxy forces `DllMain` / the loader lock.** A forwarding proxy is entered by the loader while it resolves the game's imports, i.e. under the loader lock, where deadlocks live — whereas a companion called from a normal code site installs outside it.
2. **A proxy makes the DLL load-bearing for the *game*, not just the feature.** If the proxy is wrong about a forwarded export or gets quarantined, the game won't start at all; a called companion degrades to the feature silently not existing (which matters for a patcher shipped to players who can't debug it).

**The decision procedure:** check whether each failure mode actually applies to VF2's exe and loader, and whether the proxy approach has a concrete reason it avoids them. If it does, that reason beats the mechanism objection; if it doesn't, the called-companion shape wins on those grounds. Do not decide it by which session said what.

**Within the proxy option only, IF it is chosen — a tie-breaker, not a reason to choose it (feasibility-study session):** the vanilla exe directly imports `fmod.dll`, `SDL2.dll`, `SDL2_image.dll`, `WININET.dll`. `SDL2_image.dll` has the smallest export surface (41 exports, vs SDL2's 536, fmod's 230), so it is the cheapest of the three to forward; use **linker export-forwarders** (`#pragma comment(linker,"/export:IMG_Load=._real_SDL2_image.IMG_Load")`) to a renamed real copy rather than hand-writing 41 thunks. (fmod is a *direct* import in vanilla — the `LoadLibrary` fmod thunks are only in the modded helper build, so don't rely on them.) This picks the cheapest hijack target; it does not argue for hijacking over the launcher or static-stub vectors, and no one has yet tested it against the two mechanism claims. That check is the open work.

**What both agree on (the load properties — these are the actual point):**
- Load the companion **by full path** (`GetModuleFileNameA`), never a bare name (a bare `LoadLibraryA` is the search-order-hijack shape AV scores on).
- Install **outside the loader lock** — **never from `DllMain`**. VV uses a per-frame tick only because A New Home already had one; the requirement is just *any site that runs after the loader has settled and is reached reliably*. Don't manufacture a frame hook if VF2 lacks one, and don't retry `LoadLibrary` every frame — VV gets away with a tick only because the resolve is **cached on first call and the failure path latched** (retries zero times).
- **Fail open:** missing file/export → stock game, resolved once and remembered, so a feature's on/off switch becomes literally whether the patcher shipped that DLL (VV's Sort By patches zero exe bytes).

**AV constraints proven in VV** (independent of the proxy-vs-companion choice): keep the trampoline cave **R-X, never RWX** — a W+X page reads as self-modifying code and Malwarebytes quarantines it; `VirtualProtect` narrowly around any write and restore it. What has *not* drawn AV attention in VV: runtime `E9` detours installed from a legitimately-loaded companion, full-path `LoadLibrary`, `GetProcAddress`, SDL event watches — essentially this spike's shape. Whatever writes the exe must recompute the **PE checksum at 0x160** (a stale checksum is itself a strong AV signal), and the exe must be produced through the patcher from a **vanilla source**, never byte-poked in place.

### What Stage 1.5 must prove that Stage 1 could not (feasibility-study session)

1. **Loaded address under ASLR.** Locate `ChanceOfPregnancy` at its runtime address. The exe is PE32 — check whether it has a relocation table / `/DYNAMICBASE` or relies on a fixed image base; that decides whether to add `imagebase + RVA` or scan by signature (and per the prologue caveat, don't signature-match the `/O2` prologue itself).
2. **Timing.** The hook must be installed before the game first calls the target. Note the target choice interacts with this: `ChanceOfPregnancy` is a **gameplay event, not a startup point** — better for loader-lock reasons, but the companion may not load until the first pregnancy roll. If anything in Stage 2 needs the DLL present earlier, add a **separate earlier load site** and **share the fail-open latch** between the two rather than duplicating it.
3. **Real globals + in-game proof.** The helper reads the real `gVF2AllowOlderPregnancies` and the age args off the live stack, and in-game behaviour matches the static build. That is the gameplay proof the stubbed body defers.

### Per-site cautions before Stage 2 (VV production author)

- **Re-entry:** steal-and-replay is only safe if nothing re-enters the function at an address **inside** the stolen bytes. Enumerate every branch whose target lands at or past the hook site before Stage 2 — sites that look like choke points often are not, and this matters more with an 8-byte steal.
- **The prologue is not distinctive.** `mov eax,66666667h` is the signed-divide-by-5 magic constant, so the compiler inlined a `/5` there; this exact prologue is likely **shape-shared** with other `/O2` functions in the image. Hook a **fixed address**, never pattern-match this prologue.
- **The VV numbers are A-New-Home-specific.** The export counts, the mask-tick load site, and every offset are from one VV game; the other four each have their own hook site, loader and offsets. Nothing VV said transfers to VF2 **by address — only by shape**.

- **Re-entry:** steal-and-replay is only safe if nothing re-enters the function at an address **inside** the stolen bytes. Enumerate every branch whose target lands at or past the hook site before Stage 2 — sites that look like choke points often are not, and this matters more with an 8-byte steal.
- **The prologue is not distinctive.** `mov eax,66666667h` is the signed-divide-by-5 magic constant, so the compiler inlined a `/5` there; this exact prologue is likely **shape-shared** with other `/O2` functions in the image. Hook a **fixed address**, never pattern-match this prologue.

## Bearing on the study's verdict

Consistent with **GO WITH CAVEATS**. The riskiest per-site unknown for this feature — real-prologue steal — is **clean**, so the CAVE+DETOUR family (~30 sites) looks portable as the study predicted. This says nothing about the study's hard blocker (§4: the numeric ID cascade + shared tables, Stage 3), which remains the make-or-break and is untouched here.
