"""Runtime-hook sites in the VANILLA Virtual Families 2 executable.

Single source of truth for every address the companion DLL's modules touch or
rely on (Stage 1 began with Allow Older Pregnancies; each later module adds
its own section below). Every entry pins the exact vanilla bytes, so the patcher, the
companion DLL (through the generated header) and the tests all refuse an
executable that is not byte-for-byte the vanilla game at these places.

Vanilla executable: "Virtual Families 2.exe", SHA-256
1582d9e84e1c32f51475be17335c5137c592cebf809748d401ccef99a32b73c3, PE32, image
base 0x400000, no relocation directory, DllCharacteristics 0 (no ASLR).

Every address below was located structurally in the vanilla image (the stock
object files under work/desktop_obj_files name the functions, but their code
generation differs from the shipped game) and is re-proved by
runtime/tools/gen_sites.py, which decodes each pinned run with capstone.
How each one was found is recorded next to it.
"""
from __future__ import annotations

VANILLA_EXE_NAME = "Virtual Families 2.exe"
VANILLA_SHA256 = "1582d9e84e1c32f51475be17335c5137c592cebf809748d401ccef99a32b73c3"
IMAGE_BASE = 0x400000

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2fun.dll"
INI_NAME = "vf2fun.ini"

# --------------------------------------------------------------------------
# Executable-side bootstrap (the ONLY change made to the executable's own
# bytes besides the two new sections and the PE header fields).
#
# theGame's vtable is at 0x4E2998: RTTI ".?AVtheGame@@" TypeDescriptor
# 0x5336AC -> CompleteObjectLocator 0x524FB8 -> vtable 0x4E2998.
# theGame.obj's ??_7theGame@@6B@ orders the slots dtor, HandleMouse,
# HandleKey, HandleMessage, Init, Shutdown, Run, GameUpdate, GameDraw, so
# slot 4 (0x4E29A8) is theGame::Init = 0x428620. theGame is created once at
# 0x42AFEB (new 0x28 + ctor 0x4285E0) and Init is called exactly once through
# that slot at 0x42AFF8 (`mov eax,[edx+10h]; call eax`), before Run (+0x18).
# --------------------------------------------------------------------------
INIT_SLOT = 0x4E29A8
INIT_SLOT_EXPECTED = 0x428620

# KERNEL32 imports already present in the vanilla import table.
IAT_GET_MODULE_HANDLE_A = 0x4DE1E4
IAT_GET_PROC_ADDRESS = 0x4DE1E8

# The two new sections go straight after .rsrc (0xB24000 + 0x16244).
STUB_CODE_VA = 0xB3B000
STUB_DATA_VA = 0xB3C000


class Module:
    """One runtime feature module of vf2fun.dll.

    `ini_key` is its setting under [Patches] in vf2fun.ini (1 = on; anything
    else, or missing, = off = the stock game). `b200` names the static B200
    feature it reproduces and `b200_default` is that feature's state in a
    default B200 build (the patcher writes every key explicitly).
    """

    def __init__(self, key: str, ini_key: str, b200: str, b200_default: bool):
        self.key = key
        self.ini_key = ini_key
        self.b200 = b200
        self.b200_default = b200_default


# Order = install order = bit index in the status block masks.
MODULES = [
    Module("older_pregnancies", "AllowOlderPregnancies",
           "patch_allow_older_pregnancies + patch_next_generation_age_gate (.vf2preg)", False),
    Module("scene_null_guard", "SceneSetActiveNullGuard",
           "patch_ldwscene_setactive_null_guard (unconditional in B200)", True),
    Module("fix_vanilla_bugs", "FixVanillaGameBugs",
           "fix_vanilla_game_bugs (.vf2bugs): pause_yes_idempotent + title_menu_stale_hotspot + "
           "title_menu_start_over_confirms + title_menu_refresh_on_activate (all four)", True),
    Module("career_room_goals", "CareerRoomGoalReconciliation",
           "patch_career_room_goal_reconciliation (unconditional in B200; load hook)", True),
    Module("time_controls", "TimeControls",
           "none: new in the runtime build (the Virtual Families 1 patcher's Time Controls "
           "dialog; B200 has no equivalent, so the default is off)", False),
    Module("older_villager_mortality", "OlderVillagerMortality",
           "patch_older_villager_mortality (.vf2mort; the mortality half: the longevity-"
           "achievement observer is the static custom-achievements feature)", False),
]
MODULE_BY_KEY = {m.key: m for m in MODULES}
CORE = "core"  # pins every module relies on: any mismatch installs nothing


class Pin:
    """Exact vanilla bytes at an address. `role` says why the module needs it:

    detour   -- a function-entry prologue stolen into a trampoline;
    replace  -- whole non-relative instructions (5+ bytes) the DLL re-does
                (a run may end in one `call rel32` when `target` names it:
                the DLL then issues that call itself);
    retarget -- one `call rel32` / `jmp rel32` / `jcc rel32` to `target`, redirected;
    context  -- bytes the module's logic relies on; never written.
    """

    def __init__(self, name: str, va: int, hex_bytes: str, role: str, why: str,
                 module: str = "older_pregnancies", target: int | None = None):
        self.name = name
        self.va = va
        self.expected = bytes.fromhex(hex_bytes)
        self.role = role
        self.why = why
        self.module = module
        self.target = target

    @property
    def end(self) -> int:
        return self.va + len(self.expected)


# Function / data addresses the companion DLL calls or reads.
CHANCE_OF_PREGNANCY = 0x4A0810        # CVillagerState::ChanceOfPregnancy(int,int,int) thiscall, ret 0Ch
CHANCE_OF_PREGNANCY_STEAL = 8         # push ebx/ebp/esi/edi + mov edx,[esp+14h]
COOLDOWN_STORE = 0x49F6DF             # mov [eax+25AE0h],ebx in CVillagerPlans::ProcessCurrentPlan
COOLDOWN_STORE_LEN = 6
COOLDOWN_RESUME = 0x49F6E5
CAN_START_NEXT_GENERATION = 0x48FF70  # CFamilyTree::CanStartNextGeneration(bool) thiscall, ret 4
NEXT_GENERATION_CALLSITES = (0x430681, 0x430DB8, 0x43C0BD, 0x4407DC)
COUNT_SURVIVING_CHILDREN = 0x490080   # CFamilyTree::CountSurvivingChildren() thiscall, ret
GET_RANDOM = 0x403F70                 # ldwGameState::GetRandom(int) cdecl
TUTORIAL_TIP = 0xAA7E98               # global CTutorialTip TutorialTip
TUTORIAL_QUEUE = 0x4AA020             # CTutorialTip::Queue(StringId, EGameScene, bool) thiscall, ret 0Ch
VILLAGER_MANAGER = 0x5B9F58           # global CVillagerManager VillagerManager
FAMILY_TREE = 0x5ACFC8                # global CFamilyTree FamilyTree (generation at +4)
GAME_STATE_INSTANCE_PTR = 0x558FC0    # theGameState::Get() singleton pointer
VILLAGER_ARRAY_OFFSET = 0x1CC70       # VillagerManager + 0x1CC70 + i * 0x1CC0C, i < 30
VILLAGER_STRIDE = 0x1CC0C
GAME_STATE_TRY_FOR_BABY_DEADLINE = 0x25AE0

