# VF2 Patcher — 30-Commit Adversarial Regression Audit

**Date:** 2026-08-13
**HEAD at audit time:** `e5dab62d80bfe491f1213476da3ad4fc6cca1e34` ("Repair VF2 renovations curtains and Special Upgrades overlays")
**Scope:** the 30 most recent commits reachable from HEAD, verified by direct Git history inspection (not assumed to be `HEAD~30..HEAD`).
**Method:** static repository/diff/test analysis only. No IDA/HxD/WinDbg/Ghidra used. Nothing was fixed, refactored, or committed — this is the audit report only, as instructed. A companion release-gate audit (`VF2-release-gate-audit-20260812.md`) exists from a prior, separate pass; where this audit's deeper file-provenance tracing **corrects** a conclusion from that document, it is called out explicitly in §1 and §5 rather than silently reused.

---

## 1. The exact 30-commit audit scope, and why it isn't a simple `HEAD~30`

`git log --oneline -30` was checked against the raw graph rather than trusted blindly, because **history here is not linear**: commit `61b3407` ("Merge B160 release branch into main") has two parents that share **no common ancestor at all** (`git merge-base` between them returns nothing). Concretely:

- First parent `8155a62` ("Hide unbacked optional payload toggles", 2026-07-06) is the tip of an old, small `main` line — only 6 commits total reachable from it, all dated 2026-07-05/06.
- Second parent `15e6cb9` ("Publish B160 merged curtain QA package", 2026-08-12) is the tip of a long-running, unrelated 317-commit development line (the "B160 release branch") where essentially all real work happened.

`git log`'s default chronological ordering correctly resolves this: the 30 most-recent-by-date commits reachable from HEAD all come from the second-parent (B160) line plus the two commits made directly after the merge — the stale first-parent line (dated a month earlier) is correctly excluded on its own merits, not by an arbitrary cutoff. This was verified, not assumed.

**Confirmed 30-commit window, oldest → newest** (baseline immediately before the window: `d8be846468adb441898f58d787ee5513a12942e749`, "Restore stock marriage proposal state path"):

| # | Hash | Date (local) | Message |
|---|---|---|---|
| 1 | `14718ca` | 08-12 00:01 | Enable renovation overlays and stock marriage path |
| 2 | `0904be3` | 08-12 00:46 | Fix Cheat Upgrades executable overlay selection |
| 3 | `a696cae` | 08-12 02:45 | Implement native same-sex marriage semantics |
| 4 | `c3c5187` | 08-12 03:10 | Add six-child private romantic time behavior patch |
| 5 | `75b89cc` | 08-12 03:44 | Fix Bathroom 1 renovation curtain fallback |
| 6 | `b5dc6f9` | 08-12 03:55 | Pin Bathroom 1 black curtain selector |
| 7 | `57cb579` | 08-12 04:03 | Pin Bathroom 1 beige curtain selector |
| 8 | `49cc2ea` | 08-12 04:10 | Pin Bathroom 1 pink curtain selector |
| 9 | `e51b446` | 08-12 04:18 | Pin Bathroom 1 green curtain selector |
| 10 | `9e78953` | 08-12 04:48 | Add Bathroom 2 blue curtain selector |
| 11 | `d0dc9fa` | 08-12 04:56 | Pin Bathroom 2 pink curtain selector |
| 12 | `1b9d235` | 08-12 05:12 | Pin Bathroom 2 beige curtain selector |
| 13 | `9df2047` | 08-12 05:20 | Pin Bathroom 2 black curtain selector |
| 14 | `89de768` | 08-12 05:28 | Pin Bathroom 2 green curtain selector |
| 15 | `df52448` | 08-12 06:36 | Fix reversible Anti-Spam and Rockhound store rows |
| 16 | `a5cd989` | 08-12 07:28 | Route mess cheats through native spawners |
| 17 | `c3ffc35` | 08-12 08:11 | Enable Island Events and Bathroom 2 leaks |
| 18 | `0dfd91b` | 08-12 08:40 | Simplify player-facing patch descriptions |
| 19 | `c4ec432` | 08-12 09:33 | Harden release package privacy cleanup |
| 20 | `8487410` | 08-12 10:07 | Deduplicate offline patch payload aliases |
| 21 | `3d661e4` | 08-12 11:42 | **Revert** "Simplify player-facing patch descriptions" |
| 22 | `d6e451d` | 08-12 12:55 | Enable mobile furniture and sound player QA routes |
| 23 | `7b74c8b` | 08-12 13:14 | Allow Bathroom 2 renovation repurchase removal |
| 24 | `8d6f8e7` | 08-12 14:09 | Fix Bathroom 2 curtain grid routing |
| 25 | `6f55a22` | 08-12 14:37 | Enable Behavior Patches in patcher |
| 26 | `8a0af6e` | 08-12 15:44 | Enable mobile QA catalog options |
| 27 | `15e6cb9` | 08-12 20:25 | Publish B160 merged curtain QA package |
| 28 | `61b3407` | 08-12 20:34 | **Merge** B160 release branch into main |
| 29 | `92228cc` | 08-12 22:32 | Make Anti-Spam and Rockhound repurchaseable |
| 30 | `e5dab62` | 08-12 23:24 | Repair VF2 renovations curtains and Special Upgrades overlays (**HEAD**) |

