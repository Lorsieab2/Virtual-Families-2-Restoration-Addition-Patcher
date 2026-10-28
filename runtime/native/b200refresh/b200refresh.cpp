// vf2refresh_b200.dll -- "R Refreshes the Store", the companion DLL for the B200 Virtual Families 2
// executable. One feature, one DLL: nothing else is installed here.
//
// In the store, on the Clothing and Hairstyles page, pressing R (or Shift+R) picks the six stock outfit rows
// again (Discount, Department and Designer, male and female) with the game's own forced draw,
// CInventoryManager::MaybeUpdateOutfits(true): the call CInventoryManager::Reset makes for a new family. The
// game's own GenCommonBodyType / GenUncommonBodyType / GenRareBodyType pick the outfits, so the odds are the
// game's, and the next timed pick is set to 4 game hours later, exactly as after a timed pick. Nothing else is
// written: an outfit already bought keeps the picture it was bought with (the store's pick is copied when it
// is bought), the save file gets only what the game itself saves for its own pick, and the press touches no
// other page (On Sale is never touched by R anywhere). Hairstyles are not drawn at random, so R leaves them alone.
//
// The Flea Market page depends on the patcher's "All 36 Flea Market goods" setting (the executable's .vf2flea
// byte, read at each press):
//   on (byte 1, the default): the store lists all 36 goods there at all times, unlimited, so there is nothing
//     to refresh, and the game's own Flea Market draw must not run: it also sets every pooled good's stock
//     count to 1 and would make 33 unlimited goods sell out for good. R does nothing there (the game's own
//     key handler gets the key). An executable without the byte (built before the setting) is the same.
//   off (byte 0): the Flea Market is the stock one, 5 goods re-picked 6 real hours after the last pick. R
//     makes that pick happen now: the next-pick time is set to 0 (due) and the store's own SetStoreCategory
//     lists the page again, whose GetCategoryItemCount runs the game's own MaybeUpdateRotatingItems (its
//     shuffle, its stock counts, its next pick 6 real hours later). If the game clock is still 0, so no pick
//     can be due, the old next-pick time is put back and nothing is changed.
//
// How: CScrollingStoreScene's HandleKey vtable slot (slot 2, the slot ldwEventManager::HandleKey calls) is
// replaced by RefreshHandleKey. The function in that slot is the identical-code-folded HandleKey five
// scenes share, so the DLL never touches the function; it finds the STORE's vtable through its RTTI and
// replaces that one pointer. A typed character arrives as HandleKey(5, char, 0); R on the Clothing page
// ([scene+0D4h], written by SetStoreCategory, is 0Dh) is handled here; every other key, page and type goes
// to the game's own HandleKey unchanged. While a box is open no key reaches the store (each store box is
// modal), and the store screen has no text box, so R never fires while typing.
//
// The B200 executable is RELOCATED (DYNAMICBASE) and each of the 32 matrix variants links to different
// addresses, so this DLL holds NO game address. b200refresh_sites.h (generated and proved by
// runtime/tools/gen_b200_refresh_sites.py) holds runs of the core variant with wildcards where a relocated
// field or a call displacement sits; Resolve() finds every run in the live image exactly once and derives
// each address from where the runs were found.
//
// The executable's loader (theGame::Init's first call) loads this DLL once, after the other companion DLLs,
// only while the R Refreshes the Store byte (.vf2rfsh) is 1, and calls B200Refresh_Startup(). Installing is:
// setting -> resolve -> plan -> apply. With RefreshKey off (or missing) in vf2refresh.ini, or anything the
// resolver cannot prove, NOTHING is written and the game keeps B200's own bytes.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include "b200refresh_sites.h"

// ---------------------------------------------------------------- the sites
static unsigned Sites[RFSH_SITE_COUNT];
#define SITE(name) (Sites[RFSH_SITE_##name])
static unsigned StoreSlot;              // the store vtable's HandleKey slot (found through RTTI)
static volatile unsigned char *FleaFlag;  // the executable's .vf2flea byte (0 when it has none)

