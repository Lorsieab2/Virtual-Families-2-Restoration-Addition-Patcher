#!/usr/bin/env python3
"""Export an offline VF2 patch bundle from a generated build folder.

The bundle format is consumed by ``offline_vf2_patcher.py``. It contains a
manifest plus payload files, but not build outputs, caches, or extracted bulk
assets committed to git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path
from typing import Any


SOURCE_DIR = Path(__file__).resolve().parent
ROOT = SOURCE_DIR.parent
DEFAULT_BASE_PAYLOAD = SOURCE_DIR / "vanilla_runtime_payload"
DEFAULT_EXE_NAME = "Virtual Families 2.exe"
PATCHED_EXE_NAMES = (
    "Virtual Families 2 - Additive Mobile Furniture Pack.exe",
    "Virtual Families 2.exe",
)
BYTE_PATCH_CHUNK_SIZE = 256
ASSET_MODES = ("additive", "all", "full")
EXCLUDED_FULL_PAYLOAD_FILES = {
    "patch-manifest.json",
    "VF2_INTERNAL_WORKINGS_SUMMARY.txt",
}
FULL_PAYLOAD_IMAGE_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png"}
FULL_PAYLOAD_ALWAYS_INCLUDE_DIRS = {
    "OptionalVisualMods",
    "Original Virtual Families 2 Assets",
    "OptionalSongMods",
}
LOCKED_GENERATION_FRAME_COUNT = 29
LOCKED_GENERATION_CELL_WIDTH = 30
LOCKED_GENERATION_CELL_HEIGHT = 46
DEFAULT_GENERATION_LOCK_SOURCE_DIR = SOURCE_DIR / "assets" / "generation_locks"
VF3_LIVING_ROOM_BATCH_02_FILES = {
    "SofaPlaid",
    "CouchPlaid",
    "CouchFlowers",
    "CouchStriped",
    "SofaStriped",
    "FloweredLoveseat",
}
SOURCE_ONLY_PAYLOAD_DIRS = FULL_PAYLOAD_ALWAYS_INCLUDE_DIRS
OPTIONAL_SONG_SOURCE_DIR = Path("OptionalSongMods")
OPTIONAL_SONG_TARGET_DIR = Path("Sounds")
SOURCE_BACKED_OPTIONAL_SETTINGS = {
    "invisible_upgrades_graphics",
    "optional_song_mods",
    "white_birds",
    "transparent_menu_bar",
    "transparent_store_bar",
    "transparent_decor_tab",
    "custom_lorsieab2_map_images",
    "optional_visual_mod_graphics",
}

SETTINGS = [
    {
        "id": "core_executable",
        "label": "Patch game executable",
        "description": "Verifies a vanilla Virtual Families 2.exe and creates a clearly labeled modded EXE in a separate modded build folder.",
        "default": True,
        "category": "main",
    },
    {
        "id": "holiday_furniture",
        "label": "Add mobile Holiday furniture",
        "description": "Adds mobile Holiday furniture records and generated assets. These are decorative-only for now.",
        "default": True,
        "category": "main",
    },
    {
        "id": "holiday_outfits",
        "label": "Add Holiday outfits",
        "description": "Adds folder-backed Holiday outfit body values and runtime frames. Enable this for Holiday Outfit rows to appear in the expanded Outfit store.",
        "default": True,
        "category": "main",
    },
    {
        "id": "outfit_store_expansion",
        "label": "Add expanded Outfit store",
        "description": "Adds generated Outfit store rows for body values 0-49, icons, independent tray item support, and body field sync. Holiday Outfit rows require Add Holiday outfits too.",
        "default": True,
        "category": "main",
    },
    {
        "id": "mobile_furniture",
        "label": "Add additional mobile-exclusive furniture",
        "description": "Adds non-Holiday mobile furniture and supporting assets. Invisible furniture graphics are controlled by the separate Invisible Furniture settings.",
        "default": True,
        "category": "main",
    },
    {
        "id": "unused_pets",
        "label": "Add unused pets",
        "description": "Adds the unused Turtle and Hamster pets to the game.",
        "default": True,
        "category": "main",
    },
    {
        "id": "custom_couches_ldw_posters",
        "label": "Add Custom Couches and LDW Posters",
        "description": "Adds Colorful Couches and LDW Posters/Paintings mods to the game. Credit to Lorsieab2 on LDWForums.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "vf3_furniture",
        "label": "Virtual Families 3 Furniture",
        "description": "Implements furniture from Virtual Families 3, including Plaid Loveseat through Flowered Loveseat.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "invisible_furniture_visible_graphics",
        "label": "Add Invisible Furniture - Visible Graphics",
        "description": "Adds invisible furniture for decoration and gameplay purposes. Graphics use the visible base-game furniture versions. **Enable this first so you can place them in-game!**",
        "default": False,
        "category": "optional",
    },
    {
        "id": "invisible_furniture_transparent_graphics",
        "label": "Swap Invisible Furniture Graphics with Transparent Graphics",
        "description": "Once you have placed the invisible furniture how you like, enable this to make the invisible furniture fully invisible.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "vf3_tv_assets_recognition",
        "label": "Add VF3 TV assets and recognition",
        "description": "Adds VF3 TV furniture, private animation strips, and TV fmap recognition assets. Requires Patch game executable so the private TV animations are recognized.",
        "default": True,
        "category": "main",
    },
    {
        "id": "behavior_patches",
        "label": "Behavior Patches",
        "description": "Makes certain actions able to be done automatically by people, including watching the fire, relaxing in the hammock, arcade/table games, radio actions, drawing, and child-only Playhouse behavior.",
        "default": True,
        "category": "main",
    },
    {
        "id": "text_fixes",
        "label": "Text fixes",
        "description": "Misc text fixes, including the pet text fix: {name} sees their adorable pet.",
        "default": True,
        "category": "main",
    },
    {
        "id": "holiday_ornaments_collection",
        "label": "Add Holiday Ornaments collection",
        "description": "Experimental patch: adds mobile Holiday Ornament yard collectibles, collection art, and goals. May not work and might cause instability or game crashes.",
        "default": False,
        "category": "experimental",
    },
    {
        "id": "mobile_purchases",
        "label": "Add visible mobile version purchases",
        "description": "Adds visible Brokerage Account, Food Club, Health Plan, and Lucky Rock store support under Special Upgrades.",
        "default": True,
        "category": "main",
    },
    {
        "id": "settings_evict_button",
        "label": "Add Settings Evict button",
        "description": "Experimental patch: enables the mobile-style Settings Evict button. This does not work yet and may cause instability or game crashes.",
        "default": False,
        "category": "experimental",
    },
    {
        "id": "mobile_furniture_behaviors",
        "label": "Add mobile furniture behaviors",
        "description": "Experimental patch: enables added villager behavior routes for mobile furniture where implemented. May not work and might cause instability or game crashes.",
        "default": False,
        "category": "experimental",
    },
    {
        "id": "island_events",
        "label": "Add mobile-exclusive Island Events",
        "description": "Experimental patch: adds mobile-exclusive Island Event shell records. They appear but do not alter anything in the game yet, and may cause instability or game crashes.",
        "default": False,
        "category": "experimental",
    },
    {
        "id": "custom_lorsieab2_map_images",
        "label": "Lorsieab2's Custom Map Images",
        "description": "Visual only. Replaces Images/MapX*Y*.jpg with OptionalVisualMods/Custom Lorsieab2 Map Images.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "transparent_menu_bar",
        "label": "Transparent Menu Bar",
        "description": "Makes the bottom menu bars transparent. Credit to swedane on LDWForums.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "transparent_store_bar",
        "label": "Transparent Store Bar",
        "description": "Makes the bottom store bar transparent. Credit to Corylea on LDWForums.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "white_birds",
        "label": "White Birds",
        "description": "Alters the yard parrots to be white birds instead.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "store_scroll_bar",
        "label": "Store Scroll Bar",
        "description": "Adds a scroll bar to the store screen. Default off.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "invisible_upgrades_graphics",
        "label": "Invisible Upgrades Graphics",
        "description": "Optional visual mod. Replaces Images/Upgrades graphics with bundled invisible upgrade graphics. Uncheck it and click Enable/Disable Patches to restore bundled vanilla upgrade graphics.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "transparent_decor_tab",
        "label": "Transparent Decor Tab",
        "description": "Makes the purple Decor tab transparent. Credit to swedane on LDWForums.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "optional_visual_mod_graphics",
        "label": "Add loose optional visual mod graphics",
        "description": "Adds loose OptionalVisualMods image files. Furniture graphics go in Images/Furniture; future Workshop, Kitchen, and Office upgrade graphics go in Images/Upgrades; animation strips and other images go in Images.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "optional_song_mods",
        "label": "Add optional song mods",
        "description": "Adds both Virtual Families 1 and 2 songs to the game. When unchecked, click Enable/Disable Patches again to rebuild the modded folder with the original vanilla songs.",
        "default": False,
        "category": "optional",
    },
]

OPTIONAL_VISUAL_SWAP_SPECS = [
    {
        "setting": "transparent_menu_bar",
        "sources": [
            ("OptionalVisualMods/Menu-Bar/VF-2-Menu Bar/main_BG.png", "Images/main_BG.png"),
            ("OptionalVisualMods/Menu-Bar/VF-2-Menu Bar/main_BG_ws.png", "Images/main_BG_ws.png"),
        ],
        "note": "Optional transparent bottom menu bar visual swap. Credit to swedane on LDWForums.",
    },
    {
        "setting": "transparent_store_bar",
        "sources": [
            ("OptionalVisualMods/Transparent-Store-Bar/VF2_TransparentStoreBar/main_no-comm.png", "Images/main_no-comm.png"),
        ],
        "note": "Optional transparent bottom store bar visual swap. Credit to Corylea on LDWForums.",
    },
    {
        "setting": "transparent_decor_tab",
        "sources": [
            ("OptionalVisualMods/Purple-Decor-Tab/VF2_Purple_Decor_Tab/decorModeTab.png", "Images/decorModeTab.png"),
        ],
        "note": "Optional transparent purple Decor tab visual swap. Credit to swedane on LDWForums.",
    },
]

OPTIONAL_MAP_SOURCE_DIR = Path("OptionalVisualMods") / "Custom Lorsieab2 Map Images"
INVISIBLE_BASE_SOURCE_DIR = Path("OptionalVisualMods") / "Invisible Furniture - Base Graphics"
INVISIBLE_TRANSPARENT_SOURCE_DIR = Path("OptionalVisualMods") / "Invisible Furniture - Transparent"
INVISIBLE_UPGRADES_SOURCE_DIR = Path("OptionalVisualMods") / "Invisible Upgrades"
ORIGINAL_UPGRADES_SOURCE_DIR = Path("Original Virtual Families 2 Assets") / "Upgrades Original Graphics"
PATCHER_DISPLAY_NAME = "Virtual Families 2 Restoration/Addition Patcher"
MODDED_EXE_OUTPUT_TEMPLATE = "Virtual Families 2 - Modded {build_label}.exe"
MODDED_OUTPUT_FOLDER_TEMPLATE = "VF2-{build_label}-Modded"
STALE_PATCHER_LAUNCHER_NAME = "Virtual Families 2 Restoration-Addition Patcher.exe"
STALE_PATCHER_SHORTCUT_NAME = "Launch GUI.lnk"
STALE_PATCHER_SHORTCUT_STATUS_NAME = "launch_gui_shortcut.json"
TRANSPARENCY_LOG_NAME = "Transparency Log.txt"
PATCHER_ICON_PNG = "patcher_icon.png"
PATCHER_ICON_ICO = "patcher_icon.ico"
CREATOR_DISCLOSURE = "This offline patcher was created with Codex AI in collaboration with Lorsieab2."
INVALID_INSTALL_MESSAGE = (
    "No valid Virtual Families 2 Installation detected! Are you sure you downloaded it from the official website?\n\n"
    "Links:\n"
    "http://www.ldw.com/\n"
    "http://www.virtualfamilies.com/index.php"
)

HOLIDAY_FURNITURE_FILES = {
    "CandleOnHolder",
    "CandyCane",
    "ChristmasCookie",
    "ChristmasTree1",
    "ChristmasTree2",
    "Dreidel",
    "GlassOfEggnog",
    "Gnome1",
    "Gnome2",
    "Gnome3",
    "Gnome4",
    "Gnome5",
    "LargeAngel",
    "LargeStar",
    "Menorah",
    "Ornament1",
    "Ornament2",
    "Ornament3",
    "Ornament4",
    "PenguinDecoration",
    "PlateOfCookies",
    "Poinsettia",
    "PolarBearDecoration",
    "RedBow",
    "ReindeerDecoration",
    "SantaGardenDecoration",
    "SantaWallDecoration",
    "Snowman",
    "StockingLarge",
    "StockingSmall",
    "StringOfLeaves",
    "StringOfLights",
    "ThanksgivingCranberry",
    "ThanksgivingDressing",
    "ThanksgivingGravy",
    "ThanksgivingGreenBeans",
    "ThanksgivingHam",
    "ThanksgivingMashedPotatoes",
    "ThanksgivingPie",
    "ThanksgivingSouffle",
    "ThanksgivingTurkey",
    "WelcomeMat",
    "Wreath1",
    "Wreath2",
}

CUSTOM_COUCH_LDW_POSTER_FILES = {
    "LDWModernPainting4",
    "LDWModernPainting5",
    "LDWPoster1Std",
    "LDWPoster2Std",
    "LDWPoster3Std",
    "LDWPoster4Std",
    "CouchNeonPurpleStd",
    "CouchBrownColorfulStd",
    "CouchGoldColorfulStd",
    "CouchAquaStd",
    "CouchPinkColorfulStd",
    "CouchVioletStd",
    "CouchLimeGreenStd",
}

VF3_TV_FILES = {
    "VF3LargeFlatScreenTV",
    "VF3SmallFlatScreenTV",
    "FathersFavoriteTV",
    "VF3LargeFlatScreenTVAnim",
    "VF3LargeFlatScreenTVAnimEast",
    "VF3SmallFlatScreenTVAnim",
    "VF3SmallFlatScreenTVAnimEast",
    "FathersFavoriteTVAnim",
    "FathersFavoriteTVAnimEast",
}

MOBILE_PURCHASE_ICON_FILES = {
    "BrokerUpgrade_icon",
    "FoodClub_icon",
    "HealthPlan_icon",
    "LuckyRock_icon",
}

OFFICIAL_INSTALL_TOP_LEVEL_ENTRIES = [
    "Assets",
    "fmod.dll",
    "icon.bmp",
    "Images",
    "ldw.ini",
    "libjpeg-9.dll",
    "libpng16-16.dll",
    "Readme.txt",
    "SDL2.dll",
    "SDL2_image.dll",
    "Sounds",
    "uninst.exe",
    "Virtual Families 2.url",
    "zlib1.dll",
]

RUNTIME_REQUIRED_FILES = [
    "fmod.dll",
    "icon.bmp",
    "ldw.ini",
    "libjpeg-9.dll",
    "libpng16-16.dll",
    "Readme.txt",
    "SDL2.dll",
    "SDL2_image.dll",
    "uninst.exe",
    "Virtual Families 2.url",
    "zlib1.dll",
]

RUNTIME_REQUIRED_DIRS = [
    {"path": "Images", "min_files": 600},
    {"path": "Sounds", "min_files": 300},
    {"path": "Assets", "min_files": 200},
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pe_structure_fingerprint(path: Path) -> dict[str, Any] | None:
    try:
        data = path.read_bytes()
        if len(data) < 0x40 or data[:2] != b"MZ":
            return None
        pe_off = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_off + 0x18 > len(data) or data[pe_off:pe_off + 4] != b"PE\0\0":
            return None
        coff = pe_off + 4
        machine, section_count, timestamp, _symptr, _nsyms, opt_size, characteristics = struct.unpack_from(
            "<HHIIIHH",
            data,
            coff,
        )
        opt = coff + 20
        section_table = opt + opt_size
        if section_table + section_count * 40 > len(data):
            return None
        magic = struct.unpack_from("<H", data, opt)[0]
        if magic != 0x10B:
            return None
        sections = []
        for index in range(section_count):
            off = section_table + index * 40
            name = data[off:off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size, virtual_address, raw_size, raw_ptr, _reloc_ptr, _line_ptr, _reloc_count, _line_count, flags = struct.unpack_from(
                "<IIIIIIHHI",
                data,
                off + 8,
            )
            if raw_ptr + raw_size > len(data):
                return None
            raw = data[raw_ptr:raw_ptr + raw_size]
            sections.append({
                "name": name,
                "virtual_address": f"0x{virtual_address:x}",
                "virtual_size": f"0x{virtual_size:x}",
                "raw_data_pointer": f"0x{raw_ptr:x}",
                "raw_data_size": f"0x{raw_size:x}",
                "characteristics": f"0x{flags:x}",
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
        return {
            "format": "pe32-section-raw-v1",
            "pe_offset": f"0x{pe_off:x}",
            "machine": f"0x{machine:x}",
            "number_of_sections": section_count,
            "time_date_stamp": f"0x{timestamp:x}",
            "characteristics": f"0x{characteristics:x}",
            "optional_header_size": opt_size,
            "optional_magic": f"0x{magic:x}",
            "address_of_entry_point": f"0x{struct.unpack_from('<I', data, opt + 16)[0]:x}",
            "image_base": f"0x{struct.unpack_from('<I', data, opt + 28)[0]:x}",
            "section_alignment": f"0x{struct.unpack_from('<I', data, opt + 32)[0]:x}",
            "file_alignment": f"0x{struct.unpack_from('<I', data, opt + 36)[0]:x}",
            "size_of_image": f"0x{struct.unpack_from('<I', data, opt + 56)[0]:x}",
            "subsystem": f"0x{struct.unpack_from('<H', data, opt + 68)[0]:x}",
            "sections": sections,
        }
    except (OSError, struct.error):
        return None


def relative_posix(path: Path) -> str:
    return path.as_posix()


def hex_bytes(data: bytes) -> str:
    return data.hex(" ").upper()


def count_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for child in path.rglob("*") if child.is_file())


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def candidate_manifest_rel_paths(value: str) -> list[Path]:
    text = value.replace("\\", "/").strip()
    if not text:
        return []
    try:
        path = Path(text)
    except ValueError:
        return []

    candidates: list[str] = []
    if path.is_absolute():
        parts = path.parts
        lowered = [part.lower() for part in parts]
        for root_name in ("images", "assets"):
            if root_name not in lowered:
                continue
            index = lowered.index(root_name)
            candidates.append("/".join(parts[index:]))
    else:
        if text.startswith(("Images/", "Assets/")):
            candidates.append(text)
        elif text.startswith((
            "Furniture/",
            "VillagerBodies/",
            "VillagerDetailBodies/",
            "HolidayOutfits/",
            "CollectionOrnaments/",
        )):
            candidates.append("Images/" + text)
        elif "/" not in text and text.lower().endswith((".png", ".jpg", ".bmp")):
            candidates.append("Images/" + text)
        elif "/" not in text and text.lower().endswith(".fmap"):
            candidates.append("Assets/" + text)

    result = []
    for candidate in candidates:
        rel = Path(candidate)
        if rel.parts and rel.parts[0] in {"Images", "Assets"}:
            result.append(rel)
    return result


def collect_manifest_asset_paths(data: Any) -> set[Path]:
    paths: set[Path] = set()
    if isinstance(data, dict):
        for value in data.values():
            paths.update(collect_manifest_asset_paths(value))
    elif isinstance(data, list):
        for value in data:
            paths.update(collect_manifest_asset_paths(value))
    elif isinstance(data, str):
        paths.update(candidate_manifest_rel_paths(data))
    return paths


def find_patched_exe(build_dir: Path, explicit: str | None) -> Path:
    if explicit:
        path = build_dir / explicit
        if not path.is_file():
            raise FileNotFoundError(f"Patched EXE not found: {path}")
        return path
    for name in PATCHED_EXE_NAMES:
        path = build_dir / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"No patched EXE found in {build_dir}")


def target_file_record(vanilla_exe: Path, target_exe_name: str, accepted_exes: list[Path] | None = None) -> dict[str, Any]:
    record = {
        "path": target_exe_name,
        "note": "Verified vanilla VF2 PC executable by accepted PE layout, not by fixed SHA-256.",
    }
    pe_structures = []
    for exe in [vanilla_exe, *(accepted_exes or [])]:
        pe_structure = pe_structure_fingerprint(exe)
        if pe_structure is not None:
            pe_structures.append(pe_structure)
    if pe_structures:
        record["pe_structures"] = pe_structures
    else:
        record["sha256"] = sha256_file(vanilla_exe)
        record["size"] = vanilla_exe.stat().st_size
    return record


def build_byte_patches(vanilla_exe: Path, patched_exe: Path, target_exe_name: str) -> list[dict[str, Any]]:
    original = vanilla_exe.read_bytes()
    replacement = patched_exe.read_bytes()
    if len(original) != len(replacement):
        raise ValueError(
            f"Cannot export simple byte patches when EXE sizes differ: "
            f"{len(original)} != {len(replacement)}"
        )

    patches: list[dict[str, Any]] = []
    start: int | None = None
    old_chunk = bytearray()
    new_chunk = bytearray()

    def flush() -> None:
        nonlocal start, old_chunk, new_chunk
        if start is None:
            return
        patches.append(
            {
                "file_path": target_exe_name,
                "offset": f"0x{start:X}",
                "expected_original_bytes": hex_bytes(bytes(old_chunk)),
                "replacement_bytes": hex_bytes(bytes(new_chunk)),
                "requires": ["core_native_patch"],
                "note": f"Generated EXE byte diff chunk at 0x{start:X}.",
            }
        )
        start = None
        old_chunk = bytearray()
        new_chunk = bytearray()

    for offset, (old, new) in enumerate(zip(original, replacement, strict=True)):
        if old == new:
            flush()
            continue
        if start is None:
            start = offset
        old_chunk.append(old)
        new_chunk.append(new)
        if len(old_chunk) >= BYTE_PATCH_CHUNK_SIZE:
            flush()
    flush()
    return patches


def native_patch_status(status: str, **extra: Any) -> dict[str, Any]:
    data = {"status": status}
    data.update(extra)
    return data


def setting_for_native_source(path_parts: list[str]) -> str:
    path_text = "/".join(path_parts)
    if "pet_store" in path_text or "/pets/" in path_text or "gPet" in path_text:
        return "unused_pets"
    if "settings_menu/evict" in path_text:
        return "settings_evict_button"
    if "HolidayOrnament" in path_text or "holiday_ornament" in path_text:
        return "holiday_ornaments_collection"
    if "IslandEvents" in path_text:
        return "island_events"
    if "vf3_tv" in path_text or "VF3" in path_text:
        return "vf3_tv_assets_recognition"
    return "core_native_patch"


def collect_native_patch_sources(data: Any, path_parts: list[str] | None = None) -> list[dict[str, Any]]:
    if path_parts is None:
        path_parts = []
    records: list[dict[str, Any]] = []
    if isinstance(data, dict):
        has_explicit_bytes = all(
            key in data
            for key in ("offset", "expected_original_bytes", "replacement_bytes")
        )
        if has_explicit_bytes:
            records.append(
                {
                    "source_path": "/".join(path_parts),
                    "offset": str(data["offset"]),
                    "expected_original_bytes": str(data["expected_original_bytes"]),
                    "replacement_bytes": str(data["replacement_bytes"]),
                    "requires": [setting_for_native_source(path_parts)],
                    "note": str(data.get("note", "")).strip(),
                    "scope": "object_relative",
                    "apply_status": "not_file_offset",
                    "next_step": "Translate object/function-relative offset to final EXE file offset before moving into patches[].",
                }
            )
        for key, value in data.items():
            records.extend(collect_native_patch_sources(value, [*path_parts, str(key)]))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            records.extend(collect_native_patch_sources(value, [*path_parts, str(index)]))
    return records


def setting_for_asset(rel_path: Path) -> str:
    text = relative_posix(rel_path)
    stem = rel_path.stem
    if stem.endswith(".png"):
        stem = stem[:-4]
    parts = rel_path.parts
    if text.startswith("OptionalVisualMods/Custom Lorsieab2 Map Images/"):
        return "custom_lorsieab2_map_images"
    if text.startswith("OptionalVisualMods/Menu-Bar/"):
        return "transparent_menu_bar"
    if text.startswith("OptionalVisualMods/Transparent-Store-Bar/"):
        return "transparent_store_bar"
    if text in {"OptionalVisualMods/bird.png", "OptionalVisualMods/bird_shadow.png"}:
        return "white_birds"
    if text.startswith("OptionalVisualMods/Purple-Decor-Tab/"):
        return "transparent_decor_tab"
    if text.startswith("OptionalVisualMods/Invisible Furniture - Base Graphics/"):
        return "invisible_furniture_visible_graphics"
    if text.startswith("OptionalVisualMods/Invisible Furniture - Transparent/"):
        return "invisible_furniture_transparent_graphics"
    if text.startswith("OptionalVisualMods/Invisible Furniture Backups/"):
        return "invisible_furniture_transparent_graphics"
    if text.startswith("OptionalVisualMods/"):
        return "optional_visual_mod_graphics"
    if text.startswith("OptionalSongMods/"):
        return "optional_song_mods"
    if (
        text.startswith("Images/VillagerBodies/")
        or text.startswith("Images/VillagerDetailBodies/")
        or text.startswith("Images/HolidayOutfits/")
    ):
        return "holiday_outfits"
    if stem in VF3_TV_FILES or text.startswith("Images/VF3TVAnimations/"):
        return "vf3_tv_assets_recognition"
    if text.startswith("Images/GenerationLocks/") or text == "Images/locked.png":
        return "core_executable"
    if text.startswith("Images/CollectionOrnaments/") or "CollectionOrnament" in stem or stem == "collectables_small":
        return "holiday_ornaments_collection"
    if text in {
        "Images/familytree_scrollknob_btm.png",
        "Images/familytree_scrollknob_mid.png",
        "Images/familytree_scrollknob_top.png",
        "Images/getMoreCoinsScrollShadow.png",
        "Images/ScrollingStoreItemBox.png",
    }:
        return "store_scroll_bar"
    if len(parts) >= 3 and parts[0] == "Images" and parts[1] == "Furniture" and stem in HOLIDAY_FURNITURE_FILES:
        return "holiday_furniture"
    if len(parts) >= 2 and parts[0] == "Assets" and stem in HOLIDAY_FURNITURE_FILES:
        return "holiday_furniture"
    if len(parts) >= 3 and parts[0] == "Images" and parts[1] == "Furniture" and stem in CUSTOM_COUCH_LDW_POSTER_FILES:
        return "custom_couches_ldw_posters"
    if len(parts) >= 2 and parts[0] == "Assets" and stem in CUSTOM_COUCH_LDW_POSTER_FILES:
        return "custom_couches_ldw_posters"
    if len(parts) >= 3 and parts[0] == "Images" and parts[1] == "Furniture" and stem in VF3_LIVING_ROOM_BATCH_02_FILES:
        return "vf3_furniture"
    if len(parts) >= 2 and parts[0] == "Assets" and stem in VF3_LIVING_ROOM_BATCH_02_FILES:
        return "vf3_furniture"
    if is_invisible_runtime_asset(rel_path):
        return "invisible_furniture_visible_graphics"
    if stem in MOBILE_PURCHASE_ICON_FILES:
        return "mobile_purchases"
    if text.startswith("Images/OutfitStoreIcons/") or stem.startswith(("female_", "male_")):
        return "outfit_store_expansion"
    if parts and parts[0] in {"Images", "Assets"}:
        return "mobile_furniture"
    return "core_assets"


def asset_requires_for_setting(setting: str) -> list[str]:
    if setting in {"vf3_tv_assets_recognition", "vf3_furniture", "behavior_patches"}:
        return ["core_executable", setting]
    return [setting]


def is_invisible_furniture_image(rel_path: Path) -> bool:
    parts = rel_path.parts
    return len(parts) >= 3 and parts[0] == "Images" and parts[1] == "Furniture" and rel_path.stem.startswith("Invisible")


def is_invisible_runtime_asset(rel_path: Path) -> bool:
    parts = rel_path.parts
    if is_invisible_furniture_image(rel_path):
        return True
    stem = rel_path.stem
    if stem.endswith(".png"):
        stem = stem[:-4]
    return len(parts) >= 2 and parts[0] == "Assets" and stem.startswith("Invisible")


def is_full_payload_candidate(rel_path: Path) -> bool:
    if not rel_path.parts:
        return False
    top = rel_path.parts[0]
    if "__MACOSX" in rel_path.parts or rel_path.name == ".DS_Store" or rel_path.name.startswith("._"):
        return False
    if top == "OptionalVisualMods":
        return rel_path.suffix.lower() in FULL_PAYLOAD_IMAGE_EXTENSIONS
    if top == "OptionalSongMods":
        return rel_path.suffix.lower() == ".ogg"
    if top == "Original Virtual Families 2 Assets":
        return True
    if top == "Images" and rel_path.suffix.lower() in FULL_PAYLOAD_IMAGE_EXTENSIONS:
        return True
    if top == "Assets" and rel_path.suffix.lower() == ".fmap":
        return True
    return False


def iter_candidate_assets(build_dir: Path, manifest_data: dict[str, Any], asset_mode: str) -> list[Path]:
    if asset_mode == "full":
        paths: list[Path] = []
        patched_exe_candidates = {name.lower() for name in PATCHED_EXE_NAMES}
        for path in build_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(build_dir)
            rel_text = relative_posix(rel)
            if rel_text in EXCLUDED_FULL_PAYLOAD_FILES:
                continue
            if len(rel.parts) == 1 and rel.name.lower() in patched_exe_candidates:
                continue
            if not is_full_payload_candidate(rel):
                continue
            paths.append(path)
        return sorted(paths)

    roots = [build_dir / "Images", build_dir / "Assets"]
    allowed_paths: set[Path] | None = None
    if asset_mode == "additive":
        allowed_paths = {
            rel
            for rel in collect_manifest_asset_paths(manifest_data)
            if (build_dir / rel).is_file()
        }

    paths: list[Path] = []
    for root in roots:
        if root.is_dir():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if allowed_paths is not None and path.relative_to(build_dir) not in allowed_paths:
                    continue
                paths.append(path)
    return sorted(paths)


def export_asset_payloads(
    build_dir: Path,
    base_payload: Path,
    bundle_dir: Path,
    manifest_data: dict[str, Any],
    asset_mode: str,
    build_label: str,
) -> list[dict[str, Any]]:
    payload_root = bundle_dir / "payload"
    asset_patches: list[dict[str, Any]] = []
    for source in iter_candidate_assets(build_dir, manifest_data, asset_mode):
        rel = source.relative_to(build_dir)
        base = base_payload / rel
        source_sha = sha256_file(source)
        source_size = source.stat().st_size
        if base.is_file() and sha256_file(base) == source_sha:
            continue

        payload_target = payload_root / rel
        payload_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, payload_target)
        if rel.parts and rel.parts[0] in SOURCE_ONLY_PAYLOAD_DIRS:
            continue

        record = {
            "file_path": relative_posix(rel),
            "source_path": relative_posix(Path("payload") / rel),
            "source_sha256": source_sha,
            "source_size": source_size,
            "requires": asset_requires_for_setting(setting_for_asset(rel)),
            "note": f"Generated asset payload for {relative_posix(rel)}.",
        }
        invisible_base_build_source = build_dir / INVISIBLE_BASE_SOURCE_DIR / rel.name
        if is_invisible_furniture_image(rel) and invisible_base_build_source.is_file():
            base_source_rel = Path("payload") / INVISIBLE_BASE_SOURCE_DIR / rel.name
            record["source_path"] = relative_posix(base_source_rel)
            record["source_sha256"] = sha256_file(invisible_base_build_source)
            record["source_size"] = invisible_base_build_source.stat().st_size
            record["requires"] = ["invisible_furniture_visible_graphics"]
            record["note"] = (
                "Invisible Furniture visible-graphics placement payload. Enable this first so the furniture can be placed."
            )
        if asset_mode == "full":
            record["overwrite_existing"] = True
            record["note"] = f"Full {build_label} beta folder payload for {relative_posix(rel)}."
            if is_invisible_furniture_image(rel) and record["requires"] == ["invisible_furniture_visible_graphics"]:
                record["note"] = (
                    f"Full {build_label} beta folder Invisible Furniture visible-graphics payload. "
                    "Enable this first so the furniture can be placed."
                )
        elif base.is_file():
            record["expected_target_sha256"] = sha256_file(base)
            record["expected_target_size"] = base.stat().st_size
            record["overwrite_existing"] = True
        asset_patches.append(record)
    return asset_patches


def generation_lock_source_paths(source_dir: Path) -> dict[int, Path]:
    return {
        generation: source_dir / f"lock_{generation:02d}.png"
        for generation in range(2, LOCKED_GENERATION_FRAME_COUNT + 2)
    }


def find_generation_lock_source_dir(build_dir: Path, override_dir: Path | None = None) -> Path:
    candidates = [
        override_dir,
        build_dir / "Images" / "GenerationLocks",
        DEFAULT_GENERATION_LOCK_SOURCE_DIR,
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        paths = generation_lock_source_paths(candidate)
        if all(path.is_file() for path in paths.values()):
            return candidate
    checked = [str(candidate) for candidate in candidates if candidate is not None]
    raise RuntimeError(
        "Could not find complete generation lock art lock_02.png through lock_30.png. "
        f"Checked: {checked}"
    )


def generation_lock_asset_patches(
    build_dir: Path,
    bundle_dir: Path,
    source_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Force the standalone generation-lock art required by the store hook."""
    source_strip = build_dir / "Images" / "locked.png"
    if not source_strip.is_file():
        return []

    payload_root = bundle_dir / "payload"
    records: list[dict[str, Any]] = []

    locked_target = payload_root / "Images" / "locked.png"
    locked_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_strip, locked_target)
    records.append({
        "file_path": "Images/locked.png",
        "source_path": "payload/Images/locked.png",
        "source_sha256": sha256_file(locked_target),
        "source_size": locked_target.stat().st_size,
        "requires": ["core_executable"],
        "overwrite_existing": True,
        "note": "Generation-lock strip used by the core store lock draw hook.",
    })

    output_dir = payload_root / "Images" / "GenerationLocks"
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_source_dir = find_generation_lock_source_dir(build_dir, source_dir)
    for generation, source in generation_lock_source_paths(resolved_source_dir).items():
        target = output_dir / f"lock_{generation:02d}.png"
        shutil.copy2(source, target)
        records.append({
            "file_path": f"Images/GenerationLocks/lock_{generation:02d}.png",
            "source_path": f"payload/Images/GenerationLocks/lock_{generation:02d}.png",
            "source_sha256": sha256_file(target),
            "source_size": target.stat().st_size,
            "requires": ["core_executable"],
            "overwrite_existing": True,
            "note": (
                "Standalone generation-lock icon required by the core store lock draw hook. "
                f"Uses the explicit lock_{generation:02d}.png frame from {relative_posix(resolved_source_dir)}."
            ),
        })

    return records


