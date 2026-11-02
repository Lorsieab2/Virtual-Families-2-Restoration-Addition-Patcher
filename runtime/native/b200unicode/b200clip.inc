// "Copy and Paste in Text Boxes" (copy_paste_text_boxes): included by b200unicode.cpp when it is built as
// vf2clip_b200.dll (B200UNICODE_CLIP). One feature, its own DLL: it installs only the SDL_PollEvent import slot (the
// same chain the Unicode text DLL uses: each DLL calls the slot's previous function), and works with either Unicode
// setting on or with both off.
//
// Only while one of the game's own text boxes has the typing focus (the first ldwTextControlImpl that is editing in
// ldwEventManager's key order, before a handler that stops the keys - the box the game's own HandleKey would give a
// letter to):
//   Ctrl+V, Shift+Insert   paste the clipboard (CF_UNICODETEXT) at the caret (the end: the game's box has no other)
//   Ctrl+C, Ctrl+Insert    copy the box's whole text as Unicode
//   Ctrl+X                 cut the box's whole text
// Pasted text: CR, LF and Tab become one space each; other control characters and lone surrogates are dropped; it is
// cut to the box's own byte limit at whole characters (grapheme clusters). With a Unicode text setting on the text is
// stored in the patcher's one stored form (b200unicode_text.h, as typing stores it); with both off only
// Windows-1252 characters are pasted, one byte each, and the rest are dropped. A number-only box takes digits only.
// The key events are hidden from the game (it never sees them as letters); anywhere else the keys do nothing new.

static const unsigned kSdlKeyDown = 0x300, kSdlKeyUp = 0x301;
static const int kSdlkInsert = 0x40000049;
static const unsigned kModShift = 0x0003, kModCtrl = 0x00C0, kModAlt = 0x0300;
enum ClipOp { kClipNone = 0, kClipPaste = 1, kClipCopy = 2, kClipCut = 3 };

// B200Clip_Status: magic 'CLIP', version, installed, pasted (characters), copied (texts), cut (texts), dropped
// (characters left out of a paste), unicode (1 when the last paste used the stored form, 0 for Windows-1252)
struct ClipStatus { unsigned magic, version, installed, pasted, copied, cut, dropped, unicode; };
extern "C" __declspec(dllexport) volatile ClipStatus B200Clip_Status = { 0x50494C43u, 1u, 0, 0, 0, 0, 0, 0 };

static ClipOp ClipOpFor(int sym, unsigned mod) {
    bool ctrl = (mod & kModCtrl) != 0, shift = (mod & kModShift) != 0, alt = (mod & kModAlt) != 0;
    if (alt) return kClipNone;
    if (ctrl && !shift) {
        if (sym == 'v') return kClipPaste;
        if (sym == 'c' || sym == kSdlkInsert) return kClipCopy;
        if (sym == 'x') return kClipCut;
    }
    if (shift && !ctrl && sym == kSdlkInsert) return kClipPaste;
    return kClipNone;
}

static bool BoxEditing(unsigned c) {
    return *(unsigned char *)(c + 0x25) && *(unsigned *)(c + 0x1C) && *(unsigned char *)(*(unsigned *)(c + 0x1C) + 8);
}

// The text box that has the typing focus, or 0: ldwEventManager's handler list in the order its HandleKey walks it
// (node: +0 handler, +4 flags (2 = takes keys), +8 stops the walk, +0Ch next).
static unsigned FocusedBox() {
    unsigned mgr = (unsigned)((EventsGetFn)SITE(EVENTS_GET))();
    if (!mgr || !*(unsigned *)mgr) return 0;
    unsigned node = *(unsigned *)*(unsigned *)mgr;
    for (unsigned guard = 0; node && guard < 4096; ++guard) {
        unsigned handler = *(unsigned *)node;
        if ((*(unsigned *)(node + 4) & 2) && handler) {
            if (*(unsigned *)handler == TextVtable && BoxEditing(handler)) return handler;
            if (*(unsigned char *)(node + 8)) return 0;
        }
        node = *(unsigned *)(node + 0x0C);
    }
    return 0;
}

// Is a Unicode text setting on in this game (its DLL loaded and installed)?
static bool UnicodeOn() {
    const wchar_t *names[2] = { L"vf2unicode_b200.dll", L"vf2unicodefont_b200.dll" };
    for (unsigned i = 0; i < 2; ++i) {
        HMODULE m = GetModuleHandleW(names[i]);
        if (!m) continue;
        const UnicodeStatus *s = (const UnicodeStatus *)GetProcAddress(m, "B200Unicode_Status");
        if (s && s->magic == UNI_STATUS_MAGIC && s->installed) return true;
    }
    return false;
}

