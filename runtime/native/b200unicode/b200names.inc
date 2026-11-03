// Names up to 1,200 bytes (docs/UNICODE_TEXT.md, "One limit for every name box"): included by
// b200unicode.cpp in vf2unicode_b200.dll and vf2unicodefont_b200.dll (not in the Copy and Paste DLL).
//
// * ldwTextControl::SetCanEdit called from one of the ten name-box calls (its return address, UNI_NAME_BOXES): the
//   box's limit is NAME_BOX_BYTES (1,200, the engine's own cap: SetCanEdit clamps every limit to 4B0h);
// * typing in a name box stops at the box's 1,200 bytes as stored (no separate character cap), a character (grapheme
//   cluster) going in whole or not at all;
// * GetText of a name box gives the game only the SHORT FORM of a longer name (at most size - 1 bytes, the stored
//   form, never more than the stock game could store): its start + "...", or "2...", "3..." when two would start
//   alike (src/vf2_names.short_form, the same rule); the whole name goes into the slot's Names file,
//   <saves>\Virtual Families 2 Patcher Data\Names\Virtual Families 2<N>.ldw.txt;
// * a name box given a short form (SetText / SetCanEdit) opens with the whole name; the box's Draw draws a copy
//   that fits (the end while it is typed into, the start with an ellipsis otherwise), so the stock draw, which
//   deletes bytes from the end of the box's own text until it fits, never cuts the name;
// * DrawString and GetWidth draw and measure the whole name wherever a short form is drawn, fitted with an
//   ellipsis into the width of as many "W" as the field holds bytes; DrawStringJustified (dialogs) gets the whole
//   name fitted into the short form's own width, so the stock wrapping and the heights measured from the stored
//   text still hold.
// Nothing else changes: the save keeps its fields; with both Unicode settings off the save shows the short forms.

// kNameBoxBytes (1,200): b200name_limit.h, the one C copy of src/vf2_game_text.NAME_BOX_BYTES, written by
// runtime/tools/gen_b200_name_limit.py (the Copy and Paste and Family History DLLs read the same header).
static const unsigned kMaxNames = 1024;
static const unsigned kMaxShort = 24;
static const unsigned kNameBoxes = 32;

static bool NamesOn;
static unsigned NSites[UNI_NSITE_COUNT];
#define NSITE(name) (NSites[UNI_NSITE_##name])
static unsigned NameReturns[UNI_NAME_BOX_COUNT];
static unsigned char SetCanEditTrampoline[16];
static unsigned char BoxDrawTrampoline[16];

struct NameEntry {
    unsigned slot, room, shortLen, wholeLen;
    unsigned char shortForm[kMaxShort + 1];
    unsigned char *whole;              // the stored form, nul-terminated
};
static NameEntry Names[kMaxNames];
static unsigned NameCount;
static bool SlotLoaded[6];

struct NameBox { unsigned impl; char kind; int expanded; };      // expanded: the entry its text is the whole name of
static NameBox Boxes[kNameBoxes];

static bool SameBytes(const unsigned char *a, unsigned an, const unsigned char *b, unsigned bn) {
    if (an != bn) return false;
    for (unsigned i = 0; i < an; ++i) if (a[i] != b[i]) return false;
    return true;
}

// ---------------------------------------------------------------- the boxes
static NameBox *BoxOf(unsigned impl) {
    if (!impl) return 0;
    for (unsigned i = 0; i < kNameBoxes; ++i) if (Boxes[i].impl == impl) return &Boxes[i];
    return 0;
}

static NameBox *AddBox(unsigned impl, char kind) {
    NameBox *b = BoxOf(impl);
    for (unsigned i = 0; !b && i < kNameBoxes; ++i) if (!Boxes[i].impl) b = &Boxes[i];
    if (!b) b = &Boxes[(impl >> 4) % kNameBoxes];
    b->impl = impl; b->kind = kind; b->expanded = -1;
    return b;
}

// ---------------------------------------------------------------- the game state
static unsigned GameStateNow() { return NamesOn ? *(const unsigned *)NSITE(GAME_STATE_INSTANCE) : 0; }

static unsigned CurrentSlot() {
    unsigned gs = GameStateNow();
    if (!gs) return 0;
    int slot = *(const int *)(gs + UNI_GS_CURRENT_SLOT);
    return slot >= 1 && slot <= 5 ? (unsigned)slot : 0;
}

