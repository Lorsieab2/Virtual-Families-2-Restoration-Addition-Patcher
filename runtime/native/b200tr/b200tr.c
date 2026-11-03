/* vf2tr_b200.dll -- Translations: the player's chosen translation in Virtual Families 2.

   WHAT.  The executable's loader (theGame::Init's first call) loads this DLL last, after the Unicode text DLLs, only
   while the Translations byte (.vf2trns) is 1, and calls B200Tr_Startup().  It reads the translation the patcher's
   Translations window chose ("<this DLL's folder>\Translation.ini": file=<the translation's full path>, else the copy
   "Translation.txt" beside it) and from then on the game shows it.  One feature, one DLL: nothing else is installed.

   HOW.  Every line of the game is a static record {id, key*, text*, override*} of one table (b200_translations_sites:
   the DLL holds no game address; it finds the table, its size and the index of records by id through pinned runs of
   theStringManager's constructor).  The game's own lookup, theStringManager::GetString, and its template filler
   GetStringFromNameGenderTemplate return the override when it is set, else the text: the game's own localisation
   hook (it fills overrides from an "sm.xml" that the game does not ship).  This DLL sets the override of each
   translated line to its translation.  No code of the game's lookup is changed.  theStringManager's constructor
   clears every override it did not fill itself, so the DLL calls theStringManager::Get() first: the manager exists
   (and its constructor has run) before the first override is set.

   ROOM.  b200tr_limits.h (gen_b200_translations_sites.py, from the code of the executables): a line the game strncpy's
   into a fixed field gets that field less its NUL; a line it sprintf's, strncat's or copies byte by byte gets its
   English length; every line at most TR_MAX_LINE.  A longer translation is refused (English stays).  Every copy
   whose line comes from data (an item, an event, a caller's table) is covered by a guard on the C runtime's strncpy
   and sprintf (their entries are replaced by a jmp to a guard here; the stolen instructions run from a trampoline
   made executable first).  strncpy(dst, src, n) never writes more than n bytes, but it leaves dst without its NUL when
   src is n bytes or longer: a translated line that is n bytes or longer where its English is shorter than n is cut
   at n - 1, so the copy ends with its NUL as the English copy does (a copy of the start of a longer English line, the
   template filler's, is left alone).  sprintf has no count: a translated format or argument gives a text cut to the
   length the English format and arguments give.  strncat takes its caller's count and needs no guard.

   PATCHES.  Lines keyed "patch/..." are the patches' own text: kept by their English and handed out when a patch's
   DLL asks (B200Tr_TextW / B200Tr_TextA), within their room.  B200Tr_English / B200Tr_EnglishOf give a DLL that
   writes a file another program reads (the Family History log) the English, so the file stays English while the game
   shows the translation.  The likes and dislikes lists are not part of VF2.

   PERCENT.  Only a line's own English placeholders are placeholders; any other '%' in a translation is plain text
   ("2 %", "50 % de reduction").  A line the game (B200TR_FORMAT) or a patch's DLL (B200TR_PATCH_FORMAT) uses as a
   printf FORMAT gets each such '%' as "%%" (tt_escape_percent), which counts toward its room; a line that reaches
   the guarded sprintf as its format without being one is handed an escaped copy there (row.out_fmt).

   No choice, "English (original)", a missing or unreadable file, a file for another game: nothing is changed.
   A bad line (a broken placeholder, a changed English, too long, a line that is never translated) shows English; the
   file's other lines still work.  Every problem goes to "Translations.log" beside the DLL (line numbers, never the
   text).

   TEXT.  The game draws bytes.  Without the Unicode settings the translation is written in Windows-1252 (Latin-1 and
   the usual quotes and dashes; any other letter as '?'); when the Unicode text DLL ("Render Unicode with In-Game
   Fonts" / "Use Unicode Font") has installed its hooks -- B200Unicode_UnicodeTextActive() is nonzero, or its status
   block says installed -- it is passed on as UTF-8, which they draw.  Ported from the Virtual Families 1 Fun
   Patcher's native/vf1tr (which was ported from the Fish and Plant Tycoon Fix Patcher's native/ftfp_translations). */
#include <windows.h>
#include "translation_text.h"
#include "b200tr_sites.h"
#include "b200tr_limits.h"
#include "b200tr_patch_formats.h"

EXTERN_C IMAGE_DOS_HEADER __ImageBase;

#define MAX_FILE (8 * 1024 * 1024)
#define LOG_LINES 40
#define TR_ABSOLUTE_MAX TR_MAX_LINE
#define ARENA_BYTES (4 * 1024 * 1024)
#define UNI_STATUS_MAGIC 0x54584E55u

static int slen(const char *s) { int n = 0; while (s[n]) ++n; return n; }
static int wlen(const wchar_t *s) { int n = 0; while (s[n]) ++n; return n; }
static void wcopy(wchar_t *to, const wchar_t *from) { while ((*to++ = *from++) != 0) {} }
static void wcat(wchar_t *to, const wchar_t *from) { wcopy(to + wlen(to), from); }
static void bcopy_(char *to, const char *from, int n) { int k; for (k = 0; k < n; ++k) to[k] = from[k]; }
static int bsame(const char *a, const char *b) { while (*a && *a == *b) { ++a; ++b; } return *a == *b; }
static int starts(tt_span line, const char *word) {
    int k;
    for (k = 0; word[k]; ++k) if (k >= line.n || tt_lower((unsigned char)line.s[k]) != word[k]) return 0;
    return 1;
}

typedef struct record { unsigned int id; const char *key; const char *text; const char *override; } record;

typedef struct row {
    int line;
    int id;
    const char *english;             /* UTF-8, from the file */
    int english_n;
    char *english_game;              /* the English as the game holds it (Windows-1252) */
    const char *translation;         /* UTF-8, choices still in */
    int translation_n;
    char *out;                       /* the translation as the game gets it */
    record *rec;
    int patch;                       /* a "patch/..." line: text a patch adds, found by its English */
    int size;                        /* measure() of the translation, in UTF-8 bytes */
    int has_conv;                    /* the English has a printf conversion */
    int is_format;                   /* the program uses it as a printf format: plain '%' written "%%" */
    char *out_fmt;                   /* not a format but has a plain '%': `out` with every '%' as "%%" (guard_sprintf) */
    char *utf8;                      /* the translation rendered as UTF-8 */
    wchar_t *wide;                   /* ... and as UTF-16, made on first use */
    struct row *next;                /* the next patch line in its hash bucket */
} row;

#define PATCH_BUCKETS 1024
#define PATCH_WIDE_MIN 80
#define PATCH_WIDE_MAX 600
static row *patch_bucket[PATCH_BUCKETS];
static int patch_used = 0;

