/* ----------------------------------------------------------------- nothing runs off the screen (b200tr_screen.inc)
   (included by b200tr.c; runtime/native/b200unicode/b200screen.inc is the same rule inside the Unicode text DLL, which
   does it itself; src/vf2_screen_edge.py is the model; tests/test_screen_edge.py). VF1's native/vf1tr/screen_tr.inc.

   The owner, 2026-11-03: "i dont care if things run out of boxes, they just need to not run off the screen". With a
   translation installed and neither Unicode text DLL installed, a text the game draws (DrawString: every left,
   right-aligned and centred draw and every text box) or wraps (DrawStringJustified: dialogs, events, the store) that
   would leave the screen, but is partly on it, is moved so that it ends at the screen's edge; one wider than the
   screen is cut, each line, to its longest start that fits with "..." (the stock fonts have no "..." letter of their
   own); one taller keeps the lines that fit, the last ending in "..."; when not even "..." fits, the English is shown.
   A text wholly off the screen is left as it is. The two functions are found by the Unicode text DLL's own pins
   (b200unicode_sites.h: whole stock functions, proved by runtime/tools/gen_b200_unicode_sites.py); their entries are
   written only when both hold their stock bytes. The stock code runs through two trampolines made
   PAGE_EXECUTE_READWRITE by make_trampoline before any entry is written (DEP). */

typedef struct UniPin UniPin;
typedef struct UniEvidence UniEvidence;
typedef struct UniFont UniFont;
typedef struct UniNameBox UniNameBox;
#include "../b200unicode/b200unicode_sites.h"

typedef void (__fastcall *TrDrawStringFn)(void *window, void *edx, const char *text, int x, int y, unsigned colour,
                                          void *font);
typedef int (__fastcall *TrJustifiedFn)(void *self, void *edx, const char *text, int x, int y, int width,
                                        unsigned colour, void *font, int b1, int b2, int extra);
typedef int (__fastcall *TrGetWidthFn)(void *font, void *edx, const char *text, float scale);
typedef const char *(__fastcall *TrNextLineFn)(void *font, void *edx, const char *src, char *out, int max_chars,
                                               int max_width, char *dbl, int keep, float scale);

static const unsigned char STOCK_DRAW_STRING[6] = { 0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x58 };   /* push ebp; mov ebp,esp; sub esp,58h */
static const unsigned char STOCK_JUSTIFIED[9] = { 0x55, 0x8B, 0xEC, 0x81, 0xEC, 0x50, 0x05, 0x00, 0x00 };
static unsigned char DrawStringTrampoline[16];
static unsigned char JustifiedTrampoline[16];
static unsigned edge_sites[4];                   /* DrawString, DrawStringJustified, GetWidth, GetNextJustifiedLine */
static int screen_edge = 0;                      /* the two jumps are in */

static int screen_size(void *window, int *w, int *h) {
    const int *surface = window != NULL ? *(const int **)((char *)window + 0x30) : NULL;   /* SDL_Surface */
    if (surface == NULL || surface[2] <= 0 || surface[3] <= 0) return 0;
    *w = surface[2];
    *h = surface[3];
    return 1;
}

static int text_width(void *font, const char *text) {
    return ((TrGetWidthFn)(UINT_PTR)edge_sites[2])(font, NULL, text, 1.0f);
}

static int line_height(void *font) {
    const char *impl = font != NULL ? *(const char **)((const char *)font + 4) : NULL;
    return impl != NULL ? *(const int *)(impl + 4) : 0;
}

/* A line (len bytes) fitted into room pixels into out: itself when it fits and no mark is wanted, else its longest
   start that fits with "..." (trailing spaces dropped); -1 when not even "..." fits. The text is Windows-1252, one
   byte a letter. tmp has room for len + 4 bytes. */
static int fit_line(void *font, const char *line, int len, int room, int mark, char *tmp, char *out) {
    int keep;
    bcopy_(tmp, line, len);
    tmp[len] = 0;
    if (!mark && text_width(font, tmp) <= room) { bcopy_(out, line, len); return len; }
    for (keep = len; keep >= 0; --keep) {
        int k = keep;
        while (k > 0 && line[k - 1] == ' ') --k;
        bcopy_(tmp, line, k);
        tmp[k] = '.'; tmp[k + 1] = '.'; tmp[k + 2] = '.'; tmp[k + 3] = 0;
        if (text_width(font, tmp) <= room) { bcopy_(out, tmp, k + 3); return k + 3; }
    }
    return -1;
}

/* text with each line no wider than room and at most max_lines lines, the last kept one ending in "..." when lines
   were dropped; on the heap (*owned); NULL when a line does not take even "...". */
