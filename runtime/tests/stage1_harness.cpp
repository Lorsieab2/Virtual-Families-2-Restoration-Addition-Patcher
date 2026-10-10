// Stage 1 test harness (32-bit). NOT shipped; built and run by
// tests/test_runtime_hooks_stage1.py.
//
//   stage1_harness.exe "<patched Virtual Families 2.exe>"
//
// The harness never starts the game. It copies the PATCHED executable's
// headers and sections into memory at the image base 0x400000 as plain data
// (no loader, no imports, no entry point, no CRT start-up of the game), gives
// each section the protection the Windows loader would, fills only the two
// IAT slots the loader stub uses (GetModuleHandleA, GetProcAddress), and
// replaces theGame::Init with a recorder. Then it does exactly what the game
// does at 0x42AFF8: calls theGame's vtable slot 4 with ECX = a theGame
// object. That runs the real stub, which loads the real vf2fun.dll by full
// path from "<harness folder>\Virtual Families 2 Patcher Files\" and calls
// VF2Fun_Startup, which installs its hooks into this copy.
//
// After that it runs the hooked paths through the COPIED stock code, with
// recorders standing in for the few game calls that touch the game's
// runtime (GetRandom, CTutorialTip::Queue, SelectRandomLivingVillager):
//   - CVillagerState::ChanceOfPregnancy through its patched entry 0x4A0810
//     (young couples run the trampoline and the stock body; older couples
//     the late-age roll);
//   - the patched cooldown store 0x49F6DF entered with the register state
//     ProcessCurrentPlan has there, captured on arrival at 0x49F6E5;
//   - the CanStartNextGeneration wrapper through the patched call site's
//     own rel32.
// Everything observed is printed as one JSON object per line.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static const unsigned IMAGE_BASE = 0x400000;

static void Out(const char *fmt, ...) {
    va_list a;
    va_start(a, fmt);
    vprintf(fmt, a);
    va_end(a);
    printf("\n");
    fflush(stdout);
}

static void Fail(const char *what) {
    Out("{\"fatal\": \"%s\", \"error\": %lu}", what, GetLastError());
    ExitProcess(3);
}

static void Hex(char *dst, const unsigned char *src, unsigned n) {
    static const char *d = "0123456789abcdef";
    for (unsigned i = 0; i < n; ++i) {
        dst[i * 2] = d[src[i] >> 4];
        dst[i * 2 + 1] = d[src[i] & 15];
    }
    dst[n * 2] = 0;
}

static void WriteJmp(unsigned at, void *to) {
    unsigned char b[5] = { 0xE9 };
    int rel = (int)((unsigned)to - (at + 5));
    memcpy(b + 1, &rel, 4);
    DWORD old;
    if (!VirtualProtect((void *)at, 5, PAGE_EXECUTE_READWRITE, &old)) Fail("protect fake");
    memcpy((void *)at, b, 5);
    VirtualProtect((void *)at, 5, old, &old);
    FlushInstructionCache(GetCurrentProcess(), (void *)at, 5);
}

// ------------------------------------------------------------ recorders
static void *gInitThis;
static int gInitCalls;
static bool __fastcall FakeInit(void *self, void *) {
    gInitThis = self;
    gInitCalls++;
    return true;
}

static int gRandomValue, gRandomLimit, gRandomCalls;
static int __cdecl FakeGetRandom(int limit) {
    gRandomLimit = limit;
    gRandomCalls++;
    return gRandomValue;
}

static void *gQueueThis;
static int gQueueId, gQueueScene, gQueueFlag, gQueueCalls;
static void __fastcall FakeQueue(void *tip, void *, int id, int scene, int flag) {
    gQueueThis = tip;
    gQueueId = id;
    gQueueScene = scene;
    gQueueFlag = flag & 0xFF;
    gQueueCalls++;
}

static int gSelectResult = -1, gSelectCalls;
static int __fastcall FakeSelectRandomLivingVillager(void *, void *, int) {
    gSelectCalls++;
    return gSelectResult;
}

// ------------------------------------------------------------ cooldown run
static unsigned in_eax, in_ebx, in_ecx, in_edx, in_esi, in_edi, in_ebp, in_flags;
static unsigned out_eax, out_ebx, out_ecx, out_edx, out_esi, out_edi, out_ebp, out_esp, out_flags;
static unsigned gSaveEsp, gArriveEsp;
static unsigned gCooldownSite = 0x49F6DF;

