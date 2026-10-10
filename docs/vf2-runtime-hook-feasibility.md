# VF2 patcher: feasibility of moving from a static-relink matrix to VV-style runtime-hook modules

**Feasibility study — no shipping code changed.** All findings re-derived from the repo at `C:\vf2w\vf2`. The only code written for this study is a throwaway proof-of-concept (`poc/`, next to this report; not in the VF2 repo), which exists solely to substantiate §5.

> **Update 2026-10-10 (Stage 1, branch `runtime-hook-stage1`).** Stage 1 has been built on the real vanilla binary: see **§9** (what was built and proved), **§10** (the live-test script, still to be run) and **§11** (the complete, ordered conversion plan for every patch). Two parts of the original text are superseded and marked in place: the proxy-DLL loading model (§8.2, rejected by the owner; replaced by a loader stub in its own section) and §5's open question about stealing a real `/O2` prologue (now proved statically and in a harness; live confirmation pending). The owner's rule since this update: **companion DLLs over cave space unless absolutely necessary** — the executable gets only the loader stub and the single vtable slot that reaches it.

**Recommendation: GO WITH CAVEATS — as a bounded partial modularization, not a wholesale conversion.**
The riskiest single unknown (two independent modules hooking the same function, composed at load time) is *resolved and works* — a 32-bit proof-of-concept demonstrates chained trampolines with intact stock behaviour and conflict detection. But the study also confirms two hard blockers to *full* modularization: (1) the features are numerically coupled through one linear image-ID / string-ID append cascade and shared tables (`achievementOrder`), and (2) a large share of the real edits are **mid-function call insertions and relocation retargets**, not clean function-entry detours. The honest win is to modularize the cleanly-detourable, self-contained features and collapse the matrix, while leaving the numerically-coupled table/ID edits static.

---

## 1. What the two models actually are (verified)

### 1.1 The VV model (target)
One small companion DLL per feature, compiled once, composed at install/runtime. No cross-product of binaries.

### 1.2 The VF2 model (today) — re-derived
The 32-variant matrix is real and is built exactly as described. `work/build_matrix.ps1` iterates the 32 variants in `data/vf2/build-matrix-toggles.json`; for each it sets `VF2_ENABLE_*` env vars, runs the Python generator (`work/patch_mobile_furniture_pack.py`, **39,895 lines**) which performs COFF byte-surgery on stock `.obj` files, then runs `work/build_b119.bat` which **statically relinks a full monolithic exe** (`link @… 184 objects … /OUT:<exe>`). 32 generate+link cycles → 32 exes.

**Verified matrix facts:**
- Exactly **32 variants** (counted from the JSON).
- The pairing note is accurate: `mobile_renovations` and `ai_generated_bathroom2` are on/off together in all 32 (16 both-on, 16 both-off) → 6 nominal toggles collapse to 32 rather than 64.
- Two matrix env vars are **fixed constants**, not dimensions: `build_matrix.ps1` sets `VF2_ENABLE_MOBILE_SOUND_ASSETS="0"` and `VF2_ENABLE_HOLIDAY_BODY_TYPES="1"` for every variant.
- The generator has *more* toggles than the matrix uses (`ENABLE_HOLIDAY_BODY_TYPES`, `ENABLE_MOBILE_SOUND_ASSETS`, `ENABLE_DEBUGGER_FEATURES`), all defaulting **on** except the debugger gate.

### 1.3 The crucial nuance: the model is already *half* modular
The feature *logic* is already separate, compiled-once C++: `work/compile_helpers_b22.rsp` compiles one `.cpp`/`.c` per feature — `vf2_island_events.cpp`, `vf2_special_upgrade_effects.cpp`, `vf2_store_scrollbar.cpp`, `vf2_spontaneous_behaviors.cpp`, `vf2_mobile_renovations.cpp`, etc. There is even a **runtime dynamic-loading shim already shipping**: `work/vf2_fmod_thunks.cpp` does `LoadLibraryA("fmod.dll")` + `GetProcAddress` and forwards calls.

So the barrier is **not** "can this team write a runtime module" — they already ship one. The barrier is that the *wiring of feature code into stock code* is done as **link-time byte surgery on shared stock objects**, followed by a full relink. That wiring is what must become a runtime hook.

---

## 2. The core constraint, stated in the code itself

The single most important piece of evidence is `select_exact_executable_overlays()` in `work/offline_vf2_patcher.py:1824`. Its docstring is the reason the matrix exists:

> "Overlay EXEs all write the same named modded executable. Applying multiple feature overlays sequentially can silently drop earlier code when no combined overlay exists. **Fail closed** unless the manifest contains exactly one record matching the complete enabled overlay set."

The current system **already refuses** to union per-feature exes and demands a pre-built exe for the exact feature combination. This is the in-code confirmation of the "valid combinations byte-conflict" evidence. The runtime-hook proposal is precisely an attempt to escape this by never combining bytes — composing behaviour instead.

**Empirical confirmation (I re-ran the diff on the shipped B192 exes):**
| | core | behavior_patches | cheat_upgrades |
|---|---:|---:|---:|
| size (bytes) | 1,758,720 | 1,804,800 | 1,760,256 |
| first divergence from core | — | **0x128** (PE header) | **0x128** (PE header) |
| bytes changed vs core (overlap) | — | 1,507,364 | 829,728 |