static int installed = 0;
static int text_mode = 0;            /* 0 Windows-1252, 1 UTF-8 */
static int plural_rule = TT_EN;
static row *rows = NULL;
static int row_count = 0;
static row **by_id = NULL;           /* [max_id], the game's lines that are translated */
static int used = 0, refused = 0, guarded = 0;
static wchar_t folder[1024];
static char file_label[200];
static char log_text[4096];
static int log_at = 0;
static char head_text[1024];
static int head_at = 0;
static int log_lines = 0;

/* the game, found by its pinned runs */
static unsigned sites[TR_PIN_COUNT];
static unsigned tab_table, tab_count, tab_index, tab_max_id;
static unsigned image_low, image_high;

/* status block (layout version 1): magic 'T2TR', version, requested, resolved, installed, used, refused, guarded,
   textMode, patchLines */
struct TrStatus { unsigned magic, version, requested, resolved, installed, used, refused, guarded, textMode, patchLines; };
__declspec(dllexport) volatile struct TrStatus B200Tr_Status = { TR_STATUS_MAGIC, 1u, 0, 0, 0, 0, 0, 0, 0, 0 };

/* ----------------------------------------------------------------- memory and the log */

static void *tr_alloc(SIZE_T n) { return HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, n == 0 ? 1 : n); }

/* Every string the game is handed (`out`, `utf8`, the escaped copies) lives in one arena, so a pointer is known to be
   one of ours by a range test. */
static char *arena = NULL;
static unsigned arena_at = 0;