PINS = [
    Pin(
        "chance_entry", CHANCE_OF_PREGNANCY, "535556578B542414",
        "detour",
        "Entry of CVillagerState::ChanceOfPregnancy: push ebx; push ebp; push esi; "
        "push edi; mov edx,[esp+14h]. Found as the only function holding all three "
        "`push 868h` (eStringPregnancyTutorial) of the stock body; its single caller "
        "is 0x49F5FA. No branch anywhere in .text lands in 0x4A0811-0x4A0817.",
    ),
    Pin(
        "chance_tail", 0x4A08AA,
        "6A64E8BF36F6FF83C4043BC7B9987EAA007D176A006A006868080000E855970000",
        "context",
        "push 64h; call GetRandom(0x403F70); add esp,4; cmp eax,edi; "
        "mov ecx,TutorialTip(0xAA7E98); jge; push 0; push 0; push 868h; "
        "call CTutorialTip::Queue(0x4AA020). Proves the three addresses and the "
        "Queue(stringId, scene, bool) argument order the late-age roll reuses.",
    ),
    Pin(
        "chance_caller", 0x49F5DD,
        "8B87406B00008B8F546A00008B93546A000050518DB3F46A0000528BCEE81112000084C0",
        "context",
        "ProcessCurrentPlan's only ChanceOfPregnancy call: father fertility "
        "[edi+6B40h], father age [edi+6A54h], mother age [ebx+6A54h]; "
        "esi = mother+6AF4h (her CVillagerState). ebx came from 0x498D40 "
        "(GetMatriarch: active, not departed, health>0, gender==1) and edi from "
        "0x498DB0. esi and edi are callee-saved across every call up to the "
        "cooldown store, so at 0x49F6DF esi-0A0h is the mother's internal age "
        "and edi+6A54h the father's.",
    ),
    Pin(
        "chance_failed_branch", 0x49F601, "0F84BD000000",
        "context",
        "je 0x49F6C4: a failed roll goes to the cooldown block. This is the only "
        "branch that targets anything in 0x49F5F1-0x49F6E5.",
    ),
    Pin(
        "cooldown_block", 0x49F6C4,
        "E857B5F8FF8BC8E82049F6FF8D98B0040000E845B5F8FF6ACE8BCE8998E05A0200",
        "context",
        "call theGameState::Get; mov ecx,eax; call GetSecondsFromGameStart; "
        "lea ebx,[eax+4B0h]; call theGameState::Get; push -32h; mov ecx,esi; "
        "mov [eax+25AE0h],ebx. The last instruction (0x49F6DF, 6 bytes) is the "
        "failed-attempt deadline write B200's cooldown hook guards.",
    ),
    Pin(
        "cooldown_store", COOLDOWN_STORE, "8998E05A0200",
        "replace",
        "mov [eax+25AE0h],ebx. Exactly one instruction; the 5-byte jmp fits inside "
        "it. No branch anywhere in .text lands in 0x49F6E0-0x49F6E4. The DLL's "
        "replacement performs this store itself unless the couple qualifies.",
    ),
    Pin(
        "next_generation", CAN_START_NEXT_GENERATION,
        "E89BFFFFFF85C0740B807801007405B001C20400807C2404007422833DCCCF5A001E"
        "75196A00B9589F5B00E8109F000083F8FF7508B801000000C2040033C0C20400",
        "context",
        "Whole CFamilyTree::CanStartNextGeneration (GetCurrentFamily 0x48FF10; "
        "generation-30 check on FamilyTree+4 = 0x5ACFCC; "
        "VillagerManager(0x5B9F58).SelectRandomLivingVillager). The DLL calls it "
        "unmodified, first, exactly as B200's wrapper does.",
    ),
    Pin(
        "count_surviving_children", COUNT_SURVIVING_CHILDREN,
        "8B410485C07501C369C0C806000055568DB40840F9FFFF33ED803E0075055E33C05DC3"
        "5333DB399EB40100007E32578DBEE00100008B0750B9589F5B00E8EE8B000080B884BB"
        "010000740383C50183C30181C7D80000003B9EB40100007CD65F5B5E8BC55DC3",
        "context",
        "Whole CFamilyTree::CountSurvivingChildren (same body as the stock "
        "object: current family record, offspring list at +1E0h stride D8h, "
        "living = villager+1BB84h).",
    ),
    Pin(
        "get_villager", 0x498CB0,
        "8B44240485C07C1583F81E7D1569C00CCC01008D840870CC0100C20400",
        "context",
        "CVillagerManager::GetVillager: villager i = this + 1CC70h + i*1CC0Ch for "
        "0 <= i < 30, the layout the next-generation age scan reads.",
    ),
    Pin(
        "get_random", GET_RANDOM, "83EC08568B7424108D46FF3DFE7F0000",
        "context",
        "ldwGameState::GetRandom(int) entry (cdecl; the caller pops).",
    ),
    Pin(
        "game_state_get", 0x42AC41, "A1C08F550085C0",
        "context",
        "theGameState::Get reads its singleton from 0x558FC0 (used only by the "
        "read-only live probe).",
        module=CORE,
    ),
]

for _site in NEXT_GENERATION_CALLSITES:
    _rel = CAN_START_NEXT_GENERATION - (_site + 5)
    PINS.append(
        Pin(
            f"next_generation_call_{_site:x}", _site,
            "E8" + (_rel & 0xFFFFFFFF).to_bytes(4, "little").hex().upper(),
            "retarget",
            "call CFamilyTree::CanStartNextGeneration. The four callers are every "
            "direct call/jmp to 0x48FF70 in .text (no absolute references exist): "
            "CFamilyTreeScene::UpdateScene (vtable 0x4E2DD8 slot 8, +0x41), "
            "CFamilyTreeScene::Activate (slot 9, +0xA8), theMainScene::"
            "HandleVillagerDetailsButton (0x43BEE0, +0x1DD) and theMainScene::"
            "UpdateScene (0x4400F0, +0x6EC) -- the same four B200 retargets.",
            target=CAN_START_NEXT_GENERATION,
        )
    )

# --------------------------------------------------------------------------
# scene_null_guard -- B200 patch_ldwscene_setactive_null_guard.
#
# ldwScene::SetActive(bool) 0x40D1D0 (thiscall, ret 4), 59 direct callers.
# Located as the only function in .text with the stock body's
# `push 0; push 0Fh; push esi; call ldwEventManager::Get` (Subscribe) and
# `push 0Fh; push esi; call Get` (Unsubscribe) around a write through
# [esi+4]; like the stock object it then clears ldwScene::mLastUpdatedScene
# (0x5595F8) when it is this scene, calls ActivateControls (0x40D060) and the
# virtual at vtable+24h. Vanilla's code generation tests the argument BEFORE
# the write (`test bl,bl` at 0x40D1D5) and branches on it AFTER (`je` at
# 0x40D1DF), so the replacement must preserve the flags.
# --------------------------------------------------------------------------
SCENE_SET_ACTIVE = 0x40D1D0
SCENE_ACTIVE_WRITE = 0x40D1DA        # mov eax,[esi+4]; mov [eax],bl
SCENE_ACTIVE_WRITE_LEN = 5
SCENE_ACTIVE_RESUME = 0x40D1DF       # je 0x40D1F4 (flags still from test bl,bl)

PINS += [
    Pin(
        "scene_set_active", SCENE_SET_ACTIVE,
        "538B5C240884DB568BF18B4604881874136A006A0F56E85558FFFF8BC8E8CE58FFFFEB21"
        "6A0F56E84458FFFF8BC8E83D55FFFF3935F8955500750AC705F895550000000000538BCE"
        "E843FEFFFF8B168B4224538BCEFFD05E5BC20400",
        "context",
        "Whole ldwScene::SetActive: push ebx; mov ebx,[esp+8]; test bl,bl; "
        "push esi; mov esi,ecx; mov eax,[esi+4]; mov [eax],bl; je; "
        "Subscribe(this,0Fh,0) or Unsubscribe(this,0Fh) through "
        "ldwEventManager::Get 0x402A40; clear mLastUpdatedScene 0x5595F8 if it is "
        "this; ActivateControls 0x40D060; call [vtable+24h]; pop esi; pop ebx; "
        "ret 4. The guard's early return is exactly this epilogue (B200 returns "
        "through the function's own epilogue too).",
        module="scene_null_guard",
    ),
    Pin(
        "scene_active_write", SCENE_ACTIVE_WRITE, "8B46048818",
        "replace",
        "mov eax,[esi+4]; mov [eax],bl -- the unconditional write through the "
        "bound active-flag pointer (B200's hook bytes, same two instructions). "
        "Neither is relative; no branch in .text lands in 0x40D1DB-0x40D1DE.",
        module="scene_null_guard",
    ),
]

