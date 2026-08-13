from __future__ import annotations

import json
from collections import Counter

import patch_mobile_furniture_pack as patcher


def main() -> None:
    by_category = Counter(list_name for _name, _donor, list_name, _path in patcher.ITEMS)
    by_pack = Counter(
        patcher.MOBILE_DATA_BY_PATH[path].get("custom_pack", "mobile_vf2_android")
        for _name, _donor, _list_name, path in patcher.ITEMS
    )
    report = {
        "furniture_and_store_items": {
            "enabled": True,
            "added_record_count": len(patcher.ITEMS),
            "by_store_list": dict(sorted(by_category.items())),
            "by_source_pack": dict(sorted(by_pack.items())),
        },
        "pets": {
            "enabled": True,
            "added_count": len(patcher.PET_STORE_ADDITIONS),
            "items": [
                {
                    "name": item["name"],
                    "item_id": hex(item["item_id"]),
                    "list": item["list"],
                    "source": item["source"],
                }
                for item in patcher.PET_STORE_ADDITIONS
            ],
        },
        "island_events": {
            "enabled_by_default": patcher.ENABLE_ISLAND_EVENTS,
            "mapping_csv": str(patcher.MOBILE_EVENT_MAPPING_CSV),
            "text_pack_csv": str(patcher.MOBILE_EVENT_TEXT_PACK),
        },
        "holiday_outfits": {
            "enabled_by_default": patcher.ENABLE_HOLIDAY_BODY_TYPES,
            "body_values": list(patcher.HOLIDAY_BODY_VALUES),
            "source_sets": list(patcher.HOLIDAY_BODY_SET_IDS),
            "note": "Opt-in through VF2_ENABLE_HOLIDAY_BODY_TYPES=1 until stable.",
        },
        "native_array_contract": patcher.build_native_array_contract(),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
