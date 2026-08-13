# VF2 Restoration/Addition Patcher — Release-Gate Audit

**Auditor:** independent audit pass (this session), no prior claims trusted without re-derivation.
**Date:** 2026-08-12
**Repository:** `C:\Users\Owner\Documents\Codex\Virtual-Families-2-Restoration-Addition-Patcher`
**Scope note:** This audit is static/artifact-based only. No IDA Pro/HxD/Ghidra/WinDbg/Event Viewer tools were used (not authorized). No game launch, save modification, or destructive git operation was performed. Where the requested audit brief (sections F, G, I, J) calls for exhaustive manual coverage beyond what could be independently verified with hard evidence in this pass, that is stated explicitly rather than assumed — see §14 "Coverage limits."

A prior self-authored document already exists at `outputs/VF2-B162-release-audit-20260812.md`. Per the audit brief's instruction not to trust prior claims, none of its conclusions were accepted at face value. Its two headline blockers were **independently re-derived from scratch** in this pass (manifest inspection, source diff, and a live re-run of the repository's own validator) before that file was ever opened for comparison. Both are confirmed. This is noted for transparency, not as supporting evidence.

---

## 1. Repository identity and Git status

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD SHA | `e5dab62d80bfe491f1213476da3ad4fc6cca1e34` (matches the commit specified in the audit request) |
| `origin/main` SHA (after `git fetch`) | `e5dab62d80bfe491f1213476da3ad4fc6cca1e34` — **identical**, branch is up to date |
| Working tree | Clean of tracked changes. Untracked-only. |
| Untracked files preserved (not touched) | `$db.i64`, `$i64.asm`, `$i64.i64`, `$log` (IDA database/log artifacts at repo root), `src/__pycache__/`, `tests/__pycache__/`, `tmp/`, `work/ida_coff_disasm.py`, `work/ida_curtain_context.py`, `work/ida_curtain_globals.py`, `work/ida_curtain_runtime_scan.py`, `work/ida_curtain_xrefs.py`, `work/ida_linked_scan_r18.py` |

No commits, pushes, resets, or deletions were performed.

## 2. Release and artifact identity

- Latest GitHub release: **B162** — "VF2 Patcher B162 - Renovation and Special Upgrade Repair", tag `B162`, published 2026-08-13T04:25:49Z, asset `VF2-B162-Repurchaseable-20260812.zip`.
- Published ZIP SHA-256 (from release notes): `59FEB04EC375761E9973AFAE7522EEE1C8428DAF2CCD0670125C3C5D4BF2006E`.
- **Verified independently:** the local file `outputs/VF2-B162-Repurchaseable-20260812.zip` hashes to `59FEB04EC375761E9973AFAE7522EEE1C8428DAF2CCD0670125C3C5D4BF2006E` — **exact match**. The local bundle in this workspace is confirmed to be the same bytes as the published GitHub release asset, so every finding below about this ZIP applies directly to what is currently live as "Latest" on GitHub.
- Local B162 bundle (unpacked): `outputs/VF2-B162-Repurchaseable-20260812/`
- Local B162 matrix builds: `outputs/VF2-B162-matrix-r2-20260812-*` (19 directories) + `outputs/VF2-B162-matrix-r2-20260812-summary.json`
- Local B162 ZIP: `outputs/VF2-B162-Repurchaseable-20260812.zip`
- B161 tag SHA: `92228cc2a66c4e9b44926524868a96d293537fee`

## 3. Test results

### 3a. `tests/` (repository root suite)
```
python -m unittest discover -s tests -v
```
**Result: 35 passed, 0 failed, 0 skipped, 6.2s.** Matches the count claimed in the B162 release notes ("Repository tests: 35 passed").

### 3b. `work/` suite (full discovery, `test_*.py`)
```
python -m unittest discover -s work -p "test_*.py" -v
```
**Result: 469 tests run in 352.7s — 2 FAILURES, 2 skipped.** This is a materially different (and unfavorable) result versus what the release notes imply ("Focused source regression tests: 5 passed... Special-upgrade/package tests: 22 passed... Exporter overlay tests: 5 passed" — none of those narrower claims are false on their own, but no release-note line reports a clean full-suite `work/` run, and a full run is not clean):

