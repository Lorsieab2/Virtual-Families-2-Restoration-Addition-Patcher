// vf2unicode_b200.dll -- "Render Unicode with In-Game Fonts" and "Use Unicode Font (overrides in-game fonts)", the
// companion DLL for the B200 Virtual Families 2 executable. One feature (Unicode text), one DLL.
//
// What it does (runtime/b200_unicode_sites.py has the full account; src/vf2_game_text.py is the same rules in Python,
// proved equal to the game's own text code by emulation, and b200unicode_text.h is proved equal to the Python):
//
//   * text is stored as the patcher's one rule says: UTF-8 when it is valid UTF-8 with a byte of 80h or more, else
//     one byte per character (Latin-1, Windows-1252 for 80h..9Fh); ASCII never changes;
//   * DrawString, DrawChars, GetWidth and GetNextJustifiedLine are the stock functions with a CHARACTER (a grapheme
//     cluster) in place of a byte; DrawStringJustified (dialogs, store, events) is the stock function, handed a copy
//     of the text in which each character beyond ASCII is one byte the font answers with that character's glyph;
//   * a character the game's font has is drawn from the game's sheet; one it lacks is a patcher-made glyph
//     ("Unicode Text\<font>.png", made by the patcher in the font's own style), or drawn now with GDI from the first
//     Windows font that has it (Segoe UI, Segoe UI Historic, Segoe UI Symbol, Segoe UI Emoji, the CJK fonts, Nirmala UI,
//     Ebrima ..., Noto if installed) at the game font's fitted size, weight and offset, with the sheet's own alpha
//     levels, or the missing-glyph box. Those glyphs go into a taller copy of the font's sheet (the stock pixels
//     unchanged at the top), so the game's own tinting and blitting draw them;
//   * typing: SDL_TEXTINPUT of anything but one ASCII byte (accented keys, dead keys, Alt codes, the IME) reaches the
//     focused text box one character at a time; a character is added only if the box's whole text still fits the
//     box's own byte limit in the stored form; Backspace removes a whole character; GetText cuts at a character.
//
// "Use Unicode Font (overrides in-game fonts)" (Mode=2) draws every character, ASCII too, with the chosen Windows font
// (then the same fallback chain) at each game font's fitted size, so layouts keep their sizes.
//
// The B200 executable is RELOCATED and each of the 32 matrix variants links to different addresses: this DLL holds NO
// game address. b200unicode_sites.h (runtime/tools/gen_b200_unicode_sites.py) holds whole stock functions with
// wildcards for relocated fields; Resolve() finds each exactly once and derives every site. Installing is: setting ->
// resolve -> plan -> apply, all or nothing. With the setting off, or anything the resolver cannot prove, NOTHING is
// written and the game is B200's own bytes.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include "b200unicode_sites.h"
#include "b200unicode_text.h"

// ================================================================ SDL (SDL2.dll / SDL2_image.dll, as the game links)
struct SDL_PixelFormat {
    unsigned format; void *palette; unsigned char BitsPerPixel, BytesPerPixel, padding[2];
    unsigned Rmask, Gmask, Bmask, Amask;
};
struct SDL_Surface {
    unsigned flags; SDL_PixelFormat *format; int w, h, pitch; void *pixels;
};
struct SDL_Rect { int x, y, w, h; };

typedef SDL_Surface *(__cdecl *CreateRGBSurfaceFn)(unsigned, int, int, int, unsigned, unsigned, unsigned, unsigned);
typedef void (__cdecl *FreeSurfaceFn)(SDL_Surface *);
typedef int (__cdecl *LockSurfaceFn)(SDL_Surface *);
typedef void (__cdecl *UnlockSurfaceFn)(SDL_Surface *);
typedef unsigned (__cdecl *MapRGBAFn)(const SDL_PixelFormat *, unsigned char, unsigned char, unsigned char,
                                      unsigned char);
typedef void (__cdecl *GetRGBAFn)(unsigned, const SDL_PixelFormat *, unsigned char *, unsigned char *,
                                  unsigned char *, unsigned char *);
typedef int (__cdecl *UpperBlitFn)(SDL_Surface *, const SDL_Rect *, SDL_Surface *, SDL_Rect *);
typedef int (__cdecl *PollEventFn)(void *);
typedef SDL_Surface *(__cdecl *ImgLoadFn)(const char *);

static CreateRGBSurfaceFn SdlCreate;
static FreeSurfaceFn SdlFree;
static LockSurfaceFn SdlLock;
static UnlockSurfaceFn SdlUnlock;
static MapRGBAFn SdlMapRGBA;
static GetRGBAFn SdlGetRGBA;
static ImgLoadFn ImgLoad;

// ================================================================ the game's functions (derived sites)
static unsigned Sites[UNI_SITE_COUNT];
#define SITE(name) (Sites[UNI_SITE_##name])
static unsigned FontVtable, TextVtable, PollSlot;

typedef SDL_Surface *(__thiscall *GetImageFn)(void *impl, unsigned color);
typedef bool (__thiscall *ClipRectFn)(void *window, int *rect, int *x, int *y);
typedef void (__thiscall *BlitAlphaFn)(void *window, SDL_Surface *, int, int, int, int, int, int, float, float, bool);
typedef void (__thiscall *CharRectFn)(void *impl, int ch, int *rect);
typedef bool (__thiscall *HandleKeyFn)(void *ctl, int type, int code, int sym);
typedef void *(__cdecl *EventsGetFn)();
typedef void (__thiscall *EventsHandleKeyFn)(void *events, int type, int code, int sym);
typedef void (__thiscall *PostMessageFn)(void *events, int message, long value);
typedef int (__fastcall *JustifiedFn)(void *self, void *, const char *, int, int, int, unsigned, void *, int, int, int);

static PollEventFn RealPoll;
static unsigned char JustifiedTrampoline[32];

// ================================================================ status
// B200Unicode_Status: magic 'UNXT', version, mode (0 off, 1 in-game fonts, 2 Unicode font), resolved, installed,
// writeMask, fonts (font objects given glyph room), patcherGlyphs (loaded), runtimeGlyphs (drawn with GDI), boxes
// (missing-glyph boxes), typed (characters added by typing), refused (characters refused: the box was full),
// fittedCuts (GetText cuts that ended at a character before the field's end)
struct UnicodeStatus {
    unsigned magic, version, mode, resolved, installed, writeMask, fonts, patcherGlyphs, runtimeGlyphs, boxes, typed,
        refused, fittedCuts;
};
extern "C" __declspec(dllexport) volatile UnicodeStatus B200Unicode_Status = {
    UNI_STATUS_MAGIC, 1u, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };

static HMODULE ThisModule;
static wchar_t Folder[MAX_PATH];
static unsigned Mode;                       // 1 = Render Unicode with In-Game Fonts, 2 = Use Unicode Font
static wchar_t OverrideFace[LF_FACESIZE];

static void *Alloc(unsigned n) { return HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, n); }
static void Release(void *p) { if (p) HeapFree(GetProcessHeap(), 0, p); }

static bool InFolder(const wchar_t *name, wchar_t *path) {
    unsigned n = 0;
    while (Folder[n]) { if (n + 1 >= MAX_PATH) return false; path[n] = Folder[n]; ++n; }
    for (unsigned i = 0; name[i]; ++i) { if (n + 1 >= MAX_PATH) return false; path[n++] = name[i]; }
    path[n] = 0;
    return true;
}

