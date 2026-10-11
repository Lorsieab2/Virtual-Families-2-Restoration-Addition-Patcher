// vf2fun.dll -- runtime-hook companion for the VANILLA Virtual Families 2
// executable.
//
// The patched executable's only added code is a loader stub at theGame's
// Init vtable slot (see runtime/tools/build_stub.py). It loads this DLL by
// full path and calls VF2Fun_Startup() once, before theGame::Init and before
// the game loop. Everything else lives here and is installed at runtime by
// ONE install path (the host registry below), which owns every write:
//
//   1. settings: each module's [Patches] key in vf2fun.ini (1 = on; anything
//      else or missing = off = the stock game);
//   2. pin check: every core pin and every pin of the module must equal live
//      memory (vf2fun_sites.h, generated and capstone-proved by
//      runtime/tools/gen_sites.py), otherwise that module installs nothing;
//   3. trampolines: built in one private page that is PAGE_READWRITE while it
//      is filled and PAGE_EXECUTE_READ before any game byte changes;
//   4. install: per module, all or nothing. Each write makes its page
//      writable only for that write and restores the protection at once; if
//      any write of a module fails, every write of that module is put back
//      and the other modules are unaffected. No page is ever left writable
//      and executable.
//
// Modules (each a port of the B200 static build's feature, from
// work/patch_mobile_furniture_pack.py; see the per-module comments):
//   older_pregnancies  Allow Older Pregnancies (.vf2preg)
//   scene_null_guard   ldwScene::SetActive null active-flag guard
//   fix_vanilla_bugs   Fix Vanilla Game Bugs (.vf2bugs): Pause Yes, title hotspot
//
// The VF2Fun_Status export is the DLL's install-status block (documented
// below); it is part of the shipped interface. Per-call counters exist only
// in test builds (VF2FUN_TEST_COUNTERS, never defined by native/build.bat).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "vf2fun_sites.h"

// ---------------------------------------------------------------- status block
// VF2Fun_Status: what this launch installed. Written only by the install path
// in VF2Fun_Startup, never afterwards. Read by tools/probe_stage1.py (read
// only) and by the tests. Layout version 2:
//   magic           'VF2S'
//   version         2
//   moduleCount     VF2_MODULE_COUNT
//   requestedMask   bit m: module m's setting is on
//   pinsOkMask      bit m: every core pin and every pin of module m matched
//   installedMask   bit m: every write of module m is live
//   refusedMask     bit m: requested but not installed (pins, trampoline or write)
//   trampolinePage  the read-execute trampoline page, 0 if none was needed
//   writeMasks[m]   bit w: write w of module m is live
static const unsigned kMaxModules = 16;
struct VF2FunStatus {
    unsigned magic;
    unsigned version;
    unsigned moduleCount;
    unsigned requestedMask;
    unsigned pinsOkMask;
    unsigned installedMask;
    unsigned refusedMask;
    unsigned trampolinePage;
    unsigned writeMasks[kMaxModules];
};
static_assert(VF2_MODULE_COUNT <= kMaxModules, "too many modules for the status block");

extern "C" __declspec(dllexport) volatile VF2FunStatus VF2Fun_Status = {
    0x53324656u, 2u, VF2_MODULE_COUNT,
};

// ---------------------------------------------------------------- test counters
// TEST BUILDS ONLY. Lets the harness and a live test observe each hook
// without waiting for a rare event. Compiled out of release builds.
#ifdef VF2FUN_TEST_COUNTERS
struct VF2FunTestCounters {
    unsigned magic;              // 'VF2C'
    unsigned chanceCalls;        // ChanceOfPregnancy entries seen
    unsigned olderRolls;         // calls routed to the late-age roll
    unsigned olderSuccesses;     // late-age rolls that conceived
    unsigned cooldownStores;     // failed attempts whose deadline was written
    unsigned cooldownSkips;      // failed attempts whose deadline was skipped (50+)
    unsigned nextGenerationCalls;
    unsigned nextGenerationOlderGrants;  // stock said no, the 60+ rule said yes
    unsigned lastMotherAge;      // internal ages of the last ChanceOfPregnancy call
    unsigned lastFatherAge;
    unsigned sceneActiveWrites;  // SetActive with a bound flag pointer
    unsigned sceneNullSkips;     // SetActive with a null flag pointer (returned)
};
extern "C" __declspec(dllexport) volatile VF2FunTestCounters VF2Fun_TestCounters = { 0x43324656u };
#define VF2_COUNT(field) (++VF2Fun_TestCounters.field)
#define VF2_NOTE(field, value) (VF2Fun_TestCounters.field = (unsigned)(value))
#else
#define VF2_COUNT(field) ((void)0)
#define VF2_NOTE(field, value) ((void)0)
#endif