typedef const char *(__thiscall *MakePathFn)(void *state, int slot);

// <save folder>\Virtual Families 2 Patcher Data\Names\<save file>.txt; folder (optional) gets the Names folder.
static bool NamesPath(unsigned slot, char *out, unsigned cap, char *folder) {
    unsigned gs = GameStateNow();
    if (!gs || slot < 1 || slot > 5) return false;
    const unsigned *vtable = *(const unsigned *const *)gs;
    if (!vtable) return false;
    const char *save = ((MakePathFn)vtable[UNI_GS_PATH_VSLOT / 4])((void *)gs, (int)slot);
    if (!save) return false;
    unsigned n = ut::Length((const unsigned char *)save);
    unsigned cut = n;
    while (cut > 0 && save[cut - 1] != '\\' && save[cut - 1] != '/') --cut;
    static const char middle[] = "Virtual Families 2 Patcher Data\\Names\\";
    unsigned m = sizeof(middle) - 1;
    if (n == 0 || cut == 0 || cut == n || n + m + 5 >= cap) return false;
    unsigned k = 0;
    for (unsigned i = 0; i < cut; ++i) out[k++] = save[i];
    for (unsigned i = 0; i < m; ++i) out[k++] = middle[i];
    if (folder) { for (unsigned i = 0; i < k - 1; ++i) folder[i] = out[i]; folder[k - 1] = 0; }
    for (unsigned i = cut; i < n; ++i) out[k++] = save[i];
    out[k++] = '.'; out[k++] = 't'; out[k++] = 'x'; out[k++] = 't'; out[k] = 0;
    return true;
}

// ---------------------------------------------------------------- the rule (src/vf2_names.py)
// A whole name the Names file may hold: at least one character, at most 1,200 bytes stored, no control characters.
static bool NameOk(const unsigned *cps, unsigned n, unsigned storedLen) {
    if (!n || storedLen > kNameBoxBytes) return false;
    for (unsigned i = 0; i < n; ++i)
        if (cps[i] < 0x20 || (cps[i] >= 0x7F && cps[i] < 0xA0) || (cps[i] >= 0xD800 && cps[i] <= 0xDFFF)) return false;
    return true;
}

static bool EndsWithMark(const unsigned char *s, unsigned n) {
    return n >= 3 && s[n - 1] == '.' && s[n - 2] == '.' && s[n - 3] == '.';
}

static int FindShort(const unsigned char *s, unsigned n, unsigned preferSlot) {
    int any = -1;
    for (unsigned i = 0; i < NameCount; ++i)
        if (SameBytes(Names[i].shortForm, Names[i].shortLen, s, n)) {
            if (Names[i].slot == preferSlot) return (int)i;
            if (any < 0) any = (int)i;
        }
    return any;
}

static bool Taken(const unsigned char *s, unsigned n) { return FindShort(s, n, 0) >= 0; }

static bool InSlot(unsigned slot, const unsigned char *s, unsigned n) {
    for (unsigned i = 0; i < NameCount; ++i)
        if (Names[i].slot == slot && SameBytes(Names[i].shortForm, Names[i].shortLen, s, n)) return true;
    return false;
}

// What a field of `room` bytes stores for the whole name `w` (stored form, n bytes): the short form, into out
// (room + 1 bytes). Returns its length.
static unsigned ShortFor(const unsigned char *w, unsigned n, unsigned room, unsigned char *out) {
    for (unsigned i = 0; i < NameCount; ++i)          // a short form already standing for this very name
        if (SameBytes(Names[i].whole, Names[i].wholeLen, w, n) && Names[i].shortLen <= room) {
            for (unsigned k = 0; k < Names[i].shortLen; ++k) out[k] = Names[i].shortForm[k];
            return Names[i].shortLen;
        }
    if (n <= room && !Taken(w, n)) {                  // it fits and is no other name's short form
        for (unsigned k = 0; k < n; ++k) out[k] = w[k];
        return n;
    }
    static unsigned cps[1300];
    static unsigned char head[64];
    for (unsigned k = 1; k < 1000; ++k) {
        char tail[8];
        unsigned t = 0;
        if (k > 1) {
            char digits[4]; unsigned d = 0, v = k;
            while (v) { digits[d++] = (char)('0' + v % 10); v /= 10; }
            while (d) tail[t++] = digits[--d];
        }
        tail[t++] = '.'; tail[t++] = '.'; tail[t++] = '.';
        if (t > room || room - t >= sizeof(head)) return 0;
        unsigned h = ut::Fit(w, n, room - t, head, cps, 1290);
        while (h && head[h - 1] == ' ') --h;
        for (unsigned i = 0; i < h; ++i) out[i] = head[i];
        for (unsigned i = 0; i < t; ++i) out[h + i] = (unsigned char)tail[i];
        if (!Taken(out, h + t)) return h + t;
    }
    return 0;
}