static const char *cut_lines(void *font, const char *text, int room, int max_lines, char **owned) {
    int n = slen(text), m = 0, kept = 0, at = 0;
    char *out = (char *)tr_alloc((SIZE_T)n + 8), *tmp = (char *)tr_alloc((SIZE_T)n + 8);
    *owned = out;
    if (out == NULL || tmp == NULL) { if (tmp != NULL) HeapFree(GetProcessHeap(), 0, tmp); return text; }
    while (kept < max_lines) {
        int end = at, got;
        while (end < n && text[end] != '\n') ++end;
        if (kept) out[m++] = '\n';
        got = fit_line(font, text + at, end - at, room, kept + 1 == max_lines && end < n, tmp, out + m);
        if (got < 0) { HeapFree(GetProcessHeap(), 0, tmp); return NULL; }
        m += got;
        ++kept;
        if (end >= n) break;
        at = end + 1;
    }
    out[m] = 0;
    HeapFree(GetProcessHeap(), 0, tmp);
    return out;
}

static void __fastcall edge_draw_string(void *window, void *edx, const char *text, int x, int y, unsigned colour,
                                        void *font) {
    char *owned = NULL;
    void *f = font != NULL ? font : (window != NULL ? *(void **)((char *)window + 0x5C) : NULL);
    int sw, sh;
    (void)edx;
    if (text != NULL && *text && f != NULL && screen_size(window, &sw, &sh)) {
        int n = slen(text), k, lines = 1, width = text_width(f, text), line_h = line_height(f), h;
        for (k = 0; k < n; ++k) if (text[k] == '\n') ++lines;
        h = lines * line_h;
        if (!(x >= 0 && x + width <= sw && y >= 0 && y + h <= sh) && !(x >= sw || x + width <= 0 || y >= sh || y + h <= 0)) {
            int fit = line_h > 0 ? sh / line_h : lines;
            if (fit < 1) fit = 1;
            if (width > sw || lines > fit) {
                const char *cut = cut_lines(f, text, sw, fit, &owned);
                text = cut != NULL ? cut : B200Tr_EnglishOf(text);      /* not even "...": the English */
                width = text_width(f, text);
                lines = 1;
                for (k = 0; text[k]; ++k) if (text[k] == '\n') ++lines;
                h = lines * line_h;
            }
            if (x < 0 || width > sw) x = 0;
            else if (x + width > sw) x = sw - width;
            if (y < 0 || h > sh) y = 0;
            else if (y + h > sh) y = sh - h;
        }
    }
    ((TrDrawStringFn)(void *)DrawStringTrampoline)(window, NULL, text, x, y, colour, font);
    if (owned != NULL) HeapFree(GetProcessHeap(), 0, owned);
}

/* How tall the game wraps text in a box width wide: GetNextJustifiedLine over and over, times the line height. */
static int wrapped_height(void *font, const char *text, int width) {
    static char out[4096];
    const char *at = text;
    int lines = 0;
    while (*at && lines < 4096) {
        const char *next;
        char dbl = 0;
        while (*at == ' ') ++at;
        if (!*at) break;
        next = ((TrNextLineFn)(UINT_PTR)edge_sites[3])(font, NULL, at, out, 0x3FF, width, &dbl, 0, 1.0f);
        if (next == NULL || next <= at) break;
        ++lines;
        if (dbl) ++lines;
        at = next;
    }
    return lines * line_height(font);
}

static int __fastcall edge_justified(void *self, void *edx, const char *text, int x, int y, int width,
                                     unsigned colour, void *font, int b1, int b2, int extra) {
    void *window = self != NULL ? *(void **)self : NULL;
    void *f = font != NULL ? font : (window != NULL ? *(void **)((char *)window + 0x5C) : NULL);
    char *owned = NULL;
    int sw, sh, r;
    TrJustifiedFn stock = (TrJustifiedFn)(void *)JustifiedTrampoline;
    (void)edx;
    if (text != NULL && *text && f != NULL && width > 0 && screen_size(window, &sw, &sh)) {
        int h;
        if (width > sw) width = sw;                                  /* a box wider than the screen: the screen */
        h = wrapped_height(f, text, width);
        if (!(x >= 0 && x + width <= sw && y >= 0 && y + h <= sh) && !(x >= sw || x + width <= 0 || y >= sh || y + h <= 0)) {
            if (h > sh) {          /* taller than the screen: its longest start that wraps, with "...", into it */
                int n = slen(text), lo = 0, hi = n;
                char *out = (char *)tr_alloc((SIZE_T)n + 8);
                if (out != NULL) {
                    while (lo < hi) {
                        int mid = (lo + hi + 1) / 2, k = mid;
                        while (k > 0 && (text[k - 1] == ' ' || text[k - 1] == '\n')) --k;
                        bcopy_(out, text, k);
                        out[k] = '.'; out[k + 1] = '.'; out[k + 2] = '.'; out[k + 3] = 0;
                        if (wrapped_height(f, out, width) <= sh) lo = mid; else hi = mid - 1;
                    }
                    while (lo > 0 && (text[lo - 1] == ' ' || text[lo - 1] == '\n')) --lo;
                    bcopy_(out, text, lo);
                    out[lo] = '.'; out[lo + 1] = '.'; out[lo + 2] = '.'; out[lo + 3] = 0;
                    owned = out;
                    text = out;
                    h = wrapped_height(f, text, width);
                }
            }
            if (x < 0) x = 0;
            else if (x + width > sw) x = sw - width;
            if (y < 0 || h > sh) y = 0;
            else if (y + h > sh) y = sh - h;
        }
    }
    r = stock(self, NULL, text, x, y, width, colour, font, b1, b2, extra);
    if (owned != NULL) HeapFree(GetProcessHeap(), 0, owned);
    return r;
}

