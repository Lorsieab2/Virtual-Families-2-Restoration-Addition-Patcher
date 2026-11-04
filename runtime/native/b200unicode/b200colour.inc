// Colour emoji (included by b200unicode.cpp; not in the Copy and Paste build): a character drawn from a colour font
// (COLR, CBDT, sbix or SVG) is drawn by DirectWrite and Direct2D in its own colours, never tinted, with the text's
// alpha. The same steps as src/vf2_glyph_color.py (the Game Text preview), Virtual Families 1's glyph_color.inc and
// Fish and Plant Tycoon's raster_colour; tests/test_colour_emoji.py runs this copy through 32-bit rundll32 with the
// machine's real Direct2D and compares every pixel with the Python.
//
//   * which characters: an emoji shown as a picture (b200emoji.h, src/vf2_emoji.is_colour_emoji) from the first
//     colour font of the chain that has it (Segoe UI Emoji, then Noto Color Emoji), else Segoe UI Emoji; any other
//     character whose chain face is a colour font, from that face;
//   * DirectWrite lays it out at the regular weight and the game font's em; Direct2D draws it with
//     D2D1_DRAW_TEXT_OPTIONS_ENABLE_COLOR_FONT and grayscale anti-aliasing on a software DC render target bound to a
//     32-bit DIB the line high, the layout's baseline on the font's baseline row, the pen at x = pad; the cell is the
//     advance from x = pad (as the black-and-white letters are cut), its pixels made straight;
//   * a drawing with no colour of its own (a flag's two letters, in the brush's white) is not kept: GDI draws it and
//     the game's colour tints it as any letter;
//   * the cell goes into the font's sheet with its own colours, and into every tinted copy of the sheet unchanged
//     (StampColour): the game's tint, which ANDs its colour with every pixel, is never applied to it, whichever
//     drawing path (DrawString, DrawChars, DrawStringJustified) blits it, and the text's alpha still applies.
//
// Without Direct2D, DirectWrite or the face (LoadLibraryExW of d2d1.dll / dwrite.dll from System32 fails, a factory
// or the render target cannot be made), nothing here is used and the character is drawn by GDI in one colour as
// before. Nothing here runs for a character that is not drawn from a colour font.

#include <d2d1.h>
#include <dwrite.h>
#include "b200emoji.h"

static bool IsColourEmoji(const unsigned *cps, unsigned n) {
    for (unsigned i = 0; i < n; ++i) if (cps[i] == 0xFE0E) return false;
    for (unsigned i = 0; i < n; ++i) {
        unsigned cp = cps[i];
        if (cp == 0xFE0F || cp == 0x20E3 || (cp >= 0x1F3FB && cp <= 0x1F3FF) || (cp >= 0xE0020 && cp <= 0xE007F))
            return true;
        int lo = 0, hi = (int)(sizeof(kEmojiPresentation) / sizeof(kEmojiPresentation[0])) - 1;
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            if (cp < kEmojiPresentation[mid][0]) hi = mid - 1;
            else if (cp > kEmojiPresentation[mid][1]) lo = mid + 1;
            else return true;
        }
    }
    return false;
}

static ID2D1Factory *D2D;
static IDWriteFactory *DWrite;
static ID2D1DCRenderTarget *ColourTarget;
static ID2D1SolidColorBrush *ColourBrush;
static bool ColourLooked;

// The factories, the software DC render target and the white brush, made once at the first colour character.
__declspec(noinline) static bool LoadColour() {
    if (ColourLooked) return ColourTarget != 0;
    ColourLooked = true;
    typedef HRESULT (WINAPI *D2DCreateFn)(D2D1_FACTORY_TYPE, REFIID, const D2D1_FACTORY_OPTIONS *, void **);
    typedef HRESULT (WINAPI *DWCreateFn)(DWRITE_FACTORY_TYPE, REFIID, IUnknown **);
    HMODULE d2 = LoadLibraryExW(L"d2d1.dll", 0, 0x800 /* LOAD_LIBRARY_SEARCH_SYSTEM32 */);
    HMODULE dw = d2 ? LoadLibraryExW(L"dwrite.dll", 0, 0x800) : 0;
    D2DCreateFn d2create = d2 ? (D2DCreateFn)GetProcAddress(d2, "D2D1CreateFactory") : 0;
    DWCreateFn dwcreate = dw ? (DWCreateFn)GetProcAddress(dw, "DWriteCreateFactory") : 0;
    void *f = 0;
    IUnknown *w = 0;
    ID2D1DCRenderTarget *target = 0;
    ID2D1SolidColorBrush *brush = 0;
    if (d2create && dwcreate &&
        SUCCEEDED(d2create(D2D1_FACTORY_TYPE_SINGLE_THREADED, __uuidof(ID2D1Factory), 0, &f)) && f &&
        SUCCEEDED(dwcreate(DWRITE_FACTORY_TYPE_SHARED, __uuidof(IDWriteFactory), &w)) && w) {
        D2D1_RENDER_TARGET_PROPERTIES props;
        props.type = D2D1_RENDER_TARGET_TYPE_SOFTWARE;
        props.pixelFormat.format = DXGI_FORMAT_B8G8R8A8_UNORM;
        props.pixelFormat.alphaMode = D2D1_ALPHA_MODE_PREMULTIPLIED;
        props.dpiX = 96.0f; props.dpiY = 96.0f;
        props.usage = D2D1_RENDER_TARGET_USAGE_NONE;
        props.minLevel = D2D1_FEATURE_LEVEL_DEFAULT;
        D2D1_COLOR_F white = { 1.0f, 1.0f, 1.0f, 1.0f };
        if (SUCCEEDED(((ID2D1Factory *)f)->CreateDCRenderTarget(&props, &target)) && target &&
            SUCCEEDED(target->CreateSolidColorBrush(&white, 0, &brush)) && brush) {
            D2D = (ID2D1Factory *)f;
            DWrite = (IDWriteFactory *)w;
            ColourTarget = target;
            ColourBrush = brush;
            return true;
        }
    }
    if (brush) brush->Release();
    if (target) target->Release();
    if (f) ((IUnknown *)f)->Release();
    if (w) w->Release();
    Log("colour emoji: Direct2D / DirectWrite could not be started; emoji are drawn in one colour");
    return false;
}

