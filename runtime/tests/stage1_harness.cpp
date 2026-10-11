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

#pragma comment(lib, "user32.lib")

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

// ------------------------------------------------------------ ldwScene::SetActive run
static unsigned char gFakeEventManager[16];
static void *gFakeSceneVtable[16];
struct FakeScene { void **vtable; unsigned char *flag; };
static void *__cdecl FakeEventManagerGet() { return gFakeEventManager; }
static int gSubscribeCalls, gUnsubscribeCalls, gActivateCalls, gActivateArg, gVirtualCalls, gVirtualArg;
static void *gSubscribeThis, *gHandler;
static void __fastcall FakeSubscribe(void *self, void *, void *handler, int, int) {  // ret 0Ch
    gSubscribeThis = self;
    gHandler = handler;
    gSubscribeCalls++;
}
static void __fastcall FakeUnsubscribe(void *self, void *, void *handler, int) {  // ret 8
    gSubscribeThis = self;
    gHandler = handler;
    gUnsubscribeCalls++;
}
static void __fastcall FakeActivateControls(void *, void *, int arg) {  // ret 4
    gActivateCalls++;
    gActivateArg = arg & 0xFF;
}
static void __fastcall FakeSceneVirtual(void *, void *, int arg) {  // ret 4
    gVirtualCalls++;
    gVirtualArg = arg & 0xFF;
}

