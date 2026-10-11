# VF2 patcher: feasibility of moving from a static-relink matrix to VV-style runtime-hook modules

**Feasibility study — no shipping code changed.** All findings re-derived from the repo at `C:\vf2w\vf2`. The only code written for this study is a throwaway proof-of-concept (`poc/`, next to this report; not in the VF2 repo), which exists solely to substantiate §5.

> **Update 2026-10-10 (Stage 1, branch `runtime-hook-stage1`).** Stage 1 has been built on the real vanilla binary: see **§9** (what was built and proved), **§10** (the live-test script, still to be run) and **§11** (the complete, ordered conversion plan for every patch). Two parts of the original text are superseded and marked in place: the proxy-DLL loading model (§8.2, rejected by the owner; replaced by a loader stub in its own section) and §5's open question about stealing a real `/O2` prologue (now proved statically and in a harness; live confirmation pending). The owner's rule since this update: **companion DLLs over cave space unless absolutely necessary** — the executable gets only the loader stub and the single vtable slot that reaches it. **Stage 3** (branch `runtime-hook-stage1`) added the first module with no B200 counterpart, the Virtual Families 1 patcher's Time Controls dialog: see **§13**. **Stage 3 shared-table experiment** (branch `runtime-id-reservation`): can the achievement / string / image / item tables become runtime modules by reserving ID ranges? **Partly yes, proved for achievement rows, their screen order, string ids and the save; see §14** (verdict, cascade map, reservation design, per-patch table, live-test checklist).

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

Rule (owner): **DLLs over cave space unless absolutely necessary.** The executable keeps only the Stage 1 loader stub (`.vf2fun`/`.vf2fud`) and the one Init vtable slot. Everything else is a module in `vf2fun.dll`. A patch converts only when its equivalence to released B200 is proved against the pinned vanilla bytes and the B200 generator source. Anything doubtful stays static and is listed here with the reason.

### 11.1 S0: the host registry (done, commit `3a5570a`)
- **One install path owns every write** (`InstallAll` → `Apply` → `WriteCode` in `vf2fun.cpp`). It reads each module's `[Patches]` key from `vf2fun.ini` (1 = on; anything else or a missing key = off = stock). It checks the core pins, then every pin of the module. It builds trampolines in one private page that is RW while it is filled and RX before any game byte changes. It installs each module all or nothing: a failed write puts back every write of that module, and the other modules are unaffected. A runtime overlap check refuses a write that touches another module's bytes; `gen_sites` refuses overlapping pins at build time too.
- **Sites:** `vf2_runtime_sites.py` holds `MODULES` (key, ini key, B200 feature, B200 default) and tags every `Pin` with its module (or `core`). `gen_sites.py` proves every pin with capstone. Retargets name their target (call or jmp), `replace` runs may span whole instructions, and `EXCLUSIVE_CALLERS` / `NO_ABSOLUTE_REFERENCES` are checked for every listed function. The generated header carries the module table.
- **Status block:** `VF2Fun_Status` is the documented install-status block (layout v2: requested, pins-ok, installed and refused masks, the trampoline page, and per-module write masks). It is written only by the install path. The per-call counters moved to `VF2Fun_TestCounters`, compiled only with `/DVF2FUN_TEST_COUNTERS`. `native/build.bat` (the release build) never sets that flag, and a test builds the release DLL and checks the export is absent.
- **Settings:** the patcher writes every module key explicitly. The defaults are each feature's state in a default B200 build; `--set KEY=0|1` overrides one.
- Allow Older Pregnancies moved onto the registry unchanged. All 23 Stage 1 tests still pass.

### 11.2 Per-patch table (every `patch_*` in `work/patch_mobile_furniture_pack.py`)
**Converted** = a runtime module, harness-proved, with a mutation confirmed caught. **Pending** = table-free and convertible in principle, but not done or not proved this round. **Static** = must stay in the static build for the reason given. **n/a** = generator plumbing, not a feature. The 55 **Static** rows below are re-assessed in §14.6 after the ID-reservation experiment.