// `units` UTF-16 units of one whole character in `face`, regular weight, at `em`, its baseline on row `baseline` of a
// cell `height` high: the cell's straight R, G, B, A rows into rgba (at most cap bytes). Returns the width, or -1 when
// it is not drawn in colour (no Direct2D, no such face, no colour in the drawing, too wide). noinline: the tests'
// emulator carries this one function out with the machine's real Direct2D.
__declspec(noinline) static int ColourCell(const wchar_t *face, int em, int baseline, int height, const wchar_t *text,
                                           int units, unsigned char *rgba, unsigned cap) {
    if (!LoadColour() || units <= 0 || em <= 0 || height <= 0) return -1;
    IDWriteTextFormat *format = 0;
    IDWriteTextLayout *layout = 0;
    HDC dc = 0;
    HBITMAP bmp = 0;
    HGDIOBJ old = 0;
    bool ok = false;
    unsigned char *px = 0;
    int width = 0, pad = height, advance = 0;
    for (;;) {                       // once: a failed step breaks out
        if (FAILED(DWrite->CreateTextFormat(face, 0, DWRITE_FONT_WEIGHT_NORMAL, DWRITE_FONT_STYLE_NORMAL,
                                            DWRITE_FONT_STRETCH_NORMAL, (FLOAT)em, L"en-us", &format)) || !format) break;
        format->SetWordWrapping(DWRITE_WORD_WRAPPING_NO_WRAP);
        if (FAILED(DWrite->CreateTextLayout(text, (UINT32)units, format, 4096.0f, (FLOAT)(height * 4), &layout)) ||
            !layout) break;
        DWRITE_TEXT_METRICS tm;
        if (FAILED(layout->GetMetrics(&tm))) break;
        DWRITE_LINE_METRICS lm;
        UINT32 lines = 0;
        if (FAILED(layout->GetLineMetrics(&lm, 1, &lines)) || lines < 1) break;
        advance = (int)(tm.widthIncludingTrailingWhitespace + 0.5f);
        width = advance + 2 * pad;
        if (advance <= 0 || (unsigned)(advance * height * 4) > cap) break;
        dc = CreateCompatibleDC(0);
        if (!dc) break;
        BITMAPINFOHEADER info = { sizeof(BITMAPINFOHEADER), width, -height, 1, 32, BI_RGB, 0, 0, 0, 0, 0 };
        void *bits = 0;
        bmp = CreateDIBSection(dc, (BITMAPINFO *)&info, DIB_RGB_COLORS, &bits, 0, 0);
        if (!bmp || !bits) break;
        old = SelectObject(dc, bmp);
        px = (unsigned char *)bits;
        for (int i = 0; i < width * height * 4; ++i) px[i] = 0;
        RECT rect = { 0, 0, width, height };
        if (FAILED(ColourTarget->BindDC(dc, &rect))) break;
        ColourTarget->BeginDraw();
        ColourTarget->SetTextAntialiasMode(D2D1_TEXT_ANTIALIAS_MODE_GRAYSCALE);
        D2D1_COLOR_F clear = { 0.0f, 0.0f, 0.0f, 0.0f };
        ColourTarget->Clear(&clear);
        D2D1_POINT_2F origin = { (FLOAT)pad, (FLOAT)baseline - lm.baseline };
        ColourTarget->DrawTextLayout(origin, layout, ColourBrush, D2D1_DRAW_TEXT_OPTIONS_ENABLE_COLOR_FONT);
        if (FAILED(ColourTarget->EndDraw())) break;
        GdiFlush();
        // kept only when the drawing has colour (FP's raster_colour: white ink has B = G = R = A)
        for (int i = 0; i < width * height * 4 && !ok; i += 4)
            if (px[i + 3] >= 16 && (px[i] + 16 < px[i + 3] || px[i + 1] + 16 < px[i + 3] || px[i + 2] + 16 < px[i + 3]))
                ok = true;
        break;
    }
    if (ok) {
        for (int y = 0; y < height; ++y)
            for (int x = 0; x < advance; ++x) {
                const unsigned char *s = px + (y * width + pad + x) * 4;
                unsigned char *d = rgba + (y * advance + x) * 4;
                unsigned a = s[3];
                if (!a) { d[0] = d[1] = d[2] = d[3] = 0; continue; }
                unsigned r = (s[2] * 255u + a / 2) / a, g = (s[1] * 255u + a / 2) / a, b = (s[0] * 255u + a / 2) / a;
                d[0] = (unsigned char)(r > 255 ? 255 : r); d[1] = (unsigned char)(g > 255 ? 255 : g);
                d[2] = (unsigned char)(b > 255 ? 255 : b); d[3] = (unsigned char)a;
            }
    }
    if (layout) layout->Release();
    if (format) format->Release();
    if (old) SelectObject(dc, old);
    if (bmp) DeleteObject(bmp);
    if (dc) DeleteDC(dc);
    return ok ? advance : -1;
}

