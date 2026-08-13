from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


HOLIDAY_FOOTER_ROWS = (
    (0xE92, "common", "eSayCommonOrnaments", " of 4 common ornaments found."),
    (0xE93, "uncommon", "eSayUncommonOrnaments", " of 4 uncommon ornaments found."),
    (0xE94, "rare", "eSayRareOrnaments", " of 4 rare ornaments found."),
)
B152_HOLIDAY_BACKGROUND_SIZE = (1024, 768)


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    require(header[:8] == b"\x89PNG\r\n\x1a\n", f"{path}: not a PNG")
    require(header[12:16] == b"IHDR", f"{path}: missing PNG IHDR")
    return struct.unpack(">II", header[16:24])


def validate_b152_holiday_ornament_art(
    build_dir: Path,
    manifest: dict,
    ornaments_enabled: bool,
) -> dict | None:
    if not ornaments_enabled:
        return None
    background = build_dir / "Images" / "collection-ornaments_background.png"
    require(background.is_file(), f"{background}: B152 Holiday background is missing")
    actual_size = png_size(background)
    require(
        actual_size == B152_HOLIDAY_BACKGROUND_SIZE,
        f"{background}: B152 Holiday background is {actual_size}, "
        f"expected {B152_HOLIDAY_BACKGROUND_SIZE} from the supplied full page",
    )
    art = manifest.get("holiday_ornament_collection_art", {})
    background_record = art.get("background", {})
    require(
        background_record.get("dimensions")
        == list(B152_HOLIDAY_BACKGROUND_SIZE),
        f"{background}: manifest dimensions do not match the B152 runtime asset",
    )
    digest = hashlib.sha256(background.read_bytes()).hexdigest()
    require(
        str(background_record.get("sha256", "")).lower() == digest,
        f"{background}: manifest hash does not match the B152 runtime asset",
    )
    return {
        "path": str(background),
        "sha256": digest.upper(),
        "dimensions": list(actual_size),
    }