// ---------------------------------------------------------------- status block
// B200Refresh_Status: what this launch installed, and what R has done. Layout version 1:
//   magic 'RFFH', version, requested (1 = setting on), resolved (1 = every pin found and every derivation
//   agreed), installed (1 = the slot write is live), writeMask (bit w: write w live), redraws (R presses that
//   redrew the outfits), passed (R presses given to the game's own handler: another page, or the Flea Market
//   with all 36 goods listed), fleaRedraws (R presses that picked the stock Flea Market again), fleaFlag (1 =
//   the executable has the .vf2flea byte)
struct RefreshStatus {
    unsigned magic;
    unsigned version;
    unsigned requested;
    unsigned resolved;
    unsigned installed;
    unsigned writeMask;
    unsigned redraws;
    unsigned passed;
    unsigned fleaRedraws;
    unsigned fleaFlag;
};
extern "C" __declspec(dllexport) volatile RefreshStatus B200Refresh_Status = {
    RFSH_STATUS_MAGIC, 1u, 0, 0, 0, 0, 0, 0, 0, 0 };

static HMODULE ThisModule;
static wchar_t Folder[MAX_PATH];

// path = Folder + name (no C runtime: this runs under the emulator in the tests). False if it does not fit.
static bool InFolder(const wchar_t *name, wchar_t *path) {
    unsigned n = 0;
    while (Folder[n]) { if (n + 1 >= MAX_PATH) return false; path[n] = Folder[n]; ++n; }
    for (unsigned i = 0; name[i]; ++i) { if (n + 1 >= MAX_PATH) return false; path[n++] = name[i]; }
    path[n] = 0;
    return true;
}

// ---------------------------------------------------------------- log
// vf2refresh.log beside the DLL: one short record of what this launch installed.
#ifdef B200REFRESH_TEST
static void Log(const char *) {}
#else
static bool LogStarted;
static void Log(const char *line) {
    wchar_t path[MAX_PATH];
    if (!InFolder(L"vf2refresh.log", path)) return;
    HANDLE f = CreateFileW(path, LogStarted ? FILE_APPEND_DATA : GENERIC_WRITE, FILE_SHARE_READ, 0,
                           LogStarted ? OPEN_ALWAYS : CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (f == INVALID_HANDLE_VALUE) return;
    LogStarted = true;
    unsigned n = 0;
    while (line[n]) ++n;
    DWORD wrote = 0;
    WriteFile(f, line, n, &wrote, 0);
    WriteFile(f, "\r\n", 2, &wrote, 0);
    CloseHandle(f);
}
#endif

// ================================================================ plan
static const unsigned kMaxWrites = 2;

struct HookWrite {
    unsigned va;
    unsigned len;
    bool data;             // a 4-byte vtable slot (never made executable)
    unsigned char bytes[8];
    unsigned char original[8];
};

struct Plan {
    HookWrite writes[kMaxWrites];
    unsigned count;
    bool ok;

    void Slot(unsigned va, const void *to) {
        if (!ok || count >= kMaxWrites) { ok = false; return; }
        HookWrite &w = writes[count++];
        w.va = va;
        w.len = 4;
        w.data = true;
        for (unsigned i = 0; i < 8; ++i) { w.bytes[i] = 0; w.original[i] = 0; }
        *(unsigned *)w.bytes = (unsigned)to;
    }
};

// ================================================================ resolver
// The algorithm of gen_b200_refresh_sites.resolve(), over the live image.
struct ImageRange { unsigned base, size; };
static const unsigned kMaxRanges = 24;

// code: executable sections; data: readable non-executable sections; rodata: read-only data.
static bool LiveSections(ImageRange *code, unsigned *codeCount, ImageRange *data, unsigned *dataCount,
                         ImageRange *rodata, unsigned *rodataCount) {
    HMODULE exe = GetModuleHandleW(0);
    *codeCount = *dataCount = *rodataCount = 0;
    if (!exe) return false;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)exe;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    const IMAGE_SECTION_HEADER *s = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        unsigned size = s[i].Misc.VirtualSize ? s[i].Misc.VirtualSize : s[i].SizeOfRawData;
        if (s[i].SizeOfRawData < size) size = s[i].SizeOfRawData;     // only bytes the file backs
        ImageRange r = { (unsigned)exe + s[i].VirtualAddress, size };
        DWORD ch = s[i].Characteristics;
        if (ch & IMAGE_SCN_MEM_EXECUTE) {
            if (*codeCount < kMaxRanges) code[(*codeCount)++] = r;
        } else if (ch & IMAGE_SCN_MEM_READ) {
            if (*dataCount < kMaxRanges) data[(*dataCount)++] = r;
            if (!(ch & IMAGE_SCN_MEM_WRITE) && *rodataCount < kMaxRanges) rodata[(*rodataCount)++] = r;
        }
    }
    return *codeCount != 0;
}