### Files changed, and files touched repeatedly (computed from the actual 30 hashes, `--no-walk`, not the polluted `d8be846..HEAD` range which drags in the 6 unrelated old-main commits)

| File | Commits touching it | % of window |
|---|---|---|
| `work/test_patch_mobile_furniture_pack.py` | 24 | 80% |
| `work/patch_mobile_furniture_pack.py` | 19 | 63% |
| `work/export_offline_patch_bundle.py` | 14 | 47% |
| `work/test_export_offline_patch_bundle.py` | 10 | 33% |
| `docs/REQUEST_LEDGER.md` | 10 | 33% |
| `docs/offline-patcher.md` | 7 | 23% |
| `docs/B156-mobile-renovation-ledger.md` | 6 | 20% |
| `data/vf2/mobile-renovation-atlas-contract.json` | 6 | 20% |
| `work/verify_offline_bundle_zip.py` | 3 | 10% |
| `work/test_verify_offline_bundle_zip.py` | 3 | 10% |
| `work/test_special_upgrades_release_parity.py` | 3 | 10% |
| `work/offline_vf2_patcher.py` | **1** | 3% |
| `work/package_patcher_zip.py` | **0** | — |
| `src/offline_vf2_patcher.py`, `src/offline_vf2_patcher_gui.py`, `src/export_offline_patch_bundle.py` | **0** | — |

This table is the single most important structural fact in this audit and drives §2 and most of the CRITICAL/HIGH findings below.

### Renamed/deleted/regenerated files
- `docs/B158-player-descriptions-r35.md` — added by #18 (`0dfd91b`), deleted by #21 (`3d661e4`) — see §4.
- No file renames or moves were detected in the window (`git log --follow`/`--find-renames` on the touched files shows plain modifies/adds/one delete).

### Commits that partially undo or contradict earlier commits in this same window
1. **#18 → #21**: `0dfd91b` "Simplify player-facing patch descriptions" is explicitly reverted 3 hours later by `3d661e4` ("Revert \"Simplify...\""). Self-declared, not hidden — see §4.
2. **#15 → #29**: `df52448` "Fix reversible Anti-Spam and Rockhound store rows" first fixes the two rows' shared active/removal logic *but leaves it gated behind `kVF2EnableB150CheatUpgrades`*; `92228cc`, ~16 hours later, revisits the same helper functions (renaming `VF2IsCheatReversibleStockUpgrade` → `VF2IsReversibleStockUpgrade`) and removes the Cheat-Upgrades gate so the rows are reversible **regardless** of that setting. This is a genuine two-stage fix, not a contradiction — see §5/§27.
3. **#16**: `a5cd989` "Route mess cheats through native spawners" **removes** a custom bounds-accounting function (`VF2CountMessRecords`) that had explicitly reserved "half of the native 30-record mess pool for the house" (15/15 split against a shared 30-slot `CollectableItem` table) and replaces it with unconditional calls requesting up to 30 house items + 30 yard items against the same table, trusting undemonstrated native self-bounding. Flagged SUSPICIOUS — see §9/§12.

---

## 2. The central finding: a fix that only reached one of two copies of the patcher

This repository carries **two independently-tracked copies** of the core patcher runner: `src/offline_vf2_patcher.py` (1,822 lines) and `work/offline_vf2_patcher.py` (3,862 lines — more than double). They are not symlinked or generated from one another; `cmp` shows they diverge from byte 493. Confirmed from the hotspot table above: **`src/offline_vf2_patcher.py` received zero commits in this entire 30-commit window.**

Commit **#2, `0904be3` "Fix Cheat Upgrades executable overlay selection"**, modified only `work/offline_vf2_patcher.py`. It adds a new function `select_exact_executable_overlays()`, wired directly into the return path of `manifest_asset_patches()` (so every caller gets it automatically), with this docstring:

> "Overlay EXEs all write the same named modded executable. Applying multiple feature overlays sequentially can silently drop earlier code when no combined overlay exists. **Fail closed** unless the manifest contains exactly one record matching the complete enabled overlay set."

