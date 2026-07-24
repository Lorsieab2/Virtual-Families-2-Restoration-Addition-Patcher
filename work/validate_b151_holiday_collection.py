from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
from typing import Any, Iterable


WORK = Path(__file__).resolve().parent
ROOT = WORK.parent
DEFAULT_OUTPUTS = ROOT / "outputs"
DEFAULT_EXE_NAME = "Virtual Families 2 - Additive Mobile Furniture Pack.exe"
BUILD_PREFIX = "VF2-Mobile-Furniture-With-Island-Events-B151-"

HOLIDAY_START = 0x9E
HOLIDAY_END = 0xA9
HOLIDAY_IDS = tuple(range(HOLIDAY_START, HOLIDAY_END + 1))
STOCK_COLLECTION_IDS = tuple(range(0x4F, 0x73)) + tuple(range(0x86, 0x9E))
PAGE_STARTS = (0x4F, 0x5B, 0x67, 0x86, 0x92, HOLIDAY_START)
COLLECTION_TABLE_60 = struct.pack("<60I", *STOCK_COLLECTION_IDS)
COLLECTION_TABLE_72 = struct.pack("<72I", *(STOCK_COLLECTION_IDS + HOLIDAY_IDS))
PAGE_START_TABLE = struct.pack("<6I", *PAGE_STARTS)
TOOLTIP_LABELS = (0x751, 0x752, 0x753)
RARITY_RANGES = {
    "?IsCommonCollectable@CCollectableItem@@QBE?B_NW4ECarrying@@@Z": (0x9E, 0xA1),
    "?IsUncommonCollectable@CCollectableItem@@QBE?B_NW4ECarrying@@@Z": (0xA2, 0xA5),
    "?IsRareCollectable@CCollectableItem@@QBE?B_NW4ECarrying@@@Z": (0xA6, 0xA9),
}
RARITY_PATTERNS = tuple(
    b"\x3D"
    + struct.pack("<I", low)
    + b"\x7C\x0D\x3D"
    + struct.pack("<I", high)
    + b"\x7F\x06\xB0\x01\x5D\xC2\x04\x00"
    for low, high in RARITY_RANGES.values()
)
COLLECTOR_OFFER_ARGUMENTS = (
    (HOLIDAY_START, 0, 0, 1),
    (HOLIDAY_START, 0, 1, 0),
    (HOLIDAY_START, 1, 0, 0),
)
MOBILE_1716_SPAWN_RECTS = (
    (0x112, 0x0C4, 0x2FA, 0x1BD),
    (0x098, 0x178, 0x19D, 0x26F),
    (0x08D, 0x568, 0x137, 0x750),
)

FIND_PREFIX = bytes.fromhex(
    "55 8B EC 83 EC 14 53 56 33 D2 C7 45 FC 80 96 98 00 "
    "8D 71 CC 89 55 F8 57 8B 7D 0C 33 DB 89 75 F4"
)
FIND_STOCK_BYTES = bytes.fromhex("83 FF 7D 75 39 83 C0 83 83 F8 03 77 31")
WAS_SPAWNED_PREFIX = bytes.fromhex(
    "55 8B EC 8D 81 50 03 00 00 33 D2 8B 4D 08 66 90 80 78 FC 00"
)
WAS_SPAWNED_STOCK_BYTES = bytes.fromhex("74 04 39 08 74 0F 42")
HANDLE_MOUSE_PREFIX = bytes.fromhex("55 8B EC 81 EC 60 01 00 00")
DRAW_SCENE_PREFIX = bytes.fromhex("55 8B EC 81 EC 24 01 00 00")
DROP_PREFIX = bytes.fromhex("55 8B EC 83 EC 08 56 57 8B 7D 0C 8B F1 83 FF 4F")
COLLECTION_COUNT_PREFIX = bytes.fromhex("55 8B EC 51 8B 55 08 53 56 8B D9")
ADD_PREFIX = bytes.fromhex(
    "55 8B EC 83 EC 14 53 8B D9 8A 4D 14 57 33 FF 8D 83 4C 03 00 00"
)
RESET_PREFIX = bytes.fromhex(
    "55 8B EC 83 EC 08 53 8B D9 B9 1E 00 00 00 56 57"
)
COLLECTOR_CAN_FIRE_PREFIX = bytes.fromhex("55 8B EC 51 56 57 8D 45 FC 8B F9")
COLLECTOR_IMPACT_BODY = bytes.fromhex("66 0F 6E 41 0C 0F 5B C0 6A 01 51")

COUNT_LOOKUP = bytes.fromhex("8B 84 81 A4 04 00 00")
RESET_COLLECTION = bytes.fromhex(
    "57 8D B9 E0 05 00 00 33 C0 B9 AF 00 00 00 F3 AB 5F C3"
)
SAVE_COLLECTION_SPAN = bytes.fromhex(
    "8D 8B 48 03 00 00 BE AF 00 00 00 8D 97 E0 05 00 00"
)
LOAD_COLLECTION_SPAN = bytes.fromhex(
    "8D 8F E0 05 00 00 BE AF 00 00 00 C7 45 08 01 00 00 00 "
    "8D 93 48 03 00 00"
)
LUCKY_ROCK_THRESHOLDS = bytes.fromhex(
    "84 D2 C7 45 14 11 00 00 00 B8 22 00 00 00 "
    "0F 44 45 14 3B F0"
)
LUCKY_ROCK_RARITY_OFFSETS = bytes.fromhex("83 C7 04 EB 03 83 C7 08")


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def as_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{label}: boolean is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValidationError(f"{label}: invalid integer {value!r}") from exc
    raise ValidationError(f"{label}: expected integer, got {type(value).__name__}")


def int_list(values: Iterable[Any], label: str) -> list[int]:
    return [as_int(value, f"{label}[{index}]") for index, value in enumerate(values)]


