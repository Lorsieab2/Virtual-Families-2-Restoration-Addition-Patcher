// The slot's Names file, read by both DLLs (b200names.inc LoadSlot in the Unicode text DLL, b200history.cpp LoadWhole in
// the Family History DLL) by one rule, the same as src/vf2_names.py:
//
//   "VF2 Names 2" LF, then one record per line: short <TAB> room <TAB> whole name <TAB> CRC-32 LF
//   "VF2 Names 1" LF (written by B207): short <TAB> room <TAB> whole name LF, no checksum
//
// The text is UTF-8. The CRC-32 (IEEE, the zlib one) is 8 hex digits (written in upper case) over every byte of the
// record before its last tab. A record whose checksum does not match, or that is cut short or merged with another, is
// skipped. A "VF2 Names 1" file is still read.
#pragma once

namespace nf {

inline unsigned Crc32(const unsigned char *p, unsigned n) {
    unsigned crc = 0xFFFFFFFFu;
    for (unsigned i = 0; i < n; ++i) {
        crc ^= p[i];
        for (int k = 0; k < 8; ++k) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

// The 8 upper-case hex digits of crc.
inline void Hex8(unsigned crc, unsigned char *out) {
    static const char digits[] = "0123456789ABCDEF";
    for (unsigned i = 0; i < 8; ++i) out[i] = (unsigned char)digits[(crc >> (28 - 4 * i)) & 0xF];
}

// The file's version (1 or 2) and where its first record starts (in *at); 0 for a file that is not a Names file.
inline int Header(const unsigned char *text, unsigned size, unsigned *at) {
    static const char v1[] = "VF2 Names 1", v2[] = "VF2 Names 2";
    int version = 0;
    for (int v = 1; v <= 2 && !version; ++v) {
        const char *h = v == 1 ? v1 : v2;
        unsigned i = 0;
        while (h[i] && i < size && text[i] == (unsigned char)h[i]) ++i;
        if (!h[i]) version = v;
    }
    if (!version) return 0;
    unsigned i = 11;
    if (i < size && text[i] == '\r') ++i;
    if (i >= size || text[i] != '\n') return 0;
    *at = i + 1;
    return version;
}

inline bool HexValue(unsigned char c, unsigned *v) {
    if (c >= '0' && c <= '9') { *v = c - '0'; return true; }
    if (c >= 'A' && c <= 'F') { *v = c - 'A' + 10; return true; }
    if (c >= 'a' && c <= 'f') { *v = c - 'a' + 10; return true; }
    return false;
}

// One record, text[at, stop) (without its LF or CR LF): its two tabs before the whole name, where the whole name ends
// (*bodyEnd: the last tab of a version 2 record, else stop) and the room. False when the record is not whole: no
// room digits, or (version 2) no checksum, a checksum that is not 8 hex digits, or one that does not match.
inline bool Split(const unsigned char *text, unsigned at, unsigned stop, int version, unsigned *tab1, unsigned *tab2,
                  unsigned *bodyEnd, unsigned *room) {
    unsigned body = stop;
    if (version == 2) {
        unsigned last = stop;
        while (last > at && text[last - 1] != '\t') --last;
        if (last <= at || stop - last != 8) return false;          // last is just after the last tab
        unsigned want = 0, v;
        for (unsigned i = 0; i < 8; ++i) {
            if (!HexValue(text[last + i], &v)) return false;
            want = (want << 4) | v;
        }
        body = last - 1;
        if (Crc32(text + at, body - at) != want) return false;
    }
    unsigned t1 = at;
    while (t1 < body && text[t1] != '\t') ++t1;
    unsigned t2 = t1 + 1;
    while (t2 < body && text[t2] != '\t') ++t2;
    if (t1 >= body || t2 >= body || t2 <= t1 + 1) return false;
    unsigned r = 0;
    for (unsigned i = t1 + 1; i < t2; ++i) {
        if (text[i] < '0' || text[i] > '9' || r > 100000) return false;
        r = r * 10 + (text[i] - '0');
    }
    *tab1 = t1; *tab2 = t2; *bodyEnd = body; *room = r;
    return true;
}

}  // namespace nf