// Find `pat` (mask 1 = wildcard) in [base, base+size). Counts matches up to 2 in *hits; returns the first.
#ifdef B200REFRESH_TEST
__declspec(noinline)
#endif
static unsigned ScanPattern(const unsigned char *base, unsigned size, const unsigned char *pat,
                            const unsigned char *mask, unsigned len, unsigned *hits) {
    unsigned first = 0, key = 0;
    while (key < len && mask[key]) ++key;
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

// The next 4-aligned (from `from`) dword equal to `value` in [from, end), or 0.
#ifdef B200REFRESH_TEST
__declspec(noinline)
#endif
static unsigned NextDword(unsigned from, unsigned end, unsigned value) {
    for (unsigned at = from; at + 4 <= end; at += 4)
        if (*(const unsigned *)at == value) return at;
    return 0;
}

// The store's vtable through its RTTI: the one type descriptor named .?AVCScrollingStoreScene@@ (its name is
// at TD + 8), the one complete object locator at offset 0 (signature 0, offset 0, TD at +0Ch) pointing to it,
// and the one vtable whose slot -1 points to that locator. 0 if any of them is not exactly one.
static unsigned StoreVtable(const ImageRange *data, unsigned dataCount, const ImageRange *rodata,
                            unsigned rodataCount) {
    static const char name[] = RFSH_STORE_TYPE_NAME;
    const unsigned len = sizeof(name);                // with its terminating zero
    static unsigned char zeros[sizeof(name)];
    unsigned hits = 0, at = 0;
    for (unsigned r = 0; r < dataCount && hits < 2; ++r) {
        unsigned h = 0;
        unsigned found = ScanPattern((const unsigned char *)data[r].base, data[r].size,
                                     (const unsigned char *)name, zeros, len, &h);
        if (h) { if (!hits) at = found; hits += h; }
    }
    if (hits != 1 || at < 8) { Log("the store's type descriptor is not found exactly once"); return 0; }
    unsigned td = at - 8;
    unsigned cols = 0, col = 0;
    for (unsigned r = 0; r < rodataCount; ++r) {
        unsigned end = rodata[r].base + rodata[r].size;
        for (unsigned p = NextDword(rodata[r].base + 12, end, td); p; p = NextDword(p + 4, end, td)) {
            unsigned c = p - 12;
            if (((const unsigned *)c)[0] == 0 && ((const unsigned *)c)[1] == 0) { ++cols; col = c; }
        }
    }
    if (cols != 1) { Log("the store's complete object locator is not found exactly once"); return 0; }
    unsigned vts = 0, vt = 0;
    for (unsigned r = 0; r < rodataCount; ++r) {
        unsigned end = rodata[r].base + rodata[r].size;
        for (unsigned p = NextDword(rodata[r].base, end, col); p; p = NextDword(p + 4, end, col)) {
            ++vts;
            vt = p + 4;
        }
    }
    if (vts != 1) { Log("the store's vtable is not found exactly once"); return 0; }
    return vt;
}

// The executable's one writable .vf2flea section (the "All 36 Flea Market goods" byte), or 0.
static volatile unsigned char *FindFleaFlag() {
    HMODULE exe = GetModuleHandleW(0);
    if (!exe) return 0;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)exe;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    const IMAGE_SECTION_HEADER *s = IMAGE_FIRST_SECTION(nt);
    static const char name[] = RFSH_FLEA_FLAG_SECTION;
    volatile unsigned char *found = 0;
    unsigned count = 0;
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        unsigned k = 0;
        while (k < 8 && s[i].Name[k] == (k < sizeof(name) - 1 ? (BYTE)name[k] : 0)) ++k;
        if (k == 8 && s[i].SizeOfRawData && (s[i].Characteristics & IMAGE_SCN_MEM_WRITE)) {
            found = (volatile unsigned char *)((unsigned)exe + s[i].VirtualAddress);
            ++count;
        }
    }
    return count == 1 ? found : 0;
}

