// The Unicode Text rules in C++, with no Windows and no C runtime: the companion DLL vf2unicode_b200.dll uses them in
// the game, and runtime/native/b200unicode/b200unicode_texttest.cpp builds them into a 64-bit test DLL the tests
// call next to src/vf2_game_text.py (the same rules in Python), text by text.
//
// * the stored form, read per sequence: each well-formed, shortest UTF-8 sequence is its character, every other byte
//   is one character (ASCII, Latin-1 for A0h..FFh, Windows-1252 for 80h..9Fh, the five bytes it leaves out as
//   themselves), so one string can hold both;
// * encode, per character: ASCII, U+00A0..U+00FF and the Windows-1252 characters are single bytes, any other
//   character is UTF-8, in one string; if those bytes would read back as different text, every non-ASCII character
//   is UTF-8;
// * characters: a simplified extended grapheme cluster (b200unicode_tables.h EXTEND; ZWJ joins the next; regional
//   indicators pair; CR LF);
// * the stock text functions with a character in place of a byte: GetWidth and GetNextJustifiedLine, given each
//   character's glyph width by the caller; GetNextJustifiedLine also breaks a line where UAX #14 allows next to a
//   letter of a script written without spaces (ICU when the host gives it, else the table of b200linebreak_table.h)
//   and cuts a word wider than the line between whole characters.
#pragma once

#include "b200unicode_tables.h"
#include "b200linebreak_table.h"

namespace ut {

static const unsigned CP1252_HIGH[32] = {
    0x20AC, 0, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0, 0x017D, 0,
    0, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0, 0x017E,
    0x0178,
};

static const unsigned kMaxClusterCps = 16;

inline bool InRanges(const UtRange *r, unsigned count, unsigned cp) {
    unsigned lo = 0, hi = count;
    while (lo < hi) {
        unsigned mid = (lo + hi) / 2;
        if (cp < r[mid].first) hi = mid;
        else if (cp > r[mid].last) lo = mid + 1;
        else return true;
    }
    return false;
}

inline bool IsExtend(unsigned cp) { return InRanges(UT_EXTEND, UT_EXTEND_COUNT, cp); }
inline bool IsRegional(unsigned cp) { return cp >= 0x1F1E6 && cp <= 0x1F1FF; }

// ------------------------------------------------------------------------------------------- line breaking (UAX #14)
// The host (the DLL, or the 64-bit test DLL) may give Windows' ICU (icu.dll: ubrk_open(UBRK_LINE), which also knows the
// Thai, Lao, Khmer and Myanmar words, and u_getIntPropertyValue(UCHAR_LINE_BREAK)); without it the table of
// b200linebreak_table.h (src/vf2_line_break.py is the same rule in the patcher) is used.
struct IcuApi {
    int (*lineClass)(unsigned cp);                                           // ICU's line break class of a code point
    bool (*boundaries)(const wchar_t *text, int length, unsigned char *out);  // out[0..length]: 1 where a line may break
};
inline const IcuApi *&Icu() { static const IcuApi *api = 0; return api; }
// Called (when set) the first time a text has a letter of a script written without spaces: the host looks for ICU then,
// so a game that never wraps such text never loads it.
inline void (*&IcuLoader())() { static void (*load)() = 0; return load; }

// Word lists for the scripts written without spaces between words (b200words.h; src/vf2_line_break.py): used only
// without ICU, which has the same lists built in. The host sets the two functions; 0 = no lists.
static const unsigned kWordListCount = 4;     // Thai, Lao, Khmer, Burmese (Myanmar)
inline bool (*&WordLookup())(int list, const unsigned *cps, unsigned n) { static bool (*f)(int, const unsigned *, unsigned) = 0; return f; }
inline unsigned (*&WordListMax())(int list) { static unsigned (*f)(int) = 0; return f; }

// The word list of a code point's script, or -1 (src/vf2_line_break.word_list_of).
inline int WordListOf(unsigned cp) {
    if (cp >= 0x0E00 && cp <= 0x0E7F) return 0;                                            // Thai
    if (cp >= 0x0E80 && cp <= 0x0EFF) return 1;                                            // Lao
    if ((cp >= 0x1780 && cp <= 0x17FF) || (cp >= 0x19E0 && cp <= 0x19FF)) return 2;        // Khmer
    if ((cp >= 0x1000 && cp <= 0x109F) || (cp >= 0xA9E0 && cp <= 0xA9FF) || (cp >= 0xAA60 && cp <= 0xAA7F))
        return 3;                                                                          // Myanmar
    return -1;
}

inline int FallbackClass(unsigned cp) {
    int lo = 0, hi = (int)kLineBreakRangeCount - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (cp < kLineBreakRanges[mid].first) hi = mid - 1;
        else if (cp > kLineBreakRanges[mid].last) lo = mid + 1;
        else return kLineBreakRanges[mid].cls;
    }
    return LbOther;
}