static char *arena_alloc(SIZE_T n) {
    char *p;
    if (arena == NULL) {
        arena = (char *)VirtualAlloc(NULL, ARENA_BYTES, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (arena == NULL) return NULL;
    }
    n = (n + 7u) & ~7u;
    if (arena_at + n > ARENA_BYTES) return NULL;
    p = arena + arena_at;
    arena_at += (unsigned)n;
    return p;
}

static int in_arena(const void *p) {
    return arena != NULL && (const char *)p >= arena && (const char *)p < arena + arena_at;
}

static void log_add(const char *text) {
    while (*text && log_at < (int)sizeof log_text - 1) log_text[log_at++] = *text++;
    log_text[log_at] = 0;
}

static void head_add(const char *text) {
    while (*text && head_at < (int)sizeof head_text - 1) head_text[head_at++] = *text++;
    head_text[head_at] = 0;
}

static const char *number(int v) {
    static char digits[16];
    int at = 15;
    unsigned int u = v < 0 ? 0u : (unsigned int)v;
    digits[15] = 0;
    do { digits[--at] = (char)('0' + u % 10u); u /= 10u; } while (u && at > 0);
    return digits + at;
}

static void log_refused(int line, const char *why) {
    ++refused;
    if (++log_lines > LOG_LINES) return;
    log_add("  line ");
    log_add(number(line));
    log_add(": ");
    log_add(why);
    log_add(" (shows English)\r\n");
}

static void write_log(void) {
    static const char bom[] = "\xEF\xBB\xBF";
    wchar_t path[1100];
    HANDLE file;
    DWORD written;
    if (folder[0] == 0 || wlen(folder) > 1000) return;
    wcopy(path, folder);
    wcat(path, L"Translations.log");
    file = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return;
    WriteFile(file, bom, 3, &written, NULL);
    WriteFile(file, head_text, (DWORD)head_at, &written, NULL);
    WriteFile(file, log_text, (DWORD)log_at, &written, NULL);
    CloseHandle(file);
}

/* ----------------------------------------------------------------- files */

static unsigned char *read_file(const wchar_t *path, int *size) {
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD low, high = 0, got = 0;
    unsigned char *data;
    if (file == INVALID_HANDLE_VALUE) return NULL;
    low = GetFileSize(file, &high);
    if (low == INVALID_FILE_SIZE || high != 0 || low > MAX_FILE) { CloseHandle(file); return NULL; }
    data = (unsigned char *)tr_alloc(low + 4);
    if (data == NULL || (low > 0 && (!ReadFile(file, data, low, &got, NULL) || got != low))) {
        CloseHandle(file);
        return NULL;
    }
    CloseHandle(file);
    *size = (int)low;
    return data;
}

static int utf8_to_wide(const char *s, int n, wchar_t *out, int cap) {
    tt_out o;
    int i = 0;
    o.buf = (char *)out;
    o.cap = cap;
    o.mode = 2;
    o.at = 0;
    o.overflow = 0;
    while (i < n) tt_put_cp(&o, tt_next_cp(s, n, &i));
    if (o.overflow || o.at >= cap) return 0;
    out[o.at] = 0;
    return 1;
}

/* "<folder>\Translation.ini": the chosen file (file=...).  The translation's bytes, or NULL for English. */
static unsigned char *chosen_file(int *size) {
    wchar_t path[1100];
    int n = 0, i = 0;
    unsigned char *ini, *data = NULL;
    char *text;
    int text_n;
    wcopy(path, folder);
    wcat(path, L"Translation.ini");
    ini = read_file(path, &n);
    if (ini == NULL) { log_add("Translations: no translation chosen (English)\r\n"); return NULL; }
    text = (char *)tr_alloc((SIZE_T)n * 2 + 16);
    text_n = text != NULL ? tt_decode(ini, n, text, n * 2 + 16) : -1;
    if (text_n < 0) { log_add("Translations: Translation.ini is not UTF-8 (English)\r\n"); return NULL; }
    while (i < text_n) {
        int start = i, end;
        tt_span line, value;
        while (i < text_n && text[i] != '\n' && text[i] != '\r') ++i;
        end = i;
        while (i < text_n && (text[i] == '\n' || text[i] == '\r')) ++i;
        line.s = text + start;
        line.n = end - start;
        line = tt_strip(line);
        if (line.n > 5 && starts(line, "file=")) {
            value.s = line.s + 5;
            value.n = line.n - 5;
            value = tt_strip(value);
            if (value.n > 0 && utf8_to_wide(value.s, value.n, path, 1060)) {
                int k = value.n, j;
                data = read_file(path, size);
                while (k > 0 && value.s[k - 1] != '\\' && value.s[k - 1] != '/') --k;
                for (j = 0; k < value.n && j < (int)sizeof file_label - 1; ++j, ++k) file_label[j] = value.s[k];
                file_label[j] = 0;
            }
        }
    }
    if (data == NULL && file_label[0] != 0) {
        wcopy(path, folder);
        wcat(path, L"Translation.txt");
        data = read_file(path, size);
        if (data != NULL) log_add("Translations: the chosen file was not found; using the copy Translation.txt\r\n");
    }
    if (data == NULL && file_label[0] != 0) log_add("Translations: the chosen file could not be read (English)\r\n");
    if (file_label[0] == 0) log_add("Translations: English (original)\r\n");
    return data;
}

/* ----------------------------------------------------------------- the game's lines */

static int is_text(const void *p) { return (unsigned int)(UINT_PTR)p >= image_low && (unsigned int)(UINT_PTR)p < image_high; }

/* The record of a string id, found as the game's own lookup finds it: through the index its constructor builds. */
static record *record_of(int id) {
    record *r;
    if (id < 1 || (unsigned)id >= tab_max_id) return NULL;
    r = *(record **)(UINT_PTR)(tab_index + 4u * (unsigned)id);
    if (r == NULL || (int)r->id != id) return NULL;
    if (!is_text(r->key) || !is_text(r->text) || r->key[0] != 'e') return NULL;
    return r;
}

static int in_list(const unsigned short *list, int id) {
    int k;
    for (k = 0; list[k] != 0; ++k) if (list[k] == id) return 1;
    return 0;
}

/* The most a line may hold, in UTF-8 bytes (src/vf2_translation_strings.room). */
static int room(int id, int english_bytes) {
    int best = TR_MAX_LINE, k;
    for (k = 0; B200TR_STRNCPY_ROOM[k].id != 0; ++k) {
        if (B200TR_STRNCPY_ROOM[k].id == id) {
            int r = B200TR_STRNCPY_ROOM[k].room > english_bytes ? B200TR_STRNCPY_ROOM[k].room : english_bytes;
            if (r < best) best = r;
        }
    }
    if (in_list(B200TR_ENGLISH_LENGTH, id) && english_bytes < best) best = english_bytes;
    return best;
}

/* ----------------------------------------------------------------- reading the file */

static int field_decode(tt_span f, char *out) {
    int i = 0, o = 0;
    if (f.n >= 2 && f.s[0] == '"' && f.s[f.n - 1] == '"') {
        tt_span inner;
        char *w = out;
        inner.s = f.s + 1;
        inner.n = f.n - 2;
        for (i = 0; i < inner.n; ++i) {
            out[o++] = inner.s[i];
            if (inner.s[i] == '"' && i + 1 < inner.n && inner.s[i + 1] == '"') ++i;
        }
        f.s = out;
        f.n = o;
        o = 0;
        i = 0;
        while (i < f.n) {
            if (f.s[i] == '\\' && i + 1 < f.n && (f.s[i + 1] == 'n' || f.s[i + 1] == 't' || f.s[i + 1] == '\\')) {
                w[o++] = f.s[i + 1] == 'n' ? '\n' : f.s[i + 1] == 't' ? '\t' : '\\';
                i += 2;
            } else {
                w[o++] = f.s[i++];
            }
        }
        out[o] = 0;
        return o;
    }
    while (i < f.n) {
        if (f.s[i] == '\\' && i + 1 < f.n && (f.s[i + 1] == 'n' || f.s[i + 1] == 't' || f.s[i + 1] == '\\')) {
            out[o++] = f.s[i + 1] == 'n' ? '\n' : f.s[i + 1] == 't' ? '\t' : '\\';
            i += 2;
        } else {
            out[o++] = f.s[i++];
        }
    }
    out[o] = 0;
    return o;
}

static int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

static int key_char(unsigned char c, int id_part) {
    return (c >= 'a' && c <= 'z') || tt_is_digit(c) || c == '_' || c == '-' || c == '.'
        || (id_part && ((c >= 'A' && c <= 'Z') || c == '/'));
}

static int split_key(tt_span key, tt_span *source, tt_span *id, unsigned int *hash) {
    int slash = -1, tilde, i;
    for (i = 0; i < key.n; ++i) if (key.s[i] == '/') { slash = i; break; }
    if (slash <= 0 || key.n < slash + 11) return 0;
    tilde = key.n - 9;
    if (key.s[tilde] != '~' || tilde <= slash + 1) return 0;
    for (i = 0; i < slash; ++i) if (!key_char((unsigned char)key.s[i], 0)) return 0;
    for (i = slash + 1; i < tilde; ++i) if (!key_char((unsigned char)key.s[i], 1)) return 0;
    *hash = 0;
    for (i = tilde + 1; i < key.n; ++i) {
        int v = hexval(key.s[i]);
        if (v < 0) return 0;
        *hash = (*hash << 4) | (unsigned int)v;
    }
    source->s = key.s;
    source->n = slash;
    id->s = key.s + slash + 1;
    id->n = tilde - slash - 1;
    return 1;
}

/* The translation rendered into the arena (the game keeps the pointer): NULL when it does not fit. */
static char *render_out(const char *s, int n, const tt_template *t, int mode) {
    tt_out o;
    static char scratch[(TR_ABSOLUTE_MAX + 4) * 4];
    char *buf;
    int len;
    o.buf = scratch;
    o.cap = TR_ABSOLUTE_MAX * 2;
    o.mode = mode;
    if (tt_render(s, n, t, plural_rule, NULL, 0, 0, &o) < 0) return NULL;
    len = slen(scratch);
    buf = arena_alloc((SIZE_T)len + 1);
    if (buf == NULL) return NULL;
    bcopy_(buf, scratch, len + 1);
    return buf;
}

/* The translation's size as the limits count it (translation_format.measure): the larger of every choice at its
   longest and the text the game is handed, in UTF-8 bytes. */
static int measure(const char *s, int n, const tt_template *t) {
    static char scratch[(TR_ABSOLUTE_MAX + 4) * 8];
    tt_out o;
    int a, b;
    o.buf = scratch;
    o.cap = TR_ABSOLUTE_MAX * 2;
    o.mode = 1;
    a = tt_render(s, n, t, plural_rule, NULL, 0, 1, &o);
    b = tt_render(s, n, t, plural_rule, NULL, 0, 0, &o);
    if (a < 0 || b < 0) return 0x7FFFFFFF;
    return a > b ? a : b;
}

static tt_template tmpl_english, tmpl_translation;

static int is_patch_format(unsigned int hash) {
    int k;
    for (k = 0; k < B200TR_PATCH_FORMAT_COUNT; ++k) if (B200TR_PATCH_FORMAT[k] == hash) return 1;
    return 0;
}

/* A FORMAT line: its translation with every plain '%' as "%%" (a new text), parsed again; 0 when it cannot be. */
static int escape_row(row *r) {
    char *esc;
    int n;
    if (!r->is_format) return 1;
    esc = (char *)tr_alloc((SIZE_T)r->translation_n * 2 + 4);
    if (esc == NULL) return 0;
    n = tt_escape_percent(r->translation, r->translation_n, &tmpl_english, esc, r->translation_n * 2 + 4);
    if (n < 0) return 0;
    r->translation = esc;
    r->translation_n = n;
    tt_parse_template(esc, n, &tmpl_translation, &tmpl_english);
    return tmpl_translation.errors == 0;
}

/* `s` with every '%' as "%%": a line that is no format, handed to sprintf as its format (guard_sprintf). */
static char *escape_all(const char *s) {
    int n = slen(s), o = 0, k;
    char *out;
    for (k = 0; k < n && s[k] != '%'; ++k) {}
    if (k == n) return NULL;
    out = arena_alloc((SIZE_T)n * 2 + 2);
    if (out == NULL) return NULL;
    for (k = 0; k < n; ++k) { out[o++] = s[k]; if (s[k] == '%') out[o++] = '%'; }
    out[o] = 0;
    return out;
}

/* ----------------------------------------------------------------- the patches' own text */

static unsigned int patch_hash(const char *s, int n) {
    unsigned int h = 2166136261u;
    int k;
    for (k = 0; k < n; ++k) h = (h ^ (unsigned char)s[k]) * 16777619u;
    return h;
}

static row *patch_find(const char *english, int n) {
    row *r;
    int k;
    for (r = patch_bucket[patch_hash(english, n) % PATCH_BUCKETS]; r != NULL; r = r->next) {
        if (r->english_n != n) continue;
        for (k = 0; k < n && r->english[k] == english[k]; ++k) {}
        if (k == n) return r;
    }
    return NULL;
}

/* The most a patch's wide line may hold, in UTF-8 bytes (src/vf2_translation_strings.wide_room): three times its
   English, at least PATCH_WIDE_MIN, at most PATCH_WIDE_MAX. */
static int patch_room_w(const row *r) {
    int room_;
    room_ = r->english_n * 3;
    if (room_ < PATCH_WIDE_MIN) room_ = PATCH_WIDE_MIN;
    if (room_ > PATCH_WIDE_MAX) room_ = PATCH_WIDE_MAX;
    return room_;
}

static int read_rows(const char *text, int n) {
    int i = 0, line_no = 0, header = 0, lines = 1, k, format_seen = 0, pool_at = 0;
    char *pool;
    tt_span code;
    static const char title[] = TR_GAME_TITLE_TEXT;
    code.s = "en";
    code.n = 2;
    for (k = 0; k < n; ++k) if (text[k] == '\n' || text[k] == '\r') ++lines;
    rows = (row *)tr_alloc(sizeof(row) * (SIZE_T)lines);
    pool = (char *)tr_alloc((SIZE_T)n * 2 + 64);
    if (rows == NULL || pool == NULL) return 0;
    /* pass 1: the header and the information rows */
    while (i < n) {
        int start = i, end, ncols = 0;
        tt_span cols[4];
        ++line_no;
        while (i < n && text[i] != '\n' && text[i] != '\r') ++i;
        end = i;
        if (i < n && text[i] == '\r' && i + 1 < n && text[i + 1] == '\n') i += 2; else if (i < n) ++i;
        {
            tt_span whole;
            whole.s = text + start;
            whole.n = end - start;
            if (tt_strip(whole).n == 0 || text[start] == '#') continue;
        }
        {
            int c = start;
            while (ncols < 4) {
                int e = c;
                while (e < end && text[e] != '\t') ++e;
                cols[ncols].s = text + c;
                cols[ncols].n = e - c;
                ++ncols;
                if (e >= end) break;
                c = e + 1;
            }
        }
        if (!header) {
            char a[72], b[72], c3[72];
            tt_span x, y, z;
            if (ncols < 3 || cols[0].n > 64 || cols[1].n > 64 || cols[2].n > 64) {
                log_add("Translations: the file has no header row (English)\r\n");
                return 0;
            }
            x.s = a; x.n = field_decode(cols[0], a); y.s = b; y.n = field_decode(cols[1], b); z.s = c3; z.n = field_decode(cols[2], c3);
            if (!tt_span_is(tt_strip(x), "key") || !tt_span_is(tt_strip(y), "english") || !tt_span_is(tt_strip(z), "translation")) {
                log_add("Translations: the file has no header row (English)\r\n");
                return 0;
            }
            header = 1;
            continue;
        }
        if (ncols < 2) continue;
        {
            tt_span key = tt_strip(cols[0]);
            int info = key.n > 0 && (key.s[0] == '@' || (key.n >= 3 && (unsigned char)key.s[0] == 0xEF
                                                         && (unsigned char)key.s[1] == 0xBC && (unsigned char)key.s[2] == 0xA0));
            tt_span name, eng, val;
            char *e = pool + pool_at, *v;
            if (!info) continue;
            name.s = key.s + (key.s[0] == '@' ? 1 : 3);
            name.n = key.n - (key.s[0] == '@' ? 1 : 3);
            if (cols[1].n > 256 || (ncols > 2 && cols[2].n > 256)) continue;
            eng.s = e; eng.n = field_decode(cols[1], e);
            v = e + eng.n + 1;
            val.s = v; val.n = ncols > 2 ? field_decode(cols[2], v) : 0;
            if (ncols <= 2) v[0] = 0;
            if (tt_exact_case(name, "format") && !format_seen) {
                tt_span f = tt_strip(val.n > 0 ? val : eng);
                int major = 0, j = 0;
                format_seen = 1;
                while (j < f.n && f.s[j] != '.') {
                    if (!tt_is_digit((unsigned char)f.s[j]) || major > 1000) { log_add("Translations: @format is not a version (English)\r\n"); return 0; }
                    major = major * 10 + (f.s[j] - '0');
                    ++j;
                }
                if (j == 0) { log_add("Translations: @format is not a version (English)\r\n"); return 0; }
                if (major > 1) { log_add("Translations: the file is a newer format than this DLL reads (English)\r\n"); return 0; }
            } else if (tt_exact_case(name, "game") && !(header & 2)) {
                tt_span g = tt_strip(eng), want;
                want.s = title;
                want.n = slen(title);
                header |= 2;
                if (!tt_span_eq(g, want)) { log_add("Translations: the file is for another game (English)\r\n"); return 0; }
            } else if (tt_exact_case(name, "code") && !(header & 4)) {
                header |= 4;
                code = val;
                pool_at += eng.n + val.n + 2;
            }
        }
    }
    if (!header) { log_add("Translations: the file has no header row (English)\r\n"); return 0; }
    if (!(header & 2)) { log_add("Translations: the file has no @game row (English)\r\n"); return 0; }
    plural_rule = tt_rule_for(code);
    /* pass 2: the rows */
    i = 0;
    line_no = 0;
    header = 0;
    while (i < n) {
        int start = i, end, ncols = 0, v = 0, j;
        tt_span cols[4], key, source, id;
        unsigned int hash;
        row *r;
        ++line_no;
        while (i < n && text[i] != '\n' && text[i] != '\r') ++i;
        end = i;
        if (i < n && text[i] == '\r' && i + 1 < n && text[i + 1] == '\n') i += 2; else if (i < n) ++i;
        {
            tt_span whole;
            whole.s = text + start;
            whole.n = end - start;
            if (tt_strip(whole).n == 0 || text[start] == '#') continue;
        }
        if (!header) { header = 1; continue; }
        {
            int c = start;
            while (ncols < 4) {
                int e = c;
                while (e < end && text[e] != '\t') ++e;
                cols[ncols].s = text + c;
                cols[ncols].n = e - c;
                ++ncols;
                if (e >= end) break;
                c = e + 1;
            }
        }
        if (ncols < 2) continue;
        key = tt_strip(cols[0]);
        if (key.n > 0 && (key.s[0] == '@' || (unsigned char)key.s[0] == 0xEF)) continue;
        if (ncols < 3 || cols[2].n == 0) continue;                            /* not translated */
        if (!split_key(key, &source, &id, &hash)) { log_refused(line_no, "the key is not a valid key"); continue; }
        r = &rows[row_count];
        r->line = line_no;
        r->english = pool + pool_at;
        r->english_n = field_decode(cols[1], pool + pool_at);
        pool_at += r->english_n + 1;
        r->translation = pool + pool_at;
        r->translation_n = field_decode(cols[2], pool + pool_at);
        pool_at += r->translation_n + 1;
        if (r->translation_n == 0) continue;
        if (tt_sha256_head((const unsigned char *)r->english, (unsigned int)r->english_n) != hash) {
            log_refused(line_no, "the English column does not match the key");
            continue;
        }
        if (tt_span_is(source, "patch")) {
            /* Text a patch adds: used where a patch's DLL asks for it by its English (patch_find). */
            r->is_format = is_patch_format(hash);
            if (!tt_translation_ok(r->english, r->english_n, r->translation, r->translation_n, &tmpl_english, &tmpl_translation,
                                   r->is_format)
                || !escape_row(r)) {
                log_refused(line_no, "the placeholders or choices do not match the English");
                continue;
            }
            r->patch = 1;
            r->has_conv = tmpl_english.nconv > 0;
            r->size = measure(r->translation, r->translation_n, &tmpl_translation);
            if (r->size > TR_MAX_LINE) { log_refused(line_no, "too long for its space"); continue; }
            r->out = render_out(r->translation, r->translation_n, &tmpl_translation, text_mode);
            r->utf8 = render_out(r->translation, r->translation_n, &tmpl_translation, 1);
            if (r->out == NULL || r->utf8 == NULL) { log_refused(line_no, "could not be written"); continue; }
            if (patch_find(r->english, r->english_n) != NULL) continue;      /* the same line again: the first counts */
            {
                unsigned int b = patch_hash(r->english, r->english_n) % PATCH_BUCKETS;
                r->next = patch_bucket[b];
                patch_bucket[b] = r;
            }
            ++row_count;
            ++used;
            ++patch_used;
            continue;
        }
        if (!tt_span_is(source, "strings")) { log_refused(line_no, "unknown source"); continue; }
        for (j = 0; j < id.n; ++j) {
            if (!tt_is_digit((unsigned char)id.s[j]) || v > 100000) { v = -1; break; }
            v = v * 10 + (id.s[j] - '0');
        }
        if (v < 1 || (unsigned)v >= tab_max_id || id.n == 0) { log_refused(line_no, "no such game line"); continue; }
        r->id = v;
        if (in_list(B200TR_NEVER, v)) { log_refused(line_no, "this line is never translated"); continue; }
        r->rec = record_of(v);
        if (r->rec == NULL) { log_refused(line_no, "no such game line"); continue; }
        r->is_format = in_list(B200TR_FORMAT, v);
        if (!tt_translation_ok(r->english, r->english_n, r->translation, r->translation_n, &tmpl_english, &tmpl_translation,
                               r->is_format)
            || !escape_row(r)) {
            log_refused(line_no, "the placeholders or choices do not match the English");
            continue;
        }
        if (measure(r->translation, r->translation_n, &tmpl_translation) > room(v, r->english_n)) {
            log_refused(line_no, "too long for its space");
            continue;
        }
        r->english_game = render_out(r->english, r->english_n, &tmpl_english, 0);
        if (r->english_game == NULL || !bsame(r->english_game, r->rec->text)) {
            log_refused(line_no, "the game's English is not this line's English");
            continue;
        }
        r->out = render_out(r->translation, r->translation_n, &tmpl_translation, text_mode);
        if (r->out == NULL) { log_refused(line_no, "could not be written"); continue; }
        if (!r->is_format) r->out_fmt = escape_all(r->out);
        if (by_id[v] != NULL) continue;                                     /* the same line again: the first counts */
        by_id[v] = r;
        ++row_count;
        ++used;
    }
    return 1;
}

/* ----------------------------------------------------------------- the guards */

/* The row whose `out` is exactly `p`; NULL for any other pointer (a range test first: the common case). */
static const row *row_of_out(const void *p) {
    unsigned k;
    if (p == NULL || !in_arena(p)) return NULL;
    for (k = 1; k < tab_max_id; ++k) if (by_id[k] != NULL && (const void *)by_id[k]->out == p) return by_id[k];
    return NULL;
}

/* A translated line cut to `len` bytes (at a whole letter); the cut text lives in one of sixteen slots. */
static char cut_slots[16][TR_ABSOLUTE_MAX + 8];
static int cut_next = 0;

static const char *cut_to(const char *s, int len) {
    char *slot;
    if (len < 0) len = 0;
    if (slen(s) <= len) return s;
    if (text_mode == 1) while (len > 0 && ((unsigned char)s[len] & 0xC0) == 0x80) --len;
    if (len > TR_ABSOLUTE_MAX) len = TR_ABSOLUTE_MAX;
    slot = cut_slots[cut_next++ & 15];
    bcopy_(slot, s, len);
    slot[len] = 0;
    return slot;
}

/* A translated line cut to its English length; anything else as it is. */
static const char *cut(const char *s) {
    const row *r = row_of_out(s);
    if (r == NULL) return s;
    return cut_to(s, slen(r->english_game));
}

typedef char *(__cdecl *copy_fn)(char *, const char *, size_t);
typedef int (__cdecl *sprintf_fn)(char *, const char *, ...);

/* The C runtime's entries, replaced by a jmp to a guard; the stolen instructions and a jmp back run from the
   trampoline (made executable before anything is written: a trampoline in a data page crashes under DEP). */
static unsigned char StrncpyTrampoline[16];
static unsigned char SprintfTrampoline[16];
static unsigned hook_entry[2];

static char *__cdecl guard_strncpy(char *dst, const char *src, size_t n) {
    const char *use = src;
    if (in_arena(src)) {
        __try {
            const row *r = row_of_out(src);
            if (r != NULL && n > 0 && (size_t)slen(src) >= n && (size_t)slen(r->english_game) < n)
                use = cut_to(src, (int)n - 1);      /* the English copy ends with its NUL; so does this one */
        } __except (EXCEPTION_EXECUTE_HANDLER) { use = src; }
    }
    return ((copy_fn)(UINT_PTR)StrncpyTrampoline)(dst, use, n);
}

static char sprintf_t[(TR_ABSOLUTE_MAX + 64) * 10];
static char sprintf_e[(TR_ABSOLUTE_MAX + 64) * 10];

/* sprintf(dst, format, up to 8 more): a translated format or argument may make the text no longer than the English
   format and arguments make it. */
static int __cdecl guard_sprintf(char *dst, const char *format, DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4,
                                 DWORD a5, DWORD a6, DWORD a7) {
    int changed = 0, q, lt, le;
    DWORD a[8], e[8];
    const char *fe = format;
    const char *ft = format;
    sprintf_fn next = (sprintf_fn)(UINT_PTR)SprintfTrampoline;
    a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3; a[4] = a4; a[5] = a5; a[6] = a6; a[7] = a7;
    __try {
        const row *r = row_of_out(format);
        if (r != NULL) {
            fe = r->english_game;
            changed = 1;
            if (r->out_fmt != NULL) ft = r->out_fmt;   /* a line that is no format: its '%' are plain text */
        }
        for (q = 0; q < 8; ++q) {
            const row *x = row_of_out((const void *)(UINT_PTR)a[q]);
            e[q] = x != NULL ? (DWORD)(UINT_PTR)x->english_game : a[q];
            if (x != NULL) a[q] = (DWORD)(UINT_PTR)cut((const char *)(UINT_PTR)a[q]);   /* each text at most its English */
            if (x != NULL) changed = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        changed = 0;
        a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3; a[4] = a4; a[5] = a5; a[6] = a6; a[7] = a7;
    }
    /* nothing translated: the call as it was */
    if (!changed) return next(dst, format, a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]);
    lt = next(sprintf_t, ft, a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]);
    le = next(sprintf_e, fe, e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7]);
    if (lt < 0 || le < 0) return next(dst, fe, e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7]);
    if (lt > le) {
        lt = le;
        if (text_mode == 1) while (lt > 0 && ((unsigned char)sprintf_t[lt] & 0xC0) == 0x80) --lt;
    }
    bcopy_(dst, sprintf_t, lt);
    dst[lt] = 0;
    return lt;
}

