"""R Refreshes the Store: sites in the B200 Virtual Families 2 executable (core variant).

Single source of truth for every address the companion DLL vf2refresh_b200.dll touches or relies on. Every
pin is the exact bytes of the B200 link output (`Virtual Families 2 - B200.exe`, core variant, built by
work/patch_mobile_furniture_pack.py); the DLL, the generator and the tests refuse an executable that is not
that build at these places.

The B200 image is relocated (DYNAMICBASE, .reloc) and each of the 32 matrix variants links to different
addresses, so the DLL holds no game address. It searches the live image for each pinned run (relocated
fields and call/jmp displacements are wildcards) and derives every address from where the runs were found.
runtime/tools/gen_b200_refresh_sites.py proves the derivation on the core variant and on every other
executable it is given.

What the DLL does (one write at install, a vtable slot):

* CScrollingStoreScene's HandleKey (vtable slot 2, the slot ldwEventManager::HandleKey calls with
  (type, code, sym)) is the identical-code-folded body every simple scene shares: type 6 and code 3E8h
  (Esc) -> HandleMessage(8, 1). The function is shared by five vtables, so the DLL never touches the
  function; it finds the STORE's vtable through its RTTI (".?AVCScrollingStoreScene@@" -> the complete
  object locator at offset 0 -> the one vtable that points to it) and replaces that one slot. The other
  scenes keep their own pointer to the shared body.
* A typed character arrives as type 5 (ldwGameWindowImpl::CheckForEvents: SDL_TEXTINPUT -> HandleKey(5,
  char, 0)), so R and Shift+R / Caps Lock R are 72h and 52h. On the Clothing and Hairstyles page (the store
  category field [scene+0D4h], written by SetStoreCategory, is 0Dh) the DLL calls the game's own
  CInventoryManager::MaybeUpdateOutfits(true), the forced draw CInventoryManager::Reset makes for a new
  family. It picks the six stock outfit rows again with the game's own GenCommonBodyType (rand 32),
  GenUncommonBodyType (32 + rand 12) and GenRareBodyType (44 + rand 6), and sets the next timed pick to
  game seconds + 3840h, exactly as the timed draw does. Nothing else is written. Every other key, page and
  type goes to the game's own HandleKey, unchanged.
* On the Flea Market page (category 0Fh) it depends on the patcher's "All 36 Flea Market goods" setting,
  the .vf2flea byte of the executable (the DLL reads it by section name at each press):
  - byte 1 (setting on, the default): the store lists all 36 goods at all times (the
    VF2GetExpandedFleaMarketCount / Item hooks), so there is nothing to refresh, and the game's own Flea
    Market draw (MaybeUpdateRotatingItems) must not run: it also sets each pooled good's stock count to 1,
    which would make 33 unlimited goods sell out for good after one purchase. R does nothing there (the
    game's own handler gets the key). An executable with no .vf2flea section (built before the setting)
    always lists the 36, and is treated the same way.
  - byte 0 (setting off): the Flea Market is the stock one (5 goods, re-picked 6 real hours after the last
    pick). R makes the game's own pick happen now: the next-pick time [InventoryManager+4A0h] is set to 0,
    which is due, and the store's own SetStoreCategory(0Fh) lists the page again, whose GetCategoryItemCount
    runs MaybeUpdateRotatingItems: 5 goods picked with the game's own shuffle (GetRandom), their stock
    counts set as the game sets them, the next pick at now + 5460h (21,600 real seconds). If the game clock
    is still 0 (no pick can be due) the old next-pick time is put back, so nothing is changed.
* While a box is open (the buy box, a message box, the bank, the Redeem Credit box) no key reaches the
  store: every store box is shown with ldwDialog::DoModal(scene, false), which makes the box modal in
  ldwEventManager, and ldwEventManager::HandleKey stops at a modal handler. The store screen itself has no
  text box.
"""
from __future__ import annotations

IMAGE_BASE = 0x400000
B200_EXE_NAME = "Virtual Families 2 - B200.exe"

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2refresh_b200.dll"
INI_NAME = "vf2refresh.ini"
INI_KEY = "RefreshKey"
LOG_NAME = "vf2refresh.log"
STARTUP = "B200Refresh_Startup"
STATUS_MAGIC = 0x48464652          # 'RFFH' little-endian: R, F, F, H