// May a line break between a character `before` and one `after` (the table)? Next to an ideographic letter, unless the
// next one is closing punctuation or the one before opens; after closing punctuation before an opening one.
inline bool FallbackMayBreak(unsigned before, unsigned after) {
    int a = FallbackClass(before), b = FallbackClass(after);
    if (b == LbClosing || a == LbOpening) return false;
    return a == LbIdeographic || b == LbIdeographic || (a == LbClosing && b == LbOpening);
}

// A letter of a script written without spaces: the CJK punctuation blocks, and ICU's line-break classes ID, SA, H2, H3,
// JL, JT, JV, CJ, EB and EM (the table's ideographic class without ICU).
inline bool NoSpaceLetter(unsigned cp) {
    if ((cp >= 0x3000 && cp <= 0x303F) || (cp >= 0xFE30 && cp <= 0xFE4F) || (cp >= 0xFF00 && cp <= 0xFFEF)) return true;
    if (const IcuApi *icu = Icu()) {
        int c = icu->lineClass(cp);
        return c == 14 || c == 24 || (c >= 31 && c <= 35) || c == 37 || c == 40 || c == 41;
    }
    return FallbackClass(cp) == LbIdeographic;
}

inline unsigned SingleByteChar(unsigned char b) {
    if (b >= 0x80 && b <= 0x9F) { unsigned cp = CP1252_HIGH[b - 0x80]; return cp ? cp : b; }
    return b;
}

// One UTF-8 sequence at s (n bytes left), strictly (no overlong form, no surrogate, nothing past U+10FFFF).
// Returns its length and the code point, or 0.
inline unsigned Utf8Seq(const unsigned char *s, unsigned n, unsigned *cp) {
    if (!n) return 0;
    unsigned c = s[0];
    if (c < 0x80) { *cp = c; return 1; }
    unsigned len, v, min;
    if (c >= 0xC2 && c <= 0xDF) { len = 2; v = c & 0x1F; min = 0x80; }
    else if (c >= 0xE0 && c <= 0xEF) { len = 3; v = c & 0x0F; min = 0x800; }
    else if (c >= 0xF0 && c <= 0xF4) { len = 4; v = c & 0x07; min = 0x10000; }
    else return 0;
    if (n < len) return 0;
    for (unsigned i = 1; i < len; ++i) {
        if ((s[i] & 0xC0) != 0x80) return 0;
        v = (v << 6) | (s[i] & 0x3F);
    }
    if (v < min || v > 0x10FFFF || (v >= 0xD800 && v <= 0xDFFF)) return 0;
    *cp = v;
    return len;
}

inline unsigned Length(const unsigned char *s) {
    unsigned n = 0;
    while (s[n]) ++n;
    return n;
}

// The character at s[at] under the per-sequence read rule: a well-formed UTF-8 sequence, else one byte read as
// Windows-1252. Returns its length (at least 1; 0 when at is past the end).
inline unsigned ReadChar(const unsigned char *s, unsigned n, unsigned at, unsigned *cp) {
    if (at >= n) return 0;
    unsigned k = Utf8Seq(s + at, n - at, cp);
    if (k) return k;
    *cp = SingleByteChar(s[at]);
    return 1;
}

