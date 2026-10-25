# B203 matrix manifest

Built from main `471f6f5` (the merge of PR #430, Game Mechanics; tree `a1d18971bf40e980a85d881f8ad6bafb1fbe09f8`, recorded in `data/vf2/build-matrix-release-b203.json`) with `work/build_matrix_parallel.ps1` (three parallel parts of `work/build_matrix.ps1` in three worktrees of that one commit): 32 variants, seeded from the B202 matrix, 32 distinct executables. No game code changed since B202 (`0f7dc32..471f6f5` touches only the patcher GUI and its tools, the bundle and release scripts, docs and tests; no generator or game-code file); every one of the 32 executables differs from its B202 counterpart in exactly six bytes, three of them the PE header's `TimeDateStamp` (compared byte by byte, all 32).

Release DLLs, shipped in the bundle: the B202 release files themselves, since `runtime/` has not changed since B202 (`0f7dc32..471f6f5`). A fresh build from `471f6f5` differs from each in six bytes only, all linker timestamps.

- `vf2time_b200.dll`: SHA-256 `3ea0a2a5689ecbf5d1bef05368493adb3f54b8e0e96343b2d75a585267b1d35e` (the B201 and B202 file).
- `vf2kids_b200.dll`: SHA-256 `4a6bb5ff9d418849b4e750884307eb74b1b1488a51d251bea2d813cee3989f0f` (the B202 file).

| Variant | Size (bytes) | SHA-256 |
|---|---|---|
| behavior_patches | 1809408 | `1f3880179972a6ec0e27228a04fe2523f647474ba148a617af78e51d1b8f3df0` |
| behavior_patches_mobile_renovations | 1823232 | `a428913f17e9cbfa0a4041b8936e998c2bdc93a32da03f30f9c3a6b299abc516` |
| cheat_upgrades | 1765888 | `814d09535293298cb5849092c74492ee7f0a2a2f5987f6ac06ed9a990e8926b5` |
| cheat_upgrades_behavior_patches | 1811456 | `fcb8b1d70627b604bc900fb4a88cc79566882edc1e132ef98d14b34bf942144f` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1825792 | `86b42f33d45c2791e68593e8ddece83bad8f6931edbfc64553eb5f2ed8e48ba3` |
| cheat_upgrades_holiday_ornaments | 1768448 | `2587d3311ee0aa2a4461eab34364e2130e87ead185a49f4cfc8e5f09737644a0` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1813504 | `2ac01d77cfae3863c6da2aeca23688f01e0be4babd4f8f0f928878b10456dc3c` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1827840 | `f2e914537ac19cc14ef59927875cfcd5763d9a5adb9941ddc1ee49cabb7d3b95` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1782272 | `a18014e9c23ddf59dfa2755bd7957a6f19164e3a46066c1f5b9240641f7c4f35` |
| cheat_upgrades_mobile_renovations | 1779712 | `dfeb2c4f41bf6b9279a8857723c7154faa11e88ee09b007de176123a7bee0eed` |
| core | 1763840 | `f106ad7a802003078b6337f182707ff03d5bb4bc2ef6d907a4632971854637a4` |
| final_all_enabled | 1858560 | `36477736cf0332fe30f44196d2f0bd3c1ec3e029c90bc14b3f610b10826645f2` |
| holiday_ornaments | 1766400 | `f00eb5d891f13dca34c3ceb8f442fb832d7abd275dfed028569b1f8ba41062b8` |
| holiday_ornaments_behavior_patches | 1811968 | `eff8434f64db7fd92bea0f2486f2af94597178572e62e02f7c905f83e8285e07` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1826304 | `7f8503f291f09db537f53606737d206061a0c900f66dfbbd6b7cbcae52160a4e` |
| holiday_ornaments_mobile_renovations | 1780736 | `bb0f8af6086a8ac27639bb465f5bc7a4fed96f787a9932fd4ff9223fb82f2153` |
| island_events | 1794048 | `22e1269f4095d1740fdd4f7d142153887ee8c3dbb48fbe7328bab68902209dec` |
| island_events_behavior_patches | 1839104 | `cbf9cb53719a745fd365b9ca92b5516655227f6064540bee97afb2cad2467d0a` |
| island_events_behavior_patches_mobile_renovations | 1853440 | `1c5b4d17b020b9846760f081a2b785c9ffe4f0ec95a112206d45f61c1c2bf04b` |
| island_events_cheat_upgrades | 1796096 | `cc8562d4857d5681b3428ea73f9eae58fd3280255fb67ef790f5f80ed4b40cc2` |
| island_events_cheat_upgrades_behavior_patches | 1841664 | `d1bd6d75c376296320a98c5897df25a6fc8603190d64f26fd98e946d7ffdaaa3` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1856000 | `0c18695ace78d25502dc0fd38d38198ffa34cf7c7eb2d1fd32142c1f19a7bc33` |
| island_events_cheat_upgrades_holiday_ornaments | 1799168 | `9980aac70f8a03debedbfc1c810c4d39b40b3d6178309b7a4a16cde26c0c1a0c` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1844224 | `c70f9582881bcc1eb8cb81aa6ddb0529cbe6c4c4f6e86fe2165cf38d8aaabae3` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1812992 | `55ea5681f46c37163f0023939172c4204dc103026d951cbb3d861433a533d77f` |
| island_events_cheat_upgrades_mobile_renovations | 1809920 | `2997b86c49482857aa65baecc25bebf707cfa062fcc20515f008d05200e62f1e` |
| island_events_holiday_ornaments | 1797120 | `6bbc49c2f4dd4a194574d854570d0619b4da9096fdb7eee0000b033b85be51c7` |
| island_events_holiday_ornaments_behavior_patches | 1842176 | `b8bbe6b359a456cea2b3041e06d1ccfb43cbd2c1e762964c41a60512af51bd38` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1856000 | `2f578ce08c22fb354ee87524990ac31902aff2fa9f73775fef6c48830a6e4856` |
| island_events_holiday_ornaments_mobile_renovations | 1810944 | `a5a457eda0ea921daae8372c5c1a51131953e90a51d923cf3a310bf4ecbdaa0a` |
| island_events_mobile_renovations | 1808384 | `9adb6741287ccdb3226037ec492ed0d401fcf70fe2d611ebf2ca1d42cd26f5fa` |
| mobile_renovations | 1778176 | `b8ae3e28359f573d2f927d815959aa86042082c37b5fda0ded6fa386dcc234ac` |
