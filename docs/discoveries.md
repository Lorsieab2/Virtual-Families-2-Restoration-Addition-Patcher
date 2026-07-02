# Discoveries

## 2026-07-02 - General Appliances Count Collision

- `gAppliancesList` stock count is `15` (`0x0F`), with max index `14`
  (`0x0E`).
- After additive pet support, `gPetList` also has count `15`; broad patching of
  `6A 0F` or `83 FE 0E` can widen pet paths while trying to add VF3 TVs.
- Safe General Appliances widening is now targeted to
  `CInventoryManager::GetCategoryItem` offsets `0x73` and `0x95`, plus
  `CInventoryManager::GetCategoryItemCount` offset `0x37`.
- Accessories worked with the earlier pattern approach because its stock count
  `47` was distinctive in the patched object, but that should not be treated as
  safe for small/common category counts.
