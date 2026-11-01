# B206 matrix manifest

Built on 1 November 2026 from main `2ff4152` (the merge of PR #472; tree `81181dafcf5c7d3ecd0394eebb2a0b86e118ba3c`, recorded in `data/vf2/build-matrix-release-b206.json`, merged as #473) with `work/release_parallel.ps1` and `work/build_matrix_parallel.ps1`: eight parts of `work/build_matrix.ps1` in eight worktrees of one commit, then collected. 32 variants, seeded from the B205 matrix, 32 distinct executables.

Every executable carries:
- the two new dormant bytes, `.vf2free` (Free and Guaranteed Cheats) and `.vf2clth` (All outfits and hairstyles always for sale), read by the store page hooks;
- the House Renovations fix.

Emulated on all 32: Special Upgrades lists 53 rows (50 with `.vf2free` 0) with Cheat Upgrades and 10 without; House Renovations lists 30 rows with Mobile Renovations and 10 without.

Release DLLs, built fresh from this commit and shipped in the bundle:

- `vf2time_b200.dll`: SHA-256 `494f9cab35702fd173feeb88837307506d4ad2c417a84137d1378e68a68ee787`.
- `vf2kids_b200.dll`: SHA-256 `4446eb82b264ac67313232e76bb34244b5956f032313a1b36376a8d313a95563`.
- `vf2history_b200.dll`: SHA-256 `53001f477bc40dac5d64c2b180906bc6b847ff18f630868c1e570fba26978d95`.
- `vf2outfits_b200.dll`: SHA-256 `7a20d096900197635d4f55c04ee3d1c796a3179b97e8bd2322edc41598bc5af0`.
- `vf2refresh_b200.dll`: SHA-256 `a82b2b877b8c146dfc672c94e80b6082f582e959353a96f46ba911700165a450`.

| Variant | Size (bytes) | SHA-256 |
|---|---|---|
| behavior_patches | 1814016 | `2105d37d2b512c8770e826b87a25616bf5edf3cce6a5af7983d2fa2ec629cb02` |
| behavior_patches_mobile_renovations | 1827840 | `1140688a43d16185d4df4f22adcc6e82c01c67471b122b3cecffb912efde815c` |
| cheat_upgrades | 1769984 | `d3156aee4f2176bd6d6b9fe90c2c4f142d64cd2880da6ca32dcd566a53c07b2f` |
| cheat_upgrades_behavior_patches | 1816064 | `43c937aee43b7692ca6c9a83a22b671e05fe82238ba54bf5d7a11ff0cd930a62` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1829888 | `4999db630dce141a72b040b83c5ff1e8267263a03db2959c8567b40a7b613335` |
| cheat_upgrades_holiday_ornaments | 1773056 | `961b90956a69f7d8c796ee1761bb0aae57f7ded018418dee4601786276b52fa6` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1818112 | `3c77346f7318d8fa1c4800d9a825c22f318c8bdec687cf44e374edef6c4925fc` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1831936 | `8b130a8448b09a1c5d3201281761e15498cb5b91f9c80a9b6f34be88855d1cf9` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1786880 | `fa00d23268df989b87bdc4c94a6538df3da714b3125f327fffb2c1a7ef29b21e` |
| cheat_upgrades_mobile_renovations | 1784320 | `49e64724f89295f17d8abdf2de63e2e4867697436568c9fd74678807631b2c00` |
| core | 1768448 | `0d3bc19720f5522aa9bf46ff408b5982583317d2fc742c7dab8aa4dd9b401ae4` |
| final_all_enabled | 1862656 | `b18182da17da155463e2da9f2d267c0fee33189fa4725aac35401844d2a490b7` |
| holiday_ornaments | 1771008 | `1fc69bcf0d095816df7dd996320bcea38b18dcf7a5cefb2b94255a34a951c090` |
| holiday_ornaments_behavior_patches | 1816576 | `be8be9417a8544d6007454521742bc10f755d0da1f01dfa24e61c291f106edd5` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1830400 | `92d89158c8ce02a7b025a176715459c225a1af1f8880f00b94845505d508cd88` |
| holiday_ornaments_mobile_renovations | 1785344 | `ee686bfea96fc92c7610b5b4246e8db9c6ae2e774564a03892c4133eaf5e02e8` |
| island_events | 1798144 | `668c527eb642f6603e9b012322bdb24d2de901c7180616b4bba36515c793a674` |
| island_events_behavior_patches | 1843712 | `3ba1fbba6f27cc0f69a7d84e61bf788b03ca19fa07e1d87c8eba811a1c644878` |
| island_events_behavior_patches_mobile_renovations | 1858048 | `e02fb7212c7981c04550ff6d787e7cbac3d5cfb5f33a4689183a71aea0b92427` |
| island_events_cheat_upgrades | 1801216 | `0cdec77eab3d78d53e1044d345ced8dba3e7f586656bab83c1ec2ee269688434` |
| island_events_cheat_upgrades_behavior_patches | 1845760 | `f2890c990a5a4d7d00cb719327a54c3e765367e880c17f2b00136a23c39535ac` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1860096 | `49b0093eef9b11769aae9671744feba47c8eec3a5f43a32faea6ba42c8bcd7d6` |
| island_events_cheat_upgrades_holiday_ornaments | 1803776 | `438fa6c3593fe53ef69ba56f83424970363a5f12f4cbe5475e1f22fbd87b7b09` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1849344 | `06e4604a41277a0cfe5716e60f4316004d4f38b569f5dc6f7109f03910a65482` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1817600 | `eae3bf5d56311acbfa25a29d8f4969ea52365f1e44de6f3e87b619b8ac103608` |
| island_events_cheat_upgrades_mobile_renovations | 1815040 | `abafd3a6e961a9df882b4f2a68faa2e047121c6122ab4861c76a522892e904c3` |
| island_events_holiday_ornaments | 1801728 | `a985b30a116219a360764e9f668b537aea71f5cb8c7135c23622f20fdc24ecc3` |
| island_events_holiday_ornaments_behavior_patches | 1846784 | `aa3aad338a7dca15b14b08a1b5b48605701539d78abdc18e770722c63e54f9fd` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1860608 | `c3dfb4ddde382222c38d2f004d7c0c9023cfe537d1a0268d98c667377b4a40da` |
| island_events_holiday_ornaments_mobile_renovations | 1815552 | `ccf8bdbf42da00cb03e8eeb36e65f744c8d93b92d3e4760466f38f8b9456a722` |
| island_events_mobile_renovations | 1812480 | `e584bf6897c60364b3609693fa7103ff4261e2107412eee6da650369a9e8f51f` |
| mobile_renovations | 1782272 | `ab3b9d3c4aa25586736e2d20d9d184ba77fc345a6d49a737a235fba2d3d88fbb` |
