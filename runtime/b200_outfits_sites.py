"""Outfit Pictures: every site in the B200 Virtual Families 2 executable (core variant).

Single source of truth for every address the companion DLL vf2outfits_b200.dll touches or relies on. The
DLL fixes one stock bug, part of the Fix Vanilla Game Bugs setting: every outfit of a sex in the tool tray
shows, and puts on, the picture of the last one bought.

The stock bug (every step proved by a pin below):

* the store has three pictures per sex (CInventoryManager +408h + item * 4 for the store items 12h..17h,
  that is +450h..+464h), redrawn by MaybeUpdateOutfits;
* buying one (CScrollingStoreScene::HandlePurchaseItem, the run `st_buy`) calls TakeOne(item), which copies
  that picture into ONE field per sex: +468h for the male items 12h..14h, +46Ch for the female 15h..17h;
  the item becomes the tray item 49h (male outfit) or 4Ah (female outfit) and goes into the tool tray with
  CToolTray::AddItem(item, uses);
* the tray keeps only (item, uses) per place, nine places of 8 bytes (count +74h; the place in the hand
  +A0h; in hand +A4h, in use +A5h), with no spare field, and the save keeps exactly those 48h bytes;
* the tray draws each place (CToolTray::Draw) and the outfit in the hand (DrawToolInHand) with
  CInventoryManager::DrawItem, whose jump table sends 49h to the case that reads +468h and 4Ah to the case
  that reads +46Ch;
* putting an outfit on (theMainScene::HandleMouseDown, the run `ms_apply`) sets the villager's body
  (+6A84h) to GetOutfit(49h / 4Ah), which is +468h / +46Ch, before UseTool spends the place in the hand.

So every tray outfit of a sex shows and gives the last one bought. The fix keeps the picture of each tray
place in the DLL (set by the buy's AddItem, swapped with the two SwapSlots calls, lent to the two draws for
the one call, given back by the two GetOutfit calls of the apply) and, per save, in a sidecar .dat beside
the save file. Nothing is written to a game record or to the save.

Each pin is the exact bytes of the B200 link output (`Virtual Families 2 - B200.exe`, core variant, built by
work/patch_mobile_furniture_pack.py) of one game function or of the run of a function around the call the
DLL retargets. The image is relocated (DYNAMICBASE + .reloc) and every matrix variant links to different
addresses, so the DLL holds no address: it searches the live image for each pinned run (relocated 32-bit
fields and call/jmp rel32 displacements are wildcards) and derives every address from where the runs were
found. runtime/tools/gen_b200_outfits_sites.py proves every pin and derivation on the core variant with
capstone + pefile and renders the C header the DLL is built from.

The other companion DLLs are loaded first by the same loader (Time Controls, Up to 28 Children, Family
History). None of them touches the tray, the store's buy or the apply. Up to 28 Children writes a 5-byte jmp
at the entry of theGameState::Save and ::Load (the pins mark those bytes `skip`); Time Controls replaces
theGameState's Save and Load vtable slots (14 and 13) and Family History the Load slot. This DLL chains both
slots to whatever they hold, as Family History does.
"""
from __future__ import annotations

IMAGE_BASE = 0x400000
B200_EXE_NAME = "Virtual Families 2 - B200.exe"

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2outfits_b200.dll"
INI_NAME = "vf2outfits.ini"
INI_KEY = "OutfitPictures"
STARTUP_EXPORT = "B200Outfits_Startup"
STATUS_EXPORT = "B200Outfits_Status"
STATUS_MAGIC = 0x504F3242               # 'B2OP'
# The sidecar of a save file: <save folder>\Virtual Families 2 Patcher Data\Outfits\<save file>.dat
DATA_FOLDER = "Virtual Families 2 Patcher Data"
SIDECAR_FOLDER = "Outfits"
SIDECAR_MAGIC = b"VF2OUTFT"
SIDECAR_GAME_TAG = b"VF2B200\0"
SIDECAR_VERSION = 1