static int write_code(unsigned int at, const unsigned char *bytes, int n) {
    DWORD old, ignored;
    int k;
    if (!VirtualProtect((void *)(UINT_PTR)at, (SIZE_T)n, PAGE_EXECUTE_READWRITE, &old)) return 0;
    for (k = 0; k < n; ++k) ((unsigned char *)(UINT_PTR)at)[k] = bytes[k];
    VirtualProtect((void *)(UINT_PTR)at, (SIZE_T)n, old, &ignored);
    FlushInstructionCache(GetCurrentProcess(), (void *)(UINT_PTR)at, (SIZE_T)n);
    return 1;
}

/* Makes the trampoline of one hook: the stolen bytes, then a jmp to the rest of the function.  The trampoline is
   made PAGE_EXECUTE_READWRITE here, before the entry is touched. */
static int make_trampoline(unsigned char *tramp, unsigned entry, unsigned steal, unsigned char *original) {
    DWORD old;
    unsigned k;
    unsigned rel;
    if (steal < 5 || steal > 10) return 0;
    for (k = 0; k < steal; ++k) original[k] = ((const unsigned char *)(UINT_PTR)entry)[k];
    if (!VirtualProtect(tramp, 16, PAGE_EXECUTE_READWRITE, &old)) return 0;
    for (k = 0; k < steal; ++k) tramp[k] = original[k];
    tramp[steal] = 0xE9;
    rel = (entry + steal) - ((unsigned)(UINT_PTR)tramp + steal + 5u);
    tramp[steal + 1] = (unsigned char)rel;
    tramp[steal + 2] = (unsigned char)(rel >> 8);
    tramp[steal + 3] = (unsigned char)(rel >> 16);
    tramp[steal + 4] = (unsigned char)(rel >> 24);
    FlushInstructionCache(GetCurrentProcess(), tramp, 16);
    return 1;
}

