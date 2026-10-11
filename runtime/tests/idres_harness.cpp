// ID-reservation test harness (32-bit). NOT shipped; built and run by
// tests/test_runtime_id_reservation.py.
//
//   idres_harness.exe "<patched Virtual Families 2.exe>"
//
// Same method as stage1_harness.cpp: the PATCHED executable is copied to its
// image base 0x400000 as plain data (the game never starts), theGame's Init
// slot is called exactly as 0x42AFF8 does, which runs the real loader stub,
// which loads the real vf2fun.dll from "<harness folder>\Virtual Families 2
// Patcher Files\" and installs its modules into this copy. Then the REAL stock
// functions run on synthetic objects:
//
//   - theStringManager::GetString (0x448E90) and the inlined lookup of the
//     text-draw function (0x448F01..0x448F4A), against a lookup table built
//     the way the string manager's constructor builds it;
//   - the two id bounds of CAchievement::DrawAchievement (spans of the real code);
//   - CAchievement::IncrementProgress / SetComplete / PercentCompleted, and
//     SaveState / LoadState for the save round trips;
//   - CAchievementsScene::DrawScene (0x42CC80), with recorders in place of the
//     graphics and window calls, to see which achievement ids it draws.
//
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

// ------------------------------------------------------------ recorders
static void *gInitThis;
static int gInitCalls;
static bool __fastcall FakeInit(void *self, void *) {
    gInitThis = self;
    gInitCalls++;
    return true;
}

static unsigned gClock = 1000;
static unsigned __fastcall FakeSeconds(void *, void *) { return gClock; }  // CGameTime::Seconds

// ------------------------------------------------------------ register-level span runner
// Runs copied game code from `entry` with the in_* registers and a 0x200-byte
// scratch stack (initialised from gScratch) until it reaches one of two planted
// resume points, then comes back here with the registers in out_*.
static unsigned in_eax, in_ebx, in_ecx, in_edx, in_esi, in_edi, in_ebp, in_flags;
static unsigned out_eax, out_ebx, out_ecx, out_edx, out_esi, out_edi, out_ebp, out_esp, out_flags;
static unsigned gSaveEsp, gSpanEntry, gWhich;
static unsigned gScratch[0x80];