bp and cu both change bytes at **781,574** shared offsets, of which **732,996** write *different* bytes — the brief's figures reproduce exactly. But the interpretation matters: both exes diverge from core at 0x128 and have different total sizes, so the bulk of those 732,996 "conflicts" is **relink shift** — the same functions relocated to different addresses by two independent links — not two features overwriting the same semantic bytes. This is the key insight that (a) motivates the runtime model (the features are not genuinely colliding; they are shift-incompatible artifacts of independent relinks against a common base) and (b) explains why per-feature exe *diffs* can never be unioned: each diff is expressed against a layout the other has already moved. A runtime model sidesteps both by patching one fixed base image in place, at fixed addresses, so nothing shifts.

---

## 3. Classifying the edits: what is hookable and what is not

A full per-callsite inventory was produced (every `insert_section_bytes`, `retarget_relocation`, `grow_bss_section`, with enclosing function, target object, section kind, and gate). The distilled classification is below; the full table is available on request.

### 3.0 The five edit classes, by count and hookability
| Class | ~count | What it is | Runtime-hook verdict |
|---|---:|---|---|
| **CALL-RETARGET** (relocation-only) | ~28 | repoint an existing `call rel32` at a feature helper | **Cleanest.** Already behaves like a per-call detour. Several are explicitly "relocation-only" (`patch_maximum_resource_achievement_callsites:39480`, `patch_event_collectable_slot_replacement:24096`). Runtime-portable via call-site patch or, where it's an import, IAT patch. |
| **CAVE+DETOUR** | ~30 | append a trampoline at section end + write `E9` at a function entry/epilogue | **Directly portable.** This *is* an inline detour already, just resolved at link time. The whole marriage/pregnancy/mortality/older-villager family (mostly **ungated**) is this shape. |
| **MID-FUNCTION-INSERT** into `.text` | ~26 | splice bytes at an interior instruction boundary, re-encode spanning branches | **Hard.** Needs a runtime mid-body patch: locate the interior offset, steal+relocate stolen bytes, jump back. Several are at **prologue+3** (near-entry, easier). The canonical hard one is `theMainScene::DrawScene+0x39` (`:33639`). |
| **DATA-REF-RETARGET** (DIR32) | ~8 | rewrite a ctor macro-table / vtable pointer slot | **Portable but not a detour** — rewrite a function-pointer table entry at runtime. `patch_behavior_label_variants:38149` alone fans out to ~57 macro entries. |
| **DATA-TABLE / BSS growth** | ~15 + 7 | enlarge a fixed stock array + widen the bound/count immediates around it | **Hardest to modularize** — see §4. |

**Reframing finding (important): most of the surgery is ungated.** The furniture/inventory/store/string/graphics/achievement base wiring and the entire marriage/pregnancy/mortality/reconciliation family run **unconditionally in every variant**. The 6 matrix toggles gate only a *minority* of sites — chiefly Holiday Ornaments (CollectableItem/Collectable/CollectionScene + collector), Behavior Patches (spontaneous/label/venue/hammock), Island Events, Cheat Upgrades (peep lists, store price multiplier), and the renovations pair. So converting to modules does **not** shrink the always-applied surgery; it only helps for the toggled subset. One dead site exists (`patch_vf3_style_child_adoption_chooser:22523`, call commented out — applied in no build).

### 3.1 Primitive-call census (re-derived, method-call form)
| primitive | calls | meaning for runtime hooking |
|---|---:|---|
| `insert_section_bytes` | 76 | grows a section; on `.text` = **mid-function code insertion** (hard); on data = **shared-table growth** |
| `retarget_relocation` | 40 | redirect an existing call/data ref to a new symbol (sometimes a clean detour, sometimes mid-function) |
| `append_relocation` | 89 | wiring: add a reference to feature code (modular part) |
| `append_undefined_symbol` | 114 | wiring: import a feature symbol (modular part) |
| `grow_bss_section` | 7 | grow zero-init storage (shared-table growth) |
| `set_symbol_storage_class` | 2 | relax linkage so a feature can reference a stock static |

