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
import tempfile
from pathlib import Path
from typing import Any, Callable


SOURCE_DIR = Path(__file__).resolve().parent
ROOT = SOURCE_DIR.parent
DEFAULT_BASE_PAYLOAD = SOURCE_DIR / "vanilla_runtime_payload"
OFFICIAL_PE_STRUCTURES_FILE = SOURCE_DIR / "official_vf2_pe_structures.json"
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
OPTIONAL_PATCH_ASSET_DIR = ROOT / "patcher_assets" / "optional_patches"
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
DEFAULT_OPTIONAL_SONG_MODS_SOURCE = OPTIONAL_PATCH_ASSET_DIR / "optional_song_mods" / "OptionalSongMods"
MOBILE_SOUND_ASSET_SOURCE_DIR = OPTIONAL_PATCH_ASSET_DIR / "mobile_sound_assets"
MOBILE_SOUND_PARITY_CONTRACT = ROOT / "data" / "vf2" / "mobile-sound-parity-contract.json"
try:
    _mobile_sound_contract = json.loads(MOBILE_SOUND_PARITY_CONTRACT.read_text(encoding="utf-8"))
    _mobile_sound_rows = _mobile_sound_contract["sound_records"]
except (OSError, KeyError, json.JSONDecodeError) as exc:
    raise RuntimeError(f"Unable to load mobile sound parity contract: {MOBILE_SOUND_PARITY_CONTRACT}") from exc
if not isinstance(_mobile_sound_rows, list) or len(_mobile_sound_rows) != 67:
    raise RuntimeError("Mobile sound parity contract must contain exactly 67 records")
MOBILE_SOUND_ASSET_FILES = tuple(row["mobile_obb"]["asset_name"] for row in _mobile_sound_rows)
MOBILE_SOUND_ASSET_PINS = {
    row["mobile_obb"]["asset_name"]: row["mobile_obb"]["sha256"]
    for row in _mobile_sound_rows
}
MOBILE_SOUND_PC_FILENAMES = {
    row["mobile_obb"]["asset_name"]: row["pc_sound_obj"]["filename"]
    for row in _mobile_sound_rows
}
if len({name.lower() for name in MOBILE_SOUND_ASSET_FILES}) != 67:
    raise RuntimeError("Mobile sound parity contract contains duplicate asset names")
