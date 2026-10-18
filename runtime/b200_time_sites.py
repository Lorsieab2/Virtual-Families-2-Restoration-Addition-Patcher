"""Time Controls sites in the B200 Virtual Families 2 executable (core variant).

Single source of truth for every address the B200 Time Controls companion DLL
(vf2time_b200.dll) touches or relies on. Every entry pins the exact bytes of
the B200 link output (`Virtual Families 2 - B200.exe`, built by
work/patch_mobile_furniture_pack.py, core variant), so the DLL, the generator
and the tests all refuse an executable that is not byte-for-byte that build at
these places.

THE B200 IMAGE IS RELOCATED. Its DllCharacteristics are 0x8140 (DYNAMICBASE
set) and it has a .reloc section, so Windows may load it away from 0x400000.
Every address here is a link-time VA at image base 0x400000; the DLL adds
(live module base - 0x400000) to each one, and a pin compares the bytes with
every relocated 32-bit field (listed by tools/gen_b200_time_sites.py from the
.reloc table) taken back to its link-time value.

Each address was located structurally and is re-proved by
runtime/tools/gen_b200_time_sites.py, which decodes each pinned run with
capstone and reads the executable with pefile. The reasoning is in
docs/b200-time-controls-pins.md (layout) and the notes next to each pin.
"""
from __future__ import annotations

IMAGE_BASE = 0x400000
B200_EXE_NAME = "Virtual Families 2 - B200.exe"

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2time_b200.dll"
INI_NAME = "vf2time.ini"
INI_KEY = "TimeControls"


class Pin:
    """One exact run of the executable.

    kind: "context"  whole instructions, exact bytes (proves an assumption)
          "data"     exact bytes only (a vtable)
          "retarget" exactly one `call rel32` whose target is `target`; the DLL
                     re-points it (these runs are WRITTEN)
          "vtable_slot" a 4-byte pointer that holds `target`; the DLL replaces
                     it (these runs are WRITTEN)
    """

    def __init__(self, name, va, hexbytes, kind, note, target=None):
        self.name = name
        self.va = va
        self.bytes = bytes.fromhex(hexbytes)
        self.kind = kind
        self.note = note
        self.target = target


# --------------------------------------------------------------------------
# The new button. Layout decision: docs/b200-time-controls-pins.md section 4-5.
# The dialog is 0x280 x 0x1F2. Done is centred at y = 0x1F2 - 0x1E - height,
# Evict is at x = 0x1D2, the same y; Time Controls goes at x = 0x1E (30), the
# same y, id 9 (2, 3, 4 and the check boxes 5..8 are taken).
# --------------------------------------------------------------------------
OPTIONS_DIALOG_VTABLE = 0x5006D8
OPTIONS_CTOR_LAST_CALL = 0x4A621B       # call ldwCheckBox::SetChecked(bool): the constructor's last call
CONTROL_SET_CHECKED = 0x47EA50          # thiscall, ret 4
OPTIONS_HANDLE_MESSAGE = 0x4A6940       # theOptionsDialog::HandleMessage(int, long) thiscall, ret 8
OPTIONS_SLOT_HANDLE_MESSAGE = OPTIONS_DIALOG_VTABLE + 3 * 4   # 0x5006E4
OPTIONS_DONE_BUTTON_FIELD = 0xD4        # [this+0D4h] = the Done button
OPTIONS_STRING_MANAGER_FIELD = 0xB4     # [this+0B4h] = theStringManager
SCENE_TOP_FIELD = 0x18                  # ldwScene rect: left 14h, top 18h, right 1Ch, bottom 20h
SCENE_BOTTOM_FIELD = 0x20
CONTROL_HEIGHT_VOFFSET = 0x10           # ldwControl virtual: height (width is 0Ch)
OPTIONS_TIME_X = 0x1E                   # 30
OPTIONS_BUTTON_BOTTOM_MARGIN = 0x1E
OPTIONS_BUTTON_IMAGE = 0x128            # the art Done and Evict use
OPTIONS_TEXT_COLOUR = 0x58BEAC          # the colour the dialog labels its buttons with
TIME_BUTTON_ID = 9
MESSAGE_BUTTON_CLICKED = 8
GET_EVICT_FONT = 0x4A8850               # theStringManager: push 2; call GetFont -- Evict's font (thiscall)
GAME_NEW = 0x4CE840                     # operator new, cdecl
GRAPHICS_GET = 0x49AFD0                 # theGraphicsManager::Get()
GRAPHICS_GET_IMAGE_GRID = 0x49B1D0      # (EImage) thiscall, ret 4
BUTTON_CTOR = 0x472D70                  # ldwButton(id, grid, ldwPoint, scene, bool) thiscall, ret 18h
BUTTON_SET_TEXT = 0x4736C0              # ldwButton::SetText(text, c1, c2, c3, font) thiscall, ret 14h
SCENE_ADD_CONTROL = 0x47EC70            # ldwScene::AddControl(ctrl) thiscall, ret 4

