#!/usr/bin/env python3
"""Dump VF2 "Sending email to player" strings and trigger notes.

The source object files are local reverse-engineering inputs under
work/desktop_obj_files. The generated report belongs under outputs/.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coff_patch import CoffObject


ROOT = Path(__file__).resolve().parents[1]
SRC_OBJS = ROOT / "work" / "desktop_obj_files"
OUT = ROOT / "outputs" / "vf2-email-to-player-strings"

STRINGTABLE = "?stringTable@@3PAUStringItem@@A"
STRING_RECORD_SIZE = 0x10
ORIG_STRING_COUNT = 0xA5D


@dataclass(frozen=True)
class StringRow:
    row: int
    string_id: int
    key: str
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "string_id": self.string_id,
            "string_id_hex": f"0x{self.string_id:04X}",
            "key": self.key,
            "text": self.text,
        }


ARRAY_SPECS: dict[str, dict[str, tuple[str, int]]] = {
    "DailyEmail.obj": {
        "greetings": ("?greetings@@3PAW4StringId@@A", 5),
        "first_adoption_comments": ("?adoptMessages@@3PAW4StringId@@A", 3),
        "wedding_life_event": ("?weddingMessages@@3PAW4StringId@@A", 3),
        "home_renovation_life_event": ("?homeRenovationMessages@@3PAW4StringId@@A", 3),
        "own_promotion_life_event": ("?myPromotionMessages@@3PAW4StringId@@A", 3),
        "partner_promotion_life_event": ("?partnerPromotionMessages@@3PAW4StringId@@A", 3),
        "baby_life_event": ("?babyMessages@@3PAW4StringId@@A", 3),
        "death_life_event": ("?deathMessages@@3PAW4StringId@@A", 4),
        "endings": ("?endings@@3PAW4StringId@@A", 5),
        "remarks": ("?remarks@@3PAW4StringId@@A", 13),
        "salutations": ("?salutations@@3PAW4StringId@@A", 6),
        "lonely_status": ("?lonelyMessages@@3PAW4StringId@@A", 3),
        "sick_status": ("?sickMessages@@3PAW4StringId@@A", 3),
        "low_food_status": ("?hungryMessages@@3PAW4StringId@@A", 3),
        "money_tight_status": ("?moneyMessages@@3PAW4StringId@@A", 3),
        "depressed_status": ("?depressedMessages@@3PAW4StringId@@A", 3),
    },
    "CollegeKidEmail.obj": {
        "college_greetings": ("?greetings@@3PAW4StringId@@A", 5),
        "college_endings": ("?endings@@3PAW4StringId@@A", 5),
        "college_remarks": ("?remarks@@3PAW4StringId@@A", 5),
        "college_years_away_1_to_4": ("?collegeRemarks@@3PAW4StringId@@A", 4),
        "college_years_away_5_plus": ("?remarks2@@3PAW4StringId@@A", 5),
        "college_salutations": ("?salutations@@3PAW4StringId@@A", 5),
    },
}


DIRECT_STRING_IDS = {
    "email_header": [0x0041],
    "computer_action_labels": [0x071F, 0x0720, 0x0721],
    "save_return_comments": [0x034C, 0x034D, 0x034E, 0x034F],
    "single_status_messages": [0x0231, 0x0238, 0x0239, 0x023A, 0x023B, 0x023C, 0x023D, 0x023E],
}


TRIGGER_NOTES: dict[str, str] = {
    "email_header": "Always starts the composed email. `CDailyEmail::Show` and `CCollegeKidEmail::Show` call `theStringManager::GetStringFromNameGenderTemplate` with `eString_EmailHeader`.",
    "computer_action_labels": "`CBehavior::BrowsingWeb2` uses action/string id `0x0721` to call `CVillagerPlans::PlanToWriteToPlayer`; `0x0720` calls `PlanToReadEmail`. Both use the computer chair orientation (`Sit In Chair NW` or `Sit In Chair NE`).",
    "greetings": "`CDailyEmail::Show` chooses `GetRandom(5)` after the header.",
    "first_adoption_comments": "One-time daily-email comment. If `theGameState+0x25B05` is false, `CDailyEmail::Show` sets it true and chooses `GetRandom(3)` from this array.",
    "save_return_comments": "Return-after-load comment. If `CDailyEmail` was loaded from save (`CDailyEmail+0xB4`), the derived day counter is greater than `0x17`, and a 50/50 random branch passes, the string id is `0x034C..0x034F` based on branch and whether population is greater than 1.",
    "sick_status": "Primary status branch 1: selected villager `CVillagerState::IsSick()` is true; chooses `GetRandom(3)`.",
    "lonely_status": "Primary status branch 2: household population is exactly 1; chooses `GetRandom(3)`.",
    "low_food_status": "Primary status branch 3: `FoodStore+0x78 <= 100`; chooses `GetRandom(3)`.",
    "single_status_messages": "Single-id primary status branches. See each row note in the status section.",
    "money_tight_status": "Primary status branch 5: after `CMoney::UpdateInterest`, current money is below `300.0`; chooses `GetRandom(3)`.",
    "depressed_status": "Primary status branch 6: copied selected-villager state field at stack offset `-0x16854` is below `0x1E`; message semantics identify this as a depression/low-happiness branch. Chooses `GetRandom(3)`.",
    "wedding_life_event": "Life event id 1 in `CDailyEmail::FindLifeEventToReport` / `Show`; chooses `GetRandom(3)`.",
    "baby_life_event": "Life event id 2. Starts with `GetRandom(3)` baby messages, then may override to twins (`0x0357`) or triplets (`0x0358`) based on `theGameState+0x25AB4/0x25AB8`.",
    "own_promotion_life_event": "Life event id 3 when the promoted villager id matches the email sender; chooses `GetRandom(3)`.",
    "partner_promotion_life_event": "Life event id 3 when another villager was promoted; chooses `GetRandom(3)` and formats the other villager name/gender.",
    "death_life_event": "Life event id 4; chooses `GetRandom(4)` and formats the departed villager name.",
    "home_renovation_life_event": "Life event id 6; chooses `GetRandom(3)`. `theGameState::PopLifeEventPending` suppresses the immediate life-event popup for id 6 but still records it for daily email.",
    "remarks": "If no life event is appended, or after a life event 40 percent of the time, `CDailyEmail::Show` chooses `GetRandom(13)`.",
    "endings": "`CDailyEmail::Show` chooses `GetRandom(5)` near the end.",
    "salutations": "`CDailyEmail::Show` chooses `GetRandom(6)` and appends it with the sender name.",
    "college_greetings": "`CCollegeKidEmail::Show` chooses `GetRandom(5)` after the header.",
    "college_remarks": "`CCollegeKidEmail::Show` chooses `GetRandom(5)` after the greeting.",
    "college_years_away_1_to_4": "If `CVillager::YearsAwayFromHome() - 1 <= 3`, `CCollegeKidEmail::Show` chooses `GetRandom(4)` from this array.",
    "college_years_away_5_plus": "If `CVillager::YearsAwayFromHome() - 1 > 3`, `CCollegeKidEmail::Show` chooses `GetRandom(5)` from this array.",
    "college_endings": "`CCollegeKidEmail::Show` chooses `GetRandom(5)` near the end.",
    "college_salutations": "`CCollegeKidEmail::Show` chooses `GetRandom(5)` and appends it with the college kid's name.",
}


SINGLE_STATUS_TRIGGER_NOTES: dict[int, str] = {
    0x0231: "Food variety branch: `CVillagerState::FoodGroupsActive(false) < 2`.",
    0x0238: "Trash/kitchen smell branch: `theGameState+0x2C` flag is nonzero.",
    0x0239: "Messy-house branch: four `CollectableItem` counters at offsets `0x8AC..0x8B8` sum to more than 10.",
    0x023A: "Want-baby branch: population is 2 and additional copied-villager/family age/status gates pass.",
    0x023B: "Want-new-stuff branch: fewer than 20 upgrades in inventory item range `0xE1..0x1AC` are owned.",
    0x023C: "So-tired branch: copied selected-villager state field at stack offset `-0x16858` is below `0x14`; message semantics identify this as low energy.",
    0x023D: "Defined in the string table, but no direct reference was found in `CDailyEmail::Show` in the current desktop object.",
    0x023E: "Fallback branch after the other primary status checks fail.",
}


def read_c_string(obj: CoffObject, symidx: int) -> str:
    sym = obj.symbol_by_index[symidx]
    sec = obj.section(sym.section)
    raw = bytes(obj.buf[sec.raw_ptr + sym.value : sec.raw_ptr + sec.raw_size])
    return raw.split(b"\0", 1)[0].decode("cp1252", "replace")


def load_string_rows() -> dict[int, StringRow]:
    obj = CoffObject(SRC_OBJS / "theStringManager.obj")
    table = obj.symbol(STRINGTABLE)
    sec = obj.section(table.section)
    section_data = obj.section_data(table.section)

    relocs: dict[int, int] = {}
    reloc_pos = sec.reloc_ptr
    for _ in range(sec.nreloc):
        vaddr, symidx, _rtype = struct.unpack_from("<IIH", obj.buf, reloc_pos)
        relocs[vaddr] = symidx
        reloc_pos += 10

    rows: dict[int, StringRow] = {}
    for row_idx in range(ORIG_STRING_COUNT):
        row_off = table.value + row_idx * STRING_RECORD_SIZE
        key_sym = relocs.get(row_off + 4)
        text_sym = relocs.get(row_off + 8)
        if key_sym is None or text_sym is None:
            continue
        string_id = struct.unpack_from("<I", section_data, row_off)[0]
        rows[string_id] = StringRow(
            row=row_idx,
            string_id=string_id,
            key=read_c_string(obj, key_sym),
            text=read_c_string(obj, text_sym),
        )
    return rows


def read_id_array(obj_name: str, symbol_name: str, count: int) -> list[int]:
    obj = CoffObject(SRC_OBJS / obj_name)
    sym = obj.symbol(symbol_name)
    sec = obj.section(sym.section)
    start = sec.raw_ptr + sym.value
    return list(struct.unpack_from(f"<{count}I", obj.buf, start))


def rows_for_ids(by_id: dict[int, StringRow], ids: list[int]) -> list[dict[str, Any]]:
    rows = []
    for string_id in ids:
        row = by_id.get(string_id)
        if row is None:
            rows.append({"string_id": string_id, "string_id_hex": f"0x{string_id:04X}", "missing": True})
        else:
            rows.append(row.as_dict())
    return rows


def build_report() -> dict[str, Any]:
    by_id = load_string_rows()
    groups: dict[str, dict[str, Any]] = {}
    for obj_name, specs in ARRAY_SPECS.items():
        for group_name, (symbol_name, count) in specs.items():
            ids = read_id_array(obj_name, symbol_name, count)
            groups[group_name] = {
                "source_object": obj_name,
                "source_symbol": symbol_name,
                "count": count,
                "trigger": TRIGGER_NOTES[group_name],
                "strings": rows_for_ids(by_id, ids),
            }

    direct: dict[str, dict[str, Any]] = {}
    for group_name, ids in DIRECT_STRING_IDS.items():
        direct[group_name] = {
            "trigger": TRIGGER_NOTES[group_name],
            "strings": rows_for_ids(by_id, ids),
        }

    for entry in direct["single_status_messages"]["strings"]:
        if not entry.get("missing"):
            entry["trigger"] = SINGLE_STATUS_TRIGGER_NOTES.get(entry["string_id"], "")

    email_defined = [
        row.as_dict()
        for row in sorted(by_id.values(), key=lambda item: item.string_id)
        if row.key.startswith("eString_Email")
    ]

    return {
        "sources": {
            "string_table_object": str((SRC_OBJS / "theStringManager.obj").relative_to(ROOT)),
            "daily_email_object": str((SRC_OBJS / "DailyEmail.obj").relative_to(ROOT)),
            "college_email_object": str((SRC_OBJS / "CollegeKidEmail.obj").relative_to(ROOT)),
            "main_scene_disassembly": "work/dump_themainscene_disasm.txt",
            "behavior_disassembly": "work/dump_behavior_disasm.txt",
            "game_state_disassembly": "work/theGameState_disasm.txt",
        },
        "email_message_queue": [
            {
                "value": 1,
                "name": "Island/email event",
                "trigger": "Queued by `theMainScene` when the email/island cooldown expires, population is nonzero, a random living villager exists and is idle, message type 1 is not already queued, and `GetRandom(100) < 0x42` (66%). When popped it calls `CIslandEvents::FireEmailEvent`.",
            },
            {
                "value": 2,
                "name": "Marriage proposal email",
                "trigger": "Queued by `theMainScene` when the marriage proposal timer expires, adult population is 1, the current family can marry, and proposal-family gates pass. When popped it changes to scene 7.",
            },
            {
                "value": 3,
                "name": "College kid email",
                "trigger": "`theGameState::MaybeSendCollegeKidEmail` queues this when `theGameState+0x25AF0` has expired and `CVillagerManager::GetRandomCollegeKid()` returns a villager. The timer is reset by `UpdateCollegeKidEmailTimer()` to now plus `(GetRandom(0x10)+0x14) * 0xE10` seconds.",
            },
        ],
        "computer_action": {
            "behavior_function": "CBehavior::BrowsingWeb2",
            "read_email_action_id": "0x0720",
            "send_email_action_id": "0x0721",
            "read_plan": "CVillagerPlans::PlanToReadEmail",
            "send_plan": "CVillagerPlans::PlanToWriteToPlayer",
            "action_plan_types": {
                "read_email": "0x40",
                "write_to_player": "0x41",
            },
            "notes": "The computer behavior picks NW or NE chair animation from the computer orientation. When the SStringData id is `0x0721`, it schedules the write-to-player plan and shows `Sending email to player` in the action label.",
        },
        "direct_strings": direct,
        "daily_email_groups": {k: v for k, v in groups.items() if not k.startswith("college_")},
        "college_email_groups": {k: v for k, v in groups.items() if k.startswith("college_")},
        "defined_eString_Email_rows": email_defined,
    }


def quote_text(text: str) -> str:
    return text.replace("\n", "\\n")


def markdown_table(rows: list[dict[str, Any]], include_trigger: bool = False) -> list[str]:
    header = "| ID | Key | Text |"
    sep = "| --- | --- | --- |"
    if include_trigger:
        header = "| ID | Key | Text | Trigger note |"
        sep = "| --- | --- | --- | --- |"
    lines = [header, sep]
    for row in rows:
        if row.get("missing"):
            cells = [row["string_id_hex"], "(missing)", ""]
        else:
            cells = [row["string_id_hex"], f"`{row['key']}`", quote_text(row["text"])]
        if include_trigger:
            cells.append(row.get("trigger", ""))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines: list[str] = [
        "# VF2 Sending Email To Player String Dump",
        "",
        "Generated from the workspace-local desktop object files and disassembly.",
        "",
        "## Sources",
        "",
    ]
    for label, source in report["sources"].items():
        lines.append(f"- {label}: `{source}`")

    lines.extend(
        [
            "",
            "## Computer Action",
            "",
            f"- Behavior function: `{report['computer_action']['behavior_function']}`.",
            f"- Read email action id: `{report['computer_action']['read_email_action_id']}` -> `{report['computer_action']['read_plan']}`.",
            f"- Send email action id: `{report['computer_action']['send_email_action_id']}` -> `{report['computer_action']['send_plan']}`.",
            f"- Action plan types: read `{report['computer_action']['action_plan_types']['read_email']}`, write `{report['computer_action']['action_plan_types']['write_to_player']}`.",
            f"- Notes: {report['computer_action']['notes']}",
            "",
            "### Direct Computer Strings",
            "",
        ]
    )
    lines += markdown_table(report["direct_strings"]["computer_action_labels"]["strings"])

    lines.extend(["", "## Email Message Queue", ""])
    for item in report["email_message_queue"]:
        lines.append(f"- `{item['value']}` {item['name']}: {item['trigger']}")

    lines.extend(["", "## Daily Email Composition", ""])
    lines.append("- `CDailyEmail::Show` starts with the header, then one greeting, optional one-time/return comments, one primary status comment, optional life-event text, optional remark, ending, and salutation.")
    lines.append("- Life event records are stored in five `0x24`-byte slots inside `CDailyEmail`; `FindLifeEventToReport` favors event id 2 when present, then id 1, then the oldest other event. Entries older than `0x8CA0` seconds are cleared.")

    lines.extend(["", "### Header", ""])
    lines.append(report["direct_strings"]["email_header"]["trigger"])
    lines += markdown_table(report["direct_strings"]["email_header"]["strings"])

    for group_name in [
        "greetings",
        "first_adoption_comments",
    ]:
        group = report["daily_email_groups"][group_name]
        lines.extend(["", f"### {group_name.replace('_', ' ').title()}", "", group["trigger"], ""])
        lines += markdown_table(group["strings"])

    lines.extend(["", "### Save Return Comments", "", report["direct_strings"]["save_return_comments"]["trigger"], ""])
    lines += markdown_table(report["direct_strings"]["save_return_comments"]["strings"])

    lines.extend(["", "### Primary Status Comments", ""])
    for group_name in ["sick_status", "lonely_status", "low_food_status", "money_tight_status", "depressed_status"]:
        group = report["daily_email_groups"][group_name]
        lines.extend(["", f"#### {group_name.replace('_', ' ').title()}", "", group["trigger"], ""])
        lines += markdown_table(group["strings"])

    lines.extend(["", "#### Single-Id Status Branches", ""])
    lines += markdown_table(report["direct_strings"]["single_status_messages"]["strings"], include_trigger=True)

    lines.extend(["", "### Life Event Comments", ""])
    for group_name in [
        "wedding_life_event",
        "baby_life_event",
        "own_promotion_life_event",
        "partner_promotion_life_event",
        "death_life_event",
        "home_renovation_life_event",
    ]:
        group = report["daily_email_groups"][group_name]
        lines.extend(["", f"#### {group_name.replace('_', ' ').title()}", "", group["trigger"], ""])
        lines += markdown_table(group["strings"])

    for group_name in ["remarks", "endings", "salutations"]:
        group = report["daily_email_groups"][group_name]
        lines.extend(["", f"### {group_name.replace('_', ' ').title()}", "", group["trigger"], ""])
        lines += markdown_table(group["strings"])

    lines.extend(["", "## College Kid Email Composition", ""])
    lines.append("Triggered by email message type 3 and composed by `CCollegeKidEmail::Show`, not by the computer `Sending email to player` action.")
    for group_name in [
        "college_greetings",
        "college_remarks",
        "college_years_away_1_to_4",
        "college_years_away_5_plus",
        "college_endings",
        "college_salutations",
    ]:
        group = report["college_email_groups"][group_name]
        lines.extend(["", f"### {group_name.replace('_', ' ').title()}", "", group["trigger"], ""])
        lines += markdown_table(group["strings"])

    lines.extend(["", "## Defined `eString_Email*` Rows", ""])
    lines.append("These are all string-table rows whose key begins with `eString_Email`. `eString_EmailRepairHouse` is present but was not observed as a direct branch in the current `CDailyEmail::Show` object.")
    lines += markdown_table(report["defined_eString_Email_rows"])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "sending-email-to-player-strings.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_markdown(report, OUT / "sending-email-to-player-strings.md")
    print(f"Wrote {OUT / 'sending-email-to-player-strings.md'}")
    print(f"Wrote {OUT / 'sending-email-to-player-strings.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
