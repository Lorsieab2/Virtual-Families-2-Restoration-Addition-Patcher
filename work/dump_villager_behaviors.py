#!/usr/bin/env python3
"""Dump VF2 villager behavior symbols, registered macro IDs, and AI notes."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
OUT = ROOT / "outputs" / "villager-behavior-dump"

BEHAVIOR_DISASM = WORK / "Behavior_patched_disasm.txt"
BEHAVIOR_SYMBOLS = WORK / "Behavior_symbols.txt"


SPONTANEOUS_CANDIDATES: dict[int, dict[str, str]] = {
    0x023: {
        "name": "LieInHammock",
        "criteria": "All ages; refreshed each AI decision; enabled only when Weather.currentType is 0 neutral or 1 sunny.",
    },
    0x095: {"name": "WatchingFirePlace", "criteria": "All ages; weight 3000 when enabled."},
    0x0E8: {"name": "WarmingHands", "criteria": "All ages; weight 3000 when enabled."},
    0x0DC: {"name": "PlayingPinballGames", "criteria": "All ages; weight 3000 when enabled."},
    0x0DD: {"name": "PlayingPinball", "criteria": "All ages; weight 3000 when enabled."},
    0x0DE: {"name": "PlayingSlots", "criteria": "All ages; weight 3000 when enabled."},
    0x0DF: {"name": "PlayingPachinko", "criteria": "All ages; weight 3000 when enabled."},
    0x099: {"name": "PlayingPooltable", "criteria": "All ages; weight 3000 when enabled."},
    0x096: {"name": "PlayingFoosball", "criteria": "All ages; weight 3000 when enabled."},
    0x11E: {
        "name": "PlayOnPlayStructure / Playhouse",
        "criteria": "Children only, max age 0x117; refreshed each AI decision; enabled only when CNight::AIIsDayTime() is true.",
    },
    0x130: {
        "name": "ChildrenPlayAtKidsTable / Playing quietly",
        "criteria": "Children only, max age 0x117; weight 3000 when enabled.",
    },
    0x0ED: {"name": "DancingRadio", "criteria": "Existing stock candidate age gates retained; weight 3000 when enabled."},
    0x0F5: {"name": "ListenToRadio", "criteria": "Existing stock candidate age gates retained; weight 3000 when enabled."},
    0x118: {"name": "DrawingOnEasel", "criteria": "Existing stock candidate age gates retained; weight 3000 when enabled."},
}


SELECTION_CRITERIA = [
    {
        "field": "candidate table base",
        "offset": "CVillager+0x6BB8",
        "meaning": "Start of CVillager autonomous AI candidate table.",
    },
    {
        "field": "candidate stride",
        "offset": "0xD0 bytes",
        "meaning": "Each behavior ID has one SBehaviorData-like candidate record.",
    },
    {
        "field": "enabled",
        "offset": "candidate+0xCD",
        "meaning": "CVillagerAI::DecideWhatToDo skips records with this byte clear.",
    },
    {
        "field": "weight",
        "offset": "candidate+0x0C",
        "meaning": "Weighted random-choice value. Current behavior patch uses 3000 for newly enabled candidates.",
    },
    {
        "field": "max age",
        "offset": "candidate+0x48",
        "meaning": "Upper age gate. Child-only patches set 0x117; stock child boundary is CVillager+0x6A54 < 0x118.",
    },
    {
        "field": "min age",
        "offset": "candidate+0x4C",
        "meaning": "Lower age gate. Current all-age and child-only patch helpers set this to 0.",
    },
    {
        "field": "required weather",
        "offset": "candidate+0xA8",
        "meaning": "If not -1, CVillagerAI compares it with Weather.currentType.",
    },
    {
        "field": "forbidden weather",
        "offset": "candidate+0xAC",
        "meaning": "If not -1, CVillagerAI rejects the candidate when it matches Weather.currentType.",
    },
    {
        "field": "time/environment/stat gates",
        "offset": "multiple candidate fields",
        "meaning": "CVillagerAI calls CNight helpers and checks villager stat/environment fields before adding a candidate to the weighted pool; several fields are mapped only by offset so far.",
    },
]


def clean_behavior_name(symbol: str) -> str:
    return symbol.split("@CBehavior@@", 1)[0].lstrip("?")


def category_for_name(name: str) -> str:
    lowered = name.lower()
    buckets = [
        ("holiday", ("xmas", "santa", "stocking", "christmas")),
        ("furniture/game", ("pinball", "pachinko", "pool", "foosball", "hammock", "fireplace", "radio", "tv", "easel")),
        ("child/play", ("child", "children", "kid", "toy", "play")),
        ("chore/repair", ("clean", "fix", "repair", "laundry", "trash", "dust", "weed", "hole")),
        ("food/cooking", ("meal", "cook", "food", "drink", "snack", "cinnamon")),
        ("pet", ("pet", "dog", "cat")),
        ("health/status", ("sick", "depressed", "sleep", "shower", "toilet", "brush")),
        ("work/study", ("work", "career", "study", "book", "magazine", "office")),
    ]
    for category, needles in buckets:
        if any(needle in lowered for needle in needles):
            return category
    return "general"


def parse_registered_behaviors(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"push\s+offset\s+(\?[^\r\n]+?@CBehavior@@[^\r\n]+?)\r?\n"
        r"\s*[0-9A-F]+:\s+(?:6A\s+[0-9A-F]{1,2}|68\s+[0-9A-F ]{11})\s+push\s+([0-9A-F]+)h?",
        re.IGNORECASE,
    )
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for match in pattern.finditer(text):
        symbol = match.group(1)
        behavior_id = int(match.group(2), 16)
        name = clean_behavior_name(symbol)
        key = (behavior_id, name)
        if key in seen:
            continue
        seen.add(key)
        spontaneous = SPONTANEOUS_CANDIDATES.get(behavior_id)
        rows.append(
            {
                "id": behavior_id,
                "id_hex": f"0x{behavior_id:03X}",
                "name": name,
                "symbol": symbol,
                "category": category_for_name(name),
                "patched_spontaneous": bool(spontaneous),
                "spontaneous_criteria": spontaneous["criteria"] if spontaneous else "",
            }
        )
    rows.sort(key=lambda row: (row["id"], row["name"]))
    return rows


def parse_behavior_symbols(text: str) -> list[dict[str, str]]:
    pattern = re.compile(r"\|\s+(\?[^|\r\n]+?@CBehavior@@[^\r\n]+)")
    names: dict[str, str] = {}
    for match in pattern.finditer(text):
        symbol = match.group(1).strip()
        if "@@CAXAAVCVillager@@@Z" not in symbol and "@@IBE?B_NAAVCVillager@@" not in symbol:
            continue
        name = clean_behavior_name(symbol)
        names[name] = symbol
    return [
        {"name": name, "symbol": symbol, "category": category_for_name(name)}
        for name, symbol in sorted(names.items())
    ]


def write_markdown(report: dict[str, Any], path: Path) -> None:
    registered = report["registered_behaviors"]
    symbols = report["all_cbehavior_symbols"]
    spontaneous = [row for row in registered if row["patched_spontaneous"]]
    category_counts: dict[str, int] = {}
    for row in registered:
        category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1

    lines: list[str] = [
        "# VF2 Villager Behavior Dump",
        "",
        "Generated from `work/Behavior_patched_disasm.txt`, `work/Behavior_symbols.txt`, and the current spontaneous-behavior patch code.",
        "",
        "## Summary",
        "",
        f"- Registered behavior macros: {len(registered)} unique ID/name pairs.",
        f"- CBehavior symbols recovered: {len(symbols)}.",
        f"- Patched spontaneous candidates documented here: {len(spontaneous)}.",
        "",
        "## How Villagers Choose Spontaneous Actions",
        "",
        "- `CVillager::InitAI` initializes an autonomous candidate table at `CVillager+0x6BB8`.",
        "- Each behavior candidate record is `0xD0` bytes, indexed by behavior ID.",
        "- `CVillagerAI::DecideWhatToDo` walks the candidate table, rejects records that fail gates, then chooses from the remaining weighted pool.",
        "- The current mod does not replace the `Bored` behavior. It enables existing native candidates after `CVillager::InitAI`, after `CVillager::LoadAI`, and refreshes weather/time-sensitive candidates during `CVillagerAI::DecideWhatToDo`.",
        "",
        "## Candidate Record Fields",
        "",
        "| Field | Offset | Meaning |",
        "| --- | --- | --- |",
    ]
    for row in SELECTION_CRITERIA:
        lines.append(f"| {row['field']} | `{row['offset']}` | {row['meaning']} |")

    lines.extend(["", "## Patched Spontaneous Candidates", "", "| ID | Behavior | Criteria |", "| --- | --- | --- |"])
    for row in spontaneous:
        lines.append(f"| `{row['id_hex']}` | `{row['name']}` | {row['spontaneous_criteria']} |")

    lines.extend(["", "## Registered Behavior Category Counts", ""])
    for category, count in sorted(category_counts.items()):
        lines.append(f"- {category}: {count}")

    lines.extend(["", "## Registered Behavior Macros", "", "| ID | Name | Category | Patched spontaneous? |", "| --- | --- | --- | --- |"])
    for row in registered:
        lines.append(
            f"| `{row['id_hex']}` | `{row['name']}` | {row['category']} | {'yes' if row['patched_spontaneous'] else ''} |"
        )

    lines.extend(["", "## Notes / Limits", ""])
    lines.append("- This dump identifies registered native behavior macros and the spontaneous candidates currently enabled by our patch.")
    lines.append("- It does not claim every registered behavior is normally spontaneous in stock PC; many are manual, scripted, repair, event, or dispatch behaviors.")
    lines.append("- Several stock candidate fields are still named by offset only. The report keeps those as low-level criteria rather than pretending they are fully understood.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    behavior_text = BEHAVIOR_DISASM.read_text(encoding="utf-8", errors="ignore")
    symbol_text = BEHAVIOR_SYMBOLS.read_text(encoding="utf-8", errors="ignore")
    registered = parse_registered_behaviors(behavior_text)
    symbols = parse_behavior_symbols(symbol_text)
    report = {
        "sources": {
            "behavior_disasm": str(BEHAVIOR_DISASM.relative_to(ROOT)),
            "behavior_symbols": str(BEHAVIOR_SYMBOLS.relative_to(ROOT)),
            "patch_source": "work/patch_mobile_furniture_pack.py::patch_spontaneous_behaviors",
        },
        "selection_criteria": SELECTION_CRITERIA,
        "registered_behaviors": registered,
        "all_cbehavior_symbols": symbols,
        "patched_spontaneous_candidates": [
            row for row in registered if row["patched_spontaneous"]
        ],
    }
    (OUT / "villager_behaviors.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (OUT / "villager_behaviors.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "id_hex", "name", "category", "patched_spontaneous", "spontaneous_criteria", "symbol"],
        )
        writer.writeheader()
        writer.writerows(registered)
    write_markdown(report, OUT / "villager_behaviors.md")
    print(f"Wrote {OUT / 'villager_behaviors.md'}")
    print(f"Registered behavior macros: {len(registered)}")
    print(f"CBehavior symbols: {len(symbols)}")
    print(f"Patched spontaneous candidates: {len(report['patched_spontaneous_candidates'])}")


if __name__ == "__main__":
    main()
