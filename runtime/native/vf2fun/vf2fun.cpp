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
//   career_room_goals  career-room goals rebuilt from owned upgrades on load
//   time_controls      "Time Controls" dialog from the store screen (new; vf2fun_time.inc)
//   event_collectable_slot_replacement  island events replace the oldest unpicked collectable
//   power_failure_event  the Power Failure event's Take-a-chance outcome
//   older_villager_mortality  the old-age death curve (.vf2mort; the mortality half)
//
// The VF2Fun_Status export is the DLL's install-status block (documented
// below); it is part of the shipped interface. Per-call counters exist only
// in test builds (VF2FUN_TEST_COUNTERS, never defined by native/build.bat).

#define WIN32_LEAN_AND_MEAN
// The Time Controls dialog uses modern (comctl32 v6) controls through the
// manifest dependency below (embedded by the /MANIFEST:EMBED link option of
// native/build.bat); ISOLATION_AWARE makes this DLL's own windows use it
// without touching the game's.
#define ISOLATION_AWARE_ENABLED 1
#include <windows.h>
#include <commctrl.h>
#include <stdio.h>
#include <string.h>

#pragma comment(lib, "user32.lib")
#pragma comment(linker, "/MANIFESTDEPENDENCY:\"type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='x86' publicKeyToken='6595b64144ccf1df' language='*'\"")

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
    unsigned timeButtonsAdded;   // store screens given the Time Controls button
    unsigned timeDialogOpens;    // clicks on that button
    unsigned timeWarpsApplied;   // villagers handed the queued warp ticks
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
    bool data;  // a 4-byte vtable slot (never made executable), not code
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

    HookWrite *Add(unsigned va, unsigned len, bool data = false) {
        if (!ok || count >= kMaxWrites || len < (data ? 4u : 5u) || len > kMaxWriteLen) {
            ok = false;
            return 0;
        }
        HookWrite &w = writes[count++];
        memset(&w, 0, sizeof w);
        w.va = va;
        w.len = len;
        w.data = data;
        return &w;
    }
    // Replace the 4-byte function pointer in the vtable slot at va with `to`.
    void Slot(unsigned va, const void *to) {
        HookWrite *w = Add(va, 4, true);
        if (!w) return;
        unsigned target = (unsigned)to;
        memcpy(w->bytes, &target, 4);
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
    // Retarget the 6-byte `jcc rel32` at va to `to`, keeping its condition
    // (pinned as 0F 80..8F by gen_sites).
    void RetargetJcc(unsigned va, const void *to) {
        HookWrite *w = Add(va, 6);
        if (!w) return;
        w->bytes[0] = ((const unsigned char *)va)[0];
        w->bytes[1] = ((const unsigned char *)va)[1];
        int rel = (int)((unsigned)to - (va + 6));
        memcpy(w->bytes + 2, &rel, 4);
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
static bool WriteCode(unsigned va, const unsigned char *bytes, unsigned len, bool data = false) {
    DWORD old = 0;
    // A data write (a vtable slot) never makes its page executable.
    if (!VirtualProtect((void *)va, len, data ? PAGE_READWRITE : PAGE_EXECUTE_READWRITE, &old))
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
        if (!WriteCode(w.va, w.bytes, w.len, w.data)) {
            Log("module %s: write at 0x%08X failed (error %lu); restoring its writes",
                VF2_MODULE_NAMES[plan.module], w.va, GetLastError());
            for (unsigned j = 0; j < i; ++j)
                WriteCode(plan.writes[j].va, plan.writes[j].original, plan.writes[j].len, plan.writes[j].data);
            // A write that failed at VirtualProtect wrote nothing; one whose
            // restore failed did write, so put it back too.
            WriteCode(w.va, w.original, w.len, w.data);
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

// ================================================================ module: time_controls
#include "vf2fun_time.inc"

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

// (c) patch_title_menu_start_over_confirms. The `je` taken for Start Over's id
// in theMenuScene::HandleMessage (0x443F5C) goes here instead of the shared
// Play / Start Over handler (esi = the menu scene, the stack as at the jump):
//   no village yet (GameStats[0] == 0) -> the stock handler, unchanged;
//   else the click sound, ShowMessageBox(this, eSayConfirmRestart, 0, true);
//     non-zero (No) -> the function's own "return true" (menu stays up);
//     zero (Yes)    -> the live new-player sequence on the game state
//       [this+0Ch]: speed field >= 999 -> 10; theGameState::Init with the six
//       name dwords +25ABCh..+25AD0h kept; SaveCurrentGame; then the stock
//       handler just after its own click sound (it starts the intro story).
// B200's stub does exactly this (work/patch_mobile_furniture_pack.py,
// patch_title_menu_start_over_confirms). It holds the game state in esi; here
// esi stays the menu scene, which the stock continuation needs, so the game
// state is reloaded from [esi+0Ch] (a field nothing here changes).
static const unsigned StartOverGameStats = VF2_GAME_STATS;
static const unsigned StartOverSoundObject = VF2_SOUND_OBJECT;
static const unsigned StartOverSoundPlay = VF2_SOUND_PLAY;
static const unsigned StartOverShowMessageBox = VF2_SHOW_MESSAGE_BOX;
static const unsigned StartOverInit = VF2_GAME_STATE_INIT;
static const unsigned StartOverSave = VF2_GAME_STATE_SAVE_CURRENT;
static const unsigned StartOverSharedPath = VF2_START_OVER_SHARED_PATH;
static const unsigned StartOverReturnTrue = VF2_START_OVER_RETURN_TRUE;
static const unsigned StartOverAfterSound = VF2_START_OVER_AFTER_SOUND;
static_assert(VF2_START_OVER_CONFIRM_STRING_ID == 0x744 && VF2_SOUND_CLICK == 0xB9 &&
                  VF2_GAME_STATE_NAME_FIRST == 0x25ABC && VF2_GAME_STATE_NAME_LAST == 0x25AD0 &&
                  VF2_MENU_GAME_STATE_FIELD == 0xC && VF2_PAUSE_FIELD == 0x25B18,
              "the Start Over stub's literals follow the sites module");

static __declspec(naked) void StartOverStub() {
    __asm {
        mov eax, dword ptr [StartOverGameStats]
        cmp dword ptr [eax], 0
        je stock_path
        push 0xB9
        mov ecx, dword ptr [StartOverSoundObject]
        call dword ptr [StartOverSoundPlay]
        push 1
        push 0
        push 0x744
        push esi
        call dword ptr [StartOverShowMessageBox]
        add esp, 16
        test eax, eax
        jne return_true
        mov ecx, dword ptr [esi + 0xC]
        cmp dword ptr [ecx + 0x25B18], 0x3E7
        jl no_clamp
        mov dword ptr [ecx + 0x25B18], 0xA
    no_clamp:
        push dword ptr [ecx + 0x25AD0]
        push dword ptr [ecx + 0x25ACC]
        push dword ptr [ecx + 0x25AC8]
        push dword ptr [ecx + 0x25AC4]
        push dword ptr [ecx + 0x25AC0]
        push dword ptr [ecx + 0x25ABC]
        call dword ptr [StartOverInit]
        mov ecx, dword ptr [esi + 0xC]
        pop dword ptr [ecx + 0x25ABC]
        pop dword ptr [ecx + 0x25AC0]
        pop dword ptr [ecx + 0x25AC4]
        pop dword ptr [ecx + 0x25AC8]
        pop dword ptr [ecx + 0x25ACC]
        pop dword ptr [ecx + 0x25AD0]
        call dword ptr [StartOverSave]
        jmp dword ptr [StartOverAfterSound]
    stock_path:
        jmp dword ptr [StartOverSharedPath]
    return_true:
        jmp dword ptr [StartOverReturnTrue]
    }
}

// (d) patch_title_menu_refresh_on_activate. theMenuScene::UpdateShowPlayer
// becomes the one refresh point (see the sites module for the four hooks).
typedef void *(__thiscall *GetLargeFontFn)(void *strings);
typedef const char *(__thiscall *GetStringFn)(void *strings, int id);
typedef void (__thiscall *ButtonSetTextFn)(void *button, const char *text, unsigned c1, unsigned c2,
                                           unsigned c3, void *font);
typedef void (__thiscall *UpdateShowPlayerFn)(void *scene);
static const GetLargeFontFn TitleGetLargeFont = (GetLargeFontFn)VF2_STRING_GET_LARGE_FONT;
static const GetStringFn TitleGetString = (GetStringFn)VF2_STRING_GET_STRING;
static const ButtonSetTextFn TitleButtonSetText = (ButtonSetTextFn)VF2_BUTTON_SET_TEXT;
static UpdateShowPlayerFn OriginalUpdateShowPlayer;  // the trampoline

// The constructor's own label choice (0x4433F5..0x44346C): the large font of
// the string manager [this+14h], the colour three times, "Play" (0x775) or,
// with a village (GameStats[0] != 0), "Continue" (0x280), set on the Play
// button [this+0D8h]. B200's label stub repeats these calls in this order.
static void ApplyTitleLabel(unsigned char *scene) {
    void *strings = *(void **)(scene + VF2_MENU_STRING_MANAGER_FIELD);
    void *font = TitleGetLargeFont(strings);
    unsigned colour = *(unsigned *)VF2_TITLE_TEXT_COLOUR;
    int id = *(int *)VF2_GAME_STATS != 0 ? VF2_TITLE_CONTINUE_STRING_ID : VF2_TITLE_PLAY_STRING_ID;
    const char *text = TitleGetString(strings, id);
    TitleButtonSetText(*(void **)(scene + VF2_MENU_PLAY_BUTTON_FIELD), text, colour, colour, colour, font);
}

static void __fastcall UpdateShowPlayerDetour(void *scene, void *) {
    ApplyTitleLabel((unsigned char *)scene);
    OriginalUpdateShowPlayer(scene);
}

// Jumped to from 0x443C00 in place of `mov edx,[ebx+0F0h]; push edx` (the
// argument of the name's AddControl): when no control with Manage Games' id
// is in the scene, add the Manage Games button first, as B200 does; then
// redo the two instructions and resume at 0x443C07 (ebx = the menu scene).
static const unsigned ManageGetControl = VF2_SCENE_GET_CONTROL;
static const unsigned ManageAddControl = VF2_SCENE_ADD_CONTROL;
static const unsigned ManageResume = VF2_SHOW_PLAYER_ADD_NAME_RESUME;
static_assert(VF2_MENU_MANAGE_GAMES_ID_FIELD == 0xC4 && VF2_MENU_MANAGE_GAMES_BUTTON_FIELD == 0xE4 &&
                  VF2_MENU_NAME_BUTTON_FIELD == 0xF0,
              "the Manage Games stub's literals follow the sites module");

static __declspec(naked) void ManageGamesStub() {
    __asm {
        push dword ptr [ebx + 0xC4]
        mov ecx, ebx
        call dword ptr [ManageGetControl]
        test eax, eax
        jne already_shown
        push dword ptr [ebx + 0xE4]
        mov ecx, ebx
        call dword ptr [ManageAddControl]
    already_shown:
        mov edx, dword ptr [ebx + 0xF0]
        push edx
        jmp dword ptr [ManageResume]
    }
}

// Replace the two calls that end Activate(true) and the name prompt's cancel
// path: make the original call, then refresh the title (esi = the menu scene
// in both stock functions; the callee preserves it).
static const unsigned ActivateTailTarget = VF2_MENU_ACTIVATE_TAIL_TARGET;
static const unsigned NicknameDialogDtor = VF2_NICKNAME_DIALOG_DTOR;
static const unsigned RefreshTitle = VF2_UPDATE_SHOW_PLAYER;

static __declspec(naked) void ActivateTailWrapper() {
    __asm {
        call dword ptr [ActivateTailTarget]
        mov ecx, esi
        call dword ptr [RefreshTitle]
        ret
    }
}

static __declspec(naked) void NicknameCancelWrapper() {
    __asm {
        call dword ptr [NicknameDialogDtor]
        mov ecx, esi
        call dword ptr [RefreshTitle]
        ret
    }
}

static void PlanFixVanillaBugs(Plan &plan) {
    plan.Jmp(VF2_PAUSE_YES_ADD, VF2_PAUSE_YES_ADD_LEN, (const void *)&PauseYesStub);
    plan.Jmp(VF2_TITLE_HOTSPOT_TOP_STORE, VF2_TITLE_HOTSPOT_TOP_STORE_LEN, (const void *)&TitleHotspotStub);
    plan.RetargetJcc(VF2_START_OVER_BRANCH, (const void *)&StartOverStub);
    OriginalUpdateShowPlayer = (UpdateShowPlayerFn)plan.Trampoline(VF2_UPDATE_SHOW_PLAYER,
                                                                  VF2_UPDATE_SHOW_PLAYER_STEAL);
    plan.Jmp(VF2_UPDATE_SHOW_PLAYER, VF2_UPDATE_SHOW_PLAYER_STEAL, (const void *)&UpdateShowPlayerDetour);
    plan.Jmp(VF2_SHOW_PLAYER_ADD_NAME, VF2_SHOW_PLAYER_ADD_NAME_LEN, (const void *)&ManageGamesStub);
    plan.Retarget(VF2_MENU_ACTIVATE_TAIL_CALL, (const void *)&ActivateTailWrapper);
    plan.Retarget(VF2_NICKNAME_CANCEL_DTOR_CALL, (const void *)&NicknameCancelWrapper);
    if (!OriginalUpdateShowPlayer) plan.ok = false;
}

// ================================================================ module: career_room_goals
// B200 patch_career_room_goal_reconciliation, load hook: the call to
// CTech::LoadState inside theGameState::Load (0x42A75E) goes to this
// wrapper, which runs the native load and then the game's own CTech::Level
// for the three career rooms, so goals 0x36-0x38 are rebuilt from the
// upgrades this save owns. Port of B200's VF2TechLoadStateAndReconcile and
// VF2ReconcileCareerRoomGoals. (B200's second call, after the Cheat
// Upgrades "Reset Achievements" action, has no vanilla counterpart.)
static bool CareerRoomGoalReconciliation;

typedef bool (__thiscall *TechLoadStateFn)(void *tech, const void *state);
typedef int (__thiscall *TechLevelFn)(void *tech, int tech_);
static const TechLoadStateFn NativeTechLoadState = (TechLoadStateFn)VF2_TECH_LOAD_STATE;
static const TechLevelFn TechLevel = (TechLevelFn)VF2_TECH_LEVEL;
static void *const Tech = (void *)VF2_TECH;
enum { eTechKitchen = 0, eTechOffice = 1, eTechWorkshop = 2 };

static void ReconcileCareerRoomGoals() {
    TechLevel(Tech, eTechKitchen);
    TechLevel(Tech, eTechOffice);
    TechLevel(Tech, eTechWorkshop);
}

static bool __fastcall TechLoadStateAndReconcile(void *tech, void *, const void *state) {
    bool loaded = NativeTechLoadState(tech, state);
    if (loaded) ReconcileCareerRoomGoals();
    return loaded;
}

static void PlanCareerRoomGoals(Plan &plan) {
    plan.Retarget(VF2_TECH_LOAD_STATE_CALL, (const void *)&TechLoadStateAndReconcile);
}

// ================================================================ module: event_collectable_slot_replacement
// B200 patch_event_collectable_slot_replacement. CCollectableItem keeps exactly
// two event slots, at +34Ch and +368h (1Ch apart: +0 active, +8 spawn stamp,
// +14h the villager walking to it, -1 none). Add(carrying, point, false) takes
// the first free slot and RETURNS WITHOUT SPAWNING when both are busy;
// Add(.., true) always writes slot 0. Natural spawns keep the pair busy most of
// the time, so the native events that spawn collectables (Bug Whisperer twice,
// Neighbor Collectible once) mostly spawned nothing. Owner decision: an EVENT
// spawn replaces the oldest unpicked collectable. The three native call sites
// go through the thunk below; everything else (Update's natural spawns, the
// native Add itself) is untouched. This is B200's VF2EventCollectableAddImpl
// and helpers, ported function for function (the tests compare their text).
static bool EventCollectableSlotReplacement;

typedef void (__thiscall *CollectableAddFn)(void *item, int carrying, int x, int y, int force);
typedef void (__thiscall *CollectableRemoveFn)(void *item, int slot);
typedef void *(__cdecl *GameStateGetFn)();
typedef unsigned (__thiscall *SecondsFromGameStartFn)(void *gameState);
static const CollectableAddFn NativeCollectableAdd = (CollectableAddFn)VF2_COLLECTABLE_ADD;
static const CollectableRemoveFn NativeCollectableRemove = (CollectableRemoveFn)VF2_COLLECTABLE_REMOVE;
static const GameStateGetFn NativeGameStateGet = (GameStateGetFn)VF2_GAME_STATE_GET;
static const SecondsFromGameStartFn NativeSecondsFromGameStart = (SecondsFromGameStartFn)VF2_GAME_SECONDS_FROM_START;
static_assert(VF2_COLLECTABLE_SLOT_BASE == 0x34C && VF2_COLLECTABLE_SLOT_STRIDE == 0x1C &&
                  VF2_COLLECTABLE_STAMP_OFFSET == 8 && VF2_COLLECTABLE_PICKED_OFFSET == 0x14 &&
                  VF2_COLLECTABLE_STAMP_DELAY == 0x78,
              "the collectable slot layout follows the sites module");

static unsigned char *EventCollectableSlot(int slot) {
    return (unsigned char *)VF2_COLLECTABLE_ITEM + 0x34C + slot * 0x1C;
}

static bool EventCollectableSlotBusy(int slot) {
    return EventCollectableSlot(slot)[0] != 0;
}

static bool EventCollectableSlotPicked(int slot) {
    return *(int *)(EventCollectableSlot(slot) + 0x14) != -1;
}

static unsigned int EventCollectableSlotStamp(int slot) {
    return *(unsigned int *)(EventCollectableSlot(slot) + 0x08);
}

// The slot and spawn stamp of the item the previous event spawn produced.
// The Bug Whisperer spawns TWICE back to back; an item this burst just spawned
// is never sacrificed. "This burst" is bounded by the game clock: the record
// must still carry the stamp of the CURRENT game second (Add writes seconds +
// 0x78 at activation).
static int gLastEventSpawnSlot = -1;
static unsigned int gLastEventSpawnStamp = 0;

static unsigned int EventCollectableStampNow() {
    void *clock = NativeGameStateGet();
    return clock ? NativeSecondsFromGameStart(clock) + 0x78 : 0;
}

static bool EventCollectableSlotFreshFromBurst(int slot) {
    if (gLastEventSpawnSlot != slot || !EventCollectableSlotBusy(slot)) return false;
    unsigned int const stamp = EventCollectableSlotStamp(slot);
    return stamp == gLastEventSpawnStamp && stamp == EventCollectableStampNow();
}

// The slot an event spawn may take over when both are busy: never the item
// this burst just spawned, else the one nobody is walking to, else the older
// of the two.
static int EventCollectableVictim() {
    bool const fresh0 = EventCollectableSlotFreshFromBurst(0);
    bool const fresh1 = EventCollectableSlotFreshFromBurst(1);
    if (fresh0 != fresh1) return fresh0 ? 1 : 0;
    bool const picked0 = EventCollectableSlotPicked(0);
    bool const picked1 = EventCollectableSlotPicked(1);
    if (picked0 != picked1) return picked0 ? 1 : 0;
    return EventCollectableSlotStamp(1) < EventCollectableSlotStamp(0) ? 1 : 0;
}

// The native force path only ever writes slot 0, so when slot 0 must survive
// its record is moved to slot 1 first.
static void MoveEventCollectableSlot(int from, int to) {
    unsigned char *source = EventCollectableSlot(from);
    unsigned char *dest = EventCollectableSlot(to);
    for (int i = 0; i < 0x1C; ++i) dest[i] = source[i];
    source[0] = 0;
}

// A sacrificed record is kept aside until the native spawn has actually
// activated: the forced RANDOM path (Neighbor Collectible) can give up after a
// thousand invalid spawn positions and return without activating, and losing a
// collectable for nothing is exactly what this helper exists to end.
static void CopyEventCollectableSlot(int slot, unsigned char *dest) {
    unsigned char *source = EventCollectableSlot(slot);
    for (int i = 0; i < 0x1C; ++i) dest[i] = source[i];
}

static void RestoreEventCollectableSlot(int slot, unsigned char const *source) {
    unsigned char *dest = EventCollectableSlot(slot);
    for (int i = 0; i < 0x1C; ++i) dest[i] = source[i];
}

static void __cdecl EventCollectableAddImpl(void *item, int carrying, int x, int y, int force) {
    bool const busy0 = EventCollectableSlotBusy(0);
    bool const busy1 = EventCollectableSlotBusy(1);
    // The slot that must hold the new item afterwards, and the record that
    // was sacrificed to make room (none when a slot was free).
    int freed = -1;
    unsigned char sacrificed[0x1C];
    if (force) {
        if (busy0 && !busy1) {
            MoveEventCollectableSlot(0, 1);
        } else if (busy0 && busy1) {
            int const victim = EventCollectableVictim();
            CopyEventCollectableSlot(victim, sacrificed);
            freed = 0;
            if (victim == 1) {
                MoveEventCollectableSlot(0, 1);
            } else {
                NativeCollectableRemove(item, 0);
            }
        }
    } else if (busy0 && busy1) {
        freed = EventCollectableVictim();
        CopyEventCollectableSlot(freed, sacrificed);
        NativeCollectableRemove(item, freed);
    }
    // Where the native spawn lands: the force path always writes slot 0; the
    // plain path takes the first free slot, which is the one just freed or,
    // when nothing was sacrificed, the first slot that was free.
    int const landed = force ? 0 : (freed >= 0 ? freed : (busy0 ? 1 : 0));
    NativeCollectableAdd(item, carrying, x, y, force != 0);
    if (EventCollectableSlotBusy(landed)) {
        gLastEventSpawnSlot = landed;
        gLastEventSpawnStamp = EventCollectableSlotStamp(landed);
    } else if (freed >= 0) {
        RestoreEventCollectableSlot(freed, sacrificed);
    }
}

// The __thiscall shape the three native call sites already use: ecx = the
// CollectableItem, then carrying, point.x, point.y, force on the stack (the
// point is two words). Forwards ecx and the four words to the cdecl body and
// pops the caller's 16 bytes exactly as Add does.
static __declspec(naked) void EventCollectableAddThunk() {
    __asm {
        push dword ptr [esp + 16]
        push dword ptr [esp + 16]
        push dword ptr [esp + 16]
        push dword ptr [esp + 16]
        push ecx
        call EventCollectableAddImpl
        add esp, 20
        ret 16
    }
}

static void PlanEventCollectables(Plan &plan) {
    for (size_t i = 0; i < sizeof(VF2_EVENT_COLLECTABLE_ADD_CALLSITES) / sizeof(unsigned); ++i)
        plan.Retarget(VF2_EVENT_COLLECTABLE_ADD_CALLSITES[i], (const void *)&EventCollectableAddThunk);
}

// ================================================================ module: power_failure_event
// B200 patch_power_failure_event. Stock CEventThePowerFailure: choice A resets
// the food store; choice B ("Take a chance") used to hit 0-3 random villagers.
// B200 rolls once in CalcAward (1 in 4 = the food was bad, result text 0x9BE,
// otherwise 0x9BD) and on a bad roll gives every living villager at home a 15%
// upset stomach. State is per event pointer in four slots, one-shot, not
// persisted. The class's three vtable slots (CalcAward, GetResultDescription,
// ImpactGame) are replaced; the code is B200's VF2PowerFailure* helpers.
static bool PowerFailureEvent;

typedef void (__thiscall *EnvironmentSetPropFn)(void *environment, int prop);
typedef void (__thiscall *FoodStoreResetFn)(void *foodStore, bool notify);
typedef void (__thiscall *GiveAllSymptomFn)(void *manager, int symptom, int percent);
static const EnvironmentSetPropFn EnvironmentSetProp = (EnvironmentSetPropFn)VF2_ENVIRONMENT_SET_PROP;
static const FoodStoreResetFn FoodStoreReset = (FoodStoreResetFn)VF2_FOOD_STORE_RESET;
static const GiveAllSymptomFn GiveAllVillagersSymptom = (GiveAllSymptomFn)VF2_GIVE_ALL_VILLAGERS_SYMPTOM;
static_assert(VF2_POWER_FAILURE_RESULT_A == 0x9BC && VF2_POWER_FAILURE_RESULT_B1 == 0x9BD &&
                  VF2_POWER_FAILURE_RESULT_B2 == 0x9BE && VF2_PROP_FOOD_SPOILED == 0x17 &&
                  VF2_SYMPTOM_UPSET_STOMACH == 2 && VF2_POWER_FAILURE_SYMPTOM_PERCENT == 15,
              "the Power Failure constants follow the sites module");

struct PowerFailureState {
    void *event;
    int b2;
};

static PowerFailureState gPowerFailureStates[4] = {};
static unsigned int gPowerFailureReplacement = 0;

static PowerFailureState *FindPowerFailureState(void *event, bool create) {
    if (!event) return 0;
    PowerFailureState *empty = 0;
    for (int i = 0; i < 4; ++i) {
        if (gPowerFailureStates[i].event == event) {
            return &gPowerFailureStates[i];
        }
        if (!empty && !gPowerFailureStates[i].event) {
            empty = &gPowerFailureStates[i];
        }
    }
    if (!create) return 0;
    if (empty) {
        empty->event = event;
        empty->b2 = 0;
        return empty;
    }
    PowerFailureState *slot = &gPowerFailureStates[gPowerFailureReplacement++ % 4];
    slot->event = event;
    slot->b2 = 0;
    return slot;
}

static void ClearPowerFailureState(void *event) {
    PowerFailureState *state = FindPowerFailureState(event, false);
    if (state) {
        state->event = 0;
        state->b2 = 0;
    }
}

static void PowerFailureCalcAward(void *event, int choice) {
    PowerFailureState *state = FindPowerFailureState(event, true);
    if (!state) return;
    state->b2 = (choice != 0) && (GetRandom(4) == 0);
}

static int PowerFailureGetResultDescription(void *event, int choice) {
    if (choice == 0) return 0x9BC;
    PowerFailureState *state = FindPowerFailureState(event, false);
    if (state && state->b2) {
        return 0x9BE;
    }
    return 0x9BD;
}

static void PowerFailureImpactGame(void *event, int choice) {
    if (choice == 0) {
        EnvironmentSetProp((void *)VF2_ENVIRONMENT, 0x17);
        FoodStoreReset((void *)VF2_FOOD_STORE, true);
    } else {
        PowerFailureState *state = FindPowerFailureState(event, false);
        if (state && state->b2) {
            GiveAllVillagersSymptom((void *)VF2_VILLAGER_MANAGER, 2, 15);
        }
    }
    ClearPowerFailureState(event);
}

// The three virtuals: thiscall, the choice on the stack, the callee pops 4.
static void __fastcall PowerFailureCalcAwardSlot(void *self, void *, int choice) {
    PowerFailureCalcAward(self, choice);
}
static int __fastcall PowerFailureDescriptionSlot(void *self, void *, int choice) {
    return PowerFailureGetResultDescription(self, choice);
}
static void __fastcall PowerFailureImpactSlot(void *self, void *, int choice) {
    PowerFailureImpactGame(self, choice);
}

static void PlanPowerFailureEvent(Plan &plan) {
    plan.Slot(VF2_POWER_FAILURE_SLOT_CALC_AWARD, (const void *)&PowerFailureCalcAwardSlot);
    plan.Slot(VF2_POWER_FAILURE_SLOT_DESCRIPTION, (const void *)&PowerFailureDescriptionSlot);
    plan.Slot(VF2_POWER_FAILURE_SLOT_IMPACT, (const void *)&PowerFailureImpactSlot);
}

// ================================================================ module: older_villager_mortality
// B200 patch_older_villager_mortality (.vf2mort), the mortality half. In
// CVillagerManager::AllVillagersRealtimePhysiologyAndProductivityUpkeep the
// stock old-age statement opens with FoodGroupsActive(0) on the villager's
// CVillagerState (ebp) and, on a whole birthday past 55 years + groups, rolls
// GetRandom(100) against 10 * years-over-threshold. With this module on, that
// statement is never run: the decision comes from the table below (B200's
// annual hazard, in millionths, by effective age = displayed age - active food
// groups clamped to 0-4), then SetHealth(0, OldAge) when it says so, and the
// code continues after the statement. The decision is B200's
// VF2RollOlderVillagerMortality, ported line for line; the table is generated
// from B200's formula (vf2_runtime_sites.py) and compared with it by the tests.
static bool OlderVillagerMortality;

static int __cdecl RollOlderVillagerMortality(int internalAge, int activeFoodGroups) {
    if (internalAge < 0 || internalAge % 20 != 0) return 0;
    if (activeFoodGroups < 0) activeFoodGroups = 0;
    if (activeFoodGroups > 4) activeFoodGroups = 4;

    // Preserve the vanilla cumulative nutrition benefit: every active food
    // group subtracts one effective year, capped to the native 0..4 range.
    int nutritionShift = activeFoodGroups;
    int effectiveAge = internalAge / 20 - nutritionShift;
    if (effectiveAge < 55) return 0;

    int hazardMillionths = 999999;
    if (effectiveAge <= 317) {
        hazardMillionths = VF2_OLDER_MORTALITY_HAZARDS[effectiveAge - 55];
    }
    return GetRandom(1000000) < hazardMillionths ? 1 : 0;
}
static_assert(VF2_OLDER_MORTALITY_TABLE_FIRST_AGE == 55 && VF2_OLDER_MORTALITY_TABLE_LAST_AGE == 317 &&
                  VF2_OLDER_MORTALITY_RANDOM_LIMIT == 1000000 && VF2_OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS == 999999 &&
                  VF2_CAUSE_OF_DEATH_OLD_AGE == 2 && VF2_VILLAGER_STATE_AGE_OFFSET == 8,
              "the mortality constants follow the sites module");
static_assert(sizeof(VF2_OLDER_MORTALITY_HAZARDS) / sizeof(VF2_OLDER_MORTALITY_HAZARDS[0]) == 317 - 55 + 1,
              "the hazard table covers effective ages 55..317");

static const unsigned MortalityFoodGroups = VF2_FOOD_GROUPS_ACTIVE;
static const unsigned MortalitySetHealth = VF2_SET_HEALTH;
static const unsigned MortalityDone = VF2_OLDER_MORTALITY_DONE;

// Jumped to from 0x49BBBD in place of `push 0; mov ecx,ebp; call FoodGroupsActive`
// (ebp = the villager's CVillagerState, esi = the loop pointer). Both outcomes
// continue at 0x49BC47, after the stock statement, which is never entered.
static __declspec(naked) void OlderMortalityStub() {
    __asm {
        push 0
        mov ecx, ebp
        call dword ptr [MortalityFoodGroups]
        push eax
        push dword ptr [ebp + 8]
        call RollOlderVillagerMortality
        add esp, 8
        test eax, eax
        jz alive
        push 2
        push 0
        mov ecx, ebp
        call dword ptr [MortalitySetHealth]
    alive:
        jmp dword ptr [MortalityDone]
    }
}

static void PlanOlderVillagerMortality(Plan &plan) {
    plan.Jmp(VF2_UPKEEP_FOOD_GROUPS_CALL, VF2_UPKEEP_FOOD_GROUPS_CALL_LEN, (const void *)&OlderMortalityStub);
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
    { PlanCareerRoomGoals, &CareerRoomGoalReconciliation },  // VF2_MODULE_CAREER_ROOM_GOALS
    { PlanTimeControls, &TimeControls },               // VF2_MODULE_TIME_CONTROLS
    { PlanEventCollectables, &EventCollectableSlotReplacement },  // VF2_MODULE_EVENT_COLLECTABLE_SLOT_REPLACEMENT
    { PlanPowerFailureEvent, &PowerFailureEvent },  // VF2_MODULE_POWER_FAILURE_EVENT
    { PlanOlderVillagerMortality, &OlderVillagerMortality },  // VF2_MODULE_OLDER_VILLAGER_MORTALITY
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