static __declspec(naked) void CaptureCommon() {
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
static __declspec(naked) void CaptureA() { __asm { mov gWhich, 1 } __asm { jmp CaptureCommon } }
static __declspec(naked) void CaptureB() { __asm { mov gWhich, 2 } __asm { jmp CaptureCommon } }

static __declspec(naked) void RunSpanAsm() {
    __asm {
        pushad
        pushfd
        mov gSaveEsp, esp
        sub esp, 0x200
        lea edi, [esp]
        mov esi, offset gScratch
        mov ecx, 0x80
        cld
        rep movsd
        push in_flags
        popfd
        mov eax, in_eax
        mov ebx, in_ebx
        mov ecx, in_ecx
        mov edx, in_edx
        mov esi, in_esi
        mov edi, in_edi
        mov ebp, in_ebp
        jmp dword ptr [gSpanEntry]
    }
}

static int RunSpan(unsigned entry, unsigned resumeA, unsigned resumeB) {
    gSpanEntry = entry;
    gWhich = 0;
    WriteJmp(resumeA, (void *)&CaptureA);
    if (resumeB) WriteJmp(resumeB, (void *)&CaptureB);
    out_esp = 0;
    RunSpanAsm();
    return (int)gWhich;
}

static void SetRegs(unsigned eax, unsigned ebx, unsigned ecx, unsigned edx, unsigned esi, unsigned edi, unsigned ebp) {
    in_eax = eax; in_ebx = ebx; in_ecx = ecx; in_edx = edx; in_esi = esi; in_edi = edi; in_ebp = ebp;
    in_flags = 0x202;
    memset(gScratch, 0, sizeof gScratch);
}

// ------------------------------------------------------------ achievement objects
static const unsigned kRecords = 0x125, kRecordSize = 12;
static const unsigned kObjectSize = 0x1000;  // CAchievement is 0xF50 bytes; the queue is at +0xDBC

static const unsigned A_SAVE_STATE = 0x4B4C80;           // SaveState(dest)      ret 4
static const unsigned A_IS_COMPLETE = 0x4B4CC0;          // IsComplete(id)       ret 4
static const unsigned A_PERCENT_COMPLETED = 0x4B4CD0;    // PercentCompleted(id) ret 4
static const unsigned A_LOAD_STATE = 0x4B51E0;           // LoadState(src)       ret 4
static const unsigned A_INCREMENT_PROGRESS = 0x4B5300;   // IncrementProgress(id, amount) ret 8
static const unsigned A_RESET_NOTIFY_QUEUE = 0x4B5190;   // queue slots = -1

typedef int (__thiscall *Call0)(void *self);
typedef int (__thiscall *Call1)(void *self, int a);
typedef int (__thiscall *Call2)(void *self, int a, int b);

static unsigned char *NewAchievement() {
    unsigned char *o = (unsigned char *)VirtualAlloc(0, kObjectSize, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!o) Fail("alloc achievement object");
    memset(o, 0, kObjectSize);
    ((Call0)A_RESET_NOTIFY_QUEUE)(o);
    return o;
}

static void SetRecord(unsigned char *o, unsigned id, unsigned char flag, int progress, int stamp) {
    unsigned char *r = o + id * kRecordSize;
    r[0] = flag;
    *(int *)(r + 4) = progress;
    *(int *)(r + 8) = stamp;
}

static void DumpRecords(const char *label, const unsigned char *o) {
    static char hex[kRecords * kRecordSize * 2 + 1];
    Hex(hex, o, kRecords * kRecordSize);
    Out("{\"records\": \"%s\", \"hex\": \"%s\"}", label, hex);
}

// ------------------------------------------------------------ DrawScene recorders
static unsigned char gFakeGameState[0x26000];
static unsigned char gFakeWindow[64], gFakeGraphics[64];
static int gDrawn[256], gDrawnCount;
static void *__cdecl FakeGetWindow() { return gFakeWindow; }
static void *__cdecl FakeGetGraphics() { return gFakeGraphics; }
static void *__cdecl FakeGetGameState() { return gFakeGameState; }
static void __fastcall FakeGraphicsDraw(void *, void *, int, int, int, float, int) {}    // ret 14h
static void __fastcall FakeSetClip(void *, void *, int, int, int, int) {}                // ret 10h
static void __fastcall FakeNoArgs(void *, void *) {}
static void __fastcall FakeDrawAchievement(void *, void *, int, int, int id, int, float) {  // ret 14h
    if (gDrawnCount < 256) gDrawn[gDrawnCount++] = id;
}

typedef void (__thiscall *DrawSceneFn)(void *);

// ------------------------------------------------------------ string lookup
// theStringManager's constructor (0x449300) fills lookupTable[id] for id 1..0xA68
// by scanning the 0xA5D-entry stringTable (0x53DCC0, 0x10 bytes each) for the
// entry whose first dword is the id, else 0. Do exactly that here, so the real
// GetString runs against the table the game builds.
static void BuildStringLookup() {
    unsigned *lookup = (unsigned *)0x56ECF0;
    for (unsigned id = 1; id < 0xA69; ++id) {
        unsigned entry = 0;
        for (unsigned i = 0; i < 0xA5D; ++i) {
            unsigned e = 0x53DCC0 + i * 0x10;
            if (*(unsigned *)e == id) { entry = e; break; }
        }
        lookup[id] = entry;
    }
}

typedef const char *(__thiscall *GetStringFn)(void *self, unsigned id);

static void PrintText(const char *key, const char *prefix, const char *text) {
    char hex[200];
    unsigned n = 0;
    while (text[n] && n < 96) ++n;
    Hex(hex, (const unsigned char *)text, n);
    Out("{\"%s\": \"%s\", \"ptr\": %u, \"hex\": \"%s\"}", key, prefix, (unsigned)text, hex);
}

// ------------------------------------------------------------ main
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
    if (image != (unsigned char *)IMAGE_BASE) Fail("reserve image range");
    memcpy(image, file, nt->OptionalHeader.SizeOfHeaders);
    IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        unsigned n = sec[i].SizeOfRawData < sec[i].Misc.VirtualSize ? sec[i].SizeOfRawData : sec[i].Misc.VirtualSize;
        if (sec[i].Misc.VirtualSize == 0) n = sec[i].SizeOfRawData;
        memcpy(image + sec[i].VirtualAddress, file + sec[i].PointerToRawData, n);
    }
    HMODULE k32 = GetModuleHandleA("kernel32.dll");
    *(void **)0x4DE1E4 = (void *)GetProcAddress(k32, "GetModuleHandleA");
    *(void **)0x4DE1E8 = (void *)GetProcAddress(k32, "GetProcAddress");

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
    Out("{\"bootstrap\": {\"init_result\": %d, \"init_calls\": %d, \"stub_state\": %u, \"dll_loaded\": %d}}",
        initResult ? 1 : 0, gInitCalls, stubState, dll ? 1 : 0);

    struct Status {
        unsigned magic, version, moduleCount, requestedMask, pinsOkMask, installedMask, refusedMask,
            trampolinePage, writeMasks[16];
    };
    volatile Status *status = dll ? (volatile Status *)GetProcAddress(dll, "VF2Fun_Status") : 0;
    if (status) {
        Out("{\"status\": {\"magic\": %u, \"version\": %u, \"modules\": %u, \"requested\": %u, \"pins_ok\": %u, "
            "\"installed\": %u, \"refused\": %u, \"trampoline\": %u, \"write_masks\": [%u, %u, %u, %u, %u, %u, %u, %u, %u, %u, %u]}}",
            status->magic, status->version, status->moduleCount, status->requestedMask, status->pinsOkMask,
            status->installedMask, status->refusedMask, status->trampolinePage, status->writeMasks[0],
            status->writeMasks[1], status->writeMasks[2], status->writeMasks[3], status->writeMasks[4],
            status->writeMasks[5], status->writeMasks[6], status->writeMasks[7], status->writeMasks[8],
            status->writeMasks[9], status->writeMasks[10]);
    }
    if (dll) {
        IMAGE_NT_HEADERS32 *dnt = (IMAGE_NT_HEADERS32 *)((unsigned char *)dll + ((IMAGE_DOS_HEADER *)dll)->e_lfanew);
        Out("{\"dll_range\": [%u, %u]}", (unsigned)dll, (unsigned)dll + dnt->OptionalHeader.SizeOfImage);
    }

    // ---- no page anywhere in the process is writable and executable
    {
        unsigned addr = 0x10000, wx = 0;
        MEMORY_BASIC_INFORMATION m;
        while (addr < 0x7FFF0000 && VirtualQuery((void *)addr, &m, sizeof m)) {
            if (m.State == MEM_COMMIT &&
                ((m.Protect & 0xFF) == PAGE_EXECUTE_READWRITE || (m.Protect & 0xFF) == PAGE_EXECUTE_WRITECOPY))
                wx++;
            addr = (unsigned)m.BaseAddress + (unsigned)m.RegionSize;
        }
        Out("{\"wx_regions\": %u}", wx);
    }

    // ---- what is now at every field and stub site (the bytes the DLL may write)
    struct Site { unsigned va; unsigned len; };
    static const Site sites[] = {
        { 0x4B4CFF, 4 }, { 0x4B4F1D, 4 }, { 0x4B4F47, 4 }, { 0x4B4F72, 4 },    // achievementList readers
        { 0x4B4FCE, 4 }, { 0x4B507D, 4 }, { 0x4B5327, 4 }, { 0x4B53CE, 4 },
        { 0x4B4E07, 1 }, { 0x4B4EF6, 1 },                                      // DrawAchievement bounds
        { 0x42CADF, 4 }, { 0x42CAEA, 4 }, { 0x42CD34, 1 }, { 0x42CD3A, 4 }, { 0x42CD68, 4 },  // scene
        { 0x4B5213, 1 }, { 0x4B5216, 4 }, { 0x4B5231, 4 }, { 0x4B523F, 4 }, { 0x4B5244, 4 },  // LoadState
        { 0x448EC7, 5 }, { 0x448F43, 7 },                                      // string failure blocks
    };
    char hex[64];
    for (unsigned i = 0; i < sizeof sites / sizeof sites[0]; ++i) {
        Hex(hex, (const unsigned char *)sites[i].va, sites[i].len);
        Out("{\"site\": %u, \"bytes\": \"%s\", \"protect\": \"%s\"}", sites[i].va, hex, ProtAt(sites[i].va));
    }

    // ---- the retargeted tables exactly as the stock readers see them now
    unsigned rowsBase = *(unsigned *)0x4B4CFF - 4;             // idiv [ecx*4 + list + 4]
    unsigned orderBase = *(unsigned *)0x42CD3A;                // lea ebp,[ebp*4 + order]
    int orderCount = (signed char)*(unsigned char *)0x42CD34;  // cmp ebp,imm8
    bool rowsMoved = rowsBase != 0x54BB50;
    bool orderMoved = orderBase != 0x4E2AE0;
    {
        static char big[200 * 28 * 2 + 1];
        unsigned nrows = rowsMoved ? 0x60 : 0x5F;
        Hex(big, (const unsigned char *)rowsBase, nrows * 28);
        Out("{\"rows_base\": %u, \"rows\": %u, \"hex\": \"%s\"}", rowsBase, nrows, big);
        unsigned n = orderMoved ? (unsigned)orderCount : 0x5F;
        Hex(big, (const unsigned char *)orderBase, n * 4);
        Out("{\"order_base\": %u, \"order_count\": %u, \"hex\": \"%s\"}", orderBase, n, big);
    }

    // ---- strings: the real GetString and the real inlined lookup
    BuildStringLookup();
    {
        unsigned ids[16];
        unsigned n = 0;
        ids[n++] = 0; ids[n++] = 1; ids[n++] = 0x100; ids[n++] = 0x868;
        for (unsigned id = 1; id < 0xA69 && n < 7; ++id)           // the first stock gaps
            if (((unsigned *)0x56ECF0)[id] == 0) ids[n++] = id;
        ids[n++] = 0xA68; ids[n++] = 0xA69; ids[n++] = 0xE30; ids[n++] = 0xE31; ids[n++] = 0xE32; ids[n++] = 0xE33;
        ids[n++] = 0x1000;
        for (unsigned i = 0; i < n; ++i) {
            const char *got = ((GetStringFn)0x448E90)(0, ids[i]);
            char key[32];
            _snprintf_s(key, sizeof key, _TRUNCATE, "get_%u", ids[i]);
            PrintText("string", key, got);
            SetRegs(0x11111111, 0x22222222, ids[i], 0x33333333, 0x44444444, 0x55555555, 0x66666666);
            RunSpan(0x448F01, 0x448F4A, 0);
            const char *inl = *(const char **)out_esp;
            _snprintf_s(key, sizeof key, _TRUNCATE, "inline_%u", ids[i]);
            PrintText("string", key, inl);
            Out("{\"inline_regs\": %u, \"edx\": %d, \"ebx\": %d, \"esi\": %d, \"edi\": %d, \"ebp\": %d}", ids[i],
                out_edx == in_edx, out_ebx == in_ebx, out_esi == in_esi, out_edi == in_edi, out_ebp == in_ebp);
        }
    }

    // ---- DrawAchievement's two id bounds, run from the real code
    {
        unsigned char *o = NewAchievement();
        const unsigned ids[] = { 0x5E, 0x5F, 0x60, 0x7E };
        for (unsigned i = 0; i < sizeof ids / sizeof ids[0]; ++i) {
            SetRecord(o, ids[i], 1, 12, 7);
            // 0x4B4DFE: mov ebp,[esp+12Ch]; cmp ebp,bound; mov [esp+30h],eax; jge +0Dh;
            //           lea eax,[ebp+ebp*2]; mov cl,[esi+eax*4]; mov [esp+17h],cl; jmp 4B4E20
            SetRegs(0, 0, 0, 0, (unsigned)o, 0, 0);
            gScratch[0x12C / 4] = ids[i];
            RunSpan(0x4B4DFE, 0x4B4E20, 0);
            int flag = *(unsigned char *)(out_esp + 0x17);
            // 0x4B4EF4: cmp ebp,bound; jge 4B50FE (row skipped) else falls to 4B4EFD
            SetRegs(0, 0, 0, 0, (unsigned)o, 0, ids[i]);
            int which = RunSpan(0x4B4EF4, 0x4B4EFD, 0x4B50FE);
            Out("{\"draw_bound\": %u, \"complete_flag_read\": %d, \"row_drawn\": %d}", ids[i], flag, which == 1);
        }
    }

    // ---- progress, completion and the notify queue, through the real CAchievement code
    WriteJmp(0x427920, (void *)&FakeSeconds);
    {
        unsigned char *o = NewAchievement();
        // a stock row: id 1 ("1000" target)
        ((Call2)A_INCREMENT_PROGRESS)(o, 1, 500);
        Out("{\"stock_row1\": {\"percent\": %d, \"complete\": %d, \"progress\": %d}}",
            ((Call1)A_PERCENT_COMPLETED)(o, 1), ((Call1)A_IS_COMPLETE)(o, 1) & 0xFF, *(int *)(o + 12 + 4));
        if (rowsMoved) {
            Out("{\"orn_start\": {\"percent\": %d}}", ((Call1)A_PERCENT_COMPLETED)(o, 0x5F));
            ((Call2)A_INCREMENT_PROGRESS)(o, 0x5F, 6);
            int half = ((Call1)A_PERCENT_COMPLETED)(o, 0x5F);
            int halfDone = ((Call1)A_IS_COMPLETE)(o, 0x5F) & 0xFF;
            ((Call2)A_INCREMENT_PROGRESS)(o, 0x5F, 6);
            Out("{\"orn\": {\"half_percent\": %d, \"half_complete\": %d, \"percent\": %d, \"complete\": %d, "
                "\"progress\": %d, \"stamp\": %d, \"queue0\": %d, \"queue1\": %d}}",
                half, halfDone, ((Call1)A_PERCENT_COMPLETED)(o, 0x5F), ((Call1)A_IS_COMPLETE)(o, 0x5F) & 0xFF,
                *(int *)(o + 0x5F * 12 + 4), *(int *)(o + 0x5F * 12 + 8), *(int *)(o + 0xDBC), *(int *)(o + 0xDC0));
            // The record a real completion wrote survives SaveState -> LoadState byte for byte.
            static unsigned char buf[0x125 * 12];
            ((Call1)A_SAVE_STATE)(o, (int)buf);
            unsigned char *back = NewAchievement();
            ((Call1)A_LOAD_STATE)(back, (int)buf);
            Out("{\"orn_roundtrip\": {\"equal\": %d, \"flag\": %d, \"progress\": %d, \"stamp\": %d}}",
                memcmp(o, back, kRecords * kRecordSize) == 0, back[0x5F * 12],
                *(int *)(back + 0x5F * 12 + 4), *(int *)(back + 0x5F * 12 + 8));
        }
    }

    // ---- save round trips: SaveState from one object, LoadState into a fresh one
    {
        struct Case { const char *name; int ornament; int others; int tail; };
        static const Case cases[] = {
            { "vanilla_format", 0, 0, 0 },
            { "ornament_saved", 1, 0, 0 },
            { "other_features", 1, 1, 0 },
            { "reserved_tail", 1, 1, 1 },
            { "reserved_far", 1, 1, 2 },     // data only in the very last record of the tail
        };
        for (unsigned c = 0; c < sizeof cases / sizeof cases[0]; ++c) {
            unsigned char *src = NewAchievement();
            for (unsigned id = 0; id < 0x5F; ++id)
                SetRecord(src, id, (unsigned char)(id % 3 == 0), (int)(id * 7), (int)(id * 100));
            if (cases[c].ornament) SetRecord(src, 0x5F, 1, 12, 5000);
            if (cases[c].others) {
                SetRecord(src, 0x60, 1, 1, 6000);
                SetRecord(src, 0x7F, 0, 3, 0);
                SetRecord(src, 0xAB, 1, 1, 7000);
            }
            if (cases[c].tail == 1) {
                SetRecord(src, 0xAC, 0, 5, 0);
                SetRecord(src, 0xB0, 0, 0, 9999);   // only the +8 stamp: neither scanned nor cleared
                SetRecord(src, 0x124, 1, 0, 0);
            } else if (cases[c].tail == 2) {
                SetRecord(src, 0x124, 1, 0, 0);
            }
            static unsigned char buf[0x125 * 12 + 64];
            memset(buf, 0xEE, sizeof buf);
            ((Call1)A_SAVE_STATE)(src, (int)buf);
            bool saved = memcmp(buf, src, kRecords * kRecordSize) == 0 && buf[kRecords * kRecordSize] == 0xEE;
            unsigned char *dst = NewAchievement();
            memset(dst, 0x77, kRecords * kRecordSize);   // LoadState must overwrite every record
            ((Call1)A_LOAD_STATE)(dst, (int)buf);
            Out("{\"save_case\": \"%s\", \"saved_ok\": %d}", cases[c].name, saved ? 1 : 0);
            DumpRecords(cases[c].name, dst);
        }
    }

    // ---- the Achievements screen: which ids DrawScene draws at each scroll offset
    WriteJmp(0x4089F0, (void *)&FakeGetWindow);
    WriteJmp(0x448950, (void *)&FakeGetGraphics);
    WriteJmp(0x42AC20, (void *)&FakeGetGameState);
    WriteJmp(0x448AE0, (void *)&FakeGraphicsDraw);
    WriteJmp(0x408D50, (void *)&FakeSetClip);
    WriteJmp(0x4B4D30, (void *)&FakeDrawAchievement);
    WriteJmp(0x408D80, (void *)&FakeNoArgs);
    {
        unsigned char scene[0x100];
        for (unsigned idx = 0; idx < 0x62; ++idx) {
            memset(scene, 0, sizeof scene);
            *(int *)(scene + 0x08) = 0x10;
            *(int *)(scene + 0x0C) = 0x20;
            *(int *)(scene + 0x10) = 0x55;     // top   (constructor 0x42CAC6)
            *(int *)(scene + 0x14) = 0x40;
            *(int *)(scene + 0x18) = 0x300;    // bottom
            int scroll = (int)(idx * 0x42 + (idx % 5) * 3);
            *(int *)(scene + 0x50) = scroll;
            gDrawnCount = 0;
            ((DrawSceneFn)0x42CC80)(scene);
            char line[1500];
            line[0] = 0;
            int len = 0;
            for (int k = 0; k < gDrawnCount; ++k)
                len += _snprintf_s(line + len, sizeof line - len, _TRUNCATE, "%s%d", k ? ", " : "", gDrawn[k]);
            Out("{\"scene_index\": %u, \"scroll\": %d, \"ids\": [%s]}", idx, scroll, line);
        }
    }
    Out("{\"done\": 1}");
    return 0;
}