/* The four functions by the Unicode text DLL's pins, each exactly once in the executable's code. */
static int find_edge_sites(void) {
    static const int pins[4] = { UNI_PIN_DRAW_STRING, UNI_PIN_DRAW_JUSTIFIED, UNI_PIN_GET_WIDTH, UNI_PIN_NEXT_LINE };
    HMODULE exe = GetModuleHandleW(0);
    const IMAGE_NT_HEADERS32 *nt;
    const IMAGE_SECTION_HEADER *s;
    int p;
    unsigned i;
    if (exe == NULL) return 0;
    nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + ((const IMAGE_DOS_HEADER *)exe)->e_lfanew);
    s = IMAGE_FIRST_SECTION(nt);
    for (p = 0; p < 4; ++p) {
        const UniPin *pin = &UNI_PINS[pins[p]];
        unsigned hits = 0, at = 0;
        for (i = 0; i < nt->FileHeader.NumberOfSections && hits < 2; ++i) {
            unsigned size, h = 0, found;
            if (!(s[i].Characteristics & IMAGE_SCN_MEM_EXECUTE)) continue;
            size = s[i].Misc.VirtualSize ? s[i].Misc.VirtualSize : s[i].SizeOfRawData;
            if (s[i].SizeOfRawData < size) size = s[i].SizeOfRawData;
            found = ScanPattern((const unsigned char *)exe + s[i].VirtualAddress, size, pin->bytes, pin->mask,
                                pin->len, &h);
            if (h) { if (!hits) at = found; hits += h; }
        }
        if (hits != 1) return 0;
        edge_sites[p] = at;
    }
    return 1;
}

static int stock_bytes(unsigned at, const unsigned char *stock, int n) {
    int k;
    for (k = 0; k < n; ++k) if (((const unsigned char *)(UINT_PTR)at)[k] != stock[k]) return 0;
    return 1;
}

/* With a translation installed and no Unicode text DLL: the two jumps, all or nothing. */
static void install_screen_edge(void) {
    unsigned char *trampolines[2];
    unsigned char original[2][10];
    unsigned entries[2], hooks[2], steal[2];
    unsigned char jmp[5];
    int k;
    if (!installed || unicode_text_active() || !find_edge_sites()) return;
    if (!stock_bytes(edge_sites[0], STOCK_DRAW_STRING, 6) || !stock_bytes(edge_sites[1], STOCK_JUSTIFIED, 9)) return;
    trampolines[0] = DrawStringTrampoline; trampolines[1] = JustifiedTrampoline;
    entries[0] = edge_sites[0]; entries[1] = edge_sites[1];
    hooks[0] = (unsigned)(UINT_PTR)edge_draw_string; hooks[1] = (unsigned)(UINT_PTR)edge_justified;
    steal[0] = 6; steal[1] = 9;
    for (k = 0; k < 2; ++k)
        if (!make_trampoline(trampolines[k], entries[k], steal[k], original[k])) return;
    for (k = 0; k < 2; ++k) {
        unsigned rel = hooks[k] - (entries[k] + 5u);
        jmp[0] = 0xE9;
        jmp[1] = (unsigned char)rel; jmp[2] = (unsigned char)(rel >> 8);
        jmp[3] = (unsigned char)(rel >> 16); jmp[4] = (unsigned char)(rel >> 24);
        if (!write_code(entries[k], jmp, 5)) {
            if (k) write_code(entries[0], original[0], (int)steal[0]);
            return;
        }
    }
    screen_edge = 1;
    log_add("Translations: lines that would leave the screen are moved to its edge or cut\r\n");
}