class Pin:
    """One exact run of the executable (whole instructions of the core variant).

    dll: True = searched for by the DLL (emitted to the header); False = proved here and used by the tests
    only. A relocated 32-bit field and the 32-bit displacement of every call / jmp rel32 are wildcards when
    the run is looked for in another variant.
    """

    def __init__(self, name, va, hexbytes, note, dll=True):
        self.name = name
        self.va = va
        self.bytes = bytes.fromhex(hexbytes)
        self.note = note
        self.dll = dll


# ---- layout (the same in every variant; compiled into the DLL)
STORE_CATEGORY_FIELD = 0xD4         # CScrollingStoreScene: [this+0D4h] = the page's EInventoryCategory
CLOTHING_CATEGORY = 0x0D            # Clothing and Hairstyles: GetCategoryItemCount case 0Dh -> MaybeUpdateOutfits
FLEA_MARKET_CATEGORY = 0x0F         # Flea Market: GetCategoryItemCount case 0Fh -> MaybeUpdateRotatingItems
KEY_TYPE_CHARACTER = 5              # HandleKey type of a typed character
KEY_TYPE_KEYDOWN = 6                # HandleKey type of a key press (Esc is code 3E8h)
KEY_ESC = 0x3E8
KEY_R_LOWER = 0x72
KEY_R_UPPER = 0x52
HANDLE_KEY_VSLOT = 2                # ldwEventHandler::HandleKey: ldwEventManager calls [vtable+8]
OUTFIT_FIRST_FIELD = 0x450          # CInventoryManager: the six stock outfit rows' body values, +450h..+464h
OUTFIT_LAST_FIELD = 0x464
OUTFIT_NEXT_PICK_FIELD = 0x470      # game seconds of the next timed pick
OUTFIT_REPICK_DELAY = 0x3840        # 14,400 game seconds = 4 game hours
FLEA_ROWS_FIELD = 0x488             # CInventoryManager: the 5 listed Flea Market goods, +488h..+498h
FLEA_COUNT_FIELD = 0x49C            # how many are listed (5 after a pick, less after purchases)
FLEA_NEXT_PICK_FIELD = 0x4A0        # GetSecondsFromGameStart of the next pick
FLEA_REPICK_DELAY = 0x5460          # 21,600 real seconds = 6 real hours
FLEA_FLAG_SECTION = ".vf2flea"      # the "All 36 Flea Market goods" byte (1 = all 36, the default)
STORE_CLASS = "CScrollingStoreScene"

# ---- core-variant addresses (the DLL derives these in every variant)
STORE_HANDLE_KEY = 0x4025E0         # the folded scene HandleKey(type, code, sym) thiscall, ret 0Ch
SET_STORE_CATEGORY = 0x48CE00       # CScrollingStoreScene::SetStoreCategory(EInventoryCategory) thiscall, ret 4
INVENTORY_MANAGER = 0x6852C0        # the global CInventoryManager InventoryManager
MAYBE_UPDATE_OUTFITS = 0x46BE30     # CInventoryManager::MaybeUpdateOutfits(bool force) thiscall, ret 4
STORE_VTABLE = 0x4F8EB0             # CScrollingStoreScene's vtable (found through RTTI by the DLL)
STORE_SLOT_HANDLE_KEY = STORE_VTABLE + 4 * HANDLE_KEY_VSLOT