MOBILE_SOUND_ROUTE_PINS = {
    "beaker.wav": ("beaker.ogg", "0xee3b"),
    "Child3.wav": ("Child3.ogg", "0xf3cd"),
    "Child7.wav": ("Child7.ogg", "0xf431"),
    "Child8.wav": ("Child8.ogg", "0xf44a"),
}
MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR = (
    OPTIONAL_PATCH_ASSET_DIR / "mobile_furniture_behaviors" / "pc_fmaps"
)
MOBILE_CHAISE_FMAP_FILES = (
    "Chaise_blue.png.fmap",
    "Chaise_brown.png.fmap",
    "Chaise_green.png.fmap",
    "Chaise_red.png.fmap",
)
MOBILE_PATIO_UMBRELLA_FMAP_FILE = "Patio_umbrella.png.fmap"
MOBILE_BIRTHDAY_FMAP_FILES = (
    "Birthday_banner.png.fmap",
    "Balloons_birthday.png.fmap",
    "Birthday_cake.png.fmap",
    "Birthday_presents.png.fmap",
)
MOBILE_HOLIDAY_FMAP_FILES = (
    "CandleOnHolder.png.fmap",
    "ChristmasTree1.png.fmap",
    "ChristmasTree2.png.fmap",
    "Dreidel.png.fmap",
    "GlassOfEggnog.png.fmap",
    "Gnome1.png.fmap",
    "Gnome2.png.fmap",
    "Gnome3.png.fmap",
    "Gnome4.png.fmap",
    "Gnome5.png.fmap",
    "Menorah.png.fmap",
    "PenguinDecoration.png.fmap",
    "PlateOfCookies.png.fmap",
    "PolarBearDecoration.png.fmap",
    "RedBow.png.fmap",
    "ReindeerDecoration.png.fmap",
    "SantaGardenDecoration.png.fmap",
    "SantaWallDecoration.png.fmap",
    "Snowman.png.fmap",
    "StockingLarge.png.fmap",
    "StockingSmall.png.fmap",
    "StringOfLeaves.png.fmap",
    "StringOfLights.png.fmap",
)
MOBILE_FURNITURE_BEHAVIOR_FMAP_FILES = (
    *MOBILE_CHAISE_FMAP_FILES,
    MOBILE_PATIO_UMBRELLA_FMAP_FILE,
    "Patio_table.png.fmap",
    "Picnic_table.png.fmap",
    *MOBILE_BIRTHDAY_FMAP_FILES,
    *MOBILE_HOLIDAY_FMAP_FILES,
)
SOURCE_BACKED_OPTIONAL_SETTINGS = {
    "allow_older_pregnancies",
    "same_sex_marriage",
    "older_villager_mortality",
    "invisible_upgrades_graphics",
    "optional_song_mods",
    "mobile_furniture_behaviors",
    "white_birds",
    "transparent_menu_bar",
    "transparent_store_bar",
    "transparent_decor_tab",
    "custom_lorsieab2_map_images",
    "optional_visual_mod_graphics",
    "mobile_renovations",
    "mobile_sound_assets",
    "cheat_upgrades",
}
EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS = {
    "island_events",
    "cheat_upgrades",
    "holiday_ornaments_collection",
    "behavior_patches",
    "mobile_renovations",
}
OUTPUT_ONLY_REMOVABLE_ASSET_SETTINGS = EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS

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
        "description": "Enables the behavior-only executable overlay. B150 adds spontaneous Needs to sit down, Mending a button, Ironing clothes, Checking weight, and nursing-mother Teaching first words/infant care; enables the registered web, nap, sit-down, sink/grooming, snow, shower, meal, career, play, and other label routes while preserving their documented native age, object, weather, nursing, and gender gates; keeps Petting non-spontaneous; and directly preserves the exact current action string across normal praise. All Behavior Patch native changes and variations are absent when this setting is disabled.",
        "default": True,
        "category": "main",
    },
    {
        "id": "text_fixes",
        "label": "Text fixes",
        "description": "Misc text fixes, including {name} sees their adorable pet and Not feeling clean.",
        "default": True,
        "category": "main",
    },
    {
        "id": "holiday_ornaments_collection",
        "label": "Add Holiday Ornaments collection",
        "description": "Adds the fully linked mobile Holiday Ornament collection: 12 yard collectibles, six Collections Chest pages/72 total items, Ornamentologist and six-family collection goals, save/load support, Lucky Rock rarity odds, and The Collector offer/sell handling. B151 removes the non-mobile launch-crash hooks and uses tracked canonical artwork. Default-off so players opt into the extra collection; manual gameplay verification is still recommended.",
        "default": False,
        "category": "optional",
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
        "description": "Adds the mobile-style Settings Evict button in the Settings menu. Evicting removes the current family and resets the Family Tree to Generation 1.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "allow_older_pregnancies",
        "label": "Allow Older Pregnancies",
        "description": "Optional patch: preserves normal fertility behavior below age 50, then allows a small pregnancy chance when either parent is 50 or older. The older parent caps the chance from 10.0% at age 50 down to a permanent 0.1% floor at age 69+. Failed attempts involving an age-50+ parent do not start the stock try-for-baby cooldown. The stock Next Generation flow also becomes available when the oldest living person reaches age 60, provided there is a surviving child.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "same_sex_marriage",
        "label": "Allow Same-Sex Marriage",
        "description": "Optional patch: marriage proposals may offer either women or men. Same-sex spouses are stored in the native two-parent family tree, can repeat the private romantic action when dropped on each other, and have a 0% pregnancy chance. Disabling this restores the stock opposite-sex candidate and spouse behavior.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "older_villager_mortality",
        "label": "Older Villager Mortality Curve",
        "description": "Optional patch: replaces only the annual old-age death roll with a full-game calibrated chance that increases with effective age and accelerates after effective age 110. The stock threshold and 0-4 active-food-group age bonus remain. Old-age death never becomes certain and there is no hard maximum age; reaching 110 should take multiple 60-adult games and reaching 122 is exceptionally rare. All stock mortality remains active when disabled.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "mobile_furniture_behaviors",
        "label": "Add mobile furniture behaviors",
        "description": "Optional patch: enables ported actions for genuine mobile furniture where implemented. B156 makes good-weather loungers choose among relaxing, reading, studying, sitting, napping, and sleeping with exhaustion-sensitive rest odds, plus spontaneous supported variants. Exact guarded manual routes cover the Patio Umbrella and tables, Picnic Table, Birthday furniture, Christmas Trees, Dreidel, Menorah, Stockings, Holiday Candles, Santa's Cookie Plate, ten Holiday figurines, Red Bow, Santa Wall Decoration, and both garlands. Invisible/custom/VF3 furniture is excluded.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "mobile_renovations",
        "label": "Add mobile room renovations",
        "description": "Optional patch: overlays the 15 verified mobile kitchen, bathroom, office, and workshop renovation images at their exact 1:1 room-map positions. The stock map remains unchanged when this setting is disabled.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "mobile_sound_assets",
        "label": "Use mobile sound assets",
        "description": "Stages all 67 hash-pinned mobile behavior sounds and replaces the four PC WAV filename routes that must point to OGG assets. Default-off; audible parity remains pending runtime QA.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "island_events",
        "label": "Add mobile-exclusive Island Events",
        "description": "Adds mobile-exclusive Island Event records, including mobile-only email events, with their bundled event text and choice/result dialogs.",
        "default": False,
        "category": "optional",
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
        "label": "Invisible Workspace Upgrades",
        "description": "Optional visual mod. Replaces Images/Upgrades workspace graphics with bundled invisible upgrade graphics. Uncheck it and click Enable/Disable Patches to restore bundled vanilla upgrade graphics.",
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
    {
        "id": "misc_graphics_fixes",
        "label": "Misc Graphics Fixes",
        "description": "Fixes various graphics bugs, including the Super Fridge ice maker position.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "glowing_collectibles",
        "label": "Glowing Collectibles",
        "description": "Adds a white glow around grabbable objects for easier visibility.",
        "default": False,
        "category": "optional",
    },
    {
        "id": "cheat_upgrades",
        "label": "Cheat Upgrades",
        "description": "Enables the cheat-only executable overlay. Adds function-grouped money, food, achievement/puzzle/collection, price, and malfunction rows, including Trigger all house malfunctions and Fix all house malfunctions. Trigger makes the Router offline and Fix returns it online; Fix clears all 11 malfunction props without resetting ants. The Dryer lint fire remains a legitimate native random malfunction and requires a Dryer. Price modes affect every purchase routed through the store price calculator; Reset Price Multiplier restores original calculated prices. Rebuying Maid/Gardener fires that worker; rebuying Rockhound Certificate/Anti-Spam removes it; rebuying an owned house renovation `0xE1-0xEA` returns it and rebuilds the native content map so the renovation can be purchased again. All B150 cheat and reversible-upgrade behavior is absent when this setting is disabled.",
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
INVISIBLE_UPGRADES_SOURCE_DIR = Path("OptionalVisualMods") / "Invisible Workspace Upgrades" / "invisible images"
ORIGINAL_UPGRADES_SOURCE_DIR = Path("OptionalVisualMods") / "Invisible Workspace Upgrades" / "original images"
PATCHER_DISPLAY_NAME = "Virtual Families 2 Restoration/Addition Patcher"
PATCHER_RELEASE_REPO_DISPLAY_NAME = "Virtual Families 2 Restoration/Addition Patcher"
PATCHER_RELEASE_REPO_NAME = "Virtual-Families-2-Restoration-Addition-Patcher"
PATCHER_RELEASES_URL = f"https://github.com/Lorsieab2/{PATCHER_RELEASE_REPO_NAME}/releases"
MODDED_EXE_OUTPUT_TEMPLATE = "Virtual Families 2 - Modded {build_label}.exe"
MODDED_OUTPUT_FOLDER_TEMPLATE = "VF2-{build_label}-Modded"
STALE_PATCHER_LAUNCHER_NAME = "Virtual Families 2 Restoration-Addition Patcher.exe"
STALE_PATCHER_SHORTCUT_NAME = "Launch GUI.lnk"
STALE_PATCHER_SHORTCUT_STATUS_NAME = "launch_gui_shortcut.json"
TRANSPARENCY_LOG_NAME = "Transparency Log.txt"
PATCHER_ICON_PNG = "patcher_icon.png"
PATCHER_ICON_ICO = "patcher_icon.ico"
CREATOR_DISCLOSURE = "This offline patcher was created with Codex AI in collaboration with Lorsieab2."
PROJECT_CREATOR_MESSAGE = (
    'Created by Lorsieab2. This is a passion project dedicated to improving the '
    '"Virtual Families 2" experience!\n'
    'No copyright infringement intended! Please support the original game creators! :)'
)
SAVE_COMPATIBILITY_NOTE = "Vanilla Virtual Families 2 saves are compatible with the modded version!"
B150_CHANGELOG_LINES = (
    "- B150 native patch gating: Adds a complete 16-overlay executable matrix for every combination of Island Events, Cheat Upgrades, Holiday Ornaments, and Behavior Patches. Each native feature is present only when its matching manifest setting is enabled; the behavior-disabled core keeps the stock behavior objects.",
    "- B150 Holiday Ornaments hotfix: Replaces unsafe byte insertions inside CCollectionScene::HandleMouse, CCollectableItem::Find, and CCollectableItem::WasItemSpawned with fixed-size near-jump detours to end-of-section code caves. This preserves all native relative branches, repairs The Collector Keep branch, prevents the incomplete Drop path from looping, makes Ornamentologist completion idempotent, retains the stdcall page-count helper, and displays six pages/72 collectibles.",
    "- B150 spontaneous behaviors: Behavior Patches enables Needs to sit down/RestingBody, Mending a button, Ironing clothes, and Checking weight. Checking weight and sit-down are all-ages; mending and ironing start at displayed age 14. Petting retains its manual/native label variants but is deliberately not added to the autonomous candidate table.",
    "- B150 nursing behavior: Behavior Patches makes the native Teaching first words route spontaneous only for nursing mothers carrying a baby and adds Teaching baby how to walk, Talking with baby, Feeding baby, Singing lullabies to baby, Playing with baby, Admiring baby, Playing peek-a-boo with baby, Kissing baby, and Taking pictures of baby.",
    "- B150 web variations: Browsing web adds Watching memes, Making memes, and Posting memes online to the general pool. Buying stuff online is available only from displayed age 13 upward; the existing teen/adult social-web pool still follows its native age route.",
    "- B150 nap variations: Taking a nap can show Dreaming of Isola, Dreaming of family, Dreaming of pets, Dreaming of friends, Dreaming of the future, Dreaming of the beach, Dreaming of snow, Dreaming of holidays, Dreaming of vacations, Dreaming of roller coasters, Dreaming of climbing mountains, Dreaming of camping, Dreaming of family trips, Dreaming of the countryside, Dreaming of LDW games, Dreaming of the city, Dreaming of the forest, Dreaming of unicorns, Dreaming of fish, Dreaming of jungles, Dreaming of tropical islands, Dreaming of skyscrapers, Dreaming of floating in space, Dreaming of treasure, Dreaming of getting rich, Dreaming of adventures, Dreaming of swimming, Dreaming of flying, Dreaming of falling, or Dreaming of discovering something.",
    "- B150 sit-down variations: The all-age pool includes Thinking, Taking a moment to reflect, Taking a break, Enjoying life, Enjoying the scenery, Resting, Resting eyes, Resting feet, Relaxing for a bit, Thinking of weekend plans, Thinking of family, Thinking of friends, Thinking of pets, Thinking of vacations, Thinking of what to watch next, Thinking of relatives, Texting, Playing games on phone, Scrolling on phone, Checking social media on phone, Scrapbooking, Texting friends, Texting family, and Texting relatives. Displayed age 19+ also receives Thinking of children, Thinking of grandchildren, Thinking of spouse, and Texting spouse; Thinking of work requires age 19+ with a career; Thinking of school is for anyone who is not an age-19+ career holder; Texting boyfriend is female-only and Texting girlfriend male-only at displayed ages 14-18.",
    "- B150 sink, snow, and native-gate audit: Behavior Patches enables the direct bathroom-sink subroutines by cloning the stock sink candidate gates, retains the existing face-mask/nails/lotion/sunscreen and female grooming pools, and adds Putting on jewelry only for females age 14+. North-shower, snow-play, and other registered variation routes preserve their native object/age/gender gates; snow play is enabled only while Weather.currentType is Snowing.",
    "- B150 praise stability hotfix: Normal praise now captures the exact 0x28-byte action label before InvokeReward calls ForgetPlans, restores it before the restarted behavior wrapper runs, and restores it again after StartNewBehavior. This fixes the remaining variation-string reroll without changing the deliberate over-praise RunAway path.",
    "- B150 collection and puzzle cheats: Reset Ants restarts world-state puzzle 0x13, clears ant props 0x4D-0x54, and reseeds the native starting ant pieces. Reset all collections uses the native collection reset, raw-clears completed/progress state for all page achievements (including cross-overlay Holiday state) and Master Collector, then recomputes Goal Collector from preserved selling goals. Complete all collections fills exactly 12 items per active page and completes the matching page/aggregate achievements.",
    "- B150 price cheats: 2x Prices, 5x Prices, and 100x Prices are mutually exclusive persistent toggles. They multiply the final store price for furniture, Flea Market goods, house renovations, career upgrades, Special Upgrades, and every other purchase routed through CalcPrice; multiplication saturates at signed INT_MAX instead of wrapping. Reset Price Multiplier (0x12C) removes any active 0x128-0x12A mode and restores original calculated store prices; its description is 'Resets store prices to original values.'",
    "- B150 malfunction cheats: Trigger all house malfunctions (0x12B) sets the normal failures and Router Offline prop 0x17; Fix all house malfunctions (0x12D) clears all 11 malfunction props and returns the Router online without touching ant props. The Dryer lint fire prop 0x21 is also a legitimate stock random malfunction: it requires Dryer object 0x48, uses the native repair behavior, and advances Handyman. North leaks remain renovation-gated; Water Pressure Surge adds them only with Island Events.",
    "- B150 reversible upgrades: Under Cheat Upgrades, rebuying Maid or Gardener at the active zero-price row clears the worker timer/active villager and fires that worker. Rebuying Rockhound Certificate or Anti-Spam removes the owned upgrade. Rebuying an owned native house renovation `0xE1-0xEA` returns that upgrade, reloads the base content map, reapplies the remaining native renovation records, and saves. Explicit cheat-overlay guards keep these removal hooks inert when Cheat Upgrades is disabled.",
    "- B150 mobile purchase text: The Brokerage Account description now states that repeated upgrades can increase the Interest Rate up to 11%. This wording follows the visible mobile Special Upgrades/mobile_purchases feature family.",
    "- B150 patcher notices: The GUI, generated README, manifest, and Transparency Log identify Lorsieab2's passion project, ask players to support the original creators, and state that vanilla Virtual Families 2 saves are compatible with the modded version.",
    "- B150 compact package: The exporter prunes every payload file unreachable from manifest source/restore records, rejects accidental .bak generated assets, revalidates retained source hashes and sizes, and records portable base-payload metadata. This removed 1,860 unreachable files (100,244,363 bytes) without removing a selectable feature.",
    "- B150 hotfix verification status: All 16 native feature combinations generated, compiled, linked, passed manifest-gate checks, produced unique EXE hashes, and had clean build logs. All eight Holiday-enabled linked PEs passed direct detour/branch-target validation. Automated validation passed 71 binary-patcher tests plus 56 exporter/runner/GUI tests (127 total). The final export contains 1,075 asset records and 1,112 manifest-reachable payload files after pruning 1,860 unreachable files. Manual in-game verification remains required for the full Collections Chest cycle, praise retention, every autonomous/label eligibility branch, all store categories, reversible workers/upgrades, and simultaneous malfunction/repair gameplay.",
)
B151_CHANGELOG_LINES = (
    "- B151 Holiday Ornaments completion: Uses the exact mobile 1.7.16 collectible IDs 0x9E-0xA9, rarity groups, and three Holiday spawn regions. The desktop total is 19 spawn registrations. Stock Add, Find, WasItemSpawned, and Lucky Rock logic remain byte-identical instead of using the two non-mobile family-match caves associated with the B150 launch crash.",
    "- B151 Collections Chest: Adds the sixth 12-item page in mobile order, corrects every ornament slot against the resized 1024x768 mobile page, keeps the 0x30-byte scene object/hover field intact, routes page counts through a fixed-size DrawScene code cave, extends tooltip rarity buckets, and displays 72 total collectibles only in Holiday-enabled overlays.",
    "- B151 persistence and goals: Explicitly validates Count, ResetCollection, SaveState, and LoadState across the existing 0xAF-entry collection-state block. Master Collector now requires six families, Goal Collector requires 13 goals, Ornamentologist requires 12 unique ornaments, and the achievement notification queue covers all 0x60 rows.",
    "- B151 Collector event: Three relocation-only CanFire calls add Holiday common/uncommon/rare counts to the offer. Stock final eligibility and the Keep branch remain unchanged. Sell routes through a helper that resets unfinished Ornamentologist progress before the stock collection reset tail.",
    "- B151 self-contained art: The 12 ornament icons and 1024x768 collection page are tracked, hash-verified workspace assets. Holiday-disabled outputs remove inherited unused collection PNGs; Holiday-enabled outputs no longer depend on ignored tp225.dat/tp225.pvr files.",
    "- B151 verification: The complete 16-overlay matrix and independent positive/negative linked-PE validator cover spawning, observers, exact item matching, rarity/Lucky Rock thresholds, pickup/completion, chest navigation/tooltips, persistence, achievements, Collector routes, and canonical art. Manual in-game launch, chest, pickup, save/reload, Collector, and collection-cheat testing remains required.",
)
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


def require_vf2_pe32_x86(path: Path, *, label: str) -> dict[str, Any]:
    """Reject non-PE and non-x86 executable payloads before bundle export."""
    structure = pe_structure_fingerprint(path)
    if structure is None:
        raise ValueError(f"{label} is not a valid PE32 executable: {path}")
    if structure.get("machine") != "0x14c":
        raise ValueError(
            f"{label} is not a 32-bit x86 executable: {path} "
            f"(machine={structure.get('machine')})"
        )
    if not structure.get("sections"):
        raise ValueError(f"{label} has no PE sections: {path}")
    return structure


def runtime_flag_variant_for_exe(
    path: Path,
    *,
    section_name: str,
    expected_byte: int,
    replacement_byte: int,
    note: str,
) -> dict[str, Any]:
    """Build one exact-SHA post-asset variant from a one-byte PE section."""
    structure = pe_structure_fingerprint(path)
    if structure is None:
        raise ValueError(f"Runtime-flag executable is not a valid PE32 image: {path}")
    matches = [
        section
        for section in structure["sections"]
        if section.get("name") == section_name
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {section_name} section in {path}, found {len(matches)}."
        )
    section = matches[0]
    virtual_size = int(str(section["virtual_size"]), 0)
    raw_size = int(str(section["raw_data_size"]), 0)
    raw_offset = int(str(section["raw_data_pointer"]), 0)
    characteristics = int(str(section["characteristics"]), 0)
    if virtual_size != 1 or raw_size < 1:
        raise ValueError(
            f"{section_name} in {path} must contain exactly one initialized runtime byte."
        )
    if not (characteristics & 0x80000000):
        raise ValueError(f"{section_name} in {path} is not writable.")
    data = path.read_bytes()
    if raw_offset >= len(data) or data[raw_offset] != expected_byte:
        actual = data[raw_offset] if raw_offset < len(data) else None
        actual_text = f"{actual:02x}" if actual is not None else "end-of-file"
        raise ValueError(
            f"{section_name} default byte mismatch in {path}: "
            f"expected {expected_byte:02x}, got {actual_text}"
        )
    return {
        "asset_sha256": sha256_file(path),
        "offset": f"0x{raw_offset:x}",
        "expected_asset_bytes": f"{expected_byte:02X}",
        "replacement_bytes": f"{replacement_byte:02X}",
        "note": note,
    }


def setting_runtime_flag_post_asset_patches(
    executable_sources: list[Path],
    *,
    output_exe_name: str,
    runtime_flag: dict[str, Any],
    section_name: str,
    setting_id: str,
    feature_label: str,
) -> list[dict[str, Any]]:
    """Emit one exact-SHA setting gate covering every linked matrix payload."""
    if runtime_flag.get("source_section") != section_name:
        raise ValueError(
            f"Build manifest has an invalid {feature_label} runtime flag contract."
        )
    variants_by_sha: dict[str, dict[str, Any]] = {}
    for source in executable_sources:
        variant = runtime_flag_variant_for_exe(
            source,
            section_name=section_name,
            expected_byte=0,
            replacement_byte=1,
            note=f"Enable {feature_label} in {source.name}.",
        )
        sha = str(variant["asset_sha256"]).lower()
        prior = variants_by_sha.get(sha)
        if prior is not None and prior["offset"] != variant["offset"]:
            raise ValueError(
                f"Duplicate executable SHA {sha} has conflicting "
                f"{section_name} offsets."
            )
        variants_by_sha[sha] = variant
    if not variants_by_sha:
        raise ValueError(f"{feature_label} has no exported executable payloads.")
    return [
        {
            "file_path": output_exe_name,
            "requires": ["core_executable", setting_id],
            "note": (
                f"Exact-SHA runtime toggle for {feature_label} "
                f"({section_name})."
            ),
            "variants": list(variants_by_sha.values()),
        }
    ]


def older_pregnancy_post_asset_patches(
    executable_sources: list[Path],
    *,
    output_exe_name: str,
    build_manifest_data: dict[str, Any],
) -> list[dict[str, Any]]:
    contract = build_manifest_data.get("AllowOlderPregnancies")
    if not isinstance(contract, dict):
        return []
    runtime_flag = contract.get("runtime_flag")
    if not isinstance(runtime_flag, dict):
        raise ValueError(
            "Build manifest has an invalid AllowOlderPregnancies contract."
        )
    return setting_runtime_flag_post_asset_patches(
        executable_sources,
        output_exe_name=output_exe_name,
        runtime_flag=runtime_flag,
        section_name=".vf2preg",
        setting_id="allow_older_pregnancies",
        feature_label="Allow Older Pregnancies",
    )


def older_mortality_post_asset_patches(
    executable_sources: list[Path],
    *,
    output_exe_name: str,
    build_manifest_data: dict[str, Any],
) -> list[dict[str, Any]]:
    contract = build_manifest_data.get("OlderVillagerMortality")
    if not isinstance(contract, dict):
        return []
    runtime_flag = contract.get("runtime_flag")
    if not isinstance(runtime_flag, dict):
        raise ValueError(
            "Build manifest has an invalid OlderVillagerMortality contract."
        )
    return setting_runtime_flag_post_asset_patches(
        executable_sources,
        output_exe_name=output_exe_name,
        runtime_flag=runtime_flag,
        section_name=".vf2mort",
        setting_id="older_villager_mortality",
        feature_label="Older Villager Mortality Curve",
    )


def same_sex_marriage_post_asset_patches(
    executable_sources: list[Path],
    *,
    output_exe_name: str,
    build_manifest_data: dict[str, Any],
) -> list[dict[str, Any]]:
    contract = build_manifest_data.get("SameSexMarriage")
    if not isinstance(contract, dict):
        return []
    runtime_flag = contract.get("runtime_flag")
    if not isinstance(runtime_flag, dict):
        raise ValueError(
            "Build manifest has an invalid SameSexMarriage contract."
        )
    return setting_runtime_flag_post_asset_patches(
        executable_sources,
        output_exe_name=output_exe_name,
        runtime_flag=runtime_flag,
        section_name=".vf2same",
        setting_id="same_sex_marriage",
        feature_label="Same-Sex Marriage",
    )


def holiday_furniture_goal_post_asset_patches(
    executable_sources: list[Path],
    *,
    output_exe_name: str,
    build_manifest_data: dict[str, Any],
) -> list[dict[str, Any]]:
    contract = build_manifest_data.get("CustomAchievements")
    if not isinstance(contract, dict):
        return []
    runtime_flag = contract.get("runtime_flag")
    if not isinstance(runtime_flag, dict):
        raise ValueError(
            "Build manifest has an invalid CustomAchievements runtime flag contract."
        )
    return setting_runtime_flag_post_asset_patches(
        executable_sources,
        output_exe_name=output_exe_name,
        runtime_flag=runtime_flag,
        section_name=".vf2goal",
        setting_id="holiday_furniture",
        feature_label="Holiday Furniture goals",
    )


def mobile_furniture_behavior_post_asset_patches(
    executable_sources: list[Path],
    *,
    output_exe_name: str,
    build_manifest_data: dict[str, Any],
) -> list[dict[str, Any]]:
    contract = build_manifest_data.get("MobileFurnitureBehaviors")
    if not isinstance(contract, dict):
        return []
    runtime_flag = contract.get("runtime_flag")
    if not isinstance(runtime_flag, dict):
        raise ValueError(
            "Build manifest has an invalid MobileFurnitureBehaviors runtime flag contract."
        )
    return setting_runtime_flag_post_asset_patches(
        executable_sources,
        output_exe_name=output_exe_name,
        runtime_flag=runtime_flag,
        section_name=".vf2beh",
        setting_id="mobile_furniture_behaviors",
        feature_label="Mobile Furniture Behaviors",
    )


def mobile_sound_assets_post_asset_patches(
    executable_sources: list[Path],
    *,
    output_exe_name: str,
    build_manifest_data: dict[str, Any],
    allowed_source_sha256s: set[str],
) -> list[dict[str, Any]]:
    """Emit four exact-SHA, all-or-nothing Sound.obj route replacements."""
    contract = build_manifest_data.get("MobileSoundAssets")
    if not isinstance(contract, dict):
        return []
    routes = contract.get("routes")
    if not isinstance(routes, list) or len(routes) != 4:
        raise ValueError("Build manifest has an incomplete MobileSoundAssets route contract.")
    normalized_routes = []
    for route_index, route in enumerate(routes):
        if not isinstance(route, dict):
            raise ValueError(f"MobileSoundAssets route #{route_index} is invalid.")
        try:
            expected = bytes.fromhex(str(route["expected_bytes"]))
            replacement = bytes.fromhex(str(route["replacement_bytes"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"MobileSoundAssets route #{route_index} has invalid bytes.") from exc
        if not expected or len(expected) != len(replacement):
            raise ValueError(f"MobileSoundAssets route #{route_index} has invalid replacement length.")
        pc_filename = str(route.get("pc_filename", ""))
        mobile_filename = str(route.get("mobile_filename", ""))
        pin = MOBILE_SOUND_ROUTE_PINS.get(pc_filename)
        if pin is None or pin[0] != mobile_filename or str(route.get("object_offset", "")).lower() != pin[1]:
            raise ValueError(f"MobileSoundAssets route #{route_index} disagrees with the pinned contract.")
        if expected != pc_filename.encode("ascii") or replacement != mobile_filename.encode("ascii"):
            raise ValueError(f"MobileSoundAssets route #{route_index} literal bytes drifted.")
        normalized_routes.append((route_index, route, expected, replacement))

    source_variants: dict[Path, dict[str, Any]] = {}
    normalized_allowed = {str(value).lower() for value in allowed_source_sha256s}
    if not normalized_allowed:
        raise ValueError("MobileSoundAssets has no authenticated executable payload hashes.")
    for source in executable_sources:
        data = source.read_bytes()
        source_sha = sha256_file(source).lower()
        if source_sha not in normalized_allowed:
            raise ValueError(
                f"MobileSoundAssets executable payload is not authenticated: {source.name} ({source_sha})"
            )
        patched = bytearray(data)
        offsets = []
        for route_index, route, expected, replacement in normalized_routes:
            offset = data.find(expected)
            duplicate = data.find(expected, offset + 1) if offset >= 0 else -1
            if offset < 0 or duplicate >= 0:
                raise ValueError(
                    f"Expected exactly one {route.get('pc_filename', 'sound')} route in {source.name}"
                )
            offsets.append(offset)
            patched[offset : offset + len(expected)] = replacement
        source_variants[source] = {
            "source_sha256": source_sha,
            "offsets": offsets,
            "result_sha256": hashlib.sha256(bytes(patched)).hexdigest(),
        }
    if not source_variants:
        raise ValueError("MobileSoundAssets has no executable payloads.")

    records: list[dict[str, Any]] = []
    for normalized_index, (route_index, route, expected, replacement) in enumerate(normalized_routes):
        variants_by_sha: dict[str, dict[str, Any]] = {}
        for source, source_record in source_variants.items():
            sha = source_record["source_sha256"]
            variant = {
                "asset_sha256": sha,
                "offset": f"0x{source_record['offsets'][normalized_index]:x}",
                "expected_asset_bytes": expected.hex().upper(),
                "replacement_bytes": replacement.hex().upper(),
                "result_asset_sha256": source_record["result_sha256"],
                "note": f"Enable mobile sound route {route.get('pc_filename', '')} -> {route.get('mobile_filename', '')} in {source.name}.",
            }
            prior = variants_by_sha.get(sha)
            if prior is not None and prior["offset"] != variant["offset"]:
                raise ValueError(
                    f"Duplicate executable SHA {sha} has conflicting mobile sound offsets."
                )
            variants_by_sha[sha] = variant
        records.append(
            {
                "file_path": output_exe_name,
                "requires": ["core_executable", "mobile_sound_assets"],
                "note": (
                    "Atomic exact-SHA mobile sound route toggle; all four routes are validated "
                    "before one executable write."
                ),
                "variants": list(variants_by_sha.values()),
            }
        )
    return records


def b152_runtime_flag_post_asset_patches(
    executable_sources: list[Path],
    *,
    output_exe_name: str,
    build_manifest_data: dict[str, Any],
    allowed_source_sha256s: set[str] | None = None,
) -> list[dict[str, Any]]:
    return [
        *mobile_furniture_behavior_post_asset_patches(
            executable_sources,
            output_exe_name=output_exe_name,
            build_manifest_data=build_manifest_data,
        ),
        *mobile_sound_assets_post_asset_patches(
            executable_sources,
            output_exe_name=output_exe_name,
            build_manifest_data=build_manifest_data,
            allowed_source_sha256s=allowed_source_sha256s or set(),
        ),
        *holiday_furniture_goal_post_asset_patches(
            executable_sources,
            output_exe_name=output_exe_name,
            build_manifest_data=build_manifest_data,
        ),
        *older_pregnancy_post_asset_patches(
            executable_sources,
            output_exe_name=output_exe_name,
            build_manifest_data=build_manifest_data,
        ),
        *same_sex_marriage_post_asset_patches(
            executable_sources,
            output_exe_name=output_exe_name,
            build_manifest_data=build_manifest_data,
        ),
        *older_mortality_post_asset_patches(
            executable_sources,
            output_exe_name=output_exe_name,
            build_manifest_data=build_manifest_data,
        ),
    ]


def pe_structure_identity(structure: Any) -> dict[str, Any] | None:
    if not isinstance(structure, dict):
        return None
    sections = structure.get("sections")
    if not isinstance(sections, list):
        return None
    identity_sections = []
    for section in sections:
        if not isinstance(section, dict):
            return None
        identity_sections.append(
            {
                "name": section.get("name"),
                "virtual_address": section.get("virtual_address"),
                "virtual_size": section.get("virtual_size"),
                "raw_data_pointer": section.get("raw_data_pointer"),
                "raw_data_size": section.get("raw_data_size"),
                "characteristics": section.get("characteristics"),
            }
        )
    return {
        "format": structure.get("format"),
        "pe_offset": structure.get("pe_offset"),
        "machine": structure.get("machine"),
        "number_of_sections": structure.get("number_of_sections"),
        "characteristics": structure.get("characteristics"),
        "optional_header_size": structure.get("optional_header_size"),
        "optional_magic": structure.get("optional_magic"),
        "address_of_entry_point": structure.get("address_of_entry_point"),
        "image_base": structure.get("image_base"),
        "section_alignment": structure.get("section_alignment"),
        "file_alignment": structure.get("file_alignment"),
        "size_of_image": structure.get("size_of_image"),
        "subsystem": structure.get("subsystem"),
        "sections": identity_sections,
    }


def load_official_vf2_pe_structures() -> list[dict[str, Any]]:
    if not OFFICIAL_PE_STRUCTURES_FILE.is_file():
        return []
    data = json.loads(OFFICIAL_PE_STRUCTURES_FILE.read_text(encoding="utf-8"))
    raw_structures = data.get("structures") if isinstance(data, dict) else None
    if not isinstance(raw_structures, list):
        raise ValueError(f"{OFFICIAL_PE_STRUCTURES_FILE} must contain a structures array.")
    structures = []
    for index, structure in enumerate(raw_structures):
        if pe_structure_identity(structure) is None:
            raise ValueError(f"{OFFICIAL_PE_STRUCTURES_FILE} structure #{index} is not a valid PE identity record.")
        structures.append(structure)
    return structures


def accepted_vf2_pe_structures(vanilla_exe: Path, accepted_exes: list[Path] | None = None) -> list[dict[str, Any]]:
    structures: list[dict[str, Any]] = []
    for exe in [vanilla_exe, *(accepted_exes or [])]:
        pe_structure = pe_structure_fingerprint(exe)
        if pe_structure is not None:
            structures.append(pe_structure)
    structures.extend(load_official_vf2_pe_structures())

    unique: list[dict[str, Any]] = []
    seen = set()
    for structure in structures:
        identity = pe_structure_identity(structure)
        if identity is None:
            continue
        key = json.dumps(identity, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(structure)
    return unique


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
        elif "/Images/" in text or "/Assets/" in text:
            for marker in ("/Images/", "/Assets/"):
                if marker in text:
                    root_name = marker.strip("/")
                    candidates.append(root_name + "/" + text.split(marker, 1)[1])
                    break
        elif text.startswith((
            "Furniture/",
            "VillagerBodies/",
            "VillagerDetailBodies/",
            "OutfitIcons/",
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


def target_file_record(
    vanilla_exe: Path,
    target_exe_name: str,
    accepted_exes: list[Path] | None = None,
    *,
    use_pe_structures: bool = True,
) -> dict[str, Any]:
    pe_structures = accepted_vf2_pe_structures(vanilla_exe, accepted_exes) if use_pe_structures else []
    record = {
        "path": target_exe_name,
        "note": "Verified vanilla VF2 PC executable by exact SHA-256 and file size; PE layout is supplemental metadata.",
        "sha256": sha256_file(vanilla_exe),
        "size": vanilla_exe.stat().st_size,
    }
    if pe_structures:
        record["pe_structures"] = pe_structures
    return record


def load_target_identity_from_manifest(manifest_path: Path, target_exe_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load reusable EXE validation metadata from a previously exported manifest."""
    manifest = load_json(manifest_path)
    for row in manifest.get("target_files", []):
        if row.get("path") != target_exe_name:
            continue
        if row.get("sha256") and row.get("size") is not None:
            structures = row.get("pe_structures")
            target_record = {
                "path": target_exe_name,
                "note": "Verified vanilla VF2 PC executable by exact SHA-256 and file size reused from a bundled patcher manifest.",
                "sha256": row["sha256"],
                "size": row["size"],
            }
            identity_fields = {
                "expected_target_sha256": row["sha256"],
                "expected_target_size": row["size"],
            }
            if structures:
                target_record["pe_structures"] = structures
                identity_fields["expected_target_pe_structures"] = structures
            return (
                target_record,
                identity_fields,
            )
        if row.get("pe_structures"):
            raise ValueError(
                f"Reusable target identity for {target_exe_name!r} has PE structure metadata but no exact SHA-256."
            )
    for row in manifest.get("asset_patches", []):
        if row.get("file_path") != target_exe_name:
            continue
        if row.get("expected_target_sha256") and row.get("expected_target_size") is not None:
            structures = row.get("expected_target_pe_structures")
            target_record = {
                "path": target_exe_name,
                "note": "Verified vanilla VF2 PC executable by exact SHA-256 and file size reused from a bundled patcher manifest.",
                "sha256": row["expected_target_sha256"],
                "size": row["expected_target_size"],
            }
            identity_fields = {
                "expected_target_sha256": row["expected_target_sha256"],
                "expected_target_size": row["expected_target_size"],
            }
            if structures:
                target_record["pe_structures"] = structures
                identity_fields["expected_target_pe_structures"] = structures
            return (
                target_record,
                identity_fields,
            )
        if row.get("expected_target_pe_structures"):
            raise ValueError(
                f"Reusable target identity for {target_exe_name!r} has PE structure metadata but no exact SHA-256."
            )
    raise ValueError(f"No reusable target identity for {target_exe_name!r} found in {manifest_path}")


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
    if parts and parts[0] == "Sounds" and rel_path.name in MOBILE_SOUND_ASSET_FILES:
        return "mobile_sound_assets"
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
    if (
        text.startswith("Images/CollectionOrnaments/")
        or "CollectionOrnament" in stem
        or stem == "collection-ornaments_background"
        or stem == "collectables_small"
    ):
        return "holiday_ornaments_collection"
    if text.startswith("Images/MobileRenovations/"):
        return "mobile_renovations"
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
    if stem.startswith("cheat_"):
        return "cheat_upgrades"
    if stem in MOBILE_PURCHASE_ICON_FILES:
        return "mobile_purchases"
    if text.startswith("Images/OutfitIcons/") or text.startswith("Images/OutfitStoreIcons/") or stem.startswith(("female_", "male_")):
        return "outfit_store_expansion"
    if parts and parts[0] in {"Images", "Assets"}:
        return "mobile_furniture"
    return "core_assets"


def asset_requires_for_setting(setting: str) -> list[str]:
    if setting in {
        "vf3_tv_assets_recognition",
        "vf3_furniture",
        "behavior_patches",
        "mobile_renovations",
        "mobile_sound_assets",
        "cheat_upgrades",
    }:
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


def iter_candidate_assets(
    build_dir: Path,
    manifest_data: dict[str, Any],
    asset_mode: str,
    asset_filter: Callable[[Path], bool] | None = None,
) -> list[Path]:
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
            if asset_filter is not None and not asset_filter(rel):
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
                rel = path.relative_to(build_dir)
                if rel.suffix.lower() == ".bak":
                    continue
                if allowed_paths is not None and rel not in allowed_paths:
                    continue
                if asset_filter is not None and not asset_filter(rel):
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
    asset_filter: Callable[[Path], bool] | None = None,
) -> list[dict[str, Any]]:
    payload_root = bundle_dir / "payload"
    asset_patches: list[dict[str, Any]] = []
    candidate_assets = iter_candidate_assets(build_dir, manifest_data, asset_mode, asset_filter)
    for dirname in SOURCE_ONLY_PAYLOAD_DIRS:
        source_root = build_dir / dirname
        if not source_root.is_dir():
            continue
        for source in source_root.rglob("*"):
            if not source.is_file():
                continue
            rel = source.relative_to(build_dir)
            if not is_full_payload_candidate(rel):
                continue
            target = payload_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    for source in candidate_assets:
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

        setting = setting_for_asset(rel)
        record = {
            "file_path": relative_posix(rel),
            "source_path": relative_posix(Path("payload") / rel),
            "source_sha256": source_sha,
            "source_size": source_size,
            "allow_missing_target": asset_mode == "additive",
            "requires": asset_requires_for_setting(setting),
            "remove_when_disabled": (
                setting in OUTPUT_ONLY_REMOVABLE_ASSET_SETTINGS
                and rel.suffix.lower() != ".exe"
            ),
            "note": f"Generated asset payload for {relative_posix(rel)}.",
        }
        invisible_base_build_source = build_dir / INVISIBLE_BASE_SOURCE_DIR / rel.name
        if is_invisible_furniture_image(rel) and invisible_base_build_source.is_file():
            base_source_rel = Path("payload") / INVISIBLE_BASE_SOURCE_DIR / rel.name
            base_payload_target = bundle_dir / base_source_rel
            base_payload_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(invisible_base_build_source, base_payload_target)
            record["source_path"] = relative_posix(base_source_rel)
            record["source_sha256"] = sha256_file(base_payload_target)
            record["source_size"] = base_payload_target.stat().st_size
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


def export_setting_overlay_asset_payloads(
    overlay_build_dir: Path,
    base_payload: Path,
    bundle_dir: Path,
    setting_id: str,
    asset_mode: str,
    build_label: str,
) -> list[dict[str, Any]]:
    manifest_path = overlay_build_dir / "patch-manifest.json"
    if not manifest_path.is_file():
        return []
    overlay_manifest = load_json(manifest_path)
    records = export_asset_payloads(
        overlay_build_dir,
        base_payload,
        bundle_dir,
        overlay_manifest,
        asset_mode,
        build_label,
        asset_filter=lambda rel: setting_for_asset(rel) == setting_id,
    )
    for record in records:
        record["requires"] = asset_requires_for_setting(setting_id)
        record["note"] = f"{setting_id} overlay asset payload for {record['file_path']}."
    return records


def append_unique_asset_records(asset_patches: list[dict[str, Any]], records: list[dict[str, Any]]) -> None:
    existing = {
        (row.get("file_path"), tuple(row.get("requires", [])))
        for row in asset_patches
    }
    for record in records:
        key = (record.get("file_path"), tuple(record.get("requires", [])))
        if key in existing:
            continue
        asset_patches.append(record)
        existing.add(key)


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
                f"Uses the bundled explicit lock_{generation:02d}.png frame."
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


def mobile_sound_asset_patches(
    bundle_dir: Path,
    base_payload: Path,
    source_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Stage the four hash-pinned mobile OGGs behind one default-off setting."""
    resolved_source_dir = source_dir or MOBILE_SOUND_ASSET_SOURCE_DIR
    if not resolved_source_dir.is_dir():
        raise ValueError(f"Mobile sound assets directory does not exist: {resolved_source_dir}")
    validated = []
    for filename in MOBILE_SOUND_ASSET_FILES:
        source = resolved_source_dir / filename
        if not source.is_file():
            raise ValueError(f"Missing mobile sound asset: {source}")
        data = source.read_bytes()
        expected_sha = MOBILE_SOUND_ASSET_PINS[filename]
        actual_sha = hashlib.sha256(data).hexdigest()
        if actual_sha != expected_sha or not data.startswith(b"OggS"):
            raise ValueError(f"Mobile sound asset identity mismatch: {source}")
        validated.append((filename, source, data, actual_sha))

    payload_root = bundle_dir / "payload"
    payload_sound_dir = payload_root / "MobileSoundAssets"
    records: list[dict[str, Any]] = []
    payload_sound_dir.mkdir(parents=True, exist_ok=True)
    prior = {payload_sound_dir / filename: (payload_sound_dir / filename).read_bytes() if (payload_sound_dir / filename).is_file() else None for filename in MOBILE_SOUND_ASSET_FILES}
    try:
        with tempfile.TemporaryDirectory(prefix="vf2-mobile-sounds-", dir=bundle_dir) as tmp:
            stage = Path(tmp)
            staged = []
            for filename, source, data, actual_sha in validated:
                staged_path = stage / filename
                staged_path.write_bytes(data)
                if hashlib.sha256(staged_path.read_bytes()).hexdigest() != actual_sha:
                    raise ValueError(f"Staged mobile sound verification failed: {filename}")
                staged.append((filename, source, actual_sha, staged_path))
            for filename, source, actual_sha, staged_path in staged:
                payload = payload_sound_dir / filename
                staged_path.replace(payload)
                target_rel = Path("Sounds") / filename
                base_target = base_payload / target_rel
                record: dict[str, Any] = {
                    "file_path": relative_posix(target_rel),
                    "source_path": relative_posix(payload.relative_to(bundle_dir)),
                    "source_sha256": actual_sha,
                    "source_size": payload.stat().st_size,
                    "overwrite_existing": True,
                    "allow_missing_target": True,
                    "remove_when_disabled": MOBILE_SOUND_PC_FILENAMES[filename].lower() != filename.lower(),
                    "requires": ["core_executable", "mobile_sound_assets"],
                    "note": (
                        "Optional mobile OGG sound route. Enable mobile_sound_assets to stage this asset; "
                        "disabling the setting removes only the exact pinned OGG target."
                    ),
                }
                if base_target.is_file():
                    record["expected_target_sha256"] = sha256_file(base_target)
                    record["expected_target_size"] = base_target.stat().st_size
                    restore = payload_root / "OriginalMobileSoundAssets" / filename
                    restore.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(base_target, restore)
                    record["restore_source_path"] = relative_posix(restore.relative_to(bundle_dir))
                    record["restore_source_sha256"] = sha256_file(restore)
                    record["restore_source_size"] = restore.stat().st_size
                records.append(record)
    except Exception:
        for path, old_data in prior.items():
            if old_data is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(old_data)
        raise
    return records


def mobile_furniture_behavior_asset_patches(
    bundle_dir: Path,
    base_payload: Path,
) -> list[dict[str, Any]]:
    if not MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR.is_dir():
        return []
    base_maps = [
        base_payload / "Assets" / filename
        for filename in MOBILE_FURNITURE_BEHAVIOR_FMAP_FILES
    ]
    present_base_maps = [path for path in base_maps if path.is_file()]
    if not present_base_maps:
        return []
    if len(present_base_maps) != len(base_maps):
        missing = ", ".join(path.name for path in base_maps if not path.is_file())
        raise ValueError(
            f"Base payload has an incomplete implemented mobile-furniture map set; missing: {missing}"
        )
    payload_root = bundle_dir / "payload"
    enabled_dir = payload_root / "MobileFurnitureBehaviorFmaps"
    restore_dir = payload_root / "OriginalMobileFurnitureBehaviorFmaps"
    enabled_dir.mkdir(parents=True, exist_ok=True)
    restore_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for filename in MOBILE_FURNITURE_BEHAVIOR_FMAP_FILES:
        source = MOBILE_FURNITURE_BEHAVIOR_PC_FMAP_DIR / filename
        if not source.is_file():
            raise ValueError(f"Missing mobile furniture behavior map: {source}")
        target_rel = Path("Assets") / filename
        original = base_payload / target_rel
        if not original.is_file():
            raise ValueError(
                f"Base payload is missing sanitized mobile furniture map: {original}"
            )
        payload_source = enabled_dir / filename
        payload_restore = restore_dir / filename
        shutil.copy2(source, payload_source)
        shutil.copy2(original, payload_restore)
        records.append({
            "file_path": relative_posix(target_rel),
            "source_path": relative_posix(payload_source.relative_to(bundle_dir)),
            "source_sha256": sha256_file(payload_source),
            "source_size": payload_source.stat().st_size,
            "expected_target_sha256": sha256_file(original),
            "expected_target_size": original.stat().st_size,
            "restore_source_path": relative_posix(payload_restore.relative_to(bundle_dir)),
            "restore_source_sha256": sha256_file(payload_restore),
            "restore_source_size": payload_restore.stat().st_size,
            "overwrite_existing": True,
            # A clean vanilla install has no mobile-furniture fmap. The base
            # mobile-furniture record creates the sanitized map earlier in the
            # same apply operation before this optional overlay replaces it.
            "allow_missing_target": True,
            "requires": ["core_executable", "mobile_furniture_behaviors"],
            "note": (
                "Optional implemented mobile-furniture EObject-only map. "
                "Disabling the setting restores the exact rendered-only map."
            ),
        })
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
    if invisible_source_dir is None:
        bundled_invisible = OPTIONAL_PATCH_ASSET_DIR / "invisible_workspace_upgrades" / "invisible images"
        if bundled_invisible.is_dir():
            invisible_source_dir = bundled_invisible
    if original_source_dir is None:
        bundled_original = OPTIONAL_PATCH_ASSET_DIR / "invisible_workspace_upgrades" / "original images"
        if bundled_original.is_dir():
            original_source_dir = bundled_original
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
                "remove_when_disabled": (
                    setting in OUTPUT_ONLY_REMOVABLE_ASSET_SETTINGS
                    and target_rel.suffix.lower() != ".exe"
                ),
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


def copy_optional_patch_asset(
    source_rel: Path,
    payload_rel: Path,
    bundle_dir: Path,
) -> Path | None:
    source = OPTIONAL_PATCH_ASSET_DIR / source_rel
    if not source.is_file():
        return None
    target = bundle_dir / "payload" / payload_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def optional_patch_asset_patches(bundle_dir: Path) -> list[dict[str, Any]]:
    payload_root = bundle_dir / "payload"
    records: list[dict[str, Any]] = []
    specs = [
        {
            "setting": "misc_graphics_fixes",
            "asset_source": Path("misc_graphics_fixes") / "superFridge_NW.png",
            "payload_rel": Path("OptionalVisualMods") / "Misc Graphics Fixes" / "superFridge_NW.png",
            "target_rel": Path("Images") / "Upgrades" / "superFridge_NW.png",
            "restore_rel": Path("Original Virtual Families 2 Assets") / "originalimages" / "Upgrades" / "superFridge_NW.png",
            "note": "Optional misc graphics fix: Super Fridge ice maker position.",
        },
        {
            "setting": "glowing_collectibles",
            "asset_source": Path("glowing_collectibles") / "collectables_small.png",
            "payload_rel": Path("OptionalVisualMods") / "Glowing Collectibles" / "collectables_small.png",
            "target_rel": Path("Images") / "collectables_small.png",
            "restore_rel": Path("Original Virtual Families 2 Assets") / "originalimages" / "collectables_small.png",
            "note": "Optional glowing collectibles visibility sheet.",
        },
    ]
    for spec in specs:
        source = copy_optional_patch_asset(spec["asset_source"], spec["payload_rel"], bundle_dir)
        if source is None:
            continue
        record: dict[str, Any] = {
            "file_path": relative_posix(spec["target_rel"]),
            "source_path": relative_posix(source.relative_to(bundle_dir)),
            "source_sha256": sha256_file(source),
            "source_size": source.stat().st_size,
            "overwrite_existing": True,
            "requires": [str(spec["setting"])],
            "note": str(spec["note"]),
        }
        restore = payload_root / spec["restore_rel"]
        if restore.is_file():
            record.update(
                {
                    "restore_source_path": relative_posix(restore.relative_to(bundle_dir)),
                    "restore_source_sha256": sha256_file(restore),
                    "restore_source_size": restore.stat().st_size,
                }
            )
        records.append(record)
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
            sha_key = "restore_source_sha256" if key == "restore_source_path" else "source_sha256"
            size_key = "restore_source_size" if key == "restore_source_path" else "source_size"
            expected_sha = record.get(sha_key)
            if expected_sha and sha256_file(resolved).lower() != str(expected_sha).lower():
                raise ValueError(f"asset patch #{index} {key} SHA-256 does not match {sha_key}")
            expected_size = record.get(size_key)
            if expected_size is not None and resolved.stat().st_size != int(expected_size):
                raise ValueError(f"asset patch #{index} {key} size does not match {size_key}")


def prune_unreferenced_payload_files(
    bundle_dir: Path,
    asset_patches: list[dict[str, Any]],
) -> dict[str, int]:
    """Remove payload files that no manifest asset record can ever read."""

    bundle_root = bundle_dir.resolve()
    payload_root = (bundle_root / "payload").resolve()
    if not payload_root.is_dir():
        return {
            "removed_file_count": 0,
            "removed_bytes": 0,
            "retained_file_count": 0,
            "retained_bytes": 0,
        }

    referenced: set[Path] = set()
    for record in asset_patches:
        for key in ("source_path", "restore_source_path"):
            rel_text = record.get(key)
            if not rel_text:
                continue
            resolved = (bundle_root / Path(str(rel_text))).resolve()
            if resolved == payload_root or payload_root in resolved.parents:
                referenced.add(resolved)

    removed_file_count = 0
    removed_bytes = 0
    for path in sorted(payload_root.rglob("*")):
        if not path.is_file() or path.resolve() in referenced:
            continue
        removed_file_count += 1
        removed_bytes += path.stat().st_size
        path.unlink()

    directories = sorted(
        (path for path in payload_root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for path in directories:
        try:
            path.rmdir()
        except OSError:
            pass

    retained_files = [path for path in payload_root.rglob("*") if path.is_file()]
    return {
        "removed_file_count": removed_file_count,
        "removed_bytes": removed_bytes,
        "retained_file_count": len(retained_files),
        "retained_bytes": sum(path.stat().st_size for path in retained_files),
    }


def modded_exe_output_name(build_label: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", build_label).strip("._") or "Modded"
    if label.upper() == "B156":
        return "Virtual Families 2 - Modded.exe"
    return MODDED_EXE_OUTPUT_TEMPLATE.format(build_label=label)


def modded_output_folder_name(build_label: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", build_label).strip("._") or "Modded"
    if label.upper() == "B156":
        return "Virtual Families 2 - Modded"
    return MODDED_OUTPUT_FOLDER_TEMPLATE.format(build_label=label)


def modded_save_folder_name(build_label: str) -> str:
    return Path(modded_exe_output_name(build_label)).stem


def export_exe_replacement_payload(
    *,
    bundle_dir: Path,
    patched_exe: Path,
    vanilla_exe: Path | None,
    accepted_exes: list[Path] | None,
    target_exe_name: str,
    build_label: str,
    target_identity_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require_vf2_pe32_x86(patched_exe, label="Patched executable payload")
    output_exe_name = modded_exe_output_name(build_label)
    payload_rel = Path("payload") / output_exe_name
    payload_target = bundle_dir / payload_rel
    payload_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(patched_exe, payload_target)
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
    if target_identity_fields:
        record.update(target_identity_fields)
        if "expected_target_sha256" not in record:
            raise ValueError(
                "Target identity manifest must provide an exact executable SHA-256; "
                "PE structure metadata is supplemental only."
            )
    elif vanilla_exe is not None:
        pe_structures = accepted_vf2_pe_structures(vanilla_exe, accepted_exes)
        if pe_structures:
            record["expected_target_pe_structures"] = pe_structures
        record["expected_target_sha256"] = sha256_file(vanilla_exe)
        record["expected_target_size"] = vanilla_exe.stat().st_size
    else:
        raise ValueError("EXE replacement export requires --vanilla-exe or --target-identity-manifest.")
    return record


def export_optional_exe_overlay_payload(
    *,
    bundle_dir: Path,
    source_exe: Path,
    target_exe_name: str,
    output_exe_name: str,
    setting_id: str | None = None,
    requires: list[str] | None = None,
    payload_name: str,
    note: str,
    target_identity_fields: dict[str, Any],
) -> dict[str, Any]:
    require_vf2_pe32_x86(source_exe, label="Optional executable overlay")
    payload_rel = Path("payload") / payload_name
    payload_target = bundle_dir / payload_rel
    payload_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_exe, payload_target)
    record = {
        "file_path": target_exe_name,
        "output_file_path": output_exe_name,
        "source_path": relative_posix(payload_rel),
        "source_sha256": sha256_file(payload_target),
        "source_size": payload_target.stat().st_size,
        "overwrite_existing": True,
        "requires": requires if requires is not None else ["core_executable", setting_id],
        "note": note,
    }
    record.update(target_identity_fields)
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
        match = re.search(r"\bB\d+(?:\.\d+)?\b", text, flags=re.IGNORECASE)
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
    shutil.copy2(SOURCE_DIR / "vf2_crash_capture.py", bundle_dir / "vf2_crash_capture.py")
    (bundle_dir / "crash-capture-manifest.template.json").write_text(
        json.dumps(
            {
                "schema": "vf2-crash-capture/v1",
                "executable": {"path": "", "size": 0, "sha256": ""},
                "capture": {
                    "dump": {"path": "crash.dmp", "size": 0, "sha256": ""},
                    "logs": [{"path": "ldwLog.txt", "size": 0, "sha256": ""}],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="ascii",
    )
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

{PROJECT_CREATOR_MESSAGE}

{SAVE_COMPATIBILITY_NOTE}

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

B151 changelog
--------------
{chr(10).join(B151_CHANGELOG_LINES)}
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

Check for updates:
{PATCHER_RELEASES_URL}

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

Crash capture QA only (optional):
The patcher never changes Windows Error Reporting settings or launches the
game. If a test build crashes, copy crash-capture-manifest.template.json to a
new file and fill in the absolute path, byte size, and SHA-256 of the exact
modded EXE. Run vf2_crash_capture.py verify-exe first, then use its
emit-wer-plan command to generate separate reviewable setup and restore scripts.
They are inert until you choose to run them manually: run setup, reproduce and
capture the crash, and then run restore. After a crash,
record the dump/log sizes and hashes in the separate capture manifest, run
validate-bundle, and only then emit the IDA JSON. Never substitute manifest.json
for this exact-build crash manifest.

Existing saves:
{SAVE_COMPATIBILITY_NOTE}
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
        "vf2_crash_capture.py",
        "crash-capture-manifest.template.json",
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
        "vf2_crash_capture.py",
        "crash-capture-manifest.template.json",
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
        f"Generated bundle folder: {bundle_dir.name}",
        f"Source build folder: {source_build.get('build_dir')}",
        f"Source build manifest: {source_build.get('build_manifest')}",
        f"Patched EXE source: {source_build.get('patched_exe')}",
        f"Official patcher release repo: {PATCHER_RELEASE_REPO_DISPLAY_NAME}",
        f"Release URL: {PATCHER_RELEASES_URL}",
        "",
        "Creation disclosure",
        "-------------------",
        PROJECT_CREATOR_MESSAGE,
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
        f"- Unreachable payload files pruned during export: {summary.get('payload_pruning', {}).get('removed_file_count', 0)} ({summary.get('payload_pruning', {}).get('removed_bytes', 0)} bytes)",
        "- Every retained payload file is reachable through a manifest source_path or restore_source_path; every retained source is revalidated after pruning.",
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
        f"- {SAVE_COMPATIBILITY_NOTE}",
        "- Modded saves are expected under Documents/LDW/(name of modded Virtual Families 2 exe).",
        "- Existing Virtual Families 2 saves can be used by copying the contents of the original Documents/LDW/Virtual Families 2 save folder into the modded save folder.",
        "- Existing saves remain unaltered in the original save folder.",
        "",
        "Settings and defaults",
        "---------------------",
        "- Main Patches (green): core patches, mobile-exclusive furniture, Holiday furniture, and Holiday outfits.",
        "- Optional Patches (black): Holiday Ornaments, Settings Evict, Island Events, Allow Older Pregnancies, Older Villager Mortality Curve, mobile furniture behaviors, optional visual swaps, Invisible Furniture graphics modes, custom maps, LDW Posters/Paintings, and Colorful Couches.",
        "",
        "B153 native feature gating",
        "--------------------------",
        "- The B153 package carries 16 executable overlays: core plus all 15 non-empty combinations of Island Events, Cheat Upgrades, Holiday Ornaments, and Behavior Patches.",
        "- The patcher selects exactly one matching overlay from the enabled-setting combination; disabling a native feature selects an executable built without that feature's patch functions.",
        "- Behavior variations, autonomous candidates, direct sink subroutines, and exact normal-praise label capture/restore require behavior_patches.",
        "- Cheat rows, price multipliers/reset, Trigger/Fix malfunction actions, Router offline/online changes, and reversible Maid/Gardener/Rockhound/Anti-Spam handling require cheat_upgrades.",
        "- Dryer lint fire remains a stock random malfunction gated on Dryer object 0x48; native repair clears prop 0x21 and advances Handyman.",
        "- The six-page/72-item collection and Holiday-aware count require holiday_ornaments_collection. Brokerage 11% wording follows mobile_purchases.",
        "- Holiday Furniture goals 0x6D-0x7F use an exact-SHA .vf2goal post-asset byte enabled only with core_executable plus holiday_furniture.",
        "- Allow Older Pregnancies is a default-off exact-SHA post-asset toggle of the dormant .vf2preg byte; age-50+ failed attempts skip the stock cooldown deadline write. The same byte permits the native Next Generation flow when the oldest active living non-departed villager reaches age 60 while still requiring a surviving child. Native StartNextGeneration and its 30-record MakeRoomInTree rollover remain unchanged. The setting does not add another executable overlay dimension.",
        "- Allow Same-Sex Marriage is a default-off exact-SHA post-asset toggle of the dormant .vf2same byte. Proposals may offer either gender; the native two-parent family-tree records are preserved, same-sex spouses can repeat the private romantic action, and normal or cheat-forced pregnancy remains 0%.",
        "- Older Villager Mortality Curve is a default-off exact-SHA post-asset toggle of the dormant .vf2mort byte; flag-off resumes the stock old-age block and it does not add another executable overlay dimension.",
        "- F5 enables and toggles the native debugger overlay; Up/Down change pages, F6 selects Waypoint Editor, F7 selects Light Source Editor, and F4 exits an editor. B153 recognizes VF2's internal key codes as well as Win32/SDL fallbacks.",
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
            "This bundle uses verified modified EXE payloads for native/game-code changes. "
            "B153 isolates Island Events, Cheat Upgrades, Holiday Ornaments, and Behavior Patches with a complete 16-state executable overlay matrix; Holiday Furniture goals, Allow Older Pregnancies, and Older Villager Mortality use independent post-asset runtime bytes so they do not expand that matrix. Every B153 executable also contains the guarded F5 debugger route with validated internal key codes."
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
            f"- Post-asset patch records: {summary.get('post_asset_patch_count')}",
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
            "- B115 patcher refresh: Asset records marked up-to-date during validation are rechecked during apply. This prevents an output-folder refresh from deleting an already-up-to-date modded EXE and then skipping the EXE rewrite.",
            "- B116 game build: Behavior Patches enable child-only Playing quietly at the Kids Table through native behavior 0x130. Invisible Kids Table and Chairs keeps the base KidsTableAndChairsStd donor item/fmap route with no outside asset-folder dependency.",
            "- B117 game build: Spontaneous Playhouse stays child-only and is refreshed through native CNight::AIIsDayTime(), so the AI candidate is disabled at night.",
            "- B118 game build: Re-enabled the Settings Evict button by NOPing the two stock constructor skip branches in the existing theOptionsDialog Evict setup. The native confirmation dialog and CFamilyTree::EvictFamily handler are unchanged.",
            "- B119 game build: Settings Evict also inserts the missing ldwScene::AddControl call for the constructed Evict button, which B118 did not do.",
            "- B121 game build: Settings Evict warning text is explicitly line-broken so the stock dialog renderer keeps it inside the modal bounds.",
            "- B121 patcher refresh: Adds default-off Misc Graphics Fixes and Glowing Collectibles optional asset swaps, each with bundled vanilla restore sources.",
            "- B131 game build: Behavior Patches add grouped visible-label variants for native TV, web, video game, radio, reading, petting, mending, ironing, telescope, workout, career, shower/bath, coffee/tea, cocktail, pool, sandbox, toy train, playground, and snow-play routes. The wrappers preserve the original behavior plans and only change the displayed action text.",
            "- B131 patcher refresh: Cheat Upgrades adds Unlock all furniture under Special Upgrades. It toggles live furniture generation locks to 0 and restores the generated original-lock snapshot if bought again.",
            "- B131 patcher refresh: Adds an Experimental/Not Working Expand game map setting placeholder so the planned map expansion is documented but not presented as implemented.",
            "- B132 game build: Water Pressure Surge now sets north bathroom leak props 0x48, 0x49, and 0x4A when the second-bathroom renovation 0xE6 exists, and CVillager::NewBehavior routes those active props to the native north leak reactions.",
            "- B133 patcher refresh: Moves Settings Evict and Island Events into Optional Patches now that their button/event records are implemented; Experimental/Not Working remains for Holiday Ornaments, mobile furniture behaviors, Expand game map, and future unstable work.",
            "- B134 build/export refresh: FurnitureManager's generated itemInfo table is exported for helper objects so Cheat Upgrades can link the Unlock all furniture generation-lock toggle, and the Island Events helper template now emits valid C++ registrations for the optional overlay.",
            "- B135 patcher refresh: Source-only payload folders are copied whenever present, even when no normal asset diffs exist, so OptionalSongMods and Original Virtual Families 2 Assets/originalsounds restore files stay self-contained in the patcher ZIP.",
            "- B136 patcher refresh: Exact install-shape validation now tolerates top-level game EXE files separately from required folder/runtime entries, and generated manifests embed both known official VF2 PC PE layouts so older official install EXEs remain accepted without outside files.",
            "- B138 game build: Flea Market store rows now use the full native eligible sale pool from item IDs 0x1AD-0x2A8 by detouring GetCategoryItemCount/GetCategoryItem for category 3. The stock three-slot random cache is left untouched, and the helper keeps native locked-item, pet, and AvailableForSale filters.",
            "- B139 game build: Cheat Upgrades adds Reset Achievements under Special Upgrades. The row calls the stock CAchievement::Reset() routine and then saves the current game through the existing visible-special-upgrade apply path.",
            "- B142 game build: Holiday Ornaments opt-in removes stale outside-file dependencies, uses workspace-local/mobile-atlas art, and wires Mr. B/The Collector's sell branch to reset the Ornamentologist goal row 0x5F after stock ResetCollection() clears the collection table.",
            "- B142 patcher refresh: Holiday Ornaments can ship as a standalone experimental EXE overlay and as combined overlays with Island Events and Cheat Upgrades, so enabling multiple optional native patches no longer drops one overlay.",
            "- B143 game build: Flea Market Expansion now follows the expanded Clothing-section pattern. Category 0x0F returns the fixed 0x24-entry native gGoodiesList pool and reads gGoodiesList[index] directly instead of filtering through the rotating five-item cache.",
            "- B144 game build: Holiday Ornaments are now included in Mr. B/The Collector's CanFire offer and availability counts by adding base collectible 0x9E to the same CollectionCount passes used for the five stock collectible families.",
            "- B145 game build: Holiday Ornaments now extend CCollectionScene::HandleMouse's stock 60-item tooltip rarity lookup with three ornament buckets, preventing the appended page from reading uninitialized stack locals during click/tooltip handling.",
            "- B145 patcher refresh: The exporter can reuse target EXE validation metadata from a previous manifest through --target-identity-manifest, avoiding any dependency on a local vanilla EXE path when rebuilding a portable patcher package.",
            "- B146 game build: Holiday Ornaments now validate the workspace-local collectables_small.png yard sprite sheet against the stock ECarrying - 0x4F frame formula, ensuring ornament values 0x9E-0xA9 map to frames 79-90 in a portable 40x40 six-column sheet.",
            "- B146 patcher refresh: Rebuilt all core, Island Events, Cheat Upgrades, Holiday Ornaments, and combined EXE overlays from the B146 source state so the experimental Holiday Ornaments toggle carries the matching executable and asset payload.",
            "- B152 patcher refresh: Adds exact-SHA .vf2goal Holiday Furniture goal and .vf2preg Allow Older Pregnancies post-asset variants per selected executable payload, preserving the 16-state overlay matrix.",
            "- B147 game build: Holiday Ornaments now validate every bundled collectables_small.png variant that can become the runtime sheet, including the optional Glowing Collectibles replacement, and require nonblank ornament frames 79-90.",
            "- B148 game build: Holiday Ornaments now validate the native collection-state contract before packaging, proving the 0x9E-0xA9 family is covered by Count, SaveState, ResetCollection, page routing, pickup dispatch, observer registration, and Mr. B/The Collector's sell-all reset.",
            "- B149 game build: Holiday Ornaments now validate the collection page-count route, proving DrawScene uses _VF2CollectionPageCount(page) for page 5 while Activate keeps the five stock cached counters and this+0x2C hover field intact.",
            *B150_CHANGELOG_LINES,
            *B151_CHANGELOG_LINES,
            "- B153 game build: Restores the F5-gated native debugger and editor selectors in every executable layout. VF2 internal keys are F4=0x3FD, F5=0x3FE, F6=0x3FF, F7=0x400, Up=0x3EE, and Down=0x3EF.",
            "- B153 game build: Corrects debugger input-hook false fallthrough from JE +4 to JE +6, preventing the prior house-load access violation while keeping unhandled input on the stock route.",
            "- B153 validation: Rebuilds and validates all 16 feature combinations, including unique hashes, debugger hook/key maps, eight Holiday-positive/eight Holiday-negative layouts, reversible exact-SHA runtime toggles, the age-50+ pregnancy cooldown bypass, and the sigma-3/70%-cap mortality helper.",
            "- B154 game build: Allow Older Pregnancies now skips the failed-attempt cooldown when either parent is age 50+, while patch-off and both-under-50 couples retain the stock deadline write.",
            "- B154 game build: Older Villager Mortality preserves one effective bonus year per active food group (0-4), uses the sigma-3 age-75 birthday curve, and caps annual old-age hazard at 99.99% without a hard maximum age.",
            "- B154 game build: Adds Cheat Upgrade 0x12E, Complete all Achievements, through native SetComplete semantics; it and Complete all collections use the trophy icon.",
            "- B154 fixes: Restores the complete A Loan Returned description and corrects Light Source Editor + and - direction without changing other input.",
            "- B154 validation: All 177 tests pass; all 16 unique executable layouts pass debugger, Holiday-positive/negative, runtime-flag ABI, exact-SHA toggle, idempotence, and exact-disable restoration validation.",
            "- B155 game build: Changes only Older Villager Mortality: replaces the sigma-3 age-75 cliff with sex-averaged SSA 2022 annual death probabilities for effective ages 55-105, then a 50% yearly supercentenarian plateau. Active food groups still subtract 0-4 effective years; sickness and every other physiology path remain unchanged.",
            "- B155 validation: All 177 automated tests pass. All 16 unique executable layouts pass corrected B155 Holiday-positive/negative and dormant-runtime validation, including the exact embedded SSA hazard table, 50% tail, and reversible exact-SHA flag toggles.",
            "- B155.5 game build: Changes only Older Villager Mortality: retains the stock 55-plus-food-group threshold, uses a monotonic full-game calibrated millionth-resolution birthday roll, accelerates after effective age 110, never reaches certain old-age death, and imposes no hard maximum age.",
            "- B155.5 calibration: Uses 60 adults per full game. Constant 0-4 food-group cases place modal deaths at ages 72-76; reaching 110 takes about 4.279-2.289 games per success and reaching 122 takes about 2796.10-112.00 games per success.",
            "- B156 patcher refresh: Removes the active Experimental/Not Working section, drops the inactive Expand game map setting, and moves Allow Older Pregnancies, Older Villager Mortality Curve, and mobile furniture behaviors into Optional Patches.",
            "- B156 game build: Allow Older Pregnancies also exposes the native Next Generation flow at displayed age 60 for the oldest active living non-departed villager. Native eligibility remains first, a surviving child is required, native MakeRoomInTree rollover remains intact, and .vf2preg off returns the stock result.",
            "- B119 patcher refresh: The GUI stores the last vanilla install folder and modded output folder in patcher_local_settings.json beside the patcher.",
            "- B119 text fixes: Retargets existing string-table rows so Cooking like mommy becomes Cooking like a grownup and Driving like daddy becomes Driving like a grownup.",
            "- B119 patcher refresh: Supports a bundled Island Events EXE overlay that only applies when the optional Island Events setting is enabled.",
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
    island_events_exe = Path(args.island_events_exe).resolve() if args.island_events_exe else None
    cheat_upgrades_exe = Path(args.cheat_upgrades_exe).resolve() if args.cheat_upgrades_exe else None
    holiday_ornaments_exe = Path(args.holiday_ornaments_exe).resolve() if args.holiday_ornaments_exe else None
    behavior_patches_exe = Path(args.behavior_patches_exe).resolve() if args.behavior_patches_exe else None
    mobile_renovations_exe = Path(args.mobile_renovations_exe).resolve() if args.mobile_renovations_exe else None
    cheat_upgrades_mobile_renovations_exe = (
        Path(args.cheat_upgrades_mobile_renovations_exe).resolve()
        if args.cheat_upgrades_mobile_renovations_exe
        else None
    )
    if cheat_upgrades_mobile_renovations_exe is not None and (
        cheat_upgrades_exe is None or mobile_renovations_exe is None
    ):
        raise ValueError(
            "--cheat-upgrades-mobile-renovations-exe requires both "
            "--cheat-upgrades-exe and --mobile-renovations-exe."
        )
    if (
        cheat_upgrades_exe is not None
        and mobile_renovations_exe is not None
        and cheat_upgrades_mobile_renovations_exe is None
    ):
        raise ValueError(
            "Exporting both cheat_upgrades and mobile_renovations requires "
            "--cheat-upgrades-mobile-renovations-exe."
        )
    island_events_cheat_upgrades_exe = (
        Path(args.island_events_cheat_upgrades_exe).resolve()
        if args.island_events_cheat_upgrades_exe
        else None
    )
    island_events_holiday_ornaments_exe = (
        Path(args.island_events_holiday_ornaments_exe).resolve()
        if args.island_events_holiday_ornaments_exe
        else None
    )
    cheat_upgrades_holiday_ornaments_exe = (
        Path(args.cheat_upgrades_holiday_ornaments_exe).resolve()
        if args.cheat_upgrades_holiday_ornaments_exe
        else None
    )
    island_events_cheat_upgrades_holiday_ornaments_exe = (
        Path(args.island_events_cheat_upgrades_holiday_ornaments_exe).resolve()
        if args.island_events_cheat_upgrades_holiday_ornaments_exe
        else None
    )
    island_events_behavior_patches_exe = (
        Path(args.island_events_behavior_patches_exe).resolve()
        if args.island_events_behavior_patches_exe
        else None
    )
    cheat_upgrades_behavior_patches_exe = (
        Path(args.cheat_upgrades_behavior_patches_exe).resolve()
        if args.cheat_upgrades_behavior_patches_exe
        else None
    )
    holiday_ornaments_behavior_patches_exe = (
        Path(args.holiday_ornaments_behavior_patches_exe).resolve()
        if args.holiday_ornaments_behavior_patches_exe
        else None
    )
    island_events_cheat_upgrades_behavior_patches_exe = (
        Path(args.island_events_cheat_upgrades_behavior_patches_exe).resolve()
        if args.island_events_cheat_upgrades_behavior_patches_exe
        else None
    )
    island_events_holiday_ornaments_behavior_patches_exe = (
        Path(args.island_events_holiday_ornaments_behavior_patches_exe).resolve()
        if args.island_events_holiday_ornaments_behavior_patches_exe
        else None
    )
    cheat_upgrades_holiday_ornaments_behavior_patches_exe = (
        Path(args.cheat_upgrades_holiday_ornaments_behavior_patches_exe).resolve()
        if args.cheat_upgrades_holiday_ornaments_behavior_patches_exe
        else None
    )
    island_events_cheat_upgrades_holiday_ornaments_behavior_patches_exe = (
        Path(args.island_events_cheat_upgrades_holiday_ornaments_behavior_patches_exe).resolve()
        if args.island_events_cheat_upgrades_holiday_ornaments_behavior_patches_exe
        else None
    )
    vanilla_exe = Path(args.vanilla_exe).resolve() if args.vanilla_exe else None
    accepted_vanilla_exes = [Path(path).resolve() for path in args.accepted_vanilla_exe]
    for accepted_exe in accepted_vanilla_exes:
        if not accepted_exe.is_file():
            raise FileNotFoundError(f"Accepted vanilla EXE not found: {accepted_exe}")
    target_exe_name = args.target_exe_name or DEFAULT_EXE_NAME
    target_identity_record = None
    target_identity_fields = None
    if args.target_identity_manifest:
        target_identity_record, target_identity_fields = load_target_identity_from_manifest(
            Path(args.target_identity_manifest).resolve(),
            target_exe_name,
        )
    if args.include_exe_replacement and vanilla_exe is None and target_identity_record is None:
        raise ValueError("--include-exe-replacement requires --vanilla-exe or --target-identity-manifest.")

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
        target_files.append(
            target_file_record(
                vanilla_exe,
                target_exe_name,
                accepted_vanilla_exes,
                use_pe_structures=args.include_exe_replacement,
            )
        )
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
    elif target_identity_record:
        target_files.append(target_identity_record)
        native_status = native_patch_status(
            "target_identity_reused",
            reason=(
                "No --vanilla-exe was supplied; target EXE validation metadata "
                "was reused from --target-identity-manifest."
            ),
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
    if holiday_ornaments_exe is not None:
        holiday_asset_records = export_setting_overlay_asset_payloads(
            holiday_ornaments_exe.parent,
            base_payload,
            bundle_dir,
            "holiday_ornaments_collection",
            args.asset_mode,
            build_label,
        )
        append_unique_asset_records(asset_patches, holiday_asset_records)
    if mobile_renovations_exe is not None:
        renovation_asset_records = export_setting_overlay_asset_payloads(
            mobile_renovations_exe.parent,
            base_payload,
            bundle_dir,
            "mobile_renovations",
            args.asset_mode,
            build_label,
        )
        append_unique_asset_records(asset_patches, renovation_asset_records)
    generation_locks_source = Path(args.generation_locks_dir).resolve() if args.generation_locks_dir else None
    forced_lock_records = generation_lock_asset_patches(build_dir, bundle_dir, generation_locks_source)
    if forced_lock_records:
        forced_paths = {row["file_path"] for row in forced_lock_records}
        asset_patches = [row for row in asset_patches if row.get("file_path") not in forced_paths]
        asset_patches.extend(forced_lock_records)
    optional_song_source = Path(args.optional_song_mods_dir).resolve() if args.optional_song_mods_dir else (
        DEFAULT_OPTIONAL_SONG_MODS_SOURCE if DEFAULT_OPTIONAL_SONG_MODS_SOURCE.is_dir() else None
    )
    asset_patches.extend(optional_song_asset_patches(bundle_dir, base_payload, optional_song_source))
    mobile_sound_source = Path(args.mobile_sound_assets_dir).resolve() if args.mobile_sound_assets_dir else (
        MOBILE_SOUND_ASSET_SOURCE_DIR if MOBILE_SOUND_ASSET_SOURCE_DIR.is_dir() else None
    )
    if (
        args.include_exe_replacement
        and mobile_sound_source is not None
        and isinstance(build_manifest_data.get("MobileSoundAssets"), dict)
    ):
        asset_patches.extend(mobile_sound_asset_patches(bundle_dir, base_payload, mobile_sound_source))
    asset_patches.extend(
        mobile_furniture_behavior_asset_patches(bundle_dir, base_payload)
    )
    invisible_upgrades_source = Path(args.invisible_upgrades_dir).resolve() if args.invisible_upgrades_dir else None
    original_upgrades_source = Path(args.original_upgrades_dir).resolve() if args.original_upgrades_dir else None
    asset_patches.extend(invisible_upgrades_asset_patches(bundle_dir, invisible_upgrades_source, original_upgrades_source))
    asset_patches.extend(optional_visual_asset_patches(bundle_dir))
    asset_patches.extend(optional_patch_asset_patches(bundle_dir))
    exe_replacement_record = None
    output_exe_name = modded_exe_output_name(build_label)
    executable_runtime_flag_sources: list[Path] = []
    if args.include_exe_replacement and (vanilla_exe is not None or target_identity_fields is not None):
        exe_replacement_record = export_exe_replacement_payload(
            bundle_dir=bundle_dir,
            patched_exe=patched_exe,
            vanilla_exe=vanilla_exe,
            accepted_exes=accepted_vanilla_exes,
            target_exe_name=target_exe_name,
            build_label=build_label,
            target_identity_fields=target_identity_fields,
        )
        asset_patches.insert(0, exe_replacement_record)
        executable_runtime_flag_sources.append(patched_exe)
        overlay_specs = [
            (
                island_events_exe,
                "Island Events",
                ["core_executable", "island_events"],
                "Optional Island Events executable overlay. Applied only when core_executable and island_events are enabled.",
            ),
            (
                cheat_upgrades_exe,
                "Cheat Upgrades",
                ["core_executable", "cheat_upgrades"],
                "Optional Cheat Upgrades executable overlay. Applied only when core_executable and cheat_upgrades are enabled.",
            ),
            (
                holiday_ornaments_exe,
                "Holiday Ornaments",
                ["core_executable", "holiday_ornaments_collection"],
                "Optional fully linked Holiday Ornaments executable overlay. Applied only when core_executable and holiday_ornaments_collection are enabled.",
            ),
            (
                behavior_patches_exe,
                "Behavior Patches",
                ["core_executable", "behavior_patches"],
                "Optional Behavior Patches executable overlay. Applied only when core_executable and behavior_patches are enabled.",
            ),
            (
                mobile_renovations_exe,
                "Mobile Room Renovations",
                ["core_executable", "mobile_renovations"],
                "Optional mobile room-renovation executable overlay. Applied only when core_executable and mobile_renovations are enabled.",
            ),
            (
                cheat_upgrades_mobile_renovations_exe,
                "Cheat Upgrades + Mobile Room Renovations",
                ["core_executable", "cheat_upgrades", "mobile_renovations"],
                "Combined optional executable overlay. Applied only when core_executable, cheat_upgrades, and mobile_renovations are enabled.",
            ),
            (
                island_events_cheat_upgrades_exe,
                "Island Events + Cheat Upgrades",
                ["core_executable", "island_events", "cheat_upgrades"],
                "Combined optional executable overlay. Applied only when core_executable, island_events, and cheat_upgrades are enabled.",
            ),
            (
                island_events_holiday_ornaments_exe,
                "Island Events + Holiday Ornaments",
                ["core_executable", "island_events", "holiday_ornaments_collection"],
                "Combined optional executable overlay. Applied only when core_executable, island_events, and holiday_ornaments_collection are enabled.",
            ),
            (
                cheat_upgrades_holiday_ornaments_exe,
                "Cheat Upgrades + Holiday Ornaments",
                ["core_executable", "cheat_upgrades", "holiday_ornaments_collection"],
                "Combined optional executable overlay. Applied only when core_executable, cheat_upgrades, and holiday_ornaments_collection are enabled.",
            ),
            (
                island_events_behavior_patches_exe,
                "Island Events + Behavior Patches",
                ["core_executable", "island_events", "behavior_patches"],
                "Combined optional executable overlay. Applied only when core_executable, island_events, and behavior_patches are enabled.",
            ),
            (
                cheat_upgrades_behavior_patches_exe,
                "Cheat Upgrades + Behavior Patches",
                ["core_executable", "cheat_upgrades", "behavior_patches"],
                "Combined optional executable overlay. Applied only when core_executable, cheat_upgrades, and behavior_patches are enabled.",
            ),
            (
                holiday_ornaments_behavior_patches_exe,
                "Holiday Ornaments + Behavior Patches",
                ["core_executable", "holiday_ornaments_collection", "behavior_patches"],
                "Combined optional executable overlay. Applied only when core_executable, holiday_ornaments_collection, and behavior_patches are enabled.",
            ),
            (
                island_events_cheat_upgrades_holiday_ornaments_exe,
                "Island Events + Cheat Upgrades + Holiday Ornaments",
                ["core_executable", "island_events", "cheat_upgrades", "holiday_ornaments_collection"],
                "Combined optional executable overlay. Applied only when core_executable, island_events, cheat_upgrades, and holiday_ornaments_collection are enabled.",
            ),
            (
                island_events_cheat_upgrades_behavior_patches_exe,
                "Island Events + Cheat Upgrades + Behavior Patches",
                ["core_executable", "island_events", "cheat_upgrades", "behavior_patches"],
                "Combined optional executable overlay. Applied only when core_executable, island_events, cheat_upgrades, and behavior_patches are enabled.",
            ),
            (
                island_events_holiday_ornaments_behavior_patches_exe,
                "Island Events + Holiday Ornaments + Behavior Patches",
                ["core_executable", "island_events", "holiday_ornaments_collection", "behavior_patches"],
                "Combined optional executable overlay. Applied only when core_executable, island_events, holiday_ornaments_collection, and behavior_patches are enabled.",
            ),
            (
                cheat_upgrades_holiday_ornaments_behavior_patches_exe,
                "Cheat Upgrades + Holiday Ornaments + Behavior Patches",
                ["core_executable", "cheat_upgrades", "holiday_ornaments_collection", "behavior_patches"],
                "Combined optional executable overlay. Applied only when core_executable, cheat_upgrades, holiday_ornaments_collection, and behavior_patches are enabled.",
            ),
            (
                island_events_cheat_upgrades_holiday_ornaments_behavior_patches_exe,
                "Island Events + Cheat Upgrades + Holiday Ornaments + Behavior Patches",
                ["core_executable", "island_events", "cheat_upgrades", "holiday_ornaments_collection", "behavior_patches"],
                "Combined optional executable overlay. Applied only when core_executable, island_events, cheat_upgrades, holiday_ornaments_collection, and behavior_patches are enabled.",
            ),
        ]
        # The patcher applies active records in manifest order. Keep overlays
        # ordered from least to most specific so the exact combination wins.
        overlay_specs.sort(key=lambda spec: len(spec[2]))
        overlay_records = []
        overlay_target_identity = {
            key: value
            for key, value in exe_replacement_record.items()
            if key in {
                "expected_target_sha256",
                "expected_target_size",
                "expected_target_pe_structures",
            }
        }
        for source_exe, label, requires, note in overlay_specs:
            if source_exe is None:
                continue
            executable_runtime_flag_sources.append(source_exe)
            overlay_records.append(export_optional_exe_overlay_payload(
                bundle_dir=bundle_dir,
                source_exe=source_exe,
                target_exe_name=target_exe_name,
                output_exe_name=output_exe_name,
                requires=requires,
                payload_name=f"{Path(output_exe_name).stem} - {label}.exe",
                note=note,
                target_identity_fields=overlay_target_identity,
            ))
        asset_patches[1:1] = overlay_records
    overlay_settings = {
        setting
        for row in asset_patches
        if str(row.get("source_path", "")).lower().endswith(".exe")
        for setting in row.get("requires", [])
        if setting in EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS
    }
    # The renderer/code for these features lives in their executable overlays.
    # Do not expose a checkbox or leave loose assets behind when an exporter
    # invocation omitted the matching overlay; that would make a diagnostic
    # core build look selectable while remaining behaviorally inert.
    if EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS - overlay_settings:
        asset_patches = [
            row
            for row in asset_patches
            if not (
                set(row.get("requires", []))
                & (EXECUTABLE_OVERLAY_OPTIONAL_SETTINGS - overlay_settings)
            )
        ]
    validate_bundle_asset_sources(bundle_dir, asset_patches)
    payload_pruning = prune_unreferenced_payload_files(bundle_dir, asset_patches)
    validate_bundle_asset_sources(bundle_dir, asset_patches)
    native_patch_sources = collect_native_patch_sources(build_manifest_data)
    post_asset_patches = b152_runtime_flag_post_asset_patches(
        executable_runtime_flag_sources,
        output_exe_name=output_exe_name,
        build_manifest_data=build_manifest_data,
        allowed_source_sha256s={
            str(row["source_sha256"]).lower()
            for row in asset_patches
            if str(row.get("source_path", "")).lower().endswith(".exe")
            and isinstance(row.get("source_sha256"), str)
        },
    ) if exe_replacement_record is not None else []

    asset_counts_by_setting: dict[str, int] = {}
    for row in asset_patches:
        for setting in row.get("requires", []):
            asset_counts_by_setting[setting] = asset_counts_by_setting.get(setting, 0) + 1
    available_settings = set(asset_counts_by_setting)
    for row in post_asset_patches:
        available_settings.update(row.get("requires", []))

    manifest = {
        "manifest_version": 1,
        "name": args.name or f"VF2 offline patch bundle from {build_dir.name}",
        "build": build_label,
        "build_label": build_label,
        "description": "Generated offline patch bundle for user-provided vanilla VF2 PC installs.",
        "created_with": "Codex AI",
        "creator_disclosure": CREATOR_DISCLOSURE,
        "project_creator_message": PROJECT_CREATOR_MESSAGE,
        "save_compatibility_note": SAVE_COMPATIBILITY_NOTE,
        "output": {
            "default_folder_name": modded_output_folder_name(build_label),
            "default_exe_name": modded_exe_output_name(build_label),
            "default_save_folder_name": modded_save_folder_name(build_label),
            "preserve_stock_exe_icon": exe_replacement_record is not None,
            "description": "The patcher writes a separate clearly labeled modded game folder next to the user's vanilla folder by default.",
        },
        "source_build": {
            "build_dir": build_dir.name,
            "build_manifest": manifest_in.name if manifest_in.is_file() else None,
            "patched_exe": patched_exe.name,
            "island_events_exe": island_events_exe.name if island_events_exe else None,
            "cheat_upgrades_exe": cheat_upgrades_exe.name if cheat_upgrades_exe else None,
            "holiday_ornaments_exe": holiday_ornaments_exe.name if holiday_ornaments_exe else None,
            "behavior_patches_exe": behavior_patches_exe.name if behavior_patches_exe else None,
            "mobile_renovations_exe": mobile_renovations_exe.name if mobile_renovations_exe else None,
            "cheat_upgrades_mobile_renovations_exe": cheat_upgrades_mobile_renovations_exe.name if cheat_upgrades_mobile_renovations_exe else None,
            "island_events_cheat_upgrades_exe": island_events_cheat_upgrades_exe.name if island_events_cheat_upgrades_exe else None,
            "island_events_holiday_ornaments_exe": island_events_holiday_ornaments_exe.name if island_events_holiday_ornaments_exe else None,
            "cheat_upgrades_holiday_ornaments_exe": cheat_upgrades_holiday_ornaments_exe.name if cheat_upgrades_holiday_ornaments_exe else None,
            "island_events_cheat_upgrades_holiday_ornaments_exe": island_events_cheat_upgrades_holiday_ornaments_exe.name if island_events_cheat_upgrades_holiday_ornaments_exe else None,
            "island_events_behavior_patches_exe": island_events_behavior_patches_exe.name if island_events_behavior_patches_exe else None,
            "cheat_upgrades_behavior_patches_exe": cheat_upgrades_behavior_patches_exe.name if cheat_upgrades_behavior_patches_exe else None,
            "holiday_ornaments_behavior_patches_exe": holiday_ornaments_behavior_patches_exe.name if holiday_ornaments_behavior_patches_exe else None,
            "island_events_cheat_upgrades_behavior_patches_exe": island_events_cheat_upgrades_behavior_patches_exe.name if island_events_cheat_upgrades_behavior_patches_exe else None,
            "island_events_holiday_ornaments_behavior_patches_exe": island_events_holiday_ornaments_behavior_patches_exe.name if island_events_holiday_ornaments_behavior_patches_exe else None,
            "cheat_upgrades_holiday_ornaments_behavior_patches_exe": cheat_upgrades_holiday_ornaments_behavior_patches_exe.name if cheat_upgrades_holiday_ornaments_behavior_patches_exe else None,
            "island_events_cheat_upgrades_holiday_ornaments_behavior_patches_exe": island_events_cheat_upgrades_holiday_ornaments_behavior_patches_exe.name if island_events_cheat_upgrades_holiday_ornaments_behavior_patches_exe else None,
            "build_manifest_keys": sorted(build_manifest_data) if build_manifest_data else [],
        },
        "settings": default_settings(
            bool(byte_patches),
            bool(exe_replacement_record),
            available_settings,
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
        "post_asset_patches": post_asset_patches,
        "export_summary": {
            "byte_patch_count": len(byte_patches),
            "native_patch_status": native_status,
            "native_patch_source_count": len(native_patch_sources),
            "asset_patch_count": len(asset_patches),
            "post_asset_patch_count": len(post_asset_patches),
            "asset_counts_by_setting": dict(sorted(asset_counts_by_setting.items())),
            "payload_file_count": count_files(bundle_dir / "payload"),
            "payload_pruning": payload_pruning,
            "base_payload": base_payload.name,
            "asset_mode": args.asset_mode,
            "exe_replacement": exe_replacement_record is not None,
            "target_exe_name": target_exe_name,
            "modded_output_folder_name": modded_output_folder_name(build_label),
            "modded_exe_output_name": modded_exe_output_name(build_label),
            "modded_save_folder_name": modded_save_folder_name(build_label),
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
    parser.add_argument("--target-identity-manifest", help="Previously exported manifest.json to reuse target EXE validation metadata without reading a vanilla EXE.")
    parser.add_argument("--patched-exe", help="Patched EXE filename inside build dir. Auto-detected by default.")
    parser.add_argument("--island-events-exe", help="Optional EXE overlay to apply when island_events is enabled.")
    parser.add_argument("--cheat-upgrades-exe", help="Optional EXE overlay to apply when cheat_upgrades is enabled.")
    parser.add_argument("--holiday-ornaments-exe", help="Optional fully linked EXE overlay to apply when holiday_ornaments_collection is enabled.")
    parser.add_argument("--behavior-patches-exe", help="Optional EXE overlay to apply when behavior_patches is enabled.")
    parser.add_argument("--mobile-renovations-exe", help="Optional EXE overlay to apply when mobile_renovations is enabled.")
    parser.add_argument("--cheat-upgrades-mobile-renovations-exe", help="Combined optional EXE overlay to apply when cheat_upgrades and mobile_renovations are both enabled.")
    parser.add_argument("--island-events-cheat-upgrades-exe", help="Combined optional EXE overlay to apply when island_events and cheat_upgrades are both enabled.")
    parser.add_argument("--island-events-holiday-ornaments-exe", help="Combined optional EXE overlay to apply when island_events and holiday_ornaments_collection are both enabled.")
    parser.add_argument("--cheat-upgrades-holiday-ornaments-exe", help="Combined optional EXE overlay to apply when cheat_upgrades and holiday_ornaments_collection are both enabled.")
    parser.add_argument("--island-events-cheat-upgrades-holiday-ornaments-exe", help="Combined optional EXE overlay to apply when island_events, cheat_upgrades, and holiday_ornaments_collection are all enabled.")
    parser.add_argument("--island-events-behavior-patches-exe", help="Combined optional EXE overlay to apply when island_events and behavior_patches are both enabled.")
    parser.add_argument("--cheat-upgrades-behavior-patches-exe", help="Combined optional EXE overlay to apply when cheat_upgrades and behavior_patches are both enabled.")
    parser.add_argument("--holiday-ornaments-behavior-patches-exe", help="Combined optional EXE overlay to apply when holiday_ornaments_collection and behavior_patches are both enabled.")
    parser.add_argument("--island-events-cheat-upgrades-behavior-patches-exe", help="Combined optional EXE overlay to apply when island_events, cheat_upgrades, and behavior_patches are all enabled.")
    parser.add_argument("--island-events-holiday-ornaments-behavior-patches-exe", help="Combined optional EXE overlay to apply when island_events, holiday_ornaments_collection, and behavior_patches are all enabled.")
    parser.add_argument("--cheat-upgrades-holiday-ornaments-behavior-patches-exe", help="Combined optional EXE overlay to apply when cheat_upgrades, holiday_ornaments_collection, and behavior_patches are all enabled.")
    parser.add_argument("--island-events-cheat-upgrades-holiday-ornaments-behavior-patches-exe", help="Combined optional EXE overlay to apply when island_events, cheat_upgrades, holiday_ornaments_collection, and behavior_patches are all enabled.")
    parser.add_argument("--target-exe-name", default=DEFAULT_EXE_NAME, help="Relative EXE path expected in the user's game folder.")
    parser.add_argument("--name", help="Manifest display name.")
    parser.add_argument("--asset-mode", choices=ASSET_MODES, default="additive", help="Asset export mode. 'additive' exports manifest-referenced assets; 'all' exports every Images/Assets diff.")
    parser.add_argument("--optional-song-mods-dir", help="Folder containing optional song .ogg files to place in payload/OptionalSongMods and target to Sounds/.")
    parser.add_argument("--mobile-sound-assets-dir", help="Folder containing all 67 pinned mobile behavior sound .ogg files to place behind the mobile_sound_assets setting.")
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
                "post_asset_patches": len(manifest["post_asset_patches"]),
                "payload_files": manifest["export_summary"]["payload_file_count"],
                "requires_vanilla_exe_for_apply": manifest["export_summary"]["requires_vanilla_exe_for_apply"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
