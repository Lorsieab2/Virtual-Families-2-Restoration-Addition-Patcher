// A test DLL (any bitness) of b200unicode_text.h alone: the rules the Unicode Text DLL uses in the game, called by
// tests/test_b200_unicode_text.py next to src/vf2_game_text.py. Never shipped.
//   cl /nologo /O2 /LD /EHsc b200unicode_texttest.cpp /Fe:vf2unicode_texttest.dll
#include "b200unicode_text.h"

#define EXPORT extern "C" __declspec(dllexport)

EXPORT int UtIsUtf8(const unsigned char *s, unsigned n) { return ut::IsUtf8(s, n) ? 1 : 0; }

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

EXPORT unsigned UtNextLine(const unsigned char *src, unsigned char *out, int maxBytes, int maxWidth, int keep,
                           float scale, int kerning, int *doubleBreak) {
    bool dbl = false;
    unsigned used = ut::NextLine(src, out, maxBytes, maxWidth, &dbl, keep != 0, scale, kerning, &TestWidth, 0, State);
    *doubleBreak = dbl ? 1 : 0;
    return used;
}

EXPORT unsigned UtFit(const unsigned char *s, unsigned n, unsigned maxBytes, unsigned char *out) {
    static unsigned cps[4096];
    return ut::Fit(s, n, maxBytes, out, cps, 4096);
}
