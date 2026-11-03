// vf2titlebox_b200.dll -- "Title Screen Player Name Box", the companion DLL for the B200 Virtual Families 2
// executable. One feature, one DLL: nothing else is installed here.
//
// On the title screen (Play / Start Over / Manage Games / Quit) the current player's name is drawn on a white box
// at 20% opacity, so it reads on any background. The box is drawn every frame the name is drawn, before it, with
// the game's own ldwGameWindow::FillRect(rect, colour) in white at alpha 33h (51/255 = 20%), whose own blend makes
// every colour byte (old * 204 >> 8) + 50.
//
// The box is the name's own rectangle plus TBOX_BOX_PADDING (8) pixels on every side, the margin the game's hint
// (tooltip) box keeps around its text. The rectangle is worked out exactly as ldwTextControlImpl::Draw places the
// text: the scene's bounds, the control's justification, inset and offset, the font (the control's, else the
// window's), the width from the game's own ldwFont::GetWidth(text, scale) and the height from
// ldwFont::GetHeight(0) times the scale -- the very calls Draw makes, through the same function entries. A Unicode
// text DLL ("Render Unicode with In-Game Fonts" / "Use Unicode Font") that hooks GetWidth therefore sizes the box
// exactly as it sizes the text, for a long name or any script; with neither it is the stock width.
//
// How: theMenuScene's DrawScene vtable slot (slot 6, the first thing ldwScene::Draw calls each frame, before
// DrawControls draws every control, the name among them) is replaced by TitleDrawScene. It calls the game's own
// DrawScene (the background and logo) and then fills the box, only while the name control ([scene+0F0h]) is in
// the scene's control list and its Draw would draw text. The DLL finds theMenuScene's vtable through its RTTI and
// replaces that one pointer; it never touches a function.
//
// The B200 executable is RELOCATED (DYNAMICBASE) and each of the 32 matrix variants links to different addresses,
// so this DLL holds NO game address. b200titlebox_sites.h (generated and proved by
// runtime/tools/gen_b200_titlebox_sites.py) holds runs of the core variant with wildcards where a relocated field
// or a call displacement sits; Resolve() finds every run in the live image exactly once and derives each address
// from where the runs were found. The text box's Draw is searched from its eighth byte, after the 7 bytes the
// Unicode text DLL may replace.
//
// The executable's loader (theGame::Init's first call) loads this DLL once, before the Unicode text DLLs, only
// while the Title Screen Player Name Box byte (.vf2tbox) is 1, and calls B200TitleBox_Startup(). Installing is:
// setting -> resolve -> plan -> apply. With NameBox off (or missing) in vf2titlebox.ini, or anything the resolver
// cannot prove, NOTHING is written and the game keeps B200's own bytes.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include "b200titlebox_sites.h"

// ---------------------------------------------------------------- the sites
static unsigned Sites[TBOX_SITE_COUNT];
#define SITE(name) (Sites[TBOX_SITE_##name])
static unsigned MenuSlot;               // theMenuScene's DrawScene slot (found through RTTI)

