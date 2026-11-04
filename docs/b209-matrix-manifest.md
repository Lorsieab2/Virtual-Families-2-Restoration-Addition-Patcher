# B209 matrix manifest

Built on 4 November 2026 from main `9d0c9f5` (the merge of PR #521; recorded in `data/vf2/build-matrix-release-b209.json`, merged as #522) with `work/build_matrix_parallel.ps1`: four parts of `work/build_matrix.ps1` in four worktrees of one commit, then collected. 32 variants, seeded from the B208 matrix, 32 distinct executables. Every executable gains the patch lines' own string-table records (#516).

Release DLLs (as shipped in the zip), built fresh from main `010c68f` (the bundle is exported from it; #523 to #526 changed only the DLLs, the translation files and tests):

- `vf2time_b200.dll`: SHA-256 `854f8f215930196ddf44376cbedb8d069e20105bcd19d58ca3ec9fab1cc8b9ff`.
- `vf2kids_b200.dll`: SHA-256 `925b8d437eb4260e464fc2518b5e7304941155e0d25825590175aac7f231882a`.
- `vf2history_b200.dll`: SHA-256 `cad32d8e594c12521ba9bc3876aaeb11893dcb522395c9a8e2905c6975f4086a`.
- `vf2outfits_b200.dll`: SHA-256 `d8773fef8b5ae8709db8e0bbf78b29c0331e86061c914dcb73da95fff127d9b3`.
- `vf2refresh_b200.dll`: SHA-256 `d2b24ab3efe660e5fac963ac74f490e2d4bae8d75c5b57c2dc1dbb48e9960581`.
- `vf2unicode_b200.dll`: SHA-256 `2fb4ecde723e194101710dbc96b9206292f4ae001a96349c7dc4ec257f808e6e`.
- `vf2clip_b200.dll`: SHA-256 `364ed934e891f71354fd905054035c46184d059feab368efe02164b7063bf7a7`.
- `vf2titlebox_b200.dll`: SHA-256 `d855cb00aaac7fe2d61ad95d82635db091b04d42359eeb88578e69368f8c906e`.
- `vf2tr_b200.dll`: SHA-256 `fe4268d1940ac417fd9c41bdb2591ea5a4e738950d3c63d08faafb284a214279`.

| Variant | Size (bytes) | SHA-256 |
|---|---|---|
| behavior_patches | 1817600 | `5711b7a3264d204a7de7e2d8ac6593e73b913bf60478ffbc90197f7a3197c54a` |
| behavior_patches_mobile_renovations | 1831424 | `f3117738c9af0ac903468ce854ad3698716523070642776e9265265b988f6d2d` |
| cheat_upgrades | 1774080 | `53524503227135eda73054d3aa2529e5880cf4774a20a176565d57234e9f2323` |
| cheat_upgrades_behavior_patches | 1820160 | `60017fc8f5e173fada6399efd0889b553ac129a838e2899bb774777bff1649d2` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1833984 | `f848f328ac43821fb3347a6967aaa2748f3fbf01ea1a59a05848ffe79858fe53` |
| cheat_upgrades_holiday_ornaments | 1777152 | `d2eeac349c76e23bd4da37e787bd36a41e2d5f60be1f328d8637a698c22471a8` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1822720 | `1f1aeeae396fed540e7560eb8e3df5be51bd8951b2c1ee8cb216daef6fad15a3` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1837056 | `1f73377736ad366536505f369e3f92cc2cd971619532d2d541874fe211b4cc4d` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1791488 | `07177e7895a0f958787c6bb807d70e4a7717f67618394e1bbff9ef277d2140be` |
| cheat_upgrades_mobile_renovations | 1788928 | `a24955c5c9b167ba71f41c6bab44a8dbfb75879cf70098e44c84e0deb40d9fe3` |
| core | 1772544 | `82c6dd61c7088ec5ae82da1df614600dee7707fc75c446954a80c546eb86907d` |
| final_all_enabled | 1867264 | `0cef07540c02b35d1305a8d52a7b7c12b52b7f523ee92af780ce6ac35599f4d0` |
| holiday_ornaments | 1775104 | `f835091c3bfe03c6d4dc263474f028e09069de1514618d93e1bd6418769aa3c8` |
| holiday_ornaments_behavior_patches | 1820160 | `9b48510dd046f7cf3645f188ba2aaac35aca7cf83781107ef8641a407f49877c` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1834496 | `cb8e79769937161a02c141a4405e9b217dd0c2d3c13849415304ee3f9252b3b3` |
| holiday_ornaments_mobile_renovations | 1789440 | `c77cb1b6e1ebcbb5f9578f65e9531e0a627fc47daa1c1215a496f431df1a77d5` |
| island_events | 1803264 | `510410add40c8c61417241b28c0f7f39bb3209b9d372e3bb47a9086123f3d157` |
| island_events_behavior_patches | 1847808 | `195ddc9cb129dd230b0dbbf403b932cb37770d7dff40f60fe23ea76bb10f461f` |
| island_events_behavior_patches_mobile_renovations | 1862144 | `1b4946db48ecc09ffa854e53ca25e90b06f8f57983a409a3a21d89f78fe04349` |
| island_events_cheat_upgrades | 1805312 | `43871ba716d73499651d1511a6e74761f433e89013dc985f47d9eec5d3068165` |
| island_events_cheat_upgrades_behavior_patches | 1850368 | `7ddb1d52fee15fcc33921b371643a8f30927ff7456b4b870047410016023f18a` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1864192 | `49be14453bcc7c0d1f0b4a1b376b840b1a373c99449157ec741520ce82a1bfe8` |
| island_events_cheat_upgrades_holiday_ornaments | 1807360 | `83f5bdf3b11384a65a7b59d0b4950a30bcbee11951ff86e5c8f9fb54531b2f9d` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1853440 | `654058945d870a95a2c947325ac86053e8ac1269b82eb02c817952565c2fdc48` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1821696 | `802bab03a99b3bfa6551dc4881706a6ef4a723603ed7eb711a1dbd3ab9b308a5` |
| island_events_cheat_upgrades_mobile_renovations | 1819136 | `e7109aba2044096649f54f1135e2a70f49d46eb0ade19c1d07f99ea1adffd497` |
| island_events_holiday_ornaments | 1805824 | `343799e26e3bd3c4cd4305f9e03ade8bf6341b19da63473fdedb3c70c08df9c5` |
| island_events_holiday_ornaments_behavior_patches | 1850368 | `41dc1a47b4ec23b14a15fa9f2a1407de96a8a950a91b13d9ed4c7d2a9cade792` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1864192 | `96768f448fc6cc53690d5910bf2a24c3af5528e28a41b68722d6a1811e83d2da` |
| island_events_holiday_ornaments_mobile_renovations | 1819648 | `8e7f80968b6dde5464a8a6f5e824a8d4a8d0182972cc1bdaa14c9f0308e79893` |
| island_events_mobile_renovations | 1817088 | `25ff12d25d21e9398da8ad21f290ac73af442ddbf28b10ca544614006d5b7213` |
| mobile_renovations | 1786880 | `ecda9b13c8a116a2377ade4d54fff58d0b0da5d9d5e71bfa04aeda3d54dc524e` |