# ---- test-only (derived like the others, never given to the DLL)
GAME_TIME = 0x683038                # the global CGameTime
GAME_TIME_SECONDS = 0x468B00        # CGameTime::Seconds() thiscall
GEN_COMMON_BODY = 0x4BB8A0          # CVillager::GenCommonBodyType: GetRandom(20h)
GEN_RARE_BODY = 0x4BB8B0            # CVillager::GenRareBodyType: GetRandom(6) + 2Ch
GEN_UNCOMMON_BODY = 0x4BB8C0        # CVillager::GenUncommonBodyType: GetRandom(0Ch) + 20h
GET_RANDOM = 0x4757C0               # ldwGameState::GetRandom(int) cdecl
GET_CATEGORY_ITEM_COUNT = 0x46B6D0  # CInventoryManager::GetCategoryItemCount (patched head, stock table)
CLOTHING_COUNT_CASE = 0x46B77E      # its cases 9/0Bh/0Ch (return 1), then 0Dh: push 0; call MaybeUpdateOutfits; mov eax, count
RESET_FORCED_DRAW = 0x46C163        # CInventoryManager::Reset: clear +384h, then push 1; mov ecx,esi; call MaybeUpdateOutfits
EVENT_MANAGER_HANDLE_KEY = 0x474750 # ldwEventManager::HandleKey(type, code, sym): the key dispatch to the subscribed handlers
MAYBE_UPDATE_ROTATING = 0x46BEB0    # CInventoryManager::MaybeUpdateRotatingItems() thiscall: the Flea Market pick
FLEA_COUNT_CASE = 0x46B799          # GetCategoryItemCount: case 0Eh (return 12h), then case 0Fh -> MaybeUpdateRotatingItems
GET_SECONDS_FROM_GAME_START = 0x475830  # ldwGameState::GetSecondsFromGameStart() thiscall (the real clock the pick uses)
STRING_MANAGER_GET = 0x4A87A0       # theStringManager::Get() (SetStoreCategory's first call)
GAME_STATE_GET = 0x499620           # theGameState::Get() (MaybeUpdateRotatingItems' first call)
GET_NUM_AVAILABLE = 0x46B920        # CInventoryManager::GetNumAvailable (the patcher's head hook, then the stock body)
STORE_DRAW_NUM_AVAILABLE = 0x4B8860 # VF2StoreDrawNumAvailable: DrawVisibleStoreItem's checkmark question (generated)
DRAW_CHECKMARK_CALL = 0x48B30A      # DrawVisibleStoreItem: item < 1ADh; push item; ecx = InventoryManager; call it; jnz; image 27Ah
HANDLE_PURCHASE_ITEM = 0x48BF20     # CScrollingStoreScene::HandlePurchaseItem() thiscall: the buy box's Buy
PURCHASE_TRAY_ADD = 0x48C163        # its tray branch: TakeOne, the outfit ids, GetUseCount, ToolTray.AddItem
PURCHASE_SAVE = 0x48C280            # its end: theGameState::Get()->SaveCurrentGame()
TAKE_ONE = 0x46C480                 # CInventoryManager::TakeOne(item)
GET_USE_COUNT = 0x46BAF0            # CInventoryManager::GetUseCount(item)
TOOL_TRAY = 0x704000                # the global CToolTray ToolTray
TOOL_TRAY_ADD_ITEM = 0x4AB330       # CToolTray::AddItem(item, uses)
SAVE_CURRENT_GAME = 0x49AB50        # theGameState::SaveCurrentGame()
GET_STRING = 0x4A8940               # theStringManager::GetString(StringId) thiscall
TEXT_SET_TEXT = 0x480300            # ldwTextControl::SetText(const char *) thiscall: the page title
SET_STORE_CATEGORY_TEXT = 0x48CF2E  # SetStoreCategory: the default case's title, GetString(48Bh) -> SetText