def optional_song_asset_patches(
    bundle_dir: Path,
    base_payload: Path,
    source_dir: Path | None = None,
) -> list[dict[str, Any]]:
    payload_root = bundle_dir / "payload"
    payload_song_dir = payload_root / OPTIONAL_SONG_SOURCE_DIR
    if source_dir is not None:
        if not source_dir.is_dir():
            raise ValueError(f"Optional song mods directory does not exist: {source_dir}")
        payload_song_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_dir.glob("*.ogg")):
            if source.is_file():
                shutil.copy2(source, payload_song_dir / source.name)

    records: list[dict[str, Any]] = []
    if not payload_song_dir.is_dir():
        return records

    for source in sorted(payload_song_dir.glob("*.ogg")):
        target_rel = OPTIONAL_SONG_TARGET_DIR / source.name
        source_rel = source.relative_to(bundle_dir)
        record: dict[str, Any] = {
            "file_path": relative_posix(target_rel),
            "source_path": relative_posix(source_rel),
            "source_sha256": sha256_file(source),
            "source_size": source.stat().st_size,
            "overwrite_existing": True,
            "requires": ["optional_song_mods"],
            "note": (
                "Optional song mod swap. Enable this setting to copy the song into Sounds; "
                "uncheck it and click Enable/Disable Patches to rebuild the modded folder with vanilla songs."
            ),
        }
        base_target = base_payload / target_rel
        if base_target.is_file():
            record["expected_target_sha256"] = sha256_file(base_target)
            record["expected_target_size"] = base_target.stat().st_size
        restore_source = payload_root / "Original Virtual Families 2 Assets" / "originalsounds" / source.name
        if restore_source.is_file():
            record["restore_source_path"] = relative_posix(restore_source.relative_to(bundle_dir))
            record["restore_source_sha256"] = sha256_file(restore_source)
            record["restore_source_size"] = restore_source.stat().st_size
        records.append(record)
    return records


