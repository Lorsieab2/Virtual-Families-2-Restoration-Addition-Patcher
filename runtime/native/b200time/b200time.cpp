// vf2time_b200.dll -- the Time Controls companion DLL for the B200 Virtual
// Families 2 executable.
//
// It is the Settings-menu Time Controls module of the runtime-hook build
// (vf2fun_time.inc on the runtime branch), re-proved against B200 and made
// self-contained: B200 has no other runtime hooks, so this DLL has its own tiny
// host. One feature, one DLL: nothing else is installed here.
//
// The B200 executable is RELOCATED (DYNAMICBASE, with a .reloc section), so
// every game address in b200time_sites.h is a link-time VA at base 0x400000 and
// is rebased by `Delta` (live module base - 0x400000) before it is used. A pin
// compares the live bytes with every relocated 32-bit field taken back to its
// link-time value.
//
// The executable's loader calls B200Time_Startup() once, before the game loop.
// Installing is: setting -> pins -> plan -> apply. With the TimeControls key off
// (or missing) or any pin different, NOTHING is written and the game keeps
// B200's own bytes.
//
//   1. The Settings dialog constructor's last call (`call SetChecked` on the last
//      check box, 0x4A621B) is retargeted to a stub that makes the same call
//      and then adds one more button (id 9) at x = 30, built as the constructor
//      builds Evict: same art, y, font and colour.
//   2. theOptionsDialog's HandleMessage vtable slot 3 (0x4A6940) is replaced. A
//      click on that button opens the dialog; every other message goes to the
//      game's own handler unchanged.
//   3. Speed and pause use the game's own CGameTime::SetSpeed and the speed field
//      in theGameState, exactly as the Space key does. Slow, Normal and Fast are
//      the engine's own 20, 10 and 5 (AllVillagersTimeflowUpkeep compares the
//      speed field with exactly those three to cap its catch-up).
//   4. The speed is NOT saved as chosen. theGameState saves the speed field and
//      CGameTime's speed with the village, and a load catches up the hours the
//      game was closed at that speed (a village saved at 10x aged 26 years in
//      seconds and died, found live in the Virtual Families 1 port). Save and Load
//      (vtable slots 14 and 13) are replaced: Save writes any non-stock speed as
//      normal and puts the live speed back right after; a successful Load turns
//      any non-stock speed into normal (paused stays paused).
//   5. Time Warp queues extra age ticks. The one `call IncrementAge` in
//      AllVillagersTimeflowUpkeep is retargeted to a wrapper that adds them for
//      each queued villager and calls the same function. The accumulator
//      remainder uses the NATIVE ticks (saved in [ebp-14h] before the call), so
//      it is untouched. No age is written directly, so leaving home at 19 and
//      the oldest-age record still run.

#define WIN32_LEAN_AND_MEAN
// The dialog uses modern (comctl32 v6) controls through the manifest dependency
// below (embedded by /MANIFEST:EMBED); ISOLATION_AWARE makes this DLL's own
// windows use it without touching the game's. The emulator test build leaves it
// out (the wrappers are Microsoft's activation-context code, not this module's).
#ifndef B200TIME_TEST
#define ISOLATION_AWARE_ENABLED 1
#endif
#include <windows.h>
#include <stdio.h>

#pragma comment(lib, "user32.lib")
#pragma comment(linker, "/MANIFESTDEPENDENCY:\"type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='x86' publicKeyToken='6595b64144ccf1df' language='*'\"")

#include "b200time_sites.h"

// ---------------------------------------------------------------- relocation
static unsigned Delta;  // live module base - 0x400000
static inline unsigned A(unsigned linkTimeVa) { return linkTimeVa + Delta; }

// ---------------------------------------------------------------- status block
// B200Time_Status: what this launch installed. Written only by the install path
// in B200Time_Startup. Layout version 1:
//   magic 'B2TC', version, requested (1 = setting on), pinsOk (1 = every pin
//   matched), installed (1 = every write is live), writeMask (bit w: write w live)
struct B200TimeStatus {
    unsigned magic;
    unsigned version;
    unsigned requested;
    unsigned pinsOk;
    unsigned installed;
    unsigned writeMask;
};
extern "C" __declspec(dllexport) volatile B200TimeStatus B200Time_Status = { 0x43543242u, 1u, 0, 0, 0, 0 };

static HMODULE ThisModule;
static wchar_t Folder[MAX_PATH];

// ---------------------------------------------------------------- log
// vf2time.log beside the DLL: one short record of what this launch installed.
static bool LogStarted;

