# B207 release: status at the pause (3 November 2026)

Paused on the owner's order (usage limit; resume after 6 November, 7pm Chicago). Nothing is published.

## Done
- `data/vf2/build-matrix-release-b207.json` merged as PR #489 (merge `cfad729`): prefix VF2-B207-matrix,
  exe "Virtual Families 2 - B207.exe", seeds VF2-B206-matrix (all 32), built_from main `e32fe0f` (#488),
  tree `3e9a3d284ec5ae9bb264ef4ea4891d5f880d3149`.
- Worktrees C:\vf2w\b202-release and b202-m1..m4 detached at `cfad729`. B206 seeds checked in all four parts.
- The 32-exe matrix was started (4 parts) from C:\vf2w\b202-release with
  `work\build_matrix_parallel.ps1 ... -ReleaseConfig data\vf2\build-matrix-release-b207.json
  -Worktrees C:\vf2w\b202-m1..m4 -SeedsFrom C:\vf2w\b202-release -CollectInto C:\vf2w\b202-release`.
  It was left running at the pause. Its log: the session scratchpad `b207\matrix.log`.
  Outputs: C:\vf2w\b202-m1..m4\outputs\VF2-B207-matrix-* (8 variants each), collected into
  C:\vf2w\b202-release\outputs\VF2-B207-matrix-* when all four parts finish.
- Helper scripts in this folder (tested on the B206 zip: import check 26/26; default apply 10/30; Owner's 53/30).

## Left
1. Confirm the matrix: 32 exes, 32 distinct SHA-256 (`variant_table.py`). If the collect did not run, rerun the
   command above with `-CollectOnly`. Note: each variant's patch-manifest.json says the title box draws "alpha 33h";
   #490 changed only that text (exe bytes unchanged).
2. Wait for the coordinator's SHA with BOTH #490 (30% box, `311905b`) and the vf2clip clipboard fix. Put
   C:\vf2w\b202-release on it, then build every companion DLL fresh: build_b200time, kids, history, outfits,
   refresh, unicode, `build_b200unicode.bat clip`, build_b200titlebox (runtime\native).
3. `work\export_release_variant_identities.py --matrix-prefix VF2-B207-matrix --release B207`; export with
   `work\export_release_bundle.py --release B207 --matrix-prefix VF2-B207-matrix` (DLLs default to runtime\build;
   check it passes --title-box-dll); gate `work\gate_release_zip.py --release B207 --identities
   data\vf2\release-identities-B207.json` (must print "shipped defaults match the SETTINGS table" and RELEASE GATE PASSED).
4. Suite: `scripts\run_tests_parallel.py --release --workers 2`, env VF2_VCVARS32, VF2_B200_CORE_EXE =
   C:\vf2w\vf2\outputs\VF2-B200-matrix-core\Virtual Families 2 - B200.exe, VF2_B201_CORE_EXE,
   VF2_KIDS_EXE / VF2_REFRESH_EXE / VF2_UNICODE_EXE = the B207 core exe, VF2_B200_MATRIX_GLOB = VF2-B207-matrix-*\*.exe.
5. `apply_check.ps1 -Zip <B207 zip> -Release B207 -Base <new folder>`: import check, default apply (Title Screen
   Player Name Box, Render Unicode, Copy and Paste ON; cheats, 36 goods, outfits, transparent swap, 28 children,
   Use Unicode Font OFF), Owner's Defaults apply, emulated Special Upgrades 10 / House Renovations 30.
6. docs/B207-release-notes.md (draft here), docs/b207-matrix-manifest.md, release-identities-B207.json, and
   `bundle_exported_from` in the b207 config (exes from e32fe0f, bundle from the final SHA). PR, admin-merge.