# Game time and aging.
GAME_TIME = 0x683038
SET_SPEED = 0x468B80                    # CGameTime::SetSpeed(int) thiscall, ret 4
GAME_STATE_INSTANCE_PTR = 0x685A88      # theGameState::Get() singleton pointer
GAME_STATE_SPEED_FIELD = 0x25B18
PAUSED_OFFSET = 999
SPEED_NORMAL = 10
SPEED_SLOW = 20
SPEED_FAST = 5
SPEED_5X = 2
SPEED_10X = 1
TICKS_PER_YEAR = 20
VILLAGER_MANAGER = 0x706F90
VILLAGER_ARRAY_OFFSET = 0x1CC70
VILLAGER_STRIDE = 0x1CC0C
VILLAGER_AGE_OFFSET = 0x6A54
VILLAGER_ACTIVE_OFFSET = 0x1BB84
VILLAGER_LEFT_HOME_OFFSET = 0x1BB88
VILLAGER_HEALTH_OFFSET = 0x6B00
INCREMENT_AGE = 0x4C4080                # CVillagerBio::IncrementAge(int) thiscall, ret 4
TIMEFLOW_INCREMENT_AGE_CALL = 0x4C4DEF  # call IncrementAge inside AllVillagersTimeflowUpkeep

GAME_STATE_VTABLE = 0x4FC554
GAME_STATE_SLOT_LOAD = 0x4FC588         # vtable slot 13: Load(int slot)
GAME_STATE_SLOT_SAVE = 0x4FC58C         # vtable slot 14: Save(int slot)
GAME_STATE_LOAD = 0x499DC0              # thiscall, ret 4, bool
GAME_STATE_SAVE = 0x49AA00              # thiscall, ret 4

# vtable -> (class name, CompleteObjectLocator, TypeDescriptor); the generator
# proves the chain and that every slot pin lies in a declared vtable.
VTABLE_CLASSES = {
    OPTIONS_DIALOG_VTABLE: ("theOptionsDialog", 0x55C140, 0x59F33C),
    GAME_STATE_VTABLE: ("theGameState", 0x55BE04, 0x59F23C),
}