// Calls ldwScene::SetActive(arg) on `scene` exactly as a game caller does
// (push the bool, ecx = this). Returns 1 if it faulted (stock, null flag).
static int CallSetActive(void *scene, int arg, int *espDelta) {
    unsigned before = 0, after = 0;
    __try {
        __asm {
            mov before, esp
            push arg
            mov ecx, scene
            mov eax, 0x40D1D0
            call eax
            mov after, esp
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 1;
    }
    *espDelta = (int)(before - after);
    return 0;
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

// ------------------------------------------------------------ CTech::Level recorders
static unsigned char gOwned[0x200];
static char gEvents[4096];
static int gEventLen;
static void Event(const char *fmt, int a, int b) {
    gEventLen += _snprintf_s(gEvents + gEventLen, sizeof gEvents - gEventLen, _TRUNCATE,
                             gEventLen ? fmt + 0 : fmt + 1, a, b);
}
static bool __fastcall FakeHaveUpgrade(void *self, void *, int item) {  // ret 4
    if (self != (void *)0xAB3528) Event(",[\"bad_inventory_this\", %d, %d]", item, 0);
    return item >= 0 && item < 0x200 && gOwned[item];
}
static void __fastcall FakeResetSingle(void *self, void *, int id) {  // ret 4
    Event(",[\"reset\", %d, %d]", id, self == (void *)0xAA8648);
}
static void __fastcall FakeIncrement(void *self, void *, int id, int amount) {  // ret 8
    Event(",[\"increment\", %d, %d]", id, self == (void *)0xAA8648 ? amount : -9999);
}
static int gLoadResult = 1;
static bool __fastcall FakeTechLoadState(void *, void *, const void *) {  // ret 4
    return gLoadResult != 0;
}

// Runs copied game code from `entry` with the in_* registers until it
// reaches `resume` (where a capture jmp is planted), then returns here.
static void RunSpan(unsigned entry, unsigned resume) {
    gCooldownSite = entry;
    WriteJmp(resume, (void *)&CooldownResumeCapture);
    out_esp = 0;
    RunCooldown();
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
static int RunChild(const wchar_t *exe, const wchar_t *mode) {
    wchar_t self[MAX_PATH];
    GetModuleFileNameW(0, self, MAX_PATH);
    wchar_t cmd[MAX_PATH * 3];
    _snwprintf_s(cmd, _countof(cmd), _TRUNCATE, L"\"%s\" \"%s\" %s", self, exe, mode);
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

// ------------------------------------------------------------ time_controls scenarios
// Seams (all game start-up / runtime calls the scenarios would otherwise reach):
// the real-time clock, the leaving-home actions, the store screen's UI
// natives. Everything else is the copied stock code: CGameTime::SetSpeed,
// CVillagerManager::AllVillagersTimeflowUpkeep, CVillagerBio::IncrementAge,
// CScrollingStoreScene::HandleMessage.
static unsigned gClock;
static unsigned __fastcall FakeSeconds(void *, void *) { return gClock; }  // GetSecondsFromGameStart

static int gCareer;
static int __fastcall FakeCareerType(void *, void *) { return gCareer; }
static int gForgetCalls, gLeftHomeCalls, gQueueLifeCalls, gCollegeCalls;
static void *gLeftHomeThis;
static void __fastcall FakeForgetPlans(void *, void *, void *, int) { gForgetCalls++; }       // ret 8
static void __fastcall FakeSetLeftHome(void *self, void *) { gLeftHomeCalls++; gLeftHomeThis = self; }
static void __fastcall FakeQueueLifeEvent(void *, void *, int, int, int) { gQueueLifeCalls++; }  // ret 0Ch
static void __fastcall FakeUpdateCollege(void *, void *) { gCollegeCalls++; }

static unsigned char gPool[8][0x20];
static int gPoolUsed;
static unsigned gNewSize;
static void *__cdecl FakeNew(unsigned size) { gNewSize = size; return gPool[gPoolUsed++ & 7]; }
static void *__cdecl FakeGraphicsGet() { return (void *)0x7000001; }
static int gImage;
static void *gImageGraphics;
static void *__fastcall FakeGetImageGrid(void *graphics, void *, int image) {  // ret 4
    gImage = image;
    gImageGraphics = graphics;
    return (void *)0x7000002;
}
static void *__cdecl FakeStringsGet() { return (void *)0x7000003; }
static void *gFontStrings;
static void *__fastcall FakeGetLargeFont(void *strings, void *) { gFontStrings = strings; return (void *)0x7000004; }
static int gButtonCalls, gButtonId, gButtonX, gButtonY, gButtonFlag;
static void *gButtonSelf, *gButtonGrid, *gButtonScene;
static void *__fastcall FakeButtonCtor(void *self, void *, int id, void *grid, int x, int y, void *scene,
                                       int flag) {  // ret 18h
    gButtonCalls++;
    gButtonSelf = self; gButtonId = id; gButtonGrid = grid; gButtonX = x; gButtonY = y; gButtonScene = scene;
    gButtonFlag = flag & 0xFF;
    return self;
}
static char gText[32];
static unsigned gTextC1, gTextC2, gTextC3;
static void *gTextSelf, *gTextFont;
static void __fastcall FakeButtonSetText(void *self, void *, const char *text, unsigned c1, unsigned c2,
                                         unsigned c3, void *font) {  // ret 14h
    gTextSelf = self; gTextC1 = c1; gTextC2 = c2; gTextC3 = c3; gTextFont = font;
    strncpy_s(gText, sizeof gText, text, _TRUNCATE);
}
static int gAddCalls;
static void *gAddScene, *gAddControl;
static void __fastcall FakeAddControl(void *scene, void *, void *control) {  // ret 4
    gAddCalls++; gAddScene = scene; gAddControl = control;
}
static int gCategoryCalls, gCategoryValue, gOrder, gCategoryOrder, gAddOrder;
static void *gCategoryScene;
static void __fastcall FakeSetStoreCategory(void *scene, void *, int category) {  // ret 4
    gCategoryCalls++; gCategoryScene = scene; gCategoryValue = category; gCategoryOrder = ++gOrder;
}

// ---- the dialog, driven from a second thread while the game thread is in its modal loop
struct Driver {
    int mode;                  // 1: read the controls and close; 2: the full script
    int waitMs;                // how long to wait for the dialog to appear
    int quiet;                 // log nothing when no dialog appears
    char log[6000];
    int len;
};

static void DLog(Driver *d, const char *fmt, ...) {
    va_list a;
    va_start(a, fmt);
    d->len += _vsnprintf_s(d->log + d->len, sizeof d->log - d->len, _TRUNCATE, fmt, a);
    va_end(a);
}

static void Utf8(const wchar_t *w, char *out, int n) {
    WideCharToMultiByte(CP_UTF8, 0, w, -1, out, n, 0, 0);
    // JSON: the texts here contain no quote or backslash.
}

static HWND WaitWindow(const wchar_t *title, int ms) {
    for (int t = 0; t < ms; t += 5) {
        HWND w = FindWindowW(L"#32770", title);
        if (w) return w;
        Sleep(5);
    }
    return 0;
}

static void ItemText(HWND dlg, int id, char *out, int n) {
    wchar_t w[256] = L"";
    GetDlgItemTextW(dlg, id, w, 256);
    Utf8(w, out, n);
}

// Click control `id` and wait until the status line reads `expect` (or 3 s).
static void ClickUntil(HWND dlg, int id, const char *expect, char *status) {
    PostMessageW(GetDlgItem(dlg, id), BM_CLICK, 0, 0);
    for (int t = 0; t < 3000; t += 5) {
        ItemText(dlg, 560, status, 256);
        if (strcmp(status, expect) == 0) return;
        Sleep(5);
    }
}

static DWORD WINAPI DriverThread(void *param) {
    Driver *d = (Driver *)param;
    HWND dlg = WaitWindow(L"Time Controls", d->waitMs ? d->waitMs : 5000);
    if (!dlg) {
        if (!d->quiet) DLog(d, "\"no_dialog\": 1");
        return 1;
    }
    wchar_t title[64] = L"";
    GetWindowTextW(dlg, title, 64);
    char t8[128], s8[256];
    Utf8(title, t8, sizeof t8);
    ItemText(dlg, 560, s8, sizeof s8);
    DLog(d, "\"title\": \"%s\", \"status\": \"%s\", \"controls\": [", t8, s8);
    for (int id = 561; id <= 567; ++id) {
        ItemText(dlg, id, s8, sizeof s8);
        DLog(d, "%s[%d, \"%s\"]", id == 561 ? "" : ", ", id, s8);
    }
    ItemText(dlg, IDOK, s8, sizeof s8);
    DLog(d, ", [%d, \"%s\"]]", IDOK, s8);
    if (d->mode == 2) {
        char status[256];
        static const struct { int id; const char *expect; } steps[] = {
            { 561, "Paused. Speed: normal." }, { 564, "Paused. Speed: 2x." }, { 562, "Running. Speed: 2x." },
            { 565, "Running. Speed: 5x." }, { 566, "Running. Speed: 10x." }, { 563, "Running. Speed: normal." },
        };
        DLog(d, ", \"steps\": [");
        for (int i = 0; i < 6; ++i) {
            ClickUntil(dlg, steps[i].id, steps[i].expect, status);
            DLog(d, "%s\"%s\"", i ? ", " : "", status);
        }
        DLog(d, "], \"warp\": [");
        for (int answer = 0; answer < 2; ++answer) {
            PostMessageW(GetDlgItem(dlg, 567), BM_CLICK, 0, 0);
            HWND box = WaitWindow(L"Time Warp", 3000);
            if (!box) { DLog(d, "%s{\"no_box\": 1}", answer ? ", " : ""); break; }
            char text[300] = "";
            for (HWND c = GetWindow(box, GW_CHILD); c; c = GetWindow(c, GW_HWNDNEXT)) {
                wchar_t w[300] = L"";
                GetWindowTextW(c, w, 300);
                if (wcslen(w) > 10) Utf8(w, text, sizeof text);
            }
            PostMessageW(box, WM_COMMAND, answer ? IDYES : IDNO, 0);
            const char *want = answer ? "Running. Speed: normal. A time warp is under way."
                                      : "Running. Speed: normal.";
            for (int t = 0; t < 3000; t += 5) {
                ItemText(dlg, 560, status, sizeof status);
                if (!IsWindow(box) && (answer == 0 || strcmp(status, want) == 0)) break;
                Sleep(5);
            }
            DLog(d, "%s{\"text\": \"%s\", \"status\": \"%s\"}", answer ? ", " : "", text, status);
        }
        DLog(d, "]");
    }
    PostMessageW(dlg, WM_CLOSE, 0, 0);
    return 0;
}

static void RunWithDriver(Driver *d, void (*open)(void *), void *arg) {
    d->len = 0;
    d->log[0] = 0;
    HANDLE th = CreateThread(0, 0, DriverThread, d, 0, 0);
    open(arg);
    WaitForSingleObject(th, 20000);
    CloseHandle(th);
}

typedef bool (__thiscall *StoreHandleFn)(void *scene, int message, long param);
struct HandleCall { StoreHandleFn fn; void *scene; int message; long param; bool result; };
static void CallStoreHandle(void *p) {
    HandleCall *c = (HandleCall *)p;
    c->result = c->fn(c->scene, c->message, c->param);
}
typedef void (__cdecl *ShowFn)(HWND);
static void CallShow(void *p) { ((ShowFn)p)(0); }

typedef int (__cdecl *TestTimeFn)(int op, int arg);
typedef void (__thiscall *TimeflowFn)(void *manager, bool flag);

static void SetupVillager(int i, int active, int left, int health, int age, unsigned accum, unsigned last) {
    unsigned char *v = Villager(i);
    v[0x1BB84] = (unsigned char)active;
    v[0x1BB88] = (unsigned char)left;
    *(int *)(v + 0x6B00) = health;
    *(int *)(v + 0x6A54) = age;
    *(unsigned *)(v + 0x6AF4) = accum;
    *(unsigned *)(v + 0x6AF8) = last;
}

static void RunTimeScenarios(HMODULE dll, unsigned char *gameState, bool installed) {
    // The live-probe test reads this process afterwards: put back what the
    // scenarios touch (the villager fields, the singleton pointer, the clock).
    struct Saved { unsigned char active, left; int health, age; unsigned accum, last; };
    static Saved saved[30];
    for (int i = 0; i < 30; ++i) {
        unsigned char *v = Villager(i);
        saved[i] = { v[0x1BB84], v[0x1BB88], *(int *)(v + 0x6B00), *(int *)(v + 0x6A54),
                     *(unsigned *)(v + 0x6AF4), *(unsigned *)(v + 0x6AF8) };
    }
    TestTimeFn tc = (TestTimeFn)GetProcAddress(dll, "VF2Fun_TestTime");
    ShowFn show = (ShowFn)GetProcAddress(dll, "VF2Fun_TestShowTime");
    if (!tc || !show) Fail("time test exports");
    WriteJmp(0x403FF0, (void *)&FakeSeconds);
    WriteJmp(0x49FB90, (void *)&FakeCareerType);
    WriteJmp(0x49C170, (void *)&FakeForgetPlans);
    WriteJmp(0x4948F0, (void *)&FakeSetLeftHome);
    WriteJmp(0x429AD0, (void *)&FakeQueueLifeEvent);
    WriteJmp(0x429960, (void *)&FakeUpdateCollege);
    *(unsigned char **)0x558FC0 = gameState;  // theGameState::Get() returns this
    unsigned char *gameTime = (unsigned char *)0x568088;
    *(int *)0x568080 = 0;                     // no registered CGameTimers
    gClock = 100000;

    // ---- pause and speed through the real CGameTime::SetSpeed
    {
        *(int *)(gameState + 0x25B18) = 10;
        *(int *)(gameTime + 0x20) = 10;
        *(int *)(gameTime + 0x24) = 10;
        *(unsigned *)(gameTime + 0x28) = gClock;
        *(unsigned *)(gameTime + 0x2C) = 0;
        struct { int op, arg; } script[] = {
            { 1, 0 }, { 1, 0 }, { 2, 0 }, { 2, 0 }, { 3, 5 }, { 1, 0 }, { 3, 2 }, { 2, 0 }, { 3, 1 },
            { 1, 0 }, { 3, 10 }, { 2, 0 }, { 3, 1 }, { 3, 10 },
        };
        char rows[1200];
        int len = 0;
        for (auto &s : script) {
            tc(s.op, s.arg);
            len += _snprintf_s(rows + len, sizeof rows - len, _TRUNCATE, "%s[%d, %d, %d, %d]", len ? ", " : "",
                               s.op, s.arg, *(int *)(gameState + 0x25B18), *(int *)(gameTime + 0x20));
        }
        // The Options dialog's paused edge: field exactly 999.
        *(int *)(gameState + 0x25B18) = 999;
        *(int *)(gameTime + 0x20) = 999;
        tc(2, 0);
        len += _snprintf_s(rows + len, sizeof rows - len, _TRUNCATE, ", [2, -1, %d, %d]",
                           *(int *)(gameState + 0x25B18), *(int *)(gameTime + 0x20));
        Out("{\"time_speed\": [%s]}", rows);
    }

    // ---- time warp through the real AllVillagersTimeflowUpkeep
    for (int c = 0; c < 3; ++c) {
        ClearVillagers();
        *(int *)(gameState + 0x25B18) = 10;
        *(int *)(gameTime + 0x20) = 10;
        *(unsigned *)0x568038 = 0;
        gCareer = 1;
        gForgetCalls = gLeftHomeCalls = gQueueLifeCalls = gCollegeCalls = 0;
        // 0 A: adult at home, 1300 s of native time (= 2 native ticks + 100 s over)
        // 1 B: child at home;  2 C: left home;  3 D: not active;  4 E: dead
        // 5 F (case 2): 19th year is 2 ticks away, no career -> leaves home when it turns 19
        SetupVillager(0, 1, 0, 5, 400, 1300, gClock);
        SetupVillager(1, 1, 0, 3, 100, 0, gClock);
        SetupVillager(2, 1, 1, 5, 500, 0, gClock);
        SetupVillager(3, 0, 0, 5, 0, 0, gClock);
        SetupVillager(4, 1, 0, 0, 300, 0, gClock);
        if (c == 2) {
            SetupVillager(5, 1, 0, 3, 350, 0, gClock);
            gCareer = 0;
        }
        TimeflowFn timeflow = (TimeflowFn)0x499700;
        int pending = -1;
        if (c >= 1) {
            tc(4, 60);
            pending = tc(5, 0);
        }
        if (c == 1) {
            // E (not alive) and C (left home) never get ticks; D is not active.
            // A villager who dies before the game reaches them is dropped.
            SetupVillager(1, 1, 0, 0, 100, 0, gClock);  // B dies after the warp was queued
        }
        int after[2][6];
        unsigned remainder[2];
        int pendingAfter[2];
        for (int pass = 0; pass < 2; ++pass) {
            timeflow((void *)0x5B9F58, false);
            for (int i = 0; i < 6; ++i) after[pass][i] = *(int *)(Villager(i) + 0x6A54);
            remainder[pass] = *(unsigned *)(Villager(0) + 0x6AF4);
            pendingAfter[pass] = tc(5, 0);
        }
        Out("{\"time_warp\": %d, \"pending\": %d, \"ages1\": [%d, %d, %d, %d, %d, %d], \"ages2\": [%d, %d, %d, %d, %d, %d], "
            "\"remainder\": [%u, %u], \"pending_after\": [%d, %d], \"oldest\": %u, \"left_home_calls\": %d, "
            "\"left_home_ok\": %d, \"forget\": %d, \"queued\": %d, \"college\": %d}",
            c, pending, after[0][0], after[0][1], after[0][2], after[0][3], after[0][4], after[0][5],
            after[1][0], after[1][1], after[1][2], after[1][3], after[1][4], after[1][5], remainder[0],
            remainder[1], pendingAfter[0], pendingAfter[1], *(unsigned *)0x568038, gLeftHomeCalls,
            gLeftHomeThis == (void *)Villager(5) ? 1 : 0, gForgetCalls, gQueueLifeCalls, gCollegeCalls);
    }
    // A warp with nobody eligible queues nothing.
    ClearVillagers();
    tc(4, 60);
    Out("{\"time_warp_nobody\": %d}", tc(5, 0));

    // ---- the store screen: constructor wrapper and HandleMessage detour
    WriteJmp(0x4C379D, (void *)&FakeNew);
    WriteJmp(0x448950, (void *)&FakeGraphicsGet);
    WriteJmp(0x448710, (void *)&FakeGetImageGrid);
    WriteJmp(0x449610, (void *)&FakeStringsGet);
    WriteJmp(0x448E80, (void *)&FakeGetLargeFont);
    WriteJmp(0x401A40, (void *)&FakeButtonCtor);
    WriteJmp(0x4015E0, (void *)&FakeButtonSetText);
    WriteJmp(0x40CF80, (void *)&FakeAddControl);
    WriteJmp(0x432050, (void *)&FakeSetStoreCategory);
    {
        static unsigned char scene[0x400];
        memset(scene, 0, sizeof scene);
        *(int *)(scene + 0xE0) = 0x70;  // widescreen offset
        unsigned at = 0x4332A5;
        unsigned target = at + 5 + *(int *)(at + 1);
        typedef void (__fastcall *CategoryFn)(void *, void *, int);
        gOrder = 0;
        gButtonCalls = gAddCalls = gCategoryCalls = 0;
        ((CategoryFn)target)(scene, 0, 2);
        Out("{\"store_ctor\": {\"target\": %u, \"category_calls\": %d, \"category\": %d, \"category_scene_ok\": %d, "
            "\"buttons\": %d, \"id\": %d, \"image\": %d, \"graphics_ok\": %d, \"x\": %d, \"y\": %d, \"flag\": %d, "
            "\"scene_ok\": %d, \"new_size\": %u, \"text\": \"%s\", \"colours_ok\": %d, \"font_ok\": %d, "
            "\"added\": %d, \"added_ok\": %d, \"text_this_ok\": %d}}",
            target, gCategoryCalls, gCategoryValue, gCategoryScene == scene ? 1 : 0, gButtonCalls, gButtonId, gImage,
            gImageGraphics == (void *)0x7000001 ? 1 : 0, gButtonX, gButtonY, gButtonFlag,
            gButtonScene == scene ? 1 : 0, gNewSize, gText,
            gTextC1 == *(unsigned *)0x5347E4 && gTextC2 == gTextC1 && gTextC3 == gTextC1 ? 1 : 0,
            gTextFont == (void *)0x7000004 && gFontStrings == (void *)0x7000003 ? 1 : 0, gAddCalls,
            gAddScene == scene && gAddControl == gButtonSelf && gTextSelf == gButtonSelf &&
                gButtonSelf == (void *)gPool[(gPoolUsed - 1) & 7] ? 1 : 0,
            gTextSelf == gButtonSelf ? 1 : 0);

        // HandleMessage entry: other messages reach the stock body.
        struct { int message; long param; const char *name; } msgs[] = {
            { 7, 1, "other_message" }, { 8, 99, "unknown_button" }, { 8, 0x5646, "time_button" },
        };
        Driver d = {};
        for (auto &m : msgs) {
            scene[0x164] = 0xAA;
            scene[0x154] = scene[0x155] = scene[0x156] = scene[0x157] = 0;  // no scroll range
            HandleCall call = { (StoreHandleFn)0x4322B0, scene, m.message, m.param, false };
            d.mode = 1;
            // A dialog that opens when it should not would block this
            // thread for good, so a watcher closes it and reports it.
            bool click = m.param == 0x5646 && m.message == 8;
            d.waitMs = click ? 5000 : 400;
            d.quiet = !click;
            if (installed) RunWithDriver(&d, CallStoreHandle, &call);
            else { d.len = 0; d.log[0] = 0; CallStoreHandle(&call); }
            Out("{\"store_message\": \"%s\", \"installed\": %d, \"result\": %d, \"stock_ran\": %d, \"dialog\": {%s}}",
                m.name, installed ? 1 : 0, call.result ? 1 : 0, scene[0x164] == 0 ? 1 : 0, d.log);
        }
    }

    // ---- the dialog itself, scripted
    if (installed) {
        ClearVillagers();
        SetupVillager(0, 1, 0, 5, 400, 0, gClock);
        SetupVillager(1, 1, 0, 3, 100, 0, gClock);
        *(int *)(gameState + 0x25B18) = 10;
        *(int *)(gameTime + 0x20) = 10;
        Driver d = {};
        d.mode = 2;
        RunWithDriver(&d, CallShow, (void *)show);
        int pendingAfterDialog = tc(5, 0);
        // The Yes the script gave is consumed by the game's next aging pass.
        ((TimeflowFn)0x499700)((void *)0x5B9F58, false);
        Out("{\"time_dialog_script\": {%s}, \"speed_field\": %d, \"game_speed\": %d, \"pending\": %d, "
            "\"ages_after\": [%d, %d], \"pending_after\": %d}", d.log,
            *(int *)(gameState + 0x25B18), *(int *)(gameTime + 0x20), pendingAfterDialog,
            *(int *)(Villager(0) + 0x6A54), *(int *)(Villager(1) + 0x6A54), tc(5, 0));
    }
    for (int i = 0; i < 30; ++i) {
        unsigned char *v = Villager(i);
        v[0x1BB84] = saved[i].active; v[0x1BB88] = saved[i].left;
        *(int *)(v + 0x6B00) = saved[i].health; *(int *)(v + 0x6A54) = saved[i].age;
        *(unsigned *)(v + 0x6AF4) = saved[i].accum; *(unsigned *)(v + 0x6AF8) = saved[i].last;
    }
    *(unsigned char **)0x558FC0 = 0;
    *(unsigned *)0x568038 = 0;
    *(int *)(gameTime + 0x20) = 0;
    *(int *)(gameTime + 0x24) = 0;
    *(unsigned *)(gameTime + 0x28) = 0;
}

#include "stage4_scenarios.inc"

int wmain(int argc, wchar_t **argv) {
    // "--hold": keep the process for the live-probe test. "--status-only":
    // stop after the install report (the image may be deliberately corrupt).
    if (argc == 2)
        return RunChild(argv[1], L"child");
    if (argc == 3 && wcscmp(argv[2], L"--hold") == 0)
        return RunChild(argv[1], L"hold");
    if (argc == 3 && wcscmp(argv[2], L"--status-only") == 0)
        return RunChild(argv[1], L"status");
    bool hold = argc == 3 && wcscmp(argv[2], L"hold") == 0;
    bool statusOnly = argc == 3 && wcscmp(argv[2], L"status") == 0;
    if (argc != 3 || (!hold && !statusOnly && wcscmp(argv[2], L"child") != 0)) {
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

    // vf2fun.cpp's status block (layout version 2) and test-build counters.
    struct Status {
        unsigned magic, version, moduleCount, requestedMask, pinsOkMask, installedMask, refusedMask,
            trampolinePage, writeMasks[16];
    };
    struct Counters {
        unsigned magic, chanceCalls, olderRolls, olderSuccesses, cooldownStores, cooldownSkips,
            nextGenerationCalls, nextGenerationOlderGrants, lastMotherAge, lastFatherAge,
            sceneActiveWrites, sceneNullSkips, timeButtonsAdded, timeDialogOpens, timeWarpsApplied;
    };
    volatile Status *status = (volatile Status *)GetProcAddress(dll, "VF2Fun_Status");
    if (!status) Fail("status export");
    volatile Counters *counters = (volatile Counters *)GetProcAddress(dll, "VF2Fun_TestCounters");
    if (!counters) {
        // A release build: report the install, skip the counted scenarios.
        Out("{\"counters_absent\": 1}");
        statusOnly = true;
    }
    IMAGE_NT_HEADERS32 *dnt = (IMAGE_NT_HEADERS32 *)((unsigned char *)dll + ((IMAGE_DOS_HEADER *)dll)->e_lfanew);
    unsigned dllLo = (unsigned)dll, dllHi = dllLo + dnt->OptionalHeader.SizeOfImage;

    // ---- what is now at every written site
    const unsigned sites[] = { 0x4A0810, 0x49F6DF, 0x430681, 0x430DB8, 0x43C0BD, 0x4407DC, 0x40D1DA,
                               0x4226A6, 0x44337B, 0x42A75E, 0x4322B0, 0x4332A5, 0x499893,
                               0x443F5C, 0x443B80, 0x443C00, 0x443A07, 0x444073,
                               0x49BBBD, 0x419A2F, 0x41AF0E, 0x41AF4B };
    const unsigned lens[] = { 8, 6, 5, 5, 5, 5, 5, 10, 10, 5, 7, 5, 5, 6, 8, 7, 5, 5, 9, 5, 5, 5 };
    const unsigned nSites = sizeof sites / sizeof sites[0];
    char hex[64];
    for (unsigned i = 0; i < nSites; ++i) {
        Hex(hex, (const unsigned char *)sites[i], lens[i]);
        Out("{\"site\": %u, \"bytes\": \"%s\", \"protect\": \"%s\"}", sites[i], hex, ProtAt(sites[i]));
    }
    {
        char masks[200];
        int mlen = 0;
        for (unsigned m = 0; m < 16; ++m)
            mlen += _snprintf_s(masks + mlen, sizeof masks - mlen, _TRUNCATE, "%s%u", m ? ", " : "",
                                status->writeMasks[m]);
        Out("{\"status\": {\"magic\": %u, \"version\": %u, \"modules\": %u, \"requested\": %u, \"pins_ok\": %u, "
            "\"installed\": %u, \"refused\": %u, \"trampoline\": %u, \"write_masks\": [%s], "
            "\"dll_lo\": %u, \"dll_hi\": %u, \"status_va\": %u}}",
            status->magic, status->version, status->moduleCount, status->requestedMask, status->pinsOkMask,
            status->installedMask, status->refusedMask, status->trampolinePage, masks, dllLo, dllHi,
            (unsigned)status);
    }
    if (status->trampolinePage) {
        Hex(hex, (const unsigned char *)status->trampolinePage, 16);
        Out("{\"trampoline\": %u, \"bytes\": \"%s\", \"protect\": \"%s\"}", status->trampolinePage, hex,
            ProtAt(status->trampolinePage));
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
    if (statusOnly) {
        Out("{\"done\": 1}");
        return 0;
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
    // ---- ldwScene::SetActive (0x40D1D0) through the copied stock body
    WriteJmp(0x402A40, (void *)&FakeEventManagerGet);
    WriteJmp(0x402AC0, (void *)&FakeSubscribe);
    WriteJmp(0x402740, (void *)&FakeUnsubscribe);
    WriteJmp(0x40D060, (void *)&FakeActivateControls);
    gFakeSceneVtable[0x24 / 4] = (void *)&FakeSceneVirtual;
    for (int bound = 1; bound >= 0; --bound)
        for (int arg = 1; arg >= 0; --arg) {
            unsigned char flagByte = 0xAA;
            FakeScene scene = { gFakeSceneVtable, bound ? &flagByte : 0 };
            *(void **)0x5595F8 = &scene;  // ldwScene::mLastUpdatedScene
            gSubscribeCalls = gUnsubscribeCalls = gActivateCalls = gVirtualCalls = 0;
            gActivateArg = gVirtualArg = -1;
            gSubscribeThis = gHandler = 0;
            int espDelta = 0;
            int crashed = CallSetActive(&scene, arg, &espDelta);
            Out("{\"set_active\": [%d, %d], \"crashed\": %d, \"flag\": %d, \"subscribe\": %d, \"unsubscribe\": %d, "
                "\"handler_ok\": %d, \"manager_ok\": %d, \"activate_controls\": %d, \"activate_arg\": %d, "
                "\"virtual\": %d, \"virtual_arg\": %d, \"last_cleared\": %d, \"esp_delta\": %d}",
                bound, arg, crashed, flagByte, gSubscribeCalls, gUnsubscribeCalls,
                gHandler == &scene ? 1 : 0, gSubscribeThis == gFakeEventManager ? 1 : 0, gActivateCalls,
                gActivateArg, gVirtualCalls, gVirtualArg, *(void **)0x5595F8 == 0 ? 1 : 0, espDelta);
        }

    // ---- Settings "Pause Game: Yes": the add at 0x4226A6 (esi = game state)
    {
        const int values[] = { 0, 10, 998, 999, 1000, 1009, 2008, -1 };
        for (int v = 0; v < 8; ++v) {
            *(int *)(gameState + 0x25B18) = values[v];
            in_eax = 0xA0A0A0A0; in_ebx = 0xB0B0B0B0; in_ecx = 0xC0C0C0C0; in_edx = 0xD0D0D0D0;
            in_esi = (unsigned)gameState; in_edi = 0xE0E0E0E0; in_ebp = 0xEBEBEBEB; in_flags = 0x2;
            RunSpan(0x4226A6, 0x4226B0);
            Out("{\"pause_yes\": %d, \"after\": %d, \"regs_same\": %d, \"esp_same\": %d}", values[v],
                *(int *)(gameState + 0x25B18),
                out_eax == in_eax && out_ebx == in_ebx && out_ecx == in_ecx && out_edx == in_edx &&
                    out_esi == in_esi && out_edi == in_edi && out_ebp == in_ebp ? 1 : 0,
                out_esp == gArriveEsp ? 1 : 0);
        }
    }

    // ---- theGameState::Load's CTech::LoadState call (0x42A75E), through its rel32
    {
        WriteJmp(0x4B9F40, (void *)&FakeHaveUpgrade);
        WriteJmp(0x4B4D10, (void *)&FakeResetSingle);
        WriteJmp(0x4B5300, (void *)&FakeIncrement);
        typedef bool (__fastcall *TechLoadFn)(void *, void *, const void *);
        unsigned at = 0x42A75E;
        unsigned target = at + 5 + *(int *)(at + 1);
        unsigned char saveState[16] = {};
        for (int c = 0; c < 6; ++c) {
            memset(gOwned, 0, sizeof gOwned);
            for (int item = 0xEB; item <= 0x109; ++item) {
                switch (c) {
                case 0: break;                                            // nothing owned
                case 1: gOwned[item] = 1; break;                          // everything
                case 2: gOwned[item] = item == 0xF6; break;               // one kitchen item
                case 3: gOwned[item] = item <= 0xEE || (item >= 0x100 && item <= 0x105); break;
                case 4: gOwned[item] = (item * 7 + 3) % 5 < 2; break;     // scattered
                case 5: gOwned[item] = 1; break;                          // everything, load fails
                }
            }
            if (c == 5) {
                gLoadResult = 0;
                WriteJmp(0x428230, (void *)&FakeTechLoadState);  // a failed native load
            }
            gEventLen = 0;
            gEvents[0] = 0;
            TechLoadFn fn = (TechLoadFn)target;
            bool loaded = fn((void *)0x5680E4, 0, saveState);
            Out("{\"tech_load\": %d, \"target\": %u, \"loaded\": %d, \"events\": [%s]}", c, target,
                loaded ? 1 : 0, gEvents);
        }
    }

    // ---- theMenuScene ctor's old Change Player rect (top store at 0x44337B)
    {
        static unsigned char menu[0x200];
        *(int *)(menu + 0x9C) = 0x146;          // left (widescreen offset 0)
        *(int *)(menu + 0xA0) = 0x55555555;     // top: written by the code under test
        *(int *)(menu + 0xA4) = 0x146 + 0xBE;   // right
        *(int *)(menu + 0xA8) = 0x117;          // bottom
        in_eax = 0xA0A0A0A0; in_ebx = 0xB0B0B0B0; in_ecx = 0xC0C0C0C0; in_edx = 0xD0D0D0D0;
        in_esi = (unsigned)menu; in_edi = 0xE0E0E0E0; in_ebp = 0xEBEBEBEB; in_flags = 0x2 | 0x40;
        RunSpan(0x44337B, 0x443385);
        typedef bool (__thiscall *PtInRectFn)(void *, int, int);
        PtInRectFn ptInRect = (PtInRectFn)0x4016A0;
        int inside = 0, firstY = -1, lastY = -1;
        for (int y = 0xE0; y <= 0x130; ++y)
            for (int x = 0x140; x <= 0x210; x += 4)
                if (ptInRect(menu + 0x9C, x, y)) {
                    inside++;
                    if (firstY < 0) firstY = y;
                    lastY = y;
                }
        Out("{\"title_hotspot\": 1, \"top\": %d, \"inside\": %d, \"first_y\": %d, \"last_y\": %d, "
            "\"regs_same\": %d, \"flags_same\": %d, \"esp_same\": %d}",
            *(int *)(menu + 0xA0), inside, firstY, lastY,
            out_eax == in_eax && out_ebx == in_ebx && out_ecx == in_ecx && out_edx == in_edx &&
                out_esi == in_esi && out_edi == in_edi && out_ebp == in_ebp ? 1 : 0,
            (out_flags & 0x8D5) == (in_flags & 0x8D5) ? 1 : 0, out_esp == gArriveEsp ? 1 : 0);
    }

    RunTimeScenarios(dll, gameState, (status->installedMask & (1u << 4)) != 0);
    RunMenuScenarios();
    RunMortalityScenarios();
    RunCollectableScenarios();

    Out("{\"counters\": {\"chance\": %u, \"older_rolls\": %u, \"older_successes\": %u, \"cooldown_stores\": %u, "
        "\"cooldown_skips\": %u, \"next_generation\": %u, \"older_grants\": %u, \"scene_writes\": %u, "
        "\"scene_null_skips\": %u, \"time_buttons\": %u, \"time_dialogs\": %u, \"time_warps\": %u}}",
        counters->chanceCalls, counters->olderRolls, counters->olderSuccesses, counters->cooldownStores,
        counters->cooldownSkips, counters->nextGenerationCalls, counters->nextGenerationOlderGrants,
        counters->sceneActiveWrites, counters->sceneNullSkips, counters->timeButtonsAdded,
        counters->timeDialogOpens, counters->timeWarpsApplied);
    if (hold) {
        // Keep this process alive for the live-probe test until stdin closes.
        Out("{\"holding\": %lu}", GetCurrentProcessId());
        char line[16];
        fgets(line, sizeof line, stdin);
    }
    Out("{\"done\": 1}");
    return 0;
}
