# B205 matrix manifest

Built on 31 October 2026 from main `61624b1` (the merge of PR #465, the bounded server error text; tree `69ce4ac1b6d85eea7518ad141501ed64d54862c3`, recorded in `data/vf2/build-matrix-release-b205.json`) with `work/build_matrix_parallel.ps1` (three parts of `work/build_matrix.ps1` in three worktrees of that one commit, then collected; part m1 was rerun alone after the known shared link-response-file race): 32 variants, seeded from the B204 matrix, 32 distinct executables. Every executable carries the two new Fix Vanilla Game Bugs object patches behind the existing `.vf2bugs` byte: the LDW login-reply read guard (#463) and the bounded server error text (#465). No new byte and no new loader; the `.vf2hist`, `.vf2rfsh` and `.vf2flea` bytes and the Time Controls, Up to 28 Children and Outfit Pictures loaders are as in B204.

Release DLLs, shipped in the bundle: the five files of the published B204 zip, taken from its payload unchanged (`runtime/` has not changed since B204 was built):

- `vf2time_b200.dll`: SHA-256 `3ea0a2a5689ecbf5d1bef05368493adb3f54b8e0e96343b2d75a585267b1d35e`.
- `vf2kids_b200.dll`: SHA-256 `4a6bb5ff9d418849b4e750884307eb74b1b1488a51d251bea2d813cee3989f0f`.
- `vf2history_b200.dll`: SHA-256 `3c7181bc47753b8cf2e5c92c4d4068e1bd45a468a2dbc56a9a020bfb1558a686`.
- `vf2outfits_b200.dll`: SHA-256 `0ff96da2bac5b9b4415f234e61efbe66b12c86f789133afcc44c6ac1c19f90b5`.
- `vf2refresh_b200.dll`: SHA-256 `10ae09db7c1f8757d57f7e6569d3f5df8e9b207729daf298ff2ac68891000ab2`.

| Variant | Size (bytes) | SHA-256 |
|---|---|---|
| behavior_patches | 1812480 | `af174916153687a23ae435d8fa8f4ad145b1dedca0e111ae025f069f034d8e26` |
| behavior_patches_mobile_renovations | 1826816 | `fde1ad18d9c5fb8bdd4a4851837097dac67c4ce3b47cb1c266f3e8c1a207eda6` |
| cheat_upgrades | 1768448 | `7159c64f3fb2e114bce7fa7ffbd73e2723a032011e7d4f2b1a605a9dca01047c` |
| cheat_upgrades_behavior_patches | 1814528 | `75ee2e0d7b3ca2a7166a6010490a11f331aee0f89d0401f459816183adc42883` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1828352 | `f350505bffa7c39515f23882a9034e3839a56b483dd351b5d23ed023f8caa0ec` |
| cheat_upgrades_holiday_ornaments | 1771008 | `0c3c2d2197cdc9e4e304fce43c199fabca0557e0ac45d35499d4484ace546de1` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1816576 | `612d2586fd071aadf08588139a725f085f79e04aa9799678272bb15601200922` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1830400 | `8774dcb7bb95cb5bcb65ee14c609d9764e658892d2fa56f44c36e0e7933fb2ec` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1785344 | `5b52f3605b07bdeca8c9391e5a4bc6c9a7cc70a97ca890685277e6d7a7b0c89b` |
| cheat_upgrades_mobile_renovations | 1782272 | `424c5728dab48484f51b6059468dbae1a69c879334a85da04b1c648f54988c41` |
| core | 1766912 | `7a3cb5fad1a6521fb8b231e4a2cce143096a35f45a5d6f268f99decca1c21923` |
| final_all_enabled | 1861120 | `3f997767282b0fafe45296e37adb9c161ff2fb27a8e2253581ca5497e84033c8` |
| holiday_ornaments | 1769472 | `7906eb2ddc29096a586c5151217c34bc3adc522d3408f4a0da2560188fd2c5eb` |
| holiday_ornaments_behavior_patches | 1815040 | `2e18489b5b364338a5d71670f13cb6ee082486a3da0e8bfee8c090be53e91f40` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1829376 | `173f3f94583ba16185405ba675610ae013a533bb1384a1b5c4d1f79f18017516` |
| holiday_ornaments_mobile_renovations | 1783808 | `3e9a30cdc12fcbf4571d304eac15239977c3ee1cb862e30098ec9b65a0e00c5c` |
| island_events | 1797120 | `8adca8911ff1c91b33daab2678cde9d055ed53bc66de2b3ecb2889aefd29629b` |
| island_events_behavior_patches | 1842688 | `501f471df57ef240121cffa5945b1eeb7ee8768c7453dbe171e085d194a2c57b` |
| island_events_behavior_patches_mobile_renovations | 1856512 | `a75c598caa332ac09642606a1b357135ce01a5eee0772dad2e0e1d6f7b31981f` |
| island_events_cheat_upgrades | 1799168 | `ed534f1f3f97652b0612dcbfe7798ef32295b0a6d99609959a27230b34673969` |
| island_events_cheat_upgrades_behavior_patches | 1844224 | `e34508dc0173bd7579c88d00ada2fcb511636c610093b83c8c79059e28edd9b9` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1858560 | `078f9fadaa282ba563f345a173316a1e56c162c14c211e4ed868b45f7378883a` |
| island_events_cheat_upgrades_holiday_ornaments | 1801728 | `f852424d101cce0934ddac978ef981e411c0ac5aac9dbe36b465c3cddf8c494f` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1847808 | `ac5233b9d3cc1e56fd79c142a82a91d9d7d9dfa0f7492c920309f73c85a7c471` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1816064 | `cc54f5f3f7678df226e6433f3383f930e8c964f46b5ec9de9a3d8e268351f4f6` |
| island_events_cheat_upgrades_mobile_renovations | 1812992 | `a787adee71709b55303e2455e56aee6a3038d1ef4db5769abac0d9fa531c4188` |
| island_events_holiday_ornaments | 1800192 | `6545b3d59dcafa5bf73931bdb07f23275fe1b2cae990478381a43e3bbaa2a8fa` |
| island_events_holiday_ornaments_behavior_patches | 1845248 | `f0b9a15ad658fa9c44a50fd7f85047c0b8a8348a985901ced893fe15068903d8` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1859072 | `3e5091a34fbee00e7cd496ddc030bc8d4bbdf217809c1b0ae9ff4f63d81fcdc6` |
| island_events_holiday_ornaments_mobile_renovations | 1814016 | `eb36464e12e13b959d0dc52822b58d13160d5e14ca4075713278a1d01e3f2f63` |
| island_events_mobile_renovations | 1810944 | `2e629c201825a8db558a8918c8b569f0a2b70d21e983db870999353dee83f6d7` |
| mobile_renovations | 1781248 | `fb630479febd9adc3bb207c1074478fa60eaa54a400e88883255ffb8ad4c8745` |
