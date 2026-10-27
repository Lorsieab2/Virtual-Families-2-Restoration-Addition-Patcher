# B204 matrix manifest

Rebuilt in place on 27 October 2026 from main `e0bb126` (the merge of PR #448, Clear All Illnesses keeps the food groups; tree `84f86a9d30ea0707eba6ce1a339dec4e1baee143`, recorded in `data/vf2/build-matrix-release-b204.json`) with `work/build_matrix_parallel.ps1` (three parts of `work/build_matrix.ps1` in three worktrees of that one commit; part m3 failed on a file lock and was rebuilt alone, then all three were collected): 32 variants, seeded from the B203 matrix, 32 distinct executables, none identical to the first B204 build. The first B204 matrix was built from `412660f` (PR #438), and those hashes are replaced by the table below. Every executable carries a third dormant loader, `.vf2hist` (0 as built), for the Family History log (PR #437), after the Time Controls and Up to 28 Children loaders.

Release DLLs, shipped in the bundle:

- `vf2time_b200.dll`: SHA-256 `3ea0a2a5689ecbf5d1bef05368493adb3f54b8e0e96343b2d75a585267b1d35e`, the B201-B203 file (`runtime/native/b200time` unchanged since).
- `vf2kids_b200.dll`: SHA-256 `4a6bb5ff9d418849b4e750884307eb74b1b1488a51d251bea2d813cee3989f0f`, the B202-B203 file (`runtime/native/b200kids` unchanged since).
- `vf2history_b200.dll`: SHA-256 `3c7181bc47753b8cf2e5c92c4d4068e1bd45a468a2dbc56a9a020bfb1558a686`, built from `412660f` with `runtime/native/build_b200history.bat`. This is the file every B204 zip has shipped, including this rebuild, which reuses it unchanged. This line used to give `0c01c165...`, which was never in a published zip.

| Variant | Size (bytes) | SHA-256 |
|---|---|---|
| behavior_patches | 1809920 | `73defe6afd6ec5ece40dd5e4e62eef627114b24b495ad8c195304b76403eab83` |
| behavior_patches_mobile_renovations | 1824256 | `28e9dca339c874b1c49cdeb78ad0eaaede6020065b90aff5e5476fc8eca3f736` |
| cheat_upgrades | 1766400 | `ddaa2b14e261104dfaf65abb5a2f41d4a53a79a6931623a1b983edbc25f23960` |
| cheat_upgrades_behavior_patches | 1812480 | `01eeed8554f31fd08987326fab35b912f3eb0aed898530c4fe8b1419cdce6fb0` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1826304 | `518f27cc8287b8c34cfc64762e0aba6afe93ee4f519289c88272a9730e8b33dc` |
| cheat_upgrades_holiday_ornaments | 1768960 | `ec8de9b1604960278c0cd3b775c895747308ff7038a4cedfd5c64213919d7579` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1814528 | `6ab6ef4f30ada11a2282b6820a20a5b0754380f0defee4de0aec7a075987d6a5` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1828864 | `3d172ca1f1637f2971ba84577bb1dfe86f8e3628a522af08e1fcb2c4c1b00a7a` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1783296 | `518967f4614bfefd7cba2474575cf998f1a256f5711a252607082c28da426e39` |
| cheat_upgrades_mobile_renovations | 1780224 | `677e14e7eedd667aa7e485b2eae7ff012b89797f25a8311e7485b2678b74f5f2` |
| core | 1764864 | `abef1ff7a875518ef2ad28da4b7beaf378b48cc012e8e4c038760087699d6851` |
| final_all_enabled | 1859072 | `df0235a491640804e5ccc9e4d6d72c922af28339d427b4f63bd9165f1b49fe64` |
| holiday_ornaments | 1767424 | `6ea0129513a564f7793c4529c7150c506740f4877f7534429d132f3cf2ad710d` |
| holiday_ornaments_behavior_patches | 1812480 | `5ba7eb1da9491be36db8e23fd0a174d2b39362a4194c8afc88e37f15fd79425a` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1826816 | `1cc6ad2f47d8f593215f7378e80b012a716e8bfd3bf23d9ae7d207d56dd398c3` |
| holiday_ornaments_mobile_renovations | 1781760 | `5265e1ef41adc88bddd11ea6947c9305fd11c23d9b2ba79b57778417d972b1db` |
| island_events | 1795072 | `f1f62461be04df0593a3ec5892daba342e5ed211869679b39d0f6e29e59ff77d` |
| island_events_behavior_patches | 1840128 | `8f2b1fcedb879e786686370832fd8205081b45d53f3919cd7a39145b0fa19ccb` |
| island_events_behavior_patches_mobile_renovations | 1854464 | `053527fdf146c9be7f0665c84769b162e9aed74290d52a9d6e5a2afc4c1205f3` |
| island_events_cheat_upgrades | 1797120 | `ad0dddd0e862554218129e4052fae7bc667286336c3be62a00aebe6f2174358d` |
| island_events_cheat_upgrades_behavior_patches | 1842176 | `03037a9d6fe34bae3941fd8bac247950303958af2b30e99f1a980079c48cd38c` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1856512 | `0ad301fd49ac1839331c753515cc7dab3d95aa1e199f6b401ad088a7ff5ffb62` |
| island_events_cheat_upgrades_holiday_ornaments | 1799680 | `f5ffa2b81e285d91b3aaf2e0aef91b56c18be34699aafa515c915d0988e309f3` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1845248 | `55ef926936cc01ca1317093e75ab466db2e7a03508506e5c2032421e4c46185a` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1813504 | `51e289e4456c0370b9e0484cb049b36fbe9cd6fd1f94311b71bf547d58722342` |
| island_events_cheat_upgrades_mobile_renovations | 1810432 | `5351f68bc86473317129a99ce1aa19ded5186560c0392b437ca01e896b9fd43b` |
| island_events_holiday_ornaments | 1798144 | `975dd824d13c1c8e151453864a3fda73ab925fe02ee1fe83af96b6a1f89b23b0` |
| island_events_holiday_ornaments_behavior_patches | 1842688 | `2441223f2d5e743ee19818cb5b50a1c47c9b2e50a463121d1b668c48c07f990b` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1857024 | `2bcd2d3befee05553f6b6896983aaf8805860f5892fa717096e7d6443efee6db` |
| island_events_holiday_ornaments_mobile_renovations | 1811456 | `182d4be6a0a015053954862763d08993c0010f8aaedb3e6e2927d86caa493527` |
| island_events_mobile_renovations | 1808896 | `8c307dd5d91b5d5839830a29c059d5f2a55eb3faf51cf78d1d4d28bbcf2b0c46` |
| mobile_renovations | 1779200 | `0d22bfef7c5bbee9b741c44fee96353280f67363e41e07dac065bdace8f326bc` |