static int pin_matches(unsigned at, int pin) {
    unsigned k;
    const unsigned char *live = (const unsigned char *)(UINT_PTR)at;
    for (k = 0; k < TR_PINS[pin].len; ++k)
        if (!TR_PINS[pin].mask[k] && live[k] != TR_PINS[pin].bytes[k]) return 0;
    return 1;
}

/* Installs the two guards, all or nothing. */
static int install_guards(void) {
    static const int pins[2] = { TR_PIN_STRNCPY, TR_PIN_SPRINTF };
    unsigned char *trampolines[2];
    unsigned guards[2];
    unsigned char original[2][10];
    unsigned char jmp[5];
    int k;
    trampolines[0] = StrncpyTrampoline; trampolines[1] = SprintfTrampoline;
    guards[0] = (unsigned)(UINT_PTR)guard_strncpy;
    guards[1] = (unsigned)(UINT_PTR)guard_sprintf;
    for (k = 0; k < 2; ++k) {
        hook_entry[k] = sites[pins[k]];
        if (!pin_matches(hook_entry[k], pins[k])) return 0;
        if (!make_trampoline(trampolines[k], hook_entry[k], TR_STEAL[pins[k]], original[k])) return 0;
    }
    for (k = 0; k < 2; ++k) {
        unsigned rel = guards[k] - (hook_entry[k] + 5u);
        jmp[0] = 0xE9;
        jmp[1] = (unsigned char)rel; jmp[2] = (unsigned char)(rel >> 8);
        jmp[3] = (unsigned char)(rel >> 16); jmp[4] = (unsigned char)(rel >> 24);
        if (!write_code(hook_entry[k], jmp, 5)) {
            int j;
            for (j = 0; j < k; ++j) write_code(hook_entry[j], original[j], (int)TR_STEAL[pins[j]]);
            return 0;
        }
        ++guarded;
    }
    return 1;
}

