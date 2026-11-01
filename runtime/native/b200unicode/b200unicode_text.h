// The Unicode Text rules in C++, with no Windows and no C runtime: the companion DLL vf2unicode_b200.dll uses them in
// the game, and runtime/native/b200unicode/b200unicode_texttest.cpp builds them into a 64-bit test DLL the tests
// call next to src/vf2_game_text.py (the same rules in Python), text by text.
//
// * the stored form: valid UTF-8 with a byte of 80h or more is UTF-8; anything else is one byte per character
//   (ASCII, Latin-1 for A0h..FFh, Windows-1252 for 80h..9Fh, the five bytes it leaves out as themselves);
// * encode: ASCII, U+00A0..U+00FF and the Windows-1252 characters are single bytes unless those bytes would read as
//   UTF-8; anything else is UTF-8;
// * characters: a simplified extended grapheme cluster (b200unicode_tables.h EXTEND; ZWJ joins the next; regional
//   indicators pair; CR LF);
// * the stock text functions with a character in place of a byte: GetWidth and GetNextJustifiedLine, given each
//   character's glyph width by the caller.
#pragma once

#include "b200unicode_tables.h"

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

// A character after which a line may break with no space (CJK, kana, Hangul, fullwidth forms).
inline bool IsWide(unsigned cp) {
    return (cp >= 0x1100 && cp <= 0x115F) || (cp >= 0x2E80 && cp <= 0xA4CF) || (cp >= 0xAC00 && cp <= 0xD7A3) ||
           (cp >= 0xF900 && cp <= 0xFAFF) || (cp >= 0xFE30 && cp <= 0xFE4F) || (cp >= 0xFF00 && cp <= 0xFF60) ||
           (cp >= 0xFFE0 && cp <= 0xFFE6) || (cp >= 0x20000 && cp <= 0x3FFFD);
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

// The stored-form test: valid UTF-8 holding at least one byte of 80h or more.
inline bool IsUtf8(const unsigned char *s, unsigned n) {
    bool high = false;
    unsigned i = 0, cp;
    while (i < n) {
        if (s[i] >= 0x80) high = true;
        unsigned k = Utf8Seq(s + i, n - i, &cp);
        if (!k) return false;
        i += k;
    }
    return high;
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
    bool utf8;

    void Init(const unsigned char *text, unsigned length) {
        s = text; n = length; pos = 0; utf8 = IsUtf8(text, length);
    }
    bool Peek(unsigned at, unsigned *cp, unsigned *len) const {
        if (at >= n) return false;
        *len = Utf8Seq(s + at, n - at, cp);
        return *len != 0;
    }
    bool Next(Unit &u) {
        if (pos >= n) return false;
        u.start = pos;
        u.ncp = 0;
        if (!utf8) {
            u.size = 1;
            u.cps[0] = SingleByteChar(s[pos]);
            u.ncp = 1;
            ++pos;
            return true;
        }
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

// The stored form of the code points (no terminating 0). Returns the length, or -1 if more than cap bytes.
inline int Encode(const unsigned *cps, unsigned count, unsigned char *out, unsigned cap) {
    bool single = true;
    for (unsigned i = 0; i < count && single; ++i) if (cps[i] == 0 || SingleByteOf(cps[i]) < 0) single = false;
    if (single) {
        if (count <= cap) {
            unsigned n = 0;
            for (unsigned i = 0; i < count; ++i) if (cps[i]) out[n++] = (unsigned char)SingleByteOf(cps[i]);
            if (!IsUtf8(out, n)) return (int)n;
        } else {
            return -1;
        }
    }
    unsigned n = 0;
    unsigned char seq[4];
    for (unsigned i = 0; i < count; ++i) {
        if (!cps[i]) continue;
        unsigned k = PutUtf8(cps[i], seq);
        if (n + k > cap) return -1;
        for (unsigned j = 0; j < k; ++j) out[n++] = seq[j];
    }
    return (int)n;
}

// Every code point of a stored text (up to cap), in order.
inline unsigned Decode(const unsigned char *s, unsigned n, unsigned *cps, unsigned cap) {
    unsigned count = 0;
    if (IsUtf8(s, n)) {
        unsigned i = 0, cp;
        while (i < n && count < cap) { unsigned k = Utf8Seq(s + i, n - i, &cp); if (!k) break; cps[count++] = cp; i += k; }
    } else {
        for (unsigned i = 0; i < n && count < cap; ++i) cps[count++] = SingleByteChar(s[i]);
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
static const unsigned kMaxLineUnits = 4096;

struct LineState {
    unsigned bufStart[kMaxLineUnits];   // the source bytes each written unit came from (a newline: none)
    unsigned bufSize[kMaxLineUnits];
    bool bufSpace[kMaxLineUnits];
    bool bufWide[kMaxLineUnits];
    unsigned offs[kMaxLineUnits + 1];   // source byte offset of unit k
};

inline unsigned WriteLine(const unsigned char *src, LineState &st, unsigned k, unsigned char *out) {
    unsigned n = 0;
    for (unsigned i = 0; i < k; ++i) {
        if (st.bufSpace[i] && st.bufSize[i] == 0) { out[n++] = ' '; continue; }
        for (unsigned j = 0; j < st.bufSize[i]; ++j) out[n++] = src[st.bufStart[i] + j];
    }
    out[n] = 0;
    return n;
}

inline unsigned WalkBack(const unsigned char *src, LineState &st, unsigned esi, unsigned p, unsigned char *out) {
    for (;;) {
        if (esi == 0) { out[0] = 0; return st.offs[p]; }
        --esi;
        --p;
        if (st.bufSpace[esi]) { WriteLine(src, st, esi, out); return st.offs[p]; }
    }
}

inline unsigned NextLine(const unsigned char *src, unsigned char *out, int maxBytes, int maxWidth, bool *doubleBreak,
                         bool keepNewline, float scale, int kerning, WidthFn width, void *ctx, LineState &st) {
    *doubleBreak = false;
    Units it;
    it.Init(src, Length(src));
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
        again.s = src; again.n = it.n; again.pos = st.offs[k]; again.utf8 = it.utf8;
        return again.Next(out_u);
    };
    for (;;) {
        Unit cur;
        if (!unitAt(p, cur)) break;
        unsigned start = p;
        bool space = false;
        unsigned bstart = cur.start, bsize = cur.size;
        bool wide = cur.ncp && IsWide(cur.cps[0]);
        Unit measured = cur;
        if (cur.IsNewline()) {
            ++p;
            if (prevNewline) { WriteLine(src, st, esi, out); *doubleBreak = true; return st.offs[p]; }
            prevNewline = true;
            if (count == 0 || st.bufSpace[esi - 1]) continue;
            if (!keepNewline) { WriteLine(src, st, esi, out); return st.offs[p]; }
            space = true; bsize = 0; wide = false;
            measured.ncp = 1; measured.cps[0] = 0x20; measured.size = 1;
        } else {
            prevNewline = false;
            if (cur.IsSpace() && (count == 0 || st.bufSpace[esi - 1])) { ++p; continue; }
            space = cur.IsSpace();
        }
        unsigned usize = space ? 1 : cur.size;
        if (esi >= kMaxLineUnits) { WriteLine(src, st, esi, out); return st.offs[p]; }
        st.bufStart[esi] = bstart; st.bufSize[esi] = space && bsize == 0 ? 0 : bsize;
        st.bufSpace[esi] = space; st.bufWide[esi] = wide;
        if (maxBytes > 0 && usize > 1 && count + (int)usize > maxBytes) return WalkBack(src, st, esi, start + 1, out);
        int w = width(ctx, measured);
        count += (int)usize;
        p = start + 1;
        wsum += (int)F32(F32((float)(kerning + w)) * scale);
        if (wsum > maxWidth || (maxBytes > 0 && count >= maxBytes)) {
            if (st.bufSpace[esi]) { WriteLine(src, st, esi, out); return st.offs[p]; }
            if (st.bufWide[esi] || (esi > 0 && st.bufWide[esi - 1])) {
                if (esi == 0) { WriteLine(src, st, 1, out); return st.offs[p]; }
                WriteLine(src, st, esi, out);
                return st.offs[p - 1];
            }
            return WalkBack(src, st, esi, p, out);
        }
        ++esi;
    }
    WriteLine(src, st, esi, out);
    return st.offs[p];
}

}  // namespace ut