class PEImage:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        require(self.data[pe : pe + 4] == b"PE\0\0", f"{path}: invalid PE signature")
        section_count = struct.unpack_from("<H", self.data, pe + 6)[0]
        optional_size = struct.unpack_from("<H", self.data, pe + 20)[0]
        section_table = pe + 24 + optional_size
        self.sections = []
        for index in range(section_count):
            off = section_table + index * 40
            name = self.data[off : off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from(
                "<IIII", self.data, off + 8
            )
            characteristics = struct.unpack_from("<I", self.data, off + 36)[0]
            self.sections.append(
                {
                    "name": name,
                    "virtual_size": virtual_size,
                    "rva": rva,
                    "raw_size": raw_size,
                    "raw_offset": raw_offset,
                    "characteristics": characteristics,
                }
            )

    def rva_to_offset(self, rva: int) -> int | None:
        for section in self.sections:
            span = max(section["virtual_size"], section["raw_size"])
            if section["rva"] <= rva < section["rva"] + span:
                return section["raw_offset"] + rva - section["rva"]
        return None

    def offset_to_rva(self, offset: int) -> int | None:
        for section in self.sections:
            if section["raw_offset"] <= offset < section["raw_offset"] + section["raw_size"]:
                return section["rva"] + offset - section["raw_offset"]
        return None


def validate_executable(path: Path) -> dict:
    image = PEImage(path)
    manifest_path = path.parent / "patch-manifest.json"
    require(manifest_path.is_file(), f"{path}: sibling patch-manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    custom = manifest.get("CustomAchievements", {})
    require(custom.get("physical_row_count") == 0xA8, f"{path}: manifest row count is not 168")
    award_contract = manifest.get("custom_achievement_award_hook_contract", {})
    require(
        award_contract.get("status") == "validated",
        f"{path}: B2 award-hook object contract is not validated",
    )

    ornaments = bool(
        manifest.get("native_array_contract", {})
        .get("holiday_ornaments", {})
        .get("enabled")
    )
    holiday_art = validate_b152_holiday_ornament_art(
        path.parent,
        manifest,
        ornaments,
    )
    behavior = bool(manifest.get("BehaviorPatchesGate", {}).get("enabled"))
    base_count = 0x5F + 6 + (1 if ornaments else 0) + (7 if behavior else 0)
    require(
        custom.get("visible_counts")
        == {
            "holiday_furniture_flag_0": base_count,
            "holiday_furniture_flag_1": base_count + 19,
        },
        f"{path}: visible-count manifest does not match its feature gates",
    )

    stock_order = list(range(0x4D)) + [0x5D, 0x5E] + list(range(0x4D, 0x5D))
    require(len(stock_order) == 0x5F, f"{path}: internal stock order model drifted")
    expected_order = stock_order[:]
    if ornaments:
        expected_order.insert(expected_order.index(0x5E) + 1, 0x5F)
    expected_order.extend(range(0x60, 0x66))
    if behavior:
        expected_order.extend(range(0x66, 0x6D))
    expected_order.extend(range(0x6D, 0x80))
    expected_order_bytes = struct.pack(
        "<" + "I" * len(expected_order),
        *expected_order,
    )
    order_offsets = []
    cursor = 0
    while True:
        offset = image.data.find(expected_order_bytes, cursor)
        if offset < 0:
            break
        order_offsets.append(offset)
        cursor = offset + 1
    require(
        len(order_offsets) == 1,
        f"{path}: expected one exact linked achievementOrder, found {len(order_offsets)}",
    )
    order_contract = custom.get("ornamentologist_order", {})
    require(
        order_contract.get("visible") is ornaments,
        f"{path}: Ornamentologist visibility contract drifted",
    )
    if ornaments:
        bottlologist_index = expected_order.index(0x5E)
        require(
            expected_order[bottlologist_index + 1] == 0x5F,
            f"{path}: Ornamentologist does not immediately follow Bottlologist",
        )
        require(
            order_contract
            == {
                "visible": True,
                "bottlologist_id": "0x5e",
                "ornamentologist_id": "0x5f",
                "bottlologist_index": bottlologist_index,
                "ornamentologist_index": bottlologist_index + 1,
                "adjacent": True,
            },
            f"{path}: Ornamentologist adjacency manifest drifted",
        )
    else:
        require(0x5F not in expected_order, f"{path}: hidden Ornamentologist leaked")
        require(
            order_contract.get("ornamentologist_index") is None
            and order_contract.get("adjacent") is None,
            f"{path}: hidden Ornamentologist adjacency is not null",
        )

    tooltip_cave_offset = None
    if ornaments:
        scene = manifest.get("CollectionSceneHolidayOrnaments", {})
        require(
            scene.get("tooltip_rarity_label_ids")
            == [hex(row[0]) for row in HOLIDAY_FOOTER_ROWS],
            f"{path}: Holiday footer string ID manifest drifted",
        )
        string_rows = manifest.get("theStringManager", {}).get("strings", [])
        title_rows = [
            row for row in string_rows
            if row.get("source") == "holiday ornament collection page"
        ]
        require(
            len(title_rows) == 1 and title_rows[0].get("text") == "Ornaments",
            f"{path}: Collections page title is not the short Ornaments label",
        )
        footer_rows = [
            row for row in string_rows
            if row.get("source") == "holiday ornament collection footer"
        ]
        require(
            [
                (
                    int(row["pc_string_id"], 16),
                    row.get("rarity"),
                    row.get("key"),
                    row.get("text"),
                )
                for row in footer_rows
            ]
            == list(HOLIDAY_FOOTER_ROWS),
            f"{path}: dedicated Holiday footer rows drifted",
        )
        for _string_id, _rarity, _key, text in HOLIDAY_FOOTER_ROWS:
            require(
                text.encode("ascii") + b"\0" in image.data,
                f"{path}: linked Holiday footer text is missing: {text!r}",
            )
        require(b"Ornaments\0" in image.data, f"{path}: linked short title is missing")
    goal_sections = [section for section in image.sections if section["name"] == ".vf2goal"]
    require(len(goal_sections) == 1, f"{path}: expected one .vf2goal section")
    goal = goal_sections[0]
    require(goal["virtual_size"] == 1, f"{path}: .vf2goal virtual size is not one byte")
    require(goal["characteristics"] & 0x80000000, f"{path}: .vf2goal is not writable")
    require(image.data[goal["raw_offset"]] == 0, f"{path}: .vf2goal default byte is not 00")

    caves = []
    executable_sections = [
        section for section in image.sections if section["characteristics"] & 0x20000000
    ]

    def executable_prefix_matches(prefix: bytes):
        matches = []
        for section in executable_sections:
            start = section["raw_offset"]
            raw = image.data[start : start + section["raw_size"]]
            cursor = 0
            while True:
                match = raw.find(prefix, cursor)
                if match < 0:
                    break
                matches.append(start + match)
                cursor = match + 1
        return matches

    if ornaments:
        tooltip_prefix = bytes.fromhex(
            "83 F8 0F 72 10 83 F8 12 73 0B 8D 98 33 0E 00 00 E9"
        )
        tooltip_matches = executable_prefix_matches(tooltip_prefix)
        require(
            len(tooltip_matches) == 1,
            f"{path}: expected one Holiday tooltip footer route, found {len(tooltip_matches)}",
        )
        tooltip_cave_offset = tooltip_matches[0]
        first_jump_rva = image.offset_to_rva(tooltip_cave_offset + 16)
        second_jump_rva = image.offset_to_rva(tooltip_cave_offset + 28)
        require(
            first_jump_rva is not None and second_jump_rva is not None,
            f"{path}: Holiday tooltip cave jumps are unmapped",
        )
        first_return_rva = (
            first_jump_rva
            + 5
            + struct.unpack_from("<i", image.data, tooltip_cave_offset + 17)[0]
        )
        second_return_rva = (
            second_jump_rva
            + 5
            + struct.unpack_from("<i", image.data, tooltip_cave_offset + 29)[0]
        )
        require(
            first_return_rva == second_return_rva
            and image.rva_to_offset(first_return_rva) is not None,
            f"{path}: Holiday tooltip cave return routes diverged",
        )

    purchase_wrappers = [
        offset
        for offset in executable_prefix_matches(b"\x53\xFF\x74\x24\x08\xE8")
        if image.data[offset + 10 : offset + 21]
        == b"\x8A\xD8\x84\xDB\x74\x0C\xFF\x74\x24\x08\xE8"
        and image.data[offset + 25 : offset + 34]
        == b"\x83\xC4\x04\x8A\xC3\x5B\xC2\x04\x00"
    ]
    require(
        len(purchase_wrappers) == 1,
        f"{path}: expected one compiled AddToStorageAndAward wrapper, found {len(purchase_wrappers)}",
    )
    purchase_wrapper_offset = purchase_wrappers[0]
    purchase_wrapper_rva = image.offset_to_rva(purchase_wrapper_offset)
    require(purchase_wrapper_rva is not None, f"{path}: purchase wrapper is unmapped")
    native_storage_rva = purchase_wrapper_rva + 10 + struct.unpack_from(
        "<i", image.data, purchase_wrapper_offset + 6
    )[0]
    dispatch_rva = purchase_wrapper_rva + 25 + struct.unpack_from(
        "<i", image.data, purchase_wrapper_offset + 21
    )[0]
    require(
        image.rva_to_offset(native_storage_rva) is not None
        and image.rva_to_offset(dispatch_rva) is not None
        and native_storage_rva != dispatch_rva,
        f"{path}: purchase wrapper native/dispatch call targets are invalid",
    )

    purchase_sites = [
        offset
        for offset in executable_prefix_matches(
            b"\x3D\x28\x03\x00\x00\x7D\x39\x50\xB9"
        )
        if image.data[offset + 13 : offset + 14] == b"\xE8"
        and image.data[offset + 18 : offset + 19] == b"\xE8"
        and image.data[offset + 23 : offset + 26] == b"\x8B\xC8\xE8"
    ]
    matching_purchase_sites = []
    for site in purchase_sites:
        site_rva = image.offset_to_rva(site)
        if site_rva is None:
            continue
        wrapper_target = site_rva + 18 + struct.unpack_from("<i", image.data, site + 14)[0]
        if wrapper_target == purchase_wrapper_rva:
            matching_purchase_sites.append(site)
    require(
        len(matching_purchase_sites) == 1,
        f"{path}: expected one HandlePurchaseItem call to AddToStorageAndAward",
    )

    praise_wrapper_offset = None
    scold_wrapper_offset = None
    if behavior:
        praise_entries = [
            offset
            for offset in executable_prefix_matches(
                b"\x56\x8B\x74\x24\x08\x33\xC9\x89\x35"
            )
            if image.data[offset + 13 : offset + 25]
            == b"\x8D\x86\xCF\xBB\x01\x00\x8D\x96\xA8\xBB\x01\x00"
        ]
        require(
            len(praise_entries) == 1,
            f"{path}: expected one compiled praise capture/award wrapper",
        )
        praise_wrapper_offset = praise_entries[0]
        praise_wrapper_rva = image.offset_to_rva(praise_wrapper_offset)
        require(praise_wrapper_rva is not None, f"{path}: praise wrapper is unmapped")
        praise_body = image.data[praise_wrapper_offset : praise_wrapper_offset + 0x180]
        for goal_id in range(0x66, 0x6C):
            require(
                b"\x6A" + bytes([goal_id]) in praise_body,
                f"{path}: praise wrapper is missing SetComplete ID {goal_id:#x}",
            )
        for label in (
            b"Watching cat videos\0",
            b"Posting on VideoTube\0",
            b"Playing Virtual Families\0",
            b"Playing Virtual Villagers\0",
            b"Posting memes online\0",
            b"Praising pet\0",
        ):
            require(label in image.data, f"{path}: linked praise label {label!r} is missing")

        scold_entries = [
            offset
            for offset in executable_prefix_matches(b"\x83\xEC\x2C\xA1")
            if image.data[offset + 8 : offset + 19]
            == b"\x33\xC4\x89\x44\x24\x28\x56\x8B\x74\x24\x34"
            and image.data[offset + 19 : offset + 29]
            == b"\x8D\x54\x24\x04\x8D\x8E\xA8\xBB\x01\x00"
        ]
        require(
            len(scold_entries) == 1,
            f"{path}: expected one compiled scold award/ForgetPlans wrapper",
        )
        scold_wrapper_offset = scold_entries[0]
        scold_wrapper_rva = image.offset_to_rva(scold_wrapper_offset)
        require(scold_wrapper_rva is not None, f"{path}: scold wrapper is unmapped")
        scold_body = image.data[scold_wrapper_offset : scold_wrapper_offset + 0xB0]
        require(b"Scolding pet\0" in image.data, f"{path}: exact scold label is missing")
        scold_goal_call = scold_body.find(b"\x6A\x6C\xB9")
        require(
            scold_goal_call >= 0
            and scold_goal_call + 7 < len(scold_body)
            and scold_body[scold_goal_call + 7] == 0xE8,
            f"{path}: scold wrapper is missing SetComplete(0x6C)",
        )
        require(
            scold_body.endswith(b"\x83\xC4\x2C\xC2\x08\x00")
            or b"\x83\xC4\x2C\xC2\x08\x00" in scold_body,
            f"{path}: scold wrapper does not preserve stdcall @8 cleanup",
        )

        forget_call_sites = executable_prefix_matches(
            b"\x6A\x00\x53\x8B\xCB\xE8"
        )
        calls_by_target = {praise_wrapper_rva: [], scold_wrapper_rva: []}
        for site in forget_call_sites:
            site_rva = image.offset_to_rva(site)
            if site_rva is None:
                continue
            target = site_rva + 10 + struct.unpack_from("<i", image.data, site + 6)[0]
            if target in calls_by_target:
                calls_by_target[target].append(site)
        require(
            len(calls_by_target[praise_wrapper_rva]) == 1,
            f"{path}: InvokeReward does not call the praise wrapper exactly once",
        )
        require(
            len(calls_by_target[scold_wrapper_rva]) == 1,
            f"{path}: InvokeScolding does not call the scold wrapper exactly once",
        )
    for section in executable_sections:
        start = section["raw_offset"]
        end = start + section["raw_size"] - 16
        for off in range(start, max(start, end)):
            if (
                image.data[off : off + 3] == b"\x51\x52\xE8"
                and image.data[off + 7 : off + 12] == b"\x5A\x59\x3B\xF0\xE9"
            ):
                caves.append(off)
    require(len(caves) == 1, f"{path}: expected one register-preserving order cave, found {len(caves)}")
    cave_offset = caves[0]
    cave_rva = image.offset_to_rva(cave_offset)
    require(cave_rva is not None, f"{path}: cave is outside mapped sections")

    call_target_rva = cave_rva + 7 + struct.unpack_from("<i", image.data, cave_offset + 3)[0]
    call_target_offset = image.rva_to_offset(call_target_rva)
    require(call_target_offset is not None, f"{path}: order helper call target is unmapped")
    return_target_rva = cave_rva + 16 + struct.unpack_from("<i", image.data, cave_offset + 12)[0]
    return_target_offset = image.rva_to_offset(return_target_rva)
    require(return_target_offset is not None, f"{path}: cave return target is unmapped")
    require(
        image.data[return_target_offset : return_target_offset + 5] == b"\x7C\xD3\x8B\x4D\xFC",
        f"{path}: cave does not return to DrawScene +0xFB",
    )

    source_jumps = []
    for section in executable_sections:
        start = section["raw_offset"]
        end = start + section["raw_size"] - 7
        for off in range(start, max(start, end)):
            if image.data[off] != 0xE9:
                continue
            source_rva = image.offset_to_rva(off)
            if source_rva is None:
                continue
            target = source_rva + 5 + struct.unpack_from("<i", image.data, off + 1)[0]
            if target == cave_rva and image.data[off + 5 : off + 8] == b"\x90\x7C\xD3":
                source_jumps.append(off)
    require(len(source_jumps) == 1, f"{path}: expected one DrawScene jump to the order cave")

    return {
        "path": str(path),
        "sha256": hashlib.sha256(image.data).hexdigest().upper(),
        "holiday_ornaments": ornaments,
        "holiday_ornament_art": holiday_art,
        "behavior_patches": behavior,
        "visible_counts": custom["visible_counts"],
        "achievement_order_file_offset": hex(order_offsets[0]),
        "tooltip_cave_file_offset": (
            hex(tooltip_cave_offset) if tooltip_cave_offset is not None else None
        ),
        "flag_file_offset": hex(goal["raw_offset"]),
        "flag_rva": hex(goal["rva"]),
        "cave_file_offset": hex(cave_offset),
        "cave_rva": hex(cave_rva),
        "purchase_wrapper_file_offset": hex(purchase_wrapper_offset),
        "purchase_wrapper_rva": hex(purchase_wrapper_rva),
        "purchase_hook_file_offset": hex(matching_purchase_sites[0] + 13),
        "praise_wrapper_file_offset": (
            hex(praise_wrapper_offset) if praise_wrapper_offset is not None else None
        ),
        "scold_wrapper_file_offset": (
            hex(scold_wrapper_offset) if scold_wrapper_offset is not None else None
        ),
        "status": "validated",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate linked B152 custom-achievement diagnostic executables."
    )
    parser.add_argument("executables", nargs="+", type=Path)
    args = parser.parse_args()
    results = [validate_executable(path.resolve()) for path in args.executables]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