/* ----------------------------------------------------------------- finding the game */

/* Find `pat` (mask 1 = wildcard) in [base, base+size).  Counts matches up to 2 in *hits; returns the first. */
#ifdef B200TR_TEST
__declspec(noinline)
#endif
static unsigned ScanPattern(const unsigned char *base, unsigned size, const unsigned char *pat,
                            const unsigned char *mask, unsigned len, unsigned *hits) {
    unsigned first = 0, key = 0;
    while (key < len && mask[key]) ++key;
    if (key == len || size < len) return 0;
    {
        unsigned last = size - len, pos;
        for (pos = 0; pos <= last; ++pos) {
            unsigned i = 0;
            if (base[pos + key] != pat[key]) continue;
            while (i < len && (mask[i] || base[pos + i] == pat[i])) ++i;
            if (i == len) {
                if (!*hits) first = (unsigned)(UINT_PTR)base + pos;
                if (++*hits >= 2) return first;
            }
        }
    }
    return first;
}

#define TR_CHECK(cond, why) do { if (!(cond)) { log_add("Translations: NOT installed; " why "\r\n"); return 0; } } while (0)

static unsigned field_value(const TrField *f) { return *(const unsigned *)(UINT_PTR)(sites[f->pin] + f->offset); }

/* Every pin exactly once in the executable's code; the table, its size, the index and the largest id read from the
   pinned runs, and they all agree. */
