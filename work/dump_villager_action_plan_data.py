#!/usr/bin/env python3
"""Create human-readable VF2 villager behavior/action-plan dumps.

The source files are text dumps produced by Microsoft's COFF dumper.  This
script does not disassemble new binaries; it groups existing human-readable
disassembly into behavior functions, extracts calls into CVillagerPlans, and
keeps nearby push constants so body/head/duration arguments can be reviewed.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
OUT = ROOT / "outputs" / "villager-action-plan-dump"

BEHAVIOR_DISASM = WORK / "dump_behavior_disasm.txt"
BEHAVIOR_SYMBOLS = WORK / "Behavior_symbols.txt"
PLANS_DISASM = WORK / "dump_villagerplans_disasm.txt"
PLANS_SYMBOLS = WORK / "VillagerPlans_symbols.txt"


CALL_RE = re.compile(
    r"^\s*(?P<offset>[0-9A-F]{8}):\s+(?P<bytes>(?:[0-9A-F]{2}\s+)+)"
    r"call\s+(?P<symbol>\?[^\r\n]+)$"
)
FUNCTION_RE = re.compile(r"^(?P<symbol>\?[^\r\n]+):$")
PUSH_RE = re.compile(
    r"^\s*(?P<offset>[0-9A-F]{8}):\s+(?P<bytes>(?:[0-9A-F]{2}\s+)+)"
    r"push\s+(?P<operand>.+)$",
    re.IGNORECASE,
)
MOV_RE = re.compile(
    r"^\s*(?P<offset>[0-9A-F]{8}):\s+(?P<bytes>(?:[0-9A-F]{2}\s+)+)"
    r"mov\s+(?P<dst>[^,]+),(?P<src>.+)$",
    re.IGNORECASE,
)
CMP_RE = re.compile(
    r"^\s*(?P<offset>[0-9A-F]{8}):\s+(?P<bytes>(?:[0-9A-F]{2}\s+)+)"
    r"cmp\s+(?P<left>[^,]+),(?P<right>.+)$",
    re.IGNORECASE,
)


BODY_POSITION_NAMES = {
    0x00: "stock/default standing or wait body position",
    0x09: "resting hammock lead-in pose",
    0x17: "common wait/rest pose used by leak reactions and other action chains",
}

HEAD_DIRECTION_NAMES = {
    -2: "random",
    -1: "keep/default",
    1: "NE",
    7: "NW",
}

SPEED_NAMES = {
    0x64: "normal-ish speed",
    0xC8: "fast/common behavior speed",
}

PRIORITY_NAMES = {
    0: "normal/default priority",
    1: "high/front priority",
}

CONTENT_OBJECT_NAMES = {
    0x0D: "TV",
    0x5B: "Hammock",
}

VILLAGER_FIELD_NOTES = {
    0x6A54: "Age/growth field. Stock behavior gates use < 0x118 as non-adult and >= 0x118 as adult.",
    0x6A58: "Likely gender field. Stock routines compare it to 0/1 and use it for gender-specific asset/routing decisions.",
    0x6A5C: "Likely body/clothing value. Frequently read by body/outfit graphics selection paths.",
    0x6A60: "Likely head/voice selector. MomTeachingTalk reads it while choosing baby-talk sounds; it is not a confirmed baby/nursing counter.",
    0x1BBA8: "Current action/status label buffer. CBehavior routines copy string-manager text here with a 0x27 byte limit.",
}


@dataclass
class FunctionBlock:
    symbol: str
    name: str
    lines: list[str]


def undecorate_class_method(symbol: str, class_name: str) -> str:
    prefix = "?"
    marker = f"@{class_name}@@"
    if symbol.startswith(prefix) and marker in symbol:
        return symbol[1:].split(marker, 1)[0]
    return symbol


def parse_signature(symbol: str) -> tuple[str, list[str]]:
    """Return a compact method name and argument names inferred from decoration."""
    name = undecorate_class_method(symbol, "CVillagerPlans")
    args: list[str] = []
    readable = symbol
    if "PlanToWait" in name:
        if "W4EDirection@@W4EHeadDirection" in readable:
            args = ["duration", "bodyPosition", "direction", "headDirection"]
        elif "W4EHeadDirection" in readable:
            args = ["duration", "bodyPosition", "headDirection"]
        else:
            args = ["duration", "bodyPosition"]
    elif "PlanToPlayAnim" in name:
        if "PBD" in readable:
            args = ["duration", "animName", "unknownBool", "speed"]
        else:
            args = ["duration", "animEnum", "unknownBool", "speed"]
    elif "PlanToGo" in name:
        if "W4EObject@CContentMap" in readable:
            args = ["contentObject", "speed", "priority", "allowBlocked?"]
        elif "UldwPoint" in readable and "HH" in readable:
            args = ["point", "xOffset", "yOffset", "speed", "priority", "unknownBool"]
        elif "UldwPoint" in readable:
            args = ["point", "speed", "priority"]
        elif "W4EWaypoint" in readable and "UldwPoint" in readable:
            args = ["waypoint", "point", "speed", "priority"]
        elif "W4EWaypoint" in readable:
            args = ["waypoint", "speed", "priority"]
        elif "HHHH" in readable:
            args = ["x", "y", "xOffset", "yOffset", "speed", "priority", "unknownBool"]
        elif "HH" in readable:
            args = ["x", "y", "speed", "priority"]
    elif "PlanToShakeHead" in name:
        args = ["duration", "bodyPosition"]
    elif "PlanToPlaySound" in name:
        args = ["sound", "volumeOrDelay", "soundType"]
    elif "PlanToWork" in name:
        args = ["duration"]
    elif "PlanToJump" in name:
        args = ["duration"]
    elif "PlanToCarry" in name:
        args = ["carrying"]
    elif "PlanToSay" in name:
        args = ["stringId"]
    elif "PlanToInc" in name or "PlanToDec" in name:
        args = ["amount"]
    return name, args


def signed32(value: int) -> int:
    return value - 0x100000000 if value & 0x80000000 else value


def int_from_push_bytes(byte_text: str) -> int | None:
    parts = [int(part, 16) for part in byte_text.split()]
    if not parts:
        return None
    if parts[0] == 0x6A and len(parts) >= 2:
        value = parts[1]
        return value - 0x100 if value & 0x80 else value
    if parts[0] == 0x68 and len(parts) >= 5:
        return signed32(int.from_bytes(bytes(parts[1:5]), "little", signed=False))
    if parts[0] == 0xFF:
        return None
    return None


def parse_functions(path: Path, class_name: str) -> list[FunctionBlock]:
    blocks: list[FunctionBlock] = []
    current_symbol: str | None = None
    current_lines: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = FUNCTION_RE.match(line)
        if match:
            if current_symbol and f"@{class_name}@@" in current_symbol:
                blocks.append(
                    FunctionBlock(
                        symbol=current_symbol,
                        name=undecorate_class_method(current_symbol, class_name),
                        lines=current_lines,
                    )
                )
            current_symbol = match.group("symbol")
            current_lines = []
            continue
        if current_symbol:
            current_lines.append(line)
    if current_symbol and f"@{class_name}@@" in current_symbol:
        blocks.append(
            FunctionBlock(
                symbol=current_symbol,
                name=undecorate_class_method(current_symbol, class_name),
                lines=current_lines,
            )
        )
    return blocks


def parse_push_context(lines: list[str], call_index: int, max_lines: int = 14) -> list[dict[str, object]]:
    pushes: list[dict[str, object]] = []
    window = lines[max(0, call_index - max_lines):call_index]
    for line in window:
        match = PUSH_RE.match(line)
        if not match:
            continue
        value = int_from_push_bytes(match.group("bytes"))
        pushes.append(
            {
                "offset": match.group("offset"),
                "operand": match.group("operand").strip(),
                "value": value,
                "value_hex": f"0x{value:X}" if isinstance(value, int) and value >= 0 else (str(value) if value is not None else ""),
            }
        )
    return pushes


def annotate_arg(name: str, value: object) -> str:
    if not isinstance(value, int):
        return ""
    if name == "bodyPosition":
        return BODY_POSITION_NAMES.get(value, "")
    if name == "headDirection":
        return HEAD_DIRECTION_NAMES.get(value, "")
    if name == "direction":
        return HEAD_DIRECTION_NAMES.get(value, "")
    if name == "speed":
        return SPEED_NAMES.get(value, "")
    if name == "priority":
        return PRIORITY_NAMES.get(value, "")
    if name == "contentObject":
        return CONTENT_OBJECT_NAMES.get(value, "")
    if name == "duration":
        return f"{value} ticks/plan units"
    return ""


def infer_args(arg_names: list[str], pushes: list[dict[str, object]]) -> list[dict[str, object]]:
    # x86 pushes right-to-left. The last pushed value is the first C++ argument.
    recent = list(reversed(pushes[-len(arg_names):])) if arg_names else []
    inferred: list[dict[str, object]] = []
    for index, name in enumerate(arg_names):
        push = recent[index] if index < len(recent) else {}
        value = push.get("value")
        inferred.append(
            {
                "name": name,
                "value": value,
                "value_hex": push.get("value_hex", ""),
                "operand": push.get("operand", ""),
                "annotation": annotate_arg(name, value),
            }
        )
    return inferred


def extract_plan_calls(blocks: list[FunctionBlock]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for block in blocks:
        for index, line in enumerate(block.lines):
            match = CALL_RE.match(line)
            if not match:
                continue
            symbol = match.group("symbol").strip()
            if "@CVillagerPlans@@" not in symbol:
                continue
            plan_name, arg_names = parse_signature(symbol)
            pushes = parse_push_context(block.lines, index)
            rows.append(
                {
                    "behavior": block.name,
                    "behavior_symbol": block.symbol,
                    "call_offset": match.group("offset"),
                    "plan": plan_name,
                    "plan_symbol": symbol,
                    "arg_names": arg_names,
                    "push_context": pushes,
                    "inferred_args": infer_args(arg_names, pushes),
                }
            )
    return rows


def collect_plan_apis(blocks: list[FunctionBlock]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for block in blocks:
        if not block.name.startswith("Plan"):
            continue
        if block.symbol in seen:
            continue
        seen.add(block.symbol)
        name, arg_names = parse_signature(block.symbol)
        rows.append({"plan": name, "symbol": block.symbol, "args": arg_names})
    rows.sort(key=lambda row: (str(row["plan"]), str(row["symbol"])))
    return rows


def parse_registered_behaviors(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        r"push\s+offset\s+(\?[^\r\n]+?@CBehavior@@[^\r\n]+?)\r?\n"
        r"\s*[0-9A-F]+:\s+(?:6A\s+[0-9A-F]{1,2}|68\s+[0-9A-F ]{11})\s+push\s+([0-9A-F]+)h?",
        re.IGNORECASE,
    )
    rows = []
    seen: set[tuple[int, str]] = set()
    for match in pattern.finditer(text):
        behavior_id = int(match.group(2), 16)
        name = undecorate_class_method(match.group(1), "CBehavior")
        key = (behavior_id, name)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"id": behavior_id, "id_hex": f"0x{behavior_id:03X}", "behavior": name})
    rows.sort(key=lambda row: (int(row["id"]), str(row["behavior"])))
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def compact_arg_text(args: list[dict[str, object]]) -> str:
    parts = []
    for arg in args:
        value = arg.get("value_hex") or arg.get("operand") or arg.get("value")
        text = f"{arg['name']}={value}"
        if arg.get("annotation"):
            text += f" ({arg['annotation']})"
        parts.append(text)
    return "; ".join(parts)


def compact_push_text(pushes: list[dict[str, object]]) -> str:
    parts = []
    for push in pushes:
        value = push.get("value_hex") or push.get("operand")
        parts.append(f"{push['offset']}:{value}")
    return "; ".join(parts)


def write_markdown(path: Path, report: dict[str, object]) -> None:
    plan_calls: list[dict[str, object]] = report["behavior_plan_calls"]  # type: ignore[assignment]
    registered: list[dict[str, object]] = report["registered_behaviors"]  # type: ignore[assignment]
    plan_apis: list[dict[str, object]] = report["plan_apis"]  # type: ignore[assignment]

    by_behavior: dict[str, list[dict[str, object]]] = {}
    for row in plan_calls:
        by_behavior.setdefault(str(row["behavior"]), []).append(row)

    lines = [
        "# VF2 Villager Action, Behavior, And Plans Dump",
        "",
        "Generated from `work/dump_behavior_disasm.txt`, `work/Behavior_symbols.txt`, `work/dump_villagerplans_disasm.txt`, and `work/VillagerPlans_symbols.txt`.",
        "",
        "This is a reverse-engineering dump, not source code. Arguments are recovered from nearby x86 `push` instructions before `CVillagerPlans::PlanTo...` calls. When values are indirect registers/locals, the raw operand is preserved and the argument is left unresolved.",
        "",
        "## Files",
        "",
        "- `behavior_plan_calls.csv`: one row per recovered `CBehavior -> CVillagerPlans` call.",
        "- `behavior_plan_calls.json`: full data with raw push context and inferred arguments.",
        "- `registered_behaviors.csv`: behavior macro IDs recovered from `CBehavior` registration code.",
        "- `villager_plan_apis.csv`: `CVillagerPlans::PlanTo...` method signatures and inferred argument names.",
        "",
        "## Summary",
        "",
        f"- Registered behavior IDs: {len(registered)}",
        f"- Plan APIs recovered: {len(plan_apis)}",
        f"- Behavior functions with plan calls: {len(by_behavior)}",
        f"- Total recovered plan calls: {len(plan_calls)}",
        "",
        "## Known Position Constants",
        "",
        "| Kind | Value | Current meaning |",
        "| --- | --- | --- |",
    ]
    for value, name in sorted(BODY_POSITION_NAMES.items()):
        lines.append(f"| bodyPosition | `{value}` / `0x{value:X}` | {name} |")
    for value, name in sorted(HEAD_DIRECTION_NAMES.items()):
        lines.append(f"| headDirection | `{value}` | {name} |")

    lines.extend(["", "## Recovered CVillager Fields", "", "| Offset | Current meaning |", "| --- | --- |"])
    for offset, note in sorted(VILLAGER_FIELD_NOTES.items()):
        lines.append(f"| `+0x{offset:X}` | {note} |")

    lines.extend(["", "## Known Content Object Constants", "", "| Value | Current meaning |", "| --- | --- |"])
    for value, name in sorted(CONTENT_OBJECT_NAMES.items()):
        lines.append(f"| `{value}` / `0x{value:X}` | {name} |")

    lines.extend(["", "## Plan API Signatures", "", "| Plan | Inferred args | Symbol |", "| --- | --- | --- |"])
    for row in plan_apis:
        args = ", ".join(row.get("args") or [])
        lines.append(f"| `{row['plan']}` | `{args}` | `{row['symbol']}` |")

    lines.extend(["", "## Registered Behavior IDs", "", "| ID | Behavior |", "| --- | --- |"])
    for row in registered:
        lines.append(f"| `{row['id_hex']}` | `{row['behavior']}` |")

    lines.extend(["", "## Behavior Plan Calls", ""])
    for behavior in sorted(by_behavior):
        calls = by_behavior[behavior]
        lines.extend([f"### `{behavior}`", "", "| Offset | Plan | Inferred args | Raw pushes before call |", "| --- | --- | --- | --- |"])
        for call in calls:
            lines.append(
                f"| `{call['call_offset']}` | `{call['plan']}` | {compact_arg_text(call['inferred_args'])} | {compact_push_text(call['push_context'])} |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    behavior_blocks = parse_functions(BEHAVIOR_DISASM, "CBehavior")
    plan_blocks = parse_functions(PLANS_DISASM, "CVillagerPlans")
    registered = parse_registered_behaviors(BEHAVIOR_DISASM)
    plan_apis = collect_plan_apis(plan_blocks)
    plan_calls = extract_plan_calls(behavior_blocks)

    flat_calls = []
    for row in plan_calls:
        flat_calls.append(
            {
                "behavior": row["behavior"],
                "call_offset": row["call_offset"],
                "plan": row["plan"],
                "inferred_args": compact_arg_text(row["inferred_args"]),
                "raw_push_context": compact_push_text(row["push_context"]),
                "plan_symbol": row["plan_symbol"],
                "behavior_symbol": row["behavior_symbol"],
            }
        )

    report = {
        "source_files": {
            "behavior_disasm": str(BEHAVIOR_DISASM),
            "behavior_symbols": str(BEHAVIOR_SYMBOLS),
            "plans_disasm": str(PLANS_DISASM),
            "plans_symbols": str(PLANS_SYMBOLS),
        },
        "registered_behaviors": registered,
        "plan_apis": plan_apis,
        "behavior_plan_calls": plan_calls,
    }

    (OUT / "behavior_plan_calls.json").write_text(json.dumps(plan_calls, indent=2), encoding="utf-8")
    (OUT / "villager_action_plan_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_csv(
        OUT / "behavior_plan_calls.csv",
        flat_calls,
        ["behavior", "call_offset", "plan", "inferred_args", "raw_push_context", "plan_symbol", "behavior_symbol"],
    )
    write_csv(OUT / "registered_behaviors.csv", registered, ["id", "id_hex", "behavior"])
    write_csv(
        OUT / "villager_plan_apis.csv",
        [
            {"plan": row["plan"], "args": ", ".join(row.get("args") or []), "symbol": row["symbol"]}
            for row in plan_apis
        ],
        ["plan", "args", "symbol"],
    )
    write_markdown(OUT / "villager_action_plan_dump.md", report)
    print(json.dumps({
        "output": str(OUT),
        "registered_behaviors": len(registered),
        "plan_apis": len(plan_apis),
        "plan_calls": len(plan_calls),
    }, indent=2))


if __name__ == "__main__":
    main()