// ---------------------------------------------------------------- status block
// B200TitleBox_Status: what this launch installed, and what the box has done. Layout version 1:
//   magic 'TTBX', version, requested (1 = setting on), resolved (1 = every pin found and every derivation agreed),
//   installed (1 = the slot write is live), writeMask (bit w: write w live), frames (DrawScene calls through the
//   DLL), boxes (frames that drew the box), lastLeft, lastTop, lastRight, lastBottom (the last box drawn)
struct TitleBoxStatus {
    unsigned magic;
    unsigned version;
    unsigned requested;
    unsigned resolved;
    unsigned installed;
    unsigned writeMask;
    unsigned frames;
    unsigned boxes;
    int lastLeft;
    int lastTop;
    int lastRight;
    int lastBottom;
};
extern "C" __declspec(dllexport) volatile TitleBoxStatus B200TitleBox_Status = {
    TBOX_STATUS_MAGIC, 1u, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };

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
// vf2titlebox.log beside the DLL: one short record of what this launch installed.
#ifdef B200TITLEBOX_TEST
static void Log(const char *) {}
#else
static bool LogStarted;
static void Log(const char *line) {
    wchar_t path[MAX_PATH];
    if (!InFolder(L"vf2titlebox.log", path)) return;
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
// The algorithm of gen_b200_titlebox_sites.resolve(), over the live image.
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
#ifdef B200TITLEBOX_TEST
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
#ifdef B200TITLEBOX_TEST
__declspec(noinline)
#endif
static unsigned NextDword(unsigned from, unsigned end, unsigned value) {
    for (unsigned at = from; at + 4 <= end; at += 4)
        if (*(const unsigned *)at == value) return at;
    return 0;
}

// theMenuScene's vtable through its RTTI: the one type descriptor named .?AVtheMenuScene@@ (its name is at TD + 8),
// the one complete object locator at offset 0 (signature 0, offset 0, TD at +0Ch) pointing to it, and the one
// vtable whose slot -1 points to that locator. 0 if any of them is not exactly one.
static unsigned MenuVtable(const ImageRange *data, unsigned dataCount, const ImageRange *rodata,
                           unsigned rodataCount) {
    static const char name[] = TBOX_MENU_TYPE_NAME;
    const unsigned len = sizeof(name);                // with its terminating zero
    static unsigned char zeros[sizeof(name)];
    unsigned hits = 0, at = 0;
    for (unsigned r = 0; r < dataCount && hits < 2; ++r) {
        unsigned h = 0;
        unsigned found = ScanPattern((const unsigned char *)data[r].base, data[r].size,
                                     (const unsigned char *)name, zeros, len, &h);
        if (h) { if (!hits) at = found; hits += h; }
    }
    if (hits != 1 || at < 8) { Log("theMenuScene's type descriptor is not found exactly once"); return 0; }
    unsigned td = at - 8;
    unsigned cols = 0, col = 0;
    for (unsigned r = 0; r < rodataCount; ++r) {
        unsigned end = rodata[r].base + rodata[r].size;
        for (unsigned p = NextDword(rodata[r].base + 12, end, td); p; p = NextDword(p + 4, end, td)) {
            unsigned c = p - 12;
            if (((const unsigned *)c)[0] == 0 && ((const unsigned *)c)[1] == 0) { ++cols; col = c; }
        }
    }
    if (cols != 1) { Log("theMenuScene's complete object locator is not found exactly once"); return 0; }
    unsigned vts = 0, vt = 0;
    for (unsigned r = 0; r < rodataCount; ++r) {
        unsigned end = rodata[r].base + rodata[r].size;
        for (unsigned p = NextDword(rodata[r].base, end, col); p; p = NextDword(p + 4, end, col)) {
            ++vts;
            vt = p + 4;
        }
    }
    if (vts != 1) { Log("theMenuScene's vtable is not found exactly once"); return 0; }
    return vt;
}

// Resolve every pin and site in the live executable. False (and a log line) on the first thing that is not
// exactly as the core variant has it.
static bool Resolve() {
    static ImageRange code[kMaxRanges], data[kMaxRanges], rodata[kMaxRanges];
    unsigned codeCount = 0, dataCount = 0, rodataCount = 0;
    if (!LiveSections(code, &codeCount, data, &dataCount, rodata, &rodataCount)) return false;
    const unsigned pinCount = sizeof(TBOX_PINS) / sizeof(TBOX_PINS[0]);
    static unsigned loc[sizeof(TBOX_PINS) / sizeof(TBOX_PINS[0])];
    for (unsigned i = 0; i < pinCount; ++i) {
        const TboxPin &pin = TBOX_PINS[i];
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
        const TboxPin &pin = TBOX_PINS[i];
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
    bool have[TBOX_SITE_COUNT];
    for (unsigned i = 0; i < TBOX_SITE_COUNT; ++i) have[i] = false;
    for (unsigned e = 0; e < sizeof(TBOX_EVIDENCE) / sizeof(TBOX_EVIDENCE[0]); ++e) {
        const TboxEvidence &ev = TBOX_EVIDENCE[e];
        unsigned at = loc[ev.pin] + ev.offset, v;
        if (ev.kind == 'L') v = at;
        else if (ev.kind == 'A') v = *(const unsigned *)at;
        else v = at + 4 + *(const unsigned *)at;
        if (have[ev.site] && Sites[ev.site] != v) { Log("two derivations of a site disagree"); return false; }
        Sites[ev.site] = v;
        have[ev.site] = true;
    }
    for (unsigned i = 0; i < TBOX_SITE_COUNT; ++i) if (!have[i]) { Log("a site is underived"); return false; }
    unsigned vt = MenuVtable(data, dataCount, rodata, rodataCount);
    if (!vt) return false;
    MenuSlot = vt + 4 * TBOX_DRAW_SCENE_VSLOT;
    bool slotInside = false;
    for (unsigned r = 0; r < rodataCount; ++r)
        if (MenuSlot >= rodata[r].base && MenuSlot + 4 <= rodata[r].base + rodata[r].size) slotInside = true;
    if (!slotInside || *(const unsigned *)MenuSlot != SITE(MENU_DRAW_SCENE)) {
        Log("theMenuScene's DrawScene slot does not point to the pinned DrawScene");
        return false;
    }
    return true;
}

// ================================================================ module: the box
struct GameRect { int left, top, right, bottom; };
typedef void (__thiscall *DrawSceneFn)(void *scene);
typedef void *(__cdecl *WindowGetFn)();
typedef void (__thiscall *GetBoundsFn)(void *scene, GameRect *rect);
typedef void (__thiscall *FillRectFn)(void *window, GameRect *rect, unsigned color);
typedef void *(__thiscall *GetFontFn)(void *window);
typedef int (__thiscall *GetHeightFn)(void *font, const char *text);
typedef int (__thiscall *GetWidthFn)(void *font, const char *text, float scale);

#define FIELD(p, off, type) (*(type *)((unsigned)(p) + (off)))

// Is `control` in the scene's control list (what DrawControls draws)? A bounded walk.
static bool InScene(void *scene, unsigned control) {
    unsigned impl = FIELD(scene, TBOX_SCENE_IMPL_FIELD, unsigned);
    if (!impl) return false;
    unsigned node = FIELD(impl, TBOX_SCENE_CONTROLS_FIELD, unsigned);
    for (unsigned n = 0; node && n < 4096; ++n) {
        if (FIELD(node, 0, unsigned) == control) return true;
        node = FIELD(node, 4, unsigned);
    }
    return false;
}

// The rectangle ldwTextControlImpl::Draw draws the name's text in, plus the padding. False when Draw would draw
// no text (or the control is a text box being edited, which the name never is).
static bool NameBox(void *scene, void *window, GameRect *box) {
    unsigned control = FIELD(scene, TBOX_NAME_CONTROL_FIELD, unsigned);
    if (!control || !InScene(scene, control)) return false;
    unsigned impl = FIELD(control, TBOX_CONTROL_IMPL_FIELD, unsigned);
    if (!impl || !FIELD(impl, TBOX_TEXT_SHOWN, unsigned char) || FIELD(impl, TBOX_TEXT_EDITABLE, unsigned char))
        return false;
    const char *text = FIELD(impl, TBOX_TEXT_STRING, const char *);
    if (!text) return false;
    unsigned length = 0;
    if (FIELD(impl, TBOX_TEXT_COUNT_SET, unsigned char)) length = FIELD(impl, TBOX_TEXT_LENGTH, unsigned);
    else while (text[length]) ++length;
    if (!length) return false;
    GameRect bounds = { 0, 0, 0, 0 };
    void *owner = FIELD(impl, TBOX_TEXT_SCENE, void *);
    if (owner) ((GetBoundsFn)SITE(SCENE_GET_BOUNDS))(owner, &bounds);
    void *font = FIELD(impl, TBOX_TEXT_FONT, void *);
    if (!font) font = ((GetFontFn)SITE(WINDOW_GET_FONT))(window);
    if (!font) return false;
    float scale = FIELD(impl, TBOX_TEXT_SCALE, float);
    int height = (int)(scale * (float)((GetHeightFn)SITE(FONT_GET_HEIGHT))(font, 0));
    int width = ((GetWidthFn)SITE(FONT_GET_WIDTH))(font, text, scale);
    int left = FIELD(impl, TBOX_TEXT_LEFT, int), right = FIELD(impl, TBOX_TEXT_RIGHT, int);
    int inset = FIELD(impl, TBOX_TEXT_INSET, int), x;
    switch (FIELD(impl, TBOX_TEXT_JUSTIFY, int)) {
    case 0: x = inset + left; break;
    case 1: x = (right - left - width) / 2 + left; break;
    case 2: x = right - inset - width; break;
    default: return false;
    }
    x += bounds.left;
    int y = FIELD(impl, TBOX_TEXT_OFFSET_Y, int) + FIELD(impl, TBOX_TEXT_TOP, int) + bounds.top;
    const int pad = (int)TBOX_BOX_PADDING;
    box->left = x - pad;
    box->top = y - pad;
    box->right = x + width + pad;
    box->bottom = y + height + pad;
    return true;
}

// theMenuScene's DrawScene (thiscall, plain ret: __fastcall with edx unused has the same frame).
static void __fastcall TitleDrawScene(void *scene, void *) {
    ((DrawSceneFn)SITE(MENU_DRAW_SCENE))(scene);
    ++B200TitleBox_Status.frames;
    void *window = ((WindowGetFn)SITE(GAME_WINDOW_GET))();
    if (!window) return;
    GameRect box;
    if (!NameBox(scene, window, &box)) return;
    ((FillRectFn)SITE(FILL_RECT))(window, &box, TBOX_BOX_COLOR);
    ++B200TitleBox_Status.boxes;
    B200TitleBox_Status.lastLeft = box.left;
    B200TitleBox_Status.lastTop = box.top;
    B200TitleBox_Status.lastRight = box.right;
    B200TitleBox_Status.lastBottom = box.bottom;
}

static void PlanTitleBox(Plan &plan) {
    plan.Slot(MenuSlot, (const void *)&TitleDrawScene);
}

// ================================================================ install
// 0 = setting off (nothing planned); -1 = could not be proved (nothing planned); 1 = planned.
static int BuildPlan(bool enabled, Plan &plan) {
    plan.count = 0;
    plan.ok = true;
    if (!enabled) return 0;
    if (!Resolve()) return -1;
    PlanTitleBox(plan);
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
            B200TitleBox_Status.writeMask = 0;
            return false;
        }
        B200TitleBox_Status.writeMask |= 1u << i;
    }
    return true;
}

