# B204 matrix manifest

Rebuilt in place on 27 October 2026 from main `551b924` (the merge of PR #457, all 36 Flea Market goods always in stock; tree `02573834ad65f3e4fa0a89cb3ad6368fc4151a24`, recorded in `data/vf2/build-matrix-release-b204.json`) with `work/build_matrix_parallel.ps1` (three parts of `work/build_matrix.ps1` in three worktrees of that one commit, then collected): 32 variants, seeded from the B203 matrix, 32 distinct executables, none identical to the previous B204 build. Earlier B204 matrices were built from `412660f` (PR #438) and `e0bb126` (PR #448); those hashes are replaced by the table below. This build carries the Cure fix (#448), the Outfit Pictures loader behind the `.vf2bugs` byte (#454), the `.vf2rfsh` loader for R Refreshes the Store and the `.vf2flea` byte for the All 36 Flea Market goods setting (#455, #456, #457). Every executable carries a dormant loader, `.vf2hist` (0 as built), for the Family History log (PR #437), after the Time Controls and Up to 28 Children loaders.

Release DLLs, shipped in the bundle:

- `vf2time_b200.dll`: SHA-256 `3ea0a2a5689ecbf5d1bef05368493adb3f54b8e0e96343b2d75a585267b1d35e`, the B201-B203 file (`runtime/native/b200time` unchanged since).
- `vf2kids_b200.dll`: SHA-256 `4a6bb5ff9d418849b4e750884307eb74b1b1488a51d251bea2d813cee3989f0f`, the B202-B203 file (`runtime/native/b200kids` unchanged since).
- `vf2history_b200.dll`: SHA-256 `3c7181bc47753b8cf2e5c92c4d4068e1bd45a468a2dbc56a9a020bfb1558a686`, built from `412660f` with `runtime/native/build_b200history.bat`. This is the file every B204 zip has shipped, including this rebuild, which reuses it unchanged. This line used to give `0c01c165...`, which was never in a published zip.
- `vf2outfits_b200.dll`: SHA-256 `0ff96da2bac5b9b4415f234e61efbe66b12c86f789133afcc44c6ac1c19f90b5`, built from `551b924` with `runtime/native/build_b200outfits.bat` (new, #454; ships with `vf2outfits.ini` behind Fix Vanilla Game Bugs).
- `vf2refresh_b200.dll`: SHA-256 `10ae09db7c1f8757d57f7e6569d3f5df8e9b207729daf298ff2ac68891000ab2`, built from `551b924` with `runtime/native/build_b200refresh.bat` (new, #455; R Refreshes the Store).

| Variant | Size (bytes) | SHA-256 |
|---|---|---|
| behavior_patches | 1811968 | `9b8039b4156c71f9b9e693317e197d4a76e7f5d2c067da4ee175f423db373631` |
| behavior_patches_mobile_renovations | 1826304 | `ce8da3d6e227a0d826b7c337e0d536aa6ef0c99194b3822e65d7dcca457ec5ab` |
| cheat_upgrades | 1767936 | `38cac872c18e415dac0a27fc1f88b71de7943160c092345652a7f446f9788523` |
| cheat_upgrades_behavior_patches | 1814016 | `3c42eb6eb5030af4b79f580981293c6cddd06124fd69495f2c6191e3f36b8aad` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1828352 | `1ba584a408279d9a5ea51120b5c22d12683561444ab6aba120840bdeadc69bf0` |
| cheat_upgrades_holiday_ornaments | 1770496 | `47275d9650a58f1c836475701a6dfdcd83a50ac58e0fd03b79446d07ae32bc19` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1816064 | `e769338f181b75860beb6e24de32e51f1f5be544ece0d540f6fdd54338bc245f` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1830400 | `bde6b3d649d65d0862f07e4e1f84e78a0cb4462f6b0dd5b34d648e04dfefbe68` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1784832 | `3522615b011a7a792df73a2cd08494e9cdc64b1d9d76d1889f1752f96c5d57d8` |
| cheat_upgrades_mobile_renovations | 1782272 | `64a00f1a5123cd9b8ce0d58f35e62f7dc357a183eec5f7676dd958a694c3e924` |
| core | 1766912 | `5d8fd248be14ea77647e7ade9e1d78f78657dd1695e4d8826cacf5e20410e7fa` |
| final_all_enabled | 1860608 | `349c3acc1597450e679c19e8560d360b442625954bbbd472fdf4310595f71300` |
| holiday_ornaments | 1769472 | `b3254bdf7cb303056f4ea9deb702e0f501982dafcd9276d7d9b3164d43203f5f` |
| holiday_ornaments_behavior_patches | 1814528 | `f502f5f4fa73599345e749307cef5eaa492b73774a122e2e87941e07ab0ee5f3` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1828864 | `341ee3300eb035e1d31dc4e458f4eea6ced488a7cbbace46e44ca645818e33a6` |
| holiday_ornaments_mobile_renovations | 1783296 | `5091e5b99e74fd6787b3d1926e9e6eebe375db8f3386937efb37a3394bacca9a` |
| island_events | 1796608 | `9e25575c5b59fde5a92427cc5872fbf5ba3af50f219ee24bb166044e58d2db07` |
| island_events_behavior_patches | 1842176 | `1b2bde6aedb3f6ee32fabbb35f02f61a3f605766ff0fd5660e8b90af628e100d` |
| island_events_behavior_patches_mobile_renovations | 1856000 | `cf16b702e2470d5c60fab1f6bf149f753a31545d051605460fb154c973e57aa4` |
| island_events_cheat_upgrades | 1798656 | `e96aaf4ab696704a82c73e3c06b7c17c06263ee07352927af8d39f81b1121a92` |
| island_events_cheat_upgrades_behavior_patches | 1844224 | `bac8428886cb93c412e132b3840ed5435245122cad63ae447fcd7f8b094c3c74` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1858048 | `e7aaf43cfe4298158d644162c08490f43185cf1e219997ca88ac39845b0a0a65` |
| island_events_cheat_upgrades_holiday_ornaments | 1801216 | `8ef45d789690213bc094108b011508371a2980c4f7b70d874a66324f39f69ae7` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1847296 | `0303d273b7b23610ee67eabcb4e6127ffc179224079a94eeb72b149e92fb31c7` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1815552 | `19abd627dac0d9e97aadefc5908e127819688b939a83744a13e97c99cb5c6858` |
| island_events_cheat_upgrades_mobile_renovations | 1812480 | `03f81106a077da4873192947525f7d71822976f0b290d302aaf399b33f9fb915` |
| island_events_holiday_ornaments | 1799680 | `f2026670be665f50523ea37f2be4fdfc13b860cbeebc740e65b1053f86551b80` |
| island_events_holiday_ornaments_behavior_patches | 1844736 | `b51193eb638480cf181657cba0f6c616c899d53d53d2389011eb3fbd7d2e446b` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1859072 | `9afce32578788907cc933e6e1ccf849e66ae62c34425034cfa2b7300e8ec6d8f` |
| island_events_holiday_ornaments_mobile_renovations | 1813504 | `fa38651d2b025dc80ed90e19226ba1b78877c76593fcc2d8b8250f68147eb45d` |
| island_events_mobile_renovations | 1810432 | `106177eb150539af956fae44b025facbc5d45eba2c80e34f08e3565e868387f8` |
| mobile_renovations | 1780736 | `d1f9f185ebc6f80a9b2f42306f11bb1be5016d570e1a46e36a95f3a097139c12` |
