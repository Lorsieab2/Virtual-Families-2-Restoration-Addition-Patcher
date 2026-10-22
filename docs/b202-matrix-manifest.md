# B202 matrix manifest

Built from main `0f7dc32` (the merge of PR #424, Up to 28 Children; tree `711f7f46362e0a7f2eb13384c7558ec94b1b29fc`, recorded in `data/vf2/build-matrix-release-b202.json`) with `work/build_matrix.ps1`: 32 variants, seeded from the B201 matrix, run as three parallel thirds in three worktrees of that one commit (the generator writes `work/patched_mobile_furniture_pack_objs`, so one worktree can build one variant at a time). Each variant linked, and each carries both dormant loaders: Time Controls (`.vf2time` byte 0 as built) and Up to 28 Children (`.vf2kids` byte 0 as built, with the empty `.vf2kidt` table). Every hash differs from B201's: the Up to 28 Children generator changes are in every executable.

Release DLLs, shipped in the bundle:

- `vf2time_b200.dll`: SHA-256 `3ea0a2a5689ecbf5d1bef05368493adb3f54b8e0e96343b2d75a585267b1d35e`, the B201 release file itself (`runtime/native/b200time` has not changed since B201, `2e326b6..0f7dc32`). A fresh build from `0f7dc32` differs from it in six bytes only, all linker timestamps (PE header `TimeDateStamp` at 0x110-0x112, debug-directory `TimeDateStamp` in `.rdata` at 0x1EE2C-0x1EE2E), so the shipped Time Controls DLL is exactly B201's.
- `vf2kids_b200.dll`: SHA-256 `4a6bb5ff9d418849b4e750884307eb74b1b1488a51d251bea2d813cee3989f0f`, built from `0f7dc32` with `runtime/native/build_b200kids.bat`. It differs from the PR #424 head build (`C:\vf2w\wt-kids`, 747b21c) in four bytes, all linker timestamps (0x110-0x111 and 0x17CBC-0x17CBD); exports `B200Kids_Startup`, no test entry points.

Checked for every executable (static and emulated, `VF2_B200_CORE_EXE` = the B200 core executable for the pin model): the `.vf2time` and `.vf2kids` bytes are 0 and `.vf2kidt` is the empty table (magic, version 1, count 0, 22 slots of -1); the Time Controls loader end to end under emulation at the link address and relocated (byte 0 never loads, byte 1 with ini 0 installs nothing, missing DLL harmless, byte 1 with ini 1 installs); the Up to 28 Children loader end to end the same way, alone and after the Time Controls DLL (exactly its eleven entry jumps). Both features' pins resolve exactly once in all 32 (`tests/test_b200_time_controls.py` and `tests/test_b200_up_to_28_children.py` with `VF2_B200_MATRIX_GLOB` over this matrix). No live test.

| Variant | Size (bytes) | SHA-256 | Resolved and both loaders checked |
|---|---|---|---|
| behavior_patches | 1809408 | `c913b6b26c457101c16bf6b226cfc8a142e4d323bab5bb7b5fcdfe779aab015f` | yes |
| behavior_patches_mobile_renovations | 1823232 | `2f19cd51d530cdbb678cd49f26d4eeabcfc23849ce64d520127e1f5f2b922478` | yes |
| cheat_upgrades | 1765888 | `1ee47d2fbe7d69738e390f91ece916e5b1a539bfc32455beca1637a6b47ef74b` | yes |
| cheat_upgrades_behavior_patches | 1811456 | `df8a7605c965b525fc886a2e02e03e8c3c5c6d11b9fd6d3b8bb624700aa95668` | yes |
| cheat_upgrades_behavior_patches_mobile_renovations | 1825792 | `e31968bcc2962e3bdac3ffbf2c5a00f714bddb5c39fc7a768c8f02035a0647ae` | yes |
| cheat_upgrades_holiday_ornaments | 1768448 | `f2d8cfae5e2a34535fbb94db7c45b2a0e5b2961584ca2daf9a5adcfdd882f647` | yes |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1813504 | `0a7974937bf7be879fd071110197b265293a2ace454df0117323d25c54fde49a` | yes |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1827840 | `b0bd866d3d45c32792d68ca72e738117edd7686e345497e38b62b2c0a78e1240` | yes |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1782272 | `394e83df3b036e219d0859c9eb10f63d5c3858bba98a0e416638027c61588742` | yes |
| cheat_upgrades_mobile_renovations | 1779712 | `c08d52acf655021fdff6372998d35a8fc23455974e28d1229386ab7f6874ca33` | yes |
| core | 1763840 | `3ad8982566b77bc1e89ccce780d30f989d77705b06ade60d990e129f52d1a464` | yes |
| final_all_enabled | 1858560 | `d72c1db1d3caf9ccfaec5be701a8c64e7ef8486fc056b01a8c14d00e9a92b86d` | yes |
| holiday_ornaments | 1766400 | `561e51a61629a17a1353be80437d411893cd7a763865e1d9282d07894f058006` | yes |
| holiday_ornaments_behavior_patches | 1811968 | `ef4fa982eaa7c9fd91d17bc9d87d4e7dba06fccb2ddb4d601dff82b9355158d7` | yes |
| holiday_ornaments_behavior_patches_mobile_renovations | 1826304 | `61c131113b85f32be4f5af7b140654ce986eece3d166f779637928cef8ad21dc` | yes |
| holiday_ornaments_mobile_renovations | 1780736 | `bad014c120c74922b2295631767f42135ea0063b3034a315f0d4905bce455050` | yes |
| island_events | 1794048 | `b94039c2f868ca6352534a6957216a3ce0a919b980d9826fbb857f2b644e19b3` | yes |
| island_events_behavior_patches | 1839104 | `b0bbad9338b3b36d6ea4818d168b66ba522608aaa199cbec94c2185312efde0a` | yes |
| island_events_behavior_patches_mobile_renovations | 1853440 | `06f98f4242a3496b039a2a3749e2308ecb6941cb18e5936af64f9a96f1e87c4f` | yes |
| island_events_cheat_upgrades | 1796096 | `56d88022049292d93395184b9d61430cf64d80a7894614ed9893f16c1bf5cc79` | yes |
| island_events_cheat_upgrades_behavior_patches | 1841664 | `9934c5b3c6d3b233978425c1894d0a6bcafe85916172f522f59ccf64ab7866aa` | yes |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1856000 | `cc2173b5dcbfcc3f10f5714a7e2dea816513952492fd2086189b17858195147a` | yes |
| island_events_cheat_upgrades_holiday_ornaments | 1799168 | `8c2a2b38037c3024049b7a4d977db877f483b937e1b0eeb78e5caaecbea16443` | yes |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1844224 | `37873b461788f47e53d8b21a0d0e0182dd20ad5051b70fe9744feffe2df32615` | yes |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1812992 | `782781aaa1e50c3b896ebb0f3975a387a86a422380c4ce28f41974fb5dca0431` | yes |
| island_events_cheat_upgrades_mobile_renovations | 1809920 | `b5fb57e15082e47d28657e61cc09a540d717984a681bc4c51a78b4f621145b18` | yes |
| island_events_holiday_ornaments | 1797120 | `341d6ea31ee86ef7d62a30dc8d0a9a8873ac1e2d830deac8c309cb49097629b3` | yes |
| island_events_holiday_ornaments_behavior_patches | 1842176 | `1fde4845f82ab95cb7a6b050c488db3da22d9be98617192c23b27f43021ecacd` | yes |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1856000 | `5eddc59005fd4dd56e8a9a448f2cedaa0244a25a5a8af392dac34dfba234a4a2` | yes |
| island_events_holiday_ornaments_mobile_renovations | 1810944 | `8f34ae6cb38b4eb8556b5104dc6e3801b1e4da73f5dc09476bf3d32c10048289` | yes |
| island_events_mobile_renovations | 1808384 | `0b51582810f930494f1b9d84ef0f5367247f14421639044690b173edf371bf7d` | yes |
| mobile_renovations | 1778176 | `f8c37eaca54e70ae0b0445786767a22f52f16b8157dac13ed3ba286b1bcb82a2` | yes |
