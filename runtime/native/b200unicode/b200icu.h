// Windows' own ICU for UAX #14 line breaking (b200unicode_text.h IcuApi), loaded only when a text has a letter of a
// script written without spaces: icu.dll from System32 (Windows 10 version 1903 and later; LOAD_LIBRARY_SEARCH_SYSTEM32,
// so a copy beside the game is never loaded): ubrk_open(UBRK_LINE), which also knows the Thai, Lao, Khmer and Myanmar
// words, and u_getIntPropertyValue(UCHAR_LINE_BREAK). Without it (an older Windows) the table of
// b200linebreak_table.h is used. Included by b200unicode.cpp (the DLL) and b200unicode_texttest.cpp (the test DLL).
#pragma once

namespace icu {

typedef void *(__cdecl *OpenFn)(int type, const char *locale, const wchar_t *text, int length, int *status);
typedef int (__cdecl *StepFn)(void *it);
typedef void (__cdecl *CloseFn)(void *it);
typedef int (__cdecl *PropertyFn)(unsigned cp, int which);

static OpenFn Open;
static StepFn First, Next;
static CloseFn Close;
static PropertyFn Property;
static bool Looked;

inline int LineClass(unsigned cp) { return Property(cp, 0x1008 /* UCHAR_LINE_BREAK */); }

// out[0..length]: 1 where ICU allows a line break (before the code unit at that index); false when ICU cannot be used.
inline bool Boundaries(const wchar_t *text, int length, unsigned char *out) {
    int status = 0;
    void *it = Open(2 /* UBRK_LINE */, "", text, length, &status);
    bool ok = it != 0 && status <= 0;
    if (ok) {
        for (int b = First(it); b >= 0 && b <= length; b = Next(it)) out[b] = 1;
    }
    if (it) Close(it);
    return ok;
}

static const ut::IcuApi kApi = { &LineClass, &Boundaries };

// Looks for icu.dll once; on success the text rules use it.
inline void Install() {
    if (Looked) return;
    Looked = true;
    HMODULE m = LoadLibraryExW(L"icu.dll", 0, 0x800 /* LOAD_LIBRARY_SEARCH_SYSTEM32 */);
    if (!m) return;
    Open = (OpenFn)GetProcAddress(m, "ubrk_open");
    First = (StepFn)GetProcAddress(m, "ubrk_first");
    Next = (StepFn)GetProcAddress(m, "ubrk_next");
    Close = (CloseFn)GetProcAddress(m, "ubrk_close");
    Property = (PropertyFn)GetProcAddress(m, "u_getIntPropertyValue");
    if (Open && First && Next && Close && Property) ut::Icu() = &kApi;
}

}  // namespace icu
