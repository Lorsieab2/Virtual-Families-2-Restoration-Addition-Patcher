// A test DLL (any bitness) of b200unicode_text.h alone: the rules the Unicode Text DLL uses in the game, called by
// tests/test_b200_unicode_text.py next to src/vf2_game_text.py. Never shipped.
//   cl /nologo /O2 /LD /EHsc b200unicode_texttest.cpp /Fe:vf2unicode_texttest.dll
#include <windows.h>
#include "b200unicode_text.h"
#include "b200icu.h"
#include "b200words.h"

#define EXPORT extern "C" __declspec(dllexport)


// starts, sizes, counts: one per unit; cps: kMaxClusterCps per unit. Returns the unit count.
EXPORT unsigned UtUnits(const unsigned char *s, unsigned n, unsigned *starts, unsigned *sizes, unsigned *counts,
                        unsigned *cps, unsigned cap) {
    ut::Units it;
    it.Init(s, n);
    ut::Unit u;
    unsigned k = 0;
    while (k < cap && it.Next(u)) {
        starts[k] = u.start; sizes[k] = u.size; counts[k] = u.ncp;
        for (unsigned i = 0; i < ut::kMaxClusterCps; ++i) cps[k * ut::kMaxClusterCps + i] = i < u.ncp ? u.cps[i] : 0;
        ++k;
    }
    return k;
}

EXPORT int UtEncode(const unsigned *cps, unsigned count, unsigned char *out, unsigned cap) {
    return ut::Encode(cps, count, out, cap);
}

EXPORT unsigned UtDecode(const unsigned char *s, unsigned n, unsigned *cps, unsigned cap) {
    return ut::Decode(s, n, cps, cap);
}

EXPORT unsigned UtComposed(const unsigned *cps, unsigned count) {
    ut::Unit u;
    u.start = 0; u.size = 0; u.ncp = count;
    for (unsigned i = 0; i < count && i < ut::kMaxClusterCps; ++i) u.cps[i] = cps[i];
    return ut::Composed(u);
}

// The test font: a character's width is (7 x the sum of its code points + 3 x their count) mod 13, a space 4.
static int TestWidth(void *, const ut::Unit &u) {
    if (u.IsSpace()) return 4;
    unsigned sum = 0;
    for (unsigned i = 0; i < u.ncp && i < ut::kMaxClusterCps; ++i) sum += u.cps[i];
    return (int)((7u * sum + 3u * u.ncp) % 13u);
}

EXPORT int UtGetWidth(const unsigned char *text, float scale, int kerning) {
    return ut::GetWidth(text, scale, kerning, &TestWidth, 0);
}

static ut::LineState State;

// 1: line breaking asks Windows' ICU (when this Windows has icu.dll; returns whether it does), 0: the built-in table
EXPORT int UtIcu(int on) {
    if (!on) { ut::Icu() = 0; ut::IcuLoader() = 0; return 0; }
    icu::Install();
    if (icu::Open && icu::First && icu::Next && icu::Close && icu::Property) ut::Icu() = &icu::kApi;   // on again
    ut::IcuLoader() = &icu::Install;
    return ut::Icu() != 0 ? 1 : 0;
}

// the word lists' folder (with its trailing backslash; empty: no lists), as the DLL's Startup sets it
EXPORT void UtWords(const wchar_t *folder) { words::Install(folder); }
// whether list i was read (looked for), and how many words it has
EXPORT unsigned UtWordsRead(int i) { return words::Lists[i].looked ? 1u + words::Lists[i].count : 0u; }

EXPORT unsigned UtNextLine(const unsigned char *src, unsigned char *out, int maxBytes, int maxWidth, int keep,
                           float scale, int kerning, int *doubleBreak) {
    bool dbl = false;
    unsigned used = ut::NextLine(src, out, maxBytes, maxWidth, &dbl, keep != 0, scale, kerning, &TestWidth, 0, State);
    *doubleBreak = dbl ? 1 : 0;
    return used;
}

// The places a line may break in a text (ut::ComputeBreaks): flags[k], k = 0..units, between unit k - 1 and k. Returns the
// unit count.
EXPORT unsigned UtBreaks(const unsigned char *s, unsigned n, unsigned char *flags, unsigned cap) {
    ut::ComputeBreaks(s, n, State);
    ut::Units it;
    it.Init(s, n);
    ut::Unit u;
    unsigned k = 0;
    while (k < ut::kMaxLineUnits && it.Next(u)) ++k;
    for (unsigned i = 0; i <= k && i < cap; ++i) flags[i] = State.brk[i];
    return k;
}

EXPORT unsigned UtFit(const unsigned char *s, unsigned n, unsigned maxBytes, unsigned char *out) {
    static unsigned cps[4096];
    return ut::Fit(s, n, maxBytes, out, cps, 4096);
}