struct Unit {
    unsigned start, size;          // its bytes in the text
    unsigned ncp;                  // code points (the first kMaxClusterCps are kept)
    unsigned cps[kMaxClusterCps];
    bool IsNewline() const { return ncp == 1 && cps[0] == 0x0A && size == 1; }
    bool IsSpace() const { return ncp == 1 && cps[0] == 0x20; }
};

// The characters of a text as the drawing code steps over them.
struct Units {
    const unsigned char *s;
    unsigned n, pos;

    void Init(const unsigned char *text, unsigned length) {
        s = text; n = length; pos = 0;
    }
    bool Peek(unsigned at, unsigned *cp, unsigned *len) const {
        *len = ReadChar(s, n, at, cp);
        return *len != 0;
    }
    bool Next(Unit &u) {
        if (pos >= n) return false;
        u.start = pos;
        u.ncp = 0;
        unsigned cp, len;
        Peek(pos, &cp, &len);
        Push(u, cp);
        pos += len;
        unsigned c2, l2;
        // CR and LF are two units here (LF is the line break), as in single-byte text
        if (cp == 0x0D) { u.size = pos - u.start; return true; }
        if (IsRegional(cp) && Peek(pos, &c2, &l2) && IsRegional(c2)) { Push(u, c2); pos += l2; }
        while (Peek(pos, &c2, &l2) && IsExtend(c2)) {
            Push(u, c2);
            pos += l2;
            unsigned c3, l3;
            if (c2 == 0x200D && Peek(pos, &c3, &l3) && c3 != 0x0A && c3 != 0x0D) { Push(u, c3); pos += l3; }
        }
        u.size = pos - u.start;
        return true;
    }
    static void Push(Unit &u, unsigned cp) {
        if (u.ncp < kMaxClusterCps) u.cps[u.ncp] = cp;
        ++u.ncp;
    }
};

// A base letter and its accents as the one letter they make (b200unicode_tables.h COMPOSE), else 0.
inline unsigned Composed(const Unit &u) {
    if (u.ncp < 2 || u.ncp > 4) return 0;
    for (unsigned i = 0; i < UT_COMPOSE_COUNT; ++i) {
        const UtCompose &c = UT_COMPOSE[i];
        if (c.count != u.ncp) continue;
        unsigned k = 0;
        while (k < c.count && c.seq[k] == u.cps[k]) ++k;
        if (k == c.count) return c.cp;
    }
    return 0;
}

inline unsigned PutUtf8(unsigned cp, unsigned char *out) {
    if (cp < 0x80) { out[0] = (unsigned char)cp; return 1; }
    if (cp < 0x800) { out[0] = (unsigned char)(0xC0 | (cp >> 6)); out[1] = (unsigned char)(0x80 | (cp & 0x3F)); return 2; }
    if (cp < 0x10000) {
        out[0] = (unsigned char)(0xE0 | (cp >> 12)); out[1] = (unsigned char)(0x80 | ((cp >> 6) & 0x3F));
        out[2] = (unsigned char)(0x80 | (cp & 0x3F)); return 3;
    }
    out[0] = (unsigned char)(0xF0 | (cp >> 18)); out[1] = (unsigned char)(0x80 | ((cp >> 12) & 0x3F));
    out[2] = (unsigned char)(0x80 | ((cp >> 6) & 0x3F)); out[3] = (unsigned char)(0x80 | (cp & 0x3F));
    return 4;
}

inline int SingleByteOf(unsigned cp) {
    if (cp < 0x80 || (cp >= 0xA0 && cp <= 0xFF)) return (int)cp;
    for (unsigned i = 0; i < 32; ++i) if (CP1252_HIGH[i] == cp) return (int)(0x80 + i);
    return -1;
}