# Layout constants (each proved by an operand of the pinned code, see the prover's cross-checks).
TRAY_PLACES = 9                         # CToolTray::LoadState copies 9 places; Reset sets the count +74h to 9
TRAY_PLACE_SIZE = 8                     # (item, uses)
TRAY_SAVE_SIZE = 0x48                   # SaveState copies +0 .. +44h
TRAY_COUNT = 0x74
TRAY_HEIGHT = 0x78                      # one place's height (Draw: x = +7Ch + h/2, y = +80h + h*k + h/2 + 6)
TRAY_LEFT = 0x7C
TRAY_TOP = 0x80
TRAY_DRAW_OFFSET = 6
TRAY_HELD = 0xA0                        # the place in the hand (-1: none)
TRAY_IN_HAND = 0xA4
TRAY_IN_USE = 0xA5
TRAY_FIRST_FREE = 2                     # places 0 and 1 hold the fixed tools: AddItem and SwapSlots start at 2
TRAY_ITEM_LIMIT = 0xE1                  # LoadState keeps an item 0..E0h, anything else becomes 0
MALE_OUTFIT = 0x49
FEMALE_OUTFIT = 0x4A
STORE_MALE_FIRST = 0x12
STORE_MALE_LAST = 0x14
STORE_FEMALE_FIRST = 0x15
STORE_FEMALE_LAST = 0x17
INV_STORE_PICTURES = 0x408              # + item * 4: the store's picture of item 12h..17h
INV_MALE_PICTURE = 0x468                # the male outfit last bought (TakeOne; GetOutfit(49h); DrawItem 49h)
INV_FEMALE_PICTURE = 0x46C              # the female outfit last bought (4Ah)
INV_BIND_FIRST = 0x450                  # the store's six pictures, the two last bought and the redraw time
INV_BIND_COUNT = 9                      # +450h .. +470h, each copied 1:1 by SaveState and LoadState
INV_NEXT_REDRAW = 0x470
STORE_SCENE_ITEM = 0x160                # CScrollingStoreScene+160h: the item being bought
DRAW_FIRST_CASE = 0x12                  # DrawItem's jump table starts at item 12h
DRAW_CASE_MALE = 0x1D                   # offset of the +468h case in inv_draw_outfits
DRAW_CASE_FEMALE = 0x34                 # offset of the +46Ch case
VILLAGER_GENDER = 0x6A58                # ms_apply: 49h needs gender 0, 4Ah gender 1
VILLAGER_BODY = 0x6A84
PICTURE_LIMIT = 0x100                   # a body row; a value outside 0..FFh is never kept (the stock one shows)
SAVE_BACKUP_OFFSET = 0x14               # ldwGameState::Save keeps the previous save at slot + 20
LDW_PATH_VSLOT = 0x0C                   # theGameState vtable +0Ch: MakeGameStatePath(slot)
GS_LOAD_VSLOT = 0x34                    # theGameState vtable slot 13
GS_SAVE_VSLOT = 0x38                    # theGameState vtable slot 14


class Pin:
    """One exact run of the core executable.

    how:  "search"        found by searching the executable sections (must match exactly once);
          ("call", p, o)  the target of the call rel32 whose E8 byte is at offset o of pin p (then
                          byte-verified).
    skip: leading bytes that are wildcards because another companion DLL may have written its 5-byte
          jmp there (this DLL never writes them).
    """

    def __init__(self, name, va, hexbytes, how, note, skip=0):
        self.name = name
        self.va = va
        self.bytes = bytes.fromhex(hexbytes)
        self.how = how
        self.note = note
        self.skip = skip


SEARCH = "search"
KIDS_HOOKED = 5          # Up to 28 Children's entry jmp