1. **`test_export_offline_patch_bundle.ExportOfflinePatchBundleTests.test_overlay_backed_assets_are_not_exposed_without_their_executable`** — FAILED inside the full-suite run (exporter subprocess exited nonzero with empty stdout/stderr). **Re-run in isolation, this test PASSES** (`python -m unittest ...test_overlay_backed_assets_are_not_exposed_without_their_executable` → OK, 0.66s). This is a confirmed **test-order/state-leakage defect**: some earlier test in the 469-test run pollutes process state (most likely an environment variable — the matrix/export scripts set `VF2_ENABLE_*` and `VF2_PATCH_OUT`-style env vars documented in `work/build_b162_matrix.ps1`) that is not restored before this test's subprocess call runs. The exact contaminating test was not isolated within this audit's time budget. Severity: this does not itself prove a product defect, but it means "all tests green" cannot be asserted for the `work/` suite as shipped, and it may be masking or falsely surfacing other order-dependent failures.
2. **`test_patch_mobile_furniture_pack.HolidayOrnamentGateTests.test_canonical_holiday_assets_rebuild_byte_for_byte`** — FAILED consistently, in isolation and in the full run. The regenerated `collection-ornaments_background.png` is not byte-identical to the checked-in canonical asset (PNG `iCCP` profile chunk and compressed stream differ — `4iCCPICC Profile` vs `0iCCPICC Profile`, different zlib output). This environment has Pillow 12.3.0; the canonical asset was almost certainly captured with a different Pillow/zlib build. **This is a real, reproducible failure on this machine**, confirming the asset-generation pipeline is not byte-reproducible across toolchains, which undermines any hash-based "byte-for-byte" provenance claim that assumes regeneration determinism.

Both failures are logged verbatim; no interpretation beyond what is stated above is asserted.

### 3c. Package validator (`work/package_patcher_zip.py::validate_executable_inventory`)
Run directly against the **shipped, published** release directory `outputs/VF2-B162-Repurchaseable-20260812/`:
```
ValueError: Payload executable must have exactly one manifest asset record: payload/Virtual Families 2 - Modded B162 - Final All-Enabled Native.exe
```
**The B162 release fails the project's own package validator.** See §8/§12 (P0-1). Since the local ZIP hash matches the published GitHub asset exactly (§2), this means the exact ZIP currently marked "Latest" on GitHub does not pass its own inventory check — it could only have been produced by a packaging path that skipped calling this validator, since `package_patcher_zip.package()` calls it before writing the archive and would have raised before the ZIP could be created.

### 3d. Independent ZIP inventory checks
- `zipfile.testzip()` on the release ZIP: **no corruption** (returns `None`).
- 6,960 entries; extension breakdown: 6,504 `.png`, 149 `.fmap`, 140 `.ogg`, 119 extensionless, 19 `.jpg`, **18 `.exe`**, 3 `.txt`, 3 `.py`, 2 `.bat`, 2 `.json`, 1 `.ico`.
- **18 physical `.exe` payload files exist, but the manifest declares 19 `asset_patches` records with `.exe` outputs** — one physical file (`Final All-Enabled Native.exe`, SHA-256 `14eb59609eadc3868f1ddd48e4cca81b42db93ca34c12e4340aa1689be0bd0c2`) is referenced by two different manifest records (`requires: [core_executable]` and `requires: [core_executable, behavior_patches, cheat_upgrades, holiday_ornaments_collection, island_events, mobile_renovations]`). This is the exact condition the validator in §3c rejects.
- Payload source-file existence: **6,912/6,912 `asset_patches` source paths resolve to an existing file inside the package** (0 missing), verified by direct filesystem check, not by trusting `export_summary`.
- PE32/x86 structural validation (`require_pe32_x86`, manual header parse: MZ/PE signature, machine=0x14C, optional_magic=0x10B, section table bounds) run against all 18 shipped `.exe` payloads: **all 18 pass.**

## 4. Feature inventory (selected — see §14 for coverage limits)