// Whether the installed font `face` has a colour table (COLR, CBDT, sbix or SVG), once per face.
static bool ColourFont(const wchar_t *face) {
    static const wchar_t *known[48];
    static bool answer[48];
    static unsigned count;
    for (unsigned i = 0; i < count; ++i) if (known[i] == face) return answer[i];
    bool found = false;
    HDC dc = CreateCompatibleDC(0);
    if (dc) {
        HFONT f = MakeFont(face, 16, FW_NORMAL);
        HGDIOBJ oldFont = SelectObject(dc, f);
        wchar_t got[LF_FACESIZE];
        if (GetTextFaceW(dc, LF_FACESIZE, got) && lstrcmpiW(got, face) == 0) {
            static const DWORD tables[4] = { 0x524C4F43 /* COLR */, 0x54444243 /* CBDT */, 0x78696273 /* sbix */,
                                             0x20475653 /* SVG */ };
            for (unsigned t = 0; t < 4 && !found; ++t) found = GetFontData(dc, tables[t], 0, 0, 0) != GDI_ERROR;
        }
        SelectObject(dc, oldFont);
        DeleteObject(f);
        DeleteDC(dc);
    }
    if (count < 48) { known[count] = face; answer[count] = found; ++count; }
    return found;
}

// The face a whole character is drawn in colour from (src/vf2_glyph_color.colour_face_for), or 0.
static const wchar_t *ColourFaceFor(const ut::Unit &u, unsigned base) {
    unsigned n = u.ncp < ut::kMaxClusterCps ? u.ncp : ut::kMaxClusterCps;
    if (IsColourEmoji(u.cps, n)) {
        if (Mode == 2 && OverrideFace[0] && ColourFont(OverrideFace) && GlyphIndex(CmapOf(OverrideFace, FW_NORMAL), base))
            return OverrideFace;
        for (unsigned i = 0; i < kChainCount; ++i)
            if (ColourFont(kChain[i]) && GlyphIndex(CmapOf(kChain[i], FW_NORMAL), base)) return kChain[i];
        return L"Segoe UI Emoji";
    }
    const wchar_t *face = FaceFor(base);
    return face && ColourFont(face) ? face : 0;
}

// A character's colour cell (straight RGBA, lineHeight rows) at the font's em and baseline row, or -1: GDI draws it.
static int ColourGlyph(const ut::Unit &u, const FontRec &f, unsigned char *rgba, unsigned cap) {
    if (!LoadColour()) return -1;                        // without Direct2D nothing else here runs
    unsigned base = u.cps[0];
    for (unsigned i = 0; i < u.ncp && i < ut::kMaxClusterCps; ++i)
        if (!ut::IsExtend(u.cps[i]) || u.ncp == 1) { base = u.cps[i]; break; }
    const wchar_t *face = ColourFaceFor(u, base);
    if (!face) return -1;
    wchar_t text[2 * ut::kMaxClusterCps + 1];
    int units = 0;
    for (unsigned i = 0; i < u.ncp && i < ut::kMaxClusterCps; ++i) {
        unsigned cp = u.cps[i];
        if (cp >= 0x10000) {
            text[units++] = (wchar_t)(0xD800 + ((cp - 0x10000) >> 10));
            text[units++] = (wchar_t)(0xDC00 + ((cp - 0x10000) & 0x3FF));
        } else {
            text[units++] = (wchar_t)cp;
        }
    }
    text[units] = 0;
    return ColourCell(face, f.px, f.base, f.lineHeight, text, units, rgba, cap);
}