// ---------------------------------------------------------------- the Names file
// "VF2 Names 1", then one line per short form: short<TAB>room<TAB>whole name, in UTF-8.
static unsigned ToUtf8(const unsigned char *s, unsigned n, unsigned char *out, unsigned cap) {
    static unsigned cps[1300];
    unsigned count = ut::Decode(s, n, cps, 1300), k = 0;
    unsigned char seq[4];
    for (unsigned i = 0; i < count; ++i) {
        unsigned m = ut::PutUtf8(cps[i], seq);
        if (k + m > cap) return k;
        for (unsigned j = 0; j < m; ++j) out[k++] = seq[j];
    }
    return k;
}

// UTF-8 text -> the stored form (into out, cap bytes): its length, or -1 when it is not a valid name.
static int FromUtf8(const unsigned char *s, unsigned n, unsigned char *out, unsigned cap, bool name) {
    static unsigned cps[1300];
    unsigned count = 0, i = 0, cp;
    while (i < n) {
        unsigned k = ut::Utf8Seq(s + i, n - i, &cp);
        if (!k || count >= 1300) return -1;
        cps[count++] = cp;
        i += k;
    }
    int len = ut::Encode(cps, count, out, cap);
    if (len < 0) return -1;
    if (name && !NameOk(cps, count, (unsigned)len)) return -1;
    return len;
}

static bool AddEntry(unsigned slot, unsigned room, const unsigned char *s, unsigned sn, const unsigned char *w,
                     unsigned wn) {
    if (NameCount >= kMaxNames || sn > kMaxShort || wn > kNameBoxBytes) return false;
    unsigned char *copy = (unsigned char *)Alloc(wn + 1);
    if (!copy) return false;
    NameEntry &e = Names[NameCount++];
    e.slot = slot; e.room = room; e.shortLen = sn; e.wholeLen = wn; e.whole = copy;
    for (unsigned i = 0; i < sn; ++i) e.shortForm[i] = s[i];
    e.shortForm[sn] = 0;
    for (unsigned i = 0; i < wn; ++i) copy[i] = w[i];
    copy[wn] = 0;
    return true;
}

static void LoadSlot(unsigned slot) {
    char path[MAX_PATH + 64];
    if (!NamesPath(slot, path, sizeof(path), 0)) return;
    SlotLoaded[slot] = true;
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD size = GetFileSize(h, 0), got = 0;
    unsigned char *text = size && size < (4u << 20) ? (unsigned char *)Alloc(size + 1) : 0;
    bool ok = text && ReadFile(h, text, size, &got, 0) && got == size;
    CloseHandle(h);
    if (!ok) { Release(text); return; }
    static const char header[] = "VF2 Names 1";
    unsigned at = 0;
    for (; header[at]; ++at) if (at >= size || text[at] != (unsigned char)header[at]) { Release(text); return; }
    if (at < size && text[at] == '\r') ++at;
    if (at >= size || text[at] != '\n') { Release(text); return; }
    ++at;
    static unsigned char shortForm[64], whole[kNameBoxBytes + 8];
    while (at < size) {
        unsigned end = at;
        while (end < size && text[end] != '\n') ++end;
        unsigned stop = end > at && text[end - 1] == '\r' ? end - 1 : end;
        unsigned tab1 = at, tab2;
        while (tab1 < stop && text[tab1] != '\t') ++tab1;
        tab2 = tab1 + 1;
        while (tab2 < stop && text[tab2] != '\t') ++tab2;
        unsigned room = 0;
        bool digits = tab1 < stop && tab2 < stop && tab2 > tab1 + 1;
        for (unsigned i = tab1 + 1; digits && i < tab2; ++i) {
            if (text[i] < '0' || text[i] > '9' || room > 100000) digits = false;
            else room = room * 10 + (text[i] - '0');
        }
        if (digits && room >= 1 && room < kNameBoxBytes) {
            int sn = FromUtf8(text + at, tab1 - at, shortForm, room < sizeof(shortForm) ? room : 0, false);
            int wn = FromUtf8(text + tab2 + 1, stop - tab2 - 1, whole, kNameBoxBytes, true);
            if (sn > 0 && wn > 0 && (unsigned)sn <= kMaxShort && EndsWithMark(shortForm, (unsigned)sn) &&
                !InSlot(slot, shortForm, (unsigned)sn))
                AddEntry(slot, room, shortForm, (unsigned)sn, whole, (unsigned)wn);
        }
        at = end + 1;
    }
    Release(text);
}