| B200 patch | State | Module / reason |
|---|---|---|
| allow_older_pregnancies, next_generation_age_gate | **Converted** (Stage 1, moved onto S0) | `older_pregnancies`, key `AllowOlderPregnancies` (B200 default off) |
| ldwscene_setactive_null_guard | **Converted** (`3a5570a`) | `scene_null_guard`, key `SceneSetActiveNullGuard` (unconditional in B200 → default 1). Vanilla `ldwScene::SetActive` 0x40D1D0, 59 callers. The stub keeps the `test bl,bl` flags and returns through vanilla's own epilogue. |
| options_pause_yes_idempotent | **Converted** (`481a641`) | `fix_vanilla_bugs`, key `FixVanillaGameBugs` (default 1). Add at 0x4226A6 in theOptionsDialog::HandleMouse. |
| title_menu_stale_hotspot | **Converted** (`481a641`) | `fix_vanilla_bugs`. Top store at 0x44337B in the theMenuScene constructor; the inclusive readers are pinned. |
| title_menu_start_over_confirms | **Converted** (Stage 4) | `fix_vanilla_bugs`. `je` rel32 at 0x443F5C in theMenuScene::HandleMessage retargeted to a DLL stub (new jcc retarget role). ShowMessageBox 0x421410, theGameState::Init 0x429DD0 and SaveCurrentGame 0x429660 located and proved (the Options dialog Evict confirmation and the new-player name dialog make the same calls). |
| title_menu_refresh_on_activate | **Converted** (Stage 4) | `fix_vanilla_bugs`. UpdateShowPlayer 0x443B80 entry detour (label), Manage Games re-add at 0x443C00, Activate(true) tail call 0x443A07, name-prompt-cancel call 0x444073. **`FixVanillaGameBugs=1` is now the whole B200 setting (7 writes).** |
| fix_vanilla_game_bugs | n/a | Umbrella that calls the four fixes above. |
| career_room_goal_reconciliation | **Converted** (`17541be`) | `career_room_goals`, key `CareerRoomGoalReconciliation` (unconditional → 1). Load hook only: CTech::LoadState call 0x42A75E. B200's second call, after Cheat Upgrades' Reset Achievements, belongs to Cheat Upgrades (static). |
| event_collectable_slot_replacement | **Converted** (Stage 4) | `event_collectable_slot_replacement`, key `EventCollectableSlotReplacement` (unconditional in B200, default 1). Three call retargets to 0x415090 (Bug Whisperer x2, Neighbor Collectible); Update's natural spawn left alone. The fossil site stays with the static island events. |
| options_dialog | Pending (deferred, convertible) | Evict button: B200 NOPs a 6-byte and a 2-byte conditional branch in the constructor and inserts an AddControl call. The framework's minimum write is 5 bytes, so it needs a new "byte patch" write class, and the dormant block is stock developer-disabled UI that only a live look can vouch for. Not done; no equivalence proof attempted. |
| power_failure_event | **Converted** (Stage 4) | `power_failure_event`, key `PowerFailureEvent` (default 1; B200 installs it in island-event builds, on by default). String 0x9BE **is** in the vanilla table (record at 0x548060; the string manager constructor indexes all ids). Three vtable slots of CEventThePowerFailure replaced (new vtable_slot role, RTTI-proved). B200 drops the stock SetProp(0x17) on "Take a chance"; the module reproduces B200. |
| older_villager_mortality | **Converted** (Stage 4, mortality half) | `older_villager_mortality`, key `OlderVillagerMortality` (default 0). Replace run of `push 0; mov ecx,ebp; call FoodGroupsActive` at 0x49BBBD; the stock statement 0x49BBC6..0x49BC46 is proved single-entry/single-exit (exit 0x49BC47). Hazard table generated from B200's formula. The longevity achievement observer stays static. |
| (none in B200: new in the runtime build) | **Converted** (Stage 3) | `time_controls`, key `TimeControls` (default off). Time Controls dialog from the store screen, see §13. |
| mobile_table_prop_draw, mobile_table_prop_paint, mobile_patio_prop_execution | **Static** | They draw and paint props for B200-added mobile furniture (picnic table, patio), whose item and image IDs come from the shared append cascade (§4). |
| mobile_sound_routes | **Static** | Added sound assets and IDs. |
| holiday_body_draw_redirect, collectable_item_holiday_ornaments, collectable_holiday_ornament_observers, collection_scene_holiday_ornaments, the_collector_holiday_ornaments | **Static** | Holiday image/ID tables and `achievementOrder` (§4, §8.3 Stage 3). |
| furniture_manager, inventory_manager, visible_special_upgrades, house_renovations, scrolling_store_scene, purchase_dialog, special_upgrade_titles, string_manager, graphics_manager, floating_anim_table, added_furniture_click_aliases, added_furniture_venue_callsites, invisible_hammock_drop_action, invisible_furniture_parity, second_bathroom_leaks, bathroom1_curtain_decal, mobile_renovation_renderer | **Static** | They grow or index the shared furniture, inventory, string and image tables, or draw B200-added items (§4). |
| island_events | **Static** | Added events, strings and images (matrix toggle; needs the Stage 3 table protocol). |
| custom_achievement_draw_bounds, custom_achievements, achiever_load_reconciliation, pet_achievement_callsites, family_tree_appearance_achievement_callsites, maximum_resource_achievement_callsites, longevity_achievement_load_reconciliation, lifetime_generation_counter, new_village_clears_patcher_achievement_state | **Static** | Custom achievements: the `achievementOrder` table and B200-only bytes in achievement record 0xA8 (save data). |
| same_sex_marriage, villager_same_sex_embrace, same_sex_pregnancy_guard, villager_manager_spouse_accessors, marriage_finalization_for_same_sex, villager_details_same_sex_married_status, embrace_role_split | **Static** | The on/off state is a persisted inventory byte that exists only because Cheat Upgrades grows the inventory table (§9.1). |
| force_successful_pregnancy_callsites, force_pregnancy_skips_refusals | **Static** | Cheat Upgrades one-shot (inventory and string tables). |
| six_child_private_time, spontaneous_behaviors, bookshelf_reading_behavior, radio_drop_behavior, behavior_label_variants, arcade_behavior_labels, mobile_furniture_behavior_dispatch, mobile_furniture_behavior_macros, mobile_furniture_autonomous_candidates, mobile_furniture_external_autonomous_selection | **Static** for now | Behavior Patches and mobile-furniture behaviour: labels use the string cascade, and the dispatch tables index added furniture. The macro-table part is §8.3 Stage 2's candidate, not yet proved table-free. |
| multiple_marriage_candidates | **Static** | "Cheat upgrades only" (its own manifest scope); reroll branch lives in the Cheat Upgrades inventory. |
| marriage_candidate_reroll | **Static** | Its on/off state is the persisted inventory byte InventoryManager+0x152+0x2A3, which exists only because Cheat Upgrades grows the inventory table. |
| vf3_style_child_adoption_chooser | **Never installed in B200** | The call is commented out in B200's build list (line 41678); nothing to match. |
| tool_tray_outfit_normalization | **Static** | Normalises the B200 outfit store's synthetic tray item ids (the shared item-id cascade) back to stock ids. |
| main_scene_outfit_body_apply | **Static** (and disabled in B200) | Same synthetic ids; B200 records it as "disabled for B97 stability" and does not call it. |
| main_scene_random_tip_click | **Static** | Needs the mobile click sound asset (new sound id) and the house region baked into the modified main_BG_ws image 0x174. |
| debug_features, plan_logging | **Never ported** | Debug-only: must not ship (owner rule). |
| all, all_in_sections, section_near_jump, count_sites | n/a | Generator plumbing. |