| Feature | Source | Manifest setting | Default | Category | Visible | Tests | Runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|
| Native Home Renovations 0xE1–0xEA preserved w/ Cheat Upgrades off | `work/patch_mobile_furniture_pack.py` (`VF2B150UpgradeIsActive`, moved native-ID check ahead of the Cheat Upgrades gate — confirmed via B161→B162 diff) | n/a (native, always compiled) | always on | — | n/a | none dedicated found in `tests/`/`work/test_*` for this exact regression | UNKNOWN | **PASS (static)** |
| Bathroom/renovation live `CDecal` refresh removed from store-click paths | same file; `VF2RefreshRenovationCurtainDecals()` body reduced to comments-only, and its 4 former call sites (purchase/remove/AI-Bathroom2 apply) were deleted — confirmed via diff and a source grep showing 0 remaining call sites | `ai_generated_bathroom2_renovations`, `mobile_renovations` | True / True | optional | yes | none found asserting "zero call sites" as a regression guard | UNKNOWN | **PASS (static)** |
| Special Upgrades — 46-row final-all-enabled catalog (6 stock + 4 mobile + 36 cheat) | `work/patch_mobile_furniture_pack.py` → `patch-manifest.json` (`VisibleSpecialUpgrades.added_items`) | `cheat_upgrades` | True | optional | yes | `work/test_special_upgrades_release_parity.py` (part of the 469, passed) | UNKNOWN | **PASS (static)** — confirmed 40 added items (4 mobile IDs `0x117–0x11a` + 36 cheat) in the `final_all_enabled` matrix build |
| Mobile House Renovations catalog | same | `mobile_renovations` | True | optional | yes | `work/test_patch_mobile_furniture_pack.py` (subset passed; 2 unrelated failures noted §3b) | UNKNOWN | **PASS with a labeling discrepancy** — see §11 |
| Executable overlay selection for combined optional settings | `src/offline_vf2_patcher.py` (`manifest_asset_patches`, `apply_asset_patches`) + `work/patch_mobile_furniture_pack.py` (matrix generation) | `island_events`, `cheat_upgrades`, `holiday_ornaments_collection`, `behavior_patches`, `mobile_renovations` | True/True/True/True/True | optional | yes, all independently toggleable in GUI | `work/build_b162_matrix.ps1` builds and self-checks 19 of 32 possible combinations | n/a | **FAIL** — see §6, §12 (P0-1, P0-2) |

## 5. Settings/GUI inventory