static void EnsureNames() {
    if (!NamesOn) return;
    for (unsigned s = 1; s <= 5; ++s) if (!SlotLoaded[s]) LoadSlot(s);
}

static void MakeFolders(const char *names) {
    char path[MAX_PATH + 64];
    unsigned n = ut::Length((const unsigned char *)names);
    if (n + 1 >= sizeof(path)) return;
    for (unsigned i = 0; i <= n; ++i) path[i] = names[i];
    unsigned cut = n;
    while (cut > 0 && path[cut - 1] != '\\') --cut;
    if (cut > 0) { path[cut - 1] = 0; CreateDirectoryA(path, 0); path[cut - 1] = '\\'; }
    CreateDirectoryA(path, 0);
}

static bool SaveSlot(unsigned slot) {
    char path[MAX_PATH + 64], folder[MAX_PATH + 64], temp[MAX_PATH + 72];
    if (!NamesPath(slot, path, sizeof(path), folder)) return false;
    unsigned size = 16;
    for (unsigned i = 0; i < NameCount; ++i) if (Names[i].slot == slot) size += 4 * (Names[i].shortLen + Names[i].wholeLen) + 16;
    unsigned char *buf = (unsigned char *)Alloc(size);
    if (!buf) return false;
    static const char header[] = "VF2 Names 1\n";
    unsigned k = 0;
    for (unsigned i = 0; header[i]; ++i) buf[k++] = (unsigned char)header[i];
    for (unsigned i = 0; i < NameCount; ++i) {
        if (Names[i].slot != slot) continue;
        k += ToUtf8(Names[i].shortForm, Names[i].shortLen, buf + k, size - k);
        buf[k++] = '\t';
        char digits[8]; unsigned d = 0, v = Names[i].room;
        do { digits[d++] = (char)('0' + v % 10); v /= 10; } while (v);
        while (d) buf[k++] = (unsigned char)digits[--d];
        buf[k++] = '\t';
        k += ToUtf8(Names[i].whole, Names[i].wholeLen, buf + k, size - k - 1);
        buf[k++] = '\n';
    }
    MakeFolders(folder);
    unsigned n = ut::Length((const unsigned char *)path);
    for (unsigned i = 0; i < n; ++i) temp[i] = path[i];
    temp[n] = '.'; temp[n + 1] = 't'; temp[n + 2] = 'm'; temp[n + 3] = 'p'; temp[n + 4] = 0;
    HANDLE h = CreateFileA(temp, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    bool ok = h != INVALID_HANDLE_VALUE;
    if (ok) {
        DWORD wrote = 0;
        ok = WriteFile(h, buf, k, &wrote, 0) && wrote == k;
        if (ok) ok = FlushFileBuffers(h) != FALSE;
        CloseHandle(h);
        if (ok) ok = MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != FALSE;
        if (!ok) DeleteFileA(temp);
    }
    Release(buf);
    if (ok) ++B200Unicode_Status.namesWritten;
    else Log("a Names file could not be written");
    return ok;
}

// The short form a name box gives the game for its text (stored form w, n bytes) into dst's room; records the
// whole name in `slot`'s Names file when it is a short form (record = false: only answer).
static unsigned StoreName(const unsigned char *w, unsigned n, unsigned room, unsigned slot, bool record,
                          unsigned char *out) {
    EnsureNames();
    unsigned k = ShortFor(w, n, room, out);
    if (!k) return 0;
    if (SameBytes(out, k, w, n)) return k;
    ++B200Unicode_Status.shortForms;
    if (record && slot) {
        if (!InSlot(slot, out, k) && AddEntry(slot, room, out, k, w, n)) SaveSlot(slot);
    }
    return k;
}

// ---------------------------------------------------------------- whole names where short forms are drawn
static int WidestW(unsigned impl) {
    int widest = 0;
    for (unsigned b = 0x20; b < 0x7F; ++b) {
        Rect r = StockRect(impl, b);
        if (r.r - r.l > widest) widest = r.r - r.l;
    }
    return widest;
}

static int TextWidth(unsigned impl, const unsigned char *s) {
    WidthCtx c = { Ensure(impl), impl, s };
    return ut::GetWidth(s, 1.0f, IMPL_FIELD(impl, 0x08), &CtxWidth, &c);
}

// The whole name w (stored form, wn bytes) fitted into maxWidth in the font: itself, or its longest start of whole
// characters + an ellipsis (U+2026). Into out (cap bytes); returns the length.
static unsigned FitName(unsigned impl, const unsigned char *w, unsigned wn, int maxWidth, unsigned char *out,
                        unsigned cap, bool fromEnd) {
    static unsigned cps[1310];
    static unsigned char tryText[kNameBoxBytes + 16];
    unsigned count = ut::Decode(w, wn, cps, 1300);
    int k = ut::Encode(cps, count, tryText, sizeof(tryText) - 1);
    if (k < 0) return 0;
    tryText[k] = 0;
    if (TextWidth(impl, tryText) <= maxWidth || !count) {
        if ((unsigned)k >= cap) return 0;
        for (int i = 0; i <= k; ++i) out[i] = tryText[i];
        return (unsigned)k;
    }
    // the cluster starts
    static unsigned starts[1310];
    unsigned nstarts = 0;
    for (unsigned i = 0; i < count; i = ut::ClusterEnd(cps, count, i)) starts[nstarts++] = i;
    starts[nstarts] = count;
    static unsigned trial[1310];
    unsigned best = 0;
    // binary search the most characters that fit (with the ellipsis)
    unsigned lo = 0, hi = nstarts;
    while (lo <= hi) {
        unsigned mid = (lo + hi) / 2, m = 0;
        if (fromEnd) {
            trial[m++] = 0x2026;
            for (unsigned i = starts[nstarts - mid]; i < count; ++i) trial[m++] = cps[i];
        } else {
            for (unsigned i = 0; i < starts[mid]; ++i) trial[m++] = cps[i];
            while (m && trial[m - 1] == ' ') --m;
            trial[m++] = 0x2026;
        }
        int len = ut::Encode(trial, m, tryText, sizeof(tryText) - 1);
        bool fits = false;
        if (len >= 0) { tryText[len] = 0; fits = TextWidth(impl, tryText) <= maxWidth; }
        if (fits) { best = mid; lo = mid + 1; } else { if (!mid) break; hi = mid - 1; }
    }
    unsigned m = 0;
    if (fromEnd) {
        trial[m++] = 0x2026;
        for (unsigned i = starts[nstarts - best]; i < count; ++i) trial[m++] = cps[i];
    } else {
        for (unsigned i = 0; i < starts[best]; ++i) trial[m++] = cps[i];
        while (m && trial[m - 1] == ' ') --m;
        trial[m++] = 0x2026;
    }
    int len = ut::Encode(trial, m, out, cap - 1);
    if (len < 0) return 0;
    out[len] = 0;
    return (unsigned)len;
}

// text with every short form replaced by its whole name, fitted; 0 when the text holds none (draw it as it is).
// justified: each whole name fitted into its short form's own width, else into `room` W. The text is worked on in
// code points, so a whole name in UTF-8 inside a single-byte text (or the other way) comes out in one stored form.
static const unsigned char *Expand(unsigned impl, const unsigned char *text, unsigned char *out, unsigned cap,
                                   bool justified) {
    if (!NamesOn || !text || !impl || !IMPL_FIELD(impl, 0x10)) return 0;
    unsigned n = ut::Length(text);
    bool mark = false;
    for (unsigned i = 0; i + 2 < n && !mark; ++i) mark = text[i] == '.' && text[i + 1] == '.' && text[i + 2] == '.';
    if (!mark) return 0;
    EnsureNames();
    if (!NameCount) return 0;
    static unsigned tcps[4100], ocps[8200], scps[kMaxShort + 2], wcps[kNameBoxBytes + 8];
    static unsigned char fitted[kNameBoxBytes + 16];
    unsigned count = ut::Decode(text, n, tcps, 4096), o = 0, slot = CurrentSlot();
    bool any = false;
    for (unsigned i = 0; i < count;) {
        int best = -1;
        unsigned bestLen = 0;
        if (tcps[i] == '.' && i + 2 < count && tcps[i + 1] == '.' && tcps[i + 2] == '.') {
            // a short form ends here: the longest one known, the current slot's first
            for (unsigned e = 0; e < NameCount; ++e) {
                unsigned sl = ut::Decode(Names[e].shortForm, Names[e].shortLen, scps, kMaxShort + 1);
                if (sl < 3 || sl - 3 > o) continue;
                unsigned j = 0;
                while (j < sl - 3 && scps[j] == ocps[o - (sl - 3) + j]) ++j;
                if (j < sl - 3) continue;
                if (best < 0 || sl > bestLen || (sl == bestLen && Names[e].slot == slot)) { best = (int)e; bestLen = sl; }
            }
        }
        if (best < 0) {
            if (o + 1 >= 8192) return 0;
            ocps[o++] = tcps[i++];
            continue;
        }
        const NameEntry &e = Names[best];
        o -= bestLen - 3;
        int maxWidth;
        if (justified) {
            static unsigned char sf[kMaxShort + 1];
            for (unsigned j = 0; j <= e.shortLen; ++j) sf[j] = e.shortForm[j];
            maxWidth = TextWidth(impl, sf);
        } else {
            int kern = IMPL_FIELD(impl, 0x08);
            maxWidth = (int)e.room * (WidestW(impl) + kern) - kern;
        }
        unsigned m = FitName(impl, e.whole, e.wholeLen, maxWidth, fitted, sizeof(fitted), false);
        unsigned wc = m ? ut::Decode(fitted, m, wcps, kNameBoxBytes + 4) : 0;
        if (!wc || o + wc + 1 >= 8192) return 0;
        for (unsigned j = 0; j < wc; ++j) ocps[o++] = wcps[j];
        i += 3;
        any = true;
    }
    if (!any) return 0;
    int k = ut::Encode(ocps, o, out, cap - 1);
    if (k < 0) return 0;
    out[k] = 0;
    ++B200Unicode_Status.expanded;
    return out;
}

// ---------------------------------------------------------------- hooks
typedef void (__thiscall *SetCanEditFn)(void *ctl, int edit, int limit);
typedef void (__thiscall *BoxDrawFn)(void *impl);

static char NameKindFor(unsigned ret) {
    for (unsigned i = 0; i < UNI_NAME_BOX_COUNT; ++i) if (NameReturns[i] == ret) return UNI_NAME_BOXES[i].kind;
    return 0;
}

// A name box's text is a short form: the whole name instead (SetText through the stock function).
static void OpenWhole(unsigned impl, NameBox *b) {
    const unsigned char *text = *(const unsigned char **)(impl + 0x30);
    if (!text) return;
    EnsureNames();
    unsigned n = ut::Length(text);
    int e = EndsWithMark(text, n) ? FindShort(text, n, CurrentSlot()) : -1;
    if (e < 0) return;
    ((void (__thiscall *)(void *, const char *))(void *)SetTextTrampoline)((void *)impl, (const char *)Names[e].whole);
    MarkSetIn(impl, true);
    b->expanded = e;
}

// ldwTextControlImpl::SetText of a name box (UniSetText): a short form opens as the whole name. A box that is not
// editable is no longer a name box (its object was made again for something else).
static void NameSetText(unsigned impl, const char **text) {
    NameBox *b = BoxOf(impl);
    if (!b) return;
    if (!*(unsigned char *)(impl + 0x24)) { b->impl = 0; return; }
    b->expanded = -1;
    const unsigned char *s = (const unsigned char *)*text;
    if (!s) return;
    unsigned n = ut::Length(s);
    if (!EndsWithMark(s, n)) return;
    EnsureNames();
    int e = FindShort(s, n, CurrentSlot());
    if (e < 0) return;
    *text = (const char *)Names[e].whole;
    b->expanded = e;
}

static bool IsNameBox(unsigned impl) { return NamesOn && BoxOf(impl) != 0; }

extern "C" void *_ReturnAddress(void);
#pragma intrinsic(_ReturnAddress)
static void __fastcall UniSetCanEdit(void *ctl, void *, int edit, int limit) {
    unsigned ret = (unsigned)_ReturnAddress();
    unsigned impl = *(unsigned *)((unsigned)ctl + 0x10);
    char kind = NameKindFor(ret);
    NameBox *b = BoxOf(impl);
    if (kind) { limit = (int)kNameBoxBytes; b = AddBox(impl, kind); ++B200Unicode_Status.nameBoxes; }
    else if (b) { b->impl = 0; b = 0; }
    ((SetCanEditFn)(void *)SetCanEditTrampoline)(ctl, edit, limit);
    if (b && (edit & 0xFF)) OpenWhole(impl, b);
}

// ldwTextControlImpl::Draw: a name box draws a copy that fits.
static void __fastcall UniBoxDraw(void *implp, void *) {
    unsigned impl = (unsigned)implp;
    NameBox *b = BoxOf(impl);
    unsigned char *text = *(unsigned char **)(impl + 0x30);
    unsigned font = *(unsigned *)(impl + 0x3C);
    unsigned fimpl = font ? *(unsigned *)(font + 4) : 0;
    if (!b || !text || !fimpl || !IMPL_FIELD(fimpl, 0x10) || *(unsigned char *)(impl + 0x2F)) {
        ((BoxDrawFn)(void *)BoxDrawTrampoline)(implp);
        return;
    }
    int avail = *(int *)(impl + 0x10) - *(int *)(impl + 0x08) - *(int *)(impl + 0x44) - 4;
    static unsigned char copy[kNameBoxBytes + 16];
    if (avail <= 0 || TextWidth(fimpl, text) <= avail) {
        ((BoxDrawFn)(void *)BoxDrawTrampoline)(implp);
        return;
    }
    bool typing = *(unsigned char *)(impl + 0x25) != 0;
    unsigned n = FitName(fimpl, text, ut::Length(text), avail, copy, sizeof(copy), typing);
    if (!n) { ((BoxDrawFn)(void *)BoxDrawTrampoline)(implp); return; }
    *(unsigned char **)(impl + 0x30) = copy;
    ((BoxDrawFn)(void *)BoxDrawTrampoline)(implp);
    *(unsigned char **)(impl + 0x30) = text;
    ++B200Unicode_Status.boxCopies;
}

// GetText of a name box (UniGetText): the short form, recorded. True when it answered.
static bool NameGetText(unsigned impl, const unsigned char *src, unsigned n, char *dst, int size) {
    NameBox *b = BoxOf(impl);
    if (!NamesOn || !b || size < 4) return false;
    unsigned room = (unsigned)size - 1;
    unsigned gs = GameStateNow(), slot = 0;
    bool record = true;
    unsigned d = (unsigned)dst;
    if (gs && d >= gs + UNI_GS_PLAYER_NAMES && d < gs + UNI_GS_PLAYER_NAMES + 5 * UNI_GS_PLAYER_STRIDE)
        slot = (d - gs - UNI_GS_PLAYER_NAMES) / UNI_GS_PLAYER_STRIDE + 1;        // the slot menu's family names
    else {
        slot = CurrentSlot();                                                  // the family being played
        if (b->kind == 'F' && !(gs && d == gs + UNI_GS_NICKNAME)) record = false;  // a label read into a local
    }
    static unsigned char out[64];
    if (IsSetIn(impl)) {
        if (b->expanded >= 0 && (unsigned)b->expanded < NameCount && Names[b->expanded].shortLen <= room) {
            const NameEntry &e = Names[b->expanded];
            for (unsigned i = 0; i < e.shortLen; ++i) dst[i] = (char)e.shortForm[i];
            return true;
        }
        return false;                    // a name the game set: the stock rule (UniGetText)
    }
    if (room >= sizeof(out)) return false;
    unsigned k = StoreName(src, n, room, slot, record, out);
    if (!k) return false;
    for (unsigned i = 0; i < k; ++i) dst[i] = (char)out[i];
    return true;
}

static bool ResolveNames() {
    static ImageRange code[kMaxRanges], data[kMaxRanges], rodata[kMaxRanges];
    unsigned codeCount = 0, dataCount = 0, rodataCount = 0, imageBase = 0, imageEnd = 0;
    if (!LiveSections(code, &codeCount, data, &dataCount, rodata, &rodataCount, &imageBase, &imageEnd)) return false;
    static unsigned loc[UNI_NPIN_COUNT];
    for (unsigned i = 0; i < UNI_NPIN_COUNT; ++i) {
        const UniPin &pin = UNI_NAME_PINS[i];
        unsigned hits = 0, at = 0;
        for (unsigned r = 0; r < codeCount && hits < 2; ++r) {
            unsigned h = 0;
            unsigned found = ScanPattern((const unsigned char *)code[r].base, code[r].size, pin.bytes, pin.mask,
                                         pin.len, &h);
            if (h) { if (!hits) at = found; hits += h; }
        }
        if (hits != 1) { Log("long names: a pinned function is not found exactly once"); Log(pin.name); return false; }
        loc[i] = at;
    }
    bool have[UNI_NSITE_COUNT];
    for (unsigned i = 0; i < UNI_NSITE_COUNT; ++i) have[i] = false;
    for (unsigned e = 0; e < sizeof(UNI_NAME_EVIDENCE) / sizeof(UNI_NAME_EVIDENCE[0]); ++e) {
        const UniEvidence &ev = UNI_NAME_EVIDENCE[e];
        unsigned at = loc[ev.pin] + ev.offset;
        unsigned v = ev.kind == 'A' ? *(const unsigned *)at : at;
        if (have[ev.site] && NSites[ev.site] != v) return false;
        NSites[ev.site] = v;
        have[ev.site] = true;
    }
    for (unsigned i = 0; i < UNI_NSITE_COUNT; ++i) if (!have[i]) return false;
    static const unsigned char canEdit[UNI_SET_CAN_EDIT_STEAL] = { 0x55, 0x8B, 0xEC, 0x53, 0x8A, 0x5D, 0x08 };
    static const unsigned char draw[UNI_BOX_DRAW_STEAL] = { 0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x38, 0x56 };
    for (unsigned k = 0; k < UNI_SET_CAN_EDIT_STEAL; ++k)
        if (((const unsigned char *)NSITE(SET_CAN_EDIT))[k] != canEdit[k]) { Log("SetCanEdit's start differs"); return false; }
    for (unsigned k = 0; k < UNI_BOX_DRAW_STEAL; ++k)
        if (((const unsigned char *)NSITE(BOX_DRAW))[k] != draw[k]) { Log("the text box's Draw start differs"); return false; }
    unsigned instance = NSITE(GAME_STATE_INSTANCE);
    if (instance < imageBase || instance + 4 > imageEnd) return false;
    for (unsigned i = 0; i < UNI_NAME_BOX_COUNT; ++i) {
        unsigned at = loc[UNI_NAME_BOXES[i].pin] + UNI_NAME_BOXES[i].offset;
        if (at + *(const int *)(at - 4) != NSITE(SET_CAN_EDIT)) { Log("a name box call is not SetCanEdit"); return false; }
        NameReturns[i] = at;
    }
    return true;
}

static void Trampoline(unsigned char *t, unsigned site, unsigned steal) {
    for (unsigned i = 0; i < steal; ++i) t[i] = ((const unsigned char *)site)[i];
    t[steal] = 0xE9;
    *(int *)(t + steal + 1) = (int)((site + steal) - ((unsigned)t + steal + 5));
}

// The long names' writes, added to the plan when their sites are proved (else the plan is the Unicode text alone).
static void PlanNames(Plan &plan) {
    NamesOn = false;
    if (!ResolveNames()) { Log("long names: the executable could not be proved; names keep their stock limits"); return; }
    Trampoline(SetCanEditTrampoline, NSITE(SET_CAN_EDIT), UNI_SET_CAN_EDIT_STEAL);
    Trampoline(BoxDrawTrampoline, NSITE(BOX_DRAW), UNI_BOX_DRAW_STEAL);
    PlanJump(plan, NSITE(SET_CAN_EDIT), (const void *)&UniSetCanEdit, UNI_SET_CAN_EDIT_STEAL);
    PlanJump(plan, NSITE(BOX_DRAW), (const void *)&UniBoxDraw, UNI_BOX_DRAW_STEAL);
    NamesOn = plan.ok;
}