# --------------------------------------------------------------------------
# fix_vanilla_bugs -- B200 "Fix Vanilla Game Bugs" (.vf2bugs), the parts
# converted so far (see the study, section 11, for the rest):
#
# (a) patch_options_pause_yes_idempotent. theOptionsDialog vtable 0x4E2704
#     (RTTI ".?AVtheOptionsDialog@@" TD 0x52EF40), slot 1 HandleMouse =
#     0x422420. Its "Yes" branch: PtInRect(0x4016A0) on the Yes rect,
#     theRealtimeManager::Get/UpdateAll (0x42AD00/0x42ACB0),
#     GameTime(0x568088).SetSpeed(999) (0x427A50), esi = [esi+80h] (the game
#     state), then `add dword ptr [esi+25B18h],3E7h` (0x4226A6, 10 bytes)
#     and UpdateAll again. "No" stores 10. These are the only two writes of
#     999/10 in the function, as in the stock object. B200 adds 999 only
#     while the field is below 999 (signed `jge` skip).
# (b) patch_title_menu_stale_hotspot. theMenuScene vtable 0x4E3AB8 (TD
#     0x534BD4); its constructor 0x443180 (one caller, 0x428F77) stores the
#     old Change Player rect at this+9Ch..A8h = (ws+146h, F9h, ws+204h, 117h);
#     the top store is `mov dword ptr [esi+0A0h],0F9h` at 0x44337B (10 bytes).
#     Its only readers are theMenuScene::HandleMouse (slot 1, 0x443C70): the
#     inclusive compare block at 0x443CF6 (x<left, x>right, y<top, y>bottom
#     -> skip) and the hover PtInRect([esi+9Ch]) at 0x443E6D. PtInRect
#     (0x4016A0) is inclusive on all four sides, so top = bottom + 1 (0x118)
#     is a rect no point is in, exactly as B200 stores.
# --------------------------------------------------------------------------
PAUSE_YES_ADD = 0x4226A6
PAUSE_YES_ADD_LEN = 10
PAUSE_YES_RESUME = 0x4226B0
PAUSE_FIELD = 0x25B18
PAUSED_OFFSET = 999
TITLE_HOTSPOT_TOP_STORE = 0x44337B
TITLE_HOTSPOT_TOP_STORE_LEN = 10
TITLE_HOTSPOT_RESUME = 0x443385
TITLE_HOTSPOT_STOCK_TOP = 0xF9
TITLE_HOTSPOT_BOTTOM = 0x117
PT_IN_RECT = 0x4016A0

PINS += [
    Pin(
        "pause_yes_block", 0x422691,
        "68E7030000B988805600E8B05300008BB6800000008186185B0200E7030000E84B8600008BC8"
        "E8F48500005F5E5D32C05B83C47CC20C00",
        "context",
        "theOptionsDialog::HandleMouse 'Yes': push 3E7h; mov ecx,GameTime; call "
        "SetSpeed; mov esi,[esi+80h]; add [esi+25B18h],3E7h; call Get; mov ecx,eax; "
        "call UpdateAll; return false. esi holds the game state at the add.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "pause_no_block", 0x4226E3,
        "6A0AB988805600E8615300008B9680000000C782185B02000A000000",
        "context",
        "The 'No' branch: SetSpeed(10); [state+25B18h] = 10 (unchanged by the fix).",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "pause_yes_add", PAUSE_YES_ADD, "8186185B0200E7030000",
        "replace",
        "add dword ptr [esi+25B18h],3E7h -- one instruction, 10 bytes, not "
        "relative; no branch lands inside it. The flags it leaves are dead (the "
        "next instruction is a call).",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "title_ctor_rect", 0x443352,
        "89869C00000005BE0000008986A400000033C081C1BE000000898E94000000C7869800000019020000"
        "C786A0000000F9000000C786A800000017010000",
        "context",
        "theMenuScene ctor: [esi+9Ch]=ws+146h; [esi+0A4h]=+0BEh; ...; "
        "[esi+0A0h]=0F9h (top); [esi+0A8h]=117h (bottom).",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "title_hotspot_top", TITLE_HOTSPOT_TOP_STORE, "C786A0000000F9000000",
        "replace",
        "mov dword ptr [esi+0A0h],0F9h -- the rect's top; one 10-byte "
        "instruction, not relative; no branch lands inside it.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "title_mouse_rect_test", 0x443CF6,
        "3BBE9C0000000F8CC50100003BBEA40000000F8FB90100003BAEA00000000F8CAD010000"
        "3BAEA80000000F8FA1010000",
        "context",
        "theMenuScene::HandleMouse click test on the rect: x<left, x>right, "
        "y<top, y>bottom each skip (inclusive rect).",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "title_mouse_hover", 0x443E6D, "8D8E9C000000E828D8FBFF",
        "context",
        "theMenuScene::HandleMouse hover: lea ecx,[esi+9Ch]; call PtInRect.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "pt_in_rect", PT_IN_RECT,
        "8B4424043B017C1B3B41087F168B4424083B41047C0D3B410C7F08B801000000C2080033C0C20800",
        "context",
        "ldwRect::PtInRect(x, y): inclusive on all four sides.",
        module="fix_vanilla_bugs",
    ),
]


MENU_HANDLE_MESSAGE = 0x443EF0
START_OVER_BRANCH = 0x443F5C
START_OVER_SHARED_PATH = 0x443FFD     # stock Play / Start Over handler (click sound first)
START_OVER_RETURN_TRUE = 0x443FF6     # mov al,1; jmp epilogue
START_OVER_AFTER_SOUND = 0x44400C     # the shared handler after its click sound
START_OVER_CONFIRM_STRING_ID = 0x744  # eSayConfirmRestart
SHOW_MESSAGE_BOX = 0x421410           # cdecl (ldwScene*, StringId, int, bool); 0 = Yes
GAME_STATS = 0x568018                 # GameStats[0] (a village exists when non-zero)
SOUND_OBJECT = 0x569DB0
SOUND_PLAY = 0x446BC0                 # CSound::Play(ESound) thiscall, ret 4
SOUND_CLICK = 0xB9
GAME_STATE_INIT = 0x429DD0            # theGameState::Init() thiscall
GAME_STATE_SAVE_CURRENT = 0x429660    # theGameState::SaveCurrentGame() thiscall
MENU_GAME_STATE_FIELD = 0xC           # theMenuScene + 0Ch = theGameState*
GAME_STATE_NAME_FIRST = 0x25ABC       # six name dwords +25ABCh .. +25AD0h (24 bytes)
GAME_STATE_NAME_LAST = 0x25AD0
UPDATE_SHOW_PLAYER = 0x443B80         # theMenuScene::UpdateShowPlayer() thiscall
UPDATE_SHOW_PLAYER_STEAL = 8
SHOW_PLAYER_ADD_NAME = 0x443C00
SHOW_PLAYER_ADD_NAME_LEN = 7
SHOW_PLAYER_ADD_NAME_RESUME = 0x443C07
SCENE_GET_CONTROL = 0x40CFD0          # ldwScene::GetControl(int id) thiscall, ret 4
SCENE_ADD_CONTROL = 0x40CF80          # ldwScene::AddControl(ctrl) thiscall, ret 4
MENU_STRING_MANAGER_FIELD = 0x14
MENU_PLAY_BUTTON_FIELD = 0xD8
MENU_MANAGE_GAMES_ID_FIELD = 0xC4
MENU_MANAGE_GAMES_BUTTON_FIELD = 0xE4
MENU_NAME_BUTTON_FIELD = 0xF0
STRING_GET_STRING = 0x448E90          # theStringManager::GetString(StringId) thiscall, ret 4
STRING_GET_LARGE_FONT = 0x448E80      # theStringManager::GetLargeFont() thiscall
BUTTON_SET_TEXT = 0x4015E0            # ldwButton::SetText(text, c1, c2, c3, font) thiscall, ret 14h
TITLE_TEXT_COLOUR = 0x534BF4          # cLdwWhite as the title constructor reads it
TITLE_PLAY_STRING_ID = 0x775          # "Play"
TITLE_CONTINUE_STRING_ID = 0x280      # "Continue"
MENU_ACTIVATE = 0x4439F0
MENU_ACTIVATE_TAIL_TARGET = 0x42C020  # the floating-animation reset Activate(true) ends with
MENU_ACTIVATE_TAIL_CALL = 0x443A07
NICKNAME_DIALOG_DTOR = 0x41F970
NICKNAME_CANCEL_DTOR_CALL = 0x444073


