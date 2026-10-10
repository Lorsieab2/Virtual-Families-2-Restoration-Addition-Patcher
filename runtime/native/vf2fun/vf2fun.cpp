// vf2fun.dll -- Stage 1 runtime-hook companion for the VANILLA Virtual
// Families 2 executable.
//
// The patched executable's only added code is a loader stub at theGame's
// Init vtable slot (see runtime/tools/build_stub.py). It loads this DLL by
// full path and calls VF2Fun_Startup() once, before theGame::Init and before
// the game loop. Everything else lives here and is installed at runtime:
//
//   Allow Older Pregnancies (the B200 static build's .vf2preg feature)
//   1. CVillagerState::ChanceOfPregnancy entry detour (0x4A0810). Real
//      prologue bytes are stolen into a trampoline and the call resumes at
//      0x4A0818.
//   2. Failed-attempt cooldown store in CVillagerPlans::ProcessCurrentPlan
//      (0x49F6DF). The 6-byte `mov [eax+25AE0h],ebx` jumps here and the
//      store is done only when B200 would do it.
//   3. The four CFamilyTree::CanStartNextGeneration call sites, retargeted
//      to the B200 older-age wrapper.
//
// The logic below is a line-for-line port of B200's helpers in
// work/patch_mobile_furniture_pack.py (VF2RollOlderPregnancy,
// VF2StoreTryForBabyCooldownMaybe, VF2CanStartNextGenerationAtOlderAge) and
// of its two cave trampolines. Every address comes from the generated
// vf2fun_sites.h, and nothing is written unless every pinned run in that
// header matches live memory. A missing DLL, missing setting, or any
// mismatch leaves the game stock.
//
// Memory: trampolines live in one page that is PAGE_READWRITE while it is
// built and PAGE_EXECUTE_READ afterwards. Game code is made writable only
// for the duration of each individual write, then its original protection is
// restored; no page is left writable and executable.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "vf2fun_sites.h"

// ---------------------------------------------------------------- status
// Read by runtime/tools/probe_stage1.py through ReadProcessMemory. Stage 1
// diagnostic counters: they let a live test observe each hook without
// waiting for a rare event (see the study's Stage 1 live-test script).
struct VF2FunStatus {
    unsigned magic;              // 'VF2S'
    unsigned version;            // 1
    unsigned allowOlderPregnancies;
    unsigned pinsMatched;        // 1 when every pin matched live memory
    unsigned installedMask;      // bit 0 chance detour, 1 cooldown, 2..5 call sites
    unsigned trampoline;         // address of the ChanceOfPregnancy trampoline
    unsigned chanceCalls;        // ChanceOfPregnancy entries seen
    unsigned olderRolls;         // calls routed to the late-age roll
    unsigned olderSuccesses;     // late-age rolls that conceived
    unsigned cooldownStores;     // failed attempts whose deadline was written
    unsigned cooldownSkips;      // failed attempts whose deadline was skipped (50+)
    unsigned nextGenerationCalls;
    unsigned nextGenerationOlderGrants;  // stock said no, the 60+ rule said yes
    unsigned lastMotherAge;      // internal ages of the last ChanceOfPregnancy call
    unsigned lastFatherAge;
};

extern "C" __declspec(dllexport) volatile VF2FunStatus VF2Fun_Status = { 0x53324656u, 1u };

static HMODULE Module;
static wchar_t Folder[MAX_PATH];
static bool AllowOlderPregnancies;

// ---------------------------------------------------------------- game ABI
typedef bool (__thiscall *ChanceOfPregnancyFn)(void *state, int motherAge, int fatherAge, int fatherFertility);
typedef bool (__thiscall *CanStartNextGenerationFn)(void *tree, bool force);
typedef int (__thiscall *CountSurvivingChildrenFn)(void *tree);
typedef int (__cdecl *GetRandomFn)(int limit);
typedef void (__thiscall *TutorialQueueFn)(void *tip, int stringId, int scene, bool flag);

static ChanceOfPregnancyFn OriginalChanceOfPregnancy;  // the trampoline
static const CanStartNextGenerationFn NativeCanStartNextGeneration =
    (CanStartNextGenerationFn)VF2_CAN_START_NEXT_GENERATION;