// Resolve every pin and site in the live executable. False (and a log line) on the first thing that is not
// exactly as the core variant has it.
static bool Resolve() {
    static ImageRange code[kMaxRanges], data[kMaxRanges], rodata[kMaxRanges];
    unsigned codeCount = 0, dataCount = 0, rodataCount = 0;
    if (!LiveSections(code, &codeCount, data, &dataCount, rodata, &rodataCount)) return false;
    const unsigned pinCount = sizeof(RFSH_PINS) / sizeof(RFSH_PINS[0]);
    static unsigned loc[sizeof(RFSH_PINS) / sizeof(RFSH_PINS[0])];
    for (unsigned i = 0; i < pinCount; ++i) {
        const RfshPin &pin = RFSH_PINS[i];
        if (pin.parent >= 0) continue;
        unsigned hits = 0, at = 0;
        for (unsigned r = 0; r < codeCount && hits < 2; ++r) {
            unsigned h = 0;
            unsigned found = ScanPattern((const unsigned char *)code[r].base, code[r].size, pin.bytes, pin.mask,
                                         pin.len, &h);
            if (h) { if (!hits) at = found; hits += h; }
        }
        if (hits != 1) { Log("a pin is not found exactly once"); return false; }
        loc[i] = at;
    }
    for (unsigned i = 0; i < pinCount; ++i) {
        const RfshPin &pin = RFSH_PINS[i];
        if (pin.parent < 0) continue;
        loc[i] = loc[pin.parent] + (unsigned)pin.offset;
        bool inside = false;
        for (unsigned r = 0; r < codeCount; ++r)
            if (loc[i] >= code[r].base && loc[i] + pin.len <= code[r].base + code[r].size) inside = true;
        if (!inside) { Log("an anchored pin lies outside the code"); return false; }
        const unsigned char *live = (const unsigned char *)loc[i];
        for (unsigned k = 0; k < pin.len; ++k)
            if (!pin.mask[k] && live[k] != pin.bytes[k]) { Log("an anchored pin differs"); return false; }
    }
    bool have[RFSH_SITE_COUNT];
    for (unsigned i = 0; i < RFSH_SITE_COUNT; ++i) have[i] = false;
    for (unsigned e = 0; e < sizeof(RFSH_EVIDENCE) / sizeof(RFSH_EVIDENCE[0]); ++e) {
        const RfshEvidence &ev = RFSH_EVIDENCE[e];
        unsigned at = loc[ev.pin] + ev.offset, v;
        if (ev.kind == 'L') v = at;
        else if (ev.kind == 'A') v = *(const unsigned *)at;
        else v = at + 4 + *(const unsigned *)at;
        if (have[ev.site] && Sites[ev.site] != v) { Log("two derivations of a site disagree"); return false; }
        Sites[ev.site] = v;
        have[ev.site] = true;
    }
    for (unsigned i = 0; i < RFSH_SITE_COUNT; ++i) if (!have[i]) { Log("a site is underived"); return false; }
    unsigned vt = StoreVtable(data, dataCount, rodata, rodataCount);
    if (!vt) return false;
    StoreSlot = vt + 4 * RFSH_HANDLE_KEY_VSLOT;
    bool slotInside = false;
    for (unsigned r = 0; r < rodataCount; ++r)
        if (StoreSlot >= rodata[r].base && StoreSlot + 4 <= rodata[r].base + rodata[r].size) slotInside = true;
    if (!slotInside || *(const unsigned *)StoreSlot != SITE(STORE_HANDLE_KEY)) {
        Log("the store's HandleKey slot does not point to the pinned HandleKey");
        return false;
    }
    FleaFlag = FindFleaFlag();
    B200Refresh_Status.fleaFlag = FleaFlag ? 1u : 0u;
    return true;
}

// ================================================================ module: the R key
typedef bool (__thiscall *HandleKeyFn)(void *scene, int type, int code, int sym);
typedef void (__thiscall *MaybeUpdateOutfitsFn)(void *inventory, bool force);
typedef void (__thiscall *SetStoreCategoryFn)(void *scene, int category);

// The stock Flea Market's pick, now: only while the "All 36 Flea Market goods" byte exists and is 0.
static bool RedrawStockFleaMarket(void *scene) {
    if (!FleaFlag || *FleaFlag != 0) return false;
    volatile unsigned *next = (volatile unsigned *)(SITE(INVENTORY_MANAGER) + RFSH_FLEA_NEXT_PICK_FIELD);
    unsigned saved = *next;
    *next = 0;
    ((SetStoreCategoryFn)SITE(SET_STORE_CATEGORY))(scene, (int)RFSH_FLEA_MARKET_CATEGORY);
    if (*next == 0) *next = saved;          // the clock was 0: no pick could be due, so nothing changed
    return true;
}