# ---- fix_vanilla_bugs, part 2: title_menu_start_over_confirms and
# title_menu_refresh_on_activate (the rest of B200's .vf2bugs).
#
# (c) patch_title_menu_start_over_confirms. theMenuScene::HandleMessage
#     (vtable 0x4E3AB8 slot 3 = 0x443EF0; RTTI ".?AVtheMenuScene@@") tests a
#     clicked button id against Play ([this+0C0h]) and Start Over ([this+0C8h]);
#     both `je` rel32 land on the shared handler 0x443FFD: click sound, then
#     the GameStats[0] test, and with a village in progress it just rolls the
#     current story slot over and returns (the owner-reported defect: Start
#     Over keeps going into the current game). B200 re-points Start Over's
#     `je` (0x443F5C) at a stub: no village yet -> the stock path; else the
#     click sound, ShowMessageBox(this, eSayConfirmRestart 0x744, 0, true),
#     No (non-zero) -> the function's own `mov al,1` return at 0x443FF6, Yes
#     -> the live new-player sequence on the game state [this+0Ch] (clamp the
#     speed field, theGameState::Init with the 6 name dwords at +25ABCh..
#     +25AD0h kept, SaveCurrentGame), then the stock story/scene-9 path just
#     after its click sound (0x44400C). ShowMessageBox 0x421410 (cdecl, 4
#     args, returns 0 for Yes) is the function behind 4 callers whose
#     argument shape is proved by the Options dialog's Evict confirmation
#     (0x4229D9: push 1; push 0; push 11h; push esi; call; add esp,10h; test
#     eax,eax; jne skip; call EvictFamily). theGameState::Init 0x429DD0 and
#     SaveCurrentGame 0x429660 are the calls the stock theCreateNickNameDlg
#     (vtable 0x4E24F4, HandleMessage 0x41F980) makes for a new player, in the
#     same order and with the same speed clamp.
PINS += [
    Pin(
        "start_over_dispatch", 0x443F1B,
        "8BF183BC24F4000000080F85890100008B8424F80000003B86CC0000000F846A0100003B86D40000000F"
        "845E0100003B86C00000000F84A70000003B86C80000000F849B0000003B86C4000000",
        "context",
        "theMenuScene::HandleMessage: esi = this; message 8 (button clicked); the "
        "button id [esp+0F8h] is compared with [esi+0CCh] and [esi+0D4h] (other "
        "buttons), Play [esi+0C0h] (je 0x443FFD), Start Over [esi+0C8h] (je 0x443FFD, "
        "the branch B200 re-points) and Manage Games [esi+0C4h].",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "start_over_branch", 0x443F5C,
        "0F849B000000",
        "retarget",
        "je rel32 taken when the clicked id is Start Over's: the one branch the fix "
        "re-points (B200: the je at theMenuScene::HandleMessage+0x64). Play's own je "
        "at 0x443F50 stays.",
        module="fix_vanilla_bugs", target=START_OVER_SHARED_PATH,
    ),
    Pin(
        "start_over_paths", 0x443FF6,
        "B001E9B900000068B9000000B9B09D5600E8B42B0000833D1880560000741E8B760C8B86B85C02008986"
        "BC5C0200C786B85C020000000000E9810000008B4E0C83B9205B02000075426A008D4C2410E8F6B5FDFF"
        "6A00568D4C2414C78424F400000000000000E8FFDAFBFF83C9FF898C24EC0000003BC18D4C240C7509E8"
        "F8B8FDFFB001EB3AE8EFB8FDFF6A00B9A095AA00E8031D07008B760C8B96B85C02008996BC5C0200C786"
        "B85C020009000000EB0CE84349FCFF8BC8E84C49FCFF32C08B8C24E400000064890D00000000595E5B81"
        "C4E4000000C20800",
        "context",
        "The tail of HandleMessage: return-true at 0x443FF6 (mov al,1; jmp epilogue); "
        "the shared Play/Start Over handler 0x443FFD (push 0B9h; mov ecx,Sound "
        "0x569DB0; call CSound::Play 0x446BC0; cmp GameStats[0] 0x568018,0; je "
        "0x444033; rollover that keeps the current game); 0x444033 (slot "
        "[state+25B20h] zero -> the name prompt theCreateNickNameDlg: DoModal -1 = "
        "cancel -> dtor + return true, via the call at 0x444073); 0x444081 "
        "(SetStory(0), story slot [state+25CB8h] = 9, return false); the epilogue.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "show_message_box", 0x421410,
        "6AFF6808B14D0064A1000000005083EC7056A1447A550033C4508D44247864A3000000008B8424940000"
        "008B8C24900000008B94248C0000005051528D4C2414E87BFDFFFF8B8424880000006A00508D4C2410C7"
        "84248800000000000000E8ED06FEFF8D4C24088BF0C7842480000000FFFFFFFFE8F7FBFFFF8BC68B4C24"
        "7864890D00000000595E83C47CC3",
        "context",
        "Whole ShowMessageBox(ldwScene*, StringId, int, bool) (cdecl, 4 stack "
        "arguments, the caller pops): builds the message dialog, DoModal(scene, 0), "
        "returns its result.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "show_message_box_caller", 0x4229D4,
        "3B7E7C75216A016A006A1156E82BEAFFFF83C41085C075078BCEE87DFEFFFF",
        "context",
        "theOptionsDialog::HandleMouse, Evict: push 1; push 0; push 11h; push esi; "
        "call ShowMessageBox; add esp,10h; test eax,eax; jne past; mov ecx,esi; call "
        "EvictFamily. Result 0 = Yes: the argument order the Start Over stub uses.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "new_player_sequence", 0x41F9B1,
        "81BE185B0200E70300007C0AC786185B02000A000000578BCEE801A400008B4D4C6A148DBEBC5A020057"
        "E830E8FEFF8D96305B02008BC72BD75FEB038D49008A08880C0283C00184C975F48BCEC686995B020001"
        "C786205B020001000000E84C9C00005E8BCD",
        "context",
        "theCreateNickNameDlg::HandleMessage (vtable 0x4E24F4 slot 3), OK branch: "
        "[state+25B18h] >= 999 -> 10; theGameState::Init(0x429DD0); the typed name "
        "copied to +25ABCh; slot [state+25B20h] = 1; theGameState::SaveCurrentGame "
        "(0x429660). The live sequence B200's Yes repeats.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "game_state_init", 0x429DD0,
        "53568BF133DB57B988805600C686CC5C020001889EBC5A0200899ED45A0200E88CDAFFFF",
        "context",
        "theGameState::Init entry: first byte of the player name [esi+25ABCh] cleared "
        "(so the stub keeps the name dwords around the call) and the start of the "
        "subsystem resets.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "save_current_game", 0x429660,
        "53568BF18B068B50386A00FFD28AD88B86205B020085C0741A8B16508B42388BCEFFD022D8E89691FDFF"
        "83C0788986E45C02005E8AC35BC3",
        "context",
        "Whole theGameState::SaveCurrentGame (thiscall, no arguments, returns bool in "
        "al).",
        module="fix_vanilla_bugs",
    ),

# (d) patch_title_menu_refresh_on_activate. The title screen is built once
#     while loading. theMenuScene::UpdateShowPlayer (0x443B80, thiscall, no
#     arguments; callers 0x443DA9 and 0x443FF1) keeps the player-name label
#     (control id [this+0D0h], object [this+0F0h]) and Manage Games
#     (id [this+0C4h], object [this+0E4h]) in step with the current player,
#     but it only ever re-adds the name, so Manage Games is gone for the
#     session once a player is removed, and nothing calls it on Activate or
#     after a cancelled name prompt. B200 makes it the one refresh point:
#     (1) on entry it repeats the constructor's Play/Continue label choice;
#     (2) when it re-adds the name it re-adds Manage Games unless a control
#     with Manage Games' id is already in the scene; (3) Activate(true) calls
#     it; (4) the name prompt's cancel path calls it before returning true.
#     The constructor's label choice is at 0x4433F5..0x44346C: GetLargeFont
#     (0x448E80) of the string manager [this+14h], cLdwWhite x3 (the copy at
#     0x534BF4), the string 0x775 ("Play") or, with GameStats[0] != 0, 0x280
#     ("Continue") through GetString (0x448E90), ldwButton::SetText (0x4015E0)
#     on [this+0D8h].
    Pin(
        "title_ctor_label", 0x4433F5,
        "8B4E14889C24480100008986D8000000E8765A00008B4E1450A1F44B53005050506875070000E8705A00"
        "008B8ED800000050E8B4E1FBFF8B8ED8000000518BCEE8469BFCFF391D18805600742A8B4E14E8365A00"
        "008B4E1450A1F44B53005050506880020000E8305A00008B8ED800000050E874E1FBFF",
        "context",
        "theMenuScene constructor: the Play button [esi+0D8h] gets its label: ecx = "
        "[esi+14h]; GetLargeFont; push cLdwWhite (0x534BF4) three times; "
        "GetString(0x775); SetText; AddControl; cmp GameStats[0],ebx; je; the same "
        "with 0x280.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "show_player_body", 0x443B80,
        "83EC68A1447A550033C489442464538BD98B83D00000005550E83294FCFF8BE88B430C83B8205B020000"
        "747305BC5A0200C6442408008BD08A0883C00184C975F756578D7C24102BC283C7FF8D6424008A4F0183"
        "C70184C975F68BC8C1E9028BF2F3A58BC883E103F3A48D4C2410518B8BF0000000E8D6A5FCFF85ED5F5E"
        "753F8B93F0000000528BCBE87293FCFF5D5B8B4C246433CCE8B3FF070083C468C385ED741C8B83E40000"
        "00508BCBE8CF93FCFF8B8BF0000000518BCBE8C193FCFF8B4C246C5D5B33CCE882FF070083C468C3",
        "context",
        "Whole theMenuScene::UpdateShowPlayer: ebx = this; ebp = GetControl(0x40CFD0) "
        "of the name id [ebx+0D0h]; a player exists when [state+25B20h] != 0: the "
        "name is copied and SetText'd on [ebx+0F0h], and when ebp is 0 "
        "AddControl([ebx+0F0h]) (0x443C00); no player: Manage Games [ebx+0E4h] and "
        "the name are RemoveControl'd (0x40D000) when the name is shown.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "show_player_entry", 0x443B80,
        "83EC68A1447A5500",
        "detour",
        "sub esp,68h; mov eax,[0x557A44]: whole non-relative instructions at the "
        "function's entry; the trampoline resumes at 0x443B88. B200 detours the "
        "6-byte prologue of its own build the same way.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "show_player_add_name", 0x443C00,
        "8B93F000000052",
        "replace",
        "mov edx,[ebx+0F0h]; push edx -- the argument of the name's AddControl at "
        "0x443C09. Not relative; the stub adds Manage Games first and then redoes "
        "these two instructions and resumes at 0x443C07.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "menu_activate", 0x4439F0,
        "807C240400568BF17412B998F55500E8CC31FEFF8B4E10E81486FEFF5EC20400",
        "context",
        "theMenuScene::Activate(bool) (vtable 0x4E3AB8 slot 9, ret 4): when the "
        "argument is non-zero, SpawnButterflies (0x426BD0) and the floating animation "
        "reset 0x42C020 on [this+10h]; esi = this throughout.",
        module="fix_vanilla_bugs",
    ),
    Pin(
        "menu_activate_tail", 0x443A07,
        "E81486FEFF",
        "retarget",
        "call 0x42C020, the last act of Activate(true) (its only caller): the wrapper "
        "makes the call and then UpdateShowPlayer(this) with esi.",
        module="fix_vanilla_bugs", target=MENU_ACTIVATE_TAIL_TARGET,
    ),
    Pin(
        "nickname_cancel_dtor", 0x444073,
        "E8F8B8FDFF",
        "retarget",
        "call theCreateNickNameDlg's destructor (0x41F970) on the cancel path only "
        "(DoModal returned -1: `jne 0x44407C` is not taken). The wrapper makes the "
        "call and then UpdateShowPlayer(esi = this), then the stock `mov al,1` "
        "return.",
        module="fix_vanilla_bugs", target=NICKNAME_DIALOG_DTOR,
    ),
]