static const CountSurvivingChildrenFn CountSurvivingChildren =
    (CountSurvivingChildrenFn)VF2_COUNT_SURVIVING_CHILDREN;
static const GetRandomFn GetRandom = (GetRandomFn)VF2_GET_RANDOM;
static const TutorialQueueFn TutorialQueue = (TutorialQueueFn)VF2_TUTORIAL_QUEUE;
static void *const TutorialTip = (void *)VF2_TUTORIAL_TIP;
static const int eStringPregnancyTutorial = 0x868;
static const int eGameSceneNone = 0;

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

// ---------------------------------------------------------------- B200 helpers (ported)
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
    VF2Fun_Status.chanceCalls++;
    VF2Fun_Status.lastMotherAge = (unsigned)motherAge;
    VF2Fun_Status.lastFatherAge = (unsigned)fatherAge;
    if (AllowOlderPregnancies && (motherAge >= 1000 || fatherAge >= 1000)) {
        VF2Fun_Status.olderRolls++;
        int conceived = RollOlderPregnancy(state, motherAge, fatherAge, fatherFertility);
        if (conceived) VF2Fun_Status.olderSuccesses++;
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
        VF2Fun_Status.cooldownStores++;
    } else {
        VF2Fun_Status.cooldownSkips++;
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

static unsigned char *VillagerByIndex(int index) {
    if (index < 0 || index >= 30) return 0;
    return (unsigned char *)VF2_VILLAGER_MANAGER + VF2_VILLAGER_ARRAY_OFFSET + index * VF2_VILLAGER_STRIDE;
}

// B200 VF2CanStartNextGenerationAtOlderAge.
static bool __fastcall CanStartNextGenerationAtOlderAge(void *tree, void *, bool force) {
    VF2Fun_Status.nextGenerationCalls++;
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
    if (granted) VF2Fun_Status.nextGenerationOlderGrants++;
    return granted;
}

// ---------------------------------------------------------------- hook engine
struct CodeWrite {
    unsigned va;
    unsigned char bytes[8];
    unsigned len;
    unsigned char original[8];
    bool done;
};

static bool PinsMatch() {
    for (size_t i = 0; i < sizeof(VF2_PINS) / sizeof(VF2_PINS[0]); ++i) {
        const VF2Pin &pin = VF2_PINS[i];
        if (memcmp((const void *)pin.va, pin.bytes, pin.len) != 0) {
            Log("pin %s at 0x%08X does not match the vanilla bytes; installing nothing", pin.name, pin.va);
            return false;
        }
    }
    return true;
}

// Write `len` bytes of game code. The page is writable only for this write
// and gets its original protection back before returning.
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

static void EncodeRel32(unsigned char *out, unsigned char opcode, unsigned from, unsigned to) {
    out[0] = opcode;
    int rel = (int)(to - (from + 5));
    memcpy(out + 1, &rel, 4);
}

// Builds the ChanceOfPregnancy trampoline: the stolen prologue copied from
// live memory (already proved equal to the pin and free of relative
// instructions by gen_sites.py) followed by jmp 0x4A0818. Returns 0 on failure.
static unsigned char *BuildTrampoline() {
    unsigned char *page = (unsigned char *)VirtualAlloc(0, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!page) return 0;
    memcpy(page, (const void *)VF2_CHANCE_OF_PREGNANCY, VF2_CHANCE_OF_PREGNANCY_STEAL);
    EncodeRel32(page + VF2_CHANCE_OF_PREGNANCY_STEAL, 0xE9,
                (unsigned)(page + VF2_CHANCE_OF_PREGNANCY_STEAL),
                VF2_CHANCE_OF_PREGNANCY + VF2_CHANCE_OF_PREGNANCY_STEAL);
    DWORD old = 0;
    if (!VirtualProtect(page, 4096, PAGE_EXECUTE_READ, &old)) {
        VirtualFree(page, 0, MEM_RELEASE);
        return 0;
    }
    FlushInstructionCache(GetCurrentProcess(), page, 4096);
    return page;
}

static void InstallAllowOlderPregnancies() {
    if (!PinsMatch())
        return;
    VF2Fun_Status.pinsMatched = 1;

    unsigned char *trampoline = BuildTrampoline();
    if (!trampoline) {
        Log("could not build the trampoline page; installing nothing");
        return;
    }

    CodeWrite writes[6] = {};
    unsigned count = 0;

    CodeWrite &chance = writes[count++];
    chance.va = VF2_CHANCE_OF_PREGNANCY;
    chance.len = VF2_CHANCE_OF_PREGNANCY_STEAL;
    EncodeRel32(chance.bytes, 0xE9, chance.va, (unsigned)&ChanceOfPregnancyDetour);
    for (unsigned i = 5; i < chance.len; ++i) chance.bytes[i] = 0x90;

    CodeWrite &cooldown = writes[count++];
    cooldown.va = VF2_COOLDOWN_STORE;
    cooldown.len = VF2_COOLDOWN_STORE_LEN;
    EncodeRel32(cooldown.bytes, 0xE9, cooldown.va, (unsigned)&CooldownStub);
    for (unsigned i = 5; i < cooldown.len; ++i) cooldown.bytes[i] = 0x90;

    for (size_t i = 0; i < sizeof(VF2_NEXT_GENERATION_CALLSITES) / sizeof(unsigned); ++i) {
        CodeWrite &call = writes[count++];
        call.va = VF2_NEXT_GENERATION_CALLSITES[i];
        call.len = 5;
        EncodeRel32(call.bytes, 0xE8, call.va, (unsigned)&CanStartNextGenerationAtOlderAge);
    }

    // The detour must be able to reach the stock body before the entry jmp
    // goes live.
    OriginalChanceOfPregnancy = (ChanceOfPregnancyFn)trampoline;
    VF2Fun_Status.trampoline = (unsigned)trampoline;

    for (unsigned i = 0; i < count; ++i) {
        memcpy(writes[i].original, (const void *)writes[i].va, writes[i].len);
        if (!WriteCode(writes[i].va, writes[i].bytes, writes[i].len)) {
            Log("write at 0x%08X failed (error %lu); restoring every hook", writes[i].va, GetLastError());
            for (unsigned j = 0; j < i; ++j)
                WriteCode(writes[j].va, writes[j].original, writes[j].len);
            // A write that failed at VirtualProtect wrote nothing; one whose
            // restore failed did write, so put it back too.
            WriteCode(writes[i].va, writes[i].original, writes[i].len);
            VF2Fun_Status.installedMask = 0;
            return;
        }
        VF2Fun_Status.installedMask |= 1u << i;
    }
    Log("Allow Older Pregnancies installed: trampoline 0x%08X, ChanceOfPregnancy 0x%08X -> 0x%08X, "
        "cooldown 0x%08X -> 0x%08X, next generation x4 -> 0x%08X",
        (unsigned)trampoline, VF2_CHANCE_OF_PREGNANCY, (unsigned)&ChanceOfPregnancyDetour,
        VF2_COOLDOWN_STORE, (unsigned)&CooldownStub, (unsigned)&CanStartNextGenerationAtOlderAge);
}

// ---------------------------------------------------------------- entry
static bool SettingOn(const wchar_t *key) {
    wchar_t ini[MAX_PATH];
    if (_snwprintf_s(ini, MAX_PATH, _TRUNCATE, L"%svf2fun.ini", Folder) < 0)
        return false;
    return GetPrivateProfileIntW(L"Patches", key, 0, ini) == 1;
}

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

    AllowOlderPregnancies = SettingOn(L"AllowOlderPregnancies");
    VF2Fun_Status.allowOlderPregnancies = AllowOlderPregnancies ? 1u : 0u;
    Log("vf2fun Stage 1 started; AllowOlderPregnancies=%d", AllowOlderPregnancies ? 1 : 0);
    // Off means stock: nothing is written, exactly like B200 with .vf2preg = 00
    // (whose dormant hooks reproduce the stock behaviour byte for byte).
    if (AllowOlderPregnancies)
        InstallAllowOlderPregnancies();
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        Module = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