// The store's HandleKey (thiscall, ret 0Ch: __fastcall with edx unused has the same frame).
static bool __fastcall RefreshHandleKey(void *scene, void *, int type, int code, int sym) {
    if (type == (int)RFSH_KEY_TYPE_CHARACTER && (code == (int)RFSH_KEY_R_LOWER || code == (int)RFSH_KEY_R_UPPER)) {
        int category = *(const int *)((const unsigned char *)scene + RFSH_STORE_CATEGORY_FIELD);
        if (category == (int)RFSH_CLOTHING_CATEGORY) {
            ((MaybeUpdateOutfitsFn)SITE(MAYBE_UPDATE_OUTFITS))((void *)SITE(INVENTORY_MANAGER), true);
            ++B200Refresh_Status.redraws;
            return true;
        }
        if (category == (int)RFSH_FLEA_MARKET_CATEGORY && RedrawStockFleaMarket(scene)) {
            ++B200Refresh_Status.fleaRedraws;
            return true;
        }
        ++B200Refresh_Status.passed;
    }
    return ((HandleKeyFn)SITE(STORE_HANDLE_KEY))(scene, type, code, sym);
}

static void PlanRefresh(Plan &plan) {
    plan.Slot(StoreSlot, (const void *)&RefreshHandleKey);
}

// ================================================================ install
// 0 = setting off (nothing planned); -1 = could not be proved (nothing planned); 1 = planned.
static int BuildPlan(bool enabled, Plan &plan) {
    plan.count = 0;
    plan.ok = true;
    if (!enabled) return 0;
    if (!Resolve()) return -1;
    PlanRefresh(plan);
    return plan.ok ? 1 : -1;
}

// The ONLY function that writes the executable's memory. The page is writable for this write alone and gets
// its original protection back before returning.
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
            Log("a write failed; restoring the earlier writes");
            for (unsigned j = 0; j < i; ++j)
                WriteCode(plan.writes[j].va, plan.writes[j].original, plan.writes[j].len, plan.writes[j].data);
            WriteCode(w.va, w.original, w.len, w.data);
            B200Refresh_Status.writeMask = 0;
            return false;
        }
        B200Refresh_Status.writeMask |= 1u << i;
    }
    return true;
}

static bool SettingOn() {
    wchar_t path[MAX_PATH];
    if (!InFolder(L"vf2refresh.ini", path)) return false;
    return GetPrivateProfileIntW(L"Patches", L"RefreshKey", 0, path) == 1;
}

// Called once by the executable's loader, before the game loop starts.
extern "C" __declspec(dllexport) void __cdecl B200Refresh_Startup() {
    static bool started = false;
    if (started) return;
    started = true;

    DWORD n = GetModuleFileNameW(ThisModule, Folder, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    unsigned cut = n;
    while (cut > 0 && Folder[cut - 1] != L'\\') --cut;
    if (!cut) return;
    Folder[cut] = 0;

    Log("vf2refresh_b200 started");
    bool on = SettingOn();
    B200Refresh_Status.requested = on ? 1u : 0u;
    static Plan plan;
    int built = BuildPlan(on, plan);
    if (built == 0) { Log("RefreshKey is off: the game is stock"); return; }
    if (built < 0) { Log("the executable could not be proved: installing nothing"); return; }
    B200Refresh_Status.resolved = 1;
    if (Apply(plan)) {
        B200Refresh_Status.installed = 1;
        Log("R Refreshes the Store installed (1 write)");
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
#ifdef B200REFRESH_TEST
// The addresses of ScanPattern and NextDword, so the emulator harness can replace the scans (a million-byte
// loop per pin) with native ones while every other line of the resolver still runs.
extern "C" __declspec(dllexport) unsigned __cdecl B200Refresh_TestScanAddress() {
    return (unsigned)&ScanPattern;
}
extern "C" __declspec(dllexport) unsigned __cdecl B200Refresh_TestNextDwordAddress() {
    return (unsigned)&NextDword;
}
// The planning half of the install path against the mapped image, without writing it.
// out: [status, count, then per write: va, len, data, bytes0..3, bytes4..7].
extern "C" __declspec(dllexport) int __cdecl B200Refresh_TestPlan(int enabled, unsigned *out) {
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
// DllMain does not run under the emulator: tell the DLL which module it is.
extern "C" __declspec(dllexport) void __cdecl B200Refresh_TestSetModule(unsigned module) {
    ThisModule = (HMODULE)module;
}
// The resolved sites (live addresses), RFSH_SITE_COUNT of them, then the store's HandleKey slot.
extern "C" __declspec(dllexport) void __cdecl B200Refresh_TestSites(unsigned *out) {
    for (unsigned i = 0; i < RFSH_SITE_COUNT; ++i) out[i] = Sites[i];
    out[RFSH_SITE_COUNT] = StoreSlot;
}
#endif
