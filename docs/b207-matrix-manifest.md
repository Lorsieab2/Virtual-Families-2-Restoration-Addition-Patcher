# B207 matrix manifest

Built on 3 November 2026 from main `e32fe0f` (the merge of PR #488; tree `3e9a3d284ec5ae9bb264ef4ea4891d5f880d3149`, recorded in `data/vf2/build-matrix-release-b207.json`, merged as #489) with `work/build_matrix_parallel.ps1`: four parts of `work/build_matrix.ps1` in four worktrees of one commit, then collected. 32 variants, seeded from the B206 matrix, 32 distinct executables.

Every executable carries the new setting bytes of the Unicode text settings, Copy and Paste in Text Boxes (`.vf2utxt`, `.vf2ufnt`, the clip loader) and the Title Screen Player Name Box (`.vf2tbox`), and the Fix Vanilla Game Bugs fixes of #481 and #485.

Emulated on all 32 in the B207 run: Special Upgrades lists 53 rows (50 with `.vf2free` 0) with Cheat Upgrades and 10 without; House Renovations lists 30 rows with Mobile Renovations and 10 without.

Release DLLs, built fresh from main `cbdb06e` (the bundle is exported from it; #490 to #492 changed DLL code, the README and tests only) and shipped in the bundle:

- `vf2time_b200.dll`: SHA-256 `8f42d0d368e0765e918aa1f408afd94fcee7cba323a12abdbb437a690c9189ef`.
- `vf2kids_b200.dll`: SHA-256 `518ee831e858bd74280185dd13701773858aa3575c552c4af5c702f182df13d9`.
- `vf2history_b200.dll`: SHA-256 `a2a67abfb393d13be23b7375a72d48e2be64bc96a474db404d78869abba8a84a`.
- `vf2outfits_b200.dll`: SHA-256 `37d1a22a04f4b188b7cba3ce442a2ab00167ef29884a9a64583f775e4b9e45a2`.
- `vf2refresh_b200.dll`: SHA-256 `e4d5090944119f9c79bab083d64dc255fc07828c2851b9aeaf0346f9b5f51640`.
- `vf2unicode_b200.dll`: SHA-256 `4007c0399f3d2e953902b93ec215179a5afd76a30a0a8e15de14d161b6aece84`.
- `vf2clip_b200.dll`: SHA-256 `22407dae55be8b86efd194a6c5ffe8b65f886af20c0a4ccbe4697a2f35f64fc1`.
- `vf2titlebox_b200.dll`: SHA-256 `c5bcd3634a596fadc062aa4e45750c676d5d50c76eb83a04a6b8d286b29f098e`.

| Variant | Size (bytes) | SHA-256 |
|---|---|---|
| behavior_patches | 1816576 | `c71892442c2b33fa18e5f48c2afd5eedda07033eccda3a6c55191fdad816c7bc` |
| behavior_patches_mobile_renovations | 1830912 | `f4a9dbedaccc09a20004302aba9f2418ceababcfe17f4b5a2c075761660dba0b` |
| cheat_upgrades | 1773056 | `8ecbf864ef4442532d5c45586119cf143dd6dc4f4d638207a725c40f6ce66970` |
| cheat_upgrades_behavior_patches | 1819136 | `94bdeffb6339a0b71dc37377fdd7f4ae50f28b523dc21c9ac30596a54be1a761` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1832960 | `91c6f6d973014bd4faca461c0c745d9cc00c89ad5416d11141a6c3ee42293148` |
| cheat_upgrades_holiday_ornaments | 1776128 | `a07feacd5c9d074756b1b84dffe7f0dacb8d0cb43611544351bfa141ecd86e46` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1821184 | `14d494fc027ce93feda632d4ffdf6967846c77815335b3b6ad1bc31217e237af` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1835008 | `b9c03223b5cc612fab5adc37b15cce402df7f15b08e058649689277d6000aaf3` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1789440 | `907de2ec5c88a45951b93fd9627027c107d515559f523016a000a2ffce5ea098` |
| cheat_upgrades_mobile_renovations | 1786880 | `a1a03be70c595c0a4111cca937d1f113a390b1822b33966f44ef9528d73716bd` |
| core | 1771520 | `15f19831ec2577b425c271e8c75338bbaafe0039144ad4368515edec2dc37441` |
| final_all_enabled | 1865728 | `2e7f4e8daf07e32a8747688ec8f277bcc6375ebdbbc02a0414a7935173ddba9e` |
| holiday_ornaments | 1774080 | `34db25d9431abd8bc2ba906edcfc42e4967df1d7b3854ffc28952205dacd5fc8` |
| holiday_ornaments_behavior_patches | 1819136 | `663afb20ddd6c84cfc1499a3bcbdfc4cff8d79253234e6d876c77c0c53d568df` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1833472 | `34cac59e98ae5a0b8d0c08632bb6dc5d678955fd75bd5b621dcd76ab69928950` |
| holiday_ornaments_mobile_renovations | 1787904 | `6020e06e6757e02c3c95a4ed27eee3ed484289939900090bf18881efcaa90a63` |
| island_events | 1801728 | `fb1d57b0b9d25f1f5b39be9c22a77e5d412135a6b34876da3a52d4553e1c2ae8` |
| island_events_behavior_patches | 1846272 | `1c07aea833ae9aed964a1d2dde7f039d218cbbc5ba13f3bc62a6d998bbe3edb8` |
| island_events_behavior_patches_mobile_renovations | 1861120 | `1687ea1ef862d6df19b8fc0612e49597ac638d2966851c96ae19e2aea6ddadfc` |
| island_events_cheat_upgrades | 1803264 | `6db1c72e1863710c6046ac06798ba056857f81118133e548fb8eb25a9a934d9b` |
| island_events_cheat_upgrades_behavior_patches | 1848832 | `863717d05776c8ef5683e631594fec1b438b96980d183ef8d2ab88be753a20aa` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1863168 | `d494e7a5577a98311fd9a6a2f083bb3917bf1d3b80865573d6771767956bf25f` |
| island_events_cheat_upgrades_holiday_ornaments | 1806336 | `9af0ada6c4f1fe75611b49f20ad38eea06d6ea5fa6868536a7b0304958b3551e` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1852416 | `c10f4645ceea71cf43fab2195124fbaa3315f14296640016deae57c78fc0b8a1` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1820160 | `78673cfd4ef6fdc692ca817f0caed6261832919aaedbd1ea0066d71737c6469c` |
| island_events_cheat_upgrades_mobile_renovations | 1817600 | `199c57cef68959779997b25a0ed58304352856c05bf90768538114a310c853a6` |
| island_events_holiday_ornaments | 1804288 | `19d259a7229fa9114b08ae4da196c83ebdde33733475a0d137d58d9ad3e0c98e` |
| island_events_holiday_ornaments_behavior_patches | 1848832 | `673a83d4f4e06964f7fad5ea7ac6d4750d75dd22e1f2169ae721e37d464df2c0` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1863680 | `9b8c8a24acdb3cde09ceb5b07424eee5db5db343e6038e0bd5208c1e2fb3b880` |
| island_events_holiday_ornaments_mobile_renovations | 1818624 | `1faf77950eef350efba2eb4eae03bac8832305d2e895d03a6c0d17225355505a` |
| island_events_mobile_renovations | 1815552 | `ad552f3e858c33ad9b51ea54ae48c3100c69897a98126fc13961675dc4b6f4cd` |
| mobile_renovations | 1785344 | `e2a676af8ec74a94e90a7f54fbbe158ce1247fb76bd2059d999aa5c2e8d1c1b6` |