PINS = [
    Pin("st_buy", 0x48C15C, (
        "3DE10000007D6350B9C0526800E81203FEFF8B8E600100008D41EE83F8027711C7866001000049000000B849000000EB"
        "1B8BC183F9157C1483F9177F0FC786600100004A000000B84A00000050B9C0526800E83DF9FDFF50FFB660010000B900"
        "407000E86CF10100EB6A"
    ), SEARCH, "CScrollingStoreScene::HandlePurchaseItem, a tray item (< E1h): TakeOne(item) (+0Dh), the store "
               "item 12h..14h becomes 49h and 15h..17h becomes 4Ah (+160h), then ToolTray.AddItem(item, "
               "GetUseCount(item)) (+63h): the buy's only AddItem."),
    Pin("tt_add_item", 0x4AB330, (
        "558BEC568BF1E8850100008BC883F9FF750732C05E5DC208008B45088904CE8B450C8944CE04518BCEE822080000B001"
        "5E5DC20800"
    ), ("call", "st_buy", 0x63),
        "CToolTray::AddItem(EInventoryItem, int uses): GetAvailableSlot (+6), then place = (item, uses); "
        "returns al, ret 8."),
    Pin("tt_available", 0x4AB4C0, (
        "8B5174B8020000003BD07E0F0F1F4000833CC1007408403BC27CF583C8FFC3"
    ), ("call", "tt_add_item", 0x06),
        "CToolTray::GetAvailableSlot(): the first empty place from 2, else -1; thiscall, plain ret."),
    Pin("tt_draw", 0x4AB3B0, (
        "56578BF933F63977747E54530F1F400080BFA40000000074083BB7A000000074378B1CF785DB74308B4F788BC1992BC2"
        "0FAFCE8B577C6A00D1F86A00038F8000000003D06A0083C00603C1B9C0526800535052E878FAFBFF463B77747CB25B5F"
        "5EC3"
    ), SEARCH, "CToolTray::Draw(): every place but the one in the hand, DrawItem(x, y, item, 0, 0, 0) (+53h) "
               "at x = +7Ch + h/2, y = +80h + h*k + h/2 + 6 (h = +78h)."),
    Pin("tt_draw_in_hand", 0x4AB420, (
        "558BEC83EC08568BF183BEA0000000FF0F84850000008D45F85750E82010FDFF8BC8E82910FDFF80BEA5000000008B86"
        "A00000008B3CC67407B801000000EB0957E8DA03FCFF83C4046A006A005057FF75FCB9C0526800FF75F8E801FAFBFF8B"
        "86A00000005F833CC603752F8B4DF88B45FC3B4E7C7C183B8E840000007F103B86800000007C083B86880000007E0C50"
        "51B958AA5D00E855B6F5FF5E8BE55DC3"
    ), SEARCH, "CToolTray::DrawToolInHand(): the place in the hand (+A0h) at the cursor, DrawItem (+5Ah)."),
    Pin("inv_draw_item", 0x46AE80, (
        "558BEC51FF751CFF7518FF7514FF7510FF750CFF7508E8F5E9040083C4185984C074045DC2180083EC50A100C6590033"
        "C58945FC568B7510894DC885F60F843802000081FEAD0100000F8D2C0200005357E8FA0003008D4EEE8945C033FFC745"
        "C46400000083CBFFBA6002000083F93877600FB68920B14600FF248D0CB14600"
    ), ("call", "tt_draw", 0x53),
        "CInventoryManager::DrawItem(ldwPoint, item, state, position, bool) head: B200's added-icon prefix "
        "(an item it draws itself returns there, ret 18h), then the stock switch on item - 12h through a byte "
        "table (+75h) and a case table (+7Ch)."),
    Pin("inv_draw_outfits", 0x46AF00, (
        "8B5DC8BA460200008B9CB308040000EB388B5DC88B9CB308040000EB278B5DC8BA46020000C745C4460000008B9B6804"
        "0000EB158B5DC8C745C4460000008B9B6C040000BA4202000083FBFF0F8588000000"
    ), SEARCH, "DrawItem's outfit cases: the store items' pictures (+408h + item * 4), the male outfit's "
               "+468h (+1Dh) and the female outfit's +46Ch (+34h); a picture of -1 draws the plain icon."),
    Pin("inv_get_outfit", 0x46B9B0, (
        "558BEC51FF7508E814E1040083C4045983F8FF74045DC204008B450883F849750A8B81680400005DC2040083F84A750A"
        "8B816C0400005DC2040033C05DC20400"
    ), ("call", "ms_apply", 0x3A),
        "CInventoryManager::GetOutfit(item): B200's expansion-outfit prefix (VF2GetOutfitStoreBodyValue; -1 "
        "for anything it does not own), then the stock 49h -> +468h, 4Ah -> +46Ch; thiscall, ret 4."),
    Pin("tt_swap", 0x4ABB10, (
        "558BEC53568B75088BD983FEFF7451578B7D0C83FFFF74473BF7743D83FF027C3883FE027C338B04FB8B14F38B4CF304"
        "8904F38B44FB048944F304894CFB048BCB568914FBE826000000578BCBE81E0000005F5E5B5DC2080056E8110000005F"
        "5E5B5DC20800"
    ), ("call", "tt_mouse_down", 0x84),
        "CToolTray::SwapSlots(a, b): swaps the two places' (item, uses) when a, b != -1, a != b, both >= 2; "
        "thiscall, ret 8. Its only two callers are tt_mouse_down and tt_mouse_up."),
    Pin("tt_mouse_down", 0x4AB660, (
        "558BEC568BF18B4D083B8E8C0000000F8CBA0000003B8E940000000F8FAE0000008B450C3B86900000000F8C9F000000"
        "3B86980000000F8F9300000050518BCEE8EB020000833E01740DC70601000000C74604FFFFFFFF837E0801740EC74608"
        "02000000C7460CFFFFFFFF80BEA400000000742650FFB6A00000008BCEC686A400000000E827040000C786A0000000FF"
        "FFFFFFB0015E5DC20800833CC6007511C786A0000000FFFFFFFF32C05E5DC20800508BCE8986A000000066C786A40000"
        "000100E858040000B0015E5DC2080080BEA40000000074D2C686A500000001B0015E5DC20800"
    ), SEARCH, "CToolTray::HandleMouseDown(ldwPoint): a click on the tray with a tool in the hand swaps the "
               "held place with the clicked one, SwapSlots(+A0h, clicked) (+84h)."),
    Pin("tt_mouse_up", 0x4AB790, (
        "558BEC53568BF1578BBEA0000000C6869C0000000083FFFF0F84DA00000080BEA50000000074105FC686A500000000B0"
        "015E5B5DC2080080BEA4000000000F84B40000008B45088B5D0C3B467C7C593B86840000007F513B9E800000007C493B"
        "9E880000007F415350E8920100003BC77506833CFE03752753FF75088BCE66C786A40000000000E87401000050578BCE"
        "E8EB020000C786A0000000FFFFFFFF5F5EB0015B5DC20800833CFE03754A5350B958AA5D00E8F6B2F5FF8B86A0000000"
        "8BCEC686A400000000C704C600000000FFB6A0000000E815030000B9E8C0B600C786A0000000FFFFFFFFE8C12C02005F"
        "5EB0015B5DC208005F5E32C05B5DC20800"
    ), SEARCH, "CToolTray::HandleMouseUp(ldwPoint): a drag dropped on another tray place swaps them, "
               "SwapSlots(held, PointToSlot) (+90h)."),
    Pin("ms_apply", 0x49FB5A, (
        "83F9490F859B00000083FFFF0F840B01000057B9906F7000E8996302008BF083BE586A000000755657B9906F7000E843"
        "6C02006A49B9C0526800E817BEFCFF6A00568BCE8986846A0000E8677C02008D45F350689A0000008BCEE8A7110200B9"
        "00407000E82DC00000B0018B4DF464890D00000000595F5E8BE55DC208006AFF688F000000B9C0FB6500E8D737FBFFB0"
        "018B4DF464890D00000000595F5E8BE55DC2080083F94A0F858100000083FFFF746B57B9906F7000E8F96202008BF083"
        "BE586A000000742F57B9906F7000E8A36B02006A4AB9C0526800E877BDFCFF6A00568BCE8986846A0000E8C77B02008D"
        "45DFE95BFFFFFF6AFF6891000000B9C0FB6500E85E37FBFFB0018B4DF464890D00000000595F5E8BE55DC208006AFF68"
        "90000000B9C0FB6500E83837FBFF"
    ), SEARCH, "theMainScene::HandleMouseDown, the tool in use (ecx) dropped on a villager (edi): 49h on a "
               "male (+6A58h == 0) or 4Ah on a female: MakeInFocus, body (+6A84h) = GetOutfit(49h) (+3Ah) / "
               "GetOutfit(4Ah) (+DAh), ForgetPlans, NewBehavior, then UseTool (+64h) spends the place in the "
               "hand."),
    Pin("tt_use_tool", 0x4ABBF0, (
        "568BF180BEA50000000074588B86A000000083F8FF744D8D0CC68B410485C07E43488941048B86A0000000837CC60400"
        "753266C786A400000000008BCEC704C600000000FFB6A0000000E841FFFFFFC786A0000000FFFFFFFFB9E8C0B6005EE9"
        "EC2802005EC3"
    ), ("call", "ms_apply", 0x64),
        "CToolTray::UseTool(): the place in the hand (+A0h, in use +A5h) loses one use; at 0 it is emptied."),
    Pin("inv_take_one", 0x46C480, (
        "558BEC56578B7D088BF18D8753FEFFFF3D84010000775A"
    ), ("call", "st_buy", 0x0D), "CInventoryManager::TakeOne(item) head: thiscall, ret 4."),
    Pin("inv_take_outfit", 0x46C51D, (
        "8D47FF3DDF0000000F87930000008B04BE85C00F84880000007E04488904BE8D47EE83F80277138B84BE080400005F89"
        "86680400005E5DC204008D47EB83F80277138B84BE080400005F89866C0400005E5DC20400"
    ), SEARCH, "TakeOne's outfit tail: the count of a stock item drops by one, then items 12h..14h copy "
               "their store picture (+408h + item * 4) into +468h and 15h..17h into +46Ch."),
    Pin("tt_load_state", 0x4AB900, (
        "558BEC51535657894DFCE8A10000008B4DFC33FF8B5D088BF12BD90F1F4400008B043389068B4433048946048B0685C0"
        "78073DE10000007C06C7060000000057E83B0200008B4DFC4783C60883FF097CCF5F5EB0015B8BE55DC20400"
    ), SEARCH, "CToolTray::LoadState(SSaveState const &): Reset, then the 9 places' (item, uses) copied, an "
               "item < 0 or >= E1h made 0."),
    Pin("tt_save_state", 0x4ABA90, (
        "558BEC8B55088B0189028B41048942048B41088942088B410C89420C8B41108942108B41148942148B41188942188B41"
        "1C89421C8B41208942208B41248942248B41288942288B412C89422C8B41308942308B41348942348B41388942388B41"
        "3C89423C8B41408942408B4144894244B0015DC20400"
    ), SEARCH, "CToolTray::SaveState(SSaveState &): +0 .. +44h copied, the 9 places and nothing else."),
    Pin("inv_load_state", 0x46BD00, (
        "558BEC515356578B7D088D91880400008BDF894DFC33C0BE74FE56002BD9669083F8057D058B0C13890A83F8037D0A8B"
        "8C8774040000894AEC833EFF750583C9FFEB038B0C87898A78FBFFFF83C6244083C20481FE181E57007CC58B75FCBACC"
        "0000008D8E840300000F1F80000000008A04198D49018841FF83EA0175F28B87700400008986700400008B8750040000"
        "8986500400008B875C04000089865C0400008B87540400008986540400008B87600400008986600400008B8758040000"
        "8986580400008B87640400008986640400008B87680400008986680400008B876C04000089866C0400008B8784040000"
        "8986840400008B87800400008986800400008B879C04000089869C0400008B87A00400005F8986A0040000B0015E5B8B"
        "E55DC20400"
    ), SEARCH, "CInventoryManager::LoadState: +450h .. +470h (the store's pictures, the two last bought, the "
               "redraw time) copied 1:1 from the save."),
    Pin("inv_save_state", 0x46C2C0, (
        "558BEC538B5D0833C056578BF18BFE8D93880400002BFB83F8057D058B0C17890A83F8037D0A8B8C8674040000894AEC"
        "8B0C8640898A78FBFFFF83C2043DE10000007CD38D8B84030000BACC000000908A04398D49018841FF83EA0175F28B86"
        "700400008983700400008B86500400008983500400008B865C04000089835C0400008B86540400008983540400008B86"
        "600400008983600400008B86580400008983580400008B86640400008983640400008B86680400008983680400008B86"
        "6C04000089836C0400008B86840400008983840400008B86800400008983800400008B86A00400008983A00400008B86"
        "9C0400005F89839C040000B0015E5B5DC20400"
    ), SEARCH, "CInventoryManager::SaveState: the same fields copied 1:1 into the save."),
    Pin("gs_ctor", 0x4993B0, (
        "558BEC6AFF68C82B4F0064A100000000505156A100C6590033C5508D45F464A3000000008BF18975F08D4E08E8BFFEFF"
        "FF8BCEE808C1FDFFC70654C54F00B9E8C0B600C786D85C020000040000C786DC5C020000030000C686E05C020000"
        "C786C05C020000000000C786B85C020002000000C745FC00000000C705E8C0B600F4010000C705ECC0B600F4010000"
        "E87E4E0300B9E8C0B600E8F4500300C786C45C0200FFFFFFFFE8A5B1FDFF83C0788BCE8986E45C0200E8C50600006A00"
        "8BCEE84C09000084C075078BCEE8D10500008BC68B4DF464890D00000000595E8BE55DC3"
    ), SEARCH, "theGameState::theGameState(): stores the vtable (+3Ah) and loads the settings file "
               "directly, Load(0) (+BFh)."),
    Pin("gs_load", 0x499DC0, (
        "558BECB8AC5B0200E823500300A100C6590033C58945FC53568B75088BD985F60F85A10000005668900000008D856CFF"
        "FFFF50E8B8BAFDFF84C00F849B050000578BFB8D83205B0200F7DF8DB56CFFFFFF68A8C54F001BFFB92400000023F86A"
        "00F3A568B0C54F00E8B3B8FDFF83C40C5F85C0741B5EC683295B020001B0015B8B4DFC33CDE8564D03008BE55DC20400"
        "68A8C54F006A0068C0C54F00E87FB8FDFF83C40C85C00F841B0500005EC683295B020000B0015B8B4DFC33CDE81F4D03"
        "008BE55DC204008D8D54A4FDFFE80EF4FFFF5668185B02008D8554A4FDFF8BCB50E80ABAFDFF84C0"
    ), SEARCH, "theGameState::Load(int slot), head: 0 = the settings file, 1..5 a family; ret 4.",
        skip=KIDS_HOOKED),
    Pin("gs_save", 0x49AA00, (
        "558BEC837D0800568BF175208BD68D86205B0200F7DA6A001BD2689000000023D052E8D9B5FDFF5E5DC204008D866801"
        "0000B9B8F4590050E8C373F6FF"
    ), SEARCH, "theGameState::Save(int slot), head: 0 = the settings file, 1..5 a family; ret 4.",
        skip=KIDS_HOOKED),
]

