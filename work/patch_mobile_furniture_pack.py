from pathlib import Path
import csv
import json
import os
import shutil
import struct
import sys
from io import BytesIO
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coff_patch import CoffObject

ROOT = Path(__file__).resolve().parents[1]
SRC_OBJS = ROOT / "work" / "desktop_obj_files"
PATCHED = ROOT / "work" / "patched_mobile_furniture_pack_objs"
OUT = Path(os.environ.get("VF2_PATCH_OUT", ROOT / "outputs" / "VF2-Mobile-Additive-Furniture-Pack"))
ENABLE_ISLAND_EVENTS = os.environ.get("VF2_ENABLE_ISLAND_EVENTS", "1") == "1"
# Debugger/editor hooks have repeatedly crashed during save-load and mouse
# input. Keep normal builds stock; use this only for isolated debugger research.
ENABLE_DEBUGGER_FEATURES = os.environ.get("VF2_ENABLE_DEBUGGER_FEATURES", "0") == "1"
# Holiday body rows are now part of the normal additive build.  Set the env var
# to 0 only when intentionally making a stock-body diagnostic build.
ENABLE_HOLIDAY_BODY_TYPES = os.environ.get("VF2_ENABLE_HOLIDAY_BODY_TYPES", "1") != "0"
ANALYSIS = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"
if not (ANALYSIS / "furniture-records.json").exists():
    ANALYSIS = ROOT / "Unneeded crap" / "VF2-Desktop-Object-Analysis"

ITEMINFO = "?itemInfo@@3PAUsFurnitureInfo@@A"
ITEMLOOKUP = "?itemInfoLookup@@3PAPAUsFurnitureInfo@@A"
IMAGELIST = "?ImageList@@3PAUImageDescriptor@@A"
IMAGEINDEX = "?ImageIndex@@3PAPAUImageDescriptor@@A"
STRINGTABLE = "?stringTable@@3PAUStringItem@@A"
STRINGLOOKUP = "?lookupTable@@3PAPAUStringItem@@A"
INVENTORY_ITEMINFO = "?itemInfo@@3PAUsInventoryItemInfo@@A"
GSERVICESLIST = "?gServicesList@@3PAW4EInventoryItem@@A"
GCLOTHINGLIST = "?gClothingList@@3PAW4EInventoryItem@@A"
GET_CATEGORY_ITEM = "?GetCategoryItem@CInventoryManager@@QAE?AW4EInventoryItem@@W4EInventoryCategory@@H@Z"
GET_CATEGORY_ITEM_COUNT = "?GetCategoryItemCount@CInventoryManager@@QAEHW4EInventoryCategory@@@Z"
IMAGE_REL_I386_REL32 = 0x0014

RECORD_SIZE = 0x6C
DESC_SIZE = 0x30
STRING_RECORD_SIZE = 0x10
ORIG_FURNITURE_COUNT = 252
ORIG_IMAGE_COUNT = 637
ORIG_IMAGE_MAX = 0x27C
LOCKED_IMAGE_ID = 632
LOCKED_GENERATION_FRAME_COUNT = 29
LOCKED_GENERATION_CELL_WIDTH = 30
LOCKED_GENERATION_CELL_HEIGHT = 46
LOCKED_PNG_SOURCE = Path(r"C:\Users\Owner\Downloads\locked.png")
VF3_SPRITE_SOURCE_DIR = Path(r"C:\Users\Owner\Downloads\Sprite")
INVISIBLE_OUTDOOR_SPRITE_SOURCE_DIR = Path(r"C:\Users\Owner\Downloads\Virtual Families 2 - Copy Official\Images\Furniture")
HOLIDAY_OUTFIT_ARCHIVE = Path(r"C:\Users\Owner\Downloads\VF2_Holiday_Content\Holiday Outfits.zip")
ORIGINAL_VF2_SPRITE_COPY_SOURCE_DIR = Path(r"C:\Users\Owner\OneDrive\Desktop\LDW Desktop Games!! And Other Stuff\Virtual Families 2 - Copy Official\originalimages")
GENERATED_VILLAGER_BODIES = ROOT / "generated" / "VillagerBodies"
FALLBACK_HOLIDAY_BODY_BUILD = ROOT / "outputs" / "VF2-Mobile-Furniture-With-Island-Events-B56-Holiday-Body-Lookup-Test"
HOLIDAY_BODY_SET_IDS = (51, 52, 53, 54)
HOLIDAY_BODY_BASE_ROWS = 50
HOLIDAY_BODY_VALUES = tuple(range(50, 50 + len(HOLIDAY_BODY_SET_IDS)))
OUTFIT_STORE_GENDERS = ("female", "male")
OUTFIT_STORE_GENDER_ITEM_BASES = {
    "female": 0x400,
    "male": 0x440,
}
OUTFIT_STORE_ITEM_BASE = OUTFIT_STORE_GENDER_ITEM_BASES["female"]
OUTFIT_BASE_BODY_VALUES = tuple(range(0, HOLIDAY_BODY_BASE_ROWS))
OUTFIT_STORE_BODY_VALUES = OUTFIT_BASE_BODY_VALUES + HOLIDAY_BODY_VALUES
OUTFIT_STORE_ENTRY_COUNT = len(OUTFIT_STORE_GENDERS) * len(OUTFIT_STORE_BODY_VALUES)
OUTFIT_STORE_PRICE = 75
OUTFIT_STORE_HOLIDAY_PRICE = 500
HOLIDAY_BODY_CELL_SIZE = 91
HOLIDAY_BODY_ROLE_SPECS = [
    {
        "role": "bodies",
        "source_range": (1, 32),
        "columns": 32,
        "sheets": {
            "female": ("female_bodies00.png", "Female Outfits", "FemaleBodies_0"),
            "male": ("male_bodies00.png", "Male Outfits", "MaleBodies_00"),
        },
    },
    {
        "role": "actions",
        "source_range": (33, 47),
        "columns": 15,
        "sheets": {
            "female": ("female_actions00.png", "Female Outfits", "FemaleBodies_0"),
            "male": ("male_actions00.png", "Male Outfits", "MaleBodies_00"),
        },
    },
    {
        "role": "sit",
        "source_range": (48, 56),
        "columns": 9,
        "sheets": {
            "female": ("female_sit00.png", "Female Outfits", "FemaleBodies_0"),
            "male": ("male_sit00.png", "Male Outfits", "MaleBodies_00"),
        },
    },
]
HOLIDAY_BODY_ROLE_OFFSETS = {"bodies": 0, "actions": 32, "sit": 47}
HOLIDAY_BODY_ROLE_FRAME_COUNTS = {"bodies": 32, "actions": 15, "sit": 9}
HOLIDAY_BODY_FRAMES_PER_VALUE = sum(HOLIDAY_BODY_ROLE_FRAME_COUNTS.values())
HOLIDAY_BODY_IMAGE_COUNT = 2 * len(HOLIDAY_BODY_VALUES) * HOLIDAY_BODY_FRAMES_PER_VALUE
OUTFIT_STORE_ICON_ROLE = "actions"
OUTFIT_STORE_ICON_SOURCE_SHEETS = {
    "female": "female_actions00.png",
    "male": "male_actions00.png",
}
VILLAGER_SPRITE_SHEET_FILES = (
    "female_bodies00.png",
    "female_actions00.png",
    "female_sit00.png",
    "male_bodies00.png",
    "male_actions00.png",
    "male_sit00.png",
)
LARGE_TV_ANIMATION_SHEETS = {
    "Large": Path(r"C:\Users\Owner\Downloads\TVAnimBigE.png"),
    "LargeEast": Path(r"C:\Users\Owner\Downloads\TVAnimBig.png"),
}
VF3_TV_ANIMATION_FRAME_PREFIXES = {
    "Large": "TVAnimBigE",
    "LargeEast": "TVAnimBig",
    "Small": "FlatScreenSmallAnimE",
    "SmallEast": "FlatScreenSmallAnim",
    "FathersFavorite": "TVAnimBigE",
    "FathersFavoriteEast": "TVAnimBig",
}
VF3_TV_RUNTIME_ANIMATION_NAMES = {
    "Large": "VF3LargeFlatScreenTVAnim.png",
    "LargeEast": "VF3LargeFlatScreenTVAnimEast.png",
    "Small": "VF3SmallFlatScreenTVAnim.png",
    "SmallEast": "VF3SmallFlatScreenTVAnimEast.png",
    "FathersFavorite": "FathersFavoriteTVAnim.png",
    "FathersFavoriteEast": "FathersFavoriteTVAnimEast.png",
}
VF3_TV_FLOATING_ANIM_BASE = 0x40
VF3_TV_FLOATING_ANIMS = {
    "Large": {"enum": VF3_TV_FLOATING_ANIM_BASE + 0, "donor_image_id": 0x1FB},
    "LargeEast": {"enum": VF3_TV_FLOATING_ANIM_BASE + 1, "donor_image_id": 0x20E},
    "Small": {"enum": VF3_TV_FLOATING_ANIM_BASE + 2, "donor_image_id": 0x1FC},
    "SmallEast": {"enum": VF3_TV_FLOATING_ANIM_BASE + 3, "donor_image_id": 0x20D},
    "FathersFavorite": {"enum": VF3_TV_FLOATING_ANIM_BASE + 4, "donor_image_id": 0x1FB},
    "FathersFavoriteEast": {"enum": VF3_TV_FLOATING_ANIM_BASE + 5, "donor_image_id": 0x20E},
}
VF3_TV_ANIMATION_SCREEN_BOXES = {
    # x, y, width, height inside one furniture-cell canvas.
    "Large": (4, 5, 65, 80),
    "LargeEast": (4, 5, 65, 80),
    "Small": (2, 2, 48, 60),
    "SmallEast": (2, 2, 48, 60),
    "FathersFavorite": (5, 8, 96, 104),
    "FathersFavoriteEast": (5, 8, 96, 104),
}
VISIBLE_SPECIAL_UPGRADE_ICON_FILES = {
    0x117: "BrokerUpgrade_icon.png",
    0x118: "FoodClub_icon.png",
    0x119: "HealthPlan_icon.png",
    0x11A: "LuckyRock_icon.png",
}
VISIBLE_SPECIAL_UPGRADE_ICON_CELL_SIZE = 90
HOLIDAY_ORNAMENT_COLLECTABLE_START = 0x9E
HOLIDAY_ORNAMENT_COLLECTABLE_END = 0xA9
HOLIDAY_ORNAMENT_COLLECTION_PAGE = 5
HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT = 12
HOLIDAY_ORNAMENT_COLLECTION_IMAGE_COUNT = HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT + 1
HOLIDAY_ORNAMENT_ACHIEVEMENT_ID = 0x5F
HOLIDAY_ORNAMENT_ACHIEVEMENT_TARGET = 12
HOLIDAY_ORNAMENT_ACHIEVEMENT_ORDER_COUNT = 0x60
ACHIEVEMENT_ROW_SIZE = 0x1C
HOLIDAY_ORNAMENT_MOBILE_ATLAS_DAT = ROOT / "work" / "vf2_obb" / "assets" / "tp225.dat"
HOLIDAY_ORNAMENT_MOBILE_ATLAS_PVR = ROOT / "work" / "vf2_obb" / "assets" / "tp225.pvr"
HOLIDAY_ORNAMENT_BACKGROUND_FILENAME = "collection-ornaments_background.png"
HOLIDAY_ORNAMENT_IMAGE_SCALE = 1024.0 / 800.0
HOLIDAY_ORNAMENT_ATLAS_RECORDS = [
    ("collection_christmasornament_blueball.png", 903, 334, 93, 115),
    ("collection_christmasornament_crosses.png", 804, 345, 92, 114),
    ("collection_christmasornament_disco.png", 804, 227, 95, 114),
    ("collection_christmasornament_golddealio.png", 804, 0, 114, 117),
    ("collection_christmasornament_heart.png", 804, 463, 88, 106),
    ("collection_christmasornament_hotairballoon.png", 922, 0, 100, 109),
    ("collection_christmasornament_redgoldornament.png", 900, 453, 89, 114),
    ("collection_christmasornament_silverbell.png", 804, 573, 64, 113),
    ("collection_christmasornament_star.png", 916, 220, 105, 110),
    ("collection_christmasornament_threebells.png", 896, 571, 85, 119),
    ("collection_christmasornament_twirl.png", 922, 113, 96, 103),
    ("collection_christmasornament_twisty.png", 804, 121, 108, 102),
]
HOLIDAY_ORNAMENT_COLLECTION_SLOT_POSITIONS = [
    (0x0B4, 0x1DC),
    (0x161, 0x1DC),
    (0x213, 0x1DC),
    (0x2C4, 0x1DC),
    (0x0C1, 0x12E),
    (0x213, 0x12E),
    (0x161, 0x12E),
    (0x2C4, 0x12E),
    (0x0B4, 0x07E),
    (0x161, 0x07E),
    (0x213, 0x07E),
    (0x2C4, 0x07E),
]
CHARACTER_SHEET_SPECS = {
    "female_heads": {
        "image_id": 576,
        "probe_file": "female_heads00.png",
        "cell_size": (28, 56),
        "original_grid": (24, 50),
    },
    "female_bodies00.png": {
        "image_id": 577,
        "probe_file": "female_bodies00.png",
        "cell_size": (91, 91),
        "original_grid": (32, 50),
    },
    "male_heads": {
        "image_id": 580,
        "probe_file": "male_heads00.png",
        "cell_size": (28, 56),
        "original_grid": (24, 50),
    },
    "male_bodies00.png": {
        "image_id": 581,
        "probe_file": "male_bodies00.png",
        "cell_size": (91, 91),
        "original_grid": (32, 50),
    },
    "highrez_bodies_final2.png": {
        "image_id": 22,
        "probe_file": "highrez_bodies_final2.png",
        "cell_size": (164, 164),
        "original_grid": (2, 50),
    },
}
ORIG_STRING_COUNT = 0xA5D
ORIG_STRING_ONE_PAST_MAX = 0xA69
ORIG_STRING_GET_MAX_MINUS_ONE = 0xA67
ORIG_STRING_LOOKUP_BYTES = 0x29A4
SPECIAL_UPGRADE_DESCRIPTION_COUNT = 4
BEHAVIOR_LABELS = [
    ("eString_PlayingPachinko", "Playing pachinko"),
    ("eString_PlayingPinball", "Playing pinball"),
]


def build_native_array_contract():
    """Describe every native array/list that additive builds intentionally grow."""
    return {
        "furniture": {
            "record_table": ITEMINFO,
            "lookup_table": ITEMLOOKUP,
            "base_count": ORIG_FURNITURE_COUNT,
            "append_source": "ITEMS",
            "requirements": [
                "append new sFurnitureInfo records after the stock table",
                "extend itemInfoLookup so new EInventoryItem values resolve to records",
                "preserve every stock record and stock lookup entry",
            ],
        },
        "store_categories": {
            name: {
                "list_symbol": spec[0],
                "sorted_list_symbol": spec[1],
                "stock_count": spec[2],
                "requirements": [
                    "append only the new item IDs assigned to this category",
                    "patch GetCategoryItem/GetCategoryItemCount consumers to use the grown count",
                    "leave stock ordering and IDs untouched",
                ],
            }
            for name, spec in LIST_SYMBOLS.items()
        },
        "pets": {
            "store_category": "gPet",
            "stock_count": 13,
            "append_source": "PET_STORE_ADDITIONS",
            "added": [
                {
                    "name": pet["name"],
                    "item_id": hex(pet["item_id"]),
                    "source": pet["source"],
                }
                for pet in PET_STORE_ADDITIONS
            ],
            "requirements": [
                "append hidden/mobile pet item IDs to gPet",
                "patch pet category count logic by the same number of appended entries",
                "preserve stock pet list entries and ordering",
            ],
        },
        "graphics": {
            "descriptor_table": IMAGELIST,
            "index_table": IMAGEINDEX,
            "base_count": ORIG_IMAGE_COUNT,
            "requirements": [
                "append descriptors for new furniture, TV animation, icons, and optional body frames",
                "grow ImageIndex by the same descriptor count",
                "keep stock image IDs stable as fallback",
            ],
        },
        "strings": {
            "string_table": STRINGTABLE,
            "lookup_table": STRINGLOOKUP,
            "base_count": ORIG_STRING_COUNT,
            "requirements": [
                "append text rows for new store names/descriptions, behavior labels, and event text",
                "patch string table scan/count bounds",
                "never reuse or overwrite stock string IDs",
            ],
        },
        "island_events": {
            "event_table": "?mEventList@CIslandEvents@@0PAPAVCIslandEvent@@A",
            "has_fired_table": "?mEventHasFired@CIslandEvents@@0PA_NA",
            "stock_slots": "0x01-0x60",
            "append_start_slot": "0x61",
            "enabled": ENABLE_ISLAND_EVENTS,
            "requirements": [
                "append mobile-only events as CIslandEvent-compatible objects",
                "move mEventHasFired after the grown pointer table",
                "patch constructor/destructor/ForceEvent scan bounds to the new exclusive end",
                "treat rows whose source starts with CEventEmail as email events",
            ],
        },
        "click_dispatch": {
            "function": "?HandleMouseDown@CFurnitureManager@@QAE_NUldwPoint@@@Z",
            "requirements": [
                "extend the native lookup table instead of replacing stock cases",
                "copy donor case bytes for added furniture that inherits clickable behavior",
                "preserve all stock clickable furniture behavior",
            ],
        },
        "villager_behaviors": {
            "source": "CVillager::InitAI autonomous candidate table",
            "requirements": [
                "enable existing native candidates additively",
                "do not route through the Bored action as a replacement",
                "keep drop-action behavior separate from spontaneous eligibility",
            ],
        },
        "holiday_outfits": {
            "enabled": ENABLE_HOLIDAY_BODY_TYPES,
            "body_values": list(HOLIDAY_BODY_VALUES),
            "source_sets": list(HOLIDAY_BODY_SET_IDS),
            "status": "default-on additive body rows",
            "requirements": [
                "keep stock body values 0-49 unchanged",
                "register body/action/sit frames for new values together",
                "fall back to stock spritesheet rendering for missing extracted frames",
            ],
        },
        "holiday_ornaments": {
            "collectable_range": f"{hex(HOLIDAY_ORNAMENT_COLLECTABLE_START)}-{hex(HOLIDAY_ORNAMENT_COLLECTABLE_END)}",
            "collection_page": HOLIDAY_ORNAMENT_COLLECTION_PAGE,
            "achievement": hex(HOLIDAY_ORNAMENT_ACHIEVEMENT_ID),
            "requirements": [
                "reuse CCollectableItem::Update/Add so spawn timing and Lucky Rock odds remain stock",
                "register base carrying value 0x9E as another 12-item spawn collection",
                "append one Collections scene page without changing CCollectionScene object size",
                "append one Goals screen achievement row without changing the save-state size",
                "use generated Images/CollectionOrnaments payloads copied into the modified build folder",
            ],
        },
    }

MOBILE_CSV = Path(
    r"C:\Users\Owner\Documents\Codex\2026-06-01\virtual-families-2-has-a-lot\outputs\mobile-port-analysis\vf2_desktop_base_and_mobile_furniture_sections.csv"
)
MOBILE_EVENT_TEXT_PACK = Path(
    r"C:\Users\Owner\Documents\Codex\2026-06-13\files-mentioned-by-the-user-virtual\work\mobile_only_event_text_pack.csv"
)
MOBILE_EVENT_MAPPING_CSV = Path(
    r"C:\Users\Owner\Documents\Codex\2026-06-13\files-mentioned-by-the-user-virtual\work\mobile_event_shell_mapping.csv"
)

SECTION_LIST = {
    "Accessory/Small Decor": "gAccessories",
    "Welcome Mat/Floor Decor": "gAccessories",
    "Furniture/Placeable": "gFurniture5",
    "Outdoor Ground/Patio": "gFurniture5",
}

CATEGORY_BY_PATH = {
    "Furniture/ChristmasTree1.png": "gAccessories",
    "Furniture/ChristmasTree2.png": "gAccessories",
    "Furniture/TowelRackBathroomBrownStd.png": "gAccessories",
    "Furniture/TowelRackBathroomPinkStd.png": "gAccessories",
}

DONOR_BY_PATH = {
    "Furniture/Chaise_blue.png": 0x26E,
    "Furniture/Chaise_brown.png": 0x26F,
    "Furniture/Chaise_green.png": 0x270,
    "Furniture/Chaise_red.png": 0x272,
    "Furniture/Patio_brick.png": 0x29A,
    "Furniture/Patio_cobblestone.png": 0x29B,
    "Furniture/Patio_table.png": 0x1D8,
    "Furniture/Patio_umbrella.png": 0x233,
    "Furniture/Picnic_table.png": 0x1D8,
    "Furniture/WelcomeMat.png": 0x21D,
    "Furniture/TowelRackBathroomBrownStd.png": 0x1EF,
    "Furniture/TowelRackBathroomPinkStd.png": 0x1EF,
    "Furniture/SoapBlackStd.png": 0x1EB,
    "Furniture/SoapGreenStd.png": 0x1EB,
    "Furniture/Lamp_office_black.png": 0x203,
    "Furniture/Lamp_office_chrome.png": 0x203,
}

DESCRIPTION_OVERRIDES_BY_PATH = {
    "Furniture/SoapBlackStd.png": {
        "short_description": "Black Designer Soap",
        "long_description": "Fancy, miniature black soap bars with an attractive soap dish. Helps your family stay clean while adding a decorative touch to their bathroom.",
    },
    "Furniture/SoapGreenStd.png": {
        "short_description": "Green Designer Soap",
        "long_description": "Fancy, miniature green soap bars with an attractive soap dish. Helps your family stay clean while adding a decorative touch to their bathroom.",
    },
    "Furniture/TowelRackBathroomBrownStd.png": {
        "short_description": "Brown Towel Set",
        "long_description": "A deluxe set of color-coordinated brown towels, complete with towel heater.",
    },
    "Furniture/TowelRackBathroomPinkStd.png": {
        "short_description": "Pink Towel Set",
        "long_description": "A deluxe set of color-coordinated pink towels, complete with towel heater.",
    },
    "Furniture/Patio_cobblestone.png": {
        "long_description": "Give your family a stylish outdoor area for barbecues, picnics, or just relaxing outside!",
    },
}

CUSTOM_ITEMS = [
    {
        "name": "LDWModernPainting4",
        "item_id": 0x2E9,
        "donor": 0x230,
        "list": "gAccessories",
        "price": 2795,
        "lock_generation": 30,
        "item_type": 5,
        "short_symbol": "eString_LDWModernPainting4ShortDesc",
        "long_symbol": "eString_LDWModernPainting4LongDesc",
        "short_description": "Virtual Villagers Painting",
        "long_description": "A landscape painting depicting one of many island adventures on Isola!",
    },
    {
        "name": "LDWModernPainting5",
        "item_id": 0x2EA,
        "donor": 0x231,
        "list": "gAccessories",
        "price": 12995,
        "lock_generation": 30,
        "item_type": 5,
        "short_symbol": "eString_LDWModernPainting5ShortDesc",
        "long_symbol": "eString_LDWModernPainting5LongDesc",
        "short_description": "Painting of Isola",
        "long_description": "A lovingly-painted rendition of the fabled island of Isola.",
    },
    {
        "name": "LDWPoster1Std",
        "item_id": 0x2EB,
        "donor": 0x20D,
        "list": "gFurniture4",
        "price": 35,
        "lock_generation": 25,
        "item_type": 5,
        "short_symbol": "eString_LDWPoster1StdShortDesc",
        "long_symbol": "eString_LDWPoster1StdLongDesc",
        "short_description": "Last Day of Work Poster",
        "long_description": "Show your love for LDW games with this poster!",
    },
    {
        "name": "LDWPoster2Std",
        "item_id": 0x2EC,
        "donor": 0x20E,
        "list": "gFurniture4",
        "price": 35,
        "lock_generation": 25,
        "item_type": 5,
        "short_symbol": "eString_LDWPoster2StdShortDesc",
        "long_symbol": "eString_LDWPoster2StdLongDesc",
        "short_description": "Casino Game Posters and Wall Calendar",
        "long_description": "Dedicated to only the most longtime Palm OS fans!",
    },
    {
        "name": "LDWPoster3Std",
        "item_id": 0x2ED,
        "donor": 0x20F,
        "list": "gFurniture4",
        "price": 55,
        "lock_generation": 25,
        "item_type": 5,
        "short_symbol": "eString_LDWPoster3StdShortDesc",
        "long_symbol": "eString_LDWPoster3StdLongDesc",
        "short_description": "Virtual Families and Tycoon Games Posters",
        "long_description": "For the love of family, friends, fish and plants!",
    },
    {
        "name": "LDWPoster4Std",
        "item_id": 0x2EE,
        "donor": 0x210,
        "list": "gFurniture4",
        "price": 75,
        "lock_generation": 25,
        "item_type": 5,
        "short_symbol": "eString_LDWPoster4StdShortDesc",
        "long_symbol": "eString_LDWPoster4StdLongDesc",
        "short_description": "Virtual Town and Cook Off Posters",
        "long_description": "For LDW fans both old and new!",
    },
    {
        "name": "CouchNeonPurpleStd",
        "item_id": 0x2EF,
        "donor": 0x1BD,
        "list": "gFurniture2",
        "price": 750,
        "lock_generation": 19,
        "item_type": 5,
        "short_symbol": "eString_CouchNeonPurpleStdShortDesc",
        "long_symbol": "eString_CouchNeonPurpleStdLongDesc",
        "short_description": "Vibrant Purple Couch",
        "long_description": "A neon-purple couch!",
    },
    {
        "name": "CouchBrownColorfulStd",
        "item_id": 0x2F0,
        "donor": 0x1BE,
        "list": "gFurniture2",
        "price": 700,
        "lock_generation": 17,
        "item_type": 5,
        "short_symbol": "eString_CouchBrownColorfulStdShortDesc",
        "long_symbol": "eString_CouchBrownColorfulStdLongDesc",
        "short_description": "Vibrant Brown Couch",
        "long_description": "A classic brown couch.",
    },
    {
        "name": "CouchGoldColorfulStd",
        "item_id": 0x2F1,
        "donor": 0x1BF,
        "list": "gFurniture2",
        "price": 1800,
        "lock_generation": 17,
        "item_type": 5,
        "short_symbol": "eString_CouchGoldColorfulStdShortDesc",
        "long_symbol": "eString_CouchGoldColorfulStdLongDesc",
        "short_description": "Vibrant Gold Couch",
        "long_description": "A vibrant gold couch to lounge on.",
    },
    {
        "name": "CouchAquaStd",
        "item_id": 0x2F2,
        "donor": 0x1C3,
        "list": "gFurniture2",
        "price": 750,
        "lock_generation": 19,
        "item_type": 5,
        "short_symbol": "eString_CouchAquaStdShortDesc",
        "long_symbol": "eString_CouchAquaStdLongDesc",
        "short_description": "Vibrant Aqua Couch",
        "long_description": "A sea-blue couch to relax on!",
    },
    {
        "name": "CouchPinkColorfulStd",
        "item_id": 0x2F3,
        "donor": 0x1C2,
        "list": "gFurniture2",
        "price": 750,
        "lock_generation": 19,
        "item_type": 5,
        "short_symbol": "eString_CouchPinkColorfulStdShortDesc",
        "long_symbol": "eString_CouchPinkColorfulStdLongDesc",
        "short_description": "Vibrant Pink Couch",
        "long_description": "A blush-pink couch!",
    },
    {
        "name": "CouchVioletStd",
        "item_id": 0x2F4,
        "donor": 0x1C4,
        "list": "gFurniture2",
        "price": 900,
        "lock_generation": 17,
        "item_type": 5,
        "short_symbol": "eString_CouchVioletStdShortDesc",
        "long_symbol": "eString_CouchVioletStdLongDesc",
        "short_description": "Vibrant Violet Couch",
        "long_description": "A comfy violet couch to rest on.",
    },
    {
        "name": "CouchLimeGreenStd",
        "item_id": 0x2F5,
        "donor": 0x1C5,
        "list": "gFurniture2",
        "price": 750,
        "lock_generation": 17,
        "item_type": 5,
        "short_symbol": "eString_CouchLimeGreenStdShortDesc",
        "long_symbol": "eString_CouchLimeGreenStdLongDesc",
        "short_description": "Vibrant Lime Couch",
        "long_description": "A fluorescent green couch to light up the room!",
    },
]

VF3_CUSTOM_ITEMS = [
    {
        "name": "AntiqueRadioStd",
        "item_id": 0x2F6,
        "donor": 0x256,
        "list": "gFurniture4",
        "price": 450,
        "lock_generation": 12,
        "item_type": 5,
        "short_description": "Antique Radio",
        "long_description": "A handsome vintage radio from Virtual Families 3, adapted as a decorative furniture piece.",
    },
    {
        "name": "AqauriumStd",
        "item_id": 0x2F7,
        "donor": 0x256,
        "list": "gAccessories",
        "price": 950,
        "lock_generation": 14,
        "item_type": 5,
        "short_description": "Aquarium",
        "long_description": "A lively aquarium from Virtual Families 3, brought over as a decorative display item.",
    },
    {
        "name": "BallonsStd",
        "item_id": 0x2F8,
        "donor": 0x256,
        "list": "gAccessories",
        "price": 125,
        "lock_generation": 6,
        "item_type": 5,
        "short_description": "Party Balloons",
        "long_description": "A cheerful bunch of balloons from Virtual Families 3 for brightening up the house.",
    },
    {
        "name": "BookshelfBlue",
        "item_id": 0x2F9,
        "donor": 0x256,
        "list": "gFurniture4",
        "price": 725,
        "lock_generation": 9,
        "item_type": 5,
        "short_description": "Blue Bookshelf",
        "long_description": "A blue bookshelf from Virtual Families 3, adapted as decorative study furniture.",
    },
    {
        "name": "BBQSmallStd",
        "item_id": 0x2FA,
        "donor": 0x256,
        "list": "gFurniture5",
        "price": 750,
        "lock_generation": 10,
        "item_type": 5,
        "short_description": "Small BBQ",
        "long_description": "A compact backyard barbecue from Virtual Families 3.",
    },
    {
        "name": "BBQUltimateStd",
        "item_id": 0x2FB,
        "donor": 0x256,
        "list": "gFurniture5",
        "price": 1750,
        "lock_generation": 18,
        "item_type": 5,
        "short_description": "Ultimate BBQ",
        "long_description": "A deluxe outdoor grill from Virtual Families 3 for serious patio style.",
    },
    {
        "name": "BedAdultBrownStd",
        "item_id": 0x2FC,
        "donor": 0x256,
        "list": "gFurniture3",
        "price": 1295,
        "lock_generation": 12,
        "item_type": 5,
        "short_description": "Brown Adult Bed",
        "long_description": "A brown adult bed from Virtual Families 3, imported as decorative bedroom furniture.",
    },
    {
        "name": "BedAdultGreenStd",
        "item_id": 0x2FD,
        "donor": 0x256,
        "list": "gFurniture3",
        "price": 1295,
        "lock_generation": 12,
        "item_type": 5,
        "short_description": "Green Adult Bed",
        "long_description": "A green adult bed from Virtual Families 3, imported as decorative bedroom furniture.",
    },
    {
        "name": "BedAdultOrangeStd",
        "item_id": 0x2FE,
        "donor": 0x256,
        "list": "gFurniture3",
        "price": 1295,
        "lock_generation": 12,
        "item_type": 5,
        "short_description": "Orange Adult Bed",
        "long_description": "An orange adult bed from Virtual Families 3, imported as decorative bedroom furniture.",
    },
    {
        "name": "BedAdultRedStd",
        "item_id": 0x2FF,
        "donor": 0x256,
        "list": "gFurniture3",
        "price": 1295,
        "lock_generation": 12,
        "item_type": 5,
        "short_description": "Red Adult Bed",
        "long_description": "A red adult bed from Virtual Families 3, imported as decorative bedroom furniture.",
    },
    {
        "name": "BedBoatStd",
        "item_id": 0x300,
        "donor": 0x256,
        "list": "gFurniture3",
        "price": 1095,
        "lock_generation": 10,
        "item_type": 5,
        "short_description": "Boat Bed",
        "long_description": "A playful boat-shaped bed from Virtual Families 3, imported as decorative furniture.",
    },
    {
        "name": "BedCarRedStd",
        "item_id": 0x301,
        "donor": 0x256,
        "list": "gFurniture3",
        "price": 1095,
        "lock_generation": 10,
        "item_type": 5,
        "short_description": "Red Car Bed",
        "long_description": "A red car bed from Virtual Families 3, imported as decorative furniture.",
    },
    {
        "name": "BedKidsBlueStd",
        "item_id": 0x302,
        "donor": 0x256,
        "list": "gFurniture3",
        "price": 895,
        "lock_generation": 8,
        "item_type": 5,
        "short_description": "Blue Kids Bed",
        "long_description": "A blue children's bed from Virtual Families 3, adapted for this furniture pack.",
    },
    {
        "name": "BedKidsPinkStd",
        "item_id": 0x303,
        "donor": 0x256,
        "list": "gFurniture3",
        "price": 895,
        "lock_generation": 8,
        "item_type": 5,
        "short_description": "Pink Kids Bed",
        "long_description": "A pink children's bed from Virtual Families 3, adapted for this furniture pack.",
    },
    {
        "name": "BigPosterBarbies",
        "item_id": 0x304,
        "donor": 0x230,
        "list": "gFurniture2",
        "price": 225,
        "lock_generation": 7,
        "item_type": 5,
        "short_description": "Big Barbie Poster",
        "long_description": "A large Virtual Families 3 wall poster with a bright toy-inspired design.",
    },
    {
        "name": "BigPosterCatsAndDogs",
        "item_id": 0x305,
        "donor": 0x230,
        "list": "gFurniture2",
        "price": 225,
        "lock_generation": 7,
        "item_type": 5,
        "short_description": "Big Cats and Dogs Poster",
        "long_description": "A large Virtual Families 3 poster celebrating cats and dogs.",
    },
    {
        "name": "BigPosterDinosaurs",
        "item_id": 0x306,
        "donor": 0x230,
        "list": "gFurniture2",
        "price": 225,
        "lock_generation": 7,
        "item_type": 5,
        "short_description": "Big Dinosaur Poster",
        "long_description": "A large Virtual Families 3 dinosaur poster for a playful wall display.",
    },
    {
        "name": "BigPosterFish",
        "item_id": 0x307,
        "donor": 0x230,
        "list": "gFurniture2",
        "price": 225,
        "lock_generation": 7,
        "item_type": 5,
        "short_description": "Big Fish Poster",
        "long_description": "A large Virtual Families 3 fish poster for a cheerful wall display.",
    },
    {
        "name": "BigPosterHearts",
        "item_id": 0x308,
        "donor": 0x230,
        "list": "gFurniture2",
        "price": 225,
        "lock_generation": 7,
        "item_type": 5,
        "short_description": "Big Hearts Poster",
        "long_description": "A large Virtual Families 3 hearts poster with a sweet decorative look.",
    },
    {
        "name": "BookCaseBirchStd",
        "item_id": 0x309,
        "donor": 0x256,
        "list": "gFurniture4",
        "price": 850,
        "lock_generation": 11,
        "item_type": 5,
        "short_description": "Birch Bookcase",
        "long_description": "A full birch bookcase from Virtual Families 3, adapted as decorative study furniture.",
    },
]

VF3_CUSTOM_ITEMS = []

VF3_LIVING_ROOM_BATCH_02_ITEMS = [
    {
        "name": "SofaPlaid",
        "item_id": 0x2F6,
        "donor": 0x1BE,
        "list": "gFurniture2",
        "price": 725,
        "lock_generation": 12,
        "item_type": 4,
        "short_description": "Plaid Loveseat",
        "long_description": "A cozy plaid loveseat from Virtual Families 3, imported for the living room.",
    },
    {
        "name": "CouchPlaid",
        "item_id": 0x2F7,
        "donor": 0x1BE,
        "list": "gFurniture2",
        "price": 950,
        "lock_generation": 13,
        "item_type": 4,
        "short_description": "Plaid Couch",
        "long_description": "A comfortable plaid couch from Virtual Families 3.",
    },
    {
        "name": "CouchFlowers",
        "item_id": 0x2F8,
        "donor": 0x1BF,
        "list": "gFurniture2",
        "price": 1250,
        "lock_generation": 14,
        "item_type": 4,
        "short_description": "Flowered Couch",
        "long_description": "A cheerful flowered couch from Virtual Families 3.",
    },
    {
        "name": "CouchStriped",
        "item_id": 0x2F9,
        "donor": 0x1C3,
        "list": "gFurniture2",
        "price": 1050,
        "lock_generation": 14,
        "item_type": 4,
        "short_description": "Striped Couch",
        "long_description": "A striped couch from Virtual Families 3 with a relaxed living-room look.",
    },
    {
        "name": "SofaStriped",
        "item_id": 0x2FA,
        "donor": 0x1C3,
        "list": "gFurniture2",
        "price": 725,
        "lock_generation": 13,
        "item_type": 4,
        "short_description": "Striped Loveseat",
        "long_description": "A striped loveseat from Virtual Families 3.",
    },
    {
        "name": "FloweredLoveseat",
        "item_id": 0x2FB,
        "donor": 0x1C3,
        "list": "gFurniture2",
        "price": 825,
        "lock_generation": 14,
        "item_type": 4,
        "short_description": "Flowered Loveseat",
        "long_description": "A flowered loveseat from Virtual Families 3.",
    },
]

INVISIBLE_OUTDOOR_ITEMS = [
    {
        "name": "InvisibleKiddiePool",
        "item_id": 0x30A,
        "donor": 0x1E4,
        "list": "gFurniture5",
        "price": 250,
        "lock_generation": 12,
        "item_type": 1,
        "short_description": "Invisible Kiddie Pool",
        "long_description": "An invisible kiddie pool for decorating purposes.",
        "source_png": "PoolChildrensStd.png",
        "base_png": "PoolChildrensStd.png",
        "donor_fmap": "PoolChildrensStd.png.fmap",
    },
    {
        "name": "InvisibleFullSizePool",
        "item_id": 0x30B,
        "donor": 0x1E5,
        "list": "gFurniture5",
        "price": 14150,
        "lock_generation": 12,
        "item_type": 1,
        "short_description": "Invisible Full-Size Pool",
        "long_description": "An invisible Olympic-sized pool for decorating purposes.",
        "source_png": "PoolLargeStd.png",
        "base_png": "PoolLargeStd.png",
        "donor_fmap": "PoolLargeStd.png.fmap",
    },
    {
        "name": "InvisibleHammock",
        "item_id": 0x30C,
        "donor": 0x1E1,
        "list": "gFurniture5",
        "price": 450,
        "lock_generation": 12,
        "item_type": 5,
        "short_description": "Invisible Hammock",
        "long_description": "An invisible hammock for decorating purposes.",
        "source_png": "HammockStd1.png",
        "base_png": "HammockStd.png",
        "donor_fmap": "HammockStd.png.fmap",
    },
]

