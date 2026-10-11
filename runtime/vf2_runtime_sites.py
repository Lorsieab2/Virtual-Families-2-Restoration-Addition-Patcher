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
           "fix_vanilla_game_bugs (.vf2bugs): pause_yes_idempotent + title_menu_stale_hotspot "
           "converted; start_over_confirms + refresh_on_activate pending", True),
    Module("career_room_goals", "CareerRoomGoalReconciliation",
           "patch_career_room_goal_reconciliation (unconditional in B200; load hook)", True),
]
MODULE_BY_KEY = {m.key: m for m in MODULES}
CORE = "core"  # pins every module relies on: any mismatch installs nothing


class Pin:
    """Exact vanilla bytes at an address. `role` says why the module needs it:

    detour   -- a function-entry prologue stolen into a trampoline;
    replace  -- whole non-relative instructions (5+ bytes) the DLL re-does;
    retarget -- one `call rel32` / `jmp rel32` to `target`, redirected;
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

# Every direct caller of these functions must be exactly the listed sites
# (gen_sites refuses if .text has any other).
EXCLUSIVE_CALLERS = {
    CAN_START_NEXT_GENERATION: NEXT_GENERATION_CALLSITES,
    CHANCE_OF_PREGNANCY: (0x49F5FA,),
    TECH_LOAD_STATE: (TECH_LOAD_STATE_CALL,),
}
# Functions that must have no absolute (pointer) reference anywhere in the file.
NO_ABSOLUTE_REFERENCES = (CAN_START_NEXT_GENERATION, CHANCE_OF_PREGNANCY)

PIN_BY_NAME = {pin.name: pin for pin in PINS}
