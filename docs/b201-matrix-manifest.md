# B201 matrix manifest

Built from main `2e326b6` (the merge of PR #423; tree `ebf0784302068b18471eeafc7a85b43f1b1c7b18`, recorded in `data/vf2/build-matrix-release-b201.json`) with `work/build_matrix.ps1`: 32 variants, seeded from the B200 matrix. Each variant linked, and each carries the dormant Time Controls loader (`.vf2time` byte 0 as built).

Release DLL `runtime/build/vf2time_b200.dll` (`runtime/native/build_b200time.bat`, built from the same tree): SHA-256 `7ec7eb32974e1705759376a186de8778b8a4132039d4e729c456c75fea97fb09`.

Checked for every executable: links; its pinned runs resolve exactly once with all derivations agreeing; loader present, flag 0; the loader end to end under emulation (byte 0 never loads, byte 1 with ini 0 installs nothing, missing DLL harmless, byte 1 with ini 1 installs). No live test.

## Why these hashes differ from the first rebuild (efbe304)

An earlier build of the same 32 variants from `efbe304` (an earlier commit of the same branch) hashed differently. Every executable differs from it in exactly six bytes, all linker build timestamps: three bytes of the PE header `TimeDateStamp` (file offset 0x128) and three bytes of the `TimeDateStamp` of the debug-directory entry in `.rdata`. Code, data, sections, checksum and every payload file are byte-identical. The release DLL changes the same way (the debug-directory timestamp in its `.rdata`; its code, data and resources are identical). A rebuild always produces new hashes, so the hashes below are those of the files now shipped and listed here.

| Variant | Size (bytes) | SHA-256 | Resolved and loader checked | efbe304 SHA-256 (timestamp bytes only differ) |
|---|---|---|---|---|
| behavior_patches | 1807872 | `61674fa769ba9f4b3f19ffe591dc9faffbbe48953b917f4e5605abf9add3463b` | yes | `8609a2794ac1ba31b726ff6c038a55eeb97816de7be8795d6dfaaa17cbd47650` |
| behavior_patches_mobile_renovations | 1822208 | `655aa06c9850f2bdd63f5bac2ee70240dbd946528d487b39f953afcbe44a265f` | yes | `63bb645cb986f8e96dcbe185f213ca750a7d0933da876b5bedadaaae95d66a87` |
| cheat_upgrades | 1764352 | `5c2bdea75ad9b23fa97fa58fc8e6e731f6c0438871e7e16ed7e370b821bbbc8a` | yes | `9f668ff9807720bc2e8c0039a48f9a0eb494a3dd29757d297dba8b4f2c84a7b6` |
| cheat_upgrades_behavior_patches | 1809920 | `7a49c8c31525d9bd826d722944bd90f4d3b41fcc6ec61ec8f1b3e139a53ed003` | yes | `bc77cce81a24957bb8fc87885866704f131c2fb4fe8fd63640f51e9c3cc4b5d7` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1824256 | `4d98ff80efcc07026795434c5a77ca1719b2039adc26ba6cf87aa5ba9bb4a9ed` | yes | `70e0fee4dc50415c104c85a7115355b632750b95aae2eee25aaf3b3fa2365dd9` |
| cheat_upgrades_holiday_ornaments | 1767424 | `e047b452a78a7d2d7708341174eb5262923a96d68318e4bab1e8acc93a5c62e5` | yes | `53ac0cee498c2323ef39ca8926ecf6429a5111dccc7447046808626341e71b61` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1811968 | `f21aa1936e19f129e5a28914e21ce174c3a859f5414f1378df1b42ad2be56504` | yes | `a54e069f432d399e995e562dd59f2a3e69decc85a34267c6f32bfa2cfe5c8d3d` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1826304 | `55b5d550ac82a61c4ed70e9fb16f8ca6b10a5caa7ce29f13697bec460dd65407` | yes | `292ad7fdabf9906efacba9dffd34fb8b061205fafb843758668061c0e99438b1` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1781248 | `1c6f568881b02ce1b806e3b8c80e1f3db380c481a0bd4aaad22fe42b465a486d` | yes | `ec2088017ad06e12b1b40588c89459bcc13b83e8c039ccaa721afb708a44a8d7` |
| cheat_upgrades_mobile_renovations | 1778688 | `3c93c5a67ca396ab8059864dfb9f724a12c21a7daea4f629577d9f65a171d3d1` | yes | `5d415ed29e81ee71c12d079c827d2bfb76f800fea45d833e4930b7e3d3887774` |
| core | 1762816 | `c3fedecd743ada4345877913b300ffde4b5cf14284b3eb44290ff235c021433b` | yes | `5f4a49508270cb44365c115204ba8e2027619b8451aabe0caf1b2372150ef681` |
| final_all_enabled | 1857024 | `ee87bddaf573fcbe2aa1a78f5de6bae63cf15d44c64db2c03c225ef053170b8f` | yes | `2a7227ff09b803decbaf52987c2911ff121976b33e87a00606dbb19fccb8080e` |
| holiday_ornaments | 1765376 | `d96ee76ee6c65cca242edd668beeacb79e5c88387b5186535f39368b7763d920` | yes | `8ca5c8e8931315d6db3fabb413d27016c364e2c3ae1e339b092a480e6604e598` |
| holiday_ornaments_behavior_patches | 1810432 | `67b37554fe7f77b9ae1269361e8a0f9a506602d57276bb3fe620be5c33fcf110` | yes | `3e7ddda1efcee490169835ca997c07cc1454cb8b98220a4d7c4c9e6737de478e` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1824768 | `3d40fcf03d97271601ee147e0cc879395cda20879c76299eecd9c26492f38ce3` | yes | `a69bea5c14d3855d54ae24a1143a68c5b697a0f64df9d9633db9396fc763f04f` |
| holiday_ornaments_mobile_renovations | 1779200 | `b0dfb757c5b81e7245b8a6839483cf7b1f3107dc686451702fff9d042b7a5289` | yes | `41a7adb7f2f92500239ad6df058d8b8a62fc2613d9c297e1b1883f551e33a2ee` |
| island_events | 1792512 | `8a5047f9a2b7009d76acaf3b4b351c2b4cb47dde9b48c1d22e8fe340d6d905e1` | yes | `b211752c8babee245ed9d6589b11881273587573afc70597df92da910cf1d1f6` |
| island_events_behavior_patches | 1838080 | `0f120abe0d72f32460ec7dc9b2aa17f2e1f7da4fe4a4658ecd2983a80b97dd66` | yes | `c659dd8e7fafce3671bf9ff7ae44873419f17da5eabbb229c6f9f338060ddc1a` |
| island_events_behavior_patches_mobile_renovations | 1851904 | `993052cad439659bdcb919fcbc5b8ecac8a3dfcfe69f2f6c4fb6bac1981355f7` | yes | `54d0180b9c1523c65f303ac1c0fea7e1df2fac3191a070b61fea37884bd34a0d` |
| island_events_cheat_upgrades | 1794560 | `6c161ac3ed4e7a15f50db908dc1d5759c9ccf4dae883195921ab67ea6f778b60` | yes | `cab3663615a8de80b89c280d1b45b831e7d4330fd7cd3745f2f710de0a7d557f` |
| island_events_cheat_upgrades_behavior_patches | 1840128 | `2b6c2c492f2aba70f1b6f2a5a06db7cb124a4a11d54b96c2f8a50d5b6530d37b` | yes | `5015a7fbe04e42e1ae3b455f15f3c797ab6da85999801f31f160bc835db8b822` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1854464 | `d84857d387af7cdf9d9a5be6e8d09c8f41f7182539519d0c6b0f530c115aa037` | yes | `8fa4893a82f1c077b311972797f26937b5076298c2549102361abce7eec8aa30` |
| island_events_cheat_upgrades_holiday_ornaments | 1797632 | `e8de03ad5fe224708d98b6cae32ad5eea2623e2f4dca8c755a93874fd9af3c89` | yes | `3552bc7c002717b6479851133ff9641d7dd92520eeb59e89df77666a51a9f6fe` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1842688 | `c4b8409893d675e797fb97ecdde43de2f2780baa033c41026da06c21daff3feb` | yes | `a34c462e2406876f226b286e79e8eb9a051505f72523d918a5ffe1dcad17cb41` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1811456 | `c8d9dfc9e35a8302b71ee71e8747c287760ea26a1e5ca102a4503f062fe5e4a6` | yes | `8033c4fbe910e710b4395a691d85b755a930750c0163ff662563b22a8874848e` |
| island_events_cheat_upgrades_mobile_renovations | 1808384 | `63243a30d44a2e16db5d33ba4ef9b745281522414e11a4bc34d65efda46e109b` | yes | `6f6c40f01899cd7ed9214064b8c57f4e125bf6f007ecd41d6ecf5f0b47c8ecbe` |
| island_events_holiday_ornaments | 1795072 | `5fe3db4107fa916133cb1131738a219524901a5c92f33f78fbbc98cd86c1c86b` | yes | `bcbd0d0a5129ecbad89c0eb763abbaf1d2c9ff4f85a13d888bd3b7566116bae6` |
| island_events_holiday_ornaments_behavior_patches | 1840640 | `f5b67b86fe518f32ab2d29826931b4b325522e7330a6d4b63538611b66c67003` | yes | `c1ac0dc44583470e54c6c449df67af83f5fa418dbad6f5a08d9a4b36a5b34cc8` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1854976 | `c83528a9b7aa364c177054c281bb534ec4ae41d4167bcae953c33ebfa7a9c03e` | yes | `90a3b4a4e42c03e4d4ee1ddf94a4c7238118f2d3d206d4367b4b8870f772afc1` |
| island_events_holiday_ornaments_mobile_renovations | 1809408 | `2d4908e588c0d9f2f39283f9df87d5750a13d424b087f765782d96a34bdc2b65` | yes | `65bc0a93283e63560c90a69c86e34f65d3b11b59029051f38c22337a6dbc8c63` |
| island_events_mobile_renovations | 1806848 | `0c7468c7b11967dccbbbf1e69742039f0d0cd711a072dafdd561a08244148c11` | yes | `e178577b6addc0dfc9178aa85787b55750618fdf69aa62e857c16c3c23061ae9` |
| mobile_renovations | 1776640 | `36edcfcd65f04d143acc47cab84a868dde4e77a700c340fce5d45631e0a6d80c` | yes | `30ebb4990d24ddd9ab04236270e464113fac38cdc9f21d6dbf1258b435f1e1fe` |