# --------------------------------------------------------------------------
# career_room_goals -- B200 patch_career_room_goal_reconciliation (load hook;
# its second hook, after the Cheat Upgrades "Reset Achievements" action,
# belongs to Cheat Upgrades and has no vanilla counterpart).
#
# theGameState::Load (vtable 0x4E29CC; RTTI TD 0x5336C4) loads the
# subsystems in the stock object's order: GameTime 0x4279F0, Achievement
# (0xAA8648) 0x4B51E0, Ball, DailyEmail, FamilyTree, FoodStore, GameStats,
# InventoryManager (0xAB3528) 0x4B9B80, CollectableItem, Money 0x427C70, then
# `lea eax,[ebx+168C0h]; push eax; mov ecx,Tech(0x5680E4); call
# CTech::LoadState` at 0x42A75E (0x428230 = `mov al,1; ret 4`, its only
# caller), then ToolTray, TutorialTip, PetManager, VillagerManager -- so, as
# B200 requires, after InventoryManager and Achievement. B200 retargets that
# call to a wrapper that calls LoadState and, when it returns true, runs
# CTech::Level(eTechKitchen=0), Level(eTechOffice=1), Level(eTechWorkshop=2).
# Vanilla CTech::Level 0x428260 (thiscall, ret 4) is the stock routine:
# tech 0 counts HaveUpgrade(0xF6..0xFF) -> goal 0x36, tech 1 (0xEB..0xF5)
# -> 0x37, tech 2 (0x100..0x109) -> 0x38; ResetSingleAchievementProgress
# (0x4B4D10) then IncrementProgress(goal, min(count,10)) (0x4B5300), and
# IncrementProgress(0x35, 1) when count > 0.
# --------------------------------------------------------------------------
TECH = 0x5680E4
TECH_LOAD_STATE = 0x428230
TECH_LOAD_STATE_CALL = 0x42A75E
TECH_LEVEL = 0x428260
HAVE_UPGRADE = 0x4B9F40
INVENTORY_MANAGER = 0xAB3528
ACHIEVEMENT = 0xAA8648
ACHIEVEMENT_RESET_SINGLE = 0x4B4D10
ACHIEVEMENT_INCREMENT = 0x4B5300

PINS += [
    Pin(
        "tech_load_state", TECH_LOAD_STATE, "B001C20400",
        "context",
        "CTech::LoadState: mov al,1; ret 4 (the stock object's body).",
        module="career_room_goals",
    ),
    Pin(
        "tech_load_state_block", 0x42A752, "8D83C068010050B9E4805600",
        "context",
        "theGameState::Load: lea eax,[ebx+168C0h]; push eax; mov ecx,Tech.",
        module="career_room_goals",
    ),
    Pin(
        "tech_load_state_call", TECH_LOAD_STATE_CALL, "E8CDDAFFFF",
        "retarget",
        "call CTech::LoadState inside theGameState::Load (B200's +0x205 site).",
        module="career_room_goals", target=TECH_LOAD_STATE,
    ),
    Pin(
        "tech_level", TECH_LEVEL,
        "8B4424045633F62BC60F842402000083E8010F840701000083E8010F85310300006800010000B92835AB00"
        "E8B01C090084C07405BE010000006801010000B92835AB00E8981C090084C0740383C6016802010000B928"
        "35AB00E8821C090084C0740383C6016803010000B92835AB00E86C1C090084C0740383C6016804010000B9"
        "2835AB00E8561C090084C0740383C6016805010000B92835AB00E8401C090084C0740383C6016806010000"
        "B92835AB00E82A1C090084C0740383C6016807010000B92835AB00E8141C090084C0740383C6016808010000"
        "B92835AB00E8FE1B090084C0740383C6016809010000B92835AB00E8E81B090084C0740383C6016A38B9488"
        "6AA00E8A5C9080083FE0A8BC67C05B80A000000506A38E90D02000068EB000000B92835AB00E8B21B090084"
        "C07405BE0100000068EC000000B92835AB00E89A1B090084C0740383C60168ED000000B92835AB00E8841B09"
        "0084C0740383C60168EE000000B92835AB00E86E1B090084C0740383C60168EF000000B92835AB00E8581B09"
        "0084C0740383C60168F0000000B92835AB00E8421B090084C0740383C60168F1000000B92835AB00E82C1B09"
        "0084C0740383C60168F2000000B92835AB00E8161B090084C0740383C60168F3000000B92835AB00E8001B09"
        "0084C0740383C60168F4000000B92835AB00E8EA1A090084C0740383C60168F5000000B92835AB00E8D41A09"
        "0084C0740383C6016A37B94886AA00E891C8080083FE0A8BC67C05B80A000000506A37E9F900000068F60000"
        "00B92835AB00E89E1A090084C07405BE0100000068F7000000B92835AB00E8861A090084C0740383C60168F8"
        "000000B92835AB00E8701A090084C0740383C60168F9000000B92835AB00E85A1A090084C0740383C60168FA"
        "000000B92835AB00E8441A090084C0740383C60168FB000000B92835AB00E82E1A090084C0740383C60168FC"
        "000000B92835AB00E8181A090084C0740383C60168FD000000B92835AB00E8021A090084C0740383C60168FE"
        "000000B92835AB00E8EC19090084C0740383C60168FF000000B92835AB00E8D619090084C0740383C6016A36"
        "B94886AA00E893C7080083FE0A8BC67C05B80A000000506A36B94886AA00E86ACD080085F674186A016A35B9"
        "4886AA00E858CD080085F67D0633C05EC2040083FE0CB80C0000007F028BC65EC20400",
        "context",
        "Whole vanilla CTech::Level(ETech): the stock routine B200 calls.",
        module="career_room_goals",
    ),
]