// The stored form of the code points (no terminating 0), per character: a Windows-1252 character is its one byte, any
// other character is UTF-8, in one string. If those bytes would read back as different text (the per-sequence read
// of Decode), every non-ASCII character is UTF-8 instead. Returns the length, or -1 if more than cap bytes (the
// mixed form is never longer than the all-UTF-8 one, so it decides).
inline int Encode(const unsigned *cps, unsigned count, unsigned char *out, unsigned cap) {
    unsigned n = 0;
    unsigned char seq[4];
    for (unsigned i = 0; i < count; ++i) {
        if (!cps[i]) continue;
        int b = SingleByteOf(cps[i]);
        unsigned k = 1;
        if (b >= 0) seq[0] = (unsigned char)b;
        else k = PutUtf8(cps[i], seq);
        if (n + k > cap) return -1;
        for (unsigned j = 0; j < k; ++j) out[n++] = seq[j];
    }
    unsigned at = 0, i = 0, cp;
    bool same = true;
    while (same && at < n) {
        while (i < count && !cps[i]) ++i;
        unsigned k = ReadChar(out, n, at, &cp);
        if (i >= count || cps[i] != cp) same = false;
        at += k;
        ++i;
    }
    while (same && i < count) { if (cps[i]) same = false; ++i; }
    if (same) return (int)n;
    n = 0;
    for (unsigned j = 0; j < count; ++j) {
        if (!cps[j]) continue;
        unsigned k = PutUtf8(cps[j], seq);
        if (n + k > cap) return -1;
        for (unsigned m = 0; m < k; ++m) out[n++] = seq[m];
    }
    return (int)n;
}

// Every code point of a stored text (up to cap), in order, read per sequence.
inline unsigned Decode(const unsigned char *s, unsigned n, unsigned *cps, unsigned cap) {
    unsigned count = 0, i = 0, cp;
    while (count < cap) {
        unsigned k = ReadChar(s, n, i, &cp);
        if (!k) break;
        cps[count++] = cp;
        i += k;
    }
    return count;
}

// The stored form of the longest start of the text, in whole characters, that fits in maxBytes bytes
// (src/vf2_game_text.fit). cps is scratch room for cpsCap code points; out needs maxBytes bytes. Returns the length.
// The end of the character (cluster) that starts at cps[i] (src/vf2_game_text.clusters, over code points).
inline unsigned ClusterEnd(const unsigned *cps, unsigned n, unsigned i) {
    unsigned cp = cps[i++];
    if (cp == 0x0D && i < n && cps[i] == 0x0A) ++i;
    else if (IsRegional(cp) && i < n && IsRegional(cps[i])) ++i;
    while (i < n && IsExtend(cps[i])) {
        unsigned c = cps[i++];
        if (c == 0x200D && i < n && cps[i] != 0x0A && cps[i] != 0x0D) ++i;
    }
    return i;
}

inline unsigned Fit(const unsigned char *s, unsigned n, unsigned maxBytes, unsigned char *out, unsigned *cps,
                    unsigned cpsCap) {
    unsigned total = Decode(s, n, cps, cpsCap);
    unsigned best = 0, i = 0;
    bool any = false;
    // every start is tried (a start that must be UTF-8 can be longer than a longer start in single bytes)
    while (i < total) {
        unsigned end = ClusterEnd(cps, total, i);
        if (Encode(cps, end, out, maxBytes) >= 0) { best = end; any = true; }
        i = end;
    }
    if (!any) return 0;
    int k = Encode(cps, best, out, maxBytes);
    return k < 0 ? 0 : (unsigned)k;
}
// ------------------------------------------------------------------------------------------- the stock functions
typedef int (*WidthFn)(void *ctx, const Unit &u);

inline float F32(float v) { volatile float f = v; return f; }