def nested(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise ValidationError(f"manifest missing {'.'.join(keys)}")
        current = current[key]
    return current


def flattened_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(
            f"{str(key).lower()} {flattened_text(item)}"
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return " ".join(flattened_text(item) for item in value)
    return str(value).lower()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    require(header[:8] == b"\x89PNG\r\n\x1a\n", f"{path}: not a PNG")
    require(header[12:16] == b"IHDR", f"{path}: missing PNG IHDR")
    return struct.unpack(">II", header[16:24])


@dataclass(frozen=True)
class SourceContract:
    spawn_rects: tuple[tuple[int, int, int, int], ...]
    mobile_slot_positions: tuple[tuple[int, int], ...]
    slot_positions: tuple[tuple[int, int], ...]
    runtime_files: tuple[str, ...]
    image_base: int
    title_string: int
    achievement_title_string: int
    achievement_description_string: int


def load_source_contract() -> SourceContract:
    module_path = WORK / "patch_mobile_furniture_pack.py"
    spec = importlib.util.spec_from_file_location("_vf2_b151_contract_source", module_path)
    require(spec is not None and spec.loader is not None, f"cannot import {module_path}")
    module = importlib.util.module_from_spec(spec)
    work_text = str(WORK)
    if work_text not in sys.path:
        sys.path.insert(0, work_text)
    spec.loader.exec_module(module)
    rects = tuple(tuple(int(value) for value in rect) for _symbol, rect in module.HOLIDAY_ORNAMENT_SPAWN_RECTS)
    positions = tuple(tuple(int(value) for value in row) for row in module.HOLIDAY_ORNAMENT_COLLECTION_SLOT_POSITIONS)
    mobile_positions = tuple(
        tuple(int(value) for value in row)
        for row in module.HOLIDAY_ORNAMENT_MOBILE_SLOT_POSITIONS
    )
    runtime_files = tuple(row[0] for row in module.HOLIDAY_ORNAMENT_COLLECTION_FILES)
    body_count = module.holiday_body_descriptor_count() if module.ENABLE_HOLIDAY_BODY_TYPES else 0
    return SourceContract(
        spawn_rects=rects,
        mobile_slot_positions=mobile_positions,
        slot_positions=positions,
        runtime_files=runtime_files,
        image_base=module.holiday_ornament_collection_image_base(body_count),
        title_string=module.holiday_ornament_collection_title_string_id(),
        achievement_title_string=module.holiday_ornament_achievement_title_string_id(),
        achievement_description_string=module.holiday_ornament_achievement_desc_string_id(),
    )


@dataclass
class PESection:
    name: str
    rva: int
    virtual_size: int
    raw_ptr: int
    raw_size: int
    characteristics: int


class PEImage:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        require(len(self.data) >= 0x40, f"{path}: file is too small")
        pe_off = struct.unpack_from("<I", self.data, 0x3C)[0]
        require(self.data[pe_off : pe_off + 4] == b"PE\0\0", f"{path}: not a PE image")
        coff = pe_off + 4
        section_count = struct.unpack_from("<H", self.data, coff + 2)[0]
        optional_size = struct.unpack_from("<H", self.data, coff + 16)[0]
        section_off = coff + 20 + optional_size
        self.sections: list[PESection] = []
        for index in range(section_count):
            off = section_off + index * 40
            name = self.data[off : off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size, rva, raw_size, raw_ptr = struct.unpack_from("<IIII", self.data, off + 8)
            characteristics = struct.unpack_from("<I", self.data, off + 36)[0]
            self.sections.append(
                PESection(name, rva, virtual_size, raw_ptr, raw_size, characteristics)
            )

    def executable_sections(self) -> list[PESection]:
        return [section for section in self.sections if section.characteristics & 0x20000000]

    def file_to_rva(self, file_off: int) -> int:
        for section in self.sections:
            if section.raw_ptr <= file_off < section.raw_ptr + section.raw_size:
                return section.rva + file_off - section.raw_ptr
        raise ValidationError(f"{self.path}: file offset {file_off:#x} is outside sections")

    def rva_to_file(self, rva: int) -> int:
        for section in self.sections:
            span = max(section.virtual_size, section.raw_size)
            if section.rva <= rva < section.rva + span:
                return section.raw_ptr + rva - section.rva
        raise ValidationError(f"{self.path}: RVA {rva:#x} is outside sections")

    def find_all(self, pattern: bytes, executable_only: bool = False) -> list[int]:
        sections = self.executable_sections() if executable_only else self.sections
        matches: list[int] = []
        for section in sections:
            start = section.raw_ptr
            end = start + section.raw_size
            position = start
            while True:
                position = self.data.find(pattern, position, end)
                if position < 0:
                    break
                matches.append(position)
                position += 1
        return matches

    def find_unique(self, pattern: bytes, label: str, executable_only: bool = True) -> int:
        matches = self.find_all(pattern, executable_only)
        require(len(matches) == 1, f"{self.path}: expected one {label}, found {len(matches)}")
        return matches[0]

    def rel32_target_rva(self, opcode_off: int, instruction_size: int = 5) -> int:
        displacement = struct.unpack_from("<i", self.data, opcode_off + instruction_size - 4)[0]
        return self.file_to_rva(opcode_off) + instruction_size + displacement

    def rel8_target_file(self, opcode_off: int) -> int:
        displacement = struct.unpack_from("<b", self.data, opcode_off + 1)[0]
        return opcode_off + 2 + displacement


def variant_name(mask: int) -> str:
    parts: list[str] = []
    if mask & 1:
        parts.append("island_events")
    if mask & 2:
        parts.append("cheat_upgrades")
    if mask & 4:
        parts.append("holiday_ornaments")
    if mask & 8:
        parts.append("behavior_patches")
    return "_".join(parts) if parts else "core"


def load_manifest(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing manifest: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc
    require(isinstance(value, dict), f"{path}: manifest root is not an object")
    return value


def validate_gates(manifest: dict[str, Any], mask: int) -> None:
    expected = {
        "Island Events": bool(mask & 1),
        "Cheat Upgrades": bool(mask & 2),
        "Holiday Ornaments": bool(mask & 4),
        "Behavior Patches": bool(mask & 8),
    }
    actual = {
        "Island Events": bool(nested(manifest, "native_array_contract", "island_events", "enabled")),
        "Cheat Upgrades": bool(nested(manifest, "ScrollingStoreScene", "price_multiplier", "enabled")),
        "Holiday Ornaments": bool(nested(manifest, "native_array_contract", "holiday_ornaments", "enabled")),
        "Behavior Patches": bool(nested(manifest, "BehaviorPatchesGate", "enabled")),
    }
    require(actual == expected, f"manifest feature gates {actual!r}, expected {expected!r}")


def validate_stock_family_recognizers(image: PEImage) -> None:
    find = image.find_unique(FIND_PREFIX, "CCollectableItem::Find prefix")
    require(
        image.data[find + 0x86 : find + 0x86 + len(FIND_STOCK_BYTES)] == FIND_STOCK_BYTES,
        "CCollectableItem::Find does not retain the stock exact-equality family route; "
        "the obsolete B150 Holiday family cave may still be present",
    )
    spawned = image.find_unique(WAS_SPAWNED_PREFIX, "CCollectableItem::WasItemSpawned prefix")
    require(
        image.data[
            spawned + 0x14 : spawned + 0x14 + len(WAS_SPAWNED_STOCK_BYTES)
        ] == WAS_SPAWNED_STOCK_BYTES,
        "CCollectableItem::WasItemSpawned does not retain the stock exact-equality route; "
        "the obsolete B150 Holiday family cave may still be present",
    )


def validate_collection_persistence_pe(image: PEImage) -> None:
    for pattern, label in (
        (COUNT_LOOKUP, "Count collection-state lookup at this+0x4A4"),
        (RESET_COLLECTION, "ResetCollection 0xAF-entry clear"),
        (SAVE_COLLECTION_SPAN, "SaveState 0xAF-entry copy"),
        (LOAD_COLLECTION_SPAN, "LoadState 0xAF-entry copy"),
    ):
        image.find_unique(pattern, label)


def validate_lucky_rock_thresholds_pe(image: PEImage) -> None:
    add = image.find_unique(ADD_PREFIX, "CCollectableItem::Add prefix")
    block = image.data[add : add + 0x280]
    # The stock object stores the Lucky Rock byte in [ebp+0Bh] between
    # push 4 and the relocated GetRandom call.
    random_call = block.find(b"\x6A\x04\x88\x45\x0B\xE8")
    require(random_call >= 0, "CCollectableItem::Add no longer rolls four base family members")
    require(
        block[random_call + 10 : random_call + 10 + 12]
        == bytes.fromhex("8B F8 8D 0C B6 03 BC 8B 94 03 00 00"),
        "CCollectableItem::Add family-base lookup after GetRandom(4) drifted",
    )
    require(
        LUCKY_ROCK_THRESHOLDS in block,
        "CCollectableItem::Add Lucky Rock 0x11/0x22 rarity thresholds drifted",
    )
    require(
        LUCKY_ROCK_RARITY_OFFSETS in block,
        "CCollectableItem::Add uncommon +4 / rare +8 offsets drifted",
    )


def validate_common_pe(image: PEImage) -> None:
    validate_stock_family_recognizers(image)
    validate_collection_persistence_pe(image)
    validate_lucky_rock_thresholds_pe(image)


def normalize_rects(value: Any, label: str) -> list[list[int]]:
    require(isinstance(value, list), f"{label}: expected list")
    result: list[list[int]] = []
    for index, row in enumerate(value):
        require(isinstance(row, list), f"{label}[{index}]: expected list")
        values = int_list(row, f"{label}[{index}]")
        require(len(values) == 4, f"{label}[{index}]: expected four coordinates")
        result.append(values)
    return result


def patch_rows(section: dict[str, Any]) -> list[dict[str, Any]]:
    rows = section.get("patches")
    require(isinstance(rows, list), "CollectableItemHolidayOrnaments.patches must be a list")
    require(all(isinstance(row, dict) for row in rows), "Holiday patch rows must be objects")
    return rows


def patch_row(rows: list[dict[str, Any]], function_name: str) -> dict[str, Any]:
    matches = [row for row in rows if row.get("function") == function_name]
    require(len(matches) == 1, f"expected one Holiday patch row for {function_name}, found {len(matches)}")
    return matches[0]


def validate_positive_collectable_manifest(
    manifest: dict[str, Any], source: SourceContract
) -> None:
    native = nested(manifest, "native_array_contract", "holiday_ornaments")
    require(native.get("collectable_range") == "0x9e-0xa9", "native Holiday range must be 0x9e-0xa9")
    require(as_int(native.get("collection_page"), "holiday collection page") == 5, "Holiday page must be 5")
    require(as_int(native.get("achievement"), "Holiday achievement") == 0x5F, "Holiday achievement must be 0x5F")
    require(as_int(native.get("achievement_target"), "Holiday target") == 12, "Ornamentologist target must be 12")
    require(as_int(native.get("goal_collector_target"), "Goal Collector target") == 13, "Goal Collector target must be 13")

    item = nested(manifest, "CollectableItemHolidayOrnaments")
    expected_rects = [list(rect) for rect in source.spawn_rects]
    require(
        as_int(item.get("spawn_area_count"), "CollectableItemHolidayOrnaments.spawn_area_count")
        == len(expected_rects),
        "Holiday spawn-area count does not match patcher source contract",
    )
    require(
        normalize_rects(
            item.get("mobile_spawn_rects"),
            "CollectableItemHolidayOrnaments.mobile_spawn_rects",
        )
        == expected_rects,
        "Holiday spawn rectangles do not match patcher source contract",
    )
    require(
        normalize_rects(native.get("spawn_rects"), "native Holiday spawn_rects")
        == expected_rects,
        "native Holiday spawn rectangles disagree with CollectableItemHolidayOrnaments",
    )
    spawn_text = flattened_text(item.get("spawn_model", ""))
    require("update/add" in spawn_text and "lucky rock" in spawn_text, "spawn model must preserve stock Update/Add and Lucky Rock routing")

    rows = patch_rows(item)
    reset = patch_row(rows, "?Reset@CCollectableItem@@QAEXXZ")
    require(as_int(reset.get("base_collectable"), "Reset base collectable") == HOLIDAY_START, "Reset base must be 0x9E")
    require(as_int(reset.get("spawn_area_count"), "Reset spawn count") == len(expected_rects), "Reset spawn count mismatch")
    require(
        normalize_rects(reset.get("mobile_spawn_rects"), "Reset mobile_spawn_rects")
        == expected_rects,
        "Reset spawn rectangles mismatch",
    )

    for function_name, expected_range in RARITY_RANGES.items():
        row = patch_row(rows, function_name)
        actual = row.get("range", "")
        require(
            actual == f"{hex(expected_range[0])}-{hex(expected_range[1])}",
            f"{function_name} range is {actual!r}, expected {expected_range!r}",
        )

    count = patch_row(
        rows, "?CollectionCount@CCollectableItem@@QBE?BHW4ECarrying@@_N11@Z"
    )
    require(count.get("range") == "0x9e-0xa9", "CollectionCount Holiday range drifted")
    require(as_int(count.get("collection_base"), "CollectionCount base") == HOLIDAY_START, "CollectionCount base must be 0x9E")

    drop = patch_row(
        rows, "?Drop@CCollectableItem@@UAEXAAVCVillager@@W4ECarrying@@@Z"
    )
    require(drop.get("first_copy_range") == "0x9e-0xa9", "Drop first-copy range drifted")
    require(as_int(drop.get("specific_goal_row"), "Drop goal row") == 0x5F, "Drop must increment Ornamentologist 0x5F")
    require(as_int(drop.get("complete_check_base"), "Drop complete base") == HOLIDAY_START, "Drop complete base must be 0x9E")
    require(
        as_int(drop.get("complete_meta_goal_row", 0x4D), "Drop meta goal row") == 0x4D,
        "complete Holiday collection must increment achievement 0x4D",
    )
    native_drop = (
        manifest.get("holiday_ornament_native_contract", {})
        .get("pickup_dispatch", {})
        .get("drop", "")
    )
    duplicate_text = flattened_text(
        drop.get("duplicate_route", drop.get("note", native_drop))
    )
    require("duplicate" in duplicate_text and "coin" in duplicate_text, "Drop metadata must prove duplicate ornaments take the coin-only route")

    obsolete = {
        "?Find@CCollectableItem@@QAE?B_NAAVCVillager@@W4ECarrying@@AAUldwPoint@@@Z",
        "?WasItemSpawned@CCollectableItem@@QBE?B_NW4ECarrying@@@Z",
    }
    require(
        not any(row.get("function") in obsolete for row in rows),
        "manifest still declares obsolete Holiday Find/WasItemSpawned family caves",
    )

    observers = nested(manifest, "CollectableHolidayOrnamentObservers")
    require(
        int_list(observers.get("registered_collectables", []), "registered_collectables")
        == list(HOLIDAY_IDS),
        "observer registrations must be exactly 0x9E-0xA9",
    )


def validate_positive_scene_manifest(
    manifest: dict[str, Any], source: SourceContract
) -> None:
    scene = nested(manifest, "CollectionSceneHolidayOrnaments")
    require(as_int(scene.get("page"), "Holiday scene page") == 5, "Holiday scene page must be 5")
    require(int_list(scene.get("page_starts", []), "page_starts") == list(PAGE_STARTS), "six page starts drifted")
    require(scene.get("collectable_range") == "0x9e-0xa9", "scene Holiday range drifted")
    require(as_int(scene.get("title_string"), "Holiday title string") == source.title_string, "Holiday collection title string drifted")
    require(as_int(scene.get("background_image_id"), "Holiday background image") == source.image_base + 12, "Holiday background descriptor must follow 12 item descriptors")

    rows = scene.get("item_images")
    require(isinstance(rows, list) and len(rows) == 12, "Holiday scene must have exactly 12 item descriptors")
    for index, row in enumerate(rows):
        require(isinstance(row, dict), f"item_images[{index}] is not an object")
        require(as_int(row.get("collectable"), f"item_images[{index}].collectable") == HOLIDAY_IDS[index], f"item descriptor {index} carrying ID drifted")
        require(as_int(row.get("image_id"), f"item_images[{index}].image_id") == source.image_base + index, f"item descriptor {index} image ID drifted")
        require(int_list(row.get("position", []), f"item_images[{index}].position") == list(source.slot_positions[index]), f"item descriptor {index} position drifted")

    require(int_list(scene.get("tooltip_rarity_label_ids", []), "tooltip labels") == list(TOOLTIP_LABELS), "tooltip labels must be 0x751-0x753")
    for key in ("page_count_route", "page_count_detour_offset"):
        require(key in scene, f"CollectionSceneHolidayOrnaments missing {key}")
    require(
        "code_cave_offset" in scene or "page_count_code_cave_offset" in scene,
        "CollectionSceneHolidayOrnaments missing page-count code-cave offset",
    )
    require(as_int(scene["page_count_detour_offset"], "page_count_detour_offset") >= 0, "invalid page-count detour offset")
    cave_value = scene.get("code_cave_offset", scene.get("page_count_code_cave_offset"))
    require(as_int(cave_value, "page-count code-cave offset") >= 0, "invalid page-count cave offset")
    route_text = flattened_text(scene["page_count_route"])
    require(
        "detour" in route_text and ("helper" in route_text or "page-count" in route_text),
        "page-count route must document its fixed-size helper detour",
    )

    total = scene.get("main_scene_total")
    require(isinstance(total, dict), "CollectionSceneHolidayOrnaments.main_scene_total missing")
    require(int_list(total.get("family_starts", []), "main total family starts") == list(PAGE_STARTS), "main total family starts drifted")
    require(as_int(total.get("total"), "main collection total") == 72, "main collection total must be 72")


def validate_positive_achievement_manifest(
    manifest: dict[str, Any], source: SourceContract
) -> None:
    achievement = nested(manifest, "HolidayOrnamentAchievement")
    require(as_int(achievement.get("achievement_id"), "Ornamentologist ID") == 0x5F, "Ornamentologist ID must be 0x5F")
    require(as_int(achievement.get("target"), "Ornamentologist target") == 12, "Ornamentologist target must be 12")
    require(achievement.get("title") == "Ornamentologist", "Ornamentologist title drifted")
    require(
        achievement.get("description")
        == "You completed the collection of holiday ornaments.",
        "Ornamentologist description drifted",
    )
    require(as_int(achievement.get("title_string"), "Ornamentologist title string") == source.achievement_title_string, "Ornamentologist title string ID drifted")
    require(as_int(achievement.get("description_string"), "Ornamentologist description string") == source.achievement_description_string, "Ornamentologist description string ID drifted")
    require(as_int(achievement.get("master_collector_id"), "Master Collector ID") == 0x4D, "Master Collector ID must be 0x4D")
    require(as_int(achievement.get("master_collector_target"), "Master Collector target") == 6, "Master Collector target must be 6")
    require(as_int(achievement.get("goal_collector_id"), "Goal Collector ID") == 0x54, "Goal Collector ID must be 0x54")
    require(as_int(achievement.get("goal_collector_target"), "Goal Collector target") == 13, "Goal Collector target must be 13")
    require(as_int(achievement.get("notification_queue_count"), "achievement notification queue count") == 0x60, "achievement notification queue count must be 0x60")
    save_text = flattened_text(achievement.get("save_state_note", ""))
    require("0x125" in save_text and "no save-state size change" in save_text, "achievement metadata must preserve the existing 0x125-record save block")


def validate_positive_native_contract(
    manifest: dict[str, Any], source: SourceContract
) -> None:
    contract = nested(manifest, "holiday_ornament_native_contract")
    require(contract.get("status") == "validated", "Holiday native contract is not validated")

    state = nested(contract, "collection_state")
    expected_state = {
        "count_lookup_base": 0x4A4,
        "stock_clear_start": 0x5E0,
        "stock_clear_entries": 0xAF,
        "stock_clear_end_exclusive": 0x89C,
        "holiday_state_start": 0x71C,
        "holiday_state_end_exclusive": 0x74C,
    }
    for key, expected in expected_state.items():
        require(as_int(state.get(key), f"collection_state.{key}") == expected, f"collection_state.{key} drifted")
    for key in (
        "save_state_covers_holiday_range",
        "load_state_covers_holiday_range",
        "reset_collection_covers_holiday_range",
    ):
        require(state.get(key) is True, f"collection_state.{key} must be true")

    spawning = nested(contract, "spawning")
    require(as_int(spawning.get("stock_spawn_area_count"), "stock spawn-area count") == 16, "stock spawn-area count must remain 16")
    require(as_int(spawning.get("holiday_spawn_area_count"), "Holiday spawn-area count") == 3, "Holiday spawn-area count must be 3")
    require(as_int(spawning.get("total_spawn_area_count"), "total spawn-area count") == 19, "total spawn-area count must be 19")
    require(
        normalize_rects(spawning.get("mobile_spawn_rects"), "native mobile spawn rectangles")
        == [list(rect) for rect in MOBILE_1716_SPAWN_RECTS],
        "native contract spawn rectangles drifted from mobile 1.7.16",
    )

    total = nested(contract, "count_total_collectables")
    require(total.get("stock_scan_range") == "0x4f-0xfd", "stock total scan must remain 0x4F-0xFD")
    require(total.get("stock_skip_range") == "0x73-0x85", "stock non-collectible hole drifted")
    require(total.get("holiday_range_included_without_detour") is True, "Holiday IDs must remain inside the stock total-count scan")

    scene = nested(contract, "collection_scene")
    require(as_int(scene.get("page"), "native collection page") == 5, "native Holiday page must be 5")
    require(int_list(scene.get("page_starts", []), "native page starts") == list(PAGE_STARTS), "native page starts drifted")
    require(int_list(scene.get("g_collectable_values", []), "native gCollectable values") == list(HOLIDAY_IDS), "native gCollectable page must be exactly 0x9E-0xA9")
    require(int_list(scene.get("tooltip_rarity_label_ids", []), "native tooltip labels") == list(TOOLTIP_LABELS), "native tooltip labels drifted")
    public_scene = nested(manifest, "CollectionSceneHolidayOrnaments")
    expected_slots = [
        {
            "image_id": as_int(row["image_id"], f"public slot {index} image"),
            "position": int_list(row["position"], f"public slot {index} position"),
        }
        for index, row in enumerate(public_scene["item_images"])
    ]
    native_slots = scene.get("slot_entries")
    require(isinstance(native_slots, list) and len(native_slots) == 12, "native collection scene must record 12 slot entries")
    require(all(isinstance(row, dict) for row in native_slots), "native slot entries must be objects")
    normalized_native_slots = [
        {
            "image_id": as_int(row.get("image_id"), f"native slot {index} image"),
            "position": int_list(row.get("position", []), f"native slot {index} position"),
        }
        for index, row in enumerate(native_slots)
    ]
    require(normalized_native_slots == expected_slots, "native slot descriptors disagree with CollectionSceneHolidayOrnaments")
    raw_mobile_slots = scene.get("mobile_slot_positions")
    require(isinstance(raw_mobile_slots, list), "native mobile slot positions missing")
    normalized_mobile_slots = [
        int_list(row, f"native mobile slot {index}")
        for index, row in enumerate(raw_mobile_slots)
        if isinstance(row, list)
    ]
    require(
        normalized_mobile_slots == [list(row) for row in source.mobile_slot_positions],
        "native mobile slot coordinates drifted",
    )

    main_total = nested(contract, "main_scene_total")
    require(as_int(main_total.get("total"), "native main total") == 72, "native collection total must be 72")
    require(main_total.get("suffix") == " / 72", "native collection suffix must be ' / 72'")
    require(int_list(main_total.get("family_starts", []), "native family starts") == list(PAGE_STARTS), "native main total family starts drifted")

    pickup = nested(contract, "pickup_dispatch")
    require(pickup.get("observer_registration") == "validated", "Holiday observer registration is not validated")
    pickup_text = flattened_text(pickup)
    require("exact" in pickup_text and "observer" in pickup_text, "pickup contract must document stock exact-equality plus observer dispatch")
    require("code cave" not in pickup_text and "range detour" not in pickup_text, "pickup contract still documents obsolete Find/WasItemSpawned caves")

    persistence = flattened_text(contract.get("persistence", state))
    for token in ("count", "save", "load", "reset"):
        require(token in persistence, f"native persistence contract does not mention {token}")

    lucky = flattened_text(
        spawning.get(
            "add_and_lucky_rock_route",
            contract.get("lucky_rock", contract.get("spawn_model", "")),
        )
    )
    require(
        all(
            token in lucky
            for token in ("3/6600", "3/3300", "83", "13", "4", "66", "26", "8")
        ),
        "native contract must preserve the exact stock Lucky Rock Update/Add odds",
    )
    require(
        spawning.get("normal_spawn_attempt_per_update") == "3/6600 (1/2200)",
        "normal collectible spawn-attempt odds drifted",
    )
    require(
        spawning.get("lucky_rock_spawn_attempt_per_update") == "3/3300 (1/1100)",
        "Lucky Rock collectible spawn-attempt odds drifted",
    )
    require(
        spawning.get("normal_rarity_percent")
        == {"common": 83, "uncommon": 13, "rare": 4},
        "normal collectible rarity odds drifted",
    )
    require(
        spawning.get("lucky_rock_rarity_percent")
        == {"common": 66, "uncommon": 26, "rare": 8},
        "Lucky Rock collectible rarity odds drifted",
    )

    control = nested(contract, "control_flow")
    require(control.get("find_code_cave") is False, "obsolete Find Holiday cave is still enabled")
    require(control.get("was_item_spawned_code_cave") is False, "obsolete WasItemSpawned Holiday cave is still enabled")
    require(control.get("handle_mouse_code_cave") is True, "tooltip HandleMouse code cave must remain validated")
    require(control.get("page_count_code_cave") is True, "DrawScene page-count code cave must be validated")
    require(control.get("drop_first_copy_route") is True, "Drop first-copy route must be validated")
    require(control.get("achievement_completion_idempotent") is True, "achievement completion must be idempotent")


def validate_positive_collector_manifest(manifest: dict[str, Any]) -> None:
    collector = nested(manifest, "TheCollectorHolidayOrnaments")
    relocations = collector.get("offer_count_relocations")
    require(isinstance(relocations, list) and len(relocations) == 3, "Collector must have exactly three Holiday offer-count relocations")
    actual_args: list[tuple[int, int, int, int]] = []
    rarities: set[str] = set()
    routes: set[str] = set()
    for index, row in enumerate(relocations):
        require(isinstance(row, dict), f"offer_count_relocations[{index}] is not an object")
        require("operand_offset" in row, f"offer_count_relocations[{index}] has no relocation operand offset")
        as_int(row["operand_offset"], f"offer_count_relocations[{index}].operand_offset")
        rarity = str(row.get("rarity", "")).lower()
        require(rarity in {"common", "uncommon", "rare"}, f"offer_count_relocations[{index}] has invalid rarity {rarity!r}")
        rarities.add(rarity)
        route_name = str(row.get("route", ""))
        require("CollectionCountWithHolidayOrnaments" in route_name, f"offer_count_relocations[{index}] does not target the Holiday aggregate helper")
        routes.add(route_name)
        args = row.get("collection_count_args", row.get("args"))
        if args is not None:
            require(isinstance(args, list), f"offer_count_relocations[{index}] argument metadata is not a list")
            values = tuple(int_list(args, f"offer_count_relocations[{index}].args"))
            require(len(values) == 4, f"offer_count_relocations[{index}] must have four CollectionCount arguments")
            actual_args.append(values)
    require(rarities == {"common", "uncommon", "rare"}, "Collector relocations must cover common, uncommon, and rare exactly once")
    require(len(routes) == 1, "all three Collector offer relocations must target the same aggregate helper")
    if actual_args:
        require(set(actual_args) == set(COLLECTOR_OFFER_ARGUMENTS), "Collector Holiday argument metadata must cover rare, uncommon, and common exactly once")

    availability = collector.get("availability_route")
    require(availability is not None, "Collector availability_route missing")
    availability_text = flattened_text(availability)
    require("mobile" in availability_text or "stock" in availability_text, "Collector availability route must document stock/mobile parity")
    require(
        "holiday-only" not in availability_text
        and "extra availability" not in availability_text
        and not (
            isinstance(availability, dict)
            and availability.get("holiday_final_eligibility") is True
        ),
        "Collector still adds the non-mobile Holiday-only final availability hook",
    )

    reset = collector.get("achievement_reset_route")
    require(reset is not None, "Collector achievement_reset_route missing")
    reset_text = flattened_text(reset)
    require("0x5f" in reset_text, "Collector reset helper must cover Ornamentologist 0x5F progress")
    require("helper" in reset_text or "reloc" in reset_text, "Collector achievement reset must use a relocation-safe helper route")
    if isinstance(reset, dict):
        if "stock_tail_argument" in reset:
            require(as_int(reset["stock_tail_argument"], "Collector stock tail argument") == 0x5E, "Collector stock tail argument must remain 0x5E")
        require(
            "tail_relocation_operand" in reset
            or {"detour_offset", "code_cave_offset"}.issubset(reset),
            "Collector reset route must identify its relocation operand or detour/cave",
        )
    require(as_int(collector.get("sell_choice"), "Collector sell choice") == 0, "Collector Sell choice must be 0")


def validate_positive_art_manifest(
    build_dir: Path, manifest: dict[str, Any], source: SourceContract
) -> None:
    art = nested(manifest, "holiday_ornament_collection_art")
    status = flattened_text(art.get("status", ""))
    require("missing" not in status and "partial" not in status, "Holiday collection art is incomplete")
    require("fallback_mobile_atlas" not in status, "B151 Holiday art still depends on the ignored mobile atlas")
    entries = art.get("entries")
    require(isinstance(entries, list) and len(entries) == 12, "Holiday art manifest must have exactly 12 icon entries")
    for index, row in enumerate(entries):
        require(isinstance(row, dict), f"Holiday art entry {index} is not an object")
        require(as_int(row.get("collectable"), f"art entry {index} collectable") == HOLIDAY_IDS[index], f"Holiday art entry {index} carrying ID drifted")
        require(as_int(row.get("image_id"), f"art entry {index} image ID") == source.image_base + index, f"Holiday art entry {index} image ID drifted")
        relative = str(row.get("path", "")).replace(chr(92), "/")
        require(relative.endswith(source.runtime_files[index]), f"Holiday art entry {index} runtime filename drifted")
        target = build_dir / "Images" / relative
        require(target.is_file(), f"missing Holiday icon: {target}")
        width, height = png_size(target)
        require(width > 0 and height > 0, f"{target}: empty dimensions")
        require(
            sha256_file(target) == str(row.get("sha256", "")).upper(),
            f"{target}: hash differs from canonical art manifest",
        )

    background = build_dir / "Images" / "collection-ornaments_background.png"
    require(background.is_file(), f"missing Holiday collection background: {background}")
    require(png_size(background) == (1024, 768), "Holiday collection background must be 1024x768")
    background_record = art.get("background")
    require(isinstance(background_record, dict), "Holiday background manifest record missing")
    require(
        sha256_file(background)
        == str(background_record.get("sha256", "")).upper(),
        "Holiday background hash differs from canonical art manifest",
    )
    small = build_dir / "Images" / "collectables_small.png"
    require(small.is_file(), f"missing ornament-aware collectables_small.png: {small}")
    require(png_size(small) == (240, 640), "collectables_small.png must be a 240x640 6x16 sheet")
    small_contract = art.get("collectables_small")
    require(isinstance(small_contract, dict), "collectables_small art contract missing")
    require(int_list(small_contract.get("engine_frame_range", []), "engine frame range") == [79, 90], "yard sprite frames must be 79-90")
    visible = small_contract.get("visible_engine_frames")
    require(isinstance(visible, list) and len(visible) == 12, "collectables_small must validate 12 visible ornament frames")
    require(all(isinstance(row, dict) for row in visible), "visible ornament frame records must be objects")
    require(all(as_int(row.get("alpha_pixels"), "alpha_pixels") > 0 for row in visible), "every ornament yard frame must contain visible pixels")


def validate_positive_manifest(
    build_dir: Path, manifest: dict[str, Any], source: SourceContract
) -> None:
    validate_positive_collectable_manifest(manifest, source)
    validate_positive_scene_manifest(manifest, source)
    validate_positive_achievement_manifest(manifest, source)
    validate_positive_native_contract(manifest, source)
    validate_positive_collector_manifest(manifest)
    validate_positive_art_manifest(build_dir, manifest, source)


def push_immediate(value: int) -> bytes:
    if 0 <= value <= 0x7F:
        return b"\x6A" + bytes([value])
    return b"\x68" + struct.pack("<I", value)


def collection_count_argument_pattern(args: tuple[int, int, int, int]) -> bytes:
    base, common, uncommon, rare = args
    return (
        push_immediate(rare)
        + push_immediate(uncommon)
        + push_immediate(common)
        + push_immediate(base)
    )


def handle_mouse_base(image: PEImage) -> int:
    candidates = [
        position
        for position in image.find_all(HANDLE_MOUSE_PREFIX, executable_only=True)
        if image.data[position + 0x2A : position + 0x32]
        == bytes.fromhex("83 E9 01 74 66 83 E9 01")
    ]
    require(len(candidates) == 1, f"{image.path}: expected one CCollectionScene::HandleMouse, found {len(candidates)}")
    return candidates[0]


def validate_near_detour(
    image: PEImage,
    function_base: int,
    detour_offset: int,
    cave_offset: int,
    label: str,
) -> int:
    detour = function_base + detour_offset
    require(image.data[detour] == 0xE9, f"{label}: detour is not a near jump")
    require(
        image.data[detour + 5 : detour + 7] == b"\x90\x90",
        f"{label}: fixed-size seven-byte detour padding drifted",
    )
    cave = image.rva_to_file(image.rel32_target_rva(detour))
    require(cave_offset > detour_offset, f"{label}: declared code-cave offset is not after the detour")
    # Patcher manifests record the cave as a COFF-section offset. If a future
    # build records it function-relative instead, it will equal cave-base.
    function_relative = cave - function_base
    require(
        cave_offset == function_relative or cave_offset > function_relative,
        f"{label}: declared code-cave offset {cave_offset:#x} is inconsistent "
        f"with linked cave delta {function_relative:#x}",
    )
    return cave


def validate_tooltip_pe(image: PEImage, scene: dict[str, Any]) -> None:
    base = handle_mouse_base(image)
    require(struct.unpack_from("<I", image.data, base + 0x4E)[0] == 5, "HandleMouse previous-page wrap must target page 5")
    require(image.data[base + 0x7B] == 6, "HandleMouse next-page wrap must use six pages")
    detour_offset = as_int(scene.get("tooltip_detour_offset"), "tooltip_detour_offset")
    cave_offset = as_int(scene.get("tooltip_code_cave_offset"), "tooltip_code_cave_offset")
    cave = validate_near_detour(image, base, detour_offset, cave_offset, "HandleMouse tooltip")
    cave_data = image.data[cave : cave + 64]
    require(bytes.fromhex("83 F8 0F") in cave_data, "tooltip cave lacks Holiday common-bucket lower bound")
    require(bytes.fromhex("83 F8 12") in cave_data, "tooltip cave lacks Holiday rare-bucket upper bound")
    require(bytes.fromhex("8D 98 42 07 00 00") in cave_data, "tooltip cave no longer maps buckets 15-17 to labels 0x751-0x753")
    require(
        image.rel8_target_file(cave + 3) == cave + 21
        and image.rel8_target_file(cave + 8) == cave + 21,
        "tooltip cave stock-bound branches do not reach the stock lookup",
    )
    for jump in (cave + 16, cave + 28):
        require(image.data[jump] == 0xE9, "tooltip cave return is not a near jump")
        require(
            image.rva_to_file(image.rel32_target_rva(jump)) == base + 0x1F2,
            "tooltip cave does not resume at native HandleMouse+0x1F2",
        )


def validate_page_count_detour_pe(image: PEImage, scene: dict[str, Any]) -> None:
    detour_offset = as_int(scene.get("page_count_detour_offset"), "page_count_detour_offset")
    cave_offset = as_int(
        scene.get("code_cave_offset", scene.get("page_count_code_cave_offset")),
        "page-count code-cave offset",
    )
    matches: list[tuple[int, int]] = []
    for base in image.find_all(DRAW_SCENE_PREFIX, executable_only=True):
        detour = base + detour_offset
        if detour >= len(image.data) or image.data[detour] != 0xE9:
            continue
        try:
            cave = image.rva_to_file(image.rel32_target_rva(detour))
        except ValidationError:
            continue
        if image.data[cave : cave + 4] == bytes.fromhex("FF 77 14 E8"):
            matches.append((base, cave))
    require(len(matches) == 1, f"{image.path}: expected one DrawScene page-count detour, found {len(matches)}")
    base, cave = matches[0]
    detour = base + detour_offset
    require(
        image.data[detour + 5 : detour + 7] == b"\x90\x90",
        "DrawScene page-count detour padding drifted",
    )
    require(cave_offset > detour_offset, "DrawScene manifest cave offset is not after its detour")
    cave_data = image.data[cave : cave + 96]
    require(cave_data[3] == 0xE8, "DrawScene page-count cave has no helper call")
    require(cave_data[8:10] == b"\x50\xE9", "DrawScene page-count cave does not push the helper result and jump back")
    return_target = image.rva_to_file(image.rel32_target_rva(cave + 9))
    require(base <= return_target < base + 0x380, "DrawScene page-count cave does not return to native DrawScene")


def validate_positive_achievement_pe(
    image: PEImage, manifest: dict[str, Any], source: SourceContract
) -> None:
    row = struct.pack(
        "<7I",
        0x5F,
        12,
        0x1ED,
        0,
        source.achievement_title_string,
        source.achievement_description_string,
        0,
    )
    matches = image.find_all(row, executable_only=False)
    require(len(matches) == 1, f"expected one Ornamentologist achievement row, found {len(matches)}")
    table = matches[0] - 0x5F * 28
    require(table >= 0, "achievement table base underflow")

    def achievement_row(index: int) -> tuple[int, ...]:
        return struct.unpack_from("<7I", image.data, table + index * 28)

    master = achievement_row(0x4D)
    goal_collector = achievement_row(0x54)
    ornament = achievement_row(0x5F)
    require(master[0] == 0x4D and master[1] == 6, "achievement 0x4D target must be six completed collection families")
    require(goal_collector[0] == 0x54 and goal_collector[1] == 13, "Goal Collector 0x54 target must be 13")
    require(ornament[0] == 0x5F and ornament[1] == 12, "Ornamentologist 0x5F target must be 12")
    for text in (
        b"Ornamentologist\0",
        b"You completed the collection of holiday ornaments.\0",
    ):
        require(text in image.data, f"linked PE missing Holiday achievement string {text!r}")
    require(
        len(image.find_all(bytes.fromhex("83 FF 60"), executable_only=True)) >= 2,
        "DrawAchievement does not contain both 0x60 visible-row bounds",
    )
    require(
        image.find_all(bytes.fromhex("83 F8 60"), executable_only=True),
        "QueueAchievementNotify bound is not 0x60",
    )
    require(
        image.find_all(bytes.fromhex("B9 60 00 00 00"), executable_only=True),
        "ResetNotifyQueue count is not 0x60",
    )

    contract = nested(manifest, "holiday_ornament_native_contract")
    achievement_contract = contract.get("achievement")
    require(isinstance(achievement_contract, dict), "native achievement contract missing")
    require(as_int(achievement_contract.get("collection_master_target"), "collection master target") == 6, "native achievement contract must record 0x4D target 6")
    require(as_int(achievement_contract.get("goal_collector_target"), "native Goal Collector target") == 13, "native achievement contract must record 0x54 target 13")
    require(as_int(achievement_contract.get("ornamentologist_target"), "native Ornamentologist target") == 12, "native achievement contract must record 0x5F target 12")
    require(as_int(achievement_contract.get("visible_order_bound"), "visible achievement order bound") == 0x60, "visible achievement order bound must be 0x60")
    require(as_int(achievement_contract.get("notify_queue_bound"), "achievement notify queue bound") == 0x60, "achievement notify queue bound must be 0x60")


def validate_positive_drop_pe(image: PEImage) -> None:
    base = image.find_unique(DROP_PREFIX, "CCollectableItem::Drop prefix")
    block = image.data[base : base + 0x380]
    for pattern, label in (
        (b"\x8D\x87" + struct.pack("<i", -HOLIDAY_START), "Holiday index calculation"),
        (push_immediate(0x5F), "Ornamentologist increment"),
        (push_immediate(HOLIDAY_START), "Holiday family completion check"),
        (push_immediate(0x4D), "six-family collection achievement increment"),
    ):
        require(pattern in block, f"Drop lacks {label}")


def validate_positive_collection_count_pe(image: PEImage) -> None:
    base = image.find_unique(
        COLLECTION_COUNT_PREFIX, "CCollectableItem::CollectionCount prefix"
    )
    payload = image.data[base + 0x0B : base + 0x0B + 34]
    require(
        payload[0:6] == b"\x81\xFA" + struct.pack("<I", HOLIDAY_START),
        "CollectionCount Holiday lower bound is not 0x9E",
    )
    require(
        payload[12:18] == b"\x81\xFA" + struct.pack("<I", HOLIDAY_END),
        "CollectionCount Holiday upper bound is not 0xA9",
    )
    require(
        payload[24:29] == b"\xBE" + struct.pack("<I", HOLIDAY_START),
        "CollectionCount does not select Holiday base 0x9E",
    )


def validate_positive_spawn_pe(image: PEImage) -> None:
    reset = image.find_unique(RESET_PREFIX, "CCollectableItem::Reset prefix")
    block = image.data[reset : reset + 0x360]
    holiday_prefix = (
        b"\x8B\xCB"
        + push_immediate(HOLIDAY_START)
        + bytes.fromhex("83 EC 10 8B C4 0F 11 00 E8")
    )
    registrations: list[int] = []
    position = 0
    while True:
        position = block.find(holiday_prefix, position)
        if position < 0:
            break
        call = reset + position + len(holiday_prefix) - 1
        registrations.append(image.rel32_target_rva(call))
        position += len(holiday_prefix)
    require(len(registrations) == 3, f"expected three Holiday AddSpawnArea registrations, found {len(registrations)}")
    require(len(set(registrations)) == 1, "Holiday spawn registrations do not call one AddSpawnArea target")
    add_spawn_target = registrations[0]
    all_spawn_calls = 0
    for index, opcode in enumerate(block[:-4]):
        if opcode != 0xE8:
            continue
        try:
            target = image.rel32_target_rva(reset + index)
        except (struct.error, ValidationError):
            continue
        if target == add_spawn_target:
            all_spawn_calls += 1
    require(all_spawn_calls == 19, f"expected 19 total AddSpawnArea calls, found {all_spawn_calls}")


def observer_records(image: PEImage) -> list[tuple[int, int, int]]:
    records: list[tuple[int, int, int]] = []
    for section in image.executable_sections():
        start = section.raw_ptr
        end = start + section.raw_size - 17
        for offset in range(start, max(start, end) + 1):
            if (
                image.data[offset] != 0x68
                or image.data[offset + 5] != 0x68
                or image.data[offset + 10 : offset + 12] != b"\x8B\xCE"
                or image.data[offset + 12] != 0xE8
            ):
                continue
            carrying = struct.unpack_from("<I", image.data, offset + 6)[0]
            if carrying not in HOLIDAY_IDS:
                continue
            observer_address = struct.unpack_from("<I", image.data, offset + 1)[0]
            call_target = image.rel32_target_rva(offset + 12)
            records.append((carrying, observer_address, call_target))
    return records


def holiday_observer_blocks(
    image: PEImage,
) -> list[list[tuple[int, int, int]]]:
    grouped: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
    for record in observer_records(image):
        grouped.setdefault((record[1], record[2]), []).append(record)
    return [
        rows
        for rows in grouped.values()
        if [row[0] for row in rows] == list(HOLIDAY_IDS)
    ]


def validate_positive_observers_pe(image: PEImage) -> None:
    blocks = holiday_observer_blocks(image)
    require(
        len(blocks) == 1,
        "linked PE must contain exactly one 12-record Holiday observer block",
    )
    records = blocks[0]
    require(
        [row[0] for row in records] == list(HOLIDAY_IDS),
        "linked Holiday observer block must be exactly 0x9E-0xA9 in order",
    )


def collector_impact_base(image: PEImage) -> int:
    candidates = []
    for body in image.find_all(COLLECTOR_IMPACT_BODY, executable_only=True):
        base = body - 9
        if (
            base >= 0
            and image.data[base : base + 7]
            == bytes.fromhex("55 8B EC 83 7D 08 00")
            and image.data[base + 7] in (0x74, 0x75)
        ):
            candidates.append(base)
    require(
        len(candidates) == 1,
        f"{image.path}: expected one prefixed CEventTheCollector::ImpactGame, "
        f"found {len(candidates)}",
    )
    return candidates[0]


def validate_positive_collector_pe(image: PEImage, manifest: dict[str, Any]) -> None:
    can_fire = image.find_unique(
        COLLECTOR_CAN_FIRE_PREFIX, "CEventTheCollector::CanFire prefix"
    )
    collector = nested(manifest, "TheCollectorHolidayOrnaments")
    relocations = collector["offer_count_relocations"]
    helper_targets: list[int] = []
    for index, row in enumerate(relocations):
        operand = as_int(
            row["operand_offset"], f"offer_count_relocations[{index}].operand_offset"
        )
        opcode = can_fire + operand - 1
        require(
            image.data[opcode] == 0xE8,
            f"Collector offer relocation {index} is not attached to a near call",
        )
        helper_targets.append(image.rel32_target_rva(opcode))
    require(
        len(set(helper_targets)) == 1,
        "Collector common/uncommon/rare calls do not share one aggregate helper",
    )
    helper_file = image.rva_to_file(helper_targets[0])
    helper_data = image.data[helper_file : helper_file + 0x180]
    require(
        push_immediate(HOLIDAY_START) in helper_data,
        "Collector aggregate helper does not add Holiday base 0x9E",
    )
    obsolete_availability = collection_count_argument_pattern(
        (HOLIDAY_START, 1, 1, 1)
    )
    require(
        not image.find_all(obsolete_availability, executable_only=True),
        "linked PE still contains the non-mobile Holiday-only Collector availability call",
    )

    reset_route = collector.get("achievement_reset_route")
    base = collector_impact_base(image)
    branch_target = image.rel8_target_file(base + 7)
    require(
        image.data[branch_target : branch_target + 4] == bytes.fromhex("5D C2 04 00"),
        "Collector Keep branch does not land on the native return",
    )
    if isinstance(reset_route, dict) and "tail_relocation_operand" in reset_route:
        operand = as_int(
            reset_route["tail_relocation_operand"],
            "Collector reset tail relocation operand",
        )
        opcode = base + operand - 1
        require(
            image.data[opcode] in (0xE8, 0xE9),
            "Collector reset tail relocation is not attached to a near call/jump",
        )
        helper_rva = image.rel32_target_rva(opcode)
        helper_file = image.rva_to_file(helper_rva)
        reset_bytes = image.data[helper_file : helper_file + 0x100]
    elif isinstance(reset_route, dict) and {
        "detour_offset",
        "code_cave_offset",
    }.issubset(reset_route):
        cave = validate_near_detour(
            image,
            base,
            as_int(reset_route["detour_offset"], "Collector reset detour"),
            as_int(reset_route["code_cave_offset"], "Collector reset cave"),
            "Collector Sell achievement reset",
        )
        reset_bytes = image.data[cave : cave + 96]
    else:
        reset_bytes = image.data[base : base + 0x180]
    require(push_immediate(0x5F) in reset_bytes, "Collector Sell route does not push achievement 0x5F")


def validate_positive_descriptors_pe(
    image: PEImage, scene: dict[str, Any], source: SourceContract
) -> None:
    require(len(image.find_all(COLLECTION_TABLE_72, executable_only=False)) == 1, "linked PE must contain one exact 72-item collection table")
    require(len(image.find_all(PAGE_START_TABLE, executable_only=False)) >= 1, "linked PE lacks exact six-page start table")
    require(b" / 72\0" in image.data, "linked PE lacks the /72 collection suffix")
    require(b" / 60\0" not in image.data, "Holiday PE still contains the /60 collection suffix")

    for index, row in enumerate(scene["item_images"]):
        descriptor = struct.pack(
            "<3I",
            as_int(row["image_id"], f"item image {index}"),
            *int_list(row["position"], f"item position {index}"),
        )
        require(descriptor in image.data, f"linked PE lacks exact Holiday UI descriptor {index}")
    for rectangle in source.spawn_rects:
        require(struct.pack("<4I", *rectangle) in image.data, f"linked PE lacks spawn rectangle {rectangle!r}")
    for pattern in RARITY_PATTERNS:
        require(len(image.find_all(pattern, executable_only=True)) == 1, "linked PE lacks an exact Holiday rarity range")
    for carrying in HOLIDAY_IDS:
        require(push_immediate(carrying) in image.data, f"linked PE lacks observer/immediate for {carrying:#x}")
    for filename in source.runtime_files:
        path = f"CollectionOrnaments/{filename}".encode("ascii") + b"\0"
        require(path in image.data, f"linked PE lacks image descriptor path {path!r}")
    require(b"collection-ornaments_background.png\0" in image.data, "linked PE lacks Holiday background descriptor path")


def validate_positive_pe(
    image: PEImage, manifest: dict[str, Any], source: SourceContract
) -> None:
    scene = nested(manifest, "CollectionSceneHolidayOrnaments")
    validate_positive_descriptors_pe(image, scene, source)
    validate_tooltip_pe(image, scene)
    validate_page_count_detour_pe(image, scene)
    validate_positive_spawn_pe(image)
    validate_positive_observers_pe(image)
    validate_positive_collection_count_pe(image)
    validate_positive_drop_pe(image)
    validate_positive_achievement_pe(image, manifest, source)
    validate_positive_collector_pe(image, manifest)


POSITIVE_MANIFEST_SECTIONS = (
    "HolidayOrnamentAchievement",
    "CollectableItemHolidayOrnaments",
    "CollectableHolidayOrnamentObservers",
    "CollectionSceneHolidayOrnaments",
    "TheCollectorHolidayOrnaments",
    "holiday_ornament_native_contract",
)


def validate_negative_manifest(
    build_dir: Path, manifest: dict[str, Any], source: SourceContract
) -> None:
    disabled = nested(manifest, "HolidayOrnamentsCollection")
    require(disabled.get("enabled") is False, "Holiday-disabled manifest does not record enabled=false")
    for key in POSITIVE_MANIFEST_SECTIONS:
        require(key not in manifest, f"Holiday-disabled manifest unexpectedly contains {key}")
    art = manifest.get("holiday_ornament_collection_art")
    require(isinstance(art, dict) and art.get("enabled") is False, "Holiday-disabled art contract must record enabled=false")

    background = build_dir / "Images" / "collection-ornaments_background.png"
    require(not background.exists(), f"Holiday-disabled build contains stale background {background}")
    ornament_dir = build_dir / "Images" / "CollectionOrnaments"
    if ornament_dir.exists():
        stale = [path for path in ornament_dir.rglob("*") if path.is_file()]
        require(not stale, f"Holiday-disabled build contains {len(stale)} stale ornament files")


def validate_negative_pe(image: PEImage, source: SourceContract) -> None:
    require(len(image.find_all(COLLECTION_TABLE_60, executable_only=False)) == 1, "stock PE must contain one exact 60-item collection table")
    require(not image.find_all(COLLECTION_TABLE_72, executable_only=False), "Holiday-disabled PE contains the 72-item collection table")
    require(b" / 60\0" in image.data, "Holiday-disabled PE lacks the /60 collection suffix")
    require(b" / 72\0" not in image.data, "Holiday-disabled PE contains the /72 collection suffix")

    handle = handle_mouse_base(image)
    require(struct.unpack_from("<I", image.data, handle + 0x4E)[0] == 4, "stock previous-page wrap must target page 4")
    require(image.data[handle + 0x7B] == 5, "stock next-page wrap must use five pages")
    require(image.data[handle + 0x1EB] != 0xE9, "Holiday-disabled HandleMouse contains the tooltip detour")

    for pattern in RARITY_PATTERNS:
        require(not image.find_all(pattern, executable_only=True), "Holiday-disabled PE contains a Holiday rarity-range hook")
    count = image.find_unique(
        COLLECTION_COUNT_PREFIX, "stock CCollectableItem::CollectionCount prefix"
    )
    require(
        image.data[count + 0x0B : count + 0x0E] == bytes.fromhex("8D 42 99"),
        "Holiday-disabled CollectionCount contains a Holiday family range hook",
    )
    require(
        not holiday_observer_blocks(image),
        "Holiday-disabled PE contains the appended 12-record Holiday observer block",
    )
    require(
        not image.find_all(
            collection_count_argument_pattern((HOLIDAY_START, 1, 1, 1)),
            executable_only=True,
        ),
        "Holiday-disabled PE contains obsolete Collector Holiday availability args",
    )

    impact = collector_impact_base(image)
    impact_end = image.rel8_target_file(impact + 7)
    require(push_immediate(0x5F) not in image.data[impact:impact_end], "Holiday-disabled Collector Sell route resets 0x5F")

    for text in (
        b"Ornamentologist\0",
        b"You completed the collection of holiday ornaments.\0",
        b"collection-ornaments_background.png\0",
    ):
        require(text not in image.data, f"Holiday-disabled PE contains Holiday data {text!r}")
    for filename in source.runtime_files:
        require(
            f"CollectionOrnaments/{filename}".encode("ascii") + b"\0" not in image.data,
            f"Holiday-disabled PE contains descriptor for {filename}",
        )


@dataclass(frozen=True)
class VariantResult:
    mask: int
    variant: str
    holiday_enabled: bool
    executable: Path
    sha256: str


def validate_variant(
    outputs_root: Path,
    mask: int,
    exe_name: str,
    source: SourceContract,
) -> VariantResult:
    variant = variant_name(mask)
    build_dir = outputs_root / f"{BUILD_PREFIX}{variant}"
    require(build_dir.is_dir(), f"missing B151 variant directory: {build_dir}")
    manifest = load_manifest(build_dir / "patch-manifest.json")
    validate_gates(manifest, mask)
    executable = build_dir / exe_name
    require(executable.is_file(), f"missing linked executable: {executable}")
    image = PEImage(executable)
    validate_common_pe(image)
    holiday_enabled = bool(mask & 4)
    if holiday_enabled:
        validate_positive_manifest(build_dir, manifest, source)
        validate_positive_pe(image, manifest, source)
    else:
        validate_negative_manifest(build_dir, manifest, source)
        validate_negative_pe(image, source)
    return VariantResult(
        mask=mask,
        variant=variant,
        holiday_enabled=holiday_enabled,
        executable=executable,
        sha256=sha256_file(executable),
    )


def validate_matrix(outputs_root: Path, exe_name: str) -> list[VariantResult]:
    source = load_source_contract()
    require(
        source.spawn_rects == MOBILE_1716_SPAWN_RECTS,
        "patcher source must define the three exact mobile 1.7.16 Holiday spawn rectangles",
    )
    require(len(source.slot_positions) == 12, "patcher source must define exactly 12 Holiday slot positions")
    require(len(source.mobile_slot_positions) == 12, "patcher source must define exactly 12 mobile Holiday slot positions")
    require(len(source.runtime_files) == 12, "patcher source must define exactly 12 Holiday runtime files")
    require(source.image_base > 0, "patcher source Holiday image base is invalid")

    results: list[VariantResult] = []
    failures: list[str] = []
    for mask in range(16):
        try:
            result = validate_variant(outputs_root, mask, exe_name, source)
        except (OSError, KeyError, IndexError, struct.error, ValidationError) as exc:
            failures.append(f"{variant_name(mask)}: {exc}")
            continue
        results.append(result)
        marker = "Holiday+" if result.holiday_enabled else "Holiday-"
        print(f"PASS {marker} {result.variant} {result.sha256}")

    if failures:
        details = "\n".join(f"- {failure}" for failure in failures)
        raise ValidationError(f"B151 Holiday matrix validation failed:\n{details}")

    positives = [result for result in results if result.holiday_enabled]
    negatives = [result for result in results if not result.holiday_enabled]
    require(len(positives) == 8, f"expected eight Holiday-positive variants, got {len(positives)}")
    require(len(negatives) == 8, f"expected eight Holiday-negative variants, got {len(negatives)}")
    hashes = {result.sha256 for result in results}
    require(len(hashes) == 16, f"expected 16 unique linked executable hashes, got {len(hashes)}")
    by_mask = {result.mask: result for result in results}
    for mask in range(16):
        if mask & 4:
            continue
        require(
            by_mask[mask].sha256 != by_mask[mask | 4].sha256,
            f"Holiday pair {variant_name(mask)} / {variant_name(mask | 4)} has the same executable hash",
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate all 16 linked B151 executables: eight exact Holiday "
            "Ornaments contracts and eight stock Holiday-negative contracts."
        )
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=DEFAULT_OUTPUTS,
        help="Workspace outputs directory containing the 16 B151 variant folders.",
    )
    parser.add_argument(
        "--exe-name",
        default=DEFAULT_EXE_NAME,
        help="Linked executable filename inside each B151 variant folder.",
    )
    args = parser.parse_args()
    try:
        results = validate_matrix(args.outputs_root.resolve(), args.exe_name)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "PASS B151 matrix: "
        f"{len(results)} variants, 8 Holiday-positive, 8 Holiday-negative"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
