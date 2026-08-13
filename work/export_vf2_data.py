"""Export transparent, source-labeled VF2 desktop/mobile data summaries."""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import patch_mobile_furniture_pack as vf2  # noqa: E402

OUT = Path(sys.argv[1]).resolve()
MANIFEST = json.loads((OUT / "patch-manifest.json").read_text(encoding="utf-8"))

AUTONOMOUS_BEHAVIORS = [
    {"id": "0x023", "name": "Relaxing in hammock", "all_ages": True, "conditions": ["weather neutral", "weather sunny"]},
    {"id": "0x095", "name": "Watching fireplace", "all_ages": True},
    {"id": "0x0E8", "name": "Warming hands by fireplace", "all_ages": True},
    {"id": "0x0DC", "name": "Playing pinball games", "all_ages": True},
    {"id": "0x0DD", "name": "Playing pinball", "all_ages": True},
    {"id": "0x0DE", "name": "Playing slots", "all_ages": True},
    {"id": "0x0DF", "name": "Playing pachinko", "all_ages": True},
    {"id": "0x099", "name": "Playing pool", "all_ages": True},
    {"id": "0x096", "name": "Playing foosball", "all_ages": True},
    {"id": "0x0ED", "name": "Dancing", "all_ages": False},
    {"id": "0x0F5", "name": "Listening to radio", "all_ages": False},
    {"id": "0x118", "name": "Drawing", "all_ages": False},
]

COLLECTIBLE_CATEGORIES = [
    "Bones", "Leaves & Nuts", "Bugs", "Bones 2", "Pterodactyl", "Caps", "Ornaments"
]


def mobile_store_items():
    with vf2.MOBILE_CSV.open(newline="", encoding="utf-8-sig") as stream:
        return [row for row in csv.DictReader(stream) if row.get("source") == "mobile_vf2_android"]


def event_data():
    rows = []
    for event in vf2.load_mobile_island_events():
        strings = {entry["kind"]: entry["text"] for entry in event["strings"]}
        rows.append({
            "name": event["name"],
            "mobile_class": event["class"],
            "mobile_table_slot": event["slot"],
            "has_choices": event["has_choices"],
            "is_email_event": event["is_email_event"],
            "outcomes": {
                "choice_a": strings.get("ResultA"),
                "choice_b": strings.get("ResultB"),
            },
            "likelihood": {"value": None, "status": "not_decoded_from_mobile_native_event_scheduler"},
        })
    return rows


def collectible_data():
    return [
        {
            "category": category,
            "rarity": {"value": None, "status": "not_decoded"},
            "spawning": {
                "status": "native random-yard collectible system",
                "weights": "not_decoded",
                "holiday_collection": category == "Ornaments",
            },
        }
        for category in COLLECTIBLE_CATEGORIES
    ]


def extract_goals(binary_path):
    data = binary_path.read_bytes()
    strings = [chunk.decode("latin1", errors="ignore") for chunk in data.split(b"\0")]
    goals = []
    for index, key in enumerate(strings):
        match = re.fullmatch(r"eString_Achievement(.+)Title", key)
        if not match or index + 3 >= len(strings):
            continue
        if strings[index + 2] != f"eString_Achievement{match.group(1)}Desc":
            continue
        goals.append({"id": match.group(1), "title": strings[index + 1], "description": strings[index + 3]})
    return goals


base_records = sorted(vf2.raw_records_by_item().values(), key=lambda item: item["item_id"])
desktop = {
    "build": "B47",
    "villager_behaviors": {
        "spontaneous_additions": AUTONOMOUS_BEHAVIORS,
        "mechanic": "Existing CVillagerAI weighted candidate selection; additive candidate enablement after InitAI and LoadAI.",
        "bookshelf_drop": "Native Read Magazine / Reading Book selected randomly.",
    },
    "store_items": {
        "base_desktop_records": base_records,
        "additive_items": MANIFEST.get("items", []),
        "new_tvs": [item for item in MANIFEST.get("items", []) if item["name"] in {"VF3LargeFlatScreenTV", "VF3SmallFlatScreenTV"}],
    },
    "island_events": {
        "status": MANIFEST.get("IslandEvents", {}).get("status"),
        "mobile_event_definitions": event_data(),
    },
    "collectibles": collectible_data(),
}

mobile = {
    "source": "VF2 mobile APK analysis",
    "villager_behaviors": {"status": "native behavior IDs not fully decoded", "known_requested_behavior_ids": AUTONOMOUS_BEHAVIORS},
    "store_items": mobile_store_items(),
    "island_events": event_data(),
    "collectibles": collectible_data(),
}

(OUT / "VF2_Desktop_B47_Game_Data.json").write_text(json.dumps(desktop, indent=2), encoding="utf-8")
(OUT / "VF2_Mobile_Game_Data.json").write_text(json.dumps(mobile, indent=2), encoding="utf-8")
(OUT / "VF2_Desktop_Base_Game_Goals.json").write_text(json.dumps(extract_goals(ROOT / "Unneeded crap" / "VF2-Mobile-Furniture-Modded" / "Virtual Families 2 - Copy Official.exe"), indent=2), encoding="utf-8")
(OUT / "VF2_Mobile_Goals.json").write_text(json.dumps(extract_goals(ROOT / "work" / "vf2_apk_extract" / "lib" / "x86" / "libVirtualFamilies2.so"), indent=2), encoding="utf-8")
