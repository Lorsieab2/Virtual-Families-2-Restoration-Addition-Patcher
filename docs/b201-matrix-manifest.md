# B201 matrix manifest

Built from `efbe304` (tree recorded in `data/vf2/build-matrix-release-b201.json`) with `work/build_matrix.ps1`, 32 variants, seeded from the B200 matrix. Each variant linked; each carries the dormant Time Controls loader (`.vf2time` byte 0 as built).

Release DLL `runtime/build/vf2time_b200.dll` (`runtime/native/build_b200time.bat`): SHA-256 `238cbfe9aed1d5204534465d076cdb2b95b6cab61346fcd7c50bed55d3bb5787` (the file hash changes on every rebuild because the linker stamps a timestamp; the code, data and resources are byte-identical to the build that produced `1d646d97...`, which a rebuild after removing the REDUX files confirmed).

Checked for every executable: links; its pinned runs resolve exactly once with all derivations agreeing; loader present, flag 0; the loader end to end under emulation (byte 0 never loads, byte 1 with ini 0 installs nothing, missing DLL harmless, byte 1 with ini 1 installs). No live test.

| Variant | Size (bytes) | SHA-256 | Resolved and loader checked |
|---|---|---|---|
| behavior_patches | 1807872 | `8609a2794ac1ba31b726ff6c038a55eeb97816de7be8795d6dfaaa17cbd47650` | yes |
| behavior_patches_mobile_renovations | 1822208 | `63bb645cb986f8e96dcbe185f213ca750a7d0933da876b5bedadaaae95d66a87` | yes |
| cheat_upgrades | 1764352 | `9f668ff9807720bc2e8c0039a48f9a0eb494a3dd29757d297dba8b4f2c84a7b6` | yes |
| cheat_upgrades_behavior_patches | 1809920 | `bc77cce81a24957bb8fc87885866704f131c2fb4fe8fd63640f51e9c3cc4b5d7` | yes |
| cheat_upgrades_behavior_patches_mobile_renovations | 1824256 | `70e0fee4dc50415c104c85a7115355b632750b95aae2eee25aaf3b3fa2365dd9` | yes |
| cheat_upgrades_holiday_ornaments | 1767424 | `53ac0cee498c2323ef39ca8926ecf6429a5111dccc7447046808626341e71b61` | yes |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1811968 | `a54e069f432d399e995e562dd59f2a3e69decc85a34267c6f32bfa2cfe5c8d3d` | yes |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1826304 | `292ad7fdabf9906efacba9dffd34fb8b061205fafb843758668061c0e99438b1` | yes |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1781248 | `ec2088017ad06e12b1b40588c89459bcc13b83e8c039ccaa721afb708a44a8d7` | yes |
| cheat_upgrades_mobile_renovations | 1778688 | `5d415ed29e81ee71c12d079c827d2bfb76f800fea45d833e4930b7e3d3887774` | yes |
| core | 1762816 | `5f4a49508270cb44365c115204ba8e2027619b8451aabe0caf1b2372150ef681` | yes |
| final_all_enabled | 1857024 | `2a7227ff09b803decbaf52987c2911ff121976b33e87a00606dbb19fccb8080e` | yes |
| holiday_ornaments | 1765376 | `8ca5c8e8931315d6db3fabb413d27016c364e2c3ae1e339b092a480e6604e598` | yes |
| holiday_ornaments_behavior_patches | 1810432 | `3e7ddda1efcee490169835ca997c07cc1454cb8b98220a4d7c4c9e6737de478e` | yes |
| holiday_ornaments_behavior_patches_mobile_renovations | 1824768 | `a69bea5c14d3855d54ae24a1143a68c5b697a0f64df9d9633db9396fc763f04f` | yes |
| holiday_ornaments_mobile_renovations | 1779200 | `41a7adb7f2f92500239ad6df058d8b8a62fc2613d9c297e1b1883f551e33a2ee` | yes |
| island_events | 1792512 | `b211752c8babee245ed9d6589b11881273587573afc70597df92da910cf1d1f6` | yes |
| island_events_behavior_patches | 1838080 | `c659dd8e7fafce3671bf9ff7ae44873419f17da5eabbb229c6f9f338060ddc1a` | yes |
| island_events_behavior_patches_mobile_renovations | 1851904 | `54d0180b9c1523c65f303ac1c0fea7e1df2fac3191a070b61fea37884bd34a0d` | yes |
| island_events_cheat_upgrades | 1794560 | `cab3663615a8de80b89c280d1b45b831e7d4330fd7cd3745f2f710de0a7d557f` | yes |
| island_events_cheat_upgrades_behavior_patches | 1840128 | `5015a7fbe04e42e1ae3b455f15f3c797ab6da85999801f31f160bc835db8b822` | yes |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1854464 | `8fa4893a82f1c077b311972797f26937b5076298c2549102361abce7eec8aa30` | yes |
| island_events_cheat_upgrades_holiday_ornaments | 1797632 | `3552bc7c002717b6479851133ff9641d7dd92520eeb59e89df77666a51a9f6fe` | yes |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1842688 | `a34c462e2406876f226b286e79e8eb9a051505f72523d918a5ffe1dcad17cb41` | yes |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1811456 | `8033c4fbe910e710b4395a691d85b755a930750c0163ff662563b22a8874848e` | yes |
| island_events_cheat_upgrades_mobile_renovations | 1808384 | `6f6c40f01899cd7ed9214064b8c57f4e125bf6f007ecd41d6ecf5f0b47c8ecbe` | yes |
| island_events_holiday_ornaments | 1795072 | `bcbd0d0a5129ecbad89c0eb763abbaf1d2c9ff4f85a13d888bd3b7566116bae6` | yes |
| island_events_holiday_ornaments_behavior_patches | 1840640 | `c1ac0dc44583470e54c6c449df67af83f5fa418dbad6f5a08d9a4b36a5b34cc8` | yes |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1854976 | `90a3b4a4e42c03e4d4ee1ddf94a4c7238118f2d3d206d4367b4b8870f772afc1` | yes |
| island_events_holiday_ornaments_mobile_renovations | 1809408 | `65bc0a93283e63560c90a69c86e34f65d3b11b59029051f38c22337a6dbc8c63` | yes |
| island_events_mobile_renovations | 1806848 | `e178577b6addc0dfc9178aa85787b55750618fdf69aa62e857c16c3c23061ae9` | yes |
| mobile_renovations | 1776640 | `30ebb4990d24ddd9ab04236270e464113fac38cdc9f21d6dbf1258b435f1e1fe` | yes |
