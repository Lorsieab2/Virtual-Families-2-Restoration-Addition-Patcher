// Word lists for line breaking where Windows has no icu.dll (before Windows 10 1903): Thai, Lao, Khmer and Burmese
// are written without spaces between words, so a line may only break between WORDS of a run of their letters. The
// lists are ICU 77-1's own (runtime/word-lists, copied unchanged: tests/test_word_lists.py checks each SHA-256), the
// same ones icu.dll has built in. The release ships them beside the DLL (<data folder>\Word Lists\). A list is read
// only the first time a line with a letter of its script is wrapped without icu.dll, so a game that never shows such
// text never reads one.
//
// Segmentation (b200unicode_text.h ComputeBreaks; src/vf2_line_break.dictionary_breaks is the same rule): from the run's
// first character, the longest word of the list that starts there and ends at a whole character is taken; when no
// word starts there, one character. A line may break between two such pieces.
//
// Included by b200unicode.cpp (the DLL) and b200unicode_texttest.cpp (the test DLL), after b200unicode_text.h.
#pragma once

namespace words {

struct List {
    bool looked;              // the file was looked for
    unsigned *cps;            // every word's code points, one after another
    unsigned *start;          // word k: cps[start[k] .. start[k] + len[k])
    unsigned char *len;
    unsigned count;
    unsigned *slots;          // open addressing: word index + 1, 0 = empty
    unsigned slotMask;
    unsigned maxLen;
};

static List Lists[ut::kWordListCount];
static wchar_t Folder[MAX_PATH];           // ends in a backslash; empty = no lists
static const wchar_t *const kFiles[ut::kWordListCount] = {
    L"thaidict.txt", L"laodict.txt", L"khmerdict.txt", L"burmesedict.txt" };
static const unsigned kMaxWord = 32;       // code points (the longest word of the four lists has 29)
static const unsigned kMaxFile = 8u << 20;

inline void *Get(unsigned n) { return HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, n ? n : 1); }

inline unsigned Hash(const unsigned *cps, unsigned n) {
    unsigned h = 2166136261u;
    for (unsigned i = 0; i < n; ++i) { h ^= cps[i]; h *= 16777619u; }
    return h ^ (n * 0x9E3779B9u);
}

inline bool Same(const List &l, unsigned k, const unsigned *cps, unsigned n) {
    if (l.len[k] != n) return false;
    const unsigned *w = l.cps + l.start[k];
    for (unsigned i = 0; i < n; ++i) if (w[i] != cps[i]) return false;
    return true;
}

inline bool Find(const List &l, const unsigned *cps, unsigned n) {
    if (!l.slots || n == 0 || n > l.maxLen) return false;
    for (unsigned at = Hash(cps, n) & l.slotMask;; at = (at + 1) & l.slotMask) {
        unsigned s = l.slots[at];
        if (!s) return false;
        if (Same(l, s - 1, cps, n)) return true;
    }
}

// The list's file: UTF-8 (a byte order mark is skipped), "#" lines are comments, one word per line (anything after a
// tab is not part of the word). A line that is not strict UTF-8, empty or longer than kMaxWord code points is skipped.
inline void Load(List &l, int which) {
    l.looked = true;
    l.cps = 0; l.start = 0; l.len = 0; l.slots = 0; l.count = 0; l.maxLen = 0; l.slotMask = 0;
    if (!Folder[0]) return;
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    for (unsigned i = 0; Folder[i]; ++i) { if (n + 1 >= MAX_PATH) return; path[n++] = Folder[i]; }
    for (unsigned i = 0; kFiles[which][i]; ++i) { if (n + 1 >= MAX_PATH) return; path[n++] = kFiles[which][i]; }
    path[n] = 0;
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (f == INVALID_HANDLE_VALUE) return;
    DWORD size = GetFileSize(f, 0), got = 0;
    unsigned char *text = size != INVALID_FILE_SIZE && size && size <= kMaxFile ? (unsigned char *)Get(size) : 0;
    bool ok = text && ReadFile(f, text, size, &got, 0) && got == size;
    CloseHandle(f);
    if (!ok) { if (text) HeapFree(GetProcessHeap(), 0, text); return; }
    unsigned lines = 1;
    for (DWORD i = 0; i < size; ++i) if (text[i] == '\n') ++lines;
    l.cps = (unsigned *)Get(4 * size);                 // a code point takes at least one byte
    l.start = (unsigned *)Get(4 * lines);
    l.len = (unsigned char *)Get(lines);
    unsigned slots = 1;
    while (slots < 2 * lines) slots <<= 1;
    l.slots = (unsigned *)Get(4 * slots);
    if (!l.cps || !l.start || !l.len || !l.slots) { l.slots = 0; HeapFree(GetProcessHeap(), 0, text); return; }
    l.slotMask = slots - 1;
    unsigned used = 0;
    DWORD p = size >= 3 && text[0] == 0xEF && text[1] == 0xBB && text[2] == 0xBF ? 3 : 0;
    while (p < size) {
        DWORD e = p;
        while (e < size && text[e] != '\n') ++e;
        DWORD end = e;
        for (DWORD t = p; t < end; ++t) if (text[t] == '\t') { end = t; break; }
        while (end > p && (text[end - 1] == '\r' || text[end - 1] == ' ')) --end;
        if (end > p && text[p] != '#') {
            unsigned k = l.count, wn = 0;
            bool good = true;
            for (DWORD q = p; q < end && good;) {
                unsigned cp = 0;
                unsigned m = ut::Utf8Seq(text + q, end - q, &cp);
                if (!m || wn >= kMaxWord) { good = false; break; }
                l.cps[used + wn++] = cp;
                q += m;
            }
            if (good && wn && !Find(l, l.cps + used, wn)) {
                l.start[k] = used; l.len[k] = (unsigned char)wn;
                for (unsigned at = Hash(l.cps + used, wn) & l.slotMask;; at = (at + 1) & l.slotMask)
                    if (!l.slots[at]) { l.slots[at] = k + 1; break; }
                used += wn;
                ++l.count;
                if (wn > l.maxLen) l.maxLen = wn;
            }
        }
        p = e + 1;
    }
    HeapFree(GetProcessHeap(), 0, text);
}

// ut::WordLookup: is cps[0..n) a word of list `which`? (the list is read the first time it is asked)
inline bool Lookup(int which, const unsigned *cps, unsigned n) {
    if (which < 0 || which >= (int)ut::kWordListCount) return false;
    List &l = Lists[which];
    if (!l.looked) Load(l, which);
    return Find(l, cps, n);
}

// ut::WordListMax: the longest word of list `which` (0: no list, or it could not be read)
inline unsigned Longest(int which) {
    if (which < 0 || which >= (int)ut::kWordListCount) return 0;
    List &l = Lists[which];
    if (!l.looked) Load(l, which);
    return l.slots ? l.maxLen : 0;
}

// The folder that holds the lists (with its trailing backslash); the rules use them from now on.
inline void Install(const wchar_t *folder) {
    unsigned n = 0;
    while (folder && folder[n] && n + 1 < MAX_PATH) { Folder[n] = folder[n]; ++n; }
    Folder[n] = 0;
    for (unsigned i = 0; i < ut::kWordListCount; ++i) Lists[i].looked = false;
    ut::WordLookup() = n ? &Lookup : 0;
    ut::WordListMax() = n ? &Longest : 0;
}

}  // namespace words