PINS = [
    Pin(
        "options_ctor_head", 0x4A5D28,
        "8BD9895DEC6A01E80CAAFDFFC703D8065000",
        "context",
        "theOptionsDialog constructor: mov ebx,ecx (ebx = the dialog for the whole constructor); the stock vtable 0x5006D8 is stored into it.",
    ),
    Pin(
        "options_ctor_ids", 0x4A5D5D,
        "C7437402000000C7437803000000C7437C04000000",
        "context",
        "The constructor sets the three button ids: Done [ebx+74h] = 2, [ebx+78h] = 3, Evict [ebx+7Ch] = 4.",
    ),
    Pin(
        "options_ctor_buttons", 0x4A5F32,
        "6A00536A006A0068280100008BCFE88B52FFFF50FF73748BCEE820CEFCFF8BC8EB0233C9898BD400"
        "00008B01C645FC00FF500C8B8BD40000008BF08B11FF521089450C8B431C2B43148B8BD400000099"
        "2BC28BF88BC6992BC2D1FF8B11D1F82BF88B43202B43182B450C83E81E5057FF52048B8BB4000000"
        "E8912800008B8BD400000050A1ACBE5800505050FF7508E8FAD6FCFFFFB3D40000008BCBE89D8CFD"
        "FF833D0830660000909090909090833D0C3066000290906A14E8508802008BF083C404897508C645"
        "FC0285F674318B4B202B4B182B4D0C6A005383E91E518B4DF068D20100006828010000E8AE51FFFF"
        "50FF737C8BCEE843CDFCFF8BF0EB0233F68B8BB4000000C645FC00E80E2800008B8BB400000050A1"
        "ACBE58005050506A10E8E8280000508BCEE860D6FCFF568BCBE8088CFDFF",
        "context",
        "The Done button (button ctor 0x472D70 with GetImageGrid(0x128), field [ebx+0D4h], width and height from its vtable slots 3 and 4, text colour [0x58BEAC], font, AddControl) and the Evict button built beside it: x = 1D2h, y = dialog height - Done height - 1Eh. The Time Controls button is built the same way.",
    ),
    Pin(
        "options_ctor_tail", 0x4A61F9,
        "568BCBC645FC00E86B8AFDFF8B83800000008BCE80B80A5B0200000F95C00FB6C050",
        "context",
        "The last check box (ids 5..8, id 8) is added and its state loaded; esi = that check box, ebx = the dialog; the next instruction is the SetChecked call the module retargets.",
    ),
    Pin(
        "options_ctor_exit", 0x4A6220,
        "833DC82F680000C74364000000000F94C08843618BC38B4DF464890D00000000595F5E5B8BE55DC2"
        "0800",
        "context",
        "After the last SetChecked call: two flag stores, eax = this, SEH unwind, ret 8. eax, ecx and edx are dead here.",
    ),
    Pin(
        "set_checked", 0x47EA50,
        "558BEC8B49108A45088841315DC20400",
        "context",
        "ldwCheckBox::SetChecked(bool): mov ecx,[ecx+10h]; mov [ecx+31h],al; ret 4. Only the call at 0x4A621B is retargeted, never the function.",
    ),
    Pin(
        "options_vtable", 0x5006D8,
        "60624A00606B4A00403B400040694A00A0394700503847007008480050254000",
        "data",
        "theOptionsDialog vtable (slots 0..7); slot 3 is HandleMessage.",
    ),
    Pin(
        "options_handle_head", 0x4A6940,
        "558BEC6AFF682B324F0064A1000000005081EC80000000A100C6590033C58945F05657508D45F464"
        "A3000000008BF1837D08080F85AE0100008B7D0C3B7E74751B",
        "context",
        "theOptionsDialog::HandleMessage(int message, long param) thiscall, ret 8: message 8 (button clicked) compared with [ebp+8], the id (param) in edi, then compared with the dialog's own button ids.",
    ),
    Pin(
        "button_ctor_head", 0x472D70,
        "558BEC6AFF689F1C4F0064A1000000005051535657A100C6590033C5508D45F464A3000000008BF9"
        "897DF08B5D0853E82C9C0000",
        "context",
        "ldwButton constructor head: this = ecx, the id [ebp+8].",
    ),
    Pin(
        "button_ctor_ret", 0x472ED6,
        "C21800",
        "context",
        "ldwButton constructor: ret 18h (id, image grid, ldwPoint by value, scene, bool).",
    ),
    Pin(
        "add_control_head", 0x47EC70,
        "558BEC515356576A088BF9E8C0FB0400",
        "context",
        "ldwScene::AddControl(control) head: thiscall, one argument.",
    ),
    Pin(
        "add_control_ret", 0x47ECBC,
        "C20400",
        "context",
        "ldwScene::AddControl: ret 4.",
    ),
    Pin(
        "image_grid_wrapper", 0x49B1D0,
        "558BEC8B095DE905000000",
        "context",
        "GetImageGrid wrapper: mov ecx,[ecx]; jmp 0x49B1E0 (ecx = theGraphicsManager::Get()).",
    ),
    Pin(
        "image_grid_head", 0x49B1E0,
        "558BEC6AFF687D2C4F0064A100000000505657A100C6590033C5508D45F464A300000000FF7508E8"
        "54FFFFFF",
        "context",
        "GetImageGrid(EImage) head.",
    ),
    Pin(
        "image_grid_ret_1", 0x49B271,
        "C20400",
        "context",
        "GetImageGrid exit: ret 4.",
    ),
    Pin(
        "image_grid_ret_2", 0x49B28B,
        "C20400",
        "context",
        "GetImageGrid exit: ret 4.",
    ),
    Pin(
        "image_grid_ret_3", 0x49B2E7,
        "C20400",
        "context",
        "GetImageGrid exit: ret 4.",
    ),
    Pin(
        "image_grid_ret_4", 0x49B31B,
        "C20400",
        "context",
        "GetImageGrid exit: ret 4.",
    ),
    Pin(
        "image_grid_ret_5", 0x49B336,
        "C20400",
        "context",
        "GetImageGrid exit: ret 4.",
    ),
    Pin(
        "image_grid_ret_6", 0x49B34B,
        "C20400",
        "context",
        "GetImageGrid exit: ret 4.",
    ),
    Pin(
        "set_text", 0x4736C0,
        "558BEC8B51108B4514FF7518FF750889426C8B51108B450C8942648B51108B4510894268E807FFFF"
        "FF5DC21400",
        "context",
        "ldwButton::SetText(text, c1, c2, c3, font) thiscall, ret 14h.",
    ),
    Pin(
        "graphics_get_head", 0x49AFD0,
        "558BEC6AFF685F1C4F0064A1000000005051A100C6590033C5508D45F464A300000000A1D0E66F00"
        "85C0753A",
        "context",
        "theGraphicsManager::Get() head (cdecl, no arguments).",
    ),
    Pin(
        "graphics_get_ret_1", 0x49B02E,
        "C3",
        "context",
        "theGraphicsManager::Get() exit: plain ret.",
    ),
    Pin(
        "graphics_get_ret_2", 0x49B044,
        "C3",
        "context",
        "theGraphicsManager::Get() exit: plain ret.",
    ),
    Pin(
        "get_font", 0x4A8820,
        "558BEC8B450883F8047D088B4481105DC204008B41105DC20400",
        "context",
        "theStringManager::GetFont(int) thiscall, ret 4.",
    ),
    Pin(
        "get_evict_font", 0x4A8850,
        "6A02E8C9FFFFFFC3",
        "context",
        "push 2; call GetFont; ret -- the font the Evict button uses.",
    ),
    Pin(
        "game_new", 0x4CE840,
        "558BEC568B750856E8F3B3000083C40485C0751A56E8160A010083C40485C0741056E8D9B3000083"
        "C40485C074E65E5DC3",
        "context",
        "operator new (cdecl): the allocator the constructor uses for each button (push 14h; call).",
    ),
    Pin(
        "set_speed", 0x468B80,
        "558BEC51568BF1578B7D083B7E200F84070100005381FFE7030000753533DB33FF391D303068000F"
        "8ECB0000000F1F008B0CBEE888D0FEFF84C074088B0CBEE86C010000473B3D303068007CE3E9A600"
        "0000E8490A03008BC8E852CC00008BD88B462085C07512F30F1005B4454F002B5E28F30F1145FCEB"
        "3B660F6EC08BC30F5BC0C1E81F660F6ECF0F5BC9F30F5EC8660F6EC3F30FE6C0F30F114DFCF20F58"
        "04C5C0454F00660F5AC0F30F59C1F30F2CC02BD833FF393D303068007E3766908B0CBEE8F8CFFEFF"
        "84C074208B0CBEE8AC00000084C07514F30F1045FC518B0CBEF30F11042453E864000000473B3D30"
        "3068007CCB8B5D088BCEE881FEFFFF89462CE8990903008BC8E8A2CB00008946288B4620895E2089"
        "46245B5F5E8BE55DC20400",
        "context",
        "Whole CGameTime::SetSpeed(int) thiscall, ret 4 on GameTime (0x683038): returns at once when unchanged, 999 pauses the registered timers, any other value rescales them and stores the speed at +20h (the old one at +24h).",
    ),
    Pin(
        "space_toggle", 0x49EAC8,
        "8B47148B80185B02003DE70300007C360519FCFFFFB90A000000568BF00F44F1B93830680050E88D"
        "A0FCFF8B4714B9C0FB650089B0185B0200E86A48FBFF5E32C05F5DC2040068E7030000B938306800"
        "E863A0FCFF8B47145F8180185B0200E703000032C05DC20400",
        "context",
        "The Space key's pause toggle: field [state+25B18h] >= 999 -> SetSpeed(field - 999) and field = that (10 if 0); else SetSpeed(999) and field += 999. GameTime is 0x683038. Resume also clears a key-state object, which the module does not need.",
    ),
    Pin(
        "increment_age", 0x4C4080,
        "558BEC8B450801015DC20400",
        "context",
        "CVillagerBio::IncrementAge(int): push ebp; mov ebp,esp; mov eax,[ebp+8]; add [ecx],eax; ret 4. Adding is all it does.",
    ),
    Pin(
        "timeflow_head", 0x4C4C30,
        "558BEC83EC145356578BF9897DF4E8DD49FDFF8BD88DB7F4870300B80C78FCFF895DFC2BC78945F0"
        "B81E0000008945F8",
        "context",
        "AllVillagersTimeflowUpkeep(bool) prologue: edi = this (the villager manager), the loop runs 30 villagers; esi = villager + 1BB84h.",
    ),
    Pin(
        "timeflow_eligible", 0x4C4CD4,
        "803E000F84C8010000807E04000F85BE0100008BBE74AFFEFF85FF0F84B001000083BE7CAFFEFF00"
        "0F8EA3010000",
        "context",
        "Loop body: [esi] active, [esi+4] left home, health [esi-15084h] > 0 (villager + 6B00h), then the catch-up calculation.",
    ),
    Pin(
        "timeflow_caps", 0x4C4D47,
        "807D0800754C8B45F08B8B185B020003C683F90574228B55F48B84106437020083F90A740583F914"
        "74073D18790000EB153DF85C0000EB0E8B4DF481BC086437020038950000760AC78670AFFEFF1879"
        "000081BB185B0200E70300007C0AC78670AFFEFF00000000",
        "context",
        "Catch-up cap by the speed field [state+25B18h]: fast (5) 9538h, normal (10) and any other 7918h, slow (20) 5CF8h; paused (>= 999) -> 0.",
    ),
    Pin(
        "timeflow_ticks", 0x4C4DAF,
        "8BCBE87A0AFBFF8B9ED0AEFEFF8BBE70AFFEFF898674AFFEFFE85348FDFF8BC8B889888888F7E78D"
        "BED0AEFEFFC1EA058BC233D2F7B1185B02008BCF508945EC",
        "context",
        "ticks = (accumulator * 88888889h >> 37) / [state+25B18h]; edi = &age (esi-15130h = villager + 6A54h); push eax; [ebp-14h] = eax (the NATIVE ticks); the next instruction is the call to IncrementAge the module retargets.",
    ),
    Pin(
        "timeflow_remainder", 0x4C4E73,
        "E8A847FDFF8B80185B02000FAF45EC8BD0C1E2042BD08B8670AFFEFF8BC8C1E2022BCA3BD01BC023"
        "C1898670AFFEFF8B45F8",
        "context",
        "After the age is added: the accumulator remainder is computed from the NATIVE ticks [ebp-14h], so extra ticks given to IncrementAge never touch the accumulator.",
    ),
    Pin(
        "timeflow_tail", 0x4C4EA5,
        "81C60CCC010083E8018945F80F85A9FDFFFF5F5E5B8BE55DC20400",
        "context",
        "Loop end: esi += 1CC0Ch (the villager stride), 30 villagers, ret 4.",
    ),
    Pin(
        "timeflow_caller", 0x4A7CF2,
        "8BF9B9906F70006A00E830CF0100",
        "context",
        "The caller of AllVillagersTimeflowUpkeep: mov ecx,0x706F90 (the villager manager); push 0; call.",
    ),
    Pin(
        "game_state_get", 0x499620,
        "558BEC6AFF68022C4F0064A1000000005051A100C6590033C5508D45F464A300000000A1885A6800"
        "85C0753D68FC610200E8EA51030083C4048945F0C745FC0000000085C0741B8BC8E842FDFFFFA388"
        "5A68008B4DF464890D00000000598BE55DC333C0A3885A68008B4DF464890D00000000598BE55DC3",
        "context",
        "theGameState::Get(): [0x685A88] is the singleton pointer (created on first use).",
    ),
    Pin(
        "game_state_load_speed", 0x499E87,
        "8D8D54A4FDFFE80EF4FFFF5668185B02008D8554A4FDFF8BCB50E80ABAFDFF84C00F84ED0400008B"
        "CB8D8554A4FDFFF7D968185B0200508D43081BC923C851E8B568030083C40C8D83FC630100B93830"
        "680050E841EBFCFF84C0",
        "context",
        "theGameState::Load(slot != 0): reads 25B18h bytes, copies them over this+8 (so the speed field +25B18h is the saved one) and calls CGameTime::LoadState (0x468A20) on +163FCh.",
    ),
    Pin(
        "game_state_save_time", 0x49AAA3,
        "8D86FC630100B93830680050E80CE0FCFF",
        "context",
        "theGameState::Save(slot != 0): CGameTime::SaveState (0x468AC0) into +163FCh.",
    ),
    Pin(
        "game_state_save_blob", 0x49AB2B,
        "FF75088D4608C786D85A0200E903000068185B0200508BCEE8B8B4FDFF5E5DC20400",
        "context",
        "theGameState::Save(slot != 0) end: writes 25B18h bytes from this+8, which include the speed field, then ret 4.",
    ),
    Pin(
        "options_ctor_last_call", OPTIONS_CTOR_LAST_CALL, "E83088FDFF", "retarget",
        "The constructor's last call, `call SetChecked` on the last check box (ecx = esi, one bool "
        "argument, ret 4). Retargeted to a stub that makes the same call and then adds the button.",
        target=CONTROL_SET_CHECKED,
    ),
    Pin(
        "timeflow_increment_age_call", TIMEFLOW_INCREMENT_AGE_CALL, "E88CF2FFFF", "retarget",
        "AllVillagersTimeflowUpkeep's call to CVillagerBio::IncrementAge (ecx = &age, the ticks "
        "pushed). Retargeted to a wrapper that adds queued Time Warp ticks and calls the same function.",
        target=INCREMENT_AGE,
    ),
    Pin(
        "options_slot_handle_message", OPTIONS_SLOT_HANDLE_MESSAGE, "40694A00", "vtable_slot",
        "theOptionsDialog vtable slot 3 (HandleMessage): the function pointer the module replaces.",
        target=OPTIONS_HANDLE_MESSAGE,
    ),
    Pin(
        "game_state_slot_load", GAME_STATE_SLOT_LOAD, "C09D4900", "vtable_slot",
        "theGameState vtable slot 13 (Load): the function pointer the module replaces.",
        target=GAME_STATE_LOAD,
    ),
    Pin(
        "game_state_slot_save", GAME_STATE_SLOT_SAVE, "00AA4900", "vtable_slot",
        "theGameState vtable slot 14 (Save): the function pointer the module replaces.",
        target=GAME_STATE_SAVE,
    ),
]
