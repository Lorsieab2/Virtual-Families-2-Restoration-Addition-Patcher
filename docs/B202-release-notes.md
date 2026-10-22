# VF2 B202 release notes

**The patcher bundle.** Built from `main` at `0f7dc32` (PR #424, Up to 28 Children, on top of PR #423, Time Controls), seeded from the B201 matrix.

B202 adds one setting and removes none: the 37 settings of B201 plus **Up to 28 Children**, 38 in all. The 32 executable variants are the same feature combinations as B201.

## Up to 28 Children (Experimental, off by default) (#424)

Virtual Families 2 keeps at most 6 children per generation in its Family Tree, and a household holds 30 villagers (2 parents and 28 children). With **Up to 28 Children** on, a family can have up to 28 children. Only the first 6 appear in the Family Tree; children 7 to 28 are kept in a separate file beside the save (`Virtual Families 2 Patcher Data\Children\<save file>.dat`), so they never overwrite Family Tree entries, and every child can be chosen to inherit the house in Next Generation. Twins and triplets near the limit are clamped, never past 28. The save file itself is unchanged.

It is in its own **Experimental** section of the patcher, **off by default**, and **Enable All leaves it off**: it has not yet been tested in a running game, so back up your saves before using it. It comes from its own companion DLL (`vf2kids_b200.dll`), which the executable loads only when the setting is on; with it off the executable never looks for the DLL and two patcher functions that now ask the Family Tree for free child slots answer exactly as before. Design, pins and evidence: `docs/b200-up-to-28-children.md`.

## Time Controls (unchanged since B201)

The Time Controls DLL in this bundle is the B201 file itself (SHA-256 `3ea0a2a5...`); its source has not changed.

## Checks

- All 32 variants built from the commit above, 32 distinct executables, every one different from B201's; hashes in `docs/b202-matrix-manifest.md`, identities in `data/vf2/release-identities-B202.json`.
- Every executable: both dormant loader bytes are 0 and the children table is empty as built; both loaders work end to end under emulation (at the link address and relocated); both features' pins resolve in all 32. Static and emulated evidence only.
- The bundle reproduces the build on a clean install (8194 of 8194 files) and passed the release gate: **RELEASE GATE PASSED**, no features lost against 22 retained releases (B179 to B201).
- **No live test** of Up to 28 Children or of Time Controls has been done.
- Asset: `VF2-B202-Release.zip`, 146,820,349 bytes, SHA-256 `8f0bc50284f33344ba94a664eb26c15646e40352bfa795a6904cd9c2b84c2ae2`.