// Windows-1252 bytes 80h..9Fh
static const unsigned short kCp1252High[32] = {
    0x20AC, 0, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0, 0x017D, 0,
    0, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0, 0x017E, 0x0178 };

static int Cp1252Byte(unsigned cp) {
    if ((cp >= 0x20 && cp < 0x7F) || (cp >= 0xA0 && cp <= 0xFF)) return (int)cp;
    for (unsigned i = 0; i < 32; ++i) if (kCp1252High[i] && kCp1252High[i] == cp) return (int)(0x80 + i);
    return -1;
}

static unsigned Cp1252Char(unsigned char b) {
    if (b >= 0x80 && b < 0xA0) return kCp1252High[b - 0x80] ? kCp1252High[b - 0x80] : b;
    return b;
}

// The clipboard's text as code points, cleaned: CR / LF / Tab -> a space each, other controls and lone surrogates
// left out. Returns the count (at most cap).
static unsigned ClipboardText(unsigned *cps, unsigned cap, unsigned &dropped) {
    unsigned n = 0;
    dropped = 0;
    if (!OpenClipboard(GetActiveWindow())) return 0;
    HANDLE h = GetClipboardData(CF_UNICODETEXT);
    const wchar_t *w = h ? (const wchar_t *)GlobalLock(h) : 0;
    if (w) {
        for (unsigned i = 0; w[i] && n < cap; ++i) {
            unsigned u = w[i];
            if (u >= 0xD800 && u <= 0xDBFF) {
                unsigned lo = w[i + 1];
                if (lo >= 0xDC00 && lo <= 0xDFFF) { cps[n++] = 0x10000 + ((u - 0xD800) << 10) + (lo - 0xDC00); ++i; }
                else ++dropped;
                continue;
            }
            if (u >= 0xDC00 && u <= 0xDFFF) { ++dropped; continue; }
            if (u == 0x0D || u == 0x0A || u == 0x09) { cps[n++] = 0x20; continue; }
            if (u < 0x20 || u == 0x7F || (u >= 0x80 && u < 0xA0)) { ++dropped; continue; }
            cps[n++] = u;
        }
        GlobalUnlock(h);
    }
    CloseClipboard();
    return n;
}

// Writing needs an owner window (OpenClipboard(NULL) + EmptyClipboard leaves no owner and SetClipboardData fails):
// the game's own window, which is active while a box is typed in. No window: nothing is copied and the clipboard is
// left as it was.
static bool SetClipboardText(const unsigned *cps, unsigned n) {
    HWND owner = GetActiveWindow();
    if (!owner || !OpenClipboard(owner)) return false;
    EmptyClipboard();
    HGLOBAL g = GlobalAlloc(GMEM_MOVEABLE, (n * 2 + 1) * sizeof(wchar_t));
    bool ok = false;
    if (g) {
        wchar_t *w = (wchar_t *)GlobalLock(g);
        unsigned k = 0;
        for (unsigned i = 0; i < n; ++i) {
            unsigned cp = cps[i];
            if (cp >= 0x10000) { cp -= 0x10000; w[k++] = (wchar_t)(0xD800 + (cp >> 10)); w[k++] = (wchar_t)(0xDC00 + (cp & 0x3FF)); }
            else w[k++] = (wchar_t)cp;
        }
        w[k] = 0;
        GlobalUnlock(g);
        ok = SetClipboardData(CF_UNICODETEXT, g) != 0;
        if (!ok) GlobalFree(g);
    }
    CloseClipboard();
    return ok;
}

static void Changed(unsigned box) {
    void *events = ((EventsGetFn)SITE(EVENTS_GET))();
    ((PostMessageFn)SITE(POST_MESSAGE))(events, 0x0C, *(long *)(box + 4));
}

static unsigned ClipCps[1300], ClipAdd[1300];
static char ClipBefore[1300];