#ifdef B200TIME_TEST
// Test builds run under an emulator without the C runtime's start-up: no log.
static void Log(const char *, ...) {}
#else
static void Log(const char *fmt, ...) {
    wchar_t path[MAX_PATH];
    if (_snwprintf_s(path, MAX_PATH, _TRUNCATE, L"%svf2time.log", Folder) < 0)
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
#endif

// ================================================================ plan
static const unsigned kMaxWrites = 8;

struct HookWrite {
    unsigned va;      // live address
    unsigned len;
    bool data;        // a 4-byte vtable slot (never made executable), not code
    unsigned char bytes[8];
    unsigned char original[8];
};

struct Plan {
    HookWrite writes[kMaxWrites];
    unsigned count;
    bool ok;

    HookWrite *Add(unsigned liveVa, unsigned len, bool data) {
        if (!ok || count >= kMaxWrites) { ok = false; return 0; }
        HookWrite &w = writes[count++];
        w.va = liveVa;
        w.len = len;
        w.data = data;
        for (unsigned i = 0; i < 8; ++i) { w.bytes[i] = 0; w.original[i] = 0; }
        return &w;
    }
    // Replace the 4-byte function pointer in the vtable slot (link-time va) with `to`.
    void Slot(unsigned va, const void *to) {
        HookWrite *w = Add(A(va), 4, true);
        if (!w) return;
        *(unsigned *)w->bytes = (unsigned)to;
    }
    // Retarget the 5-byte `call rel32` at va (pinned as E8 by the generator) to `to`.
    void Retarget(unsigned va, const void *to) {
        HookWrite *w = Add(A(va), 5, false);
        if (!w) return;
        w->bytes[0] = *(const unsigned char *)A(va);
        *(int *)(w->bytes + 1) = (int)((unsigned)to - (A(va) + 5));
    }
};

// ---------------------------------------------------------------- pins
static bool InImage(unsigned liveVa, unsigned len) {
    HMODULE exe = GetModuleHandleW(0);
    if (!exe) return false;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)exe;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    unsigned base = (unsigned)exe;
    return liveVa >= base && len <= nt->OptionalHeader.SizeOfImage && liveVa - base <= nt->OptionalHeader.SizeOfImage - len;
}

// Every pin must equal live memory, each relocated field taken back to its
// link-time value.
static bool PinsMatch() {
    for (size_t p = 0; p < sizeof(B200_PINS) / sizeof(B200_PINS[0]); ++p) {
        const B200Pin &pin = B200_PINS[p];
        unsigned live = A(pin.va);
        if (!InImage(live, pin.len)) {
            Log("pin %s at 0x%08X is outside the image", pin.name, live);
            return false;
        }
        unsigned char tmp[512];
        if (pin.len > sizeof tmp) return false;
        for (unsigned i = 0; i < pin.len; ++i) tmp[i] = ((const unsigned char *)live)[i];
        for (unsigned r = 0; r < pin.relocCount; ++r) {
            unsigned off = pin.relocs[r];
            unsigned v = (unsigned)tmp[off] | ((unsigned)tmp[off + 1] << 8) | ((unsigned)tmp[off + 2] << 16) |
                         ((unsigned)tmp[off + 3] << 24);
            v -= Delta;
            tmp[off] = (unsigned char)v; tmp[off + 1] = (unsigned char)(v >> 8);
            tmp[off + 2] = (unsigned char)(v >> 16); tmp[off + 3] = (unsigned char)(v >> 24);
        }
        for (unsigned i = 0; i < pin.len; ++i) {
            if (tmp[i] != pin.bytes[i]) {
                Log("pin %s at 0x%08X does not match the B200 bytes", pin.name, live);
                return false;
            }
        }
    }
    return true;
}

// ================================================================ module: time_controls
#include "b200time_time.inc"

// ================================================================ install
// 0 = setting off (nothing planned); -1 = a pin differs (nothing planned); 1 = planned.
static int BuildPlan(bool enabled, Plan &plan) {
    plan.count = 0;
    plan.ok = true;
    if (!enabled) return 0;
    if (!PinsMatch()) return -1;
    ResolveAbi();
    PlanTimeControls(plan);
    return plan.ok ? 1 : -1;
}

// The ONLY function that writes game code. The page is writable for this write
// alone and gets its original protection back before returning.
static bool WriteCode(unsigned va, const unsigned char *bytes, unsigned len, bool data) {
    DWORD old = 0;
    if (!VirtualProtect((void *)va, len, data ? PAGE_READWRITE : PAGE_EXECUTE_READWRITE, &old))
        return false;
    for (unsigned i = 0; i < len; ++i) ((volatile unsigned char *)va)[i] = bytes[i];
    DWORD ignored = 0;
    BOOL restored = VirtualProtect((void *)va, len, old, &ignored);
    FlushInstructionCache(GetCurrentProcess(), (void *)va, len);
    return restored != FALSE;
}

