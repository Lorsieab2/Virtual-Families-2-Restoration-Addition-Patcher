# B204 matrix manifest

Built from main `412660f` (the merge of PR #438, Family Tree Maker; tree `4383705bd5ecb36906b42d03384da7f257adaed1`, recorded in `data/vf2/build-matrix-release-b204.json`) with `work/build_matrix_parallel.ps1` (three parallel parts of `work/build_matrix.ps1` in three worktrees of that one commit): 32 variants, seeded from the B203 matrix, 32 distinct executables. Every executable now carries a third dormant loader, `.vf2hist` (0 as built), for the Family History log (PR #437), after the Time Controls and Up to 28 Children loaders.

Release DLLs, shipped in the bundle:

- `vf2time_b200.dll`: SHA-256 `3ea0a2a5689ecbf5d1bef05368493adb3f54b8e0e96343b2d75a585267b1d35e`, the B201-B203 file (`runtime/native/b200time` unchanged since).
- `vf2kids_b200.dll`: SHA-256 `4a6bb5ff9d418849b4e750884307eb74b1b1488a51d251bea2d813cee3989f0f`, the B202-B203 file (`runtime/native/b200kids` unchanged since).
- `vf2history_b200.dll`: SHA-256 `0c01c1659d6b54f071ac17b1d4b7f52d62a5c1687b08fd592b83c0f9eff0aaf5`, built from `412660f` with `runtime/native/build_b200history.bat`.

| Variant | Size (bytes) | SHA-256 |
|---|---|---|
| behavior_patches | 1809920 | `110f5ab8c1dea5a6cd3d4418c2bb3bbe348c2d4e634d363a45d5f8935198e5f0` |
| behavior_patches_mobile_renovations | 1824256 | `4a87d91615e68865b7d69a5f351cdf29b6e8d62989d7857da55880d112076cf1` |
| cheat_upgrades | 1766400 | `04c6441134e5fbfbdb33902f8979a7d1df034c3c86a2d86c72be53a31769dbc8` |
| cheat_upgrades_behavior_patches | 1812480 | `673aab8b226abd459d7f76ad556943606e033f1110467f11960d6d39bb23a50f` |
| cheat_upgrades_behavior_patches_mobile_renovations | 1826304 | `19cec271c871fe01b039690b4f8d97cdc8bf9083de66ab8e054ed859f9a9c540` |
| cheat_upgrades_holiday_ornaments | 1768960 | `4f1b70503096d7870fb441b90badf37cdd21f48c67b4c99a736584f6eb27f2f1` |
| cheat_upgrades_holiday_ornaments_behavior_patches | 1814528 | `8dd9072a220e7cab2f21db1e3ae0bb40823fb49c98e92f93ca19a68ded3b494f` |
| cheat_upgrades_holiday_ornaments_behavior_patches_mobile_renovations | 1828864 | `3946963c99d749e2d018ded4957573e7cc48a068aca7af5d34a716fddc289459` |
| cheat_upgrades_holiday_ornaments_mobile_renovations | 1783296 | `3a760ba4208a38f5fbc51808313f1bfb66599b172a6b0f2a21c700d4e9cc3954` |
| cheat_upgrades_mobile_renovations | 1780736 | `a96870e37340086e7a70d8d0e30b0d3591984f151ae6d8a6db0b622bb10df4a0` |
| core | 1764864 | `d20aad5f8664fa04da23a29055c0158f9b56ac06d70c1ed53c083272fd47e265` |
| final_all_enabled | 1859072 | `d055cb899ccac5b779ea387a051057a884e3ebce2e9386b9dcd0f0da893be927` |
| holiday_ornaments | 1767424 | `d701e5c5aee69bf4a805e3228cd5013f7ee66ea3ad38cf24a16a9b5efabcf31d` |
| holiday_ornaments_behavior_patches | 1812480 | `217be36c8a072d166669c4c2536e5034c40f880caf5f6a48868810df19862b57` |
| holiday_ornaments_behavior_patches_mobile_renovations | 1826816 | `6e347c068723cd84e826089253618864eb8586dcd1def07178784a048001fada` |
| holiday_ornaments_mobile_renovations | 1781760 | `aad7fcaab57c06d22711e8fc80410bae1f4bb0754b7d3bf873070affda58d5f2` |
| island_events | 1795072 | `c08c99db732a67bdb3a227de9ba7657565e2658ca3b1ebddc13e00e45af99690` |
| island_events_behavior_patches | 1840128 | `c45ea2df95eda516bdcf7f5e472972e9fb5950859362163de7827179737ab896` |
| island_events_behavior_patches_mobile_renovations | 1854464 | `4796f61aff6e4515a21e6d4c4dc15710e3482e939f5f146b43a5b57c35b747ed` |
| island_events_cheat_upgrades | 1797120 | `93c7b6614d380f6c309cc4b5e26aae0d25ebd5bdc6310978186c040d88615959` |
| island_events_cheat_upgrades_behavior_patches | 1842688 | `e7181052e493d7006719597fe8e6dd4e7fe3d861eaf2eb5202a213899f8afe41` |
| island_events_cheat_upgrades_behavior_patches_mobile_renovations | 1856512 | `edc3c76ed0e4bb0e49aad56879bbb64b641c3647d9ca477c31926345da64ae13` |
| island_events_cheat_upgrades_holiday_ornaments | 1799680 | `56e51fda145b03b0b5608cb73d6ccbfd97b89c09aaaa252d356e355397a77b77` |
| island_events_cheat_upgrades_holiday_ornaments_behavior_patches | 1845248 | `2f3d904ce8ba7e29e57a8cea702eee26db34203bb4f95ea80b35105bad32ea79` |
| island_events_cheat_upgrades_holiday_ornaments_mobile_renovations | 1813504 | `73274f455dfc9b6c020bd211494adb6f9914ba498c76ee9c3de0ee938669de48` |
| island_events_cheat_upgrades_mobile_renovations | 1810432 | `d0f62e711bb188dd7a5d2355257f1bdc70bad507f461ea783f2c871b8272cd79` |
| island_events_holiday_ornaments | 1798144 | `2154136f706d1bc0e0006f727a49295930d5bd12a5cd12e6f95511bd23f18e5b` |
| island_events_holiday_ornaments_behavior_patches | 1842688 | `88d7a150d22646f8a5b6963936db50ee6005922f47eb67d60ff6b4fb327476cc` |
| island_events_holiday_ornaments_behavior_patches_mobile_renovations | 1857024 | `85a1062417506fe59821e9258ddcc04297dd90e414cb7ae0c419fae0a4edb6a6` |
| island_events_holiday_ornaments_mobile_renovations | 1811456 | `52334b560fc868a425d1b0e6660eb77eb20b8894e4e54894a7b42e3759339e86` |
| island_events_mobile_renovations | 1808896 | `3b501e1285967a7bc99b252add4393a206379aaa0f1e71d47103ec056ea46b73` |
| mobile_renovations | 1779200 | `9e382f6abf6662523936409e8c702d006bbdc396ca2f89c6aaeda2af6ce60818` |