# Function entries the DLL calls or relies on: name -> pin (the entry is the pin's first byte).
FUNCTIONS = {
    "TT_ADD_ITEM": "tt_add_item",
    "TT_AVAILABLE": "tt_available",
    "INV_DRAW_ITEM": "inv_draw_item",
    "INV_DRAW_OUTFITS": "inv_draw_outfits",
    "INV_GET_OUTFIT": "inv_get_outfit",
    "TT_SWAP": "tt_swap",
    "TT_USE_TOOL": "tt_use_tool",
    "INV_TAKE_ONE": "inv_take_one",
    "INV_TAKE_OUTFIT": "inv_take_outfit",
    "GS_LOAD": "gs_load",
    "GS_SAVE": "gs_save",
}

# Globals read from a relocated 32-bit field of a pin: name -> (pin, offset of the field).
GLOBALS = {
    "INVENTORY_MANAGER": ("st_buy", 0x09),
    "TOOL_TRAY": ("st_buy", 0x5F),
    "GS_VTABLE": ("gs_ctor", 0x3A),
    "DRAW_CASE_BYTES": ("inv_draw_item", 0x75),
    "DRAW_CASE_TABLE": ("inv_draw_item", 0x7C),
}
# Every other place the same globals appear (the prover and the DLL check each one agrees).
GLOBAL_ALSO = {
    "INVENTORY_MANAGER": (("st_buy", 0x4E), ("tt_draw", 0x4C), ("tt_draw_in_hand", 0x53), ("ms_apply", 0x36),
                          ("ms_apply", 0xD6)),
    "TOOL_TRAY": (("ms_apply", 0x60),),
}
# Core-variant values (evidence, checked by the prover; never given to the DLL).
CORE_VALUES = {
    "INVENTORY_MANAGER": 0x6852C0,
    "TOOL_TRAY": 0x704000,
    "GS_VTABLE": 0x4FC554,
    "DRAW_CASE_BYTES": 0x46B120,
    "DRAW_CASE_TABLE": 0x46B10C,
}
CORE_MAKE_GAME_STATE_PATH = 0x475B40