// ldwFont::GetWidth(const char *, float), per character.
inline int GetWidth(const unsigned char *text, float scale, int kerning, WidthFn width, void *ctx) {
    Units it;
    it.Init(text, Length(text));
    Unit u;
    int widest = 0, cur = 0;
    while (it.Next(u)) {
        if (u.IsNewline()) {
            if (cur && cur > widest) widest = cur;
            cur = 0;
            continue;
        }
        int w = width(ctx, u);
        cur += (int)F32(F32((float)(kerning + w)) * scale);
    }
    if (widest > cur) cur = widest;
    return cur ? cur - kerning : 0;
}

// ldwFont::GetNextJustifiedLine, per character (src/vf2_game_text.next_justified_line, line for line).
// out gets the line (0-terminated; never more than maxBytes bytes plus the 0). Returns how many bytes of src were
// consumed; *doubleBreak as the stock flag.
//
// The stock function ends a line that is too long at its last space (an empty line, one character consumed, when
// there is none: the letters of a word wider than the line were lost). Here the line ends at the nearest of: a space
// (the stock rule, exactly), or a place UAX #14 allows a break, next to a letter of a script written without spaces
// (ideographs, kana, Hangul, Thai, ...; kinsoku: no line starts with a closing mark or ends with an opening one); and
// a word wider than the whole line is cut after its longest start of whole characters (at least one). Text with no
// such letter and no word wider than the line is laid out by the stock rule, character for character.
static const unsigned kMaxLineUnits = 4096;
static const unsigned kMaxBreakUnits = 12288;     // UTF-16 units handed to ICU (a character keeps at most 16 code points)

struct LineState {
    unsigned bufStart[kMaxLineUnits];   // the source bytes each written unit came from (a newline: none)
    unsigned bufSize[kMaxLineUnits];
    unsigned bufSrc[kMaxLineUnits];     // the source unit it came from
    int bufW[kMaxLineUnits];            // its width as the stock function adds it
    unsigned short bufBytes[kMaxLineUnits];
    bool bufSpace[kMaxLineUnits];
    unsigned offs[kMaxLineUnits + 1];   // source byte offset of unit k
    unsigned char brk[kMaxLineUnits + 1];   // a line may break between source unit k - 1 and k (UAX #14)
    unsigned first[kMaxLineUnits], last[kMaxLineUnits];   // a source unit's first and last code point
    unsigned short at16[kMaxLineUnits + 1];               // where it starts in the UTF-16 text given to ICU
    wchar_t text16[kMaxBreakUnits + 1];
    unsigned char bound[kMaxBreakUnits + 1];
};