### 11.3 Order for the next round (steps 1-4 done in Stage 4, section 14; options_dialog deferred)
1. Finish `fix_vanilla_bugs` (start_over_confirms, refresh_on_activate). The setting is only B200-complete once these land.
2. older_villager_mortality (DLL hazard table, mortality half).
3. event_collectable_slot_replacement (native sites), power_failure_event (after the 0x9BE string check), options_dialog.
4. Assess the "not assessed" rows.
5. Stage 2/3 of §8.3 for the table-coupled rows. (Stage 3's table protocol is §14: achievements and strings proved, images designed, items not attempted.)

## 12. Stage 2 live-test checklist (main session; one live test at a time)
**Build:** `C:\vf2w\vf2-runtime-stage2-test\VF2 Runtime Stage2 Test.exe`. The exe is byte-identical to the Stage 1 test exe (SHA-256 `04f9ff02…1b28e`): the bootstrap did not change. `Virtual Families 2 Patcher Files\vf2fun.dll` is a **test build** (`/DVF2FUN_TEST_COUNTERS`, SHA-256 `c58b420a…ce1280`). `vf2fun.ini` turns every module on, and `ldw.ini` has FullScreen=0. Saves go to `Documents\LDW\VF2 Runtime Stage2 Test\`. Probe from `C:\vf2w\wt-runtime`: `python runtime\tools\probe_stage1.py --exe-name "VF2 Runtime Stage2 Test.exe"`.

- **A. Install.** Launch and reach the title screen. Probe: stub `DLL loaded`, and the modules `older_pregnancies`, `scene_null_guard`, `fix_vanilla_bugs` and `career_room_goals` are all `installed`, none `REFUSED`. Every written site shows `jmp`/`call` into the DLL. `vf2fun.log` lists four "installed" lines.
- **B. Title hotspot.** On the title screen, click empty space where Manage Games first sat (the old rect: x 326–516 plus the widescreen offset, y 249–279), then hover there. Expect no Change Player dialog and no hover sound. The real Manage Games button (centre, lower) still works.
- **C. Pause Yes.** In a family, open Settings and press Pause Game: Yes **twice** (pause is already on the second time), close Settings, then press Space once. Expect the game to resume on that single Space. Stock needed two.
- **D. Career-room goals.** Load a family that owns career upgrades (or buy one, quit cleanly, relaunch). After load, the Achievements screen's kitchen/office/workshop goals show the owned count (all owned = complete). Counters are not exposed for this module; judge by the screen.
- **E. SetActive guard.** Reach six children in one family (the stock crash point B200 recorded). Expect no crash when the six-child scene event fires. `sceneNullSkips` in the probe's test counters rises if the null slot is hit; `sceneActiveWrites` rises on every scene change.
- **F. Allow Older Pregnancies.** Repeat §10 C–E with this build (same expectations).
- **G. Off = stock.** Quit cleanly, set every key in `vf2fun.ini` to 0, relaunch. Probe: every module `off` and every site vanilla. The hotspot opens Change Player again, and Yes twice then Space stays paused.
- **H. Save/reload.** Quit cleanly and relaunch; the family loads. No module writes save data of its own. Career goals and pause state are stock fields that B200 writes the same way.


## 13. Stage 3: Time Controls (new module `time_controls`, key `TimeControls`)

The Virtual Families 1 patcher's Time Controls dialog, rebuilt for the vanilla Virtual Families 2 as a registry module in `vf2fun.dll` (code in `runtime/native/vf2fun/vf2fun_time.inc`; pins in `runtime/vf2_runtime_sites.py`; header regenerated by `gen_sites.py`). Nothing is added to the executable: it still carries only the Stage 1 loader stub. B200 has no equivalent, so the module has no static counterpart to match; the references are the vanilla game's own code. Default: **off** (the patcher writes `TimeControls=0` unless asked).

### 13.1 What it does
A **Time** button appears on the store screen, in the next slot to the right of Done and Back (same art and font as they use). It opens a Windows dialog titled **Time Controls**, laid out and worded like the VF1 one: a status line (`Running. Speed: normal.` / `Paused. Speed: 2x. A time warp is under way.`), **Pause**, **Resume**, **Normal / 2x / 5x / 10x**, one **Time Warp: +3 years** (with a Yes/No question: *Everyone at home ages at once, with every normal rule: birthdays, leaving home, and old age. Continue?*) and **Close**. The game leaves fullscreen while the dialog is open and returns to it afterwards (the game's own SDL2, as VF1).

### 13.2 Research: what VF2 has (all addresses pinned and capstone-proved against the vanilla executable)
| Fact | Evidence |
|---|---|
| Game-time object `CGameTime` `GameTime` at `0x568088`; `SetSpeed(int)` at `0x427A50` (thiscall, ret 4). Speed 10 = normal; `Seconds` = base + realElapsed / (speed / 10), so 5 = 2x, 2 = 5x, 1 = 10x. | Whole function pinned (`set_speed`); matches `GameTime.obj` (`SetSpeed`, `SpeedMultiplier` = field/10, `Seconds`). |
| `SetSpeed(999)` is **pause**: it pauses the registered timers and stores **0** (`IsPaused` = multiplier 0). Any other value rescales the timers and stores itself; an unchanged speed returns at once. | Same function; the harness runs it and reads game speed 0 after a pause. |
| The same speed is kept in `theGameState` (pointer at `0x558FC0`) at `+0x25B18`. The aging code divides by it. Paused = field >= 999 (it holds speed + 999). | 35 readers of `+0x25B18` were read; none treats non-paused values specially except as divisor/threshold (5, 10, 20 select catch-up caps). |
| The **Space key** (theMainScene::HandleMessage `0x43BC2D`) is the pause toggle: field >= 999 -> `SetSpeed(field - 999)`, field = that (10 if 0); else `SetSpeed(999)`, field += 999. Options "Pause Game" Yes/No (`0x42269B`/`0x4226EA`) are the only other `SetSpeed` callers. | Pinned (`space_pause_toggle`). The dialog's Pause and Resume do exactly this. |
| **Speed buttons** have no stock UI in VF2 (the game only ever sets 10, or 999). Values 5, 2 and 1 are legal: the aging code and `CGameTime` are generic in the divisor, and the aging catch-up caps already name 5, 10 and 20. | Not a new mechanic, just values the stock code already handles. |
| **Aging**: `AllVillagersTimeflowUpkeep(bool)` `0x499700` (from `theRealtimeManager::UpdateAll 0x42ACB0`, called by `theMainScene::UpdateScene` each frame, and once from `0x432A46`) turns each villager's real seconds into ticks = accumulator / 60 / speed and calls `CVillagerBio::IncrementAge` (`0x498B40`, which only does `add [ecx],eax`) at `0x499898`. The leaving-home check at 19 years (380 ticks), the oldest-age record (`GameStats+0x20`) and the accumulator remainder (`speed * ticks * 60`, from the NATIVE ticks in `ebx`) run after it in the same function. | Pinned (`timeflow_ticks`, `increment_age`). **20 ticks = 1 year** (the pregnancy code divides the age by 20; 380 = 19 years), so +3 years = 60 ticks. |
| Old age is not tick-edge based: it is a per-frame health roll (`IsNotOld`, `AdjustHealth`), so a lump of 60 ticks skips no roll. | `AllVillagersRealtimePhysiologyAndProductivityUpkeep` read in `VillagerManager.obj`. |

**What VF2 lacks (skipped):** no speed UI or setting exists (so the speed buttons are values for the field rather than a mapped feature); the dialog does not keep a speed of its own, because the game saves the field itself. The VF1 per-frame speed re-apply (`FeaturesTick`) is not needed and not ported: nothing in VF2 resets a non-paused speed except a new village and the Options dialog's "No" (both set 10, which is the stock behaviour the player asked for).

### 13.3 Entry point (decision)
**A button on the store screen**, the VF1 way. The store (`CScrollingStoreScene`, RTTI `.?AVCScrollingStoreScene@@`, vtable `0x4E2E44`) has a Done button (id 1), Back (id 3) and the Bank hit-area (id 2) built in its constructor `0x432F10`; its handler (`HandleMessage`, slot 3, `0x4322B0`) knows only ids 1 to 3. Why this and not a hotkey or the main scene: it is the same flow the owner already uses in VF1; it needs exactly two hooks that are already proven shapes (one call retarget, one function-entry detour); a modal dialog from the store cannot interrupt a villager drag or a main-scene click; and the store is not the main scene, so no frame of main-scene drawing is waiting on the dialog. The button is `btn_orange.png` (image `0x129`, the art of Done and Back), at widescreen offset + `0x164`, y `0x2DD`, id `0x5646`, label **Time** (short on purpose: the button art is 145 px wide and the label has not been seen in the game yet).

### 13.4 Sites (module `time_controls`; three writes, all in `Apply` all-or-nothing)
| Write | Role | Where |
|---|---|---|
| `0x4332A5` `call SetStoreCategory(2)` (last act of the store constructor) | retarget -> wrapper (makes the same call, then adds the button with the store's own sequence: operator new, GetImageGrid, ldwButton ctor, SetText, AddControl) | pin `store_ctor_category_call`; whole constructor pinned (`store_ctor`) |
| `0x4322B0` `CScrollingStoreScene::HandleMessage` entry | detour (7 stolen bytes `push -1; push 4DBC8Bh`, trampoline resumes at `0x4322B7`): message 8 with id `0x5646` opens the dialog; everything else goes to the game | pins `store_handle_message_entry`, `store_handle_message` |
| `0x499893` `mov ecx,edi; mov ebx,eax; push ebx` (5 bytes) | replace -> `WarpStub`: `ebx` keeps the native ticks, the pushed value is native + queued warp ticks, then jumps to the `call IncrementAge` at `0x499898` | pins `timeflow_ticks_site`, `timeflow_ticks` |

The warp is queued per villager (active, at home, health > 0) and consumed on that villager's next pass through the aging function (the main scene runs it each frame, so the ticks land as soon as the player is back in the village). A villager who dies or leaves before their turn is dropped. Nothing writes an age directly.

### 13.5 Tests (harness style, 51 passed in total)
`tests/test_runtime_hooks_stage1.py` section `time_controls`: pins proved; the module's game calls are the ones the stock constructor makes; the store handler is vtable slot 3 of the RTTI-named class; the Space handler and aging site decoded and compared with the module's model; the three writes present, RX, no W+X page; the real `CGameTime::SetSpeed` driven through 14 pause/resume/speed operations and compared with a model (paused stores speed 0; paused speed changes ride in the field; the exactly-999 edge resumes at 10); the real `AllVillagersTimeflowUpkeep` with a synthetic roster (adult, child, left home, inactive, dead, a child about to turn 19): warp ticks land exactly once on the right villagers, the accumulator remainder keeps the NATIVE ticks, the oldest-age record updates, and leaving home still runs; the constructor wrapper (button id, image, position, text, colours, font, added to the scene after SetStoreCategory); the handler detour (unknown ids and other messages reach the stock body with identical results); and the REAL dialog driven from a second thread (title, nine controls, every button's status text, the Yes/No question and its two answers). Off: nothing written, every scenario stock. Release build: no test exports (`VF2Fun_TestTime`, `VF2Fun_TestShowTime`) and no counters.

Mutation checks (each single change made, the intended tests failed, change reverted): (1) dropping `mov ebx,eax` in the warp stub (the accumulator remainder then uses the warped ticks): the warp-ages test; (2) the dialog's warp of 3 years changed to 2: the dialog script test (the first mutation run did NOT catch this, which is why the harness now consumes the dialog's Yes with a real aging pass and checks +60); (3) Resume restoring `field - 999 + 1`: the speed-model test; (4) the button one pixel off its slot: the constructor-wrapper test; (5) the click test inverted (`!=`): the handler test (the first run hung on an unexpected modal dialog, so the harness now has a watcher that closes and reports it); (6) a paused speed change that forgets the paused offset: the speed-model test; (7) health `> 0` loosened to `>= 0` so the dead get the warp: the warp-ages test; (8) the handled click also passed to the game: the handler test. Each change was made alone, the named test failed, and the change was reverted (`git status` clean).

### 13.6 Stage 3 live-test checklist (main session; one live test at a time)
**Build:** `C:\vf2w\vf2-runtime-stage3-test\VF2 Runtime Stage3 Test.exe`. The executable is byte-identical to the Stage 1 and 2 test exes (SHA-256 `04f9ff02...1b28e`): the bootstrap did not change. `Virtual Families 2 Patcher Files\vf2fun.dll` is a **test build** (`/DVF2FUN_TEST_COUNTERS`), `vf2fun.ini` has every module on including `TimeControls=1`, `ldw.ini` FullScreen=0. Saves go to `Documents\LDW\VF2 Runtime Stage3 Test\`. Probe: `python runtime\tools\probe_stage1.py --exe-name "VF2 Runtime Stage3 Test.exe"`.

- **A. Install.** Launch, reach a family. Probe: module `time_controls` `installed`, none `REFUSED`; sites `store_ctor_category_call`, `store_handle_message_entry`, `timeflow_ticks_site` show `call`/`jmp` into the DLL.
- **B. Button.** Open the store (the Store button on the main screen). Expect a new **Time** button in the bottom-left row, right of Done and Back, in the same orange art with white text that fits. Probe counter `timeButtonsAdded` = 1. *If the label overflows or the button overlaps something, report a screenshot: only `kTimeButtonText` / the X offset change.*
- **C. Dialog.** Click it. Expect a dialog **Time Controls** (centred, game goes windowed if it was fullscreen) with the status line `Running. Speed: normal.`, Pause / Resume, Normal 2x 5x 10x, **Time Warp: +3 years**, Close. Counter `timeDialogOpens` = 1. Close (Escape or Close): the store works as before, Done and Back still work.
- **D. Pause.** Pause: status `Paused. Speed: normal.`. Close the dialog and look at the village: nothing moves/ages, the game shows its normal paused state (same as Space). Press **Space** once: it must resume (stock Space), and reopening the dialog shows `Running.` Then Pause from the dialog and Resume from the dialog: villagers move again.
- **E. Speed.** 2x: villagers walk and the day/night clock run about twice as fast; 5x and 10x faster again; Normal returns. Speed while paused: Pause, 5x (status `Paused. Speed: 5x.`), Resume (status `Running. Speed: 5x.`). Probe `speed field` shows 5 running or 1004 paused. Quit cleanly at 5x and relaunch: the game keeps 5x (its own save holds it); the dialog shows it; Normal restores. (Options "Pause Game: No" also returns to normal, as stock.)
- **F. Time Warp.** Note villager ages (Details). Dialog, Time Warp, **No**: nothing happens. Time Warp, **Yes**: status gains ` A time warp is under way.` Close the dialog and the store: within a second everyone at home is 3 years older (a child that crosses 19 leaves home as usual); the oldest-ever record updates in the Family Tree/Achievements. Warping again works. Probe counter `timeWarpsApplied` = number of villagers aged.
- **G. Off = stock.** Quit cleanly, set `TimeControls=0` in `vf2fun.ini`, relaunch: no Time button, the store works, probe shows the module off and its three sites vanilla.
- **H. Save/reload.** Quit cleanly and relaunch: the family loads. The module writes no save data of its own (only the speed field the game itself saves).


## 14. Stage 4: the rest of the table-free rows

Branch `runtime-hook-stage1`, commits `338f807` (fix_vanilla_bugs complete), `bd00e4d` (older_villager_mortality), `5621359` (event_collectable_slot_replacement), `2b9fe3a` (power_failure_event). Every conversion follows the same bar: pins located structurally in the vanilla image and proved by capstone (`gen_sites.py`), the DLL's logic compared with B200's generator source (text comparison of ported helpers or byte comparison of the stubs), a harness test that runs the real stock code against recorders and a model written from B200, and one deliberate single-point mutation confirmed caught and reverted.

### 14.1 What was added to the framework
- **jcc retarget** (a `je/jne rel32` pointed at a DLL stub), **replace-run ending in a pinned call** (the DLL re-issues the call itself), **vtable_slot** (a 4-byte data pointer, written under PAGE_READWRITE, never executable; RTTI of the vtable proved), **data** pins (table records and texts) and **SINGLE_ENTRY_REGIONS** (a stock statement the module skips whole is proved single-entry with every exit at one address).
- The branch-target scan is deliberately over-approximate. Where it reports a "branch" inside another instruction's displacement, `NOT_INSTRUCTION_STARTS` waives it only after a linear decode from the function start proves the address is inside an instruction.

### 14.2 Results
| Module | Writes | Evidence |
|---|---|---|
| `fix_vanilla_bugs` (complete) | 7 | 10 Start Over/Play click cases, name prompt OK/cancel, 16 UpdateShowPlayer states and Activate through the real stock menu code; Start Over Yes keeps the 24 name bytes through Init and clamps the speed field like the new-player dialog. |
| `older_villager_mortality` | 1 | The stock statement run for every birthday 0-330 years x 0-5 food groups plus off-birthday ages; the kill threshold is found by binary search and equals B200's table (on) or 10 x years over (off). |
| `event_collectable_slot_replacement` | 3 | 468 slot configurations (burst protection, stale burst, forced random path, native spawn giving up) replayed against an independent model of B200's policy; Update's natural spawn untouched. |
| `power_failure_event` | 3 | The real virtuals driven through the vtable (stock and replaced), including five events at once (four-slot overflow). |

Tests: 109 pass (`VF2_VANILLA_RUNTIME_DIR` + VS x86), the Stage 1-3 tests unchanged. Mutations caught and reverted: Start Over `jne`->`je`; Manage Games button field 0xE4->0xF0; hazard index -55->-56; mortality `jz`->`jnz`; collectable victim `<`->`>`; collectable restore condition; Power Failure `==0`->`==1`.

### 14.3 Observations (not changed)
- B200's Power Failure replacement drops the stock `SetProp(0x17)` (spoiled-food prop) for "Take a chance"; stock set it for both choices. Reproduced as B200 does.
- B200's mortality clamps food groups at 4; the stock statement allows 5.

### 14.4 Conversion state
80 `patch_*` functions in the B200 generator. Converted: 11 (allow_older_pregnancies + next_generation_age_gate counted as two, SetActive guard, pause_yes, stale_hotspot, start_over, refresh_on_activate, career_room_goals, event_collectable, power_failure, older_villager_mortality), about 14%. Of the remainder, one (options_dialog) is convertible and deferred, the rest are static for the recorded reasons (shared tables, Cheat Upgrades inventory, assets, mobile events, never installed, plumbing, debug). Time Controls is an additional new module.

### 14.5 Stage 4 live-test checklist (main session; one live test at a time)
**Build:** `C:\vf2w\vf2-runtime-stage4-test\VF2 Runtime Stage4 Test.exe` (exe SHA-256 `04f9ff02...1b28e`, unchanged bootstrap). `Virtual Families 2 Patcher Files\vf2fun.dll` is a **test build** (SHA-256 `eba5553e...170f3`); `vf2fun.ini` has every module on, `ldw.ini` FullScreen=0. Saves go to `Documents\LDW\VF2 Runtime Stage4 Test\`. Probe: `python runtime\tools\probe_stage1.py --exe-name "VF2 Runtime Stage4 Test.exe"`.
- **A. Install.** Probe: all nine modules `installed`, none `REFUSED`; vtable sites show `vtable slot -> DLL`.
- **B. Start Over.** With a village, title screen, Start Over: the confirmation appears. No keeps the menu; Yes starts a new game under the same player name (check the name on the title screen afterwards). Without a village, Start Over starts the intro as before.
- **C. Title refresh.** Delete the only player in Manage Games and cancel the name prompt: the old name and Continue are gone, Manage Games is back. Return to the title from a game: Play/Continue label is right.
- **D. Collectables.** Wait until both yard collectable spots are busy, then trigger Bug Whisperer / Neighbor Collectible (or Time Warp for the email): the event adds its collectables by replacing the oldest unpicked one; the Bug Whisperer nets two.
- **E. Power Failure.** Take a chance several times: about one in four says "Everyone gets an upset stomach. The food was not ok." and some villagers get an upset stomach; the rest say "This stuff still looks okay."; Throw it out resets the food.
- **F. Old-age mortality.** Time Warp elders past 55 (ages in years 55-90): deaths follow the gentler B200 curve (very rare at 56-60) compared with the Off build, where each year past 55 adds 10%.
- **G. Off = stock.** Set every key to 0: each behaviour above reverts and the probe shows every site vanilla.
- **H. Save/reload.** Quit cleanly and reload: no module writes save data.

### 14.6 Open risks
1. Not live-tested. 2. The harness cannot run the full stock physiology/dialog stack, so the live pass is what proves the hooks inside the real game. 3. Anti-virus heuristics as in section 9.6. 4. A transient harness stall was seen once when another process was running heavily (the next run passed); it did not reproduce.

## 15. Stage 3 experiment: can the shared ID tables become runtime modules? (branch `runtime-id-reservation`)

**Question (§4, §8.3, §11):** can fixed per-feature ID ranges be reserved so that a feature's added images / strings / achievements / items get the SAME IDs whether it is on or off, and so that the runtime DLL can register them, with no change to a saved game?

**Verdict: PARTLY FEASIBLE, and better than §4 feared.** Nothing had to be *moved*. Every shared table is read through a small, enumerable set of instructions in the vanilla file, and three of the four table families can be extended from the DLL by one of three mechanisms (retarget a displacement, replace a failure block, fill a pre-provisioned row). Proved end to end, on the real vanilla code, for **achievement rows + the Achievements screen order + string ids + the save**. Designed and evidenced but not built: images. Not attempted: furniture/inventory items and their category lists (they stay static; the evidence below says why and what it would take). No changed byte in the executable: the test exe is still byte-identical to the Stage 1 one (SHA-256 `04f9ff02…1b28e`).

Commits on `runtime-id-reservation` (from `runtime-hook-stage1`): `2b99cca` registry + pin roles, `ca56b66` harness and tests, `8f07a96` single requirement check + far-tail save case, `a96eb14` cascade-map evidence tests and probe. Tests: 75 new (`tests/test_runtime_id_reservation.py`), all 51 Stage 1–3 tests still pass (126 in total); they skip cleanly without the vanilla game or the VS x86 toolchain.

### 15.1 The cascade map (vanilla addresses; how every reader indexes each table)

"Bound" says where the table's size lives: **imm** = an immediate in code (patchable at runtime), **ptr** = a table pointer, **save** = baked into the saved game. "Readers" were found two ways that must agree: a whole-file raw byte scan (vanilla has no relocation table, so an absolute reference can only be a 4-byte value in the file) and a capstone linear sweep; `gen_sites.py` asserts the raw scan for the achievement tables, `tests/test_runtime_id_reservation.py` re-derives the rest.

| Table (vanilla) | Size / stride | What B200 does | Readers in vanilla | Bound lives in | Runtime verdict |
|---|---|---|---|---|---|
| `achievementList` `0x54BB50` | 0x5F rows × 28 B (`{id, target, icon, 0, titleStr, descStr, coins}`), 2660 B of `.data`, last row ends `0x54C5B4` | inserts rows 0x5F–0xAB (77, reserved capacity in **all 32** variants; strings always valid) | **8 instructions** in 4 functions (`PercentCompleted 0x4B4CD0`, `DrawAchievement 0x4B4D30` ×5, `IncrementProgress 0x4B5300`, `Update 0x4B5340`), each a 32-bit displacement; nothing else in the file points into it | none for the access; DrawAchievement's id guard is `cmp ebp,5Fh` imm8 ×2 (`0x4B4E05`, `0x4B4EF4`) | **PROVED**: DLL copy, 8 displacements retargeted, guards raised |
| `achievementOrder` `0x4E2AE0` | 0x5F ints (stock order: 0–0x4C, 0x5D, 0x5E, 0x4D–0x5C) | inserts 0x5F after Bottlologist (0x5E) when Holiday Ornaments is on; appends ~74 custom ids depending on Behavior Patches and a runtime byte | **one loop**, `CAchievementsScene::DrawScene 0x42CC80`, three fields: count `cmp ebp,5Fh` (imm8, `0x42CD32`), base (`lea ebp,[ebp*4+order]`, `0x42CD37`), end pointer (`cmp ebp,order+17Ch`, `0x42CD66`); the constructor `0x42C930` holds the scroll height `0x189A` (= 0x5F·0x42+0x1C) twice | imm | **PROVED**: DLL copy, 3 fields + 2 constructor immediates follow the row count |
| `CAchievement` records, global `0xAA8648` | **0x125 records × 12 B = 0xDBC, at +0**; notify queue 0x5F dwords at **+0xDBC**; popup timer +0xF38, object 0xF50 | uses record ids 0x5F–0xAB (the slots are already in the save); changes LoadState (below) | `SaveState 0x4B4C80` / `LoadState 0x4B51E0` copy exactly 0x125 records | **save**: 3,564 bytes of records | ids 0x5F–0x124 **already exist in every save**: no reservation needed, none possible beyond 0x124 (see 15.5) |
| `stringTable` `0x53DCC0` + `lookupTable` `0x56ECF0` | 0xA5D entries × 16 B; 0xA69 pointers; `0x571694` right after is the string-manager singleton | appends ids 0xA69–0xFF2 (1,418), **unconditionally reserved**, populated by toggle | `GetString 0x448E90` and the same lookup inlined in the text-draw function `0x448ED0`; the constructor `0x449300` builds the lookup (and reads `sm.xml`, absent from the game folder) | imm: `cmp …,0A67h` ×2, `0A5Dh`, `0A69h` | **PROVED**: both readers end in a failure block (`"Unknown String Id!!!!"`); the block is replaced by a stub that answers registered ids |
| `ImageList` `0x5364C8` + `ImageIndex` `0x56E2E8` | 637 × 0x30 B; 0x27D pointers | appends up to 936 descriptors (ids 637–1572 when everything is on); **ids shift with two toggles** (15.2) | `GetDescriptor 0x448420` (4 index refs, 5 list refs) and the unload loop `0x4483C0`; 3 `push 27Dh` and 1 `push 27Ch` elsewhere (not examined) | imm: `cmp edx,27Ch` | **DESIGNED, not built**: same shape as strings; `GetDescriptor`'s failure block `33 C0 C2 04 00` (`xor eax,eax; ret 4`) is reached by the id guard |
| furniture `itemInfo` `0x54C738` + `itemInfoLookup` (bss `0xAA9AE0`) | 252 × 0x6C B; item ids 0x1AD–0x2A8 | appends 122 records, rewrites the bound `0xFB` | `LookupFurnitureInfo 0x4B63C0` (4 refs); the bound `0xFB` is an immediate in **13** places and `0xFC` in **5** | imm (18); ids are in the **save** | **NOT ATTEMPTED**: reader side is small, but 18 bounds + category lists + per-id state not examined |
| inventory `itemInfo` `0x5531E8` | 0x1AD × 0x24 B, ends exactly at the category lists `0x556E3C` | fills rows from 0x117 (cheat upgrade items 0x11B–0x15B and the other added inventory items) | 14 functions, 17 field displacements | ids are in the **save** | **rows 0x117–0x1AC are zero rows in vanilla** (tested): B200's cheat/renovation rows can be written in place by the DLL, no retarget |
| category lists `gHomeList`… `0x556E3C–0x5575EC` | fixed `.data` block | interleaves ids, widens counts | 3 functions (`0x4BA710`, `0x4BA8F0`, `0x4BAA50`), 56 refs | imm counts | **NOT ATTEMPTED** (hook `GetCategoryItem`/`Count`) |

What the three mechanisms are, in order of preference: (1) **fill a pre-provisioned row in place** (inventory rows, achievement save slots: free); (2) **hook the one failure path** (strings, images, furniture fallback: the stock code already answers "unknown id" and every reader funnels into one block per reader); (3) **retarget the displacements** of a closed list of readers to a DLL copy (achievement list/order). A *table move* with an unbounded reference search was never needed.

### 15.2 What is reserved today, and what is not (measured on the generator, all 32 variants)

Run `VF2_FULL_ID_SWEEP=1 pytest tests/test_runtime_id_reservation.py -k never_move` for all 32 (about a minute); the default run checks four.

* **String ids never move.** 28 anchors (items, events, special-upgrade descriptions, cheat rows, outfits, behaviour labels, ornament title/achievement strings, custom achievements, renovations, bathroom 2, hairstyles) are identical in all 32 variants. §4's worry about `mobile_island_event_string_count()` is already answered by the generator: those ids are reserved unconditionally and only *populated* by toggle. Reservation = B200's numbers.
* **Achievement ids are slots.** Row id = save record index; the ids and their strings do not depend on any toggle. Reservation = B200's numbers (0x5F Ornamentologist, 0x60–0xAB customs).
* **Image ids move with exactly two toggles.** `img_renov` (1407) is stable; the ornament collection base moves with *renovations* only (1407 off, 1422 on); store icons, bathroom 2, curtains, hairstyle icons and prop art move with *ornaments and renovations* (hairstyle icons 1407/1420/1457/1470, prop art 1507/1520/1557/1570). Island events, cheat upgrades and behaviour patches never move an image. **Reserved layout = the all-on build** (so the default B200 ids are the runtime ids): items 637 (122), generation locks 759 (29), special icons 788 (49), holiday bodies 837 (456), VF3 TV 1293 (6), outfit icons 1299 (108), renovations 1407 (15), ornament collection 1422 (13), renovation store icons 1435 (15), bathroom 2 1450 (10), curtains 1460 (10), hairstyle icons 1470 (100), prop art 1570 (3); highest id 1572 (0x624), 936 appended. A feature that is off leaves its range unregistered (the descriptor lookup then answers "none", as stock does for an unknown id) instead of shifting everything behind it. Nothing in this order depends on other modules, so a module can be written against constants.
* **Item ids** are B200's constants (not a cascade): inventory 0x117–0x1AC fit the provisioned rows; furniture ids 0x2A9 and up (B200 goes to 0x330) exceed the stock furniture range 0x1AD–0x2A8.
* **Do image/string ids reach a save?** Unverified here: the achievement record holds ids and counters, not strings or images, and no other SaveState was read in full. Image ids differ between B200's own variants, which is indirect evidence that they are not persisted, but whether a save crosses variants was not checked. This matters only for the unbuilt image registry.

### 15.3 What was built and proved (feature: B200's "Ornamentologist", achievement 0x5F)

Why this feature: the smallest one that touches **every** shared table at once (a row, an order slot, two strings, and a saved record) without dragging in any of the 12 ornament items, their images, or the collector scene, whose ids are not provisioned in vanilla. It has no vanilla trigger, so it is an *infrastructure proof*, not a shippable feature: the module is `OrnamentologistAchievement`, **default off, experimental**. It deliberately does not include B200's other Holiday Ornaments achievement edits (Goal Collector target 12→13 and the SetComplete hook, Master Collector target 5→6): without the collection they would make "Goal Collector" unreachable.

* `id_registry` (internal module, no setting; installed exactly when a module that requires it is on and planned; always planned last): `RegisterString` / `RegisterAchievement`, validated (ids outside the reserved window or duplicates make the *registering module* fail to plan), registrations of a module that is not planned are ignored. Writes: 8 row displacements, 2 draw guards, 5 scene fields, 2 string stubs (17 writes, all-or-nothing). New pin roles `field` (rewrite one displacement/immediate in place; capstone proves it is that instruction's field, the instruction is not relative, no branch lands inside it) and `data`; `RAW_REFERENCE_CENSUS` makes `gen_sites` fail if any other 4-byte reference to the list or the order array exists anywhere in the file.
* `achievement_records` (B200's `patch_custom_achievements` LoadState change, **unconditional in B200 → default on**): five immediates. Stock `LoadState` copies the 0x125 records and, if any record from 0x5F is non-empty, clears 200 records from **0x5D** (it also wipes Bottlologist 0x5E). B200 validates and clears only 0xAC–0x124, so every defined row survives a load.
* `ornament_achievement`: registers B200's row `(0x5F, target 12, icon 0x1ED, 0, 0xE31, 0xE32, 0)`, the two B200 strings and the slot after Bottlologist. No write of its own.

Harness (`runtime/tests/idres_harness.cpp`, Stage 1 method: the real stub loads the real DLL into an in-memory copy of the patched image; real stock code runs): **`GetString` and the inlined lookup** against a lookup built the way the constructor builds it (stock ids, stock gaps, registered, unregistered, id 0, all registers preserved); **both DrawAchievement id guards** run from the real code (the complete flag is read and the row drawn for 0x5E/0x5F, not for 0x60); **`IncrementProgress`/`SetComplete`/`PercentCompleted`** (50% at 6 of 12, complete at 12, stamp, queue slot 0 = 0x5F); **`SaveState`/`LoadState`** on five save shapes against an oracle of the stock rule and of B200's rule; **the real `DrawScene`** at 98 scroll positions (graphics/window calls replaced by recorders) against a model of its loop, for the 95-entry stock order and B200's 96-entry order; the five scene/constructor fields against B200's `count·0x42+0x1C`; no W+X page; a corrupted registry pin refuses the registry **and** its consumer while `achievement_records` still installs.

Save results (all asserted):
* a **vanilla-format save loads byte-for-byte unchanged** in all five builds (no DLL, all off, records only, feature, ornament-only);
* a save written **with the feature on loads with it off** (records module on) and keeps record 0x5F, the other defined rows and 0x5D/0x5E; vanilla (and any build without the records module) wipes 0x5D–0x124 from it, which is exactly why the records module exists and why it must be on whenever the feature may ever have been on;
* a save written **with the feature off loads with it on**: record 0x5F is empty, the row starts at 0 of 12;
* a record written by a real completion survives `SaveState → LoadState` byte for byte; data only in the very last reserved record is cleared exactly like B200.

Mutation checks (each a single change, the intended tests failed, change reverted with `git checkout`, `git status` clean): M1 inline stub stores its result one slot off; M2 string lookup compares `id+1`; M3 first list reader left on the old table; M4 target 12→13; M5 placed after 0x5D instead of 0x5E; M6 draw guard one too low; M7 scroll range one row short; M8 order end pointer one short; M9 LoadState clear pointer left at record 0x5D; M10 registry not requested by its consumer; M11 a module installs although its required module did not (needs the corrupt-pin test); M12 scene count immediate one short; M13 LoadState counter start left at 0x5F (first run **not caught**: the save cases put garbage at the start of the tail; a case with data only in record 0x124 was added and now catches it).

### 15.4 Equivalence with the static B200 build, and where it is conditional

* Values (row, strings, order slot, `count·0x42+0x1C`, the five LoadState constants) are asserted against the generator's source and against numbers computed by importing it.
* The release DLL adds no export and no counter; `Plan::Field` refuses one-byte values above 0x7F (they are signed compare immediates).
* **Order of the Achievements screen with other B200 features on is not reproduced** (only the Ornamentologist slot is): B200 appends ~74 more ids in a toggle-dependent order. The registry places each id after an anchor; the full order must be a fixed template filtered by what is registered (design below).
* **Ids at or above 0x80** need a stub: `DrawAchievement`'s two guards and `DrawScene`'s count are `cmp ebp,imm8`, which cannot hold 0xAC (sign extension). B200 used caves; at runtime it needs a `jcc` retarget role (a `jge` rel32 is relative, so it cannot use the `replace` role). `RegisterAchievement` refuses ids ≥ 0x7F until that exists.
* **Goal/Master Collector** and the SetComplete→Goal-Collector hook are not part of this module (see 15.3).

### 15.5 What cannot move, and what depends on it

* **CAchievement record array and notify queue**: records `[0, 0xDBC)` are copied as exactly 0x125 × 12 bytes by `SaveState`/`LoadState` (`0x4B4C80`, `0x4B51E0`) and the notify queue (0x5F dwords) starts at `+0xDBC`, followed by the popup timer at `+0xF38`. Neither can grow. **No feature in the list needs it to**: ids stop at 0xAB. What depends on it staying fixed: B200's *Complete all achievements* (Cheat Upgrades), which clears all 0x5F queue slots before each completion, and any feature completing more than 95 goals in one frame. Those stay **static** (they live in Cheat Upgrades).
* **Per-item state arrays** (placed/owned/enabled bytes in `CInventoryManager`/`CFurnitureManager`): not examined. B200's same-sex toggle persists a byte at `InventoryManager+0x14C+0x2A3` — an *existing* stock slot (item 0x2A3) — so the converted-or-not decision for the same-sex family (7 patches) and the Cheat Upgrades one-shots (2) hinges on those arrays, not on the tables studied here. Marked **STATIC (unproven)**, not "impossible".

### 15.6 Updated per-patch table (replaces the 55 "Static" rows of §11.2)

| Group (patches) | Count | State after this experiment |
|---|---:|---|
| `custom_achievements` (rows + LoadState), `string_manager` (the string-table growth) | 2 | **Converted/proved** (`id_registry`, `achievement_records`; the Ornamentologist row is the consumer). `string_manager` here means the table growth only. |
| `custom_achievement_draw_bounds` | 1 | Proved for ids < 0x80; ids 0x80–0xAB need a `jcc` retarget role |
| `achiever_load_reconciliation`, `pet_achievement_callsites`, `family_tree_appearance_achievement_callsites`, `maximum_resource_achievement_callsites`, `longevity_achievement_load_reconciliation`, `lifetime_generation_counter`, `new_village_clears_patcher_achievement_state` | 7 | **Unblocked**: their blocker (the list/order/string tables) is gone; each is still its own port (call-site retargets and load hooks), plus its goal rows |
| `graphics_manager` | 1 | **Convertible by design** (image failure block, 15.1); four unexamined immediates (`push 27Dh` ×3, `push 27Ch`) first |
| `holiday_body_draw_redirect`, `collectable_item_holiday_ornaments`, `collectable_holiday_ornament_observers`, `collection_scene_holiday_ornaments`, `the_collector_holiday_ornaments` | 5 | Achievement part proved; the rest needs the collectable-item table (ids 0x9E–0xA9), 13 images and 4 strings, not examined → **pending** |
| `island_events` | 1 | Strings and images now possible; the event tables (`event_has_fired`, vtables) not examined → pending |
| `behavior_label_variants`, `arcade_behavior_labels` + 8 other behaviour/furniture-dispatch patches | 10 | Labels are strings (now possible); dispatch tables index added furniture → **STATIC (unproven)** |
| `furniture_manager`, `inventory_manager`, `visible_special_upgrades`, `house_renovations`, `scrolling_store_scene`, `purchase_dialog`, `special_upgrade_titles`, `floating_anim_table`, `added_furniture_click_aliases`, `added_furniture_venue_callsites`, `invisible_hammock_drop_action`, `invisible_furniture_parity`, `second_bathroom_leaks`, `bathroom1_curtain_decal`, `mobile_renovation_renderer` | 15 | **STATIC (unproven)**: furniture/inventory item growth (18 bound immediates, category lists, per-id state) |
| `mobile_table_prop_draw`, `mobile_table_prop_paint`, `mobile_patio_prop_execution` | 3 | STATIC (need furniture ids and images) |
| `same_sex_marriage` family | 7 | STATIC (unproven): persisted inventory byte; the cheat rows themselves *can* be written in place (rows 0x117–0x1AC are zero rows) |
| `force_successful_pregnancy_callsites`, `force_pregnancy_skips_refusals` | 2 | STATIC (Cheat Upgrades one-shot; also uses the fixed notify queue indirectly) |
| `mobile_sound_routes` | 1 | STATIC (sound ids not examined) |
| **Total** | **55** | **2 converted + 1 partly + 7 unblocked + 1 by design = 11** newly convertible; **44 stay static** (6 pending a table that looks provable, 38 unproven or out of scope) |

Honest scale: the experiment unblocks about a fifth of the static patches and removes the numeric-coupling blocker for the achievement and string families. The big-ticket items (furniture, inventory, the added-furniture behaviour, renovations) are untouched; their cost is the 18 bound immediates plus the category-list hooks plus the per-id state check, and nothing here argues that cannot work — only that it is unproved.

### 15.7 Risks to saves

1. No module writes a byte of save data of its own; the record layout and its 3,564 bytes are unchanged; a runtime-built save and a B200 save use the same slot for Ornamentologist (cross-load is the asserted LoadState rule).
2. **Turning `AchievementReservedRecords` off, or loading in a build without it, after the feature ever wrote a record, makes stock `LoadState` wipe records 0x5D–0x124** (the stock rule, shown by `test_vanilla_loses_the_feature_record…`). B200 has no off switch for this; the runtime default is on. If the module is ever offered as a setting, the patcher must refuse "off" for a profile that has ever had a registry feature on, or simply not expose it.
3. A save from a different registry configuration is safe: ids are constants, rows are slot-indexed, and the order screen is rebuilt every run.
4. Unexamined: item-id state arrays and the furniture/inventory save (15.5).

### 15.8 Live-test checklist for the proved feature (main session; one live test at a time)

**Build:** `C:\vf2w\vf2-idres-test\VF2 IdRes Test.exe` (SHA-256 `04f9ff02…1b28e`, the unchanged Stage 1 bootstrap exe); `Virtual Families 2 Patcher Files\vf2fun.dll` is the **release** build (SHA-256 `ce56931b…48f9`, no test exports); `vf2fun.ini`: `AchievementReservedRecords=1`, `OrnamentologistAchievement=1`, every other key 0; `ldw.ini` `FullScreen=0`. Saves go to `Documents\LDW\VF2 IdRes Test\`. Probe: `python runtime\tools\probe_stage1.py --exe-name "VF2 IdRes Test.exe"` from `C:\vf2w\wt-idres`; the achievement writes below refuse unless the exe name contains "Test".

* **A. Install.** Launch to the title screen. Probe: stub `DLL loaded`; modules `achievement_records`, `ornament_achievement`, `id_registry` all `installed`, none `REFUSED`; `achievements.rows_moved` true; 8 sites `ach_rows_*` show "field retargeted to 0x…" (all inside the DLL), `scene_*`/`ach_draw_bound_*` fields changed, `string_get_fail` and `string_inline_fail` are `jmp`s into the DLL; `order_count` 96 and `order_around_0x5E` = `[…, 0x5D, 0x5E, 0x5F, 0x4D…]`. `vf2fun.log` lists `achievement_records`, `id_registry` and `ornament_achievement` as installed (17 + 5 writes).
* **B. The row.** Start a new family; open the Goals/Achievements screen. Expect the usual list with **"Ornamentologist" ("You completed the collection of holiday ornaments.")** directly after "Bottlologist", the same medallion as the others, a progress bar "0 of 12". Scroll to the very bottom: the last row of the list (goal 0x5C) is fully reachable, one row further down than in stock; nothing is cut off or repeated; scrolling back to the top shows row 1 intact. The screen draws every existing row as before.
* **C. Completed state and the popup.** `probe … --set-achievement 0x5F 1 12`: the row shows as complete (check mark / full bar) after the screen is redrawn. `probe … --queue-achievement 0x5F`: the goal popup shows "Ornamentologist" with its text and the usual 25-coin reward. Also set `--set-achievement 0x5F 0 6` and reopen the screen: bar at half, "6 of 12".
* **D. Save/reload with the feature on.** Complete 0x5F as in C, quit cleanly, relaunch. The row is still complete; the probe's `records.0x5f` shows `flag 1, progress 12`; Bottlologist (`0x5e`) and the other achievements you had are unchanged.
* **E. Feature off, records on.** Quit cleanly, set `OrnamentologistAchievement=0` (keep `AchievementReservedRecords=1`), relaunch. No Ornamentologist row; probe `rows_moved` false, every `ach_*`/`scene_*` site vanilla, `string_*` vanilla. Play a minute, quit cleanly. Set it back to 1 and relaunch: the row is still complete (the record survived a load with the feature off, B200's rule).
* **F. All off = stock.** Quit cleanly, set both to 0, relaunch: stock Goals screen (95 rows), all sites vanilla. Stock `LoadState` now wipes records 0x5D–0x124 on that load (documented stock behaviour, 15.7 item 2): Bottlologist is lost in this test save. Expected; do not use a save you care about.
* **G. Vanilla-format save.** Delete the test save folder, start a new family with the feature on, quit cleanly at once: record 0x5F reads `flag 0, progress 0`. (Compare with a save from `Documents\LDW\VF2 Runtime Stage3 Test\` if present: it loads with the feature on and the row at 0 of 12.)
* **H. Strings elsewhere.** Nothing else in the game should change: spot-check one tutorial popup and the store descriptions (stock strings), and the Details screen.
* **Pass** = A–H as stated; any crash on the Goals screen, a missing last row, a repeated row, or a lost record in D/E is a fail.

### 15.9 Reproducing

* `python runtime\tools\gen_sites.py --vanilla "<vanilla>\Virtual Families 2.exe"` (proves the new pins and the reader census, regenerates `vf2fun_sites.h`); `runtime\native\build.bat` (DLL); `VF2_VANILLA_RUNTIME_DIR=<vanilla folder> python -m pytest tests\test_runtime_hooks_stage1.py tests\test_runtime_id_reservation.py`.
* Test copy: `python runtime\vf2_runtime_patcher.py apply --game-dir <vanilla folder> --output-dir C:\vf2w\vf2-idres-test --dll runtime\build\vf2fun.dll --exe-name "VF2 IdRes Test.exe" --set …` (every key set explicitly; see 15.8).
