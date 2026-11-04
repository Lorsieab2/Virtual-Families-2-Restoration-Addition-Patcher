// Nothing runs off the screen (included by b200unicode.cpp before the draw hooks; src/vf2_screen_edge.py is the
// model; tests/test_screen_edge.py). The same rule as Virtual Families 1 (native/vf1text/screen.inc).
//
// The owner, 2026-11-03: "i dont care if things run out of boxes, they just need to not run off the screen".
//   * DrawString (every left, right-aligned and centred text, every text box): a text that would leave the screen but
//     is partly on it is moved so that it ends at the screen's edge. One wider than the screen is cut, each line, to its
//     longest start of whole characters and "…". One taller than the screen keeps the lines that fit, the last ending
//     in "…". When not even "…" fits, the English is shown (the Translations DLL's B200Tr_EnglishOf), if there is one.
//   * DrawStringJustified (dialogs, events, the store, which wrap at the game's own line breaks): its box is moved so
//     that it ends at the screen's edge. A box wider than the screen becomes the screen's width (the text wraps again
//     at its own line breaks). A text that wraps taller than the screen keeps the lines that fit, with "…".
//   * Only text the patches or a translation bring is touched: text with a byte beyond ASCII, or any text while a
//     translation is chosen (vf2tr_b200.dll installed). The stock English game is drawn exactly as before, and a text
//     wholly off the screen (an animation not yet in view) is left as it is.

static const unsigned char kEllipsis[] = { 0xE2, 0x80, 0xA6, 0 };             // "…" (U+2026, UTF-8)

static bool TranslationChosen() {
    static const volatile unsigned *status;                // vf2tr_b200.dll loads after this DLL: looked for until found
    if (!status) {
        HMODULE tr = GetModuleHandleW(L"vf2tr_b200.dll");
        status = tr ? (const volatile unsigned *)GetProcAddress(tr, "B200Tr_Status") : 0;
    }
    return status && status[4] != 0;                                             // TrStatus.installed
}

static bool ClampWanted(const unsigned char *text, unsigned n) {
    for (unsigned i = 0; i < n; ++i) if (text[i] >= 0x80) return true;
    return TranslationChosen();
}

static bool ScreenSize(void *window, int *w, int *h) {
    SDL_Surface *s = window ? *(SDL_Surface **)((unsigned)window + 0x30) : 0;
    if (!s || s->w <= 0 || s->h <= 0) return false;
    *w = s->w;
    *h = s->h;
    return true;
}

// ldwFont::GetWidth's arithmetic over the pieces DrawString draws (characters, shaped runs drawn whole).
static int PieceWidth(FontRec *f, unsigned impl, const unsigned char *raw, float scale) {
    WidthCtx c = { f, impl, raw };
    int kerning = IMPL_FIELD(impl, 0x08), widest = 0, cur = 0;
    ut::Units it;
    it.Init(raw, ut::Length(raw));
    ut::Unit u;
    while (it.Next(u)) {
        if (u.IsNewline()) {
            if (cur && cur > widest) widest = cur;
            cur = 0;
            continue;
        }
        Rect g;
        unsigned size;
        int w = RunPiece(f, it, u, raw, true, g, &size) ? g.r - g.l : CtxWidth(&c, u);
        cur += (int)ut::F32(ut::F32((float)(kerning + w)) * scale);
    }
    if (widest > cur) cur = widest;
    return cur ? cur - kerning : 0;
}

// One line (n bytes) fitted to `room` pixels: itself when it fits, else its longest start of whole characters,
// trailing spaces dropped, then "…"; written to out (at most cap bytes with the 0). Returns its length, or -1 when not
// even "…" fits.
static int FitLine(FontRec *f, unsigned impl, const unsigned char *line, unsigned n, int room, unsigned char *out,
                   unsigned cap) {
    if (n + 4 > cap) n = cap - 4;
    for (unsigned i = 0; i < n; ++i) out[i] = line[i];
    out[n] = 0;
    if (PieceWidth(f, impl, out, 1.0f) <= room) return (int)n;
    // the starts of whole characters, the longest that fits with "…"
    ut::Units it;
    it.Init(line, n);
    ut::Unit u;
    unsigned best = 0;
    bool any = false;
    while (it.Next(u)) {
        unsigned end = u.start + u.size, k = end;
        while (k > 0 && line[k - 1] == ' ') --k;
        for (unsigned i = 0; i < k; ++i) out[i] = line[i];
        for (unsigned i = 0; i < 4; ++i) out[k + i] = kEllipsis[i];
        if (PieceWidth(f, impl, out, 1.0f) > room) break;
        best = k;
        any = true;
    }
    for (unsigned i = 0; i < 4; ++i) out[i] = kEllipsis[i];
    if (!any && PieceWidth(f, impl, out, 1.0f) > room) return -1;
    for (unsigned i = 0; i < best; ++i) out[i] = line[i];
    for (unsigned i = 0; i < 4; ++i) out[best + i] = kEllipsis[i];
    return (int)best + 3;
}