// With a Unicode text setting on, each whole character (grapheme cluster) of the clipboard goes to the box the way
// typing does: through ldwEventManager::HandleKey, so the box's own rules apply (its byte limit, a number-only box, the
// stored form and the name-width cap of the Unicode text DLL's HandleKey). A character the box
// takes only part of is taken back whole (the text as it was before it); the paste stops at the first character that
// does not fit, and skips one the box refuses for another reason (a letter in a number-only box).
static void ClipPaste(unsigned box) {
    if (!*(char **)(box + 0x30) || *(int *)(box + 0x28) <= 0) return;
    unsigned dropped = 0;
    unsigned add = ClipboardText(ClipAdd, 1200, dropped);
    bool unicode = UnicodeOn();
    B200Clip_Status.unicode = unicode ? 1u : 0u;
    if (!unicode) {
        // both Unicode settings off: Windows-1252 bytes straight into the box (the stock HandleKey takes no byte
        // above 7Fh), to its byte limit; the rest are dropped
        char *buf = *(char **)(box + 0x30);
        unsigned max = (unsigned)*(int *)(box + 0x28), at = ut::Length((const unsigned char *)buf), pasted = 0;
        bool number = *(unsigned char *)(box + 0x2D) != 0;
        for (unsigned i = 0; i < add; ++i) {
            int b = Cp1252Byte(ClipAdd[i]);
            if (b < 0 || (number && (b < '0' || b > '9'))) { ++dropped; continue; }
            if (at >= max) { dropped += add - i; break; }
            buf[at++] = (char)b;
            ++pasted;
        }
        buf[at] = 0;
        B200Clip_Status.pasted += pasted;
        B200Clip_Status.dropped += dropped;
        if (pasted) Changed(box);
        return;
    }
    void *events = ((EventsGetFn)SITE(EVENTS_GET))();
    unsigned pasted = 0, start = 0;
    while (start < add) {
        unsigned end = ut::ClusterEnd(ClipAdd, add, start);
        char *buf = *(char **)(box + 0x30);
        unsigned before = ut::Length((const unsigned char *)buf);
        if (before >= sizeof(ClipBefore)) break;
        for (unsigned i = 0; i <= before; ++i) ClipBefore[i] = buf[i];
        bool skip = false;
        for (unsigned i = start; i < end && !skip; ++i) {
            unsigned cp = ClipAdd[i];
            if (cp < 0x80) ((EventsHandleKeyFn)SITE(EVENTS_HANDLE_KEY))(events, UNI_KEY_TYPE_CHARACTER, 0, (int)cp);
            else ((EventsHandleKeyFn)SITE(EVENTS_HANDLE_KEY))(events, UNI_KEY_TYPE_CHARACTER, (int)(cp | UNI_KEY_MARK), 0);
        }
        buf = *(char **)(box + 0x30);
        // taken whole? the text is the one before plus exactly this character
        unsigned now = ut::Length((const unsigned char *)buf);
        bool whole = !skip && now > before;
        if (whole) {
            unsigned n0 = ut::Decode((const unsigned char *)ClipBefore, before, ClipCps, 1290);
            unsigned n1 = ut::Decode((const unsigned char *)buf, now, ClipCps + 640, 640);
            whole = n1 == n0 + (end - start);
        }
        if (!whole) {
            bool changed = now != before;
            for (unsigned i = 0; i <= before; ++i) buf[i] = ClipBefore[i];   // back to the text before it
            if (changed) Changed(box);
            dropped += end - start;
            if (!skip && now <= before && !(*(unsigned char *)(box + 0x2D))) {   // the box is full: stop
                dropped += add - end;
                break;
            }
            if (changed && !skip) { dropped += add - end; break; }
            start = end;
            continue;
        }
        pasted += end - start;
        start = end;
    }
    B200Clip_Status.pasted += pasted;
    B200Clip_Status.dropped += dropped;
}

static bool ClipCopy(unsigned box) {
    const unsigned char *buf = *(const unsigned char **)(box + 0x30);
    if (!buf || *(unsigned char *)(box + 0x2F)) return false;          // a hidden (password) text is never copied
    unsigned n = ut::Length(buf), count = 0;
    if (UnicodeOn()) count = ut::Decode(buf, n, ClipCps, 1290);
    else for (unsigned i = 0; i < n && count < 1290; ++i) ClipCps[count++] = Cp1252Char(buf[i]);
    if (!SetClipboardText(ClipCps, count)) return false;
    ++B200Clip_Status.copied;
    return true;
}

static int __cdecl ClipPollEvent(void *event) {
    int r = RealPoll(event);
    if (!r || !event) return r;
    unsigned type = *(unsigned *)event;
    if (type != kSdlKeyDown && type != kSdlKeyUp) return r;
    int sym = *(int *)((unsigned char *)event + 0x14);
    unsigned mod = *(unsigned short *)((unsigned char *)event + 0x18);
    ClipOp op = ClipOpFor(sym, mod);
    if (op == kClipNone) return r;
    unsigned box = FocusedBox();
    if (!box) return r;                                                  // no text box: the keys do nothing new
    if (type == kSdlKeyDown) {
        if (op == kClipPaste) ClipPaste(box);
        else if (ClipCopy(box) && op == kClipCut) {
            char *buf = *(char **)(box + 0x30);
            buf[0] = 0;
            ++B200Clip_Status.cut;
            Changed(box);
        }
    }
    *(unsigned *)event = UNI_SDL_HIDDEN_EVENT;                          // never reaches the game
    return r;
}