INVISIBLE_TRANSPARENT_BASE_ITEMS = [
    {
        "name": "InvisibleThreeSeaterCouch",
        "item_id": 0x30D,
        "donor": 0x1C2,
        "list": "gFurniture2",
        "price": 45,
        "short_description": "Invisible 3-Seater Couch",
        "long_description": "An invisible 3-seater couch for decorating purposes.",
        "source_png": "CouchTrashedBeigeStd.png",
        "donor_fmap": "CouchTrashedBeigeStd.png.fmap",
        "item_type": 5,
        "frame_count": 4,
    },
    {
        "name": "InvisibleTwoSeaterLoveseat",
        "item_id": 0x30E,
        "donor": 0x1D6,
        "list": "gFurniture2",
        "price": 99,
        "short_description": "Invisible 2-Seater Loveseat",
        "long_description": "An invisible 2-seater loveseat for decorating purposes.",
        "source_png": "SofaWornWhiteStd.png",
        "donor_fmap": "SofaWornWhiteStd.png.fmap",
        "item_type": 5,
        "frame_count": 4,
    },
    {
        "name": "InvisibleSingleCouch",
        "item_id": 0x30F,
        "donor": 0x273,
        "list": "gFurniture2",
        "price": 1415,
        "short_description": "Invisible Single Couch",
        "long_description": "An invisible single couch for decorating purposes.",
        "source_png": "SofaBlue.png",
        "donor_fmap": "SofaBlue.png.fmap",
        "item_type": 5,
        "frame_count": 4,
    },
    {
        "name": "InvisibleBeanbagChair",
        "item_id": 0x310,
        "donor": 0x1FA,
        "list": "gFurniture2",
        "price": 250,
        "short_description": "Invisible Beanbag Chair",
        "long_description": "An invisible beanbag chair for decorating purposes.",
        "source_png": "ChairBeanbagBlueStd.png",
        "donor_fmap": "ChairBeanbagBlueStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleLargeBookshelf",
        "item_id": 0x311,
        "donor": 0x1F8,
        "list": "gFurniture2",
        "price": 2450,
        "short_description": "Invisible Large Bookshelf",
        "long_description": "An invisible large bookshelf for decorating purposes.",
        "source_png": "BookCaseBirchStd.png",
        "donor_fmap": "BookCaseBirchStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleThinBookshelf",
        "item_id": 0x312,
        "donor": 0x1F7,
        "list": "gFurniture2",
        "price": 450,
        "short_description": "Invisible Thin Bookshelf",
        "long_description": "An invisible thin bookshelf for decorating purposes.",
        "source_png": "BookCaseBirchSmStd.png",
        "donor_fmap": "BookCaseBirchSmStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleSmallSquareBookshelf",
        "item_id": 0x313,
        "donor": 0x253,
        "list": "gFurniture2",
        "price": 1250,
        "short_description": "Invisible Small Square Bookshelf",
        "long_description": "An invisible small square bookshelf for decorating purposes.",
        "source_png": "LowerBookshelf.png",
        "donor_fmap": "LowerBookshelf.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleAdultDoubleBed",
        "item_id": 0x314,
        "donor": 0x1B7,
        "list": "gFurniture4",
        "price": 850,
        "short_description": "Invisible Adult Double Bed",
        "long_description": "An invisible adult double bed for decorating purposes.",
        "source_png": "BedAdultBrownStd.png",
        "donor_fmap": "BedAdultBrownStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleChildSingleBed",
        "item_id": 0x315,
        "donor": 0x1B5,
        "list": "gFurniture4",
        "price": 550,
        "short_description": "Invisible Child Single Bed",
        "long_description": "An invisible child single bed for decorating purposes.",
        "source_png": "BedKidsBlueStd.png",
        "donor_fmap": "BedKidsBlueStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleDoubleBed",
        "item_id": 0x316,
        "donor": 0x264,
        "list": "gFurniture4",
        "price": 3875,
        "short_description": "Invisible Double Bed",
        "long_description": "An invisible double bed for decorating purposes.",
        "source_png": "DoubleBedCheckeredDuvetBlue.png",
        "donor_fmap": "DoubleBedCheckeredDuvetBlue.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleSingleBed",
        "item_id": 0x317,
        "donor": 0x250,
        "list": "gFurniture4",
        "price": 2195,
        "short_description": "Invisible Single Bed",
        "long_description": "An invisible single bed for decorating purposes.",
        "source_png": "Gothic_SingleBedBlue.png",
        "donor_fmap": "Gothic_SingleBedBlue.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleMantleFireplace",
        "item_id": 0x318,
        "donor": 0x201,
        "list": "gAccessories",
        "price": 9150,
        "short_description": "Invisible Mantle Fireplace",
        "long_description": "Click the fireplace to turn the fire on or off.",
        "source_png": "FirePlaceRusticStd.png",
        "donor_fmap": "FirePlaceRusticStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleMP3Player",
        "item_id": 0x319,
        "donor": 0x207,
        "list": "gAccessories",
        "price": 350,
        "short_description": "Invisible MP3 Player",
        "long_description": "An invisible MP3 player for decorating purposes.",
        "source_png": "IpodSpeakersStd.png",
        "donor_fmap": "IpodSpeakersStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleSandbox",
        "item_id": 0x31A,
        "donor": 0x235,
        "list": "gFurniture5",
        "price": 695,
        "short_description": "Invisible Sandbox",
        "long_description": "An invisible sandbox for decorating purposes.",
        "source_png": "Sandbox.png",
        "donor_fmap": "Sandbox.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisiblePlayhouse",
        "item_id": 0x31B,
        "donor": 0x1E3,
        "list": "gFurniture5",
        "price": 18000,
        "short_description": "Invisible Playhouse",
        "long_description": "An invisible playhouse for decorating purposes.",
        "source_png": "PlayStructureStd.png",
        "donor_fmap": "PlayStructureStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleTrainTable",
        "item_id": 0x31C,
        "donor": 0x239,
        "list": "gFurniture5",
        "price": 950,
        "short_description": "Invisible Train Table",
        "long_description": "An invisible train table for decorating purposes.",
        "source_png": "TrainTableForKids.png",
        "donor_fmap": "TrainTableForKids.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleBathroomScale",
        "item_id": 0x31D,
        "donor": 0x1EA,
        "list": "gAccessories",
        "price": 130,
        "short_description": "Invisible Bathroom Scale",
        "long_description": "An invisible bathroom scale for decorating purposes.",
        "source_png": "ScaleBathroomStd.png",
        "donor_fmap": "ScaleBathroomStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleDryingRack",
        "item_id": 0x31E,
        "donor": 0x1CF,
        "list": "gAccessories",
        "price": 80,
        "short_description": "Invisible Drying Rack",
        "long_description": "An invisible drying rack for decorating purposes.",
        "source_png": "LaundryDryingRackStd.png",
        "donor_fmap": "LaundryDryingRackStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleGrandfatherClock",
        "item_id": 0x31F,
        "donor": 0x205,
        "list": "gAccessories",
        "price": 8500,
        "short_description": "Invisible Grandfather Clock",
        "long_description": "Click the clock to make it chime.",
        "source_png": "GrandfatherClockStd.png",
        "donor_fmap": "GrandfatherClockStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleDresser",
        "item_id": 0x320,
        "donor": 0x1CA,
        "list": "gFurniture4",
        "price": 250,
        "short_description": "Invisible Dresser",
        "long_description": "An invisible dresser for decorating purposes.",
        "source_png": "DresserStd1.png",
        "donor_fmap": "DresserStd1.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleKidsTableAndChairs",
        "item_id": 0x321,
        "donor": 0x1CE,
        "list": "gFurniture3",
        "price": 950,
        "short_description": "Invisible Kids Table with Chairs",
        "long_description": "An invisible kids table with chairs for decorating purposes.",
        "source_png": "KidsTableAndChairsStd.png",
        "donor_fmap": "KidsTableAndChairsStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleIroningBoard",
        "item_id": 0x322,
        "donor": 0x1CD,
        "list": "gAccessories",
        "price": 250,
        "short_description": "Invisible Ironing Board",
        "long_description": "An invisible ironing board for decorating purposes.",
        "source_png": "IroningBoardStd.png",
        "donor_fmap": "IroningBoardStd.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
    {
        "name": "InvisibleTrampoline",
        "item_id": 0x323,
        "donor": 0x263,
        "list": "gFurniture5",
        "price": 2695,
        "short_description": "Invisible Trampoline",
        "long_description": "An invisible trampoline for decorating purposes.",
        "source_png": "Trampoline.png",
        "donor_fmap": "Trampoline.png.fmap",
        "item_type": 5,
        "frame_count": 2,
    },
]

# Appended after the established B19 catalog so existing item ids and saves
# remain untouched.
VF3_TV_ITEMS = [
    {
        "name": "VF3LargeFlatScreenTV",
        "item_id": 0x324,
        "donor": 0x1F3,
        "list": "gAppliances",
        "price": 6500,
        "lock_generation": 12,
        "item_type": 5,
        "short_description": "Large Flat Screen TV",
        "long_description": "A large flat screen TV from Virtual Families 3.",
        "source_png": "FlatScreenLrg.png",
        "animation_labels": ("Large", "LargeEast"),
    },
    {
        "name": "VF3SmallFlatScreenTV",
        "item_id": 0x325,
        "donor": 0x1F3,
        "list": "gAppliances",
        "price": 4250,
        "lock_generation": 12,
        "item_type": 5,
        "short_description": "Small Flat Screen TV",
        "long_description": "A small flat screen TV from Virtual Families 3.",
        "source_png": "FlatScreenSmall.png",
        "animation_labels": ("Small", "SmallEast"),
    },
    {
        "name": "FathersFavoriteTV",
        "item_id": 0x326,
        "donor": 0x1F3,
        "list": "gAppliances",
        "price": 5250,
        "lock_generation": 12,
        "item_type": 5,
        "short_description": "Father's Favorite TV",
        "long_description": "A fiery flat screen TV from Virtual Families 3.",
        "source_png": "FathersFavoriteTV.png",
        "animation_labels": ("FathersFavorite", "FathersFavoriteEast"),
    },
]

COUCH_FMAP_DONORS = {
    "CouchNeonPurpleStd.png.fmap": "CouchBeigeStd.png.fmap",
    "CouchBrownColorfulStd.png.fmap": "CouchBrownStd.png.fmap",
    "CouchGoldColorfulStd.png.fmap": "CouchGoldStd.png.fmap",
    "CouchAquaStd.png.fmap": "CouchLightlyWornBeigeStd.png.fmap",
    "CouchPinkColorfulStd.png.fmap": "CouchTrashedBeigeStd.png.fmap",
    "CouchVioletStd.png.fmap": "CouchWornLandlordGreenStd.png.fmap",
    "CouchLimeGreenStd.png.fmap": "CouchWornSteelBlueStd.png.fmap",
    "SofaPlaid.png.fmap": "SofaWhiteStd.png.fmap",
    "CouchPlaid.png.fmap": "CouchBrownStd.png.fmap",
    "CouchFlowers.png.fmap": "CouchGoldStd.png.fmap",
    "CouchStriped.png.fmap": "CouchLightlyWornBeigeStd.png.fmap",
    "SofaStriped.png.fmap": "SofaWhiteStd.png.fmap",
    "FloweredLoveseat.png.fmap": "SofaWhiteStd.png.fmap",
}
INVISIBLE_OUTDOOR_FMAP_DONORS = {
    f"{item['name']}.png.fmap": item["donor_fmap"]
    for item in INVISIBLE_OUTDOOR_ITEMS
}
INVISIBLE_TRANSPARENT_FMAP_DONORS = {
    f"{item['name']}.png.fmap": item["donor_fmap"]
    for item in INVISIBLE_TRANSPARENT_BASE_ITEMS
}
INVISIBLE_TRANSPARENT_GRAPHIC_OVERRIDES = {
    "InvisibleMantleFireplace": Path(r"C:\Users\Owner\Downloads\Virtual Families 2 - Copy Official\Images\Furniture\FirePlaceRusticStd.png"),
    "InvisibleGrandfatherClock": Path(r"C:\Users\Owner\Downloads\Virtual Families 2 - Copy Official\Images\Furniture\GrandfatherClockStd.png"),
}
VF3_TV_FMAP_DONORS = {
    "VF3LargeFlatScreenTV.png.fmap": "TVFlatScreenStd.png.fmap",
    "VF3SmallFlatScreenTV.png.fmap": "TVFlatScreenStd.png.fmap",
    "FathersFavoriteTV.png.fmap": "TVFlatScreenStd.png.fmap",
}
EXPLICIT_FRAME_COUNTS_BY_PATH = {
    f"Furniture/{item['name']}.png": item["frame_count"]
    for item in INVISIBLE_TRANSPARENT_BASE_ITEMS
}

VF3_FOUR_FRAME_FURNITURE = {
    f"Furniture/{item['name']}.png"
    for item in VF3_LIVING_ROOM_BATCH_02_ITEMS
}
VF3_SPRITE_STRIP_SOURCES = {
    "Furniture/SofaPlaid.png": ("SofaPlaid.png", "SofaPlaid - back.png"),
    "Furniture/CouchPlaid.png": ("CouchPlaid.png", "CouchPlaid - back.png"),
    "Furniture/CouchFlowers.png": ("CouchFlowers.png", "CouchFlowers - back.png"),
    "Furniture/CouchStriped.png": ("CouchStriped.png", "CouchStriped - back.png"),
    "Furniture/SofaStriped.png": ("SofaStriped.png", "SofaStriped - back.png"),
    "Furniture/FloweredLoveseat.png": ("SofaFlower.png", "SofaFlower - back.png"),
}

SAFE_EMPTY_FMAP_DONOR = 0x256
EXPLICIT_SAFE_EMPTY_FMAP_PATHS = {
    "Furniture/ChristmasTree1.png": "mobile Christmas tree object-grid markers are decorative and should not dispatch desktop behavior",
    "Furniture/ChristmasTree2.png": "mobile Christmas tree object-grid markers are decorative and should not dispatch desktop behavior",
    "Furniture/Chaise_blue.png": "mobile chaise object-grid markers are not mapped to a known desktop sitting behavior",
    "Furniture/Chaise_brown.png": "mobile chaise object-grid markers are not mapped to a known desktop sitting behavior",
    "Furniture/Chaise_green.png": "mobile chaise object-grid markers are not mapped to a known desktop sitting behavior",
    "Furniture/Chaise_red.png": "mobile chaise object-grid markers are not mapped to a known desktop sitting behavior",
    "Furniture/Patio_table.png": "mobile patio table object-grid markers are decorative and should not dispatch desktop behavior",
    "Furniture/Patio_umbrella.png": "mobile patio umbrella uses object-grid markers unsupported by the desktop Palm donor",
    "Furniture/Picnic_table.png": "mobile picnic table object-grid markers are decorative and should not dispatch desktop behavior",
}


def donor_for_row(row):
    path = row["image_path"]
    if path in DONOR_BY_PATH:
        return DONOR_BY_PATH[path]
    if row["section_name"] == "Accessory/Small Decor":
        return 0x256
    return 0x233


def load_mobile_rows():
    if not MOBILE_CSV.exists():
        raise FileNotFoundError(f"Missing mobile furniture CSV: {MOBILE_CSV}")
    with MOBILE_CSV.open(newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["source"] == "mobile_vf2_android"]
    rows.sort(key=lambda r: int(r["section_position"]))
    items = []
    data_by_path = {}
    for row in rows:
        path = row["image_path"]
        list_name = CATEGORY_BY_PATH.get(path, SECTION_LIST[row["section_name"]])
        donor = donor_for_row(row)
        data = {
            "mobile_row": int(row["section_position"]),
            "mobile_source_id": int(row["object_id"]),
            "mobile_item_id": int(row["mobile_asset_id"], 16),
            "price": int(row["price"]),
            "lock_generation": int(row["generation_lock"]),
            "item_type": int(row["item_type"]),
            "mobile_short_id": int(row["short_text_id"], 16),
            "mobile_long_id": int(row["long_text_id"], 16),
            "short_symbol": row["short_text_key"],
            "long_symbol": row["long_text_key"],
            "short_description": row["short_description"],
            "long_description": row["long_description"],
            "section_name": row["section_name"],
            "section_number": int(row["section_number"]),
        }
        data.update(DESCRIPTION_OVERRIDES_BY_PATH.get(path, {}))
        items.append((row["short_description"], donor, list_name, path))
        data_by_path[path] = data
    for item in CUSTOM_ITEMS:
        path = f"Furniture/{item['name']}.png"
        data = {
            "mobile_row": None,
            "mobile_source_id": None,
            "mobile_item_id": item["item_id"],
            "price": item["price"],
            "lock_generation": item["lock_generation"],
            "item_type": item["item_type"],
            "mobile_short_id": 0,
            "mobile_long_id": 0,
            "short_symbol": item["short_symbol"],
            "long_symbol": item["long_symbol"],
            "short_description": item["short_description"],
            "long_description": item["long_description"],
            "section_name": "Custom/Additive",
            "section_number": -1,
            "custom_pack": "LDW poster pack" if item["name"].startswith("LDW") else "Colorful couches",
        }
        items.append((item["short_description"], item["donor"], item["list"], path))
        data_by_path[path] = data
    for item in VF3_CUSTOM_ITEMS:
        path = f"Furniture/{item['name']}.png"
        data = {
            "mobile_row": None,
            "mobile_source_id": None,
            "mobile_item_id": item["item_id"],
            "price": item["price"],
            "lock_generation": item["lock_generation"],
            "item_type": item["item_type"],
            "mobile_short_id": 0,
            "mobile_long_id": 0,
            "short_symbol": f"eString_VF3{item['name']}ShortDesc",
            "long_symbol": f"eString_VF3{item['name']}LongDesc",
            "short_description": item["short_description"],
            "long_description": item["long_description"],
            "section_name": "Accessory/Small Decor",
            "section_number": -1,
            "custom_pack": "VF3 furniture import batch 01",
        }
        items.append((item["short_description"], item["donor"], item["list"], path))
        data_by_path[path] = data
    for item in VF3_LIVING_ROOM_BATCH_02_ITEMS:
        path = f"Furniture/{item['name']}.png"
        data = {
            "mobile_row": None,
            "mobile_source_id": None,
            "mobile_item_id": item["item_id"],
            "price": item["price"],
            "lock_generation": item["lock_generation"],
            "item_type": item["item_type"],
            "mobile_short_id": 0,
            "mobile_long_id": 0,
            "short_symbol": f"eString_VF3{item['name']}ShortDesc",
            "long_symbol": f"eString_VF3{item['name']}LongDesc",
            "short_description": item["short_description"],
            "long_description": item["long_description"],
            "section_name": "General Appliances",
            "section_number": 5,
            "custom_pack": "VF3 living room import batch 02",
        }
        items.append((item["short_description"], item["donor"], item["list"], path))
        data_by_path[path] = data
    for item in INVISIBLE_OUTDOOR_ITEMS:
        path = f"Furniture/{item['name']}.png"
        data = {
            "mobile_row": None,
            "mobile_source_id": None,
            "mobile_item_id": item["item_id"],
            "price": item["price"],
            "lock_generation": item["lock_generation"],
            "item_type": item["item_type"],
            "mobile_short_id": 0,
            "mobile_long_id": 0,
            "short_symbol": f"eString_{item['name']}ShortDesc",
            "long_symbol": f"eString_{item['name']}LongDesc",
            "short_description": item["short_description"],
            "long_description": item["long_description"],
            "section_name": "Invisible Outdoors",
            "section_number": -1,
            "custom_pack": "Invisible outdoor decoration batch 01",
        }
        items.append((item["short_description"], item["donor"], item["list"], path))
        data_by_path[path] = data
    for item in INVISIBLE_TRANSPARENT_BASE_ITEMS:
        path = f"Furniture/{item['name']}.png"
        data = {
            "mobile_row": None,
            "mobile_source_id": None,
            "mobile_item_id": item["item_id"],
            "price": item["price"],
            "lock_generation": 12,
            "item_type": item["item_type"],
            "mobile_short_id": 0,
            "mobile_long_id": 0,
            "short_symbol": f"eString_{item['name']}ShortDesc",
            "long_symbol": f"eString_{item['name']}LongDesc",
            "short_description": item["short_description"],
            "long_description": item["long_description"],
            "section_name": "Invisible Base Furniture",
            "section_number": -1,
            "custom_pack": "Invisible base-furniture decoration batch 02",
        }
        items.append((item["short_description"], item["donor"], item["list"], path))
        data_by_path[path] = data
    for item in VF3_TV_ITEMS:
        path = f"Furniture/{item['name']}.png"
        data = {
            "mobile_row": None,
            "mobile_source_id": None,
            "mobile_item_id": item["item_id"],
            "price": item["price"],
            "lock_generation": item["lock_generation"],
            "item_type": item["item_type"],
            "mobile_short_id": 0,
            "mobile_long_id": 0,
            "short_symbol": f"eString_{item['name']}ShortDesc",
            "long_symbol": f"eString_{item['name']}LongDesc",
            "short_description": item["short_description"],
            "long_description": item["long_description"],
            "section_name": "General Appliances",
            "section_number": 5,
            "custom_pack": "VF3 television import batch 03",
        }
        items.append((item["short_description"], item["donor"], item["list"], path))
        data_by_path[path] = data
    return items, data_by_path


ITEMS, MOBILE_DATA_BY_PATH = load_mobile_rows()


def is_small_decor_safety_item(manifest_item):
    mobile = manifest_item["mobile_data"]
    return (
        mobile.get("section_name") == "Accessory/Small Decor"
        and int(manifest_item["donor_item"], 16) == SAFE_EMPTY_FMAP_DONOR
    )


def safety_fmap_reason(manifest_item):
    path = manifest_item["path"]
    if Path(path).name + ".fmap" in COUCH_FMAP_DONORS:
        return None
    if Path(path).name + ".fmap" in INVISIBLE_OUTDOOR_FMAP_DONORS:
        return None
    if Path(path).name + ".fmap" in INVISIBLE_TRANSPARENT_FMAP_DONORS:
        return None
    if Path(path).name + ".fmap" in VF3_TV_FMAP_DONORS:
        return None
    if path.startswith("Furniture/Couch"):
        return None
    if is_small_decor_safety_item(manifest_item):
        return "mobile small-decor behavior grid unsupported by desktop donor 0x256"
    return EXPLICIT_SAFE_EMPTY_FMAP_PATHS.get(path) or "added non-couch item is rendered-only to avoid unsupported desktop behavior dispatch"


def apply_generation_lock_distribution():
    generations = list(range(10, 31))
    base = len(ITEMS) // len(generations)
    remainder = len(ITEMS) % len(generations)
    schedule = []
    for pos, generation in enumerate(generations):
        schedule.extend([generation] * (base + (1 if pos < remainder else 0)))
    if len(schedule) != len(ITEMS):
        raise RuntimeError("Generation lock schedule does not match item count")
    for idx, (_name, _donor, _list_name, path) in enumerate(ITEMS):
        pack = MOBILE_DATA_BY_PATH[path].get("custom_pack", "")
        if pack.startswith("Invisible "):
            generation = 0
        else:
            generation = schedule[idx]
        MOBILE_DATA_BY_PATH[path]["lock_generation"] = generation
        MOBILE_DATA_BY_PATH[path]["assigned_lock_generation"] = generation


apply_generation_lock_distribution()

LIST_SYMBOLS = {
    "gAppliances": ("?gAppliancesList@@3PAW4EInventoryItem@@A", "?gAppliancesListSorted@@3PAW4EInventoryItem@@A", 15),
    "gFurniture2": ("?gFurniture2List@@3PAW4EInventoryItem@@A", "?gFurniture2ListSorted@@3PAW4EInventoryItem@@A", 88),
    "gFurniture3": ("?gFurniture3List@@3PAW4EInventoryItem@@A", "?gFurniture3ListSorted@@3PAW4EInventoryItem@@A", 26),
    "gFurniture4": ("?gFurniture4List@@3PAW4EInventoryItem@@A", "?gFurniture4ListSorted@@3PAW4EInventoryItem@@A", 74),
    "gFurniture5": ("?gFurniture5List@@3PAW4EInventoryItem@@A", "?gFurniture5ListSorted@@3PAW4EInventoryItem@@A", 12),
    "gAccessories": ("?gAccessoriesList@@3PAW4EInventoryItem@@A", "?gAccessoriesListSorted@@3PAW4EInventoryItem@@A", 47),
    "gPet": ("?gPetList@@3PAW4EInventoryItem@@A", "?gPetListSorted@@3PAW4EInventoryItem@@A", 13),
}

COUNT_PATCHES = {
    # old max-index compare, old push/sort count, new values patched at runtime below
    "gAppliances": (0x0E, 0x0F),
    "gFurniture2": (0x57, 0x58),
    "gFurniture3": (0x19, 0x1A),
    "gFurniture4": (0x49, 0x4A),
    "gFurniture5": (0x0B, 0x0C),
    "gAccessories": (0x2E, 0x2F),
    "gPet": (0x0C, 0x0D),
}

# Some store categories share the same desktop item count. Broadly replacing a
# GetCategoryItemCount return value can widen an unrelated stock category and
# make the store walk past the end of its original list. Keep known ambiguous
# categories surgical.
COUNT_RETURN_OFFSETS = {
    "gAppliances": 0x37,
}

# General Appliances has the same desktop visible count (15) as other lists
# after additive pet expansion, so broad byte-pattern widening can corrupt the
# pet category. Patch the appliance case at verified symbol-relative sites.
COUNT_PATCH_TARGETS = {
    "gAppliances": {
        "function": GET_CATEGORY_ITEM,
        "sort_count_push": 0x73,
        "max_index_cmp": 0x95,
    },
}

PET_STORE_ADDITIONS = [
    {
        "name": "Turtle",
        "item_id": 0x245,
        "list": "gPet",
        "source": "desktop-hidden/mobile pet",
    },
    {
        "name": "Hamster",
        "item_id": 0x247,
        "list": "gPet",
        "source": "desktop-hidden/mobile pet",
    },
]


def copy_obj_tree():
    if PATCHED.exists():
        shutil.rmtree(PATCHED)
    PATCHED.mkdir(parents=True)
    for obj in SRC_OBJS.glob("*.obj"):
        shutil.copy2(obj, PATCHED / obj.name)


def raw_records_by_item():
    data = json.loads((ANALYSIS / "furniture-records.json").read_text(encoding="utf-8"))
    return {r["item_id"]: r for r in data["records"]}


def image_records_by_id():
    data = json.loads((ANALYSIS / "image-descriptors.json").read_text(encoding="utf-8"))
    return {r["image_id"]: r for r in data["records"]}


def patch_all(buf: bytearray, old: bytes, new: bytes) -> int:
    n = 0
    pos = 0
    while True:
        hit = buf.find(old, pos)
        if hit < 0:
            return n
        buf[hit : hit + len(old)] = new
        n += 1
        pos = hit + len(new)


def patch_all_in_sections(obj: CoffObject, section_names, old: bytes, new: bytes) -> int:
    n = 0
    for sec in obj.sections:
        if sec.name not in section_names or not sec.raw_ptr or not sec.raw_size:
            continue
        start = sec.raw_ptr
        end = sec.raw_ptr + sec.raw_size
        pos = start
        while True:
            hit = obj.buf.find(old, pos, end)
            if hit < 0:
                break
            obj.buf[hit : hit + len(old)] = new
            n += 1
            pos = hit + len(new)
    return n


def patch_count_sites(obj, list_name, old_max, old_count, new_max_index, new_count):
    target = COUNT_PATCH_TARGETS.get(list_name)
    if target is None:
        n = 0
        n += patch_all(obj.buf, b"\x83\xFE" + bytes([old_max]), b"\x83\xFE" + bytes([new_max_index]))
        n += patch_all(obj.buf, b"\x6A" + bytes([old_count]), b"\x6A" + bytes([new_count]))
        n += patch_all(obj.buf, b"\xC7\x45\x08" + struct.pack("<I", old_count), b"\xC7\x45\x08" + struct.pack("<I", new_count))
        return {"mode": "pattern", "patches": n}

    sym = obj.symbol(target["function"])
    sec = obj.section(sym.section)
    patches = []

    push_raw = sec.raw_ptr + sym.value + target["sort_count_push"]
    expected_push = b"\x6A" + bytes([old_count])
    if obj.buf[push_raw : push_raw + len(expected_push)] != expected_push:
        raise RuntimeError(f"Unexpected {list_name} sort-count push bytes")
    obj.buf[push_raw : push_raw + len(expected_push)] = b"\x6A" + bytes([new_count])
    patches.append({"site": "sort_count_push", "offset": hex(target["sort_count_push"])})

    cmp_raw = sec.raw_ptr + sym.value + target["max_index_cmp"]
    expected_cmp = b"\x83\xFE" + bytes([old_max])
    if obj.buf[cmp_raw : cmp_raw + len(expected_cmp)] != expected_cmp:
        raise RuntimeError(f"Unexpected {list_name} max-index compare bytes")
    obj.buf[cmp_raw : cmp_raw + len(expected_cmp)] = b"\x83\xFE" + bytes([new_max_index])
    patches.append({"site": "max_index_cmp", "offset": hex(target["max_index_cmp"])})

    return {"mode": "targeted", "function": target["function"], "patches": patches}


def item_id_for(idx):
    data = MOBILE_DATA_BY_PATH[ITEMS[idx][3]]
    if "mobile_item_id" in data:
        return data["mobile_item_id"]
    return data["item_id"]


def outfit_item_id_for_body(gender, body_value):
    return OUTFIT_STORE_GENDER_ITEM_BASES[gender] + body_value


def outfit_body_for_item(item_id):
    for gender, base in OUTFIT_STORE_GENDER_ITEM_BASES.items():
        body_value = item_id - base
        if body_value in OUTFIT_STORE_BODY_VALUES:
            return gender, body_value
    return None


def outfit_store_entry_index(gender, body_value):
    return OUTFIT_STORE_GENDERS.index(gender) * len(OUTFIT_STORE_BODY_VALUES) + OUTFIT_STORE_BODY_VALUES.index(body_value)


def outfit_store_entries():
    entries = []
    for gender in OUTFIT_STORE_GENDERS:
        gender_title = gender.title()
        for body_value in OUTFIT_STORE_BODY_VALUES:
            is_holiday = body_value in HOLIDAY_BODY_VALUES
            entries.append({
                "entry_index": outfit_store_entry_index(gender, body_value),
                "item_id": outfit_item_id_for_body(gender, body_value),
                "gender": gender,
                "body_value": body_value,
                "name": f"{gender_title} {'Holiday ' if is_holiday else ''}Outfit Body {body_value:02d}",
                "price": OUTFIT_STORE_HOLIDAY_PRICE if is_holiday else OUTFIT_STORE_PRICE,
                "lock_generation": 0,
                "source": "holiday body row" if is_holiday else "base body row",
            })
    return entries


def image_id_for(idx):
    return ORIG_IMAGE_MAX + 1 + idx


def lock_image_id_for(frame):
    return ORIG_IMAGE_MAX + 1 + len(ITEMS) + frame


def visible_special_upgrade_icon_id_for(item_id):
    ordered = list(VISIBLE_SPECIAL_UPGRADE_ICON_FILES)
    return ORIG_IMAGE_MAX + 1 + len(ITEMS) + LOCKED_GENERATION_FRAME_COUNT + ordered.index(item_id)


def vf3_tv_anim_image_base(holiday_body_descriptor_count=0):
    return (
        ORIG_IMAGE_MAX
        + 1
        + len(ITEMS)
        + LOCKED_GENERATION_FRAME_COUNT
        + len(VISIBLE_SPECIAL_UPGRADE_ICON_FILES)
        + holiday_body_descriptor_count
    )


def vf3_tv_anim_image_id(label, holiday_body_descriptor_count=0):
    return vf3_tv_anim_image_base(holiday_body_descriptor_count) + list(VF3_TV_FLOATING_ANIMS).index(label)


def outfit_icon_image_base(holiday_body_descriptor_count=0):
    return vf3_tv_anim_image_base(holiday_body_descriptor_count) + len(VF3_TV_FLOATING_ANIMS)


def outfit_icon_image_id(gender, body_value, holiday_body_descriptor_count=0):
    return outfit_icon_image_base(holiday_body_descriptor_count) + outfit_store_entry_index(gender, body_value)


def outfit_icon_path(gender, body_value):
    return f"OutfitIcons/{gender.title()}_Body_{body_value:02d}.png"


def holiday_ornament_collection_image_base(holiday_body_descriptor_count=0):
    return outfit_icon_image_base(holiday_body_descriptor_count) + OUTFIT_STORE_ENTRY_COUNT


def holiday_ornament_collection_item_image_id(index, holiday_body_descriptor_count=0):
    return holiday_ornament_collection_image_base(holiday_body_descriptor_count) + index


def holiday_ornament_collection_background_image_id(holiday_body_descriptor_count=0):
    return holiday_ornament_collection_image_base(holiday_body_descriptor_count) + HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT


def holiday_ornament_collection_title_string_id():
    return (
        ORIG_STRING_ONE_PAST_MAX
        + len(ITEMS) * 2
        + mobile_island_event_string_count()
        + SPECIAL_UPGRADE_DESCRIPTION_COUNT
        + OUTFIT_STORE_ENTRY_COUNT * 2
        + len(BEHAVIOR_LABELS)
    )


def holiday_ornament_achievement_title_string_id():
    return holiday_ornament_collection_title_string_id() + 1


def holiday_ornament_achievement_desc_string_id():
    return holiday_ornament_collection_title_string_id() + 2


def villager_body_image_base():
    return ORIG_IMAGE_MAX + 1 + len(ITEMS) + LOCKED_GENERATION_FRAME_COUNT + len(VISIBLE_SPECIAL_UPGRADE_ICON_FILES)


def villager_body_image_index(gender, body_value, role, frame):
    gender_index = {"female": 0, "male": 1}[gender]
    body_index = HOLIDAY_BODY_VALUES.index(body_value)
    return (
        gender_index * len(HOLIDAY_BODY_VALUES) * HOLIDAY_BODY_FRAMES_PER_VALUE
        + body_index * HOLIDAY_BODY_FRAMES_PER_VALUE
        + HOLIDAY_BODY_ROLE_OFFSETS[role]
        + frame
    )


def villager_body_image_id(gender, body_value, role, frame):
    return villager_body_image_base() + villager_body_image_index(gender, body_value, role, frame)


def expected_furniture_frame_count(path):
    name = Path(path).name
    stem = Path(name).stem
    if path in EXPLICIT_FRAME_COUNTS_BY_PATH:
        return EXPLICIT_FRAME_COUNTS_BY_PATH[path]
    if path in VF3_FOUR_FRAME_FURNITURE:
        return 4
    if stem.startswith("Couch"):
        return 4
    if "Chair" in stem and "Chaise" not in stem:
        return 4
    return 2


def read_png_size(path):
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:
        return None


def sync_original_villager_sprite_sheets(manifest):
    """Copy user-supplied stock villager sheets into the build-local Images folder."""
    copied = []
    missing = []
    issues = []
    target_root = OUT / "Images"
    target_root.mkdir(parents=True, exist_ok=True)

    for filename in VILLAGER_SPRITE_SHEET_FILES:
        source = ORIGINAL_VF2_SPRITE_COPY_SOURCE_DIR / filename
        target = target_root / filename
        if not source.exists():
            missing.append(filename)
            continue
        try:
            backup = target.with_name(target.name + ".pre-user-sprite-copy.bak")
            if backup.exists():
                backup.unlink()
            shutil.copy2(source, target)
            copied.append({
                "filename": filename,
                "runtime_path": str(Path("Images") / filename),
                "size": list(read_png_size(target) or []),
                "bytes": target.stat().st_size,
            })
        except Exception as exc:
            issues.append({
                "filename": filename,
                "runtime_path": str(Path("Images") / filename),
                "reason": str(exc),
            })

    manifest["villager_sprite_sheet_copy"] = {
        "status": "copied to build-local Images folder" if copied and not missing and not issues else "partial_or_failed",
        "copy_source": "external build input only; not serialized as a runtime image source",
        "runtime_images_dir": "Images",
        "runtime_note": "The game uses the copied Images/*.png files in the modified build folder; it does not reference the originalimages source folder.",
        "copied": copied,
        "missing": missing,
        "issues": issues,
    }


def sync_vf3_living_room_sprite_strips(manifest):
    copied = []
    expanded = []
    missing = []
    issues = []
    for item in manifest["items"]:
        pair = VF3_SPRITE_STRIP_SOURCES.get(item["path"])
        if not pair:
            continue
        front_name, back_name = pair
        front_path = VF3_SPRITE_SOURCE_DIR / front_name
        back_path = VF3_SPRITE_SOURCE_DIR / back_name
        if not front_path.exists() or not back_path.exists():
            missing.append({
                "path": item["path"],
                "name": item["name"],
                "front": str(front_path),
                "back": str(back_path),
            })
            continue
        dst = OUT / "Images" / item["path"]
        try:
            from PIL import Image

            with Image.open(front_path).convert("RGBA") as front, Image.open(back_path).convert("RGBA") as back:
                cell_w = max(front.width, back.width)
                cell_h = max(front.height, back.height)
                strip = Image.new("RGBA", (cell_w * 4, cell_h), (0, 0, 0, 0))
                strip.paste(front, (0, cell_h - front.height))
                strip.paste(front.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (cell_w, cell_h - front.height))
                strip.paste(back, (cell_w * 2, cell_h - back.height))
                strip.paste(back.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (cell_w * 3, cell_h - back.height))
                dst.parent.mkdir(parents=True, exist_ok=True)
                backup = dst.with_name(dst.name + ".pre-vf3-sprite-strip.bak")
                if dst.exists() and not backup.exists():
                    shutil.copy2(dst, backup)
                strip.save(dst)
            copied.append({
                "path": item["path"],
                "name": item["name"],
                "front": str(front_path),
                "back": str(back_path),
                "new_size": [cell_w * 4, cell_h],
                "frames": 4,
                "backup": str(backup) if backup.exists() else None,
            })
        except Exception as exc:
            issues.append({
                "path": item["path"],
                "name": item["name"],
                "reason": str(exc),
            })
    expected_paths = sorted(VF3_FOUR_FRAME_FURNITURE)
    copied_paths = {entry["path"] for entry in copied}
    configured_paths = set(VF3_SPRITE_STRIP_SOURCES)
    for path in expected_paths:
        if path not in configured_paths:
            dst = OUT / "Images" / path
            try:
                from PIL import Image

                with Image.open(dst).convert("RGBA") as image:
                    if image.width % 2 != 0:
                        raise ValueError(f"existing two-frame fallback width is odd: {image.width}")
                    cell_w = image.width // 2
                    cell_h = image.height
                    front = image.crop((0, 0, cell_w, cell_h))
                    back = image.crop((cell_w, 0, cell_w * 2, cell_h))
                    strip = Image.new("RGBA", (cell_w * 4, cell_h), (0, 0, 0, 0))
                    strip.paste(front, (0, 0))
                    strip.paste(front.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (cell_w, 0))
                    strip.paste(back, (cell_w * 2, 0))
                    strip.paste(back.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (cell_w * 3, 0))
                    backup = dst.with_name(dst.name + ".pre-vf3-four-frame-expand.bak")
                    if dst.exists() and not backup.exists():
                        shutil.copy2(dst, backup)
                    strip.save(dst)
                expanded.append({
                    "path": path,
                    "reason": "expanded existing added two-frame sprite into four mirrored frames",
                    "old_size": [cell_w * 2, cell_h],
                    "new_size": [cell_w * 4, cell_h],
                    "frames": 4,
                    "backup": str(backup),
                })
            except Exception as exc:
                missing.append({
                    "path": path,
                    "reason": "no Sprite folder front/back mapping configured",
                    "fallback_error": str(exc),
                })
        elif path not in copied_paths and not any(entry.get("path") == path for entry in missing):
            missing.append({
                "path": path,
                "reason": "configured Sprite folder pair was not copied",
            })
    manifest["vf3_sprite_strips"] = {
        "source_dir": str(VF3_SPRITE_SOURCE_DIR),
        "copied": copied,
        "expanded_existing_two_frame": expanded,
        "missing": missing,
        "issues": issues,
    }


def sync_vf3_tv_sprite_strips(manifest):
    """Create two orientation cells while preserving each VF3 TV's footprint."""
    copied = []
    missing = []
    try:
        from PIL import Image

        for item in VF3_TV_ITEMS:
            source = VF3_SPRITE_SOURCE_DIR / item["source_png"]
            target = OUT / "Images" / "Furniture" / f"{item['name']}.png"
            if not source.exists():
                if target.exists():
                    copied.append({
                        "item": item["short_description"],
                        "source": str(source),
                        "target": str(target),
                        "status": "kept_existing_target_missing_source",
                    })
                else:
                    missing.append(str(source))
                continue
            with Image.open(source).convert("RGBA") as image:
                cell_w, cell_h = image.size
                strip = Image.new("RGBA", (cell_w * 2, cell_h), (0, 0, 0, 0))
                strip.paste(image, (0, 0), image)
                strip.paste(image.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (cell_w, 0), image.transpose(Image.Transpose.FLIP_LEFT_RIGHT))
                target.parent.mkdir(parents=True, exist_ok=True)
                strip.save(target)
            copied.append({"item": item["short_description"], "source": str(source), "target": str(target), "size": [cell_w * 2, cell_h], "frames": 2})
    except Exception as exc:
        missing.append(str(exc))
    manifest["vf3_tv_sprite_strips"] = {"copied": copied, "missing": missing}


def paste_scaled_tv_anim_frame(sheet, frame, label, column, row, cell_w, cell_h):
    from PIL import Image

    bbox = frame.getchannel("A").getbbox()
    if not bbox:
        return None
    x, y, width, height = VF3_TV_ANIMATION_SCREEN_BOXES[label]
    x = max(0, min(x, cell_w - 1))
    y = max(0, min(y, cell_h - 1))
    width = max(1, min(width, cell_w - x))
    height = max(1, min(height, cell_h - y))
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    scaled = frame.crop(bbox).resize((width, height), resampling)
    composed = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    composed.paste(scaled, (x, y), scaled)
    sheet.paste(composed, (column * cell_w, row * cell_h), composed)
    return composed, [x, y, width, height]


def sync_vf3_tv_animation_sheets(manifest):
    """Split supplied TV sheets and assemble bounded animation sheets."""
    copied = []
    missing = []
    try:
        from PIL import Image

        specs = []
        for item in VF3_TV_ITEMS:
            for label in item.get("animation_labels", ()):
                specs.append((label, item["name"]))
        destination = OUT / "Images" / "VF3TVAnimations"
        destination.mkdir(parents=True, exist_ok=True)
        for label, furniture_name in specs:
            furniture_path = OUT / "Images" / "Furniture" / f"{furniture_name}.png"
            if furniture_path.exists():
                with Image.open(furniture_path).convert("RGBA") as furniture:
                    cell_w, cell_h = furniture.width // 2, furniture.height
            else:
                cell_w, cell_h = 87, 101
                missing.append(f"{furniture_path}: missing, used fallback cell geometry")
            sheet = Image.new("RGBA", (cell_w * 6, cell_h * 3), (0, 0, 0, 0))
            present = 0
            supplied_sheet = LARGE_TV_ANIMATION_SHEETS.get(label)
            frame_prefix = VF3_TV_ANIMATION_FRAME_PREFIXES[label]
            frame_dir = destination / label
            frame_dir.mkdir(parents=True, exist_ok=True)
            if supplied_sheet:
                if not supplied_sheet.exists():
                    copied.append({
                        "source_sheet": str(supplied_sheet),
                        "status": "not_present_using_individual_frames",
                    })
                else:
                    with Image.open(supplied_sheet).convert("RGBA") as source_sheet:
                        for index in range(1, 19):
                            column = (index - 1) % 6
                            row = (index - 1) // 6
                            left = source_sheet.width * column // 6
                            right = source_sheet.width * (column + 1) // 6
                            top = source_sheet.height * row // 3
                            bottom = source_sheet.height * (row + 1) // 3
                            cell = source_sheet.crop((left, top, right, bottom))
                            bbox = cell.getchannel("A").getbbox()
                            if not bbox:
                                missing.append(f"{supplied_sheet}: blank frame {index}")
                                continue
                            frame = cell.crop(bbox)
                            composed = paste_scaled_tv_anim_frame(sheet, frame, label, column, row, cell_w, cell_h)
                            if not composed:
                                missing.append(f"{supplied_sheet}: blank trimmed frame {index}")
                                continue
                            frame_path = frame_dir / f"Frame{index:02d}.png"
                            composed[0].save(frame_path)
                            copied.append({
                                "source_sheet": str(supplied_sheet),
                                "frame": index,
                                "target": str(frame_path),
                                "source_trimmed_size": list(frame.size),
                                "screen_box": composed[1],
                            })
                            present += 1
            if not supplied_sheet or not supplied_sheet.exists():
                for index in range(1, 19):
                    source = VF3_SPRITE_SOURCE_DIR / f"{frame_prefix}_{index:02d}.png"
                    if not source.exists() and frame_prefix.startswith("FlatScreenSmallAnim"):
                        fallback_prefix = "TVAnimBig" if label.endswith("East") else "TVAnimBigE"
                        source = VF3_SPRITE_SOURCE_DIR / f"{fallback_prefix}_{index:02d}.png"
                    if not source.exists():
                        missing.append(str(source))
                        continue
                    with Image.open(source).convert("RGBA") as frame:
                        column = (index - 1) % 6
                        row = (index - 1) // 6
                        composed = paste_scaled_tv_anim_frame(sheet, frame, label, column, row, cell_w, cell_h)
                        if not composed:
                            missing.append(f"{source}: blank frame")
                            continue
                        frame_path = frame_dir / f"Frame{index:02d}.png"
                        composed[0].save(frame_path)
                        copied.append({
                            "source_frame": str(source),
                            "frame": index,
                            "target": str(frame_path),
                            "source_size": list(frame.size),
                            "screen_box": composed[1],
                        })
                        present += 1
            target = destination / f"VF3TVAnim{label}.png"
            sheet.save(target)
            copied.append({"sheet": str(target), "frames": present, "grid": [6, 3], "cell": [cell_w, cell_h], "size": list(sheet.size)})
            runtime_name = VF3_TV_RUNTIME_ANIMATION_NAMES.get(label)
            if runtime_name:
                runtime_target = OUT / "Images" / runtime_name
                sheet.save(runtime_target)
                copied.append({
                    "sheet": str(runtime_target),
                    "frames": present,
                    "grid": [6, 3],
                    "cell": [cell_w, cell_h],
                    "size": list(sheet.size),
                    "kind": "private_runtime_alias",
                })
    except Exception as exc:
        missing.append(str(exc))
    manifest["vf3_tv_animation_sheets"] = {"copied": copied, "missing": missing}


def sync_invisible_outdoor_sprites(manifest):
    copied = []
    missing = []
    for item in INVISIBLE_OUTDOOR_ITEMS:
        transparent_src = INVISIBLE_OUTDOOR_SPRITE_SOURCE_DIR / item["source_png"]
        base_src = OUT / "Images" / "Furniture" / item["base_png"]
        dst = OUT / "Images" / "Furniture" / f"{item['name']}.png"
        original_dst = dst.with_name(dst.name + "ORIGINAL")
        if not transparent_src.exists() or not base_src.exists():
            missing.append({
                "name": item["short_description"],
                "transparent_source": str(transparent_src),
                "base_source": str(base_src),
                "target": str(dst),
            })
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(transparent_src, original_dst)
        shutil.copy2(base_src, dst)
        copied.append({
            "name": item["short_description"],
            "transparent_source": str(transparent_src),
            "base_source": str(base_src),
            "target": str(dst),
            "original": str(original_dst),
            "bytes": dst.stat().st_size,
            "original_bytes": original_dst.stat().st_size,
            "size": list(read_png_size(dst) or []),
        })
    manifest["invisible_outdoor_sprites"] = {
        "source_dir": str(INVISIBLE_OUTDOOR_SPRITE_SOURCE_DIR),
        "copied": copied,
        "missing": missing,
    }


def sync_transparent_base_furniture_sprites(manifest):
    generated = []
    missing = []
    issues = []
    for item in INVISIBLE_TRANSPARENT_BASE_ITEMS:
        src = OUT / "Images" / "Furniture" / item["source_png"]
        dst = OUT / "Images" / "Furniture" / f"{item['name']}.png"
        original_dst = dst.with_name(dst.name + "ORIGINAL")
        if not src.exists():
            missing.append({
                "name": item["short_description"],
                "source": str(src),
                "target": str(dst),
            })
            continue
        try:
            from PIL import Image

            with Image.open(src).convert("RGBA") as image:
                override = INVISIBLE_TRANSPARENT_GRAPHIC_OVERRIDES.get(item["name"])
                if override and override.exists():
                    with Image.open(override).convert("RGBA") as supplied:
                        transparent = supplied.copy()
                else:
                    transparent = Image.new("RGBA", image.size, (0, 0, 0, 0))
                dst.parent.mkdir(parents=True, exist_ok=True)
                # The editable backup uses a custom suffix; specify PNG rather
                # than relying on Pillow to infer a format from `.pngORIGINAL`.
                transparent.save(original_dst, format="PNG")
                shutil.copy2(src, dst)
            generated.append({
                "name": item["short_description"],
                "source": str(src),
                "target": str(dst),
                "original": str(original_dst),
                "size": list(read_png_size(dst) or []),
                "frame_count": item["frame_count"],
                "bytes": dst.stat().st_size,
                "original_bytes": original_dst.stat().st_size,
                "transparent_override": str(override) if override and override.exists() else None,
            })
        except Exception as exc:
            issues.append({
                "name": item["short_description"],
                "source": str(src),
                "target": str(dst),
                "reason": str(exc),
            })
    manifest["transparent_base_furniture_sprites"] = {
        "generated": generated,
        "missing": missing,
        "issues": issues,
    }


def sync_separated_villager_sheets(manifest):
    """Export live sheets and a canonical per-body, per-frame hierarchy."""
    export_root = OUT / "Images" / "VillagerSheets"
    groups = {
        export_root / "Heads": [
            "female_heads00.png", "female_heads10.png",
            "male_heads00.png", "male_heads10.png",
            "bigheads00.png", "bigheads10.png",
        ],
        export_root / "Bodies": list(VILLAGER_SPRITE_SHEET_FILES),
    }
    copied = []
    missing = []
    for destination, filenames in groups.items():
        destination.mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            source = OUT / "Images" / filename
            target = destination / filename
            if source.exists():
                shutil.copy2(source, target)
                copied.append({"source": str(source), "target": str(target)})
            else:
                missing.append(str(source))

    holiday_root = export_root / "Bodies" / "HolidayOutfits"
    holiday_files = [str(path.relative_to(OUT)) for path in holiday_root.rglob("*.png")]

    # The renderer consumes 91x91 grids, but editing and validation should
    # happen against unambiguous individual frames for each role.
    body_frames = []
    try:
        from PIL import Image

        role_specs = [
            ("bodies", 32),
            ("actions", 15),
            ("sit", 9),
        ]
        for gender in OUTFIT_STORE_GENDERS:
            gender_title = gender.title()
            for role, frame_count in role_specs:
                source = OUT / "Images" / f"{gender}_{role}00.png"
                if not source.exists():
                    missing.append(str(source))
                    continue
                with Image.open(source).convert("RGBA") as sheet:
                    row_count = sheet.height // HOLIDAY_BODY_CELL_SIZE
                    column_count = min(frame_count, sheet.width // HOLIDAY_BODY_CELL_SIZE)
                    for body_type in range(row_count):
                        body_dir = OUT / "Images" / "VillagerBodies" / gender_title / f"Body_{body_type:02d}" / role
                        body_dir.mkdir(parents=True, exist_ok=True)
                        for frame_index in range(column_count):
                            box = (
                                frame_index * HOLIDAY_BODY_CELL_SIZE,
                                body_type * HOLIDAY_BODY_CELL_SIZE,
                                (frame_index + 1) * HOLIDAY_BODY_CELL_SIZE,
                                (body_type + 1) * HOLIDAY_BODY_CELL_SIZE,
                            )
                            target = body_dir / f"Frame{frame_index:02d}.png"
                            sheet.crop(box).save(target)
                        body_frames.append({
                            "gender": gender,
                            "body_type": body_type,
                            "role": role,
                            "frames": column_count,
                            "folder": str(body_dir.relative_to(OUT)),
                            "holiday": body_type >= HOLIDAY_BODY_BASE_ROWS,
                        })
    except Exception as exc:
        missing.append(f"body-frame export: {exc}")

    manifest["villager_sheet_exports"] = {
        "root": str(export_root),
        "copied": copied,
        "holiday_outfit_files": holiday_files,
        "body_frame_folders": body_frames,
        "missing": missing,
        "runtime_note": "VillagerBodies contains 91x91 body/action/sit frame exports. The desktop renderer still uses build-local Images sheets for stock rows; holiday body values are 50-53.",
    }


def _alpha_bbox(image):
    return image.convert("RGBA").getchannel("A").getbbox()


def _normalize_holiday_body_frame(source_image, target_template):
    from PIL import Image

    source_bbox = _alpha_bbox(source_image)
    target_bbox = _alpha_bbox(target_template)
    output = Image.new("RGBA", (HOLIDAY_BODY_CELL_SIZE, HOLIDAY_BODY_CELL_SIZE), (0, 0, 0, 0))
    if not source_bbox or not target_bbox:
        return output
    target_width = target_bbox[2] - target_bbox[0]
    target_height = target_bbox[3] - target_bbox[1]
    cropped = source_image.crop(source_bbox)
    resized = cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
    output.alpha_composite(resized, (target_bbox[0], target_bbox[1]))
    return output


def _image_source_roots():
    roots = [OUT / "Images"]
    outputs = ROOT / "outputs"
    if outputs.exists():
        roots.extend(
            build / "Images"
            for build in sorted(
                outputs.glob("VF2-Mobile-Furniture-With-Island-Events-B*"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        )
    roots.append(FALLBACK_HOLIDAY_BODY_BUILD / "Images")

    unique = []
    seen = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen and root.exists():
            unique.append(root)
            seen.add(key)
    return unique


def _find_source_image(sheet_name, min_width=0, min_height=0):
    short = []
    for root in _image_source_roots():
        candidate = root / sheet_name
        if not candidate.exists():
            continue
        size = read_png_size(candidate)
        if size and size[0] >= min_width and size[1] >= min_height:
            return candidate, short
        short.append(f"{candidate}: size {size}, required {min_width}x{min_height}")
    return None, short


def sync_holiday_body_types(manifest):
    """Append complete action/body/sit rows for four additive holiday bodies."""
    appended = []
    missing = []
    issues = []
    export_root = OUT / "Images" / "VillagerSheets" / "Bodies" / "HolidayOutfits"
    try:
        from PIL import Image

        archive = ZipFile(HOLIDAY_OUTFIT_ARCHIVE) if HOLIDAY_OUTFIT_ARCHIVE.exists() else None
        archive_names = set(archive.namelist()) if archive else set()
        try:
            for role_spec in HOLIDAY_BODY_ROLE_SPECS:
                role = role_spec["role"]
                first_frame, last_frame = role_spec["source_range"]
                frame_count = last_frame - first_frame + 1
                for gender, (sheet_name, archive_folder, prefix) in role_spec["sheets"].items():
                    target = OUT / "Images" / sheet_name
                    if not target.exists():
                        missing.append(str(target))
                        continue
                    with Image.open(target).convert("RGBA") as existing:
                        expected_size = (
                            HOLIDAY_BODY_CELL_SIZE * role_spec["columns"],
                            HOLIDAY_BODY_CELL_SIZE * HOLIDAY_BODY_BASE_ROWS,
                        )
                        if existing.size != expected_size:
                            issues.append({"sheet": str(target), "reason": f"expected {expected_size}, got {existing.size}"})
                            continue
                        backup = target.with_name(target.name + ".pre-holiday-bodies.bak")
                        if not backup.exists():
                            existing.save(backup, format="PNG")
                        expanded = Image.new(
                            "RGBA",
                            (existing.width, existing.height + HOLIDAY_BODY_CELL_SIZE * len(HOLIDAY_BODY_SET_IDS)),
                            (0, 0, 0, 0),
                        )
                        expanded.paste(existing, (0, 0))
                        gender_title = gender.title()
                        for row, set_id in enumerate(HOLIDAY_BODY_SET_IDS):
                            body_value = HOLIDAY_BODY_BASE_ROWS + row
                            frame_targets = []
                            for frame_number in range(first_frame, last_frame + 1):
                                role_frame = frame_number - first_frame
                                generated_frame = (
                                    GENERATED_VILLAGER_BODIES
                                    / gender_title
                                    / f"Body_{body_value:02d}"
                                    / f"{gender_title}_Body_{body_value:02d}_{role}_Frame_{role_frame:02d}.png"
                                )
                                normalized = None
                                source_kind = None
                                if generated_frame.exists():
                                    normalized = Image.open(generated_frame).convert("RGBA")
                                    source_kind = "generated"
                                elif archive:
                                    archive_name = (
                                        f"Holiday Outfits/{archive_folder}/{prefix}{set_id:02d}_{frame_number:04d}.png"
                                    )
                                    if archive_name in archive_names:
                                        raw = archive.read(archive_name)
                                        with Image.open(BytesIO(raw)).convert("RGBA") as mobile_frame:
                                            template_box = (
                                                role_frame * HOLIDAY_BODY_CELL_SIZE,
                                                (HOLIDAY_BODY_BASE_ROWS - 1) * HOLIDAY_BODY_CELL_SIZE,
                                                (role_frame + 1) * HOLIDAY_BODY_CELL_SIZE,
                                                HOLIDAY_BODY_BASE_ROWS * HOLIDAY_BODY_CELL_SIZE,
                                            )
                                            template = existing.crop(template_box)
                                            normalized = _normalize_holiday_body_frame(mobile_frame, template)
                                            source_kind = "archive"
                                if normalized is None:
                                    missing.append(str(generated_frame))
                                    continue
                                if normalized.size != (HOLIDAY_BODY_CELL_SIZE, HOLIDAY_BODY_CELL_SIZE):
                                    issues.append({
                                        "frame": str(generated_frame),
                                        "reason": f"expected 91x91, got {normalized.size}",
                                    })
                                    continue
                                x = role_frame * HOLIDAY_BODY_CELL_SIZE
                                y = body_value * HOLIDAY_BODY_CELL_SIZE
                                expanded.paste(normalized, (x, y), normalized)
                                export_path = export_root / gender / f"Body_{body_value:02d}" / role / f"Frame{role_frame:02d}.png"
                                export_path.parent.mkdir(parents=True, exist_ok=True)
                                normalized.save(export_path)
                                frame_targets.append(str(export_path.relative_to(OUT)))
                                normalized.close()
                            appended.append({
                                "gender": gender,
                                "role": role,
                                "body_type": body_value,
                                "source_set": set_id,
                                "frames": len(frame_targets),
                                "expected_frames": frame_count,
                                "source": source_kind or "missing",
                                "exported_frames": frame_targets,
                            })
                        expanded.save(target)
        finally:
            if archive:
                archive.close()

        # The stock rare generator returns 44..49. Widen it to 44..53 so all
        # four appended sets can be generated without replacing existing types.
        villager = CoffObject(PATCHED / "Villager.obj")
        rare = villager.symbol("?GenRareBodyType@CVillager@@SAHXZ")
        data = villager.section_data(rare.section)
        prologue = bytes(data[rare.value : rare.value + 3])
        if prologue not in (b"\x6A\x06\xE8", b"\x6A\x0A\xE8"):
            raise RuntimeError("unexpected GenRareBodyType prologue")
        data[rare.value + 1] = 10
        villager.write(PATCHED / "Villager.obj")
        manifest["holiday_body_types"] = {
            "archive": str(HOLIDAY_OUTFIT_ARCHIVE),
            "appended": appended,
            "missing": missing,
            "issues": issues,
            "body_type_range": [HOLIDAY_BODY_BASE_ROWS, HOLIDAY_BODY_BASE_ROWS + len(HOLIDAY_BODY_SET_IDS) - 1],
            "rare_generator": "expanded from 44-49 to 44-53",
            "runtime_sheet_rows": "expanded all female/male bodies, actions, and sit sheets from 50 to 54 rows",
        }
    except Exception as exc:
        issues.append({"reason": str(exc)})
        manifest["holiday_body_types"] = {
            "archive": str(HOLIDAY_OUTFIT_ARCHIVE),
            "appended": appended,
            "missing": missing,
            "issues": issues,
        }


def sync_holiday_body_runtime_frames(manifest):
    """Generate cropped, individually addressable holiday body frames.

    These files are runtime assets for the B57 folder-backed body renderer.
    Stock spritesheets remain untouched; the helper applies the saved crop
    offsets when drawing each one-cell image.
    """
    output_root = OUT / "Images" / "VillagerBodies"
    frames = []
    missing = []
    issues = []
    source_roots = []
    try:
        from PIL import Image

        output_root.mkdir(parents=True, exist_ok=True)
        archive = ZipFile(HOLIDAY_OUTFIT_ARCHIVE) if HOLIDAY_OUTFIT_ARCHIVE.exists() else None
        archive_names = set(archive.namelist()) if archive else set()
        sheet_cache = {}
        source_roots = [str(root) for root in _image_source_roots()]
        try:
            for role_spec in HOLIDAY_BODY_ROLE_SPECS:
                role = role_spec["role"]
                first_frame, last_frame = role_spec["source_range"]
                for gender, (sheet_name, archive_folder, prefix) in role_spec["sheets"].items():
                    template_sheet, template_skips = _find_source_image(
                        sheet_name,
                        min_width=HOLIDAY_BODY_CELL_SIZE * role_spec["columns"],
                        min_height=HOLIDAY_BODY_CELL_SIZE * HOLIDAY_BODY_BASE_ROWS,
                    )
                    if not template_sheet:
                        missing.append(sheet_name)
                        missing.extend(template_skips)
                        continue
                    with Image.open(template_sheet).convert("RGBA") as existing:
                        for body_value, source_set in zip(HOLIDAY_BODY_VALUES, HOLIDAY_BODY_SET_IDS):
                            gender_title = gender.title()
                            fallback_sheet, fallback_skips = _find_source_image(
                                sheet_name,
                                min_width=HOLIDAY_BODY_CELL_SIZE * role_spec["columns"],
                                min_height=(body_value + 1) * HOLIDAY_BODY_CELL_SIZE,
                            )
                            for frame_number in range(first_frame, last_frame + 1):
                                role_frame = frame_number - first_frame
                                template_box = (
                                    role_frame * HOLIDAY_BODY_CELL_SIZE,
                                    (HOLIDAY_BODY_BASE_ROWS - 1) * HOLIDAY_BODY_CELL_SIZE,
                                    (role_frame + 1) * HOLIDAY_BODY_CELL_SIZE,
                                    HOLIDAY_BODY_BASE_ROWS * HOLIDAY_BODY_CELL_SIZE,
                                )
                                template = existing.crop(template_box)
                                normalized = None
                                source_kind = None
                                archive_name = f"Holiday Outfits/{archive_folder}/{prefix}{source_set:02d}_{frame_number:04d}.png"
                                if archive and archive_name in archive_names:
                                    with Image.open(BytesIO(archive.read(archive_name))).convert("RGBA") as mobile_frame:
                                        normalized = _normalize_holiday_body_frame(mobile_frame, template)
                                    source_kind = "holiday_archive"
                                else:
                                    if fallback_sheet:
                                        if fallback_sheet not in sheet_cache:
                                            sheet_cache[fallback_sheet] = Image.open(fallback_sheet).convert("RGBA")
                                        fallback = sheet_cache[fallback_sheet]
                                        box = (
                                            role_frame * HOLIDAY_BODY_CELL_SIZE,
                                            body_value * HOLIDAY_BODY_CELL_SIZE,
                                            (role_frame + 1) * HOLIDAY_BODY_CELL_SIZE,
                                            (body_value + 1) * HOLIDAY_BODY_CELL_SIZE,
                                        )
                                        normalized = fallback.crop(box)
                                        source_kind = f"expanded_sheet:{fallback_sheet}"
                                if normalized is None:
                                    missing.append(archive_name)
                                    missing.extend(fallback_skips)
                                    continue
                                bbox = _alpha_bbox(normalized)
                                if bbox:
                                    cropped = normalized.crop(bbox)
                                    offset_x, offset_y = bbox[0], bbox[1]
                                else:
                                    cropped = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
                                    offset_x, offset_y = 0, 0
                                dst = (
                                    output_root
                                    / gender_title
                                    / f"Body_{body_value:02d}"
                                    / role
                                    / f"Frame{role_frame:02d}.png"
                                )
                                dst.parent.mkdir(parents=True, exist_ok=True)
                                cropped.save(dst)
                                frames.append({
                                    "gender": gender,
                                    "body_value": body_value,
                                    "source_set": source_set,
                                    "role": role,
                                    "frame": role_frame,
                                    "image_id": hex(villager_body_image_id(gender, body_value, role, role_frame)),
                                    "path": str(dst.relative_to(OUT / "Images")).replace("\\", "/"),
                                    "offset": [offset_x, offset_y],
                                    "size": list(cropped.size),
                                    "source": source_kind,
                                })
        finally:
            for image in sheet_cache.values():
                image.close()
            if archive:
                archive.close()
    except Exception as exc:
        issues.append({"reason": str(exc)})
    manifest["holiday_body_runtime_frames"] = {
        "status": "generated individual folder-backed body frames" if frames else "failed_or_missing",
        "root": str(output_root),
        "body_values": list(HOLIDAY_BODY_VALUES),
        "source_sets": list(HOLIDAY_BODY_SET_IDS),
        "frames": frames,
        "missing": missing,
        "issues": issues,
        "source_roots": source_roots,
        "runtime_note": "The original sheets stay as fallback; body values 50-53 draw from these individual images.",
    }


def _outfit_icon_source_roots():
    return _image_source_roots()


def _find_outfit_icon_action_frame(gender, body_value):
    sheet_name = OUTFIT_STORE_ICON_SOURCE_SHEETS[gender]
    required_height = (body_value + 1) * HOLIDAY_BODY_CELL_SIZE
    missing = []
    for root in _outfit_icon_source_roots():
        candidate = root / sheet_name
        if not candidate.exists():
            continue
        size = read_png_size(candidate)
        if not size:
            missing.append(f"{candidate}: unreadable PNG size")
            continue
        column_count = size[0] // HOLIDAY_BODY_CELL_SIZE
        if column_count > 0 and size[1] >= required_height:
            return candidate, column_count - 1, missing
        missing.append(
            f"{candidate}: size {size}, required at least "
            f"{HOLIDAY_BODY_CELL_SIZE}x{required_height}"
        )
    return None, None, missing


def sync_outfit_store_icon_art(manifest):
    """Generate one store-preview icon per added male/female outfit row."""
    from PIL import Image

    output_root = OUT / "Images" / "OutfitIcons"
    output_root.mkdir(parents=True, exist_ok=True)
    entries = []
    missing = []
    issues = []
    sheet_cache = {}

    try:
        for entry in outfit_store_entries():
            gender = entry["gender"]
            body_value = entry["body_value"]
            target = output_root / f"{gender.title()}_Body_{body_value:02d}.png"
            source, action_frame, skipped = _find_outfit_icon_action_frame(gender, body_value)
            if not source:
                missing.append(OUTFIT_STORE_ICON_SOURCE_SHEETS[gender])
                missing.extend(skipped)
                continue
            if source not in sheet_cache:
                sheet_cache[source] = Image.open(source).convert("RGBA")
            sheet = sheet_cache[source]
            icon = sheet.crop((
                action_frame * HOLIDAY_BODY_CELL_SIZE,
                body_value * HOLIDAY_BODY_CELL_SIZE,
                (action_frame + 1) * HOLIDAY_BODY_CELL_SIZE,
                (body_value + 1) * HOLIDAY_BODY_CELL_SIZE,
            ))

            icon.save(target)
            entries.append({
                "item_id": hex(entry["item_id"]),
                "gender": gender,
                "body_value": body_value,
                "image_id": hex(outfit_icon_image_id(gender, body_value, HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0)),
                "path": str(target.relative_to(OUT / "Images")).replace("\\", "/"),
                "source": str(source),
                "source_kind": f"{OUTFIT_STORE_ICON_ROLE}_sheet_last_frame",
                "source_frame": action_frame,
                "size": list(icon.size),
            })
    except Exception as exc:
        issues.append({"reason": str(exc)})
    finally:
        for image in sheet_cache.values():
            image.close()

    manifest["outfit_store_icons"] = {
        "status": "generated" if len(entries) == OUTFIT_STORE_ENTRY_COUNT else "partial_or_failed",
        "root": str(output_root),
        "image_base": hex(outfit_icon_image_base(HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0)),
        "source_rule": {
            "role": OUTFIT_STORE_ICON_ROLE,
            "sheets": OUTFIT_STORE_ICON_SOURCE_SHEETS,
            "frame": "last 91px frame column",
        },
        "expected_count": OUTFIT_STORE_ENTRY_COUNT,
        "generated_count": len(entries),
        "entries": entries,
        "missing": missing,
        "issues": issues,
    }


def sync_visible_special_upgrade_icon_art(manifest):
    output_root = OUT / "Images"
    output_root.mkdir(parents=True, exist_ok=True)
    entries = []
    missing = []

    for item_id, filename in VISIBLE_SPECIAL_UPGRADE_ICON_FILES.items():
        target = output_root / filename
        source = None
        status = "existing"
        if not target.exists():
            for root in _outfit_icon_source_roots():
                candidate = root / filename
                if candidate.exists() and candidate.resolve() != target.resolve():
                    source = candidate
                    break
            if source:
                shutil.copy2(source, target)
                status = "copied"
            else:
                missing.append(filename)
                status = "missing"
        else:
            source = target

        entries.append({
            "item_id": hex(item_id),
            "image_id": hex(visible_special_upgrade_icon_id_for(item_id)),
            "path": filename,
            "source": str(source) if source else None,
            "status": status,
            "size": list(read_png_size(target) or []),
        })

    manifest["visible_special_upgrade_icon_art"] = {
        "status": "available" if not missing else "partial_or_missing",
        "root": str(output_root),
        "image_base": hex(visible_special_upgrade_icon_id_for(min(VISIBLE_SPECIAL_UPGRADE_ICON_FILES))),
        "expected_count": len(VISIBLE_SPECIAL_UPGRADE_ICON_FILES),
        "entries": entries,
        "missing": missing,
    }


def decode_rgba4444_pvr(path):
    from PIL import Image

    raw = path.read_bytes()
    header = struct.unpack_from("<13I", raw, 0)
    header_size = header[0]
    height = header[1]
    width = header[2]
    data_size = header[5]
    bit_count = header[6]
    red_mask, green_mask, blue_mask, alpha_mask = header[7:11]
    if header_size != 0x34 or bit_count != 16:
        raise RuntimeError(f"Unsupported PVR header in {path}")
    if (red_mask, green_mask, blue_mask, alpha_mask) != (0xF000, 0x0F00, 0x00F0, 0x000F):
        raise RuntimeError(f"Unsupported PVR channel masks in {path}")

    pixels = raw[header_size : header_size + data_size]
    rgba = bytearray(width * height * 4)
    out = 0
    for i in range(0, len(pixels), 2):
        value = pixels[i] | (pixels[i + 1] << 8)
        rgba[out + 0] = ((value & 0xF000) >> 12) * 17
        rgba[out + 1] = ((value & 0x0F00) >> 8) * 17
        rgba[out + 2] = ((value & 0x00F0) >> 4) * 17
        rgba[out + 3] = (value & 0x000F) * 17
        out += 4
    return Image.frombytes("RGBA", (width, height), bytes(rgba))


def sync_holiday_ornament_collection_art(manifest):
    from PIL import Image

    image_base = holiday_ornament_collection_image_base(HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0)
    output_root = OUT / "Images" / "CollectionOrnaments"
    output_root.mkdir(parents=True, exist_ok=True)
    background_target = OUT / "Images" / HOLIDAY_ORNAMENT_BACKGROUND_FILENAME
    status = {
        "source_dat": str(HOLIDAY_ORNAMENT_MOBILE_ATLAS_DAT),
        "source_pvr": str(HOLIDAY_ORNAMENT_MOBILE_ATLAS_PVR),
        "image_base": hex(image_base),
        "background_image_id": hex(holiday_ornament_collection_background_image_id(HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0)),
        "entries": [],
    }
    if not HOLIDAY_ORNAMENT_MOBILE_ATLAS_DAT.exists() or not HOLIDAY_ORNAMENT_MOBILE_ATLAS_PVR.exists():
        status.update({"status": "missing_mobile_atlas"})
        manifest["holiday_ornament_collection_art"] = status
        return

    atlas = decode_rgba4444_pvr(HOLIDAY_ORNAMENT_MOBILE_ATLAS_PVR)
    tex_w, tex_h = atlas.size
    resample = Image.Resampling.LANCZOS
    background_crop = atlas.crop((0, tex_h - 600, 800, tex_h))
    background_crop.resize((1024, 768), Image.Resampling.BILINEAR).save(background_target)
    status["background"] = {
        "path": str(background_target),
        "source_box_bottom_origin": [0, 0, 800, 600],
        "output_size": [1024, 768],
    }

    for index, (filename, x, y, width, height) in enumerate(HOLIDAY_ORNAMENT_ATLAS_RECORDS):
        target = output_root / filename
        crop_y = tex_h - y - height
        icon = atlas.crop((x, crop_y, x + width, crop_y + height))
        scaled_size = (
            max(1, round(width * HOLIDAY_ORNAMENT_IMAGE_SCALE)),
            max(1, round(height * HOLIDAY_ORNAMENT_IMAGE_SCALE)),
        )
        icon = icon.resize(scaled_size, resample)
        icon.save(target)
        status["entries"].append({
            "collectable": hex(HOLIDAY_ORNAMENT_COLLECTABLE_START + index),
            "image_id": hex(holiday_ornament_collection_item_image_id(index, HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0)),
            "path": str(target.relative_to(OUT / "Images")).replace("\\", "/"),
            "source_box_bottom_origin": [x, y, width, height],
            "output_size": list(icon.size),
        })

    manifest["holiday_ornament_collection_art"] = {
        **status,
        "status": "generated" if len(status["entries"]) == HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT else "partial",
        "output_root": str(output_root),
    }


def patch_holiday_body_lookup(manifest):
    """Allow the native animator to address the four additive outfit rows.

    A villager's ``body`` value is an outfit ID.  The desktop animator uses
    that ID as the row in the 32-frame body grid, but stock code clamps it to
    0..49.  The holiday IDs are 50..53, so the old clamp silently displayed
    row 49 for those poses.  Extend only that bound; base outfit rows and the
    native frame ordering remain untouched.
    """
    obj = CoffObject(PATCHED / "AnimManager.obj")
    functions = [
        {
            "name": "?GetScaledLinkToNextPt@CAnimManager@@QAE?AUldwPoint@@W4EAnimFrame@@W4EAnimPart@@W4EAnimGender@@HMPAPAVldwImageGrid@@PAH@Z",
            "body_arg_offset": 0x18,
        },
        {
            "name": "?GetScaledLinkToPrevPt@CAnimManager@@QAE?AUldwPoint@@W4EAnimFrame@@W4EAnimPart@@W4EAnimGender@@HM@Z",
            "body_arg_offset": 0x18,
        },
    ]
    patches = []
    max_row = HOLIDAY_BODY_BASE_ROWS + len(HOLIDAY_BODY_SET_IDS) - 1
    row_count = max_row + 1
    for function in functions:
        function_name = function["name"]
        body_arg_offset = function["body_arg_offset"]
        symbol = obj.symbol(function_name)
        section = obj.section(symbol.section)
        raw = section.raw_ptr + symbol.value
        data = obj.buf
        # The body NextPt/PrevPt overloads encode: cmp body, 0x32;
        # cmovl row, body; default row 0x31.  Replace only those body-row
        # immediates.  Head overloads deliberately stay stock 0..49.
        window = data[raw : raw + 0xB0]
        cmp_pattern = bytes([0x83, 0x7D, body_arg_offset, HOLIDAY_BODY_BASE_ROWS])
        cmp_at = window.find(cmp_pattern)
        if cmp_at < 0:
            raise RuntimeError(f"unexpected body-row clamp in {function_name}")
        data[raw + cmp_at + 3] = row_count
        default_at = window.find(b"\xB9\x31\x00\x00\x00")
        if default_at < 0:
            default_at = window.find(b"\xBA\x31\x00\x00\x00")
        if default_at < 0:
            raise RuntimeError(f"unexpected default body row in {function_name}")
        data[raw + default_at + 1] = max_row
        patches.append({
            "function": function_name,
            "old_valid_rows": [0, HOLIDAY_BODY_BASE_ROWS - 1],
            "new_valid_rows": [0, max_row],
        })
    obj.write(PATCHED / "AnimManager.obj")
    manifest["holiday_body_lookup"] = {
        "status": "native body row clamp expanded for additive holiday outfit IDs",
        "body_values": list(range(HOLIDAY_BODY_BASE_ROWS, max_row + 1)),
        "patched_functions": patches,
    }


def write_holiday_body_draw_helper(manifest):
    frame_entries = {
        (entry["gender"], entry["body_value"], entry["role"], entry["frame"]): entry
        for entry in manifest.get("holiday_body_runtime_frames", {}).get("frames", [])
    }
    image_ids = []
    offset_x = []
    offset_y = []
    for gender in ("female", "male"):
        for body_value in HOLIDAY_BODY_VALUES:
            for role in ("bodies", "actions", "sit"):
                for frame in range(HOLIDAY_BODY_ROLE_FRAME_COUNTS[role]):
                    entry = frame_entries.get((gender, body_value, role, frame), {})
                    image_ids.append(villager_body_image_id(gender, body_value, role, frame))
                    offset = entry.get("offset") or [0, 0]
                    offset_x.append(int(offset[0]))
                    offset_y.append(int(offset[1]))

    def c_array(values):
        chunks = []
        for i in range(0, len(values), 16):
            chunks.append("    " + ", ".join(str(v) for v in values[i : i + 16]))
        return ",\n".join(chunks)

    helper = f'''// Generated by patch_mobile_furniture_pack.py.
// Folder-backed renderer for additive villager body values {HOLIDAY_BODY_VALUES[0]}-{HOLIDAY_BODY_VALUES[-1]}.
class ldwImageGrid;
enum EImage {{ eImageDummy = 0 }};

class ldwGameWindow {{
public:
    void DrawScaled(ldwImageGrid* grid, int x, int y, int row, int col, int scale, bool mirror);
}};

class theGraphicsManager {{
public:
    static theGraphicsManager* Get();
    ldwImageGrid* GetImageGrid(EImage image);
}};

static const int kHolidayBodyFirst = {HOLIDAY_BODY_VALUES[0]};
static const int kHolidayBodyCount = {len(HOLIDAY_BODY_VALUES)};
static const int kFramesPerHolidayBody = {HOLIDAY_BODY_FRAMES_PER_VALUE};
static const int kFrameImageCount = {len(image_ids)};
static const int kRoleOffsets[3] = {{{HOLIDAY_BODY_ROLE_OFFSETS["bodies"]}, {HOLIDAY_BODY_ROLE_OFFSETS["actions"]}, {HOLIDAY_BODY_ROLE_OFFSETS["sit"]}}};
static const int kRoleFrameCounts[3] = {{{HOLIDAY_BODY_ROLE_FRAME_COUNTS["bodies"]}, {HOLIDAY_BODY_ROLE_FRAME_COUNTS["actions"]}, {HOLIDAY_BODY_ROLE_FRAME_COUNTS["sit"]}}};
static const int kImageIds[kFrameImageCount] = {{
{c_array(image_ids)}
}};
static const int kOffsetX[kFrameImageCount] = {{
{c_array(offset_x)}
}};
static const int kOffsetY[kFrameImageCount] = {{
{c_array(offset_y)}
}};

static int VF2ResolveBodyRole(theGraphicsManager* graphics, ldwImageGrid* stockGrid) {{
    if (!graphics || !stockGrid) return -1;
    const int imageIds[6] = {{577, 578, 579, 581, 582, 583}};
    for (int i = 0; i < 6; ++i) {{
        if (stockGrid == graphics->GetImageGrid((EImage)imageIds[i])) return i;
    }}
    return -1;
}}

extern "C" void __cdecl VF2DrawVillagerBodyFrameImpl(
    ldwGameWindow* window,
    ldwImageGrid* stockGrid,
    int x,
    int y,
    int body,
    int frame,
    int scale,
    int mirror
) {{
    theGraphicsManager* graphics = theGraphicsManager::Get();
    int roleSlot = VF2ResolveBodyRole(graphics, stockGrid);
    if (window && graphics && roleSlot >= 0 && body >= kHolidayBodyFirst && body < kHolidayBodyFirst + kHolidayBodyCount) {{
        int role = roleSlot % 3;
        if (frame >= 0 && frame < kRoleFrameCounts[role]) {{
            int gender = roleSlot / 3;
            int bodyIndex = body - kHolidayBodyFirst;
            int index = gender * kHolidayBodyCount * kFramesPerHolidayBody
                + bodyIndex * kFramesPerHolidayBody
                + kRoleOffsets[role]
                + frame;
            if (index >= 0 && index < kFrameImageCount) {{
                ldwImageGrid* frameGrid = graphics->GetImageGrid((EImage)kImageIds[index]);
                if (frameGrid) {{
                    window->DrawScaled(frameGrid, x + kOffsetX[index], y + kOffsetY[index], 0, 0, scale, mirror != 0);
                    return;
                }}
            }}
        }}
    }}
    int fallbackBody = body;
    if (roleSlot >= 0 && body >= kHolidayBodyFirst && body < kHolidayBodyFirst + kHolidayBodyCount) {{
        fallbackBody = kHolidayBodyFirst - 1;
    }}
    if (window) window->DrawScaled(stockGrid, x, y, fallbackBody, frame, scale, mirror != 0);
}}

extern "C" __declspec(naked) void VF2DrawVillagerBodyFrame() {{
    __asm {{
        mov eax, esp
        push dword ptr [eax+1Ch]
        push dword ptr [eax+18h]
        push dword ptr [eax+14h]
        push dword ptr [eax+10h]
        push dword ptr [eax+0Ch]
        push dword ptr [eax+08h]
        push dword ptr [eax+04h]
        push ecx
        call VF2DrawVillagerBodyFrameImpl
        add esp, 20h
        ret 1Ch
    }}
}}
'''
    (PATCHED / "vf2_villager_body_frames.cpp").write_text(helper, encoding="ascii")
    manifest["holiday_body_draw_helper"] = {
        "source": str(PATCHED / "vf2_villager_body_frames.cpp"),
        "image_ids": len(image_ids),
        "body_values": list(HOLIDAY_BODY_VALUES),
        "stock_fallback": "recognized holiday body grids clamp to row 49 if an individual frame image is unavailable",
    }


def patch_holiday_body_draw_redirect(manifest):
    obj = CoffObject(PATCHED / "Villager.obj")
    helper_sym = obj.append_undefined_symbol("_VF2DrawVillagerBodyFrame")
    targets = [
        ("?DrawDetailVillager@CVillager@@QAEXUldwPoint@@_N@Z", 0x124),
        ("?DrawEventVillager@CVillager@@QAEXHHW4EBodyPosition@@M_N@Z", 0x18E),
    ]
    patched = []
    for symbol_name, reloc_delta in targets:
        sym = obj.symbol(symbol_name)
        obj.retarget_relocation(sym.section, sym.value + reloc_delta, helper_sym, IMAGE_REL_I386_REL32)
        patched.append({"function": symbol_name, "relocation": hex(sym.value + reloc_delta)})
    obj.write(PATCHED / "Villager.obj")
    manifest["holiday_body_draw_redirect"] = {
        "status": "body draw calls redirected through folder-backed holiday renderer",
        "patched": patched,
        "stock_body_values": "0-49 fall back to the native DrawScaled call",
        "holiday_body_values": list(HOLIDAY_BODY_VALUES),
    }


def patch_invisible_hammock_drop_action(manifest):
    """Extend the stock hammock hotspot predicate to include the added item."""
    obj = CoffObject(PATCHED / "HotSpot.obj")
    symbol = obj.symbol("?Hammock@CHotSpot@@CA?B_NAAVCVillager@@@Z")
    section = obj.section(symbol.section)
    raw = section.raw_ptr + symbol.value
    expected = b"\x68\xE1\x01\x00\x00\xB9"
    if obj.buf[raw + 4 : raw + 10] != expected:
        raise RuntimeError("unexpected stock hammock hotspot predicate")

    # Reuse the stock call instruction/REL32 relocation at +0x0B.  It now
    # calls a tiny helper that returns true when either base HammockStd or the
    # additive InvisibleHammock is in the world.  The native action below it
    # remains exactly the same eBehavior_LieInHammockNoLeadIn route.
    obj.buf[raw + 4 : raw + 11] = b"\x90" * 7
    helper = obj.append_undefined_symbol("_VF2EitherHammockInWorld")
    obj.retarget_relocation(symbol.section, symbol.value + 0x0F, helper, 0x14)
    obj.write(PATCHED / "HotSpot.obj")

    helper_cpp = r'''enum EInventoryItem { eInventoryItemPlaceholder = 0 };

class CFurnitureManager {
public:
    bool IsInWorld(EInventoryItem item);
};

extern CFurnitureManager FurnitureManager;

extern "C" bool __cdecl VF2EitherHammockInWorld()
{
    return FurnitureManager.IsInWorld((EInventoryItem)0x1E1) ||
           FurnitureManager.IsInWorld((EInventoryItem)0x30C);
}
'''
    helper_path = PATCHED / "vf2_invisible_hammock.cpp"
    helper_path.write_text(helper_cpp, encoding="ascii")
    manifest["invisible_hammock_drop_action"] = {
        "status": "added to the stock hammock hotspot predicate",
        "base_item": "0x1E1",
        "added_item": "0x30C",
        "native_behavior": "eBehavior_LieInHammockNoLeadIn (0x24)",
        "base_hammock_modified": False,
    }


def sync_invisible_furniture_reference_sets(manifest):
    """Bundle the user's editable invisible-furniture variants without activating them."""
    sources = {
        "Invisible Furniture - Transparent": Path(r"C:\Users\Owner\Downloads\Invisible Furniture - Transparent"),
        "Invisible Furniture - Base Graphics": Path(r"C:\Users\Owner\Downloads\Invisible Furniture - Base Graphics"),
    }
    copied = []
    missing = []
    root = OUT / "ReferenceAssets"
    for name, source in sources.items():
        target = root / name
        if source.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)
            source_note = str(source)
        else:
            # Build the editable pair from the active base image and its saved
            # transparent original. This keeps both folders in every build.
            target.mkdir(parents=True, exist_ok=True)
            for image in (OUT / "Images" / "Furniture").glob("Invisible*.png"):
                transparent = image.with_name(image.name + "ORIGINAL")
                if name == "Invisible Furniture - Transparent" and transparent.exists():
                    shutil.copy2(transparent, target / image.name)
                elif name == "Invisible Furniture - Base Graphics":
                    shutil.copy2(image, target / image.name)
            source_note = "generated from active base sheets and .pngORIGINAL variants"
        if name == "Invisible Furniture - Transparent":
            for item_name, override in INVISIBLE_TRANSPARENT_GRAPHIC_OVERRIDES.items():
                if override.exists():
                    shutil.copy2(override, target / f"{item_name}.png")
        copied.append({"name": name, "source": source_note, "target": str(target), "png_count": len(list(target.glob("*.png")))})
    manifest["invisible_furniture_reference_sets"] = {"copied": copied, "missing": missing, "active_game_assets": "unchanged"}


def item_string_ids(idx):
    base = ORIG_STRING_ONE_PAST_MAX + idx * 2
    return base, base + 1


EVENT_KIND_SUFFIX = {
    "Title": "Title",
    "Desc": "Desc",
    "ChoiceA": "ChoiceA",
    "ChoiceB": "ChoiceB",
    "ResultA": "ResultA",
    "ResultB": "ResultB",
}

EVENT_KIND_ORDER = ["Title", "Desc", "ChoiceA", "ChoiceB", "ResultA", "ResultB"]

EVENT_CHOICE_OVERRIDES = {
    ("GroupOfKidsAtTheDoor", "ChoiceA"): "Take one",
    ("GroupOfKidsAtTheDoor", "ChoiceB"): "No thanks",
    ("HearStrangeSound", "ChoiceA"): "Open the door",
    ("HearStrangeSound", "ChoiceB"): "Walk away",
    ("MenInBlackAtDoor", "ChoiceA"): "Open the door",
    ("MenInBlackAtDoor", "ChoiceB"): "Back away",
    ("MetallicKnockingOnDoor", "ChoiceA"): "Open the door",
    ("MetallicKnockingOnDoor", "ChoiceB"): "Back away",
    ("Volunteer", "ChoiceA"): "Volunteer",
    ("Volunteer", "ChoiceB"): "Sorry, no",
}

EMAIL_EVENT_NAMES = {
    "EmailFromACME",
    "EmailFromAntonioGuildenstern",
    "EmailFromSchool",
    "GreatUncleElmer",
    "InterestingArticleAboutFossils",
    "MarchingBandTripExpenses",
    "RIPUncleAlpert",
}


def event_string_id_for(idx):
    return ORIG_STRING_ONE_PAST_MAX + len(ITEMS) * 2 + idx


def visible_special_upgrade_desc_id_for(index):
    return ORIG_STRING_ONE_PAST_MAX + len(ITEMS) * 2 + mobile_island_event_string_count() + index


def outfit_string_ids_for_entry(entry_index):
    base = (
        ORIG_STRING_ONE_PAST_MAX
        + len(ITEMS) * 2
        + mobile_island_event_string_count()
        + SPECIAL_UPGRADE_DESCRIPTION_COUNT
        + entry_index * 2
    )
    return base, base + 1


def behavior_label_string_id_for(index):
    return (
        ORIG_STRING_ONE_PAST_MAX
        + len(ITEMS) * 2
        + mobile_island_event_string_count()
        + SPECIAL_UPGRADE_DESCRIPTION_COUNT
        + OUTFIT_STORE_ENTRY_COUNT * 2
        + index
    )


def normalize_event_text(value):
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(part.strip() for part in text.split())
    fixes = {
        "electricaloutlet": "electrical outlet",
        "open,ready": "open, ready",
        "There's reward": "There's a reward",
        "it's artificial intelligence": "its artificial intelligence",
        "God love you": "God loves you",
        "Ressurection": "Resurrection",
    }
    for old, new in fixes.items():
        text = text.replace(old, new)
    return text


def load_mobile_island_events():
    if not MOBILE_EVENT_TEXT_PACK.exists() or not MOBILE_EVENT_MAPPING_CSV.exists():
        return []
    event_text = {}
    with MOBILE_EVENT_TEXT_PACK.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            kind = row["kind"]
            if kind not in EVENT_KIND_SUFFIX:
                continue
            event_name = row["event_class"].removeprefix("CEvent")
            value = row["value"]
            if not value:
                continue
            value = EVENT_CHOICE_OVERRIDES.get((event_name, kind), value)
            event_text.setdefault(event_name, {})[kind] = normalize_event_text(value)

    ordered_names = []
    with MOBILE_EVENT_MAPPING_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            event_name = row["mobile_event"]
            if event_name in event_text and event_name not in ordered_names:
                ordered_names.append(event_name)

    events = []
    flat_index = 0
    for slot_index, event_name in enumerate(ordered_names):
        strings = []
        ids = {}
        for kind in EVENT_KIND_ORDER:
            text = event_text[event_name].get(kind)
            if text is None:
                ids[kind] = 0
                continue
            string_id = event_string_id_for(flat_index)
            key = f"eEvent{event_name}{EVENT_KIND_SUFFIX[kind]}"
            strings.append({
                "kind": kind,
                "string_id": string_id,
                "key": key,
                "text": text,
            })
            ids[kind] = string_id
            flat_index += 1
        has_choices = ids.get("ChoiceA", 0) != 0 and ids.get("ChoiceB", 0) != 0
        event_class = f"CEvent{event_name}"
        # Mobile classes named CEventEmail* use the stock email-event path.
        # Keep the known non-prefixed email shells and Subject:-style entries too.
        is_email = (
            event_class.startswith("CEventEmail")
            or event_name in EMAIL_EVENT_NAMES
            or event_text[event_name].get("Title", "").startswith("Subject:")
        )
        events.append({
            "name": event_name,
            "class": event_class,
            "slot": 0x61 + slot_index,
            "strings": strings,
            "ids": ids,
            "has_choices": has_choices,
            "is_email_event": is_email,
        })
    return events


def mobile_island_event_string_count():
    return sum(len(event["strings"]) for event in load_mobile_island_events())


def c_string(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def max_item_offset():
    return max(item_id_for(i) for i in range(len(ITEMS))) - 0x1AD


def patch_furniture_manager(manifest):
    obj = CoffObject(PATCHED / "FurnitureManager.obj")
    records = raw_records_by_item()
    item_sym = obj.symbol(ITEMINFO)
    insert_off = item_sym.value + ORIG_FURNITURE_COUNT * RECORD_SIZE
    payload = bytearray()
    behavior_safety_overrides = []
    vf3_tv_animation_records = []
    vf3_tv_behavior_contracts = []
    vf3_tv_by_name = {item["short_description"]: item for item in VF3_TV_ITEMS}
    for idx, (name, donor_id, _list_name, path) in enumerate(ITEMS):
        donor_vals = records[donor_id]["raw_u32"]
        vals = donor_vals[:]
        mobile = MOBILE_DATA_BY_PATH[path]
        vals[0] = item_id_for(idx)
        vals[1] = image_id_for(idx)
        vals[2] = mobile["price"]
        vals[3] = mobile["lock_generation"]
        vals[4] = mobile["item_type"]
        if mobile.get("section_name") == "Accessory/Small Decor" and donor_id == 0x256:
            # Desktop has no behavior handlers for several mobile-only holiday
            # food/decor interactions. Keep these on the inert desktop donor
            # type so dropping a person onto them cannot dispatch into an
            # unsupported mobile behavior path.
            vals[4] = records[donor_id]["raw_u32"][4]
            if vals[4] != mobile["item_type"]:
                behavior_safety_overrides.append({
                    "item": name,
                    "item_id": hex(item_id_for(idx)),
                    "path": path,
                    "mobile_item_type": mobile["item_type"],
                    "desktop_donor_item_type": vals[4],
                    "donor_item": hex(donor_id),
                })
        vf3_tv = vf3_tv_by_name.get(name)
        if vf3_tv:
            west_label, east_label = vf3_tv["animation_labels"]
            # The generated VF3 TV furniture strip stores the source sprite as
            # frame 0 and its horizontal mirror as frame 1. That frame order is
            # opposite the stock donor's animation order, so assign the private
            # animation enums by the generated frame slant, not by donor order.
            # The private animation cells are already padded to their furniture
            # canvas, so their floating animation origin is the cell origin.
            vals[0x24 // 4] = VF3_TV_FLOATING_ANIMS[west_label]["enum"]
            vals[0x28 // 4] = VF3_TV_FLOATING_ANIMS[east_label]["enum"]
            vals[0x2C // 4] = 0
            vals[0x30 // 4] = 0
            vals[0x34 // 4] = 0
            vals[0x38 // 4] = 0
            vals[0x3C // 4] = 0
            vals[0x40 // 4] = 0
            vals[0x44 // 4] = 0
            vals[0x48 // 4] = 0
            vals[0x4C // 4] = 0
            vals[0x50 // 4] = 0
            vf3_tv_animation_records.append({
                "item": name,
                "item_id": hex(vals[0]),
                "frame0_enum": hex(vals[0x24 // 4]),
                "frame1_enum": hex(vals[0x28 // 4]),
                "frame0_label": west_label,
                "frame1_label": east_label,
                "offsets": {"x": [0, 0, 0, 0], "y": [0, 0, 0, 0]},
            })
        vals[5], vals[6] = item_string_ids(idx)
        vals[0x58 // 4] = 0
        if vf3_tv:
            allowed = {0, 1, 2, 3, 5, 6, *range(0x24 // 4, 0x50 // 4 + 1)}
            drift = [
                {
                    "offset": hex(i * 4),
                    "donor": hex(donor_vals[i]),
                    "added": hex(vals[i]),
                }
                for i in range(len(vals))
                if i not in allowed and vals[i] != donor_vals[i]
            ]
            if drift:
                raise RuntimeError(f"VF3 TV behavior fields drifted from base TV donor for {name}: {drift}")
            vf3_tv_behavior_contracts.append({
                "item": name,
                "item_id": hex(vals[0]),
                "donor_item": hex(donor_id),
                "donor_behavior": "base flat-screen TV",
                "item_type": vals[4],
                "verified": "all non-identity, non-store, non-animation fields match donor 0x1F3",
            })
        payload += struct.pack("<" + "I" * (RECORD_SIZE // 4), *vals)
    obj.insert_section_bytes(item_sym.section, insert_off, bytes(payload))

    new_max = max_item_offset()
    range_patches = 0
    for reg in [b"\x3D", b"\x81\xFE", b"\x81\xF9", b"\x81\xFA"]:
        old = reg + struct.pack("<I", 0xFB)
        new = reg + struct.pack("<I", new_max)
        range_patches += patch_all(obj.buf, old, new)
    end_patches = patch_all(obj.buf, struct.pack("<I", ORIG_FURNITURE_COUNT * RECORD_SIZE), struct.pack("<I", (ORIG_FURNITURE_COUNT + len(ITEMS)) * RECORD_SIZE))
    fmap_refresh_patches = patch_all_in_sections(
        obj,
        {".text$mn"},
        b"\x81\xFE" + struct.pack("<I", 0xFC),
        b"\x81\xFE" + struct.pack("<I", new_max + 1),
    )

    lookup_sym = obj.symbol(ITEMLOOKUP)
    lookup_sec = obj.section(lookup_sym.section)
    obj.grow_bss_section(lookup_sym.section, lookup_sec.raw_size, (new_max - 0xFB) * 4)

    obj.write(PATCHED / "FurnitureManager.obj")
    manifest["FurnitureManager"] = {
        "added_records": len(ITEMS),
        "new_item_max_offset": hex(new_max),
        "range_patches": range_patches,
        "scan_end_patches": end_patches,
        "fmap_refresh_patches": fmap_refresh_patches,
        "behavior_safety_overrides": behavior_safety_overrides,
        "vf3_tv_animation_records": vf3_tv_animation_records,
        "vf3_tv_behavior_contracts": vf3_tv_behavior_contracts,
    }


def patch_inventory_manager(manifest):
    obj = CoffObject(PATCHED / "InventoryManager.obj")
    by_list = {}
    for idx, item in enumerate(ITEMS):
        by_list.setdefault(item[2], []).append(item_id_for(idx))
    for pet in PET_STORE_ADDITIONS:
        by_list.setdefault(pet["list"], []).append(pet["item_id"])
    outfit_entries = outfit_store_entries()
    outfit_ids = [entry["item_id"] for entry in outfit_entries]

    list_manifest = {}
    # Insert from highest section offset to lowest to reduce offset surprises.
    work = []
    for list_name, ids in by_list.items():
        list_sym_name, sorted_sym_name, old_count = LIST_SYMBOLS[list_name]
        list_sym = obj.symbol(list_sym_name)
        sorted_sym = obj.symbol(sorted_sym_name)
        work.append((list_sym.section, list_sym.value + old_count * 4, list_name, ids, old_count, sorted_sym_name))
    for _sec, _off, list_name, ids, old_count, sorted_sym_name in sorted(work, reverse=True):
        list_sym_name, _sorted, _old = LIST_SYMBOLS[list_name]
        list_sym = obj.symbol(list_sym_name)
        obj.insert_section_bytes(list_sym.section, list_sym.value + old_count * 4, struct.pack("<" + "I" * len(ids), *ids))
        sorted_sym = obj.symbol(sorted_sym_name)
        obj.grow_bss_section(sorted_sym.section, sorted_sym.value + old_count * 4, len(ids) * 4)
        list_manifest[list_name] = {"old_count": old_count, "new_count": old_count + len(ids), "added_ids": [hex(x) for x in ids]}

    clothing_sym = obj.symbol(GCLOTHINGLIST)
    clothing_old_count = 6
    clothing_new_count = clothing_old_count + len(outfit_ids)
    holiday_body_descriptor_count = HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0
    obj.insert_section_bytes(
        clothing_sym.section,
        clothing_sym.value + clothing_old_count * 4,
        struct.pack("<" + "I" * len(outfit_ids), *outfit_ids),
    )
    list_manifest["gClothingList"] = {
        "old_count": clothing_old_count,
        "new_count": clothing_new_count,
        "added_ids": [hex(x) for x in outfit_ids],
    }

    new_max = max_item_offset()
    range_patches = 0
    for reg in [b"\x3D", b"\x81\xFE", b"\x81\xF9", b"\x81\xFA"]:
        range_patches += patch_all(obj.buf, reg + struct.pack("<I", 0xFB), reg + struct.pack("<I", new_max))

    count_patches = {}
    count_return_patches = {}
    for list_name, info in list_manifest.items():
        if list_name not in COUNT_PATCHES:
            continue
        old_max, old_count = COUNT_PATCHES[list_name]
        new_count = info["new_count"]
        new_max_index = new_count - 1
        count_patches[list_name] = patch_count_sites(obj, list_name, old_max, old_count, new_max_index, new_count)
        # CScrollingStoreScene asks GetCategoryItemCount() for the visible
        # row count. If these return values stay at the desktop counts, newly
        # sorted additive items appear to replace base items in the store.
        targeted_return_off = COUNT_RETURN_OFFSETS.get(list_name)
        if targeted_return_off is not None:
            count_sym = obj.symbol(GET_CATEGORY_ITEM_COUNT)
            count_sec = obj.section(count_sym.section)
            count_raw = count_sec.raw_ptr + count_sym.value + targeted_return_off
            expected = b"\xB8" + struct.pack("<I", old_count) + b"\x5E\x5D\xC2\x04\x00"
            if obj.buf[count_raw : count_raw + len(expected)] != expected:
                raise RuntimeError(f"Unexpected targeted GetCategoryItemCount return for {list_name}")
            obj.buf[count_raw : count_raw + 5] = b"\xB8" + struct.pack("<I", new_count)
            count_return_patches[list_name] = {"mode": "targeted", "offset": hex(targeted_return_off), "patches": 1}
        else:
            count_return_patches[list_name] = {
                "mode": "pattern",
                "patches": patch_all(
                    obj.buf,
                    b"\xB8" + struct.pack("<I", old_count) + b"\x5E\x5D\xC2\x04\x00",
                    b"\xB8" + struct.pack("<I", new_count) + b"\x5E\x5D\xC2\x04\x00",
                ),
            }

    item_sym = obj.symbol(GET_CATEGORY_ITEM)
    item_sec = obj.section(item_sym.section)
    clothing_bounds_off = item_sym.value + 0x313
    clothing_bounds_raw = item_sec.raw_ptr + clothing_bounds_off
    if obj.buf[clothing_bounds_raw : clothing_bounds_raw + 3] != b"\x83\xFE\x05":
        raise RuntimeError("Unexpected GetCategoryItem clothing bounds bytes")
    obj.buf[clothing_bounds_raw : clothing_bounds_raw + 3] = b"\x83\xFE" + bytes([clothing_new_count - 1])

    count_sym = obj.symbol(GET_CATEGORY_ITEM_COUNT)
    count_sec = obj.section(count_sym.section)
    clothing_count_off = count_sym.value + 0xA8
    clothing_count_raw = count_sec.raw_ptr + clothing_count_off
    if obj.buf[clothing_count_raw : clothing_count_raw + 5] != b"\xB8\x06\x00\x00\x00":
        raise RuntimeError("Unexpected GetCategoryItemCount clothing return bytes")
    obj.buf[clothing_count_raw : clothing_count_raw + 5] = b"\xB8" + struct.pack("<I", clothing_new_count)

    def insert_inventory_getter_hook(function_name, helper_name, returns_stdcall=True):
        symbol = obj.symbol(function_name)
        section = obj.section(symbol.section)
        insert_off = symbol.value + 3
        raw = section.raw_ptr + insert_off
        if obj.buf[raw - 3 : raw] != b"\x55\x8B\xEC":
            raise RuntimeError(f"Unexpected prologue in {function_name}")
        helper_sym = obj.append_undefined_symbol(helper_name)
        if returns_stdcall:
            payload = bytearray()
            payload += b"\x51"                  # preserve this/ecx for stock fallthrough
            payload += b"\xFF\x75\x08"          # push [ebp+8]
            payload += b"\xE8\x00\x00\x00\x00"  # call helper
            payload += b"\x83\xC4\x04"          # add esp,4
            payload += b"\x59"                  # restore this/ecx before any fallthrough
            payload += b"\x83\xF8\xFF"          # cmp eax,-1
            payload += b"\x74\x04"              # je original body
            payload += b"\x5D"                  # pop ebp
            payload += b"\xC2\x04\x00"          # ret 4
        else:
            payload = bytearray()
            payload += b"\xFF\x75\x08"
            payload += b"\xE8\x00\x00\x00\x00"
            payload += b"\x83\xC4\x04"
            payload += b"\x83\xF8\xFF"
            payload += b"\x74\x02"
            payload += b"\x5D"
            payload += b"\xC3"
        obj.insert_section_bytes(symbol.section, insert_off, bytes(payload))
        call_reloc_offset = insert_off + (5 if returns_stdcall else 4)
        obj.append_relocation(symbol.section, call_reloc_offset, helper_sym, IMAGE_REL_I386_REL32)
        return {
            "function": function_name,
            "helper": helper_name,
            "insert_offset": hex(insert_off),
            "preserves_ecx_for_stock_fallthrough": bool(returns_stdcall),
        }

    outfit_getter_hooks = [
        insert_inventory_getter_hook("?GetNumAvailable@CInventoryManager@@QAEHW4EInventoryItem@@@Z", "_VF2GetOutfitStoreNumAvailable"),
        insert_inventory_getter_hook("?GetOutfit@CInventoryManager@@QAEHW4EInventoryItem@@@Z", "_VF2GetOutfitStoreBodyValue"),
        insert_inventory_getter_hook("?GetPrice@CInventoryManager@@QAEHW4EInventoryItem@@@Z", "_VF2GetOutfitStorePrice"),
        insert_inventory_getter_hook("?GetLockGenerationLevel@CInventoryManager@@QAEHW4EInventoryItem@@@Z", "_VF2GetOutfitStoreLockGeneration"),
        insert_inventory_getter_hook("?GetShortDesc@CInventoryManager@@SA?AW4StringId@@W4EInventoryItem@@@Z", "_VF2GetOutfitStoreShortDesc", returns_stdcall=False),
        insert_inventory_getter_hook("?GetLongDesc@CInventoryManager@@SA?AW4StringId@@W4EInventoryItem@@@Z", "_VF2GetOutfitStoreLongDesc", returns_stdcall=False),
    ]

    def insert_draw_item_hook(function_name, helper_name, ret_bytes, arg_offsets):
        symbol = obj.symbol(function_name)
        section = obj.section(symbol.section)
        insert_off = symbol.value + 3
        raw = section.raw_ptr + insert_off
        if obj.buf[raw - 3 : raw] != b"\x55\x8B\xEC":
            raise RuntimeError(f"Unexpected prologue in {function_name}")
        helper_sym = obj.append_undefined_symbol(helper_name)
        payload = bytearray()
        payload += b"\x51"  # preserve this/ecx for fallthrough
        for offset in reversed(arg_offsets):
            payload += b"\xFF\x75" + bytes([offset])
        payload += b"\xE8\x00\x00\x00\x00"
        payload += b"\x83\xC4" + bytes([len(arg_offsets) * 4])
        payload += b"\x59"
        payload += b"\x84\xC0"
        payload += b"\x74\x04"
        payload += b"\x5D"
        payload += ret_bytes
        obj.insert_section_bytes(symbol.section, insert_off, bytes(payload))
        obj.append_relocation(symbol.section, insert_off + 2 + len(arg_offsets) * 3, helper_sym, IMAGE_REL_I386_REL32)
        return {"function": function_name, "helper": helper_name, "insert_offset": hex(insert_off)}

    outfit_draw_hooks = [
        insert_draw_item_hook(
            "?DrawItem@CInventoryManager@@QAEXUldwPoint@@W4EInventoryItem@@W4EInventoryItemState@@W4EInventoryItemPosition@@_N@Z",
            "_VF2DrawOutfitStoreIconPoint",
            b"\xC2\x18\x00",
            (0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C),
        ),
        insert_draw_item_hook(
            "?DrawItem@CInventoryManager@@QAEXUldwRect@@W4EInventoryItem@@W4EInventoryItemState@@W4EInventoryItemPosition@@_N@Z",
            "_VF2DrawOutfitStoreIconRect",
            b"\xC2\x20\x00",
            (0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24),
        ),
    ]

    # SortGenLockItems only included locked items up to generation 9. Custom
    # furniture uses higher official/mod locks, so raise the visible lock window.
    generation_cap_patches = patch_all(obj.buf, b"\x83\xF8\x09", b"\x83\xF8\x1E")

    # The desktop Outdoors category is the one category where additive counts
    # can collide with another base category count. In B12, gFurniture5 grew
    # from 12 to 26, then the later Bedroom patch (old count 26 -> 30) also
    # rewrote the freshly-patched Outdoors immediates and exposed blank rows.
    # Force the three gFurniture5 count sites after the broad replacements.
    outdoor_exact_count_patch = {}
    if "gFurniture5" in list_manifest:
        outdoor_count = list_manifest["gFurniture5"]["new_count"]
        outdoor_max_index = outdoor_count - 1
        item_sym = obj.symbol(GET_CATEGORY_ITEM)
        item_sec = obj.section(item_sym.section)
        item_raw = item_sec.raw_ptr + item_sym.value
        count_sym = obj.symbol(GET_CATEGORY_ITEM_COUNT)
        count_sec = obj.section(count_sym.section)
        count_raw = count_sec.raw_ptr + count_sym.value

        sort_count_off = item_raw + 0x250
        bounds_off = item_raw + 0x272
        return_off = count_raw + 0x83
        obj.buf[sort_count_off : sort_count_off + 2] = b"\x6A" + bytes([outdoor_count])
        obj.buf[bounds_off : bounds_off + 3] = b"\x83\xFE" + bytes([outdoor_max_index])
        obj.buf[return_off : return_off + 5] = b"\xB8" + struct.pack("<I", outdoor_count)
        outdoor_exact_count_patch = {
            "new_count": outdoor_count,
            "new_max_index": outdoor_max_index,
            "sort_count_offset": hex(0x250),
            "bounds_offset": hex(0x272),
            "count_return_offset": hex(0x83),
        }

    obj.write(PATCHED / "InventoryManager.obj")
    manifest["InventoryManager"] = {
        "lists": list_manifest,
        "pet_store_additions": [
            {"name": pet["name"], "item_id": hex(pet["item_id"]), "source": pet["source"]}
            for pet in PET_STORE_ADDITIONS
        ],
        "range_patches": range_patches,
        "count_patches": count_patches,
        "count_return_patches": count_return_patches,
        "outdoor_exact_count_patch": outdoor_exact_count_patch,
        "outfit_store_additions": {
            "status": "gClothingList extended additively",
            "base_count": clothing_old_count,
            "new_count": clothing_new_count,
            "body_values": list(OUTFIT_STORE_BODY_VALUES),
            "genders": list(OUTFIT_STORE_GENDERS),
            "items": [
                {
                    "item_id": hex(entry["item_id"]),
                    "gender": entry["gender"],
                    "body_value": entry["body_value"],
                    "name": entry["name"],
                    "price": entry["price"],
                    "source": entry["source"],
                    "icon_image_id": hex(outfit_icon_image_id(entry["gender"], entry["body_value"], holiday_body_descriptor_count)),
                }
                for entry in outfit_entries
            ],
            "getter_hooks": outfit_getter_hooks,
            "draw_hooks": outfit_draw_hooks,
        },
        "generation_sort_cap": {"old": 9, "new": 30, "patches": generation_cap_patches},
    }


def patch_visible_special_upgrades(manifest):
    obj = CoffObject(PATCHED / "InventoryManager.obj")

    services_sym = obj.symbol(GSERVICESLIST)
    services_sec = obj.section(services_sym.section)
    services_raw = services_sec.raw_ptr + services_sym.value
    original_visible_ids = list(struct.unpack_from("<6I", obj.buf, services_raw))
    if original_visible_ids != [0x111, 0x112, 0x113, 0x115, 0x116, 0x114]:
        raise RuntimeError(f"Unexpected visible Special Upgrades base list: {[hex(x) for x in original_visible_ids]}")

    added_service_ids = [0x117, 0x118, 0x119, 0x11A]
    insert_off = services_sym.value + len(original_visible_ids) * 4
    existing_after = list(struct.unpack_from("<4I", obj.buf, services_sec.raw_ptr + insert_off))
    inserted = False
    if existing_after != added_service_ids:
        obj.insert_section_bytes(services_sym.section, insert_off, struct.pack("<4I", *added_service_ids))
        inserted = True

    iteminfo_sym = obj.symbol(INVENTORY_ITEMINFO)
    iteminfo_sec = obj.section(iteminfo_sym.section)
    iteminfo_raw = iteminfo_sec.raw_ptr + iteminfo_sym.value
    special_upgrade_records = {
        0x117: [0x117, visible_special_upgrade_icon_id_for(0x117), 1, 10000, 0, 0x2C, visible_special_upgrade_desc_id_for(0), 0, 0],
        0x118: [0x118, visible_special_upgrade_icon_id_for(0x118), 1, 10000, 0, 0x2D, visible_special_upgrade_desc_id_for(1), 0, 0],
        0x119: [0x119, visible_special_upgrade_icon_id_for(0x119), 1, 10000, 0, 0x2E, visible_special_upgrade_desc_id_for(2), 0, 0],
        0x11A: [0x11A, visible_special_upgrade_icon_id_for(0x11A), 1, 77777, 0, 0x2F, visible_special_upgrade_desc_id_for(3), 0, 0],
    }
    for item_id, vals in special_upgrade_records.items():
        struct.pack_into("<9I", obj.buf, iteminfo_raw + item_id * 36, *vals)

    count_sym = obj.symbol(GET_CATEGORY_ITEM_COUNT)
    count_sec = obj.section(count_sym.section)
    count_raw = count_sec.raw_ptr + count_sym.value + 0x19
    if obj.buf[count_raw : count_raw + 5] != b"\xB8\x06\x00\x00\x00":
        raise RuntimeError("Unexpected GetCategoryItemCount Special Upgrades return bytes")
    obj.buf[count_raw : count_raw + 5] = b"\xB8\x0A\x00\x00\x00"

    item_sym = obj.symbol(GET_CATEGORY_ITEM)
    item_sec = obj.section(item_sym.section)
    item_raw = item_sec.raw_ptr + item_sym.value + 0x1D
    if obj.buf[item_raw : item_raw + 3] != b"\x83\xFE\x05":
        raise RuntimeError("Unexpected GetCategoryItem Special Upgrades bounds bytes")
    obj.buf[item_raw : item_raw + 3] = b"\x83\xFE\x09"

    price_sym = obj.symbol("?GetPrice@CInventoryManager@@QAEHW4EInventoryItem@@@Z")
    price_insert = price_sym.value + 0x3
    price_sec = obj.section(price_sym.section)
    price_raw = price_sec.raw_ptr + price_insert
    if obj.buf[price_raw : price_raw + 3] != b"\x8B\x4D\x08":
        raise RuntimeError("Unexpected GetPrice prologue bytes")
    price_helper_sym = obj.append_undefined_symbol("_VF2GetVisibleSpecialUpgradePrice")
    price_payload = bytearray()
    price_payload += b"\xFF\x75\x08"              # push [ebp+8] ; item id
    price_payload += b"\xE8\x00\x00\x00\x00"      # call helper
    price_payload += b"\x83\xC4\x04"              # add esp,4
    price_payload += b"\x83\xF8\xFF"              # cmp eax,-1
    price_payload += b"\x74\x04"                  # je original GetPrice body
    price_payload += b"\x5D"                      # pop ebp
    price_payload += b"\xC2\x04\x00"              # ret 4
    if len(price_payload) != 0x14:
        raise RuntimeError("Unexpected visible Special Upgrades price payload length")
    obj.insert_section_bytes(price_sym.section, price_insert, bytes(price_payload))
    obj.append_relocation(price_sym.section, price_insert + 4, price_helper_sym, IMAGE_REL_I386_REL32)

    obj.write(PATCHED / "InventoryManager.obj")
    manifest["VisibleSpecialUpgrades"] = {
        "status": "visible Special Upgrades category extended additively",
        "source_list": "gServicesList",
        "old_count": 6,
        "new_count": 10,
        "inserted_list_entries": inserted,
        "base_items_preserved": [hex(x) for x in original_visible_ids],
        "added_items": [
            {"item_id": "0x117", "name": "Brokerage Account", "price": 10000, "icon": hex(visible_special_upgrade_icon_id_for(0x117)), "icon_file": VISIBLE_SPECIAL_UPGRADE_ICON_FILES[0x117], "title_string": "0x2c", "description_string": hex(visible_special_upgrade_desc_id_for(0))},
            {"item_id": "0x118", "name": "Food Club", "price": 10000, "icon": hex(visible_special_upgrade_icon_id_for(0x118)), "icon_file": VISIBLE_SPECIAL_UPGRADE_ICON_FILES[0x118], "title_string": "0x2d", "description_string": hex(visible_special_upgrade_desc_id_for(1))},
            {"item_id": "0x119", "name": "Health Plan", "price": 10000, "icon": hex(visible_special_upgrade_icon_id_for(0x119)), "icon_file": VISIBLE_SPECIAL_UPGRADE_ICON_FILES[0x119], "title_string": "0x2e", "description_string": hex(visible_special_upgrade_desc_id_for(2))},
            {"item_id": "0x11a", "name": "Lucky Rock", "price": 77777, "icon": hex(visible_special_upgrade_icon_id_for(0x11A)), "icon_file": VISIBLE_SPECIAL_UPGRADE_ICON_FILES[0x11A], "title_string": "0x2f", "description_string": hex(visible_special_upgrade_desc_id_for(3))},
        ],
        "active_reset_price": {
            "status": "GetPrice hook returns 0 coins when one of the added Special Upgrades is already active",
            "hook": "?GetPrice@CInventoryManager@@QAEHW4EInventoryItem@@@Z + 0x3",
            "helper": "_VF2GetVisibleSpecialUpgradePrice",
        },
        "icon_draw_route": {
            "status": "shared added-item DrawItem hook draws these standalone icon descriptors",
            "image_base": hex(visible_special_upgrade_icon_id_for(0x117)),
            "image_count": len(VISIBLE_SPECIAL_UPGRADE_ICON_FILES),
        },
    }


def write_outfit_store_helpers(manifest):
    helper_path = PATCHED / "vf2_special_upgrade_effects.cpp"
    if not helper_path.exists():
        raise RuntimeError("Expected vf2_special_upgrade_effects.cpp before adding outfit helpers")
    first_short, _first_long = outfit_string_ids_for_entry(0)
    helper_path.write_text(
        helper_path.read_text(encoding="ascii")
        + f"""

enum EImage {{ eImageDummy = 0 }};
class theGraphicsManager {{
public:
    static theGraphicsManager* Get();
    void Draw(EImage image, int x, int y, float scale, int alpha);
}};

enum EInventoryItem {{ eInventoryItemDummy = 0 }};
class CToolTray {{
public:
    bool AddItem(EInventoryItem item, int useCount);
}};

class CInventoryManager {{
public:
    char pad0[0x468];
    int maleOutfitBody;
    int femaleOutfitBody;
}};

extern CToolTray ToolTray;
extern CInventoryManager InventoryManager;

static const int kVF2OutfitStoreFemaleItemBase = {OUTFIT_STORE_GENDER_ITEM_BASES["female"]};
static const int kVF2OutfitStoreMaleItemBase = {OUTFIT_STORE_GENDER_ITEM_BASES["male"]};
static const int kVF2OutfitStoreBodyCount = {len(OUTFIT_STORE_BODY_VALUES)};
static const int kVF2OutfitStoreHolidayFirst = {HOLIDAY_BODY_VALUES[0]};
static const int kVF2MaleOutfitTrayItem = 0x49;
static const int kVF2FemaleOutfitTrayItem = 0x4A;
static const int kVF2OutfitStoreShortStringBase = {first_short};
static const int kVF2OutfitStoreIconImageBase = {outfit_icon_image_base(HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0)};
static const int kVF2OutfitStoreIconCellSize = {HOLIDAY_BODY_CELL_SIZE};
static const int kVF2VisibleSpecialUpgradeFirstItem = {min(VISIBLE_SPECIAL_UPGRADE_ICON_FILES)};
static const int kVF2VisibleSpecialUpgradeCount = {len(VISIBLE_SPECIAL_UPGRADE_ICON_FILES)};
static const int kVF2VisibleSpecialUpgradeIconImageBase = {visible_special_upgrade_icon_id_for(min(VISIBLE_SPECIAL_UPGRADE_ICON_FILES))};
static const int kVF2VisibleSpecialUpgradeIconCellSize = {VISIBLE_SPECIAL_UPGRADE_ICON_CELL_SIZE};
static int gVF2SyntheticOutfitToolInHand = 0;

static int VF2OutfitStoreEntryIndex(int itemId) {{
    int femaleBody = itemId - kVF2OutfitStoreFemaleItemBase;
    if (femaleBody >= 0 && femaleBody < kVF2OutfitStoreBodyCount) return femaleBody;
    int maleBody = itemId - kVF2OutfitStoreMaleItemBase;
    if (maleBody >= 0 && maleBody < kVF2OutfitStoreBodyCount) return kVF2OutfitStoreBodyCount + maleBody;
    return -1;
}}

static int VF2OutfitBodyForItem(int itemId) {{
    int index = VF2OutfitStoreEntryIndex(itemId);
    return index < 0 ? -1 : index % kVF2OutfitStoreBodyCount;
}}

static int VF2OutfitGenderForItem(int itemId) {{
    int index = VF2OutfitStoreEntryIndex(itemId);
    if (index < 0) {{
        return -1;
    }}
    return index >= kVF2OutfitStoreBodyCount ? 1 : 0;
}}

static int VF2OutfitStockTrayItemForItem(int itemId) {{
    int gender = VF2OutfitGenderForItem(itemId);
    if (gender < 0) {{
        return -1;
    }}
    return gender == 0 ? kVF2FemaleOutfitTrayItem : kVF2MaleOutfitTrayItem;
}}

extern "C" int __cdecl VF2GetOutfitStoreBodyValue(int itemId) {{
    int body = VF2OutfitBodyForItem(itemId);
    if (body >= 0) {{
        return body;
    }}

    int selected = gVF2SyntheticOutfitToolInHand;
    if (selected && VF2OutfitStockTrayItemForItem(selected) == itemId) {{
        return VF2OutfitBodyForItem(selected);
    }}
    return -1;
}}

extern "C" int __cdecl VF2GetOutfitStoreNumAvailable(int itemId) {{
    return VF2OutfitBodyForItem(itemId) < 0 ? -1 : 1;
}}

extern "C" bool __cdecl VF2PurchaseOutfitStoreItem(int itemId) {{
    int body = VF2OutfitBodyForItem(itemId);
    if (body < 0) {{
        return false;
    }}

    ToolTray.AddItem((EInventoryItem)itemId, 1);
    theGameState::Get()->SaveCurrentGame();
    return true;
}}

extern "C" int __cdecl VF2NormalizeOutfitToolInHand(void* tray, int activeFlagOffset) {{
    unsigned char* base = (unsigned char*)tray;
    if (!base || !base[activeFlagOffset]) {{
        gVF2SyntheticOutfitToolInHand = 0;
        return 0;
    }}

    int slot = *(int*)(base + 0xA0);
    if (slot < 0 || slot >= 9) {{
        gVF2SyntheticOutfitToolInHand = 0;
        return 0;
    }}

    int itemId = *(int*)(base + slot * 8);
    int stockItem = VF2OutfitStockTrayItemForItem(itemId);
    if (stockItem >= 0) {{
        gVF2SyntheticOutfitToolInHand = itemId;
        return stockItem;
    }}

    gVF2SyntheticOutfitToolInHand = 0;
    return itemId;
}}

extern "C" int __cdecl VF2GetOutfitStorePrice(int itemId) {{
    int body = VF2OutfitBodyForItem(itemId);
    if (body < 0) {{
        return -1;
    }}
    return body >= kVF2OutfitStoreHolidayFirst ? {OUTFIT_STORE_HOLIDAY_PRICE} : {OUTFIT_STORE_PRICE};
}}

extern "C" int __cdecl VF2GetOutfitStoreLockGeneration(int itemId) {{
    return VF2OutfitBodyForItem(itemId) < 0 ? -1 : 0;
}}

extern "C" int __cdecl VF2GetOutfitStoreShortDesc(int itemId) {{
    int index = VF2OutfitStoreEntryIndex(itemId);
    return index < 0 ? -1 : kVF2OutfitStoreShortStringBase + index * 2;
}}

extern "C" int __cdecl VF2GetOutfitStoreLongDesc(int itemId) {{
    int index = VF2OutfitStoreEntryIndex(itemId);
    return index < 0 ? -1 : kVF2OutfitStoreShortStringBase + index * 2 + 1;
}}

extern "C" int __cdecl VF2GetOutfitStoreIconImage(int itemId) {{
    int index = VF2OutfitStoreEntryIndex(itemId);
    return index < 0 ? -1 : kVF2OutfitStoreIconImageBase + index;
}}

static int VF2GetVisibleSpecialUpgradeIconImage(int itemId) {{
    int index = itemId - kVF2VisibleSpecialUpgradeFirstItem;
    return index < 0 || index >= kVF2VisibleSpecialUpgradeCount ? -1 : kVF2VisibleSpecialUpgradeIconImageBase + index;
}}

static int VF2GetAddedStoreIconImage(int itemId) {{
    int image = VF2GetOutfitStoreIconImage(itemId);
    if (image >= 0) return image;
    return VF2GetVisibleSpecialUpgradeIconImage(itemId);
}}

static int VF2GetAddedStoreIconCellSize(int itemId) {{
    return VF2GetVisibleSpecialUpgradeIconImage(itemId) >= 0
        ? kVF2VisibleSpecialUpgradeIconCellSize
        : kVF2OutfitStoreIconCellSize;
}}

extern "C" bool __cdecl VF2DrawOutfitStoreIconPoint(int x, int y, int itemId, int state, int position, int selected) {{
    int image = VF2GetAddedStoreIconImage(itemId);
    if (image < 0) return false;
    int cellSize = VF2GetAddedStoreIconCellSize(itemId);
    theGraphicsManager* graphics = theGraphicsManager::Get();
    if (graphics) graphics->Draw((EImage)image, x - cellSize / 2, y - cellSize / 2, 1.0f, 100);
    return true;
}}

extern "C" bool __cdecl VF2DrawOutfitStoreIconRect(
    int left,
    int top,
    int right,
    int bottom,
    int itemId,
    int state,
    int position,
    int selected
) {{
    int image = VF2GetAddedStoreIconImage(itemId);
    if (image < 0) return false;
    int cellSize = VF2GetAddedStoreIconCellSize(itemId);
    theGraphicsManager* graphics = theGraphicsManager::Get();
    if (graphics) {{
        int x = left + ((right - left) - cellSize) / 2;
        int y = top + ((bottom - top) - cellSize) / 2;
        graphics->Draw((EImage)image, x, y, 1.0f, 100);
    }}
    return true;
}}
""",
        encoding="ascii",
    )
    manifest["outfit_store_helpers"] = {
        "source": str(helper_path),
        "item_bases": {gender: hex(base) for gender, base in OUTFIT_STORE_GENDER_ITEM_BASES.items()},
        "body_values": list(OUTFIT_STORE_BODY_VALUES),
        "genders": list(OUTFIT_STORE_GENDERS),
        "holiday_body_values": list(HOLIDAY_BODY_VALUES),
        "short_string_base": hex(first_short),
        "icon_image_base": hex(outfit_icon_image_base(HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0)),
        "icon_count": OUTFIT_STORE_ENTRY_COUNT,
        "visible_special_upgrade_icon_base": hex(visible_special_upgrade_icon_id_for(min(VISIBLE_SPECIAL_UPGRADE_ICON_FILES))),
        "visible_special_upgrade_icon_count": len(VISIBLE_SPECIAL_UPGRADE_ICON_FILES),
        "draw_route": "shared DrawItem hook resolves outfit icons and added visible Special Upgrade icons",
        "purchase_route": {
            "male_stock_tray_item": "0x49",
            "female_stock_tray_item": "0x4a",
            "independent_tray_storage": "generated outfit item IDs are stored directly in ToolTray slots",
            "body_value_source": "decoded from synthetic item ID during outfit application",
            "helper": "_VF2PurchaseOutfitStoreItem",
        },
    }


def patch_tool_tray_outfit_normalization(manifest):
    obj = CoffObject(PATCHED / "ToolTray.obj")
    helper_sym = obj.append_undefined_symbol("_VF2NormalizeOutfitToolInHand")

    def patch_getter(function_name, active_flag_offset):
        sym = obj.symbol(function_name)
        sec = obj.section(sym.section)
        raw = sec.raw_ptr + sym.value
        expected = (
            b"\x80\xB9" + struct.pack("<I", active_flag_offset) + b"\x00"
            b"\x74\x0A"
            b"\x8B\x81\xA0\x00\x00\x00"
            b"\x8B\x04\xC1"
            b"\xC3"
            b"\x33\xC0"
            b"\xC3"
        )
        if obj.buf[raw : raw + len(expected)] != expected:
            raise RuntimeError(f"Unexpected {function_name} body bytes")
        payload = (
            b"\x68" + struct.pack("<I", active_flag_offset)  # push active flag offset
            + b"\x51"                                      # push this
            + b"\xE8\x00\x00\x00\x00"                      # call helper
            + b"\x83\xC4\x08"                              # add esp,8
            + b"\xC3"                                      # ret
        )
        payload += b"\x90" * (len(expected) - len(payload))
        obj.buf[raw : raw + len(expected)] = payload
        obj.append_relocation(sym.section, sym.value + 7, helper_sym, IMAGE_REL_I386_REL32)
        return {
            "function": function_name,
            "active_flag_offset": hex(active_flag_offset),
            "helper": "_VF2NormalizeOutfitToolInHand",
            "overwritten_bytes": len(expected),
        }

    patches = [
        patch_getter("?GetToolInHand@CToolTray@@QAE?AW4EInventoryItem@@XZ", 0xA4),
        patch_getter("?GetToolInUse@CToolTray@@QAE?AW4EInventoryItem@@XZ", 0xA5),
    ]
    obj.write(PATCHED / "ToolTray.obj")
    manifest["outfit_tooltray_normalization"] = {
        "status": "synthetic outfit tray IDs normalize to stock IDs only for vanilla application checks",
        "synthetic_ranges": {gender: hex(base) for gender, base in OUTFIT_STORE_GENDER_ITEM_BASES.items()},
        "stock_mapping": {
            "male": "0x49",
            "female": "0x4a",
        },
        "patches": patches,
        "note": "ToolTray storage, save data, and icon drawing keep the independent synthetic item ID.",
    }


def patch_scrolling_store_scene(manifest):
    obj = CoffObject(PATCHED / "ScrollingStoreScene.obj")
    new_furniture_end = max(item_id_for(i) for i in range(len(ITEMS))) + 1
    patches = 0
    for reg in [b"\x3D", b"\x81\xFB", b"\x81\xFE", b"\x81\xF9", b"\x81\xFA"]:
        patches += patch_all_in_sections(
            obj,
            {".text$mn"},
            reg + struct.pack("<I", 0x2A9),
            reg + struct.pack("<I", new_furniture_end),
        )
    draw_sym = obj.symbol("?DrawVisibleStoreItem@CScrollingStoreScene@@AAEXHHH@Z")
    lock_helper_sym = obj.append_undefined_symbol("_VF2DrawGenerationLock")
    obj.retarget_relocation(draw_sym.section, draw_sym.value + 0x354, lock_helper_sym, IMAGE_REL_I386_REL32)

    scene_draw_sym = obj.symbol("?DrawScene@CScrollingStoreScene@@MAEXXZ")
    scrollbar_draw_helper = obj.append_undefined_symbol("_VF2DrawStoreScrollbar")
    draw_insert = scene_draw_sym.value + 0x154
    draw_payload = bytearray([
        0x57,                         # push edi ; this
        0xE8, 0, 0, 0, 0,             # call _VF2DrawStoreScrollbar
        0x83, 0xC4, 0x04,             # add esp, 4
    ])
    obj.insert_section_bytes(scene_draw_sym.section, draw_insert, draw_payload)
    obj.append_relocation(scene_draw_sym.section, draw_insert + 2, scrollbar_draw_helper, IMAGE_REL_I386_REL32)

    mouse_sym = obj.symbol("?HandleMouse@CScrollingStoreScene@@UAE_NHUldwPoint@@@Z")
    scrollbar_mouse_helper = obj.append_undefined_symbol("_VF2HandleStoreScrollbarMouse")
    mouse_insert = mouse_sym.value + 0x30
    mouse_payload = bytearray([
        0xFF, 0x75, 0x10,             # push [ebp+10h] ; y
        0xFF, 0x75, 0x0C,             # push [ebp+0Ch] ; x
        0xFF, 0x75, 0x08,             # push [ebp+8]   ; message
        0x57,                         # push edi       ; this
        0xE8, 0, 0, 0, 0,             # call helper
        0x83, 0xC4, 0x10,             # add esp, 10h
    ])
    obj.insert_section_bytes(mouse_sym.section, mouse_insert, mouse_payload)
    obj.append_relocation(mouse_sym.section, mouse_insert + 11, scrollbar_mouse_helper, IMAGE_REL_I386_REL32)

    purchase_sym = obj.symbol("?HandlePurchaseItem@CScrollingStoreScene@@AAEXXZ")
    purchase_insert = purchase_sym.value + 0x1AD
    purchase_sec = obj.section(purchase_sym.section)
    purchase_raw = purchase_sec.raw_ptr + purchase_insert
    expected_purchase_bytes = b"\x8B\x8E\x60\x01\x00\x00\x8B\xC1\x83\xF9\x04"
    if obj.buf[purchase_raw:purchase_raw + len(expected_purchase_bytes)] != expected_purchase_bytes:
        raise RuntimeError("Unexpected HandlePurchaseItem visible-special dispatch bytes")

    outfit_purchase_helper_sym = obj.append_undefined_symbol("_VF2PurchaseOutfitStoreItem")
    special_upgrade_helper_sym = obj.append_undefined_symbol("_VF2ApplyVisibleSpecialUpgrade")
    purchase_payload = bytearray()
    purchase_payload += b"\x8B\x86\x60\x01\x00\x00"                  # mov eax,[esi+160h]
    purchase_payload += b"\x50"                                      # push eax ; original item id
    purchase_payload += b"\xE8\x00\x00\x00\x00"                      # call _VF2PurchaseOutfitStoreItem
    purchase_payload += b"\x83\xC4\x04"                              # add esp,4
    purchase_payload += b"\x84\xC0"                                  # test al,al
    purchase_payload += b"\x74\x05"                                  # jz visible special purchase test
    outfit_return_jmp_off = len(purchase_payload)
    purchase_payload += b"\xE9\x00\x00\x00\x00"                      # jmp post-save cleanup; helper saved
    if len(purchase_payload) != 0x18:
        raise RuntimeError("Unexpected outfit purchase payload length")

    special_payload_start = len(purchase_payload)
    purchase_payload += b"\x8B\x86\x60\x01\x00\x00"                  # mov eax,[esi+160h]
    purchase_payload += b"\x8B\xC8"                                  # mov ecx,eax
    purchase_payload += b"\x2D\x17\x01\x00\x00"                      # sub eax,117h
    purchase_payload += b"\x83\xF8\x03"                              # cmp eax,3
    purchase_payload += b"\x77\x0E"                                  # ja normal visible purchase
    purchase_payload += b"\x51"                                      # push ecx ; original item id
    purchase_payload += b"\xE8\x00\x00\x00\x00"                      # call _VF2ApplyVisibleSpecialUpgrade
    purchase_payload += b"\x83\xC4\x04"                              # add esp,4
    special_return_jmp_off = len(purchase_payload)
    purchase_payload += b"\xE9\x00\x00\x00\x00"                      # jmp post-save cleanup; helper saved
    if len(purchase_payload) - special_payload_start != 0x20:
        raise RuntimeError("Unexpected visible Special Upgrades purchase payload length")
    return_after_purchase = purchase_sym.value + 0x31C + len(purchase_payload)
    for jmp_off in (outfit_return_jmp_off, special_return_jmp_off):
        rel_to_return = (return_after_purchase - (purchase_insert + jmp_off + 5)) & 0xFFFFFFFF
        purchase_payload[jmp_off + 1 : jmp_off + 5] = struct.pack("<I", rel_to_return)

    obj.insert_section_bytes(purchase_sym.section, purchase_insert, bytes(purchase_payload))
    obj.append_relocation(purchase_sym.section, purchase_insert + 8, outfit_purchase_helper_sym, IMAGE_REL_I386_REL32)
    obj.append_relocation(purchase_sym.section, purchase_insert + special_payload_start + 20, special_upgrade_helper_sym, IMAGE_REL_I386_REL32)

    obj.write(PATCHED / "ScrollingStoreScene.obj")
    lock_base = lock_image_id_for(0)
    (PATCHED / "vf2_generation_locks.cpp").write_text(
        f"""
enum EImage {{ eImageDummy = 0 }};

class theGraphicsManager {{
public:
    void Draw(EImage image, int x, int y, float scale, int alpha);
}};

extern "C" void __cdecl VF2DrawGenerationLockImpl(theGraphicsManager* graphics, int frame, int x, int y, float scale, int alpha) {{
    if (frame < 0) {{
        frame = 0;
    }} else if (frame >= {LOCKED_GENERATION_FRAME_COUNT}) {{
        frame = {LOCKED_GENERATION_FRAME_COUNT - 1};
    }}
    graphics->Draw((EImage)({lock_base} + frame), x, y, scale, alpha);
}}

extern "C" void __cdecl VF2DrawVisibleSpecialUpgradeIcon(theGraphicsManager* graphics, int item, int x, int y) {{
    if (!graphics) {{
        return;
    }}

    int frame = item - 0x117;
    if (frame < 0 || frame >= {len(VISIBLE_SPECIAL_UPGRADE_ICON_FILES)}) {{
        return;
    }}

    graphics->Draw((EImage)({visible_special_upgrade_icon_id_for(0x117)} + frame), x, y, 1.0f, 100);
}}

extern "C" __declspec(naked) void VF2DrawGenerationLock() {{
    __asm {{
        push ebp
        mov ebp, esp
        push dword ptr [ebp+1Ch]
        push dword ptr [ebp+18h]
        push dword ptr [ebp+14h]
        push dword ptr [ebp+10h]
        push dword ptr [ebp+0Ch]
        push ecx
        call VF2DrawGenerationLockImpl
        add esp, 18h
        pop ebp
        ret 18h
    }}
}}
""".lstrip(),
        encoding="ascii",
    )
    (PATCHED / "vf2_store_scrollbar.cpp").write_text(
        r"""
struct ldwRect {
    int left;
    int top;
    int right;
    int bottom;
};

struct ldwColor {
    unsigned int value;
};

class ldwGameWindow {
public:
    static ldwGameWindow *Get();
    void FillRect(ldwRect &rect, ldwColor color);
};

static int &field_i(void *scene, int offset) {
    return *(int *)((char *)scene + offset);
}

static unsigned char &field_b(void *scene, int offset) {
    return *(unsigned char *)((char *)scene + offset);
}

static int clamp_int(int value, int lo, int hi) {
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}

static void sync_thumb_from_scroll(void *scene) {
    int maxScroll = field_i(scene, 0x154);
    if (maxScroll <= 0) {
        return;
    }
    int railTop = field_i(scene, 0x0F8);
    int railBottom = field_i(scene, 0x100);
    int thumbHeight = field_i(scene, 0x110);
    int travel = (railBottom - railTop) - thumbHeight;
    if (travel <= 0) {
        return;
    }
    int scroll = clamp_int(field_i(scene, 0x148), 0, maxScroll);
    field_i(scene, 0x148) = scroll;
    field_i(scene, 0x108) = railTop + (travel * scroll) / maxScroll;
}

extern "C" void __cdecl VF2DrawStoreScrollbar(void *scene) {
    int maxScroll = field_i(scene, 0x154);
    if (maxScroll <= 0) {
        return;
    }

    sync_thumb_from_scroll(scene);

    int left = field_i(scene, 0x0EC) + 8;
    int right = left + 12;
    int railTop = field_i(scene, 0x0E8) + 8;
    int railBottom = field_i(scene, 0x0F0) - 42;
    int thumbTop = clamp_int(field_i(scene, 0x108), railTop, railBottom - 22);
    int thumbBottom = thumbTop + field_i(scene, 0x110);
    if (thumbBottom > railBottom) {
        thumbBottom = railBottom;
    }

    ldwGameWindow *window = ldwGameWindow::Get();
    ldwRect rail = { left, railTop, right, railBottom };
    ldwRect groove = { left + 3, railTop + 3, right - 3, railBottom - 3 };
    ldwRect thumb = { left + 1, thumbTop, right - 1, thumbBottom };
    ldwRect thumbHi = { left + 3, thumbTop + 3, right - 3, thumbTop + 8 };

    ldwColor railColor = { 0xCC24466F };
    ldwColor grooveColor = { 0xCC7FB3DC };
    ldwColor thumbColor = { 0xEEB7E1FF };
    ldwColor thumbHiColor = { 0xFFFFFFFF };

    window->FillRect(rail, railColor);
    window->FillRect(groove, grooveColor);
    window->FillRect(thumb, thumbColor);
    window->FillRect(thumbHi, thumbHiColor);
}

extern "C" void __cdecl VF2HandleStoreScrollbarMouse(void *scene, int message, int x, int y) {
    int maxScroll = field_i(scene, 0x154);
    if (maxScroll <= 0) {
        return;
    }

    int left = field_i(scene, 0x0EC) + 4;
    int right = left + 20;
    int railTop = field_i(scene, 0x0E8) + 8;
    int railBottom = field_i(scene, 0x0F0) - 42;
    if (x < left || x > right || y < railTop || y > railBottom) {
        return;
    }

    if (message != 2) {
        return;
    }

    int thumbHeight = field_i(scene, 0x110);
    int travel = (railBottom - railTop) - thumbHeight;
    if (travel <= 0) {
        return;
    }

    int newThumbTop = clamp_int(y - thumbHeight / 2, railTop, railTop + travel);
    int scroll = ((newThumbTop - railTop) * maxScroll) / travel;
    field_i(scene, 0x148) = clamp_int(scroll, 0, maxScroll);
    field_i(scene, 0x108) = newThumbTop;
    field_i(scene, 0x118) = y;
    field_b(scene, 0x114) = 1;
    field_b(scene, 0x121) = 0;
    field_b(scene, 0x140) = 0;
}
""".lstrip(),
        encoding="ascii",
    )
    (PATCHED / "vf2_special_upgrade_effects.cpp").write_text(
        r"""
class CFoodStore {
public:
    char pad0[0x7C];
    unsigned char haveFoodClub;
    char pad1[3];
    unsigned int lastFoodClubDelivery;
    unsigned char organicDelivery[4];

    void JoinFoodClub();
};

class CMoney {
public:
    char pad0[8];
    float bankingInterest;
};

enum ECarrying {
    eCarryingDummy = 0
};

class CCollectableItem {
public:
    int const CollectionCount(ECarrying item, bool common, bool uncommon, bool rare) const;

    char pad0[0x8A8];
    unsigned char luckyRockActive;
};

class theGameState {
public:
    static theGameState *Get();
    bool SaveCurrentGame();

    char pad0[0x25B1D];
    unsigned char healthPlanActive;
};

extern CFoodStore FoodStore;
extern CMoney Money;
extern CCollectableItem CollectableItem;

extern "C" int __cdecl VF2CollectionPageCount(int page) {
    static const int starts[6] = {0x4F, 0x5B, 0x67, 0x86, 0x92, 0x9E};
    if (page < 0 || page >= 6) {
        return 0;
    }
    return CollectableItem.CollectionCount((ECarrying)starts[page], true, true, true);
}

extern "C" int __cdecl VF2GetVisibleSpecialUpgradePrice(int itemId) {
    switch (itemId) {
    case 0x117:
        return Money.bankingInterest > 0.1001f ? 0 : -1;
    case 0x118:
        return FoodStore.haveFoodClub ? 0 : -1;
    case 0x119:
        return theGameState::Get()->healthPlanActive ? 0 : -1;
    case 0x11A:
        return CollectableItem.luckyRockActive ? 0 : -1;
    default:
        return -1;
    }
}

extern "C" void __cdecl VF2ApplyVisibleSpecialUpgrade(int itemId) {
    switch (itemId) {
    case 0x117: {
        if (Money.bankingInterest > 0.1001f) {
            Money.bankingInterest = 0.01f;
            break;
        }
        float next = Money.bankingInterest + 0.02f;
        if (next > 0.11f) {
            next = 0.11f;
        }
        Money.bankingInterest = next;
        break;
    }
    case 0x118:
        if (FoodStore.haveFoodClub) {
            FoodStore.haveFoodClub = 0;
            FoodStore.lastFoodClubDelivery = 0;
            FoodStore.organicDelivery[0] = 0;
            FoodStore.organicDelivery[1] = 0;
            FoodStore.organicDelivery[2] = 0;
            FoodStore.organicDelivery[3] = 0;
            break;
        }
        FoodStore.JoinFoodClub();
        break;
    case 0x119:
        if (theGameState::Get()->healthPlanActive) {
            theGameState::Get()->healthPlanActive = 0;
            break;
        }
        theGameState::Get()->healthPlanActive = 1;
        break;
    case 0x11A:
        if (CollectableItem.luckyRockActive) {
            CollectableItem.luckyRockActive = 0;
            break;
        }
        CollectableItem.luckyRockActive = 1;
        break;
    default:
        return;
    }

    theGameState::Get()->SaveCurrentGame();
}
""".lstrip(),
        encoding="ascii",
    )
    manifest["ScrollingStoreScene"] = {
        "new_furniture_one_past_end": hex(new_furniture_end),
        "furniture_end_patches": patches,
        "generation_lock_draw": {
            "status": "DrawCell retargeted to standalone generation lock helper",
            "patched_function": "?DrawVisibleStoreItem@CScrollingStoreScene@@AAEXHHH@Z",
            "call_offset": "0x354",
            "helper": "_VF2DrawGenerationLock",
            "image_base": hex(lock_base),
            "image_count": LOCKED_GENERATION_FRAME_COUNT,
        },
        "store_scrollbar": {
            "draw_hook": "?DrawScene@CScrollingStoreScene@@MAEXXZ + 0x154",
            "mouse_hook": "?HandleMouse@CScrollingStoreScene@@UAE_NHUldwPoint@@@Z + 0x30",
            "helper": "_VF2DrawStoreScrollbar / _VF2HandleStoreScrollbarMouse",
            "fields": {
                "scroll_offset": "this+0x148",
                "max_scroll": "this+0x154",
                "rail_top": "this+0x0F8",
                "rail_bottom": "this+0x100",
                "thumb_top": "this+0x108",
                "thumb_height": "this+0x110",
                "thumb_dragging": "this+0x114",
            },
        },
        "outfit_store_purchase": {
            "status": "generated Clothing rows add their synthetic item ID to ToolTray after normal coin charge",
            "purchase_hook": "?HandlePurchaseItem@CScrollingStoreScene@@AAEXXZ + 0x1AD",
            "helper": "_VF2PurchaseOutfitStoreItem",
            "item_bases": {gender: hex(base) for gender, base in OUTFIT_STORE_GENDER_ITEM_BASES.items()},
            "synthetic_tray_items": {
                "female": f"{hex(OUTFIT_STORE_GENDER_ITEM_BASES['female'])}-{hex(OUTFIT_STORE_GENDER_ITEM_BASES['female'] + len(OUTFIT_STORE_BODY_VALUES) - 1)}",
                "male": f"{hex(OUTFIT_STORE_GENDER_ITEM_BASES['male'])}-{hex(OUTFIT_STORE_GENDER_ITEM_BASES['male'] + len(OUTFIT_STORE_BODY_VALUES) - 1)}",
            },
            "stock_normalized_tray_items": {
                "female": "0x4a",
                "male": "0x49",
            },
        },
        "visible_special_upgrades": {
            "status": "visible purchases call a direct effect helper after normal coin charge; hidden IAP UI/dialog path bypassed",
            "visible_item_ids": ["0x117", "0x118", "0x119", "0x11a"],
            "native_iap_rows": [7, 8, 9, 10],
            "purchase_hook": "?HandlePurchaseItem@CScrollingStoreScene@@AAEXXZ + 0x1AD",
            "effects": {
                "0x117": "Brokerage Account helper increments banking interest; active reset sets interest to 1%",
                "0x118": "Food Club helper calls JoinFoodClub",
                "0x119": "Health Plan helper sets the health-plan discount flag",
                "0x11a": "Lucky Rock helper sets the collectible boost flag",
            },
            "dialog": "disabled for stability; the native hidden-IAP message box path produced blank/crashing dialogs when called from visible Store rows",
            "icons": {
                "status": "drawn by the shared CInventoryManager::DrawItem added-item hook",
                "image_base": hex(visible_special_upgrade_icon_id_for(0x117)),
                "image_count": len(VISIBLE_SPECIAL_UPGRADE_ICON_FILES),
            },
        },
    }


def patch_purchase_dialog(manifest):
    obj = CoffObject(PATCHED / "thePurchaseDialog.obj")
    new_furniture_end = max(item_id_for(i) for i in range(len(ITEMS))) + 1
    patches = 0
    for reg in [b"\x3D", b"\x81\xFF", b"\x81\xFE", b"\x81\xFB", b"\x81\xF9", b"\x81\xFA"]:
        patches += patch_all_in_sections(
            obj,
            {".text$mn"},
            reg + struct.pack("<I", 0x2A9),
            reg + struct.pack("<I", new_furniture_end),
        )
    obj.write(PATCHED / "thePurchaseDialog.obj")
    manifest["thePurchaseDialog"] = {
        "new_furniture_one_past_end": hex(new_furniture_end),
        "furniture_preview_bound_patches": patches,
    }


def c_symbol_for_string(kind, idx, role):
    return f"_vf2mobstr_{kind}_{idx}_{role}"


def patch_string_manager(manifest):
    obj = CoffObject(PATCHED / "theStringManager.obj")
    table_sym = obj.symbol(STRINGTABLE)
    insert_off = table_sym.value + ORIG_STRING_COUNT * STRING_RECORD_SIZE
    new_rows = []
    helper_lines = []
    string_manifest = []

    for idx, (_name, _donor_id, _list_name, path) in enumerate(ITEMS):
        data = MOBILE_DATA_BY_PATH[path]
        short_id, long_id = item_string_ids(idx)
        for string_id, key, text, role in [
            (short_id, data["short_symbol"], data["short_description"], "short"),
            (long_id, data["long_symbol"], data["long_description"], "long"),
        ]:
            key_sym = c_symbol_for_string("key", idx, role)
            text_sym = c_symbol_for_string("text", idx, role)
            helper_lines.append(f'const char {key_sym[1:]}[] = "{c_string(key)}";')
            helper_lines.append(f'const char {text_sym[1:]}[] = "{c_string(text)}";')
            new_rows.append((string_id, key_sym, text_sym))
            string_manifest.append({
                "pc_string_id": hex(string_id),
                "mobile_string_id": hex(data["mobile_short_id"] if role == "short" else data["mobile_long_id"]),
                "mobile_item_id": hex(data["mobile_item_id"]) if "mobile_item_id" in data else hex(data["item_id"]),
                "key": key,
                "text": text,
            })

    if ENABLE_ISLAND_EVENTS:
        for event in load_mobile_island_events():
            for string_row in event["strings"]:
                string_id = string_row["string_id"]
                key_sym = f"_vf2eventstr_key_{string_id:X}"
                text_sym = f"_vf2eventstr_text_{string_id:X}"
                helper_lines.append(f'const char {key_sym[1:]}[] = "{c_string(string_row["key"])}";')
                helper_lines.append(f'const char {text_sym[1:]}[] = "{c_string(string_row["text"])}";')
                new_rows.append((string_id, key_sym, text_sym))
                string_manifest.append({
                    "pc_string_id": hex(string_id),
                    "source": "mobile island event",
                    "event": event["class"],
                    "slot": hex(event["slot"]),
                    "kind": string_row["kind"],
                    "key": string_row["key"],
                    "text": string_row["text"],
                })

    removable_note = " (This upgrade can be removed by purchasing it again)"
    special_upgrade_descriptions = [
        (
            visible_special_upgrade_desc_id_for(0),
            "eString_BrokerageAccountDescRemovable",
            "Upgrade your broker. Provides a permanent 2% boost to your family's banking interest rate." + removable_note,
        ),
        (
            visible_special_upgrade_desc_id_for(1),
            "eString_FoodClubDescRemovable",
            "Bags of organic, local groceries containing all 4 food groups, delivered each day (helps prevent accidental starvation). Plus a permanent 50% discount on all food!" + removable_note,
        ),
        (
            visible_special_upgrade_desc_id_for(2),
            "eString_HealthPlanDescRemovable",
            "Provides a permanent 75% discount on all health care and medicines." + removable_note,
        ),
        (
            visible_special_upgrade_desc_id_for(3),
            "eString_LuckyRockDescRemovable",
            "This lucky rock increases the rate and rarity of random collectibles that appear in the yard." + removable_note,
        ),
    ]
    for string_id, key, text in special_upgrade_descriptions:
        key_sym = f"_vf2specialstr_key_{string_id:X}"
        text_sym = f"_vf2specialstr_text_{string_id:X}"
        helper_lines.append(f'const char {key_sym[1:]}[] = "{c_string(key)}";')
        helper_lines.append(f'const char {text_sym[1:]}[] = "{c_string(text)}";')
        new_rows.append((string_id, key_sym, text_sym))
        string_manifest.append({
            "pc_string_id": hex(string_id),
            "source": "visible special upgrade",
            "key": key,
            "text": text,
        })

    for entry in outfit_store_entries():
        short_id, long_id = outfit_string_ids_for_entry(entry["entry_index"])
        gender_title = entry["gender"].title()
        rows = [
            (
                short_id,
                f"eString_{gender_title}OutfitBody{entry['body_value']:02d}ShortDesc",
                entry["name"],
                "short",
            ),
            (
                long_id,
                f"eString_{gender_title}OutfitBody{entry['body_value']:02d}LongDesc",
                f"Adds {entry['gender']} villager body value {entry['body_value']} to the Outfits store.",
                "long",
            ),
        ]
        for string_id, key, text, role in rows:
            key_sym = f"_vf2outfitstr_key_{string_id:X}"
            text_sym = f"_vf2outfitstr_text_{string_id:X}"
            helper_lines.append(f'const char {key_sym[1:]}[] = "{c_string(key)}";')
            helper_lines.append(f'const char {text_sym[1:]}[] = "{c_string(text)}";')
            new_rows.append((string_id, key_sym, text_sym))
            string_manifest.append({
                "pc_string_id": hex(string_id),
                "source": "outfit store entry",
                "item_id": hex(entry["item_id"]),
                "gender": entry["gender"],
                "body_value": entry["body_value"],
                "role": role,
                "key": key,
                "text": text,
            })

    for index, (key, text) in enumerate(BEHAVIOR_LABELS):
        string_id = behavior_label_string_id_for(index)
        key_sym = f"_vf2behaviorstr_key_{string_id:X}"
        text_sym = f"_vf2behaviorstr_text_{string_id:X}"
        helper_lines.append(f'const char {key_sym[1:]}[] = "{c_string(key)}";')
        helper_lines.append(f'const char {text_sym[1:]}[] = "{c_string(text)}";')
        new_rows.append((string_id, key_sym, text_sym))
        string_manifest.append({
            "pc_string_id": hex(string_id),
            "source": "behavior label",
            "key": key,
            "text": text,
        })

    ornament_title_id = holiday_ornament_collection_title_string_id()
    ornament_key = "eString_CollectionHolidayOrnaments"
    ornament_text = "Holiday Ornaments"
    ornament_key_sym = f"_vf2ornamentstr_key_{ornament_title_id:X}"
    ornament_text_sym = f"_vf2ornamentstr_text_{ornament_title_id:X}"
    helper_lines.append(f'const char {ornament_key_sym[1:]}[] = "{c_string(ornament_key)}";')
    helper_lines.append(f'const char {ornament_text_sym[1:]}[] = "{c_string(ornament_text)}";')
    new_rows.append((ornament_title_id, ornament_key_sym, ornament_text_sym))
    string_manifest.append({
        "pc_string_id": hex(ornament_title_id),
        "source": "holiday ornament collection page",
        "key": ornament_key,
        "text": ornament_text,
    })

    ornament_goal_strings = [
        (
            holiday_ornament_achievement_title_string_id(),
            "eString_AchievementOrnamentsTitle",
            "Ornamentologist",
        ),
        (
            holiday_ornament_achievement_desc_string_id(),
            "eString_AchievementOrnamentsDesc",
            "You completed the collection of holiday ornaments.",
        ),
    ]
    for string_id, key, text in ornament_goal_strings:
        key_sym = f"_vf2ornamentachievement_key_{string_id:X}"
        text_sym = f"_vf2ornamentachievement_text_{string_id:X}"
        helper_lines.append(f'const char {key_sym[1:]}[] = "{c_string(key)}";')
        helper_lines.append(f'const char {text_sym[1:]}[] = "{c_string(text)}";')
        new_rows.append((string_id, key_sym, text_sym))
        string_manifest.append({
            "pc_string_id": hex(string_id),
            "source": "mobile holiday ornament achievement",
            "key": key,
            "text": text,
        })

    # Retain the existing string id used by the pet behavior while replacing
    # its text through the normal string-table lookup.
    pet_candidates = (
        b"{name} sees pet",
        b"{name} sees their adorable pet",
        b"{name} sees their adorable pet.",
    )
    pet_new = "{name} sees their adorable pet."
    pet_symbol = None
    for symbol in obj.symbols:
        if symbol.section <= 0:
            continue
        section_data = bytes(obj.section_data(symbol.section))
        if (
            symbol.name.startswith("??_C@")
            and any(
                section_data[symbol.value : symbol.value + len(candidate)] == candidate
                for candidate in pet_candidates
            )
        ):
            pet_symbol = symbol
            break
    if pet_symbol is None:
        raise RuntimeError("Could not locate the existing pet-behavior string")
    pet_key_sym = "_vf2petstr_key"
    pet_text_sym = "_vf2petstr_text"
    helper_lines.append(f'const char {pet_key_sym[1:]}[] = "eString_SeesTheirAdorablePet";')
    helper_lines.append(f'const char {pet_text_sym[1:]}[] = "{c_string(pet_new)}";')

    payload = b"".join(struct.pack("<IIII", string_id, 0, 0, 0) for string_id, _key, _text in new_rows)
    obj.insert_section_bytes(table_sym.section, insert_off, payload)
    for row_idx, (_string_id, key_sym, text_sym) in enumerate(new_rows):
        row_off = insert_off + row_idx * STRING_RECORD_SIZE
        key_symidx = obj.append_undefined_symbol(key_sym)
        text_symidx = obj.append_undefined_symbol(text_sym)
        obj.append_relocation(table_sym.section, row_off + 4, key_symidx)
        obj.append_relocation(table_sym.section, row_off + 8, text_symidx)

    pet_text_symidx = obj.append_undefined_symbol(pet_text_sym)
    pet_retargeted = []
    table_section = obj.section(table_sym.section)
    p = table_section.reloc_ptr
    for _ in range(table_section.nreloc):
        vaddr, symidx, _rtype = struct.unpack_from("<IIH", obj.buf, p)
        if (
            symidx == pet_symbol.index
            and table_sym.value <= vaddr < insert_off
            and (vaddr - table_sym.value) % STRING_RECORD_SIZE == 8
        ):
            obj.retarget_relocation(table_sym.section, vaddr, pet_text_symidx)
            pet_retargeted.append(hex(vaddr))
            break
        p += 10
    if not pet_retargeted:
        raise RuntimeError("Could not retarget the pet behavior string-table entry")

    new_count = ORIG_STRING_COUNT + len(new_rows)
    new_one_past = ORIG_STRING_ONE_PAST_MAX + len(new_rows)
    new_get_max_minus_one = new_one_past - 2
    new_lookup_bytes = new_one_past * 4
    count_patches = patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", ORIG_STRING_COUNT), struct.pack("<I", new_count))
    max_patches = patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", ORIG_STRING_ONE_PAST_MAX), struct.pack("<I", new_one_past))
    get_guard_patches = patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", ORIG_STRING_GET_MAX_MINUS_ONE), struct.pack("<I", new_get_max_minus_one))
    lookup_patches = patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", ORIG_STRING_LOOKUP_BYTES), struct.pack("<I", new_lookup_bytes))

    lookup_sym = obj.symbol(STRINGLOOKUP)
    obj.grow_bss_section(lookup_sym.section, lookup_sym.value + ORIG_STRING_LOOKUP_BYTES, new_lookup_bytes - ORIG_STRING_LOOKUP_BYTES)
    obj.write(PATCHED / "theStringManager.obj")
    (PATCHED / "vf2_mobile_string_table.c").write_text("\n".join(helper_lines) + "\n", encoding="ascii")
    manifest["theStringManager"] = {
        "added_strings": len(new_rows),
        "new_string_count": hex(new_count),
        "new_one_past_max": hex(new_one_past),
        "strings": string_manifest,
        "patches": {
            "string_count": count_patches,
            "one_past_max": max_patches,
            "get_guard": get_guard_patches,
            "lookup_bytes": lookup_patches,
        },
        "updated_existing_strings": [{
            "old": "{name} sees pet",
            "new": pet_new,
            "table_relocations": pet_retargeted,
        }],
    }


def patch_special_upgrade_titles(manifest):
    obj_path = PATCHED / "theStringManager.obj"
    data = bytearray(obj_path.read_bytes())
    replacements = {
        b"Brokerage Account $0.99": b"Brokerage Account",
        b"Food Club $0.99": b"Food Club",
        b"Health Plan $0.99": b"Health Plan",
        b"Lucky Rock $0.99": b"Lucky Rock",
    }
    patched = []
    for old, new in replacements.items():
        idx = data.find(old)
        if idx < 0:
            padded = new + b"\0" * (len(old) - len(new))
            if data.find(padded) >= 0:
                patched.append(new.decode("ascii"))
                continue
            raise RuntimeError(f"Could not find special upgrade title {old!r}")
        if len(new) > len(old):
            raise RuntimeError(f"Replacement too long for {old!r}")
        data[idx : idx + len(old)] = new + b"\0" * (len(old) - len(new))
        patched.append(new.decode("ascii"))
    obj_path.write_bytes(data)
    manifest["SpecialUpgrades"] = {
        "mode": "native append-only rows",
        "rows": "desktop SetStoreCategory already exposes 11 Special Upgrades rows",
        "native_effects_preserved": [
            "Roll the Dice",
            "Time Warp",
            "Adoption Service",
            "On Call Maid Service",
            "On Call Gardening Service",
            "Lotto Ticket",
            "Redeem Code/credit row",
            "Brokerage Account",
            "Food Club",
            "Health Plan",
            "Lucky Rock",
        ],
        "title_patches": patched,
        "disabled_risky_hooks": [
            "old dialog-result reroute",
            "old precharge hook inside HandlePurchaseItem",
        ],
    }


def patch_island_events(manifest):
    mobile_events = load_mobile_island_events()
    if not mobile_events:
        manifest["IslandEvents"] = {"added": [], "status": "no mobile event rows found"}
        return

    obj = CoffObject(PATCHED / "IslandEvents.obj")
    ctor_sym = obj.symbol("??0CIslandEvents@@AAE@XZ")
    event_list_sym = obj.symbol("?mEventList@CIslandEvents@@0PAPAVCIslandEvent@@A")
    event_has_fired_sym = obj.symbol("?mEventHasFired@CIslandEvents@@0PA_NA")
    sec = obj.section(ctor_sym.section)
    start = sec.raw_ptr + ctor_sym.value
    if obj.buf[start + 0x15B8:start + 0x15BE] != b"\x8B\xC6\x5E\x8B\xE5\x5D":
        raise ValueError("Unexpected CIslandEvents constructor epilogue")

    new_bound = 0x61 + len(mobile_events)
    if new_bound > 0xFF:
        raise ValueError("Too many mobile island events for current one-byte bound patch")

    first_added_slot = 0x61
    first_slot_offset = first_added_slot * 4
    new_table_end_offset = new_bound * 4
    old_has_fired_offset = event_has_fired_sym.value - event_list_sym.value
    event_table_growth = new_table_end_offset - old_has_fired_offset
    if event_table_growth < 0:
        raise ValueError("Unexpected CIslandEvents event-table layout")
    if event_table_growth:
        obj.grow_bss_section(event_has_fired_sym.section, event_has_fired_sym.value, event_table_growth)
        event_list_sym = obj.symbol("?mEventList@CIslandEvents@@0PAPAVCIslandEvent@@A")
        event_has_fired_sym = obj.symbol("?mEventHasFired@CIslandEvents@@0PA_NA")

    insert_off = ctor_sym.value + 0x15B8
    payload = bytearray([
        0x68, first_slot_offset & 0xFF, (first_slot_offset >> 8) & 0xFF, 0x00, 0x00,  # push offset mEventList+184h
        0xE8, 0x00, 0x00, 0x00, 0x00,       # call _VF2RegisterMobileIslandEvents
        0x83, 0xC4, 0x04,                   # add esp,4
    ])
    obj.insert_section_bytes(ctor_sym.section, insert_off, payload)
    helper_sym = obj.append_undefined_symbol("_VF2RegisterMobileIslandEvents")
    obj.append_relocation(ctor_sym.section, insert_off + 1, event_list_sym.index)
    obj.append_relocation(ctor_sym.section, insert_off + 6, helper_sym, IMAGE_REL_I386_REL32)

    bound_patches = 0
    bound_patches += patch_all_in_sections(obj, {".text$mn"}, b"\x83\xFE\x61", bytes([0x83, 0xFE, new_bound]))
    bound_patches += patch_all_in_sections(obj, {".text$mn"}, b"\x83\xFF\x61", bytes([0x83, 0xFF, new_bound]))
    bound_patches += patch_all_in_sections(obj, {".text$mn"}, b"\x6A\x61", bytes([0x6A, new_bound]))
    bound_patches += patch_all_in_sections(obj, {".text$mn"}, b"\x83\xF8\x5F", bytes([0x83, 0xF8, new_bound - 2]))
    destructor_bound_patches = patch_all_in_sections(
        obj,
        {".text$mn"},
        b"\x81\xFE\x84\x01\x00\x00",
        b"\x81\xFE" + struct.pack("<I", new_table_end_offset),
    )

    obj.write(PATCHED / "IslandEvents.obj")

    registrations = []
    for idx, event in enumerate(mobile_events):
        ids = event["ids"]
        registrations.append(
            "    slots[{idx}] = (void *)new CMobileIslandEvent({title}, {desc}, {choice_a}, {choice_b}, {result_a}, {result_b}, {has_choices}, {is_email});".format(
                idx=idx,
                title=ids.get("Title", 0),
                desc=ids.get("Desc", 0),
                choice_a=ids.get("ChoiceA", 0),
                choice_b=ids.get("ChoiceB", 0),
                result_a=ids.get("ResultA", 0),
                result_b=ids.get("ResultB", 0),
                has_choices="true" if event["has_choices"] else "false",
                is_email="true" if event["is_email_event"] else "false",
            )
        )

    helper_cpp = f'''
#include <stddef.h>

enum StringId {{ eStringDummy = 0 }};
enum EBodyPosition {{ eBodyPosition_Standing = 0 }};
enum EAgeSelecter {{ eAgeSelecterAny = 2 }};
enum EGender {{ eGenderAny = -1 }};

class CVillager;
class CVillagerManager {{
public:
    CVillager *GetRandomVillager(EAgeSelecter age_selector, EGender gender, int *out_id);
}};

extern CVillagerManager VillagerManager;

static CVillager *VF2PickMobileEventVillager()
{{
    // Mirrors CEventBoring::CanFire: choose a villager only when the event is
    // considered for firing, never while CIslandEvents is being constructed.
    return VillagerManager.GetRandomVillager(eAgeSelecterAny, eGenderAny, 0);
}}

// Vtable- and layout-compatible with CIslandEvent.  The first 0x10 bytes are
// the stock base object: vptr, target villager, second target villager, award.
// Keeping that prefix prevents dialog/scheduler code from interpreting title
// and description IDs as pointers.
struct CMobileIslandEvent {{
    CVillager *target1_;
    CVillager *target2_;
    int award_;
    int title_;
    int desc_;
    int choice_a_;
    int choice_b_;
    int result_a_;
    int result_b_;
    bool has_choices_;
    bool is_email_;

    CMobileIslandEvent(int title, int desc, int choice_a, int choice_b, int result_a, int result_b, bool has_choices, bool is_email)
        : target1_(0), target2_(0), award_(0), title_(title), desc_(desc), choice_a_(choice_a), choice_b_(choice_b), result_a_(result_a), result_b_(result_b),
          has_choices_(has_choices), is_email_(is_email) {{}}
    virtual ~CMobileIslandEvent() {{}}
    virtual bool CanFire() {{
        target1_ = VF2PickMobileEventVillager();
        target2_ = target1_;
        return target1_ != 0;
    }}
    virtual StringId GetTitle() {{ return (StringId)title_; }}
    virtual StringId GetDescription() {{ return (StringId)desc_; }}
    virtual bool HasChoices() {{ return has_choices_; }}
    virtual bool IsEmailEvent() {{ return is_email_; }}
    virtual StringId GetChoiceAText() {{ return (StringId)choice_a_; }}
    virtual StringId GetChoiceBText() {{ return (StringId)choice_b_; }}
    virtual CVillager *GetTargetVillager() {{ return target1_; }}
    virtual CVillager *GetTargetVillager2() {{ return target2_ ? target2_ : target1_; }}
    virtual EBodyPosition GetVillagerPose() {{ return eBodyPosition_Standing; }}
    virtual StringId GetResultDescription(int choice) {{ return (StringId)(choice == 0 ? result_a_ : result_b_); }}
    virtual void ImpactGame() {{}}
    virtual void ImpactGame(int choice) {{ (void)choice; }}
    virtual void CalcAward() {{}}
    virtual void CalcAward(int choice) {{ (void)choice; }}
    virtual int GetAwardAmount() {{ return award_; }}
}};

static_assert(offsetof(CMobileIslandEvent, target1_) == 4, "CIslandEvent target1 layout");
static_assert(offsetof(CMobileIslandEvent, target2_) == 8, "CIslandEvent target2 layout");
static_assert(offsetof(CMobileIslandEvent, award_) == 12, "CIslandEvent award layout");

extern "C" void __cdecl VF2RegisterMobileIslandEvents(void **slots)
{{
    if (!slots) {{
        return;
    }}
{chr(10).join(registrations)}
}}
'''.strip() + "\n"
    (PATCHED / "vf2_island_events.cpp").write_text(helper_cpp, encoding="ascii")
    manifest["IslandEvents"] = {
        "added": [
            {
                "class": event["class"],
                "table_slot": hex(event["slot"]),
                "slot_offset": f"mEventList+0x{event['slot'] * 4:X}",
                "source": "mobile-only island event class/string names",
                "is_email_event": event["is_email_event"],
                "has_choices": event["has_choices"],
                "strings": [hex(row["string_id"]) for row in event["strings"]],
            }
            for event in mobile_events
        ],
        "constructor_hook": {
            "function": "??0CIslandEvents@@AAE@XZ",
            "insert_offset": hex(insert_off),
            "helper": "_VF2RegisterMobileIslandEvents",
        },
        "first_added_slot": hex(first_added_slot),
        "base_desktop_slots_preserved": "0x01-0x60",
        "new_event_scan_bound_exclusive": hex(new_bound),
        "event_list_growth_bytes": event_table_growth,
        "event_list_new_end_offset": hex(new_table_end_offset),
        "mEventHasFired_new_offset": hex(event_has_fired_sym.value),
        "event_bound_patches": bound_patches,
        "destructor_bound_patches": destructor_bound_patches,
    }


def patch_graphics_manager(manifest):
    obj = CoffObject(PATCHED / "theGraphicsManager.obj")
    image_records = image_records_by_id()
    furniture_records = raw_records_by_item()
    img_sym = obj.symbol(IMAGELIST)
    img_sec = obj.section(img_sym.section)
    furniture_donor = image_records[74]["raw_u32"]

    locked_record = image_records[LOCKED_IMAGE_ID]["raw_u32"][:]
    locked_record[2] = LOCKED_GENERATION_FRAME_COUNT
    locked_record[3] = 1
    locked_desc_off = img_sym.value + LOCKED_IMAGE_ID * DESC_SIZE
    obj.buf[img_sec.raw_ptr + locked_desc_off : img_sec.raw_ptr + locked_desc_off + DESC_SIZE] = struct.pack(
        "<" + "I" * (DESC_SIZE // 4),
        *locked_record,
    )

    character_sheet_manifest = []
    for image_path, spec in CHARACTER_SHEET_SPECS.items():
        image_id = spec["image_id"]
        record = image_records[image_id]["raw_u32"][:]
        probe_path = OUT / "Images" / spec["probe_file"]
        size = read_png_size(probe_path)
        old_grid = [record[2], record[3]]
        new_grid = old_grid[:]
        status = "image_missing"
        if size:
            cell_w, cell_h = spec["cell_size"]
            inferred_cols = size[0] // cell_w if cell_w else record[2]
            inferred_rows = size[1] // cell_h if cell_h else record[3]
            if inferred_cols > record[2] or inferred_rows > record[3]:
                record[2] = max(record[2], inferred_cols)
                record[3] = max(record[3], inferred_rows)
                desc_off = img_sym.value + image_id * DESC_SIZE
                obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack(
                    "<" + "I" * (DESC_SIZE // 4),
                    *record,
                )
                new_grid = [record[2], record[3]]
                status = "patched"
            else:
                status = "unchanged"
        character_sheet_manifest.append({
            "image_id": hex(image_id),
            "image_path": image_path,
            "probe_file": str(probe_path),
            "probe_size": list(size) if size else None,
            "cell_size": list(spec["cell_size"]),
            "old_grid": old_grid,
            "new_grid": new_grid,
            "status": status,
        })

    holiday_body_descriptor_count = HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0
    append_count = (
        len(ITEMS)
        + LOCKED_GENERATION_FRAME_COUNT
        + len(VISIBLE_SPECIAL_UPGRADE_ICON_FILES)
        + holiday_body_descriptor_count
        + len(VF3_TV_FLOATING_ANIMS)
        + OUTFIT_STORE_ENTRY_COUNT
        + HOLIDAY_ORNAMENT_COLLECTION_IMAGE_COUNT
    )
    if append_count:
        obj.insert_section_bytes(img_sym.section, img_sym.value + ORIG_IMAGE_COUNT * DESC_SIZE, b"\0" * (append_count * DESC_SIZE))

    helper_lines = []
    desc_manifest = []
    for idx, (name, donor_item, _list_name, path) in enumerate(ITEMS):
        image_id = image_id_for(idx)
        is_custom_couch = Path(path).name + ".fmap" in COUCH_FMAP_DONORS
        if is_custom_couch:
            donor_image_id = furniture_records[donor_item]["raw_u32"][1]
            vals = image_records[donor_image_id]["raw_u32"][:]
        else:
            donor_image_id = 74
            vals = furniture_donor[:]
        vals[0] = image_id
        vals[1] = 0
        vals[2] = expected_furniture_frame_count(path)
        vals[3] = 0
        desc_off = img_sym.value + image_id * DESC_SIZE
        img_sec = obj.section(img_sym.section)
        obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack("<" + "I" * (DESC_SIZE // 4), *vals)
        sym = "_vf2mob_" + path.split("/")[-1].replace(".", "_").replace("-", "_").replace("'", "").replace("&", "and")
        helper_lines.append(f'const char {sym[1:]}[] = "{path}";')
        symidx = obj.append_undefined_symbol(sym)
        obj.append_relocation(img_sym.section, desc_off + 4, symidx)
        desc_manifest.append({
            "name": name,
            "image_id": hex(image_id),
            "path": path,
            "symbol": sym,
            "donor_image_id": hex(donor_image_id),
            "donor_frame_mode": vals[2],
            "expected_frame_count": expected_furniture_frame_count(path),
        })

    plain_image_donor = image_records[0]["raw_u32"]
    lock_desc_manifest = []
    for frame in range(LOCKED_GENERATION_FRAME_COUNT):
        image_id = lock_image_id_for(frame)
        generation = frame + 2
        path = f"GenerationLocks/lock_{generation:02d}.png"
        vals = plain_image_donor[:]
        vals[0] = image_id
        vals[1] = 0
        vals[2] = 0
        vals[3] = 0
        desc_off = img_sym.value + image_id * DESC_SIZE
        img_sec = obj.section(img_sym.section)
        obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack("<" + "I" * (DESC_SIZE // 4), *vals)
        sym = f"_vf2genlock_{generation:02d}_png"
        helper_lines.append(f'const char {sym[1:]}[] = "{path}";')
        symidx = obj.append_undefined_symbol(sym)
        obj.append_relocation(img_sym.section, desc_off + 4, symidx)
        lock_desc_manifest.append({
            "generation": generation,
            "frame": frame,
            "image_id": hex(image_id),
            "path": path,
            "symbol": sym,
        })

    special_icon_desc_manifest = []
    for item_id, filename in VISIBLE_SPECIAL_UPGRADE_ICON_FILES.items():
        image_id = visible_special_upgrade_icon_id_for(item_id)
        vals = plain_image_donor[:]
        vals[0] = image_id
        vals[1] = 0
        vals[2] = 0
        vals[3] = 0
        desc_off = img_sym.value + image_id * DESC_SIZE
        img_sec = obj.section(img_sym.section)
        obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack("<" + "I" * (DESC_SIZE // 4), *vals)
        sym = "_vf2specialicon_" + filename.replace(".", "_").replace("-", "_")
        helper_lines.append(f'const char {sym[1:]}[] = "{filename}";')
        symidx = obj.append_undefined_symbol(sym)
        obj.append_relocation(img_sym.section, desc_off + 4, symidx)
        special_icon_desc_manifest.append({
            "item_id": hex(item_id),
            "image_id": hex(image_id),
            "path": filename,
            "symbol": sym,
        })

    holiday_body_desc_manifest = []
    if ENABLE_HOLIDAY_BODY_TYPES:
        frame_entries = {
            (entry["gender"], entry["body_value"], entry["role"], entry["frame"]): entry
            for entry in manifest.get("holiday_body_runtime_frames", {}).get("frames", [])
        }
        for gender in ("female", "male"):
            gender_title = gender.title()
            for body_value in HOLIDAY_BODY_VALUES:
                for role in ("bodies", "actions", "sit"):
                    for frame in range(HOLIDAY_BODY_ROLE_FRAME_COUNTS[role]):
                        image_id = villager_body_image_id(gender, body_value, role, frame)
                        entry = frame_entries.get((gender, body_value, role, frame))
                        path = (
                            entry["path"]
                            if entry
                            else f"VillagerBodies/{gender_title}/Body_{body_value:02d}/{role}/Frame{frame:02d}.png"
                        )
                        vals = plain_image_donor[:]
                        vals[0] = image_id
                        vals[1] = 0
                        vals[2] = 1
                        vals[3] = 1
                        desc_off = img_sym.value + image_id * DESC_SIZE
                        img_sec = obj.section(img_sym.section)
                        obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack("<" + "I" * (DESC_SIZE // 4), *vals)
                        sym = f"_vf2body_{gender}_{body_value:02d}_{role}_{frame:02d}_png"
                        helper_lines.append(f'const char {sym[1:]}[] = "{path}";')
                        symidx = obj.append_undefined_symbol(sym)
                        obj.append_relocation(img_sym.section, desc_off + 4, symidx)
                        holiday_body_desc_manifest.append({
                            "gender": gender,
                            "body_value": body_value,
                            "role": role,
                            "frame": frame,
                            "image_id": hex(image_id),
                            "path": path,
                            "symbol": sym,
                            "offset": entry.get("offset") if entry else None,
                            "size": entry.get("size") if entry else None,
                        })

    vf3_tv_anim_desc_manifest = []
    for label, info in VF3_TV_FLOATING_ANIMS.items():
        image_id = vf3_tv_anim_image_id(label, holiday_body_descriptor_count)
        vals = image_records[info["donor_image_id"]]["raw_u32"][:]
        vals[0] = image_id
        vals[1] = 0
        vals[2] = 6
        vals[3] = 3
        desc_off = img_sym.value + image_id * DESC_SIZE
        img_sec = obj.section(img_sym.section)
        obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack("<" + "I" * (DESC_SIZE // 4), *vals)
        runtime_name = VF3_TV_RUNTIME_ANIMATION_NAMES[label]
        sym = "_vf3tv_anim_" + runtime_name.replace(".", "_").replace("-", "_")
        helper_lines.append(f'const char {sym[1:]}[] = "{runtime_name}";')
        symidx = obj.append_undefined_symbol(sym)
        obj.append_relocation(img_sym.section, desc_off + 4, symidx)
        vf3_tv_anim_desc_manifest.append({
            "label": label,
            "floating_anim_enum": hex(info["enum"]),
            "image_id": hex(image_id),
            "path": runtime_name,
            "symbol": sym,
            "donor_image_id": hex(info["donor_image_id"]),
            "grid": [6, 3],
        })

    outfit_icon_desc_manifest = []
    for entry in outfit_store_entries():
        image_id = outfit_icon_image_id(entry["gender"], entry["body_value"], holiday_body_descriptor_count)
        path = outfit_icon_path(entry["gender"], entry["body_value"])
        vals = plain_image_donor[:]
        vals[0] = image_id
        vals[1] = 0
        vals[2] = 1
        vals[3] = 1
        desc_off = img_sym.value + image_id * DESC_SIZE
        img_sec = obj.section(img_sym.section)
        obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack("<" + "I" * (DESC_SIZE // 4), *vals)
        sym = f"_vf2outfiticon_{entry['gender']}_{entry['body_value']:02d}_png"
        helper_lines.append(f'const char {sym[1:]}[] = "{path}";')
        symidx = obj.append_undefined_symbol(sym)
        obj.append_relocation(img_sym.section, desc_off + 4, symidx)
        outfit_icon_desc_manifest.append({
            "item_id": hex(entry["item_id"]),
            "gender": entry["gender"],
            "body_value": entry["body_value"],
            "image_id": hex(image_id),
            "path": path,
            "symbol": sym,
            "grid": [1, 1],
        })

    ornament_desc_manifest = []
    for index, (filename, _x, _y, _w, _h) in enumerate(HOLIDAY_ORNAMENT_ATLAS_RECORDS):
        image_id = holiday_ornament_collection_item_image_id(index, holiday_body_descriptor_count)
        path = f"CollectionOrnaments/{filename}"
        vals = plain_image_donor[:]
        vals[0] = image_id
        vals[1] = 0
        vals[2] = 0
        vals[3] = 0
        desc_off = img_sym.value + image_id * DESC_SIZE
        img_sec = obj.section(img_sym.section)
        obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack("<" + "I" * (DESC_SIZE // 4), *vals)
        sym = "_vf2ornament_" + filename.replace(".", "_").replace("-", "_")
        helper_lines.append(f'const char {sym[1:]}[] = "{path}";')
        symidx = obj.append_undefined_symbol(sym)
        obj.append_relocation(img_sym.section, desc_off + 4, symidx)
        ornament_desc_manifest.append({
            "collectable": hex(HOLIDAY_ORNAMENT_COLLECTABLE_START + index),
            "image_id": hex(image_id),
            "path": path,
            "symbol": sym,
        })

    ornament_background_image_id = holiday_ornament_collection_background_image_id(holiday_body_descriptor_count)
    vals = plain_image_donor[:]
    vals[0] = ornament_background_image_id
    vals[1] = 0
    vals[2] = 0
    vals[3] = 0
    desc_off = img_sym.value + ornament_background_image_id * DESC_SIZE
    img_sec = obj.section(img_sym.section)
    obj.buf[img_sec.raw_ptr + desc_off : img_sec.raw_ptr + desc_off + DESC_SIZE] = struct.pack("<" + "I" * (DESC_SIZE // 4), *vals)
    ornament_bg_sym = "_vf2ornament_collection_background_png"
    helper_lines.append(f'const char {ornament_bg_sym[1:]}[] = "{HOLIDAY_ORNAMENT_BACKGROUND_FILENAME}";')
    symidx = obj.append_undefined_symbol(ornament_bg_sym)
    obj.append_relocation(img_sym.section, desc_off + 4, symidx)
    ornament_desc_manifest.append({
        "role": "background",
        "image_id": hex(ornament_background_image_id),
        "path": HOLIDAY_ORNAMENT_BACKGROUND_FILENAME,
        "symbol": ornament_bg_sym,
    })

    new_image_max = ORIG_IMAGE_MAX + append_count
    new_scan_end = ORIG_IMAGE_COUNT * DESC_SIZE + append_count * DESC_SIZE
    new_cleanup_end = 0x7798 + append_count * DESC_SIZE
    patches = {
        "max_image_guard": patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", ORIG_IMAGE_MAX), struct.pack("<I", new_image_max)),
        "image_scan_end": patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", ORIG_IMAGE_COUNT * DESC_SIZE), struct.pack("<I", new_scan_end)),
        "cleanup_end": patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", 0x7798), struct.pack("<I", new_cleanup_end)),
    }

    index_sym = obj.symbol(IMAGEINDEX)
    index_sec = obj.section(index_sym.section)
    obj.grow_bss_section(index_sym.section, index_sec.raw_size, append_count * 4)
    obj.write(PATCHED / "theGraphicsManager.obj")

    (PATCHED / "vf2_mobile_furniture_strings.c").write_text("\n".join(helper_lines) + "\n", encoding="ascii")
    manifest["theGraphicsManager"] = {
        "generation_lock_art": {
            "image_id": hex(LOCKED_IMAGE_ID),
            "path": "locked.png",
            "old_grid": image_records[LOCKED_IMAGE_ID]["raw_u32"][2:4],
            "new_grid": [LOCKED_GENERATION_FRAME_COUNT, 1],
            "standalone_image_base": hex(lock_image_id_for(0)),
            "standalone_images": lock_desc_manifest,
        },
        "visible_special_upgrade_icons": special_icon_desc_manifest,
        "holiday_body_frame_images": {
            "enabled": ENABLE_HOLIDAY_BODY_TYPES,
            "image_base": hex(villager_body_image_base()) if ENABLE_HOLIDAY_BODY_TYPES else None,
            "image_count": holiday_body_descriptor_count,
            "descriptors": holiday_body_desc_manifest,
        },
        "vf3_tv_floating_animation_images": {
            "image_base": hex(vf3_tv_anim_image_base(holiday_body_descriptor_count)),
            "image_count": len(VF3_TV_FLOATING_ANIMS),
            "descriptors": vf3_tv_anim_desc_manifest,
        },
        "outfit_store_icons": {
            "image_base": hex(outfit_icon_image_base(holiday_body_descriptor_count)),
            "image_count": OUTFIT_STORE_ENTRY_COUNT,
            "descriptors": outfit_icon_desc_manifest,
        },
        "holiday_ornament_collection_images": {
            "image_base": hex(holiday_ornament_collection_image_base(holiday_body_descriptor_count)),
            "image_count": HOLIDAY_ORNAMENT_COLLECTION_IMAGE_COUNT,
            "descriptors": ornament_desc_manifest,
        },
        "character_sheet_art": character_sheet_manifest,
        "descriptors": desc_manifest,
        "append_count": append_count,
        "new_image_max": hex(new_image_max),
        "patches": patches,
    }


def patch_floating_anim_table(manifest):
    obj = CoffObject(PATCHED / "FloatingAnim.obj")
    anim_sym = obj.symbol("?m_sAnim@CFloatingAnim@@0PAUSAnim@1@A")
    holiday_body_descriptor_count = HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0
    old_table_size = 0x400
    new_entries = []
    for label, info in VF3_TV_FLOATING_ANIMS.items():
        new_entries.append(struct.pack("<IIII", vf3_tv_anim_image_id(label, holiday_body_descriptor_count), 18, 1, 0))
    payload = b"".join(new_entries)

    obj.insert_section_bytes(anim_sym.section, anim_sym.value + old_table_size, payload)

    load_sym = obj.symbol("?LoadAssets@CFloatingAnim@@QAEXXZ")
    load_sec = obj.section(load_sym.section)
    old_bound = b"\x81\xFE" + struct.pack("<I", old_table_size)
    new_bound = b"\x81\xFE" + struct.pack("<I", old_table_size + len(payload))
    load_start = load_sec.raw_ptr + load_sym.value
    load_end = load_start + load_sec.raw_size
    hit = obj.buf.find(old_bound, load_start, load_end)
    if hit < 0:
        raise RuntimeError("Could not find CFloatingAnim::LoadAssets table bound")
    obj.buf[hit : hit + len(old_bound)] = new_bound

    obj.write(PATCHED / "FloatingAnim.obj")
    manifest["FloatingAnim"] = {
        "private_vf3_tv_entries": [
            {
                "label": label,
                "enum": hex(info["enum"]),
                "image_id": hex(vf3_tv_anim_image_id(label, holiday_body_descriptor_count)),
                "runtime_name": VF3_TV_RUNTIME_ANIMATION_NAMES[label],
                "frames": 18,
                "random_start_frame": True,
            }
            for label, info in VF3_TV_FLOATING_ANIMS.items()
        ],
        "old_table_size": hex(old_table_size),
        "new_table_size": hex(old_table_size + len(payload)),
        "load_assets_bound_patch_offset": hex(hit - load_start),
    }


def patch_achievement_holiday_ornaments(manifest):
    achievement_obj = CoffObject(PATCHED / "Achievement.obj")
    list_sym = achievement_obj.symbol("?achievementList@@3PAUsAchievementListEntry@@A")
    list_sec = achievement_obj.section(list_sym.section)
    row_insert = list_sym.value + 0x5F * ACHIEVEMENT_ROW_SIZE
    if row_insert != list_sec.raw_size:
        raise RuntimeError("Unexpected achievementList append site")
    ornament_row = struct.pack(
        "<7I",
        HOLIDAY_ORNAMENT_ACHIEVEMENT_ID,
        HOLIDAY_ORNAMENT_ACHIEVEMENT_TARGET,
        0x1ED,
        0,
        holiday_ornament_achievement_title_string_id(),
        holiday_ornament_achievement_desc_string_id(),
        0,
    )
    achievement_obj.insert_section_bytes(list_sym.section, row_insert, ornament_row)

    goal_collector_target_off = list_sym.value + 0x54 * ACHIEVEMENT_ROW_SIZE + 4
    if struct.unpack_from("<I", achievement_obj.buf, list_sec.raw_ptr + goal_collector_target_off)[0] != 12:
        raise RuntimeError("Unexpected Goal collector target count")
    struct.pack_into("<I", achievement_obj.buf, list_sec.raw_ptr + goal_collector_target_off, 13)

    complete_sym = achievement_obj.symbol("?AchievementsComplete@CAchievement@@QAEHXZ")
    complete_sec = achievement_obj.section(complete_sym.section)
    complete_cmp = complete_sym.value + 0x23
    if achievement_obj.buf[complete_sec.raw_ptr + complete_cmp : complete_sec.raw_ptr + complete_cmp + 3] != b"\x83\xFE\x5F":
        raise RuntimeError("Unexpected AchievementsComplete bound")
    achievement_obj.buf[complete_sec.raw_ptr + complete_cmp + 2] = HOLIDAY_ORNAMENT_ACHIEVEMENT_ORDER_COUNT

    draw_achievement_sym = achievement_obj.symbol("?DrawAchievement@CAchievement@@QAEXHHH_NM@Z")
    draw_sec = achievement_obj.section(draw_achievement_sym.section)
    draw_raw = draw_sec.raw_ptr + draw_achievement_sym.value
    for bound_off in (0xD8, 0x191):
        if achievement_obj.buf[draw_raw + bound_off : draw_raw + bound_off + 3] != b"\x83\xFF\x5F":
            raise RuntimeError(f"Unexpected DrawAchievement bound at {bound_off:#x}")
        achievement_obj.buf[draw_raw + bound_off + 2] = HOLIDAY_ORNAMENT_ACHIEVEMENT_ORDER_COUNT

    set_complete_sym = achievement_obj.symbol("?SetComplete@CAchievement@@QAEXW4EAchievement@@@Z")
    set_complete_sec = achievement_obj.section(set_complete_sym.section)
    set_complete_insert = set_complete_sym.value + 0x95
    expected_epilogue = b"\x5F\x5E\x5B\x5D\xC2\x04\x00"
    if achievement_obj.buf[set_complete_sec.raw_ptr + set_complete_insert : set_complete_sec.raw_ptr + set_complete_insert + len(expected_epilogue)] != expected_epilogue:
        raise RuntimeError("Unexpected SetComplete epilogue")
    increment_sym = achievement_obj.symbol("?IncrementProgress@CAchievement@@QAEXW4EAchievement@@H@Z").index
    collection_meta_payload = (
        b"\x83\xFE" + bytes([HOLIDAY_ORNAMENT_ACHIEVEMENT_ID])
        + b"\x75\x0B"
        + b"\x6A\x01"
        + b"\x6A\x54"
        + b"\x8B\xCF"
        + b"\xE8\x00\x00\x00\x00"
    )
    achievement_obj.insert_section_bytes(set_complete_sym.section, set_complete_insert, collection_meta_payload)
    achievement_obj.append_relocation(
        set_complete_sym.section,
        set_complete_insert + len(collection_meta_payload) - 4,
        increment_sym,
        IMAGE_REL_I386_REL32,
    )
    achievement_obj.write(PATCHED / "Achievement.obj")

    scene_obj = CoffObject(PATCHED / "AchievementsScene.obj")
    order_sym = scene_obj.symbol("?achievementOrder@@3QBHB")
    order_sec = scene_obj.section(order_sym.section)
    order_insert = order_sym.value + 0x5F * 4
    if order_insert != order_sec.raw_size:
        raise RuntimeError("Unexpected achievementOrder append site")
    scene_obj.insert_section_bytes(order_sym.section, order_insert, struct.pack("<I", HOLIDAY_ORNAMENT_ACHIEVEMENT_ID))

    ctor_sym = scene_obj.symbol("??0CAchievementsScene@@AAE@XZ")
    ctor_sec = scene_obj.section(ctor_sym.section)
    ctor_start = ctor_sec.raw_ptr + ctor_sym.value
    ctor_data = scene_obj.buf[ctor_start : ctor_start + ctor_sec.raw_size - ctor_sym.value]
    old_content_height = struct.pack("<I", 0x189A)
    new_content_height = struct.pack("<I", 0x18DC)
    patched_heights = 0
    search_from = 0
    while True:
        hit = ctor_data.find(old_content_height, search_from)
        if hit < 0:
            break
        scene_obj.buf[ctor_start + hit : ctor_start + hit + 4] = new_content_height
        patched_heights += 1
        search_from = hit + 4
    if patched_heights != 2:
        raise RuntimeError("Unexpected CAchievementsScene content height patches")

    draw_sym = scene_obj.symbol("?DrawScene@CAchievementsScene@@MAEXXZ")
    draw_sec = scene_obj.section(draw_sym.section)
    draw_raw = draw_sec.raw_ptr + draw_sym.value
    if scene_obj.buf[draw_raw + 0xAD : draw_raw + 0xAD + 6] != b"\x81\xF9\x7E\x18\x00\x00":
        raise RuntimeError("Unexpected CAchievementsScene draw threshold")
    struct.pack_into("<I", scene_obj.buf, draw_raw + 0xAF, 0x18C0)
    if scene_obj.buf[draw_raw + 0xF5 : draw_raw + 0xF5 + 6] != b"\x81\xFE\x7C\x01\x00\x00":
        raise RuntimeError("Unexpected CAchievementsScene order bound")
    struct.pack_into("<I", scene_obj.buf, draw_raw + 0xF7, 0x180)
    scene_obj.write(PATCHED / "AchievementsScene.obj")

    manifest["HolidayOrnamentAchievement"] = {
        "status": "patched",
        "achievement_id": hex(HOLIDAY_ORNAMENT_ACHIEVEMENT_ID),
        "target": HOLIDAY_ORNAMENT_ACHIEVEMENT_TARGET,
        "title": "Ornamentologist",
        "description": "You completed the collection of holiday ornaments.",
        "title_string": hex(holiday_ornament_achievement_title_string_id()),
        "description_string": hex(holiday_ornament_achievement_desc_string_id()),
        "goal_collector_target": 13,
        "save_state_note": "CAchievement already serializes 0x125 12-byte records; no save-state size change was needed for achievement 0x5F.",
    }


def patch_collectable_item_holiday_ornaments(manifest):
    obj = CoffObject(PATCHED / "CollectableItem.obj")
    patches = []

    reset_sym = obj.symbol("?Reset@CCollectableItem@@QAEXXZ")
    reset_insert = reset_sym.value + 0x1ED
    reset_sec = obj.section(reset_sym.section)
    expected_reset = b"\xC7\x83\xAC\x08\x00\x00\x00\x00\x00\x00"
    if obj.buf[reset_sec.raw_ptr + reset_insert : reset_sec.raw_ptr + reset_insert + len(expected_reset)] != expected_reset:
        raise RuntimeError("Unexpected CCollectableItem::Reset insertion site")

    add_spawn_sym = obj.symbol("?AddSpawnArea@CCollectableItem@@QAEXUldwRect@@W4ECarrying@@@Z").index
    rect_symbols = [
        "__xmm@0000030200000764000000b400000634",
        "__xmm@000001bd000002fa000000c400000112",
        "__xmm@0000026f0000019d0000017800000098",
        "__xmm@0000075000000137000005680000008d",
    ]
    reset_payload = bytearray()
    reset_relocs = []
    for rect_symbol in rect_symbols:
        start = len(reset_payload)
        reset_payload += b"\x0F\x28\x05\x00\x00\x00\x00"  # movaps xmm0,[rect]
        reset_payload += b"\x8B\xCB"                      # mov ecx,ebx
        reset_payload += b"\x68" + struct.pack("<I", HOLIDAY_ORNAMENT_COLLECTABLE_START)
        reset_payload += b"\x83\xEC\x10"                  # sub esp,10h
        reset_payload += b"\x8B\xC4"                      # mov eax,esp
        reset_payload += b"\x0F\x11\x00"                  # movups [eax],xmm0
        reset_payload += b"\xE8\x00\x00\x00\x00"          # call AddSpawnArea
        reset_relocs.append((start + 3, obj.symbol(rect_symbol).index, None))
        reset_relocs.append((start + len(reset_payload[start:]) - 4, add_spawn_sym, IMAGE_REL_I386_REL32))
    obj.insert_section_bytes(reset_sym.section, reset_insert, bytes(reset_payload))
    for local_off, symidx, rtype in reset_relocs:
        if rtype is None:
            obj.append_relocation(reset_sym.section, reset_insert + local_off, symidx)
        else:
            obj.append_relocation(reset_sym.section, reset_insert + local_off, symidx, rtype)
    patches.append({
        "function": "?Reset@CCollectableItem@@QAEXXZ",
        "insert_offset": "0x1ed",
        "spawn_area_count": len(rect_symbols),
        "base_collectable": hex(HOLIDAY_ORNAMENT_COLLECTABLE_START),
    })

    def insert_range_true(function_name, start_item, end_item):
        sym = obj.symbol(function_name)
        insert_off = sym.value + 0x06
        sec = obj.section(sym.section)
        expected = b"\x83\xF8"
        if obj.buf[sec.raw_ptr + insert_off : sec.raw_ptr + insert_off + len(expected)] != expected:
            raise RuntimeError(f"Unexpected {function_name} range insertion site")
        payload = bytearray()
        payload += b"\x3D" + struct.pack("<I", start_item)
        payload += b"\x7C\x0D"
        payload += b"\x3D" + struct.pack("<I", end_item)
        payload += b"\x7F\x06"
        payload += b"\xB0\x01"
        payload += b"\x5D"
        payload += b"\xC2\x04\x00"
        obj.insert_section_bytes(sym.section, insert_off, bytes(payload))
        return {
            "function": function_name,
            "insert_offset": "0x6",
            "range": f"{hex(start_item)}-{hex(end_item)}",
        }

    patches.append(insert_range_true(
        "?IsCommonCollectable@CCollectableItem@@QBE?B_NW4ECarrying@@@Z",
        HOLIDAY_ORNAMENT_COLLECTABLE_START,
        HOLIDAY_ORNAMENT_COLLECTABLE_START + 3,
    ))
    patches.append(insert_range_true(
        "?IsUncommonCollectable@CCollectableItem@@QBE?B_NW4ECarrying@@@Z",
        HOLIDAY_ORNAMENT_COLLECTABLE_START + 4,
        HOLIDAY_ORNAMENT_COLLECTABLE_START + 7,
    ))
    patches.append(insert_range_true(
        "?IsRareCollectable@CCollectableItem@@QBE?B_NW4ECarrying@@@Z",
        HOLIDAY_ORNAMENT_COLLECTABLE_START + 8,
        HOLIDAY_ORNAMENT_COLLECTABLE_END,
    ))

    count_sym = obj.symbol("?CollectionCount@CCollectableItem@@QBE?BHW4ECarrying@@_N11@Z")
    count_insert = count_sym.value + 0x0B
    count_sec = obj.section(count_sym.section)
    expected_count = b"\x8D\x42\x99"
    if obj.buf[count_sec.raw_ptr + count_insert : count_sec.raw_ptr + count_insert + len(expected_count)] != expected_count:
        raise RuntimeError("Unexpected CCollectableItem::CollectionCount insertion site")
    count_payload_len = 34
    count_continue = count_insert + count_payload_len
    count_target = count_sym.value + 0x5A + count_payload_len
    count_payload = bytearray()
    count_payload += b"\x81\xFA" + struct.pack("<I", HOLIDAY_ORNAMENT_COLLECTABLE_START)
    count_payload += b"\x0F\x8C" + struct.pack("<i", count_continue - (count_insert + len(count_payload) + 6))
    count_payload += b"\x81\xFA" + struct.pack("<I", HOLIDAY_ORNAMENT_COLLECTABLE_END)
    count_payload += b"\x0F\x8F" + struct.pack("<i", count_continue - (count_insert + len(count_payload) + 6))
    count_payload += b"\xBE" + struct.pack("<I", HOLIDAY_ORNAMENT_COLLECTABLE_START)
    count_payload += b"\xE9" + struct.pack("<i", count_target - (count_insert + len(count_payload) + 5))
    if len(count_payload) != count_payload_len:
        raise RuntimeError("Unexpected CollectionCount payload length")
    obj.insert_section_bytes(count_sym.section, count_insert, bytes(count_payload))
    patches.append({
        "function": "?CollectionCount@CCollectableItem@@QBE?BHW4ECarrying@@_N11@Z",
        "insert_offset": "0xb",
        "range": f"{hex(HOLIDAY_ORNAMENT_COLLECTABLE_START)}-{hex(HOLIDAY_ORNAMENT_COLLECTABLE_END)}",
        "collection_base": hex(HOLIDAY_ORNAMENT_COLLECTABLE_START),
    })

    drop_sym = obj.symbol("?Drop@CCollectableItem@@UAEXAAVCVillager@@W4ECarrying@@@Z")
    drop_insert = drop_sym.value + 0x1D4
    drop_sec = obj.section(drop_sym.section)
    expected_drop = b"\x5F\x5E\x8B\xE5"
    if obj.buf[drop_sec.raw_ptr + drop_insert : drop_sec.raw_ptr + drop_insert + len(expected_drop)] != expected_drop:
        raise RuntimeError("Unexpected CCollectableItem::Drop insertion site")
    achievement_sym = obj.symbol("?Achievement@@3VCAchievement@@A").index
    increment_sym = obj.symbol("?IncrementProgress@CAchievement@@QAEXW4EAchievement@@H@Z").index
    drop_payload = bytearray()
    drop_payload += b"\x8D\x87" + struct.pack("<i", -HOLIDAY_ORNAMENT_COLLECTABLE_START)
    drop_payload += b"\x83\xF8\x0B"
    drop_payload += b"\x77\x00"
    drop_skip_rel_off = len(drop_payload) - 1
    drop_payload += b"\x6A\x01"
    drop_payload += b"\x6A" + bytes([HOLIDAY_ORNAMENT_ACHIEVEMENT_ID])
    drop_payload += b"\xB9\x00\x00\x00\x00"
    achievement_reloc_off = len(drop_payload) - 4
    drop_payload += b"\xE8\x00\x00\x00\x00"
    increment_reloc_off = len(drop_payload) - 4
    drop_payload += b"\x68" + struct.pack("<I", HOLIDAY_ORNAMENT_COLLECTABLE_START)
    drop_payload += b"\xE9" + struct.pack("<i", (drop_sym.value + 0x168) - (drop_insert + len(drop_payload) + 5))
    drop_payload[drop_skip_rel_off] = len(drop_payload) - (drop_skip_rel_off + 1)
    obj.insert_section_bytes(drop_sym.section, drop_insert, bytes(drop_payload))
    obj.append_relocation(drop_sym.section, drop_insert + achievement_reloc_off, achievement_sym)
    obj.append_relocation(drop_sym.section, drop_insert + increment_reloc_off, increment_sym, IMAGE_REL_I386_REL32)
    patches.append({
        "function": "?Drop@CCollectableItem@@UAEXAAVCVillager@@W4ECarrying@@@Z",
        "insert_offset": "0x1d4",
        "first_copy_range": f"{hex(HOLIDAY_ORNAMENT_COLLECTABLE_START)}-{hex(HOLIDAY_ORNAMENT_COLLECTABLE_END)}",
        "complete_check_base": hex(HOLIDAY_ORNAMENT_COLLECTABLE_START),
        "specific_goal_row": hex(HOLIDAY_ORNAMENT_ACHIEVEMENT_ID),
    })

    obj.write(PATCHED / "CollectableItem.obj")
    manifest["CollectableItemHolidayOrnaments"] = {
        "status": "patched",
        "collectable_range": f"{hex(HOLIDAY_ORNAMENT_COLLECTABLE_START)}-{hex(HOLIDAY_ORNAMENT_COLLECTABLE_END)}",
        "spawn_model": "registered as an additional AddSpawnArea collection; CCollectableItem::Update/Add and Lucky Rock odds remain stock",
        "patches": patches,
    }


def patch_collection_scene_holiday_ornaments(manifest):
    obj = CoffObject(PATCHED / "CollectionScene.obj")
    holiday_body_descriptor_count = HOLIDAY_BODY_IMAGE_COUNT if ENABLE_HOLIDAY_BODY_TYPES else 0
    page_entries = [
        (
            holiday_ornament_collection_item_image_id(index, holiday_body_descriptor_count),
            x,
            y,
        )
        for index, (x, y) in enumerate(HOLIDAY_ORNAMENT_COLLECTION_SLOT_POSITIONS)
    ]

    sm_sym_name = "?sm_sCollectable@CCollectionScene@@0PAUSCollectable@1@A"
    frame_sym_name = "?gCollectionFrame@@3PAUSCollectable@CCollectionScene@@A"
    label_sym_name = "?gCollectionLabel@@3PAUSCollectable@CCollectionScene@@A"
    label_info_sym_name = "?gLabelInfo@@3PAUsCollectionLabelInfo@@A"
    collectable_sym_name = "?gCollectable@@3PAW4ECarrying@@A"

    sm_sym = obj.symbol(sm_sym_name)
    obj.insert_section_bytes(
        sm_sym.section,
        sm_sym.value + 5 * HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT * 12,
        b"".join(struct.pack("<III", *entry) for entry in page_entries),
    )

    frame_sym = obj.symbol(frame_sym_name)
    obj.insert_section_bytes(
        frame_sym.section,
        frame_sym.value + 5 * 12,
        struct.pack("<III", holiday_ornament_collection_background_image_id(holiday_body_descriptor_count), 0, 0),
    )

    label_sym = obj.symbol(label_sym_name)
    obj.insert_section_bytes(
        label_sym.section,
        label_sym.value + 5 * 12,
        struct.pack("<III", 0x198, 0x154, 0x5F),
    )

    label_info_sym = obj.symbol(label_info_sym_name)
    obj.insert_section_bytes(
        label_info_sym.section,
        label_info_sym.value + 5 * 20,
        struct.pack("<IIIII", holiday_ornament_collection_title_string_id(), 0xC3, 0x0C, 0xCE, 0x0C),
    )

    collectable_sym = obj.symbol(collectable_sym_name)
    obj.insert_section_bytes(
        collectable_sym.section,
        collectable_sym.value + 5 * HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT * 4,
        struct.pack("<" + "I" * HOLIDAY_ORNAMENT_COLLECTION_ITEM_COUNT, *range(HOLIDAY_ORNAMENT_COLLECTABLE_START, HOLIDAY_ORNAMENT_COLLECTABLE_END + 1)),
    )

    mouse_sym = obj.symbol("?HandleMouse@CCollectionScene@@UAE_NHUldwPoint@@@Z")
    mouse_sec = obj.section(mouse_sym.section)
    mouse_raw = mouse_sec.raw_ptr + mouse_sym.value
    if obj.buf[mouse_raw + 0x4B : mouse_raw + 0x52] != b"\xC7\x43\x14\x04\x00\x00\x00":
        raise RuntimeError("Unexpected CCollectionScene::HandleMouse decrement wrap bytes")
    obj.buf[mouse_raw + 0x4E : mouse_raw + 0x52] = struct.pack("<I", HOLIDAY_ORNAMENT_COLLECTION_PAGE)
    if obj.buf[mouse_raw + 0x79 : mouse_raw + 0x7C] != b"\x83\xF8\x05":
        raise RuntimeError("Unexpected CCollectionScene::HandleMouse increment wrap bytes")
    obj.buf[mouse_raw + 0x7B] = HOLIDAY_ORNAMENT_COLLECTION_PAGE + 1

    draw_sym = obj.symbol("?DrawScene@CCollectionScene@@MAEXXZ")
    draw_sec = obj.section(draw_sym.section)
    draw_count_off = draw_sym.value + 0x17D
    if obj.buf[draw_sec.raw_ptr + draw_count_off : draw_sec.raw_ptr + draw_count_off + 7] != b"\x8B\x47\x14\xFF\x74\x87\x18":
        raise RuntimeError("Unexpected CCollectionScene::DrawScene count bytes")
    obj.insert_section_bytes(draw_sym.section, draw_sym.value + 0x184, b"\x90\x90")
    draw_sec = obj.section(draw_sym.section)
    draw_payload = b"\xFF\x77\x14\xE8\x00\x00\x00\x00\x50"
    obj.buf[draw_sec.raw_ptr + draw_count_off : draw_sec.raw_ptr + draw_count_off + len(draw_payload)] = draw_payload
    helper_sym = obj.append_undefined_symbol("_VF2CollectionPageCount")
    obj.append_relocation(draw_sym.section, draw_sym.value + 0x181, helper_sym, IMAGE_REL_I386_REL32)

    obj.write(PATCHED / "CollectionScene.obj")
    manifest["CollectionSceneHolidayOrnaments"] = {
        "status": "patched",
        "page": HOLIDAY_ORNAMENT_COLLECTION_PAGE,
        "collectable_range": f"{hex(HOLIDAY_ORNAMENT_COLLECTABLE_START)}-{hex(HOLIDAY_ORNAMENT_COLLECTABLE_END)}",
        "title_string": hex(holiday_ornament_collection_title_string_id()),
        "background_image_id": hex(holiday_ornament_collection_background_image_id(holiday_body_descriptor_count)),
        "item_images": [
            {
                "collectable": hex(HOLIDAY_ORNAMENT_COLLECTABLE_START + index),
                "image_id": hex(image_id),
                "position": [x, y],
            }
            for index, (image_id, x, y) in enumerate(page_entries)
        ],
        "page_count_helper": "_VF2CollectionPageCount",
        "object_size_note": "CCollectionScene stays 0x30 bytes; DrawScene asks helper for page counts instead of adding a sixth cached field.",
    }


def sync_generation_lock_art(manifest):
    dst = OUT / "Images" / "locked.png"
    source_strip_width = LOCKED_GENERATION_FRAME_COUNT * LOCKED_GENERATION_CELL_WIDTH
    icon_dir = OUT / "Images" / "GenerationLocks"
    status = {
        "source": str(LOCKED_PNG_SOURCE),
        "destination": str(dst),
        "expected_frames": LOCKED_GENERATION_FRAME_COUNT,
        "strip_size": [source_strip_width, LOCKED_GENERATION_CELL_HEIGHT],
        "standalone_icon_dir": str(icon_dir),
    }
    if LOCKED_PNG_SOURCE.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        icon_dir.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image

            image = Image.open(LOCKED_PNG_SOURCE).convert("RGBA")
            source_size = list(image.size)
            if image.size != (source_strip_width, LOCKED_GENERATION_CELL_HEIGHT):
                image = image.resize((source_strip_width, LOCKED_GENERATION_CELL_HEIGHT), Image.Resampling.LANCZOS)
                normalized_source = True
            else:
                normalized_source = False
            image.save(dst)
            icons = []
            for frame in range(LOCKED_GENERATION_FRAME_COUNT):
                generation = frame + 2
                src_box = (
                    frame * LOCKED_GENERATION_CELL_WIDTH,
                    0,
                    (frame + 1) * LOCKED_GENERATION_CELL_WIDTH,
                    LOCKED_GENERATION_CELL_HEIGHT,
                )
                icon_path = icon_dir / f"lock_{generation:02d}.png"
                image.crop(src_box).save(icon_path)
                icons.append({"generation": generation, "path": str(icon_path), "bytes": icon_path.stat().st_size})
            status.update({
                "copied": True,
                "normalized_source_strip": normalized_source,
                "source_size": source_size,
                "output_size": [source_strip_width, LOCKED_GENERATION_CELL_HEIGHT],
                "standalone_icons": icons,
                "bytes": dst.stat().st_size,
            })
        except Exception as exc:
            shutil.copy2(LOCKED_PNG_SOURCE, dst)
            status.update({
                "copied": True,
                "normalized": False,
                "normalization_error": str(exc),
                "bytes": dst.stat().st_size,
            })
    else:
        status.update({"copied": False, "reason": "source_missing"})
    manifest["generation_lock_art_asset"] = status


def write_internal_workings_summary(manifest):
    text = """Virtual Families 2 - Internal Furniture/Store Notes
====================================================

Core model
----------
Most store-placeable things are EInventoryItem values. Furniture, pets,
decorations, rugs, and similar objects are backed by a central furniture/item
record, then exposed to store tabs through CInventoryManager category lists.

A valid item generally needs:

1. A CFurnitureManager item record.
2. A valid EImage descriptor/path.
3. Store category/list membership.
4. Valid short and long string IDs.
5. A price and generation lock value.
6. A compatible item type / behavior type.
7. A matching .fmap asset when the item is placeable.

Furniture records
-----------------
The furniture info table is:

    ?itemInfo@@3PAUsFurnitureInfo@@A

Each record is 0x6C bytes. The fields we rely on most are:

    +0x00  EInventoryItem item id
    +0x04  EImage image id
    +0x08  store price
    +0x0C  generation lock
    +0x10  item type / behavior category
    +0x14  short description string id
    +0x18  long description string id
    +0x58  extra/mobile field, zeroed for added furniture safety

Images
------
Images are managed by theGraphicsManager through:

    ?ImageList@@3PAUImageDescriptor@@A

Important descriptor fields are:

    +0x00  EImage id
    +0x04  path string pointer
    +0x08  columns / strip count
    +0x0C  rows / grid rows

Normal furniture uses paths such as:

    Furniture/CouchBlue.png
    Furniture/Chaise_red.png

The game commonly calls:

    theGraphicsManager::GetImageGrid(EImage)
    theGraphicsManager::Draw(...)
    theGraphicsManager::DrawCell(...)

Store categories
----------------
Items do not appear in store tabs just because a furniture record exists. Their
item IDs must also be inserted into CInventoryManager category arrays.

Important lists include:

    gFurniture2List      Living Room
    gFurniture3List      Dining/Office style categories
    gFurniture4List      Bedroom
    gFurniture5List      Outdoors
    gFurniture6List      Additional furniture category
    gAccessoriesList     Accessories
    gPetList             Pets

When extending a list, both the array contents and the store/category count
logic must be extended. If the counts are not patched, new items can appear to
replace base-game entries.

Store draw flow
---------------
The store render path is approximately:

    CScrollingStoreScene::DrawVisibleStoreItem(...)
      -> CInventoryManager::GetCategoryItem(category, index)
      -> CInventoryManager::DrawItem(...)
      -> CInventoryManager::IsLocked(item)
      -> CInventoryManager::GetLockGenerationLevel(item)
      -> draw generation-lock icon if locked
      -> CInventoryManager::GetShortDesc(item)
      -> CInventoryManager::GetLongDesc(item)
      -> CalcPrice(item)
      -> DrawMoney(...)

Furniture previews eventually delegate into CFurnitureManager drawing paths for
furniture-range items.

Strings
-------
Names and descriptions come from theStringManager. Each furniture record points
to a short and long string id. If either id has no valid string table row, the
game displays:

    Unknown String Id!!!!

Generation locks
----------------
Generation lock is the integer at furniture record +0x0C.

The desktop store originally only sorted/considered generation-locked items up
to generation 9. The additive build raises that visible lock window to 30.

The original desktop lock art was one small locked.png strip for generations
2-9. For generations 2-30, this build generates standalone images:

    Images/GenerationLocks/lock_02.png
    ...
    Images/GenerationLocks/lock_30.png

The store's lock draw call is retargeted to _VF2DrawGenerationLock, which maps
frame generation-2 to the corresponding standalone image. This avoids the old
DrawCell strip wrapping/slicing behavior.

Fmaps and behavior
------------------
Placeable furniture uses .fmap files in Assets. These appear to define collision
and interaction regions/hotspots. If an added mobile item has an unsupported
desktop behavior hotspot, dropping a villager on it can crash.

For safety:

    - Vibrant couches keep couch-compatible behavior and couch-style fmaps.
    - Most non-couch mobile-only added decor has its behavior grid sanitized.
    - Risky mobile item types are overridden to safer desktop donor types where
      needed.

Item type matters
-----------------
The item type field at record +0x10 affects how villagers and game systems treat
the item. Matching base-game couch item type/behavior is what made custom
couches sittable. Inert/decor types prevent unsupported interaction dispatch.

Common failure symptoms
-----------------------
Missing store item:
    Item is not in a category list, or category count/list capacity was not
    patched.

Replaces an existing item:
    Category array/count extension is wrong.

Unknown String Id!!!!:
    Bad string IDs or missing string table rows.

Wrong or missing sprite:
    Bad image id, descriptor, path, or missing PNG.

Crash when dropping a person:
    Bad item type, unsafe .fmap behavior grid, or unsupported behavior callback.

Wrong lock art:
    Bad generation value or lock draw path.

Wrong store section:
    Item was inserted into the wrong CInventoryManager category list.
"""
    path = OUT / "VF2_INTERNAL_WORKINGS_SUMMARY.txt"
    path.write_text(text, encoding="utf-8")
    manifest["internal_workings_summary"] = {
        "path": str(path),
        "status": "written",
    }


def sync_behavior_assets(manifest):
    assets = OUT / "Assets"
    copied = []
    invisible_outdoor_copied = []
    invisible_transparent_copied = []
    missing = []
    sanitized = []
    for target, donor in COUCH_FMAP_DONORS.items():
        src = assets / donor
        dst = assets / target
        if src.exists():
            shutil.copy2(src, dst)
            copied.append({"target": target, "donor": donor, "bytes": dst.stat().st_size})
        else:
            missing.append({"target": target, "donor": donor})
    for target, donor in INVISIBLE_OUTDOOR_FMAP_DONORS.items():
        src = assets / donor
        dst = assets / target
        if src.exists():
            shutil.copy2(src, dst)
            invisible_outdoor_copied.append({"target": target, "donor": donor, "bytes": dst.stat().st_size})
        else:
            missing.append({"target": target, "donor": donor})
    for target, donor in INVISIBLE_TRANSPARENT_FMAP_DONORS.items():
        src = assets / donor
        dst = assets / target
        if src.exists():
            shutil.copy2(src, dst)
            invisible_transparent_copied.append({"target": target, "donor": donor, "bytes": dst.stat().st_size})
        else:
            missing.append({"target": target, "donor": donor})
    for target, donor in VF3_TV_FMAP_DONORS.items():
        src = assets / donor
        dst = assets / target
        if src.exists():
            shutil.copy2(src, dst)
            invisible_transparent_copied.append({"target": target, "donor": donor, "bytes": dst.stat().st_size})
        else:
            missing.append({"target": target, "donor": donor})
    for item in manifest["items"]:
        reason = safety_fmap_reason(item)
        if not reason:
            continue
        target = Path(item["path"]).name + ".fmap"
        dst = assets / target
        if not dst.exists():
            missing.append({"target": target, "reason": "small_decor_safety_fmap_missing"})
            continue
        data = bytearray(dst.read_bytes())
        if len(data) < 0x30 or data[:4] != b"QAMF":
            missing.append({"target": target, "reason": "small_decor_safety_fmap_unrecognized"})
            continue
        content_start = 0x20
        content_end = len(data) - 0x10
        if content_end <= content_start:
            missing.append({"target": target, "reason": "small_decor_safety_fmap_has_no_grid"})
            continue
        before_cells = sum(
            1
            for offset in range(content_start, content_end, 4)
            if data[offset:offset + 4] != b"\x00\x00\x00\x00"
        )
        for offset in range(content_start, content_end):
            data[offset] = 0
        dst.write_bytes(data)
        sanitized.append({
            "target": target,
            "item_id": item["item_id"],
            "name": item["name"],
            "reason": reason,
            "bytes": len(data),
            "zeroed_range": [hex(content_start), hex(content_end)],
            "nonzero_grid_cells_before": before_cells,
        })
    manifest["behavior_assets"] = {
        "couch_fmap_donors": copied,
        "invisible_outdoor_fmap_donors": invisible_outdoor_copied,
        "invisible_transparent_fmap_donors": invisible_transparent_copied,
        "small_decor_sanitized_fmaps": sanitized,
        "missing": missing,
    }


def sync_vf3_tv_fmaps(manifest):
    """Create separate native fmaps from each VF3 TV's rendered footprint."""
    generated = []
    issues = []
    try:
        from PIL import Image

        for item in VF3_TV_ITEMS:
            png = OUT / "Images" / "Furniture" / f"{item['name']}.png"
            fmap = OUT / "Assets" / f"{item['name']}.png.fmap"
            donor = OUT / "Assets" / "TVFlatScreenStd.png.fmap"
            if not png.exists() or not donor.exists():
                issues.append({"item": item["short_description"], "reason": "missing png or donor fmap"})
                continue
            data = bytearray(donor.read_bytes())
            width, height = struct.unpack_from("<II", data, 24)
            grid_start = 32
            grid_end = grid_start + width * height * 4
            if data[:4] != b"QAMF" or grid_end + 16 != len(data):
                raise ValueError(f"unexpected TV fmap layout: {fmap}")
            # Build the selection cells directly from the first directional
            # sprite cell. Map coordinates are normalized to that cell, so
            # this stays limited to the visible TV rather than the full map.
            with Image.open(png).convert("RGBA") as image:
                frame_w = image.width // 2
                frame = image.crop((0, 0, frame_w, image.height))
                alpha = frame.getchannel("A")
                for y in range(height):
                    top = y * frame.height // height
                    bottom = (y + 1) * frame.height // height
                    for x in range(width):
                        left = x * frame.width // width
                        right = (x + 1) * frame.width // width
                        occupied = alpha.crop((left, top, right, bottom)).getbbox() is not None
                        struct.pack_into("<I", data, grid_start + (y * width + x) * 4, 0x003C0001 if occupied else 0)
            fmap.write_bytes(data)
            generated.append({"item": item["short_description"], "path": str(fmap), "grid": [width, height], "source": "normalized alpha footprint of the VF3 TV sprite"})
    except Exception as exc:
        issues.append({"reason": str(exc)})
    manifest["vf3_tv_fmaps"] = {"generated": generated, "issues": issues}


def normalize_added_furniture_sheets(manifest):
    normalized = []
    issues = []
    for item in manifest["items"]:
        path = OUT / "Images" / item["path"]
        frames = expected_furniture_frame_count(item["path"])
        if frames <= 1 or not path.exists():
            continue
        size = read_png_size(path)
        if not size:
            issues.append({
                "path": item["path"],
                "name": item["name"],
                "reason": "png_unreadable_or_missing",
            })
            continue
        width, height = size
        if item["path"] == "Furniture/FloweredLoveseat.png" and width < 160:
            try:
                from PIL import Image

                with Image.open(path).convert("RGBA") as image:
                    fixed = Image.new("RGBA", (width * frames, height), (0, 0, 0, 0))
                    for frame in range(frames):
                        fixed.paste(image, (frame * width, 0))
                    backup = path.with_name(path.name + ".pre-frame-duplicate.bak")
                    if not backup.exists():
                        shutil.copy2(path, backup)
                    fixed.save(path)
                normalized.append({
                    "path": item["path"],
                    "name": item["name"],
                    "frames": frames,
                    "old_size": [width, height],
                    "new_size": [width * frames, height],
                    "backup": str(backup),
                    "reason": "duplicated single VF3 loveseat sprite into a two-frame strip",
                })
                continue
            except Exception as exc:
                issues.append({
                    "path": item["path"],
                    "name": item["name"],
                    "reason": str(exc),
                })
                continue
        remainder = width % frames
        if remainder == 0:
            continue
        try:
            from PIL import Image

            with Image.open(path).convert("RGBA") as image:
                pad = frames - remainder
                fixed = Image.new("RGBA", (width + pad, height), (0, 0, 0, 0))
                fixed.paste(image, (0, 0))
                backup = path.with_name(path.name + ".pre-frame-pad.bak")
                if not backup.exists():
                    shutil.copy2(path, backup)
                fixed.save(path)
            normalized.append({
                "path": item["path"],
                "name": item["name"],
                "frames": frames,
                "old_size": [width, height],
                "new_size": [width + pad, height],
                "backup": str(backup),
            })
        except Exception as exc:
            issues.append({
                "path": item["path"],
                "name": item["name"],
                "frames": frames,
                "size": [width, height],
                "reason": str(exc),
            })
    manifest["furniture_sheet_normalization"] = {
        "normalized": normalized,
        "issues": issues,
        "note": "Pads added furniture sheets so descriptor frame counts divide evenly into the PNG width.",
    }


def patch_debug_features(manifest):
    obj = CoffObject(PATCHED / "theMainScene.obj")

    def insert_debug_input_hook(function_name, helper_name, arg_bytes, ret_bytes):
        symbol = obj.symbol(function_name)
        section = obj.section(symbol.section)
        raw = section.raw_ptr + symbol.value
        if obj.buf[raw:raw + 3] != b"\x55\x8B\xEC":
            raise RuntimeError(f"Unexpected prologue in {function_name}")
        insert_off = symbol.value + 3
        helper_sym = obj.append_undefined_symbol(helper_name)
        payload = bytearray()
        payload += b"\x51"  # push ecx ; preserve this
        for offset in reversed(arg_bytes):
            payload += b"\xFF\x75" + bytes([offset])
        payload += b"\xE8\x00\x00\x00\x00"
        payload += b"\x83\xC4" + bytes([len(arg_bytes) * 4])
        payload += b"\x59"  # pop ecx
        payload += b"\x84\xC0"  # test al,al
        payload += b"\x74\x04"  # je original body
        payload += b"\xB0\x01"  # mov al,1
        payload += b"\x5D"  # pop ebp
        payload += b"\xC2" + struct.pack("<H", ret_bytes)
        obj.insert_section_bytes(symbol.section, insert_off, bytes(payload))
        obj.append_relocation(symbol.section, insert_off + 2 + len(arg_bytes) * 3, helper_sym, IMAGE_REL_I386_REL32)
        return {"function": function_name, "helper": helper_name, "insert_offset": hex(insert_off)}

    def insert_main_scene_keydown_hook():
        function_name = "?HandleKeyDown@theMainScene@@IAE?B_NH@Z"
        symbol = obj.symbol(function_name)
        section = obj.section(symbol.section)
        raw = section.raw_ptr + symbol.value
        if obj.buf[raw:raw + 3] != b"\x55\x8B\xEC":
            raise RuntimeError(f"Unexpected prologue in {function_name}")
        insert_off = symbol.value + 3
        helper_sym = obj.append_undefined_symbol("_VF2PatchedMainSceneHandleKeyDown")
        payload = bytearray([
            0x51,                         # push ecx ; preserve this
            0xFF, 0x75, 0x08,             # push dword ptr [ebp+8] ; key
            0x51,                         # push ecx ; this for helper
            0xE8, 0, 0, 0, 0,             # call _VF2PatchedMainSceneHandleKeyDown
            0x83, 0xC4, 0x08,             # add esp, 8
            0x59,                         # pop ecx
            0x84, 0xC0,                   # test al,al
            0x74, 0x04,                   # je original body
            0xB0, 0x01,                   # mov al,1
            0x5D,                         # pop ebp
            0xC2, 0x04, 0x00,             # ret 4
        ])
        obj.insert_section_bytes(symbol.section, insert_off, bytes(payload))
        obj.append_relocation(symbol.section, insert_off + 6, helper_sym, IMAGE_REL_I386_REL32)
        return {"function": function_name, "helper": "_VF2PatchedMainSceneHandleKeyDown", "insert_offset": hex(insert_off)}

    draw_sym = obj.symbol("?DrawScene@theMainScene@@MAEXXZ")
    draw_helper_sym = obj.append_undefined_symbol("_VF2PatchedDrawOverlaysAndDebugger")
    obj.retarget_relocation(draw_sym.section, draw_sym.value + 0x149, draw_helper_sym, IMAGE_REL_I386_REL32)
    input_hooks = [
        insert_main_scene_keydown_hook(),
    ]
    obj.write(PATCHED / "theMainScene.obj")

    helper_cpp = r'''
#include <stdio.h>
#include <stdarg.h>
#include <excpt.h>

class ldwLog {
public:
    static ldwLog *Get();
    void WriteLine(char const *fmt, ...);
};

class IDebugger;

struct ldwPoint {
    int x;
    int y;
};

class CDebugger {
public:
    bool const Register(IDebugger *debugger);
    bool const HandleKeyDown(int key);
    void Draw();
};

class IEditor {
public:
    virtual void Draw();
    virtual void Reset();
    virtual void Activate(bool active);
    virtual bool const HandleKeyCharacter(char key);
    virtual bool const HandleKeyDown(int key);
    virtual bool const HandleKeyUp(int key);
    virtual bool const HandleMouseDown(ldwPoint point);
    virtual bool const HandleMouseMove(ldwPoint point);
    virtual bool const HandleMouseUp(ldwPoint point);
};

class CWaypointEditor : public IEditor {};
class CLightSourceEditor : public IEditor {};

class CFloatingAnim {
public:
    void DrawOverlays() const;
};

extern CDebugger Debugger;
extern CWaypointEditor WaypointEditor;
extern CLightSourceEditor LightSourceEditor;
extern CFloatingAnim FloatingAnim;

struct VF2DebuggerLayout {
    unsigned char visible;
    unsigned char pad0[3];
    IDebugger *providers[8];
    int providerCount;
    int selectedProvider;
    int drawX;
    int drawY;
};

static bool gVF2DebuggerInputEnabled = false;
static bool gVF2DebuggerFaulted = false;
static IDebugger *gVF2MainSceneDebuggerProvider = 0;

static void VF2WriteDirectDebug(char const *fmt, ...)
{
    FILE *f = fopen("vf2_additive_debug.txt", "a");
    if (!f) {
        return;
    }
    va_list args;
    va_start(args, fmt);
    vfprintf(f, fmt, args);
    va_end(args);
    fputc('\n', f);
    fclose(f);
}

static bool VF2CanUseDebugger()
{
    return gVF2DebuggerInputEnabled && !gVF2DebuggerFaulted;
}

static bool VF2IsDebuggerActivationKey(int key)
{
    return key == 0x74 || key == 0x4000003e;
}

static int VF2TranslateDebugKey(int key)
{
    if (VF2IsDebuggerActivationKey(key)) {
        return 0x3FE;
    }
    if (key == 0x26 || key == 0x40000052) {
        return 0x3EE;
    }
    if (key == 0x28 || key == 0x40000051) {
        return 0x3EF;
    }
    return key;
}

static void VF2DisableDebuggerAfterFault(char const *context)
{
    gVF2DebuggerFaulted = true;
    gVF2DebuggerInputEnabled = false;
    VF2WriteDirectDebug("debugger disabled after guarded exception in %s", context);
}

static void VF2EnsureDebugLogging()
{
    static bool initialized = false;
    if (initialized) {
        return;
    }
    initialized = true;
    VF2WriteDirectDebug("VF2 debugger input enabled by F5.");
    __try {
        ldwLog::Get()->WriteLine("VF2 additive build: debugger input enabled by F5.");
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2WriteDirectDebug("ldwLog unavailable while enabling debugger input.");
    }
}

static IEditor *VF2ActiveDebugEditor()
{
    if (!VF2CanUseDebugger()) {
        return 0;
    }
    IEditor *editor = 0;
    __try {
        VF2DebuggerLayout *state = reinterpret_cast<VF2DebuggerLayout *>(&Debugger);
        if (!state->visible || state->providerCount <= 0) {
            return 0;
        }
        int selected = state->selectedProvider;
        if (selected < 0 || selected >= state->providerCount || selected >= 8) {
            return 0;
        }
        IDebugger *provider = state->providers[selected];
        if (!provider || provider == gVF2MainSceneDebuggerProvider) {
            return 0;
        }
        editor = reinterpret_cast<IEditor *>(provider);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("VF2ActiveDebugEditor");
        return 0;
    }
    return editor;
}

static void VF2RegisterDebuggerProvider(IDebugger *provider, char const *label)
{
    VF2DebuggerLayout *state = reinterpret_cast<VF2DebuggerLayout *>(&Debugger);
    for (int i = 0; i < state->providerCount && i < 8; ++i) {
        if (state->providers[i] == provider) {
            return;
        }
    }
    if (Debugger.Register(provider)) {
        VF2WriteDirectDebug("registered debugger provider: %s", label);
    } else {
        VF2WriteDirectDebug("failed to register debugger provider: %s", label);
    }
}

static void VF2EnsureEditorDebuggers(void *mainScene)
{
    static bool registered = false;
    if (!VF2CanUseDebugger() || registered || !mainScene) {
        return;
    }
    __try {
        gVF2MainSceneDebuggerProvider = reinterpret_cast<IDebugger *>(static_cast<char *>(mainScene) + 8);
        VF2RegisterDebuggerProvider(gVF2MainSceneDebuggerProvider, "main scene");
        WaypointEditor.Activate(true);
        LightSourceEditor.Activate(true);
        VF2RegisterDebuggerProvider(reinterpret_cast<IDebugger *>(&WaypointEditor), "waypoint editor");
        VF2RegisterDebuggerProvider(reinterpret_cast<IDebugger *>(&LightSourceEditor), "light source editor");
        registered = true;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("VF2EnsureEditorDebuggers");
    }
}

static bool VF2SafeDebuggerHandleKeyDown(int key)
{
    bool handled = false;
    __try {
        handled = Debugger.HandleKeyDown(key);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("Debugger.HandleKeyDown");
        handled = false;
    }
    return handled;
}

static void VF2SafeDebuggerDraw()
{
    __try {
        Debugger.Draw();
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("Debugger.Draw");
    }
}

static bool VF2SafeEditorKeyCharacter(IEditor *editor, int key)
{
    bool handled = false;
    __try {
        handled = editor->HandleKeyCharacter(static_cast<char>(key));
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("IEditor.HandleKeyCharacter");
        handled = false;
    }
    return handled;
}

static bool VF2SafeEditorKeyDown(IEditor *editor, int key)
{
    bool handled = false;
    __try {
        handled = editor->HandleKeyDown(key);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("IEditor.HandleKeyDown");
        handled = false;
    }
    return handled;
}

static bool VF2SafeEditorKeyUp(IEditor *editor, int key)
{
    bool handled = false;
    __try {
        handled = editor->HandleKeyUp(key);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("IEditor.HandleKeyUp");
        handled = false;
    }
    return handled;
}

static bool VF2SafeEditorMouseDown(IEditor *editor, ldwPoint point)
{
    bool handled = false;
    __try {
        handled = editor->HandleMouseDown(point);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("IEditor.HandleMouseDown");
        handled = false;
    }
    return handled;
}

static bool VF2SafeEditorMouseMove(IEditor *editor, ldwPoint point)
{
    bool handled = false;
    __try {
        handled = editor->HandleMouseMove(point);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("IEditor.HandleMouseMove");
        handled = false;
    }
    return handled;
}

static bool VF2SafeEditorMouseUp(IEditor *editor, ldwPoint point)
{
    bool handled = false;
    __try {
        handled = editor->HandleMouseUp(point);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        VF2DisableDebuggerAfterFault("IEditor.HandleMouseUp");
        handled = false;
    }
    return handled;
}

extern "C" bool __cdecl VF2PatchedMainSceneHandleKeyDown(void *mainScene, int key)
{
    bool activating = VF2IsDebuggerActivationKey(key);
    if (!gVF2DebuggerInputEnabled && !activating) {
        return false;
    }
    if (gVF2DebuggerFaulted) {
        return false;
    }
    if (activating) {
        gVF2DebuggerInputEnabled = true;
    }
    VF2EnsureDebugLogging();
    VF2EnsureEditorDebuggers(mainScene);
    if (!VF2CanUseDebugger()) {
        return false;
    }
    int translated = VF2TranslateDebugKey(key);
    VF2WriteDirectDebug("main scene keydown raw=%d translated=%d", key, translated);
    if (VF2SafeDebuggerHandleKeyDown(translated)) {
        return true;
    }
    IEditor *editor = VF2ActiveDebugEditor();
    return editor ? VF2SafeEditorKeyDown(editor, key) : false;
}

extern "C" bool __cdecl VF2PatchedDebuggerKeyCharacter(int key)
{
    if (!VF2CanUseDebugger()) {
        return false;
    }
    IEditor *editor = VF2ActiveDebugEditor();
    return editor ? VF2SafeEditorKeyCharacter(editor, key) : false;
}

extern "C" bool __cdecl VF2PatchedDebuggerKeyUp(int key)
{
    if (!VF2CanUseDebugger()) {
        return false;
    }
    IEditor *editor = VF2ActiveDebugEditor();
    return editor ? VF2SafeEditorKeyUp(editor, key) : false;
}

extern "C" bool __cdecl VF2PatchedDebuggerMouseDown(int x, int y)
{
    if (!VF2CanUseDebugger()) {
        return false;
    }
    IEditor *editor = VF2ActiveDebugEditor();
    ldwPoint point = {x, y};
    return editor ? VF2SafeEditorMouseDown(editor, point) : false;
}

extern "C" bool __cdecl VF2PatchedDebuggerMouseMove(int x, int y)
{
    if (!VF2CanUseDebugger()) {
        return false;
    }
    IEditor *editor = VF2ActiveDebugEditor();
    ldwPoint point = {x, y};
    return editor ? VF2SafeEditorMouseMove(editor, point) : false;
}

extern "C" bool __cdecl VF2PatchedDebuggerMouseUp(int x, int y)
{
    if (!VF2CanUseDebugger()) {
        return false;
    }
    IEditor *editor = VF2ActiveDebugEditor();
    ldwPoint point = {x, y};
    return editor ? VF2SafeEditorMouseUp(editor, point) : false;
}

extern "C" void __cdecl VF2PatchedDrawOverlaysAndDebugger()
{
    FloatingAnim.DrawOverlays();
    if (VF2CanUseDebugger()) {
        VF2SafeDebuggerDraw();
    }
}
'''.strip() + "\n"
    (PATCHED / "vf2_debug_features.cpp").write_text(helper_cpp, encoding="ascii")
    manifest["debug_features"] = {
        "ldw_log": {
            "status": "enabled after debugger activation",
            "filename": "ldwLog.txt",
            "mechanism": "ldwLog::Get()->WriteLine when F5 enables debugger input",
        },
        "developer_keys": {
            "status": "F5-gated with guarded debugger/editor calls",
            "patched_function": "?HandleKeyDown@theMainScene@@IAE?B_NH@Z",
            "helper": "_VF2PatchedMainSceneHandleKeyDown",
            "activation_key": "F5",
            "vanilla_play": "helpers return false without touching Debugger/editor globals until F5 is pressed, then the original handler falls through when unhandled",
            "draw_hook": "?DrawScene@theMainScene@@MAEXXZ + 0x149",
            "input_hooks": input_hooks,
            "direct_debug_log": "vf2_additive_debug.txt",
            "fault_guard": "SEH guards disable debugger input and fall through to stock input after a debugger/editor access violation",
            "known_debugger_keys": {
                "F5": "enable debugger input and toggle CDebugger overlay",
                "Up": "next debugger page",
                "Down": "previous debugger page",
                "F4": "handled by selected editor when supported",
            },
            "skipped_hooks": [
                {
                    "function": "?HandleKeyUp@theMainScene@@IAE?B_NH@Z",
                    "reason": "stock function is a tiny return-false stub without a patchable prologue",
                },
                {
                    "function": "?HandleKeyCharacter@theMainScene@@IAE?B_ND@Z",
                    "reason": "left stock to reduce debugger surface area in opt-in builds",
                },
                {
                    "function": "?HandleMouseDown@theMainScene@@IAE?B_NUldwPoint@@@Z",
                    "reason": "left stock after B61/B62 mouse-path crashes",
                },
                {
                    "function": "?HandleMouseMove@theMainScene@@IAE?B_NUldwPoint@@@Z",
                    "reason": "left stock after B58-B62 save-load and mouse-path crashes",
                },
                {
                    "function": "?HandleMouseUp@theMainScene@@IAE?B_NUldwPoint@@@Z",
                    "reason": "left stock after B61/B62 mouse-path crashes",
                }
            ],
            "registered_providers": [
                "main scene debugger",
                "CWaypointEditor global",
                "CLightSourceEditor global",
            ],
            "unavailable_in_this_object_set": [
                "BehaviorEditor.obj has no exported behavior editor class/object methods",
                "ContentMapEditor.obj has no exported content-map editor class/object methods",
                "Editor.obj has no exported editor class/object methods",
            ],
        },
    }


def write_disabled_debug_features(manifest):
    (PATCHED / "vf2_debug_features.cpp").write_text(
        "/* Debugger hooks are disabled for normal builds. */\n",
        encoding="ascii",
    )
    manifest["debug_features"] = {
        "status": "disabled",
        "reason": "B61/B62 debugger hooks crashed during save-load and mouse input testing.",
        "normal_gameplay": "theMainScene key, draw, mouse down, mouse move, and mouse up handlers remain stock.",
        "opt_in": "Set VF2_ENABLE_DEBUGGER_FEATURES=1 only for isolated debugger research builds.",
    }


def patch_plan_logging(manifest):
    obj = CoffObject(PATCHED / "VillagerPlans.obj")
    add_plan_sym = obj.symbol("?AddPlan@CVillagerPlans@@AAEXUSActionPlan@1@W4EPriority@@@Z")
    sec = obj.section(add_plan_sym.section)
    start = sec.raw_ptr + add_plan_sym.value
    if obj.buf[start:start + 3] != b"\x55\x8B\xEC":
        raise ValueError("Unexpected CVillagerPlans::AddPlan prologue")

    # Insert after the normal function prologue so EBP-based argument offsets
    # are stable. This logs every queued villager plan, then execution falls
    # through into the original AddPlan body unchanged.
    insert_off = add_plan_sym.value + 3
    payload = bytearray([
        0x51,                         # push ecx ; preserve this
        0x8D, 0x45, 0x08,             # lea eax, [ebp+8] ; SActionPlan*
        0xFF, 0x75, 0x4C,             # push dword ptr [ebp+4Ch] ; priority
        0x50,                         # push eax ; plan
        0x51,                         # push ecx ; CVillagerPlans*
        0xE8, 0, 0, 0, 0,             # call _VF2LogAddPlan
        0x83, 0xC4, 0x0C,             # add esp, 0Ch
        0x59,                         # pop ecx
    ])
    obj.insert_section_bytes(add_plan_sym.section, insert_off, payload)
    helper_sym = obj.append_undefined_symbol("_VF2LogAddPlan")
    obj.append_relocation(add_plan_sym.section, insert_off + 10, helper_sym, IMAGE_REL_I386_REL32)
    obj.write(PATCHED / "VillagerPlans.obj")

    helper_cpp = r'''
#include <stdio.h>
#include <stdarg.h>

class ldwLog {
public:
    static ldwLog *Get();
    void WriteLine(char const *fmt, ...);
};

static void VF2WriteDirectPlanLog(char const *fmt, ...)
{
    FILE *f = fopen("vf2_plan_log.txt", "a");
    if (!f) {
        return;
    }
    va_list args;
    va_start(args, fmt);
    vfprintf(f, fmt, args);
    va_end(args);
    fputc('\n', f);
    fclose(f);
}

static unsigned int VF2ReadPlanWord(unsigned int const *plan, int index)
{
    __try {
        return plan[index];
    } __except (1) {
        return 0xFFFFFFFFu;
    }
}

extern "C" void __cdecl VF2LogAddPlan(void *plans, unsigned int const *plan, int priority)
{
    unsigned int w0 = VF2ReadPlanWord(plan, 0);
    unsigned int w1 = VF2ReadPlanWord(plan, 1);
    unsigned int w2 = VF2ReadPlanWord(plan, 2);
    unsigned int w3 = VF2ReadPlanWord(plan, 3);
    unsigned int w4 = VF2ReadPlanWord(plan, 4);
    unsigned int w5 = VF2ReadPlanWord(plan, 5);
    unsigned int w6 = VF2ReadPlanWord(plan, 6);
    unsigned int w7 = VF2ReadPlanWord(plan, 7);
    unsigned int w8 = VF2ReadPlanWord(plan, 8);
    unsigned int w9 = VF2ReadPlanWord(plan, 9);
    unsigned int w10 = VF2ReadPlanWord(plan, 10);
    unsigned int w11 = VF2ReadPlanWord(plan, 11);
    unsigned int w12 = VF2ReadPlanWord(plan, 12);
    unsigned int w13 = VF2ReadPlanWord(plan, 13);
    unsigned int w14 = VF2ReadPlanWord(plan, 14);
    unsigned int w15 = VF2ReadPlanWord(plan, 15);
    unsigned int w16 = VF2ReadPlanWord(plan, 16);

    VF2WriteDirectPlanLog(
        "AddPlan plans=%p priority=%d raw=%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X",
        plans, priority,
        w0, w1, w2, w3, w4, w5, w6, w7, w8, w9, w10, w11, w12, w13, w14, w15, w16);

    ldwLog::Get()->WriteLine(
        "AddPlan plans=%p priority=%d raw=%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X",
        plans, priority,
        w0, w1, w2, w3, w4, w5, w6, w7, w8, w9, w10, w11, w12, w13, w14, w15, w16);
}
'''.strip() + "\n"
    (PATCHED / "vf2_plan_logger.cpp").write_text(helper_cpp, encoding="ascii")
    manifest["plan_logging"] = {
        "status": "instrumented",
        "patched_function": "?AddPlan@CVillagerPlans@@AAEXUSActionPlan@1@W4EPriority@@@Z",
        "insert_offset": hex(insert_off),
        "helper": "_VF2LogAddPlan",
        "ldw_log_message": "AddPlan plans=%p priority=%d raw=...",
        "direct_debug_log": "vf2_plan_log.txt",
        "note": "Logs every SActionPlan inserted into CVillagerPlans without replacing the original AddPlan implementation.",
    }


def patch_spontaneous_behaviors(manifest):
    """Enable native object behaviors in VF2's actual AI candidate table."""
    obj = CoffObject(PATCHED / "Villager.obj")
    init_ai = obj.symbol("?InitAI@CVillager@@QAEXXZ")
    sec = obj.section(init_ai.section)
    epilogue = init_ai.value + 0x4513
    raw_epilogue = sec.raw_ptr + epilogue
    expected = b"\x5F\x5E\x5B\x8B\xE5\x5D\xC3"
    if obj.buf[raw_epilogue:raw_epilogue + len(expected)] != expected:
        raise ValueError("Unexpected CVillager::InitAI epilogue")

    # InitAI has finished constructing and randomizing every stock candidate
    # before this epilogue. The detour only enables the listed existing
    # behavior IDs; it does not alter the Bored routine or replace any macro.
    helper_off = sec.raw_size
    helper = bytearray([
        0xFF, 0x75, 0xFC,             # push dword ptr [ebp-4] ; CVillager*
        0xE8, 0, 0, 0, 0,             # call _VF2EnableAutonomousCandidates
        0x83, 0xC4, 0x04,             # add esp, 4
        0x5F,                         # pop edi
        0x5E,                         # pop esi
        0x5B,                         # pop ebx
        0x8B, 0xE5,                   # mov esp, ebp
        0x5D,                         # pop ebp
        0xC3,                         # ret
    ])
    obj.insert_section_bytes(sec.index, helper_off, bytes(helper))
    helper_sym = obj.append_undefined_symbol("_VF2EnableAutonomousCandidates")
    obj.append_relocation(sec.index, helper_off + 4, helper_sym, IMAGE_REL_I386_REL32)

    # LoadAI initializes the same table, then restores saved selection weights.
    # Run the same additive enabler after either stock LoadAI return path so an
    # existing household receives the new choices on its next load.
    load_ai = obj.symbol("?LoadAI@CVillager@@QAEXAAUSSaveState@1@@Z")
    sec = obj.section(load_ai.section)
    load_section_index = sec.index
    load_epilogues = (load_ai.value + 0x53, load_ai.value + 0x94)
    load_expected = b"\x5F\x5E\x5D\xC2\x04\x00"
    for offset in load_epilogues:
        raw = sec.raw_ptr + offset
        if obj.buf[raw:raw + len(load_expected)] != load_expected:
            raise ValueError("Unexpected CVillager::LoadAI epilogue")

    load_helper_off = sec.raw_size
    load_helper = bytearray([
        0x57,                         # push edi ; CVillager*
        0xE8, 0, 0, 0, 0,             # call _VF2EnableAutonomousCandidates
        0x83, 0xC4, 0x04,             # add esp, 4
        0x5F,                         # pop edi
        0x5E,                         # pop esi
        0x5D,                         # pop ebp
        0xC2, 0x04, 0x00,             # ret 4
    ])
    obj.insert_section_bytes(sec.index, load_helper_off, bytes(load_helper))
    obj.append_relocation(sec.index, load_helper_off + 2, helper_sym, IMAGE_REL_I386_REL32)

    init_sec = obj.section(init_ai.section)
    raw_epilogue = init_sec.raw_ptr + epilogue
    rel = struct.pack("<i", helper_off - (epilogue + 5))
    obj.buf[raw_epilogue:raw_epilogue + len(expected)] = b"\xE9" + rel + b"\x90\x90"
    load_sec = obj.section(load_section_index)
    for offset in load_epilogues:
        raw = load_sec.raw_ptr + offset
        rel = struct.pack("<i", load_helper_off - (offset + 5))
        obj.buf[raw:raw + len(load_expected)] = b"\xE9" + rel + b"\x90"
    obj.write(PATCHED / "Villager.obj")

    # Candidate configuration happens at family load, but weather can change
    # while the household is running.  Refresh the hammock candidate at the
    # start of every native decision pass so it is only considered in neutral
    # or sunny weather.
    ai_obj = CoffObject(PATCHED / "VillagerAI.obj")
    decide = ai_obj.symbol("?DecideWhatToDo@CVillagerAI@@AAEXAAVCVillager@@@Z")
    ai_sec = ai_obj.section(decide.section)
    refresh_insert = decide.value + 0x1E
    raw_refresh = ai_sec.raw_ptr + refresh_insert
    if ai_obj.buf[raw_refresh:raw_refresh + 5] != b"\xE8\x00\x00\x00\x00":
        raise ValueError("Unexpected CVillagerAI::DecideWhatToDo refresh site")
    refresh_helper = ai_obj.append_undefined_symbol("_VF2RefreshHammockEligibility")
    refresh_payload = bytes([
        0x56,                         # push esi ; CVillager*
        0xE8, 0, 0, 0, 0,             # call _VF2RefreshHammockEligibility
        0x83, 0xC4, 0x04,             # add esp, 4
    ])
    ai_obj.insert_section_bytes(ai_sec.index, refresh_insert, refresh_payload)
    ai_obj.append_relocation(ai_sec.index, refresh_insert + 2, refresh_helper, IMAGE_REL_I386_REL32)
    ai_obj.write(PATCHED / "VillagerAI.obj")

    helper_cpp = r'''
// CVillager::InitAI owns the real autonomous candidate table. Each candidate
// is 0xD0 bytes; +0xCD is its enabled flag and +0x0C its random-choice weight.
// These IDs are existing VF2 behavior macros, so their native object search,
// walking, animation, sounds, and failure handling remain unchanged.
static void EnableAutonomousCandidate(unsigned char *villager, unsigned int behavior)
{
    unsigned char *candidate = villager + 0x6BB8 + behavior * 0xD0;
    candidate[0xCD] = 1;
    *(unsigned int *)(candidate + 0x0C) = 3000;
}

static void EnableAllAgesAutonomousCandidate(unsigned char *villager, unsigned int behavior)
{
    unsigned char *candidate = villager + 0x6BB8 + behavior * 0xD0;
    candidate[0xCD] = 1;
    *(unsigned int *)(candidate + 0x0C) = 3000;
    *(unsigned int *)(candidate + 0x48) = 0;
    *(unsigned int *)(candidate + 0x4C) = 0;
}

static void EnableChildOnlyAutonomousCandidate(unsigned char *villager, unsigned int behavior)
{
    unsigned char *candidate = villager + 0x6BB8 + behavior * 0xD0;
    candidate[0xCD] = 1;
    *(unsigned int *)(candidate + 0x0C) = 3000;
    *(unsigned int *)(candidate + 0x48) = 0x117;
    *(unsigned int *)(candidate + 0x4C) = 0;
}

class CWeather {
public:
    int currentType;
};

extern CWeather Weather;

extern "C" void __cdecl VF2RefreshHammockEligibility(void *villager)
{
    unsigned char *data = (unsigned char *)villager;
    unsigned char *candidate = data + 0x6BB8 + 0x023 * 0xD0;
    const int weatherAllowsHammock = Weather.currentType == 0 || Weather.currentType == 1;
    candidate[0xCD] = (unsigned char)weatherAllowsHammock;
    *(unsigned int *)(candidate + 0x0C) = weatherAllowsHammock ? 3000 : 0;
    *(unsigned int *)(candidate + 0x48) = 0;
    *(unsigned int *)(candidate + 0x4C) = 0;
}

class CVillager;
extern "C" void __cdecl VF2RandomBookshelfReading(CVillager &);
class CBehavior {
private:
    static void __cdecl ReadMagazine(CVillager &);
    static void __cdecl ReadingBook(CVillager &);
    friend void __cdecl VF2RandomBookshelfReading(CVillager &);
};

class ldwGameState {
public:
    static int __cdecl GetRandom(int);
};

extern "C" void __cdecl VF2RandomBookshelfReading(CVillager &villager)
{
    if (ldwGameState::GetRandom(2) == 0) {
        CBehavior::ReadMagazine(villager);
    } else {
        CBehavior::ReadingBook(villager);
    }
}

extern "C" void __cdecl VF2EnableAutonomousCandidates(void *villager)
{
    unsigned char *data = (unsigned char *)villager;
    EnableAllAgesAutonomousCandidate(data, 0x095); // WatchingFirePlace
    EnableAllAgesAutonomousCandidate(data, 0x0E8); // WarmingHands
    EnableAllAgesAutonomousCandidate(data, 0x0DC); // PlayingPinballGames
    EnableAllAgesAutonomousCandidate(data, 0x0DD); // PlayingPinball
    EnableAllAgesAutonomousCandidate(data, 0x0DE); // PlayingSlots
    EnableAllAgesAutonomousCandidate(data, 0x0DF); // PlayingPachinko
    EnableAllAgesAutonomousCandidate(data, 0x099); // PlayingPooltable
    EnableAllAgesAutonomousCandidate(data, 0x096); // PlayingFoosball
    EnableChildOnlyAutonomousCandidate(data, 0x11E); // PlayOnPlayStructure / Playhouse
    EnableAutonomousCandidate(data, 0x0ED); // DancingRadio
    EnableAutonomousCandidate(data, 0x0F5); // ListenToRadio
    EnableAutonomousCandidate(data, 0x118); // DrawingOnEasel
    VF2RefreshHammockEligibility(data);
}
'''.strip() + "\n"
    (PATCHED / "vf2_spontaneous_behaviors.cpp").write_text(helper_cpp, encoding="ascii")
    manifest["spontaneous_behaviors"] = {
        "status": "enabled through the autonomous AI candidate table",
        "hooks": ["CVillager::InitAI", "CVillager::LoadAI", "CVillagerAI::DecideWhatToDo"],
        "selection": "existing weighted CVillagerAI::DecideWhatToDo selection; weight 3000 per enabled candidate",
        "actions": ["hammock (all ages; neutral/sunny only)", "warm hands by fireplace (all ages)", "watch fireplace (all ages)", "pinball (all ages)", "slots (all ages)", "pachinko (all ages)", "pool (all ages)", "foosball (all ages)", "playhouse (children only; max age 0x117)", "listen to radio", "dance to radio", "drawing"],
        "note": "No Bored hook. The patch enables existing native behavior candidates after stock InitAI and after saved weights are restored by LoadAI. The hammock candidate is refreshed at each native AI decision and is eligible only in weather states 0 (neutral) and 1 (sunny). Playhouse is capped at the stock child boundary, where CVillager+0x6A54 < 0x118 is child and >= 0x118 is adult.",
    }


def patch_bookshelf_reading_behavior(manifest):
    """Randomize the stock bookshelf-drop route between the native readers."""
    obj = CoffObject(PATCHED / "Behavior.obj")
    ctor = obj.symbol("??0CBehavior@@QAE@XZ")
    sec = obj.section(ctor.section)
    relocation_vaddr = ctor.value + 0x299
    expected = b"\x68\x00\x00\x00\x00\x6A\x33"
    raw = sec.raw_ptr + ctor.value + 0x298
    if obj.buf[raw:raw + len(expected)] != expected:
        raise ValueError("Unexpected ReadMagazine behavior macro entry")
    random_reader = obj.append_undefined_symbol("_VF2RandomBookshelfReading")
    obj.retarget_relocation(sec.index, relocation_vaddr, random_reader)
    obj.write(PATCHED / "Behavior.obj")
    manifest["bookshelf_drop_behavior"] = {
        "status": "stock bookshelf dispatch calls a random native reader",
        "old_behavior": "0x33 ReadMagazine",
        "new_behavior": "random choice: ReadMagazine or ReadingBook",
        "scope": "the native bookshelf drop route; no furniture records or fmaps changed",
    }


def patch_arcade_behavior_labels(manifest):
    """Give pachinko and pinball their own labels without changing shared text."""
    obj = CoffObject(PATCHED / "Behavior.obj")
    patches = [
        ("?PlayingPachinko@CBehavior@@CAXAAVCVillager@@@Z", behavior_label_string_id_for(0), "Playing pachinko"),
        ("?PlayingPinball@CBehavior@@CAXAAVCVillager@@@Z", behavior_label_string_id_for(1), "Playing pinball"),
    ]
    changed = []
    for symbol_name, string_id, text in patches:
        symbol = obj.symbol(symbol_name)
        sec = obj.section(symbol.section)
        raw = sec.raw_ptr + symbol.value + 0x51
        expected = b"\x68\x5D\x02\x00\x00"
        if obj.buf[raw:raw + len(expected)] != expected:
            raise ValueError(f"Unexpected shared Playing string in {symbol_name}")
        obj.buf[raw + 1:raw + 5] = struct.pack("<I", string_id)
        changed.append({"behavior": symbol_name, "string_id": hex(string_id), "text": text})
    obj.write(PATCHED / "Behavior.obj")
    manifest["arcade_behavior_labels"] = changed


def restore_supplied_game_table_sprites(manifest):
    """Use the user-supplied original-size pool and foosball sheets verbatim."""
    source_root = Path(r"C:\Users\Owner\Downloads\Virtual Families 2 - Copy Official\Images\Furniture")
    copied = []
    missing = []
    for filename in ("PoolTableStd.png", "FoosballTableStd.png"):
        source = source_root / filename
        target = OUT / "Images" / "Furniture" / filename
        if source.exists():
            shutil.copy2(source, target)
            copied.append({"file": filename, "bytes": target.stat().st_size})
        else:
            missing.append(filename)
    manifest["restored_game_table_sprites"] = {"copied": copied, "missing": missing}


def patch_options_dialog(manifest):
    obj = CoffObject(PATCHED / "theOptionsDialog.obj")
    ctor_sym = obj.symbol("??0theOptionsDialog@@QAE@PADW4DialogColorEnum@@@Z")
    sec = obj.section(ctor_sym.section)
    start = sec.raw_ptr + ctor_sym.value

    # Desktop already contains an Evict button and handler, but constructor
    # branches only build the button before generation 2. Keep the button
    # available for every active generation, while still hiding it when the
    # family tree has already been cleared.
    expected_1 = bytes([0x0F, 0x85, 0x80, 0x00, 0x00, 0x00])
    expected_generation_cmp = bytes([0x83, 0x3D, 0x04, 0x00, 0x00, 0x00, 0x02])
    expected_2 = bytes([0x7D, 0x77])
    if obj.buf[start + 0x2DA:start + 0x2E0] != expected_1:
        raise ValueError("Unexpected Evict first skip branch bytes")
    if obj.buf[start + 0x2E0:start + 0x2E7] != expected_generation_cmp:
        raise ValueError("Unexpected Evict generation compare bytes")
    if obj.buf[start + 0x2E7:start + 0x2E9] != expected_2:
        raise ValueError("Unexpected Evict second skip branch bytes")
    obj.buf[start + 0x2DA:start + 0x2E0] = b"\x90" * 6
    obj.buf[start + 0x2E6] = 0
    obj.buf[start + 0x2E7:start + 0x2E9] = b"\x7E\x77"
    obj.write(PATCHED / "theOptionsDialog.obj")

    manifest["settings_menu"] = {
        "evict": {
            "status": "available for every active family generation",
            "button_control_id": 4,
            "label_string_id": "0x10",
            "confirmation_string_id": "0x11",
            "handler": "?EvictFamily@theOptionsDialog@@AAEXXZ",
            "family_tree_handler": "?EvictFamily@CFamilyTree@@QAEXXZ",
            "click_safety": "CFamilyTree::EvictFamily is generation-agnostic: Reset(), then mark tree evicted; constructor guard hides the button when generation count is 0.",
            "constructor_patches": [
                {
                    "offset": "0x2DA",
                    "expected_original_bytes": expected_1.hex(),
                    "replacement_bytes": ("90" * 6),
                    "note": "ignore the evicted-flag branch so active later generations can reach the generation-count guard",
                },
                {
                    "offset": "0x2E0",
                    "expected_original_bytes": expected_generation_cmp.hex(),
                    "replacement_bytes": "833d0400000000",
                    "note": "change generation compare from < 2 to active-family count > 0",
                },
                {
                    "offset": "0x2E7",
                    "expected_original_bytes": expected_2.hex(),
                    "replacement_bytes": "7e77",
                    "note": "skip Evict only when generation count is <= 0",
                },
            ],
        }
    }


def patch_added_furniture_click_aliases(manifest):
    """Extend HandleMouseDown's native lookup table for appended furniture."""
    obj = CoffObject(PATCHED / "FurnitureManager.obj")
    sym = obj.symbol("?HandleMouseDown@CFurnitureManager@@QAE_NUldwPoint@@@Z")
    sec = obj.section(sym.section)
    guard_off = sym.value + 0xE3
    raw_guard = sec.raw_ptr + guard_off
    if obj.buf[raw_guard:raw_guard + 5] != b"\x3D\xC0\x00\x00\x00":
        raise ValueError("Unexpected HandleMouseDown lookup bound")
    table_sym = obj.symbol("$LN54")
    if table_sym.section != sym.section or table_sym.value + 0xC1 != sec.raw_size:
        raise ValueError("Unexpected HandleMouseDown native lookup-table layout")

    max_offset = max(item_id_for(idx) - 0x1AD for idx in range(len(ITEMS)))
    old_count = 0xC1
    new_count = max_offset + 1
    obj.insert_section_bytes(sec.index, sec.raw_size, b"\0" * (new_count - old_count))
    sec = obj.section(sym.section)
    table_raw = sec.raw_ptr + table_sym.value
    aliases = []
    aliases = []
    for idx, (_name, donor_id, _list, _path) in enumerate(ITEMS):
        added_id = item_id_for(idx)
        added_offset = added_id - 0x1AD
        donor_offset = donor_id - 0x1AD
        obj.buf[table_raw + added_offset] = obj.buf[table_raw + donor_offset]
        aliases.append({"item": _name, "item_id": hex(added_id), "donor_item": hex(donor_id)})
    struct.pack_into("<I", obj.buf, sec.raw_ptr + guard_off + 1, max_offset)
    obj.write(PATCHED / "FurnitureManager.obj")
    manifest["clickable_added_furniture"] = {
        "status": "native mouse-dispatch table extended with donor case bytes",
        "route": "stock donor lookup case; no detour or generic replacement path",
        "stock_furniture_dispatch": "unmodified",
        "old_lookup_count": old_count,
        "new_lookup_count": new_count,
        "items": aliases,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    copy_obj_tree()
    manifest = {
        "native_array_contract": build_native_array_contract(),
        "items": [
            {
                "name": name,
                "item_id": hex(item_id_for(i)),
                "image_id": hex(image_id_for(i)),
                "donor_item": hex(donor),
                "list": list_name,
                "path": path,
                "mobile_data": MOBILE_DATA_BY_PATH[path],
            }
            for i, (name, donor, list_name, path) in enumerate(ITEMS)
        ]
    }
    patch_furniture_manager(manifest)
    patch_added_furniture_click_aliases(manifest)
    patch_visible_special_upgrades(manifest)
    patch_inventory_manager(manifest)
    patch_scrolling_store_scene(manifest)
    patch_purchase_dialog(manifest)
    patch_options_dialog(manifest)
    write_outfit_store_helpers(manifest)
    patch_tool_tray_outfit_normalization(manifest)
    patch_string_manager(manifest)
    patch_special_upgrade_titles(manifest)
    patch_achievement_holiday_ornaments(manifest)
    patch_collectable_item_holiday_ornaments(manifest)
    patch_collection_scene_holiday_ornaments(manifest)
    patch_spontaneous_behaviors(manifest)
    patch_bookshelf_reading_behavior(manifest)
    if ENABLE_DEBUGGER_FEATURES:
        patch_debug_features(manifest)
    else:
        write_disabled_debug_features(manifest)
    if ENABLE_ISLAND_EVENTS:
        patch_island_events(manifest)
    else:
        # The legacy linker response contains the event helper object even
        # while grafted mobile events are disabled for stability.
        (PATCHED / "vf2_island_events.cpp").write_text(
            'extern "C" void __cdecl VF2RegisterMobileIslandEvents(void **) {}\n',
            encoding="ascii",
        )
        manifest["IslandEvents"] = {
            "added": [],
            "status": "disabled because the additive event object graft crashes the game",
        }
    if ENABLE_HOLIDAY_BODY_TYPES:
        sync_original_villager_sprite_sheets(manifest)
        sync_holiday_body_runtime_frames(manifest)
    else:
        sync_original_villager_sprite_sheets(manifest)
    sync_outfit_store_icon_art(manifest)
    sync_visible_special_upgrade_icon_art(manifest)
    sync_holiday_ornament_collection_art(manifest)
    patch_graphics_manager(manifest)
    patch_floating_anim_table(manifest)
    if ENABLE_HOLIDAY_BODY_TYPES:
        write_holiday_body_draw_helper(manifest)
        patch_holiday_body_draw_redirect(manifest)
    sync_generation_lock_art(manifest)
    sync_vf3_living_room_sprite_strips(manifest)
    sync_vf3_tv_sprite_strips(manifest)
    sync_vf3_tv_animation_sheets(manifest)
    sync_invisible_outdoor_sprites(manifest)
    sync_transparent_base_furniture_sprites(manifest)
    sync_invisible_furniture_reference_sets(manifest)
    if ENABLE_HOLIDAY_BODY_TYPES:
        sync_separated_villager_sheets(manifest)
        manifest["holiday_body_types"] = {
            "status": "folder-backed runtime renderer enabled",
            "body_values": list(HOLIDAY_BODY_VALUES),
            "source_sets": list(HOLIDAY_BODY_SET_IDS),
            "spritesheets": "not expanded; original sheets remain fallback",
        }
        manifest["holiday_body_lookup"] = {
            "status": "not patched; native animator stays stock and the body draw hook handles values 50-53",
        }
    else:
        manifest["holiday_body_types"] = {
            "status": "disabled; stock body rows 0-49 retained",
            "reason": "B54 restores base-game villager body behavior",
        }
        manifest["holiday_body_lookup"] = {
            "status": "not patched; stock animator body-row clamp retained",
        }
    sync_behavior_assets(manifest)
    sync_vf3_tv_fmaps(manifest)
    restore_supplied_game_table_sprites(manifest)
    normalize_added_furniture_sheets(manifest)
    write_internal_workings_summary(manifest)
    (OUT / "patch-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