# --------------------------------------------------------------------------
# time_controls -- NEW in the runtime build (no B200 equivalent): the Virtual
# Families 1 patcher's "Time Controls" Windows dialog (pause, resume, 2x/5x/10x
# speed, one "Time Warp: +3 years"), opened by a button on the store screen.
#
# Game time. CGameTime (global 0x568088; Seconds = base + realElapsed /
# (speed / 10)) has SetSpeed(int) 0x427A50 (thiscall, ret 4): speed 10 is
# normal, 5 is 2x, 2 is 5x, 1 is 10x, and 999 pauses (the active CGameTimers
# are paused). theGameState (singleton pointer at 0x558FC0) keeps the same
# speed in a field at +0x25B18 that the aging code divides by. The Space key
# (theMainScene::HandleMessage, 0x43BC2D) is the game's own pause toggle: field
# >= 999 means paused and Space does SetSpeed(field - 999) and field = that
# value (10 if it is 0); otherwise it does SetSpeed(999) and field += 999. The
# only other callers of SetSpeed are the Options dialog's Pause Game Yes
# (0x42269B) and No (0x4226EA, stores 10). Nothing in the game resets a
# non-paused speed except a new village (0x429733 stores 10) and the Options
# dialog's No.
#
# Aging. CVillagerManager::AllVillagersTimeflowUpkeep(bool) 0x499700 (called
# by theRealtimeManager::UpdateAll 0x42ACB0, from theMainScene::UpdateScene
# every frame, and once from 0x432A46) runs for each of the 30 villagers
# (stride 0x1CC0C; the loop pointer esi is villager + 0x1BB88 = the
# "left home" byte). When one is active, at home and alive it turns the real
# seconds since its last update (villager + 0x6AF4 = seconds accumulator,
# + 0x6AF8 = last update) into age ticks: ticks = accumulator / 60 / speed
# (the speed field). Then, at 0x499893, `mov ecx,edi; mov ebx,eax; push ebx;
# call 0x498B40` adds them to the age at villager + 0x6A54 through
# CVillagerBio::IncrementAge (0x498B40, `add [ecx],eax; ret 4`), and
# afterwards the SAME function does the leaving-home check at 19 years (380
# ticks), the oldest-age record (GameStats + 0x20 = 0x568038) and subtracts
# speed * ticks * 60 from the accumulator using ebx (the native ticks). 20 ticks
# are one year (the pregnancy code divides the age by 20; 380 ticks = 19
# years), so "+3 years" is 60 extra ticks. The module hands the game extra
# ticks through that one IncrementAge call and never writes an age itself.
#
# Entry point. The store screen is CScrollingStoreScene (RTTI
# ".?AVCScrollingStoreScene@@" TD 0x534854 -> COL 0x52528C -> vtable
# 0x4E2E44; slot 0 dtor 0x4332C0, 1 HandleMouse 0x4340E0, 3 HandleMessage
# 0x4322B0). Its constructor (0x432F10; stores the vtable at 0x432F44) builds
# the controls: "Done" (string 0x76C) and "Back" (0x76D) on btn_orange.png
# (image 0x129, 145 x 34 per state) at (widescreenOffset + 0x10 / + 0xBA,
# 0x2DD) with ids 1 and 3, and the Bank hit-area (id 2). Its last act is
# `push 2; call SetStoreCategory` (0x4332A5). HandleMessage handles message 8
# (button clicked) with the button id in the second argument; ids 1, 2 and 3
# are the only ones it knows. The module adds a fourth button of the same
# art at widescreenOffset + 0x164 (the next slot to the right of Back) by
# retargeting that one call to a wrapper, and takes ownership of its clicks
# (id 0x5646) by detouring HandleMessage's entry.
# --------------------------------------------------------------------------
GAME_TIME = 0x568088
SET_SPEED = 0x427A50
GAME_STATE_SPEED_FIELD = 0x25B18      # same field as PAUSE_FIELD
SPEED_NORMAL = 10
STORE_VTABLE = 0x4E2E44
STORE_SET_CATEGORY = 0x432050         # CScrollingStoreScene::SetStoreCategory(int) thiscall, ret 4
STORE_CTOR_SET_CATEGORY_CALL = 0x4332A5
STORE_HANDLE_MESSAGE = 0x4322B0       # CScrollingStoreScene::HandleMessage(int,long) thiscall, ret 8
STORE_HANDLE_MESSAGE_STEAL = 7        # push -1; push offset handler
STORE_WIDESCREEN_OFFSET_FIELD = 0xE0
STORE_TIME_BUTTON_X = 0x164
STORE_TIME_BUTTON_Y = 0x2DD
MESSAGE_BUTTON_CLICKED = 8
BUTTON_IMAGE = 0x129                  # btn_orange.png
BUTTON_TEXT_COLOUR = 0x5347E4         # cLdwWhite
GAME_NEW = 0x4C379D                   # operator new (cdecl)
GRAPHICS_GET = 0x448950               # theGraphicsManager::Get()
GRAPHICS_GET_IMAGE_GRID = 0x448710    # (EImage) thiscall, ret 4
STRING_GET = 0x449610                 # theStringManager::Get()
BUTTON_CTOR = 0x401A40                # ldwButton(id, grid, ldwPoint, scene, bool) thiscall, ret 18h
# (BUTTON_SET_TEXT, STRING_GET_LARGE_FONT and SCENE_ADD_CONTROL are defined with fix_vanilla_bugs above.)
WARP_SITE = 0x499893                  # mov ecx,edi; mov ebx,eax; push ebx
WARP_SITE_LEN = 5
WARP_RESUME = 0x499898                # call CVillagerBio::IncrementAge
INCREMENT_AGE = 0x498B40
VILLAGER_ACTIVE_OFFSET = 0x1BB84
VILLAGER_LEFT_HOME_OFFSET = 0x1BB88
VILLAGER_HEALTH_OFFSET = 0x6B00
TICKS_PER_YEAR = 20