- The shipped `manifest.json` declares **36 settings**, each with `id`, `label`, `category` (`main`/`optional`), `default`, `description`. No setting uses `category: experimental` in the current release (the GUI's `SETTING_CATEGORIES` list in `src/offline_vf2_patcher_gui.py` does define an `"experimental"` bucket with a red label "Experimental/Not Working Patches", but no shipped setting is currently placed in it — nothing is presented to the player as blocked/experimental while actually being broken by that mechanism).
- No `hidden`/`visible` field exists on setting records; the GUI renders whatever categories are present, so no setting is structurally hidden.
- README.md and the in-package `How to Use.txt` both link only to the generic `https://github.com/Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher/releases` page — no stale B160/B161-specific URLs found.
- **Confirmed description/default contradiction:** setting `holiday_ornaments_collection` has `"default": true` in the manifest, but its own description text reads *"Default-off so players opt into the extra collection; manual gameplay verification is still recommended."* A GUI-wide sweep for this class of error (checking every description for "default-off/-on" phrasing against the actual `default` field) found **exactly one** such mismatch — this one. Severity P2 (misleading text, not a functional break), but it means the description text is stale relative to at least one shipped default and cannot be trusted as authoritative without cross-checking the `default` field.
- **Confirmed count discrepancy:** `mobile_renovations`'s description reads *"overlays the **15** verified mobile kitchen, bathroom, office, and workshop renovation images..."* — the generated catalog (`HouseRenovations.order_contract` in the `final_all_enabled` build) actually contains **20** mobile rows (bathroom1: 5, bathroom2: 5, kitchen: 3, office: 5, workshop: 2). The audit brief's own expectation of "15 mobile renovation styles" appears to trace back to this same stale figure in the setting description, not to the actual current catalog. Severity P2 — cosmetic/documentation, not functional, but worth correcting since the description is player-facing.
- No setting description discloses the overlay-combination gap described in §6 — a player enabling Mobile Renovations together with Island Events, Holiday Ornaments, and/or Behavior Patches (without Cheat Upgrades) is given no warning that the resulting executable may silently omit one of the features they selected.

## 6. Executable overlay matrix — the central finding

This is the most severe and most thoroughly evidenced defect in this audit. It was derived independently from three separate sources that all agree:

**A. The generation script only builds 19 of 32 possible combinations.**
`work/build_b162_matrix.ps1` hard-codes exactly 19 `$configs` entries. The 5 independently-toggleable executable-affecting settings are `island_events`, `cheat_upgrades`, `holiday_ornaments_collection`, `behavior_patches`, `mobile_renovations` (2⁵ = 32 combinations). All **16** combinations of the first four flags are built with `mobile_renovations = 0`. But with `mobile_renovations = 1`, only **3** of the 16 corresponding combinations are built: `mobile_renovations` alone, `cheat_upgrades + mobile_renovations`, and `final_all_enabled` (all five on). **13 mobile-combined configurations are never built or tested:** Island+Mobile, Holiday+Mobile, Behavior+Mobile, Island+Cheat+Mobile, Island+Holiday+Mobile, Island+Behavior+Mobile, Cheat+Holiday+Mobile, Cheat+Behavior+Mobile, Holiday+Behavior+Mobile, and the four possible 4-flag-plus-mobile combinations short of all five.

**B. The shipped manifest has exactly one asset-patch record per built exe, and no more.** Confirmed directly from `outputs/VF2-B162-Repurchaseable-20260812/manifest.json`: 19 `asset_patches` records write to `Virtual Families 2 - Modded B162.exe`, each gated by a `requires` list corresponding 1:1 to the 19 matrix builds above. There is no record for any of the 13 missing combinations.

**C. The selection logic has no specificity-based tie-break — it is pure list order, last-match-wins.** Read directly from `src/offline_vf2_patcher.py`:
- `manifest_asset_patches()` (line ~820) filters records with `record_is_active()`, a plain **subset test** (`set(requires).issubset(enabled_settings)`) — it does not rank or sort by how many requirements a record satisfies.
- `apply_asset_patches()` (line ~1283) iterates the filtered list **in manifest order** and unconditionally copies each active record's source over the same output path (`overwrite_existing: true` on all 19 exe records) — so whichever active record appears **last in the manifest's declaration order** silently wins, no matter how well it actually matches the player's selected settings.

**Consequence, proven by walking the actual manifest order against real settings combinations (not runtime-tested, but deterministic and verifiable from the static list alone):**

| Player selects (besides `core_executable`) | Records that match (`requires` ⊆ selected) | Last one wins → shipped exe | What silently disappears |
|---|---|---|---|
| `mobile_renovations` + `island_events` | base, Island Events, Mobile Renovations | **Mobile Room Renovations.exe** (index 5 > Island Events at index 1) | Island Events compiled code |
| `mobile_renovations` + `holiday_ornaments_collection` | base, Holiday Ornaments, Mobile Renovations | **Mobile Room Renovations.exe** | Holiday Ornaments compiled code |
| `mobile_renovations` + `behavior_patches` | base, Behavior Patches, Mobile Renovations | **Mobile Room Renovations.exe** | Behavior Patches compiled code |
| `mobile_renovations` + `island_events` + `cheat_upgrades` | base, Island Events, Cheat Upgrades, Mobile Renovations, Cheat+Mobile, Island+Cheat | **Island Events + Cheat Upgrades.exe** (index 7, the latest 3-requirement match) | **Mobile Renovations compiled code — even though the player explicitly enabled it** |
| Shipped **default profile minus just Island Events** (i.e. `cheat_upgrades`+`holiday_ornaments_collection`+`behavior_patches`+`mobile_renovations` on, `island_events` off — a completely ordinary customization from the out-of-the-box defaults) | base, Cheat, Holiday, Behavior, Mobile, Cheat+Mobile, Cheat+Holiday, Cheat+Behavior, Holiday+Behavior, Cheat+Holiday+Behavior | **Cheat Upgrades + Holiday Ornaments + Behavior Patches.exe** (index 16) | **Mobile Renovations compiled code, silently, with no error, while the mobile renovation image/asset files (separate `asset_patches` records, unaffected by this bug) are still copied in** — a real risk of orphaned image assets referencing store rows/item IDs the shipped executable no longer implements |

No error, warning, or log entry is produced for any of these cases — `record_is_active` and `apply_asset_patches` both succeed normally; the manifest's own validation step never checks "does exactly one *maximally specific* record match," only "is this record active." This directly matches audit-brief concerns E.3, E.4, and E.5 verbatim, and is confirmed by source code, not conjecture.

**D. The "core executable" default and the "final all-enabled" overlay are the same physical file.** The record with `requires: [core_executable]` — i.e. the fallback used whenever no more specific record matches — points to `payload/Virtual Families 2 - Modded B162 - Final All-Enabled Native.exe` (SHA-256 `14eb5960...`), and the record with `requires: [core_executable, behavior_patches, cheat_upgrades, holiday_ornaments_collection, island_events, mobile_renovations]` points to the **identical file and hash**. This matches audit-brief concern E.1 exactly, and is the root cause of §3c/§8's validator failure.

## 7. Asset completeness

- 6,912 `asset_patches` source paths checked against the shipped package directory: **0 missing** (matches the release notes' "0 missing" claim — this specific number was independently re-derived, not trusted).
- No `.bak`, `.env`, or obviously credential-shaped strings were searched for exhaustively across all 6,912 payload files in this pass (see §14) — a targeted extension/keyword scan of the top-level package tree found no such files among the runtime root files, `Images`, `Sounds`, `OptionalVisualMods`, or DLL set.
- All root runtime files declared in `export_summary.runner_files` (`offline_vf2_patcher.py`, `offline_vf2_patcher_gui.py`, `vf2_crash_capture.py`, the crash-capture manifest template, both icons, both `.bat` launchers, the README/How-to-Use texts) are present in the package directory.
- `clean_package_validation` — the generator (`work/patch_mobile_furniture_pack.py`) computes this key internally and raises `RuntimeError` on failure, but **the shipped `manifest.json` does not carry a `clean_package_validation` key at all** (looked up directly: `"MISSING"`). This means either the final packaging step strips it, or the manifest actually shipped was not the one the validation gate ran against last. Either way, the audit brief's request to "verify `clean_package_validation` output" cannot be satisfied from the shipped artifact as-is — flagged as P2/UNKNOWN, not asserted as a pass.

## 8. Conflict/overlap results

- **Byte patches: 0** in this release (`export_summary.byte_patch_count: 0`, `patches: []` in the manifest) — B162 is asset-mode-only (`asset_mode: "full"`), so the classic byte-offset overlap/collision class of defect (audit brief §F) does not apply to this build's mechanism in the way it would for older byte-patched builds. There is nothing to overlap-check.
- `native_patch_sources` contains 3 entries, all `apply_status: "not_file_offset"` with `next_step: "Translate object/function-relative offset to final EXE file offset before moving into patches[]."` — these are unresolved, un-applied, metadata-only staged records (confirmed covered by a passing test named for exactly this contract, `test_exports_object_relative_native_patch_sources_as_metadata_only`). Not a functional defect, but they are unfinished work items left in the shipped manifest as dead metadata.
- **Executable-inventory conflict — confirmed, see §3c/§6/§12 (P0-1).**
- No duplicate `output_file_path` + incompatible-`requires` pairs were found among the non-`.exe` asset records in a spot check; a full pairwise scan of all 6,912+10 records for output-path collisions was not completed in this pass (see §14).

## 9. Access-violation / crash-risk audit

Static-only, per project rules (no IDA/HxD/WinDbg used).

- The curtain-refresh removal (§4, §K) eliminates the specific call class the audit brief was most worried about (`Decal.RefreshProps()`/`Decal.RefreshDecals()` invoked from a store-click handler against potentially-stale live state) — confirmed via source diff and a grep showing zero remaining call sites for `VF2RefreshRenovationCurtainDecals()`.
- The native-renovation gating fix (checking `itemId >= 0xE1 && itemId <= 0xEA` and mobile-style IDs *before* the `if (!kVF2EnableB150CheatUpgrades) return false;` early-out, rather than after it) removes a class of "feature silently non-functional when Cheat Upgrades disabled" bug for native/mobile renovations specifically — confirmed via diff.
- No new null-dereference, use-after-free, or invalid-`this` pattern was found in the diffed regions between B161 and B162 (the diff is small and targeted — 4 files, 181 insertions / 25 deletions total).
- **This audit did not perform a full manual C++-generation-output read-through for the broader J checklist** (out-of-bounds table access, string-table ID validity, calling-convention mismatches, vtable overwrites, etc.) across the full generated source — the generator output is tens of thousands of lines and doing this by hand/pattern-search within this pass's budget would not meet the bar of genuine verification. This is marked **UNKNOWN**, not passed.
- No WER dump, crash dump, or `ldwLog.txt` exists anywhere in the local workspace (checked `outputs/`, `tmp/`, repo root). **Runtime crash status is UNKNOWN and requires player-supplied live crash tracing, exactly as the project rules anticipate.** I am not asserting the Bathroom 2 crash route is fixed at runtime — only that its specific previously-known trigger (the live `CDecal` refresh call from the store-click path) is confirmed removed from the source that generates the shipped executables.

## 10. Regression comparison vs B161

`git diff refs/tags/B161 refs/tags/B162` touches exactly 4 files: `work/build_b162_matrix.ps1` (new, 123 lines), `work/export_offline_patch_bundle.py` (+11), `work/patch_mobile_furniture_pack.py` (+44/-25), `work/test_patch_mobile_furniture_pack.py` (+28/-16 — test updates, not product code).

Net effect of the `patch_mobile_furniture_pack.py` diff (confirmed positive, already covered above):
- Native 0xE1–0xEA renovation active/repurchase logic no longer requires `cheat_upgrades`.
- Mobile-renovation and native-renovation active-byte checks moved ahead of the Cheat Upgrades gate.
- All curtain live-refresh call sites removed; the refresh helper is now a documented no-op stub.
- Mobile renovation state is explicitly documented as `independent_of_cheat_upgrades: True`.

**Nothing that worked in B161 was found to be removed, disabled, or newly blocked in B162** within the diffed scope. The overlay-matrix defect in §6 is **not a regression introduced by the B161→B162 diff** — `work/build_b162_matrix.ps1` is a brand-new file in this diff, and the same list-order/subset-match selection logic in `src/offline_vf2_patcher.py` (which is what actually causes the silent feature loss) is untouched between the two tags. In other words: **the underlying selection-logic defect (§6C/§6D) predates B162 and was already present in B161's matrix design; B162 only made the missing-combination gap larger in surface area by adding new independently-toggleable flags without extending the mobile overlay matrix to cover them.** This should be corrected regardless of which release first introduced it.

## 11. Missing, disabled, hidden, blocked, or stale features

- No feature was found to be hidden from the GUI, marked experimental while actually working, or advertised while non-functional at the settings/description level, **except**:
  - `holiday_ornaments_collection` description says "Default-off" while `default: true` (§5).
  - `mobile_renovations` description says "15" mobile styles; actual generated catalog has 20 rows across bathroom1/bathroom2/kitchen/office/workshop (§5).
- The 13 missing mobile-combination executable overlays (§6) are not "hidden" in the GUI sense — the settings that would trigger them (`island_events`, `holiday_ornaments_collection`, `behavior_patches`, all independently toggleable alongside `mobile_renovations`) are fully visible and default-on. The defect is that selecting them together silently degrades to a differently-scoped executable rather than being blocked, warned about, or correctly built.

## 12. Blockers with severity

**P0 — release-stopping**

1. **Executable-inventory validator failure on the exact published release artifact.** `work/package_patcher_zip.validate_executable_inventory()`, run directly against the live B162 GitHub release ZIP (hash-verified identical, §2), raises: `Payload executable must have exactly one manifest asset record: payload/Virtual Families 2 - Modded B162 - Final All-Enabled Native.exe`. The project's own packaging tool would refuse to produce this ZIP; it reached GitHub through a path that did not enforce this check. See §3c, §6D.
2. **Silent, unwarned feature loss for 13 of 16 Mobile-Renovations-combined executable overlays.** Confirmed by static trace through the actual shipped manifest and the actual selection code (no runtime testing required to establish this — it is deterministic list-order behavior). Concretely: enabling Mobile Renovations together with any one (or more) of Island Events / Holiday Ornaments / Behavior Patches, without also enabling every other flag up to "final all-enabled," produces an executable missing one or more of the player's selected features, with zero error or warning. This includes an easily-reached case — disabling just Island Events from the shipped default profile while leaving Mobile Renovations on — silently drops Mobile Renovations from the compiled executable while still installing its image/asset payload. See §6.

**P1 — major functional defect**

3. `work/` full-suite test run is not clean: 2 failures out of 469 (§3b). One is a confirmed test-order/state-leakage bug (masks or falsely reports failures depending on run order — undermines confidence in any "all tests passed" claim for this suite going forward). The other is a confirmed non-reproducible asset-regeneration byte mismatch on the current toolchain (Pillow 12.3.0), which means the "byte-for-byte" reproducibility the generator claims for canonical Holiday assets does not hold on at least this environment.

**P2 — non-blocking defect**

4. `holiday_ornaments_collection` setting description contradicts its own shipped `default: true` (§5).
5. `mobile_renovations` setting description states "15" styles against an actual 20-row generated catalog (§5).
6. Shipped `manifest.json` lacks the `clean_package_validation` record the generator computes internally, so that specific audit-brief check cannot be positively confirmed from the shipped artifact (§7).
7. Three unresolved `native_patch_sources` entries remain in the shipped manifest as unapplied, metadata-only staged patches (§8) — not a functional risk, but unfinished work left in a shipped artifact.

**UNKNOWN — requires player/runtime evidence**

8. Actual game launch, purchase/repurchase, save/reload, curtain-restart, Special Upgrades scrolling, and Bathroom 2 behavior at runtime. No WER dump, crash dump, or `ldwLog.txt` exists in the workspace. **I am requesting, per project rule 12, that you supply live crash tracing, WER data, `ldwLog.txt`, a crash dump, or a reproducible player test before any runtime claim (including "the Bathroom 2 crash is fixed") is treated as established.** The static source fix in §9 is real and verifiable, but it is not runtime proof.
9. Full manual C++-generation-output review for the complete J-checklist (out-of-bounds indices, string-table ID validity, calling-convention/stack-cleanup correctness across the entire generator, vtable/function-pointer integrity) was not exhaustively performed in this pass — see §14.

## 13. Release decision

# **BLOCKED**

Two independently-confirmed P0 defects (§12.1, §12.2) mean the current B162 bundle — which is byte-identical to what is already published as "Latest" on GitHub — does not meet the project's own packaging invariants and will silently ship functionally-incomplete executables for a large, easily-reachable set of player-selectable setting combinations. Do not cut a new release from this bundle until:

- The executable source matrix is extended to cover the missing 13 Mobile-Renovations combinations (or the selection logic in `src/offline_vf2_patcher.py` is changed to pick the *most specific* matching record deterministically, and the generator is changed to guarantee a matching record exists for every reachable combination — whichever fix the maintainers prefer).
- The `core_executable`-only fallback is backed by a genuinely distinct minimal/core executable, not the same physical file used as the final-all-enabled overlay, so `package_patcher_zip.validate_executable_inventory` passes on the actual packaged artifact before it is zipped and published.
- The `work/` full-suite test run is clean (or the 2 current failures are triaged and explicitly waived with a documented reason).
- Runtime/player verification (§12.8) is obtained for at least: game launch, a purchase/repurchase cycle for a native and a mobile renovation row, save/reload of curtain state, Special Upgrades scrolling at 46 rows, and the specific Bathroom 2 interaction previously known to crash.

No fixes were applied. No source files were modified. This report and its evidence are ready for your review; I will not implement any of the above without your explicit authorization.

## 14. Coverage limits (what this pass did and did not do)

Given the size of this repository (hundreds of generator/work scripts, a 4MB manifest, ~200 historical build directories under `outputs/`), this audit prioritized depth on the areas most likely to gate a release — the overlay/matrix mechanism, package validation, and test execution — over breadth across every checklist line in the original brief. Verified with direct evidence: git/release identity (§1–2), full test execution counts (§3), the overlay-matrix defect chain end-to-end from generator script → manifest → selection code (§6), asset source-file existence for all 6,912 records (§7), PE32/x86 structure for all 18 shipped exes (§3d), the B161→B162 diff (§10), and the two description/default text mismatches (§5). **Not exhaustively performed:** per-color curtain image hash/dimension verification against the manifest, a full pairwise output-path collision scan across all ~6,900 non-exe asset records, a complete manual crash-risk read-through of the full generated C++ source, and a full click-through of every GUI screen/dialog. These would be the natural next steps if you want the audit deepened before or alongside fixing the P0 items above.