This is a real fix for a real, serious class of bug (the exact "silent feature loss from an incomplete overlay matrix" class the user asked this audit to hunt for): it groups executable-overlay asset records by output path, computes the exact `requires` set the player's enabled settings imply, and **raises `PatchError`** — refusing to run — if no manifest record's `requires` exactly matches that set, instead of silently picking the nearest/last-matching candidate. A genuine, non-trivial regression test (`test_rejects_incomplete_executable_overlay_matrix_instead_of_falling_back`, also added in #2) constructs exactly this scenario and asserts the `PatchError` fires. **This test currently passes at HEAD** (confirmed by running the full `work/` suite in this audit — see §11).

**I traced which copy of `offline_vf2_patcher.py` is the one actually inside the shipped, published release ZIP** (`outputs/VF2-B162-Repurchaseable-20260812.zip`, hash-verified identical to the live GitHub "Latest" asset in the companion release-gate audit): `cmp` shows the shipped file is **byte-identical to `work/offline_vf2_patcher.py`**, not `src/offline_vf2_patcher.py`. So the fail-closed fix from commit #2 **is** the runner a player actually executes. This **corrects** a conclusion in the prior, separate release-gate audit, which examined `src/offline_vf2_patcher.py` (reasonably, since it's the file that repo convention would suggest is canonical) and concluded the shipped patcher would *silently* select the wrong executable for the 13 missing overlay combinations described in §5 below. That specific runtime claim was based on the wrong copy of the file. The corrected picture, verified in this pass:

- **The shipped runner correctly fails closed** for any of the 13 missing mobile-renovation overlay combinations (see §5) — the player gets a clear `PatchError`, not a silently wrong executable.
- **`src/offline_vf2_patcher.py` still contains the old, unsafe subset/last-match-wins selection logic with no such guard.** It is not what ships today, but it is a live landmine: it is the file whose path convention (`src/` vs `work/`) looks canonical, it is what a future contributor or an alternate release script would most plausibly read from, and nothing in this 30-commit window synchronized, deprecated, or even flagged it as stale. If release tooling is ever pointed at `src/` instead of `work/` — or if `work/`'s fix is only ever manually cherry-picked forward and someone misses it — the silent-corruption bug returns immediately with zero warning, because `src/`'s copy has no equivalent test guarding it (the fail-closed test was added only to `work/test_offline_vf2_patcher.py`; `tests/test_offline_vf2_patcher.py`, which covers `src/`, was not touched by commit #2 or any other commit in this window).

This is the single clearest example in this window of Codex fixing something real but the fix not fully "landing" — not because the fix is wrong, but because the repository has a silent fork of the file it fixed, and nothing in the 30 commits acknowledges or closes that fork.

---

## 3. What the fail-closed fix does *not* cover — the matrix and packaging defects remain

`select_exact_executable_overlays()` only fires when the *player's enabled settings* have no exact matching overlay record. It does **not** address a separate, still-fully-present defect: the manifest contains a record with `requires: ["core_executable"]` alone (the fallback used when a player enables **no** optional overlay features at all) whose source payload is `Virtual Families 2 - Modded B162 - Final All-Enabled Native.exe` — **the exact same physical file, same SHA-256**, as the record for the full `{core_executable, behavior_patches, cheat_upgrades, holiday_ornaments_collection, island_events, mobile_renovations}` combination. Both requires-sets are internally self-consistent (each matches its own record exactly, so `select_exact_executable_overlays` sees nothing wrong), but the packaging is still broken: a player who disables **every** optional feature is silently handed the fully-loaded, everything-enabled executable as their "clean/core" build.

This was **independently re-verified in this audit session** (not reused from the prior document) by running the repository's own dedicated validator, `work/package_patcher_zip.py::validate_executable_inventory()`, directly against the live release directory:

```
ValueError: Payload executable must have exactly one manifest asset record:
payload/Virtual Families 2 - Modded B162 - Final All-Enabled Native.exe
```

`work/package_patcher_zip.py` — the file containing this exact check — **was not touched by any of the 30 commits** (confirmed: zero entries for it in the hotspot table). It sat there, unrun, the entire time. Meanwhile, `work/verify_offline_bundle_zip.py` — a *different* validator that genuinely **was** hardened three separate times in this window (#26 `8a0af6e` +144/−59, #27 `15e6cb9` +40/−28, #29 `92228cc` +111/−) — was checked directly in this audit and **contains no equivalent "exactly one manifest record per executable" check** (its duplicate/uniqueness checks cover: duplicate `requires` lists, case-insensitive duplicate ZIP member names, duplicate top-level ZIP roots, duplicate setting IDs, duplicate mobile-sound routes — none of which is the one that actually matters here). Three commits' worth of hardening effort went into the validator that can't catch this defect, while the validator that can catch it was left idle.

Separately, commit **#20, `8487410` "Deduplicate offline patch payload aliases,"** sounds on its title alone like it might address "duplicate executable payload." It does not: it performs byte-level, on-disk **file** deduplication (collapsing physically-identical payload files down to one copy to shrink the ZIP — confirmed from its diff, and consistent with the `payload_deduplication: {removed_file_count: 615, removed_bytes: 44958081}` figure recorded in the shipped manifest). It operates one layer below the actual defect: it correctly collapsed the two exe copies down to one file on disk, which is *why* the two conflicting manifest **records** now point at the same physical file rather than two separate ones — but the two manifest records themselves, and the semantic confusion they represent, are untouched. A future reader of the commit log could easily mistake "Deduplicate offline patch payload aliases" for a fix to this exact problem; it is not, and the underlying defect it's adjacent to is still open at HEAD.

**Net effect, confirmed at current HEAD:** the executable-overlay matrix still only covers 3 of 16 possible Mobile-Renovations-combined states (`mobile_renovations` alone, `cheat_upgrades + mobile_renovations`, and the full "final all-enabled" set — all traced from `work/build_b162_matrix.ps1`, itself new in commit #30 `e5dab62`, the very last commit of this window). For the 13 missing combinations, the player gets a clean, informative failure (§2) rather than silent corruption — genuinely fixed. For the "everything off" baseline, the player silently gets the everything-on executable — not fixed, still present, independently reproduced this session, and the release ZIP fails its own project's inventory validator.

---

## 4. The "simplify then revert" pair — verified as a clean, self-documented U-turn

Commit #18 (`0dfd91b`) rewrote every player-facing patch description to shorter text, adding `docs/B158-player-descriptions-r35.md` explaining the rationale. Commit #21 (`3d661e4`), 3 hours later, is a literal git-style revert ("Revert \"Simplify player-facing patch descriptions\""), deleting that doc and restoring the longer descriptions. Verified in this session: diffing the pre-#18 tree against the post-#21 tree for `work/patch_mobile_furniture_pack.py` shows only the residual changes contributed by the two unrelated commits (#19 `c4ec432`, #20 `8487410`) that landed in between — the description text itself is cleanly restored, not partially reverted. This is workflow churn (a wasted ~3-hour round trip, worth asking why the simplification was rejected) but **not** a hidden regression: it is self-declared in the commit title and the net result at HEAD matches the pre-simplification state for the text itself. Severity: LOW.

---

## 5. Mortality/aging — explicitly checked, confirmed untouched in this window

Per the audit brief's emphasis on this area: `older_villager_mortality` and every file/function associated with the calibrated old-age death-roll (`.vf2mort` dormant-byte toggle, the "increases with effective age, accelerates after effective age 110, never certain, no hard maximum age" design documented in the setting's own description) was searched for across the full window. **Zero files matching mortality/aging paths were touched.** The only two places the word "mortality" appears in the 30-commit diff are both **description-text passthroughs inside the #18/#21 simplify/revert pair** (§4) — the description string is removed and re-added with **identical content**, not edited. No mortality probability formula, injected assembly, age-comparison boundary, or RNG call was touched, added, or removed anywhere in this window. **Conclusion: no mortality/aging regression risk from these 30 commits.** (This does not re-verify the mortality patch's own correctness against its intended design in isolation — that would require re-auditing the commits that originally introduced it, which predate this window and are out of scope per the user's own framing.)

---

## 6. Curtain-selector sequence (#5–#14, 8 near-identical "Pin BathroomN color" commits)

Traced #6–#9 (Bathroom 1: black, beige, pink, green) at the code level, not just the commit titles. Each commit is **strictly additive** to a `bathroom1_curtain_selector` / `bathroom2_curtain_selector` metadata dict inside `work/patch_mobile_furniture_pack.py`'s `patch_graphics_manager()`: one new `{color}_item` / `{color}_asset` key pair per commit, one color per commit, no prior color's mapping edited or removed. This is a clean incremental build-out, not oscillation or repeated breakage-and-refix — no evidence of a color being pinned, then unpinned, then re-pinned differently within the window.

Each commit's paired test (e.g. `b5dc6f9`'s `test_...`) does more than assert dict shape: it also opens the actual asset file on disk and asserts its SHA-256 against a hard-coded hash, and cross-checks `active_item_to_color[item_id]`. That is real, non-tautological coverage of *asset presence and identity*.

**What was not fully traced in this pass, and should be flagged SUSPICIOUS / NEEDS VERIFICATION:** whether this `*_curtain_selector` dict is actually consumed by the generated C++ that binds a store-purchase item ID to a runtime image descriptor (i.e., whether it is a *causal* source of truth for in-game curtain color selection), or whether it is a *descriptive* metadata block layered on top of item-ID-to-asset associations that already existed elsewhere in this very large (tens of thousands of lines) generator file, in which case these 8 commits are documentation/verification hardening rather than functional fixes. The commit titles ("Pin... selector") read as if something was previously ambiguous or wrong and is now fixed, but I could not fully close the loop from this dict to the actual injected store-icon binding code within this audit's budget. Recommend a targeted trace of `patch_graphics_manager()`'s full body against the actual C++ emission for the curtain item IDs (`0x13C`–`0x140`, `0x14D`–`0x151`) before trusting that these commits changed in-game behavior versus only hardening self-verification.

Commit #24 (`8d6f8e7`, "Fix Bathroom 2 curtain grid routing") and the earlier baseline-side commit `8d6f8e7`'s predecessor content (Bathroom 2 grid/leak fixes, #17 `c3ffc35`, #23 `7b74c8b`) were not traced to the same depth in this pass — flagged for follow-up.

---

## 7. GUI wiring across the window

`src/offline_vf2_patcher_gui.py` and `work/offline_vf2_patcher_gui.py` — **neither was touched by any of the 30 commits.** This is not automatically a defect: the previously-audited GUI renders settings generically from the manifest's `settings[]` array by category (`main`/`optional`/`experimental`), so a new *value* for an existing setting's underlying behavior doesn't need a GUI code change. This was checked directly: **no new top-level setting `"id"` was registered anywhere in the 30-commit diff** (`grep` for new `"id": "..."` additions inside the settings-shaping code returned nothing). Everything this window changed (same-sex marriage semantics, six-child private time, mess-cheat routing, Anti-Spam/Rockhound repurchase, Island Events, Bathroom 2 leaks, Behavior Patches enablement, mobile QA routes) rides on **existing** setting IDs (`same_sex_marriage`, `behavior_patches`, `cheat_upgrades`, `island_events`, `mobile_renovations`, `mobile_furniture_behaviors`), so no GUI/backend disconnect was introduced at the top-level-toggle granularity. This is a genuinely low-risk area for this window — confirmed, not assumed.

What was **not** independently re-verified in this pass: whether the *descriptions* shown for those existing toggles still accurately reflect the newly-changed behavior underneath them (e.g., does `behavior_patches`'s GUI description text correctly describe the six-child private-time addition from commit #4?). The companion release-gate audit already found one confirmed description/default mismatch (`holiday_ornaments_collection`) and one confirmed stale count (`mobile_renovations` description says "15" styles vs. an actual 20-row catalog) — neither of those originates in this 30-commit window (both predate it), so they are not re-litigated here, but they remain open at HEAD.

---

## 8. Same-sex marriage and six-child private time (#2/#3, #4)

`a696cae` ("Implement native same-sex marriage semantics") is the single largest functional diff in the window: 252 insertions / — in `work/patch_mobile_furniture_pack.py`, with a **204-line rewrite of the corresponding test file that nets fewer lines than before** (204 changed, test file shrank). A large test-file rewrite alongside a large implementation rewrite is exactly the pattern the audit brief asks to be suspicious of ("did Codex repair the implementation, or alter the test until it went green?"). This audit did not have budget to line-by-line diff the pre/post test assertions to confirm the same behavioral claims are still being checked with equal or greater rigor rather than weakened. **Flagged SUSPICIOUS / NEEDS VERIFICATION** — recommend a dedicated pass diffing `test_patch_mobile_furniture_pack.py`'s marriage-role assertions before and after `a696cae` line-by-line.

`c3c5187` ("Add six-child private romantic time behavior patch") is additive under the existing `behavior_patches` umbrella (confirmed via the `behavior_patches` setting description read in the companion audit, which already documents "exact opposite-sex adult spouse pairs with six children use native Having Private Romantic Time with 0% pregnancy and no argument" — text that predates this specific commit, consistent with this being an incremental extension of already-described behavior rather than a new undocumented feature). Not deep-traced at the instruction level in this pass.

---

## 9. Mess-cheat routing (#16) — trust-the-native-code risk

Detailed in §1 (contradiction list, item 3). Restated with the risk explicit: the removed code computed how many mess records of each kind already existed in the shared 30-slot `CollectableItem` table and only topped up to a 15/15 house/yard split, with a comment explaining this was **deliberately** reserving half the pool for the house so yard weeds couldn't starve it (or vice versa). The replacement trusts native `SpawnTrashInHouse`/`SpawnStainInHouse`/`SpawnSockInHouse`/`SpawnWeedsInYard` to "perform their own bounded slot selection" — a claim asserted in a comment, not demonstrated by anything in this diff. If those native routines are the same stock "Cause a Mess"/weed-spawn routines the base game already calls (plausible, since this patch only changes the requested *counts*, not the call targets), then this is likely safe — vanilla VF2 already has to handle its own mess-spawn slot exhaustion gracefully or the base game would already crash on a busy house. But this was not independently confirmed against the native function bodies in this pass (would require the disassembly-level review the project rules gate behind explicit tool authorization). **Flagged SUSPICIOUS / NEEDS VERIFICATION**, not CRITICAL, because the risk is speculative and the removed custom logic was itself unverified in the other direction (its own 15/15 split cap was never proven correct either — I found no test in the pre-#16 code asserting the mess pool never overflowed).

---

## 10. Packaging/privacy hardening (#19, `c4ec432`)

This commit adds `PACKAGE_DEVELOPMENT_SUFFIXES` / `PACKAGE_DEVELOPMENT_ROOT_FILES` / `PACKAGE_DEVELOPMENT_EXACT_FILES` / `PACKAGE_UNWANTED_NAMES` allow/deny-lists to `seed_from_previous_build()`, plus (confirmed by function-name reference, not fully re-read line-by-line) the `clean_package_validation` gate referenced in the companion audit. This is legitimate, additive hardening against exactly the class of defect the audit brief's §19/§21 worry about (dev artifacts, IDA files, owner-machine paths leaking into a package). One earlier finding stands from the companion audit and was **not** re-derived fresh in this pass (flagged, not re-verified here): the shipped `manifest.json`'s top level does not carry a `clean_package_validation` key at all, so this gate's actual pass/fail result cannot be confirmed from the shipped artifact even though the check code exists and runs during generation.

---

## 11. Test results at HEAD (re-run fresh in this session)

- `python -m unittest discover -s tests -v` → **35 passed, 0 failed.**
- `python -m unittest discover -s work -p "test_*.py" -v` → **469 run, 2 failed, 2 skipped**, 352.7s:
  1. `test_export_offline_patch_bundle.ExportOfflinePatchBundleTests.test_overlay_backed_assets_are_not_exposed_without_their_executable` — fails only inside the full 469-test run (empty stdout/stderr from the exporter subprocess); **passes cleanly in isolation** (confirmed by direct re-run). This is a test-order/state-leakage bug in the suite itself, not a demonstrated product defect — but it means "all green" cannot be claimed for a full `work/` run as-is, and it could be masking a real interaction between two of the 30 commits' env-var-setting test fixtures (the matrix/export scripts documented in `work/build_b162_matrix.ps1` set and (in the failure path) may not fully restore `VF2_ENABLE_*` environment variables). Not isolated to a specific offending test within this budget.
  2. `test_patch_mobile_furniture_pack.HolidayOrnamentGateTests.test_canonical_holiday_assets_rebuild_byte_for_byte` — fails **consistently**, in isolation too, on this machine (Pillow 12.3.0): the regenerated `collection-ornaments_background.png` differs byte-for-byte from the checked-in canonical asset (different `iCCP` profile chunk / zlib stream — an encoder-version artifact, not obviously a content change, but a real, reproducible non-determinism in the generator's asset pipeline). Not attributable to any specific one of the 30 commits without bisecting against the machine's Pillow version, which was not done in this pass.
  - Specifically confirmed passing: `test_rejects_incomplete_executable_overlay_matrix_instead_of_falling_back` (§2's key regression test).

Neither failure was silently tolerated by weakening an assertion or skipping — both are genuine, currently-red tests. No evidence was found in this window of a test being edited to match broken output rather than the implementation being fixed (the one large test-file rewrite worth distrust, `a696cae`'s 204-line rewrite in §8, was not fully diffed assertion-by-assertion — flagged, not cleared).

---

## 12. Findings by severity

### CRITICAL
*None identified in this pass that constitute confirmed, demonstrated executable corruption or an access violation with a shown mechanism.* The closest candidate (§9, mess-cheat spawn bounds) is explicitly downgraded to SUSPICIOUS because the actual overflow mechanism could not be shown without decompiler access this audit isn't authorized to use.

### HIGH

1. **Executable-overlay matrix still only covers 3/16 Mobile-Renovations combinations at HEAD**, unchanged in outcome by anything in this window except that the failure mode for 13 of them was correctly hardened to fail closed (§2/§3). *Introduced (matrix incompleteness): predates this window (§3's evidence shows `build_b162_matrix.ps1` — new in commit #30 — still only encodes 19 of 32 combinations, so the gap was carried forward, not created here, but it was also not closed here despite the opportunity and despite writing the exact defensive code that detects it).* Still present at HEAD: **yes**. User-visible symptom: selecting Mobile Renovations together with any one or two of Island Events/Holiday Ornaments/Behavior Patches (without also enabling every remaining flag) makes the patcher refuse to run, with an error message, for a combination the GUI presents as freely selectable. Repair: extend the matrix (rebuild script + manifest) to cover all 16 mobile combinations, or make the GUI aware of which combinations are actually buildable and gray out the rest. Mandatory before those combinations can be considered supported.

2. **`src/offline_vf2_patcher.py` is an unfixed, untested fork of the exact function this window patched for safety** (§2). Introduced: predates the window (the fork itself is old); the divergence became load-bearing risk specifically because commit #2 fixed one copy and not the other, within this window. Still present at HEAD: **yes**. Not currently player-facing (confirmed the shipped ZIP uses the `work/` copy), but it is a live landmine for the next release-tooling change or manual cherry-pick. Repair: either delete `src/offline_vf2_patcher.py`/`src/offline_vf2_patcher_gui.py`/`src/export_offline_patch_bundle.py` if `work/` is now canonical and update anything that still references `src/`, or establish and enforce a real sync step. Mandatory.

3. **Packaging defect confirmed still open**: the shipped B162 release ZIP fails `work/package_patcher_zip.py::validate_executable_inventory()` (re-confirmed fresh in this session), because the same physical executable backs both the "no optional features" baseline and the "everything enabled" overlay. Not introduced by this window's own commits in the sense of a new regression (the underlying duplicate dates to how the matrix/manifest were assembled before commit #30), but commit #30 (`e5dab62`, the final commit of this window) is what produced the currently-shipped matrix/manifest exhibiting it, and the validator that would have caught it was never run as part of that commit's own work. Still present at HEAD: **yes**. Repair: give the "core only" baseline its own distinct build, not a reuse of the final-all-enabled binary; wire `package_patcher_zip.validate_executable_inventory` into whatever process produces the release ZIP. Mandatory before another release.

### MEDIUM

4. **`work/` full-suite test run is not clean** (§11): a test-order/state-leakage bug (test passes in isolation, fails in the full run) undermines the reliability of "all tests passed" as a release gate for this suite as currently structured. Introduced: not attributable to a single commit within this budget; the suite grew substantially across this window (469 tests, many added by commits in this list) so the contamination is plausibly recent. Still present: **yes**. Repair: identify and fix the leaking global/env-var state; not urgent for gameplay but urgent for trusting future CI-style runs.

5. **Non-deterministic asset regeneration** (§11, `collection-ornaments_background.png`): confirms the generator's "byte-for-byte" canonical-asset claim does not hold on at least one current toolchain. Still present: **yes**. Repair: pin the image-encoding library/version used for canonical asset generation, or relax the test to a content/perceptual hash instead of raw bytes.

6. **Mess-cheat spawn bounds now rely on unverified native self-limiting** (§9). Suspicious rather than confirmed; recommend verification before treating as safe.

### LOW

7. **"Simplify then revert" description churn** (§4): ~3 hours of round-trip work with no net effect on shipped text; not a defect, but worth asking why the simplification was rejected so a repeat attempt doesn't happen.
8. **Misleadingly-named commit** (`8487410` "Deduplicate offline patch payload aliases", §3): solves file-level duplication, not the adjacent manifest-record-level duplication that a reader would reasonably assume it addresses given the audit brief's own wording. Worth a commit-message/doc clarification so it isn't mistaken for a fix to finding #3 above in the future.

### SUSPICIOUS / NEEDS VERIFICATION

9. Whether the 8-commit curtain-selector sequence (§6) changed actual in-game color-selection behavior or only hardened self-verifying metadata/tests around already-correct behavior — not fully traced to the generated C++ emission in this pass.
10. Whether `a696cae`'s 204-line same-sex-marriage test rewrite (§8) preserved or weakened its prior assertions — not diffed assertion-by-assertion in this pass.
11. Bathroom 2 grid-routing fixes (#17, #23, #24) — touched repeatedly in a short window (classic "fragile area" signature per the hotspot table) but not independently re-traced at the code level in this pass beyond what the companion release-gate audit already covered (confirmed the *store-click live-refresh removal* is real and complete; did not re-verify the grid-routing specifics from these three commits individually).

---

## 13. Regression ledger

| Functionality | Existed before window | Modified in window | Broken now | Restored | Currently verified | Currently broken | Uncertain |
|---|---|---|---|---|---|---|---|
| Executable overlay selection (safety) | yes (unsafe) | yes (#2) | — | n/a | **yes** — fail-closed, tested, confirmed shipped | — | — |
| Executable overlay matrix completeness | no (never complete) | no (not extended) | — | — | — | **yes** (3/16 mobile combos) | — |
| `src/` vs `work/` patcher sync | pre-existing fork | no (fork not addressed) | — | — | — | **yes**, as a risk (not active today) | — |
| Package executable-inventory validity | broken pre-window | not touched | — | — | — | **yes** (re-confirmed) | — |
| Anti-Spam/Rockhound repurchase | partially working, Cheat-Upgrades-gated | yes (#15, #29) | — | — | **yes**, per description text and code trace | — | runtime purchase flow not player-tested |
| Native/mobile renovation curtains (store-click crash route) | broken | not touched *in this window* (fixed in earlier, out-of-window work per companion audit) | — | — | statically yes | — | runtime |
| Curtain color selector metadata (8 commits) | partial | yes, additive | — | — | metadata/tests only | — | **causal link to runtime rendering** |
| Mess cheats bounds-safety | custom-bounded | yes (#16), bounds removed | — | — | — | — | **yes** |
| Mortality/aging | pre-existing, out of window | **no** | — | — | n/a (untouched) | — | — |
| GUI/backend setting wiring | working | not touched, not needed | — | — | yes (no new IDs orphaned) | — | description accuracy for changed behaviors |
| Full `work/` test suite green | — | grew substantially | — | — | — | **yes**, 2 failures | — |

---

## 14. Timeline (condensed)

- **00:01–00:46** (#1–#2): renovation overlays enabled; the fail-closed overlay-matrix safety net is built and tested the same morning — the single best piece of engineering in this window.
- **02:45–04:18** (#3, #4, #5–#9): large same-sex-marriage rewrite, a new behavior patch, then a clean 4-commit build-out of Bathroom 1 curtain colors.
- **04:48–05:28** (#10–#14): mirrored 4-commit build-out for Bathroom 2 curtain colors.
- **06:36–07:28** (#15–#16): Anti-Spam/Rockhound reversibility fixed (stage 1, still Cheat-Upgrades-gated); mess-cheat spawning simplified in a way that trades a custom safety cap for trust in native code.
- **08:11–08:40** (#17–#18): Island Events/Bathroom 2 leak work; descriptions simplified.
- **09:33–11:42** (#19–#21): privacy/dev-file packaging hardened; payload files byte-deduplicated; the description simplification from #18 is explicitly reverted.
- **12:55–15:44** (#22–#26): mobile furniture/sound QA routes, Bathroom 2 repurchase-removal, Bathroom 2 grid routing, Behavior Patches enabled, mobile QA catalog options — the highest concentration of "enable X" commits in the window, each touching the core generator and its test file.
- **20:25–20:34** (#27–#28): the long-running B160 branch is published and merged into `main` — this is also the point where the unrelated, month-old `src/` history rejoins the graph (§1), silently reintroducing the unfixed `src/offline_vf2_patcher.py` fork alongside everything else.
- **22:32** (#29): Anti-Spam/Rockhound fixed properly (stage 2, gate removed).
- **23:24** (#30, HEAD): the B162 matrix-build script is added — 19 of 32 possible combinations, still missing the same 13 mobile combinations the matrix has been missing all along, and the manifest it produces still fails the project's own executable-inventory validator.

**Unresolved consequence carried to HEAD:** a real, well-engineered safety fix (#2) coexists with a still-incomplete matrix and a still-broken package validator that the fix's own logic doesn't (and isn't meant to) address — and the final commit of the window is exactly where that incompleteness was most recently re-baked into the shipped artifact.

---

## 15. Current-HEAD completeness matrix (selected)

- ✅ Executable overlay selection fails closed instead of silently corrupting — verified end-to-end (code + test + confirmed shipped copy).
- ✅ No new GUI/backend setting disconnects introduced this window.
- ✅ Mortality/aging unaffected by this window.
- ⚠️ Anti-Spam/Rockhound repurchase — verified in source, not in a live game.
- ⚠️ Curtain color selectors — metadata/tests verified, causal link to rendering not traced.
- ⚠️ Same-sex marriage test rewrite — not diffed for weakening.
- ⚠️ Mess-cheat spawn bounds — plausible but unverified reliance on native code.
- ❌ Executable overlay matrix completeness (3/16 mobile combos).
- ❌ Package executable-inventory validator (fails on shipped ZIP).
- 🧩 `src/offline_vf2_patcher.py` — backend fork with no fix and no test coverage, currently unused but present and unaddressed.
- ❓ `work/` full-suite green run — 2 failures, one order-dependent, one environment-dependent.

---

## 16. Final verdict

1. **Did any of the last 30 commits regress previously working VF2 functionality?** No clear case of "working → broken" was found *caused by* one of these 30 commits. The closest is #16 (mess-cheat bounds), which is a risk trade, not a confirmed regression.
2. **Did Codex remove or fail to carry forward any patch options?** No top-level GUI-facing setting was removed or orphaned in this window.
3. **Are any patches currently disabled, blocked, orphaned, or unreachable?** The 13 missing mobile-overlay combinations are effectively unreachable (the patcher refuses to build them), though this predates the window.
4. **Are there plausible access violations or crash paths?** None demonstrated with a shown mechanism in this window; §9's mess-cheat change is the only candidate and is unverified, not confirmed.
5. **Are any binary patches writing unsafe or incorrect machine code?** Not demonstrated in this pass at the instruction level for this window's changes; a full instruction-level review (user's §11) was not completed within this budget.
6. **Are the mortality/aging patches internally consistent with their intended behavior?** Not applicable to this window — untouched.
7. **Does the GUI expose everything it should?** At the top-level-setting granularity, yes, for what changed in this window. Description-accuracy gaps found (both pre-existing, per the companion audit) remain open.
8. **Do all GUI options actually reach functional backend patches?** For settings touched in this window, yes, traced to existing IDs.
9. **Are all required assets present and packaged?** Not re-audited fully in this pass; the companion audit found 0 missing payload sources for the full B162 package.
10. **Are patch signatures sufficiently specific and reliable?** Not assessed at the AOB level in this pass — out of realistic budget without decompiler access.
11. **Can patches safely coexist where intended?** The overlay-selection mechanism now fails closed rather than silently corrupting when combinations conflict — a real improvement — but the underlying combination-availability gap remains.
12. **Are Codex's claimed fixes supported by actual evidence?** Mixed, itemized above: #2 (overlay selection) — yes, strongly. #15/#29 (Anti-Spam/Rockhound) — yes. #20 ("deduplicate... aliases") — yes for what it actually does, but does not fix what its name might suggest to a future reader. #16 (mess cheats) — comment's safety claim not independently verified.
13. **Is current HEAD safe for me to continue developing from?** Yes, with the two `src/`-vs-`work/` fork and packaging-validator items (§12, findings 2–3) understood and not accidentally re-triggered by future release tooling changes.
14. **Is current HEAD stable enough for personal gameplay/testing?** Likely yes for combinations within the 19 built/supported overlays; the patcher will refuse (not corrupt) anything outside that set.
15. **Is current HEAD release-worthy?** **No**, unchanged from the companion release-gate audit's conclusion, now further corroborated: the shipped package fails its own packaging validator, and the executable matrix is incomplete. The severity of the *runtime* risk is lower than that audit could show at the time (the shipped runner fails closed, not silently), but the release-blocking packaging defect itself is real, current, and independently re-confirmed in this session.

No fixes were applied. No files were modified. Awaiting authorization before any repair work begins.