Distinct stock objects referenced via `PATCHED /`: **32**. (The study brief's "28 objects / 65 sites" are hand-counts; they are directionally right but the verified figures are the ones above. "Sites" here = individual primitive calls.)

*NOTE: the user's hot-object counts (theMainScene 10, Behavior 9, …) count all primitives per object; my re-derivation splits them by primitive — see the classification agent's per-site inventory folded in below.*

### 3.2 The three edit classes and their hookability
1. **Function-entry redirect / call-target swap (CLEAN).** A `retarget_relocation` that repoints an existing `call rel32` at a feature helper. Example: the Holiday Ornaments hooks in `IslandEvents.obj` repoint `CEventTheCollector::CanFire`'s existing calls (offsets +0x088/+0x0FB/+0x171) from `CollectionCount` to `CollectionCountWithHolidayOrnaments` (`patch_mobile_furniture_pack.py:9310`+, comment: "relocation-only Holiday offer hooks"). These map well to a runtime call-site patch or an IAT/vtable-style redirect **if** the target resolves to a fixed address.
2. **Mid-function call insertion (HARD).** `insert_section_bytes` on a `.text` section, injecting a 5-byte `call rel32` at a *verified interior instruction boundary*. Canonical example: `theMainScene::DrawScene` at **+0x39**, "after `CWorldMap::Draw` and before `CDecal::DrawDecals`" (`patch_mobile_furniture_pack.py:33636`). This is not an entry detour; a runtime equivalent must patch bytes mid-body, steal+relocate the stolen instructions, and jump back — doable but per-site engineering, and it needs the interior offset located reliably at runtime.
3. **Shared-table / data growth (HARDEST to modularize).** `insert_section_bytes` on data sections + `grow_bss_section`, growing tables multiple features append to. See §4.

### 3.3 Prologue reality check
`theMainScene::DrawScene` prologue is `56 / 8B F1 / 83 EC 10` (`push esi; mov esi,ecx; sub esp,10h`) — a clean 7-byte stealable prologue, **but no `mov edi,edi` hotpatch pad** anywhere in the disassembly. The build was **not** compiled `/hotpatch`, so the cleanest Microsoft Detours hot-patch slot is unavailable; runtime hooks must steal and relocate real prologue bytes. This raises the per-site cost but does not block it.

---

## 4. Shared-structure edits — the real blocker to full modularization

Multiple features grow the **same** tables and share **one** linearly-computed ID space. This is confirmed, with line numbers:

- **One linear image-ID append cascade.** `holiday_body_descriptor_count()` (`:6903`) is the first addend in a chain that shifts *every* downstream image base: outfit icons (`:6462`), mobile renovations (`:6470`), holiday ornaments (`:6688`, also gated on `ENABLE_MOBILE_RENOVATIONS`), the store-icon base (`:6480`, a function of **three** flags), bathroom2, curtains, head icons, prop art. Turn one feature on and later features' image IDs move.
- **One linear string-ID cascade.** `mobile_island_event_string_count()` (`:11624`) — *not* gated by `ENABLE_ISLAND_EVENTS` (IDs reserved unconditionally, populated conditionally) — feeds cheat/outfit/behavior-label/ornament string IDs. Island-event data files shift the other features' string IDs even when island_events is off.
- **`achievementOrder` shared table** (`:21596`+): `holiday_ornaments` inserts 1 row, `behavior_patches` appends ~29, and both feed one shared visible-count (`:21820`). The generator grows the table and rewrites the count in place.
- **`gHomeList` House Renovations list** (`:12553`+): `mobile_renovations` and `ai_generated_bathroom2` append **interleaved** rows and jointly widen three native count sites.

Two independently-loaded DLLs cannot grow one fixed stock table at runtime by inserting bytes — there is no link step to relayout it, and no spare capacity. The runtime alternatives are: (a) **reserve a fixed capacity** in the stock table via one static base patch and have modules register entries into the reserve at load (works only if a max is acceptable and the stock code reads a length variable, not a hard-coded count); or (b) **retarget the table pointer** to a module-allocated larger table and have each module register into it (needs a merge/registration protocol and one owner). Both are real engineering, and neither is a drop-in per-feature DLL. The linear ID cascade is the deeper problem: to be order-independent, each feature needs its **own reserved, non-overlapping ID range**, decoupling the bases that are currently computed sequentially across features.

**Control-flow vs numeric independence:** the four "free" matrix toggles (island_events, cheat_upgrades, holiday_ornaments, behavior_patches) are **control-flow independent** — verified: no `if ENABLE_X and ENABLE_Y` and no nested feature gates among them, so all 16 combinations are valid and distinct, and no dependency rule can prune them. But they are **numerically coupled** through the ID cascade and `achievementOrder`. That is exactly why per-feature diffs of shipped exes overlap and cannot be unioned: the diffs are computed against layouts that no longer match once combined.

---

## 5. The riskiest unknown — two modules hooking one function

**The claim tested:** two independently-compiled feature modules can hook the *same* stock function, in an order fixed only at load time, without corrupting each other or the stock function, and each still reaches the real original behaviour. This is the composition semantics the whole proposal rests on, and it is the thing the current system fails at (`select_exact_executable_overlays` fails closed precisely because sequential per-feature exe overlays "silently drop earlier code").

**PoC design (throwaway, 32-bit, built with the repo's own VS18 x86 toolchain):**
- A stock `DrawScene(frame)` compiled `/O2` with an ordinary MSVC prologue (the stand-in for a hot shared function like `theMainScene::DrawScene`).
- Two independent "feature" detours, `A` (+7 to the result, like a behavior tweak) and `B` (×2 and counts calls, like a cheat), each written to call `original(frame)` without knowing the other exists.
- A tiny shared hook engine (`hookkit.c`) — the "loader" — with one registry per target. **Composition rule:** the first module to hook a target steals its prologue into a trampoline; each later module's `original` pointer is set to the *previously installed detour*, and only the registry ever rewrites the target's entry bytes. So load order = call nesting (last installed = outermost), and no module overwrites another module's patch.
- Conflict detection: the engine refuses to hook an entry it cannot decode as a clean stealable prologue (the proxy for "this is a mid-function / not a function entry" target — the un-hookable class from §3).
- A shared-table append test: two modules append into one fixed-capacity stock table through a registry-owned `table_append`, the runtime analogue of §4's growth problem.

**Expected result:** `DrawScene(5)` stock = 1005; after loading A then B, a stock call site yields `B(A(1005)) = (1005+7)*2 = 2024`; the trampoline still returns 1005 (stock intact); the table grows cooperatively; and re-hooking the already-patched entry is refused.

**PoC RESULT — built with VS18 x86 and executed (exit 0, all checks passed):**

```
== VF2 runtime-hook composition PoC (32-bit) ==
stock DrawScene(5)            = 1005 (expect 1005)
composed DrawScene(5)         = 2024 (expect 2024)
stock via trampoline          = 1005 (expect 1005)
table after A,B append: len=5 slots A=3 B=4 (expect 5,3,4)
re-hookability of patched entry = 0 (expect 0): entry begins with a jmp (0xe9): not a clean stock prologue

RESULT: all checks passed
```

**What this proves and what it does not.**
- *Proven:* two independently-compiled detours hook one function; composition follows load order (`B(A(stock)) = (1005+7)*2 = 2024`); the real stock body stays intact and reachable via the trampoline; two modules grow one shared table through a registry without a link step; and the engine refuses to re-hook a non-clean entry (conflict detection). The composition mechanism — the thing the current matrix cannot do — works.
- *Not proven by this PoC (deliberately out of scope, and the real risk that Stage 1 must retire):* stealing and **relocating** a *real* `/O2` prologue. The PoC target uses a hand-written clean 5-byte prologue so the steal is deterministic; the real `theMainScene::DrawScene` prologue is `56 8B F1 83 EC 10` with no hotpatch pad, and the toy length-reader here *correctly refused* the real `/O2` shape (`0xC7 mov r/m,imm`) rather than guess — which is exactly the honesty the production port needs (it must decode with capstone, as `coff_patch.py` already does). So the mechanism is proven; the per-site prologue engineering on the actual binary is the next thing to prove.
- *Update (Stage 1):* done on the vanilla executable for `CVillagerState::ChanceOfPregnancy` (0x4A0810, FPO prologue `53 55 56 57 8B 54 24 14`, 8 bytes stolen, decoded and checked by capstone) plus one mid-function store and four call sites — §9. Note the shipped vanilla code generation differs from the object files: the object's prologue is `55 8B EC B8 67 66 66 66`, the vanilla one has no frame pointer, so every runtime site must be located and pinned in the **vanilla** image, never derived from the objects.

---

## 6. What the offline patcher/exporter becomes

Today the bundle ships **one full patched exe per executable combination** and authenticates each by **exact SHA-256**, recorded *independently* from the matrix build outputs:
- `work/export_release_bundle.py` wires one `--<variant>-exe` per built variant into the exporter and refuses to package if any declared variant's exe is missing or any overlay setting would be silently dropped (`--release-bundle`).
- `work/export_release_variant_identities.py` reads the matrix outputs (not the bundle) and writes `release-identities-<REL>.json`: for each variant, `{requires, sha256, size}`. It refuses if two variants collide to one binary.
- The gate `work/verify_offline_bundle_zip.py --require-identities` checks the packaged exes match those independent hashes.
- At apply time, `select_exact_executable_overlays()` picks the single exe whose `requires` set equals the user's enabled settings, or fails closed.

The entire trust model is **whole-exe identity**. In a runtime-hook model there are no per-combination exes; the bundle ships **stock-exe hash + N feature-DLL hashes + a loader**, apply drops the DLLs + loader next to the stock exe, and there is **no way to pre-authenticate the composed result** because it is assembled at runtime. Gating shifts from "this exact combined exe hash is blessed" to "this exact stock exe + these exact module hashes are blessed, and the loader composed them" — a materially weaker guarantee that the study must call out.

---

## 7. Scope, risk, and player-facing changes

- **Player-facing change:** instead of a single patched exe, the player gets the stock exe plus a loader and DLLs (or an injected/proxy DLL). This is a bigger install surface and a new failure mode (loader must run before/at game start).
- **Anti-virus / false-positive risk:** runtime code injection, inline trampolines, and `VirtualProtect`/`WriteProcessMemory` on another process's `.text` are classic heuristic-AV triggers. A proxy-DLL (hijacking an already-loaded dependency like `SDL2_image.dll`/`zlib1.dll`) that installs in-process hooks is lower-risk than an external injector but still touches executable memory. The current static exe has none of this.
- **Save compatibility:** unchanged in principle (same save format), but must be verified per feature; the ID-cascade reservation scheme could shift on-disk IDs if not pinned.

---

## 8. Recommendation and staged plan

### 8.1 Verdict: GO WITH CAVEATS — bounded partial modularization, not a full conversion

**NO-GO on the maximal reading** ("replace the 32-variant matrix with one stock exe + N per-feature DLLs composed at runtime, full stop"). Two findings block it:
1. **Numeric coupling (§4).** The features share one linear image-ID / string-ID append cascade and shared tables (`achievementOrder`, `gHomeList`). Independent modules cannot each grow a fixed stock table at runtime, and cannot be order-independent while their ID bases are computed sequentially across features. Making them independent means giving each feature its own reserved, non-overlapping ID range and a runtime table-registration protocol — real work, and a behaviour change to the ID layout that risks save compatibility.
2. **The always-on surgery doesn't shrink (§3.0).** Most sites are ungated. Modularizing the 6 toggles leaves the large unconditional base-wiring + marriage/pregnancy family exactly as it is; you'd still need a static base patch (or those become "always-loaded module 0"), so you don't get to a pure stock exe.

**GO on the bounded reading**, because the core mechanism works (§5) and a large, well-isolated slice of the edits is already detour-shaped:
- The **CAVE+DETOUR** family (~30 sites) is already an inline detour resolved at link time — it ports to runtime almost mechanically.
- The **CALL-RETARGET** family (~28 sites) is per-call redirection, several explicitly relocation-only.
- Together that is the majority of sites, and it is exactly the shape the PoC validates.

The honest win: **collapse the matrix and modularize the cleanly-composable features; keep the numerically-coupled table/ID edits as one static base.**

### 8.2 What the delivery model becomes (recommended target)
- Ship **one statically-built base exe** = stock + all *unconditional* wiring + the *table/ID reservations* for every optional feature (fixed capacity, populated at runtime). This is ~1 build, not 32.
- Ship **one runtime module per matrix toggle** (island_events, cheat_upgrades, holiday_ornaments, behavior_patches, and the renovations pair as one module) as a companion DLL, loaded by a **proxy DLL** hijacking an already-present dependency (e.g. `zlib1.dll`/`SDL2_image.dll`) — no external injector, lowest AV profile.
  - **SUPERSEDED (2026-10-10):** the proxy-DLL loader was rejected by the owner's Virtual Villagers patcher author. The loading model is now: one tiny loader stub in the game executable, in its own read-execute section (`.vf2fun`) with its state in a separate read-write section (`.vf2fud`), reached from theGame's Init vtable slot; it loads the companion DLL by full path (`GetModuleFileNameW` + `LoadLibraryW`, never a bare name, never from `DllMain`), resolves exports with `GetProcAddress`, and fails open. Same model as the Virtual Families 1 patcher. Built in Stage 1 (§9). The "one statically-built base exe" above is also superseded for anything the DLL can do (§11): the owner's rule is DLLs over cave space unless absolutely necessary.
- The offline patcher ships **base-exe hash + N module hashes + the proxy loader**, applies by dropping files next to the stock exe, and gates on `{base sha256} + {selected module sha256s}` instead of one combined-exe hash (§6). Note the weaker guarantee: the composed result is never pre-authenticated.

### 8.3 Staged plan — riskiest unknown first
1. **Stage 0 (done here):** prove two modules compose on one function at load time. → §5 PoC.
2. **Stage 1 — spike on the real binary (the next riskiest unknown):** take **one** already-CAVE+DETOUR, self-contained, *ungated* feature (e.g. the older-pregnancy or same-sex-marriage patch) and reimplement its link-time cave as a runtime trampoline installed by a proxy DLL against the *stock* exe. Success = identical in-game behaviour to the static build, verified against the existing per-feature contract tests. This resolves prologue-stealing + relocation + fixed-load-address assumptions on the actual code.
3. **Stage 2 — one toggled, table-free feature:** convert `behavior_patches`' DATA-REF-RETARGET macro-table edits (`:38149` etc.) to a runtime function-pointer-table rewrite in a module. Resolves the ctor-macro/vtable class.
4. **Stage 3 — the shared-table protocol:** design and prove the reserve-capacity + runtime-registration scheme for `achievementOrder` and the image/string ID ranges, with a save-compat test. This is the make-or-break for holiday_ornaments and the renovations pair. If it fails, those stay static and the matrix collapses only along the axes that converted.
5. **Stage 4 — re-gate the packaging/identity model** (§6) and cut the matrix to (base × converted modules).

### 8.4 If Stage 3 fails (the fallback that is still a win)
Keep the numerically-coupled features (holiday_ornaments, renovations pair, and anything touching the ID cascade) **static**, modularize only the table-free toggles (cheat_upgrades price/list logic that reads a length var, behavior_patches macro table). Even partial conversion removes toggle axes from the matrix: dropping 2 of the 4 free toggles takes 32 variants to 8. That alone roughly quarters build time with none of the ID-cascade risk.

---

### Appendix A — throwaway PoC
Sources: `poc/` next to this report (`hookkit.h`, `hookkit.c`, `poc.c`). Not in the VF2 repo; delete freely. It exists only to substantiate §5.
Build (must use a **short path** — the VS18 preview `cl` fails with `C1083: … file: ''` when the build directory path is near MAX_PATH, which is why it was built in `C:\vf2poc`):
```
copy poc.c hookkit.c hookkit.h C:\vf2poc\   &   cd /d C:\vf2poc
call "…\VC\Auxiliary\Build\vcvarsall.bat" x86
cl /nologo /O2 /D_CRT_SECURE_NO_WARNINGS /Fepoc.exe poc.c hookkit.c
poc.exe
```

### Appendix B — corrections to the brief's figures
- Verified: **32 variants**, **32 distinct patched objects**, pairing is real (all 32 consistent).
- The brief's "65 sites / 28 objects" are hand-counts; re-derived primitive-call totals are **76 `insert_section_bytes`, 40 `retarget_relocation`, 89 `append_relocation`, 114 `append_undefined_symbol`, 7 `grow_bss_section`, 2 `set_symbol_storage_class`**.
- The pairing rule is **convention-only in the matrix JSON**, not enforced in generator code — the generator even has a bathroom2-only branch (`:34016`). Dependency rules therefore cannot forbid `behavior_patches+cheat_upgrades`, confirming the brief.
- `VF2_ENABLE_MOBILE_SOUND_ASSETS` and `VF2_ENABLE_HOLIDAY_BODY_TYPES` are **fixed** across the matrix (not toggled), so the effective free toggles are the 4 the brief names.

---

## 9. Stage 1 results — Allow Older Pregnancies as a runtime add-on to the VANILLA game

Branch `runtime-hook-stage1` (worktree `C:\vf2w\wt-runtime`), not pushed. Everything below is **static and harness evidence**; the in-game confirmation is §10 and has not been run yet.

### 9.1 Feature chosen, and why
**Allow Older Pregnancies** (`patch_allow_older_pregnancies` + `patch_next_generation_age_gate`, offline setting `allow_older_pregnancies`, B200 flag byte `.vf2preg`).
- **Ungated by the matrix:** installed in every B200 executable, switched by its own one-byte flag. The flag maps one-to-one onto a setting the DLL reads (`vf2fun.ini`), so equivalence with B200 is a property of one feature, not of a matrix cell.
- **Self-contained data:** reads only stock state (ages, fertility, the villager array, the Family Tree record, the try-for-baby deadline). No shared table, no ID cascade, no save-format change.
- **Covers all three hookable classes the study needs proved on the real binary:** a true function-entry prologue steal (ChanceOfPregnancy), a mid-function instruction replacement (the cooldown store), and call-site retargets (Next Generation).
- **Same-sex marriage was rejected for Stage 1** even though its gender decision is a single 6-byte site. In B200 that feature spans six patch functions (candidate gender, embrace, pregnancy guard, spouse accessors, Accept finalization and the details status), and the gender hook alone would ship a half-working marriage. Its on/off state is also a persisted inventory byte (`InventoryManager+0x14C+0x2A3`) that exists only because Cheat Upgrades grows the inventory tables. Vanilla has no such row, so it cannot be ported without the table work in §11 step S6. It is also gated by `ENABLE_CHEAT_UPGRADES`.

### 9.2 Hook sites in the vanilla executable (SHA-256 `1582d9e8…b73c3`, image base 0x400000, no relocations, no ASLR)
All found structurally in the vanilla image and pinned byte for byte in `runtime/vf2_runtime_sites.py`. `runtime/tools/gen_sites.py` re-proves every pin with capstone.
| Site | Vanilla bytes / instructions | How it was located and proved |
|---|---|---|
| theGame Init vtable slot `0x4E29A8` → `0x428620` | data | RTTI `.?AVtheGame@@` TD `0x5336AC` → COL `0x524FB8` → vtable `0x4E2998`. theGame.obj orders the slots so that slot 4 is `Init`. Created once at `0x42AFEB`, then Init is called once through `[edx+10h]` at `0x42AFF8`, before `Run` (+0x18). **This is the only pre-existing byte the patcher changes.** |
| `CVillagerState::ChanceOfPregnancy` `0x4A0810` (entry detour) | `53 55 56 57 8B 54 24 14` = `push ebx; push ebp; push esi; push edi; mov edx,[esp+14h]` | The only function with all three `push 868h` (eStringPregnancyTutorial) of the stock body. GetRandom `0x403F70`, TutorialTip `0xAA7E98`, Queue `0x4AA020` (`ret 0Ch`) and WasDisplayed `0x4A9D40` are pinned via `0x4A08AA`. The only caller is `0x49F5FA`. No absolute reference exists. No direct branch anywhere in .text lands in `0x4A0811-0x4A0817`. The 8 stolen bytes are whole instructions, none relative. |
| Cooldown store `0x49F6DF` in `CVillagerPlans::ProcessCurrentPlan` (fn `0x49EC00`) | `89 98 E0 5A 02 00` = `mov [eax+25AE0h],ebx` | A failed roll (`je 0x49F6C4` at `0x49F601`, the only branch into the block) runs `Get; GetSecondsFromGameStart; lea ebx,[eax+4B0h]; Get; push -32h; mov ecx,esi; <store>`. `esi = mother+6AF4h` (`lea esi,[ebx+6AF4h]` at `0x49F5F1`, ebx = `0x498D40` GetMatriarch) and `edi` = father (`0x498DB0`). Both are callee-saved up to the store. No branch lands in `0x49F6E0-0x49F6E4`. |
| `CFamilyTree::CanStartNextGeneration` `0x48FF70` callers `0x430681`, `0x430DB8`, `0x43C0BD`, `0x4407DC` | `E8 rel32 → 0x48FF70` | These are all the direct calls in .text, and there are no absolute references. They map 1:1 to B200's four retargets: CFamilyTreeScene vtable `0x4E2DD8` slot 8 `UpdateScene` (+0x41, object +0x43), slot 9 `Activate` (+0xA8, object +0xB0), theMainScene `HandleVillagerDetailsButton` `0x43BEE0` (+0x1DD, object +0x1D2) and `UpdateScene` `0x4400F0` (+0x6EC, object +0x6F9). |
| Data the DLL reads | VillagerManager `0x5B9F58` (villager i at `+0x1CC70 + i*0x1CC0C`, pinned via GetVillager `0x498CB0`), FamilyTree `0x5ACFC8`, CountSurvivingChildren `0x490080` (whole body pinned), theGameState singleton `0x558FC0` | |

`theMainScene::TryToMakeBaby` (a second ChanceOfPregnancy caller in theMainScene.obj) is **not in the vanilla executable**: its "Joey" string has one code reference, in ProcessCurrentPlan. In the objects it is referenced only by debug relocations (types 7/10/11), never called. So B200 and vanilla share the single live caller.

### 9.3 What was built (all under `runtime/` + `tests/test_runtime_hooks_stage1.py`)
- **Executable bootstrap only** (`runtime/vf2_runtime_patcher.py`, stub from `runtime/tools/build_stub.py` → `runtime/stub.json`). There are two new sections: `.vf2fun` at `0xB3B000` (RX, 223 bytes of code plus strings) and `.vf2fud` at `0xB3C000` (RW, 2064 bytes). The Init slot is pointed at the stub. SizeOfImage, NumberOfSections and CheckSum are updated. **No cave in any existing section, no other byte changed** (asserted by test).
  - The stub runs `pushfd; pushad`, then the one-shot loader: `GetModuleHandleA("kernel32")` and `GetProcAddress` through the game's own IAT (`0x4DE1E4`/`0x4DE1E8`), `GetModuleFileNameW(0)`, strip to the folder, append `Virtual Families 2 Patcher Files\vf2fun.dll`, `LoadLibraryW`, `GetProcAddress("VF2Fun_Startup")`. It calls Startup if present, then `popad; popfd; jmp 0x428620`. Any failure leaves state = 2 and the stock game.
- **Companion DLL** `runtime/native/vf2fun/vf2fun.cpp` (built by `runtime/native/build.bat`: static CRT, `/W4 /WX`). `VF2Fun_Startup` reads `[Patches] AllowOlderPregnancies` from `vf2fun.ini` beside the DLL. Off means nothing is written (stock game). On, it first compares **every** pinned run (`vf2fun_sites.h`, generated) with live memory and installs nothing on any mismatch. It then builds the trampoline (stolen 8 bytes copied from live memory, then `jmp 0x4A0818`) in a page that is RW while built and RX after. It writes the six patches (entry `jmp`+3 NOP, cooldown `jmp`+1 NOP, four `call` rel32), each under its own VirtualProtect that is restored straight away, and rolls everything back if any write fails. The logic is a line-for-line port of B200's helpers: `VF2RollOlderPregnancy`, `VF2StoreTryForBabyCooldownMaybe`, `VF2CanStartNextGenerationAtOlderAge`, and its ChanceOfPregnancy cave condition. It writes `vf2fun.log` and exports a `VF2Fun_Status` block of counters for the live test.
- **Read-only live probe** `runtime/tools/probe_stage1.py` (PROCESS_VM_READ). It shows the stub state, the bytes at each site, the status counters, the villagers (age, gender, fertility, health) and the try-for-baby deadline as seconds remaining. Its only write, `--set-age`, refuses unless the exe name contains "Test".
- **Patched test copy** (not in git): `C:\vf2w\vf2-runtime-stage1-test\VF2 Runtime Test.exe` (SHA-256 `04f9ff02840b6e60e6f999a3d625e698defaa5dc1965a8a662a408558871b28e`), with `vf2fun.dll` (SHA-256 `74b337a3…cdafb6e`), `AllowOlderPregnancies=1` and `FullScreen=0`.

### 9.4 Test results (23 passed; 8 run without the game, 15 more with `VF2_VANILLA_RUNTIME_DIR` + VS x86)
- The site header is regenerated byte-identical, and the stub decodes to the intended loader. Every absolute write lands in `.vf2fud`, every call/jmp stays in the stub, goes through the two IAT slots or `eax`, or is the final `jmp 0x428620`. There is no `LoadLibraryA`.
- gen_sites proves every pin and refuses a corrupted byte, a split instruction or a relative steal.
- The patched exe differs from vanilla only in NumberOfSections, SizeOfImage, CheckSum, the two new section headers, the Init slot and the appended sections. No existing section header changed. Our checksum reproduces vanilla's stored value, and on the patched file Windows' `MapFileAndCheckSumW` agrees with the stored checksum.
- **Harness** (`runtime/tests/stage1_harness.cpp`, 32-bit): the patched image is copied to `0x400000` as data, so the game never starts and no loader or CRT runs. The harness calls theGame's slot 4 exactly as `0x42AFF8` does. Results:
  - The real stub loads the real DLL from the full path, Init is reached once with the right `this`, and a missing DLL leaves the stock game.
  - Off: nothing is written.
  - On: all six writes are present, all game pages are back to RX, the trampoline page is RX and outside the DLL, and **no page in the process is writable and executable**.
  - Young couples (both < 1000), with the tutorial shown and not shown: results, RNG limit and tutorial queue are identical with and without the hook. This is the stock body running through the stolen-prologue trampoline.
  - Older couples (1,890 cases over ages 50–80, three fertilities and ten RNG values): every result equals a Python model of B200's `VF2RollOlderPregnancy`. GetRandom is called with 1000, and the tutorial 0x868 is queued only on success.
  - Cooldown store: written for 600/600 and 999/999, skipped for 1000/600, 600/1000 and 1400/1400. Off, it is always written. All registers, the arithmetic flags and ESP are preserved.
  - Next Generation through each of the four retargeted call sites: stock-eligible yes; no child no; dead child no; oldest 59 no; oldest 60 yes; departed or dead elder no; force yes. Off, everything is stock.
  - The probe reads all of this from a held harness process.
- **Two-way validation:** four single-point mutations of the DLL were each caught by the intended test: the late-age threshold `>=1000` changed to `>1000`; the cooldown mother-age offset `esi-0A0h` changed to `esi-9Ch`; the trampoline resuming one byte early; and the Next Generation age changed from 60 to 59.

### 9.5 Equivalence with the static B200 build, and where it is conditional
- **Setting off = B200 with `.vf2preg` 00 = stock.** B200's dormant hooks replicate stock exactly; the runtime build installs nothing.
- **Setting on** gives the same decisions as B200's cave and helpers (port verified by text comparison and the harness model), under two conditions that always hold in the vanilla game:
  1. B200's cooldown helper first returns early for a same-sex marriage or an opposite-sex six-child couple under Behavior Patches. Vanilla can create neither: there is no same-sex candidate, and the six-child predicate is compiled out without Behavior Patches. The DLL treats both as false. If a later module adds same-sex marriage, those predicates must move into a shared module (§11 S6).
  2. In B200, ProcessCurrentPlan reaches ChanceOfPregnancy through `VF2ChanceOfPregnancyForced` (the Cheat Upgrades one-shot). Without an armed one-shot, which vanilla cannot have, that is a plain call.
- B200's "stock" functions come from the relinked object code, whose code generation differs from vanilla's (e.g. a frame-pointer prologue). Where the semantics were compared (ChanceOfPregnancy, CanStartNextGeneration, CountSurvivingChildren) they agree. The runtime build always runs vanilla's own stock code.
- Observation, not changed: B200's rule caps a young mother with a 50+ father at the older-parent curve (10% at 50), where stock gives about 70%. The manifest documents this as intended ("capped by older-parent curve"). The owner may want to confirm it.

### 9.6 Open risks
1. **Not yet live-tested.** The harness runs the real stub, DLL and stock code, but not the real loader, CRT, threads or AV environment. §10 must pass first.
2. **Install timing:** hooks are written during the first call of theGame::Init, before the game loop. Another thread executing ChanceOfPregnancy, ProcessCurrentPlan or the scene code at that moment is not plausible (the scenes do not exist yet), but it is not proved live.
3. **Anti-virus heuristics:** VirtualProtect on .text plus an executable allocated page is the classic pattern (§7). VF1's identical loader has not been flagged (owner's experience), but VF2 has not been checked.
4. **Composition:** Stage 1 is one module. A second module touching the same bytes would fail its pin check and install nothing (fail-safe, not composed). Composing several modules needs the shared registry from §5 inside one DLL, or a host DLL that owns all writes (§11 S0).
5. **Diagnostic counters** (`VF2Fun_Status`) exist for the live test. Per the no-debug-in-shipped-builds rule, decide before shipping whether they stay as a status block or go.
6. **DEP:** vanilla's DllCharacteristics is 0 (no NX opt-in). The design never needs W+X, so DEP being on or off changes nothing; this is noted only for completeness.

---

## 10. Stage 1 live-test script (for the main session; one live test at a time)

**Build under test:** `C:\vf2w\vf2-runtime-stage1-test\VF2 Runtime Test.exe`. Its saves go to the new folder `Documents\LDW\VF2 Runtime Test\`, never the owner's. It runs windowed (`ldw.ini FullScreen=0`), and the setting is in `Virtual Families 2 Patcher Files\vf2fun.ini`. Run the probe from `C:\vf2w\wt-runtime`: `python runtime\tools\probe_stage1.py --exe-name "VF2 Runtime Test.exe"` (add `--watch 2 --count 30` to poll). Pause with Space before grabbing any villager.

**A. Load and install (proves bootstrap, full-path load and runtime install).**
1. Launch the test exe and reach the main scene of a new family.
2. Probe → expect `stub: state 'DLL loaded'` with dll_path ending `\Virtual Families 2 Patcher Files\vf2fun.dll`. Every site should show `jmp`/`call` to an address in the DLL, not "vanilla". Status should read `allowOlderPregnancies=1`, `pinsMatched=1`, `installedMask=63`, trampoline non-zero.
3. `vf2fun.log` beside the DLL should say "Allow Older Pregnancies installed". Within a few seconds on the main scene, `nextGenerationCalls` should climb: theMainScene::UpdateScene polls it every frame, which proves the call-site retarget is live.
   *Fail = stub state 2, "vanilla" sites, or a crash at start-up. Stop and report the log.*

**B. Married couple.** Accept the stock marriage proposal (email path EEmailMessage 2) for the first adult. Probe → two active adults, one female and one male. Note their slot indices.

**C. 50+ couple: the late-age roll and the skipped cooldown (B200 behaviour).**
1. `probe_stage1.py --exe-name "VF2 Runtime Test.exe" --set-age <wife> 50`, then the same for `<husband>`. Fifty exactly gives the highest late-age chance: 10% at fertility 50 (cap 100 tenths). At 55 with fertility 50 the stock age penalty already brings it down to the 0.1% floor.
2. Pause, drag one spouse onto the other, unpause. They try for a baby (behaviours 0x165/0x164).
3. Probe → `chanceCalls` +1, `olderRolls` +1, `lastMotherAge`/`lastFatherAge` = 1000.
   - **Failed roll (about 90%):** `cooldownSkips` +1, `cooldownStores` unchanged, and `try_for_baby.seconds_remaining` stays 0 (no new 1200 s deadline). **Dropping them together again immediately is accepted, not refused.** B200 does exactly this for a 50+ couple.
   - **Successful roll:** `olderSuccesses` +1, the pregnancy starts, and the pregnancy tutorial tip appears if it has not been shown before.
4. Repeat step 2 until one roll succeeds (about 10% each). Retries need no waiting.

**D. Control: under 50 (stock path through the trampoline).**
1. Set both to 49. Drop them together.
2. Probe → `chanceCalls` +1, `olderRolls` unchanged (the stock body ran via the trampoline). On a failed roll: `cooldownStores` +1, `seconds_remaining` about 1200, and an immediate re-drop is **refused** (the couple refuses with behaviour 0x175, as stock). On success, the normal stock pregnancy.

**E. Next Generation at 60 (needs one surviving child, e.g. from C or D after the birth).**
1. With the stock rule not yet met, set the oldest adult to 59. The Next Generation flow stays unavailable and `nextGenerationOlderGrants` does not rise.
2. Set that adult to 60. Next Generation becomes available (Family Tree screen and villager-details button, the same four call sites as B200), and `nextGenerationOlderGrants` starts rising.

**F. Off = stock.**
1. Quit cleanly, set `AllowOlderPregnancies=0` in `vf2fun.ini` and relaunch.
2. Probe → every site "vanilla (not installed)", `allowOlderPregnancies=0`, `installedMask=0`.
3. With both spouses at 50, they never conceive, and every failed attempt sets about 1200 s of cooldown with refusal on re-drop. At 60, Next Generation stays unavailable.

**G. Save/reload.** Quit cleanly with a pregnancy or child in progress, relaunch and confirm the family loads. The setting is not in the save (in B200 it lives in the executable, here in the ini), so no save-format change is expected.

**Pass = A–G as stated.** Behaviour then matches B200's documented Allow Older Pregnancies: stock under 50; the older-parent cap; 50+ failed attempts skip the 1200 s cooldown; Next Generation at 60 with a surviving child; off is stock. The decision-level identity is already proved by the harness (§9.4). The live run proves the same code runs inside the real game. **Optional A/B:** repeat C–E in a B200 playtest build with `.vf2preg` = 01. The probe does not work there (different addresses), so compare the visible behaviour only.

## 11. Complete, ordered conversion plan
*(See below.)*