static __declspec(naked) void CooldownResumeCapture() {
    __asm {
        pushfd
        pop out_flags
        mov out_eax, eax
        mov out_ebx, ebx
        mov out_ecx, ecx
        mov out_edx, edx
        mov out_esi, esi
        mov out_edi, edi
        mov out_ebp, ebp
        mov out_esp, esp
        mov esp, gSaveEsp
        popfd
        popad
        ret
    }
}

static __declspec(naked) void RunCooldown() {
    __asm {
        pushad
        pushfd
        mov gSaveEsp, esp
        mov gArriveEsp, esp
        push in_flags
        popfd
        mov eax, in_eax
        mov ebx, in_ebx
        mov ecx, in_ecx
        mov edx, in_edx
        mov esi, in_esi
        mov edi, in_edi
        mov ebp, in_ebp
        jmp dword ptr [gCooldownSite]
    }
}

// ------------------------------------------------------------ helpers
static unsigned char *Villager(int i) {
    return (unsigned char *)0x5B9F58 + 0x1CC70 + i * 0x1CC0C;
}

static void ClearVillagers() {
    for (int i = 0; i < 30; ++i) {
        unsigned char *v = Villager(i);
        v[0x1BB84] = 0;
        v[0x1BB88] = 0;
        *(int *)(v + 0x6B00) = 0;
        *(int *)(v + 0x6A54) = 0;
    }
}

typedef bool (__thiscall *ChanceFn)(void *, int, int, int);
typedef bool (__fastcall *NextGenFn)(void *, void *, bool);

static const char *Prot(DWORD p) {
    switch (p & 0xFF) {
    case PAGE_NOACCESS: return "NOACCESS";
    case PAGE_READONLY: return "R";
    case PAGE_READWRITE: return "RW";
    case PAGE_WRITECOPY: return "WC";
    case PAGE_EXECUTE: return "X";
    case PAGE_EXECUTE_READ: return "RX";
    case PAGE_EXECUTE_READWRITE: return "RWX";
    case PAGE_EXECUTE_WRITECOPY: return "WCX";
    }
    return "?";
}

static const char *ProtAt(unsigned va) {
    MEMORY_BASIC_INFORMATION m;
    if (!VirtualQuery((void *)va, &m, sizeof m)) return "none";
    return Prot(m.Protect);
}

// Process start-up maps heaps and locale data in the 0x400000-0xB3D000 range,
// so the harness re-launches itself suspended and reserves that range in the
// child before any of its start-up code runs.
static int RunChild(const wchar_t *exe) {
    wchar_t self[MAX_PATH];
    GetModuleFileNameW(0, self, MAX_PATH);
    wchar_t cmd[MAX_PATH * 3];
    _snwprintf_s(cmd, _countof(cmd), _TRUNCATE, L"\"%s\" \"%s\" child", self, exe);
    STARTUPINFOW si = { sizeof si };
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    PROCESS_INFORMATION pi;
    if (!CreateProcessW(0, cmd, 0, 0, TRUE, CREATE_SUSPENDED, 0, 0, &si, &pi)) Fail("create child");
    // Big enough for the patched image (SizeOfImage is checked in the child).
    if (VirtualAllocEx(pi.hProcess, (void *)IMAGE_BASE, 0x740000, MEM_RESERVE, PAGE_READWRITE) != (void *)IMAGE_BASE) {
        TerminateProcess(pi.hProcess, 4);
        Fail("reserve image range in child");
    }
    ResumeThread(pi.hThread);
    WaitForSingleObject(pi.hProcess, 300000);
    DWORD code = 5;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)code;
}