static HMODULE Module;
static wchar_t Folder[MAX_PATH];

// ---------------------------------------------------------------- log
// vf2fun.log beside the DLL: one short record of what this launch installed.
// The first line of a launch replaces the previous launch's log.
static bool LogStarted;

static void Log(const char *fmt, ...) {
    wchar_t path[MAX_PATH];
    if (_snwprintf_s(path, MAX_PATH, _TRUNCATE, L"%svf2fun.log", Folder) < 0)
        return;
    FILE *f = 0;
    if (_wfopen_s(&f, path, LogStarted ? L"a" : L"w") != 0 || !f)
        return;
    LogStarted = true;
    va_list args;
    va_start(args, fmt);
    vfprintf(f, fmt, args);
    va_end(args);
    fputc('\n', f);
    fclose(f);
}

// ================================================================ host registry
static const unsigned kMaxWrites = 16;
static const unsigned kMaxWriteLen = 16;

struct HookWrite {
    unsigned va;
    unsigned len;
    unsigned char bytes[kMaxWriteLen];
    unsigned char original[kMaxWriteLen];
};

// Trampoline arena: one page, RW while modules are planned, RX before any
// game byte is written.
static unsigned char *Arena;
static unsigned ArenaUsed;

static void EncodeRel32(unsigned char *out, unsigned char opcode, unsigned from, unsigned to) {
    out[0] = opcode;
    int rel = (int)(to - (from + 5));
    memcpy(out + 1, &rel, 4);
}

// A module's planned writes. Planning never touches game code.
struct Plan {
    unsigned module;
    HookWrite writes[kMaxWrites];
    unsigned count;
    bool ok;

