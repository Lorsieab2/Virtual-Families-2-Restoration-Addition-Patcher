// Shaped and right-to-left scripts: which stretches of a text the Unicode text DLL draws as one shaped RUN (the
// shared spec's row 3; src/vf2_shaping.py is the same rule, tests/test_shaping.py proves the two equal). The rule is
// Virtual Villagers' (text_utf8.h UT_RUN) and Virtual Families 1's (native/vf1text/shape.inc):
//
// Arabic, Hebrew, Syriac, Thaana, the Indic scripts, Thai, Lao, Tibetan, Myanmar, Khmer, Mongolian and the other
// scripts whose letters change shape with their neighbours or run right to left were drawn one whole character at a
// time, each in its isolated form and in logical order. A run of such letters is drawn as ONE piece by GDI's
// ExtTextOutW of the whole run, which shapes it (Uniscribe: joining forms, ligatures, conjuncts, stacked marks) and
// lays it out in visual order (the bidi algorithm, left-to-right base), as Windows draws it in its own windows.
//
// A run is whole characters of one script group, and the spaces between two of its words; any other character ends it.
// It is at most kMaxRunUnits characters and kMaxRunBytes bytes; a longer one is cut at its last space. A run of one
// character is not a run (it is drawn as before). Included by b200unicode.cpp and b200unicode_texttest.cpp, after
// b200unicode_text.h.
#pragma once

namespace sh {

struct Range { unsigned first, last; unsigned char group; bool rtl; };
static const Range kComplex[] = {     // sorted, not overlapping (src/vf2_shaping.COMPLEX_RANGES; VF1 shape.inc)
    { 0x0590, 0x05FF, 1, true },      // Hebrew
    { 0x0600, 0x08FF, 2, true },      // Arabic, Syriac, Arabic Supplement, Thaana, NKo, Samaritan, Mandaic, Arabic Ext.
    { 0x0900, 0x097F, 3, false },     // Devanagari
    { 0x0980, 0x09FF, 4, false },     // Bengali
    { 0x0A00, 0x0A7F, 5, false },     // Gurmukhi
    { 0x0A80, 0x0AFF, 6, false },     // Gujarati
    { 0x0B00, 0x0B7F, 7, false },     // Oriya
    { 0x0B80, 0x0BFF, 8, false },     // Tamil
    { 0x0C00, 0x0C7F, 9, false },     // Telugu
    { 0x0C80, 0x0CFF, 10, false },    // Kannada
    { 0x0D00, 0x0D7F, 11, false },    // Malayalam
    { 0x0D80, 0x0DFF, 12, false },    // Sinhala
    { 0x0E00, 0x0E7F, 13, false },    // Thai
    { 0x0E80, 0x0EFF, 14, false },    // Lao
    { 0x0F00, 0x0FFF, 15, false },    // Tibetan
    { 0x1000, 0x109F, 16, false },    // Myanmar
    { 0x1780, 0x17FF, 17, false },    // Khmer
    { 0x1800, 0x18AF, 18, false },    // Mongolian
    { 0x1900, 0x194F, 19, false },    // Limbu
    { 0x1980, 0x19DF, 20, false },    // New Tai Lue
    { 0x1A00, 0x1AAF, 21, false },    // Buginese, Tai Tham
    { 0x1B00, 0x1BBF, 22, false },    // Balinese, Sundanese
    { 0x1BC0, 0x1BFF, 23, false },    // Batak
    { 0x1C00, 0x1C4F, 24, false },    // Lepcha
    { 0xA800, 0xA82F, 25, false },    // Syloti Nagri
    { 0xA880, 0xA8DF, 26, false },    // Saurashtra
    { 0xA8E0, 0xA8FF, 3, false },     // Devanagari Extended
    { 0xA900, 0xA92F, 27, false },    // Kayah Li
    { 0xA930, 0xA95F, 28, false },    // Rejang
    { 0xA980, 0xA9DF, 29, false },    // Javanese
    { 0xA9E0, 0xA9FF, 16, false },    // Myanmar Extended-B
    { 0xAA00, 0xAA5F, 30, false },    // Cham
    { 0xAA60, 0xAA7F, 16, false },    // Myanmar Extended-A
    { 0xAA80, 0xAADF, 31, false },    // Tai Viet
    { 0xABC0, 0xABFF, 32, false },    // Meetei Mayek
    { 0xFB1D, 0xFB4F, 1, true },      // Hebrew presentation forms
    { 0xFB50, 0xFDFF, 2, true },      // Arabic presentation forms A
    { 0xFE70, 0xFEFF, 2, true },      // Arabic presentation forms B
    { 0x10800, 0x10FFF, 33, true },   // the right-to-left historic scripts (Cypriot .. Old Uyghur)
    { 0x11000, 0x11FFF, 34, false },  // Brahmi and the other Indic scripts of the supplementary plane
    { 0x1E800, 0x1EFFF, 35, true },   // Mende Kikakui, Adlam, Arabic Mathematical
};
static const unsigned kMaxRunUnits = 64;
static const unsigned kMaxRunBytes = 380;

inline int Group(unsigned cp) {
    int lo = 0, hi = (int)(sizeof(kComplex) / sizeof(kComplex[0])) - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (cp < kComplex[mid].first) hi = mid - 1;
        else if (cp > kComplex[mid].last) lo = mid + 1;
        else return kComplex[mid].group;
    }
    return 0;
}

inline bool PlainSpace(const ut::Unit &v) { return v.ncp == 1 && v.cps[0] == 0x20 && v.size == 1; }

// The end (a byte offset) of the shaped run that starts with the character u, `after` being the characters that
// follow it; 0 when the run is that one character (src/vf2_shaping.run_end).
inline unsigned RunEnd(const ut::Units &after, const ut::Unit &u) {
    int group = Group(u.cps[0]);
    if (!group) return 0;
    ut::Units it = after;
    ut::Unit v;
    unsigned first = u.start + u.size, end = first, units = 1, bytes = u.size, lastSpace = 0;
    bool capped = false;
    while (it.Next(v)) {
        if (Group(v.cps[0]) == group) {
            if (units >= kMaxRunUnits || bytes + v.size > kMaxRunBytes) { capped = true; break; }
            end = v.start + v.size;
            bytes += v.size;
            ++units;
            continue;
        }
        if (!PlainSpace(v)) break;
        unsigned spaceAt = v.start, spaces = 1;
        bool letter = false;
        while (it.Next(v)) {
            if (PlainSpace(v)) { ++spaces; continue; }
            letter = Group(v.cps[0]) == group;
            break;
        }
        if (!letter) break;                                     // spaces end the run unless its script goes on
        if (units + spaces >= kMaxRunUnits || bytes + spaces > kMaxRunBytes) { capped = true; break; }
        lastSpace = spaceAt;
        units += spaces;
        bytes += spaces;
        if (units >= kMaxRunUnits || bytes + v.size > kMaxRunBytes) { capped = true; break; }   // the next letter
        end = v.start + v.size;
        bytes += v.size;
        ++units;
    }
    if (capped && lastSpace > u.start) end = lastSpace;
    return end > first ? end : 0;
}

}  // namespace sh