static int resolve(void) {
    HMODULE exe = GetModuleHandleW(0);
    const IMAGE_DOS_HEADER *dos;
    const IMAGE_NT_HEADERS32 *nt;
    const IMAGE_SECTION_HEADER *s;
    unsigned i, pin;
    static const TrField f_table = TR_STRING_TABLE_SCAN_TABLE, f_count = TR_STRING_TABLE_SCAN_COUNT,
        f_index = TR_STRING_TABLE_SCAN_INDEX, f_max = TR_STRING_TABLE_SCAN_MAX_ID,
        f_index_get = TR_GET_STRING_INDEX, f_index_fill = TR_FILL_TEMPLATE_INDEX;
    TR_CHECK(exe != NULL, "no executable");
    dos = (const IMAGE_DOS_HEADER *)exe;
    nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    image_low = (unsigned)(UINT_PTR)exe;
    image_high = image_low + nt->OptionalHeader.SizeOfImage;
    s = IMAGE_FIRST_SECTION(nt);
    for (pin = 0; pin < TR_PIN_COUNT; ++pin) {
        unsigned hits = 0, at = 0;
        for (i = 0; i < nt->FileHeader.NumberOfSections && hits < 2; ++i) {
            unsigned size, h = 0, found;
            if (!(s[i].Characteristics & IMAGE_SCN_MEM_EXECUTE)) continue;
            size = s[i].Misc.VirtualSize ? s[i].Misc.VirtualSize : s[i].SizeOfRawData;
            if (s[i].SizeOfRawData < size) size = s[i].SizeOfRawData;
            found = ScanPattern((const unsigned char *)exe + s[i].VirtualAddress, size, TR_PINS[pin].bytes,
                                TR_PINS[pin].mask, TR_PINS[pin].len, &h);
            if (h) { if (!hits) at = found; hits += h; }
        }
        TR_CHECK(hits == 1, "a pinned run of the game is not found exactly once");
        sites[pin] = at;
    }
    tab_table = field_value(&f_table);
    tab_count = field_value(&f_count);
    tab_index = field_value(&f_index);
    tab_max_id = field_value(&f_max);
    TR_CHECK(field_value(&f_index_get) == tab_index && field_value(&f_index_fill) == tab_index,
             "the pins disagree about the index of lines");
    TR_CHECK(tab_count >= 1 && tab_count <= 0x4000 && tab_max_id > 1 && tab_max_id <= 0x2000, "the line table is not believable");
    TR_CHECK(tab_table >= image_low && tab_table + tab_count * TR_RECORD_SIZE <= image_high
             && tab_index >= image_low && tab_index + 4u * tab_max_id <= image_high, "the line table is outside the game");
    {
        const record *first = (const record *)(UINT_PTR)tab_table;
        TR_CHECK(first->id == 1 && first->override == NULL && is_text(first->key) && is_text(first->text),
                 "the line table does not start as expected");
    }
    return 1;
}

/* theStringManager::Get(): builds the manager (its constructor indexes the table) on first use. */
static int build_manager(void) {
    typedef void *(__cdecl *get_fn)(void);
    get_fn get = (get_fn)(UINT_PTR)sites[TR_PIN_STRING_MANAGER_GET];
    int ok = 0;
    __try { ok = get() != NULL; } __except (EXCEPTION_EXECUTE_HANDLER) { ok = 0; }
    TR_CHECK(ok, "the game's string manager could not be built");
    TR_CHECK(record_of(1) != NULL, "the game's string manager has not indexed its lines");
    return 1;
}

/* ----------------------------------------------------------------- installing */

static void own_folder(void) {
    DWORD n = GetModuleFileNameW((HMODULE)&__ImageBase, folder, 1000);
    wchar_t *slash;
    if (n == 0 || n >= 1000) { folder[0] = 0; return; }
    folder[n] = 0;
    slash = folder + n;
    while (slash > folder && slash[-1] != L'\\' && slash[-1] != L'/') --slash;
    *slash = 0;
}

/* The Unicode text DLL has installed its hooks (it draws UTF-8): B200Unicode_UnicodeTextActive() is nonzero, else its
   status block says installed. */
static int unicode_text_active(void) {
    static const wchar_t *const names[2] = { L"vf2unicode_b200.dll", L"vf2unicodefont_b200.dll" };
    int k;
    for (k = 0; k < 2; ++k) {
        HMODULE m = GetModuleHandleW(names[k]);
        FARPROC p;
        const unsigned *st;
        if (m == NULL) continue;
        p = GetProcAddress(m, "B200Unicode_UnicodeTextActive");
        if (p == NULL) p = GetProcAddress(m, "_B200Unicode_UnicodeTextActive@0");
        if (p != NULL) {
            if (((int (__stdcall *)(void))p)() != 0) return 1;
            continue;
        }
        st = (const unsigned *)GetProcAddress(m, "B200Unicode_Status");
        if (st != NULL && st[0] == UNI_STATUS_MAGIC && st[4] != 0) return 1;
    }
    return 0;
}

/* Everything after the choice is read: the game found, the file parsed, the guards in, the overrides set. */
static int install_from_text(const char *text, int text_n) {
    unsigned k;
    if (!resolve()) return 0;
    B200Tr_Status.resolved = 1;
    if (!build_manager()) return 0;
    by_id = (row **)tr_alloc(sizeof(row *) * (SIZE_T)(tab_max_id + 1));
    TR_CHECK(by_id != NULL, "out of memory");
    if (!read_rows(text, text_n)) return 0;
    if (used == 0) { log_add("Translations: no translated line could be used (English)\r\n"); return 0; }
    TR_CHECK(install_guards(), "a C runtime entry is not what this build expects");
    for (k = 1; k < tab_max_id; ++k) if (by_id[k] != NULL) by_id[k]->rec->override = by_id[k]->out;
    return 1;
}

static int started = 0;

static void finish(int ok) {
    installed = ok;
    B200Tr_Status.installed = (unsigned)ok;
    B200Tr_Status.used = (unsigned)used;
    B200Tr_Status.refused = (unsigned)refused;
    B200Tr_Status.guarded = (unsigned)guarded;
    B200Tr_Status.textMode = (unsigned)text_mode;
    B200Tr_Status.patchLines = (unsigned)patch_used;
    if (installed) {
        head_add("Translations: installed (");
        head_add(file_label[0] ? file_label : "Translation.txt");
        head_add("): ");
        head_add(number(used));
        head_add(" lines used, ");
        head_add(number(guarded));
        head_add(" copies guarded, ");
        head_add(text_mode ? "UTF-8 text" : "Windows-1252 text");
        head_add("\r\n");
    }
    if (refused > 0) {
        head_add("Translations: ");
        head_add(number(refused));
        head_add(" line(s) show English:\r\n");
    }
}