# The calls the DLL retargets: name -> (pin, offset of the E8 byte, the function it must call).
CALL_HOOKS = {
    "CALL_BUY_ADD": ("st_buy", 0x63, "TT_ADD_ITEM"),
    "CALL_DRAW_TRAY": ("tt_draw", 0x53, "INV_DRAW_ITEM"),
    "CALL_DRAW_IN_HAND": ("tt_draw_in_hand", 0x5A, "INV_DRAW_ITEM"),
    "CALL_SWAP_CLICK": ("tt_mouse_down", 0x84, "TT_SWAP"),
    "CALL_SWAP_DROP": ("tt_mouse_up", 0x90, "TT_SWAP"),
    "CALL_APPLY_MALE": ("ms_apply", 0x3A, "INV_GET_OUTFIT"),
    "CALL_APPLY_FEMALE": ("ms_apply", 0xDA, "INV_GET_OUTFIT"),
}
# Other calls the DLL relies on (checked, never written): (pin, offset, function).
CALLS = (
    ("st_buy", 0x0D, "INV_TAKE_ONE"),
    ("tt_add_item", 0x06, "TT_AVAILABLE"),
    ("ms_apply", 0x64, "TT_USE_TOOL"),
    ("gs_ctor", 0xBF, "GS_LOAD"),
)
# The only callers of these functions anywhere in the code (the prover counts every call rel32): nothing
# else swaps tray places or asks for an outfit's picture.
ONLY_CALLERS = {
    "TT_SWAP": ("CALL_SWAP_CLICK", "CALL_SWAP_DROP"),
    "INV_GET_OUTFIT": ("CALL_APPLY_MALE", "CALL_APPLY_FEMALE"),
}

# Address constants the DLL derives (enum order of the header): functions, globals, then call sites.
ADDRESS_CONSTANTS = tuple(FUNCTIONS) + tuple(GLOBALS) + tuple(CALL_HOOKS)
# Values that only exist for the core variant.
CORE_ONLY_CONSTANTS = ("IMAGE_BASE", "CORE_MAKE_GAME_STATE_PATH", "KIDS_HOOKED")
