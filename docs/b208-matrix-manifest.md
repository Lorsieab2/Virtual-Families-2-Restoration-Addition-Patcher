# B208 matrix manifest

Built on 3 November 2026 from main `bb52bcd` (the merge of PR #507; recorded in `data/vf2/build-matrix-release-b208.json`, merged as #509) with `work/build_matrix_parallel.ps1`: four parts of `work/build_matrix.ps1` in four worktrees of one commit, then collected. 32 variants, seeded from the B207 matrix, 32 distinct executables. Every executable gains the Translations setting byte (`.vf2trns`).

Release DLLs, built fresh from main `015d456` (the bundle is exported from it; #508 and #510 changed only the README, tests and the translations folder):

- `vf2time_b200.dll`: SHA-256 `6e6cbb56fdda741c0ae4953cf8544b615faf996653b66ae1b828d8c767f2543a`.
- `vf2kids_b200.dll`: SHA-256 `978b95d2d4a1e2293de80218c8caf76f8745e8d764d2a9d9a366a3ad4a764289`.
- `vf2history_b200.dll`: SHA-256 `b0fa281430ee629ed6a8380e32f07886727d67da7bd0ace8295c180636b0bbdd`.
- `vf2outfits_b200.dll`: SHA-256 `ae4412e31755408ed2d3126bbd6046e918e95654698fdf9a803fdb232588b031`.
- `vf2refresh_b200.dll`: SHA-256 `5ea6432e279c792d30c0a5117fff955342451f3d32f903564e2c1323bc323cec`.
- `vf2unicode_b200.dll`: SHA-256 `421366503a661a7397439cdd7dab65057c15dc76ebab900b385c8e3856ded1ea`.
- `vf2clip_b200.dll`: SHA-256 `e0df62496dd547d97275a2769a410b2fa35eb569b8ffb20fa00258094197d31b`.
- `vf2titlebox_b200.dll`: SHA-256 `26c1a522e0a4e84e338e40ea9c823d5c7f711e0a98d9e9bf4340140b9642f300`.
- `vf2tr_b200.dll`: SHA-256 `9b89a5b069e2a72708c49f6c6a8b422601f3256c83589c6c58a2319acf12ddc7`.

| Variant | Size (bytes) | SHA-256 |
|---|---|---|
| behavior_patches | 1817088 | `b9e7b6b618348013f6783443ef10f3751cb3309e1d2816e4af58c4cc6b52ba6b` |
| behavior_patches_mobile_renovations | 1831424 | `445bbd61ad72797b662f83ccdd391b40d50c925e065aa64d65d6a262a87f754b` |
| cheat_upgrades | 1773568 | `efd1a99de096e03bc25494f42ede28237e11c95d65851d0ae5cfb9d7f6c1f0c2` |
| cheat_upgrades_behavior_patches | 1819648 | `777bd870a99a0cdf516bb4d309925b5644d9f1e94ab24c204b9eaf2483a43bac` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1833472 | `57c179b9a984317a830344a0b10d1fcc0c8f3381fd7a92cbc81bbaa4c2b54c14` |
| cheat_upgrades_holiday_ornaments | 1776640 | `56ff1995eeb286962a091a7d8a2cb8c68966021766ef7fc0620b83d423c5b363` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1821696 | `9f838b7551a715b20ce88493f4650a011f6bf5a1785045385c562418145aa1e7` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1836032 | `0fa47e65cfaa6afcd50c8478d5dc62ca2541d10c456886714952b637e07eeb97` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1790976 | `5b53253cdd8410ba3354204be0ead48d2b60ec9ab8822f539818a97f6370670f` |
| cheat_upgrades_mobile_renovations | 1787392 | `717f329027245de01733db6720fe479dad9b7e6fd62c9bff3d79af289bb2b5c8` |
| core | 1772032 | `8932451fbdfaf13aab6d4de5ab4800d717b9bd48da5cf64022c3823dd893f182` |
| final_all_enabled | 1866240 | `d14b7c9c78a0af6b609d754ec8fdba3e56bb2cf8e9e4a2294d2b519b74e4fe76` |
| holiday_ornaments | 1774592 | `e2b16035a9dd43b5a7575ac0015da06aff510fb9ff8c87e061b101d696ce2503` |
| holiday_ornaments_behavior_patches | 1819648 | `7680354bb01c4815a29bae1aec18c520ac83ee60aa70d778fa6c4158f8c9623c` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1834496 | `4bd754ef55edb53ce7b941bae6b7aff6c86290dd29673e2039f221bd78ce1965` |
| holiday_ornaments_mobile_renovations | 1788928 | `eeb1cd64a33958e3d749a7f7626f62d0138ff47fe28ecb54b43a103a06776965` |
| island_events | 1802752 | `a0523443f69f05a76fe964f8e9c889242ec3bcaab1739682820f19a81bce06fa` |
| island_events_behavior_patches | 1847296 | `2daeaa13c1bc876868319d01aae92d2898f9d3ef9f73caafe9b4eddd2c86cf90` |
| island_events_behavior_patches_mobile_renovations | 1861632 | `940a39b6c91ac82e262ea62d6c9f84a2cfff4445f4ae88f9ba6b42effd05bca6` |
| island_events_cheat_upgrades | 1804288 | `3eb4af30f9443aca4a1228881efeb4eb7455c4093f6a936ddcaa7c77bc969ac8` |
| island_events_cheat_upgrades_behavior_patches | 1849856 | `274459a4b69c5f83b6a75f82c667c80884c52853888c0a158ad371f5e7decfdf` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1863680 | `824b5a588b589a10e2c8764dc7494deb30e9daa04bb1e5dbae862894c11f50f1` |
| island_events_cheat_upgrades_holiday_ornaments | 1806848 | `a960891639c758916ea63a4b71a878f367b3cbdcab2814eff9df26b7cbeded89` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1852928 | `6c52953af97c49a69258ef69850ad58830eff16732e49e3e5872f471bcfe6354` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1821184 | `e182305ab9b16b6ed196f6a84af8e374da9e6a4f8b68f511361a3c2abd086e15` |
| island_events_cheat_upgrades_mobile_renovations | 1818112 | `235d0c03fb4556e440c42baa05857e256ffbebbac0d4786895c69e043eb6a8fc` |
| island_events_holiday_ornaments | 1805312 | `dd5f16b11a0efb1e491cf9b95160349fbd9023df4f93ec4fcd3dc86013e9821d` |
| island_events_holiday_ornaments_behavior_patches | 1850368 | `986b8f4d23457ed1b9dc6af195f7db0e04c4c5fabe35cd04d78156d6d43d0829` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1864192 | `aa1c85671dda77f6b2340990e1d8863772319c3118f5c65896781f0c63a45486` |
| island_events_holiday_ornaments_mobile_renovations | 1819136 | `be05ae6151aa3a04739670c66b5a1d1586e0abc783ef77de3f22b89b46c7d8a5` |
| island_events_mobile_renovations | 1816064 | `0c2abde06acf38cea6bf65b66415cfd11fc2b4f431fd30d16be33e730cf75b78` |
| mobile_renovations | 1786368 | `2b4a424d071dca92fc33c31f0f7b8c71a02f66b1dab43d51cc4850eede33b077` |