static unsigned char ScreenText[8192];

// What and where DrawString draws so that nothing leaves the screen.
static const unsigned char *OnScreen(void *window, FontRec *f, unsigned impl, const unsigned char *text, int *x,
                                     int *y) {
    int sw, sh;
    if (!f || f->index < 0 || !text || !*text || !ScreenSize(window, &sw, &sh)) return text;
    unsigned n = ut::Length(text);
    if (!ClampWanted(text, n)) return text;                              // the stock game's own text: as before
    int width = PieceWidth(f, impl, text, 1.0f), lineH = IMPL_FIELD(impl, 0x04), lines = 1;
    for (unsigned i = 0; i < n; ++i) if (text[i] == '\n') ++lines;
    int h = lines * lineH;
    if (*x >= 0 && *x + width <= sw && *y >= 0 && *y + h <= sh) return text;            // on the screen: as before
    if (*x >= sw || *x + width <= 0 || *y >= sh || *y + h <= 0) return text;            // wholly off it: left alone
    int fitLines = lineH > 0 ? sh / lineH : lines;
    if (fitLines < 1) fitLines = 1;
    if (width > sw || lines > fitLines) {
        static unsigned char line[sizeof(ScreenText)], fitted[sizeof(ScreenText)];
        unsigned m = 0, at = 0;
        int kept = 0;
        bool none = false;
        while (at <= n && kept < fitLines && m + 8 < sizeof(ScreenText)) {
            unsigned end = at;
            while (end < n && text[end] != '\n') ++end;
            unsigned len = end - at;
            if (len + 8 > sizeof(line)) len = sizeof(line) - 8;
            for (unsigned i = 0; i < len; ++i) line[i] = text[at + i];
            if (kept + 1 == fitLines && end < n) { for (unsigned i = 0; i < 3; ++i) line[len + i] = kEllipsis[i]; len += 3; }
            int fl = FitLine(f, impl, line, len, sw, fitted, sizeof(fitted));
            if (fl < 0) { none = true; break; }
            if (kept) ScreenText[m++] = '\n';
            for (int i = 0; i < fl && m + 1 < sizeof(ScreenText); ++i) ScreenText[m++] = fitted[i];
            ++kept;
            if (end >= n) break;
            at = end + 1;
        }
        ScreenText[m] = 0;
        if (none) {                                      // not even "…" fits: the English line, when there is one
            typedef const char *(__cdecl *EnglishOfFn)(const char *);
            HMODULE tr = GetModuleHandleW(L"vf2tr_b200.dll");
            EnglishOfFn english = tr ? (EnglishOfFn)GetProcAddress(tr, "B200Tr_EnglishOf") : 0;
            const char *e = english ? english((const char *)text) : 0;
            if (!e || !*e || (const unsigned char *)e == text) return text;
            text = (const unsigned char *)e;
        } else {
            text = ScreenText;
            ++B200Unicode_Status.screenCuts;
        }
        n = ut::Length(text);
        width = PieceWidth(f, impl, text, 1.0f);
        lines = 1;
        for (unsigned i = 0; i < n; ++i) if (text[i] == '\n') ++lines;
        h = lines * lineH;
    }
    int ox = *x, oy = *y;
    if (*x < 0 || width > sw) *x = 0;
    else if (*x + width > sw) *x = sw - width;
    if (*y < 0 || h > sh) *y = 0;
    else if (*y + h > sh) *y = sh - h;
    if (*x != ox || *y != oy) ++B200Unicode_Status.screenMoves;
    return text;
}

static ut::LineState ScreenLines;

// How tall DrawStringJustified wraps `text` in a box `width` wide: its lines (GetNextJustifiedLine, as the game's
// wrapping measures) times the line height; *cutAt: the byte where the first line that does not fit in `rows` starts.
static int WrappedHeight(FontRec *f, unsigned impl, const unsigned char *text, int width, int rows, unsigned *cutAt) {
    static unsigned char out[4096];
    unsigned n = ut::Length(text), at = 0;
    int lines = 0;
    *cutAt = n;
    ut::IcuLoader() = &icu::Install;
    while (at < n && lines < 4096) {
        while (at < n && text[at] == ' ') ++at;
        if (at >= n) break;
        if (lines == rows) *cutAt = at;
        bool dbl = false;
        WidthCtx c = { f, impl, text + at };                            // CtxWidth reads the line's own bytes
        unsigned used = ut::NextLine(text + at, out, 0x3FF, width, &dbl, false, 1.0f, IMPL_FIELD(impl, 0x08), &CtxWidth,
                                     &c, ScreenLines);
        if (!used) break;
        ++lines;
        if (dbl) { if (lines == rows) *cutAt = at + used; ++lines; }
        at += used;
    }
    return lines * IMPL_FIELD(impl, 0x04);
}