// Where a line may break in the source text: st.brk[k] for 1 <= k < the unit count (the same as
// src/vf2_line_break.break_flags): never next to a space or a line feed, and only where a letter of a script written
// without spaces (or a zero width space) is next to the place and the rules (ICU, else the table) allow it.
inline void ComputeBreaks(const unsigned char *src, unsigned n, LineState &st) {
    for (unsigned k = 0; k <= kMaxLineUnits; ++k) st.brk[k] = 0;
    bool ascii = true;
    for (unsigned i = 0; i < n && ascii; ++i) if (src[i] >= 0x80) ascii = false;
    if (ascii) return;                                         // no such letter: nothing to compute
    if (void (*load)() = IcuLoader()) load();
    Units it;
    it.Init(src, n);
    Unit u;
    unsigned count = 0, len16 = 0;
    bool any = false;
    while (count < kMaxLineUnits && it.Next(u)) {
        unsigned kept = u.ncp < kMaxClusterCps ? u.ncp : kMaxClusterCps;
        unsigned need = 0;
        for (unsigned i = 0; i < kept; ++i) need += u.cps[i] >= 0x10000 ? 2 : 1;
        if (len16 + need > kMaxBreakUnits) break;
        st.first[count] = u.cps[0];
        st.last[count] = u.cps[kept - 1];
        st.at16[count] = (unsigned short)len16;
        for (unsigned i = 0; i < kept; ++i) {
            unsigned cp = u.cps[i];
            if (cp >= 0x10000) {
                st.text16[len16++] = (wchar_t)(0xD800 + ((cp - 0x10000) >> 10));
                st.text16[len16++] = (wchar_t)(0xDC00 + ((cp - 0x10000) & 0x3FF));
            } else {
                st.text16[len16++] = (wchar_t)cp;
            }
        }
        if (NoSpaceLetter(u.cps[0]) || u.cps[0] == 0x200B) any = true;
        ++count;
    }
    if (!any) return;
    st.at16[count] = (unsigned short)len16;
    bool useIcu = false;
    if (const IcuApi *icu = Icu()) {
        for (unsigned i = 0; i <= len16; ++i) st.bound[i] = 0;
        useIcu = icu->boundaries(st.text16, (int)len16, st.bound);
    }
    for (unsigned i = 1; i < count; ++i) {
        unsigned before = st.first[i - 1], after = st.first[i], last = st.last[i - 1];
        if (before == ' ' || before == '\n' || after == ' ' || after == '\n') continue;
        if (!(NoSpaceLetter(before) || NoSpaceLetter(after) || last == 0x200B)) continue;
        st.brk[i] = (useIcu ? st.bound[st.at16[i]] != 0 : (last == 0x200B || FallbackMayBreak(before, after))) ? 1 : 0;
    }
    // Without ICU, a run of Thai, Lao, Khmer or Burmese letters breaks only between its words (b200words.h): from
    // the run's start the longest listed word that ends at a whole character, else one character, and so on.
    if (useIcu || !WordLookup() || !WordListMax()) return;
    unsigned word[64];
    for (unsigned a = 0; a < count;) {
        int list = WordListOf(st.first[a]);
        unsigned b = a + 1;
        if (list >= 0) while (b < count && WordListOf(st.first[b]) == list) ++b;
        unsigned longest = list >= 0 && b - a > 1 ? WordListMax()(list) : 0;
        if (longest > 64) longest = 64;
        if (longest) {
            for (unsigned i = a + 1; i < b; ++i) st.brk[i] = 0;
            for (unsigned pos = a; pos < b;) {
                unsigned best = pos + 1, wn = 0;
                bool full = false;
                for (unsigned k = pos; k < b && !full; ++k) {
                    for (unsigned q = st.at16[k]; q < st.at16[k + 1]; ++q) {
                        unsigned cp = st.text16[q];
                        if (cp >= 0xD800 && cp <= 0xDBFF && q + 1 < st.at16[k + 1]) {
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (st.text16[q + 1] - 0xDC00u);
                            ++q;
                        }
                        if (wn >= longest) { full = true; break; }
                        word[wn++] = cp;
                    }
                    if (!full && WordLookup()(list, word, wn)) best = k + 1;
                }
                if (best < b) st.brk[best] = 1;
                pos = best;
            }
        }
        a = b;
    }
}

inline unsigned WriteLine(const unsigned char *src, LineState &st, unsigned k, unsigned char *out) {
    unsigned n = 0;
    for (unsigned i = 0; i < k; ++i) {
        if (st.bufSpace[i] && st.bufSize[i] == 0) { out[n++] = ' '; continue; }
        for (unsigned j = 0; j < st.bufSize[i]; ++j) out[n++] = src[st.bufStart[i] + j];
    }
    out[n] = 0;
    return n;
}

// The line is too long at the unit buf[esi] (written, unless !written: a character that would pass the byte limit).
// p is the source unit after it. The line ends at the nearest place a line may break at or before it.
inline unsigned Overflow(const unsigned char *src, LineState &st, unsigned esi, unsigned p, bool written, int maxBytes,
                         int maxWidth, unsigned char *out) {
    for (unsigned b = esi; b >= 1; --b) {
        if (st.brk[st.bufSrc[b]]) { WriteLine(src, st, b, out); return st.offs[st.bufSrc[b]]; }   // UAX #14
        if (st.bufSpace[b - 1]) { WriteLine(src, st, b - 1, out); return st.offs[p - (esi - (b - 1))]; }   // the stock walk back
    }
    // no place: one word wider than the line. Its longest start of whole characters that fits, at least one.
    unsigned n = written ? esi + 1 : esi, best = 0;
    int w = 0, bytes = 0;
    for (unsigned k = 1; k <= n; ++k) {
        w += st.bufW[k - 1];
        bytes += st.bufBytes[k - 1];
        if (w <= maxWidth && (maxBytes <= 0 || bytes < maxBytes)) best = k;
    }
    if (!best && n && (maxBytes <= 0 || st.bufBytes[0] < maxBytes)) best = 1;
    if (!best) { out[0] = 0; return st.offs[p]; }              // nothing fits (a character larger than the buffer)
    WriteLine(src, st, best, out);
    return st.offs[st.bufSrc[best - 1] + 1];
}