PINS = [
    Pin(
        "store_handle_key", STORE_HANDLE_KEY,
        "558BEC837D08067518817D0CE8030000750F8B016A016A08FF500CB0015DC20C0032C05DC20C00",
        "The scene HandleKey(int type, int code, int sym) every simple scene shares (identical-code folded): "
        "type 6 and code 3E8h (Esc) -> this->HandleMessage(8, 1) (vtable slot 3), return true; anything else "
        "returns false. thiscall, ret 0Ch.",
    ),
    Pin(
        "set_store_category_head", SET_STORE_CATEGORY,
        "558BEC5356578BF1E893B901008B5D08B9C0526800538BF8899ED4000000E8ADE8FDFF8986D8000000",
        "CScrollingStoreScene::SetStoreCategory(category): [this+0D4h] = category, then "
        "InventoryManager.GetCategoryItemCount(category) (ecx = the global InventoryManager 0x6852C0) into "
        "[this+0D8h]. Every store page is a category set here.",
    ),
    Pin(
        "maybe_update_outfits", MAYBE_UPDATE_OUTFITS,
        "558BEC807D0800568BF17512B938306800E8BACCFFFF3B86700400007657E84DFA0400898650040000E842FA0400"
        "89865C040000E857FA0400898654040000E84CFA0400898660040000E831FA0400898658040000E826FA0400B938"
        "306800898664040000E866CCFFFF05403800008986700400005E5DC20400",
        "Whole CInventoryManager::MaybeUpdateOutfits(bool force) thiscall, ret 4: unless force, return while "
        "GameTime.Seconds() <= [this+470h]; else +450h/+45Ch = GenCommonBodyType, +454h/+460h = "
        "GenUncommonBodyType, +458h/+464h = GenRareBodyType, +470h = Seconds() + 3840h.",
    ),
    Pin(
        "gen_body_types", GEN_COMMON_BODY,
        "6A20E8199FFBFF83C404C3CCCCCCCCCC6A06E8099FFBFF83C40483C02CC3CCCC6A0CE8F99EFBFF83C40483C020C3",
        "CVillager::GenCommonBodyType (GetRandom(20h)), GenRareBodyType (GetRandom(6) + 2Ch) and "
        "GenUncommonBodyType (GetRandom(0Ch) + 20h): the game's own odds.",
        dll=False,
    ),
    Pin(
        "clothing_count_case", CLOTHING_COUNT_CASE,
        "B8010000005E5DC204006A00E8A1060000B8D60000005E5DC20400",
        "GetCategoryItemCount: the shared case returning 1, then case 0Dh (Clothing and Hairstyles, jump-table entry 13): MaybeUpdateOutfits(false), then the page's "
        "count. The page the DLL redraws is this category.",
        dll=False,
    ),
    Pin(
        "reset_forced_draw", RESET_FORCED_DRAW,
        "8DBE84030000B933000000F3AB6A018BCEE8B7FCFFFF8B8650040000",
        "CInventoryManager::Reset: MaybeUpdateOutfits(true) -- the game's own forced draw, the call the DLL "
        "makes.",
        dll=False,
    ),
    Pin(
        "maybe_update_rotating_items", MAYBE_UPDATE_ROTATING,
        "558BEC81EC9C000000A100C6590033C58945FC53898D68FFFFFFE851D702008BC8E85A9900008B8D68FFFFFF8D98605400"
        "008B91A0040000899D64FFFFFF3BDA730FC781A004000001000000BA010000003BC20F86E2000000565733FFBBBCF55600"
        "8B3381FEE10000007D1C8D04F6833C8574FE5600017506833CB1007421C704B101000000EB1056E802FCFFFF8B8D68FFFF"
        "FF84C0750889B4BD6CFFFFFF4783C30481FB4CF656007CB733F685FF7E3057E8599800008BD083C4043BD6741C8B8CB56C"
        "FFFFFF8B84956CFFFFFF8984B56CFFFFFF898C956CFFFFFF463BF77CD08B8D68FFFFFF8B856CFFFFFF5F5E898188040000"
        "8B8570FFFFFF89818C0400008B8574FFFFFF8981900400008B8578FFFFFF8981940400008B857CFFFFFF898198040000"
        "8B8564FFFFFFC7819C040000050000008981A00400008B4DFC33CD5BE8AA2B06008BE55DC3",
        "Whole CInventoryManager::MaybeUpdateRotatingItems() thiscall: now = GetSecondsFromGameStart(); a "
        "next-pick time [this+4A0h] more than 5460h ahead is clamped to 1; when now > [this+4A0h] the 36 goods "
        "of gGoodiesList (each not a bought one-off, each stock count set to 1) are shuffled with GetRandom, "
        "the first 5 stored at +488h..+498h, the count +49Ch = 5 and +4A0h = now + 5460h. A next-pick time of "
        "0 is due whenever now > 0.",
        dll=False,
    ),
    Pin(
        "flea_count_case", FLEA_COUNT_CASE,
        "B8120000005E5DC20400E8080700008B869C0400005E5DC20400",
        "GetCategoryItemCount: case 0Eh returns 12h, then case 0Fh (the Flea Market, jump-table entry 15): "
        "MaybeUpdateRotatingItems(), then the count [this+49Ch]. Listing the page is what picks.",
        dll=False,
    ),
    Pin(
        "set_store_category_text", SET_STORE_CATEGORY_TEXT,
        "688B0400008BCFE806BA01008B8E5801000050E8BA33FFFF",
        "SetStoreCategory: the page title, theStringManager GetString(id) -> [this+158h]->SetText(text) (the "
        "emulator records both).",
        dll=False,
    ),
    Pin(
        "get_num_available", GET_NUM_AVAILABLE,
        "558BEC51FF7508E8E4E4040083C4045983F8FF74045DC20400568B7508578BF981FE130100007516B9906F7000E8EEAA050084C0"
        "752D5F33C05E5DC20400",
        "CInventoryManager::GetNumAvailable(item): the patcher's head hook (VF2GetOutfitStoreNumAvailable; not -1 "
        "returns at once), then the stock body: item 113h asks IsRoomToPopulate, items below E1h return the stock "
        "count [this + item*4]. The store shows \"sold out\" at 0.",
        dll=False,
    ),
    Pin(
        "draw_checkmark_call", DRAW_CHECKMARK_CALL,
        "81FBAD0100007D5653B9C0526800E843D5020085C075478B4DF0687A020000",
        "DrawVisibleStoreItem: the patcher's VF2StoreDrawNumAvailable(InventoryManager, item) answers whether the "
        "row draws its checkmark (image 27Ah at 0).",
        dll=False,
    ),
    Pin(
        "handle_purchase_head", HANDLE_PURCHASE_ITEM,
        "558BEC6AFF68AB224F0064A1000000005081EC90000000A100C6590033C58945F05657508D45F464A3000000008BF1E8CCD6"
        "000083BED400000016",
        "CScrollingStoreScene::HandlePurchaseItem() head: esi = the scene; category [esi+0D4h] 16h (the bank) is "
        "the other branch; the item is [esi+160h].",
        dll=False,
    ),
    Pin(
        "purchase_tray_add", PURCHASE_TRAY_ADD,
        "50B9C0526800E81203FEFF8B8E600100008D41EE83F8027711C7866001000049000000B849000000EB1B8BC183F9157C1483F9"
        "177F0FC786600100004A000000B84A00000050B9C0526800E83DF9FDFF50FFB660010000B900407000E86CF10100",
        "HandlePurchaseItem, an item below E1h: TakeOne(item) (a count of 0 is left as it is), then "
        "ToolTray.AddItem(item, GetUseCount(item)): every purchase puts one in the tray.",
        dll=False,
    ),
    Pin(
        "purchase_save", PURCHASE_SAVE,
        "E89BD300008BC8E8C4E800008B4DF464890D00000000595F5E8B4DF033CD",
        "HandlePurchaseItem's end: theGameState::Get()->SaveCurrentGame(), then the SEH unwind.",
        dll=False,
    ),
    Pin(
        "event_manager_handle_key", EVENT_MANAGER_HANDLE_KEY,
        "558BEC8B0183EC108B0085C07447538B5D08568B7510578B7D0C660F1F4400000F10000F1145F0660F73D804660F7EC0A802"
        "74118B4DF05657538B018B4008FFD084C0750D807DF80075078B45FC85C075CE5F5E5B8BE55DC20C00",
        "Whole ldwEventManager::HandleKey(type, code, sym): walks the subscriber list {handler, flags, modal, "
        "next}; a handler subscribed for keys (flags bit 2) gets [vtable+8](type, code, sym); the walk stops "
        "when a handler returns true or at a MODAL entry (ldwEventManager::SetModal, which ldwDialog::DoModal "
        "calls for every store box). So no key reaches the store while one of its boxes is open.",
        dll=False,
    ),
]