static bool SettingOn() {
    wchar_t path[MAX_PATH];
    if (!InFolder(L"vf2titlebox.ini", path)) return false;
    return GetPrivateProfileIntW(L"Patches", L"NameBox", 0, path) == 1;
}

// Called once by the executable's loader, before the game loop starts.
extern "C" __declspec(dllexport) void __cdecl B200TitleBox_Startup() {
    static bool started = false;
    if (started) return;
    started = true;

    DWORD n = GetModuleFileNameW(ThisModule, Folder, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    unsigned cut = n;
    while (cut > 0 && Folder[cut - 1] != L'\\') --cut;
    if (!cut) return;
    Folder[cut] = 0;

    Log("vf2titlebox_b200 started");
    bool on = SettingOn();
    B200TitleBox_Status.requested = on ? 1u : 0u;
    static Plan plan;
    int built = BuildPlan(on, plan);
    if (built == 0) { Log("NameBox is off: the game is stock"); return; }
    if (built < 0) { Log("the executable could not be proved: installing nothing"); return; }
    B200TitleBox_Status.resolved = 1;
    if (Apply(plan)) {
        B200TitleBox_Status.installed = 1;
        Log("Title Screen Player Name Box installed (1 write)");
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
#ifdef B200TITLEBOX_TEST
// The addresses of ScanPattern and NextDword, so the emulator harness can replace the scans (a million-byte
// loop per pin) with native ones while every other line of the resolver still runs.
extern "C" __declspec(dllexport) unsigned __cdecl B200TitleBox_TestScanAddress() {
    return (unsigned)&ScanPattern;
}
extern "C" __declspec(dllexport) unsigned __cdecl B200TitleBox_TestNextDwordAddress() {
    return (unsigned)&NextDword;
}
// The planning half of the install path against the mapped image, without writing it.
// out: [status, count, then per write: va, len, data, bytes0..3, bytes4..7].
extern "C" __declspec(dllexport) int __cdecl B200TitleBox_TestPlan(int enabled, unsigned *out) {
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
// Plan and apply (the emulator maps the image writable, so VirtualProtect is a seam).
extern "C" __declspec(dllexport) int __cdecl B200TitleBox_TestInstall(int enabled) {
    static Plan plan;
    int built = BuildPlan(enabled != 0, plan);
    if (built > 0 && Apply(plan)) B200TitleBox_Status.installed = 1;
    return built;
}
// DllMain does not run under the emulator: tell the DLL which module it is.
extern "C" __declspec(dllexport) void __cdecl B200TitleBox_TestSetModule(unsigned module) {
    ThisModule = (HMODULE)module;
}
// The resolved sites (live addresses), TBOX_SITE_COUNT of them, then theMenuScene's DrawScene slot.
extern "C" __declspec(dllexport) void __cdecl B200TitleBox_TestSites(unsigned *out) {
    for (unsigned i = 0; i < TBOX_SITE_COUNT; ++i) out[i] = Sites[i];
    out[TBOX_SITE_COUNT] = MenuSlot;
}
// The DLL's DrawScene replacement, so a test can tell it from the stock pointer.
extern "C" __declspec(dllexport) unsigned __cdecl B200TitleBox_TestHook() {
    return (unsigned)&TitleDrawScene;
}
#endif