// All or nothing.
static bool Apply(Plan &plan) {
    for (unsigned i = 0; i < plan.count; ++i) {
        HookWrite &w = plan.writes[i];
        for (unsigned j = 0; j < w.len; ++j) w.original[j] = ((const unsigned char *)w.va)[j];
        if (!WriteCode(w.va, w.bytes, w.len, w.data)) {
            Log("write at 0x%08X failed (error %lu); restoring the earlier writes", w.va, GetLastError());
            for (unsigned j = 0; j < i; ++j)
                WriteCode(plan.writes[j].va, plan.writes[j].original, plan.writes[j].len, plan.writes[j].data);
            WriteCode(w.va, w.original, w.len, w.data);
            B200Time_Status.writeMask = 0;
            return false;
        }
        B200Time_Status.writeMask |= 1u << i;
    }
    return true;
}

static bool SettingOn() {
    wchar_t path[MAX_PATH];
    if (_snwprintf_s(path, MAX_PATH, _TRUNCATE, L"%svf2time.ini", Folder) < 0) return false;
    return GetPrivateProfileIntW(L"Patches", L"TimeControls", 0, path) == 1;
}

// Called once by the executable's loader, before the game loop starts.
extern "C" __declspec(dllexport) void __cdecl B200Time_Startup() {
    static bool started = false;
    if (started) return;
    started = true;

    DWORD n = GetModuleFileNameW(ThisModule, Folder, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    wchar_t *slash = wcsrchr(Folder, L'\\');
    if (!slash) return;
    slash[1] = 0;

    Delta = (unsigned)GetModuleHandleW(0) - B200TC_IMAGE_BASE;
    Log("vf2time_b200 started (module base delta 0x%08X)", Delta);
    bool on = SettingOn();
    B200Time_Status.requested = on ? 1u : 0u;
    static Plan plan;
    int built = BuildPlan(on, plan);
    if (built == 0) { Log("TimeControls is off: the game is stock"); return; }
    if (built < 0) { Log("pins differ or the plan failed: installing nothing"); return; }
    B200Time_Status.pinsOk = 1;
    if (Apply(plan)) {
        B200Time_Status.installed = 1;
        Log("Time Controls installed (%u writes)", plan.count);
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        ThisModule = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}

// ---------------------------------------------------------------- test builds only
#ifdef B200TIME_TEST
// Runs the install path's planning half against whatever executable image the
// harness has mapped at imageBase (the pins, the plan) without writing it.
// out: [status, count, then per write: va, len, data, bytes0..3, bytes4..7].
extern "C" __declspec(dllexport) int __cdecl B200Time_TestPlan(unsigned imageBase, int enabled, unsigned *out) {
    static Plan plan;
    Delta = imageBase - B200TC_IMAGE_BASE;
    int built = BuildPlan(enabled != 0, plan);
    out[0] = (unsigned)built;
    out[1] = built > 0 ? plan.count : 0;
    for (unsigned i = 0; built > 0 && i < plan.count; ++i) {
        out[2 + i * 5 + 0] = plan.writes[i].va;
        out[2 + i * 5 + 1] = plan.writes[i].len;
        out[2 + i * 5 + 2] = plan.writes[i].data ? 1u : 0u;
        out[2 + i * 5 + 3] = *(unsigned *)plan.writes[i].bytes;
        out[2 + i * 5 + 4] = *(unsigned *)(plan.writes[i].bytes + 4);
    }
    return built;
}
// The state machine without the dialog: op 1 pause, 2 resume, 3 speed(arg),
// 4 start a warp of arg ticks, 5 warp pending villager count, 6 speed field.
extern "C" __declspec(dllexport) int __cdecl B200Time_TestTime(int op, int arg) {
    switch (op) {
    case 1: PauseGame(); return 0;
    case 2: ResumeGame(); return 0;
    case 3: ChooseSpeed(arg); return 0;
    case 4: StartTimeWarp(arg); return 0;
    case 5: {
        WarpUnderWay();
        int n = 0;
        for (unsigned bits = WarpPending; bits; bits &= bits - 1) ++n;
        return n;
    }
    case 6: return SpeedField() ? *SpeedField() : -1;
    }
    return -1;
}
#endif
