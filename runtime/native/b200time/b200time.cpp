// vf2time_b200.dll -- the Time Controls companion DLL for the B200 Virtual
// Families 2 executable.
//
// It is the Settings-menu Time Controls module of the runtime-hook build
// (vf2fun_time.inc on the runtime branch), re-proved against B200 and made
// self-contained: B200 has no other runtime hooks, so this DLL has its own tiny
// host. One feature, one DLL: nothing else is installed here.
//
// The B200 executable is RELOCATED (DYNAMICBASE, with a .reloc section) and each
// of the 32 matrix variants links to different addresses, so this DLL holds NO
// game address. b200time_sites.h (generated and proved by
// runtime/tools/gen_b200_time_sites.py) holds pinned runs of the core variant
// with wildcards where a relocated field or a call displacement sits; Resolve()
// finds every run in the live image exactly once and derives each address from
// where the runs were found.
//
// The executable's loader calls B200Time_Startup() once, before the game loop.
// Installing is: setting -> resolve -> plan -> apply. With the TimeControls key
// off (or missing), or anything the resolver cannot prove, NOTHING is written
// and the game keeps B200's own bytes.
//
//   1. The Settings dialog constructor's last call (`call SetChecked` on the last
//      check box) is retargeted to a stub that makes the same call
//      and then adds one more button (id 9) at x = 30, built as the constructor
//      builds Evict: same art, y, font and colour.
//   2. theOptionsDialog's HandleMessage vtable slot 3 is replaced. A
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

// ---------------------------------------------------------------- the sites
// Live addresses derived by Resolve(), indexed by B200Site.
static unsigned Sites[B200_SITE_COUNT];
#define SITE(name) (Sites[B200_SITE_##name])

// ---------------------------------------------------------------- status block
// B200Time_Status: what this launch installed. Written only by the install path
// in B200Time_Startup. Layout version 2:
//   magic 'B2TC', version, requested (1 = setting on), resolved (1 = every pin
//   found and every derivation agreed), installed (1 = every write is live),
//   writeMask (bit w: write w live)
struct B200TimeStatus {
    unsigned magic;
    unsigned version;
    unsigned requested;
    unsigned resolved;
    unsigned installed;
    unsigned writeMask;
};
extern "C" __declspec(dllexport) volatile B200TimeStatus B200Time_Status = { 0x43543242u, 2u, 0, 0, 0, 0 };

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
    // Replace the 4-byte function pointer in the vtable slot at `va` with `to`.
    void Slot(unsigned va, const void *to) {
        HookWrite *w = Add(va, 4, true);
        if (!w) return;
        *(unsigned *)w->bytes = (unsigned)to;
    }
    // Retarget the 5-byte `call rel32` at `va` (proved to be an E8 by Resolve) to `to`.
    void Retarget(unsigned va, const void *to) {
        HookWrite *w = Add(va, 5, false);
        if (!w) return;
        w->bytes[0] = *(const unsigned char *)va;
        *(int *)(w->bytes + 1) = (int)((unsigned)to - (va + 5));
    }
};

// ================================================================ resolver
// The algorithm of gen_b200_time_sites.resolve(), over the live image.
struct ImageRange { unsigned base, size; };
static const unsigned kMaxRanges = 24;

static unsigned LiveSections(ImageRange *code, unsigned *codeCount, ImageRange *rodata, unsigned *rodataCount) {
    HMODULE exe = GetModuleHandleW(0);
    *codeCount = 0;
    *rodataCount = 0;
    if (!exe) return 0;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)exe;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    const IMAGE_SECTION_HEADER *s = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        unsigned size = s[i].Misc.VirtualSize ? s[i].Misc.VirtualSize : s[i].SizeOfRawData;
        ImageRange r = { (unsigned)exe + s[i].VirtualAddress, size };
        DWORD ch = s[i].Characteristics;
        if ((ch & IMAGE_SCN_MEM_EXECUTE) && *codeCount < kMaxRanges) code[(*codeCount)++] = r;
        else if ((ch & IMAGE_SCN_MEM_READ) && !(ch & IMAGE_SCN_MEM_WRITE) && *rodataCount < kMaxRanges)
            rodata[(*rodataCount)++] = r;
    }
    return (unsigned)exe;
}

// Find `pat` (mask 1 = wildcard) in [base, base+size). Counts matches up to 2 in *hits;
// returns the first match (0 if none).
#ifdef B200TIME_TEST
__declspec(noinline)
#endif
static unsigned ScanPattern(const unsigned char *base, unsigned size, const unsigned char *pat,
                            const unsigned char *mask, unsigned len, unsigned *hits) {
    unsigned first = 0, key = 0;
    while (key < len && mask[key]) ++key;       // the first byte that must match
    if (key == len || size < len) return 0;
    unsigned last = size - len;
    for (unsigned pos = 0; pos <= last; ++pos) {
        if (base[pos + key] != pat[key]) continue;
        unsigned i = 0;
        while (i < len && (mask[i] || base[pos + i] == pat[i])) ++i;
        if (i == len) {
            if (!*hits) first = (unsigned)base + pos;
            if (++*hits >= 2) return first;
        }
    }
    return first;
}

static bool ReadOnlyPointerTo(const ImageRange *rodata, unsigned count, unsigned target, unsigned *slot) {
    unsigned found = 0, at = 0;
    for (unsigned r = 0; r < count; ++r) {
        for (unsigned off = 0; off + 4 <= rodata[r].size; off += 4) {
            if (*(const unsigned *)(rodata[r].base + off) == target) {
                ++found;
                at = rodata[r].base + off;
            }
        }
    }
    *slot = at;
    return found == 1;
}