PINS += [
    Pin(
        "store_ctor", 0x432F37,
        "8BF189742424E8EE9EFDFF33DBC706442E4E00889EDC000000899EE4000000899EE8000000899EEC0000"
        "00899EF0000000899EF4000000899EF8000000899EFC000000899E00010000895C2430899E0401000089"
        "9E08010000899E0C010000899E10010000E8AF59010089442420E8666601008BF8E86F7CFFFF8BC8E838"
        "67FFFF8986E000000001054448530001054C485300B87000000001053448530001053C4853006A14899E"
        "34010000E8B50709008BE883C404896C241C3BEBC644243001743B8B86E0000000D9E851D91C24050002"
        "00006A038BCF8944241CE8385E0100506A01686C2E4E00B823000000508B44242850568BCDE85DB6FDFF"
        "EB0233C0508BCE885C2434898658010000E8379FFDFF6A14E84D0709008BE883C404896C241C3BEBC644"
        "243002742E8B86E00000005356B9DD020000518B4C242C83C010506829010000E88E560100506A018BCD"
        "E8B4E9FCFF8BE8EB0233ED8BCF885C2430E8E35D010050A1E4475300505050686C0700008BCFE8DE5D01"
        "00508BCDE826E5FCFF558BCEE8BE9EFDFF6A14E8D40609008BE883C404896C241C3BEBC644243003742E"
        "8B86E00000005356B9DD020000518B4C242C05BA000000506829010000E813560100506A038BCDE839E9"
        "FCFFEB0233C08BCF885C243089865C010000E8645D010050A1E4475300505050686D0700008BCFE85F5D"
        "01008B8E5C01000050E8A3E4FCFF6A14E8590609008BE883C404896C241C3BEBC64424300474318B86E0"
        "0000006A0156B9A4020000518B4C242C053E03000050682B010000E897550100506A028BCDE8BDE8FCFF"
        "8BE8EB0233EDB0FF8BCF885C2430884424148844241588442416884424178844241C8844241D8844241E"
        "8844241F88442420884424218844242288442423E8BA5C01008B4C24148B54241C508B4424245152506A"
        "7D8BCFE8B15C0100508BCDE8F9E3FCFF6AF06A148BCDE81EE4FCFF558BCEE8869DFDFF8B86E00000008D"
        "48288D90D603000005E90200008986F4000000C786F800000079000000C786000100002D02000083C01D"
        "8986FC0000008B86F4000000898EE40000008B8EF80000008986040100008B86000100008996EC000000"
        "8B96FC000000898E0801000089960C010000C786E800000055000000C786F00000000003000089861001"
        "0000838604010000FA83860C010000066A028BCE889E14010000889E21010000899E48010000E8A6EDFF"
        "FF8BC68B4C242864890D00000000595F5E5D5B83C420C3",
        "context",
        "Body of CScrollingStoreScene::CScrollingStoreScene from `mov esi,ecx`: "
        "the vtable store 0x4E2E44, the Done (id 1, string 0x76C), Back (id 3, "
        "string 0x76D) and Bank (id 2) buttons with their images, positions and "
        "calls (operator new 0x4C379D, theGraphicsManager::Get 0x448950, "
        "GetImageGrid 0x448710, theStringManager::Get 0x449610, GetLargeFont "
        "0x448E80, ldwButton ctor 0x401A40, SetText 0x4015E0, AddControl "
        "0x40CF80) and the final `push 2; call 0x432050`.",
        module="time_controls",
    ),
    Pin(
        "store_ctor_category_call", STORE_CTOR_SET_CATEGORY_CALL, "E8A6EDFFFF",
        "retarget",
        "The constructor's last call, SetStoreCategory(2) with ecx = the new "
        "scene. The module's wrapper makes that call and then adds its button.",
        module="time_controls", target=STORE_SET_CATEGORY,
    ),
    Pin(
        "store_handle_message", STORE_HANDLE_MESSAGE,
        "6AFF688BBC4D0064A1000000005081EC98000000535657A1447A550033C4508D8424A800000064A30000"
        "00008BF133DB83BC24B800000008889E640100000F85010100008B8424BC00000083F801",
        "context",
        "Entry of CScrollingStoreScene::HandleMessage (vtable slot 3): SEH "
        "prologue, esi = this, `cmp [esp+0B8h],8` (message 8 = button clicked), "
        "then the button id at [esp+0BCh] compared with 1.",
        module="time_controls",
    ),
    Pin(
        "store_handle_message_entry", STORE_HANDLE_MESSAGE, "6AFF688BBC4D00",
        "detour",
        "push -1; push 4DBC8Bh: whole, non-relative instructions at the entry. "
        "The trampoline runs them and resumes at 0x4322B7 (mov eax,fs:[0]).",
        module="time_controls",
    ),
    Pin(
        "timeflow_ticks", 0x499859,
        "8BCBE890A7F6FF8BAECCAEFEFF8B9E6CAFFEFF8DBECCAEFEFF898670AFFEFFE8A313F9FF8BC8B8898888"
        "88F7E38BC2C1E80533D2F7B1185B02008BCF8BD853E8A3F2FFFF",
        "context",
        "Inside AllVillagersTimeflowUpkeep: the last update stored (esi-15090h), "
        "ebp = the old age, ebx = the accumulator, edi = &age (esi-15134h), then "
        "ticks = (accumulator * 88888889h >> 37) / [state+25B18h] and "
        "`mov ecx,edi; mov ebx,eax; push ebx; call IncrementAge`.",
        module="time_controls",
    ),
    Pin(
        "timeflow_ticks_site", WARP_SITE, "8BCF8BD853",
        "replace",
        "mov ecx,edi; mov ebx,eax; push ebx -- exactly 5 bytes, non-relative. "
        "The module's stub redoes them with the queued warp ticks added to the "
        "pushed value (ebx keeps the native ticks for the accumulator remainder) "
        "and jumps to the call at 0x499898.",
        module="time_controls",
    ),
    Pin(
        "increment_age", INCREMENT_AGE, "8B4424040101C20400",
        "context",
        "CVillagerBio::IncrementAge(int): mov eax,[esp+4]; add [ecx],eax; ret 4. "
        "Adding is all it does; the leaving-home and oldest-age checks are in "
        "the caller, after this call.",
        module="time_controls",
    ),
    Pin(
        "space_pause_toggle", 0x43BC2D,
        "8B46148B80185B02003DE70300007C340519FCFFFF578BF87505BF0A00000050B988805600E8F9BDFEFF"
        "8B4E1489B9185B0200B9B0B15600E846BC00005F32C05EC2040068E7030000B988805600E8D0BDFEFF8B"
        "76148186185B0200E703000032C05EC20400",
        "context",
        "The Space key's pause toggle in theMainScene::HandleMessage: field "
        "[state+25B18h] >= 999 -> SetSpeed(field - 999), field = that (10 if 0); "
        "else SetSpeed(999), field += 999. GameTime is 0x568088 and the callee "
        "is 0x427A50.",
        module="time_controls",
    ),
    Pin(
        "set_speed", SET_SPEED,
        "83EC0C558B6C2414568BF13B6E200F841401000081FDE703000057753733FF33ED393D808056000F8ED8"
        "0000008D49008B0CBEE83801000084C074088B0CBEE86C01000083C7013B3D808056007CE1E9B1000000"
        "53E8763100008BC8E83FC5FDFF8BC88B462085C089442410750BD9E82B4E28D95C2410EB48DB4424208B"
        "C185C089442420DA742410D95C2410DB4424207D06D80534294E00D84C2410D97C24200FB74424200D00"
        "0C000089442414D96C2414DF7C24148B5424142BCAD96C242033FF393D808056008BD97E378D49008B0C"
        "BEE89800000084C0741D8B0CBEE89C00000084C07511D9442410518B0CBED91C2453E83700000083C701"
        "3B3D808056007CCC5B8BCEE8C4FDFFFF89462CE8BC3000008BC8E885C4FDFF8946288B4620894624896E"
        "205F5E5D83C40CC20400",
        "context",
        "Whole CGameTime::SetSpeed(int): returns at once when the speed is "
        "unchanged; 999 pauses the registered timers; any other value rescales "
        "them (CGameTimer::Adjust) and stores the new speed at +20h (the old "
        "one at +24h).",
        module="time_controls",
    ),
]

# --------------------------------------------------------------------------
# older_villager_mortality -- B200 patch_older_villager_mortality, the
# mortality half. B200 hooks CVillagerManager::
# AllVillagersRealtimePhysiologyAndProductivityUpkeep (here 0x49B840) at the
# `push 0; mov ecx,state; call FoodGroupsActive` that opens the stock old-age
# statement. With its flag on, B200 never runs the stock statement: it asks
# VF2RollOlderVillagerMortality(internal age, active food groups) and, when
# that says so, SetHealth(0, OldAge = 2), then rejoins after the statement
# (+0x3C8). Its flag-off path calls the longevity-achievement observer
# (custom achievements 0x85-0x89) in place of FoodGroupsActive; that observer
# belongs to the static custom-achievements feature and has no vanilla
# counterpart, so the runtime module carries the mortality decision only.
#
# The stock statement is 0x49BBC6..0x49BC46 (see the pins); gen_sites proves it
# is single-entry and that every exit of it is 0x49BC47.
# --------------------------------------------------------------------------
UPKEEP_FOOD_GROUPS_CALL = 0x49BBBD
UPKEEP_FOOD_GROUPS_CALL_LEN = 9
UPKEEP_FOOD_GROUPS_RESUME = 0x49BBC6
OLDER_MORTALITY_DONE = 0x49BC47
FOOD_GROUPS_ACTIVE = 0x4A0A80         # CVillagerState::FoodGroupsActive(int) thiscall, ret 4
SET_HEALTH = 0x4A0420                 # CVillagerState::SetHealth(int, ECauseOfDeath) thiscall, ret 8
CAUSE_OF_DEATH_OLD_AGE = 2
VILLAGER_STATE_AGE_OFFSET = 8
OLDER_MORTALITY_RANDOM_LIMIT = 1_000_000
OLDER_MORTALITY_TABLE_FIRST_AGE = 55
OLDER_MORTALITY_TABLE_LAST_AGE = 317
OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS = 999_999