inline unsigned NextLine(const unsigned char *src, unsigned char *out, int maxBytes, int maxWidth, bool *doubleBreak,
                         bool keepNewline, float scale, int kerning, WidthFn width, void *ctx, LineState &st) {
    *doubleBreak = false;
    unsigned srcLen = Length(src);
    ComputeBreaks(src, srcLen, st);
    Units it;
    it.Init(src, srcLen);
    Unit u;
    unsigned nunits = 0;
    st.offs[0] = 0;
    // the units, read as the loop needs them
    unsigned esi = 0, p = 0;
    int count = 0, wsum = 0;
    bool prevNewline = false;
    auto unitAt = [&](unsigned k, Unit &out_u) -> bool {
        while (nunits <= k) {
            if (nunits >= kMaxLineUnits || !it.Next(u)) return false;
            st.offs[nunits + 1] = u.start + u.size;
            ++nunits;
            if (nunits - 1 == k) { out_u = u; return true; }
        }
        // re-read a unit already seen: decode again from its offset
        Units again;
        again.s = src; again.n = it.n; again.pos = st.offs[k];
        return again.Next(out_u);
    };
    for (;;) {
        Unit cur;
        if (!unitAt(p, cur)) break;
        unsigned start = p;
        bool space = false;
        unsigned bstart = cur.start, bsize = cur.size;
        Unit measured = cur;
        if (cur.IsNewline()) {
            ++p;
            if (prevNewline) { WriteLine(src, st, esi, out); *doubleBreak = true; return st.offs[p]; }
            prevNewline = true;
            if (count == 0 || st.bufSpace[esi - 1]) continue;
            if (!keepNewline) { WriteLine(src, st, esi, out); return st.offs[p]; }
            space = true; bsize = 0;
            measured.ncp = 1; measured.cps[0] = 0x20; measured.size = 1;
        } else {
            prevNewline = false;
            if (cur.IsSpace() && (count == 0 || st.bufSpace[esi - 1])) { ++p; continue; }
            space = cur.IsSpace();
        }
        unsigned usize = space ? 1 : cur.size;
        if (esi >= kMaxLineUnits) { WriteLine(src, st, esi, out); return st.offs[p]; }
        st.bufStart[esi] = bstart; st.bufSize[esi] = space && bsize == 0 ? 0 : bsize;
        st.bufSpace[esi] = space; st.bufSrc[esi] = start;
        st.bufBytes[esi] = (unsigned short)(usize < 0xFFFF ? usize : 0xFFFF);
        st.bufW[esi] = 0;
        if (maxBytes > 0 && usize > 1 && count + (int)usize > maxBytes)
            return Overflow(src, st, esi, start + 1, false, maxBytes, maxWidth, out);
        int w = width(ctx, measured);
        count += (int)usize;
        p = start + 1;
        int add = (int)F32(F32((float)(kerning + w)) * scale);
        st.bufW[esi] = add;
        wsum += add;
        if (wsum > maxWidth || (maxBytes > 0 && count >= maxBytes)) {
            if (st.bufSpace[esi]) { WriteLine(src, st, esi, out); return st.offs[p]; }
            return Overflow(src, st, esi, p, true, maxBytes, maxWidth, out);
        }
        ++esi;
    }
    WriteLine(src, st, esi, out);
    return st.offs[p];
}

}  // namespace ut