// The game's own wrapping (DrawStringJustified) ends a line only at a space: where GetNextJustifiedLine ends one
// inside a word (next to a letter of a script written without spaces, UAX #14, or in a word wider than the box), a
// line break is put, so the game ends the line there too. Text whose lines all end at spaces is unchanged.
static unsigned char BrokenText[8192];
static const unsigned char *BreakInsideWords(FontRec *f, unsigned impl, const unsigned char *text, int width) {
    static unsigned char line[4096];
    unsigned n = ut::Length(text), at = 0, m = 0;
    bool changed = false;
    ut::IcuLoader() = &icu::Install;
    while (at < n && m + 2 < sizeof(BrokenText)) {
        while (at < n && text[at] == ' ' && m + 2 < sizeof(BrokenText)) BrokenText[m++] = text[at++];
        if (at >= n) break;
        bool dbl = false;
        WidthCtx c = { f, impl, text + at };
        unsigned used = ut::NextLine(text + at, line, 0x3FF, width, &dbl, false, 1.0f, IMPL_FIELD(impl, 0x08),
                                     &CtxWidth, &c, ScreenLines);
        if (!used) used = n - at;
        for (unsigned i = 0; i < used && m + 2 < sizeof(BrokenText); ++i) BrokenText[m++] = text[at + i];
        at += used;
        if (at < n && text[at - 1] != ' ' && text[at - 1] != '\n' && text[at] != ' ' && text[at] != '\n') {
            BrokenText[m++] = '\n';
            changed = true;
        }
    }
    if (!changed || at < n) return text;                 // nothing to break, or too long to copy: as it is
    BrokenText[m] = 0;
    return BrokenText;
}

// DrawStringJustified's box (x, y, width) moved so that its text ends at the screen's edge; a text that wraps taller
// than the screen keeps the lines that fit, with "…".
static const unsigned char *WrapOnScreen(void *window, FontRec *f, unsigned impl, const unsigned char *text, int *x,
                                         int *y, int *width) {
    int sw, sh;
    if (!f || f->index < 0 || !text || !*text || *width <= 0 || !ScreenSize(window, &sw, &sh)) return text;
    unsigned n = ut::Length(text);
    if (!ClampWanted(text, n)) return text;
    int ox = *x, oy = *y;
    if (*width > sw) { *width = sw; ++B200Unicode_Status.screenMoves; }    // a box wider than the screen: the screen
    text = BreakInsideWords(f, impl, text, *width);
    n = ut::Length(text);
    int lineH = IMPL_FIELD(impl, 0x04), rows = lineH > 0 ? sh / lineH : 1;
    if (rows < 1) rows = 1;
    unsigned cutAt;
    int h = WrappedHeight(f, impl, text, *width, rows, &cutAt);
    if (*x >= 0 && *x + *width <= sw && *y >= 0 && *y + h <= sh) return text;
    if (*x >= sw || *x + *width <= 0 || *y >= sh || *y + h <= 0) return text;
    if (h > sh && cutAt < n && cutAt + 8 < sizeof(ScreenText)) {
        unsigned k = cutAt;
        while (k > 0 && (text[k - 1] == ' ' || text[k - 1] == '\n')) --k;
        for (unsigned i = 0; i < k; ++i) ScreenText[i] = text[i];
        for (unsigned i = 0; i < 4; ++i) ScreenText[k + i] = kEllipsis[i];
        // the "…" may make the last line wrap once more: drop whole characters until it fits the screen
        while (k > 0 && WrappedHeight(f, impl, ScreenText, *width, rows, &cutAt) > sh) {
            unsigned j = 0, last = 0;
            ut::Units it;
            it.Init(text, k);
            ut::Unit u;
            while (it.Next(u)) { last = j; j = u.start + u.size; }
            k = last;
            while (k > 0 && (text[k - 1] == ' ' || text[k - 1] == '\n')) --k;
            for (unsigned i = 0; i < 4; ++i) ScreenText[k + i] = kEllipsis[i];
        }
        text = ScreenText;
        h = WrappedHeight(f, impl, text, *width, rows, &cutAt);
        ++B200Unicode_Status.screenCuts;
    }
    if (*x < 0) *x = 0;
    else if (*x + *width > sw) *x = sw - *width;
    if (*y < 0 || h > sh) *y = 0;
    else if (*y + h > sh) *y = sh - h;
    if (*x != ox || *y != oy) ++B200Unicode_Status.screenMoves;
    return text;
}