def older_mortality_hazard_millionths(effective_age: int) -> int:
    """B200's annual old-age threshold in the 0..999999 domain (the same formula
    as work/patch_mobile_furniture_pack.py; the test compares them)."""
    import math
    years_past_threshold = max(0, effective_age - 55)
    late_years = max(0, effective_age - 110)
    intensity = 0.00365 * years_past_threshold + 0.06 * late_years
    hazard = -math.expm1(-intensity)
    threshold = int(math.floor(hazard * OLDER_MORTALITY_RANDOM_LIMIT + 0.5))
    return min(OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS, threshold)


OLDER_MORTALITY_HAZARDS = tuple(
    older_mortality_hazard_millionths(a)
    for a in range(OLDER_MORTALITY_TABLE_FIRST_AGE, OLDER_MORTALITY_TABLE_LAST_AGE + 1)
)

# The stock old-age statement: no branch from outside lands inside it (a branch
# to its first byte is fine), and every jump inside it that leaves it goes to
# `exit`. (name, first byte, one past the last byte, exit)
SINGLE_ENTRY_REGIONS = (
    ("older_mortality_statement", UPKEEP_FOOD_GROUPS_RESUME, OLDER_MORTALITY_DONE, OLDER_MORTALITY_DONE),
)

PINS += [
    Pin(
        "upkeep_caller", 0x42ACB4,
        "6A00B9589F5B00E840EA0600B9589F5B00E8760B0700",
        "context",
        "theRealtimeManager::UpdateAll: push 0; mov ecx,VillagerManager (0x5B9F58); "
        "call AllVillagersTimeflowUpkeep (0x499700); mov ecx,VillagerManager; call "
        "0x49B840 = "
        "CVillagerManager::AllVillagersRealtimePhysiologyAndProductivityUpkeep, the "
        "function the old-age roll lives in (its only caller).",
        module="older_villager_mortality",
    ),
    Pin(
        "mortality_scope", 0x49BB1E,
        "8DAE6CAFFEFF8BCDE8654E000084C074326A64E83A84F6FF83C40483F83C7F2383BE78AFFEFF147F0F6A"
        "64E82284F6FF83C40483F81E7F0B6A006AFF8BCDE8FF480000833D00805600007E538BCDE81F4E000084"
        "C075486A64E8F483F6FF83C40483F8327D398BCBE8A5CFFFFF84C0750F6A64E8DA83F6FF83C40483F814"
        "7D0B6AFF6A018BCDE8B748000083BE78AFFEFF647E0B6AFF6A648BCDE863480000",
        "context",
        "Inside the per-villager loop of 0x49B840: esi = &villager+387F8h (the 'left "
        "home' byte pointer), ebp = esi-15094h = the villager's CVillagerState, so "
        "[ebp+8] = [esi-1508Ch] is its internal age (CVillagerBio, 20 ticks = 1 year; "
        "IsNotOld 0x498B30 is `cmp [ecx],44Ch`, 55 years). The preceding statements "
        "(sickness, healing, afraid) are untouched.",
        module="older_villager_mortality",
    ),
    Pin(
        "mortality_food_groups", 0x49BBBD,
        "6A008BCDE8BA4E0000",
        "replace",
        "push 0; mov ecx,ebp; call CVillagerState::FoodGroupsActive(0) (0x4A0A80): "
        "the first act of the old-age statement (B200 hooks the same call). The stub "
        "redoes the call and takes the old-age decision itself.",
        module="older_villager_mortality", target=FOOD_GROUPS_ACTIVE,
    ),
    Pin(
        "mortality_block", 0x49BBBD,
        "6A008BCDE8BA4E00008BBE74AFFEFF8D0C80B867666666F7EFC1FA038BC2C1E81F03C28D048003C003C9"
        "03C08BD703C92BD075568D994C0400003BFB7E4C6A64E86E83F6FF89442420B867666666F7EFC1FA038B"
        "C2C1E81F03C28BC8B867666666F7EBC1FA038BC2C1E81F03C22BC88B4424208D0C8903C983C4043BC17D"
        "0B6A026A008BCDE8D9470000",
        "context",
        "The stock old-age statement, 0x49BBBD..0x49BC46: n = FoodGroupsActive(0) "
        "(0-5 active food groups); only on a whole birthday (age % 20 == 0) and past "
        "55 years + n (age > 1100 + 20n) roll GetRandom(100) < 10 * (age/20 - "
        "(1100+20n)/20); if it succeeds SetHealth(0, 2 = OldAge) on ebp. Every exit "
        "goes to 0x49BC47.",
        module="older_villager_mortality",
    ),
    Pin(
        "mortality_done", 0x49BC47,
        "8B8690AFFEFF85C08B5C24100F8478020000",
        "context",
        "The statement after the old-age block (mov eax,[esi-15070h]; test eax,eax; "
        "...): where B200 rejoins (+0x3C8) and where every stock exit of the block "
        "lands.",
        module="older_villager_mortality",
    ),
    Pin(
        "food_groups_active", 0x4A0A80,
        "53555633ED578DB1840000008DB9880000008D5D05E886A1F8FF8BC8E84F35F6FF39077305C60600EB08"
        "803E00740383C50183C70483C60183EB0175D85F5E8BC55D5BC20400",
        "context",
        "Whole CVillagerState::FoodGroupsActive(int) (thiscall, ret 4): counts the 5 "
        "food groups whose timer has not run out; returns 0-5.",
        module="older_villager_mortality",
    ),
    Pin(
        "set_health", 0x4A0420,
        "8B44240485C089410C7F118B442408C7410C00000000894110C2080083F8647E07C7410C64000000C741"
        "10FFFFFFFFC20800",
        "context",
        "Whole CVillagerState::SetHealth(int health, ECauseOfDeath) (thiscall, ret "
        "8): [this+0Ch] = health (capped at 100), [this+10h] = cause. Called with (0, "
        "2) at 0x49BC42, the only `push 2; push 0; call SetHealth` in the image.",
        module="older_villager_mortality",
    ),
]

# Byte offsets the branch scan (deliberately over-approximate: every offset
# counts as an opcode) reports but which are inside another instruction;
# source -> the start of the function containing it. gen_sites proves each by
# linear decode before dropping it.
NOT_INSTRUCTION_STARTS = {
    0x443F08: MENU_HANDLE_MESSAGE,  # the 7Ah displacement byte of `mov eax,[557A44h]` at 0x443F06
    # Inside the old-age statement's neighbourhood (0x49B840): bytes of displacements.
    0x49BC5E: 0x49B840,             # the 74h of `cmp eax,[esi-1508Ch]` (3B 86 74 AF FE FF) at 0x49BC5C
    0x49BC93: 0x49B840,             # the 74h of `cmp [esi-1508Ch],edx` (39 96 74 AF FE FF) at 0x49BC91
}

# Every direct caller of these functions must be exactly the listed sites
# (gen_sites refuses if .text has any other).
EXCLUSIVE_CALLERS = {
    CAN_START_NEXT_GENERATION: NEXT_GENERATION_CALLSITES,
    CHANCE_OF_PREGNANCY: (0x49F5FA,),
    TECH_LOAD_STATE: (TECH_LOAD_STATE_CALL,),
    MENU_ACTIVATE_TAIL_TARGET: (MENU_ACTIVATE_TAIL_CALL,),
}
# Functions that must have no absolute (pointer) reference anywhere in the file.
NO_ABSOLUTE_REFERENCES = (CAN_START_NEXT_GENERATION, CHANCE_OF_PREGNANCY)

PIN_BY_NAME = {pin.name: pin for pin in PINS}