    HookWrite *Add(unsigned va, unsigned len) {
        if (!ok || count >= kMaxWrites || len < 5 || len > kMaxWriteLen) {
            ok = false;
            return 0;
        }
        HookWrite &w = writes[count++];
        memset(&w, 0, sizeof w);
        w.va = va;
        w.len = len;
        return &w;
    }
    // jmp rel32 at va to `to`, the rest of `len` bytes NOP.
    void Jmp(unsigned va, unsigned len, const void *to) {
        HookWrite *w = Add(va, len);
        if (!w) return;
        EncodeRel32(w->bytes, 0xE9, va, (unsigned)to);
        for (unsigned i = 5; i < len; ++i) w->bytes[i] = 0x90;
    }
    // Retarget the 5-byte call rel32 (or jmp rel32) at va to `to`, keeping
    // its opcode (pinned as E8 or E9 by gen_sites).
    void Retarget(unsigned va, const void *to) {
        HookWrite *w = Add(va, 5);
        if (!w) return;
        EncodeRel32(w->bytes, *(const unsigned char *)va, va, (unsigned)to);
    }
    // Copy the `steal` bytes at va (proved whole, non-relative instructions)
    // into the arena followed by jmp va+steal. Returns the trampoline, or 0.
    void *Trampoline(unsigned va, unsigned steal) {
        if (!ok) return 0;
        if (!Arena) {
            Arena = (unsigned char *)VirtualAlloc(0, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            if (!Arena) { ok = false; return 0; }
        }
        if (ArenaUsed + steal + 5 > 4096) { ok = false; return 0; }
        unsigned char *t = Arena + ArenaUsed;
        memcpy(t, (const void *)va, steal);
        EncodeRel32(t + steal, 0xE9, (unsigned)(t + steal), va + steal);
        ArenaUsed += (steal + 5 + 15) & ~15u;
        return t;
    }
};

static bool PinsMatch(unsigned module) {
    for (size_t i = 0; i < sizeof(VF2_PINS) / sizeof(VF2_PINS[0]); ++i) {
        const VF2Pin &pin = VF2_PINS[i];
        if (pin.module != module) continue;
        if (memcmp((const void *)pin.va, pin.bytes, pin.len) != 0) {
            Log("pin %s at 0x%08X does not match the vanilla bytes", pin.name, pin.va);
            return false;
        }
    }
    return true;
}

// The ONLY function that writes game code. The page is writable for this
// write alone and gets its original protection back before returning.
static bool WriteCode(unsigned va, const unsigned char *bytes, unsigned len) {
    DWORD old = 0;
    if (!VirtualProtect((void *)va, len, PAGE_EXECUTE_READWRITE, &old))
        return false;
    memcpy((void *)va, bytes, len);
    DWORD ignored = 0;
    BOOL restored = VirtualProtect((void *)va, len, old, &ignored);
    FlushInstructionCache(GetCurrentProcess(), (void *)va, len);
    return restored != FALSE;
}

// Every write installed so far this launch (all modules), for the overlap check.
static HookWrite Installed[kMaxModules * kMaxWrites];
static unsigned InstalledCount;

static bool OverlapsInstalled(const HookWrite &w) {
    for (unsigned i = 0; i < InstalledCount; ++i) {
        const HookWrite &o = Installed[i];
        if (w.va < o.va + o.len && o.va < w.va + w.len) return true;
    }
    return false;
}

// All or nothing for one module.
static bool Apply(Plan &plan) {
    for (unsigned i = 0; i < plan.count; ++i) {
        if (OverlapsInstalled(plan.writes[i])) {
            Log("module %s: write at 0x%08X overlaps another module; installing nothing",
                VF2_MODULE_NAMES[plan.module], plan.writes[i].va);
            return false;
        }
    }
    for (unsigned i = 0; i < plan.count; ++i) {
        HookWrite &w = plan.writes[i];
        memcpy(w.original, (const void *)w.va, w.len);
        if (!WriteCode(w.va, w.bytes, w.len)) {
            Log("module %s: write at 0x%08X failed (error %lu); restoring its writes",
                VF2_MODULE_NAMES[plan.module], w.va, GetLastError());
            for (unsigned j = 0; j < i; ++j)
                WriteCode(plan.writes[j].va, plan.writes[j].original, plan.writes[j].len);
            // A write that failed at VirtualProtect wrote nothing; one whose
            // restore failed did write, so put it back too.
            WriteCode(w.va, w.original, w.len);
            VF2Fun_Status.writeMasks[plan.module] = 0;
            return false;
        }
        VF2Fun_Status.writeMasks[plan.module] |= 1u << i;
    }
    for (unsigned i = 0; i < plan.count; ++i)
        Installed[InstalledCount++] = plan.writes[i];
    return true;
}

// ================================================================ game ABI (shared)
typedef int (__cdecl *GetRandomFn)(int limit);
static const GetRandomFn GetRandom = (GetRandomFn)VF2_GET_RANDOM;

static unsigned char *VillagerByIndex(int index) {
    if (index < 0 || index >= 30) return 0;
    return (unsigned char *)VF2_VILLAGER_MANAGER + VF2_VILLAGER_ARRAY_OFFSET + index * VF2_VILLAGER_STRIDE;
}

// ================================================================ module: older_pregnancies
// Allow Older Pregnancies (the B200 static build's .vf2preg feature)
//   1. CVillagerState::ChanceOfPregnancy entry detour (0x4A0810). Real
//      prologue bytes are stolen into a trampoline and the call resumes at
//      0x4A0818.
//   2. Failed-attempt cooldown store in CVillagerPlans::ProcessCurrentPlan
//      (0x49F6DF). The 6-byte `mov [eax+25AE0h],ebx` jumps here and the
//      store is done only when B200 would do it.
//   3. The four CFamilyTree::CanStartNextGeneration call sites, retargeted
//      to the B200 older-age wrapper.
// The logic is a line-for-line port of B200's helpers (VF2RollOlderPregnancy,
// VF2StoreTryForBabyCooldownMaybe, VF2CanStartNextGenerationAtOlderAge) and
// of its two cave trampolines.
static bool AllowOlderPregnancies;

typedef bool (__thiscall *ChanceOfPregnancyFn)(void *state, int motherAge, int fatherAge, int fatherFertility);
typedef bool (__thiscall *CanStartNextGenerationFn)(void *tree, bool force);
typedef int (__thiscall *CountSurvivingChildrenFn)(void *tree);
typedef void (__thiscall *TutorialQueueFn)(void *tip, int stringId, int scene, bool flag);

static ChanceOfPregnancyFn OriginalChanceOfPregnancy;  // the trampoline
static const CanStartNextGenerationFn NativeCanStartNextGeneration =
    (CanStartNextGenerationFn)VF2_CAN_START_NEXT_GENERATION;
static const CountSurvivingChildrenFn CountSurvivingChildren =
    (CountSurvivingChildrenFn)VF2_COUNT_SURVIVING_CHILDREN;
static const TutorialQueueFn TutorialQueue = (TutorialQueueFn)VF2_TUTORIAL_QUEUE;
static void *const TutorialTip = (void *)VF2_TUTORIAL_TIP;
static const int eStringPregnancyTutorial = 0x868;
static const int eGameSceneNone = 0;

static int PregnancyAgeYears(int internalAge) {
    return internalAge / 20;
}

static int OlderPregnancyCapTenths(int ageYears) {
    if (ageYears <= 59) return (60 - ageYears) * 10;
    if (ageYears <= 68) return 69 - ageYears;
    return 1;
}

static int StockPregnancyChanceWithoutCutoff(int motherFertility, int fatherFertility,
                                             int motherAgeYears, int fatherAgeYears) {
    int chance = 105 - (100 - motherFertility) / 3 - (100 - fatherFertility) / 3;
    if (fatherAgeYears >= 41) {
        chance -= (fatherAgeYears - 40) / 5;
    }
    if (motherAgeYears > 30) {
        chance -= 2 * (motherAgeYears - 20);
    }
    return chance;
}

// B200 VF2RollOlderPregnancy.
static int RollOlderPregnancy(void *villagerState, int motherInternalAge, int fatherInternalAge,
                              int fatherFertility) {
    int motherAgeYears = PregnancyAgeYears(motherInternalAge);
    int fatherAgeYears = PregnancyAgeYears(fatherInternalAge);
    int olderAgeYears = motherAgeYears > fatherAgeYears ? motherAgeYears : fatherAgeYears;
    if (olderAgeYears < 50) {
        return 0;
    }
    int motherFertility = *(int *)((unsigned char *)villagerState + 0x4C);
    int chanceTenths = StockPregnancyChanceWithoutCutoff(
        motherFertility, fatherFertility, motherAgeYears, fatherAgeYears) * 10;
    int ageCapTenths = OlderPregnancyCapTenths(olderAgeYears);
    if (chanceTenths > ageCapTenths) chanceTenths = ageCapTenths;
    if (chanceTenths < 1) chanceTenths = 1;

    if (GetRandom(1000) >= chanceTenths) {
        return 0;
    }
    TutorialQueue(TutorialTip, eStringPregnancyTutorial, eGameSceneNone, false);
    return 1;
}

// B200's ChanceOfPregnancy cave: flag off or both parents under internal age
// 1000 (50 years) -> the untouched stock body; otherwise the late-age roll's
// answer is the result (there is no fall-through to stock).
// __fastcall with a dummy EDX is ABI-identical to the game's __thiscall:
// ECX = this, three stack arguments, callee pops 12 bytes.
static bool __fastcall ChanceOfPregnancyDetour(void *state, void *, int motherAge, int fatherAge,
                                               int fatherFertility) {
    VF2_COUNT(chanceCalls);
    VF2_NOTE(lastMotherAge, motherAge);
    VF2_NOTE(lastFatherAge, fatherAge);
    if (AllowOlderPregnancies && (motherAge >= 1000 || fatherAge >= 1000)) {
        VF2_COUNT(olderRolls);
        int conceived = RollOlderPregnancy(state, motherAge, fatherAge, fatherFertility);
        if (conceived) VF2_COUNT(olderSuccesses);
        return conceived != 0;
    }
    return OriginalChanceOfPregnancy(state, motherAge, fatherAge, fatherFertility);
}

// B200 VF2StoreTryForBabyCooldownMaybe. B200's two leading predicates
// (VF2IsSameSexMarriage, VF2IsBehaviorSixChildPrivateTimeMarriage) belong to
// the same-sex-marriage and behaviour-patches features. In the vanilla game
// neither can be true: vanilla never makes a same-sex marriage, and the
// six-child predicate is compiled out of every B200 build without Behavior
// Patches. They therefore return false here.
static void __cdecl StoreTryForBabyCooldownMaybe(void *gameState, unsigned deadline,
                                                 int motherInternalAge, int fatherInternalAge) {
    bool olderCouple = motherInternalAge >= 50 * 20 || fatherInternalAge >= 50 * 20;
    if (!AllowOlderPregnancies || !olderCouple) {
        *(unsigned *)((unsigned char *)gameState + VF2_GAME_STATE_TRY_FOR_BABY_DEADLINE) = deadline;
        VF2_COUNT(cooldownStores);
    } else {
        VF2_COUNT(cooldownSkips);
    }
}

static unsigned CooldownResume = VF2_COOLDOWN_RESUME;

// Reached by the jmp written over `mov [eax+25AE0h],ebx` at 0x49F6DF.
// Registers there (proved by the pins chance_caller/cooldown_block):
//   eax = theGameState*, ebx = deadline (now + 4B0h),
//   esi = mother's CVillagerState (= mother + 6AF4h), edi = father.
// The mother's internal age is [esi - 6AF4h + 6A54h] = [esi - 0A0h]; the
// father's is [edi + 6A54h]. Every register and the flags are restored, then
// execution resumes at 0x49F6E5 exactly as after the stock store.
static __declspec(naked) void CooldownStub() {
    __asm {
        pushfd
        pushad
        push dword ptr [edi + 0x6A54]
        push dword ptr [esi - 0xA0]
        push ebx
        push eax
        call StoreTryForBabyCooldownMaybe
        add esp, 16
        popad
        popfd
        jmp dword ptr [CooldownResume]
    }
}

// B200 VF2CanStartNextGenerationAtOlderAge.
static bool __fastcall CanStartNextGenerationAtOlderAge(void *tree, void *, bool force) {
    VF2_COUNT(nextGenerationCalls);
    bool stockEligible = NativeCanStartNextGeneration(tree, force);
    if (stockEligible || !AllowOlderPregnancies) {
        return stockEligible;
    }
    if (CountSurvivingChildren(tree) <= 0) {
        return false;
    }
    int oldestInternalAge = -1;
    for (int index = 0; index < 30; ++index) {
        unsigned char *data = VillagerByIndex(index);
        bool active = data[0x1BB84] != 0;
        bool leftHome = data[0x1BB88] != 0;
        int health = *(int *)(data + 0x6B00);
        if (!active || leftHome || health <= 0) continue;
        int internalAge = *(int *)(data + 0x6A54);
        if (internalAge > oldestInternalAge) oldestInternalAge = internalAge;
    }
    bool granted = oldestInternalAge >= 60 * 20;
    if (granted) VF2_COUNT(nextGenerationOlderGrants);
    return granted;
}

static void PlanOlderPregnancies(Plan &plan) {
    // The detour must be able to reach the stock body before the entry jmp
    // goes live: the trampoline is built (and made RX) before any write.
    OriginalChanceOfPregnancy = (ChanceOfPregnancyFn)plan.Trampoline(
        VF2_CHANCE_OF_PREGNANCY, VF2_CHANCE_OF_PREGNANCY_STEAL);
    plan.Jmp(VF2_CHANCE_OF_PREGNANCY, VF2_CHANCE_OF_PREGNANCY_STEAL, (const void *)&ChanceOfPregnancyDetour);
    plan.Jmp(VF2_COOLDOWN_STORE, VF2_COOLDOWN_STORE_LEN, (const void *)&CooldownStub);
    for (size_t i = 0; i < sizeof(VF2_NEXT_GENERATION_CALLSITES) / sizeof(unsigned); ++i)
        plan.Retarget(VF2_NEXT_GENERATION_CALLSITES[i], (const void *)&CanStartNextGenerationAtOlderAge);
    if (!OriginalChanceOfPregnancy) plan.ok = false;
}

// ================================================================ module: scene_null_guard
// B200 patch_ldwscene_setactive_null_guard. ldwScene::SetActive(bool)
// writes its argument through this->field_4 (a bound active-flag pointer)
// before anything else; one scene slot reachable once a family has six
// children never binds it, and stock crashes on the null write. B200 turns
// `mov eax,[esi+4]; mov [eax],bl` into: load; if null return through the
// function's own epilogue; else store and continue. Bound scenes are
// unchanged.
//
// Vanilla 0x40D1D0: push ebx; mov ebx,[esp+8]; test bl,bl; push esi;
// mov esi,ecx; [0x40D1DA: mov eax,[esi+4]; mov [eax],bl]; je ...
// The je at 0x40D1DF uses the flags of `test bl,bl`, so the stub keeps them.
// Early return = vanilla's epilogue `pop esi; pop ebx; ret 4`.
static bool SceneNullGuard;
static unsigned SceneActiveResume = VF2_SCENE_ACTIVE_RESUME;

#ifdef VF2FUN_TEST_COUNTERS
#define SCENE_COUNT_WRITE inc dword ptr [VF2Fun_TestCounters.sceneActiveWrites]
#define SCENE_COUNT_SKIP inc dword ptr [VF2Fun_TestCounters.sceneNullSkips]
#else
#define SCENE_COUNT_WRITE nop
#define SCENE_COUNT_SKIP nop
#endif

static __declspec(naked) void SceneActiveWriteStub() {
    __asm {
        mov eax, dword ptr [esi + 4]
        pushfd
        test eax, eax
        jz null_flag
        SCENE_COUNT_WRITE
        popfd
        mov byte ptr [eax], bl
        jmp dword ptr [SceneActiveResume]
    null_flag:
        SCENE_COUNT_SKIP
        popfd
        pop esi
        pop ebx
        ret 4
    }
}

static void PlanSceneNullGuard(Plan &plan) {
    plan.Jmp(VF2_SCENE_ACTIVE_WRITE, VF2_SCENE_ACTIVE_WRITE_LEN, (const void *)&SceneActiveWriteStub);
}

// ================================================================ module: fix_vanilla_bugs
// B200 "Fix Vanilla Game Bugs" (.vf2bugs). B200's stubs test the flag byte
// first and run the stock instruction when it is zero; here "off" installs
// nothing, which is the same stock instruction.
static bool FixVanillaGameBugs;

// (a) patch_options_pause_yes_idempotent. Settings "Pause Game: Yes" adds
// 999 to options[+25B18h] unconditionally, so Yes while already paused
// stored 2008 and one Space left the game at 1009 (still paused). B200:
// cmp [field],3E7h; jge skip; add [field],3E7h. Vanilla's register is esi.
static unsigned PauseYesResume = VF2_PAUSE_YES_RESUME;

static __declspec(naked) void PauseYesStub() {
    __asm {
        cmp dword ptr [esi + 0x25B18], 0x3E7
        jge already_paused
        add dword ptr [esi + 0x25B18], 0x3E7
    already_paused:
        jmp dword ptr [PauseYesResume]
    }
}

// (b) patch_title_menu_stale_hotspot. The constructor's old Change Player
// rect gets top = bottom + 1 (0x118), an empty inclusive rect, so neither
// the click test nor the hover PtInRect in HandleMouse can match it.
static unsigned TitleHotspotResume = VF2_TITLE_HOTSPOT_RESUME;

static __declspec(naked) void TitleHotspotStub() {
    __asm {
        mov dword ptr [esi + 0xA0], 0x118
        jmp dword ptr [TitleHotspotResume]
    }
}
static_assert(VF2_TITLE_HOTSPOT_BOTTOM + 1 == 0x118, "empty-rect top");

static void PlanFixVanillaBugs(Plan &plan) {
    plan.Jmp(VF2_PAUSE_YES_ADD, VF2_PAUSE_YES_ADD_LEN, (const void *)&PauseYesStub);
    plan.Jmp(VF2_TITLE_HOTSPOT_TOP_STORE, VF2_TITLE_HOTSPOT_TOP_STORE_LEN, (const void *)&TitleHotspotStub);
}

// ================================================================ module table
struct ModuleDef {
    void (*plan)(Plan &);
    bool *enabled;
};

static const ModuleDef Modules[] = {
    { PlanOlderPregnancies, &AllowOlderPregnancies },  // VF2_MODULE_OLDER_PREGNANCIES
    { PlanSceneNullGuard, &SceneNullGuard },           // VF2_MODULE_SCENE_NULL_GUARD
    { PlanFixVanillaBugs, &FixVanillaGameBugs },       // VF2_MODULE_FIX_VANILLA_BUGS
};
static_assert(sizeof(Modules) / sizeof(Modules[0]) == VF2_MODULE_COUNT, "module table out of step with the sites");

static bool SettingOn(const wchar_t *key) {
    wchar_t ini[MAX_PATH];
    if (_snwprintf_s(ini, MAX_PATH, _TRUNCATE, L"%svf2fun.ini", Folder) < 0)
        return false;
    return GetPrivateProfileIntW(L"Patches", key, 0, ini) == 1;
}

static Plan Plans[VF2_MODULE_COUNT];

static void InstallAll() {
    unsigned requested = 0;
    for (unsigned m = 0; m < VF2_MODULE_COUNT; ++m) {
        *Modules[m].enabled = SettingOn(VF2_MODULE_INI_KEYS[m]);
        if (*Modules[m].enabled) requested |= 1u << m;
        Log("setting %ls=%d", VF2_MODULE_INI_KEYS[m], *Modules[m].enabled ? 1 : 0);
    }
    VF2Fun_Status.requestedMask = requested;
    // Off means stock: a module that is off writes nothing.
    if (!requested) return;

    if (!PinsMatch(VF2_MODULE_CORE)) {
        Log("a core pin does not match; installing nothing");
        VF2Fun_Status.refusedMask = requested;
        return;
    }
    unsigned planned = 0;
    for (unsigned m = 0; m < VF2_MODULE_COUNT; ++m) {
        if (!(requested & (1u << m))) continue;
        if (!PinsMatch(m)) {
            Log("module %s: pins do not match; installing nothing for it", VF2_MODULE_NAMES[m]);
            continue;
        }
        VF2Fun_Status.pinsOkMask |= 1u << m;
        Plan &plan = Plans[m];
        plan.module = m;
        plan.count = 0;
        plan.ok = true;
        Modules[m].plan(plan);
        if (plan.ok) planned |= 1u << m;
        else Log("module %s: could not be planned; installing nothing for it", VF2_MODULE_NAMES[m]);
    }
    if (Arena) {
        DWORD old = 0;
        if (!VirtualProtect(Arena, 4096, PAGE_EXECUTE_READ, &old)) {
            Log("could not make the trampoline page executable; installing nothing");
            VirtualFree(Arena, 0, MEM_RELEASE);
            Arena = 0;
            VF2Fun_Status.refusedMask = requested;
            return;
        }
        FlushInstructionCache(GetCurrentProcess(), Arena, 4096);
        VF2Fun_Status.trampolinePage = (unsigned)Arena;
    }
    for (unsigned m = 0; m < VF2_MODULE_COUNT; ++m) {
        if (!(planned & (1u << m))) continue;
        if (Apply(Plans[m])) {
            VF2Fun_Status.installedMask |= 1u << m;
            Log("module %s installed (%u writes)", VF2_MODULE_NAMES[m], Plans[m].count);
        }
    }
    VF2Fun_Status.refusedMask = requested & ~VF2Fun_Status.installedMask;
}

// ---------------------------------------------------------------- entry
// Called once by the executable's loader stub, before theGame::Init runs and
// before the game loop starts.
extern "C" __declspec(dllexport) void __cdecl VF2Fun_Startup() {
    static bool started = false;
    if (started) return;
    started = true;

    DWORD n = GetModuleFileNameW(Module, Folder, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    wchar_t *slash = wcsrchr(Folder, L'\\');
    if (!slash) return;
    slash[1] = 0;

    Log("vf2fun started (%u modules)", VF2_MODULE_COUNT);
    InstallAll();
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        Module = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