# Addresses the DLL derives (in this order: the header's enum).
ADDRESS_CONSTANTS = ("STORE_HANDLE_KEY", "INVENTORY_MANAGER", "MAYBE_UPDATE_OUTFITS", "SET_STORE_CATEGORY")
# Addresses only the tests need.
TEST_ADDRESS_CONSTANTS = ("GAME_TIME", "GAME_TIME_SECONDS", "GEN_COMMON_BODY", "GEN_RARE_BODY",
                          "GEN_UNCOMMON_BODY", "GET_RANDOM", "GET_CATEGORY_ITEM_COUNT",
                          "EVENT_MANAGER_HANDLE_KEY", "MAYBE_UPDATE_ROTATING", "GET_SECONDS_FROM_GAME_START",
                          "STRING_MANAGER_GET", "GET_STRING", "TEXT_SET_TEXT", "GAME_STATE_GET",
                          "GET_NUM_AVAILABLE", "STORE_DRAW_NUM_AVAILABLE", "HANDLE_PURCHASE_ITEM", "TAKE_ONE",
                          "GET_USE_COUNT", "TOOL_TRAY", "TOOL_TRAY_ADD_ITEM", "SAVE_CURRENT_GAME")
# Core-variant numbers used only to prove things; never emitted to the DLL.
CORE_ONLY_CONSTANTS = ("IMAGE_BASE", "STORE_VTABLE", "STORE_SLOT_HANDLE_KEY", "CLOTHING_COUNT_CASE",
                       "RESET_FORCED_DRAW", "FLEA_COUNT_CASE", "SET_STORE_CATEGORY_TEXT", "DRAW_CHECKMARK_CALL",
                       "PURCHASE_TRAY_ADD", "PURCHASE_SAVE", *TEST_ADDRESS_CONSTANTS)