// Resolve every pin and site in the live executable. False (and a log line) on the first thing
// that is not exactly as the core variant has it.
static bool Resolve() {
    static ImageRange code[kMaxRanges], rodata[kMaxRanges];
    unsigned codeCount = 0, rodataCount = 0;
    if (!LiveSections(code, &codeCount, rodata, &rodataCount) || !codeCount) return false;
    const unsigned pinCount = sizeof(B200_PINS) / sizeof(B200_PINS[0]);
    static unsigned loc[sizeof(B200_PINS) / sizeof(B200_PINS[0])];
    for (unsigned i = 0; i < pinCount; ++i) {
        const B200Pin &pin = B200_PINS[i];
        if (pin.parent >= 0) continue;
        unsigned hits = 0, at = 0;
        for (unsigned r = 0; r < codeCount && hits < 2; ++r) {
            unsigned h = 0;
            unsigned found = ScanPattern((const unsigned char *)code[r].base, code[r].size, pin.bytes, pin.mask,
                                         pin.len, &h);
            if (h) { if (!hits) at = found; hits += h; }
        }
        if (hits != 1) {
            Log("pin %s found %u times", pin.name, hits);
            return false;
        }
        loc[i] = at;
    }
    for (unsigned i = 0; i < pinCount; ++i) {
        const B200Pin &pin = B200_PINS[i];
        if (pin.parent < 0) continue;
        loc[i] = loc[pin.parent] + (unsigned)pin.offset;
        const unsigned char *live = (const unsigned char *)loc[i];
        bool inside = false;
        for (unsigned r = 0; r < codeCount; ++r)
            if (loc[i] >= code[r].base && loc[i] + pin.len <= code[r].base + code[r].size) inside = true;
        if (!inside) { Log("pin %s lies outside the code", pin.name); return false; }
        for (unsigned k = 0; k < pin.len; ++k) {
            if (!pin.mask[k] && live[k] != pin.bytes[k]) {
                Log("pin %s differs at its anchor offset", pin.name);
                return false;
            }
        }
    }
    bool have[B200_SITE_COUNT];
    for (unsigned i = 0; i < B200_SITE_COUNT; ++i) have[i] = false;
    for (unsigned e = 0; e < sizeof(B200_EVIDENCE) / sizeof(B200_EVIDENCE[0]); ++e) {
        const B200Evidence &ev = B200_EVIDENCE[e];
        unsigned at = loc[ev.pin] + ev.offset, v;
        if (ev.kind == 'L') v = at;
        else if (ev.kind == 'A') v = *(const unsigned *)at;
        else v = at + 4 + *(const unsigned *)at;
        if (have[ev.site] && Sites[ev.site] != v) { Log("site %u: derivations disagree", ev.site); return false; }
        Sites[ev.site] = v;
        have[ev.site] = true;
    }
    for (unsigned c = 0; c < sizeof(B200_CALLS) / sizeof(B200_CALLS[0]); ++c) {
        const unsigned char *site = (const unsigned char *)Sites[B200_CALLS[c].site];
        unsigned target = Sites[B200_CALLS[c].site] + 5 + *(const unsigned *)(site + 1);
        if (site[0] != 0xE8 || target != Sites[B200_CALLS[c].function]) { Log("a patched call site is not as expected"); return false; }
        have[B200_CALLS[c].site] = true;
    }
    for (unsigned s = 0; s < sizeof(B200_SLOTS) / sizeof(B200_SLOTS[0]); ++s) {
        unsigned slot = 0;
        if (!ReadOnlyPointerTo(rodata, rodataCount, Sites[B200_SLOTS[s].function], &slot)) {
            Log("a vtable slot is not the single pointer to its function");
            return false;
        }
        Sites[B200_SLOTS[s].site] = slot;
        have[B200_SLOTS[s].site] = true;
    }
    if (Sites[B200_SITE_GAME_STATE_SLOT_SAVE] != Sites[B200_SITE_GAME_STATE_SLOT_LOAD] + 4) {
        Log("theGameState Save does not follow Load");
        return false;
    }
    for (unsigned i = 0; i < B200_SITE_COUNT; ++i) if (!have[i]) { Log("site %u is underived", i); return false; }
    return true;
}

// ================================================================ module: time_controls
#include "b200time_time.inc"

// ================================================================ install
// 0 = setting off (nothing planned); -1 = could not be proved (nothing planned); 1 = planned.
static int BuildPlan(bool enabled, Plan &plan) {
    plan.count = 0;
    plan.ok = true;
    if (!enabled) return 0;
    if (!Resolve()) return -1;
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

    Log("vf2time_b200 started");
    bool on = SettingOn();
    B200Time_Status.requested = on ? 1u : 0u;
    static Plan plan;
    int built = BuildPlan(on, plan);
    if (built == 0) { Log("TimeControls is off: the game is stock"); return; }
    if (built < 0) { Log("the executable could not be proved or the plan failed: installing nothing"); return; }
    B200Time_Status.resolved = 1;
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
// The address of ScanPattern, so the emulator harness can replace the scan (a million-byte loop
// per pin) with a native one while every other line of the resolver still runs.
extern "C" __declspec(dllexport) unsigned __cdecl B200Time_TestScanAddress() {
    return (unsigned)&ScanPattern;
}
// Runs the install path's planning half against the image the harness has mapped, without writing it.
// out: [status, count, then per write: va, len, data, bytes0..3, bytes4..7].
extern "C" __declspec(dllexport) int __cdecl B200Time_TestPlan(int enabled, unsigned *out) {
    static Plan plan;
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
// The resolved sites (live addresses), B200_SITE_COUNT of them, after a TestPlan with the setting on.
extern "C" __declspec(dllexport) void __cdecl B200Time_TestSites(unsigned *out) {
    for (unsigned i = 0; i < B200_SITE_COUNT; ++i) out[i] = Sites[i];
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