__declspec(dllexport) int __cdecl B200Tr_Startup(void) {
    unsigned char *data;
    char *text;
    int size = 0, text_n, ok = 0;
    wchar_t ini[1100];
    if (started) return installed;
    started = 1;
    __try {
        own_folder();
        if (folder[0] == 0 || wlen(folder) > 1000) {
            log_add("Translations: NOT installed; the DLL's folder is unknown\r\n");
        } else {
            wcopy(ini, folder);
            wcat(ini, L"vf2tr.ini");
            B200Tr_Status.requested = GetPrivateProfileIntW(L"Patches", L"Translations", 0, ini) == 1 ? 1u : 0u;
            if (!B200Tr_Status.requested) {
                log_add("Translations: off in vf2tr.ini; nothing is changed\r\n");
            } else if ((data = chosen_file(&size)) != NULL) {
                text_mode = unicode_text_active();
                text = (char *)tr_alloc((SIZE_T)size * 2 + 16);
                text_n = text != NULL ? tt_decode(data, size, text, size * 2 + 16) : -1;
                if (text_n < 0) log_add("Translations: the file is not UTF-8 or UTF-16 with a byte-order mark (English)\r\n");
                else ok = install_from_text(text, text_n);
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        log_add("Translations: stopped by an error; the game stays in English where it was not yet changed\r\n");
        ok = 0;
    }
    finish(ok);
    write_log();
    return installed;
}

#ifdef B200TR_TEST
/* The harness: the same install, with the translation's text handed in (no file, no ini) and the Unicode state given. */
__declspec(dllexport) int __cdecl B200Tr_TestInstall(const char *text, int n, int unicode) {
    int ok = 0;
    if (started) return -1;
    started = 1;
    text_mode = unicode ? 1 : 0;
    __try {
        char *decoded = (char *)tr_alloc((SIZE_T)n * 2 + 16);
        int decoded_n = decoded != NULL ? tt_decode((const unsigned char *)text, n, decoded, n * 2 + 16) : -1;
        ok = decoded_n >= 0 && install_from_text(decoded, decoded_n);
        if (decoded_n < 0) log_add("Translations: the file is not UTF-8 or UTF-16 with a byte-order mark (English)\r\n");
    } __except (EXCEPTION_EXECUTE_HANDLER) { ok = 0; }
    finish(ok);
    return installed;
}
__declspec(dllexport) const char *__cdecl B200Tr_TestLog(void) { return log_text; }
__declspec(dllexport) void *__cdecl B200Tr_TestScanAddress(void) { return (void *)ScanPattern; }
/* the Unicode contract's answer as the install asks it (1 UTF-8, 0 Windows-1252) */
__declspec(dllexport) int __cdecl B200Tr_TestUnicodeActive(void) { return unicode_text_active(); }
#endif

/* The line's override for a string id now (tests and other DLLs): the translation, or NULL (English). */
__declspec(dllexport) const char *__cdecl B200Tr_Translation(int id) {
    return id >= 1 && (unsigned)id < tab_max_id && by_id != NULL && by_id[id] != NULL && installed ? by_id[id]->out : NULL;
}

/* ----------------------------------------------------------------- for the other DLLs */

/* A patch's wide text (a Windows dialog, message box or list): its translation, or `english` itself when there is
   none, it is too long for its room (patch_room_w), or nothing is installed.  Never NULL for a non-NULL `english`.
   The translation lives as long as the game. */
__declspec(dllexport) const wchar_t *__cdecl B200Tr_TextW(const wchar_t *english) {
    static char key[(TR_MAX_LINE + 8) * 3];
    tt_out o;
    row *r;
    int k = 0;
    if (english == NULL || !installed || patch_used == 0) return english;
    o.buf = key;
    o.cap = TR_MAX_LINE * 3;
    o.mode = 1;
    o.at = 0;
    o.overflow = 0;
    while (english[k] != 0 && !o.overflow) {
        unsigned int cp = english[k++];
        if (cp >= 0xD800 && cp < 0xDC00 && english[k] >= 0xDC00 && english[k] < 0xE000)
            cp = 0x10000u + ((cp - 0xD800u) << 10) + (english[k++] - 0xDC00u);
        tt_put_cp(&o, cp);
    }
    if (o.overflow) return english;
    r = patch_find(key, o.at);
    if (r == NULL || r->size > patch_room_w(r)) return english;
    if (r->wide == NULL) {
        int n = slen(r->utf8);
        wchar_t *w = (wchar_t *)tr_alloc((SIZE_T)(n + 2) * sizeof(wchar_t) * 2);
        if (w == NULL || !utf8_to_wide(r->utf8, n, w, n * 2 + 2)) return english;
        r->wide = w;
    }
    return r->wide;
}

/* A patch's narrow text that the game draws (a button, a caption): its translation as the game draws text
   (Windows-1252, or UTF-8 with the Unicode settings), or `english` itself when there is none, it is longer than
   `room` bytes, or nothing is installed.  `english` is Windows-1252 (the patches' own text is ASCII). */
__declspec(dllexport) const char *__cdecl B200Tr_TextA(const char *english, int room_) {
    static char key[(TR_MAX_LINE + 8) * 3];
    tt_out o;
    row *r;
    int k = 0;
    if (english == NULL || !installed || patch_used == 0) return english;
    o.buf = key;
    o.cap = TR_MAX_LINE * 3;
    o.mode = 1;
    o.at = 0;
    o.overflow = 0;
    while (english[k] != 0 && !o.overflow) {
        unsigned char c = (unsigned char)english[k++];
        tt_put_cp(&o, c < 0x80 || c >= 0xA0 ? c : '?');
    }
    if (o.overflow) return english;
    r = patch_find(key, o.at);
    if (r == NULL || r->size > room_ || slen(r->out) > room_) return english;
    return r->out;
}

/* A game line's English, whatever the translation (the Family History log is written in English). */
__declspec(dllexport) const char *__cdecl B200Tr_English(int id) {
    record *r = tab_index != 0 ? record_of(id) : NULL;
    return r != NULL ? r->text : NULL;
}

/* The English of a line the game showed translated (a Random Event's title, for the Family History log): `shown`
   when it is no translated line. */
__declspec(dllexport) const char *__cdecl B200Tr_EnglishOf(const char *shown) {
    unsigned k;
    if (shown == NULL || !installed || by_id == NULL) return shown;
    for (k = 1; k < tab_max_id; ++k)
        if (by_id[k] != NULL && (by_id[k]->out == shown || bsame(by_id[k]->out, shown))) return by_id[k]->rec->text;
    return shown;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(instance);
    return TRUE;
}