#ifdef B200UNICODE_TEST
static void Log(const char *) {}
#else
static bool LogStarted;
static void Log(const char *line) {
    wchar_t path[MAX_PATH];
    if (!InFolder(L"vf2unicode.log", path)) return;
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

// ================================================================ resolver
struct ImageRange { unsigned base, size; };
static const unsigned kMaxRanges = 24;

static bool LiveSections(ImageRange *code, unsigned *codeCount, ImageRange *data, unsigned *dataCount,
                         ImageRange *rodata, unsigned *rodataCount, unsigned *imageBase, unsigned *imageEnd) {
    HMODULE exe = GetModuleHandleW(0);
    *codeCount = *dataCount = *rodataCount = 0;
    if (!exe) return false;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)exe;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    *imageBase = (unsigned)exe;
    *imageEnd = (unsigned)exe + nt->OptionalHeader.SizeOfImage;
    const IMAGE_SECTION_HEADER *s = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        unsigned size = s[i].Misc.VirtualSize ? s[i].Misc.VirtualSize : s[i].SizeOfRawData;
        if (s[i].SizeOfRawData < size) size = s[i].SizeOfRawData;
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

#ifdef B200UNICODE_TEST
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

#ifdef B200UNICODE_TEST
__declspec(noinline)
#endif
static unsigned NextDword(unsigned from, unsigned end, unsigned value) {
    for (unsigned at = from; at + 4 <= end; at += 4)
        if (*(const unsigned *)at == value) return at;
    return 0;
}

// A class's vtable through its RTTI: the one type descriptor named `name`, the one complete object locator at
// offset 0 pointing to it, and the one vtable whose slot -1 points to that locator. 0 if any is not exactly one.
static unsigned VtableOf(const char *name, unsigned len, const ImageRange *data, unsigned dataCount,
                         const ImageRange *rodata, unsigned rodataCount) {
    static unsigned char zeros[64];
    if (len > sizeof(zeros)) return 0;
    unsigned hits = 0, at = 0;
    for (unsigned r = 0; r < dataCount && hits < 2; ++r) {
        unsigned h = 0;
        unsigned found = ScanPattern((const unsigned char *)data[r].base, data[r].size, (const unsigned char *)name,
                                     zeros, len, &h);
        if (h) { if (!hits) at = found; hits += h; }
    }
    if (hits != 1 || at < 8) return 0;
    unsigned td = at - 8, cols = 0, col = 0;
    for (unsigned r = 0; r < rodataCount; ++r) {
        unsigned end = rodata[r].base + rodata[r].size;
        for (unsigned p = NextDword(rodata[r].base + 12, end, td); p; p = NextDword(p + 4, end, td)) {
            unsigned c = p - 12;
            if (((const unsigned *)c)[0] == 0 && ((const unsigned *)c)[1] == 0) { ++cols; col = c; }
        }
    }
    if (cols != 1) return 0;
    unsigned vts = 0, vt = 0;
    for (unsigned r = 0; r < rodataCount; ++r) {
        unsigned end = rodata[r].base + rodata[r].size;
        for (unsigned p = NextDword(rodata[r].base, end, col); p; p = NextDword(p + 4, end, col)) { ++vts; vt = p + 4; }
    }
    return vts == 1 ? vt : 0;
}

static bool Resolve() {
    static ImageRange code[kMaxRanges], data[kMaxRanges], rodata[kMaxRanges];
    unsigned codeCount = 0, dataCount = 0, rodataCount = 0, imageBase = 0, imageEnd = 0;
    if (!LiveSections(code, &codeCount, data, &dataCount, rodata, &rodataCount, &imageBase, &imageEnd)) return false;
    static unsigned loc[UNI_PIN_COUNT];
    for (unsigned i = 0; i < UNI_PIN_COUNT; ++i) {
        const UniPin &pin = UNI_PINS[i];
        unsigned hits = 0, at = 0;
        for (unsigned r = 0; r < codeCount && hits < 2; ++r) {
            unsigned h = 0;
            unsigned found = ScanPattern((const unsigned char *)code[r].base, code[r].size, pin.bytes, pin.mask,
                                         pin.len, &h);
            if (h) { if (!hits) at = found; hits += h; }
        }
        if (hits != 1) { Log("a pinned function is not found exactly once"); Log(pin.name); return false; }
        loc[i] = at;
    }
    bool have[UNI_SITE_COUNT];
    for (unsigned i = 0; i < UNI_SITE_COUNT; ++i) have[i] = false;
    for (unsigned e = 0; e < sizeof(UNI_EVIDENCE) / sizeof(UNI_EVIDENCE[0]); ++e) {
        const UniEvidence &ev = UNI_EVIDENCE[e];
        unsigned at = loc[ev.pin] + ev.offset, v;
        if (ev.kind == 'L') v = at;
        else if (ev.kind == 'A') v = *(const unsigned *)at;
        else v = at + 4 + *(const unsigned *)at;
        if (have[ev.site] && Sites[ev.site] != v) { Log("two derivations of a site disagree"); return false; }
        Sites[ev.site] = v;
        have[ev.site] = true;
    }
    for (unsigned i = 0; i < UNI_SITE_COUNT; ++i) if (!have[i]) { Log("a site is underived"); return false; }
    static const char fontName[] = UNI_FONT_TYPE_NAME;
    static const char textName[] = UNI_TEXT_TYPE_NAME;
    FontVtable = VtableOf(fontName, sizeof(fontName), data, dataCount, rodata, rodataCount);
    TextVtable = VtableOf(textName, sizeof(textName), data, dataCount, rodata, rodataCount);
    if (!FontVtable || !TextVtable) { Log("a vtable is not found exactly once"); return false; }
    if (*(const unsigned *)(FontVtable + 4 * UNI_FONT_VSLOT_CHAR_RECT) != SITE(CHAR_RECT) ||
        *(const unsigned *)(TextVtable + 4 * UNI_TEXT_VSLOT_HANDLE_KEY) != SITE(TEXT_HANDLE_KEY)) {
        Log("a vtable slot does not hold the pinned function");
        return false;
    }
    const unsigned char *thunk = (const unsigned char *)SITE(POLL_EVENT);
    if (thunk[0] != 0xFF || thunk[1] != 0x25) { Log("SDL_PollEvent is not called through an import thunk"); return false; }
    PollSlot = *(const unsigned *)(thunk + 2);
    if (PollSlot < imageBase || PollSlot + 4 > imageEnd) { Log("the SDL_PollEvent import slot is outside the image"); return false; }
    static const unsigned char head[UNI_JUSTIFIED_STEAL] = { 0x55, 0x8B, 0xEC, 0x81, 0xEC, 0x50, 0x05, 0x00, 0x00 };
    for (unsigned k = 0; k < UNI_JUSTIFIED_STEAL; ++k)
        if (((const unsigned char *)SITE(DRAW_JUSTIFIED))[k] != head[k]) { Log("DrawStringJustified's start differs"); return false; }
    return true;
}

static bool LoadSdl() {
    HMODULE sdl = GetModuleHandleW(L"SDL2.dll");
    if (!sdl) return false;
    SdlCreate = (CreateRGBSurfaceFn)GetProcAddress(sdl, "SDL_CreateRGBSurface");
    SdlFree = (FreeSurfaceFn)GetProcAddress(sdl, "SDL_FreeSurface");
    SdlLock = (LockSurfaceFn)GetProcAddress(sdl, "SDL_LockSurface");
    SdlUnlock = (UnlockSurfaceFn)GetProcAddress(sdl, "SDL_UnlockSurface");
    SdlMapRGBA = (MapRGBAFn)GetProcAddress(sdl, "SDL_MapRGBA");
    SdlGetRGBA = (GetRGBAFn)GetProcAddress(sdl, "SDL_GetRGBA");
    HMODULE img = GetModuleHandleW(L"SDL2_image.dll");
    ImgLoad = img ? (ImgLoadFn)GetProcAddress(img, "IMG_Load") : 0;
    return SdlCreate && SdlFree && SdlLock && SdlUnlock && SdlMapRGBA && SdlGetRGBA;
}

// ================================================================ GDI: a character in a Windows font
static const wchar_t *const kChain[] = {
    L"Segoe UI", L"Segoe UI Historic", L"Segoe UI Symbol", L"Segoe UI Emoji",
    L"Microsoft YaHei UI", L"Microsoft JhengHei UI", L"Yu Gothic UI", L"Malgun Gothic", L"SimSun-ExtB",
    L"Nirmala UI", L"Ebrima", L"Gadugi", L"Leelawadee UI", L"Javanese Text", L"Myanmar Text", L"Mongolian Baiti",
    L"Microsoft Himalaya", L"Microsoft New Tai Lue", L"Microsoft Tai Le", L"Microsoft Yi Baiti", L"Sylfaen",
    L"Noto Sans", L"Noto Sans CJK SC", L"Noto Sans Symbols", L"Noto Sans Symbols 2", L"Noto Sans Cuneiform",
};
static const unsigned kChainCount = sizeof(kChain) / sizeof(kChain[0]);

struct CmapCache { const wchar_t *face; int weight; unsigned char *table; unsigned size; unsigned sub12, sub4; bool loaded; };
static CmapCache Cmaps[2 * (sizeof(kChain) / sizeof(kChain[0]) + 1)];

static unsigned BE16(const unsigned char *p) { return (p[0] << 8) | p[1]; }
static unsigned BE32(const unsigned char *p) { return ((unsigned)p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]; }

static HFONT MakeFont(const wchar_t *face, int px, int weight) {
    return CreateFontW(-px, 0, 0, 0, weight, 0, 0, 0, DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, face);
}

// The font's "cmap" (src/vf2_glyph_render.Cmap): the first Unicode format 12 subtable, else the first format 4.
static CmapCache *CmapOf(const wchar_t *face, int weight) {
    unsigned free = 0xFFFFFFFF;
    for (unsigned i = 0; i < sizeof(Cmaps) / sizeof(Cmaps[0]); ++i) {
        if (Cmaps[i].loaded && Cmaps[i].face == face && Cmaps[i].weight == weight) return &Cmaps[i];
        if (!Cmaps[i].loaded && free == 0xFFFFFFFF) free = i;
    }
    if (free == 0xFFFFFFFF) return 0;
    CmapCache &c = Cmaps[free];
    c.face = face; c.weight = weight; c.loaded = true; c.table = 0; c.size = 0; c.sub12 = c.sub4 = 0;
    HDC dc = CreateCompatibleDC(0);
    if (!dc) return &c;
    HFONT f = MakeFont(face, 16, weight);
    HGDIOBJ old = SelectObject(dc, f);
    wchar_t got[LF_FACESIZE];
    if (GetTextFaceW(dc, LF_FACESIZE, got) && lstrcmpiW(got, face) == 0) {
        DWORD tag = 0x70616D63;                      // 'cmap'
        DWORD n = GetFontData(dc, tag, 0, 0, 0);
        if (n != GDI_ERROR && n) {
            c.table = (unsigned char *)Alloc(n);
            if (c.table && GetFontData(dc, tag, 0, c.table, n) == n) c.size = n;
        }
    }
    SelectObject(dc, old);
    DeleteObject(f);
    DeleteDC(dc);
    if (c.size >= 4) {
        unsigned count = BE16(c.table + 2);
        for (unsigned k = 0; k < count && 4 + 8 * k + 8 <= c.size; ++k) {
            const unsigned char *rec = c.table + 4 + 8 * k;
            unsigned pid = BE16(rec), eid = BE16(rec + 2), off = BE32(rec + 4);
            if (off + 2 > c.size || !(pid == 0 || (pid == 3 && (eid == 1 || eid == 10)))) continue;
            unsigned fmt = BE16(c.table + off);
            if (fmt == 12 && !c.sub12) c.sub12 = off;
            else if (fmt == 4 && !c.sub4) c.sub4 = off;
        }
    }
    return &c;
}

static unsigned GlyphIndex(CmapCache *c, unsigned cp) {
    if (!c || !c->size) return 0;
    const unsigned char *t = c->table;
    if (c->sub12 && c->sub12 + 16 <= c->size) {
        unsigned off = c->sub12, n = BE32(t + off + 12);
        unsigned lo = 0, hi = n;
        while (lo < hi) {
            unsigned mid = (lo + hi) / 2;
            unsigned at = off + 16 + 12 * mid;
            if (at + 12 > c->size) return 0;
            unsigned first = BE32(t + at), last = BE32(t + at + 4);
            if (cp < first) hi = mid;
            else if (cp > last) lo = mid + 1;
            else return BE32(t + at + 8) + (cp - first);
        }
        return 0;
    }
    if (c->sub4 && c->sub4 + 14 <= c->size && cp <= 0xFFFF) {
        unsigned off = c->sub4, segx2 = BE16(t + off + 6);
        unsigned ends = off + 14, starts = ends + segx2 + 2, deltas = starts + segx2, offsets = deltas + segx2;
        if (offsets + segx2 > c->size) return 0;
        for (unsigned k = 0; k < segx2 / 2; ++k) {
            unsigned end = BE16(t + ends + 2 * k), start = BE16(t + starts + 2 * k);
            if (start > end || start == 0xFFFF || cp < start || cp > end) continue;
            int delta = (short)BE16(t + deltas + 2 * k);
            unsigned ro = BE16(t + offsets + 2 * k);
            if (ro == 0) return (cp + delta) & 0xFFFF;
            unsigned at = offsets + 2 * k + ro + 2 * (cp - start);
            unsigned g = at + 2 <= c->size ? BE16(t + at) : 0;
            return g ? ((g + delta) & 0xFFFF) : 0;
        }
    }
    return 0;
}

static bool Ignorable(unsigned cp) {
    return cp == 0x200B || cp == 0x200C || cp == 0x200D || cp == 0x2060 || cp == 0xFEFF ||
           (cp >= 0xFE00 && cp <= 0xFE0F) || (cp >= 0xE0000 && cp <= 0xE0FFF);
}

// The face that draws a character: the first of the chain whose normal-weight cmap has `base` (an override face
// first in Mode 2). 0 = none.
static const wchar_t *FaceFor(unsigned base) {
    if (Mode == 2 && OverrideFace[0] && GlyphIndex(CmapOf(OverrideFace, FW_NORMAL), base)) return OverrideFace;
    for (unsigned i = 0; i < kChainCount; ++i)
        if (GlyphIndex(CmapOf(kChain[i], FW_NORMAL), base)) return kChain[i];
    return 0;
}

// src/vf2_glyph_render.render + src/vf2_game_text.runtime_glyph: the cluster drawn glyph by glyph on a 10 x px canvas
// (pen from x = px, the text's top at ty; baseline: the text's baseline at ty, TA_BASELINE - Use Unicode Font), cut to
// its advance, grey -> the sheet's alpha levels. alpha gets width * lineHeight bytes (at most cap). Returns the
// width, or -1 when no font has the character.
static int RenderRuntime(const ut::Unit &u, const UniFont &font, int px, int ty, bool baseline, unsigned char *alpha,
                         unsigned cap) {
    unsigned base = u.cps[0];
    for (unsigned i = 0; i < u.ncp && i < ut::kMaxClusterCps; ++i)
        if (!ut::IsExtend(u.cps[i]) || u.ncp == 1) { base = u.cps[i]; break; }
    const wchar_t *face = FaceFor(base);
    if (!face) return -1;
    int h = font.lineHeight, width = 10 * (px > 1 ? px : 1);
    CmapCache *cm = CmapOf(face, font.weight);
    HDC dc = CreateCompatibleDC(0);
    if (!dc) return -1;
    BITMAPINFO bmi;
    for (unsigned k = 0; k < sizeof(bmi); ++k) ((unsigned char *)&bmi)[k] = 0;
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = width;
    bmi.bmiHeader.biHeight = -h;
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 32;
    void *bits = 0;
    HBITMAP bmp = CreateDIBSection(dc, &bmi, DIB_RGB_COLORS, &bits, 0, 0);
    if (!bmp || !bits) { DeleteDC(dc); return -1; }
    HGDIOBJ oldBmp = SelectObject(dc, bmp);
    HFONT f = MakeFont(face, px, font.weight);
    HGDIOBJ oldFont = SelectObject(dc, f);
    SetTextColor(dc, 0x00FFFFFF);
    SetBkColor(dc, 0);
    SetBkMode(dc, OPAQUE);
    SetTextAlign(dc, baseline ? TA_BASELINE : 0);
    unsigned char *b = (unsigned char *)bits;
    for (int k = 0; k < width * h * 4; ++k) b[k] = 0;
    int pen = px;
    for (unsigned i = 0; i < u.ncp && i < ut::kMaxClusterCps; ++i) {
        if (Ignorable(u.cps[i])) continue;
        unsigned g = GlyphIndex(cm, u.cps[i]);
        if (!g) continue;
        WORD gi = (WORD)g;
        ExtTextOutW(dc, pen, ty, ETO_GLYPH_INDEX, 0, (LPCWSTR)&gi, 1, 0);
        ABC abc;
        if (GetCharABCWidthsI(dc, gi, 1, 0, &abc)) pen += abc.abcA + (int)abc.abcB + abc.abcC;
    }
    GdiFlush();
    int adv = pen - px;
    if (adv > width - px) adv = width - px;
    if (adv < 0) adv = 0;
    if ((unsigned)(adv * h) <= cap) {
        for (int y = 0; y < h; ++y)
            for (int x = 0; x < adv; ++x) alpha[y * adv + x] = font.alpha[b[(y * width + px + x) * 4 + 1]];
    } else {
        adv = -1;
    }
    SelectObject(dc, oldFont);
    DeleteObject(f);
    SelectObject(dc, oldBmp);
    DeleteObject(bmp);
    DeleteDC(dc);
    return adv;
}

// src/vf2_game_text.missing_box
static int MissingBox(const UniFont &font, unsigned char *alpha, unsigned cap) {
    int px = font.px, h = font.lineHeight;
    int w = (px * 6 + 5) / 10; if (w < 4) w = 4;
    int ascent = (px * 7 + 5) / 10; if (ascent < 2) ascent = 2;
    int base = -font.top + (px * 108 + 50) / 100; if (base > h - 1) base = h - 1;
    int top = base - ascent; if (top < 0) top = 0;
    if ((unsigned)(w * h) > cap) return -1;
    for (int k = 0; k < w * h; ++k) alpha[k] = 0;
    for (int y = top; y <= base; ++y)
        for (int x = 1; x < w - 1; ++x)
            if (y == top || y == base || x == 1 || x == w - 2) alpha[y * w + x] = 255;
    return w;
}

// ================================================================ the fonts' glyph room
struct GlyphSlot { unsigned key[ut::kMaxClusterCps]; unsigned nk; int x, y, w; bool used; };
static const unsigned kSlots = 16384;

struct PatcherGlyph { unsigned cp; int x, y, w; };

struct FontRec {
    unsigned impl;            // the ldwFontImpl
    SDL_Surface *patcherSurf; // "Unicode Text\<font>.png", loaded once
    PatcherGlyph *patcher;    // its glyphs, by code point
    unsigned patcherCount;
    int index;                // UNI_FONTS index, -1 = not one of the four (left stock)
    int lineHeight, sheetW, stockH, nextX, nextY;
    int px, base;             // Use Unicode Font: the fitted pixel size and the baseline row (FitOverride)
    SDL_Surface *sheet;
    GlyphSlot *slots;
};
static FontRec Fonts[16];
static unsigned FontCount;

#define IMPL_FIELD(impl, off) (*(int *)((unsigned)(impl) + (off)))

static unsigned HashKey(const unsigned *k, unsigned n) {
    unsigned h = 2166136261u;
    for (unsigned i = 0; i < n; ++i) { h ^= k[i]; h *= 16777619u; }
    return h ^ n;
}

static GlyphSlot *FindSlot(FontRec &f, const unsigned *key, unsigned n, bool insert) {
    if (!f.slots || n == 0 || n > ut::kMaxClusterCps) return 0;
    unsigned at = HashKey(key, n) & (kSlots - 1);
    for (unsigned probe = 0; probe < kSlots; ++probe) {
        GlyphSlot &s = f.slots[(at + probe) & (kSlots - 1)];
        if (!s.used) {
            if (!insert) return 0;
            s.used = true; s.nk = n;
            for (unsigned i = 0; i < n; ++i) s.key[i] = key[i];
            s.w = -1;
            return &s;
        }
        if (s.nk == n) {
            unsigned i = 0;
            while (i < n && s.key[i] == key[i]) ++i;
            if (i == n) return &s;
        }
    }
    return 0;
}

// GetImage's tint: every pixel AND (r, g, b, FFh) of the colour.
static SDL_Surface *Tinted(SDL_Surface *src, unsigned color) {
    SDL_PixelFormat *fmt = src->format;
    SDL_Surface *dst = SdlCreate(0, src->w, src->h, fmt->BitsPerPixel, fmt->Rmask, fmt->Gmask, fmt->Bmask, fmt->Amask);
    if (!dst) return 0;
    SdlLock(dst); SdlLock(src);
    unsigned mask = SdlMapRGBA(dst->format, (unsigned char)color, (unsigned char)(color >> 8),
                               (unsigned char)(color >> 16), 0xFF);
    for (int y = 0; y < src->h; ++y) {
        const unsigned *s = (const unsigned *)((unsigned char *)src->pixels + y * src->pitch);
        unsigned *d = (unsigned *)((unsigned char *)dst->pixels + y * dst->pitch);
        for (int x = 0; x < src->w; ++x) d[x] = s[x] & mask;
    }
    SdlUnlock(src); SdlUnlock(dst);
    return dst;
}

// The font's tint cache (ldwFontImpl +41Ch: nodes { colour, surface, next }): every cached copy remade from the sheet.
static void RebuildTints(unsigned impl, SDL_Surface *sheet) {
    for (unsigned *node = *(unsigned **)(impl + 0x41C); node; node = (unsigned *)node[2]) {
        SDL_Surface *fresh = Tinted(sheet, node[0]);
        if (!fresh) continue;
        SdlFree((SDL_Surface *)node[1]);
        node[1] = (unsigned)fresh;
    }
}

// A taller copy of the font's sheet: the stock pixels at the top, `extra` clear rows below; the font's image and
// height take it, and every tinted copy is remade. The old sheet is kept (never freed while the game may hold it).
static bool GrowSheet(FontRec &f, int extra) {
    unsigned imageImpl = (unsigned)IMPL_FIELD(f.impl, 0x0C);
    if (!imageImpl) return false;
    SDL_Surface *old = *(SDL_Surface **)imageImpl;
    if (!old || old->format->BytesPerPixel != 4) return false;
    SDL_PixelFormat *fmt = old->format;
    SDL_Surface *sheet = SdlCreate(0, old->w, old->h + extra, fmt->BitsPerPixel, fmt->Rmask, fmt->Gmask, fmt->Bmask,
                                   fmt->Amask);
    if (!sheet) return false;
    SdlLock(sheet); SdlLock(old);
    unsigned clear = SdlMapRGBA(sheet->format, 255, 255, 255, 0);
    for (int y = 0; y < sheet->h; ++y) {
        unsigned *d = (unsigned *)((unsigned char *)sheet->pixels + y * sheet->pitch);
        if (y < old->h) {
            const unsigned *s = (const unsigned *)((unsigned char *)old->pixels + y * old->pitch);
            for (int x = 0; x < old->w; ++x) d[x] = s[x];
        } else {
            for (int x = 0; x < sheet->w; ++x) d[x] = clear;
        }
    }
    SdlUnlock(old); SdlUnlock(sheet);
    *(SDL_Surface **)imageImpl = sheet;
    IMPL_FIELD(f.impl, 0x18) = sheet->h;
    f.sheet = sheet;
    RebuildTints(f.impl, sheet);
    return true;
}

// A glyph cell (white, alpha) into the sheet and every tinted copy; returns its slot's place.
static bool PlaceGlyph(FontRec &f, GlyphSlot *slot, const unsigned char *alpha, int w) {
    if (w <= 0) { slot->w = 0; slot->x = slot->y = 0; return true; }
    if (w > f.sheetW) w = f.sheetW;
    if (f.nextX + w > f.sheetW) { f.nextX = 0; f.nextY += f.lineHeight; }
    if (f.nextY + f.lineHeight > f.sheet->h) {
        int extra = f.sheet->h - f.stockH;               // double the glyph room
        if (extra < 8 * f.lineHeight) extra = 8 * f.lineHeight;
        if (!GrowSheet(f, extra)) return false;
    }
    int gx = f.nextX, gy = f.nextY;
    f.nextX += w;
    SDL_Surface *s = f.sheet;
    SdlLock(s);
    for (int y = 0; y < f.lineHeight; ++y) {
        unsigned *row = (unsigned *)((unsigned char *)s->pixels + (gy + y) * s->pitch);
        for (int x = 0; x < w; ++x) row[gx + x] = SdlMapRGBA(s->format, 255, 255, 255, alpha[y * w + x]);
    }
    SdlUnlock(s);
    for (unsigned *node = *(unsigned **)(f.impl + 0x41C); node; node = (unsigned *)node[2]) {
        SDL_Surface *t = (SDL_Surface *)node[1];
        if (!t || t->h < gy + f.lineHeight) continue;
        unsigned color = node[0];
        unsigned mask = SdlMapRGBA(t->format, (unsigned char)color, (unsigned char)(color >> 8),
                                   (unsigned char)(color >> 16), 0xFF);
        SdlLock(t);
        for (int y = 0; y < f.lineHeight; ++y) {
            unsigned *row = (unsigned *)((unsigned char *)t->pixels + (gy + y) * t->pitch);
            for (int x = 0; x < w; ++x) row[gx + x] = SdlMapRGBA(t->format, 255, 255, 255, alpha[y * w + x]) & mask;
        }
        SdlUnlock(t);
    }
    slot->x = gx; slot->y = gy; slot->w = w;
    return true;
}

// "Unicode Text\<font>.png" + ".txt": the patcher-made glyphs. The picture stays loaded; a glyph is copied into the
// font's room the first time it is drawn (so the room, and every tinted copy of it, holds only what is used).
static void LoadPatcherGlyphs(FontRec &f) {
    if (!ImgLoad) return;
    const char *name = UNI_FONTS[f.index].name;
    wchar_t rel[64] = L"Unicode Text\\";
    unsigned n = 0;
    while (rel[n]) ++n;
    for (unsigned i = 0; name[i] && n < 50; ++i) rel[n++] = (wchar_t)name[i];
    rel[n] = 0;
    wchar_t txt[MAX_PATH], png[MAX_PATH], tmp[64];
    for (unsigned i = 0; i <= n; ++i) tmp[i] = rel[i];
    lstrcatW(tmp, L".txt");
    if (!InFolder(tmp, txt)) return;
    for (unsigned i = 0; i <= n; ++i) tmp[i] = rel[i];
    lstrcatW(tmp, L".png");
    if (!InFolder(tmp, png)) return;
    HANDLE h = CreateFileW(txt, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD size = GetFileSize(h, 0), got = 0;
    char *text = size && size < (8u << 20) ? (char *)Alloc(size + 1) : 0;
    bool ok = text && ReadFile(h, text, size, &got, 0) && got == size;
    CloseHandle(h);
    if (!ok) { Release(text); return; }
    char utf8[MAX_PATH * 3];
    if (!WideCharToMultiByte(CP_UTF8, 0, png, -1, utf8, sizeof(utf8), 0, 0)) { Release(text); return; }
    SDL_Surface *src = ImgLoad(utf8);
    if (!src) { Release(text); Log("a patcher-made glyph picture could not be read"); return; }
    unsigned cap = 0;
    for (DWORD i = 0; i < size; ++i) if (text[i] == '\n') ++cap;
    f.patcher = (PatcherGlyph *)Alloc(sizeof(PatcherGlyph) * (cap + 1));
    if (!f.patcher) { SdlFree(src); Release(text); return; }
    int height = -1;
    for (char *line = text; line && *line;) {
        char *end = line;
        while (*end && *end != '\n') ++end;
        char keep = *end;
        *end = 0;
        if (line[0] == 'h' && line[1] == 'e') {                       // "height N"
            height = 0;
            for (char *p = line + 7; *p >= '0' && *p <= '9'; ++p) height = height * 10 + (*p - '0');
        } else if (line[0] != '#' && line[0] != 'f' && line[0] != 'c' && height == f.lineHeight) {
            unsigned v[4] = { 0, 0, 0, 0 };
            unsigned field = 0;
            for (char *p = line; *p && field < 4; ++p) {
                if (*p == '\t') { ++field; continue; }
                unsigned d = (*p >= '0' && *p <= '9') ? (unsigned)(*p - '0') :
                             (*p >= 'A' && *p <= 'F') ? (unsigned)(*p - 'A' + 10) : 99;
                if (d == 99) continue;
                v[field] = v[field] * (field == 0 ? 16u : 10u) + d;
            }
            int gx = (int)v[1], gy = (int)v[2], gw = (int)v[3];
            if (field == 3 && gw > 0 && gw <= f.sheetW && gx + gw <= src->w && gy + f.lineHeight <= src->h &&
                f.patcherCount < cap + 1) {
                PatcherGlyph &g = f.patcher[f.patcherCount++];
                g.cp = v[0]; g.x = gx; g.y = gy; g.w = gw;
            }
        }
        *end = keep;
        line = keep ? end + 1 : 0;
    }
    Release(text);
    // the file lists the code points in rising order; keep only a sorted list (a binary search finds them)
    for (unsigned i = 1; i < f.patcherCount; ++i)
        if (f.patcher[i].cp <= f.patcher[i - 1].cp) { f.patcherCount = 0; break; }
    if (!f.patcherCount) { SdlFree(src); return; }
    f.patcherSurf = src;
    B200Unicode_Status.patcherGlyphs += f.patcherCount;
}

// The patcher-made glyph of cp as an alpha cell, or -1.
static int PatcherCell(FontRec &f, unsigned cp, unsigned char *cell, unsigned cap) {
    if (!f.patcherSurf) return -1;
    unsigned lo = 0, hi = f.patcherCount;
    while (lo < hi) {
        unsigned mid = (lo + hi) / 2;
        if (f.patcher[mid].cp < cp) lo = mid + 1; else hi = mid;
    }
    if (lo >= f.patcherCount || f.patcher[lo].cp != cp) return -1;
    const PatcherGlyph &g = f.patcher[lo];
    if ((unsigned)(g.w * f.lineHeight) > cap) return -1;
    SDL_Surface *src = f.patcherSurf;
    SdlLock(src);
    for (int y = 0; y < f.lineHeight; ++y) {
        const unsigned char *row = (const unsigned char *)src->pixels + (g.y + y) * src->pitch;
        for (int x = 0; x < g.w; ++x) {
            unsigned pixel = 0;
            const unsigned char *p = row + (g.x + x) * src->format->BytesPerPixel;
            for (unsigned k = 0; k < src->format->BytesPerPixel && k < 4; ++k) pixel |= (unsigned)p[k] << (8 * k);
            unsigned char r, gg, b, a;
            SdlGetRGBA(pixel, src->format, &r, &gg, &b, &a);
            cell[y * g.w + x] = a;
        }
    }
    SdlUnlock(src);
    return g.w;
}
static void FitOverride(FontRec &f, unsigned impl);    // Use Unicode Font: below

// The record of a font object; the first time, the font is recognised by its glyph widths and given its room.
static FontRec *Ensure(unsigned impl) {
    if (!impl) return 0;
    for (unsigned i = 0; i < FontCount; ++i) if (Fonts[i].impl == impl) return &Fonts[i];
    if (FontCount >= sizeof(Fonts) / sizeof(Fonts[0])) return 0;
    FontRec &f = Fonts[FontCount++];
    f.impl = impl; f.index = -1; f.sheet = 0; f.slots = 0; f.patcherSurf = 0; f.patcher = 0; f.patcherCount = 0;
    const int *table = (const int *)IMPL_FIELD(impl, 0x10);
    int lineHeight = IMPL_FIELD(impl, 0x04);
    if (!table || !IMPL_FIELD(impl, 0x0C)) return &f;
    for (unsigned k = 0; k < sizeof(UNI_FONTS) / sizeof(UNI_FONTS[0]); ++k) {
        const UniFont &u = UNI_FONTS[k];
        if (u.lineHeight != lineHeight) continue;
        unsigned j = 0;
        while (j < 24 && table[5 * j] && table[5 * j + 3] - table[5 * j + 1] == u.signature[j]) ++j;
        if (j == 24) { f.index = (int)k; break; }
    }
    if (f.index < 0) return &f;
    SDL_Surface *old = *(SDL_Surface **)IMPL_FIELD(impl, 0x0C);
    f.slots = (GlyphSlot *)Alloc(sizeof(GlyphSlot) * kSlots);
    if (!old || !f.slots) { f.index = -1; return &f; }
    f.lineHeight = lineHeight;
    f.sheetW = old->w;
    f.stockH = old->h;
    if (!GrowSheet(f, 16 * lineHeight)) { f.index = -1; return &f; }
    f.nextX = 0;
    f.nextY = f.stockH;
    f.px = UNI_FONTS[f.index].px;
    f.base = UNI_FONTS[f.index].top;
    if (Mode == 2) FitOverride(f, impl);
    LoadPatcherGlyphs(f);
    ++B200Unicode_Status.fonts;
    return &f;
}

static FontRec *Find(unsigned impl) {
    for (unsigned i = 0; i < FontCount; ++i) if (Fonts[i].impl == impl) return &Fonts[i];
    return 0;
}

// ================================================================ which glyph a character uses
struct Rect { int l, t, r, b; };

static bool HasStock(unsigned impl, unsigned cp) {
    if (cp >= 0x100) return false;
    if (cp < 0x20 || cp == 0x7F) return true;
    const int *charmap = (const int *)(impl + 0x1C);
    const int *table = (const int *)IMPL_FIELD(impl, 0x10);
    int k = charmap[cp];
    return (unsigned)table[5 * k] == cp || (k == 0 && (unsigned)table[0] == cp);
}

static Rect StockRect(unsigned impl, unsigned b) {
    const int *charmap = (const int *)(impl + 0x1C);
    const int *table = (const int *)IMPL_FIELD(impl, 0x10);
    const int *e = table + 5 * charmap[b & 0xFF];
    Rect r = { e[1], e[2], e[3], e[4] };
    return r;
}

// ================================================================ Use Unicode Font
// src/vf2_game_text.fit_unicode_font / unicode_baseline (VF1's FitChosenFont, the same arithmetic): the size at
// which kFitReference is as wide in the chosen face as the game font draws it, within 60% to 130% of the game
// font's fitted Segoe UI size (that size when the face is not installed); every face's baseline where Segoe UI's
// falls in the game font's line.
static const char kFitReference[] = "The quick brown fox jumps over the lazy dog 0123456789";

// GetTextExtentPoint32W of text in face (0 when Windows has no font of that name), or tmAscent when ascent.
static int FaceMeasure(const wchar_t *face, int px, int weight, const char *text, bool ascent) {
    HDC dc = CreateCompatibleDC(0);
    if (!dc) return 0;
    HFONT f = MakeFont(face, px, weight);
    HGDIOBJ old = SelectObject(dc, f);
    int out = 0;
    if (ascent) {
        TEXTMETRICW tm;
        if (GetTextMetricsW(dc, &tm)) out = tm.tmAscent;
    } else {
        wchar_t got[LF_FACESIZE], w[64];
        int n = 0;
        while (text[n] && n < 63) { w[n] = (wchar_t)(unsigned char)text[n]; ++n; }
        SIZE size = { 0, 0 };
        if (GetTextFaceW(dc, LF_FACESIZE, got) && lstrcmpiW(got, face) == 0 && GetTextExtentPoint32W(dc, w, n, &size))
            out = size.cx;
    }
    SelectObject(dc, old);
    DeleteObject(f);
    DeleteDC(dc);
    return out;
}

static void FitOverride(FontRec &f, unsigned impl) {
    const UniFont &font = UNI_FONTS[f.index];
    f.base = font.top + FaceMeasure(L"Segoe UI", font.px, font.weight, 0, true);
    int game = 0;
    for (const char *p = kFitReference; *p; ++p) {
        Rect r = StockRect(impl, (unsigned char)*p);
        game += r.r - r.l;
    }
    int width = OverrideFace[0] ? FaceMeasure(OverrideFace, font.px, font.weight, kFitReference, false) : 0;
    if (width <= 0 || game <= 0) return;
    int em = (font.px * game * 2 + width) / (2 * width);
    int lo = font.px * 6 / 10, hi = font.px * 13 / 10;
    f.px = em < lo ? lo : em > hi ? hi : em;
}

// src/vf2_game_text.GameFont.glyph. create: false = never make a glyph now (while the game holds a tinted sheet).
static bool GlyphFor(FontRec *f, unsigned impl, const ut::Unit &u, const unsigned char *raw, bool create, Rect &out) {
    bool known = f && f->index >= 0;
    if (!known || Mode != 2) {
        if (u.size == 1 && (raw[u.start] < 0x80 || HasStock(impl, u.cps[0]))) { out = StockRect(impl, raw[u.start]); return true; }
        if (!known) { out = StockRect(impl, raw[u.start]); return true; }
        unsigned cp = u.ncp == 1 ? u.cps[0] : ut::Composed(u);
        if (cp && cp < 0x100 && HasStock(impl, cp)) { out = StockRect(impl, cp); return true; }
        if (cp) {
            GlyphSlot *s = FindSlot(*f, &cp, 1, false);
            if (s && s->w >= 0) { Rect r = { s->x, s->y, s->x + s->w, s->y + f->lineHeight }; out = r; return true; }
            if (create && !s) {
                static unsigned char pcell[512 * 64];
                int w = PatcherCell(*f, cp, pcell, sizeof(pcell));
                if (w >= 0) {
                    s = FindSlot(*f, &cp, 1, true);
                    if (s && PlaceGlyph(*f, s, pcell, w)) {
                        Rect r = { s->x, s->y, s->x + s->w, s->y + f->lineHeight };
                        out = r;
                        return true;
                    }
                }
            }
        }
    }
    unsigned n = u.ncp < ut::kMaxClusterCps ? u.ncp : ut::kMaxClusterCps;
    unsigned key[ut::kMaxClusterCps];
    for (unsigned i = 0; i < n; ++i) key[i] = u.cps[i];
    if (Mode == 2) key[0] |= 0x80000000u;        // the override face's glyphs are their own (never the sheet's)
    GlyphSlot *s = FindSlot(*f, key, n, create);
    if (!s) return false;
    if (s->w < 0) {
        if (!create) return false;
        static unsigned char cell[512 * 64];
        const UniFont &font = UNI_FONTS[f->index];
        int w = Mode == 2 ? RenderRuntime(u, font, f->px, f->base, true, cell, sizeof(cell))
                          : RenderRuntime(u, font, font.px, font.top, false, cell, sizeof(cell));
        if (w < 0) { w = MissingBox(font, cell, sizeof(cell)); ++B200Unicode_Status.boxes; }
        else ++B200Unicode_Status.runtimeGlyphs;
        if (w < 0 || !PlaceGlyph(*f, s, cell, w)) { s->w = 0; }
    }
    Rect r = { s->x, s->y, s->x + s->w, s->y + f->lineHeight };
    out = r;
    return true;
}

static int WidthOf(FontRec *f, unsigned impl, const ut::Unit &u, const unsigned char *raw) {
    Rect r;
    if (!GlyphFor(f, impl, u, raw, true, r)) return 0;
    return r.r - r.l;
}

struct WidthCtx { FontRec *f; unsigned impl; const unsigned char *raw; };
static int CtxWidth(void *ctx, const ut::Unit &u) {
    WidthCtx *c = (WidthCtx *)ctx;
    if (u.ncp == 1 && u.cps[0] == 0x20 && u.size == 1 && c->raw[u.start] != ' ') {
        // the space a line break became (GetNextJustifiedLine measures it as ' ')
        static const unsigned char space[2] = { ' ', 0 };
        ut::Unit s = u;
        s.start = 0;
        return WidthOf(c->f, c->impl, s, space);
    }
    return WidthOf(c->f, c->impl, u, c->raw);
}

// ================================================================ drawing
static void BlitGlyph(void *window, SDL_Surface *surf, const Rect &g, int x, int y, unsigned color) {
    int rect[4] = { g.l, g.t, g.r, g.b };
    int cx = x, cy = y;
    if (!((ClipRectFn)SITE(CLIP_RECT))(window, rect, &cx, &cy)) return;
    if ((color >> 24) == 0xFF) {
        SDL_Rect s = { rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1] };
        SDL_Rect d = { cx, cy, s.w, s.h };
        ((UpperBlitFn)SITE(UPPER_BLIT))(surf, &s, *(SDL_Surface **)((unsigned)window + 0x30), &d);
    } else {
        float alpha = (float)(color >> 24) / 255.0f;
        ((BlitAlphaFn)SITE(BLIT_ALPHA))(window, surf, cx, cy, rect[0], rect[1], rect[2], rect[3], alpha, 1.0f, true);
    }
}

// Make every glyph a text needs before the game's tinted sheet is taken (a new glyph may remake the sheet).
static bool JustMapped(const ut::Unit &u, const unsigned char *raw, const ut::Unit **mapped);

static void Prepare(FontRec *f, unsigned impl, const unsigned char *text, unsigned limit) {
    ut::Units it;
    it.Init(text, ut::Length(text));
    ut::Unit u;
    Rect r;
    const ut::Unit *mapped;
    while (it.Next(u) && u.start + u.size <= limit)
        if (!u.IsNewline() && !JustMapped(u, text, &mapped)) GlyphFor(f, impl, u, text, true, r);
}

static unsigned FontOf(void *window, void *font) {
    if (!font) font = *(void **)((unsigned)window + 0x5C);
    return font ? *(unsigned *)((unsigned)font + 4) : 0;
}

// ldwGameWindowImpl::DrawString(text, x, y, colour, font) per character.
static void __fastcall UniDrawString(void *window, void *, const char *text, int x, int y, unsigned color, void *font) {
    unsigned impl = FontOf(window, font);
    if (!impl || !IMPL_FIELD(impl, 0x0C) || !text) return;
    const unsigned char *raw = (const unsigned char *)text;
    if ((color >> 24) == 0) color = *(const unsigned *)SITE(WHITE);
    FontRec *f = Ensure(impl);
    Prepare(f, impl, raw, 0xFFFFFFFF);
    SDL_Surface *surf = ((GetImageFn)SITE(GET_IMAGE))((void *)impl, color);
    if (!surf) return;
    int kern = IMPL_FIELD(impl, 0x08), x0 = x;
    ut::Units it;
    it.Init(raw, ut::Length(raw));
    ut::Unit u;
    while (it.Next(u)) {
        if (u.IsNewline()) { y += IMPL_FIELD(impl, 0x04); x = x0; continue; }
        Rect g;
        if (!GlyphFor(f, impl, u, raw, false, g)) continue;
        int w = g.r - g.l;
        if (!w) continue;
        BlitGlyph(window, surf, g, x, y, color);
        x += w + kern;
    }
}

struct JustState { bool active; unsigned impl; unsigned count; ut::Unit units[128]; const unsigned char *raw; };
static JustState Just;

// Inside DrawStringJustified's call (the only stock caller of DrawChars, which it calls on a literal " " to measure a
// space), a byte 80h..FFh of the mapped copy is the character it stands for.
static bool JustMapped(const ut::Unit &u, const unsigned char *raw, const ut::Unit **mapped) {
    if (!Just.active || u.size != 1 || raw[u.start] < 0x80 || raw[u.start] - 0x80u >= Just.count) return false;
    *mapped = &Just.units[raw[u.start] - 0x80];
    return true;
}

// ldwGameWindowImpl::DrawChars(text, count, x, y, measureOnly, colour, font): at most `count` bytes, never part of a
// character; returns how far x moved.
static int __fastcall UniDrawChars(void *window, void *, const char *text, int count, int x, int y, int measureOnly,
                                   unsigned color, void *font) {
    unsigned impl = FontOf(window, font);
    if (!impl || !IMPL_FIELD(impl, 0x0C) || !text) return 0;
    const unsigned char *raw = (const unsigned char *)text;
    if ((color >> 24) == 0) color = *(const unsigned *)SITE(WHITE);
    FontRec *f = Ensure(impl);
    Prepare(f, impl, raw, count > 0 ? (unsigned)count : 0);
    SDL_Surface *surf = ((GetImageFn)SITE(GET_IMAGE))((void *)impl, color);
    if (!surf) return 0;
    int kern = IMPL_FIELD(impl, 0x08), x0 = x;
    unsigned used = 0;
    ut::Units it;
    it.Init(raw, ut::Length(raw));
    ut::Unit u;
    while (it.Next(u)) {
        if ((int)(used + u.size) > count) break;
        used += u.size;
        if (u.IsNewline()) { y += IMPL_FIELD(impl, 0x04); x = x0; continue; }
        Rect g;
        const ut::Unit *mapped = 0;
        bool ok = JustMapped(u, raw, &mapped) ? GlyphFor(f, impl, *mapped, Just.raw, false, g)
                                               : GlyphFor(f, impl, u, raw, false, g);
        if (!ok) continue;
        int w = g.r - g.l;
        if (!w) continue;
        if (!(measureOnly & 0xFF)) BlitGlyph(window, surf, g, x, y, color);
        x += w + kern;
    }
    return x - x0;
}

// ldwFont::GetWidth(text, scale)
static int __fastcall UniGetWidth(void *font, void *, const char *text, float scale) {
    unsigned impl = *(unsigned *)((unsigned)font + 4);
    if (!impl || !IMPL_FIELD(impl, 0x0C) || !text) return 0;
    WidthCtx c = { Ensure(impl), impl, (const unsigned char *)text };
    return ut::GetWidth((const unsigned char *)text, scale, IMPL_FIELD(impl, 0x08), &CtxWidth, &c);
}

static ut::LineState LineScratch;

// ldwFont::GetNextJustifiedLine(src, out, maxChars, maxWidth, bool &doubleBreak, keepNewline, scale)
static const char *__fastcall UniNextLine(void *font, void *, const char *src, char *out, int maxChars, int maxWidth,
                                          bool *doubleBreak, int keep, float scale) {
    unsigned impl = *(unsigned *)((unsigned)font + 4);
    if (!impl || !IMPL_FIELD(impl, 0x0C)) return 0;
    WidthCtx c = { Ensure(impl), impl, (const unsigned char *)src };
    bool dbl = false;
    unsigned used = ut::NextLine((const unsigned char *)src, (unsigned char *)out, maxChars, maxWidth, &dbl,
                                 (keep & 0xFF) != 0, scale, IMPL_FIELD(impl, 0x08), &CtxWidth, &c, LineScratch);
    *doubleBreak = dbl;
    return src + used;
}

// ---------------------------------------------------------------- DrawStringJustified: one byte per character

static void __fastcall UniCharRect(void *impl, void *, int ch, int *rect) {
    if (ch < 0x100) {
        unsigned b = ch < 0 ? (unsigned)(ch & 0xFF) : (unsigned)ch;
        FontRec *f = Find((unsigned)impl);
        Rect g;
        if (Just.active && Just.impl == (unsigned)impl && b >= 0x80 && b - 0x80 < Just.count && f &&
            GlyphFor(f, (unsigned)impl, Just.units[b - 0x80], Just.raw, false, g)) {
            rect[0] = g.l; rect[1] = g.t; rect[2] = g.r; rect[3] = g.b;
            return;
        }
        if (Just.active && Mode == 2 && f && b < 0x80 && b != 0x0A) {
            ut::Unit u;
            u.start = 0; u.size = 1; u.ncp = 1; u.cps[0] = b;
            static unsigned char one[1];
            one[0] = (unsigned char)b;
            if (GlyphFor(f, (unsigned)impl, u, one, false, g)) {
                rect[0] = g.l; rect[1] = g.t; rect[2] = g.r; rect[3] = g.b;
                return;
            }
        }
    }
    ((CharRectFn)SITE(CHAR_RECT))(impl, ch, rect);
}

static int __fastcall UniDrawJustified(void *self, void *, const char *text, int x, int y, int width, unsigned color,
                                       void *font, int b1, int b2, int extra) {
    JustifiedFn stock = (JustifiedFn)(void *)JustifiedTrampoline;
    if (!text) return stock(self, 0, text, x, y, width, color, font, b1, b2, extra);
    const unsigned char *raw = (const unsigned char *)text;
    unsigned n = ut::Length(raw);
    bool ascii = true;
    for (unsigned i = 0; i < n && ascii; ++i) if (raw[i] >= 0x80) ascii = false;
    void *window = *(void **)self;
    unsigned impl = FontOf(window, font);
    if ((ascii && Mode != 2) || !impl || !IMPL_FIELD(impl, 0x0C)) return stock(self, 0, text, x, y, width, color, font, b1, b2, extra);
    FontRec *f = Ensure(impl);
    if (!f || f->index < 0) return stock(self, 0, text, x, y, width, color, font, b1, b2, extra);
    unsigned char *copy = (unsigned char *)Alloc(n + 1);
    if (!copy) return stock(self, 0, text, x, y, width, color, font, b1, b2, extra);
    JustState saved = Just;
    Just.active = false;
    Just.impl = impl;
    Just.count = 0;
    Just.raw = raw;
    ut::Units it;
    it.Init(raw, n);
    ut::Unit u;
    unsigned k = 0;
    Rect g;
    while (it.Next(u)) {
        if (u.IsNewline() || (u.size == 1 && raw[u.start] < 0x80)) {
            copy[k++] = raw[u.start];
            if (Mode == 2 && !u.IsNewline()) GlyphFor(f, impl, u, raw, true, g);
            continue;
        }
        unsigned slot = 0xFFFFFFFF;
        for (unsigned j = 0; j < Just.count && slot == 0xFFFFFFFF; ++j) {
            const ut::Unit &v = Just.units[j];
            if (v.ncp != u.ncp) continue;
            unsigned i = 0;
            while (i < u.ncp && i < ut::kMaxClusterCps && v.cps[i] == u.cps[i]) ++i;
            if (i == u.ncp || i == ut::kMaxClusterCps) slot = j;
        }
        if (slot == 0xFFFFFFFF && Just.count < 128) { slot = Just.count; Just.units[Just.count++] = u; }
        if (slot == 0xFFFFFFFF) slot = 127;          // more than 128 different characters: the last one's glyph
        GlyphFor(f, impl, Just.units[slot], raw, true, g);
        copy[k++] = (unsigned char)(0x80 + slot);
    }
    copy[k] = 0;
    Just.active = true;
    int r = stock(self, 0, (const char *)copy, x, y, width, color, font, b1, b2, extra);
    Just = saved;
    Release(copy);
    return r;
}

// ================================================================ typing
static bool __fastcall UniHandleKey(void *ctl, void *, int type, int code, int sym) {
    unsigned c = (unsigned)ctl;
    bool editing = *(unsigned char *)(c + 0x25) && *(unsigned *)(c + 0x1C) && *(unsigned char *)(*(unsigned *)(c + 0x1C) + 8);
    if (type == UNI_KEY_TYPE_CHARACTER && editing && !*(unsigned char *)(c + 0x2F) &&
        (((unsigned)code & UNI_KEY_MARK) || sym == 8)) {
        char *buf = *(char **)(c + 0x30);
        int max = *(int *)(c + 0x28);
        if (!buf || max <= 0) return true;
        static unsigned cps[1300];
        static unsigned char next[1300];
        unsigned n = ut::Length((const unsigned char *)buf);
        unsigned count = ut::Decode((const unsigned char *)buf, n, cps, 1290);
        if (sym == 8 && !((unsigned)code & UNI_KEY_MARK)) {
            if (!count) return true;
            unsigned start = 0, last = 0;
            while (start < count) { last = start; start = ut::ClusterEnd(cps, count, start); }
            count = last;
        } else {
            unsigned cp = (unsigned)code & 0x1FFFFF;
            if (*(unsigned char *)(c + 0x2D)) return true;              // a number-only box
            if (cp < 0x20 || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) return true;
            cps[count++] = cp;
        }
        int k = ut::Encode(cps, count, next, (unsigned)max < sizeof(next) ? (unsigned)max : sizeof(next) - 1);
        if (k < 0) { ++B200Unicode_Status.refused; return true; }
        for (int i = 0; i < k; ++i) buf[i] = (char)next[i];
        buf[k] = 0;
        if (sym != 8) ++B200Unicode_Status.typed;
        void *events = ((EventsGetFn)SITE(EVENTS_GET))();
        ((PostMessageFn)SITE(POST_MESSAGE))(events, 0x0C, *(long *)(c + 4));
        return true;
    }
    return ((HandleKeyFn)SITE(TEXT_HANDLE_KEY))(ctl, type, code, sym);
}

// ldwTextControl::GetText(buffer, size): the text cut to size - 1 bytes at a character, the rest zeros.
static void __fastcall UniGetText(void *ctl, void *, char *dst, int size) {
    unsigned impl = *(unsigned *)((unsigned)ctl + 0x10);
    const char *src = impl ? *(const char **)(impl + 0x30) : 0;
    if (!dst || size <= 0) return;
    for (int i = 0; i < size; ++i) dst[i] = 0;
    if (!src) return;
    static unsigned cps[1300];
    static unsigned char cut[1300];
    unsigned n = ut::Length((const unsigned char *)src);
    unsigned room = (unsigned)size - 1 < sizeof(cut) ? (unsigned)size - 1 : sizeof(cut);
    unsigned k = ut::Fit((const unsigned char *)src, n, room, cut, cps, 1290);     // cut also holds failed tries
    for (unsigned i = 0; i < k; ++i) dst[i] = (char)cut[i];
    if (k < n) ++B200Unicode_Status.fittedCuts;
}

static int __cdecl UniPollEvent(void *event) {
    int r = RealPoll(event);
    if (!r || !event || *(unsigned *)event != UNI_SDL_TEXTINPUT) return r;
    const unsigned char *text = (const unsigned char *)event + UNI_TEXT_FIELD;
    unsigned n = 0;
    while (n < 32 && text[n]) ++n;
    if (n == 1 && text[0] < 0x80) return r;                             // one ASCII key: the stock path
    unsigned cps[32];
    unsigned count = ut::IsUtf8(text, n) ? ut::Decode(text, n, cps, 32) : 0;
    if (!count && n) count = ut::Decode(text, n, cps, 32);
    void *events = ((EventsGetFn)SITE(EVENTS_GET))();
    for (unsigned i = 0; i < count; ++i) {
        if (cps[i] < 0x80) ((EventsHandleKeyFn)SITE(EVENTS_HANDLE_KEY))(events, UNI_KEY_TYPE_CHARACTER, 0, (int)cps[i]);
        else ((EventsHandleKeyFn)SITE(EVENTS_HANDLE_KEY))(events, UNI_KEY_TYPE_CHARACTER, (int)(cps[i] | UNI_KEY_MARK), 0);
    }
    *(unsigned *)event = UNI_SDL_HIDDEN_EVENT;                          // the stock code would drop it anyway
    return r;
}

// ================================================================ plan and install
static const unsigned kMaxWrites = 10;
struct HookWrite { unsigned va, len; bool data; unsigned char bytes[12], original[12]; };
struct Plan { HookWrite writes[kMaxWrites]; unsigned count; bool ok; };

static void PlanJump(Plan &p, unsigned va, const void *to, unsigned len) {
    if (!p.ok || p.count >= kMaxWrites || len < 5 || len > 12) { p.ok = false; return; }
    HookWrite &w = p.writes[p.count++];
    w.va = va; w.len = len; w.data = false;
    w.bytes[0] = 0xE9;
    *(int *)(w.bytes + 1) = (int)((unsigned)to - (va + 5));
    for (unsigned i = 5; i < len; ++i) w.bytes[i] = 0x90;
}

static void PlanSlot(Plan &p, unsigned va, const void *to) {
    if (!p.ok || p.count >= kMaxWrites) { p.ok = false; return; }
    HookWrite &w = p.writes[p.count++];
    w.va = va; w.len = 4; w.data = true;
    *(unsigned *)w.bytes = (unsigned)to;
}

static int BuildPlan(unsigned mode, Plan &plan) {
    plan.count = 0;
    plan.ok = true;
    if (mode != 1 && mode != 2) return 0;
    if (!Resolve()) return -1;
    // the trampoline: DrawStringJustified's first 9 bytes, then a jump back after them
    for (unsigned i = 0; i < UNI_JUSTIFIED_STEAL; ++i) JustifiedTrampoline[i] = ((const unsigned char *)SITE(DRAW_JUSTIFIED))[i];
    JustifiedTrampoline[UNI_JUSTIFIED_STEAL] = 0xE9;
    *(int *)(JustifiedTrampoline + UNI_JUSTIFIED_STEAL + 1) =
        (int)((SITE(DRAW_JUSTIFIED) + UNI_JUSTIFIED_STEAL) - ((unsigned)JustifiedTrampoline + UNI_JUSTIFIED_STEAL + 5));
    PlanJump(plan, SITE(DRAW_STRING), (const void *)&UniDrawString, 5);
    PlanJump(plan, SITE(DRAW_CHARS), (const void *)&UniDrawChars, 5);
    PlanJump(plan, SITE(GET_WIDTH), (const void *)&UniGetWidth, 5);
    PlanJump(plan, SITE(NEXT_LINE), (const void *)&UniNextLine, 5);
    PlanJump(plan, SITE(GET_TEXT), (const void *)&UniGetText, 5);
    PlanJump(plan, SITE(DRAW_JUSTIFIED), (const void *)&UniDrawJustified, UNI_JUSTIFIED_STEAL);
    PlanSlot(plan, FontVtable + 4 * UNI_FONT_VSLOT_CHAR_RECT, (const void *)&UniCharRect);
    PlanSlot(plan, TextVtable + 4 * UNI_TEXT_VSLOT_HANDLE_KEY, (const void *)&UniHandleKey);
    PlanSlot(plan, PollSlot, (const void *)&UniPollEvent);
    return plan.ok ? 1 : -1;
}

static bool WriteCode(unsigned va, const unsigned char *bytes, unsigned len, bool data) {
    DWORD old = 0;
    if (!VirtualProtect((void *)va, len, data ? PAGE_READWRITE : PAGE_EXECUTE_READWRITE, &old)) return false;
    for (unsigned i = 0; i < len; ++i) ((volatile unsigned char *)va)[i] = bytes[i];
    DWORD ignored = 0;
    BOOL restored = VirtualProtect((void *)va, len, old, &ignored);
    FlushInstructionCache(GetCurrentProcess(), (void *)va, len);
    return restored != FALSE;
}

static bool Apply(Plan &plan) {
    DWORD old = 0;
    if (!VirtualProtect(JustifiedTrampoline, sizeof(JustifiedTrampoline), PAGE_EXECUTE_READWRITE, &old)) return false;
    RealPoll = *(PollEventFn *)PollSlot;
    if (!RealPoll) return false;
    for (unsigned i = 0; i < plan.count; ++i) {
        HookWrite &w = plan.writes[i];
        for (unsigned j = 0; j < w.len; ++j) w.original[j] = ((const unsigned char *)w.va)[j];
        if (!WriteCode(w.va, w.bytes, w.len, w.data)) {
            Log("a write failed; restoring the earlier writes");
            for (unsigned j = 0; j < i; ++j) WriteCode(plan.writes[j].va, plan.writes[j].original, plan.writes[j].len, plan.writes[j].data);
            WriteCode(w.va, w.original, w.len, w.data);
            B200Unicode_Status.writeMask = 0;
            return false;
        }
        B200Unicode_Status.writeMask |= 1u << i;
    }
    return true;
}

// [Patches] Mode=1 (Render Unicode with In-Game Fonts) or 2 (Use Unicode Font); [Font] Face=<a Windows font
// name>, File=<a .ttf/.otf in "Unicode Text\" beside the DLL, added for this game only>.
// The two settings are exclusive and each installs its own ini: vf2unicodefont.ini (Mode=2) with Use Unicode Font,
// vf2unicode.ini (Mode=1) with Render Unicode with In-Game Fonts.
// The font chosen with the patcher's Unicode Font tool (src/vf2_unicode_font.py) is "Unicode Font\Unicode Font.ini"
// [UnicodeFont] Face=, File=<a .ttf/.otf/.ttc copied into "Unicode Font\">; it wins over [Font] when it names a face.
static unsigned ReadSettings() {
    wchar_t path[MAX_PATH];
    unsigned mode = 0;
    if (InFolder(L"vf2unicodefont.ini", path) && GetPrivateProfileIntW(L"Patches", L"Mode", 0, path) == 2) mode = 2;
    else if (InFolder(L"vf2unicode.ini", path)) mode = GetPrivateProfileIntW(L"Patches", L"Mode", 0, path) == 1 ? 1u : 0u;
    OverrideFace[0] = 0;
    if (mode == 2) {
        wchar_t choice[MAX_PATH];
        if (InFolder(L"Unicode Font\\Unicode Font.ini", choice)
                && GetPrivateProfileStringW(L"UnicodeFont", L"Face", L"", OverrideFace, LF_FACESIZE, choice)
                && OverrideFace[0]) {
            wchar_t file[MAX_PATH], rel[MAX_PATH] = L"Unicode Font\\", full[MAX_PATH];
            if (GetPrivateProfileStringW(L"UnicodeFont", L"File", L"", file, MAX_PATH, choice) && file[0]) {
                bool plain = true;
                for (unsigned i = 0; file[i]; ++i) if (file[i] == L'\\' || file[i] == L'/' || file[i] == L':') plain = false;
                if (plain && lstrlenW(rel) + lstrlenW(file) < MAX_PATH - 1) {
                    lstrcatW(rel, file);
                    if (InFolder(rel, full)) AddFontResourceExW(full, FR_PRIVATE, 0);
                }
            }
            return mode;
        }
        GetPrivateProfileStringW(L"Font", L"Face", L"Segoe UI", OverrideFace, LF_FACESIZE, path);
        wchar_t file[MAX_PATH], rel[MAX_PATH] = L"Unicode Text\\", full[MAX_PATH];
        if (GetPrivateProfileStringW(L"Font", L"File", L"", file, MAX_PATH, path) && file[0]) {
            bool plain = true;
            for (unsigned i = 0; file[i]; ++i) if (file[i] == L'\\' || file[i] == L'/' || file[i] == L':') plain = false;
            if (plain && lstrlenW(rel) + lstrlenW(file) < MAX_PATH - 1) {
                lstrcatW(rel, file);
                if (InFolder(rel, full)) AddFontResourceExW(full, FR_PRIVATE, 0);
            }
        }
    }
    return mode;
}

extern "C" __declspec(dllexport) void __cdecl B200Unicode_Startup() {
    static bool started = false;
    if (started) return;
    started = true;
    DWORD n = GetModuleFileNameW(ThisModule, Folder, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    unsigned cut = n;
    while (cut > 0 && Folder[cut - 1] != L'\\') --cut;
    if (!cut) return;
    Folder[cut] = 0;
    Log("vf2unicode_b200 started");
    Mode = ReadSettings();
    B200Unicode_Status.mode = Mode;
    if (Mode != 1 && Mode != 2) { Log("Unicode text is off: the game is stock"); return; }
    if (!LoadSdl()) { Log("SDL2.dll's functions were not found: installing nothing"); return; }
    static Plan plan;
    int built = BuildPlan(Mode, plan);
    if (built < 0) { Log("the executable could not be proved: installing nothing"); return; }
    B200Unicode_Status.resolved = 1;
    if (Apply(plan)) {
        B200Unicode_Status.installed = 1;
        Log(Mode == 2 ? "Use Unicode Font installed" : "Render Unicode with In-Game Fonts installed");
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        ThisModule = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}

#ifdef B200UNICODE_TEST
extern "C" __declspec(dllexport) unsigned __cdecl B200Unicode_TestScanAddress() { return (unsigned)&ScanPattern; }
extern "C" __declspec(dllexport) unsigned __cdecl B200Unicode_TestNextDwordAddress() { return (unsigned)&NextDword; }
extern "C" __declspec(dllexport) void __cdecl B200Unicode_TestSetModule(unsigned module) { ThisModule = (HMODULE)module; }
// out: [status, count, then per write: va, len, data, bytes 0..3, bytes 4..7]
extern "C" __declspec(dllexport) int __cdecl B200Unicode_TestPlan(int mode, unsigned *out) {
    static Plan plan;
    Mode = (unsigned)mode;
    int built = BuildPlan((unsigned)mode, plan);
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
extern "C" __declspec(dllexport) void __cdecl B200Unicode_TestSites(unsigned *out) {
    for (unsigned i = 0; i < UNI_SITE_COUNT; ++i) out[i] = Sites[i];
    out[UNI_SITE_COUNT] = FontVtable;
    out[UNI_SITE_COUNT + 1] = TextVtable;
    out[UNI_SITE_COUNT + 2] = PollSlot;
}
// the settings as Startup reads them, from `folder` (with its trailing backslash): the mode
extern "C" __declspec(dllexport) unsigned __cdecl B200Unicode_TestReadSettings(const wchar_t *folder) {
    unsigned n = 0;
    while (folder[n] && n + 1 < MAX_PATH) { Folder[n] = folder[n]; ++n; }
    Folder[n] = 0;
    Mode = ReadSettings();
    return Mode;
}
// SDL2.dll / SDL2_image.dll' functions, as Startup finds them
extern "C" __declspec(dllexport) int __cdecl B200Unicode_TestLoadSdl() { return LoadSdl() ? 1 : 0; }
// the real SDL_PollEvent the hook calls (Apply sets it from the import slot)
extern "C" __declspec(dllexport) void __cdecl B200Unicode_TestSetPoll(unsigned fn) { RealPoll = (PollEventFn)fn; }
// the hooks' own addresses, so a test can call them under the emulator
extern "C" __declspec(dllexport) void __cdecl B200Unicode_TestHooks(unsigned *out) {
    out[0] = (unsigned)&UniDrawString; out[1] = (unsigned)&UniDrawChars; out[2] = (unsigned)&UniGetWidth;
    out[3] = (unsigned)&UniNextLine; out[4] = (unsigned)&UniGetText; out[5] = (unsigned)&UniDrawJustified;
    out[6] = (unsigned)&UniCharRect; out[7] = (unsigned)&UniHandleKey; out[8] = (unsigned)&UniPollEvent;
}
#endif