def copy_optional_png_folder(source_dir: Path | None, target_dir: Path) -> None:
    if source_dir is None:
        return
    if not source_dir.is_dir():
        raise ValueError(f"Optional graphics directory does not exist: {source_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_dir.glob("*.png")):
        if source.is_file():
            shutil.copy2(source, target_dir / source.name)


def invisible_upgrades_asset_patches(
    bundle_dir: Path,
    invisible_source_dir: Path | None = None,
    original_source_dir: Path | None = None,
) -> list[dict[str, Any]]:
    payload_root = bundle_dir / "payload"
    payload_invisible_dir = payload_root / INVISIBLE_UPGRADES_SOURCE_DIR
    payload_original_dir = payload_root / ORIGINAL_UPGRADES_SOURCE_DIR
    copy_optional_png_folder(invisible_source_dir, payload_invisible_dir)
    copy_optional_png_folder(original_source_dir, payload_original_dir)

    if not payload_invisible_dir.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for source in sorted(payload_invisible_dir.glob("*.png")):
        target_rel = Path("Images") / "Upgrades" / source.name
        record: dict[str, Any] = {
            "file_path": relative_posix(target_rel),
            "source_path": relative_posix(source.relative_to(bundle_dir)),
            "source_sha256": sha256_file(source),
            "source_size": source.stat().st_size,
            "overwrite_existing": True,
            "requires": ["invisible_upgrades_graphics"],
            "note": (
                "Optional Invisible Upgrades visual swap. Enable this setting to replace the matching "
                "Images/Upgrades graphic with the bundled invisible version; uncheck it and click "
                "Enable/Disable Patches to rebuild the modded folder with vanilla upgrade graphics."
            ),
        }
        original = payload_original_dir / source.name
        if original.is_file():
            record["restore_source_path"] = relative_posix(original.relative_to(bundle_dir))
            record["restore_source_sha256"] = sha256_file(original)
            record["restore_source_size"] = original.stat().st_size
        records.append(record)
    return records


def loose_optional_visual_target(source: Path) -> Path:
    name = source.name
    stem_lower = source.stem.lower()
    path_text = relative_posix(source).lower()
    if any(key in path_text for key in ("workshop", "kitchen", "office", "upgrade")):
        return Path("Images") / "Upgrades" / name
    if stem_lower.endswith("std") or "furniture" in path_text:
        return Path("Images") / "Furniture" / name
    return Path("Images") / name


def optional_visual_asset_patches(bundle_dir: Path) -> list[dict[str, Any]]:
    payload_root = bundle_dir / "payload"
    records: list[dict[str, Any]] = []

    for source in sorted((payload_root / OPTIONAL_MAP_SOURCE_DIR).glob("MapX*Y*.jpg")):
        if not source.is_file():
            continue
        target_rel = Path("Images") / source.name
        source_rel = source.relative_to(bundle_dir)
        records.append(
            {
                "file_path": relative_posix(target_rel),
                "source_path": relative_posix(source_rel),
                "source_sha256": sha256_file(source),
                "source_size": source.stat().st_size,
                "overwrite_existing": True,
                "requires": ["custom_lorsieab2_map_images"],
                "note": "Optional visual-only custom map image swap by Lorsieab2.",
            }
        )

    for spec in OPTIONAL_VISUAL_SWAP_SPECS:
        for source_text, target_text in spec["sources"]:
            source = payload_root / Path(source_text)
            if not source.is_file():
                continue
            records.append(
                {
                    "file_path": target_text,
                    "source_path": relative_posix(source.relative_to(bundle_dir)),
                    "source_sha256": sha256_file(source),
                    "source_size": source.stat().st_size,
                    "overwrite_existing": True,
                    "requires": [str(spec["setting"])],
                    "note": str(spec["note"]),
                }
            )
    optional_root = payload_root / "OptionalVisualMods"
    for source in sorted(optional_root.glob("*")):
        if not source.is_file() or source.suffix.lower() not in FULL_PAYLOAD_IMAGE_EXTENSIONS:
            continue
        target_rel = loose_optional_visual_target(source.relative_to(optional_root))
        setting = setting_for_asset(source.relative_to(payload_root))
        records.append(
            {
                "file_path": relative_posix(target_rel),
                "source_path": relative_posix(source.relative_to(bundle_dir)),
                "source_sha256": sha256_file(source),
                "source_size": source.stat().st_size,
                "overwrite_existing": True,
                "requires": asset_requires_for_setting(setting),
                "note": (
                    "Named optional visual swap."
                    if setting != "optional_visual_mod_graphics"
                    else (
                        "Loose OptionalVisualMods image swap. Furniture graphics target Images/Furniture; "
                        "future room-upgrade graphics target Images/Upgrades; other images target Images."
                    )
                ),
            }
        )
    for source in sorted((payload_root / INVISIBLE_TRANSPARENT_SOURCE_DIR).glob("Invisible*.png")):
        if not source.is_file():
            continue
        target_rel = Path("Images") / "Furniture" / source.name
        records.append(
            {
                "file_path": relative_posix(target_rel),
                "source_path": relative_posix(source.relative_to(bundle_dir)),
                "source_sha256": sha256_file(source),
                "source_size": source.stat().st_size,
                "overwrite_existing": True,
                "requires": [
                    "invisible_furniture_visible_graphics",
                    "invisible_furniture_transparent_graphics",
                ],
                "note": "Optional swap from visible Invisible Furniture graphics to fully transparent graphics.",
            }
        )
    return records


def validate_bundle_asset_sources(bundle_dir: Path, asset_patches: list[dict[str, Any]]) -> None:
    bundle_root = bundle_dir.resolve()
    for index, record in enumerate(asset_patches):
        for key in ("source_path", "restore_source_path"):
            rel_text = record.get(key)
            if not rel_text:
                continue
            rel_path = Path(str(rel_text))
            if rel_path.is_absolute():
                raise ValueError(f"asset patch #{index} {key} must be bundle-relative, got {rel_text!r}")
            resolved = (bundle_root / rel_path).resolve()
            if resolved != bundle_root and bundle_root not in resolved.parents:
                raise ValueError(f"asset patch #{index} {key} escapes the patcher bundle: {rel_text!r}")
            if not resolved.is_file():
                raise FileNotFoundError(f"asset patch #{index} {key} does not exist in the patcher bundle: {rel_text!r}")


def modded_exe_output_name(build_label: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", build_label).strip("._") or "Modded"
    return MODDED_EXE_OUTPUT_TEMPLATE.format(build_label=label)


def modded_output_folder_name(build_label: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", build_label).strip("._") or "Modded"
    return MODDED_OUTPUT_FOLDER_TEMPLATE.format(build_label=label)


def export_exe_replacement_payload(
    *,
    bundle_dir: Path,
    patched_exe: Path,
    vanilla_exe: Path,
    accepted_exes: list[Path] | None,
    target_exe_name: str,
    build_label: str,
) -> dict[str, Any]:
    output_exe_name = modded_exe_output_name(build_label)
    payload_rel = Path("payload") / output_exe_name
    payload_target = bundle_dir / payload_rel
    payload_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(patched_exe, payload_target)
    pe_structures = []
    for exe in [vanilla_exe, *(accepted_exes or [])]:
        pe_structure = pe_structure_fingerprint(exe)
        if pe_structure is not None:
            pe_structures.append(pe_structure)
    record = {
        "file_path": target_exe_name,
        "output_file_path": output_exe_name,
        "source_path": relative_posix(payload_rel),
        "source_sha256": sha256_file(payload_target),
        "source_size": payload_target.stat().st_size,
        "overwrite_existing": True,
        "requires": ["core_executable"],
        "note": f"Create clearly named modded {build_label} executable after verifying the vanilla Virtual Families 2.exe.",
    }
    if pe_structures:
        record["expected_target_pe_structures"] = pe_structures
    else:
        record["expected_target_sha256"] = sha256_file(vanilla_exe)
        record["expected_target_size"] = vanilla_exe.stat().st_size
    return record


def default_settings(
    include_byte_patches: bool,
    include_exe_replacement: bool,
    available_settings: set[str] | None = None,
) -> list[dict[str, Any]]:
    settings = [row for row in SETTINGS if include_exe_replacement or row["id"] != "core_executable"]
    if available_settings is not None:
        settings = [
            row
            for row in settings
            if row["id"] not in SOURCE_BACKED_OPTIONAL_SETTINGS or row["id"] in available_settings
        ]
    if include_byte_patches:
        settings.insert(
            0,
            {
                "id": "core_native_patch",
                "label": "Apply core native code/table patches",
                "description": "Applies byte records generated by diffing the vanilla EXE against the patched build EXE.",
                "default": True,
                "category": "main",
            },
        )
    settings.append(
        {
            "id": "core_assets",
            "label": "Copy required support files and uncategorized generated assets",
            "description": "Copies generated Images/Assets payloads that are not tied to a narrower feature toggle. Source-only payload folders are read-only/copy-only and are not copied wholesale into the game.",
            "default": True,
            "category": "main",
        }
    )
    return settings


def infer_build_label(bundle_dir: Path, manifest_name: str | None = None) -> str:
    for text in (manifest_name or "", bundle_dir.name):
        match = re.search(r"\bB\d+\b", text, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()
    return "Current"


def copy_patcher_icon_assets(bundle_dir: Path) -> list[str]:
    copied = []
    source_dir = SOURCE_DIR / "assets"
    for name in (PATCHER_ICON_PNG, PATCHER_ICON_ICO):
        source = source_dir / name
        if source.is_file():
            shutil.copy2(source, bundle_dir / name)
            copied.append(name)
    return copied


def write_bundle_runner_files(bundle_dir: Path, build_label: str) -> list[str]:
    icon_files = copy_patcher_icon_assets(bundle_dir)
    shutil.copy2(SOURCE_DIR / "offline_vf2_patcher.py", bundle_dir / "offline_vf2_patcher.py")
    shutil.copy2(SOURCE_DIR / "offline_vf2_patcher_gui.py", bundle_dir / "offline_vf2_patcher_gui.py")
    apply_name = f"Apply_{build_label}_Patcher.bat"
    readme_name = f"README-{build_label}-PATCHER.txt"
    (bundle_dir / apply_name).write_text(
        f'''@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
echo.
echo {PATCHER_DISPLAY_NAME} - {build_label}
echo This creates a separate modded game folder next to the vanilla folder.
echo Enter or drag the original "Virtual Families 2.exe" here.
set /p VF2_EXE=EXE path: 
set "VF2_EXE=%VF2_EXE:"=%"
if not exist "%VF2_EXE%" (
  echo File not found: "%VF2_EXE%"
  pause
  exit /b 1
)
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%SCRIPT_DIR%offline_vf2_patcher.py" apply --exe "%VF2_EXE%" --manifest "%SCRIPT_DIR%manifest.json"
) else (
  python "%SCRIPT_DIR%offline_vf2_patcher.py" apply --exe "%VF2_EXE%" --manifest "%SCRIPT_DIR%manifest.json"
)
echo.
pause
''',
        encoding="ascii",
        newline="\r\n",
    )
    (bundle_dir / "Launch_GUI.bat").write_text(
        r'''@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%SCRIPT_DIR%offline_vf2_patcher_gui.py" "%SCRIPT_DIR%manifest.json"
) else (
  python "%SCRIPT_DIR%offline_vf2_patcher_gui.py" "%SCRIPT_DIR%manifest.json"
)
''',
        encoding="ascii",
        newline="\r\n",
    )
    (bundle_dir / readme_name).write_text(
        f"""{PATCHER_DISPLAY_NAME} - {build_label}

{CREATOR_DISCLOSURE}

Use {apply_name} and enter or drag the original Virtual Families 2.exe, or run
Launch_GUI.bat for the GUI. This package does not ship a prebuilt Windows
shortcut because .lnk targets are path-specific and can break after ZIP
extraction.

The patcher validates that the selected folder is an official Virtual Families
2 install before it creates backups or writes any modded output. It then
refreshes or creates a clearly labeled modded game folder next to the vanilla
folder, writes a backup under the modded folder in .vf2_patch_backups, and
recreates the {build_label} beta support folder structure using only enabled
patch records.

Click Enable/Disable Patches after changing checkboxes. Unchecked patches are
restored by rebuilding the modded folder from the vanilla install and applying
only the checked patches. Payload files are read-only/copy-only during apply.

Dry Run / Validate Only validates that the patcher's working. It checks whether
the selected VF2 folder looks right, whether the EXE is the expected official
one, whether all patch data matches, and whether the needed payload files are
intact. It does not actually change or write files. If you do not choose a
custom log path, dry-run and pre-write failure logs are written next to
manifest.json so the vanilla game folder stays untouched.
""",
        encoding="ascii",
        newline="\r\n",
    )
    (bundle_dir / "How to Use.txt").write_text(
        f"""{PATCHER_DISPLAY_NAME} - How to Use
{'=' * (len(PATCHER_DISPLAY_NAME) + len(' - How to Use'))}

ELI5 version:
This patcher makes a separate modded copy of your official Virtual Families 2
folder. It checks that your original game folder looks correct before it
changes anything.

1. Download and install the official Virtual Families 2 PC version.

2. Unzip this patcher package anywhere you like.

3. Run:
   Launch_GUI.bat

   The BAT file is the supported launcher. It resolves files relative to the
   folder where you extracted this ZIP.

4. The patcher should auto-load manifest.json.

5. Select your vanilla Virtual Families 2 install folder. It should be the
   folder that contains Virtual Families 2.exe, Images, Sounds, Assets, and the
   required DLL files.

6. Review the optional patch checkboxes.

7. Optional but recommended: click Dry Run (Validate Only).
   Dry Run validates that the patcher's working. It does not actually
   change/write files.

8. Click Enable/Disable Patches. If you uncheck a patch later, click this
   button again to rebuild the modded folder from vanilla with that patch
   disabled.

9. The patcher creates or refreshes a separate modded folder next to your
   vanilla game folder. Your original game folder and original saves are left
   alone.

10. Run the clearly named modded EXE inside the new modded folder.

Existing saves:
The modded game uses its own save folder under Documents/LDW using the modded
EXE name. To play existing saves in the modded game, copy the contents of your
original Documents/LDW/Virtual Families 2 save folder into the modded save
folder shown after patching.

If no valid install is detected:
Make sure you selected the official Virtual Families 2 install folder, not a
partial folder or the patcher folder itself.

Have fun! -Lorsieab2 :)
""",
        encoding="ascii",
        newline="\r\n",
    )
    files = [
        "offline_vf2_patcher.py",
        "offline_vf2_patcher_gui.py",
        *icon_files,
        apply_name,
        "Launch_GUI.bat",
        readme_name,
        "How to Use.txt",
    ]
    return files


def clear_generated_runner_files(bundle_dir: Path) -> None:
    for pattern in (
        "Apply_*_Patcher.bat",
        "README-*-PATCHER.txt",
        "How to Use.txt",
        "Launch_GUI.bat",
        STALE_PATCHER_SHORTCUT_NAME,
        STALE_PATCHER_SHORTCUT_STATUS_NAME,
        STALE_PATCHER_LAUNCHER_NAME,
        PATCHER_ICON_PNG,
        PATCHER_ICON_ICO,
        "vf2_patcher_launcher.cs",
        "patcher_launcher_build.json",
        "patch_dry_run_log.json",
        "patch_error_log.json",
        TRANSPARENCY_LOG_NAME,
        "offline_vf2_patcher.py",
        "offline_vf2_patcher_gui.py",
    ):
        for path in bundle_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def write_transparency_log(bundle_dir: Path, manifest: dict[str, Any]) -> str:
    summary = manifest.get("export_summary", {})
    source_build = manifest.get("source_build", {})
    settings = manifest.get("settings", [])
    payload_root = bundle_dir / "payload"
    payload_files = sorted(path for path in payload_root.rglob("*") if path.is_file()) if payload_root.is_dir() else []
    payload_top_counts: dict[str, int] = {}
    for path in payload_files:
        rel = path.relative_to(payload_root)
        key = rel.parts[0] if len(rel.parts) > 1 else "(root files)"
        payload_top_counts[key] = payload_top_counts.get(key, 0) + 1
    lines = [
        f"{PATCHER_DISPLAY_NAME} Transparency Log",
        "=" * (len(PATCHER_DISPLAY_NAME) + len(" Transparency Log")),
        "",
        f"Manifest name: {manifest.get('name')}",
        f"Generated bundle folder: {bundle_dir}",
        f"Source build folder: {source_build.get('build_dir')}",
        f"Source build manifest: {source_build.get('build_manifest')}",
        f"Patched EXE source: {source_build.get('patched_exe')}",
        "",
        "Creation disclosure",
        "-------------------",
        CREATOR_DISCLOSURE,
        "",
        "What this patcher does",
        "----------------------",
        "- Verifies the selected vanilla Virtual Families 2 folder by official install shape and accepts any executable in that folder matching a known VF2 PE layout.",
        "- Applies active patch records from manifest.json only when their required settings are enabled.",
        "- Writes per-record validation/apply progress to the GUI/console and to the JSON patch log.",
        "- Creates a separate clearly labeled modded output folder by default.",
        "- Rebuilds or refreshes recognized modded output folders from the vanilla install before applying checked records, so unchecked patches are removed on the next Enable/Disable Patches run.",
        "- Creates backups before writing changed files in the modded output folder.",
        "- Writes machine-readable success/failure logs.",
        "- Dry Run / Validate Only validates that the patcher's working: it checks the install, EXE, patch records, and payload hashes, then stops before creating backups, creating the modded output folder, or changing/writing files. Default dry-run and pre-write failure logs are written next to manifest.json, not into the vanilla game folder.",
        "- Launch_GUI.bat starts the GUI with adjacent manifest.json. Prebuilt .lnk shortcuts are not shipped because they are path-specific and can break after ZIP extraction.",
        "- Payload files are read-only/copy-only during apply. The patcher reads payload sources and copies selected files into the separate modded output folder; it never writes back into payload/ during patching.",
        "- Provides a restore command for backups created by this patcher.",
        "",
        "What this patcher does not do",
        "-----------------------------",
        "- Does not inject code into a running game.",
        "- Does not edit process memory.",
        "- Does not use obfuscation, packers, or admin-only install locations.",
        "- Does not alter the original save folder unless the user manually copies saves.",
        "",
        "Payload folder",
        "--------------",
        "- payload/ is the patch bundle's local stash of files that may be copied into the separate modded output folder.",
        "- The patcher does not apply payload/ blindly. Each copied file must be referenced by an active asset_patches record in manifest.json.",
        "- Before copying a payload file, the patcher verifies the file against that record's source_sha256 and source_size metadata.",
        "- This bundle keeps payload lean: changed Images files, .fmap files, OptionalVisualMods/, Original Virtual Families 2 Assets/, and OptionalSongMods/.",
        "- OptionalVisualMods/, Original Virtual Families 2 Assets/, and OptionalSongMods/ are source-only payload folders. They are not copied wholesale into the game.",
        "- Optional song mod records copy payload/OptionalSongMods/*.ogg to Sounds/*.ogg only when enabled; unchecking then clicking Enable/Disable Patches rebuilds the modded output with vanilla Sounds/*.ogg.",
        "- Optional visual records copy source graphics to runtime folders: furniture graphics to Images/Furniture, future Workshop/Kitchen/Office upgrade graphics to Images/Upgrades, and animation strips or other images to Images.",
        "- Feature-specific payloads for optional visual mods and Invisible Furniture are tied to their default-off settings, so unchecked settings leave those files unused and omitted from refreshed modded output folders.",
        "- Custom Couches and LDW Posters/Paintings payload files are tied to their own default-off setting. Current native store-row support still comes from the full modded EXE payload until those native table edits are split into per-feature patch records.",
        f"- Payload file count in this bundle: {len(payload_files)}",
        "",
        "Official install validation",
        "---------------------------",
        "- Before patching, the patcher validates the selected vanilla folder has the official LDW website install shape.",
        "- The selected folder path and executable name do not need to match any hardcoded local path; executable identity is matched by accepted VF2 PE layout.",
        "- Required top-level entries: " + ", ".join(OFFICIAL_INSTALL_TOP_LEVEL_ENTRIES),
        f"- Invalid-install popup text: {INVALID_INSTALL_MESSAGE.replace(chr(10), ' / ')}",
        "",
        "Payload files by top-level folder",
        "---------------------------------",
    ]
    if payload_top_counts:
        for key in sorted(payload_top_counts):
            lines.append(f"- {key}: {payload_top_counts[key]}")
    else:
        lines.append("- (payload folder not present when this log was written)")
    lines.extend([
        "",
        "Output and saves",
        "----------------",
        f"- Default modded output folder: {summary.get('modded_output_folder_name')}",
        f"- Modded EXE name: {summary.get('modded_exe_output_name')}",
        "- Modded saves are expected under Documents/LDW/(name of modded Virtual Families 2 exe).",
        "- Existing Virtual Families 2 saves can be used by copying the contents of the original Documents/LDW/Virtual Families 2 save folder into the modded save folder.",
        "- Existing saves remain unaltered in the original save folder.",
        "",
        "Settings and defaults",
        "---------------------",
        "- Main Patches (green): core patches, mobile-exclusive furniture, Holiday furniture, and Holiday outfits.",
        "- Optional Patches (black): optional visual swaps, Invisible Furniture graphics modes, custom maps, LDW Posters/Paintings, and Colorful Couches.",
        "- Experimental/Not Working Patches (red): Settings Evict, Island Events, and anything not 100% confirmed working and crash-free.",
    ]
    )
    for row in settings:
        if not isinstance(row, dict):
            continue
        default = "on" if row.get("default") else "off"
        lines.append(f"- {row.get('id')} [{default}]: {row.get('label')}")
        description = str(row.get("description", "")).strip()
        if description:
            lines.append(f"  {description}")
    if summary.get("byte_patch_count"):
        limitation = (
            "This bundle avoids a prebuilt modified game EXE payload by representing native/game-code changes as byte patch records. "
            "Complete per-feature native on/off behavior still requires splitting future native changes into narrower setting-gated byte/table records."
        )
    elif summary.get("exe_replacement"):
        limitation = (
            "This bundle uses a verified full modded EXE payload for native/game-code changes. "
            "Asset and file patches are gated by settings, but complete native per-feature off/on behavior requires translating future native changes into separate byte/table patch records with their own setting requirements."
        )
    else:
        limitation = (
            "This bundle omits both a modded EXE payload and native byte patch records. "
            "Native/game-code changes require byte/table patch records before they can be applied by this no-EXE patcher shape."
        )
    lines.extend(
        [
            "",
            "Patch record counts",
            "-------------------",
            f"- Byte patch records: {summary.get('byte_patch_count')}",
            f"- Native patch source metadata records: {summary.get('native_patch_source_count')}",
            f"- Asset patch records: {summary.get('asset_patch_count')}",
            f"- Payload files: {summary.get('payload_file_count')}",
            "",
            "Asset counts by setting",
            "-----------------------",
        ]
    )
    counts = summary.get("asset_counts_by_setting", {})
    if isinstance(counts, dict) and counts:
        for key, value in counts.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "Implementation map",
            "------------------",
            "- offline_vf2_patcher.py: validates manifests, target files, byte patch records, asset payload records, backups, restore, progress, and logs.",
            "- offline_vf2_patcher_gui.py: Tkinter GUI wrapper that renders manifest settings, streams patch progress, and shows a completion popup.",
            "- export_offline_patch_bundle.py: source-side exporter that builds manifest.json, payload/, runner scripts, and this transparency log.",
            "- Launch_GUI.bat: readable batch launcher for the GUI. No compiled patcher launcher EXE is shipped in this bundle.",
            "",
            "GUI launcher",
            "------------",
            "- Launch_GUI.bat is the supported GUI launcher.",
            "- Prebuilt Launch GUI.lnk is intentionally omitted because Windows shortcuts are path-specific inside ZIP distributions.",
        ]
    )
    lines.extend(
        [
            "",
            "Changelog",
            "---------",
            "- B103: Adds separate Invisible Heart-Shaped Bed using Heart-Shaped Bed behavior/graphics lineage.",
            "- B103 patcher refresh: Adds per-record progress output and process_log success/error entries.",
            "- B103 patcher refresh: Adds separate modded output folder support and clearly named modded EXE output.",
            "- B103 patcher refresh: Adds default-off optional visual patches for custom map images, transparent menu/store bars, transparent Decor tab, visible invisible furniture, and transparent invisible furniture swaps.",
            "- B103 patcher refresh: Adds a GUI completion popup with enabled patches, altered files, output folder, save folder, and save-copy guidance.",
            "- B104 patcher refresh: Removes the compiled patcher launcher EXE; ships readable BAT launchers and an optional iconed GUI shortcut instead.",
            "- B105 patcher refresh: Removes the prebuilt Launch GUI.lnk shortcut because zipped shortcuts can point at a stale path after extraction.",
            "- B105 patcher refresh: Prefer native byte/table patch records over a full modded EXE payload so the ZIP does not contain a ready-made modified game executable.",
            "- B104 patcher refresh: Adds default-on unused Turtle/Hamster pet setting metadata.",
            "- B104 patcher refresh: Adds default-off OptionalSongMods support targeting Sounds/*.ogg.",
            "- B104 patcher refresh: Refreshes the modded output folder from vanilla on Enable/Disable Patches so unchecked patches are removed.",
            "- B110 patcher refresh: Adds default-on Behavior Patches and Text fixes settings.",
            "- B110 patcher refresh: Adds default-off Invisible Upgrades Graphics, bundling invisible upgrade PNGs into OptionalVisualMods/Invisible Upgrades and targeting Images/Upgrades.",
            "- B110 patcher refresh: Exposes Store Scroll Bar as a default-off optional setting; current native support still comes from the core modded executable payload.",
            "- B111 patcher refresh: Target-file and EXE replacement validation find any accepted VF2 PE-layout executable in the selected install folder, so the patcher does not require a hardcoded install path or exact EXE filename.",
            "- B111 patcher refresh: VF3 Furniture is split into its own default-off optional setting using the runtime stems SofaPlaid, CouchPlaid, CouchFlowers, CouchStriped, SofaStriped, and FloweredLoveseat.",
            "- B111 patcher refresh: Holiday Outfit Details-screen body files under Images/VillagerDetailBodies are bundled with the Holiday Outfits patch.",
            "- B111 patcher refresh: Generation-lock standalone icons are bundled under Images/GenerationLocks.",
            "- B112 patcher refresh: Generation-lock icons now come from explicit bundled lock_02.png through lock_30.png files; missing numbered frames fail export instead of being synthesized from a short strip.",
            "- B112 game build: Added mobile/Holiday/VF3 furniture records with original generation_lock 0 are deterministically shuffled into 3-item groups across generations 10-30; base-game furniture records are not part of that path.",
            "- B112 game build: VF3 TV animation strips use bundled nonblank runtime strips when external creator Sprite frames are absent, and validation rejects fully transparent strips.",
            "- B112 game build: Holiday Body animation graphics are not resized; runtime frame generation transparent-crops the source pixels and stores draw offsets for alignment.",
            "- B113 game build: Child Holiday Body rendering scales those stored draw offsets by the active child/adult draw scale in both the Details screen and main game, while still preserving supplied source pixels without resizing.",
            "- B114 patcher refresh: Invisible Furniture Base/Transparent Graphics are rebuilt only from files already inside the generated build. Invisible Full-Size Pool, Invisible Kiddie Pool, and Invisible Hammock Base Graphics use base-game donor art while Transparent Graphics use .pngORIGINAL backups generated from those donor image dimensions.",
            "- B114 game build: Main-world Holiday Body drawing treats the native draw parameters as scale followed by alpha, so child Holiday Outfit crop offsets use body scale on both axes. The Details-screen renderer was left unchanged.",
            "",
            "Experimental patch warning",
            "--------------------------",
            "Experimental patches may not work and might cause instability or game crashes. Leave them disabled unless intentionally testing them.",
            "",
            "Known transparency limitation",
            "-----------------------------",
            limitation,
            "",
            "Have fun! -Lorsieab2 :)",
        ]
    )
    path = bundle_dir / TRANSPARENCY_LOG_NAME
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\r\n")
    return TRANSPARENCY_LOG_NAME


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    build_dir = Path(args.build_dir).resolve()
    bundle_dir = Path(args.out_dir).resolve()
    base_payload = Path(args.base_payload).resolve()
    build_label = infer_build_label(bundle_dir, args.name)
    manifest_in = Path(args.build_manifest).resolve() if args.build_manifest else build_dir / "patch-manifest.json"
    build_manifest_data = load_json(manifest_in) if manifest_in.is_file() else {}
    patched_exe = find_patched_exe(build_dir, args.patched_exe)
    vanilla_exe = Path(args.vanilla_exe).resolve() if args.vanilla_exe else None
    accepted_vanilla_exes = [Path(path).resolve() for path in args.accepted_vanilla_exe]
    for accepted_exe in accepted_vanilla_exes:
        if not accepted_exe.is_file():
            raise FileNotFoundError(f"Accepted vanilla EXE not found: {accepted_exe}")
    target_exe_name = args.target_exe_name or DEFAULT_EXE_NAME
    if args.include_exe_replacement and vanilla_exe is None:
        raise ValueError("--include-exe-replacement requires --vanilla-exe so the patcher can verify the original EXE.")

    if bundle_dir.exists() and any(bundle_dir.iterdir()) and not args.force:
        raise FileExistsError(f"Output bundle directory is not empty: {bundle_dir}")
    bundle_dir.mkdir(parents=True, exist_ok=True)
    if args.force:
        payload_dir = bundle_dir / "payload"
        if payload_dir.exists():
            shutil.rmtree(payload_dir)
        manifest_path = bundle_dir / "manifest.json"
        if manifest_path.exists():
            manifest_path.unlink()
        clear_generated_runner_files(bundle_dir)

    byte_patches: list[dict[str, Any]] = []
    native_status: dict[str, Any]
    target_files: list[dict[str, Any]] = []
    if vanilla_exe:
        target_files.append(target_file_record(vanilla_exe, target_exe_name, accepted_vanilla_exes))
        if args.include_byte_patches:
            try:
                byte_patches = build_byte_patches(vanilla_exe, patched_exe, target_exe_name)
                native_status = native_patch_status(
                    "byte_diff_exported",
                    byte_patch_count=len(byte_patches),
                    vanilla_size=vanilla_exe.stat().st_size,
                    patched_size=patched_exe.stat().st_size,
                )
            except ValueError as exc:
                if args.strict_byte_patches:
                    raise
                native_status = native_patch_status(
                    "byte_diff_skipped",
                    reason=str(exc),
                    next_step="Extract native patch records from object/linker patch data instead of full EXE diff.",
                    vanilla_size=vanilla_exe.stat().st_size,
                    patched_size=patched_exe.stat().st_size,
                )
        else:
            native_status = native_patch_status(
                "not_requested",
                reason="Vanilla EXE metadata was exported, but --include-byte-patches was not set.",
                vanilla_size=vanilla_exe.stat().st_size,
                patched_size=patched_exe.stat().st_size,
            )
    else:
        native_status = native_patch_status(
            "missing_vanilla_exe",
            reason="No --vanilla-exe was supplied, so target EXE metadata and byte patches were not exported.",
        )

    asset_patches = export_asset_payloads(
        build_dir,
        base_payload,
        bundle_dir,
        build_manifest_data,
        args.asset_mode,
        build_label,
    )
    generation_locks_source = Path(args.generation_locks_dir).resolve() if args.generation_locks_dir else None
    forced_lock_records = generation_lock_asset_patches(build_dir, bundle_dir, generation_locks_source)
    if forced_lock_records:
        forced_paths = {row["file_path"] for row in forced_lock_records}
        asset_patches = [row for row in asset_patches if row.get("file_path") not in forced_paths]
        asset_patches.extend(forced_lock_records)
    optional_song_source = Path(args.optional_song_mods_dir).resolve() if args.optional_song_mods_dir else None
    asset_patches.extend(optional_song_asset_patches(bundle_dir, base_payload, optional_song_source))
    invisible_upgrades_source = Path(args.invisible_upgrades_dir).resolve() if args.invisible_upgrades_dir else None
    original_upgrades_source = Path(args.original_upgrades_dir).resolve() if args.original_upgrades_dir else None
    asset_patches.extend(invisible_upgrades_asset_patches(bundle_dir, invisible_upgrades_source, original_upgrades_source))
    asset_patches.extend(optional_visual_asset_patches(bundle_dir))
    exe_replacement_record = None
    if args.include_exe_replacement and vanilla_exe is not None:
        exe_replacement_record = export_exe_replacement_payload(
            bundle_dir=bundle_dir,
            patched_exe=patched_exe,
            vanilla_exe=vanilla_exe,
            accepted_exes=accepted_vanilla_exes,
            target_exe_name=target_exe_name,
            build_label=build_label,
        )
        asset_patches.insert(0, exe_replacement_record)
    native_patch_sources = collect_native_patch_sources(build_manifest_data)
    validate_bundle_asset_sources(bundle_dir, asset_patches)

    asset_counts_by_setting: dict[str, int] = {}
    for row in asset_patches:
        for setting in row.get("requires", []):
            asset_counts_by_setting[setting] = asset_counts_by_setting.get(setting, 0) + 1

    manifest = {
        "manifest_version": 1,
        "name": args.name or f"VF2 offline patch bundle from {build_dir.name}",
        "description": "Generated offline patch bundle for user-provided vanilla VF2 PC installs.",
        "created_with": "Codex AI",
        "creator_disclosure": CREATOR_DISCLOSURE,
        "output": {
            "default_folder_name": modded_output_folder_name(build_label),
            "default_exe_name": modded_exe_output_name(build_label),
            "description": "The patcher writes a separate clearly labeled modded game folder next to the user's vanilla folder by default.",
        },
        "source_build": {
            "build_dir": str(build_dir),
            "build_manifest": str(manifest_in) if manifest_in.is_file() else None,
            "patched_exe": str(patched_exe),
            "build_manifest_keys": sorted(build_manifest_data) if build_manifest_data else [],
        },
        "settings": default_settings(
            bool(byte_patches),
            bool(exe_replacement_record),
            set(asset_counts_by_setting),
        ),
        "target_files": target_files,
        "runtime_requirements": {
            "invalid_install_message": INVALID_INSTALL_MESSAGE,
            "exact_top_level_entries": OFFICIAL_INSTALL_TOP_LEVEL_ENTRIES,
            "required_files": RUNTIME_REQUIRED_FILES,
            "required_dirs": RUNTIME_REQUIRED_DIRS,
        },
        "patches": byte_patches,
        "native_patch_sources": native_patch_sources,
        "asset_patches": asset_patches,
        "export_summary": {
            "byte_patch_count": len(byte_patches),
            "native_patch_status": native_status,
            "native_patch_source_count": len(native_patch_sources),
            "asset_patch_count": len(asset_patches),
            "asset_counts_by_setting": dict(sorted(asset_counts_by_setting.items())),
            "payload_file_count": count_files(bundle_dir / "payload"),
            "base_payload": str(base_payload),
            "asset_mode": args.asset_mode,
            "exe_replacement": exe_replacement_record is not None,
            "target_exe_name": target_exe_name,
            "modded_output_folder_name": modded_output_folder_name(build_label),
            "modded_exe_output_name": modded_exe_output_name(build_label),
            "requires_vanilla_exe_for_apply": not bool(target_files),
        },
    }
    if args.include_patcher_scripts:
        manifest["export_summary"]["runner_files"] = write_bundle_runner_files(bundle_dir, build_label)
    manifest["export_summary"]["transparency_log"] = write_transparency_log(bundle_dir, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True, help="Generated VF2 build folder to export.")
    parser.add_argument("--out-dir", required=True, help="Bundle output directory.")
    parser.add_argument("--build-manifest", help="Generated build patch-manifest.json. Defaults to BUILD_DIR/patch-manifest.json.")
    parser.add_argument("--base-payload", default=str(DEFAULT_BASE_PAYLOAD), help="Clean base asset payload used for diff filtering.")
    parser.add_argument("--vanilla-exe", help="Original vanilla VF2 EXE used for target hash and optional byte diff export.")
    parser.add_argument("--accepted-vanilla-exe", action="append", default=[], help="Additional official VF2 EXE whose PE layout should be accepted during install validation. Repeatable.")
    parser.add_argument("--patched-exe", help="Patched EXE filename inside build dir. Auto-detected by default.")
    parser.add_argument("--target-exe-name", default=DEFAULT_EXE_NAME, help="Relative EXE path expected in the user's game folder.")
    parser.add_argument("--name", help="Manifest display name.")
    parser.add_argument("--asset-mode", choices=ASSET_MODES, default="additive", help="Asset export mode. 'additive' exports manifest-referenced assets; 'all' exports every Images/Assets diff.")
    parser.add_argument("--optional-song-mods-dir", help="Folder containing optional song .ogg files to place in payload/OptionalSongMods and target to Sounds/.")
    parser.add_argument("--invisible-upgrades-dir", help="Folder containing invisible upgrade .png files to place in payload/OptionalVisualMods/Invisible Upgrades and target to Images/Upgrades.")
    parser.add_argument("--original-upgrades-dir", help="Folder containing original upgrade .png files to bundle as restore/reference sources for Invisible Upgrades.")
    parser.add_argument("--generation-locks-dir", help="Folder containing lock_02.png through lock_30.png; defaults to bundled workspace assets.")
    parser.add_argument("--include-byte-patches", action="store_true", help="Diff vanilla EXE against patched EXE into byte patch records.")
    parser.add_argument("--include-exe-replacement", action="store_true", help="Copy the patched EXE into payload and replace a verified vanilla target EXE during apply.")
    parser.add_argument("--include-patcher-scripts", action="store_true", help="Copy the CLI/GUI patcher scripts plus convenience batch files into the bundle.")
    parser.add_argument("--strict-byte-patches", action="store_true", help="Fail if --include-byte-patches cannot produce byte records.")
    parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty output directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_manifest(args)
    out_dir = Path(args.out_dir).resolve()
    manifest_path = out_dir / "manifest.json"
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "byte_patches": len(manifest["patches"]),
                "asset_patches": len(manifest["asset_patches"]),
                "payload_files": manifest["export_summary"]["payload_file_count"],
                "requires_vanilla_exe_for_apply": manifest["export_summary"]["requires_vanilla_exe_for_apply"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