int wmain(int argc, wchar_t **argv) {
    if (argc == 2)
        return RunChild(argv[1]);
    if (argc != 3 || wcscmp(argv[2], L"child") != 0) {
        Out("{\"fatal\": \"usage\"}");
        return 2;
    }
    HANDLE f = CreateFileW(argv[1], GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (f == INVALID_HANDLE_VALUE) Fail("open exe");
    DWORD size = GetFileSize(f, 0);
    unsigned char *file = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, size);
    DWORD got = 0;
    if (!file || !ReadFile(f, file, size, &got, 0) || got != size) Fail("read exe");
    CloseHandle(f);

    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)file;
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(file + dos->e_lfanew);
    if (nt->OptionalHeader.ImageBase != IMAGE_BASE) Fail("image base");
    unsigned imageSize = nt->OptionalHeader.SizeOfImage;
    if (imageSize > 0x740000) Fail("image larger than the reservation");
    unsigned char *image = (unsigned char *)VirtualAlloc((void *)IMAGE_BASE, imageSize, MEM_COMMIT, PAGE_READWRITE);
    if (image != (unsigned char *)IMAGE_BASE) {
        MEMORY_BASIC_INFORMATION m;
        for (unsigned a = IMAGE_BASE; a < IMAGE_BASE + imageSize && VirtualQuery((void *)a, &m, sizeof m);
             a = (unsigned)m.BaseAddress + (unsigned)m.RegionSize)
            if (m.State != MEM_FREE)
                Out("{\"occupied\": %u, \"size\": %u, \"type\": %u}", (unsigned)m.BaseAddress,
                    (unsigned)m.RegionSize, (unsigned)m.Type);
        Fail("reserve image range");
    }
    memcpy(image, file, nt->OptionalHeader.SizeOfHeaders);
    IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        unsigned n = sec[i].SizeOfRawData < sec[i].Misc.VirtualSize ? sec[i].SizeOfRawData : sec[i].Misc.VirtualSize;
        if (sec[i].Misc.VirtualSize == 0) n = sec[i].SizeOfRawData;
        memcpy(image + sec[i].VirtualAddress, file + sec[i].PointerToRawData, n);
    }
    // Only the two imports the stub calls.
    HMODULE k32 = GetModuleHandleA("kernel32.dll");
    *(void **)0x4DE1E4 = (void *)GetProcAddress(k32, "GetModuleHandleA");
    *(void **)0x4DE1E8 = (void *)GetProcAddress(k32, "GetProcAddress");

    // Section protections as the loader applies them.
    DWORD old;
    VirtualProtect(image, nt->OptionalHeader.SizeOfHeaders, PAGE_READONLY, &old);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        DWORD c = sec[i].Characteristics;
        bool x = (c & IMAGE_SCN_MEM_EXECUTE) != 0, w = (c & IMAGE_SCN_MEM_WRITE) != 0;
        DWORD p = x ? (w ? PAGE_EXECUTE_READWRITE : PAGE_EXECUTE_READ) : (w ? PAGE_READWRITE : PAGE_READONLY);
        unsigned span = sec[i].Misc.VirtualSize ? sec[i].Misc.VirtualSize : sec[i].SizeOfRawData;
        if (!VirtualProtect(image + sec[i].VirtualAddress, span, p, &old)) Fail("protect section");
    }

    // theGame::Init itself is game start-up code: record the call instead.
    WriteJmp(0x428620, (void *)&FakeInit);

    // ---- bootstrap: exactly what 0x42AFF8 does.
    struct { unsigned vtable; unsigned char rest[0x24]; } game = { 0x4E2998 };
    typedef bool (__thiscall *InitFn)(void *);
    InitFn slot = *(InitFn *)(0x4E2998 + 4 * 4);
    bool initResult = slot(&game);
    unsigned stubState = *(unsigned *)0xB3C000;
    HMODULE dll = *(HMODULE *)0xB3C008;
    wchar_t dllPath[MAX_PATH] = L"";
    if (dll) GetModuleFileNameW(dll, dllPath, MAX_PATH);
    char dllPathA[MAX_PATH * 3] = "";
    WideCharToMultiByte(CP_UTF8, 0, dllPath, -1, dllPathA, sizeof dllPathA, 0, 0);
    for (char *p = dllPathA; *p; ++p) if (*p == '\\') *p = '/';
    Out("{\"bootstrap\": {\"slot\": %u, \"init_result\": %d, \"init_calls\": %d, \"init_this_ok\": %d, "
        "\"stub_state\": %u, \"dll_loaded\": %d, \"dll_path\": \"%s\"}}",
        (unsigned)slot, initResult ? 1 : 0, gInitCalls, gInitThis == &game ? 1 : 0, stubState,
        dll ? 1 : 0, dllPathA);
    if (!dll) return 0;

    struct Status {
        unsigned magic, version, allowOlderPregnancies, pinsMatched, installedMask, trampoline,
            chanceCalls, olderRolls, olderSuccesses, cooldownStores, cooldownSkips,
            nextGenerationCalls, nextGenerationOlderGrants, lastMotherAge, lastFatherAge;
    };
    volatile Status *status = (volatile Status *)GetProcAddress(dll, "VF2Fun_Status");
    if (!status) Fail("status export");
    IMAGE_NT_HEADERS32 *dnt = (IMAGE_NT_HEADERS32 *)((unsigned char *)dll + ((IMAGE_DOS_HEADER *)dll)->e_lfanew);
    unsigned dllLo = (unsigned)dll, dllHi = dllLo + dnt->OptionalHeader.SizeOfImage;

    // ---- what is now at every site
    const unsigned sites[] = { 0x4A0810, 0x49F6DF, 0x430681, 0x430DB8, 0x43C0BD, 0x4407DC };
    const unsigned lens[] = { 8, 6, 5, 5, 5, 5 };
    char hex[64];
    for (int i = 0; i < 6; ++i) {
        Hex(hex, (const unsigned char *)sites[i], lens[i]);
        Out("{\"site\": %u, \"bytes\": \"%s\", \"protect\": \"%s\"}", sites[i], hex, ProtAt(sites[i]));
    }
    Out("{\"status\": {\"magic\": %u, \"allow\": %u, \"pins\": %u, \"mask\": %u, \"trampoline\": %u, "
        "\"dll_lo\": %u, \"dll_hi\": %u}}",
        status->magic, status->allowOlderPregnancies, status->pinsMatched, status->installedMask,
        status->trampoline, dllLo, dllHi);
    if (status->trampoline) {
        Hex(hex, (const unsigned char *)status->trampoline, 16);
        Out("{\"trampoline\": %u, \"bytes\": \"%s\", \"protect\": \"%s\"}", status->trampoline, hex,
            ProtAt(status->trampoline));
    }

    // ---- no page anywhere in the process is writable and executable
    {
        unsigned addr = 0x10000, wx = 0;
        MEMORY_BASIC_INFORMATION m;
        while (addr < 0x7FFF0000 && VirtualQuery((void *)addr, &m, sizeof m)) {
            if (m.State == MEM_COMMIT &&
                ((m.Protect & 0xFF) == PAGE_EXECUTE_READWRITE || (m.Protect & 0xFF) == PAGE_EXECUTE_WRITECOPY)) {
                Out("{\"wx_region\": %u, \"size\": %u}", (unsigned)m.BaseAddress, (unsigned)m.RegionSize);
                wx++;
            }
            addr = (unsigned)m.BaseAddress + (unsigned)m.RegionSize;
        }
        Out("{\"wx_regions\": %u}", wx);
    }

    // ---- recorders for the game calls the scenarios reach
    WriteJmp(0x403F70, (void *)&FakeGetRandom);
    WriteJmp(0x4AA020, (void *)&FakeQueue);
    WriteJmp(0x499EB0, (void *)&FakeSelectRandomLivingVillager);
    WriteJmp(0x49F6E5, (void *)&CooldownResumeCapture);

    // ---- ChanceOfPregnancy through its (possibly patched) entry
    static unsigned char motherVillager[0x1CC0C];
    unsigned char *state = motherVillager + 0x6AF4;
    ChanceFn chance = (ChanceFn)0x4A0810;
    // CTutorialTip::WasDisplayed(id) reads TutorialTip + (id - 0x844) * 32.
    unsigned char *tutorialShown = (unsigned char *)0xAA7E98 + (0x868 - 0x844) * 32;
    const int ages[] = { 18 * 20, 30 * 20, 40 * 20, 41 * 20, 49 * 20 + 19, 50 * 20, 51 * 20, 55 * 20, 59 * 20,
                         60 * 20, 64 * 20, 68 * 20, 69 * 20, 80 * 20 };
    const int fertilities[] = { 1, 50, 100 };
    const int randoms[] = { 0, 1, 5, 9, 10, 49, 50, 99, 100, 999 };
    for (int mi = 0; mi < 14; ++mi)
        for (int fi = 0; fi < 14; ++fi)
            for (int mf = 0; mf < 3; ++mf)
                for (int ff = 0; ff < 3; ++ff)
                    for (int r = 0; r < 10; ++r)
                    for (int shown = 0; shown < 2; ++shown) {
                        if (ages[mi] < 1000 && ages[fi] < 1000 && (mf != 1 || ff != 1) && r > 3) continue;
                        *tutorialShown = (unsigned char)shown;
                        *(int *)(state + 0x4C) = fertilities[mf];
                        gRandomValue = randoms[r];
                        gRandomLimit = gRandomCalls = gQueueCalls = 0;
                        gQueueId = gQueueScene = gQueueFlag = -1;
                        bool result = chance(state, ages[mi], ages[fi], fertilities[ff]);
                        Out("{\"chance\": [%d, %d, %d, %d, %d, %d], \"result\": %d, \"random_calls\": %d, "
                            "\"random_limit\": %d, \"queue_calls\": %d, \"queue\": [%d, %d, %d], \"queue_this\": %u}",
                            ages[mi], ages[fi], fertilities[mf], fertilities[ff], randoms[r], shown, result ? 1 : 0,
                            gRandomCalls, gRandomLimit, gQueueCalls, gQueueId, gQueueScene, gQueueFlag,
                            (unsigned)gQueueThis);
                    }

    // ---- the failed-attempt cooldown store
    static unsigned char gameState[0x26000];
    static unsigned char fatherVillager[0x1CC0C];
    const int cAges[][2] = { { 600, 600 }, { 999, 999 }, { 1000, 600 }, { 600, 1000 }, { 1400, 1400 } };
    for (int c = 0; c < 5; ++c) {
        *(int *)(motherVillager + 0x6A54) = cAges[c][0];
        *(int *)(fatherVillager + 0x6A54) = cAges[c][1];
        *(unsigned *)(gameState + 0x25AE0) = 0xDDDDDDDD;
        in_eax = (unsigned)gameState;
        in_ebx = 0x12345678;
        in_ecx = (unsigned)state;           // stock: mov ecx,esi just before the store
        in_edx = 0xEDEDEDED;
        in_esi = (unsigned)state;
        in_edi = (unsigned)fatherVillager;
        in_ebp = 0xEBEBEBEB;
        in_flags = 0x2 | 0x1 | 0x40 | 0x80 | 0x800;  // CF ZF SF OF set, DF clear
        out_esp = 0;
        RunCooldown();
        Out("{\"cooldown\": [%d, %d], \"deadline\": %u, \"regs_same\": %d, \"flags_same\": %d, "
            "\"esp_same\": %d}",
            cAges[c][0], cAges[c][1], *(unsigned *)(gameState + 0x25AE0),
            out_eax == in_eax && out_ebx == in_ebx && out_ecx == in_ecx && out_edx == in_edx &&
                out_esi == in_esi && out_edi == in_edi && out_ebp == in_ebp ? 1 : 0,
            (out_flags & 0x8D5) == (in_flags & 0x8D5) ? 1 : 0, out_esp == gArriveEsp ? 1 : 0);
    }

    // ---- CanStartNextGeneration through each patched call site's rel32
    unsigned char *tree = (unsigned char *)0x5ACFC8;
    *(int *)(tree + 4) = 3;  // generation 3 -> record at tree + 3*0x6C8 - 0x6C0
    unsigned char *record = tree + 3 * 0x6C8 - 0x6C0;
    struct Case { const char *name; int canStart; int children; int childAlive; int age; int leftHome; int health; int force; };
    const Case cases[] = {
        { "stock_yes", 1, 0, 0, 0, 0, 1, 0 },
        { "no_children", 0, 0, 0, 1200, 0, 1, 0 },
        { "dead_child", 0, 1, 0, 1200, 0, 1, 0 },
        { "oldest_59", 0, 1, 1, 1199, 0, 1, 0 },
        { "oldest_60", 0, 1, 1, 1200, 0, 1, 0 },
        { "oldest_60_left_home", 0, 1, 1, 1200, 1, 1, 0 },
        { "oldest_60_dead", 0, 1, 1, 1200, 0, 0, 0 },
        { "oldest_60_force", 0, 1, 1, 1200, 0, 1, 1 },
    };
    for (int site = 0; site < 4; ++site) {
        unsigned at = sites[2 + site];
        unsigned target = at + 5 + *(int *)(at + 1);
        NextGenFn fn = (NextGenFn)target;
        for (int c = 0; c < 8; ++c) {
            const Case &k = cases[c];
            ClearVillagers();
            record[0] = 1;
            record[1] = (unsigned char)k.canStart;
            *(int *)(record + 0x1B4) = k.children;
            *(int *)(record + 0x1E0) = 1;          // the child is villager 1
            Villager(1)[0x1BB84] = (unsigned char)k.childAlive;
            *(int *)(Villager(1) + 0x6B00) = 1;
            *(int *)(Villager(1) + 0x6A54) = 100;
            unsigned char *elder = Villager(0);    // the oldest candidate
            elder[0x1BB84] = 1;
            elder[0x1BB88] = (unsigned char)k.leftHome;
            *(int *)(elder + 0x6B00) = k.health;
            *(int *)(elder + 0x6A54) = k.age;
            gSelectCalls = 0;
            bool r = fn(tree, 0, k.force != 0);
            Out("{\"next_generation\": \"%s\", \"site\": %u, \"target\": %u, \"result\": %d, \"select_calls\": %d}",
                k.name, at, target, r ? 1 : 0, gSelectCalls);
        }
    }
    Out("{\"counters\": {\"chance\": %u, \"older_rolls\": %u, \"older_successes\": %u, \"cooldown_stores\": %u, "
        "\"cooldown_skips\": %u, \"next_generation\": %u, \"older_grants\": %u}}",
        status->chanceCalls, status->olderRolls, status->olderSuccesses, status->cooldownStores,
        status->cooldownSkips, status->nextGenerationCalls, status->nextGenerationOlderGrants);
    Out("{\"done\": 1}");
    return 0;
}
